"""Deterministic panel seat-map composition engine (issue #510).

Pure, stdlib-only. Derives all model/vendor data from model_registry — no parallel literals.

Needed-set shape: {vendor: [[model, effort], ...]} — positional [model, effort]; produced by
preflight_probe.needed_configs_for and seat_map.reachable_configs, consumed by liveness_cache.
"""
from __future__ import annotations

import hashlib
import itertools
import math

import liveness_cache
from model_registry import family_for, is_allowed, matrix_config, vendors
import version_skew

LIVE_CELLS_SOURCES = liveness_cache.LIVE_CELLS_SOURCES

LENS_SEATS = (
    "architecture-reviewer",
    "code-reviewer",
    "security-reviewer",
    "test-reviewer",
    "premortem-reviewer",
)
GROUNDING_SEAT = "grounding-seat"
PANEL_ROSTER = LENS_SEATS + (GROUNDING_SEAT,)
STRONG_TIER_SEATS = frozenset({"security-reviewer", "architecture-reviewer"})
STRONG_TIER_REQUIRED = "reviewer-deep"
CRITICAL_SEATS = frozenset({"security-reviewer", "premortem-reviewer", "code-reviewer"})
MIN_CRITICAL_FAMILIES = 2
# The maker's model family is barred from EVERY panel seat (#670, owner-ratified 2026-07-26) — the
# five lens seats AND the grounding seat, not merely the strong-tier/critical subset. `test-reviewer`
# was the hole: it is neither strong-tier nor critical, so post-#651 (cursor's first-party models are
# ONE `xai` family) a composer-made diff could have cursor-grok reviewing its own tests with no
# violation recorded. STRONG_TIER_SEATS / CRITICAL_SEATS keep their OTHER jobs (the reviewer-deep bar
# and the critical-diversity bar) unchanged.
MAKER_EXCLUDED_SEATS = frozenset(PANEL_ROSTER)
# Degradation constraints that mean the liveness set was SYNTHESIZED rather than probed. A seat map
# carrying any of these cannot prove an alternative family was absent, so a maker-family seat under
# one is a violation, never an excused degradation (#670 review).
UNPROVEN_LIVENESS_CONSTRAINTS = frozenset({
    "live-vendors",           # build() synthesized ["claude"] when handed no live vendors
    # No live producer since the cache-only receipt-only path was reaped (#1138) — RETAINED
    # deliberately: this set is read against seat maps supplied from outside this process
    # (`round_driver` persists and re-reads `seatMap`), so a map written by an older plugin
    # version can still carry the constraint. Dropping the member would make that stale map
    # read as PROVEN liveness — a fall-open, not a cleanup.
    "preflight-cache-only",   # legacy receipt: vendors were never probed
    "compose-failed",         # compose blew up and every seat fell open to Claude
})
DEFAULT_TIER_BY_SEAT = {s: "reviewer-deep" for s in LENS_SEATS}
DEFAULT_TIER_BY_SEAT[GROUNDING_SEAT] = "reviewer"

ALT_LIVE = "alternative-live"
ALT_NONE = "no-alternative-live"
ALT_UNUSABLE = "evidence-unusable"


def _same_family_record(seat: str, family: str) -> dict:
    """The disclosed-degradation record for a seat that had to take the maker's own family because no
    alternative family was live (#670). Degradation, NOT violation — the panel still runs, and the
    self-review is named in the receipt instead of reading as clean."""
    return {
        "constraint": "same-family",
        "seat": seat,
        "reason": "seat %s seated the maker family %s — no alternative family is live" % (seat, family),
    }


def _seat_tier(seat: str, cfg: dict) -> str:
    tier = cfg.get("tier")
    if isinstance(tier, str) and tier:
        return tier
    return DEFAULT_TIER_BY_SEAT.get(seat, "reviewer")


def _normalize_live_cell(entry) -> tuple[str, str, str | None] | None:
    if isinstance(entry, (list, tuple)) and len(entry) == 3:
        vendor, model, effort = entry[0], entry[1], entry[2]
        if isinstance(vendor, str) and vendor and isinstance(model, str) and model:
            return (vendor, model, effort)
    return None


def _synthesize_live_cells(
    live_vendors: list[str],
    roster: tuple[str, ...] | list[str],
    tier_by_seat: dict[str, str] | None,
) -> set[tuple[str, str, str | None]]:
    tiers_map = dict(DEFAULT_TIER_BY_SEAT)
    if tier_by_seat:
        tiers_map.update(tier_by_seat)
    tiers_in_play = {tiers_map.get(s, "reviewer") for s in roster}
    cells: set[tuple[str, str, str | None]] = set()
    for vendor in live_vendors:
        if not isinstance(vendor, str) or not vendor:
            continue
        for tier in tiers_in_play:
            cell = matrix_config(tier, vendor)
            if cell is None:
                continue
            model, effort = cell
            if is_allowed(tier, vendor, model, effort):
                cells.add((vendor, model, effort))
    return cells


