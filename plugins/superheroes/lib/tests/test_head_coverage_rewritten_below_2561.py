# plugins/superheroes/lib/tests/test_head_coverage_rewritten_below_2561.py
"""Issue 2561 (WO-A): the head-coverage check proves a stack layer after the layer below it is rewritten.

The layer below is rebuilt on a new commit with the same tree (``git commit-tree <old>^{tree} -p <parent>``). The caller
gives ``base_at_review``, the layer below's old heads; the check reads the reviewed change against one only when git
shows its tree equals the base's. Edges: no value is today's check; a non-sha value reads needs-review; an object-less,
another-tree, unreadable or merge-base-less full-sha value is ignored, so the answer is the check's own without it plus
one ``base-at-review-ignored`` line; an unusable record or a head that is X is unchanged.

Bite-proof record: i2561_head_coverage_rewritten_below
"""
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
NO_OBJECT = "0123456789abcdef0123456789abcdef01234567"
LIVE = {"outcome": "READY", "why": "covered", "review": "none", "sheet": "republish-carried"}


def run_check(repo, base, record, head, **kwargs):
    """``head_coverage.check`` over ``repo``, with the result's shape asserted every time."""
    got = HC.check(repo.root, base, record, head, **kwargs)
    assert set(got) == KEYS and got["answer"] in HC.ANSWERS and got["why"], got
    assert all(w.split(":", 1)[0] in HC.WHY_TOKENS for w in got["why"]), got
    return got


def tokens(got):
    return [w.split(":", 1)[0] for w in got["why"]]


def shared_text(*layers, upper="upper"):
    """The shared file with the lower layer's lines 10 to 12 and the upper layer's lines 11 to 13 (they overlap)."""
    lines = TR.numbered("shared", 30).splitlines(keepends=True)
    for i in (10, 11, 12) if "lower" in layers else ():
        lines[i] = "lower_%d = 1\n" % i
    for i in (11, 12, 13) if "upper" in layers else ():
        lines[i] = "%s_%d = 2\n" % (upper, i)
    return "".join(lines)


def stack(repo):
    """``lower`` off ``main``, ``upper`` off ``lower``, both editing the shared file; returns ``(main, lower, x)``."""
    repo.git("checkout", "-q", "-b", "lower", "main")
    repo.write(SHARED, shared_text("lower"))
    lower = repo.commit("lower layer")
    repo.git("checkout", "-q", "-b", "upper", "lower")
    repo.write(SHARED, shared_text("lower", "upper"))
    return repo.git("rev-parse", "main"), lower, repo.commit("upper layer")


def rebuild(repo, old, parent, message="straighten"):
    """The merge train's rewrite: ``old``'s tree on ``parent``, on no branch."""
    return repo.git("commit-tree", old + "^{tree}", "-p", parent, "-m", message)


def straightened(repo):
    main, lower, x = stack(repo)
    b1 = rebuild(repo, lower, main)
    return {"main": main, "lower": lower, "x": x, "b1": b1, "h1": rebuild(repo, x, b1)}


def seam(repo, fails):
    real = R.production_git(repo.root)
    return lambda argv: (1, "") if fails(argv) else real(argv)


def app_text(edited=False):
    text = TR.numbered("app", 30)
    return text.replace("value_app_3 = 3", "lower_3 = 1") if edited else text


def upper_shared():
    return TR.numbered("shared", 30).replace("value_shared_20 = 20", "upper_20 = 2")


def layers(repo):
    """``main`` holds the shared and the app file; ``lower`` edits the app file, ``upper`` (on ``lower``) edits the shared
    file; returns ``(main, lower, x)``."""
    repo.git("checkout", "-q", "main")
    repo.write(APP, app_text())
    main = repo.commit("main gains the app file")
    repo.git("checkout", "-q", "-b", "lower", "main")
    repo.write(APP, app_text(True))
    lower = repo.commit("lower layer")
    repo.git("checkout", "-q", "-b", "upper", "lower")
    repo.write(SHARED, upper_shared())
    return main, lower, repo.commit("upper layer")


