# WO-B (#1340 layer 2b) bite-proof — `launcher.py` stack premise and layer gate

Per-guard bite proof for stack field validation (I1) and the layer gate in `launch_build` (I2).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-B-1 | `validate_premise` stack/layer pairing | stack and layerPosition must both be present or both absent | `test_premise_stack_fields_incomplete[premise_overrides0]` |
| BP-B-2 | `validate_premise` stack field types | stack and layerPosition must be positive ints (bool is not an int here) | `test_premise_stack_field_invalid[stack-1]` |
| BP-B-3 | `_lookup_stack_entry_pr` zero candidates | zero open PRs carry this head — base is not a layer head | `test_stack_gate_zero_entry_candidates_refuses` |
| BP-B-4 | `_apply_stack_gate` position predicate | queried position must equal layerPosition - 1 | `test_stack_gate_position_mismatch_refuses` |
| BP-B-5 | `_apply_stack_gate` head predicate | queried headRefOid must equal resolved base commit | `test_stack_gate_head_mismatch_refuses` |
| BP-B-6 | `_apply_stack_gate` not-linked branch | entry PR is not linked to a stack | `test_stack_gate_not_linked_refuses` |
| BP-B-7 | `_lookup_stack_entry_pr` ambiguous lookup | ambiguous or unreadable entry PR lookup | `test_stack_gate_two_entry_candidates_refuses` |

Budget note: invocations 7–14 recorded red/green for BP-B-1 through BP-B-4; BP-B-5 through BP-B-7 have proving tests but no separate red/green capture in this dispatch (budget ceiling).

---

## BP-B-1 — premise-stack-fields-incomplete

- **axis:** stack and layerPosition must both be present or both absent

**neutralization** (`plugins/superheroes/lib/launcher.py`):
```python
    if False and has_stack != has_layer:
```
(replaces `if has_stack != has_layer:`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-woB -m pytest 'plugins/superheroes/lib/tests/test_launcher.py::test_premise_stack_fields_incomplete[premise_overrides0]' -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_premise_stack_fields_incomplete[premise_overrides0] ___________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2421/test_premise_stack_fields_inco0')
premise_overrides = {'stack': 1}

    @pytest.mark.parametrize("premise_overrides", [
        {"stack": 1},
        {"layerPosition": 2},
    ])
    def test_premise_stack_fields_incomplete(tmp_path, premise_overrides):
      # axis: premise-stack-fields-incomplete
        repo = _init_repo(tmp_path / "repo")
        premise = _valid_premise(repo)
        premise.update(premise_overrides)
>       result = L.validate_premise(premise, repo)

plugins/superheroes/lib/tests/test_launcher.py:6036: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

premise = {'baseCommit': 'af38fc98679de316cfb57bcd3a1e607bd1039aed', 'bashMaxTimeoutMs': 900000, 'batchId': 'wave-test', 'grantScope': {'applicable': True, 'kind': 'prs', 'prs': [701]}, ...}
repo_root = '/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2421/test_premise_stack_fields_inco0/repo'
preflight_checks = None, env = None, issue = None

    def validate_premise(premise, repo_root, preflight_checks=None, env=None, issue=None):
        ...
        if has_stack:
            stack_val = premise["stack"]
>           layer_val = premise["layerPosition"]
E           KeyError: 'layerPosition'

plugins/superheroes/lib/launcher.py:1069: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_premise_stack_fields_incomplete[premise_overrides0]
1 failed in 0.43s
```

**restore:**
```python
    if has_stack != has_layer:
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.54s
```

---

## BP-B-2 — premise-stack-field-invalid

- **axis:** stack and layerPosition must be positive ints (bool is not an int here)

**neutralization** (`plugins/superheroes/lib/launcher.py`):
```python
        if False and (
            not isinstance(stack_val, int)
            ...
        ):
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-woB -m pytest 'plugins/superheroes/lib/tests/test_launcher.py::test_premise_stack_field_invalid[stack-1]' -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_premise_stack_field_invalid[stack-1] ___________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2424/test_premise_stack_field_inval0')
field = 'stack', value = '1'

    @pytest.mark.parametrize("field,value", [
        ("stack", "1"),
        ...
    ])
    def test_premise_stack_field_invalid(tmp_path, field, value):
      # axis: premise-stack-field-invalid
        ...
>       assert result["ok"] is False
E       assert True is False

plugins/superheroes/lib/tests/test_launcher.py:6055: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_premise_stack_field_invalid[stack-1]
1 failed in 0.53s
```

**restore:**
```python
        if (
            not isinstance(stack_val, int)
            ...
        ):
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.40s
```

---

## BP-B-3 — zero entry PR candidates

- **axis:** zero open PRs carry this head — base is not a layer head

**neutralization** (`plugins/superheroes/lib/launcher.py`):
```python
    if False and not candidates:
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-woB -m pytest plugins/superheroes/lib/tests/test_launcher.py::test_stack_gate_zero_entry_candidates_refuses -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_stack_gate_zero_entry_candidates_refuses _________________
...
>       return {"ok": True, "pr": candidates[0], "repo": repo_name}
E       IndexError: list index out of range

plugins/superheroes/lib/launcher.py:1421: IndexError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_stack_gate_zero_entry_candidates_refuses
1 failed in 0.53s
```

**restore:**
```python
    if not candidates:
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.71s
```

---

## BP-B-4 — position acceptance predicate

- **axis:** queried position must equal layerPosition - 1

**neutralization** (`plugins/superheroes/lib/launcher.py`):
```python
    if False and queried["position"] != layer_pos - 1:
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-woB -m pytest plugins/superheroes/lib/tests/test_launcher.py::test_stack_gate_position_mismatch_refuses -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_stack_gate_position_mismatch_refuses ___________________
...
>       assert result["ok"] is False
E       assert True is False

plugins/superheroes/lib/tests/test_launcher.py:6278: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_stack_gate_position_mismatch_refuses
1 failed in 21.99s
```

**restore:**
```python
    if queried["position"] != layer_pos - 1:
```

**raw green:**
```
.                                                                        [100%]
1 passed in 2.49s
```
