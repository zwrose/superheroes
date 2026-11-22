# plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py
"""Issue 2600: a builder's conflict fix reads ``judgement`` (``conflict-fix``) in the head-coverage check, on real
repositories.

A merge of the base into a reviewed pull request that the builder resolved by hand has no three-way reconstruction, so
the check read it needs-review. When every new commit is such a merge by the builder, the check rebuilds git's own
automatic merge of every remaining file and lists every line the builder made by hand as a hunk for the vet.

One test per row of the issue, and the fail-closed edges:

E-cf-nonmerge   a non-merge commit that changes code keeps needs-review, alone or beside a qualifying merge;
E-cf-side       a merge whose second parent is not the base or an ancestor of it keeps needs-review;
E-cf-first      a merge whose first parent is neither X nor another new merge keeps needs-review (parents reversed too);
E-cf-author     a merge by someone other than the builder keeps needs-review (other-author);
E-cf-untouched  a merge that also changes a file neither parent changed keeps needs-review;
E-cf-clean-edit a hand edit inside a file git merged cleanly keeps needs-review;
E-cf-unresolved a conflict block kept verbatim with its markers keeps needs-review;
E-cf-mode       a merge that changes the file's mode keeps needs-review;
E-cf-attr       a merge driver attribute on the file keeps needs-review;
E-cf-binary     a NUL byte in any of the blobs keeps needs-review;
E-cf-criss      two merge bases keep needs-review;
E-cf-unreadable a failed git read keeps needs-review;
E-cf-onesided   a resolution that takes one side wholesale still reads judgement and lists what it drops;
E-cf-span       a conflict block is listed as one hunk, markers included;
E-cf-none       a merge with no hand-made line keeps today's answer;
E-cf-rename     a rename or copy source keeps today's answer.

Bite-proof record: i2600_head_coverage_conflict_fix
"""
import hashlib
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import head_coverage as HC  # noqa: E402
import returning_review as R  # noqa: E402
import test_returning_review_c1l11 as TR  # noqa: E402
from test_head_coverage_2496 import commit_by_other  # noqa: E402
from test_head_coverage_union_probe_2589 import (  # noqa: E402
    APP, BASE_FUNC, MAIN_FUNC, PR_FUNC, RESOLVED, SHARED, Shape, conflict_merge, run_check, tokens, two_anchor)
from test_returning_review_c1l11 import _isolated_git  # noqa: E402,F401  (autouse: no global git config)

_SCRIPT = os.path.join(_LIB, "head_coverage.py")
OTHER_PY = "src/other.py"
CLEAN_PY = "src/clean.py"
INDENT = " " * 4


class Scene:
    """A fork holding ``fork`` files; the pull request's reviewed leg X holding ``pr`` files; ``main`` moved on by one
    commit per ``main`` file. The builder's merge of main is made by ``merge()``; the repository is left on ``pr``."""

    def __init__(self, tmp_path, fork, pr, main):
        repo = self.repo = TR.Repo(tmp_path)
        for rel, text in fork.items():
            repo.write(rel, text)
        repo.commit("fork files")
        repo.git("branch", "-f", "main", "pr")
        self.fork = repo.git("rev-parse", "HEAD")
        _, self.x, self.record = TR.returning(repo, first=pr)
        for rel, text in main.items():
            repo.main_commit(rel, text)
        self.base = repo.git("rev-parse", "main")

    def merge(self, files, conflict=True, message="merge main"):
        """Merge main into ``pr``; ``files`` (path -> text, or a function of the merged text) are then written by
        hand, and the merge is committed."""
        repo = self.repo
        if conflict:
            conflict_merge(repo)
        else:
            repo.git("merge", "--no-ff", "--no-commit", "main")
        for rel, text in files.items():
            repo.write(rel, text(repo.read(rel)) if callable(text) else text)
        return repo.commit(message)

    def check(self, head, **kwargs):
        return run_check(self.repo, self.base, self.record, head, **kwargs)


