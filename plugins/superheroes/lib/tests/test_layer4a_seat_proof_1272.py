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


_SEAT_TIME = RD.SEAT_NO_RUNNER_RECORD_CAUSE


def test_l4a_2_transport_fault_refuses_every_durable_runner_proof_seat_off_the_runner():
    # axis: every runner-proof phase, one token — a claude or absent vendor refuses at seat time
    state = _durable_state(vendors=["claude"], fixerVendor="claude")
    assert RD.RUNNER_PROOF_PHASES == frozenset((
        RD.P_PANEL, RD.P_VERIFIERS, RD.P_SCOPED, RD.P_GAPSWEEP, RD.P_AUDITS))
    for phase in sorted(RD.RUNNER_PROOF_PHASES):
        for vendor in ("claude", None, ""):
            assert RD._seat_transport_fault({"vendor": vendor}, "s", phase, state) == (
                "seat-no-runner-record:%s"
                % (vendor if isinstance(vendor, str) else repr(vendor))), (phase, vendor)
        for vendor in ("codex", "cursor"):
            assert RD._seat_transport_fault({"vendor": vendor}, "s", phase, state) is None


def test_l4a_2_single_seat_phases_seat_a_runner_vendor_on_a_durable_session(tmp_path):
    # the auditor rule, widened: the reviewer engine resolves to claude here (no core.md), so a
    # durable session seats the live runner vendor outside the fixer's family instead
    repo_root = str(tmp_path)
    durable = _durable_state(vendors=["claude", "codex"], fixerVendor="claude")
    hand = dict(durable, _submitUsed=True)
    only_claude = _durable_state(vendors=["claude"], fixerVendor="claude")
    for phase in (RD.P_VERIFIERS, RD.P_SCOPED, RD.P_GAPSWEEP):
        row = RD._seat_transport_row(durable, phase, "s", 0, durable["config"], {}, repo_root)
        assert row["vendor"] == "codex", (phase, row)
        role = RD._SINGLE_SEAT_ROLES[phase]
        assert (row["model"], row["effort"], row["role"]) == (
            RD.model_registry.matrix_config(role, "codex") + (role,)), (phase, row)
        assert RD._seat_transport_fault(row, "s", phase, durable) is None
        assert RD._seat_channel(phase, row) == RD.CHANNEL_STDOUT
        kept = RD._seat_transport_row(hand, phase, "s", 0, hand["config"], {}, repo_root)
        assert kept["vendor"] == "claude", (phase, kept)
        none = RD._seat_transport_row(only_claude, phase, "s", 0, only_claude["config"], {},
                                      repo_root)
        assert RD._seat_transport_fault(none, "s", phase, only_claude) == (
            "seat-no-runner-record:claude")


def test_l4a_2_transport_fault_leaves_synthesis_the_fixer_and_hand_sessions_alone():
    durable = _durable_state(vendors=["claude"], fixerVendor="claude")
    hand = dict(durable, _submitUsed=True)
    library = dict(durable, _advanceUsed=False)
    assert RD._seat_transport_fault({"vendor": "claude"}, "s", RD.P_SYNTHESIS, durable) is None
    assert RD._seat_transport_fault({"vendor": "claude"}, "f", RD.P_FIXER, durable) is None
    for phase in sorted(RD.RUNNER_PROOF_PHASES):
        assert RD._seat_transport_fault({"vendor": "claude"}, "s", phase, hand) is None
        assert RD._seat_transport_fault({"vendor": "claude"}, "s", phase, library) is None


def test_l4a_2_a_claude_only_durable_session_refuses_the_first_gated_order_before_dispatch(tmp_path):
    # axis: the refusal lands when the order is emitted — nothing to record, nothing lost. The
    # round-1 panel precedes the path latch; the verifiers are the first order after it.
    session_dir, gitdir, head_path = _TDI._bootstrap(tmp_path, name="claude-only",
                                                     vendors=["claude"], fixerVendor="claude")
    findings = [_TDI._blocking_finding("unchecked index", 2)]
    try:
        _TDI._drive_to_phase(session_dir, gitdir, findings, head_path, RD.P_AUDITS)
    except AssertionError as exc:
        seen, out = exc.args[0]
    else:
        raise AssertionError("the claude-only durable session reached dispatch-audits")
    assert seen == RD.P_PANEL
    assert out["ok"] is False and out["reason"] == "order-render-refused"
    assert out["detail"].endswith(":seat-no-runner-record:claude"), out
    state = _TDI._state(session_dir)
    # the panel folded; the verifier step was never handed out, and asking again refuses again
    assert state.get("pending") is None and state["step"] == RD.P_VERIFIERS
    again = RD.cmd_next(session_dir)
    assert again["ok"] is False and again["detail"] == out["detail"]
    verifiers_dir = os.path.join(session_dir, "round-%d" % state["round"], "orders",
                                 RD.P_VERIFIERS)
    assert not os.path.exists(verifiers_dir)


