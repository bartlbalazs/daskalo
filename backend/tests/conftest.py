"""
Shared pytest fixtures for Daskalo backend tests.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from models.firestore import (
    AttemptStatus,
    ExerciseAttempt,
    ExerciseAttemptPayload,
    ExerciseType,
)

# ---------------------------------------------------------------------------
# Prevent Firebase Admin SDK from initialising during tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_firebase_admin():
    """Stub out firebase_admin so tests never need real credentials."""
    with patch("firebase_admin.initialize_app"), patch("firebase_admin._apps", {__name__: MagicMock()}):
        yield


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def make_attempt(
    exercise_type: ExerciseType = ExerciseType.translation_challenge,
    text: str = "Γεια σου",
    status: AttemptStatus = AttemptStatus.pending,
    user_id: str = "user-123",
    chapter_id: str = "chapter-abc",
    exercise_id: str = "ex_0",
) -> ExerciseAttempt:
    return ExerciseAttempt(
        userId=user_id,
        chapterId=chapter_id,
        exerciseId=exercise_id,
        type=exercise_type,
        submittedAt=datetime(2026, 1, 1, 12, 0, 0),
        payload=ExerciseAttemptPayload(text=text),
        status=status,
    )


def make_flask_request(
    body: dict | None = None,
    auth_header: str | None = "Bearer valid-token",
) -> MagicMock:
    """Return a minimal Flask-Request-compatible mock."""
    req = MagicMock()
    req.get_json.return_value = body
    req.headers = MagicMock()
    req.headers.get = lambda key, default="": auth_header if key == "Authorization" else default
    return req
