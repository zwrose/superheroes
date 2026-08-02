"""Tests for pilot_seed.py — seed/mint call shapes and verify-at-seed integrity."""
import hashlib
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_seed as ps  # noqa: E402


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


# --- required_context_options -------------------------------------------------

def test_required_context_options_cookies_only():
    assert ps.required_context_options(["cookies"]) == {
        "indexedDB": False,
        "credentials": False,
    }


def test_required_context_options_indexed_db_and_webauthn():
    assert ps.required_context_options(["indexedDB", "webauthn"]) == {
        "indexedDB": True,
        "credentials": True,
    }


def test_required_context_options_refuses_none():
    with pytest.raises(ps.PilotSeedError) as exc:
        ps.required_context_options(None)
    assert exc.value.reason == ps.REFUSAL_SURFACES_INVALID


def test_required_context_options_refuses_empty():
    with pytest.raises(ps.PilotSeedError) as exc:
        ps.required_context_options([])
    assert exc.value.reason == ps.REFUSAL_SURFACES_EMPTY


def test_required_context_options_refuses_duplicate():
    with pytest.raises(ps.PilotSeedError) as exc:
        ps.required_context_options(["cookies", "cookies"])
    assert exc.value.reason == ps.REFUSAL_SURFACE_DUPLICATE


def test_required_context_options_refuses_unknown_surface():
    with pytest.raises(ps.PilotSeedError) as exc:
        ps.required_context_options(["bogus"])
    assert exc.value.reason == ps.REFUSAL_SURFACE_UNKNOWN


def test_required_context_options_refuses_session_storage():
    with pytest.raises(ps.PilotSeedError) as exc:
        ps.required_context_options(["sessionStorage"])
    assert exc.value.reason == ps.REFUSAL_SESSION_STORAGE


def test_required_context_options_refuses_bare_string():
    with pytest.raises(ps.PilotSeedError) as exc:
        ps.required_context_options("cookies")
    assert exc.value.reason == ps.REFUSAL_SURFACES_INVALID


# --- verify_artifact ----------------------------------------------------------

def test_verify_artifact_ok(tmp_path):
    artifact = tmp_path / "seed.bin"
    digest = _write_artifact(artifact)
    result = ps.verify_artifact(
        str(artifact),
        expected_uid=os.getuid(),
        expected_mode=0o600,
        recorded_sha256=digest,
    )
    assert result == {"ok": True, "reason": None, "sha256": digest}


def test_verify_artifact_refuses_symlinked_leaf(tmp_path):
    target = tmp_path / "target.bin"
    _write_artifact(target)
    link = tmp_path / "link.bin"
    link.symlink_to(target)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    result = ps.verify_artifact(
        str(link),
        expected_uid=os.getuid(),
        expected_mode=0o600,
        recorded_sha256=digest,
    )
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_ARTIFACT_SYMLINK


def test_verify_artifact_refuses_symlinked_parent_directory(tmp_path):
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    artifact = real_dir / "seed.bin"
    digest = _write_artifact(artifact)
    linked_parent = tmp_path / "linked"
    linked_parent.symlink_to(real_dir)
    linked_artifact = linked_parent / "seed.bin"
    result = ps.verify_artifact(
        str(linked_artifact),
        expected_uid=os.getuid(),
        expected_mode=0o600,
        recorded_sha256=digest,
    )
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_ARTIFACT_SYMLINK


def test_verify_artifact_refuses_dangling_symlink(tmp_path):
    link = tmp_path / "dangling"
    link.symlink_to(tmp_path / "missing")
    result = ps.verify_artifact(
        str(link),
        expected_uid=os.getuid(),
        expected_mode=0o600,
        recorded_sha256="a" * 64,
    )
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_ARTIFACT_SYMLINK


def test_verify_artifact_refuses_missing_path(tmp_path):
    missing = tmp_path / "missing.bin"
    result = ps.verify_artifact(
        str(missing),
        expected_uid=os.getuid(),
        expected_mode=0o600,
        recorded_sha256="a" * 64,
    )
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_ARTIFACT_MISSING


def test_verify_artifact_refuses_directory(tmp_path):
    result = ps.verify_artifact(
        str(tmp_path),
        expected_uid=os.getuid(),
        expected_mode=0o700,
        recorded_sha256="a" * 64,
    )
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_ARTIFACT_NOT_REGULAR


@pytest.mark.skipif(not hasattr(os, "getuid"), reason="no os.getuid on this platform")
def test_verify_artifact_refuses_owner_mismatch(tmp_path):
    artifact = tmp_path / "seed.bin"
    digest = _write_artifact(artifact)
    result = ps.verify_artifact(
        str(artifact),
        expected_uid=os.getuid() + 1,
        expected_mode=0o600,
        recorded_sha256=digest,
    )
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_ARTIFACT_OWNER_MISMATCH


