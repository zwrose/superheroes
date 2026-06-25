# plugins/superheroes/lib/tests/test_build_state_cli.py
import json, os, subprocess, sys
HERE = os.path.dirname(__file__)
CLI = os.path.join(HERE, "..", "build_state_cli.py")


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
                            GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t"))


def test_gather_maps_trailered_commit_and_flags_untrailered(tmp_path):
    repo = str(tmp_path)
    _git(repo, "init", "-q")
    _git(repo, "commit", "--allow-empty", "-m", "base", "-q")
    # Move onto a feature branch, then anchor a `main` base ref at the base commit, so the
    # task/stray commits land ABOVE the merge-base (works whatever git's default branch is).
    _git(repo, "checkout", "-q", "-b", "superheroes/wi-abc")
    _git(repo, "branch", "-f", "main", "HEAD")
    _git(repo, "commit", "--allow-empty", "-m", "task 1\n\nTask-Id: 1", "-q")
    _git(repo, "commit", "--allow-empty", "-m", "stray (no trailer)", "-q")
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    out = subprocess.run([sys.executable, CLI, "gather", "--work-item", "wi",
                          "--branch", "superheroes/wi-abc", "--valid-ids", "1,2"],
                         cwd=repo, env=env, capture_output=True, text=True)
    st = json.loads(out.stdout)
    assert "1" in st["committed_task_ids"]
    assert st["unmapped_commits"] >= 1                 # the stray commit
    assert st["provenance"] in ("absent", "present", "garbled")


def test_record_reviewed_then_gather_reads_it(tmp_path):
    repo = str(tmp_path)
    _git(repo, "init", "-q")
    _git(repo, "commit", "--allow-empty", "-m", "base", "-q")
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    subprocess.run([sys.executable, CLI, "record-reviewed", "--work-item", "wi", "--task", "1"],
                   cwd=repo, env=env, check=True)
    out = subprocess.run([sys.executable, CLI, "gather", "--work-item", "wi",
                          "--branch", "superheroes/wi-abc", "--valid-ids", "1"],
                         cwd=repo, env=env, capture_output=True, text=True)
    assert json.loads(out.stdout)["review_records"].get("1") == "passed"
