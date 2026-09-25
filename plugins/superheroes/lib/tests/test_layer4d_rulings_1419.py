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
    assert rows[key]["gateRuling"]["disposition"] == RD.RULING_GUIDANCE
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
    assert out["ok"] is False and out["reason"] == RD.RULING_ENTRY_INVALID, out


def _refusal_cases(ruled):
    good = {"id": ruled, "ruling": "refuted", "reason": "unreachable"}
    return [
        ("unreadable", None, RD.RULING_ARTIFACT_UNREADABLE),
        ("empty", {"rulings": [], "_provenance": PROV}, RD.RULING_ARTIFACT_SHAPE),
        ("no-provenance", {"rulings": [good]}, RD.RULING_PROVENANCE_MISSING),
        ("bad-provenance", {"rulings": [good], "_provenance": dict(PROV, records=[])},
         RD.RULING_PROVENANCE_MISSING),
        ("duplicate", {"rulings": [good, good], "_provenance": PROV}, RD.RULING_ENTRY_INVALID),
        ("unknown-kind", {"rulings": [dict(good, ruling="skip")], "_provenance": PROV},
         RD.RULING_ENTRY_INVALID),
        ("no-reason", {"rulings": [dict(good, reason=" ")], "_provenance": PROV},
         RD.RULING_ENTRY_INVALID),
        ("no-follow-up", {"rulings": [dict(good, ruling="out-of-scope")], "_provenance": PROV},
         RD.RULING_ENTRY_INVALID),
        ("unknown-target", {"rulings": [dict(good, id="src/nowhere.py::ghost@L9")],
                            "_provenance": PROV}, RD.RULING_TARGET_UNKNOWN),
        ("later-row-invalid", {"rulings": [good, {"id": "src/nowhere.py::ghost@L9",
                                                  "ruling": "refuted", "reason": "x"}],
                               "_provenance": PROV}, RD.RULING_TARGET_UNKNOWN),
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
    assert out["ok"] is False and out["reason"] == RD.RULING_ENTRY_INVALID, out


def test_owner_gate_and_answered_attempts_refuse(tmp_path):
    d = _session_at_fixer(tmp_path, name="rule-gates")
    state = TRI._state(d)
    key = _keys(state["_fixBatch"])[0]
    ruling = [{"id": key, "ruling": "refuted", "reason": "unreachable"}]
    _stub_dispatch_observed_land(d, state, state["pending"], "fixer", payload=FIXER_PAYLOAD)
    out = _rule(tmp_path, d, ruling)
    assert out["ok"] is False and out["reason"] == RD.RULING_ATTEMPT_HAS_RESULTS, out
    state["pending"] = dict(state["pending"], phase=RD.P_JUDGMENT)
    RD.save_state(d, state)
    out = _rule(tmp_path, d, ruling, name="gate.json")
    assert out["ok"] is False and out["reason"] == RD.RULING_OWNER_GATE_PENDING, out


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
    assert out["ok"] is False and out["reason"] == RD.RULING_ENTRY_INVALID, out
    assert _rule(tmp_path, d, [{"id": key, "ruling": "refuted", "reason": "r"}],
                 name="ok.json")["ok"] is True
    out = _rule(tmp_path, d, [{"id": key, "ruling": "refuted", "reason": "again"}],
                name="again.json")
    assert out["ok"] is False and out["reason"] == RD.RULING_SESSION_TERMINAL, out
    # The crash window: a receipt landed but the stale refusal was not yet retired. The session is
    # certified, and that alone refuses.
    with open(os.path.join(d, RD.CERTIFICATION_REFUSAL_FILE), "w", encoding="utf-8") as fh:
        fh.write("{}\n")
    out = _rule(tmp_path, d, [{"id": key, "ruling": "refuted", "reason": "again"}],
                name="again2.json")
    assert out["ok"] is False and out["reason"] == RD.RULING_SESSION_TERMINAL, out
    assert "certified" in out["detail"], out


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
