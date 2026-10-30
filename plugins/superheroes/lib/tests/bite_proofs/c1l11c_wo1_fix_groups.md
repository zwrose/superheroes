# Bite-proof record c1l11c_wo1_fix_groups

The detectors this change adds: the fix-group rule for findings that carry break-it tests and share a root cause
(`verification.merge_and_rank`'s `fixGroups`; `round_driver._stamp_fix_groups`, `_close_batch_over_fix_groups`,
`_queue_fix_batch`'s slice pull-in, `_shared_fix_commit`, `_apply_fixes_commit_fault`'s split check, the re-queued
audit target's `reviewerTest`; `review_record._fix_group_fault`), and the replacement of
`test_l4_merge_and_rank_never_merges_a_break_it_finding` by `test_l4_merge_and_rank_keeps_each_break_it_member_in_one_fix_group`.

Guarded elements, declared up front by the order: E1 a test-carrying member stays out of the merge, E2 `fixGroups`
is emitted, E3 the group's commit is one commit bound to every member, E4 the commit changes something besides every
member's test, E5 a partly unfixed group is refused, E6 a cap slice never splits a group, E7 the record refuses a
malformed `fixGroup`, E8 the batch is closed over fix groups, E9 the test role's original test rides a re-queued
target, E10 the group id is the driver's own. One neutralization and one red each, then one combined green.

Who ran it: the implementer's attempt was cut off by the runner's timeout during its E7 red run, leaving E7's
neutralization in the build worktree; the builder restored it by the inverse edit, committed the landed work
(`573343af`), and re-ran all ten proofs itself in a detached probe worktree at that commit. Every neutralization was a
targeted edit through the edit tool, undone by the inverse edit; no `git checkout`, `git restore`, `git reset` or
`git stash` was run. After the last restore, `git status --short` and `git diff --stat` in the probe worktree printed
nothing. One edit (E9's first try) matched two places and was refused by the edit tool, so its run had no
neutralization in place; that green run is discarded and E9 was re-run with a unique match.

Every run used, from the probe worktree:
`scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-probe -m pytest plugins/superheroes/lib/tests/test_fix_groups_c1l11c.py plugins/superheroes/lib/tests/test_break_it_loop.py -q -p no:cacheprovider -n auto`
(`--timeout` is not an option of this pytest setup). Captures below are the failing nodes and their assertion lines;
the `UV_NATIVE_TLS` deprecation warning and the `bringing up nodes...` lines are left out. Nothing is redacted.

---

## E1 — a test-carrying member stays out of the merge (`verification.py`, the carve-out loop)

- neutralization: `for m in [m for m in members if break_it.carries_test(m)]:` became `for m in []:`.
- detector: `test_break_it_loop.py::test_l4_merge_and_rank_keeps_each_break_it_member_in_one_fix_group` (DoD row 3).
- red: `2 failed, 42 passed, 3 errors`; failing nodes include
  `test_break_it_loop.py::test_l4_merge_and_rank_keeps_each_break_it_member_in_one_fix_group` and
  `test_fix_groups_c1l11c.py::test_merge_and_rank_ties_only_groups_with_a_test_carrier_and_two_results`, with
  `AssertionError: assert ([] == [{'group_id':...['v0', 'v2']}]`; the three errors are `KeyError: 'Break-it: a retried
  charge runs twice'` in fixtures whose test-carrying finding was folded into another (its test lost).

## E2 — `fixGroups` is emitted (`verification.py`, the return)

- neutralization: `"fixGroups": fix_groups` became `"fixGroups": []`.
- detector: `test_fix_groups_c1l11c.py::test_fr18_two_break_it_findings_sharing_a_root_cause_get_one_fix_and_both_runs_are_recorded` (DoD row 1).
- red: `4 failed, 43 passed`; the DoD row-1 test fails with `KeyError: 'fixGroup'`, beside the two-round test, the
  `merge_and_rank` unit pin and the row-3 replacement.

## E3 — one commit bound to every member (`round_driver._shared_fix_commit`)

- neutralization: `if not all(sha_of(commit) in {sha_of(c) for c in bound[key]} for key, _block in members):` became `if False:`.
- detector: `test_fix_groups_c1l11c.py::test_members_bound_to_different_commits_or_a_commit_that_fails_one_member_refuse_no_shared_commit`.
- red: `1 failed, 46 passed`; `At index 0 diff: None != 'fix-group-no-shared-commit:fg-fa811dcc4f29'`.

## E4 — a change beside every member's test (`round_driver._shared_fix_commit`)

- neutralization: `_fix_commit_test_fault(facts.get(commit), block, exempt_paths=paths)` became `_fix_commit_test_fault(facts.get(commit), block)`.
- detector: `test_fix_groups_c1l11c.py::test_a_commit_that_holds_every_members_test_and_nothing_else_refuses_no_shared_commit`.
- red: `1 failed, 46 passed`; `At index 0 diff: None != 'fix-group-no-shared-commit:fg-fa811dcc4f29'`.

## E5 — a partly unfixed group is refused (`round_driver._apply_fixes_commit_fault`)

- neutralization: `if len(keys) > 1 and 0 < len([k for k in keys if k in left]) < len(keys):` became `if False:`.
- detector: `test_fix_groups_c1l11c.py::test_members_listed_partly_unfixed_refuse_a_split_group_and_all_unfixed_owes_nothing`.
- red: `1 failed, 46 passed`; `At index 0 diff: None != 'fix-group-split:fg-fa811dcc4f29'`.

## E6 — a cap slice never splits a group (`round_driver._queue_fix_batch`)

- neutralization: `pulled = [r for r in tail if _fix_group_id(r) in head_groups]` became `pulled = []`.
- detector: `test_fix_groups_c1l11c.py::test_a_fix_group_member_queued_past_the_cap_is_pulled_into_the_slice`.
- red: `1 failed, 46 passed`; `assert ['member 0'] == ['member 0', 'member 1']`.

## E7 — the record refuses a malformed `fixGroup` (`review_record._validate`)

- neutralization: `fault = _fix_group_fault(f["fixGroup"])` became `fault = None`.
- detector: `test_fix_groups_c1l11c.py::test_the_record_writer_refuses_a_malformed_fix_group_naming_the_finding_and_the_part`.
- red: `1 failed, 46 passed`; the writer accepted the malformed record (`{'ok': True, 'action': 'created', ...}`):
  `assert (True, None) == (False, 'revi...ount-invalid')`.

## E8 — the batch is closed over fix groups (`round_driver._close_batch_over_fix_groups`)

- neutralization: `if key and key not in present and key not in held and _fix_group_id(row) in group_ids:` became `if False:`.
- detector: `test_fix_groups_c1l11c.py::test_an_important_and_a_minor_member_both_reach_the_apply_fixes_check_and_both_get_audit_targets`.
- red: `1 failed, 46 passed`; the Minor member is missing: `Right contains one more item: 'tests/test_charge_once.py::member 0@L1'`.

## E9 — the test role's original test rides a re-queued target (`round_driver._audit_targets`)

- neutralization: `REVIEWER_TEST_FIELD` removed from `for carried in ("suggestion", "body", break_it.RUN_FIELD, break_it.RUNS_FIELD, REVIEWER_TEST_FIELD):`.
- detector: `test_fix_groups_c1l11c.py::test_a_requeued_member_judged_weakened_is_compared_on_its_next_audit_to_the_test_roles_original`.
- red: `1 failed, 46 passed`; `KeyError: 'reviewerTest'`.

## E10 — the group id is the driver's own (`round_driver._stamp_fix_groups`)

- neutralization: `group_id = "fg-" + hashlib.sha256(...).hexdigest()[:12]` became `group_id = group.get("group_id")`.
- detector: `test_fix_groups_c1l11c.py::test_the_fix_group_id_is_the_drivers_hash_of_the_member_keys_whatever_the_grouping_names`.
- red: `7 failed, 40 passed`; on axis: `{'id': 'g0', ...} != {'id': 'fg-fa811dcc4f29', ...}`.

## Green

All ten restored: `47 passed`, exit 0.

---

## Review-fix guards E11–E15 (appended by build #2279, C1-L11f, WO-C)

The five review-loop fixes of PR #2270 in `round_driver.py` (`42ae1a8b`, `67a51f15`, `50db579a`, `ea737d76`, `5b0f8054`)
carry `# axis:` comments citing this record (all but `42ae1a8b`'s line, which has none), yet E1–E10 above did not cover them.
Their original red/green receipts sit in PR #2270's build record: "`42ae1a8b`, the plain-member binding check neutralized: `2
failed` (`…whether_or_not_each_carries_a_test[tests1]`, `[tests2]`) / green `116 passed`; `67a51f15`, `named = named +
plain_named` dropped: `2 failed` (`test_a_plain_member_bound_to_head_naming_the_shared_commit_folds[tests0]`, `[tests1]`) /
green `119 passed`; `50db579a`, the batch closure emptied: `3 failed` (the ruled, guidance-restored and delta-settle
entry-path tests) / green `123 passed`; `ea737d76`, `_hold_owner_choice` on pulled siblings dropped: `2 failed` (the two
`tradeoff` sibling tests) / green `125 passed`; `5b0f8054`, `_attach_row_rulings` over the composed batch dropped: `1 failed`
(`test_a_pulled_sibling_carries_the_guidance_a_finding_merged_into_it_was_already_sent_under`) / green `126 passed`."
That is the provenance; the receipts below are a re-run on the tree of build #2279 (head `4f350065` plus WO-C's uncommitted
work), by the WO-C implementer, in `/home/user/wt-2279-c`. Each neutralization was one targeted edit through the edit tool in
`round_driver.py`, undone by the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was run. After each restore
`git diff --stat plugins/superheroes/lib/round_driver.py` printed nothing and the restored line was found by `grep -n`
(quoted per entry). Every run was
`timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-c -m pytest <node ids> -q -p no:cacheprovider --tb=short`
over the named nodes of `plugins/superheroes/lib/tests/test_fix_groups_c1l11c.py`; the captures are the runner's output
apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out. The counts differ from PR #2270's because these
runs are narrowed to the named nodes, not the three test files. Nothing is redacted.

### E11 — a plain member's bound commit must be the shared one (`round_driver._shared_fix_commit`, `42ae1a8b`)

- neutralization: `if not all(sha_of(commit) in {sha_of(c) for c in bound[key]} for key in plain_keys if bound.get(key)):` became `if False:`.
- detector: `test_fix_groups_c1l11c.py::test_members_bound_to_different_commits_refuse_whether_or_not_each_carries_a_test` (its `[tests1]` and `[tests2]` cases).
- red (taken in a second dispatch, with a literal command, `--tb=short`, only the `UV_NATIVE_TLS` warning line left out):
```
.FF                                                                      [100%]
=================================== FAILURES ===================================
_ test_members_bound_to_different_commits_refuse_whether_or_not_each_carries_a_test[tests1] _
/home/user/wt-2279-c/plugins/superheroes/lib/tests/test_fix_groups_c1l11c.py:442: in test_members_bound_to_different_commits_refuse_whether_or_not_each_carries_a_test
    assert _check(u, [(u.ka, "c1"), (u.kb, "c2")], {"c1": passing, "c2": passing}) == (
E   AssertionError: assert (None, [{'fin...mmit': 'c1'}]) == ('fix-group-n...1dcc4f29', [])
E     
E     At index 0 diff: None != 'fix-group-no-shared-commit:fg-fa811dcc4f29'
E     Use -v to get more diff
_ test_members_bound_to_different_commits_refuse_whether_or_not_each_carries_a_test[tests2] _
/home/user/wt-2279-c/plugins/superheroes/lib/tests/test_fix_groups_c1l11c.py:442: in test_members_bound_to_different_commits_refuse_whether_or_not_each_carries_a_test
    assert _check(u, [(u.ka, "c1"), (u.kb, "c2")], {"c1": passing, "c2": passing}) == (
E   AssertionError: assert (None, [{'fin...mmit': 'c2'}]) == ('fix-group-n...1dcc4f29', [])
E     
E     At index 0 diff: None != 'fix-group-no-shared-commit:fg-fa811dcc4f29'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_fix_groups_c1l11c.py::test_members_bound_to_different_commits_refuse_whether_or_not_each_carries_a_test[tests1]
FAILED plugins/superheroes/lib/tests/test_fix_groups_c1l11c.py::test_members_bound_to_different_commits_refuse_whether_or_not_each_carries_a_test[tests2]
2 failed, 1 passed in 2.20s
```
  This matches PR #2270's original red for this element (`2 failed`, `[tests1]` and `[tests2]`). The first dispatch's red
  run was refused by the harness's command check (a shell variable in the command); it was not retried in another form.
- restore: the inverse edit (`if False:` back to the `if not all(…)` line); `git diff --stat -- plugins/superheroes/lib/round_driver.py`
  printed nothing, and `grep -n` printed
  `5858:        if not all(sha_of(commit) in {sha_of(c) for c in bound[key]} for key in plain_keys if bound.get(key)):`.
- green (the restored tree):
```
...                                                                      [100%]
3 passed in 2.14s
```

### E12 — a plain member's bound commit is resolved with the carriers' (`round_driver._apply_fixes_commit_fault`, `67a51f15`)

- neutralization: `named = named + plain_named` became `named = named`.
- detector: `test_fix_groups_c1l11c.py::test_a_plain_member_bound_to_head_naming_the_shared_commit_folds`.
- red:
```
FF                                                                       [100%]
=================================== FAILURES ===================================
___ test_a_plain_member_bound_to_head_naming_the_shared_commit_folds[tests0] ___
/home/user/wt-2279-c/plugins/superheroes/lib/tests/test_fix_groups_c1l11c.py:453: in test_a_plain_member_bound_to_head_naming_the_shared_commit_folds
    assert detail is None
E   AssertionError: assert 'fix-group-no-shared-commit:fg-fa811dcc4f29' is None
___ test_a_plain_member_bound_to_head_naming_the_shared_commit_folds[tests1] ___
/home/user/wt-2279-c/plugins/superheroes/lib/tests/test_fix_groups_c1l11c.py:453: in test_a_plain_member_bound_to_head_naming_the_shared_commit_folds
    assert detail is None
E   AssertionError: assert 'fix-group-no-shared-commit:fg-fa811dcc4f29' is None
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_fix_groups_c1l11c.py::test_a_plain_member_bound_to_head_naming_the_shared_commit_folds[tests0]
FAILED plugins/superheroes/lib/tests/test_fix_groups_c1l11c.py::test_a_plain_member_bound_to_head_naming_the_shared_commit_folds[tests1]
2 failed in 2.14s
```
- restore receipt: `git diff --stat` over `round_driver.py` printed nothing; `grep -n` printed `5916:    named = named + plain_named`.
- green:
```
..                                                                       [100%]
2 passed in 2.19s
```

### E13 — every composed batch is closed over its fix groups (`round_driver._queue_fix_batch`, `50db579a`)

- neutralization: in `siblings = [dict(r) for r in _close_batch_over_fix_groups(state, [], filtered)`, the call became `[]`: `siblings = [dict(r) for r in []`.
- detector: `test_fix_groups_c1l11c.py::test_an_owner_ruling_that_adds_a_group_member_brings_its_sibling_into_the_batch`, `::test_a_guidance_restored_member_offered_beside_no_sibling_brings_its_sibling_into_the_batch` and `::test_a_delta_settle_offering_the_important_member_brings_its_minor_sibling_into_the_batch`.
- red:
```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_an_owner_ruling_that_adds_a_group_member_brings_its_sibling_into_the_batch _
/home/user/wt-2279-c/plugins/superheroes/lib/tests/test_fix_groups_c1l11c.py:587: in test_an_owner_ruling_that_adds_a_group_member_brings_its_sibling_into_the_batch
    assert sorted(RD._finding_identity_key(r) for r in u.state["_fixBatch"]) == sorted([u.ka, u.kb])
E   AssertionError: assert ['tests/test_...:member 0@L1'] == ['tests/test_...:member 0@L1']
E     
E     At index 0 diff: 'tests/test_charge_once.py::member 0@L1' != 'tests/test_charge_amount.py::member 1@L1'
E     Right contains one more item: 'tests/test_charge_once.py::member 0@L1'
E     Use -v to get more diff
_ test_a_guidance_restored_member_offered_beside_no_sibling_brings_its_sibling_into_the_batch _
/home/user/wt-2279-c/plugins/superheroes/lib/tests/test_fix_groups_c1l11c.py:596: in test_a_guidance_restored_member_offered_beside_no_sibling_brings_its_sibling_into_the_batch
    assert sorted(RD._finding_identity_key(r) for r in u.state["_fixBatch"]) == sorted([u.ka, u.kb])
E   AssertionError: assert ['tests/test_...:member 0@L1'] == ['tests/test_...:member 0@L1']
E     
E     At index 0 diff: 'tests/test_charge_once.py::member 0@L1' != 'tests/test_charge_amount.py::member 1@L1'
E     Right contains one more item: 'tests/test_charge_once.py::member 0@L1'
E     Use -v to get more diff
_ test_a_delta_settle_offering_the_important_member_brings_its_minor_sibling_into_the_batch _
/home/user/wt-2279-c/plugins/superheroes/lib/tests/test_fix_groups_c1l11c.py:605: in test_a_delta_settle_offering_the_important_member_brings_its_minor_sibling_into_the_batch
    assert sorted(RD._finding_identity_key(r) for r in state["_fixBatch"]) == sorted([u.ka, u.kb])
E   AssertionError: assert ['tests/test_...:member 0@L1'] == ['tests/test_...:member 0@L1']
E     
E     At index 0 diff: 'tests/test_charge_once.py::member 0@L1' != 'tests/test_charge_amount.py::member 1@L1'
E     Right contains one more item: 'tests/test_charge_once.py::member 0@L1'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_fix_groups_c1l11c.py::test_an_owner_ruling_that_adds_a_group_member_brings_its_sibling_into_the_batch
FAILED plugins/superheroes/lib/tests/test_fix_groups_c1l11c.py::test_a_guidance_restored_member_offered_beside_no_sibling_brings_its_sibling_into_the_batch
FAILED plugins/superheroes/lib/tests/test_fix_groups_c1l11c.py::test_a_delta_settle_offering_the_important_member_brings_its_minor_sibling_into_the_batch
3 failed in 2.42s
```
- restore receipt: `git diff --stat` over `round_driver.py` printed nothing; `grep -n` printed `5493:    siblings = [dict(r) for r in _close_batch_over_fix_groups(state, [], filtered)`.
- green:
```
...                                                                      [100%]
3 passed in 2.01s
```

### E14 — a pulled sibling goes through the owner-choice hold (`round_driver._close_batch_over_fix_groups`, `ea737d76`)

- neutralization: `return closed + (_hold_owner_choice(state, pulled) if pulled else [])` became `return closed + pulled`.
- detector: `test_fix_groups_c1l11c.py::test_a_tradeoff_minor_sibling_pulled_by_the_closure_is_held_for_the_owner_not_admitted` and `::test_a_tradeoff_sibling_pulled_by_the_queue_closure_is_held_for_the_owner_not_admitted`.
- red:
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_a_tradeoff_minor_sibling_pulled_by_the_closure_is_held_for_the_owner_not_admitted _
/home/user/wt-2279-c/plugins/superheroes/lib/tests/test_fix_groups_c1l11c.py:621: in test_a_tradeoff_minor_sibling_pulled_by_the_closure_is_held_for_the_owner_not_admitted
    assert u.state["ownerChoiceHeld"] == [u.kb]
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
E   KeyError: 'ownerChoiceHeld'
_ test_a_tradeoff_sibling_pulled_by_the_queue_closure_is_held_for_the_owner_not_admitted _
/home/user/wt-2279-c/plugins/superheroes/lib/tests/test_fix_groups_c1l11c.py:630: in test_a_tradeoff_sibling_pulled_by_the_queue_closure_is_held_for_the_owner_not_admitted
    assert u.state["ownerChoiceHeld"] == [u.kb]
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
E   KeyError: 'ownerChoiceHeld'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_fix_groups_c1l11c.py::test_a_tradeoff_minor_sibling_pulled_by_the_closure_is_held_for_the_owner_not_admitted
FAILED plugins/superheroes/lib/tests/test_fix_groups_c1l11c.py::test_a_tradeoff_sibling_pulled_by_the_queue_closure_is_held_for_the_owner_not_admitted
2 failed in 2.32s
```
- restore receipt: `git diff --stat` over `round_driver.py` printed nothing; `grep -n` printed `4473:    return closed + (_hold_owner_choice(state, pulled) if pulled else [])`.
- green:
```
..                                                                       [100%]
2 passed in 2.20s
```

### E15 — a pulled sibling gets the inherited-ruling attachment (`round_driver._queue_fix_batch`, `5b0f8054`)

- neutralization: `_attach_row_rulings(state, filtered, _live_ruling_by_key(state), _sibling_ledger)` became `pass`.
- detector: `test_fix_groups_c1l11c.py::test_a_pulled_sibling_carries_the_guidance_a_finding_merged_into_it_was_already_sent_under`.
- red:
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_pulled_sibling_carries_the_guidance_a_finding_merged_into_it_was_already_sent_under _
/home/user/wt-2279-c/plugins/superheroes/lib/tests/test_fix_groups_c1l11c.py:648: in test_a_pulled_sibling_carries_the_guidance_a_finding_merged_into_it_was_already_sent_under
    assert (batch[u.kb].get("ruledBy"), batch[u.kb].get("ruledBySeq")) == (km, seq)
E   AssertionError: assert (None, None) == ('tests/test_...ibling@L1', 1)
E     
E     At index 0 diff: None != 'tests/test_charge_amount.py::merged into the sibling@L1'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_fix_groups_c1l11c.py::test_a_pulled_sibling_carries_the_guidance_a_finding_merged_into_it_was_already_sent_under
1 failed in 2.09s
```
- restore receipt: `git diff --stat` over `round_driver.py` printed nothing; `grep -n` printed `5507:            _attach_row_rulings(state, filtered, _live_ruling_by_key(state), _sibling_ledger)`.
- green:
```
.                                                                        [100%]
1 passed in 1.98s
```
