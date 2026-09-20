# C14 layer 2 bite-proof — caller-facing claude mode threading (#1273 WO-3)

Re-run on head `11b2dba7` (branch `build/1273-c14-layer2a-mode-contract`). Three review-fix rounds moved several guarded elements; entries below reflect the live code on this head.

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-1 | `_claude_mode_unknown_detail` | garbage `claude_mode` refuses before open with `claude-mode-unknown:<value>` | `test_claude_mode_unknown_refused_before_open` |
| BP-2 | `_claude_mode_unsupported_detail` | `background` on non-claude seat refuses with `claude-mode-unsupported:<vendor>` | `test_claude_mode_unsupported_codex_background_refused` |
| BP-3 | review continuation claude-mode mismatch gate (`normalize_claude_mode`) | disagreeing `--claude-mode` refuses `run-dir-claude-mode-mismatch` with `attempts: 0` | `test_run_dir_claude_mode_mismatch_refused` |
| BP-4 | `_spawn_attempt` background guard (`engine_result_channel.MODE_BACKGROUND`) | opened `claudeMode: background` refuses spawn with `claude-mode-not-dispatchable:background`, no injected runner | `test_claude_mode_background_review_open_records_caller_provenance` |
| BP-5 | `result_delivery` undeclared-mode raise | unknown `(engine, mode)` pair raises instead of falling back | `test_result_delivery_undeclared_mode_refuses` |
| BP-6 | `build_argv_result` `unknown-claude-mode` refusal | non-string / unknown `claudeMode` refuses with token `unknown-claude-mode` | `test_build_argv_unknown_claude_mode_refuses` |
| BP-7 | `build_argv_result` `claude-mode-unsupported` refusal | `background` on non-claude vendor refuses with token `claude-mode-unsupported` | `test_build_argv_claude_mode_unsupported_on_codex` |
| BP-8 | write `_claude_mode_unknown_detail` | garbage `claude_mode` on write refuses before open with `claude-mode-unknown:<value>` | `test_claude_mode_unknown_refused_before_open_write` |
| BP-9 | write `_claude_mode_unsupported_detail` | `background` on codex write seat refuses with `claude-mode-unsupported:codex` | `test_claude_mode_unsupported_codex_background_refused_write` |
| BP-10 | write continuation claude-mode mismatch gate (`normalize_claude_mode`) | disagreeing `--claude-mode` on write refuses `run-dir-claude-mode-mismatch` with `attempts: 0` | `test_run_dir_claude_mode_mismatch_refused_write` |
| BP-11 | `engine_adapter.claude_mode_supported` | codex + `background` refused before open via `claude_mode_supported` check | `test_claude_mode_unsupported_codex_background_refused` |
| BP-12 | `_stdout_delivery_gate` unresolved-delivery refusal (`_result_delivery_gate_refusal`) | `result_delivery` exception forfeits with `result-delivery-unresolved` instead of falling open | `test_stdout_delivery_gate_unresolved_delivery_forfeits` |
| BP-13 | `test_native_materializer_delivery_census` drift pin | `_NATIVE_MATERIALIZER_DELIVERIES` must equal stdout + transcript members | `test_native_materializer_delivery_census` |

---

## BP-1 — `claude-mode-unknown`

- **axis:** garbage `claude_mode` refuses before open with detail `claude-mode-unknown:<value>`, no spawn
- **stale target:** none — `_claude_mode_unknown_detail` unchanged; entry path now routes through `_claude_mode_entry_refusal` → `_entry_refusal_terminal`

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

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2198/test_claude_mode_unknown_refus0')

    def test_claude_mode_unknown_refused_before_open(tmp_path):
        fake = FakeRunner([])
        run_dir = str(tmp_path / "no-open")
        res = ED.dispatch_review(
            seat=_reviewer_claude_seat(),
            prompt_path=_valid_prompt(tmp_path),
            repo_root=_repo(tmp_path),
            run_engine=fake,
            build_view=_never_build_view,
            run_dir=run_dir,
            claude_mode="bogus",
        )
        assert res["reason"] == "unrunnable"
>       assert res["detail"] == "claude-mode-unknown:'bogus'"
E       assert 'wrong-claude-mode-detail' == "claude-mode-unknown:'bogus'"
E         
E         - claude-mode-unknown:'bogus'
E         + wrong-claude-mode-detail

