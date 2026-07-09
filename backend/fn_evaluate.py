"""
Cloud Function entry point: evaluate_attempt

Deployed as a 2nd-gen Cloud Function (HTTP trigger, --allow-unauthenticated).
Auth is enforced in code via Firebase ID token verification.

Firebase Callable wire protocol:
  Request:  POST /
            Authorization: Bearer <firebase-id-token>
            Content-Type: application/json
            Body: { "data": { "attemptId": "<Firestore document ID>" } }

  Success:  { "result": { "score": int, "feedback": str, "isCorrect": bool } }
  Error:    { "error": { "status": "...", "message": "..." } }

The function:
  1. Verifies the caller's Firebase ID token.
  2. Verifies the caller's account is "active" and within their rate limit.
  3. Atomically (Firestore transaction) validates + claims the attempt for
     evaluation — ownership, status, exercise type, and audio presence are
     all checked before transitioning "pending" -> "evaluating", so a stuck
     or lost request never happens because of a race between two calls for
     the same attemptId (BE-02), and an attempt whose "evaluating" claim is
     older than a safety threshold can be reclaimed (IMP-BE-05).
  4. Fetches the exercise prompt from the parent chapter document.
  5. Calls Gemini to evaluate the answer.
  6. Writes the result (status + evaluation) back to Firestore — this and
     every failure path below it share one try/except so a Firestore-write
     failure after a successful (paid) Gemini call still produces a
     well-formed Callable error response instead of a raw 500 (BE-04).
  7. Returns the evaluation result to the caller.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from functools import lru_cache

import firebase_admin
import flask
import functions_framework
from firebase_admin import credentials
from google.cloud.firestore import Client as FirestoreClient
from google.cloud.firestore import Transaction, transactional

import log_setup  # noqa: F401 — configures root logger for Cloud Logging
from callable_helpers import (
    RateLimitExceeded,
    callable_error,
    callable_response,
    check_rate_limit,
    cors_preflight,
    ensure_active_user,
    parse_callable_request,
    verify_firebase_token,
)
from constants import EVALUATING_STALE_SECONDS, RATE_LIMIT_EVALUATE, RATE_LIMIT_WINDOW_SECONDS
from models.firestore import AI_GRADED_EXERCISE_TYPES, AttemptStatus, ExerciseAttempt, ExerciseType
from services.evaluation import evaluate_attempt, evaluate_pronunciation

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Firebase Admin SDK — initialised once per cold start.
# Uses the attached service account in Cloud Functions; falls back to
# GOOGLE_APPLICATION_CREDENTIALS for local dev.
# ---------------------------------------------------------------------------


def _init_firebase() -> None:
    if firebase_admin._DEFAULT_APP_NAME in firebase_admin._apps:
        return
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    cred = credentials.Certificate(cred_path) if cred_path else credentials.ApplicationDefault()
    firebase_admin.initialize_app(
        cred,
        {"projectId": os.getenv("GOOGLE_CLOUD_PROJECT")},
    )


# IMP-BE-03: construct the Firestore client once and reuse it across
# invocations within the same process, instead of on every single request.
# Lazily cached (rather than built at raw import time) so importing this
# module never requires credentials to already be resolvable — this matters
# for test collection and for any tooling that imports Cloud Function modules
# without a live GCP environment.
@lru_cache(maxsize=1)
def _get_db() -> FirestoreClient:
    return FirestoreClient(database=os.getenv("FIRESTORE_DB", "(default)"))


# ---------------------------------------------------------------------------
# Claim-time exceptions — each maps to exactly one Callable error response.
# ---------------------------------------------------------------------------


class _AttemptNotFound(Exception):
    """The attempt document does not exist -> 404."""


class _AttemptNotOwned(Exception):
    """The attempt belongs to a different user -> 403."""


class _AttemptNotClaimable(Exception):
    """Status isn't pending, or a stale-enough evaluating -> 409."""


class _AttemptInvalidRequest(Exception):
    """Unknown/non-AI-graded exercise type, or missing required audio -> 400."""


class _ChapterNotFoundError(Exception):
    """The attempt's chapterId no longer resolves to a chapter document -> 404."""


