#!/usr/bin/env python3
"""#977 — the record-submit interleave fence and advance manifest disclosure.

Real driver, real adapters, real session dir — same discipline as
`test_round_driver_integration.py`. Reuses that module's harness helpers.
"""
import errno
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
import round_driver  # noqa: E402
import round_records  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "test_round_driver_integration",
    os.path.join(_HERE, "test_round_driver_integration.py"))
_TDI = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_TDI)

_bootstrap = _TDI._bootstrap
_land = _TDI._land
_write_dispatch_manifest = _TDI._write_dispatch_manifest
_slots_of = _TDI._slots_of
_payload_for = _TDI._payload_for
_blocking_finding = _TDI._blocking_finding
_state = _TDI._state
_fake_git = _TDI._fake_git
_drive_to_phase = _TDI._drive_to_phase
_auditor_vendor_for = _TDI._auditor_vendor_for
_blocking_finding_for_drive = _TDI._blocking_finding
_payload_for = _TDI._payload_for


def _panel_hand_artifact(session_dir):
    dims = round_driver._panel_dimensions(_state(session_dir)["config"])
    return {"seats": {dim: {"findings": [], "confidence": "high", "tier": round_driver.DEEP}
                      for dim in dims}}


def _verifier_hand_artifact():
    return {"verdicts": []}


def _hand_submit_panel(session_dir, panel_findings=None):
    if panel_findings is not None:
        state = _state(session_dir)
        pend = state["pending"]
        dims = round_driver._panel_dimensions(state["config"])
        art = {"seats": {dim: {"findings": [], "confidence": "high", "tier": round_driver.DEEP}
                         for dim in dims}}
        if panel_findings:
            seat = "code-reviewer"
            if seat in art["seats"]:
                art["seats"][seat] = {"findings": [dict(f) for f in panel_findings],
                                      "confidence": "high", "tier": round_driver.DEEP}
    else:
        art = _panel_hand_artifact(session_dir)
    state = _state(session_dir)
    pend = state["pending"]
    return round_driver.cmd_submit(session_dir, pend["phase"], pend["attempt"],
                                   round_driver.state_hash(state), art)


def _journal_recorded_for_phase(session_dir, phase, attempt):
    return [e for e in round_driver.read_journal(session_dir)
            if e.get("outcome") == "recorded" and e.get("phase") == phase
            and e.get("attempt") == attempt]


def _expected_cmd_names():
    return tuple(sorted(name for name in dir(round_driver) if name.startswith("cmd_")))


_EXPECTED_CMD_NAMES = (
    "cmd_advance",
    "cmd_attest",
    "cmd_next",
    "cmd_record_missing",
    "cmd_record_result",
    "cmd_submit",
)


def _land_panel_and_sweep(session_dir, gitdir, head_path, panel_findings=None):
    state = _state(session_dir)
    pend = state["pending"]
    assert pend["phase"] == round_driver.P_PANEL
    slots = _slots_of(round_adapters.roster_for(pend["phase"], state, state["config"])[0])
    _write_dispatch_manifest(session_dir, pend, slots, _auditor_vendor_for(state))
    findings = panel_findings if panel_findings is not None else []
    for seat, occurrence in slots:
        _land(session_dir, state, pend, seat,
              _payload_for(session_dir, state, pend, seat, findings, head_path),
              occurrence=occurrence)
    out = round_driver.cmd_record_result(session_dir, sweep=True)
    assert out["ok"] is True, out
    return pend, slots, out


def test_hand_submit_refused_after_record_sweep_pending_unchanged(tmp_path):
    """record-result --sweep then hand submit → record-submit-interleaved; pending survives."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    pend, _slots, _sweep = _land_panel_and_sweep(session_dir, gitdir, head_path)
    before = _state(session_dir)
    out = round_driver.cmd_submit(session_dir, pend["phase"], pend["attempt"],
                                  round_driver.state_hash(before), _panel_hand_artifact(session_dir))
    assert out["ok"] is False and out["reason"] == "record-submit-interleaved", out
    assert "advance" in out.get("detail", "")
    after = _state(session_dir)
    assert after["pending"] == before["pending"]
    assert after.get("_incompletePanel") is not True
    assert after["step"] == round_driver.P_PANEL


def test_hand_submit_without_store_records_still_folds(tmp_path):
    """Clean hand-submit round with no durable records is unchanged."""
    session_dir, _gitdir, _head_path = _bootstrap(tmp_path)
    state = _state(session_dir)
    pend = state["pending"]
    art = _panel_hand_artifact(session_dir)
    out = round_driver.cmd_submit(session_dir, pend["phase"], pend["attempt"],
                                  round_driver.state_hash(state), art)
    assert out["ok"] is True, out
    assert _state(session_dir)["step"] == round_driver.P_VERIFIERS


def test_stale_attempt_store_does_not_fire_fence(tmp_path):
    """A store record at attempt K while pending is K+1 leaves hand submit permitted."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    pend, _slots, _sweep = _land_panel_and_sweep(session_dir, gitdir, head_path)
    state = _state(session_dir)
    state["pending"] = dict(state["pending"], attempt=pend["attempt"] + 1)
    round_driver.save_state(session_dir, state)
    state = _state(session_dir)
    art = _panel_hand_artifact(session_dir)
    out = round_driver.cmd_submit(session_dir, pend["phase"], state["pending"]["attempt"],
                                  round_driver.state_hash(state), art)
    assert out["ok"] is True, out