# --- item 3: a host seat never certifies; its refusal is the one named reason -------------------

import round_certification as RC  # noqa: E402
import round_records as RR  # noqa: E402
from round_certification_fixtures import (  # noqa: E402
    DEFAULT_PANEL_PAYLOAD_SHA, HEAD_SHA, _default_journal_row, write_session)

_HOST = "test-reviewer"


# The seat payload each runner-proof phase lands (audits land the auditor's ruling object).
_PHASE_PAYLOAD = {
    RC.PANEL_PHASE: {"findings": []},
    RD.P_VERIFIERS: {"verdicts": []},
    RD.P_SCOPED: {"findings": []},
    RD.P_GAPSWEEP: {"findings": []},
    RD.P_AUDITS: {"id": "t1", "ruling": "discharged", "reason": "fixed", "evidence": "read it"},
}


def _host_envelope(phase=RC.PANEL_PHASE):
    payload = _PHASE_PAYLOAD[phase]
    return {"schema": RR.SEAT_RESULT_SCHEMA_V2, "session": "test-session-001", "round": 1,
            "phase": phase, "seat": _HOST, "attempt": 0, "vendor": "claude",
            "model": "opus-5", "payload": payload, "payloadSha256": RR.payload_sha256(payload),
            "provenance": RC.PROVENANCE_DISPATCH_OBSERVED,
            "envelopeSha256": RR.envelope_sha256(payload, None)}


def _host_row(seat=_HOST, phase=RC.PANEL_PHASE):
    return {"cmd": "record-result", "outcome": "recorded", "phase": phase, "round": 1,
            "attempt": 0, "seat": seat, "occurrence": 0,
            "provenance": RC.PROVENANCE_DISPATCH_OBSERVED,
            "payloadSha256": RR.payload_sha256(_PHASE_PAYLOAD[phase]), "headSha": HEAD_SHA,
            "recordIdentity": {"phase": phase, "seat": seat, "occurrence": 0,
                               "attempt": 0}}


def _manifest(engine_seat=True, phase=RC.PANEL_PHASE):
    seats = {}
    if engine_seat:
        seats["code-reviewer-k"] = {"seat": "code-reviewer", "occurrence": 0, "vendor": "codex",
                                    "model": "gpt-5.6-sol", "engine": None}
    seats[_HOST + "-k"] = {"seat": _HOST, "occurrence": 0, "vendor": "claude", "model": "opus-5",
                           "engine": None}
    return {"schema": "orders-manifest/1", "session": "test-session-001", "round": 1,
            "phase": phase, "attempt": 0, "orders": "not-emitted", "seats": seats}


