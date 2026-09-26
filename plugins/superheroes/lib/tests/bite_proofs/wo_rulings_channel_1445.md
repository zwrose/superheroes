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

- **Guarded element:** `round_driver.py` — `_filter_excluded_discharged_fixes`, out-of-scope key skip (≈3874–3877).
- **Axis:** Live out-of-scope ruling keys are excluded from queued fix-batch rows.
- **Neutralization:** Deleted the `if key and key in oos_keys and not _live_out_of_scope_blocks_row(row): continue` guard; rows append regardless of `oos_keys`.

```python
        key = _fix_batch_row_key(row)
        filtered.append(row)
```

- **Detector:** `test_out_of_scope_queue_row_absent_after_fixer_landing`
- **Failing assertion:** `assert key_b not in scheduled`
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_out_of_scope_queue_row_absent_after_fixer_landing ____________
/Users/zwrose/.superheroes-worktrees/superheroes/issue-1445-e50bdbe8ca139cbb/plugins/superheroes/lib/tests/test_rulings_channel_1445.py:529: in test_out_of_scope_queue_row_absent_after_fixer_landing
    assert key_b not in scheduled
E   AssertionError: assert 'src/f00.py::bounds b@L3' not in {'src/f00.py::bounds a@L2', 'src/f00.py::bounds b@L3'}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_rulings_channel_1445.py::test_out_of_scope_queue_row_absent_after_fixer_landing
1 failed in 36.20s
```

- **Restore:** Reinserted oos-key skip before `filtered.append(row)`.
- **Restore receipt (quoted lines):**

```python
        key = _fix_batch_row_key(row)
        if key and key in oos_keys and not _live_out_of_scope_blocks_row(row):
            continue
        filtered.append(row)
```

- **Raw green:**

```
.                                                                        [100%]
1 passed in 29.50s
```

---

## BP-3

- **Guarded element:** `round_driver.py` — `_stage_findings`, live out-of-scope re-apply via `_record_disposition` (≈1549–1556).
- **Axis:** Restaging findings re-applies live out-of-scope dispositions from the rulings log.
- **Neutralization:** Removed the `live_oos` / `_record_disposition(...)` block inside the compile loop.

- **Detector:** `test_edge3_restage_reapplies_out_of_scope`
- **Failing assertion:** `assert entry.get("disposition") == "out-of-scope"`
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_edge3_restage_reapplies_out_of_scope ___________________
/Users/zwrose/.superheroes-worktrees/superheroes/issue-1445-e50bdbe8ca139cbb/plugins/superheroes/lib/tests/test_rulings_channel_1445.py:289: in test_edge3_restage_reapplies_out_of_scope
    assert entry.get("disposition") == "out-of-scope"
E   AssertionError: assert None == 'out-of-scope'
E    +  where None = <built-in method get of dict object at 0x10432b280>('disposition')
E    +    where <built-in method get of dict object at 0x10432b280> = {'classification': 'mechanical', 'detail': 'bounds B at src/f00.py:3', ...}.get
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_rulings_channel_1445.py::test_edge3_restage_reapplies_out_of_scope
1 failed in 22.29s
```

- **Restore:** Reinserted `live_oos` block before `seeded = True`.
- **Restore receipt (quoted lines):**