def fails_closed(monkeypatch, repo, base, record, head, **kwargs):
    """The check reads needs-review for ``head``, and it is key for key what the check reads with ``_conflict_fix``
    answering None (today's check)."""
    got = run_check(repo, base, record, head, **kwargs)
    assert got["answer"] == "needs-review" and HC.WHY_CONFLICT_FIX not in tokens(got), got
    assert HC.WHY_BEHAVIOUR_CHANGE in tokens(got), got
    with monkeypatch.context() as patch:
        patch.setattr(HC, "_conflict_fix", lambda *args, **kw: None)
        today = run_check(repo, base, record, head, **kwargs)
    assert got == today, (got, today)
    return got


def func_lines(text):
    return text.splitlines(keepends=True)


# --- row 1: the #2585 shape ---------------------------------------------------------------------------------------------


def test_row_1_a_builders_hand_resolved_conflict_reads_judgement_and_lists_the_conflict(tmp_path):
    s = Shape(tmp_path)
    head = s.head()
    got = run_check(s.repo, s.base, s.record, head)
    assert got["answer"] == "judgement" and tokens(got) == [HC.WHY_CONFLICT_FIX], got
    assert got["why"] == ["conflict-fix: every new commit is a merge by the builder that brings the base in; the vet reads "
                          "the 1 hand-made hunk(s) of the conflict fix against both sides"]
    assert got["files"] == [SHARED] and got["reconstructed"] == [] and got["copies"] == [] and got["certified"] == s.reviewed
    assert [c["sha"] for c in got["commits"]] == [head]
    assert len(got["hunks"]) == 1
    hunk = got["hunks"][0]
    assert hunk["kind"] == "conflict-fix" and hunk["file"] == SHARED and hunk["merge"] == head
    assert hunk["parents"] == [s.reviewed, s.base] and hunk["mergeBase"] == s.old_base
    base_lines, pr_lines, main_lines, resolved = (func_lines(t) for t in (BASE_FUNC, PR_FUNC, MAIN_FUNC, RESOLVED))
    body = [" " + line for line in base_lines[:3]]
    body += ["-<<<<<<< ours\n", "-" + pr_lines[3], "-||||||| base\n", "-" + base_lines[3], "-=======\n",
             "-" + main_lines[3], "->>>>>>> theirs\n", "+" + resolved[3], " " + base_lines[4]]
    assert hunk["header"] == "@@ -1,11 +1,5 @@" and hunk["text"] == "@@ -1,11 +1,5 @@\n" + "".join(body), hunk
    assert HC.outcome(got["answer"], "green") == {"outcome": "NOT-READY", "why": "judged-meaningful", "review": "returning",
                                                  "sheet": "none"}
    assert HC.outcome(got["answer"], "green", judged_clear=True) == {"outcome": "READY", "why": "covered", "review": "none",
                                                                     "sheet": "none"}
    carried = HC.outcome(got["answer"], "green", judged_clear=True, sheet="live", sheet_commit=s.reviewed, head=head,
                         carry_answer="judgement", carry_judged_clear=True)
    assert carried == {"outcome": "READY", "why": "covered", "review": "none", "sheet": "republish-carried"}


def test_row_1_only_the_conflicted_region_of_a_long_file_is_listed(tmp_path):
    top, bottom = TR.numbered("top", 20), TR.numbered("bottom", 20)
    s = Scene(tmp_path, {SHARED: top + BASE_FUNC + bottom}, {SHARED: top + PR_FUNC + bottom},
              {SHARED: top + MAIN_FUNC + bottom})
    head = s.merge({SHARED: top + RESOLVED + bottom})
    got = s.check(head)
    assert got["answer"] == "judgement" and tokens(got) == [HC.WHY_CONFLICT_FIX] and got["files"] == [SHARED], got
    assert len(got["hunks"]) == 1
    hunk = got["hunks"][0]
    assert hunk["header"] == "@@ -21,13 +21,7 @@", hunk
    assert "value_top_0 = 0" not in hunk["text"] and "value_bottom_19 = 19" not in hunk["text"], hunk
    assert "value_bottom_1 = 1\n" in hunk["text"] and "-<<<<<<< ours\n" in hunk["text"]


# --- row 2 and 3: a clean catch-up and a tested probe stay proven ---------------------------------------------------------------


