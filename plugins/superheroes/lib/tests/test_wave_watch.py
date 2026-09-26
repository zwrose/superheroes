import hashlib
import json
import os
import stat
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

import heartbeat as hb
import launch_ledger as ll
import launcher
import stack_check as sc
import wave_watch as ww

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_WW_SCRIPT = os.path.join(_LIB, "wave_watch.py")
_LEDGER_LOCK_SUFFIX = ".lock"


def _init_repo(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    (tmp_path / "file.txt").write_text("x\n")
    subprocess.run(
        [
            "git", "-C", str(tmp_path),
            "-c", "user.email=test@test.local",
            "-c", "user.name=test",
            "add", ".",
        ],
        check=True,
    )
    subprocess.run(
        [
            "git", "-C", str(tmp_path),
            "-c", "user.email=test@test.local",
            "-c", "user.name=test",
            "commit", "-q", "-m", "init",
        ],
        check=True,
    )
    return str(tmp_path)


def _ledger_env(tmp_path, monkeypatch):
    root = str(tmp_path / "ledger-root")
    os.makedirs(root, mode=0o700, exist_ok=True)
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, root)
    return root


def _reserved(launch_id, batch_id, surfaces, repo_root, **extra):
    rec = {
        "event": "reserved",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "batchId": batch_id,
        "repoId": ll.repo_identity(repo_root) or "test",
        "issue": 982,
        "surfaces": surfaces,
        "premise": {},
        "preflight": {},
        "argv": [],
        "doctrineDigest": "abc123",
        "model": "test-model",
    }
    rec.update(extra)
    return rec


def _started(launch_id, attempt=1, pid=999999):
    return {
        "event": "started",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "attempt": attempt,
        "pid": pid,
        "logPath": "/tmp/log",
        "errPath": "/tmp/err",
    }


def _retry(launch_id, attempt=2):
    return {
        "event": "retry",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "attempt": attempt,
        "reason": "test",
        "delaySeconds": 0,
    }


def _outcome(launch_id, outcome="handback", evidence="done"):
    return {
        "event": "outcome",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "outcome": outcome,
        "evidence": evidence,
    }


def _run_cli(args, env=None):
    cmd = [sys.executable, "-B", _WW_SCRIPT, *args]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env or os.environ,
        timeout=30,
    )
    return proc


def _noop_gh_run(argv, **kwargs):
    body = [{"number": 1}]
    return subprocess.CompletedProcess(
        argv, 0, stdout=json.dumps(body), stderr="",
    )


_DEADLINE_LOOP_BUDGET = 100


def _with_loop_budget(monotonic_fn, budget=_DEADLINE_LOOP_BUDGET):
    calls = [0]

    def bounded():
        calls[0] += 1
        if calls[0] > budget:
            raise AssertionError(
                f"wave_watch exceeded {budget} monotonic() calls; "
                "probable infinite deadline hang"
            )
        return monotonic_fn()

    return bounded


def _advancing_monotonic(step=0.1):
    """Monotonic callable that advances by step on every read, starting at 0.0."""
    value = [0.0]

    def mono():
        current = value[0]
        value[0] += step
        return current

    return mono


_WATCHER_CLOCK_CALL_BUDGET = 10_000


class _WatcherClock:
    """Virtual clock for wave_watch: time moves only when the watcher sleeps.

    Host load cannot move it, so an arm's deadline, tick spacing and gh budget
    are the same on a busy machine as on an idle one.
    """

    def __init__(self):
        self.now = 0.0
        self.calls = 0

    def monotonic(self):
        self.calls += 1
        if self.calls > _WATCHER_CLOCK_CALL_BUDGET:
            raise AssertionError(
                f"wave_watch read the virtual clock {_WATCHER_CLOCK_CALL_BUDGET} "
                "times; a sleep that never advances it hangs the watcher"
            )
        return self.now

    def sleep(self, duration):
        if duration > 0:
            self.now += duration


class _WatcherTimeModule:
    """Stands in for wave_watch's `time`: virtual monotonic/sleep, real everything else."""

    def __init__(self, clock):
        self.monotonic = clock.monotonic
        self.sleep = clock.sleep

    def __getattr__(self, name):
        return getattr(time, name)


@pytest.fixture(autouse=True)
def watcher_clock(monkeypatch):
    # Every default monotonic/sleep in wave_watch resolves through its module-level
    # `time` at call time, so this one swap covers every arm a test does not clock.
    clock = _WatcherClock()
    monkeypatch.setattr(ww, "time", _WatcherTimeModule(clock))
    return clock


def test_wave_watch_defaults_never_reach_the_real_clock(watcher_clock):
    assert ww.time.monotonic is not time.monotonic
    assert ww.time.sleep is not time.sleep
    assert ww.time.monotonic() == 0.0
    ww.time.sleep(5)
    assert ww.time.monotonic() == 5.0
    assert ww.time.time is time.time


def test_unclocked_arm_runs_to_its_deadline_on_the_virtual_clock(
    tmp_path, monkeypatch, watcher_clock,
):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=5, interval_seconds=1, gh_run=_noop_gh_run,
    )
    assert result["event"] == "timer"
    assert watcher_clock.now == 5.0


def test_watcher_clock_budget_fails_a_non_advancing_loop(watcher_clock):
    with pytest.raises(AssertionError, match="never advances"):
        for _ in range(_WATCHER_CLOCK_CALL_BUDGET + 1):
            watcher_clock.monotonic()


def _fake_gh_cli_env(tmp_path):
    shim_dir = tmp_path / "gh-shim"
    shim_dir.mkdir()
    gh_script = shim_dir / "gh"
    gh_script.write_text('#!/bin/sh\necho \'[{"number": 1}]\'\n')
    gh_script.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
    return env


def _precreate_repo_store_dir(repo, store_root):
    # Pre-create repo-id directory so read-only assertions target files only
    # (ll.read may mkdir the repo-id dir — launch_ledger.py:192).
    repo_id = ll.repo_identity(repo)
    os.makedirs(os.path.join(store_root, repo_id), mode=0o700, exist_ok=True)
    return repo_id


def _setup_live_lane(repo, tmp_path, monkeypatch, launch_id="lane-a", batch_id="batch-982",
                     pid=999999999, stamp_state=None):
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, batch_id, 1)
    ll.append(repo, _reserved(launch_id, batch_id, ["plugins/superheroes/lib"], repo))
    ll.append(repo, _started(launch_id, pid=pid))
    if stamp_state is not None:
        hb.stamp(
            repo,
            state=stamp_state,
            phase="watch",
            launch_id=launch_id,
            stale_after_seconds=3600,
        )
    return store_root


def _setup_stale_lane(
    repo, tmp_path, monkeypatch, launch_id="lane-a", batch_id="batch-982",
    pid=None, stamp_state="working", stale_after_seconds=1, age_seconds=60,
):
    if pid is None:
        pid = os.getpid()
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, batch_id, 1)
    ll.append(repo, _reserved(launch_id, batch_id, ["plugins/superheroes/lib"], repo))
    ll.append(repo, _started(launch_id, pid=pid))
    hb.stamp(
        repo,
        state=stamp_state,
        phase="watch",
        launch_id=launch_id,
        stale_after_seconds=stale_after_seconds,
        now=time.time() - age_seconds,
    )
    hb_result = hb.read_heartbeat(repo, launch_id)
    assert hb_result["class"] == "stale"
    return store_root


# --- refusals R1–R5 -----------------------------------------------------------


def test_refusal_r1_batch_invalid_cli():
    proc = _run_cli([
        "run", "--repo-root", os.getcwd(), "--batch", "   ",
    ])
    out = json.loads(proc.stdout.strip())
    assert proc.returncode == 1
    assert out == {"batchId": "   ", "ok": False, "reason": "batch-invalid"}


def test_refusal_r1_batch_invalid_run(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    result = ww.watch_arm(repo, None)
    assert result["ok"] is False
    assert result["reason"] == "batch-invalid"


def test_refusal_r2_interval_invalid_cli():
    proc = _run_cli([
        "run", "--repo-root", os.getcwd(), "--batch", "b",
        "--interval-seconds", "0",
    ])
    assert proc.returncode == 2


def test_refusal_r2_interval_bool_run(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    result = ww.watch_arm(repo, "batch-982", interval_seconds=True, max_seconds=2)
    assert result["reason"] == "interval-invalid"


def test_refusal_r3_max_seconds_invalid_cli():
    proc = _run_cli([
        "run", "--repo-root", os.getcwd(), "--batch", "b",
        "--max-seconds", "5",
    ])
    assert proc.returncode == 2


def test_refusal_r3_max_seconds_bool_run(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    result = ww.watch_arm(repo, "batch-982", max_seconds=False, interval_seconds=1)
    assert result["reason"] == "max-seconds-invalid"


def test_refusal_r4_repo_root_invalid_cli():
    proc = _run_cli([
        "run", "--repo-root", "/nonexistent/ww-r4", "--batch", "b",
    ])
    out = json.loads(proc.stdout.strip())
    assert proc.returncode == 1
    assert out["reason"] == "repo-root-invalid"
    assert out["batchId"] == "b"


def test_refusal_r5_store_unresolvable(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    result = ww.watch_arm(str(plain), "batch-982", max_seconds=1, interval_seconds=1)
    assert result["ok"] is False
    assert result["reason"] == "store-unresolvable"
    assert result["batchId"] == "batch-982"


def test_refusal_internal_error_on_read_exception(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)

    def raiser(repo_root, env=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(ww.ll, "read", raiser)
    result = ww.watch_arm(repo, "batch-982", max_seconds=1, interval_seconds=1)
    assert result["ok"] is False
    assert result["reason"] == "internal-error"
    assert result["detail"] == "RuntimeError"
    exit_code = ww.main([
        "wave_watch.py", "run", "--repo-root", repo, "--batch", "batch-982",
    ])
    assert exit_code == 1


# --- events E1–E5 -------------------------------------------------------------


def test_event_e1_lane_terminal(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_live_lane(repo, tmp_path, monkeypatch, stamp_state="handback")
    result = ww.watch_arm(repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run)
    assert result["ok"] is True
    assert result["event"] == "lane-terminal"
    assert result["batchId"] == "batch-982"
    assert result["launchId"] == "lane-a"
    assert result["launches"] == [{"launchId": "lane-a", "state": "handback"}]
    assert result["degraded"] == []


def test_event_e2_lane_blocked(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_live_lane(repo, tmp_path, monkeypatch, stamp_state="blocked")
    result = ww.watch_arm(repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run)
    assert result["ok"] is True
    assert result["event"] == "lane-blocked"
    assert result["launchId"] == "lane-a"
    assert result["launches"] == [{"launchId": "lane-a", "state": "blocked"}]


def test_event_e3_builder_exited(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    dead_pid = 999999999
    _setup_live_lane(repo, tmp_path, monkeypatch, pid=dead_pid)
    result = ww.watch_arm(repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run)
    assert result["ok"] is True
    assert result["event"] == "builder-exited"
    assert result["pids"] == [dead_pid]
    assert result["launches"] == [{"launchId": "lane-a", "pid": dead_pid}]


def test_lane_terminal_makes_zero_gh_run_calls(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_live_lane(repo, tmp_path, monkeypatch, stamp_state="handback")
    gh_calls = [0]

    def counting_gh_run(argv, **kwargs):
        gh_calls[0] += 1
        return _noop_gh_run(argv, **kwargs)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=60,
        monotonic=_advancing_monotonic(), sleep=lambda _d: None,
        gh_run=counting_gh_run,
    )
    assert result["event"] == "lane-terminal"
    # axis: no gh child on a tick whose event is a lane event
    assert gh_calls[0] == 0


def test_lane_blocked_makes_zero_gh_run_calls(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_live_lane(repo, tmp_path, monkeypatch, stamp_state="blocked")
    gh_calls = [0]

    def counting_gh_run(argv, **kwargs):
        gh_calls[0] += 1
        return _noop_gh_run(argv, **kwargs)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=60,
        monotonic=_advancing_monotonic(), sleep=lambda _d: None,
        gh_run=counting_gh_run,
    )
    assert result["event"] == "lane-blocked"
    # axis: no gh child on a tick whose event is a lane event
    assert gh_calls[0] == 0


def test_builder_exited_makes_zero_gh_run_calls(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    dead_pid = 999999999
    _setup_live_lane(repo, tmp_path, monkeypatch, pid=dead_pid)
    gh_calls = [0]

    def counting_gh_run(argv, **kwargs):
        gh_calls[0] += 1
        return _noop_gh_run(argv, **kwargs)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=60,
        monotonic=_advancing_monotonic(), sleep=lambda _d: None,
        gh_run=counting_gh_run,
    )
    assert result["event"] == "builder-exited"
    # axis: no gh child on a tick whose event is a lane event
    assert gh_calls[0] == 0


def test_suppressed_terminal_lane_polls_prs_for_pr_set_changed(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_live_lane(
        repo, tmp_path, monkeypatch, stamp_state="handback", pid=os.getpid(),
    )
    pr_list_calls = [0]

    def counting_gh_run(argv, **kwargs):
        if argv[:3] == ["gh", "pr", "list"]:
            pr_list_calls[0] += 1
            body = [{"number": n} for n in [1, 3]]
            return subprocess.CompletedProcess(
                argv, 0, stdout=json.dumps(body), stderr="",
            )
        return _noop_gh_run(argv, **kwargs)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=60,
        monotonic=_advancing_monotonic(), sleep=lambda _d: None,
        gh_run=counting_gh_run,
        pr_state=[{1, 2}],
        ignore_events=(("lane-a", ww.EVENT_LANE_TERMINAL),),
    )
    assert result["event"] == ww.EVENT_PR_SET_CHANGED
    assert result["prs"] == [1, 3]
    assert pr_list_calls[0] == 1


def test_event_e4_pr_set_changed(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    calls = []

    pr_sets = [{1, 2}, {1, 3}]
    idx = [0]

    def gh_run_seq(argv, **kwargs):
        calls.append({"argv": list(argv), "cwd": kwargs.get("cwd")})
        stdout = json.dumps([{"number": n} for n in sorted(pr_sets[idx[0]])])
        idx[0] += 1
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=5, interval_seconds=1,
        gh_run=gh_run_seq,
    )
    assert result["ok"] is True
    assert result["event"] == "pr-set-changed"
    assert result["prs"] == [1, 3]
    assert result["prsAdded"] == [3]
    assert result["prsRemoved"] == [2]
    assert calls[0]["argv"] == [
        "gh", "pr", "list", "--state", "open", "--json", "number", "--limit", "1000",
    ]
    assert calls[0]["cwd"] == repo


def test_event_e5_timer(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run,
    )
    assert result["ok"] is True
    assert result["event"] == "timer"
    assert result["batchId"] == "batch-982"
    assert result["degraded"] == []


# --- fail-closed degradation edges --------------------------------------------


def test_corrupt_ledger_interior_corrupt_refuses_immediately(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 1)
    ll.append(repo, _reserved("lane-a", "batch-982", ["plugins/superheroes/lib"], repo))
    ll.append(repo, _started("lane-a", pid=999999999))
    assert ll.read(repo)["state"] == "ok"
    ledger_file = ll.ledger_path(repo)["path"]
    with open(ledger_file, "ab") as fh:
        fh.write(b"not-valid-json\n")
    assert ll.read(repo)["state"] == "interiorCorrupt"
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=1, interval_seconds=1, gh_run=_noop_gh_run,
    )
    assert result["ok"] is False
    assert result["reason"] == ww.REFUSAL_LEDGER_UNREADABLE


def test_torn_tail_ledger_still_detects_builder_exited(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    dead_pid = 999999999
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 1)
    ll.append(repo, _reserved("lane-a", "batch-982", ["plugins/superheroes/lib"], repo))
    ll.append(repo, _started("lane-a", pid=dead_pid))
    ledger_file = ll.ledger_path(repo)["path"]
    with open(ledger_file, "ab") as fh:
        fh.write(b'{"event":"started"')
    assert ll.read(repo)["state"] == "tornTail"
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run,
    )
    assert result["event"] == "builder-exited"
    assert result["pids"] == [dead_pid]
    assert ww.DEGRADATION_LEDGER_TORN_TAIL in result["degraded"]
    assert ww.DEGRADATION_LEDGER_UNREADABLE not in result["degraded"]


def test_corrupt_heartbeat_dead_pid_emits_builder_exited_with_degradation(
    tmp_path, monkeypatch,
):
    repo = _init_repo(tmp_path / "repo")
    launch_id = "lane-a"
    dead_pid = 777777777
    _setup_live_lane(
        repo, tmp_path, monkeypatch, launch_id=launch_id, pid=dead_pid,
        stamp_state="working",
    )
    hb_path = hb.heartbeat_path(repo, launch_id)["path"]
    with open(hb_path, "wb") as fh:
        fh.write(b"not json")
    hb_result = hb.read_heartbeat(repo, launch_id)
    assert hb_result["class"] == "unknown"
    assert hb_result["reason"] != ww.REASON_HEARTBEAT_MISSING
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run,
    )
    assert result["event"] == "builder-exited"
    assert result["pids"] == [dead_pid]
    assert ww.DEGRADATION_HEARTBEAT_UNREADABLE in result["degraded"]


def test_corrupt_heartbeat_emits_timer_degraded(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    launch_id = "lane-a"
    _setup_live_lane(
        repo, tmp_path, monkeypatch, launch_id=launch_id, pid=os.getpid(),
        stamp_state="working",
    )
    hb_path = hb.heartbeat_path(repo, launch_id)["path"]
    with open(hb_path, "wb") as fh:
        fh.write(b"not json")
    hb_result = hb.read_heartbeat(repo, launch_id)
    assert hb_result["class"] == "unknown"
    assert hb_result["reason"] != "heartbeat-missing"
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=1, interval_seconds=1, gh_run=_noop_gh_run,
    )
    assert result["event"] == "timer"
    assert ww.DEGRADATION_HEARTBEAT_UNREADABLE in result["degraded"]


def test_ledger_unreadable_refuses_at_timer_when_still_unreadable(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 1)
    ll.append(repo, _reserved("lane-a", "batch-982", ["plugins/superheroes/lib"], repo))
    ll.append(repo, _started("lane-a", pid=os.getpid()))
    assert ll.read(repo)["state"] == "ok"
    real_read = ll.read
    calls = [0]
    clock = [0.0]

    def flaky_read(repo_root, env=None):
        calls[0] += 1
        if calls[0] >= 3:
            return {"state": "unreadable", "records": []}
        return real_read(repo_root, env=env)

    monkeypatch.setattr(ww.ll, "read", flaky_read)

    def mono():
        return clock[0]

    def fake_sleep(duration):
        clock[0] += duration

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=1,
        monotonic=_with_loop_budget(mono), sleep=fake_sleep, gh_run=_noop_gh_run,
    )
    assert result["ok"] is False
    assert result["reason"] == ww.REFUSAL_LEDGER_UNREADABLE
    assert clock[0] >= 2.0


def test_ledger_transient_unreadable_then_readable_emits_timer_degraded(
    tmp_path, monkeypatch,
):
    repo = _init_repo(tmp_path / "repo")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 1)
    ll.append(repo, _reserved("lane-a", "batch-982", ["plugins/superheroes/lib"], repo))
    ll.append(repo, _started("lane-a", pid=os.getpid()))
    real_read = ll.read
    calls = [0]

    def flaky_read(repo_root, env=None):
        calls[0] += 1
        if calls[0] == 2:
            return {"state": "unreadable", "records": []}
        return real_read(repo_root, env=env)

    monkeypatch.setattr(ww.ll, "read", flaky_read)
    clock = [0.0]

    def mono():
        return clock[0]

    def fake_sleep(duration):
        clock[0] += duration

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=1,
        monotonic=_with_loop_budget(mono), sleep=fake_sleep, gh_run=_noop_gh_run,
    )
    assert result["ok"] is True
    assert result["event"] == "timer"
    assert ww.DEGRADATION_LEDGER_UNREADABLE in result["degraded"]


def test_first_interval_unreadable_refuses_immediately(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    clock = [0.0]

    def mono():
        return clock[0]

    def fake_sleep(duration):
        clock[0] += duration

    def unreadable_read(repo_root, env=None):
        return {"state": "unreadable", "records": []}

    monkeypatch.setattr(ww.ll, "read", unreadable_read)
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2400, interval_seconds=60,
        monotonic=mono, sleep=fake_sleep, gh_run=_noop_gh_run,
    )
    assert result["ok"] is False
    assert result["reason"] == ww.REFUSAL_LEDGER_UNREADABLE
    assert clock[0] < 1.0


def test_fold_failure_refuses_on_first_interval(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 1)
    ll.append(repo, _reserved("lane-a", "batch-982", ["plugins/superheroes/lib"], repo))
    ll.append(repo, {"not": "a-valid-record"})
    assert ll.read(repo)["state"] == "ok"
    real_fold = ll.fold

    def bad_fold(records):
        return {"ok": False, "reason": "fold-not-an-object", "launches": {},
                "batchDeclarations": {}}

    monkeypatch.setattr(ww.ll, "fold", bad_fold)
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=1, gh_run=_noop_gh_run,
    )
    assert result["ok"] is False
    assert result["reason"] == ww.REFUSAL_LEDGER_UNREADABLE
    monkeypatch.setattr(ww.ll, "fold", real_fold)


def test_unrecognized_ledger_state_refuses_on_first_interval(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)

    def bogus_read(repo_root, env=None):
        return {"state": "future-state", "records": []}

    monkeypatch.setattr(ww.ll, "read", bogus_read)
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=1, gh_run=_noop_gh_run,
    )
    assert result["ok"] is False
    assert result["reason"] == ww.REFUSAL_LEDGER_UNREADABLE


def test_missing_ledger_never_observed_emits_timer(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=1, interval_seconds=1, gh_run=_noop_gh_run,
    )
    assert result["ok"] is True
    assert result["event"] == "timer"
    assert "reason" not in result


def test_observed_then_missing_refuses_at_deadline(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 1)
    ll.append(repo, _reserved("lane-a", "batch-982", ["plugins/superheroes/lib"], repo))
    ll.append(repo, _started("lane-a", pid=os.getpid()))
    assert ll.read(repo)["state"] == "ok"
    real_read = ll.read
    calls = [0]
    clock = [0.0]

    def flaky_read(repo_root, env=None):
        calls[0] += 1
        if calls[0] >= 2:
            return {"state": "missing", "records": []}
        return real_read(repo_root, env=env)

    monkeypatch.setattr(ww.ll, "read", flaky_read)

    def mono():
        return clock[0]

    def fake_sleep(duration):
        clock[0] += duration

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=1,
        monotonic=_with_loop_budget(mono), sleep=fake_sleep, gh_run=_noop_gh_run,
    )
    assert result["ok"] is False
    assert result["reason"] == ww.REFUSAL_LEDGER_UNREADABLE


def test_deadline_blind_on_final_read_refuses_not_timer(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 1)
    assert ll.read(repo)["state"] == "ok"
    real_read = ll.read
    read_calls = [0]
    clock = [0.0]

    def flaky_read(repo_root, env=None):
        read_calls[0] += 1
        if read_calls[0] >= 2:
            return {"state": "unreadable", "records": []}
        return real_read(repo_root, env=env)

    monkeypatch.setattr(ww.ll, "read", flaky_read)

    def mono():
        return clock[0]

    def fake_sleep(duration):
        clock[0] += duration

    def gh_advance(argv, **kwargs):
        clock[0] = 3.0
        return _noop_gh_run(argv, **kwargs)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=1,
        monotonic=mono, sleep=fake_sleep, gh_run=gh_advance,
    )
    assert result["ok"] is False
    assert result["reason"] == ww.REFUSAL_LEDGER_UNREADABLE


# --- lane-stale (INV-2) -------------------------------------------------------


def test_lane_stale_working_state_with_live_pid(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_stale_lane(repo, tmp_path, monkeypatch, stamp_state="working")
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run,
    )
    assert result["ok"] is True
    assert result["event"] == "lane-stale"
    assert result["launchId"] == "lane-a"
    assert result["launches"][0]["launchId"] == "lane-a"
    assert result["launches"][0]["state"] == "working"
    assert result["launches"][0]["ageSeconds"] is not None
    assert result["launches"][0]["staleAfterSeconds"] == 1


def test_lane_stale_awaiting_dispatch_state_with_live_pid(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_stale_lane(repo, tmp_path, monkeypatch, stamp_state="awaiting-dispatch")
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run,
    )
    assert result["event"] == "lane-stale"
    assert result["launches"][0]["state"] == "awaiting-dispatch"


def test_stale_heartbeat_pid_uncertain_no_lane_stale(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_stale_lane(repo, tmp_path, monkeypatch)

    def raiser(pid, sig):
        raise OSError("probe failed")

    monkeypatch.setattr(ww.os, "kill", raiser)
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=1, interval_seconds=1, gh_run=_noop_gh_run,
    )
    assert result["event"] == "timer"
    assert result["event"] != "lane-stale"
    assert ww.DEGRADATION_PID_PROBE_UNCERTAIN in result["degraded"]


def test_stale_heartbeat_dead_pid_emits_builder_exited_not_lane_stale(
    tmp_path, monkeypatch,
):
    repo = _init_repo(tmp_path / "repo")
    dead_pid = 999999999
    _setup_stale_lane(repo, tmp_path, monkeypatch, pid=dead_pid)
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run,
    )
    assert result["event"] == "builder-exited"
    assert result["event"] != "lane-stale"
    assert result["pids"] == [dead_pid]
    also_observed = result.get("alsoObserved")
    if also_observed is not None:
        assert "stale" not in also_observed


def test_dead_pid_stale_heartbeat_not_in_stale_live(monkeypatch):
    live_lanes = {
        "lane-a": {"started": True, "pid": 999999999, "batchId": "batch-982"},
    }
    stale_launches = [{
        "launchId": "lane-a",
        "state": "working",
        "ageSeconds": 60.0,
        "staleAfterSeconds": 1,
    }]
    monkeypatch.setattr(ww, "_pid_is_live", lambda pid: False)
    degraded = set()
    exited, stale_live = ww._evaluate_pid_signals(
        live_lanes, stale_launches, degraded,
    )
    assert stale_live == []
    assert exited is not None
    pids, exited_launches = exited
    assert pids == [999999999]
    assert exited_launches == [{"launchId": "lane-a", "pid": 999999999}]


def test_lane_never_stamped_emits_timer_not_lane_stale(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 1)
    ll.append(repo, _reserved("lane-a", "batch-982", ["plugins/superheroes/lib"], repo))
    ll.append(repo, _started("lane-a", pid=os.getpid()))
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=1, interval_seconds=1, gh_run=_noop_gh_run,
    )
    assert result["event"] == "timer"
    assert result["event"] != "lane-stale"
    assert ww.DEGRADATION_LANE_NEVER_STAMPED in result["degraded"]


