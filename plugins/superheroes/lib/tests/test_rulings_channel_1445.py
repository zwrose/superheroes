"""#1445 WO-1 — owner/advisor rulings channel (`rule` verb)."""
import importlib.util
import json
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_certification as RC  # noqa: E402
import round_driver as RD  # noqa: E402
import round_records as RR  # noqa: E402
import session_contract  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "test_round_driver_integration",
    os.path.join(_HERE, "test_round_driver_integration.py"))
_TRI = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_TRI)

_bootstrap = _TRI._bootstrap
_blocking_finding = _TRI._blocking_finding
_state = _TRI._state
_fake_git = _TRI._fake_git
_drive_to_phase = _TRI._drive_to_phase
_drive_one_phase = _TRI._drive_one_phase
_write_execution_run_dir = _TRI._write_execution_run_dir
_fixer_envelope_for_write_run = _TRI._fixer_envelope_for_write_run
_anchor_hashes = _TRI._anchor_hashes
_land = _TRI._land
_write_dispatch_manifest = _TRI._write_dispatch_manifest
_slots_of = _TRI._slots_of
_auditor_vendor_for = _TRI._auditor_vendor_for

P_FIXER = RD.P_FIXER
STATE_PATH = session_contract.STATE_FILE


def _state_bytes(session_dir):
    with open(os.path.join(session_dir, STATE_PATH), "rb") as fh:
        return fh.read()


def _provenance():
    return {"ruledBy": "owner", "ruledAt": "2026-08-26T00:00:00Z", "records": ["rulings.json"]}


def _follow_up():
    return {"item": "backlog item", "revisitTrigger": "next milestone"}


def _write_ruling_file(path, entries, *, provenance=None):
    doc = {"_provenance": provenance if provenance is not None else _provenance(),
           "rulings": entries}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    return path


def _rule(session_dir, ruling_path, by="owner"):
    return RD.cmd_rule(session_dir, ruling_path, by)


def _fixer_order_text(session_dir):
    state = _state(session_dir)
    pend = state["pending"]
    assert pend["phase"] == P_FIXER
    roster, reason = __import__("round_adapters").roster_for(
        pend["phase"], state, state.get("config") or {})
    assert reason is None
    seat, occurrence = __import__("round_records").roster_slots(roster)[0]
    cfg = state.get("config") or {}
    repo_root = cfg.get("repoRoot") or os.getcwd()
    row = RD._seat_transport_row(state, pend["phase"], seat, occurrence, cfg,
                                 pend.get("payload") or {}, repo_root)
    ctx, _paths = RD._build_order_render_context(
        session_dir, state, pend["round"], pend["phase"], pend["attempt"],
        seat, occurrence, pend.get("payload") or {}, row, roster=roster)
    import round_orders as RO
    text, render_reason = RO.render_order(pend["phase"], seat, ctx)
    assert render_reason is None, render_reason
    return text


def _deliver_rulings(order_text, rulings):
    """Operator-style appendix when the hashed order already carries rulings."""
    guidance_ok = all(
        isinstance(r.get("guidance"), str) and r["guidance"] in order_text
        for r in rulings if r.get("ruling") == "guidance")
    sha_match = re.search(r"Fix batch sha256: ([0-9a-f]{64})", order_text)
    batch_path_match = re.search(r"Findings to fix: (.+?) \(", order_text)
    batch_ok = True
    if sha_match and batch_path_match:
        batch_path = batch_path_match.group(1).strip()
        try:
            with open(batch_path, encoding="utf-8") as fh:
                batch_doc = json.load(fh)
        except (OSError, ValueError):
            batch_ok = False
        else:
            oos_keys = {r.get("findingKey") or r.get("id") for r in rulings
                        if r.get("ruling") == "out-of-scope"}
            for row in batch_doc if isinstance(batch_doc, list) else []:
                key = RD._fix_batch_row_key(row) or row.get("id")
                if key in oos_keys:
                    batch_ok = False
                    break
    if guidance_ok and batch_ok:
        return order_text
    appendix = "\n\n## Rulings\n" + json.dumps(rulings, indent=2)
    return order_text + appendix


