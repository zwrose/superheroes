"""Guards for the owner ruling: a finding left for the owner ends `ruling` only when its pointer resolves."""
import copy
import json
from pathlib import Path

import pytest

import canon
import finding_outcomes as fo
import pr_sheet
import review_record as rr
import review_record_session as rs
from test_review_record_session import CODEX, HEAD, KEY, Fake, Session, extras, ledger_row, put_extras, _merged, _second_session

WORDS = json.loads((Path(__file__).resolve().parents[2] / "theme" / "sheet-words.json").read_text(encoding="utf-8"))["pr"]
U = "https://github.com/o/r/issues/12#issuecomment-555"
W = "ship it as is"
DOC = {"id": 555, "issue_url": "https://api.github.com/repos/o/r/issues/12", "html_url": U, "author_association": "OWNER",
       "user": {"login": "o"}, "body": canon.ruling_record("2026-10-18", "12:00", W, "finding f-1")}
X = {"id": "f-1", "title": "Unchecked index", "severity": "Important", "file": "a.py", "line": 9, "body": "b",
     "consequence": "the total on the page is wrong", "outcome": "left-for-owner", "reason": "waits for the owner",
     "reviewer": "r1"}
Y = dict(X, id="f-2", title="Unbounded loop", line=20)
ADVISOR = {"schema": "pr-sheet-input/1", "kind": "pr", "number": 7, "title": "T", "summary": "S"}
CARD = {"why": "the check found it open", "context": "the index is read unchecked", "options": "none"}


def entry(**over):
    return {"key": "f-1", "url": U, "words": W, **over}


def account(rulings, findings=None):
    return {"schema": rr.ACCOUNT_SCHEMA, "pr": 7, "repo": "o/r", "sessionId": "s-1", "lane": "light", "laneReason": None,
            "finalCommit": HEAD, "ci": "green", "reviewers": [{"name": "r1", "vendor": "codex", "model": CODEX,
                                                                   "planned": True, "ran": True, "runDir": None}],
            "findings": copy.deepcopy([X] if findings is None else findings), "rawFindingsFiles": [],
            "rounds": {"count": 1, "cap": 3, "stoppedAtCap": False}, "ownerRulings": rulings}


def readers(doc=DOC, calls=None, fake=None):
    def comment(repo, comment_id):
        if calls is not None:
            calls.append((repo, comment_id))
        if isinstance(doc, Exception):
            raise doc
        return copy.deepcopy(doc)
    return {**(fake or Fake()).readers(), "owner_ruling_comment": comment}


def build(rulings, findings=None, **kw):
    return rr.build_record(account(rulings, findings), readers(**kw))


def the_finding(rec):
    (f,) = rec["findings"]
    return f


def cards(rec, leftovers):
    sheet = pr_sheet.build([rec], {**ADVISOR, "leftovers": leftovers}, WORDS)
    return sheet, [c for c in sheet["cards"] if c["callKind"].startswith(WORDS["leftoverKind"])]


def test_t1_a_ruled_finding_folds_into_already_decided_and_leaves_no_card():
    # Axis: the whole path, a left-for-owner finding with a resolving pointer ends ruling and the sheet does not ask.
    rec = build([entry()])
    f = the_finding(rec)
    assert f["outcome"] == "ruling" and f["sheetPart"] == rr.rfs.OUTCOME_SHEET_PART["ruling"]
    assert f["decidedBy"] == {"kind": "owner-ruling", "ref": {"url": U, "words": W}}
    assert f["reason"].startswith(f'owner ruling "{W}" ({U})') and f["reason"].endswith("; waits for the owner")
    assert rec["decisionRechecks"] == [{"finding": "f-1", "from": "left-for-owner", "to": "ruling",
                                        "why": f'owner ruling "{W}" ({U})'}]
    assert rec["leftForOwner"] == []
    sheet = pr_sheet.build([rec], ADVISOR, WORDS)
    assert not [c for c in sheet["cards"] if c["callKind"].startswith(WORDS["leftoverKind"])]
    assert [d["title"] for d in sheet["prSheet"]["alreadyDecided"]] == [X["title"]]
    assert "alreadyDecided" not in sheet["prSheet"]["whatChanged"]
    assert sheet["prSheet"]["alreadyDecided"][0]["detail"] == f["reason"]


