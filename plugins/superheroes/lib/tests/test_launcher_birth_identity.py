"""What the launcher records about a lane's process and account at spawn and at reserve (C8a WO4).

Two seams are covered here:
- the spawn site: the `started` record carries the child's birth identity (`pidLstart`, `pidCommand`)
  so a reused pid can later be told from the lane's child (vet 464);
- the cloud reserve: the `reserved` record carries the launching account's id when it can be read, so
  a later reader decides "the advisor's account" by id and not by config-dir path (C7p FU2).

`ps` is never run: `read_birth_identity` and `cloud_setup.launching_account` are replaced.
"""
import os
import subprocess
import time

import pytest

import launch_ledger as ll

from test_launcher import L, _all_checks, _spawn_cwd  # noqa: E402
from test_launcher_cloud import (  # noqa: E402,F401
    ENV_ID,
    _cloud_repo,
    _fake_spawn,
    _isolated,
    _lanes,
    _launch,
    _records,
)

BORN = {"pidLstart": "Mon Oct 12 09:00:00 2026", "pidCommand": "claude -p test"}


def _plain_repo(tmp_path):
    """A repository with no commit: the ledger needs only `git init`."""
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    return str(root)


def _spawn_one(tmp_path, monkeypatch, launch_id="spawn-identity-lane"):
    repo = _plain_repo(tmp_path)
    ledger_root = str(tmp_path / "ledger-root")
    os.makedirs(ledger_root, mode=0o700, exist_ok=True)
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, ledger_root)
    ll.declare_batch(repo, "batch-spawn-identity", 1)
    assert ll.append(repo, {
        "event": "reserved", "launchId": launch_id, "ts": time.time(), "schema": ll.SCHEMA,
        "batchId": "batch-spawn-identity", "repoId": ll.repo_identity(repo), "issue": 656,
        "surfaces": ["plugins/superheroes/lib"], "premise": {}, "preflight": {}, "argv": [],
        "doctrineDigest": "abc", "model": "test",
    })

    def spawn(argv, cwd, out_fh, err_fh, child_env):
        class _Proc:
            pid = 424242

        out_fh.close()
        err_fh.close()
        return _Proc()

    log_dir = str(tmp_path / "logs")
    os.makedirs(log_dir)
    result = L._spawn_attempt(
        repo, launch_id, 1, ["claude", "-p", "test"],
        os.path.join(log_dir, "out.log"), os.path.join(log_dir, "err.log"), 900000,
        env={ll.LEDGER_ROOT_ENV: ledger_root}, spawn_fn=spawn, cwd=_spawn_cwd(tmp_path))
    started = [r for r in ll.read(repo)["records"] if r.get("event") == "started"]
    return result, started


# --- the spawn site ---------------------------------------------------------------------------
# The `started` append is exercised elsewhere by test_launcher.py::test_spawn_attempt_exports_heartbeat_env_without_ledger_root;
# its birth-identity fields are tested here, in a file this order owns.


# axis: the child's birth identity is recorded on its started record at spawn — see bite-proof record c8a_wo4.md
def test_the_started_record_carries_the_childs_birth_identity(tmp_path, monkeypatch):
    asked = []

    def read(pid):
        asked.append(pid)
        return dict(BORN)

    monkeypatch.setattr(ll, "read_birth_identity", read)
    result, started = _spawn_one(tmp_path, monkeypatch)
    assert result["ok"] is True and asked == [424242]
    assert len(started) == 1
    assert started[0]["pid"] == 424242
    assert started[0]["pidLstart"] == BORN["pidLstart"] and started[0]["pidCommand"] == BORN["pidCommand"]


@pytest.mark.parametrize("read", [
    {},  # every read failed
    {"pidCommand": "claude -p test"},  # the start-time read failed
    {"pidLstart": "Mon Oct 12 09:00:00 2026"},  # the command read failed
])
def test_a_failed_identity_read_omits_that_field_and_never_fails_the_spawn(tmp_path, monkeypatch, read):
    monkeypatch.setattr(ll, "read_birth_identity", lambda pid: dict(read))
    result, started = _spawn_one(tmp_path, monkeypatch)
    assert result["ok"] is True
    assert len(started) == 1
    assert {k: v for k, v in started[0].items() if k.startswith("pid") and k != "pid"} == read


# --- the cloud reserve ------------------------------------------------------------------------


def _account(monkeypatch, answer):
    seen = []

    def fake(env=None, cwd=None):
        seen.append(cwd)
        return answer

    monkeypatch.setattr(L.cloud_setup, "launching_account", fake)
    return seen


# axis: the cloud reserved record carries the launching account's id — see bite-proof record c8a_wo4.md
def test_a_cloud_reserve_records_the_launching_accounts_id(tmp_path, monkeypatch):
    repo = _cloud_repo(tmp_path)
    seen = _account(monkeypatch, "acct-0001")
    result = _launch(repo, tmp_path, _fake_spawn())
    assert result["ok"] is True
    assert seen and all(cwd == repo for cwd in seen)
    reserved = _records(repo, result["launchId"], "reserved")[0]
    assert reserved["accountId"] == "acct-0001"
    assert _lanes(repo)[result["launchId"]]["accountId"] == "acct-0001"


@pytest.mark.parametrize("answer", [None, ""])
def test_an_unreadable_account_leaves_the_field_off_the_cloud_reserve(tmp_path, monkeypatch, answer):
    # edge: the account unreadable at reserve -> no accountId; the launch goes on
    repo = _cloud_repo(tmp_path)
    _account(monkeypatch, answer)
    result = _launch(repo, tmp_path, _fake_spawn())
    assert result["ok"] is True
    assert "accountId" not in _records(repo, result["launchId"], "reserved")[0]
    assert _lanes(repo)[result["launchId"]]["accountId"] is None


@pytest.mark.parametrize("answer", ["acct-0002", None])
def test_a_cloud_launch_refused_at_a_gate_records_the_account_id_when_it_is_readable(tmp_path, monkeypatch, answer):
    # the refusal-path twin of the reserve
    repo = _cloud_repo(tmp_path)
    _account(monkeypatch, answer)
    checks = _all_checks(**{"engine-auth": {"state": "fail", "reason": "nope"}})
    result = _launch(repo, tmp_path, _fake_spawn(), checks=checks)
    assert result["ok"] is False
    reserved = _records(repo, result["launchId"], "reserved")
    assert len(reserved) == 1
    assert reserved[0].get("accountId") == answer
    assert ("accountId" in reserved[0]) is (answer is not None)
