"""A verifier refutation that rests on a scope ruling is recorded as a ruling or left for the owner, never as shown wrong.

Invariant: a verifier wrong grade whose reason rests on a scope / out-of-scope ruling rather than on the code never yields
`shown-wrong` and never acts as a code refutation (outcome, repeat keep, fix-holds); it yields `ruling` only when the ruling
row cites a decision the record writer can re-check (`decidedBy`), carrying that `decidedBy`, and otherwise `left-for-owner`.
A wrong grade that rests on the code is unchanged everywhere.

Edges: E-a non-str text / empty or blank or non-str keys never raise · E-b a key named that is not a live ruling key is
decided by the phrase pattern alone · E-c a mark with no key, a key with no ruling, a ruling that is not out-of-scope or one
with no dict `decidedBy` is left for the owner · E-d a `restsOnRuling` that is not a dict is no mark · E-e a verdict other
than wrong never rests on a ruling.
"""
import os
import sys
from pathlib import Path

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import finding_outcomes as FO  # noqa: E402
import repeat_marks as RM  # noqa: E402
import review_record as rr  # noqa: E402
import review_record_session as RS  # noqa: E402
import round_driver as RD  # noqa: E402
import round_orders  # noqa: E402
import verification as V  # noqa: E402

from test_review_record_carried_recheck import FIX, X, X_KEY, account, entry, readers  # noqa: E402
from test_review_record_session import HEAD  # noqa: E402

PROOF = "plugins/superheroes/lib/tests/bite_proofs/wo1_scope_ruling_2478.md"
KEY = "rk:src/foo.py:12:unchecked-index"
OWNER = {"kind": "owner-ruling",
         "ref": {"url": "https://github.com/o/r/issues/1#issuecomment-5", "words": "that belongs to the follow-up"}}
ON_RULING = f"the standing ruling on {KEY} routes this to the follow-up, so it is not raised here"
ON_CODE = "the index is checked at foo.py:12, quoted: `if i < len(xs)`"


def ruling_row(**over):
    return {"findingKey": KEY, "ruling": "out-of-scope", "reason": "belongs to the follow-up", "seq": 1,
            "provenance": {"ruledBy": "the owner", "ruledAt": "2026-01-02"}, "decidedBy": OWNER, **over}


def refuted_row(grade):
    return {"findingKey": "fk-1", "id": "f-1", "title": "Unchecked index", "file": "a.py", "line": 3,
            "severity": "Important", "raisedSeq": 1, "dispositionSeq": 2, "disposition": "refuted",
            "dispositionRound": 1, "refutedReason": grade["reason"], "grade": grade}


def drop_grade(reason, keys=(KEY,)):
    """The grade `apply_verdicts` gives a REFUTED with this reason, through the real function."""
    staged = V.stage_ids([{"file": "a.py", "title": "Unchecked index", "severity": "Important"}])
    done = V.apply_verdicts(staged, [{"id": "v0", "verdict": "REFUTED", "reason": reason}], keys)
    (drop,) = done["drops"]
    return drop["grade"]


def decide(grade, rulings):
    row = refuted_row(grade)
    return RS._decide(row, {"fk-1": row}, rulings)


# ---- the detector ---------------------------------------------------------------------------------------------

def test_a1_a_text_naming_exactly_one_live_ruling_key_rests_on_that_ruling():
    # axis: ruling_rest key match (E1)
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1_scope_ruling_2478.md
    assert FO.ruling_rest(f"see {KEY} for why", [KEY]) == {"findingKey": KEY}
    assert FO.ruling_rest(f"see {KEY} for why", [KEY, "rk:other"]) == {"findingKey": KEY}
    assert FO.ruling_rest(f"see {KEY} and rk:other", [KEY, "rk:other"]) == {"findingKey": None}
    assert FO.ruling_rest("the index is checked at foo.py:12", [KEY]) is None


@pytest.mark.parametrize("text", [
    "the standing ruling covers this", "Standing Rulings cover this", "standing-ruling covers this",
    "this was ruled out of scope", "the owner ruled it out of scope", "they ruled this out of scope",
    "the out of scope ruling applies", "the out-of-scope rulings apply", "it sits on an out-of-scope row",
    "it matches the scope rows", "an OUT  OF  SCOPE   ruling"])
