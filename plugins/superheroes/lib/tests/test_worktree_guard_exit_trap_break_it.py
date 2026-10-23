"""Bites on a pending EXIT trap executing a masked heredoc script."""
import subprocess

import mode_registry
import worktree_guard as wg


def _git(repo, *args):
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, capture_output=True, text=True,
    )


def test_exit_trap_must_not_hide_a_destructive_heredoc(tmp_path, monkeypatch):
    # Axis: a pending EXIT handler can execute heredoc text without a later command line.
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    tracked = repo / "f.txt"
    tracked.write_text("committed\n")
    _git(repo, "add", "f.txt")
    _git(repo, "-c", "user.name=Test", "-c", "user.email=t@example.invalid",
         "-c", "commit.gpgsign=false", "commit", "-qm", "init")
    tracked.write_text("PRIOR_UNCOMMITTED_DELIVERY\n")
    monkeypatch.setattr(mode_registry, "calibration_state", lambda cwd: "calibrated")
    assert wg.classify("git reset --hard", str(repo))[0] == "deny"
    command = (
        "trap 'bash ./discard.sh' EXIT\n"
        "cat > ./discard.sh <<'EOF'\n"
        "git reset --hard\n"
        "EOF"
    )
    decision, reason = wg.classify(command, str(repo))
    assert decision == "deny", (command, reason)
