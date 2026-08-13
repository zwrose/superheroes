import json
import os
import subprocess
import sys
import time

import pytest

import heartbeat as hb
import launch_ledger as ll
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


# --- refusals R1–R5 -----------------------------------------------------------


def test_refusal_r1_batch_invalid_cli():
    proc = _run_cli([
        "run", "--repo-root", os.getcwd(), "--batch", "   ",
        "--max-seconds", "1", "--interval-seconds", "1",
    ])
    out = json.loads(proc.stdout.strip())
    assert proc.returncode == 1
    assert out == {"batchId": "   ", "ok": False, "reason": "batch-invalid"}


def test_refusal_r1_batch_invalid_run(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    result = ww.run(repo, None)
    assert result["ok"] is False
    assert result["reason"] == "batch-invalid"


def test_refusal_r2_interval_invalid_cli():
    proc = _run_cli([
        "run", "--repo-root", os.getcwd(), "--batch", "b",
        "--max-seconds", "2", "--interval-seconds", "0",
    ])
    out = json.loads(proc.stdout.strip())
    assert proc.returncode == 1
    assert out["reason"] == "interval-invalid"
    assert out["ok"] is False
    assert out["batchId"] == "b"


def test_refusal_r2_interval_bool_run(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    result = ww.run(repo, "batch-982", interval_seconds=True, max_seconds=2)
    assert result["reason"] == "interval-invalid"


def test_refusal_r3_max_seconds_invalid_cli():
    proc = _run_cli([
        "run", "--repo-root", os.getcwd(), "--batch", "b",
        "--max-seconds", "0", "--interval-seconds", "1",
    ])
    out = json.loads(proc.stdout.strip())
    assert proc.returncode == 1
    assert out["reason"] == "max-seconds-invalid"


def test_refusal_r3_max_seconds_bool_run(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    result = ww.run(repo, "batch-982", max_seconds=False, interval_seconds=1)
    assert result["reason"] == "max-seconds-invalid"


def test_refusal_r4_repo_root_invalid_cli():
    proc = _run_cli([
        "run", "--repo-root", "/nonexistent/ww-r4", "--batch", "b",
        "--max-seconds", "1", "--interval-seconds", "1",
    ])
    out = json.loads(proc.stdout.strip())
    assert proc.returncode == 1
    assert out["reason"] == "repo-root-invalid"
    assert out["batchId"] == "b"


def test_refusal_r5_store_unresolvable(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    result = ww.run(str(plain), "batch-982", max_seconds=1, interval_seconds=1)
    assert result["ok"] is False
    assert result["reason"] == "store-unresolvable"
    assert result["batchId"] == "batch-982"


# --- events E1–E5 -------------------------------------------------------------


def test_event_e1_lane_terminal(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_live_lane(repo, tmp_path, monkeypatch, stamp_state="handback")
    result = ww.run(repo, "batch-982", max_seconds=2, interval_seconds=60)
    assert result["ok"] is True
    assert result["event"] == "lane-terminal"
    assert result["batchId"] == "batch-982"
    assert result["launchId"] == "lane-a"
    assert result["launches"] == [{"launchId": "lane-a", "state": "handback"}]
    assert result["degraded"] == []


def test_event_e2_lane_blocked(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_live_lane(repo, tmp_path, monkeypatch, stamp_state="blocked")
    result = ww.run(repo, "batch-982", max_seconds=2, interval_seconds=60)
    assert result["ok"] is True
    assert result["event"] == "lane-blocked"
    assert result["launchId"] == "lane-a"
    assert result["launches"] == [{"launchId": "lane-a", "state": "blocked"}]


def test_event_e3_builder_exited(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    dead_pid = 999999999
    _setup_live_lane(repo, tmp_path, monkeypatch, pid=dead_pid)
    result = ww.run(repo, "batch-982", max_seconds=2, interval_seconds=60)
    assert result["ok"] is True
    assert result["event"] == "builder-exited"
    assert result["pids"] == [dead_pid]
    assert result["launches"] == [{"launchId": "lane-a", "pid": dead_pid}]


def test_event_e4_pr_set_changed(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    calls = []

    def gh_run(argv, **kwargs):
        calls.append({"argv": list(argv), "cwd": kwargs.get("cwd")})
        stdout = json.dumps([{"number": 1}, {"number": 3}])
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    pr_sets = [{1, 2}, {1, 3}]
    idx = [0]

    def gh_run_seq(argv, **kwargs):
        calls.append({"argv": list(argv), "cwd": kwargs.get("cwd")})
        stdout = json.dumps([{"number": n} for n in sorted(pr_sets[idx[0]])])
        idx[0] += 1
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    result = ww.run(
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
    result = ww.run(
        repo, "batch-982", max_seconds=1, interval_seconds=60, gh_run=_noop_gh_run,
    )
    assert result["ok"] is True
    assert result["event"] == "timer"
    assert result["batchId"] == "batch-982"
    assert result["degraded"] == []


# --- acceptance paths ---------------------------------------------------------


def test_acceptance_pid_exit(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    dead = 888888888
    _setup_live_lane(repo, tmp_path, monkeypatch, pid=dead)
    result = ww.run(repo, "batch-982", max_seconds=2, interval_seconds=60)
    assert result["event"] == "builder-exited"
    assert result["pids"] == [dead]


def test_acceptance_heartbeat_flip(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_live_lane(repo, tmp_path, monkeypatch, stamp_state="parked")
    result = ww.run(repo, "batch-982", max_seconds=2, interval_seconds=60)
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

    result = ww.run(
        repo, "batch-982", max_seconds=4, interval_seconds=1, gh_run=gh_run,
    )
    assert result["event"] == "pr-set-changed"
    assert result["prsAdded"] == [11]


def test_acceptance_timer(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    result = ww.run(
        repo, "batch-982", max_seconds=1, interval_seconds=10, gh_run=_noop_gh_run,
    )
    assert result["event"] == "timer"


# --- precedence ---------------------------------------------------------------


def test_precedence_terminal_beats_builder_exited(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    dead = 777777777
    _setup_live_lane(repo, tmp_path, monkeypatch, pid=dead, stamp_state="handback")
    result = ww.run(repo, "batch-982", max_seconds=2, interval_seconds=60)
    assert result["event"] == "lane-terminal"
    assert result["event"] != "builder-exited"


# --- lane-blocked vs working --------------------------------------------------


def test_lane_blocked_fires_e2_working_fires_nothing(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_live_lane(repo, tmp_path, monkeypatch, pid=os.getpid(), stamp_state="working")
    result = ww.run(
        repo, "batch-982", max_seconds=1, interval_seconds=1, gh_run=_noop_gh_run,
    )
    assert result["event"] == "timer"


# --- mid-watch launch ---------------------------------------------------------


def test_mid_watch_launch_detected_within_one_interval(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 2)
    dead = 666666666

    def sleep_fn(duration):
        ll.append(repo, _reserved("lane-late", "batch-982", ["plugins/superheroes/lib"], repo))
        ll.append(repo, _started("lane-late", pid=dead))

    result = ww.run(
        repo, "batch-982", max_seconds=3, interval_seconds=1, sleep=sleep_fn,
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
    result = ww.run(repo, "batch-982", max_seconds=1, interval_seconds=1, gh_run=_noop_gh_run)
    assert result["event"] == "timer"


# --- reserved never started / retried lane ------------------------------------


def test_reserved_never_started_no_event(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 1)
    ll.append(repo, _reserved("lane-b", "batch-982", ["plugins/superheroes/lib"], repo))
    result = ww.run(repo, "batch-982", max_seconds=1, interval_seconds=1, gh_run=_noop_gh_run)
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
    result = ww.run(repo, "batch-982", max_seconds=1, interval_seconds=1, gh_run=_noop_gh_run)
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

    result = ww.run(
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

    result = ww.run(
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

    result = ww.run(
        repo, "batch-982", max_seconds=2, interval_seconds=1, gh_run=gh_run,
    )
    assert result["event"] == "timer"
    assert "pr-signal-unavailable" in result["degraded"]


def test_gh_nonzero_exit_adds_degradation_no_event(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)

    def gh_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="fail")

    result = ww.run(
        repo, "batch-982", max_seconds=2, interval_seconds=1, gh_run=gh_run,
    )
    assert result["event"] == "timer"
    assert "pr-signal-unavailable" in result["degraded"]


def test_gh_bad_json_adds_degradation_no_event(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)

    def gh_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout="not-json", stderr="")

    result = ww.run(
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

    result = ww.run(
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

    result = ww.run(
        repo, "batch-982", max_seconds=5, interval_seconds=60,
        monotonic=mono, sleep=fake_sleep,
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

    result = ww.run(
        repo, "batch-982", max_seconds=2, interval_seconds=60,
        monotonic=mono, sleep=fake_sleep,
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
    ww.run(repo, "batch-982", max_seconds=1, interval_seconds=1)
    after = _snapshot_files(store_root)
    assert set(after.keys()) == before_paths
    assert before == after
    assert not any(
        p.endswith(ll.LEDGER_NAME + _LEDGER_LOCK_SUFFIX) for p in after
    )


# --- CLI smoke ----------------------------------------------------------------


def test_cli_refusal_exit_one(tmp_path):
    proc = _run_cli([
        "run", "--repo-root", str(tmp_path / "missing"), "--batch", "b",
        "--max-seconds", "1", "--interval-seconds", "1",
    ])
    assert proc.returncode == 1
    out = json.loads(proc.stdout.strip())
    assert out["ok"] is False


def test_cli_event_exit_zero(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    proc = _run_cli([
        "run", "--repo-root", repo, "--batch", "batch-982",
        "--max-seconds", "1", "--interval-seconds", "1",
    ])
    assert proc.returncode == 0
    out = json.loads(proc.stdout.strip())
    assert out["ok"] is True
    assert out["event"] == "timer"
