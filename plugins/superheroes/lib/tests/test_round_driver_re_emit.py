"""Layer 2i-b — re-emit, certification close, and the relocation fence (#1272)."""
import importlib.util
import json
import os
import subprocess
import sys

import pytest

import round_adapters  # noqa: E402
import round_certification as RC  # noqa: E402
import record_paths  # noqa: E402
import round_records as RR  # noqa: E402

import test_round_driver_session_mobility as M  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

_SPEC = importlib.util.spec_from_file_location(
    "round_driver", os.path.join(_LIB, "round_driver.py"))
RD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(RD)

_TDI_SPEC = importlib.util.spec_from_file_location(
    "test_round_driver_integration",
    os.path.join(_HERE, "test_round_driver_integration.py"))
_TDI = importlib.util.module_from_spec(_TDI_SPEC)
_TDI_SPEC.loader.exec_module(_TDI)


def _re_emit(session_dir, capsys, by="tester"):
    rc = RD.main(["re-emit", "--session-dir", session_dir, "--by", by])
    return rc, M._cli_json(capsys)


def _stale_session(tmp_path, capsys):
    repo = M._mobility_repo(tmp_path)
    sess = M._mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    M._relocate(session_dir, repo["root_b"], capsys)
    return repo, sess, session_dir


def _orders_dir(session_dir, rnd, phase):
    return os.path.join(session_dir, "round-%d" % rnd, "orders", phase)


def _collect_attempt_files(session_dir, rnd, phase, attempt):
    odir = _orders_dir(session_dir, rnd, phase)
    needle = ".a%d." % attempt
    paths = []
    if os.path.isdir(odir):
        for name in os.listdir(odir):
            if needle in name:
                paths.append(os.path.join(odir, name))
    manifest = RD._orders_manifest_path(session_dir, rnd, phase, attempt)
    if os.path.isfile(manifest):
        paths.append(manifest)
    return sorted(paths)


def _snapshot_order_bytes(session_dir, rnd, phase):
    snap = {}
    for attempt in (0, 1, 2):
        for path in _collect_attempt_files(session_dir, rnd, phase, attempt):
            snap[path] = M._read_bytes(path)
    return snap


def _anchor_for(session_dir, rnd, phase, attempt):
    ok, state = RD.load_state(session_dir)
    assert ok and state is not None
    return RD._orders_anchor(state, session_dir, rnd, phase, attempt)


def _last_refused(session_dir, reason):
    for row in reversed(M._journal_rows(session_dir)):
        if row.get("outcome") == "refused" and row.get("reason") == reason:
            return row
    return None


def _panel_roster(session_dir):
    ok, state = RD.load_state(session_dir)
    assert ok and state is not None
    pend = state["pending"]
    roster, reason = round_adapters.roster_for(pend["phase"], state, state.get("config") or {})
    assert reason is None, reason
    return state, pend, roster


def _first_seat(roster):
    seat = roster[0]
    if isinstance(seat, tuple):
        return seat[0], seat[1]
    return seat, 0


def _land_panel_seat(session_dir, state, pend, seat, occurrence, head_path):
    return _TDI._land(
        session_dir, state, pend, seat,
        _TDI._payload_for(session_dir, state, pend, seat, [], head_path),
        occurrence=occurrence,
    )


def _panel_hand_artifact(session_dir):
    state = json.load(open(os.path.join(session_dir, RD.STATE_FILE), encoding="utf-8"))
    dims = RD._panel_dimensions(state["config"])
    return {"seats": {dim: {"findings": [], "confidence": "high", "tier": RD.DEEP}
                      for dim in dims}}


