---
description: Author a new Daskalo lesson through conversation, then generate it locally.
agent: build
---

Load the `lesson-author` skill and run an interactive Daskalo lesson-authoring session for curriculum chapter "$ARGUMENTS". Use `docs/TARGET_AUDIENCE.md` as the default learner profile unless the user gives per-lesson audience overrides.

If "$ARGUMENTS" is empty, ask the user which chapter to work on after showing the curriculum-aware chapter list from the skill's brief helper.
