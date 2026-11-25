"""Issue 2641: a citation the record writer cannot find on record is a structured field, never text in the reason.

The writer sets `decisionNotOnRecord` (the failure text `finding_outcomes.on_record` returned) on a finding that ends
left-for-owner with a cited decision that does not resolve, and clears it when the decision resolves. The reason is
left as it was; `review_record.shown_reason` builds the owner's text from the reason and the field. No code reads a
clause back out of a reason, and no writer appends one to it.
"""
import ast
import copy
from pathlib import Path

import pytest

import canon
import finding_outcomes as fo
import pr_sheet
import review_record as rr
import review_record_session as rs
from test_review_record_owner_ruling import ADVISOR, DOC, L2, L3, U, W, WORDS, X, account, readers, the_finding
from test_review_record_repeat_follows_2438 import LFO, OLD, kept, mark, repeat
from test_review_record_session import HEAD, STANDING, Fake, Session, _merged, extras

FIELD = rr.NOT_ON_RECORD_FIELD
BY = {"kind": "owner-ruling", "ref": {"url": U, "words": W}}
CITE = f'owner ruling "{W}" ({U})'
CLAUSE_L2 = "the cited decision is not on record: " + L2
RESOLVES = {"repo": "o/r", "ownerRulings": {U: DOC}}
MEMBER_RAW = "m::t@L1"
OPEN = "waits for the owner"


def stamped(**over):
    """The left-for-owner finding `settle` returns when no repository is named, with the citation kept."""
    got = fo.settle(X, ruling={"decidedBy": copy.deepcopy(BY)}, sources={}, open_reason=OPEN)
    return {**X, "outcome": got["outcome"], "reason": got["reason"], "decidedBy": got["decidedBy"], **over}


def record(finding, **kw):
    return rr.build_record(account([], [finding]), readers(**kw))


def doc_for(words):
    return dict(DOC, body=canon.ruling_record("2026-10-18", "12:00", words, "finding f-1"))


def test_n1_settle_writes_no_text_about_the_citation_and_the_resolving_record_reads_clean():
    # Axis: DoD 1, `settle` leaves the reason as the open reason; a resolving write promotes it with the citation once.
    got = fo.settle(X, ruling={"decidedBy": copy.deepcopy(BY)}, sources={}, open_reason=OPEN)
    assert got["reason"] == OPEN and got["decidedBy"] == BY and got["outcome"] == "left-for-owner"
    rec = record(stamped())
    f = the_finding(rec)
    assert f["outcome"] == "ruling" and f["reason"] == f'owner ruling "{W}" ({U}); waits for the owner' and FIELD not in f
    (decided,) = pr_sheet.build([rec], ADVISOR, WORDS)["prSheet"]["alreadyDecided"]
    assert decided["detail"] == f["reason"]


def test_n2_an_unreadable_comment_sets_the_field_and_leaves_the_reason_for_shown_reason_to_extend():
    # Axis: DoD 2, a citation that does not resolve is a field on the finding, never text appended to its reason.
    f = the_finding(record(stamped(), doc=None))
    assert f["outcome"] == "left-for-owner" and f["reason"] == OPEN and f[FIELD] == L3
    assert rr.shown_reason(f) == "waits for the owner; the owner ruling it cites is not on record (" + L3 + ")"
    canon_left = {**X, "decidedBy": {"kind": "canon", "ref": STANDING}}
    c = the_finding(record(canon_left, fake=Fake()))
    assert c["outcome"] == "left-for-owner" and c["reason"] == OPEN and c[FIELD] == "no Canon text was available"
    assert rr.shown_reason(c) == OPEN + "; " + rr._DEMOTED_CLAUSE % "no Canon text was available"


