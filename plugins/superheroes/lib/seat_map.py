"""Deterministic panel seat-map composition engine (issue #510).

Pure, stdlib-only. Derives all model/vendor data from model_registry — no parallel literals.

Needed-set shape: {vendor: [[model, effort], ...]} — positional [model, effort]; produced by
preflight_probe.needed_configs_for and seat_map.reachable_configs, consumed by liveness_cache.
"""
from __future__ import annotations

import hashlib
import itertools
import math

import host_model as host_model_lib
import liveness_cache
import model_registry
from model_registry import family_for, is_allowed, matrix_config, vendors

LIVE_CELLS_SOURCES = liveness_cache.LIVE_CELLS_SOURCES

LENS_SEATS = (
    "architecture-reviewer",
    "code-reviewer",
    "security-reviewer",
    "test-role",
    "premortem-reviewer",
)
# Seat keys an owner's saved pins may still name, mapped to the seat that now holds the job. The
# one home: every pin normalizer reads it, so a pin under the old key is read as the new seat's pin
# (an explicit pin under the new key wins). Nothing on disk is rewritten.
LEGACY_SEAT_ALIASES = {"test-reviewer": "test-role"}
# Every seat a roster may name, the architecture reviewer included.
KNOWN_SEATS = LENS_SEATS
# The risky full-lane roster: the default for any caller that names no roster, and the roster a
# change with a touched or unclear risk gets. The architecture reviewer is not on it.
PANEL_ROSTER = tuple(s for s in KNOWN_SEATS if s != "architecture-reviewer")
# Seats on every full-lane panel; the specialists are added when the lane call has a floor.
BASE_ROSTER = ("code-reviewer", "test-role")
STRONG_TIER_SEATS = frozenset({"security-reviewer", "architecture-reviewer"})
STRONG_TIER_REQUIRED = "reviewer-deep"
CRITICAL_SEATS = frozenset({"security-reviewer", "premortem-reviewer", "code-reviewer"})
MIN_CRITICAL_FAMILIES = 2
# The maker's model family is barred from EVERY panel seat (#670, owner-ratified 2026-07-26) — the
# five lens seats, not merely the strong-tier/critical subset. The test
# role's seat was the hole: it is neither strong-tier nor critical, so post-#651 (cursor's first-party models are
# ONE `xai` family) a composer-made diff could have cursor-grok reviewing its own tests with no
# violation recorded. STRONG_TIER_SEATS / CRITICAL_SEATS keep their OTHER jobs (the reviewer-deep bar
# and the critical-diversity bar) unchanged.
MAKER_EXCLUDED_SEATS = frozenset(KNOWN_SEATS)
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
    "compose-failed",         # compose blew up and every seat fell open to the host model
    liveness_cache.LIVENESS_READ_ERROR_CONSTRAINT,    # liveness read crashed — an unknown subset of cells were examined
})
# `source` of a seat no reviewer outside the makers' families could fill — recorded, never run.
UNFILLED_SOURCE = "unfilled"
DEFAULT_TIER_BY_SEAT = {s: "reviewer-deep" for s in LENS_SEATS}
# The registry roles whose per-vendor matrix cells the non-panel phases dispatch (the verifier, the
# seams-check / scoped reviewers and the synthesis grouper): compose probes and records these beside
# the panel's own cells.
NONPANEL_CELL_ROLES = ("verifier", "reviewer-deep", "synthesis")


def roster_for(lane_basis) -> tuple[str, ...]:
    """The full-lane panel the lane call asks for. The generalist and the test seat are always on
    it; the security and premortem seats join whenever the floor is not None.
    Fail-closed: a basis that is not a dict, or has no `floor` key, gets the risky roster."""
    if isinstance(lane_basis, dict) and "floor" in lane_basis and lane_basis["floor"] is None:
        return tuple(s for s in PANEL_ROSTER if s in BASE_ROSTER)
    return PANEL_ROSTER


def effective_roster(seat_map) -> tuple[str, ...] | None:
    """The map's own `roster` when it is a non-empty list of strings, else None."""
    raw = seat_map.get("roster") if isinstance(seat_map, dict) else None
    if isinstance(raw, list) and raw and all(isinstance(s, str) for s in raw):
        return tuple(raw)
    return None


def required_critical_families(roster) -> int:
    """How many distinct families the critical seats on `roster` must span: the minimum, capped at
    the number of critical seats the roster seats."""
    return min(MIN_CRITICAL_FAMILIES, len(CRITICAL_SEATS & set(roster)))


# Tiers _backfill's primary rotation tries after the seat's configured tier (#1269).
_BACKFILL_DOWNGRADE_TO = "reviewer"
# Tiers _backfill's claude-only fallback rotation tries (#1269).
_BACKFILL_CLAUDE_ROTATION = (STRONG_TIER_REQUIRED, _BACKFILL_DOWNGRADE_TO)

# `reviewer` stays a pin tier: the backfill downgrade still seats panel seats at it, and a saved map's pins may key it.
_PANEL_PIN_TIERS = frozenset(model_registry.codex_pin_roles()) & (
    frozenset(DEFAULT_TIER_BY_SEAT.values()) | {_BACKFILL_DOWNGRADE_TO}
)


def panel_pin_tiers() -> frozenset[str]:
    """Return panel tier names that participate in codex role-pin seating."""
    return _PANEL_PIN_TIERS


def _tiers_in_play(tiers) -> set[str]:
    # compose can backfill any seat at the downgrade tier, so its cells are in play whatever the roster's own tiers
    return set(tiers) | {_BACKFILL_DOWNGRADE_TO}


def _read_codex_role_pins(seat_map: dict) -> tuple[dict[str, str] | None, bool]:
    """Read ``codexRolePins`` from a seat map — absent, validated mapping, or unusable."""
    if "codexRolePins" not in seat_map:
        return None, True
    raw = seat_map.get("codexRolePins")
    if raw is None:
        return None, False
    if not isinstance(raw, dict):
        return None, False
    pins: dict[str, str] = {}
    for role, pin in raw.items():
        if role not in _PANEL_PIN_TIERS:
            return None, False
        if not isinstance(pin, str) or not pin:
            return None, False
        pins[role] = pin
    return pins, True


