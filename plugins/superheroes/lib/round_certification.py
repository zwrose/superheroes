#!/usr/bin/env python3
"""Certification receipt writer — journal on disk as sole input, no driver imports (#1271 C12)."""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import subprocess

import circuit_breaker
import decision_kinds
import model_registry
import record_paths
import receipt_disclosures
import seat_map_receipts
import session_contract
import session_mode

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
HEAD_CONTENT_BLOBS_FILE = session_contract.HEAD_CONTENT_BLOBS_FILE
HEAD_CONTENT_BLOBS_SCHEMA = session_contract.HEAD_CONTENT_BLOBS_SCHEMA

REFUSAL_CLASSES = frozenset(
    ("unrun-review", "same-family-seat", "unfetched-findings", "disposition-without-receipt")
)

CERTIFICATION_LIVE_CONTENT_FIELDS = (
    "file", "line", "title", "severity", "verdict", "challenge", "unverified", "id",
)
EXECUTION_ONLY_BINDING = session_contract.EXECUTION_ONLY_BINDING

PANEL_PHASE = session_contract.PANEL_PHASE
FIXER_PHASE = session_contract.FIXER_PHASE
AUDITS_PHASE = session_contract.AUDITS_PHASE
P_FIXER = session_contract.FIXER_PHASE
P_AUDITS = session_contract.AUDITS_PHASE

SEAT_MISSING_SCHEMA = session_contract.SEAT_MISSING_SCHEMA
SEAT_RESULT_SCHEMA_V2 = "seat-result/2"
ORDERS_DIRNAME = "orders"

BINDING_FAILURE_EXECUTION_EVIDENCE_HEAD_UNBOUND = "execution-evidence-head-unbound"
BINDING_FAILURE_CERTIFIED_HEAD_UNRESOLVABLE = "certified-head-unresolvable"

RECEIPT_FORM_CERTIFIED = receipt_disclosures.RECEIPT_FORM_CERTIFIED
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
round_dir = record_paths.round_dir
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

_DECISION_KEYS = decision_kinds.DECISION_KINDS

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
        check_seat_independence,
        check_disposition_without_receipt,
        check_evidence_head_bound,
        check_hand_landed_read_engaged,
    ):
        refusal = check(ctx)
        if refusal is not None:
            return None, refusal
    verdict = ctx["state"].get("terminal")
    terminal_state, terminal_cause, refusal = _resolve_terminal(verdict, ctx["state"])
    if refusal is not None:
        return None, refusal
    receipt, build_refusal = _build_receipt(ctx, terminal_state, terminal_cause)
    if build_refusal is not None:
        return None, build_refusal
    refusal = _validate_receipt_findings(receipt)
    if refusal is not None:
        return None, refusal
    refusal = _validate_receipt_additions(receipt)
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


