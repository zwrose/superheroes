"""#2137 WO-A — a late ruling re-renders a fixer order nobody has picked up (`rule --fixer-not-dispatched`)."""
import importlib.util
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_driver as RD  # noqa: E402
import round_records as RR  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "test_rulings_channel_1445", os.path.join(_HERE, "test_rulings_channel_1445.py"))
_RC = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_RC)

_pending_fixer_two_findings = _RC._pending_fixer_two_findings
_write_ruling_file = _RC._write_ruling_file
_follow_up = _RC._follow_up
_state = _RC._state
_state_bytes = _RC._state_bytes
_blocking_finding = _RC._blocking_finding
_bootstrap = _RC._bootstrap
_drive_to_phase = _RC._drive_to_phase

P_FIXER = RD.P_FIXER


def _row_id(row):
    return row.get("id") or RD._fix_batch_row_key(row)


def _batch_keys(batch):
    return [RD._fix_batch_row_key(row) or row.get("id") for row in batch]


def _rule(session_dir, path, **kwargs):
    return RD.cmd_rule(session_dir, str(path), "owner", **kwargs)


def _oos(tmp_path, row, name="r.json"):
    return _write_ruling_file(tmp_path / name, [
        {"id": _row_id(row), "ruling": "out-of-scope", "reason": "defer",
         "followUp": _follow_up()}])


def _manifest(session_dir, rnd, attempt):
    with open(RD._orders_manifest_path(session_dir, rnd, P_FIXER, attempt),
              encoding="utf-8") as fh:
        return json.load(fh)


def _order_text_of(session_dir, rnd, attempt):
    seats = _manifest(session_dir, rnd, attempt)["seats"]
    assert seats
    with open(next(iter(seats.values()))["orderPath"], encoding="utf-8") as fh:
        return fh.read()


def _slot_paths(session_dir, state, rnd, attempt):
    roster, refusal = RD._roster_of(session_dir, state, RD.RULE_CMD, P_FIXER, rnd, attempt)
    assert refusal is None
    out = []
    for seat_key, occurrence in RR.roster_slots(roster):
        skey = RR.storage_key(seat_key, occurrence)
        out.append((RR.store_path(session_dir, rnd, P_FIXER, skey, attempt),
                    RR.landing_path(session_dir, rnd, P_FIXER, skey, attempt),
                    RR.bare_payload_path(session_dir, rnd, P_FIXER, skey, attempt)))
    return out


def _untouched(session_dir, before, out, reason):
    assert out.get("ok") is True, out
    assert out["fixerOrder"] == {"reshaped": False, "attempt": before["pending"]["attempt"],
                                 "reason": reason}, out
    after = _state(session_dir)
    assert after["pending"] == before["pending"]
    assert after["_fixBatch"] == before["_fixBatch"]
    assert len(after["rulingsLog"]) == len(before.get("rulingsLog") or []) + 1


def test_flagged_ruling_reshapes_unpicked_order_at_next_attempt(tmp_path):
    """axis: a ruling with --fixer-not-dispatched on an emitted, unpicked-up fixer order re-slices the
    batch and emits a fresh order at attempt K+1 (one orders-emit commit), which `next` then re-emits."""
    session_dir, _, _, row_a, row_b = _pending_fixer_two_findings(tmp_path, fixer_orders_emitted=True)
    before = _state(session_dir)
    k = before["pending"]["attempt"]
    rnd = before["pending"]["round"]
    assert _batch_keys(before["pending"]["payload"]["batch"]) == _batch_keys([row_a])
    out = _rule(session_dir, _oos(tmp_path, row_a), fixer_not_dispatched=True)
    assert out.get("ok") is True, out
    fixer_order = out["fixerOrder"]
    assert fixer_order["commitCheck"] in ("clean", "unreadable")
    assert {k2: v for k2, v in fixer_order.items() if k2 != "commitCheck"} == {
        "reshaped": True, "attempt": k + 1, "supersededAttempt": k, "reason": "reshaped"}
    after = _state(session_dir)
    assert after["pending"]["phase"] == P_FIXER
    assert after["pending"]["attempt"] == k + 1
    keys = _batch_keys(after["pending"]["payload"]["batch"])
    assert _batch_keys([row_a])[0] not in keys
    assert _batch_keys([row_b])[0] in keys
    assert out["attempt"] == k + 1
    assert _manifest(session_dir, rnd, k + 1)["attempt"] == k + 1
    again = RD.cmd_next(session_dir)
    assert again["ok"] is True
    assert again["attempt"] == k + 1
    assert again["payload"] == after["pending"]["payload"]


