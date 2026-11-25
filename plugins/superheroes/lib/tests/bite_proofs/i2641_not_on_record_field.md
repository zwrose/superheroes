# Bite-proof record: i2641_not_on_record_field

Detector: the not-on-record field the record writer carries instead of reason text, in
`plugins/superheroes/lib/review_record.py` (`NOT_ON_RECORD_FIELD`, `shown_reason`, `_leads_with_citation`,
`_recheck_decisions`, `_drop_stale_open_marker`, the `_validate_findings` line), `plugins/superheroes/lib/finding_outcomes.py`
(`settle`) and `plugins/superheroes/lib/pr_sheet.py` (the listed-for-merge detail).

Guarding tests: `plugins/superheroes/lib/tests/test_review_record_not_on_record_2641.py` and
`plugins/superheroes/lib/tests/test_finding_outcomes_c7.py`. Each element below was neutralized by a targeted Edit (the
edit tool refuses an `old_string` that is not unique, which is the "occurs exactly once" check), its named test(s) were run
alone by exact node id (red), the line was restored by the inverse edit and read back from the file, and the same node(s)
were run again (green). Command for every run (the node ids are in each section):
`scripts/pinned-python -B -X pycache_prefix=/tmp/claude-2641-pyc -m pytest <file>::<node> [<file>::<node>] -q`

Raw captures are trimmed to the assertion line(s), the failing assertion's diff and the summary line; the
`UV_NATIVE_TLS` deprecation warning that opens each run and the pytest traceback framing (the test source echoed back,
the worktree path) are elided. Nothing in them is a secret, token, private URL or personal detail; the one URL in a
capture is the fixture link `https://github.com/o/r/...`.

Guarded-element set: (E-settle), (E-set), (E-clear), (E-demote), (E-shown), (E-sheet), (E-once), (E-once-B1), (E-drop),
(E-valid). No equivalence class is used; each element has its own neutralization and its own red.

