"""
Production environment integration service.

Provides:

  ingest_remote(zip_path)
      Reads a generated chapter ZIP, uploads all media assets to the production
      GCS assets bucket, archives the ZIP itself, and writes the chapter document
      directly to production Firestore. Mirrors ingest_direct() from local_ingest.py
      but targets real GCP resources instead of the local emulators.

      Production config (project_id, assets bucket, db name) is read from
      infra/terraform.tfvars at the repo root — no duplication of config values.

      Authentication uses Application Default Credentials (ADC). Run
        gcloud auth application-default login
      before using this command.

Config (read from infra/terraform.tfvars):
  project_id                — GCP project ID
  public_assets_bucket_name — GCS bucket for chapter assets (created by Terraform)
  db_name                   — Firestore database name (e.g. "daskalo-db")
"""

from __future__ import annotations

import io
import json
import logging
import re
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

# Path to terraform.tfvars relative to repo root
_TFVARS_PATH = _repo_root / "infra" / "terraform.tfvars"

# Required tfvars keys
_REQUIRED_TFVARS = ("project_id", "public_assets_bucket_name", "db_name")


# ---------------------------------------------------------------------------
# Config parsing
# ---------------------------------------------------------------------------


def parse_tfvars(tfvars_path: Path | None = None) -> dict[str, str]:
    """
    Parse a terraform.tfvars file and return a dict of string values.

    Only handles simple  key = "value"  assignments (which covers all fields
    used in this project). Ignores comments, blank lines, and numeric values.

    Raises FileNotFoundError if the file is missing.
    Raises ValueError if any required key is absent.
    """
    path = tfvars_path or _TFVARS_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"terraform.tfvars not found at {path}.\n"
            "Copy infra/terraform.tfvars.example to infra/terraform.tfvars and fill in real values."
        )

    result: dict[str, str] = {}
    # Match:  key  =  "value"  (with optional surrounding whitespace)
    _line_re = re.compile(r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*"([^"]*)"\s*$')

    for line in path.read_text(encoding="utf-8").splitlines():
        m = _line_re.match(line)
        if m:
            result[m.group(1)] = m.group(2)

    missing = [k for k in _REQUIRED_TFVARS if k not in result]
    if missing:
        raise ValueError(f"terraform.tfvars is missing required keys: {', '.join(missing)}\n  File: {path}")

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def upsert_book(fs_client: firestore.Client, book_id: str) -> str:
    """
    Upsert the book document from the per-book curriculum YAML files.

    Uses set(merge=True) so it is safe to call repeatedly.
    Returns the book ID that was written.
    """
    curriculum = load_curriculum(_repo_root)

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
    logger.info("Book '%s' (%s) upserted in production Firestore.", book_id, book["title"])
    return book_id


def ingest_remote(zip_path: str) -> str:
    """
    Ingest a chapter or practice-set ZIP directly into production GCP (Firestore + GCS).

    Steps:
      1. Parse project config from infra/terraform.tfvars.
      2. Upload all media assets to the production assets bucket.
      3. Archive the ZIP itself.
      4. Upsert the parent book document.
      5. Write (merge) the chapter or practice-set document in production Firestore.
         For practice sets, also ArrayUnion the ID onto the parent chapter.

    Returns the chapter or practice-set ID that was written.
    """
    config = parse_tfvars()
    project_id = config["project_id"]
    assets_bucket_name = config["public_assets_bucket_name"]
    db_name = config["db_name"]

    logger.info(
        "Remote ingest: project=%s  bucket=%s  db=%s",
        project_id,
        assets_bucket_name,
        db_name,
    )

    storage_client = storage.Client(project=project_id)
    assets_bucket = storage_client.bucket(assets_bucket_name)

    fs_client = firestore.Client(project=project_id, database=db_name)

    zip_bytes = Path(zip_path).read_bytes()

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        try:
            descriptor = json.loads(zf.read("descriptor.json"))
        except KeyError as exc:
            raise ValueError("ZIP is missing descriptor.json") from exc

        action = descriptor.get("action", "create_or_update_chapter")

        if action == "create_practice_set":
            entity_id = _ingest_practice_set_remote(zf, descriptor, fs_client, assets_bucket, assets_bucket_name)
        else:
            chapter = descriptor["chapter"]
            chapter_id: str = chapter["id"]
            book_id: str = descriptor["bookId"]
            logger.info("Remote-ingesting chapter '%s' (id=%s)", chapter.get("title"), chapter_id)

            upsert_book(fs_client, book_id)
            process_chapter_assets(zf, chapter, chapter_id, assets_bucket)

            chapter["bookId"] = book_id
            doc_ref = fs_client.collection("chapters").document(chapter_id)
            doc_ref.set(chapter, merge=True)
            logger.info("Chapter '%s' written to production Firestore (db=%s).", chapter_id, db_name)
            entity_id = chapter_id

    # Archive the original ZIP
    archive_blob_name = f"archives/{entity_id}.zip"
    archive_blob = assets_bucket.blob(archive_blob_name)
    archive_blob.upload_from_string(zip_bytes, content_type="application/zip")
    logger.info("ZIP archived to: gs://%s/%s", assets_bucket_name, archive_blob_name)

    return entity_id


def _ingest_practice_set_remote(
    zf,
    descriptor: dict,
    fs_client: firestore.Client,
    assets_bucket,
    assets_bucket_name: str,
) -> str:
    """Write a practice set to production Firestore and ArrayUnion onto its chapter."""
    practice_set = descriptor["practiceSet"]
    practice_set_id: str = practice_set["id"]
    chapter_id: str = descriptor["chapterId"]
    book_id: str = descriptor.get("bookId", "")

    logger.info("Remote-ingesting practice set '%s' for chapter '%s'", practice_set_id, chapter_id)

    upsert_book(fs_client, book_id)
    process_practice_set_assets(zf, practice_set, practice_set_id, assets_bucket)

    ps_ref = fs_client.collection("practice_sets").document(practice_set_id)
    ps_ref.set(practice_set, merge=True)
    logger.info("Practice set '%s' written to production Firestore.", practice_set_id)

    chapter_ref = fs_client.collection("chapters").document(chapter_id)
    chapter_ref.set(
        {"practiceSetIds": firestore.ArrayUnion([practice_set_id])},
        merge=True,
    )
    logger.info("ArrayUnion'd '%s' onto chapter '%s'.practiceSetIds.", practice_set_id, chapter_id)

    return practice_set_id


# ---------------------------------------------------------------------------
# Config introspection helper (used by main.py to show the user what will be
# targeted before asking for confirmation)
# ---------------------------------------------------------------------------


def get_remote_config() -> dict[str, str]:
    """Return parsed production config. Raises if tfvars is missing or incomplete."""
    return parse_tfvars()
