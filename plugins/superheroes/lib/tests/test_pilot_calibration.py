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
    assert result == {"declares": True, "reason": pc.REASON_DECLARED, "path": path}


def test_declares_slots_no_calibration(tmp_path, monkeypatch):
    # axis: no-calibration when store resolves no profile
    _patch_resolve(monkeypatch, None, exists=False)
    result = pc.declares_slots("/fake/repo")
    assert result == {
        "declares": False,
        "reason": pc.REASON_NO_CALIBRATION,
        "path": None,
    }


def test_declares_slots_no_config_block(tmp_path, monkeypatch):
    # axis: no-config-block when profile has no fenced block
    path = _write_profile(tmp_path, "# prose only\n")
    _patch_resolve(monkeypatch, path)
    result = pc.declares_slots("/fake/repo")
    assert result == {
        "declares": False,
        "reason": pc.REASON_NO_CONFIG_BLOCK,
        "path": path,
    }


def test_declares_slots_config_unparseable(tmp_path, monkeypatch):
    # axis: config-unparseable when block JSON is invalid
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
        "declares": False,
        "reason": pc.REASON_CONFIG_UNPARSEABLE,
        "path": path,
    }


def test_declares_slots_no_pilot_block(tmp_path, monkeypatch):
    # axis: no-pilot-block when config has no pilot object
    path = _write_profile(tmp_path, _profile_text({"schemaVersion": 1}))
    _patch_resolve(monkeypatch, path)
    result = pc.declares_slots("/fake/repo")
    assert result == {
        "declares": False,
        "reason": pc.REASON_NO_PILOT_BLOCK,
        "path": path,
    }


def test_declares_slots_credential_set_empty(tmp_path, monkeypatch):
    # axis: credential-set-empty when credentialSet is absent or empty
    path = _write_profile(
        tmp_path,
        _profile_text({"schemaVersion": 1, "pilot": {}}),
    )
    _patch_resolve(monkeypatch, path)
    result = pc.declares_slots("/fake/repo")
    assert result == {
        "declares": False,
        "reason": pc.REASON_CREDENTIAL_SET_EMPTY,
        "path": path,
    }


def test_declares_slots_resolver_raises(monkeypatch):
    # axis: resolver raises → no-calibration, no exception escapes
    def boom(repo_root, root):
        raise RuntimeError("resolve failed")

    monkeypatch.setattr(pc.store, "resolve", boom)
    result = pc.declares_slots("/fake/repo")
    assert result == {
        "declares": False,
        "reason": pc.REASON_NO_CALIBRATION,
        "path": None,
    }


def test_declares_slots_repo_root_none():
    # axis: repo_root None → no-calibration
    result = pc.declares_slots(None)
    assert result == {
        "declares": False,
        "reason": pc.REASON_NO_CALIBRATION,
        "path": None,
    }


def test_declares_slots_repo_root_empty():
    # axis: repo_root empty → no-calibration
    result = pc.declares_slots("")
    assert result == {
        "declares": False,
        "reason": pc.REASON_NO_CALIBRATION,
        "path": None,
    }


def test_declares_slots_unreadable_profile(tmp_path, monkeypatch):
    # axis: unreadable profile path → no-config-block
    missing = str(tmp_path / "missing-profile.md")
    _patch_resolve(monkeypatch, missing)
    result = pc.declares_slots("/fake/repo")
    assert result == {
        "declares": False,
        "reason": pc.REASON_NO_CONFIG_BLOCK,
        "path": missing,
    }


def test_declares_slots_invalid_credential_entries_still_declared(tmp_path, monkeypatch):
    # axis: presence not validation — contract-invalid credentialSet still declared
    path = _write_profile(
        tmp_path,
        _profile_text({
            "schemaVersion": 1,
            "pilot": {"credentialSet": [{"account": "a"}]},
        }),
    )
    _patch_resolve(monkeypatch, path)
    result = pc.declares_slots("/fake/repo")
    assert result == {"declares": True, "reason": pc.REASON_DECLARED, "path": path}


def test_declares_slots_pilot_not_dict(tmp_path, monkeypatch):
    # axis: pilot block not a dict → no-pilot-block
    path = _write_profile(
        tmp_path,
        _profile_text({"schemaVersion": 1, "pilot": []}),
    )
    _patch_resolve(monkeypatch, path)
    result = pc.declares_slots("/fake/repo")
    assert result == {
        "declares": False,
        "reason": pc.REASON_NO_PILOT_BLOCK,
        "path": path,
    }


def test_declares_slots_config_not_object(tmp_path, monkeypatch):
    # axis: parsed config not an object → config-unparseable
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
        "declares": False,
        "reason": pc.REASON_CONFIG_UNPARSEABLE,
        "path": path,
    }


def test_declares_slots_credential_set_not_list(tmp_path, monkeypatch):
    # axis: credentialSet not a list → credential-set-empty
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
        "declares": False,
        "reason": pc.REASON_CREDENTIAL_SET_EMPTY,
        "path": path,
    }
