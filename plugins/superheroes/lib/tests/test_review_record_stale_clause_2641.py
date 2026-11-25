"""Issue 2641: a finding that ends `ruling` carries no stale "not on record" clause an earlier unresolved read stamped.

A citation that does not resolve keeps every clause as before; the owner's quoted words, the open reason, merge marks,
the carried suffix and `earlier:` text are kept byte for byte.
"""
import ast
import copy
import re
from pathlib import Path

import pytest

import canon
import finding_outcomes as fo
import pr_sheet
import review_record as rr
import review_record_session as rs
from test_review_record_owner_ruling import ADVISOR, DOC, L2, L3, U, W, WORDS, X, account, readers, the_finding
from test_review_record_repeat_follows_2438 import LFO, OLD, kept, mark, repeat
from test_review_record_session import CANON_SOURCES, STANDING, Fake

BY = {"kind": "owner-ruling", "ref": {"url": U, "words": W}}
CITE = f'owner ruling "{W}" ({U})'
A_L2 = "the cited decision is not on record: " + L2
B_L3 = f"the cited decision is not on record ({L3})"
C_L3 = f"the owner ruling it cites is not on record ({L3})"
RESOLVES = {"repo": "o/r", "ownerRulings": {U: DOC}}
MEMBER_RAW = "m::t@L1"


def stamped(**over):
    """The left-for-owner finding `settle` stamps when no repository is named: shape A with the repository leg's text."""
    got = fo.settle(X, ruling={"decidedBy": copy.deepcopy(BY)}, sources={}, open_reason="waits for the owner")
    assert got["reason"] == "waits for the owner; " + A_L2
    return {**X, "outcome": got["outcome"], "reason": got["reason"], "decidedBy": got["decidedBy"], **over}


def record(finding, **kw):
    return rr.build_record(account([], [finding]), readers(**kw))


def doc_for(words):
    return dict(DOC, body=canon.ruling_record("2026-10-18", "12:00", words, "finding f-1"))


def test_t1_a_stamped_clause_is_gone_once_the_leftover_resolves_and_is_promoted():
    # Axis: DoD row 1, the shape `settle` stamps goes when the write-time re-check promotes the finding to ruling.
    rec = record(stamped())
    f = the_finding(rec)
    assert f["outcome"] == "ruling"
    assert f["reason"] == f"{CITE}; waits for the owner"
    (decided,) = pr_sheet.build([rec], ADVISOR, WORDS)["prSheet"]["alreadyDecided"]
    assert decided["detail"] == f["reason"] and "not on record" not in decided["detail"]


def test_t2_a_carried_clause_goes_and_the_carried_suffix_stays_on_the_part_before_it():
    # Axis: DoD row 1, the record put the words in front but kept the clause; the carried suffix moves to the part before it.
    carried = stamped(outcome="ruling", reason=f"{CITE}; waits for the owner; {A_L2}" + rs.CARRIED)
    f = the_finding(record(carried))
    assert f["outcome"] == "ruling" and f["reason"] == f"{CITE}; waits for the owner" + rs.CARRIED
    promoted = the_finding(record(stamped(reason=f"waits for the owner; {A_L2}" + rs.CARRIED)))
    assert promoted["outcome"] == "ruling" and promoted["reason"] == f"{CITE}; waits for the owner" + rs.CARRIED


def test_t3_a_shape_b_clause_in_the_middle_of_the_reason_goes():
    # Axis: BRIEF-1, a demotion clause (shape B) between the citation and later prose is removed; the prose stays.
    ruled = {**X, "outcome": "ruling", "decidedBy": copy.deepcopy(BY),
             "reason": f"{CITE}; {B_L3}; the owner said so"}
    f = the_finding(record(ruled))
    assert f["outcome"] == "ruling" and f["reason"] == f"{CITE}; the owner said so"


def test_t4_a_shape_c_clause_goes_when_the_leftover_resolves():
    # Axis: shape C (the owner ruling it cites is not on record) is removed on promotion and the open reason stays.
    left = {**X, "decidedBy": copy.deepcopy(BY), "reason": "waits for the owner; " + C_L3}
    f = the_finding(record(left))
    assert f["outcome"] == "ruling" and f["reason"] == f"{CITE}; waits for the owner"


