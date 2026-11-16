# plugins/superheroes/lib/tests/test_head_coverage_2496.py
"""Issue 2496 (WO-A): the one head-coverage check and the pure outcome function, on real repositories.

One test per row 1 to 16 of the permutation table of the issue (rows 12, 13, 15 and 16 pin the outcome and the sheet
action; the others pin the check's answer and the outcome it leads to), and the fail-closed edges:

E1  any git failure, unreadable or malformed record, short sha or exception reads needs-review, never proven or judgement;
E2  a judgement answer needs the content rule and the author rule both;
E3  a proof entry counts only when git re-validates it at the head;
E4  the stricter rule of ``returning_review.decide`` is unchanged by the reconstruction proof.

Bite-proof record: i2496_wo_a_head_coverage
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
from test_returning_review_c1l11 import _isolated_git  # noqa: E402,F401  (autouse: no global git config)

_SCRIPT = os.path.join(_LIB, "head_coverage.py")
SHARED = "src/shared.py"
APP = "src/app.py"
KEYS = {"answer", "why", "certified", "head", "base", "files", "reconstructed", "copies", "hunks", "commits"}
OTHER = "--author=Other <other@example.com>"


def run_check(repo, base, record, head=None, **kwargs):
    """``head_coverage.check`` over ``repo``, with the result's shape asserted every time."""
    head = repo.git("rev-parse", "HEAD") if head is None else head
    got = HC.check(repo.root, base, record, head, **kwargs)
    assert set(got) == KEYS and got["answer"] in HC.ANSWERS and got["why"], got
    assert all(w.split(":", 1)[0] in HC.WHY_TOKENS for w in got["why"]), got
    return got


def tokens(got):
    return [w.split(":", 1)[0] for w in got["why"]]


def commit_by_other(repo, message="other pushes"):
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", message, OTHER)
    return repo.git("rev-parse", "HEAD")


def pr_edit_text(marker="pr_edit = 1\n"):
    lines = TR.numbered("shared", 30).splitlines(keepends=True)
    lines[25] = marker
    return "".join(lines)


