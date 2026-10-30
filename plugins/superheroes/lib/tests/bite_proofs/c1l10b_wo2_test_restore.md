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
