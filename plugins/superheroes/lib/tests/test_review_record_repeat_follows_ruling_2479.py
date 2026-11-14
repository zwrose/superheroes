"""A kept repeat follows its earlier finding's cited ruling when the record is written.

When the earlier finding reads `ruling` with a cited decision that is on record now (for example the owner ruled on
its card), a kept `left-for-owner` repeat that cites no decision and is named by no carried check reads that ruling:
it carries a copy of the cited decision, its reason leads with the citation and names the earlier finding, and it adds
no owner card, no leftover line and no `leftForOwner` entry. Findings merged into it follow it, each with its own copy
of the citation. Every other repeat is as before (the fixed-follow of the earlier order included).

Edges: E1 the citation does not resolve (R3) · E2 the earlier ruling cites no decision (R4) · E3 the repeat's kept
outcome is not left-for-owner (R5) · E4 the repeat carries a decidedBy or a carried check names it (the fixed-follow
tests of the earlier order) · E5 a ring of repeats (the same file) · E6 a later rewrite whose citation stops resolving
demotes every inherited ruling (R8).
"""
import copy
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import review_record as rr  # noqa: E402

from test_review_record_carried_recheck import PRIOR, X, account, entry, readers  # noqa: E402
from test_review_record_owner_ruling import DOC, U, W, cards  # noqa: E402
from test_review_record_repeat_follows_2438 import OLD, by_id, kept, mark, repeat  # noqa: E402
from test_review_record_session import STANDING, CANON_SOURCES  # noqa: E402

LFO = "left-for-owner"
CITATION = f'owner ruling "{W}" ({U})'
RULED = {"key": "f-1", "url": U, "words": W}
MEMBER_RAW = "m::t@L1"
WAS = "merged note"


def rd(doc=DOC, sources=None):
    """The carried-recheck readers with the owner-ruling comment reader and the decision sources added."""
    return {**readers(), "owner_ruling_comment": lambda repo, cid: copy.deepcopy(doc),
            "decision_sources": lambda root, base, answers, pr: dict(sources or {})}


def acct(findings, rulings=(RULED,), checks=()):
    return dict(account(list(checks), findings), ownerRulings=[dict(r) for r in rulings])


def build(findings, rulings=(RULED,), checks=(), **kw):
    return rr.build_record(acct(findings, rulings, checks), rd(**kw), prior=PRIOR)


def rebuild(rec, **kw):
    """Write again from the findings a record holds, as a later write of the same account does."""
    return rr.build_record(account([], [{k: v for k, v in f.items() if k != "sheetPart"} for f in rec["findings"]]),
                           rd(**kw), prior=PRIOR)


def member_repeat():
    """A kept repeat of X that lists one merged member."""
    return repeat(repeatOf=mark(kept={"outcome": LFO, "verdict": "wrong", "members": [MEMBER_RAW]}))


def member():
    return dict(X, id="f-3", title="Merged one", line=30, findingKey=MEMBER_RAW, outcome=LFO, reason=WAS)


# --- the field case ---

def test_r1_a_kept_repeat_of_a_finding_the_owner_ruled_on_reads_that_ruling_and_adds_no_card():
    # axis: the field case, the owner ruled on the earlier finding's card, so its kept repeat reads the same ruling
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2479_repeat_follows_ruling.md
    rec = build([X, repeat()])
    rows = by_id(rec)
    assert rows["f-1"]["outcome"] == "ruling"
    r = rows["f-2"]
    assert r["outcome"] == "ruling"
    assert r["decidedBy"] == rows["f-1"]["decidedBy"] == {"kind": "owner-ruling", "ref": {"url": U, "words": W}}
    assert r["reason"].startswith(CITATION)
    assert rr.REPEAT_FOLLOWS_RULING.format(name="f-1") in r["reason"]
    assert r["reason"].endswith("; earlier: " + OLD)
    assert r["repeatOf"][rr.REPEAT_KEPT_FIELD]["outcome"] == "ruling"
    assert r["sheetPart"] == rr.rfs.OUTCOME_SHEET_PART["ruling"]
    assert rec["leftForOwner"] == []
    assert rr.leftover_line(repeat()) not in str(rec["whatIsMissing"])
    # the sheet asks for a leftovers entry for every card, so it builds with none only when no finding is left for the owner
    assert cards(rec, {})[1] == []