def test_t5_a_non_linked_ruling_loses_the_clause_and_gets_no_citation_prepended():
    # Axis: BRIEF-2, an already-ruling canon finding whose citation resolves is cleaned only; nothing is prepended.
    ruled = {**X, "outcome": "ruling", "decidedBy": {"kind": "canon", "ref": STANDING},
             "reason": "decided earlier; the cited decision is not on record: the cited Canon entry is not on record"}
    rec = record(ruled, fake=Fake(sources=CANON_SOURCES))
    f = the_finding(rec)
    assert f["outcome"] == "ruling" and f["reason"] == "decided earlier" and rec["decisionRechecks"] == []


@pytest.mark.parametrize("words, open_reason", [
    pytest.param("keep it; " + A_L2, "waits for the owner", id="the-whole-clause-inside-the-words"),
    pytest.param("keep it; " + A_L2 + "; and more", "waits for the owner", id="a-whole-clause-as-a-middle-part-of-the-words"),
])
def test_t6_the_owners_quoted_words_are_never_split_or_matched(words, open_reason):
    # Axis: BRIEF-4, the lead span holds the owner's words whole; only the real clause after it goes, and the citation is not doubled.
    cite = f'owner ruling "{words}" ({U})'
    ruled = {**X, "outcome": "ruling", "decidedBy": {"kind": "owner-ruling", "ref": {"url": U, "words": words}},
             "reason": f"{cite}; {open_reason}; {A_L2}"}
    f = the_finding(record(ruled, doc=doc_for(words)))
    assert f["outcome"] == "ruling" and f["reason"] == f"{cite}; {open_reason}"
    assert f["reason"].count(cite) == 1


def test_t6_a_free_form_note_that_only_looks_like_a_clause_is_kept():
    # Axis: BRIEF-4, a part whose why is not in the list is prose, so it is not dropped.
    note = "the cited decision is not on record: an unrelated prose note"
    ruled = {**X, "outcome": "ruling", "decidedBy": copy.deepcopy(BY), "reason": f"{CITE}; {note}"}
    assert the_finding(record(ruled))["reason"] == f"{CITE}; {note}"


def test_t7_a_citation_that_does_not_resolve_keeps_every_clause():
    # Axis: DoD row 2, with no readable comment the finding stays for the owner and its stamped clause stays, as today.
    f = the_finding(record(stamped(), doc=None))
    assert f["outcome"] == "left-for-owner"
    assert "the cited decision is not on record: the ruling's link is not in this repository" in f["reason"]
    assert f["reason"] == "waits for the owner; " + A_L2 + "; " + C_L3


@pytest.mark.parametrize("shape", [
    pytest.param(A_L2, id="shape-A"),
    pytest.param(B_L3, id="shape-B"),
    pytest.param(C_L3, id="shape-C"),
])
def test_t7_a_reason_holding_a_shape_is_unchanged_when_its_citation_does_not_resolve(shape):
    # Axis: DoD row 2, fail closed; the same shapes survive when the citation does not resolve, canon and linked kinds alike.
    reason = f"waits for the owner; {shape}"
    canon_left = {**X, "decidedBy": {"kind": "canon", "ref": STANDING}, "reason": reason}
    assert the_finding(record(canon_left, fake=Fake()))["reason"] == reason
    demoted = the_finding(record({**X, "outcome": "ruling", "decidedBy": copy.deepcopy(BY), "reason": f"{CITE}; {shape}"}, doc=None))
    assert demoted["outcome"] == "left-for-owner" and demoted["reason"] == f"{B_L3}; {CITE}; {shape}"


def test_t8_a_repeat_inheriting_a_ruling_writes_its_earlier_text_without_the_clause():
    # Axis: BRIEF-3, the `earlier:` text of a repeat and of a merged member moved to ruling carries no stale clause.
    ruled = {**X, "outcome": "ruling", "reason": "the owner ruled", "decidedBy": copy.deepcopy(BY)}
    given = repeat(repeatOf=mark(kept={**kept(), "members": [MEMBER_RAW]}), reason=f"{OLD}; {A_L2}")
    member = {**X, "id": "f-3", "title": "Merged one", "line": 30, "findingKey": MEMBER_RAW, "outcome": LFO,
              "reason": f"merged note; {A_L2}"}
    out = rr._follow_repeats([ruled, given, member], [], lambda: RESOLVES)
    assert out[1]["reason"] == f"{CITE}; " + rr.REPEAT_FOLLOWS_RULING.format(name="f-1") + "; earlier: " + OLD
    assert out[2]["reason"] == f"{CITE}; " + rr.REPEAT_MEMBER_FOLLOWS_RULING.format(name="f-2") + "; earlier: merged note"
    assert out[1]["outcome"] == out[2]["outcome"] == "ruling"
    bare = repeat(reason=A_L2)
    assert rr._follow_repeats([ruled, bare], [], lambda: RESOLVES)[1]["reason"] == (
        f"{CITE}; " + rr.REPEAT_FOLLOWS_RULING.format(name="f-1"))