def test_flagged_guidance_ruling_reaches_the_reemitted_order(tmp_path):
    """axis: guidance ruled on a row of the unpicked batch lands in the K+1 order text and was absent
    from the K order text."""
    session_dir, _, _, row_a, _ = _pending_fixer_two_findings(tmp_path, fixer_orders_emitted=True)
    k = _state(session_dir)["pending"]["attempt"]
    rnd = _state(session_dir)["pending"]["round"]
    guidance = "keep the bounds check inclusive, 2137-guidance"
    assert guidance not in _order_text_of(session_dir, rnd, k)
    out = _rule(session_dir, _write_ruling_file(tmp_path / "g.json", [
        {"id": _row_id(row_a), "ruling": "guidance", "reason": "g", "guidance": guidance}]),
        fixer_not_dispatched=True)
    assert out.get("ok") is True, out
    assert out["fixerOrder"]["reshaped"] is True
    assert out["fixerOrder"]["attempt"] == k + 1
    assert guidance in _order_text_of(session_dir, rnd, k + 1)
    assert guidance not in _order_text_of(session_dir, rnd, k)


def test_reshaped_attempt_k_can_no_longer_be_recorded(tmp_path):
    """axis: after a reshape the old attempt K is not the pending one, so record-result refuses it
    `attempt-not-pending`."""
    session_dir, _, _, row_a, _ = _pending_fixer_two_findings(tmp_path, fixer_orders_emitted=True)
    k = _state(session_dir)["pending"]["attempt"]
    out = _rule(session_dir, _oos(tmp_path, row_a), fixer_not_dispatched=True)
    assert out["fixerOrder"]["reshaped"] is True, out
    state = _state(session_dir)
    seat = RR.roster_slots(RD._roster_of(
        session_dir, state, RD.RULE_CMD, P_FIXER, state["pending"]["round"], k)[0])[0][0]
    rec = RD.cmd_record_result(session_dir, seat=seat, attempt=k)
    assert rec.get("ok") is False
    assert rec.get("reason") == "attempt-not-pending", rec


def test_flag_absent_leaves_the_emitted_order_alone(tmp_path):
    """axis: without --fixer-not-dispatched an emitted order is never reshaped; the ruling is
    recorded and the result says dispatch-not-ruled-out."""
    session_dir, _, _, row_a, _ = _pending_fixer_two_findings(tmp_path, fixer_orders_emitted=True)
    before = _state(session_dir)
    out = _rule(session_dir, _oos(tmp_path, row_a))
    _untouched(session_dir, before, out, "dispatch-not-ruled-out")


def test_landed_slot_file_leaves_the_emitted_order_alone(tmp_path):
    """axis: a landing file for the attempt-K fixer slot is pickup evidence; the flag then changes
    nothing and the result says fixer-landed."""
    session_dir, _, _, row_a, _ = _pending_fixer_two_findings(tmp_path, fixer_orders_emitted=True)
    before = _state(session_dir)
    landing = _slot_paths(session_dir, before, before["pending"]["round"],
                          before["pending"]["attempt"])[0][1]
    os.makedirs(os.path.dirname(landing), exist_ok=True)
    with open(landing, "w", encoding="utf-8") as fh:
        fh.write("{}")
    out = _rule(session_dir, _oos(tmp_path, row_a), fixer_not_dispatched=True)
    _untouched(session_dir, before, out, "fixer-landed")


def test_commits_past_emission_head_leave_the_emitted_order_alone(tmp_path, monkeypatch):
    """axis: commits past the order's emission head are pickup evidence; the flag then changes
    nothing and the result says fixer-committed."""
    session_dir, _, _, row_a, _ = _pending_fixer_two_findings(tmp_path, fixer_orders_emitted=True)
    before = _state(session_dir)
    monkeypatch.setattr(RD, "_fixer_unlanded_commits", lambda *a, **k: ["a" * 40])
    out = _rule(session_dir, _oos(tmp_path, row_a), fixer_not_dispatched=True)
    _untouched(session_dir, before, out, "fixer-committed")


def test_ruling_that_empties_the_batch_drops_the_fixer_pending(tmp_path):
    """axis: when the reshape re-slice leaves no fixer batch there is no K+1 order: the ruling is
    recorded in a rule-record commit and the result says batch-emptied."""
    session_dir, _, _, row_a, row_b = _pending_fixer_two_findings(tmp_path, fixer_orders_emitted=True)
    before = _state(session_dir)
    k = before["pending"]["attempt"]
    out = _rule(session_dir, _write_ruling_file(tmp_path / "both.json", [
        {"id": _row_id(row_a), "ruling": "out-of-scope", "reason": "a", "followUp": _follow_up()},
        {"id": _row_id(row_b), "ruling": "out-of-scope", "reason": "b", "followUp": _follow_up()}]),
        fixer_not_dispatched=True)
    assert out.get("ok") is True, out
    fixer_order = out["fixerOrder"]
    assert fixer_order["attempt"] is None
    assert fixer_order["reason"] == "batch-emptied"
    assert fixer_order["reshaped"] is True
    assert fixer_order["supersededAttempt"] == k
    after = _state(session_dir)
    pending = after.get("pending")
    assert not (isinstance(pending, dict) and pending.get("phase") == P_FIXER)
    assert len(after["rulingsLog"]) == len(before.get("rulingsLog") or []) + 2


