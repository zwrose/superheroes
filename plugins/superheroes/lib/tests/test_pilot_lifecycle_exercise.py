"""Tests for pilot_lifecycle_exercise.py — app-lifecycle navigation trace exercise."""
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_contract  # noqa: E402
import pilot_lifecycle_exercise as ple  # noqa: E402
import pilot_provision as pp  # noqa: E402

APP_ORIGIN = "https://app.example.com"
IDP_ORIGIN = "https://idp.example.com"
OTHER_IDP = "https://other-idp.example.com"
SLOT_REF = "slot-a@1"
POLICY_DIGEST = "abcd1234ef567890"
EXERCISED_AT = "2026-08-07T12:00:00Z"

HOSTILE_VALUES = [
    None,
    [],
    {},
    set(),
    0,
    True,
    "",
    b"x",
    object(),
]


def _sign_in_trace(idp=IDP_ORIGIN):
    return [
        "%s/" % APP_ORIGIN,
        "%s/login?token=secret" % idp,
        "%s/callback?code=abc" % APP_ORIGIN,
    ]


def _declaration(**overrides):
    base = {
        "slot_ref": SLOT_REF,
        "policy_digest": POLICY_DIGEST,
        "origin": APP_ORIGIN,
        "permitted_redirects": [IDP_ORIGIN],
    }
    base.update(overrides)
    return ple.app_lifecycle_declaration(**base)


# --- normalize_origin ---------------------------------------------------------

@pytest.mark.parametrize("value", ["file:///tmp", "javascript:alert(1)", "data:text/plain,x", "app.example.com"])
def test_normalize_origin_refuses_non_http_scheme(value):
    """Edge 1: non-http(s) schemes refuse lifecycle-exercise-origin-invalid."""
    with pytest.raises(ple.PilotLifecycleExerciseError) as exc:
        ple.normalize_origin(value)
    assert exc.value.reason == ple.REFUSAL_ORIGIN_INVALID


@pytest.mark.parametrize("value", HOSTILE_VALUES + [" ", "https://app.example.com\n", "https://app\x00.example.com"])
def test_normalize_origin_refuses_non_string_or_whitespace(value):
    """Edge 2: non-string / empty / whitespace / control chars refuse."""
    with pytest.raises(ple.PilotLifecycleExerciseError) as exc:
        ple.normalize_origin(value)
    assert exc.value.reason == ple.REFUSAL_ORIGIN_INVALID


def test_normalize_origin_strips_default_ports_keeps_non_default():
    """Edge 3: default ports stripped; non-default ports kept."""
    assert ple.normalize_origin("https://a.example:443") == "https://a.example"
    assert ple.normalize_origin("https://a.example") == "https://a.example"
    assert ple.normalize_origin("http://a.example:80") == "http://a.example"
    assert ple.normalize_origin("http://a.example:8080") == "http://a.example:8080"


def test_normalize_origin_lowercases_and_drops_path_query_fragment():
    """Edge 4: scheme/host lowercased; path/query/fragment dropped."""
    assert ple.normalize_origin("HTTPS://APP.EXAMPLE.COM/Path?Q=1#frag") == "https://app.example.com"


@pytest.mark.parametrize("value", [
    "https://app.example:bad",
    "https://app.example:99999",
    "https://[::1",
])
def test_normalize_origin_refuses_malformed_authority(value):
    """Malformed port or IPv6 authority refuses lifecycle-exercise-origin-invalid."""
    with pytest.raises(ple.PilotLifecycleExerciseError) as exc:
        ple.normalize_origin(value)
    assert exc.value.reason == ple.REFUSAL_ORIGIN_INVALID


def test_normalize_origin_accepts_valid_ipv6_with_port():
    """Edge 9: valid IPv6 origin normalizes without refusing."""
    assert ple.normalize_origin("https://[::1]:8443") == "https://[::1]:8443"


