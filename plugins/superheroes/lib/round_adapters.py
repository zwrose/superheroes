#!/usr/bin/env python3
"""Per-phase aggregate adapters (#723): recorded seat envelopes -> the artifact the phase's
EXISTING `round_driver._fold_<phase>` already consumes.

One pure function per concern, none of which mutate anything:

  * `roster_for(phase, state, config)`  — the seat keys this phase owes, from driver state.
  * `payload_fault(phase, payload, seat_key)` — record-time per-field validation of ONE seat's
    payload, naming the offending field.
  * `missing_policy(phase)` — what a `seat-missing/1` envelope (or an unlanded roster seat) does
    to the fold: `seat-status` | `refuse-fold` | `fold-fail-closed`.
  * `assemble(phase, envelopes, state, config, dispatch_manifest, canary)` — the artifact, or
    `(None, reason)`. NEVER raises.

Design rules this module is bound by (each one is a defect class it exists to prevent):

TRUST. `ranManifest` (panel) and `collectionManifest` (audits) are DISPATCH PROVENANCE and come
ONLY from `dispatch_manifest` — the orchestrator's own out-of-band record of which engine it
seated. A seat envelope's `vendor`/`model` is a claimant-controlled ADVISORY ECHO: a forfeiting or
misrouted worker simply echoes the expected value, so the echo authenticates nothing (see
`audits.apply_audit_results` and `round_driver._fell_open_rows`, both explicit on this). A
disagreement between the echo and the manifest is DISCLOSED in the artifact's `provenance` block;
it never populates a manifest. With no `dispatch_manifest` the manifest key is OMITTED so the
driver's existing provenance-unavailable disclosure fires — a synthesized manifest would silently
authenticate an unauthenticated run.

SILENCE NEVER CERTIFIES. `missing_policy` is the whole safety surface of this module. A
`record-missing` seat must never become a success artifact: single-seat phases REFUSE to assemble
(`missing-seat-refuse-fold:<seat>`) rather than emit `{"findings": []}`, because an empty
scoped-finder artifact settles the delta and can certify a round nobody reviewed.

DURABILITY. The fixer's `headDiffPath` is opened at FOLD time, so a path into caller-controlled
space can change between record and fold. When the envelope carries a store copy
(`payload["headDiffStorePath"]`) the artifact emits THAT path; falling back to the caller's path is
disclosed in `provenance`.

stdlib only; runs on Python 3.9 and 3.12 (no `match`, no PEP-604 runtime annotations).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audits  # noqa: E402
import dispatch_outcome  # noqa: E402
import round_phases  # noqa: E402
import round_records  # noqa: E402
import seat_map_receipts  # noqa: E402
import verification  # noqa: E402
import payload_contracts  # noqa: E402

# =============================================================================================
# phases, seat keys, policies
# =============================================================================================

P_PANEL = round_phases.P_PANEL
P_VERIFIERS = round_phases.P_VERIFIERS
P_SYNTHESIS = round_phases.P_SYNTHESIS
P_GAPSWEEP = round_phases.P_GAPSWEEP
P_AUDITS = round_phases.P_AUDITS
P_SCOPED = round_phases.P_SCOPED
P_VERIFY = round_phases.P_VERIFY
P_FIXER = round_phases.P_FIXER

# Re-export payload-contract names from the single contract home (CONVENTIONS §11 Pattern 1).
ADAPTER_PHASES = payload_contracts.ADAPTER_PHASES
SEAT_SYNTHESIS = payload_contracts.SEAT_SYNTHESIS
SEAT_GAPSWEEP = payload_contracts.SEAT_GAPSWEEP
SEAT_SCOPED = payload_contracts.SEAT_SCOPED
SEAT_VERIFY = payload_contracts.SEAT_VERIFY
SEAT_FIXER = payload_contracts.SEAT_FIXER
RULING_NEW_ISSUE = payload_contracts.RULING_NEW_ISSUE
VACUOUS_FIELD = payload_contracts.VACUOUS_FIELD
TYPE_TOKENS = payload_contracts.TYPE_TOKENS
payload_contract = payload_contracts.payload_contract
payload_fault = payload_contracts.payload_fault
_label = payload_contracts._label
_type_name = payload_contracts._type_name

# Single-seat phases: one dispatch, one seat, one payload.
_SINGLE_SEAT = {
    P_SYNTHESIS: SEAT_SYNTHESIS,
    P_GAPSWEEP: SEAT_GAPSWEEP,
    P_SCOPED: SEAT_SCOPED,
    P_VERIFY: SEAT_VERIFY,
    P_FIXER: SEAT_FIXER,
}

# Phases fulfilled by the orchestrator itself — no `dispatch-*` orders manifest is emitted.
ORCHESTRATOR_FULFILLED_PHASES = (P_VERIFY,)


def is_orchestrator_fulfilled(phase):
    """True when the orchestrator fulfils the phase and no orders manifest is emitted.

    Unknown phase strings fall to the conservative side (False) — treated as seat phases that
    require an anchor."""
    return isinstance(phase, str) and phase in ORCHESTRATOR_FULFILLED_PHASES


def orchestrator_payload_fault(phase, payload):
    """Submit-shape guard for orchestrator-fulfilled phase payloads. None when well-formed."""
    if phase == P_VERIFY:
        return round_phases.verify_result_fault(payload)
    return "orchestrator-payload-unknown-phase:%s" % _label(phase)


# A verifier seat is one CLUSTER of the round's staged findings.
VERIFIER_SEAT_PREFIX = "verifier:"

# `missing_policy` values.
MISSING_SEAT_STATUS = "seat-status"
MISSING_REFUSE_FOLD = "refuse-fold"
MISSING_FOLD_FAIL_CLOSED = "fold-fail-closed"

_MISSING_POLICY = {
    # The panel fold ALREADY models an absent seat: `seat_status[dim] = "missing"`, the dim rides
    # `missingSeats`, `fullPanelRan` goes False. Omitting the dim from `seats` lands exactly there.
    P_PANEL: MISSING_SEAT_STATUS,
    # A silent cluster leaves its findings unverified — `apply_verdicts` keeps them PLAUSIBLE. An
    # EMPTY verdict list would read as "verified, nothing found", so the cluster is OMITTED.
    P_VERIFIERS: MISSING_FOLD_FAIL_CLOSED,
    # A silent auditor leaves its target `unaudited` -> not-discharged. Omit the result.
    P_AUDITS: MISSING_FOLD_FAIL_CLOSED,
    # Single-seat phases: an empty success artifact could let the run certify. Refuse.
    P_SYNTHESIS: MISSING_REFUSE_FOLD,
    P_GAPSWEEP: MISSING_REFUSE_FOLD,
    P_SCOPED: MISSING_REFUSE_FOLD,
    P_VERIFY: MISSING_REFUSE_FOLD,
    P_FIXER: MISSING_REFUSE_FOLD,
}

_KIND_RESULT = "result"
_KIND_MISSING = "missing"

# Reason emitted for a roster seat that landed no envelope at all (distinct from a recorded
# `seat-missing/1`, which carries the dispatch's own reason).
NO_ENVELOPE = "no-envelope"



def missing_policy(phase):
    """What a missing seat does to `phase`'s fold.

    An UNKNOWN phase answers the most conservative of the three (`refuse-fold`) rather than None:
    a caller branching on the value must never fall open on a phase this module does not model.
    """
    return _MISSING_POLICY.get(phase, MISSING_REFUSE_FOLD)


# =============================================================================================
# roster
# =============================================================================================

def roster_for(phase, state, config):

    """(seat keys this phase owes, reason_or_None).

    Deterministic. Order is SEMANTIC on every multi-seat phase and is therefore preserved, not
    sorted: the panel folds in `_panel_dimensions` order, the verifiers artifact concatenates in
    cluster order (`verification.cluster_findings` already sorts by (file, bucket)), and the audits
    artifact lists results in audit-target order. A reason is returned only when the roster cannot
    be derived at all — never an empty roster standing in for an underivable one.
    """
    if phase not in ADAPTER_PHASES:
        return [], "unknown-phase:%s" % _label(phase)
    st = state if isinstance(state, dict) else {}
    cfg = config if isinstance(config, dict) else {}
    if phase == P_PANEL:
        return list(round_phases.panel_dimensions(cfg)), None
    if phase == P_VERIFIERS:
        staged = verification.stage_ids(st.get("_toVerify") or [])
        keys = []
        for index, cluster in enumerate(verification.cluster_findings(staged)):
            key = cluster.get("key") if isinstance(cluster, dict) else None
            if not isinstance(key, str) or not key:
                return [], "verifier-cluster-has-no-key:index-%d" % index
            keys.append(VERIFIER_SEAT_PREFIX + key)
        return keys, None
    if phase == P_AUDITS:
        targets = st.get("_auditTargets")
        if targets is None:
            targets = []
        if not isinstance(targets, list):
            return [], "audit-targets-not-a-list:%s" % _type_name(targets)
        keys = []
        for index, target in enumerate(targets):
            if not isinstance(target, dict):
                return [], "audit-target-not-an-object:index-%d" % index
            tid = target.get("id")
            if not isinstance(tid, str) or not tid:
                return [], "audit-target-has-no-id:index-%d" % index
            keys.append(tid)
        return keys, None
    return [_SINGLE_SEAT[phase]], None


def _roster_slots(keys):
    """[(key, occurrence)] — the roster expanded so a REPEATED key stays addressable.

    Two DISTINCT audit targets can legitimately share one roster seat key (same per-location id
    before occurrence suffixing), so the roster is occurrence-indexed exactly the way
    `round_records.storage_key` is: identity is (seat_key, occurrence), never the seat key alone. The expansion itself is DELEGATED to
    `round_records.roster_slots` — the driver's advance path enumerates the same slots to read the
    store, and two independent expansions could disagree about which record is which seat.
    """
    return round_records.roster_slots(keys)



# =============================================================================================
# envelope indexing
# =============================================================================================

def _index_envelopes(phase, envelopes, roster):
    """({(seat, occurrence): entry}, reason_or_None). Every fail-closed edge lives here."""
    if not isinstance(envelopes, list):
        return None, "envelopes-not-a-list:%s" % _type_name(envelopes)
    slots = _roster_slots(roster)
    slot_set = set(slots)
    seats = set(key for key, _ in slots)
    indexed = {}
    for index, envelope in enumerate(envelopes):
        if not isinstance(envelope, dict):
            return None, "envelope-not-an-object:index-%d:%s" % (index, _type_name(envelope))
        seat = envelope.get("seat")
        if not isinstance(seat, str) or not seat:
            return None, "envelope-has-no-seat:index-%d" % index
        occurrence = envelope.get("occurrence", 0)
        if isinstance(occurrence, bool) or not isinstance(occurrence, int) or occurrence < 0:
            return None, "envelope-bad-occurrence:%s:%s" % (seat, _label(occurrence))
        if seat not in seats:
            return None, "seat-not-in-roster:%s" % seat
        if (seat, occurrence) not in slot_set:
            return None, "seat-occurrence-not-in-roster:%s#%d" % (seat, occurrence)
        if (seat, occurrence) in indexed:
            # Ambiguous — NEVER last-wins. Two records for one seat is a dispatch accounting fault
            # the caller must resolve; picking one would silently discard a real result.
            return None, "duplicate-envelope:%s#%d" % (seat, occurrence)
        schema = envelope.get("schema")
        if schema == round_records.SEAT_RESULT_SCHEMA:
            if "payload" not in envelope:
                return None, "seat-result-missing-payload:%s" % seat
            payload = envelope.get("payload")
            fault = payload_fault(phase, payload, seat)
            if fault:
                return None, "payload-fault:%s:%s" % (seat, fault)
            indexed[(seat, occurrence)] = {"kind": _KIND_RESULT, "payload": payload,
                                           "envelope": envelope}
        elif schema == round_records.SEAT_MISSING_SCHEMA:
            indexed[(seat, occurrence)] = {"kind": _KIND_MISSING, "payload": None,
                                           "envelope": envelope}
        else:
            return None, "unknown-envelope-schema:%s:%s" % (seat, _label(schema))
    return indexed, None


def _missing_detail(seat, occurrence, entry):
    detail = {"seat": seat, "occurrence": occurrence}
    if entry is None:
        detail["reason"] = NO_ENVELOPE
    else:
        reason = entry["envelope"].get("reason")
        detail["reason"] = reason if isinstance(reason, str) and reason else NO_ENVELOPE
    return detail


def _landed(indexed, seat, occurrence):
    """(entry_or_None, is_result)."""
    entry = indexed.get((seat, occurrence))
    return entry, entry is not None and entry["kind"] == _KIND_RESULT


# =============================================================================================
# provenance — trusted manifest only, echo disclosed
# =============================================================================================

def _trusted_vendors(roster, indexed, dispatch_manifest, disclosures):
    """{seat: vendor} from the ORCHESTRATOR's dispatch manifest ONLY.

    The envelope's own `vendor` never contributes a value here — it is compared against the
    manifest and any disagreement is disclosed, which is the whole point: the result side of a
    dispatch is claimant-controlled, so using it as provenance would authenticate a claim with the
    claimant's own words.
    """
    if dispatch_manifest is None:
        disclosures["dispatchManifestUnavailable"] = True
        return {}
    trusted = {}
    unusable = []
    mismatch = []
    hand_dispatched = []
    for seat, occurrence in _roster_slots(roster):
        entry_manifest = dispatch_manifest.get(seat)
        vendor = None
        if isinstance(entry_manifest, dict):
            candidate = entry_manifest.get("vendor")
            if isinstance(candidate, str) and candidate:
                vendor = candidate
            if entry_manifest.get("handDispatched"):
                hand_dispatched.append(seat)
        if vendor is None:
            if seat not in unusable:
                unusable.append(seat)
            continue
        trusted[seat] = vendor
        entry, is_result = _landed(indexed, seat, occurrence)
        if entry is None:
            continue
        echo = entry["envelope"].get("vendor")
        if isinstance(echo, str) and echo and echo != vendor:
            mismatch.append({"seat": seat, "occurrence": occurrence, "echo": echo,
                             "manifest": vendor})
    if unusable:
        disclosures["dispatchManifestEntryUnusable"] = unusable
    if mismatch:
        disclosures["vendorEchoMismatch"] = mismatch
    if hand_dispatched:
        disclosures["handDispatchedSeats"] = sorted(hand_dispatched)
    return trusted


def _normalize_canary(canary):
    """(probe_list_or_None, reason_or_None). A single dict is tolerated (the existing contract
    accepts one); absent stays absent so the driver's `canaryUnverified` disclosure fires."""
    if canary is None:
        return None, None
    probes = [canary] if isinstance(canary, dict) else canary
    if not isinstance(probes, list):
        return None, "canary-not-a-list:%s" % _type_name(canary)
    out = []
    for index, probe in enumerate(probes):
        if not isinstance(probe, dict):
            return None, "canary-entry-not-an-object:index-%d:%s" % (index, _type_name(probe))
        engine = probe.get("engine")
        if not isinstance(engine, str) or not engine:
            # A probe with no engine matches NO vendor in `canary_liveness` — it is silently inert,
            # which reads as "a probe was supplied" while proving nothing.
            return None, "canary-entry-has-no-engine:index-%d" % index
        out.append(dict(probe))
    return out, None


