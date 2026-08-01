"""Writer/reader round-trip property tests for launch ledger paths.

Reuses harness helpers from test_launcher.py (repo init, ledger env, checks,
premise builder, spawn factory, launcher module).
"""
import os
import random
import signal
import time

import pytest

import launch_ledger as ll

# Harness reused from test_launcher.py — do not duplicate.
from test_launcher import (  # noqa: E402
    L,
    _all_checks,
    _init_repo,
    _ledger_env,
    _make_spawn_fn,
    _valid_premise,
)


def _read_ledger(repo):
    """Read ledger bytes from disk."""
    return ll.read(repo)


def _assert_p1(repo):
    """P1: reader accepts every record the writers emitted."""
    read_result = _read_ledger(repo)
    assert read_result["state"] == "ok"
    folded = ll.fold(read_result["records"])
    assert folded["ok"] is True
    return read_result, folded


def _records_for_launch(records, launch_id):
    return [r for r in records if r.get("launchId") == launch_id]


def _events_for_launch(records, launch_id):
    return [r["event"] for r in _records_for_launch(records, launch_id)]


def _assert_terminal(folded, launch_id, *, terminal, terminal_kind=None, outcome=None):
    """P2: terminal state matches the path."""
    info = folded["launches"][launch_id]
    assert info["terminal"] is terminal
    if terminal:
        assert info["terminalKind"] == terminal_kind
        if outcome is not None:
            assert info["outcome"] == outcome


def _assert_child_dead(pid):
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def _assert_child_alive(pid):
    os.kill(pid, 0)


def _kill_child(pid):
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass


def _kill_process_group_and_wait(pid, timeout=3.0):
    """SIGKILL the launcher process group and poll until pid is gone."""
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return
        except ProcessLookupError:
            return
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    pytest.fail(
        "child pid %s did not die within %s seconds after SIGKILL" % (pid, timeout),
    )


def _run_launch(repo, log_dir, premise, checks, monkeypatch, **kwargs):
    return L.launch_build(
        repo,
        656,
        premise,
        checks,
        log_dir,
        spawn_fn=kwargs.pop("spawn_fn", None),
        settle_seconds=kwargs.pop("settle_seconds", 0.3),
        max_attempts=kwargs.pop("max_attempts", None),
        backoff_seconds=kwargs.pop("backoff_seconds", (0,)),
        total_deadline_seconds=kwargs.pop("total_deadline_seconds", None),
        model=kwargs.pop("model", None),
        **kwargs,
    )


# --- Part 2 scenario runners (return launch_id) -----------------------------


def _scenario_preflight_refusal(repo, log_dir, surfaces, batch_id, monkeypatch):
    checks = _all_checks()
    checks["engine-auth"] = {"state": "fail", "reason": "no auth"}
    premise = _valid_premise(repo, surfaces=surfaces, batchId=batch_id)
    result = _run_launch(repo, log_dir, premise, checks, monkeypatch)
    assert result["ok"] is False
    launch_id = result["launchId"]
    _, folded = _assert_p1(repo)
    records = _read_ledger(repo)["records"]
    assert _events_for_launch(records, launch_id) == ["reserved", "refused"]
    _assert_terminal(folded, launch_id, terminal=True, terminal_kind="refused")
    return launch_id


def _scenario_premise_refusal(repo, log_dir, surfaces, batch_id, monkeypatch):
    premise = _valid_premise(repo, surfaces=surfaces, batchId=batch_id)
    del premise["baseCommit"]
    result = _run_launch(repo, log_dir, premise, _all_checks(), monkeypatch)
    assert result["ok"] is False
    launch_id = result["launchId"]
    _, folded = _assert_p1(repo)
    records = _read_ledger(repo)["records"]
    assert _events_for_launch(records, launch_id) == ["reserved", "refused"]
    _assert_terminal(folded, launch_id, terminal=True, terminal_kind="refused")
    return launch_id


def _scenario_compose_refusal(repo, log_dir, surfaces, batch_id, monkeypatch):
    premise = _valid_premise(repo, surfaces=surfaces, batchId=batch_id)
    result = _run_launch(
        repo, log_dir, premise, _all_checks(), monkeypatch, model="__nope__",
    )
    assert result["ok"] is False
    assert result["reason"] == "model-not-registry-known"
    launch_id = result["launchId"]
    _, folded = _assert_p1(repo)
    records = _read_ledger(repo)["records"]
    assert _events_for_launch(records, launch_id) == ["reserved", "refused"]
    _assert_terminal(folded, launch_id, terminal=True, terminal_kind="refused")
    return launch_id


