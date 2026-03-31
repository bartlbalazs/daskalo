"""
Local environment integration service.

Provides two modes for targeting the local Firebase Emulator Suite:

  upload_to_storage_emulator(zip_path)
      Uploads the generated ZIP to the local Storage emulator ingestion bucket.

  ingest_direct(zip_path)
      Bypasses the ZIP → Storage → backend flow entirely.
      Reads the ZIP locally, uploads assets to the Storage emulator, and writes
      the chapter document directly to the Firestore emulator. Useful for fast
      local iteration without running the backend.

Both modes require the Firebase Emulator Suite to be running (dev.sh).

Environment variables used:
  STORAGE_EMULATOR_HOST   — set automatically; defaults to http://localhost:9199
                            (must include http:// scheme — required by google-cloud-storage v2+)
  FIRESTORE_EMULATOR_HOST — set automatically; defaults to localhost:8081
  GOOGLE_CLOUD_PROJECT    — used as the GCS project ID (can be the demo project)
"""

from __future__ import annotations

import io
import json
import logging
import os
import sys
import zipfile
from pathlib import Path

from google.cloud import firestore, storage

# Ensure shared package is importable.
_repo_root = Path(__file__).parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from shared.data.curriculum_loader import load_curriculum  # noqa: E402

from services.ingest_helpers import process_chapter_assets, process_practice_set_assets  # noqa: E402

logger = logging.getLogger(__name__)

# Emulator defaults (match firebase.json emulator ports)
# Note: google-cloud-storage v2+ requires the full URL with scheme in STORAGE_EMULATOR_HOST.
_STORAGE_EMULATOR_HOST = "http://localhost:9199"
_FIRESTORE_EMULATOR_HOST = "localhost:8081"

# Local bucket names (emulator auto-creates these)
LOCAL_INGESTION_BUCKET = "demo-daskalo-ingestion"
LOCAL_ASSETS_BUCKET = "demo-daskalo-assets"

# Firestore demo project ID (matches firebase.json / frontend environment.ts)
LOCAL_PROJECT_ID = "demo-daskalo"


def upload_to_storage_emulator(zip_path: str) -> str:
    """
    Upload the generated ZIP to the local Storage emulator ingestion bucket.

    The watcher + backend will pick it up and run the full ingestion pipeline.
    Returns the GCS URI of the uploaded ZIP.
    """
    _configure_emulator_env()

    zip_path_obj = Path(zip_path)
    # Always use the demo project ID for emulator clients (see ingest_direct comment).
    client = storage.Client(project=LOCAL_PROJECT_ID)
    bucket = _ensure_bucket(client, LOCAL_INGESTION_BUCKET)

    blob_name = zip_path_obj.name
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(str(zip_path_obj), content_type="application/zip")

    uri = f"gs://{LOCAL_INGESTION_BUCKET}/{blob_name}"
    logger.info("Uploaded ZIP to Storage emulator: %s", uri)
    return uri


def upsert_book(fs_client: firestore.Client, book_id: str) -> str:
    """
    Upsert the book document from the per-book curriculum YAML files.

    Uses set(merge=True) so it is safe to call repeatedly — it will not
    overwrite fields that have been manually edited in the emulator.

    Returns the book ID that was written.
    """
    repo_root = Path(__file__).parent.parent.parent
    curriculum = load_curriculum(repo_root)

    book = next((b for b in curriculum.get("books", []) if b["id"] == book_id), None)
    if not book:
        logger.warning("Book '%s' not found in curriculum books", book_id)
        return book_id

    doc_ref = fs_client.collection("books").document(book_id)
    doc_ref.set(
        {
            "title": book["title"],
            "description": book["description"],
            "order": book["order"],
            "isActive": True,
        },
        merge=True,
    )
    logger.info("Book '%s' (%s) upserted in Firestore emulator.", book_id, book["title"])
    return book_id


