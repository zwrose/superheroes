"""#1272 WO-1: seat provenance derives from the runner record at state v5."""
import importlib.util
import json
import os
import sys
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import engine_adapter  # noqa: E402
import engine_dispatch  # noqa: E402
import receipt_disclosures  # noqa: E402
import round_adapters  # noqa: E402
import round_records  # noqa: E402
import sanitized_view  # noqa: E402

from test_recorded_row_chokepoint_1272 import (  # noqa: E402
    DIFF,
    HEAD_SHA,
    _advance,
    _anchor_hashes,
    _execution_evidence,
    _land,
    _land_and_record,
    _pending,
    _record_all_panel_seats,
    _result_envelope,
    _session,
    _session_id,
    _state,
)

RD = importlib.import_module("round_driver")

_SPEC = importlib.util.spec_from_file_location(
    "test_round_driver_integration",
    os.path.join(_HERE, "test_round_driver_integration.py"))
_TDI = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_TDI)

_bootstrap = _TDI._bootstrap
_blocking_finding = _TDI._blocking_finding
_drive_to_phase = _TDI._drive_to_phase
_fake_git = _TDI._fake_git

_TRD_SPEC = importlib.util.spec_from_file_location(
    "test_round_driver_for_1272",
    os.path.join(_HERE, "test_round_driver.py"))
_TRD = importlib.util.module_from_spec(_TRD_SPEC)
_TRD_SPEC.loader.exec_module(_TRD)


def _journal(session_dir):
    return RD.read_journal(session_dir)


def _last_journal_row(session_dir):
    rows = _journal(session_dir)
    assert rows, "journal empty"
    return rows[-1]


def _drive_to_audits(tmp_path, findings=None, name="audits"):
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name=name)
    findings = findings if findings is not None else [_blocking_finding("unchecked index", 2)]
    _drive_to_phase(session_dir, gitdir, findings, head_path, RD.P_AUDITS)
    return session_dir, gitdir, head_path


def _audit_targets(session_dir):
    return _state(session_dir).get("_auditTargets") or []


def _audit_roster(session_dir):
    state = _state(session_dir)
    roster, reason = round_adapters.roster_for(RD.P_AUDITS, state, state.get("config") or {})
    assert reason is None, reason
    return roster


def _audit_payload(seat, ruling="discharged"):
    return {"id": seat, "ruling": ruling, "auditorVendor": "claude",
            "reason": "re-read the fixed hunk; the defect is gone"}


def _store_path(session_dir, seat, pend=None):
    pend = pend or _pending(session_dir)
    return round_records.store_path(session_dir, pend["round"], pend["phase"],
                                    round_records.storage_key(seat), pend["attempt"])


def _anchor_head_sha(session_dir):
    pend = _pending(session_dir)
    state = _state(session_dir)
    anchor = RD._orders_anchor(state, session_dir, pend["round"], pend["phase"], pend["attempt"])
    if isinstance(anchor, dict):
        return anchor.get("headSha")
    return None


def _land_audits(session_dir, seat, payload=None, **over):
    """Land on a session driven through _TDI with anchor-aligned headSha."""
    head = _anchor_head_sha(session_dir)
    if head:
        over = dict(over)
        over["headSha"] = head
    return _land(session_dir, seat, payload=payload, **over)


def _legacy_session(tmp_path, name="legacy"):
    session_dir = _session(tmp_path, name=name)
    state = _state(session_dir)
    state["schemaVersion"] = 2
    RD.save_state(session_dir, state)
    return session_dir


def _legacy_audits_session(tmp_path, name="legacy-audits", seat="src/f00.py::unchecked index@L2"):
    """Hand-built legacy (seat-result/1) session pending on dispatch-audits."""
    session_dir = _legacy_session(tmp_path, name=name)
    state = _state(session_dir)
    state["round"] = 1
    state["pending"] = {"round": 1, "phase": RD.P_AUDITS, "attempt": 0}
    state["_auditTargets"] = [{"id": seat, "identity": "unchecked index", "auditorVendor": "claude",
                               "verdict": "blocking", "evidence": "unchecked index at src/f00.py:2"}]
    RD.save_state(session_dir, state)
    return session_dir, seat


