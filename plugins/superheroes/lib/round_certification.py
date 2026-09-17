#!/usr/bin/env python3
"""Certification receipt writer — journal on disk as sole input, no driver imports (#1271 C12)."""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re

import model_registry
import record_paths
import receipt_disclosures
import seat_map_receipts
import session_contract
import session_mode
import version_skew

STATE_FILE = session_contract.STATE_FILE
JOURNAL_FILE = session_contract.JOURNAL_FILE
JOURNAL_FAULT_FILE = session_contract.JOURNAL_FAULT_FILE
META_FILE = session_contract.META_FILE

BASE_GUARD_CHECKED = "checked-stat-bound"
SCHEMA_VERSION = 2
STATE_SCHEMA_VERSION = 5
SUPPORTED_STATE_VERSIONS = (2, 3, 4, 5)

CERTIFIED_VERDICTS = (
    "converged",
    "halted",
    "held",
    "stalled",
    "cannot-certify",
    "capped-with-open-critical",
    "capped-with-open-blocker",
)
ATTESTED_VERDICT = "uncertified-manual"
ALL_VERDICTS = CERTIFIED_VERDICTS + (ATTESTED_VERDICT,)

PROVENANCE_DISPATCH_OBSERVED = "dispatch-observed"
PROVENANCE_HAND_LANDED = "hand-landed"
PROVENANCE_ORCHESTRATOR_FULFILLED = "orchestrator-fulfilled"
SEAT_PROVENANCE = (
    PROVENANCE_DISPATCH_OBSERVED,
    PROVENANCE_HAND_LANDED,
    PROVENANCE_ORCHESTRATOR_FULFILLED,
)
RECEIPT_PROVENANCE = (PROVENANCE_DISPATCH_OBSERVED, PROVENANCE_HAND_LANDED)

EXECUTION_EVIDENCE_READ_VALUES = frozenset(("engaged", "unknown"))
EXECUTION_EVIDENCE_TELEMETRY_VALUES = frozenset(("tool-calls", "none"))
EXECUTION_EVIDENCE_BINDING_FIELDS = (
    "source",
    "runnerNonce",
    "recordDigest",
    "resultDigest",
    "resultKind",
)
EXECUTION_EVIDENCE_OBSERVATION_FIELDS = frozenset(
    ("tokens", "toolCalls", "stdoutBytes", "wallSeconds", "source", "read", "telemetry")
)
HEAD_CONTENT_BLOBS_FILE = "head-content-blobs.json"

REFUSAL_CLASSES = frozenset(
    ("unrun-review", "same-family-seat", "unfetched-findings", "disposition-without-receipt")
)

PANEL_PHASE = session_contract.PANEL_PHASE

SEAT_MISSING_SCHEMA = "seat-missing/1"

RECEIPT_FORM_CERTIFIED = "certified"
VENDOR_SOURCE_DEFAULTED = "defaulted"
ROUND_ENTRY_KEY_FORMS = receipt_disclosures.ROUND_ENTRY_KEY_FORMS
RESUMABLE_DISCLOSURE_CHANNELS = receipt_disclosures.RESUMABLE_DISCLOSURE_CHANNELS
DISCLOSE_ON_PRESENCE = receipt_disclosures.DISCLOSE_ON_PRESENCE
build_degraded_prose = receipt_disclosures.build_degraded_prose
declared_disclosures = receipt_disclosures.declared_disclosures
round_entry_key_allowed = receipt_disclosures.round_entry_key_allowed
receipt_round_disclosures = receipt_disclosures.receipt_round_disclosures
maker_author_family = receipt_disclosures.maker_author_family
storage_key = record_paths.storage_key
store_path = record_paths.store_path
_round_entry_key_allowed = round_entry_key_allowed
_receipt_round_disclosures = receipt_round_disclosures
_declared_disclosures = declared_disclosures


def _certification_shape(state, seats):
    """Hand-landed shape override — tested directly; receipt certificationShape follows driver parity."""
    cert = state.get("certification") or {}
    shape = cert.get("shape")
    hand_landed = any(s.get("provenance") == PROVENANCE_HAND_LANDED for s in seats)
    if hand_landed:
        if shape == "full-panel-confirmed":
            return "audited-chain"
        if isinstance(shape, str) and shape.startswith("full-panel"):
            return "audited-chain"
        if shape is None:
            return "audited-chain"
    if isinstance(shape, str) and shape:
        return shape
    return cert.get("shape")

_DECISION_KEYS = (
    "audit-echo-mismatch",
    "audit-provenance-fail",
    "author-justified-drop",
    "canary-failed",
    "canary-outcome-failed",
    "canary-plant-undetected",
    "canary-unverified",
    "cannot-certify",
    "capped-with-open-blocker",
    "capped-with-open-critical",
    "confirmation-rearm",
    "converged",
    "judgment-fail-closed",
    "judgment-gate",
    "judgment-skip",
    "not-discharged",
    "panel-incomplete-canary-gap",
    "panel-seat-missing",
    "receipt-missing-seat",
    "resume-confirmation",
    "round-ceiling",
    "scoped-finder-skipped",
    "seat-engaged-artifact",
    "seat-map-constraint-violated",
    "seat-vacuous",
    "self-recovery",
    "stall-choice",
    "stall-menu",
    "unknown-surface",
    "verifier-refuted",
    "verify-fail",
    "verify-skip-but-configured",
    "verify-skipped",
    "verify-unresolved",
)

VERDICT_TO_TERMINAL_STATE = {
    "converged": "certified",
    "capped-with-open-critical": "cap",
    "capped-with-open-blocker": "cap",
    "cannot-certify": "cannot-certify",
    "halted": "cannot-certify",
    "held": "cannot-certify",
    "stalled": "cannot-certify",
    ATTESTED_VERDICT: "cannot-certify",
}

