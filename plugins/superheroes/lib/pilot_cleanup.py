"""Cleanup-command resolution, sentinel instrumentation, and receipt binding primitives (C9).

Non-goals: receipt assembly, containment resolution, and resurrection planning land in a later
order.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import stat
import subprocess
import threading
import unicodedata

import pilot_boundary
import pilot_policy
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

NAMESPACE_PLACEHOLDER = "{namespace}"
SENTINEL_PLACEHOLDER = "{sentinel}"

_PLACEHOLDER_RE = re.compile(r"\{[^{}]*\}")
_SENTINEL_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_HEAD_RE = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")

_SENTINEL_KEYS = frozenset({"plantCommand", "probeCommand", "connectionEnvVar"})


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
        )
    except OSError:
        raise PilotCleanupError(REFUSAL_PROBE_INDETERMINATE)

    timed_out = False
    stdout_bytes = 0
    try:
        stdout_holder = []

        def _read_stdout():
            try:
                stdout_holder.append(proc.stdout.read(max_output_bytes + 1))
            except Exception:
                stdout_holder.append(b"")

        reader = threading.Thread(target=_read_stdout, daemon=True)
        reader.start()
        reader.join(timeout=timeout_seconds)

        if reader.is_alive():
            _terminate_and_wait(proc)
            timed_out = True
        else:
            raw = stdout_holder[0] if stdout_holder else b""
            stdout_bytes = len(raw)
            try:
                proc.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                _terminate_and_wait(proc)
                timed_out = True

        exit_code = None if timed_out else proc.returncode
        return {"exit": exit_code, "timedOut": timed_out, "stdoutBytes": stdout_bytes}
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


def source_identity(cleanup_root):
    """Return source-state identity for the cleanup run: HEAD oid and porcelain status digest.

    Hashing the declared argv does not catch a branch rewriting the script at the same path — HEAD
    catches a committed edit; porcelain status catches an uncommitted one.
    """
    if not isinstance(cleanup_root, str) or not os.path.isdir(cleanup_root):
        raise PilotCleanupError(REFUSAL_SOURCE_ROOT_INVALID)

    head = None
    try:
        result = subprocess.run(
            ["git", "-C", cleanup_root, "rev-parse", "HEAD"],
            capture_output=True,
            timeout=30,
            shell=False,
        )
        if result.returncode == 0:
            candidate = result.stdout.decode("utf-8", errors="replace").strip()
            if _HEAD_RE.match(candidate):
                head = candidate
    except (OSError, subprocess.TimeoutExpired):
        pass

    try:
        status_result = subprocess.run(
            ["git", "-C", cleanup_root, "status", "--porcelain"],
            capture_output=True,
            timeout=30,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise PilotCleanupError(REFUSAL_SOURCE_UNREADABLE)
    if status_result.returncode != 0:
        raise PilotCleanupError(REFUSAL_SOURCE_UNREADABLE)

    status_digest = hashlib.sha256(status_result.stdout).hexdigest()
    return {"head": head, "statusDigest": status_digest, "argv0Digest": None}


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


def _terminate_and_wait(proc):
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