@pytest.mark.parametrize("value", [
    "https://app.example:bad",
    "https://app.example:99999",
    "https://[::1",
])
def test_evaluate_trace_malformed_trace_entry_returns_trace_invalid(value):
    """Malformed trace URL returns lifecycle-exercise-trace-invalid, never raises."""
    result = ple.evaluate_trace(
        [APP_ORIGIN, value, APP_ORIGIN],
        origin=APP_ORIGIN,
        permitted_redirects=[IDP_ORIGIN],
    )
    assert result["ok"] is False
    assert result["reason"] == ple.REFUSAL_TRACE_INVALID


def test_evaluate_trace_malformed_permitted_redirect_returns_redirect_invalid():
    """Malformed permitted_redirects member returns redirect-invalid, never raises."""
    result = ple.evaluate_trace(
        [APP_ORIGIN],
        origin=APP_ORIGIN,
        permitted_redirects=["https://app.example:bad"],
    )
    assert result["ok"] is False
    assert result["reason"] == ple.REFUSAL_REDIRECT_INVALID


def test_evaluate_trace_prefix_lookalike_refuses():
    """Edge 5: prefix lookalike refuses lifecycle-exercise-navigation-escaped."""
    trace = [
        APP_ORIGIN,
        "https://app.example.com.evil.test/login",
        APP_ORIGIN,
    ]
    result = ple.evaluate_trace(
        trace,
        origin=APP_ORIGIN,
        permitted_redirects=[IDP_ORIGIN],
    )
    assert result["ok"] is False
    assert result["reason"] == ple.REFUSAL_NAVIGATION_ESCAPED
    assert result["escaped"]["origin"] == "https://app.example.com.evil.test"
    assert result["escaped"]["index"] == 1


@pytest.mark.parametrize("trace", [None, "not-a-list", [APP_ORIGIN, 1]])
def test_evaluate_trace_invalid_shape(trace):
    """Edge 6: trace not a list or containing non-string refuses trace-invalid."""
    result = ple.evaluate_trace(trace, origin=APP_ORIGIN, permitted_redirects=[])
    assert result["ok"] is False
    assert result["reason"] == ple.REFUSAL_TRACE_INVALID


def test_evaluate_trace_empty():
    """Edge 7: empty trace refuses lifecycle-exercise-trace-empty."""
    result = ple.evaluate_trace([], origin=APP_ORIGIN, permitted_redirects=[])
    assert result["ok"] is False
    assert result["reason"] == ple.REFUSAL_TRACE_EMPTY


def test_evaluate_trace_url_fails_normalize_origin():
    """Edge 8: trace URL that fails normalize_origin refuses trace-invalid."""
    result = ple.evaluate_trace(
        [APP_ORIGIN, "not-a-url"],
        origin=APP_ORIGIN,
        permitted_redirects=[],
    )
    assert result["ok"] is False
    assert result["reason"] == ple.REFUSAL_TRACE_INVALID


def test_evaluate_trace_permitted_redirects_not_list():
    """Edge 9: permitted_redirects not a list refuses redirect-invalid."""
    result = ple.evaluate_trace(
        [APP_ORIGIN],
        origin=APP_ORIGIN,
        permitted_redirects="bad",
    )
    assert result["ok"] is False
    assert result["reason"] == ple.REFUSAL_REDIRECT_INVALID


def test_evaluate_trace_invalid_redirect_member():
    """Edge 10: invalid permitted_redirects member refuses redirect-invalid."""
    result = ple.evaluate_trace(
        [APP_ORIGIN],
        origin=APP_ORIGIN,
        permitted_redirects=["javascript:void(0)"],
    )
    assert result["ok"] is False
    assert result["reason"] == ple.REFUSAL_REDIRECT_INVALID


def test_evaluate_trace_empty_redirects_on_origin_only():
    """Edge 11: empty permitted_redirects with origin-only trace passes."""
    result = ple.evaluate_trace(
        [APP_ORIGIN],
        origin=APP_ORIGIN,
        permitted_redirects=[],
    )
    assert result == {
        "ok": True,
        "reason": None,
        "origins": ["https://app.example.com"],
        "escaped": None,
    }


