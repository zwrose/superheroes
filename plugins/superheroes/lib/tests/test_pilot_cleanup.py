"""Tests for pilot_cleanup.py — cleanup primitives and receipt binding."""
import copy
import errno
import hashlib
import inspect
import json
import os
import stat
import subprocess
import sys
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_boundary  # noqa: E402
import pilot_contract  # noqa: E402
import pilot_journal  # noqa: E402
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
        "source_identity": {
            "head": None,
            "worktreeDigest": "a" * 64,
            "argv0Digest": None,
            "argvDigests": [],
        },
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
    assert result == {"exit": 0, "timedOut": False, "stdoutBytes": 0, "stdoutTruncated": False}


def test_run_bounded_exit_one(private_tmp):
    _, run_cwd, bin_dir = _confinement_layout(private_tmp)
    script = os.path.join(bin_dir, "exit1.sh")
    _write_executable(script, "#!/bin/sh\nexit 1\n")
    result = pc.run_bounded([script], cwd=run_cwd, env={})
    assert result == {"exit": 1, "timedOut": False, "stdoutBytes": 0, "stdoutTruncated": False}


def test_run_bounded_exit_forty_two(private_tmp):
    _, run_cwd, bin_dir = _confinement_layout(private_tmp)
    script = os.path.join(bin_dir, "exit42.sh")
    _write_executable(script, "#!/bin/sh\nexit 42\n")
    result = pc.run_bounded([script], cwd=run_cwd, env={})
    assert result == {"exit": 42, "timedOut": False, "stdoutBytes": 0, "stdoutTruncated": False}


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
    assert result["stdoutBytes"] == 100
    assert result["stdoutTruncated"] is True
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
    assert len(result["worktreeDigest"]) == 64
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
    assert len(result["worktreeDigest"]) == 64


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


def test_argv0_content_digest_unreadable_regular_file(private_tmp):
    path = os.path.join(private_tmp, "script.sh")
    with open(path, "wb") as handle:
        handle.write(b"content\n")
    os.chmod(path, 0o000)
    try:
        assert pc.argv0_content_digest(path) is None
    finally:
        os.chmod(path, stat.S_IMODE(os.stat(path).st_mode) | 0o600)


