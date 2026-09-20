# C14 L1 WO-D bite-proof — write-side stdout-delivery gate

## D1 — `_admit_native_write_result` stdout-delivery gate

**Guarded element:** `engine_dispatch.py:3741` `gate = _stdout_delivery_gate(run_dir_real, attempt, opened)` in `_admit_native_write_result` — axis: write admission refuses when stdout carried no result event but the native result path is occupied by a planted valid file.

**Neutralization:** `gate = _stdout_delivery_gate(run_dir_real, attempt, opened)` → `gate = None` (count 1).

**Detector:** `test_claude_write_planted_valid_result_without_stdout_result_forfeits_occupied`

**Raw red:**
```
F
=================================== FAILURES ===================================
_ test_claude_write_planted_valid_result_without_stdout_result_forfeits_occupied _

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-1651/test_claude_write_planted_vali0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x103c8f7c0>

    def test_claude_write_planted_valid_result_without_stdout_result_forfeits_occupied(tmp_path, monkeypatch):
        _ensure_claude_config_dir(tmp_path, monkeypatch)
        wt, _main = _linked_worktree(tmp_path)
        run_dir = str(tmp_path / "occupied-no-result")
        os.makedirs(run_dir, exist_ok=True)
        monkeypatch.setenv("WO_B_CLAUDE_RUN_DIR", os.path.realpath(run_dir))

        plant_calls = []
        valid = _valid_claude_write_structured()

        def plant_no_result(argv, prompt_bytes, timeout, progress_cb, cwd):
            attempt = len(plant_calls) + 1
            plant_calls.append(attempt)
            result_path = ED._native_result_path(os.environ["WO_B_CLAUDE_RUN_DIR"], attempt)
            with open(result_path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(valid, separators=(",", ":")) + "\n")
            return "", False, 0, ""

        res = _dispatch_write(
            tmp_path,
            _ClaudeStdoutWriteFakeRunner([plant_no_result, plant_no_result]),
            cwd=wt,
            run_dir=run_dir,
            seat=_claude_seat(),
        )
>       assert res["forfeited"] is True
E       KeyError: 'forfeited'

plugins/superheroes/lib/tests/test_engine_dispatch_write.py:3624: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_claude_write_planted_valid_result_without_stdout_result_forfeits_occupied
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed, 196 deselected in 0.63s
```

**Restore:** `gate = None` → `gate = _stdout_delivery_gate(run_dir_real, attempt, opened)`.

**Raw green:**
```
.                                                                        [100%]
1 passed, 196 deselected in 0.70s
```

**Post-restore `git status --porcelain`:**
```
 M plugins/superheroes/lib/tests/test_engine_dispatch_write.py
```

---

## Final suite receipt (`-k claude`)

```
.....                                                                    [100%]
5 passed, 192 deselected in 1.48s
```
