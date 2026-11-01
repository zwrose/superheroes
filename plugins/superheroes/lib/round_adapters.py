#!/usr/bin/env python3
"""Per-phase aggregate adapters (#723): recorded seat envelopes -> the artifact the phase's
EXISTING `round_driver._fold_<phase>` already consumes.

One pure function per concern, none of which mutate anything:

  * `roster_for(phase, state, config)`  — the seat keys this phase owes, from driver state.
  * `payload_fault(phase, payload, seat_key)` — record-time per-field validation of ONE seat's
    payload, naming the offending field.
  * `missing_policy(phase)` — what a `seat-missing/1` envelope (or an unlanded roster seat) does
    to the fold: `seat-status` | `refuse-fold` | `fold-fail-closed`.
  * `assemble(phase, envelopes, state, config, dispatch_manifest)` — the artifact, or
    `(None, reason)`. NEVER raises.

Design rules this module is bound by (each one is a defect class it exists to prevent):

TRUST. At state v5 (`seat-result/2`), `ranManifest` (panel) and `collectionManifest` (audits) are
DISPATCH PROVENANCE derived from each stored envelope's `executionEvidence.source` — the runner's
own record of who executed the seat. The orchestrator's `dispatch_manifest` is LEGACY-ONLY: read
for `seat-result/1` envelopes; when every landed result is v2 and a manifest file is present it is
ignored (`dispatchManifestIgnored`). A seat envelope's `vendor`/`model` is a claimant-controlled
ADVISORY ECHO: a forfeiting or misrouted worker simply echoes the expected value, so the echo
authenticates nothing (see `audits.apply_audit_results` and `round_driver._fell_open_rows`, both
explicit on this). A disagreement between the echo and the trusted source is DISCLOSED in the
artifact's `provenance` block; it never populates a manifest. With no trusted source on a v2
envelope the manifest key is OMITTED and the seat rides `provenanceUnderived`; on legacy v1 with
no `dispatch_manifest` the manifest key is OMITTED so the driver's provenance-unavailable disclosure
fires — a synthesized manifest would silently authenticate an unauthenticated run.

SILENCE NEVER CERTIFIES. `missing_policy` is the whole safety surface of this module. A
`record-missing` seat must never become a success artifact: single-seat phases REFUSE to assemble
(`missing-seat-refuse-fold:<seat>`) rather than emit `{"findings": []}`, because an empty
scoped-finder artifact settles the delta and can certify a round nobody reviewed.

stdlib only; runs on Python 3.9 and 3.12 (no `match`, no PEP-604 runtime annotations).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audits  # noqa: E402
import dispatch_outcome  # noqa: E402
import model_registry  # noqa: E402 — stdlib-only leaf; no cycle with adapters layer
import round_phases  # noqa: E402
import round_records  # noqa: E402
import seat_map_receipts  # noqa: E402
import session_contract  # noqa: E402
import verification  # noqa: E402
import payload_contracts  # noqa: E402
import receipt_disclosures  # noqa: E402

# =============================================================================================
# phases, seat keys, policies
# =============================================================================================

P_PANEL = round_phases.P_PANEL
P_VERIFIERS = round_phases.P_VERIFIERS
P_SYNTHESIS = round_phases.P_SYNTHESIS
P_SEAMS = round_phases.P_SEAMS
P_SECOND_TEST = round_phases.P_SECOND_TEST
P_AUDITS = round_phases.P_AUDITS
P_SCOPED = round_phases.P_SCOPED
P_VERIFY = round_phases.P_VERIFY
P_APPLY_FIXES = round_phases.P_APPLY_FIXES

# Re-export payload-contract names from the single contract home (CONVENTIONS §11 Pattern 1).
ADAPTER_PHASES = payload_contracts.ADAPTER_PHASES
SEAT_SYNTHESIS = payload_contracts.SEAT_SYNTHESIS
SEAT_SEAMS = payload_contracts.SEAT_SEAMS
SEAT_SECOND_TEST = payload_contracts.SEAT_SECOND_TEST
SEAT_SCOPED = payload_contracts.SEAT_SCOPED
SEAT_VERIFY = payload_contracts.SEAT_VERIFY
SEAT_APPLY_FIXES = payload_contracts.SEAT_APPLY_FIXES
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
    P_SEAMS: SEAT_SEAMS,
    P_SECOND_TEST: SEAT_SECOND_TEST,
    P_SCOPED: SEAT_SCOPED,
    P_VERIFY: SEAT_VERIFY,
    P_APPLY_FIXES: SEAT_APPLY_FIXES,
}

# Phases fulfilled by the orchestrator itself — no `dispatch-*` orders manifest is emitted.
ORCHESTRATOR_FULFILLED_PHASES = (P_VERIFY, P_APPLY_FIXES)


def is_orchestrator_fulfilled(phase):
    """True when the orchestrator fulfils the phase and no orders manifest is emitted.

    Unknown phase strings fall to the conservative side (False) — treated as seat phases that
    require an anchor."""
    return isinstance(phase, str) and phase in ORCHESTRATOR_FULFILLED_PHASES


def orchestrator_payload_fault(phase, payload):
    """Submit-shape guard for orchestrator-fulfilled phase payloads. None when well-formed."""
    if phase == P_VERIFY:
        return round_phases.verify_result_fault(payload)
    if phase == P_APPLY_FIXES:
        return payload_contracts.payload_fault(P_APPLY_FIXES, payload, SEAT_APPLY_FIXES)
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
    P_SEAMS: MISSING_REFUSE_FOLD,
    P_SECOND_TEST: MISSING_REFUSE_FOLD,
    P_SCOPED: MISSING_REFUSE_FOLD,
    P_VERIFY: MISSING_REFUSE_FOLD,
    P_APPLY_FIXES: MISSING_REFUSE_FOLD,
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
    sorted: the panel folds in `round_phases.panel_roster` order, the verifiers artifact concatenates in
    cluster order (`verification.cluster_findings` already sorts by (file, bucket)), and the audits
    artifact lists results in audit-target order. A reason is returned only when the roster cannot
    be derived at all — never an empty roster standing in for an underivable one.
    """
    if phase not in ADAPTER_PHASES:
        return [], "unknown-phase:%s" % _label(phase)
    st = state if isinstance(state, dict) else {}
    cfg = config if isinstance(config, dict) else {}
    if phase == P_PANEL:
        return list(round_phases.panel_roster(st, cfg)), None
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
        if schema in round_records.SEAT_RESULT_SCHEMAS:
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