def test_argv0_content_digest_large_file(private_tmp):
    path = os.path.join(private_tmp, "large.sh")
    digest = hashlib.sha256()
    with open(path, "wb") as handle:
        for _ in range(64):
            chunk = b"x" * 65536
            handle.write(chunk)
            digest.update(chunk)
    expected = digest.hexdigest()
    assert pc.argv0_content_digest(path) == expected


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
            "source_identity": {
                "head": "a" * 40,
                "worktreeDigest": "b" * 64,
                "argv0Digest": None,
                "argvDigests": [],
            }
        })),
    ],
    ids=[
        "resolvedCleanupArgv",
        "sentinelPlantCommand",
        "sentinelProbeCommand",
        "sentinelConnectionEnvVar",
        "connectionDetailViaBindingKey",
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

def test_cleanup_effect_receipt_plant_nonzero_returns_fail_receipt(private_tmp):
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, journal_path = _harness_layout(
        private_tmp
    )
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    _write_executable(plant, "#!/bin/sh\nexit 2\n")
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
    assert receipt["reason"] == pc.REFUSAL_PLANT_FAILED
    assert len(receipt["residualSentinels"]) == 1
    assert receipt["residualSentinels"][0]["namespace"] == "slot-a"
    assert receipt["residualSentinels"][0]["state"] == "possibly-planted"


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


def test_cleanup_effect_receipt_own_plant_silently_failing_is_vacuous(private_tmp):
    # The sibling test's plant no-ops for every namespace, so a missing vacuity check
    # is masked by the foreign-sentinel detector; this fixture isolates own-namespace
    # plant failure, which is the path where vacuity removal yields a false pass.
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, journal_path = _harness_layout(
        private_tmp
    )
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    selective_plant = (
        "#!/bin/sh\n"
        'ns="$2"\n'
        'id="$4"\n'
        'store="$PILOT_DATASTORE_URL"\n'
        'if [ "$ns" = "slot-a" ]; then\n'
        "  exit 0\n"
        "fi\n"
        'mkdir -p "$store/$ns"\n'
        'touch "$store/$ns/$id"\n'
        "exit 0\n"
    )
    _write_executable(plant, selective_plant)
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
    postplant = receipt["observations"]["postplant"]
    assert postplant["slot-a"] is False
    for foreign in ("slot-ab", "slot-b"):
        assert postplant[foreign] is True


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


def test_cleanup_effect_receipt_indeterminate_probe_after_cleanup_raises(private_tmp):
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, journal_path = _harness_layout(
        private_tmp
    )
    count_file = os.path.join(private_tmp, "probe-count.txt")
    counting_probe = (
        "#!/bin/sh\n"
        f'countfile="{count_file}"\n'
        "if [ -f \"$countfile\" ]; then\n"
        "  n=$(cat \"$countfile\")\n"
        "else\n"
        "  n=0\n"
        "fi\n"
        "echo $((n + 1)) > \"$countfile\"\n"
        "if [ \"$n\" -ge 6 ]; then exit 2; fi\n"
        'ns="$2"\n'
        'id="$4"\n'
        'store="$PILOT_DATASTORE_URL"\n'
        'if [ -f "$store/$ns/$id" ]; then exit 0; else exit 1; fi\n'
    )
    plant, _ = _write_scripts(bin_dir)
    probe = os.path.join(bin_dir, "counting-probe.sh")
    _write_executable(probe, counting_probe)
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


# axis: refusal precedes sentinel plant
def test_cleanup_effect_receipt_refuses_unbindable_argv_tail(private_tmp):
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, journal_path = _harness_layout(
        private_tmp
    )
    plant, probe = _write_scripts(bin_dir)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    policy = _three_slot_policy(store_dir, plant, probe)
    pilot_block = _pilot_block(cleanup_script)
    os.makedirs(os.path.join(run_cwd, "slot-a"))
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.cleanup_effect_receipt(
            policy=policy,
            pilot_block=pilot_block,
            slot_ref=_SLOT_REF,
            reach_roots=[reach_root],
            run_cwd=run_cwd,
            cleanup_root=cleanup_repo,
            journal_path=journal_path,
            now=_NOW,
            observed_identity="example_dev",
            identity_provenance="observed",
            identity_strength="strong",
        )
    assert exc.value.reason == pc.REFUSAL_SOURCE_ARGV_UNBINDABLE
    assert not os.listdir(store_dir)


# --- happy path: passing receipt -----------------------------------------------

def test_cleanup_effect_receipt_pass(private_tmp):
    planned_ids = {
        "slot-a": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "slot-ab": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "slot-b": "cccccccccccccccccccccccccccccccc",
    }
    id_queue = list(planned_ids.values())

    def factory():
        return id_queue.pop(0)

    receipt, ctx = _run_receipt(
        private_tmp,
        _cleanup_correct_script(),
        sentinel_factory=factory,
    )
    assert receipt["result"] == pc.RESULT_PASS
    assert receipt["reason"] is None
    assert receipt["kind"] == pc.KIND_CLEANUP_CONTAINMENT
    assert receipt["slotRef"] == _SLOT_REF
    assert receipt["foreignNamespaces"] == ["slot-ab", "slot-b"]
    assert receipt["assuranceLimits"] == list(pc.ASSURANCE_LIMITS)
    assert all(step in receipt["observations"] for step in ("preplant", "postplant", "postcleanup"))
    assert receipt["residualSentinels"] == [
        {
            "namespace": "slot-ab",
            "sentinelId": planned_ids["slot-ab"],
            "state": "planted",
        },
        {
            "namespace": "slot-b",
            "sentinelId": planned_ids["slot-b"],
            "state": "planted",
        },
    ]
    assert len(receipt["commandDigest"]) == 64
    assert len(receipt["configDigest"]) == 64


# --- receipt_valid_for edge 12 -------------------------------------------------

def test_receipt_valid_for_happy_path(private_tmp):
    receipt, ctx = _run_receipt(private_tmp, _cleanup_correct_script())
    assert pc._digest_hex_valid(receipt["commandDigest"])
    assert pc._digest_hex_valid(receipt["configDigest"])
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


# axis: receipt_valid_for re-checks argv-tail binding
def test_receipt_valid_for_refuses_unbindable_argv_tail(private_tmp):
    receipt, ctx = _run_receipt(private_tmp, _cleanup_correct_script())
    os.makedirs(os.path.join(ctx["run_cwd"], "slot-a"))
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.receipt_valid_for(
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
    assert exc.value.reason == pc.REFUSAL_SOURCE_ARGV_UNBINDABLE


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
        pc.cleanup_containment_exercise_declaration(
            ctx["pilot_block"]["cleanup"],
            receipt["slot"],
        ),
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


def test_resolve_containment_permissions_empty_evidence_does_not_win(private_tmp, monkeypatch):
    original_validate_containment = pilot_policy._validate_containment

    def _validate_containment_allow_empty_evidence(containment):
        if isinstance(containment, dict):
            permissions = containment.get("permissions")
            if (
                isinstance(permissions, dict)
                and permissions.get("cannotReachForeignNamespaces") is True
                and permissions.get("evidence") == ""
            ):
                patched = copy.deepcopy(containment)
                patched["permissions"]["evidence"] = "validation-placeholder"
                return original_validate_containment(patched)
        return original_validate_containment(containment)

    monkeypatch.setattr(
        pilot_policy,
        "_validate_containment",
        _validate_containment_allow_empty_evidence,
    )
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, journal_path = _harness_layout(
        private_tmp
    )
    plant, probe = _write_scripts(bin_dir)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    policy = _three_slot_policy(store_dir, plant, probe)
    policy["datastore"]["containment"]["permissions"] = {
        "cannotReachForeignNamespaces": True,
        "evidence": "",
    }
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
    result = pc.resolve_containment(
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
    assert result["mode"] == pc.MODE_RECEIPT


def test_receipt_invalidated_by_any_policy_mutation(private_tmp):
    receipt, ctx = _run_receipt(private_tmp, _cleanup_correct_script())
    policy = ctx["policy"]
    policy["protectedTargets"].append("something-new")
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
    assert result["mode"] == pc.MODE_REFUSED
    assert result["reason"] == pc.REASON_RECEIPT_STALE_COMMAND


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


# --- _guarded_plan_view --------------------------------------------------------

def test_guarded_plan_view_replaces_only_the_reseed_request():
    reseed_request = {
        "account": "owner",
        "slotRef": "slot-a@1",
        "artifact": {"path": "/tmp/seed.bin", "sha256": "abc"},
    }
    plan = {
        "action": pc.ACTION_RESURRECT,
        "slotRef": "slot-a@1",
        "steps": [
            {
                "op": "cleanup",
                "argv": ["/abs/cleanup", "slot-a"],
                "namespace": "slot-a",
                "journal": {
                    "kind": "namespace-touched",
                    "slotRef": "slot-a@1",
                    "nested": {"a": 1},
                },
            },
            {"op": "reseed", "request": reseed_request, "path": "captured"},
            {
                "op": "begin-generation",
                "owner": "C7",
                "requires": "released",
                "note": "generation bump",
            },
            {"op": "resume", "owner": "C7"},
        ],
    }
    original_request = plan["steps"][1]["request"]
    view = pc._guarded_plan_view(plan)
    assert plan["steps"][1]["request"] is original_request
    expected = copy.deepcopy(plan)
    expected["steps"][1]["request"] = "<authorized-reseed-request>"
    assert view == expected


def test_guarded_plan_view_still_refuses_material_outside_the_reseed_request(private_tmp):
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, _ = _harness_layout(private_tmp)
    plant, probe = _write_scripts(bin_dir)
    policy = _three_slot_policy(store_dir, plant, probe)
    policy["slots"]["slot-a"]["mintableAccounts"] = ["owner"]
    material = pilot_policy.policy_material(policy)
    connection_leak = material["connection-detail"][0]
    plan = {
        "action": pc.ACTION_RESURRECT,
        "steps": [
            {"op": "cleanup", "argv": [connection_leak, "slot-a"]},
            {
                "op": "reseed",
                "request": {"account": "owner", "slotRef": "slot-a@1"},
                "path": "captured",
            },
        ],
    }
    with pytest.raises(pilot_policy.PilotPolicyError):
        pilot_policy.assert_results_only(pc._guarded_plan_view(plan), material)


def test_guarded_plan_view_tolerates_a_park_plan():
    plan = {
        "action": pc.ACTION_PARK,
        "reason": pc.REASON_EFFECTS_ESCAPE_PARK,
        "owner": "owner inspection required",
        "steps": [],
    }
    view = pc._guarded_plan_view(plan)
    assert view == plan
    assert view is not plan


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
        journal_path=os.path.join(private_tmp, "j.jsonl"),
        verdict=_passing_verdict(policy),
    )
    assert result["action"] == pc.ACTION_REFUSE
    assert result["reason"] == pc.REASON_CONTAINMENT_UNRESOLVED
    assert "containment" in result


def test_resurrection_plan_refuses_unexercised_cleanup_containment(private_tmp):
    policy, reach_root, run_cwd, cleanup_repo = _resurrection_policy(private_tmp)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    block = _pilot_block(cleanup_script)
    receipt = _take_receipt(private_tmp, policy, block, reach_root, run_cwd, cleanup_repo)
    registry = _registry_with(_effects_escape_record(block))
    result = pc.resurrection_plan(
        policy,
        block,
        _SLOT_REF,
        registry=registry,
        journal_path=os.path.join(private_tmp, "j.jsonl"),
        verdict=_passing_verdict(policy),
        receipt=receipt,
        cleanup_root=cleanup_repo,
        run_cwd=run_cwd,
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="strong",
    )
    assert result["action"] == pc.ACTION_REFUSE
    assert result["reason"] == pc.REASON_CONTAINMENT_UNEXERCISED
    assert result["containment"]["mode"] == pc.MODE_RECEIPT


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
        journal_path=os.path.join(private_tmp, "j.jsonl"),
        verdict=None,
        receipt=receipt,
        cleanup_root=cleanup_repo,
        run_cwd=run_cwd,
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="strong",
    )
    assert result["action"] == pc.ACTION_REFUSE
    assert result["reason"] == pc.REASON_VERDICT_MISSING


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
        journal_path=os.path.join(private_tmp, "j.jsonl"),
        verdict=_passing_verdict(policy),
        account="owner",
        artifact=artifact,
        receipt=receipt,
        cleanup_root=cleanup_repo,
        run_cwd=run_cwd,
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="strong",
    )
    assert plan["action"] == pc.ACTION_RESURRECT
    assert plan["slotRef"] == _SLOT_REF
    assert plan["containment"]["mode"] == pc.MODE_RECEIPT
    assert plan["steps"][0]["op"] == "cleanup"
    assert plan["steps"][1]["op"] == "reseed"
    assert plan["steps"][1]["path"] == "captured"
    assert plan["steps"][2]["op"] == "begin-generation"
    assert plan["steps"][3]["op"] == "resume"
    # axis: the plan-step key is `owner` again (#866 reverting #857's dodge), and this policy
    # declares a mintable account literally named `owner` — so these two lines are also the
    # regression proof that #870's guard no longer refuses a plan whose step key spells an
    # account name. Undo #870's carve-out and `resurrection_plan` raises before it returns.
    assert plan["steps"][2]["owner"] == "C7"
    assert plan["steps"][3]["owner"] == "C7"


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
        journal_path=os.path.join(private_tmp, "j.jsonl"),
        verdict=_passing_verdict(policy),
        account="owner",
        mint_envelope=block["mint"]["envelope"],
        receipt=receipt,
        cleanup_root=cleanup_repo,
        run_cwd=run_cwd,
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="strong",
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
            journal_path=os.path.join(private_tmp, "j.jsonl"),
            verdict=verdict,
            account="owner",
            artifact=artifact,
            receipt=receipt,
            cleanup_root=cleanup_repo,
            run_cwd=run_cwd,
            observed_identity="example_dev",
            identity_provenance="observed",
            identity_strength="strong",
        )


# --- FIX-1: content-addressed source binding -----------------------------------

