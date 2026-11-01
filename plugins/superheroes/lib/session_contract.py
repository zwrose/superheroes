#!/usr/bin/env python3
"""Session-contract path and phase constants — leaf module with no round_* imports."""
import copy
import hashlib
import json
from dataclasses import dataclass

import model_registry
import review_findings_schema

from finding_identity import clamp_title, finding_identity, finding_label, normalize_title

__all__ = (
    "STATE_FILE",
    "MIRROR_FILE",
    "JOURNAL_FILE",
    "JOURNAL_FAULT_FILE",
    "META_FILE",
    "PANEL_PHASE",
    "AUDITS_PHASE",
    "CHANNEL_FILE",
    "CHANNEL_STDOUT",
    "SEAT_MISSING_SCHEMA",
    "FIX_FOLD_HEAD_KEY",
    "WRITE_RESULT_KIND",
    "RECORD_RESULT_KINDS",
    "REVIEW_LIST_RESULT_KINDS",
    "OUTSIDE_FIX_AUDITOR",
    "OUTSIDE_SCOPED_FINDER",
    "OUTSIDE_SEAMS_CHECK",
    "FINDING_KEY_FIELD",
    "TRANSIENT_FINDING_FIELDS",
    "DISPOSITIONS",
    "FOLLOW_UP_FIELDS",
    "follow_up_shape_fault",
    "copy_follow_up_field",
    "copy_decided_by_field",
    "decided_by_of",
    "has_decided_by",
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
    "RAISED_SEQ_FIELD",
    "DISPOSITION_SEQ_FIELD",
    "DISPOSITION_FAMILY_FIELDS",
    "has_disposition_family",
    "disposition_family_snapshot",
    "apply_disposition_family",
    "strip_disposition_family",
    "evidence_digest_subject",
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
    "location_key",
    "minted_identity_key",
    "finding_content_canonical",
    "content_hash_suffix",
    "coerce_line",
    "add_outside_hit",
    "resolve_merged_into_entry",
    "legacy_disposition_ledger_rows",
    "legacy_key_collision",
    "EXECUTION_ONLY_BINDING",
    "PAYLOAD_BOUND_BINDING",
    "evidence_binding",
    "execution_only_admissible_for_phase",
    "RUN_KIND_REVIEW",
    "RUN_KIND_WRITE",
    "RUN_KIND_SEARCH",
    "RUN_KIND_VALUES",
    "add_sweep_hit",
    "classify_sweep_hits",
    "sweep_hit_finding",
    "sweep_hit_title",
    "SWEEP_SOURCE_NAME",
    "SWEEP_OF_FIELD",
    "run_kind_value_ok",
    "run_kind_for_phase",
    "RUN_KIND_BY_PHASE",
    "EXECUTION_EVIDENCE_RUN_KIND_FIELD",
    "EXECUTION_EVIDENCE_BINDING_FIELDS",
    "runner_channel_vendor",
    "RULE_CMD",
)

RAISED_ROUND_FIELD = "raisedRound"
RAISED_SEQ_FIELD = "raisedSeq"
DISPOSITION_SEQ_FIELD = "dispositionSeq"

# Fields the loop stamps onto a finding row after a seat reported it — excluded from content hash.
TRANSIENT_FINDING_FIELDS = frozenset({
    "id", "findingKey", "verdict", "evidence", "challenge", "unverified", "reason",
    "disposition", "dispositionReceipt",
    "dispositionRound", "refutedReason", "outOfScopeReason", "followUp", "mergedInto",
    RAISED_ROUND_FIELD, RAISED_SEQ_FIELD, DISPOSITION_SEQ_FIELD,
})

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
EXECUTION_ONLY_BINDING = "execution-only"
PAYLOAD_BOUND_BINDING = "payload-bound"


def evidence_binding(result_kind):
    """Which binding a result kind carries — the one home for write-run vs payload-bound kinds."""
    if result_kind == WRITE_RESULT_KIND:
        return EXECUTION_ONLY_BINDING
    return PAYLOAD_BOUND_BINDING


def execution_only_admissible_for_phase(phase):
    """True when execution-only (write-run) evidence binding is admissible for this phase. No
    phase is: every dispatched seat is a review run, and the build session writes its own fixes."""
    return False

PANEL_PHASE = "dispatch-panel"
AUDITS_PHASE = "dispatch-audits"

RUN_KIND_REVIEW = "review"
RUN_KIND_WRITE = "write"
# A repository-sweep searcher is neither a reviewer nor a writer: it only reads the files it is given for one described mistake.
RUN_KIND_SEARCH = "search"
RUN_KIND_VALUES = frozenset((RUN_KIND_REVIEW, RUN_KIND_WRITE, RUN_KIND_SEARCH))


