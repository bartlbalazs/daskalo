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
  2. Loads the exercise_attempts/{attemptId} document from Firestore.
  3. Confirms the attempt belongs to the authenticated user.
  4. Fetches the exercise prompt from the parent chapter document.
  5. Calls Gemini to evaluate the answer.
  6. Writes the result (status + evaluation) back to Firestore.
  7. Returns the evaluation result to the caller.
"""

from __future__ import annotations

import logging
import os

import firebase_admin
import flask
import functions_framework
from firebase_admin import credentials, firestore

from callable_helpers import (
    callable_error,
    callable_response,
    parse_callable_request,
    verify_firebase_token,
)
from models.firestore import AttemptStatus, ExerciseAttempt, ExerciseType
from services.evaluation import evaluate_attempt, evaluate_pronunciation

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

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


_AI_GRADED_TYPES = {
    ExerciseType.image_description,
    ExerciseType.translation_challenge,
    ExerciseType.dictation,
    ExerciseType.pronunciation_practice,
}


# ---------------------------------------------------------------------------
# Cloud Function entry point
# ---------------------------------------------------------------------------


@functions_framework.http
def evaluate_attempt_fn(request: flask.Request) -> tuple:
    """HTTP Cloud Function entry point for exercise evaluation."""
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

    # 3. Load the attempt document
    db = firestore.client()
    ref = db.collection("exercise_attempts").document(attempt_id)
    snap = ref.get()

    if not snap.exists:
        return callable_error("NOT_FOUND", f"Attempt '{attempt_id}' not found.", 404)

    attempt_data = snap.to_dict()

    # 4. Verify ownership — the attempt must belong to the authenticated user
    if attempt_data.get("userId") != caller_uid:
        return callable_error("PERMISSION_DENIED", "Attempt does not belong to this user.", 403)

    # 5. Validate state and exercise type
    if attempt_data.get("status") != AttemptStatus.pending.value:
        return callable_error(
            "FAILED_PRECONDITION",
            f"Attempt status is '{attempt_data.get('status')}', expected 'pending'.",
            409,
        )

    try:
        exercise_type = ExerciseType(attempt_data.get("type", ""))
    except ValueError:
        return callable_error("INVALID_ARGUMENT", f"Unknown exercise type '{attempt_data.get('type')}'.", 400)

    if exercise_type not in _AI_GRADED_TYPES:
        return callable_error(
            "INVALID_ARGUMENT",
            f"Exercise type '{exercise_type}' is not AI-graded.",
            400,
        )

    # 6. Mark as evaluating
    ref.update({"status": AttemptStatus.evaluating.value})

    # 7. Fetch the exercise prompt (and target_text for pronunciation) from the chapter document
    chapter_ref = db.collection("chapters").document(attempt_data.get("chapterId", ""))
    chapter_snap = chapter_ref.get()
    prompt = ""
    target_text = ""
    if chapter_snap.exists:
        exercises = chapter_snap.to_dict().get("exercises", [])
        try:
            ex_index = int(attempt_data.get("exerciseId", "ex_0").split("_")[-1])
            if 0 <= ex_index < len(exercises):
                exercise_data = exercises[ex_index]
                prompt = exercise_data.get("prompt", "")
                target_text = exercise_data.get("data", {}).get("targetText", "")
        except (ValueError, IndexError):
            logger.warning("Could not resolve exercise data for exerciseId=%s", attempt_data.get("exerciseId"))

    # 8. Evaluate with Gemini
    try:
        attempt = ExerciseAttempt(**attempt_data)
        if exercise_type == ExerciseType.pronunciation_practice:
            if not audio_base64:
                return callable_error("INVALID_ARGUMENT", "audioBase64 is required for pronunciation_practice.", 400)
            result = evaluate_pronunciation(attempt, target_text, audio_base64)
        else:
            result = evaluate_attempt(attempt, prompt)
    except ValueError as exc:
        logger.warning("Validation error for attempt '%s': %s", attempt_id, exc)
        ref.update({"status": AttemptStatus.error.value})
        return callable_error("INVALID_ARGUMENT", str(exc), 400)
    except Exception as exc:
        logger.exception("Evaluation failed for attempt '%s': %s", attempt_id, exc)
        ref.update({"status": AttemptStatus.error.value})
        return callable_error("INTERNAL", "Evaluation failed. Please try again.", 500)

    # 9. Write result back to Firestore
    ref.update(
        {
            "status": AttemptStatus.completed.value,
            "evaluation": result.model_dump(),
        }
    )
    logger.info("Attempt '%s' evaluated — score=%d", attempt_id, result.score)

    # 10. Return result to caller
    return callable_response(result.model_dump())