def _dangling_symlink(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.lexists(path):
        os.remove(path)
    os.symlink(path + ".no-such-target", path)
    assert os.path.lexists(path) and not os.path.exists(path)


# --- re-emit (R*) ---------------------------------------------------------------------------

def test_re_emit_positive_after_relocate(tmp_path, capsys):
    repo, sess, session_dir = _stale_session(tmp_path, capsys)
    rnd, phase, old_attempt = 1, RD.P_PANEL, 0
    a0_files = {p: M._read_bytes(p) for p in _collect_attempt_files(session_dir, rnd, phase, old_attempt)}
    assert a0_files
    anchor0_before = _anchor_for(session_dir, rnd, phase, old_attempt)
    journal_path = os.path.join(session_dir, RD.JOURNAL_FILE)
    journal_before = M._read_bytes(journal_path)
    state_before = M._read_bytes(os.path.join(session_dir, RD.STATE_FILE))
    rc, out = _re_emit(session_dir, capsys)
    assert rc == 0
    assert out["ok"] is True
    assert out["superseded"]["attempt"] == 0
    ok, state = RD.load_state(session_dir)
    assert state["pending"]["attempt"] == 1
    for path, content in a0_files.items():
        assert M._read_bytes(path) == content
    anchor0_after = _anchor_for(session_dir, rnd, phase, old_attempt)
    assert json.dumps(anchor0_after, sort_keys=True) == json.dumps(anchor0_before, sort_keys=True)
    assert _anchor_for(session_dir, rnd, phase, 1) is not None
    assert M._read_bytes(journal_path).startswith(journal_before)
    assert M._read_bytes(os.path.join(session_dir, RD.STATE_FILE)) != state_before
    rows = M._journal_rows(session_dir)
    relocated = next(r for r in rows if r.get("outcome") == "relocated")
    superseded = rows[-2]
    emitted = rows[-1]
    assert superseded["outcome"] == "orders-superseded"
    assert superseded["attempt"] == 0
    assert superseded["newAttempt"] == 1
    assert superseded["supersededManifestSha256"] == anchor0_before["manifestSha256"]
    assert superseded["supersededOrderSha256"] == anchor0_before["orders"]
    assert superseded["relocation"] == {
        "oldRoot": relocated["oldRoot"],
        "newRoot": relocated["newRoot"],
        "oldBranch": relocated["oldBranch"],
        "newBranch": relocated["newBranch"],
        "sessionDir": relocated["sessionDir"],
        "at": relocated["at"],
    }
    assert emitted["outcome"] == "orders-emitted"
    assert emitted["cmd"] == "re-emit"
    assert emitted["attempt"] == 1


def test_re_emit_cli_success_json(tmp_path, capsys):
    _repo, _sess, session_dir = _stale_session(tmp_path, capsys)
    rc, out = _re_emit(session_dir, capsys)
    assert rc == 0
    assert out["ok"] is True
    assert out["superseded"]["attempt"] == 0


def test_re_emit_blocking_keeps_distinct_tuple_identity(tmp_path):
    """A recorded (seat, occurrence) must not mask a different slot with the same label."""
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir)
    rnd, phase, attempt = 1, RD.P_PANEL, 0
    roster = ["finding", "finding", "finding#1"]
    journal = [{
        "outcome": "recorded",
        "round": rnd,
        "phase": phase,
        "attempt": attempt,
        "recordIdentity": {
            "seat": "finding",
            "phase": phase,
            "attempt": attempt,
            "occurrence": 1,
        },
    }]
    skey = RR.storage_key("finding#1", 0)
    landing = RR.landing_path(session_dir, rnd, phase, skey, attempt)
    os.makedirs(os.path.dirname(landing), exist_ok=True)
    with open(landing, "w", encoding="utf-8") as fh:
        fh.write("{}")
    names = RD._re_emit_blocking_result_names(
        session_dir, journal, rnd, phase, attempt, roster)
    assert names == ["landing:%s" % skey]


def test_re_emit_with_journal_recorded_before_relocate(tmp_path, capsys):
    repo = M._mobility_repo(tmp_path)
    sess = M._mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    state, pend, roster = _panel_roster(session_dir)
    seat, occurrence = _first_seat(roster)
    _land_panel_seat(session_dir, state, pend, seat, occurrence, sess["diff_path"])
    recorded = RD.cmd_record_result(session_dir, seat, occurrence=occurrence)
    assert recorded["ok"] is True, recorded
    M._relocate(session_dir, repo["root_b"], capsys)
    rc, out = _re_emit(session_dir, capsys)
    assert rc == 0
    assert out["ok"] is True
    assert out["superseded"]["attempt"] == 0
    ok, state = RD.load_state(session_dir)
    assert state["pending"]["attempt"] == 1
    superseded = next(r for r in M._journal_rows(session_dir)
                      if r.get("outcome") == "orders-superseded")
    assert superseded["supersededRecords"] == [seat if not occurrence else "%s#%d" % (seat, occurrence)]
    unclosed, refusal = RC._journal_open_seats(RD.read_journal(session_dir), session_dir)
    assert refusal is None
    assert not [k for k, _ in unclosed if k[2] == 0]
    manifest = json.load(open(RD._orders_manifest_path(session_dir, pend["round"], pend["phase"], 1),
                               encoding="utf-8"))
    attempt1_keys = [k for k, _ in unclosed
                     if k[2] == 1 and k[0] == pend["phase"] and k[1] == pend["round"]]
    assert len(attempt1_keys) == len(manifest.get("seats") or {})