PROVENANCE_SOURCE_DISPATCH_MANIFEST = round_records.AUDIT_PROVENANCE_LEGACY_DISPATCH_MANIFEST


def _maker_barred(state, config):
    """Predicate: True when a vendor may not review (maker family, the fixer's vendor, or an
    unresolvable reviewer family) — `receipt_disclosures.reviewer_ineligible`, the same bar
    `nonpanel_reviewer` applies when the driver selects a non-panel reviewer — including the host
    family a native seat takes from the seat map, so the two sides judge a vendor identically."""
    return receipt_disclosures.nonpanel_barred(state, config)


def _manifest_vendor_for_wrapped_seat(envelope, seat, occurrence, orders_manifest, is_barred):
    """The vendor the DRIVER's orders manifest recorded at emission for a host-seat (a file-channel
    seat, or a native-vendor seat handed the stdout fallback contract) whose v2 envelope the driver wrapped itself from a bare payload (so it carries no runner
    execution evidence); None for any other landing, a runner-channel seat, an unusable entry, or a
    vendor in a maker family. This is the only place a manifest vendor stands in for evidence."""
    if not isinstance(orders_manifest, dict) or envelope.get("executionEvidence") is not None:
        return None
    if envelope.get("payloadHashSource") != "driver-computed":
        return None
    seats = orders_manifest.get("seats")
    entry = seats.get(round_records.storage_key(seat, occurrence)) if isinstance(seats, dict) else None
    if not isinstance(entry, dict):
        return None
    vendor = entry.get("vendor")
    if not isinstance(vendor, str) or vendor not in model_registry.VENDORS:
        return None
    # A native (non-runner) vendor can be handed the stdout contract (an unresolved or defaulted
    # preference read) and the orchestrator lands its returned payload, which the driver wraps just
    # as it wraps a file landing; only a runner-channel vendor must carry runner execution evidence.
    if entry.get("channel") != session_contract.CHANNEL_FILE \
            and session_contract.runner_channel_vendor(vendor):
        return None
    if callable(is_barred) and is_barred(vendor):
        return None
    return vendor


