"""
Pydantic models for the Daskalo content generation pipeline.

These models serve three purposes:
  1. Enforce the LLM structured output schema (GeneratedContent, ReviewResult).
  2. Type the state that flows through LangGraph nodes.
  3. Drive the descriptor.json serialisation in package_output.

Exercise types and their grading location:
  Frontend-graded : slang_matcher, vocab_flashcard, fill_in_the_blank,
                    word_scramble, odd_one_out, sentence_reorder,
                    passage_comprehension, listening_comprehension,
                    roleplay_choice, dialogue_completion, cultural_context,
                    pronunciation_practice, conversation
  Backend-graded  : image_description, translation_challenge, dictation
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Lesson length
# ---------------------------------------------------------------------------


class LessonLength(StrEnum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


LESSON_CONFIG: dict[str, dict] = {
    LessonLength.SHORT: {
        "passage_sentences": "8-12",
        "vocab_count": "12-18",
        "grammar_concepts": "2-3",
        "exercise_count": "4-5",
        "available_types": [
            "slang_matcher",
            "fill_in_the_blank",
            "word_scramble",
            "odd_one_out",
            "sentence_reorder",
            "passage_comprehension",
            "roleplay_choice",
            "cultural_context",
            "conversation",
            "image_description",
        ],
    },
    LessonLength.MEDIUM: {
        "passage_sentences": "12-20",
        "vocab_count": "20-30",
        "grammar_concepts": "3-5",
        "exercise_count": "7-9",
        "available_types": [
            "slang_matcher",
            "fill_in_the_blank",
            "word_scramble",
            "odd_one_out",
            "sentence_reorder",
            "passage_comprehension",
            "roleplay_choice",
            "cultural_context",
            "translation_challenge",
            "listening_comprehension",
            "dictation",
            "dialogue_completion",
            "conversation",
            "image_description",
        ],
    },
    LessonLength.LONG: {
        "passage_sentences": "20-30",
        "vocab_count": "30-45",
        "grammar_concepts": "4-6",
        "exercise_count": "11-14",
        "available_types": [
            "slang_matcher",
            "fill_in_the_blank",
            "word_scramble",
            "odd_one_out",
            "sentence_reorder",
            "passage_comprehension",
            "roleplay_choice",
            "cultural_context",
            "translation_challenge",
            "listening_comprehension",
            "dictation",
            "dialogue_completion",
            "conversation",
            "image_description",
            "pronunciation_practice",
        ],
    },
}

# ---------------------------------------------------------------------------
# Passage sentence (Greek + English translation)
# ---------------------------------------------------------------------------


class PassageSentence(BaseModel):
    greek: str = Field(description="One sentence of the passage in Greek.")
    english: str = Field(description="The full English translation of this Greek sentence.")


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------


class VocabularyItem(BaseModel):
    model_config = ConfigDict(frozen=False)

    greek: str
    english: str
    audioPath: str | None = None  # Set by generate_media; backend replaces with GCS URL


# ---------------------------------------------------------------------------
# Grammar notes
# ---------------------------------------------------------------------------


class GrammarExample(BaseModel):
    model_config = ConfigDict(frozen=False)

    greek: str
    english: str
    note: str | None = None
    audioPath: str | None = None  # Set by generate_media (per-example TTS); replaced with GCS URL on ingest


class GrammarNote(BaseModel):
    model_config = ConfigDict(frozen=False)

    heading: str
    explanation: str
    examples: list[GrammarExample]
    grammar_table: str | None = Field(
        default=None,
        description=(
            "A Markdown pipe-table (| col | col |) presenting structured linguistic data. "
            "Use this field generously — provide a table whenever a tabular layout makes the "
            "concept clearer. This includes (but is not limited to): "
            "verb conjugations (all 6 persons), noun/adjective declensions (all 4 cases × singular & plural), "
            "pronoun paradigms, the Greek alphabet (letter, name, pronunciation, example word), "
            "numbers (numeral, Greek word, pronunciation), prepositions with the cases they govern, "
            "grouped expressions or collocations, and any other paradigm or inventory that benefits "
            "from a side-by-side layout. "
            "Leave null ONLY for purely narrative/cultural notes where no structured data exists."
        ),
    )
    image_prompt: str | None = Field(
        default=None,
        description=(
            "Optional English prompt for AI image generation if a visual illustration "
            "would help explain this grammar concept (e.g. a diagram showing verb conjugation in context, "
            "or a scene illustrating a grammatical structure). Leave null if not applicable."
        ),
    )
    imagePath: str | None = None  # Set by generate_media; backend replaces with GCS URL
    audioPath: str | None = (
        None  # Legacy: single combined audio for all examples (deprecated). New chapters use per-example audioPath on each GrammarExample.
    )


# ---------------------------------------------------------------------------
# Exercise types
# ---------------------------------------------------------------------------

# 1. slang_matcher --------------------------------------------------------


class SlangMatcherPair(BaseModel):
    formal: str
    slang: str


class SlangMatcherData(BaseModel):
    pairs: list[SlangMatcherPair]


class SlangMatcherExercise(BaseModel):
    type: Annotated[str, Field(pattern="^slang_matcher$")]
    prompt: str
    data: SlangMatcherData


# 2. vocab_flashcard -------------------------------------------------------


class FlashcardItem(BaseModel):
    greek: str
    english: str


class VocabFlashcardData(BaseModel):
    cards: list[FlashcardItem]


class VocabFlashcardExercise(BaseModel):
    type: Annotated[str, Field(pattern="^vocab_flashcard$")]
    prompt: str
    data: VocabFlashcardData


# 3. fill_in_the_blank -----------------------------------------------------


class FillBlankOption(BaseModel):
    text: str
    isCorrect: bool


class FillInTheBlankData(BaseModel):
    sentence: str  # Greek sentence with "___" marking the blank
    options: list[FillBlankOption]


class FillInTheBlankExercise(BaseModel):
    type: Annotated[str, Field(pattern="^fill_in_the_blank$")]
    prompt: str
    data: FillInTheBlankData


# 4. word_scramble ---------------------------------------------------------


class WordScrambleData(BaseModel):
    word: str  # Correct Greek word
    scrambled: str  # Same letters in random order


class WordScrambleExercise(BaseModel):
    type: Annotated[str, Field(pattern="^word_scramble$")]
    prompt: str
    data: WordScrambleData


# 5. odd_one_out -----------------------------------------------------------


class OddOneOutData(BaseModel):
    words: list[str]  # Exactly 4 Greek words
    correct_index: int  # 0-based index of the odd one out


class OddOneOutExercise(BaseModel):
    type: Annotated[str, Field(pattern="^odd_one_out$")]
    prompt: str
    data: OddOneOutData


# 6. image_description -----------------------------------------------------


class ImageDescriptionExercise(BaseModel):
    model_config = ConfigDict(frozen=False)

    type: Annotated[str, Field(pattern="^image_description$")]
    prompt: str
    imagePath: str | None = None  # Set by generate_media; backend replaces with GCS URL


# 7. translation_challenge -------------------------------------------------


class TranslationChallengeData(BaseModel):
    english_sentence: str  # The sentence the student must translate into Greek


class TranslationChallengeExercise(BaseModel):
    type: Annotated[str, Field(pattern="^translation_challenge$")]
    prompt: str
    data: TranslationChallengeData


# 8. sentence_reorder ------------------------------------------------------


class SentenceReorderData(BaseModel):
    correct_order: list[str]  # Greek words in the correct sequence
    scrambled_order: list[str]  # Same words in a randomised sequence


class SentenceReorderExercise(BaseModel):
    type: Annotated[str, Field(pattern="^sentence_reorder$")]
    prompt: str
    data: SentenceReorderData


# 9. passage_comprehension -------------------------------------------------


class ComprehensionOption(BaseModel):
    text: str
    isCorrect: bool


class ComprehensionQuestion(BaseModel):
    question: str
    options: list[ComprehensionOption]


class PassageComprehensionData(BaseModel):
    questions: list[ComprehensionQuestion]


class PassageComprehensionExercise(BaseModel):
    type: Annotated[str, Field(pattern="^passage_comprehension$")]
    prompt: str
    data: PassageComprehensionData


# 10. listening_comprehension ----------------------------------------------


class ListeningOption(BaseModel):
    text: str
    isCorrect: bool


class ListeningComprehensionData(BaseModel):
    sentence_index: int  # 0-based index into the per-sentence audio clips
    question: str
    options: list[ListeningOption]


class ListeningComprehensionExercise(BaseModel):
    type: Annotated[str, Field(pattern="^listening_comprehension$")]
    prompt: str
    data: ListeningComprehensionData


# 11. dictation ------------------------------------------------------------


class DictationData(BaseModel):
    sentence_index: int  # 0-based index into the per-sentence audio clips


class DictationExercise(BaseModel):
    type: Annotated[str, Field(pattern="^dictation$")]
    prompt: str
    data: DictationData


# 12. pronunciation_practice -----------------------------------------------


class PronunciationPracticeData(BaseModel):
    target_text: str  # The Greek text the student must pronounce


class PronunciationPracticeExercise(BaseModel):
    model_config = ConfigDict(frozen=False)

    type: Annotated[str, Field(pattern="^pronunciation_practice$")]
    prompt: str
    data: PronunciationPracticeData
    audioPath: str | None = None  # Dedicated Piper clip generated for target_text


# 13. roleplay_choice ------------------------------------------------------


class RoleplayOption(BaseModel):
    text: str
    isCorrect: bool


class RoleplayData(BaseModel):
    options: list[RoleplayOption]


class RoleplayExercise(BaseModel):
    type: Annotated[str, Field(pattern="^roleplay_choice$")]
    prompt: str
    data: RoleplayData


# 14. dialogue_completion --------------------------------------------------


class DialogueCompletionOption(BaseModel):
    text: str
    isCorrect: bool


class DialogueCompletionData(BaseModel):
    dialogue: list[str]  # Lines of dialogue; the missing line is represented as "___"
    options: list[DialogueCompletionOption]


class DialogueCompletionExercise(BaseModel):
    type: Annotated[str, Field(pattern="^dialogue_completion$")]
    prompt: str
    data: DialogueCompletionData


# 15. cultural_context -----------------------------------------------------


class CulturalOption(BaseModel):
    text: str
    isCorrect: bool


class CulturalContextData(BaseModel):
    fact: str  # Background cultural information presented to the student
    question: str
    options: list[CulturalOption]


class CulturalContextExercise(BaseModel):
    type: Annotated[str, Field(pattern="^cultural_context$")]
    prompt: str
    data: CulturalContextData


# 16. conversation ---------------------------------------------------------


class ConversationLine(BaseModel):
    speaker: Annotated[str, Field(pattern="^(male|female)$")]
    text: str  # Greek dialogue line spoken by this speaker
    translation: str = Field(description="English translation of the Greek line, shown below the bubble.")
    audioPath: str | None = None  # Set by generate_media; relative path to the audio clip


# Checkpoint question types -----------------------------------------------


class McqCheckpoint(BaseModel):
    """Multiple-choice checkpoint: student picks the best Greek option."""

    type: Literal["mcq"] = "mcq"
    after_line_index: int = Field(
        description="0-based index of the last conversation line in this chunk, after which the question appears."
    )
    question: str = Field(description="Short English question asking which option best fits / what happens next.")
    options: list[Annotated[dict, Field(description="Each option has 'text' (Greek) and 'isCorrect' (bool).")]]


class TrueFalseCheckpoint(BaseModel):
    """True/False checkpoint based on the conversation so far."""

    type: Literal["true_false"] = "true_false"
    after_line_index: int = Field(
        description="0-based index of the last conversation line in this chunk, after which the question appears."
    )
    statement: str = Field(description="An English statement about the conversation that is either true or false.")
    is_true: bool = Field(description="Whether the statement is true (True) or false (False).")


class TranslationCheckpoint(BaseModel):
    """Translation checkpoint: student translates a short Greek phrase from the conversation into English."""

    type: Literal["translation"] = "translation"
    after_line_index: int = Field(
        description="0-based index of the last conversation line in this chunk, after which the question appears."
    )
    greek_phrase: str = Field(description="A short Greek phrase from the conversation for the student to translate.")
    english_answer: str = Field(description="The correct English translation of the Greek phrase.")


ConversationCheckpoint = Union[McqCheckpoint, TrueFalseCheckpoint, TranslationCheckpoint]


class ConversationData(BaseModel):
    topic_description: str = Field(
        description="A brief English description of the conversation scenario and what is being discussed."
    )
    lines: list[ConversationLine] = Field(
        description=(
            "The full conversation. Aim for 8-16 lines alternating between male and female speakers. "
            "Each line is a natural, complete Greek utterance appropriate for the lesson level."
        )
    )
    checkpoints: list[
        Annotated[McqCheckpoint | TrueFalseCheckpoint | TranslationCheckpoint, Field(discriminator="type")]
    ] = Field(
        description=(
            "2-4 checkpoints placed at natural break points in the conversation. "
            "Use a variety of types: 'mcq' (3 Greek options, one correct), "
            "'true_false' (an English statement the student marks true or false), "
            "'translation' (a short Greek phrase from the conversation to translate into English). "
            "Do not use the same type for consecutive checkpoints."
        )
    )


class ConversationExercise(BaseModel):
    model_config = ConfigDict(frozen=False)

    type: Annotated[str, Field(pattern="^conversation$")]
    prompt: str
    data: ConversationData


# ---------------------------------------------------------------------------
# Discriminated union of all exercise types
# ---------------------------------------------------------------------------

Exercise = (
    SlangMatcherExercise
    | VocabFlashcardExercise
    | FillInTheBlankExercise
    | WordScrambleExercise
    | OddOneOutExercise
    | ImageDescriptionExercise
    | TranslationChallengeExercise
    | SentenceReorderExercise
    | PassageComprehensionExercise
    | ListeningComprehensionExercise
    | DictationExercise
    | PronunciationPracticeExercise
    | RoleplayExercise
    | DialogueCompletionExercise
    | CulturalContextExercise
    | ConversationExercise
)

# ---------------------------------------------------------------------------
# Internal-only: image generation prompts (not included in descriptor.json)
# ---------------------------------------------------------------------------


class ImagePrompt(BaseModel):
    exercise_index: int  # 0-based index into the exercises list
    prompt: str  # English prompt for Vertex AI image generation


# ---------------------------------------------------------------------------
# LLM structured output schemas
# ---------------------------------------------------------------------------


class GrammarConceptOutline(BaseModel):
    concept: str = Field(description="The name of the grammar concept")
    brief_explanation: str = Field(description="A very short explanation of how it's used in the passage")


class LessonPlan(BaseModel):
    """Output schema for the plan_lesson node."""

    chapter_title: str = Field(
        description=(
            "A creative, engaging English title for this chapter (e.g. 'Lost in Monastiraki'). "
            "Should be evocative and specific — not just a plain topic label."
        )
    )
    chapter_summary: str = Field(
        description=(
            "A single sentence in English pitching the lesson scenario to the learner "
            "(e.g. 'You\\'re wandering through the flea market and need to ask for directions to the Acropolis.'). "
            "Written in second person, warm and inviting."
        )
    )
    chapter_introduction: str = Field(
        description=(
            "A 2-3 paragraph English introduction designed to spark interest and raise the mood before the lesson begins. "
            "It should 'lure' the student in by vividly setting the cultural or historical context of the scenario. "
            "Make them curious and excited to learn. Do NOT include any Greek text or grammar rules here."
        )
    )
    chapter_image_prompt: str = Field(
        description=(
            "An English prompt for AI image generation that captures the lesson's scenario as a cover image. "
            "Should depict the main scene of the lesson vividly "
            "(e.g. 'A tourist looking at a map in a bustling Athens flea market, Mediterranean sunlight, "
            "colourful stalls in the background.'). No text or letters in the image."
        )
    )
    passage: list[PassageSentence] = Field(
        description=(
            "The reading passage as a list of sentence objects. Each object has 'greek' (the Greek sentence) "
            "and 'english' (its full English translation). Do NOT return the passage as a plain string."
        )
    )
    vocabulary: list[VocabularyItem]
    grammar_concept_outlines: list[GrammarConceptOutline]


class LessonExercises(BaseModel):
    """Output schema for the generate_exercises node."""

    grammar_notes: list[GrammarNote]
    exercises: list[Exercise]
    image_prompts: list[ImagePrompt]  # One entry per image_description exercise


class ReviewResult(BaseModel):
    """Output schema for the review_content node."""

    approved: bool
    tone_ok: bool
    accuracy_ok: bool
    level_ok: bool
    slang_ok: bool
    exercises_ok: bool
    culture_ok: bool
    issues: list[str]  # Empty list when approved


# ---------------------------------------------------------------------------
# Split-pipeline output schemas (new parallel nodes)
# ---------------------------------------------------------------------------


class DraftLesson(BaseModel):
    """Output schema for the draft_lesson_core node."""

    chapter_title: str = Field(
        description=(
            "A creative, engaging English title for this chapter (e.g. 'Lost in Monastiraki'). "
            "Should be evocative and specific — not just a plain topic label."
        )
    )
    chapter_summary: str = Field(
        description=(
            "A single sentence in English pitching the lesson scenario to the learner "
            "(e.g. 'You\\'re wandering through the flea market and need to ask for directions to the Acropolis.'). "
            "Written in second person, warm and inviting."
        )
    )
    chapter_introduction: str = Field(
        description=(
            "A 2-3 paragraph English introduction designed to spark interest and raise the mood before the lesson begins. "
            "It should 'lure' the student in by vividly setting the cultural or historical context of the scenario. "
            "Make them curious and excited to learn. Do NOT include any Greek text or grammar rules here."
        )
    )
    chapter_image_prompt: str = Field(
        description=(
            "An English prompt for AI image generation that captures the lesson's scenario as a cover image. "
            "Should depict the main scene of the lesson vividly. No text or letters in the image."
        )
    )
    narrator_gender: Literal["male", "female"] = Field(
        description="Choose the most appropriate voice gender for narrating this passage based on its perspective or main character."
    )
    passage: list[PassageSentence] = Field(
        description=(
            "The reading passage as a list of sentence objects. Each object has 'greek' (the Greek sentence) "
            "and 'english' (its full English translation). Do NOT return the passage as a plain string."
        )
    )


class VocabularyResult(BaseModel):
    """Output schema for the extract_vocabulary node."""

    vocabulary: list[VocabularyItem]


class GrammarOutlinesResult(BaseModel):
    """Output schema for the extract_grammar_outlines node."""

    grammar_concept_outlines: list[GrammarConceptOutline]


class GrammarNotesResult(BaseModel):
    """Output schema for the generate_grammar_notes node."""

    grammar_notes: list[GrammarNote]


class ExercisesResult(BaseModel):
    """Output schema for the generate_exercises node (exercises only, no grammar notes)."""

    exercises: list[Exercise]
    image_prompts: list[ImagePrompt]  # One entry per image_description exercise
