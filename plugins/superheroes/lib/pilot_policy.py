"""Pilot policy document resolution, material extraction, and reach exercise (A3).

Non-goals: no boundary binding, no provisioning — policy home only.
The policy document also carries the out-of-reach datastore containment declaration.
"""
import json
import os
import re
import stat
import time

import pilot_contract
import pilot_paths
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
REFUSAL_OWNERSHIP_PROBE_ACCOUNT_INVALID = "policy-ownership-probe-account-invalid"
REFUSAL_OWNERSHIP_PROBE_ACCOUNT_UNDECLARED = "policy-ownership-probe-account-undeclared"
REFUSAL_SCHEMA_VERSION_UNSUPPORTED = "policy-schema-version-unsupported"
REFUSAL_MATERIAL_IN_RESULT = "policy-material-in-result"
REFUSAL_MATERIAL_INVALID = "policy-material-invalid"
REFUSAL_EXERCISE_VACUOUS = "policy-exercise-vacuous"
REFUSAL_EXERCISE_UNREADABLE = "policy-exercise-unreadable"
REFUSAL_REACH_ROOT_INVALID = "policy-reach-root-invalid"

REASON_EXERCISE_MATERIAL_FOUND = "policy-exercise-material-found"

_DECLARATION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*\Z")
ENV_VAR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# An account name spelled like a bare field name is indistinguishable from a result's own schema
# key, so `assert_results_only` never matches one in key position (#861).
_FIELD_NAME_SHAPED_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*\Z")
# The one material class the key-position carve-out reaches. Account names are chosen by the
# project and collide with field names by construction; identities and connection details are not
# under naming pressure toward field names, and the policy schema lets either be a bare word, so
# neither may be exempted by spelling.
_KEY_CARVE_OUT_CLASS = "mintable-account"

_TOP_LEVEL_REQUIRED_KEYS = frozenset(
    {
        "schemaVersion",
        "declaration",
        "protectedTargets",
        "datastore",
        "slots",
    }
)
_TOP_LEVEL_ALLOWED_KEYS = _TOP_LEVEL_REQUIRED_KEYS | frozenset({"ownershipProbe"})
_DATASTORE_REQUIRED_KEYS = frozenset(
    {"expectedIdentity", "connectionDetail", "observer"}
)
_DATASTORE_KEYS = _DATASTORE_REQUIRED_KEYS | frozenset({"containment"})
CONTAINMENT_KEYS = frozenset({"permissions", "sentinel"})
CONTAINMENT_PERMISSIONS_KEYS = frozenset(
    {"cannotReachForeignNamespaces", "evidence"}
)
CONTAINMENT_SENTINEL_KEYS = frozenset(
    {"plantCommand", "probeCommand", "connectionEnvVar"}
)
# `{namespace}` is declaration grammar and homes in `pilot_contract`, which validates it on the
# declared cleanup command; `{sentinel}` is containment grammar and homes here, where the
# sentinel commands are validated. Each token has exactly one literal in the library, and
# `test_pilot_placeholder_census` is the census that keeps it that way (#866).
NAMESPACE_PLACEHOLDER = pilot_contract.NAMESPACE_PLACEHOLDER
SENTINEL_PLACEHOLDER = "{sentinel}"
ACCOUNT_PLACEHOLDER = "{account}"
ACCOUNT_CLASS_TOKEN_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}\Z")
_PLACEHOLDER_RE = pilot_contract.PLACEHOLDER_RE
_ALLOWED_PLACEHOLDERS = frozenset(
    {NAMESPACE_PLACEHOLDER, SENTINEL_PLACEHOLDER}
)
_OWNERSHIP_PROBE_KEYS = frozenset({"command", "connectionEnvVar"})
OBSERVER_KEYS = frozenset({"command", "connectionEnvVar"})
_SLOT_KEYS = frozenset(
    {
        "origin",
        "permittedRedirects",
        "expectedIdentities",
        "mintableAccounts",
        "accountClasses",
    }
)
_SLOT_REQUIRED_KEYS = frozenset(
    {"origin", "permittedRedirects", "expectedIdentities"}
)

