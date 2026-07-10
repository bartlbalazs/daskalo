"""
Shared constants used across multiple backend modules.

Centralizing these avoids drift between files that would otherwise each
hardcode their own copy (see docs/planning/BUGS.md#BE-14 and #IMP-BE-09).
"""

from __future__ import annotations

# Gemini model used for all evaluation/generation calls (exercise evaluation,
# pronunciation grading, chapter progress summaries, own-word normalisation).
GEMINI_MODEL_ID = "gemini-2.5-flash"

# XP awarded for completing a practice set (flat, regardless of length).
PRACTICE_XP = 175

# IMP-BE-05: an exercise attempt stuck in "evaluating" for longer than this
# (seconds) is assumed to be an abandoned/crashed invocation and becomes
# eligible for another call to reclaim it, instead of being a permanent
# dead end.
EVALUATING_STALE_SECONDS = 150

# IMP-BE-07: per-user, per-function rate limits enforced in callable_helpers.
# check_rate_limit(), as defense-in-depth underneath the per-project API
# Gateway quota (which today is shared across *all* users — see BE-15).
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_EVALUATE = 5
RATE_LIMIT_COMPLETE_CHAPTER = 3
RATE_LIMIT_ADD_OWN_WORD = 5
RATE_LIMIT_COMPLETE_PRACTICE = 3
RATE_LIMIT_SET_CURRICULUM_SELECTION = 10
RATE_LIMIT_MARK_ONBOARDING_SEEN = 3
