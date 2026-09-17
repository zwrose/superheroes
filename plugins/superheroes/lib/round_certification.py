#!/usr/bin/env python3
"""Certification receipt writer — journal on disk as sole input, no driver imports (#1271 C12)."""
from __future__ import annotations

import hashlib
import json
import os
import re

import model_registry
import seat_map_receipts
import session_mode
import version_skew

STATE_FILE = "loop-state.json"
JOURNAL_FILE = "driver-journal.jsonl"
JOURNAL_FAULT_FILE = "driver-journal-fault.jsonl"
META_FILE = "meta.json"

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
EXECUTION_EVIDENCE_OBSERVATION_FIELDS = frozenset(
    ("tokens", "toolCalls", "stdoutBytes", "wallSeconds", "source", "read", "telemetry")
)

REFUSAL_CLASSES = frozenset(
    ("unrun-review", "same-family-seat", "unfetched-findings", "disposition-without-receipt")
)

PANEL_PHASE = "dispatch-panel"

RECEIPT_FORM_CERTIFIED = "certified"
VENDOR_SOURCE_DEFAULTED = "defaulted"
ROUND_ENTRY_KEY_FORMS = {
    "verifyPasses": {
        "min_certified_version": 3,
        "non_certified_schemas": ("receipt-attested/1", "receipt-interim/1"),
    },
}
_DISCLOSE_ON_PRESENCE = ("canaryVerified",)


def _str_list(value):
    return isinstance(value, list) and all(isinstance(x, str) for x in value)


def _dict_list(value):
    return isinstance(value, list) and all(isinstance(x, dict) for x in value)


def _bool_value(value):
    return isinstance(value, bool)


def _canary_failed_shape(value):
    return isinstance(value, dict) and _str_list(value.get("seats") or [])


def _canary_verified_shape(value):
    return isinstance(value, dict) and all(isinstance(k, str) for k in value)


def _adapter_provenance_shape(value):
    if not isinstance(value, dict):
        return False
    if "byPhase" in value:
        return isinstance(value.get("byPhase"), dict)
    return True


def _order_vendor_provenance_gaps_shape(value):
    if not isinstance(value, list):
        return False
    for row in value:
        if not isinstance(row, dict):
            return False
        seat = row.get("seat")
        if not isinstance(seat, str) or not seat:
            return False
        if "occurrence" in row:
            occ = row.get("occurrence")
            if not isinstance(occ, int) or occ < 0:
                return False
    return True


def _plugin_version_skew_shape(value):
    if not _dict_list(value):
        return False
    for row in value:
        if row.get("constraint") != version_skew.CONSTRAINT:
            return False
        if not isinstance(row.get("status"), str):
            return False
    return True


RESUMABLE_DISCLOSURE_CHANNELS = {
    "fellOpen": _dict_list,
    "fellOpenProvenanceMissing": _str_list,
    "seatMapUnavailable": _str_list,
    "seatMapUnjudgeable": _str_list,
    "seatMapViolations": _dict_list,
    "pluginVersionSkew": _plugin_version_skew_shape,
    "vacuousSeats": _str_list,
    "engagedArtifactSeats": _str_list,
    "canaryUnverified": _str_list,
    "canaryFailed": _canary_failed_shape,
    "canaryOutcomeFailed": _canary_failed_shape,
    "canaryPlantUndetected": _canary_failed_shape,
    "canaryVerified": _canary_verified_shape,
    "adapterProvenance": _adapter_provenance_shape,
    "recordOrphansIgnored": _str_list,
    "orderVendorProvenanceGaps": _order_vendor_provenance_gaps_shape,
    "priorCommentsUnavailable": _bool_value,
    "verifyPasses": _dict_list,
    "judgmentDispositions": _dict_list,
    "gateGuidanceRowCarried": _dict_list,
}


def _normalize_adapter_provenance(prov):
    if not isinstance(prov, dict):
        return {}
    if "byPhase" in prov:
        by_phase = prov.get("byPhase")
        if not isinstance(by_phase, dict):
            return {}
        return dict(by_phase)
    if prov:
        return {"unknown-phase": dict(prov)}
    return {}


