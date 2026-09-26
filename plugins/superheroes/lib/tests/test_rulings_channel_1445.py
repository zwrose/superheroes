"""#1445 WO-1 — owner/advisor rulings channel (`rule` verb)."""
import hashlib
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
_dispatch_observed_land = _TRI._dispatch_observed_land
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
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="rulings-1445", fixBatchCap=1)
    _drive_to_phase(session_dir, gitdir, [f_a, f_b], head_path, P_FIXER)
    state = _state(session_dir)
    assert state["pending"]["phase"] == P_FIXER
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
    ("ruling-attempt-recorded", "attempt_recorded"),
])
def test_rule_refusal_tokens(tmp_path, token, setup):
    session_dir, gitdir, head_path, row_a, row_b = _pending_fixer_two_findings(tmp_path)
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
        before = _state_bytes(session_dir)
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


def test_critical_restage_not_suppressed_by_stale_out_of_scope(tmp_path):
    session_dir, _, _, row_a, row_b = _pending_fixer_two_findings(tmp_path)
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


def test_rule_supersession_closes_prior_fixer_attempt_for_certification(tmp_path):
    f_a = _blocking_finding("bounds A", 2)
    f_b = _blocking_finding("bounds B", 3)
    f_b["severity"] = "Minor"
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="rule-super", fixBatchCap=2)
    _drive_to_phase(session_dir, gitdir, [f_a, f_b], head_path, P_FIXER)
    row_b = (_state(session_dir).get("_fixBatch") or [None, {}])[1]
    id_b = row_b.get("id") or RD._fix_batch_row_key(row_b)
    out = _rule(session_dir, _write_ruling_file(tmp_path / "r.json", [
        {"id": id_b, "ruling": "out-of-scope", "reason": "defer B",
         "followUp": _follow_up()}]))
    assert out.get("ok"), out
    assert out.get("superseded")
    journal = RD.read_journal(session_dir)
    unclosed, refusal = RC._journal_open_seats(journal, session_dir)
    assert refusal is None
    fixer_open = [k for k, _ in unclosed if k[0] == P_FIXER]
    assert not fixer_open


def test_edge5_aggregate_cap_refuses_ruling_omitted(tmp_path):
    f_a = _blocking_finding("cap A", 2)
    f_b = _blocking_finding("cap B", 3)
    f_b["severity"] = "Minor"
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="edge5-cap", fixBatchCap=4)
    _drive_to_phase(session_dir, gitdir, [f_a, f_b], head_path, P_FIXER)
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
    assert out.get("pendingCleared") is True
    state = _state(session_dir)
    assert state.get("pending") is None
    superseded_rows = [
        row for row in RD.read_journal(session_dir)
        if row.get("outcome") == session_contract.ORDERS_SUPERSEDED_OUTCOME
        and row.get("reason") == "ruling-emptied-batch"]
    assert len(superseded_rows) == 1
    assert "newAttempt" not in superseded_rows[0]
    nxt = RD.cmd_next(session_dir)
    assert nxt.get("ok"), nxt
    after = _state(session_dir)
    pend = after.get("pending") or {}
    assert pend.get("phase") != P_FIXER or after.get("terminal")


def test_fix_batch_unreadable_refuses_order_render(tmp_path, monkeypatch):
    session_dir, _, _, _, _ = _pending_fixer_two_findings(tmp_path)
    state = _state(session_dir)
    rnd = state["round"]
    missing = str(tmp_path / "no-such-fix-batch.json")

    def _broken_ensure(_session_dir, _rnd, _state):
        return missing

    monkeypatch.setattr(RD, "_ensure_fix_batch_file", _broken_ensure)
    with pytest.raises(ValueError, match="order-render-refused:fix-batch-unreadable"):
        RD._fix_batch_file_sha256(session_dir, rnd, state)


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


