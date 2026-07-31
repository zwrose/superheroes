import importlib.util
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_MOD = os.path.join(_HERE, "..", "launcher.py")
_LD_MOD = os.path.join(_HERE, "..", "launch_doctrine.py")

import launch_ledger as ll  # noqa: E402


def _load_launcher():
    spec = importlib.util.spec_from_file_location("launcher", _MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_doctrine():
    spec = importlib.util.spec_from_file_location("launch_doctrine", _LD_MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


L = _load_launcher()
LD = _load_doctrine()


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


def _head_sha(repo):
    out = subprocess.run(
        ["git", "-C", repo, "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


def _ledger_env(tmp_path, monkeypatch):
    root = str(tmp_path / "ledger-root")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, root)
    return root


def _all_checks(**overrides):
    base = {
        "quota": {"state": "pass", "reason": ""},
        "engine-auth": {"state": "pass", "reason": ""},
        "base-state": {"state": "pass", "reason": ""},
        "disjoint-surfaces": {"state": "pass", "reason": ""},
        "workspace-isolation": {"state": "pass", "reason": ""},
        "owner-capability": {"state": "pass", "reason": ""},
        "grant-state": {"state": "pass", "reason": ""},
    }
    base.update(overrides)
    return base


def _valid_premise(repo, **overrides):
    future = (datetime.now(timezone.utc) + timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    base = {
        "baseCommit": _head_sha(repo),
        "surfaces": ["plugins/superheroes/lib"],
        "batchId": "wave-test",
        "issue": 656,
        "maxRunMinutes": 240,
        "bashMaxTimeoutMs": 900000,
        "grantScope": {"applicable": True, "kind": "prs", "prs": [701]},
        "ownerCapability": {"applicable": True, "cleared": ["gh auth"], "expiresAt": future},
    }
    base.update(overrides)
    return base


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)


# --- preflight refusals ------------------------------------------------------


def test_preflight_unknown_check(tmp_path):
  # axis: preflight-unknown-check
    repo = _init_repo(tmp_path / "repo")
    checks = _all_checks()
    checks["bogus"] = {"state": "pass", "reason": ""}
    result = L.walk_preflight(checks, repo)
    assert result["ok"] is False
    assert result["reason"] == "preflight-unknown-check:bogus"


@pytest.mark.parametrize("missing", [
    "quota", "engine-auth", "base-state", "disjoint-surfaces",
    "workspace-isolation", "owner-capability", "grant-state",
])
def test_preflight_missing_check(tmp_path, missing):
  # axis: preflight-missing-check
    repo = _init_repo(tmp_path / "repo")
    checks = _all_checks()
    del checks[missing]
    result = L.walk_preflight(checks, repo)
    assert result["ok"] is False
    assert result["reason"] == "preflight-missing-check:%s" % missing


def test_preflight_malformed_input_list(tmp_path):
  # axis: preflight-malformed-input
    repo = _init_repo(tmp_path / "repo")
    result = L.walk_preflight([], repo)
    assert result["ok"] is False
    assert result["reason"] == "preflight-malformed-input"


def test_preflight_bad_state(tmp_path):
  # axis: preflight-bad-state
    repo = _init_repo(tmp_path / "repo")
    checks = _all_checks()
    checks["quota"] = {"state": "maybe", "reason": ""}
    result = L.walk_preflight(checks, repo)
    assert result["ok"] is False
    assert result["reason"] == "preflight-bad-state:quota"


def test_preflight_na_without_reason(tmp_path):
  # axis: preflight-na-without-reason
    repo = _init_repo(tmp_path / "repo")
    checks = _all_checks()
    checks["grant-state"] = {"state": "na"}
    result = L.walk_preflight(checks, repo)
    assert result["ok"] is False
    assert result["reason"] == "preflight-na-without-reason:grant-state"


def test_preflight_always_check_na(tmp_path):
  # axis: preflight-always-check-na
    repo = _init_repo(tmp_path / "repo")
    checks = _all_checks()
    checks["quota"] = {"state": "na", "reason": "n/a"}
    result = L.walk_preflight(checks, repo)
    assert result["ok"] is False
    assert result["reason"] == "preflight-always-check-na:quota"


def test_preflight_failed_check(tmp_path):
  # axis: preflight-failed
    repo = _init_repo(tmp_path / "repo")
    checks = _all_checks()
    checks["engine-auth"] = {"state": "fail", "reason": "no auth"}
    result = L.walk_preflight(checks, repo)
    assert result["ok"] is False
    assert result["reason"] == "preflight-failed:engine-auth"


def test_preflight_launcher_owned_check(tmp_path):
  # axis: preflight-launcher-owned-check
    repo = _init_repo(tmp_path / "repo")
    checks = _all_checks()
    checks["standing-rulings"] = {"state": "pass", "reason": ""}
    result = L.walk_preflight(checks, repo)
    assert result["ok"] is False
    assert result["reason"] == "preflight-launcher-owned-check:standing-rulings"


def test_standing_rulings_pass_with_digest(tmp_path):
  # axis: standing-rulings discharged by launcher
    repo = _init_repo(tmp_path / "repo")
    result = L.walk_preflight(_all_checks(), repo)
    assert result["ok"] is True
    sr = [c for c in result["checks"] if c["id"] == "standing-rulings"][0]
    assert sr["state"] == "pass"
    doctrine = LD.load()
    assert sr["evidence"] == doctrine["digest"]


def test_disjoint_surfaces_required_with_live_launch(tmp_path, monkeypatch):
  # axis: refusal when live launch exists and disjoint-surfaces is na
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    live_id = "live-1"
    rec = {
        "event": "reserved",
        "launchId": live_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "batchId": "other",
        "repoId": ll.repo_identity(repo),
        "issue": 1,
        "surfaces": ["other/path"],
        "premise": {},
        "preflight": {},
        "argv": [],
        "doctrineDigest": "d",
        "model": "m",
    }
    ll.reserve(repo, rec)
    checks = _all_checks()
    checks["disjoint-surfaces"] = {"state": "na", "reason": "not needed"}
    result = L.walk_preflight(checks, repo)
    assert result["ok"] is False
    assert result["reason"] == "preflight-disjointness-required"


def test_disjoint_surfaces_unreadable_ledger(tmp_path, monkeypatch):
  # axis: unreadable ledger refuses disjointness check
    repo = _init_repo(tmp_path / "repo")
    root = _ledger_env(tmp_path, monkeypatch)
    path = ll.ledger_path(repo)["path"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("not-json")
    checks = _all_checks()
    checks["disjoint-surfaces"] = {"state": "na", "reason": "n/a"}
    result = L.walk_preflight(checks, repo)
    assert result["ok"] is False
    assert result["reason"] == "preflight-disjointness-required"


# --- premise refusals --------------------------------------------------------


@pytest.mark.parametrize("field", [
    "baseCommit", "surfaces", "batchId", "issue",
    "maxRunMinutes", "bashMaxTimeoutMs", "grantScope", "ownerCapability",
])
def test_premise_missing_field(tmp_path, field):
  # axis: premise-missing-field
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo)
    del premise[field]
    result = L.validate_premise(premise, repo)
    assert result["ok"] is False
    assert result["reason"] == "premise-missing-field:%s" % field


def test_premise_base_commit_unresolved(tmp_path):
  # axis: resolution, not shape — 40 hex but not a real commit
    repo = _init_repo(tmp_path / "repo")
    fake = "0" * 40
    premise = _valid_premise(repo, baseCommit=fake)
    result = L.validate_premise(premise, repo)
    assert result["ok"] is False
    assert result["reason"] == "premise-base-commit-unresolved"


def test_premise_surfaces_empty(tmp_path):
  # axis: premise-surfaces-empty
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo, surfaces=[])
    result = L.validate_premise(premise, repo)
    assert result["ok"] is False
    assert result["reason"] == "premise-surfaces-empty"


def test_premise_max_run_minutes(tmp_path):
  # axis: premise-max-run-minutes
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo, maxRunMinutes=0)
    result = L.validate_premise(premise, repo)
    assert result["ok"] is False
    assert result["reason"] == "premise-max-run-minutes"


def test_premise_bash_max_timeout(tmp_path):
  # axis: premise-bash-max-timeout
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo, bashMaxTimeoutMs=0)
    result = L.validate_premise(premise, repo)
    assert result["ok"] is False
    assert result["reason"] == "premise-bash-max-timeout"


