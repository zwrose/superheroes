"""Tests for pilot_contract validator and declare-and-exercise registry."""
import copy
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_contract as pc  # noqa: E402
import pilot_probe  # noqa: E402


def valid_pilot_block():
    """Return a fresh deep copy of a valid pilot block."""
    return copy.deepcopy({
        "schemaVersion": 1,
        "signInPath": "captured",
        "credentialSet": [
            {"account": "owner", "role": "resource-owner"},
            {"account": "guest", "role": "share-recipient"},
        ],
        "captureSurface": ["cookies", "localStorage"],
        "captureOptions": {"indexedDB": False, "credentials": False},
        "validityProvenance": "server-probe",
        "identityProbe": {"path": "/api/me", "unseededExpectation": "no-session"},
        "cleanup": {
            "command": ["npm", "run", "fixtures:clean", "--", "--namespace", "{namespace}"],
        },
        "administrativeMax": 4,
        "effectsEscape": {
            "canEscape": False,
            "evidence": "dev mail capture + sandboxed outbound calls",
        },
        "policyRef": {"declaration": "example-project-pilot-policy"},
        "mint": {
            "envelope": {
                "enablingFlagEnvVar": "ALLOW_TEST_MINT",
                "enabledScopes": ["development"],
                "forbiddenScopes": ["production", "staging"],
                "gateOffTestCommand": ["npm", "run", "test:mint-gate-off"],
            },
            "sentinelIdentifier": "pilot-sentinel-no-such-account",
        },
    })


def _assert_refusal(mutator, reason, path_fragment=None):
    block = valid_pilot_block()
    mutator(block)
    with pytest.raises(pc.PilotContractError) as excinfo:
        pc.validate_pilot_block(block)
    assert excinfo.value.reason == reason
    if path_fragment is not None:
        assert path_fragment in excinfo.value.path


def test_valid_block_passes():
    pc.validate_pilot_block(valid_pilot_block())


def test_validate_config_no_pilot_key_is_noop():
    pc.validate_config({"schemaVersion": 1, "protectedTargets": ["main"]})


def test_validate_config_with_valid_pilot():
    cfg = {"schemaVersion": 1, "pilot": valid_pilot_block()}
    pc.validate_config(cfg)


def test_cfg_not_mapping():
    with pytest.raises(pc.PilotContractError) as excinfo:
        pc.validate_config("not-a-mapping")
    assert excinfo.value.reason == pc.REFUSAL_UNKNOWN_FIELD


def test_pilot_not_mapping():
    with pytest.raises(pc.PilotContractError) as excinfo:
        pc.validate_config({"pilot": []})
    assert excinfo.value.reason == pc.REFUSAL_UNKNOWN_FIELD


def test_empty_pilot_block_schema_version_absent():
    with pytest.raises(pc.PilotContractError) as excinfo:
        pc.validate_pilot_block({})
    assert excinfo.value.reason == pc.REFUSAL_SCHEMA_VERSION_UNSUPPORTED


def test_schema_version_zero():
    _assert_refusal(lambda b: b.update({"schemaVersion": 0}), pc.REFUSAL_SCHEMA_VERSION_UNSUPPORTED)


def test_schema_version_two():
    _assert_refusal(lambda b: b.update({"schemaVersion": 2}), pc.REFUSAL_SCHEMA_VERSION_UNSUPPORTED)


def test_schema_version_string():
    _assert_refusal(lambda b: b.update({"schemaVersion": "1"}), pc.REFUSAL_SCHEMA_VERSION_UNSUPPORTED)


def test_sign_in_path_invalid():
    _assert_refusal(lambda b: b.update({"signInPath": "oauth"}), pc.REFUSAL_SIGN_IN_PATH_INVALID)


def test_credential_set_absent():
    _assert_refusal(lambda b: b.pop("credentialSet"), pc.REFUSAL_CREDENTIAL_SET_EMPTY)


def test_credential_set_empty():
    _assert_refusal(lambda b: b.update({"credentialSet": []}), pc.REFUSAL_CREDENTIAL_SET_EMPTY)


def test_credential_set_invalid_entry():
    _assert_refusal(
        lambda b: b.update({"credentialSet": ["not-an-object"]}),
        pc.REFUSAL_CREDENTIAL_SET_INVALID,
    )


def test_account_key_invalid():
    _assert_refusal(
        lambda b: b["credentialSet"][0].update({"account": ""}),
        pc.REFUSAL_ACCOUNT_KEY_INVALID,
    )


