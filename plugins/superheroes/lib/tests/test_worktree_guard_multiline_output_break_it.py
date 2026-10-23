"""Bites on destructive heredoc output forwarded to a shell across lines."""
import subprocess

import pytest

import mode_registry
import worktree_guard as wg


def _git(repo, *args):
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, capture_output=True, text=True,
    )


@pytest.mark.parametrize("command", [
    "sh < <(\ncat <<'EOF'\ngit reset --hard\nEOF\n)",
    "(\ncat <<'EOF'\ngit reset --hard\nEOF\n) | sh",
], ids=["process-substitution", "grouped-pipeline"])
def test_multiline_heredoc_output_executed_by_shell_is_denied(tmp_path, monkeypatch, command):
    # Axis: forwarding a data consumer's output must not hide an executable discard.
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
    decision, reason = wg.classify(command, str(repo))
    assert decision == "deny", (command, reason)
