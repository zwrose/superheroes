"""#1272 layer 4a: how a seat proves it ran, and the audit cluster.

Item 1 — no step is handed out under an unrecognized disposition-ledger owner.
"""
import ast
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_driver as RD  # noqa: E402
import session_contract as SC  # noqa: E402

_OWNER_CAUSE = "disposition-ledger-owner-unrecognized"


def _cfg():
    return {"leg": "code", "vendors": ["claude", "codex"], "diff": "d", "fixerVendor": "codex"}


def _state_bytes(session_dir):
    with open(os.path.join(session_dir, SC.STATE_FILE), "rb") as fh:
        return fh.read()


def _plant_owner(session_dir, value):
    ok, state = RD.load_state(session_dir)
    assert ok and state is not None
    state[SC.DISPOSITION_LEDGER_OWNER_FIELD] = value
    RD.save_state(session_dir, state)


# --- item 1: the refusal at the one hand-out builder -----------------------------------------

def test_l4a_1_next_refuses_a_pending_dispatch_under_an_unrecognized_owner(tmp_path):
    # axis: an unrecognized owner refuses the re-emitted dispatch before anyone spends on it
    session_dir = str(tmp_path)
    first = RD.cmd_next(session_dir, _cfg())
    assert first["ok"] and first["phase"] == RD.P_PANEL, first
    _plant_owner(session_dir, "ledger-v2")
    before = _state_bytes(session_dir)
    out = RD.cmd_next(session_dir)
    assert out == {"ok": False, "reason": _OWNER_CAUSE}
    assert "expectedStateHash" not in out
    assert _state_bytes(session_dir) == before
    last = RD.read_journal(session_dir)[-1]
    assert last["cmd"] == "next"
    assert last["outcome"] == _OWNER_CAUSE
    assert last["phase"] == RD.P_PANEL


def test_l4a_1_null_owner_is_unrecognized_and_refuses_too(tmp_path):
    session_dir = str(tmp_path)
    assert RD.cmd_next(session_dir, _cfg())["ok"]
    _plant_owner(session_dir, None)
    assert RD.cmd_next(session_dir) == {"ok": False, "reason": _OWNER_CAUSE}


def test_l4a_1_recognized_and_absent_owners_still_hand_the_step_out(tmp_path):
    session_dir = str(tmp_path)
    first = RD.cmd_next(session_dir, _cfg())
    assert first["ok"]
    again = RD.cmd_next(session_dir)
    assert again["ok"] and again["expectedStateHash"] == first["expectedStateHash"]
    _plant_owner(session_dir, SC.DISPOSITION_LEDGER_OWNER_VALUE)
    assert RD.cmd_next(session_dir)["ok"]


def test_l4a_1_builder_refuses_for_every_caller_and_names_the_caller(tmp_path):
    session_dir = str(tmp_path)
    state = RD.new_state(_cfg())
    state[SC.DISPOSITION_LEDGER_OWNER_FIELD] = "ledger-v2"
    pending = {"action": RD.P_AUDITS, "round": 2, "phase": RD.P_AUDITS, "attempt": 0,
               "payload": {"targets": []}}
    out = RD._next_response(session_dir, RD.RE_EMIT_CMD, state, pending)
    assert out == {"ok": False, "reason": _OWNER_CAUSE}
    last = RD.read_journal(session_dir)[-1]
    assert (last["cmd"], last["phase"], last["round"], last["attempt"], last["outcome"]) == (
        RD.RE_EMIT_CMD, RD.P_AUDITS, 2, 0, _OWNER_CAUSE)


def test_l4a_1_a_terminal_step_still_answers_under_an_unrecognized_owner(tmp_path):
    # axis: a terminal hands nothing out — certification refuses it on its own path
    session_dir = str(tmp_path)
    state = RD.new_state(_cfg())
    state[SC.DISPOSITION_LEDGER_OWNER_FIELD] = "ledger-v2"
    pending = {"action": RD.P_TERMINAL, "round": 1, "phase": RD.P_TERMINAL, "attempt": 0,
               "payload": {"verdict": "cannot-certify"}}
    out = RD._next_response(session_dir, "next", state, pending)
    assert out["ok"] is True
    assert out["expectedStateHash"] == RD.state_hash(state)


def _driver_tree():
    with open(os.path.join(_LIB, "round_driver.py"), encoding="utf-8") as fh:
        return ast.parse(fh.read())