L1 = "the ruling's link is not a comment permalink"
L2 = "the ruling's link is not in this repository"
L3 = "the ruling's comment could not be read"
L4 = "the ruling's comment is not the owner's"
L5 = "the ruling's comment does not hold the owner's words"
L6 = "the ruling's comment is not a chat-ruling record"
NOT_ON_RECORD = "; the owner ruling it cites is not on record (%s)"
FAILS = [
    pytest.param({"url": "https://github.com/o/r/pull/12#issuecomment-555"}, {}, L1, id="L1-not-a-comment-permalink"),
    pytest.param({"url": "https://github.com/o/r/issues/12"}, {}, L1, id="L1-no-comment-anchor"),
    pytest.param({"url": "https://github.com/o/r/issues/12#issuecomment-555x"}, {}, L1, id="L1-trailing-text"),
    pytest.param({"url": "https://github.com/x/y/issues/12#issuecomment-555"}, {}, L2, id="L2-another-repository"),
    pytest.param({}, {"doc": None}, L3, id="L3-reader-returns-none"),
    pytest.param({}, {"doc": RuntimeError("down")}, L3, id="L3-reader-raises"),
    pytest.param({}, {"doc": dict(DOC, id=556)}, L3, id="L3-another-comment-id"),
    pytest.param({}, {"doc": dict(DOC, id=True)}, L3, id="L3-id-is-a-bool"),
    pytest.param({}, {"doc": dict(DOC, issue_url="https://api.github.com/repos/o/r/issues/13")}, L3, id="L3-another-issue"),
    pytest.param({}, {"doc": dict(DOC, issue_url="https://api.github.com/repos/o/r/issues/112")}, L3, id="L3-issue-number-suffix"),
    pytest.param({}, {"doc": dict(DOC, issue_url="https://api.github.com/repos/x/y/issues/12")}, L3, id="L3-another-repo-issue"),
    pytest.param({}, {"doc": {k: v for k, v in DOC.items() if k != "issue_url"}}, L3, id="L3-no-issue-url"),
    pytest.param({}, {"doc": dict(DOC, author_association="MEMBER")}, L4, id="L4-member"),
    pytest.param({}, {"doc": dict(DOC, author_association="COLLABORATOR")}, L4, id="L4-collaborator"),
    pytest.param({}, {"doc": dict(DOC, author_association="NONE")}, L4, id="L4-none"),
    pytest.param({}, {"doc": dict(DOC, author_association="owner")}, L4, id="L4-lowercase"),
    pytest.param({}, {"doc": dict(DOC, body=canon.ruling_record("2026-10-18", "12:00", "I think otherwise", "finding f-1"))}, L5,
                 id="L5-words-absent"),
    pytest.param({}, {"doc": dict(DOC, body=canon.ruling_record("2026-10-18", "12:00", "Ship it as is", "finding f-1"))}, L5,
                 id="L5-case-differs"),
    pytest.param({}, {"doc": dict(DOC, body=None)}, L6, id="L5-body-not-text"),
]


@pytest.mark.parametrize("over, kw, why", FAILS)
def test_t2_no_pointer_no_fold_and_the_finding_stays_a_card(over, kw, why):
    # Axis: fail closed, a left-for-owner finding stays one unless every leg of its pointer holds; it is never dropped.
    rec = build([entry(**over)], **kw)
    f = the_finding(rec)
    assert f["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"] and rec["decisionRechecks"] == []
    assert f["reason"] == "waits for the owner" + NOT_ON_RECORD % why
    sheet, found = cards(rec, {"f-1": CARD})
    assert len(found) == 1 and sheet["prSheet"]["alreadyDecided"] == []


