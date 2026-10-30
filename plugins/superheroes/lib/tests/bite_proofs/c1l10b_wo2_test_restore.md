# C1-L10b (WO-2) bite-proof — the test role's break-it test is restored, then the one correction

**Provenance:** implementer WO-2 / `lib/round_driver.py`, `lib/tests/test_c1l10b_test_restore.py`

Declared guarded elements (from the order): E1 the restore entry at the end of `_fold_audits`; E2 the shared restore check's byte comparison; E3 the once-only guard on the correction; E4 the carried-block sync. Each was neutralized with one targeted edit and restored with the inverse edit (the same line, edited back); no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2264`. Raw captures are the pytest output of the named node(s) with `--tb=line`, the `UV_NATIVE_TLS` warning line and the `bringing up nodes...` lines left out; nothing else is trimmed and no secret, token or private URL appears in them.

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| E1 | `round_driver.py` `_fold_audits`, the `if restorable:` entry | an audit fold that lists a mismatch sets the restore-only step, not its old continuation | `test_t1_a_weakened_test_is_restored_by_a_restore_only_step_before_anything_else` |
| E2 | `round_driver.py` `_restore_commit_fault`, the `if have != item["content"].encode("utf-8"):` comparison | a restore commit that does not hold the test role's bytes is refused (handed back) | `test_t5_the_shared_check_refuses_every_way_a_restore_can_fail[wrong-bytes]`, `test_t5_through_submit_a_restore_that_failed_hands_the_pr_back[wrong-bytes]` |
| E3 | `round_driver.py` `_correction_used`, the `held.get("used") is True` test | no finding is offered a second correction | `test_t3_the_test_reviewer_gets_exactly_one_correction_over_the_session` |
| E4 | `round_driver.py` `_sync_reviewer_test`, the `if block is not None:` rewrite of `suggestion` | the carried block holds the test role's version on every row that holds the finding | `test_t4_a_landed_correction_is_committed_and_becomes_the_reviewers_version_everywhere` |

Not separately neutralized in this order, so unproven by this record: the `testCorrection` write on the finding, the unseatable skip, the correction fold's "no correction" reasons, the submit-side refusal of a restore report that carries `unfixed` or a binding, the pending-restore guards in `_apply_fixes_payload_fields`, `_stage_apply_fixes_step` and `_reconcile_fix_queue_after_rulings`, and the verify gate after the restore. Their tests exist in the same file; none was reddened here. E1 was reddened with its T1 node only; the T2 nodes (extra audit round, correction seat, round at the cap) were not run against the neutralization.

---

## E1 — the restore entry

**neutralization** (`round_driver.py`, `_fold_audits`):
```python
-    if restorable:
+    if False and restorable:  # BITE-PROOF NEUTRALIZED: if restorable:
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -n auto --tb=line -p no:cacheprovider "plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_t1_a_weakened_test_is_restored_by_a_restore_only_step_before_anything_else"`
```
F                                                                        [100%]
=================================== FAILURES ===================================
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmp3mU5G3/bin/python
E   AssertionError: assert 'run-verify' == 'apply-fixes'
      
      - apply-fixes
      + run-verify
/home/user/wt-2264/plugins/superheroes/lib/tests/test_c1l10b_test_restore.py:207: AssertionError: assert 'run-verify' == 'apply-fixes'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_t1_a_weakened_test_is_restored_by_a_restore_only_step_before_anything_else
1 failed in 1.64s
```

**restore:** the inverse edit, `    if False and restorable:  # BITE-PROOF NEUTRALIZED: if restorable:` back to `    if restorable:`.

**restore receipt:** `grep` of `round_driver.py` for `^    if restorable:` finds line 7340, `    if restorable:`; a search of `plugins/superheroes/lib/round_driver.py` for `BITE-PROOF NEUTRALIZED` finds nothing.

**raw green:** same command.
```
.                                                                        [100%]
1 passed in 9.22s
```

---

## E2 — the shared restore check's byte comparison