@pytest.mark.parametrize("stop_at", ["staged", "sealed", "applied", "done"])
def test_re_emit_orders_emit_crash_matrix(tmp_path, capsys, monkeypatch, stop_at):
    _repo, _sess, session_dir = _stale_session(tmp_path, capsys)
    rnd, phase, old_attempt = 1, RD.P_PANEL, 0
    before = _snapshot_order_bytes(session_dir, rnd, phase)
    M._stop_at_kind(monkeypatch, "orders-emit", stop_at, n=0)
    with pytest.raises(RD.round_commit.StopPoint):
        RD.cmd_re_emit(session_dir, "tester")
    RD.round_commit.recover(session_dir)
    if stop_at == "staged":
        after = _snapshot_order_bytes(session_dir, rnd, phase)
        assert after == before
        rc, out = _re_emit(session_dir, capsys)
        assert rc == 0
        assert out["ok"] is True
    else:
        rc, out = _re_emit(session_dir, capsys)
        assert rc == 0
        assert out["ok"] is True
        assert out["superseded"]["attempt"] == old_attempt
        ok, state = RD.load_state(session_dir)
        assert state["pending"]["attempt"] == old_attempt + 1
    assert M._commits_empty(session_dir)


@pytest.mark.parametrize("reason,setup", [
    ("re-emit-session-unreadable", "unreadable"),
    ("re-emit-no-pending-order", "terminal"),
    ("re-emit-no-pending-order", "non_dispatch"),
    ("re-emit-no-anchor", "no_anchor"),
    ("re-emit-head-unresolved", "head_unresolved"),
    ("re-emit-head-moved", "head_moved"),
    ("re-emit-not-stale", "not_stale"),
    ("re-emit-attempt-has-results", "results_landing"),
    ("re-emit-attempt-has-results", "results_bare"),
    ("re-emit-attempt-has-results", "results_lstat_denied"),
    ("re-emit-locked", "locked"),
])
def test_re_emit_refusal_tokens(tmp_path, capsys, reason, setup, monkeypatch):
    repo = M._mobility_repo(tmp_path)
    sess = M._mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    state_path = os.path.join(session_dir, RD.STATE_FILE)
    if setup == "unreadable":
        os.remove(state_path)
    elif setup == "terminal":
        ok, state = RD.load_state(session_dir)
        state["terminal"] = "converged"
        RD.save_state(session_dir, state)
        M._relocate(session_dir, repo["root_b"], capsys)
    elif setup == "non_dispatch":
        ok, state = RD.load_state(session_dir)
        state["pending"] = {"action": RD.P_VERIFY, "round": 1, "phase": RD.P_VERIFY,
                            "attempt": 0, "payload": {}}
        RD.save_state(session_dir, state)
        M._relocate(session_dir, repo["root_b"], capsys)
    elif setup == "no_anchor":
        M._relocate(session_dir, repo["root_b"], capsys)
        ok, state = RD.load_state(session_dir)
        rnd, phase, attempt = state["pending"]["round"], state["pending"]["phase"], 0
        anchors = state.get("_ordersAnchors") or {}
        anchors.pop(RD._anchor_key(rnd, phase, attempt), None)
        state["_ordersAnchors"] = anchors
        RD.save_state(session_dir, state)
        manifest_path = RD._orders_manifest_path(session_dir, rnd, phase, attempt)
        os.rename(manifest_path, manifest_path + ".aside")
    elif setup == "head_unresolved":
        M._relocate(session_dir, repo["root_b"], capsys)
        subprocess.check_call(["git", "-C", repo["root_a"], "worktree", "remove", "--force",
                               repo["root_b"]])
    elif setup == "head_moved":
        M._relocate(session_dir, repo["root_b"], capsys)
        subprocess.check_call(
            ["git", "-C", repo["root_b"], "commit", "-q", "--allow-empty", "-m", "ahead"])
    elif setup == "not_stale":
        pass
    elif setup == "results_landing":
        M._relocate(session_dir, repo["root_b"], capsys)
        ok, state = RD.load_state(session_dir)
        pend = state["pending"]
        roster, _ = round_adapters.roster_for(pend["phase"], state, state.get("config") or {})
        seat, occurrence = _first_seat(roster)
        skey = RR.storage_key(seat, occurrence)
        landing = RR.landing_path(session_dir, pend["round"], pend["phase"], skey, 0)
        os.makedirs(os.path.dirname(landing), exist_ok=True)
        with open(landing, "w", encoding="utf-8") as fh:
            fh.write("{}")
    elif setup == "results_bare":
        M._relocate(session_dir, repo["root_b"], capsys)
        ok, state = RD.load_state(session_dir)
        pend = state["pending"]
        roster, _ = round_adapters.roster_for(pend["phase"], state, state.get("config") or {})
        seat, occurrence = _first_seat(roster)
        skey = RR.storage_key(seat, occurrence)
        bare = RR.bare_payload_path(session_dir, pend["round"], pend["phase"], skey, 0)
        os.makedirs(os.path.dirname(bare), exist_ok=True)
        with open(bare, "w", encoding="utf-8") as fh:
            fh.write("{}")
    elif setup == "results_lstat_denied":
        M._relocate(session_dir, repo["root_b"], capsys)
        ok, state = RD.load_state(session_dir)
        pend = state["pending"]
        roster, _ = round_adapters.roster_for(pend["phase"], state, state.get("config") or {})
        seat, occurrence = _first_seat(roster)
        denied_path = RR.landing_path(session_dir, pend["round"], pend["phase"],
                                      RR.storage_key(seat, occurrence), 0)
        real_present = record_paths.landing_entry_present

        def _present(path):
            if path == denied_path:
                return True
            return real_present(path)

        monkeypatch.setattr(record_paths, "landing_entry_present", _present)
    elif setup == "locked":
        M._relocate(session_dir, repo["root_b"], capsys)
        RR.atomic_write_json(RR.session_lock_path(session_dir),
                             {"pid": 424242, "createdAt": "2026-08-07T00:00:00"})
    else:
        pytest.fail("unknown setup %r" % setup)

    order_snap = _snapshot_order_bytes(session_dir, 1, RD.P_PANEL)
    state_before = M._read_bytes(state_path) if os.path.isfile(state_path) else b""
    rc, out = _re_emit(session_dir, capsys)
    assert rc == 1
    assert out["ok"] is False
    assert out["reason"] == reason
    assert _last_refused(session_dir, reason) is not None
    if os.path.isfile(state_path):
        assert M._read_bytes(state_path) == state_before
    for path, content in order_snap.items():
        assert M._read_bytes(path) == content


