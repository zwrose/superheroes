"""#1445 WO-1 — owner/advisor rulings channel (`rule` verb)."""
import importlib.util
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_driver as RD  # noqa: E402
import round_records as RR  # noqa: E402
import session_contract  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "test_round_driver_integration",
    os.path.join(_HERE, "test_round_driver_integration.py"))
_TRI = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_TRI)

_bootstrap = _TRI._bootstrap


def _blocking_finding(title, line):
    finding = _TRI._blocking_finding(title, line)
    finding["consequence"] = "a reviewer-found defect stays in the change"
    return finding


_state = _TRI._state
_fake_git = _TRI._fake_git
_drive_to_phase = _TRI._drive_to_phase
_drive_one_phase = _TRI._drive_one_phase
_land = _TRI._land
_write_dispatch_manifest = _TRI._write_dispatch_manifest
_slots_of = _TRI._slots_of
_auditor_vendor_for = _TRI._auditor_vendor_for

P_APPLY_FIXES = RD.P_APPLY_FIXES
STATE_PATH = session_contract.STATE_FILE


def _state_bytes(session_dir):
    with open(os.path.join(session_dir, STATE_PATH), "rb") as fh:
        return fh.read()


def _provenance():
    return {"ruledBy": "owner", "ruledAt": "2026-08-26T00:00:00Z", "records": ["rulings.json"]}


def _follow_up():
    return {
        "item": "backlog item",
        "revisitTrigger": "next milestone",
        "classClosure": "owner backlog",
    }


def _write_ruling_file(path, entries, *, provenance=None):
    doc = {"_provenance": provenance if provenance is not None else _provenance(),
           "rulings": entries}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    return path


def _rule(session_dir, ruling_path, by="owner"):
    return RD.cmd_rule(session_dir, ruling_path, by)


def _apply_fixes_text(session_dir):
    """What the pending `apply-fixes` step hands the build session: its batch file and, when there
    is guidance for it, its guidance file (the step makes no order)."""
    pend = _state(session_dir)["pending"]
    assert pend["phase"] == P_APPLY_FIXES
    payload = pend["payload"]
    with open(payload["fixBatchPath"], encoding="utf-8") as fh:
        text = fh.read()
    if payload.get("guidancePath"):
        with open(payload["guidancePath"], encoding="utf-8") as fh:
            text += "\n" + fh.read()
    return text


def _pending_apply_fixes_two_findings(tmp_path):
    f_a = _blocking_finding("bounds A", 2)
    f_b = _blocking_finding("bounds B", 3)
    f_b["severity"] = "Minor"
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="rulings-1445", fixBatchCap=1)
    _drive_to_phase(session_dir, gitdir, [f_a, f_b], head_path, P_APPLY_FIXES)
    state = _state(session_dir)
    assert state["pending"]["phase"] == P_APPLY_FIXES
    batch = state.get("_fixBatch") or []
    queue = state.get("_fixQueue") or []
    assert batch and (queue or len(batch) >= 2)
    row_b = queue[0] if queue else batch[1]
    return session_dir, gitdir, head_path, batch[0], row_b


