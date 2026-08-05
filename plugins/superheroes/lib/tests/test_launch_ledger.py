import ast
import fcntl
import inspect
import json
import os
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time

import pytest

import launch_ledger as ll

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)


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
        "issue": 656,
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


def _refused(launch_id, stage="preflight", reason="quota"):
    return {
        "event": "refused",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "stage": stage,
        "reason": reason,
    }


def _batch_declared(batch_id, expected_launches):
    return {
        "event": "batch-declared",
        "batchId": batch_id,
        "expectedLaunches": expected_launches,
        "ts": time.time(),
        "schema": ll.SCHEMA,
    }


def _declare(repo_root, batch_id, expected, env=None):
    return ll.declare_batch(repo_root, batch_id, expected, env=env)


def _ledger_file(repo_root, env):
    return ll.ledger_path(repo_root, env=env)["path"]


def _walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _walk_strings(v)


def _read_path(path):
    with open(path, "rb") as fh:
        return ll._parse_ledger_bytes(fh.read())


def _append_raw(path, record):
    parent = os.path.dirname(path)
    os.makedirs(parent, mode=0o700, exist_ok=True)
    line = json.dumps(record, separators=(",", ":")) + "\n"
    with open(path, "ab") as fh:
        fh.write(line.encode("utf-8"))


def _open_fd_count():
    try:
        return len(os.listdir("/dev/fd"))
    except OSError:
        return 0


_LEDGER_OPEN_ALLOWLIST = frozenset({
    "open_ledger",
    "_open_ledger_dirs",
    "_ensure_lock_file",
})


# --- fail-closed edges -------------------------------------------------------


