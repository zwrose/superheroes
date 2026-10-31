"""C1-L4: the owner gates are retired — nothing from the review reaches the owner mid-review.

The round driver has no phase that presents anything to the owner: every phase is a `dispatch-*`
phase, `run-verify`, `apply-fixes` or `terminal`. Where the loop used to stop at the owner-judgment gate or the
audit-stall menu it now keeps working or hands the PR back through the one `handed-back` verdict:

  - an audit stall that persists after the one recovery attempt → `fix-keeps-failing`;
  - a blocking finding only the owner's choice can settle is held out of the fix batch and handed
    back open (`owner-choice-open`) by the convergence chokepoint, `_terminal_converged`.

Drives the real round driver: `run_loop` with scripted seams for the loop-shaped cases, the CLI
(`next` / `submit` / `rule`) for the ruled case, and the pieces directly for the edges.

Bite-proof record: c1l4_wo_a
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import decision_kinds as DK  # noqa: E402
import review_record_session as RS  # noqa: E402
import round_phases as RP  # noqa: E402
import session_contract as SC  # noqa: E402
import test_outcome_settle_c7 as TOC  # noqa: E402
import test_review_record_session as TRRS  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD  # run_loop runs on test_round_driver's own load of the module

_BUG = {"title": "bug", "severity": "Important", "consequence": TRD._CONSEQUENCE,
        "file": "f.py", "line": 1}
_CHOICE = {"title": "widen the API", "severity": "Important", "consequence": TRD._CONSEQUENCE,
           "file": "f.py", "line": 2, "tradeoff": True}
_BUG_KEY = "f.py::bug@L1"
_CHOICE_KEY = "f.py::widen the api@L2"
_ALLOWED_ACTIONS = ("run-verify", "apply-fixes", "terminal")


def _is_allowed(action):
    return action.startswith("dispatch-") or action in _ALLOWED_ACTIONS


def _spy_actions(monkeypatch):
    """Record every action the loop emits, and — at each fixer order — how many `self-recovery`
    decisions the session had journaled by then."""
    seen, fixer_orders = [], []
    orig = RD._advance

    def spy(state, config):
        step = orig(state, config)
        seen.append(step["action"])
        if step["action"] == RD.P_APPLY_FIXES:
            fixer_orders.append(sum(1 for d in state["decisions"] if d["kind"] == "self-recovery"))
        return step

    monkeypatch.setattr(RD, "_advance", spy)
    return seen, fixer_orders


def _reviewer(findings):
    def reviewer(dim, tier, rnd, ctx):
        if rnd == 1 and dim == "code-reviewer":
            return {"findings": [dict(f) for f in findings]}
        return []

    return reviewer


def _failing_fix_seams(findings):
    """Every fix fails its audit: the PLAUSIBLE blockers are fixed, never discharged."""
    counter = {"n": 0}

    def fix_step(batch, rnd, payload):
        counter["n"] += 1
        return {"fixes": [], "headDiff": TRD._headf(counter["n"]), "changedSubjects": ["Code"]}

    def plausible(clusters, rnd):
        return [{"id": i, "verdict": "PLAUSIBLE", "reason": "checked"}
                for c in (clusters or []) for i in (c.get("ids") or [])]

    return TRD._seams(
        reviewer=_reviewer(findings), verifier=plausible, fix_step=fix_step,
        auditor=lambda targets, rnd: [{"id": t["id"], "ruling": "not-discharged", "reason": "broken",
                                       "checks": TRD.audit_checks(right="no")}
                                      for t in (targets or [])])


def _cfg_scoped_finder_seated(**over):
    """A fix changes a file, so the round's scoped finder runs; the proven non-panel cells let it seat on
    the vendor outside the fixer's family, so the loop reaches the end the test guards, not a park."""
    return TRD._cfg_cert(seatMap=TRD._nonpanel_cell_proof(["claude", "codex"]), **over)


def _kinds(state):
    return [d["kind"] for d in state["decisions"]]


