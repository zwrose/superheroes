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
    "VERIFIED_HEAD_FIELD",
    "DISPOSITIONS",
    "FOLLOW_UP_FIELDS",
    "follow_up_shape_fault",
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
    "legacy_key_collision",
    "LegacyKeyCollision",
    "DISPOSITION_LEDGER_LEGACY_KEY_COLLISION_TOKEN",
    "EXECUTION_ONLY_BINDING",
    "PAYLOAD_BOUND_BINDING",
    "evidence_binding",
    "verify_result_for_head",
    "RE_EMIT_CMD",
    "ORDERS_SUPERSEDED_OUTCOME",
    "journal_is_re_emit_orders_superseded",
)

# Fields the loop stamps onto a finding row after a seat reported it — excluded from content hash.
TRANSIENT_FINDING_FIELDS = frozenset({
    "id", "findingKey", "verdict", "evidence", "challenge", "unverified", "reason",
    "disposition", "dispositionReceipt",
    "dispositionRound", "refutedReason", "outOfScopeReason", "followUp", "mergedInto",
    "raisedRound",
})

# Result kind a write run's execution record carries — binds the run's own report, not a payload key.
WRITE_RESULT_KIND = "evidence"
EXECUTION_ONLY_BINDING = "execution-only"
PAYLOAD_BOUND_BINDING = "payload-bound"


def evidence_binding(result_kind):
    """Which binding a result kind carries — the one home for write-run vs payload-bound kinds."""
    if result_kind == WRITE_RESULT_KIND:
        return EXECUTION_ONLY_BINDING
    return PAYLOAD_BOUND_BINDING
RECORD_RESULT_KINDS = ("ruling",)   # kinds whose seat payload IS the record the runner hashed
REVIEW_LIST_RESULT_KINDS = ("findings", "verdicts")

STATE_FILE = "loop-state.json"
JOURNAL_FILE = "driver-journal.jsonl"
JOURNAL_FAULT_FILE = "driver-journal-fault.jsonl"
RE_EMIT_CMD = "re-emit"
ORDERS_SUPERSEDED_OUTCOME = "orders-superseded"
META_FILE = "meta.json"


def journal_is_re_emit_orders_superseded(event):
    """True when a journal row commits the re-emit supersession protocol."""
    if not isinstance(event, dict):
        return False
    return (event.get("cmd") == RE_EMIT_CMD
            and event.get("outcome") == ORDERS_SUPERSEDED_OUTCOME)
PANEL_PHASE = "dispatch-panel"
FIXER_PHASE = "dispatch-fixer"
AUDITS_PHASE = "dispatch-audits"
HEAD_CONTENT_BLOBS_FILE = "head-content-blobs.json"
HEAD_CONTENT_BLOBS_SCHEMA = "head-content-blobs/2"
SEAT_MISSING_SCHEMA = "seat-missing/1"
FIX_FOLD_HEAD_KEY = "fixFoldHeadSha"
VERIFIED_HEAD_FIELD = "verifiedHead"
FINDING_KEY_FIELD = "findingKey"

DISPOSITIONS = ("fixed", "refuted", "out-of-scope")
FOLLOW_UP_FIELDS = ("item", "revisitTrigger", "classClosure")


def follow_up_shape_fault(follow_up, *, require_item=True):
    """None when followUp is fully shaped; otherwise (binding_failure, detail).

    With ``require_item=True`` a missing ``item`` is refused; with ``require_item=False`` a missing
    ``item`` passes, but a present-but-empty or non-string ``item`` is still refused."""
    if not isinstance(follow_up, dict):
        return (None, "out-of-scope disposition lacks named follow-up item")
    if require_item and "item" not in follow_up:
        return ("missing-follow-up-item", "out-of-scope follow-up lacks named item")
    if "item" in follow_up:
        item = follow_up.get("item")
        if not isinstance(item, str) or not item.strip():
            return ("missing-follow-up-item", "out-of-scope follow-up lacks named item")
    trigger = follow_up.get("revisitTrigger")
    if not isinstance(trigger, str) or not trigger.strip():
        return ("missing-revisit-trigger", "out-of-scope follow-up lacks revisit trigger")
    if "documented" in trigger.lower():
        return (None, "revisit trigger must not be the word documented")
    closure = follow_up.get("classClosure")
    if not isinstance(closure, str) or not closure.strip():
        return ("missing-class-closure", "out-of-scope follow-up lacks class-closure line")
    return None