def test_source_identity_detects_second_edit_to_dirty_file(private_tmp):
    repo = os.path.join(private_tmp, "git-repo")
    os.makedirs(repo)
    _init_git_repo(repo)
    script = os.path.join(repo, "cleanup.sh")
    _write_executable(script, "#!/bin/sh\necho v1\n")
    subprocess.run(["git", "-C", repo, "add", "cleanup.sh"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", repo, "-c", "user.email=pilot@example.test", "-c", "user.name=Pilot",
         "commit", "-m", "add cleanup"],
        check=True,
        capture_output=True,
    )
    with open(script, "w", encoding="utf-8") as handle:
        handle.write("#!/bin/sh\necho v2\n")
    first = pc.source_identity(repo)
    with open(script, "w", encoding="utf-8") as handle:
        handle.write("#!/bin/sh\necho v3\n")
    second = pc.source_identity(repo)
    assert first["worktreeDigest"] != second["worktreeDigest"]


def test_source_identity_detects_edit_to_untracked_file(private_tmp):
    repo = os.path.join(private_tmp, "git-repo")
    os.makedirs(repo)
    _init_git_repo(repo)
    script = os.path.join(repo, "cleanup.sh")
    _write_executable(script, "#!/bin/sh\necho v1\n")
    first = pc.source_identity(repo)
    with open(script, "w", encoding="utf-8") as handle:
        handle.write("#!/bin/sh\necho v2\n")
    second = pc.source_identity(repo)
    assert first["worktreeDigest"] != second["worktreeDigest"]


def test_source_identity_detects_deleted_file(private_tmp):
    repo = os.path.join(private_tmp, "git-repo")
    os.makedirs(repo)
    _init_git_repo(repo)
    script = os.path.join(repo, "cleanup.sh")
    _write_executable(script, "#!/bin/sh\necho v1\n")
    first = pc.source_identity(repo)
    os.remove(script)
    second = pc.source_identity(repo)
    assert first["worktreeDigest"] != second["worktreeDigest"]


def test_source_identity_handles_path_with_space(private_tmp):
    repo = os.path.join(private_tmp, "git-repo")
    os.makedirs(repo)
    _init_git_repo(repo)
    spaced = os.path.join(repo, "my script.sh")
    _write_executable(spaced, "#!/bin/sh\necho v1\n")
    first = pc.source_identity(repo)
    with open(spaced, "w", encoding="utf-8") as handle:
        handle.write("#!/bin/sh\necho v2\n")
    second = pc.source_identity(repo)
    assert first["worktreeDigest"] != second["worktreeDigest"]


def test_receipt_valid_for_stale_config_interpreter_invoked_script(private_tmp):
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, journal_path = _harness_layout(
        private_tmp
    )
    plant, probe = _write_scripts(bin_dir)
    cleanup_script = os.path.join(bin_dir, "cleanup.sh")
    _write_executable(cleanup_script, _cleanup_correct_script())
    subprocess.run(
        ["git", "-C", cleanup_repo, "-c", "user.email=pilot@example.test", "-c", "user.name=Pilot",
         "commit", "--allow-empty", "-m", "pin clean root"],
        check=True,
        capture_output=True,
    )
    policy = _three_slot_policy(store_dir, plant, probe)
    pilot_block = {
        "schemaVersion": 1,
        "signInPath": "captured",
        "credentialSet": [{"account": "owner", "role": "resource-owner"}],
        "captureSurface": ["cookies"],
        "captureOptions": {"indexedDB": False, "credentials": False},
        "validityProvenance": "server-probe",
        "identityProbe": {"path": "/api/me", "unseededExpectation": "no-session"},
        "cleanup": {
            "command": ["/bin/sh", cleanup_script, pc.NAMESPACE_PLACEHOLDER],
        },
        "administrativeMax": 4,
        "effectsEscape": {
            "canEscape": False,
            "evidence": "dev mail capture",
        },
        "policyRef": {"declaration": "example-project-pilot-policy"},
    }
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


def test_source_identity_ignores_inherited_git_dir(private_tmp, monkeypatch):
    repo = os.path.join(private_tmp, "target-repo")
    other = os.path.join(private_tmp, "other-repo")
    os.makedirs(repo)
    os.makedirs(other)
    _init_git_repo(repo)
    _init_git_repo(other)
    marker = os.path.join(repo, "marker.txt")
    with open(marker, "w", encoding="utf-8") as handle:
        handle.write("bound\n")
    other_marker = os.path.join(other, "other.txt")
    with open(other_marker, "w", encoding="utf-8") as handle:
        handle.write("other\n")
    subprocess.run(["git", "-C", other, "add", "other.txt"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", other, "-c", "user.email=pilot@example.test", "-c", "user.name=Pilot",
         "commit", "-m", "other"],
        check=True,
        capture_output=True,
    )
    baseline = pc.source_identity(repo)
    monkeypatch.setenv("GIT_DIR", os.path.join(other, ".git"))
    poisoned = pc.source_identity(repo)
    assert poisoned["worktreeDigest"] == baseline["worktreeDigest"]
    assert poisoned["head"] == baseline["head"]


def test_argv_tail_digest_binds_relative_script_via_run_cwd(private_tmp):
    repo = os.path.join(private_tmp, "repo")
    run_cwd = os.path.join(private_tmp, "cwd")
    os.makedirs(repo)
    _init_git_repo(repo)
    scripts_dir = os.path.join(run_cwd, "scripts")
    os.makedirs(scripts_dir)
    script = os.path.join(scripts_dir, "cleanup.py")
    _write_executable(script, "#!/usr/bin/env python3\nprint('v1')\n")
    resolved_argv = [sys.executable, "scripts/cleanup.py", "slot-a"]

    def _config_for_binding():
        source_id = pc.source_identity(repo)
        pc._populate_source_binding(source_id, resolved_argv, run_cwd)
        inputs = _config_digest_inputs(
            source_identity=source_id,
            resolved_cleanup_argv=resolved_argv,
            run_cwd=run_cwd,
        )
        return pc.config_digest(**inputs)

    first = _config_for_binding()
    with open(script, "w", encoding="utf-8") as handle:
        handle.write("#!/usr/bin/env python3\nprint('v2')\n")
    second = _config_for_binding()
    assert first != second


def test_argv_tail_digest_binds_symlinked_script(private_tmp):
    repo = os.path.join(private_tmp, "repo")
    run_cwd = os.path.join(private_tmp, "cwd")
    os.makedirs(repo)
    _init_git_repo(repo)
    os.makedirs(run_cwd)
    script = os.path.join(run_cwd, "cleanup.py")
    link = os.path.join(run_cwd, "cleanup-link.py")
    _write_executable(script, "#!/usr/bin/env python3\nprint('v1')\n")
    os.symlink(script, link)
    resolved_argv = [sys.executable, link, "slot-a"]

    def _config_for_binding():
        source_id = pc.source_identity(repo)
        pc._populate_source_binding(source_id, resolved_argv, run_cwd)
        inputs = _config_digest_inputs(
            source_identity=source_id,
            resolved_cleanup_argv=resolved_argv,
            run_cwd=run_cwd,
        )
        return pc.config_digest(**inputs)

    first = _config_for_binding()
    with open(script, "w", encoding="utf-8") as handle:
        handle.write("#!/usr/bin/env python3\nprint('v2')\n")
    second = _config_for_binding()
    assert first != second


def test_worktree_digest_detects_retargeted_dirty_symlink(private_tmp):
    repo = os.path.join(private_tmp, "repo")
    os.makedirs(repo)
    _init_git_repo(repo)
    target_a = os.path.join(repo, "target-a.txt")
    target_b = os.path.join(repo, "target-b.txt")
    link = os.path.join(repo, "link")
    with open(target_a, "w", encoding="utf-8") as handle:
        handle.write("a\n")
    with open(target_b, "w", encoding="utf-8") as handle:
        handle.write("b\n")
    os.symlink(target_a, link)
    first = pc.source_identity(repo)
    os.remove(link)
    os.symlink(target_b, link)
    second = pc.source_identity(repo)
    assert first["worktreeDigest"] != second["worktreeDigest"]


# axis: symlink-to-directory tail refuses
def test_argv_tail_refuses_symlink_to_directory(private_tmp):
    run_cwd = os.path.join(private_tmp, "cwd")
    os.makedirs(run_cwd)
    dir_a = os.path.join(run_cwd, "dirA")
    dir_b = os.path.join(run_cwd, "dirB")
    os.makedirs(dir_a)
    os.makedirs(dir_b)
    link_a = os.path.join(run_cwd, "link-a.py")
    link_b = os.path.join(run_cwd, "link-b.py")
    os.symlink(dir_a, link_a)
    os.symlink(dir_b, link_b)
    source_id = {
        "head": None,
        "worktreeDigest": "a" * 64,
        "argv0Digest": None,
        "argvDigests": [],
    }
    for link in (link_a, link_b):
        resolved_argv = [sys.executable, os.path.basename(link), "slot-a"]
        with pytest.raises(pc.PilotCleanupError) as exc:
            pc._populate_source_binding(source_id, resolved_argv, run_cwd)
        assert exc.value.reason == pc.REFUSAL_SOURCE_ARGV_UNBINDABLE


