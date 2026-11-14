# Bite-proof record — a reviewer's last attempt gets its own silence limit (#2437, order `wo1-2437`)

Detector file: `plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py` (25 tests), unedited between each red and its green. Production file: `plugins/superheroes/lib/engine_dispatch.py`, base commit `37965f6ccb3b7692ff4ada85af4578c5de58f410` plus the uncommitted change under proof. Every neutralization is a targeted edit made and undone with the edit tool (never `git checkout --`, `git restore`, `git reset` or `git stash`). Every run is the single test file, no output filter: `scripts/pinned-python -B -m pytest plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py -q -p no:cacheprovider`. The dispatch's own runs; nothing is redacted (no secret, token, URL or personal data appears; the temp paths are the pytest `tmp_path` of the sandbox). The `UV_NATIVE_TLS` deprecation warning that opens each run is dropped from the captures below (it is the launcher's, not the detector's); every other line is as printed. `git status --porcelain` over the neutralized path reads ` M` after every restore, because the production change itself is uncommitted; the restore receipt is therefore the restored lines quoted back, and the full diff against the base was read after G5 and shows only the intended change.

## G1. The last-attempt branch of `_silence_watchdog_threshold` (`engine_dispatch.py:3795-3796`)

- **Axis:** the last attempt is armed with its own limit.
- **Neutralization:** the line `            seconds = opened.get("lastAttemptSilenceWatchdogSeconds")  # axis: the last attempt reads its own limit, never the earlier one` changed to `            return None  # G1-NEUTRALIZED` (the branch returns `None`).
- **Raw red:** `4 failed, 21 passed in 45.51s` — L1, L2, and L5 `[1800]` / `[0.5]`:

```
FF...FF..................                                                [100%]
=================================== FAILURES ===================================
___________ test_l1_a_silent_last_attempt_is_ended_as_a_silence_stop ___________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-3/test_l1_a_silent_last_attempt_0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f94d92d0ef0>

    def test_l1_a_silent_last_attempt_is_ended_as_a_silence_stop(tmp_path, monkeypatch):
        run_dir, prompt, argv = _open_two_limit_run(tmp_path)
        TD._install_fake_codex(monkeypatch, tmp_path, W._SILENT)
        W._Clock(monkeypatch)
        ended = W._run_attempt(run_dir, prompt, argv, ED.MAX_ATTEMPTS, 60)
>       assert ended["signalSource"] == "silence-watchdog"
E       AssertionError: assert None == 'silence-watchdog'

/home/user/wt-2437/plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py:82: AssertionError
___________ test_l2_the_last_attempt_does_not_use_the_earlier_limit ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-3/test_l2_the_last_attempt_does_0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f94d92d0f20>

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
>       assert last["signalSource"] == "silence-watchdog"
E       AssertionError: assert None == 'silence-watchdog'

/home/user/wt-2437/plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py:109: AssertionError
______________ test_l5_the_last_attempt_reads_the_last_key[1800] _______________

good = 1800

    @pytest.mark.parametrize("good", [1800, 0.5])
    def test_l5_the_last_attempt_reads_the_last_key(good):
>       assert _reader(_base_opened(lastAttemptSilenceWatchdogSeconds=good), ED.MAX_ATTEMPTS) == good
E       AssertionError: assert None == 1800
E        +  where None = _reader({'engine': 'codex', 'runKind': 'review', 'lastAttemptSilenceWatchdogSeconds': 1800}, 2)
E        +    where {'engine': 'codex', 'runKind': 'review', 'lastAttemptSilenceWatchdogSeconds': 1800} = _base_opened(lastAttemptSilenceWatchdogSeconds=1800)
E        +    and   2 = ED.MAX_ATTEMPTS

/home/user/wt-2437/plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py:170: AssertionError
_______________ test_l5_the_last_attempt_reads_the_last_key[0.5] _______________

good = 0.5

    @pytest.mark.parametrize("good", [1800, 0.5])
    def test_l5_the_last_attempt_reads_the_last_key(good):
>       assert _reader(_base_opened(lastAttemptSilenceWatchdogSeconds=good), ED.MAX_ATTEMPTS) == good
E       AssertionError: assert None == 0.5
E        +  where None = _reader({'engine': 'codex', 'runKind': 'review', 'lastAttemptSilenceWatchdogSeconds': 0.5}, 2)
E        +    where {'engine': 'codex', 'runKind': 'review', 'lastAttemptSilenceWatchdogSeconds': 0.5} = _base_opened(lastAttemptSilenceWatchdogSeconds=0.5)
E        +    and   2 = ED.MAX_ATTEMPTS

/home/user/wt-2437/plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py:170: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py::test_l1_a_silent_last_attempt_is_ended_as_a_silence_stop
FAILED plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py::test_l2_the_last_attempt_does_not_use_the_earlier_limit
FAILED plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py::test_l5_the_last_attempt_reads_the_last_key[1800]
FAILED plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py::test_l5_the_last_attempt_reads_the_last_key[0.5]
4 failed, 21 passed in 45.51s
```
- **Restore:** the inverse edit (`return None  # G1-NEUTRALIZED` back to the original line).
- **Restore receipt:** `engine_dispatch.py:3796` reads `            seconds = opened.get("lastAttemptSilenceWatchdogSeconds")  # axis: the last attempt reads its own limit, never the earlier one`; a search for `G1-NEUTRALIZED` finds nothing.
- **Raw green:** `.........................` / `25 passed in 6.68s`.

