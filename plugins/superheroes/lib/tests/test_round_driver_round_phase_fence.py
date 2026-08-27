#!/usr/bin/env python3
"""#1177-C — round/phase addressing fence on durable-record commands.

Real driver, real adapters, real session dir — reuses `test_round_driver_integration` harness.
"""
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
_blocking_finding = _TDI._blocking_finding
_state = _TDI._state
_fake_git = _TDI._fake_git
_drive_to_phase = _TDI._drive_to_phase
_drive_one_phase = _TDI._drive_one_phase
_auditor_vendor_for = _TDI._auditor_vendor_for

REASON = round_driver.ROUND_PHASE_NOT_PENDING_REFUSAL
P_AUDITS = round_driver.P_AUDITS


def _audit_payload(seat, ruling="not-discharged"):
    return {"id": seat, "ruling": ruling, "auditorVendor": "claude",
            "reason": "re-read the fixed hunk; defect persists"}


def _store_bytes_snapshot(session_dir):
    """Byte snapshot of every file under session ``seats/`` trees."""
    snap = {}
    for root, _dirs, files in os.walk(session_dir):
        norm = root.replace("\\", "/")
        if "/seats/" not in norm:
            continue
        for name in files:
            path = os.path.join(root, name)
            with open(path, "rb") as fh:
                snap[path] = fh.read()
    return snap


def _complete_audits_not_discharged(session_dir, gitdir, ruling="not-discharged"):
    """Land + record every audit roster slot, then advance."""
    state = _state(session_dir)
    pend = state["pending"]
    assert pend["phase"] == P_AUDITS
    roster, reason = round_adapters.roster_for(pend["phase"], state, state.get("config") or {})
    assert reason is None
    slots = _slots_of(roster)
    _write_dispatch_manifest(session_dir, pend, slots, _auditor_vendor_for(state))
    for seat, occurrence in slots:
        _land(session_dir, state, pend, seat, _audit_payload(seat, ruling), occurrence=occurrence)
        out = round_driver.cmd_record_result(session_dir, seat, occurrence=occurrence)
        assert out["ok"], out
    return round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))


def _drive_until_audits_round(session_dir, gitdir, findings, head_path, target_round, max_steps=50):
    """Drive the real loop until ``dispatch-audits`` is pending at ``target_round``."""
    for _ in range(max_steps):
        state = _state(session_dir)
        if state.get("terminal"):
            raise AssertionError("session terminal before round %d audits" % target_round)
        pend = state["pending"]
        if pend["phase"] == P_AUDITS and pend["round"] == target_round:
            return pend
        if pend["phase"] == P_AUDITS:
            out = _complete_audits_not_discharged(session_dir, gitdir)
            assert out["ok"], out
        elif pend["phase"] == round_driver.P_STALL:
            art = {"choice": round_driver.ONE_MORE_ROUND_CHOICE}
            path = os.path.join(session_dir, "stall-artifact.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(art, fh)
            out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir),
                                          owner_artifact_path=path)
            if not out.get("ok") and out.get("reason") == "fold-refused":
                art = {"choice": round_driver.HOLD_CHOICE}
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(art, fh)
                out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir),
                                              owner_artifact_path=path)
            assert out["ok"], out
        else:
            phase, out = _drive_one_phase(session_dir, gitdir, findings, head_path)
            assert out["ok"], (phase, out)
    raise AssertionError("never reached round %d audits" % target_round)


def _setup_audits_pending(tmp_path):
    findings = [_blocking_finding("missing bounds guard", 2)]
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="fence")
    _drive_to_phase(session_dir, gitdir, findings, head_path, P_AUDITS)
    state = _state(session_dir)
    pend = state["pending"]
    tid = state["_auditTargets"][0]["id"]
    roster, _ = round_adapters.roster_for(pend["phase"], state, state.get("config") or {})
    slots = _slots_of(roster)
    _write_dispatch_manifest(session_dir, pend, slots, _auditor_vendor_for(state))
    return session_dir, gitdir, head_path, findings, pend, tid, slots