def test_account_role_missing():
    _assert_refusal(
        lambda b: b["credentialSet"][0].pop("role"),
        pc.REFUSAL_ACCOUNT_ROLE_MISSING,
    )


def test_account_key_duplicate():
    def mutate(block):
        block["credentialSet"].append(
            {"account": "owner", "role": "duplicate-role"},
        )

    _assert_refusal(mutate, pc.REFUSAL_ACCOUNT_KEY_DUPLICATE)


def test_expected_identity_inline_refused():
    _assert_refusal(
        lambda b: b["credentialSet"][0].update({"expectedIdentity": "owner@example.com"}),
        pc.REFUSAL_EXPECTED_IDENTITY_INLINE_REFUSED,
    )


def test_capture_surface_session_storage():
    _assert_refusal(
        lambda b: (
            b.update({"captureSurface": ["sessionStorage"]}),
            b.update({"captureOptions": {"indexedDB": False, "credentials": False}}),
        ),
        pc.REFUSAL_CAPTURE_SURFACE_SESSION_STORAGE,
    )


def test_capture_surface_indexed_db_without_option():
    def mutate(block):
        block["captureSurface"] = ["indexedDB"]
        block["captureOptions"] = {"indexedDB": False, "credentials": False}

    _assert_refusal(mutate, pc.REFUSAL_CAPTURE_OPTIONS_MISMATCH)


def test_capture_options_credentials_without_webauthn():
    def mutate(block):
        block["captureOptions"] = {"indexedDB": False, "credentials": True}

    _assert_refusal(mutate, pc.REFUSAL_CAPTURE_OPTIONS_MISMATCH)


def test_unseeded_expectation_unknown():
    _assert_refusal(
        lambda b: b["identityProbe"].update({"unseededExpectation": "nosession"}),
        pc.REFUSAL_IDENTITY_PROBE_EXPECTATION_UNKNOWN,
    )


def test_cleanup_command_empty():
    _assert_refusal(
        lambda b: b["cleanup"].update({"command": []}),
        pc.REFUSAL_CLEANUP_COMMAND_INVALID,
    )


def test_cleanup_unparameterized():
    _assert_refusal(
        lambda b: b["cleanup"].update({"command": ["npm", "run", "clean"]}),
        pc.REFUSAL_CLEANUP_UNPARAMETERIZED,
    )


def test_cleanup_placeholder_in_argv0():
    _assert_refusal(
        lambda b: b["cleanup"].update({"command": ["{namespace}", "run"]}),
        pc.REFUSAL_CLEANUP_PLACEHOLDER_IN_ARGV0,
    )


def test_administrative_max_zero():
    _assert_refusal(
        lambda b: b.update({"administrativeMax": 0}),
        pc.REFUSAL_ADMINISTRATIVE_MAX_INVALID,
    )


def test_administrative_max_true():
    _assert_refusal(
        lambda b: b.update({"administrativeMax": True}),
        pc.REFUSAL_ADMINISTRATIVE_MAX_INVALID,
    )


def test_administrative_max_string():
    _assert_refusal(
        lambda b: b.update({"administrativeMax": "4"}),
        pc.REFUSAL_ADMINISTRATIVE_MAX_INVALID,
    )


def test_effects_escape_absent():
    _assert_refusal(
        lambda b: b.pop("effectsEscape"),
        pc.REFUSAL_EFFECTS_ESCAPE_ABSENT,
    )


def test_effects_escape_can_escape_int():
    _assert_refusal(
        lambda b: b["effectsEscape"].update({"canEscape": 1}),
        pc.REFUSAL_EFFECTS_ESCAPE_INVALID,
    )


def test_effects_escape_evidence_empty():
    _assert_refusal(
        lambda b: b["effectsEscape"].update({"evidence": ""}),
        pc.REFUSAL_EFFECTS_ESCAPE_EVIDENCE_MISSING,
    )


def test_policy_ref_absent():
    _assert_refusal(lambda b: b.pop("policyRef"), pc.REFUSAL_POLICY_REF_MISSING)


def test_sign_in_path_minted_without_mint():
    def mutate(block):
        block["signInPath"] = "minted"
        block.pop("mint")

    _assert_refusal(mutate, pc.REFUSAL_MINT_DECLARATION_MISSING)


def test_mintable_accounts_inline_refused():
    _assert_refusal(
        lambda b: b["mint"].update({"mintableAccounts": ["owner"]}),
        pc.REFUSAL_MINTABLE_ALLOWLIST_INLINE_REFUSED,
    )


