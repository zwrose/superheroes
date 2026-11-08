"""#2395: a review record written from a session that did not converge never reads reviewed; its whatIsMissing names
the withheld certificate and its cause."""
import copy
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import decision_kinds  # noqa: E402
import pr_sheet  # noqa: E402
import review_record as rr  # noqa: E402
import review_record_session as rs  # noqa: E402

from test_review_record_session import (  # noqa: E402
    GOOD_RUN, HEAD, OOS, Fake, Session, extras, ledger_row, put_extras,
)
from test_pr_sheet import WORDS, load  # noqa: E402

REASON = "kept break-it check errored at setup"
LINE_START = "the review session ended"
# every verdict a session can end on but converged; the census test holds this list against decision_kinds
UNCERTIFIED_TERMINALS = ("halted", "held", "stalled", "cannot-certify", "capped-with-open-critical",
                         "capped-with-open-blocker", "handed-back")
# a decision kind each terminal's cause mapping accepts (the round-cap mapping needs one for handed-back)
LAST_KIND = {"handed-back": "round-cap", "halted": "round-ceiling"}


def _ended(root, terminal, certification=None, decisions=(), ledger=None, **state):
    """Every reviewed condition holds (the one finding fixed, a maker named, one planned reviewer that ran on the final
    commit, CI green): only the session's terminal differs."""
    s = Session(root, terminal=terminal, dispositionLedger=ledger or [ledger_row()], decisions=list(decisions),
                seatMapReceipts=[{"round": "1", "map": {"seats": {}, "makerFamilies": ["xai"]}}], **state)
    if certification is not None:
        s.state["certification"] = certification
    s.seat("code-reviewer", head=HEAD, nonce="n1")
    runs = {"/run/n1": (dict(GOOD_RUN, runnerNonce="n1", viewHeadSha=HEAD), None)}
    return s.save(), Fake(runs=runs), {"ci": "green", "runDirs": ["/run/n1"]}


def _sub(tmp_path, name):
    root = tmp_path / name
    root.mkdir()
    return root


def _write(tmp_path, session, fake, body, **over):
    return rs.write_from_session(session, put_extras(tmp_path, extras(**body, **over)), str(tmp_path), fake.readers())


def _cert(reason):
    return {"shape": None, "reason": reason}


def _record(tmp_path, terminal, certification=None, decisions=(), ledger=None):
    session, fake, body = _ended(tmp_path, terminal, certification, decisions, ledger)
    out = _write(tmp_path, session, fake, body)
    assert out["ok"], out
    return out, rr.read(7, readers=fake.readers())


def test_a_cannot_certify_session_with_every_other_line_clear_reads_not_reviewed(tmp_path):
    """axis: E-line — the withheld-certificate line alone keeps a record not-reviewed; the same session ended converged reads reviewed."""
    ctl_session, ctl_fake, ctl_body = _ended(_sub(tmp_path, "ctl"), "converged", _cert(REASON))
    assert _write(tmp_path, ctl_session, ctl_fake, ctl_body)["status"] == "reviewed"
    out, rec = _record(tmp_path, "cannot-certify", _cert(REASON))
    line = rr.uncertified_line({"terminal": "cannot-certify", "reason": REASON})
    assert out["status"] == rec["status"] == "not-reviewed"
    assert rec["whatIsMissing"] == [line]
    assert "cannot-certify" in line and REASON in line
    assert not rr.cleared(rec["status"])
    assert rec["uncertified"] == {"terminal": "cannot-certify", "reason": REASON, "source": "session"}


@pytest.mark.parametrize("terminal", UNCERTIFIED_TERMINALS)
def test_every_terminal_but_converged_reads_not_reviewed_and_names_itself(tmp_path, terminal):
    """axis: E-account — the session writer carries the terminal and the driver's reason for each non-converged terminal."""
    kind = LAST_KIND.get(terminal)
    decisions = [{"round": 1, "kind": kind, "detail": "the driver's last word"}] if kind else []
    _, rec = _record(tmp_path, terminal, _cert(f"{terminal} for a stated cause"), decisions)
    assert rec["status"] == "not-reviewed" and not rr.cleared(rec["status"])
    (line,) = [m for m in rec["whatIsMissing"] if m.startswith(LINE_START)]
    assert line.startswith(f"{LINE_START} {terminal}, not converged") and f"{terminal} for a stated cause" in line
    assert rec["uncertified"] == {"terminal": terminal, "reason": f"{terminal} for a stated cause", "source": "session"}


