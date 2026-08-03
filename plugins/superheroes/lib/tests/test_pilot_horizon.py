"""Tests for pilot_horizon — launch-time credential validity margin math."""
import base64
import inspect
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_horizon as ph  # noqa: E402
import pilot_slot  # noqa: E402

HOSTILE_VALUES = [
    None,
    [],
    {},
    set(),
    0,
    "",
    b"x",
    object(),
    True,
    False,
    1.0,
    "x" * 100,
]


def _raises(reason):
    return pytest.raises(ph.PilotHorizonError, match=reason)


def _jwt(payload):
    header = base64.urlsafe_b64encode(b"{}").decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = base64.urlsafe_b64encode(b"sig").decode().rstrip("=")
    return "%s.%s.%s" % (header, body, sig)


def _cookie_state(expires, name="session", extra=None):
    entry = {"name": name}
    if expires is not None:
        entry["expires"] = expires
    if extra:
        entry.update(extra)
    return {"cookies": [entry]}


def _token_obs(expires_at):
    return ph.token_claim_observation(_jwt({"exp": expires_at}))


def _slot_accounts(accounts=None):
    if accounts is None:
        accounts = [
            {"account": "good", "role": "resource-owner"},
            {"account": "bad", "role": "viewer"},
        ]
    return pilot_slot.slot_account_set("slot-a", 1, accounts)


def _margin_kwargs(**overrides):
    base = {
        "deadline_at": 1000,
        "margin_seconds": 100,
        "sign_in_path": "captured",
        "attended": False,
    }
    base.update(overrides)
    return base


def _wave_margin(slot_accounts, accounts, **overrides):
    return ph.wave_margin(slot_accounts, accounts, **_margin_kwargs(**overrides))


# --- parse_instant ---


def test_parse_instant_valid():
    import calendar
    import time

    expected = calendar.timegm(time.strptime("2026-08-02T04:00:00Z", "%Y-%m-%dT%H:%M:%SZ"))
    assert ph.parse_instant("2026-08-02T04:00:00Z") == expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        123,
        "2026-08-02T04:00:00",
        "2026-08-02T04:00:00+00:00",
        "2026-08-02T04:00:00.5Z",
        "2026-13-02T04:00:00Z",
    ],
)
def test_parse_instant_refuses_invalid(value):
    with _raises(ph.REFUSAL_INSTANT_INVALID):
        ph.parse_instant(value)


# --- cookie_expiry_observation ---


def test_cookie_expiry_observation_valid():
    obs = ph.cookie_expiry_observation(
        {"cookies": [{"name": "sid", "expires": 5000}]},
        cookie_name="sid",
    )
    assert obs == {"provenance": "cookie-expiry", "expiresAt": 5000}


def test_cookie_expiry_truncates_float_down():
    obs = ph.cookie_expiry_observation(
        {"cookies": [{"name": "sid", "expires": 1000.9}]},
        cookie_name="sid",
    )
    assert obs["expiresAt"] == 1000


@pytest.mark.parametrize(
    "storage_state",
    [None, [], "x", {"cookies": "x"}, {"cookies": [None]}, {"cookies": ["x"]}],
)
def test_cookie_expiry_refuses_invalid_storage_state(storage_state):
    with _raises(ph.REFUSAL_STORAGE_STATE_INVALID):
        ph.cookie_expiry_observation(storage_state, cookie_name="sid")


@pytest.mark.parametrize("cookie_name", [None, "", 1, True])
def test_cookie_expiry_refuses_invalid_cookie_name(cookie_name):
    state = {"cookies": [{"name": "sid", "expires": 5000}]}
    with _raises(ph.REFUSAL_COOKIE_NAME_INVALID):
        ph.cookie_expiry_observation(state, cookie_name=cookie_name)


def test_cookie_expiry_refuses_not_found():
    with _raises(ph.REFUSAL_COOKIE_NOT_FOUND):
        ph.cookie_expiry_observation(
            {"cookies": [{"name": "other", "expires": 5000}]},
            cookie_name="sid",
        )


def test_cookie_expiry_refuses_ambiguous():
    state = {
        "cookies": [
            {"name": "sid", "expires": 5000},
            {"name": "sid", "expires": 6000},
        ],
    }
    with _raises(ph.REFUSAL_COOKIE_AMBIGUOUS):
        ph.cookie_expiry_observation(state, cookie_name="sid")


@pytest.mark.parametrize(
    "expires",
    [-1, 0],
)
def test_cookie_expiry_refuses_session_cookie_numeric(expires):
    with _raises(ph.REFUSAL_COOKIE_SESSION_ONLY):
        ph.cookie_expiry_observation(_cookie_state(expires), cookie_name="session")