def _pending_fixer_two_findings(tmp_path):
    f_a = _blocking_finding("bounds A", 2)
    f_b = _blocking_finding("bounds B", 3)
    f_b["severity"] = "Minor"
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="rulings-1445")
    _drive_to_phase(session_dir, gitdir, [f_a, f_b], head_path, P_FIXER)
    state = _state(session_dir)
    assert state["pending"]["phase"] == P_FIXER
    batch = state.get("_fixBatch") or []
    assert len(batch) >= 2
    return session_dir, gitdir, head_path, batch[0], batch[1]


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
    ("ruling-attempt-recorded", "attempt_recorded"),
])
def test_rule_refusal_tokens(tmp_path, token, setup):
    session_dir, gitdir, head_path, row_a, row_b = _pending_fixer_two_findings(tmp_path)
    before = _state_bytes(session_dir)
    ruling_path = tmp_path / "rulings.json"
    id_a = row_a.get("id") or RD._fix_batch_row_key(row_a)
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
        out = _rule(session_dir, str(ruling_path))
    elif setup == "terminal":
        state = _state(session_dir)
        state["terminal"] = True
        RD.save_state(session_dir, state)
        _write_ruling_file(ruling_path, [{"id": id_a, "ruling": "guidance",
                                           "reason": "r", "guidance": "g"}])
        out = _rule(session_dir, str(ruling_path))
    elif setup == "attempt_recorded":
        state = _state(session_dir)
        pend = state["pending"]
        roster, _ = __import__("round_adapters").roster_for(
            pend["phase"], state, state.get("config") or {})
        seat, occurrence = RR.roster_slots(roster)[0]
        _write_dispatch_manifest(session_dir, pend, _slots_of(roster), _auditor_vendor_for(state))
        payload = {"fixes": [], "headDiff": "diff --git a/x b/x\n"}
        _land(session_dir, state, pend, seat, payload, occurrence=occurrence)
        _write_ruling_file(ruling_path, [{"id": id_a, "ruling": "guidance",
                                           "reason": "r", "guidance": "g"}])
        out = _rule(session_dir, str(ruling_path))
    else:
        pytest.fail("unknown setup")
    assert out.get("ok") is False, out
    assert out.get("reason") == token, out
    assert _state_bytes(session_dir) == before


def test_edge2_ruling_off_batch_logged(tmp_path):
    session_dir, gitdir, head_path, row_a, row_b = _pending_fixer_two_findings(tmp_path)
    id_b = row_b.get("id") or RD._fix_batch_row_key(row_b)
    path = _write_ruling_file(tmp_path / "r.json", [
        {"id": id_b, "ruling": "guidance", "reason": "defer", "guidance": "only fix A"}])
    out = _rule(session_dir, path)
    assert out.get("ok"), out
    state = _state(session_dir)
    assert any(r.get("findingKey") == RD._fix_batch_row_key(row_b)
               for r in state.get("rulingsLog") or [])


def test_edge3_restage_reapplies_out_of_scope(tmp_path):
    session_dir, gitdir, head_path, row_a, row_b = _pending_fixer_two_findings(tmp_path)
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
    session_dir, _, _, row_a, row_b = _pending_fixer_two_findings(tmp_path)
    id_b = row_b.get("id") or RD._fix_batch_row_key(row_b)
    p1 = _write_ruling_file(tmp_path / "r1.json", [
        {"id": id_b, "ruling": "out-of-scope", "reason": "skip",
         "followUp": _follow_up()}])
    assert _rule(session_dir, p1)["ok"]
    p2 = _write_ruling_file(tmp_path / "r2.json", [
        {"id": id_b, "ruling": "guidance", "reason": "fix now", "guidance": "use guard X"}])
    assert _rule(session_dir, p2)["ok"]
    assert id_b not in RD._live_out_of_scope_ruling_keys(_state(session_dir))


def test_edge5_aggregate_cap_refuses_ruling_omitted(tmp_path):
    session_dir, _, _, row_a, _row_b = _pending_fixer_two_findings(tmp_path)
    state = _state(session_dir)
    rnd = state["round"]
    huge = "z" * (RD.GATE_GUIDANCE_AGGREGATE_BYTE_CAP + 100)
    state.setdefault("rounds", {}).setdefault(str(rnd), {})["judgmentDispositions"] = [
        {"disposition": "fix-with-guidance", "id": "fill", "guidance": huge,
         "title": "t", "file": "f.py", "line": 1}]
    RD.save_state(session_dir, state)
    id_a = row_a.get("id") or RD._fix_batch_row_key(row_a)
    path = _write_ruling_file(tmp_path / "r.json", [
        {"id": id_a, "ruling": "guidance", "reason": "cap", "guidance": "must appear whole"}])
    out = _rule(session_dir, path)
    assert out.get("ok") is False
    assert out.get("reason") == "order-render-refused"
    assert "ruling-guidance-omitted" in str(out.get("detail", ""))


def test_edge6_two_rule_calls_append(tmp_path):
    session_dir, _, _, row_a, row_b = _pending_fixer_two_findings(tmp_path)
    id_a = row_a.get("id") or RD._fix_batch_row_key(row_a)
    id_b = row_b.get("id") or RD._fix_batch_row_key(row_b)
    assert _rule(session_dir, _write_ruling_file(tmp_path / "r1.json", [
        {"id": id_a, "ruling": "guidance", "reason": "a", "guidance": "ga"}]))["ok"]
    assert _rule(session_dir, _write_ruling_file(tmp_path / "r2.json", [
        {"id": id_b, "ruling": "guidance", "reason": "b", "guidance": "gb"}]))["ok"]
    rec = _state(session_dir)["rounds"][str(_state(session_dir)["round"])]
    assert len(rec.get("rulings") or []) == 2


