import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_calibration as pc  # noqa: E402


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


def test_declares_slots_credential_set_empty(tmp_path, monkeypatch):
    # axis: absent / credential-set-empty when credentialSet is absent or empty
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
