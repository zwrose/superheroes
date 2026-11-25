"""Guards for the scope ruling and the advisor's bound: a recorded decision the record writer follows and re-checks.

A finding whose `decidedBy` kind is `scope-ruling` or `advisor-bound` ends `ruling` exactly when every leg of its pointer
holds at write time (finding_outcomes._scope_or_bound_on_record); otherwise it is, or becomes, `left-for-owner` with the
failed leg named, and withholds as any leftover does."""
import copy

import pytest

import canon
import finding_outcomes as fo
import review_record as rr
import vet_slot
from test_review_record_owner_ruling import CARD, X, Y, account, cards, readers

KEY = rr._key(X)
RU = "https://github.com/o/r/issues/7#issuecomment-777"
RU2 = "https://github.com/o/r/issues/7#issuecomment-778"
RU3 = "https://github.com/o/r/issues/7#issuecomment-779"
SW = "the page total belongs to the follow-up work"
BW = "stop after two rounds, the contract is prose"
SCOPE, BOUND = fo.SCOPE_RULING, fo.ADVISOR_BOUND
NOT_ON_RECORD = {SCOPE: "; the scope ruling it cites is not on record (%s)",
                 BOUND: "; the advisor's bound it cites is not on record (%s)"}

L1 = "the ruling's link is not a comment permalink"
L2 = "the ruling's link is not in this repository"
L3 = "the ruling's comment could not be read"
L5 = "the ruling's comment does not hold the owner's words"
CRITICAL = "a Critical finding is never settled by a scope ruling or the advisor's bound"
NEITHER = "the ruling's comment is neither a chat-ruling record nor a vet receipt"
NOT_THIS_PR = "the vet receipt is not on this pull request"
NO_SCOPE_LINE = "the vet receipt records no scope ruling for this finding with these words"
NO_BOUND_LINE = "the vet receipt records no advisor's bound with these words"
NO_NUMBER = "the bound's words state no number of rounds"


def scope_line(key=KEY):
    return "<!-- superheroes:scope-ruling key=%s -->" % key


def bound_line(rounds=2):
    return "<!-- superheroes:advisor-bound rounds=%s -->" % rounds


def receipt(*decision_lines):
    """A vet receipt body: the receipt marker first, boilerplate the receipt always holds, then the decision lines."""
    return "\n".join([fo.VET_RECEIPT_MARKER, "## Vet receipt", "", "Calls accepted.", "", "**Decisions.**", *decision_lines, ""])


def chat(words):
    return canon.ruling_record("2026-10-18", "12:00", words, "finding f-1")


def doc_of(body, issue=7, comment=777):
    url = "https://github.com/o/r/issues/%d#issuecomment-%d" % (issue, comment)
    return {"id": comment, "issue_url": "https://api.github.com/repos/o/r/issues/%d" % issue, "html_url": url,
            "author_association": "MEMBER", "user": {"login": "o"}, "body": body}


def cite(kind, url=RU, words=SW):
    return {"kind": kind, "ref": {"url": url, "words": words}}


def finding(by=None, **over):
    return dict(X, **({"decidedBy": by} if by is not None else {}), **over)


def build(findings, count=3, **kw):
    a = account([], findings)
    a["rounds"] = {"count": count, "cap": 3, "stoppedAtCap": False}
    return rr.build_record(a, readers(**kw))


def the_finding(rec):
    (f,) = rec["findings"]
    return f


# ---- DoD row 1: a resolving citation is a decided finding, listed, with no card and nothing withheld ----

RESOLVES = [
    pytest.param(SCOPE, SW, receipt("- " + SW, scope_line()), 3, id="scope-through-a-vet-receipt"),
    pytest.param(SCOPE, SW, chat(SW), 3, id="scope-through-a-chat-ruling-record"),
    pytest.param(BOUND, "bound the review at two rounds", receipt("- bound the review at two rounds", bound_line(2)), 3,
                 id="bound-through-a-vet-receipt"),
    pytest.param(BOUND, BW, chat(BW), 3, id="bound-through-a-chat-ruling-record"),
]


