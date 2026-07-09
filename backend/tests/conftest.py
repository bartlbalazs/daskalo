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
# Fake Firestore transaction
# ---------------------------------------------------------------------------
#
# google.cloud.firestore.transactional() wraps a function in real machinery
# (transaction._begin()/_commit()/_rollback(), retry-on-Aborted looping, etc.)
# that expects a real Transaction-like object. Rather than mock all of that
# with a MagicMock (which breaks on `range(transaction._max_attempts)` since
# a bare MagicMock attribute isn't an int), FakeTransaction is a tiny stand-in
# that satisfies exactly the surface `transactional()` needs, so our
# @firestore.transactional-decorated functions can be exercised against plain
# MagicMock document references (`ref.get(transaction=...)`, `ref.update(...)`)
# exactly like the rest of this test suite already does for non-transactional
# code.


class FakeTransaction:
    """Minimal stand-in for google.cloud.firestore.Transaction for unit tests."""

    _max_attempts = 1
    _read_only = False

    def __init__(self) -> None:
        self._id = None

    # --- internals required by firestore.transactional()'s _Transactional wrapper ---
    def _clean_up(self) -> None:
        pass

    def _begin(self, retry_id=None) -> None:  # noqa: ANN001
        pass

    def _commit(self) -> list:
        return []

    def _rollback(self) -> None:
        pass

    # --- read/write API used by our transactional business logic ---
    def update(self, ref, data: dict) -> None:  # noqa: ANN001
        ref.update(data)

    def set(self, ref, data: dict, merge: bool = False) -> None:  # noqa: ANN001
        if merge:
            ref.set(data, merge=True)
        else:
            ref.set(data)

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
