"""Cleanup-command resolution, sentinel instrumentation, containment receipts, and resurrection planning (C9)."""
import copy
import hashlib
import hmac
import json
import os
import re
import secrets
import signal
import stat
import subprocess
import threading
import unicodedata

import pilot_boundary
import pilot_contract
import pilot_journal
import pilot_policy
import pilot_provision
import pilot_slot

REFUSAL_NAMESPACE_INVALID = "cleanup-namespace-invalid"
REFUSAL_COMMAND_INVALID = "cleanup-command-invalid"
REFUSAL_COMMAND_UNPARAMETERIZED = "cleanup-command-unparameterized"
REFUSAL_COMMAND_ARGV0_PLACEHOLDER = "cleanup-command-argv0-placeholder"
REFUSAL_COMMAND_PLACEHOLDER_UNKNOWN = "cleanup-command-placeholder-unknown"
REFUSAL_SUBSTITUTION_EMPTY = "cleanup-substitution-empty"
REFUSAL_SENTINEL_UNDECLARED = "cleanup-sentinel-undeclared"
REFUSAL_SENTINEL_DECLARATION_INVALID = "cleanup-sentinel-declaration-invalid"
REFUSAL_SENTINEL_CONFINEMENT = "cleanup-sentinel-confinement"
REFUSAL_SENTINEL_ID_INVALID = "cleanup-sentinel-id-invalid"
REFUSAL_PLANT_FAILED = "cleanup-sentinel-plant-failed"
REFUSAL_PROBE_INDETERMINATE = "cleanup-sentinel-probe-indeterminate"
REFUSAL_SOURCE_ROOT_INVALID = "cleanup-source-root-invalid"
REFUSAL_SOURCE_UNREADABLE = "cleanup-source-unreadable"
REFUSAL_POLICY_INVALID = "cleanup-policy-invalid"
REFUSAL_CLEANUP_ARGV0_NOT_ABSOLUTE = "cleanup-argv0-not-absolute"

KIND_CLEANUP_CONTAINMENT = "cleanup-containment"

MODE_PERMISSIONS = "permissions"
MODE_RECEIPT = "receipt"
MODE_SINGLE_SLOT = "single-slot"
MODE_REFUSED = "refused"

RESULT_PASS = "pass"
RESULT_FAIL = "fail"

ACTION_PARK = "park"
ACTION_RESURRECT = "resurrect"
ACTION_REFUSE = "refuse"

REASON_RECEIPT_VACUOUS = "cleanup-receipt-vacuous"
REASON_OWN_SENTINEL_SURVIVED = "cleanup-own-sentinel-survived"
REASON_FOREIGN_SENTINEL_DESTROYED = "cleanup-foreign-sentinel-destroyed"
REASON_CLEANUP_COMMAND_FAILED = "cleanup-command-failed"
REASON_NO_FOREIGN_NAMESPACE = "cleanup-no-foreign-namespace"

REASON_RECEIPT_SCHEMA_INVALID = "receipt-schema-invalid"
REASON_RECEIPT_NOT_PASS = "receipt-result-not-pass"
REASON_RECEIPT_SLOT_MISMATCH = "receipt-slot-mismatch"
REASON_RECEIPT_STALE_COMMAND = "receipt-stale-command"
REASON_RECEIPT_STALE_CONFIG = "receipt-stale-config"

REASON_CONTAINMENT_UNDECLARED = "containment-undeclared"

REASON_EFFECTS_ESCAPE_PARK = "resurrection-effects-escape-park"
REASON_EFFECTS_ESCAPE_UNEXERCISED = "resurrection-effects-escape-unexercised"
REASON_CONTAINMENT_UNRESOLVED = "resurrection-containment-unresolved"
REASON_CONTAINMENT_UNEXERCISED = "resurrection-cleanup-containment-unexercised"
REASON_VERDICT_MISSING = "resurrection-verdict-missing"

ASSURANCE_LIMITS = (
    "This receipt is evidence about one execution of one cleanup command. It shows that a "
    "stale, buggy, or edited cleanup did not reach a foreign namespace on this run.",
    "It is NOT a defense against hostile cleanup code. A cleanup with datastore access can "
    "preserve or recreate a sentinel while destroying other foreign data, so a passing receipt "
    "does not establish containment against an adversary. Datastore permissions that cannot "
    "reach foreign namespaces are the stronger assurance, which is why resolve_containment "
    "prefers them.",
)

NAMESPACE_PLACEHOLDER = "{namespace}"
SENTINEL_PLACEHOLDER = "{sentinel}"

_PLACEHOLDER_RE = re.compile(r"\{[^{}]*\}")
_SENTINEL_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_HEAD_RE = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")

_SENTINEL_KEYS = frozenset({"plantCommand", "probeCommand", "connectionEnvVar"})

_RECEIPT_SCHEMA_KEYS = frozenset({
    "kind",
    "result",
    "reason",
    "evidence",
    "slot",
    "slotRef",
    "namespace",
    "foreignNamespaces",
    "commandDigest",
    "configDigest",
    "identityProvenance",
    "identityStrength",
    "observations",
    "residualSentinels",
    "assuranceLimits",
    "exercisedAt",
})

_CONTAINMENT_RESOLVED_MODES = frozenset({
    MODE_PERMISSIONS,
    MODE_RECEIPT,
    MODE_SINGLE_SLOT,
})