def test_row_2_a_clean_merge_of_main_still_reads_proven(tmp_path):
    repo = TR.Repo(tmp_path)
    base, reviewed, earlier = TR.returning(repo)
    moved = repo.main_commit("docs/other.md", "other\n")
    head = repo.merge_main()
    got = run_check(repo, moved, earlier, head)
    assert got["answer"] == "proven" and tokens(got) == [HC.WHY_OWN_CHANGE_UNCHANGED], got
    assert got["files"] == [] and got["hunks"] == [] and got["certified"] == reviewed


def test_row_3_a_head_that_is_a_tested_union_probe_still_reads_proven_union_with_no_hunks(tmp_path):
    s = Shape(tmp_path)
    head = s.head()
    without = s.without_proof(head)
    assert without["answer"] == "judgement" and tokens(without) == [HC.WHY_CONFLICT_FIX]
    got = run_check(s.repo, s.base, s.record, head, s.proof())
    assert got["answer"] == "proven" and tokens(got) == [HC.WHY_PROVEN_UNION], got
    assert got["hunks"] == [] and got["files"] == [] and got["unionProbe"]["used"] is True
    assert got["unionProbe"]["covers"] == [SHARED]


# --- E-cf-nonmerge ----------------------------------------------------------------------------------------------------------------------


def test_e_cf_nonmerge_a_plain_code_commit_alone_keeps_needs_review(tmp_path, monkeypatch):
    repo = TR.Repo(tmp_path)
    base, reviewed, earlier = TR.returning(repo)
    repo.write(APP, TR.numbered("app", 100) + "more = 1\n")
    head = repo.commit("a plain code commit")
    got = fails_closed(monkeypatch, repo, base, earlier, head)
    assert got["files"] == [APP]


def test_e_cf_nonmerge_a_plain_code_commit_beside_a_qualifying_merge_keeps_needs_review(tmp_path, monkeypatch):
    s = Shape(tmp_path, later=True)
    head = s.head()
    got = fails_closed(monkeypatch, s.repo, s.base, s.record, head)
    assert APP in got["files"] and [c["sha"] for c in got["commits"]] == [head, s.later], got


# --- E-cf-side and E-cf-first -------------------------------------------------------------------------------------------------------------


def test_e_cf_side_a_merge_of_a_side_branch_keeps_needs_review(tmp_path, monkeypatch):
    s = Shape(tmp_path)
    repo = s.repo
    repo.git("checkout", "-q", "-b", "alt")
    conflict_merge(repo)
    repo.write(SHARED, RESOLVED)
    alt = repo.commit("a builder's conflict fix on a side branch")
    repo.git("checkout", "-q", "pr")
    repo.git("merge", "--no-ff", "-q", "-m", "merge the side branch", "alt")
    head = repo.git("rev-parse", "HEAD")
    assert repo.git("rev-parse", head + "^1") == s.reviewed and repo.git("rev-parse", head + "^2") == alt
    got = fails_closed(monkeypatch, repo, s.base, s.record, head)
    assert [c["sha"] for c in got["commits"]] == [head, alt]


def test_e_cf_first_a_merge_built_on_an_older_leg_that_drops_the_reviewed_leg_keeps_needs_review(tmp_path, monkeypatch):
    repo = TR.Repo(tmp_path)
    repo.write(SHARED, BASE_FUNC)
    repo.commit("shared function")
    repo.git("branch", "-f", "main", "pr")
    _, first_leg, _ = TR.returning(repo, first={SHARED: PR_FUNC})
    repo.write(APP, "def added():\n    return 1\n")
    certified = repo.commit("second reviewed leg")
    record = TR.earlier_record(certified)
    base = repo.main_commit(SHARED, MAIN_FUNC)
    repo.git("checkout", "-q", "-b", "rewound", first_leg)
    conflict_merge(repo)
    repo.write(SHARED, RESOLVED)
    head = repo.commit("merge main onto the first leg")
    assert repo.git("rev-parse", head + "^1") == first_leg
    got = fails_closed(monkeypatch, repo, base, record, head)
    assert APP in got["files"] and [c["sha"] for c in got["commits"]] == [head]