# ---------------------------------------------------------------------------
# Transactional claim (BE-02, BE-03, BE-04, IMP-BE-01, IMP-BE-05)
# ---------------------------------------------------------------------------


@transactional
def _claim_attempt(
    transaction: Transaction,
    ref,  # noqa: ANN001 - google.cloud.firestore.DocumentReference
    caller_uid: str,
    audio_base64: str | None,
) -> tuple[dict, ExerciseType]:
    """
    Atomically validate + claim an attempt for evaluation.

    Reads the attempt doc and validates ownership, claimability, exercise
    type, and (for pronunciation_practice) audio presence — all *before*
    transitioning status -> "evaluating" — so two concurrent calls for the
    same attemptId can't both proceed to call Gemini/STT (BE-02), and a
    doomed request (bad type, missing audio) never gets stuck in
    "evaluating" in the first place.

    An attempt already "evaluating" can be reclaimed if `evaluatingSince` is
    older than EVALUATING_STALE_SECONDS, recovering attempts abandoned by a
    crashed/timed-out invocation (IMP-BE-05) instead of leaving them stuck
    forever (BE-03).
    """
    snap = ref.get(transaction=transaction)
    if not snap.exists:
        raise _AttemptNotFound("Attempt not found.")

    data = snap.to_dict() or {}

    if data.get("userId") != caller_uid:
        raise _AttemptNotOwned("Attempt does not belong to this user.")

    status = data.get("status")
    if status == AttemptStatus.pending.value:
        claimable = True
    elif status == AttemptStatus.evaluating.value:
        evaluating_since = data.get("evaluatingSince")
        claimable = evaluating_since is not None and (
            datetime.now(UTC) - evaluating_since
        ).total_seconds() > EVALUATING_STALE_SECONDS
    else:
        claimable = False

    if not claimable:
        raise _AttemptNotClaimable(
            f"Attempt status is '{status}'; it is already being evaluated or has already been completed."
        )

    try:
        exercise_type = ExerciseType(data.get("type", ""))
    except ValueError as exc:
        raise _AttemptInvalidRequest(f"Unknown exercise type '{data.get('type')}'.") from exc

    if exercise_type not in AI_GRADED_EXERCISE_TYPES:
        raise _AttemptInvalidRequest(f"Exercise type '{exercise_type}' is not AI-graded.")

    if exercise_type == ExerciseType.pronunciation_practice and not audio_base64:
        raise _AttemptInvalidRequest("audioBase64 is required for pronunciation_practice.")

    transaction.update(
        ref,
        {
            "status": AttemptStatus.evaluating.value,
            "evaluatingSince": datetime.now(UTC),
        },
    )
    return data, exercise_type


# ---------------------------------------------------------------------------
# Exercise context lookup (BE-10)
# ---------------------------------------------------------------------------


def _load_exercise_context(db: FirestoreClient, attempt_data: dict) -> tuple[str, str, str]:
    """
    Resolve (prompt, target_text, image_url) for the exercise referenced by an
    attempt document.

    Raises:
        _ChapterNotFoundError — the chapter document does not exist.
        ValueError            — exerciseId cannot be parsed as an index, or the
                                 index is out of range for the chapter's exercises.
    """
    chapter_id = attempt_data.get("chapterId", "")
    chapter_snap = db.collection("chapters").document(chapter_id).get()
    if not chapter_snap.exists:
        raise _ChapterNotFoundError(f"Chapter '{chapter_id}' not found.")

    exercises = (chapter_snap.to_dict() or {}).get("exercises", [])
    exercise_id = attempt_data.get("exerciseId", "")
    try:
        ex_index = int(str(exercise_id).split("_")[-1])
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Could not parse an exercise index from exerciseId '{exercise_id}'.") from exc

    if not (0 <= ex_index < len(exercises)):
        raise ValueError(f"Exercise index {ex_index} is out of range for chapter '{chapter_id}'.")

    exercise_data = exercises[ex_index]
    prompt = exercise_data.get("prompt", "")
    target_text = exercise_data.get("data", {}).get("target_text", "")
    image_url = exercise_data.get("imageUrl", "")
    return prompt, target_text, image_url


