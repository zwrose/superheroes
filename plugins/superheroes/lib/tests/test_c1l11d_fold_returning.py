# plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py
"""C1-L11d (WO-C): the returning-review decider's two folds, on a real repository.

Pins, each at the place the rule is enforced:

C1  a catch-up whose lower layer changed a file the pull request also changes, with the pull request's own lines
    unchanged, reads no changed file (the `index` line and the hunk-header line numbers are no part of a file's own
    change), so the empty-round path fires;
C2  a file whose own lines changed, or whose hunk context the base changed, still reads changed, and `overlap` names it;
C3  an earlier record whose only gap is CI pending on its final commit counts as finished once CI is green there;
C4  or green on a head with no changed file; a head with a real change since reads full;
C5  CI that is not green, a reader that fails or answers anything else, or no reader, reads full;
C6  any other gap in the earlier record, or a CI line that names anything else, reads full;
C7  the round driver and the record writer hand the decider a CI reader.

Bite-proof record: c1l11d_wo_c_fold
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import returning_review as R  # noqa: E402
import review_record as RR  # noqa: E402
import test_c1l11b_returning_session as TS  # noqa: E402
import test_returning_review_c1l11 as TR  # noqa: E402
from test_returning_review_c1l11 import _isolated_git  # noqa: E402,F401  (autouse: no global git config)

SHARED = "src/shared.py"


class Reader:
    """A CI reader: ``states[sha]`` (None for a commit it was not given), and the commits it was asked about."""

    def __init__(self, states):
        self.states = states
        self.asked = []

    def __call__(self, sha):
        self.asked.append(sha)
        return self.states.get(sha)


def _pending(reviewed, **over):
    """The record a review writes before CI finishes: ``not-reviewed`` for its CI line alone."""
    record = dict(TR.earlier_record(reviewed), status="not-reviewed",
                  ci={"state": "pending", "sha": reviewed, "source": "GitHub checks", "workflow": None,
                      "read": "1 check pending"},
                  whatIsMissing=["CI is pending on %s (1 check pending)" % reviewed[:7]])
    record.update(over)
    return record


def _shared_with_pr_edit():
    lines = TR.numbered("shared", 30).splitlines(keepends=True)
    lines[25] = "pr_edit = 1\n"
    return "".join(lines)


def _catch_up(tmp_path, base_text):
    """A pull request that edited line 26 of the shared file, reviewed, then a base that rewrote the file, merged in.
    Returns ``(repo, moved base, reviewed commit, earlier record)``."""
    repo = TR.Repo(tmp_path)
    _, reviewed, earlier = TR.returning(repo, first={SHARED: _shared_with_pr_edit()})
    moved = repo.main_commit(SHARED, base_text)
    repo.merge_main()
    return repo, moved, reviewed, earlier


def _far_base_text():
    """The base inserts three lines at the top of the shared file, far from the pull request's hunk."""
    return TR.numbered("top", 3) + TR.numbered("shared", 30)


def _head_only(tmp_path):
    """A pull request reviewed once, then a catch-up merge of an unrelated file: no changed file at the head."""
    repo = TR.Repo(tmp_path)
    _, reviewed, earlier = TR.returning(repo)
    moved = repo.main_commit("docs/other.md", "other\n")
    repo.merge_main()
    return repo, moved, reviewed, earlier


def _with_fix(tmp_path):
    """A pull request reviewed once, then a five-line fix: one changed file at the head."""
    repo = TR.Repo(tmp_path)
    base, reviewed, earlier = TR.returning(repo)
    repo.write("src/app.py", repo.read("src/app.py") + TR.numbered("fix", 5))
    repo.commit("fix")
    return repo, base, reviewed, earlier


# --- C1 / C2: a file reads changed only when its own change differs -----------------------------------------------------

def test_c1_a_catch_up_over_a_file_the_pr_also_changes_reads_no_changed_file(tmp_path):
    # axis: a file is changed when its own change differs, never for an index line or hunk-header line numbers — see bite-proof record c1l11d_wo_c_fold
    repo, moved, reviewed, earlier = _catch_up(tmp_path, _far_base_text())
    head = repo.git("rev-parse", "HEAD")
    raw_reviewed = R._sections_by_file(repo.git("diff", *R._DIFF_ARGS, "%s...%s" % (moved, reviewed)))[SHARED]
    raw_head = R._sections_by_file(repo.git("diff", *R._DIFF_ARGS, "%s...%s" % (moved, head)))[SHARED]
    # the fixture does move the header: the raw sections differ, their own change does not
    assert raw_reviewed != raw_head and "index " in raw_head and "@@ -" in raw_head
    assert R._own_change(raw_reviewed) == R._own_change(raw_head)
    got = TR.decide(repo, moved, earlier)
    assert got["read"] == "changed" and got["changedFiles"] == [] and got["countable"] == 0, got
    assert got["overlap"] == [] and got["deltaDiff"] == "" and TR.tokens(got) == [R.WHY_CHANGED_ONLY]