def test_l4a_1_census_the_step_echo_has_one_builder():
    """Every hand-out carries `expectedStateHash`; the key is built in exactly one function, so a
    new hand-out path that skips the refusal cannot exist without failing here."""
    tree = _driver_tree()
    owners = []
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.Dict):
                for key in node.keys:
                    if isinstance(key, ast.Constant) and key.value == "expectedStateHash":
                        owners.append(fn.name)
            if (isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant)
                    and node.slice.value == "expectedStateHash"
                    and isinstance(node.ctx, ast.Store)):
                owners.append(fn.name)
    assert owners == ["_next_response"], owners


# --- item 2: an audit seat that cannot produce a runner record refuses at seat time ---------------

import importlib.util  # noqa: E402

import receipt_disclosures  # noqa: E402

_TDI_SPEC = importlib.util.spec_from_file_location(
    "test_round_driver_integration_for_l4a", os.path.join(_HERE, "test_round_driver_integration.py"))
_TDI = importlib.util.module_from_spec(_TDI_SPEC)
_TDI_SPEC.loader.exec_module(_TDI)


def _durable_state(**cfg):
    state = RD.new_state(dict({"leg": "code", "diff": "d"}, **cfg))
    state["_advanceUsed"] = True
    return state


def test_l4a_2_durable_selection_skips_host_vendors_for_an_independent_engine():
    # the 2g r2 shape: claude listed first, fixer on cursor — today's rule seats claude
    cfg = {"vendors": ["claude", "codex", "cursor"], "fixerVendor": "cursor"}
    assert RD._auditor_vendor(cfg, "cursor") == ("claude", "independent")
    assert RD._auditor_vendor(cfg, "cursor", True) == ("codex", "independent")


def test_l4a_2_durable_selection_degrades_inside_the_runner_set_never_to_a_host():
    cfg = {"vendors": ["claude", "codex"], "fixerVendor": "codex"}
    assert RD._auditor_vendor(cfg, "codex") == ("claude", "independent")
    assert RD._auditor_vendor(cfg, "codex", True) == ("codex", "degraded")


def test_l4a_2_audit_targets_carry_the_seated_verifier_cell():
    state = _durable_state(vendors=["claude", "codex"], fixerVendor="claude")
    state["fixBatch"] = [{"file": "f.py", "line": 3, "title": "bug", "severity": "Important"}]
    targets = RD._audit_targets(state, state["config"], {})
    assert [(t["auditorVendor"], t["auditorModel"], t["auditorEffort"]) for t in targets] == [
        ("codex",) + tuple(RD.model_registry.matrix_config("verifier", "codex"))]


def test_l4a_2_transport_fault_refuses_a_durable_audit_seat_off_the_runner():
    state = _durable_state(vendors=["claude"], fixerVendor="claude")
    for vendor in ("claude", None, ""):
        assert RD._seat_transport_fault({"vendor": vendor}, "t1", RD.P_AUDITS, state) == (
            "auditor-no-runner-record:%s" % (vendor if isinstance(vendor, str) else repr(vendor)))
    for vendor in ("codex", "cursor"):
        assert RD._seat_transport_fault({"vendor": vendor}, "t1", RD.P_AUDITS, state) is None


def test_l4a_2_transport_fault_leaves_other_phases_and_hand_sessions_alone():
    durable = _durable_state(vendors=["claude"], fixerVendor="claude")
    hand = dict(durable, _submitUsed=True)
    library = dict(durable, _advanceUsed=False)
    assert RD._seat_transport_fault({"vendor": "claude"}, "s", RD.P_PANEL, durable) is None
    assert RD._seat_transport_fault({"vendor": "claude"}, "t1", RD.P_AUDITS, hand) is None
    assert RD._seat_transport_fault({"vendor": "claude"}, "t1", RD.P_AUDITS, library) is None


def test_l4a_2_a_claude_only_durable_session_refuses_the_audit_order_before_dispatch(tmp_path):
    # axis: the refusal lands when the audit order is emitted — nothing to record, nothing lost
    session_dir, gitdir, head_path = _TDI._bootstrap(tmp_path, name="claude-only",
                                                     vendors=["claude"], fixerVendor="claude")
    findings = [_TDI._blocking_finding("unchecked index", 2)]
    try:
        _TDI._drive_to_phase(session_dir, gitdir, findings, head_path, RD.P_AUDITS)
    except AssertionError as exc:
        seen, out = exc.args[0]
    else:
        raise AssertionError("the claude-only durable session reached dispatch-audits")
    assert seen == RD.P_FIXER
    assert out["ok"] is False and out["reason"] == "order-render-refused"
    assert out["detail"].endswith(":auditor-no-runner-record:claude"), out
    state = _TDI._state(session_dir)
    # the fixer folded; the audit step was never handed out, and asking again refuses again
    assert state.get("pending") is None and state["step"] == RD.P_AUDITS
    again = RD.cmd_next(session_dir)
    assert again["ok"] is False and again["detail"] == out["detail"]
    audits_dir = os.path.join(session_dir, "round-%d" % state["round"], "orders", RD.P_AUDITS)
    assert not os.path.exists(audits_dir)


