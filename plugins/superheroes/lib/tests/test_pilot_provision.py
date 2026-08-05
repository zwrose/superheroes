"""Tests for pilot_provision.py — boundary verification and credential authorization."""
import copy
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


def _captured_policy():
    """Captured-project policy with no policy-side mint grant."""
    policy = dict(SAMPLE_POLICY)
    slot_cfg = dict(policy["slots"]["slot-a"])
    del slot_cfg["mintableAccounts"]
    policy["slots"] = {"slot-a": slot_cfg}
    return policy


def _passing_verdict(policy, slot_ref="slot-a@1"):
    return {
        "schemaVersion": pilot_boundary.BOUNDARY_SCHEMA_VERSION,
        "slotRef": pilot_slot.format_slot_ref(*pilot_slot.parse_slot_ref(slot_ref)),
        "result": "pass",
        "reason": None,
        "checks": [
            {"check": "target-binding", "result": "pass", "reason": None},
            {"check": "datastore-identity", "result": "pass", "reason": None},
        ],
        "datastoreIdentity": None,
        "policyDigest": _digest(policy),
        "verifiedAt": "2026-01-01T00:00:00Z",
    }


def _write_artifact_dir(private_tmp):
    artifact_dir = tempfile.mkdtemp(dir=private_tmp)
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

def test_edge1_refused_verdict_raises_before_seed(private_tmp, monkeypatch):
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    verdict["result"] = "refuse"
    artifact_path, digest = _write_artifact_dir(private_tmp)
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


def test_edge2_verdict_bound_to_different_slot_raises(private_tmp, monkeypatch):
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy, slot_ref="slot-b@1")
    artifact_path, digest = _write_artifact_dir(private_tmp)
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


def test_edge3_policy_digest_mismatch_raises(private_tmp, monkeypatch):
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    tampered = dict(policy)
    tampered["declaration"] = "tampered-policy"
    artifact_path, digest = _write_artifact_dir(private_tmp)
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


def test_edge8_unknown_account_refused_before_seed_request(private_tmp, monkeypatch):
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    artifact_path, digest = _write_artifact_dir(private_tmp)
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


def test_edge8_slot_absent_from_policy_raises_typed_refusal(private_tmp, monkeypatch):
    policy = dict(SAMPLE_POLICY)
    policy["slots"] = {}
    verdict = _passing_verdict(policy)
    artifact_path, digest = _write_artifact_dir(private_tmp)
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

def test_authorized_seed_request_pass_end_to_end(private_tmp, monkeypatch):
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    artifact_path, digest = _write_artifact_dir(private_tmp)
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

    artifact_path, digest = _write_artifact_dir(private_tmp)
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

    artifact_path, digest = _write_artifact_dir(private_tmp)
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


# --- authorized_sentinel_probe_request (T3) -----------------------------------

def test_authorized_sentinel_probe_request_pass_end_to_end(private_tmp, monkeypatch):
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    envelope = {"enablingFlagEnvVar": "ALLOW_TEST_MINT"}
    sentinel = "pilot-sentinel-no-such-account"
    call_order = []
    real_sentinel = pilot_seed.sentinel_probe_request

    def track_sentinel(sentinel_value, *, allowlist, envelope):
        call_order.append("sentinel_probe_request")
        return real_sentinel(sentinel_value, allowlist=allowlist, envelope=envelope)

    real_authorize = pilot_boundary.authorize_credentials

    def track_authorize(*args, **kwargs):
        call_order.append("authorize_credentials")
        return real_authorize(*args, **kwargs)

    monkeypatch.setattr(pilot_boundary, "authorize_credentials", track_authorize)
    monkeypatch.setattr(pilot_seed, "sentinel_probe_request", track_sentinel)

    result = pp.authorized_sentinel_probe_request(
        verdict,
        policy,
        "slot-a@1",
        sentinel,
        envelope,
    )
    assert call_order.index("authorize_credentials") < call_order.index(
        "sentinel_probe_request"
    )
    assert result == {
        "sentinel": sentinel,
        "enablingFlagEnvVar": "ALLOW_TEST_MINT",
    }