def test_c2_a_file_whose_own_lines_changed_again_still_reads_changed_and_overlap_names_it(tmp_path):
    repo, moved, _, earlier = _catch_up(tmp_path, _far_base_text())
    repo.write(SHARED, repo.read(SHARED).replace("pr_edit = 1", "pr_edit = 2"))
    repo.commit("own change again")
    got = TR.decide(repo, moved, earlier)
    assert got["read"] == "changed" and got["changedFiles"] == [SHARED] and got["overlap"] == [SHARED], got
    assert any(w.startswith(R.WHY_OVERLAP) for w in got["why"])


def test_c2_a_base_edit_inside_the_prs_hunk_context_still_reads_changed_and_overlap_names_it(tmp_path):
    # axis: a hunk body line, a context line included, still compares exactly — see bite-proof record c1l11d_wo_c_fold
    base_text = TR.numbered("shared", 30).replace("value_shared_28 = 28", "value_shared_28 = 280")
    repo, moved, _, earlier = _catch_up(tmp_path, base_text)
    got = TR.decide(repo, moved, earlier)
    assert got["changedFiles"] == [SHARED] and got["overlap"] == [SHARED], got
    assert got["read"] == "changed" and any(w.startswith(R.WHY_OVERLAP) for w in got["why"])


def test_c2_own_change_drops_only_index_lines_and_hunk_header_numbers():
    text = ("diff --git a/f b/f\nindex 111..222 100644\n--- a/f\n+++ b/f\n@@ -1,3 +4,5 @@ def fn():\n ctx\n-old\n+new\n"
            "@@ -20 +30 @@\n+x\n")
    assert R._own_change(text) == "diff --git a/f b/f\n--- a/f\n+++ b/f\n@@ def fn():\n ctx\n-old\n+new\n@@\n+x\n"
    for kept in ("old mode 100644\nnew mode 100755\n", "rename from a\nrename to b\n", "Binary files a/f and b/f differ\n",
                 "+index 1..2\n", " index 1..2\n"):
        assert R._own_change(kept) == kept


# --- C3 / C4: CI has since passed on an earlier record written with CI pending ------------------------------------------

def test_c3_ci_green_on_the_last_reviewed_commit_settles_the_earlier_record(tmp_path):
    repo, base, reviewed, earlier = _with_fix(tmp_path)
    reader = Reader({reviewed: "green"})
    got = TR.decide(repo, base, _pending(reviewed), ci_state=reader)
    assert got["read"] == "changed" and got["changedFiles"] == ["src/app.py"] and got["countable"] == 5, got
    assert TR.tokens(got) == [R.WHY_CI_SETTLED, R.WHY_CHANGED_ONLY] and R.WHY_CI_SETTLED in R.WHY_TOKENS
    assert reviewed[:7] in got["why"][0] and reader.asked == [reviewed]


def test_c3_ci_green_on_the_last_reviewed_commit_settles_a_catch_up_only_head(tmp_path):
    repo, moved, reviewed, earlier = _head_only(tmp_path)
    got = TR.decide(repo, moved, _pending(reviewed), ci_state=Reader({reviewed: "green"}))
    assert got["read"] == "changed" and got["changedFiles"] == [] and got["countable"] == 0, got
    assert TR.tokens(got) == [R.WHY_CI_SETTLED, R.WHY_CHANGED_ONLY]


def test_c4_ci_green_only_on_a_head_reached_by_catch_up_merges_only_settles_the_earlier_record(tmp_path):
    repo, moved, reviewed, earlier = _head_only(tmp_path)
    head = repo.git("rev-parse", "HEAD")
    got = TR.decide(repo, moved, _pending(reviewed), ci_state=Reader({reviewed: "pending", head: "green"}))
    assert got["read"] == "changed" and got["changedFiles"] == [] and got["countable"] == 0, got
    assert TR.tokens(got) == [R.WHY_CI_SETTLED, R.WHY_CHANGED_ONLY] and head[:7] in got["why"][0], got["why"]


def test_c4_ci_green_only_on_a_head_with_a_real_change_since_reads_full(tmp_path):
    # axis: CI green on the head settles an earlier record only when the head has no changed file — see bite-proof record c1l11d_wo_c_fold
    repo, base, reviewed, earlier = _with_fix(tmp_path)
    head = repo.git("rev-parse", "HEAD")
    got = TR.decide(repo, base, _pending(reviewed), ci_state=Reader({reviewed: "pending", head: "green"}))
    assert got["read"] == "full" and TR.tokens(got) == [R.WHY_INCOMPLETE], got
    assert got["changedFiles"] == [] and got["countable"] is None and "pending" in got["why"][0]


