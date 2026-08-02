# Stand-ins for pilot_boundary and pilot_policy exist because sibling modules land in
# parallel work orders; the orchestrator re-runs the whole suite against the real
# modules after integration.
"""Tests for pilot_provision.py — boundary verification and credential authorization."""
import hashlib
import inspect
import os
import sys
import tempfile
import types
from unittest import mock

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_contract  # noqa: E402
import pilot_seed  # noqa: E402
import pilot_slot  # noqa: E402

# --- stand-in infrastructure -------------------------------------------------

BOUNDARY_SCHEMA_VERSION = 1
CALL_LOG = []
ORDER_LOG = []

REFUSAL_UNVERIFIED = "boundary-unverified"
REFUSAL_DATASTORE_IDENTITY_UNAVAILABLE = "boundary-datastore-identity-unavailable"
REFUSAL_DATASTORE_OBSERVER_FAILED = "boundary-datastore-observer-failed"
REFUSAL_MATERIAL_IN_RESULT = "policy-material-in-result"

_boundary_config = {}
_policy_config = {}


class PilotBoundaryError(Exception):
    def __init__(self, reason, detail=None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


class PilotPolicyError(Exception):
    def __init__(self, reason, detail=None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _reset_standins():
    CALL_LOG.clear()
    ORDER_LOG.clear()
    _boundary_config.clear()
    _policy_config.clear()


def _record(name):
    CALL_LOG.append(name)
    ORDER_LOG.append(name)


def _standin_target_binding(slot_ref, *, origin, permitted_redirects, protected_targets):
    _record("target_binding")
    slot, generation = pilot_slot.parse_slot_ref(slot_ref)
    return {
        "slotRef": pilot_slot.format_slot_ref(slot, generation),
        "origin": origin,
        "permittedRedirects": list(permitted_redirects),
        "protectedTargets": list(protected_targets),
    }


def _standin_check_target(binding, url):
    _record("check_target")
    handler = _boundary_config.get("check_target")
    if handler:
        return handler(binding, url)
    if url == binding["origin"]:
        return {"ok": True, "reason": None}
    return {"ok": False, "reason": "boundary-target-off-allowlist"}


def _standin_check_redirect(binding, url):
    _record("check_redirect")
    handler = _boundary_config.get("check_redirect")
    if handler:
        return handler(binding, url)
    allowed = {binding["origin"]} | set(binding["permittedRedirects"])
    if url in allowed:
        return {"ok": True, "reason": None}
    return {"ok": False, "reason": "boundary-redirect-off-allowlist"}


def _standin_observe_datastore_identity(
    observer,
    *,
    connection_detail,
    reach_roots,
    run_cwd,
    timeout_seconds=20,
    max_output_bytes=4096,
):
    _record("observe_datastore_identity")
    handler = _boundary_config.get("observe_datastore_identity")
    if handler:
        return handler(
            observer,
            connection_detail=connection_detail,
            reach_roots=reach_roots,
            run_cwd=run_cwd,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
        )
    return {
        "identity": "example_dev",
        "provenance": "observed",
        "strength": "strong",
        "weaker": False,
    }


def _standin_app_reported_identity(value):
    _record("app_reported_identity")
    if not isinstance(value, str) or not value:
        raise PilotBoundaryError(REFUSAL_DATASTORE_IDENTITY_UNAVAILABLE)
    return {
        "identity": value,
        "provenance": "app-reported",
        "strength": "weaker",
        "weaker": True,
    }


def _standin_check_datastore_identity(binding, observation, expected_identity):
    _record("check_datastore_identity")
    handler = _boundary_config.get("check_datastore_identity")
    if handler:
        return handler(binding, observation, expected_identity)
    match = observation["identity"] == expected_identity
    return {
        "ok": match,
        "reason": None if match else "boundary-datastore-identity-mismatch",
        "provenance": observation["provenance"],
        "strength": observation["strength"],
        "match": match,
    }


def _standin_boundary_verdict(
    binding,
    *,
    checks,
    policy_digest,
    datastore_identity=None,
    verified_at=None,
):
    _record("boundary_verdict")
    check_entries = []
    first_reason = None
    all_ok = True
    for name, result in checks:
        ok = result["ok"]
        if not ok and first_reason is None:
            first_reason = result.get("reason")
        if not ok:
            all_ok = False
        check_entries.append(
            {
                "check": name,
                "result": "pass" if ok else "refuse",
                "reason": result.get("reason"),
            },
        )
    return {
        "schemaVersion": BOUNDARY_SCHEMA_VERSION,
        "slotRef": binding["slotRef"],
        "result": "pass" if all_ok else "refuse",
        "reason": first_reason,
        "checks": check_entries,
        "datastoreIdentity": datastore_identity,
        "policyDigest": policy_digest,
        "verifiedAt": verified_at or "2026-01-01T00:00:00Z",
    }


def _standin_authorize_credentials(verdict, slot_ref, policy_digest):
    _record("authorize_credentials")
    if not isinstance(verdict, dict):
        raise PilotBoundaryError(REFUSAL_UNVERIFIED)
    if verdict.get("schemaVersion") != BOUNDARY_SCHEMA_VERSION:
        raise PilotBoundaryError(REFUSAL_UNVERIFIED)
    if verdict.get("result") != "pass":
        raise PilotBoundaryError(REFUSAL_UNVERIFIED)
    canonical = pilot_slot.format_slot_ref(*pilot_slot.parse_slot_ref(slot_ref))
    if verdict.get("slotRef") != canonical:
        raise PilotBoundaryError(REFUSAL_UNVERIFIED)
    if (
        not isinstance(policy_digest, str)
        or not policy_digest
        or verdict.get("policyDigest") != policy_digest
    ):
        raise PilotBoundaryError(REFUSAL_UNVERIFIED)
    return {
        "slotRef": canonical,
        "policyDigest": policy_digest,
        "authorized": True,
    }


def _standin_policy_material(policy):
    _record("policy_material")
    handler = _policy_config.get("policy_material")
    if handler:
        return handler(policy)
    expected = []
    mintable = []
    for slot_cfg in policy.get("slots", {}).values():
        expected.extend(slot_cfg.get("expectedIdentities", {}).values())
        mintable.extend(slot_cfg.get("mintableAccounts", []))
    ds = policy.get("datastore", {})
    connection = [ds.get("connectionDetail", "")]
    return {
        "expected-identity": sorted(set(expected)),
        "mintable-account": sorted(set(mintable)),
        "connection-detail": sorted(set(connection)),
    }


def _standin_assert_results_only(result, material):
    _record("assert_results_only")
    handler = _policy_config.get("assert_results_only")
    if handler:
        return handler(result, material)
    import json

    serialized = json.dumps(result, sort_keys=True, ensure_ascii=False)
    for material_class, strings in material.items():
        for value in strings:
            if value and value in serialized:
                raise PilotPolicyError(REFUSAL_MATERIAL_IN_RESULT, detail=material_class)


_pilot_boundary = types.ModuleType("pilot_boundary")
_pilot_boundary.BOUNDARY_SCHEMA_VERSION = BOUNDARY_SCHEMA_VERSION
_pilot_boundary.REFUSAL_DATASTORE_IDENTITY_UNAVAILABLE = REFUSAL_DATASTORE_IDENTITY_UNAVAILABLE
_pilot_boundary.REFUSAL_DATASTORE_OBSERVER_FAILED = REFUSAL_DATASTORE_OBSERVER_FAILED
_pilot_boundary.REFUSAL_UNVERIFIED = REFUSAL_UNVERIFIED
_pilot_boundary.PilotBoundaryError = PilotBoundaryError
_pilot_boundary.target_binding = _standin_target_binding
_pilot_boundary.check_target = _standin_check_target
_pilot_boundary.check_redirect = _standin_check_redirect
_pilot_boundary.observe_datastore_identity = _standin_observe_datastore_identity
_pilot_boundary.app_reported_identity = _standin_app_reported_identity
_pilot_boundary.check_datastore_identity = _standin_check_datastore_identity
_pilot_boundary.boundary_verdict = _standin_boundary_verdict
_pilot_boundary.authorize_credentials = _standin_authorize_credentials

_pilot_policy = types.ModuleType("pilot_policy")
_pilot_policy.REFUSAL_MATERIAL_IN_RESULT = REFUSAL_MATERIAL_IN_RESULT
_pilot_policy.PilotPolicyError = PilotPolicyError
_pilot_policy.policy_material = _standin_policy_material
_pilot_policy.assert_results_only = _standin_assert_results_only

sys.modules["pilot_boundary"] = _pilot_boundary
sys.modules["pilot_policy"] = _pilot_policy

import pilot_provision as pp  # noqa: E402


# --- fixtures ----------------------------------------------------------------

SAMPLE_POLICY = {
    "schemaVersion": 1,
    "declaration": "test-policy",
    "protectedTargets": ["https://app.example.com:443", "example_prod"],
    "datastore": {
        "expectedIdentity": "example_dev",
        "connectionDetail": "postgres://localhost:5432/example_dev",
        "observer": None,
    },
    "slots": {
        "slot-a": {
            "origin": "http://127.0.0.1:5173",
            "permittedRedirects": ["http://127.0.0.1:5173"],
            "expectedIdentities": {"owner": "pilot-owner@example.test"},
            "mintableAccounts": ["pilot-owner"],
        },
    },
}


@pytest.fixture(autouse=True)
def _reset():
    _reset_standins()
    yield
    _reset_standins()


def _digest(policy):
    return pilot_contract.declaration_digest(policy)


def _passing_verdict(policy, slot_ref="slot-a@1"):
    return {
        "schemaVersion": BOUNDARY_SCHEMA_VERSION,
        "slotRef": pilot_slot.format_slot_ref(*pilot_slot.parse_slot_ref(slot_ref)),
        "result": "pass",
        "reason": None,
        "checks": [],
        "datastoreIdentity": None,
        "policyDigest": _digest(policy),
        "verifiedAt": "2026-01-01T00:00:00Z",
    }


def _write_artifact_dir():
    artifact_dir = tempfile.mkdtemp(dir="/private/tmp")
    artifact_path = os.path.join(artifact_dir, "seed.bin")
    content = b"artifact-bytes"
    with open(artifact_path, "wb") as handle:
        handle.write(content)
    os.chmod(artifact_path, 0o600)
    digest = hashlib.sha256(content).hexdigest()
    return artifact_path, digest


# --- policy_digest -----------------------------------------------------------

def test_policy_digest_matches_contract():
    assert pp.policy_digest(SAMPLE_POLICY) == _digest(SAMPLE_POLICY)


# --- verify_boundary pass path -----------------------------------------------

def test_verify_boundary_pass_with_observer(tmp_path):
    policy = dict(SAMPLE_POLICY)
    policy = {
        **policy,
        "datastore": {
            **policy["datastore"],
            "observer": {
                "command": ["/opt/pilot/db-identity"],
                "connectionEnvVar": "PILOT_DB_URL",
            },
        },
    }
    verdict = pp.verify_boundary(
        policy,
        "slot-a@1",
        "http://127.0.0.1:5173",
        reach_roots=[str(tmp_path)],
        run_cwd=str(tmp_path),
    )
    assert verdict["result"] == "pass"
    assert verdict["policyDigest"] == _digest(policy)
    assert "observe_datastore_identity" in CALL_LOG
    assert "app_reported_identity" not in CALL_LOG
    assert ORDER_LOG.index("target_binding") < ORDER_LOG.index("boundary_verdict")
    assert ORDER_LOG.index("assert_results_only") == len(ORDER_LOG) - 1


def test_verify_boundary_redirect_checks_one_per_candidate_in_order(tmp_path):
    policy = dict(SAMPLE_POLICY)
    policy["datastore"] = {
        **policy["datastore"],
        "observer": {
            "command": ["/opt/pilot/db-identity"],
            "connectionEnvVar": "PILOT_DB_URL",
        },
    }
    redirects = [
        "http://127.0.0.1:5173",
        "http://evil.example.com:80",
        "http://127.0.0.1:5173",
    ]
    redirect_calls = []

    def track_redirect(binding, url):
        redirect_calls.append(url)
        allowed = {binding["origin"]} | set(binding["permittedRedirects"])
        if url in allowed:
            return {"ok": True, "reason": None}
        return {"ok": False, "reason": "boundary-redirect-off-allowlist"}

    _boundary_config["check_redirect"] = track_redirect

    verdict = pp.verify_boundary(
        policy,
        "slot-a@1",
        "http://127.0.0.1:5173",
        reach_roots=[str(tmp_path)],
        run_cwd=str(tmp_path),
        candidate_redirects=redirects,
    )
    assert redirect_calls == redirects
    redirect_checks = [
        c for c in verdict["checks"] if c["check"] == "redirect-binding"
    ]
    assert len(redirect_checks) == 3
    assert redirect_checks[0]["result"] == "pass"
    assert redirect_checks[1]["result"] == "refuse"
    assert redirect_checks[2]["result"] == "pass"
    assert verdict["result"] == "refuse"
    assert verdict["reason"] == "boundary-redirect-off-allowlist"


# --- fail-closed edges -------------------------------------------------------

def test_edge1_refused_verdict_raises_before_seed(tmp_path):
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    verdict["result"] = "refuse"
    artifact_path, digest = _write_artifact_dir()
    artifact = {
        "path": artifact_path,
        "expectedUid": os.getuid(),
        "expectedMode": 0o600,
        "sha256": digest,
        "captureSurfaces": ["cookies"],
    }
    with mock.patch.object(pilot_seed, "seed_request", wraps=pilot_seed.seed_request) as seed_mock:
        with pytest.raises(PilotBoundaryError) as exc:
            pp.authorized_seed_request(
                verdict,
                policy,
                "slot-a@1",
                "owner",
                artifact,
            )
        seed_mock.assert_not_called()
    assert exc.value.reason == REFUSAL_UNVERIFIED
    assert "authorize_credentials" in ORDER_LOG
    assert "seed_request" not in [c for c in ORDER_LOG]


def test_edge2_verdict_bound_to_different_slot_raises(tmp_path):
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy, slot_ref="slot-b@1")
    artifact_path, digest = _write_artifact_dir()
    artifact = {
        "path": artifact_path,
        "expectedUid": os.getuid(),
        "expectedMode": 0o600,
        "sha256": digest,
        "captureSurfaces": ["cookies"],
    }
    with mock.patch.object(pilot_seed, "seed_request", wraps=pilot_seed.seed_request) as seed_mock:
        with pytest.raises(PilotBoundaryError) as exc:
            pp.authorized_seed_request(
                verdict,
                policy,
                "slot-a@1",
                "owner",
                artifact,
            )
        seed_mock.assert_not_called()
    assert exc.value.reason == REFUSAL_UNVERIFIED


def test_edge3_policy_digest_mismatch_raises(tmp_path):
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    tampered = dict(policy)
    tampered["declaration"] = "tampered-policy"
    artifact_path, digest = _write_artifact_dir()
    artifact = {
        "path": artifact_path,
        "expectedUid": os.getuid(),
        "expectedMode": 0o600,
        "sha256": digest,
        "captureSurfaces": ["cookies"],
    }
    with mock.patch.object(pilot_seed, "seed_request", wraps=pilot_seed.seed_request) as seed_mock:
        with pytest.raises(PilotBoundaryError) as exc:
            pp.authorized_seed_request(
                verdict,
                tampered,
                "slot-a@1",
                "owner",
                artifact,
            )
        seed_mock.assert_not_called()
    assert exc.value.reason == REFUSAL_UNVERIFIED


def test_edge4_observer_failure_becomes_refused_check_not_app_reported(tmp_path):
    policy = dict(SAMPLE_POLICY)
    policy["datastore"] = {
        **policy["datastore"],
        "observer": {
            "command": ["/opt/pilot/db-identity"],
            "connectionEnvVar": "PILOT_DB_URL",
        },
    }

    def failing_observer(*_args, **_kwargs):
        raise PilotBoundaryError(REFUSAL_DATASTORE_OBSERVER_FAILED)

    _boundary_config["observe_datastore_identity"] = failing_observer

    verdict = pp.verify_boundary(
        policy,
        "slot-a@1",
        "http://127.0.0.1:5173",
        reach_roots=[str(tmp_path)],
        run_cwd=str(tmp_path),
        app_reported="should-not-be-used",
    )
    assert "app_reported_identity" not in CALL_LOG
    ds_checks = [c for c in verdict["checks"] if c["check"] == "datastore-identity"]
    assert len(ds_checks) == 1
    assert ds_checks[0]["result"] == "refuse"
    assert ds_checks[0]["reason"] == REFUSAL_DATASTORE_OBSERVER_FAILED
    assert verdict["result"] == "refuse"


def test_edge5_no_observer_no_app_reported_refused(tmp_path):
    policy = dict(SAMPLE_POLICY)
    policy["datastore"] = {**policy["datastore"], "observer": None}
    verdict = pp.verify_boundary(
        policy,
        "slot-a@1",
        "http://127.0.0.1:5173",
        reach_roots=[str(tmp_path)],
        run_cwd=str(tmp_path),
    )
    ds_checks = [c for c in verdict["checks"] if c["check"] == "datastore-identity"]
    assert ds_checks[0]["result"] == "refuse"
    assert ds_checks[0]["reason"] == REFUSAL_DATASTORE_IDENTITY_UNAVAILABLE
    assert verdict["result"] == "refuse"


def test_edge6_no_observer_app_reported_recorded_weaker(tmp_path):
    policy = dict(SAMPLE_POLICY)
    policy["datastore"] = {**policy["datastore"], "observer": None}
    verdict = pp.verify_boundary(
        policy,
        "slot-a@1",
        "http://127.0.0.1:5173",
        reach_roots=[str(tmp_path)],
        run_cwd=str(tmp_path),
        app_reported="example_dev",
    )
    assert "app_reported_identity" in CALL_LOG
    assert verdict["datastoreIdentity"] == {
        "provenance": "app-reported",
        "strength": "weaker",
        "match": True,
    }
    ds_checks = [c for c in verdict["checks"] if c["check"] == "datastore-identity"]
    assert ds_checks[0]["result"] == "pass"


def test_edge7_unknown_slot_refused_before_binding():
    policy = SAMPLE_POLICY
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.verify_boundary(
            policy,
            "unknown-slot@1",
            "http://127.0.0.1:5173",
            reach_roots=["/tmp"],
            run_cwd="/tmp",
        )
    assert exc.value.reason == pp.REFUSAL_SLOT_UNKNOWN
    assert "target_binding" not in CALL_LOG


def test_edge8_unknown_account_refused_before_seed_request(tmp_path):
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    artifact_path, digest = _write_artifact_dir()
    artifact = {
        "path": artifact_path,
        "expectedUid": os.getuid(),
        "expectedMode": 0o600,
        "sha256": digest,
        "captureSurfaces": ["cookies"],
    }
    with mock.patch.object(pilot_seed, "seed_request", wraps=pilot_seed.seed_request) as seed_mock:
        with pytest.raises(pp.PilotProvisionError) as exc:
            pp.authorized_seed_request(
                verdict,
                policy,
                "slot-a@1",
                "intruder",
                artifact,
            )
        seed_mock.assert_not_called()
    assert exc.value.reason == pp.REFUSAL_ACCOUNT_UNKNOWN
    assert ORDER_LOG == ["authorize_credentials"]


def test_edge9_no_mintable_accounts_refused(tmp_path):
    policy = dict(SAMPLE_POLICY)
    policy["slots"] = {
        "slot-a": {
            **policy["slots"]["slot-a"],
            "mintableAccounts": [],
        },
    }
    verdict = _passing_verdict(policy)
    envelope = {"enablingFlagEnvVar": "ALLOW_TEST_MINT"}
    with mock.patch.object(pilot_seed, "mint_request", wraps=pilot_seed.mint_request) as mint_mock:
        with pytest.raises(pp.PilotProvisionError) as exc:
            pp.authorized_mint_request(
                verdict,
                policy,
                "slot-a@1",
                "pilot-owner",
                envelope,
            )
        mint_mock.assert_not_called()
    assert exc.value.reason == pp.REFUSAL_MINT_UNSUPPORTED


def test_edge9_absent_mintable_accounts_refused():
    policy = dict(SAMPLE_POLICY)
    slot_cfg = dict(policy["slots"]["slot-a"])
    del slot_cfg["mintableAccounts"]
    policy["slots"] = {"slot-a": slot_cfg}
    verdict = _passing_verdict(policy)
    envelope = {"enablingFlagEnvVar": "ALLOW_TEST_MINT"}
    with mock.patch.object(pilot_seed, "mint_request", wraps=pilot_seed.mint_request) as mint_mock:
        with pytest.raises(pp.PilotProvisionError) as exc:
            pp.authorized_mint_request(
                verdict,
                policy,
                "slot-a@1",
                "pilot-owner",
                envelope,
            )
        mint_mock.assert_not_called()
    assert exc.value.reason == pp.REFUSAL_MINT_UNSUPPORTED


def test_edge10_assert_results_only_raises_verdict_never_leaves(tmp_path):
    policy = dict(SAMPLE_POLICY)
    policy["datastore"] = {
        **policy["datastore"],
        "observer": {
            "command": ["/opt/pilot/db-identity"],
            "connectionEnvVar": "PILOT_DB_URL",
        },
    }

    def raising_assert(_result, _material):
        raise PilotPolicyError(REFUSAL_MATERIAL_IN_RESULT, detail="connection-detail")

    _policy_config["assert_results_only"] = raising_assert

    with pytest.raises(_pilot_policy.PilotPolicyError) as exc:
        pp.verify_boundary(
            policy,
            "slot-a@1",
            "http://127.0.0.1:5173",
            reach_roots=[str(tmp_path)],
            run_cwd=str(tmp_path),
        )
    assert exc.value.reason == REFUSAL_MATERIAL_IN_RESULT
    assert ORDER_LOG[-1] == "assert_results_only"
    assert "boundary_verdict" in ORDER_LOG
    assert ORDER_LOG.index("boundary_verdict") < ORDER_LOG.index("assert_results_only")


# --- authorized_seed_request pass path -----------------------------------------

def test_authorized_seed_request_pass_end_to_end():
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    artifact_path, digest = _write_artifact_dir()
    capture_surfaces = ["indexedDB", "webauthn"]
    artifact = {
        "path": artifact_path,
        "expectedUid": os.getuid(),
        "expectedMode": 0o600,
        "sha256": digest,
        "captureSurfaces": capture_surfaces,
    }
    context_options = pilot_seed.required_context_options(capture_surfaces)
    real_seed = pilot_seed.seed_request

    def track_seed(*args, **kwargs):
        _record("seed_request")
        return real_seed(*args, **kwargs)

    with mock.patch.object(pilot_seed, "seed_request", side_effect=track_seed):
        result = pp.authorized_seed_request(
            verdict,
            policy,
            "slot-a@1",
            "owner",
            artifact,
        )
    assert ORDER_LOG.index("authorize_credentials") < ORDER_LOG.index("seed_request")
    assert result == {
        "slotRef": "slot-a@1",
        "account": "owner",
        "artifact": {"path": artifact_path, "sha256": digest},
        "contextOptions": context_options,
    }


# --- authorized_mint_request allowlist from policy -----------------------------

def test_authorized_mint_request_has_no_allowlist_parameter():
    sig = inspect.signature(pp.authorized_mint_request)
    assert "allowlist" not in sig.parameters


def test_authorized_mint_request_uses_policy_allowlist():
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    envelope = {"enablingFlagEnvVar": "ALLOW_TEST_MINT"}
    mint_calls = []
    real_mint = pilot_seed.mint_request

    def track_mint(account, *, allowlist, envelope):
        _record("mint_request")
        mint_calls.append({"account": account, "allowlist": allowlist, "envelope": envelope})
        return real_mint(account, allowlist=allowlist, envelope=envelope)

    with mock.patch.object(pilot_seed, "mint_request", side_effect=track_mint):
        result = pp.authorized_mint_request(
            verdict,
            policy,
            "slot-a@1",
            "pilot-owner",
            envelope,
        )
    assert mint_calls[0]["allowlist"] == policy["slots"]["slot-a"]["mintableAccounts"]
    assert result == {"account": "pilot-owner", "enablingFlagEnvVar": "ALLOW_TEST_MINT"}
    assert ORDER_LOG.index("authorize_credentials") < ORDER_LOG.index("mint_request")


def test_refused_verdict_never_reaches_mint():
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    verdict["result"] = "refuse"
    envelope = {"enablingFlagEnvVar": "ALLOW_TEST_MINT"}
    with mock.patch.object(pilot_seed, "mint_request", wraps=pilot_seed.mint_request) as mint_mock:
        with pytest.raises(PilotBoundaryError):
            pp.authorized_mint_request(
                verdict,
                policy,
                "slot-a@1",
                "pilot-owner",
                envelope,
            )
        mint_mock.assert_not_called()