@pytest.mark.parametrize("kind, words, body, count", RESOLVES)
def test_row1_a_resolving_citation_reads_ruling_and_leaves_no_card(kind, words, body, count):
    # Axis: the whole path, an Important left-for-owner finding with a resolving citation ends ruling and nothing asks the owner.
    rec = build([finding(cite(kind, words=words))], count, doc=doc_of(body))
    f = the_finding(rec)
    label = "scope ruling" if kind == SCOPE else "advisor's bound"
    text = '%s "%s" (%s)' % (label, words, RU)
    assert f["outcome"] == "ruling" and f["decidedBy"] == cite(kind, words=words)
    assert f["reason"].startswith(text) and f["reason"].endswith("; waits for the owner")
    assert rec["decisionRechecks"] == [{"finding": "f-1", "from": "left-for-owner", "to": "ruling", "why": text}]
    assert rec["leftForOwner"] == []
    assert not [m for m in rec["whatIsMissing"] if "left for the owner" in m]
    sheet, found = cards(rec, {})
    assert found == [] and [d["title"] for d in sheet["prSheet"]["alreadyDecided"]] == [X["title"]]


# ---- DoD row 2: anything short of every leg stays a card, with the failed leg named ----

def fails(kind=SCOPE, url=RU, words=SW, body=None, doc="build", severity="Important", count=3):
    if body is None:
        body = receipt("- " + words, scope_line() if kind == SCOPE else bound_line(2))
    return {"kind": kind, "url": url, "words": words, "doc": doc_of(body) if doc == "build" else doc,
            "severity": severity, "count": count}


RU9 = "https://github.com/o/r/issues/9#issuecomment-777"
STAYS = [
    pytest.param(fails(url="https://github.com/o/r/pull/7"), L1, id="not-a-comment-permalink"),
    pytest.param(fails(url="https://github.com/x/y/issues/7#issuecomment-777"), L2, id="another-repository"),
    pytest.param(fails(doc=RuntimeError("down")), L3, id="the-comment-cannot-be-read"),
    pytest.param(fails(doc=doc_of(receipt("- " + SW, scope_line()), comment=778)), L3, id="the-comment-read-is-another-comment"),
    pytest.param(fails(body="Fine by me, this is out of scope."), NEITHER, id="a-plain-comment"),
    pytest.param(fails(body=chat("I think otherwise")), L5, id="a-chat-record-without-the-words"),
    pytest.param(fails(url=RU9, doc=doc_of(receipt("- " + SW, scope_line()), issue=9)), NOT_THIS_PR, id="a-receipt-on-another-pr"),
    pytest.param(fails(body=receipt("- " + SW, scope_line("rr1:someotherkey"))), NO_SCOPE_LINE, id="a-marker-naming-another-key"),
    pytest.param(fails(words="Calls accepted.", body=receipt()), NO_SCOPE_LINE, id="boilerplate-words-and-no-marker-line"),
    pytest.param(fails(body=receipt("- " + SW, "- some other bullet", scope_line())), NO_SCOPE_LINE,
                 id="the-line-above-the-marker-lacks-the-words"),
    pytest.param(fails(words="too short", body=receipt("- too short", scope_line())), NO_SCOPE_LINE, id="words-under-12-characters"),
    pytest.param(fails(severity="Critical", body=receipt("- " + SW, scope_line())), CRITICAL, id="a-critical-with-a-resolving-citation"),
    pytest.param(fails(severity="Critical", body=chat(SW)), CRITICAL, id="a-critical-through-a-chat-ruling-record"),
    pytest.param(fails(kind=BOUND, words="bound the review at four rounds", body=receipt("- bound the review at four rounds", bound_line(4))),
                 "the review ran 3 rounds, fewer than the bound's 4", id="a-bound-above-the-reviews-rounds"),
    pytest.param(fails(kind=BOUND, words="stop here, the contract is prose", body=chat("stop here, the contract is prose")), NO_NUMBER, id="a-bound-whose-chat-words-state-no-number"),
    pytest.param(fails(kind=BOUND, words="bound the review at two rounds", body=receipt("- bound the review at two rounds", scope_line())),
                 NO_BOUND_LINE, id="a-bound-citing-a-scope-ruling-line"),
]