# --- item 3: a host seat with no execution evidence sits out of the certified panel ---------------

import round_certification as RC  # noqa: E402
import round_records as RR  # noqa: E402
from round_certification_fixtures import (  # noqa: E402
    DEFAULT_PANEL_PAYLOAD_SHA, HEAD_SHA, _default_journal_row, write_session)

_HOST = "test-reviewer"


def _host_envelope():
    payload = {"findings": []}
    return {"schema": RR.SEAT_RESULT_SCHEMA_V2, "session": "test-session-001", "round": 1,
            "phase": RC.PANEL_PHASE, "seat": _HOST, "attempt": 0, "vendor": "claude",
            "model": "opus-5", "payload": payload, "payloadSha256": RR.payload_sha256(payload),
            "provenance": RC.PROVENANCE_DISPATCH_OBSERVED,
            "envelopeSha256": RR.envelope_sha256(payload, None)}


def _host_row(seat=_HOST):
    return {"cmd": "record-result", "outcome": "recorded", "phase": RC.PANEL_PHASE, "round": 1,
            "attempt": 0, "seat": seat, "occurrence": 0,
            "provenance": RC.PROVENANCE_DISPATCH_OBSERVED,
            "payloadSha256": RR.payload_sha256({"findings": []}), "headSha": HEAD_SHA,
            "recordIdentity": {"phase": RC.PANEL_PHASE, "seat": seat, "occurrence": 0,
                               "attempt": 0}}


def _manifest(host_channel="file", drop_channel=False, engine_seat=True):
    seats = {}
    if engine_seat:
        seats["code-reviewer-k"] = {"seat": "code-reviewer", "occurrence": 0, "vendor": "codex",
                                    "model": "gpt-5.6-sol", "engine": None, "channel": "stdout"}
    host = {"seat": _HOST, "occurrence": 0, "vendor": "claude", "model": "opus-5",
            "engine": None, "channel": host_channel}
    if drop_channel:
        host.pop("channel")
    seats[_HOST + "-k"] = host
    return {"schema": "orders-manifest/1", "session": "test-session-001", "round": 1,
            "phase": RC.PANEL_PHASE, "attempt": 0, "orders": "not-emitted", "seats": seats}