_TERMINAL_CAUSE_TABLE = {
    ("converged", "converged"): None,
    ("capped-with-open-critical", "capped-with-open-critical"): {
        "kind": "non-loop",
        "reason": "open-findings",
    },
    ("capped-with-open-blocker", "capped-with-open-blocker"): {
        "kind": "non-loop",
        "reason": "open-findings",
    },
    ("cannot-certify", "cannot-certify"): {"kind": "loop", "reason": "detector"},
    ("halted", "verify-fail"): {"kind": "loop", "reason": "detector"},
    ("halted", "verify-skip-but-configured"): {"kind": "loop", "reason": "detector"},
    ("halted", "verify-unresolved"): {"kind": "loop", "reason": "detector"},
    ("halted", "round-ceiling"): {"kind": "non-loop", "reason": "budget"},
    ("held", "stall-choice"): {"kind": "loop", "reason": "latch"},
    ("stalled", "stall-choice"): {"kind": "loop", "reason": "latch"},
    ("stalled", "stall-menu"): {"kind": "loop", "reason": "latch"},
    (ATTESTED_VERDICT, "cannot-certify"): {"kind": "loop", "reason": "detector"},
    ("cannot-certify", "resume-confirmation"): {"kind": "loop", "reason": "resume"},
    ("cannot-certify", "self-recovery"): {"kind": "loop", "reason": "fixer-cycle"},
}


def certify(session_dir):
    """Return (receipt, refusal) — exactly one non-None."""
    ctx, refusal = _load_context(session_dir)
    if refusal is not None:
        return None, refusal
    for check in (
        check_empty_seat_set,
        check_unfetched_findings,
        check_unrun_review,
        check_same_family_seat,
        check_disposition_without_receipt,
    ):
        refusal = check(ctx)
        if refusal is not None:
            return None, refusal
    verdict = ctx["state"].get("terminal")
    terminal_state, terminal_cause, refusal = _resolve_terminal(verdict, ctx["state"])
    if refusal is not None:
        return None, refusal
    receipt = _build_receipt(ctx, terminal_state, terminal_cause)
    refusal = _validate_receipt_findings(receipt)
    if refusal is not None:
        return None, refusal
    return receipt, None


def _refusal(class_name, artifact, detail, binding_failure=None):
    if class_name not in REFUSAL_CLASSES:
        raise ValueError("invalid refusal class %r" % (class_name,))
    return {
        "class": class_name,
        "artifact": artifact,
        "detail": detail,
        "bindingFailure": binding_failure,
    }


def _load_context(session_dir):
    if not isinstance(session_dir, str) or not session_dir:
        return None, _refusal(
            "unfetched-findings",
            session_dir or "(missing)",
            "session directory path missing or empty",
        )
    if not os.path.isdir(session_dir):
        return None, _refusal(
            "unfetched-findings",
            session_dir,
            "session directory absent or not a directory",
        )
    state_path = os.path.join(session_dir, STATE_FILE)
    if not os.path.exists(state_path):
        return None, _refusal(
            "unfetched-findings",
            STATE_FILE,
            "loop-state.json missing",
        )
    try:
        with open(state_path, encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError) as exc:
        return None, _refusal(
            "unfetched-findings",
            STATE_FILE,
            "loop-state.json unreadable or malformed: %s" % exc,
        )
    if not isinstance(state, dict):
        return None, _refusal(
            "unfetched-findings",
            STATE_FILE,
            "loop-state.json root is not an object",
        )
    journal_path = os.path.join(session_dir, JOURNAL_FILE)
    if not os.path.exists(journal_path):
        return None, _refusal(
            "unfetched-findings",
            JOURNAL_FILE,
            "driver-journal.jsonl missing",
        )
    journal, refusal = _read_jsonl(journal_path, JOURNAL_FILE)
    if refusal is not None:
        return None, refusal
    fault_path = os.path.join(session_dir, JOURNAL_FAULT_FILE)
    if os.path.exists(fault_path):
        _, fault_refusal = _read_jsonl(fault_path, JOURNAL_FAULT_FILE)
        if fault_refusal is not None:
            return None, fault_refusal
        return None, _refusal(
            "unfetched-findings",
            JOURNAL_FAULT_FILE,
            "journal fault marker present — incomplete journal evidence",
        )
    meta = _read_json(os.path.join(session_dir, META_FILE)) or {}
    return {
        "session_dir": session_dir,
        "state": state,
        "journal": journal,
        "meta": meta if isinstance(meta, dict) else {},
    }, None


def _read_jsonl(path, artifact):
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line_number, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError as exc:
                    return None, _refusal(
                        "unfetched-findings",
                        artifact,
                        "line %d is not valid JSON: %s" % (line_number, exc),
                    )
                if not isinstance(row, dict):
                    return None, _refusal(
                        "unfetched-findings",
                        artifact,
                        "line %d is not a JSON object" % line_number,
                    )
                out.append(row)
    except OSError as exc:
        return None, _refusal(
            "unfetched-findings",
            artifact,
            "%s unreadable: %s" % (artifact, exc),
        )
    return out, None


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _canonical_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _payload_sha256(payload):
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _journal_event_slot(event):
    ident = event.get("recordIdentity")
    if not isinstance(ident, dict):
        ident = {}
    ev_seat = event.get("seat") or ident.get("seat")
    ev_phase = event.get("phase") if event.get("phase") is not None else ident.get("phase")
    ev_attempt = event.get("attempt")
    if ev_attempt is None:
        ev_attempt = ident.get("attempt")
    ev_occ = event.get("occurrence", ident.get("occurrence", 0))
    ev_round = event.get("round")
    return ev_seat, ev_phase, ev_attempt, ev_occ, ev_round


def _journal_slot_matches(event, seat, phase, attempt, occurrence=0, rnd=None):
    ev_seat, ev_phase, ev_attempt, ev_occ, ev_round = _journal_event_slot(event)
    return (
        ev_seat == seat
        and ev_phase == phase
        and ev_attempt == attempt
        and ev_occ == occurrence
        and (rnd is None or ev_round == rnd)
    )


def _receipt_version(state):
    version = state.get("schemaVersion")
    if isinstance(version, bool) or not isinstance(version, int):
        return SCHEMA_VERSION
    if version in SUPPORTED_STATE_VERSIONS:
        return version
    return SCHEMA_VERSION


