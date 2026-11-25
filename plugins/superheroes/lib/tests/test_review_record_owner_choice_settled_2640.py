"""#2640: a review record for the session's own owner-choice-only hand-back (`handed-back` / `owner-choice-open`, the driver's
`ownerChoiceOnly` stamp) whose every finding the session left for the owner now reads `ruling` through a resolving
owner-ruling citation, with every other finding keeping the outcome the session gave it, leaves the withheld-certificate line
out and reads `reviewed`; every other record keeps the line as before.

Bite-proof record: i2640_owner_choice_settled
"""
import copy
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import pr_sheet  # noqa: E402
import review_record as rr  # noqa: E402
import review_record_session as rs  # noqa: E402

from test_c1l4_gates_retired import _CHOICE_KEY  # noqa: E402
from test_pr_sheet import WORDS, load  # noqa: E402
from test_review_record_carried_recheck import entry as carried_entry  # noqa: E402
from test_review_record_owner_choice_only_2638 import (  # noqa: E402
    ONLY, OTHER_HANDBACK_KINDS, OWNER_CHOICE, REASON, _driven_state, _from_state,
)
from test_review_record_owner_ruling import DOC, U, W  # noqa: E402
from test_review_record_session import (  # noqa: E402
    GOOD_RUN, HEAD, KEY, OOS, Fake, Session, _by_key, _first_record, extras, ledger_row, put_extras,
)
from test_review_record_uncertified_2395 import LINE_START, _ended, _sub  # noqa: E402

SECOND = dict(key="g.py::second@L9", id="f-9", title="second", file="g.py", line=9)
OWNER_RULING = {"kind": "owner-ruling", "ref": {"url": U, "words": W}}


def _readers(fake, doc=DOC):
    """The fake's readers plus the owner-ruling comment reader: the comment resolves to `doc` (None: it cannot be read)."""
    return {**fake.readers(), "owner_ruling_comment": lambda repo, comment_id: copy.deepcopy(doc)}


def _put(tmp_path, session, readers, body, **over):
    return rs.write_from_session(session, put_extras(tmp_path, extras(**body, **over)), str(tmp_path), readers)


def _ruling(key):
    return {"repo": "o/r", "ownerRulings": [{"key": key, "url": U, "words": W}]}


def _line(rec):
    return rr.uncertified_line(rec["uncertified"])


def _held_key(rec, unruled=None):
    (held,) = [f for f in rec["findings"] if rr.waits_for_owner(f, rec["findings"]) and f["id"] != unruled]
    return held["findingKey"]


def _twice(tmp_path, name, doc=DOC, unruled=None, **over):
    """The real driven state written with no rulings (the control), then written again with the owner's ruling on the
    finding it waits on (not the one id `unruled` names). Returns (control record, ruled record, readers, fake)."""
    session, fake, body = _from_state(_sub(tmp_path, name), _driven_state(), **over)
    rd = _readers(fake, doc)
    first = _put(tmp_path, session, rd, body)
    assert first["ok"], first
    before = rr.read(7, readers=rd)
    second = _put(tmp_path, session, rd, body, **_ruling(_held_key(before, unruled)))
    assert second["ok"], second
    return before, rr.read(7, readers=rd), rd, fake


def test_t1_a_fully_ruled_owner_choice_session_reads_reviewed(tmp_path):
    """axis: T1 — the real loop's owner-choice hand-back reads awaits-owner with no withheld line (control); written again with
    the owner's ruling on the finding it waits on, it reads reviewed, whatIsMissing empty, the finding a ruling through an
    owner-ruling citation, and the entry unchanged."""
    before, rec, _rd, _fake = _twice(tmp_path, "t1")
    assert before["status"] == "awaits-owner" and not any(m.startswith(LINE_START) for m in before["whatIsMissing"])
    assert before["leftForOwner"] == [_CHOICE_KEY]
    (f,) = rec["findings"]
    assert f["outcome"] == "ruling" and f["decidedBy"]["kind"] == "owner-ruling", f
    assert rec["leftForOwner"] == []
    assert rec["status"] == "reviewed" and rec["whatIsMissing"] == [], (rec["status"], rec["whatIsMissing"])
    assert rec["uncertified"] == {"terminal": "handed-back", "reason": before["uncertified"]["reason"],
                                  "ownerChoiceOnly": True, "source": "session"}
    assert rr.cleared(rec["status"])


