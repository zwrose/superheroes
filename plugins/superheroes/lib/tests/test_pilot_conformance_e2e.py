"""End-to-end conformance run — whole-run green receipt across all eight exercises (C10)."""
import datetime
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_conformance # noqa: E402
import pilot_conformance_runtime as pcr # noqa: E402
import pilot_policy # noqa: E402
from test_pilot_conformance_cleanup import ( # noqa: E402
    _build_cleanup_inputs,
    _cleanup_correct_script,
    _SLOT_REF,
)

_PINNED_NOW = "2026-08-05T16:00:00Z"
_QUARANTINE_AT = pcr._QUARANTINE_AT
_GRACE_HOURS = 72

_EXPECTED_EXERCISE_NAMES = frozenset({
    "artifact-store",
    "boundary-refusals",
    "cleanup-end-to-end",
    "horizon-validity",
    "mint-gate-off",
    "ownership-probe",
    "reclaim-sweep",
    "wave-headless",
})

_INPUT_KEY_TO_EXERCISE = {
    "artifacts": "artifact-store",
    "boundary": "boundary-refusals",
    "cleanup": "cleanup-end-to-end",
    "horizon": "horizon-validity",
    "mint": "mint-gate-off",
    "ownership_probe": "ownership-probe",
    "reclaim": "reclaim-sweep",
    "wave": "wave-headless",
}


def _artifacts_dir(tmp_root):
    path = os.path.join(tmp_root, "artifacts")
    os.makedirs(path, mode=0o700)
    os.chmod(path, 0o700)
    return path


def _slots_dir(tmp_root):
    slots = os.path.join(tmp_root, "slots")
    slot_a = os.path.join(slots, "slot-a")
    os.makedirs(slot_a)
    return slots


def _flatten_policy_material(policy):
    material = pilot_policy.policy_material(policy)
    items = []
    for values in material.values():
        if isinstance(values, list):
            for value in values:
                if isinstance(value, str) and value:
                    items.append(value)
    return sorted(set(items))


def _assert_cleanup_policy_shape(policy):
    """Fixture guard: multi-slot policy without permissions-based containment."""
    slots = policy.get("slots", {})
    assert len(slots) > 1
    permissions = (
        policy.get("datastore", {})
        .get("containment", {})
        .get("permissions", {})
    )
    assert permissions.get("cannotReachForeignNamespaces") is not True


def _assert_now_past_quarantine_grace(now):
    quarantine_dt = datetime.datetime.strptime(_QUARANTINE_AT, "%Y-%m-%dT%H:%M:%SZ")
    now_dt = datetime.datetime.strptime(now, "%Y-%m-%dT%H:%M:%SZ")
    grace_end = quarantine_dt + datetime.timedelta(hours=_GRACE_HOURS)
    assert now_dt >= grace_end


def _assert_gate_off_command_executable(envelope):
    import shutil

    command = envelope.get("gateOffTestCommand")
    assert isinstance(command, list) and command
    first = command[0]
    if isinstance(first, str) and (os.path.sep in first or first.startswith(".")):
        assert os.path.isfile(first) and os.access(first, os.X_OK)
    else:
        assert shutil.which(first) is not None


def _assert_path_under_tmp(path, tmp_root):
    real_path = os.path.realpath(path)
    real_tmp = os.path.realpath(tmp_root)
    common = os.path.commonpath([real_path, real_tmp])
    assert common == real_tmp