@pytest.mark.parametrize("token,setup", [
    ("ruling-file-unreadable", "missing_file"),
    ("ruling-file-shape", "bad_shape"),
    ("ruling-provenance-malformed", "bad_prov"),
    ("ruling-unknown-kind", "bad_kind"),
    ("ruling-reason-missing", "no_reason"),
    ("ruling-follow-up-malformed", "bad_follow"),
    ("ruling-guidance-oversize", "big_guidance"),
    ("ruling-target-unknown", "unknown_id"),
    ("ruling-critical-out-of-scope", "critical_oos"),
    ("ruling-session-terminal", "terminal"),
    ("disposition-ledger-owner-unrecognized", "unrecognized_owner"),
    ("disposition-ledger-malformed", "malformed_ledger"),
])
def test_rule_refusal_tokens(tmp_path, token, setup):
    session_dir, gitdir, head_path, row_a, row_b = _pending_apply_fixes_two_findings(tmp_path)
    ruling_path = tmp_path / "rulings.json"
    id_a = row_a.get("id") or RD._fix_batch_row_key(row_a)
    before = _state_bytes(session_dir)
    if setup == "missing_file":
        out = _rule(session_dir, str(tmp_path / "nope.json"))
    elif setup == "bad_shape":
        ruling_path.write_text("[]", encoding="utf-8")
        out = _rule(session_dir, str(ruling_path))
    elif setup == "bad_prov":
        _write_ruling_file(ruling_path, [{"id": id_a, "ruling": "guidance",
                                           "reason": "r", "guidance": "g"}],
                           provenance={"ruledBy": "", "ruledAt": "t", "records": ["x"]})
        out = _rule(session_dir, str(ruling_path))
    elif setup == "bad_kind":
        _write_ruling_file(ruling_path, [{"id": id_a, "ruling": "nope", "reason": "r"}])
        out = _rule(session_dir, str(ruling_path))
    elif setup == "no_reason":
        _write_ruling_file(ruling_path, [{"id": id_a, "ruling": "guidance",
                                           "reason": "  ", "guidance": "g"}])
        out = _rule(session_dir, str(ruling_path))
    elif setup == "bad_follow":
        _write_ruling_file(ruling_path, [{"id": id_a, "ruling": "out-of-scope", "reason": "r",
                                           "followUp": {"item": "x"}}])
        out = _rule(session_dir, str(ruling_path))
    elif setup == "big_guidance":
        _write_ruling_file(ruling_path, [{"id": id_a, "ruling": "guidance", "reason": "r",
                                           "guidance": "x" * 3000}])
        out = _rule(session_dir, str(ruling_path))
    elif setup == "unknown_id":
        _write_ruling_file(ruling_path, [{"id": "no-such-finding", "ruling": "guidance",
                                           "reason": "r", "guidance": "g"}])
        out = _rule(session_dir, str(ruling_path))
    elif setup == "critical_oos":
        crit_id = row_a.get("id") or RD._fix_batch_row_key(row_a)
        state = _state(session_dir)
        for row in (state.get("_fixBatch") or []):
            if RD._fix_batch_row_key(row) == RD._fix_batch_row_key(row_a):
                row["severity"] = "Critical"
        RD.save_state(session_dir, state)
        _write_ruling_file(ruling_path, [{"id": crit_id, "ruling": "out-of-scope", "reason": "r",
                                           "followUp": _follow_up()}])
        before = _state_bytes(session_dir)
        out = _rule(session_dir, str(ruling_path))
    elif setup == "terminal":
        state = _state(session_dir)
        state["terminal"] = True
        RD.save_state(session_dir, state)
        _write_ruling_file(ruling_path, [{"id": id_a, "ruling": "guidance",
                                           "reason": "r", "guidance": "g"}])
        before = _state_bytes(session_dir)
        out = _rule(session_dir, str(ruling_path))
    elif setup == "unrecognized_owner":
        state = _state(session_dir)
        state["dispositionLedgerOwner"] = "ledger-v2"
        RD.save_state(session_dir, state)
        _write_ruling_file(ruling_path, [{"id": id_a, "ruling": "out-of-scope", "reason": "r",
                                           "followUp": _follow_up()}])
        before = _state_bytes(session_dir)
        out = _rule(session_dir, str(ruling_path))
    elif setup == "malformed_ledger":
        state = _state(session_dir)
        state[session_contract.DISPOSITION_LEDGER_KEY] = {"not": "a-list"}
        RD.save_state(session_dir, state)
        _write_ruling_file(ruling_path, [{"id": id_a, "ruling": "out-of-scope", "reason": "r",
                                           "followUp": _follow_up()}])
        before = _state_bytes(session_dir)
        out = _rule(session_dir, str(ruling_path))
    else:
        pytest.fail("unknown setup")
    assert out.get("ok") is False, out
    assert out.get("reason") == token, out
    assert _state_bytes(session_dir) == before


def test_edge2_ruling_off_batch_logged(tmp_path):
    session_dir, gitdir, head_path, row_a, row_b = _pending_apply_fixes_two_findings(tmp_path)
    id_b = row_b.get("id") or RD._fix_batch_row_key(row_b)
    path = _write_ruling_file(tmp_path / "r.json", [
        {"id": id_b, "ruling": "guidance", "reason": "defer", "guidance": "only fix A"}])
    out = _rule(session_dir, path)
    assert out.get("ok"), out
    state = _state(session_dir)
    assert any(r.get("findingKey") == RD._fix_batch_row_key(row_b)
               for r in state.get("rulingsLog") or [])