# ---------------------------------------------------------------------------
# Cloud Function entry point
# ---------------------------------------------------------------------------


@functions_framework.http
def evaluate_attempt_fn(request: flask.Request) -> tuple:
    """HTTP Cloud Function entry point for exercise evaluation."""
    # Handle CORS preflight before any auth/logic.
    if request.method == "OPTIONS":
        return cors_preflight()

    _init_firebase()

    # 1. Verify caller identity
    try:
        decoded_token = verify_firebase_token(request)
    except PermissionError as exc:
        return callable_error("UNAUTHENTICATED", str(exc), 401)

    caller_uid: str = decoded_token["uid"]

    # 2. Parse request data
    try:
        data = parse_callable_request(request)
        attempt_id: str = data["attemptId"]
        if not attempt_id:
            raise ValueError("attemptId must not be empty.")
        audio_base64: str | None = data.get("audioBase64")
    except (ValueError, KeyError) as exc:
        return callable_error("INVALID_ARGUMENT", str(exc), 400)

    db = _get_db()

    # 3. Active-user gate (BE-05) — must run before any billable work.
    try:
        ensure_active_user(db, caller_uid)
    except PermissionError as exc:
        return callable_error("PERMISSION_DENIED", str(exc), 403)

    # 4. Per-user rate limit (IMP-BE-07)
    try:
        check_rate_limit(
            db,
            caller_uid,
            "evaluate",
            limit=RATE_LIMIT_EVALUATE,
            window_seconds=RATE_LIMIT_WINDOW_SECONDS,
        )
    except RateLimitExceeded as exc:
        return callable_error("RESOURCE_EXHAUSTED", str(exc), 429)

    # 5. Ownership/status: atomically validate + claim the attempt (BE-02, BE-03, IMP-BE-05)
    ref = db.collection("exercise_attempts").document(attempt_id)
    transaction = db.transaction()
    try:
        attempt_data, exercise_type = _claim_attempt(transaction, ref, caller_uid, audio_base64)
    except _AttemptNotFound:
        return callable_error("NOT_FOUND", f"Attempt '{attempt_id}' not found.", 404)
    except _AttemptNotOwned as exc:
        return callable_error("PERMISSION_DENIED", str(exc), 403)
    except _AttemptNotClaimable as exc:
        return callable_error("FAILED_PRECONDITION", str(exc), 409)
    except _AttemptInvalidRequest as exc:
        return callable_error("INVALID_ARGUMENT", str(exc), 400)

    # 6. Business logic: exercise context lookup (BE-10) + Gemini/STT evaluation +
    #    the final write — all in one try/except so ANY failure here (including a
    #    failure of the final write itself) still produces a well-formed Callable
    #    error response and marks the attempt "error" instead of leaving it stuck (BE-04).
    try:
        prompt, target_text, image_url = _load_exercise_context(db, attempt_data)
        attempt = ExerciseAttempt(**attempt_data)
        if exercise_type == ExerciseType.pronunciation_practice:
            result = evaluate_pronunciation(attempt, target_text, audio_base64)
        else:
            result = evaluate_attempt(attempt, prompt, image_url=image_url)

        ref.update(
            {
                "status": AttemptStatus.completed.value,
                "evaluation": result.model_dump(),
            }
        )
    except _ChapterNotFoundError as exc:
        logger.warning("Chapter lookup failed for attempt '%s': %s", attempt_id, exc)
        ref.update({"status": AttemptStatus.error.value})
        return callable_error("NOT_FOUND", str(exc), 404)
    except ValueError as exc:
        logger.warning("Validation error for attempt '%s': %s", attempt_id, exc)
        ref.update({"status": AttemptStatus.error.value})
        return callable_error("INVALID_ARGUMENT", str(exc), 400)
    except Exception as exc:
        logger.exception("Evaluation failed for attempt '%s': %s", attempt_id, exc)
        ref.update({"status": AttemptStatus.error.value})
        return callable_error("INTERNAL", "Evaluation failed. Please try again.", 500)

    logger.info("Attempt '%s' evaluated — score=%d", attempt_id, result.score)

    # 7. Return result to caller
    return callable_response(result.model_dump())