def _seat_family(seat, cfg):
    if not isinstance(cfg, dict):
        return None
    vendor = cfg.get("vendor")
    if not isinstance(vendor, str) or not vendor:
        return None
    tier = cfg.get("tier")
    if not isinstance(tier, str) or not tier:
        tier = "reviewer"
    fam = model_registry.family_for(tier, vendor)
    if fam is not None:
        return fam
    return model_registry.family_for("reviewer", vendor)


def _seat_map_receipts(state):
    receipts = []
    legacy = state.get("seatMap")
    if isinstance(legacy, dict) and legacy:
        receipts.append({"round": "legacy", "map": legacy})
    raw = state.get("seatMapReceipts")
    if isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, dict) and isinstance(entry.get("map"), dict):
                receipts.append(entry)
    return receipts


def _effective_seat_map(state):
    for entry in reversed(_seat_map_receipts(state)):
        seats = entry["map"].get("seats")
        if isinstance(seats, dict) and seats:
            return entry["map"]
    cfg_sm = (state.get("config") or {}).get("seatMap")
    if isinstance(cfg_sm, dict):
        return cfg_sm
    return {}


def _declared_same_family_seats(state):
    """Seats named by upstream same-family degradations — collected unconditionally."""
    seats = []
    for entry in _seat_map_receipts(state):
        smap = entry["map"]
        degradations = smap.get("degradations")
        if not isinstance(degradations, list):
            continue
        for deg in degradations:
            if not isinstance(deg, dict):
                continue
            if deg.get("constraint") != "same-family":
                continue
            seat = deg.get("seat")
            if not isinstance(seat, str) or not seat:
                seat = deg.get("configured")
            if not isinstance(seat, str) or not seat:
                continue
            seats.append(seat)
    return sorted(set(seats))


def _seat_map_artifact(state):
    receipts = _seat_map_receipts(state)
    if receipts:
        rnd = receipts[-1].get("round")
        if isinstance(rnd, str) and rnd:
            return "seatMapReceipts/%s" % rnd
    if isinstance(state.get("seatMap"), dict) and state["seatMap"]:
        return "seatMap"
    cfg_sm = (state.get("config") or {}).get("seatMap")
    if isinstance(cfg_sm, dict) and cfg_sm:
        return "config.seatMap"
    return "seatMapReceipts"


def _additive_same_family_seats(state, author):
    """Undeclared seats whose resolved family matches the maker — registry may only add refusals."""
    declared = set(_declared_same_family_seats(state))
    seat_configs = {}
    for entry in _seat_map_receipts(state):
        smap = entry["map"]
        raw_seats = smap.get("seats")
        if isinstance(raw_seats, dict):
            seat_configs.update(raw_seats)
    seats = []
    for seat, cfg in seat_configs.items():
        if seat in declared:
            continue
        fam = _seat_family(seat, cfg)
        if fam is None or fam == author:
            seats.append(seat)
    return sorted(set(seats))


def _same_family_seats(state):
    declared = _declared_same_family_seats(state)
    author = maker_author_family(state)
    if not author:
        return declared
    additive = _additive_same_family_seats(state, author)
    return sorted(set(declared + additive))


def _journal_recorded_identities(journal):
    latest = {}
    for event in journal:
        if event.get("outcome") != "recorded":
            continue
        ident = event.get("recordIdentity")
        if not isinstance(ident, dict):
            seat = event.get("seat")
            if not isinstance(seat, str) or not seat:
                continue
            ident = {
                "phase": event.get("phase"),
                "seat": seat,
                "occurrence": event.get("occurrence", 0),
                "attempt": event.get("attempt"),
            }
        rnd = event.get("round")
        key = (
            rnd,
            ident.get("phase"),
            ident.get("seat"),
            ident.get("occurrence", 0),
            ident.get("attempt"),
        )
        if key[0] is None or key[1] is None or key[2] is None or key[4] is None:
            continue
        latest[key] = {
            "event": event,
            "ident": ident,
            "payloadSha256": event.get("payloadSha256"),
            "provenance": event.get("provenance"),
            "executionEvidence": event.get("executionEvidence"),
        }
    return latest


def _journal_open_seats(journal):
    """Seats opened by advance/next for a dispatch phase but never recorded — incomplete journal."""
    opened = {}
    closed = set()
    for event in journal:
        cmd = event.get("cmd")
        outcome = event.get("outcome")
        phase = event.get("phase")
        rnd = event.get("round")
        attempt = event.get("attempt")
        seat = event.get("seat")
        if cmd in ("next", "advance") and outcome in ("emitted", "pending", "opened"):
            roster = event.get("roster") or event.get("seats")
            if isinstance(roster, list):
                for item in roster:
                    if isinstance(item, dict):
                        sk = item.get("seat") or item.get("seatKey")
                        occ = item.get("occurrence", 0)
                    else:
                        sk, occ = item, 0
                    if isinstance(sk, str) and sk:
                        opened[(phase, rnd, attempt, sk, occ)] = event
            elif isinstance(seat, str) and seat:
                opened[(phase, rnd, attempt, seat, event.get("occurrence", 0))] = event
        if outcome == "recorded" and isinstance(seat, str):
            closed.add((phase, rnd, attempt, seat, event.get("occurrence", 0)))
        ident = event.get("recordIdentity")
        if outcome == "recorded" and isinstance(ident, dict):
            closed.add(
                (
                    ident.get("phase"),
                    event.get("round"),
                    ident.get("attempt"),
                    ident.get("seat"),
                    ident.get("occurrence", 0),
                )
            )
    unclosed = []
    for key, event in opened.items():
        if key not in closed:
            unclosed.append((key, event))
    return unclosed


def _certified_head_sha(ctx):
    meta = ctx.get("meta") or {}
    head = meta.get("headSha")
    if isinstance(head, str) and head:
        return head
    cfg = (ctx.get("state") or {}).get("config") or {}
    head = cfg.get("headSha")
    if isinstance(head, str) and head:
        return head
    return None


