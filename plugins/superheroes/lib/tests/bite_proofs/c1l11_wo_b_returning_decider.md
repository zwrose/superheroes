# C1-L11 (WO-B) bite-proof — the returning-review decider

**Provenance:** implementer WO-B / `lib/returning_review.py`, `lib/tests/test_returning_review_c1l11.py`

Declared guarded elements (from the order): E1 the over-bar comparison; E2 the new-area test; E3 the unclear-risk rule's earlier-unclear exception; E4 the ancestor check; E5 leaving proven copies out of the changed files; E6 the incremental diff being two-dot `lastReviewed head` rather than the whole PR section. Each was neutralized with one targeted edit and restored with the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2215-b` under `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider`. The captures are the runner's whole output for each run apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out; nothing is redacted (no secrets, tokens or URLs appear).

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| E1 | `returning_review.py` `_decide`, `countable > countable_lines.COUNTABLE_LINES_BAR` | one countable line over the bar reads full, exactly the bar reads changed | `test_a_later_change_of_1001_countable_lines_reads_full_and_exactly_1000_reads_changed` |
| E2 | `returning_review.py` `_decide`, `result["newAreas"] = sorted(delta_areas - earlier_areas)` | a risk area the earlier basis did not touch reads full and is named | `test_a_later_change_touching_an_area_the_earlier_review_did_not_reads_full` |
| E3 | `returning_review.py` `_decide`, `if not _is_unclear(earlier["laneBasis"].get("why"))` | an unclear risk reads full unless the earlier basis was unclear too | `test_an_unclear_risk_reads_full_when_the_earlier_review_was_clear` |
| E4 | `returning_review.py` `_decide`, `ancestor = code == 0` | a last reviewed commit git does not prove an ancestor of the head reads full | `test_a_rewritten_history_whose_last_reviewed_commit_is_not_an_ancestor_reads_full` |
| E5 | `returning_review.py` `_decide`, `files = [f for f in files if f not in proven_files]` | a proven copy is never a changed file | `test_a_returning_change_that_is_only_a_proven_copy_reads_changed_with_nothing_to_read` and `test_a_proven_copy_of_2000_lines_beside_a_10_line_edit_counts_only_the_edit` (run together) |
| E6 | `returning_review.py` `_decide`, `run(["diff", *diff_args, last_reviewed, head, "--", *files])` | the incremental diff is two-dot from the last reviewed commit, never the whole section of the change | `test_a_one_line_replacement_in_a_file_the_earlier_review_added_whole_counts_two` |

The other tests of the file (the fail-closed rows other than the ancestor check, the overlap, catch-up, unsettled-count and CLI tests) were not separately neutralized in this order; they are the unproven part of this record. The unsettled-counted line has no test: a file the counter leaves unsettled cannot be made in a throwaway repo without a failing git, so that branch is unproven.

---

## E1 — the over-bar comparison

**axis:** exactly 1,000 countable lines reads changed and 1,001 reads full.

**neutralization** (`returning_review.py`, `_decide`: the bar moved up by one line):
```python
-    if countable > countable_lines.COUNTABLE_LINES_BAR:
+    if countable > countable_lines.COUNTABLE_LINES_BAR + 1:  # BITE-PROOF NEUTRALIZATION (E1)
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider "plugins/superheroes/lib/tests/test_returning_review_c1l11.py::test_a_later_change_of_1001_countable_lines_reads_full_and_exactly_1000_reads_changed"`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_later_change_of_1001_countable_lines_reads_full_and_exactly_1000_reads_changed _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-16/test_a_later_change_of_1001_co0')

    def test_a_later_change_of_1001_countable_lines_reads_full_and_exactly_1000_reads_changed(tmp_path):
        # axis: the over-bar comparison; one line over the bar reading changed
        repo = Repo(tmp_path)
        base, _, earlier = returning(repo)
        repo.write("src/big.py", numbered("big", 1000))
        repo.commit("exactly the bar")
        exact = decide(repo, base, earlier)
        assert exact["read"] == "changed" and exact["countable"] == 1000
        repo.write("src/big.py", numbered("big", 1000) + "one_more = 1\n")
        repo.commit("one over")
        over = decide(repo, base, earlier)