def _cell(
    tier: str,
    vendor: str,
    role_pins: dict[str, str] | None = None,
) -> tuple[str | None, str | None, dict[str, object] | None]:
    """The one resolver from (tier, vendor) to (model, effort) for seating and needed-set.

    For codex at a panel tier with a role pin, returns the pinned cell when dispatch resolves and
    the pin is on that tier's allowlist and only a pin ``codex_pin_verdict`` accepts; otherwise the matrix cell. The third tuple element
    describes an attempted role pin: ``{"pin": <model>, "honored": bool}`` or ``None``."""
    role_pins = role_pins or {}
    if vendor == "codex" and tier in _PANEL_PIN_TIERS and tier in role_pins:
        pin = role_pins[tier]
        ok, _reason = model_registry.codex_pin_verdict(tier, pin)
        resolved = model_registry.resolve_dispatch(tier, "codex", pin, None)
        if ok and resolved.get("ok"):
            model = resolved["model_id"]
            effort = resolved["effort"]
            if is_allowed(tier, vendor, model, effort):
                return model, effort, {"pin": pin, "honored": True}
        cell = matrix_config(tier, vendor)
        if cell is None:
            return None, None, {"pin": pin, "honored": False}
        return cell[0], cell[1], {"pin": pin, "honored": False}
    cell = matrix_config(tier, vendor)
    if cell is None:
        return None, None, None
    return cell[0], cell[1], None


def _backfill_rotation_tiers(primary_tier: str) -> tuple[str, ...]:
    """Tiers ``_backfill`` tries in order: configured tier, then reviewer."""
    return (primary_tier, _BACKFILL_DOWNGRADE_TO)


def _backfill_emittable_tiers(primary_tier: str) -> frozenset[str]:
    """Every tier ``_backfill`` may record — primary rotation, claude fallback, terminal."""
    return frozenset(_backfill_rotation_tiers(primary_tier)) | frozenset(_BACKFILL_CLAUDE_ROTATION)


def accepted_tiers_for_seat(seat: str, tier_by_seat: dict[str, str] | None = None) -> frozenset[str]:
    """Every tier seat_map.build may record for ``seat`` — default, override, and backfill."""
    tiers_map = dict(DEFAULT_TIER_BY_SEAT)
    if tier_by_seat:
        tiers_map.update(tier_by_seat)
    primary = tiers_map.get(seat, "reviewer")
    return _backfill_emittable_tiers(primary)

ALT_LIVE = "alternative-live"
ALT_NONE = "no-alternative-live"
ALT_UNUSABLE = "evidence-unusable"

VIOLATION_BASIS_COMPLETE = "complete"
VIOLATION_BASIS_NO_SEATS = "no-seats"
VIOLATION_BASIS_NO_AUTHOR_FAMILY = "no-author-family"
VIOLATION_BASIS_SELF_ASSERTED_AUTHOR_FAMILY = "self-asserted-author-family"

EVIDENCE_UNPROVEN_BASIS = "unproven-basis"


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
        # axis: a malformed effort never reaches a set as an unhashable triple — see bite-proof record c7l3_wo4_tooling
        if effort is not None and not isinstance(effort, str):
            return None
        if isinstance(vendor, str) and vendor and isinstance(model, str) and model:
            return (vendor, model, effort)
    return None


def _synthesize_live_cells(
    live_vendors: list[str],
    roster: tuple[str, ...] | list[str],
    tier_by_seat: dict[str, str] | None,
    codex_role_pins: dict[str, str] | None = None,
) -> set[tuple[str, str, str | None]]:
    tiers_map = dict(DEFAULT_TIER_BY_SEAT)
    if tier_by_seat:
        tiers_map.update(tier_by_seat)
    tiers_in_play = _tiers_in_play(tiers_map.get(s, "reviewer") for s in roster)
    cells: set[tuple[str, str, str | None]] = set()
    for vendor in live_vendors:
        if not isinstance(vendor, str) or not vendor:
            continue
        for tier in tiers_in_play:
            model, effort, _pin = _cell(tier, vendor, codex_role_pins)
            if model is None:
                continue
            if is_allowed(tier, vendor, model, effort):
                cells.add((vendor, model, effort))
    return cells


def _live_cells_fields_for_receipt(seat_map: dict) -> tuple[list, object]:
    raw_cells = seat_map.get("liveCells")
    raw_source = seat_map.get("liveCellsSource")
    if isinstance(raw_cells, list) and raw_source in LIVE_CELLS_SOURCES:
        return list(raw_cells), raw_source
    if raw_source is None:
        receipt_source = liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED
    elif raw_source not in LIVE_CELLS_SOURCES:
        receipt_source = raw_source
    else:
        receipt_source = liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED
    live = seat_map.get("liveVendors")
    if isinstance(live, list) and live:
        roster = tuple(seat_map.get("seats", {}).keys()) or PANEL_ROSTER
        role_pins, pins_usable = _read_codex_role_pins(seat_map)
        if "codexRolePins" in seat_map and not pins_usable:
            return [], liveness_cache.LIVE_CELLS_SOURCE_UNPROBED
        pin_arg = role_pins if pins_usable and role_pins else None
        synthesized = _synthesize_live_cells(live, roster, None, codex_role_pins=pin_arg)
        return sorted([list(c) for c in synthesized]), receipt_source
    return [], receipt_source


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
    role_pins, pins_usable = _read_codex_role_pins(seat_map)
    if not pins_usable:
        return None
    pin_arg = role_pins if role_pins else None
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
            model, effort, pin_info = _cell(tier, vendor, pin_arg)
            if model is None:
                continue
            if (vendor, model, effort) not in live_cell_set:
                if pin_info and pin_info.get("honored") and vendor != "claude":
                    matrix_model, matrix_effort, _mp = _cell(tier, vendor, None)
                    if matrix_model is None:
                        continue
                    model, effort = matrix_model, matrix_effort
                    if (vendor, model, effort) not in live_cell_set:
                        continue
                else:
                    continue
            fam = family_for(tier, vendor)
            if fam is None or not is_allowed(tier, vendor, model, effort):
                continue
            families.add(fam)
        # claude is always live and is never probed — count its registry cell at this tier
        claude_model, claude_effort, _pin = _cell(tier, "claude", None)
        if claude_model is not None:
            fam = family_for(tier, "claude")
            if fam is not None and is_allowed(tier, "claude", claude_model, claude_effort):
                families.add(fam)
        return families
    if cells_source == liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED:
        # synthesized cells derive from the pessimistic liveVendors rollup
        live = seat_map.get("liveVendors")
        if not isinstance(live, list) or not live:
            return None
        for vendor in live:
            if not isinstance(vendor, str) or not vendor or vendor not in known_vendors:
                return None
        for vendor in live:
            model, effort, _pin = _cell(tier, vendor, pin_arg)
            if model is None:
                continue
            fam = family_for(tier, vendor)
            if fam is None or not is_allowed(tier, vendor, model, effort):
                continue
            families.add(fam)
        return families
    # absent, unrecognized, non-string, or wrong-case liveCellsSource — not evidence
    return None


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