def test_e_cf_first_a_merge_with_its_parents_reversed_keeps_needs_review(tmp_path, monkeypatch):
    s = Shape(tmp_path)
    repo = s.repo
    repo.git("checkout", "-q", "-b", "reversed", s.base)
    conflict_merge(repo, ref=s.reviewed)
    repo.write(SHARED, RESOLVED)
    head = repo.commit("main with the pull request merged in")
    assert repo.git("rev-parse", head + "^1") == s.base and repo.git("rev-parse", head + "^2") == s.reviewed
    fails_closed(monkeypatch, repo, s.base, s.record, head)


# --- E-cf-author ----------------------------------------------------------------------------------------------------------------------------


def test_e_cf_author_a_merge_by_someone_other_than_the_builder_keeps_needs_review(tmp_path, monkeypatch):
    s = Shape(tmp_path)
    conflict_merge(s.repo)
    s.repo.write(SHARED, RESOLVED)
    head = commit_by_other(s.repo)
    got = fails_closed(monkeypatch, s.repo, s.base, s.record, head)
    assert HC.WHY_OTHER_AUTHOR in tokens(got), got


# --- E-cf-untouched and E-cf-clean-edit -------------------------------------------------------------------------------------------------------


def test_e_cf_untouched_a_merge_that_also_changes_a_file_neither_parent_changed_keeps_needs_review(tmp_path, monkeypatch):
    s = Scene(tmp_path, {SHARED: BASE_FUNC, OTHER_PY: TR.numbered("other", 10)}, {SHARED: PR_FUNC}, {SHARED: MAIN_FUNC})
    head = s.merge({SHARED: RESOLVED, OTHER_PY: lambda text: text + "hand_made = 1\n"})
    got = fails_closed(monkeypatch, s.repo, s.base, s.record, head)
    assert OTHER_PY in got["files"] and SHARED in got["files"], got


def test_e_cf_clean_edit_a_hand_edit_inside_a_file_git_merged_cleanly_keeps_needs_review(tmp_path, monkeypatch):
    lines = func_lines(TR.numbered("clean", 30))
    pr_clean = "".join(lines[:4] + ["pr_clean = 1\n"] + lines[5:])
    main_clean = "".join(lines[:24] + ["main_clean = 1\n"] + lines[25:])
    s = Scene(tmp_path, {SHARED: BASE_FUNC, CLEAN_PY: "".join(lines)}, {SHARED: PR_FUNC, CLEAN_PY: pr_clean},
              {SHARED: MAIN_FUNC, CLEAN_PY: main_clean})
    head = s.merge({SHARED: RESOLVED, CLEAN_PY: lambda text: text + "hand_edit = 1\n"})
    # git merged the file cleanly (both sides' edits are in it); the builder then added a line of their own
    assert "pr_clean = 1" in s.repo.read(CLEAN_PY) and "main_clean = 1" in s.repo.read(CLEAN_PY)
    got = fails_closed(monkeypatch, s.repo, s.base, s.record, head)
    assert CLEAN_PY in got["files"], got


# --- E-cf-unresolved --------------------------------------------------------------------------------------------------------------------------


def two_functions(one, two):
    return ("def one():\n" + INDENT + 'return "%s"\n' % one + TR.numbered("filler", 12) + "def two():\n" + INDENT
            + 'return "%s"\n' % two)


def test_e_cf_unresolved_a_block_kept_verbatim_with_its_markers_keeps_needs_review(tmp_path, monkeypatch):
    s = Scene(tmp_path, {SHARED: two_functions("base-one", "base-two")}, {SHARED: two_functions("pr-one", "pr-two")},
              {SHARED: two_functions("main-one", "main-two")})
    kept = ("<<<<<<< ours\n" + INDENT + 'return "pr-two"\n' + "||||||| base\n" + INDENT + 'return "base-two"\n'
            + "=======\n" + INDENT + 'return "main-two"\n' + ">>>>>>> theirs\n")
    resolved = (two_functions("main-one", "x").split("def two():")[0] + "def two():\n" + INDENT + "return '''\n" + kept + "'''\n")
    head = s.merge({SHARED: resolved})
    assert compile(s.repo.read(SHARED), SHARED, "exec"), "the file still parses"
    fails_closed(monkeypatch, s.repo, s.base, s.record, head)


