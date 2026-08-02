"""Pilot policy document resolution, material extraction, and reach exercise (A3).

Non-goals: no boundary binding, no provisioning — policy home only.
"""
import json
import os
import re
import stat
import time

import pilot_slot

POLICY_SCHEMA_VERSION = 1
MATERIAL_CLASSES = ("expected-identity", "mintable-account", "connection-detail")

REFUSAL_POLICY_ROOT_INVALID = "policy-root-invalid"
REFUSAL_POLICY_ROOT_IN_REACH = "policy-root-in-reach"
REFUSAL_DECLARATION_INVALID = "policy-declaration-invalid"
REFUSAL_DOCUMENT_MISSING = "policy-document-missing"
REFUSAL_DOCUMENT_SYMLINK = "policy-document-symlink"
REFUSAL_DOCUMENT_NOT_REGULAR_FILE = "policy-document-not-regular-file"
REFUSAL_DOCUMENT_OWNER_MISMATCH = "policy-document-owner-mismatch"
REFUSAL_DOCUMENT_MODE_INSECURE = "policy-document-mode-insecure"
REFUSAL_DOCUMENT_UNREADABLE = "policy-document-unreadable"
REFUSAL_DOCUMENT_INVALID = "policy-document-invalid"
REFUSAL_SCHEMA_VERSION_UNSUPPORTED = "policy-schema-version-unsupported"
REFUSAL_SLOT_UNKNOWN = "policy-slot-unknown"
REFUSAL_ACCOUNT_UNKNOWN = "policy-account-unknown"
REFUSAL_MATERIAL_IN_RESULT = "policy-material-in-result"
REFUSAL_MATERIAL_INVALID = "policy-material-invalid"
REFUSAL_EXERCISE_VACUOUS = "policy-exercise-vacuous"
REFUSAL_EXERCISE_UNREADABLE = "policy-exercise-unreadable"
REFUSAL_REACH_ROOT_INVALID = "policy-reach-root-invalid"

REASON_EXERCISE_MATERIAL_FOUND = "policy-exercise-material-found"

_DECLARATION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*\Z")
_ENV_VAR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_TOP_LEVEL_KEYS = frozenset(
    {"schemaVersion", "declaration", "protectedTargets", "datastore", "slots"}
)
_DATASTORE_KEYS = frozenset({"expectedIdentity", "connectionDetail", "observer"})
_OBSERVER_KEYS = frozenset({"command", "connectionEnvVar"})
_SLOT_KEYS = frozenset(
    {"origin", "permittedRedirects", "expectedIdentities", "mintableAccounts"}
)
_SLOT_REQUIRED_KEYS = frozenset(
    {"origin", "permittedRedirects", "expectedIdentities"}
)

_COVERAGE_LIMIT_COMPRESSED = (
    "Compressed and archived content is scanned as raw bytes; material inside "
    "it is not detectable."
)


