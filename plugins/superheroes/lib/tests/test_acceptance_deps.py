# plugins/superheroes/lib/tests/test_acceptance_deps.py
#
# Covers two review findings against acceptance_deps.py:
#
# test-001: `_lease_liveness` (the UFR-4 fail-closed tri-state safety classifier feeding
# `real_reclaim_probe` -> `acceptance_reclaim.decide`) had zero test coverage. Pins each
# branch, including the two fail-open mutants the finding calls out by name: a foreign-host
# lease must NEVER report "dead" (only "unconfirmable"), and a PermissionError from os.kill
# must report "unconfirmable", not "alive" or "dead".
#
# architecture-reviewer (real_run_outcome field mismatch): `real_run_outcome` must read the
# actual `run_readout.run_outcome` projection's field names (`status`/`checks`/`reason`/
# `prUrl`/`phasesTraversed`), not invented ones (`terminal`/`checksGreen`/`failureKind`) that
# the real showrunner projection never emits. Pins that a genuinely-green run-outcome record
# projects to a `terminal: "ready"` / `readout_claimed_checks_green: True` fact set — the
# exact shape `acceptance_verdict.decide` needs to compute a pass.
import os
import socket
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_deps as deps
import hostinfo


# --- _lease_liveness -------------------------------------------------------------------


def test_liveness_unconfirmable_when_lease_is_not_a_dict_or_missing():
    assert deps._lease_liveness(None) == "unconfirmable"
    assert deps._lease_liveness("not-a-dict") == "unconfirmable"
    assert deps._lease_liveness({}) == "unconfirmable"


def test_liveness_unconfirmable_when_no_pid_recorded():
    assert deps._lease_liveness({"host": socket.gethostname()}) == "unconfirmable"


def test_liveness_foreign_host_is_unconfirmable_never_dead(monkeypatch):
    # This is the mutant the finding calls out: flipping this branch to "dead" would let
    # the harness reclaim and trample a genuinely-alive run on another host.
    lease = {"pid": 123, "host": "some-other-host-xyz"}
    monkeypatch.setattr(socket, "gethostname", lambda: "this-host")
    assert deps._lease_liveness(lease) == "unconfirmable"


def test_liveness_dead_when_boot_id_differs():
    lease = {"pid": 123, "host": socket.gethostname(), "bootId": "boot-A"}
    import hostinfo as hi
    orig = hi.boot_id
    hi.boot_id = lambda: "boot-B"
    try:
        assert deps._lease_liveness(lease) == "dead"
    finally:
        hi.boot_id = orig


def test_liveness_alive_when_pid_signalable(monkeypatch):
    lease = {"pid": os.getpid(), "host": socket.gethostname(), "bootId": None}
    assert deps._lease_liveness(lease) == "alive"


def test_liveness_dead_when_pid_lookup_error(monkeypatch):
    def fake_kill(pid, sig):
        raise ProcessLookupError()
    monkeypatch.setattr(os, "kill", fake_kill)
    lease = {"pid": 99999999, "host": socket.gethostname(), "bootId": None}
    assert deps._lease_liveness(lease) == "dead"


def test_liveness_unconfirmable_on_permission_error_never_alive_or_dead(monkeypatch):
    # The other fail-open mutant the finding calls out: dropping the PermissionError
    # handling would let an unsignalable-but-possibly-alive pid be misjudged.
    def fake_kill(pid, sig):
        raise PermissionError()
    monkeypatch.setattr(os, "kill", fake_kill)
    lease = {"pid": 1, "host": socket.gethostname(), "bootId": None}
    assert deps._lease_liveness(lease) == "unconfirmable"


def test_liveness_unconfirmable_on_malformed_pid(monkeypatch):
    lease = {"pid": "not-an-int", "host": socket.gethostname(), "bootId": None}
    assert deps._lease_liveness(lease) == "unconfirmable"


# --- real_run_outcome --------------------------------------------------------------------


def _write_json(path, obj):
    import json
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


def test_real_run_outcome_reads_the_actual_run_readout_projection_shape():
    """A genuinely green run_readout.run_outcome() record must project to facts that
    acceptance_verdict.decide can pass — not the harness's invented (wrong) field names."""
    d = tempfile.mkdtemp()
    try:
        record = {
            "status": "ready",
            "phase": "ship",
            "reason": "merge-ready",
            "prUrl": "https://github.com/o/r/pull/9",
            "checks": "green",
            "phasesTraversed": ["plan", "tasks", "build", "review", "ship"],
            "readoutPath": "/some/readout.md",
        }
        path = os.path.join(d, "terminal-record.json")
        _write_json(path, record)

        read = deps.real_run_outcome("root")
        out = read(path)

        assert out["terminal"] == "ready"
        assert out["phases"] == ["plan", "tasks", "build", "review", "ship"]
        assert out["readout_pr_link"] == "https://github.com/o/r/pull/9"
        assert out["readout_claimed_checks_green"] is True
        assert out["readout_claimed_pr"] == "https://github.com/o/r/pull/9"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_real_run_outcome_no_required_checks_is_not_claimed_green():
    d = tempfile.mkdtemp()
    try:
        record = {
            "status": "ready", "prUrl": "https://x/pr/1", "checks": "none",
            "phasesTraversed": ["plan"],
        }
        path = os.path.join(d, "terminal-record.json")
        _write_json(path, record)
        out = deps.real_run_outcome("root")(path)
        assert out["readout_claimed_checks_green"] is False
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_real_run_outcome_parked_state_projects_to_non_ready_terminal():
    d = tempfile.mkdtemp()
    try:
        record = {
            "status": "parked", "reason": "ceiling breached", "checks": "none",
            "phasesTraversed": ["plan"],
        }
        path = os.path.join(d, "terminal-record.json")
        _write_json(path, record)
        out = deps.real_run_outcome("root")(path)
        assert out["terminal"] == "parked"
        assert out["failure_kind"] == "ceiling breached"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_real_run_outcome_missing_file_fails_closed_to_parked_default():
    out = deps.real_run_outcome("root")("/no/such/path/terminal-record.json")
    assert out["terminal"] == "parked"
    assert out["failure_kind"] == "no-terminal-record"


def test_real_run_outcome_corrupt_json_fails_closed():
    d = tempfile.mkdtemp()
    try:
        path = os.path.join(d, "terminal-record.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        out = deps.real_run_outcome("root")(path)
        assert out["terminal"] == "parked"
    finally:
        shutil.rmtree(d, ignore_errors=True)
