"""The bounded pass's B2 (issue 2554, layer 3): after B1, or at the post-recovery `fix-keeps-failing` stall, the open
Important findings go to one fix batch under a bounded queue policy, then one more audit round through the pass's own
round writer. What that audit leaves uncleared settles `left-for-owner` with its evidence before the break-it kept
check, and the session ends `converged`, shape `bounded-pass`.

The invariant: a bounded pass runs at most one fix step (B2's `apply-fixes`) and at most two audit rounds (B1's and
B2's); nothing else runs past the cap. Every pass path ends `converged` / `bounded-pass`, `owner-choice-open`, a
`halted` verify failure, or `bounded-pass-open` (a fault of the pass itself).

Drives the real round driver through the CLI functions on a session directory (the helpers of
`test_bounded_pass_b1_2552`), and the folds directly on a built state where the world is a break-it test or a fix
group.

Bite-proof record: i2554_bounded_pass_b2
"""
import copy
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import test_bounded_pass_b1_2552 as B1  # noqa: E402
import test_c1l10b_test_restore as TR  # noqa: E402
import test_c1l4b_extra_audit as X  # noqa: E402
import test_fix_groups_c1l11c as FG  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD
CAP = X.CAP
ALLOWED = {RD.P_AUDITS, RD.P_APPLY_FIXES, RD.P_VERIFY, RD.P_TERMINAL}


# --- scripted sessions ----------------------------------------------------------------------------------

def _by_round(answers, base=None):
    """`B1._respond()`'s answers, except that the audits of the rounds in `answers` answer
    `(outcome, new_issue)` and every other audit past the cap discharges."""
    base = base or B1._respond()

    def respond(phase, payload, rnd):
        if phase == RD.P_AUDITS and rnd in answers:
            outcome, issue = answers[rnd]
            return B1._audit_answer(payload, outcome, issue)
        return base(phase, payload, rnd)

    return respond


B1_OPEN = {CAP + 1: ("not-discharged", None)}  # B1 leaves the cap round's fix open; B2's audit then discharges


def _b2_run(tmp_path, answers, **kw):
    d, terminal, trace = B1._session(tmp_path, _by_round(answers), **kw)
    return d, terminal, trace, X._state(d)


def _after_trigger(trace, trigger_audit):
    """The (action, round) pairs emitted after the trigger round's last audit emission."""
    at = max(i for i, row in enumerate(trace) if row == trigger_audit)
    return trace[at + 1:]


def _census(after):
    actions = [action for action, _rnd in after]
    assert set(actions) <= ALLOWED, after
    assert actions.count(RD.P_APPLY_FIXES) <= 1, after
    assert len({rnd for action, rnd in after if action == RD.P_AUDITS}) <= 2, after


def _ledger_row(state, key):
    rows = [e for e in state[RD.session_contract.DISPOSITION_LEDGER_KEY] if RD._finding_identity_key(e) == key]
    assert len(rows) == 1, (key, state[RD.session_contract.DISPOSITION_LEDGER_KEY])
    return rows[0]


def _fixed_row(state, title="open-important"):
    rows = X._rows(state, title)
    assert len(rows) == 1, rows
    return rows[0]


# --- T1: B1 leaves a fix undischarged: B2 runs one fix step, its gate and its audits ---------------------

def test_t1_b1_leaves_a_fix_open_then_b2_runs_one_apply_fixes_a_verify_and_the_audits_in_the_next_round(tmp_path):
    # axis: B1's open part begins B2 instead of handing back, and B2's discharge converges `bounded-pass` — see
    # bite-proof record i2554_bounded_pass_b2 (E-b2-entry)
    answers = {CAP + 1: ("not-discharged", None), CAP + 2: ("discharged", None)}
    d, terminal, trace, final = _b2_run(tmp_path, answers)
    assert B1._after_cap_verify(trace) == [(RD.P_AUDITS, CAP + 1), (RD.P_APPLY_FIXES, CAP + 1), (RD.P_VERIFY, CAP + 1),
                                           (RD.P_AUDITS, CAP + 2), (RD.P_TERMINAL, CAP + 2)], trace
    assert terminal["payload"]["verdict"] == "converged" and final["terminal"] == "converged"
    assert final["certification"]["shape"] == "bounded-pass"
    bounded = final["boundedPass"]
    assert (bounded["trigger"], bounded["step"], bounded["rounds"]) == ("round-cap", "done", [CAP + 1, CAP + 2])
    assert isinstance(final["rounds"][str(CAP + 1)]["fix"], dict), "B2's fix leg is round cap + 1's fix leg"
    assert sorted(final["rounds"]) == ["1", "2", "3", "4"]
    row = _fixed_row(final)
    assert row["disposition"] == "fixed" and "boundedPassEvidence" not in row, row
    key = row["findingKey"]
    assert final["certification"]["boundedPass"] == {"trigger": "round-cap", "rounds": [CAP + 1, CAP + 2],
                                                     "fixed": [key], "leftForOwner": []}
    kinds = B1._kinds(final)
    assert kinds.count("bounded-pass-begun") == 2 and kinds[-2:] == ["bounded-pass-settled", "converged"]
    assert RD._verify_terminal_receipt(d) is None


# --- T2: B2 leaves it undischarged: converged with the finding left for the owner ----------------------