def test_corrupt_store_file_at_pending_attempt_fires_fence(tmp_path):
    """Existence probe: unreadable JSON at the pending attempt still refuses hand submit."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    pend, slots, _sweep = _land_panel_and_sweep(session_dir, gitdir, head_path)
    seat, occurrence = slots[0]
    target_label = round_driver._slot_label(seat, occurrence)
    for other_seat, other_occurrence in slots[1:]:
        other_path = round_records.store_path(session_dir, pend["round"], pend["phase"],
                                              round_records.storage_key(other_seat, other_occurrence),
                                              pend["attempt"])
        os.remove(other_path)
    spath = round_records.store_path(session_dir, pend["round"], pend["phase"],
                                     round_records.storage_key(seat, occurrence), pend["attempt"])
    with open(spath, "w", encoding="utf-8") as fh:
        fh.write("[not-a-dict]")
    state = _state(session_dir)
    out = round_driver.cmd_submit(session_dir, pend["phase"], pend["attempt"],
                                  round_driver.state_hash(state), _panel_hand_artifact(session_dir))
    assert out["ok"] is False and out["reason"] == "record-submit-interleaved", out
    assert out["seats"] == [target_label], out


def test_advance_still_folds_with_records_present(tmp_path):
    """_via_advance=True exempts the record path from the fence."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    _land_panel_and_sweep(session_dir, gitdir, head_path,
                          [_blocking_finding("missing bounds guard", 2)])
    out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is True, out
    assert out["folded"]["phase"] == round_driver.P_PANEL


def test_hand_submit_non_adapter_phase_no_spurious_roster_journal(tmp_path):
    """Hand submit of a gate phase must not journal a roster-unavailable refusal."""
    session_dir, _gitdir, _head_path = _bootstrap(tmp_path, name="judgment-fence")
    state = _state(session_dir)
    finding = {"title": "widen the API", "severity": "Important", "file": "f.py", "line": 1,
               "tradeoff": True}
    state["step"] = round_driver.P_JUDGMENT
    state["_judgmentFindings"] = [finding]
    state["_judgmentMechanical"] = []
    state["pending"] = {"action": round_driver.P_JUDGMENT, "round": 1,
                        "phase": round_driver.P_JUDGMENT, "attempt": 0, "payload": {}}
    round_driver.save_state(session_dir, state)
    state = _state(session_dir)
    before = len(round_driver.read_journal(session_dir))
    row_id = round_driver._judgment_row_ids([finding])[0]
    art = {"dispositions": [{"id": row_id, "disposition": "skip", "reason": "owner declined"}]}
    out = round_driver.cmd_submit(session_dir, round_driver.P_JUDGMENT, 0,
                                  round_driver.state_hash(state), art)
    assert out["ok"] is True, out
    added = round_driver.read_journal(session_dir)[before:]
    spurious = [e for e in added if e.get("reason") == "roster-unavailable"]
    assert spurious == [], spurious


def test_durable_slot_records_broken_symlink_fires_fence(tmp_path):
    """Existence probe: a broken symlink at the pending attempt counts as present."""
    session_dir = str(tmp_path / "symlink-probe")
    os.makedirs(session_dir, exist_ok=True)
    roster = ["code-reviewer"]
    rnd, phase, attempt = 1, round_driver.P_PANEL, 0
    spath = round_records.store_path(session_dir, rnd, phase,
                                     round_records.storage_key("code-reviewer", 0), attempt)
    os.makedirs(os.path.dirname(spath), exist_ok=True)
    os.symlink(os.path.join(session_dir, "missing-record.json"), spath)
    found = round_driver._durable_slot_records(session_dir, rnd, phase, attempt, roster)
    assert found == ["code-reviewer"], found


def test_durable_slot_records_absent_store_does_not_fire_fence(tmp_path):
    """Existence probe: a genuinely absent store file is not reported."""
    session_dir = str(tmp_path / "absent-probe")
    os.makedirs(session_dir, exist_ok=True)
    roster = ["code-reviewer"]
    rnd, phase, attempt = 1, round_driver.P_PANEL, 0
    found = round_driver._durable_slot_records(session_dir, rnd, phase, attempt, roster)
    assert found == [], found


