"""Tests for pilot_mint.py — authorized mint client, flag scope, gate-off, sentinel."""
import ast
import inspect
import json
import os
import signal
import subprocess
import sys
import threading
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_boundary  # noqa: E402
import pilot_contract  # noqa: E402
import pilot_journal as pj  # noqa: E402
import pilot_mint as pm  # noqa: E402
import pilot_probe  # noqa: E402
import pilot_provision as pp  # noqa: E402
import pilot_seed  # noqa: E402
import pilot_slot  # noqa: E402
from grandchild_probe import (  # noqa: E402
    _observed_process_state,
    _wait_for_process_gone,
    cleanup_grandchild_on_exit,
    probe_grandchild,
)

NOW = "2026-01-01T00:00:00Z"

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

SAMPLE_ENVELOPE = {
    "enablingFlagEnvVar": "PILOT_MINT_ENABLED",
    "enabledScopes": ["ci", "local"],
    "forbiddenScopes": ["prod"],
    "gateOffTestCommand": [sys.executable, "-c", "import sys; sys.exit(0)"],
}

HOSTILE_VALUES = [
    None, [], {}, 0, True, "", set(), object(), [[]], {"k": set()},
]


def _digest(policy):
    return pilot_contract.declaration_digest(policy)


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


def _journal_path(private_tmp):
    return os.path.join(private_tmp, "journal.jsonl")


