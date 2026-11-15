# #2489 bite-proof — the review loop rules on each finding the synthesis merged into another

**Provenance:** claude / sonnet-5.5 (implementer, work order WO-3b). Detector file: `plugins/superheroes/lib/tests/test_merged_member_loop_2489.py`.
Base for the restore checks: commit `9bbe35f6` (WO-3). Every run is
`scripts/pinned-python -B -X pycache_prefix=/tmp/wo3-pyc -m pytest plugins/superheroes/lib/tests/test_merged_member_loop_2489.py -q -p no:cacheprovider -k <test name>`,
the detector unedited, one test per run. Each neutralization is one targeted Edit on `plugins/superheroes/lib/round_driver.py`, undone by the inverse Edit.
The restore receipt is the restored line quoted back from a Grep, plus `git diff 9bbe35f6 --stat -- plugins/superheroes/lib/round_driver.py`, which printed nothing after every
restore: WO-3b made no change to `round_driver.py`, so an empty diff shows no neutralization residue.
Nothing was redacted (no credential-like text appears). Dropped from every capture: the `UV_NATIVE_TLS` deprecation warning line. Captures are far under the 32 KiB / 128 KiB ceilings.

## Guarded elements (declared in the order)

| ID | Failure mode | Neutralized site | Detector |
|---|---|---|---|
| E1 | a member the audit did not rule fixed stays merged into a fixed representative | `round_driver.py:9667` (`_fold_merged_members`) | `test_edge3_a_member_the_result_does_not_answer_is_reopened` |
| E2 | a member's `memberResults` row carries the representative's discharge, not the member's own answer | `round_driver.py:9665` | `test_edge2_a_member_answered_not_fixed_is_reopened_and_never_reads_fixed` |
| E3 | the end-of-loop settle skips a member under a fixed representative that never ruled it fixed | `round_driver.py:3164` (`_settle_open_findings`) | `test_edge9_the_settle_leaves_open_a_member_under_a_fixed_representative_with_no_ruling_of_its_own` |
| E4 | the audit target lists none of the findings merged into it | `round_driver.py:9410` (`target_row`) | `test_the_target_lists_every_finding_merged_into_it_sorted_by_id_with_its_content` |

The four are four distinct failure modes; none is grouped. The end-to-end arms (fresh session and carried) were not neutralized; each element's red above comes from the unit test named.

## E1 — the reopen of a member not answered fixed

**neutralization** (`round_driver.py:9667`): `if fixed:` → `if fixed or True:  # E1 NEUTRALIZED`. Every member now skips the reopen.

