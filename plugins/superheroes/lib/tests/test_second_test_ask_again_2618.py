"""#2618 — a second-test seat that answers none of its items is asked once more before its findings fold.

The invariant: in the driver's fold for the two logical second-test phases (`second-test`, the held findings, and
`second-test-correction`), an answer that names none of the items its order gave is, the FIRST time in a round for that
logical phase, not folded. The driver spends the round's one-shot latch for that phase (round state, so a resumed
session reads it spent), records `second-test-asked-again` / `break-it-correction-asked-again`, leaves the step and the
held findings / pending correction as they were, and the next order is the same order plus one line naming the ids
that were not answered. A SECOND silence in the same round for the same phase folds as the empty answer always did
(the silent row, now carrying `askedAgain: true`, and the silent decision), so the review always reaches a terminal.

Not re-asked: a partial answer; a held id answered twice; an order with no items. The latches are independent per
logical phase and per round. The verifiers' fold is not changed.

Groups: T1 silent then a good answer · T2 silent twice · T3 not silent · T4 resume · T5 silence forever ·
T6 independent latches · T7 the rendered order · T8 the new round, the transient and the shapes.

Bite-proof record: silent_seat_ask_again_2618
"""
import copy
import glob
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import decision_kinds  # noqa: E402
import round_orders as RO  # noqa: E402
import round_phases as RP  # noqa: E402
import test_round_driver as TRD  # noqa: E402
import test_round_orders as TRO  # noqa: E402
import test_second_test_c1l7 as C7  # noqa: E402
import test_silent_seat_fold_2617 as S17  # noqa: E402

RD = TRD.RD
C10B = S17.C10B
C1 = S17.C1

HELD = "second-test"
CORRECTION = "second-test-correction"
GUARD_REASON = "run_loop guard tripped — fail closed"


@pytest.fixture(autouse=True)
def _pinned_git_config(monkeypatch, tmp_path):
    for name in ("home", "xdg-config"):
        (tmp_path / name).mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


# ---- helpers ---------------------------------------------------------------------------------------------------

def _latch(state, rnd="1"):
    return state["rounds"].get(rnd, {}).get("askedAgain")


def _kinds(state, kind):
    return [d for d in state["decisions"] if d["kind"] == kind]


def _fold_held(state, findings):
    RD._fold(state, state["config"], RD.P_SECOND_TEST, {"findings": findings})
    return state


def _held_ids(state):
    return [row["finding"]["id"] for row in state["_secondTestHeld"]]


def _correction_world(tmp_path):
    return S17._correction_world(tmp_path)


def _no_block_for(key):
    return {"id": key, "suggestion": S17._NO_BLOCK}


def _assert_asked_again(state, phase, kind, count, ids, rnd="1"):
    """The state a first silent answer leaves: the latch spent, one decision, the transient naming the ids, the step kept."""
    assert _latch(state, rnd) == [phase]
    (decision,) = _kinds(state, kind)
    assert "%d item(s)" % count in decision["detail"] and "sent once more" in decision["detail"], decision
    assert state["_askAgainUnanswered"] == ids
    assert state["step"] == RD.P_SECOND_TEST
    assert "silentSeats" not in state["rounds"][rnd]


# ---- T1: silent, then a good answer ---------------------------------------------------------------------------------

def test_t1_held_a_silent_answer_is_asked_again_and_the_second_answer_is_used():
    state = S17._held_state(2)
    held_before = copy.deepcopy(state["_secondTestHeld"])
    _fold_held(state, [])
    _assert_asked_again(state, HELD, "second-test-asked-again", 2, ["v0", "v1"])
    # nothing of the fold happened: the held findings are as they were and nothing is recorded under `secondTest`
    assert state["_secondTestHeld"] == held_before
    assert "secondTest" not in state["rounds"]["1"]
    assert "_secondTestPass" not in state
    # the next order is the same order with the unanswered ids named
    again = RD._advance(state, state["config"])
    assert again["phase"] == RD.P_SECOND_TEST and again["payload"]["askedAgain"] == ["v0", "v1"]
    assert [f["id"] for f in again["payload"]["findings"]] == ["v0", "v1"]
    # axis: the payload `_advance` emits after a real silent fold is a declared shape, exactly one row (G5)
    assert RO.matching_order_shapes(RD.P_SECOND_TEST, again["payload"]) == ["second-test-asked-again"]
    # the second answer is the one the fold takes
    _fold_held(state, [S17._answer("v0"), S17._answer("v1")])
    assert "silentSeats" not in state["rounds"]["1"] and not _kinds(state, "second-test-silent")
    assert len(_kinds(state, "second-test-asked-again")) == 1
    assert [r["reason"] for r in state["rounds"]["1"]["secondTest"]["noTest"]] == ["no-block", "no-block"]
    assert state["step"] == RD.P_VERIFIERS
    assert "_askAgainUnanswered" not in state