def test_edge3_restage_reapplies_out_of_scope(tmp_path):
    """axis: restaging re-applies a live out-of-scope ruling onto the new ledger row.

    bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_rulings_channel_1445.md (BP-3)
    """
    session_dir, gitdir, head_path, row_a, row_b = _pending_apply_fixes_two_findings(tmp_path)
    id_b = row_b.get("id") or RD._fix_batch_row_key(row_b)
    path = _write_ruling_file(tmp_path / "r.json", [
        {"id": id_b, "ruling": "out-of-scope", "reason": "later",
         "followUp": _follow_up()}])
    assert _rule(session_dir, path)["ok"]
    state = _state(session_dir)
    key_b = RD._fix_batch_row_key(row_b)
    state["round"] = state["round"] + 1
    RD._stage_findings(state, [dict(row_b)])
    ledger = state.get(session_contract.DISPOSITION_LEDGER_KEY) or []
    entry = next(e for e in ledger if RD._finding_identity_key(e) == key_b)
    assert entry.get("disposition") == "out-of-scope"


def test_edge4_guidance_lifts_out_of_scope(tmp_path):
    """axis: guidance superseding out-of-scope clears the ledger family and restores the fix row."""
    session_dir, _, _, row_a, row_b = _pending_apply_fixes_two_findings(tmp_path)
    key_b = RD._fix_batch_row_key(row_b)
    id_b = row_b.get("id") or key_b
    p1 = _write_ruling_file(tmp_path / "r1.json", [
        {"id": id_b, "ruling": "out-of-scope", "reason": "skip",
         "followUp": _follow_up()}])
    assert _rule(session_dir, p1)["ok"]
    p2 = _write_ruling_file(tmp_path / "r2.json", [
        {"id": id_b, "ruling": "guidance", "reason": "fix now", "guidance": "use guard X"}])
    assert _rule(session_dir, p2)["ok"]
    state = _state(session_dir)
    assert key_b not in RD._live_out_of_scope_ruling_keys(state)
    ledger = state.get(session_contract.DISPOSITION_LEDGER_KEY) or []
    entry = next(e for e in ledger if RD._finding_identity_key(e) == key_b)
    assert entry.get("disposition") != "out-of-scope"
    live = RD._live_finding_by_key(state, key_b)
    if isinstance(live, dict):
        assert live.get("disposition") != "out-of-scope"
    scheduled = {RD._fix_batch_row_key(row)
                 for row in list(state.get("_fixBatch") or []) + list(state.get("_fixQueue") or [])
                 if isinstance(row, dict)}
    assert key_b in scheduled


def test_critical_restage_not_suppressed_by_stale_out_of_scope(tmp_path):
    session_dir, _, _, row_a, row_b = _pending_apply_fixes_two_findings(tmp_path)
    id_b = row_b.get("id") or RD._fix_batch_row_key(row_b)
    path = _write_ruling_file(tmp_path / "r.json", [
        {"id": id_b, "ruling": "out-of-scope", "reason": "later",
         "followUp": _follow_up()}])
    assert _rule(session_dir, path)["ok"]
    state = _state(session_dir)
    key_b = RD._fix_batch_row_key(row_b)
    crit = dict(row_b)
    crit["severity"] = "Critical"
    state["round"] = state["round"] + 1
    RD._stage_findings(state, [crit])
    ledger = state.get(session_contract.DISPOSITION_LEDGER_KEY) or []
    entry = next(e for e in ledger if RD._finding_identity_key(e) == key_b)
    assert entry.get("disposition") != "out-of-scope"
    filtered, fault = RD._filter_excluded_discharged_fixes(state, [crit])
    assert fault is None
    assert len(filtered) == 1


def test_ruling_target_ambiguous_when_staged_id_reused():
    state = {
        session_contract.DISPOSITION_LEDGER_KEY: [
            {"id": "v0", "file": "a.py", "title": "old", "line": 1, "severity": "Important"},
            {"id": "v0", "file": "b.py", "title": "new", "line": 2, "severity": "Important"},
        ],
        "findings": [],
    }
    key, row, fault = RD._resolve_ruling_target(state, "v0")
    assert key is None and row is None
    assert fault == RD.RULING_TARGET_AMBIGUOUS