_COVERAGE_LIMIT_COMPRESSED = (
    "Compressed and archived content is scanned as raw bytes; material inside "
    "it is not detectable."
)
_COVERAGE_LIMIT_SYMLINKS = (
    "Symbolic links inside reach roots are not followed; content reachable only "
    "through a symlink is not scanned."
)
_EXERCISE_CHUNK_SIZE = 64 * 1024


class PilotPolicyError(Exception):
    """Raised when policy resolution, validation, or exercise refuses."""

    def __init__(self, reason, detail=None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def resolve_policy_document(policy_root, declaration, *, reach_roots):
    """Return the validated policy document from outside branch-mutable reach."""
    # bite-axis: document trust — policy root must be outside reach; document must be owner-owned,
    # mode-safe, inode-stable via O_NOFOLLOW open, and readable; symlink or traversal escape refuses.
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
    # bite-axis: document structure — schema version, top-level keys, datastore, slots, and each
    # slot shape must match the policy schema; any structural violation raises REFUSAL_DOCUMENT_INVALID.
    if not isinstance(doc, dict):
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    extra = set(doc.keys()) - _TOP_LEVEL_ALLOWED_KEYS
    missing = _TOP_LEVEL_REQUIRED_KEYS - set(doc.keys())
    if extra or missing:
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
    if not isinstance(datastore, dict):
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    datastore_keys = set(datastore.keys())
    if datastore_keys - _DATASTORE_KEYS or datastore_keys < _DATASTORE_REQUIRED_KEYS:
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    expected_identity = datastore["expectedIdentity"]
    connection_detail = datastore["connectionDetail"]
    if not isinstance(expected_identity, str) or not expected_identity:
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    if not isinstance(connection_detail, str) or not connection_detail:
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    _validate_observer(datastore["observer"])
    if "containment" in datastore:
        _validate_containment(datastore["containment"])

    slots = doc["slots"]
    if not isinstance(slots, dict) or not slots:
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    for slot_id, slot in slots.items():
        try:
            pilot_slot.validate_slot_id(slot_id)
        except pilot_slot.PilotSlotError:
            raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
        _validate_slot(slot)

    ownership_probe = doc.get("ownershipProbe")
    if ownership_probe is not None:
        if (
            not isinstance(ownership_probe, dict)
            or set(ownership_probe.keys()) != _OWNERSHIP_PROBE_KEYS
        ):
            raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
        _validate_ownership_probe_command(ownership_probe["command"])
        env_var = ownership_probe["connectionEnvVar"]
        if not isinstance(env_var, str) or not ENV_VAR_RE.match(env_var):
            raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)

    return doc


def policy_material(policy):
    """Extract sensitive material strings grouped by class."""
    # bite-axis: material extraction — all expected-identity, mintable-account, and
    # connection-detail strings are collected from a validated policy for downstream leakage and
    # exercise checks.
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
    """Refuse when result structure embeds any policy material string."""
    # bite-axis: material leakage — any policy material string present as a result *value* raises
    # REFUSAL_MATERIAL_IN_RESULT; comparing serialized form misses JSON-escaped material.
    #
    # A dict value is data. A dict key is the result's shape — a field name the producer wrote. The
    # guard cannot tell the two apart when they spell the same word, and account names are exactly
    # the short bare words that field names use (#861: a plan step keyed `owner` met an account
    # named `owner` and refused, with nothing in the refusal to say the account NAME, not a leak,
    # was the cause). So a field-name-shaped ACCOUNT NAME is matched against values only.
    #
    # The carve-out is keyed on the material class as well as the spelling, and both conditions are
    # load-bearing. The schema permits any non-empty string for an identity or a connection detail,
    # and bare ones are ordinary — the contract's own example datastore identity is `example_dev`.
    # Exempting those by spelling would drop key-position detection for real secrets that are under
    # no naming pressure toward field names. Only account names are chosen by the project in the
    # same vocabulary its result fields use, so only they are exempt.
    if not isinstance(material, dict) or not _material_index(material):
        raise PilotPolicyError(REFUSAL_MATERIAL_INVALID)
    for material_class in MATERIAL_CLASSES:
        for needle in material.get(material_class, []):
            if not isinstance(needle, str) or not needle:
                continue
            match_keys = not (
                material_class == _KEY_CARVE_OUT_CLASS
                and _FIELD_NAME_SHAPED_RE.match(needle)
            )
            if _result_embeds_material(result, needle, match_keys=match_keys):
                raise PilotPolicyError(REFUSAL_MATERIAL_IN_RESULT, detail=material_class)


