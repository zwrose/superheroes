# WO-B (#1340 layer 2d) bite-proof — `launcher.py` layersPlanned premise validation

Per-guard bite proof for the three new `layersPlanned` clauses in `validate_premise`.

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| E1 | `validate_premise` layersPlanned pairing | layersPlanned requires stack and layerPosition | `test_premise_layers_planned_without_stack_pair_refuses` |
| E2 | `validate_premise` layersPlanned floor | layersPlanned must be at least layerPosition | `test_premise_layers_planned_under_position_refuses` |
| E3 | `validate_premise` layersPlanned `ll.is_positive_premise_int` guard | layersPlanned must be a positive int (bool is not an int here) | `test_premise_layers_planned_invalid[True]` |

---

## E1 — layersPlanned-without-the-pair refusal

- **axis:** layersPlanned requires stack and layerPosition

**neutralization** (`plugins/superheroes/lib/launcher.py`):
```python
    if False and has_layers_planned and not has_stack:
```
(replaces `if has_layers_planned and not has_stack:`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest 'plugins/superheroes/lib/tests/test_launcher.py::test_premise_layers_planned_without_stack_pair_refuses' -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_premise_layers_planned_without_stack_pair_refuses ____________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2910/test_premise_layers_planned_wi0')

    def test_premise_layers_planned_without_stack_pair_refuses(tmp_path):
      # axis: premise-stack-layers-planned-incomplete
        repo = _init_repo(tmp_path / "repo")
        premise = _valid_premise(repo, layersPlanned=3)
        result = L.validate_premise(premise, repo)
>       assert result["ok"] is False
E       assert True is False

plugins/superheroes/lib/tests/test_launcher.py:6087: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_premise_layers_planned_without_stack_pair_refuses
1 failed in 0.46s
```

**restore:**
```python
    if has_layers_planned and not has_stack:
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.37s
```

---

## E2 — layersPlanned >= layerPosition check

- **axis:** layersPlanned must be at least layerPosition

**neutralization** (`plugins/superheroes/lib/launcher.py`):
```python
            if False and layers_planned_val < layer_val:
```
(replaces `if layers_planned_val < layer_val:`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest 'plugins/superheroes/lib/tests/test_launcher.py::test_premise_layers_planned_under_position_refuses' -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_premise_layers_planned_under_position_refuses ______________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2912/test_premise_layers_planned_un0')

    def test_premise_layers_planned_under_position_refuses(tmp_path):
      # axis: premise-stack-layers-planned-under-position
        repo = _init_repo(tmp_path / "repo")
        premise = _stack_premise(repo, stack=1, layerPosition=3, layersPlanned=2)
        result = L.validate_premise(premise, repo)
>       assert result["ok"] is False
E       assert True is False

plugins/superheroes/lib/tests/test_launcher.py:6106: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_premise_layers_planned_under_position_refuses
1 failed in 0.44s
```

**restore:**
```python
            if layers_planned_val < layer_val:
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.35s
```

---

## E3 — positive-non-bool typing of layersPlanned

- **axis:** layersPlanned must be a positive int (bool is not an int here)

**neutralization** (`plugins/superheroes/lib/launcher.py`):
```python
            if False and not ll.is_positive_premise_int(layers_planned_val):
```
(replaces `if not ll.is_positive_premise_int(layers_planned_val):`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest 'plugins/superheroes/lib/tests/test_launcher.py::test_premise_layers_planned_invalid[True]' -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_premise_layers_planned_invalid[True] ___________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2914/test_premise_layers_planned_in0')
value = True

    @pytest.mark.parametrize("value", [0, -1, True, "3", 3.0])
    def test_premise_layers_planned_invalid(tmp_path, value):
      # axis: premise-stack-layers-planned-invalid
        repo = _init_repo(tmp_path / "repo")
        premise = _stack_premise(repo, layersPlanned=value)
        result = L.validate_premise(premise, repo)
>       assert result["ok"] is False
E       assert True is False

plugins/superheroes/lib/tests/test_launcher.py:6097: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_premise_layers_planned_invalid[True]
1 failed in 0.42s
```

**restore:**
```python
            if not ll.is_positive_premise_int(layers_planned_val):
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.43s
```
