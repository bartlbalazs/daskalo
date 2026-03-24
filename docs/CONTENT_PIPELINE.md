# Content Generation Pipeline (LangGraph)

This document details the state machine and logic for the local Python CLI operator tool.

## 1. Overview

The Content Generation Pipeline uses LangChain, LangGraph, and Google Gemini to orchestrate
multiple LLM calls and local tool invocations (Piper TTS, Vertex AI image generation) to produce
a comprehensive language lesson package.

All LLM calls use **structured output** (`with_structured_output(PydanticModel, method="json_schema")`),
meaning the model's output is constrained at generation time and validated against typed Pydantic schemas.
There are no manual JSON parsing steps or markdown-fence stripping.

**Model**: `gemini-3.1-pro-preview` (both generation and review nodes).

---

## 2. Lesson Length Categories

Operators choose a lesson length when running the CLI. This controls passage length, vocabulary count,
grammar concept count, exercise count, and the pool of available exercise types.

| Category | Passage     | Vocabulary | Grammar     | Exercises | Available types                             |
|----------|-------------|------------|-------------|-----------|---------------------------------------------|
| Short    | 6-10 sentences | 10-15 words  | 2-3 concepts   | 3-4         | Frontend-graded only (9 types)              |
| Medium   | 10-16 sentences | 16-25 words | 3-5 concepts| 6-8       | All except `image_description`, `pronunciation_practice` (13 types) |
| Long     | 16-24 sentences| 25-35 words| 4-6 concepts| 10-12       | All 15 types                                |

---

## 3. LangGraph State

```python
class ContentState(TypedDict):
    # Operator inputs
    phase_id: str
    curriculum_chapter_id: str  # e.g., p1_c1
    variant_id: str             # e.g., p1_c1_hotel
    chapter_order: int
    chapter_topic: str
    student_interests: str
    lesson_length: str          # "short" | "medium" | "long"

    # Curriculum constraints (from build_context)
    target_grammar: str
    mandatory_vocabulary: list[str]
    accumulated_grammar: str
    accumulated_vocabulary: list[str]

    # LLM-generated metadata
    chapter_title: str
    chapter_summary: str
    chapter_image_prompt: str

    # Generated content (Pydantic model instances)
    greek_passage: str
    grammar_notes: list[GrammarNote]       # Structured: heading + explanation + examples
    vocabulary: list[VocabularyItem]       # Mutable: audioPath set by generate_media
    exercises: list[Exercise]              # Discriminated union of 15 exercise types

    # Internal (not included in descriptor.json)
    image_prompts: list[ImagePrompt]       # One per image_description exercise
    review_feedback: str                   # Empty string means APPROVED
    generation_attempts: int

    # Asset paths
    work_dir: str
    audio_files: list[str]                 # Vocab + full passage + pronunciation clips
    sentence_audio_files: list[str]        # Per-sentence passage clips (index-aligned)
    image_files: list[str]
    chapter_image_path: str                # Cover image

    # Final output
    output_zip_path: str
```

---

## 4. Nodes and Workflow

```
START
  │
  ▼
build_context ──► generate_content ──► review_content ──► (approved or max retries) ──► generate_media ──► package_output ──► END
                        ▲                   │
                        └── (needs retry) ──┘
```

### Node 1: `build_context`

- Parses `shared/data/curriculum.yaml`.
- Extracts `target_grammar` and `mandatory_vocabulary` for the selected `curriculum_chapter_id`.
- Computes `accumulated_grammar` and `accumulated_vocabulary` from all preceding chapters.
- Injects these constraints into `ContentState` to guide the LLM.

### Node 2: `generate_content`

- **Model**: `gemini-3.1-pro-preview`
- **Structured output**: `GeneratedContent` Pydantic model
- **Retry**: Up to 3 LLM call retries (2 s sleep between) on `ValidationError` / `ValueError`
- **Prompt inputs**: `chapter_topic`, `student_interests`, `lesson_length`, passage/vocab/exercise counts,
  filtered list of available exercise types, review feedback from prior cycle (if any)
- **Output fields**: `greek_passage`, `grammar_notes`, `vocabulary`, `exercises`, `image_prompts`
- Increments `generation_attempts`. Resets `review_feedback` to `""`.

`GeneratedContent` schema:
```python
class GeneratedContent(BaseModel):
    greek_passage: str
    grammar_notes: list[GrammarNote]
    vocabulary: list[VocabularyItem]
    exercises: list[Exercise]          # discriminated union of all 15 types
    image_prompts: list[ImagePrompt]   # internal; one per image_description exercise
```

### Node 3: `review_content`

- **Model**: `gemini-3.1-pro-preview`
- **Structured output**: `ReviewResult` Pydantic model
- **Retry**: Same 3-attempt retry logic as generate_content
- **Evaluates**: tone, accuracy, level, slang, exercises — one boolean per category
- **Output**: sets `review_feedback` to a formatted issues list (empty string if approved)

`ReviewResult` schema:
```python
class ReviewResult(BaseModel):
    approved: bool
    tone_ok: bool
    accuracy_ok: bool
    level_ok: bool
    slang_ok: bool
    exercises_ok: bool
    issues: list[str]   # one entry per problem found; empty if approved
```

### Conditional edge: `should_regenerate`

- If `review_feedback` is non-empty **and** `generation_attempts < MAX_RETRIES (2)`: route back to `generate_content`
- Otherwise: route to `generate_media` (proceeds with best content even if feedback remains)

### Node 4: `generate_media`

Generates all audio and image assets in sequence.

