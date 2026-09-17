# WO-9 (#1269) bite-proof — dispatch entry doc cross-process determinism

**Provenance:** cursor / composer-2.5

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-9-1 | `test_generator_deterministic_across_processes` | two independent interpreter processes produce byte-identical generated output | `test_generator_deterministic_across_processes` |

---

## BP-9-1 — generator deterministic across processes

- **axis:** two independent interpreter processes produce byte-identical generated output

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_PARAM_UNSET`):
```python
_PARAM_UNSET = object()  # bite-proof neutralization
```
(replaces `_ParamUnsetType` singleton with stable `__repr__`)

**neutralization** (`plugins/superheroes/lib/dispatch_entry_doc.py`, `_format_default`):
```python
    if isinstance(action.default, str):
```
(removed `if action.default is engine_dispatch._PARAM_UNSET: return "runtime (see Variance envelope)"` guard)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_dispatch_entry_doc.py::test_generator_deterministic_across_processes -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_generator_deterministic_across_processes _________________

    def test_generator_deterministic_across_processes():
        # bite-axis: two independent interpreter processes produce byte-identical output.
        first = _generate_in_subprocess()
        second = _generate_in_subprocess()
>       assert first == second
E       AssertionError: assert '<!-- generat...0 seconds |\n' == '<!-- generat...0 seconds |\n'
E         
E         Skipping 2115 identical leading characters in diff, use -v to show
E         Skipping 3514 identical trailing characters in diff, use -v to show
E         - ct at 0x10412ce10> |  |
E         ?            ---
E         + ct at 0x105aa4e10> |  |
E         ?           +++...
E         
E         ...Full output truncated (36 lines hidden), use '-vv' to show

plugins/superheroes/lib/tests/test_dispatch_entry_doc.py:113: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_dispatch_entry_doc.py::test_generator_deterministic_across_processes
1 failed in 0.31s
```

**restore** (`plugins/superheroes/lib/engine_dispatch.py`):
```python
class _ParamUnsetType:
    """Sentinel: argparse default meaning caller omitted a provenance-tracked optional flag."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "none"


_PARAM_UNSET = _ParamUnsetType()
```

**restore** (`plugins/superheroes/lib/dispatch_entry_doc.py`, `_format_default`):
```python
    if action.default is engine_dispatch._PARAM_UNSET:
        return "runtime (see Variance envelope)"
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.30s
```

**restore receipt:**
```
 M docs/superheroes/KEEP-OR-RETIRE.md
 M plugins/superheroes/TRANSITION.md
 M plugins/superheroes/lib/tests/bite_proofs/wo_9_1269_doc_determinism.md
 M plugins/superheroes/skills/review-code/reference/auto-fix-loop.md
 M plugins/superheroes/skills/workhorse/SKILL.md
```

