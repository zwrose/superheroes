import json
import os
import stat
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_calibration as pc  # noqa: E402
import store  # noqa: E402


_LAYER = (
    "## Machine-readable config\n\n"
    "```json test-pilot-config\n"
    '{"schemaVersion": 1, "pilot": {"credentialSet": [{"account": "a", "role": "admin"}]}}\n'
    "```\n"
)


def _init_repo(path):
    path = str(path)
    subprocess.run(["git", "init", "-q", path], check=True,
                   capture_output=True, text=True)
    return path


def _write_in_repo_layer(repo, text=_LAYER):
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "test-pilot.md")
    open(p, "w", encoding="utf-8").write(text)
    return p


def _profile_text(config_obj):
    block = json.dumps(config_obj)
    return (
        "## Machine-readable config\n\n"
        "```json test-pilot-config\n"
        f"{block}\n"
        "```\n"
    )


def _write_profile(tmp_path, text):
    path = tmp_path / "profile.md"
    path.write_text(text, encoding="utf-8")
    return str(path)


def _patch_resolve(monkeypatch, profile_path, exists=True):
    def fake_resolve(repo_root, root):
        if not exists:
            return {"exists": False, "profile": None}
        return {"exists": True, "profile": profile_path}

    monkeypatch.setattr(pc.store, "resolve", fake_resolve)


def test_declares_slots_declared(tmp_path, monkeypatch):
    # axis: declared when pilot block has non-empty credentialSet
    path = _write_profile(
        tmp_path,
        _profile_text({
            "schemaVersion": 1,
            "pilot": {"credentialSet": [{"account": "a", "role": "admin"}]},
        }),
    )
    _patch_resolve(monkeypatch, path)
    result = pc.declares_slots("/fake/repo")
    assert result == {
        "state": pc.STATE_DECLARED,
        "cause": pc.CAUSE_DECLARED,
        "path": path,
    }


def test_declares_slots_no_calibration(tmp_path, monkeypatch):
    # axis: absent / no-calibration when store resolves no profile
    _patch_resolve(monkeypatch, None, exists=False)
    result = pc.declares_slots("/fake/repo")
    assert result == {
        "state": pc.STATE_ABSENT,
        "cause": pc.CAUSE_NO_CALIBRATION,
        "path": None,
    }


def test_declares_slots_no_pilot_block(tmp_path, monkeypatch):
    # axis: absent / no-pilot-block when config has no pilot object
    path = _write_profile(tmp_path, _profile_text({"schemaVersion": 1}))
    _patch_resolve(monkeypatch, path)
    result = pc.declares_slots("/fake/repo")
    assert result == {
        "state": pc.STATE_ABSENT,
        "cause": pc.CAUSE_NO_PILOT_BLOCK,
        "path": path,
    }


def test_declares_slots_credential_set_absent(tmp_path, monkeypatch):
    # axis: absent / credential-set-empty when credentialSet key is absent
    path = _write_profile(
        tmp_path,
        _profile_text({"schemaVersion": 1, "pilot": {}}),
    )
    _patch_resolve(monkeypatch, path)
    result = pc.declares_slots("/fake/repo")
    assert result == {
        "state": pc.STATE_ABSENT,
        "cause": pc.CAUSE_CREDENTIAL_SET_EMPTY,
        "path": path,
    }


def test_declares_slots_credential_set_empty_list(tmp_path, monkeypatch):
    # axis: absent / credential-set-empty when credentialSet is an empty list
    path = _write_profile(
        tmp_path,
        _profile_text({"schemaVersion": 1, "pilot": {"credentialSet": []}}),
    )
    _patch_resolve(monkeypatch, path)
    result = pc.declares_slots("/fake/repo")
    assert result == {
        "state": pc.STATE_ABSENT,
        "cause": pc.CAUSE_CREDENTIAL_SET_EMPTY,
        "path": path,
    }


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses chmod 000")
def test_declares_slots_unreadable_in_repo_layer(tmp_path, monkeypatch):
    # axis: cannot-tell / calibration-unresolved when layer exists but is unreadable
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    layer = _write_in_repo_layer(repo)
    os.chmod(layer, 0o000)
    try:
        result = pc.declares_slots(repo)
    finally:
        os.chmod(layer, stat.S_IMODE(os.stat(layer).st_mode) | 0o600)
    assert result == {
        "state": pc.STATE_CANNOT_TELL,
        "cause": pc.CAUSE_CALIBRATION_UNRESOLVED,
        "path": layer,
    }


