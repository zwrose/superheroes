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
    "FIXER_PHASE",
    "AUDITS_PHASE",
    "HEAD_CONTENT_BLOBS_FILE",
    "HEAD_CONTENT_BLOBS_SCHEMA",
    "SEAT_MISSING_SCHEMA",
    "FIX_FOLD_HEAD_KEY",
    "WRITE_RESULT_KIND",
    "RECORD_RESULT_KINDS",
    "REVIEW_LIST_RESULT_KINDS",
    "FINDING_KEY_FIELD",
    "evidence_digest_subject",
    "canonical",
    "payload_sha256",
    "finding_identity_key",
    "location_key",
)

# Result kind a write run's execution record carries — binds the run's own report, not a payload key.
WRITE_RESULT_KIND = "evidence"
RECORD_RESULT_KINDS = ("ruling",)   # kinds whose seat payload IS the record the runner hashed
REVIEW_LIST_RESULT_KINDS = ("findings", "verdicts")

STATE_FILE = "loop-state.json"
JOURNAL_FILE = "driver-journal.jsonl"
JOURNAL_FAULT_FILE = "driver-journal-fault.jsonl"
META_FILE = "meta.json"
PANEL_PHASE = "dispatch-panel"
FIXER_PHASE = "dispatch-fixer"
AUDITS_PHASE = "dispatch-audits"
HEAD_CONTENT_BLOBS_FILE = "head-content-blobs.json"
HEAD_CONTENT_BLOBS_SCHEMA = "head-content-blobs/2"
SEAT_MISSING_SCHEMA = "seat-missing/1"
FIX_FOLD_HEAD_KEY = "fixFoldHeadSha"
FINDING_KEY_FIELD = "findingKey"


def location_key(finding):
    """Per-LOCATION key: line-less finding_identity plus line — total for any dict."""
    if not isinstance(finding, dict):
        return None
    return "%s@L%s" % (finding_identity(finding), finding.get("line"))


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def payload_sha256(payload):
    """The hash the torn-write detector compares against: sha256 over the payload's canonical
    JSON, so a re-serialization with different key order or spacing still matches."""
    return sha256_text(canonical(payload))


def evidence_digest_subject(payload, result_kind):
    """The bytes bound by execution evidence for a review result kind. Never raises.

    Four arms, each mirroring the runner rule for that kind family:
    - record kinds (`RECORD_RESULT_KINDS`): whole payload when the record field is truthy
    - `grouping`: the grouping value when the key is present (any type)
    - other non-review kinds (`result`, `fixes`, …): the key's value when present (any type)
    - review list kinds (`REVIEW_LIST_RESULT_KINDS`): the list under the key when it is a list
    """
    if not isinstance(payload, dict):
        return False, None
    if result_kind in RECORD_RESULT_KINDS:
        if payload.get(result_kind):
            return True, payload
        return False, None
    if result_kind == "grouping":
        if "grouping" not in payload:
            return False, None
        return True, payload.get("grouping")
    if result_kind not in REVIEW_LIST_RESULT_KINDS:
        if result_kind not in payload:
            return False, None
        return True, payload[result_kind]
    value = payload.get(result_kind)
    if isinstance(value, list):
        return True, value
    return False, None


def finding_identity_key(finding):
    """Stable identity for disposition-ledger entries — shared by driver and writer."""
    if not isinstance(finding, dict):
        return None
    key = finding.get(FINDING_KEY_FIELD)
    if isinstance(key, str) and key:
        return key
    return location_key(finding)