def _ledger(state):
    return {SC.finding_identity_key(e): e for e in state.get(SC.DISPOSITION_LEDGER_KEY) or []}


# --- T1: no phase puts anything to the owner ---------------------------------------------------

def test_t1_every_phase_is_a_dispatch_or_run_verify_or_terminal():
    # axis: the phase census — a phase that is none of dispatch-*, run-verify, apply-fixes or terminal is a phase
    # that presents to the owner — see bite-proof record c1l4_wo_a
    assert RP.ALL_PHASES, "the census enumerated no phase — it is inert"
    for phase in RP.ALL_PHASES:
        assert _is_allowed(phase), "%r is not a dispatch-*, run-verify, apply-fixes or terminal phase" % (phase,)


def test_t1_a_loop_through_a_tradeoff_blocker_and_an_audit_stall_never_leaves_that_set(monkeypatch):
    # axis: the actions the loop actually emits — a census of the constants alone passes a loop that
    # still emits a phase the constants no longer list — see bite-proof record c1l4_wo_a
    seen, _orders = _spy_actions(monkeypatch)
    _result, state = TRD._run_loop_capturing_state(
        _failing_fix_seams([_BUG, _CHOICE]), _cfg_scoped_finder_seated(maxRounds=20))
    assert state["terminal"] == "handed-back"
    kinds = _kinds(state)
    assert "owner-choice-held" in kinds and "self-recovery" in kinds, kinds  # both paths were walked
    assert kinds[-1] == "fix-keeps-failing", kinds
    assert RD.P_APPLY_FIXES in seen and RD.P_AUDITS in seen
    assert [a for a in seen if not _is_allowed(a)] == []


# --- T2 / E1: a stall after the recovery attempt hands back ------------------------------------

def test_t2_a_fix_that_keeps_failing_gets_one_recovery_then_is_handed_back(monkeypatch):
    # axis: a stall with selfRecovered already true ends handed-back, never held or stalled
    seen, fixer_orders = _spy_actions(monkeypatch)
    _result, state = TRD._run_loop_capturing_state(
        _failing_fix_seams([_BUG]), _cfg_scoped_finder_seated(maxRounds=20))
    assert state["terminal"] == "handed-back"
    assert state["terminal"] not in ("held", "stalled")
    assert state["decisions"][-1]["kind"] == "fix-keeps-failing"
    assert _kinds(state).count("self-recovery") == 1
    assert state["selfRecovered"] is True
    assert 0 in fixer_orders and fixer_orders[-1] == 1, fixer_orders  # a fixer order followed the recovery
    assert [a for a in seen if a.startswith("present-")] == []
    assert [a for a in seen if not _is_allowed(a)] == []
    assert state["certification"]["shape"] is None and state["certification"]["reason"]
    ledger = _ledger(state)
    assert ledger and all(row.get("disposition") for row in ledger.values()), ledger  # every finding has an outcome
    assert state.get("settleSkipped") is None


# --- T3 / E2: a round whose only blocker needs the owner's choice ------------------------------

def test_t3_a_round_one_with_only_an_owner_choice_blocker_is_handed_back_at_round_one(monkeypatch):
    # axis: held findings leave the fixer batch and the loop reaches the chokepoint with nothing to fix
    seen, fixer_orders = _spy_actions(monkeypatch)
    _result, state = TRD._run_loop_capturing_state(
        TRD._seams(reviewer=_reviewer([_CHOICE])), TRD._cfg_cert())
    assert state["terminal"] == "handed-back"
    assert state["decisions"][-1]["kind"] == "owner-choice-open"
    assert _kinds(state).count("owner-choice-held") == 1
    assert state["ownerChoiceHeld"] == [_CHOICE_KEY]
    assert sorted(state["rounds"]) == ["1"]
    assert RD.P_APPLY_FIXES not in seen and fixer_orders == []
    assert "widen the API" in state["certification"]["reason"]


