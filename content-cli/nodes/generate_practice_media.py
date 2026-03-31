"""
Node: generate_practice_media
Generates audio and images for a Practice Set.

Reuses audio for vocabulary words that already exist in the source chapter ZIP
(populated in state["existing_audio"]). Only calls Cloud TTS for net-new words
(e.g. matching pairs from previous chapters or new conversation lines).

Identical asset naming and output contract as generate_media, but:
  - No passage, sentence, or grammar audio (practice sets have none).
  - Only generates audio for: matching pairs, conversation lines.
  - Generates images for: cover image, image_description exercises.
"""

import logging
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from models.content_models import (
    ConversationExercise,
    ImageDescriptionExercise,
    MatchingExercise,
)
from utils.media_utils import (
    VOICE_FEMALE,
    VOICE_MALE,
    generate_image,
    synthesize_speech,
)

logger = logging.getLogger(__name__)

_BOOK_SPEAKING_RATE: dict[str, float] = {"b1": 0.70, "b2": 0.80, "b3": 0.88}
_DEFAULT_SPEAKING_RATE = 1.00
_TTS_MAX_WORKERS = 10
_IMAGE_MAX_WORKERS = 5


def _rate(book_id: str) -> float:
    key = book_id.lower()
    key = key.replace("book_", "b").replace("book", "b")
    key = key.replace("phase_", "b").replace("phase", "b")
    key = re.sub(r"^p(\d+)$", r"b\1", key)
    return _BOOK_SPEAKING_RATE.get(key, _DEFAULT_SPEAKING_RATE)


def generate_practice_media(state: dict) -> dict:
    """LangGraph node — generate audio and images for a Practice Set."""
    work_dir = state.get("work_dir") or tempfile.mkdtemp(prefix="daskalo_practice_")
    Path(work_dir).mkdir(parents=True, exist_ok=True)

    practice_set_id = state.get("practice_set_id", "unknown")
    chapter_order = state.get("chapter_order", 0)
    prefix = f"{practice_set_id}_{chapter_order:02d}_"

    book_id: str = state.get("book_id", "")
    narration_rate = _rate(book_id)

    exercises = state.get("exercises", [])
    image_prompts = state.get("image_prompts", [])
    existing_audio: dict[str, str] = state.get("existing_audio", {})

    audio_files: list[str] = []
    image_files: list[str] = []
    chapter_image_path: str = ""

    tts_tasks: list[tuple[str, str, str, float, str]] = []

    # --- Matching pairs (click-to-listen) ---
    for ex_idx, exercise in enumerate(exercises):
        if not isinstance(exercise, MatchingExercise):
            continue
        for pair_idx, pair in enumerate(exercise.data.pairs):
            if not pair.greek:
                continue
            tts_text = re.split(r"\s*/\s*|\s+-\s*", pair.greek)[0].strip()
            if tts_text in existing_audio:
                pair.audioPath = existing_audio[tts_text]
                audio_files.append(existing_audio[tts_text])
                logger.debug("Reusing existing audio for matching pair '%s'", tts_text)
                continue
            safe_name = re.sub(r"[^\w]", "_", tts_text)[:30]
            out_path = str(Path(work_dir) / f"{prefix}matching_{ex_idx:02d}_pair_{pair_idx:02d}_{safe_name}.mp3")
            tts_tasks.append((tts_text, VOICE_FEMALE, out_path, narration_rate, f"matching:{ex_idx}:{pair_idx}"))

    # --- Conversation lines ---
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

    # Execute TTS in parallel
    tts_results: dict[str, str | None] = {}

    def _run_tts(task):
        text, voice, path, rate, category = task
        success = synthesize_speech(text, voice, path, speaking_rate=rate)
        return category, path if success else None

    with ThreadPoolExecutor(max_workers=_TTS_MAX_WORKERS) as executor:
        futures = {executor.submit(_run_tts, t): t for t in tts_tasks}
        for future in as_completed(futures):
            category, result_path = future.result()
            tts_results[category] = result_path

    # Apply TTS results
    for ex_idx, exercise in enumerate(exercises):
        if not isinstance(exercise, MatchingExercise):
            continue
        for pair_idx, pair in enumerate(exercise.data.pairs):
            path = tts_results.get(f"matching:{ex_idx}:{pair_idx}")
            if path:
                audio_files.append(path)
                pair.audioPath = path

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

    tts_failures = sum(1 for v in tts_results.values() if v is None)
    logger.info(
        "Practice TTS complete — %d audio files%s",
        len(audio_files),
        f" ({tts_failures} failed)" if tts_failures else "",
    )

    # --- Images ---
    image_tasks: list[tuple[str, str, str]] = []

    cover_prompt = state.get("chapter_image_prompt", "")
    if cover_prompt:
        cover_path = str(Path(work_dir) / f"{prefix}practice_cover.jpg")
        image_tasks.append((cover_prompt, cover_path, "cover"))

    prompt_by_index = {ip.exercise_index: ip.prompt for ip in image_prompts}
    for idx, exercise in enumerate(exercises):
        if not isinstance(exercise, ImageDescriptionExercise):
            continue
        prompt_text = prompt_by_index.get(idx, "")
        if not prompt_text:
            continue
        out_path = str(Path(work_dir) / f"{prefix}exercise_image_{idx:02d}.jpg")
        image_tasks.append((prompt_text, out_path, f"exercise_img:{idx}"))

    image_results: dict[str, str | None] = {}

    def _run_image(task):
        scene, path, category = task
        success = generate_image(scene, path)
        return category, path if success else None

    with ThreadPoolExecutor(max_workers=_IMAGE_MAX_WORKERS) as executor:
        futures = {executor.submit(_run_image, t): t for t in image_tasks}
        for future in as_completed(futures):
            category, result_path = future.result()
            image_results[category] = result_path

    if image_results.get("cover"):
        chapter_image_path = image_results["cover"]

    for idx, exercise in enumerate(exercises):
        if not isinstance(exercise, ImageDescriptionExercise):
            continue
        path = image_results.get(f"exercise_img:{idx}")
        if path:
            image_files.append(path)
            exercise.imagePath = path

    image_names = [Path(p).name for p in image_results.values() if p]
    if image_names:
        logger.info("Practice images complete — %s", ", ".join(image_names))

    return {
        "work_dir": work_dir,
        "audio_files": audio_files,
        "image_files": image_files,
        "chapter_image_path": chapter_image_path,
        "exercises": exercises,
    }
