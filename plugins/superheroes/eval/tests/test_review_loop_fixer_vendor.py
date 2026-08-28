"""INV-18: fixture fixerVendor override validated before seat-map build (#1190 WO-R3)."""
import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parents[1]
LIB = Path(__file__).resolve().parents[2] / "lib"
FIXTURES = EVAL / "fixtures" / "review_loop"

if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))
if str(EVAL) not in sys.path:
    sys.path.insert(0, str(EVAL))

import model_registry  # noqa: E402
import review_loop_runner as harness  # noqa: E402

_MINIMAL_FIXTURE = {
    "name": "fixer-vendor-override",
    "reviewerSet": ["security-reviewer"],
    "reviewerEvents": [
        {"round": 1, "reviewer": "security-reviewer", "findings": [], "usageTotal": 1},
    ],
    "fixEvents": [],
    "maxRounds": 1,
}


@pytest.mark.parametrize("vendor", ["claude", "codex", "not-a-registered-vendor"])
def test_fixture_fixer_vendor_override_rejected(vendor):
    fixture = dict(_MINIMAL_FIXTURE, fixerVendor=vendor)
    with pytest.raises(ValueError) as exc:
        harness.run_fixture(fixture, supply_seat_map=False)
    assert vendor in str(exc.value)


def test_default_cursor_fixer_vendor_accepted():
    observed = harness.run_fixture(FIXTURES / "confirmation_important_certifies.json")
    assert observed["terminal"] == "clean"


def test_default_cursor_seating_unchanged():
    seat_map = harness._eval_clean_seat_map(harness._EVAL_FIXER_VENDOR)
    seated = {
        cell.get("vendor")
        for cell in (seat_map.get("seats") or {}).values()
        if isinstance(cell, dict) and cell.get("vendor")
    }
    assert seated == {"claude", "codex"}


def test_rejection_set_matches_registry_pool_families():
    pool_families = {
        model_registry.family_for("code-fixer", v)
        for v in harness._EVAL_LIVE_POOL
    }
    pool_families.discard(None)
    rejected_families = set()
    for vendor in harness._EVAL_LIVE_POOL:
        with pytest.raises(ValueError):
            harness._validate_fixer_vendor_override(vendor)
        family = model_registry.family_for("code-fixer", vendor)
        if family is not None:
            rejected_families.add(family)
    assert rejected_families == pool_families
    cursor_family = model_registry.family_for("code-fixer", "cursor")
    assert cursor_family not in pool_families
    harness._validate_fixer_vendor_override("cursor")


def test_run_fixture_driver_vendors_match_eval_live_pool():
    captured = {}

    def capture_run_loop(seams, config):
        captured["vendors"] = config.get("vendors")
        return {"verdict": "halted"}

    orig = harness.RD.run_loop
    harness.RD.run_loop = capture_run_loop
    try:
        harness.run_fixture(_MINIMAL_FIXTURE, supply_seat_map=False)
    finally:
        harness.RD.run_loop = orig
    assert captured["vendors"] == list(harness._EVAL_LIVE_POOL)