def test_t2_b2_leaves_the_finding_open_and_it_is_left_for_the_owner_with_its_evidence_and_no_round_past_cap_plus_2(
        tmp_path):
    # axis: an uncleared B2 target is a `left-for-owner` card with its fix commit and its audit's ruling and reason,
    # and the session still converges — see bite-proof record i2554_bounded_pass_b2 (E-early-settle)
    d, terminal, trace, final = _b2_run(tmp_path, {CAP + 1: ("not-discharged", None), CAP + 2: ("not-discharged", None)})
    assert terminal["payload"]["verdict"] == "converged" and final["terminal"] == "converged"
    assert final["certification"]["shape"] == "bounded-pass"
    row = _fixed_row(final)
    assert row["disposition"] == "left-for-owner" and row["openAtLoopEnd"] is True, row
    evidence = row["boundedPassEvidence"]
    assert evidence["audit"] == {"ruling": "not-discharged", "reasonKind": "wrong", "reason": "still broken"}, evidence
    assert evidence["fixCommit"] == final["rounds"][str(CAP + 1)]["fixFoldHead"] and evidence["fixCommit"], evidence
    assert final["certification"]["boundedPass"]["leftForOwner"] == [row["findingKey"]]
    assert final["certification"]["boundedPass"]["fixed"] == []
    assert max(rnd for _action, rnd in trace) == CAP + 2 and sorted(final["rounds"]) == ["1", "2", "3", "4"]


def test_t2_the_fix_commit_is_the_one_bound_to_the_finding_when_the_fixer_binds_one(tmp_path):
    state = RD.new_state(TRD._cfg(maxRounds=CAP))
    state["round"] = CAP + 2
    finding = X._finding("bound")
    key = RD._finding_key_of(finding)
    state["fixBatch"] = [finding]
    state["rounds"] = {str(CAP + 1): {"fixFoldHead": "head1", "fix": {"fixes": [], "commits": [
        {"finding": key, "commit": "bound-commit"}]}}}
    assert RD._bounded_fix_commit(state, key) == "bound-commit"
    assert RD._bounded_fix_commit(state, "another-key") == "head1"
    state["rounds"][str(CAP + 1)].pop("fixFoldHead")
    assert RD._bounded_fix_commit(state, "another-key") is None


# --- T3: a new issue B2's audit raises ----------------------------------------------------------------

def test_t3_an_important_new_issue_raised_by_b2s_audit_is_left_for_the_owner_a_minor_one_settles_normally(tmp_path):
    # axis: an in-PR new issue of the final audit whose severity is not Minor or Nit is a card; a Minor one is not
    # — see bite-proof record i2554_bounded_pass_b2 (E-early-settle)
    d, terminal, trace, final = _b2_run(tmp_path / "important",
                                        {CAP + 1: ("not-discharged", None), CAP + 2: ("discharged", B1._issue("Important"))})
    assert terminal["payload"]["verdict"] == "converged"
    raised = X._rows(final, "raised-by-the-audit")
    assert len(raised) == 1 and raised[0]["disposition"] == "left-for-owner", raised
    assert raised[0]["boundedPassEvidence"] == {"fixCommit": None, "raisedByFinalAudit": True}
    assert raised[0]["findingKey"] in final["certification"]["boundedPass"]["leftForOwner"]
    d, terminal, trace, final = _b2_run(tmp_path / "minor",
                                        {CAP + 1: ("not-discharged", None), CAP + 2: ("discharged", B1._issue("Minor"))})
    assert terminal["payload"]["verdict"] == "converged"
    raised = X._rows(final, "raised-by-the-audit")
    assert len(raised) == 1 and raised[0]["disposition"] and "boundedPassEvidence" not in raised[0], raised
    assert final["certification"]["boundedPass"]["leftForOwner"] == []


def test_t3_an_important_new_issue_cited_outside_the_pr_goes_to_the_outside_list_not_a_card(tmp_path):
    outside = B1._issue("Important", file="elsewhere.py", line=5)
    d, terminal, trace, final = _b2_run(tmp_path, {CAP + 1: ("not-discharged", None), CAP + 2: ("discharged", outside)})
    assert terminal["payload"]["verdict"] == "converged"
    assert "raised-by-the-audit" in str(final.get("outsideThisPR")) and not X._rows(final, "raised-by-the-audit")


def test_t3_a_new_issue_b1_raised_is_carried_to_b2_as_a_target_and_its_minor_sibling_settles_normally(tmp_path):
    # axis: B1's Important new issue is a B2 target and its Minor sibling is no target and carries no bounded-pass
    # evidence — the Minor row is created by this test (B1's audit raises both), not assumed
    base = _by_round({CAP + 2: ("discharged", None)})

    def respond(phase, payload, rnd):
        if phase == RD.P_AUDITS and rnd == CAP + 1:
            # B1._audit_answer takes one issue, so the round's answer is built here from its result: the Important
            # issue's answer plus a second entry in each result's `newIssues`
            answer = B1._audit_answer(payload, "discharged", B1._issue("Important"))
            for result in answer["results"]:
                result["newIssues"].append(dict(B1._issue("Minor"), title="minor-raised-by-b1"))
            return answer
        return base(phase, payload, rnd)

    d, terminal, trace = B1._session(tmp_path, respond)
    final = X._state(d)
    assert terminal["payload"]["verdict"] == "converged"
    assert (RD.P_APPLY_FIXES, CAP + 1) in trace
    raised = X._rows(final, "raised-by-the-audit")
    assert len(raised) == 1 and raised[0]["disposition"] == "fixed", raised
    minor = X._rows(final, "minor-raised-by-b1")
    assert len(minor) == 1, minor
    # an open Minor is no B2 card: it settles by the terminal settle's normal rule, which leaves a still-open finding
    # `left-for-owner` marked open at loop end, with the terminal settle's own reason and no bounded-pass evidence
    assert minor[0]["disposition"] == "left-for-owner" and minor[0]["openAtLoopEnd"] is True, minor
    assert minor[0]["settledReason"] == "left unfixed when the review loop converged", minor
    assert "boundedPassEvidence" not in minor[0], minor
    assert minor[0]["findingKey"] not in final["certification"]["boundedPass"]["leftForOwner"]
    assert [row["title"] for row in final["fixBatch"]] == ["raised-by-the-audit"], final["fixBatch"]


# --- T4: the fix-keeps-failing trigger ----------------------------------------------------------------