def writer_fault(artifact, detail, binding_failure=None):
    """Driver-facing writer-fault envelope — intentionally outside REFUSAL_CLASSES."""
    return {
        "class": "writer-fault",
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


_finding_identity_key = session_contract.finding_identity_key


def _is_fix_content_receipt(receipt):
    if not isinstance(receipt, dict):
        return False
    return any(
        isinstance(key, str) and key.startswith("fixContent")
        for key in receipt
    )


def _refuted_reason_text(finding):
    reason = finding.get("refutedReason")
    if isinstance(reason, str) and reason.strip():
        return reason
    receipt = finding.get("dispositionReceipt")
    if isinstance(receipt, str) and receipt.strip():
        return receipt
    if isinstance(receipt, dict):
        if _is_fix_content_receipt(receipt):
            return None
        for key in ("reason", "refutedReason", "text"):
            val = receipt.get(key)
            if isinstance(val, str) and val.strip():
                return val
    return None


def _out_of_scope_follow_up(finding):
    follow_up = finding.get("followUp")
    if isinstance(follow_up, dict):
        return follow_up
    receipt = finding.get("dispositionReceipt")
    if isinstance(receipt, dict) and not _is_fix_content_receipt(receipt):
        return receipt
    return None


def _certification_findings_by_key(state):
    """Keyed findings for disposition checks — ledger owner uses ledger + live only."""
    classification = session_contract.disposition_ledger_owner_classification(state)
    if classification == session_contract.DISPOSITION_LEDGER_OWNER_UNRECOGNIZED:
        value = state.get(session_contract.DISPOSITION_LEDGER_OWNER_FIELD)
        return {}, _refusal(
            "disposition-without-receipt",
            STATE_FILE,
            "unrecognized dispositionLedgerOwner value %r" % (value,),
            binding_failure="disposition-ledger-owner-unrecognized",
        )
    by_key = {}
    if classification == session_contract.DISPOSITION_LEDGER_OWNER_RECOGNIZED:
        # axis: ledger-owned reads take disposition family from the ledger only — _records is not a source
        ledger_by_key = {}
        ledger_rows, ledger_fault = session_contract.read_disposition_ledger(state, required=True)
        if ledger_fault is not None:
            return {}, _refusal(
                "disposition-without-receipt",
                STATE_FILE,
                ledger_fault.detail,
                binding_failure=ledger_fault.token,
            )
        branch_rows = list(ledger_rows)
        for finding in state.get("findings") or []:
            if isinstance(finding, dict):
                branch_rows.append(finding)
        collision = session_contract.legacy_key_collision(branch_rows)
        if collision is not None:
            bare_key, minted_key = collision
            if bare_key == minted_key:
                detail = "legacy identity collision at %r" % (bare_key,)
            else:
                detail = "legacy bare key %r collides with minted key %r" % (bare_key, minted_key)
            return {}, _refusal(
                "disposition-without-receipt",
                STATE_FILE,
                detail,
                binding_failure=session_contract.DISPOSITION_LEDGER_LEGACY_KEY_COLLISION_TOKEN,
            )
        for finding in ledger_rows:
            key = _finding_identity_key(finding)
            ledger_by_key[key] = finding
        live_by_key = {}
        for finding in state.get("findings") or []:
            if isinstance(finding, dict):
                key = _finding_identity_key(finding)
                if key:
                    live_by_key[key] = finding
        for key, ledger_entry in ledger_by_key.items():
            merged = {}
            for field in session_contract.DISPOSITION_FAMILY_FIELDS:
                if field in ledger_entry:
                    merged[field] = ledger_entry[field]
            for field in (
                session_contract.FINDING_KEY_FIELD,
                session_contract.RAISED_ROUND_FIELD,
            ):
                if field in ledger_entry:
                    merged[field] = ledger_entry[field]
            live = live_by_key.get(key)
            content_source = live if live is not None else ledger_entry
            for field in CERTIFICATION_LIVE_CONTENT_FIELDS:
                if field in content_source:
                    merged[field] = content_source[field]
            by_key[key] = merged
        for key, live in live_by_key.items():
            if key in by_key:
                continue
            if session_contract.has_disposition_family(live):
                # axis: live disposition without a ledger seat refuses — disposition-without-receipt
                return {}, _refusal(
                    "disposition-without-receipt",
                    key,
                    "live finding disposition has no ledger entry",
                )
            by_key[key] = dict(live)
        return by_key, None
    branch_rows = []
    for _key, finding in session_contract.legacy_disposition_ledger_rows(state):
        branch_rows.append(finding)
    for rec in state.get("_records") or []:
        if not isinstance(rec, dict):
            continue
        for finding in rec.get("findings") or []:
            if isinstance(finding, dict):
                branch_rows.append(finding)
    for finding in state.get("findings") or []:
        if isinstance(finding, dict):
            branch_rows.append(finding)
    collision = session_contract.legacy_key_collision(branch_rows)
    if collision is not None:
        bare_key, minted_key = collision
        if bare_key == minted_key:
            detail = "legacy identity collision at %r" % (bare_key,)
        else:
            detail = "legacy bare key %r collides with minted key %r" % (bare_key, minted_key)
        return {}, _refusal(
            "disposition-without-receipt",
            STATE_FILE,
            detail,
            binding_failure=session_contract.DISPOSITION_LEDGER_LEGACY_KEY_COLLISION_TOKEN,
        )
    for key, finding in session_contract.legacy_disposition_ledger_rows(state):
        by_key[key] = finding
    for rec in state.get("_records") or []:
        if not isinstance(rec, dict):
            continue
        for finding in rec.get("findings") or []:
            if not isinstance(finding, dict):
                continue
            key = _finding_identity_key(finding)
            if key:
                by_key[key] = finding
    for finding in state.get("findings") or []:
        if isinstance(finding, dict):
            key = _finding_identity_key(finding)
            if key:
                by_key[key] = finding
    return by_key, None


def _resolve_merged_into_entry(finding, by_key):
    return session_contract.resolve_merged_into_entry(finding, by_key)


def _effective_certification_finding(finding, by_key):
    """Project a merged-away member through its representative; keep member identity."""
    if not isinstance(finding, dict):
        return finding
    if not finding.get(session_contract.MERGED_INTO_FIELD):
        return finding
    resolved = _resolve_merged_into_entry(finding, by_key)
    if resolved is None:
        return finding
    effective = dict(finding)
    for field in session_contract.DISPOSITION_FAMILY_FIELDS:
        if field == session_contract.MERGED_INTO_FIELD:
            continue
        if field in resolved:
            effective[field] = resolved[field]
        else:
            effective.pop(field, None)
    return effective


def _resolve_repo_head_sha(ctx):
    meta = ctx.get("meta") or {}
    cfg = (ctx.get("state") or {}).get("config") or {}
    repo_root = meta.get("repoRoot") or cfg.get("repoRoot")
    if not isinstance(repo_root, str) or not repo_root:
        return None
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    head = proc.stdout.strip()
    return head if head else None


def _run_kind_refusal_detail(phase, found_kind):
    expected = "write" if phase == P_FIXER else "review"
    return "phase %r requires runKind %r (found %r)" % (phase, expected, found_kind)


def _dispatch_run_kind_qualifies(obs, phase):
    if not isinstance(obs, dict):
        return False, None
    expected = "write" if phase == P_FIXER else "review"
    run_kind = obs.get("runKind")
    return (isinstance(run_kind, str) and run_kind == expected), run_kind


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


def _supports_nonblocking_disclosure(state):
    """Non-blocking Minor/Nit survivors ride the state schema v5 bump (C13 recorded-version boundary)."""
    return _receipt_version(state) >= STATE_SCHEMA_VERSION


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


_seat_map_receipts = seat_map_receipts.receipts


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
            "casToken": event.get("casToken"),
            "provenance": event.get("provenance"),
            "executionEvidence": event.get("executionEvidence"),
        }
    return latest