def test_stale_heartbeat_not_started_no_lane_stale(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 1)
    ll.append(repo, _reserved("lane-a", "batch-982", ["plugins/superheroes/lib"], repo))
    hb.stamp(
        repo,
        state="working",
        phase="watch",
        launch_id="lane-a",
        stale_after_seconds=1,
        now=time.time() - 60,
    )
    hb_result = hb.read_heartbeat(repo, "lane-a")
    assert hb_result["class"] == "stale"
    original_derive = ww._derive_batch_lanes

    def derive_with_unstarted_pid(*args, **kwargs):
        batch_lanes, live, readable = original_derive(*args, **kwargs)
        assert "lane-a" in live, "derive injection silently skipped"
        live = dict(live)
        live["lane-a"] = dict(live["lane-a"])
        live["lane-a"]["pid"] = os.getpid()
        assert not live["lane-a"].get("started")
        return batch_lanes, live, readable

    monkeypatch.setattr(ww, "_derive_batch_lanes", derive_with_unstarted_pid)
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=1, interval_seconds=1, gh_run=_noop_gh_run,
    )
    assert result["event"] == "timer"
    assert result["event"] != "lane-stale"


def test_lane_never_stamped_not_latched_when_stamp_arrives_on_tick_two(
    tmp_path, monkeypatch, watcher_clock,
):
    repo = _init_repo(tmp_path / "repo")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 1)
    ll.append(repo, _reserved("lane-a", "batch-982", ["plugins/superheroes/lib"], repo))
    ll.append(repo, _started("lane-a", pid=os.getpid()))
    stamped = [False]

    def sleep_fn(duration):
        if not stamped[0]:
            hb.stamp(
                repo,
                state="working",
                phase="watch",
                launch_id="lane-a",
                stale_after_seconds=3600,
            )
            stamped[0] = True
        watcher_clock.sleep(duration)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=1,
        sleep=sleep_fn, gh_run=_noop_gh_run,
    )
    assert result["event"] == "timer"
    assert ww.DEGRADATION_LANE_NEVER_STAMPED not in result["degraded"]


def test_os_kill_uses_signal_zero_only(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_live_lane(repo, tmp_path, monkeypatch, pid=os.getpid(), stamp_state="working")
    recorded = []
    original_kill = os.kill

    def record_kill(pid, sig):
        recorded.append((pid, sig))
        return original_kill(pid, sig)

    monkeypatch.setattr(ww.os, "kill", record_kill)
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=1, interval_seconds=1, gh_run=_noop_gh_run,
    )
    assert result["event"] == "timer"
    assert recorded
    assert all(sig == 0 for _pid, sig in recorded)


def test_stale_heartbeat_invalid_pid_no_lane_stale():
    live_lanes = {
        "lane-a": {"started": True, "pid": 0, "batchId": "batch-982"},
    }
    stale_launches = [{
        "launchId": "lane-a",
        "state": "working",
        "ageSeconds": 60.0,
        "staleAfterSeconds": 1,
    }]
    degraded = set()
    exited, stale_live = ww._evaluate_pid_signals(
        live_lanes, stale_launches, degraded,
    )
    assert exited is None
    assert stale_live == []


def test_blocked_and_stale_emits_lane_blocked_not_lane_stale(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_stale_lane(repo, tmp_path, monkeypatch, stamp_state="blocked")
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run,
    )
    assert result["event"] == "lane-blocked"
    assert result["event"] != "lane-stale"


def test_ignore_launch_suppresses_stale_lane(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_stale_lane(repo, tmp_path, monkeypatch)
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=60,
        ignore_launch_ids=("lane-a",), gh_run=_noop_gh_run,
    )
    assert result["event"] == "timer"
    assert result["event"] != "lane-stale"


def test_precedence_pr_set_changed_beats_lane_stale(tmp_path, monkeypatch, watcher_clock):
    repo = _init_repo(tmp_path / "repo")
    _setup_live_lane(
        repo, tmp_path, monkeypatch, pid=os.getpid(), stamp_state="working",
    )
    pr_sets = [{1}, {1, 2}]
    idx = [0]

    def gh_run_seq(argv, **kwargs):
        stdout = json.dumps([{"number": n} for n in sorted(pr_sets[idx[0]])])
        idx[0] += 1
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    def sleep_fn(duration):
        hb.stamp(
            repo,
            state="working",
            phase="watch",
            launch_id="lane-a",
            stale_after_seconds=1,
            now=time.time() - 60,
        )
        watcher_clock.sleep(duration)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=5, interval_seconds=1,
        gh_run=gh_run_seq, sleep=sleep_fn,
    )
    assert result["event"] == "pr-set-changed"
    assert result["event"] != "lane-stale"
    assert result["alsoObserved"] == {"stale": ["lane-a"]}


def test_precedence_builder_exited_beats_lane_stale(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    dead_pid = 888888888
    live_pid = os.getpid()
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 2)
    ll.append(repo, _reserved("lane-dead", "batch-982", ["plugins/superheroes/lib"], repo))
    ll.append(repo, _started("lane-dead", pid=dead_pid))
    ll.append(repo, _reserved("lane-stale", "batch-982", ["plugins/superheroes/lib"], repo))
    ll.append(repo, _started("lane-stale", pid=live_pid))
    hb.stamp(
        repo,
        state="working",
        phase="watch",
        launch_id="lane-stale",
        stale_after_seconds=1,
        now=time.time() - 60,
    )
    assert hb.read_heartbeat(repo, "lane-stale")["class"] == "stale"
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run,
    )
    assert result["event"] == "builder-exited"
    assert result["event"] != "lane-stale"
    assert result["pids"] == [dead_pid]
    assert result["alsoObserved"] == {"stale": ["lane-stale"]}


def test_stale_token_pin_in_sweep_classes():
    assert ww.HB_CLASS_STALE in hb.SWEEP_CLASSES


def test_pid_probe_uncertain_emits_timer_not_builder_exited(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_live_lane(repo, tmp_path, monkeypatch, pid=os.getpid())

    def raiser(pid, sig):
        raise OSError("probe failed")

    monkeypatch.setattr(ww.os, "kill", raiser)
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=1, interval_seconds=1, gh_run=_noop_gh_run,
    )
    assert result["event"] == "timer"
    assert "pid-probe-uncertain" in result["degraded"]
    assert result["event"] != "builder-exited"


def test_pid_is_live_all_branches(monkeypatch):
    assert ww._pid_is_live(os.getpid()) is True
    assert ww._pid_is_live(999999999) is False
    assert ww._pid_is_live(0) is None
    assert ww._pid_is_live(-1) is None
    assert ww._pid_is_live(None) is None
    assert ww._pid_is_live(True) is None

    def permission_error(pid, sig):
        raise PermissionError()

    monkeypatch.setattr(ww.os, "kill", permission_error)
    assert ww._pid_is_live(999999999) is True

    def os_error(pid, sig):
        raise OSError()

    monkeypatch.setattr(ww.os, "kill", os_error)
    assert ww._pid_is_live(12345) is None


# --- acceptance paths ---------------------------------------------------------


def test_acceptance_pid_exit(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    dead = 888888888
    _setup_live_lane(repo, tmp_path, monkeypatch, pid=dead)
    result = ww.watch_arm(repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run)
    assert result["event"] == "builder-exited"
    assert result["pids"] == [dead]


def test_acceptance_heartbeat_flip(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_live_lane(repo, tmp_path, monkeypatch, stamp_state="parked")
    result = ww.watch_arm(repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run)
    assert result["event"] == "lane-terminal"
    assert result["launches"][0]["state"] == "parked"


def test_acceptance_pr_set_change_mocked_gh(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    seen = [0]

    def gh_run(argv, **kwargs):
        seen[0] += 1
        if seen[0] == 1:
            body = [{"number": 10}]
        else:
            body = [{"number": 10}, {"number": 11}]
        return subprocess.CompletedProcess(
            argv, 0, stdout=json.dumps(body), stderr="",
        )

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=4, interval_seconds=1, gh_run=gh_run,
    )
    assert result["event"] == "pr-set-changed"
    assert result["prsAdded"] == [11]


def test_acceptance_timer(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=1, interval_seconds=10, gh_run=_noop_gh_run,
    )
    assert result["event"] == "timer"


def test_precedence_terminal_beats_builder_exited(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    dead = 777777777
    _setup_live_lane(repo, tmp_path, monkeypatch, pid=dead, stamp_state="handback")
    result = ww.watch_arm(repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run)
    assert result["event"] == "lane-terminal"
    assert result["event"] != "builder-exited"


def test_event_precedence_matches_docstring():
    doc = ww.__doc__
    assert "lane-terminal (E1) > lane-blocked (E2) > builder-exited (E3) >" in doc
    assert "stack-state-changed (E4) > pr-set-changed (E5) > lane-stale (E6) > timer (E7)" in doc
    assert ww.EVENT_PRECEDENCE == (
        ww.EVENT_LANE_TERMINAL,
        ww.EVENT_LANE_BLOCKED,
        ww.EVENT_BUILDER_EXITED,
        ww.EVENT_STACK_STATE_CHANGED,
        ww.EVENT_PR_SET_CHANGED,
        ww.EVENT_LANE_STALE,
        ww.EVENT_TIMER,
    )


def test_terminal_state_handling_consistent_with_heartbeat_terminal_states():
    for state in hb.TERMINAL_STATES:
        assert state in hb.STATES
    assert ww.HB_CLASS_TERMINAL in hb.SWEEP_CLASSES


def test_also_observed_carries_co_occurring_blocked_lane(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 2)
    ll.append(repo, _reserved("lane-a", "batch-982", ["plugins/superheroes/lib"], repo))
    ll.append(repo, _started("lane-a", pid=os.getpid()))
    hb.stamp(
        repo, state="handback", phase="watch", launch_id="lane-a",
        stale_after_seconds=3600,
    )
    ll.append(repo, _reserved("lane-b", "batch-982", ["plugins/superheroes/lib"], repo))
    ll.append(repo, _started("lane-b", pid=os.getpid()))
    hb.stamp(
        repo, state="blocked", phase="watch", launch_id="lane-b",
        stale_after_seconds=3600,
    )
    result = ww.watch_arm(repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run)
    assert result["event"] == "lane-terminal"
    assert result["launchId"] == "lane-a"
    assert result["alsoObserved"] == {"blocked": ["lane-b"]}


def test_ignore_launch_suppresses_lane_event(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    dead = 777777777
    _setup_live_lane(repo, tmp_path, monkeypatch, pid=dead, stamp_state="handback")
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=60,
        ignore_launch_ids=("lane-a",), gh_run=_noop_gh_run,
    )
    assert result["event"] == "timer"


def test_ignore_launch_cli_flag(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    dead = 777777777
    _setup_live_lane(repo, tmp_path, monkeypatch, pid=dead, stamp_state="handback")
    proc = _run_cli([
        "run", "--repo-root", repo, "--batch", "batch-982",
        "--ignore-launch", "lane-a",
    ], env=_fake_gh_cli_env(tmp_path))
    assert proc.returncode == 0
    out = json.loads(proc.stdout.strip())
    assert out["event"] == "timer"


# --- lane-blocked vs working --------------------------------------------------


def test_working_lane_fires_nothing(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_live_lane(repo, tmp_path, monkeypatch, pid=os.getpid(), stamp_state="working")
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=1, interval_seconds=1, gh_run=_noop_gh_run,
    )
    assert result["event"] == "timer"


# --- mid-watch launch ---------------------------------------------------------


def test_mid_watch_launch_detected_within_one_interval(tmp_path, monkeypatch, watcher_clock):
    repo = _init_repo(tmp_path / "repo")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 2)
    dead = 666666666

    def sleep_fn(duration):
        ll.append(repo, _reserved("lane-late", "batch-982", ["plugins/superheroes/lib"], repo))
        ll.append(repo, _started("lane-late", pid=dead))
        watcher_clock.sleep(duration)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=3, interval_seconds=1,
        sleep=sleep_fn, gh_run=_noop_gh_run,
    )
    assert result["event"] == "builder-exited"
    assert result["launches"][0]["launchId"] == "lane-late"
    assert result["pids"] == [dead]


# --- batch isolation ----------------------------------------------------------


def test_batch_isolation_other_batch_never_produces_event(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 1)
    ll.declare_batch(repo, "batch-other", 1)
    dead = 555555555
    ll.append(repo, _reserved("lane-other", "batch-other", ["plugins/superheroes/lib"], repo))
    ll.append(repo, _started("lane-other", pid=dead))
    result = ww.watch_arm(repo, "batch-982", max_seconds=1, interval_seconds=1, gh_run=_noop_gh_run)
    assert result["event"] == "timer"


# --- reserved never started / retried lane ------------------------------------


def test_reserved_never_started_no_event(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 1)
    ll.append(repo, _reserved("lane-b", "batch-982", ["plugins/superheroes/lib"], repo))
    result = ww.watch_arm(repo, "batch-982", max_seconds=1, interval_seconds=1, gh_run=_noop_gh_run)
    assert result["event"] == "timer"


def test_retried_lane_old_pid_dead_latest_live_no_event(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 1)
    launch_id = "lane-a"
    ll.append(repo, _reserved(launch_id, "batch-982", ["plugins/superheroes/lib"], repo))
    ll.append(repo, _started(launch_id, attempt=1, pid=444444444))
    ll.append(repo, _retry(launch_id, attempt=2))
    ll.append(repo, _started(launch_id, attempt=2, pid=os.getpid()))
    result = ww.watch_arm(repo, "batch-982", max_seconds=1, interval_seconds=1, gh_run=_noop_gh_run)
    assert result["event"] == "timer"


# --- PR set behaviour ---------------------------------------------------------


def test_pr_identical_set_no_event(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)

    def gh_run(argv, **kwargs):
        body = [{"number": 1}, {"number": 2}]
        return subprocess.CompletedProcess(
            argv, 0, stdout=json.dumps(body), stderr="",
        )

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=3, interval_seconds=1, gh_run=gh_run,
    )
    assert result["event"] == "timer"


def test_pr_same_tick_open_close_fires(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    sets = [{1, 2}, {1, 3}]
    idx = [0]

    def gh_run(argv, **kwargs):
        body = [{"number": n} for n in sorted(sets[idx[0]])]
        idx[0] += 1
        return subprocess.CompletedProcess(
            argv, 0, stdout=json.dumps(body), stderr="",
        )

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=4, interval_seconds=1, gh_run=gh_run,
    )
    assert result["event"] == "pr-set-changed"
    assert result["prsRemoved"] == [2]
    assert result["prsAdded"] == [3]


# --- gh failure ---------------------------------------------------------------


def test_gh_exception_adds_degradation_no_event(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)

    def gh_run(argv, **kwargs):
        raise OSError("gh missing")

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=1, gh_run=gh_run,
    )
    assert result["event"] == "timer"
    assert "pr-signal-unavailable" in result["degraded"]


def test_gh_nonzero_exit_adds_degradation_no_event(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)

    def gh_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="fail")

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=1, gh_run=gh_run,
    )
    assert result["event"] == "timer"
    assert "pr-signal-unavailable" in result["degraded"]


def test_gh_bad_json_adds_degradation_no_event(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)

    def gh_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout="not-json", stderr="")

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=1, gh_run=gh_run,
    )
    assert result["event"] == "timer"
    assert "pr-signal-unavailable" in result["degraded"]


def test_gh_first_failure_then_success_baselines(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    calls = [0]

    def gh_run(argv, **kwargs):
        calls[0] += 1
        if calls[0] == 1:
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="")
        body = [{"number": 5}]
        return subprocess.CompletedProcess(
            argv, 0, stdout=json.dumps(body), stderr="",
        )

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=3, interval_seconds=1, gh_run=gh_run,
    )
    assert result["event"] == "timer"
    assert "pr-signal-unavailable" in result["degraded"]
    assert calls[0] >= 2


# --- deadline -----------------------------------------------------------------


def test_deadline_timer_without_overshoot(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    clock = [100.0]
    sleeps = []

    def mono():
        return clock[0]

    def fake_sleep(duration):
        sleeps.append(duration)
        clock[0] += duration

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=5, interval_seconds=60,
        monotonic=_with_loop_budget(mono), sleep=fake_sleep, gh_run=_noop_gh_run,
    )
    assert result["event"] == "timer"
    assert clock[0] == 105.0
    assert sleeps == [5.0]
    assert all(s <= 5.0 for s in sleeps)


def test_max_seconds_shorter_than_interval_evaluates_once_then_timer(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    clock = [0.0]

    def mono():
        return clock[0]

    def fake_sleep(duration):
        clock[0] += duration

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=60,
        monotonic=_with_loop_budget(mono), sleep=fake_sleep, gh_run=_noop_gh_run,
    )
    assert result["event"] == "timer"
    assert clock[0] == 2.0


# --- read-only ----------------------------------------------------------------


def _snapshot_files(root):
    snap = {}
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            path = os.path.join(dirpath, name)
            with open(path, "rb") as fh:
                snap[path] = (fh.read(), os.path.getmtime(path))
    return snap


def test_read_only_no_store_files_changed(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    store_root = _ledger_env(tmp_path, monkeypatch)
    repo_id = _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 1)
    ll.append(repo, _reserved("lane-a", "batch-982", ["plugins/superheroes/lib"], repo))
    ll.append(repo, _started("lane-a", pid=os.getpid()))
    hb.stamp(
        repo,
        state="working",
        phase="watch",
        launch_id="lane-a",
        stale_after_seconds=3600,
    )
    before = _snapshot_files(store_root)
    before_paths = set(before.keys())
    ww.watch_arm(repo, "batch-982", max_seconds=1, interval_seconds=1, gh_run=_noop_gh_run)
    after = _snapshot_files(store_root)
    assert set(after.keys()) == before_paths
    assert before == after
    assert not any(
        p.endswith(ll.LEDGER_NAME + _LEDGER_LOCK_SUFFIX) for p in after
    )


# --- gh environment and deadline ------------------------------------------------


def test_gh_child_receives_supplied_env(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    custom_env = dict(os.environ)
    custom_env["WW_TEST_MARKER"] = "reaches-gh-child"
    seen = []

    def gh_run(argv, **kwargs):
        seen.append(kwargs.get("env"))
        return _noop_gh_run(argv, **kwargs)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=1,
        env=custom_env, gh_run=gh_run,
    )
    assert result["event"] == "timer"
    assert len(seen) >= 1
    assert seen[0]["WW_TEST_MARKER"] == "reaches-gh-child"


# Literal list, deliberately NOT read from ww._GH_SCRUB_VARS: a name removed from
# the module tuple must turn exactly its own test red, never silently shrink coverage.
_EXPECTED_SCRUBBED = [
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CEILING_DIRECTORIES",
    "GH_REPO",
    "GIT_CONFIG",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_SYSTEM",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_PARAMETERS",
]


# GIT_CONFIG_COUNT/PARAMETERS must be VALID for git (any git the un-scrubbed env
# reaches chokes on malformed values before the scrub assertion runs); the test's
# point is scrub-presence, not value validity.
_SCRUB_PROBE_VALUES = {
    "GIT_CONFIG_COUNT": "0",
    "GIT_CONFIG_PARAMETERS": "'wavewatch.probe=1'",
}


@pytest.mark.parametrize("var", _EXPECTED_SCRUBBED)
def test_gh_child_env_scrubs_routing_var(tmp_path, monkeypatch, var):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    custom_env = dict(os.environ)
    custom_env[var] = _SCRUB_PROBE_VALUES.get(var, "/definitely/not/right")
    seen = []

    def gh_run(argv, **kwargs):
        seen.append(kwargs.get("env"))
        return _noop_gh_run(argv, **kwargs)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=1,
        env=custom_env, gh_run=gh_run,
    )
    assert result["event"] == "timer"
    assert len(seen) >= 1
    assert var not in seen[0]


def test_gh_child_env_preserves_auth_vars(tmp_path, monkeypatch):
    """GH_TOKEN / GH_CONFIG_DIR must survive the scrub — stripping them breaks gh auth."""
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    custom_env = dict(os.environ)
    custom_env["GH_TOKEN"] = "test-token-value"
    custom_env["GH_CONFIG_DIR"] = "/some/config/dir"
    seen = []

    def gh_run(argv, **kwargs):
        seen.append(kwargs.get("env"))
        return _noop_gh_run(argv, **kwargs)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=1,
        env=custom_env, gh_run=gh_run,
    )
    assert result["event"] == "timer"
    assert seen[0].get("GH_TOKEN") == "test-token-value"
    assert seen[0].get("GH_CONFIG_DIR") == "/some/config/dir"


def test_at_deadline_skips_gh_no_degradation(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    calls = []
    mono_calls = [0]

    def mono():
        mono_calls[0] += 1
        if mono_calls[0] == 1:
            return 0.0
        return 1.0

    def gh_run(argv, **kwargs):
        calls.append(True)
        return _noop_gh_run(argv, **kwargs)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=1, interval_seconds=60,
        monotonic=_with_loop_budget(mono), sleep=lambda d: None, gh_run=gh_run,
    )
    assert result["event"] == "timer"
    assert calls == []
    assert ww.DEGRADATION_PR_SIGNAL_UNAVAILABLE not in result["degraded"]


def test_pr_change_after_deadline_not_returned(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    clock = [0.0]
    calls = [0]

    def mono():
        return clock[0]

    def fake_sleep(duration):
        clock[0] += duration

    def gh_run(argv, **kwargs):
        calls[0] += 1
        if calls[0] == 1:
            body = [{"number": 1}]
        else:
            body = [{"number": 1}, {"number": 99}]
        return subprocess.CompletedProcess(
            argv, 0, stdout=json.dumps(body), stderr="",
        )

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=1, interval_seconds=1,
        monotonic=_with_loop_budget(mono), sleep=fake_sleep, gh_run=gh_run,
    )
    assert result["event"] == "timer"
    assert result["event"] != "pr-set-changed"
    assert calls[0] == 1


def test_gh_timeout_never_exceeds_remaining(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    clock = [0.0]
    timeouts = []

    def mono():
        return clock[0]

    def fake_sleep(duration):
        clock[0] += duration

    def gh_run(argv, **kwargs):
        timeouts.append(kwargs.get("timeout"))
        return _noop_gh_run(argv, **kwargs)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=3, interval_seconds=1,
        monotonic=_with_loop_budget(mono), sleep=fake_sleep, gh_run=gh_run,
    )
    assert result["event"] == "timer"
    assert len(timeouts) >= 1
    for idx, timeout in enumerate(timeouts):
        remaining_at_call = 3.0 - (idx * 1.0)
        assert timeout <= remaining_at_call
        assert timeout <= 30


def test_first_tick_slow_scans_skip_gh_poll_without_overrun(tmp_path, monkeypatch):
    """First-tick scans must not inflate poll budget when remaining is sub-floor."""
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    max_seconds = 2
    scan_cost = 1.95
    clock = [0.0]
    gh_calls = []
    derive_calls = [0]
    original_derive = ww._derive_batch_lanes

    def slow_derive(*args, **kwargs):
        derive_calls[0] += 1
        if derive_calls[0] == 1:
            clock[0] += scan_cost
        return original_derive(*args, **kwargs)

    monkeypatch.setattr(ww, "_derive_batch_lanes", slow_derive)

    def mono():
        return clock[0]

    def fake_sleep(duration):
        clock[0] += duration

    def gh_run(argv, **kwargs):
        gh_calls.append(kwargs.get("timeout"))
        return _noop_gh_run(argv, **kwargs)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=max_seconds, interval_seconds=60,
        monotonic=mono, sleep=fake_sleep, gh_run=gh_run,
    )
    assert result["event"] == "timer"
    assert gh_calls == []
    assert clock[0] <= max_seconds


def test_gh_poll_budget_computed_after_scans(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    clock = [0.0]
    scan_cost = 1.5
    timeouts = []
    original_derive = ww._derive_batch_lanes

    def slow_derive(*args, **kwargs):
        clock[0] += scan_cost
        return original_derive(*args, **kwargs)

    monkeypatch.setattr(ww, "_derive_batch_lanes", slow_derive)

    def mono():
        return clock[0]

    def gh_run(argv, **kwargs):
        timeouts.append(kwargs.get("timeout"))
        return _noop_gh_run(argv, **kwargs)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=3, interval_seconds=60,
        monotonic=mono, sleep=lambda d: None, gh_run=gh_run,
    )
    assert result["event"] == "timer"
    assert len(timeouts) >= 1
    assert timeouts[0] <= 3.0 - scan_cost + 0.01
    assert timeouts[0] < 3.0


def test_gh_timeout_ceiling_thirty_when_remaining_large(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    clock = [0.0]
    timeouts = []

    def mono():
        return clock[0]

    def fake_sleep(duration):
        clock[0] += duration

    def gh_run(argv, **kwargs):
        timeouts.append(kwargs.get("timeout"))
        return _noop_gh_run(argv, **kwargs)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=35, interval_seconds=60,
        monotonic=mono, sleep=fake_sleep, gh_run=gh_run,
    )
    assert result["event"] == "timer"
    assert timeouts == [30.0]


def test_gh_poll_spacing_skips_missed_ticks(tmp_path, monkeypatch):
    """Missed ticks must not replay back-to-back; spacing comes from the scheduler."""
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    clock = [0.0]
    gh_starts = []
    interval_seconds = 3
    gh_calls = [0]

    def mono():
        return clock[0]

    def fake_sleep(duration):
        clock[0] += duration

    def paced_gh_run(argv, **kwargs):
        gh_starts.append(clock[0])
        gh_calls[0] += 1
        # First poll outruns the interval; later polls are fast so gaps
        # after a replay bug collapse to gh cost, not interval spacing.
        gh_cost = 7.0 if gh_calls[0] == 1 else 1.0
        clock[0] += gh_cost
        return _noop_gh_run(argv, **kwargs)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=15, interval_seconds=interval_seconds,
        monotonic=mono, sleep=fake_sleep, gh_run=paced_gh_run,
    )
    assert result["event"] == "timer"
    assert len(gh_starts) >= 3
    for idx in range(1, len(gh_starts)):
        gap = gh_starts[idx] - gh_starts[idx - 1]
        assert gap >= interval_seconds


def test_sub_floor_remaining_skips_gh_no_pr_degradation(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    calls = []
    clock = [0.0]
    timeouts = []

    def mono():
        return clock[0]

    sleeps = [0]

    def fake_sleep(duration):
        sleeps[0] += 1
        clock[0] = 1.9 if sleeps[0] == 1 else 2.0

    def gh_run(argv, **kwargs):
        calls.append(True)
        timeouts.append(kwargs.get("timeout"))
        return _noop_gh_run(argv, **kwargs)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=1,
        monotonic=mono, sleep=fake_sleep, gh_run=gh_run,
    )
    assert result["event"] == "timer"
    assert timeouts == [2.0]
    assert calls == [True]
    assert ww.DEGRADATION_PR_SIGNAL_UNAVAILABLE not in result["degraded"]


def test_all_skipped_gh_polls_add_pr_signal_never_sampled(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    calls = []
    mono_calls = [0]

    def mono():
        mono_calls[0] += 1
        if mono_calls[0] == 1:
            return 0.0
        if mono_calls[0] <= 20:
            return 0.5
        return 1.0

    def gh_run(argv, **kwargs):
        calls.append(True)
        return _noop_gh_run(argv, **kwargs)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=1, interval_seconds=1,
        monotonic=mono, sleep=lambda d: None, gh_run=gh_run,
    )
    assert result["event"] == "timer"
    assert calls == []
    assert ww.DEGRADATION_PR_SIGNAL_NEVER_SAMPLED in result["degraded"]


