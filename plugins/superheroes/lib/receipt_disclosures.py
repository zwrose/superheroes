#!/usr/bin/env python3
"""Disclosure-channel vocabulary, selection rule, and degraded-prose collector — leaf module."""
import liveness_cache
import model_registry
import round_phases
import seat_map
import seat_map_receipts
import session_contract
from seat_map import is_unfilled as seat_is_unfilled

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

def str_list(value):
    return isinstance(value, list) and all(isinstance(x, str) for x in value)


def dict_list(value):
    return isinstance(value, list) and all(isinstance(x, dict) for x in value)


def bool_value(value):
    return isinstance(value, bool)


def verify_via_shape(value):
    return isinstance(value, dict) and isinstance(value.get("via"), str)


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


CARRIED_DISCLOSURE_CHANNELS = {
    "fellOpen": dict_list,
    "fellOpenProvenanceMissing": str_list,
    "seatMapUnavailable": str_list,
    "seatMapUnjudgeable": str_list,
    "seatMapViolations": dict_list,
    "vacuousSeats": str_list,
    "engagedArtifactSeats": str_list,
    "adapterProvenance": adapter_provenance_shape,
    "recordOrphansIgnored": str_list,
    "orderVendorProvenanceGaps": order_vendor_provenance_gaps_shape,
    "priorCommentsUnavailable": bool_value,
    "verifyPasses": dict_list,
    "verifierProvenance": dict_list,
    "synthesisUnseatable": dict_list,
    "secondTestUnseatable": dict_list,
    "sweeps": dict_list,
    "judgmentDispositions": dict_list,
    "gateGuidanceRowCarried": dict_list,
    "breakItRuns": dict_list,
    "breakItKept": dict_list,
    "verifyVia": verify_via_shape,
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
    for chan, shape_ok in CARRIED_DISCLOSURE_CHANNELS.items():
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


def independent_auditor(config, fixer_vendor, runner_only=False, maker_families=frozenset(),
                        pinned_vendors=None):
    """The first live vendor whose auditor family is neither the build session's nor any maker's.

    ``maker_families`` are the families the seat map lists as makers; ``pinned_vendors``, when a
    non-empty set, narrows the pool to those vendors (a pinned roster names who may audit)."""
    fixer_fam = model_registry.family_for("implementer", fixer_vendor)
    if fixer_fam is None:
        return None, None
    barred = set(maker_families or ())
    barred.add(fixer_fam)
    for v in live_vendors(config):
        if runner_only and not session_contract.runner_channel_vendor(v):
            continue
        if pinned_vendors and v not in pinned_vendors:
            continue
        if v != fixer_vendor:
            cand_fam = model_registry.family_for("auditor", v)
            if cand_fam is not None and cand_fam not in barred:
                return v, fixer_fam
    return None, fixer_fam


# Sentinel for `reviewer_ineligible(host_family=...)`: judge every vendor by its registry family.
HOST_FAMILY_REGISTRY = object()

# The dispatched-cell roles of the non-panel phases (`model_registry.matrix_config` rows).
# One home: `seat_map.NONPANEL_CELL_ROLES` (verifier, finder, synthesis, in that order) — composition
# probes those cells and selection consumes them; this unpacking fails loudly if the arity drifts.
NONPANEL_ROLES = seat_map.NONPANEL_CELL_ROLES
NONPANEL_ROLE_VERIFIER, NONPANEL_ROLE_FINDER, NONPANEL_ROLE_SYNTHESIS = NONPANEL_ROLES

_SEAT_MAP_HOST_KEY = "hostFamily"
_SEAT_MAP_CELLS_KEY = "nonPanelLiveCells"
_SEAT_MAP_CELLS_SOURCE_KEY = "nonPanelLiveCellsSource"


def host_family(seat_map_):
    """The seat map's `hostFamily` when it is a non-empty string, else None (host model unknown)."""
    fam = seat_map_.get(_SEAT_MAP_HOST_KEY) if isinstance(seat_map_, dict) else None
    return fam if isinstance(fam, str) and fam else None


def reviewer_ineligible(maker_families=frozenset(), fixer_vendor=None,
                        host_family=HOST_FAMILY_REGISTRY):
    """Predicate ``(vendor) -> bool``: True when ``vendor`` may not review. The one home of the
    reviewer-independence bar: barred families are the makers' plus the fixer's (a fixer is a maker
    by definition); the fixer's own vendor never reviews its fix whatever its family resolves to; a
    family ``family_for`` cannot resolve is never independent.

    ``host_family`` (default: the registry family for every vendor): when passed, a registered vendor
    that is not a runner-channel vendor runs as a native host seat, so it takes ``host_family`` as
    its family and is ineligible when that is None or not a non-empty string (host model unknown)."""
    barred = set(maker_families or ())
    if fixer_vendor:
        fixer_fam = model_registry.family_for("implementer", fixer_vendor)
        if fixer_fam is not None:
            barred.add(fixer_fam)

    def is_ineligible(vendor):
        if fixer_vendor and vendor == fixer_vendor:
            return True
        if (host_family is not HOST_FAMILY_REGISTRY
                and vendor in model_registry.vendors()
                and not session_contract.runner_channel_vendor(vendor)):
            fam = host_family if isinstance(host_family, str) and host_family else None
        else:
            fam = model_registry.family_for("reviewer", vendor)
        return fam is None or fam in barred
    return is_ineligible


def independent_reviewer(config, preferred_vendor, maker_families=frozenset(), fixer_vendor=None,
                         host_family=HOST_FAMILY_REGISTRY):
    """``(vendor, family)`` of a reviewer outside every maker family, else ``(None, None)``.

    The preferred vendor wins when it is live and eligible (`reviewer_ineligible`); otherwise the
    first live vendor that qualifies. ``host_family`` is passed to `reviewer_ineligible`; when passed,
    a native host seat's returned family is the host family."""
    ineligible = reviewer_ineligible(maker_families, fixer_vendor, host_family=host_family)
    live = list(live_vendors(config))
    candidates = ([preferred_vendor] if isinstance(preferred_vendor, str) and preferred_vendor
                  and preferred_vendor in live else [])
    candidates += [v for v in live if v not in candidates]
    for v in candidates:
        if not ineligible(v):
            native = (host_family is not HOST_FAMILY_REGISTRY and v in model_registry.vendors()
                      and not session_contract.runner_channel_vendor(v))
            return v, (host_family if native else model_registry.family_for("reviewer", v))
    return None, None


def _nonpanel_cell_evidence(seat_map_):
    """The set of normalized ``(vendor, model, effort)`` triples the map proves live — empty unless
    the source is `probed` or `synthesized` and `nonPanelLiveCells` is a list (malformed entries are
    skipped). A map with none of the three cell-proof keys, or no map at all, proves no cell."""
    sm = seat_map_ if isinstance(seat_map_, dict) else {}
    source = sm.get(_SEAT_MAP_CELLS_SOURCE_KEY)
    raw = sm.get(_SEAT_MAP_CELLS_KEY)
    if (source not in (liveness_cache.LIVE_CELLS_SOURCE_PROBED,
                       liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED)
            or not isinstance(raw, list)):
        return frozenset()
    cells = set()
    for entry in raw:
        normalized = seat_map._normalize_live_cell(entry)
        if normalized is not None:
            cells.add(normalized)
    return frozenset(cells)


def _dispatched_cell(role, vendor):
    """The ``(vendor, model, effort)`` triple a non-panel ``role`` dispatches on ``vendor``, else None."""
    if role not in NONPANEL_ROLES:
        return None
    cell = model_registry.matrix_config(role, vendor)
    if cell is None:
        return None
    return (vendor, cell[0], cell[1])


def nonpanel_cell_proven(config, seat_map_, vendor, role):
    """True when ``vendor``'s dispatched cell for the non-panel ``role`` (`verifier` for verifiers,
    `reviewer-deep` for seams check and scoped) is proven live: `claude` always (a host seat, never
    probed — the panel's rule); for any other vendor only when the map's `nonPanelLiveCells` lists the
    cell under a `probed` / `synthesized` source. Any other shape proves nothing, including a map with
    none of the cell-proof keys and no map at all."""
    if not isinstance(vendor, str) or not vendor:
        return False
    if vendor == "claude":
        return True
    cell = _dispatched_cell(role, vendor)
    return cell is not None and cell in _nonpanel_cell_evidence(seat_map_)


def nonpanel_candidates(config, seat_map_, role):
    """The non-panel candidate pool for ``role``: `live_vendors(config)` followed by every registry
    vendor (registry order) the map's `nonPanelLiveCells` proves for ``role`` and that is not
    already listed. Candidates are not yet filtered by `nonpanel_cell_proven` or independence."""
    out = list(live_vendors(config))
    cells = _nonpanel_cell_evidence(seat_map_)
    for v in model_registry.VENDORS:
        if v not in out and _dispatched_cell(role, v) in cells:
            out.append(v)
    return out


def nonpanel_reviewer(config, seat_map_, role, preferred_vendor, maker_families=frozenset(),
                      fixer_vendor=None):
    """``(vendor, family)`` of the non-panel reviewer for ``role``, else ``(None, None)``: the first
    candidate (the preferred vendor first when it is one) whose dispatched cell is proven live
    (`nonpanel_cell_proven`) and that is outside every maker family (`reviewer_ineligible`, with
    the seat map's host family standing for a native seat)."""
    host = host_family(seat_map_)
    ineligible = reviewer_ineligible(maker_families, fixer_vendor, host_family=host)
    pool = nonpanel_candidates(config, seat_map_, role)
    candidates = ([preferred_vendor] if isinstance(preferred_vendor, str) and preferred_vendor
                  and preferred_vendor in pool else [])
    candidates += [v for v in pool if v not in candidates]
    for v in candidates:
        if not nonpanel_cell_proven(config, seat_map_, v, role) or ineligible(v):
            continue
        native = v in model_registry.vendors() and not session_contract.runner_channel_vendor(v)
        return v, (host if native else model_registry.family_for("reviewer", v))
    return None, None


def unfilled_seats(seat_map, roster=()):
    """Names of the seats the map marks `source == "unfilled"` (no candidate outside the makers), and the seats of
    `roster` whose lens the map leaves unfilled (a slice seat is unfilled when its lens is)."""
    seats = seat_map.get("seats") if isinstance(seat_map, dict) else None
    if not isinstance(seats, dict):
        return frozenset()
    names = frozenset(name for name, entry in seats.items()
                      if seat_is_unfilled(entry))
    if not names or not isinstance(roster, (list, tuple)):
        return names
    return names | frozenset(key for key in roster if round_phases.seat_lens(key) in names)


def maker_families(seat_map):
    """The map's `makerFamilies` as a set of family strings; an old map without the key names its maker through `authorFamily`."""
    raw = seat_map.get("makerFamilies") if isinstance(seat_map, dict) else None
    if not isinstance(raw, list):
        legacy = seat_map.get("authorFamily") if isinstance(seat_map, dict) else None
        return frozenset([legacy]) if isinstance(legacy, str) and legacy else frozenset()
    return frozenset(f for f in raw if isinstance(f, str) and f)


def pinned_auditor_vendors(seat_map):
    """Vendors of the pinned seats, only when every filled seat of the map is pinned; else None."""
    seats = seat_map.get("seats") if isinstance(seat_map, dict) else None
    if not isinstance(seats, dict):
        return None
    filled = [e for e in seats.values()
              if isinstance(e, dict) and not seat_is_unfilled(e)]
    if not filled or any(e.get("source") != "pinned" for e in filled):
        return None
    vendors = {e.get("vendor") for e in filled if isinstance(e.get("vendor"), str) and e.get("vendor")}
    return vendors or None


def accumulated_maker_families(state):
    """Every maker family any submitted seat map named, plus the effective map's: a later, recomposed
    map that omits an earlier maker does not release it — the receipt writer unions them, so the
    decisions that read makers do too. Seat identities still come from the latest map alone. The
    families of external fixers a session upgrade replaced (`state["formerFixerFamilies"]`) join
    them: their commits stay in the step, so they stay makers."""
    if not isinstance(state, dict):
        return frozenset()
    former = state.get("formerFixerFamilies")
    return (maker_families(seat_map_receipts.effective_seat_map(state))
            | (seat_map_receipts.maker_family_union(seat_map_receipts.receipts(state)) or frozenset())
            | frozenset(f for f in (former if isinstance(former, list) else ())
                        if isinstance(f, str) and f))


def nonpanel_barred(state, config):
    """Predicate ``(vendor) -> bool``: True when a vendor may not review a non-panel round — the one
    home of the non-panel eligibility bar, so the driver and the adapters judge a vendor identically:
    the accumulated makers, the configured fixer's vendor, and the host family a native seat takes
    from the effective seat map. A ``config`` that is not a dict reads as empty."""
    cfg = config if isinstance(config, dict) else {}
    return reviewer_ineligible(accumulated_maker_families(state), cfg.get("fixerVendor"),
                               host_family=host_family(seat_map_receipts.effective_seat_map(state)))


def auditor_constraints(state):
    """(maker_families, pinned_vendors) for `independent_auditor`: makers accumulate over every
    seat-map receipt; the pinned vendors come off the effective seat map."""
    seat_map = seat_map_receipts.effective_seat_map(state) if isinstance(state, dict) else {}
    return accumulated_maker_families(state), pinned_auditor_vendors(seat_map)


def independent_auditor_available(config, maker_families=frozenset(), pinned_vendors=None):
    fixer = config.get("fixerVendor") if isinstance(config, dict) else None
    vendor, fam = independent_auditor(config, fixer, maker_families=maker_families,
                                      pinned_vendors=pinned_vendors)
    return (vendor is not None, fam)


def degraded(state):
    return bool(state.get("independenceDegraded"))


def base_degraded(state):
    return bool((state.get("config") or {}).get("baseDegraded"))


def author_family(state):
    cfg = state.get("config") or {}
    return model_registry.family_for("implementer", cfg.get("fixerVendor"))


def maker_author_family(state):
    return author_family(state)


def seat_judgment_family(state):
    """The author family every seat-map judgment (violations, same-family seats, pin excuses,
    unjudgeable receipts) is made against. `config.fixerVendor` names the fix maker (the build
    session's host family on the CLI path), which differs from the original author when the map
    declares a distinct `hostFamily`: then the map's own `authorFamily` is the author, so a legitimate
    split-family composition is not recorded as an `author-family-mismatch`."""
    family = author_family(state)
    seat_map_obj = seat_map_receipts.effective_seat_map(state) if isinstance(state, dict) else {}
    host, author = seat_map_obj.get("hostFamily"), seat_map_obj.get("authorFamily")
    if (isinstance(host, str) and host and isinstance(author, str) and author
            and host != author and family == host):
        return author
    return family


def same_family_seats(state):
    return seat_map_receipts.same_family_seats(state, seat_judgment_family(state))


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
    for v in seat_map_receipts.unexcused_violations(state, seat_judgment_family(state)):
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
    for rec in seat_map_receipts.pin_excused_records(state, seat_judgment_family(state)):
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
    return bool(seat_map_receipts.unjudgeable_receipts(state, seat_judgment_family(state)))


def latest_recorded_events(journal):
    if not isinstance(journal, list):
        return []
    latest = {}
    for event in journal:
        if not isinstance(event, dict) or event.get("outcome") != "recorded":
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
        if not isinstance(seat, str) or not seat:
            continue
        occurrence = event.get("occurrence", 0)
        key = (phase, rnd, attempt, seat, occurrence)
        identity = {
            "seat": seat,
            "phase": phase,
            "round": rnd,
            "attempt": attempt,
            "occurrence": occurrence,
            "provenance": provenance,
        }
        latest[key] = (identity, event)
    return list(latest.values())


def _is_missing_seat_record(event):
    return (event.get("cmd") == "record-missing"
            or event.get("casToken") == session_contract.SEAT_MISSING_SCHEMA)


def _native_in_session_seats(journal):
    disclosed = set()
    for identity, event in latest_recorded_events(journal):
        if _is_missing_seat_record(event):
            continue
        seat = identity["seat"]
        transport = event.get(session_contract.SEAT_TRANSPORT_KEY)
        if transport in session_contract.SEAT_TRANSPORTS_DISCLOSED:
            disclosed.add(seat)
        elif transport in session_contract.SEAT_TRANSPORTS:
            continue
        else:
            disclosed.add(seat)
    return sorted(disclosed)


def build_degraded_prose(state, form, journal=None):
    cfg = state.get("config") or {}
    degraded_out = []
    if degraded(state):
        degraded_out.append("independence: no live vendor outside the fixer's and the makers' "
                            "families — the fix's audit did not run; independence degraded and "
                            "named in the certification shape")
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
        # Nothing writes this channel now; it reads only an older session's stored disclosure.
        ggc = declared.get("gateGuidanceRowCarried")
        if ggc:
            degraded_out.append(
                "gate-guidance-row-carried (round %s): %d fix-batch row(s) carried the guidance "
                "key while the fold recorded none for them — row-carried text is never rendered "
                "as owner guidance" % (rkey, len(ggc)))
        vvia = declared.get("verifyVia")
        # axis: the receipt discloses a CI stand-in for the local verify — see bite-proof record wo_b_2072_ci_verify
        if vvia and vvia.get("via") == "ci-exact-head":
            degraded_out.append(
                "verify-via-ci (round %s): CI workflow %s run %s on %s (%s) stood in for the local "
                "verify command: %s" % (rkey, vvia.get("workflow"), vvia.get("runId"),
                                        str(vvia.get("headSha"))[:7], vvia.get("conclusion"),
                                        vvia.get("reason")))
        bir = declared.get("breakItRuns")
        if bir:
            not_run = [r for r in bir if r.get("outcome") == "not-run"]
            if not_run:
                degraded_out.append(
                    "break-it-test-not-run (round %s): %d break-it test(s) could not be run (%s) "
                    "— the finding was kept without a recorded failing run"
                    % (rkey, len(not_run),
                       ", ".join("%s: %s" % (r.get("path"), r.get("reason")) for r in not_run)))
        vprov = declared.get("verifierProvenance")
        if vprov:
            ignored = [r for r in vprov if isinstance(r, dict) and r.get("outcome") == "verdicts-ignored"]
            if ignored:
                degraded_out.append(
                    "verifier-verdicts-ignored (round %s): verdicts not folded — %s"
                    % (rkey, "; ".join(
                        "expected %s, ran %s%s" % (
                            r.get("expected"), r.get("ran"),
                            " (%s)" % r.get("reason") if r.get("reason") else "")
                        for r in ignored)))
        syn = declared.get("synthesisUnseatable")
        if syn:
            degraded_out.append(
                "synthesis-unseatable (round %s): no grouping seat outside the makers' families on a "
                "proven cell — findings were not grouped (nothing dropped)" % rkey)
        stu = declared.get("secondTestUnseatable")
        if stu:
            degraded_out.append(
                "second-test-unseatable (round %s): no second-test seat outside the makers' families on a "
                "proven cell — %d held finding(s) were graded with the test they have (nothing dropped)"
                % (rkey, sum(len(r.get("held") or []) for r in stu if isinstance(r, dict))))
        sweeps = declared.get("sweeps")
        if sweeps:
            # axis: a sweep that did not run, a part no searcher answered and a hit left ungraded are each a degradation of the repository search, never a pass that hides them
            for sweep in sweeps:
                if not isinstance(sweep, dict):
                    continue
                if sweep.get("notRun"):
                    degraded_out.append(
                        "sweep-not-run (round %s): %s for \"%s\" — %s; no search ran and nothing stood in"
                        % (rkey, sweep.get("sweepId"), sweep.get("title"), sweep.get("notRun")))
                missing = sweep.get("missing")
                if isinstance(missing, list) and missing:
                    degraded_out.append(
                        "sweep-incomplete (round %s): %s — searcher part(s) %s returned nothing; the search "
                        "did not cover those files" % (rkey, sweep.get("sweepId"), ", ".join(str(m) for m in missing)))
            ungraded = sum(s.get("ungraded") for s in sweeps
                           if isinstance(s, dict) and isinstance(s.get("ungraded"), int)
                           and not isinstance(s.get("ungraded"), bool))
            if ungraded:
                degraded_out.append(
                    "sweep-hit-ungraded (round %s): %d sweep hit(s) left open without a verifier grade"
                    % (rkey, ungraded))
        bik =declared.get("breakItKept")
        if bik:
            # axis: a row the owner ruled out of scope and the audit cleared is not a test the final change failed to hold — see bite-proof record wo_a_2072_ruled_exempt
            not_kept = [r for r in bik if r.get("outcome") not in ("kept", "not-required", "ruled-out-of-scope")]
            if not_kept:
                degraded_out.append(
                    "break-it-test-not-kept (round %s): %d fixed break-it test(s) not held in the "
                    "final change (%s) — certification withheld"
                    % (rkey, len(not_kept),
                       ", ".join("%s: %s" % (r.get("path"), r.get("outcome")) for r in not_kept)))
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
        seat_judgment_family(state),
        per_round_emitted=_emitted_seat_map_unjudgeable,
        no_seat_map_submitted=not seat_map_receipts.any_seats(state),
    )
    if _run_unj and seat_map_unjudgeable(state):
        degraded_out.append(_run_unj)
    native_seats = _native_in_session_seats(journal)
    if native_seats:
        degraded_out.append(
            "unprobed native seat(s) %s: seats with no runner execution record — run in-session on "
            "the host model, fallen open to it, or landed by hand — are declared live, never "
            "probed; their engagement rests on the seat's own record"
            % ", ".join(native_seats))
    return degraded_out, skipped_blockers


__all__ = (
    "RECEIPT_FORM_CERTIFIED",
    "ROUND_ENTRY_KEY_FORMS",
    "CARRIED_DISCLOSURE_CHANNELS",
    "VENDOR_SOURCE_DEFAULTED",
    "str_list",
    "dict_list",
    "bool_value",
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
    "independent_reviewer",
    "nonpanel_reviewer",
    "nonpanel_cell_proven",
    "nonpanel_candidates",
    "host_family",
    "unfilled_seats",
    "maker_families",
    "pinned_auditor_vendors",
    "auditor_constraints",
    "degraded",
    "base_degraded",
    "author_family",
    "maker_author_family",
    "seat_judgment_family",
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