def test_premise_grant_fuzzy(tmp_path):
  # axis: premise-grant-fuzzy
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo, grantScope="bare-string")
    result = L.validate_premise(premise, repo)
    assert result["ok"] is False
    assert result["reason"] == "premise-grant-fuzzy"


def test_premise_grant_kind(tmp_path):
  # axis: premise-grant-kind
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo, grantScope={"applicable": True, "kind": "prs", "prs": []})
    result = L.validate_premise(premise, repo)
    assert result["ok"] is False
    assert result["reason"] == "premise-grant-kind"


def test_premise_owner_capability_expiry_missing(tmp_path):
  # axis: premise-owner-capability-expiry-missing
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo, ownerCapability={"applicable": True, "cleared": ["gh"]})
    result = L.validate_premise(premise, repo)
    assert result["ok"] is False
    assert result["reason"] == "premise-owner-capability-expiry-missing"


def test_premise_owner_capability_expiry_unparseable(tmp_path):
  # axis: premise-owner-capability-expiry-unparseable
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(
        repo,
        ownerCapability={"applicable": True, "cleared": ["gh"], "expiresAt": "not-a-date"},
    )
    result = L.validate_premise(premise, repo)
    assert result["ok"] is False
    assert result["reason"] == "premise-owner-capability-expiry-unparseable"


