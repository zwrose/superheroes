# Bite-proof record — a run the silence watchdog ended still counts the cost it measured (#2514)

Detector file: `plugins/superheroes/lib/tests/test_partial_cost_2514.py`, unedited between each red and its green. Every entry is a targeted, reversible edit to one production file, made and undone with the edit tool (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2514 -m pytest '<exact node id>' -q`, one test node each, output captured whole; the `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out of each capture, and the `tmp_path` directory names are as the runner printed them (no secret, token, URL or personal data appears in any capture, so nothing is redacted). The thirteen guarded elements are the twelve the first order declared (G1-G12) and the one a later order added (G13); none is grouped, and each has its own neutralization, red and green. Each target occurred exactly once in the edit's `old_string` (the edit tool refuses a non-unique match). The `file:line` numbers below are those of the restored (HEAD) files.

The detectors the entries name are the tests that carry a `# bite-proof:` line: T1 (G1 and G5), T2 (G3), T5 (G2), T6 (G4), T8 (G6), T9 `[empty-list]` (G7), T10 `[partial-but-complete]` (G8) and `[partial-over-the-runs]` (G9), T11a (G10), T11b (G11), T11c (G12) and T12 `[plain]` and `[watchdog]` (G13).

## G1. Watchdog-unmeasured branch (`lib/engine_dispatch.py`, `_attempts_cost`)

- **Guarded element:** `engine_dispatch.py:7784-7787`, the branch that adds the wall time and names the attempt in `unmeasured` when a silence-watchdog-ended attempt has no usage total.
- **Axis:** a watchdog-ended attempt with no usage total leaves its tokens unmeasured, not the whole run, when another attempt measured.
- **Detector:** `test_partial_cost_2514.py::test_t1_a_watchdog_ended_attempt_with_no_usage_and_a_measured_retry_is_a_partial_run`.
- **Neutralization:** the three lines `wall += secs` / `unmeasured.append(att)` / `continue` under `if used is None:` in the watchdog branch became `return None`, the old all-or-nothing rule.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t1_a_watchdog_ended_attempt_with_no_usage_and_a_measured_retry_is_a_partial_run _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-5/test_t1_a_watchdog_ended_attem0')

    def test_t1_a_watchdog_ended_attempt_with_no_usage_and_a_measured_retry_is_a_partial_run(tmp_path):
        # axis: a watchdog-ended attempt with no usage total leaves its tokens unmeasured, not the whole run, when another attempt measured
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2514_partial_cost.md
        record = _partial_record(tmp_path)
>       assert record["attemptsCost"] == {"tokens": 60, "wallSeconds": 630, "attempts": 2, "tokensUnmeasured": [1]}
E       AssertionError: assert None == {'tokens': 60, 'wallSeconds': 630, 'attempts': 2, 'tokensUnmeasured': [1]}

/home/user/wt-2514/plugins/superheroes/lib/tests/test_partial_cost_2514.py:48: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_partial_cost_2514.py::test_t1_a_watchdog_ended_attempt_with_no_usage_and_a_measured_retry_is_a_partial_run
1 failed in 3.92s
```

**Restore:** the inverse edit put the three lines back in place of `return None`.
**Restore receipt** (the restored lines, quoted from `engine_dispatch.py:7784-7787`):

```
                if used is None:
                    wall += secs
                    unmeasured.append(att)
                    continue
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 3.72s
```

## G2. No-measured-attempt guard (`lib/engine_dispatch.py`, `_attempts_cost`)

- **Guarded element:** `engine_dispatch.py:7797-7798`, `if len(unmeasured) == len(attempts): return None`.
- **Axis:** a run with no measured attempt has no figure, however many attempts the watchdog ended.
- **Detector:** `test_partial_cost_2514.py::test_t5_a_single_watchdog_ended_attempt_with_no_usage_has_no_figure`, driven at the `_attempts_cost` seam (`seam_cost`, `test_partial_cost_2514.py:110-116`).
- **Neutralization:** the two lines `if len(unmeasured) == len(attempts):` / `return None` were deleted, so a run with no measured attempt returns its partial dict.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_t5_a_single_watchdog_ended_attempt_with_no_usage_has_no_figure ______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-7/test_t5_a_single_watchdog_ende0')

    def test_t5_a_single_watchdog_ended_attempt_with_no_usage_has_no_figure(tmp_path):
        # axis: a run with no measured attempt has no figure, however the watchdog ended its attempts
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2514_partial_cost.md
>       assert seam_cost(tmp_path, [attempt(stream(events=False), 600, **WATCHDOG)]) is None
E       assert {'tokens': 0, 'wallSeconds': 600, 'attempts': 1, 'tokensUnmeasured': [1]} is None
E        +  where {'tokens': 0, 'wallSeconds': 600, 'attempts': 1, 'tokensUnmeasured': [1]} = seam_cost(PosixPath('/tmp/claude-0/pytest-of-root/pytest-7/test_t5_a_single_watchdog_ende0'), [{'stdout': '{"type": "thread.started", "thread_id": "t"}\n{"type": "turn.started"}', 'wall': 600, 'ended': True, 'ove...gnalSource': 'silence-watchdog', 'silenceWatchdog': {'silentSeconds': 600.0, 'thresholdSeconds': 600, 'killAt': 1.0}}}])

/home/user/wt-2514/plugins/superheroes/lib/tests/test_partial_cost_2514.py:122: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_partial_cost_2514.py::test_t5_a_single_watchdog_ended_attempt_with_no_usage_has_no_figure
1 failed in 3.46s
```

**Restore:** the inverse edit put the two lines back above the partial-dict return.
**Restore receipt** (the restored lines, quoted from `engine_dispatch.py:7797-7799`):

```
        if len(unmeasured) == len(attempts):
            return None
        return {"tokens": tokens, "wallSeconds": wall, "attempts": len(attempts), "tokensUnmeasured": unmeasured}
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 3.79s
```

**Unreachable through this entry point** (for the public path only; the proof above is not affected):

- **Public path that strips the input:** `run_execution_record` (`engine_dispatch.py:7856`) refuses a run whose last completed attempt is a watchdog end: `if not _attempt_ended_successfully(ended): return None, "attempt-not-completed"` (`engine_dispatch.py:7877-7878`). A run with no measured attempt that the watchdog ended therefore never reaches `attemptsCost` through `run_execution_record`, so no test that builds the record through it can deliver this guard's input. The no-measured-attempt input is reachable only when every attempt is a watchdog end, and then the last one is too.
- **Seam that does bite:** `engine_dispatch._attempts_cost` itself (`engine_dispatch.py:7754`, the guard at `7797-7798`), called by `seam_cost` (`test_partial_cost_2514.py:110-116`) from the journaled run's own state, which also asserts (line 114) that `run_execution_record` returns `(None, "attempt-not-completed")` for that run. The red above is that seam's.

## G3. Empty-usage refusal (`lib/engine_adapter.py`, `codex_usage_tokens(explicit=True)`)

- **Guarded element:** `engine_adapter.py:1166-1167`, `if explicit and not any(isinstance(last_usage.get(part), int) for part in _CODEX_TOKEN_PARTS): return None`.
- **Axis:** with `explicit=True` a usage carrying no int token part is no figure, never a measured zero.
- **Detector:** `test_partial_cost_2514.py::test_t2_a_watchdog_ended_attempt_with_an_empty_usage_is_unmeasured_not_zero`.
- **Neutralization:** `if explicit and not any(` became `if False and not any(`, so `explicit` is ignored.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t2_a_watchdog_ended_attempt_with_an_empty_usage_is_unmeasured_not_zero __

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-9/test_t2_a_watchdog_ended_attem0')

    def test_t2_a_watchdog_ended_attempt_with_an_empty_usage_is_unmeasured_not_zero(tmp_path):
        # axis: an empty usage on a watchdog-ended attempt is no figure, never a measured zero
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2514_partial_cost.md
        record = execution_record(tmp_path, [attempt(stream(), 600, **WATCHDOG), attempt(stream(**RETRY), 30)])
>       assert record["attemptsCost"] == {"tokens": 60, "wallSeconds": 630, "attempts": 2, "tokensUnmeasured": [1]}
E       AssertionError: assert {'tokens': 60...'attempts': 2} == {'tokens': 60...easured': [1]}
E         
E         Omitting 3 identical items, use -vv to show
E         Right contains 1 more item:
E         {'tokensUnmeasured': [1]}
E         Use -v to get more diff

/home/user/wt-2514/plugins/superheroes/lib/tests/test_partial_cost_2514.py:67: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_partial_cost_2514.py::test_t2_a_watchdog_ended_attempt_with_an_empty_usage_is_unmeasured_not_zero
1 failed in 3.53s
```

**Restore:** the inverse edit put `explicit` back in place of `False`.
**Restore receipt** (the restored lines, quoted from `engine_adapter.py:1166-1167`):

```
        if explicit and not any(isinstance(last_usage.get(part), int) for part in _CODEX_TOKEN_PARTS):
            return None
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 3.51s
```

## G4. Watchdog-only restriction (`lib/engine_dispatch.py`, `_attempts_cost`)

- **Guarded element:** `engine_dispatch.py:7782`, `if _silence_watchdog_end(ended):`, the predicate that confines the unmeasured allowance to a silence-watchdog end.
- **Axis:** only a silence-watchdog end may leave its tokens unmeasured; any other attempt without usage leaves the run without a figure.
- **Detector:** `test_partial_cost_2514.py::test_t6_a_timed_out_attempt_that_the_watchdog_did_not_end_keeps_the_all_or_nothing_rule`.
- **Neutralization:** `if _silence_watchdog_end(ended):` became `if True:`, so every attempt is treated as a watchdog end.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t6_a_timed_out_attempt_that_the_watchdog_did_not_end_keeps_the_all_or_nothing_rule _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-11/test_t6_a_timed_out_attempt_th0')

    def test_t6_a_timed_out_attempt_that_the_watchdog_did_not_end_keeps_the_all_or_nothing_rule(tmp_path):
        # axis: only a silence-watchdog end may leave its tokens unmeasured; any other attempt without usage leaves the run without a figure
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2514_partial_cost.md
        record = execution_record(tmp_path, [attempt(stream(events=False), 900, **TIMED_OUT), attempt(stream(**RETRY), 30)])
>       assert record["attemptsCost"] is None
E       AssertionError: assert {'tokens': 60, 'wallSeconds': 930, 'attempts': 2, 'tokensUnmeasured': [1]} is None

/home/user/wt-2514/plugins/superheroes/lib/tests/test_partial_cost_2514.py:140: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_partial_cost_2514.py::test_t6_a_timed_out_attempt_that_the_watchdog_did_not_end_keeps_the_all_or_nothing_rule
1 failed in 4.06s
```

**Restore:** the inverse edit put `_silence_watchdog_end(ended)` back in place of `True`.
**Restore receipt** (the restored lines, quoted from `engine_dispatch.py:7782-7783`):

```
            if _silence_watchdog_end(ended):
                used = engine_adapter.codex_usage_tokens(stdout, explicit=True)
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 3.57s
```

## G5. Session `complete` rule with partial (`lib/review_record_session.py`, `_session_cost`)

- **Guarded element:** `review_record_session.py:330`, `out["complete"] = bare == 0 and partial == 0`.
- **Axis:** a session holding any partial run is never `complete`.
- **Detector:** `test_partial_cost_2514.py::test_t1_a_watchdog_ended_attempt_with_no_usage_and_a_measured_retry_is_a_partial_run` (its session half; the engine-record half, line 48, passes under this neutralization).
- **Neutralization:** `out["complete"] = bare == 0 and partial == 0` became `out["complete"] = bare == 0`.
- **How it went red:** the session helper that T1 calls (`session_cost` → `written`) posts the session through the account check, and the check refused the writer's `complete: True` beside `runsPartial: 1` (`sessionCost.complete`), so the failure is raised inside that helper at the `session_cost(...)` call (line 49), before T1's own `complete` assertion (line 51) is reached. The detector is red; the account check (G8) is the layer that caught the writer's wrong `complete`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t1_a_watchdog_ended_attempt_with_no_usage_and_a_measured_retry_is_a_partial_run _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-13/test_t1_a_watchdog_ended_attem0')

    def test_t1_a_watchdog_ended_attempt_with_no_usage_and_a_measured_retry_is_a_partial_run(tmp_path):
        # axis: a watchdog-ended attempt with no usage total leaves its tokens unmeasured, not the whole run, when another attempt measured
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2514_partial_cost.md
        record = _partial_record(tmp_path)
        assert record["attemptsCost"] == {"tokens": 60, "wallSeconds": 630, "attempts": 2, "tokensUnmeasured": [1]}
>       cost = session_cost(tmp_path, record)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2514/plugins/superheroes/lib/tests/test_partial_cost_2514.py:49: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt-2514/plugins/superheroes/lib/tests/test_session_cost_every_attempt_2381.py:84: in session_cost
    return written(tmp_path, s.save(), {NONCE: (record, None)})["sessionCost"]
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-13/test_t1_a_watchdog_ended_attem0')
session = '/tmp/claude-0/pytest-of-root/pytest-13/test_t1_a_watchdog_ended_attem0/session'
runs = {'n1': ({'source': 'codex', 'runnerNonce': 'n1', 'recordDigest': '76b964b26977cd74cf211fa073f4a27cc5feae3a2245c2ef00a95bc54ae7748a', 'observation': {'tokens': 60, 'toolCalls': 0, 'stdoutBytes': 148, 'wallSeconds': 30, ...}, ...}, None)}
dirs = None, over = {}

    def written(tmp_path, session, runs, dirs=None, **over):
        """Write the session with the given engine records and read the posted record back."""
        fake = Fake(runs={f"/run/{n}": r for n, r in runs.items()})
        out = send(tmp_path, session, fake, ci="green", runDirs=dirs if dirs is not None else sorted(fake.runs), **over)
>       assert out["ok"], out
E       AssertionError: {'ok': False, 'reason': 'review-account-invalid', 'detail': 'sessionCost.complete'}
E       assert False

/home/user/wt-2514/plugins/superheroes/lib/tests/test_review_record_session_cost_2307.py:38: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_partial_cost_2514.py::test_t1_a_watchdog_ended_attempt_with_no_usage_and_a_measured_retry_is_a_partial_run
1 failed in 3.74s
```

**Restore:** the inverse edit put `and partial == 0` back.
**Restore receipt** (the restored lines, quoted from `review_record_session.py:329-330`):

```
    # axis: a session holding any partial run is never complete — see bite-proof record i2514_partial_cost
    out["complete"] = bare == 0 and partial == 0
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 3.94s
```

## G6. `runsPartial` only when one or more (`lib/review_record_session.py`, `_session_cost`)

- **Guarded element:** `review_record_session.py:327-328`, `if partial: out["runsPartial"] = partial`.
- **Axis:** `runsPartial` is written only when one or more runs are partial, so a session of whole runs reads as before.
- **Detector:** `test_partial_cost_2514.py::test_t8_a_run_whose_attempts_all_measured_reads_exactly_as_before`.
- **Neutralization:** `if partial:` became `if True:`, so `runsPartial` is always written.
- **How it went red:** the session helper (`session_cost` → `written`) posts the session through the account check, which refuses `runsPartial: 0` (`sessionCost.runsPartial`), so the failure is raised inside that helper at the `session_cost(...)` call (line 159), before T8's exact-dict comparison could run. The detector is red; the account check (G9's rule) is the layer that caught the always-written key.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_t8_a_run_whose_attempts_all_measured_reads_exactly_as_before _______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-15/test_t8_a_run_whose_attempts_a0')

    def test_t8_a_run_whose_attempts_all_measured_reads_exactly_as_before(tmp_path):
        # axis: a run of whole attempts carries exactly the three keys and its session cost carries no runsPartial
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2514_partial_cost.md
        record = execution_record(tmp_path, [
            attempt(stream(input_tokens=30, output_tokens=10), 900, **TIMED_OUT),
            attempt(stream(input_tokens=50, cached_input_tokens=0, output_tokens=10), 30)])
        assert set(record["attemptsCost"]) == {"tokens", "wallSeconds", "attempts"}
>       assert session_cost(tmp_path, record) == {
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
            "tokens": 100, "minutes": 15.5, "runs": 1, "runsWithoutFigure": 0, "complete": True,
            "bySeat": {"code-reviewer": {"tokens": 100, "minutes": 15.5, "runs": 1}}}

/home/user/wt-2514/plugins/superheroes/lib/tests/test_partial_cost_2514.py:159: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt-2514/plugins/superheroes/lib/tests/test_session_cost_every_attempt_2381.py:84: in session_cost
    return written(tmp_path, s.save(), {NONCE: (record, None)})["sessionCost"]
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-15/test_t8_a_run_whose_attempts_a0')
session = '/tmp/claude-0/pytest-of-root/pytest-15/test_t8_a_run_whose_attempts_a0/session'
runs = {'n1': ({'source': 'codex', 'runnerNonce': 'n1', 'recordDigest': '2d95c4d10ff67fcc775a51196a5e40a33ad5403959489a7d0ae9604d68a2ea76', 'observation': {'tokens': 60, 'toolCalls': 0, 'stdoutBytes': 174, 'wallSeconds': 30, ...}, ...}, None)}
dirs = None, over = {}

    def written(tmp_path, session, runs, dirs=None, **over):
        """Write the session with the given engine records and read the posted record back."""
        fake = Fake(runs={f"/run/{n}": r for n, r in runs.items()})
        out = send(tmp_path, session, fake, ci="green", runDirs=dirs if dirs is not None else sorted(fake.runs), **over)
>       assert out["ok"], out
E       AssertionError: {'ok': False, 'reason': 'review-account-invalid', 'detail': 'sessionCost.runsPartial'}
E       assert False

/home/user/wt-2514/plugins/superheroes/lib/tests/test_review_record_session_cost_2307.py:38: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_partial_cost_2514.py::test_t8_a_run_whose_attempts_all_measured_reads_exactly_as_before
1 failed in 3.94s
```

**Restore:** the inverse edit put `partial` back in place of `True`.
**Restore receipt** (the restored lines, quoted from `review_record_session.py:326-328`):

```
    # axis: `runsPartial` is written only when one or more runs are partial, so a session of whole runs reads as before — see bite-proof record i2514_partial_cost
    if partial:
        out["runsPartial"] = partial
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 3.61s
```

## G7. Reader's malformed-`tokensUnmeasured` rule (`lib/review_record_session.py`, `_partial_state`)

- **Guarded element:** `review_record_session.py:254`, the `"partial" if isinstance(u, list) and u and all(_int(x) and x >= 1 for x in u) else "bad"` return of `_partial_state`.
- **Axis:** a `tokensUnmeasured` that is not a non-empty list of attempt numbers makes the run one without a figure, never a whole one.
- **Detector:** `test_partial_cost_2514.py::test_t9_a_malformed_tokens_unmeasured_makes_the_run_one_without_a_figure[empty-list]`.
- **Neutralization:** the return became `return "partial"`, so any present `tokensUnmeasured` counts as partial.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t9_a_malformed_tokens_unmeasured_makes_the_run_one_without_a_figure[empty-list] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-17/test_t9_a_malformed_tokens_unm0')
bad = []

    @pytest.mark.parametrize("bad", [[], [0], "1"], ids=["empty-list", "zero-attempt", "string"])
    def test_t9_a_malformed_tokens_unmeasured_makes_the_run_one_without_a_figure(tmp_path, bad):
        # axis: a tokensUnmeasured that is not a non-empty list of attempt numbers makes the run one without a figure, never a whole one
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2514_partial_cost.md
        engine_record = dict(GOOD_RUN, runnerNonce=NONCE, attemptsCost=dict(_WHOLE, tokensUnmeasured=bad))
        cost = session_cost(tmp_path, engine_record)
>       assert (cost["tokens"], cost["minutes"], cost["runs"], cost["runsWithoutFigure"], cost["complete"]) == (0, 0.0, 1, 1, False)
E       assert (100, 2.0, 1, 0, False) == (0, 0.0, 1, 1, False)
E         
E         At index 0 diff: 100 != 0
E         Use -v to get more diff

/home/user/wt-2514/plugins/superheroes/lib/tests/test_partial_cost_2514.py:173: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_partial_cost_2514.py::test_t9_a_malformed_tokens_unmeasured_makes_the_run_one_without_a_figure[empty-list]
1 failed in 3.53s
```

**Restore:** the inverse edit put the `isinstance(u, list) and u and all(...)` condition and the `else "bad"` back.
**Restore receipt** (the restored lines, quoted from `review_record_session.py:253-254`):

```
    u = obs["tokensUnmeasured"]
    return "partial" if isinstance(u, list) and u and all(_int(x) and x >= 1 for x in u) else "bad"
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 3.44s
```

## G8. Account-check complete rule (`lib/review_record.py`, `_validate`)

- **Guarded element:** `review_record.py:1028`, `chk(c["complete"] is (c["runsWithoutFigure"] == 0 and c.get("runsPartial", 0) == 0), "sessionCost.complete")`.
- **Axis:** a `sessionCost` that says `complete: true` beside a partial run is review-account-invalid.
- **Detector:** `test_partial_cost_2514.py::test_t10_the_account_check_refuses_a_malformed_partial_session_cost[partial-but-complete]`.
- **Neutralization:** the check became `chk(c["complete"] is (c["runsWithoutFigure"] == 0), "sessionCost.complete")`, the rule without the partial term.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t10_the_account_check_refuses_a_malformed_partial_session_cost[partial-but-complete] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-19/test_t10_the_account_check_ref0')
cost = {'tokens': 10, 'minutes': 1.0, 'runs': 1, 'runsWithoutFigure': 0, ...}
detail = 'sessionCost.complete'

    @pytest.mark.parametrize("cost,detail", [(c, d) for _, c, d in CHECK_BAD], ids=[i for i, _, _ in CHECK_BAD])
    def test_t10_the_account_check_refuses_a_malformed_partial_session_cost(tmp_path, cost, detail):
        # axis: a sessionCost whose runsPartial is malformed, out of bound, or beside complete: true is review-account-invalid and nothing is posted
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2514_partial_cost.md
        fake = trr.Fake()
        out = rr.write(trr.put(tmp_path, trr.account(sessionCost=cost)), str(tmp_path), fake.readers())
>       assert out["ok"] is False and out["reason"] == "review-account-invalid" and out["detail"] == detail, out
E       AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/1', 'parts': 0, ...}
E       assert (True is False)

/home/user/wt-2514/plugins/superheroes/lib/tests/test_partial_cost_2514.py:206: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_partial_cost_2514.py::test_t10_the_account_check_refuses_a_malformed_partial_session_cost[partial-but-complete]
1 failed in 3.56s
```

**Restore:** the inverse edit put `and c.get("runsPartial", 0) == 0` back.
**Restore receipt** (the restored lines, quoted from `review_record.py:1027-1028`):

```
        # axis: complete is also false when any run is partial — see bite-proof record i2514_partial_cost
        chk(c["complete"] is (c["runsWithoutFigure"] == 0 and c.get("runsPartial", 0) == 0), "sessionCost.complete")
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 3.39s
```

## G9. Account-check `runsPartial` bound (`lib/review_record.py`, `_validate`)

- **Guarded element:** `review_record.py:1024-1025`, the `chk("runsPartial" not in c or (...), "sessionCost.runsPartial")` that requires an int of one or more with `runsWithoutFigure + runsPartial <= runs`.
- **Axis:** a `runsPartial` that is out of bound (here, more partial runs than runs) is review-account-invalid.
- **Detector:** `test_partial_cost_2514.py::test_t10_the_account_check_refuses_a_malformed_partial_session_cost[partial-over-the-runs]`.
- **Neutralization:** the two-line `chk(...)` for `sessionCost.runsPartial` was deleted (the `# axis:` comment above it was left in place).

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t10_the_account_check_refuses_a_malformed_partial_session_cost[partial-over-the-runs] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-21/test_t10_the_account_check_ref0')
cost = {'tokens': 10, 'minutes': 1.0, 'runs': 1, 'runsWithoutFigure': 0, ...}
detail = 'sessionCost.runsPartial'

    @pytest.mark.parametrize("cost,detail", [(c, d) for _, c, d in CHECK_BAD], ids=[i for i, _, _ in CHECK_BAD])
    def test_t10_the_account_check_refuses_a_malformed_partial_session_cost(tmp_path, cost, detail):
        # axis: a sessionCost whose runsPartial is malformed, out of bound, or beside complete: true is review-account-invalid and nothing is posted
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2514_partial_cost.md
        fake = trr.Fake()
        out = rr.write(trr.put(tmp_path, trr.account(sessionCost=cost)), str(tmp_path), fake.readers())
>       assert out["ok"] is False and out["reason"] == "review-account-invalid" and out["detail"] == detail, out
E       AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/1', 'parts': 0, ...}
E       assert (True is False)

/home/user/wt-2514/plugins/superheroes/lib/tests/test_partial_cost_2514.py:206: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_partial_cost_2514.py::test_t10_the_account_check_refuses_a_malformed_partial_session_cost[partial-over-the-runs]
1 failed in 3.61s
```

**Restore:** the inverse edit put the two-line `chk(...)` back below its `# axis:` comment.
**Restore receipt** (the restored lines, quoted from `review_record.py:1023-1025`):

```
        # axis: `runsPartial`, when written, is an int of one or more that with the runs lacking a figure fits the runs — see bite-proof record i2514_partial_cost
        chk("runsPartial" not in c or (_is_int(c["runsPartial"]) and c["runsPartial"] >= 1
                                      and c["runsWithoutFigure"] + c["runsPartial"] <= c["runs"]), "sessionCost.runsPartial")
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 3.87s
```

## G10. Measures `_session_cost` complete rule (`lib/review_measures.py`)

- **Guarded element:** `review_measures.py:161`, `sc["complete"] == (sc["runsWithoutFigure"] == 0 and sc.get("runsPartial", 0) == 0)`.
- **Axis:** the measures reader reads a `sessionCost` as well-formed only when `complete` is false beside a partial run.
- **Detector:** `test_partial_cost_2514.py::test_t11a_the_measures_reader_checks_runs_partial_and_the_complete_rule`.
- **Neutralization:** the term `and sc.get("runsPartial", 0) == 0` was dropped, leaving `sc["complete"] == (sc["runsWithoutFigure"] == 0)`.
- **How it went red:** with the term gone the reader rejects the well-formed partial record (`complete: False` beside a partial run no longer equals `runsWithoutFigure == 0`), so T11a fails at its first assertion (line 235); it would equally accept `complete: True` beside a partial run.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_t11a_the_measures_reader_checks_runs_partial_and_the_complete_rule ____

    def test_t11a_the_measures_reader_checks_runs_partial_and_the_complete_rule():
        # axis: the measures reader reads a sessionCost as well-formed only when complete is false beside a partial run and runsPartial is an int of one or more within the runs
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2514_partial_cost.md
        good = _psc(100, 1.5, by_seat=_SEC)
>       assert RM._session_cost({"sessionCost": good}) == good
E       AssertionError: assert None == {'tokens': 100, 'minutes': 1.5, 'runs': 1, 'runsWithoutFigure': 0, ...}
E        +  where None = <function _session_cost at 0x7f1f6d8aa3e0>({'sessionCost': {'tokens': 100, 'minutes': 1.5, 'runs': 1, 'runsWithoutFigure': 0, ...}})
E        +    where <function _session_cost at 0x7f1f6d8aa3e0> = RM._session_cost

/home/user/wt-2514/plugins/superheroes/lib/tests/test_partial_cost_2514.py:235: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_partial_cost_2514.py::test_t11a_the_measures_reader_checks_runs_partial_and_the_complete_rule
1 failed in 3.27s
```

**Restore:** the inverse edit put `and sc.get("runsPartial", 0) == 0` back.
**Restore receipt** (the restored lines, quoted from `review_measures.py:160-161`):

```
          # axis: a session with a partial run is never complete, so a record that says it is reads unmeasured — see bite-proof record i2514_partial_cost
          and sc["complete"] == (sc["runsWithoutFigure"] == 0 and sc.get("runsPartial", 0) == 0) and isinstance(sc.get("bySeat"), dict)
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 3.52s
```

## G11. Measures `prsLeftOut.partial` count (`lib/review_measures.py`, `compute`)

- **Guarded element:** `review_measures.py:398-399`, the `"partial": sum(any(_partial_session(...)) ...)` count of left-out PRs that hold a partial session.
- **Axis:** `prsLeftOut.<k>.partial` counts the left-out PRs that hold a session whose cost is partial.
- **Detector:** `test_partial_cost_2514.py::test_t11b_a_pr_whose_only_session_is_partial_is_left_out_and_counted_partial`.
- **Neutralization:** the two-line `sum(...)` expression became the constant `0` (`"partial": 0}`).

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t11b_a_pr_whose_only_session_is_partial_is_left_out_and_counted_partial _

    def test_t11b_a_pr_whose_only_session_is_partial_is_left_out_and_counted_partial():
        # axis: a PR holding a partial session stays unmeasured and prsLeftOut.<k>.partial counts the left-out PRs that hold one
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2514_partial_cost.md
        ci = [{"pr": n, "minutes": 1} for n in (1, 2, 3, 4)]
        partial = _psc(100, 1.5, by_seat=_SEC)
        row = RM.compute(_full(records=[_rec(1), _rec(2, sc=partial)], ciRuns=ci[:2]), FROM, UNTIL)
        cost = row["measures"]["reviewerCostPerPr"]
        assert cost["tokens"]["total"] == 100 and cost["minutes"]["total"] == 1.5
>       assert cost["prsLeftOut"]["tokens"] == {"count": 1, "why": RM.LEFT_OUT_WHY, "partial": 1}
E       AssertionError: assert {'count': 1, ... 'partial': 0} == {'count': 1, ... 'partial': 1}
E         
E         Omitting 2 identical items, use -vv to show
E         Differing items:
E         {'partial': 0} != {'partial': 1}
E         Use -v to get more diff

/home/user/wt-2514/plugins/superheroes/lib/tests/test_partial_cost_2514.py:258: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_partial_cost_2514.py::test_t11b_a_pr_whose_only_session_is_partial_is_left_out_and_counted_partial
1 failed in 3.91s
```

