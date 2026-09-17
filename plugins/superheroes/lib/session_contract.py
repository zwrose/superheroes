#!/usr/bin/env python3
"""Session-contract path and phase constants — leaf module with no round_* imports."""
__all__ = (
    "STATE_FILE",
    "JOURNAL_FILE",
    "JOURNAL_FAULT_FILE",
    "META_FILE",
    "PANEL_PHASE",
)

STATE_FILE = "loop-state.json"
JOURNAL_FILE = "driver-journal.jsonl"
JOURNAL_FAULT_FILE = "driver-journal-fault.jsonl"
META_FILE = "meta.json"
PANEL_PHASE = "dispatch-panel"
