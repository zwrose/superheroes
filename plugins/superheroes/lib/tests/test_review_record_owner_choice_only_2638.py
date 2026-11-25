"""#2638: a review record written from a session the driver ended `handed-back` / `owner-choice-open`, whose certification
carries `ownerChoiceOnly`, leaves the withheld-certificate line out of `whatIsMissing` exactly when every finding has an
outcome, at least one waits for the owner, and the entry is the session's own; every other record keeps the line.

Bite-proof record: i2638_owner_choice_only
"""
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
import test_round_driver as TRD  # noqa: E402

from test_c1l4_gates_retired import _CHOICE, _CHOICE_KEY, _reviewer  # noqa: E402
from test_pr_sheet import WORDS, load  # noqa: E402
from test_review_record_session import (  # noqa: E402
    GOOD_RUN, HEAD, OOS, Fake, Session, extras, ledger_row, put_extras,
)
from test_review_record_uncertified_2395 import LINE_START, _ended, _hand, _sub, _write  # noqa: E402

REASON = "the owner's choices are all that is left"
OWNER_CHOICE = [{"round": 1, "kind": "owner-choice-open", "detail": "1 finding(s) need the owner's choice"}]
ONLY = {"shape": None, "reason": REASON, "ownerChoiceOnly": True}
# every handed-back decision kind but the owner-choice one; the census test holds this list against the cause table
OTHER_HANDBACK_KINDS = ("round-cap", "fix-keeps-failing", "extra-audit-open", "bounded-pass-open", "fix-surface-unknown",
                        "break-it-restore-failed", "later-round-panel-retired")

_STATE = []


def _driven_state():
    """The state the real loop leaves when a reviewer raises one finding only the owner can choose (read once, copied)."""
    if not _STATE:
        _r, state = TRD._run_loop_capturing_state(TRD._seams(reviewer=_reviewer([_CHOICE])), TRD._cfg_cert())
        _STATE.append(state)
    return copy.deepcopy(_STATE[0])


def _from_state(root, state, **over):
    """A session directory built from a driven state, every other reviewed condition holding as `_ended` makes them."""
    st = dict(state, seatMapReceipts=[{"round": "1", "map": {"seats": {}, "makerFamilies": ["xai"]}}], **over)
    s = Session(root, **copy.deepcopy(st))
    s.seat("code-reviewer", head=HEAD, nonce="n1")
    runs = {"/run/n1": (dict(GOOD_RUN, runnerNonce="n1", viewHeadSha=HEAD), None)}
    return s.save(), Fake(runs=runs), {"ci": "green", "runDirs": ["/run/n1"]}


def _driven(tmp_path, name, **over):
    state = _driven_state()
    session, fake, body = _from_state(_sub(tmp_path, name), state, **over)
    out = _write(tmp_path, session, fake, body)
    assert out["ok"], out
    return state, out, rr.read(7, readers=fake.readers()), fake


def _line(rec):
    return rr.uncertified_line(rec["uncertified"])


def test_r1_a_driver_ended_owner_choice_only_session_reads_awaits_owner_with_no_withheld_line(tmp_path):
    """axis: R1 — the real loop's owner-choice hand-back carrying ownerChoiceOnly, written through the session writer,
    reads awaits-owner: the withheld-certificate line is gone, the held finding is the one open line."""
    state, out, rec, fake = _driven(tmp_path, "r1")
    cert = state["certification"]
    assert state["terminal"] == "handed-back" and state["decisions"][-1]["kind"] == "owner-choice-open"
    assert cert["ownerChoiceOnly"] is True and "ownerChoiceGap" not in cert, cert
    assert out["status"] == rec["status"] == "awaits-owner", (out, rec["whatIsMissing"])
    assert rec["whatIsMissing"] and not any(m.startswith(LINE_START) for m in rec["whatIsMissing"])
    assert all(m.startswith("finding ") or "owner" in m for m in rec["whatIsMissing"]), rec["whatIsMissing"]
    assert rec["leftForOwner"] == [_CHOICE_KEY]
    assert rec["uncertified"] == {"terminal": "handed-back", "reason": cert["reason"], "ownerChoiceOnly": True,
                                  "source": "session"}
    assert LINE_START not in fake.marked()[0]["body"]


