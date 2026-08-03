"""Pilot target boundary — exact-origin bindings, protected-target refusal, and verdicts (A3)."""
import os
import stat
import subprocess
import threading
import time

import pilot_policy
import pilot_slot

BOUNDARY_SCHEMA_VERSION = 1

REFUSAL_ORIGIN_INVALID = "boundary-origin-invalid"
REFUSAL_SLOT_REF_INVALID = "boundary-slot-ref-invalid"
REFUSAL_REDIRECTS_INVALID = "boundary-redirects-invalid"
REFUSAL_PROTECTED_TARGETS_INVALID = "boundary-protected-targets-invalid"
REFUSAL_TARGET_OFF_ALLOWLIST = "boundary-target-off-allowlist"
REFUSAL_REDIRECT_OFF_ALLOWLIST = "boundary-redirect-off-allowlist"
REFUSAL_PROTECTED_TARGET = "boundary-protected-target-refused"
REFUSAL_DATASTORE_IDENTITY_MISMATCH = "boundary-datastore-identity-mismatch"
REFUSAL_DATASTORE_IDENTITY_UNAVAILABLE = "boundary-datastore-identity-unavailable"
REFUSAL_DATASTORE_OBSERVER_INVALID = "boundary-datastore-observer-invalid"
REFUSAL_DATASTORE_OBSERVER_FAILED = "boundary-datastore-observer-failed"
REFUSAL_UNVERIFIED = "boundary-unverified"
REFUSAL_VERDICT_VACUOUS = "boundary-verdict-vacuous"

_MANDATORY_VERDICT_CHECKS = frozenset({"target-binding", "datastore-identity"})


class PilotBoundaryError(Exception):
    def __init__(self, reason, detail=None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def parse_origin(value):
    """Return canonical ``<scheme>://<host>:<port>`` or raise."""
    # bite-axis: origin canonicalization — only http(s) origins with valid host and port are
    # accepted; any malformed or non-canonical input raises REFUSAL_ORIGIN_INVALID.
    canonical = _parse_origin_or_none(value)
    if canonical is None:
        raise PilotBoundaryError(REFUSAL_ORIGIN_INVALID)
    return canonical


def target_binding(slot_ref, *, origin, permitted_redirects, protected_targets):
    """Build a validated target binding dict."""
    # bite-axis: binding integrity — invalid slot ref, origin, redirects list, or protected
    # targets refuse before a binding dict is returned.
    try:
        slot, generation = pilot_slot.parse_slot_ref(slot_ref)
        canonical_slot_ref = pilot_slot.format_slot_ref(slot, generation)
    except pilot_slot.PilotSlotError:
        raise PilotBoundaryError(REFUSAL_SLOT_REF_INVALID)

    canonical_origin = parse_origin(origin)

    if not isinstance(permitted_redirects, list):
        raise PilotBoundaryError(REFUSAL_REDIRECTS_INVALID)
    seen_redirects = set()
    canonical_redirects = []
    for redirect in permitted_redirects:
        try:
            parsed = parse_origin(redirect)
        except PilotBoundaryError:
            raise PilotBoundaryError(REFUSAL_REDIRECTS_INVALID)
        if parsed not in seen_redirects:
            seen_redirects.add(parsed)
            canonical_redirects.append(parsed)

    if not isinstance(protected_targets, list) or not protected_targets:
        raise PilotBoundaryError(REFUSAL_PROTECTED_TARGETS_INVALID)
    canonical_protected = []
    for target in protected_targets:
        if not isinstance(target, str) or not target:
            raise PilotBoundaryError(REFUSAL_PROTECTED_TARGETS_INVALID)
        if "://" in target:
            parsed = _parse_origin_or_none(target)
            if parsed is None:
                raise PilotBoundaryError(REFUSAL_PROTECTED_TARGETS_INVALID)
            canonical_protected.append(parsed)
        else:
            canonical_protected.append(target)

    return {
        "slotRef": canonical_slot_ref,
        "origin": canonical_origin,
        "permittedRedirects": canonical_redirects,
        "protectedTargets": canonical_protected,
    }


def check_target(binding, url):
    """Check whether ``url`` is an allowed target; never raises on malformed input."""
    # bite-axis: precedence — protected targets are refused before the allowlist check and there
    # is no bypass parameter, deliberately unlike engine.gate_violations which --allow-protected
    # can bypass.
    parsed = _parse_origin_or_none(url)
    if parsed is None:
        return {"ok": False, "reason": REFUSAL_ORIGIN_INVALID}
    if parsed in binding["protectedTargets"]:
        return {"ok": False, "reason": REFUSAL_PROTECTED_TARGET}
    if parsed != binding["origin"]:
        return {"ok": False, "reason": REFUSAL_TARGET_OFF_ALLOWLIST}
    return {"ok": True, "reason": None}


def check_redirect(binding, url):
    """Check whether ``url`` is an allowed redirect destination; never raises."""
    # bite-axis: precedence — protected targets are refused before the redirect allowlist check
    # and there is no bypass parameter, deliberately unlike engine.gate_violations which
    # --allow-protected can bypass.
    parsed = _parse_origin_or_none(url)
    if parsed is None:
        return {"ok": False, "reason": REFUSAL_ORIGIN_INVALID}
    if parsed in binding["protectedTargets"]:
        return {"ok": False, "reason": REFUSAL_PROTECTED_TARGET}
    if parsed == binding["origin"] or parsed in binding["permittedRedirects"]:
        return {"ok": True, "reason": None}
    return {"ok": False, "reason": REFUSAL_REDIRECT_OFF_ALLOWLIST}


def check_protected_identity(binding, identity):
    """Refuse when ``identity`` names a protected target or is unavailable."""
    # bite-axis: protected identity refusal — an identity naming a protected target or an
    # unavailable identity is refused before any binding proceeds.
    if identity in binding["protectedTargets"]:
        return {"ok": False, "reason": REFUSAL_PROTECTED_TARGET}
    if not isinstance(identity, str) or not identity:
        return {"ok": False, "reason": REFUSAL_DATASTORE_IDENTITY_UNAVAILABLE}
    return {"ok": True, "reason": None}


def observe_datastore_identity(
    observer,
    *,
    connection_detail,
    reach_roots,
    run_cwd,
    timeout_seconds=20,
    max_output_bytes=4096,
):
    """Run the policy observer and return a strong observed identity."""
    # bite-axis: observer execution — subprocess failure, oversized output, or non-single-line
    # UTF-8 stdout raises REFUSAL_DATASTORE_OBSERVER_FAILED; only a clean one-line identity is
    # returned.
    _validate_observer(observer, connection_detail, reach_roots, run_cwd)
    env_var = observer["connectionEnvVar"]
    command = observer["command"]
    try:
        stdout = _run_bounded_observer(
            command,
            run_cwd=run_cwd,
            env={env_var: connection_detail},
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
        )
    except PilotBoundaryError:
        raise
    except (OSError, subprocess.TimeoutExpired):
        raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_FAILED)

    try:
        text = stdout.decode("utf-8")
    except UnicodeDecodeError:
        raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_FAILED)
    stripped = text.strip()
    if not stripped or "\n" in stripped or any(ord(ch) < 32 or ord(ch) == 127 for ch in stripped):
        raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_FAILED)

    return {
        "identity": stripped,
        "provenance": "observed",
        "strength": "strong",
        "weaker": False,
    }