def cascaded(repo):
    """Main moves by an unrelated file, then the lower layer is rebuilt on it and the upper layer on that: the layer
    below changes its tree (the unrelated file), and ``twin`` is a rewrite of the new lower head with the same tree."""
    main, lower, x = layers(repo)
    repo.git("checkout", "-q", "main")
    repo.write("docs/other.md", "other\n")
    moved = repo.commit("base moves")
    repo.git("checkout", "-q", "-b", "lower2", moved)
    repo.write(APP, app_text(True))
    b = repo.commit("lower layer, rebased")
    repo.git("checkout", "-q", "-b", "upper2", b)
    repo.write(SHARED, upper_shared())
    h = repo.commit("upper layer, rebased")
    return {"main": main, "lower": lower, "x": x, "b": b, "h": h, "twin": rebuild(repo, b, moved, "twin")}


def queue_removed(repo):
    """The lower layer lands on main as one squashed commit, main moves again, and the upper layer is rebuilt on the tip."""
    main, lower, x = layers(repo)
    repo.git("checkout", "-q", "main")
    repo.write(APP, app_text(True))
    repo.commit("lower layer, squashed onto main")
    repo.write("docs/other.md", "other\n")
    tip = repo.commit("base moves")
    repo.git("checkout", "-q", "-b", "upper2", tip)
    repo.write(SHARED, upper_shared())
    return {"main": main, "lower": lower, "x": x, "b": tip, "h": repo.commit("upper layer, retargeted")}


def scenario(repo, kind):
    """A layer whose bare check reads needs-review (``straightened``) or proven (``cascaded``), with ``same`` (a value
    that holds the base's tree) and ``other`` (one that does not)."""
    if kind == "straightened":
        s = straightened(repo)
        return {"base": s["b1"], "head": s["h1"], "x": s["x"], "same": s["lower"], "other": s["main"],
                "bare": "needs-review"}
    c = cascaded(repo)
    return {"base": c["b"], "head": c["h"], "x": c["x"], "same": c["twin"], "other": c["lower"], "bare": "proven"}


def assert_ignored(bare, got, *ignored):
    """``got`` is ``bare`` in every field but ``why``, which is the bare ``why`` plus one ignored line per
    ``(value, reason)`` given, in order."""
    assert {k: v for k, v in got.items() if k != "why"} == {k: v for k, v in bare.items() if k != "why"}, (bare, got)
    lines = ["%s: %s %s" % (HC.WHY_BASE_AT_REVIEW_IGNORED, value[:8], reason) for value, reason in ignored]
    assert got["why"] == bare["why"] + lines, (bare, got)


def test_a_straightened_stack_reads_needs_review_without_the_input_and_proven_with_it(tmp_path):
    # axis: a layer whose layer below was rewritten onto the same tree stays needs-review with the old head left out, or fails to read proven with it given — see bite-proof record i2561_head_coverage_rewritten_below (not a recorded element)
    repo = TR.Repo(tmp_path)
    s = straightened(repo)
    record = TR.earlier_record(s["x"])
    got = run_check(repo, s["b1"], record, s["h1"])
    assert got["answer"] == "needs-review" and SHARED in got["files"], got
    got = run_check(repo, s["b1"], record, s["h1"], base_at_review=[s["lower"]])
    assert got["answer"] == "proven" and tokens(got) == [HC.WHY_OWN_CHANGE_UNCHANGED, HC.WHY_BASE_AT_REVIEW], got


def test_a_file_the_upper_layer_deletes_after_the_lower_layer_edited_it_reads_proven_against_the_second_base(tmp_path):
    # axis: the reviewed change is read against the second base, so a file whose reconstruction cannot run (a deletion) is compared on its own change — see bite-proof record i2561_head_coverage_rewritten_below (E-xbase)
    repo = TR.Repo(tmp_path)
    main, lower, _ = stack(repo)
    repo.git("rm", "-q", SHARED)
    x = repo.commit("upper layer deletes the shared file")
    b1 = rebuild(repo, lower, main)
    h1 = rebuild(repo, x, b1)
    assert run_check(repo, b1, TR.earlier_record(x), h1)["answer"] == "needs-review"
    got = run_check(repo, b1, TR.earlier_record(x), h1, base_at_review=[lower])
    assert got["answer"] == "proven" and got["files"] == [], got


