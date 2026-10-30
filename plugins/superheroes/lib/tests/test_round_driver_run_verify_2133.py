"""#2133: the round driver runs the verify gate itself and lands its own result.

`round_driver.py run-verify` runs the session's bound verify command and publishes
`{result, exitCode, outputSha256, outputPath, command, ranBy}` as the `run-verify` landing, with a
`run-verify`/`landed` journal row carrying the payload's hash, in one commit. `advance` folds a
non-CI `run-verify` landing only against that row (`verify-landing-not-driver-written`, one site:
the `P_VERIFY` block of `cmd_submit`, reached through both advance routes); a `ci-exact-head` claim
and a hand `submit` are not subject to it.

THE REFUSAL STRING IS THE CONTRACT: every edge asserts the exact `reason`. The `run` seam of the verb
stands in for the process wherever a real one would only slow the test down; `test_the_command_runs_
under_bash_in_a_real_process` is the one that spawns bash for real.
"""
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import test_round_driver_advance as TA  # noqa: E402
from test_round_driver_advance import adapters  # noqa: E402,F401  (a fixture)
import test_verify_ci_head_2072 as T72  # noqa: E402
from test_verify_ci_head_2072 import fetch, real_verify_assembly  # noqa: E402,F401  (fixtures)

RD = TA.RD
RR = TA.RR
RP = TA.RP
COMMAND = "make test"
NOT_DRIVER = "verify-landing-not-driver-written"


# =============================================================================================
# helpers
# =============================================================================================

def _at_verify(tmp_path, name="s", command=COMMAND):
    d = TA._session(tmp_path, name=name, verifyCommand=command)
    TA._at_run_verify(tmp_path, d)
    return d


def _verb(d, exit_code=0, output=b"verify output\n", calls=None, **kw):
    return RD.cmd_run_verify(d, run=TA._verb_run(exit_code, output, calls), **kw)


def _never_run(argv, **kw):
    raise AssertionError("the verify command must not run here: %r" % (argv,))


def _state_bytes(d):
    with open(os.path.join(d, RD.STATE_FILE), "rb") as fh:
        return fh.read()


def _landing_dir(d):
    return RR.landing_dir(d, 1, RD.P_VERIFY)


def _landing_path(d, attempt=0):
    return RR.bare_payload_path(d, 1, RD.P_VERIFY, RR.storage_key("verify"), attempt)


def _claim_path(d, attempt=0):
    return os.path.join(_landing_dir(d), "_verify-claim.a%d.json" % attempt)


def _write_claim(d, text):
    os.makedirs(_landing_dir(d), exist_ok=True)
    with open(_claim_path(d), "w", encoding="utf-8") as fh:
        fh.write(text)


def _rows(d):
    return [e for e in TA._journal(d) if e.get("cmd") == "run-verify" and e.get("outcome") == "landed"]


def _nothing_landed(d):
    assert not os.path.lexists(_landing_path(d))
    assert _rows(d) == []
    assert not os.path.exists(_claim_path(d)), "a refused run left its claim behind"


def _refusals(d, reason):
    return [e for e in TA._journal(d)
            if e.get("cmd") == "run-verify" and e.get("outcome") == "refused" and e.get("reason") == reason]


def _token(out):
    return out["detail"] if out["reason"] == "fold-refused" else out["reason"]


def _hand_payload():
    return {"result": "pass", "command": COMMAND, "exit": 0}


def _assert_refused_not_driver_written(d, tmp_path):
    """The whole advance refusal: the exact token, nothing folded, the pending step alive, the state
    bytes and hash untouched, and the refusal journalled."""
    before = _state_bytes(d)
    hash_before = RD.state_hash(TA._state(d))
    out = TA._advance(d, tmp_path)
    assert out["ok"] is False and out["reason"] == "fold-refused" and out["detail"] == NOT_DRIVER, out
    assert _state_bytes(d) == before, "a refused fold mutated loop-state"
    assert RD.state_hash(TA._state(d)) == hash_before
    assert TA._pending(d)["phase"] == RD.P_VERIFY
    assert TA._state(d)["rounds"]["1"].get("verifyResult") is None
    assert NOT_DRIVER in [e.get("outcome") for e in TA._journal(d)]
    return out


def _folded_pass(d):
    return TA._state(d)["rounds"]["1"].get("verifyResult") == "pass"


# =============================================================================================
# the verb lands what it observed, and advance folds it
# =============================================================================================