@pytest.mark.parametrize("case, leg", STAYS)
def test_row2_a_citation_short_of_a_leg_stays_a_card_with_the_leg_named(case, leg):
    # Axis: fail closed, an Important left-for-owner finding stays one unless every leg holds; it is never dropped.
    f0 = finding(cite(case["kind"], case["url"], case["words"]), severity=case["severity"])
    rec = build([f0], case["count"], doc=case["doc"])
    f = the_finding(rec)
    assert f["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"] and rec["decisionRechecks"] == []
    assert f["reason"] == "waits for the owner" and f[rr.NOT_ON_RECORD_FIELD] == leg
    assert rr.shown_reason(f) == "waits for the owner" + NOT_ON_RECORD[case["kind"]] % leg
    assert f["decidedBy"] == cite(case["kind"], case["url"], case["words"])
    sheet, found = cards(rec, {"f-1": CARD})
    assert len(found) == 1 and sheet["prSheet"]["alreadyDecided"] == []


def test_row2_free_text_only_stays_a_card():
    # Axis: a ruling named only in the reason's prose is a guess; the writer does not count it.
    rec = build([finding(None, reason="out of scope: the page total belongs to the follow-up work")], doc=doc_of(receipt("- " + SW, scope_line())))
    f = the_finding(rec)
    assert f["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"] and rec["decisionRechecks"] == []
    assert f["reason"] == "out of scope: the page total belongs to the follow-up work" and "decidedBy" not in f
    sheet, found = cards(rec, {"f-1": CARD})
    assert len(found) == 1 and sheet["prSheet"]["alreadyDecided"] == []


# ---- demotion, fetch, and the unit edges of the rule ----

def test_demotion_a_ruling_whose_scope_citation_fails_becomes_a_card():
    # Axis: a ruling stands only while its scope-ruling citation resolves, re-checked at write time.
    ruled = finding(cite(SCOPE), outcome="ruling", reason="the owner said so")
    rec = build([ruled], doc=doc_of(receipt("- " + SW, scope_line("rr1:someotherkey"))))
    f = the_finding(rec)
    why = "the cited decision is not on record (%s)" % NO_SCOPE_LINE
    assert f["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"]
    assert f["reason"] == "the owner said so" and f[rr.NOT_ON_RECORD_FIELD] == NO_SCOPE_LINE
    assert rec["decisionRechecks"] == [{"finding": "f-1", "from": "ruling", "to": "left-for-owner", "why": why}]
    assert len(cards(rec, {"f-1": CARD})[1]) == 1
    kept = build([ruled], doc=doc_of(receipt("- " + SW, scope_line())))
    assert the_finding(kept)["outcome"] == "ruling" and kept["leftForOwner"] == []
    assert the_finding(kept)["reason"].startswith('scope ruling "%s" (%s); ' % (SW, RU)) and kept["decisionRechecks"] == []


def test_demotion_a_ruling_whose_bound_exceeds_the_rounds_becomes_a_card():
    # Axis: the same re-check for the advisor's bound, whose rounds the record's own round count must reach.
    words = "bound the review at four rounds"
    ruled = finding(cite(BOUND, words=words), outcome="ruling", reason="the advisor bounded it")
    rec = build([ruled], 3, doc=doc_of(receipt("- " + words, bound_line(4))))
    f = the_finding(rec)
    assert f["outcome"] == "left-for-owner"
    assert rec["decisionRechecks"][0]["why"] == "the cited decision is not on record (the review ran 3 rounds, fewer than the bound's 4)"


PU = "https://github.com/o/r/pull/7#issuecomment-777"


@pytest.mark.parametrize("kind, words, line", [(SCOPE, SW, scope_line()), (BOUND, BW, bound_line(2))])
def test_a_receipt_linked_by_its_pull_request_permalink_resolves(kind, words, line):
    # Axis: a vet receipt's own link (/pull/<n>#issuecomment-<id>) is read and counts like its /issues/ form.
    calls = []
    rec = build([finding(cite(kind, url=PU, words=words))], doc=doc_of(receipt("- " + words, line)), calls=calls)
    assert calls == [("o/r", 777)]
    assert the_finding(rec)["outcome"] == "ruling" and rec["leftForOwner"] == []


