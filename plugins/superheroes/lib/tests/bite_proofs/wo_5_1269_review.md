# WO-5 (#1269) bite-proof — build-argv role/sandbox coherence refusal

**Provenance:** cursor / composer-2.5

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-WO5-1 | `_cmd_build_argv` run-kind derivation + mismatch refusal | reviewer seat cannot receive workspace-write via `--run-kind build` | `test_build_argv_cli_reviewer_run_kind_build_refused` |

---

## BP-WO5-1 — role/sandbox coherence refusal

- **axis:** sandbox run kind is derived from the validated seat role; a disagreeing `--run-kind` is refused and never emits argv

**neutralization** (`plugins/superheroes/lib/engine_adapter.py`, `_cmd_build_argv`):
```python
    if False and args.run_kind != derived_run_kind:  # bite-proof neutralization WO-5
        ...
    res = build_argv_result(resolved, args.run_kind, opts)  # bite-proof neutralization WO-5
```
(replaces the live mismatch refusal and `build_argv_result(resolved, derived_run_kind, opts)`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_adapter.py::test_build_argv_cli_reviewer_run_kind_build_refused -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_build_argv_cli_reviewer_run_kind_build_refused ______________

capsys = <_pytest.capture.CaptureFixture object at 0x102f2a190>

    def test_build_argv_cli_reviewer_run_kind_build_refused(capsys):
        rc = EA.main([
            "build-argv",
            "--seat",
            _seat_json("codex", "gpt-5.6-terra", "high", "reviewer"),
            "--run-kind",
            "build",
        ])
        out = json.loads(capsys.readouterr().out)
        assert rc == 0
>       assert out["ok"] is False
E       TypeError: list indices must be integers or slices, not str

plugins/superheroes/lib/tests/test_engine_adapter.py:700: TypeError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_build_argv_cli_reviewer_run_kind_build_refused
1 failed in 0.80s
```

**restore:**
```python
    if args.run_kind != derived_run_kind:
        mismatch = seat_bundle.build_argv_run_kind_mismatch_refusal(
            role, supplied=args.run_kind, accepted=derived_run_kind,
        )
        sys.stdout.write(json.dumps(
            {"ok": False, "reason": "engine-config", "detail": mismatch["reason"],
             "argv": [], "seat_detail": mismatch["detail"]}) + "\n")
        return 0
    opts = {"cwd": args.cwd}
    res = build_argv_result(resolved, derived_run_kind, opts)
```

**raw green:**
```
.                                                                        [100%]
1 passed in 1.05s
```