def _live_cells_fields_for_receipt(seat_map: dict) -> tuple[list, str]:
    raw_cells = seat_map.get("liveCells")
    raw_source = seat_map.get("liveCellsSource")
    if isinstance(raw_cells, list) and raw_source in LIVE_CELLS_SOURCES:
        return list(raw_cells), raw_source
    live = seat_map.get("liveVendors")
    if isinstance(live, list) and live:
        roster = tuple(seat_map.get("seats", {}).keys()) or PANEL_ROSTER
        synthesized = _synthesize_live_cells(live, roster, None)
        return sorted([list(c) for c in synthesized]), liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED
    return [], liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED


def _resolvable_families_for_seat(
    seat_map: dict, seat: str, cfg: dict, tier: str | None = None,
) -> set[str] | None:
    """Every registry family this seat could have been filled with at `tier`, from the map's live
    vendors. `None` = evidence UNUSABLE. An EMPTY SET = usable evidence, nothing resolvable at that
    tier. `tier` defaults to the seat's own recorded tier; a caller asking about a REQUIRED tier
    passes it explicitly (#680 round 3)."""
    pin_scoped = seat_map.get("livenessPinScoped")
    if pin_scoped is not False:
        return None
    raw_degs = seat_map.get("degradations")
    if raw_degs is not None and not isinstance(raw_degs, list):
        return None
    degradations = raw_degs if isinstance(raw_degs, list) else []
    for deg in degradations:
        if isinstance(deg, dict) and deg.get("constraint") in UNPROVEN_LIVENESS_CONSTRAINTS:
            return None
    cells_source = seat_map.get("liveCellsSource")
    if cells_source == liveness_cache.LIVE_CELLS_SOURCE_UNPROBED:
        return None
    known_vendors = set(vendors())
    tier = tier or _seat_tier(seat, cfg)
    families: set[str] = set()
    if cells_source == liveness_cache.LIVE_CELLS_SOURCE_PROBED:
        raw_cells = seat_map.get("liveCells")
        if not isinstance(raw_cells, list):
            return None
        live_cell_set: set[tuple[str, str, str | None]] = set()
        for entry in raw_cells:
            normalized = _normalize_live_cell(entry)
            if normalized is None:
                return None
            vendor, _model, _effort = normalized
            if vendor not in known_vendors:
                return None
            live_cell_set.add(normalized)
        for vendor in known_vendors:
            cell = matrix_config(tier, vendor)
            if cell is None:
                continue
            model, effort = cell
            if (vendor, model, effort) not in live_cell_set:
                continue
            fam = family_for(tier, vendor)
            if fam is None or not is_allowed(tier, vendor, model, effort):
                continue
            families.add(fam)
        # claude is always live and is never probed — count its registry cell at this tier
        claude_cell = matrix_config(tier, "claude")
        if claude_cell is not None:
            model, effort = claude_cell
            fam = family_for(tier, "claude")
            if fam is not None and is_allowed(tier, "claude", model, effort):
                families.add(fam)
        return families
    # synthesized and absent source fall through: synthesized cells derive from the
    # pessimistic liveVendors rollup, so vendor-level evidence is never less conservative.
    live = seat_map.get("liveVendors")
    if not isinstance(live, list) or not live:
        return None
    for vendor in live:
        if not isinstance(vendor, str) or not vendor or vendor not in known_vendors:
            return None
    for vendor in live:
        cell = matrix_config(tier, vendor)
        if cell is None:
            continue
        model, effort = cell
        fam = family_for(tier, vendor)
        if fam is None or not is_allowed(tier, vendor, model, effort):
            continue
        families.add(fam)
    return families


def _alternative_family_evidence(
    seat_map: dict, seat: str, cfg: dict, author_family: str,
) -> str:
    """Per-seat tri-state: proved no alternative, proved alternative live, or evidence unusable."""
    if not isinstance(author_family, str) or not author_family:
        return ALT_UNUSABLE
    fams = _resolvable_families_for_seat(seat_map, seat, cfg)
    if fams is None or fams == set():
        return ALT_UNUSABLE
    if fams - {author_family}:
        return ALT_LIVE
    return ALT_NONE


def _alternative_family_live(seat_map: dict, seat: str, cfg: dict, author_family: str) -> bool:
    """Could some live vendor have seated THIS seat at a family other than the maker's?

    FAIL-CLOSED: this answers "is the alternative *disproved*", so every form of unusable evidence
    returns True — i.e. an unexplained maker-family seat reads as a VIOLATION, never as an excused
    degradation on silence. Only a well-formed, registry-resolvable receipt can authorize the
    degradation branch.
    """
    return _alternative_family_evidence(seat_map, seat, cfg, author_family) != ALT_NONE


def _critical_families(seats: dict) -> set[str]:
    """The distinct families across the seated CRITICAL_SEATS — verify()'s counting rule extracted
    for clarity. classify_violations asks a different question (families reachable, not seated); the
    shared invariant between the two paths is MIN_CRITICAL_FAMILIES (#680 round 3)."""
    return {
        fam
        for s in CRITICAL_SEATS
        if s in seats
        for fam in [seats[s].get("family") if isinstance(seats.get(s), dict) else None]
        if isinstance(fam, str) and fam
    }