def test_t2_a_ruling_with_no_link_or_words_in_the_citation_stays_a_card():
    # Axis: E8 on the record path, a hand-built citation with blank words never resolves.
    bad = dict(X, decidedBy={"kind": "owner-ruling", "ref": {"url": U, "words": "  "}})
    rec = rr.build_record(account([], [bad]), readers())
    assert the_finding(rec)["outcome"] == "left-for-owner"
    assert the_finding(rec)["reason"] == "waits for the owner" + NOT_ON_RECORD % "the ruling names no link or words"


def test_t3_a_ruling_whose_pointer_fails_is_demoted_and_becomes_a_card():
    # Axis: a ruling stands only while its owner-ruling pointer resolves.
    ruled = dict(X, outcome="ruling", reason="the owner said so")
    rec = build([entry()], [ruled], doc=dict(DOC, author_association="MEMBER"))
    f = the_finding(rec)
    assert f["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"]
    assert f["reason"] == f"the cited decision is not on record ({L4}); the owner said so"
    assert rec["decisionRechecks"] == [{"finding": "f-1", "from": "ruling", "to": "left-for-owner",
                                        "why": f"the cited decision is not on record ({L4})"}]
    assert len(cards(rec, {"f-1": CARD})[1]) == 1
    kept = build([entry()], [ruled])
    assert the_finding(kept)["outcome"] == "ruling" and kept["leftForOwner"] == []


def test_t4_the_vet_check_still_lists_the_unruled_finding_in_the_posted_record(tmp_path):
    # Axis: a ruled finding leaves leftForOwner and an unruled one stays, in the built record and in the one a reader gets back.
    rec = build([entry()], [X, Y])
    assert rec["leftForOwner"] == ["f-2"]
    assert {f["id"]: f["outcome"] for f in rec["findings"]} == {"f-1": "ruling", "f-2": "left-for-owner"}
    fake = Fake()
    path = tmp_path / "account.json"
    path.write_text(json.dumps(account([entry()], [X, Y])))
    out = rr.write(str(path), str(tmp_path), readers(fake=fake))
    assert out["ok"], out
    assert len(fake.marked()) == 1
    got = rr.read(7, readers=fake.readers())
    assert got["ok"], got
    assert {f["id"]: f["outcome"] for f in got["findings"]} == {"f-1": "ruling", "f-2": "left-for-owner"}
    assert got["leftForOwner"] == ["f-2"]
    ruled = next(f for f in got["findings"] if f["id"] == "f-1")
    assert ruled["decidedBy"] == {"kind": "owner-ruling", "ref": {"url": U, "words": W}}


@pytest.mark.parametrize("rulings, detail", [
    pytest.param([entry(key="nobody")], "ownerRulings[0].key names no finding", id="E9-names-no-finding"),
    pytest.param([entry(key="dup")], "ownerRulings[0].key names more than one finding", id="E10-names-two-findings"),
    pytest.param([entry(), entry(key=rr._key(X))], "ownerRulings[1].key names a finding another entry names",
                 id="E11-two-entries-one-finding"),
    pytest.param([entry(url=3)], "ownerRulings[0].url", id="url-not-a-string"),
    pytest.param([entry(url="")], "ownerRulings[0].url", id="url-empty"),
    pytest.param([entry(url="  ")], "ownerRulings[0].url", id="url-blank"),
    pytest.param([entry(words=None)], "ownerRulings[0].words", id="words-not-a-string"),
    pytest.param([entry(words=" \n")], "ownerRulings[0].words", id="words-blank"),
    pytest.param([entry(key="")], "ownerRulings[0].key", id="key-empty"),
    pytest.param([entry(key=7)], "ownerRulings[0].key", id="key-not-a-string"),
    pytest.param(["f-1"], "ownerRulings[0]", id="entry-not-an-object"),
    pytest.param("f-1", "ownerRulings", id="not-a-list"),
])
def test_t5_a_malformed_entry_refuses_the_account(rulings, detail):
    # Axis: every entry names exactly one finding, once, with a link and words; anything else is refused whole.
    findings = [X, Y, dict(Y, id="dup", title="Other", line=1), dict(Y, id="dup", title="Another", line=2)]
    with pytest.raises(rr.Refusal) as refused:
        build(rulings, findings)
    assert refused.value.reason == "review-account-invalid" and refused.value.detail == detail


