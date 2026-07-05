import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "review_loop"
LIB = Path(__file__).resolve().parents[2] / "lib"
ROOT = Path(__file__).resolve().parents[4]
RUNNER = Path(__file__).resolve().parents[1] / "review_loop_runner.js"

if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))


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
RT = mod("review_telemetry")


RECEIPT = {"artifact": "fixture", "chain": [{"step": "citation", "evidence": "fixture"}, {"step": "reachability", "evidence": "fixture"}, {"step": "missing-check", "evidence": "fixture"}, {"step": "tooling", "evidence": "fixture"}], "coverageDecisionIds": []}


def run_fixture(name, *args):
    proc = subprocess.run(["node", str(RUNNER), str(FIXTURES / name), *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return json.loads(proc.stdout)


def assert_full_confirmation(observed, fixture):
    final_round = max(call["round"] for call in observed["seen"])
    confirmation = [call for call in observed["seen"] if call["round"] == final_round]
    assert sorted(call["reviewer"] for call in confirmation) == sorted(fixture["reviewerSet"])
    assert all(call["roundKind"] == "confirmation" for call in confirmation)
    assert all(call["tier"] == "reviewer-deep" for call in confirmation)
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
    # #174: a full confirmation panel that surfaces a NEW Important scope-verifies it (the surfaced
    # dimension re-runs the next scoped round) and certifies with ONE panel — no ratchet to a fresh
    # fully-clean confirmation.
    observed = run_fixture("confirmation_important_certifies.json")
    assert observed["terminal"] == "clean"
    confirmations = {call["round"] for call in observed["seen"] if call["roundKind"] == "confirmation"}
    assert len(confirmations) == 1, "an Important surfaced by a confirmation is scope-verified, not re-confirmed"


def test_postconfirmation_crosscutting_rework_rearms():
    # #174 finding 1: rework responding to a confirmation can span MULTIPLE scoped rounds. A narrow
    # fix at the panel + a broad fix at a later scoped round is cross-cutting rework since the panel
    # → re-arm one more full confirmation (the follow-up unions changedSubjects since the panel).
    observed = run_fixture("confirmation_postscoped_rework_rearms.json")
    confirmations = {call["round"] for call in observed["seen"] if call["roundKind"] == "confirmation"}
    assert len(confirmations) == 2, confirmations


def test_postconfirmation_narrow_rework_certifies():
    # #174 finding 1 mirror: a broad fix BEFORE the confirmation must not count as the panel's
    # rework; a narrow post-confirmation fix certifies with one panel.
    observed = run_fixture("confirmation_postscoped_narrow_certifies.json")
    confirmations = {call["round"] for call in observed["seen"] if call["roundKind"] == "confirmation"}
    assert observed["terminal"] == "clean"
    assert len(confirmations) == 1, confirmations


def test_postconfirmation_scoped_critical_rearms():
    # #174 finding 2: a NEW Critical surfaced by a post-confirmation scoped round (not the panel
    # itself) must re-arm a full confirmation, not certify off scoped verify.
    observed = run_fixture("confirmation_postscoped_critical_rearms.json")
    confirmations = {call["round"] for call in observed["seen"] if call["roundKind"] == "confirmation"}
    assert len(confirmations) == 2, confirmations


def test_degraded_confirmation_does_not_anchor_certification():
    # #174 finding 3: a confirmation with a low-confidence dimension does not satisfy the
    # every-dim-fresh-deep-high-confidence bar; a later clean round must not anchor certification on
    # it — a proper panel must run (here at round >= 3, after the seeded degraded round-2 panel).
    observed = run_fixture("confirmation_degraded_panel_not_counted.json")
    confirmations = [call["round"] for call in observed["seen"] if call["roundKind"] == "confirmation"]
    assert any(r >= 3 for r in confirmations), confirmations


def test_resume_memory_restores_fix_context():
    observed = run_fixture("resume_memory.json")
    ctx = observed["fixContexts"][0]["context"]
    # #211: the fix worklist (read from disk by the runner) holds `findings` (prior + current), not
    # the old in-memory `priorFindings` — the fixer reads the worklist file, never inlined findings.
    assert ctx["findings"]
    assert any("Test::coverage" in key for key in ctx["classKeys"])
    assert "generalizeRequired" in ctx
    assert "Test" in ctx["changedSubjects"]
    assert any(d["id"] == "RCD-resume" for d in ctx["coverageDecisions"])


def test_telemetry_failure_keeps_terminal_but_not_benchmark_valid_in_shell():
    fixture = load("telemetry_failure.json")
    normal = run_fixture("telemetry_failure.json")
    failed = run_fixture("telemetry_failure.json", "--fail-telemetry")
    assert failed["terminal"] == normal["terminal"] == fixture["expectedTerminal"]
    assert failed["benchmarkValid"] is False


def test_wrong_principle_probe_uses_shell_runner():
    observed = run_fixture("wrong_principle.json")
    assert observed["terminal"] != "clean"
    assert "RCD-wrong" in observed["coverageDecisionIds"]


def test_skipped_dimension_regression_uses_shell_runner():
    # #174: a dimension skipped in an intermediate round is still caught by the full confirmation
    # panel (the safety property preserved). The confirmation-bar economics scope-verifies a
    # surfaced Important and certifies (deliberate trade), so the fail-safe pinned here is a
    # recurring CRITICAL in the skipped dimension — it re-arms one more confirmation and, still
    # unresolved at the cap, PARKS (terminal halted) rather than slipping through as clean.
    observed = run_fixture("skipped_dimension_regression.json")
    assert observed["terminal"] != "clean"
    assert any(call["reviewer"] == "security-reviewer" and call["roundKind"] == "confirmation" for call in observed["seen"])