def test_n2_shown_reason_is_the_reason_unless_the_field_says_otherwise_and_never_raises():
    # Axis: `shown_reason` reads only a non-blank string field, builds each kind's clause, and tolerates any shape.
    assert rr.shown_reason({"reason": OPEN}) == OPEN
    for bad in (None, "", "  ", 3, ["x"], {"a": 1}, True):
        assert rr.shown_reason({"reason": OPEN, FIELD: bad, "decidedBy": copy.deepcopy(BY)}) == OPEN, bad
    for kind, label in ((fo.OWNER_RULING, "owner ruling"), (fo.SCOPE_RULING, "scope ruling"), (fo.ADVISOR_BOUND, "advisor's bound")):
        f = {"reason": OPEN, FIELD: L3, "decidedBy": {"kind": kind, "ref": {"url": U, "words": W}}}
        assert rr.shown_reason(f) == f"{OPEN}; the {label} it cites is not on record ({L3})"
    for by in ({"kind": "canon", "ref": STANDING}, {"kind": "residual", "ref": "r"}, {"kind": "nope"}, None, "x", 3):
        assert rr.shown_reason({"reason": OPEN, FIELD: L3, "decidedBy": by}) == f"{OPEN}; " + rr._DEMOTED_CLAUSE % L3, by
    for reason in ("", None, 3, ["a"]):
        assert rr.shown_reason({"reason": reason, FIELD: L3, "decidedBy": copy.deepcopy(BY)}) == (
            f"the owner ruling it cites is not on record ({L3})"), reason
    assert rr.shown_reason({FIELD: L3}) == rr._DEMOTED_CLAUSE % L3
    for odd in (None, "text", 3, [], {}):
        rr.shown_reason(odd)  # a non-finding never raises


def test_n2_the_sheet_lists_a_merge_listed_finding_with_the_text_shown_reason_builds():
    # Axis: the listed-for-merge detail reads `shown_reason`, so the owner sees the failure the field carries.
    minor = {**X, "severity": "Minor", "decidedBy": copy.deepcopy(BY)}
    rec = rr.build_record(account([], [minor]), {**readers(doc=None), "finding_risk": lambda *args: False})
    f = the_finding(rec)
    assert rr.listed_for_merge(f) and f["reason"] == OPEN and f[FIELD] == L3
    (listed,) = pr_sheet.build([rec], ADVISOR, WORDS)["prSheet"]["listed"]
    assert listed["detail"] == "Minor: " + rr.shown_reason(f) and L3 in listed["detail"]


def test_n3_a_demoted_ruling_keeps_its_reason_and_the_recovered_one_keeps_its_citation_once():
    # Axis: demotion then recovery; the reason is never edited either way and the field comes and goes.
    ruled = {**X, "outcome": "ruling", "decidedBy": copy.deepcopy(BY), "reason": f"{CITE}; the owner said so"}
    demoted = the_finding(record(ruled, doc=None))
    assert demoted["outcome"] == "left-for-owner" and demoted["reason"] == f"{CITE}; the owner said so" and demoted[FIELD] == L3
    restored = the_finding(record(demoted))
    assert restored["outcome"] == "ruling" and restored["reason"] == f"{CITE}; the owner said so" and FIELD not in restored


@pytest.mark.parametrize("words", [
    pytest.param("keep it; " + CLAUSE_L2 + "; and more", id="clause-shaped-owner-words"),
])
def test_n3_owner_words_that_look_like_a_clause_are_never_altered(words):
    # Axis: no code reads a clause out of a reason, so clause-shaped owner words survive demotion and recovery whole.
    cite = f'owner ruling "{words}" ({U})'
    by = {"kind": "owner-ruling", "ref": {"url": U, "words": words}}
    ruled = {**X, "outcome": "ruling", "decidedBy": by, "reason": f"{cite}; {OPEN}"}
    demoted = the_finding(record(ruled, doc=None))
    assert demoted["outcome"] == "left-for-owner" and demoted["reason"] == f"{cite}; {OPEN}" and demoted[FIELD] == L3
    restored = the_finding(record(demoted, doc=doc_for(words)))
    assert restored["outcome"] == "ruling" and restored["reason"] == f"{cite}; {OPEN}" and FIELD not in restored
    kept_ruling = the_finding(record(ruled, doc=doc_for(words)))
    assert kept_ruling["outcome"] == "ruling" and kept_ruling["reason"] == f"{cite}; {OPEN}"