def app_reported_identity(value):
    """Record a weaker app-reported identity when no observer is declared."""
    # bite-axis: identity availability — empty or non-string app-reported identity raises
    # REFUSAL_DATASTORE_IDENTITY_UNAVAILABLE; only a non-empty string yields a weaker record.
    if not isinstance(value, str) or not value:
        raise PilotBoundaryError(REFUSAL_DATASTORE_IDENTITY_UNAVAILABLE)
    return {
        "identity": value,
        "provenance": "app-reported",
        "strength": "weaker",
        "weaker": True,
    }


def check_datastore_identity(binding, observation, expected_identity):
    """Compare observed identity against policy expectation."""
    # bite-axis: identity match — protected, unavailable, or mismatched observed identity refuses
    # before a passing datastore-identity check is recorded.
    protected = check_protected_identity(binding, observation["identity"])
    if not protected["ok"]:
        return {
            "ok": False,
            "reason": protected["reason"],
            "provenance": observation["provenance"],
            "strength": observation["strength"],
            "match": False,
        }
    if not isinstance(expected_identity, str) or not expected_identity:
        return {
            "ok": False,
            "reason": REFUSAL_DATASTORE_IDENTITY_UNAVAILABLE,
            "provenance": observation["provenance"],
            "strength": observation["strength"],
            "match": False,
        }
    if observation["identity"] != expected_identity:
        return {
            "ok": False,
            "reason": REFUSAL_DATASTORE_IDENTITY_MISMATCH,
            "provenance": observation["provenance"],
            "strength": observation["strength"],
            "match": False,
        }
    return {
        "ok": True,
        "reason": None,
        "provenance": observation["provenance"],
        "strength": observation["strength"],
        "match": True,
    }


