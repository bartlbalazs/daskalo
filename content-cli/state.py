"""
Content Generation State — the TypedDict that flows through every LangGraph node.
All generated content is carried as typed Pydantic model instances so that nodes
downstream of generate_content work with validated, attribute-accessible objects.
"""

from typing_extensions import TypedDict

from models.content_models import (
    Exercise,
    GrammarConceptOutline,
    GrammarNote,
    ImagePrompt,
    PassageSentence,
    VocabularyItem,
)


class ContentState(TypedDict):
    # --- Operator inputs ---
    book_id: str
    curriculum_chapter_id: str  # Curriculum structure ID (e.g. b1_c2)
    variant_id: str  # Final Firestore doc ID (e.g. p1_c2_boxing)
    chapter_order: int
    chapter_topic: str  # Seed provided by operator; LLM expands into title + summary
    student_interests: str  # Free-text, e.g. "football, cooking, travel"
    lesson_length: str  # "short" | "medium" | "long"

    # --- Curriculum constraints (populated by build_context) ---
    target_grammar: str
    language_skill: str  # The specific language skill this chapter teaches (from curriculum.yaml)
    mandatory_vocabulary: list[str]
    accumulated_grammar: str
    accumulated_vocabulary: list[str]
    cefr_level: str  # CEFR level of the current book (e.g. "A1.1", "B2", "C1.2")

    # --- LLM-generated metadata ---
    chapter_title: str  # Creative title invented by the LLM (e.g. "Lost in Monastiraki")
    chapter_summary: str  # One-sentence learner pitch invented by the LLM
    chapter_image_prompt: str  # English prompt for generating the chapter cover image

    # --- Generated text content (Pydantic model instances) ---
    passage: list[PassageSentence]  # Reading passage as list of {greek, english} sentence objects
    vocabulary: list[VocabularyItem]
    grammar_concept_outlines: list[GrammarConceptOutline]
    grammar_notes: list[GrammarNote]
    exercises: list[Exercise]

    # --- Pre-generated grammar reference (stored on the chapter, shared by all students) ---
    grammar_summary: str  # Markdown reference: grammar tables + key vocab + usage tips

    # --- Internal: not included in descriptor.json ---
    image_prompts: list[ImagePrompt]  # One per image_description exercise
    review_feedback: str  # Empty string means APPROVED
    generation_attempts: int  # Incremented on each generate_content call

    # --- Generated asset paths (local filesystem within work_dir) ---
    work_dir: str  # Temp directory for this generation run
    audio_files: list[str]  # Absolute paths to vocab + passage .mp3 files
    sentence_audio_files: list[str]  # Absolute paths to per-sentence passage clips
    image_files: list[str]  # Absolute paths to generated .jpg files
    chapter_image_path: str  # Absolute path to the chapter cover image (.jpg)

    # --- Final output ---
    output_zip_path: str  # Absolute path to the final .zip file