def test_rule_accepts_while_apply_fixes_is_pending_and_leaves_the_attempt(tmp_path):
    """axis: rule records a ruling while the `apply-fixes` step is pending (it used to refuse
    ruling-attempt-pending) and the step stays pending at the same attempt; a ruled-out row leaves
    the schedule."""
    session_dir, _, _, row_a, row_b = _pending_apply_fixes_two_findings(tmp_path)
    id_b = row_b.get("id") or RD._fix_batch_row_key(row_b)
    before = _state(session_dir)
    out = _rule(session_dir, _write_ruling_file(tmp_path / "r.json", [
        {"id": id_b, "ruling": "out-of-scope", "reason": "defer B",
         "followUp": _follow_up()}]))
    assert out.get("ok") is True, out
    after = _state(session_dir)
    assert (after["pending"]["phase"], after["pending"]["attempt"]) == (
        before["pending"]["phase"], before["pending"]["attempt"])
    assert after["_fixBatch"] == before["_fixBatch"]
    assert RD._fix_batch_row_key(row_b) not in {
        RD._fix_batch_row_key(row) for row in after.get("_fixQueue") or []}
    assert len(after["rulingsLog"]) == len(before.get("rulingsLog") or []) + 1


def test_a_ruling_on_a_batch_row_while_apply_fixes_is_pending_rewrites_the_batch_file(tmp_path):
    """axis: a ruling on a row of the step's batch rewrites `fix-batch.json` to the batch without it
    (the session reads the files the step names), at the same attempt; the file is the one the step
    named, still readable, and the payload's own path."""
    f_a = _blocking_finding("bounds A", 2)
    f_b = _blocking_finding("bounds B", 3)
    f_b["severity"] = "Minor"
    session_dir, gitdir, head_path = _bootstrap(
        tmp_path, name="rulings-1445-sha", fixBatchCap=2)
    _drive_to_phase(session_dir, gitdir, [f_a, f_b], head_path, P_APPLY_FIXES)
    state = _state(session_dir)
    pend = state["pending"]
    rnd = pend["round"]
    batch_path = pend["payload"]["fixBatchPath"]
    row_b = (state.get("_fixBatch") or [None, {}])[1]
    if not isinstance(row_b, dict):
        row_b = (state.get("_fixQueue") or [{}])[0]
    key_b = RD._fix_batch_row_key(row_b)
    id_b = row_b.get("id") or key_b
    with open(batch_path, encoding="utf-8") as fh:
        assert key_b in fh.read()
    out = _rule(session_dir, _write_ruling_file(tmp_path / "r.json", [
        {"id": id_b, "ruling": "out-of-scope", "reason": "defer B",
         "followUp": _follow_up()}]))
    assert out.get("ok") is True, out
    after = _state(session_dir)
    assert after["pending"]["attempt"] == pend["attempt"]
    assert RD._ensure_fix_batch_file(session_dir, rnd, after) == batch_path
    assert after["pending"]["payload"]["fixBatchPath"] == batch_path
    with open(batch_path, encoding="utf-8") as fh:
        assert key_b not in fh.read()


def test_edge5_aggregate_cap_refuses_ruling_omitted(tmp_path):
    f_a = _blocking_finding("cap A", 2)
    f_b = _blocking_finding("cap B", 3)
    f_b["severity"] = "Minor"
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="edge5-cap", fixBatchCap=4)
    _drive_to_phase(session_dir, gitdir, [f_a, f_b], head_path, P_APPLY_FIXES)
    state = _state(session_dir)
    batch = state.get("_fixBatch") or []
    assert batch
    row_a = batch[0]
    rnd = state["round"]
    chunk = "z" * RD.GATE_GUIDANCE_ROW_BYTE_CAP
    id_a = row_a.get("id") or RD._fix_batch_row_key(row_a)
    state.setdefault("rounds", {}).setdefault(str(rnd), {})["judgmentDispositions"] = [
        {"disposition": "fix-with-guidance", "id": "gate-%d" % i,
         RD.GATE_GUIDANCE_RECORD_KEY: chunk,
         "title": "t", "file": "f.py", "line": i}
        for i in range(6)]
    RD.save_state(session_dir, state)
    batch_path = RD._ensure_fix_batch_file(session_dir, rnd, state)
    with open(batch_path, "rb") as fh:
        batch_bytes_before = fh.read()
    path = _write_ruling_file(tmp_path / "r.json", [
        {"id": id_a, "ruling": "guidance", "reason": "cap", "guidance": "must appear whole"}])
    out = _rule(session_dir, path)
    assert out.get("ok") is False
    assert out.get("reason") == "order-render-refused"
    assert "ruling-guidance-omitted" in str(out.get("detail", ""))
    with open(batch_path, "rb") as fh:
        assert fh.read() == batch_bytes_before


