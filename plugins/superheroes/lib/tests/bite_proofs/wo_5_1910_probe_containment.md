# WO-5 (#1910) bite-proof — the readiness probe runs inside the same containment as the test

**Status: INCOMPLETE, unadjudicated.** B1's red was observed; its green half FAILED in the write sandbox (the sandbox cannot reap detached workers, see below); B2 was not run. The orchestrator owns the outstanding receipts and re-runs both from its own shell.

**Provenance:** claude / sonnet-5.5 (implementer, WO-5), `plugins/superheroes/lib/break_it.py`; detector file `plugins/superheroes/lib/tests/test_break_it_probe_1910.py`.

Declared guarded-element set (from the order): **B1, B2**.

| ID | Guarded element | Axis | Proving node |
|---|---|---|---|
| B1 | the probe runs through `_run_contained` (`_run_in_copy`, the `if interpreter:` block) | a detached worker the probe's launcher spawns is reaped, like the test's | `test_break_it_probe_1910.py::test_e1_the_probes_detached_worker_is_gone_after_run_one` |
| B2 | the trim in `_TailDrain.run` (`if len(self.buf) > OUTPUT_TAIL_BYTES:`) | the probe's output is bounded while it is collected | `test_break_it_probe_1910.py::test_e2_a_launcher_that_prints_forever_records_a_bounded_tail` |

## B1

**neutralization** (`break_it.py`, the probe call site): the `_run_contained([interpreter, "-c", "pass"], env, copy, repo_root, uuid.uuid4().hex, timeout)` call replaced by a direct `subprocess.Popen([interpreter, "-c", "pass"], cwd=copy, env=_clean_env(env, repo_root), stdin=DEVNULL, stdout=PIPE, stderr=STDOUT, start_new_session=True)` with `communicate(timeout=timeout)` and `_kill_group` only (no reaper, no token sweep, no directory sweep).

**raw red** (exit 1; `pytest -q -p no:cacheprovider <node>`):
```
F                                                                        [100%]
>           assert TB._gone(pid), "the probe's detached worker outlived run_one"
E           AssertionError: the probe's detached worker outlived run_one
E           assert False
E            +  where False = <function _gone at 0x7fb8ab980b80>(48)
FAILED plugins/superheroes/lib/tests/test_break_it_probe_1910.py::test_e1_the_probes_detached_worker_is_gone_after_run_one
1 failed in 10.87s
```
(The traceback body is trimmed here to the decisive lines; the full output is in the dispatch return.)

An earlier red attempt, before the fixture's worker released its stdio, read GREEN (`1 passed in 60.45s`): the old probe's `communicate` waited out the worker's 60 s sleep on the held pipe. The fixture was fixed (the worker's stdin, stdout and stderr go to `DEVNULL`) and the red above is the run after that fix.

**restore:** the inverse edit (the direct-Popen block replaced by the `_run_contained` call).

**restored lines:**
```
645:        failed, timed, status, tail = _run_contained(
646:            [interpreter, "-c", "pass"], env, copy, repo_root, uuid.uuid4().hex, timeout)
```

**raw green: FAILED in the write sandbox** (exit 1):
```
F                                                                        [100%]
>           assert TB._gone(pid), "the probe's detached worker outlived run_one"
E           AssertionError: the probe's detached worker outlived run_one
E           assert False
E            +  where False = <function _gone at 0x7f46cd670ae0>(52)
FAILED plugins/superheroes/lib/tests/test_break_it_probe_1910.py::test_e1_the_probes_detached_worker_is_gone_after_run_one
1 failed in 10.56s
```
Context, not a verdict: the pre-existing `test_break_it.py::test_t9_run_one_kills_a_lingering_worker[True-False]` and `[True-True]` also failed in this sandbox, on the restored (contained) code, with `the lingering worker outlived run_one`; only `[False-False]` passed. So detached-worker reaping cannot be observed here, and this red/green pair does not discriminate B1 in this environment. Whether those two failed on the base revision was not measured.

## B2

**Not run.** The order says to stop and report when a green half fails; B1's did. Outstanding: neutralize the `if len(self.buf) > OUTPUT_TAIL_BYTES:` trim in `_TailDrain.run` so it never trims, run `test_e2_a_launcher_that_prints_forever_records_a_bounded_tail` red, restore, run green. Owner: the orchestrator.