# axis: dangling symlink tail refuses
def test_argv_tail_refuses_dangling_symlink(private_tmp):
    run_cwd = os.path.join(private_tmp, "cwd")
    os.makedirs(run_cwd)
    link = os.path.join(run_cwd, "missing.py")
    os.symlink(os.path.join(run_cwd, "nowhere.py"), link)
    resolved_argv = [sys.executable, "missing.py", "slot-a"]
    source_id = {
        "head": None,
        "worktreeDigest": "a" * 64,
        "argv0Digest": None,
        "argvDigests": [],
    }
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc._populate_source_binding(source_id, resolved_argv, run_cwd)
    assert exc.value.reason == pc.REFUSAL_SOURCE_ARGV_UNBINDABLE


# axis: symlink-loop tail refuses
def test_argv_tail_refuses_symlink_loop(private_tmp):
    run_cwd = os.path.join(private_tmp, "cwd")
    os.makedirs(run_cwd)
    link_a = os.path.join(run_cwd, "a")
    link_b = os.path.join(run_cwd, "b")
    os.symlink(link_b, link_a)
    os.symlink(link_a, link_b)
    resolved_argv = [sys.executable, "a", "slot-a"]
    source_id = {
        "head": None,
        "worktreeDigest": "a" * 64,
        "argv0Digest": None,
        "argvDigests": [],
    }
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc._populate_source_binding(source_id, resolved_argv, run_cwd)
    assert exc.value.reason == pc.REFUSAL_SOURCE_ARGV_UNBINDABLE


# axis: directory tail element refuses
def test_argv_tail_refuses_directory_element(private_tmp):
    run_cwd = os.path.join(private_tmp, "cwd")
    os.makedirs(run_cwd)
    subdir = os.path.join(run_cwd, "scripts")
    os.makedirs(subdir)
    resolved_argv = [sys.executable, "scripts", "slot-a"]
    source_id = {
        "head": None,
        "worktreeDigest": "a" * 64,
        "argv0Digest": None,
        "argvDigests": [],
    }
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc._populate_source_binding(source_id, resolved_argv, run_cwd)
    assert exc.value.reason == pc.REFUSAL_SOURCE_ARGV_UNBINDABLE


# axis: fifo tail element refuses
def test_argv_tail_refuses_fifo_element(private_tmp):
    run_cwd = os.path.join(private_tmp, "cwd")
    os.makedirs(run_cwd)
    fifo = os.path.join(run_cwd, "pipe")
    try:
        os.mkfifo(fifo)
    except OSError:
        pytest.skip("platform or filesystem refuses mkfifo")
    resolved_argv = [sys.executable, "pipe", "slot-a"]
    source_id = {
        "head": None,
        "worktreeDigest": "a" * 64,
        "argv0Digest": None,
        "argvDigests": [],
    }
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc._populate_source_binding(source_id, resolved_argv, run_cwd)
    assert exc.value.reason == pc.REFUSAL_SOURCE_ARGV_UNBINDABLE


# axis: indeterminate lstat errno refuses
def test_argv_tail_refuses_indeterminate_lstat(private_tmp, monkeypatch):
    run_cwd = os.path.join(private_tmp, "cwd")
    os.makedirs(run_cwd)
    script = os.path.join(run_cwd, "cleanup.py")
    _write_executable(script, "#!/usr/bin/env python3\nprint('v1')\n")
    resolved_argv = [sys.executable, "cleanup.py", "slot-a"]
    source_id = {
        "head": None,
        "worktreeDigest": "a" * 64,
        "argv0Digest": None,
        "argvDigests": [],
    }
    real_lstat = os.lstat

    # Passthrough *args/**kwargs: stands in for global os.lstat; pytest teardown's
    # shutil.rmtree passes dir_fd= on Python 3.12.
    def _lstat(path, *args, **kwargs):
        if path == script:
            raise OSError(errno.EACCES, "denied")
        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", _lstat)
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc._populate_source_binding(source_id, resolved_argv, run_cwd)
    assert exc.value.reason == pc.REFUSAL_SOURCE_ARGV_UNBINDABLE


# axis: unreadable regular file refuses
def test_argv_tail_refuses_unreadable_regular_file(private_tmp, monkeypatch):
    run_cwd = os.path.join(private_tmp, "cwd")
    os.makedirs(run_cwd)
    script = os.path.join(run_cwd, "cleanup.py")
    _write_executable(script, "#!/usr/bin/env python3\nprint('v1')\n")
    resolved_argv = [sys.executable, "cleanup.py", "slot-a"]
    source_id = {
        "head": None,
        "worktreeDigest": "a" * 64,
        "argv0Digest": None,
        "argvDigests": [],
    }
    real_sha256 = pc._sha256_file_chunks

    def _sha256(path, *args, **kwargs):
        if path == script:
            raise OSError(errno.EACCES, "denied")
        return real_sha256(path, *args, **kwargs)

    monkeypatch.setattr(pc, "_sha256_file_chunks", _sha256)
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc._populate_source_binding(source_id, resolved_argv, run_cwd)
    assert exc.value.reason == pc.REFUSAL_SOURCE_ARGV_UNBINDABLE


# axis: unknown classifier state refuses
def test_argv_tail_refuses_unknown_classifier_state(private_tmp, monkeypatch):
    run_cwd = os.path.join(private_tmp, "cwd")
    os.makedirs(run_cwd)
    script = os.path.join(run_cwd, "cleanup.py")
    _write_executable(script, "#!/usr/bin/env python3\nprint('v1')\n")
    resolved_argv = [sys.executable, "cleanup.py", "slot-a"]
    source_id = {
        "head": None,
        "worktreeDigest": "a" * 64,
        "argv0Digest": None,
        "argvDigests": [],
    }
    monkeypatch.setattr(
        pc, "_argv_tail_content_digest", lambda candidate: ("some-future-state", None)
    )
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc._populate_source_binding(source_id, resolved_argv, run_cwd)
    assert exc.value.reason == pc.REFUSAL_SOURCE_ARGV_UNBINDABLE


# axis: non-string tail element refuses
def test_argv_tail_refuses_non_string_element(private_tmp):
    run_cwd = os.path.join(private_tmp, "cwd")
    os.makedirs(run_cwd)
    resolved_argv = [sys.executable, 42, "slot-a"]
    source_id = {
        "head": None,
        "worktreeDigest": "a" * 64,
        "argv0Digest": None,
        "argvDigests": [],
    }
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc._populate_source_binding(source_id, resolved_argv, run_cwd)
    assert exc.value.reason == pc.REFUSAL_SOURCE_ARGV_UNBINDABLE


# --- refusal position: an unbindable element refuses wherever it sits in the tail -------------
#
# Every refusal test above puts the unbindable element at tail index 1, so a fail-open that only
# refuses "while nothing has been digested yet" — `if digests: continue` in front of the raise —
# survives all of them. #868's verifier proved that mutation surviving on a scratch copy. The
# tests below put a genuinely digestible element FIRST, so the refusal has to fire with digests
# already accumulated (#866, closing #868's r2-v0).


def _later_position_run_cwd(private_tmp):
    """A run_cwd whose tail index 1 is a real, digestible script."""
    run_cwd = os.path.join(private_tmp, "cwd")
    os.makedirs(run_cwd)
    _write_executable(
        os.path.join(run_cwd, "cleanup.py"), "#!/usr/bin/env python3\nprint('v1')\n"
    )
    return run_cwd


def _fresh_source_id():
    return {
        "head": None,
        "worktreeDigest": "a" * 64,
        "argv0Digest": None,
        "argvDigests": [],
    }


