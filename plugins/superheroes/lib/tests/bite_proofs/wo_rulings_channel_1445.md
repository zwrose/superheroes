# WO #1445 — rulings channel bite-proofs (WO-1d)

Records per `rubric/bite-proof.md` § The record. Code surface: `plugins/superheroes/lib/round_driver.py`. Detectors: `plugins/superheroes/lib/tests/test_rulings_channel_1445.py`. Restore by inverse edit only (no `git checkout` / `git restore`).

---

## BP-1

- **Guarded element:** `round_driver.py` — `_gate_guidance_entries`, loop building `ruling_channel` (≈3453–3467).
- **Axis:** Ruling-channel guidance entries are prepended into gate-guidance / hashed-order material so binding certification does not rely on a prompt-file appendix alone.
- **Neutralization:** First statement of the `for key in sorted(batch_keys):` body set to `continue`, so `ruling_channel` stays empty.

```python
    for key in sorted(batch_keys):
        continue
        live = _live_ruling_by_key(state).get(key)
```

- **Detector:** `test_binding_ruling_rides_hashed_order_and_certifies`
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_binding_ruling_rides_hashed_order_and_certifies _____________

    def test_binding_ruling_rides_hashed_order_and_certifies(tmp_path):
        ...
        rec_out = RD.cmd_record_result(session_dir, seat, occurrence=occurrence,
                                       evidence_run_dir=run_dir)
>       assert rec_out.get("ok"), rec_out
E       AssertionError: {'ok': False, 'orderPromptSha256': 'cf5ec7722451be567fc8d734413465fa9efc693ca35017e02e5b43bf41f9dca5', 'orderSha256': 'e74c47fe02fb6ef6b8139763a48123b43795af8c74f930a5710274323155de5b', 'reason': 'evidence-order-mismatch', ...}
E       assert False

plugins/superheroes/lib/tests/test_rulings_channel_1445.py:449: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_rulings_channel_1445.py::test_binding_ruling_rides_hashed_order_and_certifies
1 failed in 19.32s
```

- **Restore:** Removed the inserted `continue` line.
- **Restore receipt (quoted lines):**

```python
    for key in sorted(batch_keys):
        live = _live_ruling_by_key(state).get(key)
        if not isinstance(live, dict) or live.get("ruling") != "guidance":
            continue
```

- **Raw green:**

```
.                                                                        [100%]
1 passed in 22.53s
```

---

## BP-2

- **Guarded element:** `round_driver.py` — `_filter_excluded_discharged_fixes`, out-of-scope key skip (≈3842–3844).
- **Axis:** Live out-of-scope ruling keys are excluded from queued fix-batch rows.
- **Neutralization:** Deleted the `if key and key in oos_keys: continue` guard; rows append regardless of `oos_keys`.

```python
        key = _fix_batch_row_key(row)
        filtered.append(row)
```

- **Detector:** `test_edge8_empty_batch_advances` (binding test stayed green under the same neutralization; edge-8 asserts batch emptying / `pendingCleared`).
- **Failing assertion:** `assert out.get("pendingCleared") is True`
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________________ test_edge8_empty_batch_advances ________________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-7721/test_edge8_empty_batch_advance0')

    def test_edge8_empty_batch_advances(tmp_path):
        session_dir, _, _, row_a, row_b = _pending_fixer_two_findings(tmp_path)
        id_a = row_a.get("id") or RD._fix_batch_row_key(row_a)
        id_b = row_b.get("id") or RD._fix_batch_row_key(row_b)
        out = _rule(session_dir, _write_ruling_file(tmp_path / "r.json", [
            {"id": id_a, "ruling": "out-of-scope", "reason": "a", "followUp": _follow_up()},
            {"id": id_b, "ruling": "out-of-scope", "reason": "b", "followUp": _follow_up()}]))
        assert out.get("ok"), out
>       assert out.get("pendingCleared") is True
E       AssertionError: assert None is True
E        +  where None = <built-in method get of dict object at 0x106419880>('pendingCleared')
E        +    where <built-in method get of dict object at 0x106419880> = {'action': 'dispatch-fixer', 'attempt': 0, 'expectedStateHash': '11edd2dbd6acd277c038a1b36a025eb17f1b310dc8d07fbeec6c887c5a17e6fc', 'ok': True, ...}.get

plugins/superheroes/lib/tests/test_rulings_channel_1445.py:324: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_rulings_channel_1445.py::test_edge8_empty_batch_advances
1 failed in 16.85s
```