class PilotCleanupError(Exception):
    def __init__(self, reason, detail=None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def namespace_for_slot(slot):
    """Return the cleanup namespace token for ``slot`` — the slot id itself.

    Generation is deliberately excluded: resurrection must clean data written by the *previous*
    generation, so a generation-scoped namespace would leave exactly the rows resurrection exists
    to remove.
    """
    try:
        return pilot_slot.validate_slot_id(slot)
    except pilot_slot.PilotSlotError:
        raise PilotCleanupError(REFUSAL_NAMESPACE_INVALID)


def foreign_namespaces(policy, slot):
    """Return sorted sibling slot ids that a correct cleanup must not touch.

    Every other declared slot is returned, not a single arbitrary foreign namespace: with slots
    ``a``, ``ab``, and ``b``, a cleanup that deletes by the prefix ``a*`` destroys ``ab`` while
    leaving ``b`` untouched — testing against one foreign namespace would pass.
    """
    if not isinstance(policy, dict):
        raise PilotCleanupError(REFUSAL_POLICY_INVALID)
    slots = policy.get("slots")
    if not isinstance(slots, dict) or not slots:
        raise PilotCleanupError(REFUSAL_POLICY_INVALID)
    if slot not in slots:
        raise PilotCleanupError(REFUSAL_POLICY_INVALID)
    for slot_id in slots:
        try:
            pilot_slot.validate_slot_id(slot_id)
        except pilot_slot.PilotSlotError:
            raise PilotCleanupError(REFUSAL_POLICY_INVALID)
    return sorted(sid for sid in slots if sid != slot)


def resolve_cleanup_command(command, namespace):
    """Substitute ``{namespace}`` into a declared cleanup argv and return the resolved list.

    Re-checks what ``pilot_contract`` validates at the call site that actually runs the command —
    the in-code refusal that stops the framework ever invoking an unparameterized destructive
    command.
    """
    if not isinstance(command, list) or not command:
        raise PilotCleanupError(REFUSAL_COMMAND_INVALID)
    for part in command:
        if not isinstance(part, str) or not part:
            raise PilotCleanupError(REFUSAL_COMMAND_INVALID)

    try:
        namespace = pilot_slot.validate_slot_id(namespace)
    except pilot_slot.PilotSlotError:
        raise PilotCleanupError(REFUSAL_NAMESPACE_INVALID)

    for part in command:
        for match in _PLACEHOLDER_RE.findall(part):
            if match != NAMESPACE_PLACEHOLDER:
                raise PilotCleanupError(REFUSAL_COMMAND_PLACEHOLDER_UNKNOWN)

    if NAMESPACE_PLACEHOLDER in command[0]:
        raise PilotCleanupError(REFUSAL_COMMAND_ARGV0_PLACEHOLDER)

    if not any(NAMESPACE_PLACEHOLDER in part for part in command[1:]):
        raise PilotCleanupError(REFUSAL_COMMAND_UNPARAMETERIZED)

    resolved = [part.replace(NAMESPACE_PLACEHOLDER, namespace) for part in command]
    for part in resolved:
        if not part:
            raise PilotCleanupError(REFUSAL_SUBSTITUTION_EMPTY)
    if not any(namespace in part for part in resolved):
        raise PilotCleanupError(REFUSAL_COMMAND_UNPARAMETERIZED)
    return resolved


def substitute_sentinel_command(command, namespace, sentinel_id):
    """Substitute ``{namespace}`` and ``{sentinel}`` into a plant/probe argv."""
    if not isinstance(command, list) or not command:
        raise PilotCleanupError(REFUSAL_COMMAND_INVALID)
    for part in command:
        if not isinstance(part, str) or not part:
            raise PilotCleanupError(REFUSAL_COMMAND_INVALID)

    try:
        namespace = pilot_slot.validate_slot_id(namespace)
    except pilot_slot.PilotSlotError:
        raise PilotCleanupError(REFUSAL_NAMESPACE_INVALID)

    if not isinstance(sentinel_id, str) or not _SENTINEL_ID_RE.match(sentinel_id):
        raise PilotCleanupError(REFUSAL_SENTINEL_ID_INVALID)

    for part in command:
        for match in _PLACEHOLDER_RE.findall(part):
            if match not in (NAMESPACE_PLACEHOLDER, SENTINEL_PLACEHOLDER):
                raise PilotCleanupError(REFUSAL_COMMAND_PLACEHOLDER_UNKNOWN)

    if NAMESPACE_PLACEHOLDER in command[0] or SENTINEL_PLACEHOLDER in command[0]:
        raise PilotCleanupError(REFUSAL_COMMAND_ARGV0_PLACEHOLDER)

    if not any(NAMESPACE_PLACEHOLDER in part for part in command[1:]):
        raise PilotCleanupError(REFUSAL_COMMAND_UNPARAMETERIZED)
    if not any(SENTINEL_PLACEHOLDER in part for part in command[1:]):
        raise PilotCleanupError(REFUSAL_COMMAND_UNPARAMETERIZED)

    resolved = [
        part.replace(NAMESPACE_PLACEHOLDER, namespace).replace(SENTINEL_PLACEHOLDER, sentinel_id)
        for part in command
    ]
    for part in resolved:
        if not part:
            raise PilotCleanupError(REFUSAL_SUBSTITUTION_EMPTY)
    if not any(namespace in part for part in resolved):
        raise PilotCleanupError(REFUSAL_COMMAND_UNPARAMETERIZED)
    if not any(sentinel_id in part for part in resolved):
        raise PilotCleanupError(REFUSAL_COMMAND_UNPARAMETERIZED)
    return resolved


def mint_sentinel_id():
    """Return a fresh unpredictable sentinel identifier (32 hex chars).

    A stale sentinel left by an interrupted run would otherwise make a silently-failed plant look
    like a successful one, and a predictable canary is one a modified cleanup can special-case.
    """
    return secrets.token_hex(16)


def run_bounded(command, *, cwd, env, timeout_seconds=20, max_output_bytes=4096):
    """Run ``command`` with bounded stdout; report exit code without judging it."""
    try:
        proc = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=False,
            env=env,
            start_new_session=True,
        )
    except OSError:
        raise PilotCleanupError(REFUSAL_PROBE_INDETERMINATE)

    timed_out = False
    stdout_bytes = 0
    stdout_truncated = False
    try:
        stdout_holder = []

        def _read_stdout():
            total = 0
            truncated = False
            try:
                while True:
                    chunk = proc.stdout.read(65536)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_output_bytes:
                        truncated = True
            except Exception:
                total = 0
                truncated = False
            stdout_holder.append((total, truncated))

        reader = threading.Thread(target=_read_stdout, daemon=True)
        reader.start()
        reader.join(timeout=timeout_seconds)

        if reader.is_alive():
            _terminate_and_wait(proc)
            timed_out = True
        else:
            total, truncated = stdout_holder[0] if stdout_holder else (0, False)
            stdout_truncated = truncated
            stdout_bytes = min(total, max_output_bytes)
            try:
                proc.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                _terminate_and_wait(proc)
                timed_out = True

        exit_code = None if timed_out else proc.returncode
        return {
            "exit": exit_code,
            "timedOut": timed_out,
            "stdoutBytes": stdout_bytes,
            "stdoutTruncated": stdout_truncated,
        }
    except Exception:
        _terminate_and_wait(proc)
        raise PilotCleanupError(REFUSAL_PROBE_INDETERMINATE)
    finally:
        if proc.poll() is None:
            _terminate_and_wait(proc)
        if proc.stdout:
            proc.stdout.close()


