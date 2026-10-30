# C1-L8a repeat-marks module bite-proof

Detector: `plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py` (58 tests). Five guarded elements, M1 to
M5, declared by the order. One neutralization, one red and one green per element, each by a targeted edit undone by
the inverse edit, detector unedited. Every run used this command from the worktree root:

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-c1l8a -m pytest plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py -q -n 4
```

Redaction: none needed; the captures hold no secrets, tokens or private URLs. The `UV_NATIVE_TLS` warning line and the
`bringing up nodes...` lines are kept as printed (the red captures below drop the per-test `E +` expansion lines of two
long assertion dumps; each dropped part is marked).

Restore receipt shape: `repeat_marks.py` also carries this layer's uncommitted changes, so `git status --porcelain`
reads ` M` before and after every neutralization and cannot show the restore. The receipt is the restored lines quoted
back from the file, plus a green run of the whole detector.

## M1 — the unknown-ref refusal in `grouping_fault`

**Guarded element:** `plugins/superheroes/lib/repeat_marks.py` `grouping_fault`, the `repeat_ref` return. Axis: a group
whose `repeatOf` is not an `eN` ref of the order's pool is refused, never applied.

**Neutralization:** `if ref is not None and (not isinstance(ref, str) or ref not in refs):` became
`if False and ref is not None and (not isinstance(ref, str) or ref not in refs):`.

**Raw red** (1 failed, 57 passed):

```
.........................................................F               [100%]
=================================== FAILURES ===================================
_____ test_m1_a_repeat_name_that_is_not_an_earlier_finding_ref_is_refused ______

    def test_m1_a_repeat_name_that_is_not_an_earlier_finding_ref_is_refused():
        pool = _fault_pool()
>       assert RM.grouping_fault([{"id": "v0"}], [], [_group("v0", ref="e9")], pool) == {
            "kind": "repeat_ref", "member_id": "e9", "index": 0}
E       AssertionError: assert None == {'kind': 'repeat_ref', 'member_id': 'e9', 'index': 0}

plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py:416: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py::test_m1_a_repeat_name_that_is_not_an_earlier_finding_ref_is_refused
1 failed, 57 passed in 0.59s
```

**Restore:** inverse edit, removed `False and `.

**Restore receipt:** restored lines, `repeat_marks.py:251-252`:

```python
        if ref is not None and (not isinstance(ref, str) or ref not in refs):
            return {"kind": "repeat_ref", "member_id": ref, "index": index}
```

**Raw green:**

```
..........................................................               [100%]
58 passed in 0.61s
```

## M2 — refuted ids set aside before survivor coverage in `grouping_fault`

**Guarded element:** `grouping_fault`, the `refuted_ids` set (`repeat_marks.py:244`). Axis: a refuted staged id in a
group is carried (for its repeat mark) and set aside before survivor coverage is checked, so it is never an `extra`
member.

**Neutralization:** `refuted_ids = {r["id"] for r in refuted or () if ...}` became
`refuted_ids = {r["id"] for r in () if ...}` (the refuted list is never read).

**Raw red** (2 failed, 56 passed):

```
...............................................F...F......               [100%]
=================================== FAILURES ===================================
____ test_m2_a_refuted_id_in_a_group_is_set_aside_before_survivor_coverage _____

    def test_m2_a_refuted_id_in_a_group_is_set_aside_before_survivor_coverage():
        survivors, refuted = [{"id": "v0"}], [{"id": "v1"}]
>       assert RM.grouping_fault(survivors, refuted, [_group("v0", "v1")], []) is None
E       AssertionError: assert {'kind': 'extra', 'member_id': 'v1'} is None

plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py:430: AssertionError
_ test_a_group_of_refuted_ids_alone_is_accepted_beside_survivors_and_without_any _

    def test_a_group_of_refuted_ids_alone_is_accepted_beside_survivors_and_without_any():
        pool = _fault_pool()
>       assert RM.grouping_fault([{"id": "v0"}], [{"id": "v1"}], [_group("v0"), _group("v1", ref="e1", group_id="b")],
                                 pool) is None
E       AssertionError: assert {'kind': 'extra', 'member_id': 'v1'} is None

plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py:446: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py::test_m2_a_refuted_id_in_a_group_is_set_aside_before_survivor_coverage
FAILED plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py::test_a_group_of_refuted_ids_alone_is_accepted_beside_survivors_and_without_any
2 failed, 56 passed in 0.75s
```

(The `E +  where ...` expansion lines are dropped from both failures.)

**Restore:** inverse edit, `() ` back to `refuted or () `.

**Restore receipt:** restored line, `repeat_marks.py:244`:

```python
    refuted_ids = {r["id"] for r in refuted or () if isinstance(r, dict) and isinstance(r.get("id"), str)}