def test_refused_verdict_never_reaches_sentinel_probe(monkeypatch):
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    verdict["result"] = "refuse"
    envelope = {"enablingFlagEnvVar": "ALLOW_TEST_MINT"}
    sentinel_calls = []

    def record_sentinel(*_args, **_kwargs):
        sentinel_calls.append(True)

    monkeypatch.setattr(pilot_seed, "sentinel_probe_request", record_sentinel)
    with pytest.raises(pilot_boundary.PilotBoundaryError):
        pp.authorized_sentinel_probe_request(
            verdict,
            policy,
            "slot-a@1",
            "pilot-sentinel-no-such-account",
            envelope,
        )
    assert sentinel_calls == []


def test_authorized_sentinel_probe_request_unknown_slot_refused(monkeypatch):
    policy = dict(SAMPLE_POLICY)
    policy["slots"] = {}
    verdict = _passing_verdict(policy, slot_ref="unknown-slot@1")
    envelope = {"enablingFlagEnvVar": "ALLOW_TEST_MINT"}
    sentinel_calls = []

    def record_sentinel(*_args, **_kwargs):
        sentinel_calls.append(True)

    monkeypatch.setattr(pilot_seed, "sentinel_probe_request", record_sentinel)
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.authorized_sentinel_probe_request(
            verdict,
            policy,
            "unknown-slot@1",
            "pilot-sentinel-no-such-account",
            envelope,
        )
    assert sentinel_calls == []
    assert exc.value.reason == pp.REFUSAL_SLOT_UNKNOWN


def test_authorized_sentinel_probe_request_uses_policy_allowlist(monkeypatch):
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    envelope = {"enablingFlagEnvVar": "ALLOW_TEST_MINT"}
    sentinel_calls = []
    real_sentinel = pilot_seed.sentinel_probe_request

    def track_sentinel(sentinel, *, allowlist, envelope):
        sentinel_calls.append({"allowlist": allowlist})
        return real_sentinel(sentinel, allowlist=allowlist, envelope=envelope)

    monkeypatch.setattr(pilot_seed, "sentinel_probe_request", track_sentinel)
    pp.authorized_sentinel_probe_request(
        verdict,
        policy,
        "slot-a@1",
        "pilot-sentinel-no-such-account",
        envelope,
    )
    assert sentinel_calls[0]["allowlist"] == policy["slots"]["slot-a"]["mintableAccounts"]


# --- C7: declare-and-exercise gate + datastore identity + gate_provisioning --------

def _mint_block():
    return {
        "envelope": {
            "enablingFlagEnvVar": "ALLOW_TEST_MINT",
            "enabledScopes": ["development"],
            "forbiddenScopes": ["production", "staging"],
            "gateOffTestCommand": ["npm", "run", "test:mint-gate-off"],
        },
        "sentinelIdentifier": "pilot-sentinel-no-such-account",
    }


def _valid_pilot_block():
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
    })


def _valid_minted_pilot_block():
    block = _valid_pilot_block()
    block["signInPath"] = "minted"
    block["mint"] = _mint_block()
    return block


def _registry_record(kind, declaration):
    digest = pilot_contract.declaration_digest(declaration)
    return {
        "kind": kind,
        "declarationDigest": digest,
        "exercisedAt": "2026-08-02T04:00:00Z",
        "receipt": {"result": "pass", "evidence": "exercised"},
    }


def _full_registry(block, policy, slot_ref):
    records = []
    for kind in pilot_contract.DECLARATION_KINDS:
        info = pp.declaration_for(kind, block, policy, slot_ref)
        if info["applicable"]:
            records.append(_registry_record(kind, info["declaration"]))
    return {"schemaVersion": pilot_contract.REGISTRY_SCHEMA_VERSION, "records": records}


def _verdict_with_identity(policy, *, strength="strong", match=True, provenance="observed"):
    verdict = _passing_verdict(policy)
    verdict["datastoreIdentity"] = {
        "provenance": provenance,
        "strength": strength,
        "match": match,
    }
    return verdict


def _valid_weaker_acceptance():
    return {
        "acceptedBy": "owner",
        "acceptedAt": "2026-08-02T12:00:00Z",
        "reason": "app-reported identity accepted for dev slot",
    }


