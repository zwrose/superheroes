"""Tests for pilot_provision.py — boundary verification and credential authorization."""
import hashlib
import inspect
import json
import os
import shutil
import stat
import sys
import tempfile

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_boundary  # noqa: E402
import pilot_contract  # noqa: E402
import pilot_policy  # noqa: E402
import pilot_provision as pp  # noqa: E402
import pilot_seed  # noqa: E402
import pilot_slot  # noqa: E402


# --- fixtures ----------------------------------------------------------------

@pytest.fixture
def private_tmp():
    path = tempfile.mkdtemp(dir="/private/tmp")
    yield path
    shutil.rmtree(path, ignore_errors=True)


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


def _digest(policy):
    return pilot_contract.declaration_digest(policy)


def _passing_verdict(policy, slot_ref="slot-a@1"):
    return {
        "schemaVersion": pilot_boundary.BOUNDARY_SCHEMA_VERSION,
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


def _write_policy(policy_root, declaration, doc, *, mode=0o600):
    path = os.path.join(policy_root, declaration + ".json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(doc, handle)
    os.chmod(path, mode)
    return path


def _write_executable(path, content):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    os.chmod(path, stat.S_IMODE(os.stat(path).st_mode) | stat.S_IXUSR)


def _provision_layout(private_tmp):
    """Reach/cwd under private_tmp; observer bin dir sits outside reach roots."""
    reach_root = os.path.join(private_tmp, "reach")
    run_cwd = os.path.join(private_tmp, "cwd")
    bin_dir = os.path.join(private_tmp, "bin")
    policy_root = os.path.join(private_tmp, "policy")
    os.makedirs(reach_root)
    os.makedirs(run_cwd)
    os.makedirs(bin_dir)
    os.makedirs(policy_root)
    return reach_root, run_cwd, bin_dir, policy_root


def _observer_script(bin_dir, identity):
    script = os.path.join(bin_dir, "observer.sh")
    _write_executable(script, f"#!/bin/sh\necho {identity}\n")
    return script


def _policy_with_observer(observer_command, **overrides):
    policy = dict(SAMPLE_POLICY)
    policy["datastore"] = {
        **policy["datastore"],
        "observer": {
            "command": observer_command,
            "connectionEnvVar": "PILOT_DB_URL",
        },
    }
    policy.update(overrides)
    return policy


# --- real module proof -------------------------------------------------------

def test_real_pilot_boundary_module_loaded():
    assert pilot_boundary.__file__.endswith("pilot_boundary.py")
    assert hasattr(pilot_boundary, "parse_origin")


# --- policy_digest -----------------------------------------------------------

def test_policy_digest_matches_contract():
    assert pp.policy_digest(SAMPLE_POLICY) == _digest(SAMPLE_POLICY)


# --- verify_boundary pass path -----------------------------------------------

def test_verify_boundary_pass_with_observer(private_tmp):
    reach_root, run_cwd, bin_dir, _ = _provision_layout(private_tmp)
    script = _observer_script(bin_dir, "example_dev")
    policy = _policy_with_observer([script])
    verdict = pp.verify_boundary(
        policy,
        "slot-a@1",
        "http://127.0.0.1:5173",
        reach_roots=[reach_root],
        run_cwd=run_cwd,
    )
    assert verdict["result"] == "pass"
    assert verdict["policyDigest"] == _digest(policy)
    assert verdict["datastoreIdentity"] == {
        "provenance": "observed",
        "strength": "strong",
        "match": True,
    }


def test_verify_boundary_redirect_checks_one_per_candidate_in_order(private_tmp, monkeypatch):
    reach_root, run_cwd, bin_dir, _ = _provision_layout(private_tmp)
    script = _observer_script(bin_dir, "example_dev")
    policy = _policy_with_observer([script])
    redirects = [
        "http://127.0.0.1:5173",
        "http://evil.example.com:80",
        "http://127.0.0.1:5173",
    ]
    redirect_calls = []
    real_check_redirect = pilot_boundary.check_redirect

    def track_redirect(binding, url):
        redirect_calls.append(url)
        return real_check_redirect(binding, url)

    monkeypatch.setattr(pilot_boundary, "check_redirect", track_redirect)

    verdict = pp.verify_boundary(
        policy,
        "slot-a@1",
        "http://127.0.0.1:5173",
        reach_roots=[reach_root],
        run_cwd=run_cwd,
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
    assert verdict["reason"] == pilot_boundary.REFUSAL_REDIRECT_OFF_ALLOWLIST


# --- fail-closed edges -------------------------------------------------------

def test_edge1_refused_verdict_raises_before_seed(monkeypatch):
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
    seed_calls = []

    def record_seed(*_args, **_kwargs):
        seed_calls.append(True)
        return pilot_seed.seed_request(*_args, **_kwargs)

    monkeypatch.setattr(pilot_seed, "seed_request", record_seed)
    with pytest.raises(pilot_boundary.PilotBoundaryError) as exc:
        pp.authorized_seed_request(
            verdict,
            policy,
            "slot-a@1",
            "owner",
            artifact,
        )
    assert seed_calls == []
    assert exc.value.reason == pilot_boundary.REFUSAL_UNVERIFIED


def test_edge2_verdict_bound_to_different_slot_raises(monkeypatch):
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
    seed_calls = []

    def record_seed(*_args, **_kwargs):
        seed_calls.append(True)

    monkeypatch.setattr(pilot_seed, "seed_request", record_seed)
    with pytest.raises(pilot_boundary.PilotBoundaryError) as exc:
        pp.authorized_seed_request(
            verdict,
            policy,
            "slot-a@1",
            "owner",
            artifact,
        )
    assert seed_calls == []
    assert exc.value.reason == pilot_boundary.REFUSAL_UNVERIFIED


def test_edge3_policy_digest_mismatch_raises(monkeypatch):
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
    seed_calls = []

    def record_seed(*_args, **_kwargs):
        seed_calls.append(True)

    monkeypatch.setattr(pilot_seed, "seed_request", record_seed)
    with pytest.raises(pilot_boundary.PilotBoundaryError) as exc:
        pp.authorized_seed_request(
            verdict,
            tampered,
            "slot-a@1",
            "owner",
            artifact,
        )
    assert seed_calls == []
    assert exc.value.reason == pilot_boundary.REFUSAL_UNVERIFIED


def test_edge4_observer_failure_becomes_refused_check_not_app_reported(
    private_tmp, monkeypatch,
):
    reach_root, run_cwd, bin_dir, _ = _provision_layout(private_tmp)
    script = _observer_script(bin_dir, "example_dev")
    policy = _policy_with_observer([script])
    app_reported_calls = []

    def failing_observer(*_args, **_kwargs):
        raise pilot_boundary.PilotBoundaryError(
            pilot_boundary.REFUSAL_DATASTORE_OBSERVER_FAILED,
        )

    def record_app_reported(*_args, **_kwargs):
        app_reported_calls.append(True)

    monkeypatch.setattr(
        pilot_boundary, "observe_datastore_identity", failing_observer,
    )
    monkeypatch.setattr(
        pilot_boundary, "app_reported_identity", record_app_reported,
    )

    verdict = pp.verify_boundary(
        policy,
        "slot-a@1",
        "http://127.0.0.1:5173",
        reach_roots=[reach_root],
        run_cwd=run_cwd,
        app_reported="should-not-be-used",
    )
    assert app_reported_calls == []
    ds_checks = [c for c in verdict["checks"] if c["check"] == "datastore-identity"]
    assert len(ds_checks) == 1
    assert ds_checks[0]["result"] == "refuse"
    assert ds_checks[0]["reason"] == pilot_boundary.REFUSAL_DATASTORE_OBSERVER_FAILED
    assert verdict["result"] == "refuse"


def test_edge5_no_observer_no_app_reported_refused(private_tmp):
    reach_root, run_cwd, _, _ = _provision_layout(private_tmp)
    policy = dict(SAMPLE_POLICY)
    policy["datastore"] = {**policy["datastore"], "observer": None}
    verdict = pp.verify_boundary(
        policy,
        "slot-a@1",
        "http://127.0.0.1:5173",
        reach_roots=[reach_root],
        run_cwd=run_cwd,
    )
    ds_checks = [c for c in verdict["checks"] if c["check"] == "datastore-identity"]
    assert ds_checks[0]["result"] == "refuse"
    assert ds_checks[0]["reason"] == pilot_boundary.REFUSAL_DATASTORE_IDENTITY_UNAVAILABLE
    assert verdict["result"] == "refuse"


def test_edge6_no_observer_app_reported_recorded_weaker(private_tmp):
    reach_root, run_cwd, _, _ = _provision_layout(private_tmp)
    policy = dict(SAMPLE_POLICY)
    policy["datastore"] = {**policy["datastore"], "observer": None}
    verdict = pp.verify_boundary(
        policy,
        "slot-a@1",
        "http://127.0.0.1:5173",
        reach_roots=[reach_root],
        run_cwd=run_cwd,
        app_reported="example_dev",
    )
    assert verdict["datastoreIdentity"] == {
        "provenance": "app-reported",
        "strength": "weaker",
        "match": True,
    }
    ds_checks = [c for c in verdict["checks"] if c["check"] == "datastore-identity"]
    assert ds_checks[0]["result"] == "pass"


def test_edge7_unknown_slot_refused_before_binding(private_tmp, monkeypatch):
    reach_root, run_cwd, _, _ = _provision_layout(private_tmp)
    policy = SAMPLE_POLICY
    binding_calls = []

    def record_binding(*_args, **_kwargs):
        binding_calls.append(True)

    monkeypatch.setattr(pilot_boundary, "target_binding", record_binding)
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.verify_boundary(
            policy,
            "unknown-slot@1",
            "http://127.0.0.1:5173",
            reach_roots=[reach_root],
            run_cwd=run_cwd,
        )
    assert exc.value.reason == pp.REFUSAL_SLOT_UNKNOWN
    assert binding_calls == []


def test_edge7_malformed_slot_ref_raises_typed_refusal(private_tmp):
    reach_root, run_cwd, _, _ = _provision_layout(private_tmp)
    policy = SAMPLE_POLICY
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.verify_boundary(
            policy,
            "bad@@1",
            "http://127.0.0.1:5173",
            reach_roots=[reach_root],
            run_cwd=run_cwd,
        )
    assert exc.value.reason == pp.REFUSAL_SLOT_UNKNOWN


def test_edge8_unknown_account_refused_before_seed_request(monkeypatch):
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
    seed_calls = []

    def record_seed(*_args, **_kwargs):
        seed_calls.append(True)

    monkeypatch.setattr(pilot_seed, "seed_request", record_seed)
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.authorized_seed_request(
            verdict,
            policy,
            "slot-a@1",
            "intruder",
            artifact,
        )
    assert seed_calls == []
    assert exc.value.reason == pp.REFUSAL_ACCOUNT_UNKNOWN


def test_edge8_slot_absent_from_policy_raises_typed_refusal(monkeypatch):
    policy = dict(SAMPLE_POLICY)
    policy["slots"] = {}
    verdict = _passing_verdict(policy)
    artifact_path, digest = _write_artifact_dir()
    artifact = {
        "path": artifact_path,
        "expectedUid": os.getuid(),
        "expectedMode": 0o600,
        "sha256": digest,
        "captureSurfaces": ["cookies"],
    }
    seed_calls = []

    def record_seed(*_args, **_kwargs):
        seed_calls.append(True)

    monkeypatch.setattr(pilot_seed, "seed_request", record_seed)
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.authorized_seed_request(
            verdict,
            policy,
            "slot-a@1",
            "owner",
            artifact,
        )
    assert seed_calls == []
    assert exc.value.reason == pp.REFUSAL_SLOT_UNKNOWN


def test_edge9_no_mintable_accounts_refused(monkeypatch):
    policy = dict(SAMPLE_POLICY)
    policy["slots"] = {
        "slot-a": {
            **policy["slots"]["slot-a"],
            "mintableAccounts": [],
        },
    }
    verdict = _passing_verdict(policy)
    envelope = {"enablingFlagEnvVar": "ALLOW_TEST_MINT"}
    mint_calls = []

    def record_mint(*_args, **_kwargs):
        mint_calls.append(True)

    monkeypatch.setattr(pilot_seed, "mint_request", record_mint)
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.authorized_mint_request(
            verdict,
            policy,
            "slot-a@1",
            "pilot-owner",
            envelope,
        )
    assert mint_calls == []
    assert exc.value.reason == pp.REFUSAL_MINT_UNSUPPORTED


def test_edge9_absent_mintable_accounts_refused(monkeypatch):
    policy = dict(SAMPLE_POLICY)
    slot_cfg = dict(policy["slots"]["slot-a"])
    del slot_cfg["mintableAccounts"]
    policy["slots"] = {"slot-a": slot_cfg}
    verdict = _passing_verdict(policy)
    envelope = {"enablingFlagEnvVar": "ALLOW_TEST_MINT"}
    mint_calls = []

    def record_mint(*_args, **_kwargs):
        mint_calls.append(True)

    monkeypatch.setattr(pilot_seed, "mint_request", record_mint)
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.authorized_mint_request(
            verdict,
            policy,
            "slot-a@1",
            "pilot-owner",
            envelope,
        )
    assert mint_calls == []
    assert exc.value.reason == pp.REFUSAL_MINT_UNSUPPORTED


def test_edge10_assert_results_only_raises_verdict_never_leaves(private_tmp, monkeypatch):
    reach_root, run_cwd, bin_dir, _ = _provision_layout(private_tmp)
    script = _observer_script(bin_dir, "example_dev")
    policy = _policy_with_observer([script])
    verdict_built = []

    real_boundary_verdict = pilot_boundary.boundary_verdict

    def track_verdict(*args, **kwargs):
        verdict = real_boundary_verdict(*args, **kwargs)
        verdict_built.append(verdict)
        return verdict

    def raising_assert(_result, _material):
        raise pilot_policy.PilotPolicyError(
            pilot_policy.REFUSAL_MATERIAL_IN_RESULT,
            detail="connection-detail",
        )

    monkeypatch.setattr(pilot_boundary, "boundary_verdict", track_verdict)
    monkeypatch.setattr(pilot_policy, "assert_results_only", raising_assert)

    with pytest.raises(pilot_policy.PilotPolicyError) as exc:
        pp.verify_boundary(
            policy,
            "slot-a@1",
            "http://127.0.0.1:5173",
            reach_roots=[reach_root],
            run_cwd=run_cwd,
        )
    assert exc.value.reason == pilot_policy.REFUSAL_MATERIAL_IN_RESULT
    assert len(verdict_built) == 1


# --- authorized_seed_request pass path -----------------------------------------

def test_authorized_seed_request_pass_end_to_end(monkeypatch):
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
    call_order = []
    real_seed = pilot_seed.seed_request

    def track_seed(*args, **kwargs):
        call_order.append("seed_request")
        return real_seed(*args, **kwargs)

    real_authorize = pilot_boundary.authorize_credentials

    def track_authorize(*args, **kwargs):
        call_order.append("authorize_credentials")
        return real_authorize(*args, **kwargs)

    monkeypatch.setattr(pilot_boundary, "authorize_credentials", track_authorize)
    monkeypatch.setattr(pilot_seed, "seed_request", track_seed)

    result = pp.authorized_seed_request(
        verdict,
        policy,
        "slot-a@1",
        "owner",
        artifact,
    )
    assert call_order.index("authorize_credentials") < call_order.index("seed_request")
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


def test_authorized_mint_request_uses_policy_allowlist(monkeypatch):
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    envelope = {"enablingFlagEnvVar": "ALLOW_TEST_MINT"}
    mint_calls = []
    call_order = []
    real_mint = pilot_seed.mint_request

    def track_mint(account, *, allowlist, envelope):
        call_order.append("mint_request")
        mint_calls.append({"account": account, "allowlist": allowlist, "envelope": envelope})
        return real_mint(account, allowlist=allowlist, envelope=envelope)

    real_authorize = pilot_boundary.authorize_credentials

    def track_authorize(*args, **kwargs):
        call_order.append("authorize_credentials")
        return real_authorize(*args, **kwargs)

    monkeypatch.setattr(pilot_boundary, "authorize_credentials", track_authorize)
    monkeypatch.setattr(pilot_seed, "mint_request", track_mint)

    result = pp.authorized_mint_request(
        verdict,
        policy,
        "slot-a@1",
        "pilot-owner",
        envelope,
    )
    assert mint_calls[0]["allowlist"] == policy["slots"]["slot-a"]["mintableAccounts"]
    assert result == {"account": "pilot-owner", "enablingFlagEnvVar": "ALLOW_TEST_MINT"}
    assert call_order.index("authorize_credentials") < call_order.index("mint_request")


def test_refused_verdict_never_reaches_mint(monkeypatch):
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    verdict["result"] = "refuse"
    envelope = {"enablingFlagEnvVar": "ALLOW_TEST_MINT"}
    mint_calls = []

    def record_mint(*_args, **_kwargs):
        mint_calls.append(True)

    monkeypatch.setattr(pilot_seed, "mint_request", record_mint)
    with pytest.raises(pilot_boundary.PilotBoundaryError):
        pp.authorized_mint_request(
            verdict,
            policy,
            "slot-a@1",
            "pilot-owner",
            envelope,
        )
    assert mint_calls == []


# --- integration: real policy document and observer --------------------------

def test_integration_resolve_verify_authorize_seed(private_tmp):
    reach_root, run_cwd, bin_dir, policy_root = _provision_layout(private_tmp)
    script = _observer_script(bin_dir, "example_dev")
    declaration = "provision-integration-policy"
    doc = _policy_with_observer([script], declaration=declaration)
    _write_policy(policy_root, declaration, doc, mode=0o600)

    policy = pilot_policy.resolve_policy_document(
        policy_root,
        declaration,
        reach_roots=[reach_root],
    )
    verdict = pp.verify_boundary(
        policy,
        "slot-a@1",
        "http://127.0.0.1:5173",
        reach_roots=[reach_root],
        run_cwd=run_cwd,
    )
    assert verdict["result"] == "pass"

    artifact_path, digest = _write_artifact_dir()
    capture_surfaces = ["cookies"]
    artifact = {
        "path": artifact_path,
        "expectedUid": os.getuid(),
        "expectedMode": 0o600,
        "sha256": digest,
        "captureSurfaces": capture_surfaces,
    }
    result = pp.authorized_seed_request(
        verdict,
        policy,
        "slot-a@1",
        "owner",
        artifact,
    )
    assert result["slotRef"] == "slot-a@1"
    assert result["account"] == "owner"
    assert result["artifact"]["sha256"] == digest


def test_integration_real_observer_strong_identity(private_tmp):
    reach_root, run_cwd, bin_dir, policy_root = _provision_layout(private_tmp)
    script = _observer_script(bin_dir, "example_dev")
    declaration = "provision-observer-policy"
    doc = _policy_with_observer([script], declaration=declaration)
    _write_policy(policy_root, declaration, doc, mode=0o600)

    policy = pilot_policy.resolve_policy_document(
        policy_root,
        declaration,
        reach_roots=[reach_root],
    )
    verdict = pp.verify_boundary(
        policy,
        "slot-a@1",
        "http://127.0.0.1:5173",
        reach_roots=[reach_root],
        run_cwd=run_cwd,
    )
    assert verdict["result"] == "pass"
    assert verdict["datastoreIdentity"]["provenance"] == "observed"
    assert verdict["datastoreIdentity"]["strength"] == "strong"


def test_integration_observer_mismatch_refuses_before_credentials(private_tmp, monkeypatch):
    reach_root, run_cwd, bin_dir, policy_root = _provision_layout(private_tmp)
    script = _observer_script(bin_dir, "wrong_identity")
    declaration = "provision-mismatch-policy"
    doc = _policy_with_observer([script], declaration=declaration)
    _write_policy(policy_root, declaration, doc, mode=0o600)

    policy = pilot_policy.resolve_policy_document(
        policy_root,
        declaration,
        reach_roots=[reach_root],
    )
    verdict = pp.verify_boundary(
        policy,
        "slot-a@1",
        "http://127.0.0.1:5173",
        reach_roots=[reach_root],
        run_cwd=run_cwd,
    )
    assert verdict["result"] == "refuse"
    assert verdict["reason"] == pilot_boundary.REFUSAL_DATASTORE_IDENTITY_MISMATCH

    artifact_path, digest = _write_artifact_dir()
    artifact = {
        "path": artifact_path,
        "expectedUid": os.getuid(),
        "expectedMode": 0o600,
        "sha256": digest,
        "captureSurfaces": ["cookies"],
    }
    seed_calls = []

    def record_seed(*_args, **_kwargs):
        seed_calls.append(True)

    monkeypatch.setattr(pilot_seed, "seed_request", record_seed)
    with pytest.raises(pilot_boundary.PilotBoundaryError) as exc:
        pp.authorized_seed_request(
            verdict,
            policy,
            "slot-a@1",
            "owner",
            artifact,
        )
    assert seed_calls == []
    assert exc.value.reason == pilot_boundary.REFUSAL_UNVERIFIED


def test_integration_results_only_no_policy_material_in_verdict(private_tmp):
    reach_root, run_cwd, bin_dir, policy_root = _provision_layout(private_tmp)
    script = _observer_script(bin_dir, "example_dev")
    declaration = "provision-results-only-policy"
    doc = _policy_with_observer([script], declaration=declaration)
    _write_policy(policy_root, declaration, doc, mode=0o600)

    policy = pilot_policy.resolve_policy_document(
        policy_root,
        declaration,
        reach_roots=[reach_root],
    )
    verdict = pp.verify_boundary(
        policy,
        "slot-a@1",
        "http://127.0.0.1:5173",
        reach_roots=[reach_root],
        run_cwd=run_cwd,
    )
    assert verdict["result"] == "pass"

    material = pilot_policy.policy_material(policy)
    serialized = json.dumps(verdict, sort_keys=True, ensure_ascii=False)
    for material_class in pilot_policy.MATERIAL_CLASSES:
        for needle in material[material_class]:
            assert needle not in serialized, (
                f"{material_class!r} needle {needle!r} found in verdict"
            )
