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

from test_review_record_session import (  # noqa: E402
    CODEX, EARLIER, GOOD_RUN, HEAD, KEY, Fake, Session, extras, ledger_row, put_envelope, put_extras, raw_comments,
)

REASON = "owner stopped the loop"
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


def _abandoned_titles(tmp_path, rounds, raised):
    session = Session(tmp_path, terminal=None, rounds=rounds).seat("code-reviewer").save()
    put_envelope(session, "code-reviewer", {"vendor": "codex", "model": CODEX, "payload": {"findings": raised}})
    account = rs.account_from_session(session, extras(), Fake().readers(), abandoned=REASON)
    return [(f["title"], f["line"]) for f in account["findings"]]


def test_a_same_titled_finding_at_another_line_survives_a_compile_drop_in_an_abandoned_session(tmp_path):
    """axis: the compile-drop match includes the line, so only the dropped location is left out of the unfolded rows."""
    drop = {"title": "Same title", "file": "a.py", "line": 10, "reason": "out of scope"}
    got = _abandoned_titles(tmp_path, {"1": {"compileDrops": [drop]}}, [
        {"title": "Same title", "file": "a.py", "line": 10, "severity": "Important", "consequence": "c"},
        {"title": "Same title", "file": "a.py", "line": 20, "severity": "Important", "consequence": "c"}])
    assert got == [("Same title", 20)]


def test_a_passing_break_it_proposal_is_not_recovered_as_an_open_finding_in_an_abandoned_session(tmp_path):
    """axis: a proposal whose break-it test passed was dropped before compile and is not listed open on abandonment."""
    run = {"title": "Break it", "file": "tests/test_x.py", "outcome": "passed", "findingKey": None}
    got = _abandoned_titles(tmp_path, {"1": {"breakItRuns": [run]}}, [
        {"title": "Break it", "file": "tests/test_x.py", "line": 1, "severity": "Important", "consequence": "c"},
        {"title": "Real defect", "file": "a.py", "line": 4, "severity": "Important", "consequence": "c"}])
    assert got == [("Real defect", 4)]


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