# =============================================================================================
# assemble
# =============================================================================================

def assemble(phase, envelopes, state, config, dispatch_manifest=None, canary=None,
             session_dir=None):
    """(artifact_or_None, reason_or_None). NEVER raises."""
    try:
        return _assemble(phase, envelopes, state, config, dispatch_manifest, canary, session_dir)
    except Exception as exc:  # noqa: BLE001 — the contract is total; a crash must be a reason
        return None, "adapter-internal-error:%s:%s" % (_type_name(exc), exc)


def _assemble(phase, envelopes, state, config, dispatch_manifest, canary, session_dir):
    if phase not in ADAPTER_PHASES:
        return None, "unknown-phase:%s" % _label(phase)
    if dispatch_manifest is not None and not isinstance(dispatch_manifest, dict):
        return None, "dispatch-manifest-not-a-dict:%s" % _type_name(dispatch_manifest)
    probes, fault = _normalize_canary(canary)
    if fault:
        return None, fault
    roster, fault = roster_for(phase, state, config)
    if fault:
        return None, "roster-unavailable:%s" % fault
    indexed, fault = _index_envelopes(phase, envelopes, roster)
    if fault:
        return None, fault

    # Single-seat phases refuse rather than fold silence into a success artifact.
    if missing_policy(phase) == MISSING_REFUSE_FOLD:
        for seat, occurrence in _roster_slots(roster):
            _entry, is_result = _landed(indexed, seat, occurrence)
            if not is_result:
                return None, "missing-seat-refuse-fold:%s" % seat

    disclosures = {}
    if phase == P_PANEL:
        artifact = _assemble_panel(roster, indexed, state, dispatch_manifest, probes, disclosures)
    elif phase == P_VERIFIERS:
        artifact = _assemble_verifiers(roster, indexed, disclosures)
    elif phase == P_AUDITS:
        artifact = _assemble_audits(roster, indexed, dispatch_manifest, disclosures)
    elif phase == P_SYNTHESIS:
        artifact = _assemble_synthesis(roster, indexed, disclosures)
    elif phase in (P_GAPSWEEP, P_SCOPED):
        artifact = _assemble_findings(roster, indexed, disclosures)
    elif phase == P_FIXER:
        artifact = _assemble_fixer(roster, indexed, disclosures, phase, session_dir)
        if artifact is None:
            return None, "head-diff-store-path-untrusted"
    else:
        artifact = _assemble_verify(roster, indexed, disclosures)
    if disclosures:
        # Read by no fold — a disclosure channel for the orchestrator and the receipt. Every fold
        # this module feeds reads named keys only, so an extra key changes nothing it does.
        artifact["provenance"] = disclosures
    return artifact, None


