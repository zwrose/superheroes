import shlex
import subprocess
from pathlib import Path

import pytest
import worktree_guard as wg
from test_worktree_guard_shell_program import dirty_repo


@pytest.mark.parametrize("launcher", ["bash -c", "eval"])
@pytest.mark.parametrize("prefix", ["exec", "command", "env"])
def test_quoted_git_after_execution_wrapper_is_denied(launcher, prefix, dirty_repo):
    # Axis: whole-word executable quoting behind a wrapper must preserve discard protection.
    command = launcher + " " + shlex.quote(f'{prefix} "git" reset --hard')
    target = Path(dirty_repo) / "f.txt"
    assert target.read_bytes() == b"PRIOR_UNCOMMITTED_DELIVERY"
    decision, reason = wg.classify(command, dirty_repo)
    subprocess.run(["bash", "-c", command], cwd=dirty_repo,
                   check=True, capture_output=True, text=True)
    assert target.read_bytes() == b"committed\n"
    assert decision == "deny", (command, reason)
