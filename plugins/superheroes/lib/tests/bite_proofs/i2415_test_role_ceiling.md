# Bite-proof record — the test role's attempt and retry ceilings scale with its slice (#2415)

Detectors: `plugins/superheroes/lib/tests/test_test_role_ceiling_2415.py` (G1) and `plugins/superheroes/lib/tests/test_engine_dispatch_e2e.py` (G2), unedited between each red and its green. Every neutralization is a targeted, reversible Edit-tool edit to one production file, restored by the inverse edit (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest '<exact node ids>' -q -n 0; echo "exit=$?"`, output captured whole. The `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out of each capture; the red captures also leave out the unchanged body of the G2 test function (its source is in the file), keeping the failing assertion and its `E` lines. Each `old_string` occurred exactly once (the Edit tool refuses a non-unique match). The two guarded elements are the ones the order declared; none is grouped. No secrets, tokens, private URLs or PII appear in any capture; nothing was redacted.

## G1. The panel payload carries each seat's ceiling (`round_driver._panel_ceilings`)

- **Axis:** the `dispatch-panel` payload's `ceilings` row for a seat is `round_phases.seat_ceiling` of the countable lines it reviews (a slice seat's slice weight; any other seat's plan `countable`), so a heavy slice and an unsliced change of about 800 lines raise the test role's ceiling above 900.
- **Detectors:** `test_test_role_ceiling_2415.py::test_a_sliced_plan_gives_each_seat_its_ceiling_row` and `::test_an_unsliced_change_of_about_800_lines_raises_the_test_role_ceiling`.
- **Neutralization** (`plugins/superheroes/lib/round_driver.py`, in `_panel_ceilings`): `ceiling = round_phases.seat_ceiling(key, lines)` became `ceiling = round_phases.SEAT_CEILING_FLOOR_SECONDS`, so every seat gets the floor.

**Raw red** (exit 1):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
______________ test_a_sliced_plan_gives_each_seat_its_ceiling_row ______________

    def test_a_sliced_plan_gives_each_seat_its_ceiling_row():
        # axis: G1 — the panel payload carries each seat's ceiling from its slice's weight
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2415_test_role_ceiling.md
        state, payload = _panel_payload(_new_file_diff(3000))
        weights = {s["id"]: s["weight"] for s in state["slicePlan"]["slices"]}
        assert weights and max(weights.values()) > 300
        assert set(payload["ceilings"]) == set(payload["dimensions"])
        saw_test_slice = False
        for key in payload["dimensions"]:
            row = payload["ceilings"][key]
            if key.startswith("test-role:"):
                saw_test_slice = True
                weight = weights[key.partition(":")[2]]
                assert row["lines"] == weight
>               assert row["timeout"] == row["retryTimeout"] == RP.seat_ceiling(key, weight)
E               AssertionError: assert 900 == 1800
E                +  where 1800 = <function seat_ceiling at 0x7f99c18afc40>('test-role:s1', 1000)
E                +    where <function seat_ceiling at 0x7f99c18afc40> = RP.seat_ceiling

/home/user/wt-2415/plugins/superheroes/lib/tests/test_test_role_ceiling_2415.py:114: AssertionError
___ test_an_unsliced_change_of_about_800_lines_raises_the_test_role_ceiling ____

    def test_an_unsliced_change_of_about_800_lines_raises_the_test_role_ceiling():
        # axis: G1 — the #2403 session-1 shape (one unsliced change of about 800 countable lines)
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2415_test_role_ceiling.md
        state, payload = _panel_payload(_new_file_diff(800))
        plan = state["slicePlan"]
        assert plan["sliced"] is False and plan["countable"] > 600
        row = payload["ceilings"]["test-role"]
        assert row["lines"] == plan["countable"]
>       assert row["timeout"] == row["retryTimeout"] == RP.seat_ceiling("test-role", plan["countable"]) > 900
E       AssertionError: assert 900 == 1650
E        +  where 1650 = <function seat_ceiling at 0x7f99c18afc40>('test-role', 800)
E        +    where <function seat_ceiling at 0x7f99c18afc40> = RP.seat_ceiling

/home/user/wt-2415/plugins/superheroes/lib/tests/test_test_role_ceiling_2415.py:137: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_test_role_ceiling_2415.py::test_a_sliced_plan_gives_each_seat_its_ceiling_row
FAILED plugins/superheroes/lib/tests/test_test_role_ceiling_2415.py::test_an_unsliced_change_of_about_800_lines_raises_the_test_role_ceiling
2 failed in 0.24s
exit=1
```

- **Restore:** inverse edit (`ceiling = round_phases.SEAT_CEILING_FLOOR_SECONDS` back to `ceiling = round_phases.seat_ceiling(key, lines)`).
- **Restore receipt** (read back by the Grep tool, `ceiling = round_phases`):

```
plugins/superheroes/lib/round_driver.py:3662:        ceiling = round_phases.seat_ceiling(key, lines)
```

**Raw green** (exit 0):

```
..                                                                       [100%]
2 passed in 0.24s
exit=0
```

## G2. The attempt after a silence-watchdog cut runs with the seat's ceiling (`engine_dispatch._attempt_timeout`, attempt 2)

- **Axis:** an attempt 2's bound, journaled as `timeout` on its `engine-launching` record, is the `retry_timeout` the caller passed (the seat's ceiling), not the 900 s minimum.
- **Detector:** `test_engine_dispatch_e2e.py::test_e2e_review_retry_after_silence_watchdog_runs_with_the_seat_ceiling` (two cases: 1000 lines → 1800, 100 lines → 900).
- **Neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_attempt_timeout`, the attempt-2 branch): `return max(opened.get("retryTimeout", RETRY_MIN_TIMEOUT), RETRY_MIN_TIMEOUT)` became `return RETRY_MIN_TIMEOUT`.