def test_every_linked_kind_takes_a_pull_request_permalink():
    # Axis: a pull request comment's /pull/ link names the same comment, so an owner ruling recorded on a PR resolves too.
    sources = {"repo": "o/r", "reviewPr": 7, "ownerRulings": {PU: doc_of(chat(SW))}}
    by = {"kind": fo.OWNER_RULING, "ref": {"url": PU, "words": SW}}
    assert fo.on_record(by, sources) == (True, 'owner ruling "%s" (%s)' % (SW, PU))
    assert fo.on_record(cite(SCOPE, url=PU), sources)[0]
    # the comment read must still be that comment on that issue: a /pull/ link to another number is not
    other = "https://github.com/o/r/pull/8#issuecomment-777"
    assert fo.on_record({"kind": fo.OWNER_RULING, "ref": {"url": other, "words": SW}},
                        {"repo": "o/r", "ownerRulings": {other: doc_of(chat(SW))}}) == (False, L3)


def _kept_repeat(earlier, **over):
    repeat = finding(id="f-2", title="Kept repeat", line=20, **over)
    repeat["repeatOf"] = {"findingKey": rr._key(earlier), "id": earlier["id"], "fixHolds": None,
                          "kept": {"outcome": "left-for-owner", "verdict": "confirmed"}}
    return repeat


def test_a_repeat_follows_a_receipt_scope_ruling_only_when_a_line_names_its_own_key():
    # Axis: a kept repeat is checked with its own key, so it follows a receipt scope ruling only when a line names it too.
    earlier = finding(cite(SCOPE))
    repeat = _kept_repeat(earlier)
    both = build([earlier, _kept_repeat(earlier)],
                 doc=doc_of(receipt("- " + SW, scope_line(), "- " + SW, scope_line(rr._key(repeat)))))
    assert {f["id"]: f["outcome"] for f in both["findings"]} == {"f-1": "ruling", "f-2": "ruling"}
    only = build([earlier, _kept_repeat(earlier)], doc=doc_of(receipt("- " + SW, scope_line())))
    assert {f["id"]: f["outcome"] for f in only["findings"]} == {"f-1": "ruling", "f-2": "left-for-owner"}
    assert "f-2" in only["leftForOwner"]


def test_fetch_reads_each_distinct_cited_link_once_for_the_new_kinds_and_none_for_a_non_permalink():
    # Axis: the writer reads the cited comment of a scope ruling and an advisor's bound, once per link, a Critical's included.
    z = dict(X, id="f-3", title="Third", line=30)
    w = dict(X, id="f-4", title="Fourth", line=40)
    v = dict(X, id="f-5", title="Fifth", line=50)
    items = [finding(cite(SCOPE)), dict(Y, decidedBy=cite(BOUND, words=BW)), dict(z, decidedBy=cite(SCOPE, url=RU2)),
             dict(w, decidedBy=cite(SCOPE, url="https://github.com/o/r/issues/7")),
             dict(v, severity="Critical", decidedBy=cite(SCOPE, url=RU3))]
    calls = []
    rec = build(items, doc=doc_of(receipt("- " + SW, scope_line())), calls=calls)
    assert calls == [("o/r", 777), ("o/r", 778), ("o/r", 779)]
    by_id = {f["id"]: f for f in rec["findings"]}
    assert by_id["f-5"]["outcome"] == "left-for-owner" and by_id["f-5"][rr.NOT_ON_RECORD_FIELD] == CRITICAL
    assert rr.shown_reason(by_id["f-5"]).endswith(NOT_ON_RECORD[SCOPE] % CRITICAL)
    assert by_id["f-4"]["outcome"] == "left-for-owner"


def sources(body, **over):
    return {"repo": "o/r", "ownerRulings": {RU: doc_of(body)}, "reviewPr": 7, "reviewRounds": 3, "findingKey": KEY,
            "findingSeverity": "Important", **over}


