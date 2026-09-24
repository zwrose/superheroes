# WO-D (#1340 layer 2c) bite-proof — `launcher.py` layer gate refusal tokens

Per-guard bite proof for the two new refusing clauses in `_apply_stack_gate`.

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-D-1 | `_apply_stack_gate` order-mismatch branch | membership `order-mismatch` maps to gate `order-mismatch` with reader detail | `test_stack_gate_order_mismatch_refuses_with_detail` |
| BP-D-2 | `_apply_stack_gate` layer-position-occupied branch | claimed `layerPosition` already present in membership | `test_stack_gate_layer_position_occupied_refuses` |

---

## BP-D-1 — order-mismatch mapping

- **axis:** membership `order-mismatch` maps to gate `order-mismatch` with reader detail

**neutralization** (`plugins/superheroes/lib/launcher.py`):
```python
        if False and reason == stack_check.REASON_ORDER_MISMATCH:
```
(replaces `if reason == stack_check.REASON_ORDER_MISMATCH:`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-woD -m pytest 'plugins/superheroes/lib/tests/test_launcher.py::test_stack_gate_order_mismatch_refuses_with_detail' -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_stack_gate_order_mismatch_refuses_with_detail ______________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2647/test_stack_gate_order_mismatch0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x103dca670>

    def test_stack_gate_order_mismatch_refuses_with_detail(tmp_path, monkeypatch):
      # bite-axis: membership order-mismatch maps to gate order-mismatch with reader detail
        repo = _init_repo(tmp_path / "repo")
        _ledger_env(tmp_path, monkeypatch)
        log_dir = str(tmp_path / "logs")
        reader_detail = "collected positions are not exactly 1..size"

        def reader(**kwargs):
            return {
                "ok": False,
                "reason": L.stack_check.REASON_ORDER_MISMATCH,
                "detail": reader_detail,
            }

        result = L.launch_build(
            repo,
            656,
            _stack_premise(repo, stack=1, layerPosition=2),
            _all_checks(),
            log_dir,
            pr_lookup=lambda *a, **k: _pr_lookup_ok(),
            membership_reader=reader,
        )
        assert result["ok"] is False
>       assert result["reason"] == "order-mismatch"
E       AssertionError: assert 'stack-read-unavailable' == 'order-mismatch'
E         
E         - order-mismatch
E         + stack-read-unavailable

plugins/superheroes/lib/tests/test_launcher.py:6362: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_stack_gate_order_mismatch_refuses_with_detail
1 failed in 0.60s
```

**restore:**
```python
        if reason == stack_check.REASON_ORDER_MISMATCH:
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.57s
```

---

## BP-D-2 — layer-position-occupied check

- **axis:** claimed `layerPosition` already present in membership

**neutralization** (`plugins/superheroes/lib/launcher.py`):
```python
    if False and layer_pos >= 2:
```
(replaces `if layer_pos >= 2:`)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-woD -m pytest 'plugins/superheroes/lib/tests/test_launcher.py::test_stack_gate_layer_position_occupied_refuses' -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_stack_gate_layer_position_occupied_refuses ________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2650/test_stack_gate_layer_position0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x1060356a0>

    def test_stack_gate_layer_position_occupied_refuses(tmp_path, monkeypatch):
      # bite-axis: claimed layerPosition already present in membership refuses layer-position-occupied
        repo = _init_repo(tmp_path / "repo")
        _ledger_env(tmp_path, monkeypatch)
        log_dir = str(tmp_path / "logs")
        head = _head_sha(repo)
        members = [
            {"position": 1, "number": 1352, "headRefOid": head, "headRefName": "b1", "baseRefName": "main"},
            {"position": 2, "number": 9999, "headRefOid": "a" * 40, "headRefName": "b2", "baseRefName": "main"},
        ]

        def reader(**kwargs):
            return _membership_ok(1, head, members=members)

        result = L.launch_build(
            repo,
            656,
            _stack_premise(repo, stack=1, layerPosition=2),
            _all_checks(),
            log_dir,
            pr_lookup=lambda *a, **k: _pr_lookup_ok(),
            membership_reader=reader,
        )
>       assert result["ok"] is False
E       assert True is False

plugins/superheroes/lib/tests/test_launcher.py:6389: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_stack_gate_layer_position_occupied_refuses
1 failed in 21.01s
```

**restore:**
```python
    if layer_pos >= 2:
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.60s
```