def test_cross_round_replay_false_accept_then_fenced_refusal(tmp_path):
    """Headline: same (phase, seat, occurrence, attempt) recurs across rounds — stale addressing
    refuses; bare replay still accepts (pre-fix false-accept demonstrated for contrast)."""
    findings = [_blocking_finding("missing bounds guard", 2)]
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="cross-round")
    # round 2 is the first audit phase on the real path
    _drive_to_phase(session_dir, gitdir, findings, head_path, P_AUDITS)
    state = _state(session_dir)
    pend_r2 = state["pending"]
    assert pend_r2["round"] == 2
    tid = state["_auditTargets"][0]["id"]
    roster, _ = round_adapters.roster_for(pend_r2["phase"], state, state.get("config") or {})
    slots = _slots_of(roster)
    _write_dispatch_manifest(session_dir, pend_r2, slots, _auditor_vendor_for(state))
    _land(session_dir, state, pend_r2, tid, _audit_payload(tid), occurrence=0)
    legit = round_driver.cmd_record_result(
        session_dir, tid, attempt=pend_r2["attempt"],
        expect_round=pend_r2["round"], expect_phase=pend_r2["phase"])
    assert legit["ok"] is True, legit
    stale_kwargs = {
        "seat": tid,
        "attempt": pend_r2["attempt"],
        "expect_round": pend_r2["round"],
        "expect_phase": pend_r2["phase"],
    }

    out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"], out
    pend_r3 = _drive_until_audits_round(session_dir, gitdir, findings, head_path, 3)
    state = _state(session_dir)
    assert pend_r3["round"] == 3
    assert pend_r3["phase"] == P_AUDITS
    assert pend_r3["attempt"] == pend_r2["attempt"] == 0
    assert state["_auditTargets"][0]["id"] == tid
    _land(session_dir, state, pend_r3, tid, _audit_payload(tid), occurrence=0)

    bare = round_driver.cmd_record_result(
        session_dir, stale_kwargs["seat"], attempt=stale_kwargs["attempt"])
    assert bare["ok"] is True, bare

    store_before = _store_bytes_snapshot(session_dir)
    state_before = round_driver.state_hash(_state(session_dir))
    refused = round_driver.cmd_record_result(
        session_dir, stale_kwargs["seat"], attempt=stale_kwargs["attempt"],
        expect_round=stale_kwargs["expect_round"], expect_phase=stale_kwargs["expect_phase"])
    assert refused["ok"] is False and refused["reason"] == REASON, refused
    assert refused.get("expectedRound") == stale_kwargs["expect_round"]
    assert refused.get("pendingRound") == pend_r3["round"]
    assert refused.get("expectedPhase") is None
    assert refused.get("pendingPhase") is None
    assert _store_bytes_snapshot(session_dir) == store_before
    assert round_driver.state_hash(_state(session_dir)) == state_before


# Enumerated pass/refuse matrix — both commands, both argument legs.
_MATRIX_ROWS = [
    ("none_none", None, None, True),
    ("match_round_omit_phase", "match_round", None, True),
    ("omit_round_match_phase", None, "match_phase", True),
    ("match_match", "match_round", "match_phase", True),
    ("stale_round_match_phase", "stale_round", "match_phase", False),
    ("match_round_wrong_phase", "match_round", "wrong_phase", False),
    ("stale_wrong", "stale_round", "wrong_phase", False),
]
_EXPECTED_MATRIX_CASES = len(_MATRIX_ROWS) * 2  # record-result + record-missing


