"""The `awaits-owner` review-record status (#2136).

A record reads `awaits-owner` exactly when it would read `not-reviewed`, it is not parked, its `whatIsMissing`
is non-empty, and every line of it is the leftover line of one of its own findings left for the owner. With
its leftovers it reads `awaits-owner` if and only if the same record without them reads `reviewed`. Every
reader of `status` treats it as `not-reviewed`; only `reviewed` clears.

Edges: E1 withheldFromReviewers null · E2 empty whatIsMissing reads reviewed · E3 a leftover line for a finding
that is not left-for-owner · E4 parked · E5 a raw output withheld · E6 a planned reviewer that ran on an earlier
commit · E7 an unknown status at a reader · E8 go-ahead note lines · E9 an unreadable raw file.
"""
import re
from pathlib import Path

import pytest

import review_record as rr
from test_pr_sheet import BIG, bundle as sheet_bundle, build as sheet_build, fill
from test_review_record import RED, Fake, _fix_round_account, _fix_round_runs, account, build, finding, reviewer, send
import test_review_record_owner_ruling as ruling

LIB = Path(__file__).resolve().parents[1]
LEFT = {"outcome": "left-for-owner", "reason": "needs owner"}


class Clean(Fake):
    """A Fake whose withheld-path reader names nothing withheld, so `withheldFromReviewers` is `[]`."""

    def __init__(self, withheld=(), **kw):
        super().__init__(**kw)
        self.withheld = list(withheld)

    def readers(self):
        return {**super().readers(), "withheld_paths": lambda root, sha, paths: list(self.withheld)}


def left_two():
    return [finding("f1", **LEFT), finding("f2", **LEFT)]


def acct(tmp_path, findings=None, **over):
    return account(repoRoot=str(tmp_path), findings=left_two() if findings is None else findings, **over)


def lines_of(findings):
    return [rr.leftover_line(f) for f in findings]


def test_leftovers_only_reads_awaits_owner_and_says_so_in_the_head_line(tmp_path):
    # axis: the status itself; a record whose only gaps are findings left for the owner still reading not-reviewed
    rec = build(acct(tmp_path), Clean())
    assert rec["status"] == rr.AWAITS_OWNER and rec["parked"] is False
    assert rec["whatIsMissing"] == lines_of(left_two())
    assert "Review record: reviewed; 2 findings wait for your decision (f1, f2)." in rr.render(rec)
    one = build(acct(tmp_path, findings=[finding("f1", **LEFT)]), Clean())
    assert one["status"] == rr.AWAITS_OWNER
    assert "Review record: reviewed; 1 finding waits for your decision (f1)." in rr.render(one)


def test_the_compact_head_line_lists_no_ids(tmp_path):
    # axis: compact render; the finding ids listed in a level-1 head line instead of pointing at the full record
    rec = build(acct(tmp_path), Clean())
    text = rr._summary(rec, 1)
    assert "reviewed; 2 findings wait for your decision (listed in the full record)" in text
    assert "f1" not in text.split("\n", 1)[0] and "f2" not in text.split("\n", 1)[0]
    assert rr._summary(rec, 2).startswith("**Review record: reviewed; 2 findings wait for your decision ")


def test_other_statuses_render_their_head_line_as_before(tmp_path):
    # axis: head line of the other statuses; not-reviewed or reviewed rewritten by the awaits-owner branch
    assert "**Review record: not reviewed.**" in rr.render(build(account(findings=left_two()), Clean(ci=RED)))
    assert "**Review record: reviewed.**" in rr.render(build(account(), Clean()))


def test_ci_red_with_leftovers_stays_not_reviewed(tmp_path):
    # axis: every line is a leftover; a record with another gap beside the leftovers reading awaits-owner
    rec = build(acct(tmp_path), Clean(ci=RED))
    assert rec["status"] == rr.NOT_REVIEWED
    assert any(m.startswith("CI is ") for m in rec["whatIsMissing"])