def test_n3_a_clause_shaped_phrase_inside_a_leftover_reason_is_kept_whole_on_promotion():
    # Axis: a phrase shaped like a clause inside a reason is prose, so promotion only prepends the citation.
    reason = "keep it; " + CLAUSE_L2 + "; and more"
    f = the_finding(record({**X, "decidedBy": copy.deepcopy(BY), "reason": reason}))
    assert f["outcome"] == "ruling" and f["reason"] == f"{CITE}; {reason}"
    unresolved = the_finding(record({**X, "decidedBy": copy.deepcopy(BY), "reason": reason}, doc=None))
    assert unresolved["outcome"] == "left-for-owner" and unresolved["reason"] == reason and unresolved[FIELD] == L3


def test_n4_a_carried_field_goes_when_the_citation_now_resolves():
    # Axis: an account finding that carries the field with its citation is written ruling, without the field.
    carried = {**X, "decidedBy": copy.deepcopy(BY), FIELD: L3}
    f = the_finding(record(carried))
    assert f["outcome"] == "ruling" and f["reason"] == f"{CITE}; {OPEN}" and FIELD not in f
    still = the_finding(record(carried, doc=None))
    assert still["outcome"] == "left-for-owner" and still["reason"] == OPEN and still[FIELD] == L3
    # the re-check on its own, before `_drop_stale_open_marker` could drop the field from a ruling: it clears the field itself
    (rechecked,), _ = rr._recheck_decisions([copy.deepcopy(carried)], lambda: RESOLVES)
    assert rechecked["outcome"] == "ruling" and FIELD not in rechecked


def test_n5_the_field_is_written_only_on_a_left_for_owner_finding_with_a_citation_that_failed():
    # Axis: a fixed finding and a left-for-owner finding with no citation never leave the writer holding the field.
    fixed = {**X, "outcome": "fixed", "reason": "fixed in 1a2b3c4", FIELD: L3}
    assert FIELD not in the_finding(record(fixed))
    bare = {**X, FIELD: L3}
    got = the_finding(record(bare))
    assert FIELD not in got and got["outcome"] == "left-for-owner" and got["reason"] == OPEN
    ruled_bare = {**X, "outcome": "ruling", "reason": "the owner said so", FIELD: L3}
    assert FIELD not in the_finding(record(ruled_bare))
    cited_fixed = {**X, "outcome": "fixed", "reason": "fixed in 1a2b3c4", "decidedBy": copy.deepcopy(BY), FIELD: L3}
    assert FIELD not in the_finding(record(cited_fixed, doc=None))


@pytest.mark.parametrize("bad", [
    pytest.param("", id="empty"), pytest.param("  ", id="blank"), pytest.param(3, id="not-text"),
    pytest.param(None, id="null"), pytest.param(["x"], id="list"),
])
def test_n5_a_field_that_is_not_a_non_blank_string_refuses_the_account(bad):
    # Axis: the account validator holds the field to a non-blank string when it is present.
    with pytest.raises(rr.Refusal) as refused:
        record({**X, FIELD: bad})
    assert refused.value.reason == "review-account-invalid" and refused.value.detail == f"findings[0].{FIELD}"


def _source_of(module):
    return ast.parse(Path(module.__file__).read_text(encoding="utf-8"))


def _loaded_name(node):
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
        return node.id
    if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
        return node.attr
    return None


_TEMPLATES = {"_DEMOTED_CLAUSE", "_UNMET_CLAUSE"}


def _template_misreads(tree):
    """(count of template reads, the reads that are not a % format whose result is only built, never compared)."""
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    seen, bad = 0, []
    for node in ast.walk(tree):
        if _loaded_name(node) not in _TEMPLATES:
            continue
        seen += 1
        parent = parents.get(node)
        if not (isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Mod) and parent.left is node):
            bad.append((node.lineno, "not the left side of a % format"))
            continue
        # a formatted clause used as an operand of a comparison (==, in, startswith-free matching) is a reader
        if isinstance(parents.get(parent), ast.Compare):
            bad.append((node.lineno, "formatted clause feeds a comparison"))
    return seen, bad


def test_n7_no_clause_template_is_read_as_anything_but_the_left_side_of_a_percent_format():
    # Axis: the no-reader census, a template is formatted to be shown and never searched, split or matched.
    seen, bad = _template_misreads(_source_of(rr))
    assert bad == [], f"review_record reads a clause template other than to build shown text: {bad}"
    assert seen >= 3


