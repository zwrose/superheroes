"""Convergence suite retargeted onto the Python round-driver harness (#507 WO-D).

Drives ``review_loop_runner.run_fixture`` in-process (no Node subprocess). Each test asserts its
ONE safety property with NO disjunctive escape hatch. Where #507's audited-chain / delta-round
path intentionally replaces the JS shell's mandatory-first-confirmation schedule, the assertion
pins the RATIFIED new economics exactly (an Important alone certifies with zero confirmation
panels; a Critical / cross-cutting rework re-arms; a recurring Critical parks at the two-panel cap)
— the confirmation COUNT is the driver's real behaviour, never a tautology.
"""
import importlib.util
import json
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "review_loop"
LIB = Path(__file__).resolve().parents[2] / "lib"
EVAL = Path(__file__).resolve().parents[1]
RUNNER = EVAL / "review_loop_runner.py"

if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))
if str(EVAL) not in sys.path:
    sys.path.insert(0, str(EVAL))

import review_loop_runner as harness  # noqa: E402


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def mod(name):
    spec = importlib.util.spec_from_file_location(name, LIB / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RP = mod("review_round_policy")
RM = mod("review_memory")
PT = mod("panel_tally")


def run_fixture(name, fail_telemetry=False, corrupt_records=False):
    return harness.run_fixture(FIXTURES / name, fail_telemetry=fail_telemetry,
                               corrupt_records=corrupt_records)


def confirmation_rounds(observed):
    return sorted({c["round"] for c in observed["seen"] if c["roundKind"] == "confirmation"})


def assert_full_confirmation(observed, fixture):
    """A certifying full confirmation panel is a fresh deep pass over the whole roster after fixes.
    Under #507 an Important-only path certifies as audited-chain with NO confirmation panel (the
    ratified economics migration); when a confirmation DOES run it must still be full deep over the
    roster and precede no later fix."""
    confirmations = [c for c in observed["seen"] if c["roundKind"] == "confirmation"]
    if not confirmations:
        assert observed["terminal"] == "clean"
        assert observed["_driverReceipt"]["certificationShape"] == "audited-chain"
        return
    final_round = max(c["round"] for c in confirmations)
    confirmation = [c for c in observed["seen"] if c["round"] == final_round]
    assert sorted(c["reviewer"] for c in confirmation) == sorted(fixture["reviewerSet"])
    assert all(c["roundKind"] == "confirmation" for c in confirmation)
    assert all(c["tier"] == "reviewer-deep" for c in confirmation)
    assert all(fix["round"] < final_round for fix in observed["fixContexts"])


def assert_recurrence_triggers_decision(observed, fixture):
    expected = fixture["expectedGeneralizeRequired"]
    first = next(fix for fix in observed["fixContexts"] if fix["round"] == 1)
    second = next(fix for fix in observed["fixContexts"] if fix["round"] == 2)
    assert not first["context"].get("generalizeRequired")
    assert any(item["classKey"] == expected for item in second["context"].get("generalizeRequired", []))
    first_result = next(result for result in observed["fixResults"] if result["round"] == 1)
    second_result = next(result for result in observed["fixResults"] if result["round"] == 2)
    assert first_result["coverageDecisionIds"] == []
    assert fixture["expectedCoverageDecision"] in second_result["coverageDecisionIds"]


def test_plan_120_replay_reaches_target_round_count():
    fixture = load("plan_120_replay.json")
    observed = run_fixture("plan_120_replay.json")
    assert observed["terminal"] == fixture["expectedTerminal"]
    assert observed["roundCount"] <= fixture["maxRounds"]
    assert observed["benchmarkValid"] is True
    assert observed["telemetry"]["tokenUsage"]["complete"] is True
    assert observed["tokenTotal"] < fixture["frozenBaselineTokens"]
    assert fixture["expectedCoverageDecision"] in observed["coverageDecisionIds"]
    assert_recurrence_triggers_decision(observed, fixture)
    assert_full_confirmation(observed, fixture)


def test_code_review_benchmark_has_own_target_and_decision():
    fixture = load("code_review_recurring_class.json")
    observed = run_fixture("code_review_recurring_class.json")
    assert observed["terminal"] == fixture["expectedTerminal"]
    assert observed["roundCount"] <= fixture["maxRounds"]
    assert observed["benchmarkValid"] is True
    assert observed["telemetry"]["tokenUsage"]["complete"] is True
    assert observed["tokenTotal"] < fixture["frozenBaselineTokens"]
    assert fixture["expectedCoverageDecision"] in observed["coverageDecisionIds"]
    assert_recurrence_triggers_decision(observed, fixture)
    assert_full_confirmation(observed, fixture)


def test_resume_memory_corrupt_state_cannot_certify():
    # A corrupt/mangled durable round-records state fails closed in the driver's resume seam —
    # never certify off unreadable memory. Drives the driver directly (not just the twins).
    observed = run_fixture("resume_memory.json", corrupt_records=True)
    assert observed["terminal"] != "clean"
    assert observed["terminal"] == "halted"
    assert observed["_driverReceipt"]["certificationShape"] is None


def test_confirmation_surfaced_important_certifies_after_scope_verify():
    # #174 / #507: an Important surfaced after round 1 is scope-verified and certified via
    # audited-chain — it does NOT ratchet a confirmation panel.
    observed = run_fixture("confirmation_important_certifies.json")
    assert observed["terminal"] == "clean"
    assert confirmation_rounds(observed) == [], "an Important alone certifies audited-chain, no confirmation"


def test_postconfirmation_crosscutting_rework_rearms():
    # #174 finding 1 / #507: cross-cutting rework (≥3 distinct policy subjects on the resolving fix)
    # re-arms EXACTLY ONE full confirmation panel, then certifies clean.
    observed = run_fixture("confirmation_postscoped_rework_rearms.json")
    assert observed["terminal"] == "clean"
    assert len(confirmation_rounds(observed)) == 1, confirmation_rounds(observed)


def test_postconfirmation_narrow_rework_certifies():
    # #174 finding 1 mirror: a broad fix BEFORE the confirmation does not count as the panel's
    # rework; a narrow post-confirmation fix certifies via audited-chain with NO re-arm.
    observed = run_fixture("confirmation_postscoped_narrow_certifies.json")
    assert observed["terminal"] == "clean"
    assert confirmation_rounds(observed) == [], confirmation_rounds(observed)


def test_postconfirmation_scoped_critical_rearms():
    # #174 finding 2 / #507: a NEW Critical surfaced after the baseline re-arms ONE full confirmation
    # panel (budget not exhausted → resolved → certify clean). A security-reviewer seat runs in it.
    observed = run_fixture("confirmation_postscoped_critical_rearms.json")
    assert observed["terminal"] == "clean"
    assert len(confirmation_rounds(observed)) == 1, confirmation_rounds(observed)
    assert any(c["reviewer"] == "security-reviewer" and c["roundKind"] == "confirmation"
               for c in observed["seen"])


def test_degraded_confirmation_does_not_anchor_certification():
    # #174 finding 3: a seeded degraded (low-confidence) confirmation panel does NOT satisfy the
    # every-dim-fresh-deep-high-confidence bar, so it cannot anchor certification — the resumed loop
    # owes and runs a fresh proper full confirmation panel (round ≥ 3) that certifies as a full
    # panel, not on the degraded seed.
    observed = run_fixture("confirmation_degraded_panel_not_counted.json")
    assert observed["terminal"] == "clean"
    confirmations = confirmation_rounds(observed)
    assert any(r >= 3 for r in confirmations), confirmations
    assert observed["_driverReceipt"]["certificationShape"] == "full-panel-confirmed"


def test_resume_memory_restores_fix_context():
    observed = run_fixture("resume_memory.json")
    assert observed["fixContexts"], "seeded resume must reach a fix with a worklist"
    ctx = observed["fixContexts"][0]["context"]
    # #211: the fix worklist holds `findings` (prior + current), not the old in-memory `priorFindings`.
    assert ctx["findings"]
    assert any("Test::coverage" in key for key in ctx["classKeys"])
    assert "generalizeRequired" in ctx
    assert "Test" in ctx["changedSubjects"]
    assert any(d["id"] == "RCD-resume" for d in ctx["coverageDecisions"])


def test_telemetry_failure_keeps_terminal_but_not_benchmark_valid_in_shell():
    fixture = load("telemetry_failure.json")
    normal = run_fixture("telemetry_failure.json")
    failed = run_fixture("telemetry_failure.json", fail_telemetry=True)
    assert failed["terminal"] == normal["terminal"] == fixture["expectedTerminal"]
    assert failed["benchmarkValid"] is False


def test_wrong_principle_probe_uses_shell_runner():
    # MUST-NOT-CERTIFY: the fix recorded a coverage decision on a WRONG principle (RCD-wrong) whose
    # class the reviewer keeps raising — the challenged-coverage breaker parks (never a silent
    # clean), and the coverage decision id is still recorded (receipt-coverage meaning).
    observed = run_fixture("wrong_principle.json")
    assert observed["terminal"] != "clean"
    assert "RCD-wrong" in observed["coverageDecisionIds"]


def test_skipped_dimension_regression_uses_shell_runner():
    # #174 / #507: a recurring CRITICAL in the (intermediately-skipped) security dimension re-arms
    # confirmation panels to the two-panel cap and, still unresolved, PARKS — never a silent clean.
    # A security-reviewer seat runs in the re-armed confirmation.
    observed = run_fixture("skipped_dimension_regression.json")
    assert observed["terminal"] != "clean"
    assert observed["terminal"] == "halted"
    assert len(confirmation_rounds(observed)) == RP.MAX_CONFIRMATIONS, confirmation_rounds(observed)
    assert any(c["reviewer"] == "security-reviewer" and c["roundKind"] == "confirmation"
               for c in observed["seen"])