def test_declaration_sources_covers_declaration_kinds():
    assert set(pp.DECLARATION_SOURCES) == pilot_contract.DECLARATION_KINDS
    pp._verify_declaration_sources_complete()


def test_app_lifecycle_extractor_returns_policy_origin_and_redirects():
    policy = SAMPLE_POLICY
    block = _valid_pilot_block()
    slot_ref = "slot-a@1"
    info = pp.declaration_for("app-lifecycle", block, policy, slot_ref)
    assert info["applicable"] is True
    assert set(info["declaration"]) == {"origin", "permittedRedirects"}
    assert info["declaration"] == {
        "origin": policy["slots"]["slot-a"]["origin"],
        "permittedRedirects": policy["slots"]["slot-a"]["permittedRedirects"],
    }


def test_app_lifecycle_always_applicable_for_captured_project():
    policy = _captured_policy()
    block = _valid_pilot_block()
    slot_ref = "slot-a@1"
    info = pp.declaration_for("app-lifecycle", block, policy, slot_ref)
    assert info["applicable"] is True
    assert info["declaration"] is not None


def test_app_lifecycle_missing_origin_refuses():
    policy = dict(SAMPLE_POLICY)
    slot_cfg = dict(policy["slots"]["slot-a"])
    del slot_cfg["origin"]
    policy["slots"] = {"slot-a": slot_cfg}
    block = _valid_pilot_block()
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.declaration_for("app-lifecycle", block, policy, "slot-a@1")
    assert exc.value.reason == pp.REFUSAL_DECLARATION_SOURCE_MISSING


def test_app_lifecycle_missing_permitted_redirects_refuses():
    policy = dict(SAMPLE_POLICY)
    slot_cfg = dict(policy["slots"]["slot-a"])
    del slot_cfg["permittedRedirects"]
    policy["slots"] = {"slot-a": slot_cfg}
    block = _valid_pilot_block()
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.declaration_for("app-lifecycle", block, policy, "slot-a@1")
    assert exc.value.reason == pp.REFUSAL_DECLARATION_SOURCE_MISSING


def test_app_lifecycle_unparseable_slot_ref_refuses():
    policy = SAMPLE_POLICY
    block = _valid_pilot_block()
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.declaration_for("app-lifecycle", block, policy, "bad@@1")
    assert exc.value.reason == pp.REFUSAL_DECLARATION_SOURCE_MISSING


def test_app_lifecycle_digest_moves_when_origin_changes():
    policy_a = _captured_policy()
    policy_b = copy.deepcopy(policy_a)
    policy_b["slots"]["slot-a"]["origin"] = "http://127.0.0.1:3000"
    block = _valid_pilot_block()
    slot_ref = "slot-a@1"
    info_a = pp.declaration_for("app-lifecycle", block, policy_a, slot_ref)
    info_b = pp.declaration_for("app-lifecycle", block, policy_b, slot_ref)
    digest_a = pilot_contract.declaration_digest(info_a["declaration"])
    digest_b = pilot_contract.declaration_digest(info_b["declaration"])
    assert digest_a != digest_b
    registry = {
        "schemaVersion": pilot_contract.REGISTRY_SCHEMA_VERSION,
        "records": [_registry_record("app-lifecycle", info_a["declaration"])],
    }
    with pytest.raises(pilot_contract.PilotContractError) as exc:
        pilot_contract.require_exercised(
            registry, "app-lifecycle", info_b["declaration"],
        )
    assert exc.value.reason == pilot_contract.REFUSAL_DECLARATION_UNEXERCISED


def test_gate_provisioning_pass_strong_identity_captured(private_tmp):
    policy = _captured_policy()
    block = _valid_pilot_block()
    slot_ref = "slot-a@1"
    registry = _full_registry(block, policy, slot_ref)
    verdict = _verdict_with_identity(policy)
    receipt = pp.gate_provisioning(
        verdict, policy, slot_ref, block, registry,
    )
    assert receipt["slotRef"] == "slot-a@1"
    assert receipt["policyDigest"] == _digest(policy)
    assert receipt["datastoreIdentity"] == {
        "provenance": "observed",
        "strength": "strong",
        "match": True,
    }
    assert receipt["weakerAcceptance"] is None
    mint_statuses = {
        d["kind"]: d["status"] for d in receipt["declarations"]
    }
    assert mint_statuses["mint-gate-off"] == "not-applicable"
    assert mint_statuses["mint-account-allowlist"] == "not-applicable"
    assert "gatedAt" in receipt


