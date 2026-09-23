# C14 layer 3b-3 WO-B — fail receipts

Advisor-ordered fail receipts for a test-only layer; not bite-proofs.

## R-B1 — plugins/superheroes/lib/tests/test_model_registry.py::test_matrix_cells_reviewer_roles_unchanged_at_base

- **axis:** reviewer-deep, reviewer, and verifier matrix cells at the live registry match the pre-child head baseline.
- **broken subject** (`plugins/superheroes/lib/model_registry.py`, `_MATRIX`): `"codex": ("gpt-5.6-sol", "xhigh"),` → `"codex": ("gpt-5.6-sol", "high"),  # fail-receipt R-B1` (reviewer-deep row only)
- **command:** `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3b3-B -m pytest plugins/superheroes/lib/tests/test_model_registry.py::test_matrix_cells_reviewer_roles_unchanged_at_base -q -p no:xdist`
- **raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_matrix_cells_reviewer_roles_unchanged_at_base ______________

    def test_matrix_cells_reviewer_roles_unchanged_at_base():
        base = _load_model_registry_at_sha(_PRE_CHILD_HEAD)
        compared = 0
        for role in ("reviewer-deep", "reviewer", "verifier"):
            for vendor in ("claude", "codex", "cursor"):
>               assert MR.matrix_config(role, vendor) == base.matrix_config(role, vendor)
E               AssertionError: assert ('gpt-5.6-sol', 'high') == ('gpt-5.6-sol', 'xhigh')
E                 
E                 At index 1 diff: 'high' != 'xhigh'
E                 Use -v to get more diff

plugins/superheroes/lib/tests/test_model_registry.py:571: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_model_registry.py::test_matrix_cells_reviewer_roles_unchanged_at_base
1 failed in 0.34s
```
- **restore:** `"codex": ("gpt-5.6-sol", "high"),  # fail-receipt R-B1` → `"codex": ("gpt-5.6-sol", "xhigh"),`
- **raw green** (exit 0): `1 passed in 0.31s`

Other touched tests under R-B1 neutralization: `test_registered_astra_on_reviewer_deep_allowlist_and_probe_role_admits` and `test_planted_probe_pending_astra_hidden_from_ladder_and_allowlist` both stayed green (they read `MR.matrix_config("reviewer-deep", "codex")` at the call site).

## R-B2 — plugins/superheroes/lib/tests/test_model_registry.py::test_matrix_cells_reviewer_roles_unchanged_at_base

- **axis:** reviewer-deep, reviewer, and verifier matrix cells at the live registry match the pre-child head baseline.
- **broken subject** (`plugins/superheroes/lib/tests/test_model_registry.py`, `_PRE_CHILD_HEAD`): `"aaf27b8089159c2ea4020b03ccbddcd263c57e8a"` → `"0000000000000000000000000000000000000000"`
- **command:** `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3b3-B -m pytest plugins/superheroes/lib/tests/test_model_registry.py::test_matrix_cells_reviewer_roles_unchanged_at_base -q -p no:xdist`
- **raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_matrix_cells_reviewer_roles_unchanged_at_base ______________

    def test_matrix_cells_reviewer_roles_unchanged_at_base():
>       base = _load_model_registry_at_sha(_PRE_CHILD_HEAD)

plugins/superheroes/lib/tests/test_model_registry.py:567: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
plugins/superheroes/lib/tests/test_model_registry.py:552: in _load_model_registry_at_sha
    proc = subprocess.run(
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

...
E               subprocess.CalledProcessError: Command '['git', '-C', '/Users/zwrose/.superheroes-worktrees/superheroes/wo-1273-l3b3-B', 'show', '0000000000000000000000000000000000000000:plugins/superheroes/lib/model_registry.py']' returned non-zero exit status 128.

/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/subprocess.py:528: CalledProcessError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_model_registry.py::test_matrix_cells_reviewer_roles_unchanged_at_base
1 failed in 0.36s
```
- **restore:** `"0000000000000000000000000000000000000000"` → `"aaf27b8089159c2ea4020b03ccbddcd263c57e8a"`
- **raw green** (exit 0): `1 passed in 0.28s`