def _load_envelope(session_dir, rnd, phase, seat, attempt, occurrence=0):
    path = store_path(session_dir, rnd, phase, storage_key(seat, occurrence), attempt)
    if not os.path.exists(path):
        return None, path
    obj = _read_json(path)
    if not isinstance(obj, dict):
        return None, path
    return obj, path


def _journal_observation_for_seat(
    journal, seat, phase=None, attempt=None, occurrence=0, rnd=None
):
    for event in reversed(journal):
        if event.get("outcome") != "recorded":
            continue
        if attempt is None:
            continue
        if not _journal_slot_matches(event, seat, phase, attempt, occurrence, rnd):
            continue
        obs = event.get("executionEvidence")
        if isinstance(obs, dict):
            return obs
    return None


def _execution_evidence_source_is_caller_supplied(source):
    if not isinstance(source, str) or not source:
        return True
    if source.startswith(("/", "./", "../")):
        return True
    if "/" in source or "\\" in source:
        return True
    if source.endswith(".json"):
        return True
    return False


def _journal_recorded_runner_nonces_for_slot(
    journal, seat, phase, attempt, occurrence=0, rnd=None
):
    """Runner nonces recorded for one dispatch slot — not session-wide."""
    nonces = set()
    for event in journal:
        if not isinstance(event, dict):
            continue
        if event.get("outcome") != "recorded":
            continue
        if not _journal_slot_matches(event, seat, phase, attempt, occurrence, rnd):
            continue
        evidence = event.get("executionEvidence")
        if isinstance(evidence, dict):
            nonce = evidence.get("runnerNonce")
            if isinstance(nonce, str) and nonce:
                nonces.add(nonce)
        nonce = event.get("runnerNonce")
        if isinstance(nonce, str) and nonce:
            nonces.add(nonce)
    return nonces


def _journal_execution_binding(journal, seat, phase, attempt, occurrence=0, rnd=None):
    for event in reversed(journal):
        if event.get("outcome") != "recorded":
            continue
        if not _journal_slot_matches(event, seat, phase, attempt, occurrence, rnd):
            continue
        binding = {}
        evidence = event.get("executionEvidence")
        if isinstance(evidence, dict) and evidence.get("runnerNonce"):
            for field in EXECUTION_EVIDENCE_BINDING_FIELDS:
                val = evidence.get(field)
                if isinstance(val, str) and val:
                    binding[field] = val
        for field in EXECUTION_EVIDENCE_BINDING_FIELDS:
            val = event.get(field)
            if isinstance(val, str) and val and field not in binding:
                binding[field] = val
        if binding.get("runnerNonce"):
            return binding
    return None


def _execution_binding_matches_journal(evidence, journal_binding, recorded_nonces):
    if not isinstance(evidence, dict):
        return False, "execution-evidence-absent"
    source = evidence.get("source")
    if _execution_evidence_source_is_caller_supplied(source):
        return False, "execution-evidence-caller-supplied"
    for field in EXECUTION_EVIDENCE_BINDING_FIELDS:
        val = evidence.get(field)
        if not isinstance(val, str) or not val:
            return False, "execution-evidence-binding-incomplete"
    if journal_binding is None:
        return False, "execution-evidence-dispatch-unrecorded"
    runner_nonce = evidence.get("runnerNonce")
    if runner_nonce not in recorded_nonces:
        return False, "execution-evidence-dispatch-unrecorded"
    for field in EXECUTION_EVIDENCE_BINDING_FIELDS:
        if evidence.get(field) != journal_binding.get(field):
            return False, "execution-evidence-binding-mismatch"
    return True, None


def _execution_evidence_read_value(evidence):
    if not isinstance(evidence, dict):
        return None
    observation = evidence.get("observation")
    if isinstance(observation, dict):
        return observation.get("read")
    return evidence.get("read")


def _observation_qualifies(obs, certified_head, cited_head, journal_binding=None, recorded_nonces=None):
    if not isinstance(obs, dict):
        return False, "execution-evidence-absent"
    read = _execution_evidence_read_value(obs)
    if read not in EXECUTION_EVIDENCE_READ_VALUES:
        return False, "execution-evidence-read-invalid"
    if read != "engaged":
        return False, "execution-evidence-not-engaged"
    observation = obs.get("observation")
    if isinstance(observation, dict):
        extra_obs = set(observation.keys()) - EXECUTION_EVIDENCE_OBSERVATION_FIELDS
        if extra_obs:
            return False, "execution-evidence-unknown-field"
        if set(observation.keys()) != EXECUTION_EVIDENCE_OBSERVATION_FIELDS:
            return False, "execution-evidence-malformed"
    if cited_head and certified_head and cited_head != certified_head:
        return False, "execution-evidence-stale-head"
    ok, binding_failure = _execution_binding_matches_journal(
        obs, journal_binding, recorded_nonces or set()
    )
    if not ok:
        return False, binding_failure
    return True, None


def _hand_landed_evidence_qualifies(
    envelope, certified_head, journal_binding=None, recorded_nonces=None
):
    evidence = envelope.get("executionEvidence") if isinstance(envelope, dict) else None
    if not isinstance(evidence, dict):
        return False, "execution-evidence-absent"
    ok, binding_failure = _execution_binding_matches_journal(
        evidence, journal_binding, recorded_nonces or set()
    )
    if not ok:
        return False, binding_failure
    cited = envelope.get("headSha") or evidence.get("headSha")
    if cited and certified_head and cited != certified_head:
        return False, "execution-evidence-stale-head"
    return True, None


def _read_head_content_blobs(session_dir):
    path = os.path.join(session_dir, HEAD_CONTENT_BLOBS_FILE)
    if not os.path.exists(path):
        return None, None
    try:
        with open(path, encoding="utf-8") as fh:
            blobs = json.load(fh)
    except (OSError, ValueError) as exc:
        return None, "fix-content-unreadable: %s" % exc
    if not isinstance(blobs, dict):
        return None, "fix-content-unreadable: root is not an object"
    return blobs, None


