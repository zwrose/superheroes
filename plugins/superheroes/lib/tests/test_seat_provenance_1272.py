"""#1272 WO-1: seat provenance derives from the runner record at state v5."""
import importlib.util
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_adapters  # noqa: E402
import round_records  # noqa: E402

from test_recorded_row_chokepoint_1272 import (  # noqa: E402
    DIFF,
    HEAD_SHA,
    FakeAdapters,
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
    adapters,
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
_write_dispatch_manifest = _TDI._write_dispatch_manifest


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


def _legacy_session(tmp_path, name="legacy"):
    session_dir = _session(tmp_path, name=name)
    state = _state(session_dir)
    state["schemaVersion"] = 2
    RD.save_state(session_dir, state)
    return session_dir


def test_audit_seat_missing_journal_record_refuses_at_record_time(tmp_path, adapters):
    """E1 — dispatch-observed audits envelope without minted evidence refuses at record-result."""
    session_dir, _gitdir, _head_path = _drive_to_audits(tmp_path)
    seat = _audit_roster(session_dir)[0]
    evidence = _execution_evidence(source="codex")
    _land(session_dir, seat, payload=_audit_payload(seat),
          provenance=round_records.PROVENANCE_DISPATCH_OBSERVED, executionEvidence=evidence)
    out = RD.cmd_record_result(session_dir, seat)
    assert out["ok"] is False
    assert out["reason"] == "provenance-underivable"
    assert not os.path.exists(_store_path(session_dir, seat))
    row = _last_journal_row(session_dir)
    assert row.get("outcome") == "refused"
    assert row.get("reason") == "provenance-underivable"
    assert row.get("cmd") == "record-result"


def test_audit_dispatch_observed_landed_evidence_without_run_dir_refuses(tmp_path, adapters):
    """E2 — landed executionEvidence without evidence_minted still refuses."""
    session_dir, _gitdir, _head_path = _drive_to_audits(tmp_path)
    seat = _audit_roster(session_dir)[0]
    evidence = _execution_evidence(source="codex")
    _land(session_dir, seat, payload=_audit_payload(seat),
          provenance=round_records.PROVENANCE_DISPATCH_OBSERVED, executionEvidence=evidence,
          envelopeSha256=round_records.envelope_sha256(_audit_payload(seat), evidence))
    out = RD.cmd_record_result(session_dir, seat)
    assert out["ok"] is False and out["reason"] == "provenance-underivable"


def test_advance_sweep_refuses_dispatch_observed_audits_without_minted_evidence(tmp_path, adapters):
    """E3 — advance sweep refuses provenance-underivable on dispatch-observed audits."""
    session_dir, gitdir, _head_path = _drive_to_audits(tmp_path)
    seat = _audit_roster(session_dir)[0]
    evidence = _execution_evidence(source="codex")
    _land(session_dir, seat, payload=_audit_payload(seat),
          provenance=round_records.PROVENANCE_DISPATCH_OBSERVED, executionEvidence=evidence)
    out = RD.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is False and out["reason"] == "provenance-underivable"


def test_hand_landed_audits_without_evidence_refuses(tmp_path, adapters):
    """E4 — hand-landed audits envelope without executionEvidence refuses."""
    session_dir, _gitdir, _head_path = _drive_to_audits(tmp_path)
    seat = _audit_roster(session_dir)[0]
    env = _result_envelope(session_dir, seat, payload=_audit_payload(seat),
                           provenance=round_records.PROVENANCE_HAND_LANDED)
    del env["executionEvidence"]
    env["envelopeSha256"] = round_records.envelope_sha256(env["payload"], None)
    path = round_records.landing_path(session_dir, env["round"], env["phase"],
                                      round_records.storage_key(seat), env["attempt"])
    round_records.atomic_write_json(path, env)
    out = RD.cmd_record_result(session_dir, seat)
    assert out["ok"] is False and out["reason"] == "provenance-underivable"


def test_hand_landed_audits_with_vendor_source_stores(tmp_path, adapters):
    """E4 — hand-landed audits with registry vendor source stores."""
    session_dir, _gitdir, _head_path = _drive_to_audits(tmp_path)
    seat = _audit_roster(session_dir)[0]
    evidence = _execution_evidence(source="claude")
    _land(session_dir, seat, payload=_audit_payload(seat),
          provenance=round_records.PROVENANCE_HAND_LANDED, executionEvidence=evidence)
    out = RD.cmd_record_result(session_dir, seat)
    assert out["ok"] is True, out
    stored, err = round_records.read_json(out["storePath"])
    assert err is None
    assert stored["executionEvidence"]["source"] == "claude"


def test_audit_source_not_in_vendor_registry_refuses(tmp_path, adapters):
    """E4b — executionEvidence.source outside model_registry.VENDORS refuses."""
    session_dir, _gitdir, _head_path = _drive_to_audits(tmp_path)
    seat = _audit_roster(session_dir)[0]
    evidence = _execution_evidence(source="runner")
    _land(session_dir, seat, payload=_audit_payload(seat),
          provenance=round_records.PROVENANCE_HAND_LANDED, executionEvidence=evidence)
    out = RD.cmd_record_result(session_dir, seat)
    assert out["ok"] is False and out["reason"] == "provenance-underivable"


def test_panel_dispatch_observed_without_evidence_stores_provenance_underived(tmp_path, adapters):
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


def test_legacy_manifest_missing_key_refusal_names_expected_and_found(tmp_path, adapters):
    """E6 — legacy v1 audits refuses dispatch-manifest-key-missing with expected/found keys."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="legacy-audits")
    state = _state(session_dir)
    state["schemaVersion"] = 2
    RD.save_state(session_dir, state)
    _drive_to_phase(session_dir, gitdir, findings, head_path, RD.P_AUDITS)
    seat = _audit_roster(session_dir)[0]
    _land(session_dir, seat, payload=_audit_payload(seat))
    pend = _pending(session_dir)
    manifest = {"other-seat": {"vendor": "claude", "model": "sonnet-5", "engine": "claude"}}
    round_records.atomic_write_json(
        round_records.dispatch_manifest_path(session_dir, pend["round"], pend["phase"],
                                             pend["attempt"]),
        manifest)
    out = RD.cmd_record_result(session_dir, seat)
    assert out["ok"] is False
    assert out["reason"] == "dispatch-manifest-key-missing"
    assert out["expectedKey"] == seat
    assert seat not in out["foundKeys"]


def test_legacy_manifest_absent_and_v5_manifest_ignored(tmp_path, adapters):
    """E7/E8 — legacy manifest absent stores; v5 present manifest is ignored."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="legacy-absent")
    state = _state(session_dir)
    state["schemaVersion"] = 2
    RD.save_state(session_dir, state)
    _drive_to_phase(session_dir, gitdir, [_blocking_finding("unchecked index", 2)],
                    head_path, RD.P_AUDITS)
    seat = _audit_roster(session_dir)[0]
    _land(session_dir, seat, payload=_audit_payload(seat))
    out = RD.cmd_record_result(session_dir, seat)
    assert out["ok"] is True, out

    session_dir2, _gitdir2, _head_path2 = _drive_to_audits(tmp_path, name="v5-ignored")
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
        _land(session_dir2, tid, payload=_audit_payload(tid),
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


def test_vendor_echo_mismatch_discloses_recorded_source(tmp_path, adapters):
    """E9 — envelope vendor echo mismatch discloses; source governs."""
    session_dir, _gitdir, _head_path = _drive_to_audits(tmp_path)
    seat = _audit_roster(session_dir)[0]
    evidence = _execution_evidence(source="codex")
    _land(session_dir, seat, payload=_audit_payload(seat), vendor="claude",
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


def test_record_result_sweep_refuses_dispatch_observed_audits(tmp_path, adapters):
    """E10 — record-result --sweep refuses the same provenance-underivable as advance sweep."""
    session_dir, _gitdir, _head_path = _drive_to_audits(tmp_path)
    seat = _audit_roster(session_dir)[0]
    evidence = _execution_evidence(source="codex")
    _land(session_dir, seat, payload=_audit_payload(seat),
          provenance=round_records.PROVENANCE_DISPATCH_OBSERVED, executionEvidence=evidence)
    out = RD.cmd_record_result(session_dir, sweep=True)
    assert out["ok"] is False and out["reason"] == "provenance-underivable"


def test_advance_derives_collection_manifest_from_runner_record(tmp_path, adapters):
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
        _land(session_dir, tid, payload=_audit_payload(tid),
              provenance=round_records.PROVENANCE_HAND_LANDED, executionEvidence=evidence)
        assert RD.cmd_record_result(session_dir, tid)["ok"] is True
    out = RD.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is True, out
    state = _state(session_dir)
    assert state["rounds"][str(pend["round"])]["auditProvenance"] == "runner-record"
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