def _scenario_spawn_oserror_exhausted(repo, log_dir, surfaces, batch_id, monkeypatch):
    def always_oserror(argv, repo_root, out_fh, err_fh, child_env):
        raise OSError("spawn failed")

    result = _run_launch(
        repo,
        log_dir,
        _valid_premise(repo, surfaces=surfaces, batchId=batch_id),
        _all_checks(),
        monkeypatch,
        spawn_fn=always_oserror,
        max_attempts=3,
        backoff_seconds=(0, 0, 0),
        total_deadline_seconds=3600,
    )
    assert result["ok"] is False
    assert result["reason"] == "spawn-oserror-exhausted"
    launch_id = result["launchId"]
    _, folded = _assert_p1(repo)
    records = _read_ledger(repo)["records"]
    assert _events_for_launch(records, launch_id) == ["reserved", "retry", "retry", "refused"]
    _assert_terminal(folded, launch_id, terminal=True, terminal_kind="refused")
    return launch_id


def _scenario_started_append_failure(repo, log_dir, surfaces, batch_id, monkeypatch):
    real_append = L._append_under_lock
    calls = {"n": 0}

    intercepted = []

    def failing_append(repo_root, record, env=None):
        if record.get("event") == "started":
            calls["n"] += 1
            intercepted.append(record)
            return {"ok": False, "reason": "ledger-append-failed"}
        return real_append(repo_root, record, env=env)

    L._append_under_lock = failing_append
    try:
        result = _run_launch(
            repo,
            log_dir,
            _valid_premise(repo, surfaces=surfaces, batchId=batch_id),
            _all_checks(),
            monkeypatch,
            spawn_fn=_make_spawn_fn("sleep"),
            settle_seconds=0.1,
        )
    finally:
        L._append_under_lock = real_append
    assert result["ok"] is False
    assert calls["n"] >= 1
    assert len(intercepted) == 1
    assert intercepted[0].get("repaired") is not True
    launch_id = result["launchId"]
    _, folded = _assert_p1(repo)
    records = _read_ledger(repo)["records"]
    launch_recs = _records_for_launch(records, launch_id)
    events = [r["event"] for r in launch_recs]
    assert events == ["reserved", "started", "outcome"]
    started_rec = [r for r in launch_recs if r["event"] == "started"][0]
    assert started_rec.get("repaired") is True
    outcome_rec = [r for r in launch_recs if r["event"] == "outcome"][0]
    assert outcome_rec.get("outcome") == "park"
    _assert_terminal(folded, launch_id, terminal=True, terminal_kind="outcome", outcome="park")
    pid = started_rec["pid"]
    _assert_child_dead(pid)
    return launch_id


def _scenario_settle_nonzero_exit(repo, log_dir, surfaces, batch_id, monkeypatch):
    result = _run_launch(
        repo,
        log_dir,
        _valid_premise(repo, surfaces=surfaces, batchId=batch_id),
        _all_checks(),
        monkeypatch,
        spawn_fn=_make_spawn_fn("exit1"),
        settle_seconds=10,
    )
    assert result["ok"] is False
    assert result["reason"] == "settle-nonzero-exit"
    launch_id = result["launchId"]
    _, folded = _assert_p1(repo)
    records = _read_ledger(repo)["records"]
    launch_recs = _records_for_launch(records, launch_id)
    assert [r["event"] for r in launch_recs] == ["reserved", "started", "outcome"]
    outcome_rec = [r for r in launch_recs if r["event"] == "outcome"][0]
    assert outcome_rec.get("outcome") == "park"
    _assert_terminal(folded, launch_id, terminal=True, terminal_kind="outcome", outcome="park")
    started_rec = [r for r in launch_recs if r["event"] == "started"][0]
    _assert_child_dead(started_rec["pid"])
    return launch_id