## G2. The key the last-attempt branch reads (`engine_dispatch.py:3796`)

- **Axis:** the last attempt reads `lastAttemptSilenceWatchdogSeconds`, never `silenceWatchdogSeconds`.
- **Neutralization:** `opened.get("lastAttemptSilenceWatchdogSeconds")` changed to `opened.get("silenceWatchdogSeconds")` on that branch.
- **Raw red:** `17 failed, 8 passed in 6.15s` — L1, L2, L4, L5 `[1800]` / `[0.5]`, and L5's unusable-last-key cases `[bad0]`, `[None]`, `[True]`, `[False]`, `[0]`, `[0.0]`, `[-1]`, `[nan]`, `[inf]`, `[1800]`, `[bad10]`, `[bad11]`. **This capture is incomplete:** the shell tool cut the middle of the output (its own marker `[8537 characters truncated]`); what follows is exactly what was returned, nothing reconstructed.

```
FF.F.FFFFFFFFFFFFFF......                                                [100%]
...
>       assert ended["silenceWatchdog"]["thresholdSeconds"] == _LAST
E       assert 0.3 == 0.6
...
>       assert last["silenceWatchdog"]["thresholdSeconds"] == _LAST
E       assert 0.3 == 0.6
...
>       W._assert_bound_end(ended)
...
    def _assert_not_watchdog(ended):
>       assert "silenceWatchdog" not in ended
E       AssertionError
(ended = {'kind': 'attempt-ended', 'attempt': 2, 'exit': -15, 'timedOut': False, ...})
...
E       AssertionError: assert None == 1800            (test_l5_the_last_attempt_reads_the_last_key[1800])
...
[8537 characters truncated by the tool]
...
E       AssertionError: assert 390 is None
E        +  where 390 = _reader({'engine': 'codex', 'runKind': 'review', 'silenceWatchdogSeconds': 390, 'lastAttemptSilenceWatchdogSeconds': '1800'}, 2)
...
E       AssertionError: assert 390 is None             ([bad10], last key [])
E       AssertionError: assert 390 is None             ([bad11], last key {})
=========================== short test summary info ============================
FAILED ...::test_l1_a_silent_last_attempt_is_ended_as_a_silence_stop
FAILED ...::test_l2_the_last_attempt_does_not_use_the_earlier_limit
FAILED ...::test_l4_a_run_opened_before_the_upgrade_keeps_no_limit_on_its_last_attempt
FAILED ...::test_l5_the_last_attempt_reads_the_last_key[1800]
FAILED ...::test_l5_the_last_attempt_reads_the_last_key[0.5]
FAILED ...::test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key[bad0]
FAILED ...[None] [True] [False] [0] [0.0] [-1] [nan] [inf] [1800] [bad10] [bad11] (same test, one line each)
17 failed, 8 passed in 6.15s
```

  (Here the `...::` prefix stands for `plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py`; the parenthesised notes and the compressed last `FAILED` line are mine, added for length and labelled; the first line, the `E` lines and the final summary line are as printed.)
- **Restore:** the inverse edit.
- **Restore receipt:** `engine_dispatch.py:3796` quoted back as in G1 (reads `lastAttemptSilenceWatchdogSeconds`).
- **Raw green:** `.........................` / `25 passed in 6.70s`.

## G3. The number check applied to the last key (`engine_dispatch.py:3795-3796`, last-attempt branch only)

