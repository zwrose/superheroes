"""Tests for pilot_cleanup.py — cleanup primitives and receipt binding."""
import copy
import hashlib
import json
import os
import stat
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_boundary  # noqa: E402
import pilot_contract  # noqa: E402
import pilot_policy  # noqa: E402
import pilot_provision as pp  # noqa: E402
import pilot_cleanup as pc  # noqa: E402
import pilot_slot  # noqa: E402


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


def _sentinel_declaration(plant_script, probe_script, env_var="PILOT_DATASTORE_URL"):
    return {
        "plantCommand": [plant_script, "--ns", pc.NAMESPACE_PLACEHOLDER, "--id", pc.SENTINEL_PLACEHOLDER],
        "probeCommand": [probe_script, "--ns", pc.NAMESPACE_PLACEHOLDER, "--id", pc.SENTINEL_PLACEHOLDER],
        "connectionEnvVar": env_var,
    }


def _sample_policy(**overrides):
    doc = {
        "schemaVersion": 1,
        "declaration": "example-project-pilot-policy",
        "protectedTargets": ["example_prod"],
        "datastore": {
            "expectedIdentity": "example_dev",
            "connectionDetail": "postgres://localhost:5432/example_dev",
            "observer": {
                "command": ["/opt/pilot/db-identity"],
                "connectionEnvVar": "PILOT_DB_URL",
            },
        },
        "slots": {
            "slot-a": {"origin": "http://127.0.0.1:5173"},
            "slot-b": {"origin": "http://127.0.0.1:8080"},
        },
    }
    doc.update(overrides)
    return doc


def _config_digest_inputs(**overrides):
    defaults = {
        "policy": _sample_policy(),
        "resolved_cleanup_argv": ["/abs/cleanup", "slot-a"],
        "sentinel": {
            "plantCommand": ["/abs/plant", pc.NAMESPACE_PLACEHOLDER, pc.SENTINEL_PLACEHOLDER],
            "probeCommand": ["/abs/probe", pc.NAMESPACE_PLACEHOLDER, pc.SENTINEL_PLACEHOLDER],
            "connectionEnvVar": "PILOT_DATASTORE_URL",
        },
        "namespace": "slot-a",
        "foreign_namespaces": ["slot-b"],
        "run_cwd": "/tmp/cwd",
        "identity_provenance": "observed",
        "identity_strength": "strong",
        "observed_identity": "example_dev",
        "source_identity": {"head": None, "statusDigest": "a" * 64, "argv0Digest": None},
    }
    defaults.update(overrides)
    return defaults


# --- namespace_for_slot -------------------------------------------------------

def test_namespace_for_slot_returns_slot_id():
    assert pc.namespace_for_slot("slot-a") == "slot-a"


# --- foreign_namespaces -------------------------------------------------------

def test_foreign_namespaces_single_slot_returns_empty():
    policy = {"slots": {"only": {}}}
    assert pc.foreign_namespaces(policy, "only") == []


def test_foreign_namespaces_returns_sorted_siblings():
    policy = {"slots": {"a": {}, "ab": {}, "b": {}}}
    assert pc.foreign_namespaces(policy, "a") == ["ab", "b"]


def test_foreign_namespaces_refuses_absent_slot():
    policy = {"slots": {"a": {}, "b": {}}}
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.foreign_namespaces(policy, "missing")
    assert exc.value.reason == pc.REFUSAL_POLICY_INVALID


def test_foreign_namespaces_refuses_malformed_slot_key():
    policy = {"slots": {"good": {}, "../x": {}}}
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.foreign_namespaces(policy, "good")
    assert exc.value.reason == pc.REFUSAL_POLICY_INVALID


# --- resolve_cleanup_command edge 1 -------------------------------------------

@pytest.mark.parametrize(
    "command",
    [
        [],
        None,
        "string",
        ["ok", 5],
        ["ok", ""],
    ],
)
def test_resolve_cleanup_command_refuses_invalid_command(command):
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.resolve_cleanup_command(command, "slot-a")
    assert exc.value.reason == pc.REFUSAL_COMMAND_INVALID


# --- edge 2: placeholder in argv0 ---------------------------------------------

def test_resolve_cleanup_command_refuses_namespace_in_argv0():
    command = [pc.NAMESPACE_PLACEHOLDER, "cleanup"]
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.resolve_cleanup_command(command, "slot-a")
    assert exc.value.reason == pc.REFUSAL_COMMAND_ARGV0_PLACEHOLDER


# --- edge 3: no placeholder ---------------------------------------------------

def test_resolve_cleanup_command_refuses_unparameterized():
    command = ["/abs/cleanup", "slot-a"]
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.resolve_cleanup_command(command, "slot-a")
    assert exc.value.reason == pc.REFUSAL_COMMAND_UNPARAMETERIZED


# --- edge 4: {sentinel} illegal ------------------------------------------------

def test_resolve_cleanup_command_refuses_sentinel_placeholder():
    command = ["/abs/cleanup", pc.SENTINEL_PLACEHOLDER]
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.resolve_cleanup_command(command, "slot-a")
    assert exc.value.reason == pc.REFUSAL_COMMAND_PLACEHOLDER_UNKNOWN


# --- edge 5: unknown placeholder -----------------------------------------------

@pytest.mark.parametrize(
    "command",
    [
        ["/abs/cleanup", "{slot}"],
        ["/abs/cleanup", "{}"],
    ],
)
def test_resolve_cleanup_command_refuses_unknown_placeholder(command):
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.resolve_cleanup_command(command, "slot-a")
    assert exc.value.reason == pc.REFUSAL_COMMAND_PLACEHOLDER_UNKNOWN


# --- edge 6: unclosed brace is not a placeholder -------------------------------

def test_resolve_cleanup_command_accepts_unclosed_brace():
    command = ["/abs/cleanup", "{namespace", pc.NAMESPACE_PLACEHOLDER]
    result = pc.resolve_cleanup_command(command, "slot-a")
    assert result == ["/abs/cleanup", "{namespace", "slot-a"]


# --- edge 7: invalid namespace -------------------------------------------------

@pytest.mark.parametrize("namespace", ["", "a/b", None, "../x"])
def test_resolve_cleanup_command_refuses_invalid_namespace(namespace):
    command = ["/abs/cleanup", pc.NAMESPACE_PLACEHOLDER]
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.resolve_cleanup_command(command, namespace)
    assert exc.value.reason == pc.REFUSAL_NAMESPACE_INVALID


# --- happy path resolve --------------------------------------------------------

def test_resolve_cleanup_command_substitutes_namespace():
    command = ["/abs/cleanup", "--ns", pc.NAMESPACE_PLACEHOLDER]
    assert pc.resolve_cleanup_command(command, "slot-a") == [
        "/abs/cleanup",
        "--ns",
        "slot-a",
    ]


# --- substitute_sentinel_command edge 8 ----------------------------------------

def test_substitute_sentinel_command_refuses_missing_namespace():
    command = ["/abs/plant", pc.SENTINEL_PLACEHOLDER]
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.substitute_sentinel_command(command, "slot-a", "sentinel-1")
    assert exc.value.reason == pc.REFUSAL_COMMAND_UNPARAMETERIZED


def test_substitute_sentinel_command_refuses_missing_sentinel():
    command = ["/abs/plant", pc.NAMESPACE_PLACEHOLDER]
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.substitute_sentinel_command(command, "slot-a", "sentinel-1")
    assert exc.value.reason == pc.REFUSAL_COMMAND_UNPARAMETERIZED