DISPOSITION_LEDGER_KEY = "dispositionLedger"
DISPOSITION_LEDGER_MALFORMED_TOKEN = "disposition-ledger-malformed"
DISPOSITION_LEDGER_LEGACY_KEY_COLLISION_TOKEN = "disposition-ledger-legacy-key-collision"
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


def read_disposition_ledger(state, required=False):
    """Pure read of ``dispositionLedger`` — never mutates ``state``.

    Returns shallow-copied rows and ``None``, or ``([], fault)`` when the stored ledger is
    malformed. An absent key is not malformed unless ``required`` is True (recognized-owner reads)."""
    if not isinstance(state, dict):
        if required:
            return [], DispositionLedgerReadFault(
                token=DISPOSITION_LEDGER_MALFORMED_TOKEN,
                detail="dispositionLedger key absent when dispositionLedgerOwner is %r"
                % (DISPOSITION_LEDGER_OWNER_VALUE,),
            )
        return [], None
    if DISPOSITION_LEDGER_KEY not in state:
        if required:
            return [], DispositionLedgerReadFault(
                token=DISPOSITION_LEDGER_MALFORMED_TOKEN,
                detail="dispositionLedger key absent when dispositionLedgerOwner is %r"
                % (DISPOSITION_LEDGER_OWNER_VALUE,),
            )
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


@dataclass(frozen=True)
class LegacyKeyCollision:
    """A legacy bare-key row whose key cannot be joined safely — refused, never repaired here."""
    bare_key: str
    minted_key: str
    claimant_key: Optional[str] = None

    @property
    def detail(self):
        if self.claimant_key is None:
            return "legacy bare key %r collides with minted key %r" % (self.bare_key, self.minted_key)
        return ("legacy bare key %r (minted %r) is also claimed by a different finding minted %r"
                % (self.bare_key, self.minted_key, self.claimant_key))


def legacy_key_collision(rows):
    """Return a ``LegacyKeyCollision`` when a legacy bare-key row cannot be joined safely.

    A legacy row is one stored under its bare location key while its content mints a longer key.
    Two shapes refuse: the same finding held under both its bare and its minted key, and a
    different finding (the clamp-exact short title) whose own key IS that bare key. Claimants are
    tracked per effective key by minted identity, so a legacy row beside a copy of itself under the
    same bare key is one finding and joins as before."""
    identity_keys = set()
    claimants = {}
    legacy_pairs = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        identity = finding_identity_key(row)
        bare = location_key(row)
        minted = minted_identity_key(row)
        if identity:
            identity_keys.add(identity)
            claimants.setdefault(identity, set()).add(minted)
        if identity == bare and bare != minted:
            legacy_pairs.append((bare, minted))
    for bare, minted in legacy_pairs:
        if minted in identity_keys:
            return LegacyKeyCollision(bare, minted)
        others = sorted(claimants[bare] - {minted})
        if others:
            return LegacyKeyCollision(bare, minted, others[0])
    return None


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


def verify_result_for_head(state, head):
    """The verify result recorded FOR `head`, or None. The ONE reader of the verified-head fact.

    `_fold_verify` records `verifiedHead` beside `verifyResult` in the round record it writes;
    this answers "was this head verified, and how" from that record alone. A round record with a
    `verifyResult` but NO `verifiedHead` reads as NOT VERIFIED (fail-closed) — the verified-head
    fact is never reconstructed from `verifyResult` plus `fixFoldHead`, which is the class this
    retires (three passes over that reconstruction each broke a neighbour, #1272 layer 2g)."""
    if not isinstance(head, str) or not head:
        return None
    if not isinstance(state, dict):
        return None
    rounds = state.get("rounds")
    if not isinstance(rounds, dict):
        return None
    round_nums = []
    for key in rounds:
        try:
            round_nums.append(int(key))
        except (TypeError, ValueError):
            continue
    for rnd in sorted(round_nums, reverse=True):
        rec = rounds.get(str(rnd))
        if not isinstance(rec, dict):
            continue
        verified = rec.get(VERIFIED_HEAD_FIELD)
        if isinstance(verified, str) and verified and verified == head:
            return rec.get("verifyResult")
    return None
