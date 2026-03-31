"""
Shared helpers for Firestore/Storage ingest (local and remote).

Provides:
  _upload_asset(zf, asset_path, chapter_id, bucket) -> str
      Reads a file from an open ZipFile and uploads it to the given GCS bucket.
      Returns the gs:// URI.

  _guess_content_type(filename) -> str
      Maps common media file extensions to MIME types.

  process_chapter_assets(zf, chapter, chapter_id, assets_bucket) -> None
      Iterates over all asset path fields in the chapter descriptor dict,
      uploads each file from the ZIP to GCS, and replaces *Path fields with
      *Url fields containing the resulting gs:// URIs. Mutates chapter in-place.

  process_practice_set_assets(zf, practice_set, practice_set_id, assets_bucket) -> None
      Same as process_chapter_assets but for practice-set descriptors.
      Handles matching pair audioPath and image_description imagePath fields.
"""

from __future__ import annotations

import logging
import zipfile
from pathlib import PurePosixPath

from google.cloud import storage

logger = logging.getLogger(__name__)


def _guess_content_type(filename: str) -> str:
    ext = PurePosixPath(filename).suffix.lower()
    return {
        ".mp3": "audio/mpeg",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }.get(ext, "application/octet-stream")


def _upload_asset(
    zf: zipfile.ZipFile,
    asset_path: str,
    entity_id: str,
    bucket: storage.Bucket,
    gcs_prefix: str = "chapters",
) -> str:
    """Upload a single asset from the ZIP to the GCS bucket. Returns the gs:// URI."""
    filename = PurePosixPath(asset_path).name
    gcs_path = f"{gcs_prefix}/{entity_id}/{filename}"
    try:
        asset_bytes = zf.read(asset_path)
    except KeyError as exc:
        raise ValueError(f"Asset '{asset_path}' not found in ZIP") from exc
    content_type = _guess_content_type(filename)
    blob = bucket.blob(gcs_path)
    blob.cache_control = "public, max-age=31536000"
    blob.upload_from_string(asset_bytes, content_type=content_type)
    uri = f"gs://{bucket.name}/{gcs_path}"
    logger.info("Uploaded asset: %s", uri)
    return uri


def process_chapter_assets(
    zf: zipfile.ZipFile,
    chapter: dict,
    chapter_id: str,
    assets_bucket: storage.Bucket,
) -> None:
    """
    Upload all media assets referenced in the chapter descriptor and replace
    *Path fields with *Url fields containing the resulting gs:// URIs.

    Mutates `chapter` in-place.
    """
    # Cover image
    if chapter.get("coverImagePath"):
        chapter["coverImageUrl"] = _upload_asset(zf, chapter["coverImagePath"], chapter_id, assets_bucket)
        del chapter["coverImagePath"]

    # Vocabulary audio
    for vocab_item in chapter.get("vocabulary", []):
        if vocab_item.get("audioPath"):
            vocab_item["audioUrl"] = _upload_asset(zf, vocab_item["audioPath"], chapter_id, assets_bucket)
            del vocab_item["audioPath"]

    # Grammar note images and audio
    for grammar_note in chapter.get("grammarNotes", []):
        if grammar_note.get("imagePath"):
            grammar_note["imageUrl"] = _upload_asset(zf, grammar_note["imagePath"], chapter_id, assets_bucket)
            del grammar_note["imagePath"]
        # Legacy: note-level combined audio (chapters generated before per-example audio)
        if grammar_note.get("audioPath"):
            grammar_note["audioUrl"] = _upload_asset(zf, grammar_note["audioPath"], chapter_id, assets_bucket)
            del grammar_note["audioPath"]
        # Per-example audio (new chapters)
        for example in grammar_note.get("examples", []):
            if isinstance(example, dict) and example.get("audioPath"):
                example["audioUrl"] = _upload_asset(zf, example["audioPath"], chapter_id, assets_bucket)
                del example["audioPath"]

    # Sentence audio (list of paths -> list of URLs)
    uploaded_sentence_urls: list[str] = []
    for path in chapter.get("sentenceAudioPaths", []):
        if path:
            uploaded_sentence_urls.append(_upload_asset(zf, path, chapter_id, assets_bucket))
        else:
            uploaded_sentence_urls.append("")
    if "sentenceAudioPaths" in chapter:
        chapter["sentenceAudioUrls"] = uploaded_sentence_urls
        del chapter["sentenceAudioPaths"]

    # Passage audio
    if chapter.get("passageAudioPath"):
        chapter["passageAudioUrl"] = _upload_asset(zf, chapter["passageAudioPath"], chapter_id, assets_bucket)
        del chapter["passageAudioPath"]

    # Exercise images, audio, and conversation line audio
    for exercise in chapter.get("exercises", []):
        if exercise.get("imagePath"):
            exercise["imageUrl"] = _upload_asset(zf, exercise["imagePath"], chapter_id, assets_bucket)
            del exercise["imagePath"]
        if exercise.get("audioPath"):
            audio_path: str = exercise["audioPath"]
            if not audio_path.startswith("gs://") and not audio_path.startswith("http"):
                exercise["audioUrl"] = _upload_asset(zf, audio_path, chapter_id, assets_bucket)
                del exercise["audioPath"]

        # Conversation line audio
        if exercise.get("type") == "conversation":
            data = exercise.get("data")
            if isinstance(data, dict):
                for line in data.get("lines", []):
                    if isinstance(line, dict) and line.get("audioPath"):
                        ap: str = line["audioPath"]
                        if not ap.startswith("gs://") and not ap.startswith("http"):
                            line["audioPath"] = _upload_asset(zf, ap, chapter_id, assets_bucket)


def process_practice_set_assets(
    zf: zipfile.ZipFile,
    practice_set: dict,
    practice_set_id: str,
    assets_bucket: storage.Bucket,
) -> None:
    """
    Upload all media assets referenced in the practice set descriptor and replace
    *Path fields with *Url fields. Mutates `practice_set` in-place.

    Handles: coverImagePath, matching pair audioPath, image_description imagePath,
    conversation line audioPath.
    """
    gcs_prefix = "practice_sets"

    # Cover image
    if practice_set.get("coverImagePath"):
        practice_set["coverImageUrl"] = _upload_asset(
            zf, practice_set["coverImagePath"], practice_set_id, assets_bucket, gcs_prefix
        )
        del practice_set["coverImagePath"]

    # Exercises
    for exercise in practice_set.get("exercises", []):
        ex_type = exercise.get("type", "")

        # image_description cover image
        if exercise.get("imagePath"):
            exercise["imageUrl"] = _upload_asset(zf, exercise["imagePath"], practice_set_id, assets_bucket, gcs_prefix)
            del exercise["imagePath"]

        # matching pair audio
        if ex_type == "matching":
            data = exercise.get("data", {})
            for pair in data.get("pairs", []):
                if isinstance(pair, dict) and pair.get("audioPath"):
                    ap = pair["audioPath"]
                    if not ap.startswith("gs://") and not ap.startswith("http"):
                        pair["audioUrl"] = _upload_asset(zf, ap, practice_set_id, assets_bucket, gcs_prefix)
                        del pair["audioPath"]

        # conversation line audio
        if ex_type == "conversation":
            data = exercise.get("data", {})
            if isinstance(data, dict):
                for line in data.get("lines", []):
                    if isinstance(line, dict) and line.get("audioPath"):
                        ap = line["audioPath"]
                        if not ap.startswith("gs://") and not ap.startswith("http"):
                            line["audioPath"] = _upload_asset(zf, ap, practice_set_id, assets_bucket, gcs_prefix)
