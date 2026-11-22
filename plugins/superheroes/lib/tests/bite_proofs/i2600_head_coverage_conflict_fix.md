# Issue 2600 bite-proof: the conflict-fix read in the head-coverage check

**Provenance:** typed and run by the WO-A2 implementer on 2026-11-21 in the build worktree. The guards are in
`lib/head_coverage.py` (`check` step 8, `_conflict_fix`, `_conflict_fix_file`, `_hunk_ranges`), proved by
`lib/tests/test_head_coverage_conflict_fix_2600.py` (the test file is never edited). Each red ran with one targeted text
edit in `head_coverage.py`, and each restore was the inverse edit; the restored line is quoted in each section. After the
last restore, a search of `head_coverage.py` for `False and`, `True or` and `NEUTRALIZED` found nothing, and
`git diff -- plugins/superheroes/lib/head_coverage.py` was empty. Each command was
`scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2600 -m pytest plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py -q -p no:cacheprovider --tb=line -k <selection>`.
The captures below are the printed output with the pytest `warning: The UV_NATIVE_TLS ...` line dropped, the blank lines and
`=== FAILURES ===` banner dropped, and the long dict reprs in each `E   AssertionError` line cut where they show `...`
(that cut is pytest's own). Nothing else is elided and nothing is redacted (the shas are those of throwaway test
repositories). The red exits are the bite-proof red halves, not failures of the order.

How the rule is built: for a head whose every new commit is the builder's two-parent merge of the base, the check rebuilds
git's automatic merge of each remaining file and lists only the lines the builder changed by hand; the guards below are
the reasons that read is refused. Most of the tests assert, through `fails_closed`, that the head reads `needs-review`
with `behaviour-change` and key for key what the check reads with `_conflict_fix` answering None. A red therefore reads
`'judgement' == 'needs-review'` at line 94 of the test file.

Several guards sit behind other guards (a second guard refuses the same head), so one neutralization turns only some of
a guard's tests red. Each section says which tests went red and which were held by another guard. One element, E-cf-nonmerge,
could not be made to go red by a single edit; its section says so.

## E-cf-nonmerge: a new commit that is not a two-parent merge is never a conflict fix

**guarded element:** `_conflict_fix`, `if len(parents) != 2: return None`. **Axis:** a plain code commit, alone or beside a
qualifying merge, keeps `needs-review`.

**neutralization (attempt 1):** `if len(parents) != 2:` became `if False and len(parents) != 2:` and `p1, p2 = parents`
became `p1, p2 = parents[0], parents[-1]` (needed so a one-parent commit does not crash the unpack).

**raw output** (`-k test_e_cf_nonmerge`):
```
..                                                                       [100%]
2 passed, 32 deselected in 2.30s
```

**neutralization (attempt 2):** the same, with `p2` taken as the base for a one-parent commit:
`p1, p2 = parents[0], (parents[-1] if len(parents) > 1 else base)`.

**raw output** (`-k test_e_cf_nonmerge`):
```
..                                                                       [100%]
2 passed, 32 deselected in 0.94s
```

**neutralization (attempt 3, two guards at once, disclosed as such):** attempt 2 plus the E-cf-clean-edit neutralization
(`if False and code == 0:` in `_conflict_fix_file`).

**raw output** (`-k test_e_cf_nonmerge`):
```
..                                                                       [100%]
2 passed, 32 deselected in 0.88s
```

**Finding: no red on this element's axis from a single edit, and none from two.** With the guard off, a plain commit still
reads `needs-review`. Attempt 1 reads the parents as (X, X), whose second parent is not an ancestor of the base, so
E-cf-side would refuse it (inferred from the code, not separately measured). Attempts 2 and 3 are measured: the tests stay
green with the second parent read as the base, and still green with E-cf-clean-edit also off, so some later check holds that
the implementer did not identify within the command budget. So the non-merge guard is redundant with later guards for these
two tests.
The element is therefore **unproven as placed** by this test file: the tests pin the answer, not this guard, and the
protection of the guard itself is unverified. What would make it provable: a plain commit whose content passes every later
check (not constructible from the cases in this file, which both change code in a file git would merge differently).
**restore:** the inverse edits; restored lines: `        if len(parents) != 2:` then `            return None` then
`        p1, p2 = parents`. **green** (the three tests below run together, see E-cf-untouched): `4 passed, 30 deselected in 1.41s`.

## E-cf-side: the second parent is the base or an ancestor of it

