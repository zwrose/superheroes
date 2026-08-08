"""Tests for pilot_conformance_cleanup.py — cleanup end-to-end conformance exercise.

Canonical cleanup harness construction for conformance tests lives in this module;
test_pilot_cleanup_integration.py duplicates a similar layout for integration tests.
"""
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_cleanup as pc  # noqa: E402
import pilot_conformance  # noqa: E402
import pilot_conformance_cleanup as pcc  # noqa: E402
import pilot_contract  # noqa: E402
import pilot_slot  # noqa: E402

_NOW = "2026-08-07T12:00:00Z"
_SLOT_REF = "slot-a@1"


def _write_executable(path, content):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    os.chmod(path, 0o700)


def _confinement_layout(private_tmp):
    reach_root = os.path.join(private_tmp, "reach")
    run_cwd = os.path.join(private_tmp, "cwd")
    bin_dir = os.path.join(private_tmp, "bin")
    os.makedirs(reach_root)
    os.makedirs(run_cwd)
    os.makedirs(bin_dir)
    return reach_root, run_cwd, bin_dir


def _init_git_repo(path):
    subprocess.run(["git", "init", path], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", path, "config", "user.email", "pilot@example.test"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", path, "config", "user.name", "Pilot"],
        check=True,
        capture_output=True,
    )


def _plant_script_content():
    return (
        "#!/bin/sh\n"
        'ns="$2"\n'
        'id="$4"\n'
        'store="$PILOT_DATASTORE_URL"\n'
        'mkdir -p "$store/$ns"\n'
        'touch "$store/$ns/$id"\n'
        "exit 0\n"
    )


def _probe_script_present():
    return (
        "#!/bin/sh\n"
        'ns="$2"\n'
        'id="$4"\n'
        'store="$PILOT_DATASTORE_URL"\n'
        'if [ -f "$store/$ns/$id" ]; then exit 0; else exit 1; fi\n'
    )


def _cleanup_correct_script():
    return (
        "#!/bin/sh\n"
        'ns="$1"\n'
        'rm -rf "$PILOT_DATASTORE_URL/$ns"\n'
        "exit 0\n"
    )


def _cleanup_overreach_script():
    return (
        "#!/bin/sh\n"
        'ns="$1"\n'
        'rm -rf "$PILOT_DATASTORE_URL/${ns}"*\n'
        "exit 0\n"
    )


def _harness_layout(private_tmp):
    reach_root, run_cwd, bin_dir = _confinement_layout(private_tmp)
    store_dir = os.path.join(private_tmp, "store")
    cleanup_repo = os.path.join(private_tmp, "cleanup-repo")
    journal_path = os.path.join(private_tmp, "journal.jsonl")
    os.makedirs(store_dir)
    os.makedirs(cleanup_repo)
    _init_git_repo(cleanup_repo)
    return reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, journal_path


def _write_scripts(bin_dir):
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    _write_executable(plant, _plant_script_content())
    _write_executable(probe, _probe_script_present())
    return plant, probe


def _write_cleanup_script(cleanup_repo, name, content):
    path = os.path.join(cleanup_repo, name)
    _write_executable(path, content)
    return path


def _sentinel_declaration(plant_script, probe_script, env_var="PILOT_DATASTORE_URL"):
    return {
        "plantCommand": [plant_script, "--ns", pc.NAMESPACE_PLACEHOLDER, "--id", pc.SENTINEL_PLACEHOLDER],
        "probeCommand": [probe_script, "--ns", pc.NAMESPACE_PLACEHOLDER, "--id", pc.SENTINEL_PLACEHOLDER],
        "connectionEnvVar": env_var,
    }


def _slot_entry(origin, port_offset=0):
    base = "http://127.0.0.1:%d" % (5173 + port_offset)
    return {
        "origin": origin if origin.startswith("http") else base,
        "permittedRedirects": [origin if origin.startswith("http") else base],
        "expectedIdentities": {"owner": "pilot-owner@example.test"},
    }


def _three_slot_policy(store_dir, plant, probe, **overrides):
    doc = {
        "schemaVersion": 1,
        "declaration": "example-project-pilot-policy",
        "protectedTargets": ["example_prod"],
        "datastore": {
            "expectedIdentity": "example_dev",
            "connectionDetail": store_dir,
            "observer": {
                "command": ["/opt/pilot/db-identity"],
                "connectionEnvVar": "PILOT_DB_URL",
            },
            "containment": {
                "permissions": {
                    "cannotReachForeignNamespaces": False,
                    "evidence": "not isolated",
                },
                "sentinel": _sentinel_declaration(plant, probe),
            },
        },
        "slots": {
            "slot-a": _slot_entry("http://127.0.0.1:5173"),
            "slot-ab": _slot_entry("http://127.0.0.1:5175"),
            "slot-b": _slot_entry("http://127.0.0.1:8080"),
        },
    }
    doc["slots"]["slot-a"]["mintableAccounts"] = ["owner"]
    doc.update(overrides)
    return doc


def _pilot_block(cleanup_script):
    return {
        "schemaVersion": 1,
        "signInPath": "minted",
        "attended": {"vehicle": "automation"},
        "credentialSet": [{"account": "owner", "role": "resource-owner"}],
        "captureSurface": ["cookies"],
        "captureOptions": {"indexedDB": False, "credentials": False},
        "validityProvenance": "server-probe",
        "identityProbe": {"path": "/api/me", "unseededExpectation": "no-session"},
        "cleanup": {
            "command": [cleanup_script, pc.NAMESPACE_PLACEHOLDER],
        },
        "administrativeMax": 4,
        "effectsEscape": {
            "canEscape": False,
            "evidence": "dev mail capture",
        },
        "policyRef": {"declaration": "example-project-pilot-policy"},
        "mint": {
            "envelope": {
                "enablingFlagEnvVar": "ALLOW_TEST_MINT",
                "enabledScopes": ["development"],
                "forbiddenScopes": ["production"],
                "gateOffTestCommand": ["true"],
            },
            "sentinelIdentifier": "pilot-sentinel-no-such-account",
        },
    }


def _passing_verdict(policy, slot_ref=_SLOT_REF):
    import pilot_boundary

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
        "policyDigest": pilot_contract.declaration_digest(policy),
        "verifiedAt": _NOW,
    }


def _build_cleanup_inputs(private_tmp, cleanup_content, *, policy=None, pilot_block=None):
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, journal_path = _harness_layout(
        private_tmp
    )
    plant, probe = _write_scripts(bin_dir)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", cleanup_content)
    if policy is None:
        policy = _three_slot_policy(store_dir, plant, probe)
    if pilot_block is None:
        pilot_block = _pilot_block(cleanup_script)
    return {
        "policy": policy,
        "pilot_block": pilot_block,
        "slot_ref": _SLOT_REF,
        "reach_roots": [reach_root],
        "run_cwd": run_cwd,
        "cleanup_root": cleanup_repo,
        "journal_path": journal_path,
        "observed_identity": "example_dev",
        "identity_provenance": "observed",
        "identity_strength": "strong",
        "verdict": _passing_verdict(policy),
        "account": "owner",
        "mint_envelope": pilot_block["mint"]["envelope"],
    }


def _run_exercise(private_tmp, cleanup_content, **kwargs):
    cleanup = _build_cleanup_inputs(private_tmp, cleanup_content, **kwargs)
    return pcc.cleanup_end_to_end_exercise(inputs={"cleanup": cleanup}, now=_NOW)


# --- pass path -----------------------------------------------------------------

def test_cleanup_end_to_end_pass(private_tmp):
    record = _run_exercise(private_tmp, _cleanup_correct_script())
    assert record["result"] == pilot_conformance.RESULT_PASS
    assert record["reason"] is None
    assert record["evidence"] == pcc.EVIDENCE_PASS
    assert record["exercise"] == pcc.EXERCISE_NAME
    assert set(record["surfaces"]) == set(pcc._SURFACES)


def test_cleanup_end_to_end_residual_warnings(private_tmp):
    record = _run_exercise(private_tmp, _cleanup_correct_script())
    assert record["result"] == pilot_conformance.RESULT_PASS
    assert len(record["warnings"]) >= 1
    for warning in record["warnings"]:
        assert "namespace" in warning
        assert "reason" in warning
        assert "/" not in warning["namespace"]


# --- over-reaching cleanup -----------------------------------------------------

def test_cleanup_end_to_end_fails_on_overreach(private_tmp):
    record = _run_exercise(private_tmp, _cleanup_overreach_script())
    assert record["result"] == pilot_conformance.RESULT_FAIL
    assert record["reason"] == pc.REASON_FOREIGN_SENTINEL_DESTROYED


# --- single-slot policy --------------------------------------------------------

def test_cleanup_end_to_end_fails_single_slot(private_tmp):
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, journal_path = _harness_layout(
        private_tmp
    )
    plant, probe = _write_scripts(bin_dir)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    policy = _three_slot_policy(store_dir, plant, probe)
    policy["slots"] = {"slot-a": policy["slots"]["slot-a"]}
    pilot_block = _pilot_block(cleanup_script)
    cleanup = {
        "policy": policy,
        "pilot_block": pilot_block,
        "slot_ref": _SLOT_REF,
        "reach_roots": [reach_root],
        "run_cwd": run_cwd,
        "cleanup_root": cleanup_repo,
        "journal_path": journal_path,
        "observed_identity": "example_dev",
        "identity_provenance": "observed",
        "identity_strength": "strong",
        "verdict": _passing_verdict(policy),
        "account": "owner",
        "mint_envelope": pilot_block["mint"]["envelope"],
    }
    record = pcc.cleanup_end_to_end_exercise(inputs={"cleanup": cleanup}, now=_NOW)
    assert record["result"] == pilot_conformance.RESULT_FAIL
    # Single-slot: receipt fails before containment (no foreign namespace to prove against).
    assert record["reason"] == pc.REASON_NO_FOREIGN_NAMESPACE
    containment = pc.resolve_containment(policy, pilot_block, _SLOT_REF)
    assert containment["mode"] == pc.MODE_SINGLE_SLOT


# --- permissions policy --------------------------------------------------------

def test_cleanup_end_to_end_fails_permissions(private_tmp):
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, journal_path = _harness_layout(
        private_tmp
    )
    plant, probe = _write_scripts(bin_dir)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    policy = _three_slot_policy(store_dir, plant, probe)
    policy["datastore"]["containment"]["permissions"] = {
        "cannotReachForeignNamespaces": True,
        "evidence": "isolated datastore",
    }
    pilot_block = _pilot_block(cleanup_script)
    cleanup = {
        "policy": policy,
        "pilot_block": pilot_block,
        "slot_ref": _SLOT_REF,
        "reach_roots": [reach_root],
        "run_cwd": run_cwd,
        "cleanup_root": cleanup_repo,
        "journal_path": journal_path,
        "observed_identity": "example_dev",
        "identity_provenance": "observed",
        "identity_strength": "strong",
        "verdict": _passing_verdict(policy),
        "account": "owner",
        "mint_envelope": pilot_block["mint"]["envelope"],
    }
    record = pcc.cleanup_end_to_end_exercise(inputs={"cleanup": cleanup}, now=_NOW)
    assert record["result"] == pilot_conformance.RESULT_FAIL
    assert record["reason"] == pcc.REASON_CONTAINMENT_NOT_RECEIPT


# --- missing/malformed inputs --------------------------------------------------

@pytest.mark.parametrize(
    "inputs,expected_reason",
    [
        (None, pcc.REASON_INPUTS_MISSING),
        ({}, pcc.REASON_INPUTS_MISSING),
        ({"cleanup": None}, pcc.REASON_INPUTS_MISSING),
        ({"cleanup": "bad"}, pcc.REASON_INPUTS_MALFORMED),
    ],
)
def test_cleanup_end_to_end_skipped_missing_inputs(inputs, expected_reason):
    record = pcc.cleanup_end_to_end_exercise(inputs=inputs, now=_NOW)
    assert record["result"] == pilot_conformance.RESULT_SKIPPED
    assert record["reason"] == expected_reason


def test_cleanup_end_to_end_skipped_malformed_cleanup(private_tmp):
    record = pcc.cleanup_end_to_end_exercise(
        inputs={"cleanup": {"policy": "not-a-dict"}},
        now=_NOW,
    )
    assert record["result"] == pilot_conformance.RESULT_SKIPPED
    assert record["reason"] == pcc.REASON_INPUTS_MALFORMED


# --- plan produced, not executed -----------------------------------------------

def test_plan_not_executed_structural_guard():
    """bite-axis: plan execution — module must not dispatch resurrection plans."""
    module_path = os.path.join(_LIB, "pilot_conformance_cleanup.py")
    with open(module_path, encoding="utf-8") as handle:
        source = handle.read()
    forbidden = (
        "subprocess",
        "os.system",
        "os.exec",
        "os.spawn",
        "execute_plan",
        "run_bounded",
    )
    for name in forbidden:
        assert name not in source
    assert "resurrection_plan(" in source
    assert "plan.get(" in source


def test_post_plant_exception_returns_fail_with_residual_warnings(private_tmp, monkeypatch):
    cleanup = _build_cleanup_inputs(private_tmp, _cleanup_correct_script())
    pass_record = pcc.cleanup_end_to_end_exercise(
        inputs={"cleanup": cleanup},
        now=_NOW,
    )
    assert pass_record["result"] == pilot_conformance.RESULT_PASS
    assert pass_record["warnings"]

    def boom(*_args, **_kwargs):
        raise RuntimeError("simulated post-plant failure")

    monkeypatch.setattr(pcc.pilot_cleanup, "registry_record", boom)
    fail_record = pcc.cleanup_end_to_end_exercise(
        inputs={"cleanup": cleanup},
        now=_NOW,
    )
    assert fail_record["result"] == pilot_conformance.RESULT_FAIL
    assert fail_record["reason"] == pilot_conformance.REASON_EXERCISE_RAISED
    assert fail_record["warnings"]
    assert "post-plant failure" in fail_record["evidence"]


# --- registration --------------------------------------------------------------

def test_exercise_registered():
    assert pcc.cleanup_end_to_end_exercise.conformance_exercise == "cleanup-end-to-end"
    assert set(pcc.cleanup_end_to_end_exercise.conformance_surfaces) == set(pcc._SURFACES)
