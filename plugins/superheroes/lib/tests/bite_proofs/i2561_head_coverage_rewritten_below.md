# Issue 2561 (WO-A, WO-C) bite-proof — the head-coverage check proves a stack layer after the layer below it is rewritten, tries a second base only when git proves its tree equal to the base's, and ignores every other well-formed second base

**Provenance:** implementer `i2561-wo-a`, recording the guards added to `lib/head_coverage.py` (`_check_rewritten`) and `lib/returning_review.py` (`changed_files`, `_merge_reproduces_head`), proved by `lib/tests/test_head_coverage_rewritten_below_2561.py`. Worktree `/home/user/wt-2561`, base `0535cb82d3a963f7b17a1d15ddd9c5a11e6d374a` plus this dispatch's uncommitted work. Updated by implementer `i2561-wo-c` (head `e16c123f9f47fb83ce2997defc6df82423b48b1c` plus its uncommitted work): a full-sha second base that git cannot read, whose tree differs, or that has no merge base with X is now ignored instead of refused, and the E-tree, E-read and new E-ignore entries below are re-proved for that behaviour. The E-xbase and E-fork entries are unchanged and were not re-run by this dispatch.

Declared guarded elements (the order's five): E-tree, E-read, E-ignore, E-xbase, E-fork. `i2561-wo-c` proves E-tree, E-read and E-ignore. E-xbase and E-fork are unchanged code in `returning_review.py`, outside that order's surface: the orchestrator re-runs both on the final head in its own probe worktree and carries those receipts in the build record. The axis lines are in the code at:

```
plugins/superheroes/lib/head_coverage.py:421:    # axis: a second base that is ignored never changes the answer from the check's own without it — see bite-proof record i2561_head_coverage_rewritten_below (E-ignore)
plugins/superheroes/lib/head_coverage.py:444:    # axis: a second base that is ignored never changes the answer a valid second base proves, and is reported beside it — see bite-proof record i2561_head_coverage_rewritten_below (E-ignore)
plugins/superheroes/lib/head_coverage.py:453:    # axis: a second base whose tree git could not read, or that shares no merge base with the certified commit, is never tried — see bite-proof record i2561_head_coverage_rewritten_below (E-read)
plugins/superheroes/lib/head_coverage.py:456:    # axis: a second base whose tree differs from the base's tree is never tried, so a commit from the layer's own history never lets a dropped change read proven — see bite-proof record i2561_head_coverage_rewritten_below (E-tree)
plugins/superheroes/lib/returning_review.py:195:    # axis: the fork is the merge base of the last reviewed commit and the second base when one is given, so a layer whose layer below was rewritten is reconstructed from its own fork — see bite-proof record i2561_head_coverage_rewritten_below (E-fork)
plugins/superheroes/lib/returning_review.py:228:    # axis: the reviewed side is read against the second base when one is given, so a layer whose layer below was rewritten is compared on its own change — see bite-proof record i2561_head_coverage_rewritten_below (E-xbase)
```

Each element was neutralized with targeted Edits and restored with the inverse Edits; no `git checkout`, `restore`, `reset` or `stash` was used. The E-tree, E-read and E-ignore runs (the `i2561-wo-c` ones) are `scripts/pinned-python -B -X pycache_prefix=/tmp/i2561c-pyc -m pytest "<node id>" -q -p no:cacheprovider` over the exact node id; the E-xbase and E-fork captures are the `i2561-wo-a` ones, as they were. Each capture is the runner's whole output apart from the `UV_NATIVE_TLS` deprecation warning line (the first line of each real output), which is left out; a few long `AssertionError` dict lines are printed by pytest already shortened with `...`, as they came. Nothing is redacted: no secrets, tokens or URLs appear (the `/tmp/claude-0/...` paths are pytest temp directories).

| ID | Guarded element | Axis | Proving node (in `test_head_coverage_rewritten_below_2561.py`) |
|---|---|---|---|
| E-tree | `head_coverage._ignored_reason`, the `other-tree` decision (`head_coverage.py:457`) | a second base whose tree differs from the base's is never tried, so a commit of the layer's own history never lets a dropped change read proven | `test_a_base_at_review_from_the_layers_own_history_never_lets_a_dropped_change_read_proven` |
| E-read | `head_coverage._ignored_reason`, the `unreadable` and `no-merge-base` decisions (`head_coverage.py:452`, `:454`, `:460`) | a second base git cannot read, or that has no merge base with X, is never tried | `test_a_base_at_review_git_has_no_object_for_is_ignored[straightened]` |
| E-ignore | `head_coverage._check_rewritten`, the returns that carry the ignored lines (`head_coverage.py:422`, `:445`) | a second base that is ignored never changes the answer from the check's own without it | `test_a_cascading_rebase_onto_a_main_that_moved_reads_proven_and_the_old_head_is_ignored` |
| E-xbase | `returning_review.changed_files`, the reviewed-side diff (`returning_review.py:229`) | the reviewed change is read against the second base, so a file whose reconstruction cannot run (a deletion) is compared on its own change | `test_a_file_the_upper_layer_deletes_after_the_lower_layer_edited_it_reads_proven_against_the_second_base` |
| E-fork | `returning_review._merge_reproduces_head`, the fork (`returning_review.py:196`) | the three-way merge forks at the merge base of X and the second base | `test_a_layer_below_fixed_after_the_review_is_reconstructed_from_the_second_fork` |

**Disclosure — the order's expected red for E-xbase did not hold, and the proving node differs.** The order named `T1`'s `[lower_head]` case (`test_a_straightened_stack_reads_needs_review_without_the_input_and_proven_with_it`) as E-xbase's red. With the E-xbase neutralization in place that node passed (`1 passed in 0.39s`): on T1 the head's tree equals X's, so the reconstruction with the second fork (E-fork) proves the file alone, and E-xbase is not discriminated there. A case where reconstruction cannot run (X holds no blob: the upper layer deletes a file the lower layer edited) does discriminate it, so one test was added to the new file for that (`test_a_file_the_upper_layer_deletes_...`), and it is E-xbase's proving node. The inverse also holds: E-fork is discriminated by T5 only (T1 proves by text equality under E-fork's neutralization).

**Disclosure — E-read is one element with three edits.** `_ignored_reason` has two decisions on git reads (the tree read and the merge-base read). Neutralizing the tree-read decision alone leaves the tree-equality decision (E-tree) to catch an object-less value as `other-tree`, and neutralizing it with the merge-base decision alone leaves the tree-read decision. All three edits below are applied together, so a failed read counts as an equal tree and no read decides. The red shown is the no-object case on the straightened fixture, where the bare answer is `needs-review`; the same node on the cascaded fixture (`[cascaded]`) and the other converted nodes were not run under the neutralization. The `git`-seam cases (a failed tree read, a failed merge base) were not separately neutralized: they are pinned passing by `test_a_failed_tree_read_is_ignored` and `test_a_base_at_review_with_no_merge_base_is_ignored`, each on both fixtures, and not shown to bite one by one.

**Disclosure — E-ignore is proved by one neutralization.** The step-4 return (the bare answer stands when it proves or no value is valid) and the step-5 return (a valid value's result carries the ignored lines) are one rule, and the neutralization below, which returns `needs-review` whenever any value is ignored, turns both red; the red shown is on the step-4 path (the cascading-rebase node, where the bare answer is `proven`). The step-5 path is pinned passing by `test_an_ignored_value_beside_a_valid_one_that_proves_reads_proven_with_both_lines` and was not shown red by itself.

**Not neutralized (the unproven part of this record):** the `input-invalid` refusal of a non-sha value (step 4(a)), the normalisation of `base_at_review` (a string, a tuple, an odd type), the choice among several valid second bases (the first that proves, else `first` if it is judgement, else the first judgement, else the first valid value's result) and the unchanged returns for an unusable record or a head that is X. They are pinned passing by `test_a_base_at_review_that_is_no_sha_reads_input_invalid`, `test_two_successive_straightenings_prove_when_every_old_head_of_the_layer_below_is_given`, `test_no_input_or_an_unneeded_one_leaves_the_answer_as_it_was` and `test_an_unusable_record_or_a_head_that_is_x_gets_no_ignored_line`, and were not run under a neutralization.

---

## E-tree — the `other-tree` decision

**axis:** a second base whose tree differs from the base's tree is never tried.

**neutralization** (`head_coverage.py:457`, a differing tree counts as valid):
```python
-    if tree != base_tree:
+    if False and tree != base_tree:
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/i2561c-pyc -m pytest "plugins/superheroes/lib/tests/test_head_coverage_rewritten_below_2561.py::test_a_base_at_review_from_the_layers_own_history_never_lets_a_dropped_change_read_proven" -q -p no:cacheprovider` (exit 1)
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_base_at_review_from_the_layers_own_history_never_lets_a_dropped_change_read_proven _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-15/test_a_base_at_review_from_the0')

    def test_a_base_at_review_from_the_layers_own_history_never_lets_a_dropped_change_read_proven(tmp_path):
        # axis: a second base whose tree differs from the base's tree is never tried, so a commit from the layer's own history never lets a dropped change read proven — see bite-proof record i2561_head_coverage_rewritten_below (E-tree)
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
        bare = run_check(repo, b, record, head)
        assert bare["answer"] == "needs-review", bare
        got = run_check(repo, b, record, head, base_at_review=[p])
>       assert got["answer"] == "needs-review", got
E       AssertionError: {'answer': 'proven', 'why': ["own-change-unchanged: git shows the pull request's own change at the head equals the rev...ee"], 'certified': '2d9253674ed3074318783094c79619a9f094c303', 'head': '86b78d1268733e2157e73c7a11a3885ad42fa8a5', ...}
E       assert 'proven' == 'needs-review'
E         
E         - needs-review
E         + proven

/home/user/wt-2561/plugins/superheroes/lib/tests/test_head_coverage_rewritten_below_2561.py:263: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_head_coverage_rewritten_below_2561.py::test_a_base_at_review_from_the_layers_own_history_never_lets_a_dropped_change_read_proven
1 failed in 0.54s
```

**restore:** the inverse Edit, `if False and tree != base_tree:` back to `if tree != base_tree:`.

**restore receipt** (the Grep tool over `head_coverage.py` for `tree != base_tree|False and`, after the restore):
```
456:    if tree != base_tree:
```
(That Grep ran before the second E-ignore axis line was added above it at 444, so the final line number of the same line is 457, as in the table.)

**raw green:** same command (exit 0)
```
.                                                                        [100%]
1 passed in 1.08s
```

## E-read — the `unreadable` and `no-merge-base` decisions

**axis:** a second base git cannot read (tree), or that has no merge base with X, is never tried.

**neutralization** (`head_coverage.py:452`, `:454`, `:460`: a failed tree read counts as the base's tree, and neither read decides):
```python
-    tree = _tree_of(run, value)
+    tree = _tree_of(run, value) or base_tree
-    if base_tree is None or tree is None:
+    if False and (base_tree is None or tree is None):
-    if code != 0 or not returning_review._is_sha(text.strip() if isinstance(text, str) else ""):
+    if False and (code != 0 or not returning_review._is_sha(text.strip() if isinstance(text, str) else "")):
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/i2561c-pyc -m pytest "plugins/superheroes/lib/tests/test_head_coverage_rewritten_below_2561.py::test_a_base_at_review_git_has_no_object_for_is_ignored[straightened]" -q -p no:cacheprovider` (exit 1)
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_a_base_at_review_git_has_no_object_for_is_ignored[straightened] _____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-17/test_a_base_at_review_git_has_0')
kind = 'straightened'

    @pytest.mark.parametrize("kind", ["straightened", "cascaded"])
    def test_a_base_at_review_git_has_no_object_for_is_ignored(tmp_path, kind):
        # axis: a second base git cannot read is never tried, so the answer is the bare check's, whether it reads needs-review or proven — see bite-proof record i2561_head_coverage_rewritten_below (E-read)
        repo = TR.Repo(tmp_path)
        sc = scenario(repo, kind)
        record = TR.earlier_record(sc["x"])
        bare = run_check(repo, sc["base"], record, sc["head"])
        assert bare["answer"] == sc["bare"], bare
        got = run_check(repo, sc["base"], record, sc["head"], base_at_review=[NO_OBJECT])
>       assert_ignored(bare, got, (NO_OBJECT, "unreadable"))

/home/user/wt-2561/plugins/superheroes/lib/tests/test_head_coverage_rewritten_below_2561.py:287: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

bare = {'answer': 'needs-review', 'why': ['behaviour-change: not only prose or comment lines: src/shared.py'], 'certified': '387cf5699b7a7d8a65af7f084f14206ca6be15e8', 'head': '4b4b87343f530b4680143e70e78577d3c523a93a', ...}
got = {'answer': 'needs-review', 'why': ['diff-unreadable: git could not produce the diff of the certified commit or of the ...ee"], 'certified': '387cf5699b7a7d8a65af7f084f14206ca6be15e8', 'head': '4b4b87343f530b4680143e70e78577d3c523a93a', ...}
ignored = (('0123456789abcdef0123456789abcdef01234567', 'unreadable'),)

    def assert_ignored(bare, got, *ignored):
        """``got`` is ``bare`` in every field but ``why``, which is the bare ``why`` plus one ignored line per
        ``(value, reason)`` given, in order."""
>       assert {k: v for k, v in got.items() if k != "why"} == {k: v for k, v in bare.items() if k != "why"}, (bare, got)
E       AssertionError: ({'answer': 'needs-review', 'why': ['behaviour-change: not only prose or comment lines: src/shared.py'], 'certified': ...e"], 'certified': '387cf5699b7a7d8a65af7f084f14206ca6be15e8', 'head': '4b4b87343f530b4680143e70e78577d3c523a93a', ...})
E       assert {'answer': 'n...6364dde', ...} == {'answer': 'n...6364dde', ...}
E         
E         Omitting 7 identical items, use -vv to show
E         Differing items:
E         {'files': []} != {'files': ['src/shared.py']}
E         {'commits': []} != {'commits': [{'sha': '4b4b87343f530b4680143e70e78577d3c523a93a', 'author': 't@example.com'}]}
E         Use -v to get more diff

/home/user/wt-2561/plugins/superheroes/lib/tests/test_head_coverage_rewritten_below_2561.py:152: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_head_coverage_rewritten_below_2561.py::test_a_base_at_review_git_has_no_object_for_is_ignored[straightened]
1 failed in 0.51s
```

**restore:** the three inverse Edits, each undoing its line above.

**restore receipt** (the Grep tool over `head_coverage.py` for `tree = _tree_of\(run, value\)|if base_tree is None or tree is None|if code != 0 or not returning_review|False and`, after the restore; no `False and` remains):
```
452:    tree = _tree_of(run, value)
454:    if base_tree is None or tree is None:
460:    if code != 0 or not returning_review._is_sha(text.strip() if isinstance(text, str) else ""):
```

**raw green:** same command (exit 0)
```
.                                                                        [100%]
1 passed in 0.43s
```

## E-ignore — an ignored second base never changes the answer

**axis:** a second base that is ignored never changes the answer from the check's own without it.

**neutralization** (before `head_coverage.py:422`, the old refusal restored: needs-review whenever any value is ignored; inserted as two lines before the step-4 return):
```python
+    if ignored:
+        return _needs_review(_result(base, head, x), WHY_BASE_AT_REVIEW_IGNORED, "a base at review is ignored")
     if first["answer"] == PROVEN or not valid:
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/i2561c-pyc -m pytest "plugins/superheroes/lib/tests/test_head_coverage_rewritten_below_2561.py::test_a_cascading_rebase_onto_a_main_that_moved_reads_proven_and_the_old_head_is_ignored" -q -p no:cacheprovider` (exit 1)
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_cascading_rebase_onto_a_main_that_moved_reads_proven_and_the_old_head_is_ignored _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-19/test_a_cascading_rebase_onto_a0')

    def test_a_cascading_rebase_onto_a_main_that_moved_reads_proven_and_the_old_head_is_ignored(tmp_path):
        # axis: a layer below rebased onto a main that moved changes its tree, so the old head is ignored and the bare check's proven answer stands — see bite-proof record i2561_head_coverage_rewritten_below (E-ignore)
        repo = TR.Repo(tmp_path)
        c = cascaded(repo)
        record = TR.earlier_record(c["x"])
        bare = run_check(repo, c["b"], record, c["h"])
        assert bare["answer"] == "proven", bare
        got = run_check(repo, c["b"], record, c["h"], base_at_review=[c["lower"]])
>       assert got["answer"] == "proven", got
E       AssertionError: {'answer': 'needs-review', 'why': ['base-at-review-ignored: a base at review is ignored'], 'certified': '06995b3abd94fc45173059908a6fe60313904c9f', 'head': '7f93f679280eee9c81a4104d5459e0c02220aba2', ...}
E       assert 'needs-review' == 'proven'
E         
E         - proven
E         + needs-review

/home/user/wt-2561/plugins/superheroes/lib/tests/test_head_coverage_rewritten_below_2561.py:336: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_head_coverage_rewritten_below_2561.py::test_a_cascading_rebase_onto_a_main_that_moved_reads_proven_and_the_old_head_is_ignored
1 failed in 0.41s
```

**restore:** the inverse Edit, deleting the two inserted lines.

**restore receipt** (the Grep tool over `head_coverage.py` for `if ignored:|a base at review is ignored|if first\["answer"\] == PROVEN or not valid`, after the restore; the two inserted lines are gone):
```
422:    if first["answer"] == PROVEN or not valid:
```

**raw green:** same command (exit 0)
```
.                                                                        [100%]
1 passed in 0.34s
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
