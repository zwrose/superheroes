"""#2587: a storage flip must preserve decisions when directory paths alias."""
import os
from pathlib import Path
import subprocess
import sys

_LIB = str(Path(__file__).resolve().parents[1])
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import mode_migrate as mm  # noqa: E402
import mode_registry as mr  # noqa: E402
import store_core  # noqa: E402


def test_flip_preserves_decisions_when_storage_directories_alias(
        tmp_path, isolated_default_store_root):
    # axis: carrying decisions between two names for one file never deletes its only copy.
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"],
                   check=True, capture_output=True)
    cwd = str(repo)
    root = str(isolated_default_store_root)
    ident = store_core.derive_identifiers(cwd)
    assert mr.write_registry(cwd, mr.IN_REPO, ident["remote_hash"], root=root) is not None

    claude = repo / ".claude"
    claude.mkdir()
    source = claude / "review-decisions.json"
    original = b'{"ownerDecision": "keep"}\n'
    source.write_bytes(original)
    config = Path(mr.project_store_dir(cwd, root)) / mr.CONFIG_DIRNAME
    config.symlink_to(claude, target_is_directory=True)
    destination = config / source.name
    assert os.path.samefile(source, destination)

    migration = mm.plan(
        cwd, mr.GLOBAL, root=root, owner_authorized=True,
        review_root=str(tmp_path / "legacy-review"),
        test_pilot_root=str(tmp_path / "legacy-pilot"))
    result = mm.execute(migration, root=root)
    assert result["status"] in ("done", "blocked")
    assert destination.is_file(), "the flip deleted the only decisions copy through its alias"
    assert destination.read_bytes() == original