def test_a_passing_command_lands_pass_and_advance_folds_it(tmp_path, adapters):
    d = _at_verify(tmp_path)
    calls = []
    out = _verb(d, calls=calls)
    assert out["ok"] is True and out["result"] == "pass", out
    assert (out["round"], out["attempt"]) == (1, 0)
    assert "staleClaimTakenOver" not in out
    assert out["landingPath"] == _landing_path(d)

    argv, kw = calls[0]
    assert argv == [shutil.which("bash"), "-c", COMMAND]
    assert kw["cwd"] == os.getcwd() and kw["timeout"] == 3600
    assert kw["stdin"] is subprocess.DEVNULL
    assert kw["stdout"] == subprocess.PIPE and kw["stderr"] == subprocess.STDOUT
    assert not kw.get("shell")

    payload, err = RR.read_json(out["landingPath"])
    assert err is None, err
    with open(out["outputPath"], "rb") as fh:
        captured = fh.read()
    assert captured == b"verify output\n"
    assert os.path.dirname(out["outputPath"]) == _landing_dir(d)
    assert os.path.basename(out["outputPath"]).startswith("_verify-output.a0.")
    assert out["outputPath"].endswith(".log")
    expected = {"result": "pass", "exitCode": 0,
                "outputSha256": hashlib.sha256(captured).hexdigest(),
                "outputPath": out["outputPath"], "command": COMMAND, "ranBy": "round-driver"}
    # the verb also records the head the command ran at, whenever its repo root is a git checkout
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=os.getcwd(), capture_output=True,
                          text=True, timeout=30)
    if head.returncode == 0:
        expected["headSha"] = head.stdout.strip()
    assert payload == expected
    # the payload's extra keys do not trip the shape guard: a recognised `result` is all it asks
    assert RP.verify_result_fault(payload) is None
    assert out["payloadSha256"] == RR.payload_sha256(payload)

    rows = _rows(d)
    assert len(rows) == 1
    assert (rows[0]["phase"], rows[0]["round"], rows[0]["attempt"]) == (RD.P_VERIFY, 1, 0)
    assert rows[0]["payloadSha256"] == RR.payload_sha256(payload)
    assert not os.path.exists(_claim_path(d))

    folded = TA._advance(d, tmp_path)
    assert folded["ok"] is True, folded
    assert folded["folded"] == {"phase": RD.P_VERIFY, "round": 1, "attempt": 0}
    assert _folded_pass(d)


def test_a_failing_command_lands_fail_and_advance_folds_the_halt(tmp_path, adapters):
    d = _at_verify(tmp_path)
    out = _verb(d, exit_code=3, output=b"1 failed\n")
    assert out["ok"] is True and out["result"] == "fail", out
    payload, err = RR.read_json(out["landingPath"])
    assert err is None and payload["exitCode"] == 3 and payload["result"] == "fail"
    folded = TA._advance(d, tmp_path)
    assert folded["ok"] is True and folded.get("terminal") == "halted", folded
    assert TA._state(d)["rounds"]["1"].get("verifyResult") == "fail"


def test_the_command_runs_under_bash_in_a_real_process(tmp_path, adapters):
    """`[[ ... ]]` is a bash word: it exits 127 under /bin/sh. stderr rides the same capture."""
    d = _at_verify(tmp_path, command="[[ -n x ]] && echo out && echo err >&2; exit 3")
    out = RD.cmd_run_verify(d)
    assert out["ok"] is True and out["result"] == "fail", out
    payload, _err = RR.read_json(out["landingPath"])
    assert payload["exitCode"] == 3
    with open(out["outputPath"], "rb") as fh:
        assert fh.read() == b"out\nerr\n"


def test_the_verb_leaves_state_and_its_hash_untouched(tmp_path, adapters):
    d = _at_verify(tmp_path)
    before = _state_bytes(d)
    hash_before = RD.state_hash(TA._state(d))
    assert _verb(d)["ok"] is True
    assert _state_bytes(d) == before
    assert RD.state_hash(TA._state(d)) == hash_before


def test_a_base_ref_token_reaches_the_run_with_the_pinned_base_bound(tmp_path, adapters):
    d = _at_verify(tmp_path)
    state = TA._state(d)
    state["config"]["verifyCommand"] = "git diff %s...HEAD" % RD.VERIFY_BASE_TOKEN
    state["config"]["baseRef"] = "a" * 40
    RD.save_state(d, state)
    calls = []
    out = _verb(d, calls=calls)
    assert out["ok"] is True, out
    bound = "git diff %s...HEAD" % ("a" * 40)
    assert calls[0][0][2] == bound
    payload, _err = RR.read_json(out["landingPath"])
    assert payload["command"] == bound