STALL_CAP = 7


def _stall_respond(d, b2="discharged"):
    """`X._respond` with the scoped finder raising `late` in round 2 and every ordinary audit failing it: a stall that
    persists past its one recovery. The audits of the pass's own round answer `b2`."""
    base = X._respond(cap=STALL_CAP, scoped={2: [X._finding("late")]}, fail_titles=("late",))

    def respond(phase, payload, rnd):
        pass_rounds = (X._state(d).get("boundedPass") or {}).get("rounds") or []
        if phase == RD.P_AUDITS and rnd in pass_rounds:
            return B1._audit_answer(payload, b2, None)
        return base(phase, payload, rnd)

    return respond


def _stall_session(tmp_path, b2="discharged", **kw):
    d, cfg = X._start(tmp_path, STALL_CAP)
    terminal, trace = B1._run(d, cfg, _stall_respond(d, b2), **kw)
    return d, terminal, trace, X._state(d)


def test_t4_a_stall_after_the_recovery_begins_the_pass_with_the_stuck_finding_and_its_failed_audits(tmp_path):
    # axis: the post-recovery stall begins the bounded pass instead of the fix-keeps-failing hand-back — see bite-proof
    # record i2554_bounded_pass_b2 (E-stall-entry)
    d, terminal, trace, final = _stall_session(tmp_path)
    assert terminal["payload"]["verdict"] == "converged" and final["terminal"] == "converged"
    bounded = final["boundedPass"]
    assert bounded["trigger"] == "fix-keeps-failing" and len(bounded["rounds"]) == 1 and bounded["step"] == "done"
    r = bounded["rounds"][0] - 1  # the stall was found in round r: its fix leg is the pass's, round r + 1 audits it
    assert r < STALL_CAP and isinstance(final["rounds"][str(r)]["fix"], dict) and "fix-keeps-failing" not in B1._kinds(final)
    assert final["decisions"][-1]["kind"] == "converged" and "self-recovery" in B1._kinds(final)
    assert B1._kinds(final).count("bounded-pass-begun") == 1
    batch = final["fixBatch"]
    assert [row["title"] for row in batch] == ["late"], batch
    failures = batch[0]["auditFailures"]
    assert len(failures) >= 2 and {f["ruling"] for f in failures} == {"not-discharged"}, failures
    assert all(f["reason"] == "still broken" and f["reasonKind"] for f in failures), failures
    assert [row for row in trace if row[1] == r + 1][0] == (RD.P_AUDITS, r + 1)
    assert final["certification"]["boundedPass"]["trigger"] == "fix-keeps-failing"
    assert _fixed_row(final, "late")["disposition"] == "fixed"
    _census(_after_trigger(trace, (RD.P_SCOPED, r)))


def test_t4_the_stuck_finding_b2_does_not_clear_is_left_for_the_owner_with_its_evidence(tmp_path):
    d, terminal, trace, final = _stall_session(tmp_path, b2="not-discharged")
    assert terminal["payload"]["verdict"] == "converged"
    row = _fixed_row(final, "late")
    assert row["disposition"] == "left-for-owner" and row["boundedPassEvidence"]["audit"]["reason"] == "still broken"
    assert max(rnd for _action, rnd in trace) == final["boundedPass"]["rounds"][0]


def test_t4_a_pass_that_finds_a_fix_record_in_round_r_is_a_fault_of_the_pass(tmp_path, monkeypatch):
    real = RD._begin_stall_bounded_pass

    def with_a_fix_record(state, config, breaker, session_dir=None):
        state["rounds"][str(state["round"])]["fix"] = {"fixes": [], "commits": []}
        return real(state, config, breaker, session_dir=session_dir)

    monkeypatch.setattr(RD, "_begin_stall_bounded_pass", with_a_fix_record)
    d, terminal, trace, final = _stall_session(tmp_path)
    assert terminal["payload"]["verdict"] == "handed-back" and final["decisions"][-1]["kind"] == "bounded-pass-open"
    assert "already holds a fix record" in final["decisions"][-1]["detail"]
    assert final["boundedPass"]["step"] == "done" and final["certification"]["shape"] is None
    assert not [row for row in trace if row[0] == RD.P_APPLY_FIXES and row[1] == final["round"]]


def test_t4_the_stuck_findings_failed_audits_of_two_rounds_the_second_at_another_line_are_all_in_its_row_oldest_first():
    state = RD.new_state(TRD._cfg(maxRounds=STALL_CAP))
    state["rounds"] = {
        "3": {"audits": [{"id": "a.py::late@L10", "ruling": "not-discharged", "reasonKind": "wrong", "reason": "first"},
                         {"id": "a.py::other@L10", "ruling": "not-discharged", "reasonKind": "wrong", "reason": "x"}]},
        "2": {"audits": [{"id": "a.py::late@L12", "ruling": "discharged", "reason": "cleared"}]},
        "4": {"audits": [{"id": "a.py::late@L14", "ruling": "not-discharged", "reasonKind": "wrong", "reason": "second"}]},
    }
    failures = RD._audit_failures(state, {"id": "a.py::late@L14", "title": "late"})
    assert [(f["round"], f["reason"]) for f in failures] == [(3, "first"), (4, "second")], failures
    assert RD._audit_failures(state, {"title": "no id"}) == []


def test_t4_a_stall_in_the_cap_round_keeps_the_round_cap_hand_back_with_no_recovery_and_no_pass():
    state = RD.new_state(TRD._cfg(maxRounds=CAP))
    state["round"] = CAP
    RD._handle_stall(state, state["config"], {"detail": "audit-stall in the cap round"})
    assert state["terminal"] == "handed-back" and state["decisions"][-1]["kind"] == "round-cap"
    assert "boundedPass" not in state and not state.get("selfRecovered")