def test_audit_seat_missing_journal_record_refuses_at_record_time(tmp_path):
    """E1 — dispatch-observed audits envelope without minted evidence refuses at record-result."""
    session_dir, _gitdir, _head_path = _drive_to_audits(tmp_path)
    seat = _audit_roster(session_dir)[0]
    evidence = _execution_evidence(source="codex")
    _land_audits(session_dir, seat, payload=_audit_payload(seat),
                 provenance=round_records.PROVENANCE_DISPATCH_OBSERVED, executionEvidence=evidence)
    out = RD.cmd_record_result(session_dir, seat)
    assert out["ok"] is False
    assert out["reason"] == "provenance-underivable"
    assert not os.path.exists(_store_path(session_dir, seat))
    row = _last_journal_row(session_dir)
    assert row.get("outcome") == "refused"
    assert row.get("reason") == "provenance-underivable"
    assert row.get("cmd") == "record-result"


def test_audit_dispatch_observed_landed_evidence_without_run_dir_refuses(tmp_path):
    """E2 — landed executionEvidence without evidence_minted still refuses."""
    session_dir, _gitdir, _head_path = _drive_to_audits(tmp_path)
    seat = _audit_roster(session_dir)[0]
    evidence = _execution_evidence(source="codex")
    _land_audits(session_dir, seat, payload=_audit_payload(seat),
                 provenance=round_records.PROVENANCE_DISPATCH_OBSERVED, executionEvidence=evidence,
                 envelopeSha256=round_records.envelope_sha256(_audit_payload(seat), evidence))
    out = RD.cmd_record_result(session_dir, seat)
    assert out["ok"] is False and out["reason"] == "provenance-underivable"
    assert not os.path.exists(_store_path(session_dir, seat))


def test_advance_sweep_refuses_dispatch_observed_audits_without_minted_evidence(tmp_path):
    """E3 — advance sweep refuses provenance-underivable on dispatch-observed audits."""
    session_dir, gitdir, _head_path = _drive_to_audits(tmp_path)
    seat = _audit_roster(session_dir)[0]
    evidence = _execution_evidence(source="codex")
    _land_audits(session_dir, seat, payload=_audit_payload(seat),
                 provenance=round_records.PROVENANCE_DISPATCH_OBSERVED, executionEvidence=evidence)
    out = RD.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is False and out["reason"] == "provenance-underivable"
    assert not os.path.exists(_store_path(session_dir, seat))


def test_hand_landed_audits_without_evidence_refuses(tmp_path):
    """E4 — hand-landed audits envelope without executionEvidence refuses."""
    session_dir, _gitdir, _head_path = _drive_to_audits(tmp_path)
    seat = _audit_roster(session_dir)[0]
    path, env = _land_audits(session_dir, seat, payload=_audit_payload(seat),
                             provenance=round_records.PROVENANCE_HAND_LANDED)
    del env["executionEvidence"]
    env["envelopeSha256"] = round_records.envelope_sha256(env["payload"], None)
    round_records.atomic_write_json(path, env)
    out = RD.cmd_record_result(session_dir, seat)
    assert out["ok"] is False and out["reason"] == "provenance-underivable"
    assert not os.path.exists(_store_path(session_dir, seat))


def test_hand_landed_audits_with_vendor_source_stores(tmp_path):
    """E4 — hand-landed audits with registry vendor source stores."""
    session_dir, _gitdir, _head_path = _drive_to_audits(tmp_path)
    seat = _audit_roster(session_dir)[0]
    evidence = _execution_evidence(source="claude")
    _land_audits(session_dir, seat, payload=_audit_payload(seat),
                 provenance=round_records.PROVENANCE_HAND_LANDED, executionEvidence=evidence)
    out = RD.cmd_record_result(session_dir, seat)
    assert out["ok"] is True, out
    stored, err = round_records.read_json(out["storePath"])
    assert err is None
    assert stored["executionEvidence"]["source"] == "claude"


