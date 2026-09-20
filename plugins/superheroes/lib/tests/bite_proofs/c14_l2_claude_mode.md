# C14 layer 2 bite-proof — caller-facing claude mode threading (#1273 WO-B1)

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-1 | `_claude_mode_unknown_detail` | garbage `claude_mode` refuses before open with `claude-mode-unknown:<value>` | `test_claude_mode_unknown_refused_before_open` |
| BP-2 | `_claude_mode_unsupported_detail` | `background` on non-claude seat refuses with `claude-mode-unsupported:<vendor>` | `test_claude_mode_unsupported_codex_background_refused` |
| BP-3 | review continuation claude-mode mismatch gate | disagreeing `--claude-mode` refuses `run-dir-claude-mode-mismatch` with `attempts: 0` | `test_run_dir_claude_mode_mismatch_refused` |
| BP-4 | `_spawn_attempt` background guard | opened `claudeMode: background` refuses spawn with `claude-mode-not-dispatchable:background`, no injected runner | `test_claude_mode_background_review_open_records_caller_provenance` |
| BP-5 | `result_delivery` undeclared-mode raise | unknown `(engine, mode)` pair raises instead of falling back | `test_result_delivery_undeclared_mode_refuses` |
| BP-6 | `build_argv_result` `unknown-claude-mode` refusal | non-string / unknown `claudeMode` refuses with token `unknown-claude-mode` | `test_build_argv_unknown_claude_mode_refuses` |
| BP-7 | `build_argv_result` `claude-mode-unsupported` refusal | `background` on non-claude vendor refuses with token `claude-mode-unsupported` | `test_build_argv_claude_mode_unsupported_on_codex` |
| BP-8 | write `_claude_mode_unknown_detail` | garbage `claude_mode` on write refuses before open with `claude-mode-unknown:<value>` | `test_claude_mode_unknown_refused_before_open_write` |
| BP-9 | write `_claude_mode_unsupported_detail` | `background` on codex write seat refuses with `claude-mode-unsupported:codex` | `test_claude_mode_unsupported_codex_background_refused_write` |
| BP-10 | write continuation claude-mode mismatch gate | disagreeing `--claude-mode` on write refuses `run-dir-claude-mode-mismatch` with `attempts: 0` | `test_run_dir_claude_mode_mismatch_refused_write` |

---

## BP-1 — `claude-mode-unknown`

- **axis:** garbage `claude_mode` refuses before open with detail `claude-mode-unknown:<value>`, no spawn

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`):

```python
def _claude_mode_unknown_detail(value):
    return "wrong-claude-mode-detail"
```

**command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_mode_unknown_refused_before_open -q
```

**raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_claude_mode_unknown_refused_before_open _________________

    def test_claude_mode_unknown_refused_before_open(tmp_path):
        ...
        assert res["detail"] == "claude-mode-unknown:'bogus'"
E       assert 'wrong-claude-mode-detail' == "claude-mode-unknown:'bogus'"
E         
E         - claude-mode-unknown:'bogus'
E         + wrong-claude-mode-detail

=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_mode_unknown_refused_before_open
1 failed in 2.13s
```

**restore:** revert `_claude_mode_unknown_detail` to `return "claude-mode-unknown:%s" % _coerce_rejected_mode(value)`.

**restore receipt:** restored lines quoted above; `git status --porcelain` shows only the WO-B1 deliverable edits on `engine_dispatch.py` and `test_engine_dispatch.py`.

**raw green:**

```
.                                                                        [100%]
1 passed in 3.11s
```

---

## BP-2 — `claude-mode-unsupported`

- **axis:** `background` on codex seat refuses with detail `claude-mode-unsupported:codex`

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`):

```python
def _claude_mode_unsupported_detail(vendor):
    return "wrong-unsupported-detail"
```

**command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_mode_unsupported_codex_background_refused -q
```

**raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_claude_mode_unsupported_codex_background_refused _____________

    def test_claude_mode_unsupported_codex_background_refused(tmp_path):
        ...
        assert res["detail"] == "claude-mode-unsupported:codex"
E       AssertionError: assert 'wrong-unsupported-detail' == 'claude-mode-...pported:codex'
E         
E         - claude-mode-unsupported:codex
E         + wrong-unsupported-detail

=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_mode_unsupported_codex_background_refused
1 failed in 3.82s
```

**restore:** revert `_claude_mode_unsupported_detail` to `return "claude-mode-unsupported:%s" % vendor`.

**restore receipt:** restored lines quoted above.

**raw green:**

```
.                                                                        [100%]
1 passed in 2.89s
```