def diff3_of(repo, ours, base, theirs, path):
    """``git merge-file``'s diff3 text for ``path`` from the three commits, with the labels the check uses."""
    blobs = [repo.git("rev-parse", "%s:%s" % (rev, path)) for rev in (ours, base, theirs)]
    proc = subprocess.run(["git", "-C", repo.root, "merge-file", "-p", "--diff3", "--object-id", "-L", "ours", "-L", "base",
                           "-L", "theirs", *blobs], capture_output=True, text=True)
    assert proc.returncode == 1 and "<<<<<<< ours" in proc.stdout, proc
    return proc.stdout


def test_e_cf_unresolved_whole_a_file_committed_as_gits_conflicted_merge_beside_a_resolved_one_keeps_needs_review(
        tmp_path, monkeypatch):
    # axis: a file identical to git's conflicted automatic merge is unresolved, never a file with nothing to list, so the other file's hunks never stand alone — see bite-proof record i2600_head_coverage_conflict_fix (E-cf-unresolved-whole)
    s = Scene(tmp_path, {SHARED: BASE_FUNC, OTHER_PY: BASE_FUNC}, {SHARED: PR_FUNC, OTHER_PY: PR_FUNC},
              {SHARED: MAIN_FUNC, OTHER_PY: MAIN_FUNC})
    unresolved = diff3_of(s.repo, s.x, s.fork, s.base, OTHER_PY)
    head = s.merge({SHARED: RESOLVED, OTHER_PY: unresolved})
    assert s.repo.read(OTHER_PY) == unresolved
    fails_closed(monkeypatch, s.repo, s.base, s.record, head)


# --- E-cf-mode --------------------------------------------------------------------------------------------------------------------------------


def test_e_cf_mode_a_merge_that_changes_the_files_mode_keeps_needs_review(tmp_path, monkeypatch):
    s = Shape(tmp_path)
    head = s.head(chmod=True)
    modes = s.repo.git("ls-tree", head, "--", SHARED).split()[0], s.repo.git("ls-tree", head + "^1", "--", SHARED).split()[0]
    assert modes == ("100755", "100644")
    fails_closed(monkeypatch, s.repo, s.base, s.record, head)


# --- E-cf-attr --------------------------------------------------------------------------------------------------------------------------------


def test_e_cf_attr_a_merge_driver_attribute_on_the_file_keeps_needs_review(tmp_path, monkeypatch):
    s = Scene(tmp_path, {SHARED: BASE_FUNC, ".gitattributes": SHARED + " merge=union\n"}, {SHARED: PR_FUNC},
              {SHARED: MAIN_FUNC})
    head = s.merge({}, conflict=False)
    union = s.repo.read(SHARED)
    assert "<<<<<<<" not in union and "item.price + item.tax" in union and "item.price - item.discount" in union
    got = fails_closed(monkeypatch, s.repo, s.base, s.record, head)
    assert got["files"] == [SHARED]


# --- E-cf-binary ------------------------------------------------------------------------------------------------------------------------------


def test_e_cf_binary_a_nul_byte_in_the_files_blobs_keeps_needs_review(tmp_path, monkeypatch):
    # the NUL sits past the first 8000 bytes, which is all git's own merge and diff look at, so only the check sees it
    def with_nul(function):
        return function + TR.numbered("pad", 900) + "tail = '\0'\n"

    s = Scene(tmp_path, {SHARED: with_nul(BASE_FUNC)}, {SHARED: with_nul(PR_FUNC)}, {SHARED: with_nul(MAIN_FUNC)})
    head = s.merge({SHARED: with_nul(RESOLVED)})
    assert b"\0" in subprocess.run(["git", "-C", s.repo.root, "cat-file", "blob", head + ":" + SHARED], capture_output=True).stdout
    fails_closed(monkeypatch, s.repo, s.base, s.record, head)


