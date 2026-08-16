import json
import os
import subprocess
import sys
import time

import pytest

import heartbeat as hb
import launch_ledger as ll

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_LAUNCHER_MOD = os.path.join(_LIB, "launcher.py")
_THIS_FILE = os.path.abspath(__file__)


# The #843 heartbeat/launch env pin used to live here as a module-local autouse fixture. #866
# hoisted it into conftest's `_isolate_store_root`, because the exposure is the class — every lib
# test module that resolves a heartbeat or launch-ledger root — not this module. The guard below
# (`test_e2e_survives_ambient_launcher_env`) is what proves the pin still bites from up there.


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


def _git(repo, *args):
    subprocess.run(["git", "-C", repo, *args], check=True)


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
        "issue": 657,
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


def _outcome(launch_id, outcome="handback", evidence="done"):
    return {
        "event": "outcome",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "outcome": outcome,
        "evidence": evidence,
    }


def _declare_and_reserve(repo, launch_id, monkeypatch, tmp_path):
    _ledger_env(tmp_path, monkeypatch)
    ll.declare_batch(repo, "batch-657", 1)
    ll.append(repo, _reserved(launch_id, "batch-657", ["plugins/superheroes/lib"], repo))
    ll.append(repo, _started(launch_id))


def _good_stamp_kwargs(**overrides):
    base = {
        "state": "working",
        "phase": "dispatch",
        "launch_id": "lane-a",
        "stale_after_seconds": 300,
        "now": 1_000_000.0,
    }
    base.update(overrides)
    return base


def _write_heartbeat_file(repo, launch_id, record, env=None):
    path = hb.heartbeat_path(repo, launch_id, env=env)
    assert path["ok"]
    parent = os.path.dirname(path["path"])
    os.makedirs(parent, mode=0o700, exist_ok=True)
    with open(path["path"], "w", encoding="utf-8") as fh:
        json.dump(record, fh)


def _base_record(launch_id="lane-a", **overrides):
    rec = {
        "schema": hb.SCHEMA,
        "launchId": launch_id,
        "issue": 657,
        "state": "working",
        "phase": "dispatch",
        "lastDispatch": None,
        "ts": 1_000_000.0,
        "staleAfterSeconds": 300,
        "note": None,
    }
    rec.update(overrides)
    return rec


# --- fail-closed edges 1-10 ---------------------------------------------------


