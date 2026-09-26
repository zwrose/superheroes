"""C13 layer 4d (#1419), part (ii): owner and advisor rulings reach the round driver through one
declared input (`rule --rulings FILE`), are recorded on the round with their provenance, and keep
the acting seat's runner evidence bound to the order the driver emitted."""
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_certification as RC  # noqa: E402
import round_driver as RD  # noqa: E402
import round_records as RR  # noqa: E402
import session_contract as SC  # noqa: E402
import test_layer4c3_audit_proof_1438 as T43  # noqa: E402
import test_round_driver_integration as TRI  # noqa: E402
from test_layer4a_ruling_evidence_1272 import _stub_dispatch_observed_land  # noqa: E402
from test_seat_provenance_1272 import _drive_to_audits  # noqa: E402

PROV = {"ruledBy": "owner", "ruledAt": "2026-09-25T20:00:00Z",
        "records": ["https://example.invalid/ruling"]}
FOLLOW_UP = {"item": "track the adjacent hardening", "revisitTrigger": "next C13 layer",
             "classClosure": "tracked on the parent epic"}
GUIDANCE = "use a sentinel value, not a second bounds check"
FIXER_PAYLOAD = {"fixes": [{"file": TRI.FIXED_FILE, "description": "applied fix"}]}


def _session_at_fixer(tmp_path, name="rule"):
    session_dir, gitdir, head_path = TRI._bootstrap(tmp_path, name=name)
    findings = [TRI._blocking_finding("unchecked index", 2), TRI._blocking_finding("off by one", 3)]
    TRI._drive_to_phase(session_dir, gitdir, findings, head_path, RD.P_FIXER)
    return session_dir


def _keys(rows):
    return [r.get(SC.FINDING_KEY_FIELD) for r in rows]


def _rule(tmp_path, session_dir, rulings, provenance=PROV, name="rulings.json"):
    path = tmp_path / name
    art = {"rulings": rulings}
    if provenance is not None:
        art["_provenance"] = provenance
    path.write_text(json.dumps(art), encoding="utf-8")
    return RD.cmd_rule(session_dir, str(path))


def _order_path(session_dir, pend, seat="fixer"):
    return RR.order_prompt_path(session_dir, pend["round"], pend["phase"], RR.storage_key(seat),
                                pend["attempt"])


def _journal_rows(session_dir, cmd, outcome):
    return [e for e in RD.read_journal(session_dir)
            if e.get("cmd") == cmd and e.get("outcome") == outcome]


def test_out_of_scope_ruling_takes_a_mechanical_finding_out_of_the_fix_batch(tmp_path):
    """The 4c-2 case: a mechanical finding ruled out of scope leaves the batch, with provenance,
    and the emitted order is superseded — the next order is re-rendered at a fresh attempt."""
    d = _session_at_fixer(tmp_path)
    ruled, kept = _keys(TRI._state(d)["_fixBatch"])
    out = _rule(tmp_path, d, [{"id": ruled, "ruling": "out-of-scope",
                               "reason": "belongs to the next layer", "followUp": FOLLOW_UP}])
    assert out["ok"] is True, out
    assert out["superseded"] == {"phase": RD.P_FIXER, "round": 1, "attempt": 0}
    state = TRI._state(d)
    row = next(r for r in state[SC.DISPOSITION_LEDGER_KEY] if r.get(SC.FINDING_KEY_FIELD) == ruled)
    assert row["disposition"] == "out-of-scope" and row["followUp"] == FOLLOW_UP
    assert row[SC.DISPOSITION_SEQ_FIELD] > row[SC.RAISED_SEQ_FIELD]
    rec = state["rounds"]["1"]["rulings"][0]
    assert (rec["id"], rec["ruledBy"], rec["records"]) == (ruled, "owner", PROV["records"])
    assert rec["artifactSha256"] == out["artifactSha256"]
    assert [e["attempt"] for e in _journal_rows(d, RD.RULE_CMD, "orders-superseded")] == [0]
    assert _keys(state["_fixBatch"]) == [kept]
    n = RD.cmd_next(d)
    assert (n["ok"], n["phase"], n["attempt"]) == (True, RD.P_FIXER, 1), n
    with open(os.path.join(RR.round_dir(d, 1), "fix-batch.json"), encoding="utf-8") as fh:
        assert _keys(json.load(fh)) == [kept]


