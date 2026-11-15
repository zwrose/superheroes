"""#2489 WO-1: the fix audit answers for every finding merged into the audited representative.

The invariant: a member answer is honored only as a well-formed `{id, fixed: bool, why}` row; anything else is either
refused at submit (shape) or read as "not fixed" by the judge; the representative's ruling is untouched by member answers.

E1 the judge: a member is fixed only on a `fixed: true` answer (edge 1) · E2 the shape judge: `fixed` is a boolean
(edge 4) · E3 the submit guard refuses each bad shape · E4 the ruling scrub covers `members[].why` (edge 10).
Edges 1-10 are the numbered tests below.

Bite-proof record: i2489_member_answers
"""
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import audits  # noqa: E402
import engine_adapter as EA  # noqa: E402
import engine_result_channel as ERC  # noqa: E402
import payload_contracts as PC  # noqa: E402
import round_driver as RD  # noqa: E402
import test_engine_result_channel as TERC  # noqa: E402

CHECKS = {name: {"answer": "yes", "why": "checked"} for name in audits.CHECK_NAMES}


def _members(*ids):
    return [{"id": mid, "title": "member %s" % mid, "file": "src/b.py", "line": 7} for mid in ids]


def _target(*ids, fid="t-1", kind=None):
    row = {"id": fid, "file": "src/a.py", "line": 2, "title": "Retry without a cap", "severity": "Important",
           "auditorVendor": "codex"}
    if ids:
        row["mergedMembers"] = _members(*ids)
    if kind is not None:
        row["kindOfMistake"] = kind
    return row


def _answer(mid, fixed=True, why="checked the member's own part"):
    return {"id": mid, "fixed": fixed, "why": why}


def _result(target, members=None, ruling="discharged", **extra):
    result = {"id": target["id"], "ruling": ruling, "reason": "the fix holds", "checks": CHECKS}
    if members is not None:
        result["members"] = members
    result.update(extra)
    return result


def _fold(target, result):
    return audits.apply_audit_results([target], [result], expected_auditors={target["id"]: "codex"},
                                      collection_manifest={target["id"]: "codex"})


def _unanswered(mid):
    return {"id": mid, "fixed": False, "why": None}


# ---- edge 1 --------------------------------------------------------------------------------------------------

def test_edge1_members_absent_or_null_is_no_shape_fault_and_every_member_reads_unanswered():
    # axis: a member counts fixed only when an answer says `fixed: true`, so an absent or null `members` leaves every member unfixed — see bite-proof record i2489_member_answers
    target = _target("m1", "m2")
    for result in (_result(target), dict(_result(target), members=None)):
        assert audits.member_answers_fault(result) is None
        judged = audits.judge_members(target, result)
        assert judged["rows"] == [_unanswered("m1"), _unanswered("m2")]
        assert judged["unfixed"] == [] and judged["unanswered"] == ["m1", "m2"] and judged["ignored"] == []
        entry = _fold(target, result)["audits"][0]
        assert entry["members"] == [_unanswered("m1"), _unanswered("m2")]
        assert entry["ruling"] == "discharged"  # the representative's ruling is its own


# ---- edges 2-5: the shape judge --------------------------------------------------------------------------------

def test_edge2_members_that_is_not_a_list_is_a_shape_fault():
    for bad in ("m1", {"id": "m1", "fixed": True, "why": "w"}, 3, True):
        fault = audits.member_answers_fault({"members": bad})
        assert fault == "`members` is %s, not a list of {id, fixed, why}" % type(bad).__name__, bad


def test_edge3_an_entry_that_is_not_an_object_or_has_no_usable_id_is_a_shape_fault_naming_the_entry():
    good = _answer("m1")
    for bad in ("m1", None, 4, ["m1"], {"fixed": True, "why": "w"}, {"id": "", "fixed": True, "why": "w"},
                {"id": "  ", "fixed": True, "why": "w"}, {"id": 7, "fixed": True, "why": "w"},
                {"id": None, "fixed": True, "why": "w"}):
        fault = audits.member_answers_fault({"members": [good, bad]})
        assert fault is not None and fault.startswith("`members[1]`"), bad
    assert audits.member_answers_fault({"members": [good]}) is None


