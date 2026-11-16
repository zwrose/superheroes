# Bite-proof record: i2554_bounded_pass_b2

Issue 2554, layer 3 of 2497: the bounded pass's B2 (one fix step and one more audit round). Detector files:
`plugins/superheroes/lib/tests/test_bounded_pass_b2_2554.py` and, for E-stall-entry,
`plugins/superheroes/lib/tests/test_c1l4_gates_retired.py`. Each red and green below is one run of one exact node id with
`scripts/pinned-python -B -X pycache_prefix=/tmp/wt2497-pyc -m pytest <node id> -q -n auto`.

The guarded-element set is these six, declared by the order: E-b2-entry, E-stall-entry, E-policy, E-mismatch,
E-early-settle, E-final-mismatch. Each was neutralized by a targeted edit in `plugins/superheroes/lib/round_driver.py`, run
red, restored by the inverse edit, and run green. Captures are quoted at the decisive lines (each full capture is under
4 KiB; elided: the `warning: The UV_NATIVE_TLS ...` line, the `bringing up nodes...` lines, the `[gwN] linux -- Python`
line, the `tmp_path = ...` line and the `Use -v to get more diff` lines). No secret, token, URL or personal detail appears
in any capture; nothing was redacted.

Restore receipt for the whole record: after the last restore, `git diff -U0 -- plugins/superheroes/lib/round_driver.py`
showed only the order's own `_audit_failures` change (a `line_less` helper and the id comparison); none of the six
neutralized lines appears in it. `git status --porcelain --untracked-files=no` after each restore listed exactly
`round_driver.py`, `test_bounded_pass_b2_2554.py`, `test_c1l4_gates_retired.py`, `test_outcome_settle_c7.py` and
`test_round_driver.py` as modified (this order's declared files; the bite-proof file itself is new). The restored lines are
quoted per element.

## E-b2-entry

- **Guarded element:** `round_driver.py` `_settle_bounded_audit`, the call `_begin_bounded_fix(state, config, open_ids,
  held, session_dir=session_dir)`. **Axis:** what B1 leaves open begins B2's one fix step instead of the `round-cap`
  hand-back.
- **Detector (expected red):** `plugins/superheroes/lib/tests/test_bounded_pass_b2_2554.py::test_t1_b1_leaves_a_fix_open_then_b2_runs_one_apply_fixes_a_verify_and_the_audits_in_the_next_round`
- **Neutralization:** the call replaced with `_hand_back(state, "round-cap", "neutralized: E-b2-entry", cap=True)`.
- **Raw red:**
  ```
  >       assert B1._after_cap_verify(trace) == [(RD.P_AUDITS, CAP + 1), (RD.P_APPLY_FIXES, CAP + 1), (RD.P_VERIFY, CAP + 1),
                                                 (RD.P_AUDITS, CAP + 2), (RD.P_TERMINAL, CAP + 2)], trace
  E       AssertionError: [('dispatch-panel', 1), ('dispatch-verifiers', 1), ('dispatch-synthesis', 1), ('apply-fixes', 1), ('dispatch-audits', 2), ('run-verify', 2), ...]
  E       assert [('dispatch-a...terminal', 3)] == [('dispatch-a...terminal', 4)]
  E
  E         At index 1 diff: ('terminal', 3) != ('apply-fixes', 3)
  E         Right contains 3 more items, first extra item: ('run-verify', 3)
  FAILED plugins/superheroes/lib/tests/test_bounded_pass_b2_2554.py::test_t1_b1_leaves_a_fix_open_then_b2_runs_one_apply_fixes_a_verify_and_the_audits_in_the_next_round
  1 failed in 3.61s
  ```
- **Restore:** the inverse edit. **Restored line quoted:**
  `        _begin_bounded_fix(state, config, open_ids, held, session_dir=session_dir)`
- **Raw green:** `1 passed in 3.69s`

## E-stall-entry

- **Guarded element:** `round_driver.py` `_handle_stall`, the call `_begin_stall_bounded_pass(state, config, breaker,
  session_dir=session_dir)`. **Axis:** the stall that persists past its one recovery begins the bounded pass instead of the
  `fix-keeps-failing` hand-back.
- **Detector (expected red):** `plugins/superheroes/lib/tests/test_c1l4_gates_retired.py::test_t2_a_fix_that_keeps_failing_gets_one_recovery_then_the_bounded_pass`
- **Neutralization:** the condition `if _begin_stall_bounded_pass(state, config, breaker, session_dir=session_dir):`
  replaced with `if False:  # neutralized: E-stall-entry`, so the flow falls to the `fix-keeps-failing` hand-back.
- **Raw red:**
  ```
  >       assert state["terminal"] == "converged"
  E       AssertionError: assert 'handed-back' == 'converged'
  E
  E         - converged
  E         + handed-back
  FAILED plugins/superheroes/lib/tests/test_c1l4_gates_retired.py::test_t2_a_fix_that_keeps_failing_gets_one_recovery_then_the_bounded_pass
  1 failed in 2.90s
  ```
- **Restore:** the inverse edit. **Restored line quoted:**
  `    if _begin_stall_bounded_pass(state, config, breaker, session_dir=session_dir):`
- **Raw green:** `1 passed in 0.98s`

## E-policy

- **Guarded element:** `round_driver.py` `_queue_fix_batch`, the call `filtered = _apply_bounded_queue_policy(state,
  filtered)`. **Axis:** B2's queue removes a Minor or Nit that no ruling, stall or restore names, after the fix-group
  closure.
- **Detector (expected red):** `plugins/superheroes/lib/tests/test_bounded_pass_b2_2554.py::test_t5_a_minor_pulled_in_only_as_a_fix_group_sibling_is_context_never_a_target`
- **Neutralization:** the call line replaced with `pass  # neutralized: E-policy`.
- **Raw red:**
  ```
  >       assert status == "queued" and batch == [u.ka], batch
  E       AssertionError: ['tests/test_charge_once.py::member 0@L1', 'tests/test_charge_amount.py::member 1@L1']
  E       assert ('queued' == 'queued'
  E           queued and ['tests/test_...:member 1@L1'] == ['tests/test_...:member 0@L1']
  E         Left contains one more item: 'tests/test_charge_amount.py::member 1@L1'
  FAILED plugins/superheroes/lib/tests/test_bounded_pass_b2_2554.py::test_t5_a_minor_pulled_in_only_as_a_fix_group_sibling_is_context_never_a_target
  1 failed in 0.89s
  ```
- **Restore:** the inverse edit. **Restored line quoted:**
  `        filtered = _apply_bounded_queue_policy(state, filtered)`
- **Raw green:** `1 passed in 0.93s`

## E-mismatch

- **Guarded element:** `round_driver.py` `_fold_audits`, the branch `if restorable and _is_bounded_audit_round(state):`.
  **Axis:** a test mismatch in B1's audit takes no restore-only step and no second test; its restore rides B2's one
  `apply-fixes`.
- **Detector (expected red):** `plugins/superheroes/lib/tests/test_bounded_pass_b2_2554.py::test_t6_a_b1_mismatch_takes_no_restore_step_and_no_second_test_the_restore_rides_b2s_one_apply_fixes` (both parametrized cases)
- **Neutralization:** `and state["boundedPass"].get("step") != "audit"` appended to the branch condition, so a bounded
  `audit` round falls to the ordinary `_begin_test_restore` detour.
- **Raw red:**
  ```
  >       assert RD.TEST_RESTORE_FIELD not in state and state["step"] == RD.P_APPLY_FIXES
  E       AssertionError: assert ('_testRestore' not in {'schemaVersion': 5, 'sessionGeneration': 7, 'config': {...}, 'round': 3, ...})
  E        +  where '_testRestore' = RD.TEST_RESTORE_FIELD
  FAILED ...::test_t6_a_b1_mismatch_takes_no_restore_step_and_no_second_test_the_restore_rides_b2s_one_apply_fixes[Important]
  FAILED ...::test_t6_a_b1_mismatch_takes_no_restore_step_and_no_second_test_the_restore_rides_b2s_one_apply_fixes[Minor]
  2 failed in 0.89s
  ```
  (the `[Important]` and `[Minor]` cases failed with the same assertion; one capture shown)
- **Restore:** the inverse edit. **Restored line quoted:**
  `    if restorable and _is_bounded_audit_round(state):`
- **Raw green:** `2 passed in 0.95s`

## E-early-settle

- **Guarded element:** `round_driver.py` `_settle_bounded_fix`, the order of the `left-for-owner` settle and the
  `_terminal_converged` call. **Axis:** the leftovers settle before the break-it kept check, so an unresolved break-it
  finding converges with a card instead of parking `cannot-certify`.
- **Detector:** `plugins/superheroes/lib/tests/test_bounded_pass_b2_2554.py::test_t7_an_uncleared_b2_finding_that_carries_a_break_it_test_converges_with_a_card_not_cannot_certify`
- **Finding: the first neutralization left the node GREEN.** The order's wording, "call `_terminal_converged` before the
  `left-for-owner` settle", was first applied as an addition: `_terminal_converged(state, config, full_panel=False,
  session_dir=session_dir)` inserted before the `for tid in sorted(open_ids):` loop, the existing final call kept. The node
  stayed green (the final call converges the session after the settle, over the earlier park). Raw output of that run:
  ```
  .                                                                        [100%]
  1 passed in 0.94s
  ```
  The insertion alone is therefore not a neutralization of this element; a call that runs before the settle and is the only
  one is. The node was not changed.
- **Neutralization that bit (same node):** the same early call inserted before the loop, and the final
  `_terminal_converged(...)` call at the end of the function replaced with `pass  # neutralized: E-early-settle (the call
  moved up, above)`: the terminal check runs before the settle and only there.
- **Raw red:**
  ```
  >       assert state["terminal"] == "converged", state["certification"]
  E       AssertionError: {'shape': None, 'reason': 'break-it test not kept: tests/test_charge.py (unresolved: no-disposition)'}
  E       assert 'cannot-certify' == 'converged'
  E
  E         - converged
  E         + cannot-certify
  FAILED plugins/superheroes/lib/tests/test_bounded_pass_b2_2554.py::test_t7_an_uncleared_b2_finding_that_carries_a_break_it_test_converges_with_a_card_not_cannot_certify
  1 failed in 1.04s
  ```
- **Restore:** both edits undone by their inverses (the `pass` line back to the call, the inserted early call removed).
  **Restored lines quoted:**
  `    left = []` followed by `    for tid in sorted(open_ids):`, and, at the end of the function,
  `    _terminal_converged(state, config, full_panel=False, session_dir=session_dir)`
- **Raw green:** `1 passed in 0.86s`

## E-final-mismatch

- **Guarded element:** `round_driver.py` `_fold_audits`, the branch `if restorable and _is_bounded_audit_round(state):`
  reaching `_bounded_mismatch`'s final-audit hand-back. **Axis:** a test mismatch in B2's audit hands back
  `bounded-pass-open`, so no weakened test is left on a converged head.
- **Detector (expected red):** `plugins/superheroes/lib/tests/test_bounded_pass_b2_2554.py::test_t6_a_b2_mismatch_hands_back_bounded_pass_open_with_no_restore_and_no_second_test`
- **Neutralization:** `and state["boundedPass"].get("step") != "final-audit"` appended to the branch condition, so a
  bounded `final-audit` round falls to the ordinary `_begin_test_restore` detour.
- **Raw red:**
  ```
  >       assert state["terminal"] == "handed-back" and state["decisions"][-1]["kind"] == "bounded-pass-open"
  E       AssertionError: assert (None == 'handed-back')
  FAILED plugins/superheroes/lib/tests/test_bounded_pass_b2_2554.py::test_t6_a_b2_mismatch_hands_back_bounded_pass_open_with_no_restore_and_no_second_test
  1 failed in 0.87s
  ```
- **Restore:** the inverse edit. **Restored line quoted:**
  `    if restorable and _is_bounded_audit_round(state):`
- **Raw green:** `1 passed in 0.91s`

## Review fix: two more elements (review session 1, round 1 of PR 2558)

Made by the build session at the review loop's `apply-fixes` step, for the two Important findings the panel and the
repository sweep raised. Each red and green is one run of one exact node id with
`scripts/pinned-python -B -X pycache_prefix=/tmp/wt-bp-pyc -m pytest <node id> -q -p no:cacheprovider`.

## E-ruling-empties

- **Guarded element:** `round_driver.py` `_reconcile_fix_queue_after_rulings`, the branch
  `elif status == "empty" and _in_bounded_fix_step(state) and not state.get("terminal"):` calling
  `_settle_ruled_empty_bounded_fix`. **Axis:** a ruling that leaves B2's pending step no target clears the stale slice
  and settles the pass, never a fix step still queued.
- **Detector (expected red):** `plugins/superheroes/lib/tests/test_bounded_pass_b2_2554.py::test_t10_a_ruling_that_leaves_b2s_pending_step_no_target_settles_the_pass_and_clears_the_slice`
- **Neutralization:** `False and ` inserted at the head of the branch condition, so the reconcile ignores an `empty`
  status, as before the fix.
- **Raw red:**
  ```
  >       assert state["terminal"] == "converged" and state["step"] == RD.P_TERMINAL, state.get("decisions")[-3:]
  E       AssertionError: [{'detail': 'newsurf.py::openimportant@L1', 'kind': 'not-discharged', 'round': 3}, {'detail': "the bounded pass's audi... out-of-scope on newsurf.py::openimportant@L1 (belongs to the next milestone)', 'kind': 'ruling-recorded', 'round': 3}]
  E       assert (None == 'converged')
  1 failed in 3.69s
  ```
- **Restore:** the inverse edit. **Restored line quoted:**
  `    elif status == "empty" and _in_bounded_fix_step(state) and not state.get("terminal"):`
- **Raw green:** `1 passed in 3.63s`

## E-restore-submits

- **Guarded element:** `round_driver.py` `_bounded_mismatch`, the loop `for item in items:` /
  `_sync_reviewer_test(state, item["findingKey"], item["content"])` after `bounded["restores"] = items`. **Axis:**
  B2's batch carries the test role's version the fixer commits, so its report passes the live submission check.
- **Detector (expected red):** `plugins/superheroes/lib/tests/test_bounded_pass_b2_2554.py::test_t6_b2s_fold_records_the_restore_once_and_runs_the_gate_before_its_audits`
- **Neutralization:** the element absent (the red was taken on the code before the fix, with the rebuilt test in
  place).
- **Raw red:**
  ```
  E       AssertionError: fix-without-break-it-test:tests/test_charge.py::retry charges twice@L1:test-bytes-differ
  E       assert ('fix-without-break-it-test:tests/test_charge.py::retry charges twice@L1:test-bytes-differ' is None)
  1 failed in 3.17s
  ```
- **Restore:** the fix added. **Added lines quoted:** `    for item in items:` and
  `        _sync_reviewer_test(state, item["findingKey"], item["content"])`
- **Raw green:** `1 passed in 3.17s`

## E-merge-places (review session 2, round 1 of PR 2558)

- **Guarded element:** `round_driver.py` `_begin_bounded_fix`, the line
  `rows = _union_open_blockers(targets, issue_rows)`. **Axis:** B1's reports of one finding merge with each other and
  with its open target, every place they name kept, so B2's audit owes them all.
- **Detector (expected red):** `plugins/superheroes/lib/tests/test_bounded_pass_b2_2554.py::test_t3_two_b1_reports_of_one_finding_reach_b2_as_one_row_owing_every_place_either_names`
- **Neutralization:** the line replaced by `rows = list(targets) + issue_rows`, the append before the fix.
- **Raw red:**
  ```
  E       AssertionError: [[{'title': 'unchecked retry', 'file': 'src/a.py', 'line': 2, 'severity': 'Important', ...}, {'title': 'unchecked retry', 'file': 'src/a.py', 'line': 2, 'severity': 'Important', ...}]]
  E       assert (1 == 1 and 2 == 1)
  ```
- **Restore:** the inverse edit. **Restored line quoted:** `    rows = _union_open_blockers(targets, issue_rows)`
- **Raw green:** `1 passed in 7.60s`

## E-merge-severity (review session 2, round 2 of PR 2558)

- **Guarded element:** `round_driver.py` `_begin_bounded_fix`, the line
  `row["severity"] = _strongest_severity(by_key.get(_finding_identity_key(row)) or [row.get("severity")])` after the
  union. **Axis:** a merged row carries the strongest severity any of its reports holds, so a blocking B1 report never
  rides as a Minor's context.
- **Detector (expected red):** `plugins/superheroes/lib/tests/test_bounded_pass_b2_2554.py::test_t3_a_b1_report_merged_into_an_open_target_keeps_the_strongest_severity[minor-important]`
- **Neutralization:** the line replaced by `pass`, so the union's first-wins severity stands.
- **Raw red:**
  ```
  E       AssertionError: {'id': 'src/a.py::unchecked retry@L2', 'title': 'unchecked retry', 'file': 'src/a.py', 'line': 2, ...}
  E       assert 'Minor' == 'Important'
  ```
- **Restore:** the inverse edit. **Restored line quoted:**
  `        row["severity"] = _strongest_severity(by_key.get(_finding_identity_key(row)) or [row.get("severity")])`
- **Raw green:** `1 passed in 3.31s`