def test_t1_held_hand_path_the_second_emission_names_the_ids_lands_and_folds(tmp_path):
    answers = []

    def results(payload):
        answers.append(payload)
        return [] if len(answers) == 1 else C7.Round._default_result(payload)

    r = C7.Round(tmp_path, second_result=results)
    first = r.to_second_test()
    assert "askedAgain" not in first["payload"]
    r.submit(first, r.second_result(first["payload"]))
    ids = [first["payload"]["findings"][0]["id"]]
    _assert_asked_again(r.state(), HELD, "second-test-asked-again", 1, ids)
    again = r.to_second_test()
    assert again["attempt"] == first["attempt"] + 1
    assert again["payload"]["findings"] == first["payload"]["findings"]
    assert again["payload"]["askedAgain"] == ids
    # the two orders on disk: only the second carries the added line, once
    orders = glob.glob(os.path.join(r.dir, "round-1", "orders", RD.P_SECOND_TEST, "*.md"))
    texts = [open(path, encoding="utf-8").read() for path in sorted(orders)]
    assert len(texts) == 2, orders
    assert "sent once more" not in texts[0]
    assert texts[1].count("sent once more") == 1 and again["payload"]["askedAgain"][0] in texts[1]
    r.submit(again, r.second_result(again["payload"]))
    state = r.state()
    assert "silentSeats" not in state["rounds"]["1"] and not _kinds(state, "second-test-silent")
    assert len(_kinds(state, "second-test-asked-again")) == 1
    assert state["rounds"]["1"]["secondTest"]["noTest"] == []
    assert [x["findingKey"] for x in state["rounds"]["1"]["secondTest"]["ran"]] == [C7._key()]
    assert state["_toVerify"][0]["suggestion"] == C7._SECOND  # the held finding took the new test
    assert state["step"] == RD.P_VERIFIERS and "_askAgainUnanswered" not in state


def test_t1_held_advance_path_the_second_emission_renders_lands_and_folds(tmp_path):
    answers = []

    def payload_for(items):
        answers.append(items)
        if len(answers) == 1:
            return []
        return [dict(S17._answer(f["id"], suggestion=C7._SECOND), title=f["title"], file=f["file"],
                     line=f["line"], severity=f["severity"], consequence=f["consequence"]) for f in items]

    state = S17._second_test_advance(tmp_path, payload_for, times=2)
    assert len(answers) == 2 and answers[0] == answers[1]
    assert "silentSeats" not in state["rounds"]["1"] and not _kinds(state, "second-test-silent")
    assert len(_kinds(state, "second-test-asked-again")) == 1
    assert state["rounds"]["1"]["secondTest"]["noTest"] == []
    assert len(state["rounds"]["1"]["secondTest"]["ran"]) == 1
    assert state["step"] != RD.P_SECOND_TEST and "_askAgainUnanswered" not in state


def test_t1_correction_a_silent_answer_is_asked_again_and_the_second_answer_is_used(tmp_path):
    w = _correction_world(tmp_path)
    pending_before = copy.deepcopy(w.state[RD.TEST_CORRECTION_PENDING_FIELD])
    w.fold(RD.P_SECOND_TEST, {"findings": []})
    _assert_asked_again(w.state, CORRECTION, "break-it-correction-asked-again", 1, [w.key], rnd="2")
    # the pending correction is exactly as it was and nothing of the correction is recorded
    assert w.state[RD.TEST_CORRECTION_PENDING_FIELD] == pending_before
    assert "testCorrection" not in w.state["rounds"]["2"]
    again = w.step()
    assert again["payload"]["correction"] is True and again["payload"]["askedAgain"] == [w.key]
    assert RO.matching_order_shapes(RD.P_SECOND_TEST, again["payload"]) == ["second-test-correction-asked-again"]
    w.fold(RD.P_SECOND_TEST, {"findings": [{"id": w.key, "suggestion": C1._block_text(C10B.CORRECTED_TEST)}]})
    assert "silentSeats" not in w.state["rounds"]["2"] and not _kinds(w.state, "break-it-correction-silent")
    assert len(_kinds(w.state, "break-it-correction-asked-again")) == 1
    assert w.state["rounds"]["2"]["testCorrection"] == [{"findingKey": w.key, "outcome": "corrected"}]
    assert w.state["step"] == RD.P_APPLY_FIXES  # the corrected test lands through the second restore-only step
    assert RD.TEST_CORRECTION_PENDING_FIELD not in w.state and "_askAgainUnanswered" not in w.state