def _result_embeds_material(value, needle, *, match_keys):
    if isinstance(value, str):
        return value == needle
    if isinstance(value, dict):
        for key, item in value.items():
            if match_keys and isinstance(key, str) and key == needle:
                return True
            if _result_embeds_material(item, needle, match_keys=match_keys):
                return True
        return False
    if isinstance(value, list):
        for item in value:
            if _result_embeds_material(item, needle, match_keys=match_keys):
                return True
        return False
    return False


def exercise_no_policy_material_in_reach(reach_roots, material, *, exercised_at=None):
    """Walk reach roots and scan file bytes for policy material."""
    # bite-axis: non-vacuity plus fail-closed reads — a scan that searched for zero needles,
    # covered zero files, or could not read a file or directory is a failure, never a pass.
    _validate_exercise_reach_roots(reach_roots)
    if _material_is_vacuous(material):
        raise PilotPolicyError(REFUSAL_EXERCISE_VACUOUS)

    if exercised_at is None:
        exercised_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    findings = []
    scanned_files = 0
    scanned_bytes = 0
    symlinks_skipped = 0
    material_index = _material_index(material)
    max_needle_len = max((len(needle) for _, needle in material_index), default=0)
    overlap = max(0, max_needle_len - 1)

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
                    symlinks_skipped,
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
                    symlinks_skipped,
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
                        symlinks_skipped,
                    )
                if stat.S_ISLNK(entry_stat.st_mode):
                    # bite-axis: symlink disclosure — symbolic links inside reach roots are counted
                    # and disclosed rather than followed or silently skipped.
                    symlinks_skipped += 1
                    continue
                if stat.S_ISDIR(entry_stat.st_mode):
                    continue
                if not stat.S_ISREG(entry_stat.st_mode):
                    continue

                try:
                    with open(entry_path, "rb") as handle:
                        file_bytes, file_findings = _scan_file_bytes(
                            handle, material_index, overlap
                        )
                except (OSError, MemoryError):
                    return _exercise_fail(
                        REFUSAL_EXERCISE_UNREADABLE,
                        exercised_at,
                        scanned_files,
                        scanned_bytes,
                        findings,
                        symlinks_skipped,
                    )
                if file_bytes is None:
                    return _exercise_fail(
                        REFUSAL_EXERCISE_UNREADABLE,
                        exercised_at,
                        scanned_files,
                        scanned_bytes,
                        findings,
                        symlinks_skipped,
                    )

                scanned_files += 1
                scanned_bytes += file_bytes
                for material_class in file_findings:
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
                symlinks_skipped,
            )

    if scanned_files == 0:
        return _exercise_fail(
            REFUSAL_EXERCISE_VACUOUS,
            exercised_at,
            scanned_files,
            scanned_bytes,
            findings,
            symlinks_skipped,
        )

    coverage_limits = _exercise_coverage_limits(symlinks_skipped)

    if findings:
        return {
            "kind": "policy-out-of-reach",
            "result": "fail",
            "reason": REASON_EXERCISE_MATERIAL_FOUND,
            "evidence": "policy material found in reach root",
            "scannedFiles": scanned_files,
            "scannedBytes": scanned_bytes,
            "findings": findings,
            "coverageLimits": coverage_limits,
            "symlinksSkipped": symlinks_skipped,
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
        "coverageLimits": coverage_limits,
        "symlinksSkipped": symlinks_skipped,
        "exercisedAt": exercised_at,
    }


def _validate_reach_roots_list(reach_roots):
    # bite-axis: reach-root vacuity — empty reach_roots makes policy-root containment vacuous;
    # refuse before resolution proceeds.
    if not isinstance(reach_roots, list) or not reach_roots:
        raise PilotPolicyError(REFUSAL_REACH_ROOT_INVALID)
    for reach_root in reach_roots:
        if not isinstance(reach_root, str) or not reach_root or not os.path.isabs(
            reach_root
        ):
            raise PilotPolicyError(REFUSAL_REACH_ROOT_INVALID)


