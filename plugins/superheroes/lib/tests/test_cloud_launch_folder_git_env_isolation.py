"""Destroying work: inherited Git redirects must preserve primary metadata."""
import os
from pathlib import Path

import launch_ledger as ll

from test_launcher import L
from test_launcher_cloud import _cloud_repo


def test_inherited_git_redirects_cannot_overwrite_primary_metadata(tmp_path, monkeypatch):
    # axis: ensure_cloud_launch_folder must not overwrite primary metadata when inherited
    # GIT_DIR/GIT_WORK_TREE redirect repository discovery away from the clone.
    monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger-root"))
    monkeypatch.setenv(L.WORKTREES_ROOT_ENV, str(tmp_path / "wt-root"))
    # Isolation: global/system configuration is disabled; owner-specific hooks and signing
    # are outside this test's claim. Repository redirects are introduced explicitly below.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    primary = Path(_cloud_repo(tmp_path))
    marker = primary / ".git" / L._CLOUD_FOLDER_MARKER
    tracked = primary / "file.txt"
    draft = primary / "owner-notes.txt"
    protected = {
        marker: b"Existing owner metadata must survive setup.\n",
        tracked: b"An uncommitted tracked edit.\n",
        draft: b"An untracked draft.\n",
    }
    for path, contents in protected.items():
        path.write_bytes(contents)

    monkeypatch.setenv("GIT_DIR", str(primary / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(primary))
    L.ensure_cloud_launch_folder(str(primary))

    for path, contents in protected.items():
        assert path.is_file(), f"setup removed primary data: {path.name}"
        assert path.read_bytes() == contents, f"setup overwrote primary data: {path.name}"