def test_evaluate_trace_unpermitted_origin_escapes():
    """Edge 12: origin in neither set refuses navigation-escaped with origin and index."""
    trace = [APP_ORIGIN, "https://evil.example.com", APP_ORIGIN]
    result = ple.evaluate_trace(
        trace,
        origin=APP_ORIGIN,
        permitted_redirects=[IDP_ORIGIN],
    )
    assert result["ok"] is False
    assert result["reason"] == ple.REFUSAL_NAVIGATION_ESCAPED
    assert result["escaped"] == {"origin": "https://evil.example.com", "index": 1}


def test_evaluate_trace_does_not_start_at_origin():
    """Edge 13: trace not starting at declared origin refuses trace-did-not-return."""
    result = ple.evaluate_trace(
        [IDP_ORIGIN, APP_ORIGIN],
        origin=APP_ORIGIN,
        permitted_redirects=[IDP_ORIGIN],
    )
    assert result["ok"] is False
    assert result["reason"] == ple.REFUSAL_TRACE_DID_NOT_RETURN


def test_evaluate_trace_does_not_return_to_origin():
    """Edge 14: trace ending on IdP refuses trace-did-not-return."""
    result = ple.evaluate_trace(
        [APP_ORIGIN, IDP_ORIGIN],
        origin=APP_ORIGIN,
        permitted_redirects=[IDP_ORIGIN],
    )
    assert result["ok"] is False
    assert result["reason"] == ple.REFUSAL_TRACE_DID_NOT_RETURN


def test_app_lifecycle_declaration_bad_slot():
    """Edge 15: unparseable slot_ref refuses declaration-slot-invalid."""
    with pytest.raises(ple.PilotLifecycleExerciseError) as exc:
        ple.app_lifecycle_declaration(
            slot_ref="bad",
            policy_digest=POLICY_DIGEST,
            origin=APP_ORIGIN,
            permitted_redirects=[],
        )
    assert exc.value.reason == ple.REFUSAL_DECLARATION_SLOT_INVALID


@pytest.mark.parametrize("policy_digest", ["", None, 0])
def test_app_lifecycle_declaration_bad_policy_digest(policy_digest):
    """Edge 16: empty/non-string policy_digest refuses declaration-invalid."""
    with pytest.raises(ple.PilotLifecycleExerciseError) as exc:
        ple.app_lifecycle_declaration(
            slot_ref=SLOT_REF,
            policy_digest=policy_digest,
            origin=APP_ORIGIN,
            permitted_redirects=[],
        )
    assert exc.value.reason == ple.REFUSAL_DECLARATION_INVALID


def test_app_lifecycle_declaration_redirect_order_changes_digest():
    """Redirect order in policy produces different declaration digests (gate does not sort)."""
    decl_a = ple.app_lifecycle_declaration(
        slot_ref=SLOT_REF,
        policy_digest=POLICY_DIGEST,
        origin=APP_ORIGIN,
        permitted_redirects=[IDP_ORIGIN, OTHER_IDP],
    )
    decl_b = ple.app_lifecycle_declaration(
        slot_ref=SLOT_REF,
        policy_digest=POLICY_DIGEST,
        origin=APP_ORIGIN,
        permitted_redirects=[OTHER_IDP, IDP_ORIGIN],
    )
    assert decl_a["declaration"]["permittedRedirects"] == [IDP_ORIGIN, OTHER_IDP]
    assert decl_b["declaration"]["permittedRedirects"] == [OTHER_IDP, IDP_ORIGIN]
    digest_a = pilot_contract.declaration_digest(decl_a["declaration"])
    digest_b = pilot_contract.declaration_digest(decl_b["declaration"])
    assert digest_a != digest_b