def test_verify_artifact_refuses_more_permissive_mode(tmp_path):
    artifact = tmp_path / "seed.bin"
    digest = _write_artifact(artifact, mode=0o644)
    result = ps.verify_artifact(
        str(artifact),
        expected_uid=os.getuid(),
        expected_mode=0o600,
        recorded_sha256=digest,
    )
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_ARTIFACT_MODE_MISMATCH


def test_verify_artifact_refuses_less_permissive_mode(tmp_path):
    artifact = tmp_path / "seed.bin"
    digest = _write_artifact(artifact, mode=0o400)
    result = ps.verify_artifact(
        str(artifact),
        expected_uid=os.getuid(),
        expected_mode=0o600,
        recorded_sha256=digest,
    )
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_ARTIFACT_MODE_MISMATCH


def test_verify_artifact_refuses_hash_mismatch(tmp_path):
    artifact = tmp_path / "seed.bin"
    _write_artifact(artifact, content=b"original")
    result = ps.verify_artifact(
        str(artifact),
        expected_uid=os.getuid(),
        expected_mode=0o600,
        recorded_sha256="b" * 64,
    )
    assert result["ok"] is False
    assert result["reason"] == ps.REFUSAL_ARTIFACT_HASH_MISMATCH
    assert result["sha256"] is not None


def test_verify_artifact_refuses_uppercase_recorded_sha256(tmp_path):
    artifact = tmp_path / "seed.bin"
    digest = _write_artifact(artifact)
    with pytest.raises(ps.PilotSeedError) as exc:
        ps.verify_artifact(
            str(artifact),
            expected_uid=os.getuid(),
            expected_mode=0o600,
            recorded_sha256=digest.upper(),
        )
    assert exc.value.reason == ps.REFUSAL_VERIFY_ARGUMENT_INVALID


def test_verify_artifact_refuses_wrong_length_sha256(tmp_path):
    artifact = tmp_path / "seed.bin"
    _write_artifact(artifact)
    with pytest.raises(ps.PilotSeedError) as exc:
        ps.verify_artifact(
            str(artifact),
            expected_uid=os.getuid(),
            expected_mode=0o600,
            recorded_sha256="abc",
        )
    assert exc.value.reason == ps.REFUSAL_VERIFY_ARGUMENT_INVALID


def test_verify_artifact_refuses_expected_mode_out_of_range(tmp_path):
    artifact = tmp_path / "seed.bin"
    digest = _write_artifact(artifact)
    with pytest.raises(ps.PilotSeedError) as exc:
        ps.verify_artifact(
            str(artifact),
            expected_uid=os.getuid(),
            expected_mode=0o1000,
            recorded_sha256=digest,
        )
    assert exc.value.reason == ps.REFUSAL_VERIFY_ARGUMENT_INVALID


# --- seed_request ---------------------------------------------------------------

def test_seed_request_success(tmp_path):
    artifact_path = tmp_path / "seed.bin"
    digest = _write_artifact(artifact_path)
    context_options = ps.required_context_options(["cookies"])
    result = ps.seed_request(
        "slot@1",
        "owner",
        _artifact_dict(artifact_path, sha256=digest),
        context_options,
    )
    assert result == {
        "slotRef": "slot@1",
        "account": "owner",
        "artifact": {"path": str(artifact_path), "sha256": digest},
        "contextOptions": context_options,
    }


def test_seed_request_refuses_slot_without_generation():
    with pytest.raises(ps.PilotSeedError) as exc:
        ps.seed_request("slot", "owner", {}, {"indexedDB": False, "credentials": False})
    assert exc.value.reason == ps.REFUSAL_SLOT_REF_INVALID


def test_seed_request_refuses_slot_at_zero_generation():
    with pytest.raises(ps.PilotSeedError) as exc:
        ps.seed_request("slot@0", "owner", {}, {"indexedDB": False, "credentials": False})
    assert exc.value.reason == ps.REFUSAL_SLOT_REF_INVALID


def test_seed_request_refuses_slot_with_leading_zero_generation():
    with pytest.raises(ps.PilotSeedError) as exc:
        ps.seed_request("slot@01", "owner", {}, {"indexedDB": False, "credentials": False})
    assert exc.value.reason == ps.REFUSAL_SLOT_REF_INVALID


def test_seed_request_refuses_empty_account(tmp_path):
    artifact_path = tmp_path / "seed.bin"
    digest = _write_artifact(artifact_path)
    with pytest.raises(ps.PilotSeedError) as exc:
        ps.seed_request(
            "slot@1",
            "",
            _artifact_dict(artifact_path, sha256=digest),
            {"indexedDB": False, "credentials": False},
        )
    assert exc.value.reason == ps.REFUSAL_ACCOUNT_INVALID