def test_the_timeout_flag_reaches_the_run(tmp_path, adapters):
    d = _at_verify(tmp_path)
    calls = []
    assert _verb(d, calls=calls, timeout=17)["ok"] is True
    assert calls[0][1]["timeout"] == 17


# =============================================================================================
# advance folds only what the driver landed
# =============================================================================================

def test_a_hand_written_landing_is_refused_at_advance_on_the_bare_route(tmp_path, adapters):
    d = _at_verify(tmp_path)
    TA._write_verify_payload(d, {"result": "pass"})
    _assert_refused_not_driver_written(d, tmp_path)


def test_a_hand_written_envelope_is_refused_at_advance_on_the_seat_route(tmp_path, real_verify_assembly):
    d = _at_verify(tmp_path)
    TA._land_and_record(d, "verify", payload=_hand_payload())
    assert not os.path.exists(_landing_path(d))
    _assert_refused_not_driver_written(d, tmp_path)


def test_the_driver_payload_folds_on_the_seat_route_though_the_assembly_drops_its_keys(
        tmp_path, real_verify_assembly):
    """The real `_assemble_verify` keeps `result`, `command`, `outputSha256` and drops `exitCode`,
    `outputPath` and `ranBy`, so the assembled artifact's own hash is not the landed payload's: the
    chokepoint is handed the stored envelope's payload hash."""
    d = _at_verify(tmp_path)
    landed = TA._land_verify_via_verb(d, as_record=True)
    stored, err = RR.read_json(TA._verify_store_path(d))
    assert err is None and stored["payload"] == landed
    assert RR.payload_sha256({k: landed[k] for k in ("result", "command", "outputSha256")}) \
        != RR.payload_sha256(landed)
    folded = TA._advance(d, tmp_path)
    assert folded["ok"] is True, folded
    assert _folded_pass(d)


def test_a_landing_edited_after_the_driver_wrote_it_is_refused(tmp_path, adapters):
    d = _at_verify(tmp_path)
    out = _verb(d, exit_code=3)
    payload, _err = RR.read_json(out["landingPath"])
    payload.update({"result": "pass", "exitCode": 0})
    RR.atomic_write_json(out["landingPath"], payload)
    _assert_refused_not_driver_written(d, tmp_path)


@pytest.mark.parametrize("row_round,row_attempt,authorizes", [
    (1, 0, True), (2, 0, False), (1, 1, False)], ids=["this-slot", "other-round", "other-attempt"])
def test_a_row_for_another_round_or_attempt_does_not_authorize(
        tmp_path, adapters, row_round, row_attempt, authorizes):
    d = _at_verify(tmp_path)
    payload = _hand_payload()
    TA._write_verify_payload(d, payload)
    RD._journal_append(d, {"cmd": "run-verify", "outcome": "landed", "phase": RD.P_VERIFY,
                           "round": row_round, "attempt": row_attempt,
                           "payloadSha256": RR.payload_sha256(payload)})
    if authorizes:
        assert TA._advance(d, tmp_path)["ok"] is True
        assert _folded_pass(d)
    else:
        _assert_refused_not_driver_written(d, tmp_path)


def test_a_lossy_journal_cannot_vouch_for_the_landing(tmp_path, adapters):
    d = _at_verify(tmp_path)
    assert _verb(d)["ok"] is True
    journal = os.path.join(d, RD.JOURNAL_FILE)
    with open(journal, "rb") as fh:
        intact = fh.read()
    with open(journal, "ab") as fh:
        fh.write(b"{not json\n")
    _assert_refused_not_driver_written(d, tmp_path)
    with open(journal, "wb") as fh:                      # A/B — the same journal, intact
        fh.write(intact)
    assert TA._advance(d, tmp_path)["ok"] is True
    assert _folded_pass(d)


def test_a_ci_exact_head_claim_is_not_subject_to_the_driver_written_check(tmp_path, adapters, fetch):
    d = _at_verify(tmp_path)
    head = RD._verified_head_at_fold(d, TA._state(d))[0]
    fetch.result = (T72._run(head=head), None)
    TA._write_verify_payload(d, T72._payload(ci=T72._ci(headSha=head)))
    out = TA._advance(d, tmp_path)
    assert out["ok"] is True, out
    assert _folded_pass(d)
    assert TA._state(d)["rounds"]["1"]["verifyVia"]["via"] == "ci-exact-head"
    assert _rows(d) == []


def test_a_ci_exact_head_claim_still_meets_its_own_refusal(tmp_path, adapters, fetch):
    d = _at_verify(tmp_path)
    head = RD._verified_head_at_fold(d, TA._state(d))[0]
    fetch.result = (T72._run(head=T72.OTHER_SHA), None)
    TA._write_verify_payload(d, T72._payload(ci=T72._ci(headSha=head)))
    out = TA._advance(d, tmp_path)
    assert out["ok"] is False and _token(out) == "ci-verify-sha-mismatch", out


