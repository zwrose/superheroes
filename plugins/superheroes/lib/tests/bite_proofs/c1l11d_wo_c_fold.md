# C1-L11d (WO-C) bite-proof — the returning-review decider compares a file's own change, and counts an earlier record written with CI pending as finished only when CI has since passed

**Provenance:** implementer WO-C, recording the guards of WO-C on `lib/returning_review.py`, `lib/review_record.py` and `lib/round_driver.py`, proved by `lib/tests/test_c1l11d_fold_returning.py`

Declared guarded elements (from the order: the own-change comparison [C1]; the CI-state `"green"` test [C5]; the single-CI-line test [C6]; the head-route's `files == []` requirement [C4 negative]), enumerated here as G1 to G7 (the order's "at least" four, with the `"green"` test split into its two legs and three more guards added). The census (the Grep tool, pattern `c1l11d_wo_c_fold`, over `plugins/superheroes/lib/*.py`) printed these axis lines in the three source files (G1 at 342, G2 at 263, G2b and G4 at 267 and 268, G7 at 233, G3 at 324, G6 at 1506; the `review_record.py` axis comment for G5 was added after the runs below, above the guarded line):

```
plugins/superheroes/lib/round_driver.py:1506:        # axis: the driver hands the decider a CI reader, so an earlier record written with CI pending can count as finished — see bite-proof record c1l11d_wo_c_fold
plugins/superheroes/lib/returning_review.py:233:    # axis: only the writer's not-reviewed status, never abandoned, is let through unfinished — see bite-proof record c1l11d_wo_c_fold
plugins/superheroes/lib/returning_review.py:263:    # Axis: only CI "green" settles an earlier record written with CI pending; red, pending, unreadable and no reader do not — see bite-proof record c1l11d_wo_c_fold
plugins/superheroes/lib/returning_review.py:267:    # Axis: CI green on the head settles an earlier record only when the head has no changed file — see bite-proof record c1l11d_wo_c_fold
plugins/superheroes/lib/returning_review.py:324:        # Axis: an earlier record is let through unfinished only for CI pending on its final commit and nothing else — see bite-proof record c1l11d_wo_c_fold
plugins/superheroes/lib/returning_review.py:342:    # Axis: a file is changed when its own change differs, never for an index line or a hunk header's line numbers — see bite-proof record c1l11d_wo_c_fold
```

The line numbers named in the table and the neutralizations below are those of the tree at the time of each run (before the `review_record.py` axis comment was added, which moves G5's guarded line from 400 to 401). G7's guarded line was later rewritten to ask `review_record.unfinished` (an import and an axis comment were added above it), which moved every `returning_review.py` line cited below from G7 on down by two; those citations, and the `build_record` call's (now `review_record.py:1497`), are corrected to the current tree. G1 to G6 were not re-run after that move: their guarded lines are unchanged and only their positions moved. G7 alone was re-captured (see its section). Each element was neutralized with one targeted Edit and restored with the inverse Edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2273` (head `36a5fa11` plus this dispatch's uncommitted work) under `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2273 -m pytest "<node id>" -q -p no:cacheprovider`. Each capture is the runner's whole output for that run apart from the `UV_NATIVE_TLS` deprecation warning line (the first line of each real output), which is left out; nothing else is trimmed. Nothing is redacted: no secrets, tokens or URLs appear (the `/tmp/claude-0/...` paths are pytest temp directories). The restore receipt of each element is the restored line quoted back at the same line number.

Every red is the runner's own failure of the unedited test, caused by the neutralization alone, and on the axis the element claims.

| ID | Guarded element | Axis | Proving test (node id, in `plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py`) |
|---|---|---|---|
| G1 | `returning_review._decide`, the own-change comparison (`returning_review.py:344`) | a file is changed when its own change differs, never for an `index` line or hunk-header line numbers (C1) | `test_c1_a_catch_up_over_a_file_the_pr_also_changes_reads_no_changed_file` |
| G2 | `returning_review._ci_settled`, the last-reviewed-commit `"green"` test (`returning_review.py:264`) | only CI `"green"` settles an earlier record written with CI pending (C5) | `test_c5_a_ci_that_is_not_green_reads_full[red]` |
| G2b | `returning_review._ci_settled`, the head `"green"` test (`returning_review.py:270`) | the same, on the head route (C5) | `test_c5_a_ci_that_is_not_green_reads_full[red]` |
| G3 | `returning_review._ci_pending_only`, the single-line test (`returning_review.py:240`) | the earlier record's one gap is the one CI line (C6) | `test_c6_a_gap_other_than_ci_pending_on_the_final_commit_reads_full[second-line-after]` |
| G4 | `returning_review._ci_settled`, the head route's `files == []` requirement (`returning_review.py:268`) | CI green on the head settles an earlier record only when the head has no changed file (C4 negative) | `test_c4_ci_green_only_on_a_head_with_a_real_change_since_reads_full` |
| G5 | `review_record.carry_refusal`, the reader pass to the decider (`review_record.py:400`) | the carry check hands the decider the writer's CI reader, as a keyword, and only when it has one (C7) | `test_c7_the_carry_check_hands_the_decider_its_reader_only_when_it_has_one` |
| G6 | `round_driver._returning_overrides`, the reader pass to the decider (`round_driver.py:1507`) | the driver hands the decider the production CI reader whenever the repository root is known (C7) | `test_c7_the_driver_hands_the_decider_the_production_ci_reader` |
| G7 | `returning_review._ci_pending_only`, the `abandoned`-present test (`returning_review.py:234`, `if not review_record.unfinished(earlier.get("status")) or "abandoned" in earlier:`) | a record carrying `abandoned` (present, even empty) is never let through unfinished (C6) | `test_c6_a_gap_other_than_ci_pending_on_the_final_commit_reads_full[abandoned-present-but-empty]` |