**TTS engine**: Google Cloud Text-to-Speech. Two voice tiers are used:
- **Chirp3-HD** (`el-GR-Chirp3-HD-Achernar` female / `el-GR-Chirp3-HD-Charon` male) — highest
  quality, used for vocabulary pronunciation where clarity per word matters most.
- **WaveNet** (`el-GR-Wavenet-B` female) — high quality, cost-efficient, used for longer narration
  (full passage, per-sentence clips, pronunciation practice).

Both tiers use Application Default Credentials (the same GCP project as the rest of the CLI).

1. **Vocabulary audio** — one Cloud TTS `.mp3` per vocabulary word (alternating female/male
   Chirp3-HD voices). `VocabularyItem.audioPath` is set on the mutable Pydantic model.

2. **Full passage audio** — one WaveNet `.mp3` of the complete reading passage (female narrator).

3. **Per-sentence audio** — the passage is split into sentences; one WaveNet `.mp3` per sentence
   (`sentence_00.mp3`, `sentence_01.mp3`, …). Stored index-aligned in `sentence_audio_files`.
   Referenced by `listening_comprehension` and `dictation` exercises via `sentence_index`.

4. **Pronunciation practice audio** — one dedicated WaveNet `.mp3` per `pronunciation_practice`
   exercise (target text chosen by the LLM: word, phrase, or sentence).
   `PronunciationPracticeExercise.audioPath` is set on the mutable Pydantic model.

5. **Exercise images** — one Vertex AI image generation call per `image_description` exercise.
   Image prompts come from the `image_prompts` state field (keyed by exercise index).
   `ImageDescriptionExercise.imagePath` is set on the mutable Pydantic model.

### Node 5: `package_output`

- Serialises all Pydantic models to plain dicts via `.model_dump()`
- Converts absolute local asset paths to ZIP-internal relative paths
  (e.g. `/tmp/daskalo_work_xyz/vocab_00_καλημέρα.mp3` → `assets/audio/vocab_00_καλημέρα.mp3`)
- `image_prompts` (internal-only) are excluded from `descriptor.json`
- Produces a `.zip` file with:
  ```
  chapter_id.zip
  ├── descriptor.json
  └── assets/
      ├── audio/
      │   ├── vocab_00_*.mp3
      │   ├── passage.mp3
      │   ├── pronunciation_*.mp3
      │   └── sentences/
      │       ├── sentence_00.mp3
      │       └── sentence_01.mp3
      └── images/
          └── exercise_image_*.jpg
  ```

---

## 5. Exercise Types (15 total)

| # | Type | Grading | Description |
|---|------|---------|-------------|
| 1 | `slang_matcher` | Frontend | Match formal Greek phrases to slang equivalents |
| 2 | `vocab_flashcard` | None (review) | Flip card: Greek → English; self-paced review |
| 3 | `fill_in_the_blank` | Frontend | Greek sentence with blank; pick from 3-4 options |
| 4 | `word_scramble` | Frontend | Unscramble letters of a single Greek word |
| 5 | `odd_one_out` | Frontend | Identify the word that doesn't belong among 4 |
| 6 | `image_description` | Backend | Write Greek description of an AI-generated image |
| 7 | `translation_challenge` | Backend | Translate an English sentence into Greek |
| 8 | `sentence_reorder` | Frontend | Drag Greek words into correct sentence order |
| 9 | `passage_comprehension` | Frontend | MC questions about the reading passage |
| 10 | `listening_comprehension` | Frontend | Listen to a passage sentence; answer MC question |
| 11 | `dictation` | Backend | Listen to a passage sentence; type what you hear |
| 12 | `pronunciation_practice` | Frontend | Pronounce a target text; graded via Web Speech API |
| 13 | `roleplay_choice` | Frontend | Pick the right Greek response to a scenario |
| 14 | `dialogue_completion` | Frontend | Fill the missing line in a short Greek dialogue |
| 15 | `cultural_context` | Frontend | MC question about Greek customs or etiquette |

---

## 6. Pydantic Models

All models live in `content-cli/models/content_models.py`. Key design decisions:

- `VocabularyItem`, `ImageDescriptionExercise`, and `PronunciationPracticeExercise` use
  `model_config = ConfigDict(frozen=False)` so `generate_media` can set asset paths in place.
- All other models are effectively immutable (default Pydantic behaviour).
- `Exercise` is a plain `Union` of all 15 exercise types. Pydantic validates against each member
  in order using the `type` string field.
- `LessonLength` is a `str` enum with values `"short"`, `"medium"`, `"long"`.
- `LESSON_CONFIG` maps each `LessonLength` to its passage/vocab/exercise count constraints and
  the allowed exercise type list for that length.

---

## 7. Running the CLI

```bash
cd content-cli
uv sync

# Interactive mode (local emulator, default)
uv run daskalo generate

# Interactive mode with direct Firestore/Storage ingest (local emulator)
uv run daskalo generate --direct

# Production (Vertex AI + real GCS/Firestore, no emulator)
uv run daskalo generate --no-local
```

**Flags:**
- `--local` / `--no-local` (default: `--local`): Target local Firebase emulator or production GCP.
- `--direct`: After packaging, immediately upload the ZIP to Firebase Storage and ingest into Firestore.
  Requires `--local` (cannot be used with `--no-local`).

The operator is prompted for:
1. Phase (selected from curriculum)
2. Chapter (selected from curriculum)
3. Topic description (e.g. `Hotel check-in`)
4. Student interests (optional, e.g. `football, cooking`)
5. Lesson length (`1` = short, `2` = medium, `3` = long)

The CLI uses these inputs to determine the `variant_id` (e.g. `p1_c2_hotel_check_in`).

Output: a `.zip` file in `./output/` ready to upload to the GCS ingestion bucket.