>       assert over["read"] == "full" and over["countable"] == 1001
E       AssertionError: assert ('changed' == 'full'
E         
E         - full
E         + changed)

/home/user/wt-2215-b/plugins/superheroes/lib/tests/test_returning_review_c1l11.py:175: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_returning_review_c1l11.py::test_a_later_change_of_1001_countable_lines_reads_full_and_exactly_1000_reads_changed
1 failed in 0.72s
```

**restore:** the inverse edit (`+ 1` and the marker comment removed).

**restore receipt:** a search of `returning_review.py` for `BITE-PROOF` found nothing, and the line reads again:
```python
    if countable > countable_lines.COUNTABLE_LINES_BAR:
```

**raw green:** same command
```
.                                                                        [100%]
1 passed in 0.27s
```

---

## E2 — the new-area test

**axis:** a risk area the earlier basis did not touch is named in `newAreas` and reads full.

**neutralization** (`returning_review.py`, `_decide`: the new areas always empty):
```python
-    result["newAreas"] = sorted(delta_areas - earlier_areas)
+    result["newAreas"] = sorted(set())  # BITE-PROOF NEUTRALIZATION (E2)
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider "plugins/superheroes/lib/tests/test_returning_review_c1l11.py::test_a_later_change_touching_an_area_the_earlier_review_did_not_reads_full"`
```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_a_later_change_touching_an_area_the_earlier_review_did_not_reads_full __

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-21/test_a_later_change_touching_a0')

    def test_a_later_change_touching_an_area_the_earlier_review_did_not_reads_full(tmp_path):
        # axis: the new-area test; a change into an untouched area reading changed
        repo = Repo(tmp_path)
        base, _, earlier = returning(repo, first={"src/payments/charge.py": numbered("charge", 10)}, touched=["Payments"])
        repo.write("migrations/001.sql", "alter table t add column c int;\n")
        repo.commit("add a migration")
        got = decide(repo, base, earlier)
>       assert got["read"] == "full" and got["newAreas"] == ["Customer data"]
E       AssertionError: assert ('changed' == 'full'
E         
E         - full
E         + changed)

/home/user/wt-2215-b/plugins/superheroes/lib/tests/test_returning_review_c1l11.py:189: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_returning_review_c1l11.py::test_a_later_change_touching_an_area_the_earlier_review_did_not_reads_full
1 failed in 0.26s
```

**restore:** the inverse edit.

**restore receipt:** a search for `BITE-PROOF` found nothing, and the line reads again:
```python
    result["newAreas"] = sorted(delta_areas - earlier_areas)
```

**raw green:** same command
```
.                                                                        [100%]
1 passed in 0.25s
```

---

## E3 — the unclear-risk rule's earlier-unclear exception

**axis:** an unclear change against a clear earlier basis reads full; the exception (earlier basis unclear too) must apply only then. The neutralization makes the exception apply always, so the clear-earlier case is the one that reddens; the unclear-earlier case (`test_an_unclear_risk_reads_changed_when_the_earlier_review_was_unclear_too`) stays green under it and is not the detector for this edit.

**neutralization** (`returning_review.py`, `_decide`: the exception always taken):
```python
-        if not _is_unclear(earlier["laneBasis"].get("why")):
+        if False and not _is_unclear(earlier["laneBasis"].get("why")):  # BITE-PROOF NEUTRALIZATION (E3)
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider "plugins/superheroes/lib/tests/test_returning_review_c1l11.py::test_an_unclear_risk_reads_full_when_the_earlier_review_was_clear"`
```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_an_unclear_risk_reads_full_when_the_earlier_review_was_clear _______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-27/test_an_unclear_risk_reads_ful0')

    def test_an_unclear_risk_reads_full_when_the_earlier_review_was_clear(tmp_path):
        # axis: the unclear-risk rule; an unclear change passing as changed against a clear earlier basis
        repo = Repo(tmp_path)
        base, _, earlier = returning(repo, areas=None)
        repo.write("src/app.py", repo.read("src/app.py") + "extra = 1\n")
        repo.commit("fix")
        got = decide(repo, base, earlier)