def test_premise_owner_capability_expires_before_horizon(tmp_path):
  # axis: horizon refusal — 20 minutes out with maxRunMinutes 240
    repo = _init_repo(tmp_path / "repo")
    soon = (datetime.now(timezone.utc) + timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
    premise = _valid_premise(
        repo,
        maxRunMinutes=240,
        ownerCapability={"applicable": True, "cleared": ["gh"], "expiresAt": soon},
    )
    result = L.validate_premise(premise, repo)
    assert result["ok"] is False
    assert result["reason"] == "premise-owner-capability-expires-before-horizon"


def test_premise_not_applicable_without_reason_grant(tmp_path):
  # axis: premise-not-applicable-without-reason:grantScope
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo, grantScope={"applicable": False})
    result = L.validate_premise(premise, repo)
    assert result["ok"] is False
    assert result["reason"] == "premise-not-applicable-without-reason:grantScope"


def test_premise_not_applicable_without_reason_owner(tmp_path):
  # axis: premise-not-applicable-without-reason:ownerCapability
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo, ownerCapability={"applicable": False})
    result = L.validate_premise(premise, repo)
    assert result["ok"] is False
    assert result["reason"] == "premise-not-applicable-without-reason:ownerCapability"


def test_premise_check_mismatch_grant_applicable_but_na(tmp_path):
  # axis: C7 cross-check — grant applicable but preflight na
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo)
    checks = _all_checks()
    checks["grant-state"] = {"state": "na", "reason": "n/a"}
    preflight = L.walk_preflight(checks, repo)
    result = L.validate_premise(premise, repo, preflight_checks=preflight["checks"])
    assert result["ok"] is False
    assert result["reason"] == "premise-check-mismatch:grant-state"


def test_premise_check_mismatch_grant_not_applicable_but_pass(tmp_path):
  # axis: C7 cross-check — grant not applicable but preflight pass
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(
        repo,
        grantScope={"applicable": False, "reason": "no grants"},
    )
    checks = _all_checks()
    checks["grant-state"] = {"state": "na", "reason": "n/a"}
    preflight = L.walk_preflight(checks, repo)
    result = L.validate_premise(premise, repo, preflight_checks=preflight["checks"])
    assert result["ok"] is True


def test_premise_check_mismatch_grant_not_applicable_but_pass_fails(tmp_path):
  # axis: C7 cross-check — grant not applicable but preflight pass (mismatch)
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(
        repo,
        grantScope={"applicable": False, "reason": "no grants"},
    )
    preflight = L.walk_preflight(_all_checks(), repo)
    result = L.validate_premise(premise, repo, preflight_checks=preflight["checks"])
    assert result["ok"] is False
    assert result["reason"] == "premise-check-mismatch:grant-state"


def test_premise_check_mismatch_owner_applicable_but_na(tmp_path):
  # axis: C7 cross-check — owner applicable but preflight na
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo)
    checks = _all_checks()
    checks["owner-capability"] = {"state": "na", "reason": "n/a"}
    preflight = L.walk_preflight(checks, repo)
    result = L.validate_premise(premise, repo, preflight_checks=preflight["checks"])
    assert result["ok"] is False
    assert result["reason"] == "premise-check-mismatch:owner-capability"


def test_premise_check_mismatch_owner_not_applicable_ok(tmp_path):
  # axis: C7 cross-check — owner not applicable with matching preflight na
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(
        repo,
        ownerCapability={"applicable": False, "reason": "not needed"},
    )
    checks = _all_checks()
    checks["owner-capability"] = {"state": "na", "reason": "n/a"}
    checks["grant-state"] = {"state": "na", "reason": "n/a"}
    premise["grantScope"] = {"applicable": False, "reason": "no grants"}
    preflight = L.walk_preflight(checks, repo)
    result = L.validate_premise(premise, repo, preflight_checks=preflight["checks"])
    assert result["ok"] is True


