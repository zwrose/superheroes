# C3-A bite-proof — findings outside the PR go to the record's "Outside this PR" list

**Provenance:** claude / sonnet-5.5 (implementer). Detector file: `plugins/superheroes/lib/tests/test_c3_outside_findings.py`.
Every red below is the single named node run alone (`scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest "<node>" -q --tb=short`),
the detector unedited. Each neutralization is one targeted Edit, restored by the inverse Edit; the restore receipt is
the restored lines quoted back plus a `grep -n "NEUTRALIZED" plugins/superheroes/lib/*.py` that printed nothing.
Captures are far under the 32 KiB / 128 KiB ceilings; nothing was redacted (no credential-like text appears).
The pytest `UV_NATIVE_TLS` deprecation warning line that opens every run is dropped from the captures below.

## Guarded elements

| ID | Guarded element | Axis | Detector |
|---|---|---|---|
| BP1 | `round_driver._record_outside` | an outside row never reaches `compileDrops` (so never `refused`) or the account's findings | `test_t1_…` |
| BP2 | `diff_scope.parse_touched_lines` context branch | a context line is not touched | `test_t2_…` |
| BP3 | `diff_scope.parse_touched_lines` `close_run` | the head line just after a deletion run is touched | `test_t3_…` |
| BP4 | `_record_outside` append | no cap: every raised hit is kept | `test_t4_…` |
| BP5 | `_record_outside` sweep exclusion | a sweep entry is never a target and never counted to a reviewer | `test_t5_…` |
| BP6 | `_record_outside` dedupe | a re-fold never doubles a hit | `test_t6_…` |
| BP7 | `mechanical_compile` source choice | attribution comes from the driver's seat map, never the finding's own `dimension` | `test_t7_a_panel_finding_…` |
| BP8 | `_settle_extra_audit` partition | an outside new issue never holds the extra round open | `test_t8_…outside…` |
| BP9 | `review_record_session._unfolded` skip | an abandoned session does not re-list an outside hit as open | `test_t9_…` |

Supplementary (not in the declared set): BP3b, the head line just BEFORE a deletion run (`if have_prev:`), proven too.

## BP1

**neutralization** (`round_driver.py`, `_record_outside`): inserted `return list(drops or [])  # BP1 NEUTRALIZED` directly after `rest = []`.