**neutralization** (`round_driver.py`, `_restore_commit_fault`):
```python
-        if have != item["content"].encode("utf-8"):
+        if False and have != item["content"].encode("utf-8"):  # BITE-PROOF NEUTRALIZED: if have != item["content"].encode("utf-8"):
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -n auto --tb=line -p no:cacheprovider "plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_t5_the_shared_check_refuses_every_way_a_restore_can_fail" "plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_t5_through_submit_a_restore_that_failed_hands_the_pr_back"`
```
...F....F..                                                              [100%]
=================================== FAILURES ===================================
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpP28OPv/bin/python
E   AssertionError: assert (None, 'bbbbb...bbbbbbbbbbbb') == ('tests/test_...differ', None)
      
      At index 0 diff: None != 'tests/test_charge.py:test-bytes-differ'
      Use -v to get more diff
/home/user/wt-2264/plugins/superheroes/lib/tests/test_c1l10b_test_restore.py:529: AssertionError: assert (None, 'bbbbb...bbbbbbbbbbbb') == ('tests/test_...differ', None)
[gw1] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpP28OPv/bin/python
E   AssertionError: {'ok': True, 'round': 2, 'phase': 'apply-fixes', 'nextStep': 'run-verify', ...}
    assert (True is True and 'run-verify' == 'terminal'
      
      - terminal
      + run-verify)
/home/user/wt-2264/plugins/superheroes/lib/tests/test_c1l10b_test_restore.py:609: AssertionError: {'ok': True, 'round': 2, 'phase': 'apply-fixes', 'nextStep': 'run-verify', ...}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_t5_the_shared_check_refuses_every_way_a_restore_can_fail[wrong-bytes]
FAILED plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_t5_through_submit_a_restore_that_failed_hands_the_pr_back[wrong-bytes]
2 failed, 9 passed in 8.19s
```

**restore:** the inverse edit, back to `        if have != item["content"].encode("utf-8"):`.

**restore receipt:** `grep` of `round_driver.py` for `^        if have != item\["content"\]` finds line 5520, `        if have != item["content"].encode("utf-8"):`.

**raw green:** same command.
```
...........                                                              [100%]
11 passed in 2.53s
```

---

## E3 — the once-only guard on the correction

**neutralization** (`round_driver.py`, `_correction_used`):
```python
-        if isinstance(held, dict) and held.get("used") is True:
+        if False and isinstance(held, dict) and held.get("used") is True:  # BITE-PROOF NEUTRALIZED: if isinstance(held, dict) and held.get("used") is True:
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -n auto --tb=line -p no:cacheprovider "plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_t3_the_test_reviewer_gets_exactly_one_correction_over_the_session"`
```
F                                                                        [100%]
=================================== FAILURES ===================================
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpjImfHK/bin/python
E   AssertionError: a second correction was offered
    assert 'dispatch-second-test' == 'run-verify'
      
      - run-verify
      + dispatch-second-test
/home/user/wt-2264/plugins/superheroes/lib/tests/test_c1l10b_test_restore.py:372: AssertionError: a second correction was offered
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_t3_the_test_reviewer_gets_exactly_one_correction_over_the_session
1 failed in 1.03s
```

**restore:** the inverse edit, back to `        if isinstance(held, dict) and held.get("used") is True:`.

**restore receipt:** `grep` of `round_driver.py` for `^        if isinstance\(held, dict\) and held.get\("used"\) is True:` finds line 5567, `        if isinstance(held, dict) and held.get("used") is True:`.

**raw green:** same command.
```
.                                                                        [100%]
1 passed in 1.12s
```

---

## E4 — the carried-block sync

**neutralization** (`round_driver.py`, `_sync_reviewer_test`):
```python
-            if block is not None:
+            if False and block is not None:  # BITE-PROOF NEUTRALIZED: if block is not None:
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -n auto --tb=line -p no:cacheprovider "plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_t4_a_landed_correction_is_committed_and_becomes_the_reviewers_version_everywhere"`
```
F                                                                        [100%]
=================================== FAILURES ===================================
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpyTThKv/bin/python
E   AssertionError: assert ('def test_cha...rge(2) == 2\n' == 'def test_cha...rge(3) == 3\n'
      
      Skipping 56 identical leading characters in diff, use -v to show
        ge(2) == 2
      -     assert charge(3) == 3)
/home/user/wt-2264/plugins/superheroes/lib/tests/test_c1l10b_test_restore.py:454: AssertionError: assert ('def test_cha...rge(2) == 2\n' == 'def test_cha...rge(3) == 3\n'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_t4_a_landed_correction_is_committed_and_becomes_the_reviewers_version_everywhere
1 failed in 1.10s
```

