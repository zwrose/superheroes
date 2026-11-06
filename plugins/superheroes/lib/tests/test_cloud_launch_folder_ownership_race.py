"""Destroying work: failed setup must preserve a competing directory's bytes."""
import os
from pathlib import Path

import launch_ledger as ll

from test_launcher import L
from test_launcher_cloud import _cloud_repo


def test_setup_claims_the_path_atomically_or_preserves_competing_work(tmp_path, monkeypatch):
    # axis: cleanup ownership -- a destination created by another operation survives setup failure.
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger-root"))
    monkeypatch.setenv(L.WORKTREES_ROOT_ENV, str(tmp_path / "wt-root"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    primary = _cloud_repo(tmp_path)
    folder = Path(L.cloud_launch_folder_path(primary))
    draft = folder / "owner-notes.txt"
    contents = "Uncommitted work belonging to the competing operation.\n"
    real_git = L._git_scrubbed
    raced = []

    def interleave(repo_root, *args, **kwargs):
        if args and args[0] == "clone" and not raced:
            # Pin: competing creation happens immediately before the real clone.
            # Interleavings during object transfer or cleanup are not exercised.
            try:
                folder.mkdir(parents=True)
            except FileExistsError:
                # An implementation that already reserved the path closes this window.
                pass
            else:
                draft.write_text(contents, encoding="utf-8")
                raced.append(True)
        return real_git(repo_root, *args, **kwargs)

    monkeypatch.setattr(L, "_git_scrubbed", interleave)
    result = L.ensure_cloud_launch_folder(primary)

    if raced:
        assert draft.is_file(), "failed setup deleted a directory it did not create"
        assert draft.read_text(encoding="utf-8") == contents
        assert result["ok"] is False, result
    else:
        assert result["ok"] is True, result
