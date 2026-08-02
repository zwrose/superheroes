"""Pilot launch-time credential validity horizon margin (B6).

Compares ``deadline + margin <= credential validity horizon`` per account and per
sign-in path, using provenance-bound horizon observations. Unknown provenance
cannot claim an unattended horizon.

Non-goals: runtime terminus enforcement (B5, #827); reading capture artifacts off
disk (B4); server-probe transport (caller's responsibility).
"""
import base64
import calendar
import json
import math
import time

import pilot_contract
import pilot_slot

MAX_JWT_PAYLOAD_BYTES = 8192

REFUSAL_INSTANT_INVALID = "horizon-instant-invalid"
REFUSAL_STORAGE_STATE_INVALID = "horizon-storage-state-invalid"
REFUSAL_COOKIE_NAME_INVALID = "horizon-cookie-name-invalid"
REFUSAL_COOKIE_NOT_FOUND = "horizon-cookie-not-found"
REFUSAL_COOKIE_AMBIGUOUS = "horizon-cookie-ambiguous"
REFUSAL_COOKIE_SESSION_ONLY = "horizon-cookie-session-only"
REFUSAL_TOKEN_MALFORMED = "horizon-token-malformed"
REFUSAL_TOKEN_CLAIM_MISSING = "horizon-token-claim-missing"
REFUSAL_TOKEN_CLAIM_INVALID = "horizon-token-claim-invalid"
REFUSAL_OBSERVATION_INVALID = "horizon-observation-invalid"
REFUSAL_SIGN_IN_PATH_INVALID = "horizon-sign-in-path-invalid"
REFUSAL_DEADLINE_INVALID = "horizon-deadline-invalid"
REFUSAL_MARGIN_INVALID = "horizon-margin-invalid"
REFUSAL_FLAG_INVALID = "horizon-flag-invalid"
REFUSAL_NOW_INVALID = "horizon-now-invalid"
REFUSAL_MAX_AGE_INVALID = "horizon-max-age-invalid"
REFUSAL_DEADLINE_IN_PAST = "horizon-deadline-in-past"
REFUSAL_UNKNOWN_PROVENANCE_UNATTENDED = "horizon-unknown-provenance-unattended"
REFUSAL_SERVER_PROBE_STALE = "horizon-server-probe-stale"
REFUSAL_MARGIN_EXCEEDED = "horizon-margin-exceeded"
REFUSAL_ACCOUNT_SET_EMPTY = "horizon-account-set-empty"
REFUSAL_ACCOUNT_SET_MISMATCH = "horizon-account-set-mismatch"
REFUSAL_ACCOUNT_ENTRY_INVALID = "horizon-account-entry-invalid"

_OBSERVATION_KEYS = frozenset({"provenance", "expiresAt"})
_SERVER_PROBE_KEYS = frozenset({"provenance", "expiresAt", "observedAt"})


