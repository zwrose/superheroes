"""Tests for pilot_browser — pin integrity, socket dirs, topology, broker admission."""
import os
import shutil
import socket
import stat
import sys
import tempfile
import textwrap
from datetime import datetime

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

SHORT_BASE = None  # set per-test via _socket_base_outside_worktree()


def _socket_base_outside_worktree():
    import store_core

    wt = store_core.repo_root(os.getcwd())
    parent = os.path.dirname(wt)
    base = os.path.join(parent, "pb-base")
    os.makedirs(base, exist_ok=True)
    return base


def _user_owned_observer_command(script_path):
    wrapper = os.path.join(os.path.dirname(script_path), "run-observer.sh")
    with open(wrapper, "w", encoding="utf-8") as fh:
        fh.write("#!/bin/sh\nexec '%s' \"$1\"\n" % sys.executable.replace("'", "'\\''"))
    os.chmod(wrapper, 0o700)
    return [wrapper, script_path]


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
    return {"command": _user_owned_observer_command(path)}, tmp


def _server_record(**overrides):
    parent = _tmp_dir()
    sock = os.path.join(parent, "pb-sock")
    os.makedirs(sock, exist_ok=True)
    rec = {
        "schemaVersion": 1,
        "slotRef": SLOT_REF,
        "generation": 1,
        "socketDir": sock,
        "serverPid": 100,
        "browserPid": 101,
        "pin": dict(VALID_PIN),
        "createdAt": NOW,
    }
    rec.update(overrides)
    return rec


def _lifecycle_record_at_generation(generation):
    rec = pl.new_record(SLOT, ACCOUNTS, now=NOW)
    while rec["generation"] < generation:
        rec = pl.transition(rec, pl.STATE_PROVISIONED, now=NOW)
        rec = pl.transition(rec, pl.STATE_OCCUPIED, now=NOW)
        rec = pl.transition(rec, pl.STATE_RELEASED, now=NOW)
        if rec["generation"] < generation:
            rec = pl.begin_generation(rec, now=NOW)
    return rec


def _write_slots_record(generation):
    slots_dir = os.path.join(_tmp_dir(), "pilot-slots")
    rec = _lifecycle_record_at_generation(generation)
    path = pl.record_path(slots_dir, SLOT)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    assert pl.write_record(path, rec)["ok"]
    return slots_dir


def _both_exited_observer(server_pid=100, browser_pid=101, server_status=0, browser_status=0):
    def observe(pid):
        if pid == server_pid:
            return {"exited": True, "status": server_status}
        if pid == browser_pid:
            return {"exited": True, "status": browser_status}
        return {"exited": False, "status": None}
    return observe


def _parse_ts(value):
    return datetime.fromisoformat(value[:-1] + "+00:00")


def test_later_timestamp_second_rollover():
    # bite-axis: timestamp carry — microsecond overflow increments second without ValueError.
    begin = "2026-01-01T00:00:00.999999Z"
    later = pb._later_timestamp(begin)
    assert _parse_ts(later) > _parse_ts(begin)
    assert later == "2026-01-01T00:00:01.000000Z"


def test_later_timestamp_minute_rollover():
    # bite-axis: timestamp carry — second overflow increments minute.
    begin = "2026-01-01T00:00:59.999999Z"
    later = pb._later_timestamp(begin)
    assert _parse_ts(later) > _parse_ts(begin)
    assert later == "2026-01-01T00:01:00.000000Z"


def test_later_timestamp_hour_rollover():
    # bite-axis: timestamp carry — minute overflow increments hour.
    begin = "2026-01-01T00:59:59.999999Z"
    later = pb._later_timestamp(begin)
    assert _parse_ts(later) > _parse_ts(begin)
    assert later == "2026-01-01T01:00:00.000000Z"


def test_later_timestamp_day_rollover():
    # bite-axis: timestamp carry — hour overflow increments day.
    begin = "2026-01-01T23:59:59.999999Z"
    later = pb._later_timestamp(begin)
    assert _parse_ts(later) > _parse_ts(begin)
    assert later == "2026-01-02T00:00:00.000000Z"


