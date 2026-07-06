import os, sys
import tempfile
_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pytest


@pytest.fixture(autouse=True)
def _isolate_store_root(monkeypatch, tmp_path, tmp_path_factory):
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
    # 0.10.0 qualification finding #7: the acceptance harness's child env carries the
    # SUPERHEROES_ACCEPTANCE_* markers, and a build-worktree verify run inherits them —
    # making any marker-sensitive test (e.g. enforcer selfcheck arming) fail inside a
    # live acceptance run while passing everywhere else. Scrub them so the suite is
    # hermetic wherever it runs; a test exercising marker behavior sets its own (applies
    # after this fixture).
    monkeypatch.delenv("SUPERHEROES_ACCEPTANCE_DENY_ONLY", raising=False)
    monkeypatch.delenv("SUPERHEROES_ACCEPTANCE_CONTEXT", raising=False)
    # architecture review (finding #16 follow-up, PR #266): `real_discover_artifacts` now
    # also lists `<tempfile.gettempdir()>/superheroes-acceptance/` (the launcher's
    # terminal-record handoff base) as a dir_base. Left pointed at the REAL global /tmp,
    # any dev machine that has ever run a live acceptance harness accumulates genuine
    # `accept-harness-*` dirs there — exactly the ambient state this suite must never
    # depend on (same class of leak the store/worktree isolation above already guards
    # against). Redirect `tempfile.gettempdir()` to a dir OUTSIDE this test's own
    # `tmp_path` (several tests enumerate `tmp_path`'s full contents as their own
    # fixture/scratch dir, so planting an extra entry inside it would itself be a false
    # positive) so discovery only ever sees what a given test itself plants there. A
    # test that needs the real value can still call the un-patched function directly.
    _tmp_isolation = tmp_path_factory.mktemp("tempdir_isolation", numbered=True)
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(_tmp_isolation))