def test_premise_check_mismatch_owner_not_applicable_but_pass(tmp_path):
  # axis: C7 cross-check — owner not applicable but preflight pass
    repo = _init_repo(tmp_path / "repo")
    future = (datetime.now(timezone.utc) + timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    premise = _valid_premise(
        repo,
        ownerCapability={"applicable": False, "reason": "not needed"},
    )
    preflight = L.walk_preflight(_all_checks(), repo)
    result = L.validate_premise(premise, repo, preflight_checks=preflight["checks"])
    assert result["ok"] is False
    assert result["reason"] == "premise-check-mismatch:owner-capability"


def test_premise_stamps_standing_exclusions(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo)
    result = L.validate_premise(premise, repo)
    assert result["ok"] is True
    assert result["premise"]["standingExclusions"] == L.STANDING_EXCLUSIONS


# --- compose -----------------------------------------------------------------


def test_compose_ruling_zero_absent(tmp_path):
  # axis: refusal to compose a launch whose ruling 0 it could not verify
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo)

    def bad_loader():
        doctrine = LD.load()
        mutated = dict(doctrine)
        own_line = LD.ruling_line(doctrine, "own-worktree")
        block = mutated["rulingsBlock"].replace(own_line + "\n", "").replace(own_line, "")
        mutated["rulingsBlock"] = block
        return mutated

    result = L.compose_launch(repo, 656, premise, doctrine_loader=bad_loader)
    assert result["ok"] is False
    assert result["reason"] == "compose-ruling-zero-absent"


def test_model_not_registry_known(tmp_path):
  # axis: off-registry token refuses
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo)
    result = L.compose_launch(repo, 656, premise, model="__nope__")
    assert result["ok"] is False
    assert result["reason"] == "model-not-registry-known"


def test_model_default_opus(tmp_path):
  # axis: default resolves to opus token
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo)
    result = L.compose_launch(repo, 656, premise)
    assert result["ok"] is True
    assert result["model"] == "opus"
    assert result["argv"][2] == "opus"


def test_compose_argv_shape(tmp_path):
  # axis: composed argv carries --model with registry token
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo)
    result = L.compose_launch(repo, 656, premise, model="sonnet")
    assert result["ok"] is True
    assert result["argv"] == ["claude", "--model", "sonnet", "-p", result["prompt"]]


# --- spawn ordering and detachment ---------------------------------------------


def _standin_script(behavior):
    return (
        "import sys,time,os,signal\n"
        "behavior=%r\n"
        "if behavior=='sleep':\n"
        "  time.sleep(60)\n"
        "elif behavior=='exit1':\n"
        "  sys.exit(1)\n"
        "elif behavior=='exit0':\n"
        "  sys.exit(0)\n"
        "elif behavior=='stdin':\n"
        "  data=sys.stdin.read()\n"
        "  open(os.environ['STDIN_OUT'],'w').write(repr(data))\n"
        "  time.sleep(60)\n"
        % behavior
    )


def _make_spawn_fn(behavior):
    def spawn(argv, repo_root, out_fh, err_fh, child_env):
        real_argv = [
            sys.executable, "-c", _standin_script(behavior),
        ]
        env = dict(child_env)
        return subprocess.Popen(
            real_argv,
            cwd=repo_root,
            stdin=subprocess.DEVNULL,
            stdout=out_fh,
            stderr=err_fh,
            start_new_session=True,
            close_fds=True,
            env=env,
        )
    return spawn


def test_spawn_reserved_before_child(tmp_path, monkeypatch):
  # axis: reserved before child starts; started carries real pid
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    order = []

    def tracking_spawn(argv, repo_root, out_fh, err_fh, child_env):
        lp = ll.ledger_path(repo_root)
        records = ll.read(lp["path"])["records"]
        order.append(("before_spawn", len(records)))
        proc = _make_spawn_fn("sleep")(argv, repo_root, out_fh, err_fh, child_env)
        order.append(("after_spawn", proc.pid))
        return proc

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=tracking_spawn,
        settle_seconds=0.3,
    )
    assert result["ok"] is True
    lp = ll.ledger_path(repo)["path"]
    records = ll.read(lp)["records"]
    reserved = [r for r in records if r["event"] == "reserved"]
    started = [r for r in records if r["event"] == "started"]
    assert reserved
    assert started
    assert order[0][0] == "before_spawn"
    assert order[0][1] >= 1
    assert started[0]["pid"] == order[1][1]