def test_a2_the_ruling_phrases_rest_on_a_ruling_with_no_key(text):
    # axis: ruling_rest phrase match (E2)
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1_scope_ruling_2478.md
    assert FO.ruling_rest(text) == {"findingKey": None}


@pytest.mark.parametrize("text", [
    "not in changed material; out of scope of this diff", "this is out of scope", "the change is not in changed material",
    "the index is checked at foo.py:12", "a ruling on tabs", "scoped rows"])
def test_a3_a_code_scope_refutation_is_not_a_ruling(text):
    assert FO.ruling_rest(text) is None


@pytest.mark.parametrize("text, keys", [
    (None, (KEY,)), (7, (KEY,)), ([], (KEY,)), (ON_CODE, None), (ON_CODE, 5), (ON_CODE, ["", "  ", None, 3, b"x"]),
    (f"has {KEY}", ["", "  ", None, 3]), (f"has {KEY}", "not a list")])
def test_a4_bad_text_and_bad_keys_never_raise_and_are_ignored(text, keys):
    assert FO.ruling_rest(text, keys) is None


def test_a5_a_key_that_is_not_a_live_ruling_key_leaves_the_phrase_to_decide():
    assert FO.ruling_rest(f"{KEY} alone", ["rk:another"]) is None
    assert FO.ruling_rest(f"{KEY} under the standing ruling", ["rk:another"]) == {"findingKey": None}


def test_a6_rests_on_ruling_reads_the_mark_or_the_old_phrase_and_only_on_a_wrong_grade():
    # axis: rests_on_ruling (marked grade, or an old row's reason) on a wrong grade only
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1_scope_ruling_2478.md
    marked = {"verdict": "wrong", "reason": ON_CODE, "restsOnRuling": {"findingKey": KEY}}
    assert FO.rests_on_ruling(marked) is True
    assert FO.rests_on_ruling({"verdict": "wrong", "reason": ON_RULING}) is True
    assert FO.rests_on_ruling({"verdict": "wrong", "reason": ON_CODE}, reason=ON_RULING) is True
    assert FO.rests_on_ruling({"verdict": "wrong", "reason": ON_CODE}) is False
    # a mark that is not a dict is no mark: the reason decides
    assert FO.rests_on_ruling({"verdict": "wrong", "reason": ON_CODE, "restsOnRuling": "yes"}) is False
    assert FO.rests_on_ruling({"verdict": "wrong", "reason": ON_RULING, "restsOnRuling": ["x"]}) is True
    for verdict in ("plausible", "confirmed", None):
        assert FO.rests_on_ruling(dict(marked, verdict=verdict)) is False
    for odd in (None, "wrong", 3, [], {}):
        assert FO.rests_on_ruling(odd, ON_RULING) is False


# ---- DoD-1: the drop is marked, and the record reads the ruling --------------------------------------------------

def test_b1_a_refuted_naming_a_standing_ruling_key_is_marked_and_the_record_reads_the_ruling_with_its_decision():
    # axis: apply_verdicts marks the drop (E3); _decide reads the followable ruling (E4); the account carries its decidedBy
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1_scope_ruling_2478.md
    grade = drop_grade(ON_RULING)
    assert grade == {"verdict": "wrong", "reason": ON_RULING, "restsOnRuling": {"findingKey": KEY}}
    outcome, reason, rep = decide(grade, {KEY: ruling_row()})
    assert outcome == "ruling" and outcome != "shown-wrong"
    assert reason == (f"refuted only on the out-of-scope ruling on {KEY} (belongs to the follow-up; ruled by the owner, "
                      f"2026-01-02); the verifier's reason: {ON_RULING}")
    state = {"dispositionLedger": [refuted_row(grade)], "findings": [], "rulingsLog": [ruling_row()]}
    (found,), _merged = RS._findings_and_merges(state)
    assert found["outcome"] == "ruling" and found["decidedBy"] == OWNER
    assert found["decidedBy"] is not OWNER  # copied, not shared
    assert rep["grade"] == grade


def test_b2_the_mark_on_a_drop_reaches_the_ledger_row_and_the_live_row_intact():
    grade = drop_grade(ON_RULING)
    state = {"dispositionLedger": [], "round": 1,
             "findings": [{"findingKey": "fk-1", "id": "f-1", "title": "Unchecked index", "file": "a.py", "line": 3}]}
    RD._record_grade(state, "fk-1", grade)
    assert state["findings"][0]["grade"] == grade
    assert state["dispositionLedger"][0]["grade"] == grade
    assert state["dispositionLedger"][0]["grade"] is not grade