def test_r2_a_repeat_follows_an_earlier_ruling_that_cites_canon():
    # axis: the citation is copied whatever its kind, a Canon entry that is on record carries to the repeat
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2479_repeat_follows_ruling.md
    by = {"kind": "canon", "ref": STANDING}
    ruled = dict(X, outcome="ruling", reason="decided by the standing entry", decidedBy=by)
    rec = build([ruled, repeat()], rulings=(), sources=CANON_SOURCES)
    r = by_id(rec)["f-2"]
    assert by_id(rec)["f-1"]["outcome"] == "ruling"
    assert r["outcome"] == "ruling" and r["decidedBy"] == by
    assert r["reason"] == f"canon {STANDING}; " + rr.REPEAT_FOLLOWS_RULING.format(name="f-1") + "; earlier: " + OLD
    assert rec["leftForOwner"] == []


# --- E1: fail closed ---

def test_r3_e1_an_owner_ruling_that_does_not_resolve_leaves_the_repeat_held_behind_the_earlier_finding():
    # axis: the repeat reads a ruling only while the citation is on record, otherwise it is unchanged and held behind X
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2479_repeat_follows_ruling.md
    given = repeat()
    rec = build([X, given], doc=None)
    rows = by_id(rec)
    assert rows["f-1"]["outcome"] == LFO
    r = rows["f-2"]
    assert (r["outcome"], r["reason"], r["repeatOf"]) == (LFO, OLD, given["repeatOf"])
    assert "decidedBy" not in r
    assert rec["leftForOwner"] == ["f-1"]


def test_r3_e1_the_follow_itself_leaves_the_repeat_alone_when_the_citation_is_not_on_record():
    # axis: the follow checks the citation on its own, so a ruling the record writer did not re-check never moves a repeat
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2479_repeat_follows_ruling.md
    # (build_record demotes an unresolved ruling before the follow, so only a direct call delivers this input to the check)
    by = {"kind": "owner-ruling", "ref": {"url": U, "words": W}}
    ruled = dict(X, outcome="ruling", reason="the owner ruled", decidedBy=by)
    findings = [ruled, repeat()]
    before = copy.deepcopy(findings)
    assert rr._follow_repeats(findings, [], lambda: {}) == before
    assert findings == before
    resolves = {"repo": "o/r", "ownerRulings": {U: DOC}}
    assert rr._follow_repeats(findings, [], lambda: resolves)[1]["outcome"] == "ruling"
    assert rr._follow_repeats(findings, []) == before  # with no sources the ruling branch never runs


# --- E2, sibling healthy cases ---

@pytest.mark.parametrize("earlier, cards_left", [
    pytest.param(X, ["f-1"], id="earlier-left-for-owner"),
    pytest.param(dict(X, outcome="craft", reason="a craft call"), ["f-2"], id="earlier-craft"),
    pytest.param(dict(X, outcome=None, reason="still open"), ["f-2"], id="earlier-open"),
    pytest.param(dict(X, outcome="ruling", reason="the owner ruled it out of scope (prose)"), ["f-2"],
                 id="E2-earlier-ruling-with-no-decidedBy"),
])
def test_r4_a_repeat_whose_earlier_finding_is_not_a_cited_ruling_is_unchanged_and_keeps_its_card(earlier, cards_left):
    # axis: only an earlier finding at ruling with a cited decision is followed; every other earlier outcome leaves the repeat
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2479_repeat_follows_ruling.md
    given = repeat()
    rec = build([earlier, given], rulings=())
    r = by_id(rec)["f-2"]
    assert (r["outcome"], r["reason"], r["repeatOf"]) == (LFO, OLD, given["repeatOf"])
    assert "decidedBy" not in r
    assert rec["leftForOwner"] == cards_left


# --- E3 ---

def test_r5_e3_a_repeat_kept_at_another_outcome_is_unchanged_whatever_its_earlier_finding_reads():
    # axis: only a repeat kept at left-for-owner follows a ruling; one kept at craft stays craft
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2479_repeat_follows_ruling.md
    given = repeat("craft")
    rec = build([X, given])
    rows = by_id(rec)
    assert rows["f-1"]["outcome"] == "ruling"
    r = rows["f-2"]
    assert (r["outcome"], r["reason"], r["repeatOf"]) == ("craft", OLD, given["repeatOf"])
    assert "decidedBy" not in r


# --- the fixed-follow is unchanged ---