def test_a_hand_submit_is_not_subject_to_the_check(tmp_path, adapters):
    d = _at_verify(tmp_path)
    state = TA._state(d)
    state.pop("_advanceUsed", None)
    RD.save_state(d, state)
    out = RD.cmd_submit(d, RD.P_VERIFY, 0, RD.state_hash(TA._state(d)), {"result": "pass"})
    assert out["ok"] is True and out.get("foldLanded") is True, out
    assert _folded_pass(d)


# =============================================================================================
# the concurrent shape
# =============================================================================================

def _audits_pending(d, landing, with_verify=True):
    state = TA._state(d)
    verify = {"phase": RD.P_VERIFY, "command": COMMAND, "round": state["round"], "attempt": 0,
              "landingPath": landing}
    payload = {"targets": []}
    if with_verify:
        payload["verify"] = verify
    original = dict(state["pending"])
    state["step"] = RD.P_AUDITS
    state["pending"] = {"action": RD.P_AUDITS, "round": state["round"], "phase": RD.P_AUDITS,
                        "attempt": 0, "payload": payload}
    RD.save_state(d, state)
    return original


def _audits_fold(d, run_verify_pending):
    """What the audits fold leaves behind: the gate's own pending step."""
    state = TA._state(d)
    state["step"] = RD.P_VERIFY
    state["pending"] = dict(run_verify_pending)
    RD.save_state(d, state)


def test_the_concurrent_shape_lands_while_dispatch_audits_is_pending(tmp_path, adapters):
    d = _at_verify(tmp_path)
    original = _audits_pending(d, _landing_path(d))
    before = _state_bytes(d)
    out = _verb(d)
    assert out["ok"] is True and out["result"] == "pass", out
    assert (out["round"], out["attempt"]) == (1, 0)
    assert out["landingPath"] == _landing_path(d)
    assert _state_bytes(d) == before, "the audits' expectedStateHash must not move"
    assert TA._pending(d)["phase"] == RD.P_AUDITS
    _audits_fold(d, original)
    folded = TA._advance(d, tmp_path)
    assert folded["ok"] is True and folded["folded"]["phase"] == RD.P_VERIFY, folded
    assert _folded_pass(d)


def test_the_audits_folding_during_the_run_does_not_move_the_slot(tmp_path, adapters):
    d = _at_verify(tmp_path)
    original = _audits_pending(d, _landing_path(d))

    def run(argv, **kw):
        _audits_fold(d, original)
        return subprocess.CompletedProcess(argv, 0, stdout=b"ok\n")

    out = RD.cmd_run_verify(d, run=run)
    assert out["ok"] is True and out["result"] == "pass", out
    assert os.path.exists(_landing_path(d))


# =============================================================================================
# E-1 .. E-12
# =============================================================================================

@pytest.mark.parametrize("shape", ["other-phase", "no-pending", "terminal"])
def test_e1_nothing_pending_another_phase_or_terminal_is_not_pending(tmp_path, adapters, shape):
    d = TA._session(tmp_path, verifyCommand=COMMAND)
    state = TA._state(d)
    if shape == "no-pending":
        state["pending"] = None
    elif shape == "terminal":
        state["terminal"] = "halted"
    RD.save_state(d, state)
    out = RD.cmd_run_verify(d, run=_never_run)
    assert out["ok"] is False and out["reason"] == "run-verify-not-pending", out
    assert len(_refusals(d, "run-verify-not-pending")) == 1


@pytest.mark.parametrize("verify", [None, "gate", ["x"]], ids=["absent", "string", "list"])
def test_e2_dispatch_audits_without_a_verify_slot_is_not_pending(tmp_path, adapters, verify):
    d = _at_verify(tmp_path)
    _audits_pending(d, _landing_path(d), with_verify=False)
    if verify is not None:
        state = TA._state(d)
        state["pending"]["payload"]["verify"] = verify
        RD.save_state(d, state)
    out = RD.cmd_run_verify(d, run=_never_run)
    assert out["ok"] is False and out["reason"] == "run-verify-not-pending", out