def test_a_critical_is_refused_before_the_comment_is_read():
    # Axis: E-critical is the first leg, so it needs no comment at all.
    assert fo.on_record(cite(SCOPE), {"findingSeverity": "Critical"}) == (False, CRITICAL)
    assert fo.on_record(cite(BOUND), {"findingSeverity": "Critical", "repo": "o/r"}) == (False, CRITICAL)
    assert fo.on_record(cite(SCOPE), {"findingSeverity": "Important"}) == (False, L2)


def test_the_bound_needs_a_known_round_count():
    # Axis: a missing or non-integer round count is unknown, never zero and never enough.
    body = receipt("- " + BW, bound_line(2))
    words = BW
    good = fo.on_record(cite(BOUND, words=words), sources(body))
    assert good == (True, 'advisor\'s bound "%s" (%s)' % (words, RU))
    for count in (None, True, "3", 2.5):
        assert fo.on_record(cite(BOUND, words=words), sources(body, reviewRounds=count)) == (False, "the review's round count is unknown"), count
    assert fo.on_record(cite(BOUND, words=words), {k: v for k, v in sources(body).items() if k != "reviewRounds"}) == (
        False, "the review's round count is unknown")
    assert fo.on_record(cite(BOUND, words=words), sources(body, reviewRounds=2))[0] is True
    assert fo.on_record(cite(BOUND, words=words), sources(body, reviewRounds=1)) == (
        False, "the review ran 1 rounds, fewer than the bound's 2")


def test_a_receipt_counts_only_on_a_pull_request_given_as_an_integer():
    # Axis: reviewPr must be the integer of the comment's issue; a bool, a string or nothing is not that PR.
    body = receipt("- " + SW, scope_line())
    assert fo.on_record(cite(SCOPE), sources(body))[0] is True
    for pr in (None, True, "7", 8):
        assert fo.on_record(cite(SCOPE), sources(body, reviewPr=pr)) == (False, NOT_THIS_PR), pr
    one = "https://github.com/o/r/issues/1#issuecomment-5"
    assert fo.on_record(cite(SCOPE, url=one), {"repo": "o/r", "ownerRulings": {one: doc_of(body, issue=1, comment=5)},
                                                 "reviewPr": True, "findingKey": KEY}) == (False, NOT_THIS_PR)


@pytest.mark.parametrize("key", [None, "", "  ", 7])
def test_a_scope_marker_never_matches_without_a_usable_finding_key(key):
    # Axis: a missing or blank finding key matches no marker line, even one whose key is blank-looking.
    body = receipt("- " + SW, scope_line())
    assert fo.on_record(cite(SCOPE), sources(body, findingKey=key)) == (False, NO_SCOPE_LINE)


@pytest.mark.parametrize("line", [
    "<!-- superheroes:scope-ruling key=%s  -->" % KEY, "<!-- superheroes:scope-ruling key= -->", "<!-- superheroes:scope-ruling %s -->" % KEY,
    "text <!-- superheroes:scope-ruling key=%s -->" % KEY, "<!-- superheroes:scope-ruling key=%s --> trailing" % KEY,
])
def test_a_malformed_scope_marker_line_counts_for_nothing(line):
    # Axis: a marker is matched against a whole line; anything looser is not a decision line.
    assert fo.on_record(cite(SCOPE), sources(receipt("- " + SW, line))) == (False, NO_SCOPE_LINE)


@pytest.mark.parametrize("line", ["<!-- superheroes:advisor-bound rounds=0 -->", "<!-- superheroes:advisor-bound rounds=02 -->",
                                  "<!-- superheroes:advisor-bound rounds= -->", "<!-- superheroes:advisor-bound rounds=two -->"])
def test_a_malformed_bound_marker_line_counts_for_nothing(line):
    # Axis: the bound's rounds are a positive integer without a leading zero.
    assert fo.on_record(cite(BOUND, words=BW), sources(receipt("- " + BW, line))) == (False, NO_BOUND_LINE)


