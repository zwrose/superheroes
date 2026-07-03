# plugins/superheroes/lib/tests/test_fence_cli.py
import json, os, subprocess, sys
HERE = os.path.dirname(__file__)
CLI = os.path.join(HERE, "..", "fence_cli.py")
sys.path.insert(0, os.path.join(HERE, ".."))
import ref_lock


def _git(cwd):
    subprocess.run(["git", "init", "-q"], cwd=cwd, check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "x", "-q"],
                   cwd=cwd, check=True,
                   env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
                            GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t"))


def _run(cli_args, cwd, env):
    return subprocess.run([sys.executable, CLI, *cli_args],
                          cwd=cwd, env=env, capture_output=True, text=True)


def test_cli_bad_generation_fails_closed(tmp_path):
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    _git(repo)
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    out = _run(["--work-item", "wi", "--generation", "x", "--root", repo], repo, env)
    assert json.loads(out.stdout)["ok"] is False


def test_fence_cli_uses_root_not_ambient_cwd(tmp_path):
    """Acquire in store A; fence/release with cwd=B but --root=A must hit the held lease."""
    store_root = str(tmp_path / "store")
    repo_a = str(tmp_path / "repo-a")
    repo_b = str(tmp_path / "repo-b")
    os.makedirs(repo_a)
    os.makedirs(repo_b)
    _git(repo_a)
    _git(repo_b)
    env = dict(os.environ, WORKHORSE_STORE_ROOT=store_root)
    os.environ.update(env)
    import control_plane
    store = control_plane.ensure_store(repo_a)
    ok, gen, _ = ref_lock.acquire(store, "wi")
    assert ok and gen == 1
    renew = _run(["--work-item", "wi", "--generation", str(gen), "--root", repo_a], repo_b, env)
    assert json.loads(renew.stdout)["ok"] is True
    release = _run(["--work-item", "wi", "--generation", str(gen), "--root", repo_a, "--release"],
                   repo_b, env)
    assert json.loads(release.stdout)["ok"] is True
    sha, lease = ref_lock.read_lease(store, "wi")
    assert sha is None and lease is None


def test_fence_cli_root_without_store_fails_closed(tmp_path):
    missing = str(tmp_path / "no-such-checkout")
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    out = _run(["--work-item", "wi", "--generation", "1", "--root", missing], str(tmp_path), env)
    payload = json.loads(out.stdout)
    assert payload["ok"] is False
    assert payload["reason"] == "control-plane store unusable"
