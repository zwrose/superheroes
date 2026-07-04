import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    path = os.path.join(_HERE, "..", "loop_readout.py")
    spec = importlib.util.spec_from_file_location("loop_readout", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LR = _load()


def _record(**kw):
    base = {"schemaVersion": LR.SCHEMA_VERSION, "terminal": "clean", "reason": "all clear"}
    base.update(kw)
    return base


def test_unknown_schema_version_surfaced_not_partial():
    out = LR.render({"schemaVersion": 99, "terminal": "clean"})
    assert "unknown record format" in out.lower()


def test_non_dict_record_is_safe():
    assert "unreadable" in LR.render(None).lower()


def test_names_fixes_drops_and_deferrals():
    out = LR.render(_record(
        terminal="clean-with-skips",
        fixes=["fixed the off-by-one in a.py"],
        deferred=[{"title": "rename var", "reason": "cosmetic"}],
        drops=[{"title": "phantom", "reason": "not in the diff", "was_blocking_tagged": False}]))
    assert "fixed the off-by-one in a.py" in out
    assert "rename var" in out and "cosmetic" in out
    assert "phantom" in out and "not in the diff" in out


def test_renders_per_reviewer_finding_outcomes():
    # #130: findingOutcomes from the telemetry record renders even when token usage is incomplete.
    out = LR.render(_record(telemetry={
        "roundCount": 2,
        "tokenUsage": {"complete": False, "total": 0, "missing": ["code-reviewer:r1"]},
        "findingOutcomes": {"code-reviewer": {"raised": 3, "blocking": 1, "carried": 2}}}))
    assert "Findings by reviewer" in out
    assert "code-reviewer: raised 3, blocking 1, carried 2" in out


def test_dropped_blocker_flagged_distinctly_ufr10():
    out = LR.render(_record(
        drops=[{"title": "real bug", "reason": "stale", "was_blocking_tagged": True},
               {"title": "nit", "reason": "n/a", "was_blocking_tagged": False}]))
    # the blocking-tagged drop is in its own scrutiny section, not the ordinary list
    scrutiny = out.split("tagged BLOCKING")[1]
    assert "real bug" in scrutiny and "nit" not in scrutiny


def test_parent_origin_named_fr21():
    out = LR.render(_record(terminal="halted", parentOrigin="plan"))
    assert "plan" in out and "upstream" in out.lower()


def test_record_missing_warned_ufr9():
    out = LR.render(_record(terminal="halted", recordMissing=True))
    assert "could not be written" in out.lower()


def test_parent_origin_multi_phase_names_every_phase_fr6():
    out = LR.render(_record(terminal="halted", parentOrigin="plan, tasks"))
    assert "plan" in out and "tasks" in out and "upstream" in out.lower()


def test_partial_telemetry_named_not_benchmark_valid():
    out = LR.render(_record(telemetry={"benchmarkValid": False, "tokenUsage": {"complete": False, "missing": ["synthesis:r1"]}}))
    assert "not benchmark-valid" in out
    assert "synthesis:r1" in out


def test_complete_telemetry_renders_counts_and_tokens():
    out = LR.render(_record(telemetry={"roundCount": 2, "benchmarkValid": True, "tokenUsage": {"complete": True, "total": 42}, "dimensionCounts": {"test-reviewer": {"run": 2, "skipped": 0, "cheap": 1, "deep": 1, "escalated": 1}}}))
    assert "Telemetry: 2 rounds" in out
    assert "test-reviewer: run 2" in out
    assert "tokens 42" in out


def test_readout_renders_coverage_decisions_and_challenges():
    out = LR.render(_record(coverageDecisions=[
        {"id": "RCD-1", "classKey": "Test::coverage::missing acceptance test", "text": "Acceptance fixtures cover repeated missing-test findings.", "sourceRound": 2},
        {"id": "RCD-bad", "classKey": "Security::leak", "text": "Security-only changes never affect readouts.", "challengedBy": "security-reviewer"},
    ]))
    assert "Coverage decisions:" in out
    assert "RCD-1" in out
    assert "Test::coverage::missing acceptance test" in out
    assert "challenged by security-reviewer" in out
