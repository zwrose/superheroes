"""Behaviour tests for finding_outcomes — the one home of the outcome rules."""
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.abspath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import canon  # noqa: E402
import engine_result_channel as ERC  # noqa: E402
import finding_outcomes as FO  # noqa: E402
import review_findings_schema as RFS  # noqa: E402
import round_driver  # noqa: E402
import session_contract  # noqa: E402
import verification  # noqa: E402

OPEN = "the loop ended with the finding open"
CANON_ID = "2026-01-02-abcd1234-1"
OTHER_ID = "2026-01-02-abcd1234-2"


def _entry(entry_id, supersedes=None, words='owner\'s words: "go"'):
    mid = (canon.SEP.join(["supersedes: " + supersedes, words]) if supersedes else words)
    return canon.entry_line(entry_id, "2026-01-02", "standing", "a ruling", mid, "issue thread")


def _sheet(answer, option_id=None):
    return {"answers": {"c1": {"answer": answer, "optionId": option_id, "note": ""}},
            "cards": {"c1": {"options": [{"id": option_id}] if answer == "option" and option_id else []}}}


# --- E1: a stated consequence ---------------------------------------------------------------

@pytest.mark.parametrize("finding", [
    {}, {"consequence": None}, {"consequence": ""}, {"consequence": "  \n\t "},
    {"consequence": 5}, {"consequence": ["x"]}, None, "text",
], ids=["missing", "none", "empty", "whitespace", "int", "list", "non-dict", "str-finding"])
def test_e1_unstated_consequence(finding):
    assert FO.has_stated_consequence(finding) is False


def test_e1_stated_consequence():
    assert FO.has_stated_consequence({"consequence": " users lose data "}) is True


# --- E2: an unknown kind is never craft -----------------------------------------------------

@pytest.mark.parametrize("kind", [None, "bogus", "Code-Quality", 5, ["code-quality"]],
                         ids=["none", "unknown", "case", "int", "list"])
def test_e2_kind_not_code_quality_goes_to_owner(kind):
    finding = {"consequence": "tidy", "consequenceKind": kind}
    assert FO.settle(finding, open_reason=OPEN)["outcome"] == RFS.LEFT_FOR_OWNER
    finding.pop("consequenceKind")
    assert FO.settle(finding, open_reason=OPEN)["outcome"] == RFS.LEFT_FOR_OWNER


# --- E3: merge --------------------------------------------------------------------------------

@pytest.mark.parametrize("kinds,expected", [
    (["code-quality", "real"], "real"),
    (["real", "code-quality"], "real"),
    (["code-quality", None], None),
    ([None, "code-quality"], None),
    (["code-quality", "code-quality"], "code-quality"),
    (["real", "real"], "real"),
    (["code-quality", "bogus"], None),
    ([], None),
], ids=["cq-real", "real-cq", "cq-none", "none-cq", "cq-cq", "real-real", "cq-bogus", "empty"])
def test_e3_merged_kind(kinds, expected):
    members = [{"consequence": "c%d" % i, "consequenceKind": k} for i, k in enumerate(kinds)]
    assert FO.merged_consequence(members)[1] == expected


def test_e3_merged_text_distinct_stripped_in_order():
    members = [
        {"consequence": "  first "}, {"consequence": ""}, {"consequence": None},
        {"consequence": "second"}, {"consequence": "first"}, {"consequence": 3},
    ]
    assert FO.merged_consequence(members) == ("first\n\nsecond", None)
    assert FO.merged_consequence([{}, {"consequence": " "}]) == (None, None)


def test_e3_verification_merge_group_keeps_real_from_lower_severity_member():
    high = {"id": "a", "file": "f.py", "line": 1, "title": "t", "severity": "Critical",
            "consequence": "style only", "consequenceKind": "code-quality"}
    low = {"id": "b", "file": "f.py", "line": 1, "title": "t", "severity": "Nit",
           "consequence": "data is lost", "consequenceKind": "real"}
    for members in ([high, low], [low, high]):
        merged = verification._merge_group(members)
        assert merged["severity"] == "Critical"
        assert merged["consequenceKind"] == "real"
        assert merged["consequence"] == "\n\n".join(
            m["consequence"] for m in members)
    grouping = [{"group_id": "g", "member_ids": ["a", "b"], "rationale": "same root cause"}]
    for members in ([high, low], [low, high]):
        out = verification.merge_and_rank([dict(m) for m in members], grouping)
        assert [f["consequenceKind"] for f in out["findings"]] == ["real"]