def _plant_unbindable(run_cwd, shape):
    """Create one unbindable argv-tail element of ``shape`` and return the argv element itself."""
    if shape == "symlink-to-directory":
        os.makedirs(os.path.join(run_cwd, "dirA"))
        os.symlink(os.path.join(run_cwd, "dirA"), os.path.join(run_cwd, "link-a.py"))
        return "link-a.py"
    if shape == "dangling-symlink":
        os.symlink(os.path.join(run_cwd, "nowhere.py"), os.path.join(run_cwd, "missing.py"))
        return "missing.py"
    if shape == "symlink-loop":
        link_a = os.path.join(run_cwd, "a")
        link_b = os.path.join(run_cwd, "b")
        os.symlink(link_b, link_a)
        os.symlink(link_a, link_b)
        return "a"
    if shape == "directory":
        os.makedirs(os.path.join(run_cwd, "scripts"))
        return "scripts"
    if shape == "fifo":
        try:
            os.mkfifo(os.path.join(run_cwd, "pipe"))
        except OSError:
            pytest.skip("platform or filesystem refuses mkfifo")
        return "pipe"
    if shape == "non-string":
        return 42
    raise AssertionError("unknown unbindable shape %r" % shape)


# axis: an unbindable element at a LATER tail position still refuses, with digests already taken
@pytest.mark.parametrize(
    "shape",
    [
        "symlink-to-directory",
        "dangling-symlink",
        "symlink-loop",
        "directory",
        "fifo",
        "non-string",
    ],
)
def test_argv_tail_refuses_unbindable_element_behind_a_digested_one(private_tmp, shape):
    run_cwd = _later_position_run_cwd(private_tmp)
    bad = _plant_unbindable(run_cwd, shape)
    # Non-vacuity: index 1 really is digestible, so the loop has appended a digest by the time it
    # reaches the bad element — the exact state a "refuse only while nothing is bound yet"
    # fail-open would skip over.
    state, digest = pc._argv_tail_content_digest(os.path.join(run_cwd, "cleanup.py"))
    assert state == pc._TAIL_DIGESTED and digest

    resolved_argv = [sys.executable, "cleanup.py", bad, "slot-a"]
    source_id = _fresh_source_id()
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc._populate_source_binding(source_id, resolved_argv, run_cwd)
    assert exc.value.reason == pc.REFUSAL_SOURCE_ARGV_UNBINDABLE


# axis: an unreadable regular file at a later tail position still refuses
def test_argv_tail_refuses_unreadable_regular_file_behind_a_digested_one(private_tmp, monkeypatch):
    run_cwd = _later_position_run_cwd(private_tmp)
    unreadable = os.path.join(run_cwd, "second.py")
    _write_executable(unreadable, "#!/usr/bin/env python3\nprint('v2')\n")
    real_sha256 = pc._sha256_file_chunks

    def _sha256(path, *args, **kwargs):
        if path == unreadable:
            raise OSError(errno.EACCES, "denied")
        return real_sha256(path, *args, **kwargs)

    monkeypatch.setattr(pc, "_sha256_file_chunks", _sha256)
    # Non-vacuity: the stub leaves index 1 digestible, so a digest is taken before the refusal.
    state, digest = pc._argv_tail_content_digest(os.path.join(run_cwd, "cleanup.py"))
    assert state == pc._TAIL_DIGESTED and digest

    resolved_argv = [sys.executable, "cleanup.py", "second.py", "slot-a"]
    source_id = _fresh_source_id()
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc._populate_source_binding(source_id, resolved_argv, run_cwd)
    assert exc.value.reason == pc.REFUSAL_SOURCE_ARGV_UNBINDABLE


# axis: the public seam refuses too when the unbindable element sits behind a digested one
def test_cleanup_effect_receipt_refuses_unbindable_argv_tail_at_a_later_position(private_tmp):
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, journal_path = _harness_layout(
        private_tmp
    )
    plant, probe = _write_scripts(bin_dir)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    policy = _three_slot_policy(store_dir, plant, probe)
    pilot_block = _pilot_block(cleanup_script)
    # A real digestible file at tail index 1, the unbindable namespace directory at index 2.
    _write_executable(
        os.path.join(run_cwd, "bound.py"), "#!/usr/bin/env python3\nprint('v1')\n"
    )
    # Non-vacuity: bound.py really is digestible, so the loop has appended a digest by the time it
    # reaches the unbindable namespace directory — the exact state a "refuse only while nothing is
    # bound yet" fail-open would skip over. Without this, the test would stay green even if
    # bound.py were never digested (an empty `digests` list, with the fail-open untriggered).
    state, digest = pc._argv_tail_content_digest(os.path.join(run_cwd, "bound.py"))
    assert state == pc._TAIL_DIGESTED and digest
    pilot_block["cleanup"]["command"] = [
        cleanup_script, "bound.py", pc.NAMESPACE_PLACEHOLDER,
    ]
    os.makedirs(os.path.join(run_cwd, "slot-a"))
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc.cleanup_effect_receipt(
            policy=policy,
            pilot_block=pilot_block,
            slot_ref=_SLOT_REF,
            reach_roots=[reach_root],
            run_cwd=run_cwd,
            cleanup_root=cleanup_repo,
            journal_path=journal_path,
            now=_NOW,
            observed_identity="example_dev",
            identity_provenance="observed",
            identity_strength="strong",
        )
    assert exc.value.reason == pc.REFUSAL_SOURCE_ARGV_UNBINDABLE
    # The refusal precedes any effect: nothing was planted in the store.
    assert not os.listdir(store_dir)


# axis: absent namespace token skipped not refused
def test_argv_tail_skips_absent_namespace_argument(private_tmp):
    run_cwd = os.path.join(private_tmp, "cwd")
    os.makedirs(run_cwd)
    script = os.path.join(run_cwd, "cleanup.py")
    _write_executable(script, "#!/usr/bin/env python3\nprint('v1')\n")
    resolved_argv = [sys.executable, "slot-a", "cleanup.py"]
    source_id = {
        "head": None,
        "worktreeDigest": "a" * 64,
        "argv0Digest": None,
        "argvDigests": [],
    }
    pc._populate_source_binding(source_id, resolved_argv, run_cwd)
    expected_digest = pc._sha256_file_chunks(script)
    assert source_id["argvDigests"] == [[2, expected_digest]]


# axis: ENAMETOOLONG tail skipped not refused
def test_argv_tail_skips_overlong_argument(private_tmp):
    run_cwd = os.path.join(private_tmp, "cwd")
    os.makedirs(run_cwd)
    script = os.path.join(run_cwd, "cleanup.py")
    _write_executable(script, "#!/usr/bin/env python3\nprint('v1')\n")
    overlong = "x" * 5000
    resolved_argv = [sys.executable, overlong, "cleanup.py", "slot-a"]
    source_id = {
        "head": None,
        "worktreeDigest": "a" * 64,
        "argv0Digest": None,
        "argvDigests": [],
    }
    try:
        os.lstat(os.path.join(run_cwd, overlong))
    except OSError as lstat_exc:
        if lstat_exc.errno != errno.ENAMETOOLONG:
            pytest.skip(f"overlong name raised errno {lstat_exc.errno}, not ENAMETOOLONG")
    else:
        pytest.skip("overlong name did not raise")
    pc._populate_source_binding(source_id, resolved_argv, run_cwd)
    expected_digest = pc._sha256_file_chunks(script)
    assert source_id["argvDigests"] == [[2, expected_digest]]


# axis: nul-bearing tail skipped not refused
def test_argv_tail_skips_nul_bearing_argument(private_tmp):
    run_cwd = os.path.join(private_tmp, "cwd")
    os.makedirs(run_cwd)
    script = os.path.join(run_cwd, "cleanup.py")
    _write_executable(script, "#!/usr/bin/env python3\nprint('v1')\n")
    resolved_argv = [sys.executable, "slot\x00a", "cleanup.py", "slot-a"]
    source_id = {
        "head": None,
        "worktreeDigest": "a" * 64,
        "argv0Digest": None,
        "argvDigests": [],
    }
    pc._populate_source_binding(source_id, resolved_argv, run_cwd)
    expected_digest = pc._sha256_file_chunks(script)
    assert source_id["argvDigests"] == [[2, expected_digest]]


# axis: dash-prefixed script path bound
def test_argv_tail_binds_dash_prefixed_script(private_tmp):
    repo = os.path.join(private_tmp, "repo")
    run_cwd = os.path.join(private_tmp, "cwd")
    os.makedirs(repo)
    _init_git_repo(repo)
    os.makedirs(run_cwd)
    script = os.path.join(run_cwd, "-cleanup.py")
    _write_executable(script, "#!/usr/bin/env python3\nprint('v1')\n")
    resolved_argv = [sys.executable, "-cleanup.py", "slot-a"]

    def _config_for_binding():
        source_id = pc.source_identity(repo)
        pc._populate_source_binding(source_id, resolved_argv, run_cwd)
        inputs = _config_digest_inputs(
            source_identity=source_id,
            resolved_cleanup_argv=resolved_argv,
            run_cwd=run_cwd,
        )
        return pc.config_digest(**inputs)

    first = _config_for_binding()
    with open(script, "w", encoding="utf-8") as handle:
        handle.write("#!/usr/bin/env python3\nprint('v2')\n")
    second = _config_for_binding()
    assert first != second


