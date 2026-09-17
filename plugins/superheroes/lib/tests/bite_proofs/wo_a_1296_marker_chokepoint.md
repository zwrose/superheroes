# WO-A (#1296) bite-proof — resolvedInputs `<field>Source` chokepoint

**Provenance:** cursor-agent / composer-2.5

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-1 | `_put_resolved` in `engine_dispatch.py` | refuses undeclared `<field>Source` markers at the producer chokepoint | `test_put_resolved_refuses_undeclared_marker` |

---

## BP-1 — producer chokepoint

- **axis:** undeclared marker planted at a real producer is refused before snapshot write

**neutralization** (`engine_dispatch.py`, `_build_resolved_inputs` producer):
```python
    _put_resolved(snapshot, "engine", seat.get("vendor"), "callr")
```
(replaced `resolved_inputs_vocab.CALLER` with misspelled `"callr"`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_resolved_inputs_vocab.py::test_live_dispatch_snapshot_source_markers_are_declared -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_live_dispatch_snapshot_source_markers_are_declared ____________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-720/test_live_dispatch_snapshot_so0')

    def test_live_dispatch_snapshot_source_markers_are_declared(tmp_path):
        repo_root = _repo(tmp_path)
        run_dir = str(tmp_path / "run")
        ED.dispatch_review(
            seat=_codex_seat(),
            prompt_path=_valid_prompt(tmp_path),
            repo_root=repo_root,
            run_engine=FakeRunner([]),
            build_view=_fake_build_view(tmp_path),
            run_dir=run_dir,
            max_wait=0,
            order_id="order-1",
        )
>       snapshot = _opened_resolved_inputs(run_dir)

plugins/superheroes/lib/tests/test_resolved_inputs_vocab.py:208: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

run_dir = '/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-720/test_live_dispatch_snapshot_so0/run'

    def _opened_resolved_inputs(run_dir):
        records, _ = ED._journal_read(run_dir)
>       opened = next(r for r in records if r.get("kind") == "run-opened")
E       StopIteration

plugins/superheroes/lib/tests/test_resolved_inputs_vocab.py:159: StopIteration
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_resolved_inputs_vocab.py::test_live_dispatch_snapshot_source_markers_are_declared
1 failed in 0.12s
```

**chokepoint refusal text** (from direct `_put_resolved` call with planted marker):
```
UndeclaredSourceMarker: resolvedInputs source marker 'callr' is not declared; accepted: caller, clamped, declared-none, default, environment-variable, legacy-journal, resolved, run-dir-pointer, seat, seat-default, temp-directory
```

**restore:** reinstated `resolved_inputs_vocab.CALLER` at the producer site in `_build_resolved_inputs`.

**restore receipt:**
```python
    _put_resolved(snapshot, "engine", seat.get("vendor"), resolved_inputs_vocab.CALLER)
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.17s
```
