from pathlib import Path

import pytest

from test_adopt_head_on_base import _commit_on, _fork_and_main
from test_launcher import L, _all_checks, _valid_premise
from test_launcher_cloud import _git, _isolated  # noqa: F401


def test_refused_adoption_preserves_work_and_creates_no_worktree(tmp_path, monkeypatch):
    # axis: refusal precedes worktree creation and preserves all uncommitted owner changes.
    repo, base, older = _fork_and_main(tmp_path, cloud=False)
    adopted_head = _commit_on(repo, older)
    managed_root = tmp_path / "managed-worktrees"
    monkeypatch.setenv(L.WORKTREES_ROOT_ENV, str(managed_root))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "config"))

    tracked = Path(repo) / "file.txt"
    tracked.write_text("staged owner change\n")
    _git(repo, "add", "file.txt")
    tracked.write_text("unstaged owner change\n")
    untracked = Path(repo) / "owner-notes.txt"
    untracked.write_text("irreplaceable owner notes\n")

    def snapshot():
        return (
            _git(repo, "status", "--porcelain=v1", "--untracked-files=all"),
            _git(repo, "diff", "--binary"),
            _git(repo, "diff", "--cached", "--binary"),
            _git(repo, "worktree", "list", "--porcelain"),
            _git(repo, "rev-parse", "HEAD"),
        )

    before = snapshot()
    assert before[1] and before[2]
    assert "?? owner-notes.txt" in before[0]

    def unexpected_spawn(*args, **kwargs):
        pytest.fail("a refused adoption must not spawn a child")

    premise = _valid_premise(
        repo, baseCommit=base,
        adoptsBranch="feature/adopted-2002", adoptsHead=adopted_head,
    )
    result = L.launch_build(
        repo, 656, premise, _all_checks(), str(tmp_path / "logs"),
        spawn_fn=unexpected_spawn, settle_seconds=0.2,
    )

    assert result["ok"] is False
    assert result["reason"] == "premise-adopts-head-not-on-base"
    assert result["ancestry"] == "not-descendant"
    assert snapshot() == before
    assert tracked.read_text() == "unstaged owner change\n"
    assert untracked.read_text() == "irreplaceable owner notes\n"
    assert not managed_root.exists()
