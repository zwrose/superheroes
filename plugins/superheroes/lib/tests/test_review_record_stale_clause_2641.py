"""Issue 2641: a citation the record writer cannot find on record is a structured field, never text in the reason.

The writer sets `decisionNotOnRecord` (the failure text `finding_outcomes.on_record` returned) on a finding that ends
left-for-owner with a cited decision that does not resolve, and clears it when the decision resolves. The reason is
left as it was; `review_record.shown_reason` builds the owner's text from the reason and the field. No code reads a
clause back out of a reason; the one exception is the exact whole tail the old `settle` appended.
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
from test_review_record_session import HEAD, STANDING, Fake

FIELD = rr.NOT_ON_RECORD_FIELD
BY = {"kind": "owner-ruling", "ref": {"url": U, "words": W}}
CITE = f'owner ruling "{W}" ({U})'
CLAUSE_L2 = fo.UNRESOLVED_CLAUSE % L2
# The exact tails the old `settle` appended to a reason, written out as literals so a change to the live template or
# its list cannot pass unnoticed: each is "; the cited decision is not on record: " followed by one failure text.
OLD_SETTLE_TAILS = tuple("; the cited decision is not on record: " + t for t in (
    "the ruling's link is not a comment permalink", "the ruling's link is not in this repository",
    "the ruling names no link or words", "the ruling's comment could not be read",
    "the ruling's comment is not a chat-ruling record", "the ruling's comment does not hold the owner's words",
    "a Critical finding is never settled by a scope ruling or the advisor's bound",
    "the ruling's comment is neither a chat-ruling record nor a vet receipt",
    "the bound's words state no number of rounds", "the vet receipt is not on this pull request",
    "the vet receipt records no scope ruling for this finding with these words",
    "the vet receipt records no advisor's bound with these words", "the review's round count is unknown",
    "no decision was cited", "the cited decision kind is not recognised", "the cited decision names no reference",
    "no Canon text was available", "the cited Canon entry is not on record", "no residual text was available",
    "the cited residual is not recorded", "no sheet answers were available", "the sheet answer is not settled"))
TAIL = "; the cited decision is not on record: the ruling's link is not in this repository"  # as the old settle appended it
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
    assert c["outcome"] == "left-for-owner" and c["reason"] == OPEN and c[FIELD] == fo.WHY_NO_CANON_TEXT
    assert rr.shown_reason(c) == OPEN + "; " + rr._DEMOTED_CLAUSE % fo.WHY_NO_CANON_TEXT


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
    pytest.param("keep it; " + fo.UNRESOLVED_CLAUSE % L2 + "; and more", id="clause-shaped-owner-words"),
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
    # Axis: a phrase shaped like the old clause that is not the whole tail of the reason is prose, so promotion only prepends.
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


@pytest.mark.parametrize("outcome", [
    pytest.param("ruling", id="ruling-resolves-in-place"),
    pytest.param("left-for-owner", id="leftover-is-promoted"),
])
def test_n6_the_whole_tail_the_old_settle_wrote_is_dropped_by_exact_match(outcome):
    # Axis: the one text the writer still reads, the exact literal tail, is removed once and the rest stays byte for byte.
    f = the_finding(record({**X, "outcome": outcome, "decidedBy": copy.deepcopy(BY), "reason": f"{CITE}; {OPEN}" + TAIL}))
    assert f["outcome"] == "ruling" and f["reason"] == f"{CITE}; {OPEN}" and FIELD not in f
    f = the_finding(record({**X, "outcome": outcome, "decidedBy": copy.deepcopy(BY), "reason": f"{CITE}; {OPEN}" + TAIL + rs.CARRIED}))
    assert f["outcome"] == "ruling" and f["reason"] == f"{CITE}; {OPEN}" + rs.CARRIED


def test_n6_a_leftover_with_the_old_tail_is_promoted_with_the_citation_and_no_tail():
    # Axis: a left-for-owner reason the old `settle` wrote is read back as the open reason, behind the citation.
    f = the_finding(record(stamped(reason=OPEN + TAIL)))
    assert f["outcome"] == "ruling" and f["reason"] == f"{CITE}; {OPEN}"


@pytest.mark.parametrize("tail", OLD_SETTLE_TAILS, ids=[f"tail-{n}" for n in range(len(OLD_SETTLE_TAILS))])
def test_n6_every_literal_tail_is_dropped(tail):
    # Axis: each failure text the old `settle` wrote as a tail is an exact match, the one home being the tuple.
    f = the_finding(record(stamped(reason=OPEN + tail)))
    assert f["outcome"] == "ruling" and f["reason"] == f"{CITE}; {OPEN}"


def test_n6_the_tail_is_dropped_once_and_only_as_a_whole_literal():
    # Axis: `_drop_legacy_tail` uses endswith and slicing only; one tail, once, and anything else comes back as it was.
    second = OLD_SETTLE_TAILS[3]
    assert rr._drop_legacy_tail(OPEN + TAIL, CITE) == OPEN
    assert rr._drop_legacy_tail(OPEN + TAIL + rs.CARRIED, CITE) == OPEN + rs.CARRIED
    assert rr._drop_legacy_tail(OPEN + second + TAIL, CITE) == OPEN + second
    assert rr._drop_legacy_tail(OPEN + TAIL + rs.CARRIED + rs.CARRIED, CITE) == OPEN + TAIL + rs.CARRIED + rs.CARRIED
    assert rr._drop_legacy_tail(TAIL, CITE) == ""
    for same in (OPEN, "", OPEN + TAIL[:-1], OPEN + TAIL + " ", OPEN + TAIL.replace("; ", ";", 1), None, 3, ["a"]):
        assert rr._drop_legacy_tail(same, CITE) == same, same


def test_n6_a_reason_carrying_the_formatted_round_count_text_stays_byte_for_byte():
    # Axis: the accepted gap, the formatted round-count text is not one literal, so an old reason carrying it keeps it.
    old = OPEN + "; " + fo.UNRESOLVED_CLAUSE % (fo.WHY_FEWER_ROUNDS % (1, 2))
    f = the_finding(record(stamped(reason=old)))
    assert f["outcome"] == "ruling" and f["reason"] == f"{CITE}; {old}"
    ruled = the_finding(record({**X, "outcome": "ruling", "decidedBy": copy.deepcopy(BY), "reason": f"{CITE}; {old}"}))
    assert ruled["outcome"] == "ruling" and ruled["reason"] == f"{CITE}; {old}"


def test_n6_the_older_demotion_prefix_unmet_suffix_and_a_tail_before_a_merge_mark_stay_as_written():
    # Axis: texts no exact-tail match covers stay byte for byte, with the citation prepended where promotion applies.
    prefix = rr._DEMOTED_CLAUSE % L3 + "; the owner said so"
    f = the_finding(record(stamped(reason=prefix)))
    assert f["outcome"] == "ruling" and f["reason"] == f"{CITE}; {prefix}"
    suffix = OPEN + "; " + rr._UNMET_CLAUSE % ("owner ruling", L3)
    f = the_finding(record(stamped(reason=suffix)))
    assert f["outcome"] == "ruling" and f["reason"] == f"{CITE}; {suffix}"
    merged = OPEN + TAIL + rs.MERGED_INTO_FORMAT.format("rep-1")
    f = the_finding(record(stamped(reason=merged)))
    assert f["outcome"] == "ruling" and f["reason"] == f"{CITE}; {merged}" and rs.merged_into(f["reason"]) == "rep-1"
    held = the_finding(record({**X, "outcome": "ruling", "decidedBy": copy.deepcopy(BY), "reason": f"{CITE}; {merged}"}))
    assert held["outcome"] == "ruling" and held["reason"] == f"{CITE}; {merged}"


def _source_of(module):
    return ast.parse(Path(module.__file__).read_text(encoding="utf-8"))


def _loaded_name(node):
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
        return node.id
    if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
        return node.attr
    return None


def _defined_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
    return names


def test_n7_no_clause_template_is_read_as_anything_but_the_left_side_of_a_percent_format():
    # Axis: the no-reader census, a template is formatted to be shown and never searched, split or matched.
    templates = {"_DEMOTED_CLAUSE", "_UNMET_CLAUSE", "UNRESOLVED_CLAUSE"}
    seen = 0
    for module in (rr, fo):
        tree = _source_of(module)
        parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        for node in ast.walk(tree):
            if _loaded_name(node) in templates:
                seen += 1
                parent = parents[node]
                assert isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Mod) and parent.left is node, (
                    f"{module.__name__}:{node.lineno} reads {_loaded_name(node)} other than as a % format")
    assert seen >= 3


def test_n7_the_readers_of_a_reason_clause_are_gone():
    # Axis: the helpers that parsed a clause out of a reason, and the regex list they read, no longer exist anywhere.
    gone = {"_strip_stale", "_peel_marks", "_without_stale_clauses", "_with_earlier", "_leads_with", "UNRESOLVED_WHYS"}
    for module in (rr, fo, rs):
        assert gone & _defined_names(_source_of(module)) == set(), module.__name__
    assert "merge_mark_start" not in _defined_names(_source_of(rs)) and not hasattr(rs, "merge_mark_start")
    for name in gone:
        assert not hasattr(rr, name) and not hasattr(fo, name), name


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
    assert demoted[FIELD] == fo.WHY_FEWER_ROUNDS % (-1, 2)
    restored = build(demoted, 2)
    assert restored["outcome"] == "ruling" and FIELD not in restored
    assert restored["reason"] == f'advisor\'s bound "{words}" ({url}); the advisor bounded it'
    still = build(demoted, 1)
    assert still["outcome"] == "left-for-owner" and still[FIELD] == fo.WHY_FEWER_ROUNDS % (1, 2)


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


def test_n10_the_classifier_refuses_every_inline_text_shape():
    # Axis: a literal, an f-string and an inline percent format each read as a text with no home.
    for src in ('"some failure"', 'f"some {x}"', '"unregistered failure %s" % (value,)', '"a" + b', "WHY_X + 'y'"):
        assert _failure_kind(ast.parse(src, mode="eval").body) == "unhomed", src
    assert _failure_kind(ast.parse("WHY_FEWER_ROUNDS % (a, b)", mode="eval").body) == "formatted"


def test_n10_every_failure_text_has_one_home_and_the_legacy_tails_are_built_from_them():
    # Axis: every failure return is classified, none carries a text with no home, the list holds exactly the named
    # texts, and the legacy tails are exactly what the old `settle` appended for each.
    tails = _failure_returns()
    kinds = [_failure_kind(t) for t in tails]
    assert [ast.unparse(t) for t, k in zip(tails, kinds) if k == "unhomed"] == []
    named = {t.id for t, k in zip(tails, kinds) if k == "named"}
    formatted = {t.left.id for t, k in zip(tails, kinds) if k == "formatted"}
    assert formatted == {"WHY_FEWER_ROUNDS"}
    assert {getattr(fo, n) for n in named} == set(fo.UNRESOLVED_WHY_TEXTS) and len(fo.UNRESOLVED_WHY_TEXTS) == len(named)
    assert set(fo.LEGACY_UNRESOLVED_TAILS) == set(OLD_SETTLE_TAILS)


def test_n12_a_repeats_recorded_earlier_text_is_never_trimmed_on_a_later_write():
    # Axis: the exact-match removal reads only the old settle's own reason; a reason holding a repeat's `earlier:`
    # history keeps every word, carried or not, while a plain reason still loses the tail.
    cite = f'owner ruling "{W}" ({U})'
    history = f"{cite}; " + rr.REPEAT_FOLLOWS_RULING.format(name="f-1") + f"; earlier: {OLD}; {CLAUSE_L2}"
    for reason in (history, history + rs.CARRIED):
        assert rr._drop_legacy_tail(reason, cite) == reason
        ruled = {**X, "outcome": "ruling", "decidedBy": {"kind": "owner-ruling", "ref": {"url": U, "words": W}}, "reason": reason}
        assert the_finding(rr.build_record(account([], [ruled]), readers()))["reason"] == reason
    assert rr._drop_legacy_tail(f"{cite}; waits; {CLAUSE_L2}", cite) == f"{cite}; waits"


def test_n13_ordinary_prose_holding_the_earlier_separator_still_loses_the_old_tail():
    # Axis: only the history `_follow_repeats` writes, led by the citation, is kept whole; a reason whose own prose
    # holds "; earlier: " is the old settle's reason and loses its exact tail, carried or not.
    prose = "waits for the owner; earlier: the owner asked us to defer"
    f = the_finding(record(stamped(reason=prose + TAIL)))
    assert f["outcome"] == "ruling" and f["reason"] == f"{CITE}; {prose}"
    assert rr._drop_legacy_tail(prose + TAIL, CITE) == prose
    assert rr._drop_legacy_tail(prose + TAIL + rs.CARRIED, CITE) == prose + rs.CARRIED
    assert rr._drop_legacy_tail(f"{CITE}; {prose}" + TAIL, CITE) == f"{CITE}; {prose}"
    member = f"{CITE}; " + rr.REPEAT_MEMBER_FOLLOWS_RULING.format(name="r-1") + f"; earlier: {OPEN}" + TAIL
    assert rr._drop_legacy_tail(member, CITE) == member
    assert rr._drop_legacy_tail(member, "another citation") == f"{CITE}; " + rr.REPEAT_MEMBER_FOLLOWS_RULING.format(name="r-1") + f"; earlier: {OPEN}"


def test_n14_a_merge_opener_inside_the_citation_never_counts_as_the_reasons_mark():
    # Axis: the merge mark is read only from the rest after the citation, so quoted words that look like a mark
    # leave one citation, with or without the carried suffix.
    cite = 'owner ruling "keep the note (merged into the appendix)" (https://example.invalid/c)'
    for rest in (rs.MERGED_INTO_FORMAT.format("rep-1"), rs.MERGED_INTO_FORMAT.format("rep-1") + rs.CARRIED):
        assert rr._leads_with_citation(cite + rest, cite) is True
    assert rr._leads_with_citation(cite + " (merged into rep-1) tail", cite) is False
    assert rr._leads_with_citation(cite + rs.CARRIED + rs.MERGED_INTO_FORMAT.format("rep-1"), cite) is False
