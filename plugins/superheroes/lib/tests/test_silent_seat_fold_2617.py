"""#2617 — a seat that answers none of its items is recorded as silent at the fold.

The invariant: a verifier, second-test or second-test-correction answer that REACHES the driver's fold for an order
that named at least one item, and that names none of those items (an empty list, or only ids the order did not give),
is recorded as silent — one row on the round channel `silentSeats` plus one decision line — whichever entry path
delivered it (the run loop, hand `submit`, or `advance`). Nothing else about the fold changes.

Not silent: a partial answer; an order with no items; a seat that never ran; a held second-test id that appears twice.

Every test asserts on the recorded `silentSeats` row and decision, not on a helper's return value.

Bite-proof record: silent_seat_fold_2617
"""
import copy
import json
import os
import shlex
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import decision_kinds  # noqa: E402
import receipt_disclosures  # noqa: E402
import round_adapters as RA  # noqa: E402
import round_records as RR  # noqa: E402
import test_c1l10b_test_restore as C10B  # noqa: E402
import test_round_adapters as TRA  # noqa: E402
import test_round_driver as TRD  # noqa: E402
import test_round_driver_integration as IT  # noqa: E402
import test_second_test_c1l7 as C7  # noqa: E402
import test_verifier_vendor_provenance_1797 as P1797  # noqa: E402
import verification as V  # noqa: E402
from session_checkout import enter_checkout  # noqa: E402

RD = TRD.RD
C1 = C10B.C1

_NO_BLOCK = "I could not write a test that reaches it"


@pytest.fixture(autouse=True)
def _pinned_git_config(monkeypatch, tmp_path):
    for name in ("home", "xdg-config"):
        (tmp_path / name).mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


# ---- helpers ---------------------------------------------------------------------------------------------------

def _silent(state, rnd="1"):
    return state["rounds"][rnd].get("silentSeats")


def _of_kind(state, kind):
    return [d for d in state["decisions"] if d["kind"] == kind]


def _assert_decision(state, kind, count):
    (decision,) = _of_kind(state, kind)
    assert ("%d item(s)" % count) in decision["detail"], decision
    assert "unanswered" in decision["detail"] and "nothing was re-asked" in decision["detail"], decision


def _row(phase, items, grain="answer", **extra):
    return dict({"phase": phase, "grain": grain, "items": items}, **extra)


# ---- second-test: the fold's check --------------------------------------------------------------------------------

def _held_state(count):
    """A state holding ``count`` findings for the second-test seat, as the hold leaves it."""
    state = RD.new_state({"leg": "code", "vendors": ["claude", "codex"], "diff": C7._DIFF,
                          "fixerVendor": "claude"})
    state["round"] = 1
    state["step"] = RD.P_SECOND_TEST
    state["_secondTestHeld"] = [
        {"finding": {"id": "v%d" % i, "title": "held %d" % i, "file": "f.py", "line": i + 1,
                     "severity": "Important", "consequence": C7._CONSEQUENCE, "suggestion": C7._FIRST},
         "note": C7._NOTE} for i in range(count)]
    return state


def _fold_second(state, findings):
    RD._fold(state, state["config"], RD.P_SECOND_TEST, {"findings": findings})
    return state


def _answer(item_id, suggestion=_NO_BLOCK):
    return {"id": item_id, "title": "x", "file": "f.py", "line": 1, "severity": "Important",
            "consequence": C7._CONSEQUENCE, "suggestion": suggestion}


def test_second_test_an_empty_answer_is_silent():
    state = _fold_second(_held_state(2), [])
    assert _silent(state) == [_row("second-test", 2)]
    _assert_decision(state, "second-test-silent", 2)
    # the same step and the same per-item rows as ever: the items go on with the test they have
    assert state["step"] == RD.P_VERIFIERS and state["_secondTestPass"] is True
    assert [r["reason"] for r in state["rounds"]["1"]["secondTest"]["noTest"]] == ["no-result", "no-result"]


def test_second_test_an_answer_naming_only_unknown_ids_is_silent():
    state = _fold_second(_held_state(1), [_answer("v99"), _answer("nope")])
    assert _silent(state) == [_row("second-test", 1)]
    _assert_decision(state, "second-test-silent", 1)
    assert state["rounds"]["1"]["secondTest"]["unmatched"] == ["nope", "v99"]


def test_second_test_a_partial_answer_is_not_silent():
    state = _fold_second(_held_state(2), [_answer("v0")])
    assert "silentSeats" not in state["rounds"]["1"]
    assert not _of_kind(state, "second-test-silent")
    assert state["rounds"]["1"]["secondTest"]["noTest"] == [
        {"findingKey": RD._finding_identity_key(state["_secondTestHeld"][0]["finding"]), "reason": "no-block"},
        {"findingKey": RD._finding_identity_key(state["_secondTestHeld"][1]["finding"]), "reason": "no-result"}]


def test_second_test_an_order_with_no_items_is_not_silent():
    state = _fold_second(_held_state(0), [])
    assert "silentSeats" not in state["rounds"]["1"]
    assert not _of_kind(state, "second-test-silent")


def test_second_test_a_held_id_answered_twice_is_named_not_silent():
    state = _fold_second(_held_state(1), [_answer("v0"), _answer("v0")])
    assert "silentSeats" not in state["rounds"]["1"]
    assert not _of_kind(state, "second-test-silent")
    assert [r["reason"] for r in state["rounds"]["1"]["secondTest"]["noTest"]] == ["duplicate-id"]