class PilotPolicyError(Exception):
    """Raised when policy resolution, validation, or exercise refuses."""

    def __init__(self, reason, detail=None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def resolve_policy_document(policy_root, declaration, *, reach_roots):
    """Return the validated policy document from outside branch-mutable reach."""
    if not isinstance(policy_root, str) or not policy_root or not os.path.isabs(policy_root):
        raise PilotPolicyError(REFUSAL_POLICY_ROOT_INVALID)
    if not os.path.isdir(policy_root):
        raise PilotPolicyError(REFUSAL_POLICY_ROOT_INVALID)

    _validate_reach_roots_list(reach_roots)
    if _policy_root_conflicts_with_reach(policy_root, reach_roots):
        raise PilotPolicyError(REFUSAL_POLICY_ROOT_IN_REACH)

    if not isinstance(declaration, str) or not _DECLARATION_RE.match(declaration):
        raise PilotPolicyError(REFUSAL_DECLARATION_INVALID)

    document_path = os.path.join(policy_root, declaration + ".json")
    for ancestor in _ancestors_including_self(document_path):
        if os.path.islink(ancestor):
            raise PilotPolicyError(REFUSAL_DOCUMENT_SYMLINK)

    if not os.path.exists(document_path):
        raise PilotPolicyError(REFUSAL_DOCUMENT_MISSING)
    try:
        st = os.lstat(document_path)
    except OSError:
        raise PilotPolicyError(REFUSAL_DOCUMENT_UNREADABLE)
    if not stat.S_ISREG(st.st_mode):
        raise PilotPolicyError(REFUSAL_DOCUMENT_NOT_REGULAR_FILE)

    if st.st_uid != os.getuid():
        raise PilotPolicyError(REFUSAL_DOCUMENT_OWNER_MISMATCH)
    if st.st_mode & 0o022:
        raise PilotPolicyError(REFUSAL_DOCUMENT_MODE_INSECURE)

    resolved_policy_root = os.path.realpath(policy_root)
    try:
        fd = os.open(document_path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        raise PilotPolicyError(REFUSAL_DOCUMENT_UNREADABLE)
    try:
        opened_stat = os.fstat(fd)
        if opened_stat.st_ino != st.st_ino or opened_stat.st_dev != st.st_dev:
            raise PilotPolicyError(REFUSAL_DOCUMENT_SYMLINK)
        opened_path = _fd_realpath(fd, document_path)
        if not _is_same_or_ancestor(resolved_policy_root, opened_path):
            raise PilotPolicyError(REFUSAL_DOCUMENT_SYMLINK)
        with os.fdopen(fd, "rb") as handle:
            fd = None
            raw_bytes = handle.read()
    except OSError:
        raise PilotPolicyError(REFUSAL_DOCUMENT_UNREADABLE)
    finally:
        if fd is not None:
            os.close(fd)

    try:
        raw = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)

    try:
        doc = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    if not isinstance(doc, dict):
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)

    validate_policy(doc)
    if doc["declaration"] != declaration:
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    return doc


def validate_policy(doc):
    """Structural validation of a policy document; returns the document."""
    if not isinstance(doc, dict) or set(doc.keys()) != _TOP_LEVEL_KEYS:
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)

    schema_version = doc["schemaVersion"]
    if type(schema_version) is not int or schema_version != POLICY_SCHEMA_VERSION:
        raise PilotPolicyError(REFUSAL_SCHEMA_VERSION_UNSUPPORTED)

    declaration = doc["declaration"]
    if not isinstance(declaration, str) or not declaration:
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)

    protected_targets = doc["protectedTargets"]
    if not isinstance(protected_targets, list) or not protected_targets:
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    for target in protected_targets:
        if not isinstance(target, str) or not target:
            raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)

    datastore = doc["datastore"]
    if not isinstance(datastore, dict) or set(datastore.keys()) != _DATASTORE_KEYS:
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    expected_identity = datastore["expectedIdentity"]
    connection_detail = datastore["connectionDetail"]
    if not isinstance(expected_identity, str) or not expected_identity:
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    if not isinstance(connection_detail, str) or not connection_detail:
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    _validate_observer(datastore["observer"])

    slots = doc["slots"]
    if not isinstance(slots, dict) or not slots:
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    for slot_id, slot in slots.items():
        try:
            pilot_slot.validate_slot_id(slot_id)
        except pilot_slot.PilotSlotError:
            raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
        _validate_slot(slot)

    return doc


def policy_material(policy):
    """Extract sensitive material strings grouped by class."""
    validate_policy(policy)
    expected_identities = []
    mintable_accounts = []
    connection_details = [
        policy["datastore"]["connectionDetail"],
        policy["datastore"]["expectedIdentity"],
    ]

    for slot in policy["slots"].values():
        for identity in slot["expectedIdentities"].values():
            expected_identities.append(identity)
        mintable = slot.get("mintableAccounts")
        if mintable is not None:
            for account in mintable:
                mintable_accounts.append(account)

    return {
        "expected-identity": sorted(set(expected_identities)),
        "mintable-account": sorted(set(mintable_accounts)),
        "connection-detail": sorted(set(connection_details)),
    }


def assert_results_only(result, material):
    """Refuse when serialized result embeds any policy material string."""
    if not isinstance(material, dict) or not _material_index(material):
        raise PilotPolicyError(REFUSAL_MATERIAL_INVALID)
    serialized = json.dumps(result, sort_keys=True, ensure_ascii=False)
    for material_class in MATERIAL_CLASSES:
        for value in material.get(material_class, []):
            if value in serialized:
                raise PilotPolicyError(REFUSAL_MATERIAL_IN_RESULT, detail=material_class)