@pytest.mark.parametrize("filled", ["bare", "record", "dangling"])
def test_e3_a_filled_slot_is_already_landed(tmp_path, real_verify_assembly, filled):
    d = _at_verify(tmp_path)
    if filled == "bare":
        TA._write_verify_payload(d, _hand_payload())
    elif filled == "record":
        TA._land_and_record(d, "verify", payload=_hand_payload())
    else:
        os.makedirs(_landing_dir(d), exist_ok=True)
        os.symlink(os.path.join(_landing_dir(d), "no-such-file"), _landing_path(d))
    out = RD.cmd_run_verify(d, run=_never_run)
    assert out["ok"] is False and out["reason"] == "run-verify-already-landed", out
    assert not os.path.exists(_claim_path(d))
    assert _rows(d) == []


def test_e3_a_second_run_after_a_landing_is_already_landed(tmp_path, adapters):
    d = _at_verify(tmp_path)
    assert _verb(d)["ok"] is True
    out = RD.cmd_run_verify(d, run=_never_run)
    assert out["ok"] is False and out["reason"] == "run-verify-already-landed", out
    assert len(_rows(d)) == 1


def test_e4_a_live_claim_is_refused_in_progress_and_left_alone(tmp_path, adapters):
    d = _at_verify(tmp_path)
    claim = json.dumps({"pid": os.getpid(), "token": "t", "startedAt": "then"})
    _write_claim(d, claim)
    out = RD.cmd_run_verify(d, run=_never_run)
    assert out["ok"] is False and out["reason"] == "run-verify-in-progress", out
    assert out["claimPath"] == _claim_path(d)
    with open(_claim_path(d), encoding="utf-8") as fh:
        assert fh.read() == claim
    assert not os.path.exists(_landing_path(d))


def _dead_pid():
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


@pytest.mark.parametrize("kind", ["dead-pid", "malformed", "not-an-object", "pid-zero", "pid-bool",
                                  "pid-string"])
def test_e4_a_stale_claim_is_taken_over_and_reported(tmp_path, adapters, kind):
    d = _at_verify(tmp_path)
    text = {"dead-pid": lambda: json.dumps({"pid": _dead_pid(), "token": "t"}),
            "malformed": lambda: "{not json",
            "not-an-object": lambda: "[1]",
            "pid-zero": lambda: json.dumps({"pid": 0}),
            "pid-bool": lambda: json.dumps({"pid": True}),
            "pid-string": lambda: json.dumps({"pid": "abc"})}[kind]()
    _write_claim(d, text)
    out = _verb(d)
    assert out["ok"] is True and out["result"] == "pass", out
    assert out["staleClaimTakenOver"] is True
    assert os.path.exists(_landing_path(d))
    assert not os.path.exists(_claim_path(d))


def test_e4_a_second_runner_during_the_run_is_refused_in_progress(tmp_path, adapters):
    d = _at_verify(tmp_path)
    seen = {}

    def run(argv, **kw):
        with open(_claim_path(d), encoding="utf-8") as fh:
            seen["claim"] = json.load(fh)
        seen["second"] = RD.cmd_run_verify(d, run=_never_run)
        return subprocess.CompletedProcess(argv, 0, stdout=b"ok\n")

    out = RD.cmd_run_verify(d, run=run)
    assert out["ok"] is True and out["result"] == "pass", out
    assert seen["claim"]["pid"] == os.getpid()
    assert len(seen["claim"]["token"]) == 32 and seen["claim"]["startedAt"]
    assert seen["second"]["ok"] is False and seen["second"]["reason"] == "run-verify-in-progress", seen
    assert seen["second"]["claimPath"] == _claim_path(d)
    assert not os.path.exists(_claim_path(d))
    assert os.path.basename(out["outputPath"]).endswith(".%s.log" % seen["claim"]["token"])
    assert len(_rows(d)) == 1


@pytest.mark.parametrize("command", ["none", "", " None "])
def test_e5_an_unconfigured_command_lands_none_and_runs_nothing(tmp_path, adapters, command):
    d = _at_verify(tmp_path, command=command)
    out = RD.cmd_run_verify(d, run=_never_run)
    assert out["ok"] is True and out["result"] == "none", out
    assert out["outputPath"] is None
    payload, err = RR.read_json(out["landingPath"])
    assert err is None and payload == {"result": "none", "ranBy": "round-driver"}
    assert RP.verify_result_fault(payload) is None
    assert [n for n in os.listdir(_landing_dir(d)) if n.startswith("_verify-output")] == []
    assert len(_rows(d)) == 1 and not os.path.exists(_claim_path(d))


def test_e6_bash_absent_is_refused_before_any_claim(tmp_path, adapters, monkeypatch):
    d = _at_verify(tmp_path)
    monkeypatch.setattr(RD.shutil, "which", lambda name: None)
    out = RD.cmd_run_verify(d, run=_never_run)
    assert out["ok"] is False and out["reason"] == "run-verify-no-bash", out
    _nothing_landed(d)


