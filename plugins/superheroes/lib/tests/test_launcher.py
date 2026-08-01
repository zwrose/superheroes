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
import heartbeat as hb  # noqa: E402


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


@pytest.fixture(autouse=True)
def _autouse_isolated_ledger_root(tmp_path, monkeypatch):
    _ledger_env(tmp_path, monkeypatch)


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
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("not-json\n")
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


def _write_core_with_builder_tier(repo, prefs):
    import importlib.util as _u
    _lib = os.path.join(_HERE, "..")
    spec = _u.spec_from_file_location("core_md", os.path.join(_lib, "core_md.py"))
    cm = _u.module_from_spec(spec)
    spec.loader.exec_module(cm)
    facts = {
        "verifyCommand": "npm test",
        "stackTags": [],
        "threatModel": "x",
        "patterns": "",
        "enginePreferences": prefs,
    }
    text = cm.render_core(facts, "confirmed", "2026-06-30", "2026-06-30")
    core_dir = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(core_dir, exist_ok=True)
    with open(os.path.join(core_dir, "core.md"), "w", encoding="utf-8") as fh:
        fh.write(text)


def test_compose_default_tier_from_unset_config(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo)
    result = L.compose_launch(repo, 656, premise)
    assert result["ok"] is True
    assert "opus" in result["argv"]
    assert result["modelResolution"]["source"] == "default"