def _trusted_vendors(roster, indexed, dispatch_manifest, disclosures, orders_manifest=None,
                     is_barred=None):
    """{seat: vendor} from the runner record on v2 envelopes; legacy v1 reads dispatch_manifest.

    With ``orders_manifest`` (verifier and finder seats only) a v2 envelope the driver wrapped from
    its own emitted host-seat stub, carrying no execution evidence, takes the vendor the driver's
    orders manifest recorded for that seat (provenance ``dispatch-manifest``, distinct from
    ``runner-record``) unless that vendor is in a maker family."""
    trusted = {}
    unusable = []
    mismatch = []
    underived = []
    landed_v2 = False
    landed_v1 = False
    for seat, occurrence in _roster_slots(roster):
        entry, is_result = _landed(indexed, seat, occurrence)
        if not is_result:
            continue
        envelope = entry["envelope"]
        schema = envelope.get("schema")
        if schema == round_records.SEAT_RESULT_SCHEMA_V2:
            landed_v2 = True
            provenance = envelope.get("provenance")
            evidence = envelope.get("executionEvidence")
            source = evidence.get("source") if isinstance(evidence, dict) else None
            if isinstance(source, str) and source and source in model_registry.VENDORS:
                trusted[seat] = source
                prov_src = disclosures.setdefault("provenanceSource", {})
                if provenance == round_records.PROVENANCE_DISPATCH_OBSERVED:
                    prov_src[seat] = round_records.AUDIT_PROVENANCE_RUNNER_RECORD
                elif provenance == round_records.PROVENANCE_HAND_LANDED:
                    prov_src[seat] = round_records.AUDIT_PROVENANCE_HAND_LANDED
            else:
                wrapped = _manifest_vendor_for_wrapped_seat(
                    envelope, seat, occurrence, orders_manifest, is_barred)
                if wrapped is not None:
                    trusted[seat] = wrapped
                    source = wrapped
                    disclosures.setdefault("provenanceSource", {})[seat] = \
                        PROVENANCE_SOURCE_DISPATCH_MANIFEST
                elif seat not in underived:
                    underived.append(seat)
            echo = envelope.get("vendor")
            if (isinstance(source, str) and source and isinstance(echo, str) and echo
                    and echo != source):
                mismatch.append({"seat": seat, "occurrence": occurrence, "echo": echo,
                                 "recorded": source})
            continue
        if schema in round_records.SEAT_RESULT_SCHEMAS:
            landed_v1 = True
            entry_manifest = (dispatch_manifest.get(seat)
                              if isinstance(dispatch_manifest, dict) else None)
            vendor = None
            if isinstance(entry_manifest, dict):
                candidate = entry_manifest.get("vendor")
                if isinstance(candidate, str) and candidate:
                    vendor = candidate
            if vendor is None:
                if isinstance(dispatch_manifest, dict):
                    if seat not in unusable:
                        unusable.append(seat)
                continue
            trusted[seat] = vendor
            echo = envelope.get("vendor")
            if isinstance(echo, str) and echo and echo != vendor:
                mismatch.append({"seat": seat, "occurrence": occurrence, "echo": echo,
                                 "manifest": vendor})
    if dispatch_manifest is not None and landed_v2 and not landed_v1:
        disclosures["dispatchManifestIgnored"] = True
    if dispatch_manifest is None and landed_v1:
        disclosures["dispatchManifestUnavailable"] = True
    if unusable:
        disclosures["dispatchManifestEntryUnusable"] = unusable
    if mismatch:
        disclosures["vendorEchoMismatch"] = mismatch
    if underived:
        disclosures["provenanceUnderived"] = underived
    return trusted


# =============================================================================================
# assemble
# =============================================================================================

def assemble(phase, envelopes, state, config, dispatch_manifest=None,
             session_dir=None, orders_manifest=None):
    """(artifact_or_None, reason_or_None). NEVER raises.

    ``orders_manifest`` is the driver's OWN emission-time orders manifest, already verified against
    the state anchor by the caller (an unverifiable one is passed as ``{}``); ``None`` means the
    caller supplied none. The verifier and single-seat finder phases read it (see
    `_trusted_vendors`, `_authenticate_finder`)."""
    try:
        return _assemble(phase, envelopes, state, config, dispatch_manifest, session_dir,
                         orders_manifest)
    except Exception as exc:  # noqa: BLE001 — the contract is total; a crash must be a reason
        return None, "adapter-internal-error:%s:%s" % (_type_name(exc), exc)


