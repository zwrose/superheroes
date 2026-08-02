"""Tests for pilot_context.py — context set creation and S3 option enforcement."""
import hashlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_context as pc  # noqa: E402
import pilot_seed as ps  # noqa: E402
import pilot_slot  # noqa: E402


def _artifact_fixture_base():
    if os.path.isdir("/private/tmp"):
        return "/private/tmp"
    return os.path.realpath(tempfile.gettempdir())


@pytest.fixture
def artifact_tmp():
    base = _artifact_fixture_base()
    path = tempfile.mkdtemp(dir=base)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _write_artifact(path, content=b"artifact-bytes", mode=0o600):
    path.write_bytes(content)
    os.chmod(path, mode)
    return hashlib.sha256(content).hexdigest()


def _artifact_dict(path, *, uid=None, mode=0o600, sha256=None, content=b"artifact-bytes"):
    if sha256 is None:
        sha256 = hashlib.sha256(content).hexdigest()
    if uid is None:
        uid = os.getuid()
    return {
        "path": str(path),
        "expectedUid": uid,
        "expectedMode": mode,
        "sha256": sha256,
    }


def _accounts(*names):
    return [{"account": name, "role": "resource-owner"} for name in names]


def _make_artifact_simple(artifact_tmp, name, content=None):
    if content is None:
        content = ("artifact-%s" % name).encode()
    artifact_path = Path(artifact_tmp) / ("%s.bin" % name)
    digest = _write_artifact(artifact_path, content=content)
    return _artifact_dict(artifact_path, sha256=digest)


# --- context_spec success -----------------------------------------------------

def test_context_spec_success_applies_required_options(artifact_tmp):
    artifact = _make_artifact_simple(artifact_tmp, "owner")
    surfaces = ["cookies", "indexedDB"]
    result = pc.context_spec("slot1@1", "owner", artifact, surfaces)
    assert result["ok"] is True
    assert result["reason"] is None
    assert result["schemaVersion"] == pc.CONTEXT_SCHEMA_VERSION
    assert result["slotRef"] == "slot1@1"
    assert result["account"] == "owner"
    assert result["contextOptions"] == {"indexedDB": True, "credentials": False}
    assert result["captureSurfaces"] == surfaces
    assert "path" in result["artifact"]
    assert "sha256" in result["artifact"]
    assert "expectedUid" not in result["artifact"]


def test_context_spec_success_with_matching_requested_options(artifact_tmp):
    artifact = _make_artifact_simple(artifact_tmp, "owner")
    surfaces = ["cookies"]
    options = ps.required_context_options(surfaces)
    result = pc.context_spec(
        "slot1@1", "owner", artifact, surfaces, requested_options=options,
    )
    assert result["ok"] is True
    assert result["contextOptions"] == options


# --- edge 1: indexedDB surface, indexedDB: False ------------------------------

