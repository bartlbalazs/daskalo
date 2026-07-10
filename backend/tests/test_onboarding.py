"""Tests for services/onboarding.py."""

from unittest.mock import MagicMock, patch

import pytest
from google.cloud.firestore import SERVER_TIMESTAMP

from services.onboarding import HOW_IT_WORKS_KEY, mark_onboarding_seen
from tests.conftest import FakeTransaction

UID = "user-123"


def _make_db(user_data: dict | None) -> MagicMock:
    db = MagicMock()
    user_snap = MagicMock(exists=user_data is not None)
    user_snap.to_dict.return_value = user_data
    user_ref = MagicMock()
    user_ref.get.return_value = user_snap
    users = MagicMock()
    users.document.return_value = user_ref
    db.collection.return_value = users
    db.transaction.side_effect = lambda: FakeTransaction()
    return db


def test_mark_onboarding_seen_writes_timestamp_when_missing():
    db = _make_db(user_data={"onboarding": {}})

    with patch("services.onboarding._get_db", return_value=db):
        result = mark_onboarding_seen(uid=UID, key=HOW_IT_WORKS_KEY)

    assert result == {"key": HOW_IT_WORKS_KEY, "alreadySeen": False}
    user_ref = db.collection("users").document(UID)
    user_ref.update.assert_called_once_with({"onboarding.howItWorksSeenAt": SERVER_TIMESTAMP})


def test_mark_onboarding_seen_idempotent_when_already_seen():
    db = _make_db(user_data={"onboarding": {"howItWorksSeenAt": object()}})

    with patch("services.onboarding._get_db", return_value=db):
        result = mark_onboarding_seen(uid=UID, key=HOW_IT_WORKS_KEY)

    assert result == {"key": HOW_IT_WORKS_KEY, "alreadySeen": True}
    user_ref = db.collection("users").document(UID)
    user_ref.update.assert_not_called()


def test_mark_onboarding_seen_rejects_malformed_onboarding_data():
    db = _make_db(user_data={"onboarding": "bad"})

    with patch("services.onboarding._get_db", return_value=db):
        with pytest.raises(ValueError, match="malformed onboarding"):
            mark_onboarding_seen(uid=UID, key=HOW_IT_WORKS_KEY)