def _validate_sentinel_declaration(sentinel, *, reach_roots, run_cwd):
    if not isinstance(sentinel, dict) or set(sentinel.keys()) != _SENTINEL_KEYS:
        raise PilotCleanupError(REFUSAL_SENTINEL_DECLARATION_INVALID)

    env_var = sentinel["connectionEnvVar"]
    if not isinstance(env_var, str) or not pilot_policy.ENV_VAR_RE.match(env_var):
        raise PilotCleanupError(REFUSAL_SENTINEL_DECLARATION_INVALID)

    if not isinstance(reach_roots, list) or not reach_roots:
        raise PilotCleanupError(REFUSAL_SENTINEL_CONFINEMENT)
    for root in reach_roots:
        if not isinstance(root, str) or not os.path.isabs(root):
            raise PilotCleanupError(REFUSAL_SENTINEL_CONFINEMENT)

    if not isinstance(run_cwd, str) or not os.path.isdir(run_cwd):
        raise PilotCleanupError(REFUSAL_SENTINEL_CONFINEMENT)

    for key in ("plantCommand", "probeCommand"):
        command = sentinel[key]
        if not isinstance(command, list) or not command:
            raise PilotCleanupError(REFUSAL_SENTINEL_DECLARATION_INVALID)
        for part in command:
            if not isinstance(part, str) or not part:
                raise PilotCleanupError(REFUSAL_SENTINEL_DECLARATION_INVALID)
        executable = command[0]
        if not os.path.isabs(executable):
            raise PilotCleanupError(REFUSAL_SENTINEL_CONFINEMENT)
        try:
            st = os.stat(executable)
        except OSError:
            raise PilotCleanupError(REFUSAL_SENTINEL_CONFINEMENT)
        if not stat.S_ISREG(st.st_mode):
            raise PilotCleanupError(REFUSAL_SENTINEL_CONFINEMENT)
        if st.st_uid != os.getuid():
            raise PilotCleanupError(REFUSAL_SENTINEL_CONFINEMENT)
        if st.st_mode & 0o022:
            raise PilotCleanupError(REFUSAL_SENTINEL_CONFINEMENT)
        # The cleanup command under test lives in the branch-mutable pilot block and is deliberately
        # not confined; sentinel instruments from the out-of-reach policy are confined because an
        # instrument a branch can edit can forge its own verdict.
        if not pilot_boundary.is_outside_all_reach_roots(executable, reach_roots):
            raise PilotCleanupError(REFUSAL_SENTINEL_CONFINEMENT)

        for part in command[1:]:
            candidate = part if os.path.isabs(part) else os.path.join(run_cwd, part)
            resolved = os.path.realpath(candidate)
            if not pilot_boundary.is_outside_all_reach_roots(resolved, reach_roots):
                raise PilotCleanupError(REFUSAL_SENTINEL_CONFINEMENT)

    if not pilot_boundary.is_outside_all_reach_roots(run_cwd, reach_roots):
        raise PilotCleanupError(REFUSAL_SENTINEL_CONFINEMENT)


def plant_sentinel(
    sentinel,
    namespace,
    sentinel_id,
    *,
    connection_detail,
    reach_roots,
    run_cwd,
    timeout_seconds=20,
):
    """Validate the declaration, plant a sentinel, and refuse on any non-zero exit or timeout."""
    _validate_sentinel_declaration(sentinel, reach_roots=reach_roots, run_cwd=run_cwd)
    command = substitute_sentinel_command(sentinel["plantCommand"], namespace, sentinel_id)
    env_var = sentinel["connectionEnvVar"]
    result = run_bounded(
        command,
        cwd=run_cwd,
        env={env_var: connection_detail},
        timeout_seconds=timeout_seconds,
    )
    if result["timedOut"] or result["exit"] != 0:
        raise PilotCleanupError(REFUSAL_PLANT_FAILED)
    return None