- **Restore:** Reinserted oos-key skip before `filtered.append(row)`.
- **Restore receipt (quoted lines):**

```python
        key = _fix_batch_row_key(row)
        if key and key in oos_keys:
            continue
        filtered.append(row)
```

- **Raw green:**

```
.                                                                        [100%]
1 passed in 15.63s
```

---

## BP-3

- **Guarded element:** `round_driver.py` — `_stage_findings`, live out-of-scope re-apply via `_record_disposition` (≈1548–1554).
- **Axis:** Restaging findings re-applies live out-of-scope dispositions from the rulings log.
- **Neutralization:** Removed the `live_oos` / `_record_disposition(...)` block inside the compile loop.

- **Detector:** `test_edge3_restage_reapplies_out_of_scope`
- **Failing assertion:** `assert entry.get("disposition") == "out-of-scope"`
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_edge3_restage_reapplies_out_of_scope ___________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-7726/test_edge3_restage_reapplies_o0')

    def test_edge3_restage_reapplies_out_of_scope(tmp_path):
        ...
        entry = next(e for e in ledger if RD._finding_identity_key(e) == key_b)
>       assert entry.get("disposition") == "out-of-scope"
E       AssertionError: assert None == 'out-of-scope'
E        +  where None = <built-in method get of dict object at 0x1056c20c0>('disposition')
E        +    where <built-in method get of dict object at 0x1056c20c0> = {'classification': 'mechanical', 'detail': 'bounds B at src/f00.py:3', ...}.get

plugins/superheroes/lib/tests/test_rulings_channel_1445.py:249: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_rulings_channel_1445.py::test_edge3_restage_reapplies_out_of_scope
1 failed in 13.09s
```

- **Restore:** Reinserted `live_oos` block before `seeded = True`.
- **Restore receipt (quoted lines):**

```python
        live_oos = _live_out_of_scope_ruling_for_key(state, key)
        if live_oos is not None:
            _record_disposition(
                state, key, "out-of-scope", round_no,
                outOfScopeReason=live_oos.get("reason"),
                followUp=live_oos.get("followUp"),
                rulingSeq=live_oos.get("seq"))
        seeded = True
```

- **Raw green:**

```
.                                                                        [100%]
1 passed in 12.64s
```

---

## BP-4

- **Guarded element:** `round_driver.py` — `FIX_BATCH_SHA256` placeholder in fixer order render context (≈9549–9552).
- **Axis:** Order hash material uses the real fix-batch file SHA, not a constant placeholder.
- **Neutralization:** `batch_sha = "0" * 64` instead of `_fix_batch_file_sha256(session_dir, rnd, state)`.

```python
        batch_sha = "0" * 64
```

- **Detector:** `test_fixer_order_pins_fix_batch_sha256`
- **Failing assertion:** `assert f"- Fix batch sha256: {batch_sha}" in order_text`
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________________ test_fixer_order_pins_fix_batch_sha256 ____________________

    def test_fixer_order_pins_fix_batch_sha256(tmp_path):
        ...
        order_text = _fixer_order_text(session_dir)
>       assert f"- Fix batch sha256: {batch_sha}" in order_text
E       AssertionError: assert '- Fix batch sha256: 3dacacd1123f7a9f9c2b917020c73c700d6626c71f5c536cda43b20dab948f06' in 'You are the fixer for one round of an auto-fix code-review loop.\n\n## Input\n- Findings to fix: ...'

plugins/superheroes/lib/tests/test_rulings_channel_1445.py:392: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_rulings_channel_1445.py::test_fixer_order_pins_fix_batch_sha256
1 failed in 13.84s
```

- **Restore:** `batch_sha = _fix_batch_file_sha256(session_dir, rnd, state)`
- **Restore receipt (quoted line):**

```python
        batch_sha = _fix_batch_file_sha256(session_dir, rnd, state)
```

- **Raw green:**

```
.......................                                                  [100%]
23 passed in 45.72s
```

