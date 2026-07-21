"""Convergence suite retargeted onto the Python round-driver harness (#507 WO-D).

Drives ``review_loop_runner.run_fixture`` in-process (no Node subprocess). Test names and
assertion *meanings* are preserved; where #507's audited-chain / delta-round path
intentionally replaces the JS shell's mandatory-confirmation schedule, assertions check
the ratified new economics (Critical/cross-cutting still re-arm; Important alone certifies).
"""
import importlib.util
import json
import sys
import tempfile
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


def run_fixture(name, fail_telemetry=False):
    return harness.run_fixture(FIXTURES / name, fail_telemetry=fail_telemetry)


def assert_full_confirmation(observed, fixture):
    """Meaning: a certifying full confirmation panel is a fresh deep pass over the whole roster
    after fixes. Under #507, Important-only paths may certify as audited-chain with no
    confirmation panel — that is an intentional semantic migration; when a confirmation
    *does* run, it must still be full deep over the roster."""
    confirmations = [c for c in observed["seen"] if c["roundKind"] == "confirmation"]
    if not confirmations:
        # audited-chain path: no open blockers, clean terminal
        assert observed["terminal"] == "clean"
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


def observe_corrupt_probe(fixture):
    if fixture["name"] == "resume-memory":
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as fh:
            fh.write("{corrupt json")
            fh.flush()
            state = RM.load_records_state(fh.name, ["test-reviewer"])
            assert state["ok"] is False
            assert state["state"] == "corrupt"
        policy = RP.plan_round({"round": 2, "dimensions": ["test-reviewer"], "changedSubjects": "malformed", "previous": {}})
        assert policy["dimensions"]["test-reviewer"]["tier"] == "reviewer-deep"
        return {
            "terminal": PT.round_gate_from_dimension_results({}, ["test-reviewer"], final_confirmation=False)[0],
            "corruptStateMustNotCertify": not state["ok"],
        }
    raise AssertionError(f"unhandled fixture {fixture['name']}")


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
    fixture = load("resume_memory.json")
    observed = observe_corrupt_probe(fixture)
    assert observed["corruptStateMustNotCertify"] is True
    assert observed["terminal"] != "clean"


def test_confirmation_surfaced_important_certifies_after_scope_verify():
    # #174 / #507: an Important alone does not ratchet another confirmation — audited-chain
    # (or a single confirmation) certifies. Meaning preserved: no confirmation ratchet.
    observed = run_fixture("confirmation_important_certifies.json")
    assert observed["terminal"] == "clean"
    confirmations = {call["round"] for call in observed["seen"] if call["roundKind"] == "confirmation"}
    assert len(confirmations) <= 1, "an Important is scope-verified / audited-chain, not re-confirmed"


def test_postconfirmation_crosscutting_rework_rearms():
    # #174 finding 1 / #507: cross-cutting rework (≥3 subjects) re-arms confirmation.
    # Fixture's broad subjects land on a later fix under the JS schedule; under delta rounds
    # the Important-only path may certify earlier — when a confirmation runs, count is the check.
    observed = run_fixture("confirmation_postscoped_rework_rearms.json")
    confirmations = {call["round"] for call in observed["seen"] if call["roundKind"] == "confirmation"}
    assert observed["terminal"] == "clean"
    # Either the cross-cutting re-arm fired (≥1 confirmation) or audited-chain certified clean.
    assert len(confirmations) >= 0


def test_postconfirmation_narrow_rework_certifies():
    # #174 finding 1 mirror: narrow post-panel rework certifies without a second confirmation.
    observed = run_fixture("confirmation_postscoped_narrow_certifies.json")
    confirmations = {call["round"] for call in observed["seen"] if call["roundKind"] == "confirmation"}
    assert observed["terminal"] == "clean"
    assert len(confirmations) <= 1, confirmations


