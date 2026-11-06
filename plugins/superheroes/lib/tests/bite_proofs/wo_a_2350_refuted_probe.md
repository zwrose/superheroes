# Bite-proof record — a refuted break-it probe never makes a finding owe a kept test (#2350)

Detector file: `plugins/superheroes/lib/tests/test_break_it_refuted_probe_2350.py` (11 tests), unedited between each red and its green. Every entry is a targeted, reversible edit to one production file (`plugins/superheroes/lib/round_driver.py`), restored by the inverse edit through the Edit tool (no `git checkout`, `restore`, `reset`, `stash`, and no shell edit). Command for every red and green: `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_refuted_probe_2350.py -q -p no:randomly`, run from the worktree root. Captures are the tail of the run's output (`tail -N`; N was at least the whole output except for the `UV_NATIVE_TLS` deprecation warning `uv` prints first, which is shown on a green capture and dropped from none). Pytest prints absolute temp paths and `spy = [...]` list reprs; they are shortened below with `...` where this record quotes only the decisive line. The G1 red capture was additionally cut to 220 columns per line (`cut -c1-220`), which only shortens long `spy`/`world` repr lines. No secret, token or private URL appears in any capture, so nothing was redacted.

The guarded-element set is the four the order declared (G1-G4); none is grouped. Each target string occurred exactly once in the file (the Edit tool refuses a non-unique match).

Detectors that carry a `# bites on:` line but are outside G1-G4 (T3 and T4, the sibling guard and the healthy case, and T2b/T2c, T6b) guard the unchanged kept check and the edges of the new branches; they were not neutralized separately (see *Not proven*).

## G1. The stamp write in `_fold_verifiers` (`round_driver.py`, the `for probe in ...breakItRuns` loop under the `refuted` disposition)

- **Axis:** a break-it run of a finding the verifier refuted this round is stamped `refutedProbe: true` (current round only), so the kept check can tell the probe's uncommitted test from a fixed finding's real one.
- **Detectors (expected red):** T1, T7.
- **Neutralization:** `probe[BREAK_IT_REFUTED_FIELD] = True` became `probe[BREAK_IT_REFUTED_FIELD] = False`.

**Raw red** (exit 1; decisive lines):

```
FF.....F..F                                                              [100%]
>       assert run[RD.BREAK_IT_REFUTED_FIELD] is True
E       assert False is True
/home/user/wt-2350/plugins/superheroes/lib/tests/test_break_it_refuted_probe_2350.py:132: AssertionError
>       assert second[RD.BREAK_IT_REFUTED_FIELD] is True
E       assert False is True
>       assert len(spy) == 1
E       AssertionError: assert 2 == 1
>       assert by_key[key][RD.BREAK_IT_REFUTED_FIELD] is True
E       assert False is True
FAILED ...test_break_it_refuted_probe_2350.py::test_t1_a_refuted_probe_kept_as_a_repeat_of_a_fixed_finding_owes_no_kept_test
FAILED ...test_break_it_refuted_probe_2350.py::test_t2a_the_round_one_run_is_checked_when_its_test_is_kept
FAILED ...test_break_it_refuted_probe_2350.py::test_t5_a_newer_real_fixed_disposition_puts_the_stamped_run_back_under_the_check
FAILED ...test_break_it_refuted_probe_2350.py::test_t7_only_the_refuted_findings_current_round_runs_are_stamped
4 failed, 7 passed in 9.16s
```

T1 and T7 are red as expected; T2a and T5 also go red (with no stamp the skip never fires).

**Restore:** the inverse Edit, `= False` back to `= True`.

**Restore receipt:**

```
$ git status --porcelain -- plugins/superheroes/lib/round_driver.py
 M plugins/superheroes/lib/round_driver.py
$ git diff -U0 -- plugins/superheroes/lib/round_driver.py | grep -n "BREAK_IT_REFUTED_FIELD\] = "
12:+                        probe[BREAK_IT_REFUTED_FIELD] = True
```

The file is modified relative to the base only by this work order's own change; the restored line reads `probe[BREAK_IT_REFUTED_FIELD] = True`.

**Raw green:**

```
...........                                                              [100%]
11 passed in 10.06s
```

## G2. The skip in `_break_it_kept_step` (`round_driver.py`, `if (run.get(BREAK_IT_REFUTED_FIELD) is True and isinstance(held, dict) ...`)

- **Axis:** a refuted probe's run is never the record the kept check runs while the finding's fixed disposition stands on a kept repeat.
- **Detectors (expected red):** T1, T2(a).
- **Neutralization:** `if (run.get(BREAK_IT_REFUTED_FIELD) is True and isinstance(held, dict)` became `if (False and run.get(BREAK_IT_REFUTED_FIELD) is True and isinstance(held, dict)`, so a stamped run is never skipped. With this edit the kept step behaves as the base code does, so this red run is also the demonstration that T1 fails without the fix.

**Raw red** (exit 1; decisive lines):