**raw red** (`test_t1_an_important_finding_on_a_file_the_diff_does_not_touch_is_outside_the_pr`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t1_an_important_finding_on_a_file_the_diff_does_not_touch_is_outside_the_pr _
/home/user/wt-2219-a/plugins/superheroes/lib/tests/test_c3_outside_findings.py:106: in test_t1_an_important_finding_on_a_file_the_diff_does_not_touch_is_outside_the_pr
    assert state["outsideThisPR"] == [{
           ^^^^^^^^^^^^^^^^^^^^^^
E   KeyError: 'outsideThisPR'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c3_outside_findings.py::test_t1_an_important_finding_on_a_file_the_diff_does_not_touch_is_outside_the_pr
1 failed in 0.58s
```
**restore:** deleted the inserted line. **restore receipt:** quoted back — `    rest = []` then `    for drop in drops or []:`.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.57s
```

## BP2

**neutralization** (`diff_scope.py`, `parse_touched_lines`, the `elif line.startswith(" "):` branch): after `close_run()` inserted `touched[current_file].add(new_line)  # BP2 NEUTRALIZED`.

**raw red** (`test_t2_a_finding_on_a_context_line_of_a_changed_file_is_outside`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_t2_a_finding_on_a_context_line_of_a_changed_file_is_outside _______
/home/user/wt-2219-a/plugins/superheroes/lib/tests/test_c3_outside_findings.py:136: in test_t2_a_finding_on_a_context_line_of_a_changed_file_is_outside
    assert _hits(state) == [("code-reviewer", [
E   AssertionError: assert [] == [('code-revie...dded line')])]
E     
E     Right contains one more item: ('code-reviewer', [('O-1', 'src/a.py', 1, 'On a context line'), ('O-2', 'src/a.py', 4, 'Context after the run'), ('O-3', 'src/a.py', 20, 'Context after an added line')])
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c3_outside_findings.py::test_t2_a_finding_on_a_context_line_of_a_changed_file_is_outside
1 failed in 0.47s
```
**restore:** deleted the inserted line. **restore receipt:** quoted back — `                close_run()` then `                new_line += 1` then `                have_prev = True`.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.43s
```

## BP3

**neutralization** (`diff_scope.py`, `close_run`): replaced `touched[current_file].add(new_line)` with `pass  # BP3 NEUTRALIZED`.

**raw red** (`test_t3_added_and_deletion_adjacent_lines_stay_in_the_review`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_t3_added_and_deletion_adjacent_lines_stay_in_the_review _________
/home/user/wt-2219-a/plugins/superheroes/lib/tests/test_c3_outside_findings.py:154: in test_t3_added_and_deletion_adjacent_lines_stay_in_the_review
    assert sorted(f["title"] for f in state["_toVerify"]) == [
E   AssertionError: assert ['Just before...n added line'] == ['Just after ...n added line']
E     
E     At index 0 diff: 'Just before the deletion' != 'Just after the deletion'
E     Right contains one more item: 'On an added line'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c3_outside_findings.py::test_t3_added_and_deletion_adjacent_lines_stay_in_the_review
1 failed in 0.50s
```
**restore:** replaced `pass  # BP3 NEUTRALIZED` with `touched[current_file].add(new_line)`. **restore receipt:** quoted back — inside `close_run`: `if in_run and current_file is not None and new_line is not None:` then `            touched[current_file].add(new_line)`.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.45s
```

### BP3b (supplementary) — the line before a deletion run

**neutralization:** `if have_prev:` → `if False:  # BP3b NEUTRALIZED`.

**raw red** (same node):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_t3_added_and_deletion_adjacent_lines_stay_in_the_review _________
/home/user/wt-2219-a/plugins/superheroes/lib/tests/test_c3_outside_findings.py:154: in test_t3_added_and_deletion_adjacent_lines_stay_in_the_review
    assert sorted(f["title"] for f in state["_toVerify"]) == [
E   AssertionError: assert ['Just after ...n added line'] == ['Just after ...n added line']
E     
E     At index 1 diff: 'On an added line' != 'Just before the deletion'
E     Right contains one more item: 'On an added line'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c3_outside_findings.py::test_t3_added_and_deletion_adjacent_lines_stay_in_the_review
1 failed in 0.67s
```
**restore:** `if False:  # BP3b NEUTRALIZED` → `if have_prev:`. **restore receipt:** quoted back — `                    if have_prev:` followed by `                        touched[current_file].add(new_line - 1)`.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.64s
```

## BP4

**neutralization** (`round_driver.py`, `_record_outside`): before `target["hits"].append(hit)` inserted `if len(target["hits"]) >= 3:  # BP4 NEUTRALIZED` / `continue`.

**raw red** (`test_t4_five_outside_findings_from_one_seat_are_all_kept_under_one_entry`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_t4_five_outside_findings_from_one_seat_are_all_kept_under_one_entry ___
/home/user/wt-2219-a/plugins/superheroes/lib/tests/test_c3_outside_findings.py:166: in test_t4_five_outside_findings_from_one_seat_are_all_kept_under_one_entry
    assert _hits(state) == [("code-reviewer", [("O-%d" % n, "src/other.py", n, "Outside %d" % n) for n in range(1, 6)])]
E   AssertionError: assert [('code-revie...Outside 3')])] == [('code-revie...Outside 5')])]
E     
E     At index 0 diff: ('code-reviewer', [('O-1', 'src/other.py', 1, 'Outside 1'), ('O-2', 'src/other.py', 2, 'Outside 2'), ('O-3', 'src/other.py', 3, 'Outside 3')]) != ('code-reviewer', [('O-1', 'src/other.py', 1, 'Outside 1'), ('O-2', 'src/other.py', 2, 'Outside 2'), ('O-3', 'src/other.py', 3, 'Outside 3'), ('O-4', 'src/other.py', 4, 'Outside 4'), ('O-5', 'src/other.py', 5, 'Outside 5')])
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c3_outside_findings.py::test_t4_five_outside_findings_from_one_seat_are_all_kept_under_one_entry
1 failed in 0.52s
```
**restore:** deleted the two inserted lines. **restore receipt:** quoted back — `                continue` (the dedupe's) then `            target["hits"].append(hit)`; the grep for `NEUTRALIZED` printed nothing.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.57s
```

## BP5

**Note — the code was shaped so the exclusion is the real guard.** The target test is `src.get("name") == name` AFTER the
`if src.get("kind") == "sweep": continue` line; it deliberately does not re-check `kind == "reviewer"`. A first draft
re-checked the kind, which would have made the exclusion line redundant (unprovable as placed); no run was made of that draft.
The fixture gives the sweep entry the same name as the reviewer (`test-role`) so the exclusion is what discriminates.

**neutralization** (`round_driver.py`, `_record_outside`): deleted the two lines `if src.get("kind") == "sweep":` / `continue`.

**raw red** (`test_t5_a_sweep_entry_is_never_merged_into_or_counted_against_a_reviewer`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_t5_a_sweep_entry_is_never_merged_into_or_counted_against_a_reviewer ___
/home/user/wt-2219-a/plugins/superheroes/lib/tests/test_c3_outside_findings.py:181: in test_t5_a_sweep_entry_is_never_merged_into_or_counted_against_a_reviewer
    first, second = state["outsideThisPR"]
    ^^^^^^^^^^^^^
E   ValueError: not enough values to unpack (expected 2, got 1)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c3_outside_findings.py::test_t5_a_sweep_entry_is_never_merged_into_or_counted_against_a_reviewer
1 failed in 0.51s
```
**restore:** re-inserted the two lines. **restore receipt:** quoted back from `grep -n` after the restore:
```
863-            src = entry.get("source") if isinstance(entry.get("source"), dict) else {}
864-            # axis: a sweep entry is never the target of a reviewer's hit and never counted to one, even when it shares the name — see bite-proof record c3_wo_a_outside
865:            if src.get("kind") == "sweep":
866-                continue
867-            if src.get("name") == name and target is None:
868-                target = entry
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.56s
```

## BP6

**neutralization** (`round_driver.py`, `_record_outside`): `if any(` → `if False and any(` (with `# BP6 NEUTRALIZED`).

**raw red** (`test_t6_folding_the_same_outside_drops_twice_leaves_one_hit_each`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_t6_folding_the_same_outside_drops_twice_leaves_one_hit_each _______
/home/user/wt-2219-a/plugins/superheroes/lib/tests/test_c3_outside_findings.py:198: in test_t6_folding_the_same_outside_drops_twice_leaves_one_hit_each
    assert _hits(state) == [("code-reviewer", [("O-1", "a.py", 1, "one"), ("O-2", "a.py", 2, "two")])]
E   AssertionError: assert [('code-revie..., 2, 'two')])] == [('code-revie..., 2, 'two')])]
E     
E     At index 0 diff: ('code-reviewer', [('O-1', 'a.py', 1, 'one'), ('O-2', 'a.py', 2, 'two'), ('O-3', 'a.py', 1, 'one'), ('O-4', 'a.py', 2, 'two')]) != ('code-reviewer', [('O-1', 'a.py', 1, 'one'), ('O-2', 'a.py', 2, 'two')])
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c3_outside_findings.py::test_t6_folding_the_same_outside_drops_twice_leaves_one_hit_each
1 failed in 0.43s
```
**restore:** inverse edit. **restore receipt:** quoted back — `            if any(isinstance(h, dict) and (h.get("file"), h.get("line"), h.get("title"))`.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.43s
```

## BP7

**neutralization** (`round_driver.py`, `mechanical_compile`): the drop row's source became `f.get("dimension") or sources.get(id(f)) or source or OUTSIDE_SOURCE_DEFAULT  # BP7 NEUTRALIZED`.

**raw red** (`test_t7_a_panel_finding_is_attributed_to_the_seat_that_returned_it_not_to_its_own_dimension`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t7_a_panel_finding_is_attributed_to_the_seat_that_returned_it_not_to_its_own_dimension _
/home/user/wt-2219-a/plugins/superheroes/lib/tests/test_c3_outside_findings.py:217: in test_t7_a_panel_finding_is_attributed_to_the_seat_that_returned_it_not_to_its_own_dimension
    assert _hits(state) == [("code-reviewer", [("O-1", "src/other.py", 1, "Labelled as another lens")])]
E   AssertionError: assert [('security-r...ther lens')])] == [('code-revie...ther lens')])]
E     
E     At index 0 diff: ('security-reviewer', [('O-1', 'src/other.py', 1, 'Labelled as another lens')]) != ('code-reviewer', [('O-1', 'src/other.py', 1, 'Labelled as another lens')])
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c3_outside_findings.py::test_t7_a_panel_finding_is_attributed_to_the_seat_that_returned_it_not_to_its_own_dimension
1 failed in 0.57s
```
**restore:** inverse edit. **restore receipt:** quoted back — `"source": sources.get(id(f)) or source or OUTSIDE_SOURCE_DEFAULT})`.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.63s
```

## BP8

**neutralization** (`round_driver.py`, `_settle_extra_audit`): replaced `new_issues = _route_outside_new_issues(state, new_issues)` with `pass  # BP8 NEUTRALIZED`.

**raw red** (`test_t8_an_extra_audit_new_issue_outside_the_pr_does_not_hand_the_pr_back`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_t8_an_extra_audit_new_issue_outside_the_pr_does_not_hand_the_pr_back ___
/home/user/wt-2219-a/plugins/superheroes/lib/tests/test_c3_outside_findings.py:269: in test_t8_an_extra_audit_new_issue_outside_the_pr_does_not_hand_the_pr_back
    assert calls == ["converged"]
E   AssertionError: assert [] == ['converged']
E     
E     Right contains one more item: 'converged'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c3_outside_findings.py::test_t8_an_extra_audit_new_issue_outside_the_pr_does_not_hand_the_pr_back
1 failed in 1.43s
```
**restore:** inverse edit. **restore receipt:** quoted back — `    new_issues = _route_outside_new_issues(state, new_issues)` followed by `    if open_ids is None or open_ids or new_issues:`.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.51s
```

## BP9

**neutralization** (`review_record_session.py`, `_unfolded`): `if (f["title"], …) in outside_keys:` → `if False and (f["title"], …) in outside_keys:  # BP9 NEUTRALIZED`.

**raw red** (`test_t9_an_abandoned_session_does_not_list_a_finding_on_the_outside_list_as_open`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t9_an_abandoned_session_does_not_list_a_finding_on_the_outside_list_as_open _
/home/user/wt-2219-a/plugins/superheroes/lib/tests/test_c3_outside_findings.py:311: in test_t9_an_abandoned_session_does_not_list_a_finding_on_the_outside_list_as_open
    assert account["findings"] == [] and account["refused"] == []
E   AssertionError: assert ([{'id': 'u.py...ortant', ...}] == []
E     
E     Left contains one more item: {'id': 'u.py::unfolded defect@L8', 'findingKey': 'u.py::unfolded defect@L8', 'title': 'Unfolded defect', 'severity': 'Important', ...}
E     Use -v to get more diff)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c3_outside_findings.py::test_t9_an_abandoned_session_does_not_list_a_finding_on_the_outside_list_as_open
1 failed in 0.45s
```
**restore:** inverse edit. **restore receipt:** quoted back — `            if (f["title"], _file_key(f.get("file")), _line_key(f.get("line"))) in outside_keys:`.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.47s
```

## Not guarded by a neutralization of its own

The parser's `touched` guard for the PR-body citation / `scope_exempt` / no-diff / unreadable-line edges (E1, E2) and the fail-closed
non-list replacement (E4) are covered by tests E1-E5 and P1-P4 in the same file but carry no separate neutralization here;
they are not in the declared guarded-element set.
