#!/usr/bin/env python3
"""Session-contract path and phase constants — leaf module with no round_* imports."""
import base64
import binascii
import hashlib
import json
from dataclasses import dataclass
from typing import Optional

from finding_identity import clamp_title, finding_identity, finding_label, normalize_title

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
    "TRANSIENT_FINDING_FIELDS",
    "DISPOSITIONS",
    "DISPOSITION_LEDGER_KEY",
    "DISPOSITION_LEDGER_MALFORMED_TOKEN",
    "DispositionLedgerReadFault",
    "read_disposition_ledger",
    "DISPOSITION_LEDGER_OWNER_FIELD",
    "DISPOSITION_LEDGER_OWNER_VALUE",
    "DISPOSITION_LEDGER_OWNER_ABSENT",
    "DISPOSITION_LEDGER_OWNER_RECOGNIZED",
    "DISPOSITION_LEDGER_OWNER_UNRECOGNIZED",
    "disposition_ledger_owner_classification",
    "MERGED_INTO_FIELD",
    "RAISED_ROUND_FIELD",
    "DISPOSITION_FAMILY_FIELDS",
    "has_disposition_family",
    "disposition_family_snapshot",
    "apply_disposition_family",
    "strip_disposition_family",
    "evidence_digest_subject",
    "canonical",
    "payload_sha256",
    "finding_identity_key",
    "location_key",
    "minted_identity_key",
    "finding_content_canonical",
    "content_hash_suffix",
    "HeadContentRead",
    "classify_head_content_read",
    "resolve_merged_into_entry",
    "fix_proof_path",
    "fix_still_present_at_head",
    "legacy_disposition_ledger_rows",
)

# Fields the loop stamps onto a finding row after a seat reported it — excluded from content hash.
TRANSIENT_FINDING_FIELDS = frozenset({
    "id", "findingKey", "verdict", "evidence", "challenge", "unverified", "reason",
    "disposition", "dispositionReceipt",
})

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

DISPOSITIONS = ("fixed", "refuted", "out-of-scope")
DISPOSITION_LEDGER_KEY = "dispositionLedger"
DISPOSITION_LEDGER_MALFORMED_TOKEN = "disposition-ledger-malformed"
DISPOSITION_LEDGER_OWNER_FIELD = "dispositionLedgerOwner"
DISPOSITION_LEDGER_OWNER_VALUE = "ledger"
DISPOSITION_LEDGER_OWNER_ABSENT = "absent"
DISPOSITION_LEDGER_OWNER_RECOGNIZED = "recognized"
DISPOSITION_LEDGER_OWNER_UNRECOGNIZED = "unrecognized"
MERGED_INTO_FIELD = "mergedInto"


@dataclass(frozen=True)
class DispositionLedgerReadFault:
    """Malformed dispositionLedger — propagates to certification refusal, never repaired here."""
    token: str
    detail: str


def read_disposition_ledger(state):
    """Pure read of ``dispositionLedger`` — never mutates ``state``.

    Returns shallow-copied rows and ``None``, or ``([], fault)`` when the stored ledger is
    malformed. An absent key is not malformed."""
    if not isinstance(state, dict) or DISPOSITION_LEDGER_KEY not in state:
        return [], None
    ledger = state[DISPOSITION_LEDGER_KEY]
    if not isinstance(ledger, list):
        return [], DispositionLedgerReadFault(
            token=DISPOSITION_LEDGER_MALFORMED_TOKEN,
            detail="dispositionLedger must be a list when dispositionLedgerOwner is %r"
            % (DISPOSITION_LEDGER_OWNER_VALUE,),
        )
    rows = []
    for entry in ledger:
        if not isinstance(entry, dict):
            return [], DispositionLedgerReadFault(
                token=DISPOSITION_LEDGER_MALFORMED_TOKEN,
                detail="dispositionLedger row must be an object",
            )
        key = finding_identity_key(entry)
        if not key:
            return [], DispositionLedgerReadFault(
                token=DISPOSITION_LEDGER_MALFORMED_TOKEN,
                detail="dispositionLedger row lacks a finding key",
            )
        rows.append(dict(entry))
    return rows, None