def is_unfilled(cfg) -> bool:
    """True for the record of a seat no non-maker reviewer could fill: a known not-run seat, carrying
    no vendor, model or family. A record that names a vendor is a seated reviewer whatever its
    `source` says, so it is checked as one."""
    return (
        isinstance(cfg, dict)
        and cfg.get("source") == UNFILLED_SOURCE
        and cfg.get("vendor") is None
    )


def _unfilled_cfg(tier: str) -> dict:
    return {
        "vendor": None,
        "model": None,
        "effort": None,
        "tier": tier,
        "family": None,
        "source": UNFILLED_SOURCE,
    }


def _seat_family(seat: str, cfg) -> str | None:
    """Registry-canonical family for one seat record; ``None`` when it cannot be derived."""
    if not isinstance(cfg, dict):
        return None
    vendor = cfg.get("vendor")
    if not isinstance(vendor, str) or not vendor:
        return None
    tier = cfg.get("tier")
    if not isinstance(tier, str) or not tier:
        tier = DEFAULT_TIER_BY_SEAT.get(seat, "reviewer")
    fam = family_for(tier, vendor)
    if fam is not None:
        return fam
    return family_for("reviewer", vendor)


def _critical_families(seats: dict) -> set[str]:
    """The distinct families across the seated CRITICAL_SEATS — verify()'s counting rule extracted
    for clarity. classify_violations asks a different question (families reachable, not seated); the
    shared invariant between the two paths is required_critical_families (#680 round 3)."""
    return {
        fam
        for s in CRITICAL_SEATS
        if s in seats
        for fam in [_seat_family(s, seats[s])]
        if fam is not None
    }


def _scanned_seats(seat_map: dict) -> tuple[str, ...]:
    """The seats a scanning check walks: the map's own roster, else every known seat the map carries."""
    roster = effective_roster(seat_map)
    if roster is not None:
        return roster
    seats = seat_map.get("seats") if isinstance(seat_map, dict) else None
    return tuple(s for s in KNOWN_SEATS if isinstance(seats, dict) and s in seats)


def same_family_degradations(seat_map: dict, author_family: str | None) -> list[dict]:
    """Derive the `same-family` records a seat map implies. `build()` records these directly; this
    derives the same records for a hand-built or replayed map so a receipt is never silent about a
    maker-family seat. Idempotent — `to_receipt` dedupes by (constraint, seat)."""
    seats = seat_map.get("seats")
    if not isinstance(seats, dict) or not author_family:
        return []
    out: list[dict] = []
    for seat in _scanned_seats(seat_map):
        cfg = seats.get(seat)
        if not isinstance(cfg, dict):
            continue
        seat_fam = _seat_family(seat, cfg)
        if seat_fam != author_family:
            continue  # unresolvable vendor: verify() owns unresolvable-seat-vendor
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
        canonical = LEGACY_SEAT_ALIASES.get(seat, seat)
        if canonical != seat and canonical in pins:
            continue  # explicit canonical key wins over the legacy alias
        seat = canonical
        if isinstance(pin, dict):
            normalized[seat] = dict(pin)
        elif isinstance(pin, str):
            normalized[seat] = {"vendor": pin}
        else:
            errors.append("pins-invalid:%s" % seat)
    return normalized, errors


