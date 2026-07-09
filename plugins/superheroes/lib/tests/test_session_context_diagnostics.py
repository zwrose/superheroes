# plugins/superheroes/lib/tests/test_session_context_diagnostics.py
"""B6 (#315): a half-bootstrapped session must leave a breadcrumb the running agent can read back.

Pre-fix, a genuine source FAILURE (a read error, a git error, a budget drop) was breadcrumbed only
to stderr — invisible to an owner's agent, which never sees the hook log. This fix folds those
failures into an in-block "Bootstrap diagnostics" line in the SAME `additionalContext` the agent
reads. The detectors below exercise the real `assemble` path (no monkeypatched disclosure seam):
a real read error and a real budget drop must each surface in the returned block.
"""
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
LIB = str(HERE.parent)
sys.path.insert(0, LIB)
import session_context  # noqa: E402

_PLUGIN_ROOT = str(Path(LIB).parent)


def _mkrepo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    if subprocess.run(["git", "init", "-q", str(repo)]).returncode != 0:
        pytest.skip("git unavailable")
    # A real repo so env_block / auto-memory git calls succeed cleanly (no spurious diagnostics).
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    return repo


def test_unreadable_project_claude_md_surfaces_in_the_block(tmp_path):
    repo = _mkrepo(tmp_path)
    cm = repo / "CLAUDE.md"
    cm.write_text("# project rules\n", encoding="utf-8")
    os.chmod(cm, 0)                  # make the read fail for real
    if os.access(str(cm), os.R_OK):  # running as root (or an OS that ignores the mode) — no failure
        os.chmod(cm, stat.S_IWUSR | stat.S_IRUSR)
        pytest.skip("cannot make the file unreadable in this environment")
    try:
        block = session_context.assemble(str(repo), None, _PLUGIN_ROOT, "claude")
    finally:
        os.chmod(cm, stat.S_IWUSR | stat.S_IRUSR)   # let tmp cleanup remove it
    assert "Bootstrap diagnostics" in block, "a failed source must leave an in-block breadcrumb"
    assert "Project CLAUDE.md" in block, "the diagnostics line must name the failed source"


def test_budget_drop_surfaces_in_the_block(tmp_path):
    repo = _mkrepo(tmp_path)
    # A large, readable project CLAUDE.md — present, but far over a tiny budget so it is dropped.
    (repo / "CLAUDE.md").write_text("x" * 5000 + "\n", encoding="utf-8")
    block = session_context.assemble(str(repo), None, _PLUGIN_ROOT, "claude", char_budget=400)
    assert "Bootstrap diagnostics" in block, "a budget-dropped source must leave an in-block breadcrumb"


def test_clean_bootstrap_has_no_diagnostics_line(tmp_path):
    repo = _mkrepo(tmp_path)
    (repo / "CLAUDE.md").write_text("# small\n", encoding="utf-8")
    block = session_context.assemble(str(repo), None, _PLUGIN_ROOT, "claude")
    assert "Bootstrap diagnostics" not in block, (
        "a clean bootstrap must not emit a diagnostics line (byte-compatible with pre-fix)")