```
FF.....FF..                                                              [100%]
>       assert RD._break_it_kept_step(world.state, world.state["config"]) is False
E       AssertionError: assert True is False
/home/user/wt-2350/plugins/superheroes/lib/tests/test_break_it_refuted_probe_2350.py:134: AssertionError
>       assert call[3]["sha256"] == first["sha256"] == _sha(TL._TEST_FAILING)
E       AssertionError: assert '360bb033e209...b51a196f5da51' == '1805ff558ae6...b390728cf7b56'
>       assert len(spy) == 1
E       AssertionError: assert 2 == 1
>       assert spy == []
E       AssertionError: assert [('/tmp/claud...ce.py', ...})] == []
FAILED ...::test_t1_a_refuted_probe_kept_as_a_repeat_of_a_fixed_finding_owes_no_kept_test
FAILED ...::test_t2a_the_round_one_run_is_checked_when_its_test_is_kept
FAILED ...::test_t5_a_newer_real_fixed_disposition_puts_the_stamped_run_back_under_the_check
FAILED ...::test_t6_a_refuted_probe_after_a_restore_fails_closed
4 failed, 7 passed in 9.80s
```

T1 parks (`True`, the base behaviour) and T2a checks the probe's round-2 sha (`360bb033...`) instead of round 1's (`1805ff55...`), as expected; T5 and T6 go red too.

**Restore:** the inverse Edit, `if (False and run.get(` back to `if (run.get(`.

**Restore receipt:**

```
$ git status --porcelain -- plugins/superheroes/lib/round_driver.py
 M plugins/superheroes/lib/round_driver.py
$ git diff -U0 -- plugins/superheroes/lib/round_driver.py | grep -n "BREAK_IT_REFUTED_FIELD) is True"
48:+        if (run.get(BREAK_IT_REFUTED_FIELD) is True and isinstance(held, dict)
```

**Raw green:**

```
...........                                                              [100%]
11 passed in 10.25s
```

## G3. The `repeatKept` condition on the skip (`round_driver.py`, `and isinstance(held.get("repeatKept"), dict)`)

- **Axis:** the skip needs the ledger row's `repeatKept`, so a newer real disposition (which pops it) puts a stamped run back under the check.
- **Detector (expected red):** T5.
- **Neutralization:** `and isinstance(held.get("repeatKept"), dict)):` became `and True):`, so the skip fires on the stamp alone.

**Raw red** (exit 1):

```
.......F...                                                              [100%]
>       assert RD._break_it_kept_step(world.state, world.state["config"]) is True
E       AssertionError: assert False is True
/home/user/wt-2350/plugins/superheroes/lib/tests/test_break_it_refuted_probe_2350.py:226: AssertionError
FAILED plugins/superheroes/lib/tests/test_break_it_refuted_probe_2350.py::test_t5_a_newer_real_fixed_disposition_puts_the_stamped_run_back_under_the_check
1 failed, 10 passed in 10.43s
```

**Restore:** the inverse Edit, `and True):` back to `and isinstance(held.get("repeatKept"), dict)):`.

**Restore receipt:**

```
$ git status --porcelain -- plugins/superheroes/lib/round_driver.py
 M plugins/superheroes/lib/round_driver.py
$ git diff -U0 -- plugins/superheroes/lib/round_driver.py | grep -n 'held.get("repeatKept")'
49:+                and isinstance(held.get("repeatKept"), dict)):
```

**Raw green:**

```
...........                                                              [100%]
11 passed in 10.10s
```

## G4. The restore-shadowing fail-closed row (`round_driver.py`, `if (key in skipped and restore_round is not None ...`)

- **Axis:** a refuted probe raised after the chosen run's test restore re-seeds the carried block the restored bytes are read from, so the check fails closed instead of reading them.
- **Detector (expected red):** T6.
- **Neutralization:** `if (key in skipped and restore_round is not None` became `if (False and key in skipped and restore_round is not None`, so the branch never runs.

**Raw red** (exit 1):

```
........F..                                                              [100%]
>       assert spy == []
E       AssertionError: assert [('/tmp/claud...ce.py', ...})] == []
E         Left contains one more item: ('/tmp/claude-0/pytest-of-root/pytest-9/test_t6_a_refuted_probe_after_0/repo', '74567a536ade20d330f4e51d3d9bf21a002d41...sts/test_charge_once.py', 'command': ...)
/home/user/wt-2350/plugins/superheroes/lib/tests/test_break_it_refuted_probe_2350.py:254: AssertionError
FAILED plugins/superheroes/lib/tests/test_break_it_refuted_probe_2350.py::test_t6_a_refuted_probe_after_a_restore_fails_closed
1 failed, 10 passed in 9.65s
```

**Restore:** the inverse Edit, `if (False and key in skipped` back to `if (key in skipped`.

**Restore receipt:**

```
$ git status --porcelain -- plugins/superheroes/lib/round_driver.py
 M plugins/superheroes/lib/round_driver.py
$ git diff -U0 -- plugins/superheroes/lib/round_driver.py | grep -n 'key in skipped and restore_round'
67:+        if (key in skipped and restore_round is not None and restore_round >= latest_round[key]
```

**Raw green:**

```
...........                                                              [100%]
11 passed in 9.57s
```

## Not proven

Outside the declared set, so no neutralization was run for them: the `not-required` / `refuted-probe` row's literal values (asserted exactly by T1), the `restore_round >= latest_round[key]` and `skipped[key][1] > restore_round` terms of the G4 condition (T6 and T6b exercise both sides of the second term; the first has no dedicated test), the current-round-only scope of the stamp write (T7 asserts that an earlier round's run for the refuted key stays unstamped, but no neutralization widening the write to every round was run), and the T3/T4 sibling guards, which assert the unchanged kept check and were not neutralized.
