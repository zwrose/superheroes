# C14 L2b r2 WO-R1 bite-proof — transcript gate + claude-mode census

**Provenance:** cursor CLI / composer-2.5 (implementer WO-R1)

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| E1 | `engine_dispatch.py:_stdout_delivery_gate` transcript branch, missing `transcriptResult` | missing transcript result must forfeit `native-result-missing` | `test_stdout_delivery_gate_transcript_branch` |
| E2 | `engine_dispatch.py:_stdout_delivery_gate` transcript branch, `transcriptResult == "occupied"` | occupied transcript path must forfeit `native-result-path-occupied` | `test_stdout_delivery_gate_transcript_branch` |
| E3 | `engine_dispatch.py:_stdout_delivery_gate` transcript branch, `transcriptResult == "materialized"` | materialized transcript result must admit (`None`) | `test_stdout_delivery_gate_transcript_branch` |
| E4 | `engine_adapter.py:CLAUDE_MODES` literal census | declared mode literals pin when write-path mismatch gate becomes reachable | `test_claude_mode_literal_census_pins_write_path_mismatch_gate_reachability` |

## E1 — transcript branch missing result

- **axis:** missing `transcriptResult` on the transcript delivery branch must forfeit with `native-result-missing`

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_stdout_delivery_gate` transcript branch):

```python
    if delivery == engine_result_channel.RESULT_DELIVERY_TRANSCRIPT:
        materialized = ended.get("transcriptResult")
        if materialized is None:
            return None
    else:
        materialized = ended.get("stdoutResult")
```

**command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-wor1 -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_delivery_gate_transcript_branch -q
```

**raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_stdout_delivery_gate_transcript_branch __________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2540/test_stdout_delivery_gate_tran0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x10623cf40>

    def test_stdout_delivery_gate_transcript_branch(tmp_path, monkeypatch):
        # axis: transcript delivery branch discriminates missing, occupied, and materialized transcriptResult
        cfg = _ensure_claude_config_dir(tmp_path, monkeypatch)
        repo_root = _repo(tmp_path)

        def _gate_for_transcript_result(*, transcript_result=None):
            run_dir = str(tmp_path / ("transcript-gate-%s" % (transcript_result or "missing")))
            opened = _plant_claude_background_journal(
                tmp_path, run_dir, repo_root, _reviewer_claude_seat(), config_dir=cfg,
            )
            assert ERC.result_delivery(opened["engine"], opened["claudeMode"]) == (
                ERC.RESULT_DELIVERY_TRANSCRIPT
            )
            ED._journal_append(run_dir, {
                "kind": "attempt-started", "attempt": 1, "childPid": 1, "at": time.time(),
            })
            ended = {"kind": "attempt-ended", "attempt": 1, "exit": 0, "at": time.time()}
            if transcript_result is not None:
                ended["transcriptResult"] = transcript_result
            ED._journal_append(run_dir, ended)
            return ED._stdout_delivery_gate(run_dir, 1, opened)

        gate_missing = _gate_for_transcript_result()
>       assert gate_missing == {
            "forfeit": True,
            "reason": ED.dispatch_outcome.REASON_FORFEITED,
            "detail": "native-result-missing",
        }
E       AssertionError: assert None == {'detail': 'native-result-missing', 'forfeit': True, 'reason': 'forfeited'}

plugins/superheroes/lib/tests/test_engine_dispatch.py:14528: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_delivery_gate_transcript_branch
1 failed in 1.63s
```

**restore:** removed the `if materialized is None: return None` block from the transcript branch.

**restored lines quoted back:**

```python
    if delivery == engine_result_channel.RESULT_DELIVERY_TRANSCRIPT:
        materialized = ended.get("transcriptResult")
    else:
        materialized = ended.get("stdoutResult")
```

**restore receipt:**

```
 M plugins/superheroes/lib/engine_dispatch.py
 M plugins/superheroes/lib/tests/test_engine_dispatch.py
 M plugins/superheroes/lib/tests/test_engine_dispatch_write.py
```

**raw green:**

```
.                                                                        [100%]
1 passed in 1.67s
```

---

## E2 — transcript branch occupied path

- **axis:** `transcriptResult == "occupied"` on the transcript delivery branch must forfeit with `native-result-path-occupied`

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_stdout_delivery_gate`):