**restore:** the inverse edit, back to `            if block is not None:`.

**restore receipt:** `grep` of `round_driver.py` for `^            if block is not None:$` finds line 5556, `            if block is not None:`.

**raw green:** same command.
```
.                                                                        [100%]
1 passed in 0.96s
```

---

## Addendum (WO-3, item 7) — the bite-proofs WO-2b stopped before

WO-2b built `round_orders._template_name` and `round_driver._restored_run_record` and stopped before proving them. Each proof below is one targeted edit, one run of the named detector alone, the inverse edit, and the green run of the same command. Every run was `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -n auto --tb=line -p no:cacheprovider <nodes>` from the worktree root; the captures were not filtered except that the one-line `UV_NATIVE_TLS` deprecation warning the launcher prints was dropped. They hold no secrets, tokens, private URLs or PII; the only paths are pytest's own.

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| W2-E1 (against T2) | `round_driver.py` `_fold_audits`, the `if restorable:` entry | the extra-audit, cap and unanswered-correction terminal paths all restore the test reviewer's test before any terminal | the four `test_t2_…` nodes of `test_c1l10b_test_restore.py` (`-k t2`) |
| W2-E5 | `round_driver.py` `_restored_run_record`, the final `dict(run, sha256=…, content=…)` substitution | after a restore the kept check expects the restored bytes, not the bytes the run saw | `test_t9_a_session_that_converges_after_a_restore_keeps_the_restored_test` |
| W2-E6 | `round_orders.py` `_template_name`, the correction branch | the second-test phase with `correction` exactly `true` renders from its own correction template | `test_t7_the_rendered_correction_order_carries_the_correction_instructions` |
| W2-E7 | `round_driver.py` `_restored_run_record`, the `restored < run_round` half of the guard | a run later than the restore is checked as that later run, whatever the ledger's carried block holds | `test_t9_a_later_run_wins_over_an_older_restore_whatever_the_ledger_block_holds` |

### W2-E1 against T2 — the restore entry

**neutralization** (`round_driver.py`, `_fold_audits`):
```python
-    if restorable:
+    if False and restorable:  # BITE-PROOF NEUTRALIZED: if restorable:
```

**raw red:** the command above with `plugins/superheroes/lib/tests/test_c1l10b_test_restore.py -k t2`
```
bringing up nodes...
bringing up nodes...

FFFF                                                                     [100%]
=================================== FAILURES ===================================
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpKylmoX/bin/python
E   AssertionError: assert 'run-verify' == 'apply-fixes'
      
      - apply-fixes
      + run-verify
/home/user/wt-2264/plugins/superheroes/lib/tests/test_c1l10b_test_restore.py:258: AssertionError: assert 'run-verify' == 'apply-fixes'
[gw3] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpKylmoX/bin/python
E   KeyError: 'restoreOnly'
/home/user/wt-2264/plugins/superheroes/lib/tests/test_c1l10b_test_restore.py:277: KeyError: 'restoreOnly'
[gw1] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpKylmoX/bin/python
E   AssertionError: assert ('terminal' == 'dispatch-second-test'
      
      - dispatch-second-test
      + terminal)
/home/user/wt-2264/plugins/superheroes/lib/tests/test_c1l10b_test_restore.py:305: AssertionError: assert ('terminal' == 'dispatch-second-test'
[gw2] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpKylmoX/bin/python
E   AssertionError: assert ('verify' == 'restore'
      
      - restore
      + verify)
/home/user/wt-2264/plugins/superheroes/lib/tests/test_c1l10b_test_restore.py:345: AssertionError: assert ('verify' == 'restore'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_t2_the_extra_audit_round_restores_then_verifies_then_hands_back_open
FAILED plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_t2_a_correction_seat_that_fails_authentication_parks_with_the_reviewers_test_already_committed
FAILED plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_t2_a_correction_never_answered_still_leaves_the_reviewers_test_committed
FAILED plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_t2_a_round_at_the_cap_restores_then_hands_back_the_open_finding
4 failed in 1.13s
```