def _read_journal_lines(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _mint_kwargs(private_tmp, transport):
    return {
        "verdict": _passing_verdict(SAMPLE_POLICY),
        "policy": SAMPLE_POLICY,
        "slot_ref": "slot-a@1",
        "account": "pilot-owner",
        "envelope": dict(SAMPLE_ENVELOPE),
        "transport": transport,
        "journal_path": _journal_path(private_tmp),
        "at": NOW,
    }


# --- flag_scope_check --------------------------------------------------------

def test_edge1_empty_observed_scopes_refuses():
    result = pm.flag_scope_check(SAMPLE_ENVELOPE, observed_scopes={})
    assert result["ok"] is False
    assert result["reason"] == pm.REFUSAL_OBSERVED_SCOPES_INVALID


def test_edge2_flag_set_in_forbidden_scope_disqualifies():
    result = pm.flag_scope_check(
        SAMPLE_ENVELOPE,
        observed_scopes={"prod": True, "ci": False, "local": False},
    )
    assert result["ok"] is False
    assert result["reason"] == pm.REFUSAL_FLAG_SET_OUTSIDE_DECLARED_SCOPE
    assert result["offendingScopes"] == ["prod"]


def test_edge3_flag_set_in_undeclared_scope_disqualifies():
    result = pm.flag_scope_check(
        SAMPLE_ENVELOPE,
        observed_scopes={"staging": True, "ci": False},
    )
    assert result["ok"] is False
    assert result["reason"] == pm.REFUSAL_FLAG_SET_OUTSIDE_DECLARED_SCOPE
    assert result["offendingScopes"] == ["staging"]


def test_edge4_two_offending_scopes_both_listed():
    result = pm.flag_scope_check(
        SAMPLE_ENVELOPE,
        observed_scopes={"prod": True, "staging": True, "ci": False},
    )
    assert result["offendingScopes"] == ["prod", "staging"]


def test_edge5_flag_unset_everywhere_ok():
    result = pm.flag_scope_check(
        SAMPLE_ENVELOPE,
        observed_scopes={"ci": False, "local": False, "prod": False, "staging": False},
    )
    assert result == {"ok": True, "reason": None, "offendingScopes": []}


def test_flag_scope_check_malformed_envelope():
    result = pm.flag_scope_check(None, observed_scopes={"ci": False})
    assert result["reason"] == pm.REFUSAL_ENVELOPE_INCOMPLETE


def test_flag_scope_check_invalid_observed_scopes():
    result = pm.flag_scope_check(SAMPLE_ENVELOPE, observed_scopes=None)
    assert result["reason"] == pm.REFUSAL_OBSERVED_SCOPES_INVALID


@pytest.mark.parametrize("hostile", HOSTILE_VALUES)
def test_flag_scope_check_never_raises_builtin(hostile):
    try:
        result = pm.flag_scope_check(hostile, observed_scopes={"ci": False})
    except Exception as exc:
        assert type(exc) is pm.PilotMintError
        return
    assert result["ok"] is False
    try:
        result = pm.flag_scope_check(SAMPLE_ENVELOPE, observed_scopes=hostile)
    except Exception as exc:
        assert type(exc) is pm.PilotMintError
        return
    assert result["ok"] is False


# --- run_gate_off_test -------------------------------------------------------

def test_edge6_gate_off_removes_flag_from_environment(private_tmp):
    envelope = dict(SAMPLE_ENVELOPE)
    envelope["gateOffTestCommand"] = [
        sys.executable, "-c",
        "import os, json; print(json.dumps(dict(os.environ)))",
    ]
    env = {"PILOT_MINT_ENABLED": "1", "OTHER": "x"}
    result = pm.run_gate_off_test(
        envelope,
        run_cwd=private_tmp,
        environment=env,
    )
    assert result["ok"] is True
    passed_env = json.loads(result["stdout"])
    assert "PILOT_MINT_ENABLED" not in passed_env
    assert passed_env.get("OTHER") == "x"
    assert env["PILOT_MINT_ENABLED"] == "1"


def test_edge7_gate_off_nonzero_exit(private_tmp):
    envelope = dict(SAMPLE_ENVELOPE)
    envelope["gateOffTestCommand"] = [sys.executable, "-c", "import sys; sys.exit(3)"]
    result = pm.run_gate_off_test(
        envelope,
        run_cwd=private_tmp,
        environment={},
    )
    assert result["ok"] is False
    assert result["reason"] == pm.REFUSAL_GATE_OFF_TEST_FAILED
    assert result["exitCode"] == 3


def test_edge8_gate_off_timeout_reaps_child(private_tmp):
    envelope = dict(SAMPLE_ENVELOPE)
    envelope["gateOffTestCommand"] = [
        sys.executable, "-c", "import time; time.sleep(30)",
    ]
    result = pm.run_gate_off_test(
        envelope,
        run_cwd=private_tmp,
        environment={},
        timeout_seconds=1,
    )
    assert result["ok"] is False
    assert result["reason"] == pm.REFUSAL_GATE_OFF_TIMEOUT
    time.sleep(0.2)
    assert subprocess.run(
        ["pgrep", "-f", "time.sleep(30)"],
        capture_output=True,
    ).returncode != 0


def test_gate_off_pass_with_real_command(private_tmp):
    envelope = dict(SAMPLE_ENVELOPE)
    envelope["gateOffTestCommand"] = [
        sys.executable, "-c",
        "import os; assert 'PILOT_MINT_ENABLED' not in os.environ",
    ]
    result = pm.run_gate_off_test(
        envelope,
        run_cwd=private_tmp,
        environment={"PILOT_MINT_ENABLED": "1"},
    )
    assert result["ok"] is True


def test_gate_off_invalid_cwd():
    result = pm.run_gate_off_test(SAMPLE_ENVELOPE, run_cwd="/no/such/dir", environment={})
    assert result["reason"] == pm.REFUSAL_GATE_OFF_CWD_INVALID


def test_gate_off_invalid_environment(private_tmp):
    result = pm.run_gate_off_test(SAMPLE_ENVELOPE, run_cwd=private_tmp, environment={1: "x"})
    assert result["reason"] == pm.REFUSAL_GATE_OFF_ENVIRONMENT_INVALID


def test_gate_off_invalid_command(private_tmp):
    envelope = dict(SAMPLE_ENVELOPE)
    envelope["gateOffTestCommand"] = []
    result = pm.run_gate_off_test(envelope, run_cwd=private_tmp, environment={})
    assert result["reason"] == pm.REFUSAL_ENVELOPE_INCOMPLETE


def test_gate_off_output_oversize(private_tmp):
    envelope = dict(SAMPLE_ENVELOPE)
    envelope["gateOffTestCommand"] = [
        sys.executable, "-c", "print('x' * 100)",
    ]
    result = pm.run_gate_off_test(
        envelope, run_cwd=private_tmp, environment={}, max_output_bytes=10,
    )
    assert result["reason"] == pm.REFUSAL_GATE_OFF_OUTPUT_OVERSIZE


@pytest.mark.parametrize("hostile", HOSTILE_VALUES)
def test_run_gate_off_test_never_raises_builtin(private_tmp, hostile):
    result = pm.run_gate_off_test(
        hostile,
        run_cwd=private_tmp,
        environment={},
    )
    assert result["ok"] is False


# --- gate_off_receipt --------------------------------------------------------

def test_edge9_failed_gate_off_receipt_not_exercised():
    run_result = {"ok": False, "exitCode": 1, "reason": pm.REFUSAL_GATE_OFF_TEST_FAILED}
    record = pm.gate_off_receipt(SAMPLE_ENVELOPE, run_result, exercised_at=NOW)
    assert record["receipt"]["result"] == "fail"
    registry = {"schemaVersion": pilot_contract.REGISTRY_SCHEMA_VERSION, "records": [record]}
    assert pilot_contract.is_exercised(registry, "mint-gate-off", SAMPLE_ENVELOPE) is False


def test_edge10_modified_envelope_digest_binding():
    run_result = {"ok": True, "exitCode": 0, "reason": None}
    record = pm.gate_off_receipt(SAMPLE_ENVELOPE, run_result, exercised_at=NOW)
    registry = {"schemaVersion": pilot_contract.REGISTRY_SCHEMA_VERSION, "records": [record]}
    assert pilot_contract.is_exercised(registry, "mint-gate-off", SAMPLE_ENVELOPE) is True
    modified = dict(SAMPLE_ENVELOPE)
    modified["enabledScopes"] = list(SAMPLE_ENVELOPE["enabledScopes"]) + ["extra"]
    assert pilot_contract.is_exercised(registry, "mint-gate-off", modified) is False


def test_gate_off_receipt_pass():
    run_result = {"ok": True, "exitCode": 0, "reason": None}
    record = pm.gate_off_receipt(SAMPLE_ENVELOPE, run_result, exercised_at=NOW)
    assert record["kind"] == "mint-gate-off"
    assert record["receipt"]["result"] == "pass"
    assert record["receipt"]["evidence"]
    assert "stdout" not in record["receipt"]["evidence"]


def test_gate_off_receipt_invalid_exercised_at():
    with pytest.raises(pm.PilotMintError) as exc:
        pm.gate_off_receipt(SAMPLE_ENVELOPE, {"ok": True}, exercised_at="")
    assert exc.value.reason == pm.REFUSAL_RECEIPT_ARGUMENT_INVALID


def test_require_gate_off_delegates():
    run_result = {"ok": True, "exitCode": 0, "reason": None}
    record = pm.gate_off_receipt(SAMPLE_ENVELOPE, run_result, exercised_at=NOW)
    registry = {"schemaVersion": pilot_contract.REGISTRY_SCHEMA_VERSION, "records": [record]}
    pm.require_gate_off(registry, SAMPLE_ENVELOPE)


# --- authorized_mint ---------------------------------------------------------

def test_edge11_refused_verdict_never_calls_transport(private_tmp, monkeypatch):
    transport_calls = []

    def transport(_desc):
        transport_calls.append(True)
        return {"status": 200, "body": "cred"}

    verdict = _passing_verdict(SAMPLE_POLICY)
    verdict["result"] = "refuse"
    with pytest.raises(pilot_boundary.PilotBoundaryError):
        pm.authorized_mint(
            verdict,
            SAMPLE_POLICY,
            "slot-a@1",
            "pilot-owner",
            SAMPLE_ENVELOPE,
            transport=transport,
            journal_path=_journal_path(private_tmp),
            at=NOW,
        )
    assert transport_calls == []


def test_edge12_account_not_in_allowlist_never_calls_transport(private_tmp, monkeypatch):
    transport_calls = []

    def transport(_desc):
        transport_calls.append(True)
        return {"status": 200, "body": "cred"}

    kwargs = _mint_kwargs(private_tmp, transport)
    kwargs["account"] = "not-on-allowlist"
    with pytest.raises(pilot_seed.PilotSeedError) as exc:
        pm.authorized_mint(**kwargs)
    assert transport_calls == []
    assert exc.value.reason == pilot_seed.REFUSAL_MINT_ACCOUNT_NOT_IN_ALLOWLIST


def test_edge13_transport_raises_indeterminate_journal(private_tmp):
    def transport(_desc):
        raise RuntimeError("network down")

    result = pm.authorized_mint(**_mint_kwargs(private_tmp, transport))
    assert result["ok"] is False
    assert result["reason"] == pilot_probe.REASON_TRANSPORT_ERROR
    lines = _read_journal_lines(_journal_path(private_tmp))
    end = [r for r in lines if r.get("phase") == pj.PHASE_END][-1]
    assert end["outcome"] == pj.OUTCOME_INDETERMINATE


@pytest.mark.parametrize(
    "status,expected_reason,journal_outcome",
    [
        (401, pilot_probe.REASON_UNAUTHORIZED, pj.OUTCOME_NOT_APPLIED),
        (403, pilot_probe.REASON_FORBIDDEN, pj.OUTCOME_NOT_APPLIED),
        (429, pilot_probe.REASON_RATE_LIMITED, pj.OUTCOME_INDETERMINATE),
        (500, pilot_probe.REASON_INFRASTRUCTURE_UNAVAILABLE, pj.OUTCOME_INDETERMINATE),
        (418, pilot_probe.REASON_UNEXPECTED_STATUS, pj.OUTCOME_INDETERMINATE),
    ],
)
def test_edge14_status_classification_and_journal(
    private_tmp, status, expected_reason, journal_outcome,
):
    def transport(_desc):
        return {"status": status, "body": "x"}

    result = pm.authorized_mint(**_mint_kwargs(private_tmp, transport))
    assert result["ok"] is False
    assert result["reason"] == expected_reason
    lines = _read_journal_lines(_journal_path(private_tmp))
    end = [r for r in lines if r.get("phase") == pj.PHASE_END][-1]
    assert end["outcome"] == journal_outcome


def test_edge15_success_journals_applied_with_begin_before_transport(private_tmp):
    call_order = []

    def transport(_desc):
        call_order.append("transport")
        lines = _read_journal_lines(_journal_path(private_tmp))
        begins = [r for r in lines if r.get("phase") == pj.PHASE_BEGIN]
        assert len(begins) == 1
        return {"status": 200, "body": "credential-token"}

    result = pm.authorized_mint(**_mint_kwargs(private_tmp, transport))
    assert result["ok"] is True
    assert call_order == ["transport"]
    lines = _read_journal_lines(_journal_path(private_tmp))
    end = [r for r in lines if r.get("phase") == pj.PHASE_END][-1]
    assert end["outcome"] == pj.OUTCOME_APPLIED


def test_authorized_mint_invalid_transport(private_tmp):
    kwargs = _mint_kwargs(private_tmp, None)
    kwargs["transport"] = None
    with pytest.raises(pm.PilotMintError) as exc:
        pm.authorized_mint(**kwargs)
    assert exc.value.reason == pm.REFUSAL_TRANSPORT_INVALID


def test_classify_mint_response_direct():
    assert pm._classify_mint_response({"status": 200, "body": "x"})["ok"] is True
    assert pm._classify_mint_response({"status": 200, "body": ""})["ok"] is False
    assert pm._classify_mint_response("not-a-dict")["reason"] == pilot_probe.REASON_INVALID_BODY


@pytest.mark.parametrize("hostile", HOSTILE_VALUES)
def test_authorized_mint_never_raises_builtin(private_tmp, hostile):
    with pytest.raises((pm.PilotMintError, pilot_boundary.PilotBoundaryError,
                         pilot_seed.PilotSeedError, pp.PilotProvisionError,
                         pilot_slot.PilotSlotError)):
        pm.authorized_mint(
            hostile,
            SAMPLE_POLICY,
            "slot-a@1",
            "pilot-owner",
            SAMPLE_ENVELOPE,
            transport=lambda d: {"status": 200, "body": "x"},
            journal_path=_journal_path(private_tmp),
            at=NOW,
        )


# --- sentinel_exercise -------------------------------------------------------

def _sentinel_kwargs(private_tmp, transport):
    return {
        "verdict": _passing_verdict(SAMPLE_POLICY),
        "policy": SAMPLE_POLICY,
        "slot_ref": "slot-a@1",
        "envelope": dict(SAMPLE_ENVELOPE),
        "control_account": "pilot-owner",
        "sentinel": "pilot-sentinel-no-such-account",
        "transport": transport,
        "journal_path": _journal_path(private_tmp),
        "at": NOW,
    }


def test_edge16_control_failure_skips_sentinel(private_tmp):
    calls = []

    def transport(desc):
        calls.append(desc)
        if "account" in desc:
            return {"status": 403, "body": ""}
        return {"status": 403, "body": ""}

    result = pm.sentinel_exercise(**_sentinel_kwargs(private_tmp, transport))
    assert result["outcome"] == pm.OUTCOME_INCONCLUSIVE
    assert result["reason"] == pm.REFUSAL_CONTROL_DID_NOT_MINT
    assert len(calls) == 1


def test_edge17_sentinel_2xx_disqualifying(private_tmp):
    def transport(desc):
        if "account" in desc:
            return {"status": 200, "body": "control-cred"}
        return {"status": 201, "body": "sentinel-cred"}

    result = pm.sentinel_exercise(**_sentinel_kwargs(private_tmp, transport))
    assert result["outcome"] == pm.OUTCOME_MINTED
    assert result["ok"] is False
    assert result["reason"] == pm.REFUSAL_SENTINEL_MINTED
    lines = _read_journal_lines(_journal_path(private_tmp))
    ends = [r for r in lines if r.get("phase") == pj.PHASE_END]
    assert ends[-1]["outcome"] == pj.OUTCOME_APPLIED


def test_edge18_sentinel_404_inconclusive_not_refused(private_tmp):
    def transport(desc):
        if "account" in desc:
            return {"status": 200, "body": "control-cred"}
        return {"status": 404, "body": ""}

    result = pm.sentinel_exercise(**_sentinel_kwargs(private_tmp, transport))
    assert result["outcome"] == pm.OUTCOME_INCONCLUSIVE
    assert result["ok"] is False
    assert result["reason"] == pm.REFUSAL_SENTINEL_ENDPOINT_ABSENT


def test_gate_off_invalid_envelope_reports_incomplete(private_tmp):
    result = pm.run_gate_off_test(None, run_cwd=private_tmp, environment={})
    assert result["reason"] == pm.REFUSAL_ENVELOPE_INCOMPLETE

    bad_scope = dict(SAMPLE_ENVELOPE)
    bad_scope["enabledScopes"] = "not-a-list"
    result = pm.run_gate_off_test(bad_scope, run_cwd=private_tmp, environment={})
    assert result["reason"] == pm.REFUSAL_ENVELOPE_INCOMPLETE


def test_gate_off_spawn_failed(private_tmp):
    envelope = dict(SAMPLE_ENVELOPE)
    envelope["gateOffTestCommand"] = ["/no/such/executable-pilot-mint-test"]
    result = pm.run_gate_off_test(envelope, run_cwd=private_tmp, environment={})
    assert result["reason"] == pm.REFUSAL_GATE_OFF_SPAWN_FAILED


# axis: a NUL in the argv or in the environment refuses by NAME instead of escaping as an
# uncaught ValueError out of run_gate_off_test. Popen — not the validators — is where these are
# rejected, so before #866's shared runner caught ValueError this call raised. (#866 brief check.)
@pytest.mark.parametrize(
    ("envelope_command", "environment"),
    [
        ([sys.executable, "-c", "import sys\x00"], {}),
        ([sys.executable, "-c", "pass"], {"PILOT_NUL\x00VAR": "x"}),
        ([sys.executable, "-c", "pass"], {"PILOT_OK": "value\x00with-nul"}),
    ],
)
def test_gate_off_nul_bearing_input_refuses_by_name(private_tmp, envelope_command, environment):
    envelope = dict(SAMPLE_ENVELOPE)
    envelope["gateOffTestCommand"] = envelope_command
    result = pm.run_gate_off_test(
        envelope, run_cwd=private_tmp, environment=environment,
    )
    assert result["ok"] is False
    assert result["reason"] == pm.REFUSAL_GATE_OFF_SPAWN_FAILED
    assert result["exitCode"] is None


def test_gate_off_invalid_bounds(private_tmp):
    result = pm.run_gate_off_test(
        SAMPLE_ENVELOPE, run_cwd=private_tmp, environment={}, timeout_seconds=None,
    )
    assert result["reason"] == pm.REFUSAL_GATE_OFF_ARGUMENT_INVALID

    result = pm.run_gate_off_test(
        SAMPLE_ENVELOPE, run_cwd=private_tmp, environment={}, max_output_bytes=-2,
    )
    assert result["reason"] == pm.REFUSAL_GATE_OFF_ARGUMENT_INVALID


def test_gate_off_grandchild_timeout_reaps_process_group(private_tmp):
    def script_body(pid_file):
        # Mint command is Python argv, not shell — deliberate no-op fixture file.
        return "#!/bin/sh\ntrue\n"

    def run(target, timeout_seconds):
        pid_path = target.pid_path
        envelope = dict(SAMPLE_ENVELOPE)
        envelope["gateOffTestCommand"] = [
            sys.executable, "-c",
            "import os, signal, subprocess, sys; "
            "pid_path = sys.argv[1]; "
            "subprocess.Popen([sys.executable, '-c', "
            "'import os, signal, sys, time, tempfile; "
            "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
            "pid_path = sys.argv[1]; "
            "fd, tmp = tempfile.mkstemp(dir=os.path.dirname(pid_path) or \".\"); "
            "os.write(fd, str(os.getpid()).encode()); "
            "os.close(fd); "
            "os.replace(tmp, pid_path); "
            "time.sleep(120)', "
            "pid_path], stdout=sys.stdout); "
            "os._exit(0)",
            pid_path,
        ]
        result_holder = {}

        def _run_gate_off():
            result_holder["result"] = pm.run_gate_off_test(
                envelope,
                run_cwd=private_tmp,
                environment={},
                timeout_seconds=timeout_seconds,
            )

        runner = threading.Thread(target=_run_gate_off)
        runner.start()
        runner.join(timeout=timeout_seconds + 10)
        assert runner.is_alive() is False, "run_gate_off_test did not finish"
        return result_holder["result"]

    probe = probe_grandchild(tmp_dir=private_tmp, script_body=script_body, run=run)
    with cleanup_grandchild_on_exit(probe.pid):
        assert probe.result["reason"] == pm.REFUSAL_GATE_OFF_TIMEOUT
        if not _wait_for_process_gone(probe.pid, timeout=10):
            state = _observed_process_state(probe.pid)
            detail = f"observed state: {state}"
            try:
                detail += f"; pgid={os.getpgid(probe.pid)}"
            except (ProcessLookupError, PermissionError):
                pass
            pytest.fail(
                f"grandchild pid {probe.pid} still alive after gate-off timeout reap; {detail}"
            )


def test_gate_off_receipt_pass_requires_exit_code_zero():
    with pytest.raises(pm.PilotMintError) as exc:
        pm.gate_off_receipt(
            SAMPLE_ENVELOPE,
            {"ok": True, "exitCode": 99},
            exercised_at=NOW,
        )
    assert exc.value.reason == pm.REFUSAL_RECEIPT_ARGUMENT_INVALID


def test_gate_off_receipt_pass_requires_reason_none():
    with pytest.raises(pm.PilotMintError) as exc:
        pm.gate_off_receipt(
            SAMPLE_ENVELOPE,
            {"ok": True, "exitCode": 0, "reason": pm.REFUSAL_GATE_OFF_TEST_FAILED},
            exercised_at=NOW,
        )
    assert exc.value.reason == pm.REFUSAL_RECEIPT_ARGUMENT_INVALID


def test_gate_off_receipt_requires_exit_code():
    with pytest.raises(pm.PilotMintError) as exc:
        pm.gate_off_receipt(SAMPLE_ENVELOPE, {"ok": True}, exercised_at=NOW)
    assert exc.value.reason == pm.REFUSAL_RECEIPT_ARGUMENT_INVALID


def test_gate_off_receipt_evidence_from_actual_exit_code():
    run_result = {"ok": True, "exitCode": 0, "reason": None}
    record = pm.gate_off_receipt(SAMPLE_ENVELOPE, run_result, exercised_at=NOW)
    assert record["receipt"]["evidence"] == "exitCode=0"


def test_gate_off_receipt_non_serializable_envelope():
    with pytest.raises(pm.PilotMintError) as exc:
        pm.gate_off_receipt({"k": set()}, {"ok": True, "exitCode": 0}, exercised_at=NOW)
    assert exc.value.reason == pm.REFUSAL_RECEIPT_ARGUMENT_INVALID


PINNED_REFUSAL_STATUSES = {400, 401, 403, 409, 422}


def test_refusal_statuses_pinned_membership():
    assert pm.REFUSAL_STATUSES == {400, 403, 409, 422}
    assert PINNED_REFUSAL_STATUSES - pm.REFUSAL_STATUSES == {401}


def test_sentinel_401_inconclusive(private_tmp):
    def transport(desc):
        if "account" in desc:
            return {"status": 200, "body": "control-cred"}
        return {"status": 401, "body": ""}

    result = pm.sentinel_exercise(**_sentinel_kwargs(private_tmp, transport))
    assert result["outcome"] == pm.OUTCOME_INCONCLUSIVE
    assert result["reason"] == pilot_probe.REASON_UNAUTHORIZED


def test_sentinel_429_inconclusive(private_tmp):
    def transport(desc):
        if "account" in desc:
            return {"status": 200, "body": "control-cred"}
        return {"status": 429, "body": ""}

    result = pm.sentinel_exercise(**_sentinel_kwargs(private_tmp, transport))
    assert result["outcome"] == pm.OUTCOME_INCONCLUSIVE
    assert result["reason"] == pilot_probe.REASON_RATE_LIMITED


def test_sentinel_setup_failure_preserves_control(private_tmp):
    import copy
    policy = copy.deepcopy(SAMPLE_POLICY)
    policy["slots"]["slot-a"]["mintableAccounts"].append("pilot-sentinel-no-such-account")

    def transport(desc):
        return {"status": 200, "body": "control-cred"}

    kwargs = _sentinel_kwargs(private_tmp, transport)
    kwargs["policy"] = policy
    kwargs["verdict"] = _passing_verdict(policy)
    kwargs["sentinel"] = "pilot-sentinel-no-such-account"
    result = pm.sentinel_exercise(**kwargs)
    assert result["outcome"] == pm.OUTCOME_INCONCLUSIVE
    assert result["reason"] == pm.REFUSAL_SENTINEL_SETUP_FAILED
    assert result["control"]["ok"] is True


@pytest.mark.parametrize("status", sorted(pm.REFUSAL_STATUSES))
def test_edge19_sentinel_refusal_statuses_ok(private_tmp, status):
    def transport(desc):
        if "account" in desc:
            return {"status": 200, "body": "control-cred"}
        return {"status": status, "body": ""}

    result = pm.sentinel_exercise(**_sentinel_kwargs(private_tmp, transport))
    assert result["outcome"] == pm.OUTCOME_REFUSED
    assert result["ok"] is True
    assert result["status"] == status


def test_edge20_sentinel_500_and_transport_raise_inconclusive(private_tmp):
    def transport_500(desc):
        if "account" in desc:
            return {"status": 200, "body": "control-cred"}
        return {"status": 500, "body": ""}

    result = pm.sentinel_exercise(**_sentinel_kwargs(private_tmp, transport_500))
    assert result["outcome"] == pm.OUTCOME_INCONCLUSIVE
    assert result["reason"] == pilot_probe.REASON_INFRASTRUCTURE_UNAVAILABLE

    def transport_raise(desc):
        if "account" in desc:
            return {"status": 200, "body": "control-cred"}
        raise OSError("down")

    result = pm.sentinel_exercise(**_sentinel_kwargs(private_tmp, transport_raise))
    assert result["outcome"] == pm.OUTCOME_INCONCLUSIVE
    assert result["reason"] == pilot_probe.REASON_TRANSPORT_ERROR


def test_edge21_unverified_declarations_always_present(private_tmp):
    def transport(desc):
        if "account" in desc:
            return {"status": 200, "body": "control-cred"}
        return {"status": 403, "body": ""}

    result = pm.sentinel_exercise(**_sentinel_kwargs(private_tmp, transport))
    assert pm._UNVERIFIED_SENTINEL_DECLARATION in result["unverifiedDeclarations"]


def test_sentinel_unexpected_status_inconclusive(private_tmp):
    def transport(desc):
        if "account" in desc:
            return {"status": 200, "body": "control-cred"}
        return {"status": 418, "body": ""}

    result = pm.sentinel_exercise(**_sentinel_kwargs(private_tmp, transport))
    assert result["outcome"] == pm.OUTCOME_INCONCLUSIVE
    assert result["reason"] == pm.REFUSAL_SENTINEL_UNEXPECTED_STATUS


# --- never-sets-the-flag AST census ------------------------------------------

def _pilot_mint_source_path():
    return os.path.join(_LIB, "pilot_mint.py")


def _parse_pilot_mint_tree():
    with open(_pilot_mint_source_path(), encoding="utf-8") as handle:
        return ast.parse(handle.read(), filename="pilot_mint.py")


def _is_os_environ_subscript(node):
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "os"
        and node.value.attr == "environ"
    )


