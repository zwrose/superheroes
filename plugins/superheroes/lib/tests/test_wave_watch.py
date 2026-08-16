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
    assert result["detail"] == "RuntimeError"
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


def test_lane_terminal_makes_zero_gh_run_calls(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_live_lane(repo, tmp_path, monkeypatch, stamp_state="handback")
    gh_calls = [0]

    def counting_gh_run(argv, **kwargs):
        gh_calls[0] += 1
        return _noop_gh_run(argv, **kwargs)

    result = ww.run(
        repo, "batch-982", max_seconds=2, interval_seconds=60,
        gh_run=counting_gh_run,
    )
    assert result["event"] == "lane-terminal"
    assert gh_calls[0] == 0


def test_lane_blocked_makes_zero_gh_run_calls(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_live_lane(repo, tmp_path, monkeypatch, stamp_state="blocked")
    gh_calls = [0]

    def counting_gh_run(argv, **kwargs):
        gh_calls[0] += 1
        return _noop_gh_run(argv, **kwargs)

    result = ww.run(
        repo, "batch-982", max_seconds=2, interval_seconds=60,
        gh_run=counting_gh_run,
    )
    assert result["event"] == "lane-blocked"
    assert gh_calls[0] == 0


def test_builder_exited_makes_zero_gh_run_calls(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    dead_pid = 999999999
    _setup_live_lane(repo, tmp_path, monkeypatch, pid=dead_pid)
    gh_calls = [0]

    def counting_gh_run(argv, **kwargs):
        gh_calls[0] += 1
        return _noop_gh_run(argv, **kwargs)

    result = ww.run(
        repo, "batch-982", max_seconds=2, interval_seconds=60,
        gh_run=counting_gh_run,
    )
    assert result["event"] == "builder-exited"
    assert gh_calls[0] == 0


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

    result = ww.run(
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


def test_lane_never_stamped_emits_timer_not_lane_stale(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    store_root = _ledger_env(tmp_path, monkeypatch)
    _precreate_repo_store_dir(repo, store_root)
    ll.declare_batch(repo, "batch-982", 1)
    ll.append(repo, _reserved("lane-a", "batch-982", ["plugins/superheroes/lib"], repo))
    ll.append(repo, _started("lane-a", pid=os.getpid()))
    result = ww.run(
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
    original_derive = ww._derive_live_lanes

    def derive_with_unstarted_pid(*args, **kwargs):
        live, readable = original_derive(*args, **kwargs)
        assert "lane-a" in live, "derive injection silently skipped"
        live = dict(live)
        live["lane-a"] = dict(live["lane-a"])
        live["lane-a"]["pid"] = os.getpid()
        assert not live["lane-a"].get("started")
        return live, readable

    monkeypatch.setattr(ww, "_derive_live_lanes", derive_with_unstarted_pid)
    result = ww.run(
        repo, "batch-982", max_seconds=1, interval_seconds=1, gh_run=_noop_gh_run,
    )
    assert result["event"] == "timer"
    assert result["event"] != "lane-stale"


def test_lane_never_stamped_not_latched_when_stamp_arrives_on_tick_two(
    tmp_path, monkeypatch,
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

    result = ww.run(
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
    result = ww.run(
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


def test_precedence_terminal_beats_builder_exited(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    dead = 777777777
    _setup_live_lane(repo, tmp_path, monkeypatch, pid=dead, stamp_state="handback")
    result = ww.run(repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run)
    assert result["event"] == "lane-terminal"
    assert result["event"] != "builder-exited"


def test_event_precedence_matches_docstring():
    doc = ww.__doc__
    assert "lane-terminal (E1) > lane-blocked (E2) > builder-exited (E3) >" in doc
    assert "pr-set-changed (E4) > lane-stale (E5) > timer (E6)" in doc
    assert ww.EVENT_PRECEDENCE == (
        ww.EVENT_LANE_TERMINAL,
        ww.EVENT_LANE_BLOCKED,
        ww.EVENT_BUILDER_EXITED,
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
    ], env=_fake_gh_cli_env(tmp_path))
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

    result = ww.run(
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
        repo, "batch-982", max_seconds=2, interval_seconds=1,
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

    result = ww.run(
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

    result = ww.run(
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

    result = ww.run(
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

    result = ww.run(
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
    original_derive = ww._derive_live_lanes

    def slow_derive(*args, **kwargs):
        derive_calls[0] += 1
        if derive_calls[0] == 1:
            clock[0] += scan_cost
        return original_derive(*args, **kwargs)

    monkeypatch.setattr(ww, "_derive_live_lanes", slow_derive)

    def mono():
        return clock[0]

    def fake_sleep(duration):
        clock[0] += duration

    def gh_run(argv, **kwargs):
        gh_calls.append(kwargs.get("timeout"))
        return _noop_gh_run(argv, **kwargs)

    result = ww.run(
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
    original_derive = ww._derive_live_lanes

    def slow_derive(*args, **kwargs):
        clock[0] += scan_cost
        return original_derive(*args, **kwargs)

    monkeypatch.setattr(ww, "_derive_live_lanes", slow_derive)

    def mono():
        return clock[0]

    def gh_run(argv, **kwargs):
        timeouts.append(kwargs.get("timeout"))
        return _noop_gh_run(argv, **kwargs)

    result = ww.run(
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

    result = ww.run(
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

    result = ww.run(
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

    result = ww.run(
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

    result = ww.run(
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
    ], env=_fake_gh_cli_env(tmp_path))
    assert proc.returncode == 0
    out = json.loads(proc.stdout.strip())
    assert out["ok"] is True
    assert out["event"] == "timer"


# --- loop verb (B1–B5) --------------------------------------------------------


def _valid_repo_for_loop(tmp_path):
    return _init_repo(tmp_path / "loop-repo")


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


def test_loop_timer_rearms_until_non_timer_event(tmp_path):
    repo = _valid_repo_for_loop(tmp_path)
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


def test_loop_first_non_timer_ok_terminates_with_arms(tmp_path):
    repo = _valid_repo_for_loop(tmp_path)
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


def test_loop_refusal_terminates_immediately_with_arms(tmp_path):
    repo = _valid_repo_for_loop(tmp_path)
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
    tmp_path, kwargs, expected_reason,
):
    repo = _valid_repo_for_loop(tmp_path)
    run_fn, calls, violations = _never_run_fn()
    batch_id = kwargs.pop("batch_id", "batch-982")
    result = ww.loop(repo, batch_id, run_fn=run_fn, **kwargs)
    assert result["ok"] is False
    assert result["reason"] == expected_reason
    assert result["arms"] == 0
    assert calls[0] == 0
    assert violations == []


def test_loop_max_total_seconds_emits_last_timer_not_refusal(tmp_path):
    repo = _valid_repo_for_loop(tmp_path)
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


def test_loop_accumulates_degraded_from_discarded_timer_arms(tmp_path):
    repo = _valid_repo_for_loop(tmp_path)
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
    real_run = ww.run
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
    arm = [0]
    pr_sets = [{1}, {1, 2}]
    real_run = ww.run

    def gh_for_arm(argv, **kwargs):
        idx = min(arm[0] - 1, len(pr_sets) - 1)
        body = [{"number": n} for n in sorted(pr_sets[idx])]
        return subprocess.CompletedProcess(
            argv, 0, stdout=json.dumps(body), stderr="",
        )

    def run_fn(repo_root, batch_id, **kwargs):
        arm[0] += 1
        call_kwargs = dict(kwargs)
        call_kwargs["gh_run"] = gh_for_arm
        call_kwargs["max_seconds"] = 2
        call_kwargs["interval_seconds"] = 1
        return real_run(repo_root, batch_id, **call_kwargs)

    result = ww.loop(
        repo, "batch-982",
        max_seconds=2, interval_seconds=1,
        run_fn=run_fn,
    )
    assert result["ok"] is True
    assert result["event"] == "pr-set-changed"
    assert result["prsAdded"] == [2]
    assert result["arms"] == 2


def test_loop_threads_pr_sampled_so_timer_not_never_sampled(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    arm = [0]
    real_run = ww.run
    clock = [0.0]
    original_derive = ww._derive_live_lanes
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
            monkeypatch.setattr(ww, "_derive_live_lanes", original_derive)
        else:
            call_kwargs["max_seconds"] = 1
            call_kwargs["interval_seconds"] = 60

            def slow_derive(*args, **kw):
                clock[0] += sub_floor_scan_cost
                return original_derive(*args, **kw)

            monkeypatch.setattr(ww, "_derive_live_lanes", slow_derive)
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
    ww.run(repo, "batch-982", **common)
    omitted = ww.run(repo, "batch-982", **common)
    explicit_none = ww.run(
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
    result = ww.run(
        repo, "batch-982", max_seconds=2, interval_seconds=60,
        ignore_events=(("lane-a", ww.EVENT_LANE_STALE),),
        gh_run=_noop_gh_run,
    )
    assert result["event"] == "timer"
    assert result["event"] != "lane-stale"


def test_ignore_event_same_lane_different_event_still_fires(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _setup_live_lane(repo, tmp_path, monkeypatch, stamp_state="handback")
    result = ww.run(
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
    result = ww.run(
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
    result = ww.run(
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
    result = ww.run(
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
    (("lane-a", ww.EVENT_TIMER),),
])
def test_ignore_event_invalid_direct_call(tmp_path, ignore_events):
    repo = _valid_repo_for_loop(tmp_path)
    result = ww.run(
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
    "lane-a:timer",
])
def test_ignore_event_invalid_cli(tmp_path, cli_value):
    repo = _valid_repo_for_loop(tmp_path)
    proc = _run_cli([
        "run", "--repo-root", repo, "--batch", "batch-982",
        "--max-seconds", "1", "--interval-seconds", "1",
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
        "--max-seconds", "2", "--interval-seconds", "60",
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


def test_loop_refusal_interval_invalid_has_arms_zero(tmp_path):
    repo = _valid_repo_for_loop(tmp_path)
    run_fn, calls, violations = _never_run_fn()
    result = ww.loop(
        repo, "batch-982", interval_seconds=0, run_fn=run_fn,
    )
    assert result["ok"] is False
    assert result["reason"] == ww.REFUSAL_INTERVAL_INVALID
    assert result["arms"] == 0
    assert calls[0] == 0
    assert violations == []


def test_cli_loop_uses_injected_gh_stub_not_real_gh(tmp_path, monkeypatch):
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
    env = dict(os.environ)
    env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
    proc = _run_cli([
        "loop", "--repo-root", repo, "--batch", "batch-982",
        "--max-seconds", "2", "--interval-seconds", "1",
        "--max-total-seconds", "3",
    ], env=env)
    assert proc.returncode == 0
    out = json.loads(proc.stdout.strip())
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

    result = ww.run(
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
    elif shape == "unreadable-projects-root":
        _write_session_transcript(config_dir, session_id, age_seconds=60)
        unreadable_root = os.path.join(str(config_dir), "projects")
        os.chmod(unreadable_root, 0o000)
        # A non-empty 0o000 tree defeats pytest's tmp cleanup, so hand the mode back the
        # moment the watcher has read it.
        request.addfinalizer(lambda: os.chmod(unreadable_root, 0o700))
    else:
        _write_session_transcript(config_dir, session_id, age_seconds=60)

    result = ww.run(
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
    mtime, ambiguous, unresolved = ww._session_transcript_mtime(_TEST_SESSION_ID, os.environ)
    assert mtime is None and ambiguous is False and unresolved is True


def test_absent_bucket_with_fresh_match_suppresses_lane(tmp_path, monkeypatch):
    """A genuinely absent candidate in another bucket must not block suppression."""
    repo = _init_repo(tmp_path / "repo")
    worktree = str(tmp_path / "build-wt")
    _stale_lane_with_worktree(repo, tmp_path, monkeypatch, worktree=worktree)
    config_dir = _point_config_dir_at(tmp_path, monkeypatch)
    _write_session_transcript(config_dir, _TEST_SESSION_ID, age_seconds=60, bucket="present")
    os.makedirs(os.path.join(str(config_dir), "projects", "absent"), exist_ok=True)

    result = ww.run(
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

    result = ww.run(
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

    result = ww.run(
        repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run,
    )

    assert result["event"] == "lane-stale"
    assert "staleSuppressed" not in result
    assert ww.DEGRADATION_TRANSCRIPT_UNRESOLVED not in result["degraded"]

    # And the same lane resolves once the env root IS the one holding the transcript —
    # proving the miss above is the root choice, not a broken fixture.
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(root_a))
    again = ww.run(
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

    result = ww.run(
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

    result = ww.run(
        repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run,
    )

    assert result["event"] == "lane-stale"
    assert ww.DEGRADATION_TRANSCRIPT_UNRESOLVED in result["degraded"]


def test_transcript_config_dirs_recorded_root_wins_over_env(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/tmp/env-config")
    assert ww._transcript_config_dirs(os.environ) == ["/tmp/env-config"]
    assert ww._transcript_config_dirs(
        os.environ, recorded="/tmp/lane-config",
    ) == ["/tmp/lane-config"]
    # Unusable recorded roots resolve to NO root — never to the env root.
    for bad in ("", "   ", "relative/config", 17, True):
        assert ww._transcript_config_dirs(os.environ, recorded=bad) == [], bad


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

    result = ww.run(
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

    result = ww.run(
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

    result = ww.run(
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

    result = ww.run(
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

