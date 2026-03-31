"""
Node: generate_media
Generates audio (Google Cloud Text-to-Speech) and images (Vertex AI) for the lesson content.

Audio output:
  - One .mp3 per vocabulary word (alternating male/female Chirp3-HD voices, book-scaled rate)
  - One .mp3 for the full reading passage (Chirp3-HD female narrator, speed scaled by book)
  - One .mp3 per sentence of the passage (same voice + speed as full passage)
    - referenced by listening_comprehension and dictation exercises via sentence_index
  - One .mp3 per grammar example sentence (Chirp3-HD female narrator, book-scaled rate)
    - named {prefix}grammar_{noteIdx:02d}_ex_{exIdx:02d}.mp3; stored on each GrammarExample.audioPath
  - One dedicated .mp3 per pronunciation_practice exercise target_text (Chirp3-HD female narrator)
  - One .mp3 per conversation line (male/female speaker as specified by the exercise)

Voice selection:
  - Vocabulary words: el-GR-Chirp3-HD-Achernar (female) / el-GR-Chirp3-HD-Charon (male), alternating
  - Narration (passage, sentences, pronunciation, grammar): el-GR-Chirp3-HD-Achernar (female)
  - Conversation male lines: el-GR-Chirp3-HD-Charon (male)
  - Conversation female lines: el-GR-Chirp3-HD-Achernar (female)

Passage/sentence/vocab/grammar speaking rate (scaled by book to help beginners):
  - Book 1 : 0.70x
  - Book 2 : 0.80x
  - Book 3 : 0.88x
  - Book 4+ : 1.00x (normal speed)

Vocab TTS text: alternative gender endings are stripped before synthesis
  (e.g. "ο/η δάσκαλος / -α" → "ο δάσκαλος").

Asset naming:
  All generated asset filenames are prefixed with "{variant_id}_{chapter_order:02d}_" to ensure
  assets from different chapter versions never overwrite each other in Cloud Storage.

Image output:
  - {prefix}chapter_cover.jpg  — cover image for the chapter (from chapter_image_prompt)
  - {prefix}grammar_note_{idx:02d}.jpg — one image per grammar note that provided an image_prompt
  - {prefix}exercise_image_{idx:02d}.jpg — one per image_description exercise
"""

import logging
import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import vertexai
from google.cloud import texttospeech
from vertexai.generative_models import GenerationConfig, GenerativeModel

from models.content_models import (
    ConversationExercise,
    GrammarNote,
    ImageDescriptionExercise,
    MatchingExercise,
    PassageSentence,
    PronunciationPracticeExercise,
)
from prompts.content_prompts import IMAGE_GENERATION_PROMPT_TEMPLATE
from state import ContentState

logger = logging.getLogger(__name__)

# --- Voice constants ---------------------------------------------------------
# Vocabulary: Chirp3-HD for highest quality pronunciation (alternating M/F)
VOICE_FEMALE = "el-GR-Chirp3-HD-Achernar"
VOICE_MALE = "el-GR-Chirp3-HD-Charon"
# Narration: Chirp3-HD for highest quality passage/sentence/pronunciation/grammar audio
VOICE_NARRATOR = "el-GR-Chirp3-HD-Achernar"
LANGUAGE_CODE = "el-GR"

IMAGE_MODEL = "gemini-3-pro-image-preview"
IMAGE_REGION = "global"

# --- Passage speaking rate by book ------------------------------------------
# Slower rates help beginners; normalises to 1.0 at Book 4+.
_BOOK_SPEAKING_RATE: dict[str, float] = {
    "b1": 0.70,
    "b2": 0.80,
    "b3": 0.88,
}
_DEFAULT_SPEAKING_RATE = 1.00


def _passage_rate(book_id: str) -> float:
    """Return the speaking rate for passage / sentence audio based on the book."""
    # book_id may be "b1", "book_1", "p1", "phase_1", etc. — normalise to "bN".
    key = book_id.lower()
    key = key.replace("book_", "b").replace("book", "b")
    key = key.replace("phase_", "b").replace("phase", "b")
    key = re.sub(r"^p(\d+)$", r"b\1", key)  # legacy "p1" → "b1"
    return _BOOK_SPEAKING_RATE.get(key, _DEFAULT_SPEAKING_RATE)


_TTS_MAX_WORKERS = 10
_IMAGE_MAX_WORKERS = 5


