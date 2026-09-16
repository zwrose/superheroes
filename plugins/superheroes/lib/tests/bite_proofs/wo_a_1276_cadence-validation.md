# Cadence-validation bite-proof

## Cadence-validation

**Guarded element:** `core_md.py:1667` — `_validate_guardian_cadence` call at the top of `write_guardian_cadence` — axis: refuse non-positive `minMerges` / `minDays`.

**Neutralization:** removed the validation gate:

```python
    refusal = _validate_guardian_cadence(cadence)
    if refusal is not None:
        return {"action": "refused", "reason": refusal}
```

**Command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_core_md_project_config.py::test_bite_guardian_cadence_validation_axis -q
```

**Red run:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_bite_guardian_cadence_validation_axis __________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-173/test_bite_guardian_cadence_val0')

    def test_bite_guardian_cadence_validation_axis(tmp_path):
        """axis: cadence validation — refuse non-positive minMerges."""
        repo, store = _setup_repo(tmp_path)
        _write_guardian_layer(repo, store, dict(_GUARDIAN_BLOCK))
        res = CM.write_guardian_cadence(repo, {"minMerges": 0, "minDays": 7}, root=store)
>       assert res["action"] == "refused"
E       AssertionError: assert 'written' == 'refused'
E         
E         - refused
E         + written

plugins/superheroes/lib/tests/test_core_md_project_config.py:530: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_core_md_project_config.py::test_bite_guardian_cadence_validation_axis
1 failed in 9.74s
```

**Restore:** reinserted the validation gate at `write_guardian_cadence` entry (quoted in neutralization above).

**Restore receipt:** restored lines quoted above; `git status --porcelain plugins/superheroes/lib/core_md.py` showed no output.

**Green run:**

```
.                                                                        [100%]
1 passed in 4.55s
```