def test_an_upper_layer_whose_own_change_differs_after_the_rewrite_still_reads_needs_review(tmp_path):
    # axis: a layer whose own change differs from the reviewed one reads needs-review even with a valid second base given — see bite-proof record i2561_head_coverage_rewritten_below (not a recorded element)
    repo = TR.Repo(tmp_path)
    s = straightened(repo)
    repo.git("checkout", "-q", "--detach", s["h1"])
    repo.write(SHARED, shared_text("lower", "upper", upper="changed"))
    head = repo.commit("the upper layer's own lines changed")
    got = run_check(repo, s["b1"], TR.earlier_record(s["x"]), head, base_at_review=[s["lower"]])
    assert got["answer"] == "needs-review" and HC.WHY_BEHAVIOUR_CHANGE in tokens(got) and SHARED in got["files"], got


def test_the_check_and_the_carry_check_with_the_input_republish_the_sheet_carried(tmp_path):
    # axis: the coverage check and the carry check both given the second base fail to republish the sheet carried, or the bare checks fail to take it down — see bite-proof record i2561_head_coverage_rewritten_below (not a recorded element)
    repo = TR.Repo(tmp_path)
    s = straightened(repo)
    record, given = TR.earlier_record(s["x"]), [s["lower"]]
    covered = run_check(repo, s["b1"], record, s["h1"], base_at_review=given)
    carry = run_check(repo, s["b1"], record, s["h1"], base_at_review=given)
    assert covered["answer"] == carry["answer"] == "proven"
    sheet = dict(sheet="live", sheet_commit=s["x"], head=s["h1"])
    assert HC.outcome(covered["answer"], "green", carry_answer=carry["answer"], **sheet) == LIVE
    bare = run_check(repo, s["b1"], record, s["h1"])
    assert HC.outcome(bare["answer"], "green", carry_answer=bare["answer"], **sheet)["sheet"] == "take-down"


def test_two_successive_straightenings_prove_when_every_old_head_of_the_layer_below_is_given(tmp_path):
    # axis: a layer rewritten twice reads proven only when some given old head of the layer below proves it, so a list that lacks the right head must stay needs-review — see bite-proof record i2561_head_coverage_rewritten_below (not a recorded element)
    repo = TR.Repo(tmp_path)
    s = straightened(repo)
    b2 = rebuild(repo, s["b1"], s["main"], "again")
    h2 = rebuild(repo, s["h1"], b2)
    assert b2 != s["b1"]
    record = TR.earlier_record(s["x"])
    assert run_check(repo, b2, record, h2, base_at_review=[s["b1"]])["answer"] == "needs-review"
    covered = run_check(repo, b2, record, h2, base_at_review=[s["b1"], s["lower"]])
    assert covered["answer"] == "proven" and tokens(covered)[-1] == HC.WHY_BASE_AT_REVIEW, covered
    carry = run_check(repo, b2, TR.earlier_record(s["h1"]), h2, base_at_review=[s["b1"]])
    assert carry["answer"] == "proven", carry
    outcome = HC.outcome(covered["answer"], "green", sheet="live", sheet_commit=s["h1"], head=h2,
                         carry_answer=carry["answer"])
    assert outcome == LIVE


def test_a_layer_below_fixed_after_the_review_is_reconstructed_from_the_second_fork(tmp_path):
    # axis: the three-way merge forks at the merge base of the certified commit and the second base, so a layer whose layer below was fixed after the review is reconstructed from its own fork — see bite-proof record i2561_head_coverage_rewritten_below (E-fork)
    repo = TR.Repo(tmp_path)
    main, lower, x = stack(repo)
    repo.git("checkout", "-q", "lower")
    lines = shared_text("lower").splitlines(keepends=True)
    lines[16] = "fixed_16 = 1\n"
    repo.write(SHARED, "".join(lines))
    fixed = repo.commit("lower layer fix")
    repo.git("checkout", "-q", "upper")
    repo.git("merge", "-q", "--no-ff", "-m", "merge lower", "lower")
    merged = repo.git("rev-parse", "HEAD")
    b = rebuild(repo, fixed, main)
    h = rebuild(repo, merged, b)
    record = TR.earlier_record(x)
    assert run_check(repo, b, record, h)["answer"] == "needs-review"
    got = run_check(repo, b, record, h, base_at_review=[fixed])
    assert got["answer"] == "proven" and got["reconstructed"] == [SHARED] and got["files"] == [], got