def test_gate_provisioning_weaker_acceptance_carried_in_receipt():
    policy = _captured_policy()
    block = _valid_pilot_block()
    slot_ref = "slot-a@1"
    registry = _full_registry(block, policy, slot_ref)
    acceptance = _valid_weaker_acceptance()
    verdict = _verdict_with_identity(
        policy, strength="weaker", provenance="app-reported",
    )
    receipt = pp.gate_provisioning(
        verdict, policy, slot_ref, block, registry,
        weaker_acceptance=acceptance,
    )
    assert receipt["weakerAcceptance"] == acceptance
    assert receipt["datastoreIdentity"]["strength"] == "weaker"


def test_gate_edge1_unexercised_declaration_refuses():
    policy = _captured_policy()
    block = _valid_pilot_block()
    slot_ref = "slot-a@1"
    with pytest.raises(pilot_contract.PilotContractError) as exc:
        pp.require_declarations_exercised(block, policy, slot_ref, {})
    assert exc.value.reason == pilot_contract.REFUSAL_DECLARATION_UNEXERCISED


def test_gate_edge2_digest_mismatch_refuses():
    policy = _captured_policy()
    block = _valid_pilot_block()
    slot_ref = "slot-a@1"
    registry = _full_registry(block, policy, slot_ref)
    block["identityProbe"] = {
        "path": "/api/changed",
        "unseededExpectation": "no-session",
    }
    with pytest.raises(pilot_contract.PilotContractError) as exc:
        pp.require_declarations_exercised(block, policy, slot_ref, registry)
    assert exc.value.reason == pilot_contract.REFUSAL_DECLARATION_UNEXERCISED


def test_gate_edge3_receipt_fail_refuses():
    policy = _captured_policy()
    block = _valid_pilot_block()
    slot_ref = "slot-a@1"
    info = pp.declaration_for("identity-probe", block, policy, slot_ref)
    registry = {
        "schemaVersion": pilot_contract.REGISTRY_SCHEMA_VERSION,
        "records": [{
            "kind": "identity-probe",
            "declarationDigest": pilot_contract.declaration_digest(info["declaration"]),
            "exercisedAt": "2026-08-02T04:00:00Z",
            "receipt": {"result": "fail", "evidence": "failed"},
        }],
    }
    with pytest.raises(pilot_contract.PilotContractError) as exc:
        pp.require_declarations_exercised(block, policy, slot_ref, registry)
    assert exc.value.reason == pilot_contract.REFUSAL_DECLARATION_UNEXERCISED


def test_gate_edge4_no_evidence_refuses():
    policy = _captured_policy()
    block = _valid_pilot_block()
    slot_ref = "slot-a@1"
    info = pp.declaration_for("identity-probe", block, policy, slot_ref)
    registry = {
        "schemaVersion": pilot_contract.REGISTRY_SCHEMA_VERSION,
        "records": [{
            "kind": "identity-probe",
            "declarationDigest": pilot_contract.declaration_digest(info["declaration"]),
            "exercisedAt": "2026-08-02T04:00:00Z",
            "receipt": {"result": "pass"},
        }],
    }
    with pytest.raises(pilot_contract.PilotContractError) as exc:
        pp.require_declarations_exercised(block, policy, slot_ref, registry)
    assert exc.value.reason == pilot_contract.REFUSAL_DECLARATION_UNEXERCISED


def test_gate_edge5_wrong_schema_version_refuses():
    policy = _captured_policy()
    block = _valid_pilot_block()
    slot_ref = "slot-a@1"
    registry = _full_registry(block, policy, slot_ref)
    registry["schemaVersion"] = 2
    with pytest.raises(pilot_contract.PilotContractError) as exc:
        pp.require_declarations_exercised(block, policy, slot_ref, registry)
    assert exc.value.reason == pilot_contract.REFUSAL_DECLARATION_UNEXERCISED


