import argparse
import importlib.util
import inspect
import json
import os
import shutil
import signal
import struct
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
import config_dir as cd  # noqa: E402
import engine_adapter as ea  # noqa: E402
import engine_dispatch as ed  # noqa: E402
import background_outcome as bo  # noqa: E402


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
_REAL_SEAT_CONFIG_DIR = L.seat_config_dir


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


_BG_ID = "feac172f"
_BG_SESSION = "feac172f-474c-424d-86e7-0e50688972c9"
_BG_TEST_STATE = {
    "session_pid": None,
    "row_state": "working",
    "listing_ok": True,
    "stop_result": "stopped",
    "agents_rows": None,
    "retire_calls": [],
    "acquire_calls": [],
}


def _bg_default_row(cwd, config_dir):
    pid = _BG_TEST_STATE["session_pid"] or 99999
    return {
        "pid": pid,
        "id": _BG_ID,
        "sessionId": _BG_SESSION,
        "state": _BG_TEST_STATE["row_state"],
        "kind": "background",
        "cwd": cwd,
    }


def _bg_acquire(config_dir, cwd, background_id=None, wait_seconds=None):
    _BG_TEST_STATE["acquire_calls"].append((config_dir, cwd, background_id, wait_seconds))
    if not _BG_TEST_STATE["listing_ok"]:
        return None, "agents-unreadable"
    if _BG_TEST_STATE["agents_rows"] is not None:
        rows = _BG_TEST_STATE["agents_rows"]
        if not rows:
            return None, "ended"
        live = [r for r in rows if r.get("state") not in ("stopped", "done")]
        if not live:
            return None, "ended"
        if len(live) > 1:
            return None, "ambiguous"
        row = live[0]
        pid = row.get("pid")
        if not isinstance(pid, int) or pid < 2:
            return None, "unlisted"
        return ed.BackgroundHandle(row["id"], pid, cwd, config_dir), "ok"
    pid = _BG_TEST_STATE["session_pid"]
    if pid is None:
        return None, "unlisted"
    if _BG_TEST_STATE["row_state"] in ("stopped", "done"):
        return None, "ended"
    return ed.BackgroundHandle(_BG_ID, pid, cwd, config_dir), "ok"


def _bg_retire(handle):
    _BG_TEST_STATE["retire_calls"].append(handle)
    return _BG_TEST_STATE["stop_result"]


def _bg_identity_row(config_dir, cwd, background_id):
    if not _BG_TEST_STATE["listing_ok"]:
        return None
    if _BG_TEST_STATE["agents_rows"] is not None:
        rows = ed.background_identity_rows(_BG_TEST_STATE["agents_rows"], cwd, background_id)
        return rows[0] if len(rows) == 1 else None
    if _BG_TEST_STATE["session_pid"] is None:
        return None
    if _BG_TEST_STATE["row_state"] in ("stopped", "done"):
        return None
    return _bg_default_row(cwd, config_dir)


@pytest.fixture(autouse=True)
def _autouse_background_dispatch_stubs(tmp_path, monkeypatch):
    _BG_TEST_STATE.update({
        "session_pid": None,
        "row_state": "working",
        "listing_ok": True,
        "stop_result": "stopped",
        "agents_rows": None,
        "retire_calls": [],
        "acquire_calls": [],
    })
    cfg = tmp_path / "claude-config"
    cfg.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv(cd.CONFIG_DIR_ENV, str(cfg))
    monkeypatch.setattr(ed, "acquire_background_handle", _bg_acquire)
    monkeypatch.setattr(ed, "retire", _bg_retire)
    monkeypatch.setattr(ed, "background_identity_row", _bg_identity_row)


@pytest.fixture(autouse=True)
def _autouse_seat_config_matches_spawn(monkeypatch):
    last_worktree = [None]
    orig_build_worktree_path = L.build_worktree_path

    def _tracking_build_worktree_path(repo_root, issue, launch_id, env=None):
        path = orig_build_worktree_path(repo_root, issue, launch_id, env=env)
        last_worktree[0] = path
        return path

    def _matching_seat(env=None):
        base = dict(env if env is not None else os.environ)
        requested = L.spawn_config_dir(env=base, cwd=last_worktree[0])
        if requested is not None:
            return {"instance": requested, "reason": None}
        return {"instance": None, "reason": "seat-pid-absent"}

    monkeypatch.setattr(L, "build_worktree_path", _tracking_build_worktree_path)
    monkeypatch.setattr(L, "seat_config_dir", _matching_seat)


def _ledger_env(tmp_path, monkeypatch):
    root = str(tmp_path / "ledger-root")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, root)
    return root


@pytest.fixture(autouse=True)
def _autouse_isolated_ledger_root(tmp_path, monkeypatch):
    _ledger_env(tmp_path, monkeypatch)


@pytest.fixture(autouse=True)
def _autouse_seat_config_matches_spawn(monkeypatch):
    # axis: deterministic gate — seat instance tracks spawn_config_dir the way launch_build does
    last_worktree = [None]
    orig_build_worktree_path = L.build_worktree_path

    def _tracking_build_worktree_path(repo_root, issue, launch_id, env=None):
        path = orig_build_worktree_path(repo_root, issue, launch_id, env=env)
        last_worktree[0] = path
        return path

    def _matching_seat(env=None):
        base = dict(env if env is not None else os.environ)
        requested = L.spawn_config_dir(env=base, cwd=last_worktree[0])
        if requested is not None:
            return {"instance": requested, "reason": None}
        return {"instance": None, "reason": "seat-pid-absent"}

    monkeypatch.setattr(L, "build_worktree_path", _tracking_build_worktree_path)
    monkeypatch.setattr(L, "seat_config_dir", _matching_seat)


@pytest.fixture
def unpatched_seat_config_dir(monkeypatch):
    monkeypatch.setattr(L, "seat_config_dir", _REAL_SEAT_CONFIG_DIR)


def _all_checks(**overrides):
    base = {
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


def _spawn_cwd(tmp_path):
    """A build-worktree stand-in: `_spawn_attempt` refuses a cwd that is the repo root."""
    path = tmp_path / "build-worktree"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


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
    "engine-auth", "base-state", "disjoint-surfaces",
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
    checks["engine-auth"] = {"state": "maybe", "reason": ""}
    result = L.walk_preflight(checks, repo)
    assert result["ok"] is False
    assert result["reason"] == "preflight-bad-state:engine-auth"


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
    checks["engine-auth"] = {"state": "na", "reason": "n/a"}
    result = L.walk_preflight(checks, repo)
    assert result["ok"] is False
    assert result["reason"] == "preflight-always-check-na:engine-auth"


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


def test_compose_await_dispatches_ruling_in_prompt(tmp_path):
  # axis: await-dispatches ruling text reaches the composed builder prompt
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo)
    result = L.compose_launch(repo, 656, premise)
    assert result["ok"] is True
    doctrine = LD.load()
    await_line = LD.ruling_line(doctrine, "await-dispatches")
    assert await_line in result["prompt"]


def test_compose_git_identity_ruling_in_prompt(tmp_path):
  # axis: git-identity ruling text reaches the composed builder prompt
  # compose_launch verifies only ruling zero is present, so nothing else asserts that this
  # ruling survives composition into the payload a launched builder actually receives.
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo)
    result = L.compose_launch(repo, 888, premise)
    assert result["ok"] is True
    doctrine = LD.load()
    identity_line = LD.ruling_line(doctrine, "git-identity")
    assert identity_line
    assert identity_line in result["prompt"]


def test_compose_gated_strings_ruling_in_prompt(tmp_path):
  # axis: gated-strings ruling text reaches the composed builder prompt
  # compose_launch verifies only ruling zero is present, so nothing else asserts that this
  # ruling survives composition into the payload a launched builder actually receives.
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo)
    result = L.compose_launch(repo, 889, premise)
    assert result["ok"] is True
    doctrine = LD.load()
    gated_line = LD.ruling_line(doctrine, "gated-strings")
    assert gated_line
    assert gated_line in result["prompt"]


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
    assert result["argv"][result["argv"].index("--model") + 1] == "opus"


def test_compose_argv_shape(tmp_path):
  # axis: composed argv matches engine_adapter builder argv
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo)
    result = L.compose_launch(repo, 656, premise, model="sonnet")
    assert result["ok"] is True
    expected = ea.claude_builder_argv("sonnet", result["effort"], result["prompt"])
    assert expected["reason"] is None
    assert result["argv"] == expected["argv"]
    assert "--bg" in result["argv"]
    assert "-p" not in result["argv"]
    assert "--session-id" not in result["argv"]
    assert "--restricted" not in result["argv"]
    assert result["argv"][-1] == result["prompt"]
    assert "sessionId" not in result


def test_compose_argv_carries_session_id(tmp_path):
  # axis: compose no longer mints sessionId (WO-B background argv)
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo)
    result = L.compose_launch(repo, 656, premise)
    assert result["ok"] is True
    assert "sessionId" not in result
    assert result["argv"] == ea.claude_builder_argv(
        result["model"], result["effort"], result["prompt"],
    )["argv"]


def test_compose_launch_mints_distinct_session_ids(tmp_path):
  # axis: compose no longer mints session ids (background launch)
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo)
    first = L.compose_launch(repo, 656, premise)
    second = L.compose_launch(repo, 656, premise)
    assert first["ok"] is True and second["ok"] is True
    assert "sessionId" not in first and "sessionId" not in second
    assert first["argv"] == second["argv"]


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
  # axis: unset builderDispatchTier resolves launch to opus default tier
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo)
    result = L.compose_launch(repo, 656, premise)
    assert result["ok"] is True
    assert "opus" in result["argv"]
    assert result["modelResolution"]["source"] == "default"


def test_compose_configured_sonnet_from_core_md(tmp_path):
  # axis: configured sonnet tier passes through compose_launch argv
    repo = _init_repo(tmp_path / "repo")
    _write_core_with_builder_tier(repo, {"builderDispatchTier": "sonnet"})
    premise = _valid_premise(repo)
    result = L.compose_launch(repo, 656, premise)
    assert result["ok"] is True
    assert "sonnet" in result["argv"]
    assert "opus" not in result["argv"]
    assert result["modelResolution"]["source"] == "configured"


def test_compose_configured_fable_falls_back_to_opus(tmp_path):
  # axis: configured fable tier refused — launch falls back to opus default
    repo = _init_repo(tmp_path / "repo")
    _write_core_with_builder_tier(repo, {"builderDispatchTier": "fable"})
    premise = _valid_premise(repo)
    result = L.compose_launch(repo, 656, premise)
    assert result["ok"] is True
    assert "opus" in result["argv"]
    assert "fable" not in result["argv"]
    assert result["modelResolution"]["source"] == "invalid-config-default"
    assert result["modelResolution"]["reason"] == "fable-never-a-launch-default"


def test_compose_unreadable_profile_defaults_to_opus(tmp_path):
  # axis: structurally ambiguous profile fail-closed to opus via real profile_structural_refusal path
    repo = _init_repo(tmp_path / "repo")
    _write_core_with_builder_tier(repo, {"builderDispatchTier": "sonnet"})
    import importlib.util as _u
    _lib = os.path.join(_HERE, "..")
    spec = _u.spec_from_file_location("core_md", os.path.join(_lib, "core_md.py"))
    cm = _u.module_from_spec(spec)
    spec.loader.exec_module(cm)
    core_path = os.path.join(repo, ".claude", "superheroes", "core.md")
    text = open(core_path, encoding="utf-8").read()
    extra = "\n```json superheroes-core\n{\"schemaVersion\": %d}\n```\n" % cm.SCHEMA_VERSION
    open(core_path, "w", encoding="utf-8").write(text + extra)
    premise = _valid_premise(repo)
    result = L.compose_launch(repo, 656, premise)
    assert result["ok"] is True
    assert "opus" in result["argv"]
    assert result["modelResolution"]["source"] == "unreadable-default"
    assert result["modelResolution"]["reason"].startswith("multiple-core-blocks:")
    assert result["modelResolution"]["tier"] == "opus"


def test_compose_unsanctioned_tier_falls_back_to_default(tmp_path, monkeypatch):
  # axis: stub supplies an input real config cannot produce; assertions pin _resolve_model's
  # unsanctioned-tier fallback — unlike C1 where the stub supplied the output under test
    repo = _init_repo(tmp_path / "repo")
    import engine_pref as ep

    def _unsanctioned(_cwd, root=None):
        return {
            "tier": "not-a-registry-tier",
            "source": "configured",
            "reason": None,
        }

    monkeypatch.setattr(ep, "load_builder_dispatch_tier", _unsanctioned)
    premise = _valid_premise(repo)
    result = L.compose_launch(repo, 656, premise)
    assert result["ok"] is True
    assert ep.BUILDER_DISPATCH_TIER_DEFAULT in result["argv"]
    assert result["modelResolution"]["source"] == "invalid-config-default"
    assert result["modelResolution"]["reason"] == "model-not-registry-known:not-a-registry-tier"


def test_compose_explicit_model_beats_configured_tier(tmp_path):
  # axis: explicit --model beats configured builderDispatchTier
    repo = _init_repo(tmp_path / "repo")
    _write_core_with_builder_tier(repo, {"builderDispatchTier": "haiku"})
    premise = _valid_premise(repo)
    result = L.compose_launch(repo, 656, premise, model="sonnet")
    assert result["ok"] is True
    assert "sonnet" in result["argv"]
    assert result["modelResolution"]["source"] == "explicit"


def test_compose_model_fable_refuses(tmp_path):
  # axis: explicit fable model refused — not registry-known for launch
    repo = _init_repo(tmp_path / "repo")
    premise = _valid_premise(repo)
    result = L.compose_launch(repo, 656, premise, model="fable")
    assert result["ok"] is False
    assert result["reason"] == "model-not-registry-known"


def test_launch_build_reserved_carries_model_source(tmp_path, monkeypatch):
  # axis: reserved ledger row carries model + modelResolution source from compose
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
  # axis: preflight refusal leaves modelSource and modelReason empty on reserved row
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


def _bg_unit_spawn(captured=None, *, ack_rc=0, write_id=True, session_pid=88888):
    """Minimal ack proc for direct _spawn_attempt unit tests."""

    class _AckProc:
        pid = 424240

        def poll(self):
            return ack_rc if ack_rc != 0 else 0

        def wait(self, timeout=None):
            return ack_rc if ack_rc != 0 else 0

    def spawn(argv, cwd, out_fh, err_fh, child_env):
        if captured is not None:
            captured.update(child_env)
        if write_id:
            out_fh.write(b"backgrounded \xc2\xb7 feac172f\n")
            out_fh.flush()
        _BG_TEST_STATE["session_pid"] = session_pid
        out_fh.close()
        err_fh.close()
        return _AckProc()

    return spawn


def _make_spawn_fn(behavior):
    def spawn(argv, cwd, out_fh, err_fh, child_env):
        env = dict(child_env)
        if behavior == "sleep":
            session = subprocess.Popen(
                [sys.executable, "-c", _standin_script("sleep")],
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
                env=env,
            )
            _BG_TEST_STATE["session_pid"] = session.pid
        elif behavior in ("exit0", "exit1"):
            session = subprocess.Popen(
                [sys.executable, "-c", _standin_script(behavior)],
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
                env=env,
            )
            _BG_TEST_STATE["session_pid"] = session.pid
        marker = b"backgrounded \xc2\xb7 feac172f\n"
        out_fh.write(marker)
        out_fh.flush()
        if behavior == "exit1":
            ack_script = "import sys; sys.exit(1)"
        elif behavior == "hang":
            ack_script = "import time; time.sleep(120)"
        else:
            ack_script = "pass"
        return subprocess.Popen(
            [sys.executable, "-c", ack_script],
            cwd=cwd,
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
        order.append(("after_spawn", _BG_TEST_STATE["session_pid"]))
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
    assert started[0]["pid"] == result["pid"]
    assert started[0]["launchMode"] == ll.LAUNCH_MODE_BACKGROUND


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
    pid = _BG_TEST_STATE["session_pid"]
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


# --- effort pinning at the spawn point (#1156) --------------------------------


def _capturing_spawn(captured, behavior="sleep"):
    """Spawn stand-in that records the child env the launcher actually composed."""
    def spawn(argv, cwd, out_fh, err_fh, child_env):
        captured.append(dict(child_env))
        return _make_spawn_fn(behavior)(argv, cwd, out_fh, err_fh, child_env)
    return spawn


def _reap(result):
    try:
        os.kill(result["pid"], signal.SIGTERM)
    except (ProcessLookupError, KeyError, TypeError):
        pass


def test_opus_child_effort_pinned_medium_over_ambient_high(tmp_path, monkeypatch):
  # axis: resolved opus tier pins the effort input to medium in the child even when the launching
  # env carries high — the inheritance accident #1156 closes
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.setenv(L.EFFORT_ENV, "high")
    captured = []
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_capturing_spawn(captured),
        settle_seconds=0.3,
    )
    assert result["ok"] is True
    assert result["model"] == "opus"
    assert len(captured) == 1
    assert captured[0][L.EFFORT_ENV] == "medium"
    assert result["effort"] == "medium"
    assert result["effortSource"] == "opus-policy"
    _reap(result)