def test_a_render_refusal_while_apply_fixes_is_pending_leaves_loop_state_byte_identical(tmp_path):
    """axis: an aggregate guidance overflow while the step is pending refuses `rule` and leaves
    loop-state.json byte-identical."""
    f_a = _blocking_finding("cap A", 2)
    f_b = _blocking_finding("cap B", 3)
    f_b["severity"] = "Minor"
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="e4-cap", fixBatchCap=4)
    _drive_to_phase(session_dir, gitdir, [f_a, f_b], head_path, P_APPLY_FIXES)
    state = _state(session_dir)
    row_a = (state.get("_fixBatch") or [])[0]
    rnd = state["round"]
    chunk = "z" * RD.GATE_GUIDANCE_ROW_BYTE_CAP
    state.setdefault("rounds", {}).setdefault(str(rnd), {})["judgmentDispositions"] = [
        {"disposition": "fix-with-guidance", "id": "gate-%d" % i,
         RD.GATE_GUIDANCE_RECORD_KEY: chunk, "title": "t", "file": "f.py", "line": i}
        for i in range(6)]
    RD.save_state(session_dir, state)
    state_before = _state_bytes(session_dir)
    out = _rule(session_dir, _write_ruling_file(tmp_path / "r.json", [
        {"id": row_a.get("id") or RD._fix_batch_row_key(row_a), "ruling": "guidance",
         "reason": "cap", "guidance": "must appear whole"}]))
    assert out.get("ok") is False
    assert out.get("reason") == "order-render-refused"
    assert "ruling-guidance-omitted" in str(out.get("detail", ""))
    assert _state_bytes(session_dir) == state_before


def test_edge6_two_rule_calls_append(tmp_path):
    session_dir, _, _, row_a, row_b = _pending_apply_fixes_two_findings(tmp_path)
    id_a = row_a.get("id") or RD._fix_batch_row_key(row_a)
    id_b = row_b.get("id") or RD._fix_batch_row_key(row_b)
    assert _rule(session_dir, _write_ruling_file(tmp_path / "r1.json", [
        {"id": id_a, "ruling": "guidance", "reason": "a", "guidance": "ga"}]))["ok"]
    assert _rule(session_dir, _write_ruling_file(tmp_path / "r2.json", [
        {"id": id_b, "ruling": "guidance", "reason": "b", "guidance": "gb"}]))["ok"]
    rec = _state(session_dir)["rounds"][str(_state(session_dir)["round"])]
    assert len(rec.get("rulings") or []) == 2


def test_edge7_guidance_off_batch_no_supersede(tmp_path):
    """axis: guidance on a row outside the step's batch is recorded at once and leaves the pending
    attempt and its batch as they were."""
    session_dir, _, _, _, row_b = _pending_apply_fixes_two_findings(tmp_path)
    id_b = row_b.get("id") or RD._fix_batch_row_key(row_b)
    before = _state(session_dir)
    out = _rule(session_dir, _write_ruling_file(tmp_path / "r.json", [
        {"id": id_b, "ruling": "guidance", "reason": "off batch", "guidance": "later"}]))
    assert out.get("ok") is True, out
    after = _state(session_dir)
    assert (after["pending"]["phase"], after["pending"]["attempt"]) == (
        before["pending"]["phase"], before["pending"]["attempt"])
    assert after["_fixBatch"] == before["_fixBatch"]
    assert len(after["rulingsLog"]) == len(before.get("rulingsLog") or []) + 1


def test_rule_accepts_while_apply_fixes_is_pending_when_ruling_would_empty_batch(tmp_path):
    """axis: rule records rulings that would empty the pending `apply-fixes` batch (it used to refuse
    ruling-attempt-pending)."""
    session_dir, _, _, row_a, row_b = _pending_apply_fixes_two_findings(tmp_path)
    id_a = row_a.get("id") or RD._fix_batch_row_key(row_a)
    id_b = row_b.get("id") or RD._fix_batch_row_key(row_b)
    before = _state(session_dir)
    out = _rule(session_dir, _write_ruling_file(tmp_path / "r.json", [
        {"id": id_a, "ruling": "out-of-scope", "reason": "a", "followUp": _follow_up()},
        {"id": id_b, "ruling": "out-of-scope", "reason": "b", "followUp": _follow_up()}]))
    assert out.get("ok") is True, out
    after = _state(session_dir)
    assert len(after["rulingsLog"]) == len(before.get("rulingsLog") or []) + 2