def test_e6_an_unconfigured_command_needs_no_bash(tmp_path, adapters, monkeypatch):
    d = _at_verify(tmp_path, command="none")
    monkeypatch.setattr(RD.shutil, "which", lambda name: None)
    out = RD.cmd_run_verify(d, run=_never_run)
    assert out["ok"] is True and out["result"] == "none", out


@pytest.mark.parametrize("exc", [FileNotFoundError(2, "no such directory"), PermissionError("denied"),
                                 ValueError("embedded null byte")],
                         ids=["not-found", "permission", "value"])
def test_e7_a_spawn_failure_is_refused_with_the_claim_released(tmp_path, adapters, exc):
    d = _at_verify(tmp_path)

    def run(argv, **kw):
        raise exc

    out = RD.cmd_run_verify(d, run=run)
    assert out["ok"] is False and out["reason"] == "run-verify-spawn-failed", out
    assert type(exc).__name__ in out["detail"]
    _nothing_landed(d)


@pytest.mark.parametrize("partial", [b"half a log", None], ids=["partial-output", "no-output"])
def test_e8_a_timeout_lands_timeout_with_no_exit_code(tmp_path, adapters, partial):
    d = _at_verify(tmp_path)

    def run(argv, **kw):
        raise subprocess.TimeoutExpired(argv, kw["timeout"], output=partial)

    out = RD.cmd_run_verify(d, run=run, timeout=5)
    assert out["ok"] is True and out["result"] == "timeout", out
    payload, _err = RR.read_json(out["landingPath"])
    assert payload["exitCode"] is None
    assert payload["outputSha256"] == hashlib.sha256(partial or b"").hexdigest()
    with open(out["outputPath"], "rb") as fh:
        assert fh.read() == (partial or b"")
    assert RP.verify_result_fault(payload) is None
    folded = TA._advance(d, tmp_path)
    assert folded["ok"] is True and folded.get("terminal") == "halted", folded


def _pid_gone(pid, within=5.0):
    """True once `pid` no longer exists, polled for up to `within` seconds. A zombie awaiting a reaper
    that never comes (a container whose pid 1 does not wait) is dead for this purpose."""
    deadline = time.monotonic() + within
    while True:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        try:
            with open("/proc/%d/stat" % pid, encoding="utf-8") as fh:
                if fh.read().rpartition(")")[2].split()[0] in ("Z", "X"):
                    return True
        except (OSError, IndexError):
            pass
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)


def _kill_if_alive(pid):
    if pid is None:
        return
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


