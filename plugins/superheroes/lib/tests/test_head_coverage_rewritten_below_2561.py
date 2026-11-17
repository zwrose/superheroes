# plugins/superheroes/lib/tests/test_head_coverage_rewritten_below_2561.py
"""Issue 2561 (WO-A): the head-coverage check proves a stack layer after the layer below it is rewritten.

The layer below is rebuilt on a new commit with the same tree (``git commit-tree <old>^{tree} -p <parent>``). The caller
gives ``base_at_review``, the layer below's old heads; the check reads the reviewed change against one only when git
shows its tree equals the base's. Edges: no value is today's check; a non-sha, an object-less, another-tree or an
unreadable value reads needs-review; an unusable record or a head that is X is unchanged.

Bite-proof record: i2561_head_coverage_rewritten_below
"""
import json
import os
import subprocess
import sys

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


def test_a_straightened_stack_reads_needs_review_without_the_input_and_proven_with_it(tmp_path):
    repo = TR.Repo(tmp_path)
    s = straightened(repo)
    record = TR.earlier_record(s["x"])
    got = run_check(repo, s["b1"], record, s["h1"])
    assert got["answer"] == "needs-review" and SHARED in got["files"], got
    got = run_check(repo, s["b1"], record, s["h1"], base_at_review=[s["lower"]])
    assert got["answer"] == "proven" and tokens(got) == [HC.WHY_OWN_CHANGE_UNCHANGED, HC.WHY_BASE_AT_REVIEW], got


def test_a_file_the_upper_layer_deletes_after_the_lower_layer_edited_it_reads_proven_against_the_second_base(tmp_path):
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
    repo = TR.Repo(tmp_path)
    s = straightened(repo)
    repo.git("checkout", "-q", "--detach", s["h1"])
    repo.write(SHARED, shared_text("lower", "upper", upper="changed"))
    head = repo.commit("the upper layer's own lines changed")
    got = run_check(repo, s["b1"], TR.earlier_record(s["x"]), head, base_at_review=[s["lower"]])
    assert got["answer"] == "needs-review" and HC.WHY_BEHAVIOUR_CHANGE in tokens(got) and SHARED in got["files"], got


def test_the_check_and_the_carry_check_with_the_input_republish_the_sheet_carried(tmp_path):
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
    got = run_check(repo, b, record, head, base_at_review=[p])
    assert got["answer"] == "needs-review" and tokens(got) == [HC.WHY_BASE_AT_REVIEW_UNPROVEN], got
    got = run_check(repo, b, record, head, base_at_review=[lower])
    assert got["answer"] == "needs-review" and APP in got["files"], got


def test_a_base_at_review_that_is_no_sha_reads_input_invalid(tmp_path):
    repo = TR.Repo(tmp_path)
    s = straightened(repo)
    for value in (["abc"], [""], [None], [7], [s["lower"], "abc"], 7):
        got = run_check(repo, s["b1"], TR.earlier_record(s["x"]), s["h1"], base_at_review=value)
        assert got["answer"] == "needs-review" and tokens(got) == [HC.WHY_INPUT_INVALID], (value, got)


def test_a_base_at_review_git_has_no_object_for_reads_needs_review(tmp_path):
    repo = TR.Repo(tmp_path)
    s = straightened(repo)
    got = run_check(repo, s["b1"], TR.earlier_record(s["x"]), s["h1"], base_at_review=[s["lower"], NO_OBJECT])
    assert got["answer"] == "needs-review" and tokens(got) == [HC.WHY_BASE_AT_REVIEW_UNPROVEN], got


def test_a_base_at_review_with_another_tree_reads_needs_review(tmp_path):
    repo = TR.Repo(tmp_path)
    s = straightened(repo)
    got = run_check(repo, s["b1"], TR.earlier_record(s["x"]), s["h1"], base_at_review=[s["lower"], s["main"]])
    assert got["answer"] == "needs-review" and tokens(got) == [HC.WHY_BASE_AT_REVIEW_UNPROVEN], got


def test_a_failed_tree_read_reads_needs_review(tmp_path):
    repo = TR.Repo(tmp_path)
    s = straightened(repo)
    git = seam(repo, lambda a: a[:1] == ["rev-parse"] and a[-1].endswith("^{tree}"))
    got = run_check(repo, s["b1"], TR.earlier_record(s["x"]), s["h1"], base_at_review=[s["lower"]], git=git)
    assert got["answer"] == "needs-review" and tokens(got) == [HC.WHY_BASE_AT_REVIEW_UNPROVEN], got


def test_a_base_at_review_with_no_merge_base_reads_needs_review(tmp_path):
    repo = TR.Repo(tmp_path)
    s = straightened(repo)
    git = seam(repo, lambda a: a == ["merge-base", s["x"], s["lower"]])
    got = run_check(repo, s["b1"], TR.earlier_record(s["x"]), s["h1"], base_at_review=[s["lower"]], git=git)
    assert got["answer"] == "needs-review" and tokens(got) == [HC.WHY_BASE_AT_REVIEW_UNPROVEN], got


def test_no_input_or_an_unneeded_one_leaves_the_answer_as_it_was(tmp_path):
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
