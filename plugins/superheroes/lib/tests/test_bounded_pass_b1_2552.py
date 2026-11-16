"""The review loop's bounded pass (issue 2552, layer 1): a cap round whose fixes no audit has checked does not
hand back. Round `cap + 1` audits those fixes and nothing else, with no advisor order.

The pass converges `bounded-pass` when every fix discharges with nothing Important open, and otherwise hands
back as the cap always did. The ordered extra audit round of the earlier release keeps working on a session
saved inside it. Past the cap a session runs at most one round, and that round dispatches only the audits.

Drives the real round driver through the CLI functions (`cmd_next`, `cmd_submit`) on a session directory built
the way production builds one; the record through the session writer and the record validator.

Bite-proof record: i2552_bounded_pass_b1
"""
import copy
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import review_record as RR  # noqa: E402
import session_checkout as SC  # noqa: E402
import test_c1l4b_extra_audit as X  # noqa: E402
import test_review_record as TRR  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD
CAP = X.CAP
MISSING = object()  # a new issue with no `severity` key at all


# --- a session driven to and through the bounded pass -----------------------------------------------

def _audit_answer(payload, outcome, new_issue):
    results = []
    for t in payload.get("targets", []):
        row = {"id": t["id"], "auditorVendor": t.get("auditorVendor"), "checks": TRD.audit_checks()}
        if outcome == "not-discharged":
            row.update(ruling="not-discharged", reason="still broken")
        elif new_issue is not None:
            row.update(ruling="discharged-but-new-issue", reason="fix resolves it", evidence="tests pass",
                       newIssues=[dict(new_issue)])
        else:
            row.update(ruling="discharged", reason="fix resolves it", evidence="tests pass")
        results.append(row)
    return {"results": results,
            "collectionManifest": {t["id"]: t.get("auditorVendor") for t in payload.get("targets", [])}}


def _respond(outcome="discharged", new_issue=None):
    """The scripted answers of `X._respond`, except that the audits of a round past the cap answer `outcome`
    (discharged or not-discharged) and, when `new_issue` is given, raise it. The fixer reports the fix it applied
    (the pass begins only on an applied fix), which `X._respond`'s fixer does not."""
    base = X._respond(cap=CAP)

    def respond(phase, payload, rnd):
        if phase == RD.P_AUDITS and rnd > CAP:
            return _audit_answer(payload, outcome, new_issue)
        answer = base(phase, payload, rnd)
        if phase == RD.P_APPLY_FIXES:
            answer = dict(answer, fixes=[{"note": "fixed the open finding in round %d" % rnd}])
        return answer

    return respond


def _issue(severity="Important", file="newsurf.py", line=1):
    issue = {"title": "raised-by-the-audit", "consequence": TRD._CONSEQUENCE, "file": file, "line": line}
    if severity is not MISSING:
        issue["severity"] = severity
    return issue


def _run(d, cfg, respond, stop=None, max_steps=200):
    """next/submit to the terminal (or until `stop(n)` holds of an emission); the last `next` answer and every
    (action, round) emitted."""
    trace = []
    for step in range(max_steps):
        n = RD.cmd_next(d, cfg if step == 0 else None)
        assert n["ok"], n
        trace.append((n["action"], n["round"]))
        if n["action"] == RD.P_TERMINAL or (stop is not None and stop(n)):
            return n, trace
        art = TRD._claim_reviewer(d, n["phase"], respond(n["phase"], n["payload"], n["round"]))
        sub = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], art)
        assert sub["ok"], sub
    raise AssertionError("the session did not reach a terminal in %d steps" % max_steps)


def _session(tmp_path, respond, **kw):
    d, cfg = X._start(tmp_path)
    terminal, trace = _run(d, cfg, respond, **kw)
    return d, terminal, trace


def _at_bounded_audits(tmp_path):
    """A session stopped where the bounded pass's audits are emitted, not yet answered."""
    d, n, _trace = _session(tmp_path, _respond(),
                            stop=lambda n: n["action"] == RD.P_AUDITS and n["round"] == CAP + 1)
    assert n["action"] == RD.P_AUDITS and n["round"] == CAP + 1, n
    return d


def _kinds(state):
    return [dec["kind"] for dec in state["decisions"]]


def _b1_hand_back(state, config, open_ids, held, session_dir=None):
    """What B1's settle did with findings left open before B2 (issue 2554): hand back `round-cap`."""
    parts = []
    if open_ids:
        parts.append("not discharged: %s" % ", ".join(sorted(open_ids)))
    if held:
        parts.append("new issue(s) raised: %s" % "; ".join(str(ni.get("title")) for ni in held))
    pending = RD._pending_owner_rulings(state)
    if pending:
        parts.append("owner guidance recorded but never sent to a fixer: %s" % "; ".join(pending))
    RD._hand_back(state, "round-cap",
                  "Round cap %s reached: the bounded pass audited the cap round's fixes and left "
                  "them open (%s). The PR is handed back with its findings still open; "
                  "certification is withheld." % (CAP, "; ".join(parts)), cap=True)


def _b2_off(monkeypatch):
    """Switch B2's entry off, for a test whose purpose is B1's own hand-back."""
    monkeypatch.setattr(RD, "_begin_bounded_fix", _b1_hand_back)


def _after_cap_verify(trace):
    """The (action, round) pairs emitted after the cap round's last verify gate."""
    verifies = [i for i, (action, rnd) in enumerate(trace) if action == RD.P_VERIFY and rnd == CAP]
    assert verifies, trace
    return trace[verifies[-1] + 1:]