@pytest.mark.parametrize(
    "cmd_name,row_id,round_sel,phase_sel,expect_ok",
    [(cmd, row[0], row[1], row[2], row[3])
     for cmd in ("record-result", "record-missing")
     for row in _MATRIX_ROWS],
    ids=["%s_%s" % (cmd, row[0]) for cmd in ("record-result", "record-missing")
         for row in _MATRIX_ROWS],
)
def test_round_phase_fence_matrix(tmp_path, cmd_name, row_id, round_sel, phase_sel, expect_ok):
    session_dir, gitdir, _head_path, _findings, pend, tid, slots = _setup_audits_pending(tmp_path)
    match_round = pend["round"]
    stale_round = match_round - 1
    match_phase = pend["phase"]
    wrong_phase = round_driver.P_PANEL

    def _resolve(sel):
        if sel is None:
            return None
        if sel == "match_round":
            return match_round
        if sel == "stale_round":
            return stale_round
        if sel == "match_phase":
            return match_phase
        if sel == "wrong_phase":
            return wrong_phase
        raise AssertionError(sel)

    expect_round = _resolve(round_sel)
    expect_phase = _resolve(phase_sel)

    if cmd_name == "record-result":
        state = _state(session_dir)
        _land(session_dir, state, pend, tid, _audit_payload(tid), occurrence=0)
        out = round_driver.cmd_record_result(
            session_dir, tid, attempt=pend["attempt"],
            expect_round=expect_round, expect_phase=expect_phase)
    else:
        # record-missing on a roster seat with no landing/store
        other = tid
        if len(slots) > 1:
            other = slots[1][0]
        out = round_driver.cmd_record_missing(
            session_dir, other, pend["attempt"], "forfeit",
            expect_round=expect_round, expect_phase=expect_phase)

    if expect_ok:
        assert out["ok"] is True, (row_id, cmd_name, out)
    else:
        assert out["ok"] is False and out["reason"] == REASON, (row_id, cmd_name, out)


def test_matrix_case_count_matches_table():
    assert len(_MATRIX_ROWS) * 2 == _EXPECTED_MATRIX_CASES == 14


def test_sweep_fenced_with_stale_round(tmp_path):
    session_dir, _gitdir, _head_path, _findings, pend, tid, slots = _setup_audits_pending(tmp_path)
    state = _state(session_dir)
    for seat, occurrence in slots:
        _land(session_dir, state, pend, seat, _audit_payload(seat), occurrence=occurrence)
    store_before = _store_bytes_snapshot(session_dir)
    out = round_driver.cmd_record_result(
        session_dir, sweep=True, expect_round=pend["round"] - 1, expect_phase=pend["phase"])
    assert out["ok"] is False and out["reason"] == REASON, out
    assert _store_bytes_snapshot(session_dir) == store_before


def test_store_and_state_untouched_on_refusal(tmp_path):
    session_dir, _gitdir, _head_path, _findings, pend, tid, _slots = _setup_audits_pending(tmp_path)
    state = _state(session_dir)
    _land(session_dir, state, pend, tid, _audit_payload(tid), occurrence=0)
    store_before = _store_bytes_snapshot(session_dir)
    state_before_hash = round_driver.state_hash(_state(session_dir))
    latches_before = (_state(session_dir).get("_advanceUsed"), _state(session_dir).get("_submitUsed"))
    out = round_driver.cmd_record_result(
        session_dir, tid, attempt=pend["attempt"],
        expect_round=pend["round"] - 1, expect_phase=pend["phase"])
    assert out["ok"] is False and out["reason"] == REASON, out
    assert _store_bytes_snapshot(session_dir) == store_before
    assert round_driver.state_hash(_state(session_dir)) == state_before_hash
    latches_after = (_state(session_dir).get("_advanceUsed"), _state(session_dir).get("_submitUsed"))
    assert latches_after == latches_before


def test_no_pending_phase_wins_over_addressing(tmp_path):
    session_dir, gitdir, head_path, findings, _pend, tid, _slots = _setup_audits_pending(tmp_path)
    folded = []
    while not _state(session_dir).get("terminal"):
        if _state(session_dir)["pending"]["phase"] == P_AUDITS:
            break
        phase, out = _drive_one_phase(session_dir, gitdir, findings, head_path)
        assert out["ok"], (phase, out)
        folded.append(phase)
    state = _state(session_dir)
    state["pending"] = None
    round_driver.save_state(session_dir, state)
    out = round_driver.cmd_record_result(
        session_dir, tid, attempt=0, expect_round=2, expect_phase=P_AUDITS)
    assert out["ok"] is False and out["reason"] == "no-pending-phase", out