def test_durable_slot_records_second_occurrence_only(tmp_path):
    """Repeated roster key: only the occurrence-1 store path is reported."""
    session_dir = str(tmp_path / "probe")
    os.makedirs(session_dir, exist_ok=True)
    roster = ["t", "t"]
    rnd, phase, attempt = 1, round_driver.P_PANEL, 0
    spath = round_records.store_path(session_dir, rnd, phase,
                                     round_records.storage_key("t", 1), attempt)
    os.makedirs(os.path.dirname(spath), exist_ok=True)
    with open(spath, "w", encoding="utf-8") as fh:
        fh.write("{}")
    found = round_driver._durable_slot_records(session_dir, rnd, phase, attempt, roster)
    assert found == ["t#1"], found


def test_second_distinct_audit_target_record_fires_fence_on_hand_submit(tmp_path):
    """Natural two-target audits roster: a record on only the second slot fires the fence."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="second-slot")
    findings = [_blocking_finding("unchecked index", 2), _blocking_finding("unchecked index", 3)]
    _drive_to_phase(session_dir, gitdir, findings, head_path, round_driver.P_AUDITS)
    state = _state(session_dir)
    targets = state["_auditTargets"]
    assert len(targets) == 2 and targets[0]["id"] != targets[1]["id"], targets
    tid0, tid1 = targets[0]["id"], targets[1]["id"]
    pend = state["pending"]
    _write_dispatch_manifest(session_dir, pend, [(tid0, 0), (tid1, 0)], _auditor_vendor_for(state))
    _land(session_dir, state, pend, tid1,
          {"id": tid1, "ruling": "discharged", "reason": "re-read the hunk; the defect is gone"})
    assert round_driver.cmd_record_result(session_dir, tid1, occurrence=0)["ok"] is True
    state = _state(session_dir)
    # Prior phases folded via `advance`; isolate the record-submit fence under test.
    state.pop("_advanceUsed", None)
    round_driver.save_state(session_dir, state)
    state = _state(session_dir)
    out = round_driver.cmd_submit(
        session_dir, pend["phase"], pend["attempt"], round_driver.state_hash(state),
        {"results": [{"id": tid0, "ruling": "discharged", "reason": "ok"},
                     {"id": tid1, "ruling": "discharged", "reason": "ok"}]})
    assert out["ok"] is False and out["reason"] == "record-submit-interleaved", out
    assert out.get("seats") == [tid1], out


def test_advance_reports_absent_dispatch_manifest_via_cmd_advance(tmp_path):
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    state = _state(session_dir)
    pend = state["pending"]
    slots = _slots_of(round_adapters.roster_for(pend["phase"], state, state["config"])[0])
    for seat, occurrence in slots:
        _land(session_dir, state, pend, seat,
              _payload_for(session_dir, state, pend, seat, [], head_path), occurrence=occurrence)
        assert round_driver.cmd_record_result(session_dir, seat, occurrence=occurrence)["ok"]
    expected = os.path.abspath(round_records.dispatch_manifest_path(
        session_dir, pend["round"], pend["phase"], pend["attempt"]))
    assert not os.path.exists(expected)
    out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is True, out
    disc = out.get("dispatchManifest")
    assert disc == {"path": expected, "status": "absent", "detail": None}, disc


def test_advance_reports_unreadable_dispatch_manifest_directory(tmp_path):
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    state = _state(session_dir)
    pend = state["pending"]
    slots = _slots_of(round_adapters.roster_for(pend["phase"], state, state["config"])[0])
    mpath = round_records.dispatch_manifest_path(session_dir, pend["round"], pend["phase"],
                                                 pend["attempt"])
    os.makedirs(mpath, exist_ok=True)
    for seat, occurrence in slots:
        _land(session_dir, state, pend, seat,
              _payload_for(session_dir, state, pend, seat, [], head_path), occurrence=occurrence)
        assert round_driver.cmd_record_result(session_dir, seat, occurrence=occurrence)["ok"]
    out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is True, out
    disc = out.get("dispatchManifest")
    assert disc["status"] == "unreadable", disc
    assert disc["path"] == os.path.abspath(mpath)
    assert disc["detail"] == "missing"


def test_advance_reports_unreadable_dispatch_manifest_invalid_utf8(tmp_path):
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    state = _state(session_dir)
    pend = state["pending"]
    slots = _slots_of(round_adapters.roster_for(pend["phase"], state, state["config"])[0])
    mpath = round_records.dispatch_manifest_path(session_dir, pend["round"], pend["phase"],
                                                 pend["attempt"])
    os.makedirs(os.path.dirname(mpath), exist_ok=True)
    with open(mpath, "wb") as fh:
        fh.write(b"\xff\xfe")
    for seat, occurrence in slots:
        _land(session_dir, state, pend, seat,
              _payload_for(session_dir, state, pend, seat, [], head_path), occurrence=occurrence)
        assert round_driver.cmd_record_result(session_dir, seat, occurrence=occurrence)["ok"]
    out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is True, out
    assert out.get("reason") != "driver-internal-exception", out
    disc = out.get("dispatchManifest")
    assert disc["status"] == "unreadable", disc
    assert disc["detail"] == "not-utf-8"


def _drive_one_phase_no_manifest(session_dir, gitdir, head_path, panel_findings):
    state = _state(session_dir)
    pend = state["pending"]
    roster, reason = round_adapters.roster_for(pend["phase"], state, state.get("config") or {})
    assert reason is None, (pend["phase"], reason)
    slots = _slots_of(roster)
    for seat, occurrence in slots:
        _land(session_dir, state, pend, seat,
              _payload_for(session_dir, state, pend, seat, panel_findings, head_path),
              occurrence=occurrence)
        assert round_driver.cmd_record_result(session_dir, seat, occurrence=occurrence)["ok"]
    return round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))


def _count_phases_to_terminal(session_dir, gitdir, head_path, panel_findings):
    count = 0
    for _ in range(30):
        if _state(session_dir).get("terminal"):
            return count
        out = _drive_one_phase_no_manifest(session_dir, gitdir, head_path, panel_findings)
        assert out["ok"] is True, out
        count += 1
    raise AssertionError("did not reach terminal in 30 phases")


def test_terminal_advance_disclosure_journal_fault_not_plain_ok(tmp_path, monkeypatch):
    """Disclosure journal append before the terminal receipt gate — a fault must not answer ok."""
    findings = []
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="terminal-fault-count")
    phases_to_terminal = _count_phases_to_terminal(session_dir, gitdir, head_path, findings)

    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="terminal-fault")
    for _ in range(phases_to_terminal - 1):
        out = _drive_one_phase_no_manifest(session_dir, gitdir, head_path, findings)
        assert out["ok"] is True, out

    real_append = round_driver._journal_append

    def fail_disclosure_append(sd, entry):
        if entry.get("outcome") == "dispatch-manifest-disclosure":
            round_driver._mark_journal_fault(sd, entry, OSError("simulated disclosure journal fault"))
            return
        return real_append(sd, entry)

    monkeypatch.setattr(round_driver, "_journal_append", fail_disclosure_append)
    out = _drive_one_phase_no_manifest(session_dir, gitdir, head_path, findings)
    assert out.get("ok") is not True, out
    # Fold path wraps receipt-fault as reason=fold-refused with detail=receipt-fault.
    assert "receipt-fault" in (out.get("reason"), out.get("detail")), out


def test_advance_audits_without_manifest_discloses_absent(tmp_path):
    """dispatch-audits with no manifest carries disclosure on the advance response."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="audits-disc")
    findings = [_blocking_finding("unchecked index", 2), _blocking_finding("unchecked index", 3)]
    _drive_to_phase(session_dir, gitdir, findings, head_path, round_driver.P_AUDITS)
    state = _state(session_dir)
    pend = state["pending"]
    assert pend["phase"] == round_driver.P_AUDITS
    targets = state["_auditTargets"]
    assert len(targets) == 2, targets
    tid0, tid1 = targets[0]["id"], targets[1]["id"]
    roster, reason = round_adapters.roster_for(round_driver.P_AUDITS, state, state.get("config") or {})
    assert reason is None and roster == [tid0, tid1], roster
    for tid in (tid0, tid1):
        _land(session_dir, state, pend, tid,
              {"id": tid, "ruling": "discharged", "auditorVendor": "claude",
               "reason": "re-read the fixed hunk; the cited defect is gone"})
        assert round_driver.cmd_record_result(session_dir, tid, occurrence=0)["ok"]
    expected = os.path.abspath(round_records.dispatch_manifest_path(
        session_dir, pend["round"], pend["phase"], pend["attempt"]))
    assert not os.path.exists(expected)
    out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out.get("dispatchManifest") == {
        "path": expected, "status": "absent", "detail": None}, out
    assert out["ok"] is True, out
    assert out["folded"]["phase"] == round_driver.P_AUDITS


