"""
Practice Set State — the TypedDict that flows through the practice-set LangGraph pipeline.
Simpler than ContentState: we only need to generate exercises (no passage, grammar notes, or review loop).
"""

from typing import TypedDict

from models.content_models import Exercise, ImagePrompt, VocabularyItem


class PracticeState(TypedDict):
    # --- Operator inputs ---
    book_id: str
    curriculum_chapter_id: str  # The curriculum chapter ID (e.g. b1_c3)
    chapter_id: str  # The Firestore document ID of the source chapter
    practice_set_id: str  # The Firestore document ID for the new practice set
    chapter_order: int

    # --- Chapter context (loaded from the source ZIP) ---
    chapter_topic: str
    chapter_title: str
    chapter_summary: str
    vocabulary: list[VocabularyItem]

    # Pre-existing audio from the source ZIP: greek_text -> local absolute path
    existing_audio: dict[str, str]

    # --- Generated content ---
    introduction: str
    skills: list[str]
    exercises: list[Exercise]
    image_prompts: list[ImagePrompt]
    chapter_image_prompt: str  # Cover image prompt (homework aesthetic)

    # --- Generated asset paths ---
    work_dir: str
    audio_files: list[str]
    image_files: list[str]
    chapter_image_path: str

    # --- Final output ---
    output_zip_path: str
