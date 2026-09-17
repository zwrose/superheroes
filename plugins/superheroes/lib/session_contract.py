#!/usr/bin/env python3
"""Session-contract path and phase constants — leaf module with no round_* imports."""
__all__ = (
    "STATE_FILE",
    "JOURNAL_FILE",
    "JOURNAL_FAULT_FILE",
    "META_FILE",
    "PANEL_PHASE",
    "HEAD_CONTENT_BLOBS_FILE",
    "SEAT_MISSING_SCHEMA",
    "FIX_FOLD_HEAD_KEY",
    "finding_identity_key",
)

STATE_FILE = "loop-state.json"
JOURNAL_FILE = "driver-journal.jsonl"
JOURNAL_FAULT_FILE = "driver-journal-fault.jsonl"
META_FILE = "meta.json"
PANEL_PHASE = "dispatch-panel"
HEAD_CONTENT_BLOBS_FILE = "head-content-blobs.json"
SEAT_MISSING_SCHEMA = "seat-missing/1"
FIX_FOLD_HEAD_KEY = "fixFoldHeadSha"


def finding_identity_key(finding):
    """Stable identity for disposition-ledger entries — shared by driver and writer."""
    fid = finding.get("id")
    if isinstance(fid, str) and fid:
        return fid
    title = finding.get("title")
    if isinstance(title, str) and title:
        return title
    path = finding.get("file")
    line = finding.get("line")
    if isinstance(path, str) and path:
        return "%s@L%s" % (path, line)
    return None
