"""Golden parity: Python harness vs frozen JS-shell goldens (#507 WO-D).

The JS shell this file originally checked parity against was retired in #478/#555,
so what it pins today is regression against a frozen historical snapshot rather than
parity with a live second implementation — retire it only if it ever blocks a
legitimate change.

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

# Per-golden, per-top-level-field allowlist. Every allowlisted field is a #507 SCHEDULE / ECONOMICS
# migration where the TESTED PROPERTY is preserved (coverageDecisionIds and benchmarkValid match the
# golden and are NEVER allowlisted; terminal matches every golden except skipped_dimension_regression,
# whose Critical is scripted only into confirmation panels that no later round runs). Reasons must
# stay in sync with PARITY.md.
#
# The migration classes, shared across fixtures:
#   seen        — the driver's scoped-finder delta scans + re-armed confirmation PANELS replace the
#                 JS shell's per-dimension intermediate/confirmation seat schedule
#   roundCount  — delta rounds + audited-chain / confirmation re-arm reach the terminal in a
#                 different round count than the JS mandatory-first-confirmation schedule
#   tokenTotal  — the delta schedule dispatches a different set of reviewer leaves than the JS roster
#   telemetry   — expectedLeaves / dimensionCounts / roundCount follow the driver's delta-round seats
#   fixContexts — the harness cites file/line for mechanical_compile scope; fix-context shape + fix
#                 count follow the delta schedule
#   fixResults  — fix-round numbering follows the driver's delta legs, not the JS round numbers
#   no-survivor synthesis (tokenTotal, telemetry on telemetry_failure) — a round whose verification
#                 leaves no survivors dispatches no synthesis seat, so the synthesis token leaf is absent
_SEEN = ("driver scoped-finder delta scans + re-armed confirmation panels replace the JS "
         "per-dimension intermediate/confirmation seat schedule")
_TOK = "the delta schedule dispatches a different set of reviewer leaves than the JS roster schedule"
_TELEM = "expectedLeaves / dimensionCounts / roundCount follow the driver's delta-round seats, not the JS schedule"
_FIXCTX = "harness cites file/line for mechanical_compile scope; fix-context shape + count follow the delta schedule"
_FIXRES = "fix-round numbering follows the driver's delta legs, not the JS round numbers"
_NO_SURVIVOR_SYNTH = ("a round whose verification leaves no survivors dispatches no synthesis seat, "
                      "so the synthesis token leaf is absent")

ALLOWLIST: dict[str, dict[str, str]] = {
    "telemetry_failure.golden.json": {
        "tokenTotal": _NO_SURVIVOR_SYNTH,
        "telemetry": _NO_SURVIVOR_SYNTH,
    },
    "telemetry_failure.fail-telemetry.golden.json": {
        "tokenTotal": _NO_SURVIVOR_SYNTH,
    },
    "plan_120_replay.golden.json": {
        "roundCount": "audited-chain certifies after delta rounds; the JS shell reached the confirmation panel at a later round",
        "seen": _SEEN,
        "tokenTotal": _TOK,
        "telemetry": _TELEM,
        "fixContexts": _FIXCTX,
    },
    "code_review_recurring_class.golden.json": {
        "roundCount": "audited-chain certifies after delta rounds; the JS shell reached the confirmation panel at a later round",
        "seen": _SEEN,
        "tokenTotal": _TOK,
        "telemetry": _TELEM,
        "fixContexts": _FIXCTX,
    },
    "wrong_principle.golden.json": {
        "roundCount": "the challenged-coverage breaker parks at the delta round the class recurs (round 2), earlier than the JS confirmation-cap park at round 3",
        "seen": _SEEN,
        "tokenTotal": _TOK,
        "telemetry": _TELEM,
        "fixContexts": _FIXCTX,
        "fixResults": _FIXRES,
    },
    "skipped_dimension_regression.golden.json": {
        "terminal": "no later round runs a confirmation panel, so the Critical this fixture scripts only into confirmation rounds never surfaces and the loop ends clean, where the JS shell halted",
        "roundCount": "the recurring Critical is scripted only into confirmation-panel rounds, which no longer run, so the loop reaches its end in a different round count than the JS mandatory-confirmation schedule",
        "seen": "driver scoped-finder delta scans replace the JS per-dimension intermediate/confirmation seat schedule; no later round runs a confirmation panel",
        "tokenTotal": _TOK,
        "telemetry": _TELEM,
        "fixContexts": _FIXCTX,
        "fixResults": _FIXRES,
    },
    "confirmation_important_certifies.golden.json": {
        "roundCount": "an Important certifies via audited-chain without the JS confirmation + scope-verify rounds",
        "seen": _SEEN,
        "tokenTotal": _TOK,
        "telemetry": _TELEM,
        "fixContexts": _FIXCTX,
        "fixResults": _FIXRES,
    },
    "confirmation_postscoped_rework_rearms.golden.json": {
        "roundCount": "cross-cutting rework re-arms ONE confirmation over delta rounds — fewer rounds than the JS two-confirmation schedule (no mandatory first confirmation)",
        "seen": _SEEN,
        "tokenTotal": _TOK,
        "telemetry": _TELEM,
        "fixContexts": _FIXCTX,
        "fixResults": _FIXRES,
    },
    "confirmation_postscoped_narrow_certifies.golden.json": {
        "roundCount": "narrow post-confirmation rework certifies audited-chain — fewer rounds than the JS one-confirmation schedule",
        "seen": _SEEN,
        "tokenTotal": _TOK,
        "telemetry": _TELEM,
        "fixContexts": _FIXCTX,
        "fixResults": _FIXRES,
    },
    "confirmation_postscoped_critical_rearms.golden.json": {
        "roundCount": "the Critical re-arms ONE confirmation over delta rounds — fewer rounds than the JS two-confirmation schedule (no mandatory first confirmation)",
        "seen": _SEEN,
        "tokenTotal": _TOK,
        "telemetry": _TELEM,
        "fixContexts": _FIXCTX,
        "fixResults": _FIXRES,
    },
}

CASES = [
    ("telemetry_failure.golden.json", "telemetry_failure.json", False),
    ("telemetry_failure.fail-telemetry.golden.json", "telemetry_failure.json", True),
    ("plan_120_replay.golden.json", "plan_120_replay.json", False),
    ("code_review_recurring_class.golden.json", "code_review_recurring_class.json", False),
    ("wrong_principle.golden.json", "wrong_principle.json", False),
    ("skipped_dimension_regression.golden.json", "skipped_dimension_regression.json", False),
    ("confirmation_important_certifies.golden.json", "confirmation_important_certifies.json", False),
    ("confirmation_postscoped_rework_rearms.golden.json", "confirmation_postscoped_rework_rearms.json", False),
    ("confirmation_postscoped_narrow_certifies.golden.json", "confirmation_postscoped_narrow_certifies.json", False),
    ("confirmation_postscoped_critical_rearms.golden.json", "confirmation_postscoped_critical_rearms.json", False),
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


@pytest.mark.parametrize("fail_telemetry", [False, True], ids=["telemetry-ok", "fail-telemetry"])
def test_telemetry_failure_no_survivor_difference_is_exactly_the_synthesis_leaf(fail_telemetry):
    """Bounds the ``tokenTotal`` / ``telemetry`` allowlist on telemetry_failure: the only permitted
    difference is the absent synthesis leaf, at exactly these values."""
    golden_name = ("telemetry_failure.fail-telemetry.golden.json" if fail_telemetry
                   else "telemetry_failure.golden.json")
    golden = json.loads((GOLDENS / golden_name).read_text(encoding="utf-8"))
    got = normalize(_public(harness.run_fixture(
        FIXTURES / "telemetry_failure.json", fail_telemetry=fail_telemetry)))

    assert got["tokenTotal"] == 1000, got["tokenTotal"]
    if fail_telemetry:
        # the failed telemetry write carries no token usage; the whole field equals the golden's
        assert got["telemetry"] == golden["telemetry"], got["telemetry"]
        return
    usage = got["telemetry"]["tokenUsage"]
    assert usage["expectedLeaves"] == ["test-reviewer:r1"], usage
    assert usage["present"] == ["test-reviewer:r1"], usage
    assert usage["missing"] == [], usage
    assert usage["total"] == 1000, usage
    # every other telemetry key (and every other tokenUsage key) is the golden's
    assert {k: v for k, v in got["telemetry"].items() if k != "tokenUsage"} == \
        {k: v for k, v in golden["telemetry"].items() if k != "tokenUsage"}
    assert {k: v for k, v in usage.items() if k not in ("expectedLeaves", "present", "missing", "total")} == \
        {k: v for k, v in golden["telemetry"]["tokenUsage"].items()
         if k not in ("expectedLeaves", "present", "missing", "total")}


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
