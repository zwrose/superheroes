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
    assert st["unmapped_commits"] == 1                 # EXACTLY the stray commit (no spurious empty row)
    assert st["provenance"] in ("absent", "present", "garbled")


def test_gather_reads_git_from_the_worktree_not_cwd(tmp_path):
    # The build branch lives in a SEPARATE build worktree; gather must read git from --worktree, not
    # the ambient cwd. Run from an UNRELATED empty repo (cwd) and point --worktree at the real build repo.
    wt = str(tmp_path / "wt")
    os.makedirs(wt)
    _git(wt, "init", "-q")
    _git(wt, "commit", "--allow-empty", "-m", "base", "-q")
    _git(wt, "checkout", "-q", "-b", "superheroes/wi-abc")
    _git(wt, "branch", "-f", "main", "HEAD")
    _git(wt, "commit", "--allow-empty", "-m", "task 1\n\nTask-Id: 1", "-q")
    _git(wt, "commit", "--allow-empty", "-m", "stray (no trailer)", "-q")
    cwd = str(tmp_path / "cwd")           # the showrunner's main checkout — a DIFFERENT, commit-free repo
    os.makedirs(cwd)
    _git(cwd, "init", "-q")
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    out = subprocess.run([sys.executable, CLI, "gather", "--work-item", "wi",
                          "--branch", "superheroes/wi-abc", "--valid-ids", "1,2", "--worktree", wt],
                         cwd=cwd, env=env, capture_output=True, text=True)
    st = json.loads(out.stdout)
    assert "1" in st["committed_task_ids"]              # read came from the worktree, not cwd
    assert st["unmapped_commits"] == 1                  # EXACTLY the stray commit (no spurious empty row)


# ---------------------------------------------------------------------------
# Configurable base branch (--base) tests
# ---------------------------------------------------------------------------