def same_family_degradations(seat_map: dict, author_family: str | None) -> list[dict]:
    """Derive the `same-family` records a seat map implies. `build()` records these directly; this
    derives the same records for a hand-built or replayed map so a receipt is never silent about a
    maker-family seat. Idempotent — `to_receipt` dedupes by (constraint, seat)."""
    seats = seat_map.get("seats")
    if not isinstance(seats, dict) or not author_family:
        return []
    out: list[dict] = []
    for seat in PANEL_ROSTER:
        cfg = seats.get(seat)
        if not isinstance(cfg, dict) or cfg.get("family") != author_family:
            continue
        if _alternative_family_live(seat_map, seat, cfg, author_family):
            continue
        out.append(_same_family_record(seat, author_family))
    return out


def normalize_pins(pins):
    """The one chokepoint every pin map passes through (#1039).

    Invariant: **every value in the returned map is a dict**, so no pin value shape can reach a
    resolver as a non-dict and raise. A bare string pin is EXACTLY the object pin
    ``{"vendor": <string>}`` — the documented shorthand, resolved down the identical honorability
    path (including a padded or empty vendor, which stays as unhonorable as the object form).
    Any other value shape — null, number, bool, list — is named, never crashed on.

    Returns ``(normalized, errors)``; ``errors`` are refusal tokens: ``pins-invalid`` when the pin
    map itself is not an object, ``pins-invalid:<seat>`` per unusable seat value. Never raises.
    """
    # bite-axis: pin-value shape — dict passes through, str becomes {"vendor": str}, every other
    # shape is refused by name (the axis is REFUSAL, not the resolved seat).
    if pins is None:
        return {}, []
    if not isinstance(pins, dict):
        return {}, ["pins-invalid"]
    normalized: dict = {}
    errors: list[str] = []
    for seat, pin in pins.items():
        if isinstance(pin, dict):
            normalized[seat] = pin
        elif isinstance(pin, str):
            normalized[seat] = {"vendor": pin}
        else:
            errors.append("pins-invalid:%s" % seat)
    return normalized, errors


def reachable_configs(configured_vendors, pins, roster=None, tier_by_seat=None):
    """Pin-constrained needed set: {vendor: [[model, effort], ...]}. Claude is never probed."""
    roster = tuple(roster) if roster else PANEL_ROSTER
    tiers_map = dict(DEFAULT_TIER_BY_SEAT)
    if tier_by_seat:
        tiers_map.update(tier_by_seat)

    pins, _pin_errors = normalize_pins(pins)  # #1039: string shorthand in, unusable shapes out

    reachable: dict[str, set[tuple]] = {v: set() for v in configured_vendors}

    def _tier_for(seat: str) -> str:
        return (
            (tier_by_seat or {}).get(seat)
            or tiers_map.get(seat)
            or DEFAULT_TIER_BY_SEAT.get(seat)
            or "reviewer"
        )

    def _add_cell(vendor: str, tier: str) -> None:
        cell = matrix_config(tier, vendor)
        if cell is not None:
            reachable[vendor].add(cell)

    def _rotate_all(tier: str) -> None:
        for cv in configured_vendors:
            _add_cell(cv, tier)

    for seat in roster:
        tier = _tier_for(seat)
        pin = pins.get(seat)
        if isinstance(pin, dict) and isinstance(pin.get("vendor"), str) and pin["vendor"].strip():
            v = pin["vendor"].strip()
            if v == "claude":
                continue
            if v in configured_vendors:
                cell = matrix_config(tier, v)
                default_model, default_effort = cell if cell is not None else (None, None)
                model = pin.get("model", default_model)
                effort = pin.get("effort", default_effort)
                pin_model_bad = "model" in pin and not isinstance(pin.get("model"), (str, type(None)))
                pin_effort_bad = "effort" in pin and not isinstance(pin.get("effort"), (str, type(None)))
                well_typed = not pin_model_bad and not pin_effort_bad
                honorable = (
                    cell is not None
                    and well_typed
                    and is_allowed(tier, v, model, effort)
                )
                if honorable:
                    reachable[v].add((model, effort))
                else:
                    _rotate_all(tier)
            else:
                _rotate_all(tier)
        else:
            _rotate_all(tier)

    out: dict[str, list] = {}
    for v in configured_vendors:
        out[v] = [[m, e] for m, e in sorted(reachable[v])]
    return out


def seed_from(pr_number: int | str | None, head_sha: str | None) -> int:
    if pr_number:
        raw = str(pr_number)
        return int(hashlib.sha256(raw.encode()).hexdigest()[:8], 16)
    if head_sha:
        return int(hashlib.sha256(head_sha.encode()).hexdigest()[:8], 16)
    return 0


