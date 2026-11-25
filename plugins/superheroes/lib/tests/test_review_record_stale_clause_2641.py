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
              "reason": f"merged note; {A_L2}" + rs.MERGED_INTO_FORMAT.format("f-2")}
    out = rr._follow_repeats([ruled, given, member], [], lambda: RESOLVES)
    assert out[1]["reason"] == f"{CITE}; " + rr.REPEAT_FOLLOWS_RULING.format(name="f-1") + "; earlier: " + OLD
    assert out[2]["reason"] == (f"{CITE}; " + rr.REPEAT_MEMBER_FOLLOWS_RULING.format(name="f-2") + "; earlier: merged note"
                                + rs.MERGED_INTO_FORMAT.format("f-2"))
    assert out[1]["outcome"] == out[2]["outcome"] == "ruling"
    bare = repeat(reason=A_L2)
    assert rr._follow_repeats([ruled, bare], [], lambda: RESOLVES)[1]["reason"] == (
        f"{CITE}; " + rr.REPEAT_FOLLOWS_RULING.format(name="f-1"))


def _failure_returns():
    """The second element of every `return False, ...` or `return None, ...` in finding_outcomes, as AST nodes."""
    tree = ast.parse((Path(fo.__file__)).read_text(encoding="utf-8"))
    tails = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Return) and isinstance(node.value, ast.Tuple) and len(node.value.elts) == 2):
            continue
        head, tail = node.value.elts
        if isinstance(head, ast.Constant) and (head.value is False or head.value is None):
            tails.append(tail)
    return tails


def _failure_kind(tail):
    """How one failure return's second element is written: a named WHY_ text, the formatted WHY_ text, a text
    forwarded from a leg (`why`), no text (None), or anything else, which is a text with no home."""
    if isinstance(tail, ast.Name) and tail.id.startswith("WHY_"):
        return "named"
    if (isinstance(tail, ast.BinOp) and isinstance(tail.op, ast.Mod) and isinstance(tail.left, ast.Name)
            and tail.left.id.startswith("WHY_")):
        return "formatted"
    if isinstance(tail, ast.Name) and tail.id == "why":
        return "forwarded"
    if isinstance(tail, ast.Constant) and tail.value is None:
        return "none"
    return "unhomed"


def test_t9_the_classifier_refuses_every_inline_text_shape():
    # Axis: a literal, an f-string and an inline percent format each read as a text with no home.
    for src in ('"some failure"', 'f"some {x}"', '"unregistered failure %s" % (value,)', '"a" + b', "WHY_X + 'y'"):
        assert _failure_kind(ast.parse(src, mode="eval").body) == "unhomed", src
    assert _failure_kind(ast.parse("WHY_FEWER_ROUNDS % (a, b)", mode="eval").body) == "formatted"


def test_t9_every_failure_text_has_one_home_and_the_cleanup_reads_it():
    # Axis: every failure return is classified, none carries a text with no home, the list holds exactly the named
    # texts, and each one, stamped as the settle clause, is a stale clause the cleanup removes.
    tails = _failure_returns()
    kinds = [_failure_kind(t) for t in tails]
    assert [ast.unparse(t) for t, k in zip(tails, kinds) if k == "unhomed"] == []
    named = {t.id for t, k in zip(tails, kinds) if k == "named"}
    formatted = {t.left.id for t, k in zip(tails, kinds) if k == "formatted"}
    assert formatted == {"WHY_FEWER_ROUNDS"}
    assert {getattr(fo, n) for n in named} == set(fo.UNRESOLVED_WHY_TEXTS) and len(fo.UNRESOLVED_WHY_TEXTS) == len(named)
    for why in fo.UNRESOLVED_WHY_TEXTS + tuple(fo.WHY_FEWER_ROUNDS % pair for pair in ((-1, 2), (0, 2), (12, 40))):
        assert rr._without_stale_clauses("open; " + fo.UNRESOLVED_CLAUSE % why) == "open", why


def test_t13_a_bound_that_fell_short_on_a_negative_count_resolves_without_its_clause():
    # Axis: a real advisor-bound failure, rendered by the module from a count the account accepts, is removed once the
    # bound resolves on a later write; its unresolved twin keeps it.
    words = "bound the review at two rounds"
    body = "\n".join([fo.VET_RECEIPT_MARKER, "## Vet receipt", "", "**Decisions.**", "- " + words,
                      "<!-- superheroes:advisor-bound rounds=2 -->", ""])
    url = "https://github.com/o/r/issues/7#issuecomment-777"
    doc = {"id": 777, "issue_url": "https://api.github.com/repos/o/r/issues/7", "html_url": url, "body": body,
           "author_association": "MEMBER", "user": {"login": "o"}}
    by = {"kind": fo.ADVISOR_BOUND, "ref": {"url": url, "words": words}}
    ruled = {**X, "outcome": "ruling", "decidedBy": copy.deepcopy(by), "reason": "the advisor bounded it"}

    def build(finding, count):
        a = account([], [finding])
        a["rounds"] = {"count": count, "cap": 3, "stoppedAtCap": False}
        return the_finding(rr.build_record(a, readers(doc=doc)))

    demoted = build(ruled, -1)
    assert demoted["outcome"] == "left-for-owner"
    assert demoted["reason"].startswith(rr._DEMOTED_CLAUSE % (fo.WHY_FEWER_ROUNDS % (-1, 2)))
    restored = build(demoted, 2)
    assert restored["outcome"] == "ruling"
    assert restored["reason"] == f'advisor\'s bound "{words}" ({url}); the advisor bounded it'
    assert build(demoted, 1)["outcome"] == "left-for-owner"


