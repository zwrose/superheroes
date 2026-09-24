#!/usr/bin/env python3
"""Session-contract path and phase constants — leaf module with no round_* imports."""
import hashlib
import json

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
    "SEAT_TRANSPORT_KEY",
    "SEAT_TRANSPORT_RUNNER",
    "SEAT_TRANSPORT_NATIVE",
    "SEAT_TRANSPORT_HAND_LANDED",
    "SEAT_TRANSPORT_ORCHESTRATOR",
    "SEAT_TRANSPORTS",
    "SEAT_TRANSPORTS_DISCLOSED",
    "canonical",
    "payload_sha256",
    "finding_identity_key",
)

SEAT_TRANSPORT_KEY = "transport"
SEAT_TRANSPORT_RUNNER = "runner"
SEAT_TRANSPORT_NATIVE = "native-subagent"
SEAT_TRANSPORT_HAND_LANDED = "hand-landed"
SEAT_TRANSPORT_ORCHESTRATOR = "orchestrator"
SEAT_TRANSPORTS = (
    SEAT_TRANSPORT_RUNNER,
    SEAT_TRANSPORT_NATIVE,
    SEAT_TRANSPORT_HAND_LANDED,
    SEAT_TRANSPORT_ORCHESTRATOR,
)
SEAT_TRANSPORTS_DISCLOSED = (SEAT_TRANSPORT_NATIVE, SEAT_TRANSPORT_HAND_LANDED)

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
