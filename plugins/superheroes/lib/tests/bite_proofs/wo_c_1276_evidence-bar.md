# WO-C2 evidence-bar bite-proof

## Argued evidence refusal on stamped ladder path

**Guarded element:** `grade` argued check at `front_door.py:167-168` — axis: argued evidence never grades once the ladder is stamped.

**Neutralization:** changed the stamped-ladder argued branch from `_refused(REASON_EVIDENCE_ARGUED, ...)` to `_graded(tier, band, evidence)`.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_front_door.py::test_argued_evidence_refused -q
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________________ test_argued_evidence_refused _________________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-253/test_argued_evidence_refused0')

    def test_argued_evidence_refused(tmp_path):
        repo, store = _setup_repo(tmp_path)
        _stamp_ladder(repo, store)
        got = FD.grade(
            repo,
            _claim(tier="P1", band="Band 1", evidence="argued"),
            root=store,
        )
>       assert got["outcome"] == "refused"
E       AssertionError: assert 'graded' == 'refused'
E         
E         - refused
E         + graded

plugins/superheroes/lib/tests/test_front_door.py:156: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_front_door.py::test_argued_evidence_refused
1 failed in 4.56s
```

**Restore:** reverted lines 167-168 to `return _refused(REASON_EVIDENCE_ARGUED, band, tier, evidence)`.

**Restore receipt:**
```python
    if evidence == "argued":
        return _refused(REASON_EVIDENCE_ARGUED, band, tier, evidence)
```

**Green run:**
```
.                                                                        [100%]
1 passed in 4.42s
```