def test_advance_reports_unreadable_dispatch_manifest(tmp_path):
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    state = _state(session_dir)
    pend = state["pending"]
    slots = _slots_of(round_adapters.roster_for(pend["phase"], state, state["config"])[0])
    mpath = round_records.dispatch_manifest_path(session_dir, pend["round"], pend["phase"],
                                                 pend["attempt"])
    os.makedirs(os.path.dirname(mpath), exist_ok=True)
    with open(mpath, "w", encoding="utf-8") as fh:
        fh.write("not json")
    for seat, occurrence in slots:
        _land(session_dir, state, pend, seat,
              _payload_for(session_dir, state, pend, seat, [], head_path), occurrence=occurrence)
        assert round_driver.cmd_record_result(session_dir, seat, occurrence=occurrence)["ok"]
    out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is True, out
    disc = out.get("dispatchManifest")
    assert disc["status"] == "unreadable", disc
    assert disc["path"] == os.path.abspath(mpath)
    assert disc["detail"] == "unparseable"


def test_wedge_closed(tmp_path):
    """Hand-submit panel, then record-result on the next phase is refused; hand submit still works."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    findings = [_blocking_finding("missing bounds guard", 2)]
    assert _hand_submit_panel(session_dir, findings)["ok"] is True
    assert _state(session_dir).get("_submitUsed") is True
    nxt = round_driver.cmd_next(session_dir)
    assert nxt["ok"] is True, nxt
    state = _state(session_dir)
    pend = state["pending"]
    assert pend["phase"] == round_driver.P_VERIFIERS
    roster, reason = round_adapters.roster_for(pend["phase"], state, state["config"])
    assert reason is None, reason
    seat, occurrence = _slots_of(roster)[0]
    _land(session_dir, state, pend, seat,
          _payload_for(session_dir, state, pend, seat, [], head_path), occurrence=occurrence)
    out = round_driver.cmd_record_result(session_dir, seat, occurrence=occurrence)
    assert out["ok"] is False and out["reason"] == "record-submit-interleaved", out
    state = _state(session_dir)
    submit = round_driver.cmd_submit(session_dir, pend["phase"], pend["attempt"],
                                     round_driver.state_hash(state), _verifier_hand_artifact())
    assert submit["ok"] is True, submit


def test_record_missing_honours_latch(tmp_path):
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    assert _hand_submit_panel(session_dir, [_blocking_finding("missing bounds guard", 2)])["ok"] is True
    assert round_driver.cmd_next(session_dir)["ok"] is True
    state = _state(session_dir)
    pend = state["pending"]
    roster, reason = round_adapters.roster_for(pend["phase"], state, state["config"])
    assert reason is None, reason
    seat, _occurrence = _slots_of(roster)[0]
    out = round_driver.cmd_record_missing(session_dir, seat, pend["attempt"], "no artifact")
    assert out["ok"] is False and out["reason"] == "record-submit-interleaved", out


def test_no_record_written_on_refusal(tmp_path):
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    assert _hand_submit_panel(session_dir, [_blocking_finding("missing bounds guard", 2)])["ok"] is True
    assert round_driver.cmd_next(session_dir)["ok"] is True
    state = _state(session_dir)
    pend = state["pending"]
    roster, reason = round_adapters.roster_for(pend["phase"], state, state["config"])
    assert reason is None, reason
    seat, occurrence = _slots_of(roster)[0]
    _land(session_dir, state, pend, seat,
          _payload_for(session_dir, state, pend, seat, [], head_path), occurrence=occurrence)
    out = round_driver.cmd_record_result(session_dir, seat, occurrence=occurrence)
    assert out["ok"] is False and out["reason"] == "record-submit-interleaved", out
    spath = round_records.store_path(session_dir, pend["round"], pend["phase"],
                                     round_records.storage_key(seat, occurrence), pend["attempt"])
    assert not os.path.exists(spath)
    assert _journal_recorded_for_phase(session_dir, pend["phase"], pend["attempt"]) == []


def test_advance_still_records(tmp_path):
    """Record-path session: record-result then advance still folds — latch does not fire."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    state = _state(session_dir)
    pend = state["pending"]
    slots = _slots_of(round_adapters.roster_for(pend["phase"], state, state["config"])[0])
    _write_dispatch_manifest(session_dir, pend, slots, _auditor_vendor_for(state))
    for seat, occurrence in slots:
        _land(session_dir, state, pend, seat,
              _payload_for(session_dir, state, pend, seat, [], head_path), occurrence=occurrence)
        assert round_driver.cmd_record_result(session_dir, seat, occurrence=occurrence)["ok"]
    out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is True, out
    assert out["folded"]["phase"] == round_driver.P_PANEL