# --- T4 / E3: the chokepoint refuses to converge over an open owner choice ---------------------

def test_t4_a_mixed_batch_fixes_the_mechanical_blocker_then_hands_the_owner_choice_back():
    # axis: _terminal_converged refuses to converge over a held finding nothing has settled — see bite-proof record c1l4_wo_a
    offers = []

    def fix_step(batch, rnd, payload):
        offers.append((rnd, [RD._fix_batch_row_key(r) for r in batch]))
        return {"fixes": [], "headDiff": TRD.HEAD, "changedSubjects": ["Code"]}

    _result, state = TRD._run_loop_capturing_state(
        TRD._seams(reviewer=_reviewer([_BUG, _CHOICE]), fix_step=fix_step),
        _cfg_scoped_finder_seated())
    assert state["terminal"] != "converged"
    assert state["terminal"] == "handed-back"
    assert state["decisions"][-1]["kind"] == "owner-choice-open"
    assert offers == [(1, [_BUG_KEY])]  # the held finding never reached the fixer
    ledger = _ledger(state)
    assert ledger[_BUG_KEY]["disposition"] == "fixed"
    assert ledger[_CHOICE_KEY]["disposition"] != "fixed" and ledger[_CHOICE_KEY].get("disposition")


# --- T5 / E4: the owner rules the held finding out of scope ------------------------------------

@pytest.mark.parametrize("ruled", [True, False], ids=["ruled-out-of-scope", "no-ruling"])
def test_t5_a_held_finding_ruled_out_of_scope_before_the_fixer_step_lets_the_session_converge(tmp_path, ruled):
    # axis: a `rule` out-of-scope ruling settles a held finding; without it the same fixture hands back
    d = str(tmp_path)
    cfg = TRD._cfg()
    respond = TRD._responder(round1_findings=[dict(_BUG), dict(_CHOICE)], vendors=cfg["vendors"])
    pending = TRD._drive_to_phase(d, cfg, respond, RD.P_APPLY_FIXES)
    assert [row["title"] for row in pending["payload"]["batch"]] == ["bug"]  # the choice is held out
    ok, state = RD.load_state(d)
    assert ok and state["ownerChoiceHeld"] == [_CHOICE_KEY]
    if ruled:
        path = TOC._write_rulings(tmp_path / "rulings.json", [TOC._ruling(_CHOICE_KEY)])
        out = RD.cmd_rule(d, path, "owner")
        assert out.get("ok"), out
    payload = TRD._drive_cli(d, None, respond)
    if ruled:
        assert payload["verdict"] == "converged", payload
    else:
        assert payload["verdict"] == "handed-back", payload
        assert payload["certification"]["shape"] is None


# --- E6: a ledger that cannot be read settles nothing ------------------------------------------

def _held_state():
    state = RD.new_state(TRD._cfg_cert())
    state["ownerChoiceHeld"] = [_CHOICE_KEY]
    state[SC.DISPOSITION_LEDGER_OWNER_FIELD] = SC.DISPOSITION_LEDGER_OWNER_VALUE
    return state


def test_e6_an_unreadable_ledger_hands_back_and_never_converges():
    # axis: a ledger read fault counts as unsettled at the chokepoint (fail closed)
    state = _held_state()
    state.pop(SC.DISPOSITION_LEDGER_KEY, None)  # an owned ledger that is absent is malformed
    RD._terminal_converged(state, state["config"], full_panel=True)
    assert state["terminal"] == "handed-back"
    assert state["decisions"][-1]["kind"] == "owner-choice-open"


def test_e6_the_same_state_with_a_readable_fixed_row_converges():
    # axis: A/B for the test above — a current `fixed` ledger row settles the held finding
    state = _held_state()
    state[SC.DISPOSITION_LEDGER_KEY] = [{
        SC.FINDING_KEY_FIELD: _CHOICE_KEY, "title": "widen the API", "file": "f.py", "line": 2,
        "severity": "Important", "disposition": "fixed", "dispositionRound": 2,
        SC.DISPOSITION_SEQ_FIELD: 2, SC.RAISED_SEQ_FIELD: 1}]
    assert RD._unsettled_owner_choices(state) == []
    RD._terminal_converged(state, state["config"], full_panel=True)
    assert state["terminal"] == "converged"


