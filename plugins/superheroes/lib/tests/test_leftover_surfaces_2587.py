"""#2587 WO-3 - where the owner sees leftover settings copies: the session-start notice, configure's
one-screen view, and configure's route.

Every repository is a real `git init` repository under tmp_path (never committed to). HOME is a
temporary path in every test, so `~` shortening is deterministic and nothing real is read. The
layouts need no legacy store entry (in-repo core.md, review-crew.md and review-decisions.json against
their global copies), because `session_context.assemble` and `configure_route.route` take no review or
test-pilot root. `root` is the control-plane root `assemble` reads by default.

Bite-proof record: wo3_2587_leftover_surfaces
"""
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_PLUGIN_ROOT = os.path.dirname(_LIB)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import configure_route  # noqa: E402
import configure_view  # noqa: E402
import core_md as cm  # noqa: E402
import leftover_settings  # noqa: E402
import mode_reconcile  # noqa: E402
import mode_registry as mr  # noqa: E402
import session_context  # noqa: E402
import store_core  # noqa: E402

ORIGIN = "https://github.com/acme/corner-shop.git"
SECTION = "### Leftover settings copies"
VIEW_HEADING = "## Leftover settings copies"
REASON = ('old settings copies sit where the storage setting does not keep them: %d file(s) '
          '(fix step "Retire leftover settings copies")')

_CORE = cm.render_core(
    {"verifyCommand": "npm test", "stackTags": [], "threatModel": "t", "patterns": ""},
    "confirmed", "2026-01-01", "2026-01-01")
_REVIEW_CREW = "## Focus hints\n- one\n"


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _put(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


class Project:
    """One recorded project: its repo, the control-plane root and the path spellers."""

    def __init__(self, tmp_path, root):
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q")
        _git(repo, "remote", "add", "origin", ORIGIN)
        self.cwd = str(repo)
        self.repo = os.path.realpath(self.cwd)
        self.root = root
        self.home = os.path.realpath(str(tmp_path))

    def register(self, mode):
        rec = mr.write_registry(
            self.cwd, mode, store_core.derive_identifiers(self.cwd)["remote_hash"], root=self.root)
        assert rec is not None and rec["storageMode"] == mode

    def d_in(self, name):
        return os.path.join(self.repo, ".claude", "superheroes", name)

    def d_gl(self, name):
        return os.path.join(mr.project_store_dir(self.cwd, self.root), "config", name)

    def decisions_in(self):
        return os.path.join(self.repo, ".claude", "review-decisions.json")

    def short(self, path):
        """The spelling the notice uses: the home directory shown as `~`."""
        assert path.startswith(self.home + os.sep)
        return "~" + path[len(self.home):]

    # the layouts ---------------------------------------------------------------------------------
    def _global_read_copies(self):
        self.register(mr.GLOBAL)
        _put(self.d_gl("core.md"), _CORE)
        _put(self.d_gl("review-crew.md"), _REVIEW_CREW)
        _put(self.d_gl("review-decisions.json"), '{"global": true}\n')

    def global_with_leftovers(self):
        """Registry global; the read copies on the global side, two stale in-repo copies (core.md and
        the decisions file). No in-repo review-crew.md, which mode_reconcile reports as migration-pending."""
        self._global_read_copies()
        return sorted([
            _put(self.d_in("core.md"), _CORE + "\n<!-- stale in-repo core -->\n"),
            _put(self.decisions_in(), '{"stale": true}\n'),
        ])

    def global_with_review_crew_leftover(self):
        """Registry global, the layout above plus an in-repo review-crew.md: a structural signal
        (migration-pending) is present, so a structural fix outranks the leftover step."""
        left = self.global_with_leftovers()
        left.append(_put(self.d_in("review-crew.md"), "## Focus hints\n- stale\n"))
        return sorted(left)

    def in_repo_with_leftovers(self):
        """Registry in-repo, the mirror image: the read copies in the repo, three stale global copies."""
        self.register(mr.IN_REPO)
        _put(self.d_in("core.md"), _CORE)
        _put(self.d_in("review-crew.md"), _REVIEW_CREW)
        _put(self.decisions_in(), '{"in": true}\n')
        return sorted([
            _put(self.d_gl("core.md"), _CORE + "\n<!-- stale global core -->\n"),
            _put(self.d_gl("review-crew.md"), "## Focus hints\n- stale\n"),
            _put(self.d_gl("review-decisions.json"), '{"stale": true}\n'),
        ])

    def one_copy_of_each(self):
        """Registry global; one copy of each setting, on the global side."""
        self.register(mr.GLOBAL)
        _put(self.d_gl("core.md"), _CORE)
        _put(self.d_gl("review-crew.md"), _REVIEW_CREW)
        _put(self.d_gl("review-decisions.json"), '{"global": true}\n')


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    # HOME is a temporary path, so `~` shortening is deterministic and nothing real is read.
    monkeypatch.setenv("HOME", os.path.realpath(str(tmp_path)))
    # route() reaches hero_evidence via resolve/gather_signals, which probes the real global hero
    # store; pin it so a stray entry cannot flip the route.
    monkeypatch.setattr(mr, "_hero_global_root", lambda name: str(tmp_path / "heroglobal"))


@pytest.fixture
def root(isolated_default_store_root):
    return os.path.realpath(isolated_default_store_root)


@pytest.fixture
def p(tmp_path, root):
    return Project(tmp_path, root)


def _assemble(p):
    return session_context.assemble(p.cwd, None, _PLUGIN_ROOT, "claude")


def _assert_surfaces_list(p, left):
    """The three surfaces name every leftover; the route lands on fix with the exact reason."""
    text = _assemble(p)
    assert SECTION in text
    assert "%d old settings copies" % len(left) in text
    view = configure_view.render(p.cwd, root=p.root)
    assert VIEW_HEADING in view
    for path in left:
        assert "- " + p.short(path) in text
        assert "- " + p.short(path) in view
    routed = configure_route.route(p.cwd, root=p.root)
    assert routed["path"] == "fix"
    assert routed["reasons"] == [REASON % len(left)]


def _structural(p):
    """The structural signals `configure_route.route` sees (it calls gather_signals the same way)."""
    signals = mode_reconcile.gather_signals(p.cwd, p.root) or []
    return [s for s in signals if s.get("type") in configure_route._STRUCTURAL]


# --- 1. global, stale copies left behind --------------------------------------------------------

def test_global_leftovers_reach_all_three_surfaces(p):
    # axis: a recorded global project's stale in-repo copies are named at session start, in the view and in the route
    left = p.global_with_leftovers()
    assert [f["path"] for f in leftover_settings.find(p.cwd, p.root)["files"]] == left
    # this layout trips no structural signal, which is why the route reaches the leftover step (step 5)
    assert _structural(p) == []
    _assert_surfaces_list(p, left)


# --- 2. in-repo direction -----------------------------------------------------------------------

def test_in_repo_leftovers_reach_all_three_surfaces(p):
    # axis: a recorded in-repo project's stale global copies are named at session start, in the view and in the route
    left = p.in_repo_with_leftovers()
    assert [f["path"] for f in leftover_settings.find(p.cwd, p.root)["files"]] == left
    _assert_surfaces_list(p, left)


# --- 3. none ------------------------------------------------------------------------------------

def test_no_leftovers_leaves_every_surface_as_it_was(p, monkeypatch):
    # axis: with nothing left over the bootstrap block, the view and the route are those of a build without the feature
    p.one_copy_of_each()
    assert leftover_settings.find(p.cwd, p.root)["files"] == []
    text = _assemble(p)
    view = configure_view.render(p.cwd, root=p.root)
    assert "Leftover settings copies" not in text
    assert "Leftover settings copies" not in view
    assert configure_route.route(p.cwd, root=p.root)["path"] == "view"

    def boom(*args, **kwargs):
        raise RuntimeError("probe broken")

    monkeypatch.setattr(leftover_settings, "find", boom)
    assert _assemble(p) == text
    assert configure_view.render(p.cwd, root=p.root) == view


def test_view_data_always_carries_the_leftovers_key(p):
    # axis: collect's dict gains the key whether or not anything is left over
    p.one_copy_of_each()
    assert configure_view.collect(p.cwd, p.root)["leftovers"]["files"] == []


# --- 4. a probe that raises ---------------------------------------------------------------------

def test_raising_probe_prints_nothing_and_routing_continues(p, monkeypatch, capsys):
    # axis: a broken probe adds no section and no diagnostics line to the bootstrap, nothing to the view, and the route still returns
    p.global_with_leftovers()

    def boom(*args, **kwargs):
        raise RuntimeError("probe broken")

    monkeypatch.setattr(leftover_settings, "find", boom)
    text = _assemble(p)
    assert "Leftover settings copies" not in text
    assert "Bootstrap diagnostics" not in text
    assert "superheroes bootstrap: Leftover settings copies — RuntimeError" in capsys.readouterr().err
    assert VIEW_HEADING not in configure_view.render(p.cwd, root=p.root)
    assert configure_view.collect(p.cwd, p.root)["leftovers"] is None
    # the route returns whatever path it picks; no path is asserted, only that it does not raise
    assert isinstance(configure_route.route(p.cwd, root=p.root), dict)


# --- 5. a structural fix still comes first ------------------------------------------------------

def test_structural_fix_outranks_the_leftover_step(p):
    # axis: with a structural signal present (migration-pending from an in-repo review-crew.md) the route's reason is the structural one
    left = p.global_with_review_crew_leftover()
    assert [f["path"] for f in leftover_settings.find(p.cwd, p.root)["files"]] == left
    assert "migration-pending" in {s["type"] for s in _structural(p)}
    routed = configure_route.route(p.cwd, root=p.root)
    assert routed["path"] == "fix"
    assert routed["reasons"] == ["a structural fix is pending: migration-pending"]
    assert routed["reasons"] != [REASON % len(left)]