def test_e3_verification_merge_group_sets_none_even_when_rep_has_a_value():
    rep = {"id": "a", "severity": "Critical", "consequence": "style", "consequenceKind": "code-quality"}
    other = {"id": "b", "severity": "Nit"}
    merged = verification._merge_group([rep, other])
    assert merged["consequenceKind"] is None
    assert merged["consequence"] == "style"
    merged = verification._merge_group([{"id": "a", "severity": "Nit"}, {"id": "b", "severity": "Nit"}])
    assert merged["consequence"] is None and merged["consequenceKind"] is None


def test_e3_round_driver_merge_same_finding_keeps_real_from_lower_severity_member():
    high = {"file": "f.py", "line": 1, "title": "t", "severity": "Critical",
            "consequence": "style only", "consequenceKind": "code-quality"}
    low = {"file": "f.py", "line": 1, "title": "t", "severity": "Nit",
           "consequence": "data is lost", "consequenceKind": "real"}
    for existing, incoming in ((high, low), (low, high)):
        merged = round_driver._merge_same_finding(existing, incoming)
        assert merged["severity"] == "Critical"
        assert merged["consequenceKind"] == "real"
        assert merged["consequence"] == "\n\n".join(
            m["consequence"] for m in (existing, incoming))
    merged = round_driver._merge_same_finding({"severity": "Nit"}, {"severity": "Nit"})
    assert merged["consequence"] is None and merged["consequenceKind"] is None


# --- E4: Canon --------------------------------------------------------------------------------

def test_e4_canon_complete_entry_decides():
    text = canon.HEADER + _entry(CANON_ID) + "\n"
    assert FO.canon_decides(text, CANON_ID) is True
    assert FO.canon_decides(text, OTHER_ID) is False


@pytest.mark.parametrize("build", [
    pytest.param(lambda: _entry(CANON_ID).rsplit(canon.SEP, 1)[0], id="incomplete-line"),
    pytest.param(lambda: _entry(CANON_ID) + "\n" + _entry(OTHER_ID, supersedes=CANON_ID),
                 id="superseded"),
    pytest.param(lambda: _entry(OTHER_ID, words='owner\'s words: "see %s"' % CANON_ID),
                 id="id-only-inside-other-entry"),
    pytest.param(lambda: "- **%s**" % CANON_ID, id="bare-id"),
    pytest.param(lambda: "", id="empty-text"),
])
def test_e4_canon_does_not_decide(build):
    assert FO.canon_decides(build(), CANON_ID) is False


def _conflicting_canon():
    first = _entry(CANON_ID)
    second = _entry(CANON_ID, words='owner\'s words: "no, stop"')
    assert first != second and canon._entry_shape_ok(first) and canon._entry_shape_ok(second)
    return canon.HEADER + first + "\n" + second + "\n"


def test_e4_two_different_entries_sharing_an_id_decide_nothing():
    # axis: the distinct-entry count in canon_decides; an id held by two different complete entries
    # resolving as on record, when it must resolve for no reader
    text = _conflicting_canon()
    assert FO.canon_decides(text, CANON_ID) is False
    assert FO.on_record({"kind": "canon", "ref": CANON_ID}, {"canonText": text}) == (
        False, "the cited Canon entry is not on record")


def test_e4_the_same_entry_twice_is_one_distinct_entry_and_still_decides():
    # axis: the distinct-entry count in canon_decides; a byte-for-byte duplicate refused as a conflict
    line = _entry(CANON_ID)
    text = canon.HEADER + line + "\n" + line + "\n"
    assert FO.canon_decides(text, CANON_ID) is True
    assert FO.on_record({"kind": "canon", "ref": CANON_ID}, {"canonText": text}) == (
        True, "canon %s" % CANON_ID)