def run_kind_value_ok(value):
    return isinstance(value, str) and value in RUN_KIND_VALUES


# Immutable by convention — the closed phase→runKind map; never mutate after definition.
RUN_KIND_BY_PHASE = {
    PANEL_PHASE: RUN_KIND_REVIEW,
    "dispatch-verifiers": RUN_KIND_REVIEW,
    "dispatch-synthesis": RUN_KIND_REVIEW,
    AUDITS_PHASE: RUN_KIND_REVIEW,
    "dispatch-scoped-finder": RUN_KIND_REVIEW,
    "dispatch-seams-check": RUN_KIND_REVIEW,
    "dispatch-second-test": RUN_KIND_REVIEW,
    "dispatch-sweep": RUN_KIND_SEARCH,
}

EXECUTION_EVIDENCE_RUN_KIND_FIELD = "runKind"

EXECUTION_EVIDENCE_BINDING_FIELDS = (
    "source",
    "runnerNonce",
    "recordDigest",
    "resultDigest",
    "resultKind",
    EXECUTION_EVIDENCE_RUN_KIND_FIELD,
)


def run_kind_for_phase(phase):
    """Expected executionEvidence.runKind for a dispatch phase, or None when phase is unknown."""
    if isinstance(phase, str):
        return RUN_KIND_BY_PHASE.get(phase)
    return None

RECORD_RESULT_KINDS = ("ruling",)   # kinds whose seat payload IS the record the runner hashed
REVIEW_LIST_RESULT_KINDS = ("findings", "verdicts")

# the source names of an outside hit raised outside the panel: the driver persists them as the finding's
# source name and the record writer matches them back, so both read this one home
OUTSIDE_FIX_AUDITOR = "fix auditor"
OUTSIDE_SCOPED_FINDER = "scoped finder"
OUTSIDE_SEAMS_CHECK = "seams check"

STATE_FILE = "loop-state.json"
MIRROR_FILE = "loop-state.mirror.json"
JOURNAL_FILE = "driver-journal.jsonl"
JOURNAL_FAULT_FILE = "driver-journal-fault.jsonl"
RULE_CMD = "rule"
META_FILE = "meta.json"

CHANNEL_FILE = "file"
CHANNEL_STDOUT = "stdout"
SEAT_MISSING_SCHEMA = "seat-missing/1"
FIX_FOLD_HEAD_KEY = "fixFoldHeadSha"
FINDING_KEY_FIELD = "findingKey"

# The three settled outcomes (craft, left-for-owner, ruling) are written only by the end-of-loop settle.
DISPOSITIONS = ("fixed", "refuted", "out-of-scope") + review_findings_schema.OUTCOMES[2:]
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


def copy_follow_up_field(source, target):
    """Copy followUp from source onto target when the key is present (defensive copy)."""
    if "followUp" in source:
        target["followUp"] = dict(source["followUp"])


def copy_decided_by_field(source, target):
    """Copy decidedBy from source onto target when the key is present (deep copy)."""
    if "decidedBy" in source:
        target["decidedBy"] = copy.deepcopy(source["decidedBy"])


def decided_by_of(row):
    """The row's decidedBy when the row is a dict holding it, else None."""
    if isinstance(row, dict):
        return row.get("decidedBy")
    return None


def has_decided_by(row):
    """True when the row is a dict with the decidedBy key present, whatever its value."""
    return isinstance(row, dict) and "decidedBy" in row


DISPOSITION_LEDGER_KEY = "dispositionLedger"
DISPOSITION_LEDGER_MALFORMED_TOKEN = "disposition-ledger-malformed"
DISPOSITION_LEDGER_OWNER_FIELD = "dispositionLedgerOwner"
DISPOSITION_LEDGER_OWNER_VALUE = "ledger"
DISPOSITION_LEDGER_OWNER_ABSENT = "absent"
DISPOSITION_LEDGER_OWNER_RECOGNIZED = "recognized"
DISPOSITION_LEDGER_OWNER_UNRECOGNIZED = "unrecognized"
MERGED_INTO_FIELD = "mergedInto"
FULL_PANEL_NOT_RERAISED = "full-panel-not-reraised"   # dispositionReceipt kind: a complete later panel did not raise a reported fix again


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


