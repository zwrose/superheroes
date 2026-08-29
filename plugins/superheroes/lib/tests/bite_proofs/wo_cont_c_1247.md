# WO-cont-C (#1247) bite-proof — census positional exemptions closed

**Provenance:** cursor-agent / composer-2.5

**Note:** This detector's own module is the file being changed. Neutralizations re-introduce
exemptions in the **matcher** (`census_violations_from_source`'s exemption path inside
`test_canary_outcome_census.py`). The assertions that go red are the **new position tests** —
distinct functions, not the edited matcher logic under test.

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-cont-C1 | `test_matcher_catches_banned_literal_as_dict_key_on_synthetic_source` | a banned member spelled as a dict key is reported | `test_matcher_catches_banned_literal_as_dict_key_on_synthetic_source` |
| BP-cont-C2 | `test_matcher_catches_banned_literal_as_get_argument_on_synthetic_source` | a banned member spelled as a `.get()` argument is reported | `test_matcher_catches_banned_literal_as_get_argument_on_synthetic_source` |

---

## BP-cont-C1 — dict-key position

- **axis:** a banned member spelled as a dict key is reported

**neutralization:** re-introduced `_dict_key_constant_ids` and `exempt_ids = _dict_key_constant_ids(tree)` plus `if id(node) in exempt_ids: continue` inside `census_violations_from_source` (matcher exemption path — not the position test).

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_matcher_catches_banned_literal_as_dict_key_on_synthetic_source ______

    def test_matcher_catches_banned_literal_as_dict_key_on_synthetic_source():
        """axis: a banned member spelled as a dict key is reported."""
        source = (
            "def bad():\n"
            "    return {\"plant-undetected\": 1}\n"
        )
        path = os.path.join(_LIB, "fake_consumer_dict_key.py")
        violations = census_violations_from_source(
            source, path, member_set=canary_outcome.ALL_OUTCOMES)
>       assert violations, violations
E       AssertionError: []
E       assert []

plugins/superheroes/lib/tests/test_canary_outcome_census.py:273: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_canary_outcome_census.py::test_matcher_catches_banned_literal_as_dict_key_on_synthetic_source
1 failed, 9 deselected in 0.32s
```

**restore:** remove `_dict_key_constant_ids` and the `exempt_ids` lookup from `census_violations_from_source` (inverse edit — matcher reports all str constants in `member_set`).

**restore receipt:**
```
 M plugins/superheroes/lib/tests/test_canary_outcome_census.py
```

**restored lines quoted back:**
```python
def census_violations_from_source(source, source_path, *, member_set=None):
    if member_set is None:
        member_set = _LIVE_BANNED_LITERALS
    tree = _parse_source(source, source_path)
    violations = []
    for node in ast.walk(tree):
        ...
        violations.append(
            "%s: literal '%s' (clause: canary outcome tokens live only in "
            "canary_outcome.py regardless of syntactic position)"
            % (_lineno(source_path, node), node.value)
        )
    return violations
```
(no `_dict_key_constant_ids`, no `exempt_ids`, no `if id(node) in exempt_ids: continue`)

**raw green:**
```
..........                                                               [100%]
10 passed in 10.32s
```

---

## BP-cont-C2 — `.get()` first-argument position

- **axis:** a banned member spelled as a `.get()` argument is reported

**neutralization:** re-introduced `_field_lookup_constant_ids` and `exempt_ids = _field_lookup_constant_ids(tree)` plus `if id(node) in exempt_ids: continue` inside `census_violations_from_source` (matcher exemption path — not the position test).

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_matcher_catches_banned_literal_as_get_argument_on_synthetic_source ____

    def test_matcher_catches_banned_literal_as_get_argument_on_synthetic_source():
        """axis: a banned member spelled as a .get() argument is reported."""
        source = (
            "def bad(probe):\n"
            "    return probe.get(\"not-engaged\")\n"
        )
        path = os.path.join(_LIB, "fake_consumer_get_arg.py")
        violations = census_violations_from_source(
            source, path, member_set=canary_outcome.ALL_OUTCOMES)
>       assert violations, violations
E       AssertionError: []
E       assert []

plugins/superheroes/lib/tests/test_canary_outcome_census.py:292: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_canary_outcome_census.py::test_matcher_catches_banned_literal_as_get_argument_on_synthetic_source
1 failed, 9 deselected in 0.18s
```

**restore:** remove `_field_lookup_constant_ids` and the `exempt_ids` lookup from `census_violations_from_source` (inverse edit).

**restore receipt:**
```
 M plugins/superheroes/lib/tests/test_canary_outcome_census.py
```

**restored lines quoted back:** same matcher body as BP-cont-C1 — no `_field_lookup_constant_ids`, no `exempt_ids`, no exemption branch.

**raw green:**
```
..........                                                               [100%]
10 passed in 5.56s
```

---

## Orchestrator re-verification (final head `eb1e998d`)

Verification authority never delegates: the orchestrator re-ran both declared elements itself on the
final integrated head. The neutralization goes in the **matcher**
(`census_violations_from_source`'s exemption path); the assertions that go red are the **position
tests** — distinct functions, so the detector is not editing itself.

### Element 1 — dict-key position

- **neutralization**: an `exempt_ids` set re-added to `census_violations_from_source`, populated
  from every `ast.Dict` key constant, and skipped in the walk.
- **raw red**:

```
plugins/superheroes/lib/tests/test_canary_outcome_census.py:268: AssertionError
FAILED plugins/superheroes/lib/tests/test_canary_outcome_census.py::test_matcher_catches_banned_literal_as_dict_key_on_synthetic_source
1 failed, 1 passed in 0.22s
```

  The `.get()` position test stayed **green** under this neutralization — evidence the two positions
  are independently guarded, not one assertion standing for both.

### Element 2 — `.get()` first-argument position

- **neutralization** (distinct): the same `exempt_ids` set populated instead from every
  `<expr>.get(<const>, …)` first argument.
- **raw red**:

```
plugins/superheroes/lib/tests/test_canary_outcome_census.py:281: AssertionError
FAILED plugins/superheroes/lib/tests/test_canary_outcome_census.py::test_matcher_catches_banned_literal_as_get_argument_on_synthetic_source
1 failed, 1 passed in 0.26s
```

  Symmetrically, the dict-key test stayed green here.

- **restore**: inverse edit removing the `exempt_ids` machinery entirely.
- **restore receipt**: `git status --porcelain` over the whole worktree → empty.
- **raw green**: `10 passed in 1.70s`.