def test_t2_the_sheet_asks_no_card_and_shows_no_incomplete_line_for_the_fully_ruled_record(tmp_path):
    """axis: T2 — the PR sheet built from the T1 record has no leftover card and no incomplete-record history line; the same
    record put back to not-reviewed with the withheld line shows the incomplete line (the A/B)."""
    _before, rec, _rd, _fake = _twice(tmp_path, "t2")
    assert rec["status"] == "reviewed"
    prefix = WORDS["historyIncomplete"].split("{what}")[0]
    advisor = copy.deepcopy(load("input-small.json"))
    advisor.pop("leftovers", None)

    def sheet(status, missing):
        records = [copy.deepcopy(load("record-small.json"))]
        records[0].update(status=status, whatIsMissing=missing, findings=copy.deepcopy(rec["findings"]))
        return pr_sheet.build(records, copy.deepcopy(advisor), WORDS)

    built = sheet(rec["status"], rec["whatIsMissing"])
    assert not [c for c in built["cards"] if c["callKind"].startswith(WORDS["leftoverKind"])], built["cards"]
    assert not any(h.startswith(prefix) for h in built["prSheet"]["history"]), built["prSheet"]["history"]
    back = sheet("not-reviewed", [_line(rec)] + rec["whatIsMissing"])
    assert pr_sheet._fill(WORDS["historyIncomplete"], what=_line(rec)) in back["prSheet"]["history"]


def test_t3_a_finding_with_no_outcome_keeps_the_withheld_line_though_the_waiting_one_is_ruled(tmp_path):
    """axis: T3 — the ruled session plus an Important finding with no outcome reads not-reviewed and holds the withheld line."""
    state = _driven_state()
    undecided = ledger_row(key="g.py::undecided@L9", id="f-9", title="undecided", file="g.py", line=9, disposition=None)
    _before, rec, _rd, _fake = _twice(tmp_path, "t3", dispositionLedger=state["dispositionLedger"] + [undecided])
    assert {f["outcome"] for f in rec["findings"]} == {"ruling", None}, rec["findings"]
    assert rec["status"] == "not-reviewed"
    assert _line(rec) in rec["whatIsMissing"]
    assert any(m.endswith("has no outcome") for m in rec["whatIsMissing"]), rec["whatIsMissing"]


def test_t4_one_of_two_waiting_findings_ruled_keeps_the_old_path_awaits_owner(tmp_path):
    """axis: T4 — two waiting findings with only one ruled: one still waits, so the line stays out by the #2638 path and the
    record reads awaits-owner, never reviewed."""
    state = _driven_state()
    second = ledger_row(**SECOND, **OOS)
    _before, rec, _rd, _fake = _twice(tmp_path, "t4", unruled=SECOND["id"], dispositionLedger=state["dispositionLedger"] + [second])
    assert sorted(f["outcome"] for f in rec["findings"]) == ["left-for-owner", "ruling"], rec["findings"]
    assert rec["status"] == "awaits-owner"
    assert not any(m.startswith(LINE_START) for m in rec["whatIsMissing"]), rec["whatIsMissing"]
    assert len(rec["leftForOwner"]) == 1


def test_t5_a_ruling_that_does_not_resolve_leaves_the_finding_waiting_and_the_record_awaits_owner(tmp_path):
    """axis: T5 — the cited comment cannot be read, so the finding stays left-for-owner and the record reads awaits-owner
    (the #2638 path), never reviewed."""
    _before, rec, _rd, _fake = _twice(tmp_path, "t5", doc=None)
    (f,) = rec["findings"]
    assert f["outcome"] == "left-for-owner" and rec["leftForOwner"] == [_CHOICE_KEY], f
    assert rec["status"] == "awaits-owner"
    assert not any(m.startswith(LINE_START) for m in rec["whatIsMissing"])


def _ruled_record(tmp_path, name, terminal_kind, cert):
    session, fake, body = _ended(_sub(tmp_path, name), "handed-back", cert,
                                 [{"round": 1, "kind": terminal_kind, "detail": "d"}], [ledger_row(**OOS)])
    rd = _readers(fake)
    assert _put(tmp_path, session, rd, body, **_ruling(KEY))["ok"]
    return rr.read(7, readers=rd)


def _assert_kept(rec):
    (f,) = rec["findings"]
    assert f["outcome"] == "ruling" and f["decidedBy"]["kind"] == "owner-ruling", f
    assert rec["status"] == "not-reviewed" and _line(rec) in rec["whatIsMissing"], (rec["status"], rec["whatIsMissing"])