# --- E-cf-criss -------------------------------------------------------------------------------------------------------------------------------


def test_e_cf_criss_two_merge_bases_keep_needs_review(tmp_path, monkeypatch):
    s = Shape(tmp_path)
    head = s.head()
    real = R.production_git(s.repo.root)
    asked = []

    def criss_cross(argv):
        if argv[:2] == ["merge-base", "--all"]:
            asked.append(argv)
            return 0, "%s\n%s\n" % (s.old_base, s.reviewed)
        return real(argv)

    fails_closed(monkeypatch, s.repo, s.base, s.record, head, git=criss_cross)
    assert asked, "the check never asked for the merge bases"


# --- E-cf-unreadable --------------------------------------------------------------------------------------------------------------------------


UNREADABLE = {
    "rev-list-parents": lambda argv: argv[:2] == ["rev-list", "--parents"],
    "is-ancestor": lambda argv: argv[:2] == ["merge-base", "--is-ancestor"],
    "merge-base-all": lambda argv: argv[:2] == ["merge-base", "--all"],
    "ls-tree-other-file": lambda argv: argv[0] == "ls-tree" and argv[-1] == OTHER_PY,
    "ls-tree-shared-file": lambda argv: argv[0] == "ls-tree" and argv[-1] == SHARED,
    "check-attr": lambda argv: argv[0] == "check-attr",
    "cat-file-blob": lambda argv: argv[:2] == ["cat-file", "blob"],
    "merge-file-rebuild": lambda argv: argv[0] == "merge-file" and "--diff3" in argv,
}


@pytest.mark.parametrize("case", sorted(UNREADABLE))
def test_e_cf_unreadable_a_failed_git_read_keeps_needs_review(tmp_path, monkeypatch, case):
    # a second remaining file the merge also edited by hand: a read of it that failed must never read as "nothing to list"
    s = Scene(tmp_path, {SHARED: BASE_FUNC, OTHER_PY: TR.numbered("other", 10)}, {SHARED: PR_FUNC}, {SHARED: MAIN_FUNC})
    head = s.merge({SHARED: RESOLVED, OTHER_PY: lambda text: text + "hand_made = 1\n"})
    real = R.production_git(s.repo.root)
    failed = []

    def seam(argv):
        if UNREADABLE[case](argv):
            failed.append(argv)
            return 128, ""
        return real(argv)

    assert s.check(head)["answer"] == "needs-review"
    fails_closed(monkeypatch, s.repo, s.base, s.record, head, git=seam)
    assert failed, "the check never made the read that was made to fail"


def test_e_cf_attr_unreadable_one_of_two_conflicted_files_keeps_needs_review(tmp_path, monkeypatch):
    # axis: a failed attribute read of one conflicted file refuses the whole merge; the other file's hunks never stand alone — see bite-proof record i2600_head_coverage_conflict_fix (E-cf-attr-one-file)
    s = Scene(tmp_path, {SHARED: BASE_FUNC, OTHER_PY: BASE_FUNC}, {SHARED: PR_FUNC, OTHER_PY: PR_FUNC},
              {SHARED: MAIN_FUNC, OTHER_PY: MAIN_FUNC})
    head = s.merge({SHARED: RESOLVED, OTHER_PY: RESOLVED})
    got = s.check(head)
    assert got["answer"] == "judgement" and tokens(got) == [HC.WHY_CONFLICT_FIX], got
    assert {h["file"] for h in got["hunks"]} == {SHARED, OTHER_PY}, got["hunks"]
    real = R.production_git(s.repo.root)
    asked = []

    def seam(argv):
        if argv[0] == "check-attr" and argv[-1] == OTHER_PY:
            asked.append(argv)
            return 1, ""
        return real(argv)

    fails_closed(monkeypatch, s.repo, s.base, s.record, head, git=seam)
    assert asked, "the check never read the attributes of the second file"


# --- E-cf-span --------------------------------------------------------------------------------------------------------------------------------


