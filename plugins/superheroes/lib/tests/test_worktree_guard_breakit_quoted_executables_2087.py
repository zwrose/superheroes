from pathlib import Path
import subprocess

import pytest
import worktree_guard as wg
from test_worktree_guard_shell_program import dirty_repo


@pytest.mark.parametrize("command", [
    '"eval" "git reset --hard"',
    "bash -c '\"eval\" \"git reset --hard\"'",
    'env "bash" -c "git reset --hard"',
    'command "bash" -c "git reset --hard"',
])
def test_quoted_executable_cannot_hide_a_discard(command, dirty_repo):
    # Axis: quoting executable names must not bypass discard protection.
    target = Path(dirty_repo) / "f.txt"
    assert target.read_bytes() == b"PRIOR_UNCOMMITTED_DELIVERY"
    decision, reason = wg.classify(command, dirty_repo)
    subprocess.run(["bash", "-c", command], cwd=dirty_repo,
                   check=True, capture_output=True, text=True)
    assert target.read_bytes() == b"committed\n"
    assert decision == "deny", (command, reason)