def test_gate_edge6_declaration_kinds_uncovered(monkeypatch):
    monkeypatch.setattr(
        pilot_contract,
        "DECLARATION_KINDS",
        frozenset(pilot_contract.DECLARATION_KINDS) | {"future-kind"},
    )
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp._verify_declaration_sources_complete()
    assert exc.value.reason == pp.REFUSAL_DECLARATION_KINDS_UNCOVERED


def test_gate_edge7_missing_declaration_source_key_refuses():
    policy = _captured_policy()
    block = _valid_pilot_block()
    del block["identityProbe"]
    slot_ref = "slot-a@1"
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.declaration_for("identity-probe", block, policy, slot_ref)
    assert exc.value.reason == pp.REFUSAL_DECLARATION_SOURCE_MISSING


def test_gate_edge8_captured_project_skips_mint_kinds():
    policy = _captured_policy()
    block = _valid_pilot_block()
    slot_ref = "slot-a@1"
    registry = _full_registry(block, policy, slot_ref)
    verdict = _verdict_with_identity(policy)
    receipt = pp.gate_provisioning(
        verdict, policy, slot_ref, block, registry,
    )
    statuses = {d["kind"]: d["status"] for d in receipt["declarations"]}
    assert statuses["mint-gate-off"] == "not-applicable"
    assert statuses["mint-account-allowlist"] == "not-applicable"
    assert statuses["identity-probe"] == "exercised"


def test_gate_edge9_minted_unexercised_mint_gate_off_refuses():
    policy = SAMPLE_POLICY
    block = _valid_minted_pilot_block()
    slot_ref = "slot-a@1"
    registry = _full_registry(block, policy, slot_ref)
    registry["records"] = [
        record for record in registry["records"]
        if record["kind"] != "mint-gate-off"
    ]
    with pytest.raises(pilot_contract.PilotContractError) as exc:
        pp.require_declarations_exercised(block, policy, slot_ref, registry)
    assert exc.value.reason == pilot_contract.REFUSAL_DECLARATION_UNEXERCISED


def test_gate_edge10_datastore_identity_absent_refuses():
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.gate_datastore_identity(verdict)
    assert exc.value.reason == pp.REFUSAL_DATASTORE_IDENTITY_ABSENT


def test_gate_edge11_datastore_identity_unmatched_refuses():
    policy = SAMPLE_POLICY
    verdict = _verdict_with_identity(policy, match=False)
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.gate_datastore_identity(verdict)
    assert exc.value.reason == pp.REFUSAL_DATASTORE_IDENTITY_UNMATCHED


def test_gate_edge12_weaker_without_acceptance_refuses():
    policy = SAMPLE_POLICY
    verdict = _verdict_with_identity(policy, strength="weaker", provenance="app-reported")
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.gate_datastore_identity(verdict)
    assert exc.value.reason == pp.REFUSAL_DATASTORE_IDENTITY_WEAKER_UNACCEPTED


def test_gate_edge13_malformed_weaker_acceptance_refuses():
    policy = SAMPLE_POLICY
    verdict = _verdict_with_identity(policy, strength="weaker", provenance="app-reported")
    bad = {"acceptedBy": "owner", "acceptedAt": "not-iso", "reason": "ok"}
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.gate_datastore_identity(verdict, weaker_acceptance=bad)
    assert exc.value.reason == pp.REFUSAL_WEAKER_ACCEPTANCE_INVALID


def test_gate_edge14_weaker_with_valid_acceptance_passes():
    policy = SAMPLE_POLICY
    verdict = _verdict_with_identity(policy, strength="weaker", provenance="app-reported")
    acceptance = _valid_weaker_acceptance()
    result = pp.gate_datastore_identity(verdict, weaker_acceptance=acceptance)
    assert result["ok"] is True
    assert result["acceptance"] == acceptance


def test_gate_edge15_unknown_strength_refuses():
    policy = SAMPLE_POLICY
    verdict = _verdict_with_identity(policy, strength="medium")
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.gate_datastore_identity(verdict)
    assert exc.value.reason == pp.REFUSAL_DATASTORE_IDENTITY_STRENGTH_UNKNOWN