# --- certification close (C*) -------------------------------------------------------------

def test_certification_close_after_re_emit_no_attempt0_open(tmp_path, capsys):
    _repo, _sess, session_dir = _stale_session(tmp_path, capsys)
    rnd, phase = 1, RD.P_PANEL
    _re_emit(session_dir, capsys)
    unclosed, refusal = RC._journal_open_seats(RD.read_journal(session_dir), session_dir)
    assert refusal is None
    assert not [k for k, _ in unclosed if k[2] == 0]
    attempt1_keys = [k for k, _ in unclosed if k[2] == 1 and k[0] == phase and k[1] == rnd]
    manifest = json.load(open(RD._orders_manifest_path(session_dir, rnd, phase, 1), encoding="utf-8"))
    assert len(attempt1_keys) == len(manifest.get("seats") or {})


@pytest.mark.parametrize("landing_shape,landing_kind", [
    ("envelope", "file"),
    ("bare", "file"),
    ("bare", "dangling_symlink"),
])
def test_certification_late_attempt0_landing_keeps_seat_open(
        tmp_path, capsys, landing_shape, landing_kind):
    _repo, _sess, session_dir = _stale_session(tmp_path, capsys)
    rnd, phase, old_attempt = 1, RD.P_PANEL, 0
    _re_emit(session_dir, capsys)
    ok, state = RD.load_state(session_dir)
    roster, _ = RD._roster_of(session_dir, state, "re-emit", phase, rnd, old_attempt)
    seat, occurrence = _first_seat(roster)
    skey = RR.storage_key(seat, occurrence)
    landing = RR.landing_path(session_dir, rnd, phase, skey, old_attempt)
    bare = RR.bare_payload_path(session_dir, rnd, phase, skey, old_attempt)
    target = landing if landing_shape == "envelope" else bare
    if landing_kind == "dangling_symlink":
        _dangling_symlink(target)
    else:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            fh.write("{}")
    unclosed, refusal = RC._journal_open_seats(RD.read_journal(session_dir), session_dir)
    assert refusal is None
    late_keys = [k for k, _ in unclosed
                 if k[2] == old_attempt and k[0] == phase and k[1] == rnd and k[3] == seat]
    assert len(late_keys) == 1
    aside = target + ".aside"
    os.rename(target, aside)
    unclosed_after, refusal_after = RC._journal_open_seats(RD.read_journal(session_dir), session_dir)
    assert refusal_after is None
    assert not [k for k, _ in unclosed_after
                if k[2] == old_attempt and k[0] == phase and k[1] == rnd and k[3] == seat]