def exercise_no_policy_material_in_reach(reach_roots, material, *, exercised_at=None):
    """Walk reach roots and scan file bytes for policy material."""
    _validate_exercise_reach_roots(reach_roots)
    if _material_is_vacuous(material):
        raise PilotPolicyError(REFUSAL_EXERCISE_VACUOUS)

    if exercised_at is None:
        exercised_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    findings = []
    scanned_files = 0
    scanned_bytes = 0
    material_index = _material_index(material)

    def _walk_onerror(_err):
        nonlocal walk_failed
        walk_failed = True

    for reach_root in reach_roots:
        walk_failed = False
        for dirpath, dirnames, filenames in os.walk(
            reach_root, followlinks=False, topdown=True, onerror=_walk_onerror
        ):
            if walk_failed:
                return _exercise_fail(
                    REFUSAL_EXERCISE_UNREADABLE,
                    exercised_at,
                    scanned_files,
                    scanned_bytes,
                    findings,
                )
            try:
                os.listdir(dirpath)
            except OSError:
                return _exercise_fail(
                    REFUSAL_EXERCISE_UNREADABLE,
                    exercised_at,
                    scanned_files,
                    scanned_bytes,
                    findings,
                )

            for name in dirnames + filenames:
                entry_path = os.path.join(dirpath, name)
                try:
                    entry_stat = os.lstat(entry_path)
                except OSError:
                    return _exercise_fail(
                        REFUSAL_EXERCISE_UNREADABLE,
                        exercised_at,
                        scanned_files,
                        scanned_bytes,
                        findings,
                    )
                if stat.S_ISDIR(entry_stat.st_mode):
                    continue
                if not stat.S_ISREG(entry_stat.st_mode):
                    continue

                try:
                    with open(entry_path, "rb") as handle:
                        content = handle.read()
                except OSError:
                    return _exercise_fail(
                        REFUSAL_EXERCISE_UNREADABLE,
                        exercised_at,
                        scanned_files,
                        scanned_bytes,
                        findings,
                    )

                scanned_files += 1
                scanned_bytes += len(content)
                for material_class, needle in material_index:
                    if needle in content:
                        findings.append(
                            {"path": entry_path, "materialClass": material_class}
                        )

        if walk_failed:
            return _exercise_fail(
                REFUSAL_EXERCISE_UNREADABLE,
                exercised_at,
                scanned_files,
                scanned_bytes,
                findings,
            )

    if scanned_files == 0:
        return _exercise_fail(
            REFUSAL_EXERCISE_VACUOUS,
            exercised_at,
            scanned_files,
            scanned_bytes,
            findings,
        )

    if findings:
        return {
            "kind": "policy-out-of-reach",
            "result": "fail",
            "reason": REASON_EXERCISE_MATERIAL_FOUND,
            "evidence": "policy material found in reach root",
            "scannedFiles": scanned_files,
            "scannedBytes": scanned_bytes,
            "findings": findings,
            "coverageLimits": [_COVERAGE_LIMIT_COMPRESSED],
            "exercisedAt": exercised_at,
        }

    return {
        "kind": "policy-out-of-reach",
        "result": "pass",
        "reason": None,
        "evidence": "no policy material found in reach root",
        "scannedFiles": scanned_files,
        "scannedBytes": scanned_bytes,
        "findings": [],
        "coverageLimits": [_COVERAGE_LIMIT_COMPRESSED],
        "exercisedAt": exercised_at,
    }


def _validate_reach_roots_list(reach_roots):
    if not isinstance(reach_roots, list):
        raise PilotPolicyError(REFUSAL_REACH_ROOT_INVALID)
    for reach_root in reach_roots:
        if not isinstance(reach_root, str) or not reach_root or not os.path.isabs(
            reach_root
        ):
            raise PilotPolicyError(REFUSAL_REACH_ROOT_INVALID)