# axis: argvDigests never carries null digests
def test_argv_tail_digests_carry_no_null_entries(private_tmp):
    run_cwd = os.path.join(private_tmp, "cwd")
    os.makedirs(run_cwd)
    script = os.path.join(run_cwd, "cleanup.py")
    link = os.path.join(run_cwd, "cleanup-link.py")
    _write_executable(script, "#!/usr/bin/env python3\nprint('v1')\n")
    os.symlink(script, link)
    resolved_argv = [sys.executable, "cleanup.py", "slot-a", "cleanup-link.py"]
    source_id = {
        "head": None,
        "worktreeDigest": "a" * 64,
        "argv0Digest": None,
        "argvDigests": [],
    }
    pc._populate_source_binding(source_id, resolved_argv, run_cwd)
    assert len(source_id["argvDigests"]) == 2
    assert [entry[0] for entry in source_id["argvDigests"]] == [1, 3]
    for index, digest in source_id["argvDigests"]:
        assert isinstance(index, int)
        assert isinstance(digest, str)
        assert len(digest) == 64


def test_source_identity_hashes_non_utf8_filename(private_tmp):
    repo = os.path.join(private_tmp, "repo")
    os.makedirs(repo)
    _init_git_repo(repo)
    bad_name = os.fsdecode(b"bad\xffname")
    bad_path = os.path.join(repo, bad_name)
    try:
        with open(bad_path, "wb") as handle:
            handle.write(b"v1\n")
    except OSError as exc:
        pytest.skip("filesystem rejects non-UTF-8 filename: %s" % exc)
    first = pc.source_identity(repo)
    with open(bad_path, "wb") as handle:
        handle.write(b"v2\n")
    second = pc.source_identity(repo)
    assert first["worktreeDigest"] != second["worktreeDigest"]


# --- FIX-2: resurrection_plan resolves containment internally ------------------

def test_resurrection_plan_refuses_when_containment_unresolved_from_inputs(private_tmp):
    policy, _, _, cleanup_repo = _resurrection_policy(private_tmp)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    block = _pilot_block(cleanup_script)
    registry = _registry_with(_effects_escape_record(block))
    result = pc.resurrection_plan(
        policy,
        block,
        _SLOT_REF,
        registry=registry,
        journal_path=os.path.join(private_tmp, "j.jsonl"),
        verdict=_passing_verdict(policy),
    )
    assert result["action"] == pc.ACTION_REFUSE
    assert result["reason"] == pc.REASON_CONTAINMENT_UNRESOLVED


def test_resurrection_plan_cannot_be_handed_a_forged_containment_mode():
    params = inspect.signature(pc.resurrection_plan).parameters
    assert "containment" not in params


def test_resurrection_plan_permissions_path(private_tmp):
    policy, reach_root, run_cwd, cleanup_repo = _resurrection_policy(private_tmp)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    block = _pilot_block(cleanup_script)
    policy["datastore"]["containment"]["permissions"] = {
        "cannotReachForeignNamespaces": True,
        "evidence": "isolated datastore",
    }
    registry = _registry_with(_effects_escape_record(block))
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
        journal_path=os.path.join(private_tmp, "j.jsonl"),
        verdict=_passing_verdict(policy),
        account="owner",
        artifact=artifact,
    )
    assert plan["action"] == pc.ACTION_RESURRECT
    assert plan["containment"]["mode"] == pc.MODE_PERMISSIONS


# --- FIX-3: sentinel argv-tail confinement -----------------------------------

def test_validate_sentinel_declaration_refuses_plant_argv1_inside_reach_root(private_tmp):
    reach_root, run_cwd, bin_dir = _confinement_layout(private_tmp)
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    evil = os.path.join(reach_root, "evil.py")
    with open(evil, "w", encoding="utf-8") as handle:
        handle.write("print('evil')\n")
    _write_executable(plant, "#!/bin/sh\nexit 0\n")
    _write_executable(probe, "#!/bin/sh\nexit 0\n")
    sentinel = {
        "plantCommand": [plant, evil, pc.NAMESPACE_PLACEHOLDER, pc.SENTINEL_PLACEHOLDER],
        "probeCommand": [probe, "--ns", pc.NAMESPACE_PLACEHOLDER, "--id", pc.SENTINEL_PLACEHOLDER],
        "connectionEnvVar": "PILOT_DATASTORE_URL",
    }
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc._validate_sentinel_declaration(sentinel, reach_roots=[reach_root], run_cwd=run_cwd)
    assert exc.value.reason == pc.REFUSAL_SENTINEL_CONFINEMENT


def test_validate_sentinel_declaration_refuses_probe_argv1_inside_reach_root(private_tmp):
    reach_root, run_cwd, bin_dir = _confinement_layout(private_tmp)
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    evil = os.path.join(reach_root, "evil.py")
    with open(evil, "w", encoding="utf-8") as handle:
        handle.write("print('evil')\n")
    _write_executable(plant, "#!/bin/sh\nexit 0\n")
    _write_executable(probe, "#!/bin/sh\nexit 0\n")
    sentinel = {
        "plantCommand": [plant, "--ns", pc.NAMESPACE_PLACEHOLDER, "--id", pc.SENTINEL_PLACEHOLDER],
        "probeCommand": [probe, evil, pc.NAMESPACE_PLACEHOLDER, pc.SENTINEL_PLACEHOLDER],
        "connectionEnvVar": "PILOT_DATASTORE_URL",
    }
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc._validate_sentinel_declaration(sentinel, reach_roots=[reach_root], run_cwd=run_cwd)
    assert exc.value.reason == pc.REFUSAL_SENTINEL_CONFINEMENT


def test_validate_sentinel_declaration_refuses_relative_argv1_inside_reach_root(private_tmp):
    reach_root, run_cwd, bin_dir = _confinement_layout(private_tmp)
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    evil = os.path.join(reach_root, "evil.py")
    with open(evil, "w", encoding="utf-8") as handle:
        handle.write("print('evil')\n")
    _write_executable(plant, "#!/bin/sh\nexit 0\n")
    _write_executable(probe, "#!/bin/sh\nexit 0\n")
    relative_evil = os.path.relpath(evil, run_cwd)
    sentinel = {
        "plantCommand": [plant, relative_evil, pc.NAMESPACE_PLACEHOLDER, pc.SENTINEL_PLACEHOLDER],
        "probeCommand": [probe, "--ns", pc.NAMESPACE_PLACEHOLDER, "--id", pc.SENTINEL_PLACEHOLDER],
        "connectionEnvVar": "PILOT_DATASTORE_URL",
    }
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc._validate_sentinel_declaration(sentinel, reach_roots=[reach_root], run_cwd=run_cwd)
    assert exc.value.reason == pc.REFUSAL_SENTINEL_CONFINEMENT


def test_validate_sentinel_declaration_allows_flag_argv_tail(private_tmp):
    reach_root, run_cwd, bin_dir = _confinement_layout(private_tmp)
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    _write_executable(plant, "#!/bin/sh\nexit 0\n")
    _write_executable(probe, "#!/bin/sh\nexit 0\n")
    sentinel = _sentinel_declaration(plant, probe)
    pc._validate_sentinel_declaration(sentinel, reach_roots=[reach_root], run_cwd=run_cwd)


def test_validate_sentinel_declaration_refuses_nonexistent_argv1_inside_reach_root(private_tmp):
    reach_root, run_cwd, bin_dir = _confinement_layout(private_tmp)
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    _write_executable(plant, "#!/bin/sh\nexit 0\n")
    _write_executable(probe, "#!/bin/sh\nexit 0\n")
    missing_inside = os.path.join(reach_root, "missing.py")
    sentinel = {
        "plantCommand": [plant, missing_inside, pc.NAMESPACE_PLACEHOLDER, pc.SENTINEL_PLACEHOLDER],
        "probeCommand": [probe, "--ns", pc.NAMESPACE_PLACEHOLDER, "--id", pc.SENTINEL_PLACEHOLDER],
        "connectionEnvVar": "PILOT_DATASTORE_URL",
    }
    with pytest.raises(pc.PilotCleanupError) as exc:
        pc._validate_sentinel_declaration(sentinel, reach_roots=[reach_root], run_cwd=run_cwd)
    assert exc.value.reason == pc.REFUSAL_SENTINEL_CONFINEMENT