@pytest.mark.parametrize("outcome", ["fixed", "craft", "shown-wrong", None])
def test_t6_a_finding_with_any_other_outcome_is_left_exactly_as_it_is(outcome):
    # Axis: an entry never turns a settled or undecided finding into anything else.
    other = dict(X, outcome=outcome, reason="r")
    calls = []
    rec = build([entry()], [other], calls=calls)
    f = the_finding(rec)
    assert f["outcome"] == outcome and f["reason"] == "r" and "decidedBy" not in f and rec["decisionRechecks"] == []
    assert calls == []


@pytest.mark.parametrize("key", ["a.py::t@L3", rr._key({"findingKey": "a.py::t@L3"}), "f-1"])
def test_t7_an_entry_matches_by_raw_finding_key_stored_key_or_id(key):
    # Axis: the session's raw findingKey, the stored opaque key and the id all name the finding.
    raw = dict(X, findingKey="a.py::t@L3")
    rec = build([entry(key=key)], [raw, Y])
    assert {f["id"]: f["outcome"] for f in rec["findings"]} == {"f-1": "ruling", "f-2": "left-for-owner"}
    assert rec["findings"][0]["findingKey"] == rr._key(raw)


def test_t8_the_session_adapter_expands_a_ruling_on_a_merged_groups_representative_to_its_members(tmp_path):
    # Axis: the owner rules on what the sheet showed (the representative), so its merged members fold with it.
    oos = {"disposition": "out-of-scope", "outOfScopeReason": "belongs to the follow-up"}
    ledger = _merged({}, oos) + [ledger_row("z::t@L9", id="z-1", disposition="out-of-scope", **{
        "outOfScopeReason": "unrelated"})]
    s = Session(tmp_path, dispositionLedger=ledger)
    s.seat("code-reviewer")
    session = s.save()
    given = [{"key": KEY, "url": U, "words": W}]
    account = rs.account_from_session(session, extras(repo="o/r", ownerRulings=given), Fake().readers())
    assert account["ownerRulings"] == given + [{"key": "m::t@L1", "url": U, "words": W}]
    by_id = {f["id"]: f for f in account["findings"]}
    assert by_id["m-1"]["outcome"] == by_id["rep-1"]["outcome"] == "left-for-owner" and by_id["z-1"]["outcome"] == "left-for-owner"
    fake = Fake()
    out = rs.write_from_session(session, put_extras(tmp_path, extras(repo="o/r", ownerRulings=given)), str(tmp_path),
                                readers(fake=fake))
    assert out["ok"], out
    got = {f["id"]: f["outcome"] for f in rr.read(7, readers=fake.readers())["findings"]}
    assert got == {"m-1": "ruling", "rep-1": "ruling", "z-1": "left-for-owner"}


def test_t8_a_member_an_entry_already_names_is_not_named_twice(tmp_path):
    # Axis: the expansion adds an entry for a member only when none names it, so the writer's one-entry rule holds.
    ledger = _merged({}, {"disposition": "out-of-scope", "outOfScopeReason": "belongs to the follow-up"})
    s = Session(tmp_path, dispositionLedger=ledger)
    s.seat("code-reviewer")
    given = [{"key": KEY, "url": U, "words": W}, {"key": "m-1", "url": U, "words": W}]
    account = rs.account_from_session(s.save(), extras(repo="o/r", ownerRulings=given), Fake().readers())
    assert account["ownerRulings"] == given


