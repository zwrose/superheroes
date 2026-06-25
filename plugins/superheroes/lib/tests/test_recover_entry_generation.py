# plugins/superheroes/lib/tests/test_recover_entry_generation.py
import json, os, subprocess, sys
HERE = os.path.dirname(__file__)
ENTRY = os.path.join(HERE, "..", "recover_entry.py")


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