- **Axis:** a bad value (bool, zero, negative, NaN, inf, string, container) leaves the last attempt off.
- **Neutralization:** two lines inserted directly after the last-attempt branch's `seconds = ...` line: `            if seconds is not None and opened.get("engine") == "codex" and opened.get("runKind") == RUN_KIND_REVIEW:  # G3-NEUTRALIZED` and `                return seconds` (the earlier-attempt branch keeps the number check).
- **Raw red:** `10 failed, 15 passed in 6.72s` — all ten in L5's unusable-last-key test: `[True]`, `[False]`, `[0]`, `[0.0]`, `[-1]`, `[nan]`, `[inf]`, `[1800]` (the string), `[bad10]` (`[]`), `[bad11]` (`{}`). Full capture as printed (the ten failures are one parametrized test; a case's own value is the `bad = ...` line):

```
.........FFFFFFFFFF......                                                [100%]
=================================== FAILURES ===================================
_ test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key[True] _

bad = True

    @pytest.mark.parametrize("bad", [
        _ABSENT, None, True, False, 0, 0.0, -1, float("nan"), float("inf"), "1800", [], {}])
    def test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key(bad):
        rec = _base_opened(silenceWatchdogSeconds=390)
        if bad is not _ABSENT:
            rec["lastAttemptSilenceWatchdogSeconds"] = bad
>       assert _reader(rec, ED.MAX_ATTEMPTS) is None
E       AssertionError: assert True is None
E        +  where True = _reader({'engine': 'codex', 'runKind': 'review', 'silenceWatchdogSeconds': 390, 'lastAttemptSilenceWatchdogSeconds': True}, 2)
E        +    where 2 = ED.MAX_ATTEMPTS

/home/user/wt-2437/plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py:181: AssertionError
_ test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key[False] _

bad = False

    @pytest.mark.parametrize("bad", [
        _ABSENT, None, True, False, 0, 0.0, -1, float("nan"), float("inf"), "1800", [], {}])
    def test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key(bad):
        rec = _base_opened(silenceWatchdogSeconds=390)
        if bad is not _ABSENT:
            rec["lastAttemptSilenceWatchdogSeconds"] = bad
>       assert _reader(rec, ED.MAX_ATTEMPTS) is None
E       AssertionError: assert False is None
E        +  where False = _reader({'engine': 'codex', 'runKind': 'review', 'silenceWatchdogSeconds': 390, 'lastAttemptSilenceWatchdogSeconds': False}, 2)
E        +    where 2 = ED.MAX_ATTEMPTS

/home/user/wt-2437/plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py:181: AssertionError
_ test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key[0] _

bad = 0

    @pytest.mark.parametrize("bad", [
        _ABSENT, None, True, False, 0, 0.0, -1, float("nan"), float("inf"), "1800", [], {}])
    def test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key(bad):
        rec = _base_opened(silenceWatchdogSeconds=390)
        if bad is not _ABSENT:
            rec["lastAttemptSilenceWatchdogSeconds"] = bad
>       assert _reader(rec, ED.MAX_ATTEMPTS) is None
E       AssertionError: assert 0 is None
E        +  where 0 = _reader({'engine': 'codex', 'runKind': 'review', 'silenceWatchdogSeconds': 390, 'lastAttemptSilenceWatchdogSeconds': 0}, 2)
E        +    where 2 = ED.MAX_ATTEMPTS

/home/user/wt-2437/plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py:181: AssertionError
_ test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key[0.0] _

bad = 0.0

    @pytest.mark.parametrize("bad", [
        _ABSENT, None, True, False, 0, 0.0, -1, float("nan"), float("inf"), "1800", [], {}])
    def test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key(bad):
        rec = _base_opened(silenceWatchdogSeconds=390)
        if bad is not _ABSENT:
            rec["lastAttemptSilenceWatchdogSeconds"] = bad
>       assert _reader(rec, ED.MAX_ATTEMPTS) is None
E       AssertionError: assert 0.0 is None
E        +  where 0.0 = _reader({'engine': 'codex', 'runKind': 'review', 'silenceWatchdogSeconds': 390, 'lastAttemptSilenceWatchdogSeconds': 0.0}, 2)
E        +    where 2 = ED.MAX_ATTEMPTS

/home/user/wt-2437/plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py:181: AssertionError
_ test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key[-1] _

bad = -1

    @pytest.mark.parametrize("bad", [
        _ABSENT, None, True, False, 0, 0.0, -1, float("nan"), float("inf"), "1800", [], {}])
    def test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key(bad):
        rec = _base_opened(silenceWatchdogSeconds=390)
        if bad is not _ABSENT:
            rec["lastAttemptSilenceWatchdogSeconds"] = bad
>       assert _reader(rec, ED.MAX_ATTEMPTS) is None
E       AssertionError: assert -1 is None
E        +  where -1 = _reader({'engine': 'codex', 'runKind': 'review', 'silenceWatchdogSeconds': 390, 'lastAttemptSilenceWatchdogSeconds': -1}, 2)
E        +    where 2 = ED.MAX_ATTEMPTS

/home/user/wt-2437/plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py:181: AssertionError
_ test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key[nan] _

bad = nan

    @pytest.mark.parametrize("bad", [
        _ABSENT, None, True, False, 0, 0.0, -1, float("nan"), float("inf"), "1800", [], {}])
    def test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key(bad):
        rec = _base_opened(silenceWatchdogSeconds=390)
        if bad is not _ABSENT:
            rec["lastAttemptSilenceWatchdogSeconds"] = bad
>       assert _reader(rec, ED.MAX_ATTEMPTS) is None
E       AssertionError: assert nan is None
E        +  where nan = _reader({'engine': 'codex', 'runKind': 'review', 'silenceWatchdogSeconds': 390, 'lastAttemptSilenceWatchdogSeconds': nan}, 2)
E        +    where 2 = ED.MAX_ATTEMPTS

/home/user/wt-2437/plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py:181: AssertionError
_ test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key[inf] _

bad = inf

    @pytest.mark.parametrize("bad", [
        _ABSENT, None, True, False, 0, 0.0, -1, float("nan"), float("inf"), "1800", [], {}])
    def test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key(bad):
        rec = _base_opened(silenceWatchdogSeconds=390)
        if bad is not _ABSENT:
            rec["lastAttemptSilenceWatchdogSeconds"] = bad
>       assert _reader(rec, ED.MAX_ATTEMPTS) is None
E       AssertionError: assert inf is None
E        +  where inf = _reader({'engine': 'codex', 'runKind': 'review', 'silenceWatchdogSeconds': 390, 'lastAttemptSilenceWatchdogSeconds': inf}, 2)
E        +    where 2 = ED.MAX_ATTEMPTS

/home/user/wt-2437/plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py:181: AssertionError
_ test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key[1800] _

bad = '1800'

    @pytest.mark.parametrize("bad", [
        _ABSENT, None, True, False, 0, 0.0, -1, float("nan"), float("inf"), "1800", [], {}])
    def test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key(bad):
        rec = _base_opened(silenceWatchdogSeconds=390)
        if bad is not _ABSENT:
            rec["lastAttemptSilenceWatchdogSeconds"] = bad
>       assert _reader(rec, ED.MAX_ATTEMPTS) is None
E       AssertionError: assert '1800' is None
E        +  where '1800' = _reader({'engine': 'codex', 'runKind': 'review', 'silenceWatchdogSeconds': 390, 'lastAttemptSilenceWatchdogSeconds': '1800'}, 2)
E        +    where 2 = ED.MAX_ATTEMPTS

/home/user/wt-2437/plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py:181: AssertionError
_ test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key[bad10] _

bad = []

    @pytest.mark.parametrize("bad", [
        _ABSENT, None, True, False, 0, 0.0, -1, float("nan"), float("inf"), "1800", [], {}])
    def test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key(bad):
        rec = _base_opened(silenceWatchdogSeconds=390)
        if bad is not _ABSENT:
            rec["lastAttemptSilenceWatchdogSeconds"] = bad
>       assert _reader(rec, ED.MAX_ATTEMPTS) is None
E       AssertionError: assert [] is None
E        +  where [] = _reader({'engine': 'codex', 'runKind': 'review', 'silenceWatchdogSeconds': 390, 'lastAttemptSilenceWatchdogSeconds': []}, 2)
E        +    where 2 = ED.MAX_ATTEMPTS

/home/user/wt-2437/plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py:181: AssertionError
_ test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key[bad11] _

bad = {}

    @pytest.mark.parametrize("bad", [
        _ABSENT, None, True, False, 0, 0.0, -1, float("nan"), float("inf"), "1800", [], {}])
    def test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key(bad):
        rec = _base_opened(silenceWatchdogSeconds=390)
        if bad is not _ABSENT:
            rec["lastAttemptSilenceWatchdogSeconds"] = bad
>       assert _reader(rec, ED.MAX_ATTEMPTS) is None
E       AssertionError: assert {} is None
E        +  where {} = _reader({'engine': 'codex', 'runKind': 'review', 'silenceWatchdogSeconds': 390, 'lastAttemptSilenceWatchdogSeconds': {}}, 2)
E        +    where 2 = ED.MAX_ATTEMPTS

/home/user/wt-2437/plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py:181: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py::test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key[True]
FAILED plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py::test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key[False]
FAILED plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py::test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key[0]
FAILED plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py::test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key[0.0]
FAILED plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py::test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key[-1]
FAILED plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py::test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key[nan]
FAILED plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py::test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key[inf]
FAILED plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py::test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key[1800]
FAILED plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py::test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key[bad10]
FAILED plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py::test_l5_the_last_attempt_is_off_for_an_unusable_last_key_even_with_an_earlier_key[bad11]
10 failed, 15 passed in 6.72s
```
- **Restore:** the inverse edit (the two inserted lines removed).
- **Restore receipt:** `engine_dispatch.py:3795-3796` reads `        elif attempt == MAX_ATTEMPTS:` then `            seconds = opened.get("lastAttemptSilenceWatchdogSeconds")  # axis: ...`, followed by `        else:`; a search for `G3-NEUTRALIZED` finds nothing.
- **Raw green:** `.........................` / `25 passed in 6.72s`.

