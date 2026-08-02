"""Tests for pilot_browser — pin integrity, socket dirs, topology, broker admission."""
import os
import shutil
import stat
import sys
import tempfile
import textwrap

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_browser as pb  # noqa: E402
import pilot_journal as pj  # noqa: E402
import pilot_lifecycle as pl  # noqa: E402
import pilot_slot  # noqa: E402

NOW = "2026-01-01T00:00:00Z"
LATER = "2026-01-01T00:00:01Z"
SLOT = "slot1"
SLOT_REF = "slot1@1"
ACCOUNTS = [{"account": "owner", "role": "resource-owner"}]
VALID_DIGEST = "a" * 64
VALID_PIN = {
    "schemaVersion": 1,
    "version": "1.40.0",
    "integrityDigest": VALID_DIGEST,
}

SHORT_BASE = "/tmp"


def _tmp_dir():
    return tempfile.mkdtemp()


def _observer_script(body):
    tmp = _tmp_dir()
    path = os.path.join(tmp, "observer.py")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(textwrap.dedent(body))
    return tmp, path


def _valid_observer(stdout_line):
    tmp, path = _observer_script(
        "import sys\nsys.stdout.write('%s')\n" % stdout_line.replace("'", "\\'")
    )
    return {"command": [sys.executable, path]}, tmp


def _server_record(**overrides):
    rec = {
        "schemaVersion": 1,
        "slotRef": SLOT_REF,
        "generation": 1,
        "socketDir": os.path.join(_tmp_dir(), "sock"),
        "serverPid": 100,
        "browserPid": 101,
        "pin": dict(VALID_PIN),
        "createdAt": NOW,
    }
    rec.update(overrides)
    return rec


def test_validate_pin_accepts_valid():
    assert pb.validate_pin(dict(VALID_PIN)) == VALID_PIN


def test_validate_pin_refuses_extra_key():
    bad = dict(VALID_PIN)
    bad["extra"] = "x"
    with pytest.raises(pb.PilotBrowserError, match=pb.REFUSAL_PIN_INVALID):
        pb.validate_pin(bad)


def test_verify_pin_success():
    observer, cwd = _valid_observer("1.40.0 %s" % VALID_DIGEST)
    try:
        result = pb.verify_pin(VALID_PIN, observer, run_cwd=cwd)
        assert result == {
            "ok": True,
            "reason": None,
            "version": "1.40.0",
            "integrityDigest": VALID_DIGEST,
        }
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


def test_verify_pin_observer_fails_on_nonzero_exit():
    # bite-axis: observer execution — non-zero exit refuses browser-pin-observer-failed.
    tmp, path = _observer_script("import sys; sys.exit(1)")
    observer = {"command": [sys.executable, path]}
    result = pb.verify_pin(VALID_PIN, observer, run_cwd=tmp)
    assert result["ok"] is False
    assert result["reason"] == pb.REFUSAL_PIN_OBSERVER_FAILED
    shutil.rmtree(tmp, ignore_errors=True)


def test_verify_pin_observer_fails_on_garbage_output():
    # bite-axis: observer execution — malformed stdout refuses browser-pin-observer-failed.
    observer, cwd = _valid_observer("only-one-field")
    try:
        result = pb.verify_pin(VALID_PIN, observer, run_cwd=cwd)
        assert result["reason"] == pb.REFUSAL_PIN_OBSERVER_FAILED
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


def test_verify_pin_version_mismatch():
    # bite-axis: pin version — mismatch refuses browser-pin-version-mismatch.
    observer, cwd = _valid_observer("9.9.9 %s" % VALID_DIGEST)
    try:
        result = pb.verify_pin(VALID_PIN, observer, run_cwd=cwd)
        assert result["reason"] == pb.REFUSAL_PIN_VERSION_MISMATCH
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


def test_verify_pin_integrity_mismatch():
    # bite-axis: pin digest — mismatch refuses browser-pin-integrity-mismatch.
    other = "b" * 64
    observer, cwd = _valid_observer("1.40.0 %s" % other)
    try:
        result = pb.verify_pin(VALID_PIN, observer, run_cwd=cwd)
        assert result["reason"] == pb.REFUSAL_PIN_INTEGRITY_MISMATCH
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


def test_socket_dir_plan_refuses_path_too_long():
    # bite-axis: socket path cap — measured path over SUN_PATH_MAX refuses before create.
    base = os.path.realpath(tempfile.gettempdir())
    long_base = os.path.join(base, "x" * 200)
    os.makedirs(long_base, exist_ok=True)
    try:
        result = pb.socket_dir_plan(SLOT_REF, base=long_base, launch_token="tok")
        assert result["ok"] is False
        assert result["reason"] == pb.REFUSAL_SOCKET_PATH_TOO_LONG
    finally:
        shutil.rmtree(long_base, ignore_errors=True)


