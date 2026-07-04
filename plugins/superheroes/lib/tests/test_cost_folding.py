"""#130: the phase_cost telemetry event is FOLDED into existing durable-write leaves (no new courier
leaf — #118): phase_progress_entry.py save --cost-payload and readout_post.py --terminal/--cost-payload.
These are subprocess integration tests over a real temp git repo + the conftest-isolated store."""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.dirname(HERE)
sys.path.insert(0, LIB)
import control_plane  # noqa: E402
import journal  # noqa: E402
import token_trend  # noqa: E402


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    if subprocess.run(["git", "init", "-q", str(r)]).returncode != 0:
        pytest.skip("git unavailable")
    return str(r)


def _events(repo, work_item):
    return journal.read_events(control_plane.paths(repo, work_item)["events"])


PAYLOAD = {"phase": "workhorse", "confidence": "high"}   # the phase_record _save writes


def _save(repo, work_item, cost=None, journal_only=False, terminal_park=None):
    cmd = ["python3", os.path.join(LIB, "phase_progress_entry.py"), "save",
           "--work-item", work_item, "--step", "4", "--phase", "workhorse",
           "--payload", json.dumps(PAYLOAD)]
    if cost is not None:
        cmd += ["--cost-payload", json.dumps(cost)]
    if journal_only:
        cmd += ["--journal-only"]
    if terminal_park is not None:
        cmd += ["--terminal-park", terminal_park]
    return subprocess.run(cmd, cwd=repo, capture_output=True, text=True)


COST = {"phase": "workhorse", "dispatches": {"total": 5, "byModel": {"claude-opus-4-8": 5}},
        "tokens": {"output": 123, "input": None, "measured": True, "source": "budget"}}


def test_save_folds_phase_cost_into_the_same_leaf(repo):
    out = _save(repo, "wi-a", cost=COST)
    assert json.loads(out.stdout)["ok"] is True
    types = [e["type"] for e in _events(repo, "wi-a")]
    assert "phase_record" in types and "phase_cost" in types
    pc = [e for e in _events(repo, "wi-a") if e["type"] == "phase_cost"][0]
    assert pc["payload"]["dispatches"]["total"] == 5
    assert pc["payload"]["tokens"]["output"] == 123


def test_resave_does_not_double_count_cost(repo):
    # A resume that re-saves an already-applied phase must not append a second phase_cost.
    _save(repo, "wi-b", cost=COST)
    _save(repo, "wi-b", cost=COST)
    costs = [e for e in _events(repo, "wi-b") if e["type"] == "phase_cost"]
    assert len(costs) == 1


def test_save_without_cost_writes_no_phase_cost(repo):
    _save(repo, "wi-c")
    assert not any(e["type"] == "phase_cost" for e in _events(repo, "wi-c"))


def test_crash_resume_does_not_double_append_cost(repo):
    # Crash AFTER the phase_record+cost append but BEFORE the checkpoint write: pre-seed the record +
    # cost and leave the checkpoint absent, then re-run save (the resume). _apply re-runs because
    # reflects() is false on the stale checkpoint — but must dedupe BOTH the record and the cost, or
    # cost_report.summarize would sum a duplicate phase into an inflated run total.
    ev = control_plane.paths(repo, "wi-cr")["events"]
    journal.append(ev, "phase_record", payload=PAYLOAD, root=repo)
    journal.append(ev, "phase_cost", payload=COST, root=repo)
    _save(repo, "wi-cr", cost=COST)
    costs = [e for e in _events(repo, "wi-cr") if e["type"] == "phase_cost"]
    assert len(costs) == 1


def test_journal_only_park_save_still_records_cost(repo):
    # A PARK (journal-only) records the in-flight phase's cost too — persistPhase runs
    # journalOnly+recordCost before parkFromPhases, so tokens-per-park does NOT lose it.
    _save(repo, "wi-jo", cost=COST, journal_only=True)
    assert any(e["type"] == "phase_cost" for e in _events(repo, "wi-jo"))


def test_terminal_park_marker_makes_a_midphase_park_classifiable(repo):
    # parkFromPhases journals nothing itself; the folded `parked` marker (on the journal-only save)
    # is what lets token_trend classify a mid-phase park as parked (not 'other').
    _save(repo, "wi-tp", cost=COST, journal_only=True, terminal_park="build failed — park")
    evs = _events(repo, "wi-tp")
    assert any(e["type"] == "parked" and "build failed" in (e.get("detail") or "") for e in evs)
    assert any(e["type"] == "phase_cost" for e in evs)
    assert token_trend.classify(evs) == "parked"


def test_terminal_park_marker_is_exactly_once_on_resume(repo):
    _save(repo, "wi-tp2", cost=COST, journal_only=True, terminal_park="park reason")
    _save(repo, "wi-tp2", cost=COST, journal_only=True, terminal_park="park reason")
    parks = [e for e in _events(repo, "wi-tp2") if e["type"] == "parked"]
    assert len(parks) == 1


def _readout(repo, work_item, terminal, cost=None):
    cmd = ["python3", os.path.join(LIB, "readout_post.py"),
           "--work-item", work_item, "--reason", "done", "--terminal", terminal]
    if cost is not None:
        cmd += ["--cost-payload", json.dumps(cost)]
    return subprocess.run(cmd, cwd=repo, capture_output=True, text=True)


def test_readout_completed_journals_run_completed_and_ship_cost(repo):
    out = _readout(repo, "wi-d", "completed", cost={**COST, "phase": "ship"})
    assert json.loads(out.stdout).get("posted") is False   # no PR -> recorded to store, not posted
    types = [e["type"] for e in _events(repo, "wi-d")]
    assert "run_completed" in types
    assert "parked" not in types                            # the pre-#130 bug: ready must NOT be parked
    ship = [e for e in _events(repo, "wi-d") if e["type"] == "phase_cost"][0]
    assert ship["payload"]["phase"] == "ship"


def test_readout_parked_journals_parked(repo):
    _readout(repo, "wi-e", "parked")
    types = [e["type"] for e in _events(repo, "wi-e")]
    assert "parked" in types and "run_completed" not in types


def test_readout_malformed_cost_is_ignored_not_fatal(repo):
    cmd = ["python3", os.path.join(LIB, "readout_post.py"), "--work-item", "wi-f",
           "--reason", "done", "--terminal", "parked", "--cost-payload", "{not json"]
    out = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
    # the hand-back still records; the bad cost payload is simply dropped
    assert json.loads(out.stdout).get("recorded") is True
    assert not any(e["type"] == "phase_cost" for e in _events(repo, "wi-f"))
    assert any(e["type"] == "parked" for e in _events(repo, "wi-f"))