def test_t4_a_stall_whose_batch_cannot_be_composed_keeps_the_fix_keeps_failing_hand_back():
    state = RD.new_state(TRD._cfg(maxRounds=STALL_CAP))
    state["round"], state["selfRecovered"] = 3, True
    RD._handle_stall(state, state["config"], {"detail": "audit-stall persists", "stalledIdentities": []})
    assert state["terminal"] == "handed-back" and state["decisions"][-1]["kind"] == "fix-keeps-failing"
    assert "boundedPass" not in state


# --- T5: the bounded queue policy ---------------------------------------------------------------------

def _policy_state(severities, step="fix", **bounded):
    u = FG._unit(severities=severities)
    if step is not None:
        u.state["boundedPass"] = dict({"trigger": "round-cap", "step": step, "rounds": [CAP + 1]}, **bounded)
    return u


def _queued(u, offer):
    live = {RD._finding_identity_key(r): dict(r) for r in u.state["findings"]}
    status = RD._queue_fix_batch(u.state, u.state["config"], [live[k] for k in offer])
    return status, [RD._finding_identity_key(r) for r in u.state.get("_fixBatch") or []]


def test_t5_a_minor_pulled_in_only_as_a_fix_group_sibling_is_context_never_a_target():
    # axis: the bounded queue policy removes a Minor or Nit that no ruling, stall or restore names, after the fix-group
    # closure — see bite-proof record i2554_bounded_pass_b2 (E-policy)
    u = _policy_state(("Important", "Minor"))
    status, batch = _queued(u, [u.ka])
    assert status == "queued" and batch == [u.ka], batch
    assert u.state["boundedPass"]["contextOnly"] == [{"findingKey": u.kb, "title": u.rows[1]["title"]}]
    detail = [d["detail"] for d in u.state["decisions"] if d["kind"] == "fix-batch-excluded"]
    assert len(detail) == 1 and u.kb in detail[0] and u.rows[1]["title"] in detail[0], detail
    context = RD._bounded_context_block(u.state)
    assert u.rows[1]["title"] in context and u.kb in context and u.rows[0]["title"] not in context
    assert RD._advance(u.state, u.state["config"])["payload"]["batch"][0]["title"] == u.rows[0]["title"]


def test_t5_outside_the_pass_the_same_group_keeps_its_minor_sibling_in_the_batch():
    u = _policy_state(("Important", "Minor"), step=None)
    status, batch = _queued(u, [u.ka])
    assert status == "queued" and sorted(batch) == sorted([u.ka, u.kb])
    u = _policy_state(("Important", "Minor"), step="audit")  # the policy is B2's fix step only
    assert sorted(_queued(u, [u.ka])[1]) == sorted([u.ka, u.kb])


@pytest.mark.parametrize("severity", [None, "Trivial", "minor", 3, "Critical", "Important"],
                         ids=["missing", "unknown", "wrong-case", "non-string", "critical", "important"])
def test_t5_a_sibling_whose_severity_is_not_exactly_minor_or_nit_stays_a_target(severity):
    # axis: the policy fails closed — a missing or unknown severity is a target — see bite-proof record
    # i2554_bounded_pass_b2 (E-policy)
    u = _policy_state(("Important", "Minor"))
    u.state["findings"][1]["severity"] = severity
    if severity is None:
        u.state["findings"][1].pop("severity")
    status, batch = _queued(u, [u.ka])
    assert status == "queued" and sorted(batch) == sorted([u.ka, u.kb]), batch
    assert not u.state["boundedPass"].get("contextOnly")


def test_t5_a_nit_sibling_is_context_too():
    u = _policy_state(("Important", "Nit"))
    assert _queued(u, [u.ka])[1] == [u.ka]


def test_t5_a_pending_owner_guidance_ruling_on_a_minor_makes_it_a_target():
    # axis: a Minor an owner fix or guidance ruling names stays a target, its unruled sibling is context — see
    # bite-proof record i2554_bounded_pass_b2 (E-policy)
    u = _policy_state(("Minor", "Minor"))
    FG._rule_guidance(u.state, u.ka)
    status = RD._queue_fix_batch(u.state, u.state["config"], [])
    batch = [RD._finding_identity_key(r) for r in u.state["_fixBatch"]]
    assert status == "queued" and batch == [u.ka], batch
    assert [c["findingKey"] for c in u.state["boundedPass"]["contextOnly"]] == [u.kb]


@pytest.mark.parametrize("named", ["stuck", "restores"])
def test_t5_a_minor_that_is_the_stalls_stuck_finding_or_whose_audit_found_a_test_mismatch_stays_a_target(named):
    u = _policy_state(("Minor", "Minor"))
    if named == "stuck":
        u.state["boundedPass"]["stuck"] = [u.ka]
    else:
        u.state["boundedPass"]["restores"] = [{"findingKey": u.ka, "path": "t.py", "content": "x", "sha256": "y"}]
    status, batch = _queued(u, [u.ka])
    assert status == "queued" and batch == [u.ka]
    assert [c["findingKey"] for c in u.state["boundedPass"]["contextOnly"]] == [u.kb]


def test_t5_a_batch_with_no_target_after_the_policy_queues_no_step():
    u = _policy_state(("Minor", "Minor"))
    status, _stale = _queued(u, [u.ka])
    assert status == "empty" and u.state["step"] != RD.P_APPLY_FIXES
    assert {c["findingKey"] for c in u.state["boundedPass"]["contextOnly"]} == {u.ka, u.kb}


def test_t5_the_batch_is_never_sliced_past_the_fix_batch_cap():
    # axis: the pass runs one fix step, so two independent findings (no fix group ties them) stay in one batch at a cap
    # of 1 — removing `cap = max(cap, len(filtered))` slices the second into `_fixQueue`
    u = FG._unit(severities=("Important", "Important"), stamp=False)
    u.state["boundedPass"] = {"trigger": "round-cap", "step": "fix", "rounds": [CAP + 1]}
    u.state["config"]["fixBatchCap"] = 1
    status, batch = _queued(u, [u.ka, u.kb])
    assert status == "queued" and sorted(batch) == sorted([u.ka, u.kb]), batch
    assert not u.state.get("_fixQueue")