>       assert got["read"] == "full" and tokens(got)[-1] == R.WHY_RISK_UNCLEAR and got["newAreas"] == []
E       AssertionError: assert ('changed' == 'full'
E         
E         - full
E         + changed)

/home/user/wt-2215-b/plugins/superheroes/lib/tests/test_returning_review_c1l11.py:212: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_returning_review_c1l11.py::test_an_unclear_risk_reads_full_when_the_earlier_review_was_clear
1 failed in 0.24s
```

**restore:** the inverse edit.

**restore receipt:** a search for `BITE-PROOF` found nothing, and the line reads again:
```python
        if not _is_unclear(earlier["laneBasis"].get("why")):
```

**raw green:** same command
```
.                                                                        [100%]
1 passed in 0.24s
```

---

## E4 — the ancestor check

**axis:** a last reviewed commit that is not an ancestor of the head (a rewritten history) reads full. In the test the amended commit holds the same content, so without the check the changed-file set is empty and the answer would be changed.

**neutralization** (`returning_review.py`, `_decide`: every last reviewed commit taken as an ancestor):
```python
-        ancestor = code == 0
+        ancestor = True  # BITE-PROOF NEUTRALIZATION (E4)
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider "plugins/superheroes/lib/tests/test_returning_review_c1l11.py::test_a_rewritten_history_whose_last_reviewed_commit_is_not_an_ancestor_reads_full"`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_rewritten_history_whose_last_reviewed_commit_is_not_an_ancestor_reads_full _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-31/test_a_rewritten_history_whose0')

    def test_a_rewritten_history_whose_last_reviewed_commit_is_not_an_ancestor_reads_full(tmp_path):
        # axis: the ancestor check; an orphaned last reviewed commit read as the starting point
        repo = Repo(tmp_path)
        base, reviewed, earlier = returning(repo)
        repo.git("commit", "-q", "--amend", "-m", "reworded first leg")
        assert repo.git("rev-parse", "HEAD") != reviewed
        got = decide(repo, base, earlier)
>       assert got["read"] == "full" and tokens(got) == [R.WHY_NOT_ANCESTOR] and got["lastReviewed"] == reviewed
E       AssertionError: assert ('changed' == 'full'
E         
E         - full
E         + changed)

/home/user/wt-2215-b/plugins/superheroes/lib/tests/test_returning_review_c1l11.py:339: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_returning_review_c1l11.py::test_a_rewritten_history_whose_last_reviewed_commit_is_not_an_ancestor_reads_full
1 failed in 0.28s
```

**restore:** the inverse edit.

**restore receipt:** a search for `BITE-PROOF` found nothing, and the line reads again:
```python
        ancestor = code == 0
```

**raw green:** same command
```
.                                                                        [100%]
1 passed in 0.33s
```

---

## E5 — proven copies left out of the changed files

**axis:** a proven copy is neither a changed file nor in the incremental diff, so it is neither read, counted nor matched against a risk area.

**neutralization** (`returning_review.py`, `_decide`: no file is left out):
```python
-    files = [f for f in files if f not in proven_files]
+    files = [f for f in files if f not in set()]  # BITE-PROOF NEUTRALIZATION (E5)
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider "plugins/superheroes/lib/tests/test_returning_review_c1l11.py::test_a_returning_change_that_is_only_a_proven_copy_reads_changed_with_nothing_to_read" "plugins/superheroes/lib/tests/test_returning_review_c1l11.py::test_a_proven_copy_of_2000_lines_beside_a_10_line_edit_counts_only_the_edit"`
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_a_returning_change_that_is_only_a_proven_copy_reads_changed_with_nothing_to_read _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-36/test_a_returning_change_that_i0')

    def test_a_returning_change_that_is_only_a_proven_copy_reads_changed_with_nothing_to_read(tmp_path):
        # axis: leaving proven copies out of the changed files; a copy listed as a changed file
        repo = Repo(tmp_path)
        base, _, earlier = returning(repo)
        repo.write("vendor/lib.py", numbered("vendored", 2000))
        repo.commit("vendor a copy")
        got = decide(repo, base, earlier, proven=_proven(repo, base, _proof_for(repo, "vendor/lib.py")))
        assert got["read"] == "changed" and got["countable"] == 0