def reachable_configs(
    configured_vendors,
    pins,
    roster=None,
    tier_by_seat=None,
    codex_role_pins: dict[str, str] | None = None,
):
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
        model, effort, _pin = _cell(tier, vendor, None)
        if model is not None:
            reachable[vendor].add((model, effort))

    def _rotate_all(tier: str) -> None:
        for cv in configured_vendors:
            _add_cell(cv, tier)

    any_seat_rotated = False
    honorably_pinned: set[str] = set()

    for seat in roster:
        tier = _tier_for(seat)
        pin = pins.get(seat)
        if isinstance(pin, dict) and isinstance(pin.get("vendor"), str) and pin["vendor"].strip():
            v = pin["vendor"].strip()
            if v == "claude":
                continue
            if v in configured_vendors:
                default_model, default_effort, _pin = _cell(tier, v, codex_role_pins)
                model = pin.get("model", default_model)
                effort = pin["effort"] if "effort" in pin else (model_registry.resolve_dispatch(tier, v, model, None).get("effort") if "model" in pin else default_effort)
                pin_model_bad = "model" in pin and not isinstance(pin.get("model"), (str, type(None)))
                pin_effort_bad = "effort" in pin and not isinstance(pin.get("effort"), (str, type(None)))
                well_typed = not pin_model_bad and not pin_effort_bad
                honorable = (
                    default_model is not None
                    and well_typed
                    and is_allowed(tier, v, model, effort)
                )
                if honorable:
                    reachable[v].add((model, effort))
                    honorably_pinned.add(v)
                else:
                    any_seat_rotated = True
                    _rotate_all(tier)
            else:
                any_seat_rotated = True
                _rotate_all(tier)
        else:
            any_seat_rotated = True
            _rotate_all(tier)

    seat_tiers = {_tier_for(seat) for seat in roster}
    in_play_tiers = _tiers_in_play(seat_tiers)
    # The backfill tier's cells follow the roster's pins, as the cells of a seat at that tier would: any rotating
    # seat rotates it across every vendor; otherwise only the vendors the roster was honorably pinned to get its cell.
    for tier in in_play_tiers - seat_tiers:
        if any_seat_rotated:
            _rotate_all(tier)
        else:
            for v in honorably_pinned:
                _add_cell(v, tier)

    if codex_role_pins and "codex" in configured_vendors:
        for tier in _PANEL_PIN_TIERS:
            if tier in codex_role_pins and tier in in_play_tiers:
                _add_cell("codex", tier)
                model, effort, pin_info = _cell(tier, "codex", codex_role_pins)
                if pin_info and pin_info.get("honored"):
                    reachable["codex"].add((model, effort))

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
    seed: int,
    tier_by_seat: dict[str, str] | None = None,
    pins: dict[str, dict] | None = None,
    liveness_pin_scoped: bool = False,
    live_cells: list | None = None,
    live_cells_source: str | None = None,
    codex_role_pins: dict[str, str] | None = None,
    extra_maker_families: frozenset[str] | None = None,
) -> dict:
    degradations: list[dict[str, str]] = []
    tier_degraded_seats: set[str] = set()

    roster = tuple(roster) if roster else PANEL_ROSTER

    live = [v for v in (live_vendors or []) if isinstance(v, str) and v]

    # The makers' families are barred from every maker-excluded seat: the author's plus every extra
    # maker's. A seat none of the live reviewers can fill is recorded unfilled, never seated with a
    # maker family.
    makers: set[str] = {f for f in ({author_family} | set(extra_maker_families or ())) if f}

    role_pins = codex_role_pins or {}

    if live_cells is None:
        live_cells_normalized = _synthesize_live_cells(
            live, roster, tier_by_seat, codex_role_pins=role_pins or None,
        )
        resolved_cells_source = (
            liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED
            if live_cells_source is None
            else live_cells_source
        )
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
        model, effort, pin_info = _cell(tier, vendor, role_pins or None)
        if model is None:
            return None
        source = "rotated"
        if pin_info and pin_info.get("honored"):
            if vendor != "claude" and (vendor, model, effort) not in live_cells_normalized:
                matrix_model, matrix_effort, _mp = _cell(tier, vendor, None)
                if matrix_model is None:
                    return None
                model, effort = matrix_model, matrix_effort
            else:
                source = "role-pinned"
        elif pin_info and not pin_info.get("honored"):
            matrix_model, matrix_effort, _mp = _cell(tier, vendor, None)
            if matrix_model is None:
                return None
            model, effort = matrix_model, matrix_effort
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
            "source": source,
        }

    def _resolve(seat: str, vendor: str) -> dict | None:
        return _resolve_at_tier(seat, vendor, _tier_for(seat))

    def _backfill(seat: str) -> dict:
        tier = _tier_for(seat)
        for try_tier in _backfill_rotation_tiers(tier):
            for vendor in seating_vendors:
                cfg = _resolve_at_tier(seat, vendor, try_tier)
                if cfg is not None and cfg["family"] not in makers:
                    cfg = dict(cfg)
                    cfg["source"] = "backfill"
                    if try_tier != tier:
                        cfg["tier"] = try_tier
                    return cfg
        for try_tier in _BACKFILL_CLAUDE_ROTATION:
            cfg = _resolve_at_tier(seat, "claude", try_tier)
            if cfg is not None and cfg["family"] not in makers:
                cfg = dict(cfg)
                cfg["source"] = "backfill"
                cfg["tier"] = try_tier
                return cfg
        return _unfilled_cfg(tier)

    def _note_unfilled(seat: str) -> None:
        if any(
            d.get("constraint") == "seat-unfilled" and d.get("seat") == seat
            for d in degradations
        ):
            return
        degradations.append({
            "constraint": "seat-unfilled",
            "seat": seat,
            "reason": (
                "seat %s has no live candidate outside the makers' families (%s) — "
                "recorded unfilled, not run" % (seat, ", ".join(sorted(makers)))
            ),
        })

    # Per-seat eligibility
    eligible_by_seat: dict[str, list[dict]] = {}
    maker_emptied_seats: set[str] = set()
    pin_unfilled_seats: set[str] = set()
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
        else:
            eligible = list(base)

        # #670: the makers' families are barred from EVERY seat in MAKER_EXCLUDED_SEATS. A seat with
        # no live candidate outside them is left empty and recorded unfilled below — never seated
        # with a maker family and never backfilled.
        if makers and seat in MAKER_EXCLUDED_SEATS and eligible:
            eligible = [cfg for cfg in eligible if cfg["family"] not in makers]
            if not eligible:
                maker_emptied_seats.add(seat)

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
        default_model, default_effort, _pin = _cell(tier, pin_vendor, role_pins or None)
        if default_model is None:
            degradations.append(
                {
                    "constraint": "pin",
                    "reason": f"pin {pin_seat} not honorable — fell back to rotation",
                }
            )
            continue
        model = pin.get("model", default_model)
        effort = pin["effort"] if "effort" in pin else (model_registry.resolve_dispatch(tier, pin_vendor, model, None).get("effort") if "model" in pin else default_effort)
        pin_cell_live = (
            pin_vendor == "claude"
            or (pin_vendor, model, effort) in live_cells_normalized
        )
        if pin_cell_live and is_allowed(tier, pin_vendor, model, effort):
            fam = family_for(tier, pin_vendor)
            if pin_seat in MAKER_EXCLUDED_SEATS and fam in makers:
                # a pin cannot seat a maker: the seat is left unfilled and no other vendor replaces it
                pin_unfilled_seats.add(pin_seat)
                eligible_by_seat[pin_seat] = []
                degradations.append({
                    "constraint": "pin-breaks-constraint",
                    "seat": pin_seat,
                    "reason": (
                        "pinned seat %s names vendor %s, whose family %s is a maker family — "
                        "the seat is recorded unfilled" % (pin_seat, pin_vendor, fam)
                    ),
                })
                continue
            if pin_seat in STRONG_TIER_SEATS and tier != "reviewer-deep":
                degradations.append(
                    {
                        "constraint": "pin-breaks-constraint",
                        "reason": f"pinned strong seat {pin_seat} is below reviewer-deep",
                    }
                )
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
        if not cfgs and (seat in maker_emptied_seats or seat in pin_unfilled_seats):
            unfilled = _unfilled_cfg(_tier_for(seat))
            fixed_seats[seat] = unfilled
            _note_unfilled(seat)
            options[seat] = [unfilled]
        elif not cfgs:
            fixed = _backfill(seat)
            fixed_seats[seat] = fixed
            if is_unfilled(fixed):
                _note_unfilled(seat)
            else:
                degradations.append(
                    {
                        "constraint": "seat-unfilled",
                        "seat": seat,
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
        # an unfilled seat carries no family, so it never counts as an author seat
        author_count = sum(
            1 for s in roster
            if assignment[s]["family"] is not None and assignment[s]["family"] == author_family
        )
        vendor_tuple = tuple(assignment[s]["vendor"] or "" for s in roster)
        return (author_count, vendor_tuple)

    def _meets_soft(assignment: dict[str, dict], check_author_minority: bool, check_critical: bool) -> bool:
        if check_critical:
            critical_families = {
                assignment[s]["family"]
                for s in roster
                if s in CRITICAL_SEATS and assignment[s]["family"] is not None
            }
            if len(critical_families) < required_critical_families(roster):
                return False
        if check_author_minority and author_family:
            # Per-seat maker prohibition (every roster seat) plus numeric minority cap. For a full
            # PANEL_ROSTER the per-seat bar subsumes the cap. An unfilled seat has no family and is
            # never an author seat.
            author_seats = [
                s for s in roster
                if assignment[s]["family"] is not None
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
        for s in roster:
            if is_unfilled(seats_out[s]):
                _note_unfilled(s)
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
                    "reason": "relaxed critical-diversity — no assignment spanned ≥%d families"
                    % required_critical_families(roster),
                })
                seats_out = chosen

    role_pin_degraded: set[str] = set()
    for seat in roster:
        if seat in role_pin_degraded:
            continue
        cfg = seats_out.get(seat)
        if not isinstance(cfg, dict) or cfg.get("vendor") != "codex":
            continue
        tier = cfg.get("tier") or _tier_for(seat)
        if tier not in role_pins:
            continue
        matrix_model, matrix_effort, _mp = _cell(tier, "codex", None)
        if matrix_model is None:
            continue
        if cfg.get("model") != matrix_model or cfg.get("effort") != matrix_effort:
            continue
        pin_model, pin_effort, pin_info = _cell(tier, "codex", role_pins)
        if not pin_info:
            continue
        if pin_info.get("honored"):
            if (pin_model, pin_effort) == (matrix_model, matrix_effort):
                continue
            if ("codex", pin_model, pin_effort) in live_cells_normalized:
                continue
            degradations.append({
                "constraint": "role-pin-not-live",
                "seat": seat,
                "reason": (
                    "codex role pin %s for %s is not live — the seat fell back to %s"
                    % (pin_info["pin"], tier, matrix_model)
                ),
            })
        else:
            degradations.append({
                "constraint": "role-pin-not-honorable",
                "seat": seat,
                "reason": (
                    "codex role pin %s for %s is not on that tier's allowlist — "
                    "the seat kept %s" % (pin_info["pin"], tier, matrix_model)
                ),
            })
        role_pin_degraded.add(seat)

    result = {
        "seats": seats_out,
        "degradations": degradations,
        "seed": seed,
        "liveVendors": list(live),
        "liveCells": sorted([list(c) for c in live_cells_normalized]),
        "authorFamily": author_family,
        "livenessPinScoped": bool(liveness_pin_scoped),
        "makerFamilies": sorted(makers),
        "roster": list(roster),
    }
    if resolved_cells_source is not None:
        result["liveCellsSource"] = resolved_cells_source
    if role_pins:
        result["codexRolePins"] = dict(role_pins)
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


def effective_author_family(
    seat_map: dict, driver_author_family: str | None = None,
) -> str | None:
    a_d = driver_author_family if isinstance(driver_author_family, str) and driver_author_family else None
    if not isinstance(seat_map, dict):
        return a_d
    a_m = seat_map.get("authorFamily")
    a_m = a_m if isinstance(a_m, str) and a_m else None
    return a_d if a_d else a_m


def violation_basis(seat_map: dict, driver_author_family: str | None = None) -> str:
    if not isinstance(seat_map, dict):
        return VIOLATION_BASIS_NO_SEATS
    seats = seat_map.get("seats")
    if not isinstance(seats, dict) or not seats:
        return VIOLATION_BASIS_NO_SEATS
    a_d = driver_author_family if isinstance(driver_author_family, str) and driver_author_family else None
    a_m = seat_map.get("authorFamily")
    a_m = a_m if isinstance(a_m, str) and a_m else None
    if not a_d and not a_m:
        return VIOLATION_BASIS_NO_AUTHOR_FAMILY
    if not a_d and a_m:
        return VIOLATION_BASIS_SELF_ASSERTED_AUTHOR_FAMILY
    return VIOLATION_BASIS_COMPLETE


def _normalize_submitted_violation(v) -> dict:
    if not isinstance(v, dict):
        return {"constraint": "malformed-violation-record"}
    constraint = v.get("constraint")
    if not isinstance(constraint, str) or not constraint:
        return {"constraint": "malformed-violation-record"}
    return dict(v)


def derived_violations(
    seat_map: dict, driver_author_family: str | None = None,
) -> list[dict]:
    author_family = effective_author_family(seat_map, driver_author_family)
    if violation_basis(seat_map, driver_author_family) != VIOLATION_BASIS_NO_SEATS:
        rederived = verify(seat_map, author_family)
    else:
        rederived = []

    mismatch: list[dict] = []
    if isinstance(seat_map, dict):
        a_d = driver_author_family if isinstance(driver_author_family, str) and driver_author_family else None
        a_m = seat_map.get("authorFamily")
        a_m = a_m if isinstance(a_m, str) and a_m else None
        if a_d and a_m and a_d != a_m:
            mismatch.append({"constraint": "author-family-mismatch"})

    submitted_raw = seat_map.get("violations") if isinstance(seat_map, dict) else None
    submitted: list[dict] = []
    if isinstance(submitted_raw, list):
        submitted = [_normalize_submitted_violation(v) for v in submitted_raw]

    union: dict[tuple[str, str], dict] = {}
    for v in itertools.chain(rederived, mismatch):
        key = (str(v.get("constraint", "")), str(v.get("seat") or ""))
        if key not in union:
            rec = dict(v)
            if "evidence" not in rec:
                rec["evidence"] = EVIDENCE_UNPROVEN_BASIS
            rec["derived"] = True
            union[key] = rec

    for v in submitted:
        key = (str(v.get("constraint", "")), str(v.get("seat") or ""))
        union[key] = dict(v)

    out = list(union.values())
    out.sort(key=lambda item: (str(item.get("constraint", "")), str(item.get("seat") or "")))
    return out


def classify_violations(
    seat_map: dict, driver_author_family: str | None = None,
) -> dict:
    """{'unexcused': [...], 'excusedByPin': [...], 'excusedByLiveness': [...]} (#680 R-A/R-B)."""
    empty = {"unexcused": [], "excusedByPin": [], "excusedByLiveness": []}
    if not isinstance(seat_map, dict):
        return empty
    violations = derived_violations(seat_map, driver_author_family)
    raw_seats = seat_map.get("seats")
    seats = raw_seats if isinstance(raw_seats, dict) else {}
    author_family = effective_author_family(seat_map, driver_author_family)

    unexcused: list[dict] = []
    excused_by_pin: list[dict] = []
    excused_by_liveness: list[dict] = []

    for v in violations:
        if not isinstance(v, dict):
            unexcused.append({"constraint": "malformed-violation-record"})
            continue
        if v.get("derived") is True:
            unexcused.append(dict(v))
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

        raw_makers = seat_map.get("makerFamilies")
        maker_set = {f for f in (raw_makers if isinstance(raw_makers, list) else []) if isinstance(f, str) and f}
        maker_set.add(author_family)
        achievable: set[str] | None = set()
        for cs in collapsed:
            cfg = seats.get(cs)
            if not isinstance(cfg, dict):
                achievable = None
                break
            if cfg.get("source") == "pinned":
                fam = _seat_family(cs, cfg)
                if isinstance(fam, str) and fam:
                    achievable.add(fam)
            else:
                fams = _resolvable_families_for_seat(seat_map, cs, cfg)
                if fams is None:
                    achievable = None
                    break
                achievable |= fams - maker_set

        if achievable is None:
            stamped = dict(v)
            stamped["evidence"] = "unproven-liveness"
            unexcused.append(stamped)
            continue
        if len(achievable) >= required_critical_families(effective_roster(seat_map) or PANEL_ROSTER):
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


def unexcused_violations(
    seat_map: dict, driver_author_family: str | None = None,
) -> list[dict]:
    """Back-compat thin wrapper — the violations that STAND."""
    return classify_violations(seat_map, driver_author_family)["unexcused"]


def verify(seat_map: dict, author_family: str | None) -> list[dict]:
    seats = seat_map.get("seats")
    if not isinstance(seats, dict):
        return [{"constraint": "malformed"}]

    violations: list[dict] = []

    roster = effective_roster(seat_map) or PANEL_ROSTER
    # axis: every seat the lane basis calls for must be on the roster; an absent basis calls for the risky one — see bite-proof record wo_a_1797_roster
    for seat in roster_for(seat_map.get("laneBasis")):
        if seat not in roster:
            violations.append({"seat": seat, "constraint": "roster-missing-required"})
    for seat in roster:
        if seat not in seats:
            violations.append({"seat": seat, "constraint": "missing-seat"})
        elif is_unfilled(seats[seat]):
            # a known not-run seat, disclosed as a `seat-unfilled` degradation
            continue
        elif not isinstance(seats[seat], dict):
            violations.append({"seat": seat, "constraint": "malformed"})

    if isinstance(author_family, str) and author_family:
        for seat in sorted(MAKER_EXCLUDED_SEATS):
            if seat not in seats:
                continue
            cfg = seats[seat]
            if not isinstance(cfg, dict) or is_unfilled(cfg):
                continue
            seat_fam = _seat_family(seat, cfg)
            if seat_fam is None:
                violations.append({"seat": seat, "constraint": "unresolvable-seat-vendor"})
                continue
            if seat_fam != author_family:
                continue
            if _alternative_family_live(seat_map, seat, cfg, author_family):
                # an alternative family was reachable and the maker seated anyway — a VIOLATION
                violations.append({"seat": seat, "constraint": "maker-family"})
            # else: unavoidable — carried as the `same-family` DEGRADATION, not a violation (#670)

    for seat in STRONG_TIER_SEATS:
        if seat not in seats:
            continue
        cfg = seats[seat]
        if not isinstance(cfg, dict):
            continue
        if cfg.get("tier") != STRONG_TIER_REQUIRED:
            violations.append({"seat": seat, "constraint": "strong-tier"})

    critical_families = _critical_families(seats)
    if len(critical_families) < required_critical_families(roster):
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
    raw_makers = seat_map.get("makerFamilies")
    maker_families = {f for f in (raw_makers if isinstance(raw_makers, list) else []) if isinstance(f, str) and f}
    if isinstance(af, str) and af:
        maker_families.add(af)
    roster = list(_scanned_seats(seat_map))
    out = {
        "seats": seat_map.get("seats", {}),
        "degradations": degradations,
        "seed": seat_map.get("seed"),
        "liveVendors": seat_map.get("liveVendors", []),
        "liveCells": receipt_live_cells,
        "liveCellsSource": receipt_cells_source,
        "authorFamily": af,
        "livenessPinScoped": bool(seat_map.get("livenessPinScoped")),
        "violations": verify(seat_map, af),
        "makerFamilies": sorted(maker_families),
        "roster": roster,
    }
    role_pins, pins_usable = _read_codex_role_pins(seat_map)
    if pins_usable and role_pins:
        out["codexRolePins"] = dict(role_pins)
    elif "codexRolePins" in seat_map:
        out["codexRolePins"] = seat_map["codexRolePins"]
    if "laneBasis" in seat_map:
        out["laneBasis"] = seat_map["laneBasis"]
    # compose stamps these three together; a map that never went through compose carries none
    for key in ("hostFamily", "nonPanelLiveCells", "nonPanelLiveCellsSource"):
        if key in seat_map:
            out[key] = seat_map[key]
    return out


def build_parser():
    import argparse

    import cli_contract as cc

    ap = argparse.ArgumentParser(prog="seat_map")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compose", help="compute the panel seat map for a run")
    cc.add_argument(c, "--author-family", contract="free-text", default=None)
    cc.add_argument(c, "--pr-number", contract="free-text", default=None)
    cc.add_argument(c, "--head-sha", contract="free-text", default=None)
    cc.add_argument(
        c,
        "--base-ref",
        contract="free-text",
        default=None,
        help="the pinned base commit; with --head-sha it names the diff the lane call reads, "
             "and the roster follows it (absent or unreadable: the full risky roster)",
    )
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
        help="comma list of non-claude engines to probe for liveness when --live-vendors is omitted (review-code passes preflight_probe.review_cross_vendor_engines)",
    )
    cc.add_argument(
        c,
        "--pins",
        contract="free-text",
        default=None,
        help="JSON dict of seat pins passed to build(); overlays the seat pins in core.md per seat",
    )
    cc.add_argument(c, "--host-model", contract="free-text", default=None)
    cc.add_argument(
        c,
        "--session-transcript",
        contract="free-text",
        default=None,
        help="this session's transcript path; the host model is read from its latest main-chain turn when --host-model names none (#2110)",
    )
    cc.add_argument(
        c,
        "--session-transcript-from",
        contract="free-text",
        default=None,
        help="byte offset of the session start in --session-transcript; only turns at or after it count (#2110)",
    )
    cc.add_argument(c, "--implementation-engine", contract="free-text", default=None)
    cc.add_argument(
        c,
        "--maker-family",
        contract="free-text",
        action="append",
        default=[],
        dest="maker_family",
        help="repeatable; a model family that wrote or fixed this change and may not review it "
             "(a build passes its implementers' and fixers' families)",
    )
    return ap