**Restore:** the inverse edit put the two-line `sum(...)` expression back in place of `0`.
**Restore receipt** (the restored lines, quoted from `review_measures.py:396-399`):

```
            # axis: `partial` counts the left-out PRs holding a session whose cost is partial, never more than `count` — see bite-proof record i2514_partial_cost
            out[k] = {"count": len(totals) - len(measured), "why": LEFT_OUT_WHY,
                      "partial": sum(any(_partial_session(_latest(recs)) for recs in _by_session(rs))
                                     for rs, t in zip(prs.values(), totals) if t is None)}
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 3.53s
```

## G12. Measures seat reason `cost-partial` (`lib/review_measures.py`, `compute`)

- **Guarded element:** `review_measures.py:456`, `why_not = "cost-partial" if s in part_blank and s not in other_blank and s != "unattributed" else "cost-not-recorded"`.
- **Axis:** a seat unmeasured only because every session that blanks it is partial-only reads `cost-partial`; any other blanking reads `cost-not-recorded`.
- **Detector:** `test_partial_cost_2514.py::test_t11c_a_seat_only_partial_sessions_blank_reads_cost_partial_and_any_other_blanking_does_not`.
- **Neutralization:** the line became `why_not = "cost-not-recorded"`, so the reason is always `cost-not-recorded`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t11c_a_seat_only_partial_sessions_blank_reads_cost_partial_and_any_other_blanking_does_not _

    def test_t11c_a_seat_only_partial_sessions_blank_reads_cost_partial_and_any_other_blanking_does_not():
        # axis: a seat unmeasured only because every session that blanks it is partial-only reads cost-partial; any other blanking reads cost-not-recorded
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2514_partial_cost.md
        partial = _psc(100, 1.5, by_seat=_SEC)
        row = RM.compute(_full(records=[_rec(1, sc=partial)]), FROM, UNTIL)
        seats, why = row["measures"]["seats"], _why(row)
        assert seats["security-reviewer"]["tokens"] == U and seats["security-reviewer"]["minutes"] == U
