"""Eval harness must not pre-satisfy the cross-vendor liveness gate (#681 FIX-3).

At least one fixture path runs with fabricated canary evidence suppressed so a regression where
missing liveness should withhold certification is observable through the real harness seam.
"""
import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parents[1]
LIB = Path(__file__).resolve().parents[2] / "lib"
FIXTURES = EVAL / "fixtures" / "review_loop"

if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))
if str(EVAL) not in sys.path:
    sys.path.insert(0, str(EVAL))

import review_loop_runner as harness  # noqa: E402


def test_suppressed_canary_probes_withholds_certification():
    """premortem-reviewer (codex) runs empty in round 1; without probes, gate bites."""
    observed = harness.run_fixture(
        FIXTURES / "plan_120_replay.json",
        supply_canary_probes=False,
    )
    assert observed["terminal"] == "halted"
    assert observed["_driverReceipt"]["certificationShape"] is None
    round1 = observed["_driverReceipt"]["rounds"][0]
    assert round1["canaryUnverified"] == ["premortem-reviewer"]
