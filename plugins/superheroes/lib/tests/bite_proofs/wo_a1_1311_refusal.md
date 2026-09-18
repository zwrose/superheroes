# WO-A1 (#1311) bite-proof — cross-instance refusal gate

**Provenance:** cursor composer-2.5 / dispatch-write

## Guarded element

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-A1-1 | `launch_build` foreign-instance pin gate | mismatched `CLAUDE_CONFIG_DIR` refuses before reservation | `test_launch_foreign_instance_pin_refuses_mismatch` |

---

## BP-A1-1 — foreign-instance pin refusal

- **axis:** mismatched config roots refuse with `launch-foreign-instance-pin` and both instances named

**neutralization** (`plugins/superheroes/lib/launcher.py`, `launch_build` gate):
```python
        if False and seat_norm != requested_norm:
```
(replaces `if seat_norm != requested_norm:`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_launcher.py::test_launch_foreign_instance_pin_refuses_mismatch -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_launch_foreign_instance_pin_refuses_mismatch _______________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-1411/test_launch_foreign_instance_p0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x10645e580>

    def test_launch_foreign_instance_pin_refuses_mismatch(tmp_path, monkeypatch):
        # axis: mismatched config roots refuse with both instances named
        repo = _init_repo(tmp_path / "repo")
        _ledger_env(tmp_path, monkeypatch)
        _worktree_root(tmp_path, monkeypatch)
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/tmp/launcher-pin")
        monkeypatch.setattr(
            L,
            "seat_config_dir",
            lambda env=None: {"instance": "/tmp/seat-own", "reason": None},
        )
        result = L.launch_build(
            repo,
            656,
            _valid_premise(repo),
            _all_checks(),
            str(tmp_path / "logs"),
        )
        assert result["ok"] is False
>       assert result["reason"] == "launch-foreign-instance-pin"
E       AssertionError: assert 'settle-exit-zero-uncertain' == 'launch-foreign-instance-pin'
E         
E         - launch-foreign-instance-pin
E         + settle-exit-zero-uncertain

plugins/superheroes/lib/tests/test_launcher.py:5434: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_launch_foreign_instance_pin_refuses_mismatch
1 failed in 3.99s
```

**restore:**
```python
        if seat_norm != requested_norm:
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.58s
```