def test_r2_the_sheet_history_holds_the_leftover_line_and_no_incomplete_line_for_the_owner_choice_record(tmp_path):
    """axis: R2 — the PR sheet built from the R1 record shows the leftover line and no incomplete-record line; the same
    record with the withheld-certificate line put back shows the incomplete line (the A/B)."""
    _state, _out, rec, _fake = _driven(tmp_path, "r2")
    assert rec["status"] == "awaits-owner"
    prefix = WORDS["historyIncomplete"].split("{what}")[0]
    advisor = copy.deepcopy(load("input-small.json"))
    # the sheet asks for the held finding's own card entry (no go-ahead item: the record holds no withheld-certificate line)
    (held_finding,) = [f for f in rec["findings"] if rr.waits_for_owner(f, rec["findings"])]
    advisor["leftovers"] = {held_finding["findingKey"]: {"why": "w", "context": "c", "options": "none"}}

    def history(status, missing):
        records = [copy.deepcopy(load("record-small.json"))]
        # the record's own findings ride along: the sheet counts a missing line as the owner's leftover only when a finding of the record holds it
        records[0].update(status=status, whatIsMissing=missing, findings=copy.deepcopy(rec["findings"]))
        return pr_sheet.build(records, copy.deepcopy(advisor), WORDS)["prSheet"]["history"]

    held = history(rec["status"], rec["whatIsMissing"])
    leftover = [WORDS["historyLeftover"], pr_sheet._fill(WORDS["historyLeftovers"], count=len(rec["whatIsMissing"]))]
    assert any(h in leftover for h in held), held
    assert not any(h.startswith(prefix) for h in held), held
    back = history("not-reviewed", [_line(rec)] + rec["whatIsMissing"])
    assert pr_sheet._fill(WORDS["historyIncomplete"], what=_line(rec)) in back, back


def test_r3_an_important_finding_with_no_outcome_keeps_the_withheld_line(tmp_path):
    """axis: R3 — the owner-choice-only session plus an Important finding with no outcome reads not-reviewed and holds the
    withheld-certificate line (the entry still carries the stamp: the finding alone keeps the line)."""
    state = _driven_state()
    undecided = ledger_row(key="g.py::undecided@L9", id="f-9", title="undecided", file="g.py", line=9, disposition=None)
    _, _, rec, _ = _driven(tmp_path, "r3", dispositionLedger=state["dispositionLedger"] + [undecided])
    assert rec["status"] == "not-reviewed"
    assert any(f["outcome"] is None for f in rec["findings"]), rec["findings"]
    assert rec["leftForOwner"], rec
    assert rec["uncertified"]["ownerChoiceOnly"] is True and rec["uncertified"]["source"] == "session"
    assert _line(rec) in rec["whatIsMissing"]
    assert any(m.endswith("has no outcome") for m in rec["whatIsMissing"]), rec["whatIsMissing"]


def test_r4_a_gap_certification_without_the_stamp_keeps_the_withheld_line(tmp_path):
    """axis: R4 — the same session whose certification carries ownerChoiceGap and no ownerChoiceOnly reads not-reviewed
    and holds the withheld-certificate line; its entry carries no ownerChoiceOnly."""
    cert = {"shape": None, "reason": REASON, "ownerChoiceGap": "fix owed: a fix was approved and never run"}
    _, _, rec, _ = _driven(tmp_path, "r4", certification=cert)
    assert rec["status"] == "not-reviewed" and rec["leftForOwner"], rec
    assert "ownerChoiceOnly" not in rec["uncertified"] and rec["uncertified"]["source"] == "session"
    assert _line(rec) in rec["whatIsMissing"]


def test_r5_no_finding_waiting_for_the_owner_keeps_the_withheld_line(tmp_path):
    """axis: R5 — an owner-choice-only entry with every finding fixed (none waits for the owner) keeps the line and reads
    not-reviewed."""
    session, fake, body = _ended(_sub(tmp_path, "r5"), "handed-back", ONLY, OWNER_CHOICE, [ledger_row()])
    assert _write(tmp_path, session, fake, body)["ok"]
    rec = rr.read(7, readers=fake.readers())
    assert rec["status"] == "not-reviewed" and rec["leftForOwner"] == [], rec
    assert rec["uncertified"] == {"terminal": "handed-back", "reason": REASON, "ownerChoiceOnly": True, "source": "session"}
    assert _line(rec) in rec["whatIsMissing"]