```python
    if materialized == "occupied":
        return None
```

**command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-wor1 -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_delivery_gate_transcript_branch -q
```

**raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_stdout_delivery_gate_transcript_branch __________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2541/test_stdout_delivery_gate_tran0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x10673f970>

    def test_stdout_delivery_gate_transcript_branch(tmp_path, monkeypatch):
        # axis: transcript delivery branch discriminates missing, occupied, and materialized transcriptResult
        cfg = _ensure_claude_config_dir(tmp_path, monkeypatch)
        repo_root = _repo(tmp_path)

        def _gate_for_transcript_result(*, transcript_result=None):
            run_dir = str(tmp_path / ("transcript-gate-%s" % (transcript_result or "missing")))
            opened = _plant_claude_background_journal(
                tmp_path, run_dir, repo_root, _reviewer_claude_seat(), config_dir=cfg,
            )
            assert ERC.result_delivery(opened["engine"], opened["claudeMode"]) == (
                ERC.RESULT_DELIVERY_TRANSCRIPT
            )
            ED._journal_append(run_dir, {
                "kind": "attempt-started", "attempt": 1, "childPid": 1, "at": time.time(),
            })
            ended = {"kind": "attempt-ended", "attempt": 1, "exit": 0, "at": time.time()}
            if transcript_result is not None:
                ended["transcriptResult"] = transcript_result
            ED._journal_append(run_dir, ended)
            return ED._stdout_delivery_gate(run_dir, 1, opened)

        gate_missing = _gate_for_transcript_result()
        assert gate_missing == {
            "forfeit": True,
            "reason": ED.dispatch_outcome.REASON_FORFEITED,
            "detail": "native-result-missing",
        }

        gate_occupied = _gate_for_transcript_result(transcript_result="occupied")
>       assert gate_occupied == {
            "forfeit": True,
            "reason": ED.dispatch_outcome.REASON_FORFEITED,
            "detail": "native-result-path-occupied",
        }
E       AssertionError: assert None == {'detail': 'native-result-path-occupied', 'forfeit': True, 'reason': 'forfeited'}

plugins/superheroes/lib/tests/test_engine_dispatch.py:14535: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_delivery_gate_transcript_branch
1 failed in 2.01s
```

**restore:** reinstated the occupied-branch forfeit dict.

**restored lines quoted back:**

```python
    if materialized == "occupied":
        return {
            "forfeit": True,
            "reason": dispatch_outcome.REASON_FORFEITED,
            "detail": "native-result-path-occupied",
        }
```

**restore receipt:**

```
 M plugins/superheroes/lib/engine_dispatch.py
 M plugins/superheroes/lib/tests/test_engine_dispatch.py
 M plugins/superheroes/lib/tests/test_engine_dispatch_write.py
```

**raw green:**

```
.                                                                        [100%]
1 passed in 1.67s
```

---

## E3 — transcript branch materialized admission

- **axis:** `transcriptResult == "materialized"` on the transcript delivery branch must admit (`None`)

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_stdout_delivery_gate`):

```python
    if materialized == "materialized":
        return {
            "forfeit": True,
            "reason": dispatch_outcome.REASON_FORFEITED,
            "detail": "native-result-missing",
        }
```

**command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-wor1 -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_delivery_gate_transcript_branch -q
```

**raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_stdout_delivery_gate_transcript_branch __________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-2542/test_stdout_delivery_gate_tran0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x106a2ba30>

    def test_stdout_delivery_gate_transcript_branch(tmp_path, monkeypatch):
        # axis: transcript delivery branch discriminates missing, occupied, and materialized transcriptResult
        cfg = _ensure_claude_config_dir(tmp_path, monkeypatch)
        repo_root = _repo(tmp_path)

        def _gate_for_transcript_result(*, transcript_result=None):
            run_dir = str(tmp_path / ("transcript-gate-%s" % (transcript_result or "missing")))
            opened = _plant_claude_background_journal(
                tmp_path, run_dir, repo_root, _reviewer_claude_seat(), config_dir=cfg,
            )
            assert ERC.result_delivery(opened["engine"], opened["claudeMode"]) == (
                ERC.RESULT_DELIVERY_TRANSCRIPT
            )
            ED._journal_append(run_dir, {
                "kind": "attempt-started", "attempt": 1, "childPid": 1, "at": time.time(),
            })
            ended = {"kind": "attempt-ended", "attempt": 1, "exit": 0, "at": time.time()}
            if transcript_result is not None:
                ended["transcriptResult"] = transcript_result
            ED._journal_append(run_dir, ended)
            return ED._stdout_delivery_gate(run_dir, 1, opened)

        gate_missing = _gate_for_transcript_result()
        assert gate_missing == {
            "forfeit": True,
            "reason": ED.dispatch_outcome.REASON_FORFEITED,
            "detail": "native-result-missing",
        }

        gate_occupied = _gate_for_transcript_result(transcript_result="occupied")
        assert gate_occupied == {
            "forfeit": True,
            "reason": ED.dispatch_outcome.REASON_FORFEITED,
            "detail": "native-result-path-occupied",
        }

>       assert _gate_for_transcript_result(transcript_result="materialized") is None
E       AssertionError: assert {'detail': 'native-result-missing', 'forfeit': True, 'reason': 'forfeited'} is None
E        +  where {'detail': 'native-result-missing', 'forfeit': True, 'reason': 'forfeited'} = <function test_stdout_delivery_gate_transcript_branch.<locals>._gate_for_transcript_result at 0x102281d30>(transcript_result='materialized')

plugins/superheroes/lib/tests/test_engine_dispatch.py:14541: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_stdout_delivery_gate_transcript_branch
1 failed in 1.73s
```

**restore:** reinstated `return None` on the materialized branch.

**restored lines quoted back:**

```python
    if materialized == "materialized":
        return None
```

**restore receipt:**

```
 M plugins/superheroes/lib/engine_dispatch.py
 M plugins/superheroes/lib/tests/test_engine_dispatch.py
 M plugins/superheroes/lib/tests/test_engine_dispatch_write.py
```

**raw green:**

```
.                                                                        [100%]
1 passed in 1.67s
```

---

## E4 — claude-mode literal census

- **axis:** declared claude mode literals `"print"` and `"background"` pin when the write-path `run-dir-claude-mode-mismatch` gate becomes reachable

**neutralization** (`plugins/superheroes/lib/engine_adapter.py`):

```python
CLAUDE_MODES = (MODE_PRINT, MODE_BACKGROUND, "c14-biteproof-third-mode")
```

**command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-wor1 -m pytest plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_claude_mode_literal_census_pins_write_path_mismatch_gate_reachability -q
```

**raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_claude_mode_literal_census_pins_write_path_mismatch_gate_reachability __

    def test_claude_mode_literal_census_pins_write_path_mismatch_gate_reachability():
        # axis: declared claude mode literals pin when write-path run-dir-claude-mode-mismatch becomes reachable
>       assert ERC.CLAUDE_MODES == ("print", "background"), (
            "a new claude mode makes the write-path run-dir-claude-mode-mismatch gate reachable; "
            "the gate now needs a real test"
        )
E       AssertionError: a new claude mode makes the write-path run-dir-claude-mode-mismatch gate reachable; the gate now needs a real test
E       assert ('print', 'ba...f-third-mode') == ('print', 'background')
E         
E         Left contains one more item: 'c14-biteproof-third-mode'
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_engine_dispatch_write.py:3818: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_claude_mode_literal_census_pins_write_path_mismatch_gate_reachability
1 failed in 0.57s
```

**restore:** removed the `"c14-biteproof-third-mode"` literal from `CLAUDE_MODES`.

**restored lines quoted back:**

```python
CLAUDE_MODES = (MODE_PRINT, MODE_BACKGROUND)
```

**restore receipt:**

```
 M plugins/superheroes/lib/engine_dispatch.py
 M plugins/superheroes/lib/tests/test_engine_dispatch.py
 M plugins/superheroes/lib/tests/test_engine_dispatch_write.py
```

**raw green:**

```
.                                                                        [100%]
1 passed in 1.67s
```