def test_t5_a_context_only_sibling_an_owner_then_rules_on_is_a_target_and_no_longer_context(tmp_path):
    # axis: a finding the policy keeps as a target is dropped from `contextOnly`, so the fixer's guidance never says
    # "not to be fixed or audited" of a finding the batch asks it to fix
    d, n, _trace = B1._session(tmp_path, _by_round(B1_OPEN),
                               stop=lambda n: (n["action"], n["round"]) == (RD.P_APPLY_FIXES, CAP + 1))
    assert (n["action"], n["round"]) == (RD.P_APPLY_FIXES, CAP + 1), n  # B2's fix step is pending
    state = X._state(d)
    target = state["_fixBatch"][0]
    ka = RD._finding_identity_key(target)
    sibling = X._finding("minor-sibling", severity="Minor", file="sibling.py")
    kb = RD._finding_key_of(sibling)
    sibling["findingKey"] = kb
    group = {"id": "group-of-two", "members": [ka, kb]}
    for row in (state["findings"][0], target, sibling):
        row[RD.verification.FIX_GROUP_FIELD] = dict(group)
    state["findings"].append(sibling)
    ledger = RD._ensure_disposition_ledger_for_write(state)
    RD._seed_ledger_entry(state, ledger, RD._ledger_index_by_key(ledger), copy.deepcopy(sibling), kb, 2)
    state["boundedPass"]["contextOnly"] = [{"findingKey": kb, "title": "minor-sibling"}]  # what the policy left of it
    assert "minor-sibling" in RD._bounded_context_block(state)
    RD.save_state(d, state)
    path = X.TOC._write_rulings(tmp_path / "rulings.json", [
        {"id": kb, "ruling": "guidance", "reason": "owner call", "guidance": "keep the retry behaviour"}])
    out = RD.cmd_rule(d, path, "owner")
    assert out.get("ok"), out
    state = X._state(d)
    assert sorted(RD._finding_identity_key(r) for r in state["_fixBatch"]) == sorted([ka, kb]), state["_fixBatch"]
    assert kb not in [c.get("findingKey") for c in state["boundedPass"]["contextOnly"]], state["boundedPass"]
    context = RD._bounded_context_block(state)
    assert context is None or "minor-sibling" not in context, context


def test_t5_the_empty_batch_rule_converges_with_the_minors_settled_by_the_normal_rule(tmp_path):
    # axis: B1 leaves only an undischarged Minor open: no target after the policy, so no B2 step; the session converges
    # through `_terminal_converged` and the Minor settles by the terminal settle's normal rule — see bite-proof record
    # i2554_bounded_pass_b2 (E-b2-entry)
    w = _bounded_world(tmp_path, "audit", CAP + 1, severity="Minor")
    w.state["_auditTargets"][0].pop("breakIt", None)  # no test comparison owed: the audit answers the three checks only
    results = [{"id": t["id"], "ruling": "not-discharged", "reason": "still broken", "checks": TRD.audit_checks(),
                "auditorVendor": t.get("auditorVendor")} for t in w.state["_auditTargets"]]
    w.fold(RD.P_AUDITS, {"results": results, "collectionManifest": {
        t["id"]: t.get("auditorVendor") for t in w.state["_auditTargets"]}})
    state = w.state
    assert state["terminal"] == "converged" and state["step"] == RD.P_TERMINAL, state.get("certification")
    assert state["boundedPass"]["step"] == "done" and RD.P_APPLY_FIXES not in [d.get("kind") for d in state["decisions"]]
    assert state["certification"]["boundedPass"] == {"trigger": "round-cap", "rounds": [CAP + 1], "fixed": [],
                                                    "leftForOwner": []}
    entry = _ledger_row(state, w.key)
    assert entry["disposition"] and "boundedPassEvidence" not in entry
    assert "fix" not in state["rounds"][str(CAP + 1)], "no B2 step ran"


# --- T6: the mismatch bound ---------------------------------------------------------------------------

def _bounded_world(tmp_path, step, round_no, severity="Important"):
    """A break-it world (a committed test that is not the test reviewer's) inside the bounded pass at `step`."""
    w = TR.World(tmp_path, cap=CAP, round_no=round_no)
    w.state.pop("_verifyThen")
    # a real session's ledger is recognised from its first staged finding; the kept check reads it as such
    w.state[RD.session_contract.DISPOSITION_LEDGER_OWNER_FIELD] = RD.session_contract.DISPOSITION_LEDGER_OWNER_VALUE
    rounds = [CAP + 1] if step == "audit" else [CAP + 1, CAP + 2]
    w.state["boundedPass"] = {"trigger": "round-cap", "step": step, "rounds": rounds}
    for row in [w.finding, *w.state["findings"], *w.state["fixBatch"], *w.state["_auditTargets"]]:
        row["severity"] = severity
    ledger = RD._ensure_disposition_ledger_for_write(w.state)  # the finding was raised, on the ledger, in round 1
    RD._seed_ledger_entry(w.state, ledger, RD._ledger_index_by_key(ledger), copy.deepcopy(w.state["findings"][0]),
                          w.key, 1)
    return w


