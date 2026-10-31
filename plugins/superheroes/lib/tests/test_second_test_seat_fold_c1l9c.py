"""A seat never carries `secondTest`, and an unauthenticated second-test seat keeps what the round had (C1-L9c, #2258, WO-C).

Two holes in the one-more-test step (C1-L7, `test_second_test_c1l7.py`):

V1 `secondTest` marks a finding that has had its one more test, and only the driver's second-test step (or its
unseatable path) sets it. A reviewer seat that sent `secondTest: true` on its own finding skipped the hold, so a
passing test that missed its path closed the finding as wrong on a REFUTED, against FR-16 and R7. Compile now
strips the field from every finding a seat returns.

V2 When the second-test seat's result fails vendor authentication, the park withholds certification; the terminal
receipt used to list neither the held findings nor the first pass's survivors, because the generic finder retain
is skipped for this step. They are kept now: the held findings marked unverified, the survivors as they stand.

Edges: E1 any seat-supplied value is stripped, a stamped finding's included · E2 the unseatable path still marks
its findings (`test_second_test_c1l7.py` group U) · E3 a missing, null or non-list staging keeps whatever is valid
and never raises · E4 a held row whose finding is not a dict is skipped · E5 gap-sweep and scoped-finder results
are still retained by the generic helper.
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import shlex  # noqa: E402

import test_round_driver as TRD  # noqa: E402
import test_second_test_c1l7 as C7  # noqa: E402
from session_checkout import enter_checkout  # noqa: E402

RD = TRD.RD
_HELD = C7._HELD
_PLAIN = C7._PLAIN


# ---- V1: a seat's own `secondTest` never survives compile ------------------------------------------------------

class _SeatStampedRound(C7.Round):
    """The test role stamps `secondTest: true` on the finding it raises, as a seat that sends the field would."""

    def respond(self, phase, payload, rnd):
        out = super().respond(phase, payload, rnd)
        if phase == RD.P_PANEL:
            for finding in out["seats"]["test-role"]["findings"]:
                finding[RD.SECOND_TEST_FIELD] = True
        return out


def test_v1_a_seat_supplied_second_test_does_not_skip_the_missed_path_step(tmp_path):
    # bites on: the `secondTest` strip in mechanical_compile (G1)
    # the verifier answers a `secondTest` finding from `second`: were the mark kept, it would be graded, not held
    r = _SeatStampedRound(tmp_path, second={_HELD["title"]: C7._MISSED})
    n = r.to_second_test()
    state = r.state()
    assert n["action"] == RD.P_SECOND_TEST and state["step"] == RD.P_SECOND_TEST
    (entry,) = n["payload"]["findings"]
    assert entry["title"] == _HELD["title"]
    # held, not graded or closed on the passing test
    row = r.row(state=state)
    assert "disposition" not in row and "grade" not in row
    # the field the seat sent is not on the finding the driver holds
    assert [RD.SECOND_TEST_FIELD in f for f in state["_toVerify"]] == [False]
    assert state["rounds"]["1"]["secondTest"]["held"] == [{"findingKey": C7._key(), "note": C7._NOTE}]


@pytest.mark.parametrize("value", [
    pytest.param(True, id="true"), pytest.param(False, id="false"), pytest.param("true", id="string"),
    pytest.param(1, id="int"), pytest.param(None, id="null"),
])
@pytest.mark.parametrize("stamped", [
    pytest.param(False, id="unstamped"), pytest.param(True, id="break-it-stamped"),
])
def test_v1_compile_output_carries_no_second_test_whatever_the_seat_sent(value, stamped):
    # bites on: the `secondTest` strip in mechanical_compile (G1); edge 1
    finding = dict(_PLAIN, **{RD.SECOND_TEST_FIELD: value})
    compiled, drops = RD.mechanical_compile([finding], None, stamped={id(finding)} if stamped else None)
    assert drops == [] and [f["title"] for f in compiled] == [_PLAIN["title"]]
    assert RD.SECOND_TEST_FIELD not in compiled[0]
    assert finding[RD.SECOND_TEST_FIELD] is value  # the seat's own dict is left as it was


def test_v1_the_unseatable_path_still_marks_the_findings_it_sends_to_pass_two():
    # edge 2: the driver's own mark is set after compile, so the strip never reaches it
    state = RD.new_state({"leg": "code", "vendors": ["claude", "codex"], "diff": "d", "fixerVendor": "codex",
                          "seatMap": {"hostFamily": "anthropic"}})
    state["round"] = 1
    RD._stage_second_pass(state, [dict(_HELD, **{RD.SECOND_TEST_FIELD: True})])
    assert [f.get(RD.SECOND_TEST_FIELD) for f in state["_toVerify"]] == [True]
    assert state["step"] == RD.P_VERIFIERS


# ---- V2: an unauthenticated second-test seat keeps what the round already had ----------------------------------

def _second_test_run(tmp_path, reported_vendor):
    """run_loop on a real checkout: the test role raises ``_HELD`` (its test passes on the unfixed code and the
    verifier says it missed the path), the code reviewer raises ``_PLAIN`` (kept, plausible), then the second-test
    seat answers as ``reported_vendor``."""
    checkout = os.path.join(str(tmp_path), "checkout")
    head = enter_checkout(checkout)
    calls = {"second": 0}

    def reviewer(dim, tier, rnd, ctx):
        if dim == "second-test":
            calls["second"] += 1
            return {"findings": [dict(e, suggestion=C7._SECOND) for e in ctx["findings"]], "vendor": reported_vendor}
        if rnd != 1:
            return []
        if dim == "test-role":
            return [dict(_HELD)]
        if dim == "code-reviewer":
            return [dict(_PLAIN)]
        return []

    def verifier(clusters, rnd):
        verdicts = []
        for cluster in clusters or []:
            for finding, fid in zip(cluster["findings"], cluster["ids"]):
                verdict = C7._MISSED if finding["title"] == _HELD["title"] else C7._PLAUSIBLE
                verdicts.append(dict(verdict, id=fid))
        return {"verdicts": verdicts, "vendor": "codex"}

    seams = TRD._seams(reviewer=reviewer, verifier=verifier, vendors=["claude", "codex"])
    cfg = TRD._cfg_cert(diff=C7._DIFF, repoRoot=checkout, headSha=head,
                        breakItInterpreter=shlex.quote(sys.executable))
    receipt, state = TRD._run_loop_capturing_state(seams, cfg)
    return receipt, state, calls["second"]


@pytest.mark.parametrize("reported", [
    pytest.param("claude", id="maker-vendor"), pytest.param("cursor", id="other-vendor"),
])
def test_v2_an_unauthenticated_second_test_result_keeps_the_held_finding_and_the_survivor(tmp_path, reported):
    # bites on: the second-test retain in run_loop's finder-authentication branch (G2)
    receipt, state, calls = _second_test_run(tmp_path, reported)
    assert calls == 1, calls
    assert state["terminal"] == "cannot-certify"
    reason = str(state["certification"]["reason"])
    assert reason.startswith("nonpanel-finder-unauthenticated:%s:" % RD.P_SECOND_TEST), reason
    assert reason.endswith(":reported=%s" % reported), reason
    rows = {f["title"]: f for f in receipt["findings"]}
    assert set(rows) == {_HELD["title"], _PLAIN["title"]}, receipt["findings"]
    assert rows[_HELD["title"]]["unverified"] is True
    assert rows[_PLAIN["title"]]["unverified"] is None and rows[_PLAIN["title"]]["verdict"] == "PLAUSIBLE"
    # the park withholds certification
    assert state["certification"].get("shape") is None, state["certification"]


# ---- E3, E4: the retain helper keeps what is valid and never raises ---------------------------------------------

def _staged_state(**fields):
    state = RD.new_state({"leg": "code", "vendors": ["claude", "codex"], "diff": "d", "fixerVendor": "codex"})
    state.update(fields)
    return state


@pytest.mark.parametrize("held, carried", [
    pytest.param(None, None, id="both-null"),
    pytest.param("rows", {"a": 1}, id="both-not-lists"),
    pytest.param([], [], id="both-empty"),
])
def test_e3_missing_null_or_non_list_staging_retains_nothing_and_never_raises(held, carried):
    state = _staged_state(_secondTestHeld=held, _secondTestCarry=carried)
    RD._retain_second_test_findings(state)
    assert state["findings"] == []


def test_e3_absent_staging_keys_never_raise():
    state = _staged_state()
    RD._retain_second_test_findings(state)
    assert state["findings"] == []


def test_e3_one_staging_list_missing_keeps_the_other():
    survivor = dict(_PLAIN, verdict="PLAUSIBLE")
    state = _staged_state(_secondTestHeld="not-a-list", _secondTestCarry=[survivor])
    RD._retain_second_test_findings(state)
    assert [f["title"] for f in state["findings"]] == [_PLAIN["title"]]
    held_only = _staged_state(_secondTestHeld=[{"finding": dict(_HELD), "note": "n"}])
    RD._retain_second_test_findings(held_only)
    assert [(f["title"], f["unverified"]) for f in held_only["findings"]] == [(_HELD["title"], True)]


def test_e4_a_held_row_whose_finding_is_not_a_dict_is_skipped():
    rows = [None, "row", {"note": "no finding"}, {"finding": "text", "note": "n"}, {"finding": None},
            {"finding": dict(_HELD), "note": "n"}]
    state = _staged_state(_secondTestHeld=rows, _secondTestCarry=[None, "x", dict(_PLAIN)])
    RD._retain_second_test_findings(state)
    assert {f["title"]: f.get("unverified") for f in state["findings"]} == {
        _HELD["title"]: True, _PLAIN["title"]: None}


def test_e3_the_helper_leaves_the_staging_and_the_held_finding_untouched():
    held = dict(_HELD)
    state = _staged_state(_secondTestHeld=[{"finding": held, "note": "n"}], _secondTestCarry=[])
    RD._retain_second_test_findings(state)
    assert "unverified" not in held and len(state["_secondTestHeld"]) == 1


# ---- E5: the generic retain is unchanged for gap-sweep and scoped-finder ----------------------------------------

def test_e5_the_generic_retain_still_keeps_an_unauthenticated_finders_candidates_unverified():
    state = _staged_state(findings=[dict(_PLAIN, verdict="CONFIRMED")])
    RD._retain_unauthenticated_finder_findings(state, {"findings": [dict(_HELD), "junk"]})
    assert [(f["title"], f.get("unverified")) for f in state["findings"]] == [
        (_PLAIN["title"], None), (_HELD["title"], True)]