plugins/superheroes/lib/tests/test_engine_dispatch.py:14361: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_mode_unknown_refused_before_open
1 failed in 1.58s
```

**restore:** revert `_claude_mode_unknown_detail` to `return "claude-mode-unknown:%s" % _coerce_rejected_mode(value)`.

**restore receipt:** `git status --porcelain` empty after restore.

**raw green:**

```
.                                                                        [100%]
1 passed in 1.47s
```

---

## BP-2 — `claude-mode-unsupported`

- **axis:** `background` on codex seat refuses with detail `claude-mode-unsupported:codex`
- **stale target:** none for the detail function; the guard condition now calls `engine_adapter.claude_mode_supported` (BP-11) before reaching `_claude_mode_unsupported_detail`

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

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2200/test_claude_mode_unsupported_c0')

    def test_claude_mode_unsupported_codex_background_refused(tmp_path):
        fake = FakeRunner([])
        res = ED.dispatch_review(
            seat=_codex_seat(),
            prompt_path=_valid_prompt(tmp_path),
            repo_root=_repo(tmp_path),
            run_engine=fake,
            build_view=_never_build_view,
            claude_mode="background",
        )
        assert res["reason"] == "unrunnable"
>       assert res["detail"] == "claude-mode-unsupported:codex"
E       AssertionError: assert 'wrong-unsupported-detail' == 'claude-mode-...pported:codex'
E         
E         - claude-mode-unsupported:codex
E         + wrong-unsupported-detail

plugins/superheroes/lib/tests/test_engine_dispatch.py:14379: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_mode_unsupported_codex_background_refused
1 failed in 1.61s
```

**restore:** revert `_claude_mode_unsupported_detail` to `return "claude-mode-unsupported:%s" % vendor`.

**restore receipt:** `git status --porcelain` empty after restore.

**raw green:**

```
.                                                                        [100%]
1 passed in 1.39s
```

---

## BP-3 — `run-dir-claude-mode-mismatch`

- **axis:** continuation with disagreeing `claude_mode` refuses `run-dir-claude-mode-mismatch` with `attempts: 0`
- **stale target:** yes — comparison now uses `engine_result_channel.normalize_claude_mode()` on both sides (was bare `claude_mode != journal_claude_mode`)

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, review continuation branch):

```python
                if (
                    False and claude_mode is not None
                    and engine_result_channel.normalize_claude_mode(claude_mode)
                    != engine_result_channel.normalize_claude_mode(journal_claude_mode)
                ):
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

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2202/test_run_dir_claude_mode_misma0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x103bfe580>

    def test_run_dir_claude_mode_mismatch_refused(tmp_path, monkeypatch):
        _ensure_claude_config_dir(tmp_path, monkeypatch)
        run_dir = str(tmp_path / "mode-mismatch")
        repo_root = _repo(tmp_path)
        cfg = _ensure_claude_config_dir(tmp_path, monkeypatch)
        seat = _reviewer_claude_seat()
        planted = _plant_claude_review_journal_with_claude_mode(
            tmp_path, run_dir, repo_root, seat, config_dir=cfg, claude_mode="background",
        )
        res = ED.dispatch_review(
            seat=seat,
            prompt_path=_valid_prompt(tmp_path),
            repo_root=repo_root,
            run_engine=_never_call,
            build_view=_stable_build_view(tmp_path),
            run_dir=run_dir,
            order_id="claude-mode-test",
            claude_mode="print",
            max_wait=0,
        )
>       assert res["detail"] == ED.MODE_REFUSAL_RUN_DIR_CLAUDE_MODE_MISMATCH
E       KeyError: 'detail'

plugins/superheroes/lib/tests/test_engine_dispatch.py:14404: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_run_dir_claude_mode_mismatch_refused
1 failed in 1.71s
```

**restore:** remove the `False and` prefix from the continuation mismatch condition.

**restore receipt:** `git status --porcelain` empty after restore.

**raw green:**

```
.                                                                        [100%]
1 passed in 0.90s
```

---

## BP-4 — `_spawn_attempt` background guard