def _validate_exercise_reach_roots(reach_roots):
    # bite-axis: reach root existence — each reach root must be a non-empty absolute path to an
    # existing directory before exercise walks it.
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
    # bite-axis: policy-root separation — policy root overlapping any reach root (raw or
    # realpath) refuses resolution with REFUSAL_POLICY_ROOT_IN_REACH.
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
    # bite-axis: path ancestry — descendant path components must share the ancestor prefix; used
    # to detect symlink escapes and policy-root overlap.
    return pilot_paths.is_inside(descendant, ancestor)


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


def _validate_containment(containment):
    # bite-axis: containment shape — optional datastore declaration for permissions and sentinel
    # probes; when present every field is validated fail-closed.
    if not isinstance(containment, dict) or set(containment.keys()) != CONTAINMENT_KEYS:
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)

    permissions = containment["permissions"]
    if permissions is not None:
        if (
            not isinstance(permissions, dict)
            or set(permissions.keys()) != CONTAINMENT_PERMISSIONS_KEYS
        ):
            raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
        cannot_reach = permissions["cannotReachForeignNamespaces"]
        if type(cannot_reach) is not bool:
            raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
        evidence = permissions["evidence"]
        if not isinstance(evidence, str) or not evidence:
            raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)

    sentinel = containment["sentinel"]
    if sentinel is not None:
        if (
            not isinstance(sentinel, dict)
            or set(sentinel.keys()) != CONTAINMENT_SENTINEL_KEYS
        ):
            raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
        _validate_sentinel_command(sentinel["plantCommand"])
        _validate_sentinel_command(sentinel["probeCommand"])
        env_var = sentinel["connectionEnvVar"]
        if not isinstance(env_var, str) or not ENV_VAR_RE.match(env_var):
            raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)


def _validate_placeholder_command(
    command, *, required_placeholders, allowed_placeholders
):
    if not isinstance(command, list) or not command:
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    for item in command:
        if not isinstance(item, str) or not item:
            raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    executable = command[0]
    if not os.path.isabs(executable):
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    if _PLACEHOLDER_RE.findall(executable):
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    args = command[1:]
    for placeholder in required_placeholders:
        if not any(placeholder in part for part in args):
            raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    for part in command:
        for match in _PLACEHOLDER_RE.findall(part):
            if match not in allowed_placeholders:
                raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)


def _validate_sentinel_command(command):
    _validate_placeholder_command(
        command,
        required_placeholders=(
            NAMESPACE_PLACEHOLDER,
            SENTINEL_PLACEHOLDER,
        ),
        allowed_placeholders=_ALLOWED_PLACEHOLDERS,
    )


def _validate_ownership_probe_command(command):
    _validate_placeholder_command(
        command,
        required_placeholders=(ACCOUNT_PLACEHOLDER,),
        allowed_placeholders=frozenset({ACCOUNT_PLACEHOLDER}),
    )


def _declared_slot_accounts(policy):
    accounts = set()
    slots = policy.get("slots")
    if not isinstance(slots, dict):
        return accounts
    for slot in slots.values():
        if not isinstance(slot, dict):
            continue
        identities = slot.get("expectedIdentities")
        if not isinstance(identities, dict):
            continue
        for declared_account in identities:
            if isinstance(declared_account, str) and declared_account:
                accounts.add(declared_account)
    return accounts


def ownership_probe_request(policy, account):
    """Return the resolved argv and environment for the policy's ownership probe."""
    validate_policy(policy)
    ownership_probe = policy.get("ownershipProbe")
    if ownership_probe is None:
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    if not isinstance(account, str) or not account:
        raise PilotPolicyError(REFUSAL_OWNERSHIP_PROBE_ACCOUNT_INVALID)
    if not _FIELD_NAME_SHAPED_RE.match(account):
        raise PilotPolicyError(REFUSAL_OWNERSHIP_PROBE_ACCOUNT_INVALID)
    if account not in _declared_slot_accounts(policy):
        raise PilotPolicyError(REFUSAL_OWNERSHIP_PROBE_ACCOUNT_UNDECLARED)

    command = ownership_probe["command"]
    resolved_argv = [command[0]]
    for part in command[1:]:
        resolved_argv.append(part.replace(ACCOUNT_PLACEHOLDER, account))
    return {
        "argv": resolved_argv,
        "connectionEnvVar": ownership_probe["connectionEnvVar"],
    }