>       assert why["seats.security-reviewer.tokens"] == "cost-partial" and why["seats.security-reviewer.minutes"] == "cost-partial"
E       AssertionError: assert ('cost-not-recorded' == 'cost-partial'
E         
E         - cost-partial
E         + cost-not-recorded)

/home/user/wt-2514/plugins/superheroes/lib/tests/test_partial_cost_2514.py:280: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_partial_cost_2514.py::test_t11c_a_seat_only_partial_sessions_blank_reads_cost_partial_and_any_other_blanking_does_not
1 failed in 3.44s
```

**Restore:** the inverse edit put the `"cost-partial" if ... else "cost-not-recorded"` conditional back.
**Restore receipt** (the restored lines, quoted from `review_measures.py:455-456`):

```
                # axis: a seat blanked only by partial-only sessions reads `cost-partial`; any other blanking keeps `cost-not-recorded` — see bite-proof record i2514_partial_cost
                why_not = "cost-partial" if s in part_blank and s not in other_blank and s != "unattributed" else "cost-not-recorded"
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 4.04s
```

## G13. Wall-time check (`lib/engine_dispatch.py`, `_attempts_cost`)

- **Guarded element:** `engine_dispatch.py:7805-7806`, `if isinstance(secs, bool) or not isinstance(secs, (int, float)) or not 0 <= secs < float("inf"):` / `return None`, the check that runs before the usage read and leaves the run without a figure when an ended attempt carries no finite non-negative numeric `wallSeconds`. Added after G1-G12, on the file at the merge of main into this branch, so its `file:line` is that file's (G1-G12's `engine_dispatch.py` and `review_measures.py` numbers are those of the earlier files).
- **Axis:** an ended attempt with no wall time leaves the run without a figure, a usage total and a watchdog end notwithstanding.
- **Detector:** `test_partial_cost_2514.py::test_t12_an_ended_attempt_without_wall_seconds_leaves_the_run_without_a_figure`, both parametrized cases (`[plain]`: attempt 1 has no `wallSeconds` key, no watchdog marks, and a usage total of 40 tokens, then a clean measured retry of wall 30; `[watchdog]`: the same, with attempt 1's ended record also carrying `signalSource="silence-watchdog"` and a `silenceWatchdog` record). Driven at the `_attempts_cost` seam, read as `ED._attempts_cost(os.path.realpath(run_dir), ED._journal_state(records))`, not through `seam_cost` (whose `attempt-not-completed` assertion holds only when the last attempt is a watchdog end; here the last attempt is a clean retry). The test's own helper `_journal_without_first_wall_time` journals the run with `journal_run` and rewrites attempt 1's `attempt-ended` record without its `wallSeconds` key.
- **Neutralization:** the `return None` under that `if` became `secs = 0`, so a missing wall time reads as zero.

**Raw red** (exit 1; both cases):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_t12_an_ended_attempt_without_wall_seconds_leaves_the_run_without_a_figure[plain] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-34/test_t12_an_ended_attempt_with0')
over = {}

    @pytest.mark.parametrize("over", [{}, WATCHDOG], ids=["plain", "watchdog"])
    def test_t12_an_ended_attempt_without_wall_seconds_leaves_the_run_without_a_figure(tmp_path, over):
        # axis: an ended attempt with no wall time leaves the run without a figure, a usage total and a watchdog end notwithstanding
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2514_partial_cost.md
        run_dir = _journal_without_first_wall_time(tmp_path, [
            attempt(stream(input_tokens=30, output_tokens=10), 600, **over), attempt(stream(**RETRY), 30)])
        records, _ = ED._journal_read(run_dir)
        state = ED._journal_state(records)
        assert "wallSeconds" not in state["attempts"][1]["ended"] and state["attempts"][2]["ended"]["wallSeconds"] == 30
        assert (ED._silence_watchdog_end(state["attempts"][1]["ended"])) is bool(over)
>       assert ED._attempts_cost(os.path.realpath(run_dir), state) is None
E       AssertionError: assert {'tokens': 100, 'wallSeconds': 30, 'attempts': 2} is None
E        +  where {'tokens': 100, 'wallSeconds': 30, 'attempts': 2} = <function _attempts_cost at 0x7fefe2a1cea0>('/tmp/claude-0/pytest-of-root/pytest-34/test_t12_an_ended_attempt_with0/run', {'opened': {'kind': 'run-opened', 'runKind': 'review', 'engine': 'codex', 'roleKind': 'review', ...}, 'leaseToken': No...gid': None, 'ended': {'kind': 'attempt-ended', 'attempt': 2, 'exit': 0, 'timedOut': False, ...}}}, 'folded': None, ...})
E        +    where <function _attempts_cost at 0x7fefe2a1cea0> = ED._attempts_cost
E        +    and   '/tmp/claude-0/pytest-of-root/pytest-34/test_t12_an_ended_attempt_with0/run' = <function realpath at 0x7fefe3de5da0>('/tmp/claude-0/pytest-of-root/pytest-34/test_t12_an_ended_attempt_with0/run')
E        +      where <function realpath at 0x7fefe3de5da0> = <module 'posixpath' (frozen)>.realpath
E        +        where <module 'posixpath' (frozen)> = os.path

/home/user/wt-2514/plugins/superheroes/lib/tests/test_partial_cost_2514.py:331: AssertionError
_ test_t12_an_ended_attempt_without_wall_seconds_leaves_the_run_without_a_figure[watchdog] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-34/test_t12_an_ended_attempt_with1')
over = {'signalSource': 'silence-watchdog', 'silenceWatchdog': {'silentSeconds': 600.0, 'thresholdSeconds': 600, 'killAt': 1.0}}

    @pytest.mark.parametrize("over", [{}, WATCHDOG], ids=["plain", "watchdog"])
    def test_t12_an_ended_attempt_without_wall_seconds_leaves_the_run_without_a_figure(tmp_path, over):
        # axis: an ended attempt with no wall time leaves the run without a figure, a usage total and a watchdog end notwithstanding
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2514_partial_cost.md
        run_dir = _journal_without_first_wall_time(tmp_path, [
            attempt(stream(input_tokens=30, output_tokens=10), 600, **over), attempt(stream(**RETRY), 30)])
        records, _ = ED._journal_read(run_dir)
        state = ED._journal_state(records)
        assert "wallSeconds" not in state["attempts"][1]["ended"] and state["attempts"][2]["ended"]["wallSeconds"] == 30
        assert (ED._silence_watchdog_end(state["attempts"][1]["ended"])) is bool(over)
>       assert ED._attempts_cost(os.path.realpath(run_dir), state) is None
E       AssertionError: assert {'tokens': 100, 'wallSeconds': 30, 'attempts': 2} is None
E        +  where {'tokens': 100, 'wallSeconds': 30, 'attempts': 2} = <function _attempts_cost at 0x7fefe2a1cea0>('/tmp/claude-0/pytest-of-root/pytest-34/test_t12_an_ended_attempt_with1/run', {'opened': {'kind': 'run-opened', 'runKind': 'review', 'engine': 'codex', 'roleKind': 'review', ...}, 'leaseToken': No...gid': None, 'ended': {'kind': 'attempt-ended', 'attempt': 2, 'exit': 0, 'timedOut': False, ...}}}, 'folded': None, ...})
E        +    where <function _attempts_cost at 0x7fefe2a1cea0> = ED._attempts_cost
E        +    and   '/tmp/claude-0/pytest-of-root/pytest-34/test_t12_an_ended_attempt_with1/run' = <function realpath at 0x7fefe3de5da0>('/tmp/claude-0/pytest-of-root/pytest-34/test_t12_an_ended_attempt_with1/run')
E        +      where <function realpath at 0x7fefe3de5da0> = <module 'posixpath' (frozen)>.realpath
E        +        where <module 'posixpath' (frozen)> = os.path

/home/user/wt-2514/plugins/superheroes/lib/tests/test_partial_cost_2514.py:331: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_partial_cost_2514.py::test_t12_an_ended_attempt_without_wall_seconds_leaves_the_run_without_a_figure[plain]
FAILED plugins/superheroes/lib/tests/test_partial_cost_2514.py::test_t12_an_ended_attempt_without_wall_seconds_leaves_the_run_without_a_figure[watchdog]
2 failed in 3.79s
```