def test_b3_the_fold_passes_the_keys_of_the_live_standing_rulings_as_the_orders_rendered_them():
    state = {"rulingsLog": [dict(ruling_row(), source="rule")], "dispositionLedger": [], "findings": []}
    rows, failure = RD._standing_rulings_for_orders(state)
    assert failure is None
    assert [r["findingKey"] for r in rows] == [KEY]


# ---- DoD-2: a ruling that cites no decision, or no key at all, is left for the owner ----------------------------

@pytest.mark.parametrize("grade_reason, rulings, why", [
    pytest.param(ON_RULING, {KEY: ruling_row(decidedBy=None)}, f"the ruling on {KEY} cites no decision",
                 id="provenance-but-no-decidedBy"),
    pytest.param(ON_RULING, {KEY: {k: v for k, v in ruling_row().items() if k != "decidedBy"}},
                 f"the ruling on {KEY} cites no decision", id="decidedBy-absent"),
    pytest.param(ON_RULING, {KEY: ruling_row(decidedBy="canon 3")}, f"the ruling on {KEY} cites no decision",
                 id="decidedBy-not-a-dict"),
    pytest.param(ON_RULING, {KEY: ruling_row(ruling="guidance")}, f"no out-of-scope ruling is on record for {KEY}",
                 id="not-out-of-scope"),
    pytest.param(ON_RULING, {}, f"no out-of-scope ruling is on record for {KEY}", id="no-such-ruling"),
    pytest.param(ON_RULING, "not a map", f"no out-of-scope ruling is on record for {KEY}", id="rulings-not-a-map"),
    pytest.param("the standing ruling routes this to the follow-up", {KEY: ruling_row()},
                 "the verifier named no ruling row", id="phrase-only-no-key"),
])
def test_c1_a_refutation_whose_ruling_cannot_be_followed_is_left_for_the_owner(grade_reason, rulings, why):
    # axis: _decide leaves a ruling-resting refutation for the owner unless the ruling cites a decision (E5)
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1_scope_ruling_2478.md
    grade = drop_grade(grade_reason)
    outcome, reason, _rep = decide(grade, rulings)
    assert outcome == "left-for-owner" and outcome != "shown-wrong"
    assert reason == (f"refuted only on a scope ruling whose source cannot be followed ({why}); "
                      f"the verifier's reason: {grade_reason}")


def test_c2_a_left_for_owner_refutation_carries_no_decision_and_a_non_dict_mark_falls_back_to_the_phrase():
    grade = drop_grade("the standing ruling routes this to the follow-up")
    state = {"dispositionLedger": [refuted_row(grade)], "findings": [], "rulingsLog": [ruling_row()]}
    (found,), _ = RS._findings_and_merges(state)
    assert found["outcome"] == "left-for-owner" and found["decidedBy"] is None
    odd = {"verdict": "wrong", "reason": ON_RULING, "restsOnRuling": "yes"}
    assert decide(odd, {KEY: ruling_row()})[0] == "left-for-owner"


# ---- DoD-3: a carried shown-wrong that rested on a ruling moves on a fixed check ------------------------------------

RULING_REASON = "refuted: the standing ruling puts it out of scope"
CODE_REASON = "the verifier showed the cited line does not exist"
W_RULING = dict(X, outcome="shown-wrong", reason=RULING_REASON, grade={"verdict": "wrong", "reason": RULING_REASON})
W_CODE = dict(X, outcome="shown-wrong", reason=CODE_REASON, grade={"verdict": "wrong", "reason": CODE_REASON})
SETTLED = "; the earlier shown-wrong rested on a scope ruling, not on the code, and the fixed check settles it"


def record(session, finding):
    return {"sessionId": session, "findings": [dict(finding, findingKey=rr._key(finding))]}


def build(finding, prior):
    return rr.build_record(account([entry()], [finding]), readers(), prior=prior)


