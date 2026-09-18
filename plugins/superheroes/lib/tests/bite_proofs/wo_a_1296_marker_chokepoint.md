# WO-A (#1296) bite-proof — resolvedInputs `<field>Source` chokepoint

**Provenance:** cursor-agent / composer-2.5

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-1 | `_put_resolved` in `engine_dispatch.py` | refuses undeclared `<field>Source` markers at the producer chokepoint | `test_live_dispatch_snapshot_source_markers_are_declared` |

---

## BP-1 — producer chokepoint

- **axis:** undeclared marker planted at a real producer is refused before snapshot write; dispatch terminates as `unrunnable` with `detail` `internal-UndeclaredSourceMarker`, mints no `entryReason`, and does not open the run

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

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-734/test_live_dispatch_snapshot_so0')

    def test_live_dispatch_snapshot_source_markers_are_declared(tmp_path):
        repo_root = _repo(tmp_path)
        run_dir = str(tmp_path / "run")
        result = ED.dispatch_review(
            seat=_codex_seat(),
            prompt_path=_valid_prompt(tmp_path),
            repo_root=repo_root,
            run_engine=FakeRunner([]),
            build_view=_fake_build_view(tmp_path),
            run_dir=run_dir,
            max_wait=0,
            order_id="order-1",
        )
>       assert result.get("runOpened") is True, (
            "expected run to open; got reason=%r detail=%r runOpened=%r"
            % (result.get("reason"), result.get("detail"), result.get("runOpened"))
        )
E       AssertionError: expected run to open; got reason='unrunnable' detail='internal-UndeclaredSourceMarker' runOpened=False
E       assert False is True
E        +  where False = <built-in method get of dict object at 0x106d80b80>('runOpened')
E        +    where <built-in method get of dict object at 0x106d80b80> = {'argv': ['codex', 'exec', '--sandbox', 'read-only', '-m', 'gpt-5.6-sol', ...], 'attempts': 0, 'detail': 'internal-UndeclaredSourceMarker', 'forfeited': False, ...}.get

plugins/superheroes/lib/tests/test_resolved_inputs_vocab.py:197: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_resolved_inputs_vocab.py::test_live_dispatch_snapshot_source_markers_are_declared
1 failed in 0.13s
```

**restore:** reinstated `resolved_inputs_vocab.CALLER` at the producer site in `_build_resolved_inputs`.

**restore receipt:**
```python
    _put_resolved(snapshot, "engine", seat.get("vendor"), resolved_inputs_vocab.CALLER)
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.12s
```