def test_gate_edge16_authorize_credentials_called_first(monkeypatch):
    policy = _captured_policy()
    block = _valid_pilot_block()
    slot_ref = "slot-a@1"
    registry = _full_registry(block, policy, slot_ref)
    verdict = _passing_verdict(policy)
    verdict["result"] = "refuse"
    identity_calls = []
    declaration_calls = []

    def track_identity(*_args, **_kwargs):
        identity_calls.append(True)

    def track_declarations(*_args, **_kwargs):
        declaration_calls.append(True)

    monkeypatch.setattr(pp, "gate_datastore_identity", track_identity)
    monkeypatch.setattr(pp, "require_declarations_exercised", track_declarations)
    with pytest.raises(pilot_boundary.PilotBoundaryError) as exc:
        pp.gate_provisioning(verdict, policy, slot_ref, block, registry)
    assert exc.value.reason == pilot_boundary.REFUSAL_UNVERIFIED
    assert identity_calls == []
    assert declaration_calls == []


def test_gate_edge17_receipt_has_no_policy_material(private_tmp):
    policy = _captured_policy()
    block = _valid_pilot_block()
    slot_ref = "slot-a@1"
    registry = _full_registry(block, policy, slot_ref)
    verdict = _verdict_with_identity(policy)
    receipt = pp.gate_provisioning(
        verdict, policy, slot_ref, block, registry,
    )
    material = pilot_policy.policy_material(policy)
    serialized = json.dumps(receipt, sort_keys=True, ensure_ascii=False)
    for material_class in pilot_policy.MATERIAL_CLASSES:
        for needle in material[material_class]:
            assert needle not in serialized


def test_gate_edge17_assert_results_only_refuses_material_in_receipt(monkeypatch):
    policy = _captured_policy()
    block = _valid_pilot_block()
    slot_ref = "slot-a@1"
    registry = _full_registry(block, policy, slot_ref)
    verdict = _verdict_with_identity(policy)

    def leaking_assert(_receipt, _material):
        raise pilot_policy.PilotPolicyError(
            pilot_policy.REFUSAL_MATERIAL_IN_RESULT,
            detail="connection-detail",
        )

    monkeypatch.setattr(pilot_policy, "assert_results_only", leaking_assert)
    with pytest.raises(pilot_policy.PilotPolicyError) as exc:
        pp.gate_provisioning(verdict, policy, slot_ref, block, registry)
    assert exc.value.reason == pilot_policy.REFUSAL_MATERIAL_IN_RESULT


# --- finding 2: mint applicability from policy --------------------------------

def test_mint_kinds_not_skipped_when_policy_grants_mintable_accounts():
    policy = SAMPLE_POLICY
    block = _valid_pilot_block()
    slot_ref = "slot-a@1"
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.declaration_for("mint-gate-off", block, policy, slot_ref)
    assert exc.value.reason == pp.REFUSAL_MINT_DECLARATION_MISSING


def test_mint_kinds_skipped_when_no_policy_grant_and_no_block():
    policy = _captured_policy()
    block = _valid_pilot_block()
    slot_ref = "slot-a@1"
    info = pp.declaration_for("mint-gate-off", block, policy, slot_ref)
    assert info["applicable"] is False
    assert info["declaration"] is None


# --- finding 3: ISO8601 acceptance timestamp validation ---------------------

@pytest.mark.parametrize(
    "accepted_at",
    [
        "2026-13-01T00:00:00Z",
        "2026-01-45T00:00:00Z",
        "2026-01-01T99:00:00Z",
        "2026-01-01T00:99:00Z",
        "2026-01-01T00:00:99Z",
    ],
)
def test_weaker_acceptance_refuses_impossible_timestamps(accepted_at):
    policy = SAMPLE_POLICY
    verdict = _verdict_with_identity(policy, strength="weaker", provenance="app-reported")
    bad = {
        "acceptedBy": "owner",
        "acceptedAt": accepted_at,
        "reason": "app-reported identity accepted for dev slot",
    }
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.gate_datastore_identity(verdict, weaker_acceptance=bad)
    assert exc.value.reason == pp.REFUSAL_WEAKER_ACCEPTANCE_INVALID


def test_weaker_acceptance_accepts_real_timestamp():
    policy = SAMPLE_POLICY
    verdict = _verdict_with_identity(policy, strength="weaker", provenance="app-reported")
    acceptance = _valid_weaker_acceptance()
    result = pp.gate_datastore_identity(verdict, weaker_acceptance=acceptance)
    assert result["ok"] is True