def _merged_session(tmp_path):
    oos = {"disposition": "out-of-scope", "outOfScopeReason": "belongs to the follow-up"}
    s = Session(tmp_path, dispositionLedger=_merged({}, oos))
    s.seat("code-reviewer")
    return s.save()


def test_v0_an_entry_keyed_by_the_representatives_stored_key_expands_to_its_member(tmp_path):
    # Axis: the expansion finds the representative the way the writer does, by raw findingKey, stored key or id.
    session = _merged_session(tmp_path)
    base = rs.account_from_session(session, extras(repo="o/r"), Fake().readers())
    stored = rr._key(next(f for f in base["findings"] if f["id"] == "rep-1"))
    assert stored.startswith("rr1:")
    given = [{"key": stored, "url": U, "words": W}]
    account = rs.account_from_session(session, extras(repo="o/r", ownerRulings=given), Fake().readers())
    assert account["ownerRulings"] == given + [{"key": "m::t@L1", "url": U, "words": W}]
    rec = rr.build_record(account, readers())
    assert rec["leftForOwner"] == [] and {f["id"]: f["outcome"] for f in rec["findings"]} == {"m-1": "ruling", "rep-1": "ruling"}


def test_v0_a_member_an_entry_names_by_its_stored_key_is_not_named_twice(tmp_path):
    # Axis: the already-named check reads an entry key as the writer does, so the writer's one-entry rule holds.
    session = _merged_session(tmp_path)
    base = rs.account_from_session(session, extras(repo="o/r"), Fake().readers())
    member = rr._key(next(f for f in base["findings"] if f["id"] == "m-1"))
    given = [{"key": KEY, "url": U, "words": W}, {"key": member, "url": U, "words": W}]
    account = rs.account_from_session(session, extras(repo="o/r", ownerRulings=given), Fake().readers())
    assert account["ownerRulings"] == given
    fake = Fake()
    out = rs.write_from_session(session, put_extras(tmp_path, extras(repo="o/r", ownerRulings=given)), str(tmp_path),
                                readers(fake=fake))
    assert out["ok"], out
    assert {f["id"]: f["outcome"] for f in rr.read(7, readers=fake.readers())["findings"]} == {"m-1": "ruling", "rep-1": "ruling"}


def test_v0_an_entry_that_names_no_row_adds_no_expansion(tmp_path):
    # Axis: E1, an unmatched key expands to nothing; the writer refuses it as before.
    given = [{"key": "rr1:nothing", "url": U, "words": W}]
    account = rs.account_from_session(_merged_session(tmp_path), extras(repo="o/r", ownerRulings=given), Fake().readers())
    assert account["ownerRulings"] == given


def test_v1_two_groups_whose_representatives_share_a_display_id_expand_separately(tmp_path):
    # Axis: membership is the ledger's resolved merge by identity key, never the display id or the reason text.
    second = "r2::t@L5"
    oos = {"disposition": "out-of-scope", "outOfScopeReason": "belongs to the follow-up"}
    ledger = _merged({}, oos) + [ledger_row("m2::t@L6", id="m-2", disposition=None, mergedInto=second),
                                 ledger_row(second, id="rep-1", **oos)]
    s = Session(tmp_path, dispositionLedger=ledger)
    s.seat("code-reviewer")
    session = s.save()
    given = [{"key": KEY, "url": U, "words": W}]
    account = rs.account_from_session(session, extras(repo="o/r", ownerRulings=given), Fake().readers())
    assert account["ownerRulings"] == given + [{"key": "m::t@L1", "url": U, "words": W}]
    rec = rr.build_record(account, readers())
    assert {f["findingKey"]: f["outcome"] for f in account["findings"]} == {
        KEY: "left-for-owner", "m::t@L1": "left-for-owner", second: "left-for-owner", "m2::t@L6": "left-for-owner"}
    assert {f["id"]: f["outcome"] for f in rec["findings"] if f["id"] != "rep-1"} == {"m-1": "ruling", "m-2": "left-for-owner"}
    assert sorted(f["outcome"] for f in rec["findings"] if f["id"] == "rep-1") == ["left-for-owner", "ruling"]