@pytest.mark.parametrize("src", [
    pytest.param("if (_DEMOTED_CLAUSE % x) in reason:\n    pass\n", id="membership"),
    pytest.param("ok = reason == _UNMET_CLAUSE % (a, b)\n", id="equality"),
    pytest.param("parts = reason.split(_DEMOTED_CLAUSE)\n", id="bare-read"),
])
def test_n7_the_census_refuses_a_template_used_to_match(src):
    # Axis: the census bites on a formatted clause compared against text, and on any bare read of a template.
    seen, bad = _template_misreads(ast.parse(src))
    assert seen == 1 and len(bad) == 1, (src, bad)
    assert _template_misreads(ast.parse("shown = reason + '; ' + _DEMOTED_CLAUSE % why\n")) == (1, [])


def test_n8_a_two_round_bound_demotes_with_the_field_and_recovers_with_no_clause():
    # Axis: a real advisor-bound failure, formatted from a count the account accepts, is a field; the reason is untouched.
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
    assert demoted["outcome"] == "left-for-owner" and demoted["reason"] == "the advisor bounded it"
    assert demoted[FIELD] == "the review ran %d rounds, fewer than the bound's %d" % (-1, 2)
    restored = build(demoted, 2)
    assert restored["outcome"] == "ruling" and FIELD not in restored
    assert restored["reason"] == f'advisor\'s bound "{words}" ({url}); the advisor bounded it'
    still = build(demoted, 1)
    assert still["outcome"] == "left-for-owner" and still[FIELD] == "the review ran %d rounds, fewer than the bound's %d" % (1, 2)


def test_n9_a_repeat_and_its_member_write_their_earlier_text_byte_for_byte_with_no_field():
    # Axis: `_follow_repeats` restores the base `earlier:` text, so clause-shaped text and merge marks are kept whole.
    ruled = {**X, "outcome": "ruling", "reason": "the owner ruled", "decidedBy": copy.deepcopy(BY)}
    old = f"{OLD}; {CLAUSE_L2}"
    note = f"merged note; {CLAUSE_L2}" + rs.MERGED_INTO_FORMAT.format("f-2")
    given = repeat(repeatOf=mark(kept={**kept(), "members": [MEMBER_RAW]}), reason=old)
    member = {**X, "id": "f-3", "title": "Merged one", "line": 30, "findingKey": MEMBER_RAW, "outcome": LFO, "reason": note}
    out = rr._follow_repeats([ruled, given, member], [], lambda: RESOLVES)
    assert out[1]["outcome"] == out[2]["outcome"] == "ruling"
    assert out[1]["reason"] == f"{CITE}; " + rr.REPEAT_FOLLOWS_RULING.format(name="f-1") + f"; earlier: {old}"
    assert out[2]["reason"] == f"{CITE}; " + rr.REPEAT_MEMBER_FOLLOWS_RULING.format(name="f-2") + f"; earlier: {note}"
    assert FIELD not in out[1] and FIELD not in out[2]
    bare = repeat(reason=OLD)
    assert rr._follow_repeats([ruled, bare], [], lambda: RESOLVES)[1]["reason"] == (
        f"{CITE}; " + rr.REPEAT_FOLLOWS_RULING.format(name="f-1") + f"; earlier: {OLD}")
    empty = repeat(reason="")
    assert rr._follow_repeats([ruled, empty], [], lambda: RESOLVES)[1]["reason"] == (
        f"{CITE}; " + rr.REPEAT_FOLLOWS_RULING.format(name="f-1"))


def test_n11_the_field_never_outlives_a_left_for_owner_outcome():
    # Axis: `_drop_stale_open_marker` is the last chokepoint, so a finding whose outcome is not left-for-owner loses the field.
    left = {**X, "decidedBy": {"kind": "owner-ruling", "ref": {"url": U, "words": W}}, FIELD: L3}
    for outcome in ("fixed", "ruling"):
        (got,) = rr._drop_stale_open_marker([{**left, "outcome": outcome}])
        assert FIELD not in got and got["outcome"] == outcome, outcome
    (kept_field,) = rr._drop_stale_open_marker([copy.deepcopy(left)])
    assert kept_field == left
    # the record-level path: the carried re-check moves a demoted, field-carrying leftover to fixed
    fake = {**readers(doc=None, fake=Fake(head=HEAD)), "is_ancestor": lambda root, commit, to: True}
    check = {"key": rr._key(X), "settled": "fixed", "commit": "d" * 40, "checkedHead": HEAD, "evidence": "ran the test; it passes"}
    prior = {"findings": [dict(X, findingKey=rr._key(X))]}
    rec = rr.build_record({**account([], [{**X, "decidedBy": copy.deepcopy(BY)}]), "carriedChecks": [check]}, fake, prior=prior)
    f = the_finding(rec)
    assert f["outcome"] == "fixed" and FIELD not in f