def test_back_compat_no_new_args(tmp_path):
    session_dir, _gitdir, _head_path, _findings, pend, tid, _slots = _setup_audits_pending(tmp_path)
    state = _state(session_dir)
    _land(session_dir, state, pend, tid, _audit_payload(tid), occurrence=0)
    out = round_driver.cmd_record_result(session_dir, tid, attempt=pend["attempt"])
    assert out["ok"] is True, out
    assert out["round"] == pend["round"]
    assert out["phase"] == pend["phase"]


def _last_journal_recorded(session_dir, cmd):
    rows = [e for e in round_driver.read_journal(session_dir)
            if e.get("cmd") == cmd and e.get("outcome") == "recorded"]
    assert rows, "no %s recorded journal row" % cmd
    return rows[-1]


def test_journal_addressed_true_when_round_phase_echoed(tmp_path):
    """#1177-C bite-proof: journal addressed distinguishes fenced durable-record calls."""
    session_dir, _gitdir, _head_path, _findings, pend, tid, _slots = _setup_audits_pending(tmp_path)
    state = _state(session_dir)
    _land(session_dir, state, pend, tid, _audit_payload(tid), occurrence=0)
    out = round_driver.cmd_record_result(
        session_dir, tid, attempt=pend["attempt"],
        expect_round=pend["round"], expect_phase=pend["phase"])
    assert out["ok"] is True, out
    entry = _last_journal_recorded(session_dir, "record-result")
    assert entry["addressed"] is True


def test_journal_addressed_false_when_addressing_omitted(tmp_path):
    """#1177-C bite-proof: unaddressed durable-record calls journal addressed=false."""
    session_dir, _gitdir, _head_path, _findings, pend, tid, _slots = _setup_audits_pending(tmp_path)
    state = _state(session_dir)
    _land(session_dir, state, pend, tid, _audit_payload(tid), occurrence=0)
    out = round_driver.cmd_record_result(session_dir, tid, attempt=pend["attempt"])
    assert out["ok"] is True, out
    entry = _last_journal_recorded(session_dir, "record-result")
    assert entry["addressed"] is False


def test_journal_addressed_record_missing_both_directions(tmp_path):
    findings = [_blocking_finding("missing bounds guard", 2)]
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="fence-addressed")
    _drive_to_phase(session_dir, gitdir, findings, head_path, P_AUDITS)
    state = _state(session_dir)
    pend = state["pending"]
    roster, _ = round_adapters.roster_for(pend["phase"], state, state.get("config") or {})
    slots = _slots_of(roster)
    _write_dispatch_manifest(session_dir, pend, slots, _auditor_vendor_for(state))
    other = slots[1][0] if len(slots) > 1 else slots[0][0]
    addressed_out = round_driver.cmd_record_missing(
        session_dir, other, pend["attempt"], "forfeit",
        expect_round=pend["round"], expect_phase=pend["phase"])
    assert addressed_out["ok"] is True, addressed_out
    assert _last_journal_recorded(session_dir, "record-missing")["addressed"] is True

    session_dir2, gitdir2, head_path2 = _bootstrap(tmp_path, name="fence-unaddressed")
    _drive_to_phase(session_dir2, gitdir2, findings, head_path2, P_AUDITS)
    state2 = _state(session_dir2)
    pend2 = state2["pending"]
    roster2, _ = round_adapters.roster_for(pend2["phase"], state2, state2.get("config") or {})
    slots2 = _slots_of(roster2)
    _write_dispatch_manifest(session_dir2, pend2, slots2, _auditor_vendor_for(state2))
    other2 = slots2[1][0] if len(slots2) > 1 else slots2[0][0]
    bare_out = round_driver.cmd_record_missing(session_dir2, other2, pend2["attempt"], "forfeit")
    assert bare_out["ok"] is True, bare_out
    assert _last_journal_recorded(session_dir2, "record-missing")["addressed"] is False