>       assert got["changedFiles"] == [] and got["deltaDiff"] == "" and tokens(got) == [R.WHY_CHANGED_ONLY]
E       AssertionError: assert (['vendor/lib.py'] == []
E         
E         Left contains one more item: 'vendor/lib.py'
E         Use -v to get more diff)

/home/user/wt-2215-b/plugins/superheroes/lib/tests/test_returning_review_c1l11.py:250: AssertionError
_ test_a_proven_copy_of_2000_lines_beside_a_10_line_edit_counts_only_the_edit _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-36/test_a_proven_copy_of_2000_lin0')

    def test_a_proven_copy_of_2000_lines_beside_a_10_line_edit_counts_only_the_edit(tmp_path):
        # axis: leaving proven copies out of the changed files; a copy listed or read beside the edit
        repo = Repo(tmp_path)
        base, _, earlier = returning(repo)
        repo.write("vendor/lib.py", numbered("vendored", 2000))
        repo.write("src/app.py", repo.read("src/app.py") + numbered("edit", 10))
        repo.commit("vendor a copy and edit")
        got = decide(repo, base, earlier, proven=_proven(repo, base, _proof_for(repo, "vendor/lib.py")))
        assert got["read"] == "changed" and got["countable"] == 10
>       assert got["changedFiles"] == ["src/app.py"] and "vendor/lib.py" not in got["deltaDiff"]
E       AssertionError: assert (['src/app.py'...endor/lib.py'] == ['src/app.py']
E         
E         Left contains one more item: 'vendor/lib.py'
E         Use -v to get more diff)

/home/user/wt-2215-b/plugins/superheroes/lib/tests/test_returning_review_c1l11.py:262: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_returning_review_c1l11.py::test_a_returning_change_that_is_only_a_proven_copy_reads_changed_with_nothing_to_read
FAILED plugins/superheroes/lib/tests/test_returning_review_c1l11.py::test_a_proven_copy_of_2000_lines_beside_a_10_line_edit_counts_only_the_edit
2 failed in 0.81s
```

**restore:** the inverse edit.

**restore receipt:** a search for `BITE-PROOF` found nothing, and the line reads again:
```python
    files = [f for f in files if f not in proven_files]
```

**raw green:** same command
```
..                                                                       [100%]
2 passed in 0.34s
```

---

## E6 — the incremental diff is two-dot from the last reviewed commit

**axis:** a file the earlier review added whole and the return changed by one line counts 2 (the one line out and the one in), not the 1,500 lines of its whole section of the change.

**neutralization** (`returning_review.py`, `_decide`: the whole section of the change over the same files):
```python
-    code, delta = run(["diff", *diff_args, last_reviewed, head, "--", *files])
+    code, delta = run(["diff", *diff_args, "%s...%s" % (base, head), "--", *files])  # BITE-PROOF NEUTRALIZATION (E6)
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider "plugins/superheroes/lib/tests/test_returning_review_c1l11.py::test_a_one_line_replacement_in_a_file_the_earlier_review_added_whole_counts_two"`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_one_line_replacement_in_a_file_the_earlier_review_added_whole_counts_two _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-38/test_a_one_line_replacement_in0')

    def test_a_one_line_replacement_in_a_file_the_earlier_review_added_whole_counts_two(tmp_path):
        # axis: the incremental diff being two-dot from the last reviewed commit; the whole section of the file counted
        repo = Repo(tmp_path)
        base, _, earlier = returning(repo, first={"src/big.py": numbered("big", 1500)})
        repo.write("src/big.py", repo.read("src/big.py").replace("value_big_700 = 700", "value_big_700 = -1"))
        repo.commit("replace one line")
        got = decide(repo, base, earlier)
>       assert got["read"] == "changed" and got["countable"] == 2 and got["changedFiles"] == ["src/big.py"]
E       AssertionError: assert ('full' == 'changed'
E         
E         - changed
E         + full)

/home/user/wt-2215-b/plugins/superheroes/lib/tests/test_returning_review_c1l11.py:275: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_returning_review_c1l11.py::test_a_one_line_replacement_in_a_file_the_earlier_review_added_whole_counts_two
1 failed in 1.18s
```

**restore:** the inverse edit.

**restore receipt:** a search for `BITE-PROOF` found nothing, and the line reads again:
```python
    code, delta = run(["diff", *diff_args, last_reviewed, head, "--", *files])
```

**raw green:** same command
```
.                                                                        [100%]
1 passed in 0.23s
```

---

## Review session 1 fixes (WO-F, issue #2215): E7 and E8

Declared guarded elements (from the order): E7 the proven-copy filter over the final path list; E8 the unsettled-lines addition to `countable`. Each was neutralized with one targeted edit made with the edit tool and restored with the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2215` under `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider`. The captures are the runner's whole output for each run apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out; nothing is redacted (no secrets, tokens or URLs appear). E8 supersedes the sentence above that says the unsettled-counted line has no test: the unsettled variant of the 1,000/1,001-line boundary test now covers it.

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| E7 | `returning_review.py` `_decide`, `paths = sorted(p for p in ... if p not in proven_files)` | no proven copy is ever passed to the incremental `git diff` or to `lane_call.call`, as a changed file or as a rename's source path | `test_a_proven_copy_that_an_earlier_rename_came_from_is_never_passed_on` |
| E8 | `returning_review.py` `_decide`, `countable += sum(row["lines"] for row in left)` | the lines of a file the counter could not settle are added to `countable` | `test_a_later_change_of_1001_countable_lines_reads_full_and_exactly_1000_reads_changed[unsettled-lines]` |

---

## E7 — the proven-copy filter over the final path list

**axis:** no path in the proven copies is passed to the incremental `git diff` or to `lane_call.call`, whether it reaches the path list as a changed file or as a rename source. The test: an earlier review renamed `vendor/lib.py` to `src/app.py`; the return restores `vendor/lib.py` with new bytes a copy proof covers and edits `src/app.py` by three lines; the vendor file must be in neither `deltaDiff` nor the paths `lane_call.call` receives, and `countable` is 3.

**neutralization** (`returning_review.py`, `_decide`: the filter is left to the changed files, before the rename sources are added, as the code had it):
```python
-    paths = sorted(p for p in set(files).union(*(sources.get(f, set()) for f in files)) if p not in proven_files)
+    paths = sorted(set(files).union(*(sources.get(f, set()) for f in files)))  # BITE-PROOF NEUTRALIZATION (E7)
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider "plugins/superheroes/lib/tests/test_returning_review_c1l11.py::test_a_proven_copy_that_an_earlier_rename_came_from_is_never_passed_on"`
```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_a_proven_copy_that_an_earlier_rename_came_from_is_never_passed_on ____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-43/test_a_proven_copy_that_an_ear0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f1b1696d880>

    def test_a_proven_copy_that_an_earlier_rename_came_from_is_never_passed_on(tmp_path, monkeypatch):
        # axis: the proven-copy filter over the final path list; a proven copy coming back as a rename's source path
        repo = Repo(tmp_path)
        repo.main_commit("vendor/lib.py", numbered("lib", 40))
        repo.merge_main()
        os.remove(os.path.join(repo.root, "vendor", "lib.py"))
        base, reviewed, earlier = returning(repo, first={"src/app.py": numbered("lib", 40)})
        reviewed_diff = repo.git("diff", *review_diff_bytes.REVIEW_DIFF_ARGS, "%s...%s" % (base, reviewed))
        assert "rename from vendor/lib.py" in reviewed_diff and "rename to src/app.py" in reviewed_diff
        repo.write("vendor/lib.py", numbered("newlib", 40))
        repo.write("src/app.py", repo.read("src/app.py") + numbered("edit", 3))
        repo.commit("restore the vendor file with new bytes and edit the src file")
        seen = []
        real_call = R.lane_call.call
    
        def recording_call(cwd, paths, *args, **kwargs):
            seen.append(list(paths))
            return real_call(cwd, paths, *args, **kwargs)
    
        monkeypatch.setattr(R.lane_call, "call", recording_call)
        got = decide(repo, base, earlier, proven=_proven(repo, base, _proof_for(repo, "vendor/lib.py")))
        assert got["read"] == "changed" and got["countable"] == 3
>       assert got["changedFiles"] == ["src/app.py"] and "vendor/lib.py" not in got["deltaDiff"]
E       AssertionError: assert (['src/app.py'] == ['src/app.py']
E         
E         Use -v to get more diff and 'vendor/lib.py' not in 'diff --git ...ib_39 = 39\n'
E         
E         'vendor/lib.py' is contained here:
E           f --git a/vendor/lib.py b/vendor/lib.py
E         ?           +++++++++++++
E           new file mode 100644
E           index 0000000..916d334
E           --- /dev/null...
E         
E         ...Full output truncated, use '-vv' to show)

/home/user/wt-2215/plugins/superheroes/lib/tests/test_returning_review_c1l11.py:295: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_returning_review_c1l11.py::test_a_proven_copy_that_an_earlier_rename_came_from_is_never_passed_on
1 failed in 0.72s
```

**restore:** the inverse edit.

**restore receipt:** a search for `BITE-PROOF` in `returning_review.py` found nothing, and the line reads again:
```python
    paths = sorted(p for p in set(files).union(*(sources.get(f, set()) for f in files)) if p not in proven_files)
```

**raw green:** same command
```
.                                                                        [100%]
1 passed in 0.91s
```

---

## E8 — the unsettled-lines addition to `countable`

**axis:** the lines of a file the counter could not settle are added to `countable`: with the attribute read failing (`attribute-unreadable`), exactly 1,000 unsettled lines read changed with `countable` 1000, and 1,001 read full with `countable` 1001.

**neutralization** (`returning_review.py`, `_decide`: the addition is removed):
```python
-        countable += sum(row["lines"] for row in left)
+        pass  # BITE-PROOF NEUTRALIZATION (E8)
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider "plugins/superheroes/lib/tests/test_returning_review_c1l11.py::test_a_later_change_of_1001_countable_lines_reads_full_and_exactly_1000_reads_changed[unsettled-lines]"`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_later_change_of_1001_countable_lines_reads_full_and_exactly_1000_reads_changed[unsettled-lines] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-45/test_a_later_change_of_1001_co0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f270f4f2420>
unsettled = True

    @pytest.mark.parametrize("unsettled", [False, True], ids=["settled", "unsettled-lines"])
    def test_a_later_change_of_1001_countable_lines_reads_full_and_exactly_1000_reads_changed(tmp_path, monkeypatch, unsettled):
        # axis: the over-bar comparison; one line over the bar reading changed
        # axis: the lines of a file the counter cannot settle are added to the count; an unsettled file counted as nothing
        if unsettled:
            monkeypatch.setattr(countable_lines, "_attribute_flags", lambda *args, **kwargs: None)
        repo = Repo(tmp_path)
        base, _, earlier = returning(repo)
        repo.write("src/big.py", numbered("big", 1000))
        repo.commit("exactly the bar")
        exact = decide(repo, base, earlier)
>       assert exact["read"] == "changed" and exact["countable"] == 1000
E       AssertionError: assert ('changed' == 'changed'
E         
E           changed and 0 == 1000)

/home/user/wt-2215/plugins/superheroes/lib/tests/test_returning_review_c1l11.py:175: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_returning_review_c1l11.py::test_a_later_change_of_1001_countable_lines_reads_full_and_exactly_1000_reads_changed[unsettled-lines]
1 failed in 0.81s
```

**restore:** the inverse edit.

**restore receipt:** a search for `BITE-PROOF` in `returning_review.py` found nothing, and the line reads again:
```python
        countable += sum(row["lines"] for row in left)
```

**raw green:** same command
```
.                                                                        [100%]
1 passed in 0.25s
```

The red stops at the first assertion (the 1,000-line step reads `countable` 0); the 1,001-line step of the variant is not reached under this neutralization.
