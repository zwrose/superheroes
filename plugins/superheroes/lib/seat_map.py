"""Deterministic panel seat-map composition engine (issue #510).

Pure, stdlib-only. Derives all model/vendor data from model_registry — no parallel literals.
"""
from __future__ import annotations

import hashlib
import itertools
import math

from model_registry import family_for, is_allowed, matrix_config

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
CRITICAL_SEATS = frozenset({"security-reviewer", "premortem-reviewer", "code-reviewer"})
DEFAULT_TIER_BY_SEAT = {s: "reviewer-deep" for s in LENS_SEATS}
DEFAULT_TIER_BY_SEAT[GROUNDING_SEAT] = "reviewer"


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
) -> dict:
    degradations: list[dict[str, str]] = []
    tier_degraded_seats: set[str] = set()

    roster = tuple(roster) if roster else PANEL_ROSTER

    live = [v for v in (live_vendors or []) if isinstance(v, str) and v]
    if not live:
        live = ["claude"]
        degradations.append(
            {
                "constraint": "live-vendors",
                "reason": "no live vendors — defaulted to claude",
            }
        )

    tiers = dict(DEFAULT_TIER_BY_SEAT)
    if tier_by_seat:
        tiers.update(tier_by_seat)

    pins = pins or {}

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
            for vendor in sorted(live):
                cfg = _resolve_at_tier(seat, vendor, try_tier)
                if cfg is not None:
                    cfg = dict(cfg)
                    cfg["source"] = "backfill"
                    if try_tier != tier:
                        cfg["tier"] = try_tier
                    return cfg
        for vendor in sorted(live):
            for try_tier in sorted({tiers.get(s, "reviewer") for s in roster} | {"reviewer", "reviewer-deep"}):
                cfg = _resolve_at_tier(seat, vendor, try_tier)
                if cfg is not None:
                    cfg = dict(cfg)
                    cfg["source"] = "backfill"
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
            "vendor": live[0],
            "model": "",
            "effort": None,
            "tier": tier,
            "family": fallback_family,
            "source": "backfill",
        }

    # Per-seat eligibility
    eligible_by_seat: dict[str, list[dict]] = {}
    for seat in roster:
        base = [v for v in live if _resolve(seat, v) is not None]

        if seat in STRONG_TIER_SEATS:
            eligible = [_resolve(seat, v) for v in base if _resolve(seat, v) is not None]
            if not eligible:
                degradations.append(
                    {
                        "constraint": "strong-tier",
                        "reason": f"seat {seat} has no strong-tier-eligible live vendor",
                    }
                )
        elif seat == GROUNDING_SEAT:
            excl: set[str] = set()
            if author_family:
                excl.add(author_family)
            if narrative_family:
                excl.add(narrative_family)
            if not author_family or not narrative_family:
                degradations.append(
                    {
                        "constraint": "grounding-provenance",
                        "reason": "author or narrative family unknown — grounding independence not guaranteed",
                    }
                )
            eligible = [
                _resolve(seat, v)
                for v in base
                if _resolve(seat, v) is not None and _resolve(seat, v)["family"] not in excl
            ]
            if not eligible:
                degradations.append(
                    {
                        "constraint": "grounding-independence",
                        "reason": "no grounding vendor independent of author/narrative families",
                    }
                )
                eligible = [
                    _resolve(seat, v)
                    for v in base
                    if _resolve(seat, v) is not None
                    and _resolve(seat, v)["family"] != narrative_family
                ] or [_resolve(seat, v) for v in base if _resolve(seat, v) is not None]
        else:
            eligible = [_resolve(seat, v) for v in base if _resolve(seat, v) is not None]

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
        if pin_vendor in live and is_allowed(tier, pin_vendor, model, effort):
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
            for vendor in sorted(live):
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
            author_count = sum(
                1 for s in roster if assignment[s]["family"] == author_family
            )
            if author_count >= math.ceil(len(roster) / 2):
                return False
            for s in roster:
                if s in (STRONG_TIER_SEATS | CRITICAL_SEATS) and assignment[s]["family"] == author_family:
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
                degradations.append(
                    {
                        "constraint": "author-minority",
                        "reason": "relaxed author-minority cap — no assignment satisfied it",
                    }
                )
                degradations.append(
                    {
                        "constraint": "critical-diversity",
                        "reason": "relaxed critical-diversity — no assignment spanned ≥2 families",
                    }
                )
                all_assignments.sort(key=_assignment_key)
                seats_out = all_assignments[seed % len(all_assignments)]

    return {
        "seats": seats_out,
        "degradations": degradations,
        "seed": seed,
        "liveVendors": list(live),
        "authorFamily": author_family,
        "narrativeFamily": narrative_family,
    }


