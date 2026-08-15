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


def test_refusal_internal_error_on_read_exception(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)

    def raiser(repo_root, env=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(ww.ll, "read", raiser)
    result = ww.run(repo, "batch-982", max_seconds=1, interval_seconds=1)
    assert result["ok"] is False
    assert result["reason"] == "internal-error"
    exit_code = ww.main([
        "wave_watch.py", "run", "--repo-root", repo, "--batch", "batch-982",
        "--max-seconds", "1", "--interval-seconds", "1",
    ])
    assert exit_code == 1


# --- events E1–E5 -------------------------------------------------------------


def test_event_e1_lane_terminal(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_live_lane(repo, tmp_path, monkeypatch, stamp_state="handback")
    result = ww.run(repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run)
    assert result["ok"] is True
    assert result["event"] == "lane-terminal"
    assert result["batchId"] == "batch-982"
    assert result["launchId"] == "lane-a"
    assert result["launches"] == [{"launchId": "lane-a", "state": "handback"}]
    assert result["degraded"] == []


def test_event_e2_lane_blocked(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_live_lane(repo, tmp_path, monkeypatch, stamp_state="blocked")
    result = ww.run(repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run)
    assert result["ok"] is True
    assert result["event"] == "lane-blocked"
    assert result["launchId"] == "lane-a"
    assert result["launches"] == [{"launchId": "lane-a", "state": "blocked"}]


def test_event_e3_builder_exited(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    dead_pid = 999999999
    _setup_live_lane(repo, tmp_path, monkeypatch, pid=dead_pid)
    result = ww.run(repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run)
    assert result["ok"] is True
    assert result["event"] == "builder-exited"
    assert result["pids"] == [dead_pid]
    assert result["launches"] == [{"launchId": "lane-a", "pid": dead_pid}]


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
    result = ww.run(
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
    result = ww.run(
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
    result = ww.run(
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
    result = ww.run(
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

    result = ww.run(
        repo, "batch-982", max_seconds=2, interval_seconds=1,
        monotonic=mono, sleep=fake_sleep, gh_run=_noop_gh_run,
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

    result = ww.run(
        repo, "batch-982", max_seconds=2, interval_seconds=1,
        monotonic=mono, sleep=fake_sleep, gh_run=_noop_gh_run,
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
    result = ww.run(
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
    result = ww.run(
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
    result = ww.run(
        repo, "batch-982", max_seconds=2, interval_seconds=1, gh_run=_noop_gh_run,
    )
    assert result["ok"] is False
    assert result["reason"] == ww.REFUSAL_LEDGER_UNREADABLE


def test_missing_ledger_never_observed_emits_timer(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    result = ww.run(
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

    result = ww.run(
        repo, "batch-982", max_seconds=2, interval_seconds=1,
        monotonic=mono, sleep=fake_sleep, gh_run=_noop_gh_run,
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

    result = ww.run(
        repo, "batch-982", max_seconds=2, interval_seconds=1,
        monotonic=mono, sleep=fake_sleep, gh_run=gh_advance,
    )
    assert result["ok"] is False
    assert result["reason"] == ww.REFUSAL_LEDGER_UNREADABLE


# --- lane-stale (INV-2) -------------------------------------------------------


def test_lane_stale_working_state_with_live_pid(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_stale_lane(repo, tmp_path, monkeypatch, stamp_state="working")
    result = ww.run(
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
    result = ww.run(
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
    result = ww.run(
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
    result = ww.run(
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


def test_stale_heartbeat_never_started_no_lane_stale(tmp_path, monkeypatch):
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
    assert hb.read_heartbeat(repo, "lane-a")["class"] == "stale"
    result = ww.run(
        repo, "batch-982", max_seconds=1, interval_seconds=1, gh_run=_noop_gh_run,
    )
    assert result["event"] == "timer"
    assert result["event"] != "lane-stale"


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
    result = ww.run(
        repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run,
    )
    assert result["event"] == "lane-blocked"
    assert result["event"] != "lane-stale"


def test_ignore_launch_suppresses_stale_lane(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_stale_lane(repo, tmp_path, monkeypatch)
    result = ww.run(
        repo, "batch-982", max_seconds=2, interval_seconds=60,
        ignore_launch_ids=("lane-a",), gh_run=_noop_gh_run,
    )
    assert result["event"] == "timer"
    assert result["event"] != "lane-stale"


def test_precedence_pr_set_changed_beats_lane_stale(tmp_path, monkeypatch):
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

    result = ww.run(
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
    result = ww.run(
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
    result = ww.run(
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
    result = ww.run(repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run)
    assert result["event"] == "builder-exited"
    assert result["pids"] == [dead]


def test_acceptance_heartbeat_flip(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_live_lane(repo, tmp_path, monkeypatch, stamp_state="parked")
    result = ww.run(repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run)
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
    result = ww.run(repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run)
    assert result["event"] == "lane-terminal"
    assert result["event"] != "builder-exited"


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
    result = ww.run(repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run)
    assert result["event"] == "lane-terminal"
    assert result["launchId"] == "lane-a"
    assert result["alsoObserved"] == {"blocked": ["lane-b"]}


def test_ignore_launch_suppresses_lane_event(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    dead = 777777777
    _setup_live_lane(repo, tmp_path, monkeypatch, pid=dead, stamp_state="handback")
    result = ww.run(
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
        "--max-seconds", "2", "--interval-seconds", "60",
        "--ignore-launch", "lane-a",
    ])
    assert proc.returncode == 0
    out = json.loads(proc.stdout.strip())
    assert out["event"] == "timer"


# --- lane-blocked vs working --------------------------------------------------


def test_working_lane_fires_nothing(tmp_path, monkeypatch):
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
        monotonic=mono, sleep=fake_sleep, gh_run=_noop_gh_run,
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
        monotonic=mono, sleep=fake_sleep, gh_run=_noop_gh_run,
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
    ww.run(repo, "batch-982", max_seconds=1, interval_seconds=1, gh_run=_noop_gh_run)
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

    result = ww.run(
        repo, "batch-982", max_seconds=1, interval_seconds=1,
        env=custom_env, gh_run=gh_run,
    )
    assert result["event"] == "timer"
    assert len(seen) >= 1
    assert seen[0]["WW_TEST_MARKER"] == "reaches-gh-child"


# Literal list, deliberately NOT read from ww._GIT_SCRUB_VARS: a name removed from
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

    result = ww.run(
        repo, "batch-982", max_seconds=1, interval_seconds=1,
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

    result = ww.run(
        repo, "batch-982", max_seconds=1, interval_seconds=1,
        env=custom_env, gh_run=gh_run,
    )
    assert result["event"] == "timer"
    assert seen[0].get("GH_TOKEN") == "test-token-value"
    assert seen[0].get("GH_CONFIG_DIR") == "/some/config/dir"


def test_at_deadline_skips_gh_discloses_unsampled_pr_signal(tmp_path, monkeypatch):
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

    result = ww.run(
        repo, "batch-982", max_seconds=1, interval_seconds=60,
        monotonic=mono, sleep=lambda d: None, gh_run=gh_run,
    )
    assert result["event"] == "timer"
    assert calls == []
    assert ww.DEGRADATION_PR_SIGNAL_UNAVAILABLE in result["degraded"]


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

    result = ww.run(
        repo, "batch-982", max_seconds=1, interval_seconds=1,
        monotonic=mono, sleep=fake_sleep, gh_run=gh_run,
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

    result = ww.run(
        repo, "batch-982", max_seconds=3, interval_seconds=1,
        monotonic=mono, sleep=fake_sleep, gh_run=gh_run,
    )
    assert result["event"] == "timer"
    assert len(timeouts) >= 1
    for idx, timeout in enumerate(timeouts):
        remaining_at_call = 3.0 - (idx * 1.0)
        assert timeout <= remaining_at_call
        assert timeout <= 30


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


# --- WO-A: precedence tuple, riders, loop ------------------------------------


def test_precedence_reorder_bite_proof(tmp_path, monkeypatch):
    """Reordering PRECEDENCE must change the emitted event when signals co-occur."""
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

    reordered = (
        ww.EVENT_LANE_STALE,
        ww.EVENT_LANE_TERMINAL,
        ww.EVENT_LANE_BLOCKED,
        ww.EVENT_BUILDER_EXITED,
        ww.EVENT_PR_SET_CHANGED,
        ww.EVENT_TIMER,
    )
    monkeypatch.setattr(ww, "PRECEDENCE", reordered)

    result = ww.run(
        repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run,
    )
    assert result["event"] == "lane-stale"
    assert result["event"] != "builder-exited"


def test_missed_interval_replay_spacing(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    clock = [0.0]
    eval_count = [0]
    sleep_calls = [0]

    def mono():
        return clock[0]

    def fake_sleep(duration):
        sleep_calls[0] += 1
        if sleep_calls[0] > 200:
            raise RuntimeError("sleep ceiling")
        clock[0] += duration

    def gh_run(argv, **kwargs):
        eval_count[0] += 1
        clock[0] += 3.5
        return _noop_gh_run(argv, **kwargs)

    result = ww.run(
        repo, "batch-982", max_seconds=10, interval_seconds=1,
        monotonic=mono, sleep=fake_sleep, gh_run=gh_run,
    )
    assert result["event"] == "timer"
    assert eval_count[0] <= 3


def test_internal_error_detail_class_only(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)

    def raiser(repo_root, env=None):
        raise RuntimeError("secret-path /tmp/boom")

    monkeypatch.setattr(ww.ll, "read", raiser)
    result = ww.run(repo, "batch-982", max_seconds=1, interval_seconds=1)
    assert result["ok"] is False
    assert result["reason"] == "internal-error"
    assert result["detail"] == "RuntimeError"
    assert "secret-path" not in json.dumps(result)


def test_started_lane_never_stamped_degradation(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 1)
    ll.append(repo, _reserved("lane-a", "batch-982", ["plugins/superheroes/lib"], repo))
    ll.append(repo, _started("lane-a", pid=os.getpid()))
    result = ww.run(repo, "batch-982", max_seconds=1, interval_seconds=1, gh_run=_noop_gh_run)
    assert result["event"] == "timer"
    assert ww.DEGRADATION_LANE_NEVER_STAMPED in result["degraded"]


def test_terminal_before_pr_arm_no_pr_signal_unavailable(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_live_lane(repo, tmp_path, monkeypatch, stamp_state="handback")
    result = ww.run(repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run)
    assert result["event"] == "lane-terminal"
    assert ww.DEGRADATION_PR_SIGNAL_UNAVAILABLE not in result["degraded"]


def test_pr_skip_subsecond_no_failure_token(tmp_path, monkeypatch):
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
        calls.append(kwargs.get("timeout"))
        return _noop_gh_run(argv, **kwargs)

    result = ww.run(
        repo, "batch-982", max_seconds=1, interval_seconds=60,
        monotonic=mono, sleep=lambda d: None, gh_run=gh_run,
    )
    assert result["event"] == "timer"
    assert calls == []
    assert ww.DEGRADATION_PR_SIGNAL_UNAVAILABLE in result["degraded"]


def test_pr_skip_after_baseline_stays_clean(tmp_path, monkeypatch):
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
        return _noop_gh_run(argv, **kwargs)

    result = ww.run(
        repo, "batch-982", max_seconds=2, interval_seconds=1,
        monotonic=mono, sleep=fake_sleep, gh_run=gh_run,
    )
    assert result["event"] == "timer"
    assert ww.DEGRADATION_PR_SIGNAL_UNAVAILABLE not in result["degraded"]


def test_gh_timeout_ceiling_when_remaining_large(tmp_path, monkeypatch):
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

    result = ww.run(
        repo, "batch-982", max_seconds=60, interval_seconds=1,
        monotonic=mono, sleep=fake_sleep, gh_run=gh_run,
    )
    assert result["event"] == "timer"
    assert len(timeouts) >= 1
    assert timeouts[0] == 30.0


def _bounded_sleep_ceiling():
    calls = [0]

    def sleep_fn(duration):
        calls[0] += 1
        if calls[0] > 200:
            raise RuntimeError("loop sleep ceiling")

    return sleep_fn


def test_loop_continues_through_timers_then_exits(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    sequence = [
        {"ok": True, "event": "timer", "batchId": "batch-982", "degraded": []},
        {"ok": True, "event": "timer", "batchId": "batch-982", "degraded": []},
        {"ok": True, "event": "lane-terminal", "batchId": "batch-982",
         "degraded": [], "launchId": "lane-a", "launches": []},
    ]
    idx = [0]

    def run_fn(repo_root, batch_id, **kwargs):
        if idx[0] >= len(sequence):
            raise RuntimeError("run_fn exhausted")
        result = dict(sequence[idx[0]])
        idx[0] += 1
        return result

    result = ww.loop(
        repo, "batch-982", max_seconds=1, interval_seconds=1,
        run_fn=run_fn, sleep=_bounded_sleep_ceiling(),
    )
    assert result["event"] == "lane-terminal"
    assert result["arms"] == 3


def test_loop_exits_on_refusal_mid_loop(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    sequence = [
        {"ok": True, "event": "timer", "batchId": "batch-982", "degraded": []},
        {"ok": False, "reason": "ledger-unreadable", "batchId": "batch-982"},
    ]
    idx = [0]

    def run_fn(repo_root, batch_id, **kwargs):
        result = dict(sequence[idx[0]])
        idx[0] += 1
        return result

    result = ww.loop(
        repo, "batch-982", run_fn=run_fn, sleep=_bounded_sleep_ceiling(),
    )
    assert result["ok"] is False
    assert result["reason"] == "ledger-unreadable"
    assert result["arms"] == 2


@pytest.mark.parametrize("bad_value", [0, -1, True, 1.5])
def test_loop_refuses_max_total_seconds_invalid(tmp_path, monkeypatch, bad_value):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    result = ww.loop(
        repo, "batch-982", max_total_seconds=bad_value,
        sleep=_bounded_sleep_ceiling(),
    )
    assert result["ok"] is False
    assert result["reason"] == ww.REFUSAL_MAX_TOTAL_SECONDS_INVALID
    assert result["arms"] == 0


def test_loop_max_total_emits_last_timer(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    clock = [0.0]
    arm_windows = []

    def mono():
        return clock[0]

    def run_fn(repo_root, batch_id, *, max_seconds, **kwargs):
        arm_windows.append(max_seconds)
        clock[0] += max_seconds
        return {
            "ok": True,
            "event": "timer",
            "batchId": batch_id,
            "degraded": [],
        }

    result = ww.loop(
        repo, "batch-982", max_seconds=10, max_total_seconds=15,
        monotonic=mono, run_fn=run_fn, sleep=_bounded_sleep_ceiling(),
    )
    assert result["event"] == "timer"
    assert result["arms"] == 2
    assert arm_windows == [10, 5]


def test_loop_ledger_latch_across_arms(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 1)
    ll.append(repo, _reserved("lane-a", "batch-982", ["plugins/superheroes/lib"], repo))
    ll.append(repo, _started("lane-a", pid=os.getpid()))
    hb.stamp(repo, state="working", phase="watch", launch_id="lane-a")
    calls = [0]

    def run_fn(repo_root, batch_id, **kwargs):
        calls[0] += 1
        kwargs = dict(kwargs)
        kwargs["gh_run"] = _noop_gh_run
        kwargs["sleep"] = lambda d: None
        if calls[0] == 1:
            return ww.run(repo_root, batch_id, **kwargs)
        import shutil
        shutil.rmtree(store_root)
        return ww.run(repo_root, batch_id, **kwargs)

    result = ww.loop(
        repo, "batch-982", max_seconds=1, interval_seconds=1,
        run_fn=run_fn, sleep=_bounded_sleep_ceiling(),
    )
    assert result["ok"] is False
    assert result["reason"] == "ledger-unreadable"
    assert result["arms"] == 2


def test_loop_pr_change_across_arm_boundary(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    calls = [0]

    def gh_run(argv, **kwargs):
        calls[0] += 1
        if calls[0] == 1:
            body = [{"number": 1}]
        else:
            body = [{"number": 1}, {"number": 99}]
        return subprocess.CompletedProcess(
            argv, 0, stdout=json.dumps(body), stderr="",
        )

    def run_fn(repo_root, batch_id, **kwargs):
        kwargs = dict(kwargs)
        kwargs["gh_run"] = gh_run
        kwargs["sleep"] = lambda d: None
        return ww.run(repo_root, batch_id, **kwargs)

    result = ww.loop(
        repo, "batch-982", max_seconds=1, interval_seconds=60,
        run_fn=run_fn, sleep=_bounded_sleep_ceiling(),
    )
    assert result["event"] == "pr-set-changed"
    assert result["prsAdded"] == [99]
    assert result["arms"] >= 2


def test_loop_log_one_line_per_timer_arm(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_path = str(tmp_path / "watch.log")
    clock = [0.0]
    sequence = [
        {"ok": True, "event": "timer", "batchId": "batch-982", "degraded": []},
        {"ok": True, "event": "timer", "batchId": "batch-982", "degraded": []},
        {"ok": True, "event": "lane-terminal", "batchId": "batch-982",
         "degraded": [], "launchId": "x", "launches": []},
    ]
    idx = [0]

    def mono():
        return clock[0]

    def run_fn(repo_root, batch_id, **kwargs):
        result = dict(sequence[idx[0]])
        idx[0] += 1
        clock[0] += 1.0
        return result

    result = ww.loop(
        repo, "batch-982", log_path=log_path, monotonic=mono,
        run_fn=run_fn, sleep=_bounded_sleep_ceiling(),
    )
    assert result["event"] == "lane-terminal"
    lines = open(log_path, encoding="utf-8").read().strip().split("\n")
    assert len(lines) == 2
    entry0 = json.loads(lines[0])
    assert entry0["arm"] == 1
    assert entry0["elapsedSeconds"] == 1.0
    assert entry0["result"]["event"] == "timer"
    entry1 = json.loads(lines[1])
    assert entry1["arm"] == 2
    assert entry1["elapsedSeconds"] == 2.0


def test_loop_log_unwritable_survives_to_final_result(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    sequence = [
        {"ok": True, "event": "timer", "batchId": "batch-982", "degraded": []},
        {"ok": True, "event": "builder-exited", "batchId": "batch-982",
         "degraded": [], "pids": [1], "launches": [{"launchId": "a", "pid": 1}]},
    ]
    idx = [0]

    def run_fn(repo_root, batch_id, **kwargs):
        result = dict(sequence[idx[0]])
        idx[0] += 1
        return result

    result = ww.loop(
        repo, "batch-982", log_path="/nonexistent/dir/watch.log",
        run_fn=run_fn, sleep=_bounded_sleep_ceiling(),
    )
    assert result["event"] == "builder-exited"
    assert ww.DEGRADATION_LOG_UNWRITABLE in result["degraded"]


def test_cli_loop_event_exit_zero(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    proc = _run_cli([
        "loop", "--repo-root", repo, "--batch", "batch-982",
        "--max-seconds", "1", "--interval-seconds", "1",
        "--max-total-seconds", "1",
    ])
    assert proc.returncode == 0
    out = json.loads(proc.stdout.strip())
    assert out["ok"] is True
    assert out["event"] == "timer"


def test_cli_loop_refusal_exit_one(tmp_path):
    proc = _run_cli([
        "loop", "--repo-root", str(tmp_path / "missing"), "--batch", "b",
        "--max-seconds", "1", "--interval-seconds", "1",
    ])
    assert proc.returncode == 1
    out = json.loads(proc.stdout.strip())
    assert out["ok"] is False