def test_v1_a_member_whose_merge_does_not_resolve_gets_no_entry(tmp_path):
    # Axis: E2, fail closed; a member naming a representative that is not in the ledger stays a card.
    oos = {"disposition": "out-of-scope", "outOfScopeReason": "belongs to the follow-up"}
    ledger = [ledger_row("m::t@L1", id="m-1", disposition=None, mergedInto="gone::t@L1"), ledger_row(KEY, id="rep-1", **oos)]
    s = Session(tmp_path, dispositionLedger=ledger)
    s.seat("code-reviewer")
    given = [{"key": KEY, "url": U, "words": W}]
    account = rs.account_from_session(s.save(), extras(repo="o/r", ownerRulings=given), Fake().readers())
    assert account["ownerRulings"] == given


def test_v2_the_standard_record_of_multiline_words_holds_the_words():
    # Axis: the chat-ruling record quotes each line behind a marker; the words still occur in it.
    words = "ship it\nas is"
    doc = dict(DOC, body=canon.ruling_record("2026-10-18", "12:00", words, "finding f-1"))
    rec = build([entry(words=words)], doc=doc)
    assert the_finding(rec)["outcome"] == "ruling" and rec["leftForOwner"] == []


def test_v2_words_that_occur_in_neither_form_stay_a_card():
    # Axis: E5, the de-quote widens nothing; words absent from the quoted block stay a card.
    doc = dict(DOC, body=canon.ruling_record("2026-10-18", "12:00", "ship it\nas is", "finding f-1"))
    rec = build([entry(words="ship it\nas was")], doc=doc)
    assert the_finding(rec)["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"]


def test_t8_extras_ownerrulings_that_is_not_a_list_is_refused(tmp_path):
    s = Session(tmp_path, dispositionLedger=[ledger_row()])
    s.seat("code-reviewer")
    fake = Fake()
    out = rs.write_from_session(s.save(), put_extras(tmp_path, extras(ownerRulings={"key": "x"})), str(tmp_path), fake.readers())
    assert out["ok"] is False and out["reason"] == rs.BAD_EXTRAS and out["detail"] == "ownerRulings"
    assert fake.comments == []


def test_t9_the_reader_is_not_called_for_a_link_that_fails_the_permalink_or_repository_leg():
    # Axis: nothing is fetched for a foreign or malformed link; each distinct good link is fetched once.
    calls = []
    for url in ("https://github.com/o/r/pull/12#issuecomment-555", "https://github.com/x/y/issues/12#issuecomment-555",
                "https://example.com/o/r/issues/12#issuecomment-555"):
        build([entry(url=url)], calls=calls)
    assert calls == []
    both = [dict(X, id="f-1"), dict(X, id="f-2", title="Other")]
    build([entry(), entry(key="f-2")], both, calls=calls)
    assert calls == [("o/r", 555)]


def test_t9_an_account_naming_no_repository_fetches_nothing_and_keeps_the_finding():
    # Axis: E14, with no repository to compare against the link is in no repository.
    calls = []
    acct = dict(account([entry()]), repo=None)
    rec = rr.build_record(acct, readers(calls=calls))
    assert the_finding(rec)["outcome"] == "left-for-owner" and calls == []
    assert the_finding(rec)["reason"] == "waits for the owner" + NOT_ON_RECORD % L2


def test_t9_a_repository_in_other_case_is_the_same_repository():
    rec = build([entry(url="https://github.com/O/R/issues/12#issuecomment-555")])
    assert the_finding(rec)["outcome"] == "ruling"