def build(
    roster: tuple[str, ...] | list[str] | None,
    live_vendors: list[str] | None,
    author_family: str | None,
    narrative_family: str | None,
    seed: int,
    tier_by_seat: dict[str, str] | None = None,
    pins: dict[str, dict] | None = None,
    liveness_pin_scoped: bool = False,
    live_cells: list | None = None,
    live_cells_source: str | None = None,
) -> dict:
    degradations: list[dict[str, str]] = []
    tier_degraded_seats: set[str] = set()

    roster = tuple(roster) if roster else PANEL_ROSTER

    live = [v for v in (live_vendors or []) if isinstance(v, str) and v]

    if live_cells is None:
        live_cells_normalized = _synthesize_live_cells(live, roster, tier_by_seat)
        resolved_cells_source = live_cells_source
    else:
        live_cells_normalized = set()
        for entry in live_cells:
            normalized = _normalize_live_cell(entry)
            if normalized is not None:
                live_cells_normalized.add(normalized)
        # Advisory default for callers that pass live_cells without a source; main() never reaches this.
        resolved_cells_source = live_cells_source or "probed"

    seating_vendors = sorted({v for (v, _m, _e) in live_cells_normalized})
    if "claude" in live:
        seating_vendors = sorted(set(seating_vendors) | {"claude"})
    if not seating_vendors:
        seating_vendors = ["claude"]

    if not live:
        live = ["claude"]
        if not (set(seating_vendors) - {"claude"}):
            degradations.append(
                {
                    "constraint": "live-vendors",
                    "reason": "no live vendors — defaulted to claude",
                }
            )

    tiers = dict(DEFAULT_TIER_BY_SEAT)
    if tier_by_seat:
        tiers.update(tier_by_seat)

    # bite-axis: unusable pin shape stays LOUD — a library caller gets a named degradation and a
    # rotated seat, never the traceback that a non-dict pin value used to raise (#1039).
    pins, pin_errors = normalize_pins(pins)
    for token in pin_errors:
        degradations.append({"constraint": "pin", "reason": token})

    def _tier_for(seat: str) -> str:
        if seat in tiers:
            return tiers[seat]
        if seat not in tier_degraded_seats:
            tier_degraded_seats.add(seat)
            degradations.append(
                {
                    "constraint": "tier",
                    "reason": f"seat {seat} had no tier — defaulted reviewer",
                }
            )
        return "reviewer"

    def _resolve_at_tier(seat: str, vendor: str, tier: str) -> dict | None:
        cell = matrix_config(tier, vendor)
        if cell is None:
            return None
        model, effort = cell
        # bite-axis: a seat is refused a cell that is not live — claude is always live, never probed
        if vendor != "claude" and (vendor, model, effort) not in live_cells_normalized:
            return None
        fam = family_for(tier, vendor)
        if fam is None:
            return None
        if not is_allowed(tier, vendor, model, effort):
            return None
        return {
            "vendor": vendor,
            "model": model,
            "effort": effort,
            "tier": tier,
            "family": fam,
            "source": "rotated",
        }

    def _resolve(seat: str, vendor: str) -> dict | None:
        return _resolve_at_tier(seat, vendor, _tier_for(seat))

    def _backfill(seat: str) -> dict:
        tier = _tier_for(seat)
        for try_tier in (tier, "reviewer"):
            for vendor in seating_vendors:
                cfg = _resolve_at_tier(seat, vendor, try_tier)
                if cfg is not None:
                    cfg = dict(cfg)
                    cfg["source"] = "backfill"
                    if try_tier != tier:
                        cfg["tier"] = try_tier
                    return cfg
        for try_tier in ("reviewer-deep", "reviewer"):
            cfg = _resolve_at_tier(seat, "claude", try_tier)
            if cfg is not None:
                cfg = dict(cfg)
                cfg["source"] = "backfill"
                cfg["tier"] = try_tier
                return cfg
        fallback_family = family_for("reviewer", "claude") or "anthropic"
        return {
            "vendor": seating_vendors[0] if seating_vendors else "claude",
            "model": "",
            "effort": None,
            "tier": tier,
            "family": fallback_family,
            "source": "backfill",
        }

    # Per-seat eligibility
    eligible_by_seat: dict[str, list[dict]] = {}
    same_family_seats: set[str] = set()
    pinned_maker_seats: set[str] = set()
    for seat in roster:
        base = [cfg for cfg in (_resolve(seat, v) for v in seating_vendors) if cfg is not None]

        if seat in STRONG_TIER_SEATS:
            eligible = list(base)
            if not eligible:
                degradations.append({
                    "constraint": "strong-tier",
                    "seat": seat,
                    "reason": f"seat {seat} has no strong-tier-eligible live vendor",
                })
        elif seat == GROUNDING_SEAT:
            excl: set[str] = set()
            if author_family:
                excl.add(author_family)
            if narrative_family:
                excl.add(narrative_family)
            if not author_family or not narrative_family:
                degradations.append({
                    "constraint": "grounding-provenance",
                    "reason": "author or narrative family unknown — grounding independence not guaranteed",
                })
            eligible = [cfg for cfg in base if cfg["family"] not in excl]
            if not eligible:
                degradations.append({
                    "constraint": "grounding-independence",
                    "reason": "no grounding vendor independent of author/narrative families",
                })
                # #670 finding 1: hand the FULL pool to the maker filter below rather than
                # pre-selecting "not the narrative family" — that old ordering picked the AUTHOR's
                # own family whenever author and narrative were the only live families. Maker
                # exclusion outranks narrative independence.
                eligible = list(base)
        else:
            eligible = list(base)

        # #670: the maker family is barred from EVERY seat in MAKER_EXCLUDED_SEATS. When an
        # alternative family is live the maker never seats (zero cost). When none is, the seat
        # fills with the maker family and the collapse is DISCLOSED — never silently clean, and
        # never an empty seat that falls through to the seat-unfilled backfill.
        if author_family and seat in MAKER_EXCLUDED_SEATS and eligible:
            non_maker = [cfg for cfg in eligible if cfg["family"] != author_family]
            if non_maker:
                eligible = non_maker
            else:
                same_family_seats.add(seat)

        eligible_by_seat[seat] = eligible

    # Pins (before enumeration)
    for pin_seat, pin in pins.items():
        if pin_seat not in roster:
            degradations.append(
                {
                    "constraint": "pin",
                    "reason": f"pin for unknown seat {pin_seat}",
                }
            )
            continue
        tier = _tier_for(pin_seat)
        pin_vendor = pin.get("vendor")
        if not pin_vendor:
            degradations.append(
                {
                    "constraint": "pin",
                    "reason": f"pin {pin_seat} not honorable — fell back to rotation",
                }
            )
            continue
        cell = matrix_config(tier, pin_vendor)
        if cell is None:
            degradations.append(
                {
                    "constraint": "pin",
                    "reason": f"pin {pin_seat} not honorable — fell back to rotation",
                }
            )
            continue
        default_model, default_effort = cell
        model = pin.get("model", default_model)
        effort = pin.get("effort", default_effort)
        pin_cell_live = (
            pin_vendor == "claude"
            or (pin_vendor, model, effort) in live_cells_normalized
        )
        if pin_cell_live and is_allowed(tier, pin_vendor, model, effort):
            fam = family_for(tier, pin_vendor)
            if pin_seat == GROUNDING_SEAT:
                excl = {f for f in (author_family, narrative_family) if f}
                if fam and fam in excl:
                    degradations.append(
                        {
                            "constraint": "pin-breaks-constraint",
                            "reason": f"pinned grounding seat family {fam} is not independent of author/narrative",
                        }
                    )
            if pin_seat in STRONG_TIER_SEATS and tier != "reviewer-deep":
                degradations.append(
                    {
                        "constraint": "pin-breaks-constraint",
                        "reason": f"pinned strong seat {pin_seat} is below reviewer-deep",
                    }
                )
            if pin_seat in MAKER_EXCLUDED_SEATS and author_family and fam == author_family:
                pinned_maker_seats.add(pin_seat)
                degradations.append({
                    "constraint": "pin-breaks-constraint",
                    "seat": pin_seat,
                    "reason": "pinned seat %s carries the maker family %s" % (pin_seat, author_family),
                })
            eligible_by_seat[pin_seat] = [
                {
                    "vendor": pin_vendor,
                    "model": model,
                    "effort": effort,
                    "tier": tier,
                    "family": fam,
                    "source": "pinned",
                }
            ]
        else:
            degradations.append(
                {
                    "constraint": "pin",
                    "reason": f"pin {pin_seat} not honorable — fell back to rotation",
                }
            )

    # Build options per seat
    options: dict[str, list[dict]] = {}
    fixed_seats: dict[str, dict] = {}
    for seat in roster:
        cfgs = eligible_by_seat.get(seat, [])
        if not cfgs:
            fixed = _backfill(seat)
            fixed_seats[seat] = fixed
            degradations.append(
                {
                    "constraint": "seat-unfilled",
                    "reason": f"seat {seat} had no eligible vendor — backfilled to {fixed['vendor']}",
                }
            )
            options[seat] = [fixed]
        elif len(cfgs) == 1 and cfgs[0].get("source") == "pinned":
            fixed_seats[seat] = cfgs[0]
            options[seat] = [cfgs[0]]
        else:
            seen_vendors: set[str] = set()
            sorted_cfgs: list[dict] = []
            for vendor in seating_vendors:
                for cfg in cfgs:
                    if cfg["vendor"] == vendor and vendor not in seen_vendors:
                        seen_vendors.add(vendor)
                        sorted_cfgs.append(cfg)
            options[seat] = sorted_cfgs if sorted_cfgs else cfgs

    def _assignment_key(assignment: dict[str, dict]) -> tuple:
        author_count = sum(
            1 for s in roster if assignment[s]["family"] == author_family
        )
        vendor_tuple = tuple(assignment[s]["vendor"] for s in roster)
        return (author_count, vendor_tuple)

    def _meets_soft(assignment: dict[str, dict], check_author_minority: bool, check_critical: bool) -> bool:
        if check_critical:
            critical_families = {
                assignment[s]["family"]
                for s in roster
                if s in CRITICAL_SEATS
            }
            if len(critical_families) < 2:
                return False
        if check_author_minority and author_family:
            # Per-seat maker prohibition (every roster seat) plus numeric minority cap. For a full
            # PANEL_ROSTER the per-seat bar subsumes the cap; seats discounted are unavoidable
            # (`same_family_seats`) or owner-pinned (`pinned_maker_seats`).
            author_seats = [
                s for s in roster
                if s not in same_family_seats and s not in pinned_maker_seats
                and assignment[s]["family"] == author_family
            ]
            if len(author_seats) >= math.ceil(len(roster) / 2):
                return False
            for s in author_seats:
                if s in MAKER_EXCLUDED_SEATS:
                    return False
        return True

    def _enumerate_assignments() -> list[dict[str, dict]]:
        product_seats = [s for s in roster if s not in fixed_seats]
        if not product_seats:
            return [{s: fixed_seats.get(s, options[s][0]) for s in roster}]
        combos = list(itertools.product(*[options[s] for s in product_seats]))
        result: list[dict[str, dict]] = []
        for combo in combos:
            assignment: dict[str, dict] = {}
            for i, seat in enumerate(product_seats):
                assignment[seat] = combo[i]
            for seat in roster:
                if seat in fixed_seats and seat not in product_seats:
                    assignment[seat] = fixed_seats[seat]
            result.append(assignment)
        return result

    all_assignments = _enumerate_assignments()
    if not all_assignments:
        seats_out = {s: _backfill(s) for s in roster}
    else:
        survivors = [
            a for a in all_assignments
            if _meets_soft(a, check_author_minority=True, check_critical=True)
        ]
        if survivors:
            survivors.sort(key=_assignment_key)
            chosen = survivors[seed % len(survivors)]
            seats_out = chosen
        else:
            survivors = [
                a for a in all_assignments
                if _meets_soft(a, check_author_minority=False, check_critical=True)
            ]
            if survivors:
                degradations.append(
                    {
                        "constraint": "author-minority",
                        "reason": "relaxed author-minority cap — no assignment kept the author family in the minority while retaining critical-diversity",
                    }
                )
                survivors.sort(key=_assignment_key)
                seats_out = survivors[seed % len(survivors)]
            else:
                all_assignments.sort(key=_assignment_key)
                chosen = all_assignments[seed % len(all_assignments)]
                if not _meets_soft(chosen, check_author_minority=True, check_critical=False):
                    degradations.append({
                        "constraint": "author-minority",
                        "reason": "relaxed author-minority cap — no assignment satisfied it",
                    })
                degradations.append({
                    "constraint": "critical-diversity",
                    "reason": "relaxed critical-diversity — no assignment spanned ≥2 families",
                })
                seats_out = chosen

    result = {
        "seats": seats_out,
        "degradations": degradations,
        "seed": seed,
        "liveVendors": list(live),
        "liveCells": sorted([list(c) for c in live_cells_normalized]),
        "authorFamily": author_family,
        "narrativeFamily": narrative_family,
        "livenessPinScoped": bool(liveness_pin_scoped),
    }
    if resolved_cells_source is not None:
        result["liveCellsSource"] = resolved_cells_source
    # ONE predicate decides "was the maker unavoidable?" — recording it here from the finished map
    # keeps build() and verify() from disagreeing on the same seat (#670 review, two seats).
    seen = {(d.get("constraint"), d.get("seat")) for d in degradations if isinstance(d, dict)}
    for rec in same_family_degradations(result, author_family):
        key = (rec["constraint"], rec["seat"])
        if key not in seen:
            seen.add(key)
            degradations.append(rec)
    return result