```python
        live_oos = _live_out_of_scope_ruling_for_key(state, key)
        if live_oos is not None and not _live_out_of_scope_blocks_row(entry):
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
1 passed in 27.75s
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

Superseded by **BP-7** (WO-S).

---

## BP-7

- **Guarded element:** `round_driver.py` — `_cmd_rule_locked`, `ruling-attempt-pending` check (before mutation).
- **Axis:** Rule refuses when a pending fixer attempt already has emitted orders.
- **Neutralization:** Prefixed the guard with `False and` so it never fires.

```python
    if (False and isinstance(pending, dict) and pending.get("phase") == P_FIXER
```

- **Detector:** `test_rule_refusal_tokens[ruling-attempt-pending-attempt_recorded]`
- **Failing assertion:** `assert out.get("ok") is False, out`
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_rule_refusal_tokens[ruling-attempt-pending-attempt_recorded] ______
...
>       assert out.get("ok") is False, out
E       AssertionError: {'action': 'dispatch-fixer', 'attempt': 1, ..., 'ok': True, ...}
E       assert True is False

plugins/superheroes/lib/tests/test_rulings_channel_1445.py:219: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_rulings_channel_1445.py::test_rule_refusal_tokens[ruling-attempt-pending-attempt_recorded]
1 failed in 57.70s
```

- **Restore:** Removed the `False and` prefix.
- **Restore receipt (quoted line):**

```python
    if (isinstance(pending, dict) and pending.get("phase") == P_FIXER
```

- **Raw green:**

```
.                                                                        [100%]
1 passed in 57.70s
```

---

## Post-restore workspace

```
git status --porcelain
```

(only this record file plus the round-1 fix sources differ from HEAD after restore)

---

## Final-head re-run at `12b3b95e` (review session 4, orchestrator-run)

Run by the build orchestrator in a detached probe worktree at `12b3b95e`, the layer's final code head. Each neutralization was a targeted edit through the host's edit action, reverted by the inverse edit, never by `git checkout`. Each red selected the exact detector node id. After every restore, `git status --porcelain` in the probe tree was empty. Green: `test_rulings_channel_1445.py` **38 passed** (EXIT=0), and the four fold detectors **27 passed** (EXIT=0).

| Proof | Guarded element | Neutralization | Detector | Raw red at `12b3b95e` |
|---|---|---|---|---|
| BP-1 (DoD binding) | `_gate_guidance_entries` ruling-channel loop | `continue` as the loop's first statement | `test_binding_ruling_rides_hashed_order_and_certifies` | `'reason': 'evidence-order-mismatch'` — 1 failed |
| BP-2 | `_filter_excluded_discharged_fixes` out-of-scope skip | guard deleted | `test_out_of_scope_queue_row_absent_after_fixer_landing` | `assert 'src/f00.py::bounds b@L3' not in {...}` — 1 failed |
| BP-3 | `_stage_findings` live out-of-scope re-apply | `live_oos` / `_record_disposition` block deleted | `test_edge3_restage_reapplies_out_of_scope` | `assert None == 'out-of-scope'` — 1 failed |
| BP-4 | `FIX_BATCH_SHA256` render context | `batch_sha = "0" * 64` | `test_fixer_order_pins_fix_batch_sha256` | literal `- Fix batch sha256: <64-hex>` absent from the order — 1 failed |
| BP-5 | `ruling-critical-out-of-scope` refusal | guard prefixed `False and` | `test_rule_refusal_tokens[ruling-critical-out-of-scope-critical_oos]` | `assert True is False` (rule answered ok; no refusal) — 1 failed |
| BP-7 | `ruling-attempt-pending` refusal | guard prefixed `False and` | `test_rule_refusal_tokens[ruling-attempt-pending-attempt_recorded]` | `assert True is False` — 1 failed |
| BP-8 (new) | `ruling-guidance-not-fixer` refusal (`step != P_FIXER`) | guard prefixed `False and` | `test_edge9_non_fixer_step_refuses_guidance` | `{'action': 'dispatch-audits', ..., 'ok': True}` / `assert True is False` — 1 failed |
| BP-9 (new) | `rulings-log-malformed` checks run for every owner classification | the rulings-log and counter checks moved back behind `if classification != RECOGNIZED: return None` (the advisor-named neutralization) | `test_rule_refuses_malformed_rulings_log_owner_absent[bad_log0]`, `[None]`, `test_rule_refuses_malformed_ruling_seq_counter_owner_absent` | `AttributeError: 'dict' object has no attribute 'append'`; `[None]`: `'ok': True` (the log silently rewritten to `[]`, which is the original Critical); `TypeError: can only concatenate str (not "int") to str` — 3 failed. The two recognized-owner detectors stayed green, as expected: this element doesn't guard them. |
| BP-10 (new) | pre-emission journal attribution (`rnd = state.get("round")` when nothing is pending) | `rnd = None` | `test_preemission_ruling_journal_carries_round_phase` | `assert None == 1` on the journal row's `round` — 1 failed |
| BP-v1 | `review_diff_bytes._require_explicit_commit_sha` | body reverted to the old `HEAD`-only denylist | `test_panel_diff_at_head_1419.py::test_v1_explicit_commit_guard_rejects_non_full_oid` | `AssertionError: subprocess.run must not be called` — 16 failed, 8 passed |
| BP-v2 | `_derive_panel_diff_at_head` `except ValueError` mapping | the two lines deleted | `test_panel_diff_at_head_1419.py::test_v2_derive_panel_diff_maps_head_value_error` | `ValueError: head_sha must be an explicit commit` escapes — 1 failed |
| BP-v1-base | `_derive_panel_diff_at_head` passes `verified_base` | raw `base` passed instead | `test_panel_diff_at_head_1419.py::test_v1_derive_panel_diff_resolves_short_base_ref` | `assert 'base_sha must be an explicit commit' is None` — 1 failed |
| BP-v1-caller | `handback_gate` recompute on `verified_base` | `pinned_base` passed instead | `test_handback_gate.py::test_short_base_sha_in_sidecar_still_recomputes_diff` | `assert 'refuse' == 'allow'` — 1 failed |

BP-6 stays superseded by BP-7. Refusal-token note: BP-5, BP-7, BP-8 and BP-9's owner-absent arms go red on `ok: True`. Each detector asserts `ok is False` before it asserts the exact token (`RD.<TOKEN>`), so the neutralized guard fails at the first assertion, and the token assertion is never reached.