Not separately neutralized (the unproven part of this record):

- G2 and G2b share one proving node, `[red]`; each neutralization alone turns it red (G2 by settling on the last reviewed commit, G2b by settling on the head after the last reviewed commit read `red`), so each leg is shown. The other `test_c5_*` cases (`pending`, `none`, `not-lowercase-green`, `none-answer`, `bool`, `int`, `raises`, the no-reader test and the real-change test) were not run under a neutralization: that a reader which raises, answers a non-string, or is absent reads full is pinned by those tests passing but not shown to bite here; `_ci_read`'s `callable` check, its `try`/`except` and its `isinstance(state, str)` test are **unproven** here.
- G3: the second-line case alone. The other `test_c6_*` cases (`ci.sha` another commit, the CI line naming another commit, the line not being the pending line, the line not a list, `ci` absent, `ci` not pending, status `None`, the status check) were not run under a neutralization: the `ci.get("sha") == last_reviewed` leg, the `ci.get("state") == "pending"` leg, the `startswith` line test and the `not review_record.unfinished(earlier.get("status"))` status test of `_ci_pending_only` are **unproven** here (`test_c6_an_unknown_status_with_the_ci_pending_gap_reads_full` and the `no-status` case pin the status test passing, but neither was run under a neutralization).
- G7: the line is now `if not review_record.unfinished(earlier.get("status")) or "abandoned" in earlier:` (`returning_review.py:234`); the neutralization drops only `or "abandoned" in earlier`. The truthy `abandoned` case reads `earlier-record-unusable` at step 1, which is earlier code; `test_c6_an_abandoned_record_reads_full_whatever_ci_says` pins that and is not a bite for G7.
- G5, G6: the neutralization removes the reader pass whole. The `build_record` call (`review_record.py:1497`) and the `_carry_review` call (`review_record_session.py:993`) pass a `lambda sha: _ci(...)["state"]`; no test in this order runs those two lambdas, so the lambdas' bodies and their being passed at those two call sites are **unproven** here (the existing `test_c1l11d_carried_review.py` doubles accept the keyword and were run green, but they do not read it).
- G1: the neutralization is the comparison reverted to raw section text. The helper `_own_change` itself is pinned by `test_c2_own_change_drops_only_index_lines_and_hunk_header_numbers` and the two C2 catch-up cases (own lines changed again; a base edit inside the hunk's context) but was not neutralized: its `index ` drop, its hunk-header rewrite and its keeping every other line (a hunk body line, context included) are **unproven** here as separate guards.
- `WHY_CI_SETTLED` text, the `production_ci_state` wrapper beyond its two tests, and the CLI's absent reader are not neutralized.

---

## G1 — the own-change comparison

**axis:** a file is changed when its own change differs, never for an `index` line or a hunk header's line numbers.

**neutralization** (`returning_review.py:344`, `_decide`: the comparison reverted to the raw section text):
```python
-                   if _own_change(reviewed.get(f, "")) != _own_change(current.get(f, "")))
+                   if reviewed.get(f, "") != current.get(f, ""))
```

**raw red:** `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2273 -m pytest "plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py::test_c1_a_catch_up_over_a_file_the_pr_also_changes_reads_no_changed_file" -q -p no:cacheprovider`
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_c1_a_catch_up_over_a_file_the_pr_also_changes_reads_no_changed_file ___

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-37/test_c1_a_catch_up_over_a_file0')

    def test_c1_a_catch_up_over_a_file_the_pr_also_changes_reads_no_changed_file(tmp_path):
        # axis: a file is changed when its own change differs, never for an index line or hunk-header line numbers — see bite-proof record c1l11d_wo_c_fold
        repo, moved, reviewed, earlier = _catch_up(tmp_path, _far_base_text())
        head = repo.git("rev-parse", "HEAD")
        raw_reviewed = R._sections_by_file(repo.git("diff", *R._DIFF_ARGS, "%s...%s" % (moved, reviewed)))[SHARED]
        raw_head = R._sections_by_file(repo.git("diff", *R._DIFF_ARGS, "%s...%s" % (moved, head)))[SHARED]
        # the fixture does move the header: the raw sections differ, their own change does not
        assert raw_reviewed != raw_head and "index " in raw_head and "@@ -" in raw_head
        assert R._own_change(raw_reviewed) == R._own_change(raw_head)
        got = TR.decide(repo, moved, earlier)
>       assert got["read"] == "changed" and got["changedFiles"] == [] and got["countable"] == 0, got
E       AssertionError: {'read': 'changed', 'lastReviewed': '7d531afa0200d3bf411cf2e8bd08246831b986dd', 'countable': 3, 'bar': 1000, ...}
E       assert ('changed' == 'changed'
E         
E           changed and ['src/shared.py'] == []
E         
E         Left contains one more item: 'src/shared.py'
E         Use -v to get more diff)

/home/user/wt-2273/plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py:111: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py::test_c1_a_catch_up_over_a_file_the_pr_also_changes_reads_no_changed_file
1 failed in 4.22s
```
The red is on the axis: the file reads changed and `countable` is 3 (the lower layer's three lines) where the test requires no changed file and 0.

**restore:** the inverse Edit.

**restore receipt** (`returning_review.py:344`):
```python
                   if _own_change(reviewed.get(f, "")) != _own_change(current.get(f, "")))