def test_ruling_the_whole_batch_out_never_dispatches_a_fixer(tmp_path):
    d = _session_at_fixer(tmp_path, name="rule-all")
    rulings = [{"id": k, "ruling": "refuted", "reason": "the verifier misread the guard"}
               for k in _keys(TRI._state(d)["_fixBatch"])]
    assert _rule(tmp_path, d, rulings)["ok"] is True
    n = RD.cmd_next(d)
    assert n["ok"] and n["phase"] != RD.P_FIXER, n


def test_ruling_out_a_continuation_slice_enters_post_fix_and_never_redispatches_it(tmp_path):
    """A cap-sliced round: the first slice folded, the second (index 1) is pending. Ruling its only
    finding closed resolves through the continuation leg (post-fix: the round advances to a delta
    round), never the index-0 convergence resolver, and the stale slice is never dispatched."""
    session_dir, gitdir, head_path = TRI._bootstrap(tmp_path, name="rule-cont", fixBatchCap=1)
    findings = [TRI._blocking_finding("unchecked index", 2), TRI._blocking_finding("off by one", 3)]
    TRI._drive_to_phase(session_dir, gitdir, findings, head_path, RD.P_FIXER)
    phase, out = TRI._drive_one_phase(session_dir, gitdir, findings, head_path)
    assert phase == RD.P_FIXER and out["ok"], out
    state = TRI._state(session_dir)
    assert state["_fixBatchIndex"] == 1 and state["step"] == RD.P_FIXER, state.get("step")
    (remaining,) = _keys(state["_fixBatch"])
    assert _rule(tmp_path, session_dir, [{"id": remaining, "ruling": "refuted",
                                          "reason": "the verifier misread the guard"}])["ok"]
    state = TRI._state(session_dir)
    assert not state.get("terminal") and state["round"] == 2, (state.get("step"), state["round"])
    assert "_fixBatchIndex" not in state and "_fixQueue" not in state
    n = RD.cmd_next(session_dir)
    assert n["ok"] and n["phase"] != RD.P_FIXER, n


def test_the_ruling_vocabulary_is_derived_from_the_ledger_and_judgment_homes():
    """Drift pin: every ledger disposition but the audit-only `fixed` is a closing ruling kind with
    a reason field, each ruling kind is the named ledger or judgment token itself, and the ledger
    vocabulary is built from its named tokens."""
    assert SC.DISPOSITIONS == (SC.DISPOSITION_FIXED, SC.DISPOSITION_REFUTED,
                               SC.DISPOSITION_OUT_OF_SCOPE)
    closing = set(SC.DISPOSITIONS) - {SC.DISPOSITION_FIXED}
    assert set(RD.RULING_CLOSING_KINDS) == closing
    assert set(RD.RULING_REASON_FIELDS) == closing, (
        "ruling-reason-field-drift: a ledger disposition has no ruling reason field")
    assert RD.RULING_OUT_OF_SCOPE is SC.DISPOSITION_OUT_OF_SCOPE
    assert RD.RULING_REFUTED is SC.DISPOSITION_REFUTED
    assert RD.RULING_GUIDANCE in RD.JUDGMENT_DISPOSITIONS
    assert set(RD.RULING_KINDS) == closing | {RD.RULING_GUIDANCE}


def test_guidance_ruling_renders_in_the_order_and_the_fixer_evidence_binds(tmp_path):
    """DoD: a fixer acting under a ruling keeps its runner evidence binding. The ruling is in the
    driver-rendered order, so the runner's prompt hash equals the order hash and `record-result`
    — the certification ingest gate, which never re-checks the hash later — stores the seat."""
    d = _session_at_fixer(tmp_path, name="rule-guide")
    key = _keys(TRI._state(d)["_fixBatch"])[1]
    assert _rule(tmp_path, d, [{"id": key, "ruling": "fix-with-guidance",
                                "guidance": GUIDANCE}])["ok"] is True
    n = RD.cmd_next(d)
    assert n["ok"] and n["attempt"] == 1, n
    state = TRI._state(d)
    pend = state["pending"]
    order_path = _order_path(d, pend)
    with open(order_path, encoding="utf-8") as fh:
        assert GUIDANCE in fh.read()
    with open(os.path.join(RR.round_dir(d, 1), "fix-batch.json"), encoding="utf-8") as fh:
        rows = {r[SC.FINDING_KEY_FIELD]: r for r in json.load(fh)}
    assert rows[key]["gateRuling"]["disposition"] == "fix-with-guidance"
    (tmp_path / "ev").mkdir()
    run_dir = TRI._write_execution_run_dir(tmp_path / "ev", order_path)
    _stub_dispatch_observed_land(d, state, pend, "fixer", payload=FIXER_PAYLOAD)
    out = RD.cmd_record_result(d, "fixer", evidence_run_dir=run_dir)
    assert out["ok"] is True, out
    stored, err = RR.read_json(out["storePath"])
    assert err is None and stored["provenance"] == RR.PROVENANCE_DISPATCH_OBSERVED