def test_entry_point_census():
    """Every cmd_* entry point must be enumerated — a new one forces a durable-record decision."""
    assert _expected_cmd_names() == _EXPECTED_CMD_NAMES, (
        "cmd_* census drift — add the new entry point and decide whether it writes durable records")


def test_valueerror_slot_counts_present(tmp_path):
    """`_reserved` raises in storage_key — fence fail-closed reports the slot without a store file."""
    session_dir = str(tmp_path / "valueerror-probe")
    os.makedirs(session_dir, exist_ok=True)
    roster = ["_reserved"]
    rnd, phase, attempt = 1, round_driver.P_PANEL, 0
    found = round_driver._durable_slot_records(session_dir, rnd, phase, attempt, roster)
    assert found == ["_reserved"], found


def test_store_file_exists_non_enoent_fails_closed(tmp_path, monkeypatch):
    session_dir = str(tmp_path / "lstat-probe")
    os.makedirs(session_dir, exist_ok=True)
    spath = os.path.join(session_dir, "probe.json")
    with open(spath, "w", encoding="utf-8") as fh:
        fh.write("{}")

    def deny_lstat(_path):
        raise OSError(errno.EACCES, "permission denied")

    monkeypatch.setattr(round_driver.os, "lstat", deny_lstat)
    assert round_driver._store_file_exists(spath) is True

    def missing_lstat(_path):
        raise OSError(errno.ENOENT, "no such file")

    monkeypatch.setattr(round_driver.os, "lstat", missing_lstat)
    assert round_driver._store_file_exists(spath) is False

    def notdir_lstat(_path):
        raise OSError(errno.ENOTDIR, "not a directory")

    monkeypatch.setattr(round_driver.os, "lstat", notdir_lstat)
    assert round_driver._store_file_exists(spath) is False


