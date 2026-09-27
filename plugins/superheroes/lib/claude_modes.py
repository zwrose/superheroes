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