def test_a_ruling_carried_as_a_prompt_appendix_breaks_the_binding(tmp_path):
    """DoD bite-proof: the same ruling routed around the channel — appended to the emitted order —
    changes the prompt the runner hashes, and `record-result` refuses `evidence-order-mismatch`."""
    d = _session_at_fixer(tmp_path, name="rule-appendix")
    state = TRI._state(d)
    pend = state["pending"]
    with open(_order_path(d, pend), encoding="utf-8") as fh:
        order = fh.read()
    appended = tmp_path / "order-with-appendix.md"
    appended.write_text(order + "\n\nOwner ruling: " + GUIDANCE + "\n", encoding="utf-8")
    (tmp_path / "ev").mkdir()
    run_dir = TRI._write_execution_run_dir(tmp_path / "ev", str(appended))
    _stub_dispatch_observed_land(d, state, pend, "fixer", payload=FIXER_PAYLOAD)
    out = RD.cmd_record_result(d, "fixer", evidence_run_dir=run_dir)
    assert out["ok"] is False and out["reason"] == "evidence-order-mismatch", out


def test_guidance_needs_an_unexecuted_fixer_slice(tmp_path):
    """After the fixer ran, its batch is still in state but no fixer order will render again, so
    guidance would never be acted on: refused."""
    d, _gitdir, _head = _drive_to_audits(tmp_path, name="rule-late")
    key = _keys(TRI._state(d)["fixBatch"])[0]
    out = _rule(tmp_path, d, [{"id": key, "ruling": "fix-with-guidance", "guidance": GUIDANCE}])
    assert out["ok"] is False and out["reason"] == "ruling-entry-invalid", out


def _refusal_cases(ruled):
    good = {"id": ruled, "ruling": "refuted", "reason": "unreachable"}
    return [
        ("unreadable", None, "ruling-artifact-unreadable"),
        ("empty", {"rulings": [], "_provenance": PROV}, "ruling-artifact-shape"),
        ("no-provenance", {"rulings": [good]}, "ruling-provenance-missing"),
        ("bad-provenance", {"rulings": [good], "_provenance": dict(PROV, records=[])},
         "ruling-provenance-missing"),
        ("duplicate", {"rulings": [good, good], "_provenance": PROV}, "ruling-entry-invalid"),
        ("unknown-kind", {"rulings": [dict(good, ruling="skip")], "_provenance": PROV},
         "ruling-entry-invalid"),
        ("no-reason", {"rulings": [dict(good, reason=" ")], "_provenance": PROV},
         "ruling-entry-invalid"),
        ("no-follow-up", {"rulings": [dict(good, ruling="out-of-scope")], "_provenance": PROV},
         "ruling-entry-invalid"),
        ("unknown-target", {"rulings": [dict(good, id="src/nowhere.py::ghost@L9")],
                            "_provenance": PROV}, "ruling-target-unknown"),
        ("later-row-invalid", {"rulings": [good, {"id": "src/nowhere.py::ghost@L9",
                                                  "ruling": "refuted", "reason": "x"}],
                               "_provenance": PROV}, "ruling-target-unknown"),
    ]


def test_every_refusal_is_named_and_folds_nothing(tmp_path):
    d = _session_at_fixer(tmp_path, name="rule-refusals")
    ruled = _keys(TRI._state(d)["_fixBatch"])[0]
    state_path = os.path.join(d, RD.STATE_FILE)
    for name, art, token in _refusal_cases(ruled):
        with open(state_path, "rb") as fh:
            before = fh.read()
        path = tmp_path / ("%s.json" % name)
        path.write_text("{not json" if art is None else json.dumps(art), encoding="utf-8")
        out = RD.cmd_rule(d, str(path))
        assert out["ok"] is False and out["reason"] == token, (name, out)
        with open(state_path, "rb") as fh:
            assert fh.read() == before, "%s changed state" % name