@pytest.mark.parametrize("kind", OTHER_HANDBACK_KINDS)
def test_t6_a_other_hand_back_kind_with_its_finding_ruled_keeps_the_withheld_line(tmp_path, kind):
    """axis: T6a — every hand-back kind but the owner-choice one never takes the stamp, so its ruled finding does not lift the
    line."""
    rec = _ruled_record(tmp_path, "t6a", kind, ONLY)
    assert "ownerChoiceOnly" not in rec["uncertified"]
    _assert_kept(rec)


def test_t6_b_an_owner_choice_session_whose_certification_carries_no_stamp_keeps_the_withheld_line(tmp_path):
    """axis: T6b — the owner-choice kind with no ownerChoiceOnly in its certification is not stamped, so its ruled finding does
    not lift the line."""
    rec = _ruled_record(tmp_path, "t6b", "owner-choice-open", {"shape": None, "reason": REASON})
    assert "ownerChoiceOnly" not in rec["uncertified"]
    _assert_kept(rec)


def test_t6_c_a_hand_written_account_entry_with_the_stamp_keeps_the_withheld_line(tmp_path):
    """axis: T6c — a hand-written account's entry carrying ownerChoiceOnly (source `account`) with its finding ruled keeps the
    line."""
    root = _sub(tmp_path, "t6c")
    session, fake, body = _ended(root, "converged", ledger=[ledger_row(**OOS)])
    rd = _readers(fake)
    account = rs.account_from_session(session, extras(**body, **_ruling(KEY)), rd)
    entry = {"terminal": "handed-back", "reason": REASON, "ownerChoiceOnly": True}
    path = root / "account.json"
    path.write_text(json.dumps(dict(account, uncertified=entry)))
    assert rr.write(str(path), str(tmp_path), rd)["ok"]
    rec = rr.read(7, readers=rd)
    assert rec["uncertified"] == dict(entry, source="account")
    _assert_kept(rec)


def test_t7_a_finding_a_carried_check_settles_fixed_at_write_time_keeps_the_withheld_line(tmp_path):
    """axis: T7 — a stamped owner-choice session whose one left-for-owner finding is ruled and whose other finding (no outcome
    in the session) a carried check settles fixed when the record is written: an outcome changed at write time, so the line
    stays and the record reads not-reviewed."""
    fake = Fake()
    _first_record(tmp_path, fake, disposition="out-of-scope")
    (before,) = _by_key(fake)
    assert before["outcome"] == "left-for-owner"
    ledger = [ledger_row(**SECOND, **OOS), ledger_row(disposition=None)]
    s = Session(_sub(tmp_path, "t7"), terminal="handed-back", dispositionLedger=ledger, decisions=list(OWNER_CHOICE),
                seatMapReceipts=[{"round": "1", "map": {"seats": {}, "makerFamilies": ["xai"]}}], certification=dict(ONLY))
    s.meta["sessionId"] = "s-2"
    s.seat("code-reviewer", head=HEAD, nonce="n1")
    fake.runs["/run/n1"] = (dict(GOOD_RUN, runnerNonce="n1", viewHeadSha=HEAD), None)
    rd = {**_readers(fake), "is_ancestor": lambda root, commit, to: True}
    body = {"ci": "green", "runDirs": ["/run/n1"]}
    out = _put(tmp_path, s.save(), rd, body, carriedChecks=[carried_entry(key=before["findingKey"], checkedHead=HEAD)],
               **_ruling(SECOND["key"]))
    assert out["ok"], out
    rec = rr.read(7, readers=rd)
    outcomes = {f["id"]: f["outcome"] for f in rec["findings"]}
    assert outcomes == {"f-9": "ruling", "f-1": "fixed"}, outcomes
    assert [r["result"] for r in rec["carriedRechecks"]] == ["fixed"]
    assert rec["uncertified"]["ownerChoiceOnly"] is True and rec["uncertified"]["source"] == "session"
    assert rec["status"] == "not-reviewed" and _line(rec) in rec["whatIsMissing"], (rec["status"], rec["whatIsMissing"])


# --- unit: _owner_choices_settled on hand-built lists ---

def _waiting(**over):
    return dict({"id": "f-1", "severity": "Important", "outcome": "left-for-owner"}, **over)


def _ruled(**over):
    return dict({"id": "f-1", "outcome": "ruling", "decidedBy": copy.deepcopy(OWNER_RULING)}, **over)


def _fixed(**over):
    return dict({"id": "f-2", "severity": "Important", "outcome": "fixed"}, **over)