# ---- second-test: every entry path reaches it -----------------------------------------------------------------------

def test_second_test_hand_submit_of_an_empty_answer_is_silent(tmp_path):
    state, _r = C7._round_two_after(tmp_path, lambda payload: [])
    assert _silent(state) == [_row("second-test", 1)]
    _assert_decision(state, "second-test-silent", 1)
    assert state["rounds"]["1"]["secondTest"]["noTest"] == [{"findingKey": C7._key(), "reason": "no-result"}]
    degraded = RD.build_receipt(state)["degraded"]
    assert any(line.startswith("silent-seat (round 1): the second-test seat answered none of its 1 item(s)")
               for line in degraded), degraded


def test_second_test_hand_submit_of_only_unknown_ids_is_silent(tmp_path):
    state, _r = C7._round_two_after(tmp_path, lambda payload: [
        dict(e, id="v99") for e in C7.Round._default_result(payload)])
    assert _silent(state) == [_row("second-test", 1)]
    assert state["rounds"]["1"]["secondTest"]["unmatched"] == ["v99"]


def test_second_test_hand_submit_the_fold_after_a_silent_answer_equals_the_fold_after_a_minimal_one(tmp_path):
    # the only differences: the silentSeats row, its decision, and the noTest reason (`no-result` vs `no-block`)
    (tmp_path / "silent").mkdir()
    (tmp_path / "named").mkdir()
    silent, _ = C7._round_two_after(tmp_path / "silent", lambda payload: [])
    named, _ = C7._round_two_after(tmp_path / "named", lambda payload: [
        dict(e, suggestion=_NO_BLOCK) for e in C7.Round._default_result(payload)])
    # a minimal answer for an item with no new test is graded `no-block` and is not silent
    assert "silentSeats" not in named["rounds"]["1"]
    assert named["rounds"]["1"]["secondTest"]["noTest"] == [{"findingKey": C7._key(), "reason": "no-block"}]
    assert _silent(silent) == [_row("second-test", 1)]
    assert silent["step"] == named["step"] == RD.P_VERIFIERS
    assert silent["_secondTestPass"] is named["_secondTestPass"] is True

    def staged(state):
        return [(f["id"] if "id" in f else None, f["title"], f["suggestion"], f.get("secondTest"))
                for f in state["_toVerify"]]
    assert staged(silent) == staged(named)
    silent_second, named_second = dict(silent["rounds"]["1"]["secondTest"]), dict(named["rounds"]["1"]["secondTest"])
    assert silent_second.pop("noTest")[0]["reason"] == "no-result"
    assert named_second.pop("noTest")[0]["reason"] == "no-block"
    assert silent_second == named_second
    assert [d["kind"] for d in silent["decisions"] if d["kind"] != "second-test-silent"] == \
        [d["kind"] for d in named["decisions"]]


def test_second_test_hand_submit_of_a_held_id_answered_twice_is_not_silent(tmp_path):
    state, _r = C7._round_two_after(tmp_path, lambda payload: C7.Round._default_result(payload) * 2)
    assert "silentSeats" not in state["rounds"]["1"]
    assert state["rounds"]["1"]["secondTest"]["noTest"] == [{"findingKey": C7._key(), "reason": "duplicate-id"}]


def _second_test_run_loop(tmp_path, answer):
    """run_loop on a real checkout: the test role raises a held finding, then the second-test seat answers
    ``answer(ctx)`` as the vendor it was ordered on; the verifier refutes the finding once it has had its test."""
    checkout = os.path.join(str(tmp_path), "checkout")
    head = enter_checkout(checkout)

    def reviewer(dim, tier, rnd, ctx):
        if dim == "second-test":
            return {"findings": answer(ctx), "vendor": "codex"}
        if rnd == 1 and dim == "test-role":
            return [dict(C7._HELD)]
        return []

    def verifier(clusters, rnd):
        verdicts = []
        for cluster in clusters or []:
            for finding, fid in zip(cluster["findings"], cluster["ids"]):
                verdict = C7._SECOND_REFUTED if finding.get("secondTest") is True else C7._MISSED
                verdicts.append(dict(verdict, id=fid))
        return {"verdicts": verdicts, "vendor": "codex"}

    seams = TRD._seams(reviewer=reviewer, verifier=verifier, vendors=["claude", "codex"])
    cfg = TRD._cfg_cert(diff=C7._DIFF, repoRoot=checkout, headSha=head,
                        breakItInterpreter=shlex.quote(sys.executable))
    _receipt, state = TRD._run_loop_capturing_state(seams, cfg)
    return state


def test_second_test_run_loop_an_empty_answer_is_silent(tmp_path):
    state = _second_test_run_loop(tmp_path, lambda ctx: [])
    assert _silent(state) == [_row("second-test", 1)]
    _assert_decision(state, "second-test-silent", 1)
    assert state["rounds"]["1"]["secondTest"]["noTest"][0]["reason"] == "no-result"


def test_second_test_run_loop_a_named_answer_is_not_silent(tmp_path):
    state = _second_test_run_loop(tmp_path, lambda ctx: [dict(e, suggestion=_NO_BLOCK) for e in ctx["findings"]])
    assert "silentSeats" not in state["rounds"]["1"]
    assert state["rounds"]["1"]["secondTest"]["noTest"][0]["reason"] == "no-block"