def test_the_census_of_verdicts_is_covered():
    """axis: a verdict added to the vocabulary fails here until a test covers it."""
    assert set(decision_kinds.ALL_VERDICTS) - {"converged"} == set(UNCERTIFIED_TERMINALS) | {"uncertified-manual"}
    assert set(UNCERTIFIED_TERMINALS) == set(decision_kinds.CERTIFIED_VERDICTS) - {"converged"}


ATTESTATION = {"failure": "the seat result was unreadable", "kind": "driver-error", "class": "seat-defect",
               "phase": "dispatch-panel", "event": "submit", "note": None, "attestedAt": "2026-11-08T00:00:00Z",
               "stateSchemaVersion": 1}
DRIVER_TEXT = ("attested by hand over a driver failure (kind driver-error, class seat-defect, phase dispatch-panel, "
               "failure the seat result was unreadable)")


def _attested(tmp_path, name, attestation=ATTESTATION):
    """A session the driver ended on its attested manual terminal: no certification, an `_attestation` block."""
    state = {} if attestation is None else {"_attestation": attestation}
    session, fake, body = _ended(_sub(tmp_path, name), "uncertified-manual", **state)
    return session, fake, body


def _hand(tmp_path, name, uncertified, **keyword):
    """A hand-written account (a converged session's account with the given `uncertified`) handed to the record writer."""
    root = _sub(tmp_path, name)
    session, fake, body = _ended(root, "converged")
    account = rs.account_from_session(session, extras(**body), fake.readers())
    path = root / "account.json"
    path.write_text(json.dumps(dict(account, uncertified=uncertified)))
    return rr.write(str(path), str(tmp_path), fake.readers(), **keyword), fake


def test_an_attested_session_writes_not_reviewed_with_the_drivers_text(tmp_path):
    """axis: E-attested — the session writer stamps an uncertified-manual session itself, so its record reads not-reviewed whatever the extras say."""
    session, fake, body = _attested(tmp_path, "att")
    out = _write(tmp_path, session, fake, body)
    assert out["ok"] is True and out["status"] == "not-reviewed", out
    rec = rr.read(7, readers=fake.readers())
    (line,) = rec["whatIsMissing"]
    assert rec["status"] == "not-reviewed" and not rr.cleared(rec["status"])
    assert line == rr.uncertified_line({"terminal": "uncertified-manual", "reason": DRIVER_TEXT})
    assert "uncertified-manual" in line and DRIVER_TEXT in line
    assert rec["uncertified"] == {"terminal": "uncertified-manual", "reason": DRIVER_TEXT, "note": None, "source": "session"}


def test_the_attestation_note_is_kept_as_data_and_never_enters_the_summary(tmp_path):
    """axis: E-note — the human's attestation note is in the record's uncertified.note and in no summary line."""
    note = "the owner says it is bug-free"
    session, fake, body = _attested(tmp_path, "att", dict(ATTESTATION, note=note))
    out = _write(tmp_path, session, fake, body)
    assert out["ok"] is True and out["status"] == "not-reviewed", out
    rec = rr.read(7, readers=fake.readers())
    assert rec["uncertified"]["note"] == note and rec["uncertified"]["source"] == "session"
    for level in (0, 1):
        assert note not in rr._summary(rec, level), level
    assert not any(note in m for m in rec["whatIsMissing"])


@pytest.mark.parametrize("attestation", [None, "text", 5, ["x"], {}, {"failure": " ", "kind": 3, "class": None}])
def test_an_attestation_with_no_usable_field_still_writes_not_reviewed_with_no_reason(tmp_path, attestation):
    """axis: G1 — a missing, non-dict or empty _attestation leaves the reason None; the record still reads not-reviewed."""
    session, fake, body = _attested(tmp_path, "att", attestation)
    assert rs.account_from_session(session, extras(**body), fake.readers())["uncertified"] == {
        "terminal": "uncertified-manual", "reason": None, "note": None}
    out = _write(tmp_path, session, fake, body)
    assert out["ok"] is True and out["status"] == "not-reviewed", out
    assert rr.read(7, readers=fake.readers())["whatIsMissing"][0].endswith(": no reason recorded")


def test_an_attestation_names_only_the_fields_it_has_and_a_note_that_is_not_text_is_none(tmp_path):
    """axis: G4 — the driver text leaves out a missing field; a note that is not a string is None."""
    session, fake, body = _attested(tmp_path, "att", {"class": "seat-defect", "failure": "  boom  ", "note": 5})
    assert rs.account_from_session(session, extras(**body), fake.readers())["uncertified"] == {
        "terminal": "uncertified-manual", "note": None,
        "reason": "attested by hand over a driver failure (class seat-defect, failure boom)"}