@pytest.mark.parametrize("disp_seq, raised_seq, restaged", [
    (2, 3, None),
    (2, 1, {_CHOICE_KEY: 2}),
], ids=["discharge-older-than-the-raise", "discharge-reopened-by-a-restage"])
def test_e6_a_stale_fixed_row_never_settles_a_reopened_owner_choice(disp_seq, raised_seq, restaged):
    # axis: the freshness checks in _owner_choice_settled — an old discharge cannot settle a reopened choice
    state = _held_state()
    state[SC.DISPOSITION_LEDGER_KEY] = [{
        SC.FINDING_KEY_FIELD: _CHOICE_KEY, "title": "widen the API", "file": "f.py", "line": 2,
        "severity": "Important", "disposition": "fixed", "dispositionRound": 2,
        SC.DISPOSITION_SEQ_FIELD: disp_seq, SC.RAISED_SEQ_FIELD: raised_seq}]
    if restaged is not None:
        state["restagedAfterDispositionSeq"] = restaged
    RD._terminal_converged(state, state["config"], full_panel=True)
    assert state["terminal"] == "handed-back"
    assert state["decisions"][-1]["kind"] == "owner-choice-open"
    assert state["certification"]["shape"] is None


# --- E7 / E8: the retired phases and the retired flag ------------------------------------------

@pytest.mark.parametrize("phase", ["present-judgment", "present-stall-menu"])
def test_e7_a_submit_naming_a_retired_phase_is_refused_by_the_phase_echo_check(tmp_path, phase):
    d = str(tmp_path)
    checkout = os.path.join(d, "checkout")  # the first pending step is enough: any other phase mismatches it
    TRD.enter_checkout(checkout)
    TRD._seed_repo_root_if_missing(d, checkout)
    n = RD.cmd_next(d, TRD._cfg())
    assert n["ok"], n
    out = RD.cmd_submit(d, phase, n["attempt"], n["expectedStateHash"], {})
    assert out == {"ok": False, "reason": "phase/attempt echo does not match the pending step"}, out
    assert any(e.get("outcome") == "echo-mismatch" and e.get("phase") == phase
               for e in RD.read_journal(d))


def test_e8_advance_rejects_the_retired_owner_artifact_flag(tmp_path):
    with pytest.raises(SystemExit) as exc:
        RD.build_parser().parse_args(
            ["advance", "--session-dir", str(tmp_path), "--owner-artifact", "gate.json"])
    assert exc.value.code == 2


def test_the_held_stop_reason_of_the_retired_menu_is_gone():
    assert RD.CHECKPOINT_STOP_REASONS == ("tripwire", "park")
    with pytest.raises(SystemExit):
        RD.build_parser().parse_args(["checkpoint", "--session-dir", ".", "--stop-reason", "held"])


# --- the handed-back terminal: one writer, its vocabulary and its record -----------------------

def test_hand_back_is_the_one_writer_of_the_terminal():
    state = RD.new_state(TRD._cfg_cert())
    RD._hand_back(state, "owner-choice-open", "1 finding(s) need the owner's choice", cap=False)
    assert state["terminal"] == "handed-back" and state["step"] == RD.P_TERMINAL
    assert state["certification"] == {"shape": None, "reason": "1 finding(s) need the owner's choice"}
    assert state["decisions"][-1]["kind"] == "owner-choice-open"
    assert state["decisions"][-1]["detail"] == "1 finding(s) need the owner's choice"