def test_a_base_at_review_from_the_layers_own_history_never_lets_a_dropped_change_read_proven(tmp_path):
    # axis: a second base whose tree differs from the base's tree is never tried, so a commit from the layer's own history never lets a dropped change read proven — see bite-proof record i2561_head_coverage_rewritten_below (E-tree)
    repo = TR.Repo(tmp_path)
    repo.git("checkout", "-q", "-b", "lower", "main")
    repo.write(SHARED, shared_text("lower"))
    lower = repo.commit("lower layer")
    repo.git("checkout", "-q", "-b", "upper", "lower")
    repo.write(APP, TR.numbered("app", 5))
    p = repo.commit("upper layer, first commit")
    repo.write(SHARED, shared_text("lower", "upper"))
    x = repo.commit("upper layer, second commit")
    b = rebuild(repo, lower, repo.git("rev-parse", "main"))
    repo.git("checkout", "-q", "--detach", b)
    repo.write(SHARED, shared_text("lower", "upper"))
    head = repo.commit("only the shared change, the app file dropped")
    record = TR.earlier_record(x)
    bare = run_check(repo, b, record, head)
    assert bare["answer"] == "needs-review", bare
    got = run_check(repo, b, record, head, base_at_review=[p])
    assert got["answer"] == "needs-review", got
    assert_ignored(bare, got, (p, "other-tree"))
    got = run_check(repo, b, record, head, base_at_review=[lower])
    assert got["answer"] == "needs-review" and APP in got["files"], got


def test_a_base_at_review_that_is_no_sha_reads_input_invalid(tmp_path):
    # axis: a value that is not a full sha reads needs-review with input-invalid, whatever else is given with it — see bite-proof record i2561_head_coverage_rewritten_below (not a recorded element)
    repo = TR.Repo(tmp_path)
    s = straightened(repo)
    for value in (["abc"], [""], [None], [7], [s["lower"], "abc"], 7):
        got = run_check(repo, s["b1"], TR.earlier_record(s["x"]), s["h1"], base_at_review=value)
        assert got["answer"] == "needs-review" and tokens(got) == [HC.WHY_INPUT_INVALID], (value, got)


@pytest.mark.parametrize("kind", ["straightened", "cascaded"])
def test_a_base_at_review_git_has_no_object_for_is_ignored(tmp_path, kind):
    # axis: a second base git cannot read is never tried, so the answer is the bare check's, whether it reads needs-review or proven — see bite-proof record i2561_head_coverage_rewritten_below (E-read)
    repo = TR.Repo(tmp_path)
    sc = scenario(repo, kind)
    record = TR.earlier_record(sc["x"])
    bare = run_check(repo, sc["base"], record, sc["head"])
    assert bare["answer"] == sc["bare"], bare
    got = run_check(repo, sc["base"], record, sc["head"], base_at_review=[NO_OBJECT])
    assert_ignored(bare, got, (NO_OBJECT, "unreadable"))


@pytest.mark.parametrize("kind", ["straightened", "cascaded"])
def test_a_base_at_review_with_another_tree_is_ignored(tmp_path, kind):
    # axis: a second base whose tree differs from the base's tree is never tried, so the answer is the bare check's, whether it reads needs-review or proven — see bite-proof record i2561_head_coverage_rewritten_below (E-tree)
    repo = TR.Repo(tmp_path)
    sc = scenario(repo, kind)
    record = TR.earlier_record(sc["x"])
    bare = run_check(repo, sc["base"], record, sc["head"])
    assert bare["answer"] == sc["bare"], bare
    got = run_check(repo, sc["base"], record, sc["head"], base_at_review=[sc["other"]])
    assert_ignored(bare, got, (sc["other"], "other-tree"))


@pytest.mark.parametrize("kind", ["straightened", "cascaded"])
def test_a_failed_tree_read_is_ignored(tmp_path, kind):
    # axis: a tree git could not read is never tried, so the answer is the bare check's, whether it reads needs-review or proven — see bite-proof record i2561_head_coverage_rewritten_below (E-read)
    repo = TR.Repo(tmp_path)
    sc = scenario(repo, kind)
    record = TR.earlier_record(sc["x"])
    git = seam(repo, lambda a: a[:1] == ["rev-parse"] and a[-1].endswith("^{tree}"))
    bare = run_check(repo, sc["base"], record, sc["head"], git=git)
    assert bare["answer"] == sc["bare"], bare
    got = run_check(repo, sc["base"], record, sc["head"], base_at_review=[sc["same"]], git=git)
    assert_ignored(bare, got, (sc["same"], "unreadable"))