def test_audit_source_not_in_vendor_registry_refuses(tmp_path):
    """E4b — executionEvidence.source outside model_registry.VENDORS refuses."""
    session_dir, _gitdir, _head_path = _drive_to_audits(tmp_path)
    seat = _audit_roster(session_dir)[0]
    evidence = _execution_evidence(source="runner")
    _land_audits(session_dir, seat, payload=_audit_payload(seat),
                 provenance=round_records.PROVENANCE_HAND_LANDED, executionEvidence=evidence)
    out = RD.cmd_record_result(session_dir, seat)
    assert out["ok"] is False and out["reason"] == "provenance-underivable"
    assert not os.path.exists(_store_path(session_dir, seat))


def test_panel_dispatch_observed_without_evidence_stores_provenance_underived(tmp_path):
    """E5 — panel dispatch-observed without evidence stores; provenanceUnderived discloses."""
    session_dir = _session(tmp_path)
    seat = "code-reviewer"
    for other in RD.DIMENSIONS:
        if other != seat:
            _land_and_record(session_dir, other)
    env = _result_envelope(session_dir, seat,
                           provenance=round_records.PROVENANCE_DISPATCH_OBSERVED)
    del env["executionEvidence"]
    env["envelopeSha256"] = round_records.envelope_sha256(env["payload"], None)
    path = round_records.landing_path(session_dir, env["round"], env["phase"],
                                      round_records.storage_key(seat), env["attempt"])
    round_records.atomic_write_json(path, env)
    out = RD.cmd_record_result(session_dir, seat)
    assert out["ok"] is True, out
    adv = _advance(session_dir, tmp_path)
    assert adv["ok"], adv
    stored = []
    for dim in RD.DIMENSIONS:
        spath = round_records.store_path(session_dir, 1, RD.P_PANEL,
                                         round_records.storage_key(dim), 0)
        env_stored, err = round_records.read_json(spath)
        assert err is None
        stored.append(env_stored)
    artifact, why = round_adapters.assemble(RD.P_PANEL, stored, _state(session_dir),
                                            _state(session_dir).get("config") or {},
                                            dispatch_manifest=None)
    assert why is None, why
    assert "ranManifest" not in artifact
    assert seat in artifact["provenance"]["provenanceUnderived"]


def test_hand_submit_missing_manifest_key_names_expected_and_found(tmp_path):
    """E6 — hand submit missing manifest entry names expected/found keys in audit-provenance-fail."""
    session_dir, n = _TRD._at(tmp_path, RD.P_AUDITS)
    targets = n["payload"]["targets"]
    assert targets
    tid = targets[0]["id"]
    art = {
        "results": [{"id": tid, "ruling": "discharged", "reason": "r", "evidence": "e",
                     "auditorVendor": targets[0].get("auditorVendor")}],
        "collectionManifest": {},
    }
    out = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"], art)
    assert out["ok"] is True, out
    ok, state = RD.load_state(session_dir)
    assert ok
    assert tid in (state.get("_auditOutcome") or {}).get("notDischarged", [])
    prov_fail = [dec for dec in state.get("decisions", [])
                 if dec.get("kind") == "audit-provenance-fail"]
    assert prov_fail, state.get("decisions")
    detail = prov_fail[0].get("detail", "")
    assert "expected a collectionManifest entry keyed" in detail
    assert repr(tid) in detail
    assert "manifest keys found: []" in detail

    art_empty = {
        "results": [{"id": tid, "ruling": "discharged", "reason": "r", "evidence": "e",
                     "auditorVendor": targets[0].get("auditorVendor")}],
        "collectionManifest": {tid: ""},
    }
    session_dir2, n2 = _TRD._at(tmp_path / "empty-manifest", RD.P_AUDITS)
    targets2 = n2["payload"]["targets"]
    tid2 = targets2[0]["id"]
    art_empty["results"][0]["id"] = tid2
    art_empty["collectionManifest"] = {tid2: ""}
    out2 = RD.cmd_submit(session_dir2, n2["phase"], n2["attempt"], n2["expectedStateHash"],
                         art_empty)
    assert out2["ok"] is True, out2
    ok2, state2 = RD.load_state(session_dir2)
    assert ok2
    prov_fail2 = [dec for dec in state2.get("decisions", [])
                  if dec.get("kind") == "audit-provenance-fail"]
    assert prov_fail2, state2.get("decisions")
    detail2 = prov_fail2[0].get("detail", "")
    assert "no dispatch-manifest entry for this target" in detail2
    assert "expected a collectionManifest entry keyed" not in detail2