# --- T1: a capped session audits the cap round's fixes with no order ----------------------------------

def test_t1_a_cap_round_with_unaudited_fixes_dispatches_their_audits_in_round_cap_plus_one_with_no_order(
        tmp_path, monkeypatch):
    # axis: the cap round's verify folds into the bounded pass, whose round is the audits and nothing else
    # — see bite-proof record i2552_bounded_pass_b1
    def no_order(*a, **kw):
        raise AssertionError("the pass is automatic: no extra-audit order is made")

    monkeypatch.setattr(RD, "cmd_extra_audit", no_order)
    d, n, trace = _session(tmp_path, _respond(), stop=lambda n: n["round"] > CAP)
    assert (n["action"], n["round"]) == (RD.P_AUDITS, CAP + 1), trace
    assert trace[-2:] == [(RD.P_VERIFY, CAP), (RD.P_AUDITS, CAP + 1)], trace
    state = X._state(d)
    assert state["boundedPass"] == {"trigger": "round-cap", "step": "audit", "rounds": [CAP + 1]}
    assert "extraAudit" not in state and not state.get("terminal")
    assert [t["id"] for t in n["payload"]["targets"]] == RD._fix_batch_keys(state)
    assert "bounded-pass-begun" in _kinds(state)


def test_t1_break_it_without_the_entry_the_cap_round_hands_back_with_its_fixes_unaudited(tmp_path, monkeypatch):
    # axis: A/B — with the entry in `_advance_round` the session audits the fixes; with it removed (neutralized
    # here) the same session hands back `round-cap` with the cap round's fix unaudited — see bite-proof record
    # i2552_bounded_pass_b1
    d, terminal, _trace = _session(tmp_path / "on", _respond())
    final = X._state(d)
    assert "boundedPass" in final and final["round"] == CAP + 1
    assert not (final["decisions"][-1]["kind"] == "round-cap" and RD._fix_batch_keys(final))
    monkeypatch.setattr(RD, "_bounded_pass_applies", lambda state, config: False)
    (tmp_path / "off").mkdir()
    d, terminal, _trace = _session(tmp_path / "off", _respond())
    final = X._state(d)
    assert terminal["payload"]["verdict"] == "handed-back" and final["decisions"][-1]["kind"] == "round-cap"
    assert "boundedPass" not in final and final["round"] == CAP
    assert RD._round_cap(final["config"]) == CAP and final["round"] == CAP
    assert isinstance(final["rounds"][str(CAP)]["fix"], dict) and RD._fix_batch_keys(final)
    assert final["decisions"][-1]["kind"] == "round-cap" and final["decisions"][-1]["round"] == CAP


# --- T2: every fix discharged, nothing Important open: converged `bounded-pass` -----------------------

def test_t2_a_pass_whose_audits_all_discharge_converges_bounded_pass(tmp_path):
    # axis: the pass settles on its own settle, through the one convergence chokepoint — see bite-proof record
    # i2552_bounded_pass_b1
    d, terminal, _trace = _session(tmp_path, _respond())
    assert terminal["payload"]["verdict"] == "converged"
    final = X._state(d)
    assert final["terminal"] == "converged" and final["round"] == CAP + 1
    assert final["certification"]["shape"].startswith("bounded-pass")
    assert final["certification"]["boundedPass"] == {"trigger": "round-cap", "rounds": [CAP + 1]}
    assert final["boundedPass"]["step"] == "done"
    kinds = _kinds(final)
    assert kinds.index("bounded-pass-begun") < kinds.index("bounded-pass-settled") < len(kinds) - 1
    assert kinds[-1] == "converged"
    assert sorted(final["rounds"]) == ["1", "2", "3"]
    rows = X._rows(final, "open-important")
    assert len(rows) == 1 and rows[0]["disposition"] == "fixed", rows
    assert RD._verify_terminal_receipt(d) is None


# --- T3: a fix not discharged: handed back `round-cap`, no round past cap + 1 ------------------------

def test_t3_a_fix_the_pass_does_not_discharge_hands_back_round_cap(tmp_path, monkeypatch):
    # axis: an undischarged audit id keeps the pass from converging — see bite-proof record i2552_bounded_pass_b1
    _b2_off(monkeypatch)  # B1's own hand-back; B2's continuation is `test_bounded_pass_b2_2554.py`
    d, terminal, trace = _session(tmp_path, _respond("not-discharged"))
    assert terminal["payload"]["verdict"] == "handed-back"
    final = X._state(d)
    assert final["terminal"] == "handed-back" and final["decisions"][-1]["kind"] == "round-cap"
    detail = final["decisions"][-1]["detail"]
    assert detail.startswith("Round cap %d reached: the bounded pass audited the cap round's fixes and left "
                             "them open (not discharged: " % CAP), detail
    assert detail.endswith("certification is withheld."), detail
    assert final["certification"]["shape"] is None and final["boundedPass"]["step"] == "done"
    assert final["round"] == CAP + 1 and sorted(final["rounds"]) == ["1", "2", "3"]
    assert max(rnd for _action, rnd in trace) == CAP + 1
    rows = X._rows(final, "open-important")
    assert len(rows) == 1 and rows[0]["disposition"] == "left-for-owner", rows
    again = RD.cmd_next(d)
    assert again["ok"] and again["action"] == RD.P_TERMINAL and X._state(d)["round"] == CAP + 1