def test_later_timestamp_unparseable_passthrough():
    bad = "not-a-timestamp"
    assert pb._later_timestamp(bad) == bad


def test_remove_socket_dir_with_plain_file():
    # bite-axis: socket dir removal — non-empty directory with a file is removed.
    parent = _tmp_dir()
    sock_dir = os.path.join(parent, "pb-abc")
    os.makedirs(sock_dir)
    with open(os.path.join(sock_dir, "ws.sock"), "w", encoding="utf-8") as fh:
        fh.write("")
    try:
        result = pb.remove_socket_dir(sock_dir)
        assert result == {"ok": True, "reason": None}
        assert not os.path.exists(sock_dir)
    finally:
        shutil.rmtree(parent, ignore_errors=True)


def test_remove_socket_dir_with_unix_socket():
    # bite-axis: socket dir removal — directory containing a bound AF_UNIX socket is removed.
    if not hasattr(socket, "AF_UNIX"):
        pytest.skip("AF_UNIX not available")
    parent = _tmp_dir()
    sock_dir = os.path.join(parent, "pb-sock")
    os.makedirs(sock_dir)
    sock_path = os.path.join(sock_dir, "ws.sock")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.bind(sock_path)
    except OSError:
        sock.close()
        pytest.skip("cannot bind AF_UNIX socket on this platform")
    try:
        result = pb.remove_socket_dir(sock_dir)
        assert result == {"ok": True, "reason": None}
        assert not os.path.exists(sock_dir)
    finally:
        sock.close()
        shutil.rmtree(parent, ignore_errors=True)


def test_remove_socket_dir_unlinks_symlink_without_following():
    # bite-axis: socket dir removal — symlink entry is unlinked, never followed.
    parent = _tmp_dir()
    outside = os.path.join(parent, "outside")
    os.makedirs(outside)
    outside_file = os.path.join(outside, "keep.txt")
    with open(outside_file, "w", encoding="utf-8") as fh:
        fh.write("keep")
    sock_dir = os.path.join(parent, "pb-link")
    os.makedirs(sock_dir)
    os.symlink(outside_file, os.path.join(sock_dir, "escape"))
    try:
        result = pb.remove_socket_dir(sock_dir)
        assert result == {"ok": True, "reason": None}
        assert not os.path.exists(sock_dir)
        assert os.path.isfile(outside_file)
        with open(outside_file, encoding="utf-8") as fh:
            assert fh.read() == "keep"
    finally:
        shutil.rmtree(parent, ignore_errors=True)


