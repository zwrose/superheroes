# WO-1273-L3A-I bite-proof — run-dir refusal detail token home + census

**Provenance:** cursor / composer-2.5 (implementer).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-I1 | `test_run_dir_refusal_literals_only_in_home` | a stray run-dir refusal literal outside `dispatch_outcome.py` fails the tree-derived census | `test_run_dir_refusal_literals_only_in_home` |
| BP-I2 | `test_run_dir_refusal_home_literal_values` | home constants must carry the pinned literal values, not just symbols | `test_run_dir_refusal_home_literal_values` |

---

## BP-I1 — census bites on a stray literal

- **axis:** a run-dir refusal detail token spelled as a string literal outside `dispatch_outcome.py` fails the census for that module

**neutralization** (`plugins/superheroes/lib/engine_adapter.py`, after import block):
```python
_WO1273_BP_PLANT = "run-dir-reused"
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_run_dir_refusal_census.py -q
```

**raw red** (exit 1):
```
................................F....................................... [ 44%]
........................................................................ [ 88%]
...................                                                      [100%]
=================================== FAILURES ===================================
________ test_run_dir_refusal_literals_only_in_home[engine_adapter.py] _________

basename = 'engine_adapter.py'

    @pytest.mark.parametrize("basename", _CENSUS_MODULES)
    def test_run_dir_refusal_literals_only_in_home(basename):
        banned = _PINNED_LITERALS
        path = os.path.join(_LIB, basename)
        offenders = _literal_offenders(path, banned)
>       assert offenders == [], offenders
E       AssertionError: [('run-dir-reused', 28)]
E       assert [('run-dir-reused', 28)] == []
E         
E         Left contains one more item: ('run-dir-reused', 28)
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_run_dir_refusal_census.py:77: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_run_dir_refusal_census.py::test_run_dir_refusal_literals_only_in_home[engine_adapter.py]
1 failed, 162 passed in 4.05s
```

**restore:** remove the `_WO1273_BP_PLANT = "run-dir-reused"` line from `engine_adapter.py`.

**raw green** (exit 0):
```
........................................................................ [ 44%]
........................................................................ [ 88%]
...................                                                      [100%]
163 passed in 4.00s
```

---

## BP-I2 — census pins the literal value

- **axis:** changing a home constant's value (not its name) fails the literal-value pin even when the symbol name is unchanged

**neutralization** (`plugins/superheroes/lib/dispatch_outcome.py`):
```python
DETAIL_RUN_DIR_REUSED = "run-dir-reused-bite-proof"  # was: "run-dir-reused"
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_run_dir_refusal_census.py -q
```

**raw red** (exit 1):
```
F....................................................................... [ 44%]
........................................................................ [ 88%]
...................                                                      [100%]
=================================== FAILURES ===================================
___________________ test_run_dir_refusal_home_literal_values ___________________

    def test_run_dir_refusal_home_literal_values():
        """axis: home constants carry the pinned literal values, not just symbols."""
>       assert dispatch_outcome.ALL_RUN_DIR_REFUSAL_DETAILS == _PINNED_LITERALS
E       AssertionError: assert frozenset({'r...-bite-proof'}) == frozenset({'r...-dir-reused'})
E         
E         Extra items in the left set:
E         'run-dir-reused-bite-proof'
E         Extra items in the right set:
E         'run-dir-reused'
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_run_dir_refusal_census.py:69: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_run_dir_refusal_census.py::test_run_dir_refusal_home_literal_values
1 failed, 162 passed in 3.53s
```

**restore** (`plugins/superheroes/lib/dispatch_outcome.py`):
```python
DETAIL_RUN_DIR_REUSED = "run-dir-reused"
```

**raw green** (exit 0):
```
........................................................................ [ 44%]
........................................................................ [ 88%]
...................                                                      [100%]
163 passed in 3.59s
```
