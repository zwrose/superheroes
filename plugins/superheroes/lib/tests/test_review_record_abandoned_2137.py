"""#2137: a review session the orchestrator closes as abandoned writes its own record, and that record never
reads reviewed."""
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import review_record as rr  # noqa: E402
import review_record_session as rs  # noqa: E402
import round_phases  # noqa: E402

from test_review_record_session import (  # noqa: E402
    CODEX, EARLIER, GOOD_RUN, HEAD, KEY, Fake, Session, extras, ledger_row, put_envelope, put_extras, raw_comments,
)

REASON = "owner stopped the loop"
PANEL, GAPSWEEP, SCOPED = round_phases.P_PANEL, round_phases.P_GAPSWEEP, round_phases.P_SCOPED
ABANDONED_LINE = "session abandoned: the review loop was closed before it ended, so this record cannot read reviewed"
CHECKED_ABANDONED = "the review loop was abandoned before it ended: " + REASON
CHECKED_UNFOLDED = "findings in seat results that were recorded but never folded are listed as open findings"
LIVE_FINDING = {"findingKey": KEY, "id": "f-1", "title": "t", "severity": "Important", "file": "a.py", "line": 3,
                "detail": "d", "dimension": "code-reviewer"}


def _write(tmp_path, session, fake, abandoned=None, **over):
    return rs.write_from_session(session, put_extras(tmp_path, extras(**over)), str(tmp_path), fake.readers(),
                                 abandoned=abandoned)


def _sub(tmp_path, name):
    root = tmp_path / name
    root.mkdir()
    return root


def _settled(root, terminal):
    """Every reviewed condition holds: the one finding fixed, a maker named, one planned reviewer that ran on the final commit."""
    s = Session(root, terminal=terminal, dispositionLedger=[ledger_row()],
                seatMapReceipts=[{"round": "1", "map": {"seats": {}, "makerFamilies": ["xai"]}}])
    s.seat("code-reviewer", head=HEAD, nonce="n1")
    runs = {"/run/n1": (dict(GOOD_RUN, runnerNonce="n1", viewHeadSha=HEAD), None)}
    return s.save(), runs, {"ci": "green", "runDirs": ["/run/n1"]}


def test_an_abandoned_session_with_an_open_finding_writes_a_not_reviewed_record(tmp_path):
    """axis: --abandoned on a session that never ended writes a record that reads not-reviewed, names the abandonment,
    lists the open finding undecided, and carries both fixed checked lines."""
    session = Session(tmp_path, terminal=None, findings=[LIVE_FINDING]).seat("code-reviewer").save()
    fake = Fake()
    out = _write(tmp_path, session, fake, abandoned=REASON)
    assert out["ok"] and out["status"] == "not-reviewed", out
    rec = rr.read(7, readers=fake.readers())
    assert ABANDONED_LINE in rec["whatIsMissing"]
    assert [(f["id"], f["outcome"], f["reason"]) for f in rec["findings"]] == [("f-1", None, rs.STILL_OPEN)]
    assert rs.STILL_OPEN == "still open when the review loop ended"
    assert CHECKED_ABANDONED in rec["checked"] and CHECKED_UNFOLDED in rec["checked"]
    assert rec["abandoned"] == {"reason": REASON}


def test_an_abandoned_session_whose_every_other_condition_holds_still_reads_not_reviewed(tmp_path):
    """axis: E4 — the abandoned line alone keeps a record not-reviewed when findings are settled, CI is green on the
    final commit, a maker is named and a planned reviewer covered the final commit."""
    ctl_session, ctl_runs, ctl_body = _settled(_sub(tmp_path, "ctl"), "converged")
    ctl = Fake(runs=ctl_runs)
    assert _write(tmp_path, ctl_session, ctl, **ctl_body)["status"] == "reviewed"  # the same session, ended: reviewed
    assert "abandoned" not in rr.read(7, readers=ctl.readers())
    session, runs, body = _settled(_sub(tmp_path, "abn"), None)
    fake = Fake(runs=runs)
    out = _write(tmp_path, session, fake, abandoned=REASON, **body)
    assert out["ok"] and out["status"] == "not-reviewed", out
    rec = rr.read(7, readers=fake.readers())
    assert rec["status"] == "not-reviewed"
    assert rec["whatIsMissing"] == [ABANDONED_LINE]
    assert rec["abandoned"] == {"reason": REASON}