_CHANGED_PATHS_TIMEOUT = 120


def _lane_basis(repo_root, base_ref, head_sha):
    """The lane call for the change between the pinned base and the reviewed head. Fail-closed: a
    missing base or head, a git failure, or an unreadable answer is `lane_call.unavailable`, whose
    floor is full, so the roster can only grow from it. Never raises."""
    import subprocess

    import lane_call

    def closed(why):
        return lane_call.unavailable("lane-basis-unavailable: %s" % why, proposed="full")

    if not base_ref:
        return closed("no --base-ref was given")
    if not head_sha:
        return closed("no --head-sha was given")
    try:
        done = subprocess.run(
            ["git", "-C", repo_root, "diff", "--name-only", "-z", "--no-renames",
             "%s...%s" % (base_ref, head_sha)],
            capture_output=True, timeout=_CHANGED_PATHS_TIMEOUT,
        )
        if done.returncode != 0:
            return closed("git diff exited %d" % done.returncode)
        paths = [p for p in done.stdout.decode("utf-8").split("\0") if p]
        return lane_call.call(repo_root, paths, proposed="full")
    except Exception as exc:
        return closed("%s: %s" % (type(exc).__name__, exc))


def _lane_basis_receipt(basis):
    """The lane basis as the receipt carries it: floor, lane, reasons and area names; the path
    lists reduced to counts."""
    import lane_call

    touched = [h for h in basis.get("touched", []) if isinstance(h, dict)]
    names = [h.get("name") for h in touched if isinstance(h.get("name"), str)]
    return {
        "floor": basis.get("floor"),
        "lane": basis.get("lane"),
        "why": [lane_call.why_line_paths_stripped(w, names) for w in basis.get("why", [])
                if isinstance(w, str)],
        "riskAreas": basis.get("riskAreas"),
        "touched": [
            {"name": h.get("name"), "matched": len(h.get("matched") or [])} for h in touched
        ],
    }


