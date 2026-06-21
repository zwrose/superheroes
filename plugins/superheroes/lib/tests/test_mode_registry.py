# new file: test_mode_registry.py
import json, os, subprocess
import pytest
import mode_registry as mr


def _write_raw(cwd, root, obj):
    d = mr.ensure_project_store(cwd, root=root)
    mr_store_core = __import__("store_core")
    mr_store_core.atomic_write(os.path.join(d, "registry.json"), json.dumps(obj))


def _init_repo(d, remote=None):
    subprocess.run(["git", "-C", str(d), "init", "-q"], check=True)
    if remote:
        subprocess.run(["git", "-C", str(d), "remote", "add", "origin", remote], check=True)


def test_config_key_prefers_remote_and_is_16hex(tmp_path):
    _init_repo(tmp_path, "git@github.com:org/repo.git")
    k = mr.config_key(str(tmp_path))
    assert len(k) == 16 and all(c in "0123456789abcdef" for c in k)


def test_config_key_falls_back_to_common_dir_when_no_remote(tmp_path):
    _init_repo(tmp_path)
    import store_core as sc
    assert mr.config_key(str(tmp_path)) == sc.derive_identifiers(str(tmp_path))["gitdir_hash"]


def test_ensure_project_store_creates_git_and_meta(tmp_path):
    _init_repo(tmp_path)
    d = mr.ensure_project_store(str(tmp_path), root=str(tmp_path / "store"))
    assert d is not None
    assert os.path.isdir(os.path.join(d, ".git"))
    assert json.load(open(os.path.join(d, "meta.json")))["schemaVersion"] == mr.SCHEMA_VERSION


def test_ensure_project_store_is_idempotent(tmp_path):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    a = mr.ensure_project_store(str(tmp_path), root=root)
    b = mr.ensure_project_store(str(tmp_path), root=root)
    assert a == b  # same dir, no error on second touch


def test_config_lock_is_nonblocking_and_exclusive(tmp_path):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    mr.ensure_project_store(str(tmp_path), root=root)
    with mr.config_lock(str(tmp_path), root=root) as got1:
        assert got1 is True
        with mr.config_lock(str(tmp_path), root=root) as got2:
            assert got2 is False        # held by the outer context — never blocks
    with mr.config_lock(str(tmp_path), root=root) as got3:
        assert got3 is True             # released after the outer context closed


def test_write_then_read_roundtrips(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    rec = mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root, now="2026-06-21T00:00:00Z")
    assert rec["storageMode"] == mr.IN_REPO and rec["schemaVersion"] == 1
    assert mr.read_registry(str(tmp_path), root=root)["storageMode"] == mr.IN_REPO


def test_read_unknown_newer_version_fails_closed(tmp_path):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    _write_raw(str(tmp_path), root, {"schemaVersion": 999, "storageMode": "in-repo"})
    with pytest.raises(mr.UnknownSchemaVersion):
        mr.read_registry(str(tmp_path), root=root)


def test_read_semantically_invalid_is_treated_as_absent(tmp_path):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    _write_raw(str(tmp_path), root, {"schemaVersion": 1, "storageMode": "bogus"})
    assert mr.read_registry(str(tmp_path), root=root) is None


def test_write_refuses_to_change_sticky_mode(tmp_path):
    _init_repo(tmp_path)
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.GLOBAL, None, root=root)
    assert mr.write_registry(str(tmp_path), mr.IN_REPO, None, root=root) is None   # refused
    assert mr.read_registry(str(tmp_path), root=root)["storageMode"] == mr.GLOBAL  # preserved
    # explicit migration is allowed
    assert mr.write_registry(str(tmp_path), mr.IN_REPO, None, root=root, allow_migration=True)["storageMode"] == mr.IN_REPO