(`plugins/superheroes/lib/tests/test_rulings_channel_1445.py`, `-n auto`, post-restore.)

---

## BP-5

- **Guarded element:** `round_driver.py` — `_cmd_rule_locked`, `ruling-critical-out-of-scope` check (≈7540–7546).
- **Axis:** Critical-severity findings cannot be ruled out-of-scope.
- **Neutralization:** Deleted the `entry["ruling"] == "out-of-scope"` / `circuit_breaker.is_critical` refusal block in the first `for entry in parsed` loop.

- **Detector:** `test_rule_refusal_tokens[ruling-critical-out-of-scope-critical_oos]`
- **Failing assertion:** `assert out.get("ok") is False, out`
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_rule_refusal_tokens[ruling-critical-out-of-scope-critical_oos] ______
...
>       assert out.get("ok") is False, out
E       AssertionError: {'action': 'dispatch-fixer', 'attempt': 1, ..., 'ok': True, ...}
E       assert True is False

plugins/superheroes/lib/tests/test_rulings_channel_1445.py:219: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_rulings_channel_1445.py::test_rule_refusal_tokens[ruling-critical-out-of-scope-critical_oos]
1 failed in 20.19s
```

- **Restore:** Reinserted critical out-of-scope refusal inside the target-resolution loop.
- **Restore receipt (quoted lines):**

```python
        if entry["ruling"] == "out-of-scope":
            sev = _severity_for_finding_key(
                state, key,
                candidate.get("severity") if isinstance(candidate, dict) else None)
            if circuit_breaker.is_critical(sev):
                return _refuse_cmd(session_dir, RULE_CMD, RULING_CRITICAL_OUT_OF_SCOPE,
                                   id=entry["id"])
```

- **Raw green:**

```
.                                                                        [100%]
1 passed in 7.71s
```

---

## BP-6

- **Guarded element:** `round_driver.py` — `_cmd_rule_locked`, `ruling-attempt-recorded` check (≈7547–7563).
- **Axis:** Rule refuses when dispatch attempt already has recorded results.
- **Neutralization:** Deleted the `dispatch-` phase / `_journal_has_orders_emitted` / `RULING_ATTEMPT_RECORDED` refusal block.

- **Detector:** `test_rule_refusal_tokens[ruling-attempt-recorded-attempt_recorded]`
- **Failing assertion:** `assert out.get("ok") is False, out`
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_rule_refusal_tokens[ruling-attempt-recorded-attempt_recorded] ______
...
>       assert out.get("ok") is False, out
E       AssertionError: {'action': 'dispatch-fixer', 'attempt': 1, ..., 'ok': True, ...}
E       assert True is False

plugins/superheroes/lib/tests/test_rulings_channel_1445.py:219: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_rulings_channel_1445.py::test_rule_refusal_tokens[ruling-attempt-recorded-attempt_recorded]
1 failed in 9.77s
```

- **Restore:** Reinserted full `ruling-attempt-recorded` guard block before `cfg = state.get("config")`.
- **Restore receipt (quoted lines):**

```python
    if (isinstance(pending, dict) and isinstance(pending.get("phase"), str)
            and pending["phase"].startswith("dispatch-")
            and _journal_has_orders_emitted(session_dir, pending.get("round"),
                                            pending.get("phase"), pending.get("attempt"))):
        journal = read_journal(session_dir)
        old_roster, roster_refusal = _roster_of(
            session_dir, state, RULE_CMD, pending["phase"], pending.get("round"),
            pending.get("attempt"))
        if roster_refusal is not None:
            return roster_refusal
        result_names = _re_emit_blocking_result_names(
            session_dir, journal, pending.get("round"), pending.get("phase"),
            pending.get("attempt"), old_roster)
        if result_names:
            return _refuse_cmd(session_dir, RULE_CMD, RULING_ATTEMPT_RECORDED,
                               phase=pending.get("phase"), rnd=pending.get("round"),
                               attempt=pending.get("attempt"), names=result_names)
```

- **Raw green:**

```
.                                                                        [100%]
1 passed in 15.82s
```

---

## Post-restore workspace

```
git status --porcelain
```

(empty — only this record file differs from committed tree after write)