# --- CLI smoke ----------------------------------------------------------------


def test_cli_refusal_exit_one(tmp_path):
    proc = _run_cli([
        "run", "--repo-root", str(tmp_path / "missing"), "--batch", "b",
    ])
    assert proc.returncode == 1
    out = json.loads(proc.stdout.strip())
    assert out["ok"] is False


def test_cli_event_exit_zero(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    proc = _run_cli([
        "run", "--repo-root", repo, "--batch", "batch-982",
    ], env=_fake_gh_cli_env(tmp_path))
    assert proc.returncode == 0
    out = json.loads(proc.stdout.strip())
    assert out["ok"] is True
    assert out["event"] == "timer"


# --- loop verb (B1–B5) --------------------------------------------------------


def _valid_repo_for_loop(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "loop-repo")
    _ledger_env(tmp_path, monkeypatch)
    return repo


def _timer_arm_result(batch_id="batch-982", degraded=None):
    return {
        "ok": True,
        "event": "timer",
        "batchId": batch_id,
        "degraded": list(degraded or []),
    }


def _scripted_run_fn(sequence):
    calls = [0]
    violations = []

    def run_fn(*_args, **_kwargs):
        if calls[0] >= len(sequence):
            violations.append(
                f"run_fn called {calls[0]} times but only {len(sequence)} scripted"
            )
            return {
                "ok": False,
                "reason": "test-violation",
                "batchId": "batch-982",
            }
        result = sequence[calls[0]]
        calls[0] += 1
        return result

    return run_fn, calls, violations


def _never_run_fn():
    calls = [0]
    violations = []

    def run_fn(*_args, **_kwargs):
        calls[0] += 1
        violations.append("run_fn must not be called")
        return {
            "ok": False,
            "reason": "test-violation",
            "batchId": "batch-982",
        }

    return run_fn, calls, violations


def test_loop_timer_rearms_until_non_timer_event(tmp_path, monkeypatch):
    repo = _valid_repo_for_loop(tmp_path, monkeypatch)
    terminal = {
        "ok": True,
        "event": "lane-terminal",
        "batchId": "batch-982",
        "degraded": [],
        "launchId": "lane-a",
        "launches": [{"launchId": "lane-a", "state": "handback"}],
    }
    run_fn, calls, violations = _scripted_run_fn([
        _timer_arm_result(),
        _timer_arm_result(),
        terminal,
    ])
    result = ww.loop(
        repo, "batch-982", max_seconds=1, interval_seconds=1, run_fn=run_fn,
    )
    assert result["event"] == "lane-terminal"
    assert result["arms"] == 3
    assert calls[0] == 3
    assert violations == []


def test_loop_first_non_timer_ok_terminates_with_arms(tmp_path, monkeypatch):
    repo = _valid_repo_for_loop(tmp_path, monkeypatch)
    exited = {
        "ok": True,
        "event": "builder-exited",
        "batchId": "batch-982",
        "degraded": [],
        "pids": [42],
        "launches": [{"launchId": "lane-a", "pid": 42}],
    }
    run_fn, calls, violations = _scripted_run_fn([exited])
    result = ww.loop(
        repo, "batch-982", max_seconds=1, interval_seconds=1, run_fn=run_fn,
    )
    assert result["event"] == "builder-exited"
    assert result["pids"] == [42]
    assert result["arms"] == 1
    assert calls[0] == 1
    assert violations == []
    assert result["passedOverCount"] == 0
    assert result["passedOver"] == []


def test_loop_refusal_terminates_immediately_with_arms(tmp_path, monkeypatch):
    repo = _valid_repo_for_loop(tmp_path, monkeypatch)
    refusal = {
        "ok": False,
        "reason": ww.REFUSAL_LEDGER_UNREADABLE,
        "batchId": "batch-982",
    }
    run_fn, calls, violations = _scripted_run_fn([refusal])
    result = ww.loop(
        repo, "batch-982", max_seconds=1, interval_seconds=1, run_fn=run_fn,
    )
    assert result["ok"] is False
    assert result["reason"] == ww.REFUSAL_LEDGER_UNREADABLE
    assert result["arms"] == 1
    assert calls[0] == 1
    assert violations == []


@pytest.mark.parametrize("kwargs,expected_reason", [
    ({"batch_id": "   "}, ww.REFUSAL_BATCH_INVALID),
    ({"max_total_seconds": 0}, ww.REFUSAL_MAX_TOTAL_SECONDS_INVALID),
    ({"interval_seconds": 0}, ww.REFUSAL_INTERVAL_INVALID),
    ({"max_seconds": 0}, ww.REFUSAL_MAX_SECONDS_INVALID),
    (
        {"ignore_events": (("lane-a", ww.EVENT_TIMER),)},
        ww.REFUSAL_IGNORE_EVENT_INVALID,
    ),
])
def test_loop_validation_refusal_never_calls_run_fn(
    tmp_path, monkeypatch, kwargs, expected_reason,
):
    repo = _valid_repo_for_loop(tmp_path, monkeypatch)
    run_fn, calls, violations = _never_run_fn()
    batch_id = kwargs.pop("batch_id", "batch-982")
    result = ww.loop(repo, batch_id, run_fn=run_fn, **kwargs)
    assert result["ok"] is False
    assert result["reason"] == expected_reason
    assert result["arms"] == 0
    assert calls[0] == 0
    assert violations == []


def test_loop_max_total_seconds_emits_last_timer_not_refusal(tmp_path, monkeypatch):
    repo = _valid_repo_for_loop(tmp_path, monkeypatch)
    clock = [0.0]

    def mono():
        return clock[0]

    timer = _timer_arm_result()
    arm = [0]

    def run_fn(*_args, **_kwargs):
        arm[0] += 1
        clock[0] += 3.0
        return dict(timer)

    result = ww.loop(
        repo, "batch-982",
        max_seconds=10,
        interval_seconds=1,
        max_total_seconds=5,
        monotonic=mono,
        sleep=lambda _d: None,
        run_fn=run_fn,
    )
    assert result["ok"] is True
    assert result["event"] == "timer"
    assert result["arms"] == 2


def test_loop_accumulates_degraded_from_discarded_timer_arms(tmp_path, monkeypatch):
    repo = _valid_repo_for_loop(tmp_path, monkeypatch)
    terminal = {
        "ok": True,
        "event": "lane-terminal",
        "batchId": "batch-982",
        "degraded": [],
        "launchId": "lane-a",
        "launches": [],
    }
    run_fn, _calls, violations = _scripted_run_fn([
        _timer_arm_result(degraded=[ww.DEGRADATION_LEDGER_TORN_TAIL]),
        terminal,
    ])
    result = ww.loop(
        repo, "batch-982", max_seconds=1, interval_seconds=1, run_fn=run_fn,
    )
    assert result["event"] == "lane-terminal"
    assert ww.DEGRADATION_LEDGER_TORN_TAIL in result["degraded"]
    assert violations == []


def test_loop_threads_ledger_observed_across_arms(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 1)
    ll.append(repo, _reserved("lane-a", "batch-982", ["plugins/superheroes/lib"], repo))
    ll.append(repo, _started("lane-a", pid=os.getpid()))
    arm = [0]
    real_run = ww.watch_arm
    clock = [0.0]

    def mono():
        return clock[0]

    def run_fn(repo_root, batch_id, **kwargs):
        arm[0] += 1
        if arm[0] >= 2:
            monkeypatch.setattr(
                ww.ll, "read",
                lambda *_a, **_k: {"state": "missing", "records": []},
            )
        call_kwargs = dict(kwargs)
        call_kwargs["gh_run"] = _noop_gh_run
        call_kwargs["monotonic"] = mono
        call_kwargs["sleep"] = lambda d: clock.__setitem__(0, clock[0] + d)
        return real_run(repo_root, batch_id, **call_kwargs)

    result = ww.loop(
        repo, "batch-982",
        max_seconds=1, interval_seconds=1,
        monotonic=mono,
        sleep=lambda d: clock.__setitem__(0, clock[0] + d),
        run_fn=run_fn,
    )
    assert result["ok"] is False
    assert result["reason"] == ww.REFUSAL_LEDGER_UNREADABLE
    assert result["arms"] == 2


def test_loop_threads_pr_state_across_arm_boundary(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)

    terminal = {
        "ok": True,
        "event": "lane-terminal",
        "batchId": "batch-982",
        "degraded": [],
        "launchId": "lane-a",
        "launches": [{"launchId": "lane-a", "state": "handback"}],
    }
    run_fn, calls, violations = _scripted_run_fn([
        _timer_arm_result(),
        {
            "ok": True,
            "event": "pr-set-changed",
            "batchId": "batch-982",
            "degraded": [],
            "prsAdded": [2],
            "prs": [1, 2],
            "prsRemoved": [],
            "stacks": [],
            "ungrouped": [2],
        },
        terminal,
    ])
    result = ww.loop(
        repo, "batch-982",
        max_seconds=2, interval_seconds=1,
        run_fn=run_fn,
    )
    assert result["ok"] is True
    assert result["event"] == "lane-terminal"
    assert result["passedOverCount"] == 1
    assert result["passedOver"][0]["event"] == "pr-set-changed"
    assert result["passedOver"][0]["prsAdded"] == [2]
    assert result["arms"] == 3
    assert violations == []


def test_loop_threads_pr_sampled_so_timer_not_never_sampled(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    arm = [0]
    real_run = ww.watch_arm
    clock = [0.0]
    original_derive = ww._derive_batch_lanes
    gh_calls = [0]
    # Sub-floor scan cost: remaining after derive is 0.95s, below _MIN_PR_POLL_SECONDS.
    sub_floor_scan_cost = 0.05

    def mono():
        return clock[0]

    def gh_once(argv, **kwargs):
        gh_calls[0] += 1
        return _noop_gh_run(argv, **kwargs)

    def run_fn(repo_root, batch_id, **kwargs):
        arm[0] += 1
        call_kwargs = dict(kwargs)
        call_kwargs["gh_run"] = gh_once
        call_kwargs["monotonic"] = mono
        call_kwargs["sleep"] = lambda d: clock.__setitem__(0, clock[0] + d)
        if arm[0] == 1:
            call_kwargs["max_seconds"] = 1
            call_kwargs["interval_seconds"] = 60
            monkeypatch.setattr(ww, "_derive_batch_lanes", original_derive)
        else:
            call_kwargs["max_seconds"] = 1
            call_kwargs["interval_seconds"] = 60

            def slow_derive(*args, **kw):
                clock[0] += sub_floor_scan_cost
                return original_derive(*args, **kw)

            monkeypatch.setattr(ww, "_derive_batch_lanes", slow_derive)
        return real_run(repo_root, batch_id, **call_kwargs)

    gh_calls[0] = 0
    result = ww.loop(
        repo, "batch-982",
        max_seconds=1, interval_seconds=1,
        max_total_seconds=10,
        monotonic=mono,
        sleep=lambda d: clock.__setitem__(0, clock[0] + d),
        run_fn=run_fn,
    )
    assert result["ok"] is True
    assert result["event"] == "timer"
    assert gh_calls[0] == 1
    assert ww.DEGRADATION_PR_SIGNAL_NEVER_SAMPLED not in result["degraded"]


def test_run_explicit_none_cells_start_fresh_each_call(tmp_path, monkeypatch):
    """Explicit None must allocate fresh cells per call, same as omitting them."""
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    common = dict(max_seconds=3, interval_seconds=1, gh_run=_noop_gh_run)
    ww.watch_arm(repo, "batch-982", **common)
    omitted = ww.watch_arm(repo, "batch-982", **common)
    explicit_none = ww.watch_arm(
        repo, "batch-982",
        ledger_observed=None, pr_state=None, pr_sampled=None,
        **common,
    )
    assert omitted == explicit_none
    assert omitted["event"] == "timer"
    assert "prsAdded" not in omitted


# --- ignore-events (B3) -------------------------------------------------------


def test_ignore_event_suppressed_lane_stale_falls_through(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_stale_lane(repo, tmp_path, monkeypatch)
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=60,
        ignore_events=(("lane-a", ww.EVENT_LANE_STALE),),
        gh_run=_noop_gh_run,
    )
    assert result["event"] == "timer"
    assert result["event"] != "lane-stale"


def test_ignore_event_same_lane_different_event_still_fires(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_live_lane(repo, tmp_path, monkeypatch, stamp_state="handback")
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=60,
        ignore_events=(("lane-a", ww.EVENT_LANE_STALE),),
        gh_run=_noop_gh_run,
    )
    assert result["event"] == "lane-terminal"
    assert result["launchId"] == "lane-a"


def test_ignore_event_same_event_different_lane_still_fires(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 2)
    ll.append(repo, _reserved("lane-a", "batch-982", ["plugins/superheroes/lib"], repo))
    ll.append(repo, _started("lane-a", pid=os.getpid()))
    hb.stamp(
        repo, state="working", phase="watch", launch_id="lane-a",
        stale_after_seconds=1, now=time.time() - 60,
    )
    ll.append(repo, _reserved("lane-b", "batch-982", ["plugins/superheroes/lib"], repo))
    ll.append(repo, _started("lane-b", pid=os.getpid()))
    hb.stamp(
        repo, state="working", phase="watch", launch_id="lane-b",
        stale_after_seconds=1, now=time.time() - 60,
    )
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=60,
        ignore_events=(("lane-a", ww.EVENT_LANE_STALE),),
        gh_run=_noop_gh_run,
    )
    assert result["event"] == "lane-stale"
    assert result["launchId"] == "lane-b"


def test_ignore_event_suppressed_builder_exited_filters_pids_and_launches(
    tmp_path, monkeypatch,
):
    repo = _init_repo(tmp_path / "repo")
    dead_suppressed = 888888888
    dead_unsuppressed = 777777777
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 2)
    ll.append(
        repo,
        _reserved("lane-suppressed", "batch-982", ["plugins/superheroes/lib"], repo),
    )
    ll.append(repo, _started("lane-suppressed", pid=dead_suppressed))
    ll.append(
        repo,
        _reserved("lane-live", "batch-982", ["plugins/superheroes/lib"], repo),
    )
    ll.append(repo, _started("lane-live", pid=dead_unsuppressed))
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=60,
        ignore_events=(("lane-suppressed", ww.EVENT_BUILDER_EXITED),),
        gh_run=_noop_gh_run,
    )
    assert result["event"] == "builder-exited"
    assert result["pids"] == [dead_unsuppressed]
    assert result["launches"] == [
        {"launchId": "lane-live", "pid": dead_unsuppressed},
    ]


def test_ignore_event_suppressed_lane_still_in_also_observed(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    dead = 888888888
    live_pid = os.getpid()
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 2)
    ll.append(repo, _reserved("lane-dead", "batch-982", ["plugins/superheroes/lib"], repo))
    ll.append(repo, _started("lane-dead", pid=dead))
    ll.append(repo, _reserved("lane-stale", "batch-982", ["plugins/superheroes/lib"], repo))
    ll.append(repo, _started("lane-stale", pid=live_pid))
    hb.stamp(
        repo, state="working", phase="watch", launch_id="lane-stale",
        stale_after_seconds=1, now=time.time() - 60,
    )
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=60,
        ignore_events=(("lane-stale", ww.EVENT_LANE_STALE),),
        gh_run=_noop_gh_run,
    )
    assert result["event"] == "builder-exited"
    assert result["alsoObserved"] == {"stale": ["lane-stale"]}


@pytest.mark.parametrize("ignore_events", [
    ("not-a-pair",),
    (("lane-a",),),
    (("", ww.EVENT_LANE_STALE),),
    (("lane-a", ""),),
    (("lane-a", ww.EVENT_PR_SET_CHANGED),),
    (("lane-a", ww.EVENT_STACK_STATE_CHANGED),),
    (("lane-a", ww.EVENT_TIMER),),
])
def test_ignore_event_invalid_direct_call(tmp_path, monkeypatch, ignore_events):
    repo = _valid_repo_for_loop(tmp_path, monkeypatch)
    result = ww.watch_arm(
        repo, "batch-982", max_seconds=1, interval_seconds=1,
        ignore_events=ignore_events,
    )
    assert result["ok"] is False
    assert result["reason"] == ww.REFUSAL_IGNORE_EVENT_INVALID


@pytest.mark.parametrize("cli_value", [
    "not-a-pair",
    "lane-a:",
    ":lane-stale",
    "lane-a:pr-set-changed",
    "lane-a:stack-state-changed",
    "lane-a:timer",
])
def test_ignore_event_invalid_cli(tmp_path, monkeypatch, cli_value):
    repo = _valid_repo_for_loop(tmp_path, monkeypatch)
    proc = _run_cli([
        "run", "--repo-root", repo, "--batch", "batch-982",
        "--ignore-event", cli_value,
    ])
    out = json.loads(proc.stdout.strip())
    assert proc.returncode == 1
    assert out["reason"] == ww.REFUSAL_IGNORE_EVENT_INVALID


def test_ignore_event_cli_repeatable_and_last_colon_split(tmp_path, monkeypatch):
    assert ww._parse_ignore_event_cli("lane:a:lane-stale") == (
        "lane:a", ww.EVENT_LANE_STALE,
    )
    repo = _init_repo(tmp_path / "repo")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 2)
    for launch_id in ("lane-a", "lane-b"):
        ll.append(repo, _reserved(launch_id, "batch-982", ["plugins/superheroes/lib"], repo))
        ll.append(repo, _started(launch_id, pid=os.getpid()))
        hb.stamp(
            repo, state="working", phase="watch", launch_id=launch_id,
            stale_after_seconds=1, now=time.time() - 60,
        )
        assert hb.read_heartbeat(repo, launch_id)["class"] == "stale"
    proc = _run_cli([
        "run", "--repo-root", repo, "--batch", "batch-982",
        "--ignore-event", "lane-a:lane-stale",
        "--ignore-event", "lane-b:lane-stale",
    ], env=_fake_gh_cli_env(tmp_path))
    assert proc.returncode == 0
    out = json.loads(proc.stdout.strip())
    assert out["event"] == "timer"
    assert out["event"] != "lane-stale"


# --- loop --log (B4) ----------------------------------------------------------


def test_loop_log_one_json_line_per_timer_arm(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_path = str(tmp_path / "watch.log")
    clock = [0.0]

    def mono():
        return clock[0]

    def fake_sleep(duration):
        clock[0] += duration

    result = ww.loop(
        repo, "batch-982",
        max_seconds=1, interval_seconds=1,
        max_total_seconds=3,
        log_path=log_path,
        monotonic=mono,
        sleep=fake_sleep,
        gh_run=_noop_gh_run,
    )
    assert result["ok"] is True
    assert result["event"] == "timer"
    lines = log_path and open(log_path).read().strip().splitlines()
    assert len(lines) == result["arms"]
    for line in lines:
        entry = json.loads(line)
        assert "arm" in entry
        assert "elapsedSeconds" in entry
        assert "result" in entry
        assert entry["result"]["event"] == "timer"
    arms = [json.loads(line)["arm"] for line in lines]
    assert arms == list(range(1, len(arms) + 1))


def test_loop_log_write_failure_adds_degradation_and_continues(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_path = str(tmp_path / "watch.log")
    clock = [0.0]
    writes = [0]
    real_open = ww._open_log_append

    def flaky_open(path):
        fh, deg = real_open(path)
        if fh is not None and writes[0] == 0:
            writes[0] += 1

            class FailingFile:
                def write(self, _data):
                    raise OSError("disk full")

                def flush(self):
                    pass

                def close(self):
                    pass

            return FailingFile(), None
        return fh, deg

    monkeypatch.setattr(ww, "_open_log_append", flaky_open)

    def mono():
        return clock[0]

    def fake_sleep(duration):
        clock[0] += duration

    result = ww.loop(
        repo, "batch-982",
        max_seconds=1, interval_seconds=1,
        max_total_seconds=2,
        log_path=log_path,
        monotonic=mono,
        sleep=fake_sleep,
        gh_run=_noop_gh_run,
    )
    assert result["ok"] is True
    assert result["event"] == "timer"
    assert result["arms"] == 2
    assert ww.DEGRADATION_LOG_UNWRITABLE in result["degraded"]


def test_loop_log_non_regular_file_refuses_write(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_path = str(tmp_path / "watch.log")
    os.symlink("/dev/null", log_path)
    clock = [0.0]

    def mono():
        return clock[0]

    result = ww.loop(
        repo, "batch-982",
        max_seconds=1, interval_seconds=1,
        max_total_seconds=2,
        log_path=log_path,
        monotonic=mono,
        sleep=lambda d: clock.__setitem__(0, clock[0] + d),
        gh_run=_noop_gh_run,
    )
    assert result["ok"] is True
    assert result["event"] == "timer"
    assert ww.DEGRADATION_LOG_UNWRITABLE in result["degraded"]


# --- loop gaps (B5) -----------------------------------------------------------


def test_loop_refusal_interval_invalid_has_arms_zero(tmp_path, monkeypatch):
    repo = _valid_repo_for_loop(tmp_path, monkeypatch)
    run_fn, calls, violations = _never_run_fn()
    result = ww.loop(
        repo, "batch-982", interval_seconds=0, run_fn=run_fn,
    )
    assert result["ok"] is False
    assert result["reason"] == ww.REFUSAL_INTERVAL_INVALID
    assert result["arms"] == 0
    assert calls[0] == 0
    assert violations == []
    assert result["passedOverCount"] == 0
    assert result["passedOver"] == []


def test_loop_internal_error_returns_empty_passed_over(tmp_path, monkeypatch):
    repo = _valid_repo_for_loop(tmp_path, monkeypatch)

    def run_fn(*_args, **_kwargs):
        raise RuntimeError("boom")

    result = ww.loop(
        repo, "batch-982", max_seconds=1, interval_seconds=1, run_fn=run_fn,
    )
    assert result["ok"] is False
    assert result["reason"] == ww.REFUSAL_INTERNAL_ERROR
    assert result["passedOverCount"] == 0
    assert result["passedOver"] == []


# --- C15 layer 1 watcher (issue #1274) ----------------------------------------


def test_loop_passes_over_pr_set_change(tmp_path, monkeypatch):
    repo = _valid_repo_for_loop(tmp_path, monkeypatch)
    terminal = {
        "ok": True,
        "event": "lane-terminal",
        "batchId": "batch-982",
        "degraded": [],
        "launchId": "lane-a",
        "launches": [],
    }
    pr_change = {
        "ok": True,
        "event": "pr-set-changed",
        "batchId": "batch-982",
        "degraded": [],
        "prsAdded": [2],
        "prs": [1, 2],
        "prsRemoved": [],
        "stacks": [],
        "ungrouped": [2],
    }
    run_fn, _calls, violations = _scripted_run_fn([pr_change, terminal])
    result = ww.loop(
        repo, "batch-982", max_seconds=1, interval_seconds=1, run_fn=run_fn,
    )
    assert result["event"] == "lane-terminal"
    assert result["arms"] == 2
    assert result["passedOverCount"] == 1
    assert result["passedOver"][0]["event"] == "pr-set-changed"
    assert result["passedOver"][0]["prsAdded"] == [2]
    assert violations == []


def test_second_loop_on_same_batch_refuses(tmp_path, monkeypatch):
    repo = _valid_repo_for_loop(tmp_path, monkeypatch)
    held_fd, refusal = ww._acquire_loop_lock(
        repo, "batch-982", os.environ, None,
    )
    assert refusal is None
    run_fn, calls, violations = _never_run_fn()
    try:
        result = ww.loop(
            repo, "batch-982", max_seconds=1, interval_seconds=1, run_fn=run_fn,
        )
    finally:
        ww._release_loop_lock(held_fd)
    assert result["ok"] is False
    assert result["reason"] == ww.REFUSAL_LOOP_ALREADY_LIVE
    assert result["arms"] == 0
    assert result["liveLoop"]["pid"] == os.getpid()
    assert calls[0] == 0
    assert violations == []


def test_loop_stack_state_idle_seat_exits_otherwise_passes_over(tmp_path, monkeypatch):
    repo_idle = _init_repo(tmp_path / "repo-idle")
    _setup_stack_batch(
        repo_idle, tmp_path, monkeypatch,
        launch_specs=[
            {
                "launch_id": "lane-pos1",
                "stack": _STACK_NUM,
                "layer_position": 1,
                "layers_planned": 3,
            },
            {
                "launch_id": "lane-pos2",
                "stack": _STACK_NUM,
                "layer_position": 2,
                "layers_planned": 3,
            },
        ],
    )
    _patch_pr_vet(monkeypatch, {
        50: {"state": _pr_vet_state()},
        51: {"state": _pr_vet_state()},
    })
    clock = [0.0]

    def mono():
        return clock[0]

    def sleep(duration):
        clock[0] += duration

    idle_result = ww.loop(
        repo_idle,
        "batch-982",
        max_seconds=2,
        interval_seconds=1,
        gh_run=_gh_open_prs([50, 51]),
        membership_reader=_membership_for_stack([50, 51]),
        monotonic=mono,
        sleep=sleep,
        max_total_seconds=5,
    )
    assert idle_result["event"] == ww.EVENT_STACK_STATE_CHANGED
    assert idle_result["arms"] == 1
    assert {
        "flag": ww.FLAG_IDLE_SEAT_LAUNCHABLE_CHILD,
        "stack": _STACK_NUM,
        "position": 2,
    } in idle_result["flags"]
    assert idle_result["passedOverCount"] == 0

    repo_benign = _valid_repo_for_loop(tmp_path, monkeypatch)
    benign_stack = {
        "ok": True,
        "event": "stack-state-changed",
        "batchId": "batch-982",
        "degraded": [],
        "stacks": [{"state": ww.STACK_STATE_COMPLETE}],
        "flags": [],
    }
    terminal = {
        "ok": True,
        "event": "lane-terminal",
        "batchId": "batch-982",
        "degraded": [],
        "launchId": "lane-a",
        "launches": [],
    }
    run_fn, _calls, violations = _scripted_run_fn([benign_stack, terminal])
    benign_result = ww.loop(
        repo_benign, "batch-982", max_seconds=1, interval_seconds=1, run_fn=run_fn,
    )
    assert benign_result["event"] == "lane-terminal"
    assert benign_result["passedOverCount"] == 1
    assert benign_result["passedOver"][0]["event"] == "stack-state-changed"
    assert violations == []


def _stack_loop_clock():
    clock = [0.0]

    def mono():
        return clock[0]

    def sleep(duration):
        clock[0] += duration

    return mono, sleep


def test_loop_no_idle_seat_when_next_layer_is_member_from_another_batch(
    tmp_path, monkeypatch,
):
    # axis: field case - layer N+1 is a member PR launched in another batch and
    # this batch holds only layer N+2; loop does not exit on idle-seat at N
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[{
            "launch_id": "lane-pos6",
            "stack": _STACK_NUM,
            "layer_position": 6,
            "layers_planned": 6,
        }],
    )
    prs = [50, 51, 52, 53, 54, 55]
    vet = {n: {"state": _pr_vet_state()} for n in prs[:5]}
    vet[55] = {"state": _pr_vet_state(_vet_not_ready_body())}
    _patch_pr_vet(monkeypatch, vet)
    mono, sleep = _stack_loop_clock()
    result = ww.loop(
        repo,
        "batch-982",
        max_seconds=2,
        interval_seconds=1,
        gh_run=_gh_open_prs(prs),
        membership_reader=_membership_for_stack(prs),
        monotonic=mono,
        sleep=sleep,
        max_total_seconds=5,
    )
    idle_flags = [
        entry for entry in result.get("flags") or ()
        if entry.get("flag") == "idle-seat-launchable-child"
    ]
    assert idle_flags == []
    assert result["event"] == ww.EVENT_TIMER


def test_loop_idle_seat_still_exits_when_next_position_has_no_member_or_lane(
    tmp_path, monkeypatch,
):
    # axis: true case - position N READY, N+1 has no member PR and no batch lane
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[{
            "launch_id": "lane-pos1",
            "stack": _STACK_NUM,
            "layer_position": 1,
            "layers_planned": 3,
        }],
    )
    _patch_pr_vet(monkeypatch, {50: {"state": _pr_vet_state()}})
    mono, sleep = _stack_loop_clock()
    result = ww.loop(
        repo,
        "batch-982",
        max_seconds=2,
        interval_seconds=1,
        gh_run=_gh_open_prs([50]),
        membership_reader=_membership_for_stack([50]),
        monotonic=mono,
        sleep=sleep,
        max_total_seconds=5,
    )
    assert result["event"] == ww.EVENT_STACK_STATE_CHANGED
    assert result["arms"] == 1
    assert {
        "flag": "idle-seat-launchable-child",
        "stack": _STACK_NUM,
        "position": 1,
    } in result["flags"]


def test_loop_idle_seat_exits_when_next_member_closed_unmerged(
    tmp_path, monkeypatch,
):
    # axis: a member PR at N+1 closed without merging leaves the seat idle -
    # N READY, N+1 CLOSED, no batch lane at N+1 still raises the flag at N
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[{
            "launch_id": "lane-pos1",
            "stack": _STACK_NUM,
            "layer_position": 1,
            "layers_planned": 3,
        }],
    )
    _patch_pr_vet(monkeypatch, {
        50: {"state": _pr_vet_state()},
        51: {"state": _pr_vet_state(state="CLOSED")},
    })
    mono, sleep = _stack_loop_clock()
    result = ww.loop(
        repo,
        "batch-982",
        max_seconds=2,
        interval_seconds=1,
        gh_run=_gh_open_prs([50]),
        membership_reader=_membership_for_stack([50, 51], {51: "CLOSED"}),
        monotonic=mono,
        sleep=sleep,
        max_total_seconds=5,
    )
    assert {
        "flag": "idle-seat-launchable-child",
        "stack": _STACK_NUM,
        "position": 1,
    } in (result.get("flags") or [])
    assert result["event"] == ww.EVENT_STACK_STATE_CHANGED
    assert result["arms"] == 1