# --- finding 4: datastore strength vocabulary drift guard ---------------------

def test_datastore_strength_matches_pilot_boundary(private_tmp):
    # axis: the two words still travel on the observation shapes the gate reads. Since #866 the
    # vocabulary has one home (`pilot_boundary`) and `pp` re-exports it, so a spelling *drift*
    # between the modules is no longer representable — what this still discriminates is a
    # producer that stops emitting `strength` on either observation, or emits the wrong one.
    weaker_observation = pilot_boundary.app_reported_identity("example_dev")
    assert weaker_observation["strength"] == pp.STRENGTH_WEAKER

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
    assert verdict["datastoreIdentity"]["strength"] == pp.STRENGTH_STRONG


# --- authorized_app_launch (O3 / seam S-B) -------------------------------------


def _valid_launch():
    return {
        "baseUrl": "http://127.0.0.1:5173",
        "readinessUrl": "http://127.0.0.1:5173",
    }


def test_authorized_app_launch_happy_path():
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    launch = _valid_launch()
    result = pp.authorized_app_launch(verdict, policy, "slot-a@1", launch)
    assert result == {
        "schemaVersion": 1,
        "slotRef": "slot-a@1",
        "baseUrl": launch["baseUrl"],
        "readinessUrl": launch["readinessUrl"],
        "policyDigest": _digest(policy),
    }


def test_app_launch_edge_refused_verdict(monkeypatch):
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    verdict["result"] = "refuse"
    binding_calls = []

    def record_binding(*_args, **_kwargs):
        binding_calls.append(True)

    monkeypatch.setattr(pilot_boundary, "target_binding", record_binding)
    with pytest.raises(pilot_boundary.PilotBoundaryError) as exc:
        pp.authorized_app_launch(verdict, policy, "slot-a@1", _valid_launch())
    assert exc.value.reason == pilot_boundary.REFUSAL_UNVERIFIED
    assert binding_calls == []


def test_app_launch_edge_policy_digest_mismatch(monkeypatch):
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    tampered = dict(policy)
    tampered["declaration"] = "tampered-policy"
    binding_calls = []

    def record_binding(*_args, **_kwargs):
        binding_calls.append(True)

    monkeypatch.setattr(pilot_boundary, "target_binding", record_binding)
    with pytest.raises(pilot_boundary.PilotBoundaryError) as exc:
        pp.authorized_app_launch(verdict, tampered, "slot-a@1", _valid_launch())
    assert exc.value.reason == pilot_boundary.REFUSAL_UNVERIFIED
    assert binding_calls == []


def test_app_launch_edge_verdict_slot_ref_disagrees(monkeypatch):
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy, slot_ref="slot-b@1")
    binding_calls = []

    def record_binding(*_args, **_kwargs):
        binding_calls.append(True)

    monkeypatch.setattr(pilot_boundary, "target_binding", record_binding)
    with pytest.raises(pilot_boundary.PilotBoundaryError) as exc:
        pp.authorized_app_launch(verdict, policy, "slot-a@1", _valid_launch())
    assert exc.value.reason == pilot_boundary.REFUSAL_UNVERIFIED
    assert binding_calls == []


def test_app_launch_edge_malformed_slot_ref(monkeypatch):
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    binding_calls = []

    def record_binding(*_args, **_kwargs):
        binding_calls.append(True)

    monkeypatch.setattr(pilot_boundary, "target_binding", record_binding)
    with pytest.raises(pilot_boundary.PilotBoundaryError) as exc:
        pp.authorized_app_launch(verdict, policy, "bad@@1", _valid_launch())
    assert exc.value.reason == pilot_boundary.REFUSAL_UNVERIFIED
    assert binding_calls == []


def test_app_launch_edge_slot_absent_from_policy(monkeypatch):
    policy = dict(SAMPLE_POLICY)
    policy["slots"] = {}
    verdict = _passing_verdict(policy)
    binding_calls = []

    def record_binding(*_args, **_kwargs):
        binding_calls.append(True)

    monkeypatch.setattr(pilot_boundary, "target_binding", record_binding)
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.authorized_app_launch(verdict, policy, "slot-a@1", _valid_launch())
    assert exc.value.reason == pp.REFUSAL_SLOT_UNKNOWN
    assert binding_calls == []