def _fix_still_present_at_head(ctx, finding, receipt):
    fid = finding.get("id") or finding.get("title") or "finding"
    path = finding.get("file")
    if not isinstance(path, str) or not path:
        return _refusal(
            "disposition-without-receipt",
            fid,
            "fixed disposition lacks file path for head-content verification",
            binding_failure="fix-content-missing",
        )
    head = receipt.get("headSha") or _certified_head_sha(ctx)
    if not isinstance(head, str) or not head:
        return _refusal(
            "disposition-without-receipt",
            fid,
            "fixed disposition lacks certified head for content verification",
            binding_failure="fix-content-missing",
        )
    blobs, err = _read_head_content_blobs(ctx["session_dir"])
    if err is not None:
        return _refusal(
            "disposition-without-receipt",
            fid,
            "fixed disposition fix-content read failed on certified head",
            binding_failure="fix-content-unreadable",
        )
    if blobs is None:
        return _refusal(
            "disposition-without-receipt",
            fid,
            "fixed disposition lacks head-content evidence on certified head",
            binding_failure="fix-content-missing",
        )
    if blobs.get("schema") != "head-content-blobs/2":
        return _refusal(
            "disposition-without-receipt",
            fid,
            "fixed disposition head-content schema is not supported",
            binding_failure="fix-content-schema-unsupported",
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
        return _refusal(
            "disposition-without-receipt",
            fid,
            "fixed disposition fix is not present in content at the certified head",
            binding_failure="fix-content-missing",
        )
    row = matching[-1]
    if row.get("readError") is not None or not row.get("contentDigest"):
        return _refusal(
            "disposition-without-receipt",
            fid,
            "fixed disposition fix-content read failed on certified head",
            binding_failure="fix-content-unreadable",
        )
    content_digest = row["contentDigest"]
    files = blobs.get("files")
    file_b64 = files.get(path) if isinstance(files, dict) else None
    if file_b64 is None:
        return _refusal(
            "disposition-without-receipt",
            fid,
            "fixed disposition fix-content read failed on certified head",
            binding_failure="fix-content-unreadable",
        )
    try:
        raw = base64.b64decode(file_b64, validate=True)
    except (binascii.Error, ValueError):
        return _refusal(
            "disposition-without-receipt",
            fid,
            "fixed disposition fix-content read failed on certified head",
            binding_failure="fix-content-unreadable",
        )
    if hashlib.sha256(raw).hexdigest() != content_digest:
        return _refusal(
            "disposition-without-receipt",
            fid,
            "fixed disposition fix-content read failed on certified head",
            binding_failure="fix-content-unreadable",
        )
    fix_content_digest = receipt.get("fixContentDigest")
    if not isinstance(fix_content_digest, str) or not fix_content_digest:
        return _refusal(
            "disposition-without-receipt",
            fid,
            "fixed disposition fix is not present in content at the certified head",
            binding_failure="fix-content-reverted",
        )
    if content_digest != fix_content_digest:
        return _refusal(
            "disposition-without-receipt",
            fid,
            "fixed disposition fix is not present in content at the certified head",
            binding_failure="fix-content-reverted",
        )
    return None


def check_unrun_review(ctx):
    state = ctx["state"]
    journal = ctx["journal"]
    session_dir = ctx["session_dir"]
    certified_head = _certified_head_sha(ctx)
    seats = _collect_seats(ctx)
    for seat_entry in seats:
        seat = seat_entry["seat"]
        provenance = seat_entry.get("provenance")
        phase = seat_entry.get("phase")
        attempt = seat_entry["attempt"]
        occurrence = seat_entry.get("occurrence", 0)
        rnd = seat_entry["round"]
        slot_nonces = _journal_recorded_runner_nonces_for_slot(
            journal, seat, phase, attempt, occurrence, rnd
        )
        if provenance not in RECEIPT_PROVENANCE:
            if provenance == PROVENANCE_ORCHESTRATOR_FULFILLED:
                return _refusal(
                    "unfetched-findings",
                    seat,
                    "seat provenance orchestrator-fulfilled is not mappable on the receipt",
                )
            return _refusal(
                "unfetched-findings",
                seat,
                "seat provenance %r is not mappable" % (provenance,),
            )
        if provenance == PROVENANCE_DISPATCH_OBSERVED:
            obs = _journal_observation_for_seat(
                journal, seat, phase, attempt, occurrence, rnd
            )
            journal_binding = _journal_execution_binding(
                journal,
                seat,
                phase,
                attempt,
                occurrence,
                rnd,
            )
            ok, binding = _observation_qualifies(
                obs,
                certified_head,
                seat_entry.get("citedHead"),
                journal_binding=journal_binding,
                recorded_nonces=slot_nonces,
            )
            if not ok:
                return _refusal(
                    "unrun-review",
                    seat,
                    "dispatch-observed seat lacks qualifying execution telemetry",
                    binding_failure=binding,
                )
        elif provenance == PROVENANCE_HAND_LANDED:
            env, path = _load_envelope(
                session_dir,
                seat_entry["round"],
                seat_entry["phase"],
                seat,
                seat_entry["attempt"],
                seat_entry.get("occurrence", 0),
            )
            if env is None:
                return _refusal(
                    "unfetched-findings",
                    path,
                    "hand-landed envelope missing or unreadable",
                )
            journal_binding = _journal_execution_binding(
                journal,
                seat,
                phase,
                attempt,
                occurrence,
                rnd,
            )
            ok, binding = _hand_landed_evidence_qualifies(
                env,
                certified_head,
                journal_binding=journal_binding,
                recorded_nonces=slot_nonces,
            )
            if not ok:
                return _refusal(
                    "unrun-review",
                    path,
                    "hand-landed seat lacks qualifying execution-evidence binding",
                    binding_failure=binding,
                )
    return None


def check_same_family_seat(ctx):
    state = ctx["state"]
    author = maker_author_family(state)
    if not author:
        cfg = state.get("config") or {}
        vendor = cfg.get("fixerVendor")
        return _refusal(
            "unfetched-findings",
            _seat_map_artifact(state),
            "maker family could not be resolved for fixerVendor %r" % (vendor,),
        )
    # Refusal set is deliberately broader than disclosure: upstream same-family
    # declarations are authoritative; registry lookup may add refusals, never remove.
    # Disclosure uses seat_map_receipts.same_family_seats; this path uses declared+additive.
    seats = _same_family_seats(state)
    if seats:
        return _refusal(
            "same-family-seat",
            seats[0],
            "seat(s) %s filled with the maker model family"
            % ", ".join(seats),
        )
    return None


def check_unfetched_findings(ctx):
    session_dir = ctx["session_dir"]
    journal = ctx["journal"]
    unclosed = _journal_open_seats(journal)
    if unclosed:
        key, event = unclosed[0]
        seat = key[3]
        return _refusal(
            "unfetched-findings",
            seat,
            "seat opened in journal but never closed with a recorded result",
        )
    recorded = _journal_recorded_identities(journal)
    for seat_entry in _collect_seats(ctx):
        key = (
            seat_entry["round"],
            seat_entry["phase"],
            seat_entry["seat"],
            seat_entry.get("occurrence", 0),
            seat_entry["attempt"],
        )
        ident = recorded.get(key)
        env, path = _load_envelope(
            session_dir,
            seat_entry["round"],
            seat_entry["phase"],
            seat_entry["seat"],
            seat_entry["attempt"],
            seat_entry.get("occurrence", 0),
        )
        if env is None:
            return _refusal(
                "unfetched-findings",
                path,
                "seat result never landed on disk",
            )
        if ident is None:
            return _refusal(
                "unfetched-findings",
                path,
                "seat result on disk is not reconciled with the journal",
            )
        if env.get("schema") == SEAT_MISSING_SCHEMA:
            continue
        declared_env = env.get("payloadSha256")
        declared_journal = ident.get("payloadSha256")
        if not isinstance(declared_env, str) or not declared_env:
            return _refusal(
                "unfetched-findings",
                path,
                "landed envelope lacks payloadSha256 integrity field",
            )
        if not isinstance(declared_journal, str) or not declared_journal:
            return _refusal(
                "unfetched-findings",
                path,
                "journal record lacks payloadSha256 integrity field",
            )
        try:
            computed = _payload_sha256(env.get("payload"))
        except (TypeError, ValueError):
            return _refusal(
                "unfetched-findings",
                path,
                "landed envelope payload is not hashable for integrity reconciliation",
            )
        if computed != declared_env:
            return _refusal(
                "unfetched-findings",
                path,
                "landed envelope payloadSha256 does not match envelope content",
                binding_failure="journal-envelope-mismatch",
            )
        if computed != declared_journal:
            return _refusal(
                "unfetched-findings",
                path,
                "journal payload hash disagrees with landed envelope content",
                binding_failure="journal-envelope-mismatch",
            )
    return None


def check_empty_seat_set(ctx):
    if not _collect_seats(ctx):
        return _refusal(
            "unrun-review",
            JOURNAL_FILE,
            "no recorded seat results — certification over zero seats is not a certification",
        )
    return None


def check_disposition_without_receipt(ctx):
    state = ctx["state"]
    cfg = state.get("config") or {}
    base_guard = cfg.get("baseGuard")
    if base_guard != BASE_GUARD_CHECKED:
        return _refusal(
            "disposition-without-receipt",
            STATE_FILE,
            "base guard did not run (baseGuard=%r)" % (base_guard,),
            binding_failure="base-guard-not-checked",
        )
    certified_head = _certified_head_sha(ctx)
    disclosures = []
    for finding in state.get("findings") or []:
        if not isinstance(finding, dict):
            continue
        fid = finding.get("id") or finding.get("title") or "finding"
        severity = finding.get("severity")
        disposition = finding.get("disposition")
        if disposition is None:
            return _refusal(
                "disposition-without-receipt",
                fid,
                "finding has no disposition recorded",
            )
        if disposition == "fixed":
            receipt = finding.get("dispositionReceipt")
            if not isinstance(receipt, dict):
                return _refusal(
                    "disposition-without-receipt",
                    fid,
                    "fixed disposition lacks verification receipt on certified head",
                )
            head = receipt.get("headSha")
            if certified_head and head != certified_head:
                return _refusal(
                    "disposition-without-receipt",
                    fid,
                    "fixed disposition verification receipt is not on the certified head",
                    binding_failure="verify-not-on-head",
                )
            refusal = _fix_still_present_at_head(ctx, finding, receipt)
            if refusal is not None:
                return refusal
        elif disposition == "refuted":
            reason = finding.get("dispositionReceipt") or finding.get("refutedReason")
            if not isinstance(reason, (str, dict)) or (
                isinstance(reason, str) and not reason.strip()
            ):
                return _refusal(
                    "disposition-without-receipt",
                    fid,
                    "refuted disposition lacks recorded reason",
                )
        elif disposition == "out-of-scope":
            if _severity_rank(severity) == _severity_rank("Critical"):
                return _refusal(
                    "disposition-without-receipt",
                    fid,
                    "Critical finding may not take out-of-scope disposition",
                )
            follow_up = finding.get("followUp") or finding.get("dispositionReceipt")
            if not isinstance(follow_up, dict):
                return _refusal(
                    "disposition-without-receipt",
                    fid,
                    "out-of-scope disposition lacks named follow-up item",
                )
            trigger = follow_up.get("revisitTrigger")
            if not isinstance(trigger, str) or not trigger.strip():
                return _refusal(
                    "disposition-without-receipt",
                    fid,
                    "out-of-scope follow-up lacks revisit trigger",
                    binding_failure="missing-revisit-trigger",
                )
            if "documented" in trigger.lower():
                return _refusal(
                    "disposition-without-receipt",
                    fid,
                    "revisit trigger must not be the word documented",
                )
            closure = follow_up.get("classClosure")
            if not isinstance(closure, str) or not closure.strip():
                return _refusal(
                    "disposition-without-receipt",
                    fid,
                    "out-of-scope follow-up lacks class-closure line",
                    binding_failure="missing-class-closure",
                )
            if _severity_rank(severity) == _severity_rank("Important"):
                disclosures.append(
                    {
                        "id": finding.get("id"),
                        "title": finding.get("title"),
                        "severity": severity,
                        "reason": finding.get("outOfScopeReason"),
                    }
                )
        else:
            return _refusal(
                "disposition-without-receipt",
                fid,
                "unknown disposition %r" % (disposition,),
            )
    ctx["important_disclosures"] = disclosures
    return None


def _severity_rank(severity):
    order = {"Critical": 0, "Important": 1, "Minor": 2, "Nit": 3}
    if isinstance(severity, str):
        for key, rank in order.items():
            if severity.lower() == key.lower():
                return rank
    return 99


def _collect_seats(ctx):
    state = ctx["state"]
    journal = ctx["journal"]
    seats = []
    seen = set()
    for event in journal:
        if event.get("outcome") != "recorded":
            continue
        seat = event.get("seat")
        phase = event.get("phase")
        rnd = event.get("round")
        attempt = event.get("attempt")
        provenance = event.get("provenance")
        if not isinstance(seat, str) or not seat:
            ident = event.get("recordIdentity")
            if isinstance(ident, dict):
                seat = ident.get("seat")
                phase = ident.get("phase", phase)
                attempt = ident.get("attempt", attempt)
                provenance = provenance or event.get("provenance")
        if not isinstance(seat, str) or not seat:
            continue
        occurrence = event.get("occurrence", 0)
        key = (phase, rnd, attempt, seat, occurrence)
        if key in seen:
            continue
        seen.add(key)
        cited_head = event.get("headSha") or event.get("citedHead")
        seats.append(
            {
                "seat": seat,
                "phase": phase,
                "round": rnd,
                "attempt": attempt,
                "occurrence": occurrence,
                "provenance": provenance,
                "citedHead": cited_head,
            }
        )
    return seats


def _terminal_decision_key(state):
    decisions = state.get("decisions") or []
    for entry in reversed(decisions):
        if isinstance(entry, dict):
            kind = entry.get("kind")
            if isinstance(kind, str) and kind in _DECISION_KEYS:
                return kind
    return None


def _resolve_terminal(verdict, state):
    if verdict not in ALL_VERDICTS:
        return None, None, _refusal(
            "unfetched-findings",
            STATE_FILE,
            "terminal verdict %r is not recognized" % (verdict,),
        )
    terminal_state = VERDICT_TO_TERMINAL_STATE.get(verdict)
    if terminal_state is None:
        return None, None, _refusal(
            "unfetched-findings",
            STATE_FILE,
            "verdict %r has no terminal-state mapping" % (verdict,),
        )
    decision_key = _terminal_decision_key(state)
    if terminal_state == "certified":
        if decision_key is None and verdict == "converged":
            decision_key = "converged"
        pair = (verdict, decision_key)
        if pair not in _TERMINAL_CAUSE_TABLE:
            return None, None, _refusal(
                "unfetched-findings",
                STATE_FILE,
                "unlisted terminal cause for verdict=%r decision=%r"
                % (verdict, decision_key),
            )
        if _TERMINAL_CAUSE_TABLE[pair] is not None:
            return None, None, _refusal(
                "unfetched-findings",
                STATE_FILE,
                "certified terminal has unexpected decision key %r" % (decision_key,),
            )
        return terminal_state, None, None
    if decision_key is None:
        return None, None, _refusal(
            "unfetched-findings",
            STATE_FILE,
            "non-certified terminal lacks a terminal decision key",
        )
    pair = (verdict, decision_key)
    if pair not in _TERMINAL_CAUSE_TABLE:
        return None, None, _refusal(
            "unfetched-findings",
            STATE_FILE,
            "unlisted terminal cause for verdict=%r decision=%r"
            % (verdict, decision_key),
        )
    cause_entry = _TERMINAL_CAUSE_TABLE[pair]
    if cause_entry is None:
        return None, None, _refusal(
            "unfetched-findings",
            STATE_FILE,
            "unlisted terminal cause for verdict=%r decision=%r"
            % (verdict, decision_key),
        )
    return terminal_state, dict(cause_entry), None


def _scriptran_summary(journal):
    counts = {}
    invocations = 0
    for event in journal:
        invocations += 1
        key = "%s:%s" % (event.get("cmd"), event.get("phase"))
        counts[key] = counts.get(key, 0) + 1
    return {"invocations": invocations, "byPhase": counts}


def _finding_disposition_proof(finding):
    disposition = finding.get("disposition")
    if disposition == "out-of-scope":
        return finding.get("followUp") or finding.get("dispositionReceipt")
    if disposition == "refuted":
        return finding.get("dispositionReceipt") or finding.get("refutedReason")
    return finding.get("dispositionReceipt")


def _project_finding(finding):
    row = {
        "id": finding.get("id"),
        "file": finding.get("file"),
        "line": finding.get("line"),
        "title": finding.get("title"),
        "severity": finding.get("severity"),
        "verdict": finding.get("verdict"),
        "challenge": finding.get("challenge"),
        "unverified": finding.get("unverified"),
        "disposition": finding.get("disposition"),
    }
    proof = _finding_disposition_proof(finding)
    if proof is not None:
        row["dispositionReceipt"] = proof
    return row


def _validate_receipt_findings(receipt):
    findings = receipt.get("findings")
    if not isinstance(findings, list):
        return _refusal(
            "unfetched-findings",
            STATE_FILE,
            "certified receipt findings must be a list",
        )
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        fid = finding.get("id") or finding.get("title") or "finding"
        disposition = finding.get("disposition")
        if disposition is None:
            return _refusal(
                "unfetched-findings",
                fid,
                "certified receipt finding lacks disposition",
            )
        proof = finding.get("dispositionReceipt")
        if disposition in ("fixed", "refuted"):
            if not isinstance(proof, dict) and not (
                disposition == "refuted" and isinstance(proof, str) and proof.strip()
            ):
                return _refusal(
                    "unfetched-findings",
                    fid,
                    "certified receipt finding lacks disposition proof",
                )
        elif disposition == "out-of-scope":
            if not isinstance(proof, dict):
                return _refusal(
                    "unfetched-findings",
                    fid,
                    "certified receipt finding lacks out-of-scope follow-up proof",
                )
        else:
            return _refusal(
                "unfetched-findings",
                fid,
                "certified receipt finding has unknown disposition %r" % (disposition,),
            )
    return None


def _build_receipt_rounds(state, form):
    rounds = []
    for key in sorted(state.get("rounds") or {}, key=lambda k: int(k) if str(k).isdigit() else 0):
        rec = state["rounds"][key]
        rd = {
            "round": int(key) if str(key).isdigit() else key,
            "kind": rec.get("roundKind"),
            "seatStatus": rec.get("seatStatus"),
            "blockingCount": rec.get("blockingCount"),
            "verifyResult": rec.get("verifyResult"),
            "audits": rec.get("audits"),
            "auditProvenance": rec.get("auditProvenance"),
            "scopedFinder": rec.get("scopedFinder"),
            "headDiffSource": rec.get("headDiffSource"),
            "unverified": rec.get("unverified"),
            "authorJustifiedDrops": rec.get("authorJustifiedDrops"),
            "compileDrops": rec.get("compileDrops"),
            "selfRecovery": rec.get("selfRecovery"),
            "stallChoice": rec.get("stallChoice"),
        }
        if rec.get("lensCoverage") is not None:
            rd["lensCoverage"] = rec.get("lensCoverage")
        if _round_entry_key_allowed("verifyPasses", form, state):
            verify_passes = rec.get("verifyPasses")
            rd["verifyPasses"] = verify_passes if isinstance(verify_passes, list) else []
        disclosures = _receipt_round_disclosures(rec, form, state)
        for chan in RESUMABLE_DISCLOSURE_CHANNELS:
            if chan == "verifyPasses":
                continue
            if chan in disclosures:
                rd[chan] = disclosures[chan]
        rounds.append(rd)
    return rounds



def _build_receipt(ctx, terminal_state, terminal_cause):
    state = ctx["state"]
    journal = ctx["journal"]
    cfg = state.get("config") or {}
    form = RECEIPT_FORM_CERTIFIED
    seats_info = _collect_seats(ctx)
    seat_rows = [
        {
            "seat": s["seat"],
            "phase": s["phase"],
            "round": s["round"],
            "attempt": s["attempt"],
            "provenance": s.get("provenance"),
        }
        for s in seats_info
    ]
    findings = [
        _project_finding(f)
        for f in (state.get("findings") or [])
        if isinstance(f, dict)
    ]
    rounds = _build_receipt_rounds(state, form)
    degraded, skipped_blockers = build_degraded_prose(state, form)
    base = {
        k: cfg.get(k)
        for k in (
            "baseRef",
            "baseBranch",
            "baseFetch",
            "baseRepo",
            "baseRepoCheck",
            "repoRoot",
            "diffBinding",
        )
        if cfg.get(k) is not None
    }
    meta = ctx.get("meta") or {}
    mode_resolved = session_mode.resolve(meta, cfg)
    if mode_resolved["resolved"]:
        base["mode"] = mode_resolved["mode"]
    cert = state.get("certification")
    receipt = {
        "schemaVersion": _receipt_version(state),
        "verdict": state.get("terminal"),
        "certificationShape": _certification_shape(state, seat_rows),
        "certification": cert,
        "rounds": rounds,
        "findings": findings,
        "decisions": list(state.get("decisions") or []),
        "seatMap": seat_map_receipts.emit_receipt_seat_map(state, maker_author_family(state)),
        "scriptRan": _scriptran_summary(journal),
        "degraded": degraded,
        "skippedBlockers": skipped_blockers,
        "baseGuard": cfg.get("baseGuard")
        if cfg.get("baseGuard") == BASE_GUARD_CHECKED
        else "not-checked",
        "terminalState": terminal_state,
        "terminalCause": terminal_cause,
        "seats": seat_rows,
        "disclosures": {"importantOutOfScope": list(ctx.get("important_disclosures") or [])},
        "provenanceLabels": {
            "derived": [
                "schemaVersion",
                "scriptRan",
                "terminalState",
                "terminalCause",
                "seats",
                "disclosures",
                "certificationShape",
            ],
            "makerAuthored": [
                "verdict",
                "certification",
                "findings",
                "decisions",
                "seatMap",
                "rounds",
                "degraded",
                "skippedBlockers",
                "baseGuard",
                "base",
                "policyApplied",
            ],
        },
    }
    if base:
        receipt["base"] = base
    policy_applied = state.get("_policyApplied")
    if isinstance(policy_applied, list) and policy_applied:
        receipt["policyApplied"] = list(policy_applied)
    return receipt


def map_verdict_to_terminal_state(verdict):
    """Totality table 1 — refuse unknown verdicts."""
    if verdict not in ALL_VERDICTS:
        return None
    return VERDICT_TO_TERMINAL_STATE.get(verdict)


def map_terminal_cause(verdict, decision_key):
    """Totality table 2 — refuse unlisted combinations."""
    if verdict not in ALL_VERDICTS:
        return None
    if decision_key not in _DECISION_KEYS:
        return None
    terminal_state = VERDICT_TO_TERMINAL_STATE.get(verdict)
    if terminal_state == "certified":
        if (verdict, decision_key) in _TERMINAL_CAUSE_TABLE:
            return None
        if verdict == "converged" and decision_key == "converged":
            return None
        return None
    return _TERMINAL_CAUSE_TABLE.get((verdict, decision_key))


def map_seat_provenance(provenance):
    """Totality table 3 — refuse unmapped provenance."""
    if provenance in RECEIPT_PROVENANCE:
        return provenance
    if provenance in SEAT_PROVENANCE:
        return None
    return None