def test_without_ownerrulings_nothing_changes_and_the_reader_is_never_called():
    # Axis: E15, an account without the key builds as it did.
    calls = []
    acct = account([])
    del acct["ownerRulings"]
    rec = rr.build_record(acct, readers(calls=calls))
    assert the_finding(rec)["outcome"] == "left-for-owner" and the_finding(rec)["reason"] == "waits for the owner" and calls == []


def test_t10_decided_by_well_formed_takes_exactly_the_owner_ruling_shape():
    # Axis: the shared shape check names the 4th kind and nothing looser.
    assert fo.DECISION_KINDS == ("canon", "residual", "sheet-answer", "owner-ruling")
    good = {"kind": "owner-ruling", "ref": {"url": U, "words": W}}
    assert fo.decided_by_well_formed(good)
    for ref in ({"url": U}, {"words": W}, {"url": U, "words": W, "extra": 1}, {"url": " ", "words": W}, {"url": U, "words": ""},
                {"url": U, "words": 3}, {"url": None, "words": W}, U, None, [U, W]):
        assert not fo.decided_by_well_formed({"kind": "owner-ruling", "ref": ref}), ref
    assert not fo.decided_by_well_formed(dict(good, extra=1))
    assert not fo.decided_by_well_formed({"kind": "owner-ruling"})
    assert fo.on_record(good, {"repo": "o/r", "ownerRulings": {U: DOC}}) == (True, f'owner ruling "{W}" ({U})')
    assert fo.on_record({"kind": "owner-ruling", "ref": None}, {}) == (False, "the cited decision names no reference")
    assert fo.on_record({"kind": "owner-ruling", "ref": {}}, None) == (False, "the ruling names no link or words")
    assert fo.on_record(good, {"ownerRulings": {U: DOC}}) == (False, L2)
    assert fo.on_record(good, {"repo": "o/r"}) == (False, L3)


def _earlier_merged_record(tmp_path, fake, more=()):
    oos = {"disposition": "out-of-scope", "outOfScopeReason": "belongs to the follow-up"}
    s = Session(tmp_path, dispositionLedger=_merged({}, oos) + list(more))
    s.seat("code-reviewer")
    out = rs.write_from_session(s.save(), put_extras(tmp_path, extras(repo="o/r")), str(tmp_path), readers(fake=fake))
    assert out["ok"], out
    return rr.read(7, readers=fake.readers())["findings"]


def _later_write(tmp_path, fake, rep_key):
    given = [{"key": rep_key, "url": U, "words": W}]
    out = rs.write_from_session(_second_session(tmp_path), put_extras(tmp_path, extras(repo="o/r", ownerRulings=given)),
                                str(tmp_path), readers(fake=fake))
    assert out["ok"], out
    return rr.read(7, readers=fake.readers())


def test_wo_g_a_ruling_on_a_carried_representative_does_not_cover_its_carried_member(tmp_path):
    # Axis: fail closed; a carried row gets no entry the session did not write, so the member stays a card.
    fake = Fake()
    before = {f["id"]: f for f in _earlier_merged_record(tmp_path, fake)}
    assert before["m-1"]["reason"].endswith(" (merged into rep-1)") and before["m-1"]["outcome"] == "left-for-owner"
    rec = _later_write(tmp_path, fake, before["rep-1"]["findingKey"])
    assert {f["id"]: f["outcome"] for f in rec["findings"]} == {"m-1": "left-for-owner", "rep-1": "ruling"}
    assert rs.CARRIED in next(f for f in rec["findings"] if f["id"] == "m-1")["reason"]


BUILDER_NOTE = "**Builder note** (issue 12)\n\nThe owner said in chat that we should %s, so I am treating this as decided.\n" % W