def test_teardown_server_journals_not_applied_on_socket_dir_removal_failure():
    # bite-axis: teardown journal — removal failure with no mutation records not-applied.
    tmp = _tmp_dir()
    journal = os.path.join(tmp, "journal.jsonl")
    not_a_dir = os.path.join(tmp, "notadir")
    with open(not_a_dir, "w", encoding="utf-8") as fh:
        fh.write("file")
    record = _server_record(socketDir=not_a_dir)
    try:
        result = pb.teardown_server(
            journal,
            server_record=record,
            torn_down_at=LATER,
            begin_at=NOW,
            observe_exit=_both_exited_observer(),
        )
        assert result["ok"] is False
        assert result["reason"] == pb.REFUSAL_SOCKET_DIR_NOT_DIRECTORY
        replayed = pj.replay(journal)
        assert replayed["ok"] is True
        torn = [e for e in replayed["effects"] if e["kind"] == pj.KIND_BROWSER_SERVER_TORN_DOWN]
        assert len(torn) == 1
        assert torn[0]["state"] == pj.STATE_NOT_APPLIED
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_teardown_server_journals_indeterminate_on_partial_socket_dir_removal():
    # bite-axis: partial socket-dir cleanup — journal replays as possibly-applied.
    tmp = _tmp_dir()
    journal = os.path.join(tmp, "journal.jsonl")
    sock_dir = os.path.join(tmp, "pb-partial")
    os.makedirs(sock_dir)
    with open(os.path.join(sock_dir, "first.txt"), "w", encoding="utf-8") as fh:
        fh.write("a")
    nested = os.path.join(sock_dir, "nested")
    os.makedirs(nested)
    with open(os.path.join(nested, "inner.txt"), "w", encoding="utf-8") as fh:
        fh.write("b")
    record = _server_record(socketDir=sock_dir)
    try:
        result = pb.teardown_server(
            journal,
            server_record=record,
            torn_down_at=LATER,
            begin_at=NOW,
            observe_exit=_both_exited_observer(),
        )
        assert result["ok"] is False
        assert result["reason"] == pb.REFUSAL_SOCKET_DIR_UNREMOVABLE
        replayed = pj.replay(journal)
        torn = [e for e in replayed["effects"] if e["kind"] == pj.KIND_BROWSER_SERVER_TORN_DOWN]
        assert len(torn) == 1
        assert torn[0]["state"] == pj.STATE_POSSIBLY_APPLIED
        assert not os.path.exists(os.path.join(sock_dir, "first.txt"))
        assert os.path.isdir(nested)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_remove_socket_dir_refuses_unrecognized_prefix():
    # bite-axis: socket dir removal — unrecognized basename refuses before deleting entries.
    parent = _tmp_dir()
    bad_dir = os.path.join(parent, "sock")
    os.makedirs(bad_dir)
    keeper = os.path.join(bad_dir, "keep.txt")
    with open(keeper, "w", encoding="utf-8") as fh:
        fh.write("keep")
    try:
        result = pb.remove_socket_dir(bad_dir)
        assert result["reason"] == pb.REFUSAL_SOCKET_DIR_UNRECOGNIZED
        assert os.path.isfile(keeper)
    finally:
        shutil.rmtree(parent, ignore_errors=True)


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


def test_verify_pin_observer_fails_on_missing_binary():
    # bite-axis: observer safety — missing executable refuses browser-pin-observer-unsafe.
    tmp = os.path.realpath(tempfile.gettempdir())
    observer = {"command": ["/nonexistent/definitely-not-here"]}
    with pytest.raises(pb.PilotBrowserError, match=pb.REFUSAL_PIN_OBSERVER_UNSAFE):
        pb.verify_pin(VALID_PIN, observer, run_cwd=tmp)


def test_verify_pin_observer_fails_on_nonexistent_run_cwd():
    # bite-axis: observer safety — missing run cwd refuses browser-pin-observer-unsafe.
    observer, _cwd = _valid_observer("1.40.0 %s" % VALID_DIGEST)
    with pytest.raises(pb.PilotBrowserError, match=pb.REFUSAL_PIN_OBSERVER_UNSAFE):
        pb.verify_pin(
            VALID_PIN,
            observer,
            run_cwd=os.path.join(os.path.realpath(tempfile.gettempdir()), "no-such-cwd"),
        )


def test_verify_pin_observer_fails_on_relative_executable():
    # bite-axis: observer safety — relative executable refuses browser-pin-observer-unsafe.
    observer, cwd = _valid_observer("1.40.0 %s" % VALID_DIGEST)
    try:
        relative = {"command": ["python", observer["command"][1]]}
        with pytest.raises(pb.PilotBrowserError, match=pb.REFUSAL_PIN_OBSERVER_UNSAFE):
            pb.verify_pin(VALID_PIN, relative, run_cwd=cwd)
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


def test_verify_pin_observer_fails_on_group_writable_executable():
    # bite-axis: observer safety — group-writable executable refuses browser-pin-observer-unsafe.
    observer, cwd = _valid_observer("1.40.0 %s" % VALID_DIGEST)
    try:
        os.chmod(observer["command"][0], stat.S_IRWXU | stat.S_IWGRP | stat.S_IRGRP)
        with pytest.raises(pb.PilotBrowserError, match=pb.REFUSAL_PIN_OBSERVER_UNSAFE):
            pb.verify_pin(VALID_PIN, observer, run_cwd=cwd)
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