- **axis:** opened `claudeMode: background` refuses spawn with `claude-mode-not-dispatchable:background`, injected runner never called
- **stale target:** yes — guard now compares against `engine_result_channel.MODE_BACKGROUND` (re-export of `engine_adapter.MODE_BACKGROUND`) instead of inline `"background"`

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_spawn_attempt`):

```python
        if claude_mode == engine_result_channel.MODE_PRINT:
            return False, "%s:%s" % (
                MODE_REFUSAL_CLAUDE_MODE_NOT_DISPATCHABLE,
                engine_result_channel.MODE_BACKGROUND,
            )
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

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2206/test_claude_mode_background_re0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x103d72220>

    def test_claude_mode_background_review_open_records_caller_provenance(tmp_path, monkeypatch):
        _ensure_claude_config_dir(tmp_path, monkeypatch)
        repo_root = _repo(tmp_path)
        run_dir = str(tmp_path / "bg-open")
        seat = _reviewer_claude_seat()
        fake = _ClaudeStdoutFakeRunner([_claude_native_verdicts_runner()])
        res = ED.dispatch_review(
            seat=seat,
            prompt_path=_valid_prompt(tmp_path),
            repo_root=repo_root,
            run_engine=fake,
            build_view=_stable_build_view(tmp_path),
            run_dir=run_dir,
            claude_mode="background",
        )
        assert res["ok"] is False
        assert res.get("terminal") is True
>       assert res["detail"] == "claude-mode-not-dispatchable:background"
E       AssertionError: assert 'internal-AssertionError' == 'claude-mode-...le:background'
E         
E         - claude-mode-not-dispatchable:background
E         + internal-AssertionError

plugins/superheroes/lib/tests/test_engine_dispatch.py:14319: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_mode_background_review_open_records_caller_provenance
1 failed in 1.00s
```

**restore:** revert comparison to `engine_result_channel.MODE_BACKGROUND`.

**restore receipt:** `git status --porcelain` empty after restore.

**raw green:**

```
.                                                                        [100%]
1 passed in 1.07s
```

---

## BP-5 — `result_delivery` undeclared-mode raise

- **axis:** unknown claude mode on a registered engine raises `ValueError` instead of returning a delivery entry
- **stale target:** none

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

plugins/superheroes/lib/tests/test_engine_result_channel.py:482: Failed
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_result_channel.py::test_result_delivery_undeclared_mode_refuses
1 failed in 0.25s
```

**restore:** revert body to `raise ValueError("unknown claude mode %r; declared modes: %s" % (mode, ", ".join(CLAUDE_MODES)))`.

**restore receipt:** `git status --porcelain` empty after restore.

**raw green:**

```
.                                                                        [100%]
1 passed in 0.21s
```

---

## BP-6 — adapter `unknown-claude-mode`

- **axis:** garbage `claudeMode` in `build_argv_result` refuses with reason token `unknown-claude-mode`
- **stale target:** none

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