def _assemble_panel(roster, indexed, state, dispatch_manifest, probes, disclosures):
    seats = {}
    missing = []
    for dim, occurrence in _roster_slots(roster):
        entry, is_result = _landed(indexed, dim, occurrence)
        if not is_result:
            # `seat-status` policy: omit the dimension. `_fold_panel` then folds it `missing` —
            # `missingSeats` + a `panel-seat-missing` decision + `fullPanelRan` False. The dispatch's
            # own reason rides `provenance` rather than being translated into a fold token nobody
            # reported.
            missing.append(_missing_detail(dim, occurrence, entry))
            continue
        seats[dim] = dict(entry["payload"])
    artifact = {"seats": seats}
    if isinstance(state, dict):
        seat_map = seat_map_receipts.effective_seat_map(state)
    else:
        seat_map = None
    if isinstance(seat_map, dict) and seat_map:
        artifact["seatMap"] = dict(seat_map)
    ran_manifest = _trusted_vendors(roster, indexed, dispatch_manifest, disclosures)
    if ran_manifest:
        artifact["ranManifest"] = ran_manifest
    if probes is not None:
        artifact["canaryResult"] = probes
    else:
        disclosures["canaryUnavailable"] = True
    if missing:
        disclosures["missingSeats"] = missing
    return artifact