def test_the_marker_line_may_carry_surrounding_whitespace_and_blank_lines_may_sit_above_it():
    # Axis: the nearest non-blank line above the marker holds the words; whitespace around the marker is stripped.
    body = receipt("- " + SW, "", "   " + scope_line() + "  ")
    assert fo.on_record(cite(SCOPE), sources(body))[0] is True
    first_marker_line_only = receipt(scope_line(), "- " + SW)
    assert fo.on_record(cite(SCOPE), sources(first_marker_line_only)) == (False, NO_SCOPE_LINE)


def test_a_receipt_marker_must_be_the_first_line_and_a_chat_record_is_not_a_receipt():
    # Axis: only a body whose first line is the receipt marker is a receipt.
    late = "intro\n" + receipt("- " + SW, scope_line())
    assert fo.on_record(cite(SCOPE), sources(late)) == (False, NEITHER)
    assert fo.on_record(cite(SCOPE), sources(None)) == (False, NEITHER)
    assert fo.on_record(cite(SCOPE), sources(fo.VET_RECEIPT_MARKER + "   \n- " + SW + "\n" + scope_line()))[0] is True


@pytest.mark.parametrize("words, rounds", [("stop after 3 rounds", 3), ("a 10 review round cap", 10), ("Two Rounds is the bound", 2),
                                           ("ten rounds", 10), ("five review rounds", 5)])
def test_a_chat_bound_states_its_rounds_in_digits_or_words(words, rounds):
    # Axis: the bound reads the first number of rounds the words state.
    assert fo.on_record(cite(BOUND, words=words), sources(chat(words), reviewRounds=rounds)) == (
        True, 'advisor\'s bound "%s" (%s)' % (words, RU))
    assert fo.on_record(cite(BOUND, words=words), sources(chat(words), reviewRounds=rounds - 1))[0] is False


@pytest.mark.parametrize("words", ["round two", "eleven rounds", "0 rounds", "stop soon", "2rounds"])
def test_a_chat_bound_with_no_readable_number_of_rounds_is_refused(words):
    # Axis: no number of rounds, no bound.
    assert fo.on_record(cite(BOUND, words=words), sources(chat(words))) == (False, NO_NUMBER)


def test_a_chat_scope_ruling_needs_no_number_and_no_key():
    # Axis: a chat-ruling record carries the scope ruling by its quoted words alone.
    assert fo.on_record(cite(SCOPE), sources(chat(SW), findingKey=None)) == (True, 'scope ruling "%s" (%s)' % (SW, RU))


# ---- census ----

def test_the_kinds_and_the_shared_shape_check():
    # Axis: the census of the kind sets; the shape check takes the two new kinds exactly as it takes an owner ruling.
    assert fo.DECISION_KINDS == ("canon", "residual", "sheet-answer", "owner-ruling", "scope-ruling", "advisor-bound")
    assert fo.LINKED_KINDS == ("owner-ruling", "scope-ruling", "advisor-bound")
    assert fo.VET_RECEIPT_MARKER == vet_slot.RECEIPT_MARKER
    for kind in ("scope-ruling", "advisor-bound"):
        good = {"kind": kind, "ref": {"url": RU, "words": SW}}
        assert fo.decided_by_well_formed(good)
        for ref in ({"url": RU}, {"words": SW}, {"url": RU, "words": SW, "extra": 1}, {"url": " ", "words": SW}, {"url": RU, "words": ""},
                    {"url": RU, "words": 3}, {"url": None, "words": SW}, RU, None, [RU, SW]):
            assert not fo.decided_by_well_formed({"kind": kind, "ref": ref}), (kind, ref)
        assert not fo.decided_by_well_formed(dict(good, extra=1))
        assert not fo.decided_by_well_formed({"kind": kind})
    assert not fo.decided_by_well_formed({"kind": "scope-rulings", "ref": {"url": RU, "words": SW}})


def test_the_owner_ruling_channel_stays_owner_only():
    # Axis: the account's ownerRulings entries still set an owner-ruling citation, never a new kind.
    entry = {"key": "f-1", "url": RU, "words": SW}
    a = account([entry], [copy.deepcopy(X)])
    rec = rr.build_record(a, readers(doc=doc_of(chat(SW))))
    assert the_finding(rec)["decidedBy"] == {"kind": "owner-ruling", "ref": {"url": RU, "words": SW}}