class PilotHorizonError(Exception):
    """Raised when horizon parsing, observation construction, or margin input refuses."""

    def __init__(self, reason, detail=None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def parse_instant(value):
    """Parse ``YYYY-MM-DDTHH:MM:SSZ`` to UTC epoch seconds; refuse anything else."""
    if not isinstance(value, str):
        raise PilotHorizonError(REFUSAL_INSTANT_INVALID)
    try:
        parsed = time.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise PilotHorizonError(REFUSAL_INSTANT_INVALID)
    return calendar.timegm(parsed)


def cookie_expiry_observation(storage_state, *, cookie_name):
    """Derive a cookie-expiry horizon from a parsed saved-browser-state mapping."""
    # bite-axis: cookie horizon — session or missing expiry refuses; duplicate names refuse;
    # float expiry truncates toward zero.
    if not isinstance(storage_state, dict):
        raise PilotHorizonError(REFUSAL_STORAGE_STATE_INVALID)
    cookies = storage_state.get("cookies")
    if not isinstance(cookies, list):
        raise PilotHorizonError(REFUSAL_STORAGE_STATE_INVALID)
    if not isinstance(cookie_name, str) or not cookie_name:
        raise PilotHorizonError(REFUSAL_COOKIE_NAME_INVALID)

    matches = []
    for entry in cookies:
        if not isinstance(entry, dict):
            raise PilotHorizonError(REFUSAL_STORAGE_STATE_INVALID)
        if entry.get("name") != cookie_name:
            continue
        matches.append(entry)

    if not matches:
        raise PilotHorizonError(REFUSAL_COOKIE_NOT_FOUND)
    if len(matches) > 1:
        raise PilotHorizonError(REFUSAL_COOKIE_AMBIGUOUS)

    entry = matches[0]
    if "expires" not in entry:
        raise PilotHorizonError(REFUSAL_COOKIE_SESSION_ONLY)
    expires = entry["expires"]
    if isinstance(expires, bool) or not isinstance(expires, (int, float)):
        raise PilotHorizonError(REFUSAL_STORAGE_STATE_INVALID)
    if not math.isfinite(expires):
        raise PilotHorizonError(REFUSAL_STORAGE_STATE_INVALID)
    if expires in (-1, 0):
        raise PilotHorizonError(REFUSAL_COOKIE_SESSION_ONLY)
    if expires < 0:
        raise PilotHorizonError(REFUSAL_STORAGE_STATE_INVALID)
    if int(expires) < 1:
        raise PilotHorizonError(REFUSAL_COOKIE_SESSION_ONLY)

    return {
        "provenance": "cookie-expiry",
        "expiresAt": int(expires),
    }


def token_claim_observation(token, *, claim="exp"):
    """Derive a token-claim horizon by decoding a JWT-shaped credential payload."""
    # bite-axis: token claim — malformed token, missing claim, or non-numeric expiry refuses.
    # bite-disclosure: signature is not verified; this reads a horizon the credential asserts
    # about itself, not authentication. A forged token would state a forged expiry, which is
    # acceptable here because the credential already came through the verified seed path.
    if not isinstance(token, str) or not token:
        raise PilotHorizonError(REFUSAL_TOKEN_MALFORMED)
    segments = token.split(".")
    if len(segments) != 3:
        raise PilotHorizonError(REFUSAL_TOKEN_MALFORMED)

    payload_segment = segments[1]
    if len(payload_segment.encode("utf-8")) > MAX_JWT_PAYLOAD_BYTES:
        raise PilotHorizonError(REFUSAL_TOKEN_MALFORMED)
    try:
        padding = "=" * ((4 - len(payload_segment) % 4) % 4)
        raw = base64.urlsafe_b64decode(payload_segment + padding)
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise PilotHorizonError(REFUSAL_TOKEN_MALFORMED)

    if not isinstance(payload, dict):
        raise PilotHorizonError(REFUSAL_TOKEN_MALFORMED)
    if claim not in payload:
        raise PilotHorizonError(REFUSAL_TOKEN_CLAIM_MISSING)

    claim_value = payload[claim]
    if isinstance(claim_value, bool) or not isinstance(claim_value, (int, float)):
        raise PilotHorizonError(REFUSAL_TOKEN_CLAIM_INVALID)
    if not math.isfinite(claim_value):
        raise PilotHorizonError(REFUSAL_TOKEN_CLAIM_INVALID)
    if claim_value < 1:
        raise PilotHorizonError(REFUSAL_TOKEN_CLAIM_INVALID)

    return {
        "provenance": "token-claim",
        "expiresAt": int(claim_value),
    }


def server_probe_observation(*, expires_at, observed_at):
    """Build a server-probe horizon observation."""
    if expires_at is not None:
        if type(expires_at) is not int or isinstance(expires_at, bool) or expires_at < 1:
            raise PilotHorizonError(REFUSAL_OBSERVATION_INVALID)
    if type(observed_at) is not int or isinstance(observed_at, bool) or observed_at < 1:
        raise PilotHorizonError(REFUSAL_OBSERVATION_INVALID)
    return {
        "provenance": "server-probe",
        "expiresAt": expires_at,
        "observedAt": observed_at,
    }


def unknown_observation():
    """Return an explicit unknown-provenance observation."""
    return {
        "provenance": "unknown",
        "expiresAt": None,
    }


def validate_observation(observation):
    """Refuse observations that do not match the constructor contract shape."""
    # bite-disclosure: this is a shape contract, not an unforgeable seal — callers can still
    # hand-build dicts in Python, but the comparison refuses shapes the constructors would not
    # emit.
    if not isinstance(observation, dict):
        raise PilotHorizonError(REFUSAL_OBSERVATION_INVALID)

    provenance = observation.get("provenance")
    if not isinstance(provenance, str) or provenance not in pilot_contract.VALIDITY_PROVENANCE:
        raise PilotHorizonError(REFUSAL_OBSERVATION_INVALID)

    if provenance == "server-probe":
        if set(observation.keys()) != _SERVER_PROBE_KEYS:
            raise PilotHorizonError(REFUSAL_OBSERVATION_INVALID)
        observed_at = observation.get("observedAt")
        if type(observed_at) is not int or isinstance(observed_at, bool) or observed_at < 1:
            raise PilotHorizonError(REFUSAL_OBSERVATION_INVALID)
        expires_at = observation.get("expiresAt")
        if expires_at is not None:
            if type(expires_at) is not int or isinstance(expires_at, bool) or expires_at < 1:
                raise PilotHorizonError(REFUSAL_OBSERVATION_INVALID)
        return

    if set(observation.keys()) != _OBSERVATION_KEYS:
        raise PilotHorizonError(REFUSAL_OBSERVATION_INVALID)

    expires_at = observation.get("expiresAt")
    if provenance == "unknown":
        if expires_at is not None:
            raise PilotHorizonError(REFUSAL_OBSERVATION_INVALID)
        return

    if type(expires_at) is not int or isinstance(expires_at, bool) or expires_at < 1:
        raise PilotHorizonError(REFUSAL_OBSERVATION_INVALID)


def account_margin(
    observation,
    *,
    deadline_at,
    margin_seconds,
    sign_in_path,
    attended,
    now=None,
    server_probe_max_age=None,
):
    """Compare deadline plus margin against a provenance-bound horizon observation."""
    # bite-axis: horizon claimability — unknown provenance cannot claim an unattended horizon.
    # bite-axis: margin non-degeneracy — margin_seconds must be strictly positive.
    # bite-axis: the margin math — required_until = deadline_at + margin_seconds must be <= expiresAt.
    # bite-axis: no path exemption — minted sign-in path does not bypass a shortfall.
    # bite-axis: server-probe staleness — an observation older than server_probe_max_age refuses.
    validate_observation(observation)

    if not isinstance(sign_in_path, str) or sign_in_path not in pilot_contract.SIGN_IN_PATHS:
        raise PilotHorizonError(REFUSAL_SIGN_IN_PATH_INVALID)

    if type(deadline_at) is not int or isinstance(deadline_at, bool) or deadline_at < 1:
        raise PilotHorizonError(REFUSAL_DEADLINE_INVALID)

    if type(margin_seconds) is not int or isinstance(margin_seconds, bool) or margin_seconds <= 0:
        raise PilotHorizonError(REFUSAL_MARGIN_INVALID)

    if type(attended) is not bool:
        raise PilotHorizonError(REFUSAL_FLAG_INVALID)

    if now is not None:
        if type(now) is not int or isinstance(now, bool) or now < 1:
            raise PilotHorizonError(REFUSAL_NOW_INVALID)
        if deadline_at <= now:
            raise PilotHorizonError(REFUSAL_DEADLINE_IN_PAST)

    if server_probe_max_age is not None:
        if type(server_probe_max_age) is not int or isinstance(server_probe_max_age, bool):
            raise PilotHorizonError(REFUSAL_MAX_AGE_INVALID)
        if server_probe_max_age < 1:
            raise PilotHorizonError(REFUSAL_MAX_AGE_INVALID)

    provenance = observation["provenance"]
    base = {
        "provenance": provenance,
        "signInPath": sign_in_path,
        "requiredUntil": None,
        "shortfallSeconds": None,
        "requiresMidWaveRecheck": False,
    }

    if not pilot_contract.supports_unattended_horizon(provenance):
        if attended:
            return dict(
                base,
                ok=True,
                disposition="attended",
                reason=None,
            )
        return dict(
            base,
            ok=False,
            disposition=None,
            reason=REFUSAL_UNKNOWN_PROVENANCE_UNATTENDED,
        )

    if provenance == "server-probe" and server_probe_max_age is not None:
        if now is None:
            raise PilotHorizonError(REFUSAL_NOW_INVALID)
        observed_at = observation["observedAt"]
        if now - observed_at > server_probe_max_age:
            return dict(
                base,
                ok=False,
                disposition=None,
                reason=REFUSAL_SERVER_PROBE_STALE,
            )

    expires_at = observation["expiresAt"]

    if provenance == "server-probe" and expires_at is None:
        return dict(
            base,
            ok=True,
            disposition="server-probe-recheck",
            reason=None,
            requiresMidWaveRecheck=True,
        )

    required_until = deadline_at + margin_seconds
    base["requiredUntil"] = required_until

    if required_until <= expires_at:
        return dict(
            base,
            ok=True,
            disposition="covered",
            reason=None,
        )

    return dict(
        base,
        ok=False,
        disposition=None,
        reason=REFUSAL_MARGIN_EXCEEDED,
        shortfallSeconds=required_until - expires_at,
    )


def wave_margin(
    slot_accounts,
    accounts,
    *,
    deadline_at,
    margin_seconds,
    sign_in_path,
    attended,
    now=None,
    server_probe_max_age=None,
):
    """Evaluate account_margin for every account; fail closed on the first refusal."""
    # bite-axis: account-set alignment — authoritative account list from slot_accounts; the
    # observations key set must match exactly.
    if not isinstance(slot_accounts, dict):
        raise PilotHorizonError(REFUSAL_ACCOUNT_SET_MISMATCH)
    accounts_field = slot_accounts.get("accounts")
    if not isinstance(accounts_field, list):
        raise PilotHorizonError(REFUSAL_ACCOUNT_SET_MISMATCH)
    for entry in accounts_field:
        if not isinstance(entry, dict):
            raise PilotHorizonError(REFUSAL_ACCOUNT_SET_MISMATCH)
        account = entry.get("account")
        if not isinstance(account, str) or not account:
            raise PilotHorizonError(REFUSAL_ACCOUNT_SET_MISMATCH)
    account_list = pilot_slot.account_keys(slot_accounts)
    if not account_list:
        raise PilotHorizonError(REFUSAL_ACCOUNT_SET_EMPTY)

    if not isinstance(accounts, dict) or not accounts:
        raise PilotHorizonError(REFUSAL_ACCOUNT_SET_EMPTY)

    slot_keys = set(account_list)
    observation_keys = set(accounts.keys())
    if observation_keys != slot_keys:
        raise PilotHorizonError(REFUSAL_ACCOUNT_SET_MISMATCH)

    per_account = {}
    first_reason = None
    all_ok = True
    requires_mid_wave_recheck = False

    for account in sorted(account_list):
        if not isinstance(account, str) or not account:
            raise PilotHorizonError(REFUSAL_ACCOUNT_ENTRY_INVALID, detail=repr(account))

        result = account_margin(
            accounts[account],
            deadline_at=deadline_at,
            margin_seconds=margin_seconds,
            sign_in_path=sign_in_path,
            attended=attended,
            now=now,
            server_probe_max_age=server_probe_max_age,
        )
        per_account[account] = result
        if result.get("requiresMidWaveRecheck"):
            requires_mid_wave_recheck = True
        if not result["ok"]:
            all_ok = False
            if first_reason is None:
                first_reason = result["reason"]

    return {
        "ok": all_ok,
        "reason": first_reason,
        "accounts": per_account,
        "requiresMidWaveRecheck": requires_mid_wave_recheck,
    }
