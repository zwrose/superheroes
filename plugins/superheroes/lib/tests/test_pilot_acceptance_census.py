"""Census: pilot_acceptance framework rows and evidence pointers stay honest."""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_acceptance as pa  # noqa: E402
import pilot_conformance as pc  # noqa: E402

_EXPECTED_DECLARED_LIMITS = {
    "results-only-key-position": {
        "ruling": pa.RULING_OWNER_RULED,
        "claim": (
            "An account name shaped like a field name is not matched in dict-key position, "
            "so a producer keying a result dict by account name leaks that name past the guard. "
            "Value-position detection and all non-account material are unchanged."
        ),
        "closure_path": (
            "The schema-key-position exemption design (fourteen call sites), funded only if a "
            "project's threat model names key-position account-name leakage."
        ),
    },
    "sentinel-account-attestation": {
        "ruling": pa.RULING_OWNER_RULED,
        "claim": (
            "The framework verifies the sentinel account is absent from the mint allowlist but not "
            "that it names no real account; a real-but-not-mintable account satisfies every "
            "framework-side check."
        ),
        "closure_path": (
            "Project attestation; promote to an A1 schema field only if a project's threat model "
            "demands it."
        ),
    },
    "appctl-stop-pgid-reuse": {
        "ruling": pa.RULING_OWNER_RULED,
        "claim": (
            "Reaping releases the child pid, so signals sent after a successful reap address the "
            "process group by number rather than pinned identity; a pid recycled into a group leader "
            "between two adjacent syscalls would be mis-signalled."
        ),
        "closure_path": (
            "Platform-specific group-membership enumeration, funded only if a project's threat model "
            "names pid-wraparound races."
        ),
    },
    "bounded-run-clean-exit-containment": {
        "ruling": pa.RULING_OWNER_RULED,
        "claim": (
            "The shared runner signals the whole process group on every termination path, but a "
            "command that exits cleanly after detaching a helper never has its group signalled, so "
            "the helper survives."
        ),
        "closure_path": (
            "A containment-on-success semantics decision, funded only on field evidence: a real "
            "leaked helper observed reopens it."
        ),
    },
    "residue-scan-encoded-material": {
        "ruling": pa.RULING_PENDING_OWNER_RULING,
        "claim": (
            "A substring scan cannot catch base64, UTF-16, or percent-encoded material, so "
            "redaction is established only against plain-text residue of declared material."
        ),
        "closure_path": "Awaiting owner ruling.",
    },
    "screenshot-pixels-uninspectable": {
        "ruling": pa.RULING_PENDING_OWNER_RULING,
        "claim": (
            "The capture receipt binds bytes to a digest and checks format; nothing establishes "
            "that what was rendered carries no secret."
        ),
        "closure_path": "Awaiting owner ruling.",
    },
    "trace-retention-usually-refuses": {
        "ruling": pa.RULING_PENDING_OWNER_RULING,
        "claim": (
            "Any binary archive member refuses retention fail-closed, and real browser traces carry "
            "binary screencast frames, so the opt-in trace path exists and is exercised but rarely "
            "retains."
        ),
        "closure_path": "Awaiting owner ruling.",
    },
}


def _exercise_evidence_pointers():
    pointers = []
    for spec in pa.EXTRAPOLATION_POINTS:
        evidence = spec.get("evidence")
        if evidence is not None:
            pointers.append((spec["id"], evidence))
    for spec in pa.TRIPWIRE_ROWS:
        evidence = spec.get("evidence")
        if evidence is not None:
            pointers.append((spec["id"], evidence))
    return pointers


def _registered_exercise_names():
    return {fn.conformance_exercise for fn in pc.default_exercises()}


def test_framework_declared_limits_census_bidirectional():
    actual = {row["limit_id"]: row for row in pa.FRAMEWORK_DECLARED_LIMITS}
    assert set(actual) == set(_EXPECTED_DECLARED_LIMITS)
    assert len(actual) == len(_EXPECTED_DECLARED_LIMITS)
    for limit_id, expected in _EXPECTED_DECLARED_LIMITS.items():
        row = actual[limit_id]
        assert row["ruling"] == expected["ruling"]
        assert row["claim"] == expected["claim"]
        assert row["closure_path"] == expected["closure_path"]


@pytest.mark.parametrize("row_id,evidence", _exercise_evidence_pointers())
def test_evidence_pointer_surface_in_required_inventory(row_id, evidence):
    assert evidence["surface"] in pc.REQUIRED_SURFACES, (
        "%s cites unknown surface %s" % (row_id, evidence["surface"])
    )


@pytest.mark.parametrize("row_id,evidence", _exercise_evidence_pointers())
def test_evidence_pointer_exercise_in_default_registry(row_id, evidence):
    assert evidence["exercise"] in _registered_exercise_names(), (
        "%s cites unknown exercise %s" % (row_id, evidence["exercise"])
    )