def _declared_disclosures(entry):
    if not isinstance(entry, dict):
        entry = {}
    out = {}
    for chan, shape_ok in RESUMABLE_DISCLOSURE_CHANNELS.items():
        if chan in _DISCLOSE_ON_PRESENCE:
            if chan not in entry:
                continue
            value = entry.get(chan)
        else:
            value = entry.get(chan)
            if not value:
                continue
        if not shape_ok(value):
            continue
        out[chan] = value
    return out


def _round_entry_key_declared(key, schema, certified_version):
    decl = ROUND_ENTRY_KEY_FORMS.get(key)
    if decl is None:
        return True
    if certified_version is not None:
        return certified_version >= decl["min_certified_version"]
    return schema in decl["non_certified_schemas"]


def _round_entry_key_allowed(key, form, state):
    if key not in ROUND_ENTRY_KEY_FORMS:
        return True
    if form == RECEIPT_FORM_CERTIFIED:
        return _round_entry_key_declared(key, None, _receipt_version(state))
    return True


def _receipt_round_disclosures(entry, form, state):
    return {
        chan: value
        for chan, value in _declared_disclosures(entry).items()
        if _round_entry_key_allowed(chan, form, state)
    }


def _degraded(state):
    return bool(state.get("independenceDegraded"))


def _base_degraded(state):
    return bool((state.get("config") or {}).get("baseDegraded"))


def _maker_author_family(state):
    cfg = state.get("config") or {}
    return model_registry.family_for("code-fixer", cfg.get("fixerVendor"))


def _same_family_seats_for_receipt(state):
    return seat_map_receipts.same_family_seats(state, _maker_author_family(state))


def _same_family_degraded(state):
    return bool(_same_family_seats_for_receipt(state))


def _skew_record_identity(row):
    return seat_map_receipts._skew_record_identity(row)


def _skew_records(state):
    seen = set()
    merged = []
    for rec in (state.get("rounds") or {}).values():
        if not isinstance(rec, dict):
            continue
        skew = rec.get("pluginVersionSkew")
        if not isinstance(skew, list):
            continue
        for row in skew:
            key = _skew_record_identity(row)
            if key is None:
                continue
            if not version_skew.appends_degradation(row.get("status")):
                continue
            if key in seen:
                continue
            seen.add(key)
            merged.append(row)
    for row in seat_map_receipts.skew_records(state):
        key = _skew_record_identity(row)
        if key is None or key in seen:
            continue
        seen.add(key)
        merged.append(row)
    merged.sort(
        key=lambda item: (
            str(item.get("constraint", "")),
            str(item.get("status", "")),
            str(item.get("detail", "")),
            str(item.get("inspectedRoot", "")),
        ),
    )
    return merged


def _skew_degraded(state):
    return bool(_skew_records(state))


def _seat_map_violations(state):
    seen = set()
    merged = []
    author = _maker_author_family(state)
    for rec in (state.get("rounds") or {}).values():
        if not isinstance(rec, dict):
            continue
        violations = rec.get("seatMapViolations")
        if not isinstance(violations, list):
            continue
        for v in violations:
            if not isinstance(v, dict):
                continue
            key = (str(v.get("constraint", "")), str(v.get("seat") or ""))
            if key in seen:
                continue
            seen.add(key)
            merged.append(v)
    for v in seat_map_receipts.unexcused_violations(state, author):
        key = (str(v.get("constraint", "")), str(v.get("seat") or ""))
        if key in seen:
            continue
        seen.add(key)
        merged.append(v)
    merged.sort(
        key=lambda item: (str(item.get("constraint", "")), str(item.get("seat") or "")),
    )
    return merged


def _seat_map_violated(state):
    return bool(_seat_map_violations(state))


def _seat_map_violation_breach_prose(v):
    c = str(v.get("constraint") or "unknown")
    s = v.get("seat")
    ev = v.get("evidence")
    if ev == "unproven-liveness":
        ev_phrase = "excusal unprovable — liveness evidence unusable"
    elif ev == "alternative-live":
        ev_phrase = "an alternative was available"
    else:
        ev_phrase = None
    if isinstance(s, str) and s and ev_phrase:
        return "%s (seat %s; %s)" % (c, s, ev_phrase)
    if ev_phrase:
        return "%s (%s)" % (c, ev_phrase)
    if isinstance(s, str) and s:
        return "%s (seat %s)" % (c, s)
    return c


