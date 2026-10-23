from pathlib import Path
import shutil

import pytest
import worktree_guard as wg
from test_worktree_guard_merge import _git, _merge_repo


@pytest.mark.parametrize("command", [
    "git checkout --theirs f.txt",
    "git restore --theirs f.txt",
])
def test_trailing_space_root_cannot_hide_builder_resolution(tmp_path, monkeypatch, command):
    # Engage calibration explicitly; this test isolates merge-path inspection.
    pristine = Path(_merge_repo(tmp_path, monkeypatch))
    work = pristine.with_name(pristine.name + " ")
    shutil.copytree(pristine, work)
    target = work / "f.txt"
    target.write_text("builder's resolution\n", encoding="utf-8")

    # Axis: root whitespace must not redirect inspection to an untouched sibling.
    decision, reason = wg.classify(command, str(work))

    # Demonstrate that the candidate command really destroys this resolution.
    _git(str(work), *command.split()[1:])
    assert target.read_text(encoding="utf-8") == "main\n"
    assert decision == "deny", reason