def test_edge4_fixed_that_is_not_exactly_a_boolean_is_a_shape_fault():
    # axis: `fixed` must be exactly true or false — a string or a number is not an answer — see bite-proof record i2489_member_answers
    for bad in ("true", "false", "yes", 1, 0, None):
        fault = audits.member_answers_fault({"members": [{"id": "m1", "fixed": bad, "why": "w"}]})
        assert fault == "`members[0]` `fixed` is not true or false", bad
    row_without = {"id": "m1", "why": "w"}
    assert audits.member_answers_fault({"members": [row_without]}) == "`members[0]` `fixed` is not true or false"
    for ok in (True, False):
        assert audits.member_answers_fault({"members": [{"id": "m1", "fixed": ok, "why": "w"}]}) is None


def test_edge5_why_that_is_missing_not_a_string_or_blank_is_a_shape_fault():
    for bad in ("", "   ", "\n", None, 5, ["w"], {"w": 1}):
        fault = audits.member_answers_fault({"members": [{"id": "m1", "fixed": True, "why": bad}]})
        assert fault == "`members[0]` has no usable `why`", bad
    assert audits.member_answers_fault({"members": [{"id": "m1", "fixed": True}]}) == (
        "`members[0]` has no usable `why`")
    # the one grounds predicate: whatever it accepts the shape judge accepts
    for why in ("w", " w ", 5, "", "  "):
        expected = audits.has_usable_reason(why)
        assert (audits.member_answers_fault({"members": [{"id": "m1", "fixed": False, "why": why}]}) is None) is expected


# ---- edges 6-8: the judge ------------------------------------------------------------------------------------

def test_edge6_a_member_answered_twice_is_fixed_only_when_every_answer_says_so():
    target = _target("m1", "m2")
    for order, fixed in (([False, True], False), ([True, False], False), ([True, True], True)):
        members = [_answer("m1", order[0]), _answer("m1", order[1]), _answer("m2")]
        judged = audits.judge_members(target, _result(target, members))
        assert [(r["id"], r["fixed"]) for r in judged["rows"]] == [("m1", fixed), ("m2", True)], order
        assert judged["unfixed"] == ([] if fixed else ["m1"]), order
        assert judged["unanswered"] == [] and judged["ignored"] == [], order
        entry = _fold(target, _result(target, members))["audits"][0]
        assert [(r["id"], r["fixed"]) for r in entry["members"]] == [("m1", fixed), ("m2", True)], order


def test_edge7_an_answer_for_an_unlisted_id_is_ignored_noted_once_and_never_credited():
    target = _target("m1")
    members = [_answer("m1"), _answer("zz", True), _answer("zz", False), _answer("yy")]
    judged = audits.judge_members(target, _result(target, members))
    assert judged["rows"] == [_answer("m1")]
    assert judged["ignored"] == ["zz", "yy"] and judged["unfixed"] == [] and judged["unanswered"] == []
    entry = _fold(target, _result(target, members))["audits"][0]
    assert entry["membersIgnored"] == ["zz", "yy"] and [r["id"] for r in entry["members"]] == ["m1"]
    # an answer for an id the target does not list does not credit the listed member either
    only_other = audits.judge_members(target, _result(target, [_answer("zz")]))
    assert only_other["rows"] == [_unanswered("m1")] and only_other["ignored"] == ["zz"]
    # no ignored answer, no `membersIgnored` key
    assert "membersIgnored" not in _fold(target, _result(target, [_answer("m1")]))["audits"][0]