```

**raw green:** same command.
```
.                                                                        [100%]
1 passed in 3.09s
```

---

## G2 — the last-reviewed-commit `"green"` test

**axis:** only CI `"green"` settles an earlier record written with CI pending.

**neutralization** (`returning_review.py:264`, `_ci_settled`: any non-empty state settles):
```python
-    if state == _CI_GREEN:
+    if state:
```

**raw red:** `... -m pytest "plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py::test_c5_a_ci_that_is_not_green_reads_full[red]" -q -p no:cacheprovider`
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_c5_a_ci_that_is_not_green_reads_full[red] ________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-39/test_c5_a_ci_that_is_not_green0')
answer = 'red'

    @pytest.mark.parametrize("answer", ["red", "pending", "none", "GREEN", None, True, 1, _raises],
                             ids=["red", "pending", "none", "not-lowercase-green", "none-answer", "bool", "int", "raises"])
    def test_c5_a_ci_that_is_not_green_reads_full(tmp_path, answer):
        # axis: only CI "green" settles an earlier record written with CI pending; every other answer reads full — see bite-proof record c1l11d_wo_c_fold
        repo, moved, reviewed, earlier = _head_only(tmp_path)  # no changed file: both the commit and the head are asked
        reader = _raises if answer is _raises else (lambda sha: answer)
        got = TR.decide(repo, moved, _pending(reviewed), ci_state=reader)
>       assert got["read"] == "full" and TR.tokens(got) == [R.WHY_INCOMPLETE], got
E       AssertionError: {'read': 'changed', 'lastReviewed': '1f82a5a1ecfad3c782ccd2a22f7735197e47ac60', 'countable': 0, 'bar': 1000, ...}
E       assert ('changed' == 'full'
E         
E         - full
E         + changed)

/home/user/wt-2273/plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py:190: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py::test_c5_a_ci_that_is_not_green_reads_full[red]
1 failed in 6.48s
```

**restore:** the inverse Edit.

**restore receipt** (`returning_review.py:264`):
```python
    if state == _CI_GREEN:
```

**raw green:** same command.
```
.                                                                        [100%]
1 passed in 2.88s
```

---

## G2b — the head `"green"` test

**axis:** only CI `"green"` settles an earlier record written with CI pending, on the head route.

**neutralization** (`returning_review.py:270`, `_ci_settled`):
```python
-        if head_state == _CI_GREEN:
+        if head_state:
```

**raw red:** same node as G2.
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_c5_a_ci_that_is_not_green_reads_full[red] ________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-41/test_c5_a_ci_that_is_not_green0')
answer = 'red'

    @pytest.mark.parametrize("answer", ["red", "pending", "none", "GREEN", None, True, 1, _raises],
                             ids=["red", "pending", "none", "not-lowercase-green", "none-answer", "bool", "int", "raises"])
    def test_c5_a_ci_that_is_not_green_reads_full(tmp_path, answer):
        # axis: only CI "green" settles an earlier record written with CI pending; every other answer reads full — see bite-proof record c1l11d_wo_c_fold
        repo, moved, reviewed, earlier = _head_only(tmp_path)  # no changed file: both the commit and the head are asked
        reader = _raises if answer is _raises else (lambda sha: answer)
        got = TR.decide(repo, moved, _pending(reviewed), ci_state=reader)
>       assert got["read"] == "full" and TR.tokens(got) == [R.WHY_INCOMPLETE], got
E       AssertionError: {'read': 'changed', 'lastReviewed': '7d266331cc654e44204db0a93569ef1a56d7df5b', 'countable': 0, 'bar': 1000, ...}
E       assert ('changed' == 'full'
E         
E         - full
E         + changed)

/home/user/wt-2273/plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py:190: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py::test_c5_a_ci_that_is_not_green_reads_full[red]
1 failed in 2.32s
```

**restore:** the inverse Edit.

**restore receipt** (`returning_review.py:270`):
```python
        if head_state == _CI_GREEN:
