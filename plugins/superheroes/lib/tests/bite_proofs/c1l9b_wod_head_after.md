# C1-L9b WO-D bite-proof: a re-run whose head moved during it records where it ended

**Provenance:** `plugins/superheroes/lib/round_driver.py` (`_fold_verify`) and `plugins/superheroes/lib/review_record.py` (`_moved_heads`), with `plugins/superheroes/lib/tests/test_verify_rerun_ufr3.py` and `plugins/superheroes/lib/tests/test_review_record_rerun_heads.py`. Each neutralization was applied as a targeted edit and undone by the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Runner command: `timeout 600 scripts/pinned-python -B -X pycache_prefix=/home/user/superheroes/.git/pyc-woD -m pytest <node> -q -p no:cacheprovider`. Captures are the runner's own output with the `UV_NATIVE_TLS` deprecation warning line dropped; nothing else was cut. No secrets, tokens or private URLs appear in them.

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| G1 | `round_driver._fold_verify`, the `headAfter` assignment on the second run | a re-run whose own head moved records the head it ended at | `test_verify_rerun_ufr3.py::test_edge4_a_re_run_that_straddled_a_head_change_records_where_it_ended` |
| G2 | `review_record._moved_heads`, the `headAfter` read | a re-run that ended at another head is never called unchanged code | `test_review_record_rerun_heads.py::test_1b_a_second_run_that_ended_at_another_head_adds_the_suffix` |

The fail-closed edges (unknown head on either side never counts as moved; equal heads never count as moved; `headAfter` written only for a moved second run) are pinned by tests in the same files (`test_edge10_a_passing_re_run_…`, `test_1c_…`, the first run's missing `headAfter` key in the G1 test); they have no neutralization of their own in this order's declared set and are not claimed as proven here.

### G1 — the `headAfter` assignment

- **site:** `plugins/superheroes/lib/round_driver.py`, `_fold_verify`, inside `if moved:`
- **neutralization:** replace `            second_run["headAfter"] = artifact.get("headShaAfter")` with `            pass`
- **raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_edge4_a_re_run_that_straddled_a_head_change_records_where_it_ended ____

    def test_edge4_a_re_run_that_straddled_a_head_change_records_where_it_ended():
        # axis: a re-run whose own head moved records where it ended — see bite-proof record c1l9b_wod_head_after
        state = _state()
        _fold(state, _artifact("fail", head=H1))
        _fold(state, _artifact("pass", head=H1, after=H2))
    
        _halted_with(
            state,
            "verify re-run ran at a different head (%s then %s) — halt, certification withheld" % (H1, H2),
            "verify-rerun-head-moved")
        first, second = _runs(state)
>       assert second["head"] == H1 and second["headAfter"] == H2
                                        ^^^^^^^^^^^^^^^^^^^
E       KeyError: 'headAfter'

/home/user/wt-2260-woD/plugins/superheroes/lib/tests/test_verify_rerun_ufr3.py:202: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_verify_rerun_ufr3.py::test_edge4_a_re_run_that_straddled_a_head_change_records_where_it_ended
1 failed in 1.22s
```

- **restore:** inverse edit. **restore receipt**, the restored lines (`grep -n -B2` at lines 6115-6117):

```
6115-        if moved:
6116-            # axis: a re-run whose own head moved records where it ended, so the record never calls it unchanged code — see bite-proof record c1l9b_wod_head_after
6117:            second_run["headAfter"] = artifact.get("headShaAfter")
```

- **raw green:** `.  [100%]` / `1 passed in 1.12s`
- **verdict:** RED->GREEN

### G2 — the `headAfter` read in `_moved_heads`

- **site:** `plugins/superheroes/lib/review_record.py`, `_moved_heads`
- **neutralization:** replace `    after = runs[1].get("headAfter")` with `    after = None` (the helper then ignores `headAfter`)
- **raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_1b_a_second_run_that_ended_at_another_head_adds_the_suffix ________

    def test_1b_a_second_run_that_ended_at_another_head_adds_the_suffix():
        # axis: the second run's end head is its headAfter when it moved during the run
        runs = [run(code=1, head=H1, headSource="run"), run(code=0, head=H1, headSource="run", headAfter=H2)]
        full, compact = rerun_lines([check(round=2, check="pytest -q tests/x.py", runs=runs)])
>       assert full == TODAY_FULL + SUFFIX
E       AssertionError: assert 'Re-run after...) then passed' == 'Re-run after...nchanged code'
E         
E         Skipping 92 identical leading characters in diff, use -v to show
E         - then passed — the second run was at a different head (111111111111 then 222222222222), not on unchanged code
E         + then passed

/home/user/wt-2260-woD/plugins/superheroes/lib/tests/test_review_record_rerun_heads.py:52: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_rerun_heads.py::test_1b_a_second_run_that_ended_at_another_head_adds_the_suffix
1 failed in 1.08s
```

- **restore:** inverse edit. **restore receipt**, the restored lines (`grep -n -B2 -A5` at lines 1819-1826):

```
1819:    first, second = runs[0].get("head"), runs[1].get("head")
1820:    # axis: the second run's end head is its headAfter when it moved during the run — see bite-proof record c1l9b_wod_head_after
1821:    after = runs[1].get("headAfter")
1822:    if isinstance(after, str) and after:
1823:        second = after
1824:    if not (isinstance(first, str) and first and isinstance(second, str) and second and first != second):
1825:        return None
1826:    return first, second
```

- **raw green:** `.  [100%]` / `1 passed in 0.98s`
- **verdict:** RED->GREEN