def test_context_spec_refuses_indexeddb_false_when_surface_declared(artifact_tmp):
    artifact = _make_artifact_simple(artifact_tmp, "owner")
    result = pc.context_spec(
        "slot1@1",
        "owner",
        artifact,
        ["indexedDB"],
        requested_options={"indexedDB": False, "credentials": False},
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_OPTIONS_MISMATCH


# --- edge 2: webauthn surface, credentials: False -----------------------------

def test_context_spec_refuses_credentials_false_when_webauthn_declared(artifact_tmp):
    artifact = _make_artifact_simple(artifact_tmp, "owner")
    result = pc.context_spec(
        "slot1@1",
        "owner",
        artifact,
        ["webauthn"],
        requested_options={"indexedDB": False, "credentials": False},
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_OPTIONS_MISMATCH


# --- edge 3: unrequired option True -------------------------------------------

def test_context_spec_refuses_overprovisioned_credentials(artifact_tmp):
    artifact = _make_artifact_simple(artifact_tmp, "owner")
    result = pc.context_spec(
        "slot1@1",
        "owner",
        artifact,
        ["cookies"],
        requested_options={"indexedDB": False, "credentials": True},
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_OPTIONS_MISMATCH


def test_context_spec_refuses_overprovisioned_indexeddb(artifact_tmp):
    artifact = _make_artifact_simple(artifact_tmp, "owner")
    result = pc.context_spec(
        "slot1@1",
        "owner",
        artifact,
        ["cookies"],
        requested_options={"indexedDB": True, "credentials": False},
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_OPTIONS_MISMATCH


# --- edge 4: wrong keys / wrong types -----------------------------------------

def test_context_spec_refuses_requested_options_wrong_keys(artifact_tmp):
    artifact = _make_artifact_simple(artifact_tmp, "owner")
    result = pc.context_spec(
        "slot1@1",
        "owner",
        artifact,
        ["cookies"],
        requested_options={"indexedDB": False},
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_OPTIONS_MISMATCH


def test_context_spec_refuses_requested_options_wrong_types(artifact_tmp):
    artifact = _make_artifact_simple(artifact_tmp, "owner")
    result = pc.context_spec(
        "slot1@1",
        "owner",
        artifact,
        ["cookies"],
        requested_options={"indexedDB": "false", "credentials": False},
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_OPTIONS_MISMATCH


# --- edge 5: sessionStorage propagated ----------------------------------------

def test_context_spec_refuses_session_storage_surface(artifact_tmp):
    artifact = _make_artifact_simple(artifact_tmp, "owner")
    result = pc.context_spec("slot1@1", "owner", artifact, ["sessionStorage"])
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_SESSION_STORAGE


def test_session_storage_never_reaches_context_spec(artifact_tmp):
    artifact = _make_artifact_simple(artifact_tmp, "owner")
    result = pc.context_spec("slot1@1", "owner", artifact, ["sessionStorage"])
    assert result["ok"] is False
    assert "schemaVersion" not in result


# --- edge 6: unknown / duplicate surface propagated ---------------------------

def test_context_spec_refuses_unknown_surface(artifact_tmp):
    artifact = _make_artifact_simple(artifact_tmp, "owner")
    result = pc.context_spec("slot1@1", "owner", artifact, ["bogus"])
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_SURFACE_UNKNOWN


def test_context_spec_refuses_duplicate_surface(artifact_tmp):
    artifact = _make_artifact_simple(artifact_tmp, "owner")
    result = pc.context_spec("slot1@1", "owner", artifact, ["cookies", "cookies"])
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_SURFACE_DUPLICATE


# --- edge 7: empty surface list propagated ------------------------------------

def test_context_spec_refuses_empty_surfaces(artifact_tmp):
    artifact = _make_artifact_simple(artifact_tmp, "owner")
    result = pc.context_spec("slot1@1", "owner", artifact, [])
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_SURFACES_EMPTY


# --- edge 8: artifact missing propagated --------------------------------------

def test_context_spec_refuses_missing_artifact(artifact_tmp):
    missing = os.path.join(artifact_tmp, "missing.bin")
    artifact = _artifact_dict(missing)
    result = pc.context_spec("slot1@1", "owner", artifact, ["cookies"])
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_ARTIFACT_MISSING


# --- edge 9: hash mismatch propagated -----------------------------------------

def test_context_spec_refuses_hash_mismatch(artifact_tmp):
    artifact_path = Path(artifact_tmp) / "seed.bin"
    digest = _write_artifact(artifact_path, content=b"original")
    artifact_path.write_bytes(b"changed")
    artifact = _artifact_dict(artifact_path, sha256=digest)
    result = pc.context_spec("slot1@1", "owner", artifact, ["cookies"])
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_ARTIFACT_HASH_MISMATCH


# --- edge 10: owner / mode mismatch propagated --------------------------------

@pytest.mark.skipif(not hasattr(os, "getuid"), reason="no os.getuid on this platform")
def test_context_spec_refuses_owner_mismatch(artifact_tmp):
    artifact_path = Path(artifact_tmp) / "seed.bin"
    digest = _write_artifact(artifact_path)
    artifact = _artifact_dict(artifact_path, uid=os.getuid() + 1, sha256=digest)
    result = pc.context_spec("slot1@1", "owner", artifact, ["cookies"])
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_ARTIFACT_OWNER_MISMATCH


def test_context_spec_refuses_mode_mismatch(artifact_tmp):
    artifact_path = Path(artifact_tmp) / "seed.bin"
    digest = _write_artifact(artifact_path, mode=0o644)
    artifact = _artifact_dict(artifact_path, mode=0o600, sha256=digest)
    result = pc.context_spec("slot1@1", "owner", artifact, ["cookies"])
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_ARTIFACT_MODE_MISMATCH


# --- edge 11: symlink propagated ----------------------------------------------

def test_context_spec_refuses_symlinked_artifact(artifact_tmp):
    target = Path(artifact_tmp) / "target.bin"
    digest = _write_artifact(target)
    link = Path(artifact_tmp) / "link.bin"
    link.symlink_to(target)
    artifact = _artifact_dict(link, sha256=digest)
    result = pc.context_spec("slot1@1", "owner", artifact, ["cookies"])
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_ARTIFACT_SYMLINK


# --- edge 12: account missing artifact ----------------------------------------

def test_context_set_refuses_missing_artifact_for_account(artifact_tmp):
    owner_artifact = _make_artifact_simple(artifact_tmp, "owner")
    result = pc.context_set(
        "slot1",
        1,
        _accounts("owner", "guest"),
        artifacts={"owner": owner_artifact},
        capture_surfaces=["cookies"],
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_ARTIFACT_MISSING


# --- edge 13: artifact for unknown account ------------------------------------

def test_context_set_refuses_unknown_account_artifact(artifact_tmp):
    owner_artifact = _make_artifact_simple(artifact_tmp, "owner")
    intruder_artifact = _make_artifact_simple(artifact_tmp, "intruder")
    result = pc.context_set(
        "slot1",
        1,
        _accounts("owner"),
        artifacts={"owner": owner_artifact, "intruder": intruder_artifact},
        capture_surfaces=["cookies"],
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_ARTIFACT_UNKNOWN_ACCOUNT


# --- edge 14: shared context identity -----------------------------------------

def test_context_set_refuses_shared_context_identity(artifact_tmp, monkeypatch):
    owner_artifact = _make_artifact_simple(artifact_tmp, "owner")
    guest_artifact = _make_artifact_simple(artifact_tmp, "guest")
    monkeypatch.setattr(pc, "_context_identity", lambda slot_ref, account: "collapsed")
    result = pc.context_set(
        "slot1",
        1,
        _accounts("owner", "guest"),
        artifacts={"owner": owner_artifact, "guest": guest_artifact},
        capture_surfaces=["cookies"],
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_SHARED_CONTEXT_REFUSED


# --- edge 15: malformed slot ref propagated ------------------------------------

def test_context_spec_refuses_malformed_slot_ref(artifact_tmp):
    artifact = _make_artifact_simple(artifact_tmp, "owner")
    result = pc.context_spec("slot1", "owner", artifact, ["cookies"])
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_SLOT_REF_INVALID


def test_context_spec_refuses_zero_generation(artifact_tmp):
    artifact = _make_artifact_simple(artifact_tmp, "owner")
    result = pc.context_spec("slot1@0", "owner", artifact, ["cookies"])
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_SLOT_REF_INVALID


# --- context_set success ------------------------------------------------------

def test_context_set_one_context_per_account(artifact_tmp):
    owner_artifact = _make_artifact_simple(artifact_tmp, "owner")
    guest_artifact = _make_artifact_simple(artifact_tmp, "guest")
    surfaces = ["cookies", "localStorage"]
    result = pc.context_set(
        "slot1",
        1,
        _accounts("owner", "guest"),
        artifacts={"owner": owner_artifact, "guest": guest_artifact},
        capture_surfaces=surfaces,
    )
    assert result["ok"] is True
    assert result["reason"] is None
    assert result["slotRef"] == "slot1@1"
    assert len(result["contexts"]) == 2
    assert [spec["account"] for spec in result["contexts"]] == ["owner", "guest"]
    for spec in result["contexts"]:
        assert spec["schemaVersion"] == pc.CONTEXT_SCHEMA_VERSION
        assert spec["slotRef"] == "slot1@1"
        assert spec["captureSurfaces"] == surfaces
        assert spec["contextOptions"] == {"indexedDB": False, "credentials": False}
        assert set(spec["artifact"].keys()) == {"path", "sha256"}


def test_context_set_uses_verified_artifact_not_caller_input(artifact_tmp, monkeypatch):
    sub = Path(artifact_tmp) / "subdir"
    sub.mkdir()
    artifact_path = sub / "seed.bin"
    digest = _write_artifact(artifact_path)
    monkeypatch.chdir(sub)
    relative = _artifact_dict("seed.bin", sha256=digest)
    result = pc.context_set(
        "slot1",
        1,
        _accounts("owner"),
        artifacts={"owner": relative},
        capture_surfaces=["cookies"],
    )
    assert result["ok"] is True
    assert result["contexts"][0]["artifact"]["path"] == str(artifact_path.resolve())
