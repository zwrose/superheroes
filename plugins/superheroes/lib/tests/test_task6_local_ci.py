"""#395 Task 6: diff-verifiable local CI gate (CLAUDE.md battery).

Pins the validator scripts and the CI pytest inventory count so Task 6 attestation is
independently checkable from the diff, not only from the commit message."""
import os
import re
import subprocess

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_CI_PATHS = [
    ".github/scripts/tests/",
    "plugins/superheroes/lib/tests/",
    "plugins/superheroes/eval/tests/",
    "eval/lib/tests/",
]
# Task 6 2026-07-12 inventory (includes this file + test_bundle_395_hardening.py); bump when CI grows.
_EXPECTED_COLLECTED = 3320


def _run(cmd, timeout=120):
    return subprocess.run(cmd, cwd=_ROOT, text=True, capture_output=True, timeout=timeout)


def test_validate_marketplace():
    r = _run(["python3", ".github/scripts/validate_marketplace.py"])
    assert r.returncode == 0, r.stdout + r.stderr


def test_validate_hosts():
    r = _run(["python3", ".github/scripts/validate_hosts.py"])
    assert r.returncode == 0, r.stdout + r.stderr


def test_validate_skills():
    r = _run(["python3", ".github/scripts/validate_skills.py"])
    assert r.returncode == 0, r.stdout + r.stderr


def test_ci_pytest_inventory_count():
    r = _run(["python3", "-m", "pytest", *_CI_PATHS, "--collect-only", "-q"])
    assert r.returncode == 0, r.stderr
    m = re.search(r"(\d+) tests collected", r.stdout)
    assert m, "expected 'N tests collected' in collect-only output:\n" + r.stdout
    assert int(m.group(1)) == _EXPECTED_COLLECTED
