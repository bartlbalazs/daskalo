"""
Shared media generation helpers — TTS synthesis and image generation.

Used by both generate_media (chapter pipeline) and generate_practice_media
(practice-set pipeline) to avoid duplicating Cloud TTS and Vertex AI logic.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import vertexai
from google.api_core import exceptions as google_exceptions
from google.cloud import texttospeech
from tenacity import before_sleep_log, retry, retry_if_exception, stop_after_attempt, wait_exponential, wait_random
from vertexai.generative_models import GenerationConfig, GenerativeModel

from prompts.content_prompts import IMAGE_GENERATION_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)

# --- Voice / model constants ------------------------------------------------
VOICE_FEMALE = "el-GR-Chirp3-HD-Achernar"
VOICE_MALE = "el-GR-Chirp3-HD-Charon"
LANGUAGE_CODE = "el-GR"

IMAGE_MODEL = "gemini-3-pro-image-preview"
IMAGE_REGION = "global"


def synthesize_speech(
    text: str,
    voice_name: str,
    output_path: str,
    speaking_rate: float = 1.0,
) -> bool:
    """Synthesize Greek speech via Google Cloud TTS and write MP3 to *output_path*.

    Uses Chirp3-HD voices for the highest quality.
    ``speaking_rate`` < 1.0 slows down delivery (useful for early-phase audio).

    Returns ``True`` on success, ``False`` on any failure.
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


def _is_retryable_image_error(exc: BaseException) -> bool:
    """Return True for transient Google API errors that warrant a retry (429, 503)."""
    if isinstance(exc, (google_exceptions.ResourceExhausted, google_exceptions.ServiceUnavailable)):
        return True
    # Fallback: check string representation for cases where the SDK wraps the error differently.
    msg = str(exc)
    return "429" in msg or "503" in msg or "Resource has been exhausted" in msg


def generate_image(scene_description: str, output_path: str) -> bool:
    """Call Gemini image generation (gemini-3-pro-image-preview).

    The model is loaded from the ``global`` region as required.
    Image bytes are written directly to *output_path* as JPEG.

    Retries up to 7 times (8 attempts total) on transient quota/availability
    errors (HTTP 429 / 503) using exponential backoff (15 s → 30 s → 60 s →
    120 s → 180 s, capped) plus 0–30 s of random jitter to desync parallel
    workers.

    Returns ``True`` on success, ``False`` on any failure.
    """
    project = os.environ["GOOGLE_CLOUD_PROJECT"]

    @retry(
        retry=retry_if_exception(_is_retryable_image_error),
        stop=stop_after_attempt(8),
        wait=wait_exponential(multiplier=2, min=15, max=180) + wait_random(0, 30),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _call_api() -> bytes | None:
        vertexai.init(project=project, location=IMAGE_REGION)
        model = GenerativeModel(IMAGE_MODEL)
        prompt = IMAGE_GENERATION_PROMPT_TEMPLATE.format(scene_description=scene_description)
        response = model.generate_content(
            prompt,
            generation_config=GenerationConfig(response_modalities=["IMAGE"]),
        )
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                return part.inline_data.data
        return None

    try:
        image_data = _call_api()
    except Exception as exc:  # noqa: BLE001
        logger.error("Image generation failed: %s", exc)
        return False

    if not image_data:
        logger.error("Gemini returned no image data for prompt: %s", scene_description[:60])
        return False

    Path(output_path).write_bytes(image_data)
    logger.debug("Generated image: %s", output_path)
    return True
