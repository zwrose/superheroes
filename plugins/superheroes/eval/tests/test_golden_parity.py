"""Golden parity: Python harness vs frozen JS-shell goldens (#507 WO-D).

For each of the 12 goldens under ``fixtures/review_loop/goldens/``, run the Python
harness on the matching fixture (with ``capture_goldens.normalize``) and compare.

Where #507's round-driver path is REQUIRED to differ from the JS shell schedule,
the difference is named here as an explicit per-fixture, per-field allowlist with a
one-line reason — never a blanket exclusion. ``PARITY.md`` must match this table.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parents[1]
FIXTURES = EVAL / "fixtures" / "review_loop"
GOLDENS = FIXTURES / "goldens"
LIB = EVAL.parent / "lib"

sys.path.insert(0, str(EVAL))
sys.path.insert(0, str(LIB))

import review_loop_runner as harness  # noqa: E402
from capture_goldens import normalize  # noqa: E402

# Per-golden, per-top-level-field allowlist. Reasons must stay in sync with PARITY.md.
ALLOWLIST: dict[str, dict[str, str]] = {
    "telemetry_failure.golden.json": {},
    "telemetry_failure.fail-telemetry.golden.json": {},
    "plan_120_replay.golden.json": {
        "roundCount": "#507 audited-chain certifies after delta rounds; JS needed intermediate+confirmation to round 4",
        "seen": "#507 scoped-finder replaces plan_round intermediate/confirmation seat schedule",
        "tokenTotal": "fewer reviewer leaves under delta rounds than the JS full-roster schedule",
        "telemetry": "dimensionCounts/expectedLeaves follow delta-round seats, not JS plan_round skips",
        "fixContexts": "harness cites file/line for mechanical_compile; JS kept synthesisUnverified uncited findings",
    },
    "code_review_recurring_class.golden.json": {
        "roundCount": "#507 audited-chain certifies after delta rounds; JS confirmation at round 4",
        "seen": "#507 scoped-finder replaces plan_round intermediate/confirmation seat schedule",
        "tokenTotal": "fewer reviewer leaves under delta rounds than the JS full-roster schedule",
        "telemetry": "dimensionCounts/expectedLeaves follow delta-round seats, not JS plan_round skips",
        "fixContexts": "harness cites file/line for mechanical_compile; JS kept synthesisUnverified uncited findings",
    },
    "resume_memory.golden.json": {
        "roundCount": "round_driver.run_loop has no resume seam; seeds replay from round 1 then continue",
        "seen": "seed replay starts at baseline round 1 rather than JS resume at round 2",
        "telemetry": "expectedLeaves/dimensionCounts follow seed-replay schedule, not JS resume",
        "fixContexts": "seed replay yields an extra early fix; finding shape includes cited file/line",
        "fixResults": "extra fix round under seed replay vs JS single post-resume fix",
    },
    "wrong_principle.golden.json": {
        "terminal": "#507 audited-chain certifies after discharge; JS confirmation parked on challenged principle",
        "roundCount": "delta rounds continue fixing rather than parking at confirmation",
        "seen": "#507 scoped-finder schedule replaces JS confirmation challenge path",
        "tokenTotal": "more fix rounds under delta path than JS halt-at-3",
        "telemetry": "terminal/leaves differ under audited-chain vs JS halted confirmation",
        "fixContexts": "more fixes + cited finding shape vs JS synthesisUnverified",
        "fixResults": "more fix rounds under delta path",
    },
    "skipped_dimension_regression.golden.json": {
        "terminal": "#507 Important-only path certifies audited-chain before the Critical confirmation event runs",
        "roundCount": "audited-chain ends earlier than JS confirmation-cap park",
        "seen": "Critical lived on JS confirmation seats that delta rounds never schedule",
        "tokenTotal": "fewer rounds than JS confirmation-cap path",
        "telemetry": "terminal/leaves differ under audited-chain vs JS halted",
        "fixContexts": "single fix + cited finding shape vs JS two-fix confirmation path",
        "fixResults": "single fix vs JS two-fix confirmation path",
    },
    "confirmation_important_certifies.golden.json": {
        "roundCount": "#507 Important certifies via audited-chain without JS confirmation+scope-verify rounds",
        "seen": "no confirmation panel under Important-only delta path",
        "tokenTotal": "fewer seats than JS confirmation schedule",
        "telemetry": "dimensionCounts follow delta seats, not JS confirmation",
        "fixContexts": "single fix + cited finding shape vs JS two-fix path",
        "fixResults": "single fix vs JS two-fix path",
    },
    "confirmation_postscoped_rework_rearms.golden.json": {
        "roundCount": "#507 Important-only path certifies before JS post-confirmation cross-cutting rework",
        "seen": "cross-cutting subjects on a later JS fix never reached under early audited-chain",
        "tokenTotal": "fewer seats than JS two-confirmation schedule",
        "telemetry": "dimensionCounts follow delta seats, not JS confirmation re-arm",
        "fixContexts": "single fix + cited finding shape vs JS three-fix path",
        "fixResults": "single fix vs JS three-fix path",
    },
    "confirmation_postscoped_narrow_certifies.golden.json": {
        "seen": "R1 cross-cutting subjects re-arm confirmation under driver last-fix rule; seat order differs from JS",
        "tokenTotal": "delta+confirmation hybrid token mix differs from JS schedule",
        "telemetry": "dimensionCounts/leaves differ under delta+confirmation hybrid",
        "fixContexts": "cited finding shape vs JS synthesisUnverified; classKey stamping differs",
    },
    "confirmation_postscoped_critical_rearms.golden.json": {
        "roundCount": "#507 Important-only path certifies before the post-confirmation Critical scoped event",
        "seen": "Critical on JS post-confirmation scoped seat never scheduled under early audited-chain",
        "tokenTotal": "fewer seats than JS two-confirmation schedule",
        "telemetry": "dimensionCounts follow delta seats, not JS Critical re-arm",
        "fixContexts": "single fix + cited finding shape vs JS three-fix path",
        "fixResults": "single fix vs JS three-fix path",
    },
    "confirmation_degraded_panel_not_counted.golden.json": {
        "roundCount": "no resume seam: seeds replay from round 1 rather than JS resume at confirmation round 3",
        "seen": "seed replay emits baseline seats instead of JS resumed confirmation seats",
        "tokenTotal": "seed-replay schedule differs from JS resume",
        "telemetry": "expectedLeaves/dimensionCounts follow seed replay, not JS resume",
        "fixContexts": "seed replay reaches a fix the JS resume path did not",
        "fixResults": "seed replay reaches a fix the JS resume path did not",
    },
}

CASES = [
    ("telemetry_failure.golden.json", "telemetry_failure.json", False),
    ("telemetry_failure.fail-telemetry.golden.json", "telemetry_failure.json", True),
    ("plan_120_replay.golden.json", "plan_120_replay.json", False),
    ("code_review_recurring_class.golden.json", "code_review_recurring_class.json", False),
    ("resume_memory.golden.json", "resume_memory.json", False),
    ("wrong_principle.golden.json", "wrong_principle.json", False),
    ("skipped_dimension_regression.golden.json", "skipped_dimension_regression.json", False),
    ("confirmation_important_certifies.golden.json", "confirmation_important_certifies.json", False),
    ("confirmation_postscoped_rework_rearms.golden.json", "confirmation_postscoped_rework_rearms.json", False),
    ("confirmation_postscoped_narrow_certifies.golden.json", "confirmation_postscoped_narrow_certifies.json", False),
    ("confirmation_postscoped_critical_rearms.golden.json", "confirmation_postscoped_critical_rearms.json", False),
    ("confirmation_degraded_panel_not_counted.golden.json", "confirmation_degraded_panel_not_counted.json", False),
]


def _public(payload: dict) -> dict:
    return {k: v for k, v in payload.items() if not str(k).startswith("_")}


@pytest.mark.parametrize("golden_name,fixture_name,fail_telemetry", CASES, ids=[c[0] for c in CASES])
def test_golden_parity(golden_name, fixture_name, fail_telemetry):
    assert golden_name in ALLOWLIST, f"missing allowlist entry for {golden_name}"
    golden = json.loads((GOLDENS / golden_name).read_text(encoding="utf-8"))
    got = normalize(_public(harness.run_fixture(
        FIXTURES / fixture_name, fail_telemetry=fail_telemetry)))

    allowed = ALLOWLIST[golden_name]
    # Every allowlisted field must actually differ (stale allowlist = port bug or drift).
    for field, reason in allowed.items():
        assert field in golden or field in got, f"{golden_name}: allowlisted {field} absent"
        assert golden.get(field) != got.get(field), (
            f"{golden_name}: allowlisted field {field} is identical — remove allowlist or fix port "
            f"(reason was: {reason})")

    # Non-allowlisted fields must match exactly.
    keys = sorted(set(golden) | set(got))
    for key in keys:
        if key in allowed:
            continue
        assert key in golden and key in got, f"{golden_name}: unexpected key skew on {key}"
        assert golden[key] == got[key], (
            f"{golden_name}: field {key} differs and is not allowlisted\n"
            f"  golden={golden[key]!r}\n  got={got[key]!r}")


def test_allowlist_covers_every_golden():
    on_disk = sorted(p.name for p in GOLDENS.glob("*.golden.json"))
    assert on_disk == sorted(ALLOWLIST.keys()), (
        f"ALLOWLIST keys must equal goldens on disk\n"
        f"  disk={on_disk}\n  allow={sorted(ALLOWLIST.keys())}")


def test_parity_md_matches_allowlist():
    """PARITY.md rows must reflect ALLOWLIST (identical vs each allowed deviation)."""
    text = (GOLDENS / "PARITY.md").read_text(encoding="utf-8")
    for golden_name, fields in ALLOWLIST.items():
        assert golden_name in text, f"PARITY.md missing {golden_name}"
        if not fields:
            # identical row
            assert f"| `{golden_name}` | identical |" in text or \
                f"| `{golden_name}` | identical |" in text.replace("  ", " "), \
                f"PARITY.md should mark {golden_name} identical"
        else:
            for field, reason in fields.items():
                assert f"`{field}`" in text, f"PARITY.md missing field {field} for {golden_name}"
                assert reason in text, f"PARITY.md missing reason for {golden_name}.{field}"