def _validate_observer(observer):
    # bite-axis: observer shape — when present, observer must be a dict with only command and
    # connectionEnvVar keys and each field must be a valid non-empty string or command list.
    if observer is None:
        return
    if not isinstance(observer, dict) or set(observer.keys()) != OBSERVER_KEYS:
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    command = observer["command"]
    if not isinstance(command, list) or not command:
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    for item in command:
        if not isinstance(item, str) or not item:
            raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
    env_var = observer["connectionEnvVar"]
    if not isinstance(env_var, str) or not ENV_VAR_RE.match(env_var):
        raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)


def _validate_slot(slot):
    # bite-axis: slot shape — each slot must have required keys with non-empty origin, redirects
    # list, and expectedIdentities dict; optional mintableAccounts must be a list of non-empty
    # strings.
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

    if "accountClasses" in slot:
        account_classes = slot["accountClasses"]
        if not isinstance(account_classes, dict) or not account_classes:
            raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
        for account, class_token in account_classes.items():
            if not isinstance(account, str) or not account:
                raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)
            if (
                not isinstance(class_token, str)
                or not ACCOUNT_CLASS_TOKEN_RE.match(class_token)
            ):
                raise PilotPolicyError(REFUSAL_DOCUMENT_INVALID)


def _material_is_vacuous(material):
    if not isinstance(material, dict):
        return True
    return not _material_index(material)


def _material_index(material):
    # bite-axis: material indexing — only non-empty string material values are UTF-8-encoded into
    # scan needles; empty or wrong-type material makes exercise vacuous.
    indexed = []
    for material_class in MATERIAL_CLASSES:
        for value in material.get(material_class, []):
            if isinstance(value, str) and value:
                indexed.append((material_class, value.encode("utf-8")))
    return indexed


def _fd_realpath(fd, fallback_path):
    # bite-disclosure: on platforms without /proc/self/fd (macOS among them), falls back to
    # os.path.realpath(fallback_path) which re-resolves by name rather than by descriptor and
    # does not fully close the window between the check and the open; the O_NOFOLLOW open plus
    # inode/device comparison is what carries the guarantee there.
    proc_fd = "/proc/self/fd/%d" % fd
    if os.path.exists(proc_fd):
        try:
            return os.path.realpath(proc_fd)
        except OSError:
            pass
    return os.path.realpath(fallback_path)


def _scan_file_bytes(handle, material_index, overlap):
    # bite-axis: bounded scan — file bytes are read in chunks with cross-chunk overlap so
    # needles straddling chunk boundaries are still found; MemoryError fails closed.
    carry = b""
    scanned = 0
    found_classes = []
    while True:
        try:
            chunk = handle.read(_EXERCISE_CHUNK_SIZE)
        except (OSError, MemoryError):
            return None, []
        if not chunk:
            buffer = carry
            for material_class, needle in material_index:
                if needle in buffer and material_class not in found_classes:
                    found_classes.append(material_class)
            return scanned, found_classes

        scanned += len(chunk)
        buffer = carry + chunk
        for material_class, needle in material_index:
            if needle in buffer and material_class not in found_classes:
                found_classes.append(material_class)
        carry = buffer[-overlap:] if overlap else b""


def _exercise_coverage_limits(symlinks_skipped):
    limits = [_COVERAGE_LIMIT_COMPRESSED]
    if symlinks_skipped > 0:
        limits.append(
            "%s (%d symbolic link(s) skipped during this exercise.)"
            % (_COVERAGE_LIMIT_SYMLINKS, symlinks_skipped)
        )
    return limits


def _exercise_fail(reason, exercised_at, scanned_files, scanned_bytes, findings, symlinks_skipped):
    return {
        "kind": "policy-out-of-reach",
        "result": "fail",
        "reason": reason,
        "evidence": "policy exercise failed",
        "scannedFiles": scanned_files,
        "scannedBytes": scanned_bytes,
        "findings": findings,
        "coverageLimits": _exercise_coverage_limits(symlinks_skipped),
        "symlinksSkipped": symlinks_skipped,
        "exercisedAt": exercised_at,
    }
