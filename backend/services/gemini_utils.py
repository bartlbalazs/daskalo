"""
Shared Gemini call helpers — retry + defensive parsing.

Centralizes three concerns that were previously duplicated (and, in one case,
unguarded) across services/evaluation.py and services/progress.py:

  1. ``response.text`` can be ``None``/empty (safety-blocked or empty
     candidates). Calling ``len()``/``.strip()`` on that raises a confusing
     AttributeError/TypeError instead of a clear error.
  2. ``json.loads(response.text)`` was called with no try/except, so a
     malformed response crashed with an unhandled ``json.JSONDecodeError``.
  3. A single transient failure (rate limit, timeout, transient 5xx) had no
     retry — the whole (paid, user-facing) request failed immediately.

See docs/planning/BUGS.md#BE-09 and docs/planning/IMPROVEMENTS.md#IMP-BE-04.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from google.api_core import exceptions as google_exceptions
from google.genai import types

logger = logging.getLogger(__name__)

# Errors worth retrying: rate limiting, transient network/server issues.
# Anything else (e.g. INVALID_ARGUMENT) is a caller bug and retrying won't help.
_RETRYABLE_EXCEPTIONS = (
    google_exceptions.Aborted,
    google_exceptions.DeadlineExceeded,
    google_exceptions.InternalServerError,
    google_exceptions.ResourceExhausted,
    google_exceptions.ServiceUnavailable,
)

_DEFAULT_MAX_RETRIES = 2
_RETRY_BACKOFF_SECONDS = 0.5


class GeminiCallFailed(Exception):
    """
    Raised when a Gemini call fails after exhausting all retries (transient
    errors, or persistently empty/None response.text).

    Deliberately a distinct type rather than a bare RuntimeError/Exception —
    call sites that catch their *own* RuntimeErrors for unrelated reasons
    (e.g. a misconfigured environment variable) must not accidentally catch
    (and mislabel) a Gemini failure too.
    """


def generate_content_with_retry(
    client: Any,
    *,
    model: str,
    contents: Any,
    config: types.GenerateContentConfig | None = None,
    max_retries: int = _DEFAULT_MAX_RETRIES,
) -> types.GenerateContentResponse:
    """
    Call ``client.models.generate_content(...)`` with bounded retries.

    Retries (up to ``max_retries`` additional attempts, i.e. ``max_retries + 1``
    attempts total) when:
      - the SDK raises a transient error (see ``_RETRYABLE_EXCEPTIONS``), or
      - the response comes back with an empty/``None`` ``.text`` (which can
        indicate a transient safety-block or an empty candidate list).

    Raises GeminiCallFailed if every attempt fails, chaining the last underlying
    error so the root cause is preserved in logs/tracebacks.
    """
    total_attempts = max_retries + 1
    last_exc: Exception | None = None

    for attempt in range(1, total_attempts + 1):
        try:
            kwargs: dict[str, Any] = {"model": model, "contents": contents}
            if config is not None:
                kwargs["config"] = config
            response = client.models.generate_content(**kwargs)
        except _RETRYABLE_EXCEPTIONS as exc:
            last_exc = exc
            logger.warning(
                "generate_content_with_retry: transient error on attempt %d/%d — %s",
                attempt,
                total_attempts,
                exc,
            )
        else:
            if response.text:
                return response
            last_exc = GeminiCallFailed("Gemini returned an empty response (possibly safety-blocked).")
            logger.warning(
                "generate_content_with_retry: empty response.text on attempt %d/%d",
                attempt,
                total_attempts,
            )

        if attempt < total_attempts:
            time.sleep(_RETRY_BACKOFF_SECONDS)

    logger.error(
        "generate_content_with_retry: exhausted %d attempt(s) — giving up. Last error: %s",
        total_attempts,
        last_exc,
    )
    raise GeminiCallFailed("Gemini call failed after retries.") from last_exc


def parse_json_response(text: str) -> dict[str, Any]:
    """
    Parse a Gemini JSON response, raising a clear ValueError on malformed JSON
    instead of letting json.JSONDecodeError propagate unhandled.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("parse_json_response: invalid JSON from Gemini — %s. Raw text: %r", exc, text)
        raise ValueError(f"Gemini returned invalid JSON: {exc}") from exc