**guarded element:** `_conflict_fix`, `if code != 0: return None` after `merge-base --is-ancestor p2 base`. **Axis:** a merge
of a side branch is never read as the base brought in.

**neutralization:** `if code != 0:` became `if False and code != 0:`.

**raw red** (`-k test_e_cf_side`):
```
F                                                                        [100%]
E   AssertionError: {'answer': 'judgement', 'why': ['conflict-fix: every new commit is a merge by the builder that brings the base in; the...es'], 'certified': 'e17d257dc8b28c8cbfec61c4500fc34925e27388', 'head': 'c2a53827cc7b834e8ce105d4d7cb351d09c05c52', ...}
    assert ('judgement' == 'needs-review'
/home/user/wt-2600/plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py:94: AssertionError: ...
FAILED plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py::test_e_cf_side_a_merge_of_a_side_branch_keeps_needs_review
1 failed, 33 deselected in 0.77s
```

**restore:** the inverse edit. **restore receipt**, quoted back: `        if code != 0:` then `            return None`.
**raw green:** `1 passed, 33 deselected in 0.87s`.

## E-cf-first: the first parent is the certified commit or another new commit

**guarded element:** `_conflict_fix`, `if p1 != x and p1 not in shas: return None`. **Axis:** a merge built on an older commit
that drops reviewed code is never read as a conflict fix.

**neutralization:** `if p1 != x and p1 not in shas:` became `if False and p1 != x and p1 not in shas:`.

**raw red** (`-k test_e_cf_first`):
```
F.                                                                       [100%]
E   AssertionError: {'answer': 'judgement', 'why': ['conflict-fix: every new commit is a merge by the builder that brings the base in; the...es'], 'certified': '78c25fd868a086459efc2b6e60d70205152d51eb', 'head': 'ae902364c2f7b298b4bdf2fc59eb1be4f6bc0d83', ...}
    assert ('judgement' == 'needs-review'
/home/user/wt-2600/plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py:94: AssertionError: ...
FAILED plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py::test_e_cf_first_a_merge_built_on_an_older_leg_that_drops_the_reviewed_leg_keeps_needs_review
1 failed, 1 passed, 32 deselected in 0.85s
```

