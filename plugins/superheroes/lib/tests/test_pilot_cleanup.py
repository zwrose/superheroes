"""Tests for pilot_cleanup.py — cleanup primitives and receipt binding."""
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