@pytest.mark.parametrize("bad", ["bug-free", "mystery", "", None, 5])
def test_a_hand_account_terminal_is_one_of_the_drivers_verdicts_but_converged(tmp_path, bad):
    """axis: E-vocab — a terminal that is not a driver verdict is refused; each verdict but converged is accepted."""
    out, fake = _hand(tmp_path, "bad", {"terminal": bad, "reason": None})
    assert out["ok"] is False and out["reason"] == "review-account-invalid" and out["detail"] == "uncertified", out
    assert fake.comments == []


def test_every_driver_verdict_but_converged_is_accepted_in_a_hand_account(tmp_path):
    """axis: E-vocab — the accepted terminals are exactly the driver's verdicts other than converged."""
    for i, terminal in enumerate(sorted(set(decision_kinds.ALL_VERDICTS) - {"converged"})):
        out, fake = _hand(tmp_path, f"ok{i}", {"terminal": terminal, "reason": "a clean cause"})
        assert out["ok"] is True and out["status"] == "not-reviewed", (terminal, out)
        assert rr.read(7, readers=fake.readers())["uncertified"]["terminal"] == terminal
    out, _ = _hand(tmp_path, "conv", {"terminal": "converged", "reason": None})
    assert out["ok"] is False and out["detail"] == "uncertified", out


@pytest.mark.parametrize("bad", [
    {"terminal": "halted", "reason": None, "source": "session"}, {"terminal": "halted", "reason": None, "extra": 1},
    {"terminal": "halted", "reason": None, "note": 5}, {"terminal": "halted", "reason": None, "note": ["x"]},
])
def test_a_hand_account_with_a_stray_key_or_a_note_that_is_not_text_is_refused(tmp_path, bad):
    """axis: G3/G4 — a hand account cannot carry source or any other key in uncertified, nor a note that is not text."""
    out, fake = _hand(tmp_path, "bad", bad)
    assert out["ok"] is False and out["reason"] == "review-account-invalid" and out["detail"] == "uncertified", out
    assert fake.comments == []


def test_a_hand_accounts_withheld_entry_is_claim_checked_but_the_sessions_is_not(tmp_path):
    """axis: E-source — only an entry the session writer stamped is exempt from the claim check."""
    cause = "the kept bug-free check errored at setup"
    out, fake = _hand(tmp_path, "hand", {"terminal": "cannot-certify", "reason": cause})
    assert out["ok"] is False and out["reason"] == "review-record-forbidden-claim", out
    assert fake.comments == []
    _, rec = _record(_sub(tmp_path, "sess"), "cannot-certify", _cert(cause))  # the session-written record with the same cause
    assert rec["status"] == "not-reviewed" and cause in rec["whatIsMissing"][0] and rec["uncertified"]["source"] == "session"


def test_a_hand_account_with_a_clean_reason_writes_not_reviewed_from_the_account(tmp_path):
    """axis: the control — a clean hand account writes, reads not-reviewed, and is marked as from the account; a keyword that differs from it grants no exemption."""
    entry = {"terminal": "uncertified-manual", "reason": "the owner attested the review by hand"}
    out, fake = _hand(tmp_path, "clean", entry)
    assert out["ok"] is True and out["status"] == "not-reviewed", out
    rec = rr.read(7, readers=fake.readers())
    assert rec["whatIsMissing"] == [rr.uncertified_line(entry)] and rec["uncertified"] == dict(entry, source="account")
    out, fake = _hand(tmp_path, "differs", entry, session_uncertified={"terminal": "uncertified-manual", "reason": "other"})
    assert out["ok"] is True and rr.read(7, readers=fake.readers())["uncertified"]["source"] == "account"
    out, fake = _hand(tmp_path, "same", entry, session_uncertified=dict(entry))
    assert out["ok"] is True and rr.read(7, readers=fake.readers())["uncertified"]["source"] == "session"


def test_an_attested_session_with_no_seat_result_is_still_unsupported(tmp_path):
    """axis: G5 — the no-seat-result refusal is unchanged for an uncertified-manual terminal."""
    s = Session(_sub(tmp_path, "noseat"), terminal="uncertified-manual", _attestation=ATTESTATION).save()
    out = rs.write_from_session(s, put_extras(tmp_path, extras(ci="green")), str(tmp_path), Fake().readers())
    assert out["ok"] is False and out["reason"] == rs.UNSUPPORTED == "review-session-unsupported", out
    out = rs.write_from_session(Session(_sub(tmp_path, "unknown"), terminal="mystery").seat("code-reviewer").save(),
                                put_extras(tmp_path, extras(ci="green")), str(tmp_path), Fake().readers())
    assert out["ok"] is False and out["reason"] == "review-session-unsupported", out