# The only two constraints build() deliberately RELAXES and discloses as a degradation of the same
# name when no assignment can satisfy them. Every other verify() constraint — maker-family,
# missing-seat, malformed, and any constraint added later — is unexcusable by construction: the
# fail-closed default for an unrecognised constraint is BREACH, never excused (#680).
EXCUSABLE_RELAXATIONS = frozenset({"strong-tier", "critical-diversity"})


def classify_violations(seat_map: dict) -> dict:
    """{'unexcused': [...], 'excusedByPin': [...], 'excusedByLiveness': [...]} (#680 R-A/R-B)."""
    empty = {"unexcused": [], "excusedByPin": [], "excusedByLiveness": []}
    if not isinstance(seat_map, dict):
        return empty
    violations = seat_map.get("violations")
    if not isinstance(violations, list) or not violations:
        return empty
    raw_seats = seat_map.get("seats")
    seats = raw_seats if isinstance(raw_seats, dict) else {}
    author_family = seat_map.get("authorFamily")
    if not isinstance(author_family, str) or not author_family:
        author_family = None

    unexcused: list[dict] = []
    excused_by_pin: list[dict] = []
    excused_by_liveness: list[dict] = []

    for v in violations:
        if not isinstance(v, dict):
            unexcused.append({"constraint": "malformed-violation-record"})
            continue
        constraint = v.get("constraint")
        seat = v.get("seat") if isinstance(v.get("seat"), str) else None
        if not isinstance(constraint, str) or not constraint:
            unexcused.append({"constraint": "malformed-violation-record"})
            continue
        if constraint not in EXCUSABLE_RELAXATIONS:
            unexcused.append(v)
            continue

        if constraint == "strong-tier":
            collapsed = [seat] if isinstance(seat, str) and seat else []
        else:
            collapsed = [s for s in CRITICAL_SEATS if s in seats]

        if not collapsed:
            unexcused.append(dict(v))
            continue

        if constraint == "strong-tier":
            cs = collapsed[0]
            cfg0 = seats.get(cs)
            if isinstance(cfg0, dict) and cfg0.get("source") == "pinned":
                rec = dict(v)
                rec["excusedSeats"] = [cs]
                excused_by_pin.append(rec)
                continue
            if not isinstance(cfg0, dict):
                stamped = dict(v)
                stamped["evidence"] = "unproven-liveness"
                unexcused.append(stamped)
                continue
            fams = _resolvable_families_for_seat(
                seat_map, cs, cfg0, tier=STRONG_TIER_REQUIRED,
            )
            if fams is None:
                stamped = dict(v)
                stamped["evidence"] = "unproven-liveness"
                unexcused.append(stamped)
                continue
            if fams == set():
                excused_by_liveness.append(dict(v))
                continue
            stamped = dict(v)
            stamped["evidence"] = "alternative-live"
            unexcused.append(stamped)
            continue

        if not isinstance(author_family, str) or not author_family:
            stamped = dict(v)
            stamped["evidence"] = "unproven-liveness"
            unexcused.append(stamped)
            continue

        achievable: set[str] | None = set()
        for cs in collapsed:
            cfg = seats.get(cs)
            if not isinstance(cfg, dict):
                achievable = None
                break
            if cfg.get("source") == "pinned":
                fam = cfg.get("family")
                if isinstance(fam, str) and fam:
                    achievable.add(fam)
            else:
                fams = _resolvable_families_for_seat(seat_map, cs, cfg)
                if fams is None:
                    achievable = None
                    break
                achievable |= fams - {author_family}

        if achievable is None:
            stamped = dict(v)
            stamped["evidence"] = "unproven-liveness"
            unexcused.append(stamped)
            continue
        if len(achievable) >= MIN_CRITICAL_FAMILIES:
            stamped = dict(v)
            stamped["evidence"] = "alternative-live"
            unexcused.append(stamped)
            continue

        pinned_seats = [
            cs for cs in collapsed
            if isinstance(seats.get(cs), dict) and seats[cs].get("source") == "pinned"
        ]
        if pinned_seats:
            rec = dict(v)
            rec["excusedSeats"] = sorted(pinned_seats)
            excused_by_pin.append(rec)
        else:
            excused_by_liveness.append(dict(v))

    unexcused.sort(
        key=lambda item: (str(item.get("constraint", "")), str(item.get("seat") or "")),
    )
    return {
        "unexcused": unexcused,
        "excusedByPin": excused_by_pin,
        "excusedByLiveness": excused_by_liveness,
    }