def legacy_disposition_ledger_rows(state):
    """Yield ``(key, row)`` from a legacy (non-owner) ledger — skip malformed rows only."""
    if not isinstance(state, dict):
        return
    ledger = state.get(DISPOSITION_LEDGER_KEY)
    if not isinstance(ledger, list):
        return
    for finding in ledger:
        if not isinstance(finding, dict):
            continue
        key = finding_identity_key(finding)
        if key:
            yield key, finding


def disposition_ledger_owner_classification(state):
    """Single derivation of the disposition-ledger owner marker — absent, recognized, or unrecognized."""
    if not isinstance(state, dict):
        return DISPOSITION_LEDGER_OWNER_ABSENT
    if DISPOSITION_LEDGER_OWNER_FIELD not in state:
        return DISPOSITION_LEDGER_OWNER_ABSENT
    value = state[DISPOSITION_LEDGER_OWNER_FIELD]
    if value == DISPOSITION_LEDGER_OWNER_VALUE:
        return DISPOSITION_LEDGER_OWNER_RECOGNIZED
    return DISPOSITION_LEDGER_OWNER_UNRECOGNIZED
RAISED_ROUND_FIELD = "raisedRound"
DISPOSITION_FAMILY_FIELDS = (
    "disposition", "dispositionRound", "dispositionReceipt", "refutedReason",
    "outOfScopeReason", "followUp", MERGED_INTO_FIELD,
)


def has_disposition_family(row):
    """True when row carries any disposition-family member with a non-None value."""
    if not isinstance(row, dict):
        return False
    for field in DISPOSITION_FAMILY_FIELDS:
        if field in row and row[field] is not None:
            return True
    return False


def disposition_family_snapshot(row):
    """Snapshot of disposition-family members present on row."""
    if not isinstance(row, dict):
        return {}
    return {field: row[field] for field in DISPOSITION_FAMILY_FIELDS if field in row}


def apply_disposition_family(target, family):
    """Set every named disposition-family field on target and pop any member family omits."""
    for field in DISPOSITION_FAMILY_FIELDS:
        if field in family:
            target[field] = family[field]
        else:
            target.pop(field, None)


def strip_disposition_family(row):
    """Return a copy of row with every disposition-family member removed."""
    copy = dict(row)
    for field in DISPOSITION_FAMILY_FIELDS:
        copy.pop(field, None)
    return copy


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


def minted_identity_key(finding):
    """Identity the loop mints from content — no foreign preset."""
    if not isinstance(finding, dict):
        return None
    base = location_key(finding)
    full_norm = normalize_title(finding_label(finding))
    clamped_norm = normalize_title(clamp_title(finding_label(finding)))
    if full_norm != clamped_norm:
        return base + "#" + sha256_text(full_norm)[:12]
    return base


def finding_content_canonical(finding):
    """Canonical JSON of a finding row with transient loop-stamped fields removed."""
    if not isinstance(finding, dict):
        return None
    body = {k: v for k, v in finding.items() if k not in TRANSIENT_FINDING_FIELDS}
    return canonical(body)


def content_hash_suffix(finding):
    return sha256_text(finding_content_canonical(finding))[:12]


def finding_identity_key(finding):
    """The one derivation of a finding's identity. Never reads `id`."""
    if not isinstance(finding, dict):
        return None
    key = finding.get(FINDING_KEY_FIELD)
    if isinstance(key, str) and key:
        return key
    return minted_identity_key(finding)


@dataclass(frozen=True)
class HeadContentRead:
    """Normalized outcome of a head-content-blobs read — no I/O in this module."""
    kind: str
    blobs: Optional[dict] = None


def classify_head_content_read(*, absent=False, blobs=None, error=None):
    """Classify a caller's raw head-content read attempt into ``HeadContentRead``."""
    if absent:
        return HeadContentRead(kind="missing")
    if error is not None:
        return HeadContentRead(kind="unreadable")
    if not isinstance(blobs, dict):
        return HeadContentRead(kind="unreadable")
    return HeadContentRead(kind="ok", blobs=blobs)