def boundary_verdict(
    binding,
    *,
    checks,
    policy_digest,
    datastore_identity=None,
    verified_at=None,
):
    """Assemble a traveling verdict with outcomes only — no policy material."""
    # bite-axis: verdict vacuity — a verdict with no checks or missing mandatory check names
    # refuses before assembly; a zero-check verdict must not authorize credentials.
    _refuse_if_verdict_checks_vacuous(checks)
    # bite-axis: verdict assembly — traveling verdict carries check outcomes only (no policy
    # material); any failing check makes result refuse with that check's reason.
    check_entries = []
    first_failure_reason = None
    for name, result in checks:
        entry = {
            "check": name,
            "result": "pass" if result["ok"] else "refuse",
            "reason": result["reason"],
        }
        check_entries.append(entry)
        if not result["ok"] and first_failure_reason is None:
            first_failure_reason = result["reason"]

    verdict = {
        "schemaVersion": BOUNDARY_SCHEMA_VERSION,
        "slotRef": binding["slotRef"],
        "result": "pass" if first_failure_reason is None else "refuse",
        "reason": first_failure_reason,
        "checks": check_entries,
        "datastoreIdentity": None,
        "policyDigest": policy_digest,
        "verifiedAt": verified_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if datastore_identity is not None:
        verdict["datastoreIdentity"] = {
            "provenance": datastore_identity["provenance"],
            "strength": datastore_identity["strength"],
            "match": datastore_identity["match"],
        }
    return verdict


def authorize_credentials(verdict, slot_ref, policy_digest):
    """Authorize credential minting only for a verified passing verdict."""
    # bite-axis: authority — a verdict that did not pass, or is bound to a different slot or
    # policy digest, yields no authorization; neutralizing any one of those conditions reddens
    # credential gates.
    if not isinstance(verdict, dict):
        raise PilotBoundaryError(REFUSAL_UNVERIFIED)
    schema_version = verdict.get("schemaVersion")
    if type(schema_version) is not int or schema_version != BOUNDARY_SCHEMA_VERSION:
        raise PilotBoundaryError(REFUSAL_UNVERIFIED)
    if verdict.get("result") != "pass":
        raise PilotBoundaryError(REFUSAL_UNVERIFIED)

    try:
        slot, generation = pilot_slot.parse_slot_ref(slot_ref)
        canonical_slot_ref = pilot_slot.format_slot_ref(slot, generation)
    except pilot_slot.PilotSlotError:
        raise PilotBoundaryError(REFUSAL_UNVERIFIED)

    if verdict.get("slotRef") != canonical_slot_ref:
        raise PilotBoundaryError(REFUSAL_UNVERIFIED)
    if (
        not isinstance(policy_digest, str)
        or not policy_digest
        or verdict.get("policyDigest") != policy_digest
    ):
        raise PilotBoundaryError(REFUSAL_UNVERIFIED)

    _refuse_if_authorized_checks_invalid(verdict.get("checks"))

    return {
        "slotRef": canonical_slot_ref,
        "policyDigest": policy_digest,
        "authorized": True,
    }


def _parse_origin_or_none(value):
    if not isinstance(value, str):
        return None
    sep_index = value.find("://")
    if sep_index < 1:
        return None
    scheme = value[:sep_index]
    if scheme.lower() not in ("http", "https"):
        return None
    rest = value[sep_index + 3:]
    if not rest or "/" in rest or "?" in rest or "#" in rest:
        return None
    if "@" in rest:
        return None

    if rest.startswith("["):
        close = rest.find("]")
        if close < 2 or close == len(rest) - 1:
            return None
        host = rest[:close + 1]
        if rest[close + 1:] != "" and not rest[close + 1:].startswith(":"):
            return None
        port_part = rest[close + 2:] if rest[close + 1:] else None
        if port_part is None:
            return None
    else:
        colon = rest.rfind(":")
        if colon < 1:
            return None
        host = rest[:colon]
        port_part = rest[colon + 1:]
        if ":" in host:
            return None

    if not host or "*" in host or any(ch.isspace() for ch in host):
        return None
    if host.startswith("[") and not host.endswith("]"):
        return None
    if not host.startswith("[") and "/" in host:
        return None

    if not port_part or not port_part.isascii() or not port_part.isdigit():
        return None
    if len(port_part) > 1 and port_part[0] == "0":
        return None
    port = int(port_part)
    if port < 1 or port > 65535:
        return None

    return "%s://%s:%d" % (scheme.lower(), host.lower(), port)


def _path_components(path):
    parts = os.path.realpath(path).split(os.sep)
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def _is_inside(path, root):
    path_parts = _path_components(path)
    root_parts = _path_components(root)
    if len(path_parts) < len(root_parts):
        return False
    return path_parts[:len(root_parts)] == root_parts


def _is_outside_all_reach_roots(path, reach_roots):
    real = os.path.realpath(path)
    for root in reach_roots:
        if _is_inside(real, root):
            return False
    return True


def is_outside_all_reach_roots(path, reach_roots):
    """Public: True when ``path`` resolves outside every reach root."""
    return _is_outside_all_reach_roots(path, reach_roots)


def _validate_observer(observer, connection_detail, reach_roots, run_cwd):
    # bite-axis: observer confinement — observer executable, run cwd, and reachable command
    # paths must lie outside all reach roots; violation raises REFUSAL_DATASTORE_OBSERVER_INVALID.
    if not isinstance(observer, dict) or set(observer.keys()) != pilot_policy.OBSERVER_KEYS:
        raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)

    command = observer["command"]
    if not isinstance(command, list) or not command:
        raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)
    for part in command:
        if not isinstance(part, str) or not part:
            raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)

    env_var = observer["connectionEnvVar"]
    if not isinstance(env_var, str) or not pilot_policy.ENV_VAR_RE.match(env_var):
        raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)

    if not isinstance(connection_detail, str) or not connection_detail:
        raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)

    if not isinstance(reach_roots, list) or not reach_roots:
        # bite-axis: reach-root vacuity — empty reach_roots makes confinement checks vacuous;
        # refuse before any observer path is accepted.
        raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)
    for root in reach_roots:
        if not isinstance(root, str) or not os.path.isabs(root):
            raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)

    if not isinstance(run_cwd, str) or not os.path.isdir(run_cwd):
        raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)

    executable = command[0]
    if not os.path.isabs(executable):
        raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)
    try:
        st = os.stat(executable)
    except OSError:
        raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)
    if not stat.S_ISREG(st.st_mode):
        raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)
    if st.st_uid != os.getuid():
        raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)
    if st.st_mode & 0o022:
        raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)
    if not _is_outside_all_reach_roots(executable, reach_roots):
        raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)

    if not _is_outside_all_reach_roots(run_cwd, reach_roots):
        raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)

    for part in command[1:]:
        candidate = part if os.path.isabs(part) else os.path.join(run_cwd, part)
        # bite-axis: argv confinement — resolved paths inside reach roots refuse whether or not
        # the path exists at validation time.
        resolved = os.path.realpath(candidate)
        if not _is_outside_all_reach_roots(resolved, reach_roots):
            raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_INVALID)


