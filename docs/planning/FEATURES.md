# Feature Ideas

Forward-looking feature candidates identified during the full-codebase review. These are **not** scheduled for `fix/bugs-and-improvements` — they're a backlog for future planning, except where noted.

## Legend

**Impact**: value to students/operators if built. **Effort**: rough sizing (S/M/L).

| # | Feature | Impact | Effort | Notes |
|---|---------|--------|--------|-------|
| 1 | **Conversational lesson authoring in opencode** | High | M | Replaces the external ChatGPT round-trip with an in-conversation workflow (brief → discussion → non-interactive `daskalo generate` call). Fully designed in `docs/planning/LESSON_AUTHORING_REDESIGN.md`. **To be implemented on its own branch after `fix/bugs-and-improvements` lands.** |
| 2 | **Auto-chained practice-set generation** | Medium | S | After a chapter is generated/reviewed, offer to immediately run `daskalo generate-practice` against the fresh ZIP instead of requiring a separate manual invocation. |
| 3 | **Spaced-repetition review queue** | High | L | Turn `favoriteWords`/`ownWords` into an SRS queue (e.g. SM-2) with a dedicated review page, using data the app already collects. |
| 4 | **Per-user interest profile** | Medium | M | Persist student interests (hobbies, domains) on the `users` document and feed them into `--interests` automatically during generation, instead of a one-off per-lesson string. |
| 5 | **Admin activation console** | Medium | M | A small internal page/script for flipping `users/{uid}.status` from `pending` to `active` and viewing signup queue — today this is presumably done by hand in the Firebase console. |
| 6 | **Progress dashboard from `exercise_attempts`** | Medium | M | The backend already stores per-exercise scores/feedback; nothing currently aggregates them into a student-facing "strengths/weaknesses" view. |
| 7 | **Grammar Book search / concept index** | Low | M | Add search-by-grammar-concept across all completed chapters' `grammarSummary` content (currently browse-only, grouped by book/chapter). |
| 8 | **Streaks & daily goals** | Medium | M | Lightweight gamification layer on top of existing `lastActive`/XP fields. |
| 9 | **Own-words in matching/flashcard exercises** | Low | M | Practice-set generation already pulls "previous chapters vocabulary" — extending it to include the student's own words would make practice sets more personal. |
| 10 | **Vocabulary export (Anki/CSV)** | Low | S | Export `vocabulary` + `ownWords` + `favoriteWords` to an Anki-importable format for offline SRS study. |
| 11 | **PWA / offline audio caching** | Medium | L | Cache resolved chapter audio/images for offline practice — pairs naturally with IMP-FE-02 (download-URL caching). |
| 12 | **Chapter variant management UI** | Low | M | The data model already supports multiple content variants per curriculum slot (`variantId`), but there's no UI to browse/select/retire variants — currently whichever variant was last generated wins. |
| 13 | **Error monitoring/alerting** | Medium | S | Wire up Cloud Error Reporting (or Sentry) for the Cloud Functions and the Angular app; today failures are only visible in Cloud Logging if someone goes looking. |
