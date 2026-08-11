"""Integration coverage for C9 cleanup containment through minted resurrection planning.

Exercises the live minted reseed planning path: containment receipt, registry record,
boundary verdict, resolve_containment, and resurrection_plan. The retired captured-artifact
resurrection path is gone — B4 attended seeding produces no artifact, and attended slots
park on resurrection instead. Unit-level coverage of individual surfaces lives in
test_pilot_cleanup.py; the conformance exercise lives in test_pilot_conformance_cleanup.py.
"""
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_boundary  # noqa: E402
import pilot_cleanup as pc  # noqa: E402
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


def _three_slot_policy(store_dir, plant, probe):
    return {
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


def _resurrection_policy(private_tmp):
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, journal_path = _harness_layout(
        private_tmp
    )
    plant, probe = _write_scripts(bin_dir)
    policy = _three_slot_policy(store_dir, plant, probe)
    policy["slots"]["slot-a"]["mintableAccounts"] = ["owner"]
    return policy, reach_root, run_cwd, cleanup_repo, journal_path


def _pilot_block(cleanup_script, *, sign_in_path="minted"):
    block = {
        "schemaVersion": 1,
        "signInPath": sign_in_path,
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
    }
    if sign_in_path == "minted":
        block["mint"] = {
            "envelope": {
                "enablingFlagEnvVar": "ALLOW_TEST_MINT",
                "enabledScopes": ["development"],
                "forbiddenScopes": ["production"],
                "gateOffTestCommand": ["true"],
            },
            "sentinelIdentifier": "pilot-sentinel-no-such-account",
        }
    return block


def _passing_verdict(policy, slot_ref=_SLOT_REF):
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


def _effects_escape_record(pilot_block):
    return {
        "kind": "effects-escape",
        "declarationDigest": pilot_contract.declaration_digest(pilot_block["effectsEscape"]),
        "exercisedAt": _NOW,
        "receipt": {"result": "pass", "evidence": "effects do not escape"},
    }


def test_minted_resurrection_planning_sequence(private_tmp):
    """Full planning sequence on the minted reseed path — plan produced, not executed."""
    policy, reach_root, run_cwd, cleanup_repo, journal_path = _resurrection_policy(private_tmp)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    pilot_block = _pilot_block(cleanup_script, sign_in_path="minted")

    receipt = pc.cleanup_effect_receipt(
        policy,
        pilot_block,
        _SLOT_REF,
        reach_roots=[reach_root],
        run_cwd=run_cwd,
        cleanup_root=cleanup_repo,
        journal_path=journal_path,
        now=_NOW,
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="strong",
    )
    assert receipt["result"] == pc.RESULT_PASS

    registry_record = pc.registry_record(receipt, pilot_block["cleanup"])
    assert registry_record["kind"] == pc.KIND_CLEANUP_CONTAINMENT

    registry = {
        "schemaVersion": 1,
        "records": [
            _effects_escape_record(pilot_block),
            registry_record,
        ],
    }

    verdict = _passing_verdict(policy)

    containment = pc.resolve_containment(
        policy,
        pilot_block,
        _SLOT_REF,
        receipt=receipt,
        cleanup_root=cleanup_repo,
        run_cwd=run_cwd,
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="strong",
    )
    assert containment["mode"] == pc.MODE_RECEIPT

    plan = pc.resurrection_plan(
        policy,
        pilot_block,
        _SLOT_REF,
        registry=registry,
        journal_path=journal_path,
        verdict=verdict,
        account="owner",
        mint_envelope=pilot_block["mint"]["envelope"],
        now=_NOW,
        receipt=receipt,
        cleanup_root=cleanup_repo,
        run_cwd=run_cwd,
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="strong",
    )
    # bite-axis: minted-path assertion — reseed descriptor must be minted, not captured artifact.
    assert plan["action"] == pc.ACTION_RESURRECT
    assert plan["steps"][1]["path"] == "minted"
    assert plan["steps"][1]["path"] != "captured"


def test_attended_counterpart_parks(private_tmp):
    """Attended sign-in path parks instead of producing a minted reseed plan."""
    policy, reach_root, run_cwd, cleanup_repo, journal_path = _resurrection_policy(private_tmp)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    pilot_block = _pilot_block(cleanup_script, sign_in_path="attended")

    receipt = pc.cleanup_effect_receipt(
        policy,
        pilot_block,
        _SLOT_REF,
        reach_roots=[reach_root],
        run_cwd=run_cwd,
        cleanup_root=cleanup_repo,
        journal_path=journal_path,
        now=_NOW,
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="strong",
    )
    assert receipt["result"] == pc.RESULT_PASS

    registry = {
        "schemaVersion": 1,
        "records": [
            _effects_escape_record(pilot_block),
            pc.registry_record(receipt, pilot_block["cleanup"]),
        ],
    }

    plan = pc.resurrection_plan(
        policy,
        pilot_block,
        _SLOT_REF,
        registry=registry,
        journal_path=journal_path,
        verdict=_passing_verdict(policy),
        account="owner",
        receipt=receipt,
        cleanup_root=cleanup_repo,
        run_cwd=run_cwd,
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="strong",
    )
    assert plan["action"] == pc.ACTION_PARK
    assert plan["reason"] == pc.REASON_ATTENDED_RESEED_REQUIRES_OWNER