def _refuse_if_verdict_checks_vacuous(checks):
    if not isinstance(checks, list) or not checks:
        raise PilotBoundaryError(REFUSAL_VERDICT_VACUOUS)
    names = set()
    for item in checks:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise PilotBoundaryError(REFUSAL_VERDICT_VACUOUS)
        name, _result = item
        if not isinstance(name, str):
            raise PilotBoundaryError(REFUSAL_VERDICT_VACUOUS)
        names.add(name)
    if _MANDATORY_VERDICT_CHECKS - names:
        raise PilotBoundaryError(REFUSAL_VERDICT_VACUOUS)


def _refuse_if_authorized_checks_invalid(checks):
    if not isinstance(checks, list) or not checks:
        raise PilotBoundaryError(REFUSAL_UNVERIFIED)
    names = set()
    for entry in checks:
        if not isinstance(entry, dict):
            raise PilotBoundaryError(REFUSAL_UNVERIFIED)
        name = entry.get("check")
        if not isinstance(name, str):
            raise PilotBoundaryError(REFUSAL_UNVERIFIED)
        names.add(name)
        if entry.get("result") != "pass":
            raise PilotBoundaryError(REFUSAL_UNVERIFIED)
    if _MANDATORY_VERDICT_CHECKS - names:
        raise PilotBoundaryError(REFUSAL_UNVERIFIED)


def _terminate_and_wait(proc):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def _run_bounded_observer(command, *, run_cwd, env, timeout_seconds, max_output_bytes):
    # bite-axis: output containment — observer stdout is read with a byte cap so oversized output
    # cannot exhaust memory; the child is always reaped on every exit path.
    proc = subprocess.Popen(
        command,
        cwd=run_cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        shell=False,
        env=env,
    )
    try:
        stdout_holder = []
        read_error = []

        def _read_stdout():
            try:
                stdout_holder.append(proc.stdout.read(max_output_bytes + 1))
            except Exception as exc:
                read_error.append(exc)

        reader = threading.Thread(target=_read_stdout, daemon=True)
        reader.start()
        reader.join(timeout=timeout_seconds)

        if reader.is_alive():
            _terminate_and_wait(proc)
            raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_FAILED)

        if read_error:
            _terminate_and_wait(proc)
            raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_FAILED)

        stdout = stdout_holder[0] if stdout_holder else b""

        if len(stdout) > max_output_bytes:
            _terminate_and_wait(proc)
            raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_FAILED)

        try:
            proc.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            _terminate_and_wait(proc)
            raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_FAILED)

        if proc.returncode != 0:
            raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_FAILED)

        return stdout
    except PilotBoundaryError:
        raise
    except Exception:
        _terminate_and_wait(proc)
        raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_FAILED)
    finally:
        if proc.poll() is None:
            _terminate_and_wait(proc)
        if proc.stdout:
            proc.stdout.close()
