# C1-L11f (WO-A) bite-proof — an earlier record written with CI pending may also leave findings for the owner, and nothing else

**Provenance:** implementer WO-A (build #2279), recording the guards WO-A adds in `returning_review._ci_pending_only` (`plugins/superheroes/lib/returning_review.py`), proved by `plugins/superheroes/lib/tests/test_c1l11f_wo_a_returning.py`.

Declared guarded elements (from the order): A1-G1, the allowed-set membership test; A1-G2, the `left-for-owner` outcome check; A1-G3, the exactly-one-CI-line requirement under the new shape. The census (Grep, pattern `c1l11f_wo_a_returning`, over `plugins/superheroes/lib/returning_review.py`) shows two axis lines, both in `_ci_pending_only`:

```
plugins/superheroes/lib/returning_review.py:272:    # axis: a line beside the CI line is let through only when it is the writer's waits line for a finding of the record whose outcome is left-for-owner — see bite-proof record c1l11f_wo_a_returning
plugins/superheroes/lib/returning_review.py:277:    # axis: exactly one CI-pending line is required, beside owner-wait lines too — see bite-proof record c1l11f_wo_a_returning
```

Line 272 sits above the allowed set (G2's outcome condition, `returning_review.py:274`); the membership test (G1) is the `m in waits` leg at `returning_review.py:278`, under line 277's comment together with the CI-line count (G3, `sum(is_ci) == 1`, same line).

Each element was neutralized with one targeted Edit and restored with the inverse Edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from the worktree root under `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-a -m pytest "<node id>" -q -p no:cacheprovider --tb=short`. Captures: `--tb=short` shortens the traceback (the runner's own option), and the `UV_NATIVE_TLS` deprecation warning line is dropped from each; nothing else is filtered and nothing is redacted (no secret appears in these outputs). Every capture is far below 32 KiB.

| ID | Guarded element | Axis | Proving test (node id, in `plugins/superheroes/lib/tests/test_c1l11f_wo_a_returning.py`) |
|---|---|---|---|
| A1-G1 | `_ci_pending_only`, the allowed-set membership test `m in waits` (`returning_review.py:278`) | every line beside the one CI line is a left-for-owner finding's waits line, none of any other kind | `test_a1_a_line_of_any_other_kind_beside_the_ci_line_and_a_waits_line_reads_full` |
| A1-G2 | `_ci_pending_only`, the `left-for-owner` outcome condition of the allowed set (`returning_review.py:274`) | a waits line is let through only for a finding whose outcome is left-for-owner | `test_a1_a_waits_line_naming_a_finding_that_is_not_left_for_owner_reads_full` |
| A1-G3 | `_ci_pending_only`, the exactly-one-CI-line count `sum(is_ci) == 1` (`returning_review.py:278`) | exactly one CI-pending line is required, also beside owner-wait lines | `test_a1_waits_lines_without_a_ci_line_read_full` |

Every red is the runner's own failure of the unedited test, caused by the neutralization alone, and on the axis the element claims.

---

## A1-G1 — the allowed-set membership test

**axis:** every line beside the one CI line is a left-for-owner finding's waits line, none of any other kind.

**neutralization** (`returning_review.py:278`, one Edit: any non-CI line is allowed):
```python
-    return sum(is_ci) == 1 and all(ci_line or m in waits for m, ci_line in zip(missing, is_ci))
+    return sum(is_ci) == 1 and all(ci_line or True for m, ci_line in zip(missing, is_ci))
```

**raw red:** `... -m pytest "plugins/superheroes/lib/tests/test_c1l11f_wo_a_returning.py::test_a1_a_line_of_any_other_kind_beside_the_ci_line_and_a_waits_line_reads_full" -q -p no:cacheprovider --tb=short`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a1_a_line_of_any_other_kind_beside_the_ci_line_and_a_waits_line_reads_full _
/home/user/wt-2279-a/plugins/superheroes/lib/tests/test_c1l11f_wo_a_returning.py:83: in test_a1_a_line_of_any_other_kind_beside_the_ci_line_and_a_waits_line_reads_full
    assert got["read"] == "full" and TR.tokens(got) == [R.WHY_INCOMPLETE], (other, got)
E   AssertionError: ('no maker is named, so independence cannot be shown', {'read': 'changed', 'lastReviewed': '273b8194e5d56d3c990663117545f560d7a45ce7', 'countable': 5, 'bar': 1000, ...})
E   assert ('changed' == 'full'
E     
E     - full
E     + changed)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_a_returning.py::test_a1_a_line_of_any_other_kind_beside_the_ci_line_and_a_waits_line_reads_full
1 failed in 2.22s
```
The red is on the axis: with the membership test gone, a record whose other gap is "no maker is named, so independence cannot be shown" beside the CI line and a waits line is let through, CI reads green, and the decider reads `changed` where the test requires `full`.

**restore:** the inverse Edit.

**restore receipt** (the restored line, quoted from `returning_review.py:278` by Grep):
```
278:    return sum(is_ci) == 1 and all(ci_line or m in waits for m, ci_line in zip(missing, is_ci))
```

**raw green:** same command.
```
.                                                                        [100%]
1 passed in 2.04s
```

---

## A1-G2 — the `left-for-owner` outcome condition

**axis:** a waits line is let through only for a finding whose outcome is left-for-owner.

**neutralization** (`returning_review.py:274`, one Edit: the outcome condition dropped, so a waits line for a `fixed` finding is allowed):
```python
-             if isinstance(f, dict) and f.get("outcome") == review_findings_schema.LEFT_FOR_OWNER}
+             if isinstance(f, dict)}
```

**raw red:** `... -m pytest "plugins/superheroes/lib/tests/test_c1l11f_wo_a_returning.py::test_a1_a_waits_line_naming_a_finding_that_is_not_left_for_owner_reads_full" -q -p no:cacheprovider --tb=short`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a1_a_waits_line_naming_a_finding_that_is_not_left_for_owner_reads_full __
/home/user/wt-2279-a/plugins/superheroes/lib/tests/test_c1l11f_wo_a_returning.py:90: in test_a1_a_waits_line_naming_a_finding_that_is_not_left_for_owner_reads_full
    assert got["read"] == "full" and TR.tokens(got) == [R.WHY_INCOMPLETE], got
E   AssertionError: {'read': 'changed', 'lastReviewed': '51f24acf8f86b2f78d8ebd4f2502eb3e16875ebb', 'countable': 5, 'bar': 1000, ...}
E   assert ('changed' == 'full'
E     
E     - full
E     + changed)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_a_returning.py::test_a1_a_waits_line_naming_a_finding_that_is_not_left_for_owner_reads_full
1 failed in 1.66s
```
The red is on the axis: with the outcome condition gone, the waits line naming the `fixed` finding F-2 is allowed, and the decider reads `changed` where the test requires `full`.

**restore:** the inverse Edit.

**restore receipt** (the restored line, quoted from `returning_review.py:274` by Grep):
```
274:             if isinstance(f, dict) and f.get("outcome") == review_findings_schema.LEFT_FOR_OWNER}
```

**raw green:** same command.
```
.                                                                        [100%]
1 passed in 1.61s
```

---

## A1-G3 — the exactly-one-CI-line requirement

**axis:** exactly one CI-pending line is required, also beside owner-wait lines (zero CI lines with waits lines only reads full).

**neutralization** (`returning_review.py:278`, one Edit: zero CI lines accepted):
```python
-    return sum(is_ci) == 1 and all(ci_line or m in waits for m, ci_line in zip(missing, is_ci))
+    return sum(is_ci) <= 1 and all(ci_line or m in waits for m, ci_line in zip(missing, is_ci))
```

**raw red:** `... -m pytest "plugins/superheroes/lib/tests/test_c1l11f_wo_a_returning.py::test_a1_waits_lines_without_a_ci_line_read_full" -q -p no:cacheprovider --tb=short`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_a1_waits_lines_without_a_ci_line_read_full ________________
/home/user/wt-2279-a/plugins/superheroes/lib/tests/test_c1l11f_wo_a_returning.py:102: in test_a1_waits_lines_without_a_ci_line_read_full
    assert got["read"] == "full" and TR.tokens(got) == [R.WHY_INCOMPLETE], got
E   AssertionError: {'read': 'changed', 'lastReviewed': 'ae6107a37bdc3a635a8b306f383b5067a7ee5f70', 'countable': 5, 'bar': 1000, ...}
E   assert ('changed' == 'full'
E     
E     - full
E     + changed)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_a_returning.py::test_a1_waits_lines_without_a_ci_line_read_full
1 failed in 1.68s
```
The red is on the axis: with zero CI lines accepted, a record whose only gaps are two waits lines (and whose `ci` is pending on the last reviewed commit) is let through, and the decider reads `changed` where the test requires `full`. The `>= 2` side (two CI lines) is pinned by `test_a1_two_ci_lines_read_full` in the same file and was not neutralized separately.

**restore:** the inverse Edit.

**restore receipt** (the restored line, quoted from `returning_review.py:278` by Grep):
```
278:    return sum(is_ci) == 1 and all(ci_line or m in waits for m, ci_line in zip(missing, is_ci))
```

**raw green:** same command.
```
.                                                                        [100%]
1 passed in 1.66s
```
