# Legal Compliance Pages Specification

## Status

Draft planning specification. This is a product and engineering plan, not legal advice. Final production copy should be reviewed by a qualified professional if possible, especially because the operator is an individual person rather than a company.

## Problem

Daskalo is currently a small, invite-only learning app, expected to serve only a handful of users for now, with a practical maximum around 50 users. Even at this size, the app processes personal data and needs clear public legal information, explicit acceptance of Terms and Privacy before account creation, and a basic GDPR request process.

The goal is not to overbuild a corporate compliance system. The goal is to make the app transparent, legally respectable, and operationally manageable for an EU/Hungary-based individual operator.

## Goals

- Add public legal pages before sign-in.
- Add legal links inside the authenticated app.
- Add a small footer across public and authenticated surfaces.
- Require users to accept current Terms and Privacy versions before Google sign-in creates an account.
- Store accepted legal document versions on the user document.
- Require reacceptance when Terms or materially changed Privacy versions are updated.
- Explain data processing clearly, including Google/Firebase/GCP and AI/Speech/TTS processing.
- Support GDPR data rights through a manual contact-email workflow for MVP.
- Avoid non-essential analytics, ads, pixels, and tracking cookies until a separate consent/cookie plan exists.

## Non-Goals

- Full legal CMS/admin editor.
- Self-serve GDPR export/delete UI.
- Cookie consent banner for non-essential tracking.
- Analytics implementation.
- Company-style legal identity when there is no company.
- Automatically generating final legal text without human review.

## Existing Context

- The app currently has public `/login` and `/pending` pages.
- The app currently has no legal pages and no footer.
- The authenticated app shell is `LayoutComponent`.
- The login page signs in with Google; first sign-in creates `users/{uid}` with a strict minimal shape.
- Firestore rules currently require the user document created by the client to match that minimal shape.
- The app processes personal data including Google account identity, user progress, exercise submissions, evaluations, favorite/own words, user-specific audio/text payloads, rate-limit records, and progress summaries.
- Backend and content generation use Google Cloud/Firebase services, Gemini, Speech-to-Text, and Text-to-Speech.

## Legal Identity Assumptions

The MVP should assume:

- The data controller is an EU/Hungary-based individual, not a company.
- Production legal copy must include a placeholder for controller real name that is filled before launch.
- Production legal copy must include country context: Hungary / EU.
- Production legal copy must include a contact email for privacy/legal requests.
- Production legal copy may include a postal address if counsel or local requirements say it is needed.

Do not invent these values in code or docs. The implementation should fail review if production legal copy still contains obvious placeholders.

## Pages In Scope

Add three static public pages:

- `About`
- `Privacy Policy`
- `Terms of Use`

Suggested routes:

- `/about`
- `/privacy`
- `/terms`

These routes must be accessible without authentication and from inside the authenticated app.

No separate Cookie Policy is required for this MVP because the plan explicitly forbids non-essential analytics, ads, marketing pixels, or tracking cookies. If those are added later, a Cookie Policy and consent mechanism must be planned separately.

## Content Source

Legal/about content should be static, versioned repo content.

Accepted approaches:

- Static Angular page content.
- Static Markdown files rendered by Angular.
- Static TypeScript content/config objects.

Rejected for MVP:

- Firestore-editable legal content.
- External Google Docs/Notion legal links as the source of truth.
- Runtime LLM-generated legal content.

Rationale: for a small invite-only app, legal text should be reviewed through git and deploys.

## Footer Requirements

Add a small footer across public and authenticated surfaces.

Footer links:

- About
- Privacy Policy
- Terms of Use

Footer should also show:

- App name: Daskalo / Δάσκαλο.
- Copyright or simple operator notice.
- Contact email link if design allows without clutter.

Placement:

- Public login page.
- Public pending page.
- Public legal pages.
- Authenticated app layout.

The footer must stay visually lightweight and must not compete with the learning UI.

## Login Acceptance Flow

Before Google sign-in, the login page must require explicit acceptance of Terms and Privacy.

Requirements:

- Add a required checkbox near the Google sign-in button.
- The checkbox copy should link to `/terms` and `/privacy`.
- The Google sign-in button is disabled until the checkbox is checked.
- The acceptance must happen before account creation, because first Google sign-in creates a Firestore user document.
- The current Terms and Privacy version strings are captured when the user document is created.

Suggested checkbox copy:

`I agree to the Terms of Use and Privacy Policy.`

## Legal Versioning

Each legal document has a date-string version.

Example format:

```text
2026-07-10
```

Requirements:

- Show the effective date/version on the Privacy Policy page.
- Show the effective date/version on the Terms of Use page.
- Store accepted versions on the user document at signup/acceptance time.
- Keep version constants in one obvious frontend location so UI, acceptance storage, and reacceptance checks use the same values.

## Data Model Changes

Update `docs/DATA_MODEL.md` during implementation.

