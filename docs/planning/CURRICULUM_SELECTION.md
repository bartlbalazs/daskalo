# Curriculum Selection Feature Specification

## Status

Draft specification for a future implementation pass.

## Problem

The app currently shows every generated lesson variant in the left course map and on the Course page. This is wrong because multiple generated chapters can represent the same canonical curriculum slot. Students should see one selected lesson variant per curriculum slot in normal learning navigation, while still being able to choose a better-fitting alternative when alternatives exist.

## Goals

- Show only one selected chapter variant per `curriculumChapterId` in the left Course Map.
- Show only one selected chapter variant per `curriculumChapterId` on the existing `/chapters` Course page.
- Add a `Curriculum` screen where the user can review and change selected variants row-by-row.
- Default each curriculum row to the newest generated selectable variant.
- Preserve explicit user choices when newer variants are generated later.
- Let users discover alternative versions from inside a lesson detail page.
- Add operator CLI support for pending-user listing and activation-time curriculum initialization.
- Keep the MVP simple: no named curriculum presets, no full admin UI, and no new canonical curriculum-slot Firestore collection.

## Non-Goals

- Building a full admin console.
- Modeling named curriculum presets such as "travel Greek" or "grammar-heavy Greek."
- Migrating completion from chapter-variant IDs to curriculum-slot IDs.
- Showing canonical empty curriculum rows that have no generated/selectable chapter variant.
- Reworking Grammar Book or Vocabulary behavior beyond preserving current completion-based logic.

## Existing Context

- `chapters` already has `curriculumChapterId`, which groups variants for the same canonical lesson slot.
- `chapters` are currently loaded by `bookId` and ordered by `order`; this exposes all variants in sidebar and Course page.
- User progress is keyed by concrete `chapterId` through `progress.completedChapterIds`.
- User documents are created as `pending` with a strict minimal shape; client updates to `users/{uid}` are currently forbidden by Firestore rules.
- Activation appears to be manual today; this feature requires `content-cli` activation commands.

## User Experience

### Course Map And Course Page

The normal learning navigation must show only selected variants:

- The left Course Map renders books and selected chapters only.
- The `/chapters` Course page renders selected chapters only.
- Practice links shown under a chapter come from the selected chapter variant.
- If the stored selection is stale or points to a missing chapter, the UI falls back to the newest selectable variant for that `curriculumChapterId` so the course remains usable.

### Curriculum Screen

Add a protected `Curriculum` screen, expected route: `/curriculum`.

The screen is a top-down curriculum overview:

- Rows represent available curriculum slots grouped by `curriculumChapterId`.
- Rows are derived from selectable Firestore `chapters`; rows with no available chapter variant are not shown.
- Rows are grouped by book and sorted by book order, then chapter `order`, then `curriculumChapterId` as a stable tie-breaker.
- Rows with only one variant are still shown.
- Each row contains a horizontally scrollable strip of alternative cards.
- The current selected card appears first, followed by other selectable alternatives sorted by `generatedAt` descending.

Row header content:

- Book number/title context.
- Lesson order.
- `curriculumChapterId`.
- Selected variant topic as the row title.

Alternative card content:

- Cover image from `coverImageUrl`.
- Topic.
- Title.
- Short description from existing `summary`.
- Generation date from new `generatedAt`.
- Lesson `length`, if present.
- `languageSkill`, if present.
- Exercise count from `exercises.length`.
- Practice availability from `practiceSetIds.length`.
- Selected state.
- Completed state for that specific variant, based on `completedChapterIds`.
- "No longer offered" state if the current selected variant has been hidden from new choices.

Selecting a card:

- An explicit Select action immediately updates the user's selected variant for that row.
- After selection, the sidebar and Course page reflect the new variant.
- The app may navigate/open the selected lesson after selection.
- Directly opening `/chapters/:id` for an unselected variant does not auto-select it.

Navigation access:

- The screen name is `Curriculum`.
- It should be reachable from the authenticated app navigation. The exact placement can be finalized during implementation, but it must be discoverable from normal app chrome.

### Lesson Detail Alternatives

The lesson detail page should include an `Alternative versions` section for the current chapter's `curriculumChapterId`.

- It shows the same variant-card concept as the Curriculum screen.
- It allows explicit selection of another variant.
- It should not put alternatives into the left sidebar.
- Direct page viewing remains view-only until the user explicitly selects a variant.

## Data Model Changes

Update `docs/DATA_MODEL.md` during implementation.

### Chapter Fields

Add to `chapters`:

```json
{
  "generatedAt": "Timestamp",
  "isSelectableAlternative": false
}
```

Field semantics:

- `generatedAt` is the content generation/package time, not Firestore ingest time.
- The newest selectable variant by `generatedAt` is the automatic default for each `curriculumChapterId`.
- `isSelectableAlternative` is an opt-out flag.
- Missing `isSelectableAlternative` means selectable.
- Setting `isSelectableAlternative: false` hides the variant from new choices and defaulting.
- Hidden variants remain readable as normal chapter documents.
- If a user already has a hidden variant selected, it remains visible to that user as current selection and is marked "no longer offered."

### User Fields

Add a top-level `curriculum` object to `users/{uid}` after activation:

```json
{
  "curriculum": {
    "selectedChapterIdsByCurriculumChapterId": {
      "b1_c1": "b1_c1_airport_variant"
    },
    "manualSelectionsByCurriculumChapterId": {
      "b1_c1": "Timestamp"
    },
    "initializedAt": "Timestamp",
    "updatedAt": "Timestamp"
  }
}
```

Field semantics:

- `selectedChapterIdsByCurriculumChapterId` maps each canonical curriculum slot to the selected concrete chapter variant ID.
- `manualSelectionsByCurriculumChapterId` records rows explicitly changed by the user.
- Absence from `manualSelectionsByCurriculumChapterId` means the row is automatic and can be refreshed to a newer generated default during activation/backfill.
- `initializedAt` records first curriculum initialization.
- `updatedAt` records the latest curriculum map change.

Completion remains unchanged:

- `progress.completedChapterIds` remains concrete chapter variant IDs.
- Switching to an uncompleted variant makes that row appear incomplete for that variant.
- Grammar Book and Vocabulary remain based on completed chapter IDs, including completed variants that are no longer selected.

## Defaulting And Refresh Rules

At curriculum initialization or idempotent activation/backfill:

- Group available chapters by `curriculumChapterId`.
- Ignore chapters with `isSelectableAlternative: false` unless already selected by that user.
- For missing automatic rows, select the newest selectable variant by `generatedAt`.
- For existing automatic rows, update to a newer selectable variant if one exists.
- For manual rows, preserve the user's selected variant.
- If a selected manual variant was deleted or cannot be read, display-time fallback is newest selectable variant and the CLI/backend should report that repair is needed.

## Write Paths

### Frontend Selection Changes

Selection changes should go through a backend callable rather than direct Firestore client updates.

The callable should:

- Verify Firebase auth and active-user status.
- Validate the requested `chapterId` exists.
- Validate the requested chapter belongs to the supplied/current `curriculumChapterId`.
- Reject selection of `isSelectableAlternative: false` unless it is already selected for that user.
- Update `users/{uid}.curriculum.selectedChapterIdsByCurriculumChapterId[curriculumChapterId]`.
- Set `manualSelectionsByCurriculumChapterId[curriculumChapterId]` to the current timestamp.
- Update `curriculum.updatedAt`.

Expected endpoint name can be finalized during implementation; suggested name: `set-curriculum-selection`.

### Activation-Time Initialization

Curriculum selection is generated at admin activation time, not raw account creation and not app startup.

Activation must be implemented in `content-cli`.

Required commands:

```bash
uv run daskalo users list
uv run daskalo users list --status pending
uv run daskalo users list --status active
uv run daskalo users list --status all
uv run daskalo users activate <uid>
uv run daskalo users activate <uid> --remote
```

Environment behavior:

- Default target is the local Firebase emulator / local Firestore configuration.
- `--remote` explicitly targets production Firestore, matching existing content-cli remote upload behavior.

`users list` behavior:

- Defaults to pending users.
- Displays UID, email, display name, status, createdAt, lastActive, and curriculum-initialized status.

`users activate <uid>` behavior:

- Direct UID only; no interactive picker required.
- Idempotent.
- If the user is pending, set `status: active` and initialize curriculum in the same operation.
- If the user is already active, ensure/backfill/refresh automatic curriculum selections and report that no status change was needed.
- Must not overwrite manual selections.

## Frontend Requirements

- Add user curriculum fields to TypeScript models.
- Add chapter `generatedAt` and `isSelectableAlternative` fields to TypeScript models.
- Add service methods for grouped alternatives and selected-course views.
- Update sidebar chapter loading to use selected variants only.
- Update `/chapters` Course page to use selected variants only.
- Add `/curriculum` page using standalone Angular components and local Signals where appropriate.
- Add lesson-detail alternatives section.
- Display GCS cover images through the existing GCS URL handling approach.
- Keep mobile usable: horizontal card strips must scroll cleanly on narrow screens.

## Backend Requirements

- Add a callable endpoint for user selection changes.
- Reuse existing auth, active-user, rate-limit, and callable response helpers.
- Validate Firestore data before writing user curriculum fields.
- Add deployment/API Gateway/environment configuration for the new callable.

## Content CLI Requirements

- Emit `generatedAt` during chapter packaging.
- Preserve existing generation CLI UX; adding `generatedAt` must not require a new operator prompt.
- Add user-management commands under the existing `daskalo` CLI.
- Reuse existing local/remote Firestore setup patterns.
- Activation should initialize/update curriculum based on current Firestore `chapters`.

## Security And Rules

- Keep `users/{uid}` client updates forbidden unless implementation chooses an explicitly reviewed alternative.
- Prefer backend/admin SDK writes for curriculum changes.
- `chapters` remain read-only to clients.
- Hidden alternatives are hidden by UI/query logic, not by security rules; active users can still read chapter documents if they know IDs.

## Acceptance Criteria

- Given multiple chapter documents with the same `curriculumChapterId`, the sidebar shows only the selected one.
- Given multiple chapter documents with the same `curriculumChapterId`, `/chapters` shows only the selected one.
- Given a newly activated user, `content-cli` activation writes a curriculum map selecting the newest selectable variant per available row.
- Given a user manually selects an older variant, later activation/backfill does not replace that row with a newer variant.
- Given a row with only one variant, the Curriculum page still shows that row with one selected card.
- Given a hidden variant that is not selected, it does not appear as an alternative and is not chosen as default.
- Given a hidden variant that is already selected by a user, that user can still see it as selected with a "no longer offered" indication.
- Given a direct URL to an unselected variant, opening the page does not mutate curriculum selection.
- Given a completed old variant and a selected new variant, Grammar Book and Vocabulary still include the completed old variant where current behavior already would.
- Given `uv run daskalo users list`, pending users are listed by default with activation-relevant metadata.
- Given `uv run daskalo users activate <uid> --remote`, production activation is explicit and initializes/refreshes curriculum idempotently.

## Open Implementation Notes

- Exact backend callable name and environment variable names can be finalized during implementation planning.
- Exact navigation placement for `Curriculum` should be finalized during UI implementation, but it must be available from authenticated app chrome.
- Existing users will need an activation/backfill command run once to populate missing `curriculum` data.