def test_critical_may_not_be_ruled_out_of_scope(tmp_path):
    d = _session_at_fixer(tmp_path, name="rule-critical")
    state = TRI._state(d)
    key = _keys(state["_fixBatch"])[0]
    for row in state[SC.DISPOSITION_LEDGER_KEY]:
        if row.get(SC.FINDING_KEY_FIELD) == key:
            row["severity"] = "Critical"
    RD.save_state(d, state)
    out = _rule(tmp_path, d, [{"id": key, "ruling": "out-of-scope", "reason": "r",
                               "followUp": FOLLOW_UP}])
    assert out["ok"] is False and out["reason"] == "ruling-entry-invalid", out


def test_owner_gate_and_answered_attempts_refuse(tmp_path):
    d = _session_at_fixer(tmp_path, name="rule-gates")
    state = TRI._state(d)
    key = _keys(state["_fixBatch"])[0]
    ruling = [{"id": key, "ruling": "refuted", "reason": "unreachable"}]
    _stub_dispatch_observed_land(d, state, state["pending"], "fixer", payload=FIXER_PAYLOAD)
    out = _rule(tmp_path, d, ruling)
    assert out["ok"] is False and out["reason"] == "ruling-attempt-has-results", out
    state_path = os.path.join(d, RD.STATE_FILE)
    for gate in RD.OWNER_GATE_PHASES:
        state["pending"] = dict(state["pending"], phase=gate)
        RD.save_state(d, state)
        with open(state_path, "rb") as fh:
            before = fh.read()
        out = _rule(tmp_path, d, ruling, name="gate-%s.json" % gate)
        assert out["ok"] is False and out["reason"] == "ruling-owner-gate-pending", (gate, out)
        with open(state_path, "rb") as fh:
            assert fh.read() == before, "%s changed state" % gate


def test_a_closing_ruling_on_a_pending_audit_target_is_refused_until_the_audit_folds(tmp_path):
    """The audits fold records `fixed` for every discharged target, so a closing ruling lodged while
    that audit is pending would be overwritten: it is refused, folds nothing, and lodges once the
    audit has folded."""
    findings = [TRI._blocking_finding("unchecked index", 2)]
    d, gitdir, head_path = _drive_to_audits(tmp_path, findings=findings, name="rule-under-audit")
    key = TRI._state(d)["_auditTargets"][0]["id"]
    ruling = [{"id": key, "ruling": "refuted", "reason": "the verifier misread the guard"}]
    state_path = os.path.join(d, RD.STATE_FILE)
    with open(state_path, "rb") as fh:
        before = fh.read()
    out = _rule(tmp_path, d, ruling)
    assert out["ok"] is False and out["reason"] == "ruling-target-in-pending-wave", out
    assert "after the %s wave folds" % RD.P_AUDITS in out["detail"], out
    with open(state_path, "rb") as fh:
        assert fh.read() == before
    phase, adv = TRI._drive_one_phase(d, gitdir, findings, head_path)
    assert phase == RD.P_AUDITS and adv["ok"], adv
    assert _rule(tmp_path, d, ruling, name="after-audit.json")["ok"] is True
    row = next(r for r in TRI._state(d)[SC.DISPOSITION_LEDGER_KEY]
               if r.get(SC.FINDING_KEY_FIELD) == key)
    assert row["disposition"] == "refuted", row