def test_seed_request_refuses_context_options_extra_key(tmp_path):
    artifact_path = tmp_path / "seed.bin"
    digest = _write_artifact(artifact_path)
    with pytest.raises(ps.PilotSeedError) as exc:
        ps.seed_request(
            "slot@1",
            "owner",
            _artifact_dict(artifact_path, sha256=digest),
            {"indexedDB": False, "credentials": False, "extra": True},
        )
    assert exc.value.reason == ps.REFUSAL_CONTEXT_OPTIONS_INVALID


def test_seed_request_refuses_context_options_missing_key(tmp_path):
    artifact_path = tmp_path / "seed.bin"
    digest = _write_artifact(artifact_path)
    with pytest.raises(ps.PilotSeedError) as exc:
        ps.seed_request(
            "slot@1",
            "owner",
            _artifact_dict(artifact_path, sha256=digest),
            {"indexedDB": False},
        )
    assert exc.value.reason == ps.REFUSAL_CONTEXT_OPTIONS_INVALID


def test_seed_request_refuses_failing_artifact_integrity(tmp_path):
    artifact_path = tmp_path / "seed.bin"
    digest = _write_artifact(artifact_path, content=b"original")
    artifact_path.write_bytes(b"changed")
    with pytest.raises(ps.PilotSeedError) as exc:
        ps.seed_request(
            "slot@1",
            "owner",
            _artifact_dict(artifact_path, sha256=digest),
            {"indexedDB": False, "credentials": False},
        )
    assert exc.value.reason == ps.REFUSAL_ARTIFACT_HASH_MISMATCH


# --- mint_request ---------------------------------------------------------------

def test_mint_request_success():
    envelope = {"enablingFlagEnvVar": "ALLOW_TEST_MINT"}
    result = ps.mint_request("owner", allowlist=["owner", "guest"], envelope=envelope)
    assert result == {"account": "owner", "enablingFlagEnvVar": "ALLOW_TEST_MINT"}


def test_mint_request_refuses_empty_allowlist():
    envelope = {"enablingFlagEnvVar": "ALLOW_TEST_MINT"}
    with pytest.raises(ps.PilotSeedError) as exc:
        ps.mint_request("owner", allowlist=[], envelope=envelope)
    assert exc.value.reason == ps.REFUSAL_MINT_ALLOWLIST_EMPTY


def test_mint_request_refuses_none_allowlist():
    envelope = {"enablingFlagEnvVar": "ALLOW_TEST_MINT"}
    with pytest.raises(ps.PilotSeedError) as exc:
        ps.mint_request("owner", allowlist=None, envelope=envelope)
    assert exc.value.reason == ps.REFUSAL_MINT_ALLOWLIST_EMPTY


def test_mint_request_refuses_account_not_in_allowlist():
    envelope = {"enablingFlagEnvVar": "ALLOW_TEST_MINT"}
    with pytest.raises(ps.PilotSeedError) as exc:
        ps.mint_request("intruder", allowlist=["owner"], envelope=envelope)
    assert exc.value.reason == ps.REFUSAL_MINT_ACCOUNT_NOT_IN_ALLOWLIST


def test_mint_request_refuses_empty_account():
    envelope = {"enablingFlagEnvVar": "ALLOW_TEST_MINT"}
    with pytest.raises(ps.PilotSeedError) as exc:
        ps.mint_request("", allowlist=["owner"], envelope=envelope)
    assert exc.value.reason == ps.REFUSAL_MINT_ACCOUNT_INVALID


def test_mint_request_refuses_incomplete_envelope():
    with pytest.raises(ps.PilotSeedError) as exc:
        ps.mint_request("owner", allowlist=["owner"], envelope={})
    assert exc.value.reason == ps.REFUSAL_MINT_ENVELOPE_INCOMPLETE


# --- sentinel_probe_request -----------------------------------------------------

def test_sentinel_probe_request_success():
    envelope = {"enablingFlagEnvVar": "ALLOW_TEST_MINT"}
    result = ps.sentinel_probe_request(
        "pilot-sentinel-no-such-account",
        allowlist=["owner"],
        envelope=envelope,
    )
    assert result == {
        "sentinel": "pilot-sentinel-no-such-account",
        "enablingFlagEnvVar": "ALLOW_TEST_MINT",
    }


def test_sentinel_probe_request_refuses_sentinel_in_allowlist():
    envelope = {"enablingFlagEnvVar": "ALLOW_TEST_MINT"}
    with pytest.raises(ps.PilotSeedError) as exc:
        ps.sentinel_probe_request(
            "pilot-sentinel-no-such-account",
            allowlist=["owner", "pilot-sentinel-no-such-account"],
            envelope=envelope,
        )
    assert exc.value.reason == ps.REFUSAL_MINT_SENTINEL_IN_ALLOWLIST