def probe_sentinel(
    sentinel,
    namespace,
    sentinel_id,
    *,
    connection_detail,
    reach_roots,
    run_cwd,
    timeout_seconds=20,
):
    """Probe sentinel presence: exit 0 → present, exit 1 → absent; anything else is indeterminate.

    Indeterminate is never silently coerced to present or absent — an unreadable probe must stop
    the receipt, not produce a guess.
    """
    _validate_sentinel_declaration(sentinel, reach_roots=reach_roots, run_cwd=run_cwd)
    command = substitute_sentinel_command(sentinel["probeCommand"], namespace, sentinel_id)
    env_var = sentinel["connectionEnvVar"]
    result = run_bounded(
        command,
        cwd=run_cwd,
        env={env_var: connection_detail},
        timeout_seconds=timeout_seconds,
    )
    if result["timedOut"]:
        raise PilotCleanupError(REFUSAL_PROBE_INDETERMINATE)
    exit_code = result["exit"]
    if exit_code == 0:
        return {"present": True}
    if exit_code == 1:
        return {"present": False}
    raise PilotCleanupError(REFUSAL_PROBE_INDETERMINATE)


def binding_key(policy):
    """Return raw SHA-256 digest bytes of the canonical policy JSON — an HMAC key, never published.

    The key is the whole policy because the config digest binds a low-entropy datastore identity,
    and an unkeyed truncated digest of a value like a database name is a dictionary oracle that
    would recover the very material A3 keeps out of results. A validator that can legitimately
    re-check a receipt already holds the policy; a reader who does not, cannot attack it.
    """
    payload = _canonical_json(_nfc_normalize(policy))
    return hashlib.sha256(payload.encode("utf-8")).digest()