def test_certification_lstat_permission_error_keeps_superseded_seat_open(tmp_path, capsys, monkeypatch):
    _repo, _sess, session_dir = _stale_session(tmp_path, capsys)
    rnd, phase, old_attempt = 1, RD.P_PANEL, 0
    _re_emit(session_dir, capsys)
    ok, state = RD.load_state(session_dir)
    roster, _ = RD._roster_of(session_dir, state, "re-emit", phase, rnd, old_attempt)
    seat, occurrence = _first_seat(roster)
    denied_path = RR.landing_path(session_dir, rnd, phase, RR.storage_key(seat, occurrence), old_attempt)
    real_present = record_paths.landing_entry_present

    def _present(path):
        if path == denied_path:
            return True
        return real_present(path)

    monkeypatch.setattr(record_paths, "landing_entry_present", _present)
    unclosed, refusal = RC._journal_open_seats(RD.read_journal(session_dir), session_dir)
    assert refusal is None
    assert [k for k, _ in unclosed
            if k[2] == old_attempt and k[0] == phase and k[1] == rnd and k[3] == seat]


def test_certification_legacy_emitted_row_stays_open_without_session_dir():
    journal = [
        {"cmd": "advance", "outcome": "emitted", "phase": RD.P_PANEL, "round": 1, "attempt": 0,
         "roster": [{"seat": "code-reviewer"}]},
        {"cmd": "re-emit", "outcome": "orders-superseded", "phase": RD.P_PANEL, "round": 1,
         "attempt": 0, "newAttempt": 1},
    ]
    unclosed, refusal = RC._journal_open_seats(journal, session_dir=None)
    assert refusal is None
    assert ("dispatch-panel", 1, 0, "code-reviewer", 0) in [k for k, _ in unclosed]


# --- relocation fence (F*) ------------------------------------------------------------------

def test_relocation_fence_hand_record_refused_after_relocate(tmp_path, capsys):
    repo, sess, session_dir = _stale_session(tmp_path, capsys)
    state, pend, roster = _panel_roster(session_dir)
    seat, occurrence = _first_seat(roster)
    _land_panel_seat(session_dir, state, pend, seat, occurrence, sess["diff_path"])
    state_before = M._read_bytes(os.path.join(session_dir, RD.STATE_FILE))
    skey = RR.storage_key(seat, occurrence)
    store_path = RR.store_path(session_dir, pend["round"], pend["phase"], skey, pend["attempt"])
    out = RD.cmd_record_result(session_dir, seat, occurrence=occurrence)
    assert out["ok"] is False
    assert out["reason"] == RD.RECORD_ATTEMPT_PREDATES_RELOCATION_CAUSE
    assert out["detail"] == RD.RECORD_ATTEMPT_PREDATES_RELOCATION_DETAIL
    assert not os.path.exists(store_path)
    assert M._read_bytes(os.path.join(session_dir, RD.STATE_FILE)) == state_before


