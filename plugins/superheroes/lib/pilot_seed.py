"""Pilot seed and mint call shapes with verify-at-seed artifact integrity (A1).

Non-goals (§S6): no capture, no minting, no browser context creation, no policy
resolution — call shapes and integrity checking only.
"""
import hashlib
import hmac
import os
import stat

import pilot_slot

CAPTURE_SURFACES = frozenset({"cookies", "localStorage", "indexedDB", "webauthn"})
REFUSED_CAPTURE_SURFACES = frozenset({"sessionStorage"})

REFUSAL_SESSION_STORAGE = "seed-capture-surface-session-storage-refused"
REFUSAL_SURFACE_UNKNOWN = "seed-capture-surface-unknown"
REFUSAL_SURFACES_INVALID = "seed-capture-surfaces-invalid"
REFUSAL_SURFACES_EMPTY = "seed-capture-surfaces-empty"
REFUSAL_SURFACE_DUPLICATE = "seed-capture-surface-duplicate"

REFUSAL_SLOT_REF_INVALID = "seed-slot-ref-invalid"
REFUSAL_ACCOUNT_INVALID = "seed-account-invalid"
REFUSAL_CONTEXT_OPTIONS_INVALID = "seed-context-options-invalid"
REFUSAL_VERIFY_ARGUMENT_INVALID = "seed-verify-argument-invalid"

REFUSAL_ARTIFACT_PATH_TRAVERSAL = "artifact-path-traversal"
REFUSAL_ARTIFACT_SYMLINK = "artifact-symlink-in-path"
REFUSAL_ARTIFACT_MISSING = "artifact-missing"
REFUSAL_ARTIFACT_NOT_REGULAR = "artifact-not-regular-file"
REFUSAL_ARTIFACT_OWNER_MISMATCH = "artifact-owner-mismatch"
REFUSAL_ARTIFACT_MODE_MISMATCH = "artifact-mode-mismatch"
REFUSAL_ARTIFACT_HASH_MISMATCH = "artifact-hash-mismatch"
REFUSAL_ARTIFACT_UNREADABLE = "artifact-unreadable"

REFUSAL_MINT_ALLOWLIST_EMPTY = "mint-allowlist-empty"
REFUSAL_MINT_ACCOUNT_NOT_IN_ALLOWLIST = "mint-account-not-in-allowlist"
REFUSAL_MINT_ACCOUNT_INVALID = "mint-account-invalid"
REFUSAL_MINT_ENVELOPE_INCOMPLETE = "mint-envelope-incomplete"
REFUSAL_MINT_SENTINEL_IN_ALLOWLIST = "mint-sentinel-in-allowlist"

_VALID_CONTEXT_OPTION_KEYS = frozenset({"indexedDB", "credentials"})
_SHA256_HEX_LEN = 64


