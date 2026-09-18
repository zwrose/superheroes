# WO-8 (#1269) bite-proof — provenance truthfulness and corrupt-journal echo

**Provenance:** cursor / composer-2.5

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-8-1 | `_build_resolved_inputs` model/engineModel sources | resolved model must not be recorded as caller-supplied | `test_wo8_edge1_cursor_implementer_null_model_snapshot_sources` |
| BP-8-2 | `_resolved_inputs_echo_from_run_dir` corrupt branch | corrupt journal without run-opened must not claim opened | `test_wo8_edge4_corrupt_journal_without_opened_not_reported_opened` |

---

## BP-8-1 — source truthfulness

- **axis:** resolved model must not be recorded as caller-supplied

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_build_resolved_inputs`):
```python
    _put_resolved(snapshot, "model", seat.get("model"), "caller")
    ...
    _put_resolved(snapshot, "engineModel", engine_model, engine_model_source)
```
(replaces `model_source = seat.get("modelSource", "caller")` and propagating `model_source` to model/engineModel)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_wo8_edge1_cursor_implementer_null_model_snapshot_sources -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_wo8_edge1_cursor_implementer_null_model_snapshot_sources _________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-631/test_wo8_edge1_cursor_implemen0')

    def test_wo8_edge1_cursor_implementer_null_model_snapshot_sources(tmp_path):
        # axis: resolved model must not be recorded as caller-supplied
        wt, _main = _linked_worktree(tmp_path)
        fake = FakeRunner([])
        run_dir = str(tmp_path / "wo8-null-model")
        _dispatch_write(
            tmp_path,
            fake,
            cwd=wt,
            run_dir=run_dir,
            seat=_seat_json("cursor", None, None),
            max_wait=0,
        )
        snapshot = _write_opened_resolved_inputs(run_dir)
        assert snapshot["model"] == "composer-2.5"
>       assert snapshot["modelSource"] == "seat-default"
E       AssertionError: assert 'caller' == 'seat-default'
E         
E         - seat-default
E         + caller

plugins/superheroes/lib/tests/test_engine_dispatch_write.py:2593: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_wo8_edge1_cursor_implementer_null_model_snapshot_sources
1 failed in 1.69s
```

**restore:**
```python
    model_source = seat.get("modelSource", "caller")
    _put_resolved(snapshot, "model", seat.get("model"), model_source)
    ...
    _put_resolved(snapshot, "engineModel", engine_model, model_source)
```

**raw green:**
```
.                                                                        [100%]
1 passed in 1.01s
```

---

## BP-8-2 — corrupt-journal opened claim

- **axis:** corrupt journal with no valid run-opened must not claim `runOpened: true`

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_resolved_inputs_echo_from_run_dir`):
```python
        if corrupt:
            return {"runOpened": True, "resolvedInputsStatus": "journal-corrupt"}
        opened = _journal_state(records).get("opened")
        if opened is None:
            return {"runOpened": False}
```
(replaces computing `opened` first and returning `unverifiable` when corrupt with no opened record)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_wo8_edge4_corrupt_journal_without_opened_not_reported_opened -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_wo8_edge4_corrupt_journal_without_opened_not_reported_opened _______

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-633/test_wo8_edge4_corrupt_journal0')

    def test_wo8_edge4_corrupt_journal_without_opened_not_reported_opened(tmp_path):
        # axis: corrupt journal with no valid run-opened must not claim runOpened true
        run_dir = str(tmp_path / "wo8-corrupt-empty")
        os.makedirs(run_dir, exist_ok=True)
        path = ED._journal_path(run_dir)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("not-json\n")
        echo = ED._resolved_inputs_echo_from_run_dir(run_dir)
>       assert echo["runOpened"] is False
E       assert True is False

plugins/superheroes/lib/tests/test_engine_dispatch.py:8839: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_wo8_edge4_corrupt_journal_without_opened_not_reported_opened
1 failed in 1.17s
```

**restore:** removed the early `if corrupt: return {"runOpened": True, ...}` branch; journal state is computed before forming the echo.

**raw green:**
```
.                                                                        [100%]
1 passed in 1.07s
```
