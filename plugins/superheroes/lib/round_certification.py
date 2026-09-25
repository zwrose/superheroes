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

import audits
import circuit_breaker
import decision_kinds
import model_registry
import record_paths
import round_panel_contract
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
EXECUTION_EVIDENCE_BINDING_FIELDS = session_contract.EXECUTION_EVIDENCE_BINDING_FIELDS
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


def _chain_qualified_certification_shape(shape):
    """Map a full-panel loop shape to its audited-chain counterpart — suffixes preserved."""
    confirmed = "full-panel-confirmed"
    if shape == confirmed:
        return "audited-chain"
    if isinstance(shape, str) and shape.startswith(confirmed):
        return "audited-chain" + shape[len(confirmed):]
    if isinstance(shape, str) and shape.startswith("full-panel"):
        return "audited-chain"
    if shape is None:
        return "audited-chain"
    return shape


def _certification_shape(state, seats, chain_used=False):
    """Hand-landed / audited-chain shape override — tested directly; receipt follows driver parity."""
    cert = state.get("certification") or {}
    shape = cert.get("shape")
    hand_landed = any(s.get("provenance") == PROVENANCE_HAND_LANDED for s in seats)
    if hand_landed or chain_used:
        derived = _chain_qualified_certification_shape(shape)
        if derived != shape or shape is None:
            return derived
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


_SCOPED_FINDER_PHASE = round_panel_contract.P_SCOPED_FINDER_PHASE
_AUDITED_CHAIN_MEMO_KEY = "_auditedChainMemo"
_CHAIN_QUALIFIED_KEY = "_auditedChainQualified"


def _panel_lens_coverage_complete(lc, expected_count):
    if not isinstance(lc, dict):
        return False
    for key in ("ran", "expected", "floor"):
        if key not in lc:
            return False
    ran, expected, floor = lc["ran"], lc["expected"], lc["floor"]
    if type(ran) is not int or type(expected) is not int or not isinstance(floor, bool):
        return False
    if expected != expected_count or expected <= 0:
        return False
    if floor or ran != expected:
        return False
    return True


def _valid_head_sha(head):
    return isinstance(head, str) and bool(head) and len(head) in (40, 64)


def _panel_dimension_roster_from_manifest(manifest):
    """Configured dimension names from manifest seat entries — not storage map keys."""
    seats = manifest.get("seats") if isinstance(manifest, dict) else None
    if not isinstance(seats, dict):
        return None
    roster = set()
    for entry in seats.values():
        if not isinstance(entry, dict):
            return None
        seat = entry.get("seat")
        if not isinstance(seat, str) or not seat:
            return None
        if seat in roster:
            return None
        roster.add(seat)
    return roster


def _audited_chain_panel_coverage_ok(state, manifest, panel_round):
    """Panel leg: authenticated manifest roster must cover every configured dimension."""
    cfg = (state.get("config") or {}) if isinstance(state, dict) else {}
    dims = round_panel_contract.panel_dimensions_from_config(cfg)
    if not dims:
        return True
    roster = _panel_dimension_roster_from_manifest(manifest)
    if roster is None or not all(dim in roster for dim in dims):
        return False
    return True


def _audit_fix_receipt_head_rule(repo_root, post_fix_head, certified_head):
    def _rule(cited_head):
        if not _valid_head_sha(cited_head):
            return False, "audited-chain-gap:descent"
        if not _is_ancestor(repo_root, post_fix_head, cited_head):
            return False, "audited-chain-gap:descent"
        if not _is_ancestor(repo_root, cited_head, certified_head):
            return False, "audited-chain-gap:descent"
        return True, None

    return _rule


def _resolve_post_fix_head(state, finding):
    disposition_round = finding.get("dispositionRound")
    if isinstance(disposition_round, bool) or not isinstance(disposition_round, int):
        return None
    receipt = finding.get("dispositionReceipt")
    if not isinstance(receipt, dict):
        return None
    post_fix = receipt.get("headSha")
    if not _valid_head_sha(post_fix):
        return None
    fixer_round = disposition_round - 1
    if fixer_round < 1:
        return None
    rounds = state.get("rounds") if isinstance(state, dict) else None
    if not isinstance(rounds, dict):
        return None
    rec = rounds.get(str(fixer_round))
    if not isinstance(rec, dict):
        return None
    recorded = rec.get("fixFoldHead")
    if not _valid_head_sha(recorded) or recorded != post_fix:
        return None
    return post_fix


