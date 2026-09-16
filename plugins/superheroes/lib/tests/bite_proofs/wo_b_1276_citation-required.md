# WO-B citation-required bite-proof

## Citation required

**Guarded element:** `_validate_severity_ladder` in `project_config.py` — axis: every band example carries a citation on write.

**Neutralization:** changed the citation guard to `if False and (not isinstance(citation, str) or not citation.strip()):` so examples without a citation pass validation.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_project_config.py::test_set_severity_ladder_refuses_missing_citation -q
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_set_severity_ladder_refuses_missing_citation _______________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-195/test_set_severity_ladder_refus0')

    def test_set_severity_ladder_refuses_missing_citation(tmp_path):
        repo, store = _setup_repo(tmp_path)
        bad = [{"name": "high", "examples": [{"text": "data loss"}]}]
        res = PC.set_item(repo, "severityLadder", bad, root=store)
>       assert res["action"] == "refused"
E       AssertionError: assert 'written' == 'refused'
E         
E         - refused
E         + written

plugins/superheroes/lib/tests/test_project_config.py:222: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_project_config.py::test_set_severity_ladder_refuses_missing_citation
1 failed in 7.56s
```

**Restore:** reverted the citation guard to `if not isinstance(citation, str) or not citation.strip():`.

**Restore receipt:** restored lines in `_validate_severity_ladder`:
```python
            citation = example.get("citation")
            if not isinstance(citation, str) or not citation.strip():
                return REASON_LADDER_CITATION_REQUIRED
```

**Green run:**
```
.                                                                        [100%]
1 passed in 4.41s
```