def test_n14_a_merge_opener_inside_the_citation_never_counts_as_the_reasons_mark():
    # Axis: the merge mark is read only from the rest after the citation, so quoted words that look like a mark
    # leave one citation, with or without the carried suffix.
    cite = 'owner ruling "keep the note (merged into the appendix)" (https://example.invalid/c)'
    for rest in (rs.MERGED_INTO_FORMAT.format("rep-1"), rs.MERGED_INTO_FORMAT.format("rep-1") + rs.CARRIED):
        assert rr._leads_with_citation(cite + rest, cite) is True
    assert rr._leads_with_citation(cite + " (merged into rep-1) tail", cite) is False
    held = rs.MERGED_INTO_FORMAT.format("rep-1" + rs.CARRIED)
    for rest in (held, held + rs.CARRIED):
        assert rr._leads_with_citation(cite + rest, cite) is True
    assert rr._leads_with_citation(cite + rs.CARRIED + rs.MERGED_INTO_FORMAT.format("rep-1"), cite) is False


def test_recovered_carried_ruling_keeps_its_citation_once():
    # Axis: carrying a citation-only reason adds a marker and recovery preserves both once.
    citation = f'owner ruling "{W}" ({U})'
    ruled = {**X, "outcome": "ruling", "reason": citation,
             "decidedBy": {"kind": "owner-ruling", "ref": {"url": U, "words": W}}}
    demoted = the_finding(rr.build_record(account([], [ruled]), readers(doc=None)))
    assert demoted["outcome"] == "left-for-owner"
    later = account([], [])
    later["sessionId"] = "s-2"
    later["findings"] = rs._carried(later, [demoted])
    expected = citation + rs.CARRIED
    assert later["findings"][0]["reason"] == expected
    recovered = the_finding(rr.build_record(later, readers()))
    assert recovered["outcome"] == "ruling"
    assert recovered["reason"] == expected


def test_recovered_carried_ruling_kept_open_by_a_check_keeps_its_citation_once_and_the_check_note():
    # Axis: a citation-only ruling demoted, carried, kept open by a carried check (its note follows the carried
    # suffix after "; ") and then resolved again is a ruling with the citation once, the note kept and no field.
    citation = f'owner ruling "{W}" ({U})'
    ruled = {**X, "outcome": "ruling", "reason": citation, "decidedBy": copy.deepcopy(BY)}
    demoted = the_finding(rr.build_record(account([], [ruled]), readers(doc=None)))
    assert demoted["outcome"] == "left-for-owner" and demoted["reason"] == citation and demoted[FIELD] == L3
    later = account([], [])
    later["sessionId"] = "s-2"
    later["findings"] = rs._carried(later, [demoted])
    later["carriedChecks"] = [{"key": "f-1", "settled": "applies", "commit": None, "checkedHead": None,
                               "evidence": "still reads past the end"}]
    kept_open = the_finding(rr.build_record(later, readers(doc=None)))
    note = "a check on no named commit kept it for the owner: the check found it still applies: still reads past the end"
    assert kept_open["outcome"] == "left-for-owner" and kept_open[FIELD] == L3
    assert kept_open["reason"] == citation + rs.CARRIED + "; " + note
    recovered = the_finding(rr.build_record(account([], [kept_open]), readers()))
    assert recovered["outcome"] == "ruling" and FIELD not in recovered
    assert recovered["reason"] == citation + rs.CARRIED + "; " + note
    assert recovered["reason"].count(citation) == 1 and note in recovered["reason"]
    assert rr._leads_with_citation(citation + rs.CARRIED + "; note", citation) is True
    assert rr._leads_with_citation(citation + rs.CARRIED + "note", citation) is False


