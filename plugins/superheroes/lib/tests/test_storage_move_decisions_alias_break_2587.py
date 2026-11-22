"""A storage flip preserves decisions when their slot directories alias."""
import os
from pathlib import Path
import subprocess
import sys

_LIB = str(Path(__file__).resolve().parents[1])
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import core_md  # noqa: E402
import mode_migrate  # noqa: E402
import mode_registry  # noqa: E402
import review_store  # noqa: E402
import store_core  # noqa: E402


def test_flip_preserves_decisions_through_a_linked_parent(
        tmp_path, isolated_default_store_root):
    # axis: aliasing the decisions slots through a directory link never destroys their shared file.
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(
        ["git", "-C", str(repo), "init", "-q"],
        check=True, capture_output=True)
    cwd = str(repo)
    root = os.path.realpath(isolated_default_store_root)
    remote_key = store_core.derive_identifiers(cwd)["remote_hash"]
    assert mode_registry.write_registry(
        cwd, mode_registry.IN_REPO, remote_key, root=root) is not None

    config = Path(mode_registry.project_store_dir(cwd, root)) / mode_registry.CONFIG_DIRNAME
    config.mkdir(parents=True, exist_ok=True)
    (repo / ".claude").symlink_to(config, target_is_directory=True)
    calibration = repo / ".claude" / "superheroes"
    calibration.mkdir()
    core = core_md.render_core(
        {"verifyCommand": "app-test", "stackTags": [],
         "threatModel": "single owner", "patterns": ""},
        "confirmed", "2026-01-01", "2026-01-01")
    (calibration / "core.md").write_text(core, encoding="utf-8")
    (calibration / "review-crew.md").write_text(
        "## Focus hints\n- preserve decisions\n", encoding="utf-8")

    filename = review_store.FILENAMES["decisions"]
    decisions = config / filename
    payload = b'{"keep": true}\n'
    decisions.write_bytes(payload)
    assert os.path.samefile(decisions, repo / ".claude" / filename)

    migration = mode_migrate.plan(
        cwd, mode_registry.GLOBAL, root=root, owner_authorized=True,
        review_root=str(tmp_path / "review-store"),
        test_pilot_root=str(tmp_path / "pilot-store"))
    result = mode_migrate.execute(migration, root=root)
    assert result["status"] in {"done", "blocked"}
    assert decisions.is_file(), "the flip deleted the shared decisions file"
    assert decisions.read_bytes() == payload