def test_disclosure_present_on_failure_response(tmp_path):
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    state = _state(session_dir)
    pend = state["pending"]
    slots = _slots_of(round_adapters.roster_for(pend["phase"], state, state["config"])[0])
    for seat, occurrence in slots:
        _land(session_dir, state, pend, seat,
              _payload_for(session_dir, state, pend, seat, [], head_path), occurrence=occurrence)
        assert round_driver.cmd_record_result(session_dir, seat, occurrence=occurrence)["ok"]
    seat, occurrence = slots[0]
    spath = round_records.store_path(session_dir, pend["round"], pend["phase"],
                                     round_records.storage_key(seat, occurrence), pend["attempt"])
    with open(spath, encoding="utf-8") as fh:
        envelope = json.load(fh)
    del envelope["payload"]
    with open(spath, "w", encoding="utf-8") as fh:
        json.dump(envelope, fh)
    expected = os.path.abspath(round_records.dispatch_manifest_path(
        session_dir, pend["round"], pend["phase"], pend["attempt"]))
    assert "_dispatch.a%d.json" % pend["attempt"] in expected
    assert not os.path.exists(expected)
    out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is False and out["reason"] == "assemble-refused", out
    disc = out.get("dispatchManifest")
    assert disc == {"path": expected, "status": "absent", "detail": None}, disc
    journaled = [e for e in round_driver.read_journal(session_dir)
                 if e.get("outcome") == "dispatch-manifest-disclosure"]
    assert journaled and journaled[-1]["status"] == "absent"
    assert journaled[-1]["path"] == expected


def test_legacy_hand_path_session_can_still_fold(tmp_path):
    """Legacy state: durable records plus _submitUsed — hand submit folds and journals orphans."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    pend, slots, _sweep = _land_panel_and_sweep(session_dir, gitdir, head_path)
    state = _state(session_dir)
    state["_submitUsed"] = True
    round_driver.save_state(session_dir, state)
    state = _state(session_dir)
    before_journal = len(round_driver.read_journal(session_dir))
    out = round_driver.cmd_submit(session_dir, pend["phase"], pend["attempt"],
                                  round_driver.state_hash(state), _panel_hand_artifact(session_dir))
    assert out["ok"] is True, out
    assert _state(session_dir)["step"] == round_driver.P_VERIFIERS
    orphan_rows = [e for e in round_driver.read_journal(session_dir)[before_journal:]
                   if e.get("outcome") == "record-orphans-ignored"]
    assert len(orphan_rows) == 1, orphan_rows
    expected_seats = sorted(round_driver._slot_label(s, o) for s, o in slots)
    assert orphan_rows[0].get("seats") == expected_seats, orphan_rows[0]


def test_orphan_journal_not_repeated_on_later_hand_submit_same_round(tmp_path):
    """Orphan disclosure journals once at the submit that found records — not every later hand fold."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    pend, slots, _sweep = _land_panel_and_sweep(session_dir, gitdir, head_path)
    state = _state(session_dir)
    state["_submitUsed"] = True
    round_driver.save_state(session_dir, state)
    state = _state(session_dir)
    before_orphan_journal = len(
        [e for e in round_driver.read_journal(session_dir)
         if e.get("outcome") == "record-orphans-ignored"])
    panel_phase, panel_attempt = pend["phase"], pend["attempt"]
    out = round_driver.cmd_submit(session_dir, pend["phase"], pend["attempt"],
                                  round_driver.state_hash(state), _panel_hand_artifact(session_dir))
    assert out["ok"] is True, out
    orphan_rows = [e for e in round_driver.read_journal(session_dir)
                   if e.get("outcome") == "record-orphans-ignored"]
    assert len(orphan_rows) == before_orphan_journal + 1, orphan_rows
    first_row = orphan_rows[-1]
    assert first_row["phase"] == panel_phase and first_row["attempt"] == panel_attempt, first_row
    expected_seats = sorted(round_driver._slot_label(s, o) for s, o in slots)
    assert first_row.get("seats") == expected_seats, first_row

    assert round_driver.cmd_next(session_dir)["ok"] is True
    state = _state(session_dir)
    pend = state["pending"]
    assert pend["phase"] == round_driver.P_VERIFIERS
    out = round_driver.cmd_submit(session_dir, pend["phase"], pend["attempt"],
                                  round_driver.state_hash(state), _verifier_hand_artifact())
    assert out["ok"] is True, out
    orphan_rows = [e for e in round_driver.read_journal(session_dir)
                   if e.get("outcome") == "record-orphans-ignored"]
    assert len(orphan_rows) == before_orphan_journal + 1, orphan_rows
    assert orphan_rows[-1]["phase"] == panel_phase
    assert orphan_rows[-1]["attempt"] == panel_attempt