def test_a_converged_session_is_unchanged(tmp_path):
    """axis: E4 — a converged session's account and record carry no uncertified key and no withheld-certificate line."""
    session, fake, body = _ended(_sub(tmp_path, "acct"), "converged", _cert("a reason the converged record ignores"))
    assert "uncertified" not in rs.account_from_session(session, extras(**body), fake.readers())
    _, rec = _record(tmp_path, "converged", _cert("a reason the converged record ignores"))
    assert "uncertified" not in rec and rec["status"] == "reviewed"
    assert not any(m.startswith(LINE_START) for m in rec["whatIsMissing"]) and rec["whatIsMissing"] == []


def test_a_reason_naming_a_forbidden_claim_still_writes_and_keeps_its_cause_in_the_line(tmp_path):
    """axis: E-mask — the line's literal cause is left out of the claim check; the record writes and reads not-reviewed."""
    cause = "the kept bug-free check errored at setup"
    _, rec = _record(tmp_path, "cannot-certify", _cert(cause))
    assert rec["status"] == "not-reviewed" and not rr.cleared(rec["status"])
    assert rec["whatIsMissing"] == [rr.uncertified_line({"terminal": "cannot-certify", "reason": cause})]
    assert cause in rec["whatIsMissing"][0]
    # only that line is masked: the same claim in another line of the summary is still refused
    session, fake, body = _ended(_sub(tmp_path, "other"), "cannot-certify", _cert(cause))
    out = _write(tmp_path, session, fake, body, laneReason="a bug-free change")
    assert out["ok"] is False and out["reason"] == "review-record-forbidden-claim", out


def test_a_long_reason_shortened_by_redaction_still_writes_and_keeps_the_line(tmp_path):
    """axis: E-displayed — the exemption is the entry as displayed (clipped before the scrub), not a line regenerated from the scrubbed reason."""
    # a token shape the record's scrub replaces in place (an assignment shape would be withheld whole), built from pieces
    secret = "gh" + "p_" + "A" * 36
    reason = "the kept bug-free check errored at setup " + secret + " " + "y" * 400
    assert len(reason) > 300
    out, rec = _record(tmp_path, "cannot-certify", _cert(reason))
    assert out["status"] == rec["status"] == "not-reviewed" and not rr.cleared(rec["status"])
    (line,) = [m for m in rec["whatIsMissing"] if m.startswith(rr.UNCERTIFIED_OPENING)]
    assert len(rec["whatIsMissing"]) == 1 and "bug-free" in line


def test_a_missing_reason_reads_no_reason_recorded_and_a_long_one_is_clipped(tmp_path):
    """axis: E1/E2/E6 — the reason falls back to the last decision's detail, then to none; the cause is clipped."""
    _, rec = _record(_sub(tmp_path, "none"), "cannot-certify", None)  # no certification, no decisions
    assert rec["whatIsMissing"][0].endswith(": no reason recorded") and rec["uncertified"]["reason"] is None
    for i, odd in enumerate((None, "text", {"shape": None}, {"shape": None, "reason": None}, {"shape": None, "reason": "  "},
                             {"shape": None, "reason": 5})):
        s = Session(_sub(tmp_path, f"odd{i}"), terminal="stalled", certification=odd,
                    decisions=[{"round": 1, "kind": "x", "detail": "the last decision's detail"}]).seat("code-reviewer").save()
        assert rs.account_from_session(s, extras(), Fake().readers())["uncertified"] == {
            "terminal": "stalled", "reason": "the last decision's detail"}, odd
        s2 = Session(_sub(tmp_path, f"nodec{i}"), terminal="stalled",
                     certification=odd).seat("code-reviewer").save()
        assert rs.account_from_session(s2, extras(), Fake().readers())["uncertified"] == {"terminal": "stalled", "reason": None}, odd
    s3 = Session(_sub(tmp_path, "blankdetail"), terminal="stalled", certification=_cert(" "),
                 decisions=[{"round": 1, "kind": "x", "detail": "  "}]).seat("code-reviewer").save()
    assert rs.account_from_session(s3, extras(), Fake().readers())["uncertified"]["reason"] is None
    long = "x" * 400
    line = rr.uncertified_line({"terminal": "halted", "reason": long})
    cause = line.split("withheld: ", 1)[1]
    assert len(cause) == rr.BASIS_TEXT_MAX == 300 and cause.endswith("…") and cause[:-1] == "x" * 299
    assert rr.uncertified_line({"terminal": "halted", "reason": "  spaced  "}).endswith("withheld: spaced")
    assert rr.uncertified_line({"terminal": "halted", "reason": "   "}).endswith("withheld: no reason recorded")
    _, rec = _record(_sub(tmp_path, "long"), "halted", _cert(long))
    assert rec["whatIsMissing"] == [line]