Add legal acceptance fields to `users/{uid}`:

```json
{
  "legal": {
    "termsAcceptedAt": "Timestamp",
    "termsVersion": "2026-07-10",
    "privacyAcceptedAt": "Timestamp",
    "privacyVersion": "2026-07-10"
  }
}
```

Field semantics:

- `termsAcceptedAt` records when the user accepted Terms of Use.
- `termsVersion` records the Terms version accepted.
- `privacyAcceptedAt` records when the user accepted the Privacy Policy.
- `privacyVersion` records the Privacy Policy version accepted.

Because client-side user creation currently enforces a strict shape, implementation must update:

- `AuthService._ensureUserDocument()`.
- `frontend/firestore.rules` user create validation.
- TypeScript user model.
- Any backend/user model if applicable.

## Reacceptance Flow

If Terms or Privacy versions change, existing active users whose stored accepted version is stale must reaccept before continuing to use the app.

Requirements:

- Detect stale `legal.termsVersion` or `legal.privacyVersion` after loading the active user.
- Show a lightweight authenticated blocking page or modal.
- Link to current Terms and Privacy pages.
- Require explicit acceptance of the new versions.
- Store updated acceptance timestamps and versions.
- Do not allow normal lesson/practice flow until reaccepted.

Implementation can use a backend callable or a narrowly reviewed Firestore rules update. Recommended implementation is a backend callable because user documents are otherwise backend-owned after creation.

Suggested endpoint name:

- `accept-legal-terms`

## About Page Content Requirements

The About page should be short and human.

It should include:

- What Daskalo is: a small Greek language learning app.
- Who operates it: an individual operator, with real identity/contact placeholders filled before production.
- Invite-only / small-user-base context if desired.
- A plain-language note that some content and feedback may be generated or assisted by AI.
- Links to Privacy Policy and Terms of Use.

It should avoid:

- Corporate-sounding claims.
- Overpromising learning outcomes.
- Hiding that the app is personally operated.

## Privacy Policy Content Requirements

Privacy Policy must be clear and specific enough for the current architecture.

Required sections:

- Include a section for controller identity and contact email.
- Include a collected-data section covering Google account identity: UID, email, display name, and profile image if provided by Google auth.
- Include a collected-data section covering account status and timestamps.
- Include a collected-data section covering learning progress, XP, completed lessons/practice sets, and progress summaries.
- Include a collected-data section covering exercise submissions and evaluation results.
- Include a collected-data section covering favorite words and own words.
- Include a collected-data section covering audio/text submitted for exercises where applicable.
- Include a collected-data section covering rate-limit/security records.
- Include a purpose section covering account access and invite-only activation.
- Include a purpose section covering lessons, practice, feedback, progress, vocabulary, and review.
- Include a purpose section covering security, abuse prevention, and rate limiting.
- Include a purpose section covering operating and improving the app at a basic functional level.
- Include a legal-basis section stating core processing is necessary to provide the requested learning service.
- Include a legal-basis section stating security/rate-limiting can be described as necessary for safe operation / legitimate interest if final legal copy confirms this.
- Include a legal-basis section stating there is no optional analytics/marketing processing in MVP.
- Include a processors/subprocessors section naming Firebase Authentication.
- Include a processors/subprocessors section naming Firestore.
- Include a processors/subprocessors section naming Firebase Hosting.
- Include a processors/subprocessors section naming Google Cloud Storage.
- Include a processors/subprocessors section naming Google Cloud Run / Cloud Functions.
- Include a processors/subprocessors section naming Google Gemini / Vertex AI where used for evaluation, generated feedback, summaries, and content generation.
- Include a processors/subprocessors section naming Google Speech-to-Text where audio evaluation/transcription is used.
- Include a processors/subprocessors section naming Google Text-to-Speech where app/user audio is generated.
- Include a data-location/transfers section explaining that the app uses Google Cloud/Firebase infrastructure.
- Include configured Google Cloud project region(s) if known.
- Include a retention section stating user data is retained while the account exists unless deletion is requested.
- Include a retention section stating exercise/progress records are kept to provide learning history.
- Include a retention section stating rate-limit records should be retained only as long as operationally needed, if a retention policy exists.
- Include a user-rights section covering access/export.
- Include a user-rights section covering correction.
- Include a user-rights section covering deletion/erasure.
- Include a user-rights section covering objection/restriction where applicable.
- Include a user-rights section covering complaint to the relevant data protection authority.
- Include a request-process section telling users to email the configured privacy contact.
- Include a request-process section stating requests are handled manually for MVP.
- Include an age-limit section stating the service is for users aged 16+.
- Include a no-analytics/tracking statement that the MVP does not use non-essential analytics, ads, marketing pixels, or tracking cookies.

## Terms Of Use Content Requirements

Terms should be plain and short.

Required sections:

