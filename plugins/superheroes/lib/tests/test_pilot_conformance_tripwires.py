"""Tests for boundary-refusals, horizon-validity, and ownership-probe exercises."""
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

import pilot_boundary as pb  # noqa: E402
import pilot_conformance as pc  # noqa: E402
import pilot_conformance_runtime as pcr  # noqa: E402
import pilot_horizon as ph  # noqa: E402
import pilot_policy as pp  # noqa: E402

EXERCISED_AT = "2026-08-07T12:00:00Z"
_SLOT_REF = "slot-a@1"


def _sample_policy(**overrides):
    doc = {
        "schemaVersion": 1,
        "declaration": "example-project-pilot-policy",
        "protectedTargets": ["https://app.example.com:443", "example_prod"],
        "datastore": {
            "expectedIdentity": "example_dev",
            "connectionDetail": "postgres://localhost:5432/example_dev",
            "observer": {
                "command": ["/opt/pilot/db-identity"],
                "connectionEnvVar": "PILOT_DB_URL",
            },
        },
        "slots": {
            "slot-a": {
                "origin": "http://127.0.0.1:5173",
                "permittedRedirects": ["http://127.0.0.1:5173"],
                "expectedIdentities": {"owner": "pilot-owner@example.test"},
            }
        },
        "ownershipProbe": None,
    }
    doc.update(overrides)
    return doc


def _boundary_inputs(policy, slot_ref=_SLOT_REF):
    return {"boundary": {"policy": policy, "slot_ref": slot_ref}}


def _horizon_inputs(pilot_block):
    return {"horizon": {"pilot_block": pilot_block}}


def _pilot_block(**overrides):
    block = {
        "schemaVersion": 1,
        "signInPath": "attended",
        "attended": {"vehicle": "automation"},
        "credentialSet": [{"account": "owner", "role": "resource-owner"}],
        "captureSurface": ["cookies"],
        "captureOptions": {"indexedDB": False, "credentials": False},
        "validityProvenance": "server-probe",
        "identityProbe": {"path": "/api/me", "unseededExpectation": "no-session"},
        "cleanup": {"command": ["cleanup", "{namespace}"]},
        "administrativeMax": 4,
        "effectsEscape": {"canEscape": False, "evidence": "x"},
        "policyRef": {"declaration": "example-project-pilot-policy"},
    }
    block.update(overrides)
    return block


def _ownership_probe_command(body_code, exit_code=0):
    trailer = ""
    if exit_code:
        trailer = "; sys.exit(%d)" % exit_code
    script = (
        "import json, sys; _acct=sys.argv[1]; "
        "assert _acct == '%s' or _acct == sys.argv[1]; %s%s"
    ) % (pp.ACCOUNT_PLACEHOLDER, body_code, trailer)
    return [sys.executable, "-c", script, pp.ACCOUNT_PLACEHOLDER]