def _assemble_verifiers(roster, indexed, disclosures):
    verdicts = []
    omitted = []
    for seat, occurrence in _roster_slots(roster):
        entry, is_result = _landed(indexed, seat, occurrence)
        if not is_result:
            omitted.append(_missing_detail(seat, occurrence, entry))
            continue
        for verdict in entry["payload"]["verdicts"]:
            verdicts.append(dict(verdict))
    if omitted:
        disclosures["unverifiedClusters"] = omitted
    return {"verdicts": verdicts}


def _assemble_audits(roster, indexed, dispatch_manifest, disclosures):
    results = []
    omitted = []
    for seat, occurrence in _roster_slots(roster):
        entry, is_result = _landed(indexed, seat, occurrence)
        if not is_result:
            omitted.append(_missing_detail(seat, occurrence, entry))
            continue
        results.append(dict(entry["payload"]))
    artifact = {"results": results}
    trusted = _trusted_vendors(roster, indexed, dispatch_manifest, disclosures)
    if trusted:
        artifact["collectionManifest"] = trusted
    if omitted:
        disclosures["unauditedTargets"] = omitted
    return artifact


def _assemble_synthesis(roster, indexed, disclosures):
    payload = indexed[(roster[0], 0)]["payload"]
    grouping = payload.get("grouping")
    if isinstance(grouping, list):
        grouping = [dict(group) for group in grouping]
    return {"grouping": grouping}


