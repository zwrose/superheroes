# WO-A2 (#1270 L2) bite-proof — strict-mode structural checker

**Provenance:** cursor / composer-2.5 (implementer).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-A2-1 | `assert_strict_mode_valid` rule 1 | root must be `type: object` | `test_assert_strict_mode_valid_catches_structural_violations[rule1-root]` |
| BP-A2-2 | `assert_strict_mode_valid` rule 2 | `oneOf` forbidden anywhere | `test_assert_strict_mode_valid_catches_structural_violations[rule2-oneof]` |
| BP-A2-3 | `assert_strict_mode_valid` rule 3 | every node carries `type` (or is `anyOf`) | `test_assert_strict_mode_valid_catches_structural_violations[rule3-no-type]` |
| BP-A2-4 | `assert_strict_mode_valid` rule 4 | every array carries `items` | `test_assert_strict_mode_valid_catches_structural_violations[rule4-array-items]` |
| BP-A2-5 | `assert_strict_mode_valid` rule 5 | object `additionalProperties: false` | `test_assert_strict_mode_valid_catches_structural_violations[rule5-additional]` |
| BP-A2-6 | `_strict_schema_for_field` refinement table | unrefined `list`/`any` raises at build | `test_unrefined_list_token_raises_at_schema_build` |

---

## BP-A2-1 — root must be object

- **axis:** root must be `type: object`