def legacy_key_collision(rows):
    """Return (bare_key, minted_key) when legacy identity keys collide.

    Refuses when (1) a legacy bare-keyed row's derived minted key is claimed globally
    by another row's stored identity, or (2) rows sharing a bare location key include a
    legacy bare-key claimant whose (stored identity, minted key) pair disagrees with
    another row at that location. Content drift is not an identity discriminator.
    """
    identity_keys = set()
    legacy_pairs = []
    by_bare = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        bare = location_key(row)
        if not bare:
            continue
        identity = finding_identity_key(row)
        minted = minted_identity_key(row)
        if identity:
            identity_keys.add(identity)
        if identity == bare and bare != minted:
            legacy_pairs.append((bare, minted))
        by_bare.setdefault(bare, []).append((identity, minted))
    for bare, minted in legacy_pairs:
        if minted in identity_keys:
            return bare, minted
    for bare, entries in by_bare.items():
        claimants = [entry for entry in entries if entry[0] == bare]
        if not claimants:
            continue
        ref_identity, ref_minted = claimants[0]
        for identity, minted in entries:
            if (identity, minted) != (ref_identity, ref_minted):
                return bare, ref_minted
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
DISPOSITION_FAMILY_FIELDS = (
    "disposition", "dispositionRound", "dispositionReceipt", "placeResults", "refutedReason",
    "outOfScopeReason", "followUp", MERGED_INTO_FIELD, "settledReason", "decidedBy",
)


def disposition_value(row):
    """The graded disposition value on row, or None when absent."""
    if not isinstance(row, dict):
        return None
    return row.get("disposition")


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


def coerce_line(value):
    """Return ``(ok, line)``: an int (never a bool) passes as itself; a numeric string
    (``"291"``, surrounding whitespace tolerated) coerces to its int; anything else refuses."""
    if isinstance(value, bool):
        return False, value
    if isinstance(value, int):
        return True, value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped and stripped.isascii() and stripped.isdecimal():
            try:
                return True, int(stripped)
            except ValueError:
                return False, value
        return False, value
    return False, value


def add_outside_hit(entries, name, file, line, title):
    """Add one outside-scope hit to `entries`, the review record's "Outside this PR" list, in place; return True when
    the hit was added and False when that reviewer's entry already held it. The one home of the list's insertion
    policy for the driver's fold (`round_driver._record_outside`) and the abandoned-session writer's recovery:
    one entry per reviewer source name (a new name opens an entry at the end); a sweep entry is never the target and
    its hits are never counted to a reviewer, but they number the new ids (`O-<n>` is 1 + every hit already listed);
    a hit already under that entry (same file, line, title) adds nothing; a reviewer entry with no hit list starts one."""
    target, total = None, 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        hits = entry.get("hits") if isinstance(entry.get("hits"), list) else []
        total += len(hits)
        src = entry.get("source") if isinstance(entry.get("source"), dict) else {}
        if src.get("kind") == "sweep":
            continue
        if src.get("name") == name and target is None:
            target = entry
    hit = {"id": "O-%d" % (total + 1), "file": file, "line": line, "title": title}
    if target is None:
        entries.append({"source": {"kind": "reviewer", "name": name, "sweepId": None}, "hits": [hit]})
        return True
    if not isinstance(target.get("hits"), list):
        target["hits"] = []
    if any(isinstance(h, dict) and (h.get("file"), h.get("line"), h.get("title")) == (file, line, title)
           for h in target["hits"]):
        return False
    target["hits"].append(hit)
    return True


SWEEP_SOURCE_NAME = "searchers"  # the source name of a repository sweep's outside entry
SWEEP_OF_FIELD = "sweepOf"  # marks a finding a repository sweep found: {"sweepId", "findingKey"} of the finding it searched for


def add_sweep_hit(entries, sweep_id, name, file, line, title):
    """Add one outside-scope hit of a repository sweep to `entries`, the review record's "Outside this PR" list, in
    place; return True when the hit was added and False when that sweep's entry already held it. The one home of a
    sweep entry's insertion policy for the driver's fold and the abandoned-session writer's recovery: one entry
    `{"source": {"kind": "sweep", "name": name, "sweepId": sweep_id}, "hits": [...]}` per sweep id (opened at the end
    when none exists; a reviewer entry is never the target, even when it shares the name); the new id is
    `O-<1 + every hit already listed on every entry>`; a hit already under that entry (same file, line, title) adds
    nothing; an entry with no hit list starts one."""
    target, total = None, 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        hits = entry.get("hits") if isinstance(entry.get("hits"), list) else []
        total += len(hits)
        src = entry.get("source") if isinstance(entry.get("source"), dict) else {}
        if src.get("kind") == "sweep" and src.get("sweepId") == sweep_id and target is None:
            target = entry
    hit = {"id": "O-%d" % (total + 1), "file": file, "line": line, "title": title}
    if target is None:
        entries.append({"source": {"kind": "sweep", "name": name, "sweepId": sweep_id}, "hits": [hit]})
        return True
    if not isinstance(target.get("hits"), list):
        target["hits"] = []
    if any(isinstance(h, dict) and (h.get("file"), h.get("line"), h.get("title")) == (file, line, title)
           for h in target["hits"]):
        return False
    target["hits"].append(hit)
    return True