def test_mint_envelope_scope_conflict():
    def mutate(block):
        block["mint"]["envelope"]["forbiddenScopes"].append("development")

    _assert_refusal(mutate, pc.REFUSAL_MINT_ENVELOPE_SCOPE_CONFLICT)


def test_unknown_top_level_field():
    _assert_refusal(
        lambda b: b.update({"effectsEscpae": True}),
        pc.REFUSAL_UNKNOWN_FIELD,
    )


def test_unknown_nested_mint_envelope_field():
    _assert_refusal(
        lambda b: b["mint"]["envelope"].update({"extraScope": "staging"}),
        pc.REFUSAL_UNKNOWN_FIELD,
    )


def test_supports_unattended_horizon_unknown():
    assert pc.supports_unattended_horizon("unknown") is False


def test_supports_unattended_horizon_server_probe():
    assert pc.supports_unattended_horizon("server-probe") is True


def test_supports_unattended_horizon_invalid_raises():
    with pytest.raises(ValueError):
        pc.supports_unattended_horizon("bogus")


def test_declaration_digest_stable():
    declaration = {"path": "/api/me", "unseededExpectation": pilot_probe.REASON_NO_SESSION}
    assert pc.declaration_digest(declaration) == pc.declaration_digest(declaration)


def test_is_exercised_none_registry():
    declaration = {"path": "/api/me"}
    assert pc.is_exercised(None, "identity-probe", declaration) is False


def test_is_exercised_empty_registry():
    declaration = {"path": "/api/me"}
    assert pc.is_exercised({}, "identity-probe", declaration) is False


def test_is_exercised_records_not_list():
    declaration = {"path": "/api/me"}
    assert pc.is_exercised({"records": {}}, "identity-probe", declaration) is False


def test_is_exercised_stale_digest():
    declaration = {"path": "/api/me", "unseededExpectation": "no-session"}
    registry = {
        "schemaVersion": 1,
        "records": [{
            "kind": "identity-probe",
            "declarationDigest": "deadbeefdeadbeef",
            "exercisedAt": "2026-08-02T04:00:00Z",
            "receipt": {"result": "pass", "evidence": "ok"},
        }],
    }
    assert pc.is_exercised(registry, "identity-probe", declaration) is False


def test_is_exercised_receipt_fail():
    declaration = {"path": "/api/me", "unseededExpectation": "no-session"}
    digest = pc.declaration_digest(declaration)
    registry = {
        "schemaVersion": 1,
        "records": [{
            "kind": "identity-probe",
            "declarationDigest": digest,
            "exercisedAt": "2026-08-02T04:00:00Z",
            "receipt": {"result": "fail", "evidence": "failed"},
        }],
    }
    assert pc.is_exercised(registry, "identity-probe", declaration) is False


def test_is_exercised_empty_evidence():
    declaration = {"path": "/api/me", "unseededExpectation": "no-session"}
    digest = pc.declaration_digest(declaration)
    registry = {
        "schemaVersion": 1,
        "records": [{
            "kind": "identity-probe",
            "declarationDigest": digest,
            "exercisedAt": "2026-08-02T04:00:00Z",
            "receipt": {"result": "pass", "evidence": ""},
        }],
    }
    assert pc.is_exercised(registry, "identity-probe", declaration) is False


def test_is_exercised_matching_record():
    declaration = {"path": "/api/me", "unseededExpectation": "no-session"}
    digest = pc.declaration_digest(declaration)
    registry = {
        "schemaVersion": 1,
        "records": [{
            "kind": "identity-probe",
            "declarationDigest": digest,
            "exercisedAt": "2026-08-02T04:00:00Z",
            "receipt": {"result": "pass", "evidence": "seeded returned identity"},
        }],
    }
    assert pc.is_exercised(registry, "identity-probe", declaration) is True


def test_require_exercised_raises_when_absent():
    declaration = {"path": "/api/me"}
    with pytest.raises(pc.PilotContractError) as excinfo:
        pc.require_exercised({}, "identity-probe", declaration)
    assert excinfo.value.reason == pc.REFUSAL_DECLARATION_UNEXERCISED


def test_is_exercised_unknown_kind():
    with pytest.raises(pc.PilotContractError) as excinfo:
        pc.is_exercised({}, "not-a-kind", {})
    assert excinfo.value.reason == pc.REFUSAL_DECLARATION_KIND_UNKNOWN


def test_require_exercised_unknown_kind():
    with pytest.raises(pc.PilotContractError) as excinfo:
        pc.require_exercised({}, "not-a-kind", {})
    assert excinfo.value.reason == pc.REFUSAL_DECLARATION_KIND_UNKNOWN