def _superseded_audit_attempts(journal):
    superseded = set()
    if not isinstance(journal, list):
        return superseded
    for event in journal:
        if not isinstance(event, dict):
            continue
        if not session_contract.journal_is_re_emit_orders_superseded(event):
            continue
        phase = event.get("phase")
        rnd = event.get("round")
        attempt = event.get("attempt")
        if (phase == P_AUDITS and isinstance(rnd, int) and not isinstance(rnd, bool)
                and attempt is not None):
            superseded.add((rnd, phase, attempt))
    return superseded


def _collapse_dispatch_audit_recorded_rows(journal):
    """Latest journal row per dispatch-audits slot; drop superseded attempts."""
    if not isinstance(journal, list):
        return []
    superseded = _superseded_audit_attempts(journal)
    latest = {}
    for event in journal:
        if not isinstance(event, dict):
            continue
        if event.get("outcome") != "recorded" or event.get("phase") != P_AUDITS:
            continue
        seat, phase, attempt, occ, rnd = _journal_event_slot(event)
        if attempt is None or not isinstance(rnd, int) or isinstance(rnd, bool):
            continue
        if (rnd, phase, attempt) in superseded:
            continue
        latest[(rnd, phase, attempt, seat, occ)] = event
    return list(latest.values())


def _audit_orders_emit_for_attempt(journal, rnd, attempt):
    for event in journal:
        if not isinstance(event, dict):
            continue
        if (event.get("outcome") == "orders-emitted" and event.get("phase") == P_AUDITS
                and event.get("round") == rnd and event.get("attempt") == attempt):
            return event
    return None


def _manifest_vendor_for_audit_row(session_dir, journal, event):
    seat, phase, attempt, occ, rnd = _journal_event_slot(event)
    emit = _audit_orders_emit_for_attempt(journal, rnd, attempt)
    if emit is None:
        return None
    manifest, refusal = _verified_orders_manifest(session_dir, emit)
    if refusal is not None or not isinstance(manifest, dict):
        return None
    seats = manifest.get("seats")
    if not isinstance(seats, dict):
        return None
    skey = storage_key(seat, occ)
    entry = seats.get(skey)
    if not isinstance(entry, dict):
        entry = seats.get(seat)
    if not isinstance(entry, dict):
        return None
    if entry.get("seat") != seat:
        return None
    entry_occ = entry.get("occurrence", 0)
    if entry_occ != occ:
        return None
    vendor = entry.get("vendor")
    if not isinstance(vendor, str) or not vendor:
        return None
    return vendor


def _audited_chain_fold_target_id(finding, by_key):
    if finding.get(session_contract.MERGED_INTO_FIELD):
        rep = _resolve_merged_into_entry(finding, by_key)
        if rep is None:
            return None
        return _finding_identity_key(rep)
    return _finding_identity_key(finding)


def _audit_runner_vendor_from_envelope(envelope):
    """Trusted vendor for collection-manifest binding — runner evidence only."""
    evidence = envelope.get("executionEvidence") if isinstance(envelope, dict) else None
    if not isinstance(evidence, dict):
        return None
    source = evidence.get("source")
    if isinstance(source, str) and source and source in model_registry.VENDORS:
        return source
    return None


def _audit_admitted_dispatch_result(session_dir, journal, event, certified_head, head_rule):
    """Return (payload, envelope) when a dispatch-audits journal row passes admission gates."""
    if event.get("outcome") != "recorded" or event.get("phase") != P_AUDITS:
        return None
    seat, phase, attempt, occurrence, rnd = _journal_event_slot(event)
    if not isinstance(seat, str) or attempt is None:
        return None
    env, _path = _load_envelope(session_dir, rnd, phase, seat, attempt, occurrence)
    if not isinstance(env, dict):
        return None
    payload = env.get("payload")
    if not isinstance(payload, dict):
        return None
    declared = env.get("payloadSha256")
    try:
        computed = session_contract.payload_sha256(payload)
    except (TypeError, ValueError):
        return None
    if not isinstance(declared, str) or computed != declared:
        return None
    provenance = event.get("provenance") or env.get("provenance")
    cited = event.get("headSha") or event.get("citedHead")
    slot_nonces = _journal_recorded_runner_nonces_for_slot(
        journal, seat, phase, attempt, occurrence, rnd)
    journal_binding = _journal_execution_binding(
        journal, seat, phase, attempt, occurrence, rnd)
    if provenance == PROVENANCE_DISPATCH_OBSERVED:
        obs = _journal_observation_for_seat(
            journal, seat, phase, attempt, occurrence, rnd)
        envelope_evidence = env.get("executionEvidence")
        if not isinstance(envelope_evidence, dict):
            return None
        ok, _binding = _observation_qualifies(
            obs,
            certified_head,
            cited,
            journal_binding=journal_binding,
            recorded_nonces=slot_nonces,
            require_runner_action=True,
            head_rule=head_rule,
            envelope_run_kind_evidence=envelope_evidence,
        )
        if not ok:
            return None
        rk_ok, _found_kind, _rk_binding = _dispatch_run_kind_qualifies(
            envelope_evidence, phase
        )
        if not rk_ok:
            return None
    elif provenance == PROVENANCE_HAND_LANDED:
        if head_rule is None or not _valid_head_sha(cited):
            return None
        ok_head, _gap = head_rule(cited)
        if not ok_head:
            return None
        ok, _binding = _hand_landed_evidence_qualifies(
            env,
            certified_head,
            journal_binding=journal_binding,
            recorded_nonces=slot_nonces,
            phase=phase,
        )
        if not ok:
            return None
    else:
        return None
    return dict(payload), env