def test_edge8_a_target_naming_no_member_is_judged_as_before_and_its_entry_has_no_members_key():
    no_members = [
        _target(),
        dict(_target(), mergedMembers=[]),
        dict(_target(), mergedMembers="m1"),
        dict(_target(), mergedMembers={"id": "m1"}),
        dict(_target(), mergedMembers=[{"title": "no id"}, "m1", None, {"id": ""}]),
    ]
    for target in no_members:
        assert audits.judge_members(target, _result(target, [_answer("m1")])) is None, target
        out = _fold(target, _result(target, [_answer("m1")]))
        assert out["discharged"] == ["t-1"]
        assert "members" not in out["audits"][0] and "membersIgnored" not in out["audits"][0], target
    assert audits.judge_members(None, {}) is None and audits.judge_members({}, None) is None


# ---- edge 9 and the invariant -----------------------------------------------------------------------------------

def _kind(*lines):
    return {"kind": "unchecked retry", "places": [{"file": "src/a.py", "line": n} for n in lines]}


def test_edge9_member_rows_are_written_whatever_the_representative_ruling_and_never_change_it():
    # unfixed place → the existing arm refuses the clearing ruling; the member rows are still on the entry
    target = _target("m1", kind=_kind(3))
    out = _fold(target, _result(target, [_answer("m1")], places=[{"file": "src/a.py", "line": 3, "fixed": False}]))
    (entry,) = out["audits"]
    assert entry["ruling"] == "not-discharged" and out["placesUnfixed"] == ["t-1"]
    assert "left unfixed: src/a.py:3" in entry["reason"]
    assert entry["members"] == [_answer("m1")]

    # a failed check → the existing arm refuses; the member rows are still on the entry
    target = _target("m1", "m2")
    failed = dict(CHECKS, right={"answer": "no", "why": "the retry still has no cap"})
    out = _fold(target, _result(target, [_answer("m1"), _answer("m2", False)], checks=failed))
    (entry,) = out["audits"]
    assert entry["ruling"] == "not-discharged" and entry["reason"].startswith("audit check failed: right")
    assert entry["members"] == [_answer("m1"), _answer("m2", False)]

    # the invariant, both directions: a member answered not fixed does not change a discharge,
    # and members all fixed do not change a refusal
    target = _target("m1")
    out = _fold(target, _result(target, [_answer("m1", False)]))
    assert out["discharged"] == ["t-1"] and out["notDischarged"] == []
    assert out["audits"][0]["ruling"] == "discharged" and out["audits"][0]["members"] == [_answer("m1", False)]
    out = _fold(target, _result(target, [_answer("m1")], ruling="not-discharged"))
    assert out["discharged"] == [] and out["notDischarged"] == ["t-1"]
    assert out["audits"][0]["ruling"] == "not-discharged" and out["audits"][0]["members"] == [_answer("m1")]

    # the entry is the same as a run without members apart from the member keys
    plain = _fold(_target(), _result(_target()))["audits"][0]
    with_members = dict(_fold(target, _result(target, [_answer("m1", False)]))["audits"][0])
    del with_members["members"]
    assert with_members == plain


# ---- edge 10 ------------------------------------------------------------------------------------------------------

def test_edge10_a_credential_like_value_in_a_member_why_is_scrubbed_and_id_and_fixed_are_unchanged():
    # axis: `members[].why` is free text the auditor wrote, so it is scrubbed at the parse boundary like `newIssues` — see bite-proof record i2489_member_answers
    secret = "sk-" + "a" * 48
    ruling = {"id": "f1", "ruling": "discharged", "reason": "resolved in diff", "checks": CHECKS,
              "members": [{"id": "m1", "fixed": True, "why": "the log line printed token %s before" % secret},
                          {"id": "m2", "fixed": False, "why": "still open"}]}
    res = EA.parse_result("codex", "review", json.dumps(ruling))
    assert res["ok"] is True and res["resultKind"] == "ruling"
    members = res["ruling"]["members"]
    assert secret not in json.dumps(res)
    assert members[0]["id"] == "m1" and members[0]["fixed"] is True
    assert members[0]["why"] != ruling["members"][0]["why"] and "the log line printed token" in members[0]["why"]
    assert members[1] == {"id": "m2", "fixed": False, "why": "still open"}
    # the scrubbed result is still a well-formed answer
    assert audits.member_answers_fault(res["ruling"]) is None