def _build_conformance_inputs(tmp_root, now):
    cleanup = _build_cleanup_inputs(tmp_root, _cleanup_correct_script())
    policy = cleanup["policy"]
    pilot_block = cleanup["pilot_block"]
    mint_envelope = cleanup["mint_envelope"]

    _assert_cleanup_policy_shape(policy)
    _assert_now_past_quarantine_grace(now)
    _assert_gate_off_command_executable(mint_envelope)

    slots_dir = _slots_dir(tmp_root)
    journal_path = os.path.join(slots_dir, "slot-a", "journal.ndjson")
    cleanup["journal_path"] = journal_path

    artifacts_dir = _artifacts_dir(tmp_root)
    _assert_path_under_tmp(artifacts_dir, tmp_root)

    material = _flatten_policy_material(policy)
    assert material

    env_var = mint_envelope["enablingFlagEnvVar"]
    run_cwd = cleanup["run_cwd"]

    policy = dict(policy)
    protected = list(policy.get("protectedTargets") or [])
    if not any(isinstance(target, str) and "://" in target for target in protected):
        protected.append("https://app.example.com:443")
    policy["protectedTargets"] = protected
    cleanup["policy"] = policy

    probe_script = (
        "import json, sys; _acct='%s'; sys.stdout.write(json.dumps(dict(ownsNothing=True)))"
        % pilot_policy.ACCOUNT_PLACEHOLDER
    )
    policy["ownershipProbe"] = {
        "command": [sys.executable, "-c", probe_script],
        "connectionEnvVar": "PILOT_DATASTORE_URL",
    }

    inputs = {
        "artifacts": {
            "artifacts_dir": artifacts_dir,
            "branch": "feat/conformance",
            "slot": "slot-a",
            "material": material,
        },
        "boundary": {
            "policy": policy,
            "slot_ref": _SLOT_REF,
        },
        "cleanup": cleanup,
        "horizon": {
            "pilot_block": pilot_block,
        },
        "mint": {
            "envelope": mint_envelope,
            "run_cwd": run_cwd,
            "environment": {env_var: "1"},
        },
        "ownership_probe": {
            "policy": policy,
            "pilot_block": pilot_block,
            "run_cwd": run_cwd,
            "connection_detail": policy["datastore"]["connectionDetail"],
        },
        "reclaim": {"slots_dir": slots_dir},
        "wave": {
            "slots_dir": slots_dir,
            "slot_ref": _SLOT_REF,
        },
    }
    return inputs


def build_green_report(tmp_root):
    """Assemble the full fixture beneath tmp_root and return the conformance report dict."""
    now = _PINNED_NOW
    inputs = _build_conformance_inputs(tmp_root, now)
    return pilot_conformance.run(
        pilot_conformance.default_exercises(),
        inputs=inputs,
        now=now,
    )


@pytest.fixture
def conformance_inputs(tmp_path):
    return _build_conformance_inputs(str(tmp_path), _PINNED_NOW)


@pytest.fixture
def now():
    return _PINNED_NOW


def test_conformance_run_is_green_across_every_required_surface(
    conformance_inputs, now,
):
    report = pilot_conformance.run(
        pilot_conformance.default_exercises(),
        inputs=conformance_inputs,
        now=now,
    )
    assert report["ok"] is True
    assert report["unexercised"] == []
    assert set(report["surfaces"]) == set(pilot_conformance.REQUIRED_SURFACES)
    for record in report["exercises"]:
        assert record["result"] == pilot_conformance.RESULT_PASS
    exercise_names = {record["exercise"] for record in report["exercises"]}
    assert exercise_names == _EXPECTED_EXERCISE_NAMES


@pytest.mark.parametrize("dropped_key", sorted(_INPUT_KEY_TO_EXERCISE.keys()))
def test_dropped_exercise_input_surfaces_unexercised(tmp_path, now, dropped_key):
    inputs = _build_conformance_inputs(str(tmp_path), now)
    exercise_name = _INPUT_KEY_TO_EXERCISE[dropped_key]
    del inputs[dropped_key]

    report = pilot_conformance.run(
        pilot_conformance.default_exercises(),
        inputs=inputs,
        now=now,
    )
    assert report["ok"] is False

    skipped = next(
        record for record in report["exercises"]
        if record["exercise"] == exercise_name
    )
    assert skipped["result"] == pilot_conformance.RESULT_SKIPPED

    for surface in skipped["surfaces"]:
        assert surface in report["unexercised"]