def test_fixer_order_pins_fix_batch_sha256(tmp_path):
    f_a = _blocking_finding("bounds A", 2)
    f_b = _blocking_finding("bounds B", 3)
    f_b["severity"] = "Minor"
    session_dir, gitdir, head_path = _bootstrap(
        tmp_path, name="rulings-1445-sha", fixBatchCap=2)
    _drive_to_phase(session_dir, gitdir, [f_a, f_b], head_path, P_FIXER)
    state = _state(session_dir)
    pend = state["pending"]
    rnd = pend["round"]
    batch_path = RD._ensure_fix_batch_file(session_dir, rnd, state)
    with open(batch_path, "rb") as fh:
        batch_sha = hashlib.sha256(fh.read()).hexdigest()
    order_text = _fixer_order_text(session_dir)
    sha_line_before = f"- Fix batch sha256: {batch_sha}"
    assert sha_line_before in order_text
    row_b = (state.get("_fixBatch") or [None, {}])[1]
    if not isinstance(row_b, dict):
        row_b = (state.get("_fixQueue") or [{}])[0]
    id_b = row_b.get("id") or RD._fix_batch_row_key(row_b)
    assert _rule(session_dir, _write_ruling_file(tmp_path / "r.json", [
        {"id": id_b, "ruling": "out-of-scope", "reason": "defer B",
         "followUp": _follow_up()}]))["ok"]
    state = _state(session_dir)
    batch_path = RD._ensure_fix_batch_file(session_dir, rnd, state)
    with open(batch_path, "rb") as fh:
        batch_sha_after = hashlib.sha256(fh.read()).hexdigest()
    assert batch_sha_after != batch_sha
    order_after = _fixer_order_text(session_dir)
    sha_line_after = f"- Fix batch sha256: {batch_sha_after}"
    assert sha_line_after in order_after
    assert sha_line_after != sha_line_before


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
    pend = state["pending"]
    roster, _ = __import__("round_adapters").roster_for(
        pend["phase"], state, state.get("config") or {})
    seat, occurrence = RR.roster_slots(roster)[0]
    skey = RR.storage_key(seat, occurrence)
    order_path = RR.order_prompt_path(
        session_dir, pend["round"], pend["phase"], skey, pend["attempt"])
    with open(order_path, "rb") as fh:
        driver_order_bytes = fh.read()
    _manifest_sha, anchored_order_sha = _anchor_hashes(
        session_dir, state, pend, seat, occurrence)
    driver_order_sha = hashlib.sha256(driver_order_bytes).hexdigest()
    assert driver_order_sha == anchored_order_sha
    driver_order_text = driver_order_bytes.decode("utf-8")
    key_b = RD._fix_batch_row_key(row_b)
    batch_path = RD._ensure_fix_batch_file(session_dir, pend["round"], state)
    with open(batch_path, encoding="utf-8") as fh:
        batch_doc = json.load(fh)
    batch_keys = {
        RD._fix_batch_row_key(row) or row.get("id")
        for row in (batch_doc if isinstance(batch_doc, list) else [])
        if isinstance(row, dict)}
    assert key_b not in batch_keys
    order_text = _fixer_order_text(session_dir)
    log_rows = state.get("rulingsLog") or []
    prompt = _deliver_rulings(order_text, log_rows)
    delivered_path = tmp_path / "delivered-fixer-order.md"
    delivered_path.write_text(prompt, encoding="utf-8")
    run_dir = _write_execution_run_dir(tmp_path, str(delivered_path), echo_nonce="rulings-bind")
    payload = _TRI._payload_for(session_dir, state, pend, seat, [], head_path)
    _dispatch_observed_land(session_dir, state, pend, seat, payload, occurrence=occurrence)
    rec_out = RD.cmd_record_result(session_dir, seat, occurrence=occurrence,
                                   evidence_run_dir=run_dir)
    assert rec_out.get("ok"), rec_out
    assert "apply guard A" in driver_order_text
    adv = RD.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert adv.get("ok"), adv
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