def test_edge8_empty_batch_advances(tmp_path):
    """axis: pre-emission out-of-scope on every remaining fix row settles via empty-batch convergence."""
    session_dir, _, _, row_a, row_b = _pending_apply_fixes_two_findings(tmp_path)
    state = _state(session_dir)
    state["pending"] = None
    RD.save_state(session_dir, state)
    id_a = row_a.get("id") or RD._fix_batch_row_key(row_a)
    id_b = row_b.get("id") or RD._fix_batch_row_key(row_b)
    out = _rule(session_dir, _write_ruling_file(tmp_path / "r.json", [
        {"id": id_a, "ruling": "out-of-scope", "reason": "a", "followUp": _follow_up()},
        {"id": id_b, "ruling": "out-of-scope", "reason": "b", "followUp": _follow_up()}]))
    assert out.get("ok"), out
    state = _state(session_dir)
    assert state.get("terminal") == "converged"
    assert state.get("step") == RD.P_TERMINAL


def test_preemission_out_of_scope_drops_current_fix_batch_row(tmp_path):
    """axis: a pre-emission out-of-scope ruling drops the target from `_fixBatch` before the next emit."""
    session_dir, _, _, row_a, row_b = _pending_apply_fixes_two_findings(tmp_path)
    state = _state(session_dir)
    state["pending"] = None
    RD.save_state(session_dir, state)
    key_a = RD._fix_batch_row_key(row_a)
    id_a = row_a.get("id") or key_a
    out = _rule(session_dir, _write_ruling_file(tmp_path / "r.json", [
        {"id": id_a, "ruling": "out-of-scope", "reason": "defer A",
         "followUp": _follow_up()}]))
    assert out.get("ok"), out
    state = _state(session_dir)
    batch_keys = {RD._fix_batch_row_key(row) for row in (state.get("_fixBatch") or [])
                  if isinstance(row, dict)}
    assert key_a not in batch_keys
    nxt = RD.cmd_next(session_dir)
    assert nxt.get("ok"), nxt
    payload_keys = {
        RD._fix_batch_row_key(row)
        for row in ((nxt.get("payload") or {}).get("batch") or [])
        if isinstance(row, dict)}
    assert key_a not in payload_keys


def test_out_of_scope_queue_row_absent_after_the_apply_fixes_fold(tmp_path):
    """axis: live out-of-scope keys are excluded from the post-fold fix-batch re-slice.

    bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo_rulings_channel_1445.md (BP-2)
    """
    session_dir, gitdir, head_path, row_a, row_b = _pending_apply_fixes_two_findings(tmp_path)
    state = _state(session_dir)
    state["pending"] = None
    RD.save_state(session_dir, state)
    key_b = RD._fix_batch_row_key(row_b)
    id_b = row_b.get("id") or key_b
    out = _rule(session_dir, _write_ruling_file(tmp_path / "r.json", [
        {"id": id_b, "ruling": "out-of-scope", "reason": "defer B",
         "followUp": _follow_up()}]))
    assert out.get("ok"), out
    state = _state(session_dir)
    scheduled = {RD._fix_batch_row_key(row)
                 for row in list(state.get("_fixBatch") or []) + list(state.get("_fixQueue") or [])
                 if isinstance(row, dict)}
    assert key_b not in scheduled
    nxt = RD.cmd_next(session_dir)
    assert nxt.get("ok"), nxt
    phase, adv = _drive_one_phase(session_dir, gitdir, [], head_path)
    assert phase == P_APPLY_FIXES
    assert adv.get("ok"), adv
    state = _state(session_dir)
    later = {RD._fix_batch_row_key(row)
             for row in list(state.get("_fixBatch") or []) + list(state.get("_fixQueue") or [])
             if isinstance(row, dict)}
    assert key_b not in later
    for rnd in (1, 2, state.get("round")):
        if not isinstance(rnd, int):
            continue
        batch1 = os.path.join(RR.round_dir(session_dir, rnd), "fix-batch.1.json")
        if not os.path.isfile(batch1):
            continue
        with open(batch1, encoding="utf-8") as fh:
            doc = json.load(fh)
        keys = {RD._fix_batch_row_key(row) or row.get("id")
                for row in (doc if isinstance(doc, list) else [])
                if isinstance(row, dict)}
        assert key_b not in keys