def test_reshape_render_refusal_changes_nothing(tmp_path):
    """axis: a render refusal while re-emitting (aggregate guidance overflow) refuses `rule`, leaves
    loop-state.json byte-identical and writes no K+1 manifest."""
    f_a = _blocking_finding("cap A", 2)
    f_b = _blocking_finding("cap B", 3)
    f_b["severity"] = "Minor"
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="e4-cap", fixBatchCap=4)
    _drive_to_phase(session_dir, gitdir, [f_a, f_b], head_path, P_FIXER)
    state = _state(session_dir)
    row_a = (state.get("_fixBatch") or [])[0]
    rnd = state["round"]
    chunk = "z" * RD.GATE_GUIDANCE_ROW_BYTE_CAP
    state.setdefault("rounds", {}).setdefault(str(rnd), {})["judgmentDispositions"] = [
        {"disposition": "fix-with-guidance", "id": "gate-%d" % i,
         RD.GATE_GUIDANCE_RECORD_KEY: chunk, "title": "t", "file": "f.py", "line": i}
        for i in range(6)]
    RD.save_state(session_dir, state)
    k = _state(session_dir)["pending"]["attempt"]
    state_before = _state_bytes(session_dir)
    out = _rule(session_dir, _write_ruling_file(tmp_path / "r.json", [
        {"id": _row_id(row_a), "ruling": "guidance", "reason": "cap",
         "guidance": "must appear whole"}]), fixer_not_dispatched=True)
    assert out.get("ok") is False
    assert out.get("reason") == "order-render-refused"
    assert "ruling-guidance-omitted" in str(out.get("detail", ""))
    assert _state_bytes(session_dir) == state_before
    assert not os.path.exists(RD._orders_manifest_path(session_dir, rnd, P_FIXER, k + 1))


def test_reshape_render_refusal_restores_the_rewritten_batch_file(tmp_path, monkeypatch):
    """axis: the reshape re-slice rewrites fix-batch.json to the promoted row before the K+1 render;
    when that render refuses, `rule` is refused and fix-batch.json is back to its pre-ruling bytes
    with loop-state.json unchanged and no K+1 manifest."""
    session_dir, _, _, row_a, row_b = _pending_fixer_two_findings(tmp_path, fixer_orders_emitted=True)
    before = _state(session_dir)
    k = before["pending"]["attempt"]
    rnd = before["pending"]["round"]
    batch_path = RD._ensure_fix_batch_file(session_dir, rnd, before)
    with open(batch_path, "rb") as fh:
        batch_before = fh.read()
    state_before = _state_bytes(session_dir)
    seen = []

    def _refusing_render(phase, seat_key, context):
        with open(batch_path, "rb") as fh:
            seen.append(fh.read())
        return None, "probe-render-refusal"

    monkeypatch.setattr(RD.round_orders, "render_order", _refusing_render)
    out = _rule(session_dir, _oos(tmp_path, row_a), fixer_not_dispatched=True)
    assert len(seen) == 1 and seen[0] != batch_before
    assert _batch_keys(json.loads(seen[0])) == _batch_keys([row_b])
    assert out.get("ok") is False
    assert out.get("reason") == "order-render-refused", out
    assert "probe-render-refusal" in str(out.get("detail", ""))
    with open(batch_path, "rb") as fh:
        restored = fh.read()
    assert restored == batch_before
    assert _state_bytes(session_dir) == state_before
    assert not os.path.exists(RD._orders_manifest_path(session_dir, rnd, P_FIXER, k + 1))


def test_cli_flag_reshapes_the_unpicked_order(tmp_path, capsys):
    """axis: the CLI spelling `rule --fixer-not-dispatched` reaches cmd_rule and reshapes the order."""
    session_dir, _, _, row_a, _ = _pending_fixer_two_findings(tmp_path, fixer_orders_emitted=True)
    k = _state(session_dir)["pending"]["attempt"]
    path = _oos(tmp_path, row_a)
    capsys.readouterr()
    code = RD.main(["rule", "--session-dir", str(session_dir), "--ruling-file", str(path),
                    "--by", "owner", "--fixer-not-dispatched"])
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert code == 0, out
    assert out["fixerOrder"]["reshaped"] is True
    assert out["fixerOrder"]["attempt"] == k + 1
    assert _state(session_dir)["pending"]["attempt"] == k + 1
