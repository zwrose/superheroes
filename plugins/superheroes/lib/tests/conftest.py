import os
import shutil
import subprocess
import sys
import tempfile

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import heartbeat as _heartbeat  # noqa: E402  (needs the sys.path insert above)
import round_driver as _round_driver  # noqa: E402

_TMP_BASE = os.path.realpath(tempfile.gettempdir())

# Read the names off their one home rather than respelling them here — a rename in
# heartbeat.py that this fixture did not follow would silently stop pinning.
_HEARTBEAT_ROOT_ENV = _heartbeat.HEARTBEAT_ROOT_ENV
_LAUNCH_ID_ENV = _heartbeat.LAUNCH_ID_ENV

# Single home for the autouse store-isolation dirname (#844 F7).
_STORE_ISOLATION_DIRNAME = "_store_isolation"


def _isolated_default_store_root_path(tmp_path):
    """Path to the default-store root pinned by _isolate_store_root."""
    return str(tmp_path / _STORE_ISOLATION_DIRNAME)


@pytest.fixture
def isolated_default_store_root(tmp_path):
    return _isolated_default_store_root_path(tmp_path)


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
    that reaches launcher.create_build_worktree does a real `git worktree add` into the developer's
    ~/.superheroes-worktrees
    — one orphaned checkout per unique tmp-repo path, accumulating every run and never cleaned. Isolating
    it here (mirroring the store root) keeps every test's worktrees inside tmp_path. A test that sets its
    own SUPERHEROES_WORKTREES_ROOT still wins (applies after this fixture).

    Drop SUPERHEROES_STORE_ROOT before pinning WORKHORSE_STORE_ROOT: control_plane prefers the former,
    so an exported SUPERHEROES_STORE_ROOT would bypass this isolation. A test that sets its own store
    env still wins (applies after this fixture)."""
    monkeypatch.delenv("SUPERHEROES_STORE_ROOT", raising=False)
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", _isolated_default_store_root_path(tmp_path))
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
    # #1379: the review-session marker bootstrap falls back to the repository of the process cwd
    # when a session's meta carries no repoRoot, so a test sitting in the real checkout wrote its
    # marker into that checkout's git-dir. Run every test from its own tmp_path, which is in no
    # repository, so that fallback resolves nothing. A test that needs another cwd sets its own
    # (applies after this fixture); _guard_real_review_marker below catches any path that
    # still reaches the real checkout.
    monkeypatch.chdir(tmp_path)


def _real_review_marker_path():
    """The review-session marker path of the checkout this suite runs in, or None when this
    tree is not a git checkout (then no marker can be written into it either)."""
    proc = subprocess.run(["git", "-C", _LIB, "rev-parse", "--absolute-git-dir"],
                          capture_output=True, text=True, check=False)
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    return os.path.join(proc.stdout.strip(), _round_driver.SIDECAR_DIRNAME,
                        _round_driver._REVIEW_SESSION_MARKER)


_REAL_REVIEW_MARKER = _real_review_marker_path()


def _read_marker(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except FileNotFoundError:
        return None


@pytest.fixture(autouse=True)
def _guard_real_review_marker(request):
    """#1379 detector: fail the test during which the real checkout's review-session marker
    changed (created, rewritten, or removed). Every test that wrote it is named; under xdist a
    test on another worker whose window overlapped the write is named too, so read the
    failures as candidates."""
    if _REAL_REVIEW_MARKER is None:
        yield
        return
    before = _read_marker(_REAL_REVIEW_MARKER)
    yield
    if _read_marker(_REAL_REVIEW_MARKER) != before:
        pytest.fail("review scope marker of the real checkout (%s) changed during %s"
                    % (_REAL_REVIEW_MARKER, request.node.nodeid))