def test_edge9_non_apply_fixes_step_accepts_guidance(tmp_path):
    """axis: guidance is accepted at a step that is not the `apply-fixes` step (it used to be refused)."""
    session_dir, gitdir, head_path, row_a, _ = _pending_apply_fixes_two_findings(tmp_path)
    state = _state(session_dir)
    rnd = state["round"]
    pend = {"action": RD.P_AUDITS, "round": rnd, "phase": RD.P_AUDITS, "attempt": 0,
            "payload": {"targets": state.get("_auditTargets") or []}}
    state["pending"] = pend
    state["step"] = RD.P_AUDITS
    RD.save_state(session_dir, state)
    roster, _ = __import__("round_adapters").roster_for(
        RD.P_AUDITS, state, state.get("config") or {})
    _write_dispatch_manifest(session_dir, pend, _slots_of(roster), _auditor_vendor_for(state))
    id_a = row_a.get("id") or RD._fix_batch_row_key(row_a)
    log_before = len(_state(session_dir).get("rulingsLog") or [])
    out = _rule(session_dir, _write_ruling_file(tmp_path / "r.json", [
        {"id": id_a, "ruling": "guidance", "reason": "r", "guidance": "g"}]))
    assert out.get("ok") is True, out
    log_after = _state(session_dir)["rulingsLog"]
    assert len(log_after) == log_before + 1 and log_after[-1]["ruling"] == "guidance"


def _owner_absent(state):
    state.pop(session_contract.DISPOSITION_LEDGER_OWNER_FIELD, None)


def test_rule_refuses_malformed_rulings_log(tmp_path):
    session_dir, _, _, row_a, _ = _pending_apply_fixes_two_findings(tmp_path)
    state = _state(session_dir)
    state["rulingsLog"] = {"not": "a-list"}
    RD.save_state(session_dir, state)
    id_a = row_a.get("id") or RD._fix_batch_row_key(row_a)
    before = _state_bytes(session_dir)
    out = _rule(session_dir, _write_ruling_file(tmp_path / "r.json", [
        {"id": id_a, "ruling": "guidance", "reason": "r", "guidance": "g"}]))
    assert out.get("ok") is False, out
    assert out.get("reason") == RD.RULINGS_LOG_MALFORMED, out
    assert _state_bytes(session_dir) == before


def test_rule_refuses_malformed_ruling_seq_counter(tmp_path):
    session_dir, _, _, row_a, _ = _pending_apply_fixes_two_findings(tmp_path)
    state = _state(session_dir)
    state["rulingSeqCounter"] = "not-an-int"
    RD.save_state(session_dir, state)
    id_a = row_a.get("id") or RD._fix_batch_row_key(row_a)
    before = _state_bytes(session_dir)
    out = _rule(session_dir, _write_ruling_file(tmp_path / "r.json", [
        {"id": id_a, "ruling": "guidance", "reason": "r", "guidance": "g"}]))
    assert out.get("ok") is False, out
    assert out.get("reason") == RD.RULINGS_LOG_MALFORMED, out
    assert _state_bytes(session_dir) == before


@pytest.mark.parametrize("bad_log", [{"not": "a-list"}, None])
def test_rule_refuses_malformed_rulings_log_owner_absent(tmp_path, bad_log):
    session_dir, _, _, row_a, _ = _pending_apply_fixes_two_findings(tmp_path)
    state = _state(session_dir)
    _owner_absent(state)
    state["rulingsLog"] = bad_log
    RD.save_state(session_dir, state)
    id_a = row_a.get("id") or RD._fix_batch_row_key(row_a)
    before = _state_bytes(session_dir)
    out = _rule(session_dir, _write_ruling_file(tmp_path / "r.json", [
        {"id": id_a, "ruling": "guidance", "reason": "r", "guidance": "g"}]))
    assert out.get("ok") is False, out
    assert out.get("reason") == RD.RULINGS_LOG_MALFORMED, out
    assert _state_bytes(session_dir) == before