@pytest.mark.parametrize("kind", ["straightened", "cascaded"])
def test_a_base_at_review_with_no_merge_base_is_ignored(tmp_path, kind):
    # axis: a second base that shares no merge base with the certified commit is never tried, so the answer is the bare check's, whether it reads needs-review or proven — see bite-proof record i2561_head_coverage_rewritten_below (E-read)
    repo = TR.Repo(tmp_path)
    sc = scenario(repo, kind)
    record = TR.earlier_record(sc["x"])
    git = seam(repo, lambda a: a == ["merge-base", sc["x"], sc["same"]])
    bare = run_check(repo, sc["base"], record, sc["head"], git=git)
    assert bare["answer"] == sc["bare"], bare
    got = run_check(repo, sc["base"], record, sc["head"], base_at_review=[sc["same"]], git=git)
    assert_ignored(bare, got, (sc["same"], "no-merge-base"))


def test_a_cascading_rebase_onto_a_main_that_moved_reads_proven_and_the_old_head_is_ignored(tmp_path):
    # axis: a layer below rebased onto a main that moved changes its tree, so the old head is ignored and the bare check's proven answer stands — see bite-proof record i2561_head_coverage_rewritten_below (E-ignore)
    repo = TR.Repo(tmp_path)
    c = cascaded(repo)
    record = TR.earlier_record(c["x"])
    bare = run_check(repo, c["b"], record, c["h"])
    assert bare["answer"] == "proven", bare
    got = run_check(repo, c["b"], record, c["h"], base_at_review=[c["lower"]])
    assert got["answer"] == "proven", got
    assert_ignored(bare, got, (c["lower"], "other-tree"))


def test_a_queue_removal_onto_a_main_that_moved_past_the_layer_below_reads_proven_and_the_old_head_is_ignored(tmp_path):
    # axis: a layer retargeted onto a main that holds the layer below squashed and has moved on ignores the old head, so the bare check's proven answer stands — see bite-proof record i2561_head_coverage_rewritten_below (E-ignore)
    repo = TR.Repo(tmp_path)
    q = queue_removed(repo)
    record = TR.earlier_record(q["x"])
    bare = run_check(repo, q["b"], record, q["h"])
    assert bare["answer"] == "proven", bare
    got = run_check(repo, q["b"], record, q["h"], base_at_review=[q["lower"]])
    assert got["answer"] == "proven", got
    assert_ignored(bare, got, (q["lower"], "other-tree"))


def test_an_ignored_value_beside_a_valid_one_that_proves_reads_proven_with_both_lines(tmp_path):
    # axis: a value that is ignored beside a valid one never stops the valid one from proving, and both lines are reported — see bite-proof record i2561_head_coverage_rewritten_below (E-ignore)
    repo = TR.Repo(tmp_path)
    s = straightened(repo)
    record = TR.earlier_record(s["x"])
    got = run_check(repo, s["b1"], record, s["h1"], base_at_review=[NO_OBJECT, s["lower"], s["main"]])
    assert got["answer"] == "proven", got
    assert tokens(got) == [HC.WHY_OWN_CHANGE_UNCHANGED, HC.WHY_BASE_AT_REVIEW, HC.WHY_BASE_AT_REVIEW_IGNORED,
                           HC.WHY_BASE_AT_REVIEW_IGNORED], got
    assert got["why"][2:] == ["%s: %s unreadable" % (HC.WHY_BASE_AT_REVIEW_IGNORED, NO_OBJECT[:8]),
                              "%s: %s other-tree" % (HC.WHY_BASE_AT_REVIEW_IGNORED, s["main"][:8])], got