def test_app_launch_edge_launch_not_mapping():
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.authorized_app_launch(verdict, policy, "slot-a@1", "not-a-mapping")
    assert exc.value.reason == pp.REFUSAL_LAUNCH_INVALID


def test_app_launch_edge_base_url_absent():
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.authorized_app_launch(
            verdict, policy, "slot-a@1", {"readinessUrl": "http://127.0.0.1:5173"},
        )
    assert exc.value.reason == pp.REFUSAL_LAUNCH_INVALID


def test_app_launch_edge_base_url_non_string():
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.authorized_app_launch(
            verdict,
            policy,
            "slot-a@1",
            {"baseUrl": 5173, "readinessUrl": "http://127.0.0.1:5173"},
        )
    assert exc.value.reason == pp.REFUSAL_LAUNCH_INVALID


def test_app_launch_edge_base_url_empty():
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.authorized_app_launch(
            verdict,
            policy,
            "slot-a@1",
            {"baseUrl": "", "readinessUrl": "http://127.0.0.1:5173"},
        )
    assert exc.value.reason == pp.REFUSAL_LAUNCH_INVALID


def test_app_launch_edge_readiness_url_absent():
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.authorized_app_launch(
            verdict, policy, "slot-a@1", {"baseUrl": "http://127.0.0.1:5173"},
        )
    assert exc.value.reason == pp.REFUSAL_LAUNCH_INVALID


def test_app_launch_edge_readiness_url_non_string():
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.authorized_app_launch(
            verdict,
            policy,
            "slot-a@1",
            {"baseUrl": "http://127.0.0.1:5173", "readinessUrl": 5173},
        )
    assert exc.value.reason == pp.REFUSAL_LAUNCH_INVALID


def test_app_launch_edge_readiness_url_empty():
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.authorized_app_launch(
            verdict,
            policy,
            "slot-a@1",
            {"baseUrl": "http://127.0.0.1:5173", "readinessUrl": ""},
        )
    assert exc.value.reason == pp.REFUSAL_LAUNCH_INVALID


def test_app_launch_edge_base_url_off_origin():
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.authorized_app_launch(
            verdict,
            policy,
            "slot-a@1",
            {
                "baseUrl": "http://evil.example.com:80",
                "readinessUrl": "http://127.0.0.1:5173",
            },
        )
    assert exc.value.reason == pilot_boundary.REFUSAL_TARGET_OFF_ALLOWLIST


def test_app_launch_edge_readiness_url_off_origin():
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.authorized_app_launch(
            verdict,
            policy,
            "slot-a@1",
            {
                "baseUrl": "http://127.0.0.1:5173",
                "readinessUrl": "http://evil.example.com:80",
            },
        )
    assert exc.value.reason == pilot_boundary.REFUSAL_TARGET_OFF_ALLOWLIST


def test_app_launch_edge_readiness_url_protected_target():
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)
    with pytest.raises(pp.PilotProvisionError) as exc:
        pp.authorized_app_launch(
            verdict,
            policy,
            "slot-a@1",
            {
                "baseUrl": "http://127.0.0.1:5173",
                "readinessUrl": "https://app.example.com:443",
            },
        )
    assert exc.value.reason == pilot_boundary.REFUSAL_PROTECTED_TARGET


def test_app_launch_edge_assert_results_only_refuses(monkeypatch):
    policy = SAMPLE_POLICY
    verdict = _passing_verdict(policy)

    def raising_assert(_result, _material):
        raise pilot_policy.PilotPolicyError(
            pilot_policy.REFUSAL_MATERIAL_IN_RESULT,
            detail="connection-detail",
        )

    monkeypatch.setattr(pilot_policy, "assert_results_only", raising_assert)
    with pytest.raises(pilot_policy.PilotPolicyError) as exc:
        pp.authorized_app_launch(verdict, policy, "slot-a@1", _valid_launch())
    assert exc.value.reason == pilot_policy.REFUSAL_MATERIAL_IN_RESULT
