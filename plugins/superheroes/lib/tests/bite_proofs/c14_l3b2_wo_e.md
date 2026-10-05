# WO 1273-l3b2-E bite-proofs — Astra ledger control-plane store resolver

**Provenance:** cursor / composer-2.5 (implementer, orders E and E2); BP-E1 red re-run and BP-E2 produced by the orchestrator (claude / Opus 5.5).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-E1 | `_conformance_record_dir` store lookup | the resolver finds the control-plane project store | `test_astra_record_dir_resolves_real_control_plane_layout` |
| BP-E2 | `_conformance_record_dir` don't-mint guard (`os.path.isdir(project_store)`) | an unconfigured project is refused and no `projects/<key>` directory is created | `test_astra_record_dir_refuses_unconfigured_project` |

---

## BP-E1 — the resolver's store lookup

- **axis:** the resolver finds the control-plane project store

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `_conformance_record_dir`):
```python
    entry = store_core.resolve_global(repo_root, mode_registry.control_plane.store_root())
    if entry is None:
        return None, "conformance-record-dir-unresolved"
    record_dir = os.path.join(entry["dir"], "conformance")
```

Note (orchestrator re-run at 195d4788): the neutralization first recorded here named `control_plane.store_root()`; at the head that raises `NameError: name 'control_plane' is not defined` — a wrong red — because the fix removed that import. The line above is the corrected neutralization.

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_record_dir_resolves_real_control_plane_layout`

**raw red** (exit 1):
```
>       assert err is None
E       AssertionError: assert 'conformance-record-dir-unresolved' is None
plugins/superheroes/lib/tests/test_conformance_probe.py:2236: AssertionError
1 failed in 1.67s
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

**raw green** (exit 0): `1 passed in 0.94s`

**additional real-layout evidence:** `test_astra_probe_record_survives_a_fresh_read_in_the_project_store` and `test_astra_probe_cli_end_to_end_through_real_dispatch_review` seed the control-plane `projects/<config_key>/` layout via `_ensure_store_entry`.

## BP-E2 — the don't-mint guard

- **axis:** an unconfigured project is refused and no `projects/<key>` directory is created

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `_conformance_record_dir`):
```python
    if False and not os.path.isdir(project_store):  # bite-proof BP-E2
```

**command:** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_astra_record_dir_refuses_unconfigured_project`

**raw red** (exit 1; the temporary directory prefix is redacted to `<pytest-tmp>`):
```
>       assert record_dir is None
E       AssertionError: assert '<pytest-tmp>/test_astra_record_dir_refuses_0/home/.claude/superheroes/projects/8798eb91acddb461/conformance' is None
1 failed in 0.72s
```

**restore** (`plugins/superheroes/lib/conformance_probe.py`, `_conformance_record_dir`):
```python
    if not os.path.isdir(project_store):
```

**raw green** (exit 0): `1 passed in 1.01s`

**Provenance:** proof produced and run by the orchestrator (claude / Opus 5.5) at `195d4788`; recorded by this order.