```

**raw green:** same command.
```
.                                                                        [100%]
1 passed in 2.27s
```

---

## G3 — the single-CI-line test

**axis:** the earlier record's one gap is the one CI line; a second line is another gap.

**neutralization** (`returning_review.py:240`, `_ci_pending_only`: one line or more):
```python
-    if not (isinstance(missing, list) and len(missing) == 1 and isinstance(missing[0], str)):
+    if not (isinstance(missing, list) and len(missing) >= 1 and isinstance(missing[0], str)):
```

**raw red:** `... -m pytest "plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py::test_c6_a_gap_other_than_ci_pending_on_the_final_commit_reads_full[second-line-after]" -q -p no:cacheprovider`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_c6_a_gap_other_than_ci_pending_on_the_final_commit_reads_full[second-line-after] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-43/test_c6_a_gap_other_than_ci_pe0')
damage = <function <lambda> at 0x7fecf1979f80>

    @pytest.mark.parametrize("damage", [
        lambda sha: {"whatIsMissing": [_ci_line(sha), "no maker is named, so independence cannot be shown"]},
        lambda sha: {"whatIsMissing": ["no planned reviewer ran", _ci_line(sha)]},
        lambda sha: {"whatIsMissing": []},
        lambda sha: {"whatIsMissing": _ci_line(sha)},
        lambda sha: {"whatIsMissing": ["no planned reviewer ran"]},
        lambda sha: {"whatIsMissing": ["CI is pending on %s (1 check pending)" % ("0" * 7)]},
        lambda sha: {"whatIsMissing": ["CI is red on %s" % sha[:7]]},
        lambda sha: {"ci": {"state": "pending", "sha": "c" * 40}},
        lambda sha: {"ci": {"state": "green", "sha": sha}},
        lambda sha: {"ci": {"state": "red", "sha": sha}},
        lambda sha: {"ci": None},
        lambda sha: {"abandoned": {}},
        lambda sha: {"status": "reviewed", "abandoned": {}},
        lambda sha: {"status": None},
    ], ids=["second-line-after", "second-line-before", "no-line", "line-not-a-list", "another-gap", "ci-line-another-commit",
            "line-not-the-pending-line", "ci-sha-another-commit", "ci-green-in-record", "ci-red-in-record", "no-ci",
            "abandoned-present-but-empty", "reviewed-abandoned-present-but-empty", "no-status"])
    def test_c6_a_gap_other_than_ci_pending_on_the_final_commit_reads_full(tmp_path, damage):
        # axis: only a record whose one gap is CI pending on its final commit is let through unfinished — see bite-proof record c1l11d_wo_c_fold
        repo, base, reviewed, _ = _with_fix(tmp_path)
        record = {k: v for k, v in _pending(reviewed, **damage(reviewed)).items() if v is not None}
        reader = Reader({reviewed: "green", repo.git("rev-parse", "HEAD"): "green"})  # CI is green everywhere: only the record can fail
        got = TR.decide(repo, base, record, ci_state=reader)
>       assert got["read"] == "full" and TR.tokens(got) == [R.WHY_INCOMPLETE], got
E       AssertionError: {'read': 'changed', 'lastReviewed': '60d4d315940fbc84c72efcf73aecb18288aefc56', 'countable': 5, 'bar': 1000, ...}
E       assert ('changed' == 'full'
E         
E         - full
E         + changed)

/home/user/wt-2273/plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py:238: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py::test_c6_a_gap_other_than_ci_pending_on_the_final_commit_reads_full[second-line-after]
1 failed in 2.34s
```

**restore:** the inverse Edit.

**restore receipt** (`returning_review.py:240`):
```python
    if not (isinstance(missing, list) and len(missing) == 1 and isinstance(missing[0], str)):
```

**raw green:** same command.
```
.                                                                        [100%]
1 passed in 2.37s
```

---

## G4 — the head route's `files == []` requirement

**axis:** CI green on the head settles an earlier record only when the head has no changed file.

**neutralization** (`returning_review.py:268`, `_ci_settled`: the head route is always taken):
```python
-    if not files:
+    if True:
```

**raw red:** `... -m pytest "plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py::test_c4_ci_green_only_on_a_head_with_a_real_change_since_reads_full" -q -p no:cacheprovider`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_c4_ci_green_only_on_a_head_with_a_real_change_since_reads_full ______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-45/test_c4_ci_green_only_on_a_hea0')

    def test_c4_ci_green_only_on_a_head_with_a_real_change_since_reads_full(tmp_path):
        # axis: CI green on the head settles an earlier record only when the head has no changed file — see bite-proof record c1l11d_wo_c_fold
        repo, base, reviewed, earlier = _with_fix(tmp_path)
        head = repo.git("rev-parse", "HEAD")
        got = TR.decide(repo, base, _pending(reviewed), ci_state=Reader({reviewed: "pending", head: "green"}))
>       assert got["read"] == "full" and TR.tokens(got) == [R.WHY_INCOMPLETE], got
E       AssertionError: {'read': 'changed', 'lastReviewed': 'dde851842b50eb048fb25ec6bede9f83cbbbea55', 'countable': 5, 'bar': 1000, ...}
E       assert ('changed' == 'full'
E         
E         - full
E         + changed)

/home/user/wt-2273/plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py:173: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py::test_c4_ci_green_only_on_a_head_with_a_real_change_since_reads_full
1 failed in 2.48s
```

**restore:** the inverse Edit.

**restore receipt** (`returning_review.py:268`):
```python
    if not files:
