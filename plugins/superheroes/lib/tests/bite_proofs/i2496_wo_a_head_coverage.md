# Issue 2496 (WO-A) bite-proof — the head-coverage check answers proven only when git shows it, judgement only for prose or comments by the builder, and needs-review for everything else

**Provenance:** implementer WO-A (order `wo-a-2496`), recording the guards of `lib/head_coverage.py`, proved by `lib/tests/test_head_coverage_2496.py`. Worktree `/home/user/wt-2496-a`, base `ff438e43c6209be7ca9e5689c9493af081b812b0` plus this dispatch's uncommitted work.

Declared guarded elements (the order's own list, E-recon, E-copy, E-judge, E-author, E-fail; the order named the neutralizations by element, not by text, so the neutralization chosen for each is stated below). The census (the Grep tool, pattern `bite-proof record i2496`, over `plugins/superheroes/lib`) prints the axis line of each element in the code:

```
plugins/superheroes/lib/head_coverage.py:188:        # axis: a non-prose file qualifies only when every added and removed line is blank or a comment of its own language, so a changed assertion or code line never reads judgement — see bite-proof record i2496_wo_a_head_coverage (E-judge)
plugins/superheroes/lib/head_coverage.py:254:        # axis: a fault of any kind reads needs-review, never an answer that covers the head — see bite-proof record i2496_wo_a_head_coverage (E-fail)
plugins/superheroes/lib/head_coverage.py:286:        # axis: a file is reconstructed only when a clean three-way merge of X, the fork and the base reproduces the head blob byte for byte, so a hand-resolved file stays changed — see bite-proof record i2496_wo_a_head_coverage (E-recon)
plugins/superheroes/lib/head_coverage.py:295:        # axis: a proof entry counts only when git re-validates it at the head; the entry's own word proves nothing — see bite-proof record i2496_wo_a_head_coverage (E-copy)
plugins/superheroes/lib/head_coverage.py:323:    # axis: a judgement answer needs the builder to have authored every new commit; another author, an unreadable author or no commit to name reads needs-review — see bite-proof record i2496_wo_a_head_coverage (E-author)
```

Each element was neutralized with one targeted Edit and restored with the inverse Edit; no `git checkout`, `restore`, `reset` or `stash` was used. Every red run is the one command `scripts/pinned-python -B -X pycache_prefix=/tmp/wo-a-pyc -m pytest "<node id>" -q -p no:cacheprovider` over the exact node id, with the neutralization in place. Each capture is the runner's whole output for that run apart from the `UV_NATIVE_TLS` deprecation warning line (the first line of each real output), which is left out; nothing else is trimmed. Nothing is redacted: no secrets, tokens or URLs appear (the `/tmp/claude-0/...` paths are pytest temp directories).

**Disclosure — shared green (the order's 10-command budget).** The order's budget (10 invocations, red and green runs for five elements inside it, and a baseline run) cannot hold ten separate red-and-green runs plus a baseline. Each element has its own red run (five runs). The greens are one shared run after the last restore, over all four named files, which includes each element's proving node (`196 passed`, below). No interim green was run between one element's restore and the next element's neutralization; the restore receipt of each element is the restored line quoted back (the Grep over the five guarded lines after the last restore, below). This disclosure is unadjudicated: it travels to the next independent reader of the record.

| ID | Guarded element | Axis | Proving test (node id, in `plugins/superheroes/lib/tests/test_head_coverage_2496.py`) |
|---|---|---|---|
| E-recon | `head_coverage._check`, the reconstruction proof (`head_coverage.py:287`) | a file is reconstructed only when git's three-way merge reproduces the head blob, so a hand-resolved file stays changed | `test_row_3_a_hand_resolved_conflict_reads_needs_review` |
| E-copy | `head_coverage._check`, the copy re-validation (`head_coverage.py:296`) | a proof entry counts only when git re-validates it at the head | `test_a_proof_entry_whose_sha256_does_not_match_the_head_blob_proves_nothing` |
| E-judge | `head_coverage._section_qualifies`, the body-line test (`head_coverage.py:189`) | a non-prose file qualifies for judgement only by blank and comment lines | `test_a_changed_test_assertion_reads_needs_review` |
| E-author | `head_coverage._check`, `authors_ok` (`head_coverage.py:324`) | a judgement answer needs every new commit to be the builder's | `test_a_commit_by_another_author_that_only_edits_markdown_reads_needs_review` |
| E-fail | `head_coverage.check`, the total wrapper (`head_coverage.py:253`) | a fault of any kind reads needs-review; the check never raises | `test_an_exception_anywhere_in_the_check_reads_needs_review` |

Not separately neutralized (the unproven part of this record):

- E-recon: only the permissive direction (every file counted as reconstructed) was neutralized. The disabled direction (no file ever reconstructed) would turn `test_row_2_*`-style reconstruction cases (`test_a_clean_base_update_inside_the_hunk_context_reads_proven_by_reconstruction_but_decide_still_names_the_file` and `test_row_4_the_lower_layer_merged_up_reads_proven_on_this_layers_own_diff`) red by reasoning, but was not run.
- E-judge: the body-line test is the neutralized element. The rest of `_section_qualifies` (the binary, mode-change, rename and copy refusals, the missing-file refusal, the `#!`/`//go:` directive refusal, the empty-hunk refusal for non-prose files, the prose-suffix rule) are **unproven** here as separate guards; the `.md` qualification is pinned passing by `test_row_7_*` and `test_a_commit_by_another_author_*`, not shown to bite.
- E-author: `authors_ok` as a whole is neutralized. Its legs (commits unreadable, builder unreadable, no commit named, an author that differs) are not separately neutralized; `test_authors_git_cannot_read_read_needs_review` pins the unreadable leg passing and was not run under a neutralization.
- E-copy: the whole call is neutralized (the entries are trusted as given). The restriction of relied-on entries to still-changed files and the `proof` shapes `_copies_of` accepts are **unproven** here.
- E-fail: the `except` clause as a whole. The `_certified` guard (`ok` not true, `abandoned` present) and the input-sha guard (`input-invalid`) are not among the declared elements and are not neutralized; they are pinned passing by `test_a_malformed_record_reads_needs_review`, `test_an_abandoned_record_*` and `test_a_garbage_head_reads_needs_review`.
- `outcome` (the pure function) is not a guarded element of this record; its table is pinned by the `test_row_12_*`, `test_row_13_*`, `test_row_15_*`, `test_row_16_*` tests and was not neutralized.

---

## E-recon — the reconstruction proof

**axis:** a file is reconstructed only when git's three-way merge of X's blob, the fork blob and the base blob reproduces the head blob byte for byte, so a hand-resolved file stays changed.

**neutralization** (`head_coverage.py:287`, `_check`: every changed file counted as reconstructed):
```python
-        if returning_review.merge_reproduces_head(run, base, x, head, path):
+        if True or returning_review.merge_reproduces_head(run, base, x, head, path):
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/wo-a-pyc -m pytest "plugins/superheroes/lib/tests/test_head_coverage_2496.py::test_row_3_a_hand_resolved_conflict_reads_needs_review" -q -p no:cacheprovider`
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_row_3_a_hand_resolved_conflict_reads_needs_review ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-2/test_row_3_a_hand_resolved_con0')

    def test_row_3_a_hand_resolved_conflict_reads_needs_review(tmp_path):
        # axis: a file is reconstructed only when the three-way merge reproduces the head blob, so a hand resolution stays changed — see bite-proof record i2496_wo_a_head_coverage (E-recon)
        repo = TR.Repo(tmp_path)
        base, reviewed, earlier = TR.returning(repo, first={SHARED: pr_edit_text()})
        moved, head = _conflicted_catch_up(repo, pr_edit_text("resolved = 1\n"))
        got = run_check(repo, moved, earlier, head)
>       assert got["answer"] == "needs-review" and got["files"] == [SHARED] and got["reconstructed"] == []
E       AssertionError: assert ('proven' == 'needs-review'
E         
E         - needs-review
E         + proven)

/home/user/wt-2496-a/plugins/superheroes/lib/tests/test_head_coverage_2496.py:128: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_head_coverage_2496.py::test_row_3_a_hand_resolved_conflict_reads_needs_review
1 failed in 0.38s
```
**restore:** the inverse Edit (`if True or ` removed).

**restore receipt:** `head_coverage.py:287` read back: `        if returning_review.merge_reproduces_head(run, base, x, head, path):`

**raw green:** the shared green run below.

---

## E-copy — the copy re-validation

**axis:** a proof entry counts only when git re-validates it at the head; the entry's own word proves nothing.

**neutralization** (`head_coverage.py:296`, `_check`: the entries trusted as given):
```python
-        valid = review_record.revalidated_copies(entries, os.fspath(repo_root), base, head) if entries else []
+        valid = entries
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/wo-a-pyc -m pytest "plugins/superheroes/lib/tests/test_head_coverage_2496.py::test_a_proof_entry_whose_sha256_does_not_match_the_head_blob_proves_nothing" -q -p no:cacheprovider`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_proof_entry_whose_sha256_does_not_match_the_head_blob_proves_nothing __

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-3/test_a_proof_entry_whose_sha250')

    def test_a_proof_entry_whose_sha256_does_not_match_the_head_blob_proves_nothing(tmp_path):
        # axis: a proof entry counts only when git re-validates it at the head — see bite-proof record i2496_wo_a_head_coverage (E-copy)
        repo = TR.Repo(tmp_path)
        base, reviewed, earlier = TR.returning(repo)
        repo.write("vendor/lib.py", TR.numbered("vendored", 40))
        repo.commit("vendor a copy")
        liar = {"file": "vendor/lib.py", "source": "upstream/lib.py", "sha256": "0" * 64}
        got = run_check(repo, base, earlier, proof=[liar])
>       assert got["answer"] == "needs-review" and got["copies"] == [] and got["files"] == ["vendor/lib.py"]
E       AssertionError: assert ('proven' == 'needs-review'
E         
E         - needs-review
E         + proven)

/home/user/wt-2496-a/plugins/superheroes/lib/tests/test_head_coverage_2496.py:297: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_head_coverage_2496.py::test_a_proof_entry_whose_sha256_does_not_match_the_head_blob_proves_nothing
1 failed in 1.80s
```

**restore:** the inverse Edit (`valid = entries` back to the `revalidated_copies` call).

**restore receipt:** `head_coverage.py:296` read back: `        valid = review_record.revalidated_copies(entries, os.fspath(repo_root), base, head) if entries else []`

**raw green:** the shared green run below.

---

## E-judge — the prose and comment qualification

**axis:** a non-prose file qualifies for judgement only when every added and removed body line is blank or a comment of its own language; a changed assertion or code line never reads judgement.

**neutralization** (`head_coverage.py:189`, `_section_qualifies`: the body-line test never refuses):
```python
-        if text and not (text.startswith(marker) and not text.startswith(_DIRECTIVE_PREFIXES)):
+        if False and text and not (text.startswith(marker) and not text.startswith(_DIRECTIVE_PREFIXES)):
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/wo-a-pyc -m pytest "plugins/superheroes/lib/tests/test_head_coverage_2496.py::test_a_changed_test_assertion_reads_needs_review" -q -p no:cacheprovider`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_a_changed_test_assertion_reads_needs_review _______________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-5/test_a_changed_test_assertion_0')

    def test_a_changed_test_assertion_reads_needs_review(tmp_path):
        # axis: a non-prose file qualifies for judgement only by blank and comment lines — see bite-proof record i2496_wo_a_head_coverage (E-judge)
        repo = TR.Repo(tmp_path)
        test_file = "tests/test_app.py"
        base, reviewed, earlier = TR.returning(repo, first={test_file: "def test_f():\n    assert f() == 1\n"})
        repo.write(test_file, "def test_f():\n    assert f() == 2\n")
        repo.commit("fix the expected value")
        got = run_check(repo, base, earlier)
>       assert got["answer"] == "needs-review" and got["hunks"] == [] and tokens(got) == [HC.WHY_BEHAVIOUR_CHANGE]
E       AssertionError: assert ('judgement' == 'needs-review'
E         
E         - needs-review
E         + judgement)

/home/user/wt-2496-a/plugins/superheroes/lib/tests/test_head_coverage_2496.py:237: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_head_coverage_2496.py::test_a_changed_test_assertion_reads_needs_review
1 failed in 0.44s
```

**restore:** the inverse Edit (`False and ` removed).

**restore receipt:** `head_coverage.py:189` read back: `        if text and not (text.startswith(marker) and not text.startswith(_DIRECTIVE_PREFIXES)):`

**raw green:** the shared green run below.

---

## E-author — the author check

**axis:** a judgement answer needs the builder to have authored every new commit; another author reads needs-review.

**neutralization** (`head_coverage.py:324`, `_check`: the author test always passes):
```python
-    authors_ok = commits is not None and builder is not None and all(c["author"].lower() == builder.lower() for c in commits)
+    authors_ok = True or commits is not None and builder is not None and all(c["author"].lower() == builder.lower() for c in commits)
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/wo-a-pyc -m pytest "plugins/superheroes/lib/tests/test_head_coverage_2496.py::test_a_commit_by_another_author_that_only_edits_markdown_reads_needs_review" -q -p no:cacheprovider`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_commit_by_another_author_that_only_edits_markdown_reads_needs_review __

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-6/test_a_commit_by_another_autho0')

    def test_a_commit_by_another_author_that_only_edits_markdown_reads_needs_review(tmp_path):
        # axis: a judgement answer needs every new commit to be the builder's — see bite-proof record i2496_wo_a_head_coverage (E-author)
        repo = TR.Repo(tmp_path)
        base, reviewed, earlier = TR.returning(repo, first={APP: TR.numbered("app", 100), "docs/notes.md": "notes\n"})
        repo.write("docs/notes.md", "notes\nmore notes\n")
        commit_by_other(repo, "docs by someone else")
        got = run_check(repo, base, earlier)
>       assert got["answer"] == "needs-review" and tokens(got) == [HC.WHY_OTHER_AUTHOR] and got["hunks"] == []
E       AssertionError: assert ('judgement' == 'needs-review'
E         
E         - needs-review
E         + judgement)

/home/user/wt-2496-a/plugins/superheroes/lib/tests/test_head_coverage_2496.py:343: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_head_coverage_2496.py::test_a_commit_by_another_author_that_only_edits_markdown_reads_needs_review
1 failed in 0.43s
```

**restore:** the inverse Edit (`True or ` removed).

**restore receipt:** `head_coverage.py:324` read back: `    authors_ok = commits is not None and builder is not None and all(c["author"].lower() == builder.lower() for c in commits)`

**raw green:** the shared green run below.

---

## E-fail — the total wrapper

**axis:** a fault of any kind reads needs-review; the check never raises.

**neutralization** (`head_coverage.py:253`, `check`: the handler catches an exception no check raises):
```python
-    except Exception as exc:  # total: a fault nobody foresaw is still a review owed
+    except KeyboardInterrupt as exc:  # total: a fault nobody foresaw is still a review owed
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/wo-a-pyc -m pytest "plugins/superheroes/lib/tests/test_head_coverage_2496.py::test_an_exception_anywhere_in_the_check_reads_needs_review" -q -p no:cacheprovider`
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_an_exception_anywhere_in_the_check_reads_needs_review __________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-7/test_an_exception_anywhere_in_0')

    def test_an_exception_anywhere_in_the_check_reads_needs_review(tmp_path):
        # axis: the check never raises; a fault of any kind reads needs-review — see bite-proof record i2496_wo_a_head_coverage (E-fail)
        repo = TR.Repo(tmp_path)
        base, reviewed, earlier = TR.returning(repo)
        head = repo.git("rev-parse", "main")
    
        def exploding(argv):
            raise RuntimeError("git blew up")
    
>       got = HC.check(repo.root, base, earlier, head, git=exploding)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2496-a/plugins/superheroes/lib/tests/test_head_coverage_2496.py:454: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt-2496-a/plugins/superheroes/lib/head_coverage.py:252: in check
    return _check(repo_root, base, record, head, proof, builder_author, git)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2496-a/plugins/superheroes/lib/head_coverage.py:277: in _check
    changed = returning_review.changed_files(run, base, x, head)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2496-a/plugins/superheroes/lib/returning_review.py:224: in changed_files
    code_a, reviewed_text = run(["diff", *diff_args, "%s...%s" % (base, last_reviewed)])
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

argv = ['diff', '--no-ext-diff', '--no-textconv', '--no-color', '-M', '-U3', ...]

    def exploding(argv):
>       raise RuntimeError("git blew up")
E       RuntimeError: git blew up

/home/user/wt-2496-a/plugins/superheroes/lib/tests/test_head_coverage_2496.py:452: RuntimeError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_head_coverage_2496.py::test_an_exception_anywhere_in_the_check_reads_needs_review
1 failed in 0.37s
```

**restore:** the inverse Edit (`KeyboardInterrupt` back to `Exception`).

**restore receipt:** `head_coverage.py:253` read back: `    except Exception as exc:  # total: a fault nobody foresaw is still a review owed`; the Grep over `True or|False and|KeyboardInterrupt` in `head_coverage.py` after the last restore matched nothing.

**raw green:** the shared green run below.

---

## The shared green (after the last restore, every neutralization undone)

`scripts/pinned-python -B -X pycache_prefix=/tmp/wo-a-pyc -m pytest plugins/superheroes/lib/tests/test_head_coverage_2496.py plugins/superheroes/lib/tests/test_returning_review_c1l11.py plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py plugins/superheroes/lib/tests/test_c1l11e_catch_up.py -q -p no:cacheprovider`
```
........................................................................ [ 36%]
........................................................................ [ 73%]
....................................................                     [100%]
196 passed in 19.60s
```

---

## Added at review round 1: E-mode and E-lex (2026-11-16, typed and run by the build session)

Two guards the round-1 review found missing, each added at the loop's apply-fixes step in commit b9ff148f and proved in a
detached probe worktree at that commit by one targeted Edit and its inverse. Captures keep only the assertion lines and the
summary line (the full tracebacks are long and repeat the same result dict); nothing is redacted.

### E-mode — a file whose mode changed is never reconstructed

**guard:** `head_coverage.py:351`, `same_mode = modes[path][0] is not None and modes[path][0] == modes[path][1]`.

**neutralization:** `same_mode = True`.

**raw red:** `scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest "plugins/superheroes/lib/tests/test_head_coverage_lexical_modes_2496.py::test_an_executable_bit_change_after_review_reads_needs_review" -q -p no:cacheprovider`
```
E       assert 'proven' == 'needs-review'
E       assert 'proven' == 'needs-review'
2 failed in 0.51s
```

**restore:** the inverse Edit.

### E-lex — a comment-looking line counts only where the tokenizer reads a comment

**guard:** `head_coverage.py:254`, `return _lexically_insignificant(run, x, head, section)`.

**neutralization:** `return True`.

**raw red:** `scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest plugins/superheroes/lib/tests/test_head_coverage_lexical_modes_2496.py -k inside_a_python_string -q -p no:cacheprovider`
```
E       assert ('judgement' == 'needs-review'
E       assert 'judgement' == 'needs-review'
2 failed, 5 deselected in 2.26s
```

**restore:** the inverse Edit; `git status --short` in the probe worktree printed nothing after it.

**green (both restored):** `scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest plugins/superheroes/lib/tests/test_head_coverage_lexical_modes_2496.py -q -p no:cacheprovider`
```
7 passed in 3.00s
```

**Not neutralized here:** the copy-mode condition (`wanted` in `_check`, pinned by `test_a_copy_proof_for_a_file_whose_mode_changed_proves_nothing`), and `_changed_lines`' hunk walk (pinned by the string and comment tests).

---

## Added at review round 2: E-mode-read, E-fstring and E-author-all (2026-11-16, implementer order `wo-h-2543`)

**Provenance:** implementer WO-H (order `wo-h-2543`, issue 2543, rework 1 of the review-fix surface `lib/head_coverage.py`), worktree `/home/user/wt-2543`, base commit 7db98ccc plus this dispatch's uncommitted work. The order declared three guarded elements, E-mode-read, E-fstring and E-author-all, and named the red detector for each. Each element was neutralized with one targeted Edit and restored with its inverse Edit; no `git checkout`, `restore`, `reset` or `stash` was used. Every run is `scripts/pinned-python -B -X pycache_prefix=/tmp/wo-h-pyc -m pytest <file> -k <test function name> -q -p no:cacheprovider`, selected with `-k` on the exact function name as the order directed (not by a `::` node id). Captures keep the assertion lines and the summary line (the tracebacks repeat the same fixture and the result dict); the `UV_NATIVE_TLS` deprecation warning line is left out. Nothing is redacted: no secrets, tokens or URLs appear.

The axis lines in the code (census: the Grep tool, pattern `bite-proof record i2496_wo_a_head_coverage (E-mode-read|E-fstring|E-author-all)`, over `plugins/superheroes/lib`):

```
plugins/superheroes/lib/head_coverage.py   _mode:                # axis: a mode git could not read is not an absent file ... (E-mode-read)
plugins/superheroes/lib/head_coverage.py   _insignificant_lines: # axis: every line from an f-string's start row to its matching end row is significant ... (E-fstring)
plugins/superheroes/lib/tests/test_head_coverage_2496.py:        # axis: a judgement answer needs EVERY new commit to be the builder's ... (E-author-all)
```

**Disclosure — shared final green.** Each element has its own red run and its own green run straight after its restore (six runs). One more run, over the six files the order names, was made after the last restore: `212 passed in 19.07s`. The test-command budget was 10 invocations; 8 were used.

### E-mode-read — a mode git could not read is not an absent file

**guarded element:** `head_coverage.py` `_mode` (the None / `ABSENT` / mode-string result) and its two consumers in `_check`, the reconstruction `same_mode` line and the copy `wanted` filter, both of which ask `_real_mode`. **axis:** a failed `ls-tree` keeps the file changed; it never passes the equality clause or the new-and-plain clause.

**neutralization** (`_real_mode`, the one place both consumers decide whether a mode is real; a None from a failed read then counts as a mode again, so two failed reads are equal and pass, as before the fix):
```python
-    return isinstance(mode, str)
+    return True
```

**raw red:** `... -m pytest plugins/superheroes/lib/tests/test_head_coverage_lexical_modes_2496.py -k test_a_failed_mode_read_keeps_a_copied_file_changed ...`
```
>       assert got["answer"] == "needs-review" and got["copies"] == [] and copied in got["files"], got
E       AssertionError: {'answer': 'proven', 'why': ["proven-copies: 1 file(s) are copies git re-validated at the head, and the pull request's...ge"], 'certified': '60979078307b8524fa8de97d1036f8ad12ee7e54', 'head': '4684733dac38e3a8a1140420c7fb0e220696d0fa', ...}
E       assert ('proven' == 'needs-review'
E         - needs-review
E         + proven)
FAILED plugins/superheroes/lib/tests/test_head_coverage_lexical_modes_2496.py::test_a_failed_mode_read_keeps_a_copied_file_changed
1 failed, 9 deselected in 4.60s
```
The red is on the claimed axis: with every `ls-tree` failing, the copy proof drops the file and the check answers `proven`.

**restore:** the inverse Edit (`return True` back to `return isinstance(mode, str)`).

**restore receipt:** the Grep over `return isinstance\(mode, str\)` in `head_coverage.py` printed `183:    return isinstance(mode, str)`.

**raw green:** same command
```
.                                                                        [100%]
1 passed, 9 deselected in 4.57s
```

**Not neutralized, and why it matters:** changing only `_mode` to return `ABSENT` on a failed read is not red by itself. The consumers refuse two `ABSENT` modes as well (the reconstruction needs two equal real modes, and the copy filter accepts `ABSENT` only at X with `100644` at the head), so the file stays changed when both reads fail. That variant was reasoned, not run. The distinction the test guards is the real-mode test in the consumers, which is what was neutralized. A failed read at X only, with a readable `100644` head (the finding's second case), is covered by the same `_real_mode` and `is ABSENT` tests but is not separately pinned: the test fails every `ls-tree`.

### E-fstring — every line inside an f-string is significant

**guarded element:** `head_coverage.py` `_insignificant_lines`, the span marking from an `FSTRING_START` token's start row to its matching `FSTRING_END` token's end row. **axis:** a line inside any f-string, debug or not, is never a comment or blank line, so editing it never reads judgement.

**neutralization** (the span is no longer marked; the start stack is still popped):
```python
-                significant.update(range(open_starts.pop(), tok.end[0] + 1))
+                open_starts.pop()
```

**raw red:** `... -m pytest plugins/superheroes/lib/tests/test_head_coverage_lexical_modes_2496.py -k "test_a_blank_line_inside_a_debug_fstring_changes_the_value_and_reads_needs_review or test_a_blank_line_inside_a_plain_fstring_braces_reads_needs_review" ...` (both tests, the debug and the plain f-string; they share the one neutralization)
```
E       AssertionError: {'answer': 'judgement', 'why': ['prose-or-comments: every remaining difference is prose or comment lines by the builde...s)'], 'certified': '151fbe20dcce6509eb8d49c800b0e8284d823f23', 'head': '4d86dde58d302675abcd8bc47712fcd3c51ab486', ...}
E       assert ('judgement' == 'needs-review'
E         - needs-review
E         + judgement)
E       AssertionError: {'answer': 'judgement', 'why': ['prose-or-comments: every remaining difference is prose or comment lines by the builde...s)'], 'certified': '43bfc7a16622536953842c747d04e7cc206db38f', 'head': '7cf33bf26908570406e599d60311d0d89eb28e1e', ...}
E       assert ('judgement' == 'needs-review'
E         - needs-review
E         + judgement)
FAILED plugins/superheroes/lib/tests/test_head_coverage_lexical_modes_2496.py::test_a_blank_line_inside_a_debug_fstring_changes_the_value_and_reads_needs_review
FAILED plugins/superheroes/lib/tests/test_head_coverage_lexical_modes_2496.py::test_a_blank_line_inside_a_plain_fstring_braces_reads_needs_review
2 failed, 8 deselected in 2.31s
```
The red is on the claimed axis: the added blank line inside the f-string reads as a blank line, and the change reads `judgement`.

**restore:** the inverse Edit (`open_starts.pop()` back to the `significant.update(range(open_starts.pop(), tok.end[0] + 1))` call).

**restore receipt:** the Grep over `significant\.update` in `head_coverage.py` printed `221:                significant.update(range(open_starts.pop(), tok.end[0] + 1))` and `226:            significant.update(range(tok.start[0], tok.end[0] + 1))`.

**raw green:** same command
```
..                                                                       [100%]
2 passed, 8 deselected in 0.44s
```

**Not neutralized here:** nesting (an f-string inside the braces of another) is handled by the start stack and is not separately pinned by a test; the `getattr(tokenize, "FSTRING_START", None)` fallback for an interpreter without the token type is not run, since the pinned interpreter is Python 3.12.13.

### E-author-all — every new commit must be the builder's

**guarded element:** `head_coverage.py:424`, `authors_ok = ... all(c["author"].lower() == builder.lower() for c in commits)`. **axis:** a builder commit never lets an earlier commit by someone else read judgement.

**neutralization:** `all(` changed to `any(` in that line:
```python
-    authors_ok = commits is not None and builder is not None and all(c["author"].lower() == builder.lower() for c in commits)
+    authors_ok = commits is not None and builder is not None and any(c["author"].lower() == builder.lower() for c in commits)
```

**raw red:** `... -m pytest plugins/superheroes/lib/tests/test_head_coverage_2496.py -k test_a_builder_commit_after_another_authors_markdown_commit_still_reads_needs_review ...`
```
>       assert got["answer"] == "needs-review", got
E       AssertionError: {'answer': 'judgement', 'why': ['prose-or-comments: every remaining difference is prose or comment lines by the builde...s)'], 'certified': 'c096ac65d5cb2131a201bf03f2cab4b2ca211acc', 'head': '5c34ff5d832add3b6bada26f8ce90515edd8265e', ...}
E       assert 'judgement' == 'needs-review'
E         - needs-review
E         + judgement
FAILED plugins/superheroes/lib/tests/test_head_coverage_2496.py::test_a_builder_commit_after_another_authors_markdown_commit_still_reads_needs_review
1 failed, 46 deselected in 0.43s
```

**restore:** the inverse Edit (`any(` back to `all(`).

**restore receipt:** the Grep over `authors_ok = |True or|False and|any\(c\[` in `head_coverage.py` printed only `424:    authors_ok = commits is not None and builder is not None and all(c["author"].lower() == builder.lower() for c in commits)`.

**raw green:** same command
```
.                                                                        [100%]
1 passed, 46 deselected in 0.47s
```

**The shared final green (every neutralization undone):** `scripts/pinned-python -B -X pycache_prefix=/tmp/wo-h-pyc -m pytest plugins/superheroes/lib/tests/test_head_coverage_2496.py plugins/superheroes/lib/tests/test_head_coverage_lexical_modes_2496.py plugins/superheroes/lib/tests/test_head_coverage_modes_breakit.py plugins/superheroes/lib/tests/test_returning_review_c1l11.py plugins/superheroes/lib/tests/test_c1l11d_fold_returning.py plugins/superheroes/lib/tests/test_c1l11e_catch_up.py -q -p no:cacheprovider`
```
........................................................................ [ 33%]
........................................................................ [ 67%]
....................................................................     [100%]
212 passed in 19.07s
```
This disclosure is unadjudicated: it travels to the next independent reader of the record.

---

## Added at the second review session, round 1: E-rename (2026-11-16, typed and run by the build session)

**guard:** `head_coverage.py:290` in `_qualification`, the rename and copy source paths read with the changed files
(`"--", *files, *[s for s in sources if s not in files]`), together with the `moved` set in `_check` that keeps a file
moved after review out of reconstruction and copy proofs. Added at the loop's apply-fixes step in commit d4758f2d and
proved in a detached probe worktree at that commit.

**neutralization:** the pathspec cut back to `"--", *files` (destination paths only).

**raw red:** `scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest plugins/superheroes/lib/tests/test_head_coverage_lexical_modes_2496.py -k rename_after_review -q -p no:cacheprovider`
```
E       assert ('judgement' == 'needs-review'
E       assert ('judgement' == 'needs-review'
2 failed, 11 deselected in 6.62s
```

**restore:** the inverse Edit; `git status --short` in the probe worktree printed nothing after it.

**green:** `scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest plugins/superheroes/lib/tests/test_head_coverage_lexical_modes_2496.py -q -p no:cacheprovider`
```
13 passed in 1.18s
```

**Not neutralized here:** the `moved` set on its own (with the pathspec intact, the renamed section already fails qualification), pinned by the same two tests and by `test_a_file_renamed_before_review_and_edited_in_prose_after_still_reads_judgement`.

### E-rename-scope — only a move after the review brings its source paths in (second session, round 2, commit 20d2cdeb)

**guard:** `_check`, `move_sources` built only from files in `moved`, less every path a copy proof settled.

**neutralization:** `move_sources` built from every remaining file's sources, with no copy subtraction (the commit d4758f2d form).

**raw red:** `scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest plugins/superheroes/lib/tests/test_head_coverage_lexical_modes_2496.py -k copy_proven_restore -q -p no:cacheprovider`
```
E       assert ('needs-review' == 'judgement'
1 failed, 13 deselected in 0.55s
```

**restore:** the inverse Edits; `git status --short` in the probe worktree printed nothing after them. **green:** the same file, `14 passed in 4.03s`.

**Superseded in round 3 (commit 28e8dda8):** the `moved` filter on `move_sources` hid a move into a path X already held, so every remaining file's sources are read again (the copy subtraction stays), and a file that carries sources is never dropped as a copy.

### E-rename-overwrite — a move into a reviewed path still shows the source it deletes (second session, round 3)

**guard:** `_check`, `move_sources = set().union(*(sources.get(p, set()) for p in remaining))`.

**neutralization:** the round-2 form, `... for p in remaining if p in moved`.

**raw red:** `scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest plugins/superheroes/lib/tests/test_head_coverage_lexical_modes_2496.py -k reviewed_prose_path -q -p no:cacheprovider`
```
E       assert 'judgement' == 'needs-review'
1 failed, 14 deselected in 0.63s
```

**restore:** the inverse Edit; `git status --short` printed nothing. **green:** the same file, `15 passed in 4.73s`.

## Added at the second review session, round 4: E-rename-one-rule (2026-11-16, implementer order `wo-j-2543`)

### E-rename-one-rule — one rule for rename sources: read exactly when named and not settled by a copy proof

**guard:** `head_coverage.py` `_check`, the `outstanding` line, `sorted(all_sources - {c["file"] for c in result["copies"]} - set(remaining))`, with `all_sources` the union of the sources of every changed file. Axis: a source path is read exactly when some changed file names it as a rename or copy source and that path is not itself a file a copy proof settled (a `copies` entry's `file`; an entry's `source` field plays no part); a copy proof is judged on the file's own bytes and mode alone. Step 7 answers proven only when no file remains and `git diff X head -- <outstanding>` exits 0 with empty output; a non-zero exit reads needs-review (`diff-unreadable`); a non-empty diff goes to step 8, where `_qualification` reads it (also with no remaining file).

**neutralization:** `outstanding = sorted(all_sources - {c["file"] for c in result["copies"]} - set(remaining))` replaced by `outstanding = []` (no source is read).

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/wo-j-pyc -m pytest plugins/superheroes/lib/tests/test_head_coverage_lexical_modes_2496.py -k "source_deletion or outstanding" -q -p no:cacheprovider`
```
FFFF                                                                     [100%]
E       assert 'judgement' == 'needs-review'       (test_a_move_after_review_into_a_reviewed_prose_path_still_reads_the_source_deletion)
E       AssertionError: the check never read the outstanding source through the seam   (test_a_failed_read_of_the_outstanding_sources_reads_needs_review)
E       assert 'judgement' == 'needs-review'       (test_a_move_after_review_over_a_reviewed_prose_path_with_a_copy_proof_reads_the_source_deletion)
E       assert ('proven' == 'needs-review'         (test_a_move_over_a_reviewed_prose_path_that_a_copy_proof_settles_reads_the_source_deletion)
4 failed, 15 deselected in 2.52s
```
(The `E` lines are the decisive assertion line of each failure, quoted from the full output; the tracebacks between them are elided.)

**restore:** the inverse Edit, `outstanding = []` back to the `sorted(...)` expression; the line was read back from the file after it.

**green:** the same command, `4 passed, 15 deselected in 0.59s`.

**What each test pins:** the last test is the proof that bites on the step-7 path (a copy proof git re-validates settles the destination, nothing remains, the source's deletion is the only difference, and the answer reads needs-review instead of proven). The test beside it is the order's literal pure move: git's section for a pure move carries no blob line, so the copy proof is dropped and the file stays remaining; it bites on the step-8 path (judgement instead of needs-review). `test_a_copy_proven_update_of_a_reviewed_renames_destination_reads_proven` pins the opposite edge (a reviewed rename never blocks a copy proof); the neutralization leaves it green by design, because the rule that keeps it green is the removal of the round-3 copy exclusion, which the next paragraph records.

**Retired: the round-3 copy exclusion.** `wanted` in step 6 no longer carries `and not sources.get(path)`. That exclusion refused every copy proof on a file that carries sources, so a valid proof on the destination of a rename the review already read (a rename to a core module, then a copy-proven update of it) read needs-review instead of proven. It was also redundant for safety: a proof is judged on the file's own bytes and mode, and the source a move leaves behind is read by the `outstanding` rule whether or not the destination is copy-proven, so the exclusion closed no hole the rule leaves open. `path not in moved` and the mode conditions stay. Putting the exclusion back (`... if path not in moved and not sources.get(path) and (...)`) turns `test_a_copy_proven_update_of_a_reviewed_renames_destination_reads_proven` red; run with `-k copy_proven_update`:
```
E       AssertionError: {'answer': 'needs-review', 'why': ['behaviour-change: not only prose or comment lines: src/core.py'], ...
E       assert 'needs-review' == 'proven'
1 failed, 18 deselected in 2.36s
```
Restored by the inverse Edit; green is the full run of the six order files, `221 passed` (see the order's receipts).