def test_run_is_one_shot_against_quiet_live_lane(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_live_lane(
        repo, tmp_path, monkeypatch, pid=os.getpid(), stamp_state="working",
    )
    config = tmp_path / "claude-config"
    config.mkdir(exist_ok=True)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
    ledger_reads = [0]
    real_read = ww.ll.read

    def counting_read(repo_root, env=None):
        ledger_reads[0] += 1
        return real_read(repo_root, env=env)

    monkeypatch.setattr(ww.ll, "read", counting_read)
    sleeps = []
    monkeypatch.setattr(ww.time, "sleep", lambda d: sleeps.append(d))
    result = ww.run(repo, "batch-982", gh_run=_noop_gh_run)
    assert result["event"] == "timer"
    assert sleeps == []
    assert ledger_reads[0] == 1


def test_loop_two_distinct_pr_set_changes_passed_over(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    pr_sets = [{1}, {1, 2}, {1, 2, 3}, {1, 2, 3}]
    arm = [0]
    real_run = ww.watch_arm
    clock = [0.0]

    def mono():
        return clock[0]

    def fake_sleep(duration):
        clock[0] += duration

    def gh_for_arm(argv, **kwargs):
        idx = min(max(arm[0] - 1, 0), len(pr_sets) - 1)
        body = [{"number": n} for n in sorted(pr_sets[idx])]
        return subprocess.CompletedProcess(
            argv, 0, stdout=json.dumps(body), stderr="",
        )

    def run_fn(repo_root, batch_id, **kwargs):
        arm[0] += 1
        if arm[0] <= 4:
            return real_run(
                repo_root,
                batch_id,
                gh_run=gh_for_arm,
                max_seconds=5,
                interval_seconds=1,
                monotonic=mono,
                sleep=fake_sleep,
                ledger_observed=kwargs.get("ledger_observed"),
                pr_state=kwargs.get("pr_state"),
                stack_state=kwargs.get("stack_state"),
                pr_sampled=kwargs.get("pr_sampled"),
            )
        return {
            "ok": True,
            "event": "lane-terminal",
            "batchId": batch_id,
            "degraded": [],
            "launchId": "lane-a",
            "launches": [],
        }

    result = ww.loop(
        repo, "batch-982", max_seconds=5, interval_seconds=1,
        run_fn=run_fn, monotonic=mono, sleep=fake_sleep,
    )
    assert result["event"] == "lane-terminal"
    assert result["passedOverCount"] == 2
    assert len(result["passedOver"]) == 2


def test_loop_lock_released_allows_sequential_loops(tmp_path, monkeypatch):
    repo = _valid_repo_for_loop(tmp_path, monkeypatch)
    terminal = {
        "ok": True,
        "event": "lane-terminal",
        "batchId": "batch-982",
        "degraded": [],
        "launchId": "lane-a",
        "launches": [],
    }
    first = ww.loop(
        repo, "batch-982", max_seconds=1, interval_seconds=1,
        run_fn=_scripted_run_fn([terminal])[0],
    )
    assert first["event"] == "lane-terminal"
    second = ww.loop(
        repo, "batch-982", max_seconds=1, interval_seconds=1,
        run_fn=_scripted_run_fn([terminal])[0],
    )
    assert second["ok"] is True
    assert second["event"] == "lane-terminal"


def test_loop_lock_released_on_exception_path(tmp_path, monkeypatch):
    repo = _valid_repo_for_loop(tmp_path, monkeypatch)

    def boom(*_a, **_k):
        raise RuntimeError("arm-boom")

    ww.loop(
        repo, "batch-982", max_seconds=1, interval_seconds=1, run_fn=boom,
    )
    terminal = {
        "ok": True,
        "event": "lane-terminal",
        "batchId": "batch-982",
        "degraded": [],
        "launchId": "lane-a",
        "launches": [],
    }
    run_fn, _c, _v = _scripted_run_fn([terminal])
    second = ww.loop(
        repo, "batch-982", max_seconds=1, interval_seconds=1, run_fn=run_fn,
    )
    assert second["event"] == "lane-terminal"


def test_dead_holder_lock_does_not_block_loop(tmp_path, monkeypatch):
    repo = _valid_repo_for_loop(tmp_path, monkeypatch)
    child = subprocess.run(
        [
            sys.executable, "-B", "-c",
            (
                "import os, sys; "
                f"sys.path.insert(0, {json.dumps(_LIB)}); "
                "import wave_watch as ww; "
                f"fd, ref = ww._acquire_loop_lock({json.dumps(repo)}, "
                f"'batch-982', os.environ, None); "
                "assert ref is None"
            ),
        ],
        env={**os.environ, ll.LEDGER_ROOT_ENV: os.environ[ll.LEDGER_ROOT_ENV]},
    )
    assert child.returncode == 0
    terminal = {
        "ok": True,
        "event": "lane-terminal",
        "batchId": "batch-982",
        "degraded": [],
        "launchId": "lane-a",
        "launches": [],
    }
    run_fn, _c, _v = _scripted_run_fn([terminal])
    result = ww.loop(
        repo, "batch-982", max_seconds=1, interval_seconds=1, run_fn=run_fn,
    )
    assert result["event"] == "lane-terminal"


def test_loop_lock_unavailable_insecure_store_door(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    insecure = str(tmp_path / "ledger-insecure")
    os.makedirs(insecure, mode=0o777)
    os.chmod(insecure, 0o777)
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, insecure)
    run_fn, calls, violations = _never_run_fn()
    result = ww.loop(
        repo, "batch-982", max_seconds=1, interval_seconds=1, run_fn=run_fn,
    )
    assert result["ok"] is False
    assert result["reason"] == ww.REFUSAL_LOOP_LOCK_UNAVAILABLE
    assert result["batchId"] == "batch-982"
    assert result["detail"].startswith("store-door:")
    assert result["arms"] == 0
    assert calls[0] == 0
    assert violations == []


def test_loop_locks_are_per_batch_in_one_repo(tmp_path, monkeypatch):
    repo = _valid_repo_for_loop(tmp_path, monkeypatch)
    fd_a, refusal_a = ww._acquire_loop_lock(
        repo, "batch-a", os.environ, None,
    )
    assert refusal_a is None
    fd_b, refusal_b = ww._acquire_loop_lock(
        repo, "batch-b", os.environ, None,
    )
    assert refusal_b is None
    fd_a2, refusal_a2 = ww._acquire_loop_lock(
        repo, "batch-a", os.environ, None,
    )
    assert fd_a2 is None
    assert refusal_a2 is not None
    assert refusal_a2["ok"] is False
    assert refusal_a2["reason"] == ww.REFUSAL_LOOP_ALREADY_LIVE
    ww._release_loop_lock(fd_a)
    ww._release_loop_lock(fd_b)


def test_loop_lock_released_on_top_ceiling_exit(tmp_path, monkeypatch):
    repo = _valid_repo_for_loop(tmp_path, monkeypatch)
    clock = [0.0, 10.0]
    idx = [0]

    def mono():
        i = min(idx[0], len(clock) - 1)
        idx[0] += 1
        return clock[i]

    run_fn, calls, violations = _never_run_fn()
    result = ww.loop(
        repo,
        "batch-982",
        max_seconds=10,
        interval_seconds=1,
        max_total_seconds=5,
        monotonic=mono,
        sleep=lambda _d: None,
        run_fn=run_fn,
    )
    assert result["event"] == "timer"
    assert result["arms"] == 0
    assert calls[0] == 0
    terminal = {
        "ok": True,
        "event": "lane-terminal",
        "batchId": "batch-982",
        "degraded": [],
        "launchId": "lane-a",
        "launches": [],
    }
    second = ww.loop(
        repo, "batch-982", max_seconds=1, interval_seconds=1,
        run_fn=_scripted_run_fn([terminal])[0],
    )
    assert second["ok"] is True
    assert second["event"] == "lane-terminal"
    assert violations == []


def test_loop_lock_released_on_post_arm_ceiling_exit(tmp_path, monkeypatch):
    repo = _valid_repo_for_loop(tmp_path, monkeypatch)
    clock = [0.0]

    def mono():
        return clock[0]

    pr_change = {
        "ok": True,
        "event": "pr-set-changed",
        "batchId": "batch-982",
        "degraded": [],
        "prsAdded": [1],
        "prs": [1],
        "prsRemoved": [],
        "stacks": [],
        "ungrouped": [1],
    }

    def run_fn(*_args, **_kwargs):
        clock[0] += 6.0
        return dict(pr_change)

    result = ww.loop(
        repo,
        "batch-982",
        max_seconds=10,
        interval_seconds=1,
        max_total_seconds=5,
        monotonic=mono,
        sleep=lambda _d: None,
        run_fn=run_fn,
    )
    assert result["event"] == "timer"
    assert result["arms"] == 1
    terminal = {
        "ok": True,
        "event": "lane-terminal",
        "batchId": "batch-982",
        "degraded": [],
        "launchId": "lane-a",
        "launches": [],
    }
    second = ww.loop(
        repo, "batch-982", max_seconds=1, interval_seconds=1,
        run_fn=_scripted_run_fn([terminal])[0],
    )
    assert second["ok"] is True
    assert second["event"] == "lane-terminal"


def _plant_loop_lock_file(repo, batch_id, tmp_path, monkeypatch):
    store_root = _ledger_env(tmp_path, monkeypatch)
    repo_id = ll.repo_identity(repo)
    locks_dir = os.path.join(store_root, repo_id, "wave-watch-locks")
    os.makedirs(locks_dir, mode=0o700, exist_ok=True)
    repo_dir = os.path.join(store_root, repo_id)
    for path in (store_root, repo_dir, locks_dir):
        os.chmod(path, 0o700)
    lock_name = hashlib.sha256(batch_id.encode("utf-8")).hexdigest() + ".lock"
    lock_path = os.path.join(locks_dir, lock_name)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    os.close(fd)


def _wave_watch_loop_lock_name(batch_id):
    return hashlib.sha256(batch_id.encode("utf-8")).hexdigest() + ".lock"


def _is_wave_watch_loop_lock_open(name, batch_id):
    expected = _wave_watch_loop_lock_name(batch_id)
    if isinstance(name, str):
        return name == expected
    if isinstance(name, (bytes, bytearray)):
        return name == expected.encode("ascii")
    return False


def test_loop_lock_unavailable_non_regular_lock_file(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    batch_id = "batch-982"
    _plant_loop_lock_file(repo, batch_id, tmp_path, monkeypatch)
    real_fstat = ww.os.fstat
    real_open = ww.os.open
    real_flock = ww.fcntl.flock
    wave_watch_lock_fds = set()
    flock_calls = []

    def tracking_open(name, flags, mode=0o777, *, dir_fd=None):
        fd = real_open(name, flags, mode, dir_fd=dir_fd)
        if _is_wave_watch_loop_lock_open(name, batch_id):
            wave_watch_lock_fds.add(fd)
        return fd

    def fake_fstat(fd):
        st = real_fstat(fd)
        if fd in wave_watch_lock_fds:
            fields = list(st)
            fields[0] = stat.S_IFIFO | (st.st_mode & 0o777)
            return os.stat_result(fields)
        return st

    def tracking_flock(fd, op):
        flock_calls.append((fd, op))
        return real_flock(fd, op)

    monkeypatch.setattr(ww.os, "open", tracking_open)
    monkeypatch.setattr(ww.os, "fstat", fake_fstat)
    monkeypatch.setattr(ww.fcntl, "flock", tracking_flock)
    lock_fd, refusal = ww._acquire_loop_lock(repo, batch_id, os.environ, None)
    assert lock_fd is None
    assert refusal is not None
    assert refusal["ok"] is False
    assert flock_calls == []
    assert refusal["reason"] == ww.REFUSAL_LOOP_LOCK_UNAVAILABLE
    assert refusal["batchId"] == batch_id
    assert refusal["detail"] == "lock-file-not-regular"
    assert refusal["arms"] == 0


def test_loop_lock_unavailable_flock_oserror(tmp_path, monkeypatch):
    repo = _valid_repo_for_loop(tmp_path, monkeypatch)
    import errno as errno_mod

    def bad_flock(fd, op):
        raise OSError(errno_mod.ENOLCK, "no locks")

    monkeypatch.setattr(ww.fcntl, "flock", bad_flock)
    run_fn, calls, violations = _never_run_fn()
    result = ww.loop(
        repo, "batch-982", max_seconds=1, interval_seconds=1, run_fn=run_fn,
    )
    assert result["ok"] is False
    assert result["reason"] == ww.REFUSAL_LOOP_LOCK_UNAVAILABLE
    assert result["batchId"] == "batch-982"
    assert "flock:" in result["detail"]
    assert result["arms"] == 0
    assert calls[0] == 0


def test_equal_batch_ids_different_repos_do_not_share_lock(tmp_path, monkeypatch):
    repo_a = _init_repo(tmp_path / "repo-a")
    repo_b = _init_repo(tmp_path / "repo-b")
    store_a = str(tmp_path / "ledger-a")
    store_b = str(tmp_path / "ledger-b")
    os.makedirs(store_a, mode=0o700)
    os.makedirs(store_b, mode=0o700)
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, store_a)
    _precreate_repo_store_dir(repo_a, store_a)
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, store_b)
    _precreate_repo_store_dir(repo_b, store_b)
    fd_a, ref_a = ww._acquire_loop_lock(repo_a, "same-batch", os.environ, None)
    assert ref_a is None
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, store_b)
    fd_b, ref_b = ww._acquire_loop_lock(repo_b, "same-batch", os.environ, None)
    assert ref_b is None
    ww._release_loop_lock(fd_a)
    ww._release_loop_lock(fd_b)


def test_passed_over_cap_keeps_recent_hundred(tmp_path, monkeypatch):
    repo = _valid_repo_for_loop(tmp_path, monkeypatch)
    benign = {
        "ok": True,
        "event": "stack-state-changed",
        "batchId": "batch-982",
        "degraded": [],
        "stacks": [],
        "flags": [],
    }
    cap = ww.PASSED_OVER_CAP
    sequence = []
    for arm in range(1, cap + 2):
        event = dict(benign)
        event["stacks"] = [{"arm": arm}]
        sequence.append(event)
    sequence.append({
        "ok": True,
        "event": "lane-terminal",
        "batchId": "batch-982",
        "degraded": [],
        "launchId": "lane-a",
        "launches": [],
    })
    run_fn, _c, _v = _scripted_run_fn(sequence)
    result = ww.loop(
        repo, "batch-982", max_seconds=1, interval_seconds=1, run_fn=run_fn,
    )
    assert result["passedOverCount"] == cap + 1
    assert len(result["passedOver"]) == cap
    retained_arms = [entry["arm"] for entry in result["passedOver"]]
    assert retained_arms == list(range(2, cap + 2))
    assert result["passedOver"][-1]["stacks"] == [{"arm": cap + 1}]


def test_loop_ceiling_after_benign_non_timer_returns_timer(tmp_path, monkeypatch):
    repo = _valid_repo_for_loop(tmp_path, monkeypatch)
    clock = [0.0]

    def mono():
        return clock[0]

    pr_change = {
        "ok": True,
        "event": "pr-set-changed",
        "batchId": "batch-982",
        "degraded": [],
        "prsAdded": [1],
        "prs": [1],
        "prsRemoved": [],
        "stacks": [],
        "ungrouped": [1],
    }
    calls = [0]

    def run_fn(*_args, **_kwargs):
        calls[0] += 1
        clock[0] += 6.0
        return dict(pr_change)

    result = ww.loop(
        repo, "batch-982",
        max_seconds=10,
        interval_seconds=1,
        max_total_seconds=5,
        monotonic=mono,
        sleep=lambda _d: None,
        run_fn=run_fn,
    )
    assert result["event"] == "timer"
    assert result["passedOverCount"] == 1


def test_loop_ceiling_stale_suppressed_follows_last_benign_arm(tmp_path, monkeypatch):
    repo = _valid_repo_for_loop(tmp_path, monkeypatch)
    clock = [0.0]

    def mono():
        return clock[0]

    timer_suppressed = {
        "ok": True,
        "event": "timer",
        "batchId": "batch-982",
        "degraded": [],
        "staleSuppressed": [
            {
                "launchId": "lane-a",
                "note": ww.NOTE_STALE_SUPPRESSED_TRANSCRIPT_FRESH,
            },
        ],
    }
    pr_stale_observed = {
        "ok": True,
        "event": "pr-set-changed",
        "batchId": "batch-982",
        "degraded": [],
        "prsAdded": [],
        "prs": [1],
        "prsRemoved": [],
        "stacks": [],
        "ungrouped": [1],
        "alsoObserved": {"stale": ["lane-a"]},
    }
    calls = [0]

    def run_fn(*_args, **_kwargs):
        calls[0] += 1
        clock[0] += 3.0
        if calls[0] == 1:
            return dict(timer_suppressed)
        return dict(pr_stale_observed)

    result = ww.loop(
        repo, "batch-982",
        max_seconds=10,
        interval_seconds=1,
        max_total_seconds=5,
        monotonic=mono,
        sleep=lambda _d: None,
        run_fn=run_fn,
    )
    assert result["event"] == "timer"
    assert "staleSuppressed" not in result
    assert result["passedOverCount"] == 1
    assert result["passedOver"][0]["alsoObserved"] == {"stale": ["lane-a"]}


def test_loop_benign_non_timer_writes_log_line(tmp_path, monkeypatch):
    repo = _valid_repo_for_loop(tmp_path, monkeypatch)
    log_path = str(tmp_path / "loop.log")
    pr_change = {
        "ok": True,
        "event": "pr-set-changed",
        "batchId": "batch-982",
        "degraded": [],
        "prsAdded": [1],
        "prs": [1],
        "prsRemoved": [],
        "stacks": [],
        "ungrouped": [1],
    }
    terminal = {
        "ok": True,
        "event": "lane-terminal",
        "batchId": "batch-982",
        "degraded": [],
        "launchId": "lane-a",
        "launches": [],
    }
    run_fn, _c, _v = _scripted_run_fn([pr_change, terminal])
    ww.loop(
        repo, "batch-982",
        max_seconds=1, interval_seconds=1,
        log_path=log_path, run_fn=run_fn,
    )
    lines = open(log_path, encoding="utf-8").read().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["result"]["event"] == "pr-set-changed"


def test_run_slow_gh_returns_without_waiting(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    clock = [0.0]

    def mono():
        return clock[0]

    def slow_gh(argv, **kwargs):
        clock[0] += ww.RUN_READ_BUDGET_SECONDS + 5
        return _noop_gh_run(argv, **kwargs)

    result = ww.run(
        repo, "batch-982", monotonic=mono, gh_run=slow_gh,
    )
    assert result["event"] == "timer"


def test_cli_run_max_seconds_exits_two():
    proc = _run_cli([
        "run", "--repo-root", os.getcwd(), "--batch", "b",
        "--max-seconds", "5",
    ])
    assert proc.returncode == 2


def test_lane_and_benign_event_partition():
    assert ww.LANE_ENDING_EVENTS | ww.BENIGN_EVENTS == ww.EVENTS
    assert not ww.LANE_ENDING_EVENTS & ww.BENIGN_EVENTS


def test_cli_loop_uses_injected_gh_stub_not_real_gh(tmp_path, monkeypatch, capsys):
    # In-process main(), not a subprocess: the gh poll this asserts needs the
    # virtual clock, which a child interpreter would not inherit.
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    shim_dir = tmp_path / "gh-shim"
    shim_dir.mkdir()
    marker = shim_dir / "gh-called"
    gh_script = shim_dir / "gh"
    gh_script.write_text(
        '#!/bin/sh\ntouch "' + str(marker) + '"\necho \'[{"number": 1}]\'\n'
    )
    gh_script.chmod(0o755)
    monkeypatch.setenv("PATH", str(shim_dir) + os.pathsep + os.environ.get("PATH", ""))
    returncode = ww.main([
        _WW_SCRIPT,
        "loop", "--repo-root", repo, "--batch", "batch-982",
        "--max-seconds", "2", "--interval-seconds", "1",
        "--max-total-seconds", "3",
    ])
    assert returncode == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["ok"] is True
    assert out["event"] == "timer"
    assert marker.exists(), "CLI loop must invoke the gh shim, not bypass it"


# --- transcript second chance before lane-stale (#1023) -----------------------

_UNSET = object()   # "caller said nothing", distinct from an explicit None
_TEST_SESSION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_OTHER_SESSION_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"


def _stale_lane_with_worktree(
    repo, tmp_path, monkeypatch, *, worktree, session_id=_TEST_SESSION_ID,
    launch_id="lane-a", batch_id="batch-982", stale_after_seconds=1800,
    age_seconds=1835, config_dir=None,
):
    """A pid-live lane past its own promise, with session id on the ledger record."""
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, batch_id, 1)
    extra = {}
    if worktree is not None:
        extra["worktree"] = worktree
    if session_id is not None:
        extra["sessionId"] = session_id
    if config_dir is not None:
        extra["configDir"] = config_dir
    ll.append(
        repo,
        _reserved(launch_id, batch_id, ["plugins/superheroes/lib"], repo, **extra),
    )
    ll.append(
        repo,
        dict(_started(launch_id, pid=os.getpid()), ts=time.time() - age_seconds - 600),
    )
    hb.stamp(
        repo,
        state="working",
        phase="watch",
        launch_id=launch_id,
        stale_after_seconds=stale_after_seconds,
        now=time.time() - age_seconds,
    )
    assert hb.read_heartbeat(repo, launch_id)["class"] == "stale"
    return store_root


def _point_config_dir_at(tmp_path, monkeypatch):
    """Isolate the transcript search so the real ~/.claude can never satisfy it."""
    config_dir = tmp_path / "host-config"
    config_dir.mkdir(exist_ok=True)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_dir))
    return config_dir


def _write_session_transcript(
    config_dir, session_id, *, age_seconds, bucket="bucket-a", name=None,
):
    """A transcript file named <session_id>.jsonl under an arbitrary projects bucket."""
    project_dir = os.path.join(str(config_dir), "projects", bucket)
    os.makedirs(project_dir, exist_ok=True)
    filename = (session_id + ".jsonl") if name is None else name
    path = os.path.join(project_dir, filename)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write('{"type": "summary"}\n')
    stamp_at = time.time() - age_seconds
    os.utime(path, (stamp_at, stamp_at))
    return path


def test_transcript_config_dirs_is_exactly_one_root(monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/tmp/some-config")
    assert ww._transcript_config_dirs(os.environ) == ["/tmp/some-config"]

    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setenv("HOME", "/home/someone")
    assert ww._transcript_config_dirs(os.environ) == ["/home/someone/.claude"]


def test_transcript_config_dirs_expands_the_supplied_home(monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "~/.claude-three")
    monkeypatch.setenv("HOME", "/home/someone")
    assert ww._transcript_config_dirs(os.environ) == ["/home/someone/.claude-three"]


def test_lane_stale_suppressed_when_transcript_fresh(tmp_path, monkeypatch):
    """DoD: stale heartbeat + fresh transcript => NO lane-stale, and a logged note."""
    repo = _init_repo(tmp_path / "repo")
    worktree = str(tmp_path / "build-wt")
    _stale_lane_with_worktree(repo, tmp_path, monkeypatch, worktree=worktree)
    config_dir = _point_config_dir_at(tmp_path, monkeypatch)
    _write_session_transcript(config_dir, _TEST_SESSION_ID, age_seconds=150)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=1, interval_seconds=1, gh_run=_noop_gh_run,
    )

    assert result["ok"] is True
    assert result["event"] == "timer"
    assert result["event"] != "lane-stale"
    suppressed = result["staleSuppressed"]
    assert [entry["launchId"] for entry in suppressed] == ["lane-a"]
    assert suppressed[0]["note"] == ww.NOTE_STALE_SUPPRESSED_TRANSCRIPT_FRESH
    assert suppressed[0]["staleAfterSeconds"] == 1800
    assert suppressed[0]["state"] == "working"
    assert 140 <= suppressed[0]["transcriptAgeSeconds"] <= 400


def test_session_transcript_mtime_resolves_exactly_one_match(tmp_path, monkeypatch):
    config_dir = _point_config_dir_at(tmp_path, monkeypatch)
    _write_session_transcript(config_dir, _TEST_SESSION_ID, age_seconds=30, bucket="a")
    _write_session_transcript(
        config_dir, _OTHER_SESSION_ID, age_seconds=9000, bucket="b",
    )
    mtime, ambiguous, unresolved = ww._session_transcript_mtime(_TEST_SESSION_ID, os.environ)
    assert ambiguous is False
    assert mtime is not None
    assert time.time() - mtime < 120