def test_cookie_expiry_refuses_session_cookie_absent_expires():
    with _raises(ph.REFUSAL_COOKIE_SESSION_ONLY):
        ph.cookie_expiry_observation(_cookie_state(None), cookie_name="session")


@pytest.mark.parametrize("expires", [False, True])
def test_cookie_expiry_refuses_boolean_expires(expires):
    with _raises(ph.REFUSAL_STORAGE_STATE_INVALID):
        ph.cookie_expiry_observation(_cookie_state(expires), cookie_name="session")


# --- token_claim_observation ---


def test_token_claim_observation_valid():
    obs = ph.token_claim_observation(_jwt({"exp": 9000}))
    assert obs == {"provenance": "token-claim", "expiresAt": 9000}


@pytest.mark.parametrize(
    "token",
    [
        None,
        "",
        "one.two",
        "a.b",
        _jwt([]),
        _jwt({"exp": "nope"}),
        _jwt({"exp": True}),
        _jwt({"exp": -1}),
    ],
)
def test_token_claim_observation_refuses_malformed_or_invalid(token):
    reason = ph.REFUSAL_TOKEN_MALFORMED
    if isinstance(token, str) and token.count(".") == 2:
        payload = token.split(".")[1]
        padding = "=" * ((4 - len(payload) % 4) % 4)
        try:
            decoded = json.loads(
                base64.urlsafe_b64decode(payload + padding).decode("utf-8")
            )
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            decoded = None
        if isinstance(decoded, list):
            reason = ph.REFUSAL_TOKEN_MALFORMED
        elif isinstance(decoded, dict):
            if "exp" not in decoded:
                reason = ph.REFUSAL_TOKEN_CLAIM_MISSING
            elif isinstance(decoded.get("exp"), str):
                reason = ph.REFUSAL_TOKEN_CLAIM_INVALID
            elif decoded.get("exp") is True:
                reason = ph.REFUSAL_TOKEN_CLAIM_INVALID
            elif decoded.get("exp") == -1:
                reason = ph.REFUSAL_TOKEN_CLAIM_INVALID
    with _raises(reason):
        ph.token_claim_observation(token)


def test_token_claim_refuses_unparseable_payload():
    with _raises(ph.REFUSAL_TOKEN_MALFORMED):
        ph.token_claim_observation("a.!!!.c")


def test_token_claim_refuses_missing_exp():
    with _raises(ph.REFUSAL_TOKEN_CLAIM_MISSING):
        ph.token_claim_observation(_jwt({"sub": "x"}))


def test_token_claim_refuses_surrogate_segment():
    with _raises(ph.REFUSAL_TOKEN_MALFORMED):
        ph.token_claim_observation("a.\ud800.c")


def test_token_claim_refuses_non_string_claim():
    with _raises(ph.REFUSAL_TOKEN_CLAIM_INVALID):
        ph.token_claim_observation("aGVhZA.eyJleHAiOjF9.c", claim=[])


# --- server_probe_observation ---


def test_server_probe_observation_with_expiry():
    obs = ph.server_probe_observation(expires_at=5000, observed_at=1000)
    assert obs == {
        "provenance": "server-probe",
        "expiresAt": 5000,
        "observedAt": 1000,
    }


def test_server_probe_observation_without_expiry():
    obs = ph.server_probe_observation(expires_at=None, observed_at=1000)
    assert obs["expiresAt"] is None


@pytest.mark.parametrize("observed_at", [None, 0, True, "x"])
def test_server_probe_refuses_invalid_observed_at(observed_at):
    with _raises(ph.REFUSAL_OBSERVATION_INVALID):
        ph.server_probe_observation(expires_at=5000, observed_at=observed_at)


@pytest.mark.parametrize("expires_at", [0, True, "x"])
def test_server_probe_refuses_invalid_expires_at(expires_at):
    with _raises(ph.REFUSAL_OBSERVATION_INVALID):
        ph.server_probe_observation(expires_at=expires_at, observed_at=1000)


# --- unknown_observation ---


def test_unknown_observation():
    assert ph.unknown_observation() == {
        "provenance": "unknown",
        "expiresAt": None,
    }


# --- validate_observation ---


def test_validate_observation_accepts_constructors():
    ph.validate_observation(ph.unknown_observation())
    ph.validate_observation(_token_obs(5000))
    ph.validate_observation(
        ph.server_probe_observation(expires_at=None, observed_at=1000)
    )