def _assemble_findings(roster, indexed, disclosures):
    payload = indexed[(roster[0], 0)]["payload"]
    return {"findings": [dict(f) for f in payload["findings"]]}


def _assemble_fixer(roster, indexed, disclosures, phase, session_dir):
    payload = indexed[(roster[0], 0)]["payload"]
    envelope = indexed[(roster[0], 0)]["envelope"]
    artifact = dict(payload)
    store_path = artifact.pop("headDiffStorePath", None)
    if isinstance(store_path, str) and store_path:
        if not isinstance(session_dir, str) or not session_dir:
            return None
        if not round_records.head_diff_store_path_valid(
                store_path, session_dir, envelope.get("round"), phase, envelope.get("seat"),
                envelope.get("attempt"), envelope.get("occurrence", 0)):
            return None
        # `_resolve_head_diff` opens the path at FOLD time; the immutable store copy is the only
        # path that cannot change under it between record and fold.
        artifact["headDiffPath"] = store_path
        disclosures["headDiffPathSource"] = "store"
    elif "headDiffPath" in artifact:
        disclosures["headDiffPathSource"] = "caller-path-no-store-copy"
    return artifact


def _assemble_verify(roster, indexed, disclosures):
    payload = indexed[(roster[0], 0)]["payload"]
    artifact = {"result": payload.get("result")}
    for field in ("command", "exit", "outputSha256"):
        if field in payload:
            artifact[field] = payload[field]
    return artifact