def test_pinned_effort_uses_the_documented_cli_input_variable(tmp_path, monkeypatch):
  # axis: the pin lands on the variable the CLI actually READS. Every other test in this
  # family spells the key as `L.EFFORT_ENV`, which stays green under ANY name the constant
  # happens to hold — including the CLAUDE_EFFORT this branch first shipped, which the CLI
  # overwrites with its own resolution (a live four-arm probe: injecting CLAUDE_EFFORT=medium
  # produced a child that resolved `high`). This test names the documented input as a LITERAL,
  # so a rename of the constant cannot keep it passing. It is the red-on-old proof.
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_CODE_EFFORT_LEVEL", "high")
    captured = []
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_capturing_spawn(captured),
        settle_seconds=0.3,
    )
    assert result["ok"] is True
    assert result["model"] == "opus"
    assert captured[0]["CLAUDE_CODE_EFFORT_LEVEL"] == "medium"
    _reap(result)


def test_pinned_child_drops_the_stale_effort_reflection(tmp_path, monkeypatch):
  # axis: CLAUDE_EFFORT is the CLI's own OUTPUT, not an input. Letting the launching session's
  # stale value ride into a pinned child would leave a forged observable that reads exactly
  # like a receipt — the placebo shape vet 178 caught — so the pin drops it and lets the child's
  # own reflection be the honest evidence of what the CLI resolved.
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_EFFORT", "high")
    captured = []
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_capturing_spawn(captured),
        settle_seconds=0.3,
    )
    assert result["ok"] is True
    assert result["model"] == "opus"
    assert captured[0]["CLAUDE_CODE_EFFORT_LEVEL"] == "medium"
    assert "CLAUDE_EFFORT" not in captured[0]
    _reap(result)


def test_inherit_case_touches_neither_effort_variable(tmp_path, monkeypatch):
  # axis: boundary, both variables at once — the ruling names Opus 5 only, so a non-opus child
  # inherits the documented input AND keeps the reflection the pin would otherwise have dropped.
  # Pins the literals so the boundary cannot drift with the constant.
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_EFFORT", "high")
    monkeypatch.setenv("CLAUDE_CODE_EFFORT_LEVEL", "high")
    captured = []
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        model="sonnet",
        spawn_fn=_capturing_spawn(captured),
        settle_seconds=0.3,
    )
    assert result["ok"] is True
    assert result["model"] == "sonnet"
    assert captured[0]["CLAUDE_CODE_EFFORT_LEVEL"] == "high"
    assert captured[0]["CLAUDE_EFFORT"] == "high"
    assert result["effortSource"] == "inherited"
    _reap(result)


def test_reserved_row_carries_opus_effort_provenance(tmp_path, monkeypatch):
  # axis: the ledger records what effort a lane ran at and why, beside the model resolution
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.setenv(L.EFFORT_ENV, "high")
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.3,
    )
    assert result["ok"] is True
    reserved = [r for r in ll.read(repo)["records"] if r.get("event") == "reserved"][0]
    assert reserved["model"] == "opus"
    assert reserved["modelSource"] == "default"
    assert reserved["effort"] == "medium"
    assert reserved["effortSource"] == "opus-policy"
    _reap(result)


def test_explicit_effort_overrides_opus_default_and_is_recorded(tmp_path, monkeypatch):
  # axis: --effort is the deliberate exception — it beats the opus default and lands in the ledger
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.setenv(L.EFFORT_ENV, "high")
    captured = []
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_capturing_spawn(captured),
        settle_seconds=0.3,
        effort="xhigh",
    )
    assert result["ok"] is True
    assert result["model"] == "opus"
    assert captured[0][L.EFFORT_ENV] == "xhigh"
    assert result["effortSource"] == "explicit"
    reserved = [r for r in ll.read(repo)["records"] if r.get("event") == "reserved"][0]
    assert reserved["effort"] == "xhigh"
    assert reserved["effortSource"] == "explicit"
    _reap(result)


def test_explicit_effort_applies_to_a_non_opus_tier(tmp_path, monkeypatch):
  # axis: an explicit effort is an instruction, not an opus-only default — it pins any tier
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.setenv(L.EFFORT_ENV, "high")
    captured = []
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        model="sonnet",
        spawn_fn=_capturing_spawn(captured),
        settle_seconds=0.3,
        effort="low",
    )
    assert result["ok"] is True
    assert result["model"] == "sonnet"
    assert captured[0][L.EFFORT_ENV] == "low"
    assert result["effortSource"] == "explicit"
    _reap(result)


def test_non_opus_tier_keeps_ambient_effort(tmp_path, monkeypatch):
  # axis: boundary — the ruling names Opus 5 only, so a sonnet child still inherits
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.setenv(L.EFFORT_ENV, "high")
    captured = []
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        model="sonnet",
        spawn_fn=_capturing_spawn(captured),
        settle_seconds=0.3,
    )
    assert result["ok"] is True
    assert result["model"] == "sonnet"
    assert captured[0][L.EFFORT_ENV] == "high"
    assert result["effort"] is None
    assert result["effortSource"] == "inherited"
    reserved = [r for r in ll.read(repo)["records"] if r.get("event") == "reserved"][0]
    assert reserved["effort"] == ""
    assert reserved["effortSource"] == "inherited"
    _reap(result)


def test_non_opus_tier_without_ambient_effort_sets_nothing(tmp_path, monkeypatch):
  # axis: the inherit case invents no value — an unset effort input stays unset
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.delenv(L.EFFORT_ENV, raising=False)
    captured = []
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        model="sonnet",
        spawn_fn=_capturing_spawn(captured),
        settle_seconds=0.3,
    )
    assert result["ok"] is True
    assert L.EFFORT_ENV not in captured[0]
    _reap(result)


def test_compose_cli_effort_flag_reaches_the_resolver(tmp_path):
  # axis: --effort is wired through the real parser, not just the function signature
    repo = _init_repo(tmp_path / "repo")
    premise_path = tmp_path / "premise.json"
    _write_json(premise_path, _valid_premise(repo))
    base = [
        sys.executable, _MOD, "compose",
        "--repo-root", repo, "--issue", "656", "--premise", str(premise_path),
    ]
    default = json.loads(subprocess.run(
        base, capture_output=True, text=True, check=False,
    ).stdout)
    assert default["ok"] is True
    assert default["effort"] == "medium"
    assert default["effortSource"] == "opus-policy"

    pinned = json.loads(subprocess.run(
        base + ["--effort", "low"], capture_output=True, text=True, check=False,
    ).stdout)
    assert pinned["ok"] is True
    assert pinned["effort"] == "low"
    assert pinned["effortSource"] == "explicit"

    bad = json.loads(subprocess.run(
        base + ["--effort", "turbo"], capture_output=True, text=True, check=False,
    ).stdout)
    assert bad["ok"] is False
    assert bad["reason"] == "effort-not-registry-known"


def test_opus_policy_effort_is_gated_by_the_registry_too(tmp_path, monkeypatch):
  # axis: the policy default goes through the same registry gate as an explicit --effort,
  # so a registry that stopped accepting `medium` refuses before spawn instead of falling open
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setattr(L.model_registry, "effort_enum", lambda vendor: ("low", "high"))
    result = L.compose_launch(repo, 656, _valid_premise(repo))
    assert result["ok"] is False
    assert result["reason"] == "effort-not-registry-known"


def test_non_opus_tier_resolves_without_consulting_the_effort_enum(tmp_path, monkeypatch):
  # axis: the inherit case pins no value, so a narrowed enum cannot refuse a sonnet launch
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setattr(L.model_registry, "effort_enum", lambda vendor: ())
    result = L.compose_launch(repo, 656, _valid_premise(repo), model="sonnet")
    assert result["ok"] is True
    assert result["effort"] is None
    assert result["effortSource"] == "inherited"


def test_compose_unknown_effort_refuses(tmp_path):
  # axis: the effort vocabulary comes from the registry, not from the caller
    repo = _init_repo(tmp_path / "repo")
    result = L.compose_launch(repo, 656, _valid_premise(repo), effort="turbo")
    assert result["ok"] is False
    assert result["reason"] == "effort-not-registry-known"


def test_launch_build_unknown_effort_refuses_before_any_spawn(tmp_path, monkeypatch):
  # axis: an unrunnable effort is a pre-spawn refusal, never a child launched at a guess
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)

    def never_spawn(argv, cwd, out_fh, err_fh, child_env):
        raise AssertionError("spawned despite an unknown effort")

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=never_spawn,
        effort="turbo",
    )
    assert result["ok"] is False
    assert result["reason"] == "effort-not-registry-known"
    records = ll.read(repo)["records"]
    assert not [r for r in records if r.get("event") == "started"]
    # The refusal is accounted, not merely aborted: it reserves and then terminalizes at the
    # same stage its model-resolution sibling uses, so a reader sees why the lane never ran.
    assert len([r for r in records if r.get("event") == "reserved"]) == 1
    refused = [r for r in records if r.get("event") == "refused"]
    assert len(refused) == 1
    assert refused[0]["stage"] == "model"
    assert refused[0]["reason"] == "effort-not-registry-known"


def test_opus_effort_pin_survives_a_spawn_retry(tmp_path, monkeypatch):
  # axis: the pin rides every attempt — a retried spawn is still an opus child at medium
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.setenv(L.EFFORT_ENV, "high")
    captured = []
    calls = {"n": 0}

    def oserror_then_capture(argv, cwd, out_fh, err_fh, child_env):
        calls["n"] += 1
        captured.append(dict(child_env))
        if calls["n"] == 1:
            raise OSError("spawn failed")
        return _make_spawn_fn("sleep")(argv, cwd, out_fh, err_fh, child_env)

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=oserror_then_capture,
        settle_seconds=0.3,
        backoff_seconds=(0,),
    )
    assert result["ok"] is True
    assert result["model"] == "opus"
    assert calls["n"] == 2
    assert [env[L.EFFORT_ENV] for env in captured] == ["medium", "medium"]
    _reap(result)


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
    assert result["reason"] == bo.REFUSAL_LAUNCH_FAILED
    assert calls["n"] == 1
    records = ll.read(repo)["records"]
    parks = [r for r in records if r.get("event") == "outcome" and r.get("outcome") == "park"]
    assert len(parks) == 1
    assert parks[0]["evidence"] == bo.REFUSAL_LAUNCH_FAILED
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
    assert result["reason"] == bo.REFUSAL_LAUNCH_FAILED
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
    assert result["reason"] == bo.REFUSAL_SESSION_ENDED_WITHOUT_RESULT
    parks = [
        r for r in ll.read(repo)["records"]
        if r.get("event") == "outcome" and r.get("outcome") == "park"
    ]
    assert len(parks) == 1
    assert parks[0]["evidence"] == bo.REFUSAL_SESSION_ENDED_WITHOUT_RESULT


def test_spawn_oserror_retries_then_succeeds(tmp_path, monkeypatch):
  # axis: OSError is the only retryable spawn failure
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    calls = {"n": 0}
    spawn_argv = []

    def oserror_then_sleep(argv, repo_root, out_fh, err_fh, child_env):
        calls["n"] += 1
        spawn_argv.append(list(argv))
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
    assert len(spawn_argv) == 2
    assert spawn_argv[0] == spawn_argv[1]
    assert "--bg" in spawn_argv[0]
    assert "--session-id" not in spawn_argv[0]
    records = ll.read(repo)["records"]
    reserved = [r for r in records if r.get("event") == "reserved"][0]
    assert "sessionId" not in reserved
    assert "--session-id" not in reserved["argv"]
    retries = [r for r in records if r.get("event") == "retry"]
    assert len(retries) == 1
    assert retries[0]["attempt"] == 1
    assert retries[0]["reason"] == "spawn-oserror"


def test_launch_build_reserved_session_id_matches_spawn_argv(tmp_path, monkeypatch):
  # axis: reserved argv matches spawned background argv; no compose sessionId
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    spawn_argv = []

    def capture_spawn(argv, cwd, out_fh, err_fh, child_env):
        spawn_argv.append(list(argv))
        return _make_spawn_fn("sleep")(argv, cwd, out_fh, err_fh, child_env)

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=capture_spawn,
        settle_seconds=0.2,
    )
    assert result["ok"] is True
    records = ll.read(repo)["records"]
    reserved = [r for r in records if r.get("event") == "reserved"][0]
    assert reserved["argv"] == spawn_argv[0]
    assert "--bg" in reserved["argv"]
    assert "sessionId" not in reserved
    assert result["sessionId"] == _BG_SESSION
    assert result["backgroundId"] == _BG_ID
    _reap(result)


def test_launch_build_reserved_config_dir_matches_the_child_env(tmp_path, monkeypatch):
  # axis: reserved record configDir equals the CLAUDE_CONFIG_DIR the child was spawned with
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    other_instance = str(tmp_path / "claude-two")
    os.makedirs(other_instance, exist_ok=True)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", other_instance)
    spawned_envs = []

    def capture_spawn(argv, repo_root, out_fh, err_fh, child_env):
        spawned_envs.append(dict(child_env))
        return _make_spawn_fn("sleep")(argv, repo_root, out_fh, err_fh, child_env)

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=capture_spawn,
        settle_seconds=0.2,
    )
    assert result["ok"] is True
    assert len(spawned_envs) == 1
    reserved = [
        r for r in ll.read(repo)["records"] if r.get("event") == "reserved"
    ][0]
    # The recorded root is not a second, independent guess at where the transcript
    # lands — it is the root the child actually inherited.
    assert reserved["configDir"] == spawned_envs[0]["CLAUDE_CONFIG_DIR"]
    assert reserved["configDir"] == other_instance
    try:
        os.kill(result["pid"], signal.SIGTERM)
    except ProcessLookupError:
        pass


def test_launch_build_records_the_default_config_root_when_unset(tmp_path, monkeypatch):
  # axis: no override — the recorded root is the one the child's own HOME resolves to
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    log_dir = str(tmp_path / "logs")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setenv("HOME", str(home))
    os.makedirs(home / ".claude", exist_ok=True)

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.2,
    )
    assert result["ok"] is True
    reserved = [
        r for r in ll.read(repo)["records"] if r.get("event") == "reserved"
    ][0]
    assert reserved["configDir"] == os.path.join(str(home), ".claude")
    try:
        os.kill(result["pid"], signal.SIGTERM)
    except ProcessLookupError:
        pass


def test_relative_config_dir_override_records_the_childs_effective_root(
    tmp_path, monkeypatch,
):
  # axis: a relative override resolves against the CHILD's cwd — the build worktree — so
  # the recorded root is where the transcript actually lands, not an omission and not the
  # launcher's own cwd
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "relative/config")

    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.2,
    )
    assert result["ok"] is True, result
    reserved = [
        r for r in ll.read(repo)["records"] if r.get("event") == "reserved"
    ][0]
    assert reserved["configDir"] == os.path.join(
        reserved["worktree"], "relative", "config",
    )
    # And the recorded value is one the grammar accepts, not one that refuses the launch.
    assert ll.fold(ll.read(repo)["records"])["ok"] is True
    try:
        os.kill(result["pid"], signal.SIGTERM)
    except ProcessLookupError:
        pass


def _config_dir_reporting_spawn(report_path):
    """A real spawn that makes the CHILD report the CLAUDE_CONFIG_DIR it actually sees.

    The receipt is the child's own ``os.environ`` read, written from inside the spawned
    process. Asserting against the env dict the launcher assembled proves only what we
    handed ``Popen``; it cannot prove the pin survived the spawn into a child. `#1246`'s
    DoD asks for the real spawn path, so these tests read the value back out of a process
    that genuinely started.
    """
    script = (
        "import os, time\n"
        "open(%r, 'w').write(os.environ.get('CLAUDE_CONFIG_DIR', '<unset>'))\n"
        "time.sleep(60)\n" % report_path
    )

    def spawn(argv, cwd, out_fh, err_fh, child_env):
        return subprocess.Popen(
            [sys.executable, "-c", script],
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=out_fh,
            stderr=err_fh,
            start_new_session=True,
            close_fds=True,
            env=child_env,
        )

    return spawn


