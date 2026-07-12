"""#395 Task 6: diff-verifiable local CI gate (CLAUDE.md battery).

Pins the validator scripts and the CI pytest paths so Task 6 attestation is independently
checkable from the diff, not only from the commit message."""
import os
import subprocess

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_CI_PATHS = [
    ".github/scripts/tests/",
    "plugins/superheroes/lib/tests/",
    "plugins/superheroes/eval/tests/",
    "eval/lib/tests/",
]
# Exclude this file so the battery subprocess does not recurse into itself.
_CI_PYTEST_IGNORE = "plugins/superheroes/lib/tests/test_task6_local_ci.py"


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


def test_ci_pytest_battery():
    """Run the same pytest invocation as .github/workflows/ci.yml (CLAUDE.md § CI)."""
    r = _run(
        [
            "python3",
            "-m",
            "pytest",
            *_CI_PATHS,
            "--ignore",
            _CI_PYTEST_IGNORE,
            "-q",
        ],
        timeout=1800,
    )
    assert r.returncode == 0, r.stdout + r.stderr