# Census: every I2 failure shape must leave the lane still-stale (fail toward alert).
_I2_STILL_STALE_SHAPES = (
    "no-session-id-on-record",
    "zero-matches",
    "only-a-foreign-fresh-transcript",
    "two-or-more-matches",
    "session-id-with-path-separator",
    "no-projects-dir",
    "empty-project-dir",
    "non-transcript-file-only",
    "transcript-colder-than-promise",
    "transcript-dated-in-the-future",
    "transcript-is-a-directory",
    "symlink-at-exact-filename",
    "unreadable-bucket-with-fresh-match",
    "unreadable-projects-root",
    "recorded-config-dir-not-absolute",
)

# The same census, second axis (#1036): staying stale is the INVARIANT; whether the arm
# also discloses transcript-unresolved is the shape's own answer to "could the watcher
# read the transcript at all?". Only a failed READ discloses — absence of a transcript is
# the wedge signal itself, and a record with no session id is the no-identity class.
_I2_SHAPES_DISCLOSING_UNRESOLVED = frozenset({
    "unreadable-bucket-with-fresh-match",
    "unreadable-projects-root",
    "recorded-config-dir-not-absolute",
})


@pytest.mark.parametrize("shape", _I2_STILL_STALE_SHAPES)
def test_i2_failure_shapes_leave_lane_still_stale(tmp_path, monkeypatch, request, shape):
    if shape.startswith("unreadable-") and os.geteuid() == 0:
        pytest.skip("root can read mode-0o000 directories")  # same guard the standalone tests carry
    repo = _init_repo(tmp_path / "repo")
    worktree = str(tmp_path / "build-wt")
    config_dir = _point_config_dir_at(tmp_path, monkeypatch)
    session_id = _TEST_SESSION_ID

    if shape == "no-session-id-on-record":
        _stale_lane_with_worktree(
            repo, tmp_path, monkeypatch, worktree=worktree, session_id=None,
        )
        _write_session_transcript(config_dir, _OTHER_SESSION_ID, age_seconds=60)
    elif shape == "session-id-with-path-separator":
        # Ledger validation requires a UUID sessionId, so exercise the census
        # invariant through _stale_second_chance instead of a written ledger.
        evil_session_id = "../evil"
        _write_session_transcript(config_dir, _OTHER_SESSION_ID, age_seconds=60)
        stale_live = [{
            "launchId": "lane-a",
            "state": "working",
            "ageSeconds": 1835.0,
            "staleAfterSeconds": 1800,
        }]
        live_lanes = {"lane-a": {"sessionId": evil_session_id}}
        degraded = set()
        still, suppressed = ww._stale_second_chance(
            stale_live, live_lanes, os.environ, degraded=degraded,
        )
        assert len(still) == 1 and suppressed == []
        assert ww.DEGRADATION_TRANSCRIPT_UNRESOLVED not in degraded
        return
    elif shape == "recorded-config-dir-not-absolute":
        # The ledger REFUSES a non-absolute configDir, so a lane can only reach the
        # second chance carrying one if the grammar were bypassed. Exercised at the
        # seam for the same reason the path-separator shape is: the invariant under
        # test is that an unusable recorded root never falls back to the watcher's own
        # root, which would let a foreign transcript vouch.
        _write_session_transcript(config_dir, session_id, age_seconds=60)
        stale_live = [{
            "launchId": "lane-a",
            "state": "working",
            "ageSeconds": 1835.0,
            "staleAfterSeconds": 1800,
        }]
        live_lanes = {
            "lane-a": {"sessionId": session_id, "configDir": "relative/config"},
        }
        degraded = set()
        still, suppressed = ww._stale_second_chance(
            stale_live, live_lanes, os.environ, degraded=degraded,
        )
        assert len(still) == 1 and suppressed == []
        assert ww.DEGRADATION_TRANSCRIPT_UNRESOLVED in degraded
        return
    else:
        _stale_lane_with_worktree(repo, tmp_path, monkeypatch, worktree=worktree)

    bucket_dir = os.path.join(str(config_dir), "projects", "bucket-a")
    if shape == "no-projects-dir":
        pass
    elif shape == "empty-project-dir":
        os.makedirs(bucket_dir, exist_ok=True)
    elif shape == "non-transcript-file-only":
        os.makedirs(bucket_dir, exist_ok=True)
        with open(os.path.join(bucket_dir, "notes.txt"), "w", encoding="utf-8") as fh:
            fh.write("not a transcript\n")
    elif shape == "zero-matches":
        pass
    elif shape == "only-a-foreign-fresh-transcript":
        # Regression for #1023: a fresh transcript for another session must never
        # vouch for this lane when its own transcript is absent.
        _write_session_transcript(config_dir, _OTHER_SESSION_ID, age_seconds=60)
    elif shape == "two-or-more-matches":
        _write_session_transcript(config_dir, session_id, age_seconds=60, bucket="a")
        _write_session_transcript(config_dir, session_id, age_seconds=60, bucket="b")
    elif shape == "transcript-colder-than-promise":
        _write_session_transcript(config_dir, session_id, age_seconds=5400)
    elif shape == "transcript-dated-in-the-future":
        _write_session_transcript(config_dir, session_id, age_seconds=-3600)
    elif shape == "transcript-is-a-directory":
        os.makedirs(os.path.join(bucket_dir, session_id + ".jsonl"), exist_ok=True)
    elif shape == "symlink-at-exact-filename":
        os.makedirs(bucket_dir, exist_ok=True)
        target = tmp_path / "elsewhere.jsonl"
        target.write_text("{}\n")
        os.symlink(str(target), os.path.join(bucket_dir, session_id + ".jsonl"))
    elif shape == "unreadable-bucket-with-fresh-match":
        _write_session_transcript(config_dir, session_id, age_seconds=60, bucket="readable")
        unreadable = os.path.join(str(config_dir), "projects", "unreadable")
        os.makedirs(unreadable, mode=0o000)
        # Same hygiene as its sibling: a 0o000 dir defeats pytest's tmp cleanup (rm_rf
        # warnings, garbage dirs left under the tmp root) — hand the mode back after the read.
        request.addfinalizer(lambda: os.chmod(unreadable, 0o700))
    elif shape == "unreadable-projects-root":
        _write_session_transcript(config_dir, session_id, age_seconds=60)
        unreadable_root = os.path.join(str(config_dir), "projects")
        os.chmod(unreadable_root, 0o000)
        # A non-empty 0o000 tree defeats pytest's tmp cleanup, so hand the mode back the
        # moment the watcher has read it.
        request.addfinalizer(lambda: os.chmod(unreadable_root, 0o700))
    else:
        _write_session_transcript(config_dir, session_id, age_seconds=60)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run,
    )

    assert result["event"] == "lane-stale", (
        "%s must fail toward the alert, not toward silence" % shape
    )
    assert result["launchId"] == "lane-a"
    assert "staleSuppressed" not in result
    if shape == "two-or-more-matches":
        assert ww.DEGRADATION_TRANSCRIPT_AMBIGUOUS in result["degraded"]
    # #1036's second axis: the alert is the same, the disclosure is not.
    if shape in _I2_SHAPES_DISCLOSING_UNRESOLVED:
        assert ww.DEGRADATION_TRANSCRIPT_UNRESOLVED in result["degraded"], (
            "%s could not READ the transcript — that must be disclosed, not "
            "presented as a cold transcript" % shape
        )
    else:
        assert ww.DEGRADATION_TRANSCRIPT_UNRESOLVED not in result["degraded"], (
            "%s is an ABSENT or unidentifiable transcript, not a failed read — "
            "disclosing it would make the token meaningless" % shape
        )


def test_transcript_fresh_but_promise_unusable_still_alerts(tmp_path, monkeypatch):
    """A stale entry carrying no usable promise cannot be second-chanced."""
    live_lanes = {"lane-a": {"sessionId": _TEST_SESSION_ID}}
    stale_live = [{
        "launchId": "lane-a",
        "state": "working",
        "ageSeconds": 60.0,
        "staleAfterSeconds": None,
    }]
    still, suppressed = ww._stale_second_chance(
        stale_live, live_lanes, os.environ,
        now=1000.0,
        session_transcript_mtime=lambda sid, env, cfg=None: (999.0, False, False),
    )
    assert still == stale_live
    assert suppressed == []


def test_second_chance_boundary_is_inclusive_at_the_promise():
    live_lanes = {"lane-a": {"sessionId": _TEST_SESSION_ID}}

    def entry():
        return [{
            "launchId": "lane-a", "state": "working",
            "ageSeconds": 3600.0, "staleAfterSeconds": 1800,
        }]

    # Exactly at the promise: still inside the window, so suppressed.
    still, suppressed = ww._stale_second_chance(
        entry(), live_lanes, os.environ,
        now=10000.0,
        session_transcript_mtime=lambda sid, env, cfg=None: (10000.0 - 1800, False, False),
    )
    assert still == [] and len(suppressed) == 1

    # One second past it: outside the window, so it alerts.
    still, suppressed = ww._stale_second_chance(
        entry(), live_lanes, os.environ,
        now=10000.0,
        session_transcript_mtime=lambda sid, env, cfg=None: (10000.0 - 1801, False, False),
    )
    assert len(still) == 1 and suppressed == []


def test_transcript_mtime_after_call_beginning_suppresses_lane():
    """Regression for TOCTOU: a resolver that returns time.time() when invoked must
    not misread an actively-written transcript as future-dated."""
    live_lanes = {"lane-a": {"sessionId": _TEST_SESSION_ID}}
    stale_live = [{
        "launchId": "lane-a", "state": "working",
        "ageSeconds": 3600.0, "staleAfterSeconds": 1800,
    }]
    def _mtime_after_call_beginning(sid, env, cfg=None):
        # Sleep so time.time() here is provably later than any clock read before lookup.
        time.sleep(0.05)
        return (time.time(), False, False)

    still, suppressed = ww._stale_second_chance(
        stale_live, live_lanes, os.environ,
        session_transcript_mtime=_mtime_after_call_beginning,
    )
    assert still == [] and len(suppressed) == 1


def test_session_transcript_mtime_bucket_entry_is_dir_oserror_is_unresolved(
    tmp_path, monkeypatch,
):
    """bucket_entry.is_dir raising OSError must fail closed, not continue past."""
    config_dir = _point_config_dir_at(tmp_path, monkeypatch)
    _write_session_transcript(config_dir, _TEST_SESSION_ID, age_seconds=30, bucket="fresh")
    os.makedirs(os.path.join(str(config_dir), "projects", "poison"), exist_ok=True)

    real_is_dir = os.DirEntry.is_dir

    def _is_dir(self, *args, **kwargs):
        if os.path.basename(self.path) == "poison":
            raise PermissionError("simulated is_dir failure")
        return real_is_dir(self, *args, **kwargs)

    monkeypatch.setattr(os.DirEntry, "is_dir", _is_dir)
    mtime, ambiguous, unresolved = ww._session_transcript_mtime(_TEST_SESSION_ID, os.environ)
    assert mtime is None and ambiguous is False and unresolved is True


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read mode-0o000 directories")
def test_session_transcript_mtime_unreadable_bucket_candidate_stat_is_unresolved(
    tmp_path, monkeypatch,
):
    """chmod 0o000 on a bucket dir fails at os.stat(candidate), not is_dir."""
    config_dir = _point_config_dir_at(tmp_path, monkeypatch)
    _write_session_transcript(config_dir, _TEST_SESSION_ID, age_seconds=30, bucket="unreadable")
    unreadable = os.path.join(str(config_dir), "projects", "unreadable")
    os.chmod(unreadable, 0o000)
    try:
        mtime, ambiguous, unresolved = ww._session_transcript_mtime(_TEST_SESSION_ID, os.environ)
    finally:
        os.chmod(unreadable, 0o700)  # hand the mode back so pytest's tmp cleanup can remove it
    assert mtime is None and ambiguous is False and unresolved is True


def test_absent_bucket_with_fresh_match_suppresses_lane(tmp_path, monkeypatch):
    """A genuinely absent candidate in another bucket must not block suppression."""
    repo = _init_repo(tmp_path / "repo")
    worktree = str(tmp_path / "build-wt")
    _stale_lane_with_worktree(repo, tmp_path, monkeypatch, worktree=worktree)
    config_dir = _point_config_dir_at(tmp_path, monkeypatch)
    _write_session_transcript(config_dir, _TEST_SESSION_ID, age_seconds=60, bucket="present")
    os.makedirs(os.path.join(str(config_dir), "projects", "absent"), exist_ok=True)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=1, interval_seconds=1, gh_run=_noop_gh_run,
    )

    assert result["event"] == "timer"
    assert [e["launchId"] for e in result["staleSuppressed"]] == ["lane-a"]


@pytest.mark.parametrize("ahead_seconds", [1, 30, 3600])
def test_any_future_dated_transcript_alerts(ahead_seconds):
    """No skew tolerance: the watcher and the transcript share one host clock, so a
    future mtime is a wrong clock, and the fail-toward-alert invariant is absolute."""
    live_lanes = {"lane-a": {"sessionId": _TEST_SESSION_ID}}
    stale_live = [{
        "launchId": "lane-a", "state": "working",
        "ageSeconds": 3600.0, "staleAfterSeconds": 1800,
    }]
    still, suppressed = ww._stale_second_chance(
        stale_live, live_lanes, os.environ,
        now=10000.0,
        session_transcript_mtime=lambda sid, env, cfg=None: (10000.0 + ahead_seconds, False, False),
    )
    assert len(still) == 1 and suppressed == []


def test_config_dir_override_is_searched_alone(tmp_path, monkeypatch):
    """A same-named transcript under the DEFAULT root belongs to another session and
    must never vouch for this lane when the override is set."""
    override = tmp_path / "override-config"
    decoy = tmp_path / "decoy-home" / ".claude"
    monkeypatch.setenv("HOME", str(tmp_path / "decoy-home"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(override))
    _write_session_transcript(decoy, _TEST_SESSION_ID, age_seconds=5)

    assert ww._transcript_config_dirs(os.environ) == [str(override)]
    mtime, ambiguous, unresolved = ww._session_transcript_mtime(_TEST_SESSION_ID, os.environ)
    assert mtime is None and ambiguous is False and unresolved is False

    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    assert ww._transcript_config_dirs(os.environ) == [str(decoy)]
    mtime, ambiguous, unresolved = ww._session_transcript_mtime(_TEST_SESSION_ID, os.environ)
    assert mtime is not None and ambiguous is False


def test_recorded_config_dir_is_searched_instead_of_the_watchers_own(
    tmp_path, monkeypatch,
):
    """DoD (#1036): a lane launched under ANOTHER Claude instance gets its second chance.

    Root A is the lane's recorded root and holds its fresh transcript; root B is the
    watcher's own env root and holds nothing. Before this, the watcher searched B, found
    nothing, and alerted a working builder.
    """
    repo = _init_repo(tmp_path / "repo")
    worktree = str(tmp_path / "build-wt")
    root_a = tmp_path / "config-a"
    root_b = tmp_path / "config-b"
    root_a.mkdir()
    root_b.mkdir()
    _stale_lane_with_worktree(
        repo, tmp_path, monkeypatch, worktree=worktree, config_dir=str(root_a),
    )
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(root_b))
    _write_session_transcript(root_a, _TEST_SESSION_ID, age_seconds=120)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=1, interval_seconds=1, gh_run=_noop_gh_run,
    )

    assert result["event"] == "timer"
    assert [e["launchId"] for e in result["staleSuppressed"]] == ["lane-a"]
    assert ww.DEGRADATION_TRANSCRIPT_UNRESOLVED not in result["degraded"]


def test_without_a_recorded_config_dir_only_the_env_root_resolves(
    tmp_path, monkeypatch,
):
    """DoD (#1036): a pre-change record still resolves under the watcher's env root.

    Same two roots as the test above, same fresh transcript under root A — but the lane
    records no configDir, so the watcher searches its own root B only and finds nothing.
    Unchanged behaviour, and the guarantee that #1036 never widened the search to both.
    """
    repo = _init_repo(tmp_path / "repo")
    worktree = str(tmp_path / "build-wt")
    root_a = tmp_path / "config-a"
    root_b = tmp_path / "config-b"
    root_a.mkdir()
    root_b.mkdir()
    _stale_lane_with_worktree(repo, tmp_path, monkeypatch, worktree=worktree)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(root_b))
    _write_session_transcript(root_a, _TEST_SESSION_ID, age_seconds=120)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run,
    )

    assert result["event"] == "lane-stale"
    assert "staleSuppressed" not in result
    assert ww.DEGRADATION_TRANSCRIPT_UNRESOLVED not in result["degraded"]

    # And the same lane resolves once the env root IS the one holding the transcript —
    # proving the miss above is the root choice, not a broken fixture.
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(root_a))
    again = ww.watch_arm(
        repo, "batch-982", max_seconds=1, interval_seconds=1, gh_run=_noop_gh_run,
    )
    assert [e["launchId"] for e in again["staleSuppressed"]] == ["lane-a"]


def test_recorded_config_dir_never_falls_back_to_the_env_root(tmp_path, monkeypatch):
    """A recorded root that resolves to nothing must NOT be retried under the env root.

    The fall-back would be the #1023 foreign-transcript hole reopened: the env root's
    same-named file belongs to whatever session wrote it there.
    """
    repo = _init_repo(tmp_path / "repo")
    worktree = str(tmp_path / "build-wt")
    root_a = tmp_path / "config-a"
    env_root = tmp_path / "config-env"
    root_a.mkdir()
    env_root.mkdir()
    _stale_lane_with_worktree(
        repo, tmp_path, monkeypatch, worktree=worktree, config_dir=str(root_a),
    )
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(env_root))
    _write_session_transcript(env_root, _TEST_SESSION_ID, age_seconds=60)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run,
    )

    assert result["event"] == "lane-stale"
    assert "staleSuppressed" not in result


def test_unreadable_recorded_config_dir_discloses_unresolved(tmp_path, monkeypatch, request):
    """An I/O failure under the lane's OWN root discloses, exactly like the env root's."""
    repo = _init_repo(tmp_path / "repo")
    worktree = str(tmp_path / "build-wt")
    root_a = tmp_path / "config-a"
    root_a.mkdir()
    _stale_lane_with_worktree(
        repo, tmp_path, monkeypatch, worktree=worktree, config_dir=str(root_a),
    )
    _point_config_dir_at(tmp_path, monkeypatch)
    _write_session_transcript(root_a, _TEST_SESSION_ID, age_seconds=60)
    unreadable_root = os.path.join(str(root_a), "projects")
    os.chmod(unreadable_root, 0o000)
    request.addfinalizer(lambda: os.chmod(unreadable_root, 0o700))

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run,
    )

    assert result["event"] == "lane-stale"
    assert ww.DEGRADATION_TRANSCRIPT_UNRESOLVED in result["degraded"]


@pytest.mark.parametrize("shape", ["config-root-is-a-file", "projects-is-a-file"])
def test_enotdir_is_a_failed_read_not_an_absent_transcript(tmp_path, monkeypatch, shape):
    """ENOTDIR is a malformed root, not a missing transcript.

    Absence means ENOENT and nothing else. A config root (or `projects`) that is a FILE is
    something the watcher could not read — reporting it as a plain zero-match would hide an
    unreadable root behind the same silence a genuinely cold transcript produces.
    """
    _point_config_dir_at(tmp_path, monkeypatch)
    if shape == "config-root-is-a-file":
        recorded = tmp_path / "root-is-a-file"
        recorded.write_text("not a directory\n")
    else:
        recorded = tmp_path / "root-with-file-projects"
        recorded.mkdir()
        (recorded / "projects").write_text("not a directory\n")

    mtime, ambiguous, unresolved = ww._session_transcript_mtime(
        _TEST_SESSION_ID, os.environ, str(recorded),
    )
    assert mtime is None and ambiguous is False
    assert unresolved is True, "%s is an unreadable root, not an absent transcript" % shape


def test_candidate_stat_enotdir_is_a_failed_read(tmp_path, monkeypatch):
    """The third ENOTDIR site: a bucket replaced by a file between scandir and stat.

    The two fixtures above both fail at the projects scan; this one pins the candidate
    `stat`, which is otherwise only reachable through a race.
    """
    config_dir = _point_config_dir_at(tmp_path, monkeypatch)
    _write_session_transcript(config_dir, _TEST_SESSION_ID, age_seconds=30)
    real_stat = ww.os.stat
    target = os.path.join(
        str(config_dir), "projects", "bucket-a", _TEST_SESSION_ID + ".jsonl",
    )

    def enotdir_stat(path, *a, **kw):
        if str(path) == target:
            raise NotADirectoryError("simulated ENOTDIR race")
        return real_stat(path, *a, **kw)

    monkeypatch.setattr(ww.os, "stat", enotdir_stat)
    mtime, ambiguous, unresolved = ww._session_transcript_mtime(
        _TEST_SESSION_ID, os.environ,
    )
    assert mtime is None and ambiguous is False and unresolved is True


def test_unusable_recorded_root_resolves_unresolved_instead_of_raising(monkeypatch):
    """A path can be absolute and still be unusable — that must not escape the resolver.

    os.scandir raises ValueError (not OSError) on an embedded NUL. Letting it propagate
    turns one lane's stale ALERT into a whole-watch `internal-error` refusal — the
    fail-toward-alert invariant inverted, and the watch stops instead of reporting.
    """
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/tmp/does-not-matter")
    mtime, ambiguous, unresolved = ww._session_transcript_mtime(
        _TEST_SESSION_ID, os.environ, "/tmp/\x00bad",
    )
    assert mtime is None and ambiguous is False and unresolved is True


def test_a_lane_with_an_unusable_root_still_alerts_rather_than_refusing(
    tmp_path, monkeypatch,
):
    """End-to-end: the arm emits lane-stale with the token, never an internal-error."""
    stale_live = [{
        "launchId": "lane-a", "state": "working",
        "ageSeconds": 1835.0, "staleAfterSeconds": 1800,
    }]
    live_lanes = {
        "lane-a": {"sessionId": _TEST_SESSION_ID, "configDir": "/tmp/\x00bad"},
    }
    degraded = set()
    still, suppressed = ww._stale_second_chance(
        stale_live, live_lanes, os.environ, degraded=degraded,
    )
    assert len(still) == 1 and suppressed == []
    assert ww.DEGRADATION_TRANSCRIPT_UNRESOLVED in degraded


def test_transcript_config_dirs_recorded_root_wins_over_env(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/tmp/env-config")
    assert ww._transcript_config_dirs(os.environ) == ["/tmp/env-config"]
    assert ww._transcript_config_dirs(
        os.environ, recorded="/tmp/lane-config",
    ) == ["/tmp/lane-config"]
    # Unusable recorded roots resolve to NO root — never to the env root.
    for bad in ("", "   ", "relative/config", 17, True):
        assert ww._transcript_config_dirs(os.environ, recorded=bad) == [], bad


def test_a_recorded_root_is_searched_verbatim_never_rewritten(monkeypatch):
    """The watcher searches what was RECORDED, byte for byte.

    The grammar accepts any usable absolute path, so a directory whose name genuinely
    ends in a space is a legal root. Trimming it before searching looks in a directory
    the lane never wrote to — and "the lane's own root" stops meaning anything if the
    reader gets to normalize it on the way in.
    """
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/tmp/env-config")
    for recorded in ("/tmp/lane-config ", "/tmp/trailing  ", "/tmp/a b/c "):
        assert ww._transcript_config_dirs(os.environ, recorded=recorded) == [recorded]
    # A LEADING space makes the string non-absolute, so it is not a legal recorded root
    # at all — refused as unusable, not silently trimmed into a different directory.
    assert ww._transcript_config_dirs(os.environ, recorded=" /tmp/leading") == []


def test_every_root_the_launcher_can_record_round_trips_through_the_watcher(monkeypatch):
    """The invariant that makes the pair coherent: record R, and the watcher searches R.

    This is the seam #1036 actually rests on — it pins launcher and watcher together
    rather than testing either side's parsing in isolation, so a normalization added to
    one side and not the other fails here.
    """
    monkeypatch.setenv("HOME", "/ambient-home")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/tmp/watcher-own-root")
    spellings = [
        "/abs/plain", " /abs/with-space ", "~/.claude-two", "relative/config",
        "", "   ", None,
    ]
    for spelling in spellings:
        env = {"HOME": "/lane-home"}
        if spelling is not None:
            env["CLAUDE_CONFIG_DIR"] = spelling
        recorded = launcher.spawn_config_dir(env=env, cwd="/build/wt")
        assert recorded is not None, spelling
        assert ww._transcript_config_dirs(os.environ, recorded=recorded) == [recorded], (
            "launcher recorded %r but the watcher would search elsewhere" % recorded
        )


def test_folded_session_id_wires_end_to_end_to_suppressed_lane(tmp_path, monkeypatch):
    """A real folded ledger record's sessionId reaches the suppression path."""
    repo = _init_repo(tmp_path / "repo")
    worktree = str(tmp_path / "build-wt")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 1)
    ll.append(
        repo,
        _reserved(
            "lane-a", "batch-982", ["lib"], repo,
            worktree=worktree, sessionId=_TEST_SESSION_ID,
        ),
    )
    ll.append(repo, dict(_started("lane-a", pid=os.getpid()), ts=time.time() - 4000))
    hb.stamp(repo, state="working", phase="watch", launch_id="lane-a",
             stale_after_seconds=1800, now=time.time() - 1835)
    config_dir = _point_config_dir_at(tmp_path, monkeypatch)
    _write_session_transcript(config_dir, _TEST_SESSION_ID, age_seconds=120)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=1, interval_seconds=1, gh_run=_noop_gh_run,
    )

    assert result["event"] == "timer"
    assert [e["launchId"] for e in result["staleSuppressed"]] == ["lane-a"]


def test_one_fresh_lane_cannot_hide_a_different_wedged_lane(tmp_path, monkeypatch):
    """The suppression is PER LANE. A regression clearing the whole stale list when
    any transcript is fresh would let a working builder mask a wedged sibling —
    the normal shape of a parallel wave."""
    repo = _init_repo(tmp_path / "repo")
    fresh_wt = str(tmp_path / "fresh-wt")
    cold_wt = str(tmp_path / "cold-wt")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 2)
    for lane, wt, sid in (
        ("lane-fresh", fresh_wt, _TEST_SESSION_ID),
        ("lane-cold", cold_wt, _OTHER_SESSION_ID),
    ):
        ll.append(repo, _reserved(
            lane, "batch-982", ["lib"], repo, worktree=wt, sessionId=sid,
        ))
        ll.append(repo, dict(_started(lane, pid=os.getpid()), ts=time.time() - 4000))
        hb.stamp(repo, state="working", phase="watch", launch_id=lane,
                 stale_after_seconds=1800, now=time.time() - 1835)
    config_dir = _point_config_dir_at(tmp_path, monkeypatch)
    _write_session_transcript(config_dir, _TEST_SESSION_ID, age_seconds=120)
    _write_session_transcript(config_dir, _OTHER_SESSION_ID, age_seconds=3600)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run,
    )

    assert result["event"] == "lane-stale"
    assert [e["launchId"] for e in result["launches"]] == ["lane-cold"]
    assert [e["launchId"] for e in result["staleSuppressed"]] == ["lane-fresh"]