def test_compose_configured_sonnet_from_core_md(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _write_core_with_builder_tier(repo, {"builderDispatchTier": "sonnet"})
    premise = _valid_premise(repo)
    result = L.compose_launch(repo, 656, premise)
    assert result["ok"] is True
    assert "sonnet" in result["argv"]
    assert "opus" not in result["argv"]
    assert result["modelResolution"]["source"] == "configured"


def test_compose_configured_fable_falls_back_to_opus(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    import engine_pref as ep

    def _fable_tier(_cwd, root=None):
        return {
            "tier": "opus",
            "source": "invalid-config-default",
            "reason": "fable-never-a-launch-default",
        }

    monkeypatch.setattr(ep, "load_builder_dispatch_tier", _fable_tier)
    premise = _valid_premise(repo)
    result = L.compose_launch(repo, 656, premise)
    assert result["ok"] is True
    assert "opus" in result["argv"]
    assert result["modelResolution"]["source"] == "invalid-config-default"
    assert result["modelResolution"]["reason"] == "fable-never-a-launch-default"


def test_compose_unreadable_profile_defaults_to_opus(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    import engine_pref as ep

    def _unreadable(_cwd, root=None):
        return {
            "tier": "opus",
            "source": "unreadable-default",
            "reason": "profile-ambiguous",
        }

    monkeypatch.setattr(ep, "load_builder_dispatch_tier", _unreadable)
    premise = _valid_premise(repo)
    result = L.compose_launch(repo, 656, premise)
    assert result["ok"] is True
    assert "opus" in result["argv"]
    assert result["modelResolution"]["source"] == "unreadable-default"
    assert result["modelResolution"]["reason"] == "profile-ambiguous"


def test_compose_explicit_model_beats_configured_tier(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _write_core_with_builder_tier(repo, {"builderDispatchTier": "haiku"})
    premise = _valid_premise(repo)
    result = L.compose_launch(repo, 656, premise, model="sonnet")
    assert result["ok"] is True
    assert "sonnet" in result["argv"]
    assert result["modelResolution"]["source"] == "explicit"


def test_compose_model_fable_refuses(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo)
    result = L.compose_launch(repo, 656, premise, model="fable")
    assert result["ok"] is False
    assert result["reason"] == "model-not-registry-known"


def test_launch_build_reserved_carries_model_source(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.3,
    )
    assert result["ok"] is True
    assert result["model"] == "opus"
    assert result["modelResolution"]["source"] == "default"
    records = ll.read(repo)["records"]
    reserved = [r for r in records if r.get("event") == "reserved"][0]
    assert reserved["modelSource"] == "default"
    assert reserved["modelReason"] == ""
    try:
        os.kill(result["pid"], signal.SIGTERM)
    except ProcessLookupError:
        pass


def test_launch_build_preflight_refusal_empty_model_source(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    checks = _all_checks()
    checks["engine-auth"] = {"state": "fail", "reason": "no auth"}
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        checks,
        log_dir,
    )
    assert result["ok"] is False
    records = ll.read(repo)["records"]
    reserved = [r for r in records if r.get("event") == "reserved"]
    assert len(reserved) == 1
    assert reserved[0]["model"] == ""
    assert reserved[0]["modelSource"] == ""
    assert reserved[0]["modelReason"] == ""


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
        records = ll.read(repo_root)["records"]
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
    records = ll.read(repo)["records"]
    reserved = [r for r in records if r["event"] == "reserved"]
    started = [r for r in records if r["event"] == "started"]
    assert reserved
    assert started
    assert order[0][0] == "before_spawn"
    assert order[0][1] >= 1
    assert started[0]["pid"] == order[1][1]


def test_started_append_failure_reaps_child_and_writes_no_invalid_terminal(tmp_path, monkeypatch):
    # Old assertion demanded a park the fold reader refuses (outcome without started).
    # axis: no live child without a record
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    child_pid = {"pid": None}
    calls = {"n": 0}

    real_append = ll.append

    def failing_append(repo_root, record, env=None):
        if record.get("event") == "started":
            calls["n"] += 1
            return False
        return real_append(repo_root, record, env=env)

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
    assert result["reason"] == "terminalization-failed:ledger-append-failed"
    pid = child_pid["pid"]
    assert pid is not None
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    records = ll.read(repo)["records"]
    launch_id = result["launchId"]
    launch_records = [r for r in records if r.get("launchId") == launch_id]
    assert not any(r.get("event") == "outcome" for r in launch_records)
    assert not any(r.get("event") == "started" for r in launch_records)
    folded = ll.fold(records)
    assert folded["ok"] is True
    assert folded["launches"][launch_id]["terminal"] is False
    assert calls["n"] >= 1


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


def test_retry_nonzero_exit_parks_no_retry(tmp_path, monkeypatch):
  # axis: N2/N3 — nonzero exit after spawn parks; never retries
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
    assert result["ok"] is False
    assert result["reason"] == "settle-nonzero-exit"
    assert calls["n"] == 1
    records = ll.read(repo)["records"]
    parks = [r for r in records if r.get("event") == "outcome" and r.get("outcome") == "park"]
    assert len(parks) == 1
    assert parks[0]["evidence"] == "nonzero-exit:1"
    retries = [r for r in records if r.get("event") == "retry"]
    assert retries == []


def test_nonzero_exit_parks_even_when_worktree_dirty(tmp_path, monkeypatch):
  # axis: N3 — worktree delta no longer gates retry; parks instead
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")

    def dirty_spawn(argv, repo_root, out_fh, err_fh, child_env):
        proc = _make_spawn_fn("exit1")(argv, repo_root, out_fh, err_fh, child_env)
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
    assert result["reason"] == "settle-nonzero-exit"
    parks = [
        r for r in ll.read(repo)["records"]
        if r.get("event") == "outcome" and r.get("outcome") == "park"
    ]
    assert len(parks) == 1


def test_settle_exit_zero_uncertain(tmp_path, monkeypatch):
  # axis: exit zero inside settle window parks
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
    parks = [
        r for r in ll.read(repo)["records"]
        if r.get("event") == "outcome" and r.get("outcome") == "park"
    ]
    assert len(parks) == 1
    assert parks[0]["evidence"] == "exit-zero"


def test_spawn_oserror_retries_then_succeeds(tmp_path, monkeypatch):
  # axis: OSError is the only retryable spawn failure
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    calls = {"n": 0}

    def oserror_then_sleep(argv, repo_root, out_fh, err_fh, child_env):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("spawn failed")
        return _make_spawn_fn("sleep")(argv, repo_root, out_fh, err_fh, child_env)

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=oserror_then_sleep,
        settle_seconds=0.3,
        backoff_seconds=(0,),
    )
    assert result["ok"] is True
    assert calls["n"] == 2
    records = ll.read(repo)["records"]
    retries = [r for r in records if r.get("event") == "retry"]
    assert len(retries) == 1
    assert retries[0]["attempt"] == 1
    assert retries[0]["reason"] == "spawn-oserror"


def test_spawn_oserror_exhausted_refuses(tmp_path, monkeypatch):
  # axis: spawn OSError on every attempt refuses (no child ever ran)
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")

    def always_oserror(argv, repo_root, out_fh, err_fh, child_env):
        raise OSError("spawn failed")

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=always_oserror,
        max_attempts=2,
        backoff_seconds=(0,),
    )
    assert result["ok"] is False
    assert result["reason"] == "spawn-oserror-exhausted"
    records = ll.read(repo)["records"]
    refused = [r for r in records if r.get("event") == "refused"]
    assert any(r.get("stage") == "spawn" for r in refused)
    started = [r for r in records if r.get("event") == "started"]
    assert started == []


def test_retry_deadline_exceeded_before_spawn(tmp_path, monkeypatch):
  # axis: deadline before any child spawns refuses
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")

    def always_oserror(argv, repo_root, out_fh, err_fh, child_env):
        raise OSError("spawn failed")

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=always_oserror,
        max_attempts=5,
        backoff_seconds=(1,),
        total_deadline_seconds=0,
    )
    assert result["ok"] is False
    assert result["reason"] == "retry-deadline-exceeded"
    refused = [r for r in ll.read(repo)["records"] if r.get("event") == "refused"]
    assert any(r.get("stage") == "retry-deadline-exceeded" for r in refused)


def test_deadline_after_spawn_parks(tmp_path, monkeypatch):
  # axis: deadline after child spawned parks
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    clock = {"monotonic": 1000.0}

    class _TimeShim:
        @staticmethod
        def monotonic():
            return clock["monotonic"]

        @staticmethod
        def time():
            return time.time()

        @staticmethod
        def sleep(seconds):
            pass

    monkeypatch.setattr(L, "time", _TimeShim)

    def capture_spawn(argv, repo_root, out_fh, err_fh, child_env):
        proc = _make_spawn_fn("sleep")(argv, repo_root, out_fh, err_fh, child_env)
        clock["monotonic"] += 10
        return proc

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=capture_spawn,
        settle_seconds=10,
        total_deadline_seconds=1,
    )
    assert result["ok"] is False
    assert result["reason"] == "retry-deadline-exceeded"
    parks = [
        r for r in ll.read(repo)["records"]
        if r.get("event") == "outcome" and r.get("outcome") == "park"
    ]
    assert len(parks) == 1