def test_cli_record_result_stale_round_phase_refuses(tmp_path, capsys):
    session_dir, _gitdir, _head_path, _findings, pend, tid, _slots = _setup_audits_pending(tmp_path)
    state = _state(session_dir)
    _land(session_dir, state, pend, tid, _audit_payload(tid), occurrence=0)
    store_before = _store_bytes_snapshot(session_dir)
    rc = round_driver.main([
        "record-result", "--session-dir", session_dir,
        "--seat", tid, "--attempt", str(pend["attempt"]),
        "--round", str(pend["round"] - 1), "--phase", pend["phase"],
    ])
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert rc == 0
    assert out["ok"] is False and out["reason"] == REASON, out
    assert _store_bytes_snapshot(session_dir) == store_before


def test_cli_record_result_matching_round_phase_succeeds(tmp_path, capsys):
    session_dir, _gitdir, _head_path, _findings, pend, tid, _slots = _setup_audits_pending(tmp_path)
    state = _state(session_dir)
    _land(session_dir, state, pend, tid, _audit_payload(tid), occurrence=0)
    rc = round_driver.main([
        "record-result", "--session-dir", session_dir,
        "--seat", tid, "--attempt", str(pend["attempt"]),
        "--round", str(pend["round"]), "--phase", pend["phase"],
    ])
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert rc == 0
    assert out["ok"] is True, out


def test_cli_record_result_omitting_round_phase_retains_prior_behavior(tmp_path, capsys):
    session_dir, _gitdir, _head_path, _findings, pend, tid, _slots = _setup_audits_pending(tmp_path)
    state = _state(session_dir)
    _land(session_dir, state, pend, tid, _audit_payload(tid), occurrence=0)
    rc = round_driver.main([
        "record-result", "--session-dir", session_dir,
        "--seat", tid, "--attempt", str(pend["attempt"]),
    ])
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert rc == 0
    assert out["ok"] is True, out
    assert out["round"] == pend["round"]
    assert out["phase"] == pend["phase"]


def test_cli_record_missing_stale_round_phase_refuses(tmp_path, capsys):
    session_dir, _gitdir, _head_path, _findings, pend, tid, slots = _setup_audits_pending(tmp_path)
    other = slots[1][0] if len(slots) > 1 else tid
    store_before = _store_bytes_snapshot(session_dir)
    rc = round_driver.main([
        "record-missing", "--session-dir", session_dir,
        "--seat", other, "--attempt", str(pend["attempt"]), "--reason", "forfeit",
        "--round", str(pend["round"] - 1), "--phase", pend["phase"],
    ])
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert rc == 0
    assert out["ok"] is False and out["reason"] == REASON, out
    assert _store_bytes_snapshot(session_dir) == store_before


def test_cli_record_missing_matching_round_phase_succeeds(tmp_path, capsys):
    session_dir, _gitdir, _head_path, _findings, pend, tid, slots = _setup_audits_pending(tmp_path)
    other = slots[1][0] if len(slots) > 1 else tid
    rc = round_driver.main([
        "record-missing", "--session-dir", session_dir,
        "--seat", other, "--attempt", str(pend["attempt"]), "--reason", "forfeit",
        "--round", str(pend["round"]), "--phase", pend["phase"],
    ])
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert rc == 0
    assert out["ok"] is True, out


def test_cli_sweep_stale_round_refuses(tmp_path, capsys):
    session_dir, _gitdir, _head_path, _findings, pend, tid, slots = _setup_audits_pending(tmp_path)
    state = _state(session_dir)
    for seat, occurrence in slots:
        _land(session_dir, state, pend, seat, _audit_payload(seat), occurrence=occurrence)
    store_before = _store_bytes_snapshot(session_dir)
    rc = round_driver.main([
        "record-result", "--session-dir", session_dir, "--sweep",
        "--round", str(pend["round"] - 1), "--phase", pend["phase"],
    ])
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert rc == 0
    assert out["ok"] is False and out["reason"] == REASON, out
    assert _store_bytes_snapshot(session_dir) == store_before