**Raw red** (exit 1; the test function's body, which the pytest capture reprinted in full, is cut to the lines up to and including the failing assertion's context, as stated above; the 900 case passes, as the 900 floor equals the neutralized return):

```
F.                                                                       [100%]
=================================== FAILURES ===================================
_ test_e2e_review_retry_after_silence_watchdog_runs_with_the_seat_ceiling[1000-1800] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-7/test_e2e_review_retry_after_si0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f690b7d7e00>
lines = 1000, expected = 1800

    ... (test body elided here; unchanged source in the file)
        res = _poll_review_terminal(repo, run_dir, prompt_path, timeout=90, timeout_s=ceiling, retry_timeout=ceiling)

        assert res["ok"] is True
        assert res["terminal"] is True
        assert res["attempts"] == 2
        records = _journal_records(run_dir)
        ended = {r["attempt"]: r for r in records if r.get("kind") == "attempt-ended"}
        assert ended[1]["signalSource"] == "silence-watchdog"
        carrying = [r for r in records
                    if r.get("kind") == "engine-launching" and r.get("attempt") == 2 and "timeout" in r]
        assert len(carrying) == 1
>       assert carrying[0]["timeout"] == expected
E       assert 900 == 1800

plugins/superheroes/lib/tests/test_engine_dispatch_e2e.py:570: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch_e2e.py::test_e2e_review_retry_after_silence_watchdog_runs_with_the_seat_ceiling[1000-1800]
1 failed, 1 passed in 26.47s
exit=1
```

- **Restore:** inverse edit (`return RETRY_MIN_TIMEOUT` back to `return max(opened.get("retryTimeout", RETRY_MIN_TIMEOUT), RETRY_MIN_TIMEOUT)`).
- **Restore receipt** (read back by the Grep tool, `return max\(opened.get\("retryTimeout"`):

```
plugins/superheroes/lib/engine_dispatch.py:4451:    return max(opened.get("retryTimeout", RETRY_MIN_TIMEOUT), RETRY_MIN_TIMEOUT)
```

**Raw green** (exit 0):

```
..                                                                       [100%]
2 passed in 25.93s
exit=0
```

## G3. A retry cut by the watchdog earns a third attempt (`engine_dispatch._attempt_budget`)

- **Axis:** for a codex review run with the watchdog on, attempt 1 cut by the silence watchdog and attempt 2 running or cut too gives a budget of `MAX_ATTEMPTS + 1`, so the retry is watched and its cut is followed by a third, unarmed attempt.
- **Detector:** `test_engine_dispatch_e2e.py::test_e2e_review_second_chance_a_retry_cut_by_the_watchdog_earns_a_third_attempt` (real subprocesses, fake `codex` silent on attempts 1 and 2, answering on attempt 3; threshold monkeypatched to 1 s). Its companion `::test_e2e_review_second_chance_a_retry_that_does_not_stall_earns_no_third_attempt` guards the other side (no third attempt) and is not neutralized here.
- **Neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_attempt_budget`): a first statement `return MAX_ATTEMPTS` inserted inside the `try:` block, so the budget is always 2.
- **Run:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest '<node id>' -q -n 0; echo "exit=$?"`. The `UV_NATIVE_TLS` warning line and the unchanged test body above the failing assertion are left out of the red capture (the body is in the file).

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_e2e_review_second_chance_a_retry_cut_by_the_watchdog_earns_a_third_attempt _
...
        started = time.monotonic()
        res = _poll_review_terminal(repo, run_dir, prompt_path, timeout=150)
        elapsed = time.monotonic() - started
    
        assert res["ok"] is True
        assert res["terminal"] is True