def _new_issues_dispositioned(state, fold_id, fold_round, new_issues):
    """True when every new issue raised by fold_id's discharged-but-new-issue fold is dispositioned."""
    if not isinstance(fold_id, str) or not fold_id:
        return False
    if not isinstance(fold_round, int) or isinstance(fold_round, bool):
        return False
    if not isinstance(new_issues, list):
        return False
    linked = []
    for entry in new_issues:
        if not isinstance(entry, dict):
            continue
        if entry.get("originAuditId") == fold_id:
            linked.append(entry)
    if not linked:
        return False
    if (session_contract.disposition_ledger_owner_classification(state)
            != session_contract.DISPOSITION_LEDGER_OWNER_RECOGNIZED):
        return False
    ledger_rows, ledger_fault = session_contract.read_disposition_ledger(state, required=True)
    if ledger_fault is not None:
        return False
    ledger_index = {}
    key_counts = {}
    for row in ledger_rows:
        if not isinstance(row, dict):
            continue
        key = session_contract.finding_identity_key(row)
        if not key:
            continue
        ledger_index[key] = row
        key_counts[key] = key_counts.get(key, 0) + 1
    if any(count > 1 for count in key_counts.values()):
        return False
    for cand in linked:
        copy = dict(cand)
        copy.pop(session_contract.FINDING_KEY_FIELD, None)
        copy.pop("originAuditId", None)
        file_val = copy.get("file")
        if not isinstance(file_val, str) or not file_val:
            return False
        ok, line = session_contract.coerce_line(copy.get("line"))
        if not ok:
            return False
        copy["line"] = line
        key = session_contract.minted_identity_key(copy)
        if not isinstance(key, str) or not key:
            return False
        if key == fold_id:
            return False
        count = key_counts.get(key, 0)
        if count != 1:
            return False
        row = ledger_index[key]
        raised_round = row.get(session_contract.RAISED_ROUND_FIELD)
        if not isinstance(raised_round, int) or isinstance(raised_round, bool):
            return False
        if raised_round < fold_round:
            return False
        raised_seq = row.get(session_contract.RAISED_SEQ_FIELD)
        if not isinstance(raised_seq, int) or isinstance(raised_seq, bool):
            return False
        effective = session_contract.resolve_merged_into_entry(row, ledger_index)
        if effective is None:
            return False
        rep_key = session_contract.finding_identity_key(effective)
        if rep_key == fold_id:
            return False
        disposition = effective.get("disposition")
        if disposition not in session_contract.DISPOSITIONS:
            return False
        disp_seq = effective.get(session_contract.DISPOSITION_SEQ_FIELD)
        if not isinstance(disp_seq, int) or isinstance(disp_seq, bool):
            return False
        if disp_seq <= raised_seq:
            return False
    return True