_GROUP_KWARGS = dict(stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


@pytest.mark.proc_containment
def test_a_timeout_kills_the_whole_process_group():
    pid = None
    try:
        started = time.monotonic()
        with pytest.raises(subprocess.TimeoutExpired) as caught:
            RD._run_in_process_group(["bash", "-c", "sleep 30 & echo $!; wait"], timeout=1,
                                     **_GROUP_KWARGS)
        elapsed = time.monotonic() - started
        pid = int(caught.value.output.split()[0])
        assert _pid_gone(pid), "the background child %d outlived the timeout" % pid
        # a kill that spared the group would leave the child holding the output pipe, and the call
        # would only return when that child's `sleep 30` ended on its own
        assert elapsed < 15, "the call took %.1fs; the group was not killed at the timeout" % elapsed
    finally:
        _kill_if_alive(pid)


@pytest.mark.proc_containment
def test_a_detached_helper_holding_the_pipe_does_not_stall_the_timeout(tmp_path, monkeypatch):
    pid_file = tmp_path / "helper.pid"
    monkeypatch.setattr(RD, "_POST_KILL_DRAIN_SECONDS", 0.5)
    parent = ("import subprocess,sys,time; "
              "p=subprocess.Popen(['sleep','30'], start_new_session=True); "
              "open(sys.argv[1],'w').write(str(p.pid)); print('partial', flush=True); time.sleep(60)")
    pid = None
    try:
        started = time.monotonic()
        with pytest.raises(subprocess.TimeoutExpired) as caught:
            RD._run_in_process_group([sys.executable, "-B", "-c", parent, str(pid_file)], timeout=1.5,
                                     **_GROUP_KWARGS)
        elapsed = time.monotonic() - started
        if pid_file.exists():
            pid = int(pid_file.read_text())
        assert elapsed < 15, "the call took %.1fs; the drain after the kill was unbounded" % elapsed
        assert b"partial" in caught.value.output
    finally:
        _kill_if_alive(pid)


@pytest.mark.proc_containment
def test_an_interrupted_wait_kills_the_whole_process_group(tmp_path, monkeypatch):
    pid_file = tmp_path / "child.pid"
    real_communicate = subprocess.Popen.communicate
    calls = []
    pid = None

    def communicate(self, *args, **kwargs):
        calls.append(self)
        if len(calls) > 1:
            return real_communicate(self, *args, **kwargs)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            text = pid_file.read_text() if pid_file.exists() else ""
            if text.endswith("\n") and text.strip().isdigit():
                raise RuntimeError("boom")
            time.sleep(0.02)
        raise AssertionError("the command never wrote its background pid")

    monkeypatch.setattr(subprocess.Popen, "communicate", communicate)
    try:
        started = time.monotonic()
        with pytest.raises(RuntimeError, match="boom"):
            RD._run_in_process_group(["bash", "-c", "sleep 30 & echo $! > %s; wait" % pid_file],
                                     **_GROUP_KWARGS)
        elapsed = time.monotonic() - started
        pid = int(pid_file.read_text())
        assert _pid_gone(pid), "the background child %d outlived the interrupted wait" % pid
        # without the group kill, cleanup would wait for the child's `sleep 30` to end on its own
        assert elapsed < 15, "the call took %.1fs; the group was not killed on interruption" % elapsed
    finally:
        if pid is None and pid_file.exists() and pid_file.read_text().strip().isdigit():
            pid = int(pid_file.read_text())
        _kill_if_alive(pid)


@pytest.mark.proc_containment
def test_a_sigterm_to_the_driver_kills_the_whole_process_group(tmp_path):
    import threading

    pid_file = tmp_path / "child.pid"
    pid = None

    def send_sigterm_once_the_child_is_up():
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            text = pid_file.read_text() if pid_file.exists() else ""
            if text.endswith("\n") and text.strip().isdigit():
                os.kill(os.getpid(), signal.SIGTERM)
                return
            time.sleep(0.02)

    sender = threading.Thread(target=send_sigterm_once_the_child_is_up, daemon=True)
    previous = signal.getsignal(signal.SIGTERM)
    try:
        sender.start()
        started = time.monotonic()
        with pytest.raises(SystemExit) as caught:
            RD._run_in_process_group(["bash", "-c", "sleep 30 & echo $! > %s; wait" % pid_file],
                                     **_GROUP_KWARGS)
        elapsed = time.monotonic() - started
        assert caught.value.code == 128 + signal.SIGTERM
        pid = int(pid_file.read_text())
        assert _pid_gone(pid), "the background child %d outlived the driver's SIGTERM" % pid
        # without the group kill, cleanup would wait for the child's `sleep 30` to end on its own
        assert elapsed < 15, "the call took %.1fs; the group was not killed on SIGTERM" % elapsed
        assert signal.getsignal(signal.SIGTERM) == previous, "the SIGTERM handler was not restored"
    finally:
        sender.join(timeout=15)
        if pid is None and pid_file.exists() and pid_file.read_text().strip().isdigit():
            pid = int(pid_file.read_text())
        _kill_if_alive(pid)


class _Clock(object):
    def __init__(self):
        self.t = 0.0
        self.sleeps = []

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.t += seconds


def _hold_lock(d):
    with open(RR.session_lock_path(d), "w", encoding="utf-8") as fh:
        json.dump({"pid": 999999, "createdAt": "then"}, fh)


def _release_lock(d):
    os.remove(RR.session_lock_path(d))


def test_e10_a_lock_held_past_the_wait_refuses_and_parks_nothing(tmp_path, adapters):
    d = _at_verify(tmp_path)
    clock = _Clock()

    def run(argv, **kw):
        _hold_lock(d)
        return subprocess.CompletedProcess(argv, 0, stdout=b"ok\n")

    out = RD.cmd_run_verify(d, run=run, clock=clock.now, sleep=clock.sleep, lock_wait=2)
    assert out["ok"] is False and out["reason"] == "run-verify-publish-lock-held", out
    assert clock.sleeps == [0.5] * 4
    _release_lock(d)
    _nothing_landed(d)
    # the computed result was not parked: the next run runs the command again and lands it
    calls = []
    again = _verb(d, calls=calls)
    assert again["ok"] is True and len(calls) == 1, again


def test_e10_a_lock_released_within_the_wait_publishes(tmp_path, adapters):
    d = _at_verify(tmp_path)
    clock = _Clock()

    def run(argv, **kw):
        _hold_lock(d)
        return subprocess.CompletedProcess(argv, 0, stdout=b"ok\n")

    def sleep(seconds):
        clock.sleep(seconds)
        if len(clock.sleeps) == 2:
            _release_lock(d)

    out = RD.cmd_run_verify(d, run=run, clock=clock.now, sleep=sleep, lock_wait=30)
    assert out["ok"] is True and out["result"] == "pass", out
    assert clock.sleeps == [0.5, 0.5]
    assert len(_rows(d)) == 1 and not os.path.exists(_claim_path(d))


def _move_attempt(d):
    state = TA._state(d)
    state["pending"] = dict(state["pending"], attempt=1)
    RD.save_state(d, state)


def _fill_slot(d):
    RR.atomic_write_json(_landing_path(d), {"result": "pass", "hand": "written"})


def _leave_phase(d):
    state = TA._state(d)
    state["terminal"] = "halted"
    RD.save_state(d, state)


@pytest.mark.parametrize("mover", [_move_attempt, _fill_slot, _leave_phase],
                         ids=["attempt-moved", "slot-filled", "phase-left"])
def test_e11_a_slot_that_moved_or_filled_during_the_run_lands_nothing(tmp_path, adapters, mover):
    d = _at_verify(tmp_path)

    def run(argv, **kw):
        mover(d)
        return subprocess.CompletedProcess(argv, 0, stdout=b"ok\n")

    out = RD.cmd_run_verify(d, run=run)
    assert out["ok"] is False and out["reason"] == "run-verify-slot-moved", out
    assert _rows(d) == []
    assert not os.path.exists(_claim_path(d))
    if mover is _fill_slot:
        payload, _err = RR.read_json(_landing_path(d))
        assert payload == {"result": "pass", "hand": "written"}, "the verb overwrote a filled slot"
    else:
        assert not os.path.lexists(_landing_path(d))


def test_e12_a_refused_commit_is_answered_and_the_claim_released(tmp_path, adapters, monkeypatch):
    d = _at_verify(tmp_path)
    real_begin = RD.round_commit.begin

    def begin(session_dir, kind, **kw):
        if kind == "run-verify-land":
            raise RD.round_commit.CommitRefused("target-escapes-session", "no way out")
        return real_begin(session_dir, kind, **kw)

    monkeypatch.setattr(RD.round_commit, "begin", begin)
    out = _verb(d)
    assert out["ok"] is False and out["reason"] == "target-escapes-session", out
    assert out["detail"] == "no way out"
    _nothing_landed(d)


def test_the_landing_and_its_journal_row_ride_one_commit(tmp_path, adapters, monkeypatch):
    d = _at_verify(tmp_path)
    seen = []
    real_begin = RD.round_commit.begin

    def spy(session_dir, kind, **kw):
        commit = real_begin(session_dir, kind, **kw)
        seen.append((kind, commit))
        return commit

    monkeypatch.setattr(RD.round_commit, "begin", spy)
    assert _verb(d)["ok"] is True
    lands = [c for kind, c in seen if kind == "run-verify-land"]
    assert len(lands) == 1, [k for k, _ in seen]
    parts = lands[0]._parts
    assert [os.path.join(d, p.get("target")) for p in parts if p.get("type") == "replace-file"] \
        == [_landing_path(d)]
    assert [(p.get("entry") or {}).get("outcome") for p in parts if p.get("type") == "journal-append"] \
        == ["landed"]


# =============================================================================================
# the CLI
# =============================================================================================

def test_the_cli_prints_the_result_object(tmp_path, adapters, capsys):
    d = _at_verify(tmp_path, command="true")
    rc = RD.main(["run-verify", "--session-dir", d])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["ok"] is True and out["result"] == "pass", out
    assert (out["round"], out["attempt"]) == (1, 0)
    assert out["landingPath"] == _landing_path(d) and os.path.exists(out["outputPath"])
    assert out["payloadSha256"] == RR.payload_sha256(RR.read_json(out["landingPath"])[0])


def test_the_cli_exits_zero_with_ok_false_on_a_refusal(tmp_path, adapters, capsys):
    d = TA._session(tmp_path, verifyCommand=COMMAND)
    rc = RD.main(["run-verify", "--session-dir", d])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["ok"] is False and out["reason"] == "run-verify-not-pending", out


@pytest.mark.parametrize("argv,expected", [([], 3600), (["--timeout", "7"], 7)])
def test_the_cli_timeout_defaults_to_an_hour(tmp_path, adapters, monkeypatch, capsys, argv, expected):
    d = TA._session(tmp_path)
    seen = {}

    def fake(session_dir, timeout=None, **kw):
        seen["timeout"] = timeout
        return {"ok": True}

    monkeypatch.setattr(RD, "cmd_run_verify", fake)
    assert RD.main(["run-verify", "--session-dir", d] + argv) == 0
    assert seen["timeout"] == expected