def test_unreadable_matched_bucket_still_alerts(tmp_path, monkeypatch):
    """stat on the transcript file fails — still alerts."""
    config_dir = _point_config_dir_at(tmp_path, monkeypatch)
    _write_session_transcript(config_dir, _TEST_SESSION_ID, age_seconds=60)
    real_stat = ww.os.stat
    target = os.path.join(
        str(config_dir), "projects", "bucket-a", _TEST_SESSION_ID + ".jsonl",
    )

    def refuse_stat(path, *a, **kw):
        if str(path) == target:
            raise PermissionError("refused")
        return real_stat(path, *a, **kw)

    monkeypatch.setattr(ww.os, "stat", refuse_stat)
    mtime, ambiguous, unresolved = ww._session_transcript_mtime(_TEST_SESSION_ID, os.environ)
    assert mtime is None and ambiguous is False and unresolved is True


def test_symlinked_transcript_is_never_followed(tmp_path, monkeypatch):
    """A link named <sessionId>.jsonl never suppresses."""
    config_dir = _point_config_dir_at(tmp_path, monkeypatch)
    bucket_dir = os.path.join(str(config_dir), "projects", "bucket-a")
    os.makedirs(bucket_dir, exist_ok=True)
    target = tmp_path / "elsewhere.jsonl"
    target.write_text("{}\n")
    os.symlink(str(target), os.path.join(bucket_dir, _TEST_SESSION_ID + ".jsonl"))

    mtime, ambiguous, unresolved = ww._session_transcript_mtime(_TEST_SESSION_ID, os.environ)
    assert mtime is None and ambiguous is False and unresolved is False


def test_directory_named_session_id_never_suppresses(tmp_path, monkeypatch):
    config_dir = _point_config_dir_at(tmp_path, monkeypatch)
    bucket_dir = os.path.join(str(config_dir), "projects", "bucket-a")
    os.makedirs(os.path.join(bucket_dir, _TEST_SESSION_ID + ".jsonl"), exist_ok=True)

    mtime, ambiguous, unresolved = ww._session_transcript_mtime(_TEST_SESSION_ID, os.environ)
    assert mtime is None and ambiguous is False and unresolved is False


def test_session_id_with_path_separator_resolves_to_nothing():
    mtime, ambiguous, unresolved = ww._session_transcript_mtime("../evil", os.environ)
    assert mtime is None and ambiguous is False and unresolved is False


def test_suppressed_lane_drops_out_of_also_observed(tmp_path, monkeypatch):
    """A suppressed lane is not stale at all — it must not ride alsoObserved either."""
    repo = _init_repo(tmp_path / "repo")
    worktree = str(tmp_path / "build-wt")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 2)
    ll.append(repo, _reserved("lane-a", "batch-982", ["lib"], repo))
    ll.append(repo, _started("lane-a", pid=os.getpid()))
    hb.stamp(repo, state="blocked", phase="watch", launch_id="lane-a",
             stale_after_seconds=3600)
    ll.append(
        repo,
        _reserved(
            "lane-b", "batch-982", ["lib"], repo,
            worktree=worktree, sessionId=_TEST_SESSION_ID,
        ),
    )
    ll.append(
        repo, dict(_started("lane-b", pid=os.getpid()), ts=time.time() - 2000),
    )
    hb.stamp(repo, state="working", phase="watch", launch_id="lane-b",
             stale_after_seconds=1800, now=time.time() - 1835)
    config_dir = _point_config_dir_at(tmp_path, monkeypatch)
    _write_session_transcript(config_dir, _TEST_SESSION_ID, age_seconds=120)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run,
    )

    assert result["event"] == "lane-blocked"
    assert "stale" not in (result.get("alsoObserved") or {})
    assert [e["launchId"] for e in result["staleSuppressed"]] == ["lane-b"]


def test_later_tick_finding_lane_still_stale_clears_its_suppression(
    tmp_path, monkeypatch,
):
    """The note can never contradict the event it rides on."""
    repo = _init_repo(tmp_path / "repo")
    worktree = str(tmp_path / "build-wt")
    _stale_lane_with_worktree(repo, tmp_path, monkeypatch, worktree=worktree)
    _point_config_dir_at(tmp_path, monkeypatch)

    calls = [0]

    def fading_transcript(session_id, _env, _config_dir=None):
        calls[0] += 1
        # Fresh on the first tick, long cold on every tick after it.
        if calls[0] == 1:
            return time.time() - 60, False, False
        return time.time() - 100000, False, False

    monkeypatch.setattr(ww, "_session_transcript_mtime", fading_transcript)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=4, interval_seconds=1, gh_run=_noop_gh_run,
    )

    assert calls[0] >= 2, "needed at least two ticks to exercise the clear"
    assert result["event"] == "lane-stale"
    assert "staleSuppressed" not in result


def test_loop_log_line_carries_the_suppression_note(tmp_path, monkeypatch):
    """DoD: the loop stays honest about what it saw — the note lands in --log."""
    repo = _init_repo(tmp_path / "repo")
    worktree = str(tmp_path / "build-wt")
    _stale_lane_with_worktree(repo, tmp_path, monkeypatch, worktree=worktree)
    config_dir = _point_config_dir_at(tmp_path, monkeypatch)
    _write_session_transcript(config_dir, _TEST_SESSION_ID, age_seconds=90)
    log_path = str(tmp_path / "watch.log")

    ww.loop(
        repo, "batch-982", max_seconds=1, interval_seconds=1,
        max_total_seconds=2, log_path=log_path, gh_run=_noop_gh_run,
    )

    lines = [
        json.loads(line)
        for line in open(log_path, encoding="utf-8").read().strip().splitlines()
    ]
    assert lines, "loop must have logged at least one timer arm"
    logged = lines[0]["result"]["staleSuppressed"]
    assert logged[0]["launchId"] == "lane-a"
    assert logged[0]["note"] == ww.NOTE_STALE_SUPPRESSED_TRANSCRIPT_FRESH


# --- pr-set-changed stack grouping (#1340 layer 2b) ---------------------------


_TEST_REPO_SLUG = "owner/repo"


def _stack_membership(stack_number, pr_numbers_in_order, states=None):
    states = states or {}
    return {
        "ok": True,
        "reason": None,
        "stack": {
            "number": stack_number,
            "size": len(pr_numbers_in_order),
            "baseRefName": "main",
        },
        "members": [
            {
                "position": index + 1,
                "number": number,
                "state": states.get(number, "OPEN"),
            }
            for index, number in enumerate(pr_numbers_in_order)
        ],
    }


def _gh_pr_list_with_repo_view(pr_sets, repo_slug=_TEST_REPO_SLUG):
    idx = [0]

    def gh_run(argv, **kwargs):
        if argv[:3] == ["gh", "repo", "view"]:
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout=json.dumps({"nameWithOwner": repo_slug}),
                stderr="",
            )
        if argv[:3] == ["gh", "pr", "list"]:
            body = [{"number": n} for n in sorted(pr_sets[idx[0]])]
            idx[0] += 1
            return subprocess.CompletedProcess(
                argv, 0, stdout=json.dumps(body), stderr="",
            )
        raise AssertionError("unexpected gh argv: %r" % argv)

    return gh_run


def _run_pr_set_changed(
    tmp_path, monkeypatch, pr_sets, membership_reader, *, max_seconds=5,
):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    return ww.watch_arm(
        repo,
        "batch-982",
        max_seconds=max_seconds,
        interval_seconds=1,
        gh_run=_gh_pr_list_with_repo_view(pr_sets),
        membership_reader=membership_reader,
    )


def test_pr_set_changed_two_stacks_groups_all_members_in_position_order(
    tmp_path, monkeypatch,
):
    pr_sets = [{10, 20, 30, 40}, {10, 20, 30, 40, 50, 60}]
    calls = []

    def membership_reader(*, pr, repo, **kwargs):
        calls.append({"pr": pr, "kwargs": kwargs})
        if pr == 50:
            return _stack_membership(100, [50, 51])
        if pr == 60:
            return _stack_membership(200, [60, 61, 62])
        raise AssertionError("unexpected pr %r" % pr)

    result = _run_pr_set_changed(
        tmp_path, monkeypatch, pr_sets, membership_reader,
    )

    assert result["event"] == "pr-set-changed"
    assert result["prsAdded"] == [50, 60]
    assert result["stacks"] == [
        {"stack": 100, "prs": [50, 51]},
        {"stack": 200, "prs": [60, 61, 62]},
    ]
    assert result["ungrouped"] == []
    assert [entry["pr"] for entry in calls] == [50, 60]


def test_pr_set_changed_second_member_in_stack_costs_no_extra_reader_call(
    tmp_path, monkeypatch,
):
    pr_sets = [{10, 20}, {10, 20, 30, 40}]
    calls = []

    def membership_reader(*, pr, repo, **kwargs):
        calls.append(pr)
        return _stack_membership(100, [30, 40])

    result = _run_pr_set_changed(
        tmp_path, monkeypatch, pr_sets, membership_reader,
    )

    assert result["event"] == "pr-set-changed"
    assert result["prsAdded"] == [30, 40]
    assert calls == [30]
    assert result["stacks"] == [{"stack": 100, "prs": [30, 40]}]
    assert result["ungrouped"] == []


def _gh_repo_view_proc():
    return subprocess.CompletedProcess(
        [],
        0,
        stdout=json.dumps({"nameWithOwner": _TEST_REPO_SLUG}),
        stderr="",
    )


def _changed_pr_partition(stacks, ungrouped):
    represented = set(ungrouped)
    for entry in stacks:
        represented.update(entry["prs"])
    return represented


def test_resolve_pr_stack_groups_changing_snapshot_covers_every_changed_pr():
    degraded = set()

    def membership_reader(*, pr, repo, **kwargs):
        if pr == 30:
            return _stack_membership(1, [30])
        if pr == 40:
            return _stack_membership(1, [30, 40])
        raise AssertionError("unexpected pr %r" % pr)

    stacks, ungrouped, _position_maps = ww._resolve_pr_stack_groups(
        "/fake/repo",
        deadline=time.monotonic() + 30,
        monotonic=time.monotonic,
        gh_run=lambda *args, **kwargs: _gh_repo_view_proc(),
        membership_reader=membership_reader,
        env={},
        degraded=degraded,
        changed_prs=[30, 40],
        repo_slug=_TEST_REPO_SLUG,
    )

    assert _changed_pr_partition(stacks, ungrouped) == {30, 40}
    assert stacks == [{"stack": 1, "prs": [30, 40]}]
    assert ungrouped == []


def test_resolve_pr_stack_groups_shrinking_snapshot_covers_every_changed_pr():
    degraded = set()

    def membership_reader(*, pr, repo, **kwargs):
        if pr == 30:
            return _stack_membership(1, [30])
        if pr == 40:
            return _stack_membership(1, [40])
        raise AssertionError("unexpected pr %r" % pr)

    stacks, ungrouped, _position_maps = ww._resolve_pr_stack_groups(
        "/fake/repo",
        deadline=time.monotonic() + 30,
        monotonic=time.monotonic,
        gh_run=lambda *args, **kwargs: _gh_repo_view_proc(),
        membership_reader=membership_reader,
        env={},
        degraded=degraded,
        changed_prs=[30, 40],
        repo_slug=_TEST_REPO_SLUG,
    )

    assert _changed_pr_partition(stacks, ungrouped) == {30, 40}
    assert stacks == [{"stack": 1, "prs": [30, 40]}]
    assert ungrouped == []


def test_resolve_pr_stack_groups_refusal_then_membership_no_duplicate():
    degraded = set()

    def membership_reader(*, pr, repo, **kwargs):
        if pr == 30:
            return {"ok": False, "reason": "stack-unreadable"}
        if pr == 40:
            return _stack_membership(100, [30, 40])
        raise AssertionError("unexpected pr %r" % pr)

    stacks, ungrouped, _position_maps = ww._resolve_pr_stack_groups(
        "/fake/repo",
        deadline=time.monotonic() + 30,
        monotonic=time.monotonic,
        gh_run=lambda *args, **kwargs: _gh_repo_view_proc(),
        membership_reader=membership_reader,
        env={},
        degraded=degraded,
        changed_prs=[30, 40],
        repo_slug=_TEST_REPO_SLUG,
    )

    assert _changed_pr_partition(stacks, ungrouped) == {30, 40}
    assert stacks == [{"stack": 100, "prs": [30, 40]}]
    assert ungrouped == []
    assert ww.DEGRADATION_STACK_SIGNAL_UNAVAILABLE in degraded


def test_pr_set_changed_not_linked_lands_in_ungrouped(tmp_path, monkeypatch):
    pr_sets = [{10}, {10, 99}]

    def membership_reader(*, pr, repo, **kwargs):
        return {"ok": False, "reason": sc.REASON_NOT_LINKED}

    result = _run_pr_set_changed(
        tmp_path, monkeypatch, pr_sets, membership_reader,
    )

    assert result["event"] == "pr-set-changed"
    assert result["prsAdded"] == [99]
    assert result["stacks"] == []
    assert result["ungrouped"] == [99]


def test_pr_set_changed_refusing_read_degrades_and_preserves_prs_keys(
    tmp_path, monkeypatch,
):
    pr_sets = [{10}, {10, 99}]

    def membership_reader(*, pr, repo, **kwargs):
        return {"ok": False, "reason": "stack-unreadable"}

    result = _run_pr_set_changed(
        tmp_path, monkeypatch, pr_sets, membership_reader,
    )

    assert result["event"] == "pr-set-changed"
    assert result["prs"] == [10, 99]
    assert result["prsAdded"] == [99]
    assert result["prsRemoved"] == []
    assert ww.DEGRADATION_STACK_SIGNAL_UNAVAILABLE in result["degraded"]
    assert result["stacks"] == []
    assert result["ungrouped"] == [99]


def test_pr_set_changed_exhausted_deadline_stops_walk_no_reader_after(
    tmp_path, monkeypatch,
):
    pr_sets = [{10}, {10, 30, 40}]
    reader_calls = []
    mono = [1000.0]

    def membership_reader(*, pr, repo, **kwargs):
        reader_calls.append(pr)
        if pr == 30:
            mono[0] += 10.0
            return _stack_membership(100, [30, 31])
        return _stack_membership(200, [40, 41])

    def monotonic():
        return mono[0]

    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    result = ww.watch_arm(
        repo,
        "batch-982",
        max_seconds=5,
        interval_seconds=1,
        gh_run=_gh_pr_list_with_repo_view(pr_sets),
        membership_reader=membership_reader,
        monotonic=monotonic,
    )

    assert result["event"] == "pr-set-changed"
    assert reader_calls == [30]
    assert ww.DEGRADATION_STACK_SIGNAL_UNAVAILABLE in result["degraded"]
    assert result["stacks"] == [{"stack": 100, "prs": [30, 31]}]
    assert result["ungrouped"] == [40]


def test_pr_set_changed_membership_read_timeout_bounded_by_remaining(
    tmp_path, monkeypatch,
):
    pr_sets = [{10}, {10, 99}]
    seen_deadlines = []
    mono = [500.0]
    watcher_deadline = 505.0

    def membership_reader(*, pr, repo, **kwargs):
        seen_deadlines.append(kwargs.get("deadline"))
        return {"ok": False, "reason": sc.REASON_NOT_LINKED}

    def monotonic():
        return mono[0]

    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    result = ww.watch_arm(
        repo,
        "batch-982",
        max_seconds=5,
        interval_seconds=1,
        gh_run=_gh_pr_list_with_repo_view(pr_sets),
        membership_reader=membership_reader,
        monotonic=monotonic,
    )

    assert result["event"] == "pr-set-changed"
    assert seen_deadlines == [watcher_deadline - mono[0]]


def test_pr_set_changed_no_stacks_empty_stacks_all_changed_in_ungrouped(
    tmp_path, monkeypatch,
):
    pr_sets = [{10}, {10, 88, 99}]

    def membership_reader(*, pr, repo, **kwargs):
        return {"ok": False, "reason": sc.REASON_NOT_LINKED}

    result = _run_pr_set_changed(
        tmp_path, monkeypatch, pr_sets, membership_reader,
    )

    assert result["event"] == "pr-set-changed"
    assert result["prsAdded"] == [88, 99]
    assert result["prsRemoved"] == []
    assert result["stacks"] == []
    assert result["ungrouped"] == [88, 99]


# --- pr-set-changed membership read budget (#1340 layer 2c) -------------------


def _stack_check_graphql_run(pr_number, page_size=None):
    if page_size is None:
        page_size = sc.DEFAULT_PAGE_SIZE
    owner, name = _TEST_REPO_SLUG.split("/", 1)
    stack_number = 100
    stack_size = 5
    position = 3

    def _member(member_position, number=None):
        member_number = number if number is not None else (100 + member_position)
        return {
            "position": member_position,
            "pullRequest": {
                "number": member_number,
                "state": "OPEN",
                "isDraft": False,
                "headRefName": "branch-%d" % member_position,
                "headRefOid": "oid%d" % member_position,
                "baseRefName": "main",
            },
        }

    nodes = [
        _member(1),
        _member(2),
        _member(3, number=pr_number),
        _member(4),
        _member(5),
    ]
    pull = {
        "number": pr_number,
        "baseRefName": "main",
        "headRefName": "branch-%d" % position,
        "headRefOid": "oid%d" % position,
        "stackEntry": {
            "position": position,
            "stack": {
                "number": stack_number,
                "size": stack_size,
                "baseRefName": "main",
                "entries": {
                    "pageInfo": {
                        "hasNextPage": False,
                        "endCursor": None,
                    },
                    "nodes": nodes,
                },
            },
        },
    }

    handlers = {}
    argv = tuple(sc._graphql_argv(owner, name, pr_number, page_size, None))
    payload = {"data": {"repository": {"pullRequest": pull}}}
    handlers[argv] = SimpleNamespace(
        returncode=0, stdout=json.dumps(payload), stderr="",
    )

    queues = {key: [value, value] for key, value in handlers.items()}

    def run(argv, **kwargs):
        key = tuple(argv)
        if key not in queues or not queues[key]:
            raise AssertionError("unexpected gh argv: %r" % (argv,))
        return queues[key].pop(0)

    return run


def test_pr_set_changed_whole_membership_read_bounded_by_watcher_remaining_budget(
    tmp_path, monkeypatch,
):
    pr_sets = [{10}, {10, 99}]
    recorded = []
    mono = [500.0]
    watcher_deadline = 505.0

    def membership_reader(**kwargs):
        recorded.append(dict(kwargs))
        return {"ok": False, "reason": sc.REASON_NOT_LINKED}

    def monotonic():
        return mono[0]

    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    result = ww.watch_arm(
        repo,
        "batch-982",
        max_seconds=5,
        interval_seconds=1,
        gh_run=_gh_pr_list_with_repo_view(pr_sets),
        membership_reader=membership_reader,
        monotonic=monotonic,
    )

    assert result["event"] == "pr-set-changed"
    assert len(recorded) == 1
    call = recorded[0]
    assert call["pr"] == 99
    assert call["repo"] == _TEST_REPO_SLUG
    assert call["deadline"] > 0
    assert call["deadline"] == watcher_deadline - mono[0]
    assert "timeout" not in call


def test_pr_set_changed_slow_read_refusal_degrades_without_partial_stack(
    tmp_path, monkeypatch,
):
    pr_sets = [{10}, {10, 99}]
    mono = [1000.0]

    def membership_reader(**kwargs):
        mono[0] += 10.0
        return {"ok": False, "reason": sc.REASON_STACK_UNREADABLE}

    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    result = ww.watch_arm(
        repo,
        "batch-982",
        max_seconds=5,
        interval_seconds=1,
        gh_run=_gh_pr_list_with_repo_view(pr_sets),
        membership_reader=membership_reader,
        monotonic=lambda: mono[0],
    )

    assert result["event"] == "pr-set-changed"
    assert ww.DEGRADATION_STACK_SIGNAL_UNAVAILABLE in result["degraded"]
    assert result["ungrouped"] == [99]
    assert result["stacks"] == []
    assert not any(99 in entry["prs"] for entry in result["stacks"])


def test_pr_set_changed_real_read_membership_whole_read_bounded_by_watcher_budget(
    tmp_path, monkeypatch,
):
    pr_sets = [{10}, {10, 99}]
    monkeypatch.setattr(
        sc.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None,
    )
    # Stable until membership GraphQL transport runs; then jump past the shared
    # read budget so verification sees exhaustion without pinning call count.
    sc_clock = [1000.0]

    def sc_monotonic():
        return sc_clock[0]

    monkeypatch.setattr(sc.time, "monotonic", sc_monotonic)

    base_run = _stack_check_graphql_run(99)

    def membership_graphql_run(argv, **kwargs):
        sc_clock[0] = 2000.0
        return base_run(argv, **kwargs)

    def membership_reader(**kwargs):
        return sc.read_membership(run=membership_graphql_run, **kwargs)

    mono = [1000.0]
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    result = ww.watch_arm(
        repo,
        "batch-982",
        max_seconds=5,
        interval_seconds=1,
        gh_run=_gh_pr_list_with_repo_view(pr_sets),
        membership_reader=membership_reader,
        monotonic=lambda: mono[0],
    )

    assert result["event"] == "pr-set-changed"
    assert ww.DEGRADATION_STACK_SIGNAL_UNAVAILABLE in result["degraded"]
    assert result["ungrouped"] == [99]
    assert result["stacks"] == []


# --- pr-set-changed slug read de-duplication (#1340 layer 2d) -----------------


def test_pr_set_changed_resolve_repo_slug_refusal_degrades_to_ungrouped(
    tmp_path, monkeypatch,
):
    pr_sets = [{10}, {10, 99}]

    def membership_reader(*, pr, repo, **kwargs):
        raise AssertionError("membership_reader must not run when slug read refused")

    def refusing_resolve(*args, **kwargs):
        return None, {
            "ok": False,
            "reason": sc.REASON_STACK_UNREADABLE,
            "detail": "test refusal",
        }

    monkeypatch.setattr(sc, "resolve_repo_slug", refusing_resolve)
    result = _run_pr_set_changed(
        tmp_path, monkeypatch, pr_sets, membership_reader,
    )

    assert result["event"] == "pr-set-changed"
    assert ww.DEGRADATION_STACK_SIGNAL_UNAVAILABLE in result["degraded"]
    assert result["stacks"] == []
    assert result["ungrouped"] == [99]


def test_pr_set_changed_resolve_repo_slug_argument_refusal_degrades_to_ungrouped(
    tmp_path, monkeypatch,
):
    pr_sets = [{10}, {10, 99}]

    def membership_reader(*, pr, repo, **kwargs):
        raise AssertionError("membership_reader must not run when slug read refused")

    def argument_refusing_resolve(*args, **kwargs):
        return None, {
            "ok": False,
            "reason": sc.REASON_BAD_ARGUMENT,
            "detail": "bad repo_root",
        }

    monkeypatch.setattr(sc, "resolve_repo_slug", argument_refusing_resolve)
    result = _run_pr_set_changed(
        tmp_path, monkeypatch, pr_sets, membership_reader,
    )

    assert result["event"] == "pr-set-changed"
    assert ww.DEGRADATION_STACK_SIGNAL_UNAVAILABLE in result["degraded"]
    assert result["stacks"] == []
    assert result["ungrouped"] == [99]


def test_resolve_repo_slug_sub_min_budget_makes_no_gh_call():
    gh_calls = []
    mono = [1000.0]

    def gh_run(argv, **kwargs):
        gh_calls.append(argv)
        return _gh_repo_view_proc()

    slug, refusal = ww._resolve_repo_slug(
        "/fake/repo",
        deadline=1000.5,
        monotonic=lambda: mono[0],
        gh_run=gh_run,
        env={},
    )

    assert slug is None
    assert gh_calls == []


def test_run_honours_caller_supplied_membership_reader(tmp_path, monkeypatch):
    pr_sets = [{10}, {10, 99}]
    recorded = []

    def membership_reader(*, pr, repo, **kwargs):
        recorded.append(pr)
        return {"ok": False, "reason": sc.REASON_NOT_LINKED}

    result = _run_pr_set_changed(
        tmp_path, monkeypatch, pr_sets, membership_reader,
    )

    assert result["event"] == "pr-set-changed"
    assert recorded == [99]


def test_loop_honours_caller_supplied_membership_reader(tmp_path, monkeypatch, watcher_clock):
    repo = _valid_repo_for_loop(tmp_path, monkeypatch)

    def membership_reader(*, pr, repo, **kwargs):
        return {"ok": False, "reason": sc.REASON_NOT_LINKED}

    terminal = {
        "ok": True,
        "event": "lane-terminal",
        "batchId": "batch-982",
        "degraded": [],
        "launchId": "lane-a",
        "launches": [],
    }
    scripted_run_fn, _calls, violations = _scripted_run_fn([
        _timer_arm_result(),
        {
            "ok": True,
            "event": "pr-set-changed",
            "batchId": "batch-982",
            "degraded": [],
            "prsAdded": [99],
            "prs": [10, 99],
            "prsRemoved": [],
            "stacks": [],
            "ungrouped": [99],
        },
        terminal,
    ])
    forwarded_readers = []

    def run_fn(*args, **kwargs):
        forwarded_readers.append(kwargs["membership_reader"])
        return scripted_run_fn(*args, **kwargs)

    result = ww.loop(
        repo,
        "batch-982",
        max_seconds=2,
        interval_seconds=1,
        sleep=watcher_clock.sleep,
        run_fn=run_fn,
        membership_reader=membership_reader,
    )

    assert result["event"] == "lane-terminal"
    assert result["passedOverCount"] == 1
    assert violations == []
    assert forwarded_readers
    assert all(reader is membership_reader for reader in forwarded_readers)


# --- stack-state-changed (#1340 layer 2f) -------------------------------------


import grounding_stage as gs  # noqa: E402

_STACK_NUM = 100
_HEAD_SHA = "abcdef0123456789abcdef0123456789abcdef01"
_STALE_SHA = "1234567890abcdef1234567890abcdef12345678"
_VET_MARKER = gs.REGION_MARKERS["advisor-vet"]


def _stack_premise(stack, layer_position, layers_planned=None):
    premise = {"stack": stack, "layerPosition": layer_position}
    if layers_planned is not None:
        premise["layersPlanned"] = layers_planned
    return premise


def _reserved_stack(
    launch_id, batch_id, surfaces, repo_root, stack, layer_position,
    layers_planned=None, **extra,
):
    return _reserved(
        launch_id, batch_id, surfaces, repo_root,
        premise=_stack_premise(stack, layer_position, layers_planned),
        **extra,
    )


def _vet_ready_body(head_sha=_HEAD_SHA):
    return _VET_MARKER + "\n**Verdict: READY** · %s\n" % head_sha


def _vet_not_ready_body(head_sha=_HEAD_SHA):
    return _VET_MARKER + "\n**Verdict: NOT READY** · %s\n" % head_sha