def test_abandoning_a_session_that_ended_is_refused_and_posts_nothing(tmp_path):
    """axis: E1 — a terminal session is never recorded as abandoned."""
    session, runs, body = _settled(tmp_path, "converged")
    fake = Fake(runs=runs)
    out = _write(tmp_path, session, fake, abandoned=REASON, **body)
    assert out["ok"] is False and out["reason"] == rs.NOT_ABANDONABLE == "review-session-not-abandonable", out
    assert fake.comments == [] and fake.writes == []


@pytest.mark.parametrize("reason", ["", "   ", "\t\n", 5, ["x"]])
def test_a_blank_or_non_text_abandon_reason_is_refused_and_posts_nothing(tmp_path, reason):
    """axis: E2 — --abandoned needs a reason that is text and not blank."""
    session = Session(tmp_path, terminal=None).seat("code-reviewer").save()
    fake = Fake()
    out = _write(tmp_path, session, fake, abandoned=reason)
    assert out["ok"] is False and out["reason"] == rs.ABANDON_REASON_MISSING == "review-session-abandon-reason-missing", out
    assert fake.comments == [] and fake.writes == []


def test_a_session_that_has_not_ended_is_still_refused_without_abandoned(tmp_path):
    """axis: E3 — without --abandoned a non-terminal session keeps its review-session-not-terminal refusal."""
    session = Session(tmp_path, terminal=None).seat("code-reviewer").save()
    fake = Fake()
    out = _write(tmp_path, session, fake)
    assert out["ok"] is False and out["reason"] == rs.NOT_TERMINAL, out
    assert fake.comments == [] and fake.writes == []


def test_a_session_abandoned_before_any_seat_result_lists_no_reviewer(tmp_path):
    """axis: an abandoned session that recorded no seat result or status gets an empty reviewers list instead of the
    unsupported refusal, and its record reads not-reviewed."""
    session = Session(tmp_path, terminal=None).save()
    account = rs.account_from_session(session, extras(), Fake().readers(), abandoned=REASON)
    assert account["reviewers"] == [] and account["abandoned"] == {"reason": REASON}
    fake = Fake()
    out = _write(tmp_path, session, fake, abandoned=REASON)
    assert out["ok"] and out["status"] == "not-reviewed", out
    rec = rr.read(7, readers=fake.readers())
    assert rec["reviewers"] == [] and ABANDONED_LINE in rec["whatIsMissing"]
    # the same session, ended, is still unsupported: the empty list is the abandoned path's alone
    ended = Session(_sub(tmp_path, "ended"), terminal="converged").save()
    with pytest.raises(rs.Refusal) as err:
        rs.account_from_session(ended, extras(), Fake().readers())
    assert err.value.reason == rs.UNSUPPORTED


def test_any_other_refusal_still_stands_for_an_abandoned_session(tmp_path):
    """axis: only the no-seat-result refusal is turned into an empty reviewers list; an unreadable session still refuses."""
    session = Session(tmp_path, terminal=None).save()
    os.unlink(os.path.join(session, "meta.json"))
    out = _write(tmp_path, session, Fake(), abandoned=REASON)
    assert out["ok"] is False and out["reason"] == rs.UNREADABLE, out


def test_findings_in_a_seat_result_never_folded_reach_the_record_through_its_raw_file(tmp_path):
    """axis: a recorded-but-never-folded seat result becomes one open finding row; its findings are also in the raw
    findings file the record lists."""
    session = Session(tmp_path, terminal=None).seat("code-reviewer").save()
    put_envelope(session, "code-reviewer", {"vendor": "codex", "model": CODEX, "payload": {"findings": [
        {"title": "Unfolded defect", "severity": "Important", "consequence": "a defect stays in the change"}]}})
    fake = Fake()
    out = _write(tmp_path, session, fake, abandoned=REASON)
    assert out["ok"] and out["status"] == "not-reviewed", out
    rec = rr.read(7, readers=fake.readers())
    assert len(rec["findings"]) == 1
    row = rec["findings"][0]
    assert row["outcome"] is None and row["reason"] == rs.UNFOLDED_OPEN and row["title"] == "Unfolded defect"
    assert len(rec["rawOutputs"]) == 1 and "code-reviewer" in rec["rawOutputs"][0]["file"]
    posted = raw_comments(fake)
    assert len(posted) == 1 and "Unfolded defect" in posted[0]
    assert CHECKED_UNFOLDED in rec["checked"]


