"""Refuse an unencodable detective budget before creating a build checkout."""
from pathlib import Path
import subprocess
import sys

import launch_ledger as ll
from test_launcher import L, _all_checks, _init_repo, _valid_premise


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", repo, *args],
        check=True, capture_output=True, text=True,
    ).stdout


def test_surrogate_budget_refuses_before_worktree_or_spawn(tmp_path, monkeypatch):
    # axis: an unencodable budget refuses before worktree creation or spawn, preserves owner work, and leaves one accounted refusal.
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger-root"))
    # Seat discovery is incidental to argument encoding; select a non-Claude caller.
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    repo = _init_repo(tmp_path / "repo")
    tracked = Path(repo) / "file.txt"
    notes = Path(repo) / "owner-notes.txt"
    tracked.write_text("staged owner work\n", encoding="utf-8")
    _git(repo, "add", "file.txt")
    tracked.write_text("unstaged owner work\n", encoding="utf-8")
    notes.write_text("uncommitted owner notes\n", encoding="utf-8")

    def owner_work():
        return (
            tracked.read_bytes(), notes.read_bytes(),
            _git(repo, "diff", "--cached"), _git(repo, "diff"),
            _git(repo, "status", "--porcelain"),
        )

    before = owner_work()
    worktrees_before = _git(repo, "worktree", "list", "--porcelain")
    attempts = []
    children = []

    def inert_python_spawn(argv, cwd, out_fh, err_fh, child_env):
        attempts.append(list(argv))
        # Preserve the prompt at the real process boundary without invoking Claude.
        proc = subprocess.Popen(
            [sys.executable, "-c", "pass", argv[-1]],
            cwd=cwd, env=child_env, stdin=subprocess.DEVNULL,
            stdout=out_fh, stderr=err_fh,
        )
        children.append(proc)
        return proc

    try:
        result = L.launch_build(
            repo, 656,
            _valid_premise(
                repo, charter="detective", budget="1" + chr(0xD800) + "h",
            ),
            _all_checks(), str(tmp_path / "logs"), model="opus",
            spawn_fn=inert_python_spawn, settle_seconds=0.3,
        )
    finally:
        for proc in children:
            if proc.poll() is None:
                proc.terminate()
            proc.wait(timeout=10)

    assert result["ok"] is False, result
    assert result["reason"] == "premise-budget-invalid"
    assert attempts == []
    assert owner_work() == before
    assert _git(repo, "worktree", "list", "--porcelain") == worktrees_before
    records = ll.read(repo)["records"]
    reserved = [r for r in records if r.get("event") == "reserved"]
    assert len(reserved) == 1
    assert reserved[0]["launchId"] == result["launchId"]
    assert reserved[0]["charter"] == "detective"
    refused = [
        r for r in records
        if r.get("event") == "refused" and r.get("launchId") == result["launchId"]
    ]
    assert len(refused) == 1
    assert refused[0]["stage"] == "premise"
    assert refused[0]["reason"] == "premise-budget-invalid"
    assert not [r for r in records if r.get("event") == "started"]
    assert ll.fold(records)["ok"] is True
