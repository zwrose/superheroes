# WO-C2 ladder-gate bite-proof

## Unstamped ladder refusal on P0 and P1

**Guarded element:** `_unstamped_ladder_outcome` final return at `front_door.py:122` — axis: an unstamped ladder refuses P0 and P1 instead of grading them.

**Neutralization:** changed the P0 and P1 branch from `_refused(REASON_LADDER_UNSTAMPED, ...)` to `_graded(tier, band, evidence)`.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_front_door.py::test_no_ladder_refuses_p0_and_p1 -q
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________________ test_no_ladder_refuses_p0_and_p1 _______________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-249/test_no_ladder_refuses_p0_and_0')

    def test_no_ladder_refuses_p0_and_p1(tmp_path):
        repo, store = _setup_repo(tmp_path)
        for tier in ("P0", "P1"):
            got = FD.grade(
                repo,
                _claim(tier=tier, band="Band 1", evidence="field"),
                root=store,
            )
>           assert got["outcome"] == "refused"
E           AssertionError: assert 'graded' == 'refused'
E             
E             - refused
E             + graded

plugins/superheroes/lib/tests/test_front_door.py:103: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_front_door.py::test_no_ladder_refuses_p0_and_p1
1 failed in 4.05s
```

**Restore:** reverted line 122 to `return _refused(REASON_LADDER_UNSTAMPED, band, tier, evidence)`.

**Restore receipt:**
```python
    if tier == "P2":
        return _queued(REASON_LADDER_UNSTAMPED, band, tier, evidence)
    return _refused(REASON_LADDER_UNSTAMPED, band, tier, evidence)
```

**Green run:**
```
.                                                                        [100%]
1 passed in 4.08s
```