def test_e_cf_span_a_block_resolved_by_keeping_one_side_is_one_hunk_with_its_markers(tmp_path):
    def region(tag):
        return "top = 1\n" + TR.numbered(tag, 12) + "bottom = 1\n"

    s = Scene(tmp_path, {SHARED: region("base")}, {SHARED: region("pr")}, {SHARED: region("main")})
    head = s.merge({SHARED: region("pr")})
    got = s.check(head)
    assert got["answer"] == "judgement" and tokens(got) == [HC.WHY_CONFLICT_FIX], got
    assert len(got["hunks"]) == 1, got["hunks"]
    hunk = got["hunks"][0]
    assert hunk["header"] == "@@ -1,42 +1,14 @@", hunk
    lines = hunk["text"].splitlines()
    for marker in ("-<<<<<<< ours", "-||||||| base", "-=======", "->>>>>>> theirs"):
        assert marker in lines, hunk
    assert " value_pr_0 = 0" in lines and " value_pr_11 = 11" in lines and "-value_main_0 = 0" in lines
    assert not [line for line in lines if line.startswith("+") and not line.startswith("+++")], hunk


# --- E-cf-onesided ----------------------------------------------------------------------------------------------------------------------------


def test_e_cf_onesided_a_resolution_that_takes_the_bases_side_lists_the_line_it_drops(tmp_path):
    s = Shape(tmp_path)
    head = s.head(text=MAIN_FUNC)
    got = run_check(s.repo, s.base, s.record, head)
    assert got["answer"] == "judgement" and tokens(got) == [HC.WHY_CONFLICT_FIX], got
    dropped = "-" + func_lines(PR_FUNC)[3]
    assert len(got["hunks"]) == 1 and dropped in got["hunks"][0]["text"].splitlines(keepends=True), got["hunks"]


def test_e_cf_onesided_a_resolution_that_takes_the_pull_requests_side_lists_the_line_it_drops(tmp_path):
    s = Shape(tmp_path)
    head = s.head(text=PR_FUNC)
    got = run_check(s.repo, s.base, s.record, head)
    assert got["answer"] == "judgement" and tokens(got) == [HC.WHY_CONFLICT_FIX], got
    dropped = "-" + func_lines(MAIN_FUNC)[3]
    assert len(got["hunks"]) == 1 and dropped in got["hunks"][0]["text"].splitlines(keepends=True), got["hunks"]


# --- E-cf-none --------------------------------------------------------------------------------------------------------------------------------


def test_e_cf_none_a_clean_catch_up_stays_proven_and_a_merge_with_no_hand_made_line_lists_nothing(tmp_path):
    lines = func_lines(TR.numbered("clean", 30))
    pr_clean = "".join(lines[:4] + ["pr_clean = 1\n"] + lines[5:])
    main_clean = "".join(lines[:24] + ["main_clean = 1\n"] + lines[25:])
    s = Scene(tmp_path, {CLEAN_PY: "".join(lines)}, {CLEAN_PY: pr_clean}, {CLEAN_PY: main_clean})
    head = s.merge({}, conflict=False)
    got = s.check(head)
    assert got["answer"] == "proven" and tokens(got) == [HC.WHY_OWN_CHANGE_UNCHANGED] and got["hunks"] == [], got
    run = R.production_git(s.repo.root)
    commits = HC._authors(run, s.base, s.x, head)
    assert [c["sha"] for c in commits] == [head]
    assert HC._conflict_fix(run, s.base, s.x, head, [CLEAN_PY], commits) == []


# --- E-cf-rename ------------------------------------------------------------------------------------------------------------------------------


OLD_PY, CORE_PY, NEW_PY = "src/old.py", "src/core.py", "src/new.py"