def test_leftovers_and_a_planned_reviewer_that_did_not_run_stay_not_reviewed(tmp_path):
    # axis: a reviewer that did not run; with or without a go-ahead the record is never owner-only
    sec = reviewer("security-reviewer", ran=False, runDir=None)
    rec = build(acct(tmp_path, reviewers=[reviewer(), sec]), Clean())
    assert rec["status"] == rr.NOT_REVIEWED and rec["parked"] is True
    go = {"reviewer": "security-reviewer", "kind": "owner-words", "words": "go ahead", "where": "the issue thread"}
    rec = build(acct(tmp_path, reviewers=[reviewer(), sec], goAheads=[go]), Clean())
    assert rec["status"] == rr.NOT_REVIEWED and rec["parked"] is False
    assert any("security-reviewer did not run" in m for m in rec["whatIsMissing"])


def test_leftovers_and_an_undecided_finding_stay_not_reviewed(tmp_path):
    # axis: an undecided finding; its "has no outcome" line is not a leftover line
    rec = build(acct(tmp_path, findings=[*left_two(), finding("f3", outcome=None)]), Clean())
    assert rec["status"] == rr.NOT_REVIEWED
    assert "finding f3 has no outcome" in rec["whatIsMissing"]


def test_a_ghost_leftover_line_is_not_a_leftover(tmp_path):
    # axis: E3, the leftover set is built from the record's own left-for-owner findings, not from the line's wording
    rec = build(acct(tmp_path), Clean())
    ghost = "finding ghost waits for the owner's decision"
    assert rr._owner_only(dict(rec, status=rr.NOT_REVIEWED), [*rec["whatIsMissing"], ghost]) is False
    assert rr._owner_only(dict(rec, status=rr.NOT_REVIEWED), []) is False
    assert rr._owner_only(dict(rec, status=rr.NOT_REVIEWED), rec["whatIsMissing"]) is True


def test_a_parked_record_is_never_owner_only(tmp_path):
    # axis: E4, a parked record; the helper accepting it because its lines happen to be leftovers
    rec = build(acct(tmp_path), Clean())
    assert rr._owner_only(dict(rec, status=rr.NOT_REVIEWED, parked=True), rec["whatIsMissing"]) is False


def test_a_reviewed_record_stays_reviewed(tmp_path):
    # axis: E2, an empty whatIsMissing; no gap at all reading as awaiting the owner
    rec = build(acct(tmp_path, findings=[]), Clean())
    assert rec["status"] == rr.REVIEWED and rec["whatIsMissing"] == []


def test_leftovers_with_a_withheld_path_read_awaits_owner(tmp_path):
    # axis: a withheld path narrowing the status; it keeps no record from reviewed, so it must not keep one from awaits-owner
    rec = build(acct(tmp_path), Clean(withheld=["x/.claude/settings.json"]))
    assert rec["withheldFromReviewers"] == ["x/.claude/settings.json"] and rec["status"] == rr.AWAITS_OWNER


def test_leftovers_with_an_unknown_withheld_list_read_awaits_owner():
    # axis: E1, a null withheld list narrowing the status; an account naming no repository reads no changed files
    rec = build(account(findings=left_two()), Clean())
    assert rec["withheldFromReviewers"] is None and rec["status"] == rr.AWAITS_OWNER


def test_leftovers_with_an_unreadable_raw_file_stay_not_reviewed(tmp_path):
    # axis: E9, an unreadable raw file adds a line that is not a leftover line
    gone = str(tmp_path / "gone.txt")
    rec = build(acct(tmp_path, rawFindingsFiles=[gone]), Clean())
    assert rec["status"] == rr.NOT_REVIEWED
    assert f"the raw output file {gone} could not be read" in rec["whatIsMissing"]


def test_a_withheld_raw_output_still_reads_awaits_owner_at_write(tmp_path):
    # axis: E5, a withheld raw output narrowing the status at write; its text stays out of the posted comments, the status is unchanged
    secret, clean = tmp_path / "secret.txt", tmp_path / "clean.txt"
    secret.write_text('password = "LEAKMARK"\n')
    clean.write_text("intro\nnothing sensitive here\n")
    bad = Clean()
    out = send(tmp_path, bad, repoRoot=str(tmp_path), findings=left_two(), rawFindingsFiles=[str(secret)])
    assert out["status"] == rr.AWAITS_OWNER
    assert rr.read(7, readers=bad.readers())["status"] == rr.AWAITS_OWNER
    assert "LEAKMARK" not in "".join(c["body"] for c in bad.comments)
    good = Clean()
    out = send(tmp_path, good, repoRoot=str(tmp_path), findings=left_two(), rawFindingsFiles=[str(clean)])
    assert out["status"] == rr.AWAITS_OWNER
    assert rr.read(7, readers=good.readers())["status"] == rr.AWAITS_OWNER