## G4. The `run-opened` record's new key (`engine_dispatch.py:6182`, in `_open_review_run`)

- **Axis:** the limit is recorded at run open.
- **Neutralization:** `"lastAttemptSilenceWatchdogSeconds": CODEX_LAST_ATTEMPT_SILENCE_WATCHDOG_SECONDS if engine == "codex" else None,` changed to `"lastAttemptSilenceWatchdogSeconds": None if engine == "codex" else None,`.
- **Raw red:** (full capture)

```
........................F                                                [100%]
=================================== FAILURES ===================================
_____ test_l6_run_opened_records_the_last_attempt_limit_read_at_open_time ______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-9/test_l6_run_opened_records_the0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f75ef9f3dd0>

    def test_l6_run_opened_records_the_last_attempt_limit_read_at_open_time(tmp_path, monkeypatch):
        monkeypatch.setattr(ED, "CODEX_LAST_ATTEMPT_SILENCE_WATCHDOG_SECONDS", 777)
        repo_root = TD._git_init(str(tmp_path / "repo"))
        run_dir = str(tmp_path / "opened-run")
        TD._manual_open_review_run_git(tmp_path, run_dir, repo_root)
        opened = W._state(run_dir)["opened"]
>       assert opened["lastAttemptSilenceWatchdogSeconds"] == 777
E       assert None == 777

/home/user/wt-2437/plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py:222: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py::test_l6_run_opened_records_the_last_attempt_limit_read_at_open_time
1 failed, 24 passed in 6.62s
```
- **Restore:** the inverse edit.
- **Restore receipt:** `engine_dispatch.py:6182` reads `        "lastAttemptSilenceWatchdogSeconds": CODEX_LAST_ATTEMPT_SILENCE_WATCHDOG_SECONDS if engine == "codex" else None,`.
- **Raw green:** `.........................` / `25 passed in 6.79s`.