```

**Raw green:**

```
..........................................................               [100%]
58 passed in 0.67s
```

## M3 — the exact-identity floor, exact before judge, in `mark_repeats`

**Guarded element:** `mark_repeats` (`repeat_marks.py:227`) over `exact_match`. Axis: a finding whose identity key
equals an earlier finding's is marked a repeat of that finding, whatever ref the judge named.

**Neutralization:** `entry = exact_match(finding, pool)` became
`entry = None if refs.get(sid) in by_ref else exact_match(finding, pool)` (the judge's name is read first and, when it
resolves, the exact match is skipped).

**Raw red** (1 failed, 57 passed):

```
..................................................F.......               [100%]
=================================== FAILURES ===================================
_______________ test_m3_exact_identity_wins_over_the_judges_name _______________

    def test_m3_exact_identity_wins_over_the_judges_name():
        craft, fixed = _raw("craft A", line=1), _raw("fixed B", line=2)
        pool = _pool((craft, "craft"), (fixed, "fixed"))
        staged = [dict(craft, id="v0")]
        marks = RM.mark_repeats(staged, pool, {"v0": "e2"})            # the judge names the fixed finding
>       assert marks == {"v0": (pool[0], "exact")}
E       AssertionError: assert {'v0': ({'sou.....}, 'judge')} == {'v0': ({'sou.....}, 'exact')}

plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py:393: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py::test_m3_exact_identity_wins_over_the_judges_name
1 failed, 57 passed in 0.59s
```

(The `Differing items` lines are dropped.)

**Restore:** inverse edit.

**Restore receipt:** restored line, `repeat_marks.py:227`:

```python
        entry = exact_match(finding, pool)
```

**Raw green:**

```
..........................................................               [100%]
58 passed in 0.60s
```

## M4 — the `fixed` + `wrong` row of `decide`

**Guarded element:** `decide`, the `fixed` branch (`repeat_marks.py:65`). Axis: a repeat of a fixed finding the
verifier found `wrong` is kept as `fixed` and the fix holds; any other grade is a new finding.

**Neutralization:** `if grade_verdict == "wrong":` became `if grade_verdict == "wrongx":` in the `fixed` branch.

**Raw red** (1 failed, 57 passed):

```
.........................F................................               [100%]
=================================== FAILURES ===================================
_ test_d1_a_fixed_finding_raised_again_and_found_wrong_is_kept_and_the_fix_holds _

    def test_d1_a_fixed_finding_raised_again_and_found_wrong_is_kept_and_the_fix_holds():
>       assert RM.decide("fixed", "wrong", False) == (True, True)
E       assert (False, False) == (True, True)
E         
E         At index 0 diff: False != True
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py:102: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py::test_d1_a_fixed_finding_raised_again_and_found_wrong_is_kept_and_the_fix_holds
1 failed, 57 passed in 0.57s
```

**Restore:** inverse edit, `"wrongx"` back to `"wrong"`.

**Restore receipt:** restored line, `repeat_marks.py:65`:

```python
        if grade_verdict == "wrong":
```

**Raw green:**

```
..........................................................               [100%]
58 passed in 0.56s
```

## M5 — `code_changed` fails closed on a failed git run

**Guarded element:** `code_changed`, the final `return done.returncode != 0` (`repeat_marks.py:89`). Axis: any non-zero
exit of `git diff --quiet` (a changed tree is 1; an unknown commit or a bad repo is 128) reads as changed.

**Neutralization:** `return done.returncode != 0` became `return done.returncode == 1` (only the tree-differs exit
counts; a failed run reads as unchanged).

**Raw red** (2 failed, 56 passed):

```
......................................................F.F.               [100%]
=================================== FAILURES ===================================
____________ test_code_changed_counts_an_unreadable_head_as_changed ____________

    def test_code_changed_counts_an_unreadable_head_as_changed(repo):
        assert RM.code_changed(repo.root, None, repo.same) is True
        assert RM.code_changed(repo.root, repo.changed, "") is True
        assert RM.code_changed(repo.root, repo.changed, 7) is True
>       assert RM.code_changed(repo.root, "0" * 40, repo.same) is True
E       AssertionError: assert False is True

plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py:193: AssertionError
_____________ test_code_changed_counts_a_failed_git_run_as_changed _____________

    def test_code_changed_counts_a_failed_git_run_as_changed(repo, monkeypatch):
>       assert RM.code_changed(repo.root + "-absent", repo.changed, repo.same) is True  # git exits non-zero
E       AssertionError: assert False is True

plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py:203: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py::test_code_changed_counts_an_unreadable_head_as_changed
FAILED plugins/superheroes/lib/tests/test_repeat_marks_module_c1l8a.py::test_code_changed_counts_a_failed_git_run_as_changed
2 failed, 56 passed in 0.73s
```

(The `E +  where ...` expansion lines are dropped from both failures.)

**Restore:** inverse edit, `== 1` back to `!= 0`.

**Restore receipt:** restored line, `repeat_marks.py:89`:

```python
    return done.returncode != 0
```

**Raw green:**

```
..........................................................               [100%]
58 passed in 0.74s
```