def _fixed_finding_has_discharging_audit(ctx, finding, certified_head, repo_root):
    session_dir = ctx.get("session_dir")
    journal = ctx.get("journal") or []
    state = ctx.get("state") or {}
    if session_dir is None or not isinstance(journal, list):
        return "fix-receipt"
    by_key, marker_refusal = _certification_findings_by_key(state)
    if marker_refusal is not None:
        return "fix-receipt"
    fold_id = _audited_chain_fold_target_id(finding, by_key)
    if not isinstance(fold_id, str) or not fold_id:
        return "fix-receipt"
    post_fix_head = _resolve_post_fix_head(state, finding)
    if post_fix_head is None:
        return "fix-receipt"
    head_rule = _audit_fix_receipt_head_rule(repo_root, post_fix_head, certified_head)
    fixer_fam = maker_author_family(state)
    if fixer_fam is None:
        return "fix-receipt"
    admitted_by_round = {}
    for event in _collapse_dispatch_audit_recorded_rows(journal):
        seat, _phase, _attempt, _occ, rnd = _journal_event_slot(event)
        if seat != fold_id:
            continue
        admitted = _audit_admitted_dispatch_result(
            session_dir, journal, event, certified_head, head_rule)
        if admitted is None:
            continue
        payload, env = admitted
        pid = payload.get("id")
        if pid != fold_id or pid != seat:
            continue
        manifest_vendor = _manifest_vendor_for_audit_row(session_dir, journal, event)
        if manifest_vendor is None:
            continue
        runner_vendor = _audit_runner_vendor_from_envelope(env)
        if runner_vendor is not None and fixer_fam is not None:
            audit_fam = model_registry.family_for("auditor", runner_vendor)
            if audit_fam is not None and audit_fam == fixer_fam:
                continue
        provenance = event.get("provenance") or env.get("provenance")
        dispatch_authentic = False
        if provenance == PROVENANCE_DISPATCH_OBSERVED and runner_vendor is not None:
            dispatch_authentic = True
        admitted_by_round.setdefault(rnd, []).append(
            (payload, dispatch_authentic, manifest_vendor, runner_vendor))
    if not admitted_by_round:
        return "fix-receipt"
    fold_round = max(admitted_by_round)
    row_bundle = admitted_by_round[fold_round]
    results = []
    expected_auditors = {}
    collection_manifest = {}
    for payload, dispatch_authentic, manifest_vendor, runner_vendor in row_bundle:
        results.append(payload)
        if dispatch_authentic and runner_vendor is not None:
            expected_auditors[fold_id] = manifest_vendor
            collection_manifest[fold_id] = runner_vendor
    audited_target = {
        "id": fold_id,
        "file": finding.get("file"),
        "line": finding.get("line"),
        "title": finding.get("title"),
        "severity": finding.get("severity"),
    }
    marker = finding.get(session_contract.FINDING_KEY_FIELD)
    if isinstance(marker, str) and marker:
        audited_target[session_contract.FINDING_KEY_FIELD] = marker
    outcome = audits.apply_audit_results(
        [audited_target],
        results,
        expected_auditors=expected_auditors,
        collection_manifest=collection_manifest,
    )
    for entry in outcome.get("audits") or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("id") != fold_id:
            continue
        ruling = entry.get("ruling")
        if ruling == "discharged":
            return None
        if ruling == "discharged-but-new-issue":
            if _new_issues_dispositioned(
                    state, fold_id, fold_round, outcome.get("newIssues") or []):
                return None
            return "new-issue-undispositioned"
    return "fix-receipt"