def _pr_vet_state(body=None, head=_HEAD_SHA, state="OPEN", is_draft=False):
    return {
        "body": body or _vet_ready_body(head),
        "headRefOid": head,
        "state": state,
        "isDraft": is_draft,
    }


def _patch_pr_vet(monkeypatch, vet_by_pr):
    def read_pr_vet_state(pr, repo, **kwargs):
        spec = vet_by_pr.get(pr)
        if spec is None:
            return None, {
                "ok": False,
                "reason": sc.REASON_STACK_UNREADABLE,
                "detail": "test refusal",
            }
        if spec.get("refuse"):
            return None, spec["refuse"]
        return spec["state"], None

    monkeypatch.setattr(sc, "read_pr_vet_state", read_pr_vet_state)


def _membership_for_stack(pr_numbers, states=None):
    def membership_reader(*, pr, repo, **kwargs):
        for number in pr_numbers:
            if pr == number:
                return _stack_membership(_STACK_NUM, pr_numbers, states)
        raise AssertionError("unexpected pr %r" % pr)

    return membership_reader


def _gh_open_prs(open_prs, repo_slug=_TEST_REPO_SLUG):
    pr_list = sorted(open_prs)

    def gh_run(argv, **kwargs):
        if argv[:3] == ["gh", "repo", "view"]:
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout=json.dumps({"nameWithOwner": repo_slug}),
                stderr="",
            )
        if argv[:3] == ["gh", "pr", "list"]:
            body = [{"number": n} for n in pr_list]
            return subprocess.CompletedProcess(
                argv, 0, stdout=json.dumps(body), stderr="",
            )
        raise AssertionError("unexpected gh argv: %r" % argv)

    return gh_run


def _setup_stack_batch(
    repo, tmp_path, monkeypatch, batch_id="batch-982", launch_specs=(),
):
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, batch_id, max(1, len(launch_specs)))
    for spec in launch_specs:
        ll.append(
            repo,
            _reserved_stack(
                spec["launch_id"],
                batch_id,
                ["plugins/superheroes/lib"],
                repo,
                spec["stack"],
                spec["layer_position"],
                spec.get("layers_planned"),
            ),
        )
        if spec.get("started"):
            ll.append(repo, _started(spec["launch_id"], pid=999999999))
        if spec.get("terminal"):
            result = ll.terminalize(
                repo,
                spec["launch_id"],
                child_ever_spawned=True,
                outcome="handback",
                evidence="done",
            )
            assert result["ok"], result
    return store_root


def _snapshot_stack_state(
    repo, batch_lanes, open_prs, monkeypatch, membership_reader, pr_vet_reader,
    repo_slug=_TEST_REPO_SLUG,
):
    degraded = set()
    snapshot = ww._compute_stack_state_snapshot(
        batch_lanes,
        sorted(open_prs),
        repo,
        deadline=time.monotonic() + 30,
        monotonic=time.monotonic,
        gh_run=_gh_open_prs(open_prs),
        membership_reader=membership_reader,
        env={},
        degraded=degraded,
        repo_slug=repo_slug,
        pr_vet_reader=pr_vet_reader,
    )
    return snapshot, degraded


def _fold_batch_lanes(repo, batch_id):
    read_result = ll.read(repo)
    folded = ll.fold(read_result["records"])
    assert folded["ok"]
    return {
        lid: info
        for lid, info in folded["launches"].items()
        if info.get("batchId") == batch_id
    }


def _position_ready_reader(position_map, vet_by_pr):
    def pr_vet_reader(pr_number, repo_slug, **kwargs):
        spec = vet_by_pr.get(pr_number)
        if spec is None:
            return None, {
                "ok": False,
                "reason": sc.REASON_STACK_UNREADABLE,
            }
        if spec.get("refuse"):
            return None, spec["refuse"]
        return spec["state"], None

    return pr_vet_reader


def test_stack_complete_fires_when_every_position_ready(tmp_path, monkeypatch):
    # axis: stack-complete when every position 1..layersPlanned is READY at head
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[{
            "launch_id": "lane-a",
            "stack": _STACK_NUM,
            "layer_position": 1,
            "layers_planned": 2,
        }],
    )
    _patch_pr_vet(monkeypatch, {
        50: {"state": _pr_vet_state()},
        51: {"state": _pr_vet_state()},
    })
    result = ww.watch_arm(
        repo,
        "batch-982",
        max_seconds=2,
        interval_seconds=1,
        gh_run=_gh_open_prs([50, 51]),
        membership_reader=_membership_for_stack([50, 51]),
    )
    assert result["event"] == ww.EVENT_STACK_STATE_CHANGED
    stack_entry = result["stacks"][0]
    assert stack_entry["state"] == ww.STACK_STATE_COMPLETE
    assert stack_entry["layersPlanned"] == 2


def test_stack_complete_fires_on_vet_only_without_pr_set_change(
    tmp_path, monkeypatch,
):
    # axis: unchanged open-PR set, body edit makes top layer READY — event still fires
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[
            {
                "launch_id": "lane-a",
                "stack": _STACK_NUM,
                "layer_position": 1,
                "layers_planned": 2,
            },
            {
                "launch_id": "lane-b",
                "stack": _STACK_NUM,
                "layer_position": 2,
                "layers_planned": 2,
            },
        ],
    )
    vet_states = [
        {
            50: {"state": _pr_vet_state()},
            51: {"state": _pr_vet_state(_vet_not_ready_body())},
        },
        {
            50: {"state": _pr_vet_state()},
            51: {"state": _pr_vet_state()},
        },
    ]
    tick = [0]

    def read_pr_vet_state(pr, repo, **kwargs):
        spec = vet_states[min(tick[0], len(vet_states) - 1)].get(pr)
        if spec is None:
            return None, {"ok": False, "reason": sc.REASON_STACK_UNREADABLE}
        return spec["state"], None

    monkeypatch.setattr(sc, "read_pr_vet_state", read_pr_vet_state)
    clock = [0.0]
    batch_lanes = _fold_batch_lanes(repo, "batch-982")
    complete_snapshot, _ = _snapshot_stack_state(
        repo, batch_lanes, [50, 51],
        monkeypatch,
        _membership_for_stack([50, 51]),
        _position_ready_reader(
            {1: 50, 2: 51},
            {50: {"state": _pr_vet_state()}, 51: {"state": _pr_vet_state()}},
        ),
    )
    assert ww._stack_state_fires(complete_snapshot, None)

    def mono():
        return clock[0]

    def sleep(duration):
        clock[0] += duration
        tick[0] += 1

    result = ww.watch_arm(
        repo,
        "batch-982",
        max_seconds=5,
        interval_seconds=1,
        gh_run=_gh_open_prs([50, 51]),
        membership_reader=_membership_for_stack([50, 51]),
        monotonic=mono,
        sleep=sleep,
    )
    assert result["event"] == ww.EVENT_STACK_STATE_CHANGED
    assert tick[0] >= 1
    assert result["stacks"][0]["state"] == ww.STACK_STATE_COMPLETE


def test_layers_planned_read_from_terminal_launch(tmp_path, monkeypatch):
    # axis: layersPlanned from terminal launch via all_lanes batch_lanes
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[
            {
                "launch_id": "lane-live",
                "stack": _STACK_NUM,
                "layer_position": 1,
                "started": True,
            },
            {
                "launch_id": "lane-term",
                "stack": _STACK_NUM,
                "layer_position": 2,
                "layers_planned": 2,
                "started": True,
                "terminal": True,
            },
        ],
    )
    degraded = set()
    ledger_observed = [False]
    batch_lanes, live_lanes, ledger_readable = ww._derive_batch_lanes(
        repo, "batch-982", None, degraded, set(), ledger_observed,
    )
    assert ledger_readable
    assert batch_lanes["lane-live"]["layersPlanned"] is None
    assert batch_lanes["lane-term"]["terminal"] is True
    assert batch_lanes["lane-term"]["layersPlanned"] == 2
    assert "lane-term" not in live_lanes
    snapshot, _degraded = _snapshot_stack_state(
        repo,
        batch_lanes,
        [50, 51],
        monkeypatch,
        _membership_for_stack([50, 51]),
        _position_ready_reader(
            {1: 50, 2: 51},
            {50: {"state": _pr_vet_state()}, 51: {"state": _pr_vet_state()}},
        ),
    )
    assert snapshot["stacks"][0]["layersPlanned"] == 2
    assert snapshot["stacks"][0]["state"] == ww.STACK_STATE_COMPLETE


def test_stack_incomplete_missing_position(tmp_path, monkeypatch):
    # axis: stack-incomplete names missing position
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[{
            "launch_id": "lane-a",
            "stack": _STACK_NUM,
            "layer_position": 1,
            "layers_planned": 2,
        }],
    )
    batch_lanes = _fold_batch_lanes(repo, "batch-982")
    snapshot, _ = _snapshot_stack_state(
        repo, batch_lanes, [50],
        monkeypatch,
        _membership_for_stack([50]),
        _position_ready_reader(
            {1: 50},
            {50: {"state": _pr_vet_state()}},
        ),
    )
    entry = snapshot["stacks"][0]
    assert entry["state"] == ww.STACK_STATE_INCOMPLETE
    assert entry["missingPositions"] == [2]


def test_stack_incomplete_not_ready_verdict(tmp_path, monkeypatch):
    # axis: stack-incomplete when verdict is not READY
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[{
            "launch_id": "lane-a",
            "stack": _STACK_NUM,
            "layer_position": 1,
            "layers_planned": 2,
        }],
    )
    batch_lanes = _fold_batch_lanes(repo, "batch-982")
    snapshot, _ = _snapshot_stack_state(
        repo, batch_lanes, [50, 51],
        monkeypatch,
        _membership_for_stack([50, 51]),
        _position_ready_reader(
            {1: 50, 2: 51},
            {
                50: {"state": _pr_vet_state()},
                51: {"state": _pr_vet_state(_vet_not_ready_body())},
            },
        ),
    )
    entry = snapshot["stacks"][0]
    assert entry["state"] == ww.STACK_STATE_INCOMPLETE
    assert entry["missingPositions"] == [2]


def test_stack_incomplete_stale_sha(tmp_path, monkeypatch):
    # axis: stack-incomplete when verdict pinned to stale sha
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[{
            "launch_id": "lane-a",
            "stack": _STACK_NUM,
            "layer_position": 1,
            "layers_planned": 2,
        }],
    )
    batch_lanes = _fold_batch_lanes(repo, "batch-982")
    snapshot, _ = _snapshot_stack_state(
        repo, batch_lanes, [50, 51],
        monkeypatch,
        _membership_for_stack([50, 51]),
        _position_ready_reader(
            {1: 50, 2: 51},
            {
                50: {"state": _pr_vet_state()},
                51: {
                    "state": _pr_vet_state(
                        _vet_ready_body(_STALE_SHA), head=_HEAD_SHA,
                    ),
                },
            },
        ),
    )
    entry = snapshot["stacks"][0]
    assert entry["state"] == ww.STACK_STATE_INCOMPLETE
    assert entry["missingPositions"] == [2]


def test_stack_incomplete_pr_read_refuses(tmp_path, monkeypatch):
    # axis: stack-incomplete when member vet read refuses
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[{
            "launch_id": "lane-a",
            "stack": _STACK_NUM,
            "layer_position": 1,
            "layers_planned": 2,
        }],
    )
    batch_lanes = _fold_batch_lanes(repo, "batch-982")
    snapshot, degraded = _snapshot_stack_state(
        repo, batch_lanes, [50, 51],
        monkeypatch,
        _membership_for_stack([50, 51]),
        _position_ready_reader(
            {1: 50, 2: 51},
            {
                50: {"state": _pr_vet_state()},
                51: {
                    "refuse": {
                        "ok": False,
                        "reason": sc.REASON_STACK_UNREADABLE,
                    },
                },
            },
        ),
    )
    entry = snapshot["stacks"][0]
    assert entry["state"] == ww.STACK_STATE_INCOMPLETE
    assert entry["missingPositions"] == [2]
    assert ww.DEGRADATION_STACK_SIGNAL_UNAVAILABLE in degraded


def test_stack_incomplete_vet_read_refuses(tmp_path, monkeypatch):
    # axis: stack-incomplete when vet verdict read refuses
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[{
            "launch_id": "lane-a",
            "stack": _STACK_NUM,
            "layer_position": 1,
            "layers_planned": 2,
        }],
    )
    batch_lanes = _fold_batch_lanes(repo, "batch-982")
    vet_calls = [0]
    original_read_vet = sc.read_vet_verdict

    def read_vet_verdict(body, head):
        vet_calls[0] += 1
        if vet_calls[0] == 2:
            return None, {
                "ok": False,
                "reason": sc.REASON_STACK_UNREADABLE,
            }
        return original_read_vet(body, head)

    monkeypatch.setattr(sc, "read_vet_verdict", read_vet_verdict)
    snapshot, degraded = _snapshot_stack_state(
        repo, batch_lanes, [50, 51],
        monkeypatch,
        _membership_for_stack([50, 51]),
        _position_ready_reader(
            {1: 50, 2: 51},
            {
                50: {"state": _pr_vet_state()},
                51: {"state": _pr_vet_state()},
            },
        ),
    )
    entry = snapshot["stacks"][0]
    assert entry["state"] == ww.STACK_STATE_INCOMPLETE
    assert entry["missingPositions"] == [2]
    assert entry["reason"] is None
    assert ww.DEGRADATION_STACK_SIGNAL_UNAVAILABLE in degraded


def test_stack_incomplete_membership_unresolved(tmp_path, monkeypatch):
    # axis: stack-incomplete when membership cannot be resolved
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[{
            "launch_id": "lane-a",
            "stack": _STACK_NUM,
            "layer_position": 1,
            "layers_planned": 2,
        }],
    )
    batch_lanes = _fold_batch_lanes(repo, "batch-982")

    def refusing_membership(**kwargs):
        return {"ok": False, "reason": sc.REASON_STACK_UNREADABLE}

    snapshot, degraded = _snapshot_stack_state(
        repo, batch_lanes, [50, 51],
        monkeypatch,
        refusing_membership,
        _position_ready_reader({1: 50}, {50: {"state": _pr_vet_state()}}),
    )
    entry = snapshot["stacks"][0]
    assert entry["state"] == ww.STACK_STATE_INCOMPLETE
    assert entry["reason"] == ww.STACK_REASON_MEMBERSHIP_UNRESOLVED
    assert ww.DEGRADATION_STACK_SIGNAL_UNAVAILABLE in degraded


def test_layers_planned_unknown_incomplete(tmp_path, monkeypatch):
    # axis: layers-planned-unknown reads incomplete
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[{
            "launch_id": "lane-a",
            "stack": _STACK_NUM,
            "layer_position": 1,
        }],
    )
    batch_lanes = _fold_batch_lanes(repo, "batch-982")
    snapshot, _ = _snapshot_stack_state(
        repo, batch_lanes, [50],
        monkeypatch,
        _membership_for_stack([50]),
        _position_ready_reader({1: 50}, {50: {"state": _pr_vet_state()}}),
    )
    entry = snapshot["stacks"][0]
    assert entry["state"] == ww.STACK_STATE_INCOMPLETE
    assert entry["reason"] == ww.STACK_REASON_LAYERS_PLANNED_UNKNOWN


def test_layers_planned_disagreed_incomplete(tmp_path, monkeypatch):
    # axis: layers-planned-disagreed reads incomplete
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[
            {
                "launch_id": "lane-a",
                "stack": _STACK_NUM,
                "layer_position": 1,
                "layers_planned": 2,
            },
            {
                "launch_id": "lane-b",
                "stack": _STACK_NUM,
                "layer_position": 2,
                "layers_planned": 3,
            },
        ],
    )
    batch_lanes = _fold_batch_lanes(repo, "batch-982")
    snapshot, _ = _snapshot_stack_state(
        repo, batch_lanes, [50, 51],
        monkeypatch,
        _membership_for_stack([50, 51]),
        _position_ready_reader(
            {1: 50, 2: 51},
            {50: {"state": _pr_vet_state()}, 51: {"state": _pr_vet_state()}},
        ),
    )
    entry = snapshot["stacks"][0]
    assert entry["state"] == ww.STACK_STATE_INCOMPLETE
    assert entry["reason"] == ww.STACK_REASON_LAYERS_PLANNED_DISAGREED


def test_two_stacks_one_complete_one_not(tmp_path, monkeypatch):
    # axis: two stacks in one batch evaluated on their own positions
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[
            {
                "launch_id": "lane-a",
                "stack": 100,
                "layer_position": 1,
                "layers_planned": 1,
            },
            {
                "launch_id": "lane-b",
                "stack": 200,
                "layer_position": 1,
                "layers_planned": 2,
            },
        ],
    )
    batch_lanes = _fold_batch_lanes(repo, "batch-982")

    def membership_reader(*, pr, repo, **kwargs):
        if pr in (50,):
            return _stack_membership(100, [50])
        if pr in (60, 61):
            return _stack_membership(200, [60, 61])
        raise AssertionError("unexpected pr %r" % pr)

    snapshot, _ = _snapshot_stack_state(
        repo, batch_lanes, [50, 60, 61],
        monkeypatch,
        membership_reader,
        _position_ready_reader(
            {},
            {
                50: {"state": _pr_vet_state()},
                60: {"state": _pr_vet_state()},
                61: {"state": _pr_vet_state(_vet_not_ready_body())},
            },
        ),
    )
    by_stack = {entry["stack"]: entry for entry in snapshot["stacks"]}
    assert by_stack[100]["state"] == ww.STACK_STATE_COMPLETE
    assert by_stack[200]["state"] == ww.STACK_STATE_INCOMPLETE
    assert by_stack[200]["missingPositions"] == [2]


def test_incomplete_seeds_silently_complete_fires(tmp_path, monkeypatch):
    # axis: incomplete seeds baseline; next change fires
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[
            {
                "launch_id": "lane-a",
                "stack": _STACK_NUM,
                "layer_position": 1,
                "layers_planned": 2,
            },
            {
                "launch_id": "lane-b",
                "stack": _STACK_NUM,
                "layer_position": 2,
                "layers_planned": 2,
            },
        ],
    )
    vet_states = [
        {50: {"state": _pr_vet_state()}, 51: {"state": _pr_vet_state(_vet_not_ready_body())}},
        {50: {"state": _pr_vet_state()}, 51: {"state": _pr_vet_state()}},
    ]
    tick = [0]

    def read_pr_vet_state(pr, repo, **kwargs):
        spec = vet_states[min(tick[0], len(vet_states) - 1)].get(pr)
        return spec["state"], None

    monkeypatch.setattr(sc, "read_pr_vet_state", read_pr_vet_state)
    clock = [0.0]
    batch_lanes = _fold_batch_lanes(repo, "batch-982")
    incomplete_snapshot, _ = _snapshot_stack_state(
        repo, batch_lanes, [50, 51],
        monkeypatch,
        _membership_for_stack([50, 51]),
        _position_ready_reader(
            {1: 50, 2: 51},
            {
                50: {"state": _pr_vet_state()},
                51: {"state": _pr_vet_state(_vet_not_ready_body())},
            },
        ),
    )
    complete_snapshot, _ = _snapshot_stack_state(
        repo, batch_lanes, [50, 51],
        monkeypatch,
        _membership_for_stack([50, 51]),
        _position_ready_reader(
            {1: 50, 2: 51},
            {50: {"state": _pr_vet_state()}, 51: {"state": _pr_vet_state()}},
        ),
    )
    assert not ww._stack_state_fires(incomplete_snapshot, None)
    assert ww._stack_state_fires(complete_snapshot, incomplete_snapshot)
    stack_state = [None]
    seeded = {"stack_state": stack_state, "degraded": set()}
    seeded_ctx = {
        "batch_lanes": batch_lanes,
        "open_pr_numbers": [50, 51],
        "repo_root": repo,
        "deadline": time.monotonic() + 30,
        "monotonic": time.monotonic,
        "gh_run": _gh_open_prs([50, 51]),
        "membership_reader": _membership_for_stack([50, 51]),
        "env": {},
        "degraded": seeded["degraded"],
        "pr_vet_reader": read_pr_vet_state,
        "repo_slug": _TEST_REPO_SLUG,
        "stack_state": stack_state,
        "terminal_launches": [],
        "blocked_launches": [],
        "exited_launches": [],
        "stale_live_launches": [],
    }
    assert ww._payload_stack_state_changed(seeded_ctx) is None
    assert stack_state[0] == incomplete_snapshot

    stack_state = [None]

    def mono():
        return clock[0]

    def sleep(duration):
        clock[0] += duration
        tick[0] += 1

    result = ww.watch_arm(
        repo,
        "batch-982",
        max_seconds=5,
        interval_seconds=1,
        gh_run=_gh_open_prs([50, 51]),
        membership_reader=_membership_for_stack([50, 51]),
        monotonic=mono,
        sleep=sleep,
        stack_state=stack_state,
    )
    assert result["event"] == ww.EVENT_STACK_STATE_CHANGED
    assert stack_state[0]["stacks"][0]["state"] == ww.STACK_STATE_COMPLETE


def test_baseline_advances_unchanged_complete_does_not_refire(tmp_path, monkeypatch):
    # axis: baseline advances on fire; unchanged complete state does not re-fire
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[{
            "launch_id": "lane-a",
            "stack": _STACK_NUM,
            "layer_position": 1,
            "layers_planned": 2,
        }],
    )
    _patch_pr_vet(monkeypatch, {
        50: {"state": _pr_vet_state()},
        51: {"state": _pr_vet_state()},
    })
    stack_state = [None]
    run_kwargs = {
        "max_seconds": 5,
        "interval_seconds": 1,
        "gh_run": _gh_open_prs([50, 51]),
        "membership_reader": _membership_for_stack([50, 51]),
        "sleep": lambda _d: None,
        "stack_state": stack_state,
    }
    first = ww.watch_arm(
        repo, "batch-982", **run_kwargs, monotonic=_advancing_monotonic(),
    )
    assert first["event"] == ww.EVENT_STACK_STATE_CHANGED
    second = ww.watch_arm(
        repo, "batch-982", **run_kwargs, monotonic=_advancing_monotonic(),
    )
    assert second["event"] != ww.EVENT_STACK_STATE_CHANGED


def test_loop_completed_stack_passes_over_once_with_real_watch_arm(
    tmp_path, monkeypatch,
):
    # axis: shared stack_state across loop arms; unchanged complete stack fires once
    repo = _init_repo(tmp_path / "repo")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    batch_id = "batch-982"
    ll.declare_batch(repo, batch_id, 4)
    ll.append(
        repo,
        _reserved_stack(
            "lane-pos1", batch_id, ["plugins/superheroes/lib"], repo,
            _STACK_NUM, 1, 2,
        ),
    )
    ll.append(
        repo,
        _reserved_stack(
            "lane-pos2", batch_id, ["plugins/superheroes/lib"], repo,
            _STACK_NUM, 2, 2,
        ),
    )
    ll.append(
        repo,
        _reserved(
            "lane-stale-trigger", batch_id, ["plugins/superheroes/lib"], repo,
        ),
    )
    ll.append(repo, _started("lane-stale-trigger", pid=os.getpid()))
    wall = [time.time()]
    hb.stamp(
        repo,
        state="working",
        phase="watch",
        launch_id="lane-stale-trigger",
        stale_after_seconds=3,
        now=wall[0],
    )
    _patch_pr_vet(monkeypatch, {
        50: {"state": _pr_vet_state()},
        51: {"state": _pr_vet_state()},
    })
    config = tmp_path / "claude-config"
    config.mkdir(exist_ok=True)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
    clock = [0.0]

    def mono():
        return clock[0]

    def sleep(duration):
        clock[0] += duration
        wall[0] += duration

    monkeypatch.setattr(time, "time", lambda: wall[0])

    result = ww.loop(
        repo,
        batch_id,
        max_seconds=5,
        interval_seconds=1,
        gh_run=_gh_open_prs([50, 51]),
        membership_reader=_membership_for_stack([50, 51]),
        monotonic=mono,
        sleep=sleep,
    )
    assert result["event"] == ww.EVENT_LANE_STALE
    assert result["passedOverCount"] == 1
    assert len(result["passedOver"]) == 1
    assert result["passedOver"][0]["event"] == ww.EVENT_STACK_STATE_CHANGED


def test_precedence_stack_state_over_pr_set_pr_baseline_unchanged(
    tmp_path, monkeypatch,
):
    # axis: stack-state-changed wins; pr_state baseline not advanced that tick
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[
            {
                "launch_id": "lane-a",
                "stack": _STACK_NUM,
                "layer_position": 1,
                "layers_planned": 2,
            },
            {
                "launch_id": "lane-b",
                "stack": _STACK_NUM,
                "layer_position": 2,
                "layers_planned": 2,
            },
        ],
    )
    pr_sets = [{50, 51}, {50, 51, 52}]
    vet_states = [
        {50: {"state": _pr_vet_state()}, 51: {"state": _pr_vet_state(_vet_not_ready_body())}},
        {50: {"state": _pr_vet_state()}, 51: {"state": _pr_vet_state()}, 52: {"state": _pr_vet_state()}},
    ]
    tick = [0]
    pr_state = [None]

    def read_pr_vet_state(pr, repo, **kwargs):
        spec = vet_states[min(tick[0], len(vet_states) - 1)].get(pr)
        if spec is None:
            return None, {"ok": False, "reason": sc.REASON_STACK_UNREADABLE}
        return spec["state"], None

    monkeypatch.setattr(sc, "read_pr_vet_state", read_pr_vet_state)

    def membership_reader(*, pr, repo, **kwargs):
        if pr == 52:
            return _stack_membership(_STACK_NUM, [50, 51, 52])
        return _stack_membership(_STACK_NUM, [50, 51])

    idx = [0]

    def gh_run(argv, **kwargs):
        if argv[:3] == ["gh", "repo", "view"]:
            return subprocess.CompletedProcess(
                argv, 0,
                stdout=json.dumps({"nameWithOwner": _TEST_REPO_SLUG}),
                stderr="",
            )
        if argv[:3] == ["gh", "pr", "list"]:
            body = [{"number": n} for n in sorted(pr_sets[idx[0]])]
            return subprocess.CompletedProcess(
                argv, 0, stdout=json.dumps(body), stderr="",
            )
        raise AssertionError("unexpected gh argv: %r" % argv)

    clock = [0.0]

    def mono():
        return clock[0]

    def sleep(duration):
        clock[0] += duration
        tick[0] += 1
        idx[0] = min(tick[0], len(pr_sets) - 1)

    result = ww.watch_arm(
        repo,
        "batch-982",
        max_seconds=5,
        interval_seconds=1,
        gh_run=gh_run,
        membership_reader=membership_reader,
        monotonic=mono,
        sleep=sleep,
        pr_state=pr_state,
    )
    assert result["event"] == ww.EVENT_STACK_STATE_CHANGED
    assert pr_state[0] == {50, 51}


