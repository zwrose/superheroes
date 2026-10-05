# C14 layer 3b-3 WO-C — fail receipts

Advisor-ordered fail receipts for a test-only layer; not bite-proofs.

## R-C1 — test_astra_probe_refuses_when_rubric_scale_unreadable_heading_absent

- **axis:** absent ## Severity tiers heading refuses before claim or dispatch
- **broken subject** (`plugins/superheroes/lib/conformance_probe.py`, `_severity_scale`, the heading match): `if line.strip() == "## Severity tiers":` → `if line.strip().startswith("## Severity"):  # fail-receipt R-C1`
- **command:** `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3b3-C -m pytest plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_probe_refuses_when_rubric_scale_unreadable_heading_absent -q -p no:xdist`
- **raw red** (exit 1):

```
>       assert out["reason"] == "astra-probe-scale-unreadable"
E       KeyError: 'reason'
plugins/superheroes/lib/tests/test_conformance_probe.py:2541: KeyError
1 failed in 1.69s
```

- **restore:** `if line.strip().startswith("## Severity"):  # fail-receipt R-C1` → `if line.strip() == "## Severity tiers":`
- **raw green** (exit 0): `1 passed in 1.62s`

## R-C2 — test_astra_record_dir_refuses_when_store_lookup_raises

- **axis:** store lookup exception refuses before minting conformance dir (real input: dead `.git` gitdir pointer to a nonexistent path makes `mode_registry.project_store_dir` raise `store_core.RepoRootUnavailable`)
- **broken subject** (`plugins/superheroes/lib/conformance_probe.py`, `_conformance_record_dir`): `return None, "conformance-record-dir-unresolved"` → `raise  # fail-receipt R-C2` (inside `except Exception:`)
- **command:** `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3b3-C -m pytest plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_record_dir_refuses_when_store_lookup_raises -q -p no:xdist`
- **raw red** (exit 1):

```
>       record_dir, err = CP._conformance_record_dir(str(repo))
E       store_core.RepoRootUnavailable: repository root indeterminate at .../repo: .git present at .../repo but git declined: fatal: not a git repository: /nonexistent/path
plugins/superheroes/lib/store_core.py:81: RepoRootUnavailable
1 failed in 1.92s
```

- **restore:** `raise  # fail-receipt R-C2` → `return None, "conformance-record-dir-unresolved"`
- **raw green** (exit 0): `1 passed in 1.56s`