def test_e4_canon_incomplete_superseding_line_does_not_supersede():
    broken = _entry(OTHER_ID, supersedes=CANON_ID).rsplit(canon.SEP, 1)[0]
    assert FO.canon_decides(_entry(CANON_ID) + "\n" + broken, CANON_ID) is True


@pytest.mark.parametrize("text,entry_id", [
    (None, CANON_ID), (5, CANON_ID), ("x", None), ("x", ""), (_entry(CANON_ID), 7),
])
def test_e4_canon_bad_inputs(text, entry_id):
    assert FO.canon_decides(text, entry_id) is False


# --- residual ---------------------------------------------------------------------------------

@pytest.mark.parametrize("text,ref,expected", [
    ("a  known\n  gap  here", "known gap", True),
    ("a known gap", "  known   gap ", True),
    ("a known gap", "unknown gap", False),
    ("a known gap", "   ", False),
    ("a known gap", "", False),
    ("a known gap", None, False),
    (None, "known", False),
    ("a known gap", {"x": 1}, False),
])
def test_residual_decides(text, ref, expected):
    assert FO.residual_decides(text, ref) is expected


# --- E5: sheet answers ------------------------------------------------------------------------

@pytest.mark.parametrize("answers,ref,pr,expected", [
    (_sheet("aligned"), {"pr": 9, "card": "c1"}, 9, True),
    (_sheet("option", "opt-a"), {"pr": 9, "card": "c1"}, 9, True),
    (_sheet("aligned"), {"pr": 8, "card": "c1"}, 9, False),
    (_sheet("aligned"), {"pr": True, "card": "c1"}, 1, False),
    (_sheet("aligned"), {"pr": 1, "card": "c1"}, True, False),
    (_sheet("discuss"), {"pr": 9, "card": "c1"}, 9, False),
    (_sheet("something-else"), {"pr": 9, "card": "c1"}, 9, False),
    (_sheet(None), {"pr": 9, "card": "c1"}, 9, False),
    (_sheet("accept"), {"pr": 9, "card": "c1"}, 9, False),  # not in the sheet's answer vocabulary
    (_sheet("option"), {"pr": 9, "card": "c1"}, 9, False),
    (_sheet("option", ""), {"pr": 9, "card": "c1"}, 9, False),
    (_sheet("option", 4), {"pr": 9, "card": "c1"}, 9, False),
    (_sheet("aligned"), {"pr": 9, "card": "missing"}, 9, False),
    (_sheet("aligned"), {"pr": 9}, 9, False),
    ({"answers": {"c1": "aligned"}}, {"pr": 9, "card": "c1"}, 9, False),
    ({"answers": []}, {"pr": 9, "card": "c1"}, 9, False),
    ({}, {"pr": 9, "card": "c1"}, 9, False),
    (None, {"pr": 9, "card": "c1"}, 9, False),
    (_sheet("aligned"), "c1", 9, False),
    (_sheet("aligned"), None, 9, False),
    (_sheet("aligned", "stale-option"), {"pr": 9, "card": "c1"}, 9, False),  # the sheet schema: aligned names no option
], ids=lambda v: None)
def test_e5_sheet_answer_decides(answers, ref, pr, expected):
    assert FO.sheet_answer_decides(answers, ref, pr) is expected


def test_aligned_counts_only_while_the_published_card_offers_no_options():
    ref = {"pr": 9, "card": "c1"}
    base = _sheet("aligned")
    assert FO.sheet_answer_decides(base, ref, 9) is True
    # bites on: a saved aligned answer accepted for a card that has since gained options, or for one nothing can check
    assert FO.sheet_answer_decides(dict(base, cards={"c1": {"options": ["allow-late-returns"]}}), ref, 9) is False
    assert FO.sheet_answer_decides({"answers": base["answers"]}, ref, 9) is False
    assert FO.sheet_answer_decides(dict(base, cards={"c1": "x"}), ref, 9) is False
    assert FO.sheet_answer_decides(dict(base, cards={}), ref, 9) is False


# --- E6: on_record ----------------------------------------------------------------------------

def _sources(**extra):
    base = {"canonText": _entry(CANON_ID), "residualText": "a known gap",
            "residualSource": "base", "sheetAnswers": _sheet("aligned"), "pr": 9}
    base.update(extra)
    return base


