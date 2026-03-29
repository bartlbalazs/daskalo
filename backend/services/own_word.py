"""
Service: create_own_word

Handles the full pipeline for adding a student's custom vocabulary word:
  1. Validates the raw Greek input (max 50 chars).
  2. Calls Gemini to normalise/sanitise the input and generate an English translation.
  3. Generates TTS audio via Google Cloud Text-to-Speech (Chirp3-HD female voice).
  4. Uploads the audio MP3 to GCS at users/{userId}/own_words/.
  5. Writes the word card document to Firestore users/{userId}/ownWords/.

Returns the created word card as a plain dict.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import time
from datetime import UTC, datetime

from google import genai
from google.cloud import storage, texttospeech
from google.cloud.firestore import SERVER_TIMESTAMP
from google.cloud.firestore import Client as FirestoreClient
from google.genai import types

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_INPUT_CHARS = 50
_MODEL_ID = "gemini-2.5-flash"

VOICE_FEMALE = "el-GR-Chirp3-HD-Achernar"
LANGUAGE_CODE = "el-GR"
_TTS_SPEAKING_RATE = 0.80  # Mid-range: clear but not too slow

# response_mime_type guarantees valid JSON from the model without a strict schema,
# which lets the model produce either {"greek":..,"english":..} or {"error":..}.
_NORMALISE_CONFIG = types.GenerateContentConfig(
    response_mime_type="application/json",
)

_NORMALISE_PROMPT = """\
You are a Greek language expert. A language student has entered the following Greek text:

"{input_text}"

Your task:
1. Check if this is a valid Greek word or short phrase (≤ 5 words). If it is not Greek at all, \
or is gibberish, respond with {{"error": "not_greek"}}.
2. Normalise / sanitise the input:
   - Fix obvious spelling mistakes.
   - For nouns: provide the nominative singular with the appropriate article \
(e.g. "ο δάσκαλος", "η θάλασσα", "το βιβλίο").
   - For adjectives: provide the compact format with gender endings separated by "/" with no spaces \
(e.g. "καλός/ή/ό" or "βαθύς/ιά/ύ").
   - For verbs: provide the first-person singular present indicative active \
(e.g. "μιλώ", "τρέχω").
   - For short phrases: normalise spacing and capitalisation but do not alter the meaning.
   - For proper nouns, interjections, or other invariable words: leave as-is with correct accents.
3. Provide a concise English translation (1–5 words).

Return a JSON object: {{"greek": "<normalised Greek>", "english": "<English translation>"}}
Or, if the input is not Greek: {{"error": "not_greek"}}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sanitize_greek(text: str) -> str:
    """Sanitize a Greek word/phrase for use in Firestore doc IDs and GCS paths.

    Replaces characters that are illegal or problematic in Firestore document IDs
    (forward slash) and GCS object names (forward slash interpreted as directory
    separator) with underscores.  All other Unicode characters, including Greek
    letters and accents, are preserved so that each distinct word produces a
    unique identifier.
    """
    sanitized = re.sub(r"[\s/]+", "_", text).strip("_")
    return sanitized[:80] or "word"


def _get_client() -> genai.Client:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    region = os.getenv("REGION", "europe-west1")
    logger.debug("_get_client: initialising google-genai client project=%r region=%r", project, region)
    return genai.Client(vertexai=True, project=project, location=region)


# ---------------------------------------------------------------------------
# Main service function
# ---------------------------------------------------------------------------