def _second_test_advance(tmp_path, payload_for):
    """advance, with the second-test seat's result ``payload_for(pending findings)`` landed for it."""
    head = IT.make_checkout(IT._fixture_repo(tmp_path, "s"))
    session_dir, gitdir, head_path = IT._bootstrap(
        tmp_path, head_sha=head, sliced=True, fixerVendor="cursor",
        seatMap=dict(IT.SEAT_MAP, hostFamily="anthropic"), breakItInterpreter=shlex.quote(sys.executable))
    IT._drive_to_phase(session_dir, gitdir, [IT._test_finding()], head_path, RD.P_SECOND_TEST)
    state = IT._state(session_dir)
    pend = state["pending"]
    roster, reason = RA.roster_for(RD.P_SECOND_TEST, state, state["config"])
    assert reason is None
    slots = IT._slots_of(roster)
    IT._write_dispatch_manifest(session_dir, pend, slots, IT._auditor_vendor_for(state))
    for seat, occurrence in slots:
        IT._land(session_dir, state, pend, seat, {"findings": payload_for(pend["payload"]["findings"])},
                 occurrence=occurrence)
        assert IT._record(session_dir, seat, occurrence=occurrence)["ok"]
    out = RD.cmd_advance(session_dir, git=IT._fake_git(gitdir))
    assert out["ok"], out
    assert out["folded"]["phase"] == RD.P_SECOND_TEST, out
    return IT._state(session_dir)


def test_second_test_advance_an_empty_answer_is_silent(tmp_path):
    state = _second_test_advance(tmp_path, lambda items: [])
    assert _silent(state) == [_row("second-test", 1)]
    _assert_decision(state, "second-test-silent", 1)
    assert state["rounds"]["1"]["secondTest"]["noTest"][0]["reason"] == "no-result"


def test_second_test_advance_a_named_answer_is_not_silent(tmp_path):
    state = _second_test_advance(tmp_path, lambda items: [
        dict(_answer(f["id"]), title=f["title"], file=f["file"], line=f["line"], severity=f["severity"],
             consequence=f["consequence"]) for f in items])
    assert "silentSeats" not in state["rounds"]["1"]
    assert state["rounds"]["1"]["secondTest"]["noTest"][0]["reason"] == "no-block"


# ---- second-test: a seat that never ran ----------------------------------------------------------------------------

def test_second_test_an_unseatable_seat_never_reaches_the_fold_and_records_no_silence(tmp_path):
    # no order is emitted for an unseatable seat (`_hold_for_second_test` returns before the step), so there is no fold
    r = C7.Round(tmp_path, second={C7._HELD["title"]: C7._SECOND_REFUTED}, fixer="cursor",
                 seat_map=C7._verifier_only_seat_map())
    r.drive()
    state = r.state()
    assert RD._nonpanel_unseatable(state, r.dir, RD.P_SECOND_TEST) is True
    assert RD.P_SECOND_TEST not in r.seen
    assert state["rounds"]["1"]["secondTestUnseatable"]
    assert "silentSeats" not in state["rounds"]["1"]
    assert not _of_kind(state, "second-test-silent")


# ---- correction -----------------------------------------------------------------------------------------------------

def _correction_world(tmp_path):
    w = C10B.World(tmp_path)
    w.audit()
    w.restore()
    assert w.state["step"] == RD.P_SECOND_TEST and isinstance(w.state[RD.TEST_CORRECTION_PENDING_FIELD], dict)
    return w


def _correction_row(state):
    return [r for r in state["rounds"]["2"]["testCorrection"]]


def test_correction_an_empty_answer_is_silent_at_the_fold(tmp_path):
    w = _correction_world(tmp_path)
    w.fold(RD.P_SECOND_TEST, {"findings": []})
    assert _silent(w.state, "2") == [_row("second-test-correction", 1)]
    _assert_decision(w.state, "break-it-correction-silent", 1)
    assert _correction_row(w.state) == [{"findingKey": w.key, "outcome": "none", "reason": "no-result"}]
    assert w.state["step"] == RD.P_VERIFY  # the same step an unanswered correction always took


def test_correction_an_answer_naming_only_unknown_ids_is_silent(tmp_path):
    w = _correction_world(tmp_path)
    w.fold(RD.P_SECOND_TEST, {"findings": [{"id": "stranger", "suggestion": C1._block_text(C10B.CORRECTED_TEST)}]})
    assert _silent(w.state, "2") == [_row("second-test-correction", 1)]
    assert _correction_row(w.state) == [{"findingKey": w.key, "outcome": "none", "reason": "no-result"}]


def test_correction_a_minimal_answer_with_no_block_is_not_silent(tmp_path):
    w = _correction_world(tmp_path)
    w.fold(RD.P_SECOND_TEST, {"findings": [{"id": w.key, "suggestion": _NO_BLOCK}]})
    assert "silentSeats" not in w.state["rounds"]["2"]
    assert _correction_row(w.state) == [{"findingKey": w.key, "outcome": "none", "reason": "no-block"}]


def test_correction_a_key_answered_twice_is_named_not_silent(tmp_path):
    w = _correction_world(tmp_path)
    answer = {"id": w.key, "suggestion": _NO_BLOCK}
    w.fold(RD.P_SECOND_TEST, {"findings": [answer, dict(answer)]})
    assert "silentSeats" not in w.state["rounds"]["2"]
    assert _correction_row(w.state)[0]["reason"] == "duplicate-id"