def _failure_texts():
    """Every string the module returns as the second element of `return False, ...` or `return None, ...`."""
    tree = ast.parse((Path(fo.__file__)).read_text(encoding="utf-8"))
    texts = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Return) and isinstance(node.value, ast.Tuple) and len(node.value.elts) == 2):
            continue
        head, tail = node.value.elts
        if not (isinstance(head, ast.Constant) and (head.value is False or head.value is None)):
            continue
        if isinstance(tail, ast.Constant) and isinstance(tail.value, str):
            texts.append(tail.value)
        elif (isinstance(tail, ast.BinOp) and isinstance(tail.op, ast.Mod) and isinstance(tail.left, ast.Constant)
              and isinstance(tail.left.value, str) and isinstance(tail.right, ast.Tuple)):
            texts.append(tail.left.value % tuple(range(3, 3 + len(tail.right.elts))))
    return texts


def test_t9_census_every_failure_text_on_record_returns_is_in_the_list_and_nothing_in_it_is_dead():
    # Axis: the list and the module's failure returns agree both ways, so a new text cannot slip past the cleanup.
    texts = _failure_texts()
    assert len(texts) == 24 and "the review ran 3 rounds, fewer than the bound's 4" in texts
    patterns = [re.compile(p) for p in fo.UNRESOLVED_WHYS]
    assert [t for t in texts if not any(p.fullmatch(t) for p in patterns)] == []
    assert [p.pattern for p in patterns if not any(p.fullmatch(t) for t in texts)] == []


@pytest.mark.parametrize("reason, expected", [
    pytest.param(A_L2 + rs.CARRIED + "; open", "open" + rs.CARRIED, id="a-leading-clause-hands-its-suffix-to-the-next-part"),
    pytest.param(A_L2 + rs.CARRIED, "", id="every-part-dropped-is-empty"),
    pytest.param(f"a (merged into b); {C_L3}{rs.CARRIED}{rs.CARRIED}; c", f"a (merged into b){rs.CARRIED}{rs.CARRIED}; c",
                 id="a-run-of-suffixes-moves-whole"),
    pytest.param("the cited decision is not on record: some other reason", "the cited decision is not on record: some other reason",
                 id="a-why-outside-the-list-is-prose"),
    pytest.param("", "", id="empty"),
    pytest.param(None, None, id="not-a-string"),
])
def test_t12_the_helper_drops_only_stale_parts_and_moves_the_carried_suffix(reason, expected):
    # Axis: the helper's own contract, a dropped part's carried suffix survives on a kept part, and nothing else changes.
    assert rr._without_stale_clauses(reason) == expected


@pytest.mark.parametrize("finding_over", [
    pytest.param({}, id="promotion"),
    pytest.param({"outcome": "ruling"}, id="linked-refresh"),
])
def test_t11_a_reason_that_was_only_a_stale_clause_becomes_the_citation_text(finding_over):
    # Axis: all-stale, a left-for-owner finding whose reason is only shape A reads the resolved citation text alone.
    f = the_finding(record({**X, "decidedBy": copy.deepcopy(BY), "reason": A_L2, **finding_over}))
    assert f["outcome"] == "ruling" and f["reason"] == f'owner ruling "{W}" ({U})'


def test_t11_the_same_holds_for_a_non_linked_ruling():
    # Axis: all-stale on the non-linked already-ruling branch, the reason is the citation text alone.
    ruled = {**X, "outcome": "ruling", "decidedBy": {"kind": "canon", "ref": STANDING},
             "reason": "the cited decision is not on record: the cited Canon entry is not on record"}
    assert the_finding(record(ruled, fake=Fake(sources=CANON_SOURCES)))["reason"] == f"canon {STANDING}"