def test_legacy_manifest_absent_and_v5_manifest_ignored(tmp_path):
    """E7/E8 — legacy manifest absent stores; v5 present manifest is ignored."""
    session_dir, seat = _legacy_audits_session(tmp_path, name="legacy-absent")
    _land(session_dir, seat, payload=_audit_payload(seat))
    pend = _pending(session_dir)
    state = _state(session_dir)
    roster, roster_reason = round_adapters.roster_for(RD.P_AUDITS, state, state.get("config") or {})
    assert roster_reason is None, roster_reason
    out = round_records.ingest_landing(
        session_dir, pend["round"], pend["phase"], seat, pend["attempt"],
        current_attempt=pend["attempt"], roster=roster,
        seat_result_schema=round_records.SEAT_RESULT_SCHEMA)
    assert out["ok"] is True, out
    assert os.path.exists(_store_path(session_dir, seat, pend))

    session_dir2, _gitdir2, _head_path2 = _drive_to_audits(
        tmp_path, name="v5-ignored",
        findings=[_blocking_finding("unchecked index", 2),
                  _blocking_finding("unchecked index", 3)])
    targets = _audit_targets(session_dir2)
    assert len(targets) >= 2
    tid0, tid1 = targets[0]["id"], targets[1]["id"]
    pend = _pending(session_dir2)
    misleading = {tid0: {"vendor": "cursor"}, tid1: {"vendor": "cursor"}}
    round_records.atomic_write_json(
        round_records.dispatch_manifest_path(session_dir2, pend["round"], pend["phase"],
                                             pend["attempt"]),
        misleading)
    for tid, source in ((tid0, "codex"), (tid1, "cursor")):
        evidence = _execution_evidence(source=source)
        _land_audits(session_dir2, tid, payload=_audit_payload(tid),
                     provenance=round_records.PROVENANCE_HAND_LANDED, executionEvidence=evidence)
        assert RD.cmd_record_result(session_dir2, tid)["ok"] is True
    records = []
    for tid in (tid0, tid1):
        stored, err = round_records.read_json(_store_path(session_dir2, tid, pend))
        assert err is None
        records.append(stored)
    artifact, why = round_adapters.assemble(RD.P_AUDITS, records, _state(session_dir2),
                                            _state(session_dir2).get("config") or {},
                                            dispatch_manifest=misleading)
    assert why is None, why
    assert artifact["collectionManifest"] == {tid0: "codex", tid1: "cursor"}
    assert artifact["provenance"]["provenanceSource"] == {tid0: "hand-landed-evidence",
                                                          tid1: "hand-landed-evidence"}
    assert artifact["provenance"]["dispatchManifestIgnored"] is True


def test_vendor_echo_mismatch_discloses_recorded_source(tmp_path):
    """E9 — envelope vendor echo mismatch discloses; source governs."""
    session_dir, _gitdir, _head_path = _drive_to_audits(tmp_path)
    seat = _audit_roster(session_dir)[0]
    evidence = _execution_evidence(source="codex")
    _land_audits(session_dir, seat, payload=_audit_payload(seat), vendor="claude",
                 provenance=round_records.PROVENANCE_HAND_LANDED, executionEvidence=evidence)
    out = RD.cmd_record_result(session_dir, seat)
    assert out["ok"] is True, out
    stored, err = round_records.read_json(out["storePath"])
    assert err is None
    artifact, why = round_adapters.assemble(RD.P_AUDITS, [stored], _state(session_dir),
                                            _state(session_dir).get("config") or {},
                                            dispatch_manifest={"ignored": {"vendor": "cursor"}})
    assert why is None, why
    assert artifact["collectionManifest"] == {seat: "codex"}
    mismatch = artifact["provenance"]["vendorEchoMismatch"]
    assert mismatch == [{"seat": seat, "occurrence": 0, "echo": "claude", "recorded": "codex"}]
    state = _state(session_dir)
    state["rounds"] = {
        "1": {
            "adapterProvenance": {
                "byPhase": {RD.P_AUDITS: artifact["provenance"]},
            },
        },
    }
    degraded, _skipped = receipt_disclosures.build_degraded_prose(
        state, receipt_disclosures.RECEIPT_FORM_CERTIFIED)
    degraded_text = "\n".join(degraded)
    assert "trusted='codex'" in degraded_text
    assert "trusted=None" not in degraded_text