def sha256_of(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- row 1: nothing happened --------------------------------------------------------------------


def test_row_1_the_head_is_the_certified_commit_reads_proven(tmp_path):
    repo = TR.Repo(tmp_path)
    base, reviewed, earlier = TR.returning(repo)
    got = run_check(repo, base, earlier)
    assert got["answer"] == "proven" and tokens(got) == [HC.WHY_SAME_COMMIT]
    assert got["certified"] == reviewed and got["head"] == reviewed and got["files"] == []
    assert HC.outcome(got["answer"], "green") == {"outcome": "READY", "why": "covered", "review": "none", "sheet": "none"}


# --- row 2: brought up to date with main, no conflict ---------------------------------------------


def test_row_2_a_clean_catch_up_with_main_reads_proven(tmp_path):
    repo = TR.Repo(tmp_path)
    base, reviewed, earlier = TR.returning(repo)
    moved = repo.main_commit("docs/other.md", "other\n")
    head = repo.merge_main()
    got = run_check(repo, moved, earlier, head)
    assert got["answer"] == "proven" and tokens(got) == [HC.WHY_OWN_CHANGE_UNCHANGED]
    assert got["certified"] == reviewed and got["files"] == [] and got["reconstructed"] == [] and got["copies"] == []
    assert HC.outcome(got["answer"], "green")["outcome"] == "READY"


def test_a_clean_base_update_inside_the_hunk_context_reads_proven_by_reconstruction_but_decide_still_names_the_file(tmp_path):
    # the check's reconstruction proof is its own; the decider's stricter rule is untouched (E4)
    repo = TR.Repo(tmp_path)
    base, reviewed, earlier = TR.returning(repo, first={SHARED: pr_edit_text()})
    moved = repo.main_commit(SHARED, TR.numbered("shared", 30).replace("value_shared_28 = 28", "value_shared_28 = 280"))
    head = repo.merge_main()
    got = run_check(repo, moved, earlier, head)
    assert got["answer"] == "proven" and got["reconstructed"] == [SHARED] and got["files"] == []
    assert tokens(got) == [HC.WHY_OWN_CHANGE_UNCHANGED]
    decided = TR.decide(repo, moved, earlier)
    assert decided["changedFiles"] == [SHARED], decided


# --- row 3: conflicts resolved by hand --------------------------------------------------------------


def _conflicted_catch_up(repo, resolved):
    """The pull request edited line 26 of the shared file; main edited the same line; the merge is resolved by hand."""
    moved = repo.main_commit(SHARED, pr_edit_text("main_edit = 1\n"))
    argv = ["git", "-C", repo.root, "-c", "user.name=T", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false",
            "merge", "--no-ff", "-m", "catch up", "main"]
    proc = subprocess.run(argv, capture_output=True, text=True)
    assert proc.returncode != 0, "the fixture needs a real conflict"
    repo.write(SHARED, resolved)
    return moved, repo.commit("resolve by hand")


def test_row_3_a_hand_resolved_conflict_reads_needs_review(tmp_path):
    # axis: a file is reconstructed only when the three-way merge reproduces the head blob, so a hand resolution stays changed — see bite-proof record i2496_wo_a_head_coverage (E-recon)
    repo = TR.Repo(tmp_path)
    base, reviewed, earlier = TR.returning(repo, first={SHARED: pr_edit_text()})
    moved, head = _conflicted_catch_up(repo, pr_edit_text("resolved = 1\n"))
    got = run_check(repo, moved, earlier, head)
    assert got["answer"] == "needs-review" and got["files"] == [SHARED] and got["reconstructed"] == []
    assert tokens(got) == [HC.WHY_BEHAVIOUR_CHANGE] and got["hunks"] == []
    assert HC.outcome(got["answer"], "green") == {"outcome": "NOT-READY", "why": "needs-review", "review": "returning", "sheet": "none"}


# --- row 4: a stack, the layer below changed and was merged up -----------------------------------------


def test_row_4_the_lower_layer_merged_up_reads_proven_on_this_layers_own_diff(tmp_path):
    repo = TR.Repo(tmp_path)
    repo.git("checkout", "-q", "-b", "lower", "main")
    repo.write("src/lower.py", TR.numbered("lower", 5))
    repo.commit("lower layer")
    repo.git("checkout", "-q", "pr")
    repo.git("merge", "-q", "--ff-only", "lower")
    _, reviewed, earlier = TR.returning(repo, first={SHARED: pr_edit_text()})
    repo.git("checkout", "-q", "lower")
    repo.write("src/lower.py", TR.numbered("lower", 5) + "more = 1\n")
    repo.write(SHARED, TR.numbered("shared", 30).replace("value_shared_28 = 28", "value_shared_28 = 280"))
    lower_tip = repo.commit("lower layer changes")
    repo.git("checkout", "-q", "pr")
    repo.git("merge", "-q", "--no-ff", "-m", "merge the lower layer up", "lower")
    got = run_check(repo, lower_tip, earlier)
    assert got["answer"] == "proven" and got["files"] == [] and got["reconstructed"] == [SHARED]
    assert "src/lower.py" not in got["files"] + got["reconstructed"]
    assert HC.outcome(got["answer"], "green")["outcome"] == "READY"


# --- row 5: rebased or force-pushed, the diff the same ----------------------------------------------------


def test_row_5_a_rebase_with_the_same_diff_reads_proven(tmp_path):
    repo = TR.Repo(tmp_path)
    _, reviewed, earlier = TR.returning(repo)
    moved = repo.main_commit("docs/other.md", "other\n")
    repo.git("rebase", "-q", "main")
    head = repo.git("rev-parse", "HEAD")
    assert head != reviewed
    assert subprocess.run(["git", "-C", repo.root, "merge-base", "--is-ancestor", reviewed, head]).returncode != 0
    got = run_check(repo, moved, earlier, head)
    assert got["answer"] == "proven" and tokens(got) == [HC.WHY_OWN_CHANGE_UNCHANGED] and got["files"] == []
    assert HC.outcome(got["answer"], "green")["outcome"] == "READY"


# --- row 6: rebased or force-pushed, the diff changed ---------------------------------------------------------


def test_row_6_a_rebase_that_changed_the_diff_reads_needs_review(tmp_path):
    repo = TR.Repo(tmp_path)
    _, reviewed, earlier = TR.returning(repo)
    moved = repo.main_commit("docs/other.md", "other\n")
    repo.git("rebase", "-q", "main")
    repo.write(APP, repo.read(APP).replace("value_app_5 = 5", "value_app_5 = 50"))
    repo.git("add", "-A")
    repo.git("commit", "-q", "--amend", "-m", "rewritten")
    got = run_check(repo, moved, earlier)
    assert got["answer"] == "needs-review" and got["files"] == [APP] and tokens(got) == [HC.WHY_BEHAVIOUR_CHANGE]
    assert HC.outcome(got["answer"], "green")["review"] == "returning"


# --- row 7: the builder touched only docs or comments ---------------------------------------------------------


def test_row_7_a_builder_commit_touching_only_docs_reads_judgement_with_its_hunks(tmp_path):
    repo = TR.Repo(tmp_path)
    base, reviewed, earlier = TR.returning(repo, first={APP: TR.numbered("app", 100), "docs/notes.md": "notes\n"})
    repo.write("docs/notes.md", "notes\nmore notes\n")
    head = repo.commit("docs")
    got = run_check(repo, base, earlier, head)
    assert got["answer"] == "judgement" and tokens(got) == [HC.WHY_PROSE_OR_COMMENTS]
    assert got["files"] == ["docs/notes.md"] and len(got["hunks"]) == 1
    assert got["hunks"][0]["file"] == "docs/notes.md" and got["hunks"][0]["header"].startswith("@@ ")
    assert got["commits"] == [{"sha": head, "author": "t@example.com"}]
    assert HC.outcome(got["answer"], "green", judged_clear=True)["outcome"] == "READY"
    unclear = HC.outcome(got["answer"], "green")
    assert unclear == {"outcome": "NOT-READY", "why": "judged-meaningful", "review": "returning", "sheet": "none"}


def test_a_comment_only_python_change_by_the_builder_reads_judgement(tmp_path):
    repo = TR.Repo(tmp_path)
    base, reviewed, earlier = TR.returning(repo)
    repo.write(APP, repo.read(APP) + "\n# a note about the table above\n")
    repo.commit("a comment")
    got = run_check(repo, base, earlier)
    assert got["answer"] == "judgement" and got["files"] == [APP] and got["hunks"][0]["file"] == APP


# --- row 8: a test's expected values, a fixture, config or CI ----------------------------------------------------


def test_row_8_a_builder_commit_changing_ci_config_reads_needs_review(tmp_path):
    repo = TR.Repo(tmp_path)
    ci = ".github/workflows/ci.yml"
    base, reviewed, earlier = TR.returning(repo, first={APP: TR.numbered("app", 100), ci: "steps:\n  - run: pytest\n"})
    repo.write(ci, "steps:\n  - run: pytest -k fast\n")
    repo.commit("narrow the CI run")
    got = run_check(repo, base, earlier)
    assert got["answer"] == "needs-review" and got["files"] == [ci] and tokens(got) == [HC.WHY_BEHAVIOUR_CHANGE]
    assert HC.outcome(got["answer"], "green")["outcome"] == "NOT-READY"


def test_a_changed_test_assertion_reads_needs_review(tmp_path):
    # axis: a non-prose file qualifies for judgement only by blank and comment lines — see bite-proof record i2496_wo_a_head_coverage (E-judge)
    repo = TR.Repo(tmp_path)
    test_file = "tests/test_app.py"
    base, reviewed, earlier = TR.returning(repo, first={test_file: "def test_f():\n    assert f() == 1\n"})
    repo.write(test_file, "def test_f():\n    assert f() == 2\n")
    repo.commit("fix the expected value")
    got = run_check(repo, base, earlier)
    assert got["answer"] == "needs-review" and got["hunks"] == [] and tokens(got) == [HC.WHY_BEHAVIOUR_CHANGE]


# --- row 9: product code ---------------------------------------------------------------------------------------


def test_row_9_a_builder_commit_with_product_code_reads_needs_review(tmp_path):
    repo = TR.Repo(tmp_path)
    base, reviewed, earlier = TR.returning(repo)
    repo.write(APP, repo.read(APP) + "def added():\n    return 1\n")
    repo.commit("add code")
    got = run_check(repo, base, earlier)
    assert got["answer"] == "needs-review" and got["files"] == [APP] and tokens(got) == [HC.WHY_BEHAVIOUR_CHANGE]
    assert HC.outcome(got["answer"], "green") == {"outcome": "NOT-READY", "why": "needs-review", "review": "returning",
                                                  "sheet": "none"}


# --- rows 10 and 11: copies, and regenerated files ------------------------------------------------------------


def _entry(repo, rel, text=None, source="upstream/lib.py"):
    return {"file": rel, "source": source, "sha256": sha256_of(repo.read(rel) if text is None else text)}


def test_row_10_a_file_copied_byte_for_byte_with_a_checksum_reads_proven(tmp_path):
    repo = TR.Repo(tmp_path)
    base, reviewed, earlier = TR.returning(repo)
    repo.write("vendor/lib.py", TR.numbered("vendored", 40))
    repo.commit("vendor a copy")
    entry = _entry(repo, "vendor/lib.py")
    got = run_check(repo, base, earlier, proof=[entry])
    assert got["answer"] == "proven" and tokens(got) == [HC.WHY_PROVEN_COPIES]
    assert got["copies"] == [entry] and got["files"] == []
    assert HC.outcome(got["answer"], "green")["outcome"] == "READY"
    without = run_check(repo, base, earlier)
    assert without["answer"] == "needs-review" and without["copies"] == []


def test_row_11_a_regenerated_file_is_proven_only_by_the_vets_own_rerun_entry(tmp_path):
    repo = TR.Repo(tmp_path)
    gen = "gen/table.json"
    base, reviewed, earlier = TR.returning(repo, first={APP: TR.numbered("app", 100), gen: '{"v": 1}\n'})
    repo.write(gen, '{"v": 2}\n')
    repo.commit("regenerate")
    rerun = _entry(repo, gen, source="re-run of the generator")
    got = run_check(repo, base, earlier, proof=[rerun])
    assert got["answer"] == "proven" and got["copies"] == [rerun] and got["files"] == []
    differs = run_check(repo, base, earlier, proof=[_entry(repo, gen, text='{"v": 3}\n', source="re-run of the generator")])
    assert differs["answer"] == "needs-review" and differs["files"] == [gen] and differs["copies"] == []
    assert HC.outcome(differs["answer"], "green")["review"] == "returning"


def test_a_proof_entry_whose_sha256_does_not_match_the_head_blob_proves_nothing(tmp_path):
    # axis: a proof entry counts only when git re-validates it at the head — see bite-proof record i2496_wo_a_head_coverage (E-copy)
    repo = TR.Repo(tmp_path)
    base, reviewed, earlier = TR.returning(repo)
    repo.write("vendor/lib.py", TR.numbered("vendored", 40))
    repo.commit("vendor a copy")
    liar = {"file": "vendor/lib.py", "source": "upstream/lib.py", "sha256": "0" * 64}
    got = run_check(repo, base, earlier, proof=[liar])
    assert got["answer"] == "needs-review" and got["copies"] == [] and got["files"] == ["vendor/lib.py"]


# --- rows 12 and 13: CI on the head ---------------------------------------------------------------------------------


def test_row_12_ci_still_running_on_the_head_waits_with_no_sheet():
    for ci in ("pending", "none"):
        assert HC.outcome("proven", ci) == {"outcome": "WAIT", "why": "ci-not-green", "review": "none", "sheet": "none"}
    assert HC.outcome("judgement", "pending", judged_clear=True)["outcome"] == "WAIT"
    assert HC.outcome("proven", "pending", sheet="held")["sheet"] == "keep"
    assert HC.outcome("proven", "pending", sheet="live", sheet_commit="a" * 40, head="a" * 40)["sheet"] == "keep"
    # an uncovered head is owed a review whatever CI is doing
    assert HC.outcome("needs-review", "pending")["outcome"] == "NOT-READY"


def test_row_13_ci_red_on_the_head_is_not_ready_and_owes_no_review():
    for answer in HC.ANSWERS:
        got = HC.outcome(answer, "red", judged_clear=True)
        assert got == {"outcome": "NOT-READY", "why": "ci-red", "review": "none", "sheet": "none"}
    assert HC.outcome("proven", "red", sheet="live", sheet_commit="a" * 40, head="a" * 40)["sheet"] == "take-down"
    assert HC.outcome("proven", "red", sheet="held")["sheet"] == "keep"


# --- row 14: someone other than the builder pushes ---------------------------------------------------------------------


def test_row_14_a_push_by_someone_else_reads_needs_review(tmp_path):
    repo = TR.Repo(tmp_path)
    base, reviewed, earlier = TR.returning(repo)
    repo.write(APP, repo.read(APP) + "def added():\n    return 1\n")
    other = commit_by_other(repo)
    got = run_check(repo, base, earlier)
    assert got["answer"] == "needs-review" and got["files"] == [APP]
    assert tokens(got) == [HC.WHY_OTHER_AUTHOR, HC.WHY_BEHAVIOUR_CHANGE]
    assert got["commits"] == [{"sha": other, "author": "other@example.com"}]
    assert HC.outcome(got["answer"], "green")["outcome"] == "NOT-READY"


def test_a_commit_by_another_author_that_only_edits_markdown_reads_needs_review(tmp_path):
    # axis: a judgement answer needs every new commit to be the builder's — see bite-proof record i2496_wo_a_head_coverage (E-author)
    repo = TR.Repo(tmp_path)
    base, reviewed, earlier = TR.returning(repo, first={APP: TR.numbered("app", 100), "docs/notes.md": "notes\n"})
    repo.write("docs/notes.md", "notes\nmore notes\n")
    commit_by_other(repo, "docs by someone else")
    got = run_check(repo, base, earlier)
    assert got["answer"] == "needs-review" and tokens(got) == [HC.WHY_OTHER_AUTHOR] and got["hunks"] == []
    # the builder named by the caller is the one the commits are judged against
    named = run_check(repo, base, earlier, builder_author="t@example.com")
    assert named["answer"] == "needs-review" and tokens(named) == [HC.WHY_OTHER_AUTHOR]
    named_other = run_check(repo, base, earlier, builder_author="OTHER@example.com")
    assert named_other["answer"] == "judgement" and tokens(named_other) == [HC.WHY_PROSE_OR_COMMENTS]


def test_authors_git_cannot_read_read_needs_review(tmp_path):
    repo = TR.Repo(tmp_path)
    base, reviewed, earlier = TR.returning(repo, first={APP: TR.numbered("app", 100), "docs/notes.md": "notes\n"})
    repo.write("docs/notes.md", "notes\nmore notes\n")
    repo.commit("docs")
    real = R.production_git(repo.root)

    def no_rev_list(argv):
        return (128, "") if argv[0] == "rev-list" else real(argv)

    got = run_check(repo, base, earlier, git=no_rev_list)
    assert got["answer"] == "needs-review" and tokens(got) == [HC.WHY_OTHER_AUTHOR] and got["commits"] == []


# --- rows 15 and 16: the head moves after the sheet was published ----------------------------------------------------


def test_row_15_a_head_that_moves_without_changing_what_the_owner_approved_republishes_carried(tmp_path):
    repo = TR.Repo(tmp_path)
    base, reviewed, earlier = TR.returning(repo)
    moved = repo.main_commit("docs/other.md", "other\n")
    head = repo.merge_main()
    got = run_check(repo, moved, earlier, head)
    assert got["answer"] == "proven"
    moved_on = HC.outcome(got["answer"], "green", sheet="live", sheet_commit=reviewed, head=head)
    assert moved_on == {"outcome": "READY", "why": "covered", "review": "none", "sheet": "republish-carried"}
    assert HC.outcome(got["answer"], "green", sheet="live", sheet_commit=head, head=head)["sheet"] == "keep"
    judged = HC.outcome("judgement", "green", judged_clear=True, sheet="live", sheet_commit=reviewed, head=head)
    assert judged["sheet"] == "republish-carried"


def test_row_16_a_head_that_moves_and_matters_takes_the_sheet_down_and_republishes_it_unsigned_when_ready_again(tmp_path):
    repo = TR.Repo(tmp_path)
    base, reviewed, earlier = TR.returning(repo)
    repo.write(APP, repo.read(APP) + "def added():\n    return 1\n")
    head = repo.commit("add code")
    got = run_check(repo, base, earlier, head)
    assert got["answer"] == "needs-review"
    down = HC.outcome(got["answer"], "green", sheet="live", sheet_commit=reviewed, head=head)
    assert down == {"outcome": "NOT-READY", "why": "needs-review", "review": "returning", "sheet": "take-down"}
    assert HC.outcome("judgement", "green", sheet="live", sheet_commit=reviewed, head=head)["sheet"] == "take-down"
    back = HC.outcome("proven", "green", sheet="held", sheet_commit=reviewed, head=head)
    assert back == {"outcome": "READY", "why": "covered", "review": "none", "sheet": "republish-unsigned"}
    assert HC.outcome("needs-review", "green", sheet="held")["sheet"] == "keep"


def test_outcome_rejects_values_outside_its_sets():
    for kwargs in ({"answer": "maybe", "ci": "green"}, {"answer": "proven", "ci": "yellow"},
                   {"answer": "proven", "ci": "green", "sheet": "gone"}):
        with pytest.raises(ValueError):
            HC.outcome(**kwargs)


# --- E1: every failure to read anything reads needs-review ----------------------------------------------------------------


@pytest.mark.parametrize("record", [
    None, [], "x", {}, {"ok": False, "reason": "review-record-missing"}, {"ok": "yes"},
    {"ok": True, "finalCommit": {"sha": "abc1234"}}, {"ok": True, "finalCommit": "x" * 40}, {"ok": True},
], ids=["none", "list", "string", "empty", "not-ok", "ok-not-true", "short-sha", "final-not-dict", "no-final"])
def test_a_malformed_record_reads_needs_review(tmp_path, record):
    repo = TR.Repo(tmp_path)
    base, reviewed, _ = TR.returning(repo)
    got = run_check(repo, base, record)
    assert got["answer"] == "needs-review" and tokens(got) == [HC.WHY_RECORD_UNUSABLE] and got["certified"] is None


@pytest.mark.parametrize("ok", [False, "yes", 1], ids=["false", "string", "one"])
def test_a_record_whose_ok_is_not_true_reads_needs_review_even_with_a_valid_final_commit(tmp_path, ok):
    # axis: only ok true certifies; a record that names a valid final commit but is not ok certifies nothing
    repo = TR.Repo(tmp_path)
    base, reviewed, earlier = TR.returning(repo)
    got = HC.check(repo.root, base, dict(earlier, ok=ok), reviewed)
    assert got["answer"] == "needs-review" and tokens(got) == [HC.WHY_RECORD_UNUSABLE] and got["certified"] is None


def test_an_abandoned_record_reads_needs_review_even_at_its_own_commit(tmp_path):
    repo = TR.Repo(tmp_path)
    base, reviewed, earlier = TR.returning(repo)
    got = run_check(repo, base, dict(earlier, abandoned={"reason": "closed"}))
    assert got["answer"] == "needs-review" and tokens(got) == [HC.WHY_RECORD_UNUSABLE]


@pytest.mark.parametrize("head", ["not-a-sha", "abc1234", "", None, 12345, ["x"]], ids=repr)
def test_a_garbage_head_reads_needs_review(tmp_path, head):
    repo = TR.Repo(tmp_path)
    base, reviewed, earlier = TR.returning(repo)
    got = HC.check(repo.root, base, earlier, head)
    assert set(got) == KEYS and got["answer"] == "needs-review" and tokens(got) == [HC.WHY_INPUT_INVALID]
    short_base = HC.check(repo.root, "abc1234", earlier, repo.git("rev-parse", "main"))
    assert short_base["answer"] == "needs-review" and tokens(short_base) == [HC.WHY_INPUT_INVALID]


def test_a_git_that_cannot_produce_the_diffs_reads_needs_review(tmp_path):
    repo = TR.Repo(tmp_path)
    base, reviewed, earlier = TR.returning(repo)
    head = repo.git("rev-parse", "main")
    got = HC.check(repo.root, base, earlier, head, git=lambda argv: (128, ""))
    assert got["answer"] == "needs-review" and tokens(got) == [HC.WHY_DIFF_UNREADABLE]
    missing = HC.check(repo.root, base, earlier, "f" * 40)
    assert missing["answer"] == "needs-review" and tokens(missing) == [HC.WHY_DIFF_UNREADABLE]


def test_an_exception_anywhere_in_the_check_reads_needs_review(tmp_path):
    # axis: the check never raises; a fault of any kind reads needs-review — see bite-proof record i2496_wo_a_head_coverage (E-fail)
    repo = TR.Repo(tmp_path)
    base, reviewed, earlier = TR.returning(repo)
    head = repo.git("rev-parse", "main")

    def exploding(argv):
        raise RuntimeError("git blew up")

    got = HC.check(repo.root, base, earlier, head, git=exploding)
    assert set(got) == KEYS and got["answer"] == "needs-review" and tokens(got) == [HC.WHY_CHECK_FAILED]
    assert "RuntimeError" in got["why"][0] and "git blew up" in got["why"][0] and got["hunks"] == []


# --- the CLI -----------------------------------------------------------------------------------------------------------


def _cli(*argv):
    return subprocess.run([sys.executable, _SCRIPT, *argv], capture_output=True, text=True)


def test_the_cli_exits_0_for_an_answer_and_2_for_a_usage_error(tmp_path):
    repo = TR.Repo(tmp_path)
    base, reviewed, earlier = TR.returning(repo)
    repo.write(APP, repo.read(APP) + "def added():\n    return 1\n")
    head = repo.commit("add code")
    record = tmp_path / "record.json"
    record.write_text(json.dumps(earlier), encoding="utf-8")
    proc = _cli("check", "--repo-root", repo.root, "--base", base, "--record", str(record), "--head", head)
    assert proc.returncode == 0, proc.stderr
    printed = json.loads(proc.stdout)
    assert set(printed) == KEYS and printed["answer"] == "needs-review" and printed["files"] == [APP]
    same = _cli("check", "--repo-root", repo.root, "--base", base, "--record", str(record), "--head", reviewed)
    assert same.returncode == 0 and json.loads(same.stdout)["answer"] == "proven"
    ok = _cli("outcome", "--answer", "proven", "--ci", "green", "--sheet", "live", "--sheet-commit", reviewed, "--head", head)
    assert ok.returncode == 0 and json.loads(ok.stdout)["sheet"] == "republish-carried"
    cleared = _cli("outcome", "--answer", "judgement", "--ci", "green", "--judged-clear")
    assert cleared.returncode == 0 and json.loads(cleared.stdout)["outcome"] == "READY"
    bad_ci = _cli("outcome", "--answer", "proven", "--ci", "bogus")
    assert bad_ci.returncode == 2 and bad_ci.stdout == ""
    assert _cli("outcome", "--answer", "proven", "--ci", "green", "--sheet", "bogus").returncode == 2
    assert _cli("outcome", "--answer", "bogus", "--ci", "green").returncode == 2
    unreadable = _cli("check", "--repo-root", repo.root, "--base", base, "--record", str(tmp_path / "missing.json"), "--head", head)
    assert unreadable.returncode == 2
    no_proof = _cli("check", "--repo-root", repo.root, "--base", base, "--record", str(record), "--head", head,
                    "--proof", str(tmp_path / "missing-proof.json"))
    assert no_proof.returncode == 2
    garbage = _cli("check", "--repo-root", repo.root, "--base", base, "--record", str(record), "--head", "garbage")
    assert garbage.returncode == 0 and json.loads(garbage.stdout)["answer"] == "needs-review"


def test_the_cli_reads_a_proof_file_in_the_copy_proof_schema(tmp_path):
    repo = TR.Repo(tmp_path)
    base, reviewed, earlier = TR.returning(repo)
    repo.write("vendor/lib.py", TR.numbered("vendored", 40))
    head = repo.commit("vendor a copy")
    record = tmp_path / "record.json"
    record.write_text(json.dumps(earlier), encoding="utf-8")
    proof = tmp_path / "proof.json"
    proof.write_text(json.dumps({"schema": "copy-proof/1", "copies": [_entry(repo, "vendor/lib.py")]}), encoding="utf-8")
    proc = _cli("check", "--repo-root", repo.root, "--base", base, "--record", str(record), "--head", head,
                "--proof", str(proof))
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["answer"] == "proven"
