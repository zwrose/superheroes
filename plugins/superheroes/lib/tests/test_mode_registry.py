# new file: test_mode_registry.py
import json, os, subprocess
import mode_registry as mr


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
