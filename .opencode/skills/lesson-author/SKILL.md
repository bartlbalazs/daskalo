---
name: lesson-author
description: Use when the user runs /lesson or asks to author, brainstorm, or generate a Daskalo Greek lesson through opencode conversation before running content-cli.
---

# Lesson Author

Guide an operator through curriculum-aware lesson ideation inside opencode, then run the existing `content-cli` pipeline non-interactively. This skill intentionally does not change `content-cli/`, Firestore schema, or production data.

## Scope

- Use this for `/lesson`, lesson authoring, conversational lesson brainstorming, or replacing the old external-LLM drafting workflow.
- Keep the existing pipeline authoritative: `daskalo generate` still creates the final passage, vocabulary, grammar notes, exercises, review, media, package, and local ingest.
- Use local emulator ingest by default. Do not run production upload commands unless the user explicitly asks after generation.
- Do not edit application code during this workflow unless the user separately asks for code changes.

## Helper

Use the read-only helper script for all curriculum briefs:

```bash
uv run --project content-cli python .opencode/skills/lesson-author/scripts/generate_brief.py [chapter_id]
```

Run it from the repository root. It writes nothing. It returns one JSON object with `preconditions`, and either `books` or `brief`.

## Workflow

### 1. Resolve Chapter

If the command argument contains a chapter ID, use it. Otherwise run the helper without arguments and show the user the available books/chapters concisely, then ask which chapter to author.

If the helper reports `content_cli_env_exists: false` or `google_cloud_project_set: false`, stop before generation and tell the user to create/fix `content-cli/.env` with `GOOGLE_CLOUD_PROJECT`. The brainstorming conversation may continue, but the final `daskalo generate` run will fail until this is fixed.

If `firestore_emulator_reachable` or `storage_emulator_reachable` is false, warn that local ingest needs `./dev.sh` running before generation. Do not block the brainstorming step.

### 2. Present Brief

Run the helper with the chosen chapter ID. Present:

- Book, chapter order, suggested length, CEFR level, and language skill.
- Target grammar exactly as returned.
- Mandatory vocabulary as a checklist.
- Accumulated grammar and vocabulary as allowed prior knowledge.
- Length options and sentence ranges from `length_options`.
- Existing local ZIPs and existing emulator chapter IDs as informational only. Multiple variants are allowed, so never treat existing content as a blocker.

Also state the hard passage constraints from the pipeline:

- No dialogue or direct speech in the passage; the final passage is narrated by a single continuous voice.
- Modern everyday topics should be warm and conversational with 1-2 natural Greek colloquialisms, not repetitive slang.
- Historical or mythological topics should omit modern slang and use a slightly formal storytelling tone.
- Simplify for language learning, but do not fictionalize real historical events.

### 3. Co-Author Draft

Interview the user to shape the scenario. Get enough detail for:

- Core setting and story beats.
- Tone or cultural angle.
- Student interests, if any.
- Preferred length, defaulting to the chapter's `suggested_length`.
- How each mandatory vocabulary item will appear naturally.
- How the target grammar will be featured heavily.

Iterate until the user explicitly approves the draft direction. A Greek passage draft is optional; if one is produced, make clear that it steers the pipeline but is not guaranteed to survive verbatim.

### 4. Build The Seed

After approval, condense the conversation into a rich `--topic` seed. Include:

- Scenario summary.
- Key story beats in order.
- Required cultural/tone guidance.
- Mandatory vocabulary checklist.
- Target grammar emphasis.
- Approved passage draft if one exists, labeled: `Follow this draft closely; reuse these sentences where possible, but keep the final passage compliant with the pipeline rules.`

Set `--interests` to the interests discovered during the conversation, or `general` if none were given.

### 5. Run Generation

Before generation, ensure the local stack is running if the user expects local ingest. Then run from `content-cli/`:

```bash
uv run daskalo generate --curriculum-chapter <chapter_id> --topic "<rich seed>" --interests "<interests>" --length <short|medium|long> --local
```

Use the Bash tool with `workdir` set to `content-cli`; do not use `cd`. Let the command run to completion unless it clearly waits for unexpected input.

If generation fails, report the failure and tell the user that re-running the exact same command resumes from the last completed graph node because the pipeline is checkpointed.

### 6. Report Results

Summarize:

- Whether generation and local ingest completed.
- Any reviewer retry/warning lines or unresolved feedback visible in the output.
- Any media warnings or failed media counts visible in the output.
- The generated ZIP path from the output.
- Where to inspect locally: `http://localhost:4200`.

Offer, but do not automatically run unless the user agrees:

- Generate a practice set from the new ZIP with `uv run daskalo generate-practice output/<zip-name>`.
- Publish later with `uv run daskalo upload --remote output/<zip-name>`.

## Guardrails

- Never invent curriculum fields. Use the helper output, `docs/DATA_MODEL.md`, and `shared/data/books/*.yaml`.
- Never bypass `daskalo generate` by writing Firestore documents directly.
- Never run `upload --remote` as part of `/lesson` unless the user explicitly asks for production publishing.
- Never promise verbatim passage fidelity. The approved draft steers `draft_lesson_core`; it does not replace that node.