def test_substitute_sentinel_command_refuses_namespace_in_argv0():
    command = [pc.NAMESPACE_PLACEHOLDER, "x", pc.SENTINEL_PLACEHOLDER]
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.substitute_sentinel_command(command, "slot-a", "sentinel-1")
    assert exc.value.reason == pc.REFUSAL_COMMAND_ARGV0_PLACEHOLDER


def test_substitute_sentinel_command_refuses_sentinel_in_argv0():
    command = [pc.SENTINEL_PLACEHOLDER, pc.NAMESPACE_PLACEHOLDER]
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.substitute_sentinel_command(command, "slot-a", "sentinel-1")
    assert exc.value.reason == pc.REFUSAL_COMMAND_ARGV0_PLACEHOLDER


# --- edge 9: invalid sentinel_id -----------------------------------------------

@pytest.mark.parametrize(
    "sentinel_id",
    ["", "a b", "a;b", "../x", "x" * 129, 42],
)
def test_substitute_sentinel_command_refuses_invalid_sentinel_id(sentinel_id):
    command = ["/abs/plant", pc.NAMESPACE_PLACEHOLDER, pc.SENTINEL_PLACEHOLDER]
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.substitute_sentinel_command(command, "slot-a", sentinel_id)
    assert exc.value.reason == pc.REFUSAL_SENTINEL_ID_INVALID


def test_substitute_sentinel_command_happy_path():
    command = ["/abs/plant", pc.NAMESPACE_PLACEHOLDER, pc.SENTINEL_PLACEHOLDER]
    assert pc.substitute_sentinel_command(command, "slot-a", "id-1") == [
        "/abs/plant",
        "slot-a",
        "id-1",
    ]


# --- mint_sentinel_id ----------------------------------------------------------

def test_mint_sentinel_id_is_32_hex_chars():
    sentinel_id = pc.mint_sentinel_id()
    assert len(sentinel_id) == 32
    assert all(ch in "0123456789abcdef" for ch in sentinel_id)


def test_mint_sentinel_id_is_unique():
    assert pc.mint_sentinel_id() != pc.mint_sentinel_id()


# --- run_bounded edge 13 -------------------------------------------------------

def test_run_bounded_exit_zero(private_tmp):
    _, run_cwd, bin_dir = _confinement_layout(private_tmp)
    script = os.path.join(bin_dir, "exit0.sh")
    _write_executable(script, "#!/bin/sh\nexit 0\n")
    result = pc.run_bounded([script], cwd=run_cwd, env={})
    assert result == {"exit": 0, "timedOut": False, "stdoutBytes": 0}


def test_run_bounded_exit_one(private_tmp):
    _, run_cwd, bin_dir = _confinement_layout(private_tmp)
    script = os.path.join(bin_dir, "exit1.sh")
    _write_executable(script, "#!/bin/sh\nexit 1\n")
    result = pc.run_bounded([script], cwd=run_cwd, env={})
    assert result == {"exit": 1, "timedOut": False, "stdoutBytes": 0}


def test_run_bounded_exit_forty_two(private_tmp):
    _, run_cwd, bin_dir = _confinement_layout(private_tmp)
    script = os.path.join(bin_dir, "exit42.sh")
    _write_executable(script, "#!/bin/sh\nexit 42\n")
    result = pc.run_bounded([script], cwd=run_cwd, env={})
    assert result == {"exit": 42, "timedOut": False, "stdoutBytes": 0}


def test_run_bounded_timeout(private_tmp):
    _, run_cwd, bin_dir = _confinement_layout(private_tmp)
    script = os.path.join(bin_dir, "sleep.sh")
    _write_executable(script, "#!/bin/sh\n/bin/sleep 5\n")
    result = pc.run_bounded([script], cwd=run_cwd, env={}, timeout_seconds=1)
    assert result["timedOut"] is True
    assert result["exit"] is None


# --- edge 14: nonexistent executable -------------------------------------------

def test_run_bounded_nonexistent_executable_raises(private_tmp):
    _, run_cwd, _ = _confinement_layout(private_tmp)
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.run_bounded([os.path.join(run_cwd, "missing-binary")], cwd=run_cwd, env={})
    assert exc.value.reason == pc.REFUSAL_PROBE_INDETERMINATE


# --- edge 15: oversized stdout ------------------------------------------------

def test_run_bounded_oversized_stdout(private_tmp):
    _, run_cwd, bin_dir = _confinement_layout(private_tmp)
    script = os.path.join(bin_dir, "huge.sh")
    _write_executable(
        script,
        "#!/bin/sh\n"
        "i=0\n"
        "while [ $i -lt 10000 ]; do printf x; i=$((i+1)); done\n",
    )
    result = pc.run_bounded(
        [script],
        cwd=run_cwd,
        env={},
        max_output_bytes=100,
        timeout_seconds=5,
    )
    assert result["stdoutBytes"] >= 100
    assert result["timedOut"] is False
    assert result["exit"] == 0


# --- plant_sentinel edge 17 ----------------------------------------------------

def test_plant_sentinel_success(private_tmp):
    reach_root, run_cwd, bin_dir = _confinement_layout(private_tmp)
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    _write_executable(plant, "#!/bin/sh\nexit 0\n")
    _write_executable(probe, "#!/bin/sh\nexit 0\n")
    sentinel = _sentinel_declaration(plant, probe)
    assert pc.plant_sentinel(
        sentinel,
        "slot-a",
        "sentinel-1",
        connection_detail="postgres://localhost/db",
        reach_roots=[reach_root],
        run_cwd=run_cwd,
    ) is None


def test_plant_sentinel_refuses_nonzero(private_tmp):
    reach_root, run_cwd, bin_dir = _confinement_layout(private_tmp)
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    _write_executable(plant, "#!/bin/sh\nexit 2\n")
    _write_executable(probe, "#!/bin/sh\nexit 0\n")
    sentinel = _sentinel_declaration(plant, probe)
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.plant_sentinel(
            sentinel,
            "slot-a",
            "sentinel-1",
            connection_detail="postgres://localhost/db",
            reach_roots=[reach_root],
            run_cwd=run_cwd,
        )
    assert exc.value.reason == pc.REFUSAL_PLANT_FAILED


def test_plant_sentinel_refuses_timeout(private_tmp):
    reach_root, run_cwd, bin_dir = _confinement_layout(private_tmp)
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    _write_executable(plant, "#!/bin/sh\n/bin/sleep 5\n")
    _write_executable(probe, "#!/bin/sh\nexit 0\n")
    sentinel = _sentinel_declaration(plant, probe)
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.plant_sentinel(
            sentinel,
            "slot-a",
            "sentinel-1",
            connection_detail="postgres://localhost/db",
            reach_roots=[reach_root],
            run_cwd=run_cwd,
            timeout_seconds=1,
        )
    assert exc.value.reason == pc.REFUSAL_PLANT_FAILED


# --- probe_sentinel edge 16 ----------------------------------------------------

def test_probe_sentinel_present(private_tmp):
    reach_root, run_cwd, bin_dir = _confinement_layout(private_tmp)
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    _write_executable(plant, "#!/bin/sh\nexit 0\n")
    _write_executable(probe, "#!/bin/sh\nexit 0\n")
    sentinel = _sentinel_declaration(plant, probe)
    assert pc.probe_sentinel(
        sentinel,
        "slot-a",
        "sentinel-1",
        connection_detail="postgres://localhost/db",
        reach_roots=[reach_root],
        run_cwd=run_cwd,
    ) == {"present": True}