- Who operates the app.
- Eligibility: 16+ users only.
- Invite-only / account activation requirement.
- Include user responsibilities: use the app for personal learning.
- Include user responsibilities: do not abuse, attack, scrape, or overload the service.
- Include user responsibilities: do not submit illegal, harmful, or sensitive third-party personal data.
- Include an AI/content disclaimer that lessons, feedback, translations, summaries, and evaluations may be AI-assisted.
- Include an AI/content disclaimer that AI output can be incomplete or wrong.
- Include an AI/content disclaimer that the app is for educational use, not professional advice.
- Include an availability disclaimer that this is a small personally operated service and availability is not guaranteed.
- Include an account suspension/removal section stating the operator can deny, suspend, or remove access for misuse or operational reasons.
- Privacy link.
- Contact email.

## GDPR Request Operations

MVP data rights handling is manual by contact email.

The implementation plan should include operator procedures for:

- Exporting a user's personal data.
- Correcting obvious account metadata if needed.
- Deleting a user's personal data.

Deletion scope:

- Delete Firebase Auth user.
- Delete `users/{uid}` document.
- Delete `users/{uid}` subcollections such as `favoriteWords` and `ownWords`.
- Delete `exercise_attempts` for that `userId`.
- Delete `rate_limits` records for that user.
- Delete user-specific Storage objects, such as `users/{uid}/own_words/...`.
- Keep shared generated course content, chapters, books, practice sets, and public lesson assets, because those are not personal data for a specific user.

For MVP, self-serve delete/export UI is explicitly out of scope.

## Analytics And Cookies

No non-essential analytics/tracking is allowed in this MVP legal-compliance pass.

Do not add:

- Google Analytics / Firebase Analytics.
- Marketing pixels.
- Ads.
- Session replay.
- Non-essential tracking cookies.

If analytics are introduced later, create a separate planning spec for:

- Cookie/consent banner.
- Cookie Policy.
- Analytics provider disclosure.
- Consent storage and withdrawal.

## Public Route Requirements

Routes must be public and bookmarkable:

- `/about`
- `/privacy`
- `/terms`

Route behavior:

- Anonymous users can open them.
- Pending users can open them.
- Active users can open them.
- Legal pages should not redirect authenticated users away.
- Wildcard route behavior must not swallow legal routes.

## Frontend Requirements

- Add public static pages for About, Privacy Policy, Terms of Use.
- Add a reusable footer or equivalent shared legal-link component.
- Add footer/legal links to login, pending, legal pages, and authenticated layout.
- Add required Terms/Privacy checkbox to login.
- Disable Google sign-in until checkbox is checked.
- Store legal acceptance versions during user document creation.
- Add stale-version detection and reacceptance UI for active users.
- Add user model fields for `legal`.
- Keep pages responsive and readable on mobile.
- Keep legal pages visually plain, scannable, and accessible.

## Backend Requirements

- If using backend writes for reacceptance, add a callable that verifies auth/active status and writes current legal acceptance timestamps/versions.
- Ensure backend user models tolerate the new `legal` object.
- Do not add AI calls for legal flow.

## Security And Rules Requirements

- Update user document creation rules to require the legal acceptance object when a new user signs up.
- Keep user update rules locked down unless a narrow, reviewed exception is deliberately chosen.
- Legal pages are public static content and must not expose private user data.

## Testing Requirements

Minimal tests should cover:

- Public routing for `/about`, `/privacy`, `/terms` while logged out.
- Login sign-in button disabled until Terms/Privacy checkbox is checked.
- User document creation includes legal acceptance versions/timestamps.
- Firestore rules accept valid user creation with legal fields and reject missing legal fields.
- Authenticated layout/footer includes legal links.
- Stale legal version triggers reacceptance flow.
- Current legal version does not block normal app flow.

## Acceptance Criteria

- Anonymous users can open About, Privacy Policy, and Terms of Use pages.
- Login page links to Terms and Privacy before sign-in.
- Login requires explicit checkbox acceptance before Google sign-in can start.
- New user documents store accepted Terms and Privacy versions and timestamps.
- If the current legal version changes, existing users must reaccept before using lessons/practice.
- The public and authenticated UI include legal footer links.
- Privacy Policy discloses collected data categories and Google/Firebase/GCP/AI processing.
- Terms include age limit, acceptable use, AI accuracy disclaimer, and availability disclaimer.
- Legal pages expose a contact email placeholder that must be filled before production.
- No non-essential analytics/tracking/cookie mechanism is introduced as part of this work.
- Manual GDPR export/delete request handling is documented for operators.

## Open Implementation Notes

- Final legal copy must replace placeholders before production.
- If the app's Google Cloud region is known, include it in the Privacy Policy.
- If counsel says a postal address is required for an individual controller, add it to About and Privacy Policy.
- The current login flow creates user docs client-side; implementation must carefully coordinate checkbox state, legal versions, and Firestore create rules.
- Consider adding an operator checklist for data export/deletion in a later implementation plan.
