# Issue 2561 (WO-A) bite-proof — the head-coverage check proves a stack layer after the layer below it is rewritten, only on a second base whose tree git proves equal to the base's

**Provenance:** implementer `i2561-wo-a`, recording the guards added to `lib/head_coverage.py` (`_check_rewritten`) and `lib/returning_review.py` (`changed_files`, `_merge_reproduces_head`), proved by `lib/tests/test_head_coverage_rewritten_below_2561.py`. Worktree `/home/user/wt-2561`, base `0535cb82d3a963f7b17a1d15ddd9c5a11e6d374a` plus this dispatch's uncommitted work.

Declared guarded elements (the order's own four): E-tree, E-read, E-xbase, E-fork. The axis lines are in the code at:

```
plugins/superheroes/lib/head_coverage.py:411:    # axis: a second base whose tree git could not read, or that shares no merge base with the certified commit, proves nothing and reads needs-review — see bite-proof record i2561_head_coverage_rewritten_below (E-read)
plugins/superheroes/lib/head_coverage.py:416:        # axis: a second base is read only when its tree equals the base's tree, so a commit from the layer's own history never lets a dropped change read proven — see bite-proof record i2561_head_coverage_rewritten_below (E-tree)
plugins/superheroes/lib/returning_review.py:195:    # axis: the fork is the merge base of the last reviewed commit and the second base when one is given, so a layer whose layer below was rewritten is reconstructed from its own fork — see bite-proof record i2561_head_coverage_rewritten_below (E-fork)
plugins/superheroes/lib/returning_review.py:228:    # axis: the reviewed side is read against the second base when one is given, so a layer whose layer below was rewritten is compared on its own change — see bite-proof record i2561_head_coverage_rewritten_below (E-xbase)
```

Each element was neutralized with targeted Edits and restored with the inverse Edits; no `git checkout`, `restore`, `reset` or `stash` was used. Every run is `scripts/pinned-python -B -X pycache_prefix=/tmp/i2561-pyc -m pytest "<node id>" -q -p no:cacheprovider` over the exact node id. Each capture is the runner's whole output apart from the `UV_NATIVE_TLS` deprecation warning line (the first line of each real output), which is left out; two long `AssertionError` dict lines are printed by pytest already shortened with `...`, as they came. Nothing is redacted: no secrets, tokens or URLs appear (the `/tmp/claude-0/...` paths are pytest temp directories).

| ID | Guarded element | Axis | Proving node (in `test_head_coverage_rewritten_below_2561.py`) |
|---|---|---|---|
| E-tree | `head_coverage._check_rewritten`, the tree-equality refusal (`head_coverage.py:417`) | a second base is read only when its tree equals the base's, so a commit of the layer's own history never lets a dropped change read proven | `test_a_base_at_review_from_the_layers_own_history_never_lets_a_dropped_change_read_proven` |
| E-read | `head_coverage._check_rewritten`, the git-read refusals (`head_coverage.py:410`, `:412`, `:422`) | a second base git cannot read, or that has no merge base with X, proves nothing | `test_a_base_at_review_git_has_no_object_for_reads_needs_review` |
| E-xbase | `returning_review.changed_files`, the reviewed-side diff (`returning_review.py:229`) | the reviewed change is read against the second base, so a file whose reconstruction cannot run (a deletion) is compared on its own change | `test_a_file_the_upper_layer_deletes_after_the_lower_layer_edited_it_reads_proven_against_the_second_base` |
| E-fork | `returning_review._merge_reproduces_head`, the fork (`returning_review.py:196`) | the three-way merge forks at the merge base of X and the second base | `test_a_layer_below_fixed_after_the_review_is_reconstructed_from_the_second_fork` |

**Disclosure — the order's expected red for E-xbase did not hold, and the proving node differs.** The order named `T1`'s `[lower_head]` case (`test_a_straightened_stack_reads_needs_review_without_the_input_and_proven_with_it`) as E-xbase's red. With the E-xbase neutralization in place that node passed (`1 passed in 0.39s`): on T1 the head's tree equals X's, so the reconstruction with the second fork (E-fork) proves the file alone, and E-xbase is not discriminated there. A case where reconstruction cannot run (X holds no blob: the upper layer deletes a file the lower layer edited) does discriminate it, so one test was added to the new file for that (`test_a_file_the_upper_layer_deletes_...`), and it is E-xbase's proving node. The inverse also holds: E-fork is discriminated by T5 only (T1 proves by text equality under E-fork's neutralization).

**Disclosure — E-read is one element with three edits.** `_check_rewritten` has two refusals on git reads (the tree read and the merge-base read). Neutralizing the tree-read refusal alone leaves the tree-equality refusal (E-tree) to catch an object-less value with the same token, and neutralizing it with the merge-base refusal alone leaves the tree-read refusal. All three edits below are applied together, so a failed read counts as an equal tree and no read refuses. The red shown is the no-object case, with `[lower_head, NO_OBJECT]` given. The `git`-seam cases (a failed tree read, a failed merge base) were not separately neutralized: they are pinned passing by `test_a_failed_tree_read_reads_needs_review` and `test_a_base_at_review_with_no_merge_base_reads_needs_review` and not shown to bite one by one.

**Not neutralized (the unproven part of this record):** the `input-invalid` refusal of a non-sha value (step 4(a)), the normalisation of `base_at_review` (a string, a tuple, an odd type), the choice among several second bases (the first that proves, else `first` if it is judgement, else the first judgement, else the first value's result) and the unchanged returns for an unusable record or a head that is X. They are pinned passing by `test_a_base_at_review_that_is_no_sha_reads_input_invalid`, `test_two_successive_straightenings_prove_when_every_old_head_of_the_layer_below_is_given` and `test_no_input_or_an_unneeded_one_leaves_the_answer_as_it_was`, and were not run under a neutralization.

---

## E-tree — the tree-equality refusal

**axis:** a second base is read only when its tree equals the base's tree.

**neutralization** (`head_coverage.py:417`, never refuse):
```python
-        if tree != base_tree:
+        if False and tree != base_tree:
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/i2561-pyc -m pytest "plugins/superheroes/lib/tests/test_head_coverage_rewritten_below_2561.py::test_a_base_at_review_from_the_layers_own_history_never_lets_a_dropped_change_read_proven" -q -p no:cacheprovider` (exit 1)
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_base_at_review_from_the_layers_own_history_never_lets_a_dropped_change_read_proven _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-2/test_a_base_at_review_from_the0')

    def test_a_base_at_review_from_the_layers_own_history_never_lets_a_dropped_change_read_proven(tmp_path):
        repo = TR.Repo(tmp_path)
        repo.git("checkout", "-q", "-b", "lower", "main")
        repo.write(SHARED, shared_text("lower"))
        lower = repo.commit("lower layer")
        repo.git("checkout", "-q", "-b", "upper", "lower")
        repo.write(APP, TR.numbered("app", 5))
        p = repo.commit("upper layer, first commit")
        repo.write(SHARED, shared_text("lower", "upper"))
        x = repo.commit("upper layer, second commit")
        b = rebuild(repo, lower, repo.git("rev-parse", "main"))
        repo.git("checkout", "-q", "--detach", b)
        repo.write(SHARED, shared_text("lower", "upper"))
        head = repo.commit("only the shared change, the app file dropped")
        record = TR.earlier_record(x)
        got = run_check(repo, b, record, head, base_at_review=[p])
>       assert got["answer"] == "needs-review" and tokens(got) == [HC.WHY_BASE_AT_REVIEW_UNPROVEN], got
E       AssertionError: {'answer': 'proven', 'why': ["own-change-unchanged: git shows the pull request's own change at the head equals the rev...ee"], 'certified': 'df7329aba00ae0058570db1edcb1f8693822bdc0', 'head': '29af0473f4f75d3d1123306806799945a3256f3f', ...}
E       assert ('proven' == 'needs-review'
E         
E         - needs-review
E         + proven)

/home/user/wt-2561/plugins/superheroes/lib/tests/test_head_coverage_rewritten_below_2561.py:169: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_head_coverage_rewritten_below_2561.py::test_a_base_at_review_from_the_layers_own_history_never_lets_a_dropped_change_read_proven
1 failed in 0.36s
```
(The test's line number in the red is from the file before it was shortened by two docstring lines and given one more test; the assertion is the one named.)

**restore:** the inverse Edit, `if False and tree != base_tree:` back to `if tree != base_tree:`.

**restore receipt** (the Grep tool over `head_coverage.py` for `if tree != base_tree|if False and`, after the restore):
```
417:        if tree != base_tree:
```

**raw green:** same command (exit 0)
```
.                                                                        [100%]
1 passed in 1.57s
```

## E-read — the git-read refusals

**axis:** a second base git cannot read (tree), or that has no merge base with X, proves nothing.

**neutralization** (`head_coverage.py:410`, `:412`, `:422`: a failed tree read counts as the base's tree, and neither read refuses):
```python
-    trees = [_tree_of(run, v) for v in values]
+    trees = [_tree_of(run, v) or base_tree for v in values]
-    if base_tree is None or any(t is None for t in trees):
+    if False and (base_tree is None or any(t is None for t in trees)):
-        if code != 0 or not returning_review._is_sha(text.strip() if isinstance(text, str) else ""):
+        if False and (code != 0 or not returning_review._is_sha(text.strip() if isinstance(text, str) else "")):
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/i2561-pyc -m pytest "plugins/superheroes/lib/tests/test_head_coverage_rewritten_below_2561.py::test_a_base_at_review_git_has_no_object_for_reads_needs_review" -q -p no:cacheprovider` (exit 1)
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_a_base_at_review_git_has_no_object_for_reads_needs_review ________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-4/test_a_base_at_review_git_has_0')

    def test_a_base_at_review_git_has_no_object_for_reads_needs_review(tmp_path):
        repo = TR.Repo(tmp_path)
        s = straightened(repo)
        got = run_check(repo, s["b1"], TR.earlier_record(s["x"]), s["h1"], base_at_review=[s["lower"], NO_OBJECT])
>       assert got["answer"] == "needs-review" and tokens(got) == [HC.WHY_BASE_AT_REVIEW_UNPROVEN], got
E       AssertionError: {'answer': 'proven', 'why': ["own-change-unchanged: git shows the pull request's own change at the head equals the rev...ee"], 'certified': '2afd13613b6fc9b217671b7f1180c365c304deac', 'head': '151896790f21017a344c4a4c51b279ea20fcd1cb', ...}
E       assert ('proven' == 'needs-review'
E         
E         - needs-review
E         + proven)

/home/user/wt-2561/plugins/superheroes/lib/tests/test_head_coverage_rewritten_below_2561.py:186: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_head_coverage_rewritten_below_2561.py::test_a_base_at_review_git_has_no_object_for_reads_needs_review
1 failed in 0.43s
```

**restore:** the three inverse Edits, each undoing its line above.

**restore receipt** (the Grep tool over `head_coverage.py` for `trees = \[|if base_tree is None|if code != 0 or not returning_review._is_sha\(text.strip|False and`, after the restore; no `False and` remains):
```
410:    trees = [_tree_of(run, v) for v in values]
412:    if base_tree is None or any(t is None for t in trees):
422:        if code != 0 or not returning_review._is_sha(text.strip() if isinstance(text, str) else ""):
```

**raw green:** same command (exit 0)
```
.                                                                        [100%]
1 passed in 0.31s
```

## E-xbase — the reviewed side read against the second base

**axis:** the reviewed change is read against the second base, so a file reconstruction cannot prove (a deletion) is compared on its own change.

**neutralization** (`returning_review.py:229`, `changed_files`: the reviewed side uses `base`):
```python
-    code_a, reviewed_text = run(["diff", *diff_args, "%s...%s" % (x_base if x_base is not None else base, last_reviewed)])
+    code_a, reviewed_text = run(["diff", *diff_args, "%s...%s" % (base, last_reviewed)])
```

**raw run on the order's named node (not a red):** `... -m pytest "plugins/superheroes/lib/tests/test_head_coverage_rewritten_below_2561.py::test_a_straightened_stack_reads_needs_review_without_the_input_and_proven_with_it" -q -p no:cacheprovider` (exit 0)
```
.                                                                        [100%]
1 passed in 0.39s
```

**raw red** on the added node: `scripts/pinned-python -B -X pycache_prefix=/tmp/i2561-pyc -m pytest "plugins/superheroes/lib/tests/test_head_coverage_rewritten_below_2561.py::test_a_file_the_upper_layer_deletes_after_the_lower_layer_edited_it_reads_proven_against_the_second_base" -q -p no:cacheprovider` (exit 1)
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_file_the_upper_layer_deletes_after_the_lower_layer_edited_it_reads_proven_against_the_second_base _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-7/test_a_file_the_upper_layer_de0')

    def test_a_file_the_upper_layer_deletes_after_the_lower_layer_edited_it_reads_proven_against_the_second_base(tmp_path):
        repo = TR.Repo(tmp_path)
        main, lower, _ = stack(repo)
        repo.git("rm", "-q", SHARED)
        x = repo.commit("upper layer deletes the shared file")
        b1 = rebuild(repo, lower, main)
        h1 = rebuild(repo, x, b1)
        assert run_check(repo, b1, TR.earlier_record(x), h1)["answer"] == "needs-review"
        got = run_check(repo, b1, TR.earlier_record(x), h1, base_at_review=[lower])
>       assert got["answer"] == "proven" and got["files"] == [], got
E       AssertionError: {'answer': 'needs-review', 'why': ['behaviour-change: not only prose or comment lines: src/shared.py', "base-at-review...ee"], 'certified': '9f48da05d673670736caf027e00f8e7840923024', 'head': 'edbaafbc9403b8a5f7a9df65df5ba0a8c4c7edef', ...}
E       assert ('proven' == 'needs-review'
E         
E         - proven
E         + needs-review)

/home/user/wt-2561/plugins/superheroes/lib/tests/test_head_coverage_rewritten_below_2561.py:102: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_head_coverage_rewritten_below_2561.py::test_a_file_the_upper_layer_deletes_after_the_lower_layer_edited_it_reads_proven_against_the_second_base
1 failed in 0.34s
```

**restore:** the inverse Edit, `"%s...%s" % (base, last_reviewed)` back to `"%s...%s" % (x_base if x_base is not None else base, last_reviewed)`.

**restore receipt** (the Grep tool over `returning_review.py` for `last_reviewed\)\]\)`, after the restore):
```
229:    code_a, reviewed_text = run(["diff", *diff_args, "%s...%s" % (x_base if x_base is not None else base, last_reviewed)])
```

**raw green:** same command as the red (exit 0)
```
.                                                                        [100%]
1 passed in 0.33s
```

## E-fork — the fork at the second base

**axis:** the three-way merge forks at the merge base of X and the second base.

**neutralization** (`returning_review.py:196`, `_merge_reproduces_head`: `fork_base` ignored):
```python
-    code, text = run(["merge-base", last_reviewed, fork_base if fork_base is not None else base])
+    code, text = run(["merge-base", last_reviewed, base])
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/i2561-pyc -m pytest "plugins/superheroes/lib/tests/test_head_coverage_rewritten_below_2561.py::test_a_layer_below_fixed_after_the_review_is_reconstructed_from_the_second_fork" -q -p no:cacheprovider` (exit 1)
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_layer_below_fixed_after_the_review_is_reconstructed_from_the_second_fork _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-9/test_a_layer_below_fixed_after0')

    def test_a_layer_below_fixed_after_the_review_is_reconstructed_from_the_second_fork(tmp_path):
        repo = TR.Repo(tmp_path)
        main, lower, x = stack(repo)
        repo.git("checkout", "-q", "lower")
        lines = shared_text("lower").splitlines(keepends=True)
        lines[16] = "fixed_16 = 1\n"
        repo.write(SHARED, "".join(lines))
        fixed = repo.commit("lower layer fix")
        repo.git("checkout", "-q", "upper")
        repo.git("merge", "-q", "--no-ff", "-m", "merge lower", "lower")
        merged = repo.git("rev-parse", "HEAD")
        b = rebuild(repo, fixed, main)
        h = rebuild(repo, merged, b)
        record = TR.earlier_record(x)
        assert run_check(repo, b, record, h)["answer"] == "needs-review"
        got = run_check(repo, b, record, h, base_at_review=[fixed])
>       assert got["answer"] == "proven" and got["reconstructed"] == [SHARED] and got["files"] == [], got
E       AssertionError: {'answer': 'needs-review', 'why': ['behaviour-change: not only prose or comment lines: src/shared.py', "base-at-review...ee"], 'certified': 'a5cba81dd8fa60291a2723ee6316044dd0050005', 'head': '8fa6322d42422565d2880626a1a5ea6689ba5ab6', ...}
E       assert ('needs-review' == 'proven'
E         
E         - proven
E         + needs-review)

/home/user/wt-2561/plugins/superheroes/lib/tests/test_head_coverage_rewritten_below_2561.py:161: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_head_coverage_rewritten_below_2561.py::test_a_layer_below_fixed_after_the_review_is_reconstructed_from_the_second_fork
1 failed in 0.37s
```

**restore:** the inverse Edit, `run(["merge-base", last_reviewed, base])` back to `run(["merge-base", last_reviewed, fork_base if fork_base is not None else base])`.

**restore receipt** (the Grep tool over `returning_review.py` for `"merge-base", last_reviewed`, after the restore):
```
196:    code, text = run(["merge-base", last_reviewed, fork_base if fork_base is not None else base])
```

**raw green:** same command as the red (exit 0)
```
.                                                                        [100%]
1 passed in 0.36s
```