def test_correction_a_partial_answer_is_not_silent(tmp_path):
    w = C10B.World(tmp_path)
    second = copy.deepcopy(w.finding)
    second["title"] = "Another retry bug"
    second["suggestion"] = C1._block_text(C10B.FIXED_TEST).replace(C10B.TEST_PATH, "tests/test_other.py")
    second[RD.REVIEWER_TEST_FIELD] = C10B.ROLE_TEST
    w.write("tests/test_other.py", C10B.FIXED_TEST)
    w.state["rounds"]["1"]["fixFoldHead"] = C10B._commit(w.root, "second test")
    w.state["fixBatch"] = [w.finding, second]
    w.state["_auditTargets"] = RD._audit_targets(w.state, w.cfg, {})
    w.audit()
    w.write(C10B.TEST_PATH, C10B.ROLE_TEST)
    w.write("tests/test_other.py", C10B.ROLE_TEST)
    C10B._commit(w.root, "restore both")
    w.fold(RD.P_APPLY_FIXES, {"fixes": []})
    assert len(w.state[RD.TEST_CORRECTION_PENDING_FIELD]["items"]) == 2
    w.fold(RD.P_SECOND_TEST, {"findings": [{"id": w.key, "suggestion": _NO_BLOCK}]})
    assert "silentSeats" not in w.state["rounds"]["2"]
    assert not _of_kind(w.state, "break-it-correction-silent")
    assert sorted(r["reason"] for r in _correction_row(w.state)) == ["no-block", "no-result"]


def test_correction_an_order_with_no_items_is_not_silent(tmp_path):
    w = _correction_world(tmp_path)
    w.state[RD.TEST_CORRECTION_PENDING_FIELD]["items"] = []
    w.fold(RD.P_SECOND_TEST, {"findings": []})
    assert "silentSeats" not in w.state["rounds"]["2"]
    assert not _of_kind(w.state, "break-it-correction-silent")


def test_correction_an_unseatable_seat_is_never_offered_and_records_no_silence(tmp_path):
    # no seat map, so no reviewer outside the makers' families can be seated: the offer returns before an order
    w = C10B.World(tmp_path, seat_map=False)
    w.audit()
    w.restore()
    assert "break-it-correction-unseatable" in C10B._decisions(w.state)
    assert RD.TEST_CORRECTION_PENDING_FIELD not in w.state and w.state["step"] == RD.P_VERIFY
    assert "silentSeats" not in w.state["rounds"]["2"]
    assert not _of_kind(w.state, "break-it-correction-silent")


def test_correction_run_loop_an_empty_answer_is_silent(tmp_path):
    w = C10B.World(tmp_path, cap=2)

    def fix_step(batch, rnd, payload):
        assert payload.get("restoreOnly"), "the run halts at the verify gate, before any settle fix"
        w.write(C10B.TEST_PATH, payload["restores"][0]["content"])
        C10B._commit(w.root, "restore")
        return {"fixes": []}

    seams = TRD._seams(auditor=lambda targets, rnd: w.audit_artifact()["results"], fix_step=fix_step,
                       reviewer=lambda dim, tier, rnd, ctx: {"findings": [], "vendor": "codex"},
                       verify_runner=lambda command, rnd: "pass")
    seams["panel_diff"] = lambda config, head: (TRD.DIFF, None)
    _receipt, state = w.run_loop(seams)
    assert _silent(state, "2") == [_row("second-test-correction", 1)]
    _assert_decision(state, "break-it-correction-silent", 1)
    assert state["rounds"]["2"]["testCorrection"] == [{"findingKey": w.key, "outcome": "none",
                                                       "reason": "no-result"}]


def test_correction_hand_submit_of_an_empty_answer_is_silent(tmp_path):
    w = _correction_world(tmp_path)
    session = tmp_path / "cli-session"
    session.mkdir()
    (session / RR.META_FILE).write_text(json.dumps({"repoRoot": str(w.root), "headSha": w.fix_head}))
    w.state["reviewedDiff"] = TRD.DIFF
    RD.save_state(str(session), w.state)
    n = RD.cmd_next(str(session))
    assert n["ok"] is True and n["phase"] == RD.P_SECOND_TEST and n["payload"]["correction"] is True, n
    vendor = RD._nonpanel_selection(w.state, str(session), RD.P_SECOND_TEST)[0]
    out = RD.cmd_submit(str(session), n["phase"], n["attempt"], n["expectedStateHash"],
                        {"findings": [], "reviewerVendor": vendor})
    assert out["ok"] is True, out
    ok, state = RD.load_state(str(session))
    assert ok
    assert _silent(state, "2") == [_row("second-test-correction", 1)]
    _assert_decision(state, "break-it-correction-silent", 1)
    assert state["rounds"]["2"]["testCorrection"] == [{"findingKey": w.key, "outcome": "none",
                                                       "reason": "no-result"}]


# ---- verifiers: the answer grain ---------------------------------------------------------------------------------------

def _two_item_state(count=2):
    state = P1797._state()
    state["_toVerify"] = [{"file": "a.py", "line": i + 1, "title": "defect %d" % i, "severity": "Important",
                           "consequence": "a reviewer-found defect stays in the change"} for i in range(count)]
    return state


