# WO-D (#1340 layer 2d) bite-proof — fold premise stack field projection

Per-guard bite proof for `launch_ledger._fold_premise_positive_int`: malformed premise
values must fold to `None`, not pass through raw.

**Provenance:** cursor / composer-2.5.

**Command** (referred to as *the command* below):

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_launch_ledger.py::<TEST> -q
```

## Summary table

| ID | Guarded element (file:line) | Axis | Proving test | Verdict |
|---|---|---|---|---|
| BP-L2D-1 | launch_ledger.py `_fold_premise_positive_int` | positive-int validation — bool/0/string fold to None | `test_fold_premise_stack_field_invalid_values_fold_to_none` | proven |

---

## BP-L2D-1 — positive-int validation

**neutralization** (`plugins/superheroes/lib/launch_ledger.py` `_fold_premise_positive_int`):
```
    val = premise.get(key)
    if isinstance(val, int) and not isinstance(val, bool) and val >= 1:
        return val
    return None
```
→
```
    return premise.get(key)
```

**command:** `...::test_fold_premise_stack_field_invalid_values_fold_to_none -q`

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_fold_premise_stack_field_invalid_values_fold_to_none ___________
plugins/superheroes/lib/tests/test_launch_ledger.py:5302: in test_fold_premise_stack_field_invalid_values_fold_to_none
    assert lane["stack"] is None
E   assert False is None
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_ledger.py::test_fold_premise_stack_field_invalid_values_fold_to_none
1 failed in 0.62s
```

**restore:** reverted the neutralization (quoted left-hand side under **neutralization**).

**raw green** after restore:
```
.                                                                        [100%]
1 passed in 0.67s
```