**Restore:** the inverse edit put `return None` back in place of `secs = 0`.
**Restore receipt** (the restored lines, quoted from `engine_dispatch.py:7805-7806`):

```
            if isinstance(secs, bool) or not isinstance(secs, (int, float)) or not 0 <= secs < float("inf"):
                return None
```

**Raw green** (exit 0; both cases):

```
..                                                                       [100%]
2 passed in 4.22s
```

## After every restore

The whole detector file, run once after the twelfth restore (`scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2514 -m pytest plugins/superheroes/lib/tests/test_partial_cost_2514.py -q`, exit 0):

```
............................                                             [100%]
28 passed in 4.35s
```

## Not proven (outside the declared set)

These tests carry no neutralization of their own; they are listed so nobody reads them as covered by this record: T1b (every unmeasured attempt named, ascending), T3 (only-`None` usage parts, the second route into G3's refusal), T3b (the `explicit` flag at `codex_usage_tokens` direct), T4 and T4b (a watchdog-ended attempt with a real or explicit-zero usage is a measured figure), T5b and T5c (the seam with every attempt unmeasured, and with one measured attempt among unmeasured ones), T7 (the watchdog-race attempt keeps today's rule), T9b (a well-formed `tokensUnmeasured` is partial), the other T9 cases `zero-attempt` and `string` and the other T10 cases (`partial-zero`, `partial-bool`, `partial-negative`, `partial-string`, `partial-with-unfigured-over-the-runs`), T10b (the account check accepts a well-formed partial `sessionCost` and the writer's own), and the finer branches of T11c beyond the first assertion that the G12 red reached.
