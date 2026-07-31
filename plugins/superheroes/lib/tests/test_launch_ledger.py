import json
import os
import subprocess
import sys
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


def _started(launch_id, attempt=1):
    return {
        "event": "started",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "attempt": attempt,
        "pid": os.getpid(),
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


# --- fail-closed edges -------------------------------------------------------


def test_read_torn_trailing_line(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    ll.append(path, {"event": "reserved", "launchId": "a", "ts": 1.0, "schema": 1,
                       "batchId": "b", "repoId": "r", "issue": 1, "surfaces": ["x"],
                       "premise": {}, "preflight": {}, "argv": [], "doctrineDigest": "d",
                       "model": "m"})
    ll.append(path, {"event": "started", "launchId": "a", "ts": 2.0, "schema": 1,
                     "attempt": 1, "pid": 1, "logPath": "/l", "errPath": "/e"})
    with open(path, "rb") as fh:
        raw = fh.read()
    with open(path, "wb") as fh:
        fh.write(raw.rstrip(b"\n"))
    result = ll.read(path)
    assert result["state"] == "tornTail"
    assert result["state"] != "ok"
    assert len(result["records"]) == 1


def test_read_interior_corruption(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("not-json\n")
    ll.append(path, {"event": "x"})
    result = ll.read(path)
    assert result["state"] == "interiorCorrupt"


def test_read_interior_corruption_wins_over_torn_tail(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("not-json\n")
        fh.write('{"ok":true}')  # no trailing newline
    result = ll.read(path)
    assert result["state"] == "interiorCorrupt"


def test_read_missing_file(tmp_path):
    result = ll.read(str(tmp_path / "missing.jsonl"))
    assert result["state"] == "missing"
    assert result["records"] == []


def test_read_unreadable_file(tmp_path, monkeypatch):
    path = str(tmp_path / "ledger.jsonl")
    ll.append(path, {"x": 1})
    os.chmod(path, 0o000)
    try:
        result = ll.read(path)
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
    real_root.mkdir()
    link = tmp_path / "link-ledger"
    link.symlink_to(real_root)
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(link))
    result = ll.resolve_root(repo)
    assert result["ok"] is False
    assert result["reason"] == "ledger-root-symlink"


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
    path = str(tmp_path / "sub" / "ledger.jsonl")
    os.makedirs(os.path.dirname(path), mode=0o500)
    assert ll.append(path, {"x": 1}) is False


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
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    lp = ll.ledger_path(repo)
    lock_path = lp["path"] + ".lock"
    os.makedirs(os.path.dirname(lock_path), mode=0o700, exist_ok=True)
    import file_lock
    file_lock.acquire(lock_path)
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
    path = _ledger_file(repo, os.environ)
    ll.append(path, _started("l1"))
    ll.append(path, _outcome("l1"))
    result = ll.record_outcome(repo, "l1", "handback", "again")
    assert result["ok"] is False
    assert result["reason"] == "outcome-already-terminal"


def test_record_outcome_invalid_value(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    path = _ledger_file(repo, os.environ)
    ll.append(path, _started("l1"))
    result = ll.record_outcome(repo, "l1", "bogus", "evidence")
    assert result["ok"] is False
    assert result["reason"] == "outcome-invalid:bogus"


def test_record_outcome_empty_evidence(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    ll.reserve(repo, _reserved("l1", "b1", ["a"], repo))
    path = _ledger_file(repo, os.environ)
    ll.append(path, _started("l1"))
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
    path = _ledger_file(repo, os.environ)
    assert ll.append(path, _started(launch))
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
    ll.append(path, _started("l1"))
    ll.append(path, _outcome("l1"))
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
    ll.append(path, _started("l1"))
    ll.append(path, _outcome("l1"))
    result = ll.count(repo, batch)
    assert result["indeterminate"] is True
    assert result["resolved"] is False
    assert result["reason"] == "ledger-interiorCorrupt"


def test_count_indeterminate_on_unresolved_member(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-unresolved"
    _declare(repo, batch, 2)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo))
    ll.reserve(repo, _reserved("l2", batch, ["b"], repo))
    path = _ledger_file(repo, os.environ)
    ll.append(path, _started("l1"))
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
    ll.append(path, _started("l1"))
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
    ll.append(path, _started("l1"))
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
    ll.append(path, _refused("l1"))
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
    ll.append(path, _started("l1"))
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
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    launch_id = "lock-held-bite"
    lp = ll.ledger_path(repo)
    assert lp["ok"] is True
    lock_path = ll._lock_path(lp["path"])
    os.makedirs(os.path.dirname(lock_path), mode=0o700, exist_ok=True)
    import file_lock
    file_lock.acquire(lock_path)
    try:
        result = ll.reserve(
            repo,
            _reserved(launch_id, "bite", ["plugins/superheroes/lib"], repo),
            lock_timeout=0.1,
        )
        assert result["ok"] is False
        assert result["reason"] == "lock-unavailable"
        records = ll.read(lp["path"])["records"]
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
    shared_deadline = time.time() + 1
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
deadline = %(deadline)r
waited = time.time() < deadline
wait_seconds = 0.0
if waited:
    wait_start = time.time()
    while time.time() < deadline:
        time.sleep(0)
    wait_seconds = time.time() - wait_start
res = ll.reserve(repo, record, lock_timeout=5)
out = dict(res)
out["waited"] = waited
out["waitSeconds"] = wait_seconds
print(json.dumps(out))
""" % {
        "mod": mod_path,
        "_envkey": ll.LEDGER_ROOT_ENV,
        "_envval": ledger_root,
        "repo": repo,
        "deadline": shared_deadline,
    }
    p1 = subprocess.Popen([sys.executable, "-c", child], stdout=subprocess.PIPE, text=True)
    p2 = subprocess.Popen([sys.executable, "-c", child], stdout=subprocess.PIPE, text=True)
    out1 = json.loads(p1.communicate(timeout=30)[0])
    out2 = json.loads(p2.communicate(timeout=30)[0])
    assert out1["waited"] is True, out1
    assert out2["waited"] is True, out2
    results = [out1, out2]
    ok_count = sum(1 for r in results if r.get("ok"))
    assert ok_count == 1
    other = [r for r in results if not r.get("ok")]
    assert len(other) == 1
    reason = other[0]["reason"]
    assert reason.startswith("surface-overlap:") or reason == "lock-unavailable"
    path = ll.ledger_path(repo)["path"]
    records = ll.read(path)["records"]
    reserved = [r for r in records if r.get("event") == "reserved"]
    assert len(reserved) == 1
    assert reserved[0]["surfaces"] == ["plugins/superheroes/lib"]


# --- append/read basics ------------------------------------------------------


def test_append_creates_restricted_file(tmp_path):
    path = str(tmp_path / "nested" / "ledger.jsonl")
    assert ll.append(path, {"x": 1})
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
    result = ll.read(path)
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
    result = ll.ledger_path(repo)
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
    result = ll.ledger_path(repo)
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
    result = ll.ledger_path(repo)
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
    ll.append(path, _started("l1"))
    ll.append(path, _outcome("l1"))
    result = ll.count(repo, batch)
    assert result["indeterminate"] is True
    assert result["reason"] == "batch-undeclared"


def test_edge10_count_indeterminate_on_duplicate_declaration(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-dup"
    _declare(repo, batch, 1)
    path = _ledger_file(repo, os.environ)
    ll.append(path, _batch_declared(batch, 1))
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo))
    path = _ledger_file(repo, os.environ)
    ll.append(path, _started("l1"))
    ll.append(path, _outcome("l1"))
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
    ll.append(path, _started("l1"))
    ll.append(path, _outcome("l1"))
    result = ll.count(repo, batch)
    assert result["indeterminate"] is True
    assert result["reason"] == "batch-reservation-mismatch"


def test_edge12_count_indeterminate_when_reservations_above_declared(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger"))
    batch = "b-over"
    _declare(repo, batch, 1)
    ll.reserve(repo, _reserved("l1", batch, ["a"], repo))
    ll.reserve(repo, _reserved("l2", batch, ["b"], repo))
    path = _ledger_file(repo, os.environ)
    ll.append(path, _started("l1"))
    ll.append(path, _outcome("l1"))
    ll.append(path, _started("l2"))
    ll.append(path, _outcome("l2"))
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
    ll.append(path, _started("l1"))
    ll.append(path, _outcome("l1", outcome="handback"))
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
    ll.append(path, _refused("l1"))
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
    ll.append(path, _started("blocker"))
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
    result = ll.ledger_path(repo)
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
    result = ll.ledger_path(repo)
    assert result["ok"] is False
    assert result["reason"] == "ledger-file-insecure"


def test_edge18_fold_retry_without_started_refuses(tmp_path):
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
    assert result["ok"] is False
    assert result["reason"] == "fold-retry-without-started:a"
