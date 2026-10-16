# The round driver never dispatches an unfilled seat or a maker-family auditor: bite-proof record

Implementer-run record on the working tree of branch `build/1796-wo-c`. Method: for each element the harness replaced one exact string (the old string occurs once in its file), ran the detector node alone (`python3 -B -m pytest <node> -q -p no:cacheprovider -x --tb=short`), put the old string back by the inverse exact-string edit (in a `finally`, then asserted the file byte-identical to its pre-edit content), and ran the same node again. Detectors were not edited during the proof. Production code only was neutralized. Redaction: the pytest temp directory prefix is replaced by `<tmp>/`; nothing else is altered.

Declared element set (from the order): N1 unfilled seats skipped at order emission; N2 the auto-journaled missing envelope; N3 `_fold_panel` refusing to credit a submitted unfilled seat; N4 the session's unfilled reviewer row; N5 `makerFamilies` reaching the account's makers; N6 `independent_auditor`'s maker-family exclusion; N7 its pinned-vendor restriction; N8 the removed non-runner degraded fallback; N9 the removed runner-only degraded fallback; N10 a no-auditor target folding as not run.

## Disclosures

- Every element is proven on its own neutralization and its own red; no grouping was used.
- Not in the declared set and therefore **unproven** (no neutralization applied): the interleave-fence exemption `_is_unfilled_missing_record` in `_durable_slot_records` (covered only by the hand-submit assertions in `test_hand_submitted_payload_for_an_unfilled_seat_is_folded_missing_and_not_credited`), the emission-time skip of the `AuditorUnseatable` refusal for a target with no auditor at all (`test_t2c_emit_orders_manifest_does_not_refuse_a_target_with_no_eligible_auditor`), the `independence != "independent"` stamp in `_audit_targets`, and the reworded receipt prose in `build_degraded_prose`.
- N1 and N2 share the detector `test_unfilled_seat_gets_no_order_a_missing_envelope_and_advance_completes`; each red is on a different assertion of it (N1 on the manifest's seat list, N2 on the stored `seat-missing/1` read).
- N8 and N9 apply to the same two lines of `_auditor_vendor`; N8 restores only the host-path fallback (`runner_only` false), N9 only the runner-only loop, and each is caught by a different detector.
- No element was `Unprovable as placed`, `Unreachable through this entry point`, or `Unrunnable here`.

## N1 — unfilled seats skipped at order emission

- **site:** `plugins/superheroes/lib/round_driver.py`
- **detector:** `plugins/superheroes/lib/tests/test_round_driver.py::test_unfilled_seat_gets_no_order_a_missing_envelope_and_advance_completes`
- **neutralization (exact-string, count(old)=1):**

```diff
-        if seat_key in unfilled:
-            # No candidate outside
+        if False and seat_key in unfilled:
+            # No candidate outside
```

- **raw red (rc 1):**

```
F
=================================== FAILURES ===================================
__ test_unfilled_seat_gets_no_order_a_missing_envelope_and_advance_completes ___
/home/user/wt-1796-c/plugins/superheroes/lib/tests/test_round_driver.py:7526: in test_unfilled_seat_gets_no_order_a_missing_envelope_and_advance_completes
    assert sorted(manifest["seats"]) == sorted(
E   AssertionError: assert ['architectur...764d882ad280'] == ['architectur...764d882ad280']
E     
E     At index 1 diff: 'code-reviewer-e08ba693bb6ad36a' != 'premortem-reviewer-8604769b846a4c86'
E     Left contains one more item: 'test-reviewer-39d0764d882ad280'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_unfilled_seat_gets_no_order_a_missing_envelope_and_advance_completes
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.69s
```

- **restore:** the inverse exact-string edit; the file is byte-identical to its pre-edit content (asserted in the harness). Restored lines quoted back:

```
        if seat_key in unfilled:
            # No candidate outside```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 2.38s
```

- **verdict:** RED->GREEN

## N2 — the auto-journaled missing envelope (completeness)

- **site:** `plugins/superheroes/lib/round_driver.py`
- **detector:** `plugins/superheroes/lib/tests/test_round_driver.py::test_unfilled_seat_gets_no_order_a_missing_envelope_and_advance_completes`
- **neutralization (exact-string, count(old)=1):**

```diff
-        for seat_key, occurrence in unfilled_slots:
-            missing = 
+        for seat_key, occurrence in ():
+            missing = 
```

- **raw red (rc 1):**

```
F
=================================== FAILURES ===================================
__ test_unfilled_seat_gets_no_order_a_missing_envelope_and_advance_completes ___
/home/user/wt-1796-c/plugins/superheroes/lib/tests/test_round_driver.py:7532: in test_unfilled_seat_gets_no_order_a_missing_envelope_and_advance_completes
    assert err is None
E   AssertionError: assert 'missing' is None
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_unfilled_seat_gets_no_order_a_missing_envelope_and_advance_completes
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 2.40s
```

- **restore:** the inverse exact-string edit; the file is byte-identical to its pre-edit content (asserted in the harness). Restored lines quoted back:

```
        for seat_key, occurrence in unfilled_slots:
            missing = ```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.58s
```

- **verdict:** RED->GREEN

## N3 — _fold_panel refusing to credit a submitted unfilled seat

- **site:** `plugins/superheroes/lib/round_driver.py`
- **detector:** `plugins/superheroes/lib/tests/test_round_driver.py::test_fold_panel_never_credits_an_unfilled_seats_findings_when_no_receipt_is_stored`
- **neutralization (exact-string, count(old)=1):**

```diff
-    if unfilled and isinstance(seats, dict):
-        seats = {dim: seat
+    if False and unfilled and isinstance(seats, dict):
+        seats = {dim: seat
```

- **raw red (rc 1):**

```
F
=================================== FAILURES ===================================
_ test_fold_panel_never_credits_an_unfilled_seats_findings_when_no_receipt_is_stored _
/home/user/wt-1796-c/plugins/superheroes/lib/tests/test_round_driver.py:7581: in test_fold_panel_never_credits_an_unfilled_seats_findings_when_no_receipt_is_stored
    assert state["rounds"]["1"]["seatStatus"]["security-reviewer"] == "missing"
E   AssertionError: assert 'run' == 'missing'
E     
E     - missing
E     + run
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_fold_panel_never_credits_an_unfilled_seats_findings_when_no_receipt_is_stored
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.29s
```

- **restore:** the inverse exact-string edit; the file is byte-identical to its pre-edit content (asserted in the harness). Restored lines quoted back:

```
    if unfilled and isinstance(seats, dict):
        seats = {dim: seat```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.22s
```

- **verdict:** RED->GREEN

## N4 — the session's unfilled reviewer row

- **site:** `plugins/superheroes/lib/review_record_session.py`
- **detector:** `plugins/superheroes/lib/tests/test_review_record_session.py::test_an_unfilled_seat_is_listed_as_planned_and_not_run_even_with_no_slot_journaled`
- **neutralization (exact-string, count(old)=1):**

```diff
-    out += [_unfilled_reviewer(rnd, seat) for rnd, names in unfilled.items() for seat in names]
+    out += []
```

- **raw red (rc 1):**

```
F
=================================== FAILURES ===================================
_ test_an_unfilled_seat_is_listed_as_planned_and_not_run_even_with_no_slot_journaled _
/home/user/wt-1796-c/plugins/superheroes/lib/tests/test_review_record_session.py:240: in test_an_unfilled_seat_is_listed_as_planned_and_not_run_even_with_no_slot_journaled
    assert set(rows) == {"code-reviewer (round 1)", "security-reviewer (round 1)", "security-reviewer (round 2)"}
E   AssertionError: assert {'code-reviewer (round 1)'} == {'code-review...er (round 2)'}
E     
E     Extra items in the right set:
E     'security-reviewer (round 1)'
E     'security-reviewer (round 2)'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_session.py::test_an_unfilled_seat_is_listed_as_planned_and_not_run_even_with_no_slot_journaled
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.16s
```

- **restore:** the inverse exact-string edit; the file is byte-identical to its pre-edit content (asserted in the harness). Restored lines quoted back:

```
    out += [_unfilled_reviewer(rnd, seat) for rnd, names in unfilled.items() for seat in names]
```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.07s
```

- **verdict:** RED->GREEN

## N5 — makerFamilies reaching the account's makers

- **site:** `plugins/superheroes/lib/review_record_session.py`
- **detector:** `plugins/superheroes/lib/tests/test_review_record_session.py::test_the_maps_maker_families_join_the_makers_once`
- **neutralization (exact-string, count(old)=1):**

```diff
-    for family in sorted(receipt_disclosures.maker_families(
+    for family in sorted([] and receipt_disclosures.maker_families(
```

- **raw red (rc 1):**

```
F
=================================== FAILURES ===================================
______________ test_the_maps_maker_families_join_the_makers_once _______________
/home/user/wt-1796-c/plugins/superheroes/lib/tests/test_review_record_session.py:267: in test_the_maps_maker_families_join_the_makers_once
    assert account["makers"] == [{"family": "openai", "source": "the extras"},
E   AssertionError: assert [{'family': '...'the extras'}] == [{'family': '... maker list'}]
E     
E     Right contains one more item: {'family': 'anthropic', 'source': 'seat map maker list'}
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record_session.py::test_the_maps_maker_families_join_the_makers_once
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.09s
```

- **restore:** the inverse exact-string edit; the file is byte-identical to its pre-edit content (asserted in the harness). Restored lines quoted back:

```
    for family in sorted(receipt_disclosures.maker_families(```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.08s
```

- **verdict:** RED->GREEN

## N6 — independent_auditor's maker-family exclusion

- **site:** `plugins/superheroes/lib/receipt_disclosures.py`
- **detector:** `plugins/superheroes/lib/tests/test_round_driver.py::test_auditor_vendor_excludes_every_makers_family`
- **neutralization (exact-string, count(old)=1):**

```diff
-    barred = set(maker_families or ())
+    barred = set()
```

- **raw red (rc 1):**

```
F
=================================== FAILURES ===================================
_______________ test_auditor_vendor_excludes_every_makers_family _______________
/home/user/wt-1796-c/plugins/superheroes/lib/tests/test_round_driver.py:7602: in test_auditor_vendor_excludes_every_makers_family
    assert RD._auditor_vendor(cfg, "claude", maker_families=frozenset({"openai"})) == (
E   AssertionError: assert ('codex', 'independent') == (None, 'unseatable')
E     
E     At index 0 diff: 'codex' != None
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_auditor_vendor_excludes_every_makers_family
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.27s
```

- **restore:** the inverse exact-string edit; the file is byte-identical to its pre-edit content (asserted in the harness). Restored lines quoted back:

```
    barred = set(maker_families or ())
```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.17s
```

- **verdict:** RED->GREEN

## N7 — independent_auditor's pinned-vendor restriction

- **site:** `plugins/superheroes/lib/receipt_disclosures.py`
- **detector:** `plugins/superheroes/lib/tests/test_round_driver.py::test_pinned_roster_restricts_the_auditor_to_the_pinned_vendors`
- **neutralization (exact-string, count(old)=1):**

```diff
-        if pinned_vendors and v not in pinned_vendors:
+        if False and pinned_vendors and v not in pinned_vendors:
```

- **raw red (rc 1):**

```
F
=================================== FAILURES ===================================
________ test_pinned_roster_restricts_the_auditor_to_the_pinned_vendors ________
/home/user/wt-1796-c/plugins/superheroes/lib/tests/test_round_driver.py:7617: in test_pinned_roster_restricts_the_auditor_to_the_pinned_vendors
    assert "auditorVendor" not in targets[0] and targets[0]["independence"] == "unseatable"
E   AssertionError: assert ('auditorVendor' not in {'id': 'f.py::bug@L1', 'findingKey': 'f.py::bug@L1', 'identity': 'f.py::bug', 'file': 'f.py', ...})
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_pinned_roster_restricts_the_auditor_to_the_pinned_vendors
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.27s
```

- **restore:** the inverse exact-string edit; the file is byte-identical to its pre-edit content (asserted in the harness). Restored lines quoted back:

```
        if pinned_vendors and v not in pinned_vendors:
```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.17s
```

- **verdict:** RED->GREEN

## N8 — the removed non-runner degraded fallback

- **site:** `plugins/superheroes/lib/round_driver.py`
- **detector:** `plugins/superheroes/lib/tests/test_round_driver.py::test_auditor_vendor_family_keyed_single_vendor_same_family_unseatable`
- **neutralization (exact-string, count(old)=1):**

```diff
-        return vendor, "independent"
-    return None, "unseatable"
+        return vendor, "independent"
+    live = _live_vendors(config)
+    if not runner_only:
+        return (live[0] if live else fixer_vendor), "degraded"
+    return None, "unseatable"
```

- **raw red (rc 1):**

```
F
=================================== FAILURES ===================================
____ test_auditor_vendor_family_keyed_single_vendor_same_family_unseatable _____
/home/user/wt-1796-c/plugins/superheroes/lib/tests/test_round_driver.py:4597: in test_auditor_vendor_family_keyed_single_vendor_same_family_unseatable
    assert RD._auditor_vendor({"vendors": ["claude"]}, "claude") == (None, "unseatable")
E   AssertionError: assert ('claude', 'degraded') == (None, 'unseatable')
E     
E     At index 0 diff: 'claude' != None
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_auditor_vendor_family_keyed_single_vendor_same_family_unseatable
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.26s
```

- **restore:** the inverse exact-string edit; the file is byte-identical to its pre-edit content (asserted in the harness). Restored lines quoted back:

```
        return vendor, "independent"
    return None, "unseatable"
```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.21s
```

- **verdict:** RED->GREEN

## N9 — the removed runner-only degraded fallback

- **site:** `plugins/superheroes/lib/round_driver.py`
- **detector:** `plugins/superheroes/lib/tests/test_layer4a_auditor_seat_time_1272.py::test_t1_e3_codex_only_fixer_codex_unseatable`
- **neutralization (exact-string, count(old)=1):**

```diff
-        return vendor, "independent"
-    return None, "unseatable"
+        return vendor, "independent"
+    if runner_only:
+        for v in _live_vendors(config):
+            if session_contract.runner_channel_vendor(v):
+                return v, "degraded"
+    return None, "unseatable"
```

- **raw red (rc 1):**

```
F
=================================== FAILURES ===================================
_________________ test_t1_e3_codex_only_fixer_codex_unseatable _________________
/home/user/wt-1796-c/plugins/superheroes/lib/tests/test_layer4a_auditor_seat_time_1272.py:116: in test_t1_e3_codex_only_fixer_codex_unseatable
    assert round_driver._auditor_vendor(cfg, "codex", runner_only=True) == (None, "unseatable")
E   AssertionError: assert ('codex', 'degraded') == (None, 'unseatable')
E     
E     At index 0 diff: 'codex' != None
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer4a_auditor_seat_time_1272.py::test_t1_e3_codex_only_fixer_codex_unseatable
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.07s
```

- **restore:** the inverse exact-string edit; the file is byte-identical to its pre-edit content (asserted in the harness). Restored lines quoted back:

```
        return vendor, "independent"
    return None, "unseatable"
```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.06s
```

- **verdict:** RED->GREEN

## N10 — a no-auditor target folding as not run (never discharged)

- **site:** `plugins/superheroes/lib/round_driver.py`
- **detector:** `plugins/superheroes/lib/tests/test_round_driver.py::test_a_result_submitted_for_a_target_with_no_auditor_is_ignored_and_the_target_is_unaudited`
- **neutralization (exact-string, count(old)=1):**

```diff
-    if no_auditor_ids:
-        results = [r for r in results
+    if False and no_auditor_ids:
+        results = [r for r in results
```

- **raw red (rc 1):**

```
F
=================================== FAILURES ===================================
_ test_a_result_submitted_for_a_target_with_no_auditor_is_ignored_and_the_target_is_unaudited _
/home/user/wt-1796-c/plugins/superheroes/lib/tests/test_round_driver.py:7650: in test_a_result_submitted_for_a_target_with_no_auditor_is_ignored_and_the_target_is_unaudited
    assert outcome["unaudited"] == [tid] and outcome["discharged"] == []
E   AssertionError: assert ([] == ['f.py::bug@L1']
E     
E     Right contains one more item: 'f.py::bug@L1'
E     Use -v to get more diff)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_a_result_submitted_for_a_target_with_no_auditor_is_ignored_and_the_target_is_unaudited
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.26s
```

- **restore:** the inverse exact-string edit; the file is byte-identical to its pre-edit content (asserted in the harness). Restored lines quoted back:

```
    if no_auditor_ids:
        results = [r for r in results```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed in 0.17s
```

- **verdict:** RED->GREEN