**raw red** (`-k test_edge3_a_member_the_result_does_not_answer_is_reopened`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_edge3_a_member_the_result_does_not_answer_is_reopened __________
        for key in (M_A, M_B):
>           assert SC.MERGED_INTO_FIELD not in _ledger(state, key)
E           AssertionError: assert 'mergedInto' not in {'id': 'F-mem-a', 'findingKey': 'mem-a', 'title': 'member mem-a', 'severity': 'Important', ...}
/home/user/wt-2489-wo3/plugins/superheroes/lib/tests/test_merged_member_loop_2489.py:199: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merged_member_loop_2489.py::test_edge3_a_member_the_result_does_not_answer_is_reopened
1 failed, 18 deselected in 1.82s
```
(Elided: the test's source lines above the `>` line, the `+  where` lines, and the `tmp_path` line.)

**restore:** inverse Edit. **restore receipt:** Grep after the restore for `NEUTRALIZED|^            if fixed:` printed only `9667:            if fixed:`; `git diff 9bbe35f6 --stat -- plugins/superheroes/lib/round_driver.py` printed nothing.

**raw green** (same selector):
```
.                                                                        [100%]
1 passed, 18 deselected in 1.54s
```

## E2 — `memberResults` from the member's own answer

**neutralization** (`round_driver.py:9665`): `.append({session_contract.FINDING_KEY_FIELD: key, "fixed": fixed})` → `.append({session_contract.FINDING_KEY_FIELD: key, "fixed": True})  # E2 NEUTRALIZED`. The reopen (E1's line) is intact, so only the written row changes.

**raw red** (`-k test_edge2_a_member_answered_not_fixed_is_reopened_and_never_reads_fixed`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_edge2_a_member_answered_not_fixed_is_reopened_and_never_reads_fixed ___
>       assert _ledger(state, REP)[SC.MEMBER_RESULTS_FIELD] == [
            {SC.FINDING_KEY_FIELD: M_A, "fixed": True}, {SC.FINDING_KEY_FIELD: M_B, "fixed": False}]
E       AssertionError: assert [{'findingKey...fixed': True}] == [{'findingKey...ixed': False}]
E         At index 1 diff: {'findingKey': 'mem-b', 'fixed': True} != {'findingKey': 'mem-b', 'fixed': False}
/home/user/wt-2489-wo3/plugins/superheroes/lib/tests/test_merged_member_loop_2489.py:160: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merged_member_loop_2489.py::test_edge2_a_member_answered_not_fixed_is_reopened_and_never_reads_fixed
1 failed, 18 deselected in 1.83s
```
(Elided: the `tmp_path` line, the `Use -v to get more diff` line.)

**restore:** inverse Edit. **restore receipt:** Grep after the restore for `NEUTRALIZED|member_results.setdefault` printed only
`9665:            member_results.setdefault(tid, []).append({session_contract.FINDING_KEY_FIELD: key, "fixed": fixed})`; the diff stat printed nothing.
(A first Edit with a mistyped `old_string` was refused with "String to replace not found" and changed nothing.)

**raw green** (same selector):
```
.                                                                        [100%]
1 passed, 18 deselected in 1.55s
```

## E3 — the end-of-loop settle of a member under a fixed representative with no ruling

**neutralization** (`round_driver.py:3164`): `if not (isinstance(rep, dict) and rep.get("disposition") == "fixed"` → `if True or not (isinstance(rep, dict) and rep.get("disposition") == "fixed"  # E3 NEUTRALIZED`. Every merged row is skipped again, the plain `mergedInto` skip.

**raw red** (`-k test_edge9_the_settle_leaves_open`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_edge9_the_settle_leaves_open_a_member_under_a_fixed_representative_with_no_ruling_of_its_own _
        RD._settle_open_findings(state, cap=True)
        opened = _ledger(state, M_A)
>       assert opened["disposition"] == "left-for-owner" and opened.get(SC.OPEN_AT_LOOP_END_FIELD) is True, opened
               ^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'disposition'
/home/user/wt-2489-wo3/plugins/superheroes/lib/tests/test_merged_member_loop_2489.py:288: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merged_member_loop_2489.py::test_edge9_the_settle_leaves_open_a_member_under_a_fixed_representative_with_no_ruling_of_its_own
1 failed, 18 deselected in 1.50s
```
(Elided: the test's source lines above the `>` line and the `tmp_path` line.)

**restore:** inverse Edit. **restore receipt:** Grep after the restore for `NEUTRALIZED|if not \(isinstance\(rep, dict\)` printed only `3164:            if not (isinstance(rep, dict) and rep.get("disposition") == "fixed"`; the diff stat printed nothing.

**raw green** (same selector):
```
.                                                                        [100%]
1 passed, 18 deselected in 1.46s
```

## E4 — `mergedMembers` on the target

**neutralization** (`round_driver.py:9410`): `if merged_members.get(tid):` → `if False and merged_members.get(tid):  # E4 NEUTRALIZED`.

**raw red** (`-k test_the_target_lists_every_finding_merged_into_it`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_the_target_lists_every_finding_merged_into_it_sorted_by_id_with_its_content _
        [target] = _targets(world)
>       assert [m["id"] for m in target["mergedMembers"]] == [M_A, M_B, M_C]
                                 ^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'mergedMembers'
/home/user/wt-2489-wo3/plugins/superheroes/lib/tests/test_merged_member_loop_2489.py:119: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_merged_member_loop_2489.py::test_the_target_lists_every_finding_merged_into_it_sorted_by_id_with_its_content
1 failed, 18 deselected in 1.83s
```
(Elided: the test's source lines above the `>` line and the `tmp_path` line.)

**restore:** inverse Edit. **restore receipt:** Grep after the restore for `NEUTRALIZED|if merged_members.get\(tid\)` printed only `9410:        if merged_members.get(tid):`; the diff stat printed nothing.

**raw green** (same selector):
```
.                                                                        [100%]
1 passed, 18 deselected in 1.69s
```

## E5 — unmerging a link of a merge chain re-points the findings merged into it (review round 1 fix)

- **Guarded element:** `round_driver._unmerge_finding`, the re-pointing branch (`if _nonempty_str(into) and into != key:`). **Axis:** a finding merged into a reopened (or settled) member keeps its chain to the representative its own audit answer is stored on.
- **Neutralization:** `if _nonempty_str(into) and into != key:` → `if False and _nonempty_str(into) and into != key:` (one targeted edit, the builder's own, through the host edit action).
- **Raw red:** `pytest plugins/superheroes/lib/tests/test_merged_member_loop_2489.py -q -p no:cacheprovider -k test_reopening_the_middle_of_a_merge_chain` →
  ```
  /home/user/wt-2489/plugins/superheroes/lib/tests/test_merged_member_loop_2489.py:201: AssertionError
  FAILED plugins/superheroes/lib/tests/test_merged_member_loop_2489.py::test_reopening_the_middle_of_a_merge_chain_keeps_a_fixed_leaf_on_the_representative
  1 failed, 19 deselected in 1.43s
  ```
- **Restore:** the inverse edit (`if False and ` removed). **Restore receipt:** the line reads `    if _nonempty_str(into) and into != key:` again; `git diff --stat` then showed only the fix and its test (round_driver.py 16 +/-, the test file 14 +).
- **Raw green:** the same command → `1 passed, 19 deselected in 4.66s`.

## Not neutralized

The `membersReopened` round record and the `merged-member-reopened` decision are written in the reopen branch E1 skips. The unit tests assert both, but neither write was neutralized on its own, so neither is proven by a run of its own.
