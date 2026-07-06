# Finding #14: the harness verifier's checks read must WAIT on pending rollups
# (the ready flip + DoD body edit trigger a fresh CI run; a single-shot read
# right after ship judged a healthy pass "checks are not green").
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_deps as ad


def test_rollup_pending_states():
    assert ad._rollup_pending([{"conclusion": None, "status": "IN_PROGRESS"}])
    assert ad._rollup_pending([{"conclusion": "", "status": "QUEUED"}])
    assert not ad._rollup_pending([{"conclusion": "SUCCESS", "status": "COMPLETED"}])
    assert not ad._rollup_pending([{"conclusion": "FAILURE", "status": "COMPLETED"}])
    assert not ad._rollup_pending([])          # no checks = not pending (fail-closed elsewhere)
    assert not ad._rollup_pending([None, "x"])  # junk rows never read as pending


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
