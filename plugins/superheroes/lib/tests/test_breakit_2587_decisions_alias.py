"""#2587: a legacy directory alias must not delete carried decisions."""
import os
from pathlib import Path
import subprocess
import sys

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import calibration_paths  # noqa: E402
import core_md  # noqa: E402
import mode_migrate  # noqa: E402
import mode_registry  # noqa: E402
import review_store  # noqa: E402
import store_core  # noqa: E402


def test_flip_preserves_decisions_when_legacy_directory_aliases_target(tmp_path):
    # axis: a successful in-repo-to-global flip retains carried decisions when a legacy directory aliases their destination
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"],
                   check=True, capture_output=True)
    cwd = str(repo)
    root = str(tmp_path / "registry-store")
    review_root = str(tmp_path / "legacy-review-store")
    ident = store_core.derive_identifiers(cwd)
    assert mode_registry.write_registry(
        cwd, mode_registry.IN_REPO, ident["remote_hash"], root=root) is not None

    source_cal = repo / calibration_paths.IN_REPO_DIR
    source_cal.mkdir(parents=True)
    (source_cal / core_md.CORE_FILENAME).write_text(
        core_md.render_core(
            {"verifyCommand": "pytest", "stackTags": [],
             "threatModel": "single-user", "patterns": ""},
            "confirmed", "2026-01-01", "2026-01-01"),
        encoding="utf-8")
    (source_cal / review_store.UNIFIED_LAYER).write_text(
        "## Focus hints\n- current\n", encoding="utf-8")
    name = review_store.FILENAMES["decisions"]
    expected = '{"ownerDecision": "keep"}\n'
    (repo / ".claude" / name).write_text(expected, encoding="utf-8")

    config = Path(mode_registry.project_store_dir(cwd, root)) / mode_registry.CONFIG_DIRNAME
    config.mkdir(parents=True, exist_ok=True)
    target = config / name
    target.write_text('{"previous": true}\n', encoding="utf-8")
    entry = (Path(review_root) / calibration_paths.LEGACY_STORE_ENTRIES_DIRNAME
             / ident["gitdir_hash"])
    entry.parent.mkdir(parents=True)
    entry.symlink_to(config, target_is_directory=True)
    store_core.write_pointer(review_root, ident["gitdir_hash"], ident["gitdir_hash"])
    assert os.path.samefile(entry / name, target)

    migration = mode_migrate.plan(
        cwd, mode_registry.GLOBAL, root=root, owner_authorized=True,
        review_root=review_root, test_pilot_root=str(tmp_path / "legacy-pilot-store"))
    assert migration.blocked is False
    result = mode_migrate.execute(migration, root=root)
    assert result["status"] == "done" and set(result) <= {"status", "overwritten"}
    # axis: the destination the carry overwrote keeps its prior bytes in the backup folder
    assert [Path(o["backup"]).read_text(encoding="utf-8") for o in result["overwritten"]] == ['{"previous": true}\n']
    assert mode_registry.read_registry(cwd, root)["storageMode"] == mode_registry.GLOBAL
    assert target.is_file(), "successful flip deleted the carried decisions through an alias"
    assert target.read_text(encoding="utf-8") == expected