def unexcused_violations(seat_map: dict) -> list[dict]:
    """Back-compat thin wrapper — the violations that STAND."""
    return classify_violations(seat_map)["unexcused"]


def verify(seat_map: dict, author_family: str | None) -> list[dict]:
    seats = seat_map.get("seats")
    if not isinstance(seats, dict):
        return [{"constraint": "malformed"}]

    violations: list[dict] = []

    for seat in PANEL_ROSTER:
        if seat not in seats:
            violations.append({"seat": seat, "constraint": "missing-seat"})

    if author_family:
        for seat in sorted(MAKER_EXCLUDED_SEATS):
            if seat not in seats:
                continue
            cfg = seats[seat]
            if not isinstance(cfg, dict) or cfg.get("family") != author_family:
                continue
            if _alternative_family_live(seat_map, seat, cfg, author_family):
                # an alternative family was reachable and the maker seated anyway — a VIOLATION
                violations.append({"seat": seat, "constraint": "maker-family"})
            # else: unavoidable — carried as the `same-family` DEGRADATION, not a violation (#670)

    for seat in STRONG_TIER_SEATS:
        if seat in seats and seats[seat].get("tier") != STRONG_TIER_REQUIRED:
            violations.append({"seat": seat, "constraint": "strong-tier"})

    critical_families = _critical_families(seats)
    if len(critical_families) < MIN_CRITICAL_FAMILIES:
        violations.append({"constraint": "critical-diversity"})

    violations.sort(key=lambda v: (v.get("constraint", ""), v.get("seat", "")))
    return violations


