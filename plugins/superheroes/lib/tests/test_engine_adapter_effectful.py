import importlib.util
import os
import subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    spec = importlib.util.spec_from_file_location(
        "engine_adapter", os.path.join(_HERE, "..", "engine_adapter.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


EA = _load()


def _git(cwd, *args):
    return subprocess.run(["git", "-C", cwd, *args], check=True,
                          capture_output=True, text=True)


def _repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(str(repo), "init", "-q")
    _git(str(repo), "config", "user.email", "t@t")
    _git(str(repo), "config", "user.name", "t")
    (repo / "f").write_text("x")
    _git(str(repo), "add", "f")
    _git(str(repo), "commit", "-qm", "init")
    return str(repo)


def _head(repo):
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _trailer(repo, ref="HEAD"):
    return _git(repo, "log", "-1", "--format=%(trailers:key=Task-Id,valueonly)", ref).stdout.strip()


def _subject(repo, ref="HEAD"):
    return _git(repo, "log", "-1", "--format=%s", ref).stdout.strip()


def _full_message(repo, ref="HEAD"):
    return _git(repo, "log", "-1", "--format=%B", ref).stdout


def test_commit_result_edits_only_makes_single_trailered_commit(tmp_path):
    repo = _repo(tmp_path)
    pre = _head(repo)
    # engine EDITS only (no commit)
    (tmp_path / "repo" / "g").write_text("engine wrote this")
    res = EA.commit_result(repo, "task-42", pre)
    assert res["ok"] is True and res["sha"]
    assert _head(repo) != pre               # exactly one new commit
    assert _trailer(repo) == "task-42"      # Task-Id trailer present
    # the file the engine wrote is committed
    assert "g" in _git(repo, "show", "--name-only", "--format=", "HEAD").stdout


def test_commit_result_folds_stray_engine_commit_via_soft_reset(tmp_path):
    repo = _repo(tmp_path)
    pre = _head(repo)
    # a MIS-behaving engine left a stray (untrailered) commit despite the instruction
    (tmp_path / "repo" / "g").write_text("stray edit")
    _git(repo, "add", "g")
    _git(repo, "commit", "-qm", "stray engine commit (no trailer)")
    assert _head(repo) != pre
    res = EA.commit_result(repo, "task-7", pre)
    assert res["ok"] is True
    # exactly ONE commit above pre now, and it carries the trailer (the stray was folded in)
    count = _git(repo, "rev-list", "--count", "%s..HEAD" % pre).stdout.strip()
    assert count == "1"
    assert _trailer(repo) == "task-7"


def test_multi_round_fold_prior_landed_commit_survives(tmp_path):
    # The load-bearing invariant: per-dispatch preSHA scopes the soft-reset to THIS round's
    # commits only — a prior round's already-landed trailered commit is BELOW preSHA and survives.
    repo = _repo(tmp_path)
    # Round 1: engine edits, adapter lands a trailered commit.
    pre1 = _head(repo)
    (tmp_path / "repo" / "r1").write_text("round 1 work")
    r1 = EA.commit_result(repo, "task-1", pre1)
    assert r1["ok"] is True
    round1_sha = _head(repo)
    assert _trailer(repo, round1_sha) == "task-1"
    # Round 2: preSHA re-captured AFTER round 1's landed commit; a stray commit this round.
    pre2 = _head(repo)
    (tmp_path / "repo" / "r2").write_text("round 2 stray")
    _git(repo, "add", "r2")
    _git(repo, "commit", "-qm", "round 2 stray (no trailer)")
    r2 = EA.commit_result(repo, "task-1", pre2)
    assert r2["ok"] is True
    # round 1's trailered commit STILL EXISTS untouched (it is below pre2)
    assert _git(repo, "cat-file", "-t", round1_sha).stdout.strip() == "commit"
    assert _trailer(repo, round1_sha) == "task-1"
    # and round 2 folded into exactly one trailered commit above pre2
    count2 = _git(repo, "rev-list", "--count", "%s..HEAD" % pre2).stdout.strip()
    assert count2 == "1"
    assert _trailer(repo, "HEAD") == "task-1"


def test_commit_result_preserves_engine_prescribed_message(tmp_path):
    # (a) #386: the engine committed with the SPEC-PRESCRIBED message → the single folded commit
    # carries THAT message + Task-Id trailer, and the trailer appears exactly once.
    repo = _repo(tmp_path)
    pre = _head(repo)
    prescribed = "feat: append acceptance-run dated line to target.txt"
    (tmp_path / "repo" / "target.txt").write_text("dated line")
    _git(repo, "add", "target.txt")
    _git(repo, "commit", "-qm", prescribed)
    res = EA.commit_result(repo, "task-9", pre)
    assert res["ok"] is True
    # exactly ONE commit above pre, subject is the prescribed message, trailer present once
    count = _git(repo, "rev-list", "--count", "%s..HEAD" % pre).stdout.strip()
    assert count == "1"
    assert _subject(repo) == prescribed
    assert _trailer(repo) == "task-9"
    assert _full_message(repo).count("Task-Id:") == 1


def test_commit_result_edits_only_uses_canned_subject(tmp_path):
    # (b) #386: engine EDITED without committing (HEAD == pre) → canned subject + trailer (unchanged).
    repo = _repo(tmp_path)
    pre = _head(repo)
    (tmp_path / "repo" / "g").write_text("engine wrote this")
    res = EA.commit_result(repo, "task-42", pre)
    assert res["ok"] is True
    assert _head(repo) != pre
    assert _subject(repo) == "build: apply external-engine change"
    assert _trailer(repo) == "task-42"


def test_commit_result_multi_commit_reuses_tip_message(tmp_path):
    # (c) #386: engine left MULTIPLE commits → the TIP message is reused (the engine's final word),
    # folded into a single commit.
    repo = _repo(tmp_path)
    pre = _head(repo)
    (tmp_path / "repo" / "a").write_text("first")
    _git(repo, "add", "a")
    _git(repo, "commit", "-qm", "wip: scaffolding")
    (tmp_path / "repo" / "b").write_text("second")
    _git(repo, "add", "b")
    _git(repo, "commit", "-qm", "feat: the real change")
    res = EA.commit_result(repo, "task-3", pre)
    assert res["ok"] is True
    count = _git(repo, "rev-list", "--count", "%s..HEAD" % pre).stdout.strip()
    assert count == "1"
    assert _subject(repo) == "feat: the real change"   # tip, not the first (wip) commit
    assert _trailer(repo) == "task-3"


def test_commit_result_does_not_double_existing_task_id_trailer(tmp_path):
    # (d) #386: engine commit message ALREADY carries a Task-Id trailer → not doubled.
    repo = _repo(tmp_path)
    pre = _head(repo)
    (tmp_path / "repo" / "c").write_text("change")
    _git(repo, "add", "c")
    _git(repo, "commit", "-qm", "feat: do the thing\n\nTask-Id: task-OLD")
    res = EA.commit_result(repo, "task-new", pre)
    assert res["ok"] is True
    msg = _full_message(repo)
    assert msg.count("Task-Id:") == 1          # exactly one trailer
    assert "task-OLD" not in msg               # the stale trailer was stripped
    assert _trailer(repo) == "task-new"
    assert _subject(repo) == "feat: do the thing"


def test_commit_result_empty_message_falls_back_to_canned(tmp_path):
    # (e) #386: engine commit whose message is empty/whitespace-only → canned fallback.
    repo = _repo(tmp_path)
    pre = _head(repo)
    (tmp_path / "repo" / "d").write_text("change")
    _git(repo, "add", "d")
    # allow-empty-message so git accepts a whitespace-only message
    _git(repo, "commit", "--allow-empty-message", "-qm", "   \n\t  ")
    res = EA.commit_result(repo, "task-e", pre)
    assert res["ok"] is True
    assert _subject(repo) == "build: apply external-engine change"
    assert _trailer(repo) == "task-e"


def test_commit_result_bad_worktree_returns_error_never_raises(tmp_path):
    res = EA.commit_result(str(tmp_path / "not-a-repo"), "t", "deadbeef")
    assert res["ok"] is False and res.get("error")