# --- count pass-through ------------------------------------------------------


def test_count_passthrough_preserves_indeterminate(tmp_path, monkeypatch):
  # axis: launcher adds no key and changes no value
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    expected = ll.count(repo, "missing-batch")
    got = L.count_batch(repo, "missing-batch")
    assert got == expected
    assert got["indeterminate"] is True


def test_cli_count_indeterminate_exits_nonzero(tmp_path, monkeypatch):
  # edge 21: indeterminate count exits non-zero
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    proc = subprocess.run(
        [sys.executable, _MOD, "count", "--repo-root", repo, "--batch", "missing-batch"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    payload = json.loads(proc.stdout)
    assert payload["indeterminate"] is True


def test_cli_count_resolved_exits_zero(tmp_path, monkeypatch):
  # edge 22: resolved batch count exits zero
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    batch = "resolved-batch"
    ll.declare_batch(repo, batch, 1)
    launch_id = "launch-resolved"
    ll.reserve(repo, {
        "event": "reserved",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "batchId": batch,
        "repoId": ll.repo_identity(repo),
        "issue": 656,
        "surfaces": ["plugins/superheroes/lib"],
        "premise": {},
        "preflight": {},
        "argv": [],
        "doctrineDigest": "d",
        "model": "m",
    })
    ll.append(repo, {
        "event": "started",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "attempt": 1,
        "pid": 424242,
        "logPath": "/tmp/out",
        "errPath": "/tmp/err",
    })
    ll.record_outcome(repo, launch_id, "handback", "done")
    proc = subprocess.run(
        [sys.executable, _MOD, "count", "--repo-root", repo, "--batch", batch],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["indeterminate"] is False


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


# --- fail-closed edge tests (work order N) -----------------------------------


def test_edge1_declare_batch_invalid_expected(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    result = L.declare_batch(repo, "batch-a", 0)
    assert result["ok"] is False
    assert result["reason"] == "batch-expected-invalid"
    proc = subprocess.run(
        [
            sys.executable, _MOD, "declare-batch",
            "--repo-root", repo, "--batch", "batch-a", "--expected", "0",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["reason"] == "batch-expected-invalid"


def test_edge2_declare_batch_duplicate_declaration(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    batch = "dup-batch"
    first = L.declare_batch(repo, batch, 1)
    second = L.declare_batch(repo, batch, 1)
    assert first["ok"] is True
    assert second["ok"] is True
    launch_id = "launch-dup"
    ll.reserve(repo, {
        "event": "reserved",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "batchId": batch,
        "repoId": ll.repo_identity(repo),
        "issue": 656,
        "surfaces": ["plugins/superheroes/lib"],
        "premise": {},
        "preflight": {},
        "argv": [],
        "doctrineDigest": "d",
        "model": "m",
    })
    ll.append(repo, {
        "event": "started",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "attempt": 1,
        "pid": 424242,
        "logPath": "/tmp/out",
        "errPath": "/tmp/err",
    })
    ll.append(repo, {
        "event": "outcome",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "outcome": "handback",
        "evidence": "done",
    })
    count = L.count_batch(repo, batch)
    assert count["indeterminate"] is True
    assert count["reason"] == "batch-duplicate-declaration"


def test_edge3_spawn_oserror_closes_handles_and_retries(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    calls = {"n": 0}
    open_handles = []

    real_open = open

    def tracking_open(path, mode="r", *args, **kwargs):
        fh = real_open(path, mode, *args, **kwargs)
        if "ab" in mode:
            open_handles.append(fh)
        return fh

    def oserror_then_sleep(argv, repo_root, out_fh, err_fh, child_env):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("spawn failed")
        return _make_spawn_fn("sleep")(argv, repo_root, out_fh, err_fh, child_env)

    monkeypatch.setattr("builtins.open", tracking_open)
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=oserror_then_sleep,
        settle_seconds=0.2,
        backoff_seconds=(0,),
    )
    assert result["ok"] is True
    assert calls["n"] == 2
    for fh in open_handles:
        assert fh.closed


def test_edge4_spawn_oserror_exhausted_refuses(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")

    def always_oserror(argv, repo_root, out_fh, err_fh, child_env):
        raise OSError("spawn failed")

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=always_oserror,
        max_attempts=2,
        backoff_seconds=(0,),
    )
    assert result["ok"] is False
    assert result["reason"] == "spawn-oserror-exhausted"
    records = ll.read(repo)["records"]
    assert not any(r.get("event") == "started" for r in records)
    assert any(r.get("event") == "refused" for r in records)


def test_edge5_nonzero_exit_in_settle_parks(tmp_path, monkeypatch):
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
        settle_seconds=0.3,
    )
    assert result["ok"] is False
    records = ll.read(repo)["records"]
    parks = [r for r in records if r.get("event") == "outcome" and r.get("outcome") == "park"]
    refused = [r for r in records if r.get("event") == "refused"]
    assert len(parks) == 1
    assert parks[0]["evidence"] == "nonzero-exit:1"
    assert refused == []


def test_edge6_zero_exit_in_settle_parks(tmp_path, monkeypatch):
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
        settle_seconds=0.3,
    )
    assert result["ok"] is False
    records = ll.read(repo)["records"]
    parks = [r for r in records if r.get("event") == "outcome" and r.get("outcome") == "park"]
    refused = [r for r in records if r.get("event") == "refused"]
    assert len(parks) == 1
    assert parks[0]["evidence"] == "exit-zero"
    assert refused == []


def test_edge7_child_alive_after_settle_succeeds(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.3,
    )
    assert result["ok"] is True
    try:
        os.kill(result["pid"], signal.SIGTERM)
    except ProcessLookupError:
        pass


def test_edge8_deadline_parks_if_spawned_refuses_if_not(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")

    parked = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=10,
        total_deadline_seconds=1,
    )
    assert parked["ok"] is False
    assert parked["reason"] == "retry-deadline-exceeded"
    records = ll.read(repo)["records"]
    assert any(r.get("event") == "started" for r in records)
    assert any(r.get("event") == "outcome" and r.get("outcome") == "park" for r in records)

    repo2 = _init_repo(tmp_path / "repo2")
    log_dir2 = str(tmp_path / "logs2")

    def always_oserror(argv, repo_root, out_fh, err_fh, child_env):
        raise OSError("spawn failed")

    refused = L.launch_build(
        repo2,
        656,
        _valid_premise(repo2),
        _all_checks(),
        log_dir2,
        spawn_fn=always_oserror,
        max_attempts=5,
        backoff_seconds=(1,),
        total_deadline_seconds=0,
    )
    assert refused["ok"] is False
    assert refused["reason"] == "retry-deadline-exceeded"
    records2 = ll.read(repo2)["records"]
    assert any(r.get("event") == "refused" for r in records2)
    assert not any(r.get("event") == "outcome" for r in records2)


def test_edge9_duplicate_key_in_checks_json(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    checks_path = tmp_path / "checks-dup.json"
    checks_path.write_text('{"quota": {"state": "pass", "reason": ""}, "quota": {"state": "fail", "reason": "x"}}')
    proc = subprocess.run(
        [sys.executable, _MOD, "preflight", "--repo-root", repo, "--checks", str(checks_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["reason"] == "preflight-duplicate-key"


def test_edge10_duplicate_key_in_premise_json(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    premise_path = tmp_path / "premise-dup.json"
    premise_path.write_text('{"issue": 656, "issue": 657}')
    proc = subprocess.run(
        [
            sys.executable, _MOD, "compose",
            "--repo-root", repo, "--issue", "656", "--premise", str(premise_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["reason"] == "premise-duplicate-key"


def test_edge11_owner_capability_cleared_missing(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    future = (datetime.now(timezone.utc) + timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    premise = _valid_premise(
        repo,
        ownerCapability={"applicable": True, "expiresAt": future},
    )
    result = L.validate_premise(premise, repo)
    assert result["ok"] is False
    assert result["reason"] == "premise-owner-capability-cleared-missing"


def test_edge12_owner_capability_cleared_string(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    future = (datetime.now(timezone.utc) + timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    premise = _valid_premise(
        repo,
        ownerCapability={"applicable": True, "cleared": "everything", "expiresAt": future},
    )
    result = L.validate_premise(premise, repo)
    assert result["ok"] is False
    assert result["reason"] == "premise-owner-capability-cleared-fuzzy"


def test_edge13_owner_capability_cleared_empty_list(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    future = (datetime.now(timezone.utc) + timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    premise = _valid_premise(
        repo,
        ownerCapability={"applicable": True, "cleared": [], "expiresAt": future},
    )
    result = L.validate_premise(premise, repo)
    assert result["ok"] is False
    assert result["reason"] == "premise-owner-capability-cleared-empty"


def test_edge14_owner_capability_cleared_whitespace_item(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    future = (datetime.now(timezone.utc) + timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    premise = _valid_premise(
        repo,
        ownerCapability={"applicable": True, "cleared": ["  "], "expiresAt": future},
    )
    result = L.validate_premise(premise, repo)
    assert result["ok"] is False
    assert result["reason"] == "premise-owner-capability-cleared-item-empty"


def test_edge15_owner_capability_cleared_valid_list(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo)
    result = L.validate_premise(premise, repo)
    assert result["ok"] is True


def test_edge16_base_commit_head_resolved_in_reservation(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    head = _head_sha(repo)
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo, baseCommit="HEAD"),
        _all_checks(),
        log_dir,
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.2,
    )
    assert result["ok"] is True
    records = ll.read(repo)["records"]
    reserved = [r for r in records if r.get("event") == "reserved"][0]
    assert reserved["premise"]["baseCommit"] == head
    assert len(reserved["premise"]["baseCommit"]) == 40
    try:
        os.kill(result["pid"], signal.SIGTERM)
    except ProcessLookupError:
        pass


def test_edge17_issue_mismatch_refused(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo, issue=657),
        _all_checks(),
        log_dir,
    )
    assert result["ok"] is False
    assert result["reason"] == "premise-issue-mismatch"


def test_edge18_corrupt_ledger_fails_preflight_check(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    root = _ledger_env(tmp_path, monkeypatch)
    path = ll.ledger_path(repo)["path"]
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("not-json\n")
    result = L.walk_preflight(_all_checks(), repo)
    assert result["ok"] is False
    assert result["reason"] == "preflight-ledger-unreadable"


def test_edge19_oserror_retry_does_not_ignore_refused_append_failure(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    real_append_raw = ll._append_raw
    calls = {"n": 0}

    def always_oserror(argv, repo_root, out_fh, err_fh, child_env):
        raise OSError("spawn failed")

    def failing_refused_append(repo_root, record, env=None):
        if record.get("event") == "refused" and record.get("stage") == "spawn":
            calls["n"] += 1
            return False
        return real_append_raw(repo_root, record, env=env)

    monkeypatch.setattr(ll, "_append_raw", failing_refused_append)
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=always_oserror,
        max_attempts=1,
        backoff_seconds=(0,),
    )
    assert result["ok"] is False
    assert result["reason"].startswith("terminalization-failed:")
    assert calls["n"] == 1


def test_log_dir_exists_as_file_refuses_and_terminalizes(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "not-a-dir")
    with open(log_dir, "w", encoding="utf-8") as fh:
        fh.write("x")
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
    )
    assert result["ok"] is False
    assert result["reason"] == "log-dir-create-failed"
    records = ll.read(repo)["records"]
    refused = [r for r in records if r.get("event") == "refused"]
    assert any(
        r.get("launchId") == result["launchId"]
        and r.get("stage") == "log-dir"
        and r.get("reason") == "log-dir-create-failed"
        for r in refused
    )


def test_log_dir_parent_readonly_refuses_and_terminalizes(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    readonly_parent = tmp_path / "readonly-parent"
    readonly_parent.mkdir()
    readonly_parent.chmod(0o500)
    log_dir = str(readonly_parent / "logs")
    try:
        result = L.launch_build(
            repo,
            656,
            _valid_premise(repo),
            _all_checks(),
            log_dir,
        )
        assert result["ok"] is False
        assert result["reason"] == "log-dir-create-failed"
        records = ll.read(repo)["records"]
        refused = [r for r in records if r.get("event") == "refused"]
        assert any(
            r.get("launchId") == result["launchId"]
            and r.get("event") == "refused"
            and r.get("stage") == "log-dir"
            and r.get("reason") == "log-dir-create-failed"
            for r in refused
        )
    finally:
        readonly_parent.chmod(0o700)


def test_log_dir_create_failure_reason_distinct_from_log_open_failed(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "not-a-dir")
    with open(log_dir, "w", encoding="utf-8") as fh:
        fh.write("x")
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
    )
    assert result["reason"] == "log-dir-create-failed"
    assert result["reason"] != "log-open-failed"
    records = ll.read(repo)["records"]
    refused = [r for r in records if r.get("event") == "refused"]
    assert any(r.get("reason") == "log-dir-create-failed" for r in refused)
    assert not any(r.get("reason") == "log-open-failed" for r in refused)


def test_edge20_log_open_failure_terminalizes_reservation(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    real_open = open

    def fail_open(path, mode="r", *args, **kwargs):
        if "ab" in mode:
            raise OSError("permission denied")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", fail_open)
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
    )
    assert result["ok"] is False
    assert result["reason"] == "log-open-failed"
    records = ll.read(repo)["records"]
    refused = [r for r in records if r.get("event") == "refused"]
    assert any(r.get("stage") == "spawn" and r.get("reason") == "log-open-failed" for r in refused)
    assert not any(r.get("event") == "started" for r in records)


# --- C2 terminalization chokepoint (work order C2) ---------------------------

from test_launch_chokepoint_census import class2_census_violations  # noqa: E402


def test_c2_census_only_terminalize_writes_terminals():
    violations, launch_build_calls = class2_census_violations(_MOD)
    assert launch_build_calls == [], (
        "INVARIANT: exactly one function writes a terminal ledger event for a launch; "
        "launch_build must not call _record_park or _record_refused directly"
    )
    assert violations == {}, (
        "INVARIANT: exactly one function writes a terminal ledger event for a launch; "
        "violating functions: %s" % violations
    )


def test_c2_edge1_deadline_settle_reaps_before_park(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    order = []
    child_pid = {"pid": None}
    clock = {"monotonic": 1000.0}

    class _TimeShim:
        @staticmethod
        def monotonic():
            return clock["monotonic"]

        @staticmethod
        def time():
            return time.time()

        @staticmethod
        def sleep(seconds):
            pass

    monkeypatch.setattr(L, "time", _TimeShim)

    real_reap = ll._reap_process

    def tracking_reap(proc):
        order.append(("reap", proc.pid))
        real_reap(proc)

    monkeypatch.setattr(ll, "_reap_process", tracking_reap)

    real_append_raw = ll._append_raw
    terminal_tracked = {"n": 0}

    def tracking_append(repo_root, record, env=None):
        if record.get("event") == "outcome":
            terminal_tracked["n"] += 1
            order.append(("terminal", record.get("outcome")))
        return real_append_raw(repo_root, record, env=env)

    monkeypatch.setattr(ll, "_append_raw", tracking_append)

    def capture_spawn(argv, repo_root, out_fh, err_fh, child_env):
        proc = _make_spawn_fn("sleep")(argv, repo_root, out_fh, err_fh, child_env)
        child_pid["pid"] = proc.pid
        clock["monotonic"] += 10
        return proc

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=capture_spawn,
        settle_seconds=10,
        total_deadline_seconds=1,
    )
    assert result["ok"] is False
    assert child_pid["pid"] is not None
    with pytest.raises(ProcessLookupError):
        os.kill(child_pid["pid"], 0)
    reap_entries = [e for e in order if e[0] == "reap"]
    terminal_entries = [e for e in order if e[0] == "terminal"]
    assert reap_entries
    assert terminal_entries
    assert terminal_tracked["n"] >= 1
    assert order.index(reap_entries[0]) < order.index(terminal_entries[0])


def test_c2_edge2_deadline_before_spawn_refuses(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")

    def always_oserror(argv, repo_root, out_fh, err_fh, child_env):
        raise OSError("spawn failed")

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=always_oserror,
        max_attempts=5,
        backoff_seconds=(1,),
        total_deadline_seconds=0,
    )
    assert result["ok"] is False
    records = ll.read(repo)["records"]
    refused = [r for r in records if r.get("event") == "refused"]
    assert any(r.get("stage") == "retry-deadline-exceeded" for r in refused)
    assert not any(r.get("event") == "outcome" for r in records)


def test_c2_edge3_started_append_fail_parks_not_refuses(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    real_append = ll.append

    def failing_append(repo_root, record, env=None):
        if record.get("event") == "started" and not record.get("repaired"):
            return False
        return real_append(repo_root, record, env=env)

    monkeypatch.setattr(ll, "append", failing_append)
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.1,
    )
    assert result["ok"] is False
    records = ll.read(repo)["records"]
    parks = [r for r in records if r.get("event") == "outcome" and r.get("outcome") == "park"]
    refused = [r for r in records if r.get("event") == "refused"]
    assert len(parks) == 1
    assert refused == []
    assert ll.fold(records)["ok"] is True
    launch_records = [r for r in records if r.get("launchId") == result["launchId"]]
    events = [r["event"] for r in launch_records]
    assert events == ["reserved", "started", "outcome"]
    started_rec = [r for r in launch_records if r["event"] == "started"][0]
    assert started_rec.get("repaired") is True
    outcome_rec = [r for r in launch_records if r["event"] == "outcome"][0]
    assert outcome_rec.get("outcome") == "park"


def test_c2_edge4_terminal_append_failure_surfaces_reason(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")

    real_append_raw = ll._append_raw
    calls = {"n": 0}

    def fail_park_append(repo_root, record, env=None):
        if record.get("event") == "outcome" and record.get("outcome") == "park":
            calls["n"] += 1
            return False
        return real_append_raw(repo_root, record, env=env)

    monkeypatch.setattr(ll, "_append_raw", fail_park_append)
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=_make_spawn_fn("exit1"),
        settle_seconds=0.3,
    )
    assert result["ok"] is False
    assert result["reason"] == "terminalization-failed:ledger-append-failed"
    assert calls["n"] >= 1


def test_c2_edge5_oserror_retry_writes_retry_event(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    calls = {"n": 0}

    def oserror_then_sleep(argv, repo_root, out_fh, err_fh, child_env):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("spawn failed")
        return _make_spawn_fn("sleep")(argv, repo_root, out_fh, err_fh, child_env)

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=oserror_then_sleep,
        settle_seconds=0.2,
        backoff_seconds=(0,),
    )
    assert result["ok"] is True
    records = ll.read(repo)["records"]
    retries = [r for r in records if r.get("event") == "retry"]
    assert len(retries) == 1
    assert retries[0]["delaySeconds"] == 0
    assert ll.fold(records)["ok"] is True


def test_c2_edge6_retry_append_failure_terminalizes(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    real_append_under_lock = L._append_under_lock

    def fail_retry_append(repo_root, record, env=None):
        if record.get("event") == "retry":
            return {"ok": False, "reason": "ledger-append-failed"}
        return real_append_under_lock(repo_root, record, env=env)

    monkeypatch.setattr(L, "_append_under_lock", fail_retry_append)

    def always_oserror(argv, repo_root, out_fh, err_fh, child_env):
        raise OSError("spawn failed")

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=always_oserror,
        max_attempts=3,
        backoff_seconds=(0,),
    )
    assert result["ok"] is False
    assert result["reason"] == "ledger-append-failed"
    records = ll.read(repo)["records"]
    assert not any(r.get("event") == "started" for r in records)


def test_c2_edge7_final_oserror_refuses(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")

    def always_oserror(argv, repo_root, out_fh, err_fh, child_env):
        raise OSError("spawn failed")

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=always_oserror,
        max_attempts=1,
        backoff_seconds=(0,),
    )
    assert result["ok"] is False
    assert result["reason"] == "spawn-oserror-exhausted"
    records = ll.read(repo)["records"]
    assert any(r.get("event") == "refused" for r in records)
    assert not any(r.get("event") == "started" for r in records)


def test_c2_edge8_nonzero_exit_parks(tmp_path, monkeypatch):
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
        settle_seconds=0.3,
    )
    assert result["ok"] is False
    records = ll.read(repo)["records"]
    parks = [r for r in records if r.get("event") == "outcome" and r.get("outcome") == "park"]
    assert len(parks) == 1


def test_c2_edge9_zero_exit_parks(tmp_path, monkeypatch):
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
        settle_seconds=0.3,
    )
    assert result["ok"] is False
    records = ll.read(repo)["records"]
    parks = [r for r in records if r.get("event") == "outcome" and r.get("outcome") == "park"]
    assert len(parks) == 1
    assert parks[0]["evidence"] == "exit-zero"


def test_c2_edge10_child_alive_after_settle_no_terminal(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.3,
    )
    assert result["ok"] is True
    records = ll.read(repo)["records"]
    assert not any(r.get("event") == "outcome" for r in records)
    assert not any(r.get("event") == "refused" for r in records)
    try:
        os.kill(result["pid"], signal.SIGTERM)
    except ProcessLookupError:
        pass


def test_c2_edge11_backoff_clamped_to_deadline(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    clock = {"monotonic": 1000.0}
    slept_seconds = []

    class _TimeShim:
        @staticmethod
        def monotonic():
            return clock["monotonic"]

        @staticmethod
        def time():
            return time.time()

        @staticmethod
        def sleep(seconds):
            slept_seconds.append(seconds)
            clock["monotonic"] += seconds

    monkeypatch.setattr(L, "time", _TimeShim)

    def always_oserror(argv, repo_root, out_fh, err_fh, child_env):
        raise OSError("spawn failed")

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=always_oserror,
        max_attempts=3,
        backoff_seconds=(60,),
        total_deadline_seconds=1,
    )
    assert all(delay < 60 for delay in slept_seconds)
    assert sum(slept_seconds) <= 1
    assert result["ok"] is False
    assert result["reason"] == "retry-deadline-exceeded"


def test_c2_edge12_compose_issue_mismatch_refused(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    premise_path = tmp_path / "premise.json"
    _write_json(premise_path, _valid_premise(repo, issue=657))
    proc = subprocess.run(
        [
            sys.executable, _MOD, "compose",
            "--repo-root", repo, "--issue", "656", "--premise", str(premise_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["reason"] == "premise-issue-mismatch"


def test_c2_edge13_partial_log_open_closes_handle(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    open_handles = []
    real_open = open
    opens = {"n": 0}

    def tracking_open(path, mode="r", *args, **kwargs):
        fh = real_open(path, mode, *args, **kwargs)
        if "ab" in mode:
            opens["n"] += 1
            open_handles.append(fh)
            if opens["n"] == 2:
                fh.close()
                raise OSError("second log open failed")
        return fh

    monkeypatch.setattr("builtins.open", tracking_open)
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
    )
    assert result["ok"] is False
    assert result["reason"] == "log-open-failed"
    assert open_handles
    assert open_handles[0].closed


def test_c2_edge14_ledger_path_refused_fails_preflight(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")

    def refuse_path(repo_root, env=None):
        return {"ok": False, "path": None, "reason": "ledger-repo-dir-insecure"}

    monkeypatch.setattr(ll, "ledger_path", refuse_path)
    result = L.walk_preflight(_all_checks(), repo)
    assert result["ok"] is False
    assert result["reason"] == "preflight-ledger-unreadable"


def test_c2_edge15_census_detects_bypass_outside_terminalize():
    violations, launch_build_calls = class2_census_violations(_MOD)
    assert "launcher.py::_terminalize" not in violations
    assert "launcher.py::launch_build" not in violations


def test_append_under_lock_survives_a_raising_acquire(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        ll.file_lock, "acquire", lambda _path: (_ for _ in ()).throw(OSError("acquire failed")),
    )
    record = {
        "event": "reserved",
        "launchId": "l-oserror",
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "batchId": "b-oserror",
        "repoId": ll.repo_identity(repo) or "test",
        "issue": 656,
        "surfaces": ["a"],
        "premise": {},
        "preflight": {},
        "argv": [],
        "doctrineDigest": "abc",
        "model": "test",
    }
    result = L._append_under_lock(repo, record)
    assert result["ok"] is False
    assert result["reason"] == "lock-unavailable"


def test_spawn_attempt_exports_heartbeat_env_without_ledger_root(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    ledger_root = _ledger_env(tmp_path, monkeypatch)
    launch_id = "spawn-env-lane"
    ll.declare_batch(repo, "batch-spawn-env", 1)
    ll.append(repo, {
        "event": "reserved",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "batchId": "batch-spawn-env",
        "repoId": ll.repo_identity(repo),
        "issue": 656,
        "surfaces": ["plugins/superheroes/lib"],
        "premise": {},
        "preflight": {},
        "argv": [],
        "doctrineDigest": "abc",
        "model": "test",
    })
    captured = {}

    def capture_spawn(argv, repo_root, out_fh, err_fh, child_env):
        captured.update(child_env)
        class _Proc:
            pid = 424242

        out_fh.close()
        err_fh.close()
        return _Proc()

    log_dir = str(tmp_path / "logs")
    os.makedirs(log_dir)
    result = L._spawn_attempt(
        repo,
        launch_id,
        1,
        ["claude", "-p", "test"],
        os.path.join(log_dir, "out.log"),
        os.path.join(log_dir, "err.log"),
        900000,
        env={ll.LEDGER_ROOT_ENV: ledger_root},
        spawn_fn=capture_spawn,
    )
    assert result["ok"] is True
    assert captured.get(hb.LAUNCH_ID_ENV) == launch_id
    assert captured.get(hb.HEARTBEAT_ROOT_ENV) == ledger_root
    assert ll.LEDGER_ROOT_ENV not in captured


def test_append_under_lock_refuses_a_fifo_lock_without_blocking(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    ledger_root = _ledger_env(tmp_path, monkeypatch)
    repo_id = ll.repo_identity(repo)
    repo_dir = os.path.join(ledger_root, repo_id)
    os.makedirs(repo_dir, mode=0o700, exist_ok=True)
    fifo_lock = os.path.join(repo_dir, ll.LEDGER_NAME + ".lock")
    os.mkfifo(fifo_lock)
    record = {
        "event": "reserved",
        "launchId": "l-fifo",
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "batchId": "b-fifo",
        "repoId": repo_id,
        "issue": 656,
        "surfaces": ["a"],
        "premise": {},
        "preflight": {},
        "argv": [],
        "doctrineDigest": "abc",
        "model": "test",
    }
    start = time.monotonic()
    result = L._append_under_lock(repo, record)
    elapsed = time.monotonic() - start
    assert elapsed < 5.0, "_append_under_lock blocked on FIFO lock"
    assert result["ok"] is False