@pytest.mark.parametrize("severity", ["Important", "Minor"])
def test_t6_a_b1_mismatch_takes_no_restore_step_and_no_second_test_the_restore_rides_b2s_one_apply_fixes(
        tmp_path, severity):
    # axis: a mismatch in B1's audit puts the restore into B2's fix step and the finding into B2's batch, even a Minor
    # — see bite-proof record i2554_bounded_pass_b2 (E-mismatch)
    w = _bounded_world(tmp_path, "audit", CAP + 1, severity)
    w.audit()
    state = w.state
    assert state["rounds"][str(CAP + 1)]["testMismatch"] == [w.key]
    assert RD.TEST_RESTORE_FIELD not in state and state["step"] == RD.P_APPLY_FIXES
    step = w.step()
    assert step["action"] == RD.P_APPLY_FIXES and "restoreOnly" not in step["payload"]
    assert [RD._finding_identity_key(r) for r in step["payload"]["batch"]] == [w.key]
    assert state["boundedPass"]["step"] == "fix"
    restores = RD._bounded_restore_payload(state)
    assert restores == [{"findingKey": w.key, "path": TR.TEST_PATH, "content": TR.ROLE_TEST,
                         "sha256": TR._sha(TR.ROLE_TEST)}], restores
    fields = RD._apply_fixes_payload_fields(str(tmp_path / "session"), state, CAP + 1, 0)
    assert fields["restores"] == restores
    kinds = [d["kind"] for d in state["decisions"]]
    assert "break-it-test-mismatch" in kinds and "break-it-correction-offered" not in kinds
    assert state["step"] != RD.P_SECOND_TEST and RD.TEST_CORRECTION_PENDING_FIELD not in state
    assert state["_auditOutcome"]["notDischarged"] == [w.key]


def _submit_bounded_restore(w):
    """B2's one fix step as a real submission makes it: a commit holding a source repair beside the restored test, a
    report binding the finding to it, checked by the live submission check before it folds."""
    assert w.state["step"] == RD.P_APPLY_FIXES and w.state.get("_fixStepHead"), w.state.get("step")
    w.write("src/repair.py", "def repaired():\n    return True\n")
    w.write(TR.TEST_PATH, TR.ROLE_TEST)
    sha = TR._commit(w.root, "repair the fix and restore the test")
    report = {"fixes": [{"finding": w.key, "commit": sha}]}
    detail, commits = RD._apply_fixes_commit_fault(w.state, w.cfg, report)
    assert detail is None and commits == [{"finding": w.key, "commit": sha}], detail
    w.fold(RD.P_APPLY_FIXES, report)


def test_t6_b2s_fold_records_the_restore_once_and_runs_the_gate_before_its_audits(tmp_path):
    # axis: B2's report that commits a source repair beside the restored test passes the live submission check, so
    # the restore the pass carries can be submitted at all — see bite-proof record i2554_bounded_pass_b2
    # (E-restore-submits)
    w = _bounded_world(tmp_path, "audit", CAP + 1)
    w.audit()
    _submit_bounded_restore(w)  # the one apply-fixes step; its fold is the ordinary fix fold
    state = w.state
    assert state["step"] == RD.P_VERIFY and state["_verifyThen"] == RD.VERIFY_THEN_BOUNDED
    assert state["round"] == CAP + 1 and "restores" not in state["boundedPass"]
    assert [e["findingKey"] for e in state["rounds"][str(CAP + 1)]["testRestore"]] == [w.key]
    assert isinstance(state["rounds"][str(CAP + 1)]["fix"], dict)
    assert RD._bounded_restore_payload(state) == []


def test_t6_a_b2_mismatch_hands_back_bounded_pass_open_with_no_restore_and_no_second_test(tmp_path):
    # axis: a mismatch in B2's audit hands the PR back, so no weakened test is left on a converged head — see
    # bite-proof record i2554_bounded_pass_b2 (E-final-mismatch)
    w = _bounded_world(tmp_path, "final-audit", CAP + 2)
    w.audit()
    state = w.state
    assert state["terminal"] == "handed-back" and state["decisions"][-1]["kind"] == "bounded-pass-open"
    assert "no weakened test is left" in state["decisions"][-1]["detail"] and w.key in state["decisions"][-1]["detail"]
    assert RD.TEST_RESTORE_FIELD not in state and state["step"] == RD.P_TERMINAL
    assert state["boundedPass"]["step"] == "done" and state["certification"]["shape"] is None
    assert "break-it-test-restored" not in [d["kind"] for d in state["decisions"]]


def test_t6_an_ordinary_delta_round_keeps_todays_restore_only_step(tmp_path):
    w = TR.World(tmp_path)
    w.audit()
    step = w.step()
    assert step["payload"]["restoreOnly"] is True and "boundedPass" not in w.state


# --- T7: the early settle (BC-B7) ---------------------------------------------------------------------

def test_t7_an_uncleared_b2_finding_that_carries_a_break_it_test_converges_with_a_card_not_cannot_certify(tmp_path):
    # axis: the leftovers settle before the kept check: without the early settle the unresolved break-it finding parks
    # `cannot-certify` — see bite-proof record i2554_bounded_pass_b2 (E-early-settle)
    w = _bounded_world(tmp_path, "final-audit", CAP + 2)
    w.state["rounds"]["1"] = {"breakItRuns": [{"findingKey": w.key, "path": TR.TEST_PATH, "outcome": "failing"}]}
    targets = w.state["_auditTargets"]
    artifact = {"results": [{"id": t["id"], "ruling": "not-discharged", "reason": "still broken",
                             "checks": TRD.audit_checks(), "auditorVendor": t.get("auditorVendor"),
                             **TRD.audit_test_match(t, "matches")} for t in targets],
                "collectionManifest": {t["id"]: t.get("auditorVendor") for t in targets}}
    w.fold(RD.P_AUDITS, artifact)
    state = w.state
    assert state["terminal"] == "converged", state["certification"]
    row = _ledger_row(state, w.key)
    assert row["disposition"] == "left-for-owner" and row["boundedPassEvidence"]["audit"]["reason"] == "still broken"
    assert state["certification"]["boundedPass"]["leftForOwner"] == [w.key]
    assert state["rounds"][str(CAP + 2)]["breakItKept"][0]["outcome"] == "not-required"


