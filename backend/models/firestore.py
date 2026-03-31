"""
Pydantic models mirroring the Firestore data model defined in docs/DATA_MODEL.md.
Keep these in sync with the schema at all times.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Shared enums
# ---------------------------------------------------------------------------


class UserStatus(StrEnum):
    pending = "pending"
    active = "active"


class AttemptStatus(StrEnum):
    pending = "pending"
    evaluating = "evaluating"
    completed = "completed"
    error = "error"


class ExerciseType(StrEnum):
    slang_matcher = "slang_matcher"
    vocab_flashcard = "vocab_flashcard"
    fill_in_the_blank = "fill_in_the_blank"
    word_scramble = "word_scramble"
    odd_one_out = "odd_one_out"
    image_description = "image_description"
    translation_challenge = "translation_challenge"
    sentence_reorder = "sentence_reorder"
    passage_comprehension = "passage_comprehension"
    listening_comprehension = "listening_comprehension"
    dictation = "dictation"
    pronunciation_practice = "pronunciation_practice"
    roleplay_choice = "roleplay_choice"
    dialogue_completion = "dialogue_completion"
    cultural_context = "cultural_context"
    lyrics_fill = "lyrics_fill"
    conversation = "conversation"
    matching = "matching"


# ---------------------------------------------------------------------------
# Exercise Attempt — written by the frontend, read by the backend
# ---------------------------------------------------------------------------


class ExerciseAttemptPayload(BaseModel):
    """The user's raw answer, structure depends on exercise type."""

    text: str | None = None
    selected_option: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ExerciseAttempt(BaseModel):
    """Mirrors the `exercise_attempts/{attemptId}` Firestore document."""

    userId: str
    chapterId: str
    exerciseId: str
    type: ExerciseType
    submittedAt: datetime
    payload: ExerciseAttemptPayload
    status: AttemptStatus = AttemptStatus.pending
    evaluation: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Evaluation result — written back to Firestore by the backend
# ---------------------------------------------------------------------------


class EvaluationResult(BaseModel):
    score: int = Field(ge=0, le=100)
    feedback: str
    isCorrect: bool