class PilotSeedError(Exception):
    """Caller or contract refusal from pilot_seed."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def required_context_options(capture_surfaces):
    """Return required browser context options for declared capture surfaces (§S3)."""
    if not _is_json_array(capture_surfaces):
        raise PilotSeedError(REFUSAL_SURFACES_INVALID)
    surfaces = list(capture_surfaces)
    if not surfaces:
        raise PilotSeedError(REFUSAL_SURFACES_EMPTY)
    seen = set()
    for surface in surfaces:
        if not isinstance(surface, str):
            raise PilotSeedError(REFUSAL_SURFACES_INVALID)
        if surface in seen:
            raise PilotSeedError(REFUSAL_SURFACE_DUPLICATE)
        seen.add(surface)
        if surface in REFUSED_CAPTURE_SURFACES:
            raise PilotSeedError(REFUSAL_SESSION_STORAGE)
        if surface not in CAPTURE_SURFACES:
            raise PilotSeedError(REFUSAL_SURFACE_UNKNOWN)
    return {
        "indexedDB": "indexedDB" in seen,
        "credentials": "webauthn" in seen,
    }


def verify_artifact(path, *, expected_uid, expected_mode, recorded_sha256):
    """Verify artifact integrity at seed time; returns ok/reason dict (never raises on artifact)."""
    _validate_verify_arguments(expected_uid, expected_mode, recorded_sha256)
    if _path_has_traversal_component(path):
        return _refusal(REFUSAL_ARTIFACT_PATH_TRAVERSAL)
    try:
        for ancestor in _ancestors_including_self(path):
            if os.path.islink(ancestor):
                return _refusal(REFUSAL_ARTIFACT_SYMLINK)
        try:
            st = os.lstat(path)
        except FileNotFoundError:
            return _refusal(REFUSAL_ARTIFACT_MISSING)
        except OSError:
            return _refusal(REFUSAL_ARTIFACT_UNREADABLE)
        if not stat.S_ISREG(st.st_mode):
            return _refusal(REFUSAL_ARTIFACT_NOT_REGULAR)
        if st.st_uid != expected_uid:
            return _refusal(REFUSAL_ARTIFACT_OWNER_MISMATCH)
        if (st.st_mode & 0o777) != expected_mode:
            return _refusal(REFUSAL_ARTIFACT_MODE_MISMATCH)
        digest = _sha256_file(path)
        if digest is None:
            return _refusal(REFUSAL_ARTIFACT_UNREADABLE)
        if not hmac.compare_digest(digest, recorded_sha256.lower()):
            return _refusal(REFUSAL_ARTIFACT_HASH_MISMATCH, sha256=digest)
        absolute_path = _absolute_path_without_normpath(path)
        return {"ok": True, "reason": None, "sha256": digest, "path": absolute_path}
    except OSError:
        return _refusal(REFUSAL_ARTIFACT_UNREADABLE)


def seed_request(slot_ref, account, artifact, context_options):
    """Build a seed request descriptor after local validation and artifact verification."""
    try:
        pilot_slot.parse_slot_ref(slot_ref)
    except pilot_slot.PilotSlotError:
        raise PilotSeedError(REFUSAL_SLOT_REF_INVALID)
    if not isinstance(account, str) or not account:
        raise PilotSeedError(REFUSAL_ACCOUNT_INVALID)
    if not _is_valid_context_options(context_options):
        raise PilotSeedError(REFUSAL_CONTEXT_OPTIONS_INVALID)
    _validate_artifact_mapping(artifact)
    result = verify_artifact(
        artifact["path"],
        expected_uid=artifact["expectedUid"],
        expected_mode=artifact["expectedMode"],
        recorded_sha256=artifact["sha256"],
    )
    if not result["ok"]:
        raise PilotSeedError(result["reason"])
    return {
        "slotRef": slot_ref,
        "account": account,
        "artifact": {
            "path": result["path"],
            "sha256": result["sha256"],
        },
        "contextOptions": {
            "indexedDB": context_options["indexedDB"],
            "credentials": context_options["credentials"],
        },
    }


def mint_request(account, *, allowlist, envelope):
    """Build a mint-client request descriptor; allowlist is caller-supplied policy."""
    if not _is_json_array(allowlist) or not allowlist:
        raise PilotSeedError(REFUSAL_MINT_ALLOWLIST_EMPTY)
    for item in allowlist:
        if not isinstance(item, str) or not item:
            raise PilotSeedError(REFUSAL_MINT_ALLOWLIST_EMPTY)
    if not isinstance(account, str) or not account:
        raise PilotSeedError(REFUSAL_MINT_ACCOUNT_INVALID)
    if account not in allowlist:
        raise PilotSeedError(REFUSAL_MINT_ACCOUNT_NOT_IN_ALLOWLIST)
    flag_var = _enabling_flag_env_var(envelope)
    return {
        "account": account,
        "enablingFlagEnvVar": flag_var,
    }


def sentinel_probe_request(sentinel, *, allowlist, envelope):
    """Build a sentinel probe request; refuses when sentinel is mintable."""
    if not _is_json_array(allowlist) or not allowlist:
        raise PilotSeedError(REFUSAL_MINT_ALLOWLIST_EMPTY)
    for item in allowlist:
        if not isinstance(item, str) or not item:
            raise PilotSeedError(REFUSAL_MINT_ALLOWLIST_EMPTY)
    if not isinstance(sentinel, str) or not sentinel:
        raise PilotSeedError(REFUSAL_MINT_ACCOUNT_INVALID)
    if sentinel in allowlist:
        raise PilotSeedError(REFUSAL_MINT_SENTINEL_IN_ALLOWLIST)
    flag_var = _enabling_flag_env_var(envelope)
    return {
        "sentinel": sentinel,
        "enablingFlagEnvVar": flag_var,
    }


def _is_json_array(value):
    return isinstance(value, list)


def _is_valid_context_options(context_options):
    if not isinstance(context_options, dict):
        return False
    if set(context_options.keys()) != _VALID_CONTEXT_OPTION_KEYS:
        return False
    return (
        isinstance(context_options["indexedDB"], bool)
        and isinstance(context_options["credentials"], bool)
    )


def _validate_artifact_mapping(artifact):
    if not isinstance(artifact, dict):
        raise PilotSeedError(REFUSAL_VERIFY_ARGUMENT_INVALID)
    required = {"path", "expectedUid", "expectedMode", "sha256"}
    if set(artifact.keys()) != required:
        raise PilotSeedError(REFUSAL_VERIFY_ARGUMENT_INVALID)
    if not isinstance(artifact["path"], str) or not artifact["path"]:
        raise PilotSeedError(REFUSAL_VERIFY_ARGUMENT_INVALID)
    _validate_verify_arguments(
        artifact["expectedUid"],
        artifact["expectedMode"],
        artifact["sha256"],
    )


def _validate_verify_arguments(expected_uid, expected_mode, recorded_sha256):
    if type(expected_uid) is not int:
        raise PilotSeedError(REFUSAL_VERIFY_ARGUMENT_INVALID)
    if not isinstance(expected_mode, int) or expected_mode < 0 or expected_mode > 0o777:
        raise PilotSeedError(REFUSAL_VERIFY_ARGUMENT_INVALID)
    if not isinstance(recorded_sha256, str):
        raise PilotSeedError(REFUSAL_VERIFY_ARGUMENT_INVALID)
    if len(recorded_sha256) != _SHA256_HEX_LEN:
        raise PilotSeedError(REFUSAL_VERIFY_ARGUMENT_INVALID)
    if recorded_sha256 != recorded_sha256.lower():
        raise PilotSeedError(REFUSAL_VERIFY_ARGUMENT_INVALID)
    try:
        int(recorded_sha256, 16)
    except ValueError:
        raise PilotSeedError(REFUSAL_VERIFY_ARGUMENT_INVALID)


def _enabling_flag_env_var(envelope):
    if not isinstance(envelope, dict):
        raise PilotSeedError(REFUSAL_MINT_ENVELOPE_INCOMPLETE)
    flag_var = envelope.get("enablingFlagEnvVar")
    if not isinstance(flag_var, str) or not flag_var:
        raise PilotSeedError(REFUSAL_MINT_ENVELOPE_INCOMPLETE)
    return flag_var


def _absolute_path_without_normpath(path):
    if os.path.isabs(path):
        return path
    return os.path.join(os.getcwd(), path)


def _path_has_traversal_component(path):
    absolute = _absolute_path_without_normpath(path)
    return ".." in absolute.split(os.sep)


def _ancestors_including_self(path):
    absolute = _absolute_path_without_normpath(path)
    ancestors = []
    current = absolute
    while True:
        ancestors.append(current)
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    ancestors.reverse()
    return ancestors


def _sha256_file(path):
    hasher = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            while True:
                chunk = handle.read(65536)
                if not chunk:
                    break
                hasher.update(chunk)
    except OSError:
        return None
    return hasher.hexdigest()


def _refusal(reason, sha256=None):
    return {"ok": False, "reason": reason, "sha256": sha256}