def test_t8_a_ruled_waiting_finding_and_an_unchanged_one_are_settled():
    """axis: T8 — one left-for-owner account finding now a ruling through an owner-ruling citation, the other unchanged."""
    assert rr._owner_choices_settled([_waiting(), _fixed()], [_ruled(), _fixed()]) is True


def test_t8_a_minor_with_no_outcome_that_is_now_ruled_is_settled():
    """axis: T8 — a Minor the session left with no outcome is an owner choice like a left-for-owner finding."""
    assert rr._owner_choices_settled([{"outcome": None, "severity": "Minor"}], [_ruled()]) is True


def test_t8_once_waiting_now_fixed_is_not_settled():
    """axis: T8 S-ruled — a once-waiting finding the record now reads fixed (a write-time fix) is not an owner's ruling."""
    assert rr._owner_choices_settled([_waiting()], [{"id": "f-1", "outcome": "fixed"}]) is False


def test_t8_another_outcome_changed_is_not_settled():
    """axis: T8 S-kept — a finding the session did not leave for the owner that reads another outcome in the record
    (shown-wrong to fixed) keeps the line."""
    assert rr._owner_choices_settled([_waiting(), _fixed(outcome="shown-wrong")], [_ruled(), _fixed()]) is False


def test_t8_no_once_waiting_finding_is_not_settled():
    """axis: T8 S-some — a session that left nothing for the owner settles nothing."""
    assert rr._owner_choices_settled([_fixed()], [_fixed()]) is False


@pytest.mark.parametrize("session_findings, findings", [
    pytest.param([_waiting(), _fixed()], [_ruled()], id="lengths-differ"),
    pytest.param([_waiting()], [_ruled(), _fixed()], id="lengths-differ-the-other-way"),
    pytest.param([_waiting(), "x"], [_ruled(), _fixed()], id="non-dict-account-entry"),
    pytest.param([_waiting(), _fixed()], [_ruled(), None], id="non-dict-record-entry"),
    pytest.param(None, [_ruled()], id="account-findings-not-a-list"),
    pytest.param([_waiting()], None, id="record-findings-not-a-list"),
    pytest.param([_waiting()], [_ruled(decidedBy={"kind": "scope-ruling", "ref": {"url": U, "words": W}})], id="scope-ruling"),
    pytest.param([_waiting()], [{"id": "f-1", "outcome": "ruling"}], id="ruling-with-no-decided-by"),
    pytest.param([_waiting()], [_waiting()], id="still-waiting"),
    pytest.param([{"outcome": None, "severity": "Important"}], [_ruled()], id="important-with-no-outcome-is-not-a-choice"),
    pytest.param([], [], id="empty"),
])
def test_t8_every_other_shape_is_not_settled(session_findings, findings):
    """axis: T8 — a mismatch of length, a non-dict entry, a once-waiting finding not ruled by an owner-ruling citation, or an
    empty list reads False."""
    assert rr._owner_choices_settled(session_findings, findings) is False


def _stamped(findings):
    return {"uncertified": {"terminal": "handed-back", "reason": REASON, "ownerChoiceOnly": True, "source": "session"},
            "findings": findings}


def test_t9_a_stamped_record_with_every_finding_fixed_keeps_the_line_whatever_settled_says_but_true():
    """axis: T9 — none ever waited, so only an exact `settled is True` could lift the line, and a fixed-only record never gets
    one from the writer; any settled but exactly True is not settled (the order's E5)."""
    rec = _stamped([_fixed()])
    assert rr.owner_choice_only(rec) is False
    assert rr.owner_choice_only(rec, settled=False) is False
    for loose in (1, "yes", [1], {"a": 1}):
        assert rr.owner_choice_only(rec, settled=loose) is False
    assert rr.owner_choice_only(rec, settled=True) is True


def test_t9_a_settled_record_still_needs_every_finding_to_have_an_outcome_and_the_stamp():
    """axis: T9 — `settled` never lifts the line over a finding with no outcome, a missing stamp or a hand-written entry."""
    assert rr.owner_choice_only(_stamped([_ruled(), {"id": "f-9", "outcome": None}]), settled=True) is False
    unstamped = _stamped([_ruled()])
    del unstamped["uncertified"]["ownerChoiceOnly"]
    assert rr.owner_choice_only(unstamped, settled=True) is False
    hand = _stamped([_ruled()])
    hand["uncertified"]["source"] = "account"
    assert rr.owner_choice_only(hand, settled=True) is False
    assert rr.owner_choice_only(dict(_stamped([_ruled()]), findings=None), settled=True) is False
    assert rr.owner_choice_only(_stamped([_ruled()]), settled=True) is True
