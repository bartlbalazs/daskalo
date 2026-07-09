# Content Generation Pipeline (LangGraph)

This document details the state machine and logic for the local Python CLI operator tool
in `content-cli/`. It reflects the current code as of the parallel-split pipeline
(`content-cli/graph.py`) — see that file for the authoritative topology.

## 1. Overview

The Content Generation Pipeline uses LangChain, LangGraph, and Google Gemini to orchestrate
multiple LLM calls and API-based media generation (Google Cloud Text-to-Speech, Gemini image
generation) to produce a comprehensive language lesson package.

All LLM calls use **structured output** (`with_structured_output(PydanticModel, method="json_schema")`),
meaning the model's output is constrained at generation time and validated against typed Pydantic schemas.
There are no manual JSON parsing steps or markdown-fence stripping.

**Models**:
- `gemini-3.1-pro-preview` — the higher-quality model used for creative/generative steps
  (`draft_lesson_core`, `generate_grammar_notes`, `generate_exercises`, `generate_grammar_summary`,
  and practice-set generation).
- `gemini-2.5-flash` — the faster/cheaper model used for extraction and review steps
  (`extract_vocabulary`, `extract_grammar_outlines`, `review_content`).

**Media**: Google Cloud Text-to-Speech (Chirp3-HD voices) for all audio, and Gemini image
generation (`gemini-3-pro-image-preview`) for all images. Piper and WaveNet are **not** used
anywhere in this pipeline.

**Resumability**: the compiled graph is backed by a SQLite checkpointer
(`langgraph-checkpoint-sqlite`, one `.checkpoints/{thread_id}.sqlite` file per run). If a run
fails partway through, re-running the exact same `daskalo generate` command recomputes the same
`thread_id` and resumes from the last completed node instead of repeating already-completed
(and possibly expensive) LLM calls. See `content-cli/graph.py` and `content-cli/main.py`.

---

## 2. Lesson Length Categories