def _scenario_settle_exit_zero(repo, log_dir, surfaces, batch_id, monkeypatch):
    result = _run_launch(
        repo,
        log_dir,
        _valid_premise(repo, surfaces=surfaces, batchId=batch_id),
        _all_checks(),
        monkeypatch,
        spawn_fn=_make_spawn_fn("exit0"),
        settle_seconds=10,
    )
    assert result["ok"] is False
    assert result["reason"] == "settle-exit-zero-uncertain"
    launch_id = result["launchId"]
    _, folded = _assert_p1(repo)
    records = _read_ledger(repo)["records"]
    launch_recs = _records_for_launch(records, launch_id)
    assert [r["event"] for r in launch_recs] == ["reserved", "started", "outcome"]
    outcome_rec = [r for r in launch_recs if r["event"] == "outcome"][0]
    assert outcome_rec.get("outcome") == "park"
    _assert_terminal(folded, launch_id, terminal=True, terminal_kind="outcome", outcome="park")
    started_rec = [r for r in launch_recs if r["event"] == "started"][0]
    _assert_child_dead(started_rec["pid"])
    return launch_id


def _scenario_deadline_before_spawn(repo, log_dir, surfaces, batch_id, monkeypatch):
    def always_oserror(argv, repo_root, out_fh, err_fh, child_env):
        raise OSError("spawn failed")

    result = _run_launch(
        repo,
        log_dir,
        _valid_premise(repo, surfaces=surfaces, batchId=batch_id),
        _all_checks(),
        monkeypatch,
        spawn_fn=always_oserror,
        max_attempts=5,
        backoff_seconds=(1,),
        total_deadline_seconds=0,
    )
    assert result["ok"] is False
    assert result["reason"] == "retry-deadline-exceeded"
    launch_id = result["launchId"]
    _, folded = _assert_p1(repo)
    records = _read_ledger(repo)["records"]
    assert _events_for_launch(records, launch_id) == ["reserved", "refused"]
    _assert_terminal(folded, launch_id, terminal=True, terminal_kind="refused")
    return launch_id


def _scenario_deadline_after_spawn(repo, log_dir, surfaces, batch_id, monkeypatch):
    child_pid = {"pid": None}
    clock = {"monotonic": 1000.0}
    clock_advanced = {"n": 0}

    class _TimeShim:
        @staticmethod
        def monotonic():
            return clock["monotonic"]

        @staticmethod
        def time():
            return time.time()

        @staticmethod
        def sleep(seconds):
            # No-op: monotonic is advanced explicitly; real sleep would add wall-clock
            # delay without moving the controlled deadline clock.
            pass

    real_time = L.time
    monkeypatch.setattr(L, "time", _TimeShim)
    try:
        def capture_spawn(argv, repo_root, out_fh, err_fh, child_env):
            proc = _make_spawn_fn("sleep")(argv, repo_root, out_fh, err_fh, child_env)
            child_pid["pid"] = proc.pid
            clock["monotonic"] += 10
            clock_advanced["n"] += 1
            return proc

        result = _run_launch(
            repo,
            log_dir,
            _valid_premise(repo, surfaces=surfaces, batchId=batch_id),
            _all_checks(),
            monkeypatch,
            spawn_fn=capture_spawn,
            settle_seconds=5,
            total_deadline_seconds=1,
        )
        assert result["ok"] is False
        assert result["reason"] == "retry-deadline-exceeded"
        assert clock_advanced["n"] >= 1
        launch_id = result["launchId"]
        _, folded = _assert_p1(repo)
        records = _read_ledger(repo)["records"]
        launch_recs = _records_for_launch(records, launch_id)
        assert [r["event"] for r in launch_recs] == ["reserved", "started", "outcome"]
        outcome_rec = [r for r in launch_recs if r["event"] == "outcome"][0]
        assert outcome_rec.get("outcome") == "park"
        _assert_terminal(folded, launch_id, terminal=True, terminal_kind="outcome", outcome="park")
        assert child_pid["pid"] is not None
        _assert_child_dead(child_pid["pid"])
        return launch_id
    finally:
        L.time = real_time


def _scenario_live_child_refuses_then_handback(repo, log_dir, surfaces, batch_id, monkeypatch):
    result = _run_launch(
        repo,
        log_dir,
        _valid_premise(repo, surfaces=surfaces, batchId=batch_id),
        _all_checks(),
        monkeypatch,
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.1,
    )
    assert result["ok"] is True
    launch_id = result["launchId"]
    pid = result["pid"]
    try:
        read_result, folded = _assert_p1(repo)
        _assert_terminal(folded, launch_id, terminal=False)
        records = read_result["records"]
        assert _events_for_launch(records, launch_id) == ["reserved", "started"]
        refused = ll.record_outcome(repo, launch_id, "handback", "shipped")
        assert refused["ok"] is False
        assert refused["reason"] == "terminal-child-live:%s" % pid
        records = _read_ledger(repo)["records"]
        assert _events_for_launch(records, launch_id) == ["reserved", "started"]
        _assert_child_alive(pid)
        _kill_process_group_and_wait(pid)
        assert ll.record_outcome(repo, launch_id, "handback", "shipped")["ok"]
        _, folded = _assert_p1(repo)
        records = _read_ledger(repo)["records"]
        assert _events_for_launch(records, launch_id) == [
            "reserved", "started", "outcome",
        ]
        _assert_terminal(
            folded, launch_id, terminal=True, terminal_kind="outcome", outcome="handback",
        )
        _assert_child_dead(pid)
    finally:
        _kill_child(pid)
    return launch_id