def test_record_result_sweep_refuses_dispatch_observed_audits(tmp_path):
    """E10 — record-result --sweep refuses the same provenance-underivable as advance sweep."""
    session_dir, _gitdir, _head_path = _drive_to_audits(tmp_path)
    seat = _audit_roster(session_dir)[0]
    evidence = _execution_evidence(source="codex")
    _land_audits(session_dir, seat, payload=_audit_payload(seat),
                 provenance=round_records.PROVENANCE_DISPATCH_OBSERVED, executionEvidence=evidence)
    out = RD.cmd_record_result(session_dir, sweep=True)
    assert out["ok"] is False and out["reason"] == "provenance-underivable"
    assert not os.path.exists(_store_path(session_dir, seat))


def test_advance_derives_collection_manifest_from_runner_record(tmp_path):
    """Named DoD — collectionManifest from executionEvidence.source; manifest ignored at v5."""
    session_dir, gitdir, head_path = _drive_to_audits(
        tmp_path, findings=[_blocking_finding("unchecked index", 2),
                            _blocking_finding("unchecked index", 3)])
    targets = _audit_targets(session_dir)
    assert len(targets) == 2
    tid0, tid1 = targets[0]["id"], targets[1]["id"]
    pend = _pending(session_dir)
    misleading = {tid0: {"vendor": "claude"}, tid1: {"vendor": "claude"}}
    round_records.atomic_write_json(
        round_records.dispatch_manifest_path(session_dir, pend["round"], pend["phase"],
                                             pend["attempt"]),
        misleading)
    for tid, source in ((tid0, "codex"), (tid1, "cursor")):
        evidence = _execution_evidence(source=source)
        _land_audits(session_dir, tid, payload=_audit_payload(tid),
                     provenance=round_records.PROVENANCE_HAND_LANDED, executionEvidence=evidence)
        assert RD.cmd_record_result(session_dir, tid)["ok"] is True
    out = RD.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is True, out
    state = _state(session_dir)
    assert state["rounds"][str(pend["round"])]["auditProvenance"] == "hand-landed-evidence"
    records = []
    for tid in (tid0, tid1):
        stored, err = round_records.read_json(_store_path(session_dir, tid, pend))
        assert err is None
        records.append(stored)
    artifact, why = round_adapters.assemble(RD.P_AUDITS, records, state,
                                            state.get("config") or {},
                                            dispatch_manifest=misleading)
    assert why is None, why
    assert artifact["collectionManifest"] == {tid0: "codex", tid1: "cursor"}
    assert artifact["provenance"]["provenanceSource"][tid0] == "hand-landed-evidence"
    assert artifact["provenance"]["provenanceSource"][tid1] == "hand-landed-evidence"
    assert artifact["provenance"]["dispatchManifestIgnored"] is True