def _verdict(fid, verdict="CONFIRMED"):
    return {"id": fid, "verdict": verdict, "reason": "checked", "evidence": "ran"}


def _fold_verifiers(state, verdicts, **extra):
    artifact = dict({"verdicts": verdicts, "verifierVendor": "codex"}, **extra)
    RD._fold(state, state["config"], RD.P_VERIFIERS, artifact)
    return state


def test_verifiers_an_empty_answer_is_silent_and_the_items_stay_unverified():
    state = _fold_verifiers(_two_item_state(), [])
    assert _silent(state) == [_row("verifiers", 2)]
    _assert_decision(state, "verifiers-silent", 2)
    assert sorted(state["rounds"]["1"]["verify"]["unverified"]) == ["v0", "v1"]
    assert state["rounds"]["1"]["verify"]["drops"] == []
    assert len(state["_verified"]) == 2


def test_verifiers_an_answer_naming_only_unknown_ids_is_silent():
    state = _fold_verifiers(_two_item_state(), [_verdict("v99"), _verdict("nope")])
    assert _silent(state) == [_row("verifiers", 2)]
    _assert_decision(state, "verifiers-silent", 2)


def test_verifiers_a_partial_answer_is_not_silent():
    state = _fold_verifiers(_two_item_state(), [_verdict("v0")])
    assert "silentSeats" not in state["rounds"]["1"]
    assert not _of_kind(state, "verifiers-silent")
    assert state["rounds"]["1"]["verify"]["unverified"] == ["v1"]


def test_verifiers_an_order_with_no_items_is_not_silent():
    state = _fold_verifiers(_two_item_state(0), [])
    assert "silentSeats" not in state["rounds"]["1"]
    assert not _of_kind(state, "verifiers-silent")


def test_verifiers_an_unseatable_seat_never_ran_so_its_empty_answer_is_not_silent(monkeypatch):
    monkeypatch.setattr(RD, "_nonpanel_unseatable", lambda state, session_dir, phase: phase == RD.P_VERIFIERS)
    state = _fold_verifiers(_two_item_state(), [])
    assert "silentSeats" not in state["rounds"]["1"]
    assert not _of_kind(state, "verifiers-silent")
    assert sorted(state["rounds"]["1"]["verify"]["unverified"]) == ["v0", "v1"]


def test_verifiers_an_answer_the_vendor_check_ignores_still_named_its_items_so_is_not_silent():
    # the answer names its items; it is recorded `verdicts-ignored`, never silent
    state = _fold_verifiers(_two_item_state(1), [_verdict("v0", "REFUTED")], verifierVendor="claude")
    assert state["rounds"]["1"]["verifierProvenance"][-1]["outcome"] == "verdicts-ignored"
    assert "silentSeats" not in state["rounds"]["1"]
    assert not _of_kind(state, "verifiers-silent")


def test_verifiers_run_loop_an_empty_answer_is_silent():
    seams = TRD._seams(reviewer=TRD._panel_finding_reviewer(),
                       verifier=lambda clusters, rnd: {"verdicts": [], "vendor": "codex"},
                       vendors=["claude", "codex"])
    _result, state = TRD._run_loop_capturing_state(seams, TRD._cfg_cert())
    assert _silent(state)[0] == _row("verifiers", 1)
    first = [d for d in state["decisions"] if d["kind"] == "verifiers-silent" and d["round"] == 1]
    assert len(first) == 1 and "1 item(s)" in first[0]["detail"] and "nothing was re-asked" in first[0]["detail"]
    assert state["rounds"]["1"]["verify"]["unverified"]


def test_verifiers_run_loop_an_answer_naming_only_an_unknown_id_is_silent():
    unknown = {"verdicts": [_verdict("v99")], "vendor": "codex"}
    seams = TRD._seams(reviewer=TRD._panel_finding_reviewer(), verifier=lambda clusters, rnd: unknown,
                       vendors=["claude", "codex"])
    _result, state = TRD._run_loop_capturing_state(seams, TRD._cfg_cert())
    assert _silent(state)[0] == _row("verifiers", 1)
    assert state["rounds"]["1"]["verify"]["unverified"]


def test_verifiers_run_loop_a_named_answer_is_not_silent():
    seams = TRD._seams(reviewer=TRD._panel_finding_reviewer(), vendors=["claude", "codex"])
    _result, state = TRD._run_loop_capturing_state(seams, TRD._cfg_cert())
    assert "silentSeats" not in state["rounds"]["1"]
    assert not _of_kind(state, "verifiers-silent")


def test_the_run_loop_seam_never_forwards_the_assembly_keys():
    state = RD.new_state(TRD._cfg())
    forged = {"verdicts": [], "vendor": "codex", "verifierSilentClusters": ["verifier:c1"],
              "verifierSilentItems": 5}
    artifact = RD._run_seam(TRD._seams(verifier=lambda clusters, rnd: forged), RD.P_VERIFIERS,
                            {"clusters": [{"ids": ["v0"]}]}, state, state["config"])
    assert set(artifact) == {"verdicts", "verifierVendor"}


# ---- verifiers: hand submit ---------------------------------------------------------------------------------------------