@pytest.mark.parametrize("outcome", [None, "garbage", {}, {"notDischarged": "x"}, {"notDischarged": [1]}],
                         ids=["none", "not-a-dict", "no-list", "list-a-string", "non-string-id"])
def test_t7_an_unreadable_audit_outcome_in_b2s_round_hands_back_bounded_pass_open(tmp_path, outcome):
    # fail closed: nothing is settled, nothing converges
    w = _bounded_world(tmp_path, "final-audit", CAP + 2)
    w.state["_auditOutcome"], w.state["_newIssues"] = outcome, []
    RD._settle_bounded_fix(w.state, w.state["config"], session_dir=str(tmp_path / "s"))
    state = w.state
    assert state["terminal"] == "handed-back" and state["decisions"][-1]["kind"] == "bounded-pass-open"
    assert "the audit outcome is unreadable" in state["decisions"][-1]["detail"]


@pytest.mark.parametrize("severity", [None, "Trivial", "Important", "Critical", 3],
                         ids=["missing", "unknown", "important", "critical", "non-string"])
def test_t7_an_uncleared_target_whose_severity_is_not_exactly_minor_or_nit_is_a_card(tmp_path, severity):
    # fail closed: a missing or unknown severity is a card, never a silent pass
    w = _bounded_world(tmp_path, "final-audit", CAP + 2)
    for row in w.state["_auditTargets"]:
        row["severity"] = severity
    w.state["_auditOutcome"] = {"notDischarged": [w.key], "discharged": [], "audits": [
        {"id": w.key, "ruling": "not-discharged", "reason": "broken", "reasonKind": "wrong"}]}
    w.state["_newIssues"] = []
    RD._settle_bounded_fix(w.state, w.state["config"], session_dir=str(tmp_path / "s"))
    assert w.state["terminal"] == "converged"
    entry = _ledger_row(w.state, w.key)
    assert entry["disposition"] == "left-for-owner" and entry["boundedPassEvidence"]["audit"]["ruling"] == "not-discharged"


def test_t7_an_uncleared_bare_minor_target_settles_by_the_terminal_rule_not_as_a_b2_card(tmp_path):
    w = _bounded_world(tmp_path, "final-audit", CAP + 2)
    for row in w.state["_auditTargets"]:
        row["severity"] = "Minor"
    w.state["_auditOutcome"] = {"notDischarged": [w.key], "discharged": [], "audits": []}
    w.state["_newIssues"] = []
    RD._settle_bounded_fix(w.state, w.state["config"], session_dir=str(tmp_path / "s"))
    assert w.state["terminal"] == "converged" and w.state["certification"]["boundedPass"]["leftForOwner"] == []
    assert "boundedPassEvidence" not in _ledger_row(w.state, w.key)


# --- T8: the dispatch census --------------------------------------------------------------------------

@pytest.mark.parametrize("script", ["b1-only", "b1-then-b2", "b2-open", "b1-important-issue"])
def test_t8_after_the_trigger_rounds_last_verify_only_audits_one_apply_fixes_verify_and_the_terminal_run(
        tmp_path, script):
    # axis: no panel, scoped finder, seams check, verifier, synthesis, second-test or second apply-fixes runs past the
    # cap — see bite-proof record i2554_bounded_pass_b2 (E-b2-entry)
    answers = {"b1-only": {}, "b1-then-b2": {CAP + 1: ("not-discharged", None)},
               "b2-open": {CAP + 1: ("not-discharged", None), CAP + 2: ("not-discharged", None)},
               "b1-important-issue": {CAP + 1: ("discharged", B1._issue("Important"))}}[script]
    _d, _terminal, trace, final = _b2_run(tmp_path, answers)
    after = B1._after_cap_verify(trace)
    _census(after)
    assert max(rnd for _a, rnd in trace) <= CAP + 2
    assert [a for a, _r in after].count(RD.P_APPLY_FIXES) == (0 if script == "b1-only" else 1)
    assert final["terminal"] == "converged"


def test_t8_the_stall_path_runs_only_the_allowed_actions_too(tmp_path):
    _d, _terminal, trace, final = _stall_session(tmp_path)
    r = final["boundedPass"]["rounds"][0] - 1
    # the stall is found in the fold of round r's scoped finder: that round's own audits, gate and finder come first
    after = _after_trigger(trace, (RD.P_SCOPED, r))
    assert [a for a, _r in after] == [RD.P_APPLY_FIXES, RD.P_VERIFY, RD.P_AUDITS, RD.P_TERMINAL], after
    _census(after)


# --- T9: resume at every boundary ---------------------------------------------------------------------

def _reload(d):
    ok, state = RD.load_state(d)
    assert ok
    RD.save_state(d, state)


@pytest.mark.parametrize("boundary", [(RD.P_APPLY_FIXES, CAP + 1), (RD.P_VERIFY, CAP + 1), (RD.P_AUDITS, CAP + 2)],
                         ids=["after-b1-settle", "after-b2-fold", "after-the-verify"])
def test_t9_a_saved_state_reloaded_at_each_boundary_lands_on_the_same_next_action(tmp_path, boundary):
    # axis: every step of the pass is persisted, so a resume lands on the same step — see bite-proof record
    # i2554_bounded_pass_b2 (E-b2-entry)
    answers = {CAP + 1: ("not-discharged", None), CAP + 2: ("discharged", None)}
    respond = _by_round(answers)
    d, n, _trace = B1._session(tmp_path / "run", respond, stop=lambda n: (n["action"], n["round"]) == boundary)
    assert (n["action"], n["round"]) == boundary
    before = X._state(d)
    _reload(d)
    again = RD.cmd_next(d)
    assert again["ok"] and (again["action"], again["round"], again["attempt"]) == (n["action"], n["round"], n["attempt"])
    assert not X._state(d).get("terminal") and X._state(d)["boundedPass"]["step"] == before["boundedPass"]["step"]
    final, trace = B1._run(d, None, respond)
    state = X._state(d)
    assert final["payload"]["verdict"] == "converged" and state["boundedPass"]["rounds"] == [CAP + 1, CAP + 2]
    assert state["certification"]["boundedPass"]["fixed"] == [RD._fix_batch_keys(state)[0]]