def verify(seat_map: dict, author_family: str | None) -> list[dict]:
    seats = seat_map.get("seats")
    if not isinstance(seats, dict):
        return [{"constraint": "malformed"}]

    violations: list[dict] = []

    for seat in PANEL_ROSTER:
        if seat not in seats:
            violations.append({"seat": seat, "constraint": "missing-seat"})

    for seat in sorted(STRONG_TIER_SEATS | CRITICAL_SEATS):
        if seat not in seats:
            continue
        cfg = seats[seat]
        if cfg.get("family") == author_family and author_family:
            violations.append({"seat": seat, "constraint": "maker-family"})

    if GROUNDING_SEAT in seats:
        cfg = seats[GROUNDING_SEAT]
        if cfg.get("family") == author_family and author_family:
            if not any(v.get("seat") == GROUNDING_SEAT and v.get("constraint") == "maker-family" for v in violations):
                violations.append({"seat": GROUNDING_SEAT, "constraint": "maker-family"})

    for seat in STRONG_TIER_SEATS:
        if seat in seats and seats[seat].get("tier") != "reviewer-deep":
            violations.append({"seat": seat, "constraint": "strong-tier"})

    critical_families = {
        seats[s]["family"]
        for s in CRITICAL_SEATS
        if s in seats
    }
    if len(critical_families) < 2:
        violations.append({"constraint": "critical-diversity"})

    violations.sort(key=lambda v: (v.get("constraint", ""), v.get("seat", "")))
    return violations


def to_receipt(seat_map: dict, author_family: str | None = None) -> dict:
    af = author_family if author_family is not None else seat_map.get("authorFamily")
    return {
        "seats": seat_map.get("seats", {}),
        "degradations": seat_map.get("degradations", []),
        "seed": seat_map.get("seed"),
        "liveVendors": seat_map.get("liveVendors", []),
        "authorFamily": seat_map.get("authorFamily"),
        "narrativeFamily": seat_map.get("narrativeFamily"),
        "violations": verify(seat_map, af),
    }


def main(argv):
    import argparse
    import json
    import sys

    ap = argparse.ArgumentParser(prog="seat_map")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compose", help="compute the panel seat map for a run")
    c.add_argument("--author-family", default=None)
    c.add_argument("--narrative-family", default=None)
    c.add_argument("--pr-number", default=None)
    c.add_argument("--head-sha", default=None)
    c.add_argument(
        "--live-vendors",
        default=None,
        help="comma list; overrides preflight (test/precomputed seam)",
    )
    c.add_argument(
        "--configured-engines",
        default="",
        help="comma list of non-claude engines; used to run preflight when --live-vendors omitted",
    )
    c.add_argument(
        "--pins",
        default=None,
        help="JSON dict of seat pins passed to build()",
    )
    args = ap.parse_args(argv[1:])
    if args.cmd == "compose":
        if args.live_vendors is not None:
            live = [v for v in args.live_vendors.split(",") if v]
        else:
            import preflight_probe

            configured = [e for e in args.configured_engines.split(",") if e]
            live, _liveness = preflight_probe.live_vendors_for_composition(configured)
        seed = seed_from(args.pr_number, args.head_sha)
        pins = None
        if args.pins is not None:
            try:
                pins = json.loads(args.pins)
            except json.JSONDecodeError as e:
                print(str(e), file=sys.stderr)
                return 1
        sm = build(
            PANEL_ROSTER,
            live,
            args.author_family,
            args.narrative_family,
            seed,
            pins=pins,
        )
        json.dump(to_receipt(sm), sys.stdout)
        sys.stdout.write("\n")
        return 0
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv))