def test_leftovers_in_a_mixed_head_fix_round_read_awaits_owner(tmp_path):
    # axis: a per-seat coverage check narrowing the status; specialists on an earlier commit beside a covering auditor
    rec = build(_fix_round_account(repoRoot=str(tmp_path), findings=left_two()), Clean(runs=_fix_round_runs()))
    assert [v["coversFinalCommit"] for v in rec["reviewers"]] == [False, False, True]
    assert rec["status"] == rr.AWAITS_OWNER and rec["whatIsMissing"] == lines_of(left_two())
    same = build(_fix_round_account(repoRoot=str(tmp_path)), Clean(runs=_fix_round_runs()))
    assert same["status"] == rr.REVIEWED


GO_AHEAD = {"reviewer": "security-reviewer", "kind": "owner-words", "words": "go ahead", "where": "the issue thread"}
NOT_RUN = reviewer("security-reviewer", ran=False, runDir=None)


def _read_status(tmp_path, findings, fake=None, **over):
    return build(acct(tmp_path, findings=findings, **over), fake or Clean())["status"]


def _undecided(tmp_path, findings):
    return _read_status(tmp_path, [*findings, finding("f3", outcome=None)])


def _unreadable(tmp_path, findings):
    return _read_status(tmp_path, findings, rawFindingsFiles=[str(tmp_path / "gone.txt")])


def _credential(tmp_path, findings):
    secret = tmp_path / "secret.txt"
    secret.write_text('password = "LEAKMARK"\n')
    return send(tmp_path, Clean(), repoRoot=str(tmp_path), findings=findings, rawFindingsFiles=[str(secret)])["status"]


SHAPES = {
    "clean": (rr.AWAITS_OWNER, lambda p, f: _read_status(p, f)),
    "ci-red": (rr.NOT_REVIEWED, lambda p, f: _read_status(p, f, Clean(ci=RED))),
    "reviewer-did-not-run": (rr.NOT_REVIEWED, lambda p, f: _read_status(p, f, reviewers=[reviewer(), NOT_RUN])),
    "reviewer-did-not-run-with-go-ahead": (
        rr.NOT_REVIEWED, lambda p, f: _read_status(p, f, reviewers=[reviewer(), NOT_RUN], goAheads=[GO_AHEAD])),
    "undecided-finding": (rr.NOT_REVIEWED, _undecided),
    "no-maker": (rr.NOT_REVIEWED, lambda p, f: _read_status(p, f, makers=[])),
    "mixed-head-fix-round": (rr.AWAITS_OWNER, lambda p, f: build(
        _fix_round_account(repoRoot=str(p), findings=f), Clean(runs=_fix_round_runs()))["status"]),
    "withheld-path": (rr.AWAITS_OWNER, lambda p, f: _read_status(p, f, Clean(withheld=["x/.claude/settings.json"]))),
    "null-withheld-list": (rr.AWAITS_OWNER, lambda p, f: build(account(findings=f), Clean())["status"]),
    "unreadable-raw-file": (rr.NOT_REVIEWED, _unreadable),
    "credential-raw-output": (rr.AWAITS_OWNER, _credential),
}


@pytest.mark.parametrize("shape", SHAPES)
def test_awaits_owner_iff_the_record_without_leftovers_reads_reviewed(tmp_path, shape):
    # axis: the parity; a narrowing condition on awaits-owner that does not also keep the leftover-free record from reviewed
    expected, make = SHAPES[shape]
    arms = {}
    for arm, findings in (("with", left_two()), ("without", [])):
        (tmp_path / arm).mkdir()
        arms[arm] = make(tmp_path / arm, findings)
    with_leftovers, without = arms["with"], arms["without"]
    assert with_leftovers in (rr.AWAITS_OWNER, rr.NOT_REVIEWED)
    assert (with_leftovers == rr.AWAITS_OWNER) == (without == rr.REVIEWED)
    assert with_leftovers == expected