# --- T4: a new issue an auditor raises: the one severity rule -----------------------------------------

@pytest.mark.parametrize("severity", ["Minor", "Nit"])
def test_t4_a_minor_or_nit_new_issue_does_not_hold_the_pass_open_and_is_settled(tmp_path, severity):
    # axis: an in-PR new issue holds the pass open unless its severity is exactly Minor or Nit — see bite-proof
    # record i2552_bounded_pass_b1
    d, terminal, _trace = _session(tmp_path, _respond(new_issue=_issue(severity)))
    assert terminal["payload"]["verdict"] == "converged"
    final = X._state(d)
    assert final["certification"]["shape"].startswith("bounded-pass")
    raised = X._rows(final, "raised-by-the-audit")
    assert len(raised) == 1 and raised[0]["disposition"], raised
    assert "_newIssues" not in final


@pytest.mark.parametrize("severity", ["Important", "Critical", MISSING, 3, "minor", "Trivial", None],
                         ids=["important", "critical", "missing", "non-string", "wrong-case", "unknown", "none"])
def test_t4_any_other_severity_holds_the_pass_open_and_hands_back_round_cap(tmp_path, severity, monkeypatch):
    # axis: the severity rule fails closed — a missing, non-string or unknown severity holds the pass open — see
    # bite-proof record i2552_bounded_pass_b1
    _b2_off(monkeypatch)  # B1's own hand-back
    d, terminal, _trace = _session(tmp_path, _respond(new_issue=_issue(severity)))
    assert terminal["payload"]["verdict"] == "handed-back"
    final = X._state(d)
    assert final["decisions"][-1]["kind"] == "round-cap" and "new issue(s) raised" in final["decisions"][-1]["detail"]
    assert final["round"] == CAP + 1 and final["certification"]["shape"] is None


def test_t4_an_important_new_issue_cited_outside_the_pr_goes_to_the_outside_list_and_never_holds_the_pass(tmp_path):
    # axis: a new issue cited outside the lines the PR touched is routed first, whatever its severity — see
    # bite-proof record c3_wo_a_outside
    d, terminal, _trace = _session(tmp_path, _respond(new_issue=_issue("Important", file="elsewhere.py", line=5)))
    assert terminal["payload"]["verdict"] == "converged"
    final = X._state(d)
    assert "elsewhere.py" in json.dumps(final.get("outsideThisPR")), final.get("outsideThisPR")
    assert "raised-by-the-audit" in json.dumps(final["outsideThisPR"]) and not final.get("_newIssues")


# --- T5 (BC-B1): a session saved inside an ordered extra audit round --------------------------------

def test_t5_a_saved_session_inside_an_ordered_extra_round_is_not_handed_back_and_settles_on_the_extra_settle(
        tmp_path):
    # axis: the legacy `extraAudit` round at `cap + 1` is excepted by the load guard and settled by the extra
    # settle — see bite-proof record i2552_bounded_pass_b1
    d, batch = X._ordered(tmp_path)  # built on `X._legacy_extra_round`, the writes the retired verb made
    state = X._state(d)
    assert "boundedPass" not in state and state["extraAudit"]["round"] == CAP + 1 and not state.get("terminal")
    n = RD.cmd_next(d)
    assert n["ok"] and n["action"] == RD.P_AUDITS and [t["id"] for t in n["payload"]["targets"]] == batch, n
    terminal, emitted = X._finish(d, X._respond())
    assert emitted == [RD.P_AUDITS, RD.P_TERMINAL], emitted
    final = X._state(d)
    assert terminal["payload"]["verdict"] == "converged" and final["decisions"][-1]["kind"] == "converged"
    assert not final["certification"]["shape"].startswith("bounded-pass")
    assert "boundedPass" not in final and not {"bounded-pass-begun", "bounded-pass-settled"} & set(_kinds(final))


def test_t5_an_audit_result_submitted_after_the_upgrade_settles_on_the_extra_settle(tmp_path):
    # axis: the extra round's audits, emitted before the upgrade and answered after it, hand back `extra-audit-open`
    d, _batch = X._ordered(tmp_path, extra="not-discharged")  # built on `X._legacy_extra_round`
    assert RD.cmd_next(d)["action"] == RD.P_AUDITS  # the audits were emitted by the earlier release
    terminal, emitted = X._finish(d, X._respond(extra="not-discharged"))
    assert emitted == [RD.P_AUDITS, RD.P_TERMINAL], emitted
    final = X._state(d)
    assert final["terminal"] == "handed-back" and final["decisions"][-1]["kind"] == "extra-audit-open"
    assert "boundedPass" not in final and "bounded-pass-open" not in _kinds(final)


def test_the_extra_audit_verb_refuses_a_session_that_ran_the_bounded_pass(tmp_path):
    # axis: the verb refuses every call with the retired token, so it never writes `extraAudit` into a session
    # holding `boundedPass` — see bite-proof record i2552_bounded_pass_b1
    d, _terminal, _trace = _session(tmp_path, _respond("not-discharged"))
    assert X._state(d)["decisions"][-1]["kind"] == "converged"  # B2 (issue 2554) settles the open finding left-for-owner
    out = RD.cmd_extra_audit(d, str(tmp_path / "order.json"), "advisor", X.PR)
    assert out["ok"] is False and out["reason"] == "extra-audit-retired", out
    assert "extraAudit" not in X._state(d)