# --- C5: anything but a green answer reads full -------------------------------------------------------------------------

def _raises(sha):
    raise RuntimeError("the checks API went away")


@pytest.mark.parametrize("answer", ["red", "pending", "none", "GREEN", None, True, 1, _raises],
                         ids=["red", "pending", "none", "not-lowercase-green", "none-answer", "bool", "int", "raises"])
def test_c5_a_ci_that_is_not_green_reads_full(tmp_path, answer):
    # axis: only CI "green" settles an earlier record written with CI pending; every other answer reads full — see bite-proof record c1l11d_wo_c_fold
    repo, moved, reviewed, earlier = _head_only(tmp_path)  # no changed file: both the commit and the head are asked
    reader = _raises if answer is _raises else (lambda sha: answer)
    got = TR.decide(repo, moved, _pending(reviewed), ci_state=reader)
    assert got["read"] == "full" and TR.tokens(got) == [R.WHY_INCOMPLETE], got
    assert got["changedFiles"] == [] and got["countable"] is None
    if answer == "red":
        assert "red" in got["why"][0]


def test_c5_no_reader_reads_full(tmp_path):
    repo, moved, reviewed, _ = _head_only(tmp_path)
    got = TR.decide(repo, moved, _pending(reviewed))
    assert got["read"] == "full" and TR.tokens(got) == [R.WHY_INCOMPLETE] and "unreadable" in got["why"][0], got


def test_c5_a_failed_ci_on_a_commit_with_a_real_change_reads_full(tmp_path):
    repo, base, reviewed, _ = _with_fix(tmp_path)
    got = TR.decide(repo, base, _pending(reviewed), ci_state=lambda sha: "red")
    assert got["read"] == "full" and TR.tokens(got) == [R.WHY_INCOMPLETE] and "red" in got["why"][0], got


# --- C6: a gap other than CI pending on the final commit reads full -----------------------------------------------------

def _ci_line(sha):
    return "CI is pending on %s (1 check pending)" % sha[:7]


@pytest.mark.parametrize("damage", [
    lambda sha: {"whatIsMissing": [_ci_line(sha), "no maker is named, so independence cannot be shown"]},
    lambda sha: {"whatIsMissing": ["no planned reviewer ran", _ci_line(sha)]},
    lambda sha: {"whatIsMissing": []},
    lambda sha: {"whatIsMissing": _ci_line(sha)},
    lambda sha: {"whatIsMissing": ["no planned reviewer ran"]},
    lambda sha: {"whatIsMissing": ["CI is pending on %s (1 check pending)" % ("0" * 7)]},
    lambda sha: {"whatIsMissing": ["CI is red on %s" % sha[:7]]},
    lambda sha: {"ci": {"state": "pending", "sha": "c" * 40}},
    lambda sha: {"ci": {"state": "green", "sha": sha}},
    lambda sha: {"ci": {"state": "red", "sha": sha}},
    lambda sha: {"ci": None},
    lambda sha: {"abandoned": {}},
    lambda sha: {"status": "reviewed", "abandoned": {}},
    lambda sha: {"status": None},
], ids=["second-line-after", "second-line-before", "no-line", "line-not-a-list", "another-gap", "ci-line-another-commit",
        "line-not-the-pending-line", "ci-sha-another-commit", "ci-green-in-record", "ci-red-in-record", "no-ci",
        "abandoned-present-but-empty", "reviewed-abandoned-present-but-empty", "no-status"])
def test_c6_a_gap_other_than_ci_pending_on_the_final_commit_reads_full(tmp_path, damage):
    # axis: only a record whose one gap is CI pending on its final commit is let through unfinished — see bite-proof record c1l11d_wo_c_fold
    repo, base, reviewed, _ = _with_fix(tmp_path)
    record = {k: v for k, v in _pending(reviewed, **damage(reviewed)).items() if v is not None}
    reader = Reader({reviewed: "green", repo.git("rev-parse", "HEAD"): "green"})  # CI is green everywhere: only the record can fail
    got = TR.decide(repo, base, record, ci_state=reader)
    assert got["read"] == "full" and TR.tokens(got) == [R.WHY_INCOMPLETE], got
    assert got["changedFiles"] == [] and got["countable"] is None and reader.asked == []


