# WO-R6B (#1273) bite-proof — C14 layer 3b review r6

**Provenance:** cursor / composer-2.5 (implementer).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-R6B-1 | `test_matrix_config_calls_only_inside_cell` on `seat_map.py` | qualified `matrix_config` calls outside `_cell` are offenders | `test_matrix_config_calls_only_inside_cell` |
| BP-R6B-2 | `_matrix_config_offenders` Attribute arm | `ast.Attribute` with `attr == "matrix_config"` is an offender | `test_matrix_config_offenders_detects_outside_bare_and_qualified` |

---

## BP-R6B-1 — qualified calls are caught, real channel

- **axis:** every `matrix_config` call in `seat_map.py`, bare or qualified, must sit inside `_cell`

**neutralization** (`plugins/superheroes/lib/seat_map.py`, `seed_from`):
```python
def seed_from(pr_number: int | str | None, head_sha: str | None) -> int:
    model_registry.matrix_config("reviewer", "codex")
    if pr_number:
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/wh1273r6-pyc-b -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_matrix_config_calls_only_inside_cell -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_matrix_config_calls_only_inside_cell ___________________

    def test_matrix_config_calls_only_inside_cell():
        with open(_MOD, encoding="utf-8") as fh:
            source = fh.read()
>       assert _matrix_config_offenders(source) == []
E       assert [456] == []
E         
E         Left contains one more item: 456
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_seat_map.py:3252: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_matrix_config_calls_only_inside_cell
1 failed in 0.21s
```

**restore** (`plugins/superheroes/lib/seat_map.py`, `seed_from`):
```python
def seed_from(pr_number: int | str | None, head_sha: str | None) -> int:
    if pr_number:
```

**restore receipt:** the `model_registry.matrix_config("reviewer", "codex")` line removed from `seed_from`; post-restore `git status --porcelain` shows only the order's expected edits.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.21s
```

---

## BP-R6B-2 — the helper's Attribute arm

- **axis:** `_matrix_config_offenders` must match `ast.Attribute` calls with `attr == "matrix_config"`

**neutralization** (`plugins/superheroes/lib/tests/test_seat_map.py`, `_matrix_config_offenders`):
```python
        is_matrix_config = isinstance(func, ast.Name) and func.id == "matrix_config"
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/wh1273r6-pyc-b -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_matrix_config_offenders_detects_outside_bare_and_qualified -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_matrix_config_offenders_detects_outside_bare_and_qualified ________

    def test_matrix_config_offenders_detects_outside_bare_and_qualified():
        source = """\
    def _cell():
        matrix_config("reviewer", "codex")
    
    def outside():
        matrix_config("reviewer", "claude")
        model_registry.matrix_config("reviewer", "codex")
    """
>       assert _matrix_config_offenders(source) == [5, 6]
E       assert [5] == [5, 6]
E         
E         Right contains one more item: 6
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_seat_map.py:3260: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_matrix_config_offenders_detects_outside_bare_and_qualified
1 failed in 0.19s
```

**restore** (`plugins/superheroes/lib/tests/test_seat_map.py`, `_matrix_config_offenders`):
```python
        is_matrix_config = (
            isinstance(func, ast.Name) and func.id == "matrix_config"
        ) or (
            isinstance(func, ast.Attribute) and func.attr == "matrix_config"
        )
```

**restore receipt:** the `ast.Attribute` arm restored in `_matrix_config_offenders`; post-restore `git status --porcelain` shows only the order's expected edits.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.16s
```
