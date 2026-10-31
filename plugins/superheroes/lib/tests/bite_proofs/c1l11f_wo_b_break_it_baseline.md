# C1-L11f (WO-B) bite-proof — the audit compares a break-it test with the reviewer's version up to body equivalence, a second test replaces the first as the baseline, a removal anchors inside its surviving PR hunk, and the audits submit guard is driven through a real session

**Provenance:** implementer WO-B (build #2279), recording the guards WO-B adds or changes in `lib/round_driver.py` (`_changed_why`, `_final_diff_files`, `_locate_in_final_diff`, `_break_it_target_facts`, `_fold_second_test`, `_removal_anchor`, `_fix_delta_groups`), proved by `lib/tests/test_c1l11f_wo_b_break_it_baseline.py` and by `lib/tests/test_c1l10_audit_checks.py::test_k1_the_submit_guard_refuses_a_result_missing_a_check_and_keeps_the_step_pending`.

Declared guarded elements (from the order): B-G1 the body-equivalence `same` leg; B-G2 the body-equivalence `changed-explained` leg; B-G3 the relocation leg; B-G4 the baseline-aware explanation lookup; B-G5 the second-test baseline reset; B-G6 the surviving-hunk anchor; B-G7 the submit guard for B4. Each was neutralized with one targeted Edit and restored with the inverse Edit; no `git checkout`, `restore`, `reset` or `stash` was used. Every run is `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-b -m pytest "<node id>" -q -p no:cacheprovider` from `/home/user/wt-2279-b`. Each capture is the runner's whole output for that run apart from the `UV_NATIVE` deprecation warning line (the first line of each real output), which is left out; nothing else is trimmed. Nothing is redacted: no secrets, tokens or URLs appear (the `/tmp/claude-0/...` paths are pytest temp directories). Every capture is under 32 KiB.

The axis comments at the guards (`grep -n "c1l11f_wo_b_break_it_baseline" plugins/superheroes/lib/round_driver.py`): `_changed_why` (7449, above the `start = max(...)` line), `_locate_in_final_diff` (7521), `_break_it_target_facts` (7558 and 7563), `_fold_second_test` (4291), `_removal_anchor` (7257) and `_fix_delta_groups` (7319). B-G7's guard (`audit_results_fault` at the audits branch of `cmd_submit`, `round_driver.py:11300`) is an existing guard, outside WO-B's function list, so its axis comment is in the rewritten test, which names this record.

| ID | Guarded element | Axis | Proving node |
|---|---|---|---|
| B-G1 | `round_driver._break_it_target_facts`, `hit = held_as(reviewer)` (7559) | the committed test is the reviewer's version up to formatting, title and relocation, not by exact bytes only | `test_b1_an_unchanged_reviewer_test_only_reformatted_is_same` |
| B-G2 | `_break_it_target_facts`, `hit = held_as(current) if why is not None else None` (7564) | the explained version matches up to the same equivalence | `test_b1_an_explained_correction_later_only_reformatted_is_changed_explained` |
| B-G3 | `_locate_in_final_diff`, the credit of a test found away from its path (7522) | a test relocated within the final diff is credited where `break_it_body.locate` finds it | `test_b1_an_explained_correction_later_only_relocated_is_changed_explained` |
| B-G4 | `_changed_why`, `start = max(...)` (7450) | an explanation counts only when recorded after the baseline (the second test's marked run) | `test_b3_an_explanation_older_than_the_baseline_never_explains_a_change` and `test_b3_the_rows_after_the_fold_hold_no_reviewer_baseline_of_the_first_test` |
| B-G5 | `_fold_second_test`, `copy_.pop(REVIEWER_TEST_FIELD, None)` (4292) | a second test resets the reviewer-test baseline (staged and ledger rows) | `test_b3_after_a_second_test_the_unchanged_second_test_reads_same` |
| B-G6 | `_removal_anchor`, `hunk = None if replaced_header else (...)` (7258) | a removal whose hunk header the group replaces anchors in the surviving hunk, not the preceding one | `test_b2_a_removal_that_trims_a_later_hunks_leading_context_anchors_in_that_hunk` |
| B-G7 | `cmd_submit`, `fault = audit_results_fault(artifact, state.get("_auditTargets") or [])` (11300) | a malformed-checks audits result is refused at submit with the pending step and state hash unchanged | `test_k1_the_submit_guard_refuses_a_result_missing_a_check_and_keeps_the_step_pending` (4 cases) |

Not separately neutralized (the unproven part of this record):

- The `_final_diff_files` collection (the `git diff --name-only`, `ls-tree`, `cat-file` reads and their None returns), `_locate_in_final_diff`'s input guard (a missing `baseRef`/`repoRoot`/`head`, a leading `-`) and its `files is None` return are pinned passing by the edge tests (`test_b1_a_committed_test_git_cannot_read_is_missing`, `test_b1_the_exact_bytes_stay_same_...`, `test_b1_a_test_found_twice_is_never_credited`, `test_b1_a_language_the_body_search_does_not_read_...`) but none was run under a neutralization: they are **unproven** here.
- The `committedPath` key a relocated hit adds, the `missing`/`changed-unexplained` choice on no hit, and `_fix_delta_groups`' drop of the removed lines of a hunk whose header nothing replaces (`test_b2_a_removal_with_no_surviving_line_in_its_hunk_is_marked_removal_only_never_borrowed`, and the first-hunk test `test_b2_the_earliest_removal_in_the_first_hunk_anchors_in_that_hunk`) are pinned passing, not neutralized.
- B-G4 is shown by two nodes that both go red; the order named test (v), "the unchanged second test reads `same`", for it, but that node cannot bite on B-G4 alone: with the old `reviewerTest` popped (B-G5 intact) the second test equals the carried block, so it reads `same` whatever the explanation lookup does. B-G4's bite is therefore shown on the two nodes above, which assert on `_changed_why` and on the facts of a row with an explanation older than the baseline.
- The red-at-base captures (the new tests run before any source change) were lost to a `| tail` filter on the first two runs and are not reproduced here; each guarded element's red below is the same test failing under the neutralization alone.

---

## B-G1 — the `same` leg

**axis:** the committed test is the reviewer's version up to formatting, title and relocation, not by exact bytes only.

**neutralization** (`round_driver.py:7559`, `_break_it_target_facts`: the reviewer's version matched by exact bytes only):
```python
-    hit = held_as(reviewer)
+    hit = (committed, path) if committed == reviewer else None
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_b1_an_unchanged_reviewer_test_only_reformatted_is_same __________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-71/test_b1_an_unchanged_reviewer_0')

    def test_b1_an_unchanged_reviewer_test_only_reformatted_is_same(tmp_path):
        # bites on: the body-equivalence `same` leg (B-G1)
        facts = _facts(tmp_path, {TEST_PATH: ROLE_TEST_REFORMATTED}, C10._finding())
>       assert facts["match"] == "same" and facts["committedTest"] == ROLE_TEST_REFORMATTED
E       AssertionError: assert ('changed-unexplained' == 'same'
E         
E         - same
E         + changed-unexplained)

/home/user/wt-2279-b/plugins/superheroes/lib/tests/test_c1l11f_wo_b_break_it_baseline.py:111: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_b_break_it_baseline.py::test_b1_an_unchanged_reviewer_test_only_reformatted_is_same
1 failed in 1.97s
```

**restore** (the inverse Edit):
```python
-    hit = (committed, path) if committed == reviewer else None
+    hit = held_as(reviewer)
```

**restore receipt** (the restored line quoted back by `grep -n "hit = held_as(reviewer)"`): `7559:    hit = held_as(reviewer)`

**raw green:**
```
.                                                                        [100%]
1 passed in 2.11s
```

---

## B-G2 — the `changed-explained` leg

**axis:** the explained version matches up to the same equivalence, and only with a reason recorded after the baseline.

**neutralization** (`round_driver.py:7564`, `_break_it_target_facts`: the explained version matched by exact bytes only):
```python
-        hit = held_as(current) if why is not None else None
+        hit = (committed, path) if why is not None and committed == current else None
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_b1_an_explained_correction_later_only_reformatted_is_changed_explained __

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-73/test_b1_an_explained_correctio0')

    def test_b1_an_explained_correction_later_only_reformatted_is_changed_explained(tmp_path):
        # bites on: the body-equivalence `changed-explained` leg (B-G2)
        facts = _facts(tmp_path, {TEST_PATH: FIXED_TEST_REFORMATTED}, _explained())
>       assert facts["match"] == "changed-explained" and facts["changedWhy"] == WHY
E       AssertionError: assert ('changed-unexplained' == 'changed-explained'
E         
E         - changed-explained
E         + changed-unexplained
E         ?         ++)

/home/user/wt-2279-b/plugins/superheroes/lib/tests/test_c1l11f_wo_b_break_it_baseline.py:97: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_b_break_it_baseline.py::test_b1_an_explained_correction_later_only_reformatted_is_changed_explained
1 failed in 2.48s
```

**restore** (the inverse Edit):
```python
-        hit = (committed, path) if why is not None and committed == current else None
+        hit = held_as(current) if why is not None else None
```

**restore receipt** (`grep -n "hit = held_as(current)"`): `7564:        hit = held_as(current) if why is not None else None`

**raw green:**
```
.                                                                        [100%]
1 passed in 1.85s
```

---

## B-G3 — the relocation leg

**axis:** a test relocated within the final diff is credited where `break_it_body.locate` finds it.

**neutralization** (`round_driver.py:7522`, `_locate_in_final_diff`: only a test found at its own path is credited):
```python
-    if found["status"] != "found" or not isinstance(files.get(found["path"]), str):
+    if found["status"] != "found" or found["path"] != path or not isinstance(files.get(found["path"]), str):
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_b1_an_explained_correction_later_only_relocated_is_changed_explained ___

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-75/test_b1_an_explained_correctio0')

    def test_b1_an_explained_correction_later_only_relocated_is_changed_explained(tmp_path):
        # bites on: the relocation leg (B-G3); the test is no longer at its path, it sits in another file of the diff
        facts = _facts(tmp_path, {OTHER_PATH: FIXED_TEST}, _explained())
>       assert facts["match"] == "changed-explained" and facts["changedWhy"] == WHY
E       AssertionError: assert ('missing' == 'changed-explained'
E         
E         - changed-explained
E         + missing)

/home/user/wt-2279-b/plugins/superheroes/lib/tests/test_c1l11f_wo_b_break_it_baseline.py:104: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_b_break_it_baseline.py::test_b1_an_explained_correction_later_only_relocated_is_changed_explained
1 failed in 1.87s
```

**restore** (the inverse Edit):
```python
-    if found["status"] != "found" or found["path"] != path or not isinstance(files.get(found["path"]), str):
+    if found["status"] != "found" or not isinstance(files.get(found["path"]), str):
```

**restore receipt** (`grep -n 'if found\["status"\] != "found"'`): `7522:    if found["status"] != "found" or not isinstance(files.get(found["path"]), str):`

**raw green:**
```
.                                                                        [100%]
1 passed in 1.89s
```

---

## B-G4 — the baseline-aware explanation lookup

**axis:** an explanation counts only when it was recorded after the baseline (the second test's marked run) was set.

**neutralization** (`round_driver.py:7450`, `_changed_why`: every run's `changedWhy` is read):
```python
-    start = max((i + 1 for i, run in enumerate(runs)
-                 if isinstance(run, dict) and run.get(SECOND_TEST_FIELD) is True), default=0)
+    start = 0
```

**raw red** (both proving nodes in one run):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
____ test_b3_an_explanation_older_than_the_baseline_never_explains_a_change ____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-77/test_b3_an_explanation_older_t0')

    def test_b3_an_explanation_older_than_the_baseline_never_explains_a_change(tmp_path):
        # bites on: the baseline-aware explanation lookup (B-G4): the reason was recorded before the second test's run
        # set the baseline, so a committed test that differs from the reviewer's version is a change nobody explained
        finding = C10._finding(content=FIXED_TEST, reviewer_test=ROLE_TEST, changed_why=WHY)
        older = _facts(tmp_path / "older", {TEST_PATH: FIXED_TEST}, finding)
        assert older["match"] == "changed-explained"
        finding[break_it.RUNS_FIELD].append({"test": TEST_PATH, "changedWhy": None, RD.SECOND_TEST_FIELD: True})
        after = _facts(tmp_path / "after", {TEST_PATH: FIXED_TEST}, finding)
>       assert after["match"] == "changed-unexplained" and after["changedWhy"] is None
E       AssertionError: assert ('changed-explained' == 'changed-unexplained'
E         
E         - changed-unexplained
E         ?         --
E         + changed-explained)

/home/user/wt-2279-b/plugins/superheroes/lib/tests/test_c1l11f_wo_b_break_it_baseline.py:282: AssertionError
_ test_b3_the_rows_after_the_fold_hold_no_reviewer_baseline_of_the_first_test __

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-77/test_b3_the_rows_after_the_fol0')

    def test_b3_the_rows_after_the_fold_hold_no_reviewer_baseline_of_the_first_test(tmp_path):
        # bites on: the second-test baseline reset (B-G5): neither the staged row nor the ledger row keeps the first
        # test as `reviewerTest`, and the run history stays whole, the second test's own run marking the baseline
        state, staged, ledger = _fold_second_test(tmp_path)
        for row in (staged, ledger):
            assert RD.REVIEWER_TEST_FIELD not in row
            assert [run["test"] for run in row[break_it.RUNS_FIELD]] == [
                ST.FIRST_PATH, ST.FIRST_PATH, ST.SECOND_PATH]
            assert [run.get("changedWhy") for run in row[break_it.RUNS_FIELD]] == [None, WHY, None]
>           assert RD._changed_why(row) is None
E           AssertionError: assert 'the first draft was missing an import' is None
E            +  where 'the first draft was missing an import' = <function _changed_why at 0x7f9c589b2980>({'classification': 'mechanical', 'consequence': 'a reviewer-found defect stays in the change', 'consequenceKind': None, 'dimension': 'test-role', ...})
E            +    where <function _changed_why at 0x7f9c589b2980> = RD._changed_why

/home/user/wt-2279-b/plugins/superheroes/lib/tests/test_c1l11f_wo_b_break_it_baseline.py:253: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_b_break_it_baseline.py::test_b3_an_explanation_older_than_the_baseline_never_explains_a_change
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_b_break_it_baseline.py::test_b3_the_rows_after_the_fold_hold_no_reviewer_baseline_of_the_first_test
2 failed in 3.80s
```

**restore** (the inverse Edit):
```python
-    start = 0
+    start = max((i + 1 for i, run in enumerate(runs)
+                 if isinstance(run, dict) and run.get(SECOND_TEST_FIELD) is True), default=0)
```

**restore receipt** (`grep -n "start = max((i + 1" -A1`):
```
7450:    start = max((i + 1 for i, run in enumerate(runs)
7451-                 if isinstance(run, dict) and run.get(SECOND_TEST_FIELD) is True), default=0)
```

**raw green:**
```
..                                                                       [100%]
2 passed in 3.56s
```

---

## B-G5 — the second-test baseline reset

**axis:** a second test resets the reviewer-test baseline: the staged row and the ledger row built from the copy hold no `reviewerTest` of the first test.

**neutralization** (`round_driver.py:4292`, `_fold_second_test`: the old `reviewerTest` is kept on the copy; the line removed):
```python
-            copy_.pop(REVIEWER_TEST_FIELD, None)
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_b3_after_a_second_test_the_unchanged_second_test_reads_same _______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-79/test_b3_after_a_second_test_th0')

    def test_b3_after_a_second_test_the_unchanged_second_test_reads_same(tmp_path):
        # bites on: the baseline-aware explanation lookup (B-G4) and the second-test baseline reset (B-G5)
        state, staged, ledger = _fold_second_test(tmp_path)
        assert staged["suggestion"] == ST._SECOND and ledger["suggestion"] == ST._SECOND
        config, head = _committed_second(tmp_path, _SECOND_CONTENT)
        for row in (staged, ledger):
            facts = RD._break_it_target_facts({}, config, row, head)
>           assert facts["match"] == "same", (row is staged, facts)
E           AssertionError: (True, {'path': 'tests/test_second_try.py', 'reviewerTest': "print('first try')
E             ", 'committedTest': "print('second try')
E             ", 'changedWhy': None, ...})
E           assert 'changed-unexplained' == 'same'
E             
E             - same
E             + changed-unexplained

/home/user/wt-2279-b/plugins/superheroes/lib/tests/test_c1l11f_wo_b_break_it_baseline.py:240: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_b_break_it_baseline.py::test_b3_after_a_second_test_the_unchanged_second_test_reads_same
1 failed in 3.61s
```

**restore** (the inverse Edit): the line `            copy_.pop(REVIEWER_TEST_FIELD, None)` put back above `second_runs = ...`.

**restore receipt** (`grep -n "copy_.pop(REVIEWER_TEST_FIELD, None)" -B1 -A2`):
```
4291-            # axis: the second test is the test role's latest version: the first test's reviewer baseline is dropped (the carried block is the baseline now) and the second test's own run marks where the first test's explanations stop counting — see bite-proof record c1l11f_wo_b_break_it_baseline
4292:            copy_.pop(REVIEWER_TEST_FIELD, None)
4293-            second_runs = [dict(r, **{SECOND_TEST_FIELD: True}) for r in copy_.get(break_it.RUNS_FIELD, [])
4294-                           if isinstance(r, dict)]
```

**raw green:**
```
.                                                                        [100%]
1 passed in 3.59s
```

---

## B-G6 — the surviving-hunk anchor

**axis:** a removed line whose hunk header the group replaces anchors in the surviving (following) hunk that header opens, never the preceding PR hunk.

**neutralization** (`round_driver.py:7258`, `_removal_anchor`: the hunk identity always from the preceding line):
```python
-    hunk = None if replaced_header else (behind[-1][0] if behind else None)
+    hunk = behind[-1][0] if behind else None
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_b2_a_removal_that_trims_a_later_hunks_leading_context_anchors_in_that_hunk _

    def test_b2_a_removal_that_trims_a_later_hunks_leading_context_anchors_in_that_hunk():
        # bites on: the surviving-hunk anchor (B-G6): the guard is removed from the SECOND PR hunk, whose header then
        # reads `@@ -100,7 +101,7 @@`; the removal anchors at head line 101, not on the first hunk's lines (10..13)
        reviewed = _diff(_EARLIER_HUNK, _GUARDED_TAIL.format(header="@@ -97,10 +98,11 @@"))
        head = _diff(_EARLIER_HUNK, _UNGUARDED_TAIL.format(start=101))
        entries = _surface(reviewed, head)
        assert entries and all(not e.get("removedOnly") for e in entries), entries
        starts = [e["start"] for e in entries]
>       assert min(starts) == 101 and all(start >= 100 for start in starts), entries
E       AssertionError: [{'start': 13, 'end': 13, 'text': '@@ -7,11 +7,7 @@
E           a11
E          +extra
E           a12
E         -@@ -97,10 +98,11 @@
E         - c97
E         - c98
E         - c99
E         -+guard
E         +@@ -100,7 +101,7 @@
E           c100
E           c101
E           c102'}]
E       assert (13 == 101)
E        +  where 13 = min([13])

/home/user/wt-2279-b/plugins/superheroes/lib/tests/test_c1l11f_wo_b_break_it_baseline.py:326: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_b_break_it_baseline.py::test_b2_a_removal_that_trims_a_later_hunks_leading_context_anchors_in_that_hunk
1 failed in 2.04s
```

**restore** (the inverse Edit):
```python
-    hunk = behind[-1][0] if behind else None
+    hunk = None if replaced_header else (behind[-1][0] if behind else None)
```

**restore receipt** (`grep -n "hunk = None if replaced_header"`): `7258:    hunk = None if replaced_header else (behind[-1][0] if behind else None)`

**raw green:**
```
.                                                                        [100%]
1 passed in 1.87s
```

---

## B-G7 — the audits submit guard (B4)

**axis:** an audits result missing a check is refused at submit, with the state hash and the pending phase/attempt unchanged; the corrected checks are accepted on the same attempt and hash.

**neutralization** (`round_driver.py:11300`, `cmd_submit`'s audits branch: the shape check never runs):
```python
-        fault = audit_results_fault(artifact, state.get("_auditTargets") or [])
+        fault = None
```

**raw red:**
```
FFFF                                                                     [100%]
=================================== FAILURES ===================================
_ test_k1_the_submit_guard_refuses_a_result_missing_a_check_and_keeps_the_step_pending[no-checks] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-84/test_k1_the_submit_guard_refus0')
ruling = 'discharged', checks = None

    @pytest.mark.parametrize("ruling,checks", [
        ("discharged", None),
        ("discharged", _without("testWouldFail")),
        ("discharged", _with("right", answer="perhaps")),
        ("not-discharged", None),
    ], ids=["no-checks", "one-check-missing", "unusable-answer", "not-discharged-no-checks"])
    def test_k1_the_submit_guard_refuses_a_result_missing_a_check_and_keeps_the_step_pending(
            tmp_path, ruling, checks):
        # axis: E1 at submit — a session at the audits step refuses the result through `cmd_submit`, names the check,
        # leaves the state hash and the pending phase/attempt as they were, and takes the corrected checks on the
        # same attempt and hash — see bite-proof record c1l11f_wo_b_break_it_baseline
        d, n = TRD._at(tmp_path, RD.P_AUDITS)
        bad, _targets = TRD._audit_artifact(n, ruling=ruling)
        if checks is None:
            del bad["results"][0]["checks"]
        else:
            bad["results"][0]["checks"] = checks
        good, _ = TRD._audit_artifact(n, ruling=ruling, checks=_checks(right="no") if ruling == "not-discharged"
                                      else _checks())
>       TRD._assert_shape_refused(d, n, bad, "audit-ruling-shape", ["results[0]", "checks"], good)

/home/user/wt-2279-b/plugins/superheroes/lib/tests/test_c1l10_audit_checks.py:204: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

d = '/tmp/claude-0/pytest-of-root/pytest-84/test_k1_the_submit_guard_refus0'
n = {'ok': True, 'action': 'dispatch-audits', 'round': 2, 'phase': 'dispatch-audits', ...}
artifact = {'results': [{'id': 'f.py::bug@L1', 'ruling': 'discharged', 'reason': 'r', 'evidence': 'e', ...}], 'collectionManifest': {'f.py::bug@L1': 'codex'}}
expected_outcome = 'audit-ruling-shape', must_name = ['results[0]', 'checks']
recovery = {'results': [{'id': 'f.py::bug@L1', 'ruling': 'discharged', 'reason': 'r', 'evidence': 'e', ...}], 'collectionManifest': {'f.py::bug@L1': 'codex'}}

    def _assert_shape_refused(d, n, artifact, expected_outcome, must_name, recovery):
        """The whole refusal contract in one place: refused with a shape-naming reason, state
        byte-identical, the pending step intact, a NON-terminal journal event, and the corrected
        artifact accepted on the same phase/attempt/state-hash."""
        before = _state_bytes(d)
        out = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], artifact)
>       assert out["ok"] is False, out
E       AssertionError: {'ok': True, 'round': 2, 'phase': 'dispatch-audits', 'nextStep': 'run-verify', ...}
E       assert True is False

/home/user/wt-2279-b/plugins/superheroes/lib/tests/test_round_driver.py:612: AssertionError
```
The other three cases (`one-check-missing`, `unusable-answer`, `not-discharged-no-checks`) failed identically at the same line (`test_round_driver.py:612`, `assert out["ok"] is False`, `out` = `{'ok': True, 'round': 2, 'phase': 'dispatch-audits', 'nextStep': 'run-verify', ...}`); their tracebacks, which repeat the one above with the case's own parameters, are elided here (about 9 KiB), and the summary line of the run was:
```
FAILED plugins/superheroes/lib/tests/test_c1l10_audit_checks.py::test_k1_the_submit_guard_refuses_a_result_missing_a_check_and_keeps_the_step_pending[no-checks]
FAILED plugins/superheroes/lib/tests/test_c1l10_audit_checks.py::test_k1_the_submit_guard_refuses_a_result_missing_a_check_and_keeps_the_step_pending[one-check-missing]
FAILED plugins/superheroes/lib/tests/test_c1l10_audit_checks.py::test_k1_the_submit_guard_refuses_a_result_missing_a_check_and_keeps_the_step_pending[unusable-answer]
FAILED plugins/superheroes/lib/tests/test_c1l10_audit_checks.py::test_k1_the_submit_guard_refuses_a_result_missing_a_check_and_keeps_the_step_pending[not-discharged-no-checks]
4 failed in 6.74s
```

**restore** (the inverse Edit):
```python
-        fault = None
+        fault = audit_results_fault(artifact, state.get("_auditTargets") or [])
```

**restore receipt** (`grep -n 'fault = audit_results_fault(artifact' -A1`):
```
11300:        fault = audit_results_fault(artifact, state.get("_auditTargets") or [])
11301-        if fault:
```

**raw green:**
```
....                                                                     [100%]
4 passed in 4.64s
```

---

# WO-G addendum (build #2279, C1-L11f seam fixes after the capped review)

**Provenance:** implementer WO-G, order id `wo-g`, in the worktree `/home/user/wt-2279`, head at dispatch `a722e5f5`. Two guards: G1-a in `_merged_removal_anchor` and G2-a in `_break_it_target_facts`, proved by `test_c1l11f_wo_b_break_it_baseline.py`. Each was neutralized with one targeted Edit and restored with the inverse Edit (no `git checkout`, `restore`, `reset` or `stash`). Every run is `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-g -m pytest "<node id>" -q -p no:cacheprovider`. Each capture is the runner's whole output apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out. Nothing is redacted: no secrets, tokens or URLs appear (the `/tmp/claude-0/...` paths are pytest temp directories). Every capture is under 32 KiB.

Supersession, disclosed: G2-a rewrote the classification in `_break_it_target_facts`, so the literal lines the B-G1 and B-G2 entries above neutralize (`hit = held_as(reviewer)`, `hit = held_as(current) if why is not None else None`) no longer exist. Their axes (the reviewer's version and the explained version match up to formatting, title and relocation; only a reason recorded after the baseline explains) are now carried by the `axis:` comments above `if copy is None:` and `elif run_copy and why is not None:` in `_break_it_target_facts`, and their nodes (`test_b1_an_unchanged_reviewer_test_only_reformatted_is_same`, `test_b1_an_explained_correction_later_only_reformatted_is_changed_explained`) pass on the new code; they were not re-neutralized: **unproven** at the new lines.

| ID | Guarded element | Axis | Proving node |
|---|---|---|---|
| G1-a | `_merged_removal_anchor`, `if behind and preceded:` (`round_driver.py:7334`) | when a body line of the merged hunk survived before a removed line, the removal anchors on that line whatever follows it (a header, the end of the section, or another hunk) | `test_b2_a_guard_removed_just_before_a_following_pr_hunk_anchors_on_the_line_before_it` |
| G2-a | `_break_it_target_facts`, `copy = held_as(current)` (`round_driver.py:7650`) | the audit resolves the copy `break_it.check_kept` will run (the latest run's test) first and classifies that one copy; a reviewer's copy elsewhere is never credited for a different test | `test_b1_a_relocated_explained_replacement_is_judged_before_a_reviewer_copy_elsewhere` |

## G1-a

**Red before the fix (labelled incomplete):** the new node was first run against the unchanged source as part of the whole file, with the output piped through `tail -40`, so only the last 40 lines survive; the summary line read `1 failed, 24 passed in 8.25s` and the failure was `AssertionError: [{'start': 14, 'end': 21, 'text': '@@ -2,26 +2,33 @@ ...` with `assert ([] or False)` (the same failure as the neutralized red below). The neutralized run below is the complete red output.

**Neutralization:** `    if behind and preceded:` became `    if behind and not ahead and preceded:` (the pre-fix condition).

**Raw red** (`test_b2_a_guard_removed_just_before_a_following_pr_hunk_anchors_on_the_line_before_it`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_b2_a_guard_removed_just_before_a_following_pr_hunk_anchors_on_the_line_before_it _

    def test_b2_a_guard_removed_just_before_a_following_pr_hunk_anchors_on_the_line_before_it():
        # bites on: the preceded-removal anchor (G1-a, round 8): the second guard is the merged hunk's last line and
        # another PR hunk follows it, whose header only renumbers; the removal still anchors on the surviving line
        # before it (head line 33, `c29`) or the surface carries the removal marker
        gap = "".join(" g%d\n" % n for n in range(13, 19))
        third = "@@ -100,7 +{start},8 @@\n c100\n c101\n c102\n+added\n c103\n c104\n c105\n c106\n"
        reviewed = _diff(
            _EARLIER_HUNK,
            "@@ -20,10 +21,12 @@\n c20\n c21\n c22\n+guard\n c23\n c24\n c25\n-old26\n+new26\n c27\n c28\n c29\n+guard2\n",
            third.format(start=103))
        head = _diff(
            "@@ -10,20 +10,24 @@\n a10\n a11\n+extra\n a12\n" + gap + "+bridge1\n g19\n"
            " c20\n c21\n c22\n c23\n+bridge2\n c24\n+bridge3\n c25\n-old26\n+new26\n c27\n c28\n c29\n",
            third.format(start=104))
        entries = _surface(reviewed, head)
        covered = [e for e in entries if not e.get("removedOnly") and e["start"] <= 33 <= e["end"]]
>       assert covered or any(e.get("removedOnly") for e in entries), entries
E       AssertionError: [{'start': 14, 'end': 21, 'text': '@@ -2,26 +2,33 @@
E          index 1..2 100644
E          --- a/f.py
E          +++ b/f.py
E         -@@ -10,3 +10,4 @@...n -old26
E          +new26
E           c27
E           c28
E           c29
E         -+guard2
E         -@@ -100,7 +103,8 @@
E         +@@ -100,7 +104,8 @@
E           c100
E           c101
E           c102'}]
E       assert ([] or False)
E        +  where False = any(<generator object test_b2_a_guard_removed_just_before_a_following_pr_hunk_anchors_on_the_line_before_it.<locals>.<genexpr> at 0x7fe657a006c0>)

/home/user/wt-2279/plugins/superheroes/lib/tests/test_c1l11f_wo_b_break_it_baseline.py:436: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_b_break_it_baseline.py::test_b2_a_guard_removed_just_before_a_following_pr_hunk_anchors_on_the_line_before_it
1 failed in 2.09s
```

**Restore** (the inverse Edit): `    if behind and not ahead and preceded:` back to `    if behind and preceded:`. **Restore receipt:** `grep -n "if behind and preceded" round_driver.py` prints `7334:    if behind and preceded:`.

**Raw green** (the same node):

```
.                                                                        [100%]
1 passed in 2.00s
```

## G2-a

**Red before the fix (stand-in, disclosed):** the fix to `_break_it_target_facts` was written before the new node, so the red below is not a run against the byte-unchanged source; it is the run against the fix with the pre-fix ordering reinstated (the reviewer's copy credited before the kept copy), which is the behaviour G2-a replaces.

**Neutralization:** `    copy = held_as(current)` became `    copy = held_as(reviewer) or held_as(current)`.

**Raw red** (`test_b1_a_relocated_explained_replacement_is_judged_before_a_reviewer_copy_elsewhere`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_b1_a_relocated_explained_replacement_is_judged_before_a_reviewer_copy_elsewhere _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-121/test_b1_a_relocated_explained_0')

    def test_b1_a_relocated_explained_replacement_is_judged_before_a_reviewer_copy_elsewhere(tmp_path):
        # bites on: the resolve-the-kept-copy-first step (G2-a): the recorded path is gone, the replacement the build
        # session explained sits at OTHER_PATH and the reviewer's original at a third file; the final kept check runs
        # the replacement (the latest run's content), so that is the copy the audit judges, never the original
        third = "tests/test_charge_original.py"
        facts = _facts(tmp_path, {OTHER_PATH: FIXED_TEST, third: ROLE_TEST}, _explained())
>       assert facts["match"] == "changed-explained", facts
E       AssertionError: {'path': 'tests/test_charge.py', 'reviewerTest': 'def test_charge():
E             assert charge(2) == 2
E         ', 'committedTest': 'def test_charge():
E             assert charge(2) == 2
E         ', 'changedWhy': 'the first draft was missing an import', ...}
E       assert 'same' == 'changed-explained'
E         
E         - changed-explained
E         + same

/home/user/wt-2279/plugins/superheroes/lib/tests/test_c1l11f_wo_b_break_it_baseline.py:165: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_b_break_it_baseline.py::test_b1_a_relocated_explained_replacement_is_judged_before_a_reviewer_copy_elsewhere
1 failed in 2.96s
```

**Restore** (the inverse Edit): `    copy = held_as(reviewer) or held_as(current)` back to `    copy = held_as(current)`. **Restore receipt:** `grep -n "copy = held_as(current)" round_driver.py` prints `7650:    copy = held_as(current)`.

**Raw green** (the same node):

```
.                                                                        [100%]
1 passed in 2.95s
```

Not separately neutralized (unproven): the `copy = committed, path` fallback when no copy of the latest run's test exists (pinned by `test_b1_a_real_content_change_of_the_reviewers_test_is_changed_unexplained`, and by `test_b1_a_relocated_replacement_with_no_reason_is_not_credited_as_the_reviewers_original` for the no-reason edge, passing); the `run_copy and current == reviewer` leg that keeps a relocated unchanged test `same`.

---

# C1-L12 addendum (build #2216, entries for C1-L11f's review-loop axis lines)

**Provenance:** implementer WO-4, order id `c1l12-wo4`, worktree `/home/user/wo4`, branch `c1l12-wo4`, head at dispatch `86e05768`. Each entry is **re-derived at `86e05768`** by this order: the fixers' own red/green lived in their review sessions' folders on a container that has been reclaimed, and PR #2283's review records and round comments carry no break-it red/green for these lines, so none is quoted. A1 was added by fixer commit `1dffc4fe`, A10 by `377b1f7d`. Each guarded element was neutralized with one targeted Edit and restored with the inverse Edit (no `git checkout`, `restore`, `reset` or `stash`); after each restore `git status --porcelain` listed no `.py` file outside `plugins/superheroes/lib/tests/`. Every run is `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/shpyc-wo4 -m pytest "<node id>" -q -p no:cacheprovider`. Each capture is the runner's whole output apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out. Nothing is redacted: no secrets, tokens or URLs appear (the `/tmp/claude-0/...` paths are pytest temp directories). Every capture is under 32 KiB. A9 (`93a8adb8`) has no line at the head: WO-G's rewrite of `_break_it_target_facts` (`49c0958b`) removed it, so this record gains nothing for it.

| ID | Guarded element | Axis (verbatim) | Proving node |
|---|---|---|---|
| A1 | `_locate_in_final_diff`, the condition `and not _retention_guards_hold(` (`round_driver.py:7595`) | a renamed or relocated test is credited only where break_it.check_kept would accept it (the same collection, option-token and direct-runner guards, and a mappable command), so the audit never reads `same` for a test the convergence check parks as binding-conflict — see bite-proof record c1l11f_wo_b_break_it_baseline | `test_b1_a_renamed_test_the_kept_check_would_park_is_not_credited_as_the_reviewers_original` (added by this order) |
| A10 | `_fix_delta_surface` removal-anchor walk, `if header_gone:` after the hunk loop (`round_driver.py:7410`) | removals waiting on a header nothing replaced anchor in the surviving hunk the PR hunks merged into — see bite-proof record c1l11f_wo_b_break_it_baseline | `test_b2_a_guard_removed_where_the_fix_merges_two_pr_hunks_anchors_in_the_merged_hunk` |

## A1

**Test added by this order:** `test_b1_a_renamed_test_the_kept_check_would_park_is_not_credited_as_the_reviewers_original` in `test_c1l11f_wo_b_break_it_baseline.py`: the reviewer's test is renamed in place (`test_charge` becomes `test_charge_twice`) in a repository whose `pytest.ini` sets `python_functions = check_*`, so `break_it.check_kept` would park it as binding-conflict; the audit must read `changed-unexplained`. The second assertion is the control: the same rename with no `pytest.ini` reads `same`.

**Neutralization:** `    if (found["titles"] or found["path"] != path) and not _retention_guards_hold(` became `    if (found["titles"] or found["path"] != path) and False and not _retention_guards_hold(` (the retention guards can never refuse).

**Raw red** (re-run in this dispatch; the first dispatch's red output is not available to this record, so this is the only red quoted):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_b1_a_renamed_test_the_kept_check_would_park_is_not_credited_as_the_reviewers_original _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-20/test_b1_a_renamed_test_the_kep0')

    def test_b1_a_renamed_test_the_kept_check_would_park_is_not_credited_as_the_reviewers_original(tmp_path):
        # bites on: the retention guards of `_locate_in_final_diff` (A1): the reviewer's test is renamed in place and the
        # repository declares a pytest collection override, so `break_it.check_kept` parks it as binding-conflict; the
        # audit never reads `same` for it (the control, with no override, reads `same`)
        renamed = ROLE_TEST.replace("test_charge", "test_charge_twice")
        override = {"pytest.ini": "[pytest]\npython_functions = check_*\n", TEST_PATH: renamed}
>       assert _facts(tmp_path / "a", override, C10._finding())["match"] == "changed-unexplained"
E       AssertionError: assert 'same' == 'changed-unexplained'
E         
E         - changed-unexplained
E         + same

/home/user/wo4/plugins/superheroes/lib/tests/test_c1l11f_wo_b_break_it_baseline.py:208: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_b_break_it_baseline.py::test_b1_a_renamed_test_the_kept_check_would_park_is_not_credited_as_the_reviewers_original
1 failed in 6.00s
```

The red is on the claimed axis: the failing assertion is the one that expects the kept check's refusal (`pytest.ini` override, renamed test) to keep the audit from reading `same`.

**Restore** (the inverse Edit): `and False and not _retention_guards_hold(` back to `and not _retention_guards_hold(`. **Restore receipt:** the line is back as `    if (found["titles"] or found["path"] != path) and not _retention_guards_hold(`, and `git status --porcelain` listed only the test files this order edits.

**Raw green** (the same node; both assertions run, so the control half, `same` with no override, passes here and not under the neutralization, where the run stops at the first assertion):

```
.                                                                        [100%]
1 passed in 3.46s
```

Not separately neutralized (unproven): the `found["titles"] or found["path"] != path` disjunct (a test found at its own path with its own title skips the guards) and the `_nonempty_str(command)` fail-closed branch of `_retention_guards_hold`.

## A10

**Neutralization:** `        if header_gone:` (the one before `head_lines.extend(_merged_removal_anchors(head_anchors, waiting_at))`) became `        if header_gone and False:`.

**Raw red** (`test_b2_a_guard_removed_where_the_fix_merges_two_pr_hunks_anchors_in_the_merged_hunk`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_b2_a_guard_removed_where_the_fix_merges_two_pr_hunks_anchors_in_the_merged_hunk _

    def test_b2_a_guard_removed_where_the_fix_merges_two_pr_hunks_anchors_in_the_merged_hunk():
        # bites on: the merged-hunk anchor (B-G7): the fix bridges the gap between two PR hunks, so the second header
        # vanishes with no header to replace it, and removes the guard from the surviving hunk; the removal anchors
        # on the surviving line after it (head line 25, `c23`) or the surface carries the removal marker
        gap = "".join(" g%d\n" % n for n in range(13, 19))
        reviewed = _diff(
            _EARLIER_HUNK,
            "@@ -20,10 +21,11 @@\n c20\n c21\n c22\n+guard\n c23\n c24\n c25\n-old26\n+new26\n c27\n c28\n c29\n")
        head = _diff(
            "@@ -10,20 +10,23 @@\n a10\n a11\n+extra\n a12\n" + gap + "+bridge1\n g19\n"
            " c20\n c21\n c22\n c23\n+bridge2\n c24\n c25\n-old26\n+new26\n c27\n c28\n c29\n")
        entries = _surface(reviewed, head)
        covered = [e for e in entries if not e.get("removedOnly") and e["start"] <= 25 <= e["end"]]
>       assert covered or any(e.get("removedOnly") for e in entries), entries
E       AssertionError: [{'start': 14, 'end': 21, 'text': '@@ -2,17 +2,24 @@
E          index 1..2 100644
E          --- a/f.py
E          +++ b/f.py
E         -@@ -10,3 +10,4 @@...n+ g15
E         + g16
E         + g17
E         + g18
E         ++bridge1
E         + g19
E           c20
E           c21
E           c22
E         -+guard
E           c23
E         ++bridge2
E           c24
E           c25
E          -old26'}]
E       assert ([] or False)
E        +  where False = any(<generator object test_b2_a_guard_removed_where_the_fix_merges_two_pr_hunks_anchors_in_the_merged_hunk.<locals>.<genexpr> at 0x7f4884240d40>)

/home/user/wo4/plugins/superheroes/lib/tests/test_c1l11f_wo_b_break_it_baseline.py:395: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_b_break_it_baseline.py::test_b2_a_guard_removed_where_the_fix_merges_two_pr_hunks_anchors_in_the_merged_hunk
1 failed in 1.80s
```

The red is on the claimed axis: the removed `+guard` line waits on a header nothing replaced, and with the end-of-section anchor gone no entry covers head line 25 and no `removedOnly` entry appears.

**Restore** (the inverse Edit): `        if header_gone and False:` back to `        if header_gone:`. **Restore receipt:** the line is back as `        if header_gone:` above `            head_lines.extend(_merged_removal_anchors(head_anchors, waiting_at))`, and `git status --porcelain` listed no `.py` file outside `plugins/superheroes/lib/tests/`.

**Raw green** (the same node):

```
.                                                                        [100%]
1 passed in 1.81s
```

Not separately neutralized (unproven): the in-loop `elif header_gone: survived = True` branch and the `waiting` accumulation that feeds `waiting_at`.