def test_validate_observation_refuses_hand_built_cookie_with_none_expiry():
    with _raises(ph.REFUSAL_OBSERVATION_INVALID):
        ph.validate_observation({"provenance": "cookie-expiry", "expiresAt": None})


@pytest.mark.parametrize("observation", [None, [], {"provenance": "bogus", "expiresAt": 1}])
def test_validate_observation_refuses_invalid(observation):
    with _raises(ph.REFUSAL_OBSERVATION_INVALID):
        ph.validate_observation(observation)


# --- account_margin: unknown provenance edges 1-3 ---


def test_edge1_unknown_unattended_captured_refuses():
    result = ph.account_margin(
        ph.unknown_observation(),
        **_margin_kwargs(sign_in_path="captured", attended=False),
    )
    assert result["ok"] is False
    assert result["reason"] == ph.REFUSAL_UNKNOWN_PROVENANCE_UNATTENDED


def test_edge2_unknown_unattended_minted_still_refuses():
    result = ph.account_margin(
        ph.unknown_observation(),
        **_margin_kwargs(sign_in_path="minted", attended=False),
    )
    assert result["ok"] is False
    assert result["reason"] == ph.REFUSAL_UNKNOWN_PROVENANCE_UNATTENDED


def test_edge3_unknown_attended_ok():
    result = ph.account_margin(
        ph.unknown_observation(),
        **_margin_kwargs(attended=True),
    )
    assert result["ok"] is True
    assert result["disposition"] == "attended"


# --- server-probe edges 4-7 ---


def test_edge4_server_probe_no_expiry_recheck():
    obs = ph.server_probe_observation(expires_at=None, observed_at=1000)
    result = ph.account_margin(obs, **_margin_kwargs())
    assert result["ok"] is True
    assert result["disposition"] == "server-probe-recheck"
    assert result["requiresMidWaveRecheck"] is True


def test_edge5_server_probe_shortfall_refuses():
    obs = ph.server_probe_observation(expires_at=1050, observed_at=1000)
    result = ph.account_margin(
        obs,
        **_margin_kwargs(deadline_at=1000, margin_seconds=100, sign_in_path="captured"),
    )
    assert result["ok"] is False
    assert result["reason"] == ph.REFUSAL_MARGIN_EXCEEDED
    assert result["shortfallSeconds"] == 50


def test_edge6_server_probe_stale_refuses():
    obs = ph.server_probe_observation(expires_at=5000, observed_at=1000)
    result = ph.account_margin(
        obs,
        **_margin_kwargs(deadline_at=3000, now=2000, server_probe_max_age=500),
    )
    assert result["ok"] is False
    assert result["reason"] == ph.REFUSAL_SERVER_PROBE_STALE


def test_edge7_max_age_without_now_refuses():
    obs = ph.server_probe_observation(expires_at=5000, observed_at=1000)
    with _raises(ph.REFUSAL_NOW_INVALID):
        ph.account_margin(
            obs,
            **_margin_kwargs(server_probe_max_age=500),
        )


# --- edge 8: hand-built cookie-expiry with None expiresAt ---


def test_edge8_hand_built_cookie_expiry_none_refuses_at_validate():
    obs = {"provenance": "cookie-expiry", "expiresAt": None}
    with _raises(ph.REFUSAL_OBSERVATION_INVALID):
        ph.validate_observation(obs)


# --- boundary edges 9-10 ---


def test_edge9_boundary_exact_cover_ok():
    obs = _token_obs(1100)
    result = ph.account_margin(
        obs,
        **_margin_kwargs(deadline_at=1000, margin_seconds=100),
    )
    assert result["ok"] is True
    assert result["disposition"] == "covered"
    assert result["requiredUntil"] == 1100


def test_edge10_boundary_shortfall_one_second():
    obs = _token_obs(1100)
    result = ph.account_margin(
        obs,
        **_margin_kwargs(deadline_at=1000, margin_seconds=101),
    )
    assert result["ok"] is False
    assert result["reason"] == ph.REFUSAL_MARGIN_EXCEEDED
    assert result["shortfallSeconds"] == 1


# --- edge 11: minted shortfall ---


def test_edge11_minted_shortfall_refuses():
    obs = _token_obs(1050)
    result = ph.account_margin(
        obs,
        **_margin_kwargs(
            deadline_at=1000,
            margin_seconds=100,
            sign_in_path="minted",
        ),
    )
    assert result["ok"] is False
    assert result["reason"] == ph.REFUSAL_MARGIN_EXCEEDED


