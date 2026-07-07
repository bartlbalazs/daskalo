# Performance & Reliability Improvements

Items that are not "broken" today but represent real weaknesses in performance, reliability, security posture, or maintainability. All items are in scope for `fix/bugs-and-improvements`.

## Legend

Same as `BUGS.md`: **Severity** (impact if left unaddressed) / **Effort** (S/M/L).

---

## Backend (`backend/`)

| ID | Severity | Effort | Area | Description |
|----|----------|--------|------|-------------|
| IMP-BE-01 | High | M | Reliability | Wrap the `pending → evaluating → completed/error` transition (and the chapter/practice completion read-modify-write) in Firestore transactions so concurrent requests can't double-spend Gemini calls or corrupt state (fixes the root cause behind BE-02, BE-07, BE-08). |
| IMP-BE-02 | High | S | Reliability | Use `firestore.Increment` for **all** XP writes and `ArrayUnion` for **all** ID-list appends, consistently, instead of read-modify-write in Python. |
| IMP-BE-03 | Medium | S | Performance | Construct `firestore.Client` and `genai.Client` once at module scope per function (they are currently created fresh on every invocation), reducing connection setup latency on the hot path. |
| IMP-BE-04 | High | M | Reliability | Centralize Gemini calls behind a small retry helper that (a) retries on transient errors, (b) explicitly handles `response.text is None` (safety-blocked/empty candidates) with a clear error instead of an `AttributeError`/`TypeError`, and (c) wraps `json.loads` in a `try/except` that surfaces a structured error rather than an unhandled exception. |
| IMP-BE-05 | Medium | M | Reliability | Add a recovery path for attempts stuck in `evaluating` (e.g. a `evaluatingSince` timestamp + a check that treats anything older than the function timeout as eligible for re-evaluation), instead of a permanent dead end. |
| IMP-BE-06 | High | S | Security | Add a shared `ensure_active_user(uid, db)` helper (in `callable_helpers.py`) and call it from every function that currently skips the active-status check (fixes BE-05). |
| IMP-BE-07 | Medium | M | Reliability | Add a lightweight per-user rate limiter (Firestore-backed sliding counter, checked in `callable_helpers.py`) as defense-in-depth underneath the existing per-project API Gateway quota (BE-15) — true per-JWT-subject quotas aren't supported by API Gateway's managed-service quota model, so this has to live in application code. |
| IMP-BE-08 | High | L | Testing | Add test coverage for `fn_complete_chapter.py`, `fn_complete_practice.py`, `services/progress.py`, `services/practice_progress.py`, and the `create_own_word` pipeline (currently completely untested). |
| IMP-BE-09 | Low | S | Maintainability | Extract hardcoded model names (`gemini-2.5-flash`) and `PRACTICE_XP` into one shared constants module instead of duplicating across files. |

## Frontend (`frontend/`)