def test_declares_slots_no_candidate_files(tmp_path, monkeypatch):
    # axis: absent / no-calibration when no candidate calibration path exists
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    monkeypatch.setattr(pc.store, "store_root", lambda: root)
    result = pc.declares_slots(repo)
    assert result == {
        "state": pc.STATE_ABSENT,
        "cause": pc.CAUSE_NO_CALIBRATION,
        "path": None,
    }


def test_candidate_profile_paths_matches_resolve_precedence(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    root = str(tmp_path / "store")
    candidates = store.candidate_profile_paths(repo, root)
    assert candidates[0] == os.path.join(
        repo, ".claude", "test-pilot", "profile.md")
    assert candidates[-1].endswith(os.path.join("config", "test-pilot.md"))
    assert os.path.join(repo, ".claude", "superheroes", "test-pilot.md") in candidates


@pytest.mark.parametrize("repo_root", [None, ""])
def test_declares_slots_repo_root_invalid(repo_root):
    # axis: cannot-tell / repo-root-invalid when repo_root is not a non-empty str
    result = pc.declares_slots(repo_root)
    assert result == {
        "state": pc.STATE_CANNOT_TELL,
        "cause": pc.CAUSE_REPO_ROOT_INVALID,
        "path": None,
    }


def test_declares_slots_resolver_raises(monkeypatch):
    # axis: cannot-tell / resolver-failed when store.resolve raises
    def boom(repo_root, root):
        raise RuntimeError("resolve failed")

    monkeypatch.setattr(pc.store, "resolve", boom)
    result = pc.declares_slots("/fake/repo")
    assert result == {
        "state": pc.STATE_CANNOT_TELL,
        "cause": pc.CAUSE_RESOLVER_FAILED,
        "path": None,
    }


def test_declares_slots_unreadable_profile(tmp_path, monkeypatch):
    # axis: cannot-tell / calibration-unreadable when profile file cannot be read
    missing = str(tmp_path / "missing-profile.md")
    _patch_resolve(monkeypatch, missing)
    result = pc.declares_slots("/fake/repo")
    assert result == {
        "state": pc.STATE_CANNOT_TELL,
        "cause": pc.CAUSE_CALIBRATION_UNREADABLE,
        "path": missing,
    }


def test_declares_slots_no_config_block(tmp_path, monkeypatch):
    # axis: cannot-tell / no-config-block when profile has no fenced block
    path = _write_profile(tmp_path, "# prose only\n")
    _patch_resolve(monkeypatch, path)
    result = pc.declares_slots("/fake/repo")
    assert result == {
        "state": pc.STATE_CANNOT_TELL,
        "cause": pc.CAUSE_NO_CONFIG_BLOCK,
        "path": path,
    }


def test_declares_slots_config_unparseable(tmp_path, monkeypatch):
    # axis: cannot-tell / config-unparseable when block JSON is invalid
    text = (
        "## Machine-readable config\n\n"
        "```json test-pilot-config\n"
        "{not json}\n"
        "```\n"
    )
    path = _write_profile(tmp_path, text)
    _patch_resolve(monkeypatch, path)
    result = pc.declares_slots("/fake/repo")
    assert result == {
        "state": pc.STATE_CANNOT_TELL,
        "cause": pc.CAUSE_CONFIG_UNPARSEABLE,
        "path": path,
    }


def test_declares_slots_pilot_block_malformed(tmp_path, monkeypatch):
    # axis: cannot-tell / pilot-block-malformed when pilot is not an object
    path = _write_profile(
        tmp_path,
        _profile_text({"schemaVersion": 1, "pilot": []}),
    )
    _patch_resolve(monkeypatch, path)
    result = pc.declares_slots("/fake/repo")
    assert result == {
        "state": pc.STATE_CANNOT_TELL,
        "cause": pc.CAUSE_PILOT_BLOCK_MALFORMED,
        "path": path,
    }


def test_declares_slots_credential_set_malformed(tmp_path, monkeypatch):
    # axis: cannot-tell / credential-set-malformed when credentialSet is not a list
    path = _write_profile(
        tmp_path,
        _profile_text({
            "schemaVersion": 1,
            "pilot": {"credentialSet": "not-a-list"},
        }),
    )
    _patch_resolve(monkeypatch, path)
    result = pc.declares_slots("/fake/repo")
    assert result == {
        "state": pc.STATE_CANNOT_TELL,
        "cause": pc.CAUSE_CREDENTIAL_SET_MALFORMED,
        "path": path,
    }


def test_declares_slots_config_not_object(tmp_path, monkeypatch):
    # axis: cannot-tell / config-unparseable when parsed config is not an object
    text = (
        "## Machine-readable config\n\n"
        "```json test-pilot-config\n"
        "[]\n"
        "```\n"
    )
    path = _write_profile(tmp_path, text)
    _patch_resolve(monkeypatch, path)
    result = pc.declares_slots("/fake/repo")
    assert result == {
        "state": pc.STATE_CANNOT_TELL,
        "cause": pc.CAUSE_CONFIG_UNPARSEABLE,
        "path": path,
    }


def test_declares_slots_invalid_utf8(tmp_path, monkeypatch):
    # axis: cannot-tell / calibration-unreadable on invalid UTF-8, no exception escapes
    path = tmp_path / "profile.md"
    path.write_bytes(b"\xff\xfe")
    _patch_resolve(monkeypatch, str(path))
    result = pc.declares_slots("/fake/repo")
    assert result == {
        "state": pc.STATE_CANNOT_TELL,
        "cause": pc.CAUSE_CALIBRATION_UNREADABLE,
        "path": str(path),
    }


def test_declares_slots_prose_only_in_repo_layer(tmp_path):
    # axis: absent / no-calibration when in-repo layer is prose-only (no config block)
    repo = _init_repo(tmp_path / "repo")
    _write_in_repo_layer(repo, "# prose only\n")
    result = pc.declares_slots(repo)
    assert result == {
        "state": pc.STATE_ABSENT,
        "cause": pc.CAUSE_NO_CALIBRATION,
        "path": None,
    }


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses chmod 000")
def test_declares_slots_unreadable_candidate_chmod(tmp_path):
    # axis: cannot-tell / calibration-unresolved when candidate exists but is unreadable
    repo = _init_repo(tmp_path / "repo")
    layer = _write_in_repo_layer(repo)
    os.chmod(layer, 0o000)
    try:
        result = pc.declares_slots(repo)
    finally:
        os.chmod(layer, stat.S_IMODE(os.stat(layer).st_mode) | 0o600)
    assert result == {
        "state": pc.STATE_CANNOT_TELL,
        "cause": pc.CAUSE_CALIBRATION_UNRESOLVED,
        "path": layer,
    }


def test_declares_slots_dangling_symlink_candidate(tmp_path):
    # axis: cannot-tell / calibration-unresolved for dangling symlink candidate
    repo = _init_repo(tmp_path / "repo")
    layer_dir = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(layer_dir, exist_ok=True)
    symlink = os.path.join(layer_dir, "test-pilot.md")
    os.symlink("/nonexistent/path/to/nowhere", symlink)
    result = pc.declares_slots(repo)
    assert result == {
        "state": pc.STATE_CANNOT_TELL,
        "cause": pc.CAUSE_CALIBRATION_UNRESOLVED,
        "path": symlink,
    }


def test_declares_slots_genuinely_empty_project(tmp_path):
    # axis: absent / no-calibration when no candidate calibration file exists
    repo = _init_repo(tmp_path / "repo")
    result = pc.declares_slots(repo)
    assert result == {
        "state": pc.STATE_ABSENT,
        "cause": pc.CAUSE_NO_CALIBRATION,
        "path": None,
    }