# --- T6: the dispatch census ---------------------------------------------------------------------------

@pytest.mark.parametrize("script", ["converges", "not-discharged", "important-new-issue", "minor-new-issue"])
def test_t6_after_the_cap_rounds_verify_only_audits_are_dispatched(tmp_path, script):
    # axis: round `cap + 1` dispatches only `dispatch-audits` over the cap round's fixes: no panel, scoped
    # finder, seams check, verifier, synthesis or `apply-fixes` — see bite-proof record i2552_bounded_pass_b1
    respond = {"converges": _respond(), "not-discharged": _respond("not-discharged"),
               "important-new-issue": _respond(new_issue=_issue("Important")),
               "minor-new-issue": _respond(new_issue=_issue("Minor"))}[script]
    _d, _terminal, trace = _session(tmp_path, respond)
    if script in ("not-discharged", "important-new-issue"):
        # B1 leaves a finding open: the pass continues (issue 2554) with B2's one fix, its gate and its audits
        assert _after_cap_verify(trace) == [(RD.P_AUDITS, CAP + 1), (RD.P_APPLY_FIXES, CAP + 1),
                                            (RD.P_VERIFY, CAP + 1), (RD.P_AUDITS, CAP + 2),
                                            (RD.P_TERMINAL, CAP + 2)], trace
        return
    assert _after_cap_verify(trace) == [(RD.P_AUDITS, CAP + 1), (RD.P_TERMINAL, CAP + 1)], trace


# --- T7: every other ending is unchanged -------------------------------------------------------------

def test_t7_a_cap_round_with_no_unaudited_fix_still_hands_back_round_cap_with_no_pass(tmp_path):
    # a stall found in the cap round holds no fix of that round: nothing is unaudited, so no pass begins
    cap = 4
    d, cfg = X._start(tmp_path, cap)
    terminal, _trace = _run(d, cfg, X._respond(cap=cap, scoped={2: [X._finding("late")]}, fail_titles=("late",)))
    final = X._state(d)
    assert terminal["payload"]["verdict"] == "handed-back" and final["decisions"][-1]["kind"] == "round-cap"
    assert "fix" not in final["rounds"]["4"] and final["round"] == cap
    assert "boundedPass" not in final and "bounded-pass-begun" not in _kinds(final)


def test_t7_the_advance_without_a_fix_batch_at_the_cap_hands_back_and_begins_no_pass():
    state = RD.new_state(TRD._cfg())
    state["round"] = 4
    assert RD._advance_round(state, state["config"], reason="test") is False
    assert state["decisions"][-1]["kind"] == "round-cap" and "boundedPass" not in state and state["round"] == 4


def test_t7_a_pass_that_would_converge_over_an_owner_choice_still_hands_back_owner_choice_open(
        tmp_path, monkeypatch):
    # axis: the one convergence chokepoint still holds a finding the owner must choose on — see bite-proof record c1l4_wo_a
    monkeypatch.setattr(RD, "_unsettled_owner_choices", lambda state: [("k", "a trade-off")])
    d, terminal, _trace = _session(tmp_path, _respond())
    final = X._state(d)
    assert terminal["payload"]["verdict"] == "handed-back" and final["decisions"][-1]["kind"] == "owner-choice-open"
    assert final["boundedPass"]["step"] == "done"


def _above_cap(tmp_path, **keys):
    d = str(tmp_path)
    assert RD.cmd_next(d, TRD._cfg(maxRounds=CAP))["ok"]
    state = X._state(d)
    state["round"] = CAP + 1
    state["step"] = RD.P_VERIFY  # a later round has no panel to wait at
    state["pending"] = None
    state.update(keys)
    RD.save_state(d, state)
    out = RD.cmd_next(d)
    assert out["ok"] and out["phase"] == RD.P_TERMINAL, out
    return X._state(d)


def test_t7_a_loaded_state_above_its_cap_with_neither_pass_still_hands_back_round_cap(tmp_path):
    final = _above_cap(tmp_path)
    assert final["terminal"] == "handed-back" and final["decisions"][-1]["kind"] == "round-cap"


@pytest.mark.parametrize("bounded", [
    "yes",
    {"trigger": "round-cap", "step": "audit", "rounds": "3"},
    {"trigger": "round-cap", "step": "audit", "rounds": ["3"]},
    {"trigger": "round-cap", "step": "audit", "rounds": [True]},
    {"trigger": "round-cap", "step": "audit", "rounds": [CAP + 2]},
    {"trigger": "round-cap", "step": "audit"},
], ids=["not-a-dict", "rounds-a-string", "rounds-strings", "rounds-bool", "another-round", "no-rounds"])
def test_a_malformed_bounded_pass_is_not_a_bounded_round_and_the_load_guard_hands_back_round_cap(tmp_path, bounded):
    # axis: `boundedPass` is a bounded round only as a record whose `rounds` is a list of plain ints holding the
    # round — see bite-proof record i2552_bounded_pass_b1
    final = _above_cap(tmp_path, boundedPass=bounded)
    assert final["terminal"] == "handed-back" and final["decisions"][-1]["kind"] == "round-cap"


def test_a_saved_state_inside_a_real_bounded_pass_is_not_handed_back_on_load(tmp_path):
    # axis: the load guard excepts round `cap + 1` for the bounded pass's round — see bite-proof record i2552_bounded_pass_b1
    d = _at_bounded_audits(tmp_path)
    out = RD.cmd_next(d)
    assert out["ok"] and out["action"] == RD.P_AUDITS and out["round"] == CAP + 1, out
    assert not X._state(d).get("terminal")


