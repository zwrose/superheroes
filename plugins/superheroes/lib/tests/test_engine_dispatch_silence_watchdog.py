"""#2375 order B: the codex review seat's silence watchdog in engine_dispatch._run_engine_files.

In-process tests drive ED._run_engine_files with a real fake `codex` subprocess. The loop's clock is
a deterministic fake (_Clock): one poll tick is exactly 0.25 fake seconds, so a beat is one tick and the
tick on which the watchdog becomes due (threshold 0.3 -> the second silent beat, 0.5 s) is exact.

Pinned condition (stated here, at the pin): ED.time is replaced for the test, HEARTBEAT_INTERVAL is 0.05.
Production timing the pin makes unobservable: the real beat is 10 s and a real tick is ~0.2 s, so the
real accumulation of `silent_s` is coarser (10 s steps) and wall-clock jitter between ticks is not
modelled; the e2e test in test_engine_dispatch_e2e.py runs the real 10 s heartbeat.
"""
import importlib.util
import json
import os
import subprocess
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_td():
    spec = importlib.util.spec_from_file_location(
        "test_engine_dispatch", os.path.join(_HERE, "test_engine_dispatch.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


TD = _load_td()
ED = TD.ED
CS = ED.codex_silence

_THRESHOLD = 0.3
_ABSENT = object()
_TICK = 0.25


def _spec_module(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, "..", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- fake clock, fake engines, run fixtures -----------------------------------------------------------


class _Clock:
    """Replaces ED.time: monotonic() only moves in sleep(), by exactly one tick. sleep() also really
    sleeps (so SIGTERM grace and process startup keep their real durations) and runs before_tick(n)."""

    def __init__(self, monkeypatch, before_tick=None):
        self.now = 1000.0
        self.ticks = 0
        self.before_tick = before_tick
        clock = self
        real = time

        class Shim:
            def monotonic(self):
                return clock.now

            def sleep(self, secs):
                if clock.before_tick is not None:
                    clock.before_tick(clock.ticks)
                clock.ticks += 1
                clock.now += _TICK
                real.sleep(secs)

            def __getattr__(self, name):
                return getattr(real, name)

        monkeypatch.setattr(ED, "time", Shim())


def _wait_for(predicate, what, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    pytest.fail("fixture wait timed out: %s" % what)


def _nonempty(path):
    return lambda: os.path.exists(path) and os.path.getsize(path) > 0


class _GatedProc:
    """The engine Popen, except poll() reports None until its `gate`-th call, then waits for the real
    process to be gone and reports its real return code."""

    def __init__(self, proc, gate):
        self._p = proc
        self._gate = gate
        self._calls = 0

    def poll(self):
        self._calls += 1
        if self._calls < self._gate:
            return None
        try:
            self._p.wait(timeout=10)
        except Exception:
            pass
        return self._p.poll()

    def __getattr__(self, name):
        return getattr(self._p, name)


def _gate_engine_poll(monkeypatch, gate):
    real_popen = subprocess.Popen

    def popen(argv, *args, **kwargs):
        proc = real_popen(argv, *args, **kwargs)
        if os.path.basename(str(argv[0])) in ("codex", "cursor-agent"):
            return _GatedProc(proc, gate)
        return proc

    monkeypatch.setattr(ED.subprocess, "Popen", popen)


def _result_json(body="issue found"):
    branch = TD._native_review_branch("findings")
    branch["findings"][0]["id"] = "f1"
    branch["findings"][0]["body"] = body
    return json.dumps(TD._wrap_native_review_result(branch), separators=(",", ":"))


_PRELUDE = """\
import json, os, signal, sys, time
_stdin = sys.stdin.read()
_out = sys.argv[sys.argv.index("-o") + 1] if "-o" in sys.argv else None
_RESULT = %r
""" % _result_json()

_STARTED = '{"type":"item.started","item":{"id":"c1","type":"command_execution","command":"x"}}'
_COMPLETED = '{"type":"item.completed","item":{"id":"c1","type":"command_execution","command":"x"}}'

_SILENT = _PRELUDE + "time.sleep(20)\n"
_TURN = _PRELUDE + "sys.stdout.write('{\"type\":\"turn.started\"}\\n'); sys.stdout.flush()\ntime.sleep(20)\n"
_ANSWER = _PRELUDE + "open(_out, 'w').write(_RESULT)\nsys.exit(0)\n"
_SILENT_THEN_ANSWER = _PRELUDE + (
    "if _out.endswith('-1.json'):\n    time.sleep(20)\n"
    "open(_out, 'w').write(_RESULT)\nsys.exit(0)\n")


def _command_script(completed):
    lines = [_STARTED] + ([_COMPLETED] if completed else [])
    return _PRELUDE + "sys.stdout.write(%r)\nsys.stdout.flush()\ntime.sleep(20)\n" % ("\n".join(lines) + "\n")


def _sigterm_answer_script(ready_path):
    return _PRELUDE + (
        "def _h(signum, frame):\n"
        "    with open(_out, 'w') as fh:\n        fh.write(_RESULT)\n"
        "    sys.exit(0)\n"
        "signal.signal(signal.SIGTERM, _h)\n"
        "open(%r, 'w').close()\n"
        "time.sleep(20)\n") % ready_path


def _open_run(tmp_path, *, name="run", run_kind=None, engine="codex", watchdog=_THRESHOLD,
              attempts=(1,)):
    """A journaled run ready for ED._run_engine_files. Returns (run_dir, prompt_path, argv)."""
    run_kind = ED.RUN_KIND_REVIEW if run_kind is None else run_kind
    run_dir = str(tmp_path / name)
    os.makedirs(run_dir)
    prompt = os.path.join(run_dir, "prompt.txt")
    with open(prompt, "w", encoding="utf-8") as fh:
        fh.write("go\n")
    review = run_kind == ED.RUN_KIND_REVIEW
    role_kind = ED.RUN_KIND_REVIEW if review else "build"
    if engine == "codex":
        seat = TD._codex_seat(role=TD._REVIEW_ROLE if review else TD._WRITE_ROLE)
        argv = TD._journal_codex_run_for_engine_files(
            run_dir, prompt, seat=seat, role_kind=role_kind, run_kind=run_kind)
    else:
        argv = TD._journal_cursor_run_for_engine_files(
            run_dir, prompt, seat=TD._reviewer_cursor_seat(), role_kind=role_kind, run_kind=run_kind)
    if watchdog is not _ABSENT:
        records, _ = ED._journal_read(run_dir)
        opened = [r for r in records if r.get("kind") == "run-opened"][-1]
        ED._journal_append(run_dir, dict(opened, silenceWatchdogSeconds=watchdog))
    for att in attempts:
        if att != 1:
            ED._journal_append(run_dir, {
                "kind": "engine-launching", "attempt": att, "childPid": 1, "at": time.time()})
    return run_dir, prompt, argv


def _run_attempt(run_dir, prompt, argv, attempt, timeout):
    ED._run_engine_files(
        run_dir, attempt, argv, run_dir, prompt,
        os.path.join(run_dir, "attempt-%d.stdout" % attempt),
        os.path.join(run_dir, "attempt-%d.stderr" % attempt),
        timeout, os.path.join(run_dir, "progress.jsonl"))
    return _ended(run_dir, attempt)


def _ended(run_dir, attempt):
    records, _ = ED._journal_read(run_dir)
    found = [r for r in records if r.get("kind") == "attempt-ended" and r.get("attempt") == attempt]
    assert found, "no attempt-ended for attempt %d: %r" % (attempt, [r.get("kind") for r in records])
    return found[-1]


def _state(run_dir):
    records, _ = ED._journal_read(run_dir)
    return ED._journal_state(records)


@pytest.fixture(autouse=True)
def _fast_beat(monkeypatch, tmp_path):
    monkeypatch.setattr(ED, "HEARTBEAT_INTERVAL", 0.05)
    journal_root = str(tmp_path / "journal-root")
    os.makedirs(journal_root, exist_ok=True)
    monkeypatch.setenv(ED.JOURNAL_ROOT_ENV, journal_root)
    # Keep sanitized views off the real system temp directory (as test_engine_dispatch.py's pin does).
    base = str(tmp_path / "sanitized-temp-base")
    os.makedirs(base, exist_ok=True)
    monkeypatch.setattr(TD._SV_MOD.tempfile, "gettempdir", lambda: base)
    monkeypatch.setattr(ED.tempfile, "gettempdir", lambda: base)


def _assert_not_watchdog(ended):
    assert "silenceWatchdog" not in ended
    assert ended["signalSource"] != "silence-watchdog"


def _assert_bound_end(ended):
    _assert_not_watchdog(ended)
    assert ended["timedOut"] is True
    assert ended["signalSource"] == "runner-timeout"


# --- the DoD tests -----------------------------------------------------------------------------------


def test_a_silent_attempt_with_no_command_is_ended_and_graded_a_forfeit(tmp_path, monkeypatch):
    """DoD (a): silent, no command in flight, past the threshold -> ended, journaled, forfeit."""
    run_dir, prompt, argv = _open_run(tmp_path)
    TD._install_fake_codex(monkeypatch, tmp_path, _SILENT)
    _Clock(monkeypatch)
    ended = _run_attempt(run_dir, prompt, argv, 1, 60)
    assert ended["signalSource"] == "silence-watchdog"
    assert ended["timedOut"] is False
    assert ended["silenceWatchdog"]["silentSeconds"] >= _THRESHOLD
    assert ended["silenceWatchdog"]["thresholdSeconds"] == _THRESHOLD
    assert ED._attempt_ended_successfully(ended) is False
    grade = ED._grade_review_attempt(run_dir, _state(run_dir), 1)
    assert grade == {"forfeit": True, "reason": ED.dispatch_outcome.REASON_FORFEITED,
                     "detail": "silence-watchdog"}


@pytest.mark.parametrize("completed", [False, True])
def test_b_w3_command_in_flight_is_never_silence(tmp_path, monkeypatch, completed):
    """DoD (b) and W3: an item.started with no completion keeps the attempt alive until the bound.
    The completed control shows the same stream IS silence once the command has closed."""
    run_dir, prompt, argv = _open_run(tmp_path)
    TD._install_fake_codex(monkeypatch, tmp_path, _command_script(completed))
    stdout_path = os.path.join(run_dir, "attempt-1.stdout")

    def gate(tick):
        if tick == 0:
            _wait_for(_nonempty(stdout_path), "fake engine stdout")

    _Clock(monkeypatch, before_tick=gate)
    ended = _run_attempt(run_dir, prompt, argv, 1, 2.0)
    if completed:
        assert ended["signalSource"] == "silence-watchdog"
        assert ended["timedOut"] is False
    else:
        _assert_bound_end(ended)


def test_c_retried_attempt_that_answers_is_accepted(tmp_path, monkeypatch):
    """DoD (c): attempt 1 is ended by the watchdog (forfeit); attempt 2 answers and is accepted."""
    run_dir, prompt, argv = _open_run(tmp_path, attempts=(1, 2))
    TD._install_fake_codex(monkeypatch, tmp_path, _SILENT_THEN_ANSWER)
    _Clock(monkeypatch)
    first = _run_attempt(run_dir, prompt, argv, 1, 60)
    assert first["signalSource"] == "silence-watchdog"
    second = _run_attempt(run_dir, prompt, argv, 2, 60)
    assert second["exit"] == 0 and second["timedOut"] is False
    _assert_not_watchdog(second)
    state = _state(run_dir)
    assert ED._grade_review_attempt(run_dir, state, 1)["detail"] == "silence-watchdog"
    assert ED._attempt_ended_successfully(second) is True
    grade = ED._grade_review_attempt(run_dir, state, 2)
    assert not grade.get("forfeit"), grade
    assert grade.get("ok") is True, grade


def test_d_bound_still_ends_an_attempt_that_never_answers(tmp_path, monkeypatch):
    """DoD (d) and W6: on the final attempt (attempt 3, after two watchdog-cut attempts) the watchdog is
    never armed even when silent, so the per-attempt bound ends it. Attempts 1 and 2 are the control: the
    same silence is ended by the watchdog on each (a retry after a cut is watched too)."""
    run_dir, prompt, argv = _open_run(tmp_path, attempts=(1, 2, 3))
    TD._install_fake_codex(monkeypatch, tmp_path, _SILENT)
    _Clock(monkeypatch)
    assert ED.MAX_ATTEMPTS == 2
    control = _run_attempt(run_dir, prompt, argv, 1, 60)
    assert control["signalSource"] == "silence-watchdog"
    retry = _run_attempt(run_dir, prompt, argv, 2, 60)
    assert retry["signalSource"] == "silence-watchdog"
    final = _run_attempt(run_dir, prompt, argv, ED.MAX_ATTEMPTS + 1, 1.0)
    _assert_bound_end(final)


# --- the fail-closed edges -----------------------------------------------------------------------------


def test_w1_natural_exit_on_the_due_tick_is_admitted(tmp_path, monkeypatch):
    """W1: the watchdog becomes due on the same tick poll() reports the natural exit -> admitted."""
    run_dir, prompt, argv = _open_run(tmp_path)
    TD._install_fake_codex(monkeypatch, tmp_path, _ANSWER)
    _gate_engine_poll(monkeypatch, 3)  # poll #3 is iteration 2: silent_s reaches 0.5 >= 0.3 there
    _Clock(monkeypatch)
    ended = _run_attempt(run_dir, prompt, argv, 1, 60)
    assert ended["exit"] == 0
    assert ended["timedOut"] is False
    assert ended["signalSource"] is None
    assert "silenceWatchdog" not in ended


@pytest.mark.parametrize("timeout,watchdog_ends_it", [(0.5, False), (0.75, True)])
def test_w2_timeout_on_the_due_tick_wins(tmp_path, monkeypatch, timeout, watchdog_ends_it):
    """W2: the watchdog becomes due on iteration 2 (0.5 s). A bound of 0.5 s fires on that same tick and
    wins; with a bound of 0.75 s (control) nothing outranks the watchdog and it ends the attempt."""
    run_dir, prompt, argv = _open_run(tmp_path)
    TD._install_fake_codex(monkeypatch, tmp_path, _SILENT)
    _Clock(monkeypatch)
    ended = _run_attempt(run_dir, prompt, argv, 1, timeout)
    if watchdog_ends_it:
        assert ended["signalSource"] == "silence-watchdog"
        assert ended["timedOut"] is False
    else:
        _assert_bound_end(ended)


def test_w4_stderr_only_growth_resets_the_silence(tmp_path, monkeypatch):
    """W4: stderr grows on every other beat and stdout never does. Single silent beats (0.25 s) never
    reach 0.3 s because each growth beat resets the count; without the reset they would add up."""
    run_dir, prompt, argv = _open_run(tmp_path)
    TD._install_fake_codex(monkeypatch, tmp_path, _SILENT)
    stderr_path = os.path.join(run_dir, "attempt-1.stderr")

    def grow_stderr_on_odd_ticks(tick):
        if tick % 2 == 1:
            with open(stderr_path, "ab") as fh:
                fh.write(b"x")

    _Clock(monkeypatch, before_tick=grow_stderr_on_odd_ticks)
    ended = _run_attempt(run_dir, prompt, argv, 1, 2.0)
    _assert_bound_end(ended)


@pytest.mark.parametrize("unreadable", [False, True])
def test_w5_unreadable_stdout_increment_never_ends_the_attempt(tmp_path, monkeypatch, unreadable):
    """W5: read_increment -> (None, offset) makes the beat unknown. The unpatched control, same stream,
    is idle and silent and IS ended."""
    run_dir, prompt, argv = _open_run(tmp_path)
    TD._install_fake_codex(monkeypatch, tmp_path, _TURN)
    stdout_path = os.path.join(run_dir, "attempt-1.stdout")
    if unreadable:
        monkeypatch.setattr(CS, "read_increment", lambda path, offset, max_bytes=0: (None, offset))

    def gate(tick):
        if tick == 0:
            _wait_for(_nonempty(stdout_path), "fake engine stdout")

    _Clock(monkeypatch, before_tick=gate)
    ended = _run_attempt(run_dir, prompt, argv, 1, 2.0)
    if unreadable:
        _assert_bound_end(ended)
    else:
        assert ended["signalSource"] == "silence-watchdog"


@pytest.mark.parametrize("value", [
    _ABSENT, None, 0, 0.0, -1, True, False, "390", float("nan"), float("inf")])
def test_w7_silence_watchdog_seconds_not_a_positive_finite_number_is_off(tmp_path, monkeypatch, value):
    """W7: every unusable silenceWatchdogSeconds leaves the watchdog off; the bound ends the attempt."""
    run_dir, prompt, argv = _open_run(tmp_path, watchdog=value)
    TD._install_fake_codex(monkeypatch, tmp_path, _SILENT)
    _Clock(monkeypatch)
    ended = _run_attempt(run_dir, prompt, argv, 1, 1.0)
    _assert_bound_end(ended)


def test_w7_threshold_reader_accepts_only_real_positive_finite_numbers():
    opened = {"engine": "codex", "runKind": ED.RUN_KIND_REVIEW}
    for good in (1, 0.3, 390, 1e9):
        assert ED._silence_watchdog_threshold(dict(opened, silenceWatchdogSeconds=good), 1) == good
    for bad in (_ABSENT, None, 0, -1, True, False, "390", float("nan"), float("inf"), [], {}):
        rec = dict(opened) if bad is _ABSENT else dict(opened, silenceWatchdogSeconds=bad)
        assert ED._silence_watchdog_threshold(rec, 1) is None


@pytest.mark.parametrize("kind", ["write-run", "non-codex-review-run"])
def test_w8_write_run_and_non_codex_review_run_are_never_armed(tmp_path, monkeypatch, kind):
    """W8: a codex write run and a cursor review run, both silent with a valid threshold, run to the bound."""
    if kind == "write-run":
        run_dir, prompt, argv = _open_run(tmp_path, run_kind=ED.RUN_KIND_WRITE)
        TD._install_fake_codex(monkeypatch, tmp_path, _SILENT)
    else:
        run_dir, prompt, argv = _open_run(tmp_path, engine="cursor")
        TD._install_fake_cursor(monkeypatch, tmp_path, _SILENT)
    _Clock(monkeypatch)
    ended = _run_attempt(run_dir, prompt, argv, 1, 1.0)
    _assert_bound_end(ended)


@pytest.mark.parametrize("site", ["read_increment", "silent_and_idle"])
def test_w9_exception_in_the_armed_block_disarms_the_watchdog(tmp_path, monkeypatch, site):
    """W9: any exception inside the armed block disarms it for the rest of the attempt. The failure is
    transient: the stub raises on its first call only and delegates every later call to the real function.
    The stream is output then silence with no command in flight, so after that one failure every later
    beat is silent and idle and, were the watchdog still armed, would pass the threshold well before the
    bound. The attempt still runs to its bound, and the stub is never entered again."""
    run_dir, prompt, argv = _open_run(tmp_path)
    TD._install_fake_codex(monkeypatch, tmp_path, _TURN)
    stdout_path = os.path.join(run_dir, "attempt-1.stdout")
    real = getattr(CS, site)
    calls = []

    def fail_once_then_real(*args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            raise RuntimeError("injected")
        return real(*args, **kwargs)

    monkeypatch.setattr(CS, site, fail_once_then_real)

    def gate(tick):
        if tick == 0:
            _wait_for(_nonempty(stdout_path), "fake engine stdout")

    _Clock(monkeypatch, before_tick=gate)
    ended = _run_attempt(run_dir, prompt, argv, 1, 2.0)
    _assert_bound_end(ended)
    # the disarm means no later beat re-enters the armed block
    assert len(calls) == 1


# --- W10 and every reader of a watchdog end ----------------------------------------------------------


def _watchdog_end_with_native_result(tmp_path, monkeypatch):
    """A real watchdog end whose process wrote a valid native result on SIGTERM and exited 0."""
    run_dir, prompt, argv = _open_run(tmp_path)
    ready = str(tmp_path / "handler-ready")
    TD._install_fake_codex(monkeypatch, tmp_path, _sigterm_answer_script(ready))

    def gate(tick):
        if tick == 0:
            _wait_for(lambda: os.path.exists(ready), "SIGTERM handler installed")

    _Clock(monkeypatch, before_tick=gate)
    ended = _run_attempt(run_dir, prompt, argv, 1, 60)
    assert ended["signalSource"] == "silence-watchdog"
    # the premise of W10: every other field of this end reads as a clean completion
    assert ended["exit"] == 0 and ended["timedOut"] is False and ended["refusal"] is None
    assert os.path.getsize(ED._native_result_path(run_dir, 1)) > 0
    return run_dir


def _strip_watchdog_marker(run_dir):
    """Rewrite the journal so the attempt-ended record no longer carries the watchdog marker."""
    path = ED._journal_path(run_dir)
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("kind") == "attempt-ended":
                rec.pop("silenceWatchdog", None)
                rec["signalSource"] = None
            out.append(json.dumps(rec, separators=(",", ":")))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")


def test_w10_watchdog_end_with_valid_result_and_exit_zero_is_never_clean(tmp_path, monkeypatch):
    run_dir = _watchdog_end_with_native_result(tmp_path, monkeypatch)
    state = _state(run_dir)
    ended = state["attempts"][1]["ended"]
    # E5: the kill moment is recorded on a forfeit, and a result written only on SIGTERM is no race
    assert isinstance(ended["silenceWatchdog"]["killAt"], float) and ended["silenceWatchdog"]["killAt"] > 0
    assert "silenceWatchdogRace" not in ended
    assert ED._grade_review_attempt(run_dir, state, 1) == {
        "forfeit": True, "reason": ED.dispatch_outcome.REASON_FORFEITED, "detail": "silence-watchdog"}
    assert ED._attempt_ended_successfully(ended) is False
    assert ED.run_execution_record(run_dir) == (None, "attempt-not-completed")
    assert ED._load_native_result_json(run_dir, 1, state["opened"]) == (
        None, ED.engine_result_channel.REFUSAL_RESULT_COMPLETION_UNRECORDED)
    # control: the very same end without its marker is a clean completion with an admissible result
    _strip_watchdog_marker(run_dir)
    state = _state(run_dir)
    assert ED._attempt_ended_successfully(state["attempts"][1]["ended"]) is True
    obj, detail = ED._load_native_result_json(run_dir, 1, state["opened"])
    assert detail is None and obj is not None


def test_parse_review_attempt_refuses_a_watchdog_end_even_when_admission_would_accept(
        tmp_path, monkeypatch):
    """The parse refusal is shadowed downstream by _load_native_result_json's, so admission is stubbed
    to accept; the control (marker stripped) then parses, the marked end does not."""
    run_dir = _watchdog_end_with_native_result(tmp_path, monkeypatch)
    admitted = {"ok": True, "resultKind": "findings", "findings": [{"id": "f1"}]}
    monkeypatch.setattr(ED, "_admit_native_review_result", lambda *args, **kwargs: dict(admitted))
    assert ED._parse_review_attempt(run_dir, _state(run_dir), 1) is None
    _strip_watchdog_marker(run_dir)
    parsed = ED._parse_review_attempt(run_dir, _state(run_dir), 1)
    assert parsed is not None and parsed["ok"] is True


@pytest.mark.parametrize("ended,expected", [
    ({"signalSource": "silence-watchdog"}, True),
    ({"silenceWatchdog": {"silentSeconds": 1, "thresholdSeconds": 1}}, True),
    ({"silenceWatchdog": "malformed"}, True),
    ({"exit": 0, "timedOut": False, "signalSource": None}, False),
    ({"signalSource": "runner-timeout"}, False),
    ({}, False), (None, False), ("silence-watchdog", False),
])
def test_silence_watchdog_end_is_the_one_test(ended, expected):
    assert ED._silence_watchdog_end(ended) is expected


def test_conformance_probe_reads_a_watchdog_end_as_no_response_within_wait():
    probe = _spec_module("conformance_probe")
    terminal = {"terminal": True, "ok": True, "resultKind": "findings", "findings": [{"id": "f1"}],
                "engagement": {}, "runDir": ""}
    clean = {"attempt": 1, "exit": 0, "timedOut": False, "refusal": None}

    def completion_leg(ended):
        return probe._grade_legs(terminal, {"attempts": {1: {"ended": ended}}}, False)["completionDetection"]

    assert completion_leg(clean)["ok"] is True
    marked = dict(clean, signalSource="silence-watchdog",
                  silenceWatchdog={"silentSeconds": 400.0, "thresholdSeconds": 390})
    leg = completion_leg(marked)
    assert leg["ok"] is False
    assert leg["detail"] == "no-response-within-wait"
    assert leg["evidence"] == {"silenceWatchdog": True}


# --- the open-time record and the read-only projection -----------------------------------------------


def test_run_opened_records_the_threshold_read_at_open_time(tmp_path, monkeypatch):
    monkeypatch.setattr(ED, "CODEX_SILENCE_WATCHDOG_SECONDS", 123)
    repo_root = TD._git_init(str(tmp_path / "repo"))
    run_dir = str(tmp_path / "opened-run")
    TD._manual_open_review_run_git(tmp_path, run_dir, repo_root)
    assert _state(run_dir)["opened"]["silenceWatchdogSeconds"] == 123


def test_default_threshold_constant():
    assert ED.CODEX_SILENCE_WATCHDOG_SECONDS == 390


def _append_end(run_dir, attempt, **extra):
    ED._journal_append(run_dir, dict(
        {"kind": "attempt-ended", "attempt": attempt, "exit": 0, "timedOut": False, "refusal": None,
         "at": time.time()}, **extra))


def test_silence_watchdog_ends_projection(tmp_path):
    run_dir, _prompt, _argv = _open_run(tmp_path, attempts=(1, 2))
    _append_end(run_dir, 2, signalSource="silence-watchdog",
                silenceWatchdog={"silentSeconds": 400.5, "thresholdSeconds": 390})
    with open(ED._journal_path(run_dir), "rb") as fh:
        before = fh.read()
    ends, error = ED.silence_watchdog_ends(run_dir)
    assert error is None
    assert ends == [{"attempt": 2, "silentSeconds": 400.5, "thresholdSeconds": 390, "role": TD._REVIEW_ROLE}]
    with open(ED._journal_path(run_dir), "rb") as fh:
        assert fh.read() == before


def test_silence_watchdog_ends_projection_skips_malformed_and_keeps_attempt_order(tmp_path):
    run_dir, _prompt, _argv = _open_run(tmp_path, attempts=(1, 2, 3, 4))
    good = {"silentSeconds": 1.5, "thresholdSeconds": 1}
    _append_end(run_dir, 3, silenceWatchdog=good)
    _append_end(run_dir, 1, silenceWatchdog=good)
    _append_end(run_dir, 2, silenceWatchdog={"silentSeconds": True, "thresholdSeconds": 1})
    _append_end(run_dir, 4, silenceWatchdog={"silentSeconds": "9", "thresholdSeconds": 1})
    ends, error = ED.silence_watchdog_ends(run_dir)
    assert error is None
    assert [e["attempt"] for e in ends] == [1, 3]


def test_silence_watchdog_ends_projection_is_empty_for_runs_that_are_not_codex_review(tmp_path):
    good = {"silentSeconds": 1.5, "thresholdSeconds": 1}
    write_dir, _p, _a = _open_run(tmp_path, name="write", run_kind=ED.RUN_KIND_WRITE)
    _append_end(write_dir, 1, silenceWatchdog=good)
    assert ED.silence_watchdog_ends(write_dir) == ([], None)
    cursor_dir, _p, _a = _open_run(tmp_path, name="cursor", engine="cursor")
    _append_end(cursor_dir, 1, silenceWatchdog=good)
    assert ED.silence_watchdog_ends(cursor_dir) == ([], None)


def test_silence_watchdog_ends_projection_never_raises(tmp_path):
    ends, error = ED.silence_watchdog_ends(str(tmp_path / "missing"))
    assert ends == [] and error
    assert ED.silence_watchdog_ends(None)[0] == []
    empty = tmp_path / "empty"
    empty.mkdir()
    assert ED.silence_watchdog_ends(str(empty)) == ([], None)


# --- the kill race (#2375 vet 837): a watchdog end never discards an answer produced before the kill ---
#
# Pinned condition (stated here, at the pin): the same fake clock as above, plus a hook on
# CS.silent_and_idle that runs a fixture action on the beat that brings the silence to the threshold
# (after that beat's poll and size reads, before the watchdog decides). Production timing the pin makes
# unobservable: the real window between the beat's poll and the kill is microseconds wide, so the real
# race is rare; the hook makes it deterministic. Every real-time wait below is bounded.


def _hook_decisive_beat(monkeypatch, action):
    """Wrap CS.silent_and_idle: on the first silent beat that reaches the threshold, run action() once
    and then return the real value. Returns the spy state (every call's arguments, and `done`)."""
    real = CS.silent_and_idle
    spy = {"silent": 0.0, "done": False, "calls": []}

    def wrapped(out_grew, err_grew, tracker_state):
        value = real(out_grew, err_grew, tracker_state)
        spy["calls"].append((out_grew, err_grew, tracker_state))
        if not value:
            spy["silent"] = 0.0
        elif not spy["done"]:
            spy["silent"] += _TICK
            if spy["silent"] >= _THRESHOLD:
                spy["done"] = True
                action()
        return value

    monkeypatch.setattr(CS, "silent_and_idle", wrapped)
    return spy


def _gate_stdout(run_dir):
    stdout_path = os.path.join(run_dir, "attempt-1.stdout")

    def gate(tick):
        if tick == 0:
            _wait_for(_nonempty(stdout_path), "fake engine stdout")

    return gate


def _touch(path):
    open(path, "w").close()


def _release_script(release, done, announce):
    """vet 837's engine: turn.started, then blocked until `release` exists, then the native result, an
    optional turn.completed, a marker written just before exit 0."""
    return _PRELUDE + (
        "sys.stdout.write('{\"type\":\"turn.started\"}\\n'); sys.stdout.flush()\n"
        "while not os.path.exists(%r):\n    time.sleep(0.02)\n"
        "open(_out, 'w').write(_RESULT)\n" % release
        + ("sys.stdout.write('{\"type\":\"turn.completed\"}\\n'); sys.stdout.flush()\n" if announce else "")
        + "open(%r, 'w').close()\nsys.exit(0)\n" % done)


def _answer_then_silent_script(release, wrote, on_sigterm):
    """turn.started, then (once `release` exists) the native result and a marker, then silence until
    killed. on_sigterm: 'default' dies of SIGTERM, 'exit0' exits 0, 'rewrite' writes a different result
    and exits 0."""
    handler = {
        "default": "",
        "exit0": "signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(0))\n",
        "rewrite": ("def _h(signum, frame):\n    with open(_out, 'w') as fh:\n        fh.write(%r)\n"
                    "    sys.exit(0)\nsignal.signal(signal.SIGTERM, _h)\n")
        % _result_json("rewritten after the kill"),
    }[on_sigterm]
    return _PRELUDE + handler + (
        "sys.stdout.write('{\"type\":\"turn.started\"}\\n'); sys.stdout.flush()\n"
        "while not os.path.exists(%r):\n    time.sleep(0.02)\n"
        "open(_out, 'w').write(_RESULT)\nopen(%r, 'w').close()\ntime.sleep(20)\n" % (release, wrote))


def _assert_graded_answered(run_dir):
    state = _state(run_dir)
    assert ED._attempt_ended_successfully(state["attempts"][1]["ended"]) is True
    grade = ED._grade_review_attempt(run_dir, state, 1)
    assert not grade.get("forfeit"), grade
    assert grade.get("ok") is True, grade


def _assert_watchdog_forfeit(run_dir, ended):
    assert ended["signalSource"] == "silence-watchdog"
    assert isinstance(ended["silenceWatchdog"]["killAt"], float)
    assert "silenceWatchdogRace" not in ended
    state = _state(run_dir)
    assert ED._attempt_ended_successfully(ended) is False
    assert ED._grade_review_attempt(run_dir, state, 1) == {
        "forfeit": True, "reason": ED.dispatch_outcome.REASON_FORFEITED, "detail": "silence-watchdog"}


def _answer_before_kill_run(tmp_path, monkeypatch, on_sigterm):
    """The engine writes its native result on the deciding beat (after the beat's size reads, so no
    stream grows), stays silent, and meets the watchdog's SIGTERM as `on_sigterm` says."""
    run_dir, prompt, argv = _open_run(tmp_path)
    release, wrote = str(tmp_path / "release"), str(tmp_path / "wrote")
    TD._install_fake_codex(monkeypatch, tmp_path, _answer_then_silent_script(release, wrote, on_sigterm))

    def engine_answers():
        _touch(release)
        _wait_for(lambda: os.path.exists(wrote), "fake engine wrote its result")
        time.sleep(0.2)  # real time: the result file is closed and visible

    spy = _hook_decisive_beat(monkeypatch, engine_answers)
    _Clock(monkeypatch, before_tick=_gate_stdout(run_dir))
    ended = _run_attempt(run_dir, prompt, argv, 1, 60)
    assert spy["done"], "the deciding beat never ran"
    assert ended["exit"] == 0 or on_sigterm == "default"
    return run_dir, ended


@pytest.mark.parametrize("announce", [True, False])
def test_e1_engine_exiting_after_the_deciding_polls_is_a_natural_exit(tmp_path, monkeypatch, announce):
    """E1 (vet 837): the engine answers and exits 0 after the beat's poll and size reads, before the kill.
    announce=True is vet 837's shape (it also prints turn.completed); announce=False leaves no stream
    growth, so only the re-poll can see the exit. A natural exit: no watchdog key of any kind."""
    run_dir, prompt, argv = _open_run(tmp_path)
    release, done = str(tmp_path / "release"), str(tmp_path / "done")
    TD._install_fake_codex(monkeypatch, tmp_path, _release_script(release, done, announce))

    def engine_exits():
        _touch(release)
        _wait_for(lambda: os.path.exists(done), "fake engine exit marker")
        time.sleep(0.5)  # real time: the process is gone, so the next poll() reports its exit

    spy = _hook_decisive_beat(monkeypatch, engine_exits)
    _Clock(monkeypatch, before_tick=_gate_stdout(run_dir))
    ended = _run_attempt(run_dir, prompt, argv, 1, 60)
    assert spy["done"], "the deciding beat never ran"
    assert ended["exit"] == 0 and ended["timedOut"] is False
    _assert_not_watchdog(ended)
    assert ended["signalSource"] is None
    assert "silenceWatchdogRace" not in ended
    assert os.path.getsize(ED._native_result_path(run_dir, 1)) > 0
    _assert_graded_answered(run_dir)


def test_e4_answer_written_before_the_kill_survives_an_exit_zero_on_sigterm(tmp_path, monkeypatch):
    """E4: result on disk (seen only once) before the kill, engine silent, exits 0 on SIGTERM -> a race
    record, no silenceWatchdog, graded answered."""
    run_dir, ended = _answer_before_kill_run(tmp_path, monkeypatch, "exit0")
    assert "silenceWatchdog" not in ended
    assert ended["signalSource"] is None
    assert ED._silence_watchdog_end(ended) is False
    race = ended["silenceWatchdogRace"]
    assert race["silentSeconds"] >= _THRESHOLD and race["thresholdSeconds"] == _THRESHOLD
    assert isinstance(race["killAt"], float)
    _assert_graded_answered(run_dir)


def test_e6_answer_before_the_kill_but_the_engine_dies_of_sigterm_is_still_a_forfeit(tmp_path, monkeypatch):
    """E6: the same answer-before-kill, but the engine dies of SIGTERM (non-zero exit) -> watchdog forfeit."""
    run_dir, ended = _answer_before_kill_run(tmp_path, monkeypatch, "default")
    assert ended["exit"] != 0
    _assert_watchdog_forfeit(run_dir, ended)


def test_r5_content_first_seen_after_the_kill_never_replaces_the_pre_kill_stamp(tmp_path, monkeypatch):
    """R5: the engine answers before the kill, then rewrites a different result on SIGTERM and exits 0.
    The held stamp stays the pre-kill content's digest, so the race record stands."""
    run_dir, ended = _answer_before_kill_run(tmp_path, monkeypatch, "rewrite")
    pre = ED.engine_result_channel.canonical_payload_digest(ED._scrub_native_payload(json.loads(_result_json())))
    post = ED.engine_result_channel.canonical_payload_digest(
        ED._scrub_native_payload(json.loads(_result_json("rewritten after the kill"))))
    assert pre != post
    assert ended[ED.engine_result_channel.FIELD_RESULT_COMPLETE_SHA256] == pre
    assert "silenceWatchdogRace" in ended and "silenceWatchdog" not in ended


def _recheck_run(tmp_path, monkeypatch, disturb):
    """A silent attempt whose deciding beat is disturbed before the watchdog's re-check. Returns
    (ended, ticks at the deciding beat, ticks when the kill began). The kill's own grace sleeps tick the
    fake clock, so the tick count is read at the kill, not at the end."""
    run_dir, prompt, argv = _open_run(tmp_path)
    TD._install_fake_codex(monkeypatch, tmp_path, _TURN)
    seen = {}
    clock_box = {}
    real_terminate = ED._terminate_process_group

    def action():
        seen["ticks"] = clock_box["clock"].ticks
        disturb(run_dir)

    def terminate(pgid):
        seen["kill_ticks"] = clock_box["clock"].ticks
        real_terminate(pgid)

    monkeypatch.setattr(ED, "_terminate_process_group", terminate)
    _hook_decisive_beat(monkeypatch, action)
    clock_box["clock"] = _Clock(monkeypatch, before_tick=_gate_stdout(run_dir))
    ended = _run_attempt(run_dir, prompt, argv, 1, 60)
    assert "ticks" in seen, "the deciding beat never ran"
    return ended, seen["ticks"], seen["kill_ticks"]


def test_e2_stream_growth_between_the_deciding_beat_and_the_recheck_resets_the_silence(tmp_path, monkeypatch):
    """E2: stderr grows after the beat's size reads. The attempt is not ended on that tick; the silence
    restarts and the (still silent) engine is ended by the watchdog only later."""
    def grow(run_dir):
        with open(os.path.join(run_dir, "attempt-1.stderr"), "ab") as fh:
            fh.write(b"x")

    ended, decisive_ticks, end_ticks = _recheck_run(tmp_path, monkeypatch, grow)
    assert end_ticks > decisive_ticks
    assert ended["signalSource"] == "silence-watchdog"
    assert ended["silenceWatchdog"]["silentSeconds"] >= _THRESHOLD


def test_e3_unreadable_size_at_the_recheck_does_not_fire(tmp_path, monkeypatch):
    """E3: the first size read of the re-check fails (None). Not fired on that tick."""
    state = {"armed": False}
    real = ED._size_or_none

    def flaky(path):
        if state["armed"]:
            state["armed"] = False
            return None
        return real(path)

    monkeypatch.setattr(ED, "_size_or_none", flaky)
    ended, decisive_ticks, end_ticks = _recheck_run(
        tmp_path, monkeypatch, lambda run_dir: state.update(armed=True))
    assert state["armed"] is False, "the re-check never read a size"
    assert end_ticks > decisive_ticks
    assert ended["signalSource"] == "silence-watchdog"


def test_e7_unreadable_stderr_size_never_counts_as_silence(tmp_path, monkeypatch):
    """V837-b: os.path.getsize fails for the stderr path on every call. Every beat hands the predicate an
    unknown stderr growth (None, never False) and the attempt runs to its bound."""
    run_dir, prompt, argv = _open_run(tmp_path)
    TD._install_fake_codex(monkeypatch, tmp_path, _TURN)
    stderr_path = os.path.join(run_dir, "attempt-1.stderr")
    real_getsize = os.path.getsize

    def getsize(path, *args, **kwargs):
        if os.fspath(path) == stderr_path:
            raise OSError("injected: stderr size unreadable")
        return real_getsize(path, *args, **kwargs)

    monkeypatch.setattr(os.path, "getsize", getsize)
    spy = _hook_decisive_beat(monkeypatch, lambda: None)
    _Clock(monkeypatch, before_tick=_gate_stdout(run_dir))
    ended = _run_attempt(run_dir, prompt, argv, 1, 2.0)
    _assert_bound_end(ended)
    assert spy["calls"], "no beat reached the predicate"
    assert all(err_grew is None for _out, err_grew, _state_ in spy["calls"]), spy["calls"]