**restore:** the inverse edit, `    if False and restorable:  # BITE-PROOF NEUTRALIZED: if restorable:` back to `    if restorable:`.

**restore receipt:** `grep -n "^    if restorable:"` of `round_driver.py` finds line 7352, `    if restorable:`; a search of `plugins/superheroes/lib/*.py` for `BITE-PROOF` finds nothing.

**raw green:** same command.
```
bringing up nodes...
bringing up nodes...

....                                                                     [100%]
4 passed in 1.01s
```

### W2-E5 — the restored-bytes substitution

**neutralization** (`round_driver.py`, `_restored_run_record`):
```python
-    return dict(run, sha256=_sha256(block["content"]), content=block["content"])
+    return run  # BITE-PROOF NEUTRALIZED: return dict(run, sha256=_sha256(block["content"]), content=block["content"])
```

**raw red:** the command above with `"plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_t9_a_session_that_converges_after_a_restore_keeps_the_restored_test"`
```
bringing up nodes...
bringing up nodes...

F                                                                        [100%]
=================================== FAILURES ===================================
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpo91dwA/bin/python
E   AssertionError: {'shape': None, 'reason': 'break-it test not kept: tests/test_charge_once.py (changed: sha256-differs)'}
    assert 'cannot-certify' == 'converged'
      
      - converged
      + cannot-certify
/home/user/wt-2264/plugins/superheroes/lib/tests/test_c1l10b_test_restore.py:907: AssertionError: {'shape': None, 'reason': 'break-it test not kept: tests/test_charge_once.py (changed: sha256-differs)'}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_t9_a_session_that_converges_after_a_restore_keeps_the_restored_test
1 failed in 1.42s
```

**restore:** the inverse edit, back to `    return dict(run, sha256=_sha256(block["content"]), content=block["content"])`.

**restore receipt:** the restored line is quoted in the restore sentence above; a search of `plugins/superheroes/lib/*.py` for `BITE-PROOF` finds nothing.

**raw green:** same command.
```
bringing up nodes...
bringing up nodes...

.                                                                        [100%]
1 passed in 1.50s
```

### W2-E6 — the correction template selection

**neutralization** (`round_orders.py`, `_template_name`, first line of the body):
```python
+    return phase  # BITE-PROOF NEUTRALIZED
     payload = context.get("payload")
```

**raw red:** the command above with `"plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_t7_the_rendered_correction_order_carries_the_correction_instructions"`
```
bringing up nodes...
bringing up nodes...

F                                                                        [100%]
=================================== FAILURES ===================================
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpAbtCEh/bin/python
E   AssertionError: unfilled-placeholder:HELD_FINDINGS_PATH
    assert 'unfilled-placeholder:HELD_FINDINGS_PATH' is None
/home/user/wt-2264/plugins/superheroes/lib/tests/test_c1l10b_test_restore.py:770: AssertionError: unfilled-placeholder:HELD_FINDINGS_PATH
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_t7_the_rendered_correction_order_carries_the_correction_instructions
1 failed in 1.28s
```

**restore:** the inverse edit, removing the added `return phase  # BITE-PROOF NEUTRALIZED` line so the body again starts `    payload = context.get("payload")`.

**restore receipt:** a search of `plugins/superheroes/lib/round_orders.py` for `BITE-PROOF` finds nothing; the line after the docstring of `_template_name` is `    payload = context.get("payload")`.

**raw green:** same command.
```
bringing up nodes...
bringing up nodes...

.                                                                        [100%]
1 passed in 1.12s
```

### W2-E7 — the `restored < run_round` ordering guard

**neutralization** (`round_driver.py`, `_restored_run_record`):
```python
-    if restored is None or restored < run_round:
+    if restored is None:  # BITE-PROOF NEUTRALIZED: if restored is None or restored < run_round:
```

