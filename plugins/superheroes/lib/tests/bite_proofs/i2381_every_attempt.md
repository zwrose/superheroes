# Bite-proof record — a review's `sessionCost` counts every attempt of every run (#2381)

Detector file: `plugins/superheroes/lib/tests/test_session_cost_every_attempt_2381.py`, unedited between each red and its green. Every entry is a targeted, reversible edit to one production file, made and undone with the edit tool (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2381 -m pytest '<exact node id>' -q`, one test node each, output captured whole; the `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out of each capture, and the `tmp_path` directory names are as the runner printed them (no secret, token, URL or personal data appears in any capture, so nothing is redacted). The five guarded elements are the five the order declared; none is grouped. Each target occurred exactly once in the edit's `old_string` (the edit tool refuses a non-unique match).

The detectors the entries name are the tests that carry a `# bite-proof:` line (T1, T2, T3, T5, T7). T4 and T6 carry an `# axis:` line only; their elements are listed under *Not proven* below.

## 1. Figure source (`lib/review_record_session.py`, `_session_cost`)

- **Axis:** a run's session figure is the engine record's every-attempt total (`attemptsCost`); a record with only a last-attempt `observation` gives no figure.
- **Detector:** `test_session_cost_every_attempt_2381.py::test_t7_a_record_with_only_an_observation_gives_no_figure[attemptsCost-none]`.
- **Neutralization:** `seen[n] = rec.get("attemptsCost")` became `seen[n] = rec.get("observation")`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t7_a_record_with_only_an_observation_gives_no_figure[attemptsCost-none] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-1/test_t7_a_record_with_only_an_0')
engine_record = {'source': 'codex', 'engineModel': 'gpt-5.6-sol', 'viewHeadSha': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'observation': {'tokens': 100, 'wallSeconds': 120}, ...}

    @pytest.mark.parametrize("engine_record", [
        dict(GOOD_RUN, runnerNonce=NONCE, attemptsCost=None),
        dict(GOOD_RUN, runnerNonce=NONCE),
    ], ids=["attemptsCost-none", "attemptsCost-absent"])
    def test_t7_a_record_with_only_an_observation_gives_no_figure(tmp_path, engine_record):
        # axis: the session figure comes from the every-attempt total, never from the last attempt's observation
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2381_every_attempt.md
        assert engine_record["observation"] == {"tokens": 100, "wallSeconds": 120}
        cost = session_cost(tmp_path, engine_record)
>       assert (cost["tokens"], cost["runs"], cost["runsWithoutFigure"], cost["complete"]) == (0, 1, 1, False)
E       assert (100, 1, 0, True) == (0, 1, 1, False)
E         
E         At index 0 diff: 100 != 0
E         Use -v to get more diff

/home/user/wt-2381/plugins/superheroes/lib/tests/test_session_cost_every_attempt_2381.py:154: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_session_cost_every_attempt_2381.py::test_t7_a_record_with_only_an_observation_gives_no_figure[attemptsCost-none]
1 failed in 4.17s
```

**Restore:** the inverse edit put `seen[n] = rec.get("attemptsCost")` back.
**Restore receipt** (the restored line, quoted from `review_record_session.py:262`): `            seen[n] = rec.get("attemptsCost")`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 4.34s
```

## 2. Every-attempt sum (`lib/engine_dispatch.py`, `_attempts_cost`)

- **Axis:** a run's figure is the sum over every attempt its engine journal shows, a timed-out or retried attempt included.
- **Detector:** `test_session_cost_every_attempt_2381.py::test_t1_a_timed_out_first_attempt_and_a_clean_retry_are_summed`.
- **Neutralization:** `for att in sorted(attempts):` became `for att in sorted(attempts)[-1:]:`, so only the last attempt is read.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_t1_a_timed_out_first_attempt_and_a_clean_retry_are_summed ________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-3/test_t1_a_timed_out_first_atte0')

    def test_t1_a_timed_out_first_attempt_and_a_clean_retry_are_summed(tmp_path):
        # axis: a run's figure is the sum over every attempt its engine journal shows
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2381_every_attempt.md
        record = execution_record(tmp_path, [
            attempt(stream(input_tokens=30, output_tokens=10), 900, **TIMED_OUT),
            attempt(stream(input_tokens=50, cached_input_tokens=0, output_tokens=10), 30)])
>       assert record["attemptsCost"] == {"tokens": 100, "wallSeconds": 930, "attempts": 2}
E       AssertionError: assert {'tokens': 60...'attempts': 2} == {'tokens': 10...'attempts': 2}
E         
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'wallSeconds': 30} != {'wallSeconds': 930}
E         {'tokens': 60} != {'tokens': 100}
E         Use -v to get more diff

/home/user/wt-2381/plugins/superheroes/lib/tests/test_session_cost_every_attempt_2381.py:93: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_session_cost_every_attempt_2381.py::test_t1_a_timed_out_first_attempt_and_a_clean_retry_are_summed
1 failed in 4.76s
```

**Restore:** the inverse edit put `for att in sorted(attempts):` back.
**Restore receipt** (the restored line, quoted from `engine_dispatch.py:7639`): `        for att in sorted(attempts):`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 4.75s
```

## 3. Missing-usage strictness (`lib/engine_adapter.py`, `codex_usage_tokens`)

