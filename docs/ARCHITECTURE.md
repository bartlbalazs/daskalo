# Greek Language Learning Application Architecture

## 1. Overview
The application consists of three main components:
1. **Frontend (User Application)**: An Angular SPA deployed to Firebase Hosting.
2. **Backend (Evaluation & Progress)**: Python Cloud Functions (2nd gen) deployed to Google Cloud Functions, fronted by an API Gateway.
3. **Content Generator (Operator Tool)**: A local Python CLI utilizing LangGraph for AI-assisted content creation.

## 2. Component Details

### 2.1 Frontend (Angular)
- **Role**: User interface for learning, practicing, and tracking progress.
- **Hosting**: Firebase Hosting.
- **State/Data**: Interacts directly with Firestore for reading lessons, vocabulary, and writing exercise attempts.
- **Authentication**: Firebase Authentication (Google Sign-In).
- **Backend Communication**: Uses raw `fetch()` with the Firebase Callable wire protocol (`{"data": {...}}` request body). No `@angular/fire/functions` SDK. Function URLs are routed through the API Gateway and configured in `frontend/src/environments/*`.
- **Key Features**:
  - Book-like chapter navigation.
  - Lesson display and interactive exercises (e.g., Slang Matcher, Image Description).
  - Basic local grading for simple exercises to ensure quick feedback.
  - Browser-based Speech-to-Text for pronunciation practice.

### 2.2 Backend (Cloud Functions 2nd gen + API Gateway)
- **Role**: Secure evaluation of complex exercises, chapter/practice-set completion processing, and student-authored vocabulary ("own words").
- **Deployment**: Google Cloud Functions (2nd gen), one function per entry point file.
- **Auth model (layered)**:
  1. **API Gateway** validates the Firebase JWT at the edge (`issuer: https://securetoken.google.com/{project_id}`, `audience: {project_id}`). Requests without a valid token are rejected with `401` before reaching the function. It also enforces a coarse per-project rate limit per endpoint (shared across all users).
  2. **Cloud Functions** are deployed `--no-allow-unauthenticated`. Only the `api-gateway-sa` service account (with `roles/run.invoker`) can invoke them.
  3. **Function code** re-verifies the Firebase ID token, confirms `users/{uid}.status == "active"` (`callable_helpers.ensure_active_user`), enforces a per-user/per-function rate limit as defense-in-depth under the gateway's per-project quota (`callable_helpers.check_rate_limit`, backed by the `rate_limits` collection — see `docs/DATA_MODEL.md`), and checks Firestore document ownership + status preconditions (e.g. `exercise_attempts.status == "pending"`) — all before any billable Gemini/TTS/STT call.
- **Wire Protocol**: Firebase Callable convention — request body `{"data": {...}}`, success response `{"result": {...}}`, error response `{"error": {"status": "...", "message": "..."}}`.
- **Functions**:
  - `evaluate_attempt_fn` (`fn_evaluate.py`): Evaluates an AI-graded exercise attempt using Gemini and writes the result to Firestore. The `pending → evaluating → completed/error` transition is claimed inside a Firestore transaction (preventing double-evaluation races) and a stale `evaluating` claim can be reclaimed after a timeout instead of being stuck forever.
  - `complete_chapter_fn` (`fn_complete_chapter.py`): Generates a progress summary via Gemini and updates the user document in Firestore (`completedChapterIds` via `ArrayUnion`, `xp` via `Increment`, `lastActive`, `lastProgressSummary`), inside a transaction. Grammar book entries are NOT generated here — see the content-cli pipeline.
  - `complete_practice_fn` (`fn_complete_practice.py`): Idempotently awards a flat XP amount for completing a practice set (`completedPracticeSetIds` via `ArrayUnion`, `xp` via `Increment`), inside a transaction.
  - `add_own_word_fn` (`fn_own_word.py`): Normalizes a student-submitted Greek word/phrase via Gemini, synthesizes pronunciation audio (Cloud TTS), uploads it to the public assets bucket, and writes it to `users/{uid}/ownWords` via a deterministic document ID (idempotent overwrite).
  - `set_curriculum_selection_fn` (`fn_set_curriculum_selection.py`): Validates and writes a user's selected concrete chapter variant for one `curriculumChapterId`.