def _scenario_surface_overlap_refusal(repo, log_dir, surfaces, batch_id, monkeypatch):
    first = _run_launch(
        repo,
        log_dir,
        _valid_premise(repo, surfaces=surfaces, batchId=batch_id),
        _all_checks(),
        monkeypatch,
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.1,
    )
    assert first["ok"] is True
    first_id = first["launchId"]
    pid = first["pid"]
    try:
        overlap_surfaces = [surfaces[0]]
        second = _run_launch(
            repo,
            log_dir,
            _valid_premise(repo, surfaces=overlap_surfaces, batchId=batch_id),
            _all_checks(),
            monkeypatch,
            spawn_fn=_make_spawn_fn("sleep"),
            settle_seconds=0.1,
        )
        assert second["ok"] is False
        assert second["reason"].startswith("surface-overlap:")
        second_id = second["launchId"]
        _, folded = _assert_p1(repo)
        records = _read_ledger(repo)["records"]
        assert _events_for_launch(records, first_id) == ["reserved", "started"]
        assert _records_for_launch(records, second_id) == []
        _assert_terminal(folded, first_id, terminal=False)
    finally:
        _kill_child(pid)
    return first_id


PART2_SCENARIOS = [
    _scenario_preflight_refusal,
    _scenario_premise_refusal,
    _scenario_compose_refusal,
    _scenario_spawn_oserror_exhausted,
    _scenario_started_append_failure,
    _scenario_settle_nonzero_exit,
    _scenario_settle_exit_zero,
    _scenario_deadline_before_spawn,
    _scenario_deadline_after_spawn,
    _scenario_live_child_refuses_then_handback,
    _scenario_surface_overlap_refusal,
]


# --- Part 2: one test per scenario ------------------------------------------


@pytest.mark.parametrize(
    "scenario_fn",
    PART2_SCENARIOS,
    ids=[
        "preflight-refusal",
        "premise-refusal",
        "compose-refusal",
        "spawn-oserror-exhausted",
        "started-append-failure",
        "settle-nonzero-exit",
        "settle-exit-zero",
        "deadline-before-spawn",
        "deadline-after-spawn",
        "live-child-refuses-then-handback",
        "surface-overlap-refusal",
    ],
)
def test_roundtrip_scenario(tmp_path, monkeypatch, scenario_fn):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    scenario_fn(repo, log_dir, ["plugins/superheroes/lib"], "wave-rt", monkeypatch)


# --- Part 3: batch accounting (P3) ------------------------------------------