def _hand_session(tmp_path, name, findings):
    session_dir, gitdir, head_path = IT._bootstrap(tmp_path, name=name)
    IT._drive_to_phase(session_dir, gitdir, findings, head_path, RD.P_VERIFIERS)
    state = IT._state(session_dir)
    state.pop("_advanceUsed", None)  # the same session, now answered by hand
    RD.save_state(session_dir, state)
    assert RD._nonpanel_selection(state, session_dir, RD.P_VERIFIERS)[0] == "codex"
    return session_dir, state


def _hand_submit(session_dir, state, artifact):
    return RD.cmd_submit(session_dir, RD.P_VERIFIERS, state["pending"]["attempt"], RD.state_hash(state),
                         artifact)


_ONE = [P1797._blocking_finding("unchecked index", 2)]
_TWO = [P1797._blocking_finding("unchecked index", 2), P1797._blocking_finding("late defect", 3)]


def test_verifiers_hand_submit_of_an_empty_answer_is_silent(tmp_path):
    session_dir, state = _hand_session(tmp_path, "hand-empty", _ONE)
    out = _hand_submit(session_dir, state, {"verdicts": [], "verifierVendor": "codex"})
    assert out["ok"], out
    after = IT._state(session_dir)
    assert _silent(after) == [_row("verifiers", 1)]
    _assert_decision(after, "verifiers-silent", 1)
    assert after["rounds"]["1"]["verify"]["unverified"]
    degraded = RD.build_receipt(after)["degraded"]
    assert any(line.startswith("silent-seat (round 1): the verifiers seat answered none of its 1 item(s)")
               for line in degraded), degraded


def test_verifiers_hand_submit_of_an_unknown_non_refuted_id_is_silent(tmp_path):
    session_dir, state = _hand_session(tmp_path, "hand-unknown", _ONE)
    out = _hand_submit(session_dir, state, {"verdicts": [_verdict("v99")], "verifierVendor": "codex"})
    assert out["ok"], out
    assert _silent(IT._state(session_dir)) == [_row("verifiers", 1)]


def test_verifiers_hand_submit_of_an_unknown_refuted_id_is_still_refused_before_the_fold(tmp_path):
    session_dir, state = _hand_session(tmp_path, "hand-refuted", _ONE)
    out = _hand_submit(session_dir, state, {"verdicts": [_verdict("v99", "REFUTED")], "verifierVendor": "codex"})
    assert out["ok"] is False and "staged-id-unresolvable" in str(out), out
    after = IT._state(session_dir)
    assert after["rounds"].get("1", {}).get("silentSeats") is None
    assert not _of_kind(after, "verifiers-silent")


def test_verifiers_hand_submit_a_forged_empty_seat_list_cannot_hide_a_silent_answer(tmp_path):
    session_dir, state = _hand_session(tmp_path, "hand-forged-empty", _ONE)
    out = _hand_submit(session_dir, state, {"verdicts": [], "verifierVendor": "codex",
                                            "verifierSilentClusters": [], "verifierSilentItems": 0})
    assert out["ok"], out
    assert _silent(IT._state(session_dir)) == [_row("verifiers", 1)]


def test_verifiers_hand_submit_a_forged_seat_list_cannot_make_a_partial_answer_silent(tmp_path):
    session_dir, state = _hand_session(tmp_path, "hand-forged-partial", _TWO)
    staged = V.stage_ids(state["_toVerify"])
    assert len(staged) == 2
    out = _hand_submit(session_dir, state, {"verdicts": [_verdict(staged[0]["id"])], "verifierVendor": "codex",
                                            "verifierSilentClusters": ["verifier:forged"],
                                            "verifierSilentItems": 2})
    assert out["ok"], out
    after = IT._state(session_dir)
    assert "silentSeats" not in after["rounds"]["1"]
    assert not _of_kind(after, "verifiers-silent")


def test_verifiers_hand_submit_a_forged_seat_list_does_not_change_the_answer_grain_row(tmp_path):
    session_dir, state = _hand_session(tmp_path, "hand-forged-seats", _TWO)
    out = _hand_submit(session_dir, state, {"verdicts": [], "verifierVendor": "codex",
                                            "verifierSilentClusters": ["verifier:forged"],
                                            "verifierSilentItems": 99})
    assert out["ok"], out
    assert _silent(IT._state(session_dir)) == [_row("verifiers", 2)]


def test_verifiers_hand_submit_a_partial_answer_is_not_silent(tmp_path):
    session_dir, state = _hand_session(tmp_path, "hand-partial", _TWO)
    staged = V.stage_ids(state["_toVerify"])
    out = _hand_submit(session_dir, state, {"verdicts": [_verdict(staged[0]["id"])], "verifierVendor": "codex"})
    assert out["ok"], out
    after = IT._state(session_dir)
    assert "silentSeats" not in after["rounds"]["1"]
    assert after["rounds"]["1"]["verify"]["unverified"] == [staged[1]["id"]]


# ---- verifiers: advance (the seat grain) -------------------------------------------------------------------------------

_FAR = [P1797._blocking_finding("unchecked index", 2),
        dict(P1797._blocking_finding("late defect", 2), file=IT.FILES[1])]