```

**raw green:** same command.
```
.                                                                        [100%]
1 passed in 2.28s
```

---

## G5 — the carry check's reader pass

**axis:** the carry check hands the decider the writer's CI reader as a keyword, and only when it has one.

**neutralization** (`review_record.py:400`, `carry_refusal`: no reader ever passed):
```python
-        reader = {"ci_state": ci_state} if ci_state is not None else {}
+        reader = {}
```

**raw red:** `... -m pytest "plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py::test_c7_the_carry_check_hands_the_decider_its_reader_only_when_it_has_one" -q -p no:cacheprovider`
```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_c7_the_carry_check_hands_the_decider_its_reader_only_when_it_has_one ___

    def test_c7_the_carry_check_hands_the_decider_its_reader_only_when_it_has_one():
        # axis: the carry check passes the writer's CI reader to the decider as a keyword, and only when it has one — see bite-proof record c1l11d_wo_c_fold
        seen = []
    
        def decide(*args, **kwargs):
            seen.append(kwargs)
            return {"read": "full", "changedFiles": [], "why": []}
    
        def strict(repo_root, base, head, earlier, proven=()):
            return {"read": "full", "changedFiles": [], "why": []}
    
        prior, sha, reader = {"finalCommit": {"sha": "a" * 40}, "findings": []}, "a" * 40, (lambda s: "green")
        RR.carry_refusal(prior, sha, "/r", "b" * 40, "c" * 40, [], decide, reader)
        RR.carry_refusal(prior, sha, "/r", "b" * 40, "c" * 40, [], decide)
        assert RR.carry_refusal(prior, sha, "/r", "b" * 40, "c" * 40, [], strict).startswith("the earlier review does not stand")
>       assert seen[0]["ci_state"] is reader and "ci_state" not in seen[1]
               ^^^^^^^^^^^^^^^^^^^
E       KeyError: 'ci_state'

/home/user/wt-2273/plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py:304: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py::test_c7_the_carry_check_hands_the_decider_its_reader_only_when_it_has_one
1 failed in 2.04s
```

**restore:** the inverse Edit.

**restore receipt** (`review_record.py:400`):
```python
        reader = {"ci_state": ci_state} if ci_state is not None else {}
```

**raw green:** same command.
```
.                                                                        [100%]
1 passed in 2.30s
```

---

## G6 — the driver's reader pass

**axis:** the driver hands the decider the production CI reader whenever the repository root is known.

**neutralization** (`round_driver.py:1507`, `_returning_overrides`: no reader ever passed):
```python
-        reader = {"ci_state": returning_review.production_ci_state(repo_root)} if repo_root else {}
+        reader = {}
```

**raw red:** `... -m pytest "plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py::test_c7_the_driver_hands_the_decider_the_production_ci_reader" -q -p no:cacheprovider`
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_c7_the_driver_hands_the_decider_the_production_ci_reader _________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-49/test_c7_the_driver_hands_the_d0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fb8950e0e30>

    def test_c7_the_driver_hands_the_decider_the_production_ci_reader(tmp_path, monkeypatch):
        # axis: the driver passes the production CI reader to the decider whenever the repository root is known — see bite-proof record c1l11d_wo_c_fold
        s = TS.Session(tmp_path, monkeypatch, change=TS._append("src/shared.py", "extra = 1\n"))
        sentinel, roots = (lambda sha: "green"), []
        monkeypatch.setattr(TS.RD.returning_review, "production_ci_state", lambda root: roots.append(root) or sentinel)
        calls = _seam(monkeypatch)
        s.next()
        [(args, kwargs)] = calls
>       assert kwargs["ci_state"] is sentinel and roots == [s.repo.root] and args[0] == s.repo.root
               ^^^^^^^^^^^^^^^^^^
E       KeyError: 'ci_state'

/home/user/wt-2273/plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py:276: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py::test_c7_the_driver_hands_the_decider_the_production_ci_reader
1 failed in 2.97s
```

**restore:** the inverse Edit.

**restore receipt** (`round_driver.py:1507`):
```python
        reader = {"ci_state": returning_review.production_ci_state(repo_root)} if repo_root else {}
```

**raw green:** same command.
```
.                                                                        [100%]
1 passed in 2.89s
```

---

## G7 — the `abandoned`-present test

**axis:** a record carrying `abandoned` (present, even empty) is never let through unfinished.

**Re-captured after the line changed:** the captures below were taken again against the new line (`returning_review.py:234`, which asks `review_record.unfinished` instead of spelling the status) in `/home/user/wt-2273` on head `d82fe6ad` plus this dispatch's uncommitted work; the earlier captures, taken against `earlier.get("status") != "not-reviewed" or "abandoned" in earlier`, are replaced. Same command shape as the others, and the same `UV_NATIVE_TLS` warning line left out; nothing else trimmed or redacted.

**neutralization** (`returning_review.py:234`, `_ci_pending_only`: the `abandoned` test dropped, one Edit):
```python
-    if not review_record.unfinished(earlier.get("status")) or "abandoned" in earlier:
+    if not review_record.unfinished(earlier.get("status")):
```