def resolve_merged_into_entry(finding, by_key):
    """Follow mergedInto through by_key; None when the chain does not resolve."""
    if not isinstance(finding, dict):
        return finding
    if not finding.get(MERGED_INTO_FIELD):
        return finding
    limit = max(len(by_key), 1)
    entry = finding
    visited = set()
    for _ in range(limit):
        into = entry.get(MERGED_INTO_FIELD)
        if not isinstance(into, str) or not into:
            return None
        if into in visited:
            return None
        visited.add(into)
        target = by_key.get(into)
        if target is None:
            return None
        if not target.get(MERGED_INTO_FIELD):
            return target
        entry = target
    return None


def fix_proof_path(finding, by_key=None):
    """File path whose head-content proof binds a fixed disposition — representative for merged members."""
    path = finding.get("file")
    if by_key is not None and finding.get(MERGED_INTO_FIELD):
        resolved = resolve_merged_into_entry(finding, by_key)
        if isinstance(resolved, dict):
            rep_path = resolved.get("file")
            if isinstance(rep_path, str) and rep_path:
                path = rep_path
    return path


def fix_still_present_at_head(finding, receipt, head, read_outcome, by_key=None):
    """Return ``(binding_failure_token, detail)`` when the fix no longer stands, else ``None``.

    ``head`` and ``read_outcome`` are supplied by the caller; this leaf never reaches for a session."""
    path = fix_proof_path(finding, by_key)
    if not isinstance(path, str) or not path:
        return (
            "fix-content-missing",
            "fixed disposition lacks file path for head-content verification",
        )
    if not isinstance(head, str) or not head:
        return (
            "fix-content-missing",
            "fixed disposition lacks certified head for content verification",
        )
    if read_outcome.kind == "unreadable":
        return (
            "fix-content-unreadable",
            "fixed disposition fix-content read failed on certified head",
        )
    if read_outcome.kind == "missing":
        return (
            "fix-content-missing",
            "fixed disposition lacks head-content evidence on certified head",
        )
    blobs = read_outcome.blobs
    if blobs.get("schema") != HEAD_CONTENT_BLOBS_SCHEMA:
        return (
            "fix-content-schema-unsupported",
            "fixed disposition head-content schema is not supported",
        )
    reads = blobs.get("reads")
    if not isinstance(reads, list):
        reads = []
    matching = [
        row
        for row in reads
        if isinstance(row, dict)
        and row.get("headSha") == head
        and row.get("path") == path
    ]
    if not matching:
        return (
            "fix-content-missing",
            "fixed disposition fix is not present in content at the certified head",
        )
    row = matching[-1]
    if row.get("readError") is not None or not row.get("contentDigest"):
        return (
            "fix-content-unreadable",
            "fixed disposition fix-content read failed on certified head",
        )
    content_digest = row["contentDigest"]
    files = blobs.get("files")
    file_b64 = files.get(path) if isinstance(files, dict) else None
    if file_b64 is None:
        return (
            "fix-content-unreadable",
            "fixed disposition fix-content read failed on certified head",
        )
    try:
        raw = base64.b64decode(file_b64, validate=True)
    except (binascii.Error, ValueError):
        return (
            "fix-content-unreadable",
            "fixed disposition fix-content read failed on certified head",
        )
    if hashlib.sha256(raw).hexdigest() != content_digest:
        return (
            "fix-content-reverted",
            "fixed disposition fix is not present in content at the certified head",
        )
    fix_content_digest = receipt.get("fixContentDigest")
    if not isinstance(fix_content_digest, str) or not fix_content_digest:
        return (
            "fix-content-reverted",
            "fixed disposition fix is not present in content at the certified head",
        )
    if content_digest != fix_content_digest:
        return (
            "fix-content-reverted",
            "fixed disposition fix is not present in content at the certified head",
        )
    return None
