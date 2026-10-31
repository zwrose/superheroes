#!/usr/bin/env python3
"""#1721 — a new review session takes nothing from a records file, and the driver never reads one.

The records file named by ``recordsPath`` is an export of the session's ledger: whenever the driver
writes it, its bytes are ``review_memory.records_bytes`` of this session's ledger and nothing else.
These tests watch every ``open`` of the file through an audit hook rather than trusting the code
path by inspection.
"""
import contextlib
import json
import os
import sys

from test_round_driver import (
    RD,
    _cfg,
    _cfg_cert,
    _guard_argv,
    _run_loop_capturing_state,
    _seams,
    _seed_record,
    _vacuous_round1_seams,
)
from test_round_driver_records_cli import _A_FINDING, _responder

RM = RD.review_memory

# --- the open-recorder ---------------------------------------------------------------------
# An audit hook cannot be removed, so this one is inert unless the switch is on. It never opens a
# file and never raises, so it cannot disturb the repository's own source-guard hook.
# An open is skipped only when it cannot read: a string mode with no `r` and no `+`, or integer
# flags whose access mode is write-only. Read-only and read-write opens are both recorded.
_READ_MODE_CHARS = "r+"
_RECORDER = {"on": False, "reads": []}


def _audit(event, args):
    if event != "open" or not _RECORDER["on"]:
        return
    try:
        path, mode, flags = args
        if isinstance(mode, str) and not any(ch in mode for ch in _READ_MODE_CHARS):
            return
        if isinstance(flags, int) and flags & os.O_ACCMODE == os.O_WRONLY:
            return
        if isinstance(path, int):
            return
        _RECORDER["reads"].append(os.path.realpath(os.fsdecode(path)))
    except Exception:
        return


sys.addaudithook(_audit)


@contextlib.contextmanager
def _recording():
    """Collect the real path of every file opened for reading while the block runs."""
    _RECORDER["reads"] = []
    _RECORDER["on"] = True
    try:
        yield _RECORDER["reads"]
    finally:
        _RECORDER["on"] = False


def _reads_of(reads, path):
    target = os.path.realpath(str(path))
    return [r for r in reads if r == target]


# --- shared set-up -------------------------------------------------------------------------
_STALE_DISCLOSURE = "stale-seat-from-another-session"


def _another_sessions_records():
    return [_seed_record(n, {"vacuousSeats": [_STALE_DISCLOSURE]}) for n in (1, 2, 3)]


def _ledger_bytes(state):
    payload = RD._round_records_payload(state, state["config"])
    assert payload["outcome"] == "ready", payload
    return RM.records_bytes(payload["records"])


# T1 — axis: `new_state` reads no records file and seeds nothing from one.
def test_new_state_takes_nothing_from_a_records_file(tmp_path):
    records = tmp_path / "round-records.json"
    records.write_bytes(RM.records_bytes(_another_sessions_records()))
    before = records.read_bytes()
    with _recording() as reads:
        state = RD.new_state(_cfg(dimensions=["test-role"], recordsPath=str(records)))
    assert state["round"] == 1
    assert state["_records"] == []
    assert state["_coverage"] == []
    assert state["rounds"] == {}
    assert "confirmations" not in state
    assert _reads_of(reads, records) == []
    assert records.read_bytes() == before


# T2 — axis: the library writer path (`run_loop` -> `_persist_round_records`) never reads the file
# it replaces, and what it leaves is exactly this run's ledger.
def test_run_loop_replaces_a_preexisting_file_without_reading_it(tmp_path):
    records = tmp_path / "round-records.json"
    records.write_bytes(RM.records_bytes(_another_sessions_records()))
    cfg = _cfg_cert(dimensions=["test-role", "code-reviewer"], recordsPath=str(records),
                    maxRounds=8)
    with _recording() as reads:
        _, state = _run_loop_capturing_state(_vacuous_round1_seams(), cfg)
    assert state is not None and state["_records"], "the run must have folded at least one round"
    assert _reads_of(reads, records) == []
    assert records.read_bytes() == _ledger_bytes(state)
    assert _STALE_DISCLOSURE not in records.read_text()


# T3 — axis: the command-line writer path (`next --records-path`, then `submit`'s commit sidecar)
# never reads the file it replaces, and what it leaves is exactly this session's ledger.
def test_cli_next_and_submit_replace_a_preexisting_file_without_reading_it(tmp_path, capsys):
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir)
    records = tmp_path / "export" / "round-records.json"
    os.makedirs(records.parent)
    records.write_bytes(RM.records_bytes(_another_sessions_records()))
    argv = ["next", "--session-dir", session_dir, "--records-path", str(records)]
    argv += _guard_argv(session_dir, fresh=True)
    respond = _responder(round1_findings=[dict(_A_FINDING)])
    with _recording() as reads:
        rc = RD.main(argv)
        out = capsys.readouterr().out.strip()
        n = json.loads(out.splitlines()[-1])
        assert rc == 0 and n["ok"], n
        assert n["phase"] == RD.P_PANEL, n
        sub = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"],
                            respond(n["phase"], n["payload"], n["round"]))
        assert sub["ok"], sub
    assert _reads_of(reads, records) == []
    ok, state = RD.load_state(session_dir)
    assert ok and state is not None and state["_records"]
    assert records.read_bytes() == _ledger_bytes(state)
    assert _STALE_DISCLOSURE not in records.read_text()


# T4 — axis: a pre-existing corrupt (not JSON) file neither parks the run nor survives the first
# write.
def test_corrupt_preexisting_file_does_not_park_and_is_replaced(tmp_path):
    records = tmp_path / "round-records.json"
    records.write_text("{corrupt not-a-list")
    cfg = _cfg_cert(dimensions=["test-role"], recordsPath=str(records))
    with _recording() as reads:
        receipt, state = _run_loop_capturing_state(_seams(), cfg)
    assert _reads_of(reads, records) == []
    assert receipt["verdict"] != "cannot-certify"
    assert not any("durable round records" in (d.get("detail") or "") for d in state["decisions"])
    assert state["_records"]
    assert records.read_bytes() == _ledger_bytes(state)
    assert isinstance(json.loads(records.read_text()), list)