**raw red:** `... -m pytest "plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py::test_c6_a_gap_other_than_ci_pending_on_the_final_commit_reads_full[abandoned-present-but-empty]" -q -p no:cacheprovider`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_c6_a_gap_other_than_ci_pending_on_the_final_commit_reads_full[abandoned-present-but-empty] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-55/test_c6_a_gap_other_than_ci_pe0')
damage = <function <lambda> at 0x7f148e5ea700>

    @pytest.mark.parametrize("damage", [
        lambda sha: {"whatIsMissing": [_ci_line(sha), "no maker is named, so independence cannot be shown"]},
        lambda sha: {"whatIsMissing": ["no planned reviewer ran", _ci_line(sha)]},
        lambda sha: {"whatIsMissing": []},
        lambda sha: {"whatIsMissing": _ci_line(sha)},
        lambda sha: {"whatIsMissing": ["no planned reviewer ran"]},
        lambda sha: {"whatIsMissing": ["CI is pending on %s (1 check pending)" % ("0" * 7)]},
        lambda sha: {"whatIsMissing": ["CI is red on %s" % sha[:7]]},
        lambda sha: {"ci": {"state": "pending", "sha": "c" * 40}},
        lambda sha: {"ci": {"state": "green", "sha": sha}},
        lambda sha: {"ci": {"state": "red", "sha": sha}},
        lambda sha: {"ci": None},
        lambda sha: {"abandoned": {}},
        lambda sha: {"status": "reviewed", "abandoned": {}},
        lambda sha: {"status": None},
    ], ids=["second-line-after", "second-line-before", "no-line", "line-not-a-list", "another-gap", "ci-line-another-commit",
            "line-not-the-pending-line", "ci-sha-another-commit", "ci-green-in-record", "ci-red-in-record", "no-ci",
            "abandoned-present-but-empty", "reviewed-abandoned-present-but-empty", "no-status"])
    def test_c6_a_gap_other_than_ci_pending_on_the_final_commit_reads_full(tmp_path, damage):
        # axis: only a record whose one gap is CI pending on its final commit is let through unfinished — see bite-proof record c1l11d_wo_c_fold
        repo, base, reviewed, _ = _with_fix(tmp_path)
        record = {k: v for k, v in _pending(reviewed, **damage(reviewed)).items() if v is not None}
        reader = Reader({reviewed: "green", repo.git("rev-parse", "HEAD"): "green"})  # CI is green everywhere: only the record can fail
        got = TR.decide(repo, base, record, ci_state=reader)
>       assert got["read"] == "full" and TR.tokens(got) == [R.WHY_INCOMPLETE], got
E       AssertionError: {'read': 'changed', 'lastReviewed': 'f1c7af302a7a7fdcc45bf06f335e1ce7c6a8f969', 'countable': 5, 'bar': 1000, ...}
E       assert ('changed' == 'full'
E         
E         - full
E         + changed)

/home/user/wt-2273/plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py:238: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py::test_c6_a_gap_other_than_ci_pending_on_the_final_commit_reads_full[abandoned-present-but-empty]
1 failed in 2.28s
```
The red is on the axis: with the `abandoned` test gone, the record carrying an empty `abandoned` is let through, CI reads green, and the decider reads `changed` where the test requires `full`.

**restore:** the inverse Edit.

**restore receipt** (`returning_review.py:234`):
```python
    if not review_record.unfinished(earlier.get("status")) or "abandoned" in earlier:
```

**raw green:** same command.
```
.                                                                        [100%]
1 passed in 3.08s
```

---

# Appended by C1-L11f (WO-A, build #2279, vet 737 item 1): entries for the guards whose axis comments cite this record and held none

These are proofs of existing guards: no lasting source change. Each element was neutralized with one targeted Edit and restored with the inverse Edit (no `git checkout`, `restore`, `reset` or `stash`). Run from the worktree root under `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-a -m pytest "<node id>" -q -p no:cacheprovider --tb=short`, on the tree at build base `4f350065` plus WO-A's `_ci_pending_only` change. `--tb=short` is the runner's own option; the `UV_NATIVE_TLS` deprecation warning line is dropped from each capture; nothing else is filtered and nothing is redacted (no secret appears). Line numbers are those of that tree. Elements: E1 (two pieces, E1a the call leg and E1b the function body), E2, E4 (two pieces, E4a the `carryBase` validation and E4b the session writer's pinned base).

## E1a — `_decide`, the `not _merge_reproduces_head(…)` leg

**axis:** stripped coordinates may say "unchanged" only when a three-way merge of the file reproduces the head byte for byte, so an edit moved between identical blocks is a changed file (`returning_review.py:378`, the `or (… and not _merge_reproduces_head(…))` leg).

**neutralization** (`returning_review.py:382`, one Edit: the leg can never hold):
```python
-                       and not _merge_reproduces_head(run, base, last_reviewed, head, f)))
+                       and False))
```

**raw red:** `... -m pytest "plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py::test_c1_an_edit_moved_between_identical_blocks_reads_the_file_changed" -q -p no:cacheprovider --tb=short`
```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_c1_an_edit_moved_between_identical_blocks_reads_the_file_changed _____
/home/user/wt-2279-a/plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py:408: in test_c1_an_edit_moved_between_identical_blocks_reads_the_file_changed
    assert got["changedFiles"] == [SHARED], got