def test_verify_pin_observer_fails_on_world_writable_executable():
    # bite-axis: observer safety — world-writable executable refuses browser-pin-observer-unsafe.
    observer, cwd = _valid_observer("1.40.0 %s" % VALID_DIGEST)
    try:
        os.chmod(observer["command"][0], stat.S_IRWXU | stat.S_IWOTH | stat.S_IROTH)
        with pytest.raises(pb.PilotBrowserError, match=pb.REFUSAL_PIN_OBSERVER_UNSAFE):
            pb.verify_pin(VALID_PIN, observer, run_cwd=cwd)
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


def test_verify_pin_observer_fails_on_nonzero_exit():
    # bite-axis: observer execution — non-zero exit refuses browser-pin-observer-failed.
    tmp, path = _observer_script("import sys; sys.exit(1)")
    observer = {"command": _user_owned_observer_command(path)}
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
    base = _socket_base_outside_worktree()
    result = pb.socket_dir_plan(SLOT_REF, base=base, platform="freebsd")
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


def test_socket_dir_plan_refuses_base_in_worktree_without_explicit_root():
    # bite-axis: socket base — default worktree resolution refuses in-repo base.
    import store_core

    wt = store_core.repo_root(os.getcwd())
    base = os.path.join(wt, "tmp-socket-base")
    os.makedirs(base, exist_ok=True)
    try:
        result = pb.socket_dir_plan(SLOT_REF, base=base)
        assert result["reason"] == pb.REFUSAL_SOCKET_BASE_IN_WORKTREE
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_create_socket_dir_refuses_existing():
    # bite-axis: socket dir create — existing path refuses browser-socket-dir-exists.
    base = _socket_base_outside_worktree()
    plan = pb.socket_dir_plan(SLOT_REF, base=base, launch_token="exist1")
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


def test_admit_refuses_without_slots_dir():
    # bite-axis: fencing — missing slots directory refuses browser-fencing-slots-dir-required.
    record = _server_record()
    result = pb.admit(SLOT_REF, record)
    assert result["reason"] == pb.REFUSAL_FENCING_SLOTS_DIR_REQUIRED


def test_admit_refuses_stale_server_record_against_disk():
    # bite-axis: fencing — caller-supplied record stale vs on-disk generation refuses.
    slots_dir = _write_slots_record(2)
    record = _server_record(generation=1, slotRef="slot1@1")
    try:
        result = pb.admit("slot1@1", record, slots_dir=slots_dir)
        assert result["reason"] == pb.REFUSAL_SERVER_RECORD_STALE
    finally:
        shutil.rmtree(os.path.dirname(slots_dir), ignore_errors=True)


def test_admit_refuses_stale_generation():
    # bite-axis: fencing — stale generation propagates slot-generation-stale.
    slots_dir = _write_slots_record(2)
    record = _server_record(generation=2, slotRef="slot1@2")
    try:
        result = pb.admit("slot1@1", record, slots_dir=slots_dir)
        assert result["reason"] == pl.REASON_GENERATION_STALE
    finally:
        shutil.rmtree(os.path.dirname(slots_dir), ignore_errors=True)


def test_admit_refuses_generation_ahead():
    # bite-axis: fencing — ahead generation propagates slot-generation-ahead.
    slots_dir = _write_slots_record(1)
    record = _server_record(generation=1)
    try:
        result = pb.admit("slot1@2", record, slots_dir=slots_dir)
        assert result["reason"] == pl.REASON_GENERATION_AHEAD
    finally:
        shutil.rmtree(os.path.dirname(slots_dir), ignore_errors=True)