# --- FIX-4: run_bounded drain and process-group termination --------------------

def test_run_bounded_drains_past_stdout_cap(private_tmp):
    _, run_cwd, bin_dir = _confinement_layout(private_tmp)
    script = os.path.join(bin_dir, "huge.sh")
    _write_executable(
        script,
        "#!/bin/sh\n"
        "i=0\n"
        "while [ $i -lt 307200 ]; do printf x; i=$((i+1)); done\n",
    )
    result = pc.run_bounded(
        [script],
        cwd=run_cwd,
        env={},
        max_output_bytes=4096,
        timeout_seconds=30,
    )
    assert result["exit"] == 0
    assert result["timedOut"] is False
    assert result["stdoutTruncated"] is True
    assert result["stdoutBytes"] == 4096


def test_run_bounded_kills_grandchild_on_timeout(private_tmp):
    _, run_cwd, bin_dir = _confinement_layout(private_tmp)
    pid_file = os.path.join(private_tmp, "grandchild.pid")
    script = os.path.join(bin_dir, "spawn.sh")
    _write_executable(
        script,
        "#!/bin/sh\n"
        "/bin/sleep 60 &\n"
        "echo $! > '%s'\n"
        "/bin/sleep 5\n" % pid_file,
    )
    result = pc.run_bounded(
        [script],
        cwd=run_cwd,
        env={},
        timeout_seconds=1,
    )
    assert result["timedOut"] is True
    with open(pid_file, encoding="utf-8") as handle:
        pid = int(handle.read().strip())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def _read_grandchild_pid(pid_file):
    if not os.path.isfile(pid_file):
        pytest.fail(f"grandchild pid file missing: {pid_file!r}")
    with open(pid_file, encoding="utf-8") as handle:
        raw = handle.read().strip()
    if not raw:
        pytest.fail(f"grandchild pid file empty: {pid_file!r}")
    try:
        return int(raw)
    except ValueError:
        pytest.fail(
            f"grandchild pid file not an integer: {pid_file!r} contents {raw!r}"
        )


def _observed_process_state(pid):
    """Return a description of ``pid`` if still present, else ``None`` when gone."""
    proc_stat = os.path.join("/proc", str(pid), "stat")
    if os.path.isfile(proc_stat):
        try:
            with open(proc_stat, encoding="utf-8") as handle:
                content = handle.read()
        except OSError as exc:
            return f"/proc/{pid}/stat unreadable: {exc}"
        close_paren = content.rfind(")")
        if close_paren < 0 or close_paren + 2 >= len(content):
            return f"/proc/{pid}/stat unparseable: {content!r}"
        state = content[close_paren + 2]
        if state == "Z":
            return None
        state_names = {
            "R": "running",
            "S": "sleeping",
            "D": "disk sleep",
            "T": "stopped",
            "t": "tracing stop",
            "X": "dead",
            "x": "dead",
            "Z": "zombie",
            "P": "parked",
            "I": "idle",
        }
        label = state_names.get(state, "unknown")
        return f"/proc state {state!r} ({label})"
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    except PermissionError:
        return "alive (kill(pid, 0) raised PermissionError; /proc unavailable)"
    return "alive (kill(pid, 0) succeeded; /proc unavailable)"


def _wait_for_process_gone(pid, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _observed_process_state(pid) is None:
            return True
        time.sleep(0.05)
    return False


def test_run_bounded_kills_orphan_grandchild_when_leader_exits_first(private_tmp):
    _, run_cwd, bin_dir = _confinement_layout(private_tmp)
    pid_file = os.path.join(private_tmp, "grandchild.pid")
    script = os.path.join(bin_dir, "spawn.sh")
    _write_executable(
        script,
        "#!/bin/sh\n"
        "/bin/sleep 60 >&1 &\n"
        "echo $! > '%s'\n"
        "exit 0\n" % pid_file,
    )
    started = time.monotonic()
    result = pc.run_bounded(
        [script],
        cwd=run_cwd,
        env={},
        timeout_seconds=1,
    )
    elapsed = time.monotonic() - started
    assert result["timedOut"] is True
    assert elapsed < 5
    pid = _read_grandchild_pid(pid_file)
    # Leader exits before timeout cleanup; reaping is async and zombies count as gone.
    if not _wait_for_process_gone(pid, timeout=10):
        state = _observed_process_state(pid)
        detail = f"observed state: {state}"
        try:
            detail += f"; pgid={os.getpgid(pid)}"
        except (ProcessLookupError, PermissionError):
            pass
        pytest.fail(f"grandchild pid {pid} still present after 10s poll; {detail}")


def test_run_bounded_kills_sigterm_ignoring_orphan_grandchild_when_leader_exits_first(
    private_tmp,
):
    _, run_cwd, bin_dir = _confinement_layout(private_tmp)
    pid_file = os.path.join(private_tmp, "grandchild.pid")
    script = os.path.join(bin_dir, "spawn.sh")
    _write_executable(
        script,
        "#!/bin/sh\n"
        "trap '' TERM\n"
        "("
        "trap '' TERM; "
        "/bin/sleep 60 >&1 & "
        "echo $! > '%s'"
        ") &\n"
        "exit 0\n" % pid_file,
    )
    started = time.monotonic()
    result = pc.run_bounded(
        [script],
        cwd=run_cwd,
        env={},
        timeout_seconds=1,
    )
    elapsed = time.monotonic() - started
    assert result["timedOut"] is True
    assert elapsed < 5
    with open(pid_file, encoding="utf-8") as handle:
        pid = int(handle.read().strip())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


# --- WO8 FIX-1: partial plant failure ------------------------------------------

def test_cleanup_effect_receipt_partial_plant_failure(private_tmp):
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, journal_path = _harness_layout(
        private_tmp
    )
    planned_ids = {
        "slot-a": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "slot-ab": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "slot-b": "cccccccccccccccccccccccccccccccc",
    }
    id_queue = list(planned_ids.values())

    def factory():
        return id_queue.pop(0)

    selective_plant = (
        "#!/bin/sh\n"
        'ns="$2"\n'
        'id="$4"\n'
        'store="$PILOT_DATASTORE_URL"\n'
        'if [ "$ns" = "slot-ab" ]; then exit 2; fi\n'
        'mkdir -p "$store/$ns"\n'
        'touch "$store/$ns/$id"\n'
        "exit 0\n"
    )
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    _write_executable(plant, selective_plant)
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
        sentinel_factory=factory,
    )
    assert receipt["result"] == pc.RESULT_FAIL
    assert receipt["reason"] == pc.REFUSAL_PLANT_FAILED
    assert receipt["residualSentinels"] == [
        {
            "namespace": "slot-a",
            "sentinelId": planned_ids["slot-a"],
            "state": "planted",
        },
        {
            "namespace": "slot-ab",
            "sentinelId": planned_ids["slot-ab"],
            "state": "possibly-planted",
        },
    ]
    planted_path = os.path.join(
        store_dir,
        "slot-a",
        planned_ids["slot-a"],
    )
    assert os.path.isfile(planted_path)


def test_cleanup_effect_receipt_plant_write_then_fail_records_possibly_planted(private_tmp):
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, journal_path = _harness_layout(
        private_tmp
    )
    planned_id = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

    def factory():
        return planned_id

    write_then_fail_plant = (
        "#!/bin/sh\n"
        'ns="$2"\n'
        'id="$4"\n'
        'store="$PILOT_DATASTORE_URL"\n'
        'mkdir -p "$store/$ns"\n'
        'touch "$store/$ns/$id"\n'
        "exit 3\n"
    )
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    _write_executable(plant, write_then_fail_plant)
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
        sentinel_factory=factory,
    )
    assert receipt["result"] == pc.RESULT_FAIL
    assert receipt["reason"] == pc.REFUSAL_PLANT_FAILED
    assert receipt["residualSentinels"] == [
        {
            "namespace": "slot-a",
            "sentinelId": planned_id,
            "state": "possibly-planted",
        },
    ]
    planted_path = os.path.join(store_dir, "slot-a", planned_id)
    assert os.path.isfile(planted_path)