# --- edge 12: margin_seconds ---


@pytest.mark.parametrize("margin_seconds", [0, -1])
def test_edge12_margin_non_positive_refuses(margin_seconds):
    obs = _token_obs(5000)
    with _raises(ph.REFUSAL_MARGIN_INVALID):
        ph.account_margin(
            obs,
            **_margin_kwargs(margin_seconds=margin_seconds),
        )


# --- edge 13: bool where int expected ---


@pytest.mark.parametrize(
    "kwargs",
    [
        {"deadline_at": True},
        {"margin_seconds": True},
        {"now": True},
        {"server_probe_max_age": True},
    ],
)
def test_edge13_account_margin_bool_int_refuses(kwargs):
    obs = _token_obs(5000)
    with _raises(
        ph.REFUSAL_DEADLINE_INVALID
        if "deadline_at" in kwargs
        else ph.REFUSAL_MARGIN_INVALID
        if "margin_seconds" in kwargs
        else ph.REFUSAL_NOW_INVALID
        if "now" in kwargs
        else ph.REFUSAL_MAX_AGE_INVALID
    ):
        ph.account_margin(obs, **_margin_kwargs(**kwargs))


def test_edge13_server_probe_observed_at_bool_refuses():
    with _raises(ph.REFUSAL_OBSERVATION_INVALID):
        ph.server_probe_observation(expires_at=5000, observed_at=True)


def test_edge13_server_probe_expires_at_bool_refuses():
    with _raises(ph.REFUSAL_OBSERVATION_INVALID):
        ph.server_probe_observation(expires_at=True, observed_at=1000)


# --- edge 19: wave_margin ---


def test_edge19_wave_margin_one_failing_account():
    accounts = {
        "good": _token_obs(5000),
        "bad": _token_obs(1050),
    }
    result = _wave_margin(_slot_accounts(), accounts, deadline_at=1000, margin_seconds=100)
    assert result["ok"] is False
    assert result["reason"] == ph.REFUSAL_MARGIN_EXCEEDED
    assert result["accounts"]["bad"]["ok"] is False
    assert result["accounts"]["good"]["ok"] is True


def test_wave_margin_all_ok():
    accounts = {
        "a": _token_obs(5000),
        "b": _token_obs(6000),
    }
    slot_accounts = pilot_slot.slot_account_set(
        "slot-a", 1,
        [
            {"account": "a", "role": "resource-owner"},
            {"account": "b", "role": "viewer"},
        ],
    )
    result = _wave_margin(slot_accounts, accounts, deadline_at=1000, margin_seconds=100)
    assert result["ok"] is True
    assert result["reason"] is None
    assert result["requiresMidWaveRecheck"] is False


def test_wave_margin_empty_refuses():
    with _raises(ph.REFUSAL_ACCOUNT_SET_EMPTY):
        _wave_margin(_slot_accounts(), {})


def test_wave_margin_account_set_mismatch():
    slot_accounts = _slot_accounts()
    with _raises(ph.REFUSAL_ACCOUNT_SET_MISMATCH):
        _wave_margin(slot_accounts, {"good": _token_obs(5000)})


def test_wave_margin_invalid_account_key():
    slot_accounts = {
        "slot": "slot-a",
        "generation": 1,
        "ref": "slot-a@1",
        "accounts": [{"account": "", "role": "x"}],
    }
    with _raises(ph.REFUSAL_ACCOUNT_SET_MISMATCH):
        _wave_margin(slot_accounts, {"": _token_obs(5000)})


def test_wave_margin_mixed_type_keys_refuses():
    slot_accounts = pilot_slot.slot_account_set(
        "slot-a", 1, [{"account": "a", "role": "x"}],
    )
    with _raises(ph.REFUSAL_ACCOUNT_SET_MISMATCH):
        _wave_margin(slot_accounts, {1: _token_obs(5000), "a": _token_obs(5000)})


def test_wave_margin_empty_string_account_key_refuses():
    slot_accounts = pilot_slot.slot_account_set(
        "slot-a", 1, [{"account": "x", "role": "r"}],
    )
    with _raises(ph.REFUSAL_ACCOUNT_SET_MISMATCH):
        _wave_margin(slot_accounts, {"": _token_obs(5000), "x": _token_obs(5000)})


@pytest.mark.parametrize("expires", [float("nan"), float("inf"), float("-inf")])
def test_cookie_expiry_refuses_non_finite(expires):
    with _raises(ph.REFUSAL_STORAGE_STATE_INVALID):
        ph.cookie_expiry_observation(_cookie_state(expires), cookie_name="session")


