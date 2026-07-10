"""
Integration tests for main.py — the local-dev FastAPI server.

Unlike the other test_fn_*.py files (which call the Cloud Function handlers
directly with a MagicMock request), these tests go through the *real* FastAPI
app and the real _FlaskRequestShim, using Starlette's TestClient. This is the
only place that exercises the actual request objects passed to fn_*.py in
local dev — a MagicMock-based request (used everywhere else in this test
suite) auto-fabricates any attribute access instead of raising, so it can't
catch a shim that's missing an attribute the handlers actually read (see
BE-01 verification note below).
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture
def client():
    with patch("main._init_firebase"):
        yield TestClient(main.app)


# ---------------------------------------------------------------------------
# BE-01: all four endpoints must be registered and reachable
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/evaluate", {"attemptId": "x"}),
        ("/complete-chapter", {"chapterId": "x"}),
        ("/add-own-word", {"text": "x", "chapterId": "x", "bookId": "x"}),
        ("/complete-practice", {"practiceSetId": "x"}),
    ],
)
def test_endpoint_reachable_and_returns_well_formed_callable_error(client, path, payload):
    """
    Every endpoint must be reachable (not 404 — BE-01) and, called with no auth,
    must return a well-formed Callable error response rather than crashing.

    This is also a regression test for a bug found during verification: the
    local _FlaskRequestShim didn't set `.method`, so `request.method == "OPTIONS"`
    (the first line of every fn_*.py handler) raised AttributeError for every
    request, for all four endpoints — masked in the rest of this test suite
    because MagicMock-based fake requests auto-fabricate `.method` instead of
    raising.
    """
    response = client.post(path, json={"data": payload})

    assert response.status_code == 401
    body = response.json()
    assert body["error"]["status"] == "UNAUTHENTICATED"


def test_all_endpoints_registered_in_openapi_schema(client):
    schema = client.get("/openapi.json").json()
    assert set(schema["paths"].keys()) == {
        "/evaluate",
        "/complete-chapter",
        "/add-own-word",
        "/complete-practice",
        "/set-curriculum-selection",
    }


# ---------------------------------------------------------------------------
# BE-16: CORS allow_credentials must be False (invalid to combine with "*")
# ---------------------------------------------------------------------------


def test_cors_preflight_does_not_allow_credentials(client):
    response = client.options(
        "/complete-practice",
        headers={"Origin": "http://localhost:4200", "Access-Control-Request-Method": "POST"},
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "*"
    assert "access-control-allow-credentials" not in response.headers