# --- owner guidance no fixer received holds the pass open --------------------------------------------

def _guided_bounded_pass(tmp_path, ruled):
    """A session stopped at the bounded pass's audits; with `ruled`, a guidance ruling on the round-1 finding
    (fixed and audited long before, so outside the pass's audit targets) is recorded before the audits, which
    then all discharge. The terminal `next` answer and the final state."""
    d = _at_bounded_audits(tmp_path)
    targets = RD._fix_batch_keys(X._state(d))
    assert X._RULED_KEY not in targets, targets
    if ruled:
        path = X.TOC._write_rulings(tmp_path / "rulings.json", [
            {"id": X._RULED_KEY, "ruling": "guidance", "reason": "the owner wants it handled this way",
             "guidance": "keep the public signature as it is"}])
        out = RD.cmd_rule(d, path, "owner")
        assert out.get("ok"), out
    n, trace = _run(d, None, _respond())
    assert [a for a, rnd in trace if rnd > CAP] == [RD.P_AUDITS, RD.P_TERMINAL], trace
    return n, X._state(d)


def test_a_guidance_ruling_no_fixer_received_hands_the_bounded_pass_back_round_cap(tmp_path, monkeypatch):
    # axis: owner guidance recorded but never sent to a fixer holds the bounded pass open, so it hands back
    # round-cap instead of converging — see bite-proof record i2552_bounded_pass_b1
    _b2_off(monkeypatch)  # B1's own hand-back; B2 sends the ruled finding to its fixer (test_bounded_pass_b2_2554.py)
    _n, final = _guided_bounded_pass(tmp_path, ruled=True)
    assert final["terminal"] == "handed-back", final.get("certification")
    last = final["decisions"][-1]
    assert last["kind"] == "round-cap", last
    assert "owner guidance recorded but never sent to a fixer" in last["detail"], last
    assert final["certification"]["shape"] is None


def test_the_same_bounded_pass_without_the_ruling_converges(tmp_path):
    _n, final = _guided_bounded_pass(tmp_path, ruled=False)
    assert final["terminal"] == "converged", final.get("certification")
    assert final["certification"]["shape"].startswith("bounded-pass")


# --- the state holding both post-cap rounds ----------------------------------------------------------

BOTH = "the session holds both an ordered extra audit round and a bounded pass"


def test_a_state_holding_both_rounds_is_handed_back_bounded_pass_open_on_load(tmp_path):
    # axis: the load guard excepts exactly one of the two post-cap rounds, never both — see bite-proof record i2552_bounded_pass_b1
    d = _at_bounded_audits(tmp_path)
    state = X._state(d)
    state["extraAudit"] = {"why": "x", "round": CAP + 1}
    RD.save_state(d, state)
    out = RD.cmd_next(d)
    assert out["ok"] and out["action"] == RD.P_TERMINAL, out
    final = X._state(d)
    assert final["terminal"] == "handed-back" and final["decisions"][-1]["kind"] == "bounded-pass-open"
    assert final["decisions"][-1]["detail"] == BOTH and final["certification"]["shape"] is None


def test_a_state_holding_both_rounds_never_converges_at_the_audit_settle(tmp_path):
    d = _at_bounded_audits(tmp_path)
    state = X._state(d)
    state["extraAudit"] = {"why": "x", "round": CAP + 1}
    state["_auditOutcome"] = {"notDischarged": []}
    RD._after_audits(state, state["config"], session_dir=d)
    assert state["terminal"] == "handed-back" and state["decisions"][-1]["kind"] == "bounded-pass-open"
    assert state["decisions"][-1]["detail"] == BOTH


# --- the settle's own faults ---------------------------------------------------------------------------

def _settled(tmp_path, outcome, issues):
    d = _at_bounded_audits(tmp_path)
    state = X._state(d)
    state["_auditOutcome"] = outcome
    state["_newIssues"] = issues
    RD._settle_bounded_audit(state, state["config"], session_dir=d)
    return state


@pytest.mark.parametrize("outcome", [None, "garbage", {}, {"notDischarged": "x"}, {"notDischarged": [1]}],
                         ids=["none", "not-a-dict", "no-list", "list-a-string", "non-string-id"])
def test_an_unreadable_audit_outcome_hands_back_bounded_pass_open_and_never_converges(tmp_path, outcome):
    state = _settled(tmp_path, outcome, [])
    assert state["terminal"] == "handed-back" and state["decisions"][-1]["kind"] == "bounded-pass-open"
    assert "the audit outcome is unreadable" in state["decisions"][-1]["detail"]
    assert state["boundedPass"]["step"] == "done"


@pytest.mark.parametrize("stray", ["a string", 3, None, ["x"]], ids=["string", "int", "none", "list"])
def test_a_new_issue_entry_that_is_not_a_record_hands_back_bounded_pass_open(tmp_path, stray):
    state = _settled(tmp_path, {"notDischarged": []}, [_issue("Minor"), stray])
    assert state["terminal"] == "handed-back" and state["decisions"][-1]["kind"] == "bounded-pass-open"
    assert "not a record" in state["decisions"][-1]["detail"]