def _core_pin_degradations(prefs, repo_root):
    """The disclosures for core.md seat pins that did not apply: an unreadable core.md, an invalid
    entry, and a `seatPins` that is not an object (which the loader drops silently)."""
    def disclose(reason, detail):
        return {"constraint": "pin", "reason": reason, "detail": detail}

    out: list[dict[str, str]] = []
    if prefs.get("readError") is not None:
        out.append(disclose(
            "core.md could not be read, so its seat pins were not applied — the panel composes unpinned",
            str(prefs["readError"]),
        ))
    invalid = prefs.get("invalidSeatPins")
    if isinstance(invalid, dict):
        for seat, why in sorted(invalid.items()):
            out.append(disclose(
                "core.md seat pin for %s is not usable — the seat composes by rotation" % seat,
                str(why),
            ))
    if prefs.get("readError") is None:
        try:
            import core_md

            raw = core_md.gate_config_usable_prefs(core_md.engine_preferences_for_gate(cwd=repo_root))
            if "seatPins" in raw and not isinstance(raw["seatPins"], dict):
                out.append(disclose(
                    "core.md seatPins is not an object, so none of its seat pins were applied",
                    "seatPins is a %s" % type(raw["seatPins"]).__name__,
                ))
        except Exception as exc:
            out.append(disclose(
                "core.md seatPins could not be re-read, so a malformed value would go unnoticed",
                "%s: %s" % (type(exc).__name__, exc),
            ))
    return out