def test_r6_a_hand_written_entry_with_the_flag_keeps_the_line_and_the_sessions_own_does_not(tmp_path):
    """axis: R6 — a hand-written account's uncertified entry carrying ownerChoiceOnly keeps the withheld-certificate line
    (source `account`); the same entry the session writer handed over as its own lifts it (the A/B)."""
    entry = {"terminal": "handed-back", "reason": REASON, "ownerChoiceOnly": True}

    def written(name, **keyword):
        root = _sub(tmp_path, name)
        session, fake, body = _ended(root, "converged", ledger=[ledger_row(**OOS)])
        account = rs.account_from_session(session, extras(**body), fake.readers())
        path = root / "account.json"
        path.write_text(json.dumps(dict(account, uncertified=entry)))
        out = rr.write(str(path), str(tmp_path), fake.readers(), **keyword)
        assert out["ok"] is True, out
        return rr.read(7, readers=fake.readers())

    hand = written("hand")
    assert hand["uncertified"] == dict(entry, source="account") and hand["leftForOwner"]
    assert hand["status"] == "not-reviewed" and _line(hand) in hand["whatIsMissing"]
    own = written("own", session_uncertified=dict(entry))
    assert own["uncertified"]["source"] == "session"
    assert own["status"] == "awaits-owner" and not any(m.startswith(LINE_START) for m in own["whatIsMissing"])


@pytest.mark.parametrize("bad", [
    {"terminal": "handed-back", "reason": None, "ownerChoiceOnly": False},
    {"terminal": "handed-back", "reason": None, "ownerChoiceOnly": 1},
    {"terminal": "handed-back", "reason": None, "ownerChoiceOnly": "true"},
    {"terminal": "handed-back", "reason": None, "ownerChoiceOnly": None},
    {"terminal": "cannot-certify", "reason": None, "ownerChoiceOnly": True},
    {"terminal": "uncertified-manual", "reason": None, "ownerChoiceOnly": True},
])
def test_r7_the_validator_refuses_any_ownerchoiceonly_but_true_on_handed_back(tmp_path, bad):
    """axis: R7 — ownerChoiceOnly of false, 1, "true", null, or on any terminal but handed-back is refused
    review-account-invalid at `uncertified`."""
    out, fake = _hand(tmp_path, "bad", bad)
    assert out["ok"] is False and out["reason"] == "review-account-invalid" and out["detail"] == "uncertified", out
    assert fake.comments == []


def test_r7_the_validator_accepts_true_on_handed_back(tmp_path):
    """axis: R7 — ownerChoiceOnly true on a handed-back entry is accepted, and the entry is kept with it."""
    out, fake = _hand(tmp_path, "good", {"terminal": "handed-back", "reason": None, "ownerChoiceOnly": True})
    assert out["ok"] is True, out
    assert rr.read(7, readers=fake.readers())["uncertified"]["ownerChoiceOnly"] is True


@pytest.mark.parametrize("kind", OTHER_HANDBACK_KINDS)
def test_r8_every_other_hand_back_kind_never_takes_the_stamp_and_keeps_the_line(tmp_path, kind):
    """axis: R8 — a handed-back session with another decision kind, even with a certification wrongly carrying
    ownerChoiceOnly, has no ownerChoiceOnly in its entry and keeps the withheld-certificate line."""
    decisions = [{"round": 1, "kind": kind, "detail": "the driver's last word"}]
    session, fake, body = _ended(_sub(tmp_path, "r8"), "handed-back", ONLY, decisions, [ledger_row(**OOS)])
    assert "ownerChoiceOnly" not in rs.account_from_session(session, extras(**body), fake.readers())["uncertified"]
    assert _write(tmp_path, session, fake, body)["ok"]
    rec = rr.read(7, readers=fake.readers())
    assert rec["leftForOwner"] and rec["status"] == "not-reviewed"
    assert "ownerChoiceOnly" not in rec["uncertified"] and _line(rec) in rec["whatIsMissing"]


def test_r8_census_the_listed_kinds_are_every_handed_back_kind_but_the_owner_choice_one():
    """axis: R8 — a handed-back decision kind added to the cause table fails here until it is listed."""
    kinds = {kind for verdict, kind in decision_kinds._TERMINAL_CAUSE_TABLE if verdict == "handed-back"}
    assert kinds - {"owner-choice-open"} == set(OTHER_HANDBACK_KINDS), kinds
    assert "owner-choice-open" in kinds