def _audit_execution_run_dir(tmp_path, order_path, seat, echo_nonce="nonce-audit-e2e"):
    """Build a codex run directory whose parsed ruling binds to an audit seat envelope."""
    run_dir = str(tmp_path / "audit-evidence-run")
    journal_root = str(tmp_path / "audit-journal-root")
    os.makedirs(journal_root, exist_ok=True)
    os.environ[engine_dispatch.JOURNAL_ROOT_ENV] = journal_root
    repo_root = str(tmp_path / "audit-evidence-repo")
    os.makedirs(repo_root, exist_ok=True)
    with open(os.path.join(repo_root, ".git"), "w", encoding="utf-8") as fh:
        fh.write("gitdir: /fake/worktree\n")
    view_path = str(tmp_path / "audit-evidence-view")
    os.makedirs(view_path, exist_ok=True)
    view_meta = {"headSha": "abc123fake", "stripped": [], "path": view_path}
    with open(order_path, encoding="utf-8") as fh:
        base_prompt = fh.read()
    notice = sanitized_view.sanitized_view_notice(view_meta, mode="review")
    fed_prompt = (
        engine_dispatch.ANTIHIJACK_PREAMBLE + notice + base_prompt + "\n\n"
        + engine_adapter.REVIEW_RESULT_CONTRACT("ruling")
    )
    ruling_text = json.dumps({
        "id": seat,
        "ruling": "discharged",
        "reason": "re-read the hunk; the defect is gone",
        "auditorVendor": "codex",
    })
    stdout = _TDI._codex_event_stream(ruling_text, action_items=1)
    ok, detail = engine_dispatch._open_review_run(
        run_dir, engine="codex", argv=[sys.executable, "-c", "pass"], cwd=repo_root,
        timeout=30, retry_timeout=30, prompt_path=order_path, view_path=view_path,
        view_meta=view_meta, fed_prompt=fed_prompt, order_id="audit-e2e-order",
        progress_path=os.path.join(run_dir, "progress.jsonl"), repo_root=repo_root,
        echo_nonce=echo_nonce, base_prompt=base_prompt,
    )
    assert ok, detail
    engine_dispatch._journal_append(run_dir, {
        "kind": "attempt-ended", "attempt": 1,
        "exit": 0, "timedOut": False, "refusal": None,
        "wallSeconds": 0.1, "stdoutBytes": len(stdout),
        "at": time.time(),
    })
    with open(os.path.join(run_dir, "attempt-1.stdout"), "wb") as fh:
        fh.write(stdout.encode("utf-8"))
    with open(os.path.join(run_dir, "attempt-1.stderr"), "wb") as fh:
        fh.write(b"")
    return run_dir


def test_evidence_digest_subject_follows_runner_semantics():
    """Digest subject matches engine_dispatch parse digest for every review result kind."""
    _KIND_PHASE_PAYLOAD = [
        ("findings", RD.P_PANEL, {"findings": [{"dimension": "d", "taxonomy": "t", "title": "x"}]}),
        ("verdicts", RD.P_VERIFIERS, {"verdicts": [{"id": "v1", "verdict": "pass"}]}),
        ("grouping", RD.P_SYNTHESIS, {"grouping": [{"member_ids": ["a"]}]}),
        ("ruling", RD.P_AUDITS,
         {"id": "a1", "ruling": "discharged", "reason": "ok", "evidence": "e"}),
    ]
    for kind in engine_adapter.REVIEW_RESULT_KINDS:
        match = next(((ph, p) for k, ph, p in _KIND_PHASE_PAYLOAD if k == kind), None)
        assert match is not None, kind
        phase, seat_payload = match
        runner_shaped = RD._runner_shaped_result(phase, kind, seat_payload)
        carried, subject = engine_adapter.review_payload_carried(runner_shaped, kind)
        assert carried, (kind, runner_shaped)
        parse_res = {"ok": True, "resultKind": kind, kind: runner_shaped[kind]}
        digest, parsed_kind = engine_dispatch._result_digest_and_kind_from_parse(parse_res)
        assert parsed_kind == kind
        assert round_records.payload_sha256(subject) == digest