## G5. The constant's value (`engine_dispatch.py:183`)

- **Axis:** above every answered silence on record (1,585 s), with margin.
- **Neutralization:** `CODEX_LAST_ATTEMPT_SILENCE_WATCHDOG_SECONDS = 1800` changed to `... = 1500`.
- **Raw red:** (full capture)

```
.......................F.                                                [100%]
=================================== FAILURES ===================================
____________________________ test_l6_the_constants _____________________________

    def test_l6_the_constants():
>       assert ED.CODEX_LAST_ATTEMPT_SILENCE_WATCHDOG_SECONDS == 1800
E       assert 1500 == 1800
E        +  where 1500 = ED.CODEX_LAST_ATTEMPT_SILENCE_WATCHDOG_SECONDS

/home/user/wt-2437/plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py:210: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_last_attempt_silence_2437.py::test_l6_the_constants
1 failed, 24 passed in 6.80s
```

  Note on what the red discriminates: the exact-value assertion (`== 1800`) is what goes red at 1500; the second assertion in the same test (`> 1585`) would also go red at 1500 and would stay green at, say, 1700. A value moved within 1586-1799 or above 1800 is caught only by the exact-value assertion.
- **Restore:** the inverse edit.
- **Restore receipt:** `engine_dispatch.py:183` reads `CODEX_LAST_ATTEMPT_SILENCE_WATCHDOG_SECONDS = 1800`.
- **Raw green:** `.........................` / `25 passed in 6.63s`.

## Not proven here

- Non-codex review run through `_open_review_run` recording `None` for the new key (the optional L6 clause): the harness helper the order names, `TD._manual_open_review_run_git`, opens `engine="codex"` only, and the order said not to build one. Other test modules call `_open_review_run` with another engine (for example `test_round_driver_integration.py:1100`), but those are outside this order's surface and were not used. The non-codex `None` is covered only at the reader (L5 `non-codex`), not at the record.