def test_t1_correction_hand_path_the_second_emission_names_the_ids_and_folds(tmp_path):
    w = _correction_world(tmp_path)
    session = tmp_path / "cli-session"
    session.mkdir()
    (session / S17.RR.META_FILE).write_text(json.dumps({"repoRoot": str(w.root), "headSha": w.fix_head}))
    w.state["reviewedDiff"] = TRD.DIFF
    RD.save_state(str(session), w.state)
    n = RD.cmd_next(str(session))
    assert n["ok"] is True and n["payload"]["correction"] is True and "askedAgain" not in n["payload"], n
    vendor = RD._nonpanel_selection(w.state, str(session), RD.P_SECOND_TEST)[0]
    out = RD.cmd_submit(str(session), n["phase"], n["attempt"], n["expectedStateHash"],
                        {"findings": [], "reviewerVendor": vendor})
    assert out["ok"] is True, out
    again = RD.cmd_next(str(session))
    assert again["ok"] is True and again["phase"] == RD.P_SECOND_TEST, again
    assert again["payload"]["correction"] is True and again["payload"]["askedAgain"] == [w.key], again["payload"]
    answer = {"findings": [{"id": w.key, "suggestion": C1._block_text(C10B.CORRECTED_TEST)}],
              "reviewerVendor": vendor}
    out = RD.cmd_submit(str(session), again["phase"], again["attempt"], again["expectedStateHash"], answer)
    assert out["ok"] is True, out
    ok, state = RD.load_state(str(session))
    assert ok and "silentSeats" not in state["rounds"]["2"]
    assert state["rounds"]["2"]["testCorrection"] == [{"findingKey": w.key, "outcome": "corrected"}]
    assert len(_kinds(state, "break-it-correction-asked-again")) == 1 and "_askAgainUnanswered" not in state


# ---- T2: silent twice -----------------------------------------------------------------------------------------------

def test_t2_held_a_second_silence_folds_as_it_always_did_and_the_review_reaches_a_terminal(tmp_path):
    r = C7.Round(tmp_path, second_result=lambda payload: [])
    r.drive()
    state = r.state()
    assert state["terminal"], "the review did not reach a terminal"
    assert r.seen.count(RD.P_SECOND_TEST) == 2, r.seen
    assert state["rounds"]["1"]["silentSeats"] == [
        {"phase": HELD, "grain": "answer", "items": 1, "askedAgain": True}]
    assert len(_kinds(state, "second-test-asked-again")) == 1 and len(_kinds(state, "second-test-silent")) == 1
    assert state["rounds"]["1"]["secondTest"]["noTest"] == [{"findingKey": C7._key(), "reason": "no-result"}]
    degraded = RD.build_receipt(state)["degraded"]
    assert any(line.endswith("after the seat was asked once more") for line in degraded), degraded


def test_t2_held_direct_the_second_fold_equals_the_single_fold_of_a_silent_answer():
    state = _fold_held(_fold_held(S17._held_state(2), []), [])
    assert state["rounds"]["1"]["silentSeats"] == [{"phase": HELD, "grain": "answer", "items": 2, "askedAgain": True}]
    assert len(_kinds(state, "second-test-asked-again")) == 1 and len(_kinds(state, "second-test-silent")) == 1
    assert [r["reason"] for r in state["rounds"]["1"]["secondTest"]["noTest"]] == ["no-result", "no-result"]
    assert state["step"] == RD.P_VERIFIERS and state["_secondTestPass"] is True


