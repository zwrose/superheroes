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