def test_e6_on_record_resolves_each_kind():
    assert FO.on_record({"kind": "canon", "ref": CANON_ID}, _sources()) == (True, "canon " + CANON_ID)
    assert FO.on_record({"kind": "residual", "ref": "known gap"}, _sources()) == (
        True, "residual known gap (read from base)")
    assert FO.on_record({"kind": "residual", "ref": "known gap"},
                        _sources(residualSource="calibration store")) == (
        True, "residual known gap (read from calibration store)")
    no_source = _sources()
    del no_source["residualSource"]
    assert FO.on_record({"kind": "residual", "ref": "known gap"}, no_source) == (
        True, "residual known gap")
    ok, text = FO.on_record({"kind": "sheet-answer", "ref": {"pr": 9, "card": "c1"}}, _sources())
    assert ok is True and text.startswith("sheet-answer ")


@pytest.mark.parametrize("decided_by,sources", [
    ({"kind": "memo", "ref": "x"}, _sources()),
    ({"ref": CANON_ID}, _sources()),
    ({"kind": "canon"}, _sources()),
    ({"kind": "canon", "ref": ""}, _sources()),
    ({"kind": "canon", "ref": CANON_ID}, {}),
    ({"kind": "canon", "ref": CANON_ID}, {"canonText": None}),
    ({"kind": "canon", "ref": OTHER_ID}, _sources()),
    ({"kind": "residual", "ref": "known gap"}, {}),
    ({"kind": "residual", "ref": "other gap"}, _sources()),
    ({"kind": "sheet-answer", "ref": {"pr": 9, "card": "c1"}}, {}),
    ({"kind": "sheet-answer", "ref": {"pr": 9, "card": "c1"}}, _sources(pr=None)),
    ({"kind": "sheet-answer", "ref": {"pr": 9, "card": "c1"}}, _sources(sheetAnswers=_sheet("discuss"))),
    ({"kind": "sheet-answer"}, _sources()),
    ({"kind": ["canon"], "ref": CANON_ID}, _sources()),
    (None, _sources()),
    ("canon", _sources()),
    ({"kind": "canon", "ref": CANON_ID}, None),
    ({"kind": "canon", "ref": {"nested": 1}}, _sources()),
])
def test_e6_on_record_fails_closed_never_raises(decided_by, sources):
    ok, why = FO.on_record(decided_by, sources)
    assert ok is False
    assert isinstance(why, str) and why


def test_e6_residual_source_never_changes_the_decision():
    for source in ("base", "calibration store", None, 3):
        assert FO.on_record({"kind": "residual", "ref": "nope"}, _sources(residualSource=source))[0] is False
        assert FO.on_record({"kind": "residual", "ref": "known gap"}, _sources(residualSource=source))[0] is True


# --- E7 / E8: settle --------------------------------------------------------------------------

def test_settle_craft_for_code_quality_only():
    finding = {"consequence": "  harder to read ", "consequenceKind": "code-quality"}
    assert FO.settle(finding, open_reason=OPEN) == {
        "outcome": "craft", "reason": "code quality only: harder to read", "decidedBy": None}
    bare = FO.settle({"consequenceKind": "code-quality"}, open_reason=OPEN)
    assert bare["outcome"] == "craft"
    assert bare["reason"] == "code quality only: no further consequence stated"


def test_settle_real_without_ruling_is_left_for_owner():
    out = FO.settle({"consequence": "data lost", "consequenceKind": "real"}, open_reason=OPEN)
    assert out == {"outcome": "left-for-owner", "reason": OPEN, "decidedBy": None}


def test_settle_real_with_resolving_ruling():
    decided_by = {"kind": "canon", "ref": CANON_ID}
    out = FO.settle({"consequence": "data lost", "consequenceKind": "real"},
                    ruling={"decidedBy": decided_by}, sources=_sources(), open_reason=OPEN)
    assert out == {"outcome": "ruling", "reason": "decided by canon " + CANON_ID,
                   "decidedBy": decided_by}