def _seat_pin_excused_seats(state):
    seats = set()
    for rec in seat_map_receipts.pin_excused_records(state, _maker_author_family(state)):
        for s in rec.get("excusedSeats") or []:
            if isinstance(s, str) and s:
                seats.add(s)
    return sorted(seats)


def _seat_map_unjudgeable(state):
    for rec in (state.get("rounds") or {}).values():
        if not isinstance(rec, dict):
            continue
        if rec.get("seatMapUnjudgeable"):
            return True
    return bool(
        seat_map_receipts.unjudgeable_receipts(state, _maker_author_family(state))
    )


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
    meta = ctx.get("meta") or {}
    if meta.get("producer") != "run-loop":
        for check in (
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


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _receipt_version(state):
    version = state.get("schemaVersion")
    if isinstance(version, bool) or not isinstance(version, int):
        return SCHEMA_VERSION
    if version in SUPPORTED_STATE_VERSIONS:
        return version
    return SCHEMA_VERSION


def _author_family(state):
    cfg = state.get("config") or {}
    vendor = cfg.get("fixerVendor") or "claude"
    return model_registry.family_for("code-fixer", vendor)


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
    author = _author_family(state)
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
        key = (
            ident.get("phase"),
            ident.get("seat"),
            ident.get("occurrence", 0),
            ident.get("attempt"),
        )
        if key[0] is None or key[1] is None or key[3] is None:
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


def _envelope_path(session_dir, rnd, phase, seat_key, attempt, occurrence=0):
    skey = _storage_key(seat_key, occurrence)
    return os.path.join(
        session_dir,
        "round-%d" % rnd,
        "seats",
        phase,
        "%s.a%d.json" % (skey, attempt),
    )


def _storage_key(seat_key, occurrence=0):
    slug = re.sub(r"[^a-z0-9]+", "-", seat_key.lower()).strip("-")
    if len(slug) > 40:
        slug = slug[:40].rstrip("-")
    if not slug:
        slug = "seat"
    digest = hashlib.sha256(seat_key.encode("utf-8")).hexdigest()[:16]
    base = "%s-%s" % (slug, digest)
    if occurrence:
        return "%s-o%d" % (base, occurrence)
    return base


def _load_envelope(session_dir, rnd, phase, seat, attempt, occurrence=0):
    path = _envelope_path(session_dir, rnd, phase, seat, attempt, occurrence)
    if not os.path.exists(path):
        return None, path
    obj = _read_json(path)
    if not isinstance(obj, dict):
        return None, path
    return obj, path


def _journal_observation_for_seat(journal, seat, phase=None):
    for event in reversed(journal):
        if event.get("outcome") != "recorded":
            continue
        if event.get("seat") != seat and (
            not isinstance(event.get("recordIdentity"), dict)
            or event["recordIdentity"].get("seat") != seat
        ):
            continue
        if phase is not None and event.get("phase") != phase:
            continue
        obs = event.get("executionEvidence")
        if isinstance(obs, dict):
            return obs
    return None


def _observation_qualifies(obs, certified_head, cited_head):
    if not isinstance(obs, dict):
        return False, "execution-evidence-absent"
    read = obs.get("read")
    if read not in EXECUTION_EVIDENCE_READ_VALUES:
        return False, "execution-evidence-read-invalid"
    if read != "engaged":
        return False, "execution-evidence-not-engaged"
    if cited_head and certified_head and cited_head != certified_head:
        return False, "execution-evidence-stale-head"
    return True, None


def _hand_landed_evidence_qualifies(envelope, certified_head):
    evidence = envelope.get("executionEvidence") if isinstance(envelope, dict) else None
    if not isinstance(evidence, dict):
        return False, "execution-evidence-absent"
    for field in ("source", "runnerNonce", "recordDigest", "resultDigest", "resultKind"):
        val = evidence.get(field)
        if not isinstance(val, str) or not val:
            return False, "execution-evidence-binding-incomplete"
    cited = envelope.get("headSha") or evidence.get("headSha")
    if cited and certified_head and cited != certified_head:
        return False, "execution-evidence-stale-head"
    return True, None


def check_unrun_review(ctx):
    state = ctx["state"]
    journal = ctx["journal"]
    session_dir = ctx["session_dir"]
    certified_head = _certified_head_sha(ctx)
    seats = _collect_seats(ctx)
    for seat_entry in seats:
        seat = seat_entry["seat"]
        provenance = seat_entry.get("provenance")
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
            obs = _journal_observation_for_seat(journal, seat, seat_entry.get("phase"))
            ok, binding = _observation_qualifies(
                obs, certified_head, seat_entry.get("citedHead")
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
            ok, binding = _hand_landed_evidence_qualifies(env, certified_head)
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
    declared = _declared_same_family_seats(state)
    author = _author_family(state)
    if not author:
        if declared:
            cfg = state.get("config") or {}
            vendor = cfg.get("fixerVendor") or "claude"
            return _refusal(
                "unfetched-findings",
                _seat_map_artifact(state),
                "maker family could not be resolved for fixerVendor %r" % (vendor,),
            )
        return None
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
        payload_sha = env.get("payloadSha256")
        if payload_sha and ident.get("payloadSha256") and payload_sha != ident["payloadSha256"]:
            return _refusal(
                "unfetched-findings",
                path,
                "journal payload hash disagrees with landed envelope",
                binding_failure="journal-envelope-mismatch",
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
            if severity == "Important":
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
    if seats:
        return seats
    smap = _effective_seat_map(state)
    seat_names = smap.get("seats") if isinstance(smap, dict) else None
    if isinstance(seat_names, dict):
        rnd = state.get("round") or 1
        for seat in sorted(seat_names):
            seats.append(
                {
                    "seat": seat,
                    "phase": PANEL_PHASE,
                    "round": rnd,
                    "attempt": 0,
                    "occurrence": 0,
                    "provenance": PROVENANCE_DISPATCH_OBSERVED,
                    "citedHead": _certified_head_sha(ctx),
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
        cause_entry = _TERMINAL_CAUSE_TABLE.get((verdict, decision_key))
        if cause_entry is not None:
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
    cause_entry = _TERMINAL_CAUSE_TABLE.get((verdict, decision_key))
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


def _build_degraded_prose(state, form):
    cfg = state.get("config") or {}
    degraded = []
    if _degraded(state):
        degraded.append(
            "independence: a single live vendor — the fix's auditor is the fixer's "
            "vendor; independence degraded and named in the certification shape"
        )
    if _base_degraded(state):
        degraded.append(
            "base: reviewed against a base whose fetch degraded (%s) — the pin may be stale; "
            "named in the certification shape"
            % (cfg.get("baseFetch") or "baseFetch absent")
        )
    if _same_family_degraded(state):
        degraded.append(
            "panel independence: seat(s) %s were filled with the MAKER's own model family — no "
            "alternative family was live; disclosed by the seat map and named in the certification "
            "shape" % ", ".join(_same_family_seats_for_receipt(state))
        )
    if _skew_degraded(state):
        _skew_reasons = []
        for rec in _skew_records(state):
            reason = rec.get("reason")
            if isinstance(reason, str) and reason:
                _skew_reasons.append(reason)
        if _skew_reasons:
            degraded.append(
                "%s; disclosed by the seat map and named in the certification shape"
                % "; ".join(_skew_reasons)
            )
        else:
            degraded.append(
                "plugin-version-skew: the review ran under a plugin/repository semantics skew "
                "but no usable reason text was recorded; disclosed by the seat map and named in "
                "the certification shape"
            )
    _pin_seats = _seat_pin_excused_seats(state)
    if _pin_seats:
        degraded.append(
            "seat-map pin excusal: seat(s) %s authorized a disclosed constraint relaxation via pin; "
            "named in the certification shape" % ", ".join(_pin_seats)
        )
    if _seat_map_violated(state):
        _viol_parts = []
        for v in _seat_map_violations(state):
            _viol_parts.append(_seat_map_violation_breach_prose(v))
        _shape = (state.get("certification") or {}).get("shape")
        if isinstance(_shape, str) and _shape.endswith("-constraint-violated"):
            degraded.append(
                "seat-map constraint breach: %s — certification shape marked -constraint-violated"
                % ", ".join(_viol_parts)
            )
        else:
            degraded.append(
                "seat-map constraint breach: %s — breach recorded; certification withheld"
                % ", ".join(_viol_parts)
            )
    skipped_blockers = []
    for s in state.get("_skippedBlockers") or []:
        if not isinstance(s, dict):
            continue
        skipped_blockers.append(
            {
                "id": s.get("id"),
                "title": s.get("title"),
                "severity": s.get("severity"),
                "reason": s.get("reason"),
            }
        )
        degraded.append(
            "skipped-blocker: %r (%s:%s) owner-skipped as a product-choice tradeoff — "
            "reason: %s"
            % (s.get("title"), s.get("file"), s.get("line"), s.get("reason"))
        )
    _emitted_seat_map_unjudgeable = False
    for rkey in sorted((state.get("rounds") or {}), key=lambda k: int(k) if str(k).isdigit() else 0):
        rrec = state["rounds"][rkey]
        declared = _receipt_round_disclosures(rrec, form, state)
        for row in declared.get("fellOpen") or []:
            degraded.append(
                "reviewer-fell-open (round %s): seat %s configured %s forfeited (%s) → re-ran on %s; "
                "that seat's cross-vendor mix degraded"
                % (
                    rkey,
                    row.get("seat"),
                    row.get("configured"),
                    row.get("reason"),
                    row.get("ran"),
                )
            )
        miss = declared.get("fellOpenProvenanceMissing")
        if miss:
            degraded.append(
                "reviewer-fell-open-provenance-unavailable (round %s): cross-vendor seat(s) %s ran "
                "without a trusted ranManifest entry — fall-open provenance unverified"
                % (rkey, ", ".join(miss))
            )
        smu = declared.get("seatMapUnavailable")
        if smu:
            degraded.append(
                "reviewer-fell-open-seatmap-unavailable (round %s): live panel vendor(s) %s "
                "but no seat map submitted — fall-open provenance unverified for the panel"
                % (rkey, ", ".join(smu))
            )
        smuj = declared.get("seatMapUnjudgeable")
        if smuj:
            _emitted_seat_map_unjudgeable = True
            degraded.append(
                "seat-map-unjudgeable (round %s): a seat map was submitted and is readable, but "
                "its violation basis is incomplete (%s) — \"no breach\" is unproven rather than clean"
                % (rkey, ", ".join(smuj))
            )
        vac = declared.get("vacuousSeats")
        if vac:
            degraded.append(
                "vacuous-seat (round %s): seat(s) %s returned no findings and no verifiable "
                "investigation record — classed as never-ran" % (rkey, ", ".join(vac))
            )
        eng_art = declared.get("engagedArtifactSeats")
        if eng_art:
            degraded.append(
                "engaged-artifact-seat (round %s): seat(s) %s produced a review our transport "
                "could not carry — they do not count toward certification; salvaged artifacts "
                "are available for independent verification" % (rkey, ", ".join(eng_art))
            )
        cuv = declared.get("canaryUnverified")
        if cuv:
            cv = declared.get("canaryVerified")
            verified_vendors = []
            if isinstance(cv, dict):
                if cv and all(isinstance(v, dict) for v in cv.values()):
                    verified_vendors = sorted(cv)
                elif cv:
                    verified_vendors = ["(probe submitted)"]
            probe_note = ""
            if verified_vendors:
                probe_note = " (engaged probe recorded for vendor(s) %s)" % ", ".join(
                    verified_vendors
                )
            degraded.append(
                "canary-unverified (round %s): cross-vendor seat(s) %s returned zero findings "
                "with no engaged control probe for their vendor%s — external-seat liveness unverified"
                % (rkey, ", ".join(cuv), probe_note)
            )
        cf = declared.get("canaryFailed")
        if cf:
            seats_down = cf.get("seats") if isinstance(cf, dict) else []
            detail = cf.get("detail") if isinstance(cf, dict) else None
            evidence = cf.get("evidence") if isinstance(cf, dict) else None
            engaged_failure = isinstance(cf, dict) and cf.get("engagedFailure") is True
            if isinstance(cf, dict) and isinstance(cf.get("vendors"), dict):
                parts = []
                for vendor, vinfo in sorted(cf["vendors"].items()):
                    if not isinstance(vinfo, dict):
                        continue
                    ev = vinfo.get("evidence")
                    ev_note = ""
                    if isinstance(ev, dict) and ev:
                        ev_note = "; evidence=%s" % ev
                    default_detail = "outcome failure" if engaged_failure else "engaged not true"
                    parts.append(
                        "vendor %s (%s%s)"
                        % (vendor, vinfo.get("detail") or default_detail, ev_note)
                    )
                default_detail = "outcome failure" if engaged_failure else "engaged not true"
                detail_str = "; ".join(parts) if parts else (detail or default_detail)
            else:
                default_detail = "outcome failure" if engaged_failure else "engaged not true"
                detail_str = detail or default_detail
                if evidence and isinstance(evidence, dict):
                    detail_str = "%s; evidence=%s" % (detail_str, evidence)
            if engaged_failure:
                degraded.append(
                    "canary-outcome-failed (round %s): the control probe was engaged but "
                    "reported outcome failure (%s) — cross-vendor seat(s) %s remain run; panel "
                    "certification withheld"
                    % (rkey, detail_str, ", ".join(seats_down or []))
                )
            else:
                degraded.append(
                    "canary-failed (round %s): the control probe showed no engagement (%s) — "
                    "cross-vendor seat(s) %s downgraded to never-ran"
                    % (rkey, detail_str, ", ".join(seats_down or []))
                )
        cof = declared.get("canaryOutcomeFailed")
        if cof:
            seats_outcome_failed = cof.get("seats") if isinstance(cof, dict) else []
            detail = cof.get("detail") if isinstance(cof, dict) else None
            evidence = cof.get("evidence") if isinstance(cof, dict) else None
            if isinstance(cof, dict) and isinstance(cof.get("vendors"), dict):
                parts = []
                for vendor, vinfo in sorted(cof["vendors"].items()):
                    if not isinstance(vinfo, dict):
                        continue
                    ev = vinfo.get("evidence")
                    ev_note = ""
                    if isinstance(ev, dict) and ev:
                        ev_note = "; evidence=%s" % ev
                    parts.append(
                        "vendor %s (%s%s)"
                        % (vendor, vinfo.get("detail") or "outcome failure", ev_note)
                    )
                detail_str = "; ".join(parts) if parts else (detail or "outcome failure")
            else:
                detail_str = detail or "outcome failure"
                if evidence and isinstance(evidence, dict):
                    detail_str = "%s; evidence=%s" % (detail_str, evidence)
            degraded.append(
                "canary-outcome-failed (round %s): the control probe was engaged but "
                "reported outcome failure (%s) — cross-vendor seat(s) %s remain run; panel "
                "certification withheld"
                % (rkey, detail_str, ", ".join(seats_outcome_failed or []))
            )
        cpu = declared.get("canaryPlantUndetected")
        if cpu:
            seats_undetected = cpu.get("seats") if isinstance(cpu, dict) else []
            detail = cpu.get("detail") if isinstance(cpu, dict) else None
            evidence = cpu.get("evidence") if isinstance(cpu, dict) else None
            if isinstance(cpu, dict) and isinstance(cpu.get("vendors"), dict):
                parts = []
                for vendor, vinfo in sorted(cpu["vendors"].items()):
                    if not isinstance(vinfo, dict):
                        continue
                    ev = vinfo.get("evidence")
                    ev_note = ""
                    if isinstance(ev, dict) and ev:
                        ev_note = "; evidence=%s" % ev
                    parts.append(
                        "vendor %s (%s%s)"
                        % (vendor, vinfo.get("detail") or "plant not detected", ev_note)
                    )
                detail_str = "; ".join(parts) if parts else (detail or "plant not detected")
            else:
                detail_str = detail or "plant not detected"
                if evidence and isinstance(evidence, dict):
                    detail_str = "%s; evidence=%s" % (detail_str, evidence)
            degraded.append(
                "canary-plant-undetected (round %s): the control probe was engaged but missed "
                "the planted defect (%s) — cross-vendor seat(s) %s remain run; panel "
                "certification withheld"
                % (rkey, detail_str, ", ".join(seats_undetected or []))
            )
        roi = declared.get("recordOrphansIgnored")
        if roi:
            degraded.append(
                "record-orphans-ignored (round %s): hand submit folded with durable seat record(s) "
                "%s still at this slot — records ignored (session already on hand-submit path)"
                % (rkey, ", ".join(roi))
            )
        pcu = declared.get("priorCommentsUnavailable")
        if pcu:
            degraded.append(
                "prior-comments-unavailable (round %s): orchestrator did not supply "
                "prior-comments.json in PR mode — panel ran without prior PR comments; any claim "
                "that prior comments were considered is not supported for this round"
                % rkey
            )
        jd = declared.get("judgmentDispositions")
        if isinstance(jd, list) and jd:
            fail_closed = [e for e in jd if isinstance(e, dict) and e.get("failClosed")]
            if fail_closed:
                degraded.append(
                    "judgment-fail-closed (round %s): %d judgment blocker(s) had no valid owner "
                    "disposition — owner ruling not recorded; loop defaulted to fix-as-suggested"
                    % (rkey, len(fail_closed))
                )
        ggc = declared.get("gateGuidanceRowCarried")
        if ggc:
            degraded.append(
                "gate-guidance-row-carried (round %s): %d fix-batch row(s) carried the guidance "
                "key while the fold recorded none for them — row-carried text is never rendered "
                "as owner guidance" % (rkey, len(ggc))
            )
        ovg = declared.get("orderVendorProvenanceGaps")
        if ovg:
            seats = []
            for row in ovg:
                if not isinstance(row, dict):
                    continue
                seat = row.get("seat")
                if not (isinstance(seat, str) and seat):
                    continue
                label = seat
                phase_name = row.get("phase")
                if isinstance(phase_name, str) and phase_name:
                    label = "%s@%s" % (label, phase_name)
                if row.get("vendorSource") == VENDOR_SOURCE_DEFAULTED:
                    label = "%s (vendor defaulted — engine preferences unreadable)" % label
                seats.append(label)
            if seats:
                degraded.append(
                    "order-vendor-provenance-gap (round %s): seat(s) %s emitted without a resolved "
                    "vendor" % (rkey, ", ".join(seats))
                )
        prov_by_phase = _normalize_adapter_provenance(declared.get("adapterProvenance"))
        for phase_name, prov in prov_by_phase.items():
            if not isinstance(prov, dict):
                continue
            if prov.get("dispatchManifestUnavailable"):
                degraded.append(
                    "adapter-provenance (round %s, %s): dispatch manifest unavailable — trusted "
                    "ranManifest/collectionManifest omitted" % (rkey, phase_name)
                )
            mismatch = prov.get("vendorEchoMismatch")
            if isinstance(mismatch, list) and mismatch:
                parts = [
                    "%s echo=%r manifest=%r" % (row.get("seat"), row.get("echo"), row.get("manifest"))
                    for row in mismatch
                    if isinstance(row, dict)
                ]
                degraded.append(
                    "adapter-provenance (round %s, %s): vendor echo mismatch on seat(s): %s"
                    % (rkey, phase_name, "; ".join(parts))
                )
    _run_unj = seat_map_receipts.unjudgeable_run_level_disclosure(
        state,
        _maker_author_family(state),
        per_round_emitted=_emitted_seat_map_unjudgeable,
        no_seat_map_submitted=not seat_map_receipts.any_seats(state),
    )
    if _run_unj and _seat_map_unjudgeable(state):
        degraded.append(_run_unj)
    return degraded, skipped_blockers


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
        {
            "id": f.get("id"),
            "file": f.get("file"),
            "line": f.get("line"),
            "title": f.get("title"),
            "severity": f.get("severity"),
            "verdict": f.get("verdict"),
            "challenge": f.get("challenge"),
            "unverified": f.get("unverified"),
        }
        for f in (state.get("findings") or [])
        if isinstance(f, dict)
    ]
    rounds = _build_receipt_rounds(state, form)
    degraded, skipped_blockers = _build_degraded_prose(state, form)
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
        "seatMap": seat_map_receipts.emit_receipt_seat_map(state, _maker_author_family(state)),
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
