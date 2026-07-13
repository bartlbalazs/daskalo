import pytest
from pydantic import ValidationError

from models.content_models import DraftLesson, ExercisesResult, ImageDescriptionExercise, PassageSentence


def test_draft_lesson_requires_non_empty_passage():
    with pytest.raises(ValidationError):
        DraftLesson(
            chapter_title="A Quiet Morning",
            chapter_summary="A short chapter summary.",
            chapter_introduction="A short introduction.",
            chapter_image_prompt="A quiet street in Athens, no text.",
            narrator_gender="female",
            passage=[],
        )


def test_draft_lesson_accepts_structured_passage():
    lesson = DraftLesson(
        chapter_title="A Quiet Morning",
        chapter_summary="A short chapter summary.",
        chapter_introduction="A short introduction.",
        chapter_image_prompt="A quiet street in Athens, no text.",
        narrator_gender="female",
        passage=[PassageSentence(greek="Καλημέρα.", english="Good morning.")],
    )

    assert lesson.passage[0].greek == "Καλημέρα."


def test_exercises_result_requires_passage_comprehension():
    with pytest.raises(ValidationError, match="passage_comprehension"):
        ExercisesResult(
            exercises=[ImageDescriptionExercise(type="image_description", prompt="Describe the image in Greek.")],
            image_prompts=[],
        )


def test_exercises_result_accepts_passage_comprehension():
    result = ExercisesResult(
        exercises=[
            {
                "type": "passage_comprehension",
                "prompt": "Answer the question about the passage.",
                "data": {
                    "questions": [
                        {
                            "question": "What greeting appears in the passage?",
                            "options": [
                                {"text": "Καλημέρα", "isCorrect": True},
                                {"text": "Αντίο", "isCorrect": False},
                            ],
                        }
                    ]
                },
            }
        ],
        image_prompts=[],
    )

    assert result.exercises[0].type == "passage_comprehension"