def test_c6_an_unknown_status_with_the_ci_pending_gap_reads_full(tmp_path):
    repo, base, reviewed, _ = _with_fix(tmp_path)
    reader = Reader({reviewed: "green", repo.git("rev-parse", "HEAD"): "green"})
    got = TR.decide(repo, base, _pending(reviewed, status="future-status"), ci_state=reader)
    assert got["read"] == "full" and TR.tokens(got) == [R.WHY_INCOMPLETE], got
    assert got["changedFiles"] == [] and got["countable"] is None and reader.asked == []


def test_c6_an_abandoned_record_reads_full_whatever_ci_says(tmp_path):
    repo, base, reviewed, _ = _with_fix(tmp_path)
    got = TR.decide(repo, base, _pending(reviewed, abandoned={"reason": "closed"}), ci_state=lambda sha: "green")
    assert got["read"] == "full" and TR.tokens(got) == [R.WHY_EARLIER_UNUSABLE], got


def test_c6_the_clean_pending_record_is_the_one_that_passes(tmp_path):
    repo, base, reviewed, _ = _with_fix(tmp_path)
    for line in ("CI is pending on %s" % reviewed[:7], _ci_line(reviewed)):
        got = TR.decide(repo, base, _pending(reviewed, whatIsMissing=[line]), ci_state=lambda sha: "green")
        assert got["read"] == "changed" and R.WHY_CI_SETTLED in TR.tokens(got), got


# --- C7: the callers hand the decider a CI reader -----------------------------------------------------------------------

def _seam(monkeypatch):
    calls = []

    def seam(*args, **kwargs):
        calls.append((args, kwargs))
        return {"read": "full", "lastReviewed": None, "why": ["%s: stub" % R.WHY_INCOMPLETE]}

    monkeypatch.setattr(TS.RD, "_returning_decide", seam)
    return calls


def test_c7_the_driver_hands_the_decider_the_production_ci_reader(tmp_path, monkeypatch):
    # axis: the driver passes the production CI reader to the decider whenever the repository root is known — see bite-proof record c1l11d_wo_c_fold
    s = TS.Session(tmp_path, monkeypatch, change=TS._append("src/shared.py", "extra = 1\n"))
    sentinel, roots = (lambda sha: "green"), []
    monkeypatch.setattr(TS.RD.returning_review, "production_ci_state", lambda root: roots.append(root) or sentinel)
    calls = _seam(monkeypatch)
    s.next()
    [(args, kwargs)] = calls
    assert kwargs["ci_state"] is sentinel and roots == [s.repo.root] and args[0] == s.repo.root


def test_c7_the_driver_hands_no_reader_when_it_has_no_repository_root(tmp_path, monkeypatch):
    s = TS.Session(tmp_path, monkeypatch, change=TS._append("src/shared.py", "extra = 1\n"))
    s.cfg.pop("repoRoot")
    monkeypatch.setattr(TS.RD.returning_review, "production_ci_state", lambda root: pytest.fail("no root, no reader"))
    calls = _seam(monkeypatch)
    s.next()
    [(args, kwargs)] = calls
    assert "ci_state" not in kwargs


def test_c7_the_carry_check_hands_the_decider_its_reader_only_when_it_has_one():
    # axis: the carry check passes the writer's CI reader to the decider as a keyword, and only when it has one — see bite-proof record c1l11d_wo_c_fold
    seen = []

    def decide(*args, **kwargs):
        seen.append(kwargs)
        return {"read": "full", "changedFiles": [], "why": []}

    def strict(repo_root, base, head, earlier, proven=()):
        return {"read": "full", "changedFiles": [], "why": []}

    prior, sha, reader = {"finalCommit": {"sha": "a" * 40}, "findings": []}, "a" * 40, (lambda s: "green")
    RR.carry_refusal(prior, sha, "/r", "b" * 40, "c" * 40, [], decide, reader)
    RR.carry_refusal(prior, sha, "/r", "b" * 40, "c" * 40, [], decide)
    assert RR.carry_refusal(prior, sha, "/r", "b" * 40, "c" * 40, [], strict).startswith("the earlier review does not stand")
    assert seen[0]["ci_state"] is reader and "ci_state" not in seen[1]


def test_c7_the_production_reader_reads_the_writers_ci_state_and_answers_none_on_any_fault(monkeypatch):
    asked = []
    monkeypatch.setattr(RR, "_readers", lambda overrides: {"repo_name": lambda root: "owner/repo"})
    monkeypatch.setattr(RR, "_ci", lambda rd, repo, sha, root: asked.append((repo, sha, root)) or {"state": "green"})
    assert R.production_ci_state("/r")("a" * 40) == "green" and asked == [("owner/repo", "a" * 40, "/r")]

    def boom(rd, repo, sha, root):
        raise RuntimeError("no network")

    monkeypatch.setattr(RR, "_ci", boom)
    assert R.production_ci_state("/r")("a" * 40) is None