def config_digest(
    policy,
    *,
    resolved_cleanup_argv,
    sentinel,
    namespace,
    foreign_namespaces,
    run_cwd,
    identity_provenance,
    identity_strength,
    observed_identity,
    source_identity,
):
    """Return the full HMAC-SHA256 hex digest of the receipt binding payload.

    The payload contains policy material by design and is never published — only the HMAC of it is.
    """
    payload = {
        "resolvedCleanupArgv": resolved_cleanup_argv,
        "sentinelPlantCommand": sentinel["plantCommand"],
        "sentinelProbeCommand": sentinel["probeCommand"],
        "sentinelConnectionEnvVar": sentinel["connectionEnvVar"],
        "connectionDetail": policy["datastore"]["connectionDetail"],
        "namespace": namespace,
        "foreignNamespaces": foreign_namespaces,
        "runCwd": run_cwd,
        "identityProvenance": identity_provenance,
        "identityStrength": identity_strength,
        "observedIdentity": observed_identity,
        "sourceIdentity": source_identity,
    }
    canonical = _canonical_json(_nfc_normalize(payload))
    return hmac.new(binding_key(policy), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def _git_env():
    """Environment for git subprocesses, built by rule rather than by denylist.

    Every inherited ``GIT_*`` variable is dropped — including ones this module has
    never heard of — and only process-owned values are added back.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    env["LC_ALL"] = "C"
    env["LANGUAGE"] = ""
    return env


def _parse_git_status_porcelain_z(data):
    """Parse ``git status --porcelain -z`` output into path records."""
    if isinstance(data, bytes):
        text = data.decode("utf-8", errors="surrogateescape")
    else:
        text = data
    records = []
    parts = text.split("\0")
    index = 0
    while index < len(parts):
        entry = parts[index]
        if not entry:
            index += 1
            continue
        status_xy = entry[:2]
        path = entry[3:] if len(entry) > 2 and entry[2] == " " else entry[2:]
        if status_xy[0] in ("R", "C") or status_xy[1] in ("R", "C"):
            index += 1
            original_path = parts[index] if index < len(parts) else ""
            records.append((status_xy, path, original_path))
        else:
            records.append((status_xy, path, None))
        index += 1
    return records


def _sha256_file_chunks(path, chunk_size=65536):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _worktree_path_record(cleanup_root, rel_path):
    abs_path = os.path.join(cleanup_root, rel_path)
    try:
        st = os.lstat(abs_path)
    except OSError:
        return [rel_path, "d", None]
    if stat.S_ISREG(st.st_mode):
        try:
            content_hash = _sha256_file_chunks(abs_path)
        except OSError:
            raise PilotCleanupError(REFUSAL_SOURCE_UNREADABLE)
        return [rel_path, "f", content_hash]
    return [rel_path, "o", None]


def _worktree_digest(cleanup_root, status_data):
    paths = set()
    for _status_xy, path, original_path in _parse_git_status_porcelain_z(status_data):
        if path:
            paths.add(path)
        if original_path:
            paths.add(original_path)
    canonical = []
    for path in sorted(paths):
        canonical.append(_worktree_path_record(cleanup_root, path))
    payload = _canonical_json(_nfc_normalize(canonical))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _argv_tail_digests(resolved_argv):
    digests = []
    for index, part in enumerate(resolved_argv[1:], start=1):
        try:
            st = os.lstat(part)
        except OSError:
            continue
        if not stat.S_ISREG(st.st_mode):
            continue
        try:
            content_hash = _sha256_file_chunks(part)
        except OSError:
            continue
        digests.append([index, content_hash])
    digests.sort(key=lambda item: item[0])
    return digests


def _populate_source_binding(source_id, resolved_argv):
    source_id["argv0Digest"] = argv0_content_digest(resolved_argv[0])
    source_id["argvDigests"] = _argv_tail_digests(resolved_argv)


def source_identity(cleanup_root):
    """Return source-state identity for the cleanup run: HEAD oid and worktree content digest.

    Hashing the declared argv does not catch a branch rewriting the script at the same path — HEAD
    catches a committed edit; a content digest of every dirty or untracked path catches an
    uncommitted one.
    """
    if not isinstance(cleanup_root, str) or not os.path.isdir(cleanup_root):
        raise PilotCleanupError(REFUSAL_SOURCE_ROOT_INVALID)

    git_env = _git_env()
    head = None
    try:
        result = subprocess.run(
            ["git", "-C", cleanup_root, "rev-parse", "HEAD"],
            capture_output=True,
            timeout=30,
            shell=False,
            env=git_env,
        )
        if result.returncode == 0:
            candidate = result.stdout.decode("utf-8", errors="replace").strip()
            if _HEAD_RE.match(candidate):
                head = candidate
    except (OSError, subprocess.TimeoutExpired):
        pass

    try:
        status_result = subprocess.run(
            ["git", "-C", cleanup_root, "status", "--porcelain", "-z"],
            capture_output=True,
            timeout=30,
            shell=False,
            env=git_env,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise PilotCleanupError(REFUSAL_SOURCE_UNREADABLE)
    if status_result.returncode != 0:
        raise PilotCleanupError(REFUSAL_SOURCE_UNREADABLE)

    worktree_digest = _worktree_digest(cleanup_root, status_result.stdout)
    return {
        "head": head,
        "worktreeDigest": worktree_digest,
        "argv0Digest": None,
        "argvDigests": [],
    }


def argv0_content_digest(argv0):
    """Return sha256 hex of a regular file at ``argv0``, or ``None`` when not a regular file."""
    if not isinstance(argv0, str):
        return None
    try:
        st = os.lstat(argv0)
    except OSError:
        return None
    if not stat.S_ISREG(st.st_mode):
        return None
    with open(argv0, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _command_digest(policy, declared_command):
    canonical = _canonical_json(_nfc_normalize(declared_command))
    return hmac.new(binding_key(policy), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def _sentinel_from_policy(policy):
    containment = policy.get("datastore", {}).get("containment")
    if not isinstance(containment, dict):
        raise PilotCleanupError(REFUSAL_SENTINEL_UNDECLARED)
    sentinel = containment.get("sentinel")
    if sentinel is None:
        raise PilotCleanupError(REFUSAL_SENTINEL_UNDECLARED)
    return sentinel


def _probe_all(sentinel, namespaces, sentinel_ids, *, connection_detail, reach_roots, run_cwd,
               timeout_seconds):
    observations = {}
    for namespace in namespaces:
        sentinel_id = sentinel_ids[namespace]
        result = probe_sentinel(
            sentinel,
            namespace,
            sentinel_id,
            connection_detail=connection_detail,
            reach_roots=reach_roots,
            run_cwd=run_cwd,
            timeout_seconds=timeout_seconds,
        )
        observations[namespace] = result["present"]
    return observations


def _build_receipt(
    *,
    result,
    reason,
    evidence,
    slot,
    slot_ref,
    namespace,
    foreign_namespaces,
    command_digest,
    config_digest,
    identity_provenance,
    identity_strength,
    observations,
    residual_sentinels,
    exercised_at,
):
    return {
        "kind": KIND_CLEANUP_CONTAINMENT,
        "result": result,
        "reason": reason,
        "evidence": evidence,
        "slot": slot,
        "slotRef": slot_ref,
        "namespace": namespace,
        "foreignNamespaces": foreign_namespaces,
        "commandDigest": command_digest,
        "configDigest": config_digest,
        "identityProvenance": identity_provenance,
        "identityStrength": identity_strength,
        "observations": observations,
        "residualSentinels": residual_sentinels,
        "assuranceLimits": list(ASSURANCE_LIMITS),
        "exercisedAt": exercised_at,
    }


def cleanup_effect_receipt(
    policy,
    pilot_block,
    slot_ref,
    *,
    reach_roots,
    run_cwd,
    cleanup_root,
    journal_path,
    now,
    observed_identity,
    identity_provenance,
    identity_strength,
    sentinel_factory=None,
    timeout_seconds=20,
):
    """Run the cleanup containment exercise and return a pass/fail receipt.

    The cleanup command must be independently resolvable — an absolute path — because it runs
    with a minimal environment and no shell; a relative argv0 would fail to spawn opaquely deep
    inside the runner.

    Residual foreign sentinels are recorded and disclosed rather than silently removed: the
    framework has no remove command, and running the project cleanup against a sibling namespace
    to tidy up would be the exact destruction this exercise exists to prevent.
    """
    if sentinel_factory is None:
        sentinel_factory = mint_sentinel_id

    sentinel = _sentinel_from_policy(policy)
    slot, _generation = pilot_slot.parse_slot_ref(slot_ref)
    namespace = namespace_for_slot(slot)
    foreigns = foreign_namespaces(policy, slot)

    declared_command = pilot_block["cleanup"]["command"]
    command_digest = _command_digest(policy, declared_command)

    observations = {"preplant": {}, "postplant": {}, "postcleanup": {}}
    residual_sentinels = [{"namespace": foreign} for foreign in foreigns]

    if not foreigns:
        return _build_receipt(
            result=RESULT_FAIL,
            reason=REASON_NO_FOREIGN_NAMESPACE,
            evidence="no foreign namespaces to contain against",
            slot=slot,
            slot_ref=slot_ref,
            namespace=namespace,
            foreign_namespaces=foreigns,
            command_digest=command_digest,
            config_digest="",
            identity_provenance=identity_provenance,
            identity_strength=identity_strength,
            observations=observations,
            residual_sentinels=[],
            exercised_at=now,
        )

    resolved_argv = resolve_cleanup_command(declared_command, namespace)
    if not os.path.isabs(resolved_argv[0]):
        raise PilotCleanupError(REFUSAL_CLEANUP_ARGV0_NOT_ABSOLUTE)

    source_id = source_identity(cleanup_root)
    _populate_source_binding(source_id, resolved_argv)
    config_digest_value = config_digest(
        policy,
        resolved_cleanup_argv=resolved_argv,
        sentinel=sentinel,
        namespace=namespace,
        foreign_namespaces=foreigns,
        run_cwd=run_cwd,
        identity_provenance=identity_provenance,
        identity_strength=identity_strength,
        observed_identity=observed_identity,
        source_identity=source_id,
    )

    all_namespaces = [namespace] + foreigns
    sentinel_ids = {ns: sentinel_factory() for ns in all_namespaces}
    connection_detail = policy["datastore"]["connectionDetail"]
    env_var = sentinel["connectionEnvVar"]

    observations["preplant"] = _probe_all(
        sentinel,
        all_namespaces,
        sentinel_ids,
        connection_detail=connection_detail,
        reach_roots=reach_roots,
        run_cwd=run_cwd,
        timeout_seconds=timeout_seconds,
    )
    if any(observations["preplant"].values()):
        receipt = _build_receipt(
            result=RESULT_FAIL,
            reason=REASON_RECEIPT_VACUOUS,
            evidence="sentinel already present before plant",
            slot=slot,
            slot_ref=slot_ref,
            namespace=namespace,
            foreign_namespaces=foreigns,
            command_digest=command_digest,
            config_digest=config_digest_value,
            identity_provenance=identity_provenance,
            identity_strength=identity_strength,
            observations=observations,
            residual_sentinels=residual_sentinels,
            exercised_at=now,
        )
        pilot_policy.assert_results_only(receipt, pilot_policy.policy_material(policy))
        return receipt

    with pilot_journal.effect(
        journal_path,
        slot_ref=slot_ref,
        kind=pilot_journal.KIND_NAMESPACE_TOUCHED,
        at=now,
        detail={"namespaces": list(all_namespaces)},
    ) as handle:
        for ns in all_namespaces:
            plant_sentinel(
                sentinel,
                ns,
                sentinel_ids[ns],
                connection_detail=connection_detail,
                reach_roots=reach_roots,
                run_cwd=run_cwd,
                timeout_seconds=timeout_seconds,
            )
        handle.mark_applied(at=now)

    observations["postplant"] = _probe_all(
        sentinel,
        all_namespaces,
        sentinel_ids,
        connection_detail=connection_detail,
        reach_roots=reach_roots,
        run_cwd=run_cwd,
        timeout_seconds=timeout_seconds,
    )
    if not all(observations["postplant"].values()):
        receipt = _build_receipt(
            result=RESULT_FAIL,
            reason=REASON_RECEIPT_VACUOUS,
            evidence="sentinel absent after plant",
            slot=slot,
            slot_ref=slot_ref,
            namespace=namespace,
            foreign_namespaces=foreigns,
            command_digest=command_digest,
            config_digest=config_digest_value,
            identity_provenance=identity_provenance,
            identity_strength=identity_strength,
            observations=observations,
            residual_sentinels=residual_sentinels,
            exercised_at=now,
        )
        pilot_policy.assert_results_only(receipt, pilot_policy.policy_material(policy))
        return receipt

    with pilot_journal.effect(
        journal_path,
        slot_ref=slot_ref,
        kind=pilot_journal.KIND_NAMESPACE_TOUCHED,
        at=now,
        detail={"namespace": namespace},
    ) as handle:
        cleanup_result = run_bounded(
            resolved_argv,
            cwd=run_cwd,
            env={env_var: connection_detail},
            timeout_seconds=timeout_seconds,
        )
        handle.mark_applied(at=now)

    if cleanup_result["timedOut"] or cleanup_result["exit"] != 0:
        receipt = _build_receipt(
            result=RESULT_FAIL,
            reason=REASON_CLEANUP_COMMAND_FAILED,
            evidence="cleanup command exited nonzero or timed out",
            slot=slot,
            slot_ref=slot_ref,
            namespace=namespace,
            foreign_namespaces=foreigns,
            command_digest=command_digest,
            config_digest=config_digest_value,
            identity_provenance=identity_provenance,
            identity_strength=identity_strength,
            observations=observations,
            residual_sentinels=residual_sentinels,
            exercised_at=now,
        )
        pilot_policy.assert_results_only(receipt, pilot_policy.policy_material(policy))
        return receipt

    observations["postcleanup"] = _probe_all(
        sentinel,
        all_namespaces,
        sentinel_ids,
        connection_detail=connection_detail,
        reach_roots=reach_roots,
        run_cwd=run_cwd,
        timeout_seconds=timeout_seconds,
    )

    if observations["postcleanup"].get(namespace):
        receipt = _build_receipt(
            result=RESULT_FAIL,
            reason=REASON_OWN_SENTINEL_SURVIVED,
            evidence="own sentinel survived cleanup",
            slot=slot,
            slot_ref=slot_ref,
            namespace=namespace,
            foreign_namespaces=foreigns,
            command_digest=command_digest,
            config_digest=config_digest_value,
            identity_provenance=identity_provenance,
            identity_strength=identity_strength,
            observations=observations,
            residual_sentinels=residual_sentinels,
            exercised_at=now,
        )
        pilot_policy.assert_results_only(receipt, pilot_policy.policy_material(policy))
        return receipt

    for foreign in foreigns:
        if not observations["postcleanup"].get(foreign):
            receipt = _build_receipt(
                result=RESULT_FAIL,
                reason=REASON_FOREIGN_SENTINEL_DESTROYED,
                evidence="foreign sentinel destroyed by cleanup",
                slot=slot,
                slot_ref=slot_ref,
                namespace=namespace,
                foreign_namespaces=foreigns,
                command_digest=command_digest,
                config_digest=config_digest_value,
                identity_provenance=identity_provenance,
                identity_strength=identity_strength,
                observations=observations,
                residual_sentinels=residual_sentinels,
                exercised_at=now,
            )
            pilot_policy.assert_results_only(receipt, pilot_policy.policy_material(policy))
            return receipt

    receipt = _build_receipt(
        result=RESULT_PASS,
        reason=None,
        evidence="cleanup removed own sentinel and preserved all foreign sentinels",
        slot=slot,
        slot_ref=slot_ref,
        namespace=namespace,
        foreign_namespaces=foreigns,
        command_digest=command_digest,
        config_digest=config_digest_value,
        identity_provenance=identity_provenance,
        identity_strength=identity_strength,
        observations=observations,
        residual_sentinels=residual_sentinels,
        exercised_at=now,
    )
    pilot_policy.assert_results_only(receipt, pilot_policy.policy_material(policy))
    return receipt


def _receipt_schema_valid(receipt):
    if not isinstance(receipt, dict):
        return False
    if set(receipt.keys()) != _RECEIPT_SCHEMA_KEYS:
        return False
    if receipt.get("kind") != KIND_CLEANUP_CONTAINMENT:
        return False
    return True


def receipt_valid_for(
    receipt,
    policy,
    pilot_block,
    slot_ref,
    *,
    cleanup_root,
    run_cwd,
    observed_identity,
    identity_provenance,
    identity_strength,
):
    """Return whether a receipt is fresh for the current policy, block, and source tree.

    The config recomputation calls ``source_identity(cleanup_root)`` fresh — a cleanup script
    edited since the receipt was taken changes ``head`` or ``worktreeDigest``, the config digest
    moves, and the receipt is stale.
    """
    if not _receipt_schema_valid(receipt):
        return {"ok": False, "reason": REASON_RECEIPT_SCHEMA_INVALID}

    if receipt["slotRef"] != slot_ref:
        return {"ok": False, "reason": REASON_RECEIPT_SLOT_MISMATCH}

    if receipt["result"] != RESULT_PASS:
        return {"ok": False, "reason": REASON_RECEIPT_NOT_PASS}

    declared_command = pilot_block["cleanup"]["command"]
    expected_command_digest = _command_digest(policy, declared_command)
    if not hmac.compare_digest(receipt["commandDigest"], expected_command_digest):
        return {"ok": False, "reason": REASON_RECEIPT_STALE_COMMAND}

    slot, _generation = pilot_slot.parse_slot_ref(slot_ref)
    namespace = namespace_for_slot(slot)
    foreigns = foreign_namespaces(policy, slot)
    sentinel = _sentinel_from_policy(policy)
    resolved_argv = resolve_cleanup_command(declared_command, namespace)
    source_id = source_identity(cleanup_root)
    _populate_source_binding(source_id, resolved_argv)
    expected_config_digest = config_digest(
        policy,
        resolved_cleanup_argv=resolved_argv,
        sentinel=sentinel,
        namespace=namespace,
        foreign_namespaces=foreigns,
        run_cwd=run_cwd,
        identity_provenance=identity_provenance,
        identity_strength=identity_strength,
        observed_identity=observed_identity,
        source_identity=source_id,
    )
    if not hmac.compare_digest(receipt["configDigest"], expected_config_digest):
        return {"ok": False, "reason": REASON_RECEIPT_STALE_CONFIG}

    return {"ok": True, "reason": None}


def registry_record(receipt, declaration, *, evidence=None):
    """Build a declare-and-exercise record for A1's gate from a passing receipt."""
    if not _receipt_schema_valid(receipt):
        raise PilotCleanupError(REASON_RECEIPT_SCHEMA_INVALID)
    if receipt["result"] != RESULT_PASS:
        raise PilotCleanupError(REASON_RECEIPT_NOT_PASS)
    return {
        "kind": KIND_CLEANUP_CONTAINMENT,
        "declarationDigest": pilot_contract.declaration_digest(declaration),
        "exercisedAt": receipt["exercisedAt"],
        "receipt": {
            "result": RESULT_PASS,
            "evidence": evidence if evidence is not None else receipt["evidence"],
        },
    }


def resolve_containment(
    policy,
    pilot_block,
    slot_ref,
    *,
    receipt=None,
    cleanup_root=None,
    run_cwd=None,
    observed_identity=None,
    identity_provenance=None,
    identity_strength=None,
):
    """Resolve how cleanup containment is assured for a slot."""
    containment = policy.get("datastore", {}).get("containment")
    permissions = None
    if isinstance(containment, dict):
        permissions = containment.get("permissions")

    if (
        isinstance(permissions, dict)
        and permissions.get("cannotReachForeignNamespaces") is True
        and isinstance(permissions.get("evidence"), str)
        and permissions["evidence"]
    ):
        # Permissions outrank a receipt: they remove the need to prove behaviour, and a receipt
        # cannot bind hostile code (see ASSURANCE_LIMITS).
        return {"mode": MODE_PERMISSIONS, "reason": None, "remedy": None}

    slot, _generation = pilot_slot.parse_slot_ref(slot_ref)
    if foreign_namespaces(policy, slot) == []:
        return {"mode": MODE_SINGLE_SLOT, "reason": None, "remedy": None}

    if receipt is not None:
        if cleanup_root is None or run_cwd is None or observed_identity is None:
            return {
                "mode": MODE_REFUSED,
                "reason": REASON_RECEIPT_SCHEMA_INVALID,
                "remedy": None,
            }
        validation = receipt_valid_for(
            receipt,
            policy,
            pilot_block,
            slot_ref,
            cleanup_root=cleanup_root,
            run_cwd=run_cwd,
            observed_identity=observed_identity,
            identity_provenance=identity_provenance,
            identity_strength=identity_strength,
        )
        if validation["ok"]:
            return {"mode": MODE_RECEIPT, "reason": None, "remedy": None}
        return {
            "mode": MODE_REFUSED,
            "reason": validation["reason"],
            "remedy": None,
        }

    return {
        "mode": MODE_REFUSED,
        "reason": REASON_CONTAINMENT_UNDECLARED,
        "remedy": "isolated datastores, or one slot",
    }


def _guarded_plan_view(plan):
    """Return the plan with the authorized reseed descriptor replaced by a placeholder.

    ``assert_results_only`` is A3's guard on a traveling RESULT — it must not carry policy
    material. A reseed step is not a result: it is an authorized credential descriptor built
    through ``pilot_provision``'s chokepoint, and it names the account it seeds by construction
    (``pilot_provision`` runs no such guard on its own return, for the same reason). So the guard
    applies to every other surface of the plan — the action, the cleanup argv, the namespaces, the
    journal references, the C7 notes — where an identity or connection detail appearing WOULD be a
    leak.
    """
    view = copy.deepcopy(plan)
    steps = view.get("steps")
    if not isinstance(steps, list):
        return view
    for step in steps:
        if isinstance(step, dict) and step.get("op") == "reseed" and "request" in step:
            step["request"] = "<authorized-reseed-request>"
    return view


def resurrection_plan(
    policy,
    pilot_block,
    slot_ref,
    *,
    registry,
    journal_path,
    verdict=None,
    account=None,
    artifact=None,
    mint_envelope=None,
    now=None,
    receipt=None,
    cleanup_root=None,
    run_cwd=None,
    observed_identity=None,
    identity_provenance=None,
    identity_strength=None,
):
    """Return a park, refusal, or ordered resurrection plan without executing anything.

    The generation bump is C7's seam, and B6's mint client does not exist — this function plans
    only.
    """
    pilot_contract.validate_pilot_block(pilot_block)

    try:
        pilot_contract.require_exercised(
            registry,
            "effects-escape",
            pilot_block["effectsEscape"],
        )
    except pilot_contract.PilotContractError:
        return {"action": ACTION_REFUSE, "reason": REASON_EFFECTS_ESCAPE_UNEXERCISED}

    if pilot_block["effectsEscape"]["canEscape"] is True:
        return {
            "action": ACTION_PARK,
            "reason": REASON_EFFECTS_ESCAPE_PARK,
            "owner": (
                "A crashed slot whose actions can escape the datastore parks for owner "
                "inspection: reseeding cannot un-send mail or un-fire a webhook, and replay "
                "would duplicate it."
            ),
            "steps": [],
        }

    containment = resolve_containment(
        policy,
        pilot_block,
        slot_ref,
        receipt=receipt,
        cleanup_root=cleanup_root,
        run_cwd=run_cwd,
        observed_identity=observed_identity,
        identity_provenance=identity_provenance,
        identity_strength=identity_strength,
    )
    mode = containment.get("mode")
    if mode not in _CONTAINMENT_RESOLVED_MODES:
        return {
            "action": ACTION_REFUSE,
            "reason": REASON_CONTAINMENT_UNRESOLVED,
            "containment": containment,
        }

    if mode == MODE_RECEIPT:
        try:
            pilot_contract.require_exercised(
                registry,
                "cleanup-containment",
                pilot_block["cleanup"],
            )
        except pilot_contract.PilotContractError:
            return {
                "action": ACTION_REFUSE,
                "reason": REASON_CONTAINMENT_UNEXERCISED,
                "containment": containment,
            }

    if verdict is None:
        return {
            "action": ACTION_REFUSE,
            "reason": REASON_VERDICT_MISSING,
            "containment": containment,
        }

    slot, _generation = pilot_slot.parse_slot_ref(slot_ref)
    namespace = namespace_for_slot(slot)
    declared_command = pilot_block["cleanup"]["command"]
    resolved_argv = resolve_cleanup_command(declared_command, namespace)

    sign_in_path = pilot_block["signInPath"]
    if sign_in_path == "captured":
        reseed_request = pilot_provision.authorized_seed_request(
            verdict,
            policy,
            slot_ref,
            account,
            artifact,
        )
        reseed_path = "captured"
    else:
        reseed_request = pilot_provision.authorized_mint_request(
            verdict,
            policy,
            slot_ref,
            account,
            mint_envelope,
        )
        reseed_path = "minted"

    plan = {
        "action": ACTION_RESURRECT,
        "reason": None,
        "slotRef": slot_ref,
        "containment": containment,
        "steps": [
            {
                "op": "cleanup",
                "argv": resolved_argv,
                "namespace": namespace,
                "journal": {
                    "kind": pilot_journal.KIND_NAMESPACE_TOUCHED,
                    "slotRef": slot_ref,
                },
            },
            {
                "op": "reseed",
                "request": reseed_request,
                "path": reseed_path,
            },
            {
                "op": "begin-generation",
                "responsibleParty": "C7",
                "requires": "released",
                "note": "the generation bump is enforced at the broker; this plan does not perform it",
            },
            {
                "op": "resume",
                "responsibleParty": "C7",
            },
        ],
    }
    # Narrow guard: see _guarded_plan_view docstring — reseed request is an authorized descriptor.
    pilot_policy.assert_results_only(
        _guarded_plan_view(plan),
        pilot_policy.policy_material(policy),
    )
    return plan


def _terminate_and_wait(proc):
    if proc.poll() is not None:
        return
    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGTERM)
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            os.killpg(pgid, signal.SIGKILL)
            proc.wait()
    except ProcessLookupError:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


def _nfc_normalize(value):
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, dict):
        return {_nfc_normalize(k): _nfc_normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_nfc_normalize(item) for item in value]
    return value


def _canonical_json(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
