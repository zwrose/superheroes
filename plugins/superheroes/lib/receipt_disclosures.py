#!/usr/bin/env python3
"""Disclosure-channel vocabulary, selection rule, and degraded-prose collector — leaf module."""
import model_registry
import seat_map_receipts
import session_contract

RECEIPT_FORM_CERTIFIED = "certified"
RECEIPT_FORM_ATTESTED = "attested"
RECEIPT_FORM_INTERIM = "interim"
RECEIPT_CERTIFIED_SCHEMA = "receipt-certified/%d"
RECEIPT_ATTESTED_SCHEMA = "receipt-attested/1"
RECEIPT_INTERIM_SCHEMA = "receipt-interim/1"
SCHEMA_VERSION = 2
SUPPORTED_STATE_VERSIONS = (2, 3, 4, 5)

VENDOR_SOURCE_DEFAULTED = "defaulted"

ROUND_ENTRY_KEY_FORMS = {
    "verifyPasses": {
        "min_certified_version": 3,
        "non_certified_schemas": (RECEIPT_ATTESTED_SCHEMA, RECEIPT_INTERIM_SCHEMA),
    },
}

DISCLOSE_ON_PRESENCE = ("canaryVerified",)


def str_list(value):
    return isinstance(value, list) and all(isinstance(x, str) for x in value)


def dict_list(value):
    return isinstance(value, list) and all(isinstance(x, dict) for x in value)


def bool_value(value):
    return isinstance(value, bool)


def canary_failed_shape(value):
    return isinstance(value, dict) and str_list(value.get("seats") or [])


def canary_verified_shape(value):
    return isinstance(value, dict) and all(isinstance(k, str) for k in value)


def control_probe_shape(value):
    if not isinstance(value, dict):
        return False
    if not isinstance(value.get("submitted"), bool):
        return False
    vendors = value.get("vendors")
    if not isinstance(vendors, dict):
        return False
    return all(isinstance(k, str) and isinstance(v, str) for k, v in vendors.items())


def adapter_provenance_shape(value):
    if not isinstance(value, dict):
        return False
    if "byPhase" in value:
        return isinstance(value.get("byPhase"), dict)
    return True


def order_vendor_provenance_gaps_shape(value):
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


def normalize_adapter_provenance(prov):
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


RESUMABLE_DISCLOSURE_CHANNELS = {
    "fellOpen": dict_list,
    "fellOpenProvenanceMissing": str_list,
    "seatMapUnavailable": str_list,
    "seatMapUnjudgeable": str_list,
    "seatMapViolations": dict_list,
    "vacuousSeats": str_list,
    "engagedArtifactSeats": str_list,
    "canaryUnverified": str_list,
    "canaryFailed": canary_failed_shape,
    "canaryOutcomeFailed": canary_failed_shape,
    "canaryPlantUndetected": canary_failed_shape,
    "canaryVerified": canary_verified_shape,
    "controlProbe": control_probe_shape,
    "adapterProvenance": adapter_provenance_shape,
    "recordOrphansIgnored": str_list,
    "orderVendorProvenanceGaps": order_vendor_provenance_gaps_shape,
    "priorCommentsUnavailable": bool_value,
    "verifyPasses": dict_list,
    "judgmentDispositions": dict_list,
    "gateGuidanceRowCarried": dict_list,
}


def _state_version(state):
    if not isinstance(state, dict):
        return None
    version = state.get("schemaVersion")
    if isinstance(version, bool) or not isinstance(version, int):
        return None
    return version if version in SUPPORTED_STATE_VERSIONS else None


def _receipt_version(state):
    return _state_version(state) or SCHEMA_VERSION


def _round_entry_form_schema(form, state):
    if form == RECEIPT_FORM_CERTIFIED:
        return RECEIPT_CERTIFIED_SCHEMA % _receipt_version(state)
    if form == RECEIPT_FORM_ATTESTED:
        return RECEIPT_ATTESTED_SCHEMA
    if form == RECEIPT_FORM_INTERIM:
        return RECEIPT_INTERIM_SCHEMA
    raise ValueError("unknown receipt form %r" % form)


