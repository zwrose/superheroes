#!/usr/bin/env python3
"""Single home of the claude dispatch-mode vocabulary (print is the only dispatchable mode)."""

MODE_PRINT = "print"
CLAUDE_MODES = (MODE_PRINT,)
# Retired dispatch modes: accepted by the CLI only so they reach a named refusal
# (claude-mode-retired) instead of argparse's exit 2. Never dispatchable.
RETIRED_MODE_BACKGROUND = "background"
RETIRED_CLAUDE_MODES = (RETIRED_MODE_BACKGROUND,)
CLAUDE_MODE_INPUTS = CLAUDE_MODES + RETIRED_CLAUDE_MODES
ENTRY_REASON_CLAUDE_MODE_RETIRED = "claude-mode-retired"
DETAIL_RUN_DIR_CLAUDE_MODE_RETIRED = "run-dir-claude-mode-retired"
DETAIL_RUN_DIR_CLAUDE_MODE_UNKNOWN = "run-dir-claude-mode-unknown"

CLASS_DISPATCHABLE = "dispatchable"
CLASS_RETIRED = "retired"
CLASS_UNKNOWN = "unknown"


def classify(value):
    """Classify a claude mode value for dispatch chokepoints. Never raises."""
    if value is None:
        return CLASS_DISPATCHABLE
    for mode in CLAUDE_MODES:
        if value == mode:
            return CLASS_DISPATCHABLE
    for mode in RETIRED_CLAUDE_MODES:
        if value == mode:
            return CLASS_RETIRED
    return CLASS_UNKNOWN
