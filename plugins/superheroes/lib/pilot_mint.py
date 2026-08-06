"""Pilot mint client — authorized minting, flag scope, gate-off exercise, sentinel (D10).

Minted sign-in is a supported path, never an assumption, constrained at both the gate
and the account. Every public path goes through A3's boundary verdict; this module
performs no network I/O — the caller injects a transport callable.

Non-goals: setting the enabling flag (design §4 — read-only), network I/O, policy
resolution, boundary verification — those belong to callers and sibling modules.
"""
import json
import os

import pilot_bounded_run
import pilot_contract
import pilot_journal
import pilot_probe
import pilot_provision
import pilot_slot

REFUSAL_ENVELOPE_INCOMPLETE = "mint-envelope-incomplete"
REFUSAL_OBSERVED_SCOPES_INVALID = "mint-observed-scopes-invalid"
REFUSAL_FLAG_SET_OUTSIDE_DECLARED_SCOPE = "mint-flag-set-outside-declared-scope"

REFUSAL_GATE_OFF_ARGUMENT_INVALID = "mint-gate-off-argument-invalid"
REFUSAL_GATE_OFF_CWD_INVALID = "mint-gate-off-cwd-invalid"
REFUSAL_GATE_OFF_ENVIRONMENT_INVALID = "mint-gate-off-environment-invalid"
REFUSAL_GATE_OFF_TIMEOUT = "mint-gate-off-timeout"
REFUSAL_GATE_OFF_OUTPUT_OVERSIZE = "mint-gate-off-output-oversize"
REFUSAL_GATE_OFF_SPAWN_FAILED = "mint-gate-off-spawn-failed"
REFUSAL_GATE_OFF_TEST_FAILED = "mint-gate-off-test-failed"

REFUSAL_RECEIPT_ARGUMENT_INVALID = "mint-receipt-argument-invalid"

REFUSAL_TRANSPORT_INVALID = "mint-transport-invalid"

REFUSAL_CONTROL_DID_NOT_MINT = "mint-control-did-not-mint"
REFUSAL_SENTINEL_MINTED = "mint-sentinel-minted"
REFUSAL_SENTINEL_ENDPOINT_ABSENT = "mint-sentinel-endpoint-absent"
REFUSAL_SENTINEL_UNEXPECTED_STATUS = "mint-sentinel-unexpected-status"
REFUSAL_SENTINEL_SETUP_FAILED = "mint-sentinel-setup-failed"

OUTCOME_REFUSED = "refused"
OUTCOME_MINTED = "minted"
OUTCOME_INCONCLUSIVE = "inconclusive"

REFUSAL_STATUSES = frozenset({400, 403, 409, 422})

_ENVELOPE_KEYS = frozenset({
    "enablingFlagEnvVar",
    "enabledScopes",
    "forbiddenScopes",
    "gateOffTestCommand",
})

_UNVERIFIED_SENTINEL_DECLARATION = (
    "The framework cannot verify that the sentinel identifier corresponds to no "
    "real account; sentinel_probe_request only proves absence from the mintable "
    "allowlist."
)