def round_entry_key_declared(key, schema, certified_version):
    decl = ROUND_ENTRY_KEY_FORMS.get(key)
    if decl is None:
        return True
    if certified_version is not None:
        return certified_version >= decl["min_certified_version"]
    return schema in decl["non_certified_schemas"]


def round_entry_key_allowed(key, form, state):
    if key not in ROUND_ENTRY_KEY_FORMS:
        return True
    if form == RECEIPT_FORM_CERTIFIED:
        return round_entry_key_declared(key, None, _receipt_version(state))
    return round_entry_key_declared(key, _round_entry_form_schema(form, state), None)


def declared_disclosures(entry):
    if not isinstance(entry, dict):
        entry = {}
    out = {}
    for chan, shape_ok in RESUMABLE_DISCLOSURE_CHANNELS.items():
        if chan in DISCLOSE_ON_PRESENCE:
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


def receipt_round_disclosures(entry, form, state):
    return {chan: value
            for chan, value in declared_disclosures(entry).items()
            if round_entry_key_allowed(chan, form, state)}


def live_vendors(config):
    vendors = config.get("vendors") if isinstance(config, dict) else None
    if not isinstance(vendors, list) or not vendors:
        return ["claude"]
    seen = set()
    out = []
    for v in vendors:
        if isinstance(v, str) and v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def independent_auditor(config, fixer_vendor, runner_only=False):
    fixer_fam = model_registry.family_for("code-fixer", fixer_vendor)
    if fixer_fam is None:
        return None, None
    for v in live_vendors(config):
        if runner_only and not session_contract.runner_channel_vendor(v):
            continue
        if v != fixer_vendor:
            cand_fam = model_registry.family_for("verifier", v)
            if cand_fam is not None and cand_fam != fixer_fam:
                return v, fixer_fam
    return None, fixer_fam


def independent_auditor_available(config):
    fixer = config.get("fixerVendor") if isinstance(config, dict) else None
    vendor, fam = independent_auditor(config, fixer)
    return (vendor is not None, fam)


def degraded(state):
    return bool(state.get("independenceDegraded"))


def base_degraded(state):
    return bool((state.get("config") or {}).get("baseDegraded"))


def author_family(state):
    cfg = state.get("config") or {}
    return model_registry.family_for("code-fixer", cfg.get("fixerVendor"))


def maker_author_family(state):
    return author_family(state)


def same_family_seats(state):
    return seat_map_receipts.same_family_seats(state, author_family(state))


def same_family_seats_for_receipt(state):
    return same_family_seats(state)


def same_family_degraded(state):
    return bool(same_family_seats(state))


def seat_map_violations(state):
    seen = set()
    merged = []
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
    for v in seat_map_receipts.unexcused_violations(state, author_family(state)):
        key = (str(v.get("constraint", "")), str(v.get("seat") or ""))
        if key in seen:
            continue
        seen.add(key)
        merged.append(v)
    merged.sort(
        key=lambda item: (str(item.get("constraint", "")), str(item.get("seat") or "")),
    )
    return merged


def seat_map_violated(state):
    return bool(seat_map_violations(state))


def seat_map_violation_breach_prose(v):
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


def seat_pin_excused_seats(state):
    seats = set()
    for rec in seat_map_receipts.pin_excused_records(state, author_family(state)):
        for s in rec.get("excusedSeats") or []:
            if isinstance(s, str) and s:
                seats.add(s)
    return sorted(seats)


def seat_map_unjudgeable(state):
    for rec in (state.get("rounds") or {}).values():
        if not isinstance(rec, dict):
            continue
        if rec.get("seatMapUnjudgeable"):
            return True
    return bool(seat_map_receipts.unjudgeable_receipts(state, author_family(state)))