def _is_ancestor(repo_root, ancestor, descendant):
    if (not isinstance(ancestor, str) or not isinstance(descendant, str) or not ancestor
            or not descendant or len(ancestor) not in (40, 64)
            or len(descendant) not in (40, 64)):
        return False
    if ancestor == descendant:
        return True
    if not isinstance(repo_root, str) or not repo_root:
        return False
    try:
        proc = subprocess.run(
            ["git", "-C", repo_root, "merge-base", "--is-ancestor", ancestor, descendant],
            capture_output=True, timeout=30,
            env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")})
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def _panel_round_unified_head(journal, panel_round, roster):
    """Single cited head across every panel seat recorded for ``panel_round``, or None."""
    if not isinstance(journal, list):
        return None

    def _slot_head(seat, occ):
        for event in reversed(journal):
            if not isinstance(event, dict) or event.get("outcome") != "recorded":
                continue
            ev_seat, ev_phase, _, ev_occ, ev_round = _journal_event_slot(event)
            if (ev_seat == seat and ev_phase == PANEL_PHASE and ev_occ == occ
                    and ev_round == panel_round):
                head = event.get("headSha") or event.get("citedHead")
                if isinstance(head, str) and head:
                    return head
        return None

    heads = [_slot_head(seat, occ) for seat, occ in roster]
    if not all(heads) or len(set(heads)) != 1:
        return None
    return heads[0]


def _confirmation_panel_at_head_satisfies_scoped(ctx, rnd, certified_head):
    """A complete panel at the certified head on ``rnd`` supersedes scoped-finder for that round."""
    journal = ctx.get("journal") or []
    session_dir = ctx.get("session_dir")
    state = ctx.get("state") or {}
    if session_dir is None or not isinstance(journal, list):
        return False
    for event in journal:
        if not isinstance(event, dict):
            continue
        if event.get("outcome") != "orders-emitted" or event.get("phase") != PANEL_PHASE:
            continue
        if event.get("round") != rnd:
            continue
        roster, roster_refusal = _orders_emitted_roster_or_refusal(session_dir, event)
        if roster_refusal is not None or not roster:
            return False
        manifest, manifest_refusal = _verified_orders_manifest(session_dir, event)
        if manifest_refusal is not None or not _audited_chain_panel_coverage_ok(
                state, manifest, rnd):
            return False
        head = _panel_round_unified_head(journal, rnd, roster)
        return head == certified_head
    return False


def _scoped_finder_record_qualifies(ctx, event, certified_head):
    """Whether a scoped-finder journal row has qualifying execution evidence at the tip."""
    journal = ctx.get("journal") or []
    session_dir = ctx.get("session_dir")
    cited = event.get("headSha") or event.get("citedHead")
    seat, phase, attempt = event.get("seat"), event.get("phase"), event.get("attempt")
    occurrence, rnd = event.get("occurrence", 0), event.get("round")
    if not isinstance(seat, str) or attempt is None:
        return False
    slot_nonces = _journal_recorded_runner_nonces_for_slot(
        journal, seat, phase, attempt, occurrence, rnd)
    journal_binding = _journal_execution_binding(
        journal, seat, phase, attempt, occurrence, rnd)
    provenance = event.get("provenance")
    if provenance == PROVENANCE_DISPATCH_OBSERVED:
        if session_dir is None:
            return False
        env, _path = _load_envelope(session_dir, rnd, phase, seat, attempt, occurrence)
        envelope_evidence = env.get("executionEvidence") if isinstance(env, dict) else None
        if not isinstance(envelope_evidence, dict):
            return False
        ok, _binding = _observation_qualifies(
            event.get("executionEvidence"),
            certified_head,
            cited,
            journal_binding=journal_binding,
            recorded_nonces=slot_nonces,
            require_runner_action=True,
            envelope_run_kind_evidence=envelope_evidence,
        )
        return ok
    if provenance == PROVENANCE_HAND_LANDED:
        if session_dir is None:
            return False
        env, _path = _load_envelope(session_dir, rnd, phase, seat, attempt, occurrence)
        if env is None:
            return False
        ok, _binding = _hand_landed_evidence_qualifies(
            env,
            certified_head,
            journal_binding=journal_binding,
            recorded_nonces=slot_nonces,
            phase=phase,
        )
        if not ok:
            return False
        evidence = env.get("executionEvidence") if isinstance(env, dict) else None
        ok_read, _binding = _hand_landed_read_qualifies(evidence)
        return ok_read
    return False


def _audited_chain_legs(ctx):
    state, journal = ctx.get("state") or {}, ctx.get("journal") or []
    session_dir, certified_head = ctx.get("session_dir"), _certified_head_sha(ctx)
    meta, cfg = ctx.get("meta") or {}, (ctx.get("state") or {}).get("config") or {}
    repo_root = meta.get("repoRoot") or cfg.get("repoRoot")
    panel_head = panel_round = None
    gap_out = lambda gap: (False, gap, panel_head, panel_round)
    if not isinstance(certified_head, str) or not certified_head:
        return gap_out("verify")
    panel_candidates = []
    if isinstance(journal, list):
        for event in journal:
            if (not isinstance(event, dict) or event.get("outcome") != "orders-emitted"
                    or event.get("phase") != PANEL_PHASE):
                continue
            rnd = event.get("round")
            if isinstance(rnd, int) and not isinstance(rnd, bool):
                panel_candidates.append((rnd, event))
    if not panel_candidates or session_dir is None:
        return gap_out("panel")
    panel_candidates.sort(key=lambda item: item[0])
    panel_round, panel_event = panel_candidates[-1]
    roster, roster_refusal = _orders_emitted_roster_or_refusal(session_dir, panel_event)
    if roster_refusal is not None or not roster:
        return gap_out("panel")
    manifest, manifest_refusal = _verified_orders_manifest(session_dir, panel_event)
    if manifest_refusal is not None or not _audited_chain_panel_coverage_ok(
            state, manifest, panel_round):
        return gap_out("panel")
    panel_head = _panel_round_unified_head(journal, panel_round, roster)
    if panel_head is None:
        return gap_out("panel")
    if panel_head == certified_head and len(panel_candidates) > 1:
        for rnd, ev in reversed(panel_candidates[:-1]):
            roster_i, roster_refusal_i = _orders_emitted_roster_or_refusal(session_dir, ev)
            if roster_refusal_i is not None or not roster_i:
                continue
            manifest_i, manifest_refusal_i = _verified_orders_manifest(session_dir, ev)
            if manifest_refusal_i is not None or not _audited_chain_panel_coverage_ok(
                    state, manifest_i, rnd):
                continue
            head_i = _panel_round_unified_head(journal, rnd, roster_i)
            if head_i is None or head_i == certified_head:
                continue
            panel_round, panel_event = rnd, ev
            roster, manifest = roster_i, manifest_i
            panel_head = head_i
            break
    if not _is_ancestor(repo_root, panel_head, certified_head):
        return gap_out("descent")
    by_key, marker_refusal = _certification_findings_by_key(state)
    if marker_refusal is not None:
        return gap_out("fix-receipt")
    checked_fold_targets = set()
    for finding in by_key.values():
        if not isinstance(finding, dict):
            continue
        graded = _effective_certification_finding(finding, by_key)
        if graded.get("disposition") != "fixed":
            continue
        fold_id = _audited_chain_fold_target_id(graded, by_key)
        if not isinstance(fold_id, str) or not fold_id:
            return gap_out("fix-receipt")
        if fold_id in checked_fold_targets:
            continue
        checked_fold_targets.add(fold_id)
        receipt = graded.get("dispositionReceipt")
        if not isinstance(receipt, dict) or receipt.get("verifyResult") != "pass":
            return gap_out("fix-receipt")
        gap = _fixed_finding_has_discharging_audit(
            ctx, graded, certified_head, repo_root)
        if gap is not None:
            return gap_out(gap)
    rounds = state.get("rounds")
    if not isinstance(rounds, dict):
        return gap_out("scoped-finder")
    round_nums = [int(key) for key in rounds if str(key).isdigit()]
    if not round_nums:
        return gap_out("scoped-finder")
    scoped_events = [
        event for event in journal
        if isinstance(event, dict) and event.get("outcome") == "recorded"
        and event.get("phase") == _SCOPED_FINDER_PHASE
    ]
    for rnd in range(panel_round + 1, max(round_nums) + 1):
        satisfied = any(event.get("round") == rnd for event in scoped_events)
        if not satisfied:
            rec = rounds.get(str(rnd))
            satisfied = isinstance(rec, dict) and rec.get("scopedFinder") == "skipped-empty-surface"
        if not satisfied:
            satisfied = _confirmation_panel_at_head_satisfies_scoped(ctx, rnd, certified_head)
        if not satisfied:
            return gap_out("scoped-finder")
    scoped_ok = False
    cert_round = None
    for rnd in sorted(round_nums, reverse=True):
        rec = rounds.get(str(rnd))
        if isinstance(rec, dict) and rec.get("verifiedHead") == certified_head:
            cert_round = rnd
            break
    if cert_round is None:
        cert_round = max(round_nums)
    cert_rec = rounds.get(str(cert_round))
    if (isinstance(cert_rec, dict)
            and cert_rec.get("scopedFinder") == "skipped-empty-surface"):
        scoped_ok = True
    else:
        for event in scoped_events:
            cited = event.get("headSha") or event.get("citedHead")
            if cited != certified_head:
                continue
            if _scoped_finder_record_qualifies(ctx, event, certified_head):
                scoped_ok = True
                break
    if not scoped_ok:
        return gap_out("scoped-finder")
    if session_contract.verify_result_for_head(state, certified_head) != "pass":
        return gap_out("verify")
    return True, None, panel_head, panel_round


def _audited_chain(ctx):
    memo = ctx.get(_AUDITED_CHAIN_MEMO_KEY)
    if isinstance(memo, dict):
        return memo
    panel_head = panel_round = None
    try:
        complete, gap, panel_head, panel_round = _audited_chain_legs(ctx)
        out = {"complete": complete, "gap": gap, "panelHead": panel_head, "panelRound": panel_round}
    except Exception:
        out = {"complete": False, "gap": "panel", "panelHead": panel_head, "panelRound": panel_round}
    ctx[_AUDITED_CHAIN_MEMO_KEY] = out
    return out


def _cited_head_qualifies(ctx, cited_head, seat_round):
    certified_head = _certified_head_sha(ctx)
    if not isinstance(cited_head, str) or not cited_head:
        return False, "audited-chain-gap:panel"
    if cited_head == certified_head:
        return True, None
    chain = _audited_chain(ctx)
    if not chain.get("complete"):
        return False, "audited-chain-gap:%s" % (chain.get("gap") or "panel",)
    meta, cfg = ctx.get("meta") or {}, (ctx.get("state") or {}).get("config") or {}
    repo_root = meta.get("repoRoot") or cfg.get("repoRoot")
    panel_head = chain.get("panelHead")
    panel_round = chain.get("panelRound")
    apply_lower_bound = True
    if (
        isinstance(seat_round, int)
        and not isinstance(seat_round, bool)
        and isinstance(panel_round, int)
        and not isinstance(panel_round, bool)
    ):
        apply_lower_bound = seat_round >= panel_round
    if apply_lower_bound and not _is_ancestor(repo_root, panel_head, cited_head):
        return False, "audited-chain-gap:descent"
    if not _is_ancestor(repo_root, cited_head, certified_head):
        return False, "audited-chain-gap:descent"
    return True, None


def _run_kind_refusal_detail(phase, found_kind):
    expected = session_contract.run_kind_for_phase(phase)
    if expected is None:
        return "phase %r has no admissible runKind (found %r)" % (phase, found_kind)
    return "phase %r requires runKind %r (found %r)" % (phase, expected, found_kind)


def _dispatch_run_kind_qualifies(obs, phase):
    if not isinstance(obs, dict):
        return False, None, "evidence-run-kind-mismatch"
    run_kind_field = session_contract.EXECUTION_EVIDENCE_RUN_KIND_FIELD
    expected = session_contract.run_kind_for_phase(phase)
    found = obs.get(run_kind_field)
    if expected is None:
        return False, found, "evidence-run-kind-phase-unknown"
    if not isinstance(found, str) or found != expected:
        return False, found, "evidence-run-kind-mismatch"
    return True, found, None


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


def _envelope_run_kind_field(envelope_run_kind_evidence, evidence, field):
    if field != session_contract.EXECUTION_EVIDENCE_RUN_KIND_FIELD:
        return evidence.get(field)
    if not isinstance(envelope_run_kind_evidence, dict):
        return None
    return envelope_run_kind_evidence.get(field)


def _execution_binding_matches_journal(
    evidence,
    journal_binding,
    recorded_nonces,
    *,
    envelope_run_kind_evidence,
):
    if not isinstance(evidence, dict):
        return False, "execution-evidence-absent"
    source = evidence.get("source")
    if _execution_evidence_source_is_caller_supplied(source):
        return False, "execution-evidence-caller-supplied"
    for field in EXECUTION_EVIDENCE_BINDING_FIELDS:
        val = _envelope_run_kind_field(envelope_run_kind_evidence, evidence, field)
        if not isinstance(val, str) or not val:
            if field == session_contract.EXECUTION_EVIDENCE_RUN_KIND_FIELD:
                return False, "evidence-run-kind-mismatch"
            return False, "execution-evidence-binding-incomplete"
    if journal_binding is None:
        return False, "execution-evidence-dispatch-unrecorded"
    runner_nonce = evidence.get("runnerNonce")
    if runner_nonce not in recorded_nonces:
        return False, "execution-evidence-dispatch-unrecorded"
    for field in EXECUTION_EVIDENCE_BINDING_FIELDS:
        bound_val = _envelope_run_kind_field(envelope_run_kind_evidence, evidence, field)
        if bound_val != journal_binding.get(field):
            if field == session_contract.EXECUTION_EVIDENCE_RUN_KIND_FIELD:
                return False, "evidence-run-kind-mismatch"
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
    envelope_run_kind_evidence,
    require_runner_action=False,
    head_rule=None,
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
        if head_rule is None:
            return False, "execution-evidence-stale-head"
        ok, gap_detail = head_rule(cited_head)
        if not ok:
            return False, "execution-evidence-stale-head"
    ok, binding_failure = _execution_binding_matches_journal(
        obs,
        journal_binding,
        recorded_nonces or set(),
        envelope_run_kind_evidence=envelope_run_kind_evidence,
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
        evidence,
        journal_binding,
        recorded_nonces or set(),
        envelope_run_kind_evidence=evidence,
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
            env, env_path = _load_envelope(
                session_dir,
                rnd,
                phase,
                seat,
                attempt,
                occurrence,
            )
            if env is None:
                return _refusal(
                    "unfetched-findings",
                    env_path,
                    "dispatch-observed envelope missing or unreadable",
                )
            envelope_evidence = env.get("executionEvidence")
            if not isinstance(envelope_evidence, dict):
                return _refusal(
                    "unrun-review",
                    seat,
                    "dispatch-observed seat lacks CAS-bound executionEvidence",
                    binding_failure="execution-evidence-absent",
                )
            journal_binding = _journal_execution_binding(
                journal,
                seat,
                phase,
                attempt,
                occurrence,
                rnd,
            )
            cited = seat_entry.get("citedHead")
            head_rule_state = {}
            def _dispatch_head_rule(ch):
                ok, gap_detail = _cited_head_qualifies(ctx, ch, rnd)
                head_rule_state.update(ok=ok, gap_detail=gap_detail)
                return ok, gap_detail
            ok, binding = _observation_qualifies(
                obs,
                certified_head,
                cited,
                journal_binding=journal_binding,
                recorded_nonces=slot_nonces,
                require_runner_action=True,
                head_rule=_dispatch_head_rule,
                envelope_run_kind_evidence=envelope_evidence,
            )
            if not ok:
                detail = "dispatch-observed seat lacks qualifying execution telemetry"
                if binding == "execution-evidence-stale-head":
                    gap_detail = head_rule_state.get("gap_detail")
                    if gap_detail:
                        detail = "%s (%s)" % (detail, gap_detail)
                return _refusal(
                    "unrun-review",
                    seat,
                    detail,
                    binding_failure=binding,
                )
            rk_ok, found_kind, rk_binding = _dispatch_run_kind_qualifies(
                envelope_evidence, phase
            )
            if not rk_ok:
                return _refusal(
                    "unrun-review",
                    seat,
                    _run_kind_refusal_detail(phase, found_kind),
                    binding_failure=rk_binding,
                )
            if (
                isinstance(cited, str)
                and cited
                and isinstance(certified_head, str)
                and certified_head
                and cited != certified_head
                and head_rule_state.get("ok")
            ):
                ctx[_CHAIN_QUALIFIED_KEY] = True
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
            rk_ok, found_kind, rk_binding = _dispatch_run_kind_qualifies(evidence, phase)
            if not rk_ok:
                return _refusal(
                    "unrun-review",
                    seat,
                    _run_kind_refusal_detail(phase, found_kind),
                    binding_failure=rk_binding,
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
        provenance = seat_entry.get("provenance")
        cited = seat_entry.get("citedHead")
        if provenance == PROVENANCE_DISPATCH_OBSERVED:
            if cited:
                continue
            return _refusal(
                "unrun-review",
                seat_entry["seat"],
                "dispatch-observed seat lacks cited head on the certified head",
                binding_failure=BINDING_FAILURE_EXECUTION_EVIDENCE_HEAD_UNBOUND,
            )
        if provenance != PROVENANCE_HAND_LANDED:
            continue
        if not isinstance(cited, str) or not cited or cited == certified_head:
            continue
        chain_ok, gap_detail = _cited_head_qualifies(ctx, cited, seat_entry["round"])
        if not chain_ok:
            return _refusal(
                "unrun-review",
                seat_entry["seat"],
                "hand-landed seat cited head is stale (%s)" % (gap_detail,),
                binding_failure="execution-evidence-stale-head",
            )
        ctx[_CHAIN_QUALIFIED_KEY] = True
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
    chain_used = bool(ctx.get(_CHAIN_QUALIFIED_KEY))
    chain_info = _audited_chain(ctx) if chain_used else None
    derived_labels = [
        "schemaVersion", "scriptRan", "terminalState", "terminalCause", "seats",
        "disclosures", "certificationShape", "independence",
    ]
    if chain_used and isinstance(chain_info, dict) and chain_info.get("panelHead"):
        derived_labels.append("auditedChain")
    receipt = {
        "schemaVersion": _receipt_version(state),
        "verdict": state.get("terminal"),
        "certificationShape": _certification_shape(state, seat_rows, chain_used=chain_used),
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
            "derived": derived_labels,
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
    if chain_used and isinstance(chain_info, dict):
        ph, pr = chain_info.get("panelHead"), chain_info.get("panelRound")
        if isinstance(ph, str) and ph and isinstance(pr, int):
            receipt["auditedChain"] = {"panelHead": ph, "panelRound": pr}
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