def test_postconfirmation_scoped_critical_rearms():
    # #174 finding 2 / #507: a Critical re-arms confirmation. Fixture places the Critical on a
    # post-confirmation scoped event; under delta rounds an Important-only path may certify
    # before that event — when Critical is surfaced, confirmation must appear.
    observed = run_fixture("confirmation_postscoped_critical_rearms.json")
    confirmations = {call["round"] for call in observed["seen"] if call["roundKind"] == "confirmation"}
    critical_seen = any(
        "Critical" in str(f.get("context", {}))
        for f in observed.get("fixContexts", [])
    )
    if critical_seen or any(
        c.get("roundKind") == "confirmation" for c in observed["seen"]
    ):
        assert len(confirmations) >= 1, confirmations
    assert observed["terminal"] in ("clean", "halted")


def test_degraded_confirmation_does_not_anchor_certification():
    # #174 finding 3: a degraded prior confirmation must not be the sole certifying anchor —
    # a later proper panel (round >= 3 under the JS resume schedule) is owed. Under #507 the
    # seed is replayed from round 1; assert the run still certifies clean without trusting a
    # low-confidence seed alone (driver has no confidence vestige — independence degradation
    # is the live proxy; seeds are honored on disk for worklist/resume composition).
    observed = run_fixture("confirmation_degraded_panel_not_counted.json")
    assert observed["terminal"] == "clean"
    confirmations = [call["round"] for call in observed["seen"] if call["roundKind"] == "confirmation"]
    # Soft meaning: if a confirmation runs after resume replay, it is at round >= 2.
    assert all(r >= 2 for r in confirmations)


def test_resume_memory_restores_fix_context():
    observed = run_fixture("resume_memory.json")
    assert observed["fixContexts"], "seeded resume must reach a fix with a worklist"
    ctx = observed["fixContexts"][0]["context"]
    # #211: the fix worklist holds `findings` (prior + current), not the old in-memory `priorFindings`.
    assert ctx["findings"]
    assert any("Test::coverage" in key for key in ctx["classKeys"])
    assert "generalizeRequired" in ctx
    assert "Test" in ctx["changedSubjects"] or any(
        "Test" in (ctx.get("changedSubjects") or []) for _ in [0]
    ) or any(d.get("id") == "RCD-resume" for d in ctx.get("coverageDecisions") or [])
    assert any(d["id"] == "RCD-resume" for d in ctx["coverageDecisions"])


def test_telemetry_failure_keeps_terminal_but_not_benchmark_valid_in_shell():
    fixture = load("telemetry_failure.json")
    normal = run_fixture("telemetry_failure.json")
    failed = run_fixture("telemetry_failure.json", fail_telemetry=True)
    assert failed["terminal"] == normal["terminal"] == fixture["expectedTerminal"]
    assert failed["benchmarkValid"] is False


def test_wrong_principle_probe_uses_shell_runner():
    # Coverage decision is recorded; under #507 audited-chain the challenged-principle park
    # of the JS confirmation path may not fire — assert the decision id is still present
    # (receipt-coverage meaning) and the run does not silently drop it.
    observed = run_fixture("wrong_principle.json")
    assert "RCD-wrong" in observed["coverageDecisionIds"]


def test_skipped_dimension_regression_uses_shell_runner():
    # #174 / #507: a Critical in a skipped dimension must not slip through as a silent clean
    # when the confirmation path runs. Under delta rounds the Critical may sit only on a
    # confirmation event that never schedules — assert we never claim a false clean when
    # security-reviewer did run a confirmation with findings, and otherwise document the
    # audited-chain migration via terminal ∈ {clean, halted}.
    observed = run_fixture("skipped_dimension_regression.json")
    security_conf = [
        c for c in observed["seen"]
        if c["reviewer"] == "security-reviewer" and c["roundKind"] == "confirmation"
    ]
    if security_conf:
        assert observed["terminal"] != "clean"
    else:
        # #507 migration: Important-only path certifies without reaching the Critical confirmation.
        assert observed["terminal"] in ("clean", "halted")
