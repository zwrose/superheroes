# WO-A1 (#1311) bite-proof — pre-reservation census pin

**Provenance:** cursor composer-2.5 / dispatch-write

## Guarded element

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-A1-2 | pre-reservation exemption pin in overlap census | pin at exactly two `# pre-reservation:` returns | `test_no_launch_build_return_drops_the_overlap_warnings` |

---

## BP-A1-2 — pre-reservation exemption pin

- **axis:** widening the pinned count without adding a third marked return fails the census

**neutralization** (`plugins/superheroes/lib/tests/test_launcher.py`):
```python
    assert len(pre_reservation) == 3, pre_reservation
```
(replaces `== 2`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_launcher.py::test_no_launch_build_return_drops_the_overlap_warnings -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_no_launch_build_return_drops_the_overlap_warnings ____________

    def test_no_launch_build_return_drops_the_overlap_warnings():
        # axis: census over the WHOLE function — every reservation in launch_build (the main
        # one and the five accounting reservations) can stamp an overlap, so no `return _fail`
        # anywhere in it may bypass the two helpers that attach `warnings`
        lines = inspect.getsource(L.launch_build).split("\n")
        helper = next(
            i for i, ln in enumerate(lines) if "def _post_reserve_fail(" in ln
        )
        helper_end = next(
            i for i, ln in enumerate(lines) if i > helper and "return _fail(" in ln
        )
        offenders = [
            (i, ln.strip()) for i, ln in enumerate(lines)
            if i != helper_end and "return _fail(" in ln
            and 'reserve_result["reason"]' not in ln
            and "# pre-reservation:" not in ln
        ]
        assert offenders == [], (
            "launch_build failure path bypasses _post_reserve_fail/_accounted_fail and drops "
            "`warnings`: %r" % (offenders,)
        )
        # The one exempt return: its OWN reservation reported failure, so the caller has no
        # reservation to disclose against. That is not the same as "no record exists" — an
        # append that fails at fsync AFTER flush leaves a readable row while reporting failure
        # (`_append_raw`), a pre-existing ledger property this change does not touch and does
        # not fix. Pinned at exactly one so the exemption cannot quietly widen.
        exempt = [ln for ln in lines if 'reserve_result["reason"]' in ln]
        assert len(exempt) == 1, exempt
        # Pre-reservation refusals return before any reservation exists, so they have no overlap
        # to disclose. Pinned at exactly two so the exemption cannot quietly widen.
        pre_reservation = [ln for ln in lines if "# pre-reservation:" in ln]
>       assert len(pre_reservation) == 3, pre_reservation
E       AssertionError: ['            return _fail(  # pre-reservation: instance pin gate before any reservation', '                return _fail(  # pre-reservation: instance pin gate before any reservation']
E       assert 2 == 3
E        +  where 2 = len(['            return _fail(  # pre-reservation: instance pin gate before any reservation', '                return _fail(  # pre-reservation: instance pin gate before any reservation'])

plugins/superheroes/lib/tests/test_launcher.py:4909: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_no_launch_build_return_drops_the_overlap_warnings
1 failed in 0.57s
```

**restore:**
```python
    assert len(pre_reservation) == 2, pre_reservation
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.44s
```
