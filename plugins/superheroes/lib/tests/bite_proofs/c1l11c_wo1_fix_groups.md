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