def test_edge_01_missing_heartbeat_on_live_launch(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    launch_id = "live-missing"
    _declare_and_reserve(repo, launch_id, monkeypatch, tmp_path)
    now = 1_000_000.0
    result = hb.sweep(repo, now=now)
    assert result["ok"] is True
    entry = next(e for e in result["launches"] if e["launchId"] == launch_id)
    assert entry["class"] == "unknown"
    assert entry["class"] != "fresh"
    assert entry["reason"] == "heartbeat-missing"


def test_edge_02_unreadable_corrupt_file(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    launch_id = "corrupt-lane"
    _declare_and_reserve(repo, launch_id, monkeypatch, tmp_path)
    path = hb.heartbeat_path(repo, launch_id)["path"]
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(b"{not json")
    result = hb.read_heartbeat(repo, launch_id, now=1_000_000.0)
    assert result["class"] == "unknown"
    assert result["class"] != "fresh"
    assert result["reason"] == "heartbeat-corrupt"


def test_edge_02c_unreadable_file(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    launch_id = "unreadable-lane"
    _declare_and_reserve(repo, launch_id, monkeypatch, tmp_path)
    path = hb.heartbeat_path(repo, launch_id)["path"]
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(_base_record(launch_id), fh)
    os.chmod(path, 0o000)
    try:
        result = hb.read_heartbeat(repo, launch_id, now=1_000_000.0)
    finally:
        os.chmod(path, 0o600)
    assert result["class"] == "unknown"
    assert result["reason"] == "heartbeat-unreadable"


def test_edge_02b_non_object_json(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    launch_id = "array-lane"
    _declare_and_reserve(repo, launch_id, monkeypatch, tmp_path)
    path = hb.heartbeat_path(repo, launch_id)["path"]
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("[1,2,3]")
    result = hb.read_heartbeat(repo, launch_id, now=1_000_000.0)
    assert result["class"] == "unknown"
    assert result["class"] != "fresh"


def test_edge_03_schema_not_one(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    launch_id = "schema-bad"
    _declare_and_reserve(repo, launch_id, monkeypatch, tmp_path)
    _write_heartbeat_file(repo, launch_id, _base_record(launch_id, schema=2))
    result = hb.read_heartbeat(repo, launch_id, now=1_000_000.0)
    assert result["class"] == "unknown"
    assert result["class"] != "fresh"


def test_edge_04_future_ts_no_tolerance(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    launch_id = "future-lane"
    now = 1_000_000.0
    _declare_and_reserve(repo, launch_id, monkeypatch, tmp_path)
    _write_heartbeat_file(repo, launch_id, _base_record(launch_id, ts=now + 1))
    result = hb.read_heartbeat(repo, launch_id, now=now)
    assert result["class"] == "unknown"
    assert result["reason"] == "heartbeat-ts-future"


@pytest.mark.parametrize(
    "bad_ts,expected_reason",
    [
        (float("nan"), "heartbeat-corrupt"),
        (float("inf"), "heartbeat-corrupt"),
        (float("-inf"), "heartbeat-corrupt"),
        (True, "heartbeat-ts-invalid"),
        (False, "heartbeat-ts-invalid"),
    ],
)
def test_edge_05_non_finite_ts(tmp_path, monkeypatch, bad_ts, expected_reason):
    repo = _init_repo(tmp_path / "repo")
    launch_id = "bad-ts"
    _declare_and_reserve(repo, launch_id, monkeypatch, tmp_path)
    _write_heartbeat_file(repo, launch_id, _base_record(launch_id, ts=bad_ts))
    result = hb.read_heartbeat(repo, launch_id, now=1_000_000.0)
    assert result["class"] == "unknown"
    assert result["class"] != "fresh"
    assert result["reason"] == expected_reason


def test_stamp_refuses_non_finite_now(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    result = hb.stamp(
        repo,
        state="working",
        phase="p",
        launch_id="nan-lane",
        now=float("nan"),
    )
    assert result["ok"] is False
    assert result["reason"] == "heartbeat-ts-invalid"
    assert not os.path.isfile(hb.heartbeat_path(repo, "nan-lane")["path"])


@pytest.mark.parametrize(
    "bad_stale,expected_reason",
    [
        (float("nan"), "heartbeat-corrupt"),
        (float("inf"), "heartbeat-corrupt"),
        (True, "heartbeat-stale-after-invalid"),
        (False, "heartbeat-stale-after-invalid"),
        ("300", "heartbeat-stale-after-invalid"),
        (-1, "heartbeat-stale-after-invalid"),
        (0, "heartbeat-stale-after-invalid"),
        (86401, "heartbeat-stale-after-invalid"),
    ],
)
def test_edge_05_non_finite_or_invalid_stale_after(
    tmp_path, monkeypatch, bad_stale, expected_reason,
):
    repo = _init_repo(tmp_path / "repo")
    launch_id = "bad-stale"
    _declare_and_reserve(repo, launch_id, monkeypatch, tmp_path)
    _write_heartbeat_file(
        repo, launch_id, _base_record(launch_id, staleAfterSeconds=bad_stale),
    )
    result = hb.read_heartbeat(repo, launch_id, now=1_000_000.0)
    assert result["class"] == "unknown"
    assert result["class"] != "fresh"
    assert result["reason"] == expected_reason


def test_edge_06_invalid_state(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    launch_id = "bad-state"
    _declare_and_reserve(repo, launch_id, monkeypatch, tmp_path)
    _write_heartbeat_file(repo, launch_id, _base_record(launch_id, state="dead"))
    result = hb.read_heartbeat(repo, launch_id, now=1_000_000.0)
    assert result["class"] == "unknown"
    assert result["class"] != "fresh"


@pytest.mark.parametrize("bad_state", [[], {}, 1])
def test_edge_06b_non_string_state_never_raises(tmp_path, monkeypatch, bad_state):
    repo = _init_repo(tmp_path / "repo")
    launch_id = "typed-state"
    _declare_and_reserve(repo, launch_id, monkeypatch, tmp_path)
    _write_heartbeat_file(repo, launch_id, _base_record(launch_id, state=bad_state))
    result = hb.read_heartbeat(repo, launch_id, now=1_000_000.0)
    assert result["class"] == "unknown"
    assert result["reason"] == "heartbeat-state-invalid"


def test_edge_07_ledger_unreadable(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    ledger_root = _ledger_env(tmp_path, monkeypatch)
    path = ll.ledger_path(repo)["path"]
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("not-json\n")
    result = hb.sweep(repo)
    assert result["ok"] is False
    assert result["reason"] == hb.REASON_LEDGER_UNREADABLE
    assert "launches" not in result or result.get("launches") != []


def test_edge_07b_ledger_torn_tail(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    launch_id = "torn-lane"
    ll.declare_batch(repo, "batch-t", 1)
    ll.append(repo, _reserved(launch_id, "batch-t", ["x"], repo))
    path = ll.ledger_path(repo)["path"]
    with open(path, "rb") as fh:
        raw = fh.read()
    with open(path, "wb") as fh:
        fh.write(raw.rstrip(b"\n"))
    result = hb.sweep(repo)
    assert result["ok"] is False
    assert result["reason"] == hb.REASON_LEDGER_UNREADABLE


def test_edge_07c_ledger_interior_corruption(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    path = ll.ledger_path(repo)["path"]
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("not-json\n")
        fh.write('{"event":"reserved"}\n')
    result = hb.sweep(repo)
    assert result["ok"] is False
    assert result["reason"] == hb.REASON_LEDGER_UNREADABLE


def test_edge_07d_ledger_fold_invalid(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    ll.append(repo, {"event": "bogus", "launchId": "x", "ts": 1.0, "schema": 1})
    result = hb.sweep(repo)
    assert result["ok"] is False
    assert result["reason"] == hb.REASON_LEDGER_UNREADABLE


def test_edge_07e_missing_ledger_refuses_sweep(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    result = hb.sweep(repo)
    assert result["ok"] is False
    assert result["reason"] == hb.REASON_LEDGER_UNREADABLE
    assert "launches" not in result


@pytest.mark.parametrize("launch_id", ["../../evil", "a/b"])
def test_edge_08_launch_id_traversal_refuses_stamp(tmp_path, monkeypatch, launch_id):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    result = hb.stamp(repo, **_good_stamp_kwargs(launch_id=launch_id))
    assert result["ok"] is False
    assert result["reason"] == hb.REASON_LAUNCH_ID_INVALID
  # nothing written anywhere under heartbeats
    root = hb.resolve_root(repo)["root"]
    repo_id = ll.repo_identity(repo)
    beats_dir = os.path.join(root, repo_id, hb.HEARTBEATS_DIR_NAME)
    if os.path.isdir(beats_dir):
        assert os.listdir(beats_dir) == []


def test_edge_09_terminal_on_live_launch(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    launch_id = "terminal-live"
    _declare_and_reserve(repo, launch_id, monkeypatch, tmp_path)
    _write_heartbeat_file(repo, launch_id, _base_record(launch_id, state="parked"))
    result = hb.sweep(repo, now=1_000_000.0)
    entry = next(e for e in result["launches"] if e["launchId"] == launch_id)
    assert entry["class"] == "terminal"
    assert entry["class"] != "fresh"
    assert entry.get("actionable") is True
    assert entry.get("pendingAction") == "record-outcome"


def test_edge_10_never_reports_dead(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    launch_id = "stale-lane"
    _declare_and_reserve(repo, launch_id, monkeypatch, tmp_path)
    now = 1_000_000.0
    _write_heartbeat_file(
        repo, launch_id,
        _base_record(launch_id, ts=now - 10_000, staleAfterSeconds=60),
    )
    result = hb.sweep(repo, now=now)
    entry = next(e for e in result["launches"] if e["launchId"] == launch_id)
    assert entry["class"] == "stale"
    assert "dead" not in entry
    assert entry.get("class") != "dead"


# --- classification boundaries ------------------------------------------------


def test_fresh_at_exactly_stale_boundary(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    launch_id = "boundary"
    now = 1_000_000.0
    _declare_and_reserve(repo, launch_id, monkeypatch, tmp_path)
    _write_heartbeat_file(
        repo, launch_id,
        _base_record(launch_id, ts=now - 300, staleAfterSeconds=300),
    )
    result = hb.read_heartbeat(repo, launch_id, now=now)
    assert result["class"] == "fresh"


def test_stale_one_second_past_boundary(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    launch_id = "past-boundary"
    now = 1_000_000.0
    _declare_and_reserve(repo, launch_id, monkeypatch, tmp_path)
    _write_heartbeat_file(
        repo, launch_id,
        _base_record(launch_id, ts=now - 301, staleAfterSeconds=300),
    )
    result = hb.read_heartbeat(repo, launch_id, now=now)
    assert result["class"] == "stale"


def test_stamp_and_read_round_trip(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    now = 2_000_000.0
    result = hb.stamp(
        repo,
        state="working",
        phase="implement",
        launch_id="lane-rt",
        issue=657,
        stale_after_seconds=120,
        now=now,
    )
    assert result["ok"] is True
    mode = os.stat(result["path"]).st_mode & 0o777
    assert mode == 0o600
    beats_dir = os.path.dirname(result["path"])
    dir_mode = os.stat(beats_dir).st_mode & 0o777
    assert dir_mode == 0o700
    read_back = hb.read_heartbeat(repo, "lane-rt", now=now + 1)
    assert read_back["class"] == "fresh"
    assert read_back["state"] == "working"


def test_stamp_rejects_invalid_on_write(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    result = hb.stamp(
        repo,
        state="working",
        phase="x",
        launch_id="lane-bad",
        stale_after_seconds=0,
        now=1_000_000.0,
    )
    assert result["ok"] is False
    path = hb.heartbeat_path(repo, "lane-bad")
    assert not os.path.isfile(path["path"])


def test_heartbeat_root_env_override(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    custom_root = str(tmp_path / "custom-heartbeat-root")
    os.makedirs(custom_root, mode=0o700)
    monkeypatch.setenv(hb.HEARTBEAT_ROOT_ENV, custom_root)
    monkeypatch.delenv(ll.LEDGER_ROOT_ENV, raising=False)
    now = 1_000_000.0
    result = hb.stamp(
        repo,
        state="working",
        phase="child",
        launch_id="env-lane",
        now=now,
    )
    assert result["ok"] is True
    assert result["path"].startswith(custom_root)


def test_heartbeat_root_override_refuses_in_repo(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    inside = os.path.join(repo, "inside-heartbeat")
    monkeypatch.setenv(hb.HEARTBEAT_ROOT_ENV, inside)
    result = hb.resolve_root(repo)
    assert result["ok"] is False
    assert result["reason"] == hb.REASON_ROOT_UNRESOLVED


def test_heartbeat_root_override_repo_identity_unavailable(tmp_path, monkeypatch):
    not_repo = str(tmp_path / "plain")
    os.makedirs(not_repo)
    custom_root = str(tmp_path / "custom-heartbeat-root")
    os.makedirs(custom_root, mode=0o700)
    monkeypatch.setenv(hb.HEARTBEAT_ROOT_ENV, custom_root)
    result = hb.resolve_root(not_repo)
    assert result["ok"] is False
    assert result["reason"] == hb.REASON_REPO_IDENTITY_UNAVAILABLE


def test_heartbeat_root_override_refuses_insecure(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    insecure_root = str(tmp_path / "insecure-heartbeat-root")
    os.makedirs(insecure_root, mode=0o755)
    monkeypatch.setenv(hb.HEARTBEAT_ROOT_ENV, insecure_root)
    result = hb.resolve_root(repo)
    assert result["ok"] is False
    assert result["reason"] == hb.REASON_ROOT_UNRESOLVED


def test_heartbeat_root_override_creates_mode_0700_dirs(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    custom_root = str(tmp_path / "custom-heartbeat-root")
    os.makedirs(custom_root, mode=0o700)
    monkeypatch.setenv(hb.HEARTBEAT_ROOT_ENV, custom_root)
    monkeypatch.delenv(ll.LEDGER_ROOT_ENV, raising=False)
    result = hb.stamp(
        repo,
        state="working",
        phase="child",
        launch_id="mode-lane",
        now=1_000_000.0,
    )
    assert result["ok"] is True
    repo_id = ll.repo_identity(repo)
    repo_dir = os.path.join(custom_root, repo_id)
    beats_dir = os.path.join(repo_dir, hb.HEARTBEATS_DIR_NAME)
    original_umask = os.umask(0)
    try:
        assert (os.stat(repo_dir).st_mode & 0o777) == 0o700
        assert (os.stat(beats_dir).st_mode & 0o777) == 0o700
    finally:
        os.umask(original_umask)


def test_read_heartbeat_refuses_symlink(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    launch_id = "symlink-lane"
    _declare_and_reserve(repo, launch_id, monkeypatch, tmp_path)
    path = hb.heartbeat_path(repo, launch_id)["path"]
    parent = os.path.dirname(path)
    os.makedirs(parent, mode=0o700, exist_ok=True)
    real_file = os.path.join(parent, "real.json")
    with open(real_file, "w", encoding="utf-8") as fh:
        json.dump(_base_record(launch_id), fh)
    os.symlink(real_file, path)
    result = hb.read_heartbeat(repo, launch_id, now=1_000_000.0)
    assert result["class"] == "unknown"
    assert result["reason"] == "heartbeat-unreadable"


def test_sweep_empty_when_no_live_launches(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    launch_id = "done-lane"
    ll.declare_batch(repo, "batch-done", 1)
    ll.append(repo, _reserved(launch_id, "batch-done", ["x"], repo))
    ll.append(repo, _started(launch_id))
    assert ll.record_outcome(repo, launch_id, "handback", "done")["ok"]
    result = hb.sweep(repo)
    assert result["ok"] is True
    assert result["launches"] == []


# --- end-to-end: worktree + non-default ledger root ---------------------------


def test_e2e_child_stamp_visible_from_primary_checkout(tmp_path, monkeypatch):
    """Stamp via child-exported env from a linked worktree; sweep from primary."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("launcher", _LAUNCHER_MOD)
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)

    repo = _init_repo(tmp_path / "repo")
    _git(repo, "branch", "-M", "main")
    wt = str(tmp_path / "wt")
    _git(repo, "worktree", "add", "-q", wt)

    ledger_root = str(tmp_path / "custom-ledger-root")
    os.makedirs(ledger_root, mode=0o700)
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, ledger_root)

    launch_id = "wt-lane-657"
    ll.declare_batch(repo, "batch-wt", 1)
    ll.append(repo, _reserved(launch_id, "batch-wt", ["plugins/superheroes/lib"], repo))
    ll.append(repo, _started(launch_id))

    captured_env = {}

    def capture_spawn(argv, repo_root, out_fh, err_fh, child_env):
        captured_env.update(child_env)
        class _Proc:
            pid = 424242

        out_fh.close()
        err_fh.close()
        return _Proc()

    log_dir = str(tmp_path / "logs")
    os.makedirs(log_dir)
    launcher._spawn_attempt(
        repo,
        launch_id,
        1,
        ["claude", "-p", "test"],
        os.path.join(log_dir, "out.log"),
        os.path.join(log_dir, "err.log"),
        900000,
        env=os.environ,
        spawn_fn=capture_spawn,
        cwd=wt,
    )

    assert captured_env.get(hb.LAUNCH_ID_ENV) == launch_id
    assert captured_env.get(hb.HEARTBEAT_ROOT_ENV) == ledger_root
    assert ll.LEDGER_ROOT_ENV not in captured_env

    child_env = {
        hb.LAUNCH_ID_ENV: captured_env[hb.LAUNCH_ID_ENV],
        hb.HEARTBEAT_ROOT_ENV: captured_env[hb.HEARTBEAT_ROOT_ENV],
    }
    now = 3_000_000.0
    stamp_result = hb.stamp(
        wt,
        state="working",
        phase="child-dispatch",
        stale_after_seconds=600,
        now=now,
        env=child_env,
    )
    assert stamp_result["ok"] is True

    sweep_result = hb.sweep(repo, env=os.environ, now=now + 1)
    assert sweep_result["ok"] is True
    entry = next(e for e in sweep_result["launches"] if e["launchId"] == launch_id)
    assert entry["class"] == "fresh"
    assert entry["phase"] == "child-dispatch"


def test_e2e_survives_ambient_launcher_env(tmp_path):
    """#843 guard: re-run the e2e test in a child pytest carrying the env a launcher-issued
    session exports. Without conftest's env pin the ambient SUPERHEROES_HEARTBEAT_ROOT redirects
    the sweep away from the test's own root and the child run fails. CI sets neither var, so this
    subprocess is what makes the regression visible there rather than only in a real launcher
    session.
    """
    decoy = tmp_path / "decoy-heartbeat-root"
    decoy.mkdir(mode=0o700)
    child_env = dict(os.environ)
    child_env[hb.HEARTBEAT_ROOT_ENV] = str(decoy)
    child_env[hb.LAUNCH_ID_ENV] = "ambient-launch"
    proc = subprocess.run(
        [
            sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
            "%s::test_e2e_child_stamp_visible_from_primary_checkout" % _THIS_FILE,
        ],
        capture_output=True,
        text=True,
        env=child_env,
    )
    assert proc.returncode == 0, proc.stdout[-4000:] + proc.stderr[-2000:]


# --- CLI smoke ----------------------------------------------------------------


def test_cli_stamp_prints_json(tmp_path, monkeypatch, capsys):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.setenv(hb.LAUNCH_ID_ENV, "cli-lane")
    rc = hb.main([
        "stamp",
        "--repo-root", repo,
        "--state", "working",
        "--phase", "cli",
        "--stale-after", "60",
    ])
    out = json.loads(capsys.readouterr().out.strip())
    assert rc == 0
    assert out["ok"] is True


def test_cli_read_prints_json(tmp_path, monkeypatch, capsys):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    fixed_now = time.time()
    hb.stamp(
        repo,
        state="working",
        phase="p",
        launch_id="cli-read",
        now=fixed_now,
        stale_after_seconds=3600,
    )
    monkeypatch.setattr(hb.time, "time", lambda: fixed_now + 1)
    rc = hb.main(["read", "--repo-root", repo, "--launch-id", "cli-read"])
    out = json.loads(capsys.readouterr().out.strip())
    assert rc == 0
    assert out["ok"] is True
    assert out["class"] == "fresh"


# --- F1: sweep always emits in-contract classes --------------------------------


def test_sweep_invalid_launch_id_classifies_unknown_not_none(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    valid_id = "launch-deadbeef"
    invalid_id = "launch-a.b"
    ll.declare_batch(repo, "batch-invalid", 2)
    for launch_id in (valid_id, invalid_id):
        ll.append(repo, _reserved(launch_id, "batch-invalid", ["x"], repo))
        ll.append(repo, _started(launch_id))
    result = hb.sweep(repo, now=1_000_000.0)
    assert result["ok"] is True
    for entry in result["launches"]:
        assert entry["class"] in hb.SWEEP_CLASSES, entry
    invalid_entry = next(e for e in result["launches"] if e["launchId"] == invalid_id)
    assert invalid_entry["class"] == "unknown"
    assert invalid_entry["class"] is not None
    assert invalid_entry["reason"] == hb.REASON_LAUNCH_ID_INVALID


# --- F2: lastDispatch.startedAt is ISO-8601 UTC string -------------------------


def _last_dispatch(**overrides):
    base = {
        "kind": "implementer",
        "engine": "cursor",
        "model": "composer-2.5",
        "runId": "r1",
        "startedAt": "2026-08-01T14:00:00Z",
    }
    base.update(overrides)
    return base


def test_last_dispatch_iso_started_at_accepted(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    now = 1_000_000.0
    result = hb.stamp(
        repo,
        state="working",
        phase="dispatch",
        launch_id="iso-lane",
        last_dispatch=_last_dispatch(),
        now=now,
    )
    assert result["ok"] is True
    read_back = hb.read_heartbeat(repo, "iso-lane", now=now)
    assert read_back["class"] == "fresh"
    assert read_back["lastDispatch"]["startedAt"] == "2026-08-01T14:00:00Z"


def test_last_dispatch_numeric_started_at_refused(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    result = hb.stamp(
        repo,
        state="working",
        phase="dispatch",
        launch_id="numeric-lane",
        last_dispatch=_last_dispatch(startedAt=1_000_000.0),
        now=1_000_000.0,
    )
    assert result["ok"] is False
    assert result["reason"] == "heartbeat-last-dispatch-invalid"
    path = hb.heartbeat_path(repo, "numeric-lane")
    assert not os.path.isfile(path["path"])


def test_last_dispatch_malformed_started_at_refused(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    result = hb.stamp(
        repo,
        state="working",
        phase="dispatch",
        launch_id="bad-iso-lane",
        last_dispatch=_last_dispatch(startedAt="not-a-timestamp"),
        now=1_000_000.0,
    )
    assert result["ok"] is False
    assert result["reason"] == "heartbeat-last-dispatch-invalid"
    path = hb.heartbeat_path(repo, "bad-iso-lane")
    assert not os.path.isfile(path["path"])


def test_cli_stamp_rejects_numeric_last_dispatch_started_at(tmp_path, monkeypatch, capsys):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.setenv(hb.LAUNCH_ID_ENV, "cli-iso")
    ld = json.dumps(_last_dispatch(startedAt=1_000_000.0))
    rc = hb.main([
        "stamp",
        "--repo-root", repo,
        "--state", "working",
        "--phase", "cli",
        "--last-dispatch", ld,
    ])
    out = json.loads(capsys.readouterr().out.strip())
    assert rc == 1
    assert out["ok"] is False
    assert out["reason"] == "heartbeat-last-dispatch-invalid"


def test_cli_stamp_accepts_iso_last_dispatch_started_at(tmp_path, monkeypatch, capsys):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.setenv(hb.LAUNCH_ID_ENV, "cli-iso-ok")
    ld = json.dumps(_last_dispatch())
    rc = hb.main([
        "stamp",
        "--repo-root", repo,
        "--state", "working",
        "--phase", "cli",
        "--last-dispatch", ld,
    ])
    out = json.loads(capsys.readouterr().out.strip())
    assert rc == 0
    assert out["ok"] is True


# --- floored default promise (#1023) ------------------------------------------


def test_default_stale_after_clears_twice_the_worst_measured_benign_gap():
    # The floor is DERIVED from the measurement's authoritative home, never restated
    # here — a second hardcoded copy is the cross-boundary drift this avoids.
    m = hb.STALE_AFTER_MEASUREMENT
    assert hb.DEFAULT_STALE_AFTER_SECONDS >= m["multiplier"] * m["worstBenignGapSeconds"]
    assert hb.DEFAULT_STALE_AFTER_SECONDS <= hb._STALE_AFTER_MAX
    assert m["benignGaps"] <= m["gaps"]


def test_stamp_without_a_promise_uses_the_floored_default(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    result = hb.stamp(repo, state="working", phase="build", launch_id="lane-a")
    assert result["ok"] is True
    assert hb.read_heartbeat(repo, "lane-a")["staleAfterSeconds"] == (
        hb.DEFAULT_STALE_AFTER_SECONDS
    )


def test_a_long_step_no_longer_classifies_stale_under_the_default(
    tmp_path, monkeypatch,
):
    # A builder an hour into a dispatch, having stated no promise of its own:
    # `stale` on the old 300 s default, `fresh` on the floored one.
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    hb.stamp(
        repo, state="working", phase="build", launch_id="lane-a",
        now=time.time() - 3600,
    )
    assert hb.read_heartbeat(repo, "lane-a")["class"] == "fresh"


def test_cli_stamp_default_promise_matches_the_module_constant(
    tmp_path, monkeypatch, capsys,
):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.setenv(hb.LAUNCH_ID_ENV, "lane-cli")
    rc = hb.main([
        "stamp", "--repo-root", repo, "--state", "working", "--phase", "build",
    ])
    capsys.readouterr()
    assert rc == 0
    assert hb.read_heartbeat(repo, "lane-cli")["staleAfterSeconds"] == (
        hb.DEFAULT_STALE_AFTER_SECONDS
    )