def test_r6_a_carried_fixed_check_still_moves_the_wrong_graded_repeat_to_fixed():
    # axis: the fixed branch is as it was, a carried fix on the earlier finding moves its wrong-graded kept repeat to fixed
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2479_repeat_follows_ruling.md
    rec = build([X, repeat()], rulings=(), checks=[entry()])
    rows = by_id(rec)
    assert rows["f-1"]["outcome"] == "fixed"
    r = rows["f-2"]
    assert r["outcome"] == "fixed"
    assert r["reason"] == rr.REPEAT_FOLLOWS_FIXED.format(name="f-1") + "; earlier: " + OLD
    assert r["repeatOf"]["fixHolds"] is True and r["repeatOf"][rr.REPEAT_KEPT_FIELD] == kept("fixed", "wrong")
    assert "decidedBy" not in r
    assert rec["leftForOwner"] == []


# --- B3: the citation once ---

def test_r7_b3_a_later_write_of_the_same_findings_shows_the_citation_once():
    # axis: the inherited reason leads with the citation text, so the refresh on a later write never prepends it again
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2479_repeat_follows_ruling.md
    rec = build([X, repeat()])
    again = rebuild(rec)
    r = by_id(again)["f-2"]
    assert r["outcome"] == "ruling" and r["decidedBy"] == by_id(rec)["f-2"]["decidedBy"]
    assert r["reason"].count(CITATION) == 1
    assert r["reason"] == by_id(rec)["f-2"]["reason"]


# --- B1, B2: merged members and a citation that stops resolving ---

def test_r8_b1_a_merged_member_follows_with_its_own_copy_and_all_demote_when_the_citation_stops_resolving():
    # axis: each member moved to ruling carries its own decidedBy, so a later write that cannot resolve it demotes it
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2479_repeat_follows_ruling.md
    rec = build([X, member_repeat(), member()])
    rows = by_id(rec)
    m = rows["f-3"]
    assert (rows["f-2"]["outcome"], m["outcome"]) == ("ruling", "ruling")
    assert m["decidedBy"] == rows["f-1"]["decidedBy"] and m["decidedBy"] is not rows["f-1"]["decidedBy"]
    assert m["reason"] == (f'{CITATION}; ' + rr.REPEAT_MEMBER_FOLLOWS_RULING.format(name="f-2") + "; earlier: " + WAS)
    assert rec["leftForOwner"] == []
    later = rebuild(rec, doc=None)
    assert {i: row["outcome"] for i, row in by_id(later).items()} == {"f-1": LFO, "f-2": LFO, "f-3": LFO}


def test_r9_b2_after_the_demotion_the_repeat_is_held_behind_the_earlier_finding():
    # axis: a repeat demoted with its earlier finding keeps no card of its own, the earlier finding holds the one card
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2479_repeat_follows_ruling.md
    later = rebuild(build([X, member_repeat(), member()]), doc=None)
    assert "f-1" in later["leftForOwner"] and "f-2" not in later["leftForOwner"]
    assert by_id(later)["f-2"]["outcome"] == LFO


# --- chains ---

def test_r10_a_repeat_of_a_repeat_of_a_ruled_finding_reads_the_ruling_whatever_their_order():
    # axis: the chain settles to a fixed point, a repeat of a repeat that moved to ruling follows on the next pass
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2479_repeat_follows_ruling.md
    first = repeat(fid="f-2", title="Same mistake again", line=12)
    second = repeat(fid="f-3", title="Third sighting", line=15, of=rr._key(first))
    rec = build([X, second, first])
    rows = by_id(rec)
    assert (rows["f-2"]["outcome"], rows["f-3"]["outcome"]) == ("ruling", "ruling")
    assert rows["f-3"]["decidedBy"] == rows["f-1"]["decidedBy"]
    assert rows["f-3"]["reason"].startswith(CITATION)
    assert rr.REPEAT_FOLLOWS_RULING.format(name="f-2") in rows["f-3"]["reason"]
    assert rec["leftForOwner"] == []


# --- the input ---

def test_r11_the_account_findings_are_never_changed():
    # axis: the follow returns new findings and leaves the supplied dicts as they were
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2479_repeat_follows_ruling.md
    a = acct([X, member_repeat(), member()])
    before = copy.deepcopy(a["findings"])
    rr.build_record(a, rd(), prior=PRIOR)
    assert a["findings"] == before