Operators choose a lesson length when running the CLI (or it defaults to the curriculum
chapter's `suggested_length`). This controls passage length, vocabulary count, grammar concept
count, exercise count, and the pool of available exercise types. Exact values live in
`LESSON_CONFIG` in `content-cli/models/content_models.py`.

| Category | Passage | Vocabulary | Grammar concepts | Exercises | Available exercise types |
|----------|---------|------------|-------------------|-----------|---------------------------|
| Short    | 8-12 sentences  | 12-18 words | 2-3 concepts | 4-5   | 10 types (no `translation_challenge`, `listening_comprehension`, `dictation`, `dialogue_completion`, `pronunciation_practice`) |
| Medium   | 12-20 sentences | 20-30 words | 3-5 concepts | 7-9   | 14 types (all except `pronunciation_practice`) |
| Long     | 20-30 sentences | 30-45 words | 4-6 concepts | 11-14 | 15 types (all except `vocab_flashcard` and `matching`) |

`pronunciation_practice` is therefore only ever requested for `long` lessons. `generate_exercises`
and `review_content` interpolate their "must include pronunciation_practice" instructions
conditionally on this (see `prompts/content_prompts.py`'s `pronunciation_requirement_text` /
`pronunciation_review_note_text` helpers) so the prompts never contradict the allowed type set.

`vocab_flashcard` and `matching` are modelled (see §5) but are not requested by any
`LESSON_CONFIG` pool for chapters — `matching` is exclusively used by the Practice Set
pipeline, though chapter packaging/ingest still handle it defensively if ever emitted.

---

## 3. LangGraph State

```python
class ContentState(TypedDict):
    # Operator inputs
    book_id: str
    curriculum_chapter_id: str  # e.g. b1_c2
    variant_id: str             # e.g. b1_c2_lost_in_monastiraki (derived from the LLM-generated title)
    chapter_order: int
    chapter_topic: str
    student_interests: str
    lesson_length: str          # "short" | "medium" | "long"

    # Curriculum constraints (from build_context, computed dynamically from shared/data/books/*.yaml)
    target_grammar: str
    language_skill: str
    mandatory_vocabulary: list[str]
    accumulated_grammar: str
    accumulated_vocabulary: list[str]
    cefr_level: str              # e.g. "A1.1", "B2", "C1.2"

    # LLM-generated metadata
    chapter_title: str
    chapter_summary: str
    chapter_introduction: str
    chapter_image_prompt: str
    narrator_gender: str          # "male" | "female"

    # Generated content (Pydantic model instances)
    passage: list[PassageSentence]                       # list of {greek, english} sentence objects
    vocabulary: list[VocabularyItem]                      # audioPath set by generate_media
    grammar_concept_outlines: list[GrammarConceptOutline]
    grammar_notes: list[GrammarNote]                      # heading + explanation + examples + optional table
    exercises: list[Exercise]                             # discriminated union of 17 exercise types

    # Pre-generated grammar reference (stored on the chapter, shared by all students)
    grammar_summary: str

    # Internal (not included in descriptor.json)
    image_prompts: list[ImagePrompt]       # one per image_description exercise
    review_feedback: str                   # empty string means APPROVED
    generation_attempts: int

    # Asset paths (local filesystem within work_dir)
    work_dir: str
    audio_files: list[str]                 # every generated .mp3 (all roles)
    audio_assets: list[AudioAsset]          # {role, path} records — drives packaging routing (see §4, node 9)
    passage_audio_path: str                # full-passage clip, set explicitly (not inferred from a filename)
    sentence_audio_files: list[str]        # per-sentence passage clips (index-aligned)
    image_files: list[str]
    chapter_image_path: str                # cover image

    # Final output
    output_zip_path: str
```

`AudioAsset` (`content-cli/state.py`) is `{"role": "vocab" | "passage" | "grammar" |
"pronunciation" | "conversation" | "matching", "path": str}`. It exists specifically so that
ZIP folder routing and descriptor serialisation never have to infer an asset's purpose from its
filename (early versions of this pipeline had bugs here: a chapter titled e.g. "A Passage to
Crete" could make the first vocabulary clip match a `"passage"` filename substring check).

---

## 4. Nodes and Workflow

```
START → build_context → draft_lesson_core
        → extract_vocabulary         ┐  (fan-out, parallel)
        → extract_grammar_outlines   ┘
        → generate_grammar_notes  ┐  (fan-out, parallel)
        → generate_exercises      ┘
        → generate_grammar_summary   (after generate_grammar_notes + extract_vocabulary)
        → review_content             (after generate_grammar_summary + generate_exercises)
        → (conditional) → generate_media → package_output → END
```

In plain terms: `build_context` and `draft_lesson_core` run sequentially. `draft_lesson_core`
then fans out to `extract_vocabulary` and `extract_grammar_outlines` in parallel. Once both have
completed, `generate_exercises` and `generate_grammar_notes` run in parallel (both depend on the
outputs of the extraction step). `generate_grammar_summary` runs after `generate_grammar_notes`
+ `extract_vocabulary`. `review_content` is a fan-in barrier that waits for both
`generate_grammar_summary` and `generate_exercises`. Its conditional edge (`should_regenerate`)
either routes back to `draft_lesson_core` (edge key `"regenerate"`, e.g. content rejected and
retries remain) or forward to `generate_media` → `package_output` → `END`.

This is a **10-node graph**: `build_context`, `draft_lesson_core`, `extract_vocabulary`,
`extract_grammar_outlines`, `generate_grammar_notes`, `generate_exercises`,
`generate_grammar_summary`, `review_content`, `generate_media`, `package_output`.

### Node 1: `build_context`

- Loads the curriculum from the per-book YAML files under `shared/data/books/*.yaml` via
  `shared/data/curriculum_loader.py` (there is no monolithic `curriculum.yaml` — see
  `docs/planning/BUGS.md` DOC-05).
- Locates the target chapter and computes `accumulated_grammar` / `accumulated_vocabulary`
  dynamically from every chapter that precedes it (rather than trusting any pre-baked summary
  field in the YAML).
- Exposes the current book's `cefr_level` and the chapter's `language_skill` / `target_grammar` /
  `mandatory_vocabulary` in state.

### Node 2: `draft_lesson_core`

- **Model**: `gemini-3.1-pro-preview` (`GEMINI_LOCATION`, default `global`)
- **Structured output**: `DraftLesson`
- **Retry**: up to 3 LLM call retries (2 s sleep between) via `utils/llm_utils.invoke_with_retry`
- Produces `chapter_title`, `chapter_summary`, `chapter_introduction`, `chapter_image_prompt`,
  `narrator_gender`, and the Greek `passage` (list of `{greek, english}` sentence objects — never
  a plain string).
- Derives `variant_id` by slugifying the LLM-generated title (e.g. `b1_c2` + "Lost in
  Monastiraki" → `b1_c2_lost_in_monastiraki`).
- Increments `generation_attempts` and resets `review_feedback` on every call (including retries
  triggered by `review_content`).

### Node 3: `extract_vocabulary` (parallel with node 4)

- **Model**: `gemini-2.5-flash`
- **Structured output**: `VocabularyResult`
- Extracts the vocabulary list from the passage produced by `draft_lesson_core`, always
  including every `mandatory_vocabulary` word for the chapter.

### Node 4: `extract_grammar_outlines` (parallel with node 3)

- **Model**: `gemini-2.5-flash`
- **Structured output**: `GrammarOutlinesResult`
- Identifies grammar concept outlines (name + brief explanation) illustrated in the passage,
  covering every concept listed in `target_grammar`.

### Node 5: `generate_grammar_notes` (parallel with node 6)

- **Model**: `gemini-3.1-pro-preview`
- **Structured output**: `GrammarNotesResult`
- Expands each grammar concept outline into a full `GrammarNote`: an English heading and
  explanation, 3-5 Greek/English examples, an optional Markdown `grammar_table`, and an optional
  `image_prompt`.

### Node 6: `generate_exercises` (parallel with node 5)

- **Model**: `gemini-3.1-pro-preview`
- **Structured output**: `ExercisesResult`
- Generates the interactive exercises for the lesson, drawn from the `available_types` pool for
  the current `lesson_length` (see §2). Always includes at least one `image_description`
  exercise; includes `pronunciation_practice` only when it's in the pool (`long` only); includes
  exactly one `conversation` exercise whenever `"conversation"` is in the pool.
- Also returns `image_prompts` — one entry per `image_description` exercise, keyed by exercise
  index (kept out of the final descriptor; consumed by `generate_media`).

### Node 7: `generate_grammar_summary`

- **Model**: `gemini-3.1-pro-preview` (raw string output, not structured — this is the one node
  whose output is Markdown prose rather than a Pydantic schema)
- Runs after `generate_grammar_notes` (needs the expanded notes) and `extract_vocabulary` (needs
  the vocabulary list).
- Produces a single self-contained Markdown grammar reference (≈400-800 words) stored on the
  chapter document and shown to students in their Grammar Book — generated once per chapter, not
  per-student.

### Node 8: `review_content`

- **Model**: `gemini-2.5-flash` (`GEMINI_LOCATION`, same env var as every other text-LLM node —
  it used to read `VERTEX_REGION` instead, which is inconsistent and, depending on `.env`, can
  resolve to a different region than the rest of the pipeline)
- **Structured output**: `ReviewResult`
- Evaluates six categories (tone, accuracy, level, slang, exercises, culture) plus strict
  curriculum constraints (target grammar taught, every mandatory vocabulary word present,
  grammar tables present where expected). Sets `review_feedback` to a formatted issue list, or
  `""` when approved.

**Conditional edge — `should_regenerate`**: if `review_feedback` is non-empty and
`generation_attempts < MAX_RETRIES` (2), routes back to `draft_lesson_core` via the `"regenerate"`
edge key. Otherwise (approved, or retries exhausted) proceeds to `generate_media`.

### Node 9: `generate_media`

Generates all audio and image assets in parallel (`ThreadPoolExecutor`, 10 workers for TTS, 5 for
images). Every TTS/image client is constructed once per worker thread (via `threading.local()`)
and reused across all tasks that thread runs, rather than once per individual clip.

**TTS engine**: Google Cloud Text-to-Speech, Chirp3-HD voices only
(`el-GR-Chirp3-HD-Achernar` female / `el-GR-Chirp3-HD-Charon` male). Passage/sentence/vocab/
grammar speaking rate is scaled by book (`0.70`-`1.00`) to help beginners; pronunciation and
conversation-line audio always use the normal `1.0` rate.

1. **Vocabulary audio** — one clip per word, alternating female/male voices.
2. **Full passage audio** — one clip, narrator voice/gender chosen by `draft_lesson_core`.
   Its identity is tracked explicitly via the dedicated `passage_audio_path` state field, not
   inferred later from a filename substring.
3. **Per-sentence audio** — index-aligned with `passage`, stored in `sentence_audio_files`.
   Referenced by `listening_comprehension` / `dictation` exercises via `sentence_index`.
4. **Grammar example audio** — one clip per `GrammarExample` that has Greek text.
5. **Pronunciation practice audio** — one clip per `pronunciation_practice` exercise.
6. **Conversation line audio** — one clip per line of every `conversation` exercise.
7. **Matching pair audio** (defensive; `matching` isn't in any chapter `available_types` pool
   today, but is handled correctly if ever emitted) — one clip per pair.

Every generated file is recorded in `audio_assets` as `{"role": ..., "path": ...}` — `package_output`
(node 10) routes and serialises purely off `role`, never by sniffing filenames.

**Image generation**: `gemini-3-pro-image-preview`, `global` region, up to 8 attempts with
exponential backoff on HTTP 429/503. Generates the cover image, one image per grammar note that
provided an `image_prompt`, and one image per `image_description` exercise.

**Failure threshold**: if the cover image failed, the passage audio failed, or more than ~20% of
all media tasks (TTS + image) failed, `generate_media` raises instead of silently proceeding to
packaging with missing assets. On success it logs `"N/M media assets generated successfully"`.

### Node 10: `package_output`

- Serialises all Pydantic models to plain dicts via `.model_dump()`.
- Converts every asset's absolute local path to a ZIP-relative path
  (e.g. `/tmp/daskalo_work_xyz/vocab_00_καλημέρα.mp3` → `assets/audio/vocab_00_καλημέρα.mp3`).
- Audio ZIP-subfolder routing (`assets/audio/conversation/`, `assets/audio/grammar/`, or the
  `assets/audio/` root for everything else) is driven purely by each `audio_assets` entry's
  `role` — never by checking whether the filename contains `"_conv_"` or `"_grammar_"`.
- `image_prompts` (internal-only) are excluded from `descriptor.json`.
- Produces a `.zip` file:
  ```
  {variant_id}.zip
  ├── descriptor.json
  └── assets/
      ├── audio/
      │   ├── {prefix}vocab_00_*.mp3
      │   ├── {prefix}passage.mp3
      │   ├── {prefix}pronunciation_*.mp3
      │   ├── conversation/
      │   │   └── {prefix}conv_00_line_00_*.mp3
      │   ├── grammar/
      │   │   └── {prefix}grammar_00_ex_00.mp3
      │   └── sentences/
      │       ├── {prefix}sentence_00_*.mp3
      │       └── {prefix}sentence_01_*.mp3
      └── images/
          ├── {prefix}chapter_cover.jpg
          ├── {prefix}grammar_note_00.jpg
          └── {prefix}exercise_image_00.jpg
  ```

---

## 5. Exercise Types (17 modelled)

| # | Type | Grading | Chapter pools | Description |
|---|------|---------|----------------|-------------|
| 1 | `slang_matcher` | Frontend | short, medium, long | Match formal Greek phrases to slang equivalents |
| 2 | `vocab_flashcard` | None (review) | *(none — modelled but not requested by any chapter pool; also explicitly forbidden in Practice Sets)* | Flip card: Greek → English |
| 3 | `fill_in_the_blank` | Frontend | short, medium, long | Greek sentence with blank; pick from 3-4 options |
| 4 | `word_scramble` | Frontend | short, medium, long | Unscramble letters of a single Greek word |
| 5 | `odd_one_out` | Frontend | short, medium, long | Identify the word that doesn't belong among 4 |
| 6 | `image_description` | Backend | short, medium, long (always required) | Write a Greek description of an AI-generated image |
| 7 | `translation_challenge` | Backend | medium, long | Translate an English sentence into Greek |
| 8 | `sentence_reorder` | Frontend | short, medium, long | Drag Greek words into correct sentence order |
| 9 | `passage_comprehension` | Frontend | short, medium, long | MC questions about the reading passage |
| 10 | `listening_comprehension` | Frontend | medium, long | Listen to a passage sentence; answer an MC question |
| 11 | `dictation` | Backend | medium, long | Listen to a passage sentence; type what you hear |
| 12 | `pronunciation_practice` | Frontend | long only | Pronounce a target text; graded via Web Speech API |
| 13 | `roleplay_choice` | Frontend | short, medium, long | Pick the right Greek response to a scenario |
| 14 | `dialogue_completion` | Frontend | medium, long | Fill the missing line in a short Greek dialogue |
| 15 | `cultural_context` | Frontend | short, medium, long | MC question about Greek customs or etiquette |
| 16 | `conversation` | Frontend | short, medium, long (exactly one when available) | Scripted male/female dialogue with MCQ/true-false/translation checkpoints |
| 17 | `matching` | Frontend | *(Practice Sets only — see below; defensively supported but never requested for chapters)* | Match Greek words/phrases to English translations |

---

## 6. Pydantic Models

All models live in `content-cli/models/content_models.py`. Key design decisions:

- `VocabularyItem`, `GrammarExample`, `GrammarNote`, `ImageDescriptionExercise`,
  `PronunciationPracticeExercise`, `ConversationExercise`/`ConversationLine`, and `MatchingPair`
  use `model_config = ConfigDict(frozen=False)` so `generate_media` can set asset paths in place.
- `Exercise` is a plain `Union` of all 17 exercise types; Pydantic validates against each member
  in order using the `type` string field.
- `LessonLength` is a `str` enum (`StrEnum`) with values `"short"`, `"medium"`, `"long"`.
- `LESSON_CONFIG` maps each `LessonLength` to its passage/vocab/exercise count constraints and
  the allowed exercise type list for that length (see §2).
- The pipeline uses a **split-pipeline schema set** — one narrow structured-output schema per
  node instead of one monolithic "plan" schema: `DraftLesson`, `VocabularyResult`,
  `GrammarOutlinesResult`, `GrammarNotesResult`, `ExercisesResult`, `ReviewResult`. This lets
  `extract_vocabulary` / `extract_grammar_outlines` / `generate_exercises` / `generate_grammar_notes`
  run in parallel against the same passage. There is no `LessonPlan` model — an earlier,
  single-shot `plan_lesson` node existed historically but has been removed as dead code (see
  `docs/planning/IMPROVEMENTS.md` IMP-CC-07); `PracticeSetResult` is the equivalent schema for
  the separate Practice Set pipeline (§8).

---

## 7. Checkpointing & Resumability

`content-cli/graph.py`'s `build_graph(thread_id)` compiles the graph with a `SqliteSaver`
checkpointer backed by `content-cli/.checkpoints/{thread_id}.sqlite` (gitignored). `main.py`
computes `thread_id` as a SHA-256 hash of the inputs that fully determine a `generate` run
(`curriculum_chapter_id`, `chapter_topic`, `lesson_length`), truncated to 16 hex characters.

Before invoking the graph, `main.py` checks `graph.get_state(config).next`: if it's non-empty, a
previous run for that exact thread_id stopped partway through, and the graph is invoked with
`None` as input (a true LangGraph resume) instead of a fresh initial state — already-completed
nodes are **not** re-executed. If the graph raises, `main.py` catches the exception, prints a
message telling the operator that re-running the exact same command will resume from the last
completed node, and exits non-zero. The same mechanism is wired into `practice_graph.py` /
`generate-practice`.

---

## 8. Practice Sets (separate, simpler pipeline)

`content-cli/practice_graph.py` builds a 3-node graph — `generate_practice` →
`generate_practice_media` → `package_practice_output` — for the `daskalo generate-practice`
command. It reads an existing chapter ZIP for context (topic, vocabulary, reusable audio) and
generates a 10-12 exercise homework drill via `GENERATE_PRACTICE_PROMPT` /
`PracticeSetResult`, threading the source chapter's actual CEFR level (looked up via
`shared.data.curriculum_loader.find_chapter`) into the prompt instead of a hardcoded level.
Required: at least one `matching` exercise (4 pairs from current vocabulary + 1 from a prior
chapter's vocabulary), exactly one `conversation` exercise, at least one `image_description`
exercise; `vocab_flashcard`/`word_card` are explicitly forbidden.

---

## 9. Running the CLI

```bash
cd content-cli
uv sync

# Fully interactive, writes directly to the local Firestore emulator:
uv run daskalo generate

# Scripted:
uv run daskalo generate --curriculum-chapter b1_c2 --topic "Boxing match" --length long

# Production: generates the ZIP only, no upload (operator uploads to GCS manually):
uv run daskalo generate --no-local --curriculum-chapter b1_c2 --topic "Boxing match"

# Upload an existing ZIP directly into the local Firestore emulator:
uv run daskalo upload output/b1_c2_boxing.zip

# Upload an existing ZIP directly to production GCP (Firestore + GCS):
uv run daskalo upload --remote output/b1_c2_boxing.zip

# Generate a Practice Set from an existing chapter ZIP:
uv run daskalo generate-practice output/b1_c2_boxing.zip
```

There is no `--direct` flag. `--local`/`--no-local` (default `--local`) selects between writing
directly to the Firebase emulator and producing a ZIP for manual upload; `upload --remote` writes
directly to production GCP. Both `generate` and `generate-practice` also accept an optional,
off-by-default `--keep-work-dir` flag that skips the automatic cleanup of the temporary
`output/daskalo_work_*` / `output/daskalo_practice_*` directory after a successful run (useful
for debugging).

The operator is prompted interactively for anything not passed as a flag:
1. Book and chapter (selected from the curriculum) — re-prompts on an out-of-range number instead
   of silently wrapping (`0`) or crashing.
2. Topic description (e.g. `Hotel check-in`).
3. Student interests (optional, e.g. `football, cooking`).
4. Lesson length, if not defaulted from the chapter's `suggested_length`.

The CLI derives `variant_id` from the LLM-generated chapter title once `draft_lesson_core`
completes (e.g. `b1_c2` + "Lost in Monastiraki" → `b1_c2_lost_in_monastiraki`) — not from the raw
topic string.

Output: a `.zip` file in `content-cli/output/` (resolved relative to the `content-cli/` package
directory regardless of the shell's current working directory), ready to upload to the GCS
ingestion bucket if not ingested directly.

---

## 10. opencode Lesson Authoring Integration

The repository includes a project-local opencode workflow for conversational lesson authoring:

```text
.opencode/commands/lesson.md
.opencode/skills/lesson-author/SKILL.md
.opencode/skills/lesson-author/scripts/generate_brief.py
```

Use `/lesson <curriculum_chapter_id>` in opencode to run it. The command loads the
`lesson-author` skill, generates a curriculum-aware brief from the same shared curriculum/build
context code used by `content-cli`, guides the operator through scenario brainstorming, then runs
the existing `uv run daskalo generate --local` command non-interactively.

This integration is intentionally outside `content-cli`: it does not add CLI flags, Firestore
fields, or a direct production publish path. The approved conversation draft is condensed into the
`--topic` seed, so it steers `draft_lesson_core` but is not guaranteed to survive verbatim.