def test_t2_correction_a_second_silence_folds_as_it_always_did(tmp_path):
    w = _correction_world(tmp_path)
    w.fold(RD.P_SECOND_TEST, {"findings": []})
    w.fold(RD.P_SECOND_TEST, {"findings": []})
    assert w.state["rounds"]["2"]["silentSeats"] == [
        {"phase": CORRECTION, "grain": "answer", "items": 1, "askedAgain": True}]
    assert len(_kinds(w.state, "break-it-correction-asked-again")) == 1
    assert len(_kinds(w.state, "break-it-correction-silent")) == 1
    assert w.state["rounds"]["2"]["testCorrection"] == [{"findingKey": w.key, "outcome": "none", "reason": "no-result"}]
    assert w.state["step"] == RD.P_VERIFY and RD.TEST_CORRECTION_PENDING_FIELD not in w.state


# ---- T3: not silent, so never asked again ---------------------------------------------------------------------------

def _assert_not_asked_again(state, rnd="1"):
    assert "askedAgain" not in state["rounds"][rnd]
    assert "_askAgainUnanswered" not in state
    assert not _kinds(state, "second-test-asked-again") and not _kinds(state, "break-it-correction-asked-again")


@pytest.mark.parametrize("count, answer", [
    pytest.param(2, lambda: [S17._answer("v0")], id="partial"),
    pytest.param(1, lambda: [S17._answer("v0"), S17._answer("v0")], id="a-held-id-answered-twice"),
    pytest.param(0, lambda: [], id="an-order-with-no-items"),
])
def test_t3_held_an_answer_that_is_not_silent_is_never_asked_again(count, answer):
    state = _fold_held(S17._held_state(count), answer())
    _assert_not_asked_again(state)
    assert state["step"] == RD.P_VERIFIERS


def test_t3_held_an_answer_naming_only_unknown_ids_is_asked_again():
    state = _fold_held(S17._held_state(1), [S17._answer("v99"), S17._answer("nope")])
    _assert_asked_again(state, HELD, "second-test-asked-again", 1, ["v0"])


def test_t3_correction_a_named_answer_is_never_asked_again(tmp_path):
    w = _correction_world(tmp_path)
    w.fold(RD.P_SECOND_TEST, {"findings": [_no_block_for(w.key)]})
    _assert_not_asked_again(w.state, "2")
    assert w.state["rounds"]["2"]["testCorrection"] == [{"findingKey": w.key, "outcome": "none", "reason": "no-block"}]


def test_t3_correction_an_order_with_no_items_is_never_asked_again(tmp_path):
    w = _correction_world(tmp_path)
    w.state[RD.TEST_CORRECTION_PENDING_FIELD]["items"] = []
    w.fold(RD.P_SECOND_TEST, {"findings": []})
    _assert_not_asked_again(w.state, "2")


# ---- T4: a resumed session never re-asks ----------------------------------------------------------------------------

def _reloaded(state):
    return json.loads(json.dumps(state))


def test_t4_held_a_resumed_session_reads_the_latch_spent():
    state = _fold_held(S17._held_state(1), [])
    resumed = _reloaded(state)
    assert _latch(resumed) == [HELD]
    _fold_held(resumed, [])
    assert resumed["rounds"]["1"]["silentSeats"] == [{"phase": HELD, "grain": "answer", "items": 1, "askedAgain": True}]
    assert len(_kinds(resumed, "second-test-asked-again")) == 1 and len(_kinds(resumed, "second-test-silent")) == 1
    assert resumed["step"] == RD.P_VERIFIERS


def test_t4_correction_a_resumed_session_reads_the_latch_spent(tmp_path):
    w = _correction_world(tmp_path)
    w.fold(RD.P_SECOND_TEST, {"findings": []})
    w.state = _reloaded(w.state)
    assert _latch(w.state, "2") == [CORRECTION]
    w.fold(RD.P_SECOND_TEST, {"findings": []})
    assert w.state["rounds"]["2"]["silentSeats"] == [
        {"phase": CORRECTION, "grain": "answer", "items": 1, "askedAgain": True}]
    assert len(_kinds(w.state, "break-it-correction-asked-again")) == 1
    assert w.state["step"] == RD.P_VERIFY