def test_landing_entry_present_lstat_outcomes(tmp_path, monkeypatch):
    existing = tmp_path / "exists.json"
    existing.write_text("{}")
    assert record_paths.landing_entry_present(str(existing)) is True

    dangling = tmp_path / "dangling" / "link.json"
    _dangling_symlink(str(dangling))
    assert record_paths.landing_entry_present(str(dangling)) is True

    missing = str(tmp_path / "no-such-path" / "file.json")
    assert record_paths.landing_entry_present(missing) is False

    regular_file = tmp_path / "not_a_dir"
    regular_file.write_text("x")
    under_file = str(regular_file / "child.json")
    assert record_paths.landing_entry_present(under_file) is False

    denied = tmp_path / "denied" / "target.json"
    denied.parent.mkdir()
    denied.write_text("{}")
    real_lstat = os.lstat

    def _lstat(path, *args, **kwargs):
        if path == str(denied):
            raise PermissionError("denied")
        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", _lstat)
    assert record_paths.landing_entry_present(str(denied)) is True


def test_relocation_fence_advance_folds_seats_recorded_before_relocate(tmp_path, capsys):
    repo = M._mobility_repo(tmp_path)
    sess = M._mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    state, pend, roster = _panel_roster(session_dir)
    for seat, occurrence in RR.roster_slots(roster):
        _land_panel_seat(session_dir, state, pend, seat, occurrence, sess["diff_path"])
        recorded = RD.cmd_record_result(session_dir, seat, occurrence=occurrence)
        assert recorded["ok"] is True, recorded
    M._relocate(session_dir, repo["root_b"], capsys)
    out = RD.cmd_advance(session_dir)
    assert out.get("reason") != RD.RECORD_ATTEMPT_PREDATES_RELOCATION_CAUSE
    assert not any(
        r.get("reason") == RD.RECORD_ATTEMPT_PREDATES_RELOCATION_CAUSE
        or r.get("outcome") == RD.RECORD_ATTEMPT_PREDATES_RELOCATION_CAUSE
        for r in M._journal_rows(session_dir)
    )


def test_relocation_fence_record_succeeds_for_new_attempt_after_re_emit(tmp_path, capsys):
    repo, sess, session_dir = _stale_session(tmp_path, capsys)
    _re_emit(session_dir, capsys)
    state, pend, roster = _panel_roster(session_dir)
    assert pend["attempt"] == 1
    seat, occurrence = _first_seat(roster)
    _land_panel_seat(session_dir, state, pend, seat, occurrence, sess["diff_path"])
    out = RD.cmd_record_result(session_dir, seat, occurrence=occurrence)
    assert out["ok"] is True, out


def test_relocation_fence_sweep_refuses_unclaimed_attempt0_landing(tmp_path, capsys):
    repo, sess, session_dir = _stale_session(tmp_path, capsys)
    state, pend, roster = _panel_roster(session_dir)
    seat, occurrence = _first_seat(roster)
    _land_panel_seat(session_dir, state, pend, seat, occurrence, sess["diff_path"])
    out = RD.cmd_record_result(session_dir, sweep=True)
    assert out["ok"] is False
    assert out["reason"] == RD.RECORD_ATTEMPT_PREDATES_RELOCATION_CAUSE
    assert out.get("seat") == seat


def test_relocation_fence_advance_refuses_unclaimed_attempt0_landing(tmp_path, capsys):
    repo, sess, session_dir = _stale_session(tmp_path, capsys)
    state, pend, roster = _panel_roster(session_dir)
    seat, occurrence = _first_seat(roster)
    _land_panel_seat(session_dir, state, pend, seat, occurrence, sess["diff_path"])
    out = RD.cmd_advance(session_dir)
    assert out["ok"] is False
    assert out["reason"] == RD.RECORD_ATTEMPT_PREDATES_RELOCATION_CAUSE


def test_relocation_fence_not_fired_when_nothing_new_to_ingest(tmp_path, capsys):
    repo = M._mobility_repo(tmp_path)
    sess = M._mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    state, pend, roster = _panel_roster(session_dir)
    seat, occurrence = _first_seat(roster)
    _land_panel_seat(session_dir, state, pend, seat, occurrence, sess["diff_path"])
    recorded = RD.cmd_record_result(session_dir, seat, occurrence=occurrence)
    assert recorded["ok"] is True, recorded
    M._relocate(session_dir, repo["root_b"], capsys)
    out = RD.cmd_record_result(session_dir, sweep=True)
    assert out.get("reason") != RD.RECORD_ATTEMPT_PREDATES_RELOCATION_CAUSE