| ID | Severity | Effort | Area | Description |
|----|----------|--------|------|-------------|
| IMP-FE-01 | High | M | Performance | Switch hot-path components (`chapter-detail`, `grammar-book`, exercise components) to `ChangeDetectionStrategy.OnPush` and precompute `marked.parse()` output into a signal/computed instead of calling it from the template — today it re-runs on every change-detection cycle, including ~4×/s during audio playback (`audio-player.component.ts` `timeupdate` updates). |
| IMP-FE-02 | High | M | Performance | Add a shared "resolved download URL" cache (keyed by `gs://` URI) so `getDownloadURL` isn't re-requested by every pipe/button/player instance revisiting the same chapter. |
| IMP-FE-03 | High | M | Performance | Consolidate the duplicated `books`/`chapters` realtime listeners currently opened independently by `LayoutComponent` and `ChaptersPage` into a single shared, cached source in `LessonService`. |
| IMP-FE-04 | Medium | M | UX/Reliability | Add a realtime listener (or periodic refresh) for the current user's document so XP/progress updates propagate live instead of only on explicit `loadCurrentUser()` calls. |
| IMP-FE-05 | High | M | Reliability | Add `response.ok` checks, `AbortController` timeouts, and user-facing retry affordances to every `fetch()` call in `LessonService`/`OwnWordsService` (fixes FE-05, FE-06 systemically). |
| IMP-FE-06 | Medium | S | Reliability | Roll back optimistic updates (favorites toggle) if the underlying Firestore write fails. |
| IMP-FE-07 | High | L | Accessibility | Provide a keyboard-operable alternative to the CDK drag-and-drop interactions in `slang-matcher` and `sentence-reorder` (today these exercises cannot be completed without a pointer, which can block chapter completion entirely for keyboard/AT users). |
| IMP-FE-08 | Medium | M | Accessibility | Add `aria-label`s to icon-only buttons, `role="dialog"`/`aria-modal`/focus trapping to the lightbox, `role="progressbar"`/`aria-valuenow` to progress bars, and a focus-visible affordance for hover-only vocab tooltips. |
| IMP-FE-09 | Medium | S | Maintainability | Resolve the `@angular/fire ^20.0.1` vs `@angular/* ^21.2` peer-dependency mismatch (upgrade `@angular/fire` or pin a compatible combination). |
| IMP-FE-10 | Low | S | Tooling | `npm run lint` currently fails outright — `angular.json` has no `lint` architect target and no ESLint packages are installed. Add `@angular-eslint` via `ng add` so linting actually works. |
| IMP-FE-11 | Low | S | Performance | Add long-lived cache headers for hashed build output in `firebase.json`. |

## Content-CLI (`content-cli/`)

| ID | Severity | Effort | Area | Description |
|----|----------|--------|------|-------------|
| IMP-CC-01 | High | L | Reliability | Add a LangGraph checkpointer (SQLite-backed, keyed by `variant_id`/work dir) so a late-stage failure (e.g. exhausted LLM retry after 5+ expensive Gemini Pro calls) can resume from the last completed node instead of discarding all prior work. Purely an internal reliability mechanism — no change to the existing interactive CLI flow. |
| IMP-CC-02 | High | M | Reliability | Replace filename-substring asset routing (the root cause of CC-01/CC-02) with an explicit role manifest carried in state (e.g. `{"role": "passage", "path": ...}` per generated file) so packaging never has to guess a file's purpose from its name. |
| IMP-CC-03 | Medium | M | Reliability | Add a media-generation failure threshold: if TTS/image generation fails for a meaningful fraction of assets (e.g. cover image, passage audio, or >20% of clips), stop and surface a clear error instead of silently ingesting a chapter with missing audio/images. |
| IMP-CC-04 | Medium | S | Performance | Reuse a single `TextToSpeechClient`/`genai.Client` across the thread-pool tasks in `generate_media.py` instead of constructing a new client per task. |
| IMP-CC-05 | Low | S | Reliability | Make `.env` loading and `output/` path resolution CWD-independent (resolve relative to the package/script location, not the process's current directory). |
| IMP-CC-06 | Low | S | Maintainability | Clean up `output/daskalo_work_*` work directories after a successful run (or add a `--keep-work-dir` flag for debugging). |
| IMP-CC-07 | Low | S | Maintainability | Remove dead code: `nodes/plan_lesson.py`, `PLAN_LESSON_PROMPT`, `LessonPlan`/`LessonExercises` models, the unused `upload_to_storage_emulator`, and the dead `existing_audio` branches in the chapter-pipeline `generate_media.py`. |
| IMP-CC-08 | High | L | Testing | Add a `tests/` suite (already configured in `pyproject.toml` via `testpaths = ["tests"]`, but zero tests exist today) covering the graph nodes, prompt formatting, and ingest helpers with mocked LLM/TTS/GCS clients. |

---

## Summary

- **Backend**: 9 improvements (3 High, 5 Medium, 1 Low)
- **Frontend**: 11 improvements (4 High, 4 Medium, 3 Low)
- **Content-CLI**: 8 improvements (3 High, 3 Medium, 2 Low)
