# C14 layer 3b WO-G (#1273) bite-proof — probe-only claude-cell exception

**Provenance:** cursor / composer-2.5 (implementer).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-G1 | `registration-probe` claude cell | probe-pending codex role must have no claude cell (no fall-open) | `test_claude_cells_on_allowlist_per_role` |
| BP-G2 | ordinary role claude cell | non-probe roles must have claude cell that clears dispatch_guard check | `test_claude_cells_on_allowlist_per_role` |

---

## BP-G1 — no-claude-cell half (probe-only roles)

- **axis:** roles whose codex cell names a probe-pending model must have `claude: None`

**neutralization** (`plugins/superheroes/lib/model_registry.py`, `_MATRIX["registration-probe"]`):
```python
        "claude": ("opus-5", "xhigh"),
```
(was `"claude": None`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/wh1273r3-pyc-g -m pytest plugins/superheroes/lib/tests/test_dispatch_guard.py::test_claude_cells_on_allowlist_per_role -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_claude_cells_on_allowlist_per_role ____________________

    def test_claude_cells_on_allowlist_per_role():
        # Roles whose codex cell names a probe-pending model have no claude cell (no fall-open path).
        probe_only = set()
        for role in MR.roles():
            codex_cell = MR.matrix_config(role, "codex")
            if codex_cell is not None:
                model_id = codex_cell[0]
                registration = MR._MODELS["codex"].get(model_id, {}).get("registration")
                if registration == "probe-pending":
                    probe_only.add(role)
        cells_checked = 0
        for role in MR.roles():
            if role in probe_only:
>               assert MR.matrix_config(role, "claude") is None
E               AssertionError: assert ('opus-5', 'xhigh') is None
E                +  where ('opus-5', 'xhigh') = <function matrix_config at 0x10b0ab310>('registration-probe', 'claude')
E                +    where <function matrix_config at 0x10b0ab310> = MR.matrix_config

plugins/superheroes/lib/tests/test_dispatch_guard.py:547: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_dispatch_guard.py::test_claude_cells_on_allowlist_per_role
1 failed in 1.86s
```

**restore** (`plugins/superheroes/lib/model_registry.py`, `_MATRIX["registration-probe"]`):
```python
        "claude": None,
```

**restore receipt:** inverse edit applied; `git diff -- plugins/superheroes/lib/model_registry.py` empty.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 1.76s
```

---

## BP-G2 — strict half (ordinary roles)

- **axis:** non-probe roles must have a claude cell that clears dispatch_guard check

**neutralization** (`plugins/superheroes/lib/model_registry.py`, `_MATRIX["reviewer"]`):
```python
        "claude": None,
```
(was `"claude": ("sonnet-5", "high")`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/wh1273r3-pyc-g -m pytest plugins/superheroes/lib/tests/test_dispatch_guard.py::test_claude_cells_on_allowlist_per_role -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_claude_cells_on_allowlist_per_role ____________________

    def test_claude_cells_on_allowlist_per_role():
        # Roles whose codex cell names a probe-pending model have no claude cell (no fall-open path).
        probe_only = set()
        for role in MR.roles():
            codex_cell = MR.matrix_config(role, "codex")
            if codex_cell is not None:
                model_id = codex_cell[0]
                registration = MR._MODELS["codex"].get(model_id, {}).get("registration")
                if registration == "probe-pending":
                    probe_only.add(role)
        cells_checked = 0
        for role in MR.roles():
            if role in probe_only:
                assert MR.matrix_config(role, "claude") is None
                continue
            cell = MR.matrix_config(role, "claude")
>           assert cell is not None, role
E           AssertionError: reviewer
E           assert None is not None

plugins/superheroes/lib/tests/test_dispatch_guard.py:550: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_dispatch_guard.py::test_claude_cells_on_allowlist_per_role
1 failed in 0.49s
```

**restore** (`plugins/superheroes/lib/model_registry.py`, `_MATRIX["reviewer"]`):
```python
        "claude": ("sonnet-5", "high"),
```

**restore receipt:** inverse edit applied; `git diff -- plugins/superheroes/lib/model_registry.py` empty.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 1.18s
```