def _orders_manifest_path(session_dir, rnd, phase, attempt):
    return os.path.join(round_dir(session_dir, rnd), ORDERS_DIRNAME, phase,
                        "manifest.a%d.json" % attempt)


def _verified_orders_manifest(session_dir, event):
    """Return (manifest, None) when hash-authenticated, or (None, refusal) when unusable."""
    manifest_sha = event.get("manifestSha256")
    phase = event.get("phase")
    rnd = event.get("round")
    attempt = event.get("attempt")

    def _manifest_artifact():
        if phase is not None and rnd is not None and attempt is not None:
            return _orders_manifest_path(session_dir, rnd, phase, attempt)
        return JOURNAL_FILE

    if not isinstance(manifest_sha, str) or not manifest_sha:
        return None, _refusal(
            "unfetched-findings",
            _manifest_artifact(),
            "orders-emitted event lacks manifestSha256 integrity field",
        )
    if phase is None or rnd is None or attempt is None:
        return None, _refusal(
            "unfetched-findings",
            JOURNAL_FILE,
            "orders-emitted event lacks round binding fields",
        )
    manifest_path = _orders_manifest_path(session_dir, rnd, phase, attempt)
    manifest = _read_json(manifest_path)
    if not isinstance(manifest, dict):
        return None, _refusal(
            "unfetched-findings",
            manifest_path,
            "orders manifest unreadable or malformed",
        )
    computed_sha = session_contract.sha256_text(session_contract.canonical(manifest))
    if computed_sha != manifest_sha:
        return None, _refusal(
            "unfetched-findings",
            manifest_path,
            "orders manifest sha256 does not match event manifestSha256",
        )
    seats = manifest.get("seats")
    if not isinstance(seats, dict):
        return None, _refusal(
            "unfetched-findings",
            manifest_path,
            "orders manifest seats field is not an object",
        )
    return manifest, None


def _orders_emitted_roster_or_refusal(session_dir, event):
    """Return (roster, None) when authenticated, or (None, refusal) when unusable."""
    manifest, refusal = _verified_orders_manifest(session_dir, event)
    if refusal is not None:
        return None, refusal
    manifest_path = _orders_manifest_path(
        session_dir, event.get("round"), event.get("phase"), event.get("attempt"))
    seats = manifest.get("seats")
    roster = []
    for seat_key, entry in seats.items():
        if not isinstance(entry, dict):
            return None, _refusal(
                "unfetched-findings",
                manifest_path,
                "orders manifest seat entry '%s' is not an object" % seat_key,
            )
        seat = entry.get("seat")
        if not isinstance(seat, str) or not seat:
            return None, _refusal(
                "unfetched-findings",
                manifest_path,
                "orders manifest seat entry '%s' has unusable seat field" % seat_key,
            )
        if "occurrence" in entry:
            occurrence = entry["occurrence"]
            if (isinstance(occurrence, bool) or not isinstance(occurrence, int)
                    or occurrence < 0):
                return None, _refusal(
                    "unfetched-findings",
                    manifest_path,
                    "orders manifest seat entry '%s' has unusable occurrence"
                    % seat_key,
                )
        else:
            occurrence = 0
        roster.append((seat, occurrence))
    return roster, None


def _roster_from_orders_emitted(session_dir, event):
    roster, refusal = _orders_emitted_roster_or_refusal(session_dir, event)
    if refusal is not None:
        return None
    return roster


def _journal_open_seats(journal, session_dir=None):
    """Seats opened by advance/next for a dispatch phase but never recorded — incomplete journal.

    Returns (unclosed, refusal). refusal is set when an orders-emitted roster cannot be
    authenticated.
    """
    opened = {}
    closed = set()
    superseded = set()
    for event in journal:
        cmd = event.get("cmd")
        outcome = event.get("outcome")
        phase = event.get("phase")
        rnd = event.get("round")
        attempt = event.get("attempt")
        seat = event.get("seat")
        if (cmd in ("next", "advance", session_contract.RE_EMIT_CMD)
                and outcome == "orders-emitted"
                and session_dir is not None):
            roster, refusal = _orders_emitted_roster_or_refusal(session_dir, event)
            if refusal is not None:
                return None, refusal
            for sk, occ in roster:
                opened[(phase, rnd, attempt, sk, occ)] = event
        if session_contract.journal_is_re_emit_orders_superseded(event):
            if phase is not None and rnd is not None and attempt is not None:
                superseded.add((phase, rnd, attempt))
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
        phase_key, rnd_key, attempt_key, sk_key, occ_key = key
        if (phase_key, rnd_key, attempt_key) in superseded:
            if session_dir is not None:
                skey = storage_key(sk_key, occ_key)
                landing = record_paths.landing_path(session_dir, rnd_key, phase_key, skey, attempt_key)
                bare = record_paths.bare_payload_path(session_dir, rnd_key, phase_key, skey, attempt_key)
                # Presence is the DIRECTORY ENTRY, not whether its target resolves (`lstat`, not `isfile`).
                # axis: a superseded seat closes only when neither entry exists; indeterminate or unknown session dir keeps it open
                if (not record_paths.landing_entry_present(landing)
                        and not record_paths.landing_entry_present(bare)):
                    continue
        if key not in closed:
            unclosed.append((key, event))
    return unclosed, None