def test_a_clean_outcome_with_a_minor_issue_the_settle_converges(tmp_path):
    state = _settled(tmp_path, {"notDischarged": []}, [_issue("Minor")])
    assert state["terminal"] == "converged" and state["certification"]["shape"].startswith("bounded-pass")
    assert _kinds(state)[-2:] == ["bounded-pass-settled", "converged"]


def test_a_stall_in_round_cap_plus_one_hands_back_round_cap_with_no_fix_leg(tmp_path):
    # `_after_audits` settles the pass before `_settle_delta` (the only caller of `_handle_stall`) runs, so no
    # session reaches a stall there; the guard is pinned on the function itself
    d = _at_bounded_audits(tmp_path)
    state = X._state(d)
    RD._handle_stall(state, state["config"], {"detail": "audit-stall in round %d" % (CAP + 1)})
    assert state["terminal"] == "handed-back" and state["decisions"][-1]["kind"] == "round-cap"
    assert state["step"] == RD.P_TERMINAL and not state.get("selfRecovered")
    assert RD.P_APPLY_FIXES not in (state["step"], (state.get("pending") or {}).get("action"))


# --- T8: the record ------------------------------------------------------------------------------------

def _rounds(**bounded):
    return {"count": 3, "cap": 4, "stoppedAtCap": True, "boundedPass": bounded}


@pytest.mark.parametrize("bounded", [{"trigger": "round-cap", "rounds": [5]},
                                     {"trigger": "fix-keeps-failing", "rounds": [3, 4]}])
def test_t8_the_validator_accepts_a_bounded_pass_with_the_fixed_keys(bounded):
    # axis: `rounds.boundedPass` is a fixed-key record of a known trigger and a non-empty list of ints — see bite-proof record i2552_bounded_pass_b1
    RR._validate(TRR.account(rounds=_rounds(**bounded)))


@pytest.mark.parametrize("bounded", [
    {"trigger": "round-cap", "rounds": [5], "why": "x"},
    {"trigger": "round-cap"},
    {"rounds": [5]},
    {"trigger": "advisor", "rounds": [5]},
    {"trigger": None, "rounds": [5]},
    {"trigger": "round-cap", "rounds": []},
    {"trigger": "round-cap", "rounds": [True]},
    {"trigger": "round-cap", "rounds": ["5"]},
    {"trigger": "round-cap", "rounds": 5},
], ids=["extra-key", "no-rounds", "no-trigger", "bad-trigger", "null-trigger", "empty-rounds", "bool-round",
        "string-round", "rounds-not-a-list"])
def test_t8_the_validator_refuses_a_bounded_pass_that_is_not_the_fixed_shape(bounded):
    with pytest.raises(RR.Refusal) as refused:
        RR._validate(TRR.account(rounds=_rounds(**bounded)))
    assert refused.value.reason == "review-account-invalid" and refused.value.detail == "rounds.boundedPass"


def test_t8_a_bounded_pass_that_is_not_a_record_is_refused():
    acct = TRR.account(rounds={"count": 3, "cap": 4, "stoppedAtCap": True, "boundedPass": "yes"})
    with pytest.raises(RR.Refusal) as refused:
        RR._validate(acct)
    assert refused.value.detail == "rounds.boundedPass"


def test_t8_a_converged_bounded_pass_session_is_labelled_not_counted_and_stopped_at_the_cap(tmp_path):
    # axis: the pass's round is never counted and a converged pass kept the cap — see bite-proof record i2552_bounded_pass_b1
    d, _terminal, _trace = _session(tmp_path / "run", _respond())
    final = X._state(d)
    account = X._account(tmp_path, final)
    assert account["rounds"]["count"] == CAP and account["rounds"]["stoppedAtCap"] is True
    assert account["rounds"]["boundedPass"] == {"trigger": "round-cap", "rounds": [CAP + 1]}
    RR._validate(account)
    line = RR._bounded_pass_line(account["rounds"])
    assert "audited in round %d" % (CAP + 1) in line and "not counted" in line


def test_t8_a_handed_back_bounded_pass_session_is_stopped_at_the_cap_and_not_counted(tmp_path, monkeypatch):
    _b2_off(monkeypatch)  # a handed-back pass is B1's own hand-back now
    d, _terminal, _trace = _session(tmp_path / "run", _respond("not-discharged"))
    account = X._account(tmp_path, X._state(d))
    assert account["rounds"]["count"] == CAP and account["rounds"]["stoppedAtCap"] is True
    assert account["rounds"]["boundedPass"]["rounds"] == [CAP + 1]
    RR._validate(account)


def test_t8_every_round_the_pass_lists_is_left_out_of_the_count_once(tmp_path):
    d, _terminal, _trace = _session(tmp_path / "run", _respond())
    state = copy.deepcopy(X._state(d))
    state["rounds"]["4"] = copy.deepcopy(state["rounds"]["3"])
    state["boundedPass"]["rounds"] = [3, 4]
    account = X._account(tmp_path, state)
    assert account["rounds"]["count"] == 2 and account["rounds"]["boundedPass"]["rounds"] == [3, 4]
    state["extraAudit"] = {"why": "x", "round": 3}  # a round both labels name is left out once
    assert X._account(tmp_path / "again", state)["rounds"]["count"] == 2


def test_t8_a_session_with_no_pass_carries_no_bounded_pass_key(tmp_path):
    d, cfg = X._start(tmp_path)
    terminal, _trace = _run(d, cfg, X._respond(findings=False))
    assert terminal["payload"]["verdict"] == "converged"
    account = X._account(tmp_path, X._state(d))
    assert "boundedPass" not in account["rounds"] and account["rounds"]["stoppedAtCap"] is False


