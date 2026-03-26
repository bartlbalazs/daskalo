# Greek Language Learning Application Architecture

## 1. Overview
The application consists of three main components:
1. **Frontend (User Application)**: An Angular SPA deployed to Firebase Hosting.
2. **Backend (Evaluation & Progress)**: Two Python Cloud Functions (2nd gen) deployed to Google Cloud Functions.
3. **Content Generator (Operator Tool)**: A local Python CLI utilizing LangGraph for AI-assisted content creation.

## 2. Component Details

### 2.1 Frontend (Angular)
- **Role**: User interface for learning, practicing, and tracking progress.
- **Hosting**: Firebase Hosting.
- **State/Data**: Interacts directly with Firestore for reading lessons, vocabulary, and writing exercise attempts.
- **Authentication**: Firebase Authentication (Google Sign-In).
- **Backend Communication**: Uses raw `fetch()` with the Firebase Callable wire protocol (`{"data": {...}}` request body). No `@angular/fire/functions` SDK. The two function URLs are configured via `environment.evaluateAttemptUrl` and `environment.completeChapterUrl`.
- **Key Features**:
  - Book-like chapter navigation.
  - Lesson display and interactive exercises (e.g., Slang Matcher, Image Description).
  - Basic local grading for simple exercises to ensure quick feedback.
  - Browser-based Speech-to-Text for pronunciation practice.

### 2.2 Backend (Cloud Functions 2nd gen)
- **Role**: Secure evaluation of complex exercises and chapter completion processing.
- **Deployment**: Google Cloud Functions (2nd gen), one function per entry point file.
- **Auth**: Deployed with `--allow-unauthenticated`; Firebase ID token verification is enforced in code via the `Authorization: Bearer` header.
- **Wire Protocol**: Firebase Callable convention — request body `{"data": {...}}`, success response `{"result": {...}}`, error response `{"error": {"status": "...", "message": "..."}}`.
- **Functions**:
  - `evaluate_attempt_fn` (`fn_evaluate.py`): Evaluates an AI-graded exercise attempt using Gemini and writes the result to Firestore.
  - `complete_chapter_fn` (`fn_complete_chapter.py`): Generates a progress summary via Gemini and updates the user document in Firestore (completedChapterIds, lastActive, lastProgressSummary). Grammar book entries are NOT generated here — see the content-cli pipeline.
- **Shared helpers** (`callable_helpers.py`): Token verification, request parsing, and response formatting used by both functions.
- **AI Integration**: Uses Gemini for exercise evaluation and progress summary generation.

### 2.3 Content Generator (Local CLI)
- **Role**: Offline tool for operators to generate multimodal course content.
- **Tech Stack**: Python, LangGraph, Vertex AI (Gemini for text generation), local Piper TTS.
- **Process**:
  1. Operator inputs chapter, topic, and optional student interests.
  2. LangGraph nodes generate text, vocabulary, grammar explanations, and a pre-built grammar summary (`grammarSummary`).
  3. The `generate_grammar_summary` node (Gemini Pro) runs after `generate_grammar_notes` and produces a thorough Markdown reference (grammar tables, key vocabulary, tips & common mistakes). This is stored on the chapter document and is identical for all students.
  4. A Reviewer Node ensures quality and appropriateness (max 2 retries).
  5. Media is generated (TTS audio, Vertex AI images).
  6. Content is written directly to the Firestore emulator (local) or production Firestore (`--no-local`).

## 3. Data Flow

### 3.1 Complex Exercise Evaluation
1. User completes an AI-graded exercise in the Angular app.
2. Angular app writes a document to the `exercise_attempts` collection in Firestore (status: `pending`).
3. Angular app calls the `evaluate-attempt` Cloud Function via `fetch()`, passing the `attemptId` in the Callable request body, along with the Firebase ID token in the `Authorization` header.
4. The Cloud Function verifies the token, confirms the attempt belongs to the caller, fetches the exercise prompt from the parent chapter document, and calls Gemini to evaluate the answer.
5. The Cloud Function writes the result (score, feedback, `isCorrect`) and status (`completed`) back to the `exercise_attempts` document.
6. The Cloud Function returns the evaluation result directly in the HTTP response.
7. The Angular app updates the UI with the returned result.

### 3.2 Chapter Completion
1. User finishes a chapter in the Angular app.
2. Angular app calls the `complete-chapter` Cloud Function via `fetch()`, passing the `chapterId` in the Callable request body.
3. The Cloud Function verifies the token, runs one Gemini call (progress summary), and updates the user's document in Firestore (`completedChapterIds`, `lastActive`, `lastProgressSummary`).
4. The Cloud Function returns `{ chapterId, progressSummary, completedChapterIds }` to the caller.
5. The Angular app updates the UI with the returned progress data.

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
- **Backend (local)**: `main.py` is a FastAPI dev server that bundles both Cloud Function handlers as standard POST endpoints (`/evaluate`, `/complete-chapter`). It uses a `_FlaskRequestShim` to adapt FastAPI `Request` objects to the Flask-compatible interface expected by `callable_helpers`. This file is **not deployed to production**.
- **No Watcher / No Eventarc simulation**: The direct HTTP Callable pattern means no background trigger simulation is needed locally.

### Starting the local environment
Run `dev.sh` from the project root. It starts three processes in order:
1. **Firebase Emulators** (Firestore, Auth, Hosting)
2. **FastAPI backend** (`uvicorn main:app --reload` on port 8000)
3. **Angular frontend** (`ng serve` on port 4200)

### Environment URLs
| Environment | `evaluateAttemptUrl` | `completeChapterUrl` |
|-------------|----------------------|----------------------|
| Local       | `http://localhost:8000/evaluate` | `http://localhost:8000/complete-chapter` |
| Production  | Cloud Function URL (set in `environment.prod.ts`) | Cloud Function URL (set in `environment.prod.ts`) |