# --- WO8 FIX-4: journal read-back ---------------------------------------------

def _journal_namespace_effects(replay_result):
    return [
        effect
        for effect in replay_result["effects"]
        if effect.get("kind") == pilot_journal.KIND_NAMESPACE_TOUCHED
    ]


def test_cleanup_effect_receipt_journals_plant_and_cleanup_happy_path(private_tmp):
    receipt, ctx = _run_receipt(private_tmp, _cleanup_correct_script())
    assert receipt["result"] == pc.RESULT_PASS
    replay_result = pilot_journal.replay(ctx["journal_path"], slot_ref=_SLOT_REF)
    assert replay_result["ok"] is True
    effects = _journal_namespace_effects(replay_result)
    assert len(effects) == 2
    for effect in effects:
        assert effect["beganAt"] is not None
        assert effect["endedAt"] is not None
        assert effect["outcome"] == pilot_journal.OUTCOME_APPLIED
        assert effect["state"] == pilot_journal.STATE_APPLIED
    cleanup_effect = next(
        e for e in effects
        if isinstance(e.get("detail"), dict) and "atRiskNamespaces" in e["detail"]
    )
    assert cleanup_effect["detail"]["namespace"] == "slot-a"
    assert cleanup_effect["detail"]["atRiskNamespaces"] == ["slot-a", "slot-ab", "slot-b"]


def test_cleanup_effect_receipt_journals_cleanup_applied_when_command_fails(private_tmp):
    receipt, ctx = _run_receipt(private_tmp, _cleanup_fail_script())
    assert receipt["reason"] == pc.REASON_CLEANUP_COMMAND_FAILED
    replay_result = pilot_journal.replay(ctx["journal_path"], slot_ref=_SLOT_REF)
    assert replay_result["ok"] is True
    effects = _journal_namespace_effects(replay_result)
    cleanup_effect = next(
        e for e in effects
        if isinstance(e.get("detail"), dict) and "atRiskNamespaces" in e["detail"]
    )
    assert cleanup_effect["outcome"] == pilot_journal.OUTCOME_APPLIED
    assert cleanup_effect["state"] == pilot_journal.STATE_APPLIED


def test_cleanup_effect_receipt_journals_plant_indeterminate_on_failure(private_tmp):
    reach_root, run_cwd, bin_dir, store_dir, cleanup_repo, journal_path = _harness_layout(
        private_tmp
    )
    plant = os.path.join(bin_dir, "plant.sh")
    probe = os.path.join(bin_dir, "probe.sh")
    _write_executable(plant, "#!/bin/sh\nexit 2\n")
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
    assert receipt["reason"] == pc.REFUSAL_PLANT_FAILED
    replay_result = pilot_journal.replay(journal_path, slot_ref=_SLOT_REF)
    assert replay_result["ok"] is True
    plant_effect = next(
        e for e in _journal_namespace_effects(replay_result)
        if isinstance(e.get("detail"), dict) and "namespaces" in e["detail"]
    )
    assert plant_effect["outcome"] == pilot_journal.OUTCOME_INDETERMINATE
    assert plant_effect["state"] == pilot_journal.STATE_POSSIBLY_APPLIED


# --- WO8 FIX-5: guard through resurrection_plan --------------------------------

def test_resurrection_plan_refuses_connection_detail_in_cleanup_argv(private_tmp):
    policy, reach_root, run_cwd, cleanup_repo = _resurrection_policy(private_tmp)
    policy["datastore"]["containment"]["permissions"] = {
        "cannotReachForeignNamespaces": True,
        "evidence": "isolated datastore",
    }
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    block = _pilot_block(cleanup_script)
    connection_detail = policy["datastore"]["connectionDetail"]
    block["cleanup"]["command"] = [cleanup_script, connection_detail, pc.NAMESPACE_PLACEHOLDER]
    registry = _registry_with(_effects_escape_record(block))
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
    with pytest.raises(pilot_policy.PilotPolicyError) as exc:
        pc.resurrection_plan(
            policy,
            block,
            _SLOT_REF,
            registry=registry,
            journal_path=os.path.join(private_tmp, "j.jsonl"),
            verdict=_passing_verdict(policy),
            account="owner",
            artifact=artifact,
        )
    assert exc.value.reason == pilot_policy.REFUSAL_MATERIAL_IN_RESULT


# --- WO8 FIX-6: assert_results_only on no-foreign path -------------------------

def test_cleanup_effect_receipt_no_foreign_guard_refuses_material(private_tmp):
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
    material = pilot_policy.policy_material(policy)
    contaminated = dict(receipt)
    contaminated["evidence"] = policy["datastore"]["connectionDetail"]
    with pytest.raises(pilot_policy.PilotPolicyError):
        pilot_policy.assert_results_only(contaminated, material)


# --- WO8 FIX-8: digest field typing --------------------------------------------

@pytest.mark.parametrize(
    "bad_digest",
    [
        pytest.param(None, id="none"),
        pytest.param(42, id="int"),
        pytest.param(["digest"], id="list"),
        pytest.param("", id="empty"),
        pytest.param("é" * 64, id="non_ascii"),
        pytest.param("\u0660" * 64, id="arabic_indic_digits"),
        pytest.param("a" * 63, id="short_hex"),
        pytest.param("A" * 64, id="uppercase_hex"),
        pytest.param("g" * 64, id="non_hex"),
    ],
)
def test_receipt_valid_for_refuses_malformed_command_digest(private_tmp, bad_digest):
    receipt, ctx = _run_receipt(private_tmp, _cleanup_correct_script())
    receipt["commandDigest"] = bad_digest
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


# --- WO8 FIX-9: slot-bound containment registry --------------------------------

def test_cleanup_containment_record_does_not_satisfy_other_slot(private_tmp):
    receipt_a, ctx = _run_receipt(private_tmp, _cleanup_correct_script())
    record = pc.registry_record(receipt_a, ctx["pilot_block"]["cleanup"])
    registry = _registry_with(_effects_escape_record(ctx["pilot_block"]), record)
    reach_root = ctx["reach_root"]
    run_cwd = ctx["run_cwd"]
    cleanup_repo = ctx["cleanup_repo"]
    policy = ctx["policy"]
    policy["slots"]["slot-b"]["mintableAccounts"] = ["owner"]
    block = ctx["pilot_block"]
    receipt_b = pc.cleanup_effect_receipt(
        policy,
        block,
        "slot-b@1",
        reach_roots=[reach_root],
        run_cwd=run_cwd,
        cleanup_root=cleanup_repo,
        journal_path=os.path.join(private_tmp, "journal-b.jsonl"),
        now=_NOW,
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="strong",
    )
    assert receipt_b["result"] == pc.RESULT_PASS
    artifact_path = os.path.join(private_tmp, "seed-b.bin")
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
    result = pc.resurrection_plan(
        policy,
        block,
        "slot-b@1",
        registry=registry,
        journal_path=os.path.join(private_tmp, "j.jsonl"),
        verdict=_passing_verdict(policy, "slot-b@1"),
        account="owner",
        artifact=artifact,
        receipt=receipt_b,
        cleanup_root=cleanup_repo,
        run_cwd=run_cwd,
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="strong",
    )
    assert result["action"] == pc.ACTION_REFUSE
    assert result["reason"] == pc.REASON_CONTAINMENT_UNEXERCISED


def test_cleanup_containment_record_satisfies_same_slot(private_tmp):
    policy, reach_root, run_cwd, cleanup_repo = _resurrection_policy(private_tmp)
    cleanup_script = _write_cleanup_script(cleanup_repo, "cleanup.sh", _cleanup_correct_script())
    block = _pilot_block(cleanup_script)
    receipt = _take_receipt(private_tmp, policy, block, reach_root, run_cwd, cleanup_repo)
    record = pc.registry_record(receipt, block["cleanup"])
    registry = _registry_with(_effects_escape_record(block), record)
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
        journal_path=os.path.join(private_tmp, "j.jsonl"),
        verdict=_passing_verdict(policy),
        account="owner",
        artifact=artifact,
        receipt=receipt,
        cleanup_root=cleanup_repo,
        run_cwd=run_cwd,
        observed_identity="example_dev",
        identity_provenance="observed",
        identity_strength="strong",
    )
    assert plan["action"] == pc.ACTION_RESURRECT