plugins/superheroes/lib/tests/test_engine_adapter.py:706: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
plugins/superheroes/lib/engine_adapter.py:475: in build_argv_result
    return _refuse(
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

reason = 'wrong-unknown-claude-mode'

    def _refuse(reason, *, detail=None):
>       assert reason in BUILD_ARGV_REFUSAL_TOKENS
E       AssertionError

plugins/superheroes/lib/engine_adapter.py:250: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_build_argv_unknown_claude_mode_refuses
1 failed in 0.40s
```

**restore:** revert both refusal sites to `"unknown-claude-mode"`.

**restore receipt:** `git status --porcelain` empty after restore.

**raw green:**

```
.                                                                        [100%]
1 passed in 0.31s
```

---

## BP-7 — adapter `claude-mode-unsupported`

- **axis:** `background` on codex in `build_argv_result` refuses with reason token `claude-mode-unsupported`
- **stale target:** none for the refusal token; guard now calls `claude_mode_supported` (shared with BP-11)

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

plugins/superheroes/lib/tests/test_engine_adapter.py:714: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
plugins/superheroes/lib/engine_adapter.py:487: in build_argv_result
    return _refuse(
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

reason = 'wrong-claude-mode-unsupported'

    def _refuse(reason, *, detail=None):
>       assert reason in BUILD_ARGV_REFUSAL_TOKENS
E       AssertionError

plugins/superheroes/lib/engine_adapter.py:250: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_build_argv_claude_mode_unsupported_on_codex
1 failed in 0.39s
```

**restore:** revert refusal site to `"claude-mode-unsupported"`.

**restore receipt:** `git status --porcelain` empty after restore.

**raw green:**

```
.                                                                        [100%]
1 passed in 0.37s
```

---

## BP-8 — write `claude-mode-unknown`

- **axis:** garbage `claude_mode` on `dispatch_write` refuses before open with detail `claude-mode-unknown:<value>`, no spawn
- **stale target:** none — same detail function; write entry path routes through `_claude_mode_entry_refusal`

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

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2214/test_claude_mode_unknown_refus0')

    def test_claude_mode_unknown_refused_before_open_write(tmp_path):
        fake = FakeRunner([])
        res = _dispatch_write(
            tmp_path, fake,
            claude_mode="bogus",
        )
        assert res["reason"] == "unrunnable"
>       assert res["detail"] == "claude-mode-unknown:'bogus'"
E       assert 'wrong-claude-mode-detail' == "claude-mode-unknown:'bogus'"
E         
E         - claude-mode-unknown:'bogus'
E         + wrong-claude-mode-detail

plugins/superheroes/lib/tests/test_engine_dispatch_write.py:3696: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_claude_mode_unknown_refused_before_open_write
1 failed in 0.44s
```

**restore:** revert `_claude_mode_unknown_detail` to `return "claude-mode-unknown:%s" % _coerce_rejected_mode(value)`.

**restore receipt:** `git status --porcelain` empty after restore.

**raw green:**

```
.                                                                        [100%]
1 passed in 0.38s
```

---

## BP-9 — write `claude-mode-unsupported`

- **axis:** `background` on codex write seat refuses with detail `claude-mode-unsupported:codex`
- **stale target:** none for the detail function; guard now calls `engine_adapter.claude_mode_supported`

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

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2216/test_claude_mode_unsupported_c0')

    def test_claude_mode_unsupported_codex_background_refused_write(tmp_path):
        fake = FakeRunner([])
        res = _dispatch_write(
            tmp_path, fake,
            seat=_codex_seat(),
            claude_mode="background",
        )
        assert res["reason"] == "unrunnable"
>       assert res["detail"] == "claude-mode-unsupported:codex"
E       AssertionError: assert 'wrong-unsupported-detail' == 'claude-mode-...pported:codex'
E         
E         - claude-mode-unsupported:codex
E         + wrong-unsupported-detail

plugins/superheroes/lib/tests/test_engine_dispatch_write.py:3709: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_claude_mode_unsupported_codex_background_refused_write
1 failed in 0.43s
```

**restore:** revert `_claude_mode_unsupported_detail` to `return "claude-mode-unsupported:%s" % vendor`.

**restore receipt:** `git status --porcelain` empty after restore.

**raw green:**

```
.                                                                        [100%]
1 passed in 0.40s
```

---

## BP-10 — write `run-dir-claude-mode-mismatch`

- **axis:** write continuation with disagreeing `claude_mode` refuses `run-dir-claude-mode-mismatch` with `attempts: 0`
- **stale target:** yes — comparison now uses `engine_result_channel.normalize_claude_mode()` on both sides

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, write continuation branch):

```python
            if (
                False and claude_mode is not None
                and engine_result_channel.normalize_claude_mode(claude_mode)
                != engine_result_channel.normalize_claude_mode(journal_claude_mode)
            ):
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

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2218/test_run_dir_claude_mode_misma0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x105b80550>

    def test_run_dir_claude_mode_mismatch_refused_write(tmp_path, monkeypatch):
        _ensure_claude_config_dir(tmp_path, monkeypatch)
        wt, _main = _linked_worktree(tmp_path)
        run_dir = str(tmp_path / "mode-mismatch")
        cfg = _ensure_claude_config_dir(tmp_path, monkeypatch)
        seat = _implementer_claude_seat()
        planted = _plant_claude_write_journal_with_claude_mode(
            tmp_path, run_dir, wt, seat, config_dir=cfg, claude_mode="background",
        )
        fake = FakeRunner([])
        res = _dispatch_write(
            tmp_path, fake,
            cwd=wt,
            run_dir=run_dir,
            seat=seat,
            order_id="claude-mode-test",
            claude_mode="print",
        )
>       assert res["detail"] == ED.MODE_REFUSAL_RUN_DIR_CLAUDE_MODE_MISMATCH
E       AssertionError: assert 'claude-mode-...le:background' == 'run-dir-claude-mode-mismatch'
E         
E         - run-dir-claude-mode-mismatch
E         + claude-mode-not-dispatchable:background

plugins/superheroes/lib/tests/test_engine_dispatch_write.py:3796: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_run_dir_claude_mode_mismatch_refused_write
1 failed in 0.54s
```

**restore:** remove the `False and` prefix from the write continuation mismatch condition.

**restore receipt:** `git status --porcelain` empty after restore.

**raw green:**

```
.                                                                        [100%]
1 passed in 0.45s
```

---

## BP-11 — `engine_adapter.claude_mode_supported`

- **axis:** codex + `background` is refused before open because `claude_mode_supported` returns False for that pair

**neutralization** (`plugins/superheroes/lib/engine_adapter.py`):