@pytest.mark.parametrize("finding", [
    pytest.param(W_RULING, id="old-shape-phrase"),
    pytest.param(dict(W_RULING, grade={"verdict": "wrong", "reason": CODE_REASON, "restsOnRuling": {"findingKey": KEY}}),
                 id="marked-grade"),
])
def test_d1_a_shown_wrong_that_rested_on_a_ruling_moves_to_fixed_though_the_earlier_record_lists_it_shown_wrong(finding):
    # axis: _recheck_carried skips both unchanged guards for a ruling-resting shown-wrong (E6)
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1_scope_ruling_2478.md
    rec = build(finding, record("s-0", finding))
    (f,) = rec["findings"]
    assert f["outcome"] == "fixed"
    assert f["reason"] == (f"fixed after its review at {FIX[:7]}: ran the test; it passes "
                           f"(checked against the final commit {HEAD[:7]} when this record was written)"
                           f"{SETTLED}; earlier: {finding['reason']}")
    (row,) = rec["carriedRechecks"]
    assert (row["result"], row["why"]) == ("fixed", "fixed")


def test_d2_a_shown_wrong_that_rested_on_the_code_stays_unchanged_under_the_same_check():
    # axis: the bypass is only for a ruling-resting grade; a code refutation keeps today's guard and reason
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1_scope_ruling_2478.md
    rec = build(W_CODE, record("s-0", W_CODE))
    (f,) = rec["findings"]
    assert f["outcome"] == "shown-wrong" and f["reason"] == CODE_REASON
    (row,) = rec["carriedRechecks"]
    assert (row["result"], row["why"]) == ("unchanged", "shown wrong in the earlier record")


def test_d3_a_ruling_resting_shown_wrong_still_needs_the_fixed_check_to_hold():
    no_history = rr.build_record(account([entry()], [W_RULING]), readers(ancestor=False), prior=record("s-0", W_RULING))
    (f,) = no_history["findings"]
    assert f["outcome"] == "shown-wrong"
    (row,) = no_history["carriedRechecks"]
    assert row["result"] == "kept" and row["why"] == f"its fix commit {FIX[:7]} is not in the final commit's history"
    assert rr.build_record(account([entry()], [W_RULING]), readers(), prior=None)["findings"][0]["outcome"] == "shown-wrong"


# ---- repeat precedence ----------------------------------------------------------------------------------------------

def test_e1_a_repeat_whose_grade_rests_on_a_ruling_is_no_code_refutation_and_proves_no_fix():
    # axis: _grade_verdict reads a ruling-resting wrong grade as no verdict (E7)
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1_scope_ruling_2478.md
    on_ruling = {"grade": drop_grade(ON_RULING)}
    on_code = {"grade": drop_grade(ON_CODE)}
    assert "restsOnRuling" not in on_code["grade"]
    assert RD._grade_verdict(on_ruling) is None
    assert RD._grade_verdict(on_code) == "wrong"
    assert RD._grade_verdict({"grade": {"verdict": "plausible", "reason": "r"}}) == "plausible"
    assert RD._grade_verdict({}) is None and RD._grade_verdict(None) is None
    assert RM.decide(RM.FIXED, RD._grade_verdict(on_ruling), True) == (False, False)  # no fixHolds on a scope refutation
    assert RM.decide(RM.FIXED, RD._grade_verdict(on_code), True) == (True, True)  # healthy sibling, as today
    assert RM.decide(RM.SHOWN_WRONG, RD._grade_verdict(on_ruling), False) == (True, None)  # unchanged code keeps
    assert RM.decide(RM.SHOWN_WRONG, RD._grade_verdict(on_ruling), True) == (False, None)  # changed code: not a code refutation


def test_e2_an_earlier_shown_wrong_that_rests_on_a_ruling_reads_open_so_its_repeat_is_judged_fresh():
    # axis: decision_outcome reads a ruling-resting shown-wrong entry as open (E7)
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1_scope_ruling_2478.md
    marked = {"outcome": "shown-wrong", "grade": drop_grade(ON_RULING)}
    old_shape = {"outcome": "shown-wrong", "grade": {"verdict": "wrong", "reason": ON_RULING}}
    by_reason = {"outcome": "shown-wrong", "grade": {"verdict": "wrong", "reason": ON_CODE}, "reason": ON_RULING}
    for entry_ in (marked, old_shape, by_reason):
        assert RM.decision_outcome(entry_) is None
        assert RM.decide(RM.decision_outcome(entry_), "confirmed", False) == (False, None)
    code = {"outcome": "shown-wrong", "grade": drop_grade(ON_CODE)}
    assert RM.decision_outcome(code) == "shown-wrong"
    assert RM.decide(RM.decision_outcome(code), None, False) == (True, None)
    assert RM.decision_outcome({"outcome": "fixed", "grade": drop_grade(ON_RULING)}) == "fixed"
    assert RM.decision_outcome({"outcome": "shown-wrong"}) == "shown-wrong"
    assert RM.decision_outcome("not a dict") is None