def _assemble(phase, envelopes, state, config, dispatch_manifest, session_dir,
              orders_manifest=None):
    if phase not in ADAPTER_PHASES:
        return None, "unknown-phase:%s" % _label(phase)
    if dispatch_manifest is not None and not isinstance(dispatch_manifest, dict):
        return None, "dispatch-manifest-not-a-dict:%s" % _type_name(dispatch_manifest)
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
        artifact = _assemble_panel(roster, indexed, state, dispatch_manifest, disclosures)
    elif phase == P_VERIFIERS:
        artifact = _assemble_verifiers(roster, indexed, dispatch_manifest, disclosures,
                                       orders_manifest, _maker_barred(state, config))
    elif phase == P_AUDITS:
        artifact = _assemble_audits(roster, indexed, dispatch_manifest, disclosures)
    elif phase == P_SYNTHESIS:
        fault = _authenticate_finder(roster, indexed, dispatch_manifest, orders_manifest,
                                     _maker_barred(state, config), disclosures)
        if fault is not None:
            return None, fault
        artifact = _assemble_synthesis(roster, indexed, disclosures)
    elif phase in (P_SEAMS, P_SECOND_TEST, P_SCOPED):
        fault = _authenticate_finder(roster, indexed, dispatch_manifest, orders_manifest,
                                     _maker_barred(state, config), disclosures)
        if fault is not None:
            return None, fault
        artifact = _assemble_findings(roster, indexed, disclosures)
        if phase == P_SEAMS:
            # axis: the seams artifact carries the executed vendor the authentication above checked, so the fold stamps a search description's author on the durable path as the panel's `ranManifest` does — see bite-proof record c4_wo1_kind
            ran_manifest = _trusted_vendors(roster, indexed, dispatch_manifest, {}, orders_manifest,
                                            _maker_barred(state, config))
            if ran_manifest:
                artifact["ranManifest"] = ran_manifest
    elif phase == P_APPLY_FIXES:
        artifact = _assemble_apply_fixes(roster, indexed)
    else:
        artifact = _assemble_verify(roster, indexed, disclosures)
    if disclosures:
        # Read by no fold — a disclosure channel for the orchestrator and the receipt. Every fold
        # this module feeds reads named keys only, so an extra key changes nothing it does.
        artifact["provenance"] = disclosures
    return artifact, None


def _assemble_panel(roster, indexed, state, dispatch_manifest, disclosures):
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
    if missing:
        disclosures["missingSeats"] = missing
    return artifact