def test_t4_held_the_session_file_carries_the_latch_across_a_hand_resume(tmp_path):
    r = C7.Round(tmp_path, second_result=lambda payload: [])
    first = r.to_second_test()
    r.submit(first, [])
    ok, loaded = RD.load_state(r.dir)  # what a resumed session reads off disk
    assert ok and _latch(loaded) == [HELD] and loaded["_askAgainUnanswered"]
    again = r.to_second_test()
    r.submit(again, [])
    state = r.state()
    assert state["rounds"]["1"]["silentSeats"][0]["askedAgain"] is True
    assert r.drive()["action"] == RD.P_TERMINAL


# ---- T5: silence forever --------------------------------------------------------------------------------------------

def _count_loop_steps(monkeypatch):
    steps = []
    real = RD._advance

    def counting(state, config):
        steps.append(1)
        return real(state, config)
    monkeypatch.setattr(RD, "_advance", counting)
    return steps


def test_t5_held_a_seat_that_is_silent_forever_reaches_a_terminal_that_is_not_the_guard_trip(tmp_path, monkeypatch):
    steps, calls = _count_loop_steps(monkeypatch), []

    def answer(ctx):
        calls.append(ctx)
        return []

    state = S17._second_test_run_loop(tmp_path, answer)
    assert state["terminal"]
    assert (state.get("certification") or {}).get("reason") != GUARD_REASON, state.get("certification")
    assert len(steps) < RD._RUN_LOOP_GUARD, len(steps)
    assert len(calls) == 2, [sorted(c) for c in calls]
    assert "askedAgain" not in calls[0] and calls[1]["askedAgain"] == [f["id"] for f in calls[0]["findings"]]
    assert state["rounds"]["1"]["silentSeats"] == [{"phase": HELD, "grain": "answer", "items": 1, "askedAgain": True}]


def test_t5_correction_a_seat_that_is_silent_forever_reaches_a_terminal_that_is_not_the_guard_trip(
        tmp_path, monkeypatch):
    steps, calls = _count_loop_steps(monkeypatch), []
    w = C10B.World(tmp_path, cap=2)

    def fix_step(batch, rnd, payload):
        assert payload.get("restoreOnly"), "the run halts at the verify gate, before any settle fix"
        w.write(C10B.TEST_PATH, payload["restores"][0]["content"])
        C10B._commit(w.root, "restore")
        return {"fixes": []}

    def reviewer(dim, tier, rnd, ctx):
        if dim == "second-test":
            calls.append(ctx)
        return {"findings": [], "vendor": "codex"}

    seams = TRD._seams(auditor=lambda targets, rnd: w.audit_artifact()["results"], fix_step=fix_step,
                       reviewer=reviewer, verify_runner=lambda command, rnd: "pass")
    seams["panel_diff"] = lambda config, head: (TRD.DIFF, None)
    _receipt, state = w.run_loop(seams)
    assert state["terminal"]
    assert (state.get("certification") or {}).get("reason") != GUARD_REASON, state.get("certification")
    assert len(steps) < RD._RUN_LOOP_GUARD, len(steps)
    assert len(calls) == 2 and calls[1]["askedAgain"] == [w.key] and "askedAgain" not in calls[0]
    assert state["rounds"]["2"]["silentSeats"] == [{"phase": CORRECTION, "grain": "answer", "items": 1, "askedAgain": True}]


# ---- T6: the two logical phases have independent latches --------------------------------------------------------------

def test_t6_a_spent_correction_latch_never_spends_the_held_findings_latch_in_the_same_round(tmp_path):
    # the correction's latch is spent by the real folds of the correction seat's two silent answers; the held findings
    # are then staged as the hold leaves them (S17._held_state's rows) in the same round
    w = _correction_world(tmp_path)
    w.fold(RD.P_SECOND_TEST, {"findings": []})
    w.fold(RD.P_SECOND_TEST, {"findings": []})
    assert _latch(w.state, "2") == [CORRECTION]
    w.state["step"] = RD.P_SECOND_TEST
    w.state["_secondTestHeld"] = S17._held_state(1)["_secondTestHeld"]
    w.fold(RD.P_SECOND_TEST, {"findings": []})
    assert _latch(w.state, "2") == [CORRECTION, HELD]
    (decision,) = _kinds(w.state, "second-test-asked-again")
    assert "second-test seat answered none of its 1 item(s)" in decision["detail"], decision
    assert w.state["step"] == RD.P_SECOND_TEST and w.state["_askAgainUnanswered"] == ["v0"]
    assert [row["askedAgain"] for row in w.state["rounds"]["2"]["silentSeats"]] == [True]  # the correction's, only
    # and the held findings' own second silence folds
    w.fold(RD.P_SECOND_TEST, {"findings": []})
    assert [r.get("phase") for r in w.state["rounds"]["2"]["silentSeats"]] == [CORRECTION, HELD]
    assert w.state["step"] == RD.P_VERIFIERS