def test_probe_sentinel_absent(private_tmp):
    reach_root, run_cwd, bin_dir = _confinement_layout(private_tmp)
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    _write_executable(plant, "#!/bin/sh\nexit 0\n")
    _write_executable(probe, "#!/bin/sh\nexit 1\n")
    sentinel = _sentinel_declaration(plant, probe)
    assert pc.probe_sentinel(
        sentinel,
        "slot-a",
        "sentinel-1",
        connection_detail="postgres://localhost/db",
        reach_roots=[reach_root],
        run_cwd=run_cwd,
    ) == {"present": False}


def test_probe_sentinel_indeterminate_exit_two(private_tmp):
    reach_root, run_cwd, bin_dir = _confinement_layout(private_tmp)
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    _write_executable(plant, "#!/bin/sh\nexit 0\n")
    _write_executable(probe, "#!/bin/sh\nexit 2\n")
    sentinel = _sentinel_declaration(plant, probe)
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.probe_sentinel(
            sentinel,
            "slot-a",
            "sentinel-1",
            connection_detail="postgres://localhost/db",
            reach_roots=[reach_root],
            run_cwd=run_cwd,
        )
    assert exc.value.reason == pc.REFUSAL_PROBE_INDETERMINATE


def test_probe_sentinel_indeterminate_timeout(private_tmp):
    reach_root, run_cwd, bin_dir = _confinement_layout(private_tmp)
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    _write_executable(plant, "#!/bin/sh\nexit 0\n")
    _write_executable(probe, "#!/bin/sh\n/bin/sleep 5\n")
    sentinel = _sentinel_declaration(plant, probe)
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.probe_sentinel(
            sentinel,
            "slot-a",
            "sentinel-1",
            connection_detail="postgres://localhost/db",
            reach_roots=[reach_root],
            run_cwd=run_cwd,
            timeout_seconds=1,
        )
    assert exc.value.reason == pc.REFUSAL_PROBE_INDETERMINATE


# --- _validate_sentinel_declaration edge 18 ------------------------------------

def test_validate_sentinel_declaration_refuses_empty_reach_roots(private_tmp):
    _, run_cwd, bin_dir = _confinement_layout(private_tmp)
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    _write_executable(plant, "#!/bin/sh\nexit 0\n")
    _write_executable(probe, "#!/bin/sh\nexit 0\n")
    sentinel = _sentinel_declaration(plant, probe)
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc._validate_sentinel_declaration(sentinel, reach_roots=[], run_cwd=run_cwd)
    assert exc.value.reason == pc.REFUSAL_SENTINEL_CONFINEMENT


def test_validate_sentinel_declaration_refuses_relative_argv0(private_tmp):
    reach_root, run_cwd, bin_dir = _confinement_layout(private_tmp)
    plant = "relative/plant.sh"
    probe = os.path.join(bin_dir, "probe.sh")
    _write_executable(probe, "#!/bin/sh\nexit 0\n")
    sentinel = _sentinel_declaration(plant, probe)
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc._validate_sentinel_declaration(sentinel, reach_roots=[reach_root], run_cwd=run_cwd)
    assert exc.value.reason == pc.REFUSAL_SENTINEL_CONFINEMENT


@pytest.mark.skipif(os.getuid() == 0, reason="mode checks do not bite as root")
def test_validate_sentinel_declaration_refuses_world_writable_argv0(private_tmp):
    reach_root, run_cwd, bin_dir = _confinement_layout(private_tmp)
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    _write_executable(plant, "#!/bin/sh\nexit 0\n")
    os.chmod(plant, 0o777)
    _write_executable(probe, "#!/bin/sh\nexit 0\n")
    sentinel = _sentinel_declaration(plant, probe)
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc._validate_sentinel_declaration(sentinel, reach_roots=[reach_root], run_cwd=run_cwd)
    assert exc.value.reason == pc.REFUSAL_SENTINEL_CONFINEMENT