@pytest.mark.parametrize("bad", [
    {"terminal": "converged", "reason": "x"}, {"terminal": "", "reason": "x"}, {"terminal": "  ", "reason": "x"},
    {"terminal": None, "reason": "x"}, {"reason": "x"}, {"terminal": "halted", "reason": 5},
    {"terminal": "halted", "reason": ["x"]}, "halted", ["halted"], {},
])
def test_a_hand_account_with_a_bad_uncertified_is_refused(tmp_path, bad):
    """axis: E7 — uncertified is a dict with a non-blank terminal other than converged and a null or text reason."""
    session, fake, body = _ended(tmp_path, "converged")
    account = rs.account_from_session(session, extras(**body), fake.readers())
    path = tmp_path / "account.json"
    path.write_text(json.dumps(dict(account, uncertified=bad)))
    out = rr.write(str(path), str(tmp_path), fake.readers())
    assert out["ok"] is False and out["reason"] == "review-account-invalid" and out["detail"] == "uncertified", out
    assert fake.comments == []
    for good in (None, {"terminal": "halted", "reason": None}, {"terminal": "halted", "reason": "why"}):
        path.write_text(json.dumps(dict(account, uncertified=good)))
        assert rr.write(str(path), str(tmp_path), fake.readers())["ok"] is True, good


def test_a_hand_back_with_only_a_leftover_beside_it_reads_not_reviewed_never_awaits_owner(tmp_path):
    """axis: E8 — the withheld-certificate line is not a leftover line, so a hand-back's leftovers never make it awaits-owner."""
    ctl_session, ctl_fake, ctl_body = _ended(_sub(tmp_path, "ctl"), "converged", ledger=[ledger_row(**OOS)])
    ctl = _write(tmp_path, ctl_session, ctl_fake, ctl_body)
    assert ctl["status"] == "awaits-owner", ctl  # the same session ended converged: the leftover alone waits for the owner
    decisions = [{"round": 1, "kind": "round-cap", "detail": "the round cap was reached"}]
    _, rec = _record(tmp_path, "handed-back", _cert("the round cap was reached"), decisions, ledger=[ledger_row(**OOS)])
    assert rec["leftForOwner"], rec
    assert rec["status"] == "not-reviewed" and rec["rounds"]["stoppedAtCap"] is True
    assert any(m.startswith(LINE_START + " handed-back") for m in rec["whatIsMissing"])
    assert not rr.cleared(rec["status"])


def test_the_sheet_holds_the_line_in_its_history_beside_the_owners_go_ahead_card(tmp_path):
    """axis: the PR sheet shows the withheld-certificate line as an incomplete record line, and the go-ahead card is on it."""
    _, rec = _record(tmp_path, "cannot-certify", _cert(REASON))
    line = rec["whatIsMissing"][0]
    records = [copy.deepcopy(load("record-small.json"))]
    records[0].update(status=rec["status"], whatIsMissing=rec["whatIsMissing"])
    advisor = copy.deepcopy(load("input-small.json"))
    # one item about the withheld certificate, in the shape the fixture's items use
    advisor["items"] = [{
        "id": "uncertified-go-ahead", "kind": "Behavior change", "title": "Proceed without the withheld certificate?",
        "ifLeft": line,
        "options": [
            {"id": "proceed", "label": "Proceed", "consequence": "The PR goes ahead without a review certificate.",
             "sendsBack": False},
            {"id": "send-back", "label": "Send it back", "consequence": "The PR goes back for another review session.",
             "sendsBack": True}],
        "recommendation": {"text": "Send it back", "reason": "The review never converged.", "optionId": "send-back"}}]
    sheet = pr_sheet.build(records, advisor, WORDS)
    expected = pr_sheet._fill(WORDS["historyIncomplete"], what=line)
    assert expected == f"The review record is incomplete: {line}."
    assert expected in sheet["prSheet"]["history"]
    (card,) = [c for c in sheet["cards"] if c["question"] == "Proceed without the withheld certificate?"]
    assert line in json.dumps(card)