def build_degraded_prose(state, form):
    cfg = state.get("config") or {}
    degraded_out = []
    if degraded(state):
        degraded_out.append("independence: a single live vendor — the fix's auditor is the fixer's "
                            "vendor; independence degraded and named in the certification shape")
    if base_degraded(state):
        degraded_out.append(
            "base: reviewed against a base whose fetch degraded (%s) — the pin may be stale; "
            "named in the certification shape"
            % (cfg.get("baseFetch") or "baseFetch absent"))
    if same_family_degraded(state):
        degraded_out.append(
            "panel independence: seat(s) %s were filled with the MAKER's own model family — no "
            "alternative family was live; disclosed by the seat map and named in the certification "
            "shape" % ", ".join(same_family_seats(state)))
    _pin_seats = seat_pin_excused_seats(state)
    if _pin_seats:
        degraded_out.append(
            "seat-map pin excusal: seat(s) %s authorized a disclosed constraint relaxation via pin; "
            "named in the certification shape" % ", ".join(_pin_seats))
    if seat_map_violated(state):
        _viol_parts = []
        for v in seat_map_violations(state):
            _viol_parts.append(seat_map_violation_breach_prose(v))
        _shape = (state.get("certification") or {}).get("shape")
        if isinstance(_shape, str) and _shape.endswith("-constraint-violated"):
            degraded_out.append(
                "seat-map constraint breach: %s — certification shape marked -constraint-violated"
                % ", ".join(_viol_parts))
        else:
            degraded_out.append(
                "seat-map constraint breach: %s — breach recorded; certification withheld"
                % ", ".join(_viol_parts))
    skipped_blockers = []
    for s in state.get("_skippedBlockers") or []:
        if not isinstance(s, dict):
            continue
        skipped_blockers.append({"id": s.get("id"), "title": s.get("title"),
                                 "severity": s.get("severity"), "reason": s.get("reason")})
        degraded_out.append("skipped-blocker: %r (%s:%s) owner-skipped as a product-choice tradeoff — "
                            "reason: %s" % (s.get("title"), s.get("file"), s.get("line"), s.get("reason")))
    _emitted_seat_map_unjudgeable = False
    for rkey in sorted((state.get("rounds") or {}), key=lambda k: int(k) if str(k).isdigit() else 0):
        rrec = state["rounds"][rkey]
        declared = receipt_round_disclosures(rrec, form, state)
        for row in (declared.get("fellOpen") or []):
            degraded_out.append(
                "reviewer-fell-open (round %s): seat %s configured %s forfeited (%s) → re-ran on %s; "
                "that seat's cross-vendor mix degraded" % (
                    rkey, row.get("seat"), row.get("configured"), row.get("reason"), row.get("ran")))
        miss = declared.get("fellOpenProvenanceMissing")
        if miss:
            degraded_out.append(
                "reviewer-fell-open-provenance-unavailable (round %s): cross-vendor seat(s) %s ran "
                "without a trusted ranManifest entry — fall-open provenance unverified" % (
                    rkey, ", ".join(miss)))
        smu = declared.get("seatMapUnavailable")
        if smu:
            degraded_out.append(
                "reviewer-fell-open-seatmap-unavailable (round %s): live panel vendor(s) %s "
                "but no seat map submitted — fall-open provenance unverified for the panel" % (
                    rkey, ", ".join(smu)))
        smuj = declared.get("seatMapUnjudgeable")
        if smuj:
            _emitted_seat_map_unjudgeable = True
            degraded_out.append(
                "seat-map-unjudgeable (round %s): a seat map was submitted and is readable, but "
                "its violation basis is incomplete (%s) — \"no breach\" is unproven rather than clean"
                % (rkey, ", ".join(smuj)))
        vac = declared.get("vacuousSeats")
        if vac:
            degraded_out.append(
                "vacuous-seat (round %s): seat(s) %s returned no findings and no verifiable "
                "investigation record — classed as never-ran" % (rkey, ", ".join(vac)))
        eng_art = declared.get("engagedArtifactSeats")
        if eng_art:
            degraded_out.append(
                "engaged-artifact-seat (round %s): seat(s) %s produced a review our transport "
                "could not carry — they do not count toward certification; salvaged artifacts "
                "are available for independent verification" % (rkey, ", ".join(eng_art)))
        # Record-only sampled-probe channels (#1272 l4b): ride rounds[]; no degraded prose.
        if declared.get("canaryVerified") is not None:
            pass
        if declared.get("canaryUnverified") is not None:
            pass
        if declared.get("canaryFailed") is not None:
            pass
        if declared.get("canaryOutcomeFailed") is not None:
            pass
        if declared.get("canaryPlantUndetected") is not None:
            pass
        if declared.get("controlProbe") is not None:
            pass
        roi = declared.get("recordOrphansIgnored")
        if roi:
            degraded_out.append(
                "record-orphans-ignored (round %s): hand submit folded with durable seat record(s) "
                "%s still at this slot — records ignored (session already on hand-submit path)"
                % (rkey, ", ".join(roi)))
        pcu = declared.get("priorCommentsUnavailable")
        if pcu:
            degraded_out.append(
                "prior-comments-unavailable (round %s): orchestrator did not supply "
                "prior-comments.json in PR mode — panel ran without prior PR comments; any claim "
                "that prior comments were considered is not supported for this round"
                % rkey)
        jd = declared.get("judgmentDispositions")
        if isinstance(jd, list) and jd:
            fail_closed = [e for e in jd if isinstance(e, dict) and e.get("failClosed")]
            if fail_closed:
                degraded_out.append(
                    "judgment-fail-closed (round %s): %d judgment blocker(s) had no valid owner "
                    "disposition — owner ruling not recorded; loop defaulted to fix-as-suggested"
                    % (rkey, len(fail_closed)))
        ggc = declared.get("gateGuidanceRowCarried")
        if ggc:
            degraded_out.append(
                "gate-guidance-row-carried (round %s): %d fix-batch row(s) carried the guidance "
                "key while the fold recorded none for them — row-carried text is never rendered "
                "as owner guidance" % (rkey, len(ggc)))
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
                degraded_out.append(
                    "order-vendor-provenance-gap (round %s): seat(s) %s emitted without a resolved "
                    "vendor" % (rkey, ", ".join(seats)))
        prov_by_phase = normalize_adapter_provenance(declared.get("adapterProvenance"))
        for phase_name, prov in prov_by_phase.items():
            if not isinstance(prov, dict):
                continue
            if prov.get("dispatchManifestUnavailable"):
                degraded_out.append(
                    "adapter-provenance (round %s, %s): dispatch manifest unavailable — trusted "
                    "ranManifest/collectionManifest omitted" % (rkey, phase_name))
            mismatch = prov.get("vendorEchoMismatch")
            if isinstance(mismatch, list) and mismatch:
                parts = ["%s echo=%r trusted=%r" % (row.get("seat"), row.get("echo"),
                                                     row.get("recorded", row.get("manifest")))
                         for row in mismatch if isinstance(row, dict)]
                degraded_out.append(
                    "adapter-provenance (round %s, %s): vendor echo mismatch on seat(s): %s"
                    % (rkey, phase_name, "; ".join(parts)))
    _run_unj = seat_map_receipts.unjudgeable_run_level_disclosure(
        state,
        author_family(state),
        per_round_emitted=_emitted_seat_map_unjudgeable,
        no_seat_map_submitted=not seat_map_receipts.any_seats(state),
    )
    if _run_unj and seat_map_unjudgeable(state):
        degraded_out.append(_run_unj)
    return degraded_out, skipped_blockers


__all__ = (
    "RECEIPT_FORM_CERTIFIED",
    "ROUND_ENTRY_KEY_FORMS",
    "DISCLOSE_ON_PRESENCE",
    "RESUMABLE_DISCLOSURE_CHANNELS",
    "VENDOR_SOURCE_DEFAULTED",
    "str_list",
    "dict_list",
    "bool_value",
    "canary_failed_shape",
    "canary_verified_shape",
    "control_probe_shape",
    "adapter_provenance_shape",
    "order_vendor_provenance_gaps_shape",
    "normalize_adapter_provenance",
    "declared_disclosures",
    "round_entry_key_declared",
    "round_entry_key_allowed",
    "receipt_round_disclosures",
    "live_vendors",
    "independent_auditor",
    "independent_auditor_available",
    "degraded",
    "base_degraded",
    "author_family",
    "maker_author_family",
    "same_family_seats",
    "same_family_seats_for_receipt",
    "same_family_degraded",
    "seat_map_violations",
    "seat_map_violated",
    "seat_map_violation_breach_prose",
    "seat_pin_excused_seats",
    "seat_map_unjudgeable",
    "build_degraded_prose",
)