def test_e_cf_rename_a_reviewed_rename_whose_destination_a_copy_proof_settles_keeps_needs_review(tmp_path, monkeypatch):
    repo = TR.Repo(tmp_path)
    repo.write(SHARED, BASE_FUNC)
    repo.write(OLD_PY, TR.numbered("old", 30))
    repo.commit("fork files")
    repo.git("branch", "-f", "main", "pr")
    repo.git("mv", OLD_PY, CORE_PY)
    _, certified, record = TR.returning(repo, first={SHARED: PR_FUNC})
    base = repo.main_commit(SHARED, MAIN_FUNC)
    conflict_merge(repo)
    repo.write(SHARED, RESOLVED)
    updated = repo.read(CORE_PY) + "core_extra = 1\n"
    repo.write(CORE_PY, updated)
    head = repo.commit("merge main and update the core module from upstream")
    proof = [{"file": CORE_PY, "source": "upstream/core.py", "sha256": hashlib.sha256(updated.encode()).hexdigest()}]
    got = fails_closed(monkeypatch, repo, base, record, head, proof=proof)
    assert [c["file"] for c in got["copies"]] == [CORE_PY] and got["files"] == [SHARED], got
    assert got["certified"] == certified


def test_e_cf_rename_a_rename_made_in_the_merge_of_a_file_the_pull_request_changed_keeps_needs_review(tmp_path, monkeypatch):
    s = Scene(tmp_path, {SHARED: BASE_FUNC, OLD_PY: TR.numbered("old", 30)},
              {SHARED: PR_FUNC, OLD_PY: TR.numbered("old", 30).replace("value_old_5 = 5", "value_old_5 = 55")}, {SHARED: MAIN_FUNC})
    conflict_merge(s.repo)
    s.repo.write(SHARED, RESOLVED)
    s.repo.git("mv", OLD_PY, NEW_PY)
    head = s.repo.commit("merge main and rename the old module")
    got = fails_closed(monkeypatch, s.repo, s.base, s.record, head)
    assert NEW_PY in got["files"] and SHARED in got["files"], got


# --- the carry check and the CLI ----------------------------------------------------------------------------------------------------------


def test_the_carry_check_from_the_sheets_commit_reads_judgement_for_a_conflict_fix(tmp_path):
    repo, x, s, base, probe, head, record, carry_record = two_anchor(tmp_path, RESOLVED)
    builder = "t@example.com"
    carry = run_check(repo, base, carry_record, head, builder_author=builder)
    assert carry["answer"] == "judgement" and tokens(carry) == [HC.WHY_CONFLICT_FIX], carry
    assert carry["certified"] == s and [c["sha"] for c in carry["commits"]] == [head]
    coverage = run_check(repo, base, record, head, builder_author=builder)
    assert coverage["answer"] == "judgement" and tokens(coverage) == [HC.WHY_CONFLICT_FIX], coverage
    assert [c["sha"] for c in coverage["commits"]] == [head, s]
    moved = HC.outcome(coverage["answer"], "green", judged_clear=True, sheet="live", sheet_commit=s, head=head,
                       carry_answer=carry["answer"], carry_judged_clear=True)
    assert moved == {"outcome": "READY", "why": "covered", "review": "none", "sheet": "republish-carried"}
    not_cleared = HC.outcome(coverage["answer"], "green", sheet="live", sheet_commit=s, head=head, carry_answer=carry["answer"])
    assert not_cleared["outcome"] == "NOT-READY" and not_cleared["sheet"] == "take-down"


def test_the_cli_prints_judgement_and_the_conflict_fix_token(tmp_path):
    s = Shape(tmp_path / "shape")
    head = s.head()
    record = tmp_path / "record.json"
    record.write_text(json.dumps(s.record), encoding="utf-8")
    argv = [sys.executable, _SCRIPT, "check", "--repo-root", s.repo.root, "--base", s.base, "--record", str(record), "--head", head]
    done = subprocess.run(argv, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    printed = json.loads(done.stdout)
    assert printed["answer"] == "judgement" and [w.split(":", 1)[0] for w in printed["why"]] == ["conflict-fix"], printed
    assert printed["hunks"][0]["kind"] == "conflict-fix" and printed["files"] == [SHARED]
    assert set(printed) == {"answer", "why", "certified", "head", "base", "files", "reconstructed", "copies", "hunks", "commits"}


def test_the_conflict_fix_name_is_exported():
    assert HC.WHY_CONFLICT_FIX == "conflict-fix" and HC.WHY_CONFLICT_FIX in HC.WHY_TOKENS
    assert HC.KIND_CONFLICT_FIX == "conflict-fix"