def test_handed_back_is_a_cap_verdict_known_to_both_vocabularies():
    assert "handed-back" in DK.CERTIFIED_VERDICTS and "handed-back" in RD.CERTIFIED_VERDICTS
    assert DK.map_verdict_to_terminal_state("handed-back") == "cap"
    assert {"round-cap", "fix-keeps-failing", "owner-choice-open", "extra-audit-open",
            "owner-choice-held"} <= set(DK.DECISION_KINDS)
    assert DK.map_terminal_cause("handed-back", "round-cap") == {"kind": "non-loop", "reason": "open-findings"}
    assert DK.map_terminal_cause("handed-back", "fix-keeps-failing") == {"kind": "loop", "reason": "fixer-cycle"}
    assert DK.map_terminal_cause("handed-back", "owner-choice-open") == {"kind": "non-loop", "reason": "open-findings"}
    assert DK.map_terminal_cause("handed-back", "extra-audit-open") == {"kind": "non-loop", "reason": "open-findings"}
    # a finished earlier-version session still maps
    assert DK.map_terminal_cause("held", "stall-choice") == {"kind": "loop", "reason": "latch"}
    assert DK.map_terminal_cause("stalled", "stall-menu") == {"kind": "loop", "reason": "latch"}


def test_the_driver_no_longer_writes_the_held_or_stalled_verdicts():
    for name in ("round_driver.py", "round_phases.py"):
        with open(os.path.join(_LIB, name), encoding="utf-8") as fh:
            source = fh.read()
        assert "present-judgment" not in source and "present-stall-menu" not in source, name
    with open(os.path.join(_LIB, "round_driver.py"), encoding="utf-8") as fh:
        source = fh.read()
    assert '_set_terminal(state, "held"' not in source
    assert '_set_terminal(state, "stalled"' not in source


# --- T6: the record maps the new terminal ------------------------------------------------------

def _stopped_at_cap(tmp_path, terminal, decisions):
    s = TRRS.Session(tmp_path, terminal=terminal, rounds={"1": {}, "2": {}}, decisions=decisions)
    s.state["config"] = {"maxRounds": 3}
    s.seat("code-reviewer")
    return RS.account_from_session(s.save(), TRRS.extras())["rounds"]["stoppedAtCap"]


def test_t6_the_hand_backs_of_t2_and_t3_did_not_stop_at_the_cap(tmp_path):
    # axis: stoppedAtCap reads the hand-back's own cause — a "cap" terminal state alone is not a stop at the cap
    _r, stalled = TRD._run_loop_capturing_state(
        _failing_fix_seams([_BUG]), _cfg_scoped_finder_seated(maxRounds=20))
    _r, choice = TRD._run_loop_capturing_state(
        TRD._seams(reviewer=_reviewer([_CHOICE])), TRD._cfg_cert())
    assert stalled["decisions"][-1]["kind"] == "fix-keeps-failing"
    assert choice["decisions"][-1]["kind"] == "owner-choice-open"
    assert _stopped_at_cap(tmp_path / "stalled", stalled["terminal"], stalled["decisions"]) is False
    assert _stopped_at_cap(tmp_path / "choice", choice["terminal"], choice["decisions"]) is False


@pytest.mark.parametrize("kind,cap,stopped", [
    ("round-cap", True, True),
    ("extra-audit-open", True, True),
    ("fix-keeps-failing", False, False),
    ("owner-choice-open", False, False),
])
def test_t6_a_hand_back_stopped_at_the_cap_only_for_the_round_cap_and_the_extra_audit(
        tmp_path, kind, cap, stopped):
    # axis: the record's cap flag follows the hand-back's decision kind
    state = RD.new_state(TRD._cfg_cert())
    RD._hand_back(state, kind, "findings still open", cap=cap)
    assert _stopped_at_cap(tmp_path, state["terminal"], state["decisions"]) is stopped


def test_t6_the_legacy_verdicts_keep_their_cap_rule(tmp_path):
    assert _stopped_at_cap(tmp_path / "a", "capped-with-open-blocker", []) is True
    assert _stopped_at_cap(tmp_path / "b", "converged", []) is False