def _session_with_host_seat(tmp_path, name="host", engine_seat=True, phase=RC.PANEL_PHASE):
    """A certified-looking session whose host seat is recorded on ``phase``, with that phase's OWN
    orders manifest and `orders-emitted` row (phase-matched, so the seat is a real roster seat)."""
    manifests = {phase: _manifest(engine_seat=engine_seat and phase == RC.PANEL_PHASE,
                                  phase=phase)}
    if engine_seat and phase != RC.PANEL_PHASE:
        manifests[RC.PANEL_PHASE] = _manifest(phase=RC.PANEL_PHASE)
        manifests[RC.PANEL_PHASE]["seats"].pop(_HOST + "-k")
        manifests[phase]["seats"].pop("code-reviewer-k", None)
    rows = []
    for ph, manifest in manifests.items():
        rows.append({"cmd": "next", "outcome": "orders-emitted", "phase": ph, "round": 1,
                     "attempt": 0, "manifestSha256": SC.sha256_text(SC.canonical(manifest))})
    rows += ([_default_journal_row()] if engine_seat else []) + [_host_row(phase=phase)]
    envelopes = [{"seat": _HOST, "phase": phase, "envelope": _host_envelope(phase)}]
    if engine_seat:
        envelopes.insert(0, {"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA})
    session_dir = write_session(tmp_path, name=name, journal_lines=rows, envelopes=envelopes)
    for ph, manifest in manifests.items():
        path = RC._orders_manifest_path(session_dir, 1, ph, 0)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, sort_keys=True)
    return session_dir


def test_l4a_3_a_mixed_panel_with_an_unproven_host_lens_refuses(tmp_path):
    # axis: round 4's Critical — one runner-proven lens never certifies an unproven configured one
    receipt, refusal = RC.certify(_session_with_host_seat(tmp_path))
    assert receipt is None
    assert (refusal["class"], refusal["artifact"], refusal["bindingFailure"]) == (
        "unrun-review", _HOST, "execution-evidence-absent")


def test_l4a_3_a_host_seat_on_each_runner_proof_phase_refuses_unrun_review(tmp_path):
    # axis: phase-matched manifests — the host seat is a real roster seat of the phase it sat on,
    # and on every runner-proof phase an unproven one ends certification with the named refusal
    for phase in sorted(RD.RUNNER_PROOF_PHASES):
        session_dir = _session_with_host_seat(tmp_path, name="host-" + phase, phase=phase)
        receipt, refusal = RC.certify(session_dir)
        assert receipt is None, phase
        assert (refusal["class"], refusal["artifact"], refusal["bindingFailure"]) == (
            "unrun-review", _HOST, "execution-evidence-absent"), (phase, refusal)


def test_l4a_3_a_panel_round_of_only_host_seats_refuses(tmp_path):
    session_dir = _session_with_host_seat(tmp_path, engine_seat=False)
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert (refusal["class"], refusal["bindingFailure"]) == (
        "unrun-review", "execution-evidence-absent")


def test_l4a_3_census_no_host_seat_exemption_or_label_survives_in_the_writer():
    # axis: the writer neither exempts nor labels a host seat — the refusal is the one named reason
    for gone in ("HOST_SEAT_EXEMPT_PHASES", "uncertified_host_seat",
                 "_panel_round_without_runner_proof", "BINDING_FAILURE_NO_RUNNER_PROVEN_PANEL_SEAT",
                 "host_seat_without_evidence", "_uncertified_seat_disclosures",
                 "_seat_carries_execution_evidence", "SEAT_PROOF_NONE_HOST_SEAT"):
        assert not hasattr(RC, gone), gone
    with open(RC.__file__, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    assert not any(isinstance(n, ast.Constant) and n.value in (
        "dispatch-scoped-finder", "dispatch-gap-sweep", "none-host-seat", "uncertifiedSeats")
        for n in ast.walk(tree))


def test_l4a_3_a_durable_verifier_manifest_names_the_seat_to_dispatch(tmp_path):
    # the orders manifest is the dispatcher's contract: vendor, model, effort and role, no channel
    session_dir, gitdir, head_path = _TDI._bootstrap(tmp_path, name="cell",
                                                     vendors=["claude", "codex"],
                                                     fixerVendor="claude")
    findings = [_TDI._blocking_finding("unchecked index", 2)]
    _TDI._drive_to_phase(session_dir, gitdir, findings, head_path, RD.P_VERIFIERS)
    rnd = _TDI._state(session_dir)["round"]
    with open(RC._orders_manifest_path(session_dir, rnd, RD.P_VERIFIERS, 0),
              encoding="utf-8") as fh:
        manifest = json.load(fh)
    cell = RD.model_registry.matrix_config("verifier", "codex")
    entries = list(manifest["seats"].values())
    assert entries
    for entry in entries:
        assert (entry["vendor"], entry["model"], entry["effort"], entry["role"]) == (
            ("codex",) + tuple(cell) + ("verifier",)), entry
        assert "channel" not in entry


def test_l4a_3_the_seat_map_receipt_names_seats_no_runner_record_can_prove():
    import seat_map as SM
    seats = {"code-reviewer": {"vendor": "codex", "model": "gpt-5.6-sol"},
             "test-reviewer": {"vendor": "claude", "model": "opus-5"},
             "premortem-reviewer": {"vendor": "claude", "model": "opus-5"}}
    receipt = SM.to_receipt({"seats": seats, "liveVendors": ["claude", "codex"]}, "openai")
    assert receipt["noRunnerRecordSeats"] == ["premortem-reviewer", "test-reviewer"]
    engine_only = {"code-reviewer": seats["code-reviewer"]}
    assert "noRunnerRecordSeats" not in SM.to_receipt({"seats": engine_only}, "anthropic")


# --- item 4: the fix-audit ruling carries its runner evidence; the receipt names the auditor ------

import engine_dispatch  # noqa: E402

_SP_SPEC = importlib.util.spec_from_file_location(
    "test_seat_provenance_for_l4a", os.path.join(_HERE, "test_seat_provenance_1272.py"))
_SP = importlib.util.module_from_spec(_SP_SPEC)
_SP_SPEC.loader.exec_module(_SP)


def _audit_run(tmp_path):
    session_dir, _gitdir, _head = _SP._drive_to_audits(tmp_path, name="l4a-ruling")
    state = _TDI._state(session_dir)
    pend = state["pending"]
    seat = _SP._audit_roster(session_dir)[0]
    order_path = RR.order_prompt_path(session_dir, pend["round"], pend["phase"],
                                      RR.storage_key(seat), pend["attempt"])
    run_dir = _SP._audit_execution_run_dir(
        tmp_path, order_path, seat, view_head_sha=_SP._anchor_head_sha(session_dir) or "abc123fake")
    journal, _ = engine_dispatch._journal_read(run_dir)
    parsed = engine_dispatch._parse_review_attempt(run_dir, engine_dispatch._journal_state(journal), 1)
    assert parsed["ok"] is True, parsed
    return session_dir, state, pend, seat, run_dir, parsed["ruling"]


def test_l4a_4_a_ruling_landed_with_an_undeclared_key_refuses_naming_it(tmp_path):
    session_dir, state, pend, seat, run_dir, ruling = _audit_run(tmp_path)
    _TDI._dispatch_observed_land(session_dir, state, pend, seat,
                                 dict(ruling, investigated=["reviewed.py"]))
    out = RD.cmd_record_result(session_dir, seat, evidence_run_dir=run_dir)
    assert out["ok"] is False and out["reason"] == "evidence-result-mismatch", out
    assert out["undeclaredKeys"] == ["investigated"]


def test_l4a_4_the_runners_ruling_landed_verbatim_binds_its_evidence(tmp_path):
    session_dir, state, pend, seat, run_dir, ruling = _audit_run(tmp_path)
    _TDI._dispatch_observed_land(session_dir, state, pend, seat, ruling)
    out = RD.cmd_record_result(session_dir, seat, evidence_run_dir=run_dir)
    assert out["ok"] is True, out
    stored, err = RR.read_json(out["storePath"])
    assert err is None and stored["executionEvidence"]["resultKind"] == "ruling"
    assert stored["executionEvidence"]["source"] == "codex"


def test_l4a_4_a_plain_digest_mismatch_names_no_keys():
    assert RD._record_kind_undeclared_keys(RD.P_AUDITS, "ruling",
                                           {"id": "a", "ruling": "discharged", "reason": "r"}) == []
    assert RD._record_kind_undeclared_keys(RD.P_PANEL, "findings",
                                           {"findings": [], "investigated": []}) == []


def _audit_session(tmp_path, source="codex"):
    manifest = {"schema": "orders-manifest/1", "session": "test-session-001", "round": 2,
                "phase": RC.P_AUDITS, "attempt": 0, "orders": "not-emitted",
                "seats": {"t1-k": {"seat": "t1", "occurrence": 0, "vendor": "codex",
                                   "model": "gpt-5.6-sol", "engine": None}}}
    sha = SC.sha256_text(SC.canonical(manifest))
    rows = [{"cmd": "next", "outcome": "orders-emitted", "phase": RC.P_AUDITS, "round": 2,
             "attempt": 0, "manifestSha256": sha},
            {"cmd": "record-result", "outcome": "recorded", "phase": RC.P_AUDITS, "round": 2,
             "attempt": 0, "seat": "t1", "occurrence": 0,
             "provenance": RC.PROVENANCE_DISPATCH_OBSERVED, "headSha": HEAD_SHA,
             "executionEvidence": {"source": source}}]
    session_dir = write_session(tmp_path, name="audit-row", journal_lines=rows, envelopes=[])
    path = RC._orders_manifest_path(session_dir, 2, RC.P_AUDITS, 0)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, sort_keys=True)
    return session_dir


def test_l4a_4_an_audit_receipt_row_names_the_recorded_vendor_and_the_seated_model(tmp_path):
    session_dir = _audit_session(tmp_path)
    ctx, refusal = RC._load_context(session_dir)
    assert refusal is None, refusal
    [entry] = [s for s in RC._collect_seats(ctx) if s["phase"] == RC.P_AUDITS]
    row = RC._receipt_seat_row(ctx, entry)
    assert (row["proof"], row["vendor"], row["model"]) == (
        RC.SEAT_PROOF_RUNNER_RECORD, "codex", "gpt-5.6-sol")


# --- item 5: the scoped finder has a registry role --------------------------------------------------

def test_l4a_5_the_scoped_finder_gates_as_its_own_role_on_the_deep_cells():
    import model_registry as MR
    import seat_bundle
    for vendor in MR.vendors():
        assert MR.matrix_config("scoped-finder", vendor) == MR.matrix_config("reviewer-deep", vendor)
        assert MR.family_for("scoped-finder", vendor) == MR.family_for("reviewer-deep", vendor)
    assert MR.role_read_write("scoped-finder") == "read"
    assert "scoped-finder" not in MR.model_tier_roles()
    ok = seat_bundle.resolve_entry(json.dumps({"vendor": "codex", "model": "gpt-5.6-sol",
                                               "effort": "xhigh", "role": "scoped-finder"}),
                                   verb="guard-check")
    assert ok["ok"] is True and ok["allowlistVerdict"]["ok"] is True, ok
    refused = seat_bundle.resolve_entry(json.dumps({"vendor": "codex", "model": "gpt-5.6-terra",
                                                    "effort": "high", "role": "scoped-finder"}),
                                        verb="guard-check")
    assert refused["ok"] is False



# --- review round 1 fixes -----------------------------------------------------------------------

def test_l4a_r1_the_channel_token_has_one_home():
    assert RD.CHANNEL_FILE is SC.SEAT_CHANNEL_HOST
    assert RD.CHANNEL_STDOUT is SC.SEAT_CHANNEL_ENGINE
    assert not hasattr(RC, "SEAT_CHANNEL_HOST")


def test_l4a_r1_a_fresh_emission_refuses_before_any_order_is_written(tmp_path):
    session_dir = str(tmp_path)
    assert RD.cmd_next(session_dir, _cfg())["ok"]
    ok, state = RD.load_state(session_dir)
    state["pending"] = None
    state[SC.DISPOSITION_LEDGER_OWNER_FIELD] = "ledger-v2"
    orders = os.path.join(session_dir, "round-1", "orders")
    import shutil
    shutil.rmtree(orders)
    RD.save_state(session_dir, state)
    before = _state_bytes(session_dir)
    out = RD.cmd_next(session_dir)
    assert out == {"ok": False, "reason": _OWNER_CAUSE}
    assert _state_bytes(session_dir) == before
    assert not os.path.exists(orders)


def test_l4a_r1_re_emit_refuses_before_superseding_anything(tmp_path, capsys):
    import test_round_driver_re_emit as RE
    _repo, _sess, session_dir = RE._stale_session(tmp_path, capsys)
    _plant_owner(session_dir, "ledger-v2")
    orders_before = RE._snapshot_order_bytes(session_dir, 1, RD.P_PANEL)
    state_before = _state_bytes(session_dir)
    rows_before = len(RD.read_journal(session_dir))
    out = RD.cmd_re_emit(session_dir, "tester")
    assert out == {"ok": False, "reason": _OWNER_CAUSE}
    assert RE._snapshot_order_bytes(session_dir, 1, RD.P_PANEL) == orders_before
    assert _state_bytes(session_dir) == state_before
    new_rows = RD.read_journal(session_dir)[rows_before:]
    assert [r["outcome"] for r in new_rows] == [_OWNER_CAUSE]
    assert new_rows[0]["cmd"] == "re-emit"
    assert not any(r.get("outcome") in ("orders-superseded", "orders-emitted") for r in new_rows)



def test_l4a_r2_an_unproven_host_synthesis_seat_still_refuses_certification(tmp_path):
    """Round-2 Critical: exempting synthesis let an unproven grouping clear a confirmed finding
    (merged under a representative the author-justification filter drops)."""
    synth_manifest = {"schema": "orders-manifest/1", "session": "test-session-001", "round": 1,
                      "phase": "dispatch-synthesis", "attempt": 0, "orders": "not-emitted",
                      "seats": {"synthesis-k": {"seat": "synthesis", "occurrence": 0,
                                                "vendor": "claude", "model": None,
                                                "engine": None}}}
    sha = SC.sha256_text(SC.canonical(synth_manifest))
    payload = {"grouping": [{"member_ids": ["v0"]}]}
    envelope = {"schema": RR.SEAT_RESULT_SCHEMA_V2, "session": "test-session-001", "round": 1,
                "phase": "dispatch-synthesis", "seat": "synthesis", "attempt": 0,
                "vendor": "claude", "payload": payload,
                "payloadSha256": RR.payload_sha256(payload),
                "provenance": RC.PROVENANCE_DISPATCH_OBSERVED,
                "envelopeSha256": RR.envelope_sha256(payload, None)}
    rows = [_default_journal_row(),
            {"cmd": "next", "outcome": "orders-emitted", "phase": "dispatch-synthesis",
             "round": 1, "attempt": 0, "manifestSha256": sha},
            {"cmd": "record-result", "outcome": "recorded", "phase": "dispatch-synthesis",
             "round": 1, "attempt": 0, "seat": "synthesis", "occurrence": 0,
             "provenance": RC.PROVENANCE_DISPATCH_OBSERVED,
             "payloadSha256": RR.payload_sha256(payload), "headSha": HEAD_SHA,
             "recordIdentity": {"phase": "dispatch-synthesis", "seat": "synthesis",
                                "occurrence": 0, "attempt": 0}}]
    session_dir = write_session(
        tmp_path, name="synth", journal_lines=rows,
        envelopes=[{"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA},
                   {"seat": "synthesis", "phase": "dispatch-synthesis", "envelope": envelope}])
    path = RC._orders_manifest_path(session_dir, 1, "dispatch-synthesis", 0)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(synth_manifest, fh, sort_keys=True)
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert (refusal["class"], refusal["artifact"], refusal["bindingFailure"]) == (
        "unrun-review", "synthesis", "execution-evidence-absent")


# --- review round 6 fixes -----------------------------------------------------------------------

def test_l4a_r6_the_seat_proof_words_have_one_home():
    # axis: the receipt's proof rows and the round's audit provenance spell one contract, defined once
    import round_records as RR
    assert RC.SEAT_PROOF_RUNNER_RECORD is SC.PROOF_RUNNER_RECORD
    assert RC.SEAT_PROOF_HAND_LANDED is SC.PROOF_HAND_LANDED
    assert RR.AUDIT_PROVENANCE_RUNNER_RECORD is SC.PROOF_RUNNER_RECORD
    assert RR.AUDIT_PROVENANCE_HAND_LANDED is SC.PROOF_HAND_LANDED
    words = {SC.PROOF_RUNNER_RECORD, SC.PROOF_HAND_LANDED}
    homes = set()
    for name in sorted(os.listdir(_LIB)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(_LIB, name), encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        if any(isinstance(n, ast.Constant) and n.value in words for n in ast.walk(tree)):
            homes.add(name)
    assert homes == {"session_contract.py"}, homes


def _dispatch_recipe_seat_lines():
    path = os.path.join(os.path.dirname(_LIB), "skills", "review-code", "reference",
                        "auto-fix-loop.md")
    with open(path, encoding="utf-8") as fh:
        lines = [ln[2:] if ln.startswith("> ") else ln.lstrip(">") for ln in fh.read().splitlines()]
    start = next(i for i, ln in enumerate(lines) if ln.startswith('case "$SEAT_KEY" in'))
    end = next(i for i, ln in enumerate(lines) if i > start and ln.startswith("SEAT_JSON="))
    return "\n".join(lines[start:end + 1])


def test_l4a_r6_the_dispatch_recipe_builds_a_non_panel_seat_from_its_manifest_entry(tmp_path):
    # real channel: run the documented recipe's seat block against a durable-record manifest whose
    # seat is absent from the panel-only seat map; the bundle must be the manifest's cell
    import shutil
    import subprocess
    if shutil.which("jq") is None or shutil.which("bash") is None:
        import pytest
        pytest.skip("the recipe needs jq and bash")
    manifest = tmp_path / "manifest.a0.json"
    manifest.write_text(json.dumps({"seats": {"verifier-x": {
        "vendor": "codex", "model": "m-seated", "effort": "high", "role": "verifier"}}}))
    script = _dispatch_recipe_seat_lines() + '\nprintf "%s" "$SEAT_JSON"\n'
    env = dict(os.environ, SEAT_KEY="verifier-x", SEAT_MANIFEST=str(manifest),
               SEAT_MAP=json.dumps({"seats": {"code-reviewer": {
                   "vendor": "claude", "model": "opus", "tier": "reviewer", "effort": None}}}))
    out = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == {"vendor": "codex", "model": "m-seated", "effort": "high",
                                      "role": "verifier"}
    env.pop("SEAT_MANIFEST")
    env["SEAT_KEY"] = "code-reviewer"
    out = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout)["vendor"] == "claude"
