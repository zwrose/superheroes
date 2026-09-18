# WO-A1 (#1311) bite-proof — cross-instance refusal gate

**Provenance:** cursor composer-2.5 / dispatch-write

## Guarded element

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-A1-1 | `launch_build` foreign-instance pin gate | mismatched `CLAUDE_CONFIG_DIR` refuses before reservation | `test_launch_foreign_instance_pin_refuses_mismatch` |
| BP-A1-3 | `launch_build` undetermined-seat gate | seat whose instance cannot be established refuses with `launch-seat-instance-undetermined` before reservation | `test_launch_seat_undetermined_refuses` |
| BP-A1-4 | `seatInstance` validation in `_validate_reserved_optional_fields` | non-absolute / empty / non-string `seatInstance` refused `fold-bad-field:reserved:seatInstance` | `test_reserved_seat_instance_must_be_a_non_empty_absolute_path` |
| BP-A1-5 | `foreignInstanceAllowed` validation in `_validate_reserved_optional_fields` | value other than literal `True` refused `fold-bad-field:reserved:foreignInstanceAllowed` | `test_reserved_foreign_instance_allowed_must_be_literal_true` |

---

## BP-A1-1 — foreign-instance pin refusal

- **axis:** mismatched config roots refuse with `launch-foreign-instance-pin` and both instances named

**neutralization** (`plugins/superheroes/lib/launcher.py`, `launch_build` gate inside `_claude_seat_pin_gate_applies`):
```python
            if False and seat_norm != requested_norm:
```
(replaces `if seat_norm != requested_norm:`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-a4 -m pytest plugins/superheroes/lib/tests/test_launcher.py::test_launch_foreign_instance_pin_refuses_mismatch -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_launch_foreign_instance_pin_refuses_mismatch _______________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-1557/test_launch_foreign_instance_p0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x1044904c0>

    def test_launch_foreign_instance_pin_refuses_mismatch(tmp_path, monkeypatch):
        # axis: mismatched config roots refuse with both instances named
        repo = _init_repo(tmp_path / "repo")
        _ledger_env(tmp_path, monkeypatch)
        _worktree_root(tmp_path, monkeypatch)
        monkeypatch.setenv("CLAUDE_PID", "4242")
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

plugins/superheroes/lib/tests/test_launcher.py:5530: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_launch_foreign_instance_pin_refuses_mismatch
1 failed in 1.52s
```

**restore:**
```python
            if seat_norm != requested_norm:
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.31s
```

---

## BP-A1-3 — undetermined-seat refusal

- **axis:** seat whose instance cannot be established refuses with `launch-seat-instance-undetermined` before any reservation

**neutralization** (`plugins/superheroes/lib/launcher.py`, `launch_build` undetermined-seat gate inside `_claude_seat_pin_gate_applies`):
```python
            if False and not allow_foreign_instance:
```
(replaces `if not allow_foreign_instance:` inside `if seat["instance"] is None:` within `if _claude_seat_pin_gate_applies(env=env):`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-a4 -m pytest plugins/superheroes/lib/tests/test_launcher.py::test_launch_seat_undetermined_refuses[seat_result0] -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_launch_seat_undetermined_refuses[seat_result0] ______________

seat_result = {'instance': None, 'reason': 'seat-pid-absent'}
tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-1559/test_launch_seat_undetermined_0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x1057c64c0>

    @pytest.mark.parametrize(
        "seat_result",
        [
            {"instance": None, "reason": "seat-pid-absent"},
            {"instance": None, "reason": "seat-snapshot-unreadable"},
            {"instance": None, "reason": "seat-not-claude"},
        ],
    )
    def test_launch_seat_undetermined_refuses(seat_result, tmp_path, monkeypatch):
        # axis: each undetermined reason refuses with launch-seat-instance-undetermined
        repo = _init_repo(tmp_path / "repo")
        _ledger_env(tmp_path, monkeypatch)
        _worktree_root(tmp_path, monkeypatch)
        monkeypatch.setenv("CLAUDE_PID", "4242")
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/tmp/launcher-pin")
        monkeypatch.setattr(L, "seat_config_dir", lambda env=None: dict(seat_result))
        result = L.launch_build(
            repo,
            656,
            _valid_premise(repo),
            _all_checks(),
            str(tmp_path / "logs"),
        )
        assert result["ok"] is False
>       assert result["reason"] == "launch-seat-instance-undetermined"
E       AssertionError: assert 'settle-exit-zero-uncertain' == 'launch-seat-...-undetermined'
E         
E         - launch-seat-instance-undetermined
E         + settle-exit-zero-uncertain

plugins/superheroes/lib/tests/test_launcher.py:5706: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_launch_seat_undetermined_refuses[seat_result0]
1 failed in 1.63s
```

**restore:**
```python
            if not allow_foreign_instance:
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.32s
```

---

## BP-A1-4 — seatInstance validation refusal

- **axis:** non-absolute / empty / non-string `seatInstance` is refused `fold-bad-field:reserved:seatInstance`

**neutralization** (`plugins/superheroes/lib/launch_ledger.py`, `_validate_reserved_optional_fields`):
```python
    if False and "seatInstance" in rec:
```
(replaces `if "seatInstance" in rec:`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-a4 -m pytest plugins/superheroes/lib/tests/test_launch_ledger.py::test_reserved_seat_instance_must_be_a_non_empty_absolute_path[] -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_reserved_seat_instance_must_be_a_non_empty_absolute_path[] ________

seat_instance = ''

    @pytest.mark.parametrize(
        "seat_instance",
        ["", "   ", "relative/seat", "~/.claude", 7, None, True],
    )
    def test_reserved_seat_instance_must_be_a_non_empty_absolute_path(seat_instance):
        # axis: non-absolute or empty seatInstance refuses the whole record
        rec = _reserved("l1", "b", ["a"], "/tmp", seatInstance=seat_instance)
        result = ll.fold([rec])
>       assert result["ok"] is False
E       assert True is False

plugins/superheroes/lib/tests/test_launch_ledger.py:5161: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_ledger.py::test_reserved_seat_instance_must_be_a_non_empty_absolute_path[]
1 failed in 0.30s
```

**restore:**
```python
    if "seatInstance" in rec:
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.26s
```

---

## BP-A1-5 — foreignInstanceAllowed validation refusal

- **axis:** value other than literal `True` is refused `fold-bad-field:reserved:foreignInstanceAllowed`

**neutralization** (`plugins/superheroes/lib/launch_ledger.py`, `_validate_reserved_optional_fields`):
```python
    if False and "foreignInstanceAllowed" in rec:
```
(replaces `if "foreignInstanceAllowed" in rec:`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-a4 -m pytest plugins/superheroes/lib/tests/test_launch_ledger.py::test_reserved_foreign_instance_allowed_must_be_literal_true[1] -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_reserved_foreign_instance_allowed_must_be_literal_true[1] ________

foreign_allowed = 1

    @pytest.mark.parametrize("foreign_allowed", [1, "true", False])
    def test_reserved_foreign_instance_allowed_must_be_literal_true(foreign_allowed):
        # axis: only Python True is accepted — not truthy ints or strings
        rec = _reserved("l1", "b", ["a"], "/tmp", foreignInstanceAllowed=foreign_allowed)
        result = ll.fold([rec])
>       assert result["ok"] is False
E       assert True is False

plugins/superheroes/lib/tests/test_launch_ledger.py:5175: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_ledger.py::test_reserved_foreign_instance_allowed_must_be_literal_true[1]
1 failed in 0.30s
```

**restore:**
```python
    if "foreignInstanceAllowed" in rec:
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.26s
```