def _abandoned_slots(tmp_path, rounds, slots):
    """The (title, line) of each open row an abandoned session lists; `slots` is [(seat, phase, round, findings)]."""
    s = Session(tmp_path, terminal=None, rounds=rounds)
    for seat, phase, rnd, _ in slots:
        s.seat(seat, phase=phase, rnd=rnd)
    session = s.save()
    for seat, phase, rnd, raised in slots:
        put_envelope(session, seat, {"vendor": "codex", "model": CODEX, "payload": {"findings": raised}}, phase=phase, rnd=rnd)
    account = rs.account_from_session(session, extras(), Fake().readers(), abandoned=REASON)
    return [(f["title"], f["line"]) for f in account["findings"]]


def _abandoned_titles(tmp_path, rounds, raised):
    return _abandoned_slots(tmp_path, rounds, [("code-reviewer", PANEL, 1, raised)])


def test_a_same_titled_finding_at_another_line_survives_a_compile_drop_in_an_abandoned_session(tmp_path):
    """axis: the compile-drop match includes the line, so only the dropped location is left out of the unfolded rows."""
    drop = {"title": "Same title", "file": "a.py", "line": 10, "reason": "out of scope"}
    got = _abandoned_titles(tmp_path, {"1": {"compileDrops": [drop]}}, [
        {"title": "Same title", "file": "a.py", "line": 10, "severity": "Important", "consequence": "c"},
        {"title": "Same title", "file": "a.py", "line": 20, "severity": "Important", "consequence": "c"}])
    assert got == [("Same title", 20)]


PASSED_RUN = {"title": "Break it", "file": "tests/test_x.py", "outcome": "passed", "findingKey": None}
PROPOSAL = {"title": "Break it", "file": "tests/test_x.py", "line": 1, "severity": "Important", "consequence": "c",
            "taxonomy": "break-it-test"}
SAME_PLACE = {"title": "Break it", "file": "tests/test_x.py", "line": 9, "severity": "Important", "consequence": "c"}


def test_a_passing_break_it_proposal_is_not_recovered_as_an_open_finding_in_an_abandoned_session(tmp_path):
    """axis: a test-role panel proposal whose break-it test passed was dropped before compile and is not listed open on
    abandonment."""
    got = _abandoned_slots(tmp_path, {"1": {"breakItRuns": [PASSED_RUN]}}, [("test-role", PANEL, 1, [
        PROPOSAL, {"title": "Real defect", "file": "a.py", "line": 4, "severity": "Important", "consequence": "c"}])])
    assert got == [("Real defect", 4)]


def test_a_gap_sweep_finding_sharing_a_passed_proposals_title_and_file_is_listed_open(tmp_path):
    """axis: the passed-proposal skip settles only the test role's panel proposal; a gap-sweep finding of the same title
    and file at another line stays open — see bite-proof record c1l1_wo_b_session_seam"""
    got = _abandoned_slots(tmp_path, {"1": {"breakItRuns": [PASSED_RUN]}}, [
        ("test-role", PANEL, 1, [PROPOSAL]), ("gap-sweep", GAPSWEEP, 1, [SAME_PLACE])])
    assert got == [("Break it", 9)]


def test_a_code_reviewer_finding_sharing_a_passed_proposals_title_and_file_is_listed_open(tmp_path):
    """axis: a code-reviewer panel finding of the same title and file as a passed proposal stays open."""
    got = _abandoned_slots(tmp_path, {"1": {"breakItRuns": [PASSED_RUN]}}, [
        ("test-role", PANEL, 1, [PROPOSAL]), ("code-reviewer", PANEL, 1, [SAME_PLACE])])
    assert got == [("Break it", 9)]


