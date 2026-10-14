"""The repo-root conftest keeps a cloud session's CLAUDE_CODE_REMOTE out of every test.

The proof runs the real root wiring (pytest.ini, conftest.py, source_guard.py) in a
throwaway micro-repository, as a child pytest process, so the nested
plugins/superheroes/lib/tests/conftest.py is never loaded and the root fixture is the
only thing that can unset the variable.
"""
import os
import shutil
import subprocess
import sys

_REPO_ROOT = os.path.realpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
)

_REAL_WIRING_FILES = ("pytest.ini", "conftest.py", "source_guard.py")

_CHILD_TESTS = """\
import os

import pytest


@pytest.fixture(scope="module")
def seen_at_module_scope():
    return os.environ.get("CLAUDE_CODE_REMOTE")


def test_module_scoped_fixture_saw_the_variable_unset(seen_at_module_scope):
    assert seen_at_module_scope is None


def test_variable_stays_unset_after_monkeypatch_undo(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_REMOTE", "set-by-the-test")
    assert os.environ["CLAUDE_CODE_REMOTE"] == "set-by-the-test"
    monkeypatch.undo()
    assert "CLAUDE_CODE_REMOTE" not in os.environ
"""


def _build_micro_repo(root):
    root.mkdir(parents=True, exist_ok=True)
    for name in _REAL_WIRING_FILES:
        shutil.copy2(os.path.join(_REPO_ROOT, name), root / name)
    shipped = root / "lib" / "shipped.py"
    shipped.parent.mkdir()
    shipped.write_text("VALUE = 1\n", encoding="utf-8")
    (root / "test_cloud_env.py").write_text(_CHILD_TESTS, encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        [
            "git", "-c", "user.email=t@e.com", "-c", "user.name=T",
            "-c", "commit.gpgsign=false", "commit", "-q", "-m", "init",
        ],
        cwd=root,
        check=True,
    )


def test_root_conftest_unsets_claude_code_remote_for_module_scope_and_undo(tmp_path):
    # axis: the root conftest alone (no nested conftest) leaves CLAUDE_CODE_REMOTE unset
    # for a module-scoped fixture and after monkeypatch.undo() — see bite-proof record
    # c8c_wo_b.md
    root = tmp_path / "micro"
    _build_micro_repo(root)
    env = {**os.environ, "CLAUDE_CODE_REMOTE": "true", "PYTHONPATH": str(root)}
    env["SUPERHEROES_SOURCE_GUARD_ROOT"] = str(root)
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "test_cloud_env.py", "-q", "-p", "no:cacheprovider"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 0, combined
    assert "2 passed" in combined, combined