def test_e7_unresolved_decided_by_stays_with_owner_with_reason_appended():
    finding = {"consequence": "data lost", "consequenceKind": "real"}
    out = FO.settle(finding, ruling={"decidedBy": {"kind": "canon", "ref": OTHER_ID}},
                    sources=_sources(), open_reason=OPEN)
    assert out["outcome"] == "left-for-owner"
    assert out["reason"] == OPEN + "; the cited decision is not on record: the cited Canon entry is not on record"
    assert out["decidedBy"] == {"kind": "canon", "ref": OTHER_ID}  # the citation stays, for the writer's write-time re-check
    out = FO.settle(finding, ruling={"decidedBy": {"kind": "canon", "ref": CANON_ID}}, open_reason=OPEN)
    assert out["outcome"] == "left-for-owner" and out["decidedBy"] == {"kind": "canon", "ref": CANON_ID}
    assert out["reason"].endswith("no Canon text was available")
    assert FO.settle(finding, ruling={"note": "no decidedBy"}, open_reason=OPEN)["reason"] == OPEN


def test_e7_craft_wins_over_a_resolving_ruling():
    out = FO.settle({"consequence": "naming", "consequenceKind": "code-quality"},
                    ruling={"decidedBy": {"kind": "canon", "ref": CANON_ID}},
                    sources=_sources(), open_reason=OPEN)
    assert out["outcome"] == "craft"
    assert out["decidedBy"] is None


@pytest.mark.parametrize("kind", ["code-quality", "real", None])
def test_e8_severity_never_changes_the_settlement(kind):
    results = []
    for severity in ("Nit", "Minor", "Important", "Critical", None, "bogus"):
        finding = {"consequence": "c", "consequenceKind": kind, "severity": severity}
        results.append(FO.settle(finding, open_reason=OPEN))
    assert all(r == results[0] for r in results)


def test_settle_outcomes_are_spelled_by_the_schema_module():
    assert FO.settle({"consequenceKind": "code-quality"}, open_reason=OPEN)["outcome"] == RFS.OUTCOMES[2]
    assert FO.settle({}, open_reason=OPEN)["outcome"] == RFS.OUTCOMES[3]
    assert FO.settle({"consequenceKind": "real"}, ruling={"decidedBy": {"kind": "canon", "ref": CANON_ID}},
                     sources=_sources(), open_reason=OPEN)["outcome"] == RFS.OUTCOMES[4]


# --- schema, constants and contract ------------------------------------------------------------

def _shipped_schema():
    with open(RFS.review_findings_schema_path(), encoding="utf-8") as fh:
        return json.load(fh)


def test_schema_has_consequence_kind_member_shaped_like_confidence():
    items = _shipped_schema()["properties"]["findings"]["items"]
    assert "consequenceKind" in items["properties"]
    assert "consequenceKind" in items["required"]
    assert items["required"].index("consequenceKind") == items["required"].index("consequence") + 1
    keys = list(items["properties"])
    assert keys.index("consequenceKind") == keys.index("consequence") + 1
    member = items["properties"]["consequenceKind"]
    assert member["type"] == ["string", "null"]
    assert member["enum"] == ["code-quality", "real", None]
    assert set(member) == set(items["properties"]["confidence"])
    ERC.assert_strict_mode_valid(_shipped_schema())


def test_schema_fallback_literals_match_shipped_schema():
    items = _shipped_schema()["properties"]["findings"]["items"]
    assert RFS._FALLBACK_CANONICAL_MEMBER_KEYS == tuple(items["properties"])
    fallback = RFS._FALLBACK_FINDING_PROPERTY_SCHEMAS["consequenceKind"]
    shipped = items["properties"]["consequenceKind"]
    assert fallback == {"type": shipped["type"], "enum": shipped["enum"]}
    assert RFS.CONSEQUENCE_KIND_KEY == "consequenceKind"
    assert RFS.CONSEQUENCE_KINDS == ("code-quality", "real")
    assert (RFS.CODE_QUALITY, RFS.REAL) == RFS.CONSEQUENCE_KINDS


def test_outcome_sheet_part_has_exactly_the_outcomes():
    assert set(RFS.OUTCOME_SHEET_PART) == set(RFS.OUTCOMES)
    assert RFS.OUTCOME_SHEET_PART == {
        "fixed": "how-the-review-went",
        "shown-wrong": "how-the-review-went",
        "craft": "decided-as-craft",
        "left-for-owner": "what-youre-accepting",
        "ruling": "already-decided",
    }