def test_draft_pr_excluded_from_ready_positions(tmp_path, monkeypatch):
    # axis: isDraft True — READY verdict does not count the position READY
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[
            {
                "launch_id": "lane-a",
                "stack": _STACK_NUM,
                "layer_position": 1,
                "layers_planned": 2,
            },
            {
                "launch_id": "lane-b",
                "stack": _STACK_NUM,
                "layer_position": 2,
                "layers_planned": 2,
            },
        ],
    )
    batch_lanes = _fold_batch_lanes(repo, "batch-982")
    snapshot, degraded = _snapshot_stack_state(
        repo, batch_lanes, [50, 51],
        monkeypatch,
        _membership_for_stack([50, 51]),
        _position_ready_reader(
            {1: 50, 2: 51},
            {
                50: {"state": _pr_vet_state()},
                51: {"state": _pr_vet_state(is_draft=True)},
            },
        ),
    )
    entry = snapshot["stacks"][0]
    assert entry["state"] == ww.STACK_STATE_INCOMPLETE
    assert entry["missingPositions"] == [2]
    assert ww.DEGRADATION_STACK_SIGNAL_UNAVAILABLE not in degraded


def test_merged_pr_excluded_from_ready_positions(tmp_path, monkeypatch):
    # axis: non-OPEN state — READY verdict does not count the position READY
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[
            {
                "launch_id": "lane-a",
                "stack": _STACK_NUM,
                "layer_position": 1,
                "layers_planned": 2,
            },
            {
                "launch_id": "lane-b",
                "stack": _STACK_NUM,
                "layer_position": 2,
                "layers_planned": 2,
            },
        ],
    )
    batch_lanes = _fold_batch_lanes(repo, "batch-982")
    snapshot, degraded = _snapshot_stack_state(
        repo, batch_lanes, [50, 51],
        monkeypatch,
        _membership_for_stack([50, 51]),
        _position_ready_reader(
            {1: 50, 2: 51},
            {
                50: {"state": _pr_vet_state()},
                51: {"state": _pr_vet_state(state="MERGED")},
            },
        ),
    )
    entry = snapshot["stacks"][0]
    assert entry["state"] == ww.STACK_STATE_INCOMPLETE
    assert entry["missingPositions"] == [2]
    assert ww.DEGRADATION_STACK_SIGNAL_UNAVAILABLE not in degraded


def test_repo_slug_resolved_once_per_run_tick(tmp_path, monkeypatch):
    # axis: one gh repo view per tick when stack snapshot and PR set both evaluate
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[
            {
                "launch_id": "lane-a",
                "stack": _STACK_NUM,
                "layer_position": 1,
                "layers_planned": 2,
            },
            {
                "launch_id": "lane-b",
                "stack": _STACK_NUM,
                "layer_position": 2,
                "layers_planned": 2,
            },
        ],
    )
    _patch_pr_vet(monkeypatch, {
        50: {"state": _pr_vet_state()},
        51: {"state": _pr_vet_state()},
        52: {"state": _pr_vet_state()},
    })
    batch_lanes = _fold_batch_lanes(repo, "batch-982")
    complete_snapshot, _ = _snapshot_stack_state(
        repo, batch_lanes, [50, 51],
        monkeypatch,
        _membership_for_stack([50, 51]),
        _position_ready_reader(
            {1: 50, 2: 51},
            {50: {"state": _pr_vet_state()}, 51: {"state": _pr_vet_state()}},
        ),
    )
    repo_view_calls = []

    def gh_run(argv, **kwargs):
        if argv[:3] == ["gh", "repo", "view"]:
            repo_view_calls.append(1)
            return subprocess.CompletedProcess(
                argv, 0,
                stdout=json.dumps({"nameWithOwner": _TEST_REPO_SLUG}),
                stderr="",
            )
        if argv[:3] == ["gh", "pr", "list"]:
            body = [{"number": n} for n in [50, 51, 52]]
            return subprocess.CompletedProcess(
                argv, 0, stdout=json.dumps(body), stderr="",
            )
        raise AssertionError("unexpected gh argv: %r" % argv)

    mono, sleep = _stack_loop_clock()
    result = ww.watch_arm(
        repo,
        "batch-982",
        max_seconds=2,
        interval_seconds=1,
        gh_run=gh_run,
        membership_reader=_membership_for_stack([50, 51, 52]),
        monotonic=mono,
        sleep=sleep,
        stack_state=[complete_snapshot],
        pr_state=[{50, 51}],
    )
    assert result["event"] == ww.EVENT_PR_SET_CHANGED
    assert len(repo_view_calls) == 1


def test_slug_resolution_failure_adds_stack_signal_degradation(
    tmp_path, monkeypatch, watcher_clock,
):
    # axis: slug read failure yields membership-unresolved and degradation
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[
            {
                "launch_id": "lane-a",
                "stack": _STACK_NUM,
                "layer_position": 1,
                "layers_planned": 2,
            },
            {
                "launch_id": "lane-b",
                "stack": _STACK_NUM,
                "layer_position": 2,
                "layers_planned": 2,
            },
        ],
    )

    def gh_run(argv, **kwargs):
        if argv[:3] == ["gh", "repo", "view"]:
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="fail")
        if argv[:3] == ["gh", "pr", "list"]:
            body = [{"number": n} for n in [50, 51]]
            return subprocess.CompletedProcess(
                argv, 0, stdout=json.dumps(body), stderr="",
            )
        raise AssertionError("unexpected gh argv: %r" % argv)

    result = ww.watch_arm(
        repo,
        "batch-982",
        max_seconds=2,
        interval_seconds=1,
        gh_run=gh_run,
        membership_reader=_membership_for_stack([50, 51]),
        sleep=watcher_clock.sleep,
    )
    assert ww.DEGRADATION_STACK_SIGNAL_UNAVAILABLE in result["degraded"]

    batch_lanes = _fold_batch_lanes(repo, "batch-982")
    degraded = set()
    snapshot = ww._compute_stack_state_snapshot(
        batch_lanes,
        [50, 51],
        repo,
        deadline=time.monotonic() + 30,
        monotonic=time.monotonic,
        gh_run=_gh_open_prs([50, 51]),
        membership_reader=_membership_for_stack([50, 51]),
        env={},
        degraded=degraded,
        repo_slug=None,
        pr_vet_reader=_position_ready_reader(
            {1: 50, 2: 51},
            {50: {"state": _pr_vet_state()}, 51: {"state": _pr_vet_state()}},
        ),
    )
    assert snapshot["stacks"][0]["reason"] == ww.STACK_REASON_MEMBERSHIP_UNRESOLVED


def test_unrelated_ignore_pair_does_not_suppress_stack_state_event(
    tmp_path, monkeypatch,
):
    # axis: unrelated valid ignore pair does not suppress stack-state-changed
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[{
            "launch_id": "lane-a",
            "stack": _STACK_NUM,
            "layer_position": 1,
            "layers_planned": 2,
        }],
    )
    _patch_pr_vet(monkeypatch, {
        50: {"state": _pr_vet_state()},
        51: {"state": _pr_vet_state()},
    })
    result = ww.watch_arm(
        repo,
        "batch-982",
        max_seconds=2,
        interval_seconds=1,
        gh_run=_gh_open_prs([50, 51]),
        membership_reader=_membership_for_stack([50, 51]),
        ignore_events=(("lane-a", ww.EVENT_LANE_TERMINAL),),
    )
    assert result["event"] == ww.EVENT_STACK_STATE_CHANGED


def test_ignore_launch_stack_snapshot_reads_terminal_layers_planned(
    tmp_path, monkeypatch,
):
    # axis: ignored terminal lane still supplies layersPlanned and occupied position
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[
            {
                "launch_id": "lane-live",
                "stack": _STACK_NUM,
                "layer_position": 1,
                "started": True,
            },
            {
                "launch_id": "lane-term",
                "stack": _STACK_NUM,
                "layer_position": 2,
                "layers_planned": 2,
                "started": True,
                "terminal": True,
            },
        ],
    )
    degraded = set()
    ledger_observed = [False]
    batch_lanes, live_lanes, ledger_readable = ww._derive_batch_lanes(
        repo, "batch-982", None, degraded, ("lane-term",), ledger_observed,
    )
    assert ledger_readable
    assert "lane-term" in batch_lanes
    assert batch_lanes["lane-term"]["layersPlanned"] == 2
    assert "lane-term" not in live_lanes
    snapshot, _ = _snapshot_stack_state(
        repo, batch_lanes, [50],
        monkeypatch,
        _membership_for_stack([50]),
        _position_ready_reader(
            {1: 50},
            {50: {"state": _pr_vet_state()}},
        ),
    )
    entry = snapshot["stacks"][0]
    assert entry["layersPlanned"] == 2
    assert ww._occupied_layer_positions(batch_lanes, _STACK_NUM) == {1, 2}
    assert not any(
        flag["flag"] == ww.FLAG_IDLE_SEAT_LAUNCHABLE_CHILD
        for flag in snapshot["flags"]
    )


def test_stack_state_fires_no_baseline_incomplete_with_flag(tmp_path, monkeypatch):
    # axis: no baseline fires when incomplete snapshot carries idle-seat flag
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[
            {
                "launch_id": "lane-pos1",
                "stack": _STACK_NUM,
                "layer_position": 1,
                "layers_planned": 3,
            },
            {
                "launch_id": "lane-pos2",
                "stack": _STACK_NUM,
                "layer_position": 2,
                "layers_planned": 3,
            },
        ],
    )
    batch_lanes = _fold_batch_lanes(repo, "batch-982")
    snapshot, _ = _snapshot_stack_state(
        repo, batch_lanes, [50, 51],
        monkeypatch,
        _membership_for_stack([50, 51]),
        _position_ready_reader(
            {1: 50, 2: 51},
            {50: {"state": _pr_vet_state()}, 51: {"state": _pr_vet_state()}},
        ),
    )
    assert snapshot["stacks"][0]["state"] == ww.STACK_STATE_INCOMPLETE
    expected_flag = {
        "flag": ww.FLAG_IDLE_SEAT_LAUNCHABLE_CHILD,
        "stack": _STACK_NUM,
        "position": 2,
    }
    assert expected_flag in snapshot["flags"]
    assert ww._stack_state_fires(snapshot, None)
    payload = ww._payload_stack_state_changed({
        "batch_lanes": batch_lanes,
        "open_pr_numbers": [50, 51],
        "repo_root": repo,
        "deadline": time.monotonic() + 30,
        "monotonic": time.monotonic,
        "gh_run": _gh_open_prs([50, 51]),
        "membership_reader": _membership_for_stack([50, 51]),
        "env": {},
        "degraded": set(),
        "repo_slug": _TEST_REPO_SLUG,
        "pr_vet_reader": _position_ready_reader(
            {1: 50, 2: 51},
            {50: {"state": _pr_vet_state()}, 51: {"state": _pr_vet_state()}},
        ),
        "stack_state": [None],
        "terminal_launches": [],
        "blocked_launches": [],
        "exited_launches": [],
        "stale_live_launches": [],
    })
    assert payload is not None
    assert expected_flag in payload["flags"]


def test_stack_state_fires_no_baseline_incomplete_no_flags(tmp_path, monkeypatch):
    # axis: no baseline incomplete without flags seeds silently
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[
            {
                "launch_id": "lane-a",
                "stack": _STACK_NUM,
                "layer_position": 1,
                "layers_planned": 2,
            },
            {
                "launch_id": "lane-b",
                "stack": _STACK_NUM,
                "layer_position": 2,
                "layers_planned": 2,
            },
        ],
    )
    batch_lanes = _fold_batch_lanes(repo, "batch-982")
    snapshot, _ = _snapshot_stack_state(
        repo, batch_lanes, [50, 51],
        monkeypatch,
        _membership_for_stack([50, 51]),
        _position_ready_reader(
            {1: 50, 2: 51},
            {
                50: {"state": _pr_vet_state()},
                51: {"state": _pr_vet_state(_vet_not_ready_body())},
            },
        ),
    )
    assert snapshot["stacks"][0]["state"] == ww.STACK_STATE_INCOMPLETE
    assert snapshot["flags"] == []
    assert not ww._stack_state_fires(snapshot, None)


def test_stack_state_changed_emits_flags_on_first_arm_with_idle_seat(
    tmp_path, monkeypatch,
):
    # axis: end-to-end stack-state-changed returns idle-seat flag on first arm
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[
            {
                "launch_id": "lane-pos1",
                "stack": _STACK_NUM,
                "layer_position": 1,
                "layers_planned": 3,
            },
            {
                "launch_id": "lane-pos2",
                "stack": _STACK_NUM,
                "layer_position": 2,
                "layers_planned": 3,
            },
        ],
    )
    _patch_pr_vet(monkeypatch, {
        50: {"state": _pr_vet_state()},
        51: {"state": _pr_vet_state()},
    })
    mono, sleep = _stack_loop_clock()
    result = ww.watch_arm(
        repo,
        "batch-982",
        max_seconds=2,
        interval_seconds=1,
        gh_run=_gh_open_prs([50, 51]),
        membership_reader=_membership_for_stack([50, 51]),
        monotonic=mono,
        sleep=sleep,
    )
    assert result["event"] == ww.EVENT_STACK_STATE_CHANGED
    assert {
        "flag": ww.FLAG_IDLE_SEAT_LAUNCHABLE_CHILD,
        "stack": _STACK_NUM,
        "position": 2,
    } in result["flags"]


def test_idle_seat_launchable_child_flag_present_and_absent(tmp_path, monkeypatch):
    # axis: idle-seat-launchable-child when next position has no lane and no member PR;
    # absent when a lane or a member PR occupies it, or at top
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[
            {
                "launch_id": "lane-pos1",
                "stack": _STACK_NUM,
                "layer_position": 1,
                "layers_planned": 3,
            },
            {
                "launch_id": "lane-pos2",
                "stack": _STACK_NUM,
                "layer_position": 2,
                "layers_planned": 3,
            },
        ],
    )
    batch_lanes = _fold_batch_lanes(repo, "batch-982")
    snapshot, _ = _snapshot_stack_state(
        repo, batch_lanes, [50, 51],
        monkeypatch,
        _membership_for_stack([50, 51]),
        _position_ready_reader(
            {1: 50, 2: 51},
            {50: {"state": _pr_vet_state()}, 51: {"state": _pr_vet_state()}},
        ),
    )
    flags = snapshot["flags"]
    assert {"flag": ww.FLAG_IDLE_SEAT_LAUNCHABLE_CHILD, "stack": _STACK_NUM, "position": 2} in flags
    assert not any(
        entry["position"] == 1 for entry in flags
        if entry["flag"] == ww.FLAG_IDLE_SEAT_LAUNCHABLE_CHILD
    )

    snapshot, _ = _snapshot_stack_state(
        repo, batch_lanes, [50, 51, 52],
        monkeypatch,
        _membership_for_stack([50, 51, 52]),
        _position_ready_reader(
            {1: 50, 2: 51, 3: 52},
            {
                50: {"state": _pr_vet_state()},
                51: {"state": _pr_vet_state()},
                52: {"state": _pr_vet_state()},
            },
        ),
    )
    assert snapshot["flags"] == []


def test_idle_seat_launchable_child_incomplete_unlaunched_position(
    tmp_path, monkeypatch,
):
    # axis: incomplete stack with unlaunched next layer still reports idle-seat flag
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[
            {
                "launch_id": "lane-pos1",
                "stack": _STACK_NUM,
                "layer_position": 1,
                "layers_planned": 3,
            },
            {
                "launch_id": "lane-pos2",
                "stack": _STACK_NUM,
                "layer_position": 2,
                "layers_planned": 3,
            },
        ],
    )
    batch_lanes = _fold_batch_lanes(repo, "batch-982")
    snapshot, _ = _snapshot_stack_state(
        repo, batch_lanes, [50, 51],
        monkeypatch,
        _membership_for_stack([50, 51]),
        _position_ready_reader(
            {1: 50, 2: 51},
            {50: {"state": _pr_vet_state()}, 51: {"state": _pr_vet_state()}},
        ),
    )
    entry = snapshot["stacks"][0]
    assert entry["state"] == ww.STACK_STATE_INCOMPLETE
    assert entry["missingPositions"] == [3]
    assert {
        "flag": ww.FLAG_IDLE_SEAT_LAUNCHABLE_CHILD,
        "stack": _STACK_NUM,
        "position": 2,
    } in snapshot["flags"]


def test_idle_seat_not_flagged_when_next_position_has_not_ready_member(
    tmp_path, monkeypatch,
):
    # axis: a not-READY member PR at the next position occupies it; no idle-seat flag
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[
            {
                "launch_id": "lane-pos1",
                "stack": _STACK_NUM,
                "layer_position": 1,
                "layers_planned": 3,
            },
            {
                "launch_id": "lane-pos2",
                "stack": _STACK_NUM,
                "layer_position": 2,
                "layers_planned": 3,
            },
        ],
    )
    batch_lanes = _fold_batch_lanes(repo, "batch-982")
    snapshot, _ = _snapshot_stack_state(
        repo, batch_lanes, [50, 51, 52],
        monkeypatch,
        _membership_for_stack([50, 51, 52]),
        _position_ready_reader(
            {1: 50, 2: 51, 3: 52},
            {
                50: {"state": _pr_vet_state()},
                51: {"state": _pr_vet_state()},
                52: {"state": _pr_vet_state(_vet_not_ready_body())},
            },
        ),
    )
    entry = snapshot["stacks"][0]
    assert entry["state"] == ww.STACK_STATE_INCOMPLETE
    assert entry["missingPositions"] == [3]
    assert snapshot["flags"] == []


def test_idle_seat_no_flags_layers_planned_unknown(tmp_path, monkeypatch):
    # axis: layers-planned-unknown reports no idle-seat flags
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[{
            "launch_id": "lane-a",
            "stack": _STACK_NUM,
            "layer_position": 1,
        }],
    )
    batch_lanes = _fold_batch_lanes(repo, "batch-982")
    snapshot, _ = _snapshot_stack_state(
        repo, batch_lanes, [50],
        monkeypatch,
        _membership_for_stack([50]),
        _position_ready_reader({1: 50}, {50: {"state": _pr_vet_state()}}),
    )
    assert snapshot["stacks"][0]["reason"] == ww.STACK_REASON_LAYERS_PLANNED_UNKNOWN
    assert snapshot["flags"] == []


def test_idle_seat_no_flags_layers_planned_disagreed(tmp_path, monkeypatch):
    # axis: layers-planned-disagreed reports no idle-seat flags
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[
            {
                "launch_id": "lane-a",
                "stack": _STACK_NUM,
                "layer_position": 1,
                "layers_planned": 2,
            },
            {
                "launch_id": "lane-b",
                "stack": _STACK_NUM,
                "layer_position": 2,
                "layers_planned": 3,
            },
        ],
    )
    batch_lanes = _fold_batch_lanes(repo, "batch-982")
    snapshot, _ = _snapshot_stack_state(
        repo, batch_lanes, [50, 51],
        monkeypatch,
        _membership_for_stack([50, 51]),
        _position_ready_reader(
            {1: 50, 2: 51},
            {50: {"state": _pr_vet_state()}, 51: {"state": _pr_vet_state()}},
        ),
    )
    assert snapshot["stacks"][0]["reason"] == ww.STACK_REASON_LAYERS_PLANNED_DISAGREED
    assert snapshot["flags"] == []


def test_idle_seat_no_flags_membership_unresolved(tmp_path, monkeypatch):
    # axis: membership-unresolved reports no idle-seat flags
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[{
            "launch_id": "lane-a",
            "stack": _STACK_NUM,
            "layer_position": 1,
            "layers_planned": 2,
        }],
    )
    batch_lanes = _fold_batch_lanes(repo, "batch-982")

    def refusing_membership(**kwargs):
        return {"ok": False, "reason": sc.REASON_STACK_UNREADABLE}

    snapshot, _ = _snapshot_stack_state(
        repo, batch_lanes, [50, 51],
        monkeypatch,
        refusing_membership,
        _position_ready_reader({1: 50}, {50: {"state": _pr_vet_state()}}),
    )
    assert snapshot["stacks"][0]["reason"] == ww.STACK_REASON_MEMBERSHIP_UNRESOLVED
    assert snapshot["flags"] == []


def _stack_membership_members(stack_number, member_rows):
    return {
        "ok": True,
        "reason": None,
        "stack": {
            "number": stack_number,
            "size": len(member_rows),
            "baseRefName": "main",
        },
        "members": member_rows,
    }


def test_resolve_pr_stack_groups_same_stack_position_order_not_append():
    # axis: same stack number leaves prs in position order, not append order
    degraded = set()

    def membership_reader(*, pr, repo, **kwargs):
        if pr == 30:
            return _stack_membership_members(1, [{"position": 1, "number": 30}])
        if pr == 40:
            return _stack_membership_members(
                1,
                [
                    {"position": 2, "number": 40},
                    {"position": 1, "number": 30},
                ],
            )
        raise AssertionError("unexpected pr %r" % pr)

    stacks, ungrouped, _ = ww._resolve_pr_stack_groups(
        "/fake/repo",
        deadline=time.monotonic() + 30,
        monotonic=time.monotonic,
        gh_run=lambda *args, **kwargs: _gh_repo_view_proc(),
        membership_reader=membership_reader,
        env={},
        degraded=degraded,
        changed_prs=[40, 30],
        repo_slug=_TEST_REPO_SLUG,
    )

    assert stacks == [{"stack": 1, "prs": [30, 40]}]
    assert ungrouped == []


def test_pr_set_changed_removed_pr_grouped_like_added(tmp_path, monkeypatch):
    # axis: removed pull request grouped exactly as an added one
    pr_sets = [{10, 30, 40}, {10, 40}]
    calls = []

    def membership_reader(*, pr, repo, **kwargs):
        calls.append(pr)
        return _stack_membership(100, [30, 40])

    result = _run_pr_set_changed(
        tmp_path, monkeypatch, pr_sets, membership_reader,
    )

    assert result["event"] == "pr-set-changed"
    assert result["prsRemoved"] == [30]
    assert result["stacks"] == [{"stack": 100, "prs": [30, 40]}]
    assert calls == [30]


def test_gh_scrub_removes_routing_vars_and_ledger_root(tmp_path, monkeypatch):
    # axis: gh child env removes _GH_SCRUB_VARS plus ledger root; unrelated var stays
    repo = _init_repo(tmp_path / "repo")
    store_root = _ledger_env(tmp_path, monkeypatch)
    custom_env = dict(os.environ)
    custom_env[ll.LEDGER_ROOT_ENV] = store_root
    custom_env["WW_UNRELATED_KEEP"] = "present"
    for var in _EXPECTED_SCRUBBED:
        custom_env[var] = _SCRUB_PROBE_VALUES.get(var, "/definitely/not/right")
    seen = []

    def gh_run(argv, **kwargs):
        seen.append(kwargs.get("env"))
        return _noop_gh_run(argv, **kwargs)

    result = ww.watch_arm(
        repo, "batch-982", max_seconds=2, interval_seconds=1,
        env=custom_env, gh_run=gh_run,
    )
    assert result["event"] == "timer"
    assert len(seen) >= 1
    child_env = seen[0]
    stripped = set(_EXPECTED_SCRUBBED) | {ll.LEDGER_ROOT_ENV}
    for key in stripped:
        assert key not in child_env
    assert child_env.get("WW_UNRELATED_KEEP") == "present"


def test_stack_budget_exhausted_mid_walk_remaining_incomplete(tmp_path, monkeypatch):
    # axis: budget exhaustion mid-walk leaves remaining stacks incomplete with degradation
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[
            {
                "launch_id": "lane-a",
                "stack": 100,
                "layer_position": 1,
                "layers_planned": 1,
            },
            {
                "launch_id": "lane-b",
                "stack": 200,
                "layer_position": 1,
                "layers_planned": 1,
            },
        ],
    )
    mono = [1000.0]
    reader_calls = []

    def membership_reader(*, pr, repo, **kwargs):
        reader_calls.append(pr)
        if pr == 50:
            mono[0] += 10.0
            return _stack_membership(100, [50])
        return _stack_membership(200, [60])

    batch_lanes = _fold_batch_lanes(repo, "batch-982")
    degraded = set()
    snapshot = ww._compute_stack_state_snapshot(
        batch_lanes,
        [50, 60],
        repo,
        deadline=1005.0,
        monotonic=lambda: mono[0],
        gh_run=_gh_open_prs([50, 60]),
        membership_reader=membership_reader,
        env={},
        degraded=degraded,
        repo_slug=_TEST_REPO_SLUG,
    )
    by_stack = {entry["stack"]: entry for entry in snapshot["stacks"]}
    assert reader_calls == [50]
    assert ww.DEGRADATION_STACK_SIGNAL_UNAVAILABLE in degraded
    assert by_stack[100]["state"] == ww.STACK_STATE_INCOMPLETE
    assert by_stack[200]["state"] == ww.STACK_STATE_INCOMPLETE
    assert by_stack[200]["reason"] == ww.STACK_REASON_MEMBERSHIP_UNRESOLVED


def test_stack_position_ready_budget_exhausted(tmp_path, monkeypatch):
    # axis: position-ready walk budget exhaustion marks every position missing
    repo = _init_repo(tmp_path / "repo")
    _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[{
            "launch_id": "lane-a",
            "stack": _STACK_NUM,
            "layer_position": 1,
            "layers_planned": 2,
        }],
    )
    batch_lanes = _fold_batch_lanes(repo, "batch-982")
    degraded = set()
    mono = [1000.0]
    ready_reads = [0]
    base_reader = _position_ready_reader(
        {1: 50, 2: 51},
        {50: {"state": _pr_vet_state()}, 51: {"state": _pr_vet_state()}},
    )

    def pr_vet_reader(pr_number, repo_slug, **kwargs):
        ready_reads[0] += 1
        if ready_reads[0] == 1:
            mono[0] += 4.01
        return base_reader(pr_number, repo_slug, **kwargs)

    snapshot = ww._compute_stack_state_snapshot(
        batch_lanes,
        [50, 51],
        repo,
        deadline=1005.0,
        monotonic=lambda: mono[0],
        gh_run=_gh_open_prs([50, 51]),
        membership_reader=_membership_for_stack([50, 51]),
        env={},
        degraded=degraded,
        repo_slug=_TEST_REPO_SLUG,
        pr_vet_reader=pr_vet_reader,
    )
    entry = snapshot["stacks"][0]
    assert entry["state"] == ww.STACK_STATE_INCOMPLETE
    assert entry["missingPositions"] == [1, 2]
    assert entry["reason"] is None
    assert ww.DEGRADATION_STACK_SIGNAL_UNAVAILABLE in degraded


def test_stack_state_watch_read_only_no_store_mutation(tmp_path, monkeypatch):
    # axis: fail-closed — watcher writes nothing to the store during stack evaluation
    repo = _init_repo(tmp_path / "repo")
    store_root = _setup_stack_batch(
        repo, tmp_path, monkeypatch,
        launch_specs=[{
            "launch_id": "lane-a",
            "stack": _STACK_NUM,
            "layer_position": 1,
            "layers_planned": 2,
        }],
    )
    _patch_pr_vet(monkeypatch, {
        50: {"state": _pr_vet_state()},
        51: {"state": _pr_vet_state()},
    })
    before = _snapshot_files(store_root)
    ww.watch_arm(
        repo,
        "batch-982",
        max_seconds=2,
        interval_seconds=1,
        gh_run=_gh_open_prs([50, 51]),
        membership_reader=_membership_for_stack([50, 51]),
    )
    after = _snapshot_files(store_root)
    assert before == after