- **Shared helpers** (`callable_helpers.py`): Token verification, request parsing, response formatting, the active-user gate, and the per-user rate limiter — used by all callable functions.
- **AI Integration**: Uses Gemini for exercise evaluation, pronunciation grading, progress summary generation, and own-word normalization; Cloud Speech-to-Text for pronunciation transcription; Cloud Text-to-Speech for own-word audio.
- **Service accounts**:
  - `api-gateway-sa` — held by API Gateway; has `roles/run.invoker` on Cloud Functions.
  - `cf-runtime-sa` — attached to Cloud Functions; has `roles/aiplatform.user`, `roles/datastore.user`, `roles/speech.client`, `roles/firebase.sdkAdminServiceAgent`.

### 2.3 Content Generator (Local CLI)
- **Role**: Offline tool for operators to generate multimodal course content.
- **Tech Stack**: Python, LangGraph, Vertex AI (Gemini for text generation and image generation), Google Cloud Text-to-Speech.
- **Process**:
  1. Operator inputs chapter, topic, and optional student interests.
  2. LangGraph nodes generate text, vocabulary, grammar explanations, and a pre-built grammar summary (`grammarSummary`).
  3. The `generate_grammar_summary` node (Gemini Pro) runs after `generate_grammar_notes` and produces a thorough Markdown reference (grammar tables, key vocabulary, tips & common mistakes). This is stored on the chapter document and is identical for all students.
  4. A Reviewer Node ensures quality and appropriateness (max 2 retries).
  5. Media is generated (TTS audio, Gemini-generated images).
  6. The pipeline is checkpointed (SQLite, keyed by a hash of the operator's inputs) so a late-stage failure can be resumed from the last completed node by re-running the same command, instead of discarding all prior work. See `docs/CONTENT_PIPELINE.md`.
  7. Content is written directly to the Firestore emulator (local) or production Firestore (`--no-local`).

## 3. Data Flow

### 3.1 Complex Exercise Evaluation
1. User completes an AI-graded exercise in the Angular app.
2. Angular app writes a document to the `exercise_attempts` collection in Firestore (status: `pending`).
3. Angular app calls `{api_gateway_url}/evaluate` via `fetch()`, passing the `attemptId` in the Callable request body and the Firebase ID token in the `Authorization: Bearer` header.
4. **API Gateway** validates the JWT. If invalid, returns `401` immediately.
5. API Gateway forwards the request to the `evaluate-attempt` Cloud Function using the `api-gateway-sa` service account identity.
6. The Cloud Function re-verifies the token, confirms the attempt belongs to the caller, fetches the exercise prompt from the parent chapter document, and calls Gemini to evaluate the answer.
7. The Cloud Function writes the result (score, feedback, `isCorrect`) and status (`completed`) back to the `exercise_attempts` document.
8. The Cloud Function returns the evaluation result directly in the HTTP response.
9. The Angular app updates the UI with the returned result.

### 3.2 Chapter Completion
1. User finishes a chapter in the Angular app.
2. Angular app calls `{api_gateway_url}/complete-chapter` via `fetch()`, passing the `chapterId` in the Callable request body.
3. **API Gateway** validates the JWT.
4. The Cloud Function verifies the token, runs one Gemini call (progress summary), and updates the user's document in Firestore (`completedChapterIds`, `lastActive`, `lastProgressSummary`).
5. The Cloud Function returns `{ chapterId, progressSummary, completedChapterIds }` to the caller.
6. The Angular app updates the UI with the returned progress data.

### 3.3 Grammar Book Assembly
The grammar book is assembled at runtime on the frontend — no backend call needed:
1. The grammar book page reads `completedChapterIds` from the authenticated user's Firestore document.
2. It fetches the chapter documents for those IDs (batched Firestore `in` query).
3. For each completed chapter, it renders the pre-generated `grammarSummary` Markdown field.
4. Chapters are grouped by book and sorted in curriculum order (book order → chapter order within each book).
5. Each summary entry links back to the corresponding lesson page.

## 4. Local Development Strategy

Local development uses Firebase Emulator Suite for Firestore/Auth and a FastAPI dev server for the backend.

- **Firebase Emulator Suite**: Runs Firestore and Auth locally. The Angular app connects to these instead of production.
- **Backend (local)**: `main.py` is a FastAPI dev server that bundles Cloud Function handlers as standard POST endpoints (`/evaluate`, `/complete-chapter`, `/complete-practice`, `/add-own-word`, `/set-curriculum-selection`). It uses a `_FlaskRequestShim` to adapt FastAPI `Request` objects to the Flask-compatible interface expected by `callable_helpers`. This file is **not deployed to production**.
- **Direct HTTP Callables**: The direct HTTP Callable pattern means no background trigger simulation is needed locally.

### Starting the local environment
Run `dev.sh` from the project root. It starts three processes in order:
1. **Firebase Emulators** (Firestore, Auth, Hosting)
2. **FastAPI backend** (`uvicorn main:app --reload` on port 8000)
3. **Angular frontend** (`ng serve` on port 4200)

### Environment URLs
| Environment | `evaluateAttemptUrl` | `completeChapterUrl` |
|-------------|----------------------|----------------------|
| Local       | `http://localhost:8000/evaluate` | `http://localhost:8000/complete-chapter` |
| Production  | `{api_gateway_url}/evaluate` | `{api_gateway_url}/complete-chapter` |

## 5. Deployment

All cloud infrastructure is managed by **Terraform** in the `infra/` directory.

### First-time setup
```bash
# 1. Create Terraform state bucket and run terraform init
export PROJECT_ID=your-gcp-project-id
./bootstrap.sh

# 2. Fill in your config
cp infra/terraform.tfvars.example infra/terraform.tfvars
# Edit infra/terraform.tfvars

# 3. Full deploy (infra + hosting)
./deploy.sh
```

### Subsequent deploys
```bash
./deploy.sh --infra      # infrastructure changes only
./deploy.sh --hosting    # frontend/rules update only
./deploy.sh              # both
```

### What deploy.sh does
- **`--infra`**: Zips the `backend/` source (excluding `.venv/`, `tests/`, `main.py`, etc.) → uploads to GCS → `terraform apply`. Cloud Functions are updated if the zip hash changes.
- **`--hosting`**: Reads Terraform outputs (API Gateway URL, Firebase SDK config) → generates `frontend/src/environments/environment.prod.ts` → `ng build --configuration production` → `firebase deploy --only hosting,firestore:rules,storage`.

### Terraform resources managed
| File | Resources |
|------|-----------|
| `infra/apis.tf` | All `google_project_service` API enablements |
| `infra/storage.tf` | Public assets GCS bucket (CORS, `allUsers:objectViewer`) |
| `infra/firestore.tf` | Firestore database (NATIVE mode) |
| `infra/iam.tf` | `api-gateway-sa`, `cf-runtime-sa`, IAM bindings |
| `infra/functions.tf` | CF source GCS bucket, source zip object, Cloud Function resources |
| `infra/api_gateway.tf` | `google_api_gateway_api/config/gateway` (OpenAPI 2.0 spec, Firebase JWT, CORS) |
| `infra/firebase_hosting.tf` | `google_firebase_web_app`, `google_firebase_hosting_site` |
| `infra/outputs.tf` | `api_gateway_url`, function URLs, Firebase web app config |
