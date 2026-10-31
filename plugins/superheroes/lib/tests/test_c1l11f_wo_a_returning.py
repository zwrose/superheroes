# plugins/superheroes/lib/tests/test_c1l11f_wo_a_returning.py
"""C1-L11f (WO-A): an earlier record written before CI finished may also leave findings for the owner.

Pins:

A1  a record whose gaps are the one CI-pending line plus `finding <name> waits for the owner's decision` lines, each
    naming a left-for-owner finding of the record, settles once CI has passed (it is not read full);
A1  any other line beside the CI line, a waits line naming a finding with another outcome or none, no CI line, or two
    CI lines, still reads full;
A1  a findings list that is missing, not a list or holds non-dict rows allows nothing and never raises;
A1  the route the vet names: CI red on the last reviewed commit reads full, and CI green on a catch-up-only head settles;
A2  the ledger operand of `_empty_returning_round` (the fault half, which `write_from_session` cannot reach): a
    malformed disposition ledger is never the empty round.

Bite-proof records: c1l11f_wo_a_returning (A1-G1 to A1-G3), c1l11d_wo_a_carried_review (E8)
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
import review_record_session as RS  # noqa: E402
import test_c1l11d_carried_review as TCR  # noqa: E402
import test_c1l11d_fold_returning as TF  # noqa: E402
import test_returning_review_c1l11 as TR  # noqa: E402
from test_c1l11b_returning_session import _isolated_git  # noqa: E402,F401  (autouse: no global git config; the session fixture needs this one)


def _finding(name, outcome):
    return {"id": name, "title": "a finding", "outcome": outcome, "reason": "because"}


FINDINGS = [_finding("F-1", "left-for-owner"), _finding("F-2", "fixed"), _finding("F-3", "left-for-owner")]


def _waits(name):
    return RR.leftover_line(_finding(name, "left-for-owner"))


def _owner_pending(reviewed, missing, findings=FINDINGS, **over):
    """The pending record of C1-L11d, with findings and the given ``whatIsMissing`` lines."""
    rows = [dict(f) if isinstance(f, dict) else f for f in findings] if isinstance(findings, list) else findings
    record = TF._pending(reviewed, findings=rows, whatIsMissing=missing)
    record.update(over)
    return record


def _decide_with_fix(tmp_path, build):
    repo, base, reviewed, _ = TF._with_fix(tmp_path)
    reader = TF.Reader({reviewed: "green", repo.git("rev-parse", "HEAD"): "green"})
    return TR.decide(repo, base, build(reviewed), ci_state=reader), reader


# --- A1: the CI line beside the owner-wait lines it may share a record with ---------------------------------------------

def test_a1_a_ci_line_beside_a_left_for_owner_waits_line_settles_once_ci_has_passed(tmp_path):
    got, reader = _decide_with_fix(tmp_path, lambda sha: _owner_pending(sha, [TF._ci_line(sha), _waits("F-1")]))
    assert got["read"] == "changed" and R.WHY_CI_SETTLED in TR.tokens(got), got
    assert got["changedFiles"] == ["src/app.py"] and len(reader.asked) == 1  # green on the last reviewed commit ends the asking


def test_a1_every_waits_line_in_any_order_beside_the_ci_line_settles(tmp_path):
    got, _ = _decide_with_fix(tmp_path, lambda sha: _owner_pending(sha, [_waits("F-3"), TF._ci_line(sha), _waits("F-1")]))
    assert got["read"] == "changed" and R.WHY_CI_SETTLED in TR.tokens(got), got


def test_a1_a_line_of_any_other_kind_beside_the_ci_line_and_a_waits_line_reads_full(tmp_path):
    # axis: every line beside the one CI line is a left-for-owner finding's waits line, none of any other kind — see bite-proof record c1l11f_wo_a_returning
    others = ("no maker is named, so independence cannot be shown", "no planned reviewer ran",
              "finding F-1 has no reason", "the lane (light) is below the risk floor (full); the Risk floor line gives why")
    for n, other in enumerate(others):
        got, reader = _decide_with_fix(
            tmp_path / ("x%d" % n),
            lambda sha: _owner_pending(sha, [TF._ci_line(sha), _waits("F-1"), other]))
        assert got["read"] == "full" and TR.tokens(got) == [R.WHY_INCOMPLETE], (other, got)
        assert reader.asked == []


def test_a1_a_waits_line_naming_a_finding_that_is_not_left_for_owner_reads_full(tmp_path):
    # axis: a waits line is let through only for a finding whose outcome is left-for-owner — see bite-proof record c1l11f_wo_a_returning
    got, reader = _decide_with_fix(tmp_path, lambda sha: _owner_pending(sha, [TF._ci_line(sha), _waits("F-2")]))
    assert got["read"] == "full" and TR.tokens(got) == [R.WHY_INCOMPLETE], got
    assert reader.asked == []


def test_a1_a_waits_line_naming_no_finding_of_the_record_reads_full(tmp_path):
    got, _ = _decide_with_fix(tmp_path, lambda sha: _owner_pending(sha, [TF._ci_line(sha), _waits("F-99")]))
    assert got["read"] == "full" and TR.tokens(got) == [R.WHY_INCOMPLETE], got


def test_a1_waits_lines_without_a_ci_line_read_full(tmp_path):
    # axis: exactly one CI-pending line is required, also beside owner-wait lines — see bite-proof record c1l11f_wo_a_returning
    got, _ = _decide_with_fix(tmp_path, lambda sha: _owner_pending(sha, [_waits("F-1"), _waits("F-3")]))
    assert got["read"] == "full" and TR.tokens(got) == [R.WHY_INCOMPLETE], got


def test_a1_two_ci_lines_read_full(tmp_path):
    got, _ = _decide_with_fix(tmp_path, lambda sha: _owner_pending(sha, [TF._ci_line(sha), TF._ci_line(sha), _waits("F-1")]))
    assert got["read"] == "full" and TR.tokens(got) == [R.WHY_INCOMPLETE], got


@pytest.mark.parametrize("findings", [None, "not-a-list", {"F-1": "left-for-owner"}, ["F-1"], [None, 3]],
                         ids=["missing", "string", "dict", "string-rows", "non-dict-rows"])
def test_a1_a_findings_list_that_is_missing_or_unreadable_allows_no_waits_line_and_never_raises(tmp_path, findings):
    def build(sha):
        record = _owner_pending(sha, [TF._ci_line(sha), _waits("F-1")], findings=findings)
        if findings is None:
            record.pop("findings")
        return record
    got, _ = _decide_with_fix(tmp_path, build)
    assert got["read"] == "full" and TR.tokens(got) == [R.WHY_INCOMPLETE], got


def test_a1_a_non_string_line_beside_the_ci_line_reads_full(tmp_path):
    for n, odd in enumerate((None, 7, {"line": _waits("F-1")})):
        got, _ = _decide_with_fix(tmp_path / ("y%d" % n),
                                  lambda sha: _owner_pending(sha, [TF._ci_line(sha), odd]))
        assert got["read"] == "full" and TR.tokens(got) == [R.WHY_INCOMPLETE], (odd, got)


def test_a1_the_clean_pending_record_with_no_findings_at_all_still_settles(tmp_path):
    got, _ = _decide_with_fix(tmp_path, lambda sha: _owner_pending(sha, [TF._ci_line(sha)], findings=[]))
    assert got["read"] == "changed" and R.WHY_CI_SETTLED in TR.tokens(got), got


def test_a1_the_decider_uses_the_writers_waits_wording(tmp_path):
    assert _waits("F-1") == "finding F-1 waits for the owner's decision"


# --- the route the vet names (pins existing behaviour: already true at the base) ----------------------------------------

def test_a1_ci_red_on_the_last_reviewed_commit_reads_red_and_green_on_a_catch_up_only_head_settles(tmp_path):
    repo, moved, reviewed, _ = TF._head_only(tmp_path)
    head = repo.git("rev-parse", "HEAD")
    record = TF._pending(reviewed)
    red = TR.decide(repo, moved, record, ci_state=TF.Reader({reviewed: "red", head: "red"}))
    assert red["read"] == "full" and TR.tokens(red) == [R.WHY_INCOMPLETE] and "red" in red["why"][0], red
    green = TR.decide(repo, moved, record, ci_state=TF.Reader({reviewed: "red", head: "green"}))
    assert green["read"] == "changed" and R.WHY_CI_SETTLED in TR.tokens(green) and head[:7] in green["why"][0], green


# --- A2 / E8: a malformed disposition ledger is never the empty round ---------------------------------------------------

@pytest.mark.parametrize("ledger", ["not-a-ledger", {"rows": []}, [None], ["row"], 3],
                         ids=["string", "dict", "none-row", "string-row", "int"])
def test_e8_a_malformed_disposition_ledger_is_never_the_empty_round(tmp_path, monkeypatch, ledger):
    # `write_from_session` refuses a malformed ledger before this check, so the operand's fault half is reached only by a direct call
    s = TCR._empty_session(tmp_path, monkeypatch)
    state = s.state()
    assert RS._empty_returning_round(state) == s.reviewed  # the session really is the empty round
    assert RS._empty_returning_round(dict(state, dispositionLedger=ledger)) is None