**raw red:** the command above with `"plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_t9_a_later_run_wins_over_an_older_restore_whatever_the_ledger_block_holds"`
```
bringing up nodes...
bringing up nodes...

F                                                                        [100%]
=================================== FAILURES ===================================
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpVTpO3g/bin/python
E   AssertionError: assert (True, 'changed') == (False, 'kept')
      
      At index 0 diff: True != False
      Use -v to get more diff
/home/user/wt-2264/plugins/superheroes/lib/tests/test_c1l10b_test_restore.py:951: AssertionError: assert (True, 'changed') == (False, 'kept')
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_t9_a_later_run_wins_over_an_older_restore_whatever_the_ledger_block_holds
1 failed in 1.48s
```

**restore:** the inverse edit, back to `    if restored is None or restored < run_round:`.

**restore receipt:** `grep -n "restored is None or restored < run_round"` of `round_driver.py` finds line 8072, `    if restored is None or restored < run_round:`; a search of `plugins/superheroes/lib/*.py` for `BITE-PROOF` finds nothing.

**raw green:** same command.
```
bringing up nodes...
bringing up nodes...

.                                                                        [100%]
1 passed in 1.50s
```

Still unproven by this record, as before: the `testCorrection` write on the finding, the unseatable skip, the correction fold's "no correction" reasons, the submit-side refusal of a restore report that carries `unfixed` or a binding, and the pending-restore guards.

### W5-E1 — the identity dedupe in _reviewer_test_rows (WO-5)

**guarded element:** the `and not any(r is row for r in rows)` clause in `_reviewer_test_rows` (`round_driver.py`, line 5539). Axis: a fix-batch or audit-target row whose contents equal an already-collected row, but which is a different object, is still rewritten by `_sync_reviewer_test`. Detector: `test_t4_equal_fix_batch_and_audit_target_rows_are_both_rewritten` in `plugins/superheroes/lib/tests/test_c1l10b_test_restore.py`.

**neutralization** (`round_driver.py`, `_reviewer_test_rows`):
```diff
-                and not any(r is row for r in rows)
+                and row not in rows
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/wo5-pyc -m pytest plugins/superheroes/lib/tests/test_c1l10b_test_restore.py -q -p no:cacheprovider -k test_t4_equal_fix_batch_and_audit_target_rows_are_both_rewritten`
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_t4_equal_fix_batch_and_audit_target_rows_are_both_rewritten _______

    def test_t4_equal_fix_batch_and_audit_target_rows_are_both_rewritten():
        state = RD.new_state({})
        mine = C1._finding(content=FIXED_TEST, reviewer_test=ROLE_TEST, changed_why=WHY)
        key = RD._finding_key_of(mine)
        batch_row, target_row = copy.deepcopy(mine), copy.deepcopy(mine)
        assert batch_row == target_row and batch_row is not target_row
        state["fixBatch"] = [batch_row]
        state["_auditTargets"] = [target_row]
        RD._sync_reviewer_test(state, key, CORRECTED_TEST, correction={"round": 2, "used": True, "outcome": "corrected"})
        for row in (batch_row, target_row):
>           assert row[RD.REVIEWER_TEST_FIELD] == CORRECTED_TEST
E           AssertionError: assert 'def test_cha...rge(2) == 2\n' == 'def test_cha...rge(3) == 3\n'
E             
E               def test_charge():
E             -     import charge_mod
E                   assert charge(2) == 2
E             -     assert charge(3) == 3

/home/user/sh-2264/plugins/superheroes/lib/tests/test_c1l10b_test_restore.py:499: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_t4_equal_fix_batch_and_audit_target_rows_are_both_rewritten
1 failed, 65 deselected in 1.63s
```

**restore:** the inverse edit, back to `                and not any(r is row for r in rows)`.

**restore receipt:** `grep -n "not any(r is row for r in rows)\|row not in rows" plugins/superheroes/lib/round_driver.py` finds only the identity form:
```
5539:                and not any(r is row for r in rows)
```

**raw green:** same command as the raw red.
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 65 deselected in 1.20s
```