@pytest.mark.parametrize("exercised_at", ["", None, 0])
def test_app_lifecycle_receipt_bad_exercised_at(exercised_at):
    """Edge 18: empty/non-string exercised_at refuses receipt-argument-invalid."""
    declaration = _declaration()
    result = ple.evaluate_trace(_sign_in_trace(), origin=APP_ORIGIN, permitted_redirects=[IDP_ORIGIN])
    with pytest.raises(ple.PilotLifecycleExerciseError) as exc:
        ple.app_lifecycle_receipt(declaration, result, exercised_at=exercised_at)
    assert exc.value.reason == ple.REFUSAL_RECEIPT_ARGUMENT_INVALID


def test_app_lifecycle_receipt_forged_result_refused():
    """Edge 19: forged ok result with unpermitted origins refuses receipt-argument-invalid."""
    declaration = _declaration()
    forged = {
        "ok": True,
        "reason": None,
        "origins": ["https://app.example.com", "https://evil.example.com", "https://app.example.com"],
        "escaped": None,
    }
    with pytest.raises(ple.PilotLifecycleExerciseError) as exc:
        ple.app_lifecycle_receipt(declaration, forged, exercised_at=EXERCISED_AT)
    assert exc.value.reason == ple.REFUSAL_RECEIPT_ARGUMENT_INVALID


def test_app_lifecycle_receipt_fail_carries_reason():
    """Edge 20: failing result yields receipt.result == fail with refusal reason."""
    declaration = _declaration()
    result = ple.evaluate_trace(
        [APP_ORIGIN, "https://evil.example.com", APP_ORIGIN],
        origin=APP_ORIGIN,
        permitted_redirects=[IDP_ORIGIN],
    )
    record = ple.app_lifecycle_receipt(declaration, result, exercised_at=EXERCISED_AT)
    assert record["receipt"]["result"] == "fail"
    assert record["receipt"]["evidence"] == ple.REFUSAL_NAVIGATION_ESCAPED


def test_app_lifecycle_receipt_fail_rejects_unpinned_reason():
    """Edge 10: caller reason not in REFUSAL_* tokens is not copied verbatim into evidence."""
    declaration = _declaration()
    forged = {
        "ok": False,
        "reason": "https://idp.example.com/login?token=secret",
        "origins": [],
        "escaped": None,
    }
    record = ple.app_lifecycle_receipt(declaration, forged, exercised_at=EXERCISED_AT)
    assert record["receipt"]["result"] == "fail"
    assert record["receipt"]["evidence"] == ple.EVIDENCE_REFUSAL_UNPINNED
    assert "token=secret" not in record["receipt"]["evidence"]


def test_app_lifecycle_receipt_evidence_never_carries_url_parts():
    """Edge 21: receipt evidence never contains path, query, or fragment."""
    declaration = _declaration()
    trace = _sign_in_trace()
    result = ple.evaluate_trace(trace, origin=APP_ORIGIN, permitted_redirects=[IDP_ORIGIN])
    record = ple.app_lifecycle_receipt(declaration, result, exercised_at=EXERCISED_AT)
    evidence = record["receipt"]["evidence"]
    assert "?" not in evidence
    assert "#" not in evidence
    assert "/login" not in evidence
    assert "/callback" not in evidence
    assert "token=secret" not in evidence


def test_require_app_lifecycle_exercised_propagates():
    """Edge 22: missing registry record refuses pilot-declaration-unexercised."""
    declaration = _declaration()
    with pytest.raises(pilot_contract.PilotContractError) as exc:
        ple.require_app_lifecycle_exercised({}, declaration)
    assert exc.value.reason == pilot_contract.REFUSAL_DECLARATION_UNEXERCISED


# --- positive paths -----------------------------------------------------------

def test_evaluate_trace_sign_in_round_trip():
    result = ple.evaluate_trace(
        _sign_in_trace(),
        origin=APP_ORIGIN,
        permitted_redirects=[IDP_ORIGIN],
    )
    assert result["ok"] is True
    assert result["origins"] == [
        "https://app.example.com",
        "https://idp.example.com",
        "https://app.example.com",
    ]


