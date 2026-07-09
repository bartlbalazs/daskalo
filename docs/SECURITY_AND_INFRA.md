# Security & Infrastructure Guidelines

This document outlines the security rules and infrastructure requirements for the Greek Language Learning Application.

## 1. Firebase Configuration

### 1.1 Authentication
- **Provider**: Google Sign-In via Firebase Auth.
- **Enablement**: New users signing up via the Angular frontend will be created with `status: "pending"`.
- **Admin Action**: An administrator (via the Firebase Console or an admin script) must manually change the user's status to `active` before they can access content or write exercise attempts.

### 1.2 Firestore Security Rules
Strict security rules are required to ensure data integrity and prevent unauthorized access. The rules must enforce the "active" status check.

> The canonical, always-current rules are `frontend/firestore.rules` (deployed via `firebase deploy --only firestore:rules`). The snippet below is illustrative only, kept intentionally short — refer to the real file for the exact, complete rule set (it also covers `favoriteWords`, `ownWords`, and `practice_sets`, and constrains the exact shape a client may write on user-document creation).

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Helper function to check if the user is logged in
    function isAuthenticated() {
      return request.auth != null;
    }

    // Helper function to check if the current user is "active"
    // This is the core enablement check.
    function isActiveUser() {
      return isAuthenticated() && get(/databases/$(database)/documents/users/$(request.auth.uid)).data.status == "active";
    }

    // Users can read their own document. Creation is allowed only with
    // status: "pending" and every progress field at its zero/empty value —
    // all subsequent updates (activation, xp, completed chapters, ...) are
    // performed exclusively by the backend via the Admin SDK.
    match /users/{userId} {
      allow read: if request.auth.uid == userId;
      allow create: if request.auth.uid == userId && request.resource.data.status == "pending";
      allow update, delete: if false;
    }

    // Books and Chapters are strictly read-only for active users
    match /books/{bookId} {
      allow read: if isActiveUser();
      allow write: if false; // Only written by the content-cli ingestion pipeline
    }

    match /chapters/{chapterId} {
      allow read: if isActiveUser();
      allow write: if false; // Only written by the content-cli ingestion pipeline
    }

    // Exercise Attempts
    // Active users can read their own attempts
    // Active users can create new attempts, but cannot fake evaluations
    match /exercise_attempts/{attemptId} {
      allow read: if isActiveUser() && resource.data.userId == request.auth.uid;
      allow create: if isActiveUser() && request.resource.data.userId == request.auth.uid && request.resource.data.evaluation == null && request.resource.data.status == "pending";
      allow update, delete: if false; // Only the Backend can update (add evaluation)
    }
  }
}
```

## 2. Google Cloud Infrastructure

All infrastructure is managed by Terraform in the `infra/` directory. See `docs/ARCHITECTURE.md` for the deployment workflow.

### 2.1 Org Policy Constraint
This project operates under a GCP org policy that **denies unauthenticated Cloud Function invocations**. This is why the API Gateway is mandatory — it is the public entry point that validates Firebase JWTs and invokes Cloud Functions using a dedicated service account.

### 2.2 Security Layering (Defence-in-Depth)
Three security checkpoints protect every backend call:

| Layer | What it enforces |
|-------|-----------------|
| **API Gateway** | Firebase JWT signature + issuer + audience validation at the edge. Rejects unauthenticated requests before they reach Cloud Functions. |
| **Cloud Run IAM** | Cloud Functions are `--no-allow-unauthenticated`. Only `api-gateway-sa` (with `roles/run.invoker`) can invoke them. |
| **Function code** | Re-verifies the Firebase ID token, confirms `users/{uid}.status == "active"`, enforces a per-user/per-function rate limit (defense-in-depth under the gateway's per-project quota), checks Firestore document ownership (`userId == caller uid`), and validates status preconditions (e.g. atomically claims `exercise_attempts.status: "pending" → "evaluating"` inside a transaction). |

### 2.3 Service Accounts

#### `api-gateway-sa`
- **Purpose**: Used by API Gateway to invoke Cloud Functions.
- **Permissions**: `roles/run.invoker` (project-level — covers all four functions).

#### `cf-runtime-sa`
- **Purpose**: Attached to all four Cloud Functions at runtime.
- **Permissions**:
  - `roles/aiplatform.user` — call Gemini models via Vertex AI
  - `roles/datastore.user` — read/write Firestore
  - `roles/speech.client` — Cloud Speech-to-Text (pronunciation evaluation)
  - `roles/firebase.sdkAdminServiceAgent` — Firebase Admin SDK (token verification)
  - `roles/storage.objectViewer` — read Cloud Function source from GCS

### 2.4 API Gateway OpenAPI Spec
The gateway spec (`infra/openapi.yaml.tpl`) is rendered with actual Cloud Function URLs by Terraform at apply time. It configures:
- **Firebase JWT security**: `x-google-issuer`, `x-google-jwks_uri`, `x-google-audiences`
- **Backend routing**: `x-google-backend` with `address` pointing to each Cloud Function's Cloud Run URL
- **CORS preflight**: Separate `OPTIONS` path entries forwarded to the functions

### 2.5 GCS Buckets

| Bucket | Access | Purpose |
|--------|--------|---------|
| `{project_id}-cf-source` | Private | Cloud Function source zips |
| `{var.public_assets_bucket_name}` | Firebase Storage rules (`request.auth != null`) | Images and audio served to the Angular app via Firebase Storage SDK |
| `{project_id}-terraform-state` | Private (created by bootstrap.sh) | Terraform remote state |

### 2.6 Cloud Functions Source Zip
`deploy.sh --infra` builds the zip from `backend/` excluding:
- `.venv/` — local virtual environment
- `tests/` — test files not needed at runtime
- `__pycache__/` — compiled bytecode
- `.python-version` — pyenv config
- `main.py` — FastAPI local dev server (not deployed)
- `.env*` — local environment files

## 3. Cost Control & Billing Alerts
Given the use of Vertex AI and LLMs, proactive cost management is crucial.

1. **Set up a Billing Budget**: Go to Billing → Budgets & alerts in the GCP console.
2. **Alert Thresholds**: Configure alerts at 50%, 90%, and 100% of your expected monthly spend (e.g., a $10/month budget).
3. **Action on 100%**: Consider configuring automated actions (like disabling billing or shutting down services) if the budget is reached, though simple email alerts are often sufficient for early stages.

> Note: Billing budgets are intentionally not managed by Terraform to avoid accidental removal.