### W7-E1 — the second failing post-restore run halts through the real run-verify and advance commands

**guarded element:** the `if result == "fail":` halt in `_fold_verify` (`round_driver.py`, line 6411). Axis: on a durable session where a passing verify landed before the restore, the first failing run at the restored head is recorded as a re-run and the second halts the round (`verify-fail`), driven through `cmd_run_verify` and `cmd_advance`. Detector: `test_two_failing_runs_after_a_restore_halt_through_run_verify_and_advance_never_counting_the_landed_pass` in `plugins/superheroes/lib/tests/test_c1l10b_test_restore.py`.

**neutralization** (`round_driver.py`, `_fold_verify`): the second failing run no longer takes the failure halt.
```diff
-    if result == "fail":
+    if result == "fail" and first is None:
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/w7-pyc -m pytest plugins/superheroes/lib/tests/test_c1l10b_test_restore.py -q -p no:cacheprovider -k two_failing_runs_after_a_restore` (assertion excerpt; the test body above it is elided)
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
>       assert _decisions(end)[-1] == "verify-fail"
E       AssertionError: assert 'verify-unresolved' == 'verify-fail'
E         
E         - verify-fail
E         + verify-unresolved

plugins/superheroes/lib/tests/test_c1l10b_test_restore.py:1174: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_two_failing_runs_after_a_restore_halt_through_run_verify_and_advance_never_counting_the_landed_pass
1 failed, 72 deselected in 4.01s
```

**restore:** the inverse edit, back to `    if result == "fail":`.

**restore receipt:** `grep -n 'if result == "fail"' plugins/superheroes/lib/round_driver.py` finds:
```
6355:        if result == "fail" and not moved and artifact.get("via") != "ci-exact-head":
6411:    if result == "fail":
```

**raw green:** same command as the raw red.
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 72 deselected in 52.20s
```

### W7-E2 — the gate after a restore refuses a run that moved HEAD during the run

**guarded element:** the `moved or` half of the guard in `_fold_verify` (`round_driver.py`, line 6341: `if restored is not None and (moved or (head is not None and head != restored)):`). Axis: while `_restoredHead` is set, a passing verify that starts at the restored head but ends at another commit (`headSha` is the restored head, `headShaAfter` a different full commit id) halts with `verify-unresolved`, certification withheld, step `P_TERMINAL`, the detail naming that HEAD moved during the run. Detector: `test_the_gate_after_a_restore_refuses_a_run_that_moved_head_during_the_run` in `plugins/superheroes/lib/tests/test_c1l10b_test_restore.py` (case `head-moved-during-the-run` bites; case `head-held-still`, whose `headShaAfter` equals the restored head, stays green with and without the guard half and pins that a run that held still is still accepted).

**neutralization** (`round_driver.py`, `_fold_verify`): the guard no longer fires on `moved`.
```diff
-    if restored is not None and (moved or (head is not None and head != restored)):
+    if restored is not None and ((head is not None and head != restored)):
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/wo7-pyc -m pytest plugins/superheroes/lib/tests/test_c1l10b_test_restore.py -q -p no:cacheprovider -k refuses_a_run_that_moved_head --tb=line` (the `--tb=line` flag was added to the order's command form to keep the capture short, as the earlier entries in this file do)
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F.                                                                       [100%]
=================================== FAILURES ===================================
E   AssertionError: assert (None == 'halted')
/home/user/sh-2264/plugins/superheroes/lib/tests/test_c1l10b_test_restore.py:1120: AssertionError: assert (None == 'halted')
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l10b_test_restore.py::test_the_gate_after_a_restore_refuses_a_run_that_moved_head_during_the_run[head-moved-during-the-run]
1 failed, 1 passed, 73 deselected in 2.04s
```

**restore:** the inverse edit, back to `    if restored is not None and (moved or (head is not None and head != restored)):`.

**restore receipt:** `grep -n "if restored is not None and" plugins/superheroes/lib/round_driver.py` finds:
```
6341:    if restored is not None and (moved or (head is not None and head != restored)):
```

**raw green:** same command as the raw red.
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..                                                                       [100%]
2 passed, 73 deselected in 2.52s
```