def test_t9_a_saved_state_after_b2s_audits_were_emitted_lands_on_them_and_the_load_guard_lets_cap_plus_2_run(tmp_path):
    answers = {CAP + 1: ("not-discharged", None), CAP + 2: ("discharged", None)}
    d, n, _trace = B1._session(tmp_path, _by_round(answers),
                               stop=lambda n: (n["action"], n["round"]) == (RD.P_AUDITS, CAP + 2))
    state = X._state(d)
    assert state["round"] == CAP + 2 and state["boundedPass"]["rounds"] == [CAP + 1, CAP + 2]
    assert state["boundedPass"]["step"] == "final-audit" and not RD._round_above_cap(state, state["config"])
    _reload(d)
    again = RD.cmd_next(d)
    assert again["ok"] and (again["action"], again["round"]) == (RD.P_AUDITS, CAP + 2) and not X._state(d).get("terminal")
    state["extraAudit"] = {"why": "x", "round": CAP + 2}
    assert RD._round_above_cap(state, state["config"]) is True  # the both-rounds state is not excepted
    RD.save_state(d, state)
    out = RD.cmd_next(d)
    final = X._state(d)
    assert out["ok"] and final["decisions"][-1]["kind"] == "bounded-pass-open" and final["decisions"][-1]["detail"] == B1.BOTH


@pytest.mark.parametrize("rounds,expected", [([CAP + 1, CAP + 2], False), ([CAP + 1], True), ([CAP + 3], True)],
                         ids=["both-listed", "only-b1-listed", "not-a-listed-round"])
def test_t9_the_load_guard_excepts_exactly_the_rounds_the_pass_lists(rounds, expected):
    state = RD.new_state(TRD._cfg(maxRounds=CAP))
    state["round"] = CAP + 2
    state["boundedPass"] = {"trigger": "round-cap", "step": "final-audit", "rounds": rounds}
    assert RD._round_above_cap(state, state["config"]) is expected
    state["boundedPass"]["trigger"] = "fix-keeps-failing"  # that trigger's rounds never pass the cap
    assert RD._round_above_cap(state, state["config"]) is True


# --- T10: every other non-converged ending is unchanged -----------------------------------------------

def test_t10_a_held_owner_choice_still_hands_back_owner_choice_open_after_b2(tmp_path, monkeypatch):
    monkeypatch.setattr(RD, "_unsettled_owner_choices", lambda state: [("k", "a trade-off")])
    d, terminal, trace, final = _b2_run(tmp_path, {CAP + 1: ("not-discharged", None), CAP + 2: ("discharged", None)})
    assert terminal["payload"]["verdict"] == "handed-back" and final["decisions"][-1]["kind"] == "owner-choice-open"
    assert final["boundedPass"]["step"] == "done"


def test_t10_a_failing_verify_gate_in_b2_halts_and_runs_no_audits(tmp_path):
    base = _by_round({CAP + 1: ("not-discharged", None)})

    def respond(phase, payload, rnd):
        if phase == RD.P_VERIFY and rnd == CAP + 1:
            return {"result": "fail"}
        return base(phase, payload, rnd)

    d, terminal, trace = B1._session(tmp_path, respond)
    final = X._state(d)
    assert terminal["payload"]["verdict"] == "halted" and final["decisions"][-1]["kind"] == "verify-fail"
    assert (RD.P_AUDITS, CAP + 2) not in trace and final["boundedPass"]["step"] == "fix"


def test_t10_a_ruling_that_leaves_b2s_pending_step_no_target_settles_the_pass_and_clears_the_slice(tmp_path):
    # axis: a ruling that leaves B2's pending step no target clears the stale slice and settles the pass, never a fix
    # step still queued — see bite-proof record i2554_bounded_pass_b2 (E-ruling-empties)
    d, n, _trace = B1._session(tmp_path, _by_round(B1_OPEN),
                               stop=lambda n: (n["action"], n["round"]) == (RD.P_APPLY_FIXES, CAP + 1))
    assert (n["action"], n["round"]) == (RD.P_APPLY_FIXES, CAP + 1), n
    targets = [RD._fix_batch_row_key(row) for row in n["payload"]["batch"]]
    assert len(targets) == 1 and targets[0], n["payload"]["batch"]
    path = X.TOC._write_rulings(tmp_path / "rulings.json", [
        {"id": targets[0], "ruling": "out-of-scope", "reason": "belongs to the next milestone",
         "followUp": X.TOC._follow_up()}])
    out = RD.cmd_rule(d, path, "owner")
    assert out.get("ok"), out
    state = X._state(d)
    assert state["terminal"] == "converged" and state["step"] == RD.P_TERMINAL, state.get("decisions")[-3:]
    assert not state.get("_fixBatch") and "_fixQueue" not in state and not state.get("pending")
    assert state["boundedPass"]["step"] == "done" and B1._kinds(state)[-2:] == ["bounded-pass-settled", "converged"]
    assert "fix" not in state["rounds"][str(CAP + 1)], "no B2 fix step ran"
    again = RD.cmd_next(d)
    assert again["ok"] and again["action"] == RD.P_TERMINAL, again


def test_t10_the_b1_only_pass_and_the_ordinary_session_are_unchanged(tmp_path):
    d, terminal, trace, final = _b2_run(tmp_path, {})
    assert final["certification"]["boundedPass"] == {"trigger": "round-cap", "rounds": [CAP + 1]}
    assert B1._after_cap_verify(trace) == [(RD.P_AUDITS, CAP + 1), (RD.P_TERMINAL, CAP + 1)]
