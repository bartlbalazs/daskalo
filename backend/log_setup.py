"""
Logging setup for Cloud Functions (2nd gen) and local development.

Import this module once at the top of each Cloud Function entry point
(fn_evaluate.py, fn_complete_chapter.py, fn_own_word.py).  The module-level
code runs exactly once per cold start and configures the root logger
appropriately for the environment:

  Production (Cloud Functions / Cloud Run):
    Uses google.cloud.logging.Client.setup_logging(), which attaches a
    StructuredLogHandler to the Python root logger.  The handler emits
    JSON-formatted log entries to stdout, which the Cloud Run logging agent
    parses and forwards to Cloud Logging with the correct severity level
    (INFO, WARNING, ERROR, CRITICAL, etc.).  This makes the logs visible and
    filterable in GCP Log Explorer.

  Local development (K_SERVICE env var is absent):
    Falls back to logging.basicConfig() for plain-text output to stderr,
    which is readable in the terminal without requiring GCP credentials.

All existing logger.info() / logger.warning() / logger.exception() calls
throughout the codebase work without any modifications.
"""

from __future__ import annotations

import logging
import os


def _configure() -> None:
    if os.getenv("K_SERVICE"):
        # Running on Cloud Functions 2nd gen / Cloud Run.
        # google-cloud-logging's setup_logging() replaces the root logger's
        # handlers with a StructuredLogHandler that writes JSON to stdout.
        import google.cloud.logging  # noqa: PLC0415

        client = google.cloud.logging.Client()
        client.setup_logging(log_level=logging.DEBUG)
    else:
        # Local development — plain text is fine.
        logging.basicConfig(level=logging.INFO)


_configure()
