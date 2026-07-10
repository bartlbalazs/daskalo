"""
Daskalo Backend — local development FastAPI server.

This file is NOT deployed to production.  In production, each handler is a
separate Cloud Function (fn_evaluate.py, fn_complete_chapter.py).

Locally this server bundles both Cloud Function handlers as standard FastAPI
POST endpoints so they can be exercised via the Angular dev app, curl, or
the Swagger UI at http://localhost:8000/docs.

The Firebase Callable wire protocol is preserved:
  - Request body:  { "data": { ...args... } }
  - Success body:  { "result": { ... } }
  - Error body:    { "error": { "status": "...", "message": "..." } }
"""

import logging
import os

import firebase_admin
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from firebase_admin import credentials

from fn_complete_chapter import complete_chapter_fn
from fn_complete_practice import complete_practice_fn
from fn_evaluate import evaluate_attempt_fn
from fn_mark_onboarding_seen import mark_onboarding_seen_fn
from fn_own_word import add_own_word_fn
from fn_set_curriculum_selection import set_curriculum_selection_fn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Firebase Admin SDK — initialised once at startup.
# In local dev we rely on GOOGLE_APPLICATION_CREDENTIALS or emulator env vars.
# ---------------------------------------------------------------------------


def _init_firebase() -> None:
    if firebase_admin._DEFAULT_APP_NAME in firebase_admin._apps:
        return
    # Point the Admin SDK at the local Auth emulator so it can verify tokens
    # issued by the frontend emulator. This file is never deployed to production
    # (Cloud Functions use fn_evaluate.py / fn_complete_chapter.py directly),
    # so hardcoding the emulator host here is safe.
    os.environ.setdefault("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
    os.environ.setdefault("PUBLIC_ASSETS_BUCKET", "demo-daskalo-assets")
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    cred = credentials.Certificate(cred_path) if cred_path else credentials.ApplicationDefault()
    # Force the local Firebase emulator project ID to match the frontend emulator
    # (hardcoded to "demo-daskalo" in environment.ts). If GOOGLE_CLOUD_PROJECT
    # were used here instead, auth.verify_id_token() would reject tokens because
    # the token audience ("demo-daskalo") wouldn't match the SDK's project ID.
    project_id = "demo-daskalo"
    firebase_admin.initialize_app(cred, {"projectId": project_id})
    logger.info("Firebase Admin SDK initialised (project=%s)", project_id)


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Daskalo Backend (local dev)",
    description=(
        "Local development server bundling both Cloud Function handlers. "
        'Uses the Firebase Callable wire protocol: send {"data": {...}} '
        'and receive {"result": {...}} or {"error": {...}}.'
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # BE-16: allow_origins=["*"] combined with allow_credentials=True is an
    # invalid combination per the Fetch spec. This backend never uses cookies —
    # the Firebase ID token travels in the request body (data.idToken) or the
    # Authorization header, per docs/ARCHITECTURE.md — so credentials aren't needed.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event() -> None:
    _init_firebase()


# ---------------------------------------------------------------------------
# Thin FastAPI wrappers — delegate directly to the Cloud Function handlers.
# functions_framework passes a Flask Request; we adapt the FastAPI Request
# via a lightweight shim so callable_helpers can read headers and body.
# ---------------------------------------------------------------------------


class _FlaskRequestShim:
    """Minimal Flask-Request-compatible shim wrapping a FastAPI Request body/headers."""

    def __init__(self, body: bytes, headers: dict, method: str = "POST") -> None:
        self._body = body
        self.headers = headers
        # Every fn_*.py handler's first line is `if request.method == "OPTIONS": ...` —
        # without this, that line raised AttributeError for every single request
        # (masked in unit tests, which pass a MagicMock that auto-fabricates any
        # attribute access instead of raising).
        self.method = method

    def get_json(self, silent: bool = False):  # noqa: ANN201
        import json

        try:
            return json.loads(self._body)
        except Exception:
            if silent:
                return None
            raise


async def _shim(request: Request) -> _FlaskRequestShim:
    body = await request.body()
    # Pass the Starlette Headers object directly (case-insensitive .get()),
    # NOT dict(request.headers) which lowercases all keys and breaks
    # callable_helpers.py's lookup of "Authorization".
    return _FlaskRequestShim(body, request.headers, method=request.method)


@app.post("/evaluate", summary="Evaluate an AI-graded exercise attempt")
async def evaluate_endpoint(request: Request) -> JSONResponse:
    shim = await _shim(request)
    result = evaluate_attempt_fn(shim)
    # Handlers return (body, status) or (body, status, headers).
    # CORS headers are already handled by FastAPI CORSMiddleware locally.
    body, status = result[0], result[1]
    return JSONResponse(content=body, status_code=status)


@app.post("/complete-chapter", summary="Complete a chapter and update the grammar book")
async def complete_chapter_endpoint(request: Request) -> JSONResponse:
    shim = await _shim(request)
    result = complete_chapter_fn(shim)
    body, status = result[0], result[1]
    return JSONResponse(content=body, status_code=status)


@app.post("/add-own-word", summary="Add a student's own Greek vocabulary word")
async def add_own_word_endpoint(request: Request) -> JSONResponse:
    shim = await _shim(request)
    result = add_own_word_fn(shim)
    body, status = result[0], result[1]
    return JSONResponse(content=body, status_code=status)


@app.post("/complete-practice", summary="Complete a practice set and award XP")
async def complete_practice_endpoint(request: Request) -> JSONResponse:
    shim = await _shim(request)
    result = complete_practice_fn(shim)
    body, status = result[0], result[1]
    return JSONResponse(content=body, status_code=status)


@app.post("/set-curriculum-selection", summary="Select a chapter variant for a curriculum slot")
async def set_curriculum_selection_endpoint(request: Request) -> JSONResponse:
    shim = await _shim(request)
    result = set_curriculum_selection_fn(shim)
    body, status = result[0], result[1]
    return JSONResponse(content=body, status_code=status)


@app.post("/mark-onboarding-seen", summary="Mark an onboarding item as seen")
async def mark_onboarding_seen_endpoint(request: Request) -> JSONResponse:
    shim = await _shim(request)
    result = mark_onboarding_seen_fn(shim)
    body, status = result[0], result[1]
    return JSONResponse(content=body, status_code=status)
