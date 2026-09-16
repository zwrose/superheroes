# WO-C2 carve-out-gate bite-proof

## P2 queue when the ladder is unstamped

**Guarded element:** `_unstamped_ladder_outcome` P2 branch at `front_door.py:120-121` — axis: P2 queues instead of filing when the ladder is unstamped.

**Neutralization:** changed the P2 branch from `_queued(REASON_LADDER_UNSTAMPED, ...)` to `_graded("P2", band, evidence)`.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_front_door.py::test_no_ladder_queues_instead_of_filing -q
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_no_ladder_queues_instead_of_filing ____________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-251/test_no_ladder_queues_instead_0')

    def test_no_ladder_queues_instead_of_filing(tmp_path):
        repo, store = _setup_repo(tmp_path)
        got = FD.grade(
            repo,
            _claim(tier="P2", band="Band 2", evidence="lab"),
            root=store,
        )
>       assert got["outcome"] == "queued"
E       AssertionError: assert 'graded' == 'queued'
E         
E         - queued
E         + graded

plugins/superheroes/lib/tests/test_front_door.py:115: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_front_door.py::test_no_ladder_queues_instead_of_filing
1 failed in 3.89s
```

**Restore:** reverted line 120-121 to `return _queued(REASON_LADDER_UNSTAMPED, band, tier, evidence)`.

**Restore receipt:**
```python
    if tier == "P2":
        return _queued(REASON_LADDER_UNSTAMPED, band, tier, evidence)
    return _refused(REASON_LADDER_UNSTAMPED, band, tier, evidence)
```

**Green run:**
```
.                                                                        [100%]
1 passed in 4.04s
```