# ---- T7: the rendered order -------------------------------------------------------------------------------------------

_LINE = ("- This order is sent once more: your earlier answer named none of these items: %s. "
         "Return each of them, by its id.")


def _render(correction, channel, asked_again):
    ctx = TRO._GOLDEN_CONTEXTS[RP.P_SECOND_TEST]()
    placeholders = TRO._second_test_placeholders(channel)
    findings = [{"id": "v0"}, {"id": "v1"}]
    payload = {"findings": findings}
    if correction:
        placeholders["CORRECTION_INPUTS_PATH"] = placeholders.pop("HELD_FINDINGS_PATH")
        payload["correction"] = True
    if asked_again is not None:
        payload["askedAgain"] = list(asked_again)
    ctx.update(placeholders=placeholders, payload=payload)
    text, reason = RO.render_order(RP.P_SECOND_TEST, "golden-seat", ctx)
    assert reason is None, reason
    return text


@pytest.mark.parametrize("channel", ["file", "stdout"])
@pytest.mark.parametrize("correction", [False, True], ids=["held", "correction"])
def test_t7_a_re_sent_order_names_the_unanswered_ids_once_and_nothing_else_changes(correction, channel):
    plain = _render(correction, channel, None)
    again = _render(correction, channel, ["v0", "v1"])
    line = _LINE % "v0, v1"
    assert again.count(line) == 1
    assert again.count("v0, v1") == 1
    assert "sent once more" not in plain
    assert again.replace("\n" + line, "") == plain
    # an empty `askedAgain` is no re-send
    assert _render(correction, channel, []) == plain


def test_t7_the_held_form_file_render_without_askedAgain_is_the_golden():
    plain = _render(False, "file", None)
    assert plain == TRO._render_golden(RP.P_SECOND_TEST)
    golden_path = os.path.join(TRO._GOLDEN_DIR, RP.P_SECOND_TEST + ".txt")
    with open(golden_path, encoding="utf-8") as fh:
        assert TRO._normalize_golden_machine_paths(plain) == TRO._normalize_golden_machine_paths(fh.read())


# ---- T8: a new round, the transient, the decisions and the shapes -----------------------------------------------------------

def test_t8_a_new_round_has_a_fresh_latch():
    state = _fold_held(S17._held_state(1), [])
    assert _latch(state, "1") == [HELD]
    state["round"] = 2
    _fold_held(state, [])
    assert _latch(state, "1") == [HELD] and _latch(state, "2") == [HELD]
    assert len(_kinds(state, "second-test-asked-again")) == 2 and state["step"] == RD.P_SECOND_TEST


def test_t8_the_transient_is_gone_after_the_fold_even_when_the_re_asked_answer_is_good():
    state = _fold_held(S17._held_state(1), [])
    assert state["_askAgainUnanswered"] == ["v0"]
    _fold_held(state, [S17._answer("v0")])
    assert "_askAgainUnanswered" not in state


def test_t8_the_decision_kinds_are_registered():
    for kind in ("second-test-asked-again", "break-it-correction-asked-again"):
        assert kind in decision_kinds.DECISION_KINDS, kind


def test_t8_the_order_shapes_declare_the_re_sent_orders():
    # axis: every payload shape `_advance` can emit is declared; the base rows' empty answer is asked again and the re-sent rows' folds silent
    rows = {row["id"]: row for row in RO.ORDER_SHAPES}
    assert rows["second-test"]["emptyFoldDecision"] == "second-test-asked-again"
    assert rows["second-test-correction"]["emptyFoldDecision"] == "break-it-correction-asked-again"
    assert rows["second-test-asked-again"]["emptyFoldDecision"] == "second-test-silent"
    assert rows["second-test-correction-asked-again"]["emptyFoldDecision"] == "break-it-correction-silent"
    assert rows["second-test-asked-again"]["payloadKeys"] == frozenset({"findings", "askedAgain"})
    assert rows["second-test-correction-asked-again"]["payloadKeys"] == frozenset(
        {"correction", "findings", "askedAgain"})