def _await_child_report(report_path, timeout=10.0):
    """Read the child's report, waiting for the process it came from to write it."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(report_path):
            reported = open(report_path).read()
            if reported:
                return reported
        time.sleep(0.05)
    raise AssertionError("child never reported CLAUDE_CONFIG_DIR at %s" % report_path)


def test_spawned_child_receives_the_config_dir_default_in_its_environment(
    tmp_path, monkeypatch,
):
  # axis: #1246 — with no CLAUDE_CONFIG_DIR to inherit, the child STILL gets one. This is
  # the auth-death class: an unpinned child dies "OAuth session expired", an error that
  # reads as broken auth and is really an unset variable. Read back from the child's own
  # environment through the real spawn path, and checked against the recorded configDir.
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setenv("HOME", str(home))
    report = str(tmp_path / "child-config-dir.txt")

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_config_dir_reporting_spawn(report),
        settle_seconds=0.2,
    )
    assert result["ok"] is True, result
    reserved = [
        r for r in ll.read(repo)["records"] if r.get("event") == "reserved"
    ][0]
    reported = _await_child_report(report)
    assert reported == os.path.join(str(home), ".claude")
    # The record is not a second guess at the child's root — it is that root.
    assert reported == reserved["configDir"]
    try:
        os.kill(result["pid"], signal.SIGTERM)
    except ProcessLookupError:
        pass


def test_spawned_child_config_dir_pin_never_overrides_a_deliberate_export(
    tmp_path, monkeypatch,
):
  # axis: #1246 — a caller who DID export CLAUDE_CONFIG_DIR chose that instance on purpose
  # (a second Claude install, a sandboxed profile). The pin supplies a default; silently
  # overriding a deliberate export would send the lane's transcript somewhere the caller
  # is not watching.
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    other_instance = str(tmp_path / "claude-two")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", other_instance)
    report = str(tmp_path / "child-config-dir.txt")

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_config_dir_reporting_spawn(report),
        settle_seconds=0.2,
    )
    assert result["ok"] is True, result
    reserved = [
        r for r in ll.read(repo)["records"] if r.get("event") == "reserved"
    ][0]
    reported = _await_child_report(report)
    assert reported == other_instance
    assert reported != os.path.join(str(tmp_path / "home"), ".claude")
    assert reported == reserved["configDir"]
    try:
        os.kill(result["pid"], signal.SIGTERM)
    except ProcessLookupError:
        pass


def test_spawned_child_config_dir_pin_agrees_with_the_record_on_a_padded_export(
    tmp_path, monkeypatch,
):
  # axis: #1246 review round 1 — an export carrying edge whitespace. `spawn_config_dir`
  # strips before resolving, and the reserved record has carried that stripped form since
  # #1036 — so handing the child the RAW padded value is precisely the record/child
  # divergence #1036 exists to prevent: the watcher would search the stripped root while
  # the child wrote to the padded one. The pin deliberately gives the child the same
  # stripped root the record names, and this test is what stops a later "preserve the
  # caller's exact bytes" change from silently reopening that divergence.
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    intended = str(tmp_path / "claude-padded")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", intended + "  ")
    report = str(tmp_path / "child-config-dir.txt")

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_config_dir_reporting_spawn(report),
        settle_seconds=0.2,
    )
    assert result["ok"] is True, result
    reserved = [
        r for r in ll.read(repo)["records"] if r.get("event") == "reserved"
    ][0]
    reported = _await_child_report(report)
    # Still the caller's directory — the padding is normalized, the choice is not overridden.
    assert reported == intended
    assert reported == reserved["configDir"]
    try:
        os.kill(result["pid"], signal.SIGTERM)
    except ProcessLookupError:
        pass


def test_spawned_child_config_dir_pin_resolves_a_relative_export(tmp_path, monkeypatch):
  # axis: #1246 x #1036 — a relative export is handed to the child already resolved against
  # the build worktree it runs in. Same directory the child would have reached on its own,
  # and byte-identical to the recorded value, so the watcher and the child agree.
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "relative/config")
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    report = str(tmp_path / "child-config-dir.txt")

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_config_dir_reporting_spawn(report),
        settle_seconds=0.2,
    )
    assert result["ok"] is True, result
    reserved = [
        r for r in ll.read(repo)["records"] if r.get("event") == "reserved"
    ][0]
    reported = _await_child_report(report)
    assert reported == os.path.join(reserved["worktree"], "relative", "config")
    assert os.path.isabs(reported)
    assert reported == reserved["configDir"]
    try:
        os.kill(result["pid"], signal.SIGTERM)
    except ProcessLookupError:
        pass


def test_spawn_config_dir_expands_home_in_the_override(monkeypatch, tmp_path):
  # axis: `~/.claude-two` is a real-world override shape and must record absolute
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "~/.claude-two")
    assert L.spawn_config_dir() == os.path.join(str(tmp_path / "home"), ".claude-two")


def test_spawn_config_dir_expands_the_supplied_env_home_not_the_ambient_one(monkeypatch):
  # axis: the child inherits the SUPPLIED env, so `~` must expand through THAT HOME.
  # Expanding through the launcher's ambient HOME records a root the child never writes to
  # — the watcher then searches the wrong root and alerts a working lane.
    monkeypatch.setenv("HOME", "/ambient-home")
    supplied = {"HOME": "/lane-home", "CLAUDE_CONFIG_DIR": "~/.claude-two"}
    assert L.spawn_config_dir(env=supplied) == "/lane-home/.claude-two"


def test_spawn_config_dir_resolves_a_relative_override_against_the_child_cwd(monkeypatch):
  # axis: the child inherits the RAW relative value and resolves it against its own cwd
  # (the build worktree), so that is the root the transcript actually lands under
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "relative/config")
    assert L.spawn_config_dir(cwd="/build/wt") == "/build/wt/relative/config"
    # No cwd to resolve against — omit rather than guess the launcher's own cwd.
    assert L.spawn_config_dir() is None
    assert L.spawn_config_dir(cwd="not-absolute") is None


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


def test_cli_record_outcome_amendment_exits_nonzero(tmp_path, monkeypatch):
    # axis: amendment record-outcome exits non-zero while ok:true
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    launch_id = "launch-amend-exit"
    ll.reserve(repo, {
        "event": "reserved",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "batchId": "batch-amend-exit",
        "repoId": ll.repo_identity(repo),
        "issue": 656,
        "surfaces": ["a"],
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
        [
            sys.executable, _MOD, "record-outcome",
            "--repo-root", repo,
            "--launch-id", launch_id,
            "--outcome", "handback",
            "--evidence", "retry",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["recorded"] == "amendment"


def test_cli_record_outcome_amendment_existing_exits_nonzero(tmp_path, monkeypatch):
    # axis: amendment-existing retry exits non-zero
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    launch_id = "launch-amend-existing"
    ll.reserve(repo, {
        "event": "reserved",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "batchId": "batch-amend-existing",
        "repoId": ll.repo_identity(repo),
        "issue": 656,
        "surfaces": ["a"],
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
    ll.record_outcome(repo, launch_id, "handback", "retry")
    proc = subprocess.run(
        [
            sys.executable, _MOD, "record-outcome",
            "--repo-root", repo,
            "--launch-id", launch_id,
            "--outcome", "handback",
            "--evidence", "retry",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["recorded"] == "amendment-existing"


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


def _ledger_bytes(repo):
    path = ll.ledger_path(repo)["path"]
    if not os.path.isfile(path):
        return b""
    with open(path, "rb") as fh:
        return fh.read()


def test_edge2_declare_batch_idempotent_equal_second_resolves(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    batch = "dup-batch"
    first = L.declare_batch(repo, batch, 1)
    after_first = _ledger_bytes(repo)
    second = L.declare_batch(repo, batch, 1)
    assert first["ok"] is True
    assert second["ok"] is True
    assert second.get("idempotent") is True
    assert _ledger_bytes(repo) == after_first
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
    assert ll.record_outcome(repo, launch_id, "handback", "done")["ok"]
    count = L.count_batch(repo, batch)
    assert count["indeterminate"] is False
    assert count["resolved"] is True
    assert count["counts"]["total"] == 1
    assert count["counts"]["handback"] == 1


def test_edge2_declare_batch_conflicting_second_refused(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    batch = "conflict-batch"
    assert L.declare_batch(repo, batch, 1)["ok"] is True
    before = _ledger_bytes(repo)
    second = L.declare_batch(repo, batch, 2)
    assert second["ok"] is False
    assert second["reason"] == "batch-declaration-conflict:1:2"
    assert "idempotent" not in second
    assert _ledger_bytes(repo) == before


def test_edge2_declare_batch_cli_conflicting_second_refused(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    batch = "cli-conflict-batch"
    assert L.declare_batch(repo, batch, 1)["ok"] is True
    proc = subprocess.run(
        [
            sys.executable, _MOD, "declare-batch",
            "--repo-root", repo, "--batch", batch, "--expected", "2",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["reason"] == "batch-declaration-conflict:1:2"
    assert "idempotent" not in payload


def test_edge2_declare_batch_duplicate_record_count_indeterminate(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    batch = "dup-record-batch"
    assert L.declare_batch(repo, batch, 1)["ok"] is True
    # Models corruption or a pre-fix ledger rather than a supported call.
    ll.append(repo, {
        "event": "batch-declared",
        "batchId": batch,
        "expectedLaunches": 1,
        "ts": time.time(),
        "schema": ll.SCHEMA,
    })
    launch_id = "launch-dup-rec"
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
    assert parks[0]["evidence"] == bo.REFUSAL_LAUNCH_FAILED
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
    assert parks[0]["evidence"] == bo.REFUSAL_SESSION_ENDED_WITHOUT_RESULT
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
        settle_seconds=60,
        total_deadline_seconds=15,
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
    checks_path.write_text('{"engine-auth": {"state": "pass", "reason": ""}, "engine-auth": {"state": "fail", "reason": "x"}}')
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
    assert parks[0]["evidence"] == bo.REFUSAL_SESSION_ENDED_WITHOUT_RESULT


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

    capture_spawn = _bg_unit_spawn(captured)

    log_dir = str(tmp_path / "logs")
    os.makedirs(log_dir)
    result = L._spawn_attempt(
        repo,
        launch_id,
        1,
        ["claude", "--bg", "test"],
        os.path.join(log_dir, "out.log"),
        os.path.join(log_dir, "err.log"),
        900000,
        env={ll.LEDGER_ROOT_ENV: ledger_root},
        spawn_fn=capture_spawn,
        cwd=_spawn_cwd(tmp_path),
    )
    assert result["ok"] is True
    assert captured.get(hb.LAUNCH_ID_ENV) == launch_id
    assert captured.get(hb.HEARTBEAT_ROOT_ENV) == ledger_root
    assert ll.LEDGER_ROOT_ENV not in captured
    assert L.SLOT_REF_ENV not in captured


def test_spawn_attempt_exports_slot_ref_when_supplied(tmp_path, monkeypatch):
    # axis: slot reference exported only when both slot and generation supplied
    repo = _init_repo(tmp_path / "repo")
    ledger_root = _ledger_env(tmp_path, monkeypatch)
    launch_id = "launch-slot-ref"
    ll.reserve(repo, {
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

    capture_spawn = _bg_unit_spawn(captured)

    log_dir = str(tmp_path / "logs")
    os.makedirs(log_dir)
    result = L._spawn_attempt(
        repo,
        launch_id,
        1,
        ["claude", "--bg", "test"],
        os.path.join(log_dir, "out.log"),
        os.path.join(log_dir, "err.log"),
        900000,
        env={ll.LEDGER_ROOT_ENV: ledger_root},
        spawn_fn=capture_spawn,
        cwd=_spawn_cwd(tmp_path),
        slot="slot-a",
        generation=1,
    )
    assert result["ok"] is True
    assert captured.get(L.SLOT_REF_ENV) == "slot-a@1"


def test_spawn_attempt_omits_slot_ref_without_generation(tmp_path, monkeypatch):
    # axis: slot without generation does not export SUPERHEROES_SLOT_REF
    repo = _init_repo(tmp_path / "repo")
    ledger_root = _ledger_env(tmp_path, monkeypatch)
    launch_id = "launch-slot-only"
    captured = {}

    capture_spawn = _bg_unit_spawn(captured)

    log_dir = str(tmp_path / "logs")
    os.makedirs(log_dir)
    result = L._spawn_attempt(
        repo,
        launch_id,
        1,
        ["claude", "--bg", "test"],
        os.path.join(log_dir, "out.log"),
        os.path.join(log_dir, "err.log"),
        900000,
        env={ll.LEDGER_ROOT_ENV: ledger_root},
        spawn_fn=capture_spawn,
        cwd=_spawn_cwd(tmp_path),
        slot="slot-a",
        generation=None,
    )
    assert L.SLOT_REF_ENV not in captured


def test_spawn_attempt_strips_inherited_slot_ref_when_unslotted(tmp_path, monkeypatch):
    # axis: unslotted spawn must not inherit SUPERHEROES_SLOT_REF from caller env
    repo = _init_repo(tmp_path / "repo")
    ledger_root = _ledger_env(tmp_path, monkeypatch)
    launch_id = "launch-strip-inherited"
    ll.declare_batch(repo, "batch-strip-inherited", 1)
    ll.append(repo, {
        "event": "reserved",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "batchId": "batch-strip-inherited",
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

    capture_spawn = _bg_unit_spawn(captured)

    log_dir = str(tmp_path / "logs")
    os.makedirs(log_dir)
    stale_ref = "old-slot@3"
    result = L._spawn_attempt(
        repo,
        launch_id,
        1,
        ["claude", "--bg", "test"],
        os.path.join(log_dir, "out.log"),
        os.path.join(log_dir, "err.log"),
        900000,
        env={ll.LEDGER_ROOT_ENV: ledger_root, L.SLOT_REF_ENV: stale_ref},
        spawn_fn=capture_spawn,
        cwd=_spawn_cwd(tmp_path),
    )
    assert result["ok"] is True
    assert L.SLOT_REF_ENV not in captured


def test_spawn_attempt_replaces_inherited_slot_ref_when_slotted(tmp_path, monkeypatch):
    # axis: slotted spawn exports formatted ref, not inherited stale value
    repo = _init_repo(tmp_path / "repo")
    ledger_root = _ledger_env(tmp_path, monkeypatch)
    launch_id = "launch-replace-inherited"
    ll.reserve(repo, {
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

    capture_spawn = _bg_unit_spawn(captured)

    log_dir = str(tmp_path / "logs")
    os.makedirs(log_dir)
    stale_ref = "old-slot@3"
    result = L._spawn_attempt(
        repo,
        launch_id,
        1,
        ["claude", "--bg", "test"],
        os.path.join(log_dir, "out.log"),
        os.path.join(log_dir, "err.log"),
        900000,
        env={ll.LEDGER_ROOT_ENV: ledger_root, L.SLOT_REF_ENV: stale_ref},
        spawn_fn=capture_spawn,
        cwd=_spawn_cwd(tmp_path),
        slot="slot-a",
        generation=1,
    )
    assert result["ok"] is True
    assert captured.get(L.SLOT_REF_ENV) == "slot-a@1"


def test_spawn_attempt_strips_slot_ref_from_process_env_when_unslotted(
    tmp_path, monkeypatch,
):
    # axis: env=None inherits os.environ but must still strip SUPERHEROES_SLOT_REF
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.setenv(L.SLOT_REF_ENV, "old-slot@3")
    launch_id = "launch-strip-process-env"
    ll.declare_batch(repo, "batch-strip-process", 1)
    ll.append(repo, {
        "event": "reserved",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "batchId": "batch-strip-process",
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

    capture_spawn = _bg_unit_spawn(captured)

    log_dir = str(tmp_path / "logs")
    os.makedirs(log_dir)
    result = L._spawn_attempt(
        repo,
        launch_id,
        1,
        ["claude", "--bg", "test"],
        os.path.join(log_dir, "out.log"),
        os.path.join(log_dir, "err.log"),
        900000,
        env=None,
        spawn_fn=capture_spawn,
        cwd=_spawn_cwd(tmp_path),
    )
    assert result["ok"] is True
    assert L.SLOT_REF_ENV not in captured


def test_spawn_attempt_strips_empty_string_slot_ref_when_unslotted(tmp_path, monkeypatch):
    # axis: empty SUPERHEROES_SLOT_REF in caller env must not reach child
    repo = _init_repo(tmp_path / "repo")
    ledger_root = _ledger_env(tmp_path, monkeypatch)
    launch_id = "launch-strip-empty-ref"
    ll.declare_batch(repo, "batch-strip-empty", 1)
    ll.append(repo, {
        "event": "reserved",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "batchId": "batch-strip-empty",
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

    capture_spawn = _bg_unit_spawn(captured)

    log_dir = str(tmp_path / "logs")
    os.makedirs(log_dir)
    result = L._spawn_attempt(
        repo,
        launch_id,
        1,
        ["claude", "--bg", "test"],
        os.path.join(log_dir, "out.log"),
        os.path.join(log_dir, "err.log"),
        900000,
        env={ll.LEDGER_ROOT_ENV: ledger_root, L.SLOT_REF_ENV: ""},
        spawn_fn=capture_spawn,
        cwd=_spawn_cwd(tmp_path),
    )
    assert result["ok"] is True
    assert L.SLOT_REF_ENV not in captured


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


# --- WO-864 amend CLI --------------------------------------------------------


def test_cli_amend_happy_path(tmp_path, monkeypatch):
    # axis: amend CLI happy path
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    launch_id = "launch-cli-amend"
    batch = "batch-cli"
    ll.declare_batch(repo, batch, 1)
    ll.reserve(repo, {
        "event": "reserved",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "batchId": batch,
        "repoId": ll.repo_identity(repo),
        "issue": 656,
        "surfaces": ["a"],
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
        [
            sys.executable, _MOD, "amend",
            "--repo-root", repo,
            "--launch-id", launch_id,
            "--kind", "vet",
            "--value", "ready",
            "--note", "advisor ok",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["kind"] == "vet"
    assert payload["value"] == "ready"


def test_cli_amend_kind_not_caller_writable(tmp_path, monkeypatch):
    # axis: amend-kind-not-caller-writable
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    proc = subprocess.run(
        [
            sys.executable, _MOD, "amend",
            "--repo-root", repo,
            "--launch-id", "any",
            "--kind", "reoutcome",
            "--value", "handback",
            "--note", "not allowed",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["reason"] == "amend-kind-not-caller-writable:reoutcome"


# --- slot + generation + boundary CLI (issue #830) --------------------------

def _launch_cli_args(repo, tmp_path, **extra):
    checks_path = tmp_path / "checks.json"
    premise_path = tmp_path / "premise.json"
    log_dir = tmp_path / "logs"
    _write_json(checks_path, _all_checks())
    _write_json(premise_path, _valid_premise(repo))
    args = [
        sys.executable, _MOD, "launch",
        "--repo-root", repo,
        "--issue", "656",
        "--premise", str(premise_path),
        "--checks", str(checks_path),
        "--log-dir", str(log_dir),
    ]
    for key, value in extra.items():
        flag = "--" + key.replace("_", "-")
        args.extend([flag, str(value)])
    return args


def test_launch_build_writes_slot_fields_on_reserved(tmp_path, monkeypatch):
    # axis: launch_build writes slot fields on reserved record
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    boundary = {
        "slotRef": "slot-a@1",
        "result": "pass",
        "provenance": "observed",
        "strength": "strong",
        "match": True,
        "policyDigest": "digest123",
        "verifiedAt": "2026-01-01T00:00:00Z",
        "weakerAccepted": False,
        "acceptedBy": None,
        "acceptedAt": None,
        "acceptanceReason": None,
    }
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.1,
        slot="slot-a",
        generation=1,
        boundary=boundary,
    )
    assert result["ok"] is True
    records = ll.read(repo)["records"]
    reserved = [r for r in records if r.get("event") == "reserved"][0]
    assert reserved["slot"] == "slot-a"
    assert reserved["generation"] == 1
    assert reserved["boundary"] == boundary
    try:
        os.kill(result["pid"], signal.SIGTERM)
    except ProcessLookupError:
        pass


def test_launch_build_without_slot_fields_has_no_keys(tmp_path, monkeypatch):
    # axis: launch_build without slot fields omits keys entirely
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.1,
    )
    assert result["ok"] is True
    reserved = [r for r in ll.read(repo)["records"] if r.get("event") == "reserved"][0]
    assert "slot" not in reserved
    assert "generation" not in reserved
    assert "boundary" not in reserved
    try:
        os.kill(result["pid"], signal.SIGTERM)
    except ProcessLookupError:
        pass


def test_launch_refusal_path_records_slot(tmp_path, monkeypatch):
    # axis: refusal path still records slot on reserved row
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    checks = _all_checks()
    checks["engine-auth"] = {"state": "fail", "reason": "no auth"}
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        checks,
        str(tmp_path / "logs"),
        slot="slot-a",
        generation=1,
    )
    assert result["ok"] is False
    reserved = [r for r in ll.read(repo)["records"] if r.get("event") == "reserved"][0]
    assert reserved["slot"] == "slot-a"
    assert reserved["generation"] == 1


def test_cli_launch_boundary_without_slot_generation(tmp_path):
    # axis: CLI refuses --boundary without --slot and --generation
    repo = _init_repo(tmp_path / "repo")
    boundary_path = tmp_path / "boundary.json"
    _write_json(boundary_path, {"slotRef": "slot-a@1"})
    proc = subprocess.run(
        _launch_cli_args(repo, tmp_path, boundary=boundary_path),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["reason"] == "launch-boundary-without-slot-generation"


def test_cli_launch_boundary_unreadable(tmp_path):
    # axis: CLI refuses unreadable --boundary file
    repo = _init_repo(tmp_path / "repo")
    boundary_path = tmp_path / "boundary.json"
    boundary_path.write_text("not json", encoding="utf-8")
    proc = subprocess.run(
        _launch_cli_args(
            repo, tmp_path,
            slot="slot-a", generation=1, boundary=boundary_path,
        ),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["reason"] == "launch-boundary-unreadable"


def test_cli_launch_boundary_not_object(tmp_path):
    # axis: CLI refuses --boundary JSON that is not an object
    repo = _init_repo(tmp_path / "repo")
    boundary_path = tmp_path / "boundary.json"
    _write_json(boundary_path, [1, 2, 3])
    proc = subprocess.run(
        _launch_cli_args(
            repo, tmp_path,
            slot="slot-a", generation=1, boundary=boundary_path,
        ),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["reason"] == "launch-boundary-unreadable"


def test_cli_launch_generation_zero_refused_by_fold(tmp_path, monkeypatch):
    # axis: --generation 0 accepted by argparse but refused by validate_generation
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    child_env = os.environ.copy()
    child_env.pop("CLAUDE_PID", None)
    proc = subprocess.run(
        _launch_cli_args(repo, tmp_path, slot="slot-a", generation=0),
        capture_output=True,
        text=True,
        check=False,
        env=child_env,
    )
    assert proc.returncode != 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["reason"] == "fold-bad-field:reserved:generation"


def test_cli_launch_boundary_happy_path_forwards(tmp_path, monkeypatch):
    # axis: CLI parses --boundary and forwards it to launch_build
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    boundary = {
        "slotRef": "slot-a@1",
        "result": "pass",
        "provenance": "observed",
        "strength": "strong",
        "match": True,
        "policyDigest": "digest123",
        "verifiedAt": "2026-01-01T00:00:00Z",
        "weakerAccepted": False,
        "acceptedBy": None,
        "acceptedAt": None,
        "acceptanceReason": None,
    }
    boundary_path = tmp_path / "boundary.json"
    _write_json(boundary_path, boundary)
    checks_path = tmp_path / "checks.json"
    premise_path = tmp_path / "premise.json"
    log_dir = tmp_path / "logs"
    _write_json(checks_path, _all_checks())
    _write_json(premise_path, _valid_premise(repo))
    forwarded = {}

    def capture_launch_build(*args, **kwargs):
        forwarded.update(kwargs)
        return {"ok": False, "reason": "injected-stop", "launchId": "l-test"}

    monkeypatch.setattr(L, "launch_build", capture_launch_build)
    args = argparse.Namespace(
        repo_root=repo,
        issue=656,
        checks=str(checks_path),
        premise=str(premise_path),
        log_dir=str(log_dir),
        model=None,
        effort=None,
        slot="slot-a",
        generation=1,
        boundary=str(boundary_path),
        allow_foreign_instance=False,
    )
    result = L._cli_launch(args)
    assert result["reason"] == "injected-stop"
    assert forwarded.get("boundary") == boundary
    assert forwarded.get("slot") == "slot-a"
    assert forwarded.get("generation") == 1


# --- slot reservation gate (issue #909) --------------------------------------


def _slot_calibrated(monkeypatch):
    monkeypatch.setattr(
        L.pilot_calibration,
        "declares_slots",
        lambda repo_root: {
            "state": L.pilot_calibration.STATE_DECLARED,
            "cause": L.pilot_calibration.CAUSE_DECLARED,
            "path": None,
        },
    )


def _not_slot_calibrated(monkeypatch):
    monkeypatch.setattr(
        L.pilot_calibration,
        "declares_slots",
        lambda repo_root: {
            "state": L.pilot_calibration.STATE_ABSENT,
            "cause": L.pilot_calibration.CAUSE_NO_CALIBRATION,
            "path": None,
        },
    )


def _reserve_live_lane(repo, batch_id, launch_id, slot=None, generation=None, surfaces=None):
    rec = {
        "event": "reserved",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "batchId": batch_id,
        "repoId": ll.repo_identity(repo),
        "issue": 656,
        "surfaces": surfaces or ["plugins/superheroes/lib/other"],
        "premise": {},
        "preflight": {},
        "argv": [],
        "doctrineDigest": "d",
        "model": "m",
    }
    if slot is not None:
        rec["slot"] = slot
    if generation is not None:
        rec["generation"] = generation
    ll.reserve(repo, rec)


def test_slot_gate_parallel_unslotted_refuses(tmp_path, monkeypatch):
  # axis: slot-calibrated + parallel declared + no slot refuses
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _slot_calibrated(monkeypatch)
    ll.declare_batch(repo, "wave-test", 2)
    result = L.walk_preflight(_all_checks(), repo, batch_id="wave-test")
    assert result["ok"] is False
    assert result["reason"] == "preflight-slot-reservation-required"
    assert result["missing"] == ["this-launch"]
    assert "--slot" in result["remedy"]
    assert "--generation" in result["remedy"]


def test_slot_gate_parallel_slotted_passes(tmp_path, monkeypatch):
  # axis: slot-calibrated + parallel + slot/generation passes
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _slot_calibrated(monkeypatch)
    ll.declare_batch(repo, "wave-test", 2)
    result = L.walk_preflight(
        _all_checks(),
        repo,
        batch_id="wave-test",
        slot="slot-a",
        generation=1,
    )
    assert result["ok"] is True


def test_slot_gate_single_lane_unslotted_passes(tmp_path, monkeypatch):
  # axis: slot-calibrated + single-lane + no slot passes
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _slot_calibrated(monkeypatch)
    ll.declare_batch(repo, "wave-test", 1)
    result = L.walk_preflight(_all_checks(), repo, batch_id="wave-test")
    assert result["ok"] is True


def test_slot_gate_non_pilot_parallel_passes(tmp_path, monkeypatch):
  # axis: non-pilot + parallel + no slot passes
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _not_slot_calibrated(monkeypatch)
    ll.declare_batch(repo, "wave-test", 2)
    result = L.walk_preflight(_all_checks(), repo, batch_id="wave-test")
    assert result["ok"] is True


def test_slot_gate_parallel_by_live_lane(tmp_path, monkeypatch):
  # axis: parallel by live lane without declaration refuses
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _slot_calibrated(monkeypatch)
    _reserve_live_lane(repo, "wave-test", "live-1", slot="slot-a", generation=1)
    result = L.walk_preflight(_all_checks(), repo, batch_id="wave-test")
    assert result["ok"] is False
    assert result["reason"] == "preflight-slot-reservation-required"


def test_slot_gate_unslotted_sibling_refuses(tmp_path, monkeypatch):
  # axis: slotted launch refuses when unslotted sibling in same batch
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _slot_calibrated(monkeypatch)
    ll.declare_batch(repo, "wave-test", 2)
    _reserve_live_lane(repo, "wave-test", "sibling-unslotted")
    result = L.walk_preflight(
        _all_checks(),
        repo,
        batch_id="wave-test",
        slot="slot-a",
        generation=1,
    )
    assert result["ok"] is False
    assert result["reason"] == "preflight-slot-reservation-required"
    assert "sibling-unslotted" in result["missing"]
    assert "this-launch" not in result["missing"]


def test_slot_gate_different_batch_unslotted_passes(tmp_path, monkeypatch):
  # axis: unslotted lane in different batch does not make this launch parallel
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _slot_calibrated(monkeypatch)
    _reserve_live_lane(repo, "other-batch", "other-live")
    result = L.walk_preflight(_all_checks(), repo, batch_id="wave-test")
    assert result["ok"] is True


def test_slot_gate_different_batch_unslotted_not_in_missing(tmp_path, monkeypatch):
  # axis: a live unslotted lane in a DIFFERENT batch never enters `missing` for this batch
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _slot_calibrated(monkeypatch)
    ll.declare_batch(repo, "wave-x", 2)
    _reserve_live_lane(repo, "other-wave", "other-lane")
    result = L.walk_preflight(
        _all_checks(), repo, batch_id="wave-x", slot="slot-a", generation=1,
    )
    assert result["ok"] is True


def test_launch_build_slot_refusal_propagates_missing_and_remedy(tmp_path, monkeypatch):
  # axis: launch_build propagates missing and remedy on slot refusal
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _slot_calibrated(monkeypatch)
    ll.declare_batch(repo, "wave-test", 2)
    log_dir = str(tmp_path / "logs")
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
    )
    assert result["ok"] is False
    assert result["reason"] == "preflight-slot-reservation-required"
    assert result["missing"] == ["this-launch"]
    assert "--slot" in result["remedy"]
    assert "--generation" in result["remedy"]


def test_cli_preflight_slot_reservation_refusal(tmp_path, monkeypatch):
  # axis: CLI preflight reproduces launch slot refusal with --batch
    import io
    from contextlib import redirect_stdout

    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _slot_calibrated(monkeypatch)
    ll.declare_batch(repo, "wave-test", 2)
    checks_path = tmp_path / "checks.json"
    _write_json(checks_path, _all_checks())
    buf = io.StringIO()
    with redirect_stdout(buf):
        exit_code = L.main([
            "preflight",
            "--repo-root", repo,
            "--checks", str(checks_path),
            "--batch", "wave-test",
        ])
    assert exit_code == 1
    payload = json.loads(buf.getvalue())
    assert payload["reason"] == "preflight-slot-reservation-required"


def test_launch_build_post_reserve_slot_recheck_refuses(tmp_path, monkeypatch):
  # axis: post-reserve re-check refuses without spawning when batch became parallel
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _slot_calibrated(monkeypatch)
    log_dir = str(tmp_path / "logs")
    spawn_called = False

    def tracking_spawn(argv, repo_root, out_fh, err_fh, child_env):
        nonlocal spawn_called
        spawn_called = True
        return _make_spawn_fn("sleep")(argv, repo_root, out_fh, err_fh, child_env)

    real_compose = L.compose_launch

    def compose_then_sibling(*args, **kwargs):
        sibling = {
            "event": "reserved",
            "launchId": "race-sibling",
            "ts": time.time(),
            "schema": ll.SCHEMA,
            "batchId": "wave-test",
            "repoId": ll.repo_identity(repo),
            # A genuine sibling LANE, not a duplicate of this launch's own issue: since
            # #1054 a second live launch for one issue is refused at reserve, which would
            # short-circuit the post-reserve slot re-check this test is about.
            "issue": 657,
            "surfaces": ["other/path"],
            "premise": {},
            "preflight": {},
            "argv": [],
            "doctrineDigest": "d",
            "model": "m",
        }
        ll.reserve(repo, sibling)
        return real_compose(*args, **kwargs)

    monkeypatch.setattr(L, "compose_launch", compose_then_sibling)
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=tracking_spawn,
    )
    assert result["ok"] is False
    assert result["reason"] == "preflight-slot-reservation-required"
    assert spawn_called is False
    records = ll.read(repo)["records"]
    refused = [
        r for r in records
        if r.get("event") == "refused" and r.get("launchId") != "race-sibling"
    ]
    assert len(refused) == 1


def test_slot_gate_disjoint_surfaces_na_parallel_unslotted_refuses(tmp_path, monkeypatch):
  # axis: slot-calibrated + declared-parallel + disjoint-surfaces na + no slot refuses
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _slot_calibrated(monkeypatch)
    ll.declare_batch(repo, "wave-na", 2)
    checks = _all_checks(**{
        "disjoint-surfaces": {"state": "na", "reason": "first lane of the wave"},
    })
    result = L.walk_preflight(checks, repo, batch_id="wave-na")
    assert result["ok"] is False
    assert result["reason"] == "preflight-slot-reservation-required"
    assert result["missing"] == ["this-launch"]


def test_slot_gate_disjoint_surfaces_na_non_pilot_parallel_passes(tmp_path, monkeypatch):
  # axis: non-pilot + declared-parallel + disjoint-surfaces na passes
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _not_slot_calibrated(monkeypatch)
    ll.declare_batch(repo, "wave-na", 2)
    checks = _all_checks(**{
        "disjoint-surfaces": {"state": "na", "reason": "first lane of the wave"},
    })
    result = L.walk_preflight(checks, repo, batch_id="wave-na")
    assert result["ok"] is True


def test_launch_build_single_lane_unslotted_spawns(tmp_path, monkeypatch):
  # axis: exclude_launch_id lets single-lane unslotted launch spawn on slot-calibrated project
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _slot_calibrated(monkeypatch)
    ll.declare_batch(repo, "wave-test", 1)
    log_dir = str(tmp_path / "logs")
    spawn_called = False

    def tracking_spawn(argv, repo_root, out_fh, err_fh, child_env):
        nonlocal spawn_called
        spawn_called = True
        return _make_spawn_fn("sleep")(argv, repo_root, out_fh, err_fh, child_env)

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
    assert spawn_called is True


def test_launch_build_post_reserve_unreadable_ledger_refuses(tmp_path, monkeypatch):
  # axis: unreadable ledger at post-reserve re-check refuses without spawning
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _slot_calibrated(monkeypatch)
    log_dir = str(tmp_path / "logs")
    spawn_called = False
    real_live_state = L._ledger_live_state
    calls = {"n": 0}

    def unreadable_on_recheck(repo_root, env=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return real_live_state(repo_root, env=env)
        return {
            "ok": False,
            "reason": "ledger-corrupt",
            "live": [],
            "unreadable": True,
            "unavailable": False,
            "detail": {},
            "allDetail": {},
            "declarations": {},
        }

    monkeypatch.setattr(L, "_ledger_live_state", unreadable_on_recheck)

    def tracking_spawn(argv, repo_root, out_fh, err_fh, child_env):
        nonlocal spawn_called
        spawn_called = True
        return _make_spawn_fn("sleep")(argv, repo_root, out_fh, err_fh, child_env)

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=tracking_spawn,
    )
    assert result["ok"] is False
    assert result["reason"] == "post-reserve-ledger-unreadable"
    assert spawn_called is False
    records = ll.read(repo)["records"]
    refused = [r for r in records if r.get("event") == "refused"]
    assert len(refused) == 1
    assert refused[0]["reason"] == "post-reserve-ledger-unreadable"


def test_launch_build_unslotted_lane_refuses_after_slotted_sibling_refused(tmp_path, monkeypatch):
  # axis: post-reserve parallel counts terminal reservations — unslotted lane must not spawn
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _slot_calibrated(monkeypatch)
    log_dir = str(tmp_path / "logs")
    _reserve_live_lane(repo, "wave-test", "lane-a", slot="slot-a", generation=1)
    L._terminalize(
        repo,
        "lane-a",
        False,
        "preflight-slot-reservation-required",
        stage="preflight",
    )
    spawn_called = False

    def tracking_spawn(argv, repo_root, out_fh, err_fh, child_env):
        nonlocal spawn_called
        spawn_called = True
        return _make_spawn_fn("sleep")(argv, repo_root, out_fh, err_fh, child_env)

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=tracking_spawn,
    )
    assert result["ok"] is False
    assert result["reason"] == "preflight-slot-reservation-required"
    assert spawn_called is False


def _terminalize_handback_lane(repo, batch_id, launch_id, slot=None, generation=None):
    _reserve_live_lane(repo, batch_id, launch_id, slot=slot, generation=generation)
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


def test_launch_build_single_lane_unslotted_spawns_after_handback_terminal(tmp_path, monkeypatch):
  # axis: unrelated terminal lane does not count toward post-reserve parallelism
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _slot_calibrated(monkeypatch)
    ll.declare_batch(repo, "wave-test", 1)
    _terminalize_handback_lane(repo, "wave-test", "lane-prior")
    log_dir = str(tmp_path / "logs")
    spawn_called = False

    def tracking_spawn(argv, repo_root, out_fh, err_fh, child_env):
        nonlocal spawn_called
        spawn_called = True
        return _make_spawn_fn("sleep")(argv, repo_root, out_fh, err_fh, child_env)

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
    assert spawn_called is True


def test_launch_build_single_lane_unslotted_spawns_after_post_reserve_unreadable_terminal(
    tmp_path, monkeypatch,
):
  # axis: post-reserve-ledger-unreadable terminal does not count toward parallelism
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _slot_calibrated(monkeypatch)
    ll.declare_batch(repo, "wave-test", 1)
    _reserve_live_lane(repo, "wave-test", "lane-prior")
    L._terminalize(
        repo,
        "lane-prior",
        False,
        "post-reserve-ledger-unreadable",
        stage="preflight",
    )
    log_dir = str(tmp_path / "logs")
    spawn_called = False

    def tracking_spawn(argv, repo_root, out_fh, err_fh, child_env):
        nonlocal spawn_called
        spawn_called = True
        return _make_spawn_fn("sleep")(argv, repo_root, out_fh, err_fh, child_env)

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
    assert spawn_called is True


def test_preflight_and_launch_agree_after_handback_terminal(tmp_path, monkeypatch):
  # axis: preflight and launch agree when unrelated terminal lane is in batch
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _slot_calibrated(monkeypatch)
    ll.declare_batch(repo, "wave-test", 1)
    _terminalize_handback_lane(repo, "wave-test", "lane-prior")
    checks = _all_checks()
    preflight = L.walk_preflight(checks, repo, batch_id="wave-test")
    assert preflight["ok"] is True
    log_dir = str(tmp_path / "logs")
    spawn_called = False

    def tracking_spawn(argv, repo_root, out_fh, err_fh, child_env):
        nonlocal spawn_called
        spawn_called = True
        return _make_spawn_fn("sleep")(argv, repo_root, out_fh, err_fh, child_env)

    launch = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        checks,
        log_dir,
        spawn_fn=tracking_spawn,
        settle_seconds=0.3,
    )
    assert launch["ok"] is True
    assert spawn_called is True


def _unknown_calibration(monkeypatch, path="/fake/profile.md", cause="calibration-unreadable"):
    monkeypatch.setattr(
        L.pilot_calibration,
        "declares_slots",
        lambda repo_root: {
            "state": L.pilot_calibration.STATE_CANNOT_TELL,
            "cause": cause,
            "path": path,
        },
    )


def test_slot_gate_unknown_calibration_parallel_refuses(tmp_path, monkeypatch):
  # axis: unknown calibration + parallel refuses
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _unknown_calibration(monkeypatch)
    ll.declare_batch(repo, "wave-test", 2)
    result = L.walk_preflight(_all_checks(), repo, batch_id="wave-test")
    assert result["ok"] is False
    assert result["reason"] == "preflight-slot-calibration-unreadable"


def test_slot_gate_no_calibration_parallel_passes(tmp_path, monkeypatch):
  # axis: no calibration at all + parallel still passes
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _not_slot_calibrated(monkeypatch)
    ll.declare_batch(repo, "wave-test", 2)
    result = L.walk_preflight(_all_checks(), repo, batch_id="wave-test")
    assert result["ok"] is True


def test_launch_build_parallel_slotted_spawns(tmp_path, monkeypatch):
  # axis: slot-calibrated + declared-parallel + slot/generation spawns at launch_build
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _slot_calibrated(monkeypatch)
    ll.declare_batch(repo, "wave-test", 2)
    log_dir = str(tmp_path / "logs")
    spawn_called = False

    def tracking_spawn(argv, repo_root, out_fh, err_fh, child_env):
        nonlocal spawn_called
        spawn_called = True
        return _make_spawn_fn("sleep")(argv, repo_root, out_fh, err_fh, child_env)

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
        spawn_fn=tracking_spawn,
        settle_seconds=0.3,
        slot="slot-a",
        generation=1,
    )
    assert result["ok"] is True
    assert spawn_called is True


def test_cli_preflight_slot_generation_forwards(tmp_path, monkeypatch):
  # axis: CLI preflight forwards --slot and --generation on declared-parallel batch
    import io
    from contextlib import redirect_stdout

    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _slot_calibrated(monkeypatch)
    ll.declare_batch(repo, "wave-test", 2)
    checks_path = tmp_path / "checks.json"
    _write_json(checks_path, _all_checks())
    buf = io.StringIO()
    with redirect_stdout(buf):
        exit_code = L.main([
            "preflight",
            "--repo-root", repo,
            "--checks", str(checks_path),
            "--batch", "wave-test",
            "--slot", "slot-a",
            "--generation", "1",
        ])
    assert exit_code == 0
    payload = json.loads(buf.getvalue())
    assert payload["ok"] is True


def test_slot_gate_unknown_calibration_parallel_refusal_path_and_remedy(
    tmp_path, monkeypatch,
):
  # axis: calibration-unreadable refusal carries profile path and regeneration remedy
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    profile_path = "/fake/pilot-calibration.md"
    _unknown_calibration(monkeypatch, path=profile_path)
    ll.declare_batch(repo, "wave-test", 2)
    result = L.walk_preflight(_all_checks(), repo, batch_id="wave-test")
    assert result["ok"] is False
    assert result["reason"] == "preflight-slot-calibration-unreadable"
    assert result["path"] == profile_path
    remedy = result["remedy"]
    assert "profile" in remedy.lower() or "calibration" in remedy.lower()
    assert "regenerat" in remedy.lower() or "fix" in remedy.lower()
    assert "missing" not in remedy.lower()


def test_slot_gate_resolver_failed_parallel_refuses(tmp_path, monkeypatch):
  # axis: resolver-failed cannot-tell + parallel refuses with cause in payload
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _unknown_calibration(
        monkeypatch,
        path="/fake/pilot-calibration.md",
        cause=L.pilot_calibration.CAUSE_RESOLVER_FAILED,
    )
    ll.declare_batch(repo, "wave-test", 2)
    result = L.walk_preflight(_all_checks(), repo, batch_id="wave-test")
    assert result["ok"] is False
    assert result["reason"] == "preflight-slot-calibration-unreadable"
    assert result["path"] == "/fake/pilot-calibration.md"
    assert result["cause"] == L.pilot_calibration.CAUSE_RESOLVER_FAILED


def test_slot_gate_absent_cause_parallel_passes(tmp_path, monkeypatch):
  # axis: absent cause on parallel unreserved launch passes (non-pilot project untouched)
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        L.pilot_calibration,
        "declares_slots",
        lambda repo_root: {
            "state": L.pilot_calibration.STATE_ABSENT,
            "cause": L.pilot_calibration.CAUSE_NO_PILOT_BLOCK,
            "path": "/fake/profile.md",
        },
    )
    ll.declare_batch(repo, "wave-test", 2)
    result = L.walk_preflight(_all_checks(), repo, batch_id="wave-test")
    assert result["ok"] is True


def test_slot_gate_unrecognized_cause_parallel_refuses(tmp_path, monkeypatch):
  # axis: unrecognized cause fails closed with calibration-unreadable refusal
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        L.pilot_calibration,
        "declares_slots",
        lambda repo_root: {
            "state": L.pilot_calibration.STATE_CANNOT_TELL,
            "cause": "future-unknown-cause",
            "path": "/fake/profile.md",
        },
    )
    ll.declare_batch(repo, "wave-test", 2)
    result = L.walk_preflight(_all_checks(), repo, batch_id="wave-test")
    assert result["ok"] is False
    assert result["reason"] == "preflight-slot-calibration-unreadable"
    assert result["cause"] == "future-unknown-cause"


def test_launch_build_slot_refusal_does_not_carry_cause(tmp_path, monkeypatch):
  # axis: slot reservation refusal omits cause (not a calibration-unreadable refusal)
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _slot_calibrated(monkeypatch)
    ll.declare_batch(repo, "wave-test", 2)
    log_dir = str(tmp_path / "logs")
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
    )
    assert result["ok"] is False
    assert result["reason"] == "preflight-slot-reservation-required"
    assert "cause" not in result


def test_launch_build_calibration_unreadable_propagates_cause(tmp_path, monkeypatch):
  # axis: launch_build propagates cause on calibration-unreadable refusal
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    profile_path = "/fake/pilot-calibration.md"
    _unknown_calibration(
        monkeypatch,
        path=profile_path,
        cause=L.pilot_calibration.CAUSE_RESOLVER_FAILED,
    )
    ll.declare_batch(repo, "wave-test", 2)
    log_dir = str(tmp_path / "logs")
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        log_dir,
    )
    assert result["ok"] is False
    assert result["reason"] == "preflight-slot-calibration-unreadable"
    assert result["cause"] == L.pilot_calibration.CAUSE_RESOLVER_FAILED
    assert result["path"] == profile_path
    assert result["remedy"]


# --- slot calibration policy census (issue #909 K2) -------------------------


_SLOT_CALIBRATION_GATE_EXPECTATIONS = {
    L.pilot_calibration.CAUSE_DECLARED: "continue",
    L.pilot_calibration.CAUSE_NO_CALIBRATION: "pass",
    L.pilot_calibration.CAUSE_NO_PILOT_BLOCK: "pass",
    L.pilot_calibration.CAUSE_CREDENTIAL_SET_EMPTY: "pass",
    L.pilot_calibration.CAUSE_REPO_ROOT_INVALID: "refuse",
    L.pilot_calibration.CAUSE_RESOLVER_FAILED: "refuse",
    L.pilot_calibration.CAUSE_CALIBRATION_UNRESOLVED: "refuse",
    L.pilot_calibration.CAUSE_CALIBRATION_UNREADABLE: "refuse",
    L.pilot_calibration.CAUSE_NO_CONFIG_BLOCK: "refuse",
    L.pilot_calibration.CAUSE_CONFIG_UNPARSEABLE: "refuse",
    L.pilot_calibration.CAUSE_PILOT_BLOCK_MALFORMED: "refuse",
    L.pilot_calibration.CAUSE_CREDENTIAL_SET_MALFORMED: "refuse",
}


def _mock_declares_slots(monkeypatch, state, cause, path=None):
    monkeypatch.setattr(
        L.pilot_calibration,
        "declares_slots",
        lambda repo_root: {"state": state, "cause": cause, "path": path},
    )


def test_slot_calibration_cause_policy_census():
  # axis: every CAUSE_* constant has a policy row and an explicit gate expectation
    pc = L.pilot_calibration
    cause_values = {
        getattr(pc, name)
        for name in dir(pc)
        if name.startswith("CAUSE_") and isinstance(getattr(pc, name), str)
    }
    policy_keys = set(L._SLOT_CALIBRATION_POLICY.keys())
    expectation_keys = set(_SLOT_CALIBRATION_GATE_EXPECTATIONS.keys())
    assert cause_values == policy_keys == expectation_keys


@pytest.mark.parametrize(
    "cause,expected_policy",
    sorted(_SLOT_CALIBRATION_GATE_EXPECTATIONS.items()),
)
def test_slot_gate_policy_per_cause(tmp_path, monkeypatch, cause, expected_policy):
  # axis: each calibration cause honours its explicit pass/refuse/continue policy
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    state = L.pilot_calibration.CAUSE_STATE_MAP[cause]
    _mock_declares_slots(monkeypatch, state, cause, path="/fake/profile.md")
    ll.declare_batch(repo, "wave-test", 2)
    result = L.walk_preflight(_all_checks(), repo, batch_id="wave-test")
    if expected_policy == "pass":
        assert result["ok"] is True
    elif expected_policy == "refuse":
        assert result["ok"] is False
        assert result["reason"] == "preflight-slot-calibration-unreadable"
        assert result["cause"] == cause
    else:
        assert result["ok"] is False
        assert result["reason"] == "preflight-slot-reservation-required"


def test_slot_gate_contradictory_state_cause_refuses(tmp_path, monkeypatch):
  # axis: state/cause mismatch refuses fail-closed like any other cannot-tell
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _mock_declares_slots(
        monkeypatch,
        L.pilot_calibration.STATE_ABSENT,
        L.pilot_calibration.CAUSE_RESOLVER_FAILED,
        path=None,
    )
    ll.declare_batch(repo, "wave-test", 2)
    result = L.walk_preflight(_all_checks(), repo, batch_id="wave-test")
    assert result["ok"] is False
    assert result["reason"] == "preflight-slot-calibration-unreadable"


def test_slot_gate_resolver_failed_remedy_without_path(tmp_path, monkeypatch):
  # axis: remedy names the cause when no profile path is available
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _mock_declares_slots(
        monkeypatch,
        L.pilot_calibration.STATE_CANNOT_TELL,
        L.pilot_calibration.CAUSE_RESOLVER_FAILED,
        path=None,
    )
    ll.declare_batch(repo, "wave-test", 2)
    result = L.walk_preflight(_all_checks(), repo, batch_id="wave-test")
    assert result["ok"] is False
    remedy = result["remedy"]
    assert L.pilot_calibration.CAUSE_RESOLVER_FAILED in remedy
    assert "null" not in remedy.lower()
    assert "`path`" not in remedy


def test_slot_gate_policy_bite_refuse_to_pass_no_config_block(tmp_path, monkeypatch):
  # axis: flipping a refuse row to pass reddens the no-config-block gate test
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    cause = L.pilot_calibration.CAUSE_NO_CONFIG_BLOCK
    state = L.pilot_calibration.CAUSE_STATE_MAP[cause]
    _mock_declares_slots(monkeypatch, state, cause, path="/fake/profile.md")
    ll.declare_batch(repo, "wave-test", 2)
    saved = L._SLOT_CALIBRATION_POLICY[cause]
    try:
        L._SLOT_CALIBRATION_POLICY[cause] = "pass"
        red = L.walk_preflight(_all_checks(), repo, batch_id="wave-test")
        assert red["ok"] is True
    finally:
        L._SLOT_CALIBRATION_POLICY[cause] = saved
    green = L.walk_preflight(_all_checks(), repo, batch_id="wave-test")
    assert green["ok"] is False
    assert green["reason"] == "preflight-slot-calibration-unreadable"


def test_slot_gate_policy_bite_pass_to_refuse_no_calibration(tmp_path, monkeypatch):
  # axis: flipping a pass row to refuse reddens the no-calibration gate test
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    cause = L.pilot_calibration.CAUSE_NO_CALIBRATION
    state = L.pilot_calibration.CAUSE_STATE_MAP[cause]
    _mock_declares_slots(monkeypatch, state, cause, path=None)
    ll.declare_batch(repo, "wave-test", 2)
    saved = L._SLOT_CALIBRATION_POLICY[cause]
    try:
        L._SLOT_CALIBRATION_POLICY[cause] = "refuse"
        red = L.walk_preflight(_all_checks(), repo, batch_id="wave-test")
        assert red["ok"] is False
        assert red["reason"] == "preflight-slot-calibration-unreadable"
    finally:
        L._SLOT_CALIBRATION_POLICY[cause] = saved
    green = L.walk_preflight(_all_checks(), repo, batch_id="wave-test")
    assert green["ok"] is True


# --- build worktree (#974) ---------------------------------------------------


def _worktree_root(tmp_path, monkeypatch):
    root = str(tmp_path / "worktrees")
    monkeypatch.setenv(L.WORKTREES_ROOT_ENV, root)
    return root


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True, check=True,
    ).stdout.strip()


def test_launch_spawns_child_in_build_worktree_never_repo_root(tmp_path, monkeypatch):
    # axis: the spawned session's cwd is a dedicated build worktree, never the primary checkout
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _worktree_root(tmp_path, monkeypatch)
    base_sha = _head_sha(repo)
    premise = _valid_premise(repo, baseCommit=base_sha)
    (tmp_path / "repo" / "advance.txt").write_text("y\n")
    subprocess.run(
        [
            "git", "-C", repo,
            "-c", "user.email=test@test.local",
            "-c", "user.name=test",
            "add", ".",
        ],
        check=True,
    )
    subprocess.run(
        [
            "git", "-C", repo,
            "-c", "user.email=test@test.local",
            "-c", "user.name=test",
            "commit", "-q", "-m", "advance",
        ],
        check=True,
    )
    advanced_head = _head_sha(repo)
    assert advanced_head != base_sha
    seen = {}

    def capture_spawn(argv, cwd, out_fh, err_fh, child_env):
        seen["cwd"] = cwd
        return _make_spawn_fn("sleep")(argv, cwd, out_fh, err_fh, child_env)

    result = L.launch_build(
        repo,
        656,
        premise,
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=capture_spawn,
        settle_seconds=0.3,
    )
    assert result["ok"] is True
    cwd = seen["cwd"]
    assert os.path.realpath(cwd) != os.path.realpath(repo)
    assert result["worktree"] == cwd
    assert os.path.isdir(cwd)
    # It is a real, registered worktree of THIS repo, parked at the premise's base commit.
    registered = L._registered_worktree_paths(repo)
    assert os.path.realpath(cwd) in registered
    assert _git(cwd, "rev-parse", "HEAD") == base_sha
    assert _git(cwd, "rev-parse", "HEAD") != advanced_head
    assert _git(cwd, "rev-parse", "--show-toplevel")


def test_launch_records_worktree_on_the_reserved_record(tmp_path, monkeypatch):
    # axis: the worktree is registered in the durable record, pre-spawn
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _worktree_root(tmp_path, monkeypatch)
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.3,
    )
    assert result["ok"] is True
    records = ll.read(repo)["records"]
    reserved = [r for r in records if r["event"] == "reserved"]
    assert reserved[0]["worktree"] == result["worktree"]
    assert ll.fold(records)["ok"] is True


def test_launch_over_a_live_overlapping_lane_warns_and_stamps_evidence(tmp_path, monkeypatch):
    # axis: an overlapping lane launches, and the disclosure lands in the result AND the ledger
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _worktree_root(tmp_path, monkeypatch)
    first = L.launch_build(
        repo,
        656,
        _valid_premise(repo, surfaces=["plugins/superheroes/lib"]),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.3,
    )
    assert first["ok"] is True
    assert first["warnings"] == []
    second = L.launch_build(
        repo,
        657,
        _valid_premise(repo, surfaces=["plugins/superheroes"], issue=657),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.3,
    )
    assert second["ok"] is True, second.get("reason")
    assert second["warnings"] == ["surface-overlap:%s" % first["launchId"]]

    records = ll.read(repo)["records"]
    reserved = {
        r["launchId"]: r for r in records if r.get("event") == "reserved"
    }
    assert reserved[second["launchId"]]["surfaceOverlap"] == [first["launchId"]]
    started = {r["launchId"]: r for r in records if r.get("event") == "started"}
    evidence = started[second["launchId"]]["evidence"]
    assert first["launchId"] in evidence
    assert "branch-current" in evidence
    # The lane that overlapped nothing discloses nothing.
    assert "evidence" not in started[first["launchId"]]
    assert ll.fold(records)["ok"] is True


def test_launch_without_overlap_stamps_no_evidence(tmp_path, monkeypatch):
    # axis: the silent leg — no live overlap means no warning and no started evidence
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _worktree_root(tmp_path, monkeypatch)
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.3,
    )
    assert result["ok"] is True
    assert result["warnings"] == []
    records = ll.read(repo)["records"]
    started = [r for r in records if r.get("event") == "started"]
    assert started and all("evidence" not in r for r in started)


def test_cli_launch_stdout_carries_the_overlap_warning(tmp_path, monkeypatch):
    # axis: the advisor reading stdout sees the warning without opening the ledger
    import io
    from contextlib import redirect_stdout

    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    checks_path = tmp_path / "checks.json"
    _write_json(checks_path, _all_checks())
    premise_path = tmp_path / "premise.json"
    _write_json(premise_path, _valid_premise(repo))
    warnings = ["surface-overlap:launch-abc123"]

    def fake_launch(*a, **k):
        return {"ok": True, "reason": None, "launchId": "launch-x", "warnings": warnings}

    monkeypatch.setattr(L, "launch_build", fake_launch)
    buf = io.StringIO()
    with redirect_stdout(buf):
        exit_code = L.main([
            "launch",
            "--repo-root", repo,
            "--issue", "656",
            "--premise", str(premise_path),
            "--checks", str(checks_path),
            "--log-dir", str(tmp_path / "logs"),
        ])
    assert exit_code == 0
    assert json.loads(buf.getvalue())["warnings"] == warnings


def test_no_launch_build_return_drops_the_overlap_warnings():
    # axis: census over the WHOLE function — every reservation in launch_build (the main
    # one and the five accounting reservations) can stamp an overlap, so no `return _fail`
    # anywhere in it may bypass the two helpers that attach `warnings`
    lines = inspect.getsource(L.launch_build).split("\n")
    helper = next(
        i for i, ln in enumerate(lines) if "def _post_reserve_fail(" in ln
    )
    helper_end = next(
        i for i, ln in enumerate(lines) if i > helper and "return _fail(" in ln
    )
    offenders = [
        (i, ln.strip()) for i, ln in enumerate(lines)
        if i != helper_end and "return _fail(" in ln
        and 'reserve_result["reason"]' not in ln
        and "# pre-reservation:" not in ln
    ]
    assert offenders == [], (
        "launch_build failure path bypasses _post_reserve_fail/_accounted_fail and drops "
        "`warnings`: %r" % (offenders,)
    )
    # The one exempt return: its OWN reservation reported failure, so the caller has no
    # reservation to disclose against. That is not the same as "no record exists" — an
    # append that fails at fsync AFTER flush leaves a readable row while reporting failure
    # (`_append_raw`), a pre-existing ledger property this change does not touch and does
    # not fix. Pinned at exactly one so the exemption cannot quietly widen.
    exempt = [ln for ln in lines if 'reserve_result["reason"]' in ln]
    assert len(exempt) == 1, exempt
    # Pre-reservation refusals return before any reservation exists, so they have no overlap
    # to disclose. Pinned at exactly two so the exemption cannot quietly widen.
    pre_reservation = [ln for ln in lines if "# pre-reservation:" in ln]
    assert len(pre_reservation) == 2, pre_reservation


def test_prespawn_refusal_returns_the_overlap_warnings(tmp_path, monkeypatch):
    # axis: the behavioural leg — a launch refused BEFORE spawn still discloses the
    # overlap its accounting reservation recorded
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _worktree_root(tmp_path, monkeypatch)
    first = L.launch_build(
        repo,
        656,
        _valid_premise(repo, surfaces=["plugins/superheroes/lib"]),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.3,
    )
    assert first["ok"] is True
    checks = _all_checks()
    checks["engine-auth"] = {"state": "fail", "reason": "no auth"}
    refused = L.launch_build(
        repo,
        657,
        _valid_premise(repo, surfaces=["plugins/superheroes"], issue=657),
        checks,
        str(tmp_path / "logs"),
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.3,
    )
    assert refused["ok"] is False
    assert refused["reason"] == "preflight-failed:engine-auth"
    assert refused["warnings"] == ["surface-overlap:%s" % first["launchId"]]


def test_settle_failure_still_returns_the_overlap_warnings(tmp_path, monkeypatch):
    # axis: the behavioural leg of that census — a lane that died carries its disclosure
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _worktree_root(tmp_path, monkeypatch)
    first = L.launch_build(
        repo,
        656,
        _valid_premise(repo, surfaces=["plugins/superheroes/lib"]),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.3,
    )
    assert first["ok"] is True
    second = L.launch_build(
        repo,
        657,
        _valid_premise(repo, surfaces=["plugins/superheroes"], issue=657),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_make_spawn_fn("exit1"),
        settle_seconds=0.3,
    )
    assert second["ok"] is False
    assert second["warnings"] == ["surface-overlap:%s" % first["launchId"]]


def test_overlap_evidence_ignores_unparsable_warnings():
    # axis: the disclosure is built from real overlap ids only, never from noise
    assert L._overlap_evidence([]) is None
    assert L._overlap_evidence(["lock-unavailable", 7, "surface-overlap:", None]) is None
    evidence = L._overlap_evidence(["surface-overlap:l1", "surface-overlap:l2"])
    assert evidence.startswith("overlaps l1, l2; ")
    # Both citations name rules those homes actually state; merge-train.md carries
    # branch-currency, not a landing-order rule.
    assert "base-moved" in evidence
    assert "branch-current" in evidence


def test_repaired_started_record_keeps_the_overlap_disclosure(tmp_path, monkeypatch):
    # axis: a started-append failure must not lose the disclosure — the repaired record
    # stands in for the one that failed, so it carries the same evidence
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _worktree_root(tmp_path, monkeypatch)
    first = L.launch_build(
        repo,
        656,
        _valid_premise(repo, surfaces=["plugins/superheroes/lib"]),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.3,
    )
    assert first["ok"] is True

    real_append = L._append_under_lock

    def fail_started_append(repo_root, record, env=None):
        if record.get("event") == "started":
            return {"ok": False, "reason": "ledger-append-failed"}
        return real_append(repo_root, record, env=env)

    # Restored by hand, not with monkeypatch.undo(): undo() reverts EVERY patch this test
    # made, including the ledger-root fixture, which would send the read below to a
    # different ledger entirely.
    L._append_under_lock = fail_started_append
    try:
        second = L.launch_build(
            repo,
            657,
            _valid_premise(repo, surfaces=["plugins/superheroes"], issue=657),
            _all_checks(),
            str(tmp_path / "logs"),
            spawn_fn=_make_spawn_fn("sleep"),
            settle_seconds=0.3,
        )
    finally:
        L._append_under_lock = real_append
    assert second["ok"] is False
    records = ll.read(repo)["records"]
    repaired = [
        r for r in records
        if r.get("event") == "started" and r.get("repaired") and r["launchId"] == second["launchId"]
    ]
    assert repaired, "no repaired started record was written"
    assert first["launchId"] in repaired[0]["evidence"]
    assert ll.fold(records)["ok"] is True


def test_launch_reserve_refusal_leaves_no_orphan_worktree(tmp_path, monkeypatch):
    # axis: a reserve refusal after worktree creation removes the checkout
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _worktree_root(tmp_path, monkeypatch)
    before = L._registered_worktree_paths(repo) or set()
    refusal_reason = "surface-overlap:launch-deadbeef"

    def refuse_reserve(repo_root, record, env=None):
        return {"ok": False, "reason": refusal_reason}

    monkeypatch.setattr(L.ll, "reserve", refuse_reserve)
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.3,
    )
    assert result["ok"] is False
    assert result["reason"] == refusal_reason
    assert "launchId" in result
    assert "orphanedWorktree" not in result
    worktree_path = L.build_worktree_path(repo, 656, result["launchId"])
    after = L._registered_worktree_paths(repo) or set()
    assert after == before
    assert worktree_path not in after
    assert not os.path.exists(worktree_path)


def test_launch_refuses_a_worktree_path_collision_and_never_reuses_it(tmp_path, monkeypatch):
    # axis: collision refuses loudly; the occupied checkout is neither reused nor spawned into
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _worktree_root(tmp_path, monkeypatch)
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "someone-elses-work.txt").write_text("uncommitted\n")
    monkeypatch.setattr(L, "build_worktree_path", lambda *a, **k: str(occupied))
    spawned = {"n": 0}

    def counting_spawn(argv, cwd, out_fh, err_fh, child_env):
        spawned["n"] += 1
        return _make_spawn_fn("sleep")(argv, cwd, out_fh, err_fh, child_env)

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=counting_spawn,
        settle_seconds=0.3,
    )
    assert result["ok"] is False
    assert result["reason"] == "launch-worktree-collision"
    assert result["path"] == str(occupied)
    assert "one worktree per build" in result["remedy"].lower()
    assert spawned["n"] == 0
    assert (occupied / "someone-elses-work.txt").read_text() == "uncommitted\n"
    # The refusal is accounted in the ledger, not silently dropped.
    records = ll.read(repo)["records"]
    refused = [r for r in records if r.get("event") == "refused"]
    assert refused
    assert refused[-1]["reason"] == "launch-worktree-collision"
    assert refused[-1]["stage"] == "worktree"
    reserved = [r for r in records if r.get("event") == "reserved"]
    assert reserved
    assert "worktree" not in reserved[-1]


def test_create_build_worktree_refuses_a_path_git_still_registers(tmp_path, monkeypatch):
    # axis: never reuse — a registered-but-vanished worktree is a collision, not a free path
    repo = _init_repo(tmp_path / "repo")
    _worktree_root(tmp_path, monkeypatch)
    path = str(tmp_path / "wt-a")
    first = L.create_build_worktree(repo, path, _head_sha(repo))
    assert first["ok"] is True
    shutil.rmtree(path)
    assert not os.path.exists(path)
    again = L.create_build_worktree(repo, path, _head_sha(repo))
    assert again["ok"] is False
    assert again["reason"] == "launch-worktree-collision"


def test_create_build_worktree_refuses_when_the_worktree_list_is_unreadable(
    tmp_path, monkeypatch,
):
    # axis: an unreadable worktree list fails closed rather than assuming the path is free
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setattr(L, "_registered_worktree_paths", lambda *a, **k: None)
    result = L.create_build_worktree(repo, str(tmp_path / "wt-b"), _head_sha(repo))
    assert result["ok"] is False
    assert result["reason"] == "launch-worktree-list-failed"


def test_spawn_attempt_refuses_a_cwd_that_is_the_repo_root(tmp_path, monkeypatch):
    # axis: the own-worktree invariant is enforced at the spawn chokepoint, not per caller
    repo = _init_repo(tmp_path / "repo")
    ledger_root = _ledger_env(tmp_path, monkeypatch)
    launch_id = "launch-cwd-guard"
    ll.reserve(repo, {
        "event": "reserved",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "batchId": "batch-cwd-guard",
        "repoId": ll.repo_identity(repo),
        "issue": 656,
        "surfaces": ["plugins/superheroes/lib"],
        "premise": {},
        "preflight": {},
        "argv": [],
        "doctrineDigest": "abc",
        "model": "test",
    })
    spawned = {"n": 0}

    def counting_spawn(argv, cwd, out_fh, err_fh, child_env):
        spawned["n"] += 1
        raise AssertionError("must not spawn")

    log_dir = str(tmp_path / "logs")
    os.makedirs(log_dir)
    for cwd, expected in (
        (repo, "spawn-cwd-is-repo-root"),
        (os.path.join(repo, "..", os.path.basename(repo)), "spawn-cwd-is-repo-root"),
        (None, "spawn-cwd-missing"),
        ("", "spawn-cwd-missing"),
    ):
        result = L._spawn_attempt(
            repo,
            launch_id,
            1,
            ["claude", "-p", "test"],
            os.path.join(log_dir, "out.log"),
            os.path.join(log_dir, "err.log"),
            900000,
            env={ll.LEDGER_ROOT_ENV: ledger_root},
            spawn_fn=counting_spawn,
            cwd=cwd,
        )
        assert result["ok"] is False
        assert result["reason"] == expected
    assert spawned["n"] == 0


def test_build_worktree_path_is_unique_per_launch_and_names_the_issue(tmp_path, monkeypatch):
    # axis: one worktree per BUILD — an adoption relaunch of the same issue gets its own path
    repo = _init_repo(tmp_path / "repo")
    root = _worktree_root(tmp_path, monkeypatch)
    first = L.build_worktree_path(repo, 974, "launch-aaaaaaaaaaaaaaaa")
    second = L.build_worktree_path(repo, 974, "launch-bbbbbbbbbbbbbbbb")
    same_prefix_a = L.build_worktree_path(repo, 974, "launch-aaaaaaaa11111111")
    same_prefix_b = L.build_worktree_path(repo, 974, "launch-aaaaaaaa22222222")
    assert first != second
    assert same_prefix_a != same_prefix_b
    assert first.startswith(root + os.sep)
    assert os.path.basename(first).startswith("issue-974-")
    assert os.path.basename(os.path.dirname(first)) == os.path.basename(repo)
    assert L.build_worktree_path(repo, 974, "") is None


def test_worktree_root_prefers_the_env_then_home(tmp_path, monkeypatch):
    # axis: worktrees land outside the repo — under the configured root, else the home default
    monkeypatch.setenv(L.WORKTREES_ROOT_ENV, str(tmp_path / "explicit"))
    assert L.worktree_root() == str(tmp_path / "explicit")
    monkeypatch.delenv(L.WORKTREES_ROOT_ENV, raising=False)
    assert L.worktree_root({"HOME": "/home/someone"}) == os.path.join(
        "/home/someone", L.WORKTREES_DIR_NAME,
    )
    assert L.worktree_root({"HOME": "relative/path"}) is None


def _await_exit_cli_lane(tmp_path, monkeypatch, launch_id, pid):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    ll.reserve(repo, {
        "event": "reserved",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "batchId": "batch-%s" % launch_id,
        "repoId": ll.repo_identity(repo),
        "issue": 1040,
        "surfaces": ["a"],
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
        "pid": pid,
        "logPath": "/tmp/out",
        "errPath": "/tmp/err",
    })
    return repo


def _run_record_outcome_cli(repo, launch_id, *extra):
    return subprocess.run(
        [
            sys.executable, _MOD, "record-outcome",
            "--repo-root", repo,
            "--launch-id", launch_id,
            "--outcome", "handback",
            "--evidence", "done",
        ] + list(extra),
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_record_outcome_accepts_await_exit(tmp_path, monkeypatch):
    # axis: --await-exit threads through to the ledger and still records a gone child
    launch_id = "launch-await-cli"
    repo = _await_exit_cli_lane(tmp_path, monkeypatch, launch_id, 424242)
    proc = _run_record_outcome_cli(repo, launch_id, "--await-exit", "3")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["recorded"] == "outcome"


def test_cli_record_outcome_refuses_a_negative_await_exit(tmp_path, monkeypatch):
    # axis: the CLI value reaches the validator rather than being coerced to 0
    launch_id = "launch-await-cli-bad"
    repo = _await_exit_cli_lane(tmp_path, monkeypatch, launch_id, 424242)
    proc = _run_record_outcome_cli(repo, launch_id, "--await-exit", "-1")
    assert proc.returncode != 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["reason"] == "await-exit-invalid:-1.0"
    assert not any(
        r.get("event") == "outcome" for r in ll.read(repo)["records"]
    )


# --- seat instance pin (#1311) -----------------------------------------------


def _build_kern_procargs2(exec_path, argv, env_entries):
    parts = [struct.pack("@I", len(argv))]
    parts.append(exec_path.encode("utf-8") + b"\x00")
    for arg in argv:
        parts.append(arg.encode("utf-8") + b"\x00")
    for entry in env_entries:
        parts.append(entry.encode("utf-8") + b"\x00")
    return b"".join(parts)


def test_kern_procargs2_parses_exec_argv_and_env_including_edge_values():
    # axis: synthesized Darwin payload yields exec path, argv, and env with space, =, and empty value
    payload = _build_kern_procargs2(
        "/Users/me/.local/bin/claude",
        ["claude", "--model", "opus"],
        [
            "HOME=/Users/me",
            "CLAUDE_CONFIG_DIR=/Users/me/.claude-three",
            "CLAUDE_CODE_DISABLE_CRON=",
            "WEIRD=has space inside",
            "EQUALS=foo=bar=baz",
        ],
    )
    parsed = L._parse_kern_procargs2(payload)
    assert parsed["exec_path"] == "/Users/me/.local/bin/claude"
    assert parsed["argv"] == ["claude", "--model", "opus"]
    assert parsed["env"]["HOME"] == "/Users/me"
    assert parsed["env"]["CLAUDE_CONFIG_DIR"] == "/Users/me/.claude-three"
    assert parsed["env"]["CLAUDE_CODE_DISABLE_CRON"] == ""
    assert parsed["env"]["WEIRD"] == "has space inside"
    assert parsed["env"]["EQUALS"] == "foo=bar=baz"


def test_kern_procargs2_argv_env_spoof_does_not_pollute_env():
    # axis: argv strings that look like env assignments are not parsed as env
    payload = _build_kern_procargs2(
        "/usr/local/bin/claude",
        ["claude", "CLAUDE_CONFIG_DIR=/spoofed"],
        ["HOME=/home/user", "CLAUDE_CONFIG_DIR=/real/path"],
    )
    parsed = L._parse_kern_procargs2(payload)
    assert parsed["env"]["CLAUDE_CONFIG_DIR"] == "/real/path"
    assert "CLAUDE_CONFIG_DIR=/spoofed" not in parsed["env"]


def test_seat_config_dir_defaults_to_home_claude_when_unpinned(
    monkeypatch, unpatched_seat_config_dir,
):
    # axis: absent CLAUDE_CONFIG_DIR in a readable seat snapshot resolves to <HOME>/.claude
    payload = _build_kern_procargs2(
        "/usr/local/bin/claude",
        ["claude"],
        ["HOME=/home/seat-user", "CLAUDE_PID=4242"],
    )
    monkeypatch.setenv("CLAUDE_PID", "4242")
    monkeypatch.setattr(L, "_read_kern_procargs2_darwin", lambda pid: payload)
    monkeypatch.setattr(L.platform, "system", lambda: "Darwin")
    result = L.seat_config_dir()
    assert result == {
        "instance": os.path.normpath("/home/seat-user/.claude"),
        "reason": None,
    }


def test_seat_config_dir_resolves_absolute_configured_instance(
    monkeypatch, unpatched_seat_config_dir,
):
    # axis: pinned absolute CLAUDE_CONFIG_DIR in the seat snapshot resolves to that path
    payload = _build_kern_procargs2(
        "/usr/local/bin/claude",
        ["claude"],
        [
            "HOME=/home/seat-user",
            "CLAUDE_CONFIG_DIR=/home/seat-user/.claude-two",
            "CLAUDE_PID=4242",
        ],
    )
    monkeypatch.setenv("CLAUDE_PID", "4242")
    monkeypatch.setattr(L, "_read_kern_procargs2_darwin", lambda pid: payload)
    monkeypatch.setattr(L.platform, "system", lambda: "Darwin")
    result = L.seat_config_dir()
    assert result == {
        "instance": os.path.normpath("/home/seat-user/.claude-two"),
        "reason": None,
    }


def test_seat_config_dir_resolves_relative_configured_instance(
    monkeypatch, unpatched_seat_config_dir, tmp_path,
):
    # axis: pinned relative CLAUDE_CONFIG_DIR resolves against the seat snapshot HOME
    home = str(tmp_path / "seat-home")
    payload = _build_kern_procargs2(
        "/usr/local/bin/claude",
        ["claude"],
        [
            "HOME=%s" % home,
            "CLAUDE_CONFIG_DIR=relative/config",
            "CLAUDE_PID=4242",
        ],
    )
    monkeypatch.setenv("CLAUDE_PID", "4242")
    monkeypatch.setattr(L, "_read_kern_procargs2_darwin", lambda pid: payload)
    monkeypatch.setattr(L.platform, "system", lambda: "Darwin")
    result = L.seat_config_dir()
    assert result == {
        "instance": os.path.normpath(os.path.join(home, "relative/config")),
        "reason": None,
    }


def test_seat_config_dir_unreadable_when_normalized_path_fails(
    monkeypatch, unpatched_seat_config_dir,
):
    # axis: configured CLAUDE_CONFIG_DIR that cannot normalize is seat-snapshot-unreadable
    payload = _build_kern_procargs2(
        "/usr/local/bin/claude",
        ["claude"],
        [
            "HOME=/home/seat-user",
            "CLAUDE_CONFIG_DIR=relative/config",
            "CLAUDE_PID=4242",
        ],
    )
    monkeypatch.setenv("CLAUDE_PID", "4242")
    monkeypatch.setattr(L, "_read_kern_procargs2_darwin", lambda pid: payload)
    monkeypatch.setattr(L.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(L, "_normalized_instance_path", lambda path, home: None)
    result = L.seat_config_dir()
    assert result["instance"] is None
    assert result["reason"] == "seat-snapshot-unreadable"


def test_seat_config_dir_resolves_when_snapshot_pid_differs_from_caller(
    monkeypatch, unpatched_seat_config_dir,
):
    # axis: exec-time snapshot CLAUDE_PID may differ from the caller's inherited pid
    payload = _build_kern_procargs2(
        "/usr/local/bin/claude",
        ["claude"],
        [
            "HOME=/home/seat-user",
            "CLAUDE_CONFIG_DIR=/home/seat-user/.claude-three",
            "CLAUDE_PID=9999",
        ],
    )
    monkeypatch.setenv("CLAUDE_PID", "4242")
    monkeypatch.setattr(L, "_read_kern_procargs2_darwin", lambda pid: payload)
    monkeypatch.setattr(L.platform, "system", lambda: "Darwin")
    result = L.seat_config_dir()
    assert result == {
        "instance": os.path.normpath("/home/seat-user/.claude-three"),
        "reason": None,
    }


@pytest.mark.parametrize(
    "setup,expected_reason",
    [
        ({}, "seat-pid-absent"),
        ({"CLAUDE_PID": ""}, "seat-pid-absent"),
        ({"CLAUDE_PID": "0"}, "seat-pid-absent"),
        ({"CLAUDE_PID": "not-int"}, "seat-pid-absent"),
    ],
)
def test_seat_config_dir_reports_seat_pid_absent(setup, expected_reason, monkeypatch, unpatched_seat_config_dir):
    # axis: missing or invalid CLAUDE_PID is undetermined with seat-pid-absent
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    for key, value in setup.items():
        monkeypatch.setenv(key, value)
    result = L.seat_config_dir()
    assert result["instance"] is None
    assert result["reason"] == expected_reason


def test_seat_config_dir_reports_seat_snapshot_unreadable(monkeypatch, unpatched_seat_config_dir):
    # axis: unreadable snapshot is undetermined with seat-snapshot-unreadable
    monkeypatch.setenv("CLAUDE_PID", "4242")
    monkeypatch.setattr(L, "_read_seat_snapshot", lambda pid: None)
    result = L.seat_config_dir()
    assert result["instance"] is None
    assert result["reason"] == "seat-snapshot-unreadable"


def test_seat_config_dir_reports_seat_not_claude_for_node_shape(monkeypatch, unpatched_seat_config_dir):
    # axis: exec basename not claude is undetermined — argv mentioning claude does not help
    payload = _build_kern_procargs2(
        "/usr/bin/node",
        ["node", "/path/to/claude-wrapper.js", "claude"],
        ["HOME=/home/user", "CLAUDE_CONFIG_DIR=/home/user/.claude", "CLAUDE_PID=4242"],
    )
    monkeypatch.setenv("CLAUDE_PID", "4242")
    monkeypatch.setattr(L, "_read_kern_procargs2_darwin", lambda pid: payload)
    monkeypatch.setattr(L.platform, "system", lambda: "Darwin")
    result = L.seat_config_dir()
    assert result["instance"] is None
    assert result["reason"] == "seat-not-claude"


def test_seat_config_dir_malformed_procargs2_is_unreadable(monkeypatch, unpatched_seat_config_dir):
    # axis: malformed KERN_PROCARGS2 payload is seat-snapshot-unreadable, never an exception
    monkeypatch.setenv("CLAUDE_PID", "4242")
    monkeypatch.setattr(L, "_read_kern_procargs2_darwin", lambda pid: b"\x07\x00\x00\x00bad")
    monkeypatch.setattr(L.platform, "system", lambda: "Darwin")
    result = L.seat_config_dir()
    assert result["instance"] is None
    assert result["reason"] == "seat-snapshot-unreadable"


def test_seat_config_dir_never_raises_when_reader_raises(monkeypatch, unpatched_seat_config_dir):
    # axis: seat_config_dir returns undetermined instead of raising
    monkeypatch.setenv("CLAUDE_PID", "4242")

    def _boom(_pid):
        raise OSError("nope")

    monkeypatch.setattr(L, "_read_seat_snapshot", _boom)
    result = L.seat_config_dir()
    assert result["instance"] is None
    assert result["reason"] == "seat-snapshot-unreadable"


def test_launch_foreign_instance_pin_refuses_mismatch(tmp_path, monkeypatch):
    # axis: mismatched config roots refuse with both instances named
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _worktree_root(tmp_path, monkeypatch)
    launcher_pin = str(tmp_path / "launcher-pin")
    seat_own = str(tmp_path / "seat-own")
    os.makedirs(launcher_pin)
    os.makedirs(seat_own)
    monkeypatch.setenv("CLAUDE_PID", "4242")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", launcher_pin)
    monkeypatch.setattr(
        L,
        "seat_config_dir",
        lambda env=None: {"instance": seat_own, "reason": None},
    )
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
    )
    assert result["ok"] is False
    assert result["reason"] == "launch-foreign-instance-pin"
    assert result["seatInstance"] == seat_own
    assert result["requestedInstance"] == launcher_pin
    assert "--allow-foreign-instance" in result["remedy"]


def test_launch_instance_pin_refusal_launches_nothing(tmp_path, monkeypatch):
    # axis: pre-reservation refusal creates no spawn, worktree, git registration, or ledger row
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    wt_root = _worktree_root(tmp_path, monkeypatch)
    launcher_pin = str(tmp_path / "launcher-pin")
    seat_own = str(tmp_path / "seat-own")
    os.makedirs(launcher_pin)
    os.makedirs(seat_own)
    monkeypatch.setenv("CLAUDE_PID", "4242")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", launcher_pin)
    monkeypatch.setattr(
        L,
        "seat_config_dir",
        lambda env=None: {"instance": seat_own, "reason": None},
    )
    spawn_calls = []
    monkeypatch.setattr(
        L,
        "_spawn_attempt",
        lambda *a, **k: spawn_calls.append(1) or {"refused": True, "reason": "unexpected"},
    )
    before_worktrees = _git(repo, "worktree", "list", "--porcelain")
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
    )
    assert result["ok"] is False
    assert result["reason"] == "launch-foreign-instance-pin"
    assert spawn_calls == []
    launch_id = result["launchId"]
    expected_path = L.build_worktree_path(repo, 656, launch_id, env=os.environ)
    assert expected_path is not None
    assert not os.path.exists(expected_path)
    after_worktrees = _git(repo, "worktree", "list", "--porcelain")
    assert after_worktrees == before_worktrees
    records = ll.read(repo).get("records") or []
    assert not any(r.get("launchId") == launch_id for r in records)


def _seat_snapshot_for_worktree(worktree, home, config_dir, pid="4242"):
    return {
        "exec_path": "/usr/local/bin/claude",
        "argv": ["claude"],
        "env": {
            "HOME": home,
            "CLAUDE_CONFIG_DIR": config_dir,
            "CLAUDE_PID": pid,
        },
    }


def test_launch_relative_config_dir_match_proceeds(
    tmp_path, monkeypatch, unpatched_seat_config_dir,
):
    # axis: relative override resolves against the worktree and matches the seat — no refusal
    worktree = str(tmp_path / "build-wt")
    monkeypatch.setattr(
        L,
        "build_worktree_path",
        lambda repo_root, issue, launch_id, env=None: worktree,
    )
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "relative/config")
    monkeypatch.setenv("CLAUDE_PID", "4242")
    monkeypatch.setattr(
        L,
        "_read_seat_snapshot",
        lambda pid: _seat_snapshot_for_worktree(worktree, worktree, "relative/config"),
    )
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _worktree_root(tmp_path, monkeypatch)
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.2,
    )
    assert result["ok"] is True, result
    try:
        os.kill(result["pid"], signal.SIGTERM)
    except ProcessLookupError:
        pass


def test_launch_relative_config_dir_mismatch_refuses(
    tmp_path, monkeypatch, unpatched_seat_config_dir,
):
    # axis: relative requested pin against a different seat instance refuses before spawn
    worktree = str(tmp_path / "build-wt")
    monkeypatch.setattr(
        L,
        "build_worktree_path",
        lambda repo_root, issue, launch_id, env=None: worktree,
    )
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "relative/config")
    monkeypatch.setenv("CLAUDE_PID", "4242")
    monkeypatch.setattr(
        L,
        "_read_seat_snapshot",
        lambda pid: _seat_snapshot_for_worktree(
            worktree, worktree, "/tmp/other-seat-instance",
        ),
    )
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _worktree_root(tmp_path, monkeypatch)
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
    )
    assert result["ok"] is False
    assert result["reason"] == "launch-foreign-instance-pin"
    assert result["seatInstance"] == os.path.normpath("/tmp/other-seat-instance")
    assert result["requestedInstance"] == os.path.normpath(
        os.path.join(worktree, "relative/config"),
    )


def test_launch_build_proceeds_without_claude_pid_on_non_claude_host(tmp_path, monkeypatch):
    # axis: Codex-hosted showrunner has no CLAUDE_PID — the instance-pin gate is skipped
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _worktree_root(tmp_path, monkeypatch)
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.2,
    )
    assert result["ok"] is True, result
    try:
        os.kill(result["pid"], signal.SIGTERM)
    except ProcessLookupError:
        pass


@pytest.mark.parametrize(
    "seat_result",
    [
        {"instance": None, "reason": "seat-pid-absent"},
        {"instance": None, "reason": "seat-snapshot-unreadable"},
        {"instance": None, "reason": "seat-not-claude"},
    ],
)
def test_launch_seat_undetermined_refuses(seat_result, tmp_path, monkeypatch):
    # axis: each undetermined reason refuses with launch-seat-instance-undetermined
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _worktree_root(tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_PID", "4242")
    launcher_pin = str(tmp_path / "launcher-pin"); os.makedirs(launcher_pin, exist_ok=True); monkeypatch.setenv("CLAUDE_CONFIG_DIR", launcher_pin)
    monkeypatch.setattr(L, "seat_config_dir", lambda env=None: dict(seat_result))
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
    )
    assert result["ok"] is False
    assert result["reason"] == "launch-seat-instance-undetermined"
    assert result["seatInstance"] is None
    assert result["seatReason"] == seat_result["reason"]
    assert result["requestedInstance"] == launcher_pin
    assert "--allow-foreign-instance" in result["remedy"]


def test_allow_foreign_instance_flag_permits_mismatch_and_records_override(
    tmp_path, monkeypatch,
):
    # axis: --allow-foreign-instance proceeds on mismatch and stamps foreignInstanceAllowed
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _worktree_root(tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_PID", "4242")
    launcher_pin = str(tmp_path / "launcher-pin"); seat_own = str(tmp_path / "seat-own"); os.makedirs(launcher_pin, exist_ok=True); os.makedirs(seat_own, exist_ok=True); monkeypatch.setenv("CLAUDE_CONFIG_DIR", launcher_pin)
    monkeypatch.setattr(
        L,
        "seat_config_dir",
        lambda env=None: {"instance": seat_own, "reason": None},
    )
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.2,
        allow_foreign_instance=True,
    )
    assert result["ok"] is True, result
    reserved = [
        r for r in ll.read(repo)["records"] if r.get("event") == "reserved"
    ][0]
    assert reserved["foreignInstanceAllowed"] is True
    assert reserved["seatInstance"] == seat_own
    try:
        os.kill(result["pid"], signal.SIGTERM)
    except ProcessLookupError:
        pass


def test_allow_foreign_instance_on_undetermined_seat_omits_seat_instance(
    tmp_path, monkeypatch,
):
    # axis: flag on undetermined seat proceeds with foreignInstanceAllowed and no seatInstance
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _worktree_root(tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_PID", "4242")
    launcher_pin = str(tmp_path / "launcher-pin"); os.makedirs(launcher_pin, exist_ok=True); monkeypatch.setenv("CLAUDE_CONFIG_DIR", launcher_pin)
    monkeypatch.setattr(
        L,
        "seat_config_dir",
        lambda env=None: {"instance": None, "reason": "seat-pid-absent"},
    )
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.2,
        allow_foreign_instance=True,
    )
    assert result["ok"] is True, result
    reserved = [
        r for r in ll.read(repo)["records"] if r.get("event") == "reserved"
    ][0]
    assert reserved["foreignInstanceAllowed"] is True
    assert "seatInstance" not in reserved
    try:
        os.kill(result["pid"], signal.SIGTERM)
    except ProcessLookupError:
        pass


def test_allow_foreign_instance_on_matching_launch_writes_no_override_field(
    tmp_path, monkeypatch,
):
    # axis: flag passed when nothing to override writes no foreignInstanceAllowed key
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _worktree_root(tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_PID", "4242")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/tmp/same-pin")
    monkeypatch.setattr(
        L,
        "seat_config_dir",
        lambda env=None: {"instance": "/tmp/same-pin", "reason": None},
    )
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.2,
        allow_foreign_instance=True,
    )
    assert result["ok"] is True, result
    reserved = [
        r for r in ll.read(repo)["records"] if r.get("event") == "reserved"
    ][0]
    assert "foreignInstanceAllowed" not in reserved
    try:
        os.kill(result["pid"], signal.SIGTERM)
    except ProcessLookupError:
        pass


def test_launch_proceeds_when_requested_config_dir_is_none(tmp_path, monkeypatch):
    # axis: spawn_config_dir returning None is not a mismatch — launch proceeds
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _worktree_root(tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_PID", "4242")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "relative/only")
    monkeypatch.setattr(L, "build_worktree_path", lambda *a, **k: None)
    monkeypatch.setattr(
        L,
        "seat_config_dir",
        lambda env=None: {"instance": seat_own, "reason": None},
    )
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
    )
    assert result["ok"] is False
    assert result["reason"] != "launch-foreign-instance-pin"
    assert result["reason"] != "launch-seat-instance-undetermined"


def test_seat_instance_on_successful_reserved_record(tmp_path, monkeypatch):
    # axis: normal successful launch writes seatInstance on the reserved record
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _worktree_root(tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_PID", "4242")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/tmp/same-pin")
    monkeypatch.setattr(
        L,
        "seat_config_dir",
        lambda env=None: {"instance": "/tmp/same-pin", "reason": None},
    )
    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_make_spawn_fn("sleep"),
        settle_seconds=0.2,
    )
    assert result["ok"] is True, result
    reserved = [
        r for r in ll.read(repo)["records"] if r.get("event") == "reserved"
    ][0]
    assert reserved["seatInstance"] == "/tmp/same-pin"
    try:
        os.kill(result["pid"], signal.SIGTERM)
    except ProcessLookupError:
        pass


def test_seat_instance_on_accounting_reservation_after_preflight_refusal(
    tmp_path, monkeypatch,
):
    # axis: _try_reserve_for_refusal accounting reservation carries seatInstance
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    _worktree_root(tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_PID", "4242")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/tmp/same-pin")
    monkeypatch.setattr(
        L,
        "seat_config_dir",
        lambda env=None: {"instance": "/tmp/same-pin", "reason": None},
    )
    checks = _all_checks()
    checks["engine-auth"] = {"state": "fail", "reason": "no auth"}
    result = L.launch_build(
        repo,
        657,
        _valid_premise(repo, surfaces=["plugins/superheroes"], issue=657),
        checks,
        str(tmp_path / "logs"),
    )
    assert result["ok"] is False
    assert result["reason"] == "preflight-failed:engine-auth"
    reserved = [
        r for r in ll.read(repo)["records"] if r.get("event") == "reserved"
    ][0]
    assert reserved["seatInstance"] == "/tmp/same-pin"


def test_cli_launch_parser_threads_allow_foreign_instance(tmp_path, monkeypatch):
    # axis: real launch parser accepts --allow-foreign-instance
    import io
    from contextlib import redirect_stdout

    repo = _init_repo(tmp_path / "repo")
    premise_path = tmp_path / "premise.json"
    checks_path = tmp_path / "checks.json"
    _write_json(premise_path, _valid_premise(repo))
    _write_json(checks_path, _all_checks())
    seen = {}

    def fake_launch(*a, **k):
        seen["allow"] = k.get("allow_foreign_instance")
        return {"ok": True, "reason": None, "launchId": "launch-x"}

    monkeypatch.setattr(L, "launch_build", fake_launch)
    base_args = [
        "launch",
        "--repo-root", repo,
        "--issue", "656",
        "--premise", str(premise_path),
        "--checks", str(checks_path),
        "--log-dir", str(tmp_path / "logs"),
    ]
    with redirect_stdout(io.StringIO()):
        assert L.main(base_args + ["--allow-foreign-instance"]) == 0
    assert seen["allow"] is True
    seen.clear()
    with redirect_stdout(io.StringIO()):
        assert L.main(base_args) == 0
    assert seen["allow"] is False


def test_walk_preflight_failed_check_carries_checks(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    checks = _all_checks()
    checks["engine-auth"] = {
        "state": "fail",
        "reason": "conformance probe failed: codex",
        "evidence": "codex channel=native cell=codex/gpt-5.6-sol/xhigh",
    }
    result = L.walk_preflight(checks, repo)
    assert result["ok"] is False
    assert result["reason"] == "preflight-failed:engine-auth"
    assert "checks" in result
    auth = [c for c in result["checks"] if c["id"] == "engine-auth"][0]
    assert auth["state"] == "fail"
    assert "codex" in auth["evidence"]


def test_walk_preflight_later_walked_failure_carries_every_earlier_pass(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    ids = [cid for cid, _ in LD.PREFLIGHT_CHECKS if cid not in LD.LAUNCHER_OWNED_CHECKS]
    checks = _all_checks()
    checks[ids[-1]] = {"state": "fail", "reason": "late"}
    result = L.walk_preflight(checks, repo)
    assert result["reason"] == "preflight-failed:" + ids[-1]
    walked_ids = [cid for cid, _ in LD.PREFLIGHT_CHECKS]
    fail_idx = walked_ids.index(ids[-1])
    expected_ids = walked_ids[:fail_idx + 1]
    check_ids = [c["id"] for c in result["checks"]]
    assert check_ids == expected_ids
    for c in result["checks"][:-1]:
        assert c["state"] == "pass"
    assert result["checks"][-1]["state"] == "fail"


def test_launch_refusal_record_keeps_failed_check(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    checks = _all_checks()
    checks["engine-auth"] = {
        "state": "fail",
        "reason": "conformance probe failed: codex",
        "evidence": "codex channel=native legs=resultProduction:fail",
    }
    result = L.launch_build(
        repo,
        1270,
        _valid_premise(repo),
        checks,
        str(tmp_path / "logs"),
    )
    assert result["ok"] is False
    reserved = [r for r in ll.read(repo)["records"] if r.get("event") == "reserved"][0]
    preflight_checks = reserved.get("preflight", {}).get("checks") or []
    auth = [c for c in preflight_checks if c.get("id") == "engine-auth"]
    assert auth, preflight_checks
    assert auth[0]["state"] == "fail"
    assert "codex" in auth[0].get("evidence", "")


# --- WO-B C14 layer 4a-2 (#1273) ---------------------------------------------


def test_wo_b_pre_reservation_unresolvable(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    monkeypatch.delenv(cd.CONFIG_DIR_ENV, raising=False)
    monkeypatch.setattr(cd, "resolve", lambda env=None, cwd=None: None)
    result = L.launch_build(repo, 656, _valid_premise(repo), _all_checks(), str(tmp_path / "logs"))
    assert result["ok"] is False
    assert result["reason"] == cd.REFUSAL_CONFIG_DIR_UNRESOLVABLE
    assert not ll.read(repo).get("records")


def test_wo_b_pre_reservation_not_a_directory(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    missing = str(tmp_path / "missing-abs")
    monkeypatch.setenv(cd.CONFIG_DIR_ENV, missing)
    result = L.launch_build(repo, 656, _valid_premise(repo), _all_checks(), str(tmp_path / "logs"))
    assert result["ok"] is False
    assert result["reason"] == cd.REFUSAL_CONFIG_DIR_NOT_A_DIRECTORY
    assert not ll.read(repo).get("records")


def test_wo_b_pre_reservation_gate_no_ledger_allow_foreign(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    missing = str(tmp_path / "missing-abs")
    monkeypatch.setenv(cd.CONFIG_DIR_ENV, missing)
    monkeypatch.setenv("CLAUDE_PID", "4242")
    seat_own = str(tmp_path / "seat-own")
    os.makedirs(seat_own, exist_ok=True)
    monkeypatch.setattr(L, "seat_config_dir", lambda env=None: {"instance": seat_own, "reason": None})
    result = L.launch_build(
        repo, 656, _valid_premise(repo), _all_checks(), str(tmp_path / "logs"),
        allow_foreign_instance=True,
    )
    assert result["ok"] is False
    assert result["reason"] == cd.REFUSAL_CONFIG_DIR_NOT_A_DIRECTORY
    assert not ll.read(repo).get("records")


def test_wo_b_started_pid_is_handle_not_ack(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path / "repo")
    _ledger_env(tmp_path, monkeypatch)
    result = L.launch_build(
        repo, 656, _valid_premise(repo), _all_checks(), str(tmp_path / "logs"),
        spawn_fn=_make_spawn_fn("sleep"), settle_seconds=0.2,
    )
    assert result["ok"] is True
    started = [r for r in ll.read(repo)["records"] if r.get("event") == "started"][0]
    assert started["pid"] == result["pid"]
    assert started["pid"] == _BG_TEST_STATE["session_pid"]
    _reap(result)
