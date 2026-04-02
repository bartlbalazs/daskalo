"""
Shared media generation helpers — TTS synthesis and image generation.

Used by both generate_media (chapter pipeline) and generate_practice_media
(practice-set pipeline) to avoid duplicating Cloud TTS and Vertex AI logic.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from google import genai
from google.cloud import texttospeech
from google.genai import types

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


def generate_image(scene_description: str, output_path: str) -> bool:
    """Call Gemini image generation (gemini-3-pro-image-preview).

    The model is loaded from the ``global`` region as required.
    Image bytes are written directly to *output_path* as JPEG.

    Retries up to 7 times (8 attempts total) on transient quota/availability
    errors (HTTP 429 / 503) using the google-genai SDK's built-in exponential
    backoff (15 s initial, up to 180 s, with jitter to desync parallel workers).

    Returns ``True`` on success, ``False`` on any failure.
    """
    project = os.environ["GOOGLE_CLOUD_PROJECT"]

    try:
        client = genai.Client(
            vertexai=True,
            project=project,
            location=IMAGE_REGION,
            http_options=types.HttpOptions(
                api_version="v1",
                retry_options=types.HttpRetryOptions(
                    attempts=8,
                    initial_delay=15.0,
                    max_delay=180.0,
                    exp_base=2,
                    jitter=30.0,
                    http_status_codes=[429, 503],
                ),
            ),
        )
        prompt = IMAGE_GENERATION_PROMPT_TEMPLATE.format(scene_description=scene_description)
        response = client.models.generate_content(
            model=IMAGE_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                image_data = part.inline_data.data
                Path(output_path).write_bytes(image_data)
                logger.debug("Generated image: %s", output_path)
                return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Image generation failed: %s", exc)
        return False

    logger.error("Gemini returned no image data for prompt: %s", scene_description[:60])
    return False