@pytest.mark.parametrize("seat,phase,rnd,raised,why", [
    ("test-role", PANEL, 1, dict(PROPOSAL, taxonomy="other"), "E1 a test-role finding that is not a break-it proposal"),
    ("test-role", PANEL, 1, {k: v for k, v in PROPOSAL.items() if k != "taxonomy"}, "E1 a test-role finding with no taxonomy"),
    ("code-reviewer", PANEL, 1, PROPOSAL, "E2 a break-it proposal from another seat"),
    ("test-role", GAPSWEEP, 1, PROPOSAL, "E3 a break-it proposal from the test role in a gap-sweep slot"),
    ("test-role", SCOPED, 1, PROPOSAL, "E3 a break-it proposal from the test role in a scoped-finder slot"),
    ("test-role", PANEL, 2, PROPOSAL, "E4 a passing run recorded for another round"),
])
def test_a_finding_the_passed_rule_does_not_cover_is_listed_open(tmp_path, seat, phase, rnd, raised, why):
    """axis: the passed-proposal skip needs the panel phase, the test-role seat, the break-it taxonomy and a passing run
    of the same round, title and file — see bite-proof record c1l1_wo_b_session_seam"""
    got = _abandoned_slots(tmp_path, {"1": {"breakItRuns": [PASSED_RUN]}}, [(seat, phase, rnd, [raised])])
    assert got == [("Break it", 1)], why


@pytest.mark.parametrize("phase,reopened", [
    (SCOPED, True),  # runs after the round's fix audit settled the finding: the defect came back
    (PANEL, False),  # runs before the round's fix: the settlement answers it
    (GAPSWEEP, False),
])
def test_a_same_round_report_after_the_settling_audit_reopens_the_finding_in_an_abandoned_session(tmp_path, phase, reopened):
    """axis: a finding settled (fixed) in round N and reported again in round N by a phase that runs after the audit
    (the scoped finder) reads open on abandonment; a same-round report from a phase before the fix does not."""
    s = Session(tmp_path, terminal=None, dispositionLedger=[ledger_row()], rounds={"1": {}, "2": {}})
    session = s.seat("code-reviewer", phase=phase, rnd=2).save()
    put_envelope(session, "code-reviewer", {"vendor": "codex", "model": CODEX, "payload": {"findings": [
        {"title": "t", "file": "a.py", "line": 3, "severity": "Important", "consequence": "c"}]}}, phase=phase, rnd=2)
    account = rs.account_from_session(session, extras(), Fake().readers(), abandoned=REASON)
    (row,) = [f for f in account["findings"] if f["findingKey"] == KEY]
    assert (row["outcome"] is None) is reopened, row
    assert (row["reason"] == rs.UNFOLDED_OPEN) is reopened, row


def test_the_record_writer_needs_a_reviewer_unless_the_account_is_abandoned(tmp_path):
    """axis: E5 — an empty reviewers list without abandoned is still review-account-invalid; a blank, missing-reason
    or non-dict abandoned is refused under its own name; a valid abandoned lets the empty list through."""
    session = Session(tmp_path, terminal="converged").seat("code-reviewer").save()
    base = rs.account_from_session(session, extras(), Fake().readers())
    assert "abandoned" not in base  # without --abandoned the account is what it was

    def attempt(**over):
        path = tmp_path / "account.json"
        path.write_text(json.dumps(dict(base, **over)))
        return rr.write(str(path), str(tmp_path), Fake().readers())

    out = attempt(reviewers=[])
    assert out["ok"] is False and out["reason"] == "review-account-invalid" and out["detail"] == "reviewers", out
    for bad in ({"reason": ""}, {"reason": "  "}, {"reason": 5}, {}, "owner stopped", ["x"]):
        out = attempt(reviewers=[], abandoned=bad)
        assert out["ok"] is False and out["reason"] == "review-account-invalid" and out["detail"] == "abandoned", (bad, out)
    out = attempt(abandoned={"reason": ""})  # a reviewer is listed; the blank reason alone refuses
    assert out["ok"] is False and out["detail"] == "abandoned", out
    assert attempt(reviewers=[], abandoned={"reason": REASON})["ok"] is True
    assert attempt(abandoned=None)["ok"] is True  # a null abandoned is the same as none


def test_main_passes_abandoned_through_to_write_from_session(tmp_path, monkeypatch):
    """axis: the CLI's --abandoned reaches write_from_session as abandoned=, and is None when the flag is absent."""
    seen = []
    monkeypatch.setattr(rs, "write_from_session", lambda *a, **k: seen.append((a, k)) or {"ok": True})
    argv = ["write", "--session-dir", "d", "--extras", "e", "--repo-root", "r"]
    assert rs.main(argv + ["--abandoned", "x"]) == 0
    assert rs.main(argv) == 0
    assert seen[0] == (("d", "e", "r"), {"abandoned": "x"})
    assert seen[1] == (("d", "e", "r"), {"abandoned": None})
