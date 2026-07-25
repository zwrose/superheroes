# plugins/superheroes/lib/tests/test_session_context_diagnostics.py
"""B6 (#315): a half-bootstrapped session must leave a breadcrumb the running agent can read back.

Pre-fix, a genuine source FAILURE (a read error, a git error, a budget drop) was breadcrumbed only
to stderr — invisible to an owner's agent, which never sees the hook log. This fix folds those
failures into an in-block "Bootstrap diagnostics" line in the SAME `additionalContext` the agent
reads. The detectors below exercise the real `assemble` path (no monkeypatched disclosure seam):
a real covenant read error and a real budget drop must each surface in the returned block.
"""
import os
import stat
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
LIB = str(HERE.parent)
sys.path.insert(0, LIB)
import session_context  # noqa: E402


def test_unreadable_covenant_surfaces_in_the_block(tmp_path, monkeypatch):
    import mode_registry
    monkeypatch.setattr(mode_registry, "read_registry",
                        lambda cwd, root=None: {"storageMode": "in-repo"})
    plug = tmp_path / "plug"
    rubric = plug / "rubric"
    rubric.mkdir(parents=True)
    cm = rubric / "covenant.md"
    cm.write_text("# covenant\n", encoding="utf-8")
    os.chmod(cm, 0)
    if os.access(str(cm), os.R_OK):
        os.chmod(cm, stat.S_IWUSR | stat.S_IRUSR)
        pytest.skip("cannot make the file unreadable in this environment")
    try:
        block = session_context.assemble(str(tmp_path), None, str(plug), "claude")
    finally:
        os.chmod(cm, stat.S_IWUSR | stat.S_IRUSR)
    assert "Bootstrap diagnostics" in block, "a failed source must leave an in-block breadcrumb"
    assert "Covenant" in block, "the diagnostics line must name the failed source"
    assert "read error" in block


def test_budget_drop_surfaces_in_the_block(tmp_path, monkeypatch, capsys):
    import mode_registry
    monkeypatch.setattr(mode_registry, "read_registry",
                        lambda cwd, root=None: {"storageMode": "in-repo"})
    monkeypatch.setattr(session_context, "covenant", lambda cwd, plugin_root: "c" * 5000)
    block = session_context.assemble(str(tmp_path), None, "/p", "claude", char_budget=400)
    assert "Bootstrap diagnostics" in block, "a budget-dropped source must leave an in-block breadcrumb"
    assert "omitted for space" in block
    assert "Covenant" in block
    assert "Covenant" in capsys.readouterr().err


def test_clean_bootstrap_has_no_diagnostics_line(tmp_path, monkeypatch):
    import mode_registry
    monkeypatch.setattr(mode_registry, "read_registry", lambda cwd, root=None: None)
    monkeypatch.setattr(mode_registry, "hero_evidence",
                        lambda cwd, root=None, hero_roots=None: {"review-crew": "none"})
    block = session_context.assemble(str(tmp_path), None, "/p", "claude")
    assert "Bootstrap diagnostics" not in block, (
        "a clean bootstrap must not emit a diagnostics line (byte-compatible with pre-fix)")