def test_read_torn_trailing_line(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    _append_raw(path, {"event": "reserved", "launchId": "a", "ts": 1.0, "schema": 1,
                       "batchId": "b", "repoId": "r", "issue": 1, "surfaces": ["x"],
                       "premise": {}, "preflight": {}, "argv": [], "doctrineDigest": "d",
                       "model": "m"})
    _append_raw(path, {"event": "started", "launchId": "a", "ts": 2.0, "schema": 1,
                     "attempt": 1, "pid": 424242, "logPath": "/l", "errPath": "/e"})
    with open(path, "rb") as fh:
        raw = fh.read()
    with open(path, "wb") as fh:
        fh.write(raw.rstrip(b"\n"))
    result = _read_path(path)
    assert result["state"] == "tornTail"
    assert result["state"] != "ok"
    assert len(result["records"]) == 1


def test_read_interior_corruption(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("not-json\n")
    _append_raw(path, {"event": "x"})
    result = _read_path(path)
    assert result["state"] == "interiorCorrupt"


def test_read_interior_corruption_wins_over_torn_tail(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("not-json\n")
        fh.write('{"ok":true}')  # no trailing newline
    result = _read_path(path)
    assert result["state"] == "interiorCorrupt"


def test_read_missing_file(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    result = ll.read(repo)
    assert result["state"] == "missing"
    assert result["records"] == []


def test_read_unreadable_file(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.append(repo, {"x": 1})
    path = _ledger_file(repo, os.environ)
    os.chmod(path, 0o000)
    try:
        result = ll.read(repo)
        assert result["state"] == "unreadable"
    finally:
        os.chmod(path, 0o600)


def test_resolve_root_inside_repo(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    inside = os.path.join(repo, "inside-ledger")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, inside)
    result = ll.resolve_root(repo)
    assert result["ok"] is False
    assert result["reason"] == "ledger-root-in-repo"


def test_resolve_root_symlink_component(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    real_root = tmp_path / "real-ledger"
    os.makedirs(real_root, mode=0o700)
    link = tmp_path / "link-ledger"
    link.symlink_to(real_root)
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(link))
    result = ll.resolve_root(repo)
    assert result["ok"] is True
    assert result["root"] == os.path.realpath(str(real_root))


def test_resolve_root_unusable(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    bad = str(tmp_path / "not-a-dir")
    with open(bad, "w", encoding="utf-8") as fh:
        fh.write("file")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, bad)
    result = ll.resolve_root(repo)
    assert result["ok"] is False
    assert result["reason"] == "ledger-root-unusable"


def test_resolve_root_repo_identity_unavailable(tmp_path, monkeypatch):
    not_repo = str(tmp_path / "plain")
    os.makedirs(not_repo)
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    result = ll.resolve_root(not_repo)
    assert result["ok"] is False
    assert result["reason"] == "ledger-repo-identity-unavailable"


def test_append_failure_returns_false(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    ledger_root = str(tmp_path / "ledger-root")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, ledger_root)
    os.makedirs(ledger_root, mode=0o500)
    assert ll.append(repo, {"x": 1}) is False


def test_reserve_surface_overlap(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    env = {ll.LEDGER_ROOT_ENV: str(tmp_path / "ledger")}
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, env[ll.LEDGER_ROOT_ENV])
    r1 = ll.reserve(repo, _reserved("l1", "b1", ["plugins/superheroes/lib"], repo), env=env)
    assert r1["ok"] is True
    r2 = ll.reserve(repo, _reserved("l2", "b2", ["plugins/superheroes"], repo), env=env)
    assert r2["ok"] is False
    assert r2["reason"] == "surface-overlap:l1"


def test_reserve_lock_unavailable(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    lock_result = ll._ensure_lock_file(repo)
    assert lock_result["ok"] is True
    lock_path = lock_result["path"]
    import file_lock
    file_lock.acquire(lock_path)
    os.chmod(lock_path, 0o600)
    try:
        result = ll.reserve(
            repo,
            _reserved("l1", "b1", ["a"], repo),
            lock_timeout=0.1,
        )
        assert result["ok"] is False
        assert result["reason"] == "lock-unavailable"
    finally:
        file_lock.release(lock_path)


def test_normalize_surfaces_absolute(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    result = ll.normalize_surfaces(repo, ["/absolute/path"])
    assert result["ok"] is False
    assert result["reason"] == "surface-absolute"


def test_normalize_surfaces_escapes_repo(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    result = ll.normalize_surfaces(repo, ["../outside"])
    assert result["ok"] is False
    assert result["reason"] == "surface-escapes-repo"


def test_normalize_surfaces_empty_entry(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    result = ll.normalize_surfaces(repo, ["  "])
    assert result["ok"] is False
    assert result["reason"] == "surface-empty"


def test_normalize_surfaces_empty_list(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    result = ll.normalize_surfaces(repo, [])
    assert result["ok"] is False
    assert result["reason"] == "surfaces-empty"


@pytest.mark.parametrize(
    "records,reason",
    [
        ([{"event": "bogus", "launchId": "x", "ts": 1.0, "schema": 1}],
         "fold-unknown-event:bogus"),
        (["not-a-dict"], "fold-not-an-object"),
        ([{"event": "reserved", "launchId": "a", "ts": 1.0, "schema": 1}],
         "fold-missing-field:reserved:batchId"),
        (
            [
                _reserved("a", "b", ["x"], "/tmp"),
                _reserved("a", "b", ["x"], "/tmp"),
            ],
            "fold-duplicate-reserved:a",
        ),
        ([_started("orphan")], "fold-orphan-event:orphan"),
        (
            [_reserved("a", "b", ["x"], "/tmp"), _refused("a"), _outcome("a")],
            "fold-conflicting-terminal:a",
        ),
        (
            [_reserved("a", "b", ["x"], "/tmp"), {**_outcome("a"), "outcome": "bogus"}],
            "fold-bad-outcome:a",
        ),
        (
            [_reserved("a", "b", ["x"], "/tmp"), {**_outcome("a"), "evidence": ""}],
            "fold-missing-evidence:a",
        ),
        (
            [_reserved("a", "b", ["x"], "/tmp"), {**_started("a"), "attempt": "x"}],
            "fold-bad-field:started:attempt",
        ),
        (
            [{"event": "reserved", "launchId": "a", "ts": 1.0, "schema": 9,
              "batchId": "b", "repoId": "r", "issue": 1, "surfaces": ["x"],
              "premise": {}, "preflight": {}, "argv": [], "doctrineDigest": "d",
              "model": "m"}],
            "fold-schema:9",
        ),
        (
            [_reserved("a", "b", ["x"], "/tmp"), _started("a"), _refused("a")],
            "fold-refused-after-started:a",
        ),
    ],
)
def test_fold_violations(records, reason):
    result = ll.fold(records)
    assert result["ok"] is False
    assert result["reason"] == reason


def test_record_outcome_unknown_launch(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    result = ll.record_outcome(repo, "missing", "handback", "evidence")
    assert result["ok"] is False
    assert result["reason"] == "outcome-unknown-launch"


def test_record_outcome_already_terminal(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
    result = ll.record_outcome(repo, "l1", "handback", "again")
    assert result == {
        "ok": True,
        "reason": None,
        "recorded": "amendment",
        "amendmentKind": "reoutcome",
        "attemptedOutcome": "handback",
        "terminalOutcome": "handback",
    }


def test_record_outcome_invalid_value(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    result = ll.record_outcome(repo, "l1", "bogus", "evidence")
    assert result["ok"] is False
    assert result["reason"] == "outcome-invalid:bogus"


def test_record_outcome_empty_evidence(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    result = ll.record_outcome(repo, "l1", "handback", "   ")
    assert result["ok"] is False
    assert result["reason"] == "outcome-evidence-empty"


# --- round trip --------------------------------------------------------------


def test_round_trip_reserve_started_outcome_count(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "wave-test"
    launch = "launch-1"
    assert _declare(repo, batch, 1)["ok"]
    assert ll.reserve(repo, _reserved(launch, batch, ["plugins/superheroes/lib"], repo))["ok"]
    _append_raw(_ledger_file(repo, os.environ), _started(launch))
    assert ll.record_outcome(repo, launch, "handback", "shipped")["ok"]
    result = ll.count(repo, batch)
    assert result["resolved"] is True
    assert result["indeterminate"] is False
    assert result["counts"]["handback"] == 1
    assert result["counts"]["total"] == 1


# --- count honesty axes ------------------------------------------------------


def test_count_indeterminate_on_torn_tail(tmp_path, monkeypatch):
    # Axis: refusal to report a rate it cannot ground.
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-torn"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo))
    path = _ledger_file(repo, os.environ)
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
    with open(path, "rb") as fh:
        raw = fh.read()
    with open(path, "wb") as fh:
        fh.write(raw.rstrip(b"\n"))
    result = ll.count(repo, batch)
    assert result["indeterminate"] is True
    assert result["resolved"] is False


def test_count_indeterminate_on_interior_corruption(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-corrupt"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo))
    path = _ledger_file(repo, os.environ)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("garbage\n")
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
    result = ll.count(repo, batch)
    assert result["indeterminate"] is True
    assert result["resolved"] is False
    assert result["reason"] == "ledger-interiorCorrupt"


def test_count_indeterminate_on_unresolved_member(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-unresolved"
    _declare(repo, batch, 2)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo, issue=101))
    ll.reserve(repo, _reserved("l2", batch, ["b"], repo, issue=102))
    path = _ledger_file(repo, os.environ)
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    ll.record_outcome(repo, "l1", "handback", "done")
    result = ll.count(repo, batch)
    assert result["indeterminate"] is True
    assert result["resolved"] is False
    assert result["reason"] == "batch-unresolved:l2"


def test_count_indeterminate_on_empty_batch(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "other-batch", ["a"], repo))
    result = ll.count(repo, "no-such-batch")
    assert result["indeterminate"] is True
    assert result["resolved"] is False
    assert result["reason"] == "batch-empty"


def test_count_indeterminate_on_missing_ledger(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    result = ll.count(repo, "any")
    assert result["indeterminate"] is True
    assert result["reason"] == "ledger-missing"


def test_count_flags_zero_park_batch(tmp_path, monkeypatch):
    # Axis: the zero-signal flag fires.
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-zero-park"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo))
    path = _ledger_file(repo, os.environ)
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    ll.record_outcome(repo, "l1", "handback", "done")
    result = ll.count(repo, batch)
    assert result["resolved"] is True
    assert result["inspect"] is True
    assert result["inspectReason"]
    assert "never a clean sheet" in result["inspectReason"]


def test_count_does_not_flag_when_a_park_exists(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-park"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo))
    path = _ledger_file(repo, os.environ)
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    ll.record_outcome(repo, "l1", "park", "blocked")
    result = ll.count(repo, batch)
    assert result["resolved"] is True
    assert result["inspect"] is False


def test_refused_launch_is_counted(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-refused"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo))
    path = _ledger_file(repo, os.environ)
    _append_raw(_ledger_file(repo, os.environ), _refused("l1"))
    result = ll.count(repo, batch)
    assert result["resolved"] is True
    assert result["counts"]["refusedToLaunch"] == 1


def test_no_output_string_says_clean(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-inspect-check"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo))
    path = _ledger_file(repo, os.environ)
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    ll.record_outcome(repo, "l1", "handback", "done")
    result = ll.count(repo, batch)
    for s in _walk_strings(result):
        lower = s.lower()
        if "clean" in lower:
            assert "never a clean sheet" in lower


# --- ancestor overlap --------------------------------------------------------


def test_surfaces_overlap_ancestor(tmp_path):
    assert ll.surfaces_overlap(["plugins/superheroes/lib"], ["plugins/superheroes"])


def test_surfaces_overlap_not_prefix_collision():
    assert ll.surfaces_overlap(["a/b"], ["a/bc"]) is False


def test_surfaces_overlap_whole_repo():
    assert ll.surfaces_overlap([ll.WHOLE_REPO], ["anything"]) is True
    assert ll.surfaces_overlap(["x"], [ll.WHOLE_REPO]) is True


def test_surfaces_overlap_case_insensitive():
    assert ll.surfaces_overlap(["Plugins/Superheroes"], ["plugins/superheroes/lib"])


# --- concurrency guarantee ---------------------------------------------------
# test_reserve_refuses_when_lock_is_held is the deterministic bite test for the
# lock guarantee: it fails if reserve proceeds without holding the interprocess
# lock. test_concurrent_reserve_overlapping_surfaces is a realistic-conditions
# test for two-process contention; the waited assertions exist because this
# test previously passed while synchronizing nothing (per-process monotonic
# clocks are not comparable across processes).


def test_reserve_refuses_when_lock_is_held(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    launch_id = "lock-held-bite"
    lock_result = ll._ensure_lock_file(repo)
    assert lock_result["ok"] is True
    lock_path = lock_result["path"]
    import file_lock
    file_lock.acquire(lock_path)
    os.chmod(lock_path, 0o600)
    try:
        result = ll.reserve(
            repo,
            _reserved(launch_id, "bite", ["plugins/superheroes/lib"], repo),
            lock_timeout=0.1,
        )
        assert result["ok"] is False
        assert result["reason"] == "lock-unavailable"
        records = ll.read(repo)["records"]
        reserved = [r for r in records if r.get("event") == "reserved"
                    and r.get("launchId") == launch_id]
        assert reserved == []
    finally:
        file_lock.release(lock_path)


def test_concurrent_reserve_overlapping_surfaces(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    ledger_root = str(tmp_path / "ledger")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, ledger_root)
    mod_path = os.path.join(_LIB, "launch_ledger.py")
    gate_dir = str(tmp_path / "gate")
    os.makedirs(gate_dir, exist_ok=True)
    n_workers = 2
    child = """
import json, os, sys, time
sys.path.insert(0, os.path.dirname(%(mod)r))
os.environ[%(_envkey)r] = %(_envval)r
import importlib.util
spec = importlib.util.spec_from_file_location("launch_ledger", %(mod)r)
ll = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ll)
repo = %(repo)r
launch_id = "child-" + str(os.getpid())
record = {
    "event": "reserved", "launchId": launch_id, "ts": time.time(), "schema": ll.SCHEMA,
    "batchId": "conc", "repoId": ll.repo_identity(repo), "issue": 1,
    "surfaces": ["plugins/superheroes/lib"],
    "premise": {}, "preflight": {}, "argv": [], "doctrineDigest": "d", "model": "m",
}
gate = %(gate)r
open(os.path.join(gate, str(os.getpid())), "w").close()
deadline = time.time() + 5
while len(os.listdir(gate)) < %(n_workers)d:
    if time.time() >= deadline:
        print("BARRIER-TIMEOUT")
        sys.exit(1)
    time.sleep(0.001)
res = ll.reserve(repo, record, lock_timeout=5)
print(json.dumps(res))
""" % {
        "mod": mod_path,
        "_envkey": ll.LEDGER_ROOT_ENV,
        "_envval": ledger_root,
        "repo": repo,
        "gate": gate_dir,
        "n_workers": n_workers,
    }
    procs = [
        subprocess.Popen([sys.executable, "-c", child], stdout=subprocess.PIPE, text=True)
        for _ in range(n_workers)
    ]
    outcomes = []
    try:
        for worker_idx, proc in enumerate(procs):
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pytest.fail(
                    "concurrent reserve: worker %d timed out; outcomes so far: %s"
                    % (worker_idx, outcomes)
                )
            outcome = proc.stdout.read().strip()
            if outcome == "BARRIER-TIMEOUT":
                pytest.fail(
                    "concurrent reserve: worker %d hit barrier timeout; "
                    "outcomes so far: %s" % (worker_idx, outcomes)
                )
            outcomes.append(json.loads(outcome))
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.kill()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
    ok_count = sum(1 for r in outcomes if r.get("ok"))
    assert ok_count == 1
    other = [r for r in outcomes if not r.get("ok")]
    assert len(other) == 1
    reason = other[0]["reason"]
    assert reason.startswith("surface-overlap:") or reason == "lock-unavailable"
    records = ll.read(repo)["records"]
    reserved = [r for r in records if r.get("event") == "reserved"]
    assert len(reserved) == 1
    assert reserved[0]["surfaces"] == ["plugins/superheroes/lib"]


# --- append/read basics ------------------------------------------------------


def test_append_creates_restricted_file(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    assert ll.append(repo, {"x": 1})
    path = _ledger_file(repo, os.environ)
    mode = os.stat(path).st_mode & 0o777
    assert mode == 0o600


def test_repo_identity_stable(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    a = ll.repo_identity(repo)
    b = ll.repo_identity(repo)
    assert a and a == b


def test_normalize_surfaces_collapses_and_sorts(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    result = ll.normalize_surfaces(repo, ["./b/a", "b/a/"])
    assert result["ok"] is True
    assert result["surfaces"] == ["b/a"]


# --- WO-L fail-closed edges 1-18 ---------------------------------------------


def test_edge1_invalid_utf8_returns_interior_corrupt(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    valid = json.dumps({
        "event": "reserved", "launchId": "a", "ts": 1.0, "schema": 1,
        "batchId": "b", "repoId": "r", "issue": 1, "surfaces": ["x"],
        "premise": {}, "preflight": {}, "argv": [], "doctrineDigest": "d",
        "model": "m",
    }).encode("utf-8")
    with open(path, "wb") as fh:
        fh.write(valid[:-2])
        fh.write(b"\xff\xfe")
        fh.write(valid[-2:])
        fh.write(b"\n")
    result = _read_path(path)
    assert result["state"] == "interiorCorrupt"


def test_edge2_repo_id_dir_symlink_refused(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    ledger_root = str(tmp_path / "ledger-root")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, ledger_root)
    repo_id = ll.repo_identity(repo)
    os.makedirs(ledger_root, mode=0o700, exist_ok=True)
    real_dir = os.path.join(ledger_root, "real-target")
    os.makedirs(real_dir, mode=0o700)
    os.symlink(real_dir, os.path.join(ledger_root, repo_id))
    result = ll.open_ledger(repo, "a")
    assert result["ok"] is False
    assert result["reason"] == "ledger-repo-dir-symlink"


def test_edge3_ledger_file_symlink_refused(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    ledger_root = str(tmp_path / "ledger-root")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, ledger_root)
    repo_id = ll.repo_identity(repo)
    os.makedirs(ledger_root, mode=0o700, exist_ok=True)
    repo_dir = os.path.join(ledger_root, repo_id)
    os.makedirs(repo_dir, mode=0o700)
    real_file = os.path.join(tmp_path, "real-ledger.jsonl")
    with open(real_file, "w", encoding="utf-8") as fh:
        fh.write("")
    os.symlink(real_file, os.path.join(repo_dir, ll.LEDGER_NAME))
    result = ll.open_ledger(repo, "a")
    assert result["ok"] is False
    assert result["reason"] == "ledger-file-symlink"


def test_edge4_lock_path_symlink_refused(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    ledger_root = str(tmp_path / "ledger-root")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, ledger_root)
    repo_id = ll.repo_identity(repo)
    os.makedirs(ledger_root, mode=0o700, exist_ok=True)
    repo_dir = os.path.join(ledger_root, repo_id)
    os.makedirs(repo_dir, mode=0o700)
    real_lock = os.path.join(tmp_path, "real.lock")
    with open(real_lock, "w", encoding="utf-8") as fh:
        fh.write("")
    os.symlink(real_lock, os.path.join(repo_dir, ll.LEDGER_NAME + ".lock"))
    result = ll._ensure_lock_file(repo)
    assert result["ok"] is False
    assert result["reason"] == "ledger-lock-symlink"


def test_edge5_canonical_path_overlap_same_repo(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    pkg = tmp_path / "repo" / "pkg"
    pkg.mkdir()
    (pkg / "x").mkdir()
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    r1 = ll.reserve(repo, _reserved("l1", "b1", ["pkg/x"], repo))
    assert r1["ok"] is True
    r2 = ll.reserve(repo, _reserved("l2", "b2", ["pkg/../pkg/x"], repo))
    assert r2["ok"] is False
    assert r2["reason"].startswith("surface-overlap:")


def test_edge6_symlinked_alias_surface_overlap(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    real_dir = tmp_path / "repo" / "real" / "target"
    real_dir.mkdir(parents=True)
    alias = tmp_path / "repo" / "alias"
    alias.parent.mkdir(parents=True, exist_ok=True)
    alias.symlink_to(real_dir)
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    r1 = ll.reserve(repo, _reserved("l1", "b1", ["real/target"], repo))
    assert r1["ok"] is True
    r2 = ll.reserve(repo, _reserved("l2", "b2", ["alias"], repo))
    assert r2["ok"] is False
    assert r2["reason"].startswith("surface-overlap:")


def test_edge7_record_outcome_without_started_refused(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    result = ll.record_outcome(repo, "l1", "handback", "evidence")
    assert result["ok"] is False
    assert result["reason"] == "outcome-without-started"


def test_edge8_fold_outcome_without_started_refuses(tmp_path):
    records = [_reserved("a", "b", ["x"], "/tmp")]
    records.append(_outcome("a"))
    result = ll.fold(records)
    assert result["ok"] is False
    assert result["reason"] == "fold-outcome-without-started:a"


def test_edge9_count_indeterminate_without_batch_declared(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-nodecl"
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo))
    path = _ledger_file(repo, os.environ)
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
    result = ll.count(repo, batch)
    assert result["indeterminate"] is True
    assert result["reason"] == "batch-undeclared"


def test_edge10_count_indeterminate_on_duplicate_declaration(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-dup"
    _declare(repo, batch, 1)
    path = _ledger_file(repo, os.environ)
    _append_raw(_ledger_file(repo, os.environ), _batch_declared(batch, 1))
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo))
    path = _ledger_file(repo, os.environ)
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
    result = ll.count(repo, batch)
    assert result["indeterminate"] is True
    assert result["reason"] == "batch-duplicate-declaration"


def test_edge11_count_indeterminate_when_reservations_below_declared(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-short"
    _declare(repo, batch, 2)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo))
    path = _ledger_file(repo, os.environ)
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
    result = ll.count(repo, batch)
    assert result["indeterminate"] is True
    assert result["reason"] == "batch-reservation-mismatch"


def test_edge12_count_indeterminate_when_reservations_above_declared(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-over"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo, issue=201))
    ll.reserve(repo, _reserved("l2", batch, ["b"], repo, issue=202))
    path = _ledger_file(repo, os.environ)
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
    _append_raw(_ledger_file(repo, os.environ), _started("l2"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l2"))
    result = ll.count(repo, batch)
    assert result["indeterminate"] is True
    assert result["reason"] == "batch-reservation-mismatch"


def test_edge13_count_inspect_true_on_zero_park_refusal_refused_to_launch(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-inspect-ok"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo))
    path = _ledger_file(repo, os.environ)
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1", outcome="handback"))
    result = ll.count(repo, batch)
    assert result["resolved"] is True
    assert result["inspect"] is True
    assert "never a clean sheet" in result["inspectReason"]


def test_edge14_count_refused_to_launch_only_not_inspect(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-refused-only"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo))
    path = _ledger_file(repo, os.environ)
    _append_raw(_ledger_file(repo, os.environ), _refused("l1"))
    result = ll.count(repo, batch)
    assert result["resolved"] is True
    assert result["inspect"] is False
    assert result["counts"]["refusedToLaunch"] == 1
    assert "never a clean sheet" not in result["inspectReason"]


def test_edge15_overlap_refusal_names_blocking_launch(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("blocker", "b1", ["plugins/superheroes/lib"], repo))
    path = _ledger_file(repo, os.environ)
    _append_raw(_ledger_file(repo, os.environ), _started("blocker"))
    result = ll.reserve(repo, _reserved("l2", "b2", ["plugins/superheroes"], repo))
    assert result["ok"] is False
    assert result["reason"] == "surface-overlap:blocker"
    assert result["blockingLaunchId"] == "blocker"
    assert result["blockingSurfaces"] == ["plugins/superheroes/lib"]


def test_edge16_preexisting_ledger_dir_insecure_refused(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    ledger_root = str(tmp_path / "ledger-root")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, ledger_root)
    repo_id = ll.repo_identity(repo)
    os.makedirs(ledger_root, mode=0o700, exist_ok=True)
    os.makedirs(os.path.join(ledger_root, repo_id), mode=0o755)
    result = ll.open_ledger(repo, "a")
    assert result["ok"] is False
    assert result["reason"] == "ledger-repo-dir-insecure"


def test_edge17_preexisting_ledger_file_insecure_refused(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    ledger_root = str(tmp_path / "ledger-root")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, ledger_root)
    repo_id = ll.repo_identity(repo)
    os.makedirs(ledger_root, mode=0o700, exist_ok=True)
    repo_dir = os.path.join(ledger_root, repo_id)
    os.makedirs(repo_dir, mode=0o700)
    ledger_file = os.path.join(repo_dir, ll.LEDGER_NAME)
    with open(ledger_file, "w", encoding="utf-8") as fh:
        fh.write("")
    os.chmod(ledger_file, 0o644)
    result = ll.open_ledger(repo, "a")
    assert result["ok"] is False
    assert result["reason"] == "ledger-file-insecure"


def test_edge18_fold_retry_before_started_is_legal(tmp_path):
    records = [_reserved("a", "b", ["x"], "/tmp")]
    records.append({
        "event": "retry",
        "launchId": "a",
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "attempt": 1,
        "reason": "backoff",
        "delaySeconds": 1.0,
    })
    result = ll.fold(records)
    assert result["ok"] is True
    assert result["launches"]["a"]["terminal"] is False


# --- WO-C1 chokepoint edges 1-20 + census -----------------------------------


def _census_violations(source_path, allowlist):
    with open(source_path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=source_path)
    violations = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name in allowlist:
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            func = child.func
            is_open = (
                isinstance(func, ast.Name) and func.id == "open"
            ) or (
                isinstance(func, ast.Attribute) and func.attr == "open"
            )
            if is_open:
                violations.append(node.name)
                break
    return violations


def test_c1_edge1_default_root_macos_succeeds(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.delenv(ll.LEDGER_ROOT_ENV, raising=False)
    result = ll.open_ledger(repo, "a")
    assert result["ok"] is True, result
    result["fh"].close()


def test_c1_edge2_configured_root_symlink_accepted(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    real_root = tmp_path / "real-ledger"
    os.makedirs(real_root, mode=0o700)
    link = tmp_path / "link-ledger"
    link.symlink_to(real_root)
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(link))
    result = ll.open_ledger(repo, "a")
    assert result["ok"] is True, result
    result["fh"].close()


def test_c1_edge3_resolved_root_inside_repo_refused(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    inside = os.path.join(repo, "inside-ledger")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, inside)
    result = ll.open_ledger(repo, "a")
    assert result["ok"] is False
    assert result["reason"] == "ledger-root-in-repo"


def test_c1_edge4_resolved_root_inside_git_common_dir_refused(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    proc = subprocess.run(
        ["git", "-C", repo, "rev-parse", "--git-common-dir"],
        capture_output=True,
        text=True,
        check=True,
    )
    common = proc.stdout.strip()
    if not os.path.isabs(common):
        common = os.path.join(repo, common)
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, common)
    result = ll.open_ledger(repo, "a")
    assert result["ok"] is False
    assert result["reason"] == "ledger-root-in-repo"


def test_c1_edge5_resolved_root_group_world_accessible_refused(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    ledger_root = str(tmp_path / "ledger-root")
    os.makedirs(ledger_root, mode=0o755)
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, ledger_root)
    result = ll.open_ledger(repo, "a")
    assert result["ok"] is False
    assert result["reason"] == "ledger-root-insecure"


def test_c1_edge6_repo_id_symlink_refused(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    ledger_root = str(tmp_path / "ledger-root")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, ledger_root)
    repo_id = ll.repo_identity(repo)
    os.makedirs(ledger_root, mode=0o700, exist_ok=True)
    real_dir = os.path.join(ledger_root, "real-target")
    os.makedirs(real_dir, mode=0o700)
    os.symlink(real_dir, os.path.join(ledger_root, repo_id))
    result = ll.open_ledger(repo, "a")
    assert result["ok"] is False
    assert result["reason"] == "ledger-repo-dir-symlink"


def test_c1_edge7_repo_id_regular_file_refused(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    ledger_root = str(tmp_path / "ledger-root")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, ledger_root)
    repo_id = ll.repo_identity(repo)
    os.makedirs(ledger_root, mode=0o700, exist_ok=True)
    with open(os.path.join(ledger_root, repo_id), "w", encoding="utf-8") as fh:
        fh.write("not-a-dir")
    result = ll.open_ledger(repo, "a")
    assert result["ok"] is False
    assert result["reason"] in ("ledger-repo-dir-not-directory", "ledger-repo-dir-unusable")


def test_c1_edge8_repo_id_group_world_accessible_refused(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    ledger_root = str(tmp_path / "ledger-root")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, ledger_root)
    repo_id = ll.repo_identity(repo)
    os.makedirs(ledger_root, mode=0o700, exist_ok=True)
    os.makedirs(os.path.join(ledger_root, repo_id), mode=0o755)
    result = ll.open_ledger(repo, "a")
    assert result["ok"] is False
    assert result["reason"] == "ledger-repo-dir-insecure"


def test_c1_edge9_ledger_file_symlink_refused(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    ledger_root = str(tmp_path / "ledger-root")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, ledger_root)
    repo_id = ll.repo_identity(repo)
    os.makedirs(ledger_root, mode=0o700, exist_ok=True)
    repo_dir = os.path.join(ledger_root, repo_id)
    os.makedirs(repo_dir, mode=0o700)
    real_file = os.path.join(tmp_path, "real-ledger.jsonl")
    with open(real_file, "w", encoding="utf-8") as fh:
        fh.write("")
    os.symlink(real_file, os.path.join(repo_dir, ll.LEDGER_NAME))
    result = ll.open_ledger(repo, "a")
    assert result["ok"] is False
    assert result["reason"] == "ledger-file-symlink"


def test_c1_edge10_ledger_fifo_refused_without_blocking(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    ledger_root = str(tmp_path / "ledger-root")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, ledger_root)
    repo_id = ll.repo_identity(repo)
    os.makedirs(ledger_root, mode=0o700, exist_ok=True)
    repo_dir = os.path.join(ledger_root, repo_id)
    os.makedirs(repo_dir, mode=0o700)
    fifo_path = os.path.join(repo_dir, ll.LEDGER_NAME)
    os.mkfifo(fifo_path)
    start = time.monotonic()
    result = ll.open_ledger(repo, "r")
    elapsed = time.monotonic() - start
    assert elapsed < 5.0, "open_ledger blocked on FIFO read path"
    assert result["ok"] is False
    assert result["reason"] == "ledger-file-not-regular"


def test_c1_edge10_append_ledger_fifo_refused_without_blocking(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    ledger_root = str(tmp_path / "ledger-root")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, ledger_root)
    repo_id = ll.repo_identity(repo)
    os.makedirs(ledger_root, mode=0o700, exist_ok=True)
    repo_dir = os.path.join(ledger_root, repo_id)
    os.makedirs(repo_dir, mode=0o700)
    fifo_path = os.path.join(repo_dir, ll.LEDGER_NAME)
    os.mkfifo(fifo_path)
    start = time.monotonic()
    result = ll.open_ledger(repo, "a")
    elapsed = time.monotonic() - start
    assert elapsed < 5.0, "open_ledger blocked on FIFO append path"
    assert result["ok"] is False
    assert result["reason"] == "ledger-file-not-regular"


def test_c1_open_ledger_clears_nonblock_on_regular_file(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    ledger_root = str(tmp_path / "ledger-root")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, ledger_root)
    repo_id = ll.repo_identity(repo)
    os.makedirs(ledger_root, mode=0o700, exist_ok=True)
    repo_dir = os.path.join(ledger_root, repo_id)
    os.makedirs(repo_dir, mode=0o700)
    ledger_file = os.path.join(repo_dir, ll.LEDGER_NAME)
    with open(ledger_file, "w", encoding="utf-8") as fh:
        fh.write("")
    os.chmod(ledger_file, 0o600)

    read_result = ll.open_ledger(repo, "r")
    assert read_result["ok"] is True, read_result
    try:
        flags = fcntl.fcntl(read_result["fh"].fileno(), fcntl.F_GETFL)
        assert not (flags & os.O_NONBLOCK)
    finally:
        read_result["fh"].close()

    append_result = ll.open_ledger(repo, "a")
    assert append_result["ok"] is True, append_result
    try:
        flags = fcntl.fcntl(append_result["fh"].fileno(), fcntl.F_GETFL)
        assert not (flags & os.O_NONBLOCK)
        mode = os.stat(ledger_file).st_mode & 0o777
        assert mode == 0o600
    finally:
        append_result["fh"].close()

    repo2 = _init_repo(tmp_path / "repo2")
    fresh_result = ll.open_ledger(repo2, "a")
    assert fresh_result["ok"] is True, fresh_result
    try:
        flags = fcntl.fcntl(fresh_result["fh"].fileno(), fcntl.F_GETFL)
        assert not (flags & os.O_NONBLOCK)
        fresh_path = fresh_result["path"]
        mode = os.stat(fresh_path).st_mode & 0o777
        assert mode == 0o600
    finally:
        fresh_result["fh"].close()


def test_c1_edge11_ledger_file_group_world_accessible_refused(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    ledger_root = str(tmp_path / "ledger-root")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, ledger_root)
    repo_id = ll.repo_identity(repo)
    os.makedirs(ledger_root, mode=0o700, exist_ok=True)
    repo_dir = os.path.join(ledger_root, repo_id)
    os.makedirs(repo_dir, mode=0o700)
    ledger_file = os.path.join(repo_dir, ll.LEDGER_NAME)
    with open(ledger_file, "w", encoding="utf-8") as fh:
        fh.write("")
    os.chmod(ledger_file, 0o644)
    result = ll.open_ledger(repo, "a")
    assert result["ok"] is False
    assert result["reason"] == "ledger-file-insecure"


def test_c1_edge12_lock_file_symlink_refused(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    ledger_root = str(tmp_path / "ledger-root")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, ledger_root)
    repo_id = ll.repo_identity(repo)
    os.makedirs(ledger_root, mode=0o700, exist_ok=True)
    repo_dir = os.path.join(ledger_root, repo_id)
    os.makedirs(repo_dir, mode=0o700)
    real_lock = os.path.join(tmp_path, "real.lock")
    with open(real_lock, "w", encoding="utf-8") as fh:
        fh.write("")
    os.symlink(real_lock, os.path.join(repo_dir, ll.LEDGER_NAME + ".lock"))
    result = ll._ensure_lock_file(repo)
    assert result["ok"] is False
    assert result["reason"] == "ledger-lock-symlink"


def test_c1_edge13_lock_file_group_world_accessible_accepted(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    ledger_root = str(tmp_path / "ledger-root")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, ledger_root)
    repo_id = ll.repo_identity(repo)
    os.makedirs(ledger_root, mode=0o700, exist_ok=True)
    repo_dir = os.path.join(ledger_root, repo_id)
    os.makedirs(repo_dir, mode=0o700)
    lock_file = os.path.join(repo_dir, ll.LEDGER_NAME + ".lock")
    with open(lock_file, "w", encoding="utf-8") as fh:
        fh.write("")
    os.chmod(lock_file, 0o644)
    result = ll._ensure_lock_file(repo)
    assert result["ok"] is True


def test_c1_edge14_mode_read_missing_ledger(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    opened = ll.open_ledger(repo, "r")
    assert opened["ok"] is False
    assert opened["reason"] == "ledger-missing"
    assert ll.read(repo)["state"] == "missing"


def test_c1_edge15_refusal_paths_close_descriptors(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    ledger_root = str(tmp_path / "ledger-root")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, ledger_root)
    repo_id = ll.repo_identity(repo)
    os.makedirs(ledger_root, mode=0o700, exist_ok=True)
    os.makedirs(os.path.join(ledger_root, repo_id), mode=0o755)
    before = _open_fd_count()
    result = ll.open_ledger(repo, "a")
    after = _open_fd_count()
    assert result["ok"] is False
    assert result["reason"] == "ledger-repo-dir-insecure"
    assert after <= before + 1


def test_c1_edge16_malformed_batch_declared_count_indeterminate(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-malformed"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo))
    path = _ledger_file(repo, os.environ)
    _append_raw(path, {"event": "batch-declared", "batchId": batch, "schema": ll.SCHEMA})
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
    result = ll.count(repo, batch)
    assert result["indeterminate"] is True
    assert result["resolved"] is False


def test_c1_edge17_batch_declared_after_reservations_count_indeterminate(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-late-decl"
    path = _ledger_file(repo, os.environ)
    reserved = _reserved("l1", batch, ["a"], repo)
    reserved["ts"] = 100.0
    ll.reserve(repo, reserved)
    _append_raw(path, {
        "event": "batch-declared",
        "batchId": batch,
        "expectedLaunches": 1,
        "ts": 200.0,
        "schema": ll.SCHEMA,
    })
    _append_raw(path, _started("l1"))
    _append_raw(path, _outcome("l1"))
    result = ll.count(repo, batch)
    assert result["indeterminate"] is True
    assert result["reason"] == "batch-declaration-after-reservations"


def test_c1_edge18_declare_batch_with_existing_reservations_refused(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-has-res"
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo))
    result = ll.declare_batch(repo, batch, 1)
    assert result["ok"] is False
    assert result["reason"] == "batch-already-has-reservations"


def test_c1_edge19_reserved_started_refused_fold_refuses(tmp_path):
    records = [_reserved("a", "b", ["x"], "/tmp"), _started("a"), _refused("a")]
    result = ll.fold(records)
    assert result["ok"] is False
    assert result["reason"] == "fold-refused-after-started:a"


def test_c1_edge20_census_no_ledger_open_outside_accessor():
    ledger_py = os.path.join(_LIB, "launch_ledger.py")
    launcher_py = os.path.join(_LIB, "launcher.py")
    violations = _census_violations(ledger_py, _LEDGER_OPEN_ALLOWLIST)
    assert not violations, (
        "INVARIANT: every read/write to the launch ledger must go through open_ledger; "
        "found open()/os.open() in: %s" % ", ".join(sorted(set(violations)))
    )
    with open(launcher_py, encoding="utf-8") as fh:
        launcher_source = fh.read()
    assert "LEDGER_NAME" not in launcher_source, (
        "INVARIANT: launcher.py must not reference LEDGER_NAME; "
        "reconstruct ledger paths only through launch_ledger.open_ledger"
    )
    assert not (
        "resolve_root" in launcher_source and "repo_identity" in launcher_source
        and "LEDGER_NAME" in launcher_source
    ), (
        "INVARIANT: launcher.py must not reconstruct a ledger path from "
        "resolve_root + repo_identity"
    )


# --- WO-656-A ledger grammar and terminal door --------------------------------


def test_count_indeterminate_on_backdated_declaration(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    batch = "b-backdated"
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo))
    decl = _batch_declared(batch, 1)
    decl["ts"] = 1.0
    ll.append(repo, decl)
    result = ll.count(repo, batch)
    assert result["resolved"] is False
    assert result["indeterminate"] is True
    assert result["reason"] == "batch-declaration-after-reservations"


def test_count_resolves_when_declaration_physically_precedes(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    batch = "b-physical-order"
    _declare(repo, batch, 1)
    reserved = _reserved("l1", batch, ["a"], repo)
    reserved["ts"] = 1.0
    ll.reserve(repo, reserved)
    ll.append(repo, _started("l1"))
    ll.record_outcome(repo, "l1", "handback", "done")
    result = ll.count(repo, batch)
    assert result["resolved"] is True


def test_record_outcome_refuses_while_the_recorded_child_lives(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    batch = "b-refuse-live"
    launch_id = "l-refuse-live"
    proc = subprocess.Popen(["sleep", "30"], start_new_session=True)
    try:
        _declare(repo, batch, 1)
        ll.reserve(repo, _reserved(launch_id, batch, ["a"], repo))
        started = _started(launch_id)
        started["pid"] = proc.pid
        assert ll.append(repo, started)
        count_before = len(ll.read(repo)["records"])
        result = ll.record_outcome(repo, launch_id, "handback", "done")
        assert result["ok"] is False
        assert result["reason"] == "terminal-child-live:%s" % proc.pid
        assert len(ll.read(repo)["records"]) == count_before
        os.kill(proc.pid, 0)
        ll._reap_process(proc)
        proc.wait(timeout=5)
        result2 = ll.record_outcome(repo, launch_id, "handback", "done")
        assert result2["ok"] is True
    finally:
        try:
            os.kill(proc.pid, 9)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            pass


def test_record_outcome_never_signals_the_recorded_child(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    batch = "b-no-signal"
    launch_id = "l-no-signal"
    proc = subprocess.Popen(["sleep", "30"], start_new_session=True)
    signals_sent = []
    real_kill = os.kill
    real_killpg = os.killpg

    def recording_killpg(pgid, sig):
        if sig != 0:
            signals_sent.append(("killpg", pgid, sig))
            raise AssertionError("non-zero signal sent to process group")
        return real_killpg(pgid, sig)

    def recording_kill(pid, sig):
        if sig != 0:
            signals_sent.append(("kill", pid, sig))
            raise AssertionError("non-zero signal sent to process")
        return real_kill(pid, sig)

    monkeypatch.setattr(ll.os, "killpg", recording_killpg)
    monkeypatch.setattr(ll.os, "kill", recording_kill)
    try:
        _declare(repo, batch, 1)
        ll.reserve(repo, _reserved(launch_id, batch, ["a"], repo))
        started = _started(launch_id)
        started["pid"] = proc.pid
        assert ll.append(repo, started)
        result = ll.record_outcome(repo, launch_id, "handback", "done")
        assert result["ok"] is False
        assert result["reason"] == "terminal-child-live:%s" % proc.pid
        assert signals_sent == []
        real_kill(proc.pid, 0)
    finally:
        try:
            real_kill(proc.pid, 9)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            pass


def test_terminalize_refuses_when_a_group_descendant_survives(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    launch_id = "l-descendant"
    batch = "b-descendant"
    # Leader exits while a descendant in the same session keeps the group alive.
    proc = subprocess.Popen(
        [
            "bash", "-c",
            "trap '' TERM; (while true; do sleep 1; done) & exit 0",
        ],
        start_new_session=True,
    )
    try:
        proc.wait(timeout=5)
        _declare(repo, batch, 1)
        ll.reserve(repo, _reserved(launch_id, batch, ["a"], repo))
        started = _started(launch_id)
        started["pid"] = proc.pid
        assert ll.append(repo, started)
        count_before = len(ll.read(repo)["records"])
        result = ll.terminalize(
            repo, launch_id, outcome="handback", evidence="done", require_started=True,
        )
        assert result["ok"] is False
        assert result["reason"] == "terminal-child-live:%s" % proc.pid
        assert len(ll.read(repo)["records"]) == count_before
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass


def test_terminalize_refuses_when_the_supplied_proc_does_not_match_the_record(
    tmp_path, monkeypatch,
):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    launch_id = "l-mismatch"
    batch = "b-mismatch"
    live_proc = subprocess.Popen(["sleep", "30"], start_new_session=True)
    try:
        _declare(repo, batch, 1)
        ll.reserve(repo, _reserved(launch_id, batch, ["a"], repo))
        started = _started(launch_id)
        started["pid"] = live_proc.pid
        assert ll.append(repo, started)

        class _DeadOtherProc:
            pid = 424241

            def poll(self):
                return 0

            def terminate(self):
                pass

            def kill(self):
                pass

            def wait(self, timeout=None):
                pass

        count_before = len(ll.read(repo)["records"])
        result = ll.terminalize(
            repo, launch_id, outcome="handback", evidence="done",
            require_started=True, proc=_DeadOtherProc(),
        )
        assert result["ok"] is False
        assert result["reason"] == "terminal-child-live:%s" % live_proc.pid
        assert len(ll.read(repo)["records"]) == count_before
        os.kill(live_proc.pid, 0)
    finally:
        try:
            os.kill(live_proc.pid, 9)
        except ProcessLookupError:
            pass
        try:
            live_proc.wait(timeout=5)
        except Exception:
            pass


def test_fold_refuses_a_nonpositive_started_pid(tmp_path):
    records = [_reserved("a", "b", ["x"], "/tmp")]
    bad_zero = _started("a")
    bad_zero["pid"] = 0
    records.append(bad_zero)
    result = ll.fold(records)
    assert result["ok"] is False
    assert result["reason"] == "fold-bad-field:started:pid"

    records_neg = [_reserved("a", "b", ["x"], "/tmp")]
    bad_neg = _started("a")
    bad_neg["pid"] = -1
    records_neg.append(bad_neg)
    result_neg = ll.fold(records_neg)
    assert result_neg["ok"] is False
    assert result_neg["reason"] == "fold-bad-field:started:pid"


def test_append_returns_false_on_unserializable_record(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    assert ll.append(repo, {"event": object()}) is False


def test_fold_tolerates_child_identity_on_older_started_records(tmp_path):
    records = [_reserved("a", "b", ["x"], "/tmp")]
    started = _started("a")
    started["childIdentity"] = {"bootId": "old", "start": "Jan  1 00:00:00 2020", "comm": "sleep"}
    records.append(started)
    result = ll.fold(records)
    assert result["ok"] is True
    assert "childIdentity" not in result["launches"]["a"]


def test_reserve_refuses_a_duplicate_launch_id(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    launch_id = "dup-id"
    r1 = ll.reserve(repo, _reserved(launch_id, "b1", ["a"], repo))
    assert r1["ok"] is True
    count_after_first = len(ll.read(repo)["records"])
    r2 = ll.reserve(repo, _reserved(launch_id, "b2", ["z"], repo))
    assert r2["ok"] is False
    assert r2["reason"] == "reserve-duplicate-launch-id:%s" % launch_id
    assert len(ll.read(repo)["records"]) == count_after_first
    folded = ll.fold(ll.read(repo)["records"])
    assert folded["ok"] is True

    repo2 = _init_repo(tmp_path / "repo2")
    _ledger_env(tmp_path, monkeypatch)
    launch_id2 = "dup-terminal"
    assert ll.reserve(repo2, _reserved(launch_id2, "b1", ["a"], repo2))["ok"]
    ll.append(repo2, _started(launch_id2))
    assert ll.record_outcome(repo2, launch_id2, "handback", "done")["ok"]
    count_terminal = len(ll.read(repo2)["records"])
    r3 = ll.reserve(repo2, _reserved(launch_id2, "b2", ["z"], repo2))
    assert r3["ok"] is False
    assert r3["reason"] == "reserve-duplicate-launch-id:%s" % launch_id2
    assert len(ll.read(repo2)["records"]) == count_terminal
    assert ll.fold(ll.read(repo2)["records"])["ok"] is True


def test_reserve_refuses_non_dict_record(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    for bad in (None, [], "str"):
        result = ll.reserve(repo, bad)
        assert result["ok"] is False
        assert result["reason"] == "fold-not-an-object"
        assert result["path"] is None


def test_reserve_duplicate_live_launch_identical_surfaces(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    surfaces = ["plugins/superheroes/lib"]
    launch_id = "live-dup"
    assert ll.reserve(repo, _reserved(launch_id, "b1", surfaces, repo))["ok"]
    count_after_first = len(ll.read(repo)["records"])
    r2 = ll.reserve(repo, _reserved(launch_id, "b2", surfaces, repo))
    assert r2["ok"] is False
    assert r2["reason"] == "reserve-duplicate-launch-id:%s" % launch_id
    assert len(ll.read(repo)["records"]) == count_after_first


def test_append_under_lock_accepts_valid_started(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    launch_id = "started-ok"
    ll.reserve(repo, _reserved(launch_id, "b1", ["a"], repo))
    count_before = len(ll.read(repo)["records"])
    result = ll.append_under_lock(repo, _started(launch_id))
    assert result["ok"] is True
    assert len(ll.read(repo)["records"]) == count_before + 1
    assert ll.fold(ll.read(repo)["records"])["ok"] is True


def test_append_under_lock_refuses_bad_started_fields(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    launch_id = "bad-started"
    ll.reserve(repo, _reserved(launch_id, "b1", ["a"], repo))
    count_before = len(ll.read(repo)["records"])
    bad_pid = _started(launch_id)
    bad_pid["pid"] = 1
    result = ll.append_under_lock(repo, bad_pid)
    assert result["ok"] is False
    assert result["reason"] == "fold-bad-field:started:pid"
    assert len(ll.read(repo)["records"]) == count_before

    bad_attempt = _started(launch_id)
    bad_attempt["attempt"] = 0
    result2 = ll.append_under_lock(repo, bad_attempt)
    assert result2["ok"] is False
    assert result2["reason"] == "fold-bad-field:started:attempt"
    assert len(ll.read(repo)["records"]) == count_before


def test_append_under_lock_refuses_outcome_without_started(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    launch_id = "no-started"
    ll.reserve(repo, _reserved(launch_id, "b1", ["a"], repo))
    count_before = len(ll.read(repo)["records"])
    result = ll.append_under_lock(repo, _outcome(launch_id))
    assert result["ok"] is False
    assert result["reason"] == "append-terminal-must-use-terminalize"
    assert len(ll.read(repo)["records"]) == count_before


def test_append_under_lock_refuses_non_dict(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    result = ll.append_under_lock(repo, None)
    assert result["ok"] is False
    assert result["reason"] == "fold-not-an-object"


def test_append_under_lock_refuses_unknown_launch(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    count_before = len(ll.read(repo)["records"])
    result = ll.append_under_lock(repo, _started("orphan"))
    assert result["ok"] is False
    assert result["reason"] == "fold-orphan-event:orphan"
    assert len(ll.read(repo)["records"]) == count_before


def test_append_under_lock_refuses_torn_ledger(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    launch_id = "torn-a"
    ll.reserve(repo, _reserved(launch_id, "b1", ["x"], repo))
    path = _ledger_file(repo, os.environ)
    with open(path, "rb") as fh:
        raw = fh.read()
    with open(path, "wb") as fh:
        fh.write(raw.rstrip(b"\n"))
    torn_read = ll.read(repo)
    assert torn_read["state"] == "tornTail"
    count_before = len(torn_read["records"])
    result = ll.append_under_lock(repo, _started(launch_id))
    assert result["ok"] is False
    assert result["reason"] == "ledger-unreadable:tornTail"
    assert len(ll.read(repo)["records"]) == count_before


def test_append_under_lock_accepts_missing_ledger(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    assert ll.read(repo)["state"] == "missing"
    count_before = len(ll.read(repo)["records"])
    result = ll.append_under_lock(repo, _batch_declared("b-fresh", 1))
    assert result["ok"] is True
    assert len(ll.read(repo)["records"]) == count_before + 1
    assert ll.read(repo)["state"] == "ok"


def test_terminalize_refuses_when_the_reader_would_reject_its_own_record(
    tmp_path, monkeypatch,
):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    launch_id = "l-fold-reject"
    batch = "b-fold-reject"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved(launch_id, batch, ["a"], repo))
    ll.append(repo, _started(launch_id))
    count_before = len(ll.read(repo)["records"])

    original_fold = ll.fold
    baseline_len = count_before

    def rejecting_fold(records):
        if len(records) > baseline_len:
            return {
                "ok": False,
                "reason": "fold-reject-extension",
                "launches": {},
                "batchDeclarations": {},
            }
        return original_fold(records)

    monkeypatch.setattr(ll, "fold", rejecting_fold)
    result = ll.terminalize(
        repo, launch_id, outcome="handback", evidence="done", require_started=True,
    )
    assert result["ok"] is False
    assert result["reason"] == "fold-reject-extension"
    assert len(ll.read(repo)["records"]) == count_before


def test_declare_batch_refuses_when_the_reader_would_reject_its_own_record(
    tmp_path, monkeypatch,
):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    count_before = len(ll.read(repo)["records"])
    assert ll.read(repo)["state"] == "missing"

    original_fold = ll.fold
    baseline_len = count_before

    def rejecting_fold(records):
        if len(records) > baseline_len:
            return {
                "ok": False,
                "reason": "fold-reject-extension",
                "launches": {},
                "batchDeclarations": {},
            }
        return original_fold(records)

    monkeypatch.setattr(ll, "fold", rejecting_fold)
    result = ll.declare_batch(repo, "b-new", 1)
    assert result["ok"] is False
    assert result["reason"] == "fold-reject-extension"
    assert len(ll.read(repo)["records"]) == count_before


def test_append_under_lock_refuses_a_terminal_record(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    batch = "b-terminal-guard"
    launch_id = "l-terminal-guard"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved(launch_id, batch, ["a"], repo))
    ll.append(repo, _started(launch_id))
    count_before = len(ll.read(repo)["records"])

    result_outcome = ll.append_under_lock(repo, _outcome(launch_id))
    assert result_outcome["ok"] is False
    assert result_outcome["reason"] == "append-terminal-must-use-terminalize"

    result_refused = ll.append_under_lock(repo, _refused(launch_id))
    assert result_refused["ok"] is False
    assert result_refused["reason"] == "append-terminal-must-use-terminalize"

    assert len(ll.read(repo)["records"]) == count_before
    count_result = ll.count(repo, batch)
    assert count_result["indeterminate"] is True
    assert count_result["resolved"] is False


def test_append_under_lock_cannot_resolve_a_live_child(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    batch = "b-live-guard"
    launch_id = "l-live-guard"
    proc = subprocess.Popen(["sleep", "30"], start_new_session=True)
    try:
        _declare(repo, batch, 1)
        ll.reserve(repo, _reserved(launch_id, batch, ["a"], repo))
        started = _started(launch_id)
        started["pid"] = proc.pid
        ll.append(repo, started)

        result = ll.append_under_lock(repo, _outcome(launch_id))
        assert result["ok"] is False
        assert result["reason"] == "append-terminal-must-use-terminalize"

        count_result = ll.count(repo, batch)
        assert count_result["indeterminate"] is True
        assert count_result["resolved"] is False

        os.kill(proc.pid, 0)
    finally:
        try:
            os.kill(proc.pid, 9)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            pass


def test_reserve_refuses_a_record_the_reader_would_reject(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    bad = _reserved("bad", "b1", ["a"], repo)
    del bad["batchId"]
    count_before = len(ll.read(repo)["records"])
    result = ll.reserve(repo, bad)
    assert result["ok"] is False
    assert result["reason"] == "fold-missing-field:reserved:batchId"
    assert len(ll.read(repo)["records"]) == count_before


def test_terminalize_refuses_pid_one(tmp_path):
    records = [_reserved("a", "b", ["x"], "/tmp")]
    bad = _started("a")
    bad["pid"] = 1
    records.append(bad)
    result = ll.fold(records)
    assert result["ok"] is False
    assert result["reason"] == "fold-bad-field:started:pid"
    assert ll._child_group_is_live(1) is True


def test_terminalize_repair_refuses_a_live_group(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    launch_id = "l-repair-live"
    proc = subprocess.Popen(["sleep", "30"], start_new_session=True)
    try:
        ll.reserve(repo, _reserved(launch_id, "b-repair", ["a"], repo))
        count_before = len(ll.read(repo)["records"])
        result = ll.terminalize(
            repo,
            launch_id,
            child_ever_spawned=True,
            outcome="park",
            evidence="test",
            started_repair={
                "attempt": 1,
                "pid": proc.pid,
                "logPath": "/tmp/log",
                "errPath": "/tmp/err",
            },
        )
        assert result["ok"] is False
        assert result["reason"] == "terminal-child-live:%s" % proc.pid
        assert len(ll.read(repo)["records"]) == count_before
        os.kill(proc.pid, 0)
    finally:
        try:
            os.kill(proc.pid, 9)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            pass


def test_record_outcome_succeeds_when_recorded_child_is_gone(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    batch = "b-gone"
    launch_id = "l-gone"
    proc = subprocess.Popen(["sleep", "1"], start_new_session=True)
    proc.wait(timeout=5)
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved(launch_id, batch, ["a"], repo))
    started = _started(launch_id)
    started["pid"] = proc.pid
    assert ll.append(repo, started)
    result = ll.record_outcome(repo, launch_id, "handback", "done")
    assert result["ok"] is True
    records = ll.read(repo)["records"]
    assert any(r.get("event") == "outcome" for r in records)


def test_terminalize_refuses_self_pid(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    launch_id = "l-self"
    ll.reserve(repo, _reserved(launch_id, "b-self", ["a"], repo))
    started = _started(launch_id)
    started["pid"] = os.getpid()
    assert ll.append(repo, started)
    count_before = len(ll.read(repo)["records"])
    result = ll.terminalize(
        repo, launch_id, outcome="handback", evidence="done", require_started=True,
    )
    assert result["ok"] is False
    assert result["reason"].startswith("terminal-child-live:")
    assert len(ll.read(repo)["records"]) == count_before


def test_terminalize_repair_unavailable_writes_nothing(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    launch_id = "l-repair"
    ll.reserve(repo, _reserved(launch_id, "b-repair", ["a"], repo))
    count_before = len(ll.read(repo)["records"])
    result = ll.terminalize(repo, launch_id, child_ever_spawned=True)
    assert result["ok"] is False
    assert result["reason"] == "terminal-repair-unavailable"
    assert len(ll.read(repo)["records"]) == count_before


def test_terminalize_reaps_supplied_proc_when_the_ledger_is_unusable(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    launch_id = "l-orphan"
    ll.reserve(repo, _reserved(launch_id, "b-orphan", ["a"], repo))
    proc = subprocess.Popen(["sleep", "30"], start_new_session=True)
    try:
        monkeypatch.setattr(ll, "_acquire_lock", lambda lock_path, timeout: False)
        result = ll.terminalize(
            repo, launch_id, child_ever_spawned=False, reason="test", proc=proc,
        )
        assert result["ok"] is False
        with pytest.raises(ProcessLookupError):
            os.kill(proc.pid, 0)
    finally:
        try:
            proc.wait(timeout=5)
        except Exception:
            pass


def test_fold_refuses_non_increasing_started_attempt(tmp_path):
    records = [_reserved("a", "b", ["x"], "/tmp"), _started("a", attempt=1)]
    records.append(_started("a", attempt=1))
    result = ll.fold(records)
    assert result["ok"] is False
    assert result["reason"] == "fold-started-attempt-not-increasing:a"

    records_ok = [_reserved("a", "b", ["x"], "/tmp"), _started("a", attempt=1)]
    second = _started("a", attempt=2)
    second["pid"] = 424242
    records_ok.append(second)
    result_ok = ll.fold(records_ok)
    assert result_ok["ok"] is True
    assert result_ok["launches"]["a"]["pid"] == 424242


def test_terminalize_refuses_when_supplied_proc_survives_reaping(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    launch_id = "l-survive"
    ll.reserve(repo, _reserved(launch_id, "b-survive", ["a"], repo))

    class _SurvivingProc:
        pid = 424242

        def poll(self):
            return None

        def terminate(self):
            pass

        def kill(self):
            pass

        def wait(self, timeout=None):
            pass

    reap_calls = []
    monkeypatch.setattr(ll, "_reap_process", lambda proc: reap_calls.append(proc))

    count_before = len(ll.read(repo)["records"])
    result = ll.terminalize(
        repo, launch_id, child_ever_spawned=False, reason="test", proc=_SurvivingProc(),
    )
    assert result["ok"] is False
    assert result["reason"] == "terminal-child-live:424242"
    assert len(ll.read(repo)["records"]) == count_before
    assert len(reap_calls) == 1
    assert reap_calls[0] is not None


def test_record_outcome_maps_invalid_launch_id(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    result = ll.record_outcome(repo, "", "handback", "evidence")
    assert result["ok"] is False
    assert result["reason"] == "outcome-unknown-launch"


def test_record_outcome_still_refuses_without_started(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    result = ll.record_outcome(repo, "l1", "handback", "evidence")
    assert result["ok"] is False
    assert result["reason"] == "outcome-without-started"
    result2 = ll.record_outcome(repo, "missing", "handback", "evidence")
    assert result2["ok"] is False
    assert result2["reason"] == "outcome-unknown-launch"


# --- WO-656-K1 runtime guarantees --------------------------------------------


def test_child_group_is_live_detects_a_non_leader_pid(tmp_path, monkeypatch):
    proc = subprocess.Popen(["sleep", "30"])
    try:
        assert os.getpgid(proc.pid) != proc.pid
        assert ll._child_group_is_live(proc.pid) is True

        repo = _init_repo(tmp_path / "repo")
        _ledger_env(tmp_path, monkeypatch)
        batch = "b-non-leader"
        launch_id = "l-non-leader"
        _declare(repo, batch, 1)
        ll.reserve(repo, _reserved(launch_id, batch, ["a"], repo))
        started = _started(launch_id)
        started["pid"] = proc.pid
        assert ll.append(repo, started)
        count_before = len(ll.read(repo)["records"])
        result = ll.record_outcome(repo, launch_id, "handback", "done")
        assert result["ok"] is False
        assert result["reason"] == "terminal-child-live:%s" % proc.pid
        assert len(ll.read(repo)["records"]) == count_before
        os.kill(proc.pid, 0)
    finally:
        try:
            os.kill(proc.pid, 9)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            pass


def test_public_append_refuses_terminal_records(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    ll.append(repo, _started("l1"))
    count_before = len(ll.read(repo)["records"])

    assert ll.append(repo, _outcome("l1")) is False
    assert ll.append(repo, _refused("l1")) is False
    assert len(ll.read(repo)["records"]) == count_before

    assert ll.append(repo, _started("l1", attempt=2, pid=424242)) is True
    assert len(ll.read(repo)["records"]) == count_before + 1


def test_fold_records_every_started_pid(tmp_path):
    records = [_reserved("a", "b", ["x"], "/tmp")]
    records.append(_started("a", attempt=1, pid=424241))
    records.append(_started("a", attempt=2, pid=424242))
    result = ll.fold(records)
    assert result["ok"] is True
    info = result["launches"]["a"]
    assert info["pid"] == 424242
    assert info["pids"] == [424241, 424242]


def test_terminalize_probes_every_started_attempt(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    batch = "b-multi-started"
    launch_id = "l-multi-started"
    live_proc = subprocess.Popen(["sleep", "30"], start_new_session=True)
    dead_proc = subprocess.Popen(["sleep", "0.1"], start_new_session=True)
    dead_proc.wait(timeout=5)
    try:
        _declare(repo, batch, 1)
        ll.reserve(repo, _reserved(launch_id, batch, ["a"], repo))
        started1 = _started(launch_id, attempt=1)
        started1["pid"] = live_proc.pid
        assert ll.append(repo, started1)
        started2 = _started(launch_id, attempt=2)
        started2["pid"] = dead_proc.pid
        assert ll.append(repo, started2)
        count_before = len(ll.read(repo)["records"])
        result = ll.record_outcome(repo, launch_id, "handback", "done")
        assert result["ok"] is False
        assert result["reason"] == "terminal-child-live:%s" % live_proc.pid
        assert len(ll.read(repo)["records"]) == count_before
        os.kill(live_proc.pid, 0)
        ll._reap_process(live_proc)
        live_proc.wait(timeout=5)
        result2 = ll.record_outcome(repo, launch_id, "handback", "done")
        assert result2["ok"] is True
    finally:
        try:
            os.kill(live_proc.pid, 9)
        except ProcessLookupError:
            pass
        try:
            live_proc.wait(timeout=5)
        except Exception:
            pass


def _amendment(launch_id, kind, value, note):
    return {
        "event": "amendment",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "kind": kind,
        "value": value,
        "note": note,
    }


# --- WO-864 post-terminal accounting -----------------------------------------


def test_rehandback_end_to_end(tmp_path, monkeypatch):
    # axis: genuine re-handback cycle surfaces in count
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "wave-rehandback"
    launch = "launch-rehandback"
    assert _declare(repo, batch, 1)["ok"]
    assert ll.reserve(repo, _reserved(launch, batch, ["a"], repo))["ok"]
    _append_raw(_ledger_file(repo, os.environ), _started(launch))
    first = ll.record_outcome(repo, launch, "handback", "first")
    assert first == {
        "ok": True,
        "reason": None,
        "recorded": "outcome",
        "amendmentKind": None,
        "attemptedOutcome": "handback",
        "terminalOutcome": "handback",
    }
    second = ll.record_outcome(repo, launch, "handback", "second")
    assert second["ok"] is True
    assert second["recorded"] == "amendment"
    result = ll.count(repo, batch)
    assert result["resolved"] is True
    assert result["counts"]["handback"] == 1
    assert result["amendments"]["reoutcome"] == 1
    assert result["amendments"]["rehandback"] == 1
    assert result["amendedLaunches"] == 1


def test_second_write_on_park_counts_reoutcome_not_rehandback(tmp_path, monkeypatch):
    # axis: rehandback is handback-over-handback only
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "wave-park-reoutcome"
    launch = "launch-park"
    assert _declare(repo, batch, 1)["ok"]
    ll.reserve(repo, _reserved(launch, batch, ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started(launch))
    ll.record_outcome(repo, launch, "park", "blocked")
    ll.record_outcome(repo, launch, "handback", "retry")
    result = ll.count(repo, batch)
    assert result["amendments"]["reoutcome"] == 1
    assert result["amendments"]["rehandback"] == 0


@pytest.mark.parametrize("ruling", list(ll.VET_RULINGS))
def test_vet_amendment_each_ruling(tmp_path, monkeypatch, ruling):
    # axis: vet amendments tally per ruling
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "wave-vet-%s" % ruling
    launch = "launch-vet"
    assert _declare(repo, batch, 1)["ok"]
    ll.reserve(repo, _reserved(launch, batch, ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started(launch))
    ll.record_outcome(repo, launch, "handback", "done")
    result = ll.amend(repo, launch, "vet", ruling, "advisor reason")
    assert result["ok"] is True
    counted = ll.count(repo, batch)
    key = "vet" + "".join(part.capitalize() for part in ruling.split("-"))
    assert counted["amendments"][key] == 1
    assert counted["amendments"]["total"] == 1


def test_evidence_amendment(tmp_path, monkeypatch):
    # axis: evidence amendments tally
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "wave-evidence"
    launch = "launch-evidence"
    assert _declare(repo, batch, 1)["ok"]
    ll.reserve(repo, _reserved(launch, batch, ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started(launch))
    ll.record_outcome(repo, launch, "handback", "original")
    assert ll.amend(repo, launch, "evidence", "corrected", "typo")["ok"]
    result = ll.count(repo, batch)
    assert result["amendments"]["evidence"] == 1
    assert result["amendedLaunches"] == 1


def test_amend_unknown_launch(tmp_path, monkeypatch):
    # axis: amend-unknown-launch
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    result = ll.amend(repo, "missing", "vet", "ready", "reason")
    assert result["ok"] is False
    assert result["reason"] == "amend-unknown-launch"


def test_amend_not_terminal(tmp_path, monkeypatch):
    # axis: amend-not-terminal
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    result = ll.amend(repo, "l1", "vet", "ready", "reason")
    assert result["ok"] is False
    assert result["reason"] == "amend-not-terminal"


@pytest.mark.parametrize("kind", ["bogus", 42])
def test_amend_kind_invalid(tmp_path, monkeypatch, kind):
    # axis: amend-kind-invalid
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
    result = ll.amend(repo, "l1", kind, "ready", "reason")
    assert result["ok"] is False
    assert result["reason"] == "amend-kind-invalid:%s" % kind


def test_amend_value_invalid_for_vet(tmp_path, monkeypatch):
    # axis: amend-value-invalid
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
    result = ll.amend(repo, "l1", "vet", "bogus", "reason")
    assert result["ok"] is False
    assert result["reason"] == "amend-value-invalid:bogus"


def test_amend_value_empty(tmp_path, monkeypatch):
    # axis: amend-value-empty
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
    result = ll.amend(repo, "l1", "vet", "", "reason")
    assert result["ok"] is False
    assert result["reason"] == "amend-value-empty"


def test_amend_note_empty(tmp_path, monkeypatch):
    # axis: amend-note-empty
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
    result = ll.amend(repo, "l1", "vet", "ready", "")
    assert result["ok"] is False
    assert result["reason"] == "amend-note-empty"


def test_amend_ledger_unreadable_torn_tail(tmp_path, monkeypatch):
    # axis: ledger-unreadable on torn tail
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
    path = _ledger_file(repo, os.environ)
    with open(path, "rb") as fh:
        raw = fh.read()
    with open(path, "wb") as fh:
        fh.write(raw.rstrip(b"\n"))
    result = ll.amend(repo, "l1", "vet", "ready", "reason")
    assert result["ok"] is False
    assert result["reason"] == "ledger-unreadable:tornTail"


def test_amend_lock_unavailable(tmp_path, monkeypatch):
    # axis: lock-unavailable
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
    lock_result = ll._ensure_lock_file(repo)
    import file_lock
    file_lock.acquire(lock_result["path"])
    os.chmod(lock_result["path"], 0o600)
    try:
        result = ll.amend(repo, "l1", "vet", "ready", "reason", lock_timeout=0.1)
        assert result["ok"] is False
        assert result["reason"] == "lock-unavailable"
    finally:
        file_lock.release(lock_result["path"])


def test_amend_ledger_append_failed(tmp_path, monkeypatch):
    # axis: ledger-append-failed
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
    monkeypatch.setattr(ll, "append", lambda *a, **k: False)
    result = ll.amend(repo, "l1", "vet", "ready", "reason")
    assert result["ok"] is False
    assert result["reason"] == "ledger-append-failed"


def test_amend_fold_refusal_propagated(tmp_path, monkeypatch):
    # axis: fold reason propagated unchanged
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
    original_fold = ll.fold

    def rejecting_fold(records):
        if any(r.get("event") == "amendment" for r in records):
            return {"ok": False, "reason": "fold-reject-amendment",
                    "launches": {}, "batchDeclarations": {}}
        return original_fold(records)

    monkeypatch.setattr(ll, "fold", rejecting_fold)
    result = ll.amend(repo, "l1", "vet", "ready", "reason")
    assert result["ok"] is False
    assert result["reason"] == "fold-reject-amendment"


def test_record_outcome_amend_failed(tmp_path, monkeypatch):
    # axis: amend-failed on second record_outcome
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
    monkeypatch.setattr(ll, "amend", lambda *a, **k: {"ok": False, "reason": "lock-unavailable"})
    result = ll.record_outcome(repo, "l1", "handback", "again")
    assert result["ok"] is False
    assert result["reason"] == "amend-failed:lock-unavailable"
    assert result["recorded"] is None


def test_record_outcome_invalid_on_terminal_stays_plain_refusal(tmp_path, monkeypatch):
    # axis: garbage on terminal lane never becomes amendment
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
    result = ll.record_outcome(repo, "l1", "bogus", "evidence")
    assert result["ok"] is False
    assert result["reason"] == "outcome-invalid:bogus"
    assert result["recorded"] is None
    result2 = ll.record_outcome(repo, "l1", "handback", "   ")
    assert result2["ok"] is False
    assert result2["reason"] == "outcome-evidence-empty"
    assert result2["recorded"] is None


def test_fold_amendment_before_terminal(tmp_path):
    # axis: fold-amendment-before-terminal
    records = [_reserved("a", "b", ["x"], "/tmp"), _started("a")]
    records.append(_amendment("a", "vet", "ready", "too early"))
    result = ll.fold(records)
    assert result["ok"] is False
    assert result["reason"] == "fold-amendment-before-terminal:a"


def test_fold_amendment_orphan(tmp_path):
    # axis: fold-orphan-event for amendment on unknown launch
    result = ll.fold([_amendment("orphan", "vet", "ready", "reason")])
    assert result["ok"] is False
    assert result["reason"] == "fold-orphan-event:orphan"


def test_fold_second_outcome_still_conflicting_terminal(tmp_path):
    # axis: fold-conflicting-terminal preserved
    records = [_reserved("a", "b", ["x"], "/tmp"), _started("a"), _outcome("a")]
    records.append(_outcome("a"))
    result = ll.fold(records)
    assert result["ok"] is False
    assert result["reason"] == "fold-conflicting-terminal:a"


def test_append_accepts_amendment(tmp_path, monkeypatch):
    # axis: append accepts amendment records
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
    count_before = len(ll.read(repo)["records"])
    assert ll.append(repo, _amendment("l1", "vet", "ready", "reason"))
    assert len(ll.read(repo)["records"]) == count_before + 1


def test_append_under_lock_accepts_amendment(tmp_path, monkeypatch):
    # axis: append_under_lock accepts amendment on terminal lane
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
    count_before = len(ll.read(repo)["records"])
    result = ll.append_under_lock(repo, _amendment("l1", "vet", "ready", "reason"))
    assert result["ok"] is True
    assert len(ll.read(repo)["records"]) == count_before + 1


def test_count_indeterminate_includes_zero_amendments(tmp_path, monkeypatch):
    # axis: indeterminate count still carries zeroed amendments
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    result = ll.count(repo, "missing-batch")
    assert result["indeterminate"] is True
    assert result["amendments"] == ll._zero_amendments()
    assert result["amendedLaunches"] == 0
    assert result["lanes"] == {"declared": 0, "resolved": 0}
    assert result["attempts"] == {
        "total": 0, "extra": 0, "outcomes": ll._zero_attempt_outcomes(),
    }
    assert result["laneDetail"] == []


def test_lane_sequential_retries_same_issue_resolve(tmp_path, monkeypatch):
    # axis: sequential same-issue rows fold as one lane with attempts
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-retry-lane"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo, issue=501))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1", outcome="park"))
    ll.reserve(repo, _reserved("l2", batch, ["a"], repo, issue=501))
    _append_raw(_ledger_file(repo, os.environ), _started("l2"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l2", outcome="handback"))
    result = ll.count(repo, batch)
    assert result["resolved"] is True
    assert result["counts"]["total"] == 1
    assert result["counts"]["handback"] == 1
    assert result["attempts"]["total"] == 2
    assert result["attempts"]["extra"] == 1
    assert result["attempts"]["outcomes"]["park"] == 1
    assert result["laneDetail"] == [{
        "issue": 501,
        "attempts": 2,
        "outcome": "handback",
        "terminalKind": "outcome",
        "attemptOutcomes": ["park", "handback"],
    }]


def test_lane_concurrent_same_issue_refuses(tmp_path, monkeypatch):
    # axis: overlapping same-lane launches refuse before unresolved
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-concurrent"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo, issue=601))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    ll.reserve(repo, _reserved("l2", batch, ["b"], repo, issue=601))
    result = ll.count(repo, batch)
    assert result["indeterminate"] is True
    assert result["reason"] == "batch-lane-concurrent:601"


def test_lane_concurrent_same_issue_interleaved_refuses(tmp_path, monkeypatch):
    # axis: the comparison leg of the lane-sequencing guard (earlier_terminal >= later reservedIndex)
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-interleaved"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo, issue=602))
    ll.reserve(repo, _reserved("l2", batch, ["b"], repo, issue=602))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1", outcome="park"))
    _append_raw(_ledger_file(repo, os.environ), _started("l2"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l2", outcome="handback"))
    result = ll.count(repo, batch)
    assert result["indeterminate"] is True
    assert result["reason"] == "batch-lane-concurrent:602"


def test_lane_sequential_same_issue_tightest_boundary_resolves(tmp_path, monkeypatch):
    # axis: strictly sequential rows at the >= boundary resolve as one lane
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-seq-boundary"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo, issue=603))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1", outcome="park"))
    ll.reserve(repo, _reserved("l2", batch, ["a"], repo, issue=603))
    _append_raw(_ledger_file(repo, os.environ), _started("l2"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l2", outcome="handback"))
    folded = ll.fold(ll.read(repo)["records"])
    l1 = folded["launches"]["l1"]
    l2 = folded["launches"]["l2"]
    assert l1["terminalIndex"] == l2["reservedIndex"] - 1
    result = ll.count(repo, batch)
    assert result["resolved"] is True
    assert result["attempts"]["extra"] == 1
    assert result["counts"]["handback"] == 1
    assert result["attempts"]["outcomes"]["park"] == 1


def test_count_partitions_final_into_counts_not_attempt_outcomes(tmp_path, monkeypatch):
    # axis: each launch row lands in exactly one tally (counts vs attempts.outcomes)
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-partition"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo, issue=701))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1", outcome="died"))
    ll.reserve(repo, _reserved("l2", batch, ["a"], repo, issue=701))
    _append_raw(_ledger_file(repo, os.environ), _started("l2"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l2", outcome="handback"))
    result = ll.count(repo, batch)
    assert result["resolved"] is True
    counts = result["counts"]
    outcomes = result["attempts"]["outcomes"]
    assert counts["handback"] == 1
    assert outcomes["handback"] == 0
    assert outcomes["died"] == 1
    assert counts["died"] == 0
    counts_sum = sum(counts[k] for k in counts if k != "total")
    outcomes_sum = sum(outcomes.values())
    assert counts_sum + outcomes_sum == result["attempts"]["total"]


def test_lane_issue_invalid_zero_refuses(tmp_path, monkeypatch):
    # axis: issue 0 never becomes a lane
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-issue-zero"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo, issue=0))
    _append_raw(_ledger_file(repo, os.environ), _refused("l1"))
    result = ll.count(repo, batch)
    assert result["indeterminate"] is True
    assert result["reason"] == "batch-lane-issue-invalid:l1"


def test_lane_issue_invalid_string_refuses(tmp_path, monkeypatch):
    # axis: non-int issue never becomes a lane
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-issue-str"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo, issue="656"))
    _append_raw(_ledger_file(repo, os.environ), _refused("l1"))
    result = ll.count(repo, batch)
    assert result["indeterminate"] is True
    assert result["reason"] == "batch-lane-issue-invalid:l1"


def test_lane_issue_invalid_bool_refuses(tmp_path, monkeypatch):
    # axis: bool issue never becomes a lane (bool subclasses int)
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-issue-bool"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo, issue=True))
    _append_raw(_ledger_file(repo, os.environ), _refused("l1"))
    result = ll.count(repo, batch)
    assert result["indeterminate"] is True
    assert result["reason"] == "batch-lane-issue-invalid:l1"


def test_lane_declared_with_zero_rows_refuses(tmp_path, monkeypatch):
    # axis: fewer distinct lanes than declared is batch-reservation-mismatch
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-missing-lane"
    _declare(repo, batch, 2)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo, issue=701))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
    result = ll.count(repo, batch)
    assert result["indeterminate"] is True
    assert result["reason"] == "batch-reservation-mismatch"


def test_lane_final_refused_headline_with_earlier_attempts(tmp_path, monkeypatch):
    # axis: final refused attempt is headline; earlier outcomes in attempts only
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-final-refused"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo, issue=801))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1", outcome="park"))
    ll.reserve(repo, _reserved("l2", batch, ["a"], repo, issue=801))
    _append_raw(_ledger_file(repo, os.environ), _refused("l2"))
    result = ll.count(repo, batch)
    assert result["resolved"] is True
    assert result["counts"]["refusedToLaunch"] == 1
    assert result["counts"]["park"] == 0
    assert result["attempts"]["outcomes"]["park"] == 1


def test_lane_retry_event_between_attempts_no_effect(tmp_path, monkeypatch):
    # axis: retry between attempts does not affect sequencing or tallies
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-retry-event"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo, issue=901))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), {
        "event": "retry",
        "launchId": "l1",
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "attempt": 1,
        "reason": "spawn",
        "delaySeconds": 0,
    })
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1", outcome="park"))
    ll.reserve(repo, _reserved("l2", batch, ["b"], repo, issue=901))
    _append_raw(_ledger_file(repo, os.environ), _started("l2"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l2", outcome="handback"))
    result = ll.count(repo, batch)
    assert result["resolved"] is True
    assert result["counts"]["handback"] == 1
    assert result["attempts"]["outcomes"]["park"] == 1


def test_lane_late_declaration_wins_over_concurrency(tmp_path, monkeypatch):
    # axis: batch-declaration-after-reservations wins over concurrency guard
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-late-decl-concurrent"
    path = _ledger_file(repo, os.environ)
    reserved1 = _reserved("l1", batch, ["a"], repo, issue=1001)
    reserved1["ts"] = 100.0
    ll.reserve(repo, reserved1)
    _append_raw(path, _started("l1"))
    reserved2 = _reserved("l2", batch, ["a"], repo, issue=1001)
    reserved2["ts"] = 150.0
    ll.reserve(repo, reserved2)
    _append_raw(path, {
        "event": "batch-declared",
        "batchId": batch,
        "expectedLaunches": 1,
        "ts": 200.0,
        "schema": ll.SCHEMA,
    })
    result = ll.count(repo, batch)
    assert result["indeterminate"] is True
    assert result["reason"] == "batch-declaration-after-reservations"


def test_count_result_blocks_anchor_to_real_count_keys(tmp_path, monkeypatch):
    """§11 drift chain: COUNT_RESULT_BLOCKS and CHARTER_NAMED_COUNT_BLOCKS trace to count() keys."""
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-count-blocks"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo, issue=501))
    path = _ledger_file(repo, os.environ)
    _append_raw(path, _started("l1"))
    _append_raw(path, _outcome("l1", outcome="handback"))
    result = ll.count(repo, batch)
    assert result["resolved"] is True
    for block in ll.COUNT_RESULT_BLOCKS:
        assert block in result, (
            "COUNT_RESULT_BLOCKS name %r not a key of count() result" % block
        )
    for block in ll.CHARTER_NAMED_COUNT_BLOCKS:
        assert block in ll.COUNT_RESULT_BLOCKS, (
            "CHARTER_NAMED_COUNT_BLOCKS name %r not in COUNT_RESULT_BLOCKS" % block
        )


def test_lane_sequential_reversed_timestamps_still_resolves(tmp_path, monkeypatch):
    # axis: index-based sequencing ignores reversed wall-clock ts
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-seq-rev-ts"
    path = _ledger_file(repo, os.environ)
    _declare(repo, batch, 1)
    r1 = _reserved("l1", batch, ["a"], repo, issue=701)
    r1["ts"] = 300.0
    ll.reserve(repo, r1)
    s1 = _started("l1")
    s1["ts"] = 250.0
    _append_raw(path, s1)
    o1 = _outcome("l1", outcome="park")
    o1["ts"] = 200.0
    _append_raw(path, o1)
    r2 = _reserved("l2", batch, ["a"], repo, issue=701)
    r2["ts"] = 100.0
    ll.reserve(repo, r2)
    s2 = _started("l2")
    s2["ts"] = 50.0
    _append_raw(path, s2)
    o2 = _outcome("l2", outcome="handback")
    o2["ts"] = 10.0
    _append_raw(path, o2)
    result = ll.count(repo, batch)
    assert result["resolved"] is True


def test_lane_overlapping_sequential_timestamps_still_refuses_concurrent(tmp_path, monkeypatch):
    # axis: index-based concurrency guard ignores monotonic-looking ts
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-overlap-seq-ts"
    path = _ledger_file(repo, os.environ)
    _declare(repo, batch, 1)
    r1 = _reserved("l1", batch, ["a"], repo, issue=801)
    r1["ts"] = 100.0
    ll.reserve(repo, r1)
    r2 = _reserved("l2", batch, ["b"], repo, issue=801)
    r2["ts"] = 200.0
    ll.reserve(repo, r2)
    s1 = _started("l1")
    s1["ts"] = 300.0
    _append_raw(path, s1)
    o1 = _outcome("l1", outcome="park")
    o1["ts"] = 400.0
    _append_raw(path, o1)
    s2 = _started("l2")
    s2["ts"] = 500.0
    _append_raw(path, s2)
    o2 = _outcome("l2", outcome="handback")
    o2["ts"] = 600.0
    _append_raw(path, o2)
    result = ll.count(repo, batch)
    assert result["indeterminate"] is True
    assert result["reason"] == "batch-lane-concurrent:801"


def test_lane_sequential_nonfinite_timestamp_still_resolves(tmp_path, monkeypatch):
    # axis: non-finite ts on a sequential lane does not break index-based resolution
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-seq-nan-ts"
    path = _ledger_file(repo, os.environ)
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo, issue=901))
    _append_raw(path, _started("l1"))
    o1 = _outcome("l1", outcome="park")
    o1["ts"] = float("nan")
    _append_raw(path, o1)
    ll.reserve(repo, _reserved("l2", batch, ["a"], repo, issue=901))
    s2 = _started("l2")
    s2["ts"] = float("inf")
    _append_raw(path, s2)
    _append_raw(path, _outcome("l2", outcome="handback"))
    result = ll.count(repo, batch)
    assert result["resolved"] is True


def test_count_duplicate_declaration_beats_invalid_issue(tmp_path, monkeypatch):
    # axis: declaration validity beats lane-issue validity
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-dup-vs-invalid"
    _declare(repo, batch, 1)
    _append_raw(_ledger_file(repo, os.environ), _batch_declared(batch, 1))
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo, issue=True))
    result = ll.count(repo, batch)
    assert result["indeterminate"] is True
    assert result["reason"] == "batch-duplicate-declaration"


def test_count_invalid_issue_beats_reservation_mismatch(tmp_path, monkeypatch):
    # axis: lane-issue validity beats lane cardinality
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-invalid-vs-mismatch"
    _declare(repo, batch, 2)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo, issue=True))
    result = ll.count(repo, batch)
    assert result["indeterminate"] is True
    assert result["reason"] == "batch-lane-issue-invalid:l1"


def test_count_reservation_mismatch_beats_late_declaration(tmp_path, monkeypatch):
    # axis: lane cardinality beats late declaration
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-mismatch-vs-late"
    path = _ledger_file(repo, os.environ)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo, issue=1001))
    _append_raw(path, {
        "event": "batch-declared",
        "batchId": batch,
        "expectedLaunches": 2,
        "ts": 200.0,
        "schema": ll.SCHEMA,
    })
    result = ll.count(repo, batch)
    assert result["indeterminate"] is True
    assert result["reason"] == "batch-reservation-mismatch"


def test_count_concurrency_beats_unresolved(tmp_path, monkeypatch):
    # axis: lane concurrency beats batch-unresolved
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-concurrent-vs-unresolved"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo, issue=1101))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    ll.reserve(repo, _reserved("l2", batch, ["b"], repo, issue=1101))
    result = ll.count(repo, batch)
    assert result["indeterminate"] is True
    assert result["reason"] == "batch-lane-concurrent:1101"


@pytest.mark.parametrize("field", ["kind", "value", "note"])
def test_fold_amendment_missing_field(tmp_path, field):
    # axis: fold-missing-field:amendment
    rec = _amendment("a", "vet", "ready", "reason")
    del rec[field]
    records = [_reserved("a", "b", ["x"], "/tmp"), _started("a"), _outcome("a"), rec]
    result = ll.fold(records)
    assert result["ok"] is False
    assert result["reason"] == "fold-missing-field:amendment:%s" % field


def test_terminal_outcome_unchanged_after_amendment(tmp_path, monkeypatch):
    # axis: terminal record byte-unchanged after amendment; fold projection unchanged too
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    outcome_rec = _outcome("l1", evidence="original-evidence")
    _append_raw(_ledger_file(repo, os.environ), outcome_rec)
    path = _ledger_file(repo, os.environ)
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()
    outcome_line = [ln for ln in lines if '"event":"outcome"' in ln.replace(" ", "")][0]
    records_before = ll.read(repo)["records"]
    folded_before = ll.fold(records_before)
    info_before = folded_before["launches"]["l1"]
    ll.amend(repo, "l1", "vet", "not-ready", "advisor ruling")
    with open(path, encoding="utf-8") as fh:
        lines_after = fh.readlines()
    outcome_line_after = [ln for ln in lines_after if '"event":"outcome"' in ln.replace(" ", "")][0]
    assert outcome_line_after == outcome_line
    records_after = ll.read(repo)["records"]
    folded_after = ll.fold(records_after)
    info_after = folded_after["launches"]["l1"]
    assert info_after["terminal"] == info_before["terminal"]
    assert info_after["outcome"] == info_before["outcome"]
    assert info_after["terminalKind"] == info_before["terminalKind"]
    assert len(info_after["amendments"]) == len(info_before["amendments"]) + 1


# Bite-proof tests (guarded elements) -----------------------------------------


def test_bite_fold_amendment_before_terminal_guard(tmp_path):
    # Bite: fold-amendment-before-terminal guard
    records = [_reserved("a", "b", ["x"], "/tmp"), _started("a")]
    records.append(_amendment("a", "vet", "ready", "too early"))
    result = ll.fold(records)
    assert result["ok"] is False
    assert "fold-amendment-before-terminal" in result["reason"]


def test_bite_record_outcome_reoutcome_recording(tmp_path, monkeypatch):
    # Bite: second terminal write recorded as amendment
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
    result = ll.record_outcome(repo, "l1", "handback", "again")
    assert result["recorded"] == "amendment"


def test_bite_count_amendments_tally(tmp_path, monkeypatch):
    # Bite: amendments tally reaches count
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "bite-count"
    launch = "l-bite"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved(launch, batch, ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started(launch))
    ll.record_outcome(repo, launch, "handback", "done")
    ll.amend(repo, launch, "vet", "ready", "ok")
    result = ll.count(repo, batch)
    assert result["amendments"]["total"] == 1


def test_bite_rehandback_subset_derivation(tmp_path, monkeypatch):
    # Bite: rehandback subset is handback-over-handback
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "bite-rehandback"
    launch_handback = "l-reh-handback"
    launch_park = "l-reh-park"
    _declare(repo, batch, 2)
    ll.reserve(repo, _reserved(launch_handback, batch, ["a"], repo, issue=301))
    _append_raw(_ledger_file(repo, os.environ), _started(launch_handback))
    ll.record_outcome(repo, launch_handback, "handback", "first")
    ll.record_outcome(repo, launch_handback, "handback", "second")
    ll.reserve(repo, _reserved(launch_park, batch, ["b"], repo, issue=302))
    _append_raw(_ledger_file(repo, os.environ), _started(launch_park))
    ll.record_outcome(repo, launch_park, "park", "blocked")
    ll.record_outcome(repo, launch_park, "handback", "retry")
    result = ll.count(repo, batch)
    assert result["amendments"]["reoutcome"] == 2
    assert result["amendments"]["rehandback"] == 1
    assert result["amendedLaunches"] == 2


def test_record_outcome_on_refused_lane_no_amendment(tmp_path, monkeypatch):
    # axis: refused/never-started lane keeps outcome-without-started, no amendment
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _refused("l1"))
    count_before = len(ll.read(repo)["records"])
    result = ll.record_outcome(repo, "l1", "handback", "evidence")
    assert result["ok"] is False
    assert result["reason"] == "outcome-without-started"
    assert result["recorded"] is None
    assert len(ll.read(repo)["records"]) == count_before


def test_record_outcome_concurrent_identical_retry_dedupes_under_lock(tmp_path, monkeypatch):
    # axis: dedupe and append are one lock transaction; snapshots captured before barrier sync
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "wave-concurrent-dedupe"
    launch = "launch-concurrent-dedupe"
    evidence = "identical-evidence"
    assert _declare(repo, batch, 1)["ok"]
    ll.reserve(repo, _reserved(launch, batch, ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started(launch))
    ll.record_outcome(repo, launch, "handback", evidence)

    real_read = ll.read
    barrier = threading.Barrier(2, timeout=10)
    worker_tids = set()
    shim_state = threading.local()

    def _is_record_outcome_pre_amend_read():
        chain = [frame.function for frame in inspect.stack()[1:12]]
        return (
            "record_outcome" in chain
            and "amend" not in chain
            and "terminalize" not in chain
        )

    def read_shim(repo_root, env=None):
        tid = threading.get_ident()
        if tid not in worker_tids:
            return real_read(repo_root, env=env)
        if (
            _is_record_outcome_pre_amend_read()
            and not getattr(shim_state, "pre_amend_barrier_done", False)
        ):
            shim_state.pre_amend_barrier_done = True
            snapshot = real_read(repo_root, env=env)
            try:
                barrier.wait(timeout=10)
            except threading.BrokenBarrierError as exc:
                raise AssertionError(
                    "concurrent record_outcome dedupe: barrier broken or timed out"
                ) from exc
            return snapshot
        return real_read(repo_root, env=env)

    monkeypatch.setattr(ll, "read", read_shim)

    results = [None, None]
    errors = [None, None]

    def worker(idx):
        worker_tids.add(threading.get_ident())
        try:
            results[idx] = ll.record_outcome(repo, launch, "handback", evidence)
        except Exception as exc:
            errors[idx] = exc

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
        if thread.is_alive():
            pytest.fail(
                "concurrent record_outcome dedupe: thread timed out; "
                "results=%r errors=%r" % (results, errors)
            )

    assert errors == [None, None], errors
    assert results[0]["ok"] is True
    assert results[1]["ok"] is True
    recorded = {results[0]["recorded"], results[1]["recorded"]}
    assert recorded == {"amendment", "amendment-existing"}

    folded = ll.fold(ll.read(repo)["records"])
    amendments = folded["launches"][launch]["amendments"]
    reoutcome_amendments = [a for a in amendments if a["kind"] == "reoutcome"]
    assert len(reoutcome_amendments) == 1

    amendment_events = [
        r for r in ll.read(repo)["records"]
        if r.get("event") == "amendment" and r.get("launchId") == launch
    ]
    assert len(amendment_events) == 1

    counted = ll.count(repo, batch)
    assert counted["amendments"]["reoutcome"] == 1
    assert counted["amendments"]["rehandback"] == 1


def test_record_outcome_idempotent_retry(tmp_path, monkeypatch):
    # axis: byte-identical retry appends one amendment, not two
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "wave-idempotent"
    launch = "launch-idempotent"
    assert _declare(repo, batch, 1)["ok"]
    ll.reserve(repo, _reserved(launch, batch, ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started(launch))
    ll.record_outcome(repo, launch, "handback", "done")
    second = ll.record_outcome(repo, launch, "handback", "done")
    assert second["recorded"] == "amendment"
    third = ll.record_outcome(repo, launch, "handback", "done")
    assert third["recorded"] == "amendment-existing"
    counted = ll.count(repo, batch)
    assert counted["amendments"]["reoutcome"] == 1
    assert counted["amendments"]["rehandback"] == 1
    assert counted["amendedLaunches"] == 1


@pytest.mark.parametrize("kind,value,note,reason", [
    ("bogus", "ready", "n", "fold-bad-amendment-kind:a"),
    ("vet", 7, "n", "fold-missing-amendment-value:a"),
    ("vet", "", "n", "fold-missing-amendment-value:a"),
    ("vet", "ready", "", "fold-missing-amendment-note:a"),
    ("vet", "maybe", "n", "fold-bad-amendment-value:a"),
    ("reoutcome", "ready", "n", "fold-bad-amendment-value:a"),
])
def test_fold_amendment_field_values(kind, value, note, reason):
    # axis: fold refuses a malformed amendment record with the exact token, per field
    records = [_reserved("a", "b", ["x"], "/tmp"), _started("a"), _outcome("a"),
               _amendment("a", kind, value, note)]
    result = ll.fold(records)
    assert result["ok"] is False
    assert result["reason"] == reason


def test_amend_launch_id_invalid(tmp_path, monkeypatch):
    # axis: amend-launch-id-invalid
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    result = ll.amend(repo, "", "vet", "ready", "reason")
    assert result["ok"] is False
    assert result["reason"] == "amend-launch-id-invalid"


def test_amend_value_invalid_for_reoutcome(tmp_path, monkeypatch):
    # axis: amend-value-invalid on reoutcome leg
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
    result = ll.amend(repo, "l1", "reoutcome", "bogus", "reason")
    assert result["ok"] is False
    assert result["reason"] == "amend-value-invalid:bogus"


def test_amend_failed_exception(tmp_path, monkeypatch):
    # axis: amend-failed on unexpected exception inside lock
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))

    def boom(*args, **kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(ll, "read", boom)
    result = ll.amend(repo, "l1", "vet", "ready", "reason")
    assert result["ok"] is False
    assert result["reason"] == "amend-failed"


def test_record_outcome_amend_failed_no_double_prefix(tmp_path, monkeypatch):
    # axis: amend-failed is not double-prefixed in record_outcome
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
    monkeypatch.setattr(ll, "amend", lambda *a, **k: {"ok": False, "reason": "amend-failed",
                                                     "terminalOutcome": None})
    result = ll.record_outcome(repo, "l1", "handback", "again")
    assert result["ok"] is False
    assert result["reason"] == "amend-failed"
    assert result["recorded"] is None


_RECORD_OUTCOME_KEYS = frozenset({
    "ok", "reason", "recorded", "amendmentKind", "attemptedOutcome", "terminalOutcome",
})


@pytest.mark.parametrize("case", [
    "invalid_outcome",
    "empty_evidence",
    "unknown_launch",
    "never_started",
    "fresh_amendment",
    "deduplicated_retry",
])
def test_record_outcome_uniform_keys(tmp_path, monkeypatch, case):
    # axis: every return branch carries the full key set
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    if case == "invalid_outcome":
        result = ll.record_outcome(repo, "l1", "bogus", "evidence")
    elif case == "empty_evidence":
        ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
        _append_raw(_ledger_file(repo, os.environ), _started("l1"))
        result = ll.record_outcome(repo, "l1", "handback", "   ")
    elif case == "unknown_launch":
        result = ll.record_outcome(repo, "missing", "handback", "evidence")
    elif case == "never_started":
        ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
        _append_raw(_ledger_file(repo, os.environ), _refused("l1"))
        result = ll.record_outcome(repo, "l1", "handback", "evidence")
    elif case == "fresh_amendment":
        ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
        _append_raw(_ledger_file(repo, os.environ), _started("l1"))
        _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
        result = ll.record_outcome(repo, "l1", "handback", "again")
        assert result["recorded"] == "amendment"
    elif case == "deduplicated_retry":
        ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
        _append_raw(_ledger_file(repo, os.environ), _started("l1"))
        _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
        ll.record_outcome(repo, "l1", "handback", "done")
        result = ll.record_outcome(repo, "l1", "handback", "done")
        assert result["recorded"] == "amendment-existing"
    else:
        raise AssertionError("unknown case: %s" % case)
    assert set(result.keys()) == _RECORD_OUTCOME_KEYS


def test_bite_amend_lock_gate(tmp_path, monkeypatch):
    # Bite: amend goes through ledger lock
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    _append_raw(_ledger_file(repo, os.environ), _outcome("l1"))
    lock_result = ll._ensure_lock_file(repo)
    import file_lock
    file_lock.acquire(lock_result["path"])
    os.chmod(lock_result["path"], 0o600)
    try:
        result = ll.amend(repo, "l1", "vet", "ready", "reason", lock_timeout=0.1)
        assert result["reason"] == "lock-unavailable"
    finally:
        file_lock.release(lock_result["path"])


def test_bite_amend_not_terminal_refusal(tmp_path, monkeypatch):
    # Bite: live lane cannot be amended
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    result = ll.amend(repo, "l1", "vet", "ready", "reason")
    assert result["reason"] == "amend-not-terminal"


def test_bite_terminal_invariant_preservation(tmp_path, monkeypatch):
    # Bite: amendment never becomes outcome
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    _append_raw(_ledger_file(repo, os.environ), _started("l1"))
    ll.record_outcome(repo, "l1", "handback", "done")
    ll.amend(repo, "l1", "evidence", "corrected", "fix")
    folded = ll.fold(ll.read(repo)["records"])
    info = folded["launches"]["l1"]
    assert info["outcome"] == "handback"
    assert info["terminalKind"] == "outcome"
    assert len(info["amendments"]) == 1


def test_terminalize_still_writes_its_terminal(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    batch = "b-terminal-door"
    launch_id = "l-terminal-door"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved(launch_id, batch, ["a"], repo))
    ll.append(repo, _started(launch_id))
    count_before = len(ll.read(repo)["records"])
    result = ll.terminalize(
        repo, launch_id, outcome="handback", evidence="done", require_started=True,
    )
    assert result["ok"] is True
    records = ll.read(repo)["records"]
    assert len(records) == count_before + 1
    assert records[-1]["event"] == "outcome"
    assert records[-1]["outcome"] == "handback"
