"""An aborted decisions carry preserves the previous destination contents."""
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


def test_failed_registry_commit_preserves_both_decisions_copies(
        tmp_path, isolated_default_store_root, monkeypatch):
    # axis: a refused registry commit preserves both decisions copies byte for byte.
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"],
                   check=True, capture_output=True)
    cwd = str(repo)
    root = os.path.realpath(isolated_default_store_root)
    ident = store_core.derive_identifiers(cwd)
    assert mode_registry.write_registry(
        cwd, mode_registry.IN_REPO, ident["remote_hash"], root=root) is not None
    calibration = repo / ".claude" / "superheroes"
    calibration.mkdir(parents=True)
    (calibration / "core.md").write_text(
        core_md.render_core(
            {"verifyCommand": "app-test", "stackTags": [],
             "threatModel": "single owner", "patterns": ""},
            "confirmed", "2026-01-01", "2026-01-01"),
        encoding="utf-8")
    (calibration / "review-crew.md").write_text(
        "## Focus hints\n- current\n", encoding="utf-8")
    name = review_store.FILENAMES["decisions"]
    source = repo / ".claude" / name
    source_before = b'{"source": true}\n'
    destination_before = b'{"previous": true}\n'
    source.write_bytes(source_before)
    config = Path(mode_registry.project_store_dir(cwd, root)) / mode_registry.CONFIG_DIRNAME
    config.mkdir(parents=True, exist_ok=True)
    destination = config / name
    destination.write_bytes(destination_before)
    migration = mode_migrate.plan(
        cwd, mode_registry.GLOBAL, root=root, owner_authorized=True,
        review_root=str(tmp_path / "review-store"),
        test_pilot_root=str(tmp_path / "pilot-store"))
    assert any(entry["src"] == str(source) and entry["dst"] == str(destination)
               for entry in migration.files)
    registry_path = mode_registry.registry_path(cwd, root)
    real_write = store_core.atomic_write
    attempts = []

    def fail_registry_write(path, text, *args, **kwargs):
        if os.fspath(path) == registry_path:
            attempts.append(os.fspath(path))
            raise OSError("simulated registry commit failure")
        return real_write(path, text, *args, **kwargs)

    monkeypatch.setattr(store_core, "atomic_write", fail_registry_write)
    assert mode_migrate.execute(migration, root=root) == {"status": "blocked"}
    assert attempts == [registry_path]
    assert mode_registry.read_registry(cwd, root)["storageMode"] == mode_registry.IN_REPO
    assert source.read_bytes() == source_before
    assert destination.is_file(), "abort removed the existing decisions destination"
    assert destination.read_bytes() == destination_before