On the axis: the older-leg test is red. The parents-reversed test stays green because E-cf-side refuses it first (its second
parent is the pull request's commit, not an ancestor of the base); it is not a proof of this guard.

**restore:** the inverse edit. **restore receipt**, quoted back: `        if p1 != x and p1 not in shas:`.
**raw green:** `2 passed, 32 deselected in 0.88s`.

## E-cf-author: only the builder's own merges are read

**guarded element:** `check` step 8, `may_read = authors_ok`. **Axis:** another author's merge stays `needs-review`
(`other-author`).

**neutralization:** `may_read = authors_ok` became `may_read = True`.

**raw red** (`-k test_e_cf_author`):
```
F                                                                        [100%]
E   AssertionError: {'answer': 'judgement', 'why': ['other-author: a new commit is by someone other than the builder: other@example.com', ...es'], 'certified': '6e74275a4c2f8f85c9ca3e2e73a027977366747d', 'head': 'd66123fa64b3d8fd35da641c9359dee6f38e187c', ...}
    assert ('judgement' == 'needs-review'
/home/user/wt-2600/plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py:94: AssertionError: ...
FAILED plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py::test_e_cf_author_a_merge_by_someone_other_than_the_builder_keeps_needs_review
1 failed, 33 deselected in 0.64s
```

**restore:** the inverse edit. **restore receipt**, quoted back: `        may_read = authors_ok`.
**raw green:** `1 passed, 33 deselected in 0.68s`.

## E-cf-rename: no rename or copy source outstanding, no remaining file a moved one

**guarded element:** `check` step 8, `may_read = may_read and not outstanding and not any(path in moved for path in remaining)`.
**Axis:** a move after review keeps today's answer.

**neutralization:** that line became `may_read = may_read and (True or not outstanding and not any(path in moved for path in remaining))`.

**raw red** (`-k test_e_cf_rename`):
```
F.                                                                       [100%]
E   AssertionError: {'answer': 'judgement', 'why': ['conflict-fix: every new commit is a merge by the builder that brings the base in; the...es'], 'certified': 'cf8e05130f3bbb0ffe6bbd0442d0fa4204c7c81a', 'head': '20d8cfd46131e8f3349e7eaac2f56fd9871e7cb2', ...}
    assert ('judgement' == 'needs-review'
/home/user/wt-2600/plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py:94: AssertionError: ...
FAILED plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py::test_e_cf_rename_a_reviewed_rename_whose_destination_a_copy_proof_settles_keeps_needs_review
1 failed, 1 passed, 32 deselected in 0.82s
```

On the axis: the reviewed-rename-with-copy-proof test is red. The second test (a rename made inside the merge) stays green
with this guard off, so something later refuses it (not identified); only the first test is a proof of this guard.

**restore:** the inverse edit. **restore receipt**, quoted back:
`        may_read = may_read and not outstanding and not any(path in moved for path in remaining)`.
**raw green:** `2 passed, 32 deselected in 0.97s`.

## E-cf-untouched and E-cf-clean-edit: a file git merged cleanly has no hand-made line to read

**guarded element:** `_conflict_fix_file`, `if code == 0: return None` (one guard for both names). **Axis:** an edit in a
file git merged without a conflict, or in a file neither parent changed (git's merge of it is clean), is never read as a
conflict fix.

**neutralization:** `if code == 0:` became `if False and code == 0:`.

**raw red** (`-k "test_e_cf_untouched or test_e_cf_clean_edit"`; both red):
```
FF                                                                       [100%]
E   AssertionError: {'answer': 'judgement', 'why': ['conflict-fix: every new commit is a merge by the builder that brings the base in; the...es'], 'certified': '60cf42eecf4f6245b201de2117cd835a5f9e1ef2', 'head': '7765ddeacc00c1b2612e88d5834b524690dd57a3', ...}
    assert ('judgement' == 'needs-review'
/home/user/wt-2600/plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py:94: AssertionError: ...
E   AssertionError: {'answer': 'judgement', 'why': ['conflict-fix: every new commit is a merge by the builder that brings the base in; the...es'], 'certified': 'e8628fb8e069ad21651bf8e14aeeefa7b79cefc8', 'head': '5bc2d46061b6075f8042e8cc844b30dd8a6fa591', ...}
    assert ('judgement' == 'needs-review'
/home/user/wt-2600/plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py:94: AssertionError: ...
FAILED plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py::test_e_cf_untouched_a_merge_that_also_changes_a_file_neither_parent_changed_keeps_needs_review
FAILED plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py::test_e_cf_clean_edit_a_hand_edit_inside_a_file_git_merged_cleanly_keeps_needs_review
2 failed, 32 deselected in 0.85s
```

**restore:** the inverse edit. **restore receipt**, quoted back: `    if code == 0:` then `        return None`.
**raw green** (run together with the E-cf-nonmerge tests, `-k "test_e_cf_untouched or test_e_cf_clean_edit or test_e_cf_nonmerge"`):
`4 passed, 30 deselected in 1.41s`.

## E-cf-unresolved: a conflict block whose markers survive was never resolved

**guarded element:** `_conflict_fix_file`, `if not all(mark in removed for _, _, marks in blocks for mark in marks): return None`.
**Axis:** a block kept verbatim with its markers keeps `needs-review`.

**neutralization:** `if not all(...)` became `if False and not all(...)`.

**raw red** (`-k test_e_cf_unresolved`):
```
F                                                                        [100%]
E   AssertionError: {'answer': 'judgement', 'why': ['conflict-fix: every new commit is a merge by the builder that brings the base in; the...es'], 'certified': '026c2fef9b5501cf2dd3e98099d60fa93453b4dc', 'head': 'accd204c84df6057cad2706eed900a6c5a44ab72', ...}
    assert ('judgement' == 'needs-review'
/home/user/wt-2600/plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py:94: AssertionError: ...
FAILED plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py::test_e_cf_unresolved_a_block_kept_verbatim_with_its_markers_keeps_needs_review
1 failed, 33 deselected in 0.72s
```

**restore:** the inverse edit. **restore receipt**, quoted back:
`    if not all(mark in removed for _, _, marks in blocks for mark in marks):`. **raw green:** `1 passed, 33 deselected in 0.63s`.

## E-cf-mode: a mode change, or a non-regular file, is no line of text

**guarded element:** `_conflict_fix_file`, `if len({entry[0] for entry in entries}) != 1 or at_c[0] not in _REGULAR_MODES: return None`.
**Axis:** a merge that changes the file's mode keeps `needs-review`.

**neutralization:** the condition became `if False and (len({entry[0] for entry in entries}) != 1 or at_c[0] not in _REGULAR_MODES):`.

**raw red** (`-k test_e_cf_mode`):
```
F                                                                        [100%]
E   AssertionError: {'answer': 'judgement', 'why': ['conflict-fix: every new commit is a merge by the builder that brings the base in; the...es'], 'certified': '8068f7aa127e816eded428107fc8fa2c0ff7cd4c', 'head': 'aeb3dd286d2531781ac1e35604e68fe1f99b4546', ...}
    assert ('judgement' == 'needs-review'
/home/user/wt-2600/plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py:94: AssertionError: ...
FAILED plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py::test_e_cf_mode_a_merge_that_changes_the_files_mode_keeps_needs_review
1 failed, 33 deselected in 0.68s
```

**restore:** the inverse edit. **restore receipt**, quoted back:
`    if len({entry[0] for entry in entries}) != 1 or at_c[0] not in _REGULAR_MODES:`. **raw green:** `1 passed, 33 deselected in 0.73s`.

## E-cf-attr: a merge driver or marker-size attribute means the check cannot rebuild git's merge

**guarded element:** `_conflict_fix_file`, `if not (len(rows) == 2 and ... all(row[2] == "unspecified" for row in rows)): return None`.
**Axis:** a file with a `merge=` attribute keeps `needs-review`.

**neutralization:** `if not (len(rows) == 2 and all(len(row) == 3 for row in rows)` became
`if False and not (len(rows) == 2 and all(len(row) == 3 for row in rows)` (the first line of the condition).

**raw red** (`-k test_e_cf_attr`):
```
F                                                                        [100%]
E   AssertionError: {'answer': 'judgement', 'why': ['conflict-fix: every new commit is a merge by the builder that brings the base in; the...es'], 'certified': 'e6e1bf8eee42d1faeca130f28130b3cd001b390f', 'head': 'cc3fd1a8c02d931830690d329181990547f4da81', ...}
    assert ('judgement' == 'needs-review'
/home/user/wt-2600/plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py:94: AssertionError: ...
FAILED plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py::test_e_cf_attr_a_merge_driver_attribute_on_the_file_keeps_needs_review
1 failed, 33 deselected in 0.61s
```

**restore:** the inverse edit. **restore receipt**, quoted back: `    if not (len(rows) == 2 and all(len(row) == 3 for row in rows)`.
**raw green:** `1 passed, 33 deselected in 0.67s`.

## E-cf-binary: a NUL byte anywhere means the file is binary to the eye

**guarded element:** `_conflict_fix_file`, `if any("\0" in text for text in texts): return None`. **Axis:** a NUL byte past
git's own 8000-byte look keeps `needs-review`.

**neutralization:** `if any("\0" in text for text in texts):` became `if False and any("\0" in text for text in texts):`.

**raw red** (`-k test_e_cf_binary`):
```
F                                                                        [100%]
E   AssertionError: {'answer': 'judgement', 'why': ['conflict-fix: every new commit is a merge by the builder that brings the base in; the...es'], 'certified': '1afacf369858c8aaec6eab499008beaaa9740ea0', 'head': 'dc2cd5bfb03d7f1530345c4cbdcfdaf0da663318', ...}
    assert ('judgement' == 'needs-review'
/home/user/wt-2600/plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py:94: AssertionError: ...
FAILED plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py::test_e_cf_binary_a_nul_byte_in_the_files_blobs_keeps_needs_review
1 failed, 33 deselected in 0.61s
```

**restore:** the inverse edit. **restore receipt**, quoted back: `    if any("\0" in text for text in texts):`.
**raw green:** `1 passed, 33 deselected in 0.67s`.

## E-cf-criss: exactly one merge base

**guarded element:** `_conflict_fix`, `if len(bases) != 1 or not returning_review._is_sha(bases[0]): return None`.
**Axis:** two merge bases keep `needs-review`.

**neutralization:** the condition became `if False and (len(bases) != 1 or not returning_review._is_sha(bases[0])):`.

**raw red** (`-k test_e_cf_criss`):
```
F                                                                        [100%]
E   AssertionError: {'answer': 'judgement', 'why': ['conflict-fix: every new commit is a merge by the builder that brings the base in; the...es'], 'certified': '6f34a49279ec05d4ec3a84d72c2ac7fdb33de2bb', 'head': 'f7e1b1ccf8c6b978174b88416c2bd9a7e4c37816', ...}
    assert ('judgement' == 'needs-review'
/home/user/wt-2600/plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py:94: AssertionError: ...
FAILED plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py::test_e_cf_criss_two_merge_bases_keep_needs_review
1 failed, 33 deselected in 0.66s
```

**restore:** the inverse edit. **restore receipt**, quoted back:
`        if len(bases) != 1 or not returning_review._is_sha(bases[0]):`. **raw green:** `1 passed, 33 deselected in 0.73s`.

## E-cf-unreadable: a failed read is no absent file

**guarded element:** `_conflict_fix_file`, `if any(entry is None for entry in entries): return None`. **Axis:** a failed
`ls-tree` read never passes the equality below as "both sides absent" and so never hides a hand edit.

**neutralization:** `if any(entry is None for entry in entries):` became `if False and any(entry is None for entry in entries):`.

**raw red** (`-k test_e_cf_unreadable`; 8 parametrized cases, 1 red):
```
...F....                                                                 [100%]
E   AssertionError: {'answer': 'judgement', 'why': ['conflict-fix: every new commit is a merge by the builder that brings the base in; the...es'], 'certified': '2281424fe3f01250a2bf73ae56acada3862ebecc', 'head': 'ac0e1cf8685c31afa84e1a60e69067b6076c1d9f', ...}
    assert ('judgement' == 'needs-review'
/home/user/wt-2600/plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py:94: AssertionError: ...
FAILED plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py::test_e_cf_unreadable_a_failed_git_read_keeps_needs_review[ls-tree-other-file]
1 failed, 7 passed, 26 deselected in 2.89s
```

The red case is `ls-tree-other-file`, the read that matches this guard's axis (all four entries of the second file read as
None, the equality passes, and the hand edit is hidden). The other seven cases (a failure of `rev-list`, `is-ancestor`,
`merge-base --all`, `ls-tree` of the shared file, `check-attr`, `cat-file` and the `merge-file` rebuild) are held by their
own failure checks and are not proofs of this guard.

**restore:** the inverse edit. **restore receipt**, quoted back: `    if any(entry is None for entry in entries):`.
**raw green:** `8 passed, 26 deselected in 3.41s`.

## E-cf-span: a hand-made line inside a conflict block is listed with the whole block

**guarded element:** `_hunk_ranges`, `if overlaps: lo, hi = min(lo, start), max(hi, end)`. **Axis:** a block resolved by
keeping one side is one hunk with its markers, not several.

**neutralization:** `if overlaps:` became `if False and overlaps:` (the widening dropped, so `lo, hi` stay `i1, i2`).

**raw red** (`-k test_e_cf_span`):
```
F                                                                        [100%]
E   AssertionError: [{'file': 'src/shared.py', 'merge': 'cba8ddb9189c4f2ae964eccc3baa4ce39b81457e', 'parents': ['fe31f50da95863ccbe06a1919...6f78c14fe', 'd70f18d150cb46a726ce0bedc39d814c99ee42c8'], 'mergeBase': '36775c0edd18df486768758a09232089c513d281', ...}]
    assert 2 == 1
     +  where 2 = len([{'file': 'src/shared.py', 'merge': 'cba8ddb9189c4f2ae964eccc3baa4ce39b81457e', ...}])
/home/user/wt-2600/plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py:398: AssertionError: ...
FAILED plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py::test_e_cf_span_a_block_resolved_by_keeping_one_side_is_one_hunk_with_its_markers
1 failed, 33 deselected in 0.86s
```

**restore:** the inverse edit. **restore receipt**, quoted back: `            if overlaps:` then `                lo, hi = min(lo, start), max(hi, end)`.
**raw green:** `1 passed, 33 deselected in 0.78s`.

## E-cf-onesided: a side taken wholesale is no hand-made line only while the other side is the merge base's

**guarded element:** `_conflict_fix_file`, `if (at_c == at_p1 and at_p2 == at_mb) or (at_c == at_p2 and at_p1 == at_mb): return []`.
**Axis:** a resolution that takes one side wholesale and so drops the other side's change is still read and lists the line it
drops.

**neutralization:** the condition became `if (at_c == at_p1) or (at_c == at_p2):` (the shortcut also returns `[]` when the
other side changed).

**raw red** (`-k test_e_cf_onesided`; both red, on the answer):
```
FF                                                                       [100%]
E   AssertionError: {'answer': 'needs-review', 'why': ['behaviour-change: not only prose or comment lines: src/shared.py'], 'certified': '18b90ba9f7fcdccf69a86f4610fc3f532134d508', 'head': 'dcf03c797d4ec8fc70dcaff07c29c84569f17a29', ...}
    assert ('needs-review' == 'judgement'
/home/user/wt-2600/plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py:415: AssertionError: ...
E   AssertionError: {'answer': 'needs-review', 'why': ['behaviour-change: not only prose or comment lines: src/shared.py'], 'certified': '2645f4a5b3dbe6d15e51ea489a5fb641b3daacf2', 'head': '5086e493554cfb49e78e39c935f5a343a7dd768a', ...}
    assert ('needs-review' == 'judgement'
/home/user/wt-2600/plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py:424: AssertionError: ...
FAILED plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py::test_e_cf_onesided_a_resolution_that_takes_the_bases_side_lists_the_line_it_drops
FAILED plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py::test_e_cf_onesided_a_resolution_that_takes_the_pull_requests_side_lists_the_line_it_drops
2 failed, 32 deselected in 0.88s
```

On the axis: the answer reads `needs-review` instead of the designed `judgement` (the shortcut returns no hunks for a head
with a real hand-made resolution, so no fix is found and the old answer stands), at the answer assertion of each test.

**restore:** the inverse edit. **restore receipt**, quoted back:
`    if (at_c == at_p1 and at_p2 == at_mb) or (at_c == at_p2 and at_p1 == at_mb):`. **raw green:** `2 passed, 32 deselected in 0.92s`.

## E-cf-unresolved-whole: a file identical to git's conflicted merge is unresolved, not a file with nothing to list

Added by the review's round-1 fix (finding: reject identical output when the automatic merge still has conflicts), typed
and run by the build session in the build worktree.

**guarded element:** `_conflict_fix_file`, `if a == b: return [] if code == 0 else None`. **Axis:** a file committed
exactly as git's diff3 merge output, conflict blocks included, is never passed over as having no hand-made line while
another file's hunks are listed.

**neutralization:** `        return [] if code == 0 else None` became `        return []`.

**raw red** (`-k unresolved_whole`, `--tb=line`):
```
F                                                                        [100%]
E   AssertionError: {'answer': 'judgement', 'why': ['conflict-fix: every new commit is a merge by the builder that brings the base in; the...es'], ... }
    assert ('judgement' == 'needs-review'
FAILED plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py::test_e_cf_unresolved_whole_a_file_committed_as_gits_conflicted_merge_beside_a_resolved_one_keeps_needs_review
1 failed, 34 deselected in 0.76s
```

**restore:** the inverse edit. **restore receipt**, quoted back: `        return [] if code == 0 else None`. **raw green:**
`1 passed, 34 deselected in 0.84s`.

## E-cf-attr-one-file: a failed attribute read of one file never lets the other file's hunk stand alone

Added by work order i2600-wo-e, typed and run by the implementer in the build worktree.

**guarded element:** `_conflict_fix_file`, the `return None` after the E-cf-attr axis comment (`if not (len(rows) == 2 and ...): return None`).
**Axis:** when the attribute read of one of two conflicted files fails, the merge is refused as a whole (`needs-review`); the other
file's hunks are never listed alone as a `judgement`.

**neutralization:** the one `return None` after the E-cf-attr axis comment became `return []`.

**raw red** (`-k attr_unreadable_one`, `--tb=line`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
E   AssertionError: {'answer': 'judgement', 'why': ['conflict-fix: every new commit is a merge by the builder that brings the base in; the...es'], 'certified': 'cd55495508a2e9cc799c1be8d5c27147cf1740c8', 'head': 'a6c4603270d63a945e3c385d17ba87b583257cfa', ...}
    assert ('judgement' == 'needs-review'
      
      - needs-review
      + judgement)
/home/user/wt-2600-e/plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py:94: AssertionError: {'answer': 'judgement', 'why': ['conflict-fix: every new commit is a merge by the builder that brings the base in; the...es'], 'certified': 'cd55495508a2e9cc799c1be8d5c27147cf1740c8', 'head': 'a6c4603270d63a945e3c385d17ba87b583257cfa', ...}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_head_coverage_conflict_fix_2600.py::test_e_cf_attr_unreadable_one_of_two_conflicted_files_keeps_needs_review
1 failed, 35 deselected in 4.92s
```

**restore:** the inverse edit. **restore receipt**, quoted back: `        return None` (the line after
`all(row[2] == "unspecified" for row in rows)):`); `git diff -- plugins/superheroes/lib/head_coverage.py` empty.
**raw green:** `1 passed, 35 deselected in 5.42s`.

## After the last restore

`Grep` of `head_coverage.py` for `False and|True or|NEUTRALIZED`: `No matches found`. `git diff -- plugins/superheroes/lib/head_coverage.py`:
empty. The seven head-coverage test files together: `207 passed in 11.10s`.