def test_a_closing_ruling_during_a_pending_scoped_finder_wave_is_refused_not_lost(tmp_path):
    """The scoped fold re-stages the audits' new-issue candidates, re-stamping each raise after any
    disposition written meanwhile — so a closing ruling on a candidate lodged while that wave is
    pending would be silently lost. It is refused with the one pending-wave token, folds nothing,
    and lodges once the waves that re-stage the candidate have folded."""
    findings = [TRI._blocking_finding("unchecked index", 2)]
    d, gitdir, head_path = _drive_to_audits(tmp_path, findings=findings, name="rule-scoped")
    phase, adv = TRI._drive_one_phase(d, gitdir, findings, head_path)
    assert phase == RD.P_AUDITS and adv["ok"], adv
    if TRI._state(d)["step"] == RD.P_VERIFY:
        TRI._drive_one_phase(d, gitdir, findings, head_path)
    state = TRI._state(d)
    assert state["step"] == RD.P_SCOPED and state["pending"]["phase"] == RD.P_SCOPED, (
        state.get("step"))
    cand = dict(TRI._blocking_finding("a fresh defect the audit saw", 3), originAuditId="audit-1")
    state["_newIssues"] = [cand]
    state["rounds"][str(state["round"])]["auditNewIssues"] = RD._audit_new_issue_rows([cand])
    RD.save_state(d, state)
    key = SC.new_issue_candidate_key(cand)
    ruling = [{"id": key, "ruling": "refuted", "reason": "the audit misread the guard"}]
    state_path = os.path.join(d, RD.STATE_FILE)
    with open(state_path, "rb") as fh:
        before = fh.read()
    out = _rule(tmp_path, d, ruling)
    assert out["ok"] is False and out["reason"] == "ruling-target-in-pending-wave", out
    assert "after the %s wave folds" % RD.P_SCOPED in out["detail"], out
    with open(state_path, "rb") as fh:
        assert fh.read() == before
    for _ in range(4):
        if TRI._state(d)["step"] == RD.P_FIXER:
            break
        TRI._drive_one_phase(d, gitdir, findings, head_path)
    assert TRI._state(d)["step"] == RD.P_FIXER, TRI._state(d).get("step")
    assert _rule(tmp_path, d, ruling, name="after-scoped.json")["ok"] is True
    row = next(r for r in TRI._state(d)[SC.DISPOSITION_LEDGER_KEY]
               if r.get(SC.FINDING_KEY_FIELD) == key)
    assert row["disposition"] == "refuted", row
    assert row[SC.DISPOSITION_SEQ_FIELD] > row[SC.RAISED_SEQ_FIELD], row


def test_a_step_with_no_declared_wave_reach_refuses_every_closing_ruling():
    """Fail closed: a step the reach table does not declare reaches every target."""
    assert RD._pending_wave_reach({"step": RD.P_VERIFY}) is RD._WAVE_REACH_ALL
    assert RD._pending_wave_reach({"step": RD.P_VERIFY, "_verifyThen": RD.VERIFY_THEN_POST_AUDITS,
                                   "_newIssues": [{"id": "k"}]}) >= {"k"}
    assert RD._pending_wave_reach({"step": "dispatch-some-future-wave"}) is RD._WAVE_REACH_ALL
    assert RD._pending_wave_reach({"step": RD.P_FIXER, "_newIssues": [{"id": "k"}]}) == set()


def test_a_superseded_attempt_is_never_reissued(tmp_path):
    d = _session_at_fixer(tmp_path, name="rule-attempt")
    state = TRI._state(d)
    old_order = _order_path(d, state["pending"])
    key = _keys(state["_fixBatch"])[1]
    assert _rule(tmp_path, d, [{"id": key, "ruling": "fix-with-guidance",
                                "guidance": GUIDANCE}])["ok"] is True
    assert RD._next_dispatch_attempt(d, 1, RD.P_FIXER, TRI._state(d)) == 1
    RD.cmd_next(d)
    assert _order_path(d, TRI._state(d)["pending"]) != old_order


def test_a_second_guidance_ruling_for_one_finding_in_a_round_is_refused(tmp_path):
    """Two artifacts, one finding: the second guidance ruling is refused before `next`, folds
    nothing, and the first guidance is the one the re-rendered order carries."""
    d = _session_at_fixer(tmp_path, name="rule-guide-twice")
    key = _keys(TRI._state(d)["_fixBatch"])[1]
    assert _rule(tmp_path, d, [{"id": key, "ruling": "fix-with-guidance",
                                "guidance": GUIDANCE}])["ok"] is True
    state_path = os.path.join(d, RD.STATE_FILE)
    with open(state_path, "rb") as fh:
        before = fh.read()
    other = "rewrite the loop instead"
    out = _rule(tmp_path, d, [{"id": key, "ruling": "fix-with-guidance", "guidance": other}],
                name="second-guidance.json")
    assert out["ok"] is False and out["reason"] == "ruling-entry-invalid", out
    with open(state_path, "rb") as fh:
        assert fh.read() == before
    assert len(TRI._state(d)["rounds"]["1"]["rulings"]) == 1
    n = RD.cmd_next(d)
    assert n["ok"] and n["phase"] == RD.P_FIXER and n["attempt"] == 1, n
    with open(_order_path(d, TRI._state(d)["pending"]), encoding="utf-8") as fh:
        order = fh.read()
    assert GUIDANCE in order and other not in order