def test_started_append_failed_terminates_child(tmp_path, monkeypatch):
  # axis: no live child without a record
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    child_pid = {"pid": None}

    real_append = ll.append

    def failing_append(path, record):
        if record.get("event") == "started":
            return False
        return real_append(path, record)

    monkeypatch.setattr(ll, "append", failing_append)

    def capture_spawn(argv, repo_root, out_fh, err_fh, child_env):
        proc = _make_spawn_fn("sleep")(argv, repo_root, out_fh, err_fh, child_env)
        child_pid["pid"] = proc.pid
        return proc

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=capture_spawn,
        settle_seconds=0.1,
    )
    assert result["ok"] is False
    pid = child_pid["pid"]
    assert pid is not None
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    lp = ll.ledger_path(repo)["path"]
    records = ll.read(lp)["records"]
    refused = [r for r in records if r["event"] == "refused"]
    assert any(r["stage"] == "started-append-failed" for r in refused)


def test_detachment_stdin_devnull(tmp_path, monkeypatch):
  # axis: real child outlives parent handles; stdin is DEVNULL
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    stdin_out = str(tmp_path / "stdin.txt")

    def stdin_spawn(argv, repo_root, out_fh, err_fh, child_env):
        env = dict(child_env)
        env["STDIN_OUT"] = stdin_out
        return _make_spawn_fn("stdin")(argv, repo_root, out_fh, err_fh, env)

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=stdin_spawn,
        settle_seconds=0.5,
    )
    assert result["ok"] is True
    assert os.path.exists(stdin_out)
    assert open(stdin_out, encoding="utf-8").read() == "''"
    try:
        os.kill(result["pid"], signal.SIGTERM)
    except ProcessLookupError:
        pass


# --- retry / settle branches -------------------------------------------------


def test_retry_nonzero_exit_clean_worktree(tmp_path, monkeypatch):
  # axis: nonzero exit with clean worktree retries
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    calls = {"n": 0}

    def flip_spawn(argv, repo_root, out_fh, err_fh, child_env):
        calls["n"] += 1
        behavior = "exit1" if calls["n"] == 1 else "sleep"
        return _make_spawn_fn(behavior)(argv, repo_root, out_fh, err_fh, child_env)

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=flip_spawn,
        settle_seconds=0.3,
        backoff_seconds=(0,),
    )
    assert result["ok"] is True
    assert calls["n"] == 2
    lp = ll.ledger_path(repo)["path"]
    retries = [r for r in ll.read(lp)["records"] if r["event"] == "retry"]
    assert len(retries) == 1


def test_retry_nonzero_exit_dirtied_worktree(tmp_path, monkeypatch):
  # axis: never retry a launch that may have done work
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    calls = {"once": False}

    def dirty_spawn(argv, repo_root, out_fh, err_fh, child_env):
        proc = _make_spawn_fn("exit1")(argv, repo_root, out_fh, err_fh, child_env)
        if not calls["once"]:
            calls["once"] = True
            (tmp_path / "repo" / "dirt.txt").write_text("dirty\n")
        return proc

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=dirty_spawn,
        settle_seconds=0.3,
    )
    assert result["ok"] is False
    assert result["reason"] == "retry-unsafe-worktree-dirtied"


def test_settle_exit_zero_uncertain(tmp_path, monkeypatch):
  # axis: exit zero inside settle window is uncertain
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=_make_spawn_fn("exit0"),
        settle_seconds=0.5,
    )
    assert result["ok"] is False
    assert result["reason"] == "settle-exit-zero-uncertain"


def test_retry_attempt_cap(tmp_path, monkeypatch):
  # axis: attempt cap fires
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=_make_spawn_fn("exit1"),
        settle_seconds=0.2,
        max_attempts=2,
        backoff_seconds=(0,),
    )
    assert result["ok"] is False
    assert result["reason"] == "attempts-exhausted"


def test_retry_deadline_exceeded(tmp_path, monkeypatch):
  # axis: total deadline fires before next retry
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=_make_spawn_fn("exit1"),
        settle_seconds=0.1,
        max_attempts=5,
        backoff_seconds=(1,),
        total_deadline_seconds=0,
    )
    assert result["ok"] is False
    assert result["reason"] == "retry-deadline-exceeded"


# --- count pass-through ------------------------------------------------------


def test_count_passthrough_preserves_indeterminate(tmp_path, monkeypatch):
  # axis: launcher adds no key and changes no value
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    expected = ll.count(repo, "missing-batch")
    got = L.count_batch(repo, "missing-batch")
    assert got == expected
    assert got["indeterminate"] is True


# --- CLI shape ---------------------------------------------------------------


def test_cli_preflight_exit_code(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    checks_path = tmp_path / "checks.json"
    _write_json(checks_path, _all_checks())
    proc = subprocess.run(
        [sys.executable, _MOD, "preflight", "--repo-root", repo, "--checks", str(checks_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["go"] is True