def _confined_ownership_probe_command(workspace, body_code, exit_code=0):
    reach_root = os.path.join(workspace, "reach")
    os.makedirs(reach_root, exist_ok=True)
    outer_bin = tempfile.mkdtemp(
        dir=os.path.dirname(workspace),
        prefix="ownership-probe-bin-",
    )
    probe_py = os.path.join(outer_bin, "ownership_probe.py")
    trailer = ""
    if exit_code:
        trailer = "\nsys.exit(%d)" % exit_code
    with open(probe_py, "w", encoding="utf-8") as handle:
        handle.write(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "_acct = sys.argv[1]\n"
            + body_code
            + trailer
            + "\n"
        )
    os.chmod(probe_py, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return [probe_py, pp.ACCOUNT_PLACEHOLDER]


def _run_ownership_probe(tmp_dir, policy, pilot_block, command, *, reach_roots=None):
    policy = dict(policy)
    policy["ownershipProbe"] = {
        "command": command,
        "connectionEnvVar": "PILOT_DB_URL",
    }
    if reach_roots is None:
        reach_roots = [os.path.join(tmp_dir, "reach")]
        os.makedirs(reach_roots[0], exist_ok=True)
    return pcr.ownership_probe_exercise(
        inputs={
            "ownership_probe": {
                "policy": policy,
                "pilot_block": pilot_block,
                "run_cwd": tmp_dir,
                "reach_roots": reach_roots,
                "connection_detail": policy["datastore"]["connectionDetail"],
            }
        },
        now=EXERCISED_AT,
    )


def _policy_with_probe(command):
    return _sample_policy(
        ownershipProbe={
            "command": command,
            "connectionEnvVar": "PILOT_DB_URL",
        }
    )


@pytest.fixture
def tmp_dir():
    path = tempfile.mkdtemp()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


# --- boundary-refusals --------------------------------------------------------


def test_boundary_refusals_skip_when_inputs_missing():
    record = pcr.boundary_refusals_exercise(inputs={}, now=EXERCISED_AT)
    assert record["result"] == pc.RESULT_SKIPPED
    assert record["reason"] == pcr.REASON_INPUTS_MISSING


def test_boundary_refusals_binding_accept_leg():
    policy = _sample_policy()
    record = pcr.boundary_refusals_exercise(
        inputs=_boundary_inputs(policy),
        now=EXERCISED_AT,
    )
    assert record["result"] == pc.RESULT_PASS


def test_boundary_refusals_off_allowlist_target_token(monkeypatch):
    policy = _sample_policy()

    def fake_check_target(_binding, url):
        if url == pcr._off_allowlist_origin(policy, policy["slots"]["slot-a"]):
            return {"ok": True, "reason": None}
        return pb.check_target(_binding, url)

    monkeypatch.setattr(pcr.pilot_boundary, "check_target", fake_check_target)
    record = pcr.boundary_refusals_exercise(
        inputs=_boundary_inputs(policy),
        now=EXERCISED_AT,
    )
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == pcr.REASON_BOUNDARY_EXPECTATION_UNMET


def test_boundary_refusals_off_allowlist_redirect_token(monkeypatch):
    policy = _sample_policy()
    real_redirect = pb.check_redirect

    def fake_check_redirect(binding, url):
        if url == pcr._off_allowlist_origin(policy, policy["slots"]["slot-a"]):
            return {"ok": False, "reason": "wrong-token"}
        return real_redirect(binding, url)

    monkeypatch.setattr(pcr.pilot_boundary, "check_redirect", fake_check_redirect)
    record = pcr.boundary_refusals_exercise(
        inputs=_boundary_inputs(policy),
        now=EXERCISED_AT,
    )
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == pcr.REASON_BOUNDARY_EXPECTATION_UNMET


def test_boundary_refusals_protected_target_token(monkeypatch):
    policy = _sample_policy()
    real_target = pb.check_target

    def fake_check_target(binding, url):
        if url == "https://app.example.com:443":
            return {"ok": False, "reason": "wrong-token"}
        return real_target(binding, url)

    monkeypatch.setattr(pcr.pilot_boundary, "check_target", fake_check_target)
    record = pcr.boundary_refusals_exercise(
        inputs=_boundary_inputs(policy),
        now=EXERCISED_AT,
    )
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == pcr.REASON_BOUNDARY_EXPECTATION_UNMET


def test_boundary_refusals_non_local_origin_token(monkeypatch):
    policy = _sample_policy()

    def always_local(_origin):
        return True

    monkeypatch.setattr(pcr.pilot_boundary, "is_local_development_origin", always_local)
    record = pcr.boundary_refusals_exercise(
        inputs=_boundary_inputs(policy),
        now=EXERCISED_AT,
    )
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == pcr.REASON_BOUNDARY_EXPECTATION_UNMET


def test_boundary_refusals_protected_identity_token(monkeypatch):
    policy = _sample_policy()
    real_identity = pb.check_protected_identity

    def fake_check_protected_identity(binding, identity):
        if identity == "example_prod":
            return {"ok": False, "reason": "wrong-token"}
        return real_identity(binding, identity)

    monkeypatch.setattr(
        pcr.pilot_boundary,
        "check_protected_identity",
        fake_check_protected_identity,
    )
    record = pcr.boundary_refusals_exercise(
        inputs=_boundary_inputs(policy),
        now=EXERCISED_AT,
    )
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == pcr.REASON_BOUNDARY_EXPECTATION_UNMET


def test_boundary_refusals_non_local_declared_origin_fails():
    policy = _sample_policy()
    policy["slots"]["slot-a"]["origin"] = "https://production.invalid:443"
    record = pcr.boundary_refusals_exercise(
        inputs=_boundary_inputs(policy),
        now=EXERCISED_AT,
    )
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == pb.REFUSAL_TARGET_NOT_LOCAL
    report = pc.report([record])
    assert report["ok"] is False


def test_boundary_refusals_opaque_only_protected_targets():
    policy = _sample_policy(protectedTargets=["example_prod"])
    record = pcr.boundary_refusals_exercise(
        inputs=_boundary_inputs(policy),
        now=EXERCISED_AT,
    )
    assert record["result"] == pc.RESULT_PASS
    assert "protected URL leg skipped" in record["evidence"]
    assert "protected identity refused" in record["evidence"]


def test_boundary_refusals_url_only_protected_targets():
    policy = _sample_policy(protectedTargets=["https://app.example.com:443"])
    record = pcr.boundary_refusals_exercise(
        inputs=_boundary_inputs(policy),
        now=EXERCISED_AT,
    )
    assert record["result"] == pc.RESULT_PASS
    assert "protected URL refused" in record["evidence"]
    assert "protected identity leg skipped" in record["evidence"]


def test_boundary_refusals_both_protected_target_classes():
    policy = _sample_policy(
        protectedTargets=["https://app.example.com:443", "example_prod"]
    )
    record = pcr.boundary_refusals_exercise(
        inputs=_boundary_inputs(policy),
        now=EXERCISED_AT,
    )
    assert record["result"] == pc.RESULT_PASS
    assert "protected URL refused" in record["evidence"]
    assert "protected identity refused" in record["evidence"]


# --- horizon-validity ---------------------------------------------------------


def test_horizon_validity_skip_when_inputs_missing():
    record = pcr.horizon_validity_exercise(inputs={}, now=EXERCISED_AT)
    assert record["result"] == pc.RESULT_SKIPPED
    assert record["reason"] == pcr.REASON_INPUTS_MISSING


def test_horizon_validity_margin_covered_and_exceeded():
    record = pcr.horizon_validity_exercise(
        inputs=_horizon_inputs(_pilot_block(validityProvenance="server-probe")),
        now=EXERCISED_AT,
    )
    assert record["result"] == pc.RESULT_PASS
    assert "margin covered" in record["evidence"]
    assert "margin exceeded" in record["evidence"]
    assert "not applicable" in record["evidence"]


def test_horizon_validity_margin_covered_guard_required(monkeypatch):
    real_account_margin = ph.account_margin

    def fake_account_margin(observation, **kwargs):
        if observation.get("expiresAt", 0) >= kwargs["deadline_at"] + kwargs["margin_seconds"]:
            return {"ok": False, "reason": ph.REFUSAL_MARGIN_EXCEEDED}
        return real_account_margin(observation, **kwargs)

    monkeypatch.setattr(pcr.pilot_horizon, "account_margin", fake_account_margin)
    record = pcr.horizon_validity_exercise(
        inputs=_horizon_inputs(_pilot_block(validityProvenance="server-probe")),
        now=EXERCISED_AT,
    )
    assert record["result"] == pc.RESULT_FAIL
    assert "margin covered" not in record["evidence"]


def test_horizon_validity_margin_exceeded_token(monkeypatch):
    block = _pilot_block(validityProvenance="server-probe")
    real_account_margin = ph.account_margin

    def fake_account_margin(observation, **kwargs):
        if observation.get("expiresAt", 0) < kwargs["deadline_at"] + kwargs["margin_seconds"]:
            return {"ok": True, "reason": None}
        return real_account_margin(observation, **kwargs)

    monkeypatch.setattr(pcr.pilot_horizon, "account_margin", fake_account_margin)
    record = pcr.horizon_validity_exercise(
        inputs=_horizon_inputs(block),
        now=EXERCISED_AT,
    )
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == pcr.REASON_HORIZON_EXPECTATION_UNMET


def test_horizon_validity_malformed_observation_refused():
    record = pcr.horizon_validity_exercise(
        inputs=_horizon_inputs(_pilot_block(validityProvenance="server-probe")),
        now=EXERCISED_AT,
    )
    assert record["result"] == pc.RESULT_PASS
    assert "malformed observation refused" in record["evidence"]


def test_horizon_validity_unknown_provenance_unattended():
    record = pcr.horizon_validity_exercise(
        inputs=_horizon_inputs(_pilot_block(validityProvenance="unknown")),
        now=EXERCISED_AT,
    )
    assert record["result"] == pc.RESULT_PASS
    assert "unknown-provenance-unattended exercised" in record["evidence"]


# --- ownership-probe ----------------------------------------------------------


def test_ownership_probe_skip_without_live_effects_inputs():
    record = pcr.ownership_probe_exercise(inputs={}, now=EXERCISED_AT)
    assert record["result"] == pc.RESULT_SKIPPED
    assert record["reason"] == pcr.REASON_INPUTS_MISSING


def test_ownership_probe_undeclared_skip():
    policy = _sample_policy(ownershipProbe=None)
    record = pcr.ownership_probe_exercise(
        inputs={
            "ownership_probe": {
                "policy": policy,
                "pilot_block": _pilot_block(),
                "run_cwd": os.getcwd(),
                "connection_detail": policy["datastore"]["connectionDetail"],
            }
        },
        now=EXERCISED_AT,
    )
    assert record["result"] == pc.RESULT_SKIPPED
    assert record["reason"] == pcr.REASON_OWNERSHIP_PROBE_UNDECLARED


def test_ownership_probe_multi_account_pass(tmp_dir):
    command = _confined_ownership_probe_command(
        tmp_dir,
        "sys.stdout.write(json.dumps(dict(ownsNothing=True, account=_acct)))",
    )
    pilot_block = _pilot_block(
        credentialSet=[
            {"account": "owner", "role": "resource-owner"},
            {"account": "guest", "role": "guest"},
        ]
    )
    policy = _sample_policy(
        slots={
            "slot-a": {
                "origin": "http://127.0.0.1:5173",
                "permittedRedirects": ["http://127.0.0.1:5173"],
                "expectedIdentities": {
                    "owner": "pilot-owner@example.test",
                    "guest": "pilot-guest@example.test",
                },
            }
        }
    )
    record = _run_ownership_probe(tmp_dir, policy, pilot_block, command)
    assert record["result"] == pc.RESULT_PASS
    assert "guest" in record["evidence"]
    assert "owner" in record["evidence"].split("ownership probe exercised for accounts ", 1)[1].split(";")[0]
    assert pcr._OWNERSHIP_PROBE_LIMIT_VERBATIM in record["evidence"]


def test_ownership_probe_refuses_executable_inside_configured_reach_root(tmp_dir):
    reach_root = os.path.join(tmp_dir, "reach")
    os.makedirs(reach_root, exist_ok=True)
    probe_py = os.path.join(reach_root, "ownership_probe.py")
    with open(probe_py, "w", encoding="utf-8") as handle:
        handle.write(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "_acct = sys.argv[1]\n"
            "sys.stdout.write(json.dumps(dict(ownsNothing=True, account=_acct)))\n"
        )
    os.chmod(probe_py, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    command = [probe_py, pp.ACCOUNT_PLACEHOLDER]
    record = _run_ownership_probe(
        tmp_dir,
        _sample_policy(),
        _pilot_block(),
        command,
        reach_roots=[reach_root],
    )
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == pb.REFUSAL_DATASTORE_OBSERVER_INVALID


def test_ownership_probe_nonzero_exit(tmp_dir):
    command = _confined_ownership_probe_command(tmp_dir, "pass", exit_code=1)
    record = _run_ownership_probe(tmp_dir, _sample_policy(), _pilot_block(), command)
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == pcr.REASON_OWNERSHIP_PROBE_REFUSED


def test_ownership_probe_exit_zero_unparseable_body(tmp_dir):
    command = _confined_ownership_probe_command(tmp_dir, 'sys.stdout.write("started")')
    record = _run_ownership_probe(tmp_dir, _sample_policy(), _pilot_block(), command)
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == pcr.REASON_OWNERSHIP_PROBE_ANSWER_INVALID
    assert "merely started" in record["evidence"]


def test_ownership_probe_exit_zero_owns_nothing_false(tmp_dir):
    command = _confined_ownership_probe_command(
        tmp_dir,
        "sys.stdout.write(json.dumps(dict(ownsNothing=False, account=_acct)))",
    )
    record = _run_ownership_probe(tmp_dir, _sample_policy(), _pilot_block(), command)
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == pcr.REASON_OWNERSHIP_PROBE_ANSWER_INVALID


def test_ownership_probe_exit_zero_owns_nothing_absent(tmp_dir):
    command = _confined_ownership_probe_command(
        tmp_dir, "sys.stdout.write(json.dumps(dict(account=_acct)))"
    )
    record = _run_ownership_probe(tmp_dir, _sample_policy(), _pilot_block(), command)
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == pcr.REASON_OWNERSHIP_PROBE_ANSWER_INVALID


def test_ownership_probe_exit_zero_owns_nothing_string_true(tmp_dir):
    command = _confined_ownership_probe_command(
        tmp_dir,
        'sys.stdout.write(json.dumps(dict(ownsNothing="true", account=_acct)))',
    )
    record = _run_ownership_probe(tmp_dir, _sample_policy(), _pilot_block(), command)
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == pcr.REASON_OWNERSHIP_PROBE_ANSWER_INVALID


def test_ownership_probe_exit_zero_json_array_body(tmp_dir):
    command = _confined_ownership_probe_command(
        tmp_dir,
        "sys.stdout.write(json.dumps([dict(ownsNothing=True, account=_acct)]))",
    )
    record = _run_ownership_probe(tmp_dir, _sample_policy(), _pilot_block(), command)
    assert record["result"] == pc.RESULT_FAIL
    assert record["reason"] == pcr.REASON_OWNERSHIP_PROBE_ANSWER_INVALID


def test_resolve_inputs_ownership_probe_absent_without_live_effects(tmp_path):
    inputs, resolution = pc.resolve_inputs(str(tmp_path), now=EXERCISED_AT)
    assert "ownership_probe" not in inputs
    by_input = {entry["input"]: entry for entry in resolution}
    assert by_input["ownership-probe"]["state"] == "absent"
    assert (
        by_input["ownership-probe"]["reason"]
        == pc.REASON_INPUT_LIVE_EFFECTS_NOT_PERMITTED
    )


def test_default_run_ownership_probe_surface_unexercised():
    report = pc.run(pc.default_exercises(), inputs={}, now=EXERCISED_AT)
    assert "pilot_policy.ownership_probe_request" in report["unexercised"]


# --- ownership_probe_request unit tests ---------------------------------------


def test_ownership_probe_request_refuses_when_undeclared():
    with pytest.raises(pp.PilotPolicyError) as exc:
        pp.ownership_probe_request(_sample_policy(ownershipProbe=None), "owner")
    assert exc.value.reason == pp.REFUSAL_DOCUMENT_INVALID


def test_ownership_probe_request_refuses_invalid_account_grammar():
    policy = _policy_with_probe(
        [sys.executable, "--account", pp.ACCOUNT_PLACEHOLDER]
    )
    with pytest.raises(pp.PilotPolicyError) as exc:
        pp.ownership_probe_request(policy, "--admin")
    assert exc.value.reason == pp.REFUSAL_OWNERSHIP_PROBE_ACCOUNT_INVALID


def test_ownership_probe_request_refuses_undeclared_account():
    policy = _policy_with_probe(
        [sys.executable, "--account", pp.ACCOUNT_PLACEHOLDER]
    )
    with pytest.raises(pp.PilotPolicyError) as exc:
        pp.ownership_probe_request(policy, "intruder")
    assert exc.value.reason == pp.REFUSAL_OWNERSHIP_PROBE_ACCOUNT_UNDECLARED


def test_ownership_probe_request_never_substitutes_argv0():
    command = [sys.executable, "--account", pp.ACCOUNT_PLACEHOLDER]
    policy = _policy_with_probe(command)
    request = pp.ownership_probe_request(policy, "owner")
    assert request["argv"][0] == command[0]
    assert pp.ACCOUNT_PLACEHOLDER not in request["argv"][0]


def test_ownership_probe_request_resolves_argv1_plus():
    policy = _policy_with_probe(
        [sys.executable, "--account", pp.ACCOUNT_PLACEHOLDER]
    )
    request = pp.ownership_probe_request(policy, "owner")
    assert request["argv"][0] == sys.executable
    assert request["argv"][1] == "--account"
    assert request["argv"][2] == "owner"
    assert request["connectionEnvVar"] == "PILOT_DB_URL"