Disclosure, (E-clear): the order named `test_n4_...` as the expected red, and as ported from the reference it stayed
green under the neutralization (`_drop_stale_open_marker`, (E-drop), also drops the field from a finding the re-check
promoted to ruling, so a record-level test cannot see the re-check's own removal). One assertion at the seam was added to
`test_n4_...` (it calls `_recheck_decisions` directly) so that it bites; both runs are below.

## (E-settle) `settle` appends no clause

- Guarded element and axis: `finding_outcomes.py` `settle`, the `result = {"outcome": left_for_owner, "reason": open_reason, ...}` line.
  Axis: a leftover's reason is the open reason, with no text about a cited decision that did not resolve.
- Neutralization: `result = {"outcome": left_for_owner, "reason": open_reason, "decidedBy": decided_by}` became
  `why = "; the cited decision is not on record: " + text if decided_by is not None else ""` followed by
  `result = {"outcome": left_for_owner, "reason": open_reason + why, "decidedBy": decided_by}` (the base append, re-added).
- Guarding tests: `test_review_record_not_on_record_2641.py::test_n1_settle_writes_no_text_about_the_citation_and_the_resolving_record_reads_clean`
  and `test_finding_outcomes_c7.py::test_e7_unresolved_decided_by_stays_with_owner_with_no_text_about_the_citation`.
- Raw red:

```
>       assert got["reason"] == OPEN and got["decidedBy"] == BY and got["outcome"] == "left-for-owner"
E       AssertionError: assert ('waits for th...is repository' == 'waits for the owner'
E         - waits for the owner
E         + waits for the owner; the cited decision is not on record: the ruling's link is not in this repository)
>       assert out["reason"] == OPEN  # the record writer re-checks the citation and records a failure in a field
E       AssertionError: assert 'the loop end...not on record' == 'the loop end... finding open'
E         - the loop ended with the finding open
E         + the loop ended with the finding open; the cited decision is not on record: the cited Canon entry is not on record
FAILED plugins/superheroes/lib/tests/test_review_record_not_on_record_2641.py::test_n1_settle_writes_no_text_about_the_citation_and_the_resolving_record_reads_clean
FAILED plugins/superheroes/lib/tests/test_finding_outcomes_c7.py::test_e7_unresolved_decided_by_stays_with_owner_with_no_text_about_the_citation
2 failed in 0.66s
```

- Restore: inverse edit, the two neutralized lines back to the one `result = ...` line.
- Restore receipt (the restored line, read back from the file, `finding_outcomes.py:472`):

```
    result = {"outcome": left_for_owner, "reason": open_reason, "decidedBy": decided_by}
```

- Raw green:

```
..                                                                       [100%]
2 passed in 0.63s
```

## (E-set) the field is set on a leftover whose citation fails

- Guarded element and axis: `review_record.py` `_recheck_decisions`, the `failed = text` line of the `elif outcome == _LEFT_FOR_OWNER and not ok:` branch.
  Axis: a leftover whose cited decision does not resolve says so in a field, never in its reason.
- Neutralization: `failed = text` became `failed = None` (that branch).
- Guarding test: `test_review_record_not_on_record_2641.py::test_n2_an_unreadable_comment_sets_the_field_and_leaves_the_reason_for_shown_reason_to_extend`.
- Raw red:

```
>       assert f["outcome"] == "left-for-owner" and f["reason"] == OPEN and f[FIELD] == L3
E       KeyError: 'decisionNotOnRecord'
FAILED plugins/superheroes/lib/tests/test_review_record_not_on_record_2641.py::test_n2_an_unreadable_comment_sets_the_field_and_leaves_the_reason_for_shown_reason_to_extend
1 failed in 1.07s
```

- Restore: inverse edit, `failed = None` back to `failed = text`.
- Restore receipt (read back from the file, `review_record.py:2146`):

```
                failed = text
```

- Raw green:

```
.                                                                        [100%]
1 passed in 0.62s
```

## (E-clear) the field is removed when the citation resolves

- Guarded element and axis: `review_record.py` `_recheck_decisions`, the `if NOT_ON_RECORD_FIELD in f:` removal.
  Axis: only a finding that ends left-for-owner with a cited decision that did not resolve carries the field, so the writer leaves every other one without it.
- Neutralization: `if NOT_ON_RECORD_FIELD in f:` became `if False:`.
- Guarding test: `test_review_record_not_on_record_2641.py::test_n4_a_carried_field_goes_when_the_citation_now_resolves`.
- Run 1, `test_n4_...` as ported from the reference, under the neutralization, stayed green (it does not bite; see the disclosure above):

```
.                                                                        [100%]
1 passed in 0.56s
```

- Run 2, raw red, `test_n4_...` with the added seam assertion (`(rechecked,), _ = rr._recheck_decisions([copy.deepcopy(carried)], lambda: RESOLVES)`):

```
>       assert rechecked["outcome"] == "ruling" and FIELD not in rechecked
E       AssertionError: assert ('ruling' == 'ruling'
E           ruling and 'decisionNotOnRecord' not in {'id': 'f-1', 'title': 'Unchecked index', 'severity': 'Important', 'file': 'a.py', ...})
FAILED plugins/superheroes/lib/tests/test_review_record_not_on_record_2641.py::test_n4_a_carried_field_goes_when_the_citation_now_resolves
1 failed in 0.74s
```

- Restore: inverse edit, `if False:` back to `if NOT_ON_RECORD_FIELD in f:`.
- Restore receipt (read back from the file, `review_record.py:2148`):

```
        if NOT_ON_RECORD_FIELD in f:
```

- Raw green:

```
.                                                                        [100%]
1 passed in 0.65s
```

## (E-demote) demotion keeps the reason

- Guarded element and axis: `review_record.py` `_recheck_decisions`, the `out.append(dict(f, outcome=new))` line of the demotion path.
  Axis: a demoted ruling keeps its reason exactly as it was; the failure rides the field.
- Neutralization: before `out.append(dict(f, outcome=new))` was inserted `if new == _LEFT_FOR_OWNER:` /
  `f = dict(f, reason=f"{why}; {reason}" if reason else reason)`, where `why` is `_DEMOTED_CLAUSE % text` on that path
  (the demoted reason prefixed with `_DEMOTED_CLAUSE % text + "; "`).
- Guarding test: `test_review_record_not_on_record_2641.py::test_n3_a_demoted_ruling_keeps_its_reason_and_the_recovered_one_keeps_its_citation_once`.
- Raw red:

```
>       assert demoted["outcome"] == "left-for-owner" and demoted["reason"] == f"{CITE}; the owner said so" and demoted[FIELD] == L3
E       - owner ruling "ship it as is" (https://github.com/o/r/issues/12#issuecomment-555); the owner said so
E       + the cited decision is not on record (the ruling's comment could not be read); owner ruling "ship it as is" (https://github.com/o/r/issues/12#issuecomment-555); the owner said so)
FAILED plugins/superheroes/lib/tests/test_review_record_not_on_record_2641.py::test_n3_a_demoted_ruling_keeps_its_reason_and_the_recovered_one_keeps_its_citation_once
1 failed in 0.67s
```

- Restore: inverse edit, the two inserted lines removed.
- Restore receipt (read back from the file, `review_record.py:2165-2166`; the inserted `if new == _LEFT_FOR_OWNER` no longer occurs):

```
        # axis: a demoted ruling keeps its reason exactly as it was; the failure rides the field — see bite-proof record i2641_not_on_record_field (E-demote)
        out.append(dict(f, outcome=new))
```

- Raw green:

```
.                                                                        [100%]
1 passed in 0.60s
```

## (E-shown) `shown_reason` appends the clause

- Guarded element and axis: `review_record.py` `shown_reason`, its final `return`.
  Axis: the owner's text is the reason followed by the clause the field builds, or the clause alone when there is no reason.
- Neutralization: `return f"{reason}; {clause}" if isinstance(reason, str) and reason else clause` became `return reason`.
- Guarding test: `test_review_record_not_on_record_2641.py::test_n2_shown_reason_is_the_reason_unless_the_field_says_otherwise_and_never_raises`.
- Raw red:

```
>           assert rr.shown_reason(f) == f"{OPEN}; the {label} it cites is not on record ({L3})"
E           AssertionError: assert 'waits for the owner' == 'waits for th... not be read)'
E             - waits for the owner; the owner ruling it cites is not on record (the ruling's comment could not be read)
E             + waits for the owner
FAILED plugins/superheroes/lib/tests/test_review_record_not_on_record_2641.py::test_n2_shown_reason_is_the_reason_unless_the_field_says_otherwise_and_never_raises
1 failed in 0.58s
```

- Restore: inverse edit, `return reason` back to the clause-appending return (the edit that first tried it was refused for
  matching two lines; it was redone with the axis comment above the line as context).
- Restore receipt (read back from the file, `review_record.py:2098`):

```
    return f"{reason}; {clause}" if isinstance(reason, str) and reason else clause
```

- Raw green:

```
.                                                                        [100%]
1 passed in 0.59s
```

## (E-sheet) the listed detail reads `shown_reason`

- Guarded element and axis: `pr_sheet.py`, `reason = review_record.shown_reason(f)` in the listed-for-merge branch.
  Axis: the listed detail shows the failure the finding's field carries.
- Neutralization: `reason = review_record.shown_reason(f)` became `reason = f.get("reason")`.
- Guarding tests: `test_review_record_not_on_record_2641.py::test_n2_the_sheet_lists_a_merge_listed_finding_with_the_text_shown_reason_builds`
  and `test_review_record_not_on_record_2641.py::test_the_sheet_lists_a_merge_listed_finding_with_an_empty_reason_by_the_failure_alone` (the B3 test).
- Raw red:

```
>       assert listed["detail"] == "Minor: " + rr.shown_reason(f) and L3 in listed["detail"]
E       - Minor: waits for the owner; the owner ruling it cites is not on record (the ruling's comment could not be read)
E       + Minor: waits for the owner)
>       assert listed["detail"] == "Minor: the owner ruling it cites is not on record (" + L3 + ")"
E       - Minor: the owner ruling it cites is not on record (the ruling's comment could not be read)
E       + Minor: open when the review ended, outside every risk area
FAILED plugins/superheroes/lib/tests/test_review_record_not_on_record_2641.py::test_n2_the_sheet_lists_a_merge_listed_finding_with_the_text_shown_reason_builds
FAILED plugins/superheroes/lib/tests/test_review_record_not_on_record_2641.py::test_the_sheet_lists_a_merge_listed_finding_with_an_empty_reason_by_the_failure_alone
2 failed in 0.67s
```

- Restore: inverse edit, `reason = f.get("reason")` back to `reason = review_record.shown_reason(f)`.
- Restore receipt (read back from the file, `pr_sheet.py:1734`):

```
                reason = review_record.shown_reason(f)
```

- Raw green:

```
..                                                                       [100%]
2 passed in 0.62s
```

## (E-once) promotion does not prepend a citation the reason already leads with

- Guarded element and axis: `review_record.py` `_recheck_decisions`, `lead_again = _leads_with_citation(reason, why)`.
  Axis: a promoted reason that already leads with its citation (a ruling demoted and then resolved again) is not given it twice.
- Neutralization: `lead_again = _leads_with_citation(reason, why)` became `lead_again = False`.
- Guarding tests: `test_review_record_not_on_record_2641.py::test_recovered_carried_ruling_keeps_its_citation_once` (the
  citation-only-carry test) and `test_review_record_not_on_record_2641.py::test_recovered_carried_ruling_kept_open_by_a_check_keeps_its_citation_once_and_the_check_note` (the B1 test).
- Raw red:

```
>       assert recovered["reason"] == expected
E         - mment-555) (carried from the earlier review record)
E         + mment-555); owner ruling "ship it as is" (https://github.com/o/r/issues/12#issuecomment-555) (carried from the earlier review record)
>       assert recovered["reason"] == citation + rs.CARRIED + "; " + note
E         - mment-555) (carried from the earlier review record); a check on no named commit kept it for the owner: the check found it still applies: still reads past the end
E         + mment-555); owner ruling "ship it as is" (https://github.com/o/r/issues/12#issuecomment-555) (carried from the earlier review record); a check on no named commit kept it for the owner: the check found it still applies: still reads past the end
FAILED plugins/superheroes/lib/tests/test_review_record_not_on_record_2641.py::test_recovered_carried_ruling_keeps_its_citation_once
FAILED plugins/superheroes/lib/tests/test_review_record_not_on_record_2641.py::test_recovered_carried_ruling_kept_open_by_a_check_keeps_its_citation_once_and_the_check_note
2 failed in 0.86s
```

- Restore: inverse edit, `lead_again = False` back to `lead_again = _leads_with_citation(reason, why)`.
- Restore receipt (read back from the file, `review_record.py:2163`):

```
            lead_again = _leads_with_citation(reason, why)
```

- Raw green:

```
..                                                                       [100%]
2 passed in 0.60s
```

## (E-once-B1) the carried-then-continued shape

- Guarded element and axis: `review_record.py` `_leads_with_citation`, the `rest.startswith(CARRIED + "; ")` acceptance.
  Axis: a reason carried and then continued by a carried check's note ("; " after the carried suffix) already leads with its citation.
- Neutralization: only the new acceptance was removed: `if rest in ("", CARRIED) or rest.startswith("; ") or rest.startswith(CARRIED + "; "):`
  became `if rest in ("", CARRIED) or rest.startswith("; "):`.
- Guarding test: `test_review_record_not_on_record_2641.py::test_recovered_carried_ruling_kept_open_by_a_check_keeps_its_citation_once_and_the_check_note` (the B1 test).
- Raw red:

```
>       assert recovered["reason"] == citation + rs.CARRIED + "; " + note
E         - mment-555) (carried from the earlier review record); a check on no named commit kept it for the owner: the check found it still applies: still reads past the end
E         + mment-555); owner ruling "ship it as is" (https://github.com/o/r/issues/12#issuecomment-555) (carried from the earlier review record); a check on no named commit kept it for the owner: the check found it still applies: still reads past the end
FAILED plugins/superheroes/lib/tests/test_review_record_not_on_record_2641.py::test_recovered_carried_ruling_kept_open_by_a_check_keeps_its_citation_once_and_the_check_note
1 failed in 0.62s
```

- Restore: inverse edit, the third alternative put back.
- Restore receipt (read back from the file, `review_record.py:2112`):

```
    if rest in ("", CARRIED) or rest.startswith("; ") or rest.startswith(CARRIED + "; "):
```

- Raw green:

```
.                                                                        [100%]
1 passed in 0.57s
```

## (E-drop) `_drop_stale_open_marker` drops the field from a non-leftover

- Guarded element and axis: `review_record.py` `_drop_stale_open_marker`, the `unrecorded = ...` line.
  Axis: the field stays only while the outcome is left-for-owner.
- Neutralization: `unrecorded = NOT_ON_RECORD_FIELD in f and f.get("outcome") != _LEFT_FOR_OWNER` became `unrecorded = False`.
- Guarding test: `test_review_record_not_on_record_2641.py::test_n11_the_field_never_outlives_a_left_for_owner_outcome`.
- Raw red:

```
>           assert FIELD not in got and got["outcome"] == outcome, outcome
E           AssertionError: fixed
E           assert ('decisionNotOnRecord' not in {'id': 'f-1', 'title': 'Unchecked index', 'severity': 'Important', 'file': 'a.py', ...})
FAILED plugins/superheroes/lib/tests/test_review_record_not_on_record_2641.py::test_n11_the_field_never_outlives_a_left_for_owner_outcome
1 failed in 0.68s
```

- Restore: inverse edit, `unrecorded = False` back to the full condition.
- Restore receipt (read back from the file, `review_record.py:2184`):

```
        unrecorded = NOT_ON_RECORD_FIELD in f and f.get("outcome") != _LEFT_FOR_OWNER
```

- Raw green:

```
.                                                                        [100%]
1 passed in 0.60s
```

## (E-valid) the validator refuses a non-string or blank field

- Guarded element and axis: `review_record.py` `_validate_findings`, the `chk(NOT_ON_RECORD_FIELD not in f or (...), ...)` condition.
  Axis: the not-on-record failure text, when a finding carries it, is a non-blank string and never another type.
- Neutralization: the condition `NOT_ON_RECORD_FIELD not in f or (isinstance(f[NOT_ON_RECORD_FIELD], str) and f[NOT_ON_RECORD_FIELD].strip() != "")` became `True`.
- Guarding test: `test_review_record_not_on_record_2641.py::test_n5_a_field_that_is_not_a_non_blank_string_refuses_the_account`
  (one function; its five parameters `empty`, `blank`, `not-text`, `null`, `list` run as one node group).
- Raw red:

```
>       with pytest.raises(rr.Refusal) as refused:
E       Failed: DID NOT RAISE Refusal
FAILED ...::test_n5_a_field_that_is_not_a_non_blank_string_refuses_the_account[empty]
FAILED ...::test_n5_a_field_that_is_not_a_non_blank_string_refuses_the_account[blank]
FAILED ...::test_n5_a_field_that_is_not_a_non_blank_string_refuses_the_account[not-text]
FAILED ...::test_n5_a_field_that_is_not_a_non_blank_string_refuses_the_account[null]
FAILED ...::test_n5_a_field_that_is_not_a_non_blank_string_refuses_the_account[list]
5 failed in 0.70s
```

(The "DID NOT RAISE Refusal" line is shown once; it is the same in each of the five failures. The `...` stands for
`plugins/superheroes/lib/tests/test_review_record_not_on_record_2641.py`.)

- Restore: inverse edit, `True` back to the full condition.
- Restore receipt (read back from the file, `review_record.py:1069-1070`):

```
        chk(NOT_ON_RECORD_FIELD not in f or (isinstance(f[NOT_ON_RECORD_FIELD], str) and f[NOT_ON_RECORD_FIELD].strip() != ""),
            f"findings[{i}].{NOT_ON_RECORD_FIELD}")
```

- Raw green:

```
.....                                                                    [100%]
5 passed in 0.70s
```

## After all ten restores

`git status --porcelain -- plugins` (supplementary; it lists the paths this build touched, not a per-element receipt):

```
 M plugins/superheroes/lib/finding_outcomes.py
 M plugins/superheroes/lib/pr_sheet.py
 M plugins/superheroes/lib/review_record.py
 M plugins/superheroes/lib/tests/test_finding_outcomes_c7.py
 M plugins/superheroes/lib/tests/test_outcome_settle_c7.py
 M plugins/superheroes/lib/tests/test_review_record_fit_c7l3.py
 M plugins/superheroes/lib/tests/test_review_record_owner_ruling.py
 M plugins/superheroes/lib/tests/test_review_record_scope_bound_2532.py
 M plugins/superheroes/skills/review-code/reference/review-record.md
 M plugins/superheroes/skills/review-code/reference/round-driver.md
 M plugins/superheroes/skills/showrunner/reference/vet-receipt.md
?? plugins/superheroes/lib/tests/test_review_record_not_on_record_2641.py
```

The scoped suite after all restores: `576 passed in 13.93s`. No residue that could not be reverted.