class PilotMintError(Exception):
    """Mint-time refusal."""

    def __init__(self, reason, detail=None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _json_serializable(value):
    try:
        json.dumps(value, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError):
        return False
    return True


def flag_scope_check(envelope, *, observed_scopes):
    """Return whether enabling-flag observations stay within declared scopes."""
    # bite-axis: scope authority — a flag set in any scope outside enabledScopes is
    # disqualifying; vacuous observed_scopes never passes.
    envelope_error = _validate_envelope(envelope)
    if envelope_error is not None:
        return _scope_fail(envelope_error)
    if not _is_observed_scopes_mapping(observed_scopes):
        return _scope_fail(REFUSAL_OBSERVED_SCOPES_INVALID)
    if not observed_scopes:
        return _scope_fail(REFUSAL_OBSERVED_SCOPES_INVALID)

    enabled = set(envelope["enabledScopes"])
    offending = sorted(
        scope for scope, is_set in observed_scopes.items()
        if is_set is True and scope not in enabled
    )
    if offending:
        return {
            "ok": False,
            "reason": REFUSAL_FLAG_SET_OUTSIDE_DECLARED_SCOPE,
            "offendingScopes": offending,
        }
    return {"ok": True, "reason": None, "offendingScopes": []}


def run_gate_off_test(envelope, *, run_cwd, environment, timeout_seconds=120,
                      max_output_bytes=65536):
    """Execute gateOffTestCommand with the enabling flag removed from the environment."""
    # bite-axis: gate-off execution — the declared test runs with the enabling variable
    # absent; timeout, oversize output, and spawn failure refuse rather than pass.
    envelope_error = _validate_envelope(envelope)
    if envelope_error is not None:
        return _gate_fail(envelope_error)
    if (
        type(timeout_seconds) is not int
        or isinstance(timeout_seconds, bool)
        or timeout_seconds <= 0
    ):
        return _gate_fail(REFUSAL_GATE_OFF_ARGUMENT_INVALID)
    if (
        type(max_output_bytes) is not int
        or isinstance(max_output_bytes, bool)
        or max_output_bytes <= 0
    ):
        return _gate_fail(REFUSAL_GATE_OFF_ARGUMENT_INVALID)
    command = envelope["gateOffTestCommand"]
    if not isinstance(run_cwd, str) or not run_cwd or not os.path.isdir(run_cwd):
        return _gate_fail(REFUSAL_GATE_OFF_CWD_INVALID)
    if not _is_str_str_mapping(environment):
        return _gate_fail(REFUSAL_GATE_OFF_ENVIRONMENT_INVALID)

    flag_var = envelope["enablingFlagEnvVar"]
    env_copy = dict(environment)
    env_copy.pop(flag_var, None)

    # The gate-off command is a project's own test command, so it may fork children of its own;
    # the runner's process-group containment is unconditional, so the whole group is reaped on
    # timeout regardless of caller.
    run = pilot_bounded_run.run_bounded(
        command,
        run_cwd=run_cwd,
        env=env_copy,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
    )

    outcome = run["outcome"]
    if outcome == pilot_bounded_run.OUTCOME_TIMEOUT:
        return _gate_fail(REFUSAL_GATE_OFF_TIMEOUT)
    if outcome == pilot_bounded_run.OUTCOME_OVERSIZE:
        return _gate_fail(REFUSAL_GATE_OFF_OUTPUT_OVERSIZE)
    if outcome != pilot_bounded_run.OUTCOME_COMPLETED:
        # Fail closed on anything that is not a completed run — spawn-failed today, and any
        # outcome the runner learns to report tomorrow.
        return _gate_fail(REFUSAL_GATE_OFF_SPAWN_FAILED)

    try:
        stdout_text = run["stdout"].decode("utf-8")
    except UnicodeDecodeError:
        stdout_text = ""

    # Neutral exit-code semantics, deliberately unlike pilot_boundary's observer: a nonzero
    # gate-off run is a REPORTED result carrying its exit code, not the same event as a timeout.
    exit_code = run["exitCode"]
    if exit_code == 0:
        return {
            "ok": True,
            "exitCode": exit_code,
            "reason": None,
            "stdout": stdout_text,
        }
    return {
        "ok": False,
        "exitCode": exit_code,
        "reason": REFUSAL_GATE_OFF_TEST_FAILED,
        "stdout": stdout_text,
    }


def gate_off_receipt(envelope, run_result, *, exercised_at):
    """Build a mint-gate-off registry record from a gate-off test run."""
    # bite-axis: digest binding — receipt is bound to the exact envelope exercised via
    # declaration_digest; a changed envelope invalidates the prior receipt.
    if "mint-gate-off" not in pilot_contract.DECLARATION_KINDS:
        raise PilotMintError(REFUSAL_RECEIPT_ARGUMENT_INVALID)
    if not isinstance(exercised_at, str) or not exercised_at:
        raise PilotMintError(REFUSAL_RECEIPT_ARGUMENT_INVALID)
    if not isinstance(envelope, dict) or not _json_serializable(envelope):
        raise PilotMintError(REFUSAL_RECEIPT_ARGUMENT_INVALID)

    if not isinstance(run_result, dict):
        raise PilotMintError(REFUSAL_RECEIPT_ARGUMENT_INVALID)
    passed = run_result.get("ok")
    if type(passed) is not bool:
        raise PilotMintError(REFUSAL_RECEIPT_ARGUMENT_INVALID)
    exit_code = run_result.get("exitCode")
    reason = run_result.get("reason")
    if passed:
        if (
            type(exit_code) is not int
            or isinstance(exit_code, bool)
            or exit_code != 0
            or reason is not None
        ):
            raise PilotMintError(REFUSAL_RECEIPT_ARGUMENT_INVALID)
        evidence = "exitCode=%s" % exit_code
    elif reason is not None:
        evidence = "exitCode=%s reason=%s" % (exit_code, reason)
    else:
        evidence = "exitCode=%s" % exit_code

    return {
        "kind": "mint-gate-off",
        "declarationDigest": pilot_contract.declaration_digest(envelope),
        "exercisedAt": exercised_at,
        "receipt": {
            "result": "pass" if passed else "fail",
            "evidence": evidence,
        },
    }


def require_gate_off(registry, envelope):
    """Require a passing mint-gate-off exercise for the envelope.

    A registry record is the durable receipt of an exercise that happened; it is
    never a substitute for the live sentinel exercise in the current preflight.
    is_exercised carries no freshness or launched-instance binding.
    """
    return pilot_contract.require_exercised(registry, "mint-gate-off", envelope)


def authorized_mint(verdict, policy, slot_ref, account, envelope, *, transport,
                      journal_path, at):
    """Mint a credential through the authorized boundary path with journaling."""
    # bite-axis: boundary gate — no transport call without authorized_mint_request;
    # journal records applied/not-applied/indeterminate honestly on every attempt.
    descriptor = pilot_provision.authorized_mint_request(
        verdict, policy, slot_ref, account, envelope,
    )
    if not callable(transport):
        raise PilotMintError(REFUSAL_TRANSPORT_INVALID)

    canonical_ref = _canonical_slot_ref(slot_ref)
    with pilot_journal.effect(
        journal_path,
        slot_ref=canonical_ref,
        kind=pilot_journal.KIND_CREDENTIAL_MINTED,
        at=at,
    ) as handle:
        try:
            raw = transport(descriptor)
        except Exception:
            result = _classify_mint_response(None, transport_error=True)
            handle.mark_indeterminate(at=at, reason=result["reason"])
            return result

        result = _classify_mint_response(raw)
        outcome = _mint_journal_outcome(result)
        if outcome == pilot_journal.OUTCOME_APPLIED:
            handle.mark_applied(at=at)
        elif outcome == pilot_journal.OUTCOME_NOT_APPLIED:
            handle.mark_not_applied(at=at, reason=result["reason"])
        else:
            handle.mark_indeterminate(at=at, reason=result["reason"])
        return result


def sentinel_exercise(verdict, policy, slot_ref, envelope, *, control_account,
                      sentinel, transport, journal_path, at):
    """Live preflight exercise: control mint must succeed, then sentinel must refuse."""
    # bite-axis: control-leg precondition — a refusal only discriminates when minting
    # demonstrably works; without a successful control mint the sentinel leg does not run.
    # bite-disclosure: the framework cannot verify the sentinel corresponds to no real account;
    # sentinel_probe_request only proves absence from the mintable allowlist.
    if not callable(transport):
        raise PilotMintError(REFUSAL_TRANSPORT_INVALID)

    control = authorized_mint(
        verdict, policy, slot_ref, control_account, envelope,
        transport=transport, journal_path=journal_path, at=at,
    )
    if not control["ok"]:
        return {
            "ok": False,
            "outcome": OUTCOME_INCONCLUSIVE,
            "reason": REFUSAL_CONTROL_DID_NOT_MINT,
            "status": control.get("status"),
            "control": control,
            "unverifiedDeclarations": [_UNVERIFIED_SENTINEL_DECLARATION],
        }

    try:
        descriptor = pilot_provision.authorized_sentinel_probe_request(
            verdict, policy, slot_ref, sentinel, envelope,
        )
        canonical_ref = _canonical_slot_ref(slot_ref)
        with pilot_journal.effect(
            journal_path,
            slot_ref=canonical_ref,
            kind=pilot_journal.KIND_CREDENTIAL_MINTED,
            at=at,
        ) as handle:
            try:
                raw = transport(descriptor)
            except Exception:
                result = _classify_sentinel_response(None, transport_error=True)
                handle.mark_indeterminate(at=at, reason=result["reason"])
                return _sentinel_result(result, control=control)

            result = _classify_sentinel_response(raw)
            if result["outcome"] == OUTCOME_MINTED:
                handle.mark_applied(at=at)
            elif result["outcome"] == OUTCOME_REFUSED:
                handle.mark_not_applied(at=at, reason=result["reason"])
            else:
                handle.mark_indeterminate(at=at, reason=result["reason"])
            return _sentinel_result(result, control=control)
    except Exception as exc:
        return {
            "ok": False,
            "outcome": OUTCOME_INCONCLUSIVE,
            "reason": REFUSAL_SENTINEL_SETUP_FAILED,
            "status": None,
            "control": control,
            "unverifiedDeclarations": [_UNVERIFIED_SENTINEL_DECLARATION],
            "detail": type(exc).__name__,
        }


def _classify_mint_response(raw, *, transport_error=False):
    """Classify a transport response for authorized_mint."""
    if transport_error:
        return {
            "ok": False,
            "reason": pilot_probe.REASON_TRANSPORT_ERROR,
            "credential": None,
            "status": None,
        }
    if not isinstance(raw, dict):
        return _mint_fail(pilot_probe.REASON_INVALID_BODY)
    status = raw.get("status")
    body = raw.get("body")
    if type(status) is not int:
        return _mint_fail(pilot_probe.REASON_INVALID_BODY)
    if not _is_2xx(status):
        return _mint_status_fail(status)
    if body is None or body == "" or body == b"":
        return _mint_fail(pilot_probe.REASON_INVALID_BODY)
    return {"ok": True, "reason": None, "credential": body, "status": status}


def _classify_sentinel_response(raw, *, transport_error=False):
    """Classify a transport response for the sentinel leg."""
    if transport_error:
        return {
            "ok": False,
            "outcome": OUTCOME_INCONCLUSIVE,
            "reason": pilot_probe.REASON_TRANSPORT_ERROR,
            "status": None,
        }
    if not isinstance(raw, dict):
        return _sentinel_inconclusive(pilot_probe.REASON_INVALID_BODY, status=None)
    status = raw.get("status")
    if type(status) is not int or "body" not in raw:
        return _sentinel_inconclusive(pilot_probe.REASON_INVALID_BODY, status=None)

    if status in REFUSAL_STATUSES:
        return {
            "ok": True,
            "outcome": OUTCOME_REFUSED,
            "reason": None,
            "status": status,
        }
    if status == 401:
        # 401 means the request was not authenticated — the allowlist may never have
        # been consulted, which is the same "could not tell ≠ refused" reasoning as 404.
        return _sentinel_inconclusive(pilot_probe.REASON_UNAUTHORIZED, status=status)
    if _is_2xx(status):
        return {
            "ok": False,
            "outcome": OUTCOME_MINTED,
            "reason": REFUSAL_SENTINEL_MINTED,
            "status": status,
        }
    if status == 404:
        # A 404 says the endpoint was not there at all, so the allowlist was never
        # consulted and the probe demonstrated nothing. Treating "we could not tell"
        # as "it refused" is precisely how this check fails open.
        return {
            "ok": False,
            "outcome": OUTCOME_INCONCLUSIVE,
            "reason": REFUSAL_SENTINEL_ENDPOINT_ABSENT,
            "status": status,
        }
    if status == 429:
        return _sentinel_inconclusive(pilot_probe.REASON_RATE_LIMITED, status=status)
    if status >= 500:
        return _sentinel_inconclusive(
            pilot_probe.REASON_INFRASTRUCTURE_UNAVAILABLE, status=status,
        )
    return _sentinel_inconclusive(REFUSAL_SENTINEL_UNEXPECTED_STATUS, status=status)


def _canonical_slot_ref(slot_ref):
    slot, generation = pilot_slot.parse_slot_ref(slot_ref)
    return pilot_slot.format_slot_ref(slot, generation)


def _validate_envelope(envelope):
    if not isinstance(envelope, dict):
        return REFUSAL_ENVELOPE_INCOMPLETE
    if set(envelope.keys()) != _ENVELOPE_KEYS:
        return REFUSAL_ENVELOPE_INCOMPLETE
    flag_var = envelope.get("enablingFlagEnvVar")
    if not isinstance(flag_var, str) or not flag_var:
        return REFUSAL_ENVELOPE_INCOMPLETE
    enabled = envelope.get("enabledScopes")
    forbidden = envelope.get("forbiddenScopes")
    if not isinstance(enabled, list) or not isinstance(forbidden, list):
        return REFUSAL_ENVELOPE_INCOMPLETE
    for scope in enabled:
        if not isinstance(scope, str):
            return REFUSAL_ENVELOPE_INCOMPLETE
    for scope in forbidden:
        if not isinstance(scope, str):
            return REFUSAL_ENVELOPE_INCOMPLETE
    gate_off = envelope.get("gateOffTestCommand")
    if not _is_command_argv(gate_off):
        return REFUSAL_ENVELOPE_INCOMPLETE
    return None


def _is_observed_scopes_mapping(observed_scopes):
    if not isinstance(observed_scopes, dict):
        return False
    for key, value in observed_scopes.items():
        if not isinstance(key, str):
            return False
        if type(value) is not bool:
            return False
    return True


def _is_command_argv(command):
    if not isinstance(command, list) or not command:
        return False
    return all(isinstance(part, str) and part for part in command)


def _is_str_str_mapping(value):
    if not isinstance(value, dict):
        return False
    for key, val in value.items():
        if not isinstance(key, str) or not isinstance(val, str):
            return False
    return True


def _is_2xx(status):
    return 200 <= status <= 299


def _mint_status_fail(status):
    if status == 401:
        reason = pilot_probe.REASON_UNAUTHORIZED
    elif status == 403:
        reason = pilot_probe.REASON_FORBIDDEN
    elif status == 429:
        reason = pilot_probe.REASON_RATE_LIMITED
    elif status >= 500:
        reason = pilot_probe.REASON_INFRASTRUCTURE_UNAVAILABLE
    else:
        reason = pilot_probe.REASON_UNEXPECTED_STATUS
    return _mint_fail(reason, status=status)


def _mint_fail(reason, status=None):
    return {"ok": False, "reason": reason, "credential": None, "status": status}


def _mint_journal_outcome(result):
    if result["ok"]:
        return pilot_journal.OUTCOME_APPLIED
    reason = result["reason"]
    if reason in (pilot_probe.REASON_UNAUTHORIZED, pilot_probe.REASON_FORBIDDEN):
        return pilot_journal.OUTCOME_NOT_APPLIED
    return pilot_journal.OUTCOME_INDETERMINATE


def _sentinel_inconclusive(reason, *, status):
    return {
        "ok": False,
        "outcome": OUTCOME_INCONCLUSIVE,
        "reason": reason,
        "status": status,
    }


def _sentinel_result(classified, *, control):
    return {
        "ok": classified["ok"],
        "outcome": classified["outcome"],
        "reason": classified["reason"],
        "status": classified["status"],
        "control": control,
        "unverifiedDeclarations": [_UNVERIFIED_SENTINEL_DECLARATION],
    }


def _scope_fail(reason):
    return {"ok": False, "reason": reason, "offendingScopes": []}


def _gate_fail(reason):
    return {"ok": False, "exitCode": None, "reason": reason, "stdout": ""}