@pytest.mark.parametrize("exp_value", [float("nan"), float("inf"), float("-inf")])
def test_token_claim_refuses_non_finite(exp_value):
    with _raises(ph.REFUSAL_TOKEN_CLAIM_INVALID):
        ph.token_claim_observation(_jwt({"exp": exp_value}))


def test_token_claim_refuses_zero_exp():
    with _raises(ph.REFUSAL_TOKEN_CLAIM_INVALID):
        ph.token_claim_observation(_jwt({"exp": 0}))


def test_cookie_expiry_refuses_negative_other_than_session():
    with _raises(ph.REFUSAL_STORAGE_STATE_INVALID):
        ph.cookie_expiry_observation(_cookie_state(-2), cookie_name="session")


def test_wave_margin_requires_mid_wave_recheck():
    accounts = {
        "good": ph.server_probe_observation(expires_at=None, observed_at=1000),
        "bad": _token_obs(5000),
    }
    result = _wave_margin(_slot_accounts(), accounts)
    assert result["ok"] is True
    assert result["requiresMidWaveRecheck"] is True


# --- additional refusal coverage ---


def test_sign_in_path_invalid():
    with _raises(ph.REFUSAL_SIGN_IN_PATH_INVALID):
        ph.account_margin(_token_obs(5000), **_margin_kwargs(sign_in_path="bogus"))


def test_deadline_invalid():
    with _raises(ph.REFUSAL_DEADLINE_INVALID):
        ph.account_margin(_token_obs(5000), **_margin_kwargs(deadline_at=0))


def test_attended_flag_invalid():
    with _raises(ph.REFUSAL_FLAG_INVALID):
        ph.account_margin(_token_obs(5000), **_margin_kwargs(attended="yes"))


def test_deadline_in_past():
    with _raises(ph.REFUSAL_DEADLINE_IN_PAST):
        ph.account_margin(
            _token_obs(5000),
            **_margin_kwargs(deadline_at=1000, now=1000),
        )


def test_max_age_invalid():
    obs = ph.server_probe_observation(expires_at=5000, observed_at=1000)
    with _raises(ph.REFUSAL_MAX_AGE_INVALID):
        ph.account_margin(
            obs,
            **_margin_kwargs(deadline_at=3000, now=2000, server_probe_max_age=0),
        )


def test_covered_disposition():
    result = ph.account_margin(_token_obs(5000), **_margin_kwargs())
    assert result["ok"] is True
    assert result["disposition"] == "covered"
    assert result["requiresMidWaveRecheck"] is False


# --- malformed input census ---


def _public_callables():
    names = []
    for name in dir(ph):
        if name.startswith("_"):
            continue
        obj = getattr(ph, name)
        if inspect.isclass(obj):
            continue
        if callable(obj):
            names.append(name)
    return names


@pytest.mark.parametrize("name", _public_callables())
def test_public_entry_points_never_leak_builtin_exceptions(name):
    fn = getattr(ph, name)
    sig = inspect.signature(fn)
    for hostile in HOSTILE_VALUES:
        try:
            if name == "parse_instant":
                fn(hostile)
            elif name == "cookie_expiry_observation":
                if hostile == {}:
                    fn(hostile, cookie_name="x")
                elif isinstance(hostile, dict) and "cookies" in hostile:
                    fn(hostile, cookie_name="x")
                else:
                    state = _cookie_state(hostile if isinstance(hostile, (int, float)) else 5000)
                    if isinstance(hostile, (int, float)):
                        state["cookies"][0]["expires"] = hostile
                    fn(state, cookie_name="session")
            elif name == "token_claim_observation":
                fn(hostile)
            elif name == "server_probe_observation":
                fn(expires_at=hostile, observed_at=hostile)
            elif name == "unknown_observation":
                if hostile is not None:
                    fn(hostile)
                else:
                    fn()
            elif name == "validate_observation":
                fn(hostile)
            elif name == "account_margin":
                fn(hostile, **_margin_kwargs())
            elif name == "wave_margin":
                fn(hostile, hostile, **_margin_kwargs())
            else:
                raise AssertionError("unrecognized public callable: %s" % name)
        except ph.PilotHorizonError:
            pass
        except TypeError:
            if name == "unknown_observation":
                pass
            else:
                raise
        except Exception as exc:
            if type(exc).__name__ in (
                "TypeError",
                "ValueError",
                "KeyError",
                "AttributeError",
            ):
                raise AssertionError(
                    "%s leaked %s on %r" % (name, type(exc).__name__, hostile)
                )
            raise