def test_rule_refuses_malformed_ruling_seq_counter_owner_absent(tmp_path):
    session_dir, _, _, row_a, _ = _pending_apply_fixes_two_findings(tmp_path)
    state = _state(session_dir)
    _owner_absent(state)
    state["rulingSeqCounter"] = "not-an-int"
    RD.save_state(session_dir, state)
    id_a = row_a.get("id") or RD._fix_batch_row_key(row_a)
    before = _state_bytes(session_dir)
    out = _rule(session_dir, _write_ruling_file(tmp_path / "r.json", [
        {"id": id_a, "ruling": "guidance", "reason": "r", "guidance": "g"}]))
    assert out.get("ok") is False, out
    assert out.get("reason") == RD.RULINGS_LOG_MALFORMED, out
    assert _state_bytes(session_dir) == before


def test_preemission_ruling_journal_carries_round_phase(tmp_path):
    session_dir, _, _, row_a, _ = _pending_apply_fixes_two_findings(tmp_path)
    state = _state(session_dir)
    session_round = state["round"]
    session_step = state.get("step")
    state["pending"] = None
    RD.save_state(session_dir, state)
    id_a = row_a.get("id") or RD._fix_batch_row_key(row_a)
    out = _rule(session_dir, _write_ruling_file(tmp_path / "r.json", [
        {"id": id_a, "ruling": "out-of-scope", "reason": "defer",
         "followUp": _follow_up()}]))
    assert out.get("ok"), out
    rows = [e for e in RD.read_journal(session_dir)
            if e.get("cmd") == RD.RULE_CMD and e.get("outcome") == "ruling-recorded"]
    assert rows, "expected ruling-recorded journal row"
    row = rows[-1]
    assert row.get("round") == session_round
    assert row.get("phase") == session_step
    assert row.get("attempt") is None


def test_receipt_parity_rulings_field(tmp_path):
    session_dir, _, _, row_a, _ = _pending_apply_fixes_two_findings(tmp_path)
    id_a = row_a.get("id") or RD._fix_batch_row_key(row_a)
    assert _rule(session_dir, _write_ruling_file(tmp_path / "r.json", [
        {"id": id_a, "ruling": "guidance", "reason": "r", "guidance": "g"}]))["ok"]
    state = _state(session_dir)
    driver_receipt = RD.build_receipt(state, session_dir=session_dir)
    rnd = str(state["round"])
    assert driver_receipt["rounds"][0].get("rulings") == state["rounds"][rnd].get("rulings")


def test_binding_ruling_rides_the_apply_fixes_files_and_certifies(tmp_path):
    session_dir, gitdir, head_path, row_a, row_b = _pending_apply_fixes_two_findings(tmp_path)
    id_a = row_a.get("id") or RD._fix_batch_row_key(row_a)
    id_b = row_b.get("id") or RD._fix_batch_row_key(row_b)
    path = _write_ruling_file(tmp_path / "r.json", [
        {"id": id_a, "ruling": "guidance", "reason": "fix A", "guidance": "apply guard A"},
        {"id": id_b, "ruling": "out-of-scope", "reason": "defer B",
         "followUp": _follow_up()}])
    out = _rule(session_dir, path)
    assert out.get("ok"), out
    state = _state(session_dir)
    state["pending"] = None
    RD.save_state(session_dir, state)
    nxt = RD.cmd_next(session_dir)
    assert nxt.get("ok"), nxt
    state = _state(session_dir)
    pend = state["pending"]
    key_b = RD._fix_batch_row_key(row_b)
    batch_path = pend["payload"]["fixBatchPath"]
    with open(batch_path, encoding="utf-8") as fh:
        batch_doc = json.load(fh)
    batch_keys = {
        RD._fix_batch_row_key(row) or row.get("id")
        for row in (batch_doc if isinstance(batch_doc, list) else [])
        if isinstance(row, dict)}
    assert key_b not in batch_keys
    assert "apply guard A" in _apply_fixes_text(session_dir)
    while not _state(session_dir).get("terminal"):
        phase, out = _drive_one_phase(session_dir, gitdir, [], head_path)
        assert out.get("ok"), (phase, out)
    terminal = _state(session_dir)
    assert terminal.get("terminal") == "converged", terminal.get("certification")
    receipt = RD.build_receipt(terminal, session_dir=session_dir)
    round_rulings = [v.get("rulings") for v in (terminal.get("rounds") or {}).values()
                     if v.get("rulings")]
    assert round_rulings, terminal.get("rounds")
    receipt_rulings = [r.get("rulings") for r in receipt.get("rounds") or [] if r.get("rulings")]
    assert receipt_rulings
    assert receipt_rulings[0] == round_rulings[0]
