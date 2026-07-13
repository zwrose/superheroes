import os, sys
_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pytest


@pytest.fixture(autouse=True)
def _isolate_store_root(monkeypatch, tmp_path):
    """#121 safety net: NO test may touch (or rename, via migrate_store_root) the developer's real
    ~/.claude store — including tests that spawn a SUBPROCESS (which re-imports the lib fresh, so an
    in-process constant monkeypatch wouldn't reach it). Pin the store root via the env var, which
    IS inherited by subprocesses. Using the legacy WORKHORSE_STORE_ROOT means a test that sets its
    own WORKHORSE_/SUPERHEROES_ env (or delenvs them) still wins — it applies after this fixture.

    Also pin the managed-worktree root: without this, any test (or node smoke inheriting os.environ)
    that reaches buildtree does a real `git worktree add` into the developer's ~/.superheroes-worktrees
    — one orphaned checkout per unique tmp-repo path, accumulating every run and never cleaned. Isolating
    it here (mirroring the store root) keeps every test's worktrees inside tmp_path. A test that sets its
    own SUPERHEROES_WORKTREES_ROOT still wins (applies after this fixture)."""
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "_store_isolation"))
    monkeypatch.setenv("SUPERHEROES_WORKTREES_ROOT", str(tmp_path / "_worktrees_isolation"))
    # #412 review finding: test-pilot's store has its OWN env-pinned root; without this, a
    # test (or its subprocess) that never sets TEST_PILOT_STORE_ROOT resolves — and
    # store_core's pointer self-heal can WRITE INTO — the developer's real
    # ~/.claude/test-pilot store. A test that sets its own still wins (applies after this).
    monkeypatch.setenv("TEST_PILOT_STORE_ROOT", str(tmp_path / "_tp_store_isolation"))
    # 0.10.0 qualification finding #7: the acceptance harness's child env carries the
    # SUPERHEROES_ACCEPTANCE_* markers, and a build-worktree verify run inherits them —
    # making any marker-sensitive test (e.g. enforcer selfcheck arming) fail inside a
    # live acceptance run while passing everywhere else. Scrub them so the suite is
    # hermetic wherever it runs; a test exercising marker behavior sets its own (applies
    # after this fixture).
    monkeypatch.delenv("SUPERHEROES_ACCEPTANCE_DENY_ONLY", raising=False)
    monkeypatch.delenv("SUPERHEROES_ACCEPTANCE_CONTEXT", raising=False)