def test_e3_a_record_finding_shown_wrong_on_a_ruling_pools_with_its_grade_and_reads_open():
    on_ruling = RM.record_entry(dict(X, findingKey="rr1:x", outcome="shown-wrong", reason=ON_RULING,
                                     grade={"verdict": "wrong", "reason": ON_RULING}))
    assert RM.decision_outcome(on_ruling) is None
    on_code = RM.record_entry(dict(X, findingKey="rr1:y", outcome="shown-wrong", reason=ON_CODE,
                                   grade={"verdict": "wrong", "reason": ON_CODE}))
    assert RM.decision_outcome(on_code) == "shown-wrong"
    assert "grade" not in RM.record_entry(dict(X, findingKey="rr1:z", outcome="craft", grade={"verdict": "wrong", "reason": "r"}))


# ---- healthy siblings of DoD-1 ----------------------------------------------------------------------------------------

def test_f1_a_refuted_on_the_code_is_unmarked_and_reads_shown_wrong_as_today():
    # axis: a code refutation is graded wrong with no mark and reads shown-wrong, with or without live ruling keys
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1_scope_ruling_2478.md
    for keys in ((KEY,), (), None):
        grade = drop_grade("handled at foo.py:12", keys)
        assert grade == {"verdict": "wrong", "reason": "handled at foo.py:12"}
        outcome, reason, _ = decide(grade, {KEY: ruling_row()})
        assert (outcome, reason) == ("shown-wrong", "handled at foo.py:12")
    state = {"dispositionLedger": [refuted_row({"verdict": "wrong", "reason": ON_CODE})], "findings": [],
             "rulingsLog": [ruling_row()]}
    (found,), _ = RS._findings_and_merges(state)
    assert found["outcome"] == "shown-wrong" and found["decidedBy"] is None


def test_f2_the_evidence_text_counts_and_a_code_scope_refutation_is_not_a_ruling():
    staged = V.stage_ids([{"file": "a.py", "title": "T", "severity": "Important"}])
    done = V.apply_verdicts(staged, [{"id": "v0", "verdict": "REFUTED", "reason": "unreachable", "evidence": ON_RULING}], [KEY])
    assert done["drops"][0]["grade"]["restsOnRuling"] == {"findingKey": KEY}
    grade = drop_grade("not in changed material; out of scope of this diff")
    assert "restsOnRuling" not in grade
    assert decide(grade, {})[0] == "shown-wrong"
    # no keys passed: a key in the text is only a phrase question
    assert drop_grade(f"see {KEY}", ())["reason"] == f"see {KEY}" and "restsOnRuling" not in drop_grade(f"see {KEY}", ())


# ---- order text -----------------------------------------------------------------------------------------------------------

SENTENCE = "A ruling below says only that the finding is out of scope; it is never evidence about the code"


def test_g1_the_standing_rulings_block_and_the_verifier_order_say_a_ruling_is_no_evidence_about_the_code():
    # axis: the verifier is told a ruling-resting REFUTED must name the ruling's key
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1_scope_ruling_2478.md
    block = round_orders.format_rulings_block({"standing_rulings": [{"findingKey": KEY, "reason": "later"}]})
    text = " ".join(block.split())
    assert SENTENCE in text
    assert "names that ruling's key (as listed) in its `reason`" in text
    assert f"- {KEY}: out of scope — later" in block
    empty = round_orders.format_rulings_block({"standing_rulings": []})
    assert "never evidence about the code" not in empty
    order = (Path(__file__).resolve().parents[2] / "rubric" / "orders" / "dispatch-verifiers.md").read_text(encoding="utf-8")
    flat = " ".join(order.split())
    assert "is never evidence about the code, so a REFUTED that rests on a ruling rather than on the code names that ruling's key" in flat