def create_own_word(
    raw_input: str,
    user_id: str,
    chapter_id: str,
    book_id: str,
    assets_bucket: str,
) -> dict:
    """
    Full pipeline: validate → LLM normalise → TTS → GCS upload → Firestore write.

    Returns a dict with keys: greek, english, audioUrl, chapterId, bookId, createdAt.
    Raises ValueError for invalid input or non-Greek text.
    """
    logger.info(
        "create_own_word: start — userId=%r chapterId=%r bookId=%r input=%r",
        user_id,
        chapter_id,
        book_id,
        raw_input,
    )

    # 1. Validate input length
    text = raw_input.strip()
    if not text:
        raise ValueError("Input must not be empty.")
    if len(text) > _MAX_INPUT_CHARS:
        logger.warning(
            "create_own_word: input too long — chars=%d max=%d userId=%r",
            len(text),
            _MAX_INPUT_CHARS,
            user_id,
        )
        raise ValueError(f"Input exceeds maximum allowed length of {_MAX_INPUT_CHARS} characters.")

    # 2. Normalise via Gemini
    logger.info(
        "create_own_word: calling Gemini for normalisation — model=%s input=%r userId=%r",
        _MODEL_ID,
        text,
        user_id,
    )
    client = _get_client()
    prompt = _NORMALISE_PROMPT.format(input_text=text)
    t0 = time.perf_counter()
    response = client.models.generate_content(
        model=_MODEL_ID,
        contents=prompt,
        config=_NORMALISE_CONFIG,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    logger.info(
        "create_own_word: Gemini normalisation responded — elapsed=%.0fms response_chars=%d",
        elapsed_ms,
        len(response.text),
    )
    logger.debug("create_own_word: raw Gemini normalisation response: %s", response.text)

    try:
        parsed = json.loads(response.text)
    except json.JSONDecodeError as exc:
        logger.error(
            "create_own_word: failed to parse Gemini JSON — userId=%r input=%r response=%r error=%s",
            user_id,
            text,
            response.text,
            exc,
        )
        raise ValueError("Could not process the input. Please try again.") from exc

    if "error" in parsed:
        logger.info(
            "create_own_word: Gemini flagged input as non-Greek — userId=%r input=%r error=%r",
            user_id,
            text,
            parsed.get("error"),
        )
        raise ValueError("The input does not appear to be a Greek word or phrase.")

    greek: str = parsed.get("greek", "").strip()
    english: str = parsed.get("english", "").strip()

    if not greek or not english:
        logger.error(
            "create_own_word: Gemini returned incomplete fields — userId=%r parsed=%r",
            user_id,
            parsed,
        )
        raise ValueError("Could not generate a valid word card. Please try again.")

    logger.info(
        "create_own_word: normalisation complete — greek=%r english=%r userId=%r",
        greek,
        english,
        user_id,
    )

    # 3. Generate TTS audio
    # Extract main form only (e.g. "καλός/ή/ό" → "καλός"), matching CLI behaviour.
    tts_text = re.split(r"\s*/\s*|\s+-\s*", greek)[0].strip()
    logger.info(
        "create_own_word: generating TTS audio — tts_text=%r voice=%s userId=%r",
        tts_text,
        VOICE_FEMALE,
        user_id,
    )
    tts_client = texttospeech.TextToSpeechClient()
    synthesis_input = texttospeech.SynthesisInput(text=tts_text)
    voice = texttospeech.VoiceSelectionParams(
        language_code=LANGUAGE_CODE,
        name=VOICE_FEMALE,
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=_TTS_SPEAKING_RATE,
    )
    t0 = time.perf_counter()
    tts_response = tts_client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config,
    )
    tts_elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.info(
        "create_own_word: TTS complete — elapsed=%.0fms audio_bytes=%d userId=%r",
        tts_elapsed_ms,
        len(tts_response.audio_content),
        user_id,
    )

    # 4. Upload to GCS
    sanitized = _sanitize_greek(greek)
    filename = f"{chapter_id}__{sanitized}.mp3"
    gcs_path = f"users/{user_id}/own_words/{filename}"

    logger.info(
        "create_own_word: uploading audio to GCS — bucket=%r path=%s userId=%r",
        assets_bucket,
        gcs_path,
        user_id,
    )
    gcs_client = storage.Client()
    bucket = gcs_client.bucket(assets_bucket)
    blob = bucket.blob(gcs_path)
    blob.cache_control = "public, max-age=31536000"
    blob.content_type = "audio/mpeg"

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp.write(tts_response.audio_content)
        tmp_path = tmp.name

    try:
        t0 = time.perf_counter()
        blob.upload_from_filename(tmp_path)
        gcs_elapsed_ms = (time.perf_counter() - t0) * 1000
    finally:
        os.unlink(tmp_path)

    audio_url = f"gs://{assets_bucket}/{gcs_path}"
    logger.info(
        "create_own_word: GCS upload complete — elapsed=%.0fms url=%s userId=%r",
        gcs_elapsed_ms,
        audio_url,
        user_id,
    )

    # 5. Write to Firestore
    # NOTE: sanitized Greek (slashes/spaces → underscores) is used for the doc ID to
    # avoid Firestore treating slashes in Greek text (e.g. "ήσυχος / ήσυχη / ήσυχο")
    # as subcollection separators, while still preserving uniqueness per word.
    db = FirestoreClient(database=os.getenv("FIRESTORE_DB", "(default)"))
    doc_id = f"{chapter_id}__{sanitized}"
    word_doc = {
        "greek": greek,
        "english": english,
        "audioUrl": audio_url,
        "chapterId": chapter_id,
        "bookId": book_id,
        "createdAt": SERVER_TIMESTAMP,
    }
    logger.info(
        "create_own_word: writing to Firestore — collection=users/%s/ownWords docId=%s",
        user_id,
        doc_id,
    )
    db.collection("users").document(user_id).collection("ownWords").document(doc_id).set(word_doc)

    logger.info(
        "create_own_word: done — greek=%r english=%r docId=%s userId=%r audioUrl=%s",
        greek,
        english,
        doc_id,
        user_id,
        audio_url,
    )

    # Return serialisable version (SERVER_TIMESTAMP isn't JSON-serialisable)
    return {
        "greek": greek,
        "english": english,
        "audioUrl": audio_url,
        "chapterId": chapter_id,
        "bookId": book_id,
        "docId": doc_id,
        "alreadyExisted": False,
        "createdAt": datetime.now(tz=UTC).isoformat(),
    }