---

## BP-3 — `run-dir-claude-mode-mismatch`

- **axis:** continuation with disagreeing `claude_mode` refuses `run-dir-claude-mode-mismatch` with `attempts: 0`

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, review continuation branch):

```python
                if False and claude_mode is not None and claude_mode != journal_claude_mode:
```

**command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_run_dir_claude_mode_mismatch_refused -q
```

**raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_run_dir_claude_mode_mismatch_refused ___________________

    def test_run_dir_claude_mode_mismatch_refused(tmp_path, monkeypatch):
        ...
>       assert res["detail"] == ED.MODE_REFUSAL_RUN_DIR_CLAUDE_MODE_MISMATCH
E       KeyError: 'detail'

=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_run_dir_claude_mode_mismatch_refused
1 failed in 3.44s
```

**restore:** remove the `False and` prefix from the continuation mismatch condition.

**restore receipt:** restored lines quoted above.

**raw green:**

```
.                                                                        [100%]
1 passed in 2.66s
```

---

## BP-4 — `_spawn_attempt` background guard

- **axis:** opened `claudeMode: background` refuses spawn with `claude-mode-not-dispatchable:background`, injected runner never called

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_spawn_attempt`):

```python
        if claude_mode == engine_result_channel.MODE_PRINT:
            return False, "claude-mode-not-dispatchable:background"
```

**command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_mode_background_review_open_records_caller_provenance -q
```

**raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_claude_mode_background_review_open_records_caller_provenance _______

    def test_claude_mode_background_review_open_records_caller_provenance(tmp_path, monkeypatch):
        ...
        assert res["detail"] == "claude-mode-not-dispatchable:background"
E       AssertionError: assert 'internal-AssertionError' == 'claude-mode-...le:background'
E         
E         - claude-mode-not-dispatchable:background
E         + internal-AssertionError

=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_mode_background_review_open_records_caller_provenance
1 failed in 1.52s
```

**restore:** revert comparison to `engine_result_channel.MODE_BACKGROUND`.

**restore receipt:** restored lines quoted above.

**raw green:**

```
.                                                                        [100%]
1 passed in 1.45s
```

---

## BP-5 — `result_delivery` undeclared-mode raise

- **axis:** unknown claude mode on a registered engine raises `ValueError` instead of returning a delivery entry

**neutralization** (`plugins/superheroes/lib/engine_result_channel.py`, `result_delivery`):

```python
    if mode is not None and mode not in CLAUDE_MODES:
        return RESULT_DELIVERY_ARGV
```

**command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_result_channel.py::test_result_delivery_undeclared_mode_refuses -q
```

**raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_result_delivery_undeclared_mode_refuses _________________

    def test_result_delivery_undeclared_mode_refuses():
        with pytest.raises(ValueError, match="unknown claude mode"):
>           ERC.result_delivery("claude", "bogus")
E           Failed: DID NOT RAISE <class 'ValueError'>