def test_record_orphans_ignored_on_receipt_degraded(tmp_path):
    """Hand submit with durable orphans discloses on the terminal receipt degraded channel."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    pend, slots, _sweep = _land_panel_and_sweep(session_dir, gitdir, head_path)
    state = _state(session_dir)
    state["_submitUsed"] = True
    round_driver.save_state(session_dir, state)
    state = _state(session_dir)
    out = round_driver.cmd_submit(session_dir, pend["phase"], pend["attempt"],
                                  round_driver.state_hash(state), _panel_hand_artifact(session_dir))
    assert out["ok"] is True, out
    receipt = round_driver.build_receipt(_state(session_dir), session_dir)
    degraded = "\n".join(receipt["degraded"])
    assert "record-orphans-ignored (round" in degraded
    round_entry = next(r for r in receipt["rounds"] if r["round"] == pend["round"])
    assert round_entry.get("recordOrphansIgnored")


def test_record_orphans_ignored_atomic_when_fold_aborts(tmp_path, monkeypatch):
    """Orphan disclosure and state key land together — neither without a successful submit-accept."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    pend, slots, _sweep = _land_panel_and_sweep(session_dir, gitdir, head_path)
    state = _state(session_dir)
    state["_submitUsed"] = True
    round_driver.save_state(session_dir, state)
    state = _state(session_dir)
    before_journal = len(round_driver.read_journal(session_dir))

    real_begin = round_driver.round_commit.begin

    def _abort_submit_accept_commit(session_dir_arg, kind, **kwargs):
        commit = real_begin(session_dir_arg, kind, **kwargs)
        if kind == "submit-accept":
            real_run = commit.run

            def _abort_run():
                raise RuntimeError("commit-aborted-for-test")

            commit.run = _abort_run
        return commit

    monkeypatch.setattr(round_driver.round_commit, "begin", _abort_submit_accept_commit)
    with pytest.raises(RuntimeError, match="commit-aborted-for-test"):
        round_driver.cmd_submit(session_dir, pend["phase"], pend["attempt"],
                                round_driver.state_hash(state),
                                _panel_hand_artifact(session_dir))
    disk_state = _state(session_dir)
    assert not (disk_state.get("rounds") or {}).get(str(pend["round"]), {}).get(
        "recordOrphansIgnored")
    orphan_rows = [e for e in round_driver.read_journal(session_dir)[before_journal:]
                   if e.get("outcome") == "record-orphans-ignored"]
    assert not orphan_rows


# Owner-gate phases park by design — outside the no-dead-end fold-path guarantee
# (reference/round-driver.md § record-submit interleave / no dead ends).
_OWNER_GATE_PHASES = frozenset({round_driver.P_JUDGMENT, round_driver.P_STALL})

_REFUSE_FOLD_PHASES = frozenset(
    phase for phase in round_adapters._MISSING_POLICY
    if round_adapters.missing_policy(phase) == round_adapters.MISSING_REFUSE_FOLD)

# Adapter phases the driver can pend — derived, never hand-copied.
_CENSUS_PHASES = tuple(round_adapters.ADAPTER_PHASES)

_LATCH_STATES = ("submit_used", "advance_used", "record_path")


def _census_panel_findings():
    return [_blocking_finding_for_drive("missing bounds guard", 2)]


def _hand_submit_artifact(session_dir, pend, panel_findings, head_path):
    phase = pend["phase"]
    if phase == round_driver.P_PANEL:
        return _panel_hand_artifact(session_dir)
    if phase == round_driver.P_VERIFIERS:
        return _verifier_hand_artifact()
    state = _state(session_dir)
    roster, reason = round_adapters.roster_for(phase, state, state["config"])
    assert reason is None, (phase, reason)
    seat, _occurrence = _slots_of(roster)[0]
    return _payload_for(session_dir, state, pend, seat, panel_findings, head_path)


