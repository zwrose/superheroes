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
import round_driver  # noqa: E402
import round_records  # noqa: E402
import verification  # noqa: E402

# =============================================================================================
# phases, seat keys, policies
# =============================================================================================

P_PANEL = round_driver.P_PANEL
P_VERIFIERS = round_driver.P_VERIFIERS
P_SYNTHESIS = round_driver.P_SYNTHESIS
P_GAPSWEEP = round_driver.P_GAPSWEEP
P_AUDITS = round_driver.P_AUDITS
P_SCOPED = round_driver.P_SCOPED
P_VERIFY = round_driver.P_VERIFY
P_FIXER = round_driver.P_FIXER

# The phases this module assembles. Sourced from `round_driver`'s own constants — never respelled.
ADAPTER_PHASES = (P_PANEL, P_VERIFIERS, P_SYNTHESIS, P_GAPSWEEP, P_AUDITS, P_SCOPED, P_VERIFY,
                  P_FIXER)

# Single-seat phases: one dispatch, one seat, one payload.
SEAT_SYNTHESIS = "synthesis"
SEAT_GAPSWEEP = "gap-sweep"
SEAT_SCOPED = "scoped-finder"
SEAT_VERIFY = "verify"
SEAT_FIXER = "fixer"
_SINGLE_SEAT = {
    P_SYNTHESIS: SEAT_SYNTHESIS,
    P_GAPSWEEP: SEAT_GAPSWEEP,
    P_SCOPED: SEAT_SCOPED,
    P_VERIFY: SEAT_VERIFY,
    P_FIXER: SEAT_FIXER,
}

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

# The one ruling whose claim is unusable without a new-issue payload. `audits` exposes the ENUM
# (`AUDIT_RULINGS`, which this module validates against and never hand-copies) but no per-member
# constant, so the member is named here once and `test_new_issue_ruling_is_a_real_member` holds it
# equal to a real member of that enum.
RULING_NEW_ISSUE = "discharged-but-new-issue"

# The panel payload's never-ran FLAG (`_fold_panel` reads `seat.get(...) is True`). Bound from
# `dispatch_outcome` rather than spelled as a literal: the flag IS the boolean form of that outcome
# token, and #747's census keeps every outcome token in that one home.
# `test_panel_vacuous_flag_marks_a_seat_never_ran` drives the real fold through this exact key, so
# the binding is pinned by behaviour rather than by a string comparison.
VACUOUS_FIELD = dispatch_outcome.REASON_VACUOUS

_KIND_RESULT = "result"
_KIND_MISSING = "missing"

# Reason emitted for a roster seat that landed no envelope at all (distinct from a recorded
# `seat-missing/1`, which carries the dispatch's own reason).
NO_ENVELOPE = "no-envelope"


def _label(value):
    """A message-safe rendering of an arbitrary value."""
    return value if isinstance(value, str) else repr(value)


