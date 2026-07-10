# How It Works Page Specification

## Status

Draft specification for a future implementation pass.

## Problem

New active users need a short first-visit orientation for how the app works. The page must not become a manual. If the app needs long instructions, that is a product/design failure. This page should give just enough context to help a user start learning confidently.

## Goals

- Add an authenticated-only `How It Works` page.
- Show it automatically on the user's first active app visit only.
- Keep it short, simple, and visually scannable.
- Make it available later as the last menu item.
- Explain the app flow after the Curriculum feature exists.
- Persist whether the user has already seen the page across devices.

## Non-Goals

- Public marketing landing page before login.
- Long manual or help center.
- Multi-step onboarding wizard.
- Carousel/tutorial overlay.
- First-lesson recommendation engine.

## Existing Context

- The current authenticated default route redirects `/` to `/chapters`.
- Authenticated pages render inside `LayoutComponent`.
- Current static navigation includes Course, Grammar Book, and Vocabulary in the desktop top nav.
- The sidebar footer currently includes Grammar Book and Vocabulary.
- Firestore rules currently forbid client updates to `users/{uid}` after creation.

## User Experience

### Route And Access

- Add route `/how-it-works`.
- The page is protected by the active-user guard.
- Pending users do not see this page as part of their pending flow.
- Anonymous users do not see this page as a public landing page.

### First-Visit Behavior

The page is automatically shown once per active user:

- After active user data loads, if `users/{uid}.onboarding.howItWorksSeenAt` is missing, navigate to `/how-it-works`.
- When `/how-it-works` loads through the first-visit flow, mark it as seen immediately on page load.
- After the timestamp exists, normal app entry should continue to the existing Course flow.
- The page remains manually accessible from the app menu after it has been marked seen.

The automatic first-visit behavior should not become a blocking route guard for every deep link unless implementation planning finds that necessary. The intended behavior is a simple first active app entry redirect.

### Navigation Placement

Add `How It Works` as the last static menu item in both current navigation surfaces:

- Desktop top navigation: after Course, Grammar Book, Vocabulary, and Curriculum once Curriculum exists.
- Sidebar footer: after existing static footer links and after Curriculum once Curriculum exists.

The label is exactly `How It Works`.

### Primary CTA

The page has one primary action:

- Label: `Start learning` or equivalent concise copy.
- Destination: `/chapters`.

Secondary CTAs are optional but should stay minimal. If included after the Curriculum feature exists, a secondary `Choose your curriculum` link may point to `/curriculum`.

## Page Content

The page uses a simple hero plus four compact cards. No long paragraphs.

Hero:

- Title: short welcome/orientation copy.
- Body: one or two sentences maximum.
- Primary CTA to Course.

Four cards:

- `Follow the Course Map`: lessons are arranged in order; use the left map or Course page to continue.
- `Learn inside a lesson`: each lesson includes a short story/passage, vocabulary, grammar notes, audio, and exercises.
- `Practice and review`: practice sets reinforce lessons; Grammar Book and Vocabulary help review what has already been learned.
- `Choose your curriculum`: the Curriculum page lets users choose among alternative versions of lessons when multiple variants are available.

Tone requirements:

- Friendly and direct.
- Short enough to skim in under one minute.
- Avoid explaining implementation details, data model, Firestore, variants, or generated content mechanics.
- Avoid implying the user must read this page to use the app.

Visual requirements:

- Use existing Angular standalone component patterns.
- Use existing Tailwind/design language from the app.
- Use lightweight inline icons or simple visual marks; no new external image assets are required.
- Work cleanly on desktop and mobile.

## Data Model Changes

Update `docs/DATA_MODEL.md` during implementation.

Add an optional top-level onboarding object to `users/{uid}`:

```json
{
  "onboarding": {
    "howItWorksSeenAt": "Timestamp"
  }
}
```

Field semantics:

- Missing `onboarding` or missing `howItWorksSeenAt` means the user has not yet seen the page automatically.
- `howItWorksSeenAt` is set the first time the page loads as the first-visit landing page.
- The timestamp persists across browsers and devices.

## Backend Requirements

Because client updates to `users/{uid}` are currently forbidden, marking the page as seen should use a backend callable.

Suggested endpoint name: `mark-onboarding-seen`.

The callable should:

- Verify Firebase auth.
- Verify the user is active.
- Accept a small enum/string key, initially only `howItWorks`.
- Write `users/{uid}.onboarding.howItWorksSeenAt` if missing.
- Be idempotent: calling it again should not create duplicate state or fail.
- Reuse existing callable helper conventions, active-user checks, and response format.

No Gemini, TTS, or other AI calls are needed.

## Frontend Requirements

- Add an Angular standalone page component for `/how-it-works`.
- Add route under the authenticated shell.
- Add first-active-entry routing logic based on `currentUser().onboarding?.howItWorksSeenAt`.
- Call the backend mark-seen endpoint on page load.
- Add `How It Works` as the last static menu item in desktop top nav and sidebar footer.
- Add TypeScript user model support for `onboarding.howItWorksSeenAt`.
- Ensure manual visits to `/how-it-works` do not repeatedly redirect away or produce errors if already marked seen.

## Dependency On Curriculum Feature

This page should explain the Curriculum flow as a required part of the app. Therefore, the final implementation should either:

- Ship after the Curriculum feature exists, or
- Ship in the same release as the Curriculum feature.

The `Choose your curriculum` card should link to `/curriculum` once implemented.

## Testing Requirements

Minimal tests are required:

- Active user without `onboarding.howItWorksSeenAt` is routed to `/how-it-works` on first active app entry.
- Active user with `onboarding.howItWorksSeenAt` follows the normal Course flow.
- How It Works page calls the mark-seen service/callable on page load.
- Page renders the hero and four compact cards.
- Navigation includes `How It Works` as the last static menu item in both desktop top nav and sidebar footer.

No exhaustive visual regression suite is required for this MVP spec.

## Acceptance Criteria

- Given an active user who has never seen the page, first active app entry sends them to `/how-it-works`.
- Given the page loads for first-visit orientation, `onboarding.howItWorksSeenAt` is written for that user.
- Given an active user who already has `onboarding.howItWorksSeenAt`, app entry continues to the normal Course flow.
- Given any active user, the page is accessible from the `How It Works` menu item.
- Given the desktop top nav, `How It Works` is the last static menu item.
- Given the sidebar footer, `How It Works` is the last static menu item.
- Given the user clicks the primary CTA, they navigate to `/chapters`.
- Given the page renders on mobile, the hero and four cards remain readable without horizontal page overflow.
- Given the mark-seen callable is called multiple times, it remains safe and idempotent.

## Open Implementation Notes

- Exact first-entry hook location should be decided during implementation after reviewing `AuthService`, `activeUserGuard`, and route initialization flow.
- Exact endpoint naming and environment variable naming should follow the backend/API Gateway conventions in place at implementation time.
- If the Curriculum feature changes route naming, update the fourth card link accordingly.