def test_an_unusable_record_or_a_head_that_is_x_gets_no_ignored_line(tmp_path):
    # axis: an unusable record or a head that is the certified commit returns the check's own answer with no ignored line, whatever the values — see bite-proof record i2561_head_coverage_rewritten_below (not a recorded element)
    repo = TR.Repo(tmp_path)
    s = straightened(repo)
    record = TR.earlier_record(s["x"])
    assert run_check(repo, s["b1"], {"ok": False}, s["h1"], base_at_review=[NO_OBJECT, s["main"]]) \
        == run_check(repo, s["b1"], {"ok": False}, s["h1"])
    same = run_check(repo, s["b1"], record, s["x"], base_at_review=[NO_OBJECT, s["main"]])
    assert same == run_check(repo, s["b1"], record, s["x"])
    assert tokens(same) == [HC.WHY_SAME_COMMIT]
    got = run_check(repo, s["b1"], record, s["h1"], base_at_review=[NO_OBJECT, "abc"])
    assert got["answer"] == "needs-review" and tokens(got) == [HC.WHY_INPUT_INVALID], got


def test_no_input_or_an_unneeded_one_leaves_the_answer_as_it_was(tmp_path):
    # axis: no second base, an empty one, an unusable record or a head that is the certified commit changes the answer from what the check gave before — see bite-proof record i2561_head_coverage_rewritten_below (not a recorded element)
    repo = TR.Repo(tmp_path)
    s = straightened(repo)
    record = TR.earlier_record(s["x"])
    bare = run_check(repo, s["b1"], record, s["h1"])
    assert run_check(repo, s["b1"], record, s["h1"], base_at_review=[]) == bare
    assert run_check(repo, s["b1"], record, s["h1"], base_at_review=None) == bare
    assert run_check(repo, s["b1"], {"ok": False}, s["h1"], base_at_review=[s["lower"]]) \
        == run_check(repo, s["b1"], {"ok": False}, s["h1"])
    same = run_check(repo, s["b1"], record, s["x"], base_at_review=[s["lower"]])
    assert same["answer"] == "proven" and tokens(same) == [HC.WHY_SAME_COMMIT]
    unusable = run_check(repo, s["b1"], {"ok": False}, s["h1"], base_at_review=[s["lower"]])
    assert unusable["answer"] == "needs-review" and tokens(unusable) == [HC.WHY_RECORD_UNUSABLE]


def test_a_plain_bring_current_reads_the_same_with_the_base_given_as_the_second_base(tmp_path):
    # axis: giving the base itself as the second base changes the answer of a plain bring-current merge — see bite-proof record i2561_head_coverage_rewritten_below (not a recorded element)
    repo = TR.Repo(tmp_path)
    repo.git("checkout", "-q", "-b", "lower", "main")
    repo.write("src/lower.py", TR.numbered("lower", 5))
    repo.commit("lower layer")
    repo.git("checkout", "-q", "pr")
    repo.git("merge", "-q", "--ff-only", "lower")
    _, _, earlier = TR.returning(repo, first={SHARED: TR.numbered("shared", 30).replace("value_shared_25 = 25", "pr_edit = 1")})
    repo.git("checkout", "-q", "lower")
    repo.write("src/lower.py", TR.numbered("lower", 5) + "more = 1\n")
    tip = repo.commit("lower layer changes")
    repo.git("checkout", "-q", "pr")
    repo.git("merge", "-q", "--no-ff", "-m", "merge the lower layer up", "lower")
    head = repo.git("rev-parse", "HEAD")
    bare = run_check(repo, tip, earlier, head)
    assert bare["answer"] == "proven"
    assert run_check(repo, tip, earlier, head, base_at_review=[tip]) == bare


def test_the_command_line_takes_the_flag_once_or_repeated(tmp_path):
    # axis: the command line fails to pass a once-given or repeated --base-at-review through to the check, so the layer does not read proven — see bite-proof record i2561_head_coverage_rewritten_below (not a recorded element)
    repo = TR.Repo(tmp_path)
    s = straightened(repo)
    b2 = rebuild(repo, s["b1"], s["main"], "again")
    h2 = rebuild(repo, s["h1"], b2)
    record = tmp_path / "record.json"
    record.write_text(json.dumps(TR.earlier_record(s["x"])))
    for base, head, given in ((s["b1"], s["h1"], [s["lower"]]), (b2, h2, [s["b1"], s["lower"]])):
        argv = [sys.executable, "-B", _SCRIPT, "check", "--repo-root", repo.root, "--base", base, "--record", str(record),
                "--head", head]
        for value in given:
            argv += ["--base-at-review", value]
        proc = subprocess.run(argv, capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout)["answer"] == "proven", proc.stdout