- **Axis:** an attempt whose stdout shows no token usage has no token figure (None), never a zero, and so leaves its run without one.
- **Detector:** `test_session_cost_every_attempt_2381.py::test_t2_an_attempt_with_no_usage_leaves_the_run_without_a_figure`.
- **Neutralization:** in `codex_usage_tokens`, the no-usage branch `if last_usage is None: return None` became `return 0`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_t2_an_attempt_with_no_usage_leaves_the_run_without_a_figure _______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-5/test_t2_an_attempt_with_no_usa0')

    def test_t2_an_attempt_with_no_usage_leaves_the_run_without_a_figure(tmp_path):
        # axis: an attempt whose stdout shows no token usage leaves the run without a figure, never a zero
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2381_every_attempt.md
        record = execution_record(tmp_path, [
            attempt(stream(events=False), 900, **TIMED_OUT),
            attempt(stream(input_tokens=50, output_tokens=10), 30)])
>       assert record["attemptsCost"] is None
E       AssertionError: assert {'tokens': 60, 'wallSeconds': 930, 'attempts': 2} is None

/home/user/wt-2381/plugins/superheroes/lib/tests/test_session_cost_every_attempt_2381.py:104: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_session_cost_every_attempt_2381.py::test_t2_an_attempt_with_no_usage_leaves_the_run_without_a_figure
1 failed in 4.24s
```

**Restore:** the inverse edit put `return None` back in the no-usage branch.
**Restore receipt** (the restored lines, quoted from `engine_adapter.py:1199-1200`): `        if last_usage is None:` / `            return None`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 4.35s
```

## 4. Missing end (`lib/engine_dispatch.py`, `_attempts_cost`)

- **Axis:** an attempt the journal never ended has no wall-time figure and leaves its run without a figure.
- **Detector:** `test_session_cost_every_attempt_2381.py::test_t3_an_attempt_the_journal_never_ended_leaves_the_run_without_a_figure`.
- **Neutralization:** in `_attempts_cost`, under `if not isinstance(ended, dict):`, `return None` became `continue`, so an attempt with no `ended` is skipped.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_t3_an_attempt_the_journal_never_ended_leaves_the_run_without_a_figure __

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-7/test_t3_an_attempt_the_journal0')

    def test_t3_an_attempt_the_journal_never_ended_leaves_the_run_without_a_figure(tmp_path):
        # axis: an attempt with no attempt-ended record has no wall-time figure and leaves the run without one
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2381_every_attempt.md
        record = execution_record(tmp_path, [
            attempt(stream(input_tokens=30, output_tokens=10), None, ended=False),
            attempt(stream(input_tokens=50, output_tokens=10), 30)])
>       assert record["attemptsCost"] is None
E       AssertionError: assert {'tokens': 60, 'wallSeconds': 30, 'attempts': 2} is None

/home/user/wt-2381/plugins/superheroes/lib/tests/test_session_cost_every_attempt_2381.py:115: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_session_cost_every_attempt_2381.py::test_t3_an_attempt_the_journal_never_ended_leaves_the_run_without_a_figure
1 failed in 4.39s
```

**Restore:** the inverse edit put `return None` back.
**Restore receipt** (the restored lines, quoted from `engine_dispatch.py:7642-7643`): `            if not isinstance(ended, dict):` / `                return None`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 4.18s
```

## 5. Negative part (`lib/engine_adapter.py`, `codex_usage_tokens`)

- **Axis:** a token part that is not a non-negative int invalidates its attempt's token figure (None), and so its run's.
- **Detector:** `test_session_cost_every_attempt_2381.py::test_t5_a_negative_usage_part_leaves_the_run_without_a_figure`.
- **Neutralization:** the part check `if not isinstance(val, int) or isinstance(val, bool) or val < 0:` became `if not isinstance(val, int) or isinstance(val, bool):`, so a negative int is accepted.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_t5_a_negative_usage_part_leaves_the_run_without_a_figure _________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-9/test_t5_a_negative_usage_part_0')

    def test_t5_a_negative_usage_part_leaves_the_run_without_a_figure(tmp_path):
        # axis: a token part that is not a non-negative int invalidates its attempt and so the run
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2381_every_attempt.md
        bad = stream(input_tokens=-5, output_tokens=10)
>       assert EA.codex_usage_tokens(bad) is None
E       assert 5 is None
E        +  where 5 = <function codex_usage_tokens at 0x7f7d7260fb00>('{"type": "thread.started", "thread_id": "t"}\n{"type": "turn.started"}\n{"type": "turn.completed", "usage": {"input_tokens": -5, "output_tokens": 10}}')
E        +    where <function codex_usage_tokens at 0x7f7d7260fb00> = EA.codex_usage_tokens

/home/user/wt-2381/plugins/superheroes/lib/tests/test_session_cost_every_attempt_2381.py:131: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_session_cost_every_attempt_2381.py::test_t5_a_negative_usage_part_leaves_the_run_without_a_figure
1 failed in 4.30s
```

**Restore:** the inverse edit put `or val < 0` back.
**Restore receipt** (the restored line, quoted from `engine_adapter.py:1206`): `            if not isinstance(val, int) or isinstance(val, bool) or val < 0:`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 4.20s
```

## Not proven (outside the declared set)

These tests carry no neutralization of their own; they are listed so nobody reads them as covered by this record: T4 (one clean attempt gives the figure its `observation` gives), T6 (an explicit zero usage is a figure), T7's `attemptsCost-absent` case (the same element as entry 1, not run separately), and the other fail-closed edges of `_attempts_cost` that no test drives (an empty attempts map, a non-codex engine, a missing, bool, negative or non-finite `wallSeconds`, an unreadable stdout, a bool or non-int usage part).