def _is_os_putenv_call(node):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "os"
        and node.func.attr == "putenv"
    )


def _is_environ_mutator_call(node):
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False
    if not isinstance(func.value, ast.Attribute):
        return False
    if not isinstance(func.value.value, ast.Name):
        return False
    if func.value.value.id != "os" or func.value.attr != "environ":
        return False
    return func.attr in ("update", "setdefault", "pop")


def _is_subprocess_call_with_env(node):
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        if not isinstance(func.value, ast.Name) or func.value.id != "subprocess":
            return False
    elif isinstance(func, ast.Name):
        if func.id != "Popen":
            return False
    else:
        return False
    for keyword in node.keywords:
        if keyword.arg == "env":
            return True
    return False


def test_module_never_sets_the_enabling_flag():
    tree = _parse_pilot_mint_tree()
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if _is_os_environ_subscript(target):
                    violations.append("assign to os.environ[%s]" % ast.dump(target))
        if _is_os_putenv_call(node):
            violations.append("os.putenv call at line %d" % node.lineno)
        if _is_environ_mutator_call(node):
            violations.append("os.environ mutator at line %d" % node.lineno)
        if _is_subprocess_call_with_env(node):
            if not (isinstance(node.func, ast.Attribute)
                    and node.func.attr == "Popen"):
                violations.append("subprocess env= at line %d" % node.lineno)
    assert violations == []


def test_public_api_surfaces_exist():
    for name in (
        "flag_scope_check", "run_gate_off_test", "gate_off_receipt",
        "require_gate_off", "authorized_mint", "sentinel_exercise",
    ):
        assert callable(getattr(pm, name))