def test_validate_sentinel_declaration_refuses_argv0_inside_reach_root(private_tmp):
    reach_root, run_cwd, bin_dir = _confinement_layout(private_tmp)
    plant = os.path.join(reach_root, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    _write_executable(plant, "#!/bin/sh\nexit 0\n")
    _write_executable(probe, "#!/bin/sh\nexit 0\n")
    sentinel = _sentinel_declaration(plant, probe)
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc._validate_sentinel_declaration(sentinel, reach_roots=[reach_root], run_cwd=run_cwd)
    assert exc.value.reason == pc.REFUSAL_SENTINEL_CONFINEMENT


def test_validate_sentinel_declaration_refuses_run_cwd_inside_reach_root(private_tmp):
    reach_root, _, bin_dir = _confinement_layout(private_tmp)
    run_cwd_inside = os.path.join(reach_root, "nested-cwd")
    os.makedirs(run_cwd_inside)
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    _write_executable(plant, "#!/bin/sh\nexit 0\n")
    _write_executable(probe, "#!/bin/sh\nexit 0\n")
    sentinel = _sentinel_declaration(plant, probe)
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc._validate_sentinel_declaration(sentinel, reach_roots=[reach_root], run_cwd=run_cwd_inside)
    assert exc.value.reason == pc.REFUSAL_SENTINEL_CONFINEMENT


def test_validate_sentinel_declaration_refuses_missing_key(private_tmp):
    reach_root, run_cwd, bin_dir = _confinement_layout(private_tmp)
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    _write_executable(plant, "#!/bin/sh\nexit 0\n")
    _write_executable(probe, "#!/bin/sh\nexit 0\n")
    sentinel = {
        "plantCommand": [plant, pc.NAMESPACE_PLACEHOLDER, pc.SENTINEL_PLACEHOLDER],
        "probeCommand": [probe, pc.NAMESPACE_PLACEHOLDER, pc.SENTINEL_PLACEHOLDER],
    }
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc._validate_sentinel_declaration(sentinel, reach_roots=[reach_root], run_cwd=run_cwd)
    assert exc.value.reason == pc.REFUSAL_SENTINEL_DECLARATION_INVALID


def test_validate_sentinel_declaration_refuses_unknown_key(private_tmp):
    reach_root, run_cwd, bin_dir = _confinement_layout(private_tmp)
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    _write_executable(plant, "#!/bin/sh\nexit 0\n")
    _write_executable(probe, "#!/bin/sh\nexit 0\n")
    sentinel = _sentinel_declaration(plant, probe)
    sentinel["extra"] = "nope"
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc._validate_sentinel_declaration(sentinel, reach_roots=[reach_root], run_cwd=run_cwd)
    assert exc.value.reason == pc.REFUSAL_SENTINEL_DECLARATION_INVALID


def test_validate_sentinel_declaration_refuses_bad_connection_env_var(private_tmp):
    reach_root, run_cwd, bin_dir = _confinement_layout(private_tmp)
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    _write_executable(plant, "#!/bin/sh\nexit 0\n")
    _write_executable(probe, "#!/bin/sh\nexit 0\n")
    sentinel = _sentinel_declaration(plant, probe, env_var="9INVALID")
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc._validate_sentinel_declaration(sentinel, reach_roots=[reach_root], run_cwd=run_cwd)
    assert exc.value.reason == pc.REFUSAL_SENTINEL_DECLARATION_INVALID


# --- source_identity edge 19 ---------------------------------------------------

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


def test_source_identity_nonexistent_path():
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.source_identity(os.path.join("/no/such/path", "missing"))
    assert exc.value.reason == pc.REFUSAL_SOURCE_ROOT_INVALID


def test_source_identity_not_a_git_repo(private_tmp):
    repo = os.path.join(private_tmp, "not-git")
    os.makedirs(repo)
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.source_identity(repo)
    assert exc.value.reason == pc.REFUSAL_SOURCE_UNREADABLE


def test_source_identity_no_commits(private_tmp):
    repo = os.path.join(private_tmp, "empty-git")
    os.makedirs(repo)
    _init_git_repo(repo)
    result = pc.source_identity(repo)
    assert result["head"] is None
    assert len(result["statusDigest"]) == 64
    assert result["argv0Digest"] is None


def test_source_identity_with_commit(private_tmp):
    repo = os.path.join(private_tmp, "git-repo")
    os.makedirs(repo)
    _init_git_repo(repo)
    marker = os.path.join(repo, "marker.txt")
    with open(marker, "w", encoding="utf-8") as handle:
        handle.write("x\n")
    subprocess.run(["git", "-C", repo, "add", "marker.txt"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", repo, "commit", "-m", "init"],
        check=True,
        capture_output=True,
    )
    result = pc.source_identity(repo)
    assert result["head"] is not None
    assert len(result["head"]) in (40, 64)
    assert len(result["statusDigest"]) == 64


# --- argv0_content_digest edge 20 ----------------------------------------------

def test_argv0_content_digest_regular_file(private_tmp):
    path = os.path.join(private_tmp, "script.sh")
    content = b"#!/bin/sh\necho hi\n"
    with open(path, "wb") as handle:
        handle.write(content)
    expected = hashlib.sha256(content).hexdigest()
    assert pc.argv0_content_digest(path) == expected


def test_argv0_content_digest_directory(private_tmp):
    path = os.path.join(private_tmp, "adir")
    os.makedirs(path)
    assert pc.argv0_content_digest(path) is None


def test_argv0_content_digest_nonexistent():
    assert pc.argv0_content_digest("/no/such/file") is None


def test_argv0_content_digest_symlink_to_file(private_tmp):
    target = os.path.join(private_tmp, "target.sh")
    with open(target, "wb") as handle:
        handle.write(b"content\n")
    link = os.path.join(private_tmp, "link.sh")
    os.symlink(target, link)
    assert pc.argv0_content_digest(link) is None


# --- config_digest edge 21 -----------------------------------------------------

def test_config_digest_deterministic():
    inputs = _config_digest_inputs()
    first = pc.config_digest(**inputs)
    second = pc.config_digest(**inputs)
    assert first == second
    assert len(first) == 64


@pytest.mark.parametrize(
    "field,mutator",
    [
        ("resolved_cleanup_argv", lambda i: i.update({"resolved_cleanup_argv": ["/other"]})),
        ("sentinel", lambda i: i.update({
            "sentinel": {
                "plantCommand": ["/other-plant"],
                "probeCommand": i["sentinel"]["probeCommand"],
                "connectionEnvVar": i["sentinel"]["connectionEnvVar"],
            }
        })),
        ("sentinel", lambda i: i.update({
            "sentinel": {
                "plantCommand": i["sentinel"]["plantCommand"],
                "probeCommand": ["/other-probe"],
                "connectionEnvVar": i["sentinel"]["connectionEnvVar"],
            }
        })),
        ("sentinel", lambda i: i.update({
            "sentinel": {
                "plantCommand": i["sentinel"]["plantCommand"],
                "probeCommand": i["sentinel"]["probeCommand"],
                "connectionEnvVar": "OTHER_ENV",
            }
        })),
        ("policy", lambda i: i.update({
            "policy": _sample_policy(
                datastore={
                    "expectedIdentity": "example_dev",
                    "connectionDetail": "postgres://localhost:5432/other_db",
                    "observer": i["policy"]["datastore"]["observer"],
                }
            )
        })),
        ("namespace", lambda i: i.update({"namespace": "slot-b"})),
        ("foreign_namespaces", lambda i: i.update({"foreign_namespaces": ["slot-a"]})),
        ("run_cwd", lambda i: i.update({"run_cwd": "/other/cwd"})),
        ("identity_provenance", lambda i: i.update({"identity_provenance": "app-reported"})),
        ("identity_strength", lambda i: i.update({"identity_strength": "weaker"})),
        ("observed_identity", lambda i: i.update({"observed_identity": "other_dev"})),
        ("source_identity", lambda i: i.update({
            "source_identity": {"head": "a" * 40, "statusDigest": "b" * 64, "argv0Digest": None}
        })),
    ],
    ids=[
        "resolvedCleanupArgv",
        "sentinelPlantCommand",
        "sentinelProbeCommand",
        "sentinelConnectionEnvVar",
        "connectionDetail",
        "namespace",
        "foreignNamespaces",
        "runCwd",
        "identityProvenance",
        "identityStrength",
        "observedIdentity",
        "sourceIdentity",
    ],
)
def test_config_digest_changes_when_field_changes(field, mutator):
    base = _config_digest_inputs()
    base_digest = pc.config_digest(**base)
    mutated = dict(base)
    mutator(mutated)
    assert pc.config_digest(**mutated) != base_digest


# --- binding_key edge 22 -------------------------------------------------------

def test_binding_key_changes_when_policy_changes():
    policy_a = _sample_policy()
    policy_b = _sample_policy(protectedTargets=["other_prod"])
    assert pc.binding_key(policy_a) != pc.binding_key(policy_b)


# --- C9 harness helpers -------------------------------------------------------

_NOW = "2026-08-02T12:00:00Z"
_SLOT_REF = "slot-a@1"


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


def _probe_script_indeterminate():
    return "#!/bin/sh\nexit 2\n"


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


def _cleanup_inert_script():
    return "#!/bin/sh\nexit 0\n"


def _cleanup_fail_script():
    return "#!/bin/sh\nexit 3\n"


def _harness_layout(private_tmp):
    reach_root, run_cwd, bin_dir = _confinement_layout(private_tmp)
    store_dir = os.path.join(private_tmp, "store")
    cleanup_repo = os.path.join(private_tmp, "cleanup-repo")
    journal_path = os.path.join(private_tmp, "journal.jsonl")
    os.makedirs(store_dir)
    os.makedirs(cleanup_repo)
    _init_git_repo(cleanup_repo)
    return reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, journal_path


def _write_scripts(bin_dir, *, probe_content=None):
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    _write_executable(plant, _plant_script_content())
    _write_executable(probe, probe_content or _probe_script_present())
    return plant, probe


def _write_cleanup_script(cleanup_repo, name, content):
    path = os.path.join(cleanup_repo, name)
    _write_executable(path, content)
    return path


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
    doc.update(overrides)
    return doc


def _pilot_block(cleanup_script):
    return {
        "schemaVersion": 1,
        "signInPath": "captured",
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


def _run_receipt(private_tmp, cleanup_content, *, probe_content=None, sentinel_factory=None,
                 policy_overrides=None):
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, journal_path = _harness_layout(
        private_tmp
    )
    plant, probe = _write_scripts(bin_dir, probe_content=probe_content)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", cleanup_content)
    policy = _three_slot_policy(store_dir, plant, probe)
    if policy_overrides:
        policy.update(policy_overrides)
    pilot_block = _pilot_block(cleanup_script)
    kwargs = {
        "policy": policy,
        "pilot_block": pilot_block,
        "slot_ref": _SLOT_REF,
        "reach_roots": [reach_root],
        "run_cwd": run_cwd,
        "cleanup_root": cleanup_repo,
        "journal_path": journal_path,
        "now": _NOW,
        "observed_identity": "example_dev",
        "identity_provenance": "observed",
        "identity_strength": "strong",
    }
    if sentinel_factory is not None:
        kwargs["sentinel_factory"] = sentinel_factory
    return pc.cleanup_effect_receipt(**kwargs), {
        "policy": policy,
        "pilot_block": pilot_block,
        "reach_root": reach_root,
        "run_cwd": run_cwd,
        "cleanup_repo": cleanup_repo,
        "journal_path": journal_path,
        "store_dir": store_dir,
        "cleanup_script": cleanup_script,
    }


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


def _init_git_repo_with_commit(path):
    _init_git_repo(path)
    subprocess.run(
        ["git", "-C", path, "-c", "user.email=pilot@example.test", "-c", "user.name=Pilot",
         "commit", "--allow-empty", "-m", "init"],
        check=True,
        capture_output=True,
    )


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


def _resurrection_policy(private_tmp):
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, _ = _harness_layout(private_tmp)
    plant, probe = _write_scripts(bin_dir)
    policy = _three_slot_policy(store_dir, plant, probe)
    policy["slots"]["slot-a"]["mintableAccounts"] = ["owner"]
    return policy, reach_root, run_cwd, cleanup_repo


def _effects_escape_record(pilot_block):
    return {
        "kind": "effects-escape",
        "declarationDigest": pilot_contract.declaration_digest(pilot_block["effectsEscape"]),
        "exercisedAt": _NOW,
        "receipt": {"result": "pass", "evidence": "effects do not escape"},
    }


def _cleanup_containment_record(pilot_block, receipt):
    return pc.registry_record(receipt, pilot_block["cleanup"])


def _registry_with(*records):
    return {"schemaVersion": 1, "records": list(records)}


# --- cleanup_effect_receipt edge 1 ---------------------------------------------

def test_cleanup_effect_receipt_refuses_undeclared_sentinel(private_tmp):
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, journal_path = _harness_layout(
        private_tmp
    )
    plant, probe = _write_scripts(bin_dir)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    policy = _three_slot_policy(store_dir, plant, probe)
    del policy["datastore"]["containment"]["sentinel"]
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.cleanup_effect_receipt(
            policy,
            _pilot_block(cleanup_script),
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
    assert exc.value.reason == pc.REFUSAL_SENTINEL_UNDECLARED


# --- edge 2: single-slot policy ------------------------------------------------

def test_cleanup_effect_receipt_single_slot_fails_no_foreign(private_tmp):
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, journal_path = _harness_layout(
        private_tmp
    )
    plant, probe = _write_scripts(bin_dir)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    policy = _three_slot_policy(store_dir, plant, probe)
    policy["slots"] = {"only": _slot_entry("http://127.0.0.1:1")}
    receipt = pc.cleanup_effect_receipt(
        policy,
        _pilot_block(cleanup_script),
        "only@1",
        reach_roots=[reach_root],
        run_cwd=run_cwd,
        cleanup_root=cleanup_repo,
        journal_path=journal_path,
        now=_NOW,
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="strong",
    )
    assert receipt["result"] == pc.RESULT_FAIL
    assert receipt["reason"] == pc.REASON_NO_FOREIGN_NAMESPACE


# --- edge 3: sentinel present at absent probe --------------------------------

def test_cleanup_effect_receipt_fails_sentinel_present_before_plant(private_tmp):
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, journal_path = _harness_layout(
        private_tmp
    )
    plant, probe = _write_scripts(bin_dir)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    policy = _three_slot_policy(store_dir, plant, probe)
    pilot_block = _pilot_block(cleanup_script)
    ids = iter(["fixed-01", "fixed-02", "fixed-03", "fixed-04"])

    def factory():
        return next(ids)

    os.makedirs(os.path.join(store_dir, "slot-a"), exist_ok=True)
    with open(os.path.join(store_dir, "slot-a", "fixed-01"), "w", encoding="utf-8"):
        pass
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
        sentinel_factory=factory,
    )
    assert receipt["result"] == pc.RESULT_FAIL
    assert receipt["reason"] == pc.REASON_RECEIPT_VACUOUS


# --- edge 4: plant nonzero -----------------------------------------------------

def test_cleanup_effect_receipt_plant_nonzero_raises(private_tmp):
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, journal_path = _harness_layout(
        private_tmp
    )
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    _write_executable(plant, "#!/bin/sh\nexit 2\n")
    _write_executable(probe, _probe_script_present())
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.cleanup_effect_receipt(
            _three_slot_policy(store_dir, plant, probe),
            _pilot_block(cleanup_script),
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
    assert exc.value.reason == pc.REFUSAL_PLANT_FAILED


# --- edge 5: sentinel absent post-plant ----------------------------------------

def test_cleanup_effect_receipt_fails_sentinel_absent_after_plant(private_tmp):
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, journal_path = _harness_layout(
        private_tmp
    )
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    _write_executable(plant, "#!/bin/sh\nexit 0\n")
    _write_executable(probe, _probe_script_present())
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    receipt = pc.cleanup_effect_receipt(
        _three_slot_policy(store_dir, plant, probe),
        _pilot_block(cleanup_script),
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
    assert receipt["result"] == pc.RESULT_FAIL
    assert receipt["reason"] == pc.REASON_RECEIPT_VACUOUS


# --- edge 6/7: cleanup fails or times out --------------------------------------

def test_cleanup_effect_receipt_fails_cleanup_nonzero(private_tmp):
    receipt, _ = _run_receipt(private_tmp, _cleanup_fail_script())
    assert receipt["result"] == pc.RESULT_FAIL
    assert receipt["reason"] == pc.REASON_CLEANUP_COMMAND_FAILED


def test_cleanup_effect_receipt_fails_cleanup_timeout(private_tmp):
    timeout_cleanup = "#!/bin/sh\n/bin/sleep 5\nexit 0\n"
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, journal_path = _harness_layout(
        private_tmp
    )
    plant, probe = _write_scripts(bin_dir)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", timeout_cleanup)
    receipt = pc.cleanup_effect_receipt(
        _three_slot_policy(store_dir, plant, probe),
        _pilot_block(cleanup_script),
        _SLOT_REF,
        reach_roots=[reach_root],
        run_cwd=run_cwd,
        cleanup_root=cleanup_repo,
        journal_path=journal_path,
        now=_NOW,
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="strong",
        timeout_seconds=1,
    )
    assert receipt["result"] == pc.RESULT_FAIL
    assert receipt["reason"] == pc.REASON_CLEANUP_COMMAND_FAILED


# --- edge 8: own sentinel survives ---------------------------------------------

def test_cleanup_effect_receipt_fails_own_sentinel_survived(private_tmp):
    receipt, _ = _run_receipt(private_tmp, _cleanup_inert_script())
    assert receipt["result"] == pc.RESULT_FAIL
    assert receipt["reason"] == pc.REASON_OWN_SENTINEL_SURVIVED


# --- edge 9: prefix-sibling foreign destruction --------------------------------

def test_cleanup_effect_receipt_fails_foreign_sentinel_destroyed_prefix_sibling(private_tmp):
    receipt, ctx = _run_receipt(private_tmp, _cleanup_overreach_script())
    assert receipt["result"] == pc.RESULT_FAIL
    assert receipt["reason"] == pc.REASON_FOREIGN_SENTINEL_DESTROYED
    assert "slot-ab" in ctx["policy"]["slots"]


# --- edge 10: indeterminate probe propagates -----------------------------------

def test_cleanup_effect_receipt_indeterminate_probe_raises(private_tmp):
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, journal_path = _harness_layout(
        private_tmp
    )
    plant, probe = _write_scripts(bin_dir)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())

    def probe_then_indeterminate():
        if not hasattr(probe_then_indeterminate, "called"):
            probe_then_indeterminate.called = True
            return _probe_script_present()
        return _probe_script_indeterminate()

    # Use indeterminate probe from the start for preplant
    plant_path, probe_path = _write_scripts(bin_dir, probe_content=_probe_script_indeterminate())
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.cleanup_effect_receipt(
            _three_slot_policy(store_dir, plant_path, probe_path),
            _pilot_block(cleanup_script),
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
    assert exc.value.reason == pc.REFUSAL_PROBE_INDETERMINATE


# --- edge 11: assert_results_only ----------------------------------------------

def test_cleanup_effect_receipt_assert_results_only_refuses_material(private_tmp):
    receipt, ctx = _run_receipt(private_tmp, _cleanup_correct_script())
    assert receipt["result"] == pc.RESULT_PASS
    material = pilot_policy.policy_material(ctx["policy"])
    contaminated = dict(receipt)
    contaminated["evidence"] = ctx["policy"]["datastore"]["connectionDetail"]
    with pytest.raises(pilot_policy.PilotPolicyError) as exc:
        pilot_policy.assert_results_only(contaminated, material)
    assert exc.value.reason == pilot_policy.REFUSAL_MATERIAL_IN_RESULT


# --- edge 15: relative argv0 ---------------------------------------------------

def test_cleanup_effect_receipt_refuses_relative_argv0_before_plant(private_tmp):
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, journal_path = _harness_layout(
        private_tmp
    )
    plant, probe = _write_scripts(bin_dir)
    pilot_block = _pilot_block("/abs/cleanup")
    pilot_block["cleanup"]["command"] = ["npm", "run", "clean", pc.NAMESPACE_PLACEHOLDER]
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.cleanup_effect_receipt(
            _three_slot_policy(store_dir, plant, probe),
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
    assert exc.value.reason == pc.REFUSAL_CLEANUP_ARGV0_NOT_ABSOLUTE
    assert not os.listdir(store_dir)


# --- happy path: passing receipt -----------------------------------------------

def test_cleanup_effect_receipt_pass(private_tmp):
    receipt, ctx = _run_receipt(private_tmp, _cleanup_correct_script())
    assert receipt["result"] == pc.RESULT_PASS
    assert receipt["reason"] is None
    assert receipt["kind"] == pc.KIND_CLEANUP_CONTAINMENT
    assert receipt["slotRef"] == _SLOT_REF
    assert receipt["foreignNamespaces"] == ["slot-ab", "slot-b"]
    assert receipt["assuranceLimits"] == list(pc.ASSURANCE_LIMITS)
    assert all(step in receipt["observations"] for step in ("preplant", "postplant", "postcleanup"))
    assert receipt["residualSentinels"] == [
        {"namespace": "slot-ab"},
        {"namespace": "slot-b"},
    ]
    assert len(receipt["commandDigest"]) == 64
    assert len(receipt["configDigest"]) == 64


# --- receipt_valid_for edge 12 -------------------------------------------------

def test_receipt_valid_for_happy_path(private_tmp):
    receipt, ctx = _run_receipt(private_tmp, _cleanup_correct_script())
    result = pc.receipt_valid_for(
        receipt,
        ctx["policy"],
        ctx["pilot_block"],
        _SLOT_REF,
        cleanup_root=ctx["cleanup_repo"],
        run_cwd=ctx["run_cwd"],
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="strong",
    )
    assert result == {"ok": True, "reason": None}


@pytest.mark.parametrize("receipt", [None, "not-a-dict", {}])
def test_receipt_valid_for_schema_invalid(receipt):
    policy = _sample_policy()
    block = {"cleanup": {"command": ["/x", pc.NAMESPACE_PLACEHOLDER]}}
    result = pc.receipt_valid_for(
        receipt,
        policy,
        block,
        "slot-a@1",
        cleanup_root="/tmp",
        run_cwd="/tmp",
        observed_identity="x",
        identity_provenance="observed",
        identity_strength="strong",
    )
    assert result["ok"] is False
    assert result["reason"] == pc.REASON_RECEIPT_SCHEMA_INVALID


def test_receipt_valid_for_missing_key(private_tmp):
    receipt, ctx = _run_receipt(private_tmp, _cleanup_correct_script())
    del receipt["commandDigest"]
    result = pc.receipt_valid_for(
        receipt,
        ctx["policy"],
        ctx["pilot_block"],
        _SLOT_REF,
        cleanup_root=ctx["cleanup_repo"],
        run_cwd=ctx["run_cwd"],
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="strong",
    )
    assert result == {"ok": False, "reason": pc.REASON_RECEIPT_SCHEMA_INVALID}


def test_receipt_valid_for_fail_result(private_tmp):
    receipt, ctx = _run_receipt(private_tmp, _cleanup_inert_script())
    result = pc.receipt_valid_for(
        receipt,
        ctx["policy"],
        ctx["pilot_block"],
        _SLOT_REF,
        cleanup_root=ctx["cleanup_repo"],
        run_cwd=ctx["run_cwd"],
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="strong",
    )
    assert result == {"ok": False, "reason": pc.REASON_RECEIPT_NOT_PASS}


def test_receipt_valid_for_slot_mismatch(private_tmp):
    receipt, ctx = _run_receipt(private_tmp, _cleanup_correct_script())
    result = pc.receipt_valid_for(
        receipt,
        ctx["policy"],
        ctx["pilot_block"],
        "slot-b@1",
        cleanup_root=ctx["cleanup_repo"],
        run_cwd=ctx["run_cwd"],
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="strong",
    )
    assert result == {"ok": False, "reason": pc.REASON_RECEIPT_SLOT_MISMATCH}


def test_receipt_valid_for_stale_command(private_tmp):
    receipt, ctx = _run_receipt(private_tmp, _cleanup_correct_script())
    ctx["pilot_block"]["cleanup"]["command"] = [
        ctx["cleanup_script"],
        pc.NAMESPACE_PLACEHOLDER,
        "--extra",
    ]
    result = pc.receipt_valid_for(
        receipt,
        ctx["policy"],
        ctx["pilot_block"],
        _SLOT_REF,
        cleanup_root=ctx["cleanup_repo"],
        run_cwd=ctx["run_cwd"],
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="strong",
    )
    assert result == {"ok": False, "reason": pc.REASON_RECEIPT_STALE_COMMAND}


def test_receipt_valid_for_stale_config_edited_script(private_tmp):
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, journal_path = _harness_layout(
        private_tmp
    )
    plant, probe = _write_scripts(bin_dir)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    subprocess.run(
        ["git", "-C", cleanup_repo, "add", "cleanup.sh"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", cleanup_repo, "-c", "user.email=pilot@example.test",
         "-c", "user.name=Pilot", "commit", "-m", "add cleanup"],
        check=True,
        capture_output=True,
    )
    policy = _three_slot_policy(store_dir, plant, probe)
    pilot_block = _pilot_block(cleanup_script)
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
    with open(cleanup_script, "a", encoding="utf-8") as handle:
        handle.write("# edited\n")
    result = pc.receipt_valid_for(
        receipt,
        policy,
        pilot_block,
        _SLOT_REF,
        cleanup_root=cleanup_repo,
        run_cwd=run_cwd,
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="strong",
    )
    assert result == {"ok": False, "reason": pc.REASON_RECEIPT_STALE_CONFIG}


def test_receipt_valid_for_stale_observed_identity(private_tmp):
    receipt, ctx = _run_receipt(private_tmp, _cleanup_correct_script())
    result = pc.receipt_valid_for(
        receipt,
        ctx["policy"],
        ctx["pilot_block"],
        _SLOT_REF,
        cleanup_root=ctx["cleanup_repo"],
        run_cwd=ctx["run_cwd"],
        observed_identity="other_dev",
        identity_provenance="observed",
        identity_strength="strong",
    )
    assert result == {"ok": False, "reason": pc.REASON_RECEIPT_STALE_CONFIG}


def test_receipt_valid_for_stale_identity_strength(private_tmp):
    receipt, ctx = _run_receipt(private_tmp, _cleanup_correct_script())
    result = pc.receipt_valid_for(
        receipt,
        ctx["policy"],
        ctx["pilot_block"],
        _SLOT_REF,
        cleanup_root=ctx["cleanup_repo"],
        run_cwd=ctx["run_cwd"],
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="weaker",
    )
    assert result == {"ok": False, "reason": pc.REASON_RECEIPT_STALE_CONFIG}


# --- registry_record edge 13 ---------------------------------------------------

def test_registry_record_refuses_fail_receipt(private_tmp):
    receipt, ctx = _run_receipt(private_tmp, _cleanup_inert_script())
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.registry_record(receipt, ctx["pilot_block"]["cleanup"])
    assert exc.value.reason == pc.REASON_RECEIPT_NOT_PASS


def test_registry_record_refuses_malformed():
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.registry_record({"kind": "wrong"}, {"command": []})
    assert exc.value.reason == pc.REASON_RECEIPT_SCHEMA_INVALID


def test_registry_record_closes_is_exercised_loop(private_tmp):
    receipt, ctx = _run_receipt(private_tmp, _cleanup_correct_script())
    record = pc.registry_record(receipt, ctx["pilot_block"]["cleanup"])
    registry = _registry_with(record)
    assert pilot_contract.is_exercised(
        registry,
        "cleanup-containment",
        ctx["pilot_block"]["cleanup"],
    ) is True


# --- resolve_containment edge 14 -----------------------------------------------

def test_resolve_containment_permissions_win_over_receipt(private_tmp):
    receipt, ctx = _run_receipt(private_tmp, _cleanup_correct_script())
    policy = ctx["policy"]
    policy["datastore"]["containment"]["permissions"] = {
        "cannotReachForeignNamespaces": True,
        "evidence": "isolated datastore",
    }
    result = pc.resolve_containment(
        policy,
        ctx["pilot_block"],
        _SLOT_REF,
        receipt=receipt,
        cleanup_root=ctx["cleanup_repo"],
        run_cwd=ctx["run_cwd"],
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="strong",
    )
    assert result["mode"] == pc.MODE_PERMISSIONS


def test_resolve_containment_permissions_false_does_not_win(private_tmp):
    receipt, ctx = _run_receipt(private_tmp, _cleanup_correct_script())
    policy = ctx["policy"]
    policy["datastore"]["containment"]["permissions"]["cannotReachForeignNamespaces"] = False
    result = pc.resolve_containment(
        policy,
        ctx["pilot_block"],
        _SLOT_REF,
        receipt=receipt,
        cleanup_root=ctx["cleanup_repo"],
        run_cwd=ctx["run_cwd"],
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="strong",
    )
    assert result["mode"] == pc.MODE_RECEIPT


def test_resolve_containment_permissions_empty_evidence_does_not_win(private_tmp):
    receipt, ctx = _run_receipt(private_tmp, _cleanup_correct_script())
    policy = ctx["policy"]
    policy["datastore"]["containment"]["permissions"] = {
        "cannotReachForeignNamespaces": True,
        "evidence": "",
    }
    result = pc.resolve_containment(
        policy,
        ctx["pilot_block"],
        _SLOT_REF,
        receipt=receipt,
        cleanup_root=ctx["cleanup_repo"],
        run_cwd=ctx["run_cwd"],
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="strong",
    )
    assert result["mode"] == pc.MODE_RECEIPT


def test_resolve_containment_single_slot(private_tmp):
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, _ = _harness_layout(private_tmp)
    plant, probe = _write_scripts(bin_dir)
    policy = _three_slot_policy(store_dir, plant, probe)
    policy["slots"] = {"only": _slot_entry("http://127.0.0.1:1")}
    result = pc.resolve_containment(policy, _pilot_block("/x"), "only@1")
    assert result["mode"] == pc.MODE_SINGLE_SLOT


def test_resolve_containment_valid_receipt(private_tmp):
    receipt, ctx = _run_receipt(private_tmp, _cleanup_correct_script())
    result = pc.resolve_containment(
        ctx["policy"],
        ctx["pilot_block"],
        _SLOT_REF,
        receipt=receipt,
        cleanup_root=ctx["cleanup_repo"],
        run_cwd=ctx["run_cwd"],
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="strong",
    )
    assert result["mode"] == pc.MODE_RECEIPT


def test_resolve_containment_stale_receipt(private_tmp):
    receipt, ctx = _run_receipt(private_tmp, _cleanup_correct_script())
    ctx["pilot_block"]["cleanup"]["command"] = [ctx["cleanup_script"], pc.NAMESPACE_PLACEHOLDER, "x"]
    result = pc.resolve_containment(
        ctx["policy"],
        ctx["pilot_block"],
        _SLOT_REF,
        receipt=receipt,
        cleanup_root=ctx["cleanup_repo"],
        run_cwd=ctx["run_cwd"],
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="strong",
    )
    assert result["mode"] == pc.MODE_REFUSED
    assert result["reason"] == pc.REASON_RECEIPT_STALE_COMMAND


def test_resolve_containment_receipt_without_cleanup_root(private_tmp):
    receipt, ctx = _run_receipt(private_tmp, _cleanup_correct_script())
    result = pc.resolve_containment(
        ctx["policy"],
        ctx["pilot_block"],
        _SLOT_REF,
        receipt=receipt,
        cleanup_root=None,
        run_cwd=ctx["run_cwd"],
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="strong",
    )
    assert result["mode"] == pc.MODE_REFUSED
    assert result["reason"] == pc.REASON_RECEIPT_SCHEMA_INVALID


def test_resolve_containment_undeclared(private_tmp):
    reach_root, run_cwd, bin_dir, store_dir, _, _ = _harness_layout(private_tmp)
    plant, probe = _write_scripts(bin_dir)
    policy = _three_slot_policy(store_dir, plant, probe)
    result = pc.resolve_containment(policy, _pilot_block("/x"), _SLOT_REF)
    assert result == {
        "mode": pc.MODE_REFUSED,
        "reason": pc.REASON_CONTAINMENT_UNDECLARED,
        "remedy": "isolated datastores, or one slot",
    }


# --- resurrection_plan edge 16 -------------------------------------------------

def test_resurrection_plan_refuses_missing_effects_escape():
    block = _pilot_block("/x")
    del block["effectsEscape"]
    with pytest.raises(pilot_contract.PilotContractError):
        pc.resurrection_plan(
            _sample_policy(),
            block,
            _SLOT_REF,
            registry={},
            containment={"mode": pc.MODE_SINGLE_SLOT},
            journal_path="/tmp/journal.jsonl",
        )


def test_resurrection_plan_refuses_unexercised_effects_escape(private_tmp):
    policy, _, _, cleanup_repo = _resurrection_policy(private_tmp)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    block = _pilot_block(cleanup_script)
    result = pc.resurrection_plan(
        policy,
        block,
        _SLOT_REF,
        registry=_registry_with(),
        containment={"mode": pc.MODE_SINGLE_SLOT},
        journal_path=os.path.join(private_tmp, "j.jsonl"),
    )
    assert result == {"action": pc.ACTION_REFUSE, "reason": pc.REASON_EFFECTS_ESCAPE_UNEXERCISED}


def test_resurrection_plan_parks_when_effects_escape(private_tmp):
    policy, _, _, cleanup_repo = _resurrection_policy(private_tmp)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    block = _pilot_block(cleanup_script)
    block["effectsEscape"]["canEscape"] = True
    registry = _registry_with(_effects_escape_record(block))
    result = pc.resurrection_plan(
        policy,
        block,
        _SLOT_REF,
        registry=registry,
        containment={"mode": pc.MODE_SINGLE_SLOT},
        journal_path=os.path.join(private_tmp, "j.jsonl"),
        verdict=_passing_verdict(policy),
    )
    assert result["action"] == pc.ACTION_PARK
    assert result["reason"] == pc.REASON_EFFECTS_ESCAPE_PARK
    assert result["steps"] == []
    assert "owner" in result


def test_resurrection_plan_refuses_unresolved_containment(private_tmp):
    policy, _, _, cleanup_repo = _resurrection_policy(private_tmp)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    block = _pilot_block(cleanup_script)
    registry = _registry_with(_effects_escape_record(block))
    result = pc.resurrection_plan(
        policy,
        block,
        _SLOT_REF,
        registry=registry,
        containment={"mode": pc.MODE_REFUSED},
        journal_path=os.path.join(private_tmp, "j.jsonl"),
        verdict=_passing_verdict(policy),
    )
    assert result == {"action": pc.ACTION_REFUSE, "reason": pc.REASON_CONTAINMENT_UNRESOLVED}


def test_resurrection_plan_refuses_unexercised_cleanup_containment(private_tmp):
    policy, _, _, cleanup_repo = _resurrection_policy(private_tmp)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    block = _pilot_block(cleanup_script)
    registry = _registry_with(_effects_escape_record(block))
    result = pc.resurrection_plan(
        policy,
        block,
        _SLOT_REF,
        registry=registry,
        containment={"mode": pc.MODE_RECEIPT},
        journal_path=os.path.join(private_tmp, "j.jsonl"),
        verdict=_passing_verdict(policy),
    )
    assert result == {"action": pc.ACTION_REFUSE, "reason": pc.REASON_CONTAINMENT_UNEXERCISED}


def _take_receipt(private_tmp, policy, pilot_block, reach_root, run_cwd, cleanup_repo):
    journal_path = os.path.join(private_tmp, "journal.jsonl")
    return pc.cleanup_effect_receipt(
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


def test_resurrection_plan_refuses_missing_verdict(private_tmp):
    policy, reach_root, run_cwd, cleanup_repo = _resurrection_policy(private_tmp)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    block = _pilot_block(cleanup_script)
    receipt = _take_receipt(private_tmp, policy, block, reach_root, run_cwd, cleanup_repo)
    registry = _registry_with(
        _effects_escape_record(block),
        _cleanup_containment_record(block, receipt),
    )
    result = pc.resurrection_plan(
        policy,
        block,
        _SLOT_REF,
        registry=registry,
        containment={"mode": pc.MODE_RECEIPT},
        journal_path=os.path.join(private_tmp, "j.jsonl"),
        verdict=None,
    )
    assert result == {"action": pc.ACTION_REFUSE, "reason": pc.REASON_VERDICT_MISSING}


def test_resurrection_plan_captured_happy_path(private_tmp):
    policy, reach_root, run_cwd, cleanup_repo = _resurrection_policy(private_tmp)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    block = _pilot_block(cleanup_script)
    receipt = _take_receipt(private_tmp, policy, block, reach_root, run_cwd, cleanup_repo)
    registry = _registry_with(
        _effects_escape_record(block),
        _cleanup_containment_record(block, receipt),
    )
    artifact_path = os.path.join(private_tmp, "seed.bin")
    with open(artifact_path, "wb") as handle:
        handle.write(b"artifact")
    os.chmod(artifact_path, 0o600)
    artifact = {
        "path": artifact_path,
        "expectedUid": os.getuid(),
        "expectedMode": 0o600,
        "sha256": hashlib.sha256(b"artifact").hexdigest(),
        "captureSurfaces": ["cookies"],
    }
    plan = pc.resurrection_plan(
        policy,
        block,
        _SLOT_REF,
        registry=registry,
        containment={"mode": pc.MODE_RECEIPT},
        journal_path=os.path.join(private_tmp, "j.jsonl"),
        verdict=_passing_verdict(policy),
        account="owner",
        artifact=artifact,
    )
    assert plan["action"] == pc.ACTION_RESURRECT
    assert plan["slotRef"] == _SLOT_REF
    assert plan["steps"][0]["op"] == "cleanup"
    assert plan["steps"][1]["op"] == "reseed"
    assert plan["steps"][1]["path"] == "captured"
    assert plan["steps"][2]["op"] == "begin-generation"
    assert plan["steps"][3]["op"] == "resume"


def test_resurrection_plan_minted_happy_path(private_tmp):
    policy, reach_root, run_cwd, cleanup_repo = _resurrection_policy(private_tmp)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    block = _pilot_block(cleanup_script)
    block["signInPath"] = "minted"
    block["mint"] = {
        "envelope": {
            "enablingFlagEnvVar": "ALLOW_TEST_MINT",
            "enabledScopes": ["development"],
            "forbiddenScopes": ["production"],
            "gateOffTestCommand": ["true"],
        },
        "sentinelIdentifier": "pilot-sentinel-no-such-account",
    }
    receipt = _take_receipt(private_tmp, policy, block, reach_root, run_cwd, cleanup_repo)
    registry = _registry_with(
        _effects_escape_record(block),
        _cleanup_containment_record(block, receipt),
    )
    plan = pc.resurrection_plan(
        policy,
        block,
        _SLOT_REF,
        registry=registry,
        containment={"mode": pc.MODE_RECEIPT},
        journal_path=os.path.join(private_tmp, "j.jsonl"),
        verdict=_passing_verdict(policy),
        account="owner",
        mint_envelope=block["mint"]["envelope"],
    )
    assert plan["action"] == pc.ACTION_RESURRECT
    assert plan["steps"][1]["path"] == "minted"


def test_resurrection_plan_unauthorized_verdict_propagates(private_tmp):
    policy, reach_root, run_cwd, cleanup_repo = _resurrection_policy(private_tmp)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    block = _pilot_block(cleanup_script)
    receipt = _take_receipt(private_tmp, policy, block, reach_root, run_cwd, cleanup_repo)
    registry = _registry_with(
        _effects_escape_record(block),
        _cleanup_containment_record(block, receipt),
    )
    verdict = _passing_verdict(policy)
    verdict["result"] = "refuse"
    artifact_path = os.path.join(private_tmp, "seed.bin")
    with open(artifact_path, "wb") as handle:
        handle.write(b"artifact")
    artifact = {
        "path": artifact_path,
        "expectedUid": os.getuid(),
        "expectedMode": 0o600,
        "sha256": hashlib.sha256(b"artifact").hexdigest(),
        "captureSurfaces": ["cookies"],
    }
    with pytest.raises(pilot_boundary.PilotBoundaryError):
        pc.resurrection_plan(
            policy,
            block,
            _SLOT_REF,
            registry=registry,
            containment={"mode": pc.MODE_RECEIPT},
            journal_path=os.path.join(private_tmp, "j.jsonl"),
            verdict=verdict,
            account="owner",
            artifact=artifact,
        )