def _session_with_host_seat(tmp_path, name="host", manifest=None, tamper=None,
                            engine_seat=True):
    manifest = manifest if manifest is not None else _manifest(engine_seat=engine_seat)
    sha = SC.sha256_text(SC.canonical(manifest))
    emitted = {"cmd": "next", "outcome": "orders-emitted", "phase": RC.PANEL_PHASE, "round": 1,
               "attempt": 0, "manifestSha256": sha}
    rows = [emitted] + ([_default_journal_row()] if engine_seat else []) + [_host_row()]
    envelopes = [{"seat": _HOST, "envelope": _host_envelope()}]
    if engine_seat:
        envelopes.insert(0, {"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA})
    session_dir = write_session(tmp_path, name=name, journal_lines=rows, envelopes=envelopes)
    written = dict(manifest, **(tamper or {}))
    path = RC._orders_manifest_path(session_dir, 1, RC.PANEL_PHASE, 0)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(written, fh, sort_keys=True)
    return session_dir


def test_l4a_3_a_host_seat_without_evidence_leaves_the_panel_and_the_receipt_names_it(tmp_path):
    receipt, refusal = RC.certify(_session_with_host_seat(tmp_path))
    assert refusal is None, refusal
    rows = {r["seat"]: r for r in receipt["seats"]}
    assert rows["code-reviewer"]["proof"] == RC.SEAT_PROOF_RUNNER_RECORD
    assert rows[_HOST]["proof"] == RC.SEAT_PROOF_NONE_HOST_SEAT
    assert receipt["disclosures"]["uncertifiedSeats"] == [
        {"seat": _HOST, "phase": RC.PANEL_PHASE, "round": 1, "attempt": 0, "vendor": "claude",
         "proof": RC.SEAT_PROOF_NONE_HOST_SEAT}]


def test_l4a_3_a_vendor_label_without_the_host_channel_still_refuses(tmp_path):
    # a defaulted claude is rendered on stdout: the label is a guess, not host evidence
    session_dir = _session_with_host_seat(tmp_path, manifest=_manifest(host_channel="stdout"))
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert (refusal["class"], refusal["artifact"], refusal["bindingFailure"]) == (
        "unrun-review", _HOST, "execution-evidence-absent")


def test_l4a_3_a_manifest_without_a_channel_exempts_nothing(tmp_path):
    session_dir = _session_with_host_seat(tmp_path, manifest=_manifest(drop_channel=True))
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None and refusal["bindingFailure"] == "execution-evidence-absent"


def test_l4a_3_a_manifest_edited_after_emission_exempts_nothing(tmp_path):
    # hashed with the host seat on stdout, then rewritten to claim the host channel
    session_dir = _session_with_host_seat(
        tmp_path, manifest=_manifest(host_channel="stdout"),
        tamper={"seats": _manifest(host_channel="file")["seats"]})
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None and refusal["class"] in ("unrun-review", "unfetched-findings"), refusal


def test_l4a_3_a_panel_round_of_only_host_seats_refuses(tmp_path):
    session_dir = _session_with_host_seat(tmp_path, engine_seat=False)
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert (refusal["class"], refusal["bindingFailure"]) == (
        "unrun-review", RC.BINDING_FAILURE_NO_RUNNER_PROVEN_PANEL_SEAT)


def test_l4a_3_audit_and_fixer_seats_never_leave_the_certified_panel(tmp_path):
    session_dir = _session_with_host_seat(tmp_path)
    ctx, refusal = RC._load_context(session_dir)
    assert refusal is None
    base = {"seat": _HOST, "round": 1, "attempt": 0, "occurrence": 0,
            "provenance": RC.PROVENANCE_DISPATCH_OBSERVED}
    assert RC.uncertified_host_seat(ctx, dict(base, phase=RC.PANEL_PHASE)) is True
    assert RC.uncertified_host_seat(ctx, dict(base, phase=RC.P_AUDITS)) is False
    assert RC.uncertified_host_seat(ctx, dict(base, phase=RC.P_FIXER)) is False
    assert RC.uncertified_host_seat(
        ctx, dict(base, phase=RC.PANEL_PHASE, provenance="orchestrator-fulfilled")) is False


def test_l4a_3_the_driver_records_each_seats_rendered_channel_in_the_orders_manifest(tmp_path):
    session_dir = str(tmp_path / "chan")
    os.makedirs(session_dir)
    seat_map = {"seats": {dim: dict(cell) for dim, cell in _TDI.SEAT_MAP["seats"].items()}}
    seat_map["seats"]["code-reviewer"] = {"vendor": "codex", "model": "gpt-5.6-sol",
                                          "engine": "codex"}
    out = RD.cmd_next(session_dir, {"leg": "code", "vendors": ["claude", "codex"], "diff": "d",
                                    "fixerVendor": "claude", "seatMap": seat_map})
    assert out["ok"], out
    with open(RC._orders_manifest_path(session_dir, 1, RD.P_PANEL, 0), encoding="utf-8") as fh:
        manifest = json.load(fh)
    channels = {e["seat"]: (e["vendor"], e["channel"]) for e in manifest["seats"].values()}
    assert channels["code-reviewer"] == ("codex", "stdout")
    assert channels["test-reviewer"] == ("claude", "file")
    assert all(
        ch == ("stdout" if RD._vendor_is_external_engine(v) else "file")
        for v, ch in channels.values()), channels


def test_l4a_3_the_seat_map_receipt_names_seats_no_runner_record_can_prove():
    import seat_map as SM
    seats = {"code-reviewer": {"vendor": "codex", "model": "gpt-5.6-sol"},
             "test-reviewer": {"vendor": "claude", "model": "opus-5"},
             "premortem-reviewer": {"vendor": "claude", "model": "opus-5"}}
    receipt = SM.to_receipt({"seats": seats, "liveVendors": ["claude", "codex"]}, "openai")
    assert receipt["noRunnerRecordSeats"] == ["premortem-reviewer", "test-reviewer"]
    engine_only = {"code-reviewer": seats["code-reviewer"]}
    assert "noRunnerRecordSeats" not in SM.to_receipt({"seats": engine_only}, "anthropic")