```python
def claude_mode_supported(vendor, mode):
    """True when vendor accepts this claude dispatch mode (print is universal)."""
    return True
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

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2220/test_claude_mode_unsupported_c0')

    def test_claude_mode_unsupported_codex_background_refused(tmp_path):
        fake = FakeRunner([])
        res = ED.dispatch_review(
            seat=_codex_seat(),
            prompt_path=_valid_prompt(tmp_path),
            repo_root=_repo(tmp_path),
            run_engine=fake,
            build_view=_never_build_view,
            claude_mode="background",
        )
        assert res["reason"] == "unrunnable"
>       assert res["detail"] == "claude-mode-unsupported:codex"
E       AssertionError: assert 'internal-AssertionError' == 'claude-mode-...pported:codex'
E         
E         - claude-mode-unsupported:codex
E         + internal-AssertionError

plugins/superheroes/lib/tests/test_engine_dispatch.py:14379: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_mode_unsupported_codex_background_refused
1 failed in 1.02s
```

**restore:** revert `claude_mode_supported` to the vendor/mode table lookup.

**restore receipt:** `git status --porcelain` empty after restore.

**raw green:**

```
.                                                                        [100%]
1 passed in 0.95s
```

---

## BP-12 — `_stdout_delivery_gate` unresolved-delivery refusal

- **axis:** when `engine_result_channel.result_delivery` raises `UnknownEngineError` or `ValueError`, `_stdout_delivery_gate` must forfeit with detail `result-delivery-unresolved` rather than falling open

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_result_delivery_gate_refusal`):

```python
def _result_delivery_gate_refusal():
    return None
```

**command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_delivery_gate_unresolved_delivery_forfeits -q
```

**raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_stdout_delivery_gate_unresolved_delivery_forfeits ____________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2237/test_stdout_delivery_gate_unre0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x103f3aa60>

    def test_stdout_delivery_gate_unresolved_delivery_forfeits(tmp_path, monkeypatch):
        cfg = _ensure_claude_config_dir(tmp_path, monkeypatch)
        run_dir = str(tmp_path / "corrupt-delivery-mode")
        repo_root = _repo(tmp_path)
        opened = _plant_claude_review_journal(
            tmp_path, run_dir, repo_root, _reviewer_claude_seat(), config_dir=cfg,
        )
        opened["claudeMode"] = "bogus"
        gate = ED._stdout_delivery_gate(run_dir, 1, opened)
>       assert gate is not None
E       assert None is not None

plugins/superheroes/lib/tests/test_engine_dispatch.py:14495: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_delivery_gate_unresolved_delivery_forfeits
1 failed in 0.95s
```

**restore:** revert `_result_delivery_gate_refusal` to return the forfeit dict with `detail: "result-delivery-unresolved"`.

**restore receipt:** `git status --porcelain` lists only `plugins/superheroes/lib/tests/test_engine_dispatch.py` and `plugins/superheroes/lib/tests/bite_proofs/c14_l2_claude_mode.md` after restore.

**raw green:**

```
.                                                                        [100%]
1 passed in 0.84s
```

---

## BP-13 — `test_native_materializer_delivery_census`

- **axis:** `_NATIVE_MATERIALIZER_DELIVERIES` must stay in sync with `engine_result_channel.RESULT_DELIVERY_MEMBERS` (stdout + transcript)

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`):

```python
_NATIVE_MATERIALIZER_DELIVERIES = frozenset({
    engine_result_channel.RESULT_DELIVERY_STDOUT,
})
```

(drop `RESULT_DELIVERY_TRANSCRIPT`)

**command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_native_materializer_delivery_census -q
```

**raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_native_materializer_delivery_census ___________________

    def test_native_materializer_delivery_census():
        assert ED._NATIVE_MATERIALIZER_DELIVERIES <= ERC.RESULT_DELIVERY_MEMBERS
>       assert ED._NATIVE_MATERIALIZER_DELIVERIES == frozenset({
            ERC.RESULT_DELIVERY_STDOUT,
            ERC.RESULT_DELIVERY_TRANSCRIPT,
        })
E       AssertionError: assert frozenset({'stdout'}) == frozenset({'s...'transcript'})
E         
E         Extra items in the right set:
E         'transcript'
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_engine_dispatch.py:14488: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_native_materializer_delivery_census
1 failed in 0.93s
```

**restore:** restore `_NATIVE_MATERIALIZER_DELIVERIES` to include both `RESULT_DELIVERY_STDOUT` and `RESULT_DELIVERY_TRANSCRIPT`.

**restore receipt:** `git status --porcelain` empty after restore.

**raw green:**

```
.                                                                        [100%]
1 passed in 0.81s
```