**neutralization** (`plugins/superheroes/lib/engine_result_channel.py`, `assert_strict_mode_valid`):
```python
    if False:  # bite-proof neutralization rule 1
        raise StrictModeViolationError(
            "In context=%s, root schema must have type 'object'"
            % _strict_context_path(path)
        )
```
(replaces `if path == () and schema.get("type") != "object":`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_result_channel.py::test_assert_strict_mode_valid_catches_structural_violations[rule1-root] -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_assert_strict_mode_valid_catches_structural_violations[rule1-root] ____

schema = {'type': 'string'}
path_fragment = "root schema must have type 'object'"

    @pytest.mark.parametrize("schema,path_fragment", [
        ...
    ], ids=["rule1-root", "rule2-oneof", "rule3-no-type", "rule4-array-items", "rule5-additional"])
    def test_assert_strict_mode_valid_catches_structural_violations(schema, path_fragment):
        with pytest.raises(ERC.StrictModeViolationError, match=path_fragment) as exc:
>           ERC.assert_strict_mode_valid(schema)
E           Failed: DID NOT RAISE <class 'engine_result_channel.StrictModeViolationError'>

plugins/superheroes/lib/tests/test_engine_result_channel.py:468: Failed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_result_channel.py::test_assert_strict_mode_valid_catches_structural_violations[rule1-root]
1 failed in 0.38s
```

**restore** (`plugins/superheroes/lib/engine_result_channel.py`, `assert_strict_mode_valid`):
```python
    if path == () and schema.get("type") != "object":
        raise StrictModeViolationError(
            "In context=%s, root schema must have type 'object'"
            % _strict_context_path(path)
        )
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.45s
```

---

## BP-A2-2 — oneOf forbidden

- **axis:** `oneOf` forbidden anywhere

**neutralization** (`plugins/superheroes/lib/engine_result_channel.py`, `assert_strict_mode_valid`):
```python
    if False:  # bite-proof neutralization rule 2
        raise StrictModeViolationError(
            "In context=%s, oneOf is not permitted in strict mode"
            % _strict_context_path(path)
        )
```
(replaces `if "oneOf" in schema:`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_result_channel.py::test_assert_strict_mode_valid_catches_structural_violations[rule2-oneof] -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_assert_strict_mode_valid_catches_structural_violations[rule2-oneof] ___

schema = {'oneOf': [{'type': 'string'}], 'type': 'object'}
path_fragment = 'oneOf is not permitted'

    def test_assert_strict_mode_valid_catches_structural_violations(schema, path_fragment):
        with pytest.raises(ERC.StrictModeViolationError, match=path_fragment) as exc:
>           ERC.assert_strict_mode_valid(schema)
E           AssertionError: Regex pattern did not match.
E            Regex: 'oneOf is not permitted'
E            Input: 'In context=(), object schema must set additionalProperties to false'

plugins/superheroes/lib/tests/test_engine_result_channel.py:468: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_result_channel.py::test_assert_strict_mode_valid_catches_structural_violations[rule2-oneof]
1 failed in 0.43s
```

**restore:**
```python
    if "oneOf" in schema:
        raise StrictModeViolationError(
            "In context=%s, oneOf is not permitted in strict mode"
            % _strict_context_path(path)
        )
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.44s
```

---

## BP-A2-3 — every node carries type

- **axis:** every node carries `type` (or is `anyOf`)

**neutralization** (`plugins/superheroes/lib/engine_result_channel.py`, `assert_strict_mode_valid`):
```python
    if False:  # bite-proof neutralization rule 3
        raise StrictModeViolationError(
            "In context=%s, schema must have a 'type' key"
            % _strict_context_path(path)
        )
```
(replaces `if "type" not in schema:`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_result_channel.py::test_assert_strict_mode_valid_catches_structural_violations[rule3-no-type] -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_assert_strict_mode_valid_catches_structural_violations[rule3-no-type] __

schema = {'additionalProperties': False, 'properties': {'x': {}}, 'required': ['x'], 'type': 'object'}
path_fragment = "schema must have a 'type' key"

    def test_assert_strict_mode_valid_catches_structural_violations(schema, path_fragment):
        with pytest.raises(ERC.StrictModeViolationError, match=path_fragment) as exc:
>           ERC.assert_strict_mode_valid(schema)
...
>       type_spec = schema["type"]
E       KeyError: 'type'

plugins/superheroes/lib/engine_result_channel.py:107: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_result_channel.py::test_assert_strict_mode_valid_catches_structural_violations[rule3-no-type]
1 failed in 0.59s
```

**restore:**
```python
    if "type" not in schema:
        raise StrictModeViolationError(
            "In context=%s, schema must have a 'type' key"
            % _strict_context_path(path)
        )
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.33s
```

---

## BP-A2-4 — array must carry items

- **axis:** every array carries `items`

**neutralization** (`plugins/superheroes/lib/engine_result_channel.py`, `assert_strict_mode_valid`):
```python
    if "array" in type_names:
        if False:  # bite-proof neutralization rule 4
            raise StrictModeViolationError(
                "In context=%s, array schema missing items"
                % _strict_context_path(path)
            )
        if "items" in schema:
            assert_strict_mode_valid(schema["items"], path + ("items",))
```
(replaces unconditional `items` presence check)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_result_channel.py::test_assert_strict_mode_valid_catches_structural_violations[rule4-array-items] -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_assert_strict_mode_valid_catches_structural_violations[rule4-array-items] _

schema = {'additionalProperties': False, 'properties': {'items': {'type': 'array'}}, 'required': ['items'], 'type': 'object'}
path_fragment = 'array schema missing items'

    def test_assert_strict_mode_valid_catches_structural_violations(schema, path_fragment):
        with pytest.raises(ERC.StrictModeViolationError, match=path_fragment) as exc:
>           ERC.assert_strict_mode_valid(schema)
E           Failed: DID NOT RAISE <class 'engine_result_channel.StrictModeViolationError'>

plugins/superheroes/lib/tests/test_engine_result_channel.py:468: Failed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_result_channel.py::test_assert_strict_mode_valid_catches_structural_violations[rule4-array-items]
1 failed in 0.40s
```

**restore:**
```python
    if "array" in type_names:
        if "items" not in schema:
            raise StrictModeViolationError(
                "In context=%s, array schema missing items"
                % _strict_context_path(path)
            )
        assert_strict_mode_valid(schema["items"], path + ("items",))
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.33s
```

---

## BP-A2-5 — object additionalProperties false

- **axis:** object `additionalProperties: false`

**neutralization** (`plugins/superheroes/lib/engine_result_channel.py`, `assert_strict_mode_valid`):
```python
        if False:  # bite-proof neutralization rule 5
            raise StrictModeViolationError(
                "In context=%s, object schema must set additionalProperties to false"
                % _strict_context_path(path)
            )
```
(replaces `if schema.get("additionalProperties") is not False:`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_result_channel.py::test_assert_strict_mode_valid_catches_structural_violations[rule5-additional] -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_assert_strict_mode_valid_catches_structural_violations[rule5-additional] _

schema = {'additionalProperties': True, 'properties': {}, 'required': [], 'type': 'object'}
path_fragment = 'additionalProperties to false'

    def test_assert_strict_mode_valid_catches_structural_violations(schema, path_fragment):
        with pytest.raises(ERC.StrictModeViolationError, match=path_fragment) as exc:
>           ERC.assert_strict_mode_valid(schema)
E           Failed: DID NOT RAISE <class 'engine_result_channel.StrictModeViolationError'>

plugins/superheroes/lib/tests/test_engine_result_channel.py:468: Failed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_result_channel.py::test_assert_strict_mode_valid_catches_structural_violations[rule5-additional]
1 failed in 0.42s
```

**restore:**
```python
        if schema.get("additionalProperties") is not False:
            raise StrictModeViolationError(
                "In context=%s, object schema must set additionalProperties to false"
                % _strict_context_path(path)
            )
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.33s
```

---

## BP-A2-6 — refinement table closed raise

- **axis:** unrefined `list`/`any` raises at build

**neutralization** (`plugins/superheroes/lib/engine_result_channel.py`, `_strict_schema_for_field`):
```python
        if key not in _STRICT_MODE_REFINEMENTS:
            if effective == "list":  # bite-proof neutralization refinement raise
                prop = {"type": "array"}
            else:
                prop = {}
```
(replaces `raise UnrefinedTypeTokenError(...)`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_result_channel.py::test_unrefined_list_token_raises_at_schema_build -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_unrefined_list_token_raises_at_schema_build _______________

    def test_unrefined_list_token_raises_at_schema_build():
        with pytest.raises(ERC.UnrefinedTypeTokenError, match="no strict-mode refinement"):
>           ERC._strict_schema_for_field("synthetic", "orphan", "list")
E           Failed: DID NOT RAISE <class 'engine_result_channel.UnrefinedTypeTokenError'>

plugins/superheroes/lib/tests/test_engine_result_channel.py:520: Failed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_result_channel.py::test_unrefined_list_token_raises_at_schema_build
1 failed in 0.47s
```

**restore:**
```python
        if key not in _STRICT_MODE_REFINEMENTS:
            raise UnrefinedTypeTokenError(
                "no strict-mode refinement for %r field %r (token %r)"
                % (result_kind, field, effective)
            )
        prop = dict(_STRICT_MODE_REFINEMENTS[key])
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.33s
```