def test_the_sheet_lists_a_merge_listed_finding_with_an_empty_reason_by_the_failure_alone():
    # Axis: a listed finding whose reason is empty shows the clause alone, with no stray "; " before it.
    minor = {**X, "severity": "Minor", "reason": "", "decidedBy": copy.deepcopy(BY)}
    rec = rr.build_record(account([], [minor]), {**readers(doc=None), "finding_risk": lambda *args: False})
    f = the_finding(rec)
    assert rr.listed_for_merge(f) and f["reason"] == "" and f[FIELD] == L3
    (listed,) = pr_sheet.build([rec], ADVISOR, WORDS)["prSheet"]["listed"]
    assert listed["detail"] == "Minor: the owner ruling it cites is not on record (" + L3 + ")"
    assert "; " not in listed["detail"]


@pytest.mark.parametrize("blank", [pytest.param("   ", id="spaces"), pytest.param("\t\n", id="tab-newline")])
def test_a_whitespace_only_reason_shows_the_failure_alone_on_the_sheet(blank):
    # Axis: a reason of whitespace only counts as no reason, so the listed detail has no stray "; " before the clause.
    assert rr.shown_reason({"reason": blank, FIELD: L3, "decidedBy": copy.deepcopy(BY)}) == (
        f"the owner ruling it cites is not on record ({L3})")
    minor = {**X, "severity": "Minor", "reason": blank, "decidedBy": copy.deepcopy(BY)}
    rec = rr.build_record(account([], [minor]), {**readers(doc=None), "finding_risk": lambda *args: False})
    f = the_finding(rec)
    assert rr.listed_for_merge(f) and f["reason"] == blank and f[FIELD] == L3
    (listed,) = pr_sheet.build([rec], ADVISOR, WORDS)["prSheet"]["listed"]
    assert listed["detail"] == "Minor: the owner ruling it cites is not on record (" + L3 + ")"


def test_promotion_gives_a_merged_member_its_citation_once_and_keeps_its_merge_marker(tmp_path):
    # Axis: the record promotes a merged member with the citation once and keeps its merge marker.
    citation = {"kind": "owner-ruling", "ref": {"url": U, "words": W}}
    open_reason = "waits for the owner"
    settled = fo.settle(X, ruling={"decidedBy": citation}, sources={}, open_reason=open_reason)
    ledger = _merged({}, {
        "disposition": settled["outcome"],
        "settledReason": settled["reason"],
        "decidedBy": settled["decidedBy"],
    })
    session = Session(tmp_path, dispositionLedger=ledger)
    session.seat("code-reviewer")
    sources = readers()
    account_from_session = rs.account_from_session(session.save(), extras(repo="o/r"), sources)
    rec = rr.build_record(account_from_session, sources)
    member = next(finding for finding in rec["findings"] if finding["id"] == "m-1")
    merge_marker = rs.MERGED_INTO_FORMAT.format("rep-1")
    assert member["outcome"] == "ruling"
    assert member["reason"] == f'owner ruling "{W}" ({U}); {open_reason}{merge_marker}'


def test_recovered_ruling_preserves_the_existing_quote_once():
    # Axis: the writer preserves a clause-shaped quotation when a demoted ruling resolves again.
    words = f"keep it; the cited decision is not on record: {L2}; and more"
    citation = f'owner ruling "{words}" ({U})'
    open_reason = "waits for the owner"
    ruled = {
        **X,
        "outcome": "ruling",
        "decidedBy": {"kind": "owner-ruling", "ref": {"url": U, "words": words}},
        "reason": f"{citation}; {open_reason}",
    }
    demoted = the_finding(rr.build_record(account([], [ruled]), readers(doc=None)))
    assert demoted["outcome"] == "left-for-owner"
    doc = dict(DOC, body=canon.ruling_record("2026-10-18", "12:00", words, "finding f-1"))
    restored = the_finding(rr.build_record(account([], [demoted]), readers(doc=doc)))
    assert restored["outcome"] == "ruling"
    assert restored["reason"] == f"{citation}; {open_reason}"
