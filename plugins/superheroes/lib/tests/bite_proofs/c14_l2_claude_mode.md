# C14 layer 2 bite-proof — caller-facing claude mode threading (#1273 WO-B1)

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-1 | `_claude_mode_unknown_detail` | garbage `claude_mode` refuses before open with `claude-mode-unknown:<value>` | `test_claude_mode_unknown_refused_before_open` |
| BP-2 | `_claude_mode_unsupported_detail` | `background` on non-claude seat refuses with `claude-mode-unsupported:<vendor>` | `test_claude_mode_unsupported_codex_background_refused` |
| BP-3 | review continuation claude-mode mismatch gate | disagreeing `--claude-mode` refuses `run-dir-claude-mode-mismatch` with `attempts: 0` | `test_run_dir_claude_mode_mismatch_refused` |

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
