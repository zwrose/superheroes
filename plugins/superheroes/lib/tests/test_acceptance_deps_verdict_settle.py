# Finding #14: the harness verifier's checks read must WAIT on pending rollups
# (the ready flip + DoD body edit trigger a fresh CI run; a single-shot read
# right after ship judged a healthy pass "checks are not green").
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_deps as ad


import ci_status


def _cls(rollup):
    return ci_status.classify(ad._normalize_rollup(rollup))["status"]


def test_normalize_rollup_effective_bucket_by_node_shape():
    # CheckRun completed -> conclusion; CheckRun in-flight -> status; StatusContext -> state.
    assert _cls([{"name": "v", "conclusion": "SUCCESS", "status": "COMPLETED"}]) == "green"
    assert _cls([{"name": "v", "conclusion": None, "status": "IN_PROGRESS"}]) == "pending"
    assert _cls([{"name": "v", "conclusion": "", "status": "QUEUED"}]) == "pending"
    assert _cls([{"name": "v", "conclusion": "FAILURE", "status": "COMPLETED"}]) == "red"
    assert _cls([]) == "none"
    ad._normalize_rollup([None, "x"])  # junk rows never crash


def test_finding_18_release_evidence_status_is_green():
    # THE run-12 bug: release-evidence is a commit STATUS (StatusContext: state, no
    # conclusion). Mixed with all-SUCCESS check-runs, the verdict must read GREEN — the
    # old inline all-SUCCESS check saw conclusion=null and read not-green.
    rollup = [
        {"name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"},
        {"name": "evidence", "status": "COMPLETED", "conclusion": "SUCCESS"},
        {"name": "pr-title", "status": "COMPLETED", "conclusion": "SUCCESS"},
        {"context": "release-evidence", "state": "SUCCESS"},   # StatusContext, conclusion=null
    ]
    assert _cls(rollup) == "green"


def test_finding_18_pending_status_context_waits():
    rollup = [{"name": "validate", "conclusion": "SUCCESS", "status": "COMPLETED"},
              {"context": "release-evidence", "state": "PENDING"}]
    assert _cls(rollup) == "pending"


def _reader_with_sequence(monkeypatch, rollups):
    """Build real_gh_reader with _run faked to return one PR whose rollup advances
    through `rollups` on successive reads."""
    import json
    calls = {"n": 0}

    def fake_run(argv, cwd=None):
        i = min(calls["n"], len(rollups) - 1)
        calls["n"] += 1
        pr = {"number": 9, "url": "u", "isDraft": False,
              "headRefName": "superheroes/wi-x-abc", "statusCheckRollup": rollups[i]}
        return 0, json.dumps([pr]), ""

    monkeypatch.setattr(ad, "_run", fake_run)
    monkeypatch.setattr(ad, "_check_failure_kind", lambda r: None)
    return ad.real_gh_reader("/root", {"work_item": "wi-x"}), calls


def test_settled_read_waits_out_pending_then_green(monkeypatch):
    pending = [{"conclusion": None, "status": "IN_PROGRESS"}]
    green = [{"conclusion": "SUCCESS", "status": "COMPLETED"}]
    reader, calls = _reader_with_sequence(monkeypatch, [pending, pending, green])
    naps = []
    out = reader(timeout_sec=600, interval_sec=20, _sleep=naps.append, _clock=lambda: len(naps) * 20.0)
    assert out["checks_green"] is True and not out["checks_pending"]
    assert calls["n"] == 3 and naps == [20, 20]


def test_settled_read_exhausted_budget_fails_closed(monkeypatch):
    pending = [{"conclusion": None, "status": "IN_PROGRESS"}]
    reader, calls = _reader_with_sequence(monkeypatch, [pending])
    naps = []
    out = reader(timeout_sec=60, interval_sec=20, _sleep=naps.append, _clock=lambda: len(naps) * 20.0)
    assert out["checks_green"] is False and out["checks_pending"] is True
    assert calls["n"] == 4   # initial + 3 polls before the 60s budget dies


def test_settled_read_red_never_waits(monkeypatch):
    red = [{"conclusion": "FAILURE", "status": "COMPLETED"}]
    reader, calls = _reader_with_sequence(monkeypatch, [red])
    out = reader(_sleep=lambda s: (_ for _ in ()).throw(AssertionError("slept on red")))
    assert out["checks_green"] is False and not out["checks_pending"]
    assert calls["n"] == 1


def test_settled_read_red_plus_pending_short_circuits(monkeypatch):
    # A confirmed FAILURE with a pending sibling must NOT wait out the budget —
    # the fate is sealed; waiting only delays the honest red.
    mixed = [{"conclusion": "FAILURE", "status": "COMPLETED"},
             {"conclusion": None, "status": "IN_PROGRESS"}]
    reader, calls = _reader_with_sequence(monkeypatch, [mixed])
    out = reader(_sleep=lambda s: (_ for _ in ()).throw(AssertionError("waited on sealed red")))
    assert out["checks_green"] is False and out["checks_red"] is True
    assert calls["n"] == 1


def test_neutral_skipped_are_not_red_via_classify():
    # NEUTRAL/SKIPPED are pass-like (ci_status._PASS), a null-conclusion in-flight is pending,
    # a hard failure is red — all through the single classify path now.
    assert _cls([{"name": "a", "conclusion": "SUCCESS"}, {"name": "b", "conclusion": "NEUTRAL"},
                 {"name": "c", "conclusion": "SKIPPED"}]) == "green"
    assert _cls([{"name": "d", "conclusion": "TIMED_OUT"}]) == "red"


def test_pending_taxonomy_is_single_homed():
    import ci_status
    assert "IN_PROGRESS" in ci_status.PENDING_STATES and "QUEUED" in ci_status.PENDING_STATES