def test_count_rejects_a_physically_late_declaration(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    batch = "b-late-decl"
    premise = _valid_premise(repo, batchId=batch)
    result = _run_launch(repo, log_dir, premise, _all_checks(), monkeypatch)
    assert result["ok"] is True
    try:
        _kill_child(result["pid"])
    except Exception:
        pass

    declare_result = ll.declare_batch(repo, batch, 1)
    assert declare_result["ok"] is False
    assert declare_result["reason"] == "batch-already-has-reservations"

    read_result = _read_ledger(repo)
    reserved = [
        r for r in read_result["records"]
        if r.get("event") == "reserved" and r.get("batchId") == batch
    ]
    assert len(reserved) == 1
    reservation_ts = reserved[0]["ts"]

    # Direct append models corruption or a concurrent writer, not a supported call.
    ll.append(repo, {
        "event": "batch-declared",
        "batchId": batch,
        "expectedLaunches": 1,
        "ts": reservation_ts - 100.0,
        "schema": ll.SCHEMA,
    })

    count_result = ll.count(repo, batch)
    assert count_result["indeterminate"] is True
    assert count_result["resolved"] is False
    assert count_result["reason"] == "batch-declaration-after-reservations"


def test_count_never_resolves_a_batch_with_a_live_member(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    batch = "b-two"
    assert ll.declare_batch(repo, batch, 2)["ok"]

    premise1 = _valid_premise(repo, surfaces=["plugins/superheroes/a"], batchId=batch)
    first = _run_launch(
        repo, log_dir, premise1, _all_checks(), monkeypatch,
        spawn_fn=_make_spawn_fn("exit1"), settle_seconds=10,
    )
    assert first["ok"] is False

    premise2 = _valid_premise(repo, surfaces=["plugins/superheroes/b"], batchId=batch)
    second = _run_launch(
        repo, log_dir, premise2, _all_checks(), monkeypatch,
        spawn_fn=_make_spawn_fn("sleep"), settle_seconds=0.3,
    )
    assert second["ok"] is True
    pid = second["pid"]
    try:
        count_live = ll.count(repo, batch)
        assert count_live["indeterminate"] is True
        assert count_live["resolved"] is False
        assert count_live["reason"] == "batch-unresolved:%s" % second["launchId"]

        _kill_process_group_and_wait(pid)
        assert ll.record_outcome(repo, second["launchId"], "handback", "done")["ok"]

        count_done = ll.count(repo, batch)
        assert count_done["resolved"] is True
        assert count_done["indeterminate"] is False
        assert count_done["counts"]["total"] == 2
        assert count_done["counts"]["park"] == 1
        assert count_done["counts"]["handback"] == 1
    finally:
        _kill_child(pid)


# --- Part 4: interleaving sweep ---------------------------------------------


@pytest.mark.parametrize("seed", range(25))
def test_interleaved_scenarios_fold_clean(tmp_path, monkeypatch, seed):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    rng = random.Random(seed)
    order = list(PART2_SCENARIOS)
    rng.shuffle(order)
    pids = []
    try:
        for idx, scenario_fn in enumerate(order):
            surfaces = ["plugins/superheroes/rt/%d" % idx]
            batch_id = "batch-rt-%d" % idx
            scenario_fn(repo, log_dir, surfaces, batch_id, monkeypatch)
            read_result = _read_ledger(repo)
            for rec in read_result["records"]:
                if rec.get("event") == "started" and rec.get("launchId"):
                    pid = rec.get("pid")
                    if pid:
                        try:
                            os.kill(pid, 0)
                            pids.append(pid)
                        except ProcessLookupError:
                            pass
        read_result, folded = _assert_p1(repo)
        reserved_count = sum(
            1 for r in read_result["records"] if r.get("event") == "reserved"
        )
        assert reserved_count == len(PART2_SCENARIOS)
        terminal_count = sum(
            1 for info in folded["launches"].values() if info["terminal"]
        )
        assert terminal_count == len(PART2_SCENARIOS) - 1
    finally:
        for pid in pids:
            _kill_child(pid)


# --- Part 5: prove the test can fail ----------------------------------------


def _hand_reserved(launch_id, batch_id="b", surfaces=None):
  # Minimal reserved record for fold rejection tests (not a round-trip).
    return {
        "event": "reserved",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "batchId": batch_id,
        "repoId": "test",
        "issue": 656,
        "surfaces": surfaces or ["x"],
        "premise": {},
        "preflight": {},
        "argv": [],
        "doctrineDigest": "d",
        "model": "m",
    }


def _hand_outcome(launch_id):
    return {
        "event": "outcome",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "outcome": "park",
        "evidence": "ev",
    }


def _hand_started(launch_id, pid=4242):
    return {
        "event": "started",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "attempt": 1,
        "pid": pid,
        "logPath": "/tmp/log",
        "errPath": "/tmp/err",
    }


def _hand_refused(launch_id):
    return {
        "event": "refused",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "stage": "spawn",
        "reason": "spawn-oserror-exhausted",
    }


def test_fold_rejects_a_hand_written_bad_sequence():
    outcome_without_started = [_hand_reserved("a"), _hand_outcome("a")]
    result1 = ll.fold(outcome_without_started)
    assert result1["ok"] is False
    assert result1["reason"] == "fold-outcome-without-started:a"

    refused_after_started = [
        _hand_reserved("b"), _hand_started("b"), _hand_refused("b"),
    ]
    result2 = ll.fold(refused_after_started)
    assert result2["ok"] is False
    assert result2["reason"] == "fold-refused-after-started:b"

    for bad_pid in (1, 0, -1):
        bad_started = [_hand_reserved("c"), _hand_started("c", pid=bad_pid)]
        result_pid = ll.fold(bad_started)
        assert result_pid["ok"] is False
        assert result_pid["reason"] == "fold-bad-field:started:pid"