@pytest.fixture
def refused_new_issue_session(tmp_path, monkeypatch):
    """4c-3's audited-chain session whose fix audit raised one new issue the ledger never held
    (the Nit-cap-overflow shape), finalized once so its certification refusal is on disk. The
    fixture pre-stages the certification inputs, so their git re-derivation is held still."""
    monkeypatch.setattr(RD, "_finalize_certification_inputs", lambda *a, **k: None)
    d = T43.case08_new_issue_audit(tmp_path)
    state = RD.load_state(d)[1]
    RD._terminal_receipt_gate(d, state)
    state = RD.load_state(d)[1]
    cand = dict(T43._new_issue_template(), originAuditId=T43._fold_id(state))
    state["rounds"]["2"]["auditNewIssues"] = RD._audit_new_issue_rows([cand])
    state["dispositionSeqCounter"] = 2
    RD.save_state(d, state)
    return d, state["rounds"]["2"]["auditNewIssues"][0][SC.FINDING_KEY_FIELD]


def test_terminal_ruling_dispositions_an_unledgered_new_issue_and_recertifies(
        tmp_path, refused_new_issue_session):
    """The non-blocking convergence route: the refusal names the undispositioned new issue; a
    closing ruling seeds and dispositions it, the refusal is archived, and the session certifies
    without a new panel or a re-run of the original fix audit."""
    d, key = refused_new_issue_session
    with open(os.path.join(d, RD.CERTIFICATION_REFUSAL_FILE), encoding="utf-8") as fh:
        refusal = json.load(fh)
    assert "new-issue-undispositioned" in refusal["detail"]
    out = _rule(tmp_path, d, [{"id": key, "ruling": "refuted",
                               "reason": "the adjacent path is unreachable"}])
    assert out["ok"] is True, out
    assert out["recertified"]["certified"] is True, out
    assert not os.path.exists(os.path.join(d, RD.CERTIFICATION_REFUSAL_FILE))
    with open(out["recertified"]["archivedRefusal"], encoding="utf-8") as fh:
        assert json.load(fh) == refusal
    state = RD.load_state(d)[1]
    row = next(r for r in state[SC.DISPOSITION_LEDGER_KEY] if r.get(SC.FINDING_KEY_FIELD) == key)
    assert row[SC.RAISED_ROUND_FIELD] == 2
    assert row[SC.DISPOSITION_SEQ_FIELD] > row[SC.RAISED_SEQ_FIELD]
    assert RD.RULING_RECERTIFY_MARKER not in state and state["_receiptFinalized"] is True
    receipt, cert_refusal = RC.certify(d)
    assert cert_refusal is None and receipt is not None


def test_terminal_takes_only_closing_rulings_and_never_a_certified_session(
        tmp_path, refused_new_issue_session):
    d, key = refused_new_issue_session
    out = _rule(tmp_path, d, [{"id": key, "ruling": "fix-with-guidance", "guidance": GUIDANCE}])
    assert out["ok"] is False and out["reason"] == "ruling-entry-invalid", out
    assert _rule(tmp_path, d, [{"id": key, "ruling": "refuted", "reason": "r"}],
                 name="ok.json")["ok"] is True
    out = _rule(tmp_path, d, [{"id": key, "ruling": "refuted", "reason": "again"}],
                name="again.json")
    assert out["ok"] is False and out["reason"] == "ruling-session-terminal", out
    # The crash window: a receipt landed but the stale refusal was not yet retired. The session is
    # certified, and that alone refuses.
    with open(os.path.join(d, RD.CERTIFICATION_REFUSAL_FILE), "w", encoding="utf-8") as fh:
        fh.write("{}\n")
    out = _rule(tmp_path, d, [{"id": key, "ruling": "refuted", "reason": "again"}],
                name="again2.json")
    assert out["ok"] is False and out["reason"] == "ruling-session-terminal", out
    assert "certified" in out["detail"], out


