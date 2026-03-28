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
from datetime import UTC, datetime

import vertexai
from google.cloud import storage, texttospeech
from google.cloud.firestore import SERVER_TIMESTAMP
from google.cloud.firestore import Client as FirestoreClient
from vertexai.generative_models import GenerativeModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_INPUT_CHARS = 50

VOICE_FEMALE = "el-GR-Chirp3-HD-Achernar"
LANGUAGE_CODE = "el-GR"
_TTS_SPEAKING_RATE = 0.80  # Mid-range: clear but not too slow

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

Respond ONLY with a valid JSON object in this exact format (no markdown fences):
{{"greek": "<normalised Greek>", "english": "<English translation>"}}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_filename(text: str) -> str:
    """Convert Greek text to a safe ASCII filename slug."""
    # Strip Greek accents (NFD decomposition + strip combining chars)
    import unicodedata

    nfd = unicodedata.normalize("NFD", text)
    ascii_text = nfd.encode("ascii", "ignore").decode("ascii")
    # Lowercase and replace non-alphanum with underscores
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")
    return slug[:40] or "word"


def _get_gemini_model() -> GenerativeModel:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    region = os.getenv("REGION", "europe-west1")
    vertexai.init(project=project, location=region)
    return GenerativeModel("gemini-2.5-flash")


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
    # 1. Validate input length
    text = raw_input.strip()
    if not text:
        raise ValueError("Input must not be empty.")
    if len(text) > _MAX_INPUT_CHARS:
        raise ValueError(f"Input exceeds maximum allowed length of {_MAX_INPUT_CHARS} characters.")

    # 2. Normalise via Gemini
    model = _get_gemini_model()
    prompt = _NORMALISE_PROMPT.format(input_text=text)
    response = model.generate_content(prompt)
    raw_json = response.text.strip().removeprefix("```json").removesuffix("```").strip()

    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        logger.warning("Gemini returned non-JSON response: %r", response.text)
        raise ValueError("Could not process the input. Please try again.") from exc

    if "error" in parsed:
        raise ValueError("The input does not appear to be a Greek word or phrase.")

    greek: str = parsed.get("greek", "").strip()
    english: str = parsed.get("english", "").strip()

    if not greek or not english:
        raise ValueError("Could not generate a valid word card. Please try again.")

    # 3. Generate TTS audio
    # Extract main form only (e.g. "καλός/ή/ό" → "καλός"), matching CLI behaviour.
    tts_text = re.split(r"\s*/\s*|\s+-\s*", greek)[0].strip()
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
    tts_response = tts_client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config,
    )

    # 4. Upload to GCS
    safe_name = _safe_filename(greek)
    filename = f"{chapter_id}__{safe_name}.mp3"
    gcs_path = f"users/{user_id}/own_words/{filename}"

    gcs_client = storage.Client()
    bucket = gcs_client.bucket(assets_bucket)
    blob = bucket.blob(gcs_path)
    blob.cache_control = "public, max-age=31536000"
    blob.content_type = "audio/mpeg"

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp.write(tts_response.audio_content)
        tmp_path = tmp.name

    try:
        blob.upload_from_filename(tmp_path)
    finally:
        os.unlink(tmp_path)

    audio_url = f"gs://{assets_bucket}/{gcs_path}"
    logger.info("Uploaded own-word audio to %s", audio_url)

    # 5. Write to Firestore
    # NOTE: safe_name (ASCII slug) is used for the doc ID to avoid Firestore treating
    # slashes in Greek text (e.g. "ήσυχος / ήσυχη / ήσυχο") as subcollection separators.
    db = FirestoreClient(database=os.getenv("FIRESTORE_DB", "(default)"))
    doc_id = f"{chapter_id}__{safe_name}"
    word_doc = {
        "greek": greek,
        "english": english,
        "audioUrl": audio_url,
        "chapterId": chapter_id,
        "bookId": book_id,
        "createdAt": SERVER_TIMESTAMP,
    }
    db.collection("users").document(user_id).collection("ownWords").document(doc_id).set(word_doc)
    logger.info("Saved own word '%s' for user '%s'", greek, user_id)

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