def generate_media(state: ContentState) -> dict:
    """LangGraph node — generate audio and image assets for the lesson."""
    work_dir = state.get("work_dir") or tempfile.mkdtemp(prefix="daskalo_")
    Path(work_dir).mkdir(parents=True, exist_ok=True)

    # Asset filename prefix: {variant_id}_{chapter_order:02d}_ ensures unique names per chapter version
    variant_id = state.get("variant_id", "unknown")
    chapter_order = state.get("chapter_order", 0)
    prefix = f"{variant_id}_{chapter_order:02d}_"

    book_id: str = state.get("book_id", "")
    narration_rate = _passage_rate(book_id)

    narrator_gender = state.get("narrator_gender", "female")
    narrator_voice = VOICE_MALE if narrator_gender == "male" else VOICE_FEMALE
    logger.info("Book '%s' - passage speaking rate %.2f, voice gender: %s", book_id, narration_rate, narrator_gender)

    audio_files: list[str] = []
    sentence_audio_files: list[str] = []
    image_files: list[str] = []
    chapter_image_path: str = ""

    vocabulary = state.get("vocabulary", [])
    exercises = state.get("exercises", [])
    image_prompts = state.get("image_prompts", [])
    grammar_notes: list[GrammarNote] = state.get("grammar_notes", [])
    passage: list[PassageSentence] = state.get("passage", [])

    # Pre-existing audio map: greek_text -> local_path (populated for practice-set re-generation
    # when the source chapter ZIP has already been extracted). Keys are the original Greek strings.
    existing_audio: dict[str, str] = state.get("existing_audio", {})  # type: ignore[assignment]

    # -----------------------------------------------------------------------
    # Build TTS task list — each entry is (text, voice, output_path, rate, callback)
    # callback is called with output_path on success to mutate the model + track the file.
    # -----------------------------------------------------------------------

    # We collect tasks as (text, voice, path, rate) tuples and submit them all at once.
    # After completion we sort results back into the appropriate buckets.

    tts_tasks: list[tuple[str, str, str, float, str]] = []  # (text, voice, path, rate, category)
    # category: "audio" | "sentence:{idx}" | "pronunciation" | "conv:{exercise_idx}:{line_idx}"

    # --- 1. Vocabulary audio (alternating male/female, book-scaled rate) ---
    for idx, vocab_item in enumerate(vocabulary):
        greek_text = vocab_item.greek
        if not greek_text:
            continue
        tts_text = re.split(r"\s*/\s*|\s+-\s*", greek_text)[0].strip()

        # Reuse existing audio from a source ZIP if available (practice-set re-use)
        if tts_text in existing_audio:
            existing_path = existing_audio[tts_text]
            vocab_item.audioPath = existing_path
            audio_files.append(existing_path)
            logger.debug("Reusing existing vocab audio for '%s': %s", tts_text, existing_path)
            continue

        voice = VOICE_FEMALE if idx % 2 == 0 else VOICE_MALE
        safe_name = re.sub(r"[^\w]", "_", tts_text)[:30]
        out_path = str(Path(work_dir) / f"{prefix}vocab_{idx:02d}_{safe_name}.mp3")
        tts_tasks.append((tts_text, voice, out_path, narration_rate, f"vocab:{idx}"))

    # --- 2. Full passage audio ---
    if passage:
        full_greek = " ".join([p.greek for p in passage])
        passage_out = str(Path(work_dir) / f"{prefix}passage.mp3")
        tts_tasks.append((full_greek, narrator_voice, passage_out, narration_rate, "audio"))

    # --- 3. Per-sentence audio ---
    for idx, sentence_obj in enumerate(passage):
        sentence = sentence_obj.greek
        if not sentence:
            continue
        safe_name = re.sub(r"[^\w]", "_", sentence)[:30]
        out_path = str(Path(work_dir) / f"{prefix}sentence_{idx:02d}_{safe_name}.mp3")
        tts_tasks.append((sentence, narrator_voice, out_path, narration_rate, f"sentence:{idx}"))

    # --- 4. Grammar example sentences audio — one file per example (female default) ---
    for note_idx, note in enumerate(grammar_notes):
        for ex_idx, example in enumerate(note.examples):
            if not example.greek:
                continue
            out_path = str(Path(work_dir) / f"{prefix}grammar_{note_idx:02d}_ex_{ex_idx:02d}.mp3")
            tts_tasks.append((example.greek, VOICE_FEMALE, out_path, narration_rate, f"grammar:{note_idx}:{ex_idx}"))

    # --- 5. Pronunciation practice target text audio (female default) ---
    for idx, exercise in enumerate(exercises):
        if exercise.type != "pronunciation_practice":
            continue
        target_text = exercise.data.target_text
        if not target_text:
            continue
        safe_name = re.sub(r"[^\w]", "_", target_text)[:30]
        out_path = str(Path(work_dir) / f"{prefix}pronunciation_{idx:02d}_{safe_name}.mp3")
        tts_tasks.append((target_text, VOICE_FEMALE, out_path, 1.0, f"pronunciation:{idx}"))

    # --- 6. Conversation exercise audio ---
    for ex_idx, exercise in enumerate(exercises):
        if not isinstance(exercise, ConversationExercise):
            continue
        for line_idx, line in enumerate(exercise.data.lines):
            if not line.text:
                continue
            voice = VOICE_MALE if line.speaker == "male" else VOICE_FEMALE
            safe_text = re.sub(r"[^\w]", "_", line.text)[:20]
            out_path = str(
                Path(work_dir) / f"{prefix}conv_{ex_idx:02d}_line_{line_idx:02d}_{line.speaker}_{safe_text}.mp3"
            )
            tts_tasks.append((line.text, voice, out_path, 1.0, f"conv:{ex_idx}:{line_idx}"))

    # --- 7. Matching exercise — audio for each Greek word (click-to-listen) ---
    for ex_idx, exercise in enumerate(exercises):
        if not isinstance(exercise, MatchingExercise):
            continue
        for pair_idx, pair in enumerate(exercise.data.pairs):
            if not pair.greek:
                continue
            tts_text = re.split(r"\s*/\s*|\s+-\s*", pair.greek)[0].strip()

            # Reuse existing audio if available
            if tts_text in existing_audio:
                pair.audioPath = existing_audio[tts_text]  # type: ignore[attr-defined]
                audio_files.append(existing_audio[tts_text])
                logger.debug("Reusing existing matching audio for '%s'", tts_text)
                continue

            safe_name = re.sub(r"[^\w]", "_", tts_text)[:30]
            out_path = str(Path(work_dir) / f"{prefix}matching_{ex_idx:02d}_pair_{pair_idx:02d}_{safe_name}.mp3")
            tts_tasks.append((tts_text, VOICE_FEMALE, out_path, narration_rate, f"matching:{ex_idx}:{pair_idx}"))

    # -----------------------------------------------------------------------
    # Execute all TTS tasks in parallel
    # -----------------------------------------------------------------------
    tts_results: dict[str, str | None] = {}  # category_key → path (or None on failure)

    def _run_tts(task):
        text, voice, path, rate, category = task
        success = _synthesize_speech(text, voice, path, speaking_rate=rate)
        return category, path if success else None

    with ThreadPoolExecutor(max_workers=_TTS_MAX_WORKERS) as executor:
        futures = {executor.submit(_run_tts, t): t for t in tts_tasks}
        for future in as_completed(futures):
            category, result_path = future.result()
            tts_results[category] = result_path

    # -----------------------------------------------------------------------
    # Apply TTS results back to models and file lists
    # -----------------------------------------------------------------------

    # Vocab
    for idx, vocab_item in enumerate(vocabulary):
        path = tts_results.get(f"vocab:{idx}")
        if path:
            audio_files.append(path)
            vocab_item.audioPath = path

    # Full passage
    passage_path = tts_results.get("audio")
    if passage_path:
        audio_files.append(passage_path)

    # Per-sentence (keep index alignment)
    for idx in range(len(passage)):
        path = tts_results.get(f"sentence:{idx}")
        sentence_audio_files.append(path or "")

    # Grammar notes — assign per-example audio paths
    for note_idx, note in enumerate(grammar_notes):
        for ex_idx, example in enumerate(note.examples):
            path = tts_results.get(f"grammar:{note_idx}:{ex_idx}")
            if path:
                audio_files.append(path)
                example.audioPath = path

    # Pronunciation
    for idx, exercise in enumerate(exercises):
        if not isinstance(exercise, PronunciationPracticeExercise):
            continue
        path = tts_results.get(f"pronunciation:{idx}")
        if path:
            audio_files.append(path)
            exercise.audioPath = path

    # Conversation lines
    for ex_idx, exercise in enumerate(exercises):
        if not isinstance(exercise, ConversationExercise):
            continue
        for line_idx, line in enumerate(exercise.data.lines):
            path = tts_results.get(f"conv:{ex_idx}:{line_idx}")
            if path:
                audio_files.append(path)
                line.audioPath = path
            else:
                line.audioPath = None

    # Matching pair audio
    for ex_idx, exercise in enumerate(exercises):
        if not isinstance(exercise, MatchingExercise):
            continue
        for pair_idx, pair in enumerate(exercise.data.pairs):
            path = tts_results.get(f"matching:{ex_idx}:{pair_idx}")
            if path:
                audio_files.append(path)
                pair.audioPath = path  # type: ignore[attr-defined]

    # -----------------------------------------------------------------------
    # Image generation tasks — also parallelised
    # -----------------------------------------------------------------------

    image_tasks: list[tuple[str, str, str]] = []  # (scene_description, output_path, category)

    # Cover image
    cover_prompt = state.get("chapter_image_prompt", "")
    if cover_prompt:
        cover_path = str(Path(work_dir) / f"{prefix}chapter_cover.jpg")
        image_tasks.append((cover_prompt, cover_path, "cover"))
    else:
        logger.warning("No chapter_image_prompt provided — skipping cover image generation.")

    # Grammar note images
    for idx, note in enumerate(grammar_notes):
        if not note.image_prompt:
            continue
        out_path = str(Path(work_dir) / f"{prefix}grammar_note_{idx:02d}.jpg")
        image_tasks.append((note.image_prompt, out_path, f"grammar_img:{idx}"))

    # Exercise images
    prompt_by_index = {ip.exercise_index: ip.prompt for ip in image_prompts}
    for idx, exercise in enumerate(exercises):
        if not isinstance(exercise, ImageDescriptionExercise):
            continue
        image_prompt_text = prompt_by_index.get(idx, "")
        if not image_prompt_text:
            logger.warning("No image prompt found for image_description exercise at index %d — skipping.", idx)
            continue
        out_path = str(Path(work_dir) / f"{prefix}exercise_image_{idx:02d}.jpg")
        image_tasks.append((image_prompt_text, out_path, f"exercise_img:{idx}"))

    image_results: dict[str, str | None] = {}

    def _run_image(task):
        scene, path, category = task
        success = _generate_image(scene, path, state)
        return category, path if success else None

    with ThreadPoolExecutor(max_workers=_IMAGE_MAX_WORKERS) as executor:
        futures = {executor.submit(_run_image, t): t for t in image_tasks}
        for future in as_completed(futures):
            category, result_path = future.result()
            image_results[category] = result_path

    # Apply image results
    if "cover" in image_results and image_results["cover"]:
        chapter_image_path = image_results["cover"]

    for idx, note in enumerate(grammar_notes):
        path = image_results.get(f"grammar_img:{idx}")
        if path:
            image_files.append(path)
            note.imagePath = path

    for idx, exercise in enumerate(exercises):
        if not isinstance(exercise, ImageDescriptionExercise):
            continue
        path = image_results.get(f"exercise_img:{idx}")
        if path:
            image_files.append(path)
            exercise.imagePath = path

    tts_failures = sum(1 for v in tts_results.values() if v is None)
    logger.info(
        "TTS complete — %d audio files generated%s",
        len(audio_files) + len([p for p in sentence_audio_files if p]),
        f" ({tts_failures} failed)" if tts_failures else "",
    )

    image_names = [Path(p).name for p in image_results.values() if p]
    if image_names:
        logger.info("Images complete — %s", ", ".join(image_names))

    logger.info(
        "Media generation complete: %d audio, %d sentence clips, %d image files, cover=%s.",
        len(audio_files),
        len(sentence_audio_files),
        len(image_files),
        "yes" if chapter_image_path else "no",
    )
    return {
        "work_dir": work_dir,
        "audio_files": audio_files,
        "sentence_audio_files": sentence_audio_files,
        "image_files": image_files,
        "chapter_image_path": chapter_image_path,
        "vocabulary": vocabulary,
        "exercises": exercises,
        "grammar_notes": grammar_notes,
        "passage": passage,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _synthesize_speech(
    text: str,
    voice_name: str,
    output_path: str,
    speaking_rate: float = 1.0,
) -> bool:
    """Synthesize Greek speech via Google Cloud TTS and write MP3 to output_path.

    Uses Chirp3-HD voices for the highest quality.
    speaking_rate < 1.0 slows down delivery (useful for early-phase passage audio).

    Returns True on success, False on any failure.
    """
    try:
        client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code=LANGUAGE_CODE,
            name=voice_name,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=speaking_rate,
        )
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config,
        )
        Path(output_path).write_bytes(response.audio_content)
        logger.debug("Generated audio: %s (rate=%.2f)", output_path, speaking_rate)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Cloud TTS synthesis failed for '%s' (voice=%s): %s", text[:40], voice_name, exc)
        return False


def _generate_image(scene_description: str, output_path: str, state: ContentState) -> bool:
    """Call Gemini image generation (gemini-3-pro-image-preview). Returns True on success.

    The model is loaded from the 'global' region as required for this model.
    Image bytes are written directly to output_path as JPEG.
    No resizing is applied — the image is saved at whatever resolution Gemini returns.
    """
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    try:
        vertexai.init(project=project, location=IMAGE_REGION)
        model = GenerativeModel(IMAGE_MODEL)
        prompt = IMAGE_GENERATION_PROMPT_TEMPLATE.format(scene_description=scene_description)
        response = model.generate_content(
            prompt,
            generation_config=GenerationConfig(response_modalities=["IMAGE"]),
        )
        # Extract image bytes from the first image part in the response.
        image_data: bytes | None = None
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                image_data = part.inline_data.data
                break

        if not image_data:
            logger.error("Gemini returned no image data for prompt: %s", scene_description[:60])
            return False

        Path(output_path).write_bytes(image_data)
        logger.debug("Generated image: %s", output_path)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Image generation failed: %s", exc)
        return False