def to_receipt(seat_map: dict, author_family: str | None = None) -> dict:
    af = author_family if author_family is not None else seat_map.get("authorFamily")
    raw = seat_map.get("degradations")
    incoming = list(raw) if isinstance(raw, list) else []
    # #670 (advisor ruling on PR #679's parked seam): to_receipt is the SOLE authority for the
    # same-family determination. `build()` records its copy before main() merges the preflight
    # notes, so a build-stage record can be STALE — it may assert "no alternative family is live"
    # for a seat whose liveness was never probed. Drop every incoming same-family record and derive
    # exactly once here, where the map carries all three evidence sources (build()'s own
    # degradations, the preflight notes, and livenessPinScoped). build()'s copy is advisory only.
    # Invariant this establishes: a receipt NEVER carries both a same-family degradation and a
    # maker-family violation for the same seat.
    degradations = [
        d for d in incoming
        if not (isinstance(d, dict) and d.get("constraint") == "same-family")
    ]
    seen = {
        (d.get("constraint"), d.get("seat"))
        for d in degradations
        if isinstance(d, dict)
    }
    for rec in same_family_degradations(seat_map, af):
        key = (rec["constraint"], rec["seat"])
        if key not in seen:
            seen.add(key)
            degradations.append(rec)
    receipt_live_cells, receipt_cells_source = _live_cells_fields_for_receipt(seat_map)
    raw_skew = seat_map.get("pluginVersionSkew")
    if isinstance(raw_skew, dict) and isinstance(raw_skew.get("status"), str):
        plugin_version_skew = {
            "status": raw_skew["status"],
            "detail": raw_skew.get("detail", ""),
            "inspectedRoot": raw_skew.get("inspectedRoot", ""),
        }
    else:
        # build()-only maps never ran compose skew detection — not-checked, never checked-clean.
        plugin_version_skew = {
            "status": version_skew.STATUS_NOT_CHECKED,
            "detail": version_skew.DETAIL_NOT_COMPOSED,
            "inspectedRoot": "",
        }
    out = {
        "seats": seat_map.get("seats", {}),
        "degradations": degradations,
        "seed": seat_map.get("seed"),
        "liveVendors": seat_map.get("liveVendors", []),
        "liveCells": receipt_live_cells,
        "liveCellsSource": receipt_cells_source,
        "narrativeFamily": seat_map.get("narrativeFamily"),
        "authorFamily": af,
        "livenessPinScoped": bool(seat_map.get("livenessPinScoped")),
        "violations": verify(seat_map, af),
        "pluginVersionSkew": plugin_version_skew,
    }
    return out