def test_a_faulted_terminal_receipt_is_never_reopened_by_a_ruling(
        tmp_path, refused_new_issue_session):
    """A terminal session whose receipt verification failed carries `_receiptFault`; a closing
    ruling that would otherwise be accepted is refused and records nothing."""
    d, key = refused_new_issue_session
    assert os.path.isfile(os.path.join(d, RD.CERTIFICATION_REFUSAL_FILE))
    state = RD.load_state(d)[1]
    state["_receiptFault"] = "receipt verification failed"
    RD.save_state(d, state)
    state_path = os.path.join(d, RD.STATE_FILE)
    with open(state_path, "rb") as fh:
        before = fh.read()
    out = _rule(tmp_path, d, [{"id": key, "ruling": "refuted", "reason": "unreachable"}])
    assert out["ok"] is False and out["reason"] == "ruling-session-terminal", out
    assert "faulted receipt" in out["detail"], out
    with open(state_path, "rb") as fh:
        assert fh.read() == before
    state = RD.load_state(d)[1]
    assert not any(r.get("id") == key for rec in state["rounds"].values()
                   for r in (rec.get("rulings") or []))


def test_a_crash_after_the_ruling_commit_recertifies_on_the_next_terminal_answer(
        tmp_path, refused_new_issue_session, monkeypatch):
    """Crash-consistency: the ruling's commit clears the finalized mark, so if the process dies
    before re-certifying, the next terminal answer re-finalizes and completes the retirement."""
    d, key = refused_new_issue_session
    monkeypatch.setattr(RD, "_terminal_receipt_gate", lambda *a, **k: None)
    assert _rule(tmp_path, d, [{"id": key, "ruling": "refuted", "reason": "r"}])["ok"] is True
    monkeypatch.undo()
    monkeypatch.setattr(RD, "_finalize_certification_inputs", lambda *a, **k: None)
    state = RD.load_state(d)[1]
    assert state["_receiptFinalized"] is False and state[RD.RULING_RECERTIFY_MARKER] is True
    assert RD._terminal_receipt_gate(d, state) is None
    assert os.path.exists(os.path.join(d, RD.CERTIFICATION_RECEIPT_FILE))
    assert not os.path.exists(os.path.join(d, RD.CERTIFICATION_REFUSAL_FILE))


def test_audit_new_issue_rows_use_the_certification_identity():
    cand = {"file": "src/a.py", "line": " 7 ", "title": "overflow nit", "severity": "Nit",
            "originAuditId": "src/a.py::fix@L3", SC.FINDING_KEY_FIELD: "ignored"}
    rows = RD._audit_new_issue_rows([cand, {"file": "", "line": 1, "title": "t"}])
    assert len(rows) == 1 and rows[0]["line"] == 7
    assert rows[0][SC.FINDING_KEY_FIELD] == SC.new_issue_candidate_key(cand)
    assert rows[0][SC.FINDING_KEY_FIELD] == SC.minted_identity_key(
        {"file": "src/a.py", "line": 7, "title": "overflow nit", "severity": "Nit"})


def test_the_audits_fold_records_each_new_issue_candidate_on_the_round(tmp_path):
    """The address a ruling names is written at the audits fold, before any Nit cap can drop it."""
    d, _gitdir, _head = _drive_to_audits(tmp_path, name="rule-audit-rows")
    state = TRI._state(d)
    target = state["_auditTargets"][0]
    nits = [{"file": "src/f00.py", "line": n, "title": "nit %d" % n, "severity": "Nit"}
            for n in range(1, 8)]
    artifact = {"results": [{"id": target["id"], "ruling": "discharged-but-new-issue",
                             "reason": "fixed; seven nits nearby",
                             "auditorVendor": target.get("auditorVendor"), "newIssues": nits}],
                "collectionManifest": {target["id"]: target.get("auditorVendor")}}
    RD._fold_audits(state, state["config"], artifact)
    rows = state["rounds"][str(state["round"])]["auditNewIssues"]
    assert [r["title"] for r in rows] == ["nit %d" % n for n in range(1, 8)]
    assert all(r["originAuditId"] == target["id"] for r in rows)
    assert [r[SC.FINDING_KEY_FIELD] for r in rows] == [SC.new_issue_candidate_key(n) for n in nits]


_FOLD_ONE = "src/a.py::fix one@L1"
_FOLD_THREE = "src/a.py::fix three@L9"
_NIT = {"file": "src/f00.py", "line": 4, "title": "overflow nit", "severity": "Nit"}