def _type_name(value):
    return type(value).__name__


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
        return list(round_driver._panel_dimensions(cfg)), None
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

    Two DISTINCT audit targets can legitimately share one id (`finding_identity` is line-less), so
    the roster is occurrence-indexed exactly the way `round_records.storage_key` is: identity is
    (seat_key, occurrence), never the seat key alone.
    """
    seen = {}
    slots = []
    for key in keys:
        occurrence = seen.get(key, 0)
        seen[key] = occurrence + 1
        slots.append((key, occurrence))
    return slots


# =============================================================================================
# payload_fault — record-time per-field validation
# =============================================================================================

def _field_missing(field):
    return "`%s` is missing" % field


def _field_type(field, value, expected):
    return "`%s` is %s, not %s" % (field, _type_name(value), expected)


def _optional_str(payload, field):
    if field not in payload:
        return None
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        return _field_type(field, value, "a non-empty string")
    return None


def _optional_bool(payload, field):
    if field not in payload:
        return None
    value = payload.get(field)
    if not isinstance(value, bool):
        return _field_type(field, value, "a boolean")
    return None


def _list_of_objects(value, field):
    if not isinstance(value, list):
        return _field_type(field, value, "a list")
    for index, member in enumerate(value):
        if not isinstance(member, dict):
            return "`%s`[%d] is %s, not an object" % (field, index, _type_name(member))
    return None


def _abs_path(payload, field):
    if field not in payload:
        return None
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        return _field_type(field, value, "a non-empty string")
    if not os.path.isabs(value):
        return ("`%s` is not an absolute path (%r) — the driver reads it at FOLD time and treats a "
                "non-absolute path as an unknown surface" % (field, value))
    return None


def _panel_payload_fault(payload, seat_key):
    """A reviewer seat. `confidence` and `tier` are LOAD-BEARING — `_fold_panel` reads both into the
    per-dimension review record `_confirmation_qualifies` judges — so a mis-shaped one is named.

    The `vacuous` FLAG matters more than it looks: `_fold_panel` tests it with `is True`, so a
    non-boolean truthy value ("yes", 1) does NOT mark the seat never-ran and the seat counts toward
    certification. Naming it at record time is what keeps a mis-typed flag from certifying.
    """
    declared_not_run = payload.get(VACUOUS_FIELD) is True or (
        isinstance(payload.get("reason"), str)
        and payload.get("reason") in dispatch_outcome.NOT_RUN_REASONS)
    if "findings" not in payload:
        if not declared_not_run:
            return ("%s — a seat that ran owes its findings list (a seat that did NOT run says so "
                    "with `reason` / the never-ran flag)" % _field_missing("findings"))
    else:
        fault = _list_of_objects(payload.get("findings"), "findings")
        if fault:
            return fault
    for field in ("confidence", "tier"):
        fault = _optional_str(payload, field)
        if fault:
            return fault
    for field in ("receiptMissing", "receiptStale", VACUOUS_FIELD):
        fault = _optional_bool(payload, field)
        if fault:
            return fault
    if "reason" in payload and not isinstance(payload.get("reason"), str):
        return _field_type("reason", payload.get("reason"), "a string")
    return None


def _verifiers_payload_fault(payload, seat_key):
    """A verifier cluster. `verification.apply_verdicts` keys on `id` (NOT `findingId`) and consumes
    `reason` and `severity`, so those are exactly the fields named here."""
    if "verdicts" not in payload:
        return _field_missing("verdicts")
    fault = _list_of_objects(payload.get("verdicts"), "verdicts")
    if fault:
        return fault
    for index, verdict in enumerate(payload["verdicts"]):
        where = "verdicts[%d]" % index
        vid = verdict.get("id")
        if not isinstance(vid, str) or not vid:
            detail = "`%s.id` is %s, not a non-empty string" % (where, _type_name(vid))
            if "findingId" in verdict:
                detail += ("; the payload carries `findingId` — apply_verdicts keys on `id`, and a "
                           "verdict it cannot key reaches no finding at all")
            return detail
        value = verdict.get("verdict")
        if not isinstance(value, str) or value not in verification.VERDICTS:
            return ("`%s.verdict` is %r — expected one of: %s"
                    % (where, value, ", ".join(verification.VERDICTS)))
        for field in ("reason", "severity", "evidence"):
            if field in verdict and not isinstance(verdict.get(field), str):
                return "`%s.%s` is %s, not a string" % (where, field, _type_name(verdict.get(field)))
    return None


def _synthesis_payload_fault(payload, seat_key):
    """The merge grouping `verification.merge_and_rank` consumes. `None` (no merging proposed) is a
    real answer; a mis-shaped grouping is not — `_valid_grouping` would silently discard it, losing
    the merge with no disclosure."""
    if "grouping" not in payload:
        return _field_missing("grouping")
    grouping = payload.get("grouping")
    if grouping is None:
        return None
    fault = _list_of_objects(grouping, "grouping")
    if fault:
        return fault
    for index, group in enumerate(grouping):
        member_ids = group.get("member_ids")
        if not isinstance(member_ids, list) or not member_ids:
            return ("`grouping`[%d].member_ids is %s, not a non-empty list"
                    % (index, _type_name(member_ids)))
        for member_index, member in enumerate(member_ids):
            if not isinstance(member, str) or not member:
                return ("`grouping`[%d].member_ids[%d] is %s, not a non-empty string"
                        % (index, member_index, _type_name(member)))
    return None


def _findings_payload_fault(payload, seat_key):
    """The gap-sweep / scoped-finder candidate list."""
    if "findings" not in payload:
        return _field_missing("findings")
    return _list_of_objects(payload.get("findings"), "findings")


def _fixer_payload_fault(payload, seat_key):
    if "fixes" not in payload:
        return _field_missing("fixes")
    if not isinstance(payload.get("fixes"), list):
        return _field_type("fixes", payload.get("fixes"), "a list")
    fault = _optional_bool(payload, "escalated")
    if fault:
        return fault
    if "headDiff" in payload and not isinstance(payload.get("headDiff"), str):
        return _field_type("headDiff", payload.get("headDiff"), "a string")
    for field in ("headDiffPath", "headDiffStorePath"):
        fault = _abs_path(payload, field)
        if fault:
            return fault
    if "coverageDecisions" in payload:
        fault = _list_of_objects(payload.get("coverageDecisions"), "coverageDecisions")
        if fault:
            return fault
    return None


def _verify_payload_fault(payload, seat_key):
    """Delegates the `result` vocabulary to `round_driver.verify_result_fault` — the driver's OWN
    submit-shape guard, so this adapter can never accept a token the submit path refuses."""
    fault = round_driver.verify_result_fault(payload)
    if fault:
        return fault
    if "command" in payload and not isinstance(payload.get("command"), str):
        return _field_type("command", payload.get("command"), "a string")
    if "exit" in payload:
        value = payload.get("exit")
        if isinstance(value, bool) or not isinstance(value, int):
            return _field_type("exit", value, "an integer")
    if "outputSha256" in payload and not isinstance(payload.get("outputSha256"), str):
        return _field_type("outputSha256", payload.get("outputSha256"), "a string")
    return None


def _audits_payload_fault(payload, seat_key):
    """One auditor's ruling. `ruling` is validated against `audits.AUDIT_RULINGS` — the enum
    imported from its own home, never a hand-copy — and the grounds/new-issue predicates are
    `audits`' OWN (`has_usable_reason` / `has_usable_new_issues`), so what this accepts is exactly
    what the fold can use.

    `reason` is required on EVERY ruling here (the driver's submit-shape guard requires it only on
    `discharged`): at RECORD time a reasonless ruling is a re-dispatch away from being right, and a
    ruling with no grounds is the unproven claim the audit fold exists to reject.
    """
    rid = payload.get("id")
    if not isinstance(rid, str) or not rid:
        return ("`id` is %s, not a non-empty string — a ruling with no finding id can never reach "
                "its target" % _type_name(rid))
    if isinstance(seat_key, str) and seat_key and rid != seat_key:
        return ("`id` is %r but this seat is %r — a ruling keyed to another target reaches no "
                "finding" % (rid, seat_key))
    ruling = payload.get("ruling")
    if not isinstance(ruling, str) or ruling not in audits.AUDIT_RULINGS:
        return ("`ruling` is %r — expected one of: %s"
                % (ruling, ", ".join(audits.AUDIT_RULINGS)))
    if not audits.has_usable_reason(payload.get("reason")):
        return ("`reason` is missing or blank (got %r) — a ruling with no grounds is the unproven "
                "claim the audit fold exists to reject" % (payload.get("reason"),))
    if ruling == RULING_NEW_ISSUE and not audits.has_usable_new_issues(payload.get("newIssues")):
        detail = ("`newIssues` carries no usable issue object (got %r) — a %s ruling owes the new "
                  "issue it claims" % (payload.get("newIssues"), RULING_NEW_ISSUE))
        if "newIssue" in payload:
            detail += "; the payload carries `newIssue` (singular) — the driver consumes a LIST"
        return detail
    if "newIssues" in payload:
        fault = _list_of_objects(payload.get("newIssues"), "newIssues")
        if fault:
            return fault
    for field in ("evidence", "auditorVendor"):
        if field in payload and not isinstance(payload.get(field), str):
            return _field_type(field, payload.get(field), "a string")
    return None


_PAYLOAD_CHECKERS = {
    P_PANEL: _panel_payload_fault,
    P_VERIFIERS: _verifiers_payload_fault,
    P_SYNTHESIS: _synthesis_payload_fault,
    P_GAPSWEEP: _findings_payload_fault,
    P_SCOPED: _findings_payload_fault,
    P_FIXER: _fixer_payload_fault,
    P_VERIFY: _verify_payload_fault,
    P_AUDITS: _audits_payload_fault,
}


def payload_fault(phase, payload, seat_key):
    """A reason string naming the offending field, or None. Never raises."""
    if phase not in ADAPTER_PHASES:
        return "unknown-phase:%s" % _label(phase)
    if not isinstance(payload, dict):
        return "payload is %s, not an object" % _type_name(payload)
    try:
        return _PAYLOAD_CHECKERS[phase](payload, seat_key)
    except Exception as exc:  # noqa: BLE001 — a validator that raises must not crash the adapter
        return "payload-validator-error:%s:%s" % (_type_name(exc), exc)


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
    for seat, occurrence in _roster_slots(roster):
        entry_manifest = dispatch_manifest.get(seat)
        vendor = None
        if isinstance(entry_manifest, dict):
            candidate = entry_manifest.get("vendor")
            if isinstance(candidate, str) and candidate:
                vendor = candidate
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

def assemble(phase, envelopes, state, config, dispatch_manifest=None, canary=None):
    """(artifact_or_None, reason_or_None). NEVER raises."""
    try:
        return _assemble(phase, envelopes, state, config, dispatch_manifest, canary)
    except Exception as exc:  # noqa: BLE001 — the contract is total; a crash must be a reason
        return None, "adapter-internal-error:%s:%s" % (_type_name(exc), exc)


def _assemble(phase, envelopes, state, config, dispatch_manifest, canary):
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
        artifact = _assemble_synthesis(roster, indexed)
    elif phase in (P_GAPSWEEP, P_SCOPED):
        artifact = _assemble_findings(roster, indexed)
    elif phase == P_FIXER:
        artifact = _assemble_fixer(roster, indexed, disclosures)
    else:
        artifact = _assemble_verify(roster, indexed)
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
    seat_map = state.get("seatMap") if isinstance(state, dict) else None
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


def _assemble_synthesis(roster, indexed):
    payload = indexed[(roster[0], 0)]["payload"]
    grouping = payload.get("grouping")
    if isinstance(grouping, list):
        grouping = [dict(group) for group in grouping]
    return {"grouping": grouping}


def _assemble_findings(roster, indexed):
    payload = indexed[(roster[0], 0)]["payload"]
    return {"findings": [dict(f) for f in payload["findings"]]}


def _assemble_fixer(roster, indexed, disclosures):
    payload = indexed[(roster[0], 0)]["payload"]
    artifact = dict(payload)
    store_path = artifact.pop("headDiffStorePath", None)
    if isinstance(store_path, str) and store_path:
        # `_resolve_head_diff` opens the path at FOLD time; the immutable store copy is the only
        # path that cannot change under it between record and fold.
        artifact["headDiffPath"] = store_path
        disclosures["headDiffPathSource"] = "store"
    elif "headDiffPath" in artifact:
        disclosures["headDiffPathSource"] = "caller-path-no-store-copy"
    return artifact


def _assemble_verify(roster, indexed):
    payload = indexed[(roster[0], 0)]["payload"]
    artifact = {"result": payload.get("result")}
    for field in ("command", "exit", "outputSha256"):
        if field in payload:
            artifact[field] = payload[field]
    return artifact