def _panel_codex_role_pins(codex_models: dict | None) -> dict[str, str]:
    if not isinstance(codex_models, dict):
        return {}
    out: dict[str, str] = {}
    for tier in _PANEL_PIN_TIERS:
        pin = codex_models.get(tier)
        if isinstance(pin, str) and pin:
            out[tier] = pin
    return out


def main(argv):
    import json
    import sys

    args = build_parser().parse_args(argv[1:])
    if args.cmd == "compose":
        import time

        import engine_pref

        notes: list[dict[str, str]] = []
        family_degradations: list[dict[str, str]] = []

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

        prefs = engine_pref.load_engine_prefs(args.repo_root)
        lane_basis = _lane_basis(args.repo_root, args.base_ref, args.head_sha)
        roster = roster_for(lane_basis)
        family_degradations.extend(_core_pin_degradations(prefs, args.repo_root))
        # Seat pins from core.md bind every seat of the roster; --pins overrides per seat. A core.md
        # pin for a known seat the roster does not seat is skipped: a project-wide specialist pin
        # does not apply to a change that does not seat the specialist.
        core_pins = prefs.get("seatPins")
        merged_pins = {
            seat: pin for seat, pin in (core_pins if isinstance(core_pins, dict) else {}).items()
            if seat in roster or seat not in KNOWN_SEATS
        }
        merged_pins.update(pins or {})
        if merged_pins:
            pins = merged_pins
        codex_role_pins = _panel_codex_role_pins(prefs.get("codexModels"))
        invalid_codex = prefs.get("invalidCodexModels")
        if isinstance(invalid_codex, dict):
            for tier in _PANEL_PIN_TIERS:
                if tier in invalid_codex:
                    family_degradations.append({
                        "constraint": "role-pin-not-honorable",
                        "reason": invalid_codex[tier],
                    })

        author_family = args.author_family
        receipt_host_family = None
        # The build session applies the review's fixes on this host, so its family is a maker: the
        # one family kept off every seat besides the author's, on every implementation engine.
        host_maker_family = None
        host_model, _ = host_model_lib.resolve(
            args.host_model or "", args.session_transcript or "", args.session_transcript_from or "")
        if args.implementation_engine is not None:
            if args.author_family is not None:
                print("family-flags-conflict", file=sys.stderr)
                return 1
            host_fam = model_registry.host_family(host_model)
            receipt_host_family = host_fam
            impl_engine = args.implementation_engine
            claude_host_fam = model_registry.family_for("implementer", "claude")
            author_family = model_registry.family_for("implementer", impl_engine)
            if author_family is None:
                print("author-family-unresolved:%s" % impl_engine, file=sys.stderr)
                return 1
            host_maker_family = host_fam or claude_host_fam
            if host_fam is None:
                reason = (
                    "host model unknown — neither the start event nor the session transcript "
                    "named a model; the host family fell back to the claude "
                    "host's family (%s); the author family is the %s implementation "
                    "engine's (%s)"
                    % (claude_host_fam, impl_engine, author_family)
                )
                family_degradations.append({
                    "constraint": "host-model-unknown",
                    "reason": reason,
                })
            elif host_fam != author_family:
                family_degradations.append({
                    "constraint": "maker-family-split",
                    "reason": (
                        "author family is %s (%s implementation engine) but the build "
                        "session applies the review's fixes on this host as %s; "
                        "the host family is kept off every seat as a second "
                        "maker family"
                        % (author_family, impl_engine, host_fam)
                    ),
                })

        extra_maker_families: frozenset[str] | None = None
        if host_maker_family is not None and host_maker_family != author_family:
            extra_maker_families = frozenset({host_maker_family})

        flag_makers = frozenset(f for f in (args.maker_family or []) if f)
        if flag_makers:
            extra_maker_families = frozenset(extra_maker_families or ()) | flag_makers

        live_cells = None
        live_cells_source = None
        import preflight_probe

        non_panel_report: dict = {}
        if args.live_vendors is not None:
            live = [v for v in args.live_vendors.split(",") if v]
            liveness_pin_scoped = False
            live_cells_source = "synthesized"
            synthesized_nonpanel = preflight_probe.needed_configs_for(NONPANEL_CELL_ROLES, live)
            non_panel_report = {
                "liveCells": sorted(
                    {(vendor, model, effort) for vendor, cells in synthesized_nonpanel.items()
                     for model, effort in cells},
                    key=lambda cell: (cell[0], cell[1], cell[2] is not None, cell[2] or ""),
                ),
                "source": liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED,
            }
        else:
            now = time.time()
            cache_path = liveness_cache.receipt_path(".")

            configured = [e for e in args.configured_engines.split(",") if e]
            needed_override = reachable_configs(
                configured, pins, roster=roster, codex_role_pins=codex_role_pins or None,
            )
            if not pins and not codex_role_pins:
                needed_override = None
            liveness_pin_scoped = bool(pins)
            live, live_cells, _liveness, notes, live_cells_source, _cache_provenance = (
                preflight_probe.live_vendors_for_composition(
                    configured,
                    needed_override=needed_override,
                    extra_needed=preflight_probe.needed_configs_for(NONPANEL_CELL_ROLES, configured),
                    extra_report=non_panel_report,
                    cache_path=cache_path,
                    now=now,
                )
            )
        seed =seed_from(args.pr_number, args.head_sha)
        build_kwargs: dict = {
            "pins": pins,
            "liveness_pin_scoped": liveness_pin_scoped,
            "live_cells": live_cells,
            "live_cells_source": live_cells_source,
            "codex_role_pins": codex_role_pins or None,
        }
        if extra_maker_families is not None:
            build_kwargs["extra_maker_families"] = extra_maker_families
        sm = build(
            roster,
            live,
            author_family,
            seed,
            **build_kwargs,
        )
        sm["laneBasis"] = _lane_basis_receipt(lane_basis)
        sm["hostFamily"] = receipt_host_family
        sm["nonPanelLiveCells"] = [list(c) for c in non_panel_report.get("liveCells", [])]
        sm["nonPanelLiveCellsSource"] = non_panel_report.get(
            "source", liveness_cache.LIVE_CELLS_SOURCE_UNPROBED)
        if family_degradations:
            sm["degradations"] = list(sm.get("degradations", [])) + family_degradations
        extra_degradations: list[dict[str, str]] = []
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