def test_socket_dir_plan_unrecognized_platform_uses_smallest_cap():
    # bite-axis: platform cap — unknown platform uses smallest cap fail-closed.
    result = pb.socket_dir_plan(SLOT_REF, base=SHORT_BASE, platform="freebsd")
    assert result["ok"] is True
    assert result["cap"] == min(pb.SUN_PATH_MAX.values())
    assert result["platform"] == "freebsd"


def test_socket_dir_plan_refuses_base_in_worktree():
    # bite-axis: socket base — base inside worktree refuses browser-socket-base-in-worktree.
    wt = _tmp_dir()
    base = os.path.join(wt, "tmp")
    os.makedirs(base)
    try:
        result = pb.socket_dir_plan(SLOT_REF, base=base, worktree_root=wt)
        assert result["reason"] == pb.REFUSAL_SOCKET_BASE_IN_WORKTREE
    finally:
        shutil.rmtree(wt, ignore_errors=True)


def test_create_socket_dir_refuses_existing():
    # bite-axis: socket dir create — existing path refuses browser-socket-dir-exists.
    plan = pb.socket_dir_plan(SLOT_REF, base=SHORT_BASE, launch_token="exist1")
    assert plan["ok"] is True
    path = plan["path"]
    os.makedirs(path)
    try:
        result = pb.create_socket_dir(plan)
        assert result["reason"] == pb.REFUSAL_SOCKET_DIR_EXISTS
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_create_socket_dir_refuses_symlink():
    # bite-axis: socket dir create — symlink refuses browser-socket-dir-unsafe.
    parent = _tmp_dir()
    target = os.path.join(parent, "target")
    link = os.path.join(parent, "link")
    os.makedirs(target)
    os.symlink(target, link)
    plan = {"ok": True, "path": link}
    try:
        result = pb.create_socket_dir(plan)
        assert result["reason"] == pb.REFUSAL_SOCKET_DIR_UNSAFE
    finally:
        shutil.rmtree(parent, ignore_errors=True)


def test_assert_browser_is_server_child_refuses_wrong_parent():
    # bite-axis: browser parentage — browser not child of server refuses browser-not-server-child.
    result = pb.assert_browser_is_server_child(100, 101, ppid_of=lambda _pid: 99)
    assert result["reason"] == pb.REFUSAL_NOT_SERVER_CHILD


def test_assert_browser_is_server_child_refuses_unreadable_ppid():
    # bite-axis: browser parentage — unreadable ppid refuses browser-pid-unreadable.
    result = pb.assert_browser_is_server_child(100, 101, ppid_of=lambda _pid: None)
    assert result["reason"] == pb.REFUSAL_PID_UNREADABLE


def test_teardown_server_refuses_without_observed_exit():
    # bite-axis: teardown exit — unobserved exit refuses browser-terminal-state-unobserved.
    tmp = _tmp_dir()
    journal = os.path.join(tmp, "journal.jsonl")
    sock = os.path.join(tmp, "sockdir")
    os.makedirs(sock)
    record = _server_record(socketDir=sock)
    try:
        result = pb.teardown_server(
            journal,
            server_record=record,
            torn_down_at=LATER,
            begin_at=NOW,
            observe_exit=lambda _pid: {"exited": False, "status": None},
        )
        assert result["reason"] == pb.REFUSAL_TERMINAL_STATE_UNOBSERVED
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_teardown_server_never_accepts_socket_absence_as_exit():
    # bite-axis: teardown exit — socket absence is not exit evidence.
    tmp = _tmp_dir()
    journal = os.path.join(tmp, "journal.jsonl")
    missing_sock = os.path.join(tmp, "already-gone")
    record = _server_record(socketDir=missing_sock)
    try:
        result = pb.teardown_server(
            journal,
            server_record=record,
            torn_down_at=LATER,
            begin_at=NOW,
            observe_exit=lambda _pid: {"exited": False, "status": None},
        )
        assert result["reason"] == pb.REFUSAL_TERMINAL_STATE_UNOBSERVED
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_plan_topology_refuses_shared_context():
    # bite-axis: topology — duplicate context key refuses browser-shared-context-refused.
    accounts = [
        {"account": "a", "role": "r"},
        {"account": "a", "role": "r2"},
    ]
    result = pb.plan_topology(SLOT_REF, accounts)
    assert result["reason"] == pb.REFUSAL_SHARED_CONTEXT_REFUSED


def test_plan_topology_refuses_empty_accounts():
    result = pb.plan_topology(SLOT_REF, [])
    assert result["reason"] == pilot_slot.REFUSAL_ACCOUNT_SET_EMPTY


def test_admit_server_registry_refuses_server_shared_across_slots():
    # bite-axis: registry — same server pid on two slots refuses.
    r1 = _server_record(slotRef="slot1@1", serverPid=200, browserPid=201)
    r2 = _server_record(slotRef="slot2@1", serverPid=200, browserPid=202)
    result = pb.admit_server_registry([r1, r2])
    assert result["reason"] == pb.REFUSAL_SERVER_SHARED_ACROSS_SLOTS