E   AssertionError: {'read': 'changed', 'lastReviewed': '0fbe0a82483dc8efc4879f3bb77d115c7af80996', 'countable': 0, 'bar': 1000, ...}
E   assert [] == ['src/shared.py']
E     
E     Right contains one more item: 'src/shared.py'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py::test_c1_an_edit_moved_between_identical_blocks_reads_the_file_changed
1 failed in 1.92s
```
The red is on the axis: with the leg gone, a file whose raw sections differ only by coordinates is never a changed file, so the moved edit reads no changed file (`[]`) where the test requires `['src/shared.py']`.

**restore:** the inverse Edit.

**restore receipt** (the restored line, quoted from `returning_review.py:382` by Grep):
```
382:                       and not _merge_reproduces_head(run, base, last_reviewed, head, f)))
```

**raw green:** same command.
```
.                                                                        [100%]
1 passed in 2.22s
```

## E1b — `returning_review._merge_reproduces_head`, the merge-equals-head comparison

**axis:** the same: git must prove the three-way merge of the file equals the head's file byte for byte.

**neutralization** (`returning_review.py:208`, one Edit: the comparison always holds):
```python
-    return code == 0 and merged == expected
+    return True
```

**raw red:** same command.
```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_c1_an_edit_moved_between_identical_blocks_reads_the_file_changed _____
/home/user/wt-2279-a/plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py:408: in test_c1_an_edit_moved_between_identical_blocks_reads_the_file_changed
    assert got["changedFiles"] == [SHARED], got
E   AssertionError: {'read': 'changed', 'lastReviewed': 'ee973001c4361fd63d13617ccf56aff2f7a057cb', 'countable': 0, 'bar': 1000, ...}
E   assert [] == ['src/shared.py']
E     
E     Right contains one more item: 'src/shared.py'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py::test_c1_an_edit_moved_between_identical_blocks_reads_the_file_changed
1 failed in 2.13s
```
The red is on the axis: with the function answering True, the moved edit reads no changed file, as in E1a. (The edit also left the `merged`/`expected` reads unused; it is a probe, restored below.)

**restore:** the inverse Edit.

**restore receipt** (the restored line, quoted from `returning_review.py:208` by Grep):
```
208:    return code == 0 and merged == expected
```

**raw green:** same command.
```
.                                                                        [100%]
1 passed in 1.98s
```

## E2 — `returning_review._own_change`, the binary `index`-line keep

**axis:** a binary section has no hunk text to tell versions apart, so its `index` line (the blob ids) is its content identity and is kept (`returning_review.py:177` axis comment, `binary` flag at `:178`).

**neutralization** (`returning_review.py:181`, one Edit: the `index` line is dropped from a binary section too):
```python
-        if line.startswith(_INDEX_LINE) and not binary:
+        if line.startswith(_INDEX_LINE):
```

**raw red:** `... -m pytest "plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py::test_c1_a_binary_file_whose_bytes_changed_is_a_changed_file_and_reads_full" -q -p no:cacheprovider --tb=short`
```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_c1_a_binary_file_whose_bytes_changed_is_a_changed_file_and_reads_full __
/home/user/wt-2279-a/plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py:155: in test_c1_a_binary_file_whose_bytes_changed_is_a_changed_file_and_reads_full
    assert "Binary files" in new and R._own_change(old) != R._own_change(new)
E   AssertionError: assert ('Binary files' in 'diff --git a/src/blob.bin b/src/blob.bin\nnew file mode 100644\nindex 0000000..e8ca2f4\nBinary files /dev/null and b/src/blob.bin differ' and 'diff --git a/src/blob.bin b/src/blob.bin\nnew file mode 100644\nBinary files /dev/null and b/src/blob.bin differ' != 'diff --git a/src/blob.bin b/src/blob.bin\nnew file mode 100644\nBinary files /dev/null and b/src/blob.bin differ')
E    +  where 'diff --git a/src/blob.bin b/src/blob.bin\nnew file mode 100644\nBinary files /dev/null and b/src/blob.bin differ' = <function _own_change at 0x7f7c23cff7e0>('diff --git a/src/blob.bin b/src/blob.bin\nnew file mode 100644\nindex 0000000..6541b88\nBinary files /dev/null and b/src/blob.bin differ')
E    +    where <function _own_change at 0x7f7c23cff7e0> = R._own_change
E    +  and   'diff --git a/src/blob.bin b/src/blob.bin\nnew file mode 100644\nBinary files /dev/null and b/src/blob.bin differ' = <function _own_change at 0x7f7c23cff7e0>('diff --git a/src/blob.bin b/src/blob.bin\nnew file mode 100644\nindex 0000000..e8ca2f4\nBinary files /dev/null and b/src/blob.bin differ')
E    +    where <function _own_change at 0x7f7c23cff7e0> = R._own_change
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py::test_c1_a_binary_file_whose_bytes_changed_is_a_changed_file_and_reads_full
1 failed in 1.86s
```
The red is on the axis: with the `index` line dropped from a binary section, the sections of the old and the new bytes (which differ only by blob id) become equal, so the changed binary file reads as unchanged where the test requires the two own-changes to differ.

**restore:** the inverse Edit.

**restore receipt** (the restored line, quoted from `returning_review.py:181` by Grep):
```
181:        if line.startswith(_INDEX_LINE) and not binary:
```

**raw green:** same command.
```
.                                                                        [100%]
1 passed in 1.75s
```

## E4a — `review_record._validate`, the `carryBase` validation

**axis:** a carried account names the session's pinned review base as a full sha for the carry check, never the residual-lookup `baseRef` (`review_record.py:716` axis comment, check at `:717`).

**neutralization** (`review_record.py:717`, one Edit: the check always holds):
```python
-    chk("carriedReview" not in a or _full_sha(a.get("carryBase")), "carryBase")
+    chk(True, "carryBase")
```

**raw red:** `... -m pytest "plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_a_carried_account_without_a_full_sha_carry_base_is_refused" "plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_a_symbolic_extras_base_ref_still_writes_a_carried_record_that_reads_reviewed" -q -p no:cacheprovider --tb=short`
```
FFF.                                                                     [100%]
=================================== FAILURES ===================================
___ test_a_carried_account_without_a_full_sha_carry_base_is_refused[absent] ____
/home/user/wt-2279-a/plugins/superheroes/lib/tests/test_c1l11d_carried_review.py:307: in test_a_carried_account_without_a_full_sha_carry_base_is_refused
    assert out["ok"] is False and out["reason"] == "review-account-invalid", out