def _advance_verifiers(tmp_path, name, findings, answer):
    """advance over the verifier seats. ``answer(index, ids)`` is the seat's verdict list, or None to record the
    seat missing. -> (state, [the seats' storage keys], [the seats' ordered ids])"""
    session_dir, gitdir, head_path = IT._bootstrap(tmp_path, name=name)
    IT._drive_to_phase(session_dir, gitdir, findings, head_path, RD.P_VERIFIERS)
    state = IT._state(session_dir)
    pend = state["pending"]
    roster, reason = RA.roster_for(RD.P_VERIFIERS, state, state["config"])
    assert reason is None
    slots = IT._slots_of(roster)
    IT._write_dispatch_manifest(session_dir, pend, slots, IT._auditor_vendor_for(state))
    keys, ordered = [], []
    for index, (seat, occurrence) in enumerate(slots):
        ids = [f["id"] for f in IT._cluster_for(pend, seat).get("findings") or []]
        keys.append(RR.storage_key(seat, occurrence))
        ordered.append(ids)
        verdicts = answer(index, ids)
        if verdicts is None:
            out = RD.cmd_record_missing(session_dir, seat, pend["attempt"], RR.MISSING_REASONS[0],
                                        occurrence=occurrence)
        else:
            IT._land(session_dir, state, pend, seat, {"verdicts": verdicts}, occurrence=occurrence)
            out = IT._record(session_dir, seat, occurrence=occurrence)
        assert out["ok"], out
    out = RD.cmd_advance(session_dir, git=IT._fake_git(gitdir))
    assert out["ok"] and out["folded"]["phase"] == RD.P_VERIFIERS, out
    return IT._state(session_dir), keys, ordered


def _answers(ids):
    return [_verdict(fid) for fid in ids]


def test_verifiers_advance_one_silent_seat_is_recorded_by_seat(tmp_path):
    state, keys, ordered = _advance_verifiers(
        tmp_path, "adv-one", _FAR, lambda i, ids: [] if i == 0 else _answers(ids))
    assert len(keys) == 2
    assert _silent(state) == [_row("verifiers", 1, grain="seat", seats=[keys[0]])]
    _assert_decision(state, "verifiers-silent", 1)
    # the silent seat's item stays unverified; the answering seat's folds
    assert state["rounds"]["1"]["verify"]["unverified"] == ordered[0]
    degraded = RD.build_receipt(state)["degraded"]
    assert any(line.startswith("silent-seat (round 1): verifier seat(s) %s answered none of its 1 item(s)" % keys[0])
               for line in degraded), degraded


def test_verifiers_advance_every_seat_silent_names_every_seat_sorted(tmp_path):
    state, keys, _ordered = _advance_verifiers(tmp_path, "adv-all", _FAR, lambda i, ids: [])
    assert _silent(state) == [_row("verifiers", 2, grain="seat", seats=sorted(keys))]
    (decision,) = _of_kind(state, "verifiers-silent")
    assert all(key in decision["detail"] for key in keys), decision


def test_verifiers_advance_a_seat_naming_only_an_unknown_id_is_silent(tmp_path):
    state, keys, _ordered = _advance_verifiers(
        tmp_path, "adv-unknown", _FAR, lambda i, ids: [_verdict("v99")] if i == 1 else _answers(ids))
    assert _silent(state) == [_row("verifiers", 1, grain="seat", seats=[keys[1]])]


def test_verifiers_advance_a_seat_naming_only_another_seats_id_is_silent(tmp_path):
    other = {}

    def answer(index, ids):
        other[index] = ids
        return [_verdict(other[0][0])] if index == 1 and 0 in other else _answers(ids)

    state, keys, _ordered = _advance_verifiers(tmp_path, "adv-cross", _FAR, answer)
    assert _silent(state) == [_row("verifiers", 1, grain="seat", seats=[keys[1]])]


def test_verifiers_advance_a_partial_answer_is_not_silent(tmp_path):
    state, keys, ordered = _advance_verifiers(
        tmp_path, "adv-partial", _TWO, lambda i, ids: _answers(ids[:1]))
    assert len(keys) == 1 and len(ordered[0]) == 2
    assert "silentSeats" not in state["rounds"]["1"]
    assert not _of_kind(state, "verifiers-silent")
    assert state["rounds"]["1"]["verify"]["unverified"] == ordered[0][1:]


def test_verifiers_advance_with_every_seat_missing_records_no_silence(tmp_path):
    state, keys, _ordered = _advance_verifiers(tmp_path, "adv-missing", _FAR, lambda i, ids: None)
    prov = state["rounds"]["1"]["adapterProvenance"]["byPhase"][RD.P_VERIFIERS]
    assert len(prov["unverifiedClusters"]) == len(keys) == 2
    assert "silentSeats" not in state["rounds"]["1"]
    assert not _of_kind(state, "verifiers-silent")


def test_verifiers_advance_a_missing_seat_is_never_named_with_a_silent_one(tmp_path):
    state, keys, _ordered = _advance_verifiers(
        tmp_path, "adv-mixed", _FAR, lambda i, ids: None if i == 0 else [])
    assert _silent(state) == [_row("verifiers", 1, grain="seat", seats=[keys[1]])]
    prov = state["rounds"]["1"]["adapterProvenance"]["byPhase"][RD.P_VERIFIERS]
    assert [m["seat"] for m in prov["unverifiedClusters"]] == [keys[0]]
    assert [m["seat"] for m in prov["silentClusters"]] == [keys[1]]


def test_verifiers_advance_with_no_silent_seat_records_no_silence(tmp_path):
    state, _keys, _ordered = _advance_verifiers(tmp_path, "adv-none", _FAR, lambda i, ids: _answers(ids))
    assert "silentSeats" not in state["rounds"]["1"]
    assert "silentClusters" not in state["rounds"]["1"].get("adapterProvenance", {}).get("byPhase", {}).get(
        RD.P_VERIFIERS, {})