def _assemble_verifiers(roster, indexed, dispatch_manifest, disclosures, orders_manifest=None,
                        is_barred=None):
    supplied = []
    omitted = []
    landed = []
    for seat, occurrence in _roster_slots(roster):
        entry, is_result = _landed(indexed, seat, occurrence)
        if not is_result:
            omitted.append(_missing_detail(seat, occurrence, entry))
            continue
        landed.append(seat)
        skey = round_records.storage_key(seat, occurrence)
        for verdict in entry["payload"]["verdicts"]:
            supplied.append((seat, skey, dict(verdict)))
    if omitted:
        disclosures["unverifiedClusters"] = omitted
    # A verdict counts only from the seat its order assigned (`ids`, recorded at emission and hashed
    # into the emission anchor). No manifest, or a seat entry with no `ids` list, assigns nothing, so
    # nothing is kept (never "whoever supplied it"); an id assigned to two seats is kept for neither.
    owner_of_id = {}
    double = set()
    manifest_seats = orders_manifest.get("seats") if isinstance(orders_manifest, dict) else None
    for skey, entry in (manifest_seats.items() if isinstance(manifest_seats, dict) else ()):
        ids = entry.get("ids") if isinstance(entry, dict) else None
        for vid in (ids if isinstance(ids, list) else ()):
            if isinstance(vid, str) and owner_of_id.setdefault(vid, skey) != skey:
                double.add(vid)

    def _owner(verdict):
        return owner_of_id.get(verdict["id"]) if isinstance(verdict.get("id"), str) else None
    kept = [(seat, verdict) for seat, skey, verdict in supplied
            if _owner(verdict) == skey and verdict["id"] not in double]
    unordered = [dict(seat=seat, id=verdict.get("id"), orderedTo=_owner(verdict))
                 for seat, skey, verdict in supplied if _owner(verdict) != skey]
    if unordered:
        disclosures["unorderedVerdicts"] = unordered
    if double:
        disclosures["doubleAssigned"] = sorted(double)
    verdicts = [verdict for _seat, verdict in kept]
    artifact = {"verdicts": verdicts}
    if landed:
        # The vendor that RAN each verifier is the runner's execution record (the same provenance
        # `_assemble_audits` derives `collectionManifest` from), never the payload's own claim and
        # never the driver's selection. Provenance is judged PER SEAT: a seat's executed vendor
        # authenticates only the verdicts it supplied (`verifierSeatVendors`: verdict id -> that
        # seat's vendor, "" when the seat has no derivable vendor), so an unproven cluster never
        # voids a proven one. `verifierVendor` stays the joined summary of the proven seats.
        trusted = _trusted_vendors(roster, indexed, dispatch_manifest, disclosures,
                                   orders_manifest, is_barred)
        ran = {trusted[seat] for seat in landed if seat in trusted}
        if ran:
            artifact["verifierVendor"] = "+".join(sorted(ran))
        artifact["verifierSeatVendors"] = {v["id"]: trusted.get(seat, "") for seat, v in kept}
        # A seat whose vendor is the driver's own manifest entry (a driver-wrapped host-seat landing,
        # no runner evidence) is marked so the fold records its provenance as `dispatch-manifest`.
        by_manifest = {
            v["id"]: PROVENANCE_SOURCE_DISPATCH_MANIFEST for seat, v in kept
            if disclosures.get("provenanceSource", {}).get(seat) == PROVENANCE_SOURCE_DISPATCH_MANIFEST}
        if by_manifest:
            artifact["verifierSeatProvenance"] = by_manifest
    return artifact


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


def _authenticate_finder(roster, indexed, dispatch_manifest, orders_manifest, is_barred,
                         disclosures):
    """Fault string when the single-seat finder (seams-check / scoped) result is not authenticated,
    else None. The executed vendor (runner `executionEvidence.source`, or the driver's own manifest
    vendor for a driver-wrapped host-seat landing) must equal the vendor the orders manifest recorded
    at emission for the seat and pass the eligibility bar (``is_barred``); anything else is a review
    that did not run, so the seat folds as missing (the same refuse-fold a never-landed seat gets) rather than as "ran and found nothing".
    `None` ``orders_manifest`` (no manifest supplied by the caller) leaves the check off."""
    if orders_manifest is None:
        return None
    trusted = _trusted_vendors(roster, indexed, dispatch_manifest, disclosures, orders_manifest,
                               is_barred)
    seats = orders_manifest.get("seats") if isinstance(orders_manifest, dict) else None
    for seat, occurrence in _roster_slots(roster):
        entry = seats.get(round_records.storage_key(seat, occurrence)) \
            if isinstance(seats, dict) else None
        expected = entry.get("vendor") if isinstance(entry, dict) else None
        executed = trusted.get(seat)
        ineligible = executed is not None and callable(is_barred) and is_barred(executed)
        if not isinstance(expected, str) or not expected or executed != expected or ineligible:
            disclosures["unauthenticatedFinder"] = {"seat": seat, "executed": executed,
                                                     "recorded": expected}
            return "missing-seat-refuse-fold:%s:unauthenticated-vendor:executed=%s:recorded=%s%s" % (
                seat, executed, expected, ":vendor-ineligible" if ineligible else "")
    return None


def _assemble_findings(roster, indexed, disclosures):
    payload = indexed[(roster[0], 0)]["payload"]
    return {"findings": [dict(f) for f in payload["findings"]]}


def _assemble_apply_fixes(roster, indexed):
    return dict(indexed[(roster[0], 0)]["payload"])


def _assemble_verify(roster, indexed, disclosures):
    payload = indexed[(roster[0], 0)]["payload"]
    artifact = {"result": payload.get("result")}
    # axis: the CI evidence rides the durable-seat assembly to the chokepoint — see bite-proof record wo_b_2072_ci_verify
    for field in ("command", "exit", "outputSha256", "via", "ci", "reason", "headSha",
                  "headShaAfter", "treeSha", "treeShaAfter", "exitCode", "outputPath"):
        if field in payload:
            artifact[field] = payload[field]
    return artifact