def test_app_lifecycle_declaration_shape():
    declaration = _declaration()
    assert declaration["slot"] == "slot-a"
    assert declaration["generation"] == 1
    assert declaration["policyDigest"] == POLICY_DIGEST
    assert declaration["declaration"]["origin"] == APP_ORIGIN
    assert declaration["declaration"]["permittedRedirects"] == [IDP_ORIGIN]


def test_app_lifecycle_receipt_pass_round_trip():
    declaration = _declaration()
    result = ple.evaluate_trace(_sign_in_trace(), origin=APP_ORIGIN, permitted_redirects=[IDP_ORIGIN])
    record = ple.app_lifecycle_receipt(declaration, result, exercised_at=EXERCISED_AT)
    registry = {
        "schemaVersion": pilot_contract.REGISTRY_SCHEMA_VERSION,
        "records": [record],
    }
    gate_declaration = declaration["declaration"]
    assert pilot_contract.is_exercised(registry, "app-lifecycle", gate_declaration) is True


def test_app_lifecycle_receipt_matches_pilot_provision_gate_declaration():
    """Integration: receipt digest matches pilot_provision.declaration_for gate declaration."""
    policy = {
        "schemaVersion": 1,
        "declaration": "test-policy",
        "protectedTargets": ["https://app.example.com:443"],
        "datastore": {
            "expectedIdentity": "example_dev",
            "connectionDetail": "postgres://localhost:5432/example_dev",
            "observer": None,
        },
        "slots": {
            "slot-a": {
                "origin": APP_ORIGIN,
                "permittedRedirects": [IDP_ORIGIN],
                "expectedIdentities": {"owner": "pilot-owner@example.test"},
            },
        },
    }
    block = {
        "schemaVersion": 1,
        "signInPath": "attended",
        "attended": {"vehicle": "automation"},
        "credentialSet": [{"account": "owner", "role": "resource-owner"}],
        "captureSurface": ["cookies"],
        "captureOptions": {"indexedDB": False, "credentials": False},
        "validityProvenance": "server-probe",
        "identityProbe": {"path": "/api/me", "unseededExpectation": "no-session"},
        "cleanup": {"command": ["npm", "run", "fixtures:clean"]},
        "administrativeMax": 4,
        "effectsEscape": {"canEscape": False, "evidence": "sandboxed"},
        "policyRef": {"declaration": "example-project-pilot-policy"},
    }
    slot_ref = SLOT_REF
    gate_info = pp.declaration_for("app-lifecycle", block, policy, slot_ref)
    gate_declaration = gate_info["declaration"]
    declaration = ple.app_lifecycle_declaration(
        slot_ref=slot_ref,
        policy_digest=POLICY_DIGEST,
        origin=gate_declaration["origin"],
        permitted_redirects=gate_declaration["permittedRedirects"],
    )
    result = ple.evaluate_trace(
        _sign_in_trace(),
        origin=gate_declaration["origin"],
        permitted_redirects=gate_declaration["permittedRedirects"],
    )
    assert result["ok"] is True
    record = ple.app_lifecycle_receipt(declaration, result, exercised_at=EXERCISED_AT)
    registry = {
        "schemaVersion": pilot_contract.REGISTRY_SCHEMA_VERSION,
        "records": [record],
    }
    assert pilot_contract.is_exercised(registry, "app-lifecycle", gate_declaration) is True


def test_fail_receipt_not_exercised():
    declaration = _declaration()
    result = ple.evaluate_trace(
        [APP_ORIGIN, IDP_ORIGIN],
        origin=APP_ORIGIN,
        permitted_redirects=[IDP_ORIGIN],
    )
    record = ple.app_lifecycle_receipt(declaration, result, exercised_at=EXERCISED_AT)
    registry = {
        "schemaVersion": pilot_contract.REGISTRY_SCHEMA_VERSION,
        "records": [record],
    }
    assert pilot_contract.is_exercised(registry, "app-lifecycle", declaration["declaration"]) is False