# ---- the assembly ---------------------------------------------------------------------------------------------------------

def _assembly(tmp_path, answer, manifest="ids", landed=True):
    """`assemble` over the one verifier seat of a two-finding order. ``manifest``: "ids" gives the seat its ids,
    "no-ids" an entry with no ids, "none" no manifest at all. -> (artifact, seat, storage key, ids)"""
    d, n, state = TRA._at(tmp_path, RD.P_VERIFIERS, cfg=TRA._cfg_proven(),
                          respond=TRA._responder(round1_findings=TRA._TWO_FINDINGS))
    (cluster,) = n["payload"]["clusters"]
    seat = RA.VERIFIER_SEAT_PREFIX + cluster["key"]
    skey = RR.storage_key(seat, 0)
    ids = list(cluster["ids"])
    orders = {"ids": {"seats": {skey: {"ids": ids}}}, "no-ids": {"seats": {skey: {}}}, "none": None}[manifest]
    envelope = TRA._result_env(seat, {"verdicts": answer(ids)}) if landed else TRA._missing_env(seat)
    artifact, reason = RA.assemble(RD.P_VERIFIERS, [envelope], state, state["config"], None, None, orders)
    assert reason is None, reason
    return artifact, seat, skey, ids


def test_assembly_a_landed_seat_naming_none_of_its_ids_is_silent(tmp_path):
    artifact, seat, skey, ids = _assembly(tmp_path, lambda ids: [])
    assert artifact["verifierSilentClusters"] == [skey]
    assert artifact["verifierSilentItems"] == len(ids) == 2
    assert artifact["provenance"]["silentClusters"] == [{"seat": seat, "occurrence": 0}]


def test_assembly_a_seat_naming_only_an_unknown_id_is_silent(tmp_path):
    artifact, _seat, skey, _ids = _assembly(tmp_path, lambda ids: [_verdict("v99")])
    assert artifact["verifierSilentClusters"] == [skey]


def test_assembly_a_partial_answer_is_not_silent(tmp_path):
    artifact, _seat, _skey, _ids = _assembly(tmp_path, lambda ids: [_verdict(ids[0])])
    assert artifact["verifierSilentClusters"] == [] and artifact["verifierSilentItems"] == 0
    assert "silentClusters" not in artifact.get("provenance", {})


@pytest.mark.parametrize("manifest", ["none", "no-ids"])
def test_assembly_a_seat_with_no_manifest_entry_or_no_ids_is_not_judged(tmp_path, manifest):
    artifact, _seat, _skey, _ids = _assembly(tmp_path, lambda ids: [], manifest=manifest)
    assert artifact["verifierSilentClusters"] == [] and artifact["verifierSilentItems"] == 0
    assert "silentClusters" not in artifact.get("provenance", {})


def test_assembly_an_omitted_seat_stays_in_unverified_clusters_only(tmp_path):
    artifact, seat, _skey, _ids = _assembly(tmp_path, lambda ids: [], landed=False)
    assert artifact["verifierSilentClusters"] == [] and artifact["verifierSilentItems"] == 0
    assert [m["seat"] for m in artifact["provenance"]["unverifiedClusters"]] == [seat]
    assert "silentClusters" not in artifact["provenance"]


# ---- the disclosure -------------------------------------------------------------------------------------------------------

def test_the_decision_kinds_the_folds_write_are_registered():
    for kind in ("second-test-silent", "break-it-correction-silent", "verifiers-silent"):
        assert kind in decision_kinds.DECISION_KINDS, kind


def test_silent_seats_is_a_carried_channel_the_verifier_fold_records():
    assert "silentSeats" in RD.VERIFIER_FOLD_DISCLOSURE_CHANNELS
    assert "silentSeats" in receipt_disclosures.CARRIED_DISCLOSURE_CHANNELS
    assert receipt_disclosures.CARRIED_DISCLOSURE_CHANNELS["silentSeats"] is receipt_disclosures.dict_list


def test_the_degraded_prose_names_each_grain():
    lines = []
    receipt_disclosures._round_verifier_synthesis_prose("3", {"silentSeats": [
        {"phase": "second-test", "grain": "answer", "items": 2},
        {"phase": "second-test-correction", "grain": "answer", "items": 1},
        {"phase": "verifiers", "grain": "answer", "items": 4},
        {"phase": "verifiers", "grain": "seat", "items": 3, "seats": ["verifier:c1", "verifier:c2"]}]}, lines)
    tail = ("they are recorded as unanswered (unverified or no new test) and nothing was re-asked")
    assert lines == [
        "silent-seat (round 3): the second-test seat answered none of its 2 item(s); " + tail,
        "silent-seat (round 3): the second-test-correction seat answered none of its 1 item(s); " + tail,
        "silent-seat (round 3): the verifiers seat answered none of its 4 item(s); " + tail,
        "silent-seat (round 3): verifier seat(s) verifier:c1, verifier:c2 answered none of its 3 item(s); " + tail]


def test_the_degraded_prose_says_nothing_without_a_silent_row():
    lines = []
    receipt_disclosures._round_verifier_synthesis_prose("1", {"verifyPasses": [{"CONFIRMED": 1}]}, lines)
    assert lines == []
