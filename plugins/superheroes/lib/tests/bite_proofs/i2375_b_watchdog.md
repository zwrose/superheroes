# Bite-proof record — the codex review seat's silence watchdog (#2375, order B)

Detector files: `plugins/superheroes/lib/tests/test_engine_dispatch_silence_watchdog.py` and, for H8, `plugins/superheroes/lib/tests/test_engine_dispatch_e2e.py::test_e2e_review_silence_watchdog_ends_silent_attempt_and_retry_answers`, unedited between each red and its green. Production file: `plugins/superheroes/lib/engine_dispatch.py`. Every neutralization is a targeted edit made and undone with the edit tool, at commit `59c3b9dc`. Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch_silence_watchdog.py -q -n auto --deselect plugins/superheroes/lib/tests/test_engine_dispatch_silence_watchdog.py::test_run_opened_records_the_threshold_read_at_open_time` (that one test wrote into the system temp folder at this commit and was deselected for the proofs; the next commit pins its temp base). The H8 run adds the e2e file with `-k "silence or watchdog or test_a_ or test_c_"`. The captures quote each run's `FAILED` lines and summary line, tracebacks elided. Nothing is redacted (no secret, token, URL or personal data appears). The eight guarded elements are the eight the order declared. The implementer ran the same eight; its attempt hit the dispatch timeout before writing its report, so every proof here is the builder's own run.

## H1. The final attempt is never armed (`_silence_watchdog_threshold`)

- **Axis:** armed only when `attempt < MAX_ATTEMPTS`, so the retry keeps its full bound.
- **Neutralization:** `and attempt < MAX_ATTEMPTS and isinstance(seconds, (int, float))` changed to `and isinstance(seconds, (int, float))`.
- **Raw red:** `1 failed, 41 passed` — `test_d_bound_still_ends_an_attempt_that_never_answers`.
- **Restore:** inverse edit. **Raw green:** `42 passed`.

## H2. Any growth or non-idle beat resets the silence (`_run_engine_files`)

- **Neutralization:** `silent_s = 0.0  # axis: any growth or non-idle beat resets the silence` changed to `pass  # axis: …`.
- **Raw red:** `1 failed, 41 passed` — `test_w4_stderr_only_growth_resets_the_silence`.
- **Restore:** inverse edit. **Raw green:** `42 passed`.

## H3. A natural exit, then the per-attempt bound, outrank the watchdog

- **Neutralization:** `if watchdog_due: watchdog_fired = True; break` inserted before `if rc is not None:`.
- **Raw red:** `2 failed, 40 passed` — `test_w2_timeout_on_the_due_tick_wins[0.5-False]`, `test_w1_natural_exit_on_the_due_tick_is_admitted`.
- **Restore:** the inserted lines removed. **Raw green:** `42 passed`.

## H4. Grading forfeits a watchdog end whatever its exit (`_grade_review_attempt`)

- **Neutralization:** `if _silence_watchdog_end(ended):  # axis: a watchdog end is a forfeit …` changed to `if False:`.
- **Raw red:** `3 failed, 39 passed` — `test_a_silent_attempt_with_no_command_is_ended_and_graded_a_forfeit`, `test_c_retried_attempt_that_answers_is_accepted`, `test_w10_watchdog_end_with_valid_result_and_exit_zero_is_never_clean`.
- **Restore:** inverse edit. **Raw green:** `42 passed`.

## H5. A watchdog end is never a clean completion (`_attempt_ended_successfully`)

- **Neutralization:** `if _silence_watchdog_end(ended):  # axis: a watchdog end is never a clean completion` changed to `if False:`.
- **Raw red:** `1 failed, 41 passed` — `test_w10_watchdog_end_with_valid_result_and_exit_zero_is_never_clean`.
- **Restore:** inverse edit. **Raw green:** `42 passed`.

## H6. A watchdog end parses to no result (`_parse_review_attempt`)

- **Neutralization:** `if _silence_watchdog_end(ended):  # axis: a watchdog end parses to no result` changed to `if False:`.
- **Raw red:** `1 failed, 41 passed` — `test_parse_review_attempt_refuses_a_watchdog_end_even_when_admission_would_accept`.
- **Restore:** inverse edit. **Raw green:** `42 passed`.

## H7. The end itself (`watchdog_due`)

- **Neutralization:** `watchdog_due = silent_s >= wd_threshold` changed to `watchdog_due = False`.
- **Raw red:** `8 failed, 34 passed` — `test_a_…`, `test_c_…`, `test_d_…` (its attempt-1 control), `test_w2_timeout_on_the_due_tick_wins[0.75-True]`, `test_b_w3_command_in_flight_is_never_silence[True]` and `test_w5_unreadable_stdout_increment_never_ends_the_attempt[False]` (each the control case where the watchdog must fire), `test_w10_…`, `test_parse_review_attempt_refuses_…`.
- **Restore:** inverse edit. **Raw green:** `42 passed`.

## H8. The threshold is the one recorded on `run-opened`

- **Neutralization:** `seconds = opened.get("silenceWatchdogSeconds")` changed to `seconds = 10**9`.
- **Raw red:** `10 failed, 33 passed in 144.89s`, including the real-subprocess `test_e2e_review_silence_watchdog_ends_silent_attempt_and_retry_answers` (attempt 1 was never ended, so the 120 s silent fake ran out its sleep) and `test_w7_threshold_reader_accepts_only_real_positive_finite_numbers`.
- **Restore:** inverse edit; `git status --porcelain` empty. **Raw green:** `43 passed in 20.75s` (e2e included).

## D1. One failure disarms the watchdog for the rest of the attempt (review fix, order D, commit `20198f98`)

- **Axis:** after one exception inside the armed check, a later silent, idle beat never ends the attempt.
- **Detector:** `test_w9_exception_in_the_armed_block_disarms_the_watchdog[read_increment|silent_and_idle]`, whose stub now raises once and then calls the real function (before this fix it raised every time, so the guard below could be removed behind a green test; that was the review's confirmed Minor).
- **Neutralization:** `wd_threshold = None  # axis: a failure inside the check disarms it …` changed to `pass  # axis: …`.
- **Raw red:** `2 failed, 41 passed` — both W9 cases, each `assert 'silenceWatchdog' not in ended` (the attempt was ended by the watchdog at exit -15).
- **Restore:** inverse edit; `git status --porcelain` empty. **Raw green:** `43 passed in 11.10s`.
