# plugins/superheroes/lib/tests/test_recover_entry_generation.py
import json, os, subprocess, sys
HERE = os.path.dirname(__file__)
ENTRY = os.path.join(HERE, "..", "recover_entry.py")
sys.path.insert(0, os.path.join(HERE, ".."))
import checkpoint as ckpt_lib
import control_plane
import docload
import identifiers


def _git(cwd):
    subprocess.run(["git", "init", "-q"], cwd=cwd, check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "x", "-q"],
                   cwd=cwd, check=True,
                   env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
                            GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t"))


_TASKS_DOC = (
    "---\n"
    "superheroes: doc\n"
    "docType: tasks\n"
    "workItem: wi-store\n"
    "parent: {workItem: wi-store, docType: plan}\n"
    "size: large\n"
    "gates: {review: passed}\n"
    "---\n"
    "# Title\n\nbody line\n"
)


def _setup_global_store(repo):
    import mode_registry
    assert mode_registry.write_registry(repo, mode_registry.GLOBAL, None)
    d = os.path.join(mode_registry.project_store_dir(repo), "docs", "wi-store")
    os.makedirs(d)
    with open(os.path.join(d, "spec.md"), "w", encoding="utf-8") as fh:
        fh.write("---\ndocType: spec\ngates: {review: passed}\n---\n# S\n")
    with open(os.path.join(d, "tasks.md"), "w", encoding="utf-8") as fh:
        fh.write(_TASKS_DOC)


def test_recover_entry_emits_generation(tmp_path):
    # A real git repo + store so acquire succeeds; assert the JSON now carries "generation".
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "x", "-q"],
                   cwd=str(tmp_path), check=True,
                   env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
                            GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t"))
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    out = subprocess.run([sys.executable, ENTRY, "--work-item", "wi"],
                         cwd=str(tmp_path), env=env, capture_output=True, text=True)
    obj = json.loads(out.stdout)
    # The acquired generation is a real integer (not missing/None) — the value, not just the key.
    assert isinstance(obj.get("generation"), int)


def test_recover_entry_content_hash_for_out_of_repo_tasks(tmp_path, monkeypatch):
    """Regression: recover's world.current_content_hash must be real when tasks live in the store."""
    store = str(tmp_path / "store")
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", store)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(str(repo))
    _setup_global_store(str(repo))
    env = dict(os.environ, WORKHORSE_STORE_ROOT=store)
    paths = control_plane.paths(str(repo), "wi-store")
    cp = ckpt_lib.new("wi-store", "workhorse/wi-store-deadbeef")
    ckpt_lib.write(paths["checkpoint"], cp)
    out = subprocess.run([sys.executable, ENTRY, "--work-item", "wi-store", "--snapshot"],
                         cwd=str(repo), env=env, capture_output=True, text=True)
    obj = json.loads(out.stdout)
    chash = obj["world"]["current_content_hash"]
    assert chash is not None, "out-of-repo tasks must content-hash — legacy in-repo path returned null"
    fm, body = docload.load_doc(docload.tasks_doc_path("wi-store", str(repo)))
    assert chash == identifiers.content_hash(fm, body)