def _validate_exercise_reach_roots(reach_roots):
    if not isinstance(reach_roots, list) or not reach_roots:
        raise PilotPolicyError(REFUSAL_REACH_ROOT_INVALID)
    for reach_root in reach_roots:
        if not isinstance(reach_root, str) or not reach_root or not os.path.isabs(
            reach_root
        ):
            raise PilotPolicyError(REFUSAL_REACH_ROOT_INVALID)
        if not os.path.isdir(reach_root):
            raise PilotPolicyError(REFUSAL_REACH_ROOT_INVALID)


def _policy_root_conflicts_with_reach(policy_root, reach_roots):
    policy_forms = [policy_root, os.path.realpath(policy_root)]
    for reach_root in reach_roots:
        reach_forms = [reach_root, os.path.realpath(reach_root)]
        for policy_form in policy_forms:
            for reach_form in reach_forms:
                if _paths_overlap(policy_form, reach_form):
                    return True
    return False


def _paths_overlap(left, right):
    left_real = os.path.realpath(left)
    right_real = os.path.realpath(right)
    return _is_same_or_ancestor(left_real, right_real) or _is_same_or_ancestor(
        right_real, left_real
    )


def _is_same_or_ancestor(ancestor, descendant):
    ancestor_parts = _path_parts(ancestor)
    descendant_parts = _path_parts(descendant)
    if len(ancestor_parts) > len(descendant_parts):
        return False
    return ancestor_parts == descendant_parts[: len(ancestor_parts)]


def _path_parts(path):
    return os.path.realpath(path).split(os.sep)


def _ancestors_including_self(path):
    absolute = path if os.path.isabs(path) else os.path.join(os.getcwd(), path)
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


def _validate_observer(observer):
    if observer is None:
        return
    if not isinstance(observer, dict) or set(observer.keys()) != _OBSERVER_KEYS:
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    command = observer["command"]
    if not isinstance(command, list) or not command:
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    for item in command:
        if not isinstance(item, str) or not item:
            raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    env_var = observer["connectionEnvVar"]
    if not isinstance(env_var, str) or not _ENV_VAR_RE.match(env_var):
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)


def _validate_slot(slot):
    if not isinstance(slot, dict):
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    extra = set(slot.keys()) - _SLOT_KEYS
    missing = _SLOT_REQUIRED_KEYS - set(slot.keys())
    if extra or missing:
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)

    origin = slot["origin"]
    if not isinstance(origin, str) or not origin:
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)

    redirects = slot["permittedRedirects"]
    if not isinstance(redirects, list):
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    for redirect in redirects:
        if not isinstance(redirect, str) or not redirect:
            raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)

    identities = slot["expectedIdentities"]
    if not isinstance(identities, dict) or not identities:
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    for account, identity in identities.items():
        if not isinstance(account, str) or not account:
            raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
        if not isinstance(identity, str) or not identity:
            raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)

    if "mintableAccounts" in slot:
        mintable = slot["mintableAccounts"]
        if not isinstance(mintable, list):
            raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
        for account in mintable:
            if not isinstance(account, str) or not account:
                raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)


def _material_is_vacuous(material):
    if not isinstance(material, dict):
        return True
    return not _material_index(material)


def _material_index(material):
    indexed = []
    for material_class in MATERIAL_CLASSES:
        for value in material.get(material_class, []):
            if isinstance(value, str) and value:
                indexed.append((material_class, value.encode("utf-8")))
    return indexed


def _fd_realpath(fd, fallback_path):
    proc_fd = "/proc/self/fd/%d" % fd
    if os.path.exists(proc_fd):
        try:
            return os.path.realpath(proc_fd)
        except OSError:
            pass
    return os.path.realpath(fallback_path)


def _exercise_fail(reason, exercised_at, scanned_files, scanned_bytes, findings):
    return {
        "kind": "policy-out-of-reach",
        "result": "fail",
        "reason": reason,
        "evidence": "policy exercise failed",
        "scannedFiles": scanned_files,
        "scannedBytes": scanned_bytes,
        "findings": findings,
        "coverageLimits": [_COVERAGE_LIMIT_COMPRESSED],
        "exercisedAt": exercised_at,
    }