=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_result_channel.py::test_result_delivery_undeclared_mode_refuses
1 failed in 0.36s
```

**restore:** revert body to `raise ValueError("unknown claude mode %r; declared modes: print, background" % (mode,))`.

**restore receipt:** restored lines quoted above.

**raw green:**

```
.                                                                        [100%]
1 passed in 0.31s
```

---

## BP-6 — adapter `unknown-claude-mode`

- **axis:** garbage `claudeMode` in `build_argv_result` refuses with reason token `unknown-claude-mode`

**neutralization** (`plugins/superheroes/lib/engine_adapter.py`):

```python
            return _refuse(
                "wrong-unknown-claude-mode",
```

(both `unknown-claude-mode` refusal sites in the `claude_mode != "print"` branch)

**command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_adapter.py::test_build_argv_unknown_claude_mode_refuses -q
```

**raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_build_argv_unknown_claude_mode_refuses __________________

    def test_build_argv_unknown_claude_mode_refuses():
>       res = EA.build_argv_result(_seat("claude", "sonnet-5", "high"), "review", {"claudeMode": 123})
...
    def _refuse(reason, *, detail=None):
>       assert reason in BUILD_ARGV_REFUSAL_TOKENS
E       AssertionError

=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_build_argv_unknown_claude_mode_refuses
1 failed in 0.62s
```

**restore:** revert both refusal sites to `"unknown-claude-mode"`.

**restore receipt:** restored lines quoted above.

**raw green:**

```
...                                                                      [100%]
3 passed, 577 deselected in 0.37s
```

---

## BP-7 — adapter `claude-mode-unsupported`

- **axis:** `background` on codex in `build_argv_result` refuses with reason token `claude-mode-unsupported`

**neutralization** (`plugins/superheroes/lib/engine_adapter.py`):

```python
            return _refuse(
                "wrong-claude-mode-unsupported",
```

**command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_adapter.py::test_build_argv_claude_mode_unsupported_on_codex -q
```

**raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_build_argv_claude_mode_unsupported_on_codex _______________

    def test_build_argv_claude_mode_unsupported_on_codex():
>       res = EA.build_argv_result(
            _seat("codex", "gpt-5.6-sol", "high"), "review", {"claudeMode": "background"},
        )
...
    def _refuse(reason, *, detail=None):
>       assert reason in BUILD_ARGV_REFUSAL_TOKENS
E       AssertionError

=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_build_argv_claude_mode_unsupported_on_codex
1 failed in 0.68s
```

**restore:** revert refusal site to `"claude-mode-unsupported"`.

**restore receipt:** restored lines quoted above.

**raw green:**

```
...                                                                      [100%]
3 passed, 577 deselected in 0.37s
```

---

## BP-8 — write `claude-mode-unknown`

- **axis:** garbage `claude_mode` on `dispatch_write` refuses before open with detail `claude-mode-unknown:<value>`, no spawn

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`):

```python
def _claude_mode_unknown_detail(value):
    return "wrong-claude-mode-detail"
```

**command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_claude_mode_unknown_refused_before_open_write -q
```

**raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_claude_mode_unknown_refused_before_open_write ______________

    def test_claude_mode_unknown_refused_before_open_write(tmp_path):
        ...
        assert res["detail"] == "claude-mode-unknown:'bogus'"
E       assert 'wrong-claude-mode-detail' == "claude-mode-unknown:'bogus'"
E         
E         - claude-mode-unknown:'bogus'
E         + wrong-claude-mode-detail

=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_claude_mode_unknown_refused_before_open_write
1 failed in 0.45s
```

**restore:** revert `_claude_mode_unknown_detail` to `return "claude-mode-unknown:%s" % _coerce_rejected_mode(value)`.

**restore receipt:** restored lines quoted above.

**raw green:**

```
...                                                                      [100%]
3 passed, 197 deselected in 0.75s
```

---

## BP-9 — write `claude-mode-unsupported`

- **axis:** `background` on codex write seat refuses with detail `claude-mode-unsupported:codex`

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`):

```python
def _claude_mode_unsupported_detail(vendor):
    return "wrong-unsupported-detail"
```

**command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_claude_mode_unsupported_codex_background_refused_write -q
```

**raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_claude_mode_unsupported_codex_background_refused_write __________

    def test_claude_mode_unsupported_codex_background_refused_write(tmp_path):
        ...
        assert res["detail"] == "claude-mode-unsupported:codex"
E       AssertionError: assert 'wrong-unsupported-detail' == 'claude-mode-...pported:codex'
E         
E         - claude-mode-unsupported:codex
E         + wrong-unsupported-detail

=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_claude_mode_unsupported_codex_background_refused_write
1 failed in 0.45s
```

**restore:** revert `_claude_mode_unsupported_detail` to `return "claude-mode-unsupported:%s" % vendor`.

**restore receipt:** restored lines quoted above.

**raw green:**

```
...                                                                      [100%]
3 passed, 197 deselected in 0.75s
```

---

## BP-10 — write `run-dir-claude-mode-mismatch`

- **axis:** write continuation with disagreeing `claude_mode` refuses `run-dir-claude-mode-mismatch` with `attempts: 0`

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, write continuation branch):

```python
            if False and claude_mode is not None and claude_mode != journal_claude_mode:
```

**command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_run_dir_claude_mode_mismatch_refused_write -q
```

**raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_run_dir_claude_mode_mismatch_refused_write ________________

    def test_run_dir_claude_mode_mismatch_refused_write(tmp_path, monkeypatch):
        ...
>       assert res["detail"] == ED.MODE_REFUSAL_RUN_DIR_CLAUDE_MODE_MISMATCH
E       AssertionError: assert 'claude-mode-...le:background' == 'run-dir-claude-mode-mismatch'
E         
E         - run-dir-claude-mode-mismatch
E         + claude-mode-not-dispatchable:background

=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_run_dir_claude_mode_mismatch_refused_write
1 failed in 0.47s
```

**restore:** remove the `False and` prefix from the write continuation mismatch condition.

**restore receipt:** restored lines quoted above.

**raw green:**

```
...                                                                      [100%]
3 passed, 197 deselected in 0.75s
```