def test_session_contract_dispositions_end_with_the_settled_outcomes():
    assert session_contract.DISPOSITIONS[:3] == ("fixed", "refuted", "out-of-scope")
    assert session_contract.DISPOSITIONS[3:] == ("craft", "left-for-owner", "ruling")
    assert session_contract.DISPOSITIONS[3:] == RFS.OUTCOMES[2:]
    assert session_contract.DISPOSITION_FAMILY_FIELDS[-2:] == ("settledReason", "decidedBy")


# --- the compile step refuses a finding that states no consequence -----------------------------

NO_CONSEQUENCE = "no stated consequence"
UNCITED = "uncited — no file:line"
COMPILE_DIFF = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
                "@@ -1 +1,2 @@\n-old\n+new\n+more\n")


def _raised(**extra):
    base = {"file": "f.py", "line": 1, "title": "t", "severity": "Important"}
    base.update(extra)
    return base


# axis: refusal at the compile step (the finding is absent from `compiled`, its drop row is present)
@pytest.mark.parametrize("extra", [
    {}, {"consequence": None}, {"consequence": ""}, {"consequence": "  \n\t "},
    {"consequence": 5}, {"consequence": ["x"]},
], ids=["missing", "none", "empty", "whitespace", "int", "list"])
def test_compile_drops_a_finding_that_states_no_consequence(extra):
    finding = _raised(**extra)
    compiled, drops = round_driver.mechanical_compile([finding], COMPILE_DIFF)
    assert compiled == []
    assert drops == [{"file": "f.py", "line": 1, "title": "t", "reason": NO_CONSEQUENCE}]
    assert round_driver.COMPILE_DROP_NO_CONSEQUENCE == NO_CONSEQUENCE
    stated, no_drops = round_driver.mechanical_compile(
        [_raised(consequence="users lose data")], COMPILE_DIFF)
    assert no_drops == []
    assert [f["consequence"] for f in stated] == ["users lose data"]


def test_compile_uncited_finding_with_no_consequence_drops_once_as_uncited():
    for finding in ({"title": "t", "severity": "Important"},
                    {"file": "f.py", "title": "t", "severity": "Important", "consequence": ""},
                    {"line": 1, "title": "t", "severity": "Important", "consequence": None}):
        compiled, drops = round_driver.mechanical_compile([finding], COMPILE_DIFF)
        assert compiled == []
        assert [d["reason"] for d in drops] == [UNCITED]


def test_compile_break_it_exempt_finding_with_no_consequence_is_dropped():
    # g.py:9 is outside COMPILE_DIFF, so only the exemption keeps it in scope
    for extra in ({}, {"consequence": None}, {"consequence": ""}, {"consequence": " \n"}):
        finding = _raised(file="g.py", line=9, **extra)
        compiled, drops = round_driver.mechanical_compile(
            [finding], COMPILE_DIFF, scope_exempt={id(finding)})
        assert compiled == []
        assert drops == [{"file": "g.py", "line": 9, "title": "t", "reason": NO_CONSEQUENCE}]
    stated = _raised(file="g.py", line=9, consequence="users lose data")
    compiled, drops = round_driver.mechanical_compile(
        [stated], COMPILE_DIFF, scope_exempt={id(stated)})
    assert drops == []
    assert [(f["file"], f["line"]) for f in compiled] == [("g.py", 9)]


def test_an_option_answer_counts_only_while_the_published_card_still_offers_that_option():
    ref = {"pr": 9, "card": "c1"}
    base = _sheet("option", "opt-a")
    # bites on: a saved option accepted after the card was republished without it, or for a card nothing can check
    assert FO.sheet_answer_decides(dict(base, cards={"c1": {"options": [{"id": "opt-b"}]}}), ref, 9) is False
    assert FO.sheet_answer_decides(dict(base, cards={"c1": {"options": []}}), ref, 9) is False
    assert FO.sheet_answer_decides({"answers": base["answers"]}, ref, 9) is False
