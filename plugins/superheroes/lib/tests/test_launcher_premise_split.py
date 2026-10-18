import importlib.util
import inspect
import os
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

import launch_ledger as ll  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
_MOD = os.path.join(_HERE, "..", "launcher.py")


def _load_launcher():
    spec = importlib.util.spec_from_file_location("launcher", _MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


L = _load_launcher()


def _init_repo(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    (tmp_path / "file.txt").write_text("x\n")
    for argv in (["add", "."], ["commit", "-q", "-m", "init"]):
        subprocess.run(
            [
                "git", "-C", str(tmp_path),
                "-c", "user.email=test@test.local",
                "-c", "user.name=test",
                *argv,
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


@pytest.fixture(autouse=True)
def _isolated_environment(tmp_path, monkeypatch):
    # axis: no test here reads the developer's git config, ledger, worktree root, or live seat
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger-root"))
    monkeypatch.setenv(L.WORKTREES_ROOT_ENV, str(tmp_path / "worktrees"))
    monkeypatch.setattr(L, "_claude_seat_pin_gate_applies", lambda env=None: False)


def _never_spawn(argv, cwd, out_fh, err_fh, child_env):
    raise AssertionError("spawned despite a refused premise")


def test_premise_helpers_never_bypass_refusal_accounting():
    # axis: a pre-reservation refusal goes through `_refuse_unreserved`, never a bare `_fail`
    for name in ("_check_premises", "_refuse_unreserved"):
        bare = [
            line.strip()
            for line in inspect.getsource(getattr(L, name)).splitlines()
            if "return _fail(" in line
        ]
        assert bare == [], "%s returns a refusal without accounting: %r" % (name, bare)


def _assert_one_accounted_refusal(repo, stage, reason):
    records = ll.read(repo)["records"]
    assert not [r for r in records if r.get("event") == "started"]
    assert len([r for r in records if r.get("event") == "reserved"]) == 1
    refused = [r for r in records if r.get("event") == "refused"]
    assert len(refused) == 1
    assert refused[0]["stage"] == stage
    assert refused[0]["reason"] == reason


def test_unresolvable_worktree_path_is_an_accounted_refusal(tmp_path, monkeypatch):
    # axis: a local launch with no resolvable worktree path refuses at `worktree`, accounted, unspawned
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setattr(L, "build_worktree_path", lambda *a, **k: None)

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_never_spawn,
    )
    assert result["ok"] is False
    assert result["reason"] == "launch-worktree-path-unresolvable"
    _assert_one_accounted_refusal(repo, "worktree", "launch-worktree-path-unresolvable")
    assert not (tmp_path / "worktrees").exists()


def test_missing_default_model_refuses_at_the_model_stage(tmp_path, monkeypatch):
    # axis: an empty dispatch-token registry refuses at `model`, not `compose`, and never spawns
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setattr(L, "_claude_dispatch_tokens", lambda: [])

    result = L.launch_build(
        repo,
        656,
        _valid_premise(repo),
        _all_checks(),
        str(tmp_path / "logs"),
        spawn_fn=_never_spawn,
    )
    assert result["ok"] is False
    assert result["reason"] == "model-default-unavailable"
    _assert_one_accounted_refusal(repo, "model", "model-default-unavailable")
    assert not (tmp_path / "worktrees").exists()