def _certified_head_sha(ctx):
    meta = ctx.get("meta") or {}
    cfg = (ctx.get("state") or {}).get("config") or {}
    head = meta.get(session_contract.FIX_FOLD_HEAD_KEY)
    if isinstance(head, str) and head:
        return head
    head = cfg.get(session_contract.FIX_FOLD_HEAD_KEY)
    if isinstance(head, str) and head:
        return head
    head = meta.get("headSha")
    if isinstance(head, str) and head:
        return head
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


def _runner_tool_calls(obs):
    if not isinstance(obs, dict):
        return None
    observation = obs.get("observation")
    if isinstance(observation, dict) and "toolCalls" in observation:
        return observation.get("toolCalls")
    return obs.get("toolCalls")


def _observation_qualifies(
    obs,
    certified_head,
    cited_head,
    journal_binding=None,
    recorded_nonces=None,
    *,
    require_runner_action=False,
):
    if not isinstance(obs, dict):
        return False, "execution-evidence-absent"
    read = _execution_evidence_read_value(obs)
    if read not in EXECUTION_EVIDENCE_READ_VALUES:
        return False, "execution-evidence-read-invalid"
    if read != "engaged":
        return False, "execution-evidence-not-engaged"
    if require_runner_action:
        tool_calls = _runner_tool_calls(obs)
        if not isinstance(tool_calls, int) or tool_calls < 1:
            return False, "execution-evidence-no-runner-action"
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
    envelope, certified_head, journal_binding=None, recorded_nonces=None, phase=None
):
    evidence = envelope.get("executionEvidence") if isinstance(envelope, dict) else None
    if not isinstance(evidence, dict):
        return False, "execution-evidence-absent"
    order_sha = envelope.get("orderSha256")
    if not isinstance(order_sha, str) or not order_sha:
        return False, "execution-evidence-order-unbound"
    ok, binding_failure = _execution_binding_matches_journal(
        evidence, journal_binding, recorded_nonces or set()
    )
    if not ok:
        return False, binding_failure
    result_kind = evidence.get("resultKind")
    result_digest = evidence.get("resultDigest")
    payload = envelope.get("payload")
    if (not isinstance(result_kind, str) or not result_kind
            or not isinstance(result_digest, str) or not result_digest):
        return False, "execution-evidence-binding-incomplete"
    if session_contract.evidence_binding(result_kind) == session_contract.EXECUTION_ONLY_BINDING:
        if not session_contract.execution_only_admissible_for_phase(phase):
            return False, "execution-evidence-write-stamp-out-of-phase"
        # axis: write-run stamp proves the run happened — binds no payload (execution-only)
        return True, EXECUTION_ONLY_BINDING
    carried, subject = session_contract.evidence_digest_subject(payload, result_kind)
    if not carried:
        return False, "execution-evidence-result-mismatch"
    computed = session_contract.payload_sha256(subject)
    if result_digest != computed:
        return False, "execution-evidence-result-mismatch"
    return True, None


def _hand_landed_read_qualifies(evidence):
    if not isinstance(evidence, dict):
        return False, "execution-evidence-absent"
    read = _execution_evidence_read_value(evidence)
    if read not in EXECUTION_EVIDENCE_READ_VALUES:
        return False, "execution-evidence-read-invalid"
    if read != "engaged":
        return False, "execution-evidence-not-engaged"
    observation = evidence.get("observation")
    if isinstance(observation, dict):
        extra_obs = set(observation.keys()) - EXECUTION_EVIDENCE_OBSERVATION_FIELDS
        if extra_obs:
            return False, "execution-evidence-unknown-field"
    return True, None


def _envelope_sha256(payload, execution_evidence):
    return session_contract.sha256_text(
        session_contract.canonical(
            {"payload": payload, "executionEvidence": execution_evidence}
        )
    )


def _read_head_content_blobs(session_dir):
    path = os.path.join(session_dir, HEAD_CONTENT_BLOBS_FILE)
    if not os.path.exists(path):
        return session_contract.classify_head_content_read(absent=True)
    try:
        with open(path, encoding="utf-8") as fh:
            blobs = json.load(fh)
    except (OSError, ValueError) as exc:
        return session_contract.classify_head_content_read(error=exc)
    return session_contract.classify_head_content_read(blobs=blobs)