def _cand(fold_id):
    return dict(_NIT, originAuditId=fold_id)


def _ledgered_session(rnd):
    """A recognized-owner ledger holding two fixed folds; audit new-issue rows are planted by
    each test on the round that recorded them."""
    ledger = [{SC.FINDING_KEY_FIELD: fid, "disposition": "fixed", "dispositionRound": r,
               SC.RAISED_ROUND_FIELD: 1, SC.RAISED_SEQ_FIELD: seq, SC.DISPOSITION_SEQ_FIELD: seq + 1}
              for fid, r, seq in ((_FOLD_ONE, 1, 1), (_FOLD_THREE, 3, 3))]
    return {"round": rnd, "rounds": {str(n): {} for n in range(1, rnd + 1)},
            SC.DISPOSITION_LEDGER_KEY: ledger,
            SC.DISPOSITION_LEDGER_OWNER_FIELD: SC.DISPOSITION_LEDGER_OWNER_VALUE,
            "dispositionSeqCounter": 4}


def _apply_ruling(state, key, reason):
    plan, refusal, detail = RD._plan_rulings(
        state, [{"id": key, "ruling": "refuted", "reason": reason}], True)
    assert refusal is None, (refusal, detail)
    RD._fold_rulings(state, plan, PROV, "0" * 64)


def _ledger_row(state, key):
    return next(r for r in state[SC.DISPOSITION_LEDGER_KEY] if r.get(SC.FINDING_KEY_FIELD) == key)


def test_a_candidate_raised_on_two_rounds_seeds_its_latest_raise_and_recertifies_the_later_fold():
    """Last wins: a candidate recorded in rounds 1 and 3 and ruled after round 3 is ledgered with
    raisedRound 3, so both folds that listed it reconcile."""
    state = _ledgered_session(3)
    state["rounds"]["1"]["auditNewIssues"] = RD._audit_new_issue_rows([_cand(_FOLD_ONE)])
    state["rounds"]["3"]["auditNewIssues"] = RD._audit_new_issue_rows([_cand(_FOLD_THREE)])
    key = state["rounds"]["3"]["auditNewIssues"][0][SC.FINDING_KEY_FIELD]
    _apply_ruling(state, key, "the adjacent path is unreachable")
    gap = RC._new_issues_reconciliation_gap(state, _FOLD_THREE, 3, [_cand(_FOLD_THREE)])
    assert gap is None, gap
    assert _ledger_row(state, key)[SC.RAISED_ROUND_FIELD] == 3
    assert RC._new_issues_reconciliation_gap(state, _FOLD_ONE, 1, [_cand(_FOLD_ONE)]) is None


def test_a_ruling_recorded_before_a_re_raise_never_certifies_it_and_a_fresh_ruling_does():
    """Fail-closed: a round-2 ruling answers only the round-1 raise. The round-3 re-raise stays
    refused with the ledger token until a fresh ruling re-stamps the raise and dispositions it."""
    state = _ledgered_session(2)
    state["rounds"]["1"]["auditNewIssues"] = RD._audit_new_issue_rows([_cand(_FOLD_ONE)])
    key = state["rounds"]["1"]["auditNewIssues"][0][SC.FINDING_KEY_FIELD]
    _apply_ruling(state, key, "stale answer")
    assert _ledger_row(state, key)[SC.RAISED_ROUND_FIELD] == 1
    state["round"] = 3
    state["rounds"]["3"] = {"auditNewIssues": RD._audit_new_issue_rows([_cand(_FOLD_THREE)])}
    gap = RC._new_issues_reconciliation_gap(state, _FOLD_THREE, 3, [_cand(_FOLD_THREE)])
    assert gap == "new-issue-ledger-malformed", gap
    _apply_ruling(state, key, "fresh answer to the re-raise")
    row = _ledger_row(state, key)
    assert row[SC.RAISED_ROUND_FIELD] == 3 and row.get("refutedReason") == (
        "fresh answer to the re-raise")
    assert row[SC.DISPOSITION_SEQ_FIELD] > row[SC.RAISED_SEQ_FIELD]
    assert sum(1 for r in state[SC.DISPOSITION_LEDGER_KEY]
               if r.get(SC.FINDING_KEY_FIELD) == key) == 1
    assert RC._new_issues_reconciliation_gap(state, _FOLD_THREE, 3, [_cand(_FOLD_THREE)]) is None