@pytest.mark.parametrize("reason, expected", [
    pytest.param(A_L2 + rs.CARRIED + "; open", "open" + rs.CARRIED, id="a-leading-clause-hands-its-suffix-to-the-next-part"),
    pytest.param(A_L2 + rs.CARRIED, rs.CARRIED, id="every-part-dropped-leaves-its-marks"),
    pytest.param(A_L2, "", id="every-part-dropped-with-no-marks-is-empty"),
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


PAREN_REP = "app/(auth)/page.tsx::unchecked-index@L3"


@pytest.mark.parametrize("rep", [pytest.param("rep-1", id="plain-id"), pytest.param(PAREN_REP, id="id-with-parentheses")])
def test_t14_a_merge_mark_after_the_clause_is_kept_whatever_its_id_holds(rep):
    # Axis: the merge mark is read as the session writer reads it, so an id with parentheses is peeled too.
    mark = rs.MERGED_INTO_FORMAT.format(rep)
    f = the_finding(record(stamped(reason="waits for the owner; " + A_L2 + mark)))
    assert f["outcome"] == "ruling" and f["reason"] == f"{CITE}; waits for the owner{mark}"
    assert rs.merged_into(f["reason"]) == rep


@pytest.mark.parametrize("over", [pytest.param({}, id="promotion"), pytest.param({"outcome": "ruling"}, id="linked-refresh")])
def test_t15_a_reason_that_is_only_a_clause_and_its_mark_keeps_the_mark(over):
    # Axis: all-stale with a merge mark, the citation text replaces the clause and the mark stays, so the member
    # is still read as merged.
    mark = rs.MERGED_INTO_FORMAT.format("rep-1")
    f = the_finding(record(stamped(reason=A_L2 + mark, **over)))
    assert f["outcome"] == "ruling" and f["reason"] == CITE + mark and rs.merged_into(f["reason"]) == "rep-1"


def test_t16_a_promotion_is_not_mistaken_for_a_longer_canon_id_it_starts_like():
    # Axis: the reason leads with the citation only as a whole part, so entry -1 is still named before a note on -10.
    left = {**X, "decidedBy": {"kind": "canon", "ref": STANDING}, "reason": f"canon {STANDING}0 was considered earlier"}
    f = the_finding(record(left, fake=Fake(sources=CANON_SOURCES)))
    assert f["outcome"] == "ruling" and f["reason"] == f"canon {STANDING}; canon {STANDING}0 was considered earlier"
    again = {**X, "decidedBy": {"kind": "canon", "ref": STANDING}, "reason": f"canon {STANDING}; waits"}
    assert the_finding(record(again, fake=Fake(sources=CANON_SOURCES)))["reason"] == f"canon {STANDING}; waits"


def test_t17_a_citation_inside_prose_and_a_placeholder_in_the_text_both_survive():
    # Axis: a citation held whole inside prose comes back as it was, and text that already holds the placeholder's
    # characters comes back unchanged.
    inside = f"see {CITE} for more; {A_L2}"
    assert rr._strip_stale(inside, lead=CITE) == (f"see {CITE} for more", "")
    odd = "x\x00lead\x00y"
    assert rr._strip_stale(f"{odd}; {CITE}; {A_L2}", lead=CITE) == (f"{odd}; {CITE}", "")


def test_t18_a_repeat_and_its_member_hold_the_inherited_citation_whole_in_their_earlier_text():
    # Axis: the repeat and the merged member each pass the citation they inherit, so clause-shaped owner words in
    # an earlier reason that carried it are never cut, and a merge mark after a stale clause is kept.
    words = "keep it; " + A_L2 + "; and more"
    cite = f'owner ruling "{words}" ({U})'
    by = {"kind": "owner-ruling", "ref": {"url": U, "words": words}}
    ruled = {**X, "outcome": "ruling", "reason": "the owner ruled", "decidedBy": copy.deepcopy(by)}
    given = repeat(repeatOf=mark(kept={**kept(), "members": [MEMBER_RAW]}), reason=f"{OLD}; {cite}; {A_L2}")
    member = {**X, "id": "f-3", "title": "Merged one", "line": 30, "findingKey": MEMBER_RAW, "outcome": LFO,
              "reason": f"{cite}; merged note; {A_L2}" + rs.MERGED_INTO_FORMAT.format("f-2")}
    resolves = {"repo": "o/r", "ownerRulings": {U: doc_for(words)}}
    out = rr._follow_repeats([ruled, given, member], [], lambda: resolves)
    assert out[1]["reason"] == f"{cite}; " + rr.REPEAT_FOLLOWS_RULING.format(name="f-1") + f"; earlier: {OLD}; {cite}"
    assert out[2]["reason"] == (f"{cite}; " + rr.REPEAT_MEMBER_FOLLOWS_RULING.format(name="f-2")
                                + f"; earlier: {cite}; merged note" + rs.MERGED_INTO_FORMAT.format("f-2"))
    bare_member = dict(member, reason=A_L2 + rs.MERGED_INTO_FORMAT.format("f-2"))
    out = rr._follow_repeats([ruled, given, bare_member], [], lambda: resolves)
    assert out[2]["reason"] == f"{cite}; " + rr.REPEAT_MEMBER_FOLLOWS_RULING.format(name="f-2") + rs.MERGED_INTO_FORMAT.format("f-2")


QUOTED = "keep it; " + A_L2 + "; and more"
QUOTED_CITE = f'owner ruling "{QUOTED}" ({U})'
QUOTED_BY = {"kind": "owner-ruling", "ref": {"url": U, "words": QUOTED}}


@pytest.mark.parametrize("before", [
    pytest.param("decided by ", id="after-decided-by"),
    pytest.param("note; earlier: ", id="after-earlier"),
    pytest.param("note (", id="inside-a-bracket"),
])
def test_t19_a_citation_the_writer_put_after_its_own_prefix_is_held_whole_on_a_later_write(before):
    # Axis: `settle` writes "decided by <citation>" and the repeat path writes "earlier: <citation>"; a later write
    # resolving the same citation keeps its quoted words whole there and still drops the real clause.
    ruled = {**X, "outcome": "ruling", "decidedBy": copy.deepcopy(QUOTED_BY), "reason": f"{before}{QUOTED_CITE}; {A_L2}"}
    f = the_finding(record(ruled, doc=doc_for(QUOTED)))
    assert f["outcome"] == "ruling" and f["reason"] == f"{QUOTED_CITE}; {before}{QUOTED_CITE}"


def test_t19_the_repeat_writes_earlier_text_a_later_write_reads_back_unchanged():
    # Axis: the reason `_follow_repeats` writes, read again by a later record write, keeps the inherited quote whole.
    ruled = {**X, "outcome": "ruling", "reason": "the owner ruled", "decidedBy": copy.deepcopy(QUOTED_BY)}
    given = repeat(reason=f"{OLD}; {QUOTED_CITE}")
    resolves = {"repo": "o/r", "ownerRulings": {U: doc_for(QUOTED)}}
    written = rr._follow_repeats([ruled, given], [], lambda: resolves)[1]
    assert written["reason"] == f"{QUOTED_CITE}; " + rr.REPEAT_FOLLOWS_RULING.format(name="f-1") + f"; earlier: {OLD}; {QUOTED_CITE}"
    again = the_finding(record({k: v for k, v in written.items() if k != "repeatOf"}, doc=doc_for(QUOTED)))
    assert again["reason"] == written["reason"]


def test_t20_a_merge_mark_whose_id_holds_a_part_separator_is_set_aside_whole():
    # Axis: the reason's trailing mark is set aside before the split, so an id with "; " never cuts the clause off.
    mark = rs.MERGED_INTO_FORMAT.format("a; b.py::odd name@L1")
    f = the_finding(record(stamped(reason="waits for the owner; " + A_L2 + mark)))
    assert f["outcome"] == "ruling" and f["reason"] == f"{CITE}; waits for the owner{mark}"
    assert rr._strip_stale(A_L2 + mark + rs.CARRIED) == ("", mark + rs.CARRIED)


def test_t21_a_promotion_is_not_mistaken_for_a_citation_followed_by_bracketed_prose():
    # Axis: only marks may follow a leading citation it skips; a bracketed note after it is prose, so the citation is
    # still written once in front.
    note = f"canon {STANDING} (considered and rejected)"
    left = {**X, "decidedBy": {"kind": "canon", "ref": STANDING}, "reason": note}
    f = the_finding(record(left, fake=Fake(sources=CANON_SOURCES)))
    assert f["outcome"] == "ruling" and f["reason"] == f"canon {STANDING}; {note}"
    marked = {**X, "decidedBy": {"kind": "canon", "ref": STANDING}, "reason": f"canon {STANDING}" + rs.CARRIED}
    assert the_finding(record(marked, fake=Fake(sources=CANON_SOURCES)))["reason"] == f"canon {STANDING}" + rs.CARRIED