def _fix_still_present_at_head(ctx, finding, receipt, by_key=None):
    fid = finding.get("id") or finding.get("title") or "finding"
    head = receipt.get("headSha") or _certified_head_sha(ctx)
    read_outcome = _read_head_content_blobs(ctx["session_dir"])
    binding = session_contract.fix_still_present_at_head(
        finding, receipt, head, read_outcome, by_key=by_key,
    )
    if binding is None:
        return None
    token, detail = binding
    return _refusal(
        "disposition-without-receipt",
        fid,
        detail,
        binding_failure=token,
    )


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
                require_runner_action=True,
            )
            if not ok:
                return _refusal(
                    "unrun-review",
                    seat,
                    "dispatch-observed seat lacks qualifying execution telemetry",
                    binding_failure=binding,
                )
            rk_ok, found_kind = _dispatch_run_kind_qualifies(obs, phase)
            if not rk_ok:
                return _refusal(
                    "unrun-review",
                    seat,
                    _run_kind_refusal_detail(phase, found_kind),
                    binding_failure="evidence-run-kind-mismatch",
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
                phase=phase,
            )
            if not ok:
                return _refusal(
                    "unrun-review",
                    path,
                    "hand-landed seat lacks qualifying execution-evidence binding",
                    binding_failure=binding,
                )
            evidence = env.get("executionEvidence") if isinstance(env, dict) else None
            if isinstance(evidence, dict) and "runKind" in evidence:
                rk_ok, found_kind = _dispatch_run_kind_qualifies(evidence, phase)
                if not rk_ok:
                    return _refusal(
                        "unrun-review",
                        seat,
                        _run_kind_refusal_detail(phase, found_kind),
                        binding_failure="evidence-run-kind-mismatch",
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


def _runner_recorded_vendor_status(obs, session_dir, seat_entry):
    """Return ``vendor`` | ``missing`` for an audit seat's runner-recorded vendor."""
    seat = seat_entry["seat"]
    phase = seat_entry["phase"]
    attempt = seat_entry["attempt"]
    occurrence = seat_entry.get("occurrence", 0)
    rnd = seat_entry["round"]
    vendor = obs.get("source") if isinstance(obs, dict) else None
    if isinstance(vendor, str) and vendor:
        return vendor
    provenance = seat_entry.get("provenance")
    if provenance == PROVENANCE_HAND_LANDED:
        env, _path = _load_envelope(
            session_dir,
            rnd,
            phase,
            seat,
            attempt,
            occurrence,
        )
        if isinstance(env, dict):
            evidence = env.get("executionEvidence")
            if isinstance(evidence, dict):
                vendor = evidence.get("source")
    if isinstance(vendor, str) and vendor:
        return vendor
    return "missing"


def _envelope_execution_model_field(session_dir, seat_entry):
    """Return (model_field_present, model_value) from the CAS-bound envelope."""
    provenance = seat_entry.get("provenance")
    if provenance not in RECEIPT_PROVENANCE:
        return False, None
    seat = seat_entry["seat"]
    phase = seat_entry["phase"]
    attempt = seat_entry["attempt"]
    occurrence = seat_entry.get("occurrence", 0)
    rnd = seat_entry["round"]
    env, _path = _load_envelope(
        session_dir,
        rnd,
        phase,
        seat,
        attempt,
        occurrence,
    )
    if not isinstance(env, dict):
        return False, None
    evidence = env.get("executionEvidence")
    if not isinstance(evidence, dict) or "model" not in evidence:
        return False, None
    return True, evidence.get("model")


def _envelope_execution_model(session_dir, seat_entry):
    present, value = _envelope_execution_model_field(session_dir, seat_entry)
    if not present:
        return None
    return value


def _runner_recorded_model(obs, session_dir, seat_entry):
    """Return the runner-recorded model from the CAS-bound envelope."""
    return _envelope_execution_model(session_dir, seat_entry)


def _journal_envelope_model_refusal(obs, session_dir, seat_entry):
    if not isinstance(obs, dict) or "model" not in obs:
        return None
    journal_model = obs.get("model")
    envelope_has_model, envelope_model = _envelope_execution_model_field(
        session_dir, seat_entry
    )
    if not envelope_has_model or journal_model != envelope_model:
        seat = seat_entry["seat"]
        return _refusal(
            "unfetched-findings",
            seat,
            "journal executionEvidence.model disagrees with stored envelope",
            binding_failure="journal-envelope-mismatch",
        )
    return None


def check_seat_independence(ctx):
    # axis: the receipt's independence is read from the record — the declared fixer vendor and each
    # audit seat's runner-recorded vendor — and a record that contradicts itself refuses; a record
    # that shows a same-family audit reads degraded.
    state = ctx["state"]
    journal = ctx["journal"]
    session_dir = ctx["session_dir"]
    cfg = state.get("config") or {}
    fixer = cfg.get("fixerVendor")
    fixer_fam = model_registry.family_for("code-fixer", fixer)
    if fixer_fam is None:
        return None
    for seat_entry in _collect_seats(ctx):
        seat = seat_entry["seat"]
        phase = seat_entry["phase"]
        attempt = seat_entry["attempt"]
        occurrence = seat_entry.get("occurrence", 0)
        rnd = seat_entry["round"]
        obs = _journal_observation_for_seat(
            journal, seat, phase, attempt, occurrence, rnd
        )
        if phase == P_FIXER:
            source = obs.get("source") if isinstance(obs, dict) else None
            if isinstance(source, str) and source and source != fixer:
                return _refusal(
                    "unfetched-findings",
                    seat,
                    "fixer seat %s ran on %r per the runner record; the declared fixer vendor is %r"
                    % (seat, source, fixer),
                    binding_failure="fixer-vendor-contradicted",
                )
            continue
        if phase != P_AUDITS:
            continue
        vendor_status = _runner_recorded_vendor_status(obs, session_dir, seat_entry)
        if vendor_status == "missing":
            return _refusal(
                "unrun-review",
                seat,
                "audit seat %s has no runner-recorded vendor" % seat,
                binding_failure="auditor-vendor-underivable",
            )
        vendor = vendor_status
        fam = model_registry.family_for("auditor", vendor)
        if fam is None:
            return _refusal(
                "unfetched-findings",
                seat,
                "audit seat %s vendor %r has no registry family" % (seat, vendor),
            )
        model_refusal = _journal_envelope_model_refusal(obs, session_dir, seat_entry)
        if model_refusal is not None:
            return model_refusal
    return None


def _independence_block(ctx):
    state = ctx["state"]
    journal = ctx["journal"]
    cfg = state.get("config") or {}
    fixer = cfg.get("fixerVendor")
    fixer_fam = model_registry.family_for("code-fixer", fixer)
    audit_seats = []
    for seat_entry in _collect_seats(ctx):
        if seat_entry.get("phase") != P_AUDITS:
            continue
        seat = seat_entry["seat"]
        phase = seat_entry["phase"]
        attempt = seat_entry["attempt"]
        occurrence = seat_entry.get("occurrence", 0)
        rnd = seat_entry["round"]
        obs = _journal_observation_for_seat(
            journal, seat, phase, attempt, occurrence, rnd
        )
        vendor_status = _runner_recorded_vendor_status(obs, ctx["session_dir"], seat_entry)
        if vendor_status == "missing":
            continue
        vendor = vendor_status
        fam = model_registry.family_for("auditor", vendor)
        model = _runner_recorded_model(obs, ctx["session_dir"], seat_entry)
        audit_seats.append(
            {
                "seat": seat,
                "round": rnd,
                "vendor": vendor,
                "family": fam,
                "model": model,
            }
        )
    same_family_seats = [
        entry["seat"] for entry in audit_seats
        if entry.get("family") == fixer_fam
    ]
    if same_family_seats:
        status = "degraded"
        basis = "auditor-same-family"
    elif audit_seats:
        status = "independent"
        basis = "runner-recorded-audit-seats"
    elif receipt_disclosures.independent_auditor_available(cfg)[0]:
        status = "independent"
        basis = "declared-vendors"
    else:
        status = "degraded"
        basis = "no-independent-auditor-declared"
    block = {
        "status": status,
        "basis": basis,
        "fixerVendor": fixer,
        "fixerFamily": fixer_fam,
        "declaredVendors": receipt_disclosures.live_vendors(cfg),
        "auditSeats": audit_seats,
    }
    if same_family_seats:
        block["sameFamilySeats"] = same_family_seats
    return block


def check_unfetched_findings(ctx):
    session_dir = ctx["session_dir"]
    journal = ctx["journal"]
    unclosed, roster_refusal = _journal_open_seats(journal, session_dir)
    if roster_refusal is not None:
        return roster_refusal
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
            computed = session_contract.payload_sha256(env.get("payload"))
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
        if env.get("schema") == SEAT_RESULT_SCHEMA_V2:
            declared_envelope = env.get("envelopeSha256")
            journaled_cas = ident.get("casToken")
            if not isinstance(declared_envelope, str) or not declared_envelope:
                return _refusal(
                    "unfetched-findings",
                    path,
                    "landed envelope lacks envelopeSha256 integrity field",
                )
            try:
                computed_envelope = _envelope_sha256(
                    env.get("payload"), env.get("executionEvidence")
                )
            except (TypeError, ValueError):
                return _refusal(
                    "unfetched-findings",
                    path,
                    "landed envelope is not hashable for envelope integrity reconciliation",
                )
            if computed_envelope != declared_envelope:
                return _refusal(
                    "unfetched-findings",
                    path,
                    "landed envelope envelopeSha256 does not match envelope content",
                    binding_failure="journal-envelope-mismatch",
                )
            journaled_cas = ident.get("casToken")
            if isinstance(journaled_cas, str) and journaled_cas:
                if computed_envelope != journaled_cas:
                    return _refusal(
                        "unfetched-findings",
                        path,
                        "journal casToken disagrees with landed envelope revision",
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
    nonblocking_disclosures = []
    by_key, marker_refusal = _certification_findings_by_key(state)
    if marker_refusal is not None:
        return marker_refusal
    for finding in by_key.values():
        if not isinstance(finding, dict):
            continue
        fid = finding.get("id") or finding.get("title") or "finding"
        severity = finding.get("severity")
        if finding.get(session_contract.MERGED_INTO_FIELD):
            if _resolve_merged_into_entry(finding, by_key) is None:
                return _refusal(
                    "disposition-without-receipt",
                    fid,
                    "merged-into chain does not resolve",
                )
        graded = _effective_certification_finding(finding, by_key)
        disposition = graded.get("disposition")
        if disposition is None:
            severity_rank = _severity_rank(severity)
            if severity_rank == 99:
                return _refusal(
                    "disposition-without-receipt",
                    fid,
                    "finding severity %r is not in the closed severity contract" % (severity,),
                )
            if severity_rank == _severity_rank("Critical"):
                return _refusal(
                    "disposition-without-receipt",
                    fid,
                    "Critical finding may not take the non-blocking path",
                )
            if severity_rank <= _severity_rank("Important"):
                return _refusal(
                    "disposition-without-receipt",
                    fid,
                    "finding has no disposition recorded",
                )
            if not _supports_nonblocking_disclosure(state):
                return _refusal(
                    "disposition-without-receipt",
                    fid,
                    "finding has no disposition recorded",
                )
            row = {
                "id": finding.get("id"),
                "title": finding.get("title"),
                "severity": severity,
            }
            finding_key = _finding_identity_key(finding)
            if finding_key:
                row[session_contract.FINDING_KEY_FIELD] = finding_key
            file_loc = finding.get("file")
            if file_loc is not None:
                row["file"] = file_loc
            line_loc = finding.get("line")
            if line_loc is not None:
                row["line"] = line_loc
            nonblocking_disclosures.append(row)
            continue
        if disposition not in session_contract.DISPOSITIONS:
            return _refusal(
                "disposition-without-receipt",
                fid,
                "unknown disposition %r" % (disposition,),
            )
        if _severity_rank(severity) == 99:
            return _refusal(
                "disposition-without-receipt",
                fid,
                "finding severity %r is not in the closed severity contract" % (severity,),
            )
        if disposition == "fixed":
            receipt = graded.get("dispositionReceipt")
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
            if receipt.get("verifyResult") != "pass":
                return _refusal(
                    "disposition-without-receipt",
                    fid,
                    "fixed disposition verification receipt did not pass",
                    binding_failure="verify-not-pass",
                )
            refusal = _fix_still_present_at_head(ctx, graded, receipt, by_key=by_key)
            if refusal is not None:
                return refusal
        elif disposition == "refuted":
            if _refuted_reason_text(graded) is None:
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
            reason = graded.get("outOfScopeReason")
            if not isinstance(reason, str) or not reason.strip():
                return _refusal(
                    "disposition-without-receipt",
                    fid,
                    "out-of-scope disposition lacks recorded reason",
                )
            follow_up = _out_of_scope_follow_up(graded)
            if not isinstance(follow_up, dict):
                return _refusal(
                    "disposition-without-receipt",
                    fid,
                    "out-of-scope disposition lacks named follow-up item",
                )
            # Grades persisted records; some were recorded before item was checked at submit.
            shape_fault = session_contract.follow_up_shape_fault(follow_up, require_item=False)
            if shape_fault:
                binding_failure, detail = shape_fault
                return _refusal(
                    "disposition-without-receipt",
                    fid,
                    detail,
                    binding_failure=binding_failure,
                )
            if _severity_rank(severity) == _severity_rank("Important"):
                disclosures.append(
                    {
                        "id": finding.get("id"),
                        "title": finding.get("title"),
                        "severity": severity,
                        "reason": graded.get("outOfScopeReason"),
                    }
                )
    ctx["important_disclosures"] = disclosures
    ctx["nonblocking_disclosures"] = nonblocking_disclosures
    return None


def check_hand_landed_read_engaged(ctx):
    """After disposition and head-bound checks — read engagement cannot preempt them."""
    session_dir = ctx["session_dir"]
    for seat_entry in _collect_seats(ctx):
        if seat_entry.get("provenance") != PROVENANCE_HAND_LANDED:
            continue
        env, path = _load_envelope(
            session_dir,
            seat_entry["round"],
            seat_entry["phase"],
            seat_entry["seat"],
            seat_entry["attempt"],
            seat_entry.get("occurrence", 0),
        )
        if env is None:
            continue
        ok, binding = _hand_landed_read_qualifies(env.get("executionEvidence"))
        if not ok:
            return _refusal(
                "unrun-review",
                path,
                "hand-landed seat lacks qualifying execution-evidence read engagement",
                binding_failure=binding,
            )
    return None


def check_evidence_head_bound(ctx):
    """Before hand-landed read engagement — disposition refusals keep their own class.

    Disposition, follow-up, and base-guard refusals keep their own classes rather than
    being preempted by a head refusal.
    """
    certified_head = _certified_head_sha(ctx)
    if not certified_head:
        # A session whose certified head cannot be resolved does not certify — there is
        # no head for any seat's evidence to be bound to, so nothing can be shown fresh.
        # review-code's SKILL writes meta.json and halts without it, but that halt lives in
        # a caller; another session-directory producer reaches this path.
        return _refusal(
            "unrun-review",
            META_FILE,
            "session certified head cannot be resolved",
            binding_failure=BINDING_FAILURE_CERTIFIED_HEAD_UNRESOLVABLE,
        )
    for seat_entry in _collect_seats(ctx):
        if seat_entry.get("provenance") != PROVENANCE_DISPATCH_OBSERVED:
            continue
        cited_head = seat_entry.get("citedHead")
        if cited_head:
            continue
        # A dispatch-observed seat row that cites no head is not a qualifying result — the
        # staleness comparison in _observation_qualifies can only compare a head that is
        # present, so an absent one is no check at all rather than a fresh one.
        return _refusal(
            "unrun-review",
            seat_entry["seat"],
            "dispatch-observed seat lacks cited head on the certified head",
            binding_failure=BINDING_FAILURE_EXECUTION_EVIDENCE_HEAD_UNBOUND,
        )
    return None


def _severity_rank(severity):
    if severity not in circuit_breaker.SEVERITY_TIERS:
        return 99
    return circuit_breaker.SEVERITY_TIERS.index(severity)


def _collect_seats(ctx):
    rows = []
    for identity, event in receipt_disclosures.latest_recorded_events(ctx["journal"]):
        cited_head = event.get("headSha") or event.get("citedHead")
        model = None
        if event.get(session_contract.SEAT_TRANSPORT_KEY) == session_contract.SEAT_TRANSPORT_RUNNER:
            evidence = event.get("executionEvidence")
            if isinstance(evidence, dict):
                engine_model = evidence.get("engineModel")
                if isinstance(engine_model, str) and engine_model:
                    model = engine_model
        rows.append({**identity, "citedHead": cited_head, "model": model})
    return rows


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
        return _out_of_scope_follow_up(finding)
    if disposition == "refuted":
        reason = _refuted_reason_text(finding)
        if isinstance(reason, str):
            return reason
        return finding.get("refutedReason")
    return finding.get("dispositionReceipt")


def _project_finding(finding, by_key=None):
    """axis: merged-away members report the representative's disposition family, not their own."""
    effective = (
        _effective_certification_finding(finding, by_key)
        if by_key is not None
        else finding
    )
    row = {
        "id": finding.get("id"),
        "file": finding.get("file"),
        "line": finding.get("line"),
        "title": finding.get("title"),
        "severity": finding.get("severity"),
        "verdict": finding.get("verdict"),
        "challenge": finding.get("challenge"),
        "unverified": finding.get("unverified"),
        "disposition": effective.get("disposition"),
    }
    proof = _finding_disposition_proof(effective)
    if proof is not None:
        row = dict(row, dispositionReceipt=proof)
    finding_key = finding.get(session_contract.FINDING_KEY_FIELD)
    if finding_key:
        row[session_contract.FINDING_KEY_FIELD] = finding_key
    raised_round = finding.get(session_contract.RAISED_ROUND_FIELD)
    if raised_round is not None:
        row[session_contract.RAISED_ROUND_FIELD] = raised_round
    merged_into = finding.get(session_contract.MERGED_INTO_FIELD)
    if merged_into:
        row[session_contract.MERGED_INTO_FIELD] = merged_into
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
        if disposition in session_contract.DISPOSITIONS[:2]:
            if not isinstance(proof, dict) and not (
                disposition == "refuted" and isinstance(proof, str) and proof.strip()
            ):
                return _refusal(
                    "unfetched-findings",
                    fid,
                    "certified receipt finding lacks disposition proof",
                )
        elif disposition == session_contract.DISPOSITIONS[2]:
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


def _validate_receipt_additions(receipt):
    independence = receipt.get("independence") or {}
    audit_seats = independence.get("auditSeats")
    if isinstance(audit_seats, list):
        for entry in audit_seats:
            if not isinstance(entry, dict):
                continue
            model = entry.get("model")
            if "model" in entry and model is not None:
                if not isinstance(model, str) or not model:
                    return _refusal(
                        "unfetched-findings",
                        entry.get("seat") or "audit-seat",
                        "certified receipt independence.auditSeats model must be "
                        "a non-empty string or null",
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
            "verifiedHead": rec.get("verifiedHead"),
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



def _receipt_disclosures(ctx, state):
    disclosures = {
        "importantOutOfScope": list(ctx.get("important_disclosures") or []),
    }
    if _supports_nonblocking_disclosure(state):
        disclosures["survivingNonBlocking"] = list(ctx.get("nonblocking_disclosures") or [])
    return disclosures


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
            "model": s.get("model"),
        }
        for s in seats_info
    ]
    by_key, marker_refusal = _certification_findings_by_key(state)
    if marker_refusal is not None:
        return None, marker_refusal
    findings = []
    for f in by_key.values():
        if not isinstance(f, dict):
            continue
        graded = _effective_certification_finding(f, by_key)
        if session_contract.disposition_value(graded) is None:
            rank = _severity_rank(f.get("severity"))
            if (_supports_nonblocking_disclosure(state)
                    and rank > _severity_rank("Important")):
                continue
        findings.append(_project_finding(f, by_key))
    rounds = _build_receipt_rounds(state, form)
    degraded, skipped_blockers = build_degraded_prose(state, form, journal=journal)
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
        "disclosures": _receipt_disclosures(ctx, state),
        "independence": _independence_block(ctx),
        "provenanceLabels": {
            "derived": [
                "schemaVersion",
                "scriptRan",
                "terminalState",
                "terminalCause",
                "seats",
                "disclosures",
                "certificationShape",
                "independence",
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
    return receipt, None


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