>       assert res["attempts"] == 3
E       assert 2 == 3

plugins/superheroes/lib/tests/test_engine_dispatch_e2e.py:617: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch_e2e.py::test_e2e_review_second_chance_a_retry_cut_by_the_watchdog_earns_a_third_attempt
1 failed in 132.44s (0:02:12)
exit=1
```

- **Restore:** inverse edit (the inserted `return MAX_ATTEMPTS` line removed from the `try:` block).
- **Restore receipt** (read back by the Grep tool, `return MAX_ATTEMPTS$|return MAX_ATTEMPTS \+ 1`; the five lines are the function's own fail-closed returns and its `+ 1` return, with no extra line directly under `try:`):

```
plugins/superheroes/lib/engine_dispatch.py:3804:            return MAX_ATTEMPTS
plugins/superheroes/lib/engine_dispatch.py:3807:            return MAX_ATTEMPTS
plugins/superheroes/lib/engine_dispatch.py:3810:            return MAX_ATTEMPTS
plugins/superheroes/lib/engine_dispatch.py:3814:            return MAX_ATTEMPTS + 1
plugins/superheroes/lib/engine_dispatch.py:3817:    return MAX_ATTEMPTS
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 23.96s
exit=0
```

## G4. The watchdog is armed on every attempt below the run's budget (`engine_dispatch._silence_watchdog_threshold`)

- **Axis:** attempt 2 is armed when attempt 1 was cut by the watchdog (the comparison is against `_attempt_budget(opened, state)`, not `MAX_ATTEMPTS`).
- **Detector:** `test_silence_retry_budget_2415.py::test_a_retry_after_a_watchdog_cut_is_armed`.
- **Neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_silence_watchdog_threshold`): `and attempt < _attempt_budget(opened, state)` became `and attempt < MAX_ATTEMPTS`.
- **Run:** same command shape as G3, with the unit test's node id. The `UV_NATIVE_TLS` warning line is left out.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_a_retry_after_a_watchdog_cut_is_armed __________________

    def test_a_retry_after_a_watchdog_cut_is_armed():
        # axis: G4 — attempt 2 is armed when attempt 1 was cut by the watchdog
>       assert ED._silence_watchdog_threshold(_opened(), 2, _state(_cut())) == _THRESHOLD
E       AssertionError: assert None == 390
E        +  where None = <function _silence_watchdog_threshold at 0x7f3d472bc040>({'kind': 'run-opened', 'engine': 'codex', 'runKind': 'review', 'silenceWatchdogSeconds': 390}, 2, {'opened': None, 'attempts': {1: {'childPid': 1, 'enginePgid': 1, 'ended': {'kind': 'attempt-ended', 'signalSource': 'silence-watchdog', 'timedOut': False, 'exit': -15, ...}}}})
E        +    where <function _silence_watchdog_threshold at 0x7f3d472bc040> = ED._silence_watchdog_threshold
E        +    and   {'kind': 'run-opened', 'engine': 'codex', 'runKind': 'review', 'silenceWatchdogSeconds': 390} = _opened()
E        +    and   {'opened': None, 'attempts': {1: {'childPid': 1, 'enginePgid': 1, 'ended': {'kind': 'attempt-ended', 'signalSource': 'silence-watchdog', 'timedOut': False, 'exit': -15, ...}}}} = _state({'kind': 'attempt-ended', 'signalSource': 'silence-watchdog', 'timedOut': False, 'exit': -15, ...})
E        +      where {'kind': 'attempt-ended', 'signalSource': 'silence-watchdog', 'timedOut': False, 'exit': -15, ...} = _cut()

plugins/superheroes/lib/tests/test_silence_retry_budget_2415.py:170: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_silence_retry_budget_2415.py::test_a_retry_after_a_watchdog_cut_is_armed
1 failed in 4.58s
exit=1
```

- **Restore:** inverse edit (`and attempt < MAX_ATTEMPTS` back to `and attempt < _attempt_budget(opened, state)`).
- **Restore receipt** (read back by the Grep tool, `attempt < (MAX_ATTEMPTS|_attempt_budget)`):

```
plugins/superheroes/lib/engine_dispatch.py:3827:                and attempt < _attempt_budget(opened, state)
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.17s
exit=0
```

No secrets, tokens, private URLs or PII appear in any capture; nothing was redacted.