# --- the pass begins only on fixes the fixer applied; a never-converging loop runs no round past cap + 1 -----

def _rearm_state(seams, cap):
    result, state = TRD._run_loop_capturing_state(seams, TRD._cfg_cert(maxRounds=cap))
    return result, state


def test_t9_a_cap_round_whose_fixer_applied_nothing_hands_back_round_cap_with_no_pass(tmp_path):
    # axis: the pass begins only on applied work: a batch queued with no reported fix, no commit, no PR-body fix
    # and a head diff the fixer left as it was hands back, and no round begins past the cap — see bite-proof
    # record i2552_bounded_pass_b1 (E-applied). The world is the never-converging loop of
    # `_rearm_forever_seams`, whose fixer reports no fixes; its cap round's fixer returns the head diff the
    # round before left (`_headf_ns(cap - 1)`, the cap round's reviewed diff), so the head stays put.
    cap = 4
    seams = TRD._rearm_forever_seams()
    queued = seams["fix_step"]

    def head_unchanged_at_the_cap(batch, rnd, payload):
        out = queued(batch, rnd, payload)
        if rnd == cap:
            out["headDiff"] = TRD._headf_ns(cap - 1)
        return out

    seams["fix_step"] = head_unchanged_at_the_cap
    result, state = _rearm_state(seams, cap)
    assert result["verdict"] == "handed-back" and state["decisions"][-1]["kind"] == "round-cap"
    assert state["round"] == cap and state["rounds"][str(cap)]["fix"]["fixes"] == []
    assert not state["rounds"][str(cap)]["fix"].get("commits")
    assert state["headDiff"] == state["reviewedDiff"], "the cap round's fixer left the head where it was"
    assert "boundedPass" not in state and "bounded-pass-begun" not in _kinds(state)
    assert max(int(n) for n in state["rounds"]) == cap


def test_t10_a_cap_round_that_committed_a_fix_but_reported_no_fixes_enters_the_pass(tmp_path, monkeypatch):
    # axis: the pass begins on the cap round's fix commits, not only its reported fixes: a session that committed
    # a fix and reported an empty fixes list still gets its audit — see bite-proof record i2552_bounded_pass_b1
    # (E-applied-work). The submit chokepoint records a commit only beside a `fixes` binding, so the cap round's
    # verified commit facts are injected at `_apply_fixes_commit_fault`; the session answers an empty `fixes`.
    real = RD._apply_fixes_commit_fault

    def committed_in_the_cap_round(state, config, artifact, commit_seam=None):
        if state.get("round") == CAP:
            return None, [{"finding": "open-important", "commit": "abc1234"}]
        return real(state, config, artifact, commit_seam=commit_seam)

    monkeypatch.setattr(RD, "_apply_fixes_commit_fault", committed_in_the_cap_round)
    d, n, trace = _session(tmp_path, X._respond(cap=CAP), stop=lambda n: n["round"] > CAP)
    state = X._state(d)
    cap_fix = state["rounds"][str(CAP)]["fix"]
    assert cap_fix["fixes"] == [] and cap_fix["commits"], cap_fix
    assert (n["action"], n["round"]) == (RD.P_AUDITS, CAP + 1), trace
    assert state["boundedPass"] == {"trigger": "round-cap", "step": "audit", "rounds": [CAP + 1]}
    assert "bounded-pass-begun" in _kinds(state)


def _committing_respond(checkout):
    """`_respond()`, except that the cap round's fixer commits a real (non-restore) code change in the session's
    git checkout and answers an empty fixes list with the post-fix head diff: no binding, so the submit chokepoint
    records no fix commit, and only the head diff shows the work."""
    base = _respond()

    def respond(phase, payload, rnd):
        if phase == RD.P_APPLY_FIXES and rnd == CAP:
            with open(os.path.join(checkout, "fixed_module.py"), "w", encoding="utf-8") as fh:
                fh.write("FIXED = True\n")
            SC._git(checkout, "add", "-A")
            SC._git(checkout, "commit", "-q", "-m", "fix the open finding")
            return {"fixes": [], "headDiff": TRD._headf_ns(CAP), "changedSubjects": ["Code"]}
        return base(phase, payload, rnd)

    return respond


def test_t11_a_cap_round_that_committed_a_fix_with_no_binding_enters_the_pass(tmp_path):
    # axis: the pass begins on a head diff that changed in the cap round: a session that committed a fix, bound
    # none and reported an empty fixes list leaves both record lists empty, and only the head diff shows the
    # fix — see bite-proof record i2552_bounded_pass_b1 (E-head-diff)
    checkout = str(tmp_path / "checkout")
    d, n, trace = _session(tmp_path, _committing_respond(checkout), stop=lambda n: n["round"] > CAP)
    state = X._state(d)
    cap_fix = state["rounds"][str(CAP)]["fix"]
    assert cap_fix["fixes"] == [] and not cap_fix.get("commits"), cap_fix
    # the session checkout holds its base commit and the fix commit
    assert SC._git(checkout, "rev-list", "--count", "HEAD").stdout.strip() == "2"
    assert (n["action"], n["round"]) == (RD.P_AUDITS, CAP + 1), trace
    assert state["boundedPass"] == {"trigger": "round-cap", "step": "audit", "rounds": [CAP + 1]}
    assert "bounded-pass-begun" in _kinds(state)