def build_parser():
    import argparse

    import cli_contract as cc

    ap = argparse.ArgumentParser(prog="seat_map")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compose", help="compute the panel seat map for a run")
    cc.add_argument(c, "--author-family", contract="free-text", default=None)
    cc.add_argument(c, "--narrative-family", contract="free-text", default=None)
    cc.add_argument(c, "--pr-number", contract="free-text", default=None)
    cc.add_argument(c, "--head-sha", contract="free-text", default=None)
    cc.add_argument(c, "--repo-root", contract="free-text", default=".")
    cc.add_argument(
        c,
        "--live-vendors",
        contract="free-text",
        default=None,
        help="comma list; overrides preflight (test/precomputed seam)",
    )
    cc.add_argument(
        c,
        "--configured-engines",
        contract="free-text",
        default="",
        help="comma list of non-claude engines; used to run preflight when --live-vendors omitted",
    )
    cc.add_argument(
        c,
        "--pins",
        contract="free-text",
        default=None,
        help="JSON dict of seat pins passed to build()",
    )
    return ap


def main(argv):
    import json
    import sys

    args = build_parser().parse_args(argv[1:])
    if args.cmd == "compose":
        import os
        import time

        notes: list[dict[str, str]] = []

        pins = None
        if args.pins is not None:
            try:
                pins = json.loads(args.pins)
            except json.JSONDecodeError as e:
                print(str(e), file=sys.stderr)
                return 1
            # bite-axis: REFUSAL by name — an unusable pin shape exits non-zero naming the seat,
            # never a traceback and never a silently-dropped pin (#1039).
            pins, pin_errors = normalize_pins(pins)
            if pin_errors:
                for token in pin_errors:
                    print(token, file=sys.stderr)
                return 1

        live_cells = None
        live_cells_source = None
        if args.live_vendors is not None:
            live = [v for v in args.live_vendors.split(",") if v]
            liveness_pin_scoped = False
            live_cells_source = "synthesized"
        else:
            now = time.time()
            cache_path = liveness_cache.receipt_path(".")
            import preflight_probe

            configured = [e for e in args.configured_engines.split(",") if e]
            needed_override = reachable_configs(configured, pins) if pins else None
            liveness_pin_scoped = needed_override is not None
            live, live_cells, _liveness, notes, live_cells_source = (
                preflight_probe.live_vendors_for_composition(
                    configured,
                    needed_override=needed_override,
                    cache_path=cache_path,
                    now=now,
                )
            )
        seed = seed_from(args.pr_number, args.head_sha)
        sm = build(
            PANEL_ROSTER,
            live,
            args.author_family,
            args.narrative_family,
            seed,
            pins=pins,
            liveness_pin_scoped=liveness_pin_scoped,
            live_cells=live_cells,
            live_cells_source=live_cells_source,
        )
        extra_degradations: list[dict[str, str]] = []
        plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # bite-axis: skew record reaches the receipt before to_receipt derives it — a record
        # appended after can never be seen by the evidence check (#677; same ordering bound as
        # the preflight notes merge below).
        skew_record = version_skew.detect(args.repo_root, plugin_root)
        sm["pluginVersionSkew"] = {
            "status": skew_record["status"],
            "detail": skew_record["detail"],
            "inspectedRoot": skew_record["inspectedRoot"],
        }
        # bite-axis: only checked-degraded records reach degradations — checked-clean and
        # not-checked stay off the list so a clean or skipped check never reads as degraded
        # (#677; if-and-only-if with the consumer rule in CONVENTIONS §6).
        if version_skew.is_degrading(skew_record.get("status")):
            extra_degradations.append(skew_record)
        if notes:
            extra_degradations.extend(notes)
        if extra_degradations:
            # merge BEFORE to_receipt: the evidence check reads sm["degradations"], so a note that
            # lands after the receipt is derived can never be seen by it (#670 review, two seats).
            sm["degradations"] = list(sm.get("degradations", [])) + extra_degradations
        receipt = to_receipt(sm)
        if "liveCellsSource" not in receipt:
            receipt["liveCellsSource"] = (
                live_cells_source if live_cells_source is not None else "synthesized"
            )
        json.dump(receipt, sys.stdout)
        sys.stdout.write("\n")
        return 0
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv))