def test_admit_server_registry_refuses_browser_shared_across_slots():
    # bite-axis: registry — same browser pid on two slots refuses.
    r1 = _server_record(slotRef="slot1@1", serverPid=200, browserPid=201)
    r2 = _server_record(slotRef="slot2@1", serverPid=202, browserPid=201)
    result = pb.admit_server_registry([r1, r2])
    assert result["reason"] == pb.REFUSAL_SHARED_ACROSS_SLOTS


def test_admit_server_registry_refuses_multiple_servers_per_slot():
    # bite-axis: registry — two live servers for one slot refuses.
    r1 = _server_record(slotRef="slot1@1", generation=1, serverPid=200, browserPid=201)
    r2 = _server_record(slotRef="slot1@2", generation=2, serverPid=203, browserPid=204)
    result = pb.admit_server_registry([r1, r2])
    assert result["reason"] == pb.REFUSAL_MULTIPLE_SERVERS_FOR_SLOT


def test_admit_refuses_stale_generation():
    # bite-axis: fencing — stale generation propagates slot-generation-stale.
    record = _server_record(generation=2, slotRef="slot1@2")
    result = pb.admit("slot1@1", record)
    assert result["reason"] == pl.REASON_GENERATION_STALE


def test_admit_refuses_generation_ahead():
    # bite-axis: fencing — ahead generation propagates slot-generation-ahead.
    record = _server_record(generation=1)
    result = pb.admit("slot1@2", record)
    assert result["reason"] == pl.REASON_GENERATION_AHEAD


def test_admit_refuses_slot_mismatch():
    # bite-axis: fencing — operation slot id mismatch refuses browser-operation-slot-mismatch.
    record = _server_record(slotRef="slot1@1")
    result = pb.admit("slot2@1", record)
    assert result["reason"] == pb.REFUSAL_OPERATION_SLOT_MISMATCH


def test_admit_accepts_matching_generation():
    record = _server_record()
    result = pb.admit(SLOT_REF, record)
    assert result == {"ok": True, "reason": None, "slotRef": SLOT_REF}


def test_create_socket_dir_success():
    plan = pb.socket_dir_plan(SLOT_REF, base=SHORT_BASE, launch_token="succ1")
    path = plan["path"]
    try:
        result = pb.create_socket_dir(plan)
        assert result["ok"] is True
        st = os.stat(path, follow_symlinks=False)
        assert stat.S_ISDIR(st.st_mode)
        assert st.st_mode & 0o777 == 0o700
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_provision_server_journals_and_returns_record():
    tmp = _tmp_dir()
    journal = os.path.join(tmp, "journal.jsonl")
    sock = os.path.join(tmp, "sock")
    os.makedirs(sock)
    try:
        result = pb.provision_server(
            journal,
            slot_ref=SLOT_REF,
            generation=1,
            socket_dir=sock,
            server_pid=100,
            browser_pid=101,
            pin=VALID_PIN,
            created_at=NOW,
            begin_at=NOW,
            ppid_of=lambda _pid: 100,
        )
        assert result["ok"] is True
        assert result["record"]["slotRef"] == SLOT_REF
        replayed = pj.replay(journal)
        assert replayed["ok"] is True
        kinds = [e["kind"] for e in replayed["effects"]]
        assert pj.KIND_BROWSER_SERVER_PROVISIONED in kinds
        end_times = [e["endedAt"] for e in replayed["effects"] if e["kind"] == pj.KIND_BROWSER_SERVER_PROVISIONED]
        assert end_times[0] != NOW
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_teardown_server_success():
    tmp = _tmp_dir()
    journal = os.path.join(tmp, "journal.jsonl")
    sock = os.path.join(tmp, "sockdir")
    os.makedirs(sock)
    record = _server_record(socketDir=sock)
    try:
        result = pb.teardown_server(
            journal,
            server_record=record,
            torn_down_at=LATER,
            begin_at=NOW,
            observe_exit=lambda _pid: {"exited": True, "status": 0},
        )
        assert result["ok"] is True
        assert result["receipt"]["socketDirRemoved"] is True
        assert not os.path.exists(sock)
        replayed = pj.replay(journal)
        kinds = [e["kind"] for e in replayed["effects"]]
        assert pj.KIND_BROWSER_SERVER_TORN_DOWN in kinds
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_plan_topology_success():
    accounts = [
        {"account": "a", "role": "r1"},
        {"account": "b", "role": "r2"},
    ]
    result = pb.plan_topology(SLOT_REF, accounts)
    assert result["ok"] is True
    assert result["server"]["count"] == 1
    assert result["browser"]["count"] == 1
    assert len(result["contexts"]) == 2


def test_admit_server_registry_accepts_valid():
    r1 = _server_record(slotRef="slot1@1", serverPid=200, browserPid=201)
    r2 = _server_record(slotRef="slot2@1", serverPid=203, browserPid=204)
    result = pb.admit_server_registry([r1, r2])
    assert result["ok"] is True
    assert result["accepted"] == 2