def test_t11_break_it_without_the_head_diff_signal_the_same_session_hands_back_round_cap(tmp_path, monkeypatch):
    # axis: A/B — the same session (a commit, no binding, an empty fixes list) enters the pass with the head-diff
    # signal and hands back `round-cap` with it removed (neutralized here) — see bite-proof record
    # i2552_bounded_pass_b1 (E-head-diff)
    monkeypatch.setattr(RD, "_head_diff_changed", lambda state: False)
    checkout = str(tmp_path / "checkout")
    d, terminal, _trace = _session(tmp_path, _committing_respond(checkout))
    final = X._state(d)
    assert terminal["payload"]["verdict"] == "handed-back" and final["decisions"][-1]["kind"] == "round-cap"
    assert "boundedPass" not in final and final["round"] == CAP


@pytest.mark.parametrize("reviewed,head,expected", [
    (TRD.DIFF, TRD.HEAD, True),
    (TRD.DIFF, TRD.DIFF, False),
    (None, TRD.HEAD, False),
    (TRD.DIFF, None, False),
    (TRD.DIFF, 5, False),
    (3, TRD.HEAD, False),
], ids=["differs", "equal", "reviewed-missing", "head-missing", "head-not-text", "reviewed-not-text"])
def test_t11_the_head_diff_signal_needs_both_diffs_as_text_and_unequal(reviewed, head, expected):
    state = _capped_state(fix={"fixes": [], "commits": []})
    state["reviewedDiff"], state["headDiff"] = reviewed, head
    assert RD._bounded_pass_applies(state, state["config"]) is expected


def _capped_state(**record):
    """A state at its cap holding a queued fix batch and a cap round record of `record`."""
    state = RD.new_state(TRD._cfg(maxRounds=CAP))
    state["round"] = CAP
    state["fixBatch"] = [X._finding("queued")]
    state["rounds"] = {str(CAP): record}
    return state


def test_t10_a_cap_round_whose_only_applied_work_is_a_changed_pr_body_fix_enters_the_pass():
    # axis: a PR-body-only fix (empty fixes, no commits) is applied work. The test world's fixer cannot stage a PR
    # body end to end, so the predicate is tested directly on a built state — see bite-proof record
    # i2552_bounded_pass_b1 (E-applied-work)
    state = _capped_state(fix={"fixes": [], "commits": []}, prBodyFix={"before": "old body", "after": "new body"})
    assert RD._bounded_pass_applies(state, state["config"]) is True


@pytest.mark.parametrize("record", [
    {"fix": {"fixes": [], "commits": []}},
    {"fix": {"fixes": None}},
    {"fix": {}},
    {"fix": "not-a-dict"},
    {"fix": {"fixes": [], "commits": []}, "prBodyFix": {"before": "same", "after": "same"}},
    {"fix": {"fixes": [], "commits": []}, "prBodyFix": {"before": "old", "after": ""}},
    {"fix": {"fixes": [], "commits": []}, "prBodyFix": {"before": "old", "after": None}},
    {"fix": {"fixes": [], "commits": []}, "prBodyFix": {"before": "old"}},
    {"fix": {"fixes": [], "commits": []}, "prBodyFix": "not-a-dict"},
], ids=["empty-lists", "fixes-none", "empty-fix", "fix-not-a-dict", "body-unchanged", "body-after-empty",
        "body-after-none", "body-after-missing", "body-not-a-dict"])
def test_t10_a_cap_round_that_applied_none_of_the_three_hands_back_with_no_pass(record):
    state = _capped_state(**record)
    assert RD._bounded_pass_applies(state, state["config"]) is False


@pytest.mark.parametrize("record", [{"fix": {"fixes": [], "commits": ["c1"]}}, {"fix": {"fixes": ["note"]}},
                                    {"fix": {"commits": "malformed-but-truthy"}}],
                         ids=["commits", "fixes", "malformed-truthy-commits"])
def test_t10_fixes_or_commits_are_read_by_truthiness_as_the_vendor_work_reading_does(record):
    state = _capped_state(**record)
    assert RD._bounded_pass_applies(state, state["config"]) is True
    rec = dict(record, fixerVendor="claude")
    assert RD._vendor_did_fix_work({"rounds": {"1": rec}}, {}, "claude") is True


def test_t10_a_missing_cap_round_record_is_not_applied_work():
    state = _capped_state()
    state["rounds"] = {}
    assert RD._bounded_pass_applies(state, state["config"]) is False
    assert RD._round_applied_work(None) is False


def test_t9_the_never_converging_loop_with_the_pass_on_runs_no_round_past_cap_plus_one(tmp_path):
    # the fixer now reports an applied fix each round, so the pass begins: the one round past the cap
    cap = 4
    seams = TRD._rearm_forever_seams()
    queued = seams["fix_step"]

    def applying(batch, rnd, payload):
        out = queued(batch, rnd, payload)
        out["fixes"] = [{"note": "fixed the open finding in round %d" % rnd}]
        return out

    seams["fix_step"] = applying
    _result, state = _rearm_state(seams, cap)
    assert state["boundedPass"]["rounds"] == [cap + 1] and state["round"] == cap + 1
    assert max(int(n) for n in state["rounds"]) == cap + 1
    assert max(seams["_legRnds"]["fix"] + seams["_legRnds"]["verify"]) == cap
    assert state["terminal"]

