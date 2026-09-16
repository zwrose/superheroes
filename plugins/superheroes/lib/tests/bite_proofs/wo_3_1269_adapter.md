# WO-3 (#1269) bite-proof — build-argv allowlist gate

**Provenance:** cursor-agent / composer-2.5

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-A | `resolve_entry` allowlist leg for `build-argv` | off-allowlist seat refused at build-argv entry | `test_build_argv_cli_off_allowlist_refused` |

BP-B not recorded — model-pin ladder drift closed by extraction (`_resolve_engine_model_pin`), not a drift test.

---

## BP-A — build-argv allowlist gate

- **axis:** off-allowlist seat refused at build-argv entry through `resolve_entry`

**neutralization** (`plugins/superheroes/lib/seat_bundle.py`, `resolve_entry` after model/effort validation):
```python
    if verb == "build-argv":  # bite-proof neutralization BP-A
        return {
            "ok": True,
            "vendor": vendor,
            "model": model,
            "effort": effort,
            "role": role,
            "effortSource": checked.get("effortSource", "caller"),
            "roleSource": "seat",
        }
```
(inserted immediately before `verdict = dispatch_allowlist.validate(...)`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_adapter.py::test_build_argv_cli_off_allowlist_refused -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_build_argv_cli_off_allowlist_refused ___________________

capsys = <_pytest.capture.CaptureFixture object at 0x10258d580>

    def test_build_argv_cli_off_allowlist_refused(capsys):
        rc = EA.main([
            "build-argv",
            "--seat",
            _seat_json("codex", _OFF_ALLOWLIST_CODEX, "high"),
            "--run-kind",
            "review",
        ])
        out = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert out["ok"] is False
        assert out["reason"] == "engine-config"
>       assert out["detail"] == "allowlist-refused"
E       AssertionError: assert 'unregistered-engine-model' == 'allowlist-refused'
E         
E         - allowlist-refused
E         + unregistered-engine-model

plugins/superheroes/lib/tests/test_engine_adapter.py:686: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_build_argv_cli_off_allowlist_refused
1 failed in 0.36s
```

**restore:** removed the `if verb == "build-argv":` early-return block; `dispatch_allowlist.validate` again precedes success for every verb including `build-argv`.

**restored lines quoted back:**
```python
    try:
        verdict = dispatch_allowlist.validate(role, vendor, model, effort)
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.27s
```
