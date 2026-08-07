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


def _valid_provisioning_receipt(slot_ref):
    return {
        "slotRef": slot_ref,
        "policyDigest": "policy-digest-placeholder",
        "datastoreIdentity": {
            "provenance": "observed",
            "strength": "strong",
            "match": True,
        },
        "declarations": [{"kind": "identity-probe", "status": "exercised"}],
    }


# --- context_spec_from_artifact success ---------------------------------------

def test_context_spec_from_artifact_success_applies_required_options(artifact_tmp):
    artifact = _make_artifact_simple(artifact_tmp, "owner")
    surfaces = ["cookies", "indexedDB"]
    result = pc.context_spec_from_artifact(
        "slot1@1", "owner", artifact, surfaces,
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
    )
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


def test_context_spec_from_artifact_success_with_matching_requested_options(artifact_tmp):
    artifact = _make_artifact_simple(artifact_tmp, "owner")
    surfaces = ["cookies"]
    options = ps.required_context_options(surfaces)
    result = pc.context_spec_from_artifact(
        "slot1@1", "owner", artifact, surfaces, requested_options=options,
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
    )
    assert result["ok"] is True
    assert result["contextOptions"] == options


# --- edge 1: indexedDB surface, indexedDB: False ------------------------------

def test_context_spec_refuses_indexeddb_false_when_surface_declared(artifact_tmp):
    result = pc.context_spec(
        "slot1@1",
        "owner",
        ["indexedDB"],
        requested_options={"indexedDB": False, "credentials": False},
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
        sign_in_path="attended",
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_OPTIONS_MISMATCH


# --- edge 2: webauthn surface, credentials: False -----------------------------

def test_context_spec_refuses_credentials_false_when_webauthn_declared(artifact_tmp):
    result = pc.context_spec(
        "slot1@1",
        "owner",
        ["webauthn"],
        requested_options={"indexedDB": False, "credentials": False},
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
        sign_in_path="attended",
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_OPTIONS_MISMATCH


# --- edge 3: unrequired option True -------------------------------------------

def test_context_spec_refuses_overprovisioned_credentials(artifact_tmp):
    result = pc.context_spec(
        "slot1@1",
        "owner",
        ["cookies"],
        requested_options={"indexedDB": False, "credentials": True},
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
        sign_in_path="attended",
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_OPTIONS_MISMATCH


def test_context_spec_refuses_overprovisioned_indexeddb(artifact_tmp):
    result = pc.context_spec(
        "slot1@1",
        "owner",
        ["cookies"],
        requested_options={"indexedDB": True, "credentials": False},
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
        sign_in_path="attended",
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_OPTIONS_MISMATCH


# --- edge 4: wrong keys / wrong types -----------------------------------------

def test_context_spec_refuses_requested_options_wrong_keys(artifact_tmp):
    result = pc.context_spec(
        "slot1@1",
        "owner",
        ["cookies"],
        requested_options={"indexedDB": False},
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
        sign_in_path="attended",
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_OPTIONS_MISMATCH


def test_context_spec_refuses_requested_options_wrong_types(artifact_tmp):
    result = pc.context_spec(
        "slot1@1",
        "owner",
        ["cookies"],
        requested_options={"indexedDB": "false", "credentials": False},
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
        sign_in_path="attended",
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_OPTIONS_MISMATCH


# --- edge 5: sessionStorage propagated ----------------------------------------

def test_context_spec_refuses_session_storage_surface(artifact_tmp):
    result = pc.context_spec(
        "slot1@1", "owner", ["sessionStorage"],
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
        sign_in_path="attended",
    )
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_SESSION_STORAGE


def test_session_storage_never_reaches_context_spec(artifact_tmp):
    result = pc.context_spec(
        "slot1@1", "owner", ["sessionStorage"],
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
        sign_in_path="attended",
    )
    assert result["ok"] is False
    assert "schemaVersion" not in result


# --- edge 6: unknown / duplicate surface propagated ---------------------------

def test_context_spec_refuses_unknown_surface(artifact_tmp):
    result = pc.context_spec(
        "slot1@1", "owner", ["bogus"],
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
        sign_in_path="attended",
    )
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_SURFACE_UNKNOWN


def test_context_spec_refuses_duplicate_surface(artifact_tmp):
    result = pc.context_spec(
        "slot1@1", "owner", ["cookies", "cookies"],
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
        sign_in_path="attended",
    )
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_SURFACE_DUPLICATE


# --- edge 7: empty surface list propagated ------------------------------------

def test_context_spec_refuses_empty_surfaces(artifact_tmp):
    result = pc.context_spec(
        "slot1@1", "owner", [],
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
        sign_in_path="attended",
    )
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_SURFACES_EMPTY


# --- edge 8: artifact missing propagated (latent restore path) ----------------

def test_context_spec_from_artifact_refuses_missing_artifact(artifact_tmp):
    missing = os.path.join(artifact_tmp, "missing.bin")
    artifact = _artifact_dict(missing)
    result = pc.context_spec_from_artifact(
        "slot1@1", "owner", artifact, ["cookies"],
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
    )
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_ARTIFACT_MISSING


# --- edge 9: hash mismatch propagated -----------------------------------------

def test_context_spec_from_artifact_refuses_hash_mismatch(artifact_tmp):
    artifact_path = Path(artifact_tmp) / "seed.bin"
    digest = _write_artifact(artifact_path, content=b"original")
    artifact_path.write_bytes(b"changed")
    artifact = _artifact_dict(artifact_path, sha256=digest)
    result = pc.context_spec_from_artifact(
        "slot1@1", "owner", artifact, ["cookies"],
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
    )
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_ARTIFACT_HASH_MISMATCH


# --- edge 10: owner / mode mismatch propagated --------------------------------

@pytest.mark.skipif(not hasattr(os, "getuid"), reason="no os.getuid on this platform")
def test_context_spec_from_artifact_refuses_owner_mismatch(artifact_tmp):
    artifact_path = Path(artifact_tmp) / "seed.bin"
    digest = _write_artifact(artifact_path)
    artifact = _artifact_dict(artifact_path, uid=os.getuid() + 1, sha256=digest)
    result = pc.context_spec_from_artifact(
        "slot1@1", "owner", artifact, ["cookies"],
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
    )
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_ARTIFACT_OWNER_MISMATCH


def test_context_spec_from_artifact_refuses_mode_mismatch(artifact_tmp):
    artifact_path = Path(artifact_tmp) / "seed.bin"
    digest = _write_artifact(artifact_path, mode=0o644)
    artifact = _artifact_dict(artifact_path, mode=0o600, sha256=digest)
    result = pc.context_spec_from_artifact(
        "slot1@1", "owner", artifact, ["cookies"],
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
    )
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_ARTIFACT_MODE_MISMATCH


# --- edge 11: symlink propagated ----------------------------------------------

def test_context_spec_from_artifact_refuses_symlinked_artifact(artifact_tmp):
    target = Path(artifact_tmp) / "target.bin"
    digest = _write_artifact(target)
    link = Path(artifact_tmp) / "link.bin"
    link.symlink_to(target)
    artifact = _artifact_dict(link, sha256=digest)
    result = pc.context_spec_from_artifact(
        "slot1@1", "owner", artifact, ["cookies"],
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
    )
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_ARTIFACT_SYMLINK


# --- edge 12: artifacts supplied on live path ---------------------------------

def test_context_set_refuses_artifacts_on_attended_path(artifact_tmp):
    owner_artifact = _make_artifact_simple(artifact_tmp, "owner")
    result = pc.context_set(
        "slot1",
        1,
        _accounts("owner", "guest"),
        sign_in_path="attended",
        artifacts={"owner": owner_artifact},
        capture_surfaces=["cookies"],
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_ARTIFACT_REFUSED_ON_LIVE_SEEDING


# --- edge 13: artifact for unknown account (live path refuses artifacts) ------

def test_context_set_refuses_unknown_account_artifact_on_attended(artifact_tmp):
    owner_artifact = _make_artifact_simple(artifact_tmp, "owner")
    intruder_artifact = _make_artifact_simple(artifact_tmp, "intruder")
    result = pc.context_set(
        "slot1",
        1,
        _accounts("owner"),
        sign_in_path="attended",
        artifacts={"owner": owner_artifact, "intruder": intruder_artifact},
        capture_surfaces=["cookies"],
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_ARTIFACT_REFUSED_ON_LIVE_SEEDING


# --- edge 14: shared context identity -----------------------------------------

def test_context_set_refuses_shared_context_identity(artifact_tmp, monkeypatch):
    monkeypatch.setattr(pc, "_context_identity", lambda slot_ref, account: "collapsed")
    result = pc.context_set(
        "slot1",
        1,
        _accounts("owner", "guest"),
        sign_in_path="attended",
        capture_surfaces=["cookies"],
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_SHARED_CONTEXT_REFUSED


# --- edge 15: malformed slot ref propagated ------------------------------------

def test_context_spec_refuses_malformed_slot_ref(artifact_tmp):
    artifact = _make_artifact_simple(artifact_tmp, "owner")
    result = pc.context_spec_from_artifact(
        "slot1", "owner", artifact, ["cookies"],
        provisioning_receipt=_valid_provisioning_receipt("slot1"),
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_PROVISIONING_RECEIPT_SLOT_MISMATCH


def test_context_spec_refuses_zero_generation(artifact_tmp):
    artifact = _make_artifact_simple(artifact_tmp, "owner")
    result = pc.context_spec_from_artifact(
        "slot1@0", "owner", artifact, ["cookies"],
        provisioning_receipt=_valid_provisioning_receipt("slot1@0"),
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_PROVISIONING_RECEIPT_SLOT_MISMATCH


# --- context_set success (live attended path) ---------------------------------

def test_context_set_one_context_per_account(artifact_tmp):
    surfaces = ["cookies", "localStorage"]
    result = pc.context_set(
        "slot1",
        1,
        _accounts("owner", "guest"),
        sign_in_path="attended",
        capture_surfaces=surfaces,
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
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
        assert spec["artifact"] is None


def test_context_spec_from_artifact_uses_verified_path_not_caller_input(artifact_tmp, monkeypatch):
    sub = Path(artifact_tmp) / "subdir"
    sub.mkdir()
    artifact_path = sub / "seed.bin"
    digest = _write_artifact(artifact_path)
    monkeypatch.chdir(sub)
    relative = _artifact_dict("seed.bin", sha256=digest)
    result = pc.context_spec_from_artifact(
        "slot1@1",
        "owner",
        relative,
        ["cookies"],
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
    )
    assert result["ok"] is True
    assert result["artifact"]["path"] == str(artifact_path.resolve())


# --- provisioning receipt gate (finding 1) ------------------------------------

def test_context_spec_refuses_missing_provisioning_receipt(artifact_tmp):
    result = pc.context_spec(
        "slot1@1", "owner", ["cookies"],
        provisioning_receipt=None,
        sign_in_path="attended",
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_PROVISIONING_RECEIPT_MISSING


def test_context_spec_refuses_invalid_provisioning_receipt(artifact_tmp):
    result = pc.context_spec(
        "slot1@1",
        "owner",
        ["cookies"],
        provisioning_receipt={"slotRef": "slot1@1"},
        sign_in_path="attended",
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_PROVISIONING_RECEIPT_INVALID


def test_context_spec_refuses_provisioning_receipt_slot_mismatch(artifact_tmp):
    receipt = _valid_provisioning_receipt("slot-other@1")
    result = pc.context_spec(
        "slot1@1", "owner", ["cookies"],
        provisioning_receipt=receipt,
        sign_in_path="attended",
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_PROVISIONING_RECEIPT_SLOT_MISMATCH


def test_context_spec_provisioning_receipt_checked_before_sign_in_path(artifact_tmp):
    artifact = _make_artifact_simple(artifact_tmp, "owner")
    result = pc.context_spec(
        "slot1@1", "owner", ["cookies"],
        provisioning_receipt=None,
        sign_in_path="attended",
        artifact=artifact,
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_PROVISIONING_RECEIPT_MISSING
    assert result["reason"] != pc.REFUSAL_ARTIFACT_REFUSED_ON_LIVE_SEEDING


def test_context_spec_from_artifact_provisioning_receipt_checked_before_seed_request(artifact_tmp):
    artifact_path = Path(artifact_tmp) / "seed.bin"
    digest = _write_artifact(artifact_path, content=b"original")
    artifact_path.write_bytes(b"changed")
    artifact = _artifact_dict(artifact_path, sha256=digest)
    result = pc.context_spec_from_artifact(
        "slot1@1", "owner", artifact, ["cookies"], provisioning_receipt=None,
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_PROVISIONING_RECEIPT_MISSING
    assert result["reason"] != ps.REFUSAL_ARTIFACT_HASH_MISMATCH


def test_context_spec_valid_provisioning_receipt_proceeds(artifact_tmp):
    result = pc.context_spec(
        "slot1@1",
        "owner",
        ["cookies"],
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
        sign_in_path="attended",
    )
    assert result["ok"] is True


def test_context_spec_refuses_empty_declarations(artifact_tmp):
    receipt = _valid_provisioning_receipt("slot1@1")
    receipt["declarations"] = []
    result = pc.context_spec(
        "slot1@1", "owner", ["cookies"],
        provisioning_receipt=receipt,
        sign_in_path="attended",
    )
    assert result["reason"] == pc.REFUSAL_PROVISIONING_RECEIPT_INVALID


def test_context_spec_refuses_declaration_missing_kind(artifact_tmp):
    receipt = _valid_provisioning_receipt("slot1@1")
    receipt["declarations"] = [{"status": "exercised"}]
    result = pc.context_spec(
        "slot1@1", "owner", ["cookies"],
        provisioning_receipt=receipt,
        sign_in_path="attended",
    )
    assert result["reason"] == pc.REFUSAL_PROVISIONING_RECEIPT_INVALID


def test_context_spec_refuses_datastore_identity_match_false(artifact_tmp):
    receipt = _valid_provisioning_receipt("slot1@1")
    receipt["datastoreIdentity"]["match"] = False
    result = pc.context_spec(
        "slot1@1", "owner", ["cookies"],
        provisioning_receipt=receipt,
        sign_in_path="attended",
    )
    assert result["reason"] == pc.REFUSAL_PROVISIONING_RECEIPT_INVALID


def test_context_spec_refuses_empty_policy_digest(artifact_tmp):
    receipt = _valid_provisioning_receipt("slot1@1")
    receipt["policyDigest"] = ""
    result = pc.context_spec(
        "slot1@1", "owner", ["cookies"],
        provisioning_receipt=receipt,
        sign_in_path="attended",
    )
    assert result["reason"] == pc.REFUSAL_PROVISIONING_RECEIPT_INVALID


def test_context_spec_refuses_unparseable_slot_ref_with_receipt(artifact_tmp):
    # bite-axis: provisioning receipt — unparseable slot ref refuses, never falls open.
    receipt = _valid_provisioning_receipt("slot1@1")
    result = pc.context_spec(
        "slot1", "owner", ["cookies"],
        provisioning_receipt=receipt,
        sign_in_path="attended",
    )
    assert result["reason"] == pc.REFUSAL_PROVISIONING_RECEIPT_SLOT_MISMATCH


# --- WO3: explicit sign_in_path and live-seeding edges ------------------------

def test_context_spec_refuses_retired_captured_sign_in_path(artifact_tmp):
  # bite-axis: sign_in_path validation — retired "captured" literal refuses, never live-seeds.
    result = pc.context_spec(
        "slot1@1",
        "owner",
        ["cookies"],
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
        sign_in_path="captured",
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_SIGN_IN_PATH_INVALID


def test_context_spec_refuses_none_sign_in_path(artifact_tmp):
    result = pc.context_spec(
        "slot1@1",
        "owner",
        ["cookies"],
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
        sign_in_path=None,
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_SIGN_IN_PATH_INVALID


def test_context_spec_refuses_non_string_sign_in_path(artifact_tmp):
    result = pc.context_spec(
        "slot1@1",
        "owner",
        ["cookies"],
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
        sign_in_path=123,
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_SIGN_IN_PATH_INVALID


def test_context_spec_refuses_artifact_on_attended_path(artifact_tmp):
  # bite-axis: live-seeding paths refuse a supplied artifact — attended path with artifact.
    artifact = _make_artifact_simple(artifact_tmp, "owner")
    result = pc.context_spec(
        "slot1@1",
        "owner",
        ["cookies"],
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
        sign_in_path="attended",
        artifact=artifact,
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_ARTIFACT_REFUSED_ON_LIVE_SEEDING


def test_context_spec_refuses_artifact_on_minted_path(artifact_tmp):
    artifact = _make_artifact_simple(artifact_tmp, "owner")
    result = pc.context_spec(
        "slot1@1",
        "owner",
        ["cookies"],
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
        sign_in_path="minted",
        artifact=artifact,
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_ARTIFACT_REFUSED_ON_LIVE_SEEDING


def test_context_spec_attended_path_ok_without_artifact(artifact_tmp):
    result = pc.context_spec(
        "slot1@1",
        "owner",
        ["cookies"],
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
        sign_in_path="attended",
    )
    assert result["ok"] is True
    assert result["artifact"] is None


def test_context_spec_from_artifact_refuses_none_artifact(artifact_tmp):
  # bite-axis: latent restore path requires artifact — None refuses context-artifact-missing.
    result = pc.context_spec_from_artifact(
        "slot1@1",
        "owner",
        None,
        ["cookies"],
        provisioning_receipt=_valid_provisioning_receipt("slot1@1"),
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REFUSAL_ARTIFACT_MISSING