def test_relocation_fence_hand_submit_refused_after_relocate(tmp_path, capsys):
    _repo, _sess, session_dir = _stale_session(tmp_path, capsys)
    state_before = M._read_bytes(os.path.join(session_dir, RD.STATE_FILE))
    ok, state = RD.load_state(session_dir)
    pend = state["pending"]
    out = RD.cmd_submit(session_dir, pend["phase"], pend["attempt"],
                        RD.state_hash(state), _panel_hand_artifact(session_dir))
    assert out["ok"] is False
    assert out["reason"] == RD.RECORD_ATTEMPT_PREDATES_RELOCATION_CAUSE
    assert any(r.get("outcome") == RD.RECORD_ATTEMPT_PREDATES_RELOCATION_CAUSE
               for r in M._journal_rows(session_dir))
    assert M._read_bytes(os.path.join(session_dir, RD.STATE_FILE)) == state_before


def test_relocation_fence_absent_without_relocate(tmp_path, capsys):
    repo = M._mobility_repo(tmp_path)
    sess = M._mobility_session(tmp_path, repo)
    session_dir = sess["session_dir"]
    state, pend, roster = _panel_roster(session_dir)
    seat, occurrence = _first_seat(roster)
    _land_panel_seat(session_dir, state, pend, seat, occurrence, sess["diff_path"])
    out = RD.cmd_record_result(session_dir, seat, occurrence=occurrence)
    assert out["ok"] is True, out


def test_relocation_after_emission_predicate(tmp_path):
    root_a = str(tmp_path / "a")
    root_b = str(tmp_path / "b")
    os.makedirs(root_a)
    os.makedirs(root_b)
    rnd, phase, attempt = 1, RD.P_PANEL, 0
    moved = {"outcome": "relocated", "oldRoot": root_a, "newRoot": root_b}
    equal = {"outcome": "relocated", "oldRoot": root_a, "newRoot": root_a}
    bad = {"outcome": "relocated", "oldRoot": 1, "newRoot": root_b}
    emit0 = {"outcome": "orders-emitted", "round": rnd, "phase": phase, "attempt": 0}
    emit1 = {"outcome": "orders-emitted", "round": rnd, "phase": phase, "attempt": 1}
    assert RD._relocation_after_emission([moved], rnd, phase, attempt) == moved
    assert RD._relocation_after_emission([bad], rnd, phase, attempt) is None
    assert RD._relocation_after_emission([equal], rnd, phase, attempt) is None
    between = [emit0, moved, emit1]
    assert RD._relocation_after_emission(between, rnd, phase, 1) is None
    after = [emit0, moved]
    assert RD._relocation_after_emission(after, rnd, phase, attempt) == moved


def test_runner_view_record_not_fenced_after_relocate(tmp_path, capsys):
    repo, sess, session_dir = _stale_session(tmp_path, capsys)
    state, pend, roster = _panel_roster(session_dir)
    seat, occurrence = _first_seat(roster)
    anchor_head = RD._anchor_cited_head(state, session_dir, pend["round"], pend["phase"],
                                        pend["attempt"])
    order_path = RR.order_prompt_path(
        session_dir, pend["round"], pend["phase"], RR.storage_key(seat, occurrence), pend["attempt"])
    run_dir = _TDI._execution_run_dir(tmp_path, order_path, [], view_head_sha=anchor_head)
    payload = _TDI._payload_for(session_dir, state, pend, seat, [], sess["diff_path"])
    _TDI._dispatch_observed_land(session_dir, state, pend, seat, payload, occurrence=occurrence)
    out = RD.cmd_record_result(session_dir, seat, occurrence=occurrence, evidence_run_dir=run_dir)
    assert out["ok"] is True, out
    stored, err = RR.read_json(out["storePath"])
    assert err is None
    assert stored["citedHeadSource"] == RR.CITED_HEAD_SOURCE_RUNNER_VIEW