def test_n1_an_owner_comment_that_is_not_a_chat_ruling_record_stays_a_card():
    # Axis: RM, every session posts as the owner, so a plain owner comment holding the words is no ruling.
    rec = build([entry()], doc=dict(DOC, body=BUILDER_NOTE))
    f = the_finding(rec)
    assert f["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"] and rec["decisionRechecks"] == []
    assert f["reason"] == "waits for the owner" + NOT_ON_RECORD % L6
    sheet, found = cards(rec, {"f-1": CARD})
    assert len(found) == 1 and sheet["prSheet"]["alreadyDecided"] == []


def test_n2_words_only_in_the_what_it_rules_on_line_stay_a_card():
    # Axis: QB, the words count only inside the quoted block, never in the context line of a real record.
    body = canon.ruling_record("2026-10-18", "12:00", "something else entirely", f"finding f-1, which says {W}")
    assert W in body
    rec = build([entry()], doc=dict(DOC, body=body))
    f = the_finding(rec)
    assert f["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"] and rec["decisionRechecks"] == []
    assert f["reason"] == "waits for the owner" + NOT_ON_RECORD % L5


@pytest.mark.parametrize("words", [W, "ship it\nas is", "ship it\n\nas is"])
def test_n3_a_real_chat_ruling_record_still_resolves_to_ruling(words):
    # Axis: the standard record of single-line, multiline and blank-interior-line words resolves.
    doc = dict(DOC, body=canon.ruling_record("2026-10-18", "12:00", words, "finding f-1"))
    rec = build([entry(words=words)], doc=doc)
    assert the_finding(rec)["outcome"] == "ruling" and rec["leftForOwner"] == []


def test_n4_a_ruling_whose_citation_resolves_shows_the_new_reason_once():
    # Axis: PF and ND, an already-ruling finding takes the citation's text as its reason prefix, once, and its outcome never moves.
    text = f'owner ruling "{W}" ({U})'
    prose = "belongs to a follow-up (ruled by owner, chat)"
    rec = build([entry()], [dict(X, outcome="ruling", reason=prose)])
    f = the_finding(rec)
    assert f["outcome"] == "ruling" and f["reason"] == f"{text}; {prose}" and rec["decisionRechecks"] == []
    again = build([entry()], [dict(X, outcome="ruling", reason=f"{text}; {prose}")])
    assert the_finding(again)["outcome"] == "ruling" and the_finding(again)["reason"] == f"{text}; {prose}"
    assert the_finding(again)["reason"].count(text) == 1 and again["decisionRechecks"] == []
    bare = build([entry()], [dict(X, outcome="ruling", reason="")])
    assert the_finding(bare)["reason"] == text


def test_n5_ruling_record_words_round_trips_what_ruling_record_writes():
    # Axis: the parser undoes exactly the quoting ruling_record applies.
    for words in (W, "ship it\nas is", "ship it\n\nas is", "> already quoted\nplain"):
        body = canon.ruling_record("2026-10-18", "12:00", words, "finding f-1")
        assert canon.ruling_record_words(body) == words


def test_n5_ruling_record_words_is_none_unless_it_is_a_standard_record():
    # Axis: E1 to E4 and E6, no marker on the first line, no heading, no quoted block, or no text is no record.
    good = canon.ruling_record("2026-10-18", "12:00", W, "finding f-1")
    assert canon.ruling_record_words(good) == W
    assert canon.ruling_record_words(good.replace(canon.RULING_MARKER + "\n", "", 1)) is None
    assert canon.ruling_record_words("intro\n" + good) is None
    assert canon.ruling_record_words(good.replace(canon.RULING_WORDS_HEADING, "The owner said:")) is None
    assert canon.ruling_record_words(f"{canon.RULING_MARKER}\n{canon.RULING_WORDS_HEADING}\n\nWhat it rules on: x\n") is None
    for bad in (None, 3, b"x", ["a"], {"body": good}):
        assert canon.ruling_record_words(bad) is None