def ingest_direct(zip_path: str) -> str:
    """
    Directly ingest the ZIP into the local Firebase emulators.

    Handles both chapter ZIPs (action: create_or_update_chapter) and
    practice-set ZIPs (action: create_practice_set).

    Returns the chapter/practice-set ID that was written.
    """
    _configure_emulator_env()

    # Always use the demo project ID for emulator clients — the real GCP project
    # (GOOGLE_CLOUD_PROJECT) is only needed for Vertex AI / TTS calls and must NOT
    # be used here, otherwise data lands in a different emulator namespace than the
    # one the frontend and the Firebase Emulator UI expect (demo-daskalo).
    storage_client = storage.Client(project=LOCAL_PROJECT_ID)
    assets_bucket = _ensure_bucket(storage_client, LOCAL_ASSETS_BUCKET)

    fs_client = firestore.Client(project=LOCAL_PROJECT_ID)

    zip_bytes = Path(zip_path).read_bytes()

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        try:
            descriptor = json.loads(zf.read("descriptor.json"))
        except KeyError as exc:
            raise ValueError("ZIP is missing descriptor.json") from exc

        action = descriptor.get("action", "create_or_update_chapter")

        if action == "create_practice_set":
            return _ingest_practice_set(zf, descriptor, fs_client, assets_bucket)

        # Default: chapter ingestion
        chapter = descriptor["chapter"]
        chapter_id: str = chapter["id"]
        book_id: str = descriptor["bookId"]
        logger.info("Direct-ingesting chapter '%s' (id=%s)", chapter.get("title"), chapter_id)

        upsert_book(fs_client, book_id)
        process_chapter_assets(zf, chapter, chapter_id, assets_bucket)

    chapter["bookId"] = book_id
    doc_ref = fs_client.collection("chapters").document(chapter_id)
    doc_ref.set(chapter, merge=True)
    logger.info("Chapter '%s' written to Firestore emulator.", chapter_id)

    return chapter_id


def _ingest_practice_set(
    zf,
    descriptor: dict,
    fs_client: firestore.Client,
    assets_bucket,
) -> str:
    """Write a practice set document to Firestore and ArrayUnion its ID onto the chapter."""
    practice_set = descriptor["practiceSet"]
    practice_set_id: str = practice_set["id"]
    chapter_id: str = descriptor["chapterId"]
    book_id: str = descriptor.get("bookId", "")

    logger.info("Direct-ingesting practice set '%s' for chapter '%s'", practice_set_id, chapter_id)

    upsert_book(fs_client, book_id)
    process_practice_set_assets(zf, practice_set, practice_set_id, assets_bucket)

    # Write practice set document
    ps_ref = fs_client.collection("practice_sets").document(practice_set_id)
    ps_ref.set(practice_set, merge=True)
    logger.info("Practice set '%s' written to Firestore emulator.", practice_set_id)

    # ArrayUnion the practice set ID onto the parent chapter
    chapter_ref = fs_client.collection("chapters").document(chapter_id)
    chapter_ref.set(
        {"practiceSetIds": firestore.ArrayUnion([practice_set_id])},
        merge=True,
    )
    logger.info("ArrayUnion'd '%s' onto chapter '%s'.practiceSetIds.", practice_set_id, chapter_id)

    return practice_set_id


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _configure_emulator_env() -> None:
    """Set emulator host env vars if not already set. Idempotent."""
    os.environ.setdefault("STORAGE_EMULATOR_HOST", _STORAGE_EMULATOR_HOST)
    os.environ.setdefault("FIRESTORE_EMULATOR_HOST", _FIRESTORE_EMULATOR_HOST)


def _ensure_bucket(client: storage.Client, bucket_name: str) -> storage.Bucket:
    """Return the bucket handle for the emulator.

    The Firebase Storage emulator creates buckets implicitly on first upload —
    the GCS 'create bucket' API is not implemented. We simply return the bucket
    object and let the SDK discover/create it on the first blob upload.
    """
    return client.bucket(bucket_name)