def test_gather_with_explicit_base_uses_configured_base(tmp_path):
    """--base <branch> feeds the merge-base instead of origin/HEAD detection."""
    repo = str(tmp_path)
    _git(repo, "init", "-q")
    _git(repo, "commit", "--allow-empty", "-m", "base-commit", "-q")
    # Create a local 'feature-base' branch at the base commit.
    _git(repo, "branch", "feature-base", "HEAD")
    _git(repo, "checkout", "-q", "-b", "superheroes/wi-cfg")
    _git(repo, "commit", "--allow-empty", "-m", "task 1\n\nTask-Id: 1", "-q")
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    out = subprocess.run(
        [sys.executable, CLI, "gather", "--work-item", "wi",
         "--branch", "superheroes/wi-cfg", "--valid-ids", "1",
         "--base", "feature-base"],
        cwd=repo, env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    st = json.loads(out.stdout)
    # Only 1 commit above the configured base and it carries a valid Task-Id.
    assert "1" in st["committed_task_ids"]
    # No stray commit above the configured base, and the trailers' trailing-newline artifact is
    # now dropped (sha-less rows skipped in _gather) -> EXACTLY zero unmapped.
    assert st["unmapped_commits"] == 0


def test_gather_default_base_unchanged_when_base_arg_absent(tmp_path):
    """Absent --base uses the existing _base() resolution; default unchanged."""
    repo = str(tmp_path)
    _git(repo, "init", "-q")
    _git(repo, "commit", "--allow-empty", "-m", "base", "-q")
    _git(repo, "checkout", "-q", "-b", "superheroes/wi-abc")
    _git(repo, "branch", "-f", "main", "HEAD")
    _git(repo, "commit", "--allow-empty", "-m", "task 1\n\nTask-Id: 1", "-q")
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    out = subprocess.run(
        [sys.executable, CLI, "gather", "--work-item", "wi",
         "--branch", "superheroes/wi-abc", "--valid-ids", "1"],
        cwd=repo, env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    st = json.loads(out.stdout)
    assert "1" in st["committed_task_ids"]


def test_gather_unresolvable_base_emits_structured_stdout_error(tmp_path):
    """An unresolvable --base must FAIL CLOSED as a STRUCTURED stdout error (C-I3): exit 0 with a
    {"error": <specific reason>} on stdout (NOT a stderr SystemExit the exec pipe discards). The
    spine parks on that specific reason instead of the generic 'could not gather' park."""
    repo = str(tmp_path)
    _git(repo, "init", "-q")
    _git(repo, "commit", "--allow-empty", "-m", "base", "-q")
    _git(repo, "checkout", "-q", "-b", "superheroes/wi-abc")
    _git(repo, "commit", "--allow-empty", "-m", "task 1\n\nTask-Id: 1", "-q")
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    out = subprocess.run(
        [sys.executable, CLI, "gather", "--work-item", "wi",
         "--branch", "superheroes/wi-abc", "--valid-ids", "1",
         "--base", "nonexistent-branch-xyz"],
        cwd=repo, env=env, capture_output=True, text=True)
    # Exit 0 so the exec dumb-pipe captures stdout (it returns only {ok, stdout}).
    assert out.returncode == 0, out.stderr
    payload = json.loads(out.stdout)
    # Structured error key — and crucially NOT a usable state (no silent 0-unmapped result).
    assert "error" in payload, "unresolvable base must surface a structured stdout error"
    assert "nonexistent-branch-xyz" in payload["error"], "error must name the specific base"
    assert "committed_task_ids" not in payload, "must not emit a usable state on an unresolvable base"


def test_gather_maps_task_id_before_co_authored_by_trailer_block(tmp_path):
    """Task-Id separated from Co-Authored-By by a blank line is invisible to git trailers but must map."""
    repo = str(tmp_path)
    _git(repo, "init", "-q")
    _git(repo, "commit", "--allow-empty", "-m", "base", "-q")
    _git(repo, "checkout", "-q", "-b", "superheroes/wi-abc")
    _git(repo, "branch", "-f", "main", "HEAD")
    msg = "feat: task 1\n\nTask-Id: 1\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
    _git(repo, "commit", "--allow-empty", "-m", msg, "-q")
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    out = subprocess.run([sys.executable, CLI, "gather", "--work-item", "wi",
                          "--branch", "superheroes/wi-abc", "--valid-ids", "1,2"],
                         cwd=repo, env=env, capture_output=True, text=True)
    st = json.loads(out.stdout)
    assert "1" in st["committed_task_ids"]
    assert st["unmapped_commits"] == 0


def test_gather_maps_final_review_sentinel_commit_resume_not_fail_closed(tmp_path):
    """#375 reproduction: a run that parked at the final-review round cap leaves whole-branch
    final-review FIX commits on the branch (no numeric Task-Id — they serve no single task). On
    relaunch the build-gather re-validates every above-base commit; before the fix those fix commits
    read as unmapped and the resume fail-closes on UFR-7. With the reserved sentinel trailer the gather
    maps them, so unmapped==0 and the resume proceeds."""
    import build_state as bs  # the SSOT for the sentinel value
    repo = str(tmp_path)
    _git(repo, "init", "-q")
    _git(repo, "commit", "--allow-empty", "-m", "base", "-q")
    _git(repo, "checkout", "-q", "-b", "superheroes/wi-fr")
    _git(repo, "branch", "-f", "main", "HEAD")
    _git(repo, "commit", "--allow-empty", "-m", "task 1\n\nTask-Id: 1", "-q")
    # Two whole-branch final-review fix commits (the spine's own fix loop landed these), each carrying
    # the reserved sentinel — NOT a numeric task id.
    _git(repo, "commit", "--allow-empty",
         "-m", "build: fix whole-branch findings\n\nTask-Id: %s" % bs.FINAL_REVIEW_TASK_ID, "-q")
    _git(repo, "commit", "--allow-empty",
         "-m", "build: fix more whole-branch findings\n\nTask-Id: %s" % bs.FINAL_REVIEW_TASK_ID, "-q")
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    out = subprocess.run([sys.executable, CLI, "gather", "--work-item", "wi",
                          "--branch", "superheroes/wi-fr", "--valid-ids", "1"],
                         cwd=repo, env=env, capture_output=True, text=True)
    st = json.loads(out.stdout)
    assert st["unmapped_commits"] == 0                  # the resume no longer fail-closes (UFR-7)
    assert "1" in st["committed_task_ids"]
    # The sentinel commits are mapped (not silently dropped) — reality-wins provenance stays complete.
    assert st["committed_task_ids"].count(bs.FINAL_REVIEW_TASK_ID) == 2


def test_gather_sentinel_acceptance_is_additive_stray_still_unmapped(tmp_path):
    """The sentinel acceptance must be ADDITIVE, not a gate-wide loosening: on a resumed branch that
    mixes a numeric task commit, sentinel final-review fix commits, AND a genuine untrailered stray, the
    stray STILL reads unmapped==1 while the sentinel commits map. This is the true #375 resume shape and
    proves accepting the sentinel did not open a wholesale hole in UFR-7."""
    import build_state as bs
    repo = str(tmp_path)
    _git(repo, "init", "-q")
    _git(repo, "commit", "--allow-empty", "-m", "base", "-q")
    _git(repo, "checkout", "-q", "-b", "superheroes/wi-mix")
    _git(repo, "branch", "-f", "main", "HEAD")
    _git(repo, "commit", "--allow-empty", "-m", "task 1\n\nTask-Id: 1", "-q")
    _git(repo, "commit", "--allow-empty",
         "-m", "build: fix whole-branch findings\n\nTask-Id: %s" % bs.FINAL_REVIEW_TASK_ID, "-q")
    _git(repo, "commit", "--allow-empty", "-m", "stray (no trailer)", "-q")   # a genuine unmapped commit
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    out = subprocess.run([sys.executable, CLI, "gather", "--work-item", "wi",
                          "--branch", "superheroes/wi-mix", "--valid-ids", "1"],
                         cwd=repo, env=env, capture_output=True, text=True)
    st = json.loads(out.stdout)
    assert st["unmapped_commits"] == 1                  # EXACTLY the stray — sentinel acceptance is additive
    assert "1" in st["committed_task_ids"]
    assert bs.FINAL_REVIEW_TASK_ID in st["committed_task_ids"]


def test_gather_still_flags_pre_fix_slug_trailered_commit(tmp_path):
    """#375 backward-compat: an OLD parked run whose external final-review fix minted the work-item
    SLUG as the Task-Id is STILL unmapped after this fix — the gate reserves one sentinel, it does not
    accept arbitrary ids. Those commits need a manual re-trailer to the sentinel (the documented
    convention) before they resume. This test pins that UFR-7 stays fail-closed for unknown ids."""
    repo = str(tmp_path)
    _git(repo, "init", "-q")
    _git(repo, "commit", "--allow-empty", "-m", "base", "-q")
    _git(repo, "checkout", "-q", "-b", "superheroes/wi-slug")
    _git(repo, "branch", "-f", "main", "HEAD")
    _git(repo, "commit", "--allow-empty", "-m", "task 1\n\nTask-Id: 1", "-q")
    _git(repo, "commit", "--allow-empty",
         "-m", "build: fix\n\nTask-Id: superheroes-wi-slug", "-q")   # pre-fix external mint = the slug
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    out = subprocess.run([sys.executable, CLI, "gather", "--work-item", "wi",
                          "--branch", "superheroes/wi-slug", "--valid-ids", "1"],
                         cwd=repo, env=env, capture_output=True, text=True)
    st = json.loads(out.stdout)
    assert st["unmapped_commits"] == 1                  # still fail-closed (fix is a sentinel, not "any id")


def test_external_committer_sentinel_roundtrips_through_gather(tmp_path):
    """The EXTERNAL final-review fix path commits via engine_adapter.commit_result(task_id=sentinel).
    Prove that committer's output maps clean through the gather — the whole external chain, not just
    the native-prompt path."""
    import build_state as bs
    sys.path.insert(0, os.path.join(HERE, ".."))
    import engine_adapter
    repo = str(tmp_path)
    _git(repo, "init", "-q")
    # engine_adapter.commit_result spawns its OWN `git commit` with a bare env (no GIT_AUTHOR_* inherited
    # from _git's per-subprocess injection), so pin a repo-local identity or it fails "Author identity
    # unknown" on a clean runner (mirrors test_engine_adapter_effectful.py).
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "commit", "--allow-empty", "-m", "base", "-q")
    _git(repo, "checkout", "-q", "-b", "superheroes/wi-ext")
    _git(repo, "branch", "-f", "main", "HEAD")
    pre = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    # Simulate an engine that only edited the tree (HEAD == pre_sha): the committer mints the single
    # sentinel-trailered commit.
    (tmp_path / "changed.txt").write_text("whole-branch fix")
    res = engine_adapter.commit_result(repo, bs.FINAL_REVIEW_TASK_ID, pre)
    assert res["ok"] is True, res
    env = dict(os.environ, WORKHORSE_STORE_ROOT=str(tmp_path / "store"))
    out = subprocess.run([sys.executable, CLI, "gather", "--work-item", "wi",
                          "--branch", "superheroes/wi-ext", "--valid-ids", "1"],
                         cwd=repo, env=env, capture_output=True, text=True)
    st = json.loads(out.stdout)
    assert st["unmapped_commits"] == 0
    assert bs.FINAL_REVIEW_TASK_ID in st["committed_task_ids"]


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


def test_base_fallback_refs_derive_from_the_shared_constant(monkeypatch):
    # #298 review r2 (Test): _base must genuinely DERIVE its fallback probe order from
    # DEFAULT_BRANCH_FALLBACK (the ONE home shared with acceptance_deps.real_root_ancestry) —
    # a mutant that re-hardcodes ("origin/main", "main", "master") inline would otherwise
    # survive the constant-equality assert. Drive _base with origin/HEAD unset and every
    # candidate missing, and pin the exact probe sequence against the constant.
    import build_state_cli as bsc

    probed = []

    class _R:
        def __init__(self, rc, out=""):
            self.returncode, self.stdout = rc, out

    def fake_git(git_root, *args):
        probed.append(args)
        if args[0] == "symbolic-ref":
            return _R(1)                       # origin/HEAD unset -> fallback path
        if args[0] == "rev-parse":
            return _R(1)                       # every candidate missing -> walk the whole order
        if args[0] == "rev-list":
            return _R(0, "rootsha\n")
        return _R(1)

    monkeypatch.setattr(bsc, "_git", fake_git)
    assert bsc._base("/repo") == "rootsha"
    fallback_probes = [a[-1] for a in probed if a[0] == "rev-parse"]
    expected = ["origin/%s" % bsc.DEFAULT_BRANCH_FALLBACK[0]] + list(bsc.DEFAULT_BRANCH_FALLBACK)
    assert fallback_probes == expected