def test_edge7_guidance_off_batch_no_supersede(tmp_path):
    session_dir, _, _, row_a, row_b = _pending_fixer_two_findings(tmp_path)
    state = _state(session_dir)
    attempt_before = state["pending"]["attempt"]
    id_b = row_b.get("id") or RD._fix_batch_row_key(row_b)
    out = _rule(session_dir, _write_ruling_file(tmp_path / "r.json", [
        {"id": id_b, "ruling": "guidance", "reason": "off batch", "guidance": "later"}]))
    assert out.get("ok"), out
    assert "superseded" not in out
    assert _state(session_dir)["pending"]["attempt"] == attempt_before


def test_edge8_empty_batch_advances(tmp_path):
    session_dir, _, _, row_a, row_b = _pending_fixer_two_findings(tmp_path)
    id_a = row_a.get("id") or RD._fix_batch_row_key(row_a)
    id_b = row_b.get("id") or RD._fix_batch_row_key(row_b)
    out = _rule(session_dir, _write_ruling_file(tmp_path / "r.json", [
        {"id": id_a, "ruling": "out-of-scope", "reason": "a", "followUp": _follow_up()},
        {"id": id_b, "ruling": "out-of-scope", "reason": "b", "followUp": _follow_up()}]))
    assert out.get("ok"), out
    state = _state(session_dir)
    assert state["pending"]["phase"] != P_FIXER or not (state.get("_fixBatch") or [])


def test_edge9_non_fixer_pending_no_supersede(tmp_path):
    session_dir, gitdir, head_path, _, _ = _pending_fixer_two_findings(tmp_path)
    state = _state(session_dir)
    state["pending"] = {"action": RD.P_AUDITS, "round": state["round"],
                        "phase": RD.P_AUDITS, "attempt": 0, "payload": {}}
    RD.save_state(session_dir, state)
    id_a = (state.get("_fixBatch") or [{}])[0]
    id_a = id_a.get("id") if isinstance(id_a, dict) else "x"
    out = _rule(session_dir, _write_ruling_file(tmp_path / "r.json", [
        {"id": id_a, "ruling": "guidance", "reason": "r", "guidance": "g"}]))
    assert out.get("ok"), out
    assert "superseded" not in out


def test_receipt_parity_rulings_field(tmp_path):
    session_dir, _, _, row_a, _ = _pending_fixer_two_findings(tmp_path)
    id_a = row_a.get("id") or RD._fix_batch_row_key(row_a)
    assert _rule(session_dir, _write_ruling_file(tmp_path / "r.json", [
        {"id": id_a, "ruling": "guidance", "reason": "r", "guidance": "g"}]))["ok"]
    state = _state(session_dir)
    driver_receipt = RD.build_receipt(state, session_dir=session_dir)
    cert_rounds = RC._build_receipt_rounds(state, RC.RECEIPT_FORM_CERTIFIED)
    rnd = str(state["round"])
    assert driver_receipt["rounds"][0].get("rulings") == state["rounds"][rnd].get("rulings")
    assert cert_rounds[0].get("rulings") == state["rounds"][rnd].get("rulings")


def test_binding_ruling_rides_hashed_order_and_certifies(tmp_path):
    session_dir, gitdir, head_path, row_a, row_b = _pending_fixer_two_findings(tmp_path)
    id_a = row_a.get("id") or RD._fix_batch_row_key(row_a)
    id_b = row_b.get("id") or RD._fix_batch_row_key(row_b)
    path = _write_ruling_file(tmp_path / "r.json", [
        {"id": id_a, "ruling": "guidance", "reason": "fix A", "guidance": "apply guard A"},
        {"id": id_b, "ruling": "out-of-scope", "reason": "defer B",
         "followUp": _follow_up()}])
    out = _rule(session_dir, path)
    assert out.get("ok"), out
    state = _state(session_dir)
    order_text = _fixer_order_text(session_dir)
    log_rows = state.get("rulingsLog") or []
    prompt = _deliver_rulings(order_text, log_rows)
    pend = state["pending"]
    roster, _ = __import__("round_adapters").roster_for(
        pend["phase"], state, state.get("config") or {})
    seat, occurrence = RR.roster_slots(roster)[0]
    order_path = RR.order_path(session_dir, pend["round"], pend["phase"], seat,
                               pend["attempt"], occurrence)
    run_dir = _write_execution_run_dir(tmp_path, order_path, echo_nonce="rulings-bind")
    with open(os.path.join(run_dir, "prompt.txt"), "w", encoding="utf-8") as fh:
        fh.write(prompt)
    manifest_sha, order_sha = _anchor_hashes(session_dir, state, pend, seat, occurrence)
    record = {"storePath": RR.store_path(session_dir, pend["round"], pend["phase"],
                                          RR.storage_key(seat, occurrence), pend["attempt"])}
    envelope = _fixer_envelope_for_write_run(record, order_sha=order_sha)
    rec_out = RD.cmd_record_result(session_dir, seat, occurrence=occurrence,
                                   evidence_run_dir=run_dir)
    assert rec_out.get("ok"), rec_out
    raise AssertionError(
        "binding test: fixer record-result accepted but certified terminal not reached in this budget")