def test_admit_refuses_slot_mismatch():
    # bite-axis: fencing — operation slot id mismatch refuses browser-operation-slot-mismatch.
    slots_dir = _write_slots_record(1)
    record = _server_record(slotRef="slot1@1")
    try:
        result = pb.admit("slot2@1", record, slots_dir=slots_dir)
        assert result["reason"] == pb.REFUSAL_OPERATION_SLOT_MISMATCH
    finally:
        shutil.rmtree(os.path.dirname(slots_dir), ignore_errors=True)


def test_admit_accepts_matching_generation():
    slots_dir = _write_slots_record(1)
    record = _server_record()
    try:
        result = pb.admit(SLOT_REF, record, slots_dir=slots_dir)
        assert result == {"ok": True, "reason": None, "slotRef": SLOT_REF}
    finally:
        shutil.rmtree(os.path.dirname(slots_dir), ignore_errors=True)


def test_create_socket_dir_success():
    base = _socket_base_outside_worktree()
    plan = pb.socket_dir_plan(SLOT_REF, base=base, launch_token="succ1")
    path = plan["path"]
    try:
        result = pb.create_socket_dir(plan)
        assert result["ok"] is True
        st = os.stat(path, follow_symlinks=False)
        assert stat.S_ISDIR(st.st_mode)
        assert st.st_mode & 0o777 == 0o700
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_begin_provision_server_replays_possibly_applied_without_close():
    # bite-axis: pre-spawn journal — begin without close replays as possibly-applied.
    tmp = _tmp_dir()
    journal = os.path.join(tmp, "journal.jsonl")
    try:
        result = pb.begin_provision_server(journal, slot_ref=SLOT_REF, at=NOW)
        assert result["ok"] is True
        replayed = pj.replay(journal)
        prov = [
            e for e in replayed["effects"]
            if e["kind"] == pj.KIND_BROWSER_SERVER_PROVISIONED
        ]
        assert len(prov) == 1
        assert prov[0]["state"] == pj.STATE_POSSIBLY_APPLIED
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_begin_then_provision_server_replays_applied():
    tmp = _tmp_dir()
    journal = os.path.join(tmp, "journal.jsonl")
    sock = os.path.join(tmp, "pb-sock")
    os.makedirs(sock)
    try:
        begin = pb.begin_provision_server(journal, slot_ref=SLOT_REF, at=NOW)
        assert begin["ok"] is True
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
            effect_id=begin["effectId"],
        )
        assert result["ok"] is True
        replayed = pj.replay(journal)
        prov = [
            e for e in replayed["effects"]
            if e["kind"] == pj.KIND_BROWSER_SERVER_PROVISIONED
        ]
        assert len(prov) == 1
        assert prov[0]["state"] == pj.STATE_APPLIED
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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


def test_teardown_server_refuses_when_browser_not_exited():
    # bite-axis: teardown exit — server exited but browser live refuses.
    tmp = _tmp_dir()
    journal = os.path.join(tmp, "journal.jsonl")
    record = _server_record()
    try:
        result = pb.teardown_server(
            journal,
            server_record=record,
            torn_down_at=LATER,
            begin_at=NOW,
            observe_exit=lambda pid: (
                {"exited": True, "status": 0}
                if pid == record["serverPid"]
                else {"exited": False, "status": None}
            ),
        )
        assert result["reason"] == pb.REFUSAL_TERMINAL_STATE_UNOBSERVED
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_teardown_server_success():
    tmp = _tmp_dir()
    journal = os.path.join(tmp, "journal.jsonl")
    sock = os.path.join(tmp, "pb-sockdir")
    os.makedirs(sock)
    record = _server_record(socketDir=sock)
    try:
        result = pb.teardown_server(
            journal,
            server_record=record,
            torn_down_at=LATER,
            begin_at=NOW,
            observe_exit=_both_exited_observer(),
        )
        assert result["ok"] is True
        assert result["receipt"]["socketDirRemoved"] is True
        assert result["receipt"]["observedServerExitStatus"] == 0
        assert result["receipt"]["observedBrowserExitStatus"] == 0
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
