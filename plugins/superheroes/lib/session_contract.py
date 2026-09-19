#!/usr/bin/env python3
"""Session-contract path and phase constants — leaf module with no round_* imports."""
import hashlib
import json

from finding_identity import finding_identity

__all__ = (
    "STATE_FILE",
    "JOURNAL_FILE",
    "JOURNAL_FAULT_FILE",
    "META_FILE",
    "PANEL_PHASE",
    "HEAD_CONTENT_BLOBS_FILE",
    "HEAD_CONTENT_BLOBS_SCHEMA",
    "SEAT_MISSING_SCHEMA",
    "FIX_FOLD_HEAD_KEY",
    "WRITE_RESULT_KIND",
    "FINDING_KEY_FIELD",
    "canonical",
    "payload_sha256",
    "finding_identity_key",
    "location_key",
)

# Result kind a write run's execution record carries — binds the run's own report, not a payload key.
WRITE_RESULT_KIND = "evidence"

STATE_FILE = "loop-state.json"
JOURNAL_FILE = "driver-journal.jsonl"
JOURNAL_FAULT_FILE = "driver-journal-fault.jsonl"
META_FILE = "meta.json"
PANEL_PHASE = "dispatch-panel"
HEAD_CONTENT_BLOBS_FILE = "head-content-blobs.json"
HEAD_CONTENT_BLOBS_SCHEMA = "head-content-blobs/2"
SEAT_MISSING_SCHEMA = "seat-missing/1"
FIX_FOLD_HEAD_KEY = "fixFoldHeadSha"
FINDING_KEY_FIELD = "findingKey"


def _safe_identity_finding(finding):
    """Coerce label/file to strings so location_key never raises on bad types."""
    safe = {}
    file_val = finding.get("file")
    safe["file"] = file_val if isinstance(file_val, str) else ""
    label = ""
    for key in ("title", "summary"):
        val = finding.get(key)
        if isinstance(val, str) and val:
            label = val
            break
    safe["title"] = label
    return safe


def location_key(finding):
    """Per-LOCATION key: line-less finding_identity plus line — total for any dict."""
    if not isinstance(finding, dict):
        return None
    safe = _safe_identity_finding(finding)
    return "%s@L%s" % (finding_identity(safe), finding.get("line"))


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def payload_sha256(payload):
    """The hash the torn-write detector compares against: sha256 over the payload's canonical
    JSON, so a re-serialization with different key order or spacing still matches."""
    return sha256_text(canonical(payload))


def finding_identity_key(finding):
    """Stable identity for disposition-ledger entries — shared by driver and writer."""
    if not isinstance(finding, dict):
        return None
    key = finding.get(FINDING_KEY_FIELD)
    if isinstance(key, str) and key:
        return key
    return location_key(finding)
