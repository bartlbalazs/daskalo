# AI Agent Instructions for Greek Language App

This file contains instructions for any AI agent (like Cursor, Copilot, or Opencode) operating in this repository. 
When asked to build or modify features, you MUST adhere to these rules.

## 1. Project Overview & Architecture
This is a Greek Language Learning application consisting of three parts:
- **`frontend/`**: Angular SPA (Firebase Hosting, Firestore).
- **`backend/`**: Python FastAPI (Cloud Run, Eventarc triggers).
- **`content-cli/`**: Python LangGraph local tool (Vertex AI, Piper TTS).
- **Docs**: Always consult `/docs/ARCHITECTURE.md` and `/docs/DATA_MODEL.md` before making structural or database changes.

## 2. Global Rules
- **No Assumptions**: Never assume standard configurations. Always read `package.json`, `pyproject.toml`, or `requirements.txt`.
- **Paths**: When using file tools, always use absolute paths starting from the workspace root (e.g., `/home/bartlbalazs/git/daskalo/...`).
- **Data Model**: Never invent Firestore collections or document structures. Use exact fields from `docs/DATA_MODEL.md`.
- **KISS**: Keep It Simple, Stupid. We are building an MVP. Do not add complex state management (like NgRx) unless explicitly requested.

## 3. Frontend (Angular) Rules
### Tech Stack
- Angular (latest stable), TypeScript, Firebase Web SDK (v10+ modular).
- TailwindCSS for styling (no custom CSS unless absolutely necessary).

### Style & Patterns
- **Components**: Use Standalone Components.
- **State**: Use Angular Signals (`signal`, `computed`, `effect`) for local state management, NOT RxJS `BehaviorSubject` unless interfacing with external streams.
- **Firebase Services**: Isolate Firebase calls (Auth, Firestore) into dedicated `@Injectable({ providedIn: 'root' })` services (e.g., `LessonService`, `AuthService`).
- **Data Binding**: Avoid complex logic in templates. Compute values in the TypeScript class.

### Commands
- *Run Dev Server*: `cd frontend && npm start`
- *Run Linter*: `cd frontend && npm run lint`
- *Run Single Test*: `cd frontend && npx ng test --include src/app/path/to/component.spec.ts` (Note: adjust based on actual setup, verify `angular.json` first).

## 4. Backend (FastAPI) Rules
### Tech Stack
- Python 3.11+, FastAPI, Google Cloud Vertex AI SDK, Firebase Admin SDK.

### Style & Patterns
- **Typing**: Use strict Python type hinting (`typing` module, Pydantic models).
- **Error Handling**: Use FastAPI's `HTTPException` for routing errors. Catch specific exceptions, not broad `except Exception:` unless logging and re-raising.
- **File Structure**: 
  - `main.py` (entrypoint, Eventarc endpoints)
  - `models/` (Pydantic schemas mirroring Firestore)
  - `services/` (Business logic, Gemini evaluation, ZIP processing)
- **Firebase Admin**: Initialize the Admin SDK once globally in `main.py`.

### Commands
- *Run Dev Server*: `cd backend && uvicorn main:app --reload`
- *Run Linter/Formatter*: `cd backend && ruff check .` and `black .`
- *Run Single Test*: `cd backend && pytest tests/test_file.py::test_function_name`

## 5. Content CLI (LangGraph) Rules
### Tech Stack
- Python 3.11+, LangChain, LangGraph, Google Cloud Text-to-Speech SDK, Vertex AI SDK.

### Style & Patterns
- **State**: Strictly define `TypedDict` for the graph state.
- **Nodes**: Keep node functions pure and focused. Do not mix LLM calls with file system operations in the same node if possible.
- **Prompts**: Store complex prompts in separate `.py` files or templates, not inline within the graph definition.

### Commands
- *Install dependencies*: `cd content-cli && uv sync`
- *Run CLI (local emulator, interactive)*: `cd content-cli && uv run daskalo generate`
- *Run CLI (local emulator, direct ingest)*: `cd content-cli && uv run daskalo generate --direct`
- *Run CLI (production)*: `cd content-cli && uv run daskalo generate --no-local`
- *Run Linter*: `cd content-cli && uv run ruff check .`

## 6. Local Emulation Environment
- The project relies on the Firebase Local Emulator Suite.
- To test the full flow locally, the "Watcher" script must be running to simulate Eventarc triggers from the Firestore emulator to the local FastAPI instance. See `docs/ARCHITECTURE.md`.