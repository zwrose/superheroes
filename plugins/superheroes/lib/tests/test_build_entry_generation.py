# plugins/superheroes/lib/tests/test_build_entry_generation.py
import json, os, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import control_plane, checkpoint as ckpt_lib
HERE = os.path.dirname(__file__)
ENTRY = os.path.join(HERE, "..", "build_entry.py")


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
                            GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t"))


def test_build_entry_writes_lock_generation(tmp_path, monkeypatch):
    repo = str(tmp_path)
    _git(repo, "init", "-q")
    _git(repo, "commit", "--allow-empty", "-m", "x", "-q")
    # minimal approved tasks doc so content_hash_for succeeds
    d = os.path.join(repo, "docs", "superheroes", "wi")
    os.makedirs(d)
    open(os.path.join(d, "tasks.md"), "w").write(
        "---\nsuperheroes: doc\ndocType: tasks\nworkItem: wi\n"
        "parent: {workItem: wi, docType: plan}\nsize: large\n"
        "gates: {review: passed}\n---\n# t\n")
    # The in-process reader (control_plane/checkpoint, below) must use the SAME store the
    # subprocess writes to — set it on this process's env, not just the subprocess's.
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(tmp_path / "store"))
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    out = subprocess.run([sys.executable, ENTRY, "--work-item", "wi", "--generation", "7"],
                         cwd=repo, env=env, capture_output=True, text=True)
    res = json.loads(out.stdout)
    assert "branch" in res
    assert "path" in res            # build_entry now also emits the managed build-worktree path
    # Isolation canary (#132): this is the one test whose SUBPROCESS does a real `git worktree add`,
    # so it is where a broken conftest pin (or buildtree ignoring SUPERHEROES_WORKTREES_ROOT) would
    # silently leak a checkout into the developer's ~/.superheroes-worktrees. Assert the managed
    # worktree landed under the pinned pytest tmp root — hermetic (no global-state race with a real
    # concurrent build), and loud in CI the moment either side of the pin regresses.
    assert os.path.realpath(res["path"]).startswith(os.path.realpath(str(tmp_path))), (
        "managed build worktree escaped the pinned root: %s" % res["path"])
    # build_entry also emits the reclaim_or_create outcome; resolveBuildTarget's fail-closed guard
    # parks on 'created', so a silent drop of this field must be caught here.
    assert "outcome" in res
    assert res["outcome"] in ("reused", "created")
    cp = ckpt_lib.read(control_plane.paths(repo, "wi")["checkpoint"])
    assert cp["lockGeneration"] == 7
