from pathlib import Path
import subprocess

import pytest
import worktree_guard as wg
from test_worktree_guard_shell_program import dirty_repo


@pytest.mark.parametrize("command", [
    "bash -c 'git reset --hard>/dev/null'",
    "eval 'git reset --hard>/dev/null'",
])
def test_attached_redirection_cannot_hide_hard_reset(command, dirty_repo):
    # Axis: an adjacent redirection must not hide a destructive Git flag.
    target = Path(dirty_repo) / "f.txt"
    assert target.read_bytes() == b"PRIOR_UNCOMMITTED_DELIVERY"
    decision, reason = wg.classify(command, dirty_repo)
    subprocess.run(["bash", "-c", command], cwd=dirty_repo,
                   check=True, capture_output=True, text=True)
    assert target.read_bytes() == b"committed\n"
    assert decision == "deny", (command, reason)