def test_dispatch_observed_audit_seat_binds_runner_evidence_end_to_end(tmp_path):
    """Positive-path dispatch-observed audits test the round-1 test seat asked for."""
    session_dir, gitdir, _head_path = _drive_to_audits(tmp_path, name="dispatch-audit-bind")
    state = _state(session_dir)
    pend = state["pending"]
    roster = _audit_roster(session_dir)
    seat = roster[0]
    order_path = round_records.order_prompt_path(
        session_dir, pend["round"], pend["phase"],
        round_records.storage_key(seat), pend["attempt"])
    assert os.path.isfile(order_path), order_path
    run_dir = _audit_execution_run_dir(tmp_path, order_path, seat)
    record, err = engine_dispatch.run_execution_record(run_dir)
    assert err is None, err
    assert record["resultKind"] == "ruling"
    journal_records, _ = engine_dispatch._journal_read(run_dir)
    run_state = engine_dispatch._journal_state(journal_records)
    parse_res = engine_dispatch._parse_review_attempt(run_dir, run_state, 1)
    assert parse_res["ok"] is True, parse_res
    ruling_payload = parse_res["ruling"]
    assert round_records.payload_sha256(ruling_payload) == record["resultDigest"]
    _TDI._dispatch_observed_land(session_dir, state, pend, seat, ruling_payload)
    out = RD.cmd_record_result(session_dir, seat, evidence_run_dir=run_dir)
    assert out["ok"] is True, out
    stored, read_err = round_records.read_json(out["storePath"])
    assert read_err is None
    assert stored["executionEvidence"]["source"] == "codex"
    for other in roster[1:]:
        _land_audits(session_dir, other, payload=_audit_payload(other))
        assert RD.cmd_record_result(session_dir, other)["ok"] is True
    adv = RD.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert adv["ok"] is True, adv
    state_after = _state(session_dir)
    assert state_after["rounds"][str(pend["round"])]["auditProvenance"] == "runner-record"
    artifact, why = round_adapters.assemble(
        RD.P_AUDITS,
        [round_records.read_json(_store_path(session_dir, s, pend))[0] for s in roster],
        state_after, state_after.get("config") or {}, dispatch_manifest=None)
    assert why is None, why
    assert artifact["provenance"]["provenanceSource"][seat] == "runner-record"


def test_audit_provenance_basis_follows_the_fold_path(tmp_path):
    """auditProvenance names the adapter-recorded seat sources, not the fold path alone."""
    session_dir, gitdir, _head_path = _drive_to_audits(tmp_path, name="durable-record")
    seat = _audit_roster(session_dir)[0]
    evidence = _execution_evidence(source="codex")
    _land_audits(session_dir, seat, payload=_audit_payload(seat),
                 provenance=round_records.PROVENANCE_HAND_LANDED, executionEvidence=evidence)
    assert RD.cmd_record_result(session_dir, seat)["ok"] is True
    pend = _pending(session_dir)
    out = RD.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is True, out
    state = _state(session_dir)
    assert state["rounds"][str(pend["round"])]["auditProvenance"] == "hand-landed-evidence"

    session_dir3 = _session(tmp_path, name="runner-record")
    state3 = _state(session_dir3)
    state3["_auditTargets"] = [{"id": seat, "identity": "unchecked index", "auditorVendor": "claude",
                                "independence": "cross-vendor", "verdict": "blocking",
                                "evidence": "unchecked index at src/f00.py:2"}]
    state3["auditRounds"] = []
    runner_round = state3["round"]
    RD._fold(state3, state3.get("config") or {}, RD.P_AUDITS, {
        "results": [{"id": seat, "ruling": "discharged", "reason": "r", "auditorVendor": "claude"}],
        "collectionManifest": {seat: "claude"},
        "provenance": {"provenanceSource": {seat: "runner-record"}},
    })
    assert state3["rounds"][str(runner_round)]["auditProvenance"] == "runner-record"

    session_dir2 = _session(tmp_path, name="hand-path")
    state2 = _state(session_dir2)
    state2["_submitUsed"] = True
    hand_target = {"id": seat, "identity": "unchecked index", "auditorVendor": "claude",
                   "independence": "cross-vendor", "verdict": "blocking",
                   "evidence": "unchecked index at src/f00.py:2"}
    state2["_auditTargets"] = [hand_target]
    state2["auditRounds"] = []
    hand_round = state2["round"]
    RD._fold_audits(state2, state2["config"], {
        "results": [],
        "collectionManifest": {seat: "claude"},
        "provenance": {"provenanceSource": {seat: "runner-record"}},
    })
    assert state2["rounds"][str(hand_round)]["auditProvenance"] == "collection-manifest"
