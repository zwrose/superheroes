import os
import shutil
import sys
import tempfile

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import heartbeat as _heartbeat  # noqa: E402  (needs the sys.path insert above)

_TMP_BASE = os.path.realpath(tempfile.gettempdir())

# Read the names off their one home rather than respelling them here — a rename in
# heartbeat.py that this fixture did not follow would silently stop pinning.
_HEARTBEAT_ROOT_ENV = _heartbeat.HEARTBEAT_ROOT_ENV
_LAUNCH_ID_ENV = _heartbeat.LAUNCH_ID_ENV


def _path_has_symlinked_ancestor(path):
    current = os.path.realpath(path)
    while True:
        if os.path.islink(current):
            return True
        parent = os.path.dirname(current)
        if parent == current:
            return False
        current = parent


@pytest.fixture
def tmp_base():
    return _TMP_BASE


@pytest.fixture
def path_has_symlinked_ancestor():
    return _path_has_symlinked_ancestor


@pytest.fixture
def private_tmp():
    path = tempfile.mkdtemp(dir=_TMP_BASE)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


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
    # #843, hoisted here by #866: `launcher.py` exports SUPERHEROES_LAUNCH_ID and
    # SUPERHEROES_HEARTBEAT_ROOT into every builder session it spawns, so in a launcher-issued
    # session those values are ambient for the whole suite. Any test that builds its own
    # heartbeat/launch-ledger root under tmp_path and then reaches `heartbeat.resolve_root`
    # with the process env silently resolves the AMBIENT root instead — six independent field
    # receipts in one night, while CI (which sets neither var) stayed green. #843 pinned the
    # one module that had tests then; the class is every lib test module, present and future,
    # so the pin belongs here beside the store roots. Deleting rather than redirecting is
    # deliberate: a test that needs either var establishes its own value, which still wins
    # (it applies after this fixture).
    monkeypatch.delenv(_HEARTBEAT_ROOT_ENV, raising=False)
    monkeypatch.delenv(_LAUNCH_ID_ENV, raising=False)