def classify_sweep_hits(hits, parent, scope_ok):
    """Sort the hits of every part of one sweep (in part order) into `{"inside": [hit], "outside": [hit], "covered": n,
    "dropped": n}`: the one home of the per-hit steps for the driver's fold and the abandoned-session writer's recovery.
    A hit is dropped when its file is not a non-blank string, its line is not an integer, or it cites the PR body; the
    same place found twice is one hit (the first is kept); a hit at the parent's place or one of its kind of mistake's
    places is covered; any other hit is inside when `scope_ok(hit)` says its line is one the PR touched, else outside."""
    import pr_body_stage  # lazy: pr_body_stage imports modules that import this one
    places = {(parent.get("file"), parent.get("line"))}
    kind = parent.get("kindOfMistake")
    for place in (kind.get("places") if isinstance(kind, dict) and isinstance(kind.get("places"), list) else ()):
        if isinstance(place, dict):
            places.add((place.get("file"), place.get("line")))
    out = {"inside": [], "outside": [], "covered": 0, "dropped": 0}
    seen = set()
    for hit in hits:
        file = hit.get("file") if isinstance(hit, dict) else None
        line = hit.get("line") if isinstance(hit, dict) else None
        # axis: a hit citing the PR body is dropped and counted, never classified — see bite-proof record c4_wo2b_recovery
        if (not (isinstance(file, str) and file.strip()) or isinstance(line, bool) or not isinstance(line, int)
                or file == pr_body_stage.CITATION):
            out["dropped"] += 1
            continue
        # axis: the same place found twice is one hit, the first kept — see bite-proof record c4_wo2b_recovery
        if (file, line) in seen:
            continue
        seen.add((file, line))
        # axis: a hit at the parent's own place or one of its places is covered, neither inside nor outside — see bite-proof record c4_wo2b_recovery
        if (file, line) in places:
            out["covered"] += 1
            continue
        out["inside" if scope_ok(hit) else "outside"].append(hit)
    return out


def sweep_hit_title(hit, parent):
    """The title of a sweep hit: its `what`, stripped, else the kind of the description that was searched for."""
    what = hit.get("what") if isinstance(hit, dict) else None
    if isinstance(what, str) and what.strip():
        return what.strip()
    desc = parent.get("searchDescription") if isinstance(parent, dict) else None
    kind = desc.get("kind") if isinstance(desc, dict) else None
    return kind.strip() if isinstance(kind, str) and kind.strip() else "repository sweep hit"


def sweep_hit_finding(hit, sweep, parent):
    """The finding a repository sweep's hit on a touched line becomes: the parent's severity and consequence, the
    parent's description kind as its kind of mistake (no other places, no description of its own), and the mark of the
    sweep and finding it came from. It carries no `findingKey`, so its identity is the one `finding_identity_key`
    mints from its content. The one home of the shape for the driver's fold and the abandoned-session writer."""
    desc = parent.get("searchDescription") if isinstance(parent.get("searchDescription"), dict) else {}
    kind = desc.get("kind").strip() if isinstance(desc.get("kind"), str) else ""
    what = hit.get("what").strip() if isinstance(hit.get("what"), str) else ""
    title = sweep_hit_title(hit, parent)
    out = {
        "title": title,
        "file": hit.get("file"),
        "line": hit.get("line"),
        "severity": parent.get("severity"),
        "body": "Found by repository sweep %s for the confirmed finding \"%s\" (%s:%s): %s" % (
            sweep.get("sweepId"), parent.get("title"), parent.get("file"), parent.get("line"), what or title),
        "kindOfMistake": {"kind": kind, "places": []},
        "searchDescription": None,
        SWEEP_OF_FIELD: {"sweepId": sweep.get("sweepId"), FINDING_KEY_FIELD: finding_identity_key(parent)},
    }
    for field in ("consequence", "consequenceKind"):
        if field in parent:
            out[field] = parent[field]
    if parent.get("tradeoff"):
        # An owner's-choice parent holds its copies for the owner too: the hold keys on this flag.
        out["tradeoff"] = True
    return out


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


def runner_channel_vendor(vendor):
    """True when ``vendor`` is a registered non-claude engine (codex/cursor today).

    Unknown vendors fail closed to host transport — they cannot land on the engine stdout branch."""
    if not isinstance(vendor, str) or not vendor.strip():
        return False
    v = vendor.strip()
    if v == "claude":
        return False
    return v in model_registry.vendors()