# ---- the contract, the submit guard, the strict-mode schema ------------------------------------------------------

def test_the_payload_contract_accepts_a_well_formed_members_answer_and_refuses_a_non_list():
    contract, reason = PC.payload_contract(PC.P_AUDITS)
    assert reason is None and "members" in contract["optional"] and contract["types"]["members"] == "list"
    good = {"id": "f1", "ruling": "discharged", "reason": "ok", "checks": CHECKS,
            "members": [_answer("m1"), _answer("m2", False)]}
    assert PC.payload_fault(PC.P_AUDITS, good, "") is None
    # a JSON null is read by the contract exactly as it reads one for `places` (the sibling optional list)
    assert (PC.payload_fault(PC.P_AUDITS, dict(good, members=None), "") is None) == (
        PC.payload_fault(PC.P_AUDITS, dict(good, places=None), "") is None)
    assert PC.payload_fault(PC.P_AUDITS, dict(good, members="m1"), "") is not None


def test_the_submit_guard_refuses_each_bad_members_shape_and_accepts_a_good_or_absent_one():
    # axis: the submit guard refuses a malformed `members` answer through the judge the fold uses — see bite-proof record i2489_member_answers
    target = _target("m1")
    good = {"results": [_result(target, [_answer("m1")], ruling="not-discharged")]}
    assert RD.audit_results_fault(good, [target]) is None
    assert RD.audit_results_fault({"results": [_result(target, ruling="not-discharged")]}, [target]) is None
    entry = good["results"][0]
    for bad in ("m1", {"id": "m1"}, ["m1"], [None], [{"fixed": True, "why": "w"}],
                [{"id": "", "fixed": True, "why": "w"}], [{"id": "m1", "fixed": "true", "why": "w"}],
                [{"id": "m1", "fixed": 1, "why": "w"}], [{"id": "m1", "fixed": True}],
                [{"id": "m1", "fixed": True, "why": "  "}], [{"id": "m1", "fixed": True, "why": 3}]):
        fault = RD.audit_results_fault({"results": [dict(entry, members=bad)]}, [target])
        assert fault is not None and "members" in fault, bad
        assert fault.startswith("results[0]"), bad
    # an element-level fault names the entry, not only the field
    fault = RD.audit_results_fault({"results": [dict(entry, members=[_answer("m1"), {"id": "m1", "fixed": "x",
                                                                                     "why": "w"}])]}, [target])
    assert "`members[1]` `fixed` is not true or false" in fault


def test_the_strict_mode_schema_declares_members_and_passes_the_repos_own_validator():
    assert ("ruling", "members") in ERC._STRICT_MODE_REFINEMENTS
    for vendor in ("codex", "cursor", "claude"):
        schema = ERC.declared_schema(vendor, ERC.RUN_KIND_REVIEW)
        ERC.assert_strict_mode_valid(schema)
    schema = ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW, "ruling")
    ERC.assert_strict_mode_valid(schema)
    branch = TERC._valid_review_branch("ruling")
    assert branch["members"] is None  # an optional contract field rides null in the strict tree
    ok, reason = ERC.validate(schema, TERC._wrap_result(branch))
    assert ok, reason
    branch["members"] = [_answer("m1"), _answer("m2", False)]
    ok, reason = ERC.validate(schema, TERC._wrap_result(branch))
    assert ok, reason
    for bad in ([{"id": "m1", "fixed": "true", "why": "w"}], [{"id": "m1", "fixed": True}],
                [{"id": "m1", "fixed": True, "why": "w", "extra": 1}], "m1"):
        branch["members"] = bad
        ok, _reason = ERC.validate(schema, TERC._wrap_result(branch))
        assert not ok, bad
