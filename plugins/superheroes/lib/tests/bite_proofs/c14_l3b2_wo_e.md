# WO 1273-l3b2-E bite-proofs — Astra ledger control-plane store resolver

**Provenance:** cursor / composer-2.5 (implementer).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-E1 | `_conformance_record_dir` store lookup | the resolver finds the control-plane project store | `test_astra_record_dir_resolves_real_control_plane_layout` |

---

## BP-E1 — the resolver's store lookup

- **axis:** the resolver finds the control-plane project store

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `_conformance_record_dir`):
```python
    entry = store_core.resolve_global(repo_root, control_plane.store_root())
    if entry is None:
        return None, "conformance-record-dir-unresolved"
    record_dir = os.path.join(entry["dir"], "conformance")
```

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_record_dir_resolves_real_control_plane_layout`

**raw red** (exit 1):
```
>       assert err is None
E       AssertionError: assert 'conformance-record-dir-unresolved' is None
1 failed in 0.82s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `_conformance_record_dir`):
```python
    try:
        project_store = mode_registry.project_store_dir(repo_root)
    except Exception:
        return None, "conformance-record-dir-unresolved"
    if not os.path.isdir(project_store):
        return None, "conformance-record-dir-unresolved"
    record_dir = os.path.join(project_store, "conformance")
```

**raw green** (exit 0): `1 passed in 1.09s`

**additional real-layout evidence:** `test_astra_probe_record_survives_a_fresh_read_in_the_project_store` and `test_astra_probe_cli_end_to_end_through_real_dispatch_review` seed the control-plane `projects/<config_key>/` layout via `_ensure_store_entry`.
