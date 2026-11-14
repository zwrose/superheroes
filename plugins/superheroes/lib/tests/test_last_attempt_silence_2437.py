"""#2437: a codex review seat's last attempt gets its own silence limit.

The threshold for an attempt is read only from the run's own `run-opened` record, through
ED._silence_watchdog_threshold: an attempt below MAX_ATTEMPTS reads `silenceWatchdogSeconds`, the last
attempt reads `lastAttemptSilenceWatchdogSeconds`, and each arms only when it is a real, finite, positive
number. These tests reuse the fixtures of test_engine_dispatch_silence_watchdog.py (loaded by path, not
edited) and read constants and journal / dispatch results only.

Pinned condition (stated here, at the pin): ED.time is replaced for the test (one poll tick is exactly 0.25
fake seconds) and HEARTBEAT_INTERVAL is 0.05, as in the watchdog tests. Production timing the pin makes
unobservable: the real beat is 10 s and the real limits are 390 s and 1,800 s, so the real accumulation of
silence is coarser; the limits below (0.3 s and 0.6 s) are chosen so the two limits end an attempt on
different ticks (0.3 -> the second silent beat, 0.5 s; 0.6 -> the third, 0.75 s).
"""
import importlib.util
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_watchdog_tests():
    spec = importlib.util.spec_from_file_location(
        "test_engine_dispatch_silence_watchdog",
        os.path.join(_HERE, "test_engine_dispatch_silence_watchdog.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


W = _load_watchdog_tests()
TD = W.TD
ED = W.ED

_EARLIER = 0.3
_LAST = 0.6
_ABSENT = W._ABSENT


@pytest.fixture(autouse=True)
def _fast_beat(monkeypatch, tmp_path):
    # Autouse fixtures do not cross modules: the same setup as the watchdog tests' _fast_beat.
    monkeypatch.setattr(ED, "HEARTBEAT_INTERVAL", 0.05)
    journal_root = str(tmp_path / "journal-root")
    os.makedirs(journal_root, exist_ok=True)
    monkeypatch.setenv(ED.JOURNAL_ROOT_ENV, journal_root)
    # Keep sanitized views off the real system temp directory (as test_engine_dispatch.py's pin does).
    base = str(tmp_path / "sanitized-temp-base")
    os.makedirs(base, exist_ok=True)
    monkeypatch.setattr(TD._SV_MOD.tempfile, "gettempdir", lambda: base)
    monkeypatch.setattr(ED.tempfile, "gettempdir", lambda: base)


def _open_two_limit_run(tmp_path, *, name="run", earlier=_EARLIER, last=_LAST):
    """A journaled codex review run, ready for ED._run_engine_files on attempts 1 and ED.MAX_ATTEMPTS,
    whose last-journaled `run-opened` record carries exactly the limits given. `_ABSENT` leaves a key out
    of that record (the base fixture's own record carries neither key, but the key is removed anyway so
    the record really has no such key)."""
    run_dir, prompt, argv = W._open_run(
        tmp_path, name=name, watchdog=W._ABSENT, attempts=tuple(range(1, ED.MAX_ATTEMPTS + 1)))
    records, _ = ED._journal_read(run_dir)
    opened = dict([r for r in records if r.get("kind") == "run-opened"][-1])
    opened.pop("silenceWatchdogSeconds", None)
    opened.pop("lastAttemptSilenceWatchdogSeconds", None)
    if earlier is not _ABSENT:
        opened["silenceWatchdogSeconds"] = earlier
    if last is not _ABSENT:
        opened["lastAttemptSilenceWatchdogSeconds"] = last
    ED._journal_append(run_dir, opened)
    return run_dir, prompt, argv


# --- L1 -----------------------------------------------------------------------------------------------


def test_l1_a_silent_last_attempt_is_ended_as_a_silence_stop(tmp_path, monkeypatch):
    run_dir, prompt, argv = _open_two_limit_run(tmp_path)
    TD._install_fake_codex(monkeypatch, tmp_path, W._SILENT)
    W._Clock(monkeypatch)
    ended = W._run_attempt(run_dir, prompt, argv, ED.MAX_ATTEMPTS, 60)
    assert ended["signalSource"] == "silence-watchdog"
    assert ended["timedOut"] is False
    assert ended["silenceWatchdog"]["thresholdSeconds"] == _LAST
    assert ended["silenceWatchdog"]["silentSeconds"] >= _LAST
    assert ED._attempt_ended_successfully(ended) is False
    grade = ED._grade_review_attempt(run_dir, W._state(run_dir), ED.MAX_ATTEMPTS)
    assert grade == {"forfeit": True, "reason": ED.dispatch_outcome.REASON_FORFEITED,
                     "detail": "silence-watchdog"}
    ends, error = ED.silence_watchdog_ends(run_dir)
    assert error is None
    assert [(e["attempt"], e["thresholdSeconds"]) for e in ends] == [(ED.MAX_ATTEMPTS, _LAST)]


# --- L2 -----------------------------------------------------------------------------------------------


def test_l2_the_last_attempt_does_not_use_the_earlier_limit(tmp_path, monkeypatch):
    TD._install_fake_codex(monkeypatch, tmp_path, W._SILENT)
    first_dir, first_prompt, first_argv = _open_two_limit_run(tmp_path, name="first")
    W._Clock(monkeypatch)
    first = W._run_attempt(first_dir, first_prompt, first_argv, 1, 60)
    assert first["signalSource"] == "silence-watchdog"
    assert first["silenceWatchdog"]["thresholdSeconds"] == _EARLIER

    last_dir, last_prompt, last_argv = _open_two_limit_run(tmp_path, name="last")
    W._Clock(monkeypatch)
    last = W._run_attempt(last_dir, last_prompt, last_argv, ED.MAX_ATTEMPTS, 60)
    assert last["signalSource"] == "silence-watchdog"
    assert last["silenceWatchdog"]["thresholdSeconds"] == _LAST
    assert last["silenceWatchdog"]["silentSeconds"] >= _LAST


# --- L3 -----------------------------------------------------------------------------------------------


def test_l3_a_last_attempt_that_keeps_producing_output_is_never_cut(tmp_path, monkeypatch):
    """stderr grows on every other beat and stdout never does (the shape of the watchdog file's W4):
    single silent beats (0.25 s) never reach the 0.3 s limit, so the bound ends the attempt."""
    run_dir, prompt, argv = _open_two_limit_run(tmp_path, earlier=_ABSENT, last=0.3)
    TD._install_fake_codex(monkeypatch, tmp_path, W._SILENT)
    stderr_path = os.path.join(run_dir, "attempt-%d.stderr" % ED.MAX_ATTEMPTS)

    def grow_stderr_on_odd_ticks(tick):
        if tick % 2 == 1:
            with open(stderr_path, "ab") as fh:
                fh.write(b"x")

    W._Clock(monkeypatch, before_tick=grow_stderr_on_odd_ticks)
    ended = W._run_attempt(run_dir, prompt, argv, ED.MAX_ATTEMPTS, 2.0)
    W._assert_bound_end(ended)


# --- L4 -----------------------------------------------------------------------------------------------


def test_l4_a_run_opened_before_the_upgrade_keeps_no_limit_on_its_last_attempt(tmp_path, monkeypatch):
    run_dir, prompt, argv = _open_two_limit_run(tmp_path, earlier=_EARLIER, last=_ABSENT)
    assert "lastAttemptSilenceWatchdogSeconds" not in W._state(run_dir)["opened"]
    assert W._state(run_dir)["opened"]["silenceWatchdogSeconds"] == _EARLIER
    TD._install_fake_codex(monkeypatch, tmp_path, W._SILENT)
    W._Clock(monkeypatch)
    ended = W._run_attempt(run_dir, prompt, argv, ED.MAX_ATTEMPTS, 1.0)
    W._assert_bound_end(ended)


# --- L5 -----------------------------------------------------------------------------------------------


def _base_opened(**extra):
    return dict({"engine": "codex", "runKind": ED.RUN_KIND_REVIEW}, **extra)


def _reader(opened, attempt):
    return ED._silence_watchdog_threshold(opened, attempt)


def test_l5_an_earlier_attempt_reads_only_the_earlier_key():
    for last in (1800, 0.5, None, True, 0, -1, float("nan"), "1800", _ABSENT):
        rec = _base_opened(silenceWatchdogSeconds=390)
        if last is not _ABSENT:
            rec["lastAttemptSilenceWatchdogSeconds"] = last
        assert _reader(rec, 1) == 390
    # the earlier key absent, the last key present: an earlier attempt is not armed
    assert _reader(_base_opened(lastAttemptSilenceWatchdogSeconds=1800), 1) is None


@pytest.mark.parametrize("good", [1800, 0.5])
def test_l5_the_last_attempt_reads_the_last_key(good):
    assert _reader(_base_opened(lastAttemptSilenceWatchdogSeconds=good), ED.MAX_ATTEMPTS) == good
    assert _reader(_base_opened(silenceWatchdogSeconds=390, lastAttemptSilenceWatchdogSeconds=good),
                   ED.MAX_ATTEMPTS) == good


@pytest.mark.parametrize("bad", [
    _ABSENT, None, True, False, 0, 0.0, -1, float("nan"), float("inf"), "1800", [], {}])
def test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key(bad):
    rec = _base_opened(silenceWatchdogSeconds=390)
    if bad is not _ABSENT:
        rec["lastAttemptSilenceWatchdogSeconds"] = bad
    assert _reader(rec, ED.MAX_ATTEMPTS) is None


def test_l5_an_attempt_above_the_last_is_off():
    rec = _base_opened(silenceWatchdogSeconds=390, lastAttemptSilenceWatchdogSeconds=1800)
    assert _reader(rec, ED.MAX_ATTEMPTS + 1) is None
    assert _reader(rec, ED.MAX_ATTEMPTS + 5) is None


@pytest.mark.parametrize("opened", [
    {"engine": "codex", "runKind": ED.RUN_KIND_WRITE},
    {"engine": "cursor", "runKind": ED.RUN_KIND_REVIEW},
], ids=["write-run", "non-codex"])
def test_l5_a_write_run_and_a_non_codex_engine_are_never_armed(opened):
    rec = dict(opened, silenceWatchdogSeconds=390, lastAttemptSilenceWatchdogSeconds=1800)
    for attempt in (1, ED.MAX_ATTEMPTS, ED.MAX_ATTEMPTS + 1):
        assert _reader(rec, attempt) is None


def test_l5_the_reader_never_raises():
    assert _reader(None, ED.MAX_ATTEMPTS) is None
    assert _reader("not a record", 1) is None
    assert _reader(_base_opened(silenceWatchdogSeconds=390, lastAttemptSilenceWatchdogSeconds=1800), None) is None


# --- L6 -----------------------------------------------------------------------------------------------


def test_l6_the_constants():
    assert ED.CODEX_LAST_ATTEMPT_SILENCE_WATCHDOG_SECONDS == 1800
    assert ED.CODEX_SILENCE_WATCHDOG_SECONDS == 390
    # the longest answered silence on record (the #2439 receipt) is 1,585 s
    assert ED.CODEX_LAST_ATTEMPT_SILENCE_WATCHDOG_SECONDS > 1585


def test_l6_run_opened_records_the_last_attempt_limit_read_at_open_time(tmp_path, monkeypatch):
    monkeypatch.setattr(ED, "CODEX_LAST_ATTEMPT_SILENCE_WATCHDOG_SECONDS", 777)
    repo_root = TD._git_init(str(tmp_path / "repo"))
    run_dir = str(tmp_path / "opened-run")
    TD._manual_open_review_run_git(tmp_path, run_dir, repo_root)
    opened = W._state(run_dir)["opened"]
    assert opened["lastAttemptSilenceWatchdogSeconds"] == 777
    assert opened["silenceWatchdogSeconds"] == 390