def test_leftovers_ruled_through_owner_rulings_read_reviewed(tmp_path):
    # axis: a leftover the owner ruled on is decided, not waiting; it reads reviewed whatever else the fixture allows
    def readers(**kw):
        return {**ruling.readers(**kw), "withheld_paths": lambda root, sha, paths: []}

    def made(rulings):
        base = {**ruling.account(rulings), "lane": "full", "laneReason": "the change touches the review record",
                "makers": [{"family": "anthropic"}], "reviewers": [reviewer("r1")]}
        return rr.build_record({**base, "repoRoot": str(tmp_path)}, readers())

    unruled = made([])
    assert unruled["whatIsMissing"] == ["finding f-1 waits for the owner's decision"]
    assert unruled["status"] == rr.AWAITS_OWNER and unruled["leftForOwner"] == ["f-1"]
    ruled = made([ruling.entry()])
    assert ruled["status"] == rr.REVIEWED and ruled["leftForOwner"] == [] and ruled["whatIsMissing"] == []


def test_cleared_is_true_only_for_reviewed():
    # axis: the one gate predicate; any other value, an unknown one included, clearing a gate
    assert rr.cleared("reviewed") is True
    for other in ("not-reviewed", "awaits-owner", None, "", "Reviewed"):
        assert rr.cleared(other) is False
    assert rr.STATUSES == ("reviewed", "not-reviewed", "awaits-owner")


def _sheet_history(status):
    records, advisor = sheet_bundle(BIG)
    left = [f for f in records[0]["findings"] if f["outcome"] == "left-for-owner"]
    lines = [rr.leftover_line(f) for f in left]
    assert len(lines) == 2
    records[0].update(status=status, whatIsMissing=list(lines))
    return sheet_build(records, advisor)["prSheet"]["history"]


def test_the_sheet_reads_awaits_owner_exactly_as_not_reviewed():
    # axis: pr_sheet's gap reader; awaits-owner (or an unknown status) dropping the gap and leftover lines
    awaiting, unread = _sheet_history("awaits-owner"), _sheet_history("not-reviewed")
    assert awaiting == unread
    assert _sheet_history("future-status") == unread
    assert _sheet_history(None) == unread
    expected = fill("historyLeftovers", count=2)
    assert awaiting.count(expected) == 1
    assert _sheet_history("reviewed") != unread


SKIPPED = ("review_record.py",)
STATUS_LITERAL = re.compile(r"""["']not-reviewed["']""")
REVIEWED_COMPARE = re.compile(r"""(?:[=!]=\s*["']reviewed["']|["']reviewed["']\s*[=!]=)""")
STATUS_CONSTANT = re.compile(r"\b(NOT_REVIEWED|REVIEWED|AWAITS_OWNER)\b")


def test_no_reader_outside_review_record_spells_the_status_literals():
    # axis: the status vocabulary has one home; a reader comparing against the literal or the exported constant instead of review_record.cleared
    found = []
    for path in sorted(LIB.rglob("*.py")):
        rel = path.relative_to(LIB)
        if "tests" in rel.parts or "__pycache__" in rel.parts or rel.name.startswith("test_") or rel.name in SKIPPED:
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if STATUS_LITERAL.search(line) or REVIEWED_COMPARE.search(line) or STATUS_CONSTANT.search(line):
                found.append(f"{rel}:{n}: {line.strip()}")
    assert not found, "status literals or constants outside review_record.py:\n" + "\n".join(found)


DOCTRINE = (
    "skills/review-code/reference/review-record.md",
    "skills/showrunner/reference/vet-receipt.md",
    "skills/workhorse/reference/cloud.md",
    "TRANSITION.md",
)


def test_the_doctrine_names_awaits_owner_and_says_it_never_clears_a_gate():
    # axis: the doctrine; a reference or the transition note that stops naming the status, or stops saying it clears nothing
    texts = {name: (LIB.parent / name).read_text(encoding="utf-8") for name in DOCTRINE}
    for name, text in texts.items():
        assert "awaits-owner" in text, name
    for name in (DOCTRINE[0], DOCTRINE[3]):
        assert "never clears a gate" in texts[name], name