E   AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/2', 'parts': 0, ...}
E   assert (True is False)
__ test_a_carried_account_without_a_full_sha_carry_base_is_refused[symbolic] ___
/home/user/wt-2279-a/plugins/superheroes/lib/tests/test_c1l11d_carried_review.py:307: in test_a_carried_account_without_a_full_sha_carry_base_is_refused
    assert out["ok"] is False and out["reason"] == "review-account-invalid", out
E   AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/2', 'parts': 0, ...}
E   assert (True is False)
____ test_a_carried_account_without_a_full_sha_carry_base_is_refused[short] ____
/home/user/wt-2279-a/plugins/superheroes/lib/tests/test_c1l11d_carried_review.py:307: in test_a_carried_account_without_a_full_sha_carry_base_is_refused
    assert out["ok"] is False and out["reason"] == "review-account-invalid", out
E   AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/2', 'parts': 0, ...}
E   assert (True is False)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_a_carried_account_without_a_full_sha_carry_base_is_refused[absent]
FAILED plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_a_carried_account_without_a_full_sha_carry_base_is_refused[symbolic]
FAILED plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_a_carried_account_without_a_full_sha_carry_base_is_refused[short]
3 failed, 1 passed in 2.57s
```
The red is on the axis: with the validation gone, a carried account whose `carryBase` is absent, symbolic or short is written (`'ok': True, 'action': 'created'`) where the unedited test requires the refusal `review-account-invalid`. The symbolic-base test stayed green: its `carryBase` is a full sha.

**restore:** the inverse Edit.

**restore receipt** (the restored line, quoted from `review_record.py:717` by Grep):
```
717:    chk("carriedReview" not in a or _full_sha(a.get("carryBase")), "carryBase")
```

**raw green:** same command.
```
....                                                                     [100%]
4 passed in 2.57s
```

## E4b — `review_record_session`, the session writer's pinned base

**axis:** the carry check reads the session's pinned review base (the driver's full sha), never `extras.baseRef`, which may be a symbolic ref (`review_record_session.py:925` axis comment, assignment at `:926`).

**neutralization** (`review_record_session.py:926`, one Edit: the account's `baseRef`, which may be symbolic, is used):
```python
-        account["carryBase"] = cfg["baseRef"] if review_record._full_sha(cfg.get("baseRef")) else None
+        account["carryBase"] = account["baseRef"]
```

**raw red:** same command as E4a (both node ids).
```
...F                                                                     [100%]
=================================== FAILURES ===================================
_ test_a_symbolic_extras_base_ref_still_writes_a_carried_record_that_reads_reviewed _
/home/user/wt-2279-a/plugins/superheroes/lib/tests/test_c1l11d_carried_review.py:290: in test_a_symbolic_extras_base_ref_still_writes_a_carried_record_that_reads_reviewed
    assert out["ok"] is True and out["status"] == "reviewed", out
E   AssertionError: {'ok': False, 'reason': 'review-session-unsupported', 'detail': "the session's pinned review base is not a full commit sha, so the carry cannot be checked"}
E   assert (False is True)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11d_carried_review.py::test_a_symbolic_extras_base_ref_still_writes_a_carried_record_that_reads_reviewed
1 failed, 3 passed in 2.30s
```
The red is on the axis: with the symbolic `extras.baseRef` taken as the carry base, the session writer refuses (`review-session-unsupported`, "pinned review base is not a full commit sha") a carried record it must write.

**restore:** the inverse Edit.

**restore receipt** (the restored line, quoted from `review_record_session.py:926` by Grep):
```
926:        account["carryBase"] = cfg["baseRef"] if review_record._full_sha(cfg.get("baseRef")) else None
```

**raw green:** same command.
```
....                                                                     [100%]
4 passed in 2.84s
```