def _record_all_roster_slots(session_dir, gitdir, head_path, pend, panel_findings):
    state = _state(session_dir)
    roster, reason = round_adapters.roster_for(pend["phase"], state, state["config"])
    assert reason is None, (pend["phase"], reason)
    slots = _slots_of(roster)
    _write_dispatch_manifest(session_dir, pend, slots, _auditor_vendor_for(state))
    for seat, occurrence in slots:
        _land(session_dir, state, pend, seat,
              _payload_for(session_dir, state, pend, seat, panel_findings, head_path),
              occurrence=occurrence)
        assert round_driver.cmd_record_result(session_dir, seat, occurrence=occurrence)["ok"]
    return slots


def _drive_census_phase(session_dir, gitdir, head_path, phase, panel_findings):
    """Reach `phase` pending with durable store records for the census cell."""
    if phase == round_driver.P_PANEL:
        return _land_panel_and_sweep(session_dir, gitdir, head_path, panel_findings)[0]
    try:
        _drive_to_phase(session_dir, gitdir, panel_findings, head_path, phase)
    except AssertionError as exc:
        pytest.skip("harness cannot reach %r: %s" % (phase, exc))
    state = _state(session_dir)
    pend = state["pending"]
    if pend["phase"] != phase:
        pytest.skip("harness stopped at %r before %r" % (pend["phase"], phase))
    return pend


def _apply_census_latch(session_dir, latch):
    state = _state(session_dir)
    if latch == "submit_used":
        state.pop("_advanceUsed", None)
        state["_submitUsed"] = True
    elif latch == "advance_used":
        state["_advanceUsed"] = True
    elif latch == "record_path":
        state.pop("_advanceUsed", None)
        state.pop("_submitUsed", None)
    else:
        raise ValueError("unknown latch %r" % latch)
    round_driver.save_state(session_dir, state)


def _census_records_shape(phase, latch):
    """Refuse-fold phases use the round-1 wedge (`seat-missing/1` only) on the hand-submit path."""
    return phase in _REFUSE_FOLD_PHASES and latch == "submit_used"


def _install_census_records(session_dir, gitdir, head_path, pend, panel_findings, latch):
    phase = pend["phase"]
    if _census_records_shape(phase, latch):
        state = _state(session_dir)
        roster, reason = round_adapters.roster_for(phase, state, state["config"])
        if reason is not None:
            pytest.skip("roster unavailable for %r wedge shape: %s" % (phase, reason))
        seat, _occurrence = _slots_of(roster)[0]
        out = round_driver.cmd_record_missing(session_dir, seat, pend["attempt"], "forfeit")
        assert out["ok"] is True, (phase, latch, out)
        return
    if phase == round_driver.P_PANEL:
        return
    _record_all_roster_slots(session_dir, gitdir, head_path, pend, panel_findings)


@pytest.mark.parametrize("latch", _LATCH_STATES)
@pytest.mark.parametrize("phase", _CENSUS_PHASES)
def test_no_dead_end_census(tmp_path, phase, latch):
    """Axis: phase kind × committed-path latch — every adapter phase keeps a legal fold command.

    Owner-gate phases (`present-judgment`, `present-stall-menu`) are excluded: their park is an
    intervention by design (reference/round-driver.md).
    """
    assert phase not in _OWNER_GATE_PHASES
    panel_findings = _census_panel_findings()
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="%s-%s" % (phase, latch))
    pend = _drive_census_phase(session_dir, gitdir, head_path, phase, panel_findings)
    _install_census_records(session_dir, gitdir, head_path, pend, panel_findings, latch)
    _apply_census_latch(session_dir, latch)
    state = _state(session_dir)
    artifact = _hand_submit_artifact(session_dir, pend, panel_findings, head_path)
    submit_out = round_driver.cmd_submit(
        session_dir, pend["phase"], pend["attempt"],
        round_driver.state_hash(state), artifact)
    advance_out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))
    cell = "phase=%r latch=%r" % (phase, latch)
    assert submit_out.get("ok") or advance_out.get("ok"), (
        "%s: no legal fold command — submit=%r advance=%r" % (cell, submit_out, advance_out))


def test_record_path_folds_after_fence_refusal(tmp_path):
    """After the fence refuses hand submit, advance folds the pending phase."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    pend, _slots, _sweep = _land_panel_and_sweep(session_dir, gitdir, head_path)
    state = _state(session_dir)
    refused = round_driver.cmd_submit(
        session_dir, pend["phase"], pend["attempt"],
        round_driver.state_hash(state), _panel_hand_artifact(session_dir))
    assert refused["ok"] is False and refused["reason"] == "record-submit-interleaved", refused
    assert _state(session_dir)["pending"] == state["pending"]
    out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is True, out
    assert out["folded"]["phase"] == round_driver.P_PANEL
