# Issue 2589 bite-proof: the tested-union proof in the head-coverage check

**Provenance:** typed and run by the WO-A implementer on 2026-11-21 in the build worktree at base commit 0e2baf76. The
guards are in `lib/head_coverage.py` (`check`, `_with_union`, `_union_refusal`), proved by
`lib/tests/test_head_coverage_union_probe_2589.py`. Each red ran in the worktree by one targeted text edit, and each
restore was the inverse edit. A final search of `head_coverage.py` for `False and` and `NEUTRALIZED` found nothing. Each
command was
`scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-a -m pytest plugins/superheroes/lib/tests/test_head_coverage_union_probe_2589.py -q -p no:cacheprovider --tb=line -k <selection>`
(`--tb=line` was added to keep the red short; E-receipt used `--tb=no`). The captures below are the printed output with the
pytest `warning: The UV_NATIVE_TLS ...` line and the long `E   AssertionError` lines elided where marked; nothing else is
cut, and nothing is redacted. Text in parentheses on the right of a captured line is the implementer's label, not output.
The whole file passes: see the last section.

The proof fixture is the #2585 shape (`Shape` in the test file): main and the pull request change the same line of one
function, the vet's probe merges main into the pull request's tip with a hand resolution, and the builder's head merges
main with the same (or a changed) resolution.

## E-absent: no proof, no key

**guarded element:** `check`, `if union_proof is None: return got`. **Axis:** with no union proof the result is the check's
own, key set included, so the proof path can never change an answer it was not asked about.

**neutralization:** `if union_proof is None:` became `if False and union_proof is None:`.

**raw red** (`-k test_row_12`):
```
F                                                                        [100%]
E   AssertionError: {'answer': 'needs-review', 'why': ['behaviour-change: not only prose or comment lines: src/shared.py', 'union-probe-ig...ed'], 'certified': ... }
    assert ({'answer', 'b... 'files', ...} == {'answer', 'b... 'files', ...}
      Extra items in the left set:
      'unionProbe'
FAILED ...::test_row_12_without_a_proof_the_result_has_no_union_probe_key
1 failed, 49 deselected in 1.64s
```

**restore:** the inverse edit. **restore receipt**, quoted back from the file: `        if union_proof is None:` then
`            return got`. **raw green:** `1 passed, 49 deselected in 1.48s`.

## E-consulted: a check that could not read its inputs does not consult the proof

**guarded element:** `_with_union`, the `got["certified"] is None or any(_token_of(line) in _UNION_UNREAD_WHY ...)` branch.
**Axis:** an unusable record, invalid inputs or an unreadable diff are never turned into an answer by a proof.

**neutralization:** `if <condition>:` became `if False and (<condition>):`.

**raw red** (`-k test_row_10`):
```
FF                                                                       [100%]
E   AssertionError: assert {'probe': 'aa... 'covers': []} == {'probe': 'aa... 'covers': []}
      Differing items:
      {'reason': 'other-commit'} != {'reason': 'not-consulted'}
E   AssertionError: assert ('head-not-current' == 'not-consulted'
FAILED ...::test_row_10_an_unusable_record_with_a_valid_proof_is_not_consulted
FAILED ...::test_row_10_invalid_inputs_and_an_unreadable_diff_do_not_consult_the_proof
2 failed, 48 deselected in 1.63s
```

**restore:** the inverse edit. **restore receipt:**
`    if got["certified"] is None or any(_token_of(line) in _UNION_UNREAD_WHY for line in got["why"]):`.
**raw green:** `2 passed, 48 deselected in 0.76s`.

## E-shape: the proof is exactly the union-probe/1 object (6.1)

**guarded element:** `_union_refusal`, the `isinstance(union_proof, dict) and set(union_proof) == _UNION_KEYS and
schema == UNION_SCHEMA and all(_lower_sha(...))` test. **Axis:** a proof that is not that object, with full lower-case
shas, proves nothing.

**neutralization:** `if not (isinstance(union_proof, dict) ...` became `if False and not (isinstance(union_proof, dict) ...`.

**raw red** (`-k test_row_9`; 15 cases, all red; the 15 near-identical assertion blocks are elided and one block of each
kind that was printed is shown, the kinds being `not-consulted` (the code raised, `check-failed`), `proven`,
`probe-unreadable`, `other-base`, `other-commit` and `no-receipt`; which case printed which is not mapped here):
```
FFFFFFFFFFFFFFF                                                          [100%]
E   AssertionError: assert (False is False and 'not-consulted' == 'malformed'
E   AssertionError: assert 'proven' == 'needs-review'
E   AssertionError: assert (False is False and 'probe-unreadable' == 'malformed'
E   AssertionError: assert (False is False and 'other-base' == 'malformed'
E   AssertionError: assert (False is False and 'other-commit' == 'malformed'
E   AssertionError: assert (False is False and 'no-receipt' == 'malformed'
15 failed, 35 deselected in 3.76s
```

**restore:** the inverse edit. **restore receipt:** `    if not (isinstance(union_proof, dict) and set(union_proof) == _UNION_KEYS and union_proof["schema"] == UNION_SCHEMA`
then `            and all(_lower_sha(union_proof[key]) for key in ("probe", "tree", "base"))):`.
**raw green:** `15 passed, 35 deselected in 3.39s`.

## E-receipt: a test receipt that ran, exited 0 and names the proof's own tree (6.2)

**guarded element:** `_union_refusal`, the `isinstance(receipt, dict) and set(receipt) == _UNION_RECEIPT_KEYS and command
is a non-blank string and exitCode is an int that is not a bool and is 0 and receipt["tree"] == tree` test. **Axis:** a
probe without a good receipt for its own tree proves nothing.

**neutralization:** `if not (isinstance(receipt, dict) ...` became `if False and not (isinstance(receipt, dict) ...`.

**raw red** (`-k test_row_5`, `--tb=no`):
```
FFFFFFFFFFFFFF                                                           [100%]
FAILED ...::test_row_5_a_probe_without_a_good_test_receipt_reads_no_receipt[blank-command]
FAILED ...[command-not-string]  FAILED ...[empty-command]  FAILED ...[exit-1]  FAILED ...[exit-false]
FAILED ...[exit-float]  FAILED ...[exit-string]  FAILED ...[exit-true]  FAILED ...[extra-key]  FAILED ...[missing-key]
FAILED ...[receipt-list]  FAILED ...[receipt-none]  FAILED ...[receipt-string]  FAILED ...[receipt-tree-differs]
14 failed, 36 deselected in 3.59s
```
(the node ids are shortened here; each was printed in full.)

**restore:** the inverse edit. **restore receipt:** `    if not (isinstance(receipt, dict) and set(receipt) == _UNION_RECEIPT_KEYS and isinstance(command, str)`.
**raw green:** `14 passed, 36 deselected in 3.35s`.

## E-base: the probe merged exactly the check's base (6.3)

**guarded element:** `_union_refusal`, `if union_proof["base"] != base`. **Axis:** a probe of another base, even one with
the same tree as the base, proves nothing.

**neutralization:** `if union_proof["base"] != base:` became `if False and union_proof["base"] != base:`.

**raw red** (`-k test_row_4`):
```
FF                                                                       [100%]
E   AssertionError: {'answer': 'proven', 'why': ["proven-union: the head's tree is git's tree of the vet's tested union probe f327886e of ...s)"], ... }
    assert 'proven' == 'needs-review'                                    (4a: the proof's base is an older main commit)
E   AssertionError: assert ('needs-review' == 'needs-review'
        needs-review and 'other-commit' == 'other-base'                  (4b: two bases with one tree)
FAILED ...::test_row_4a_a_probe_on_an_older_main_commit_reads_other_base
FAILED ...::test_row_4b_two_distinct_bases_holding_one_tree_read_other_base
2 failed, 48 deselected in 0.94s
```

**restore:** the inverse edit. **restore receipt:** `    if union_proof["base"] != base:`.
**raw green:** `2 passed, 48 deselected in 0.98s`.

## E-readable: the probe is a commit git can read (6.4)

**guarded element:** `_union_refusal`, `if code != 0 or not isinstance(text, str) or text.strip() != "commit"` after
`cat-file -t`. **Axis:** a missing object, a tree or a blob is never a probe.

**neutralization:** that `if <condition>:` became `if False and (<condition>):`.

**raw red** (`-k probe_unreadable`):
```
F                                                                        [100%]
E   AssertionError: {'answer': 'needs-review', 'why': ['behaviour-change: not only prose or comment lines: src/shared.py', 'union-probe-ig...ed'], ... }
    assert {'probe': '01... 'covers': []} == {'probe': '01... 'covers': []}
      Differing items:
      {'reason': 'tree-unconfirmed'} != {'reason': 'probe-unreadable'}
FAILED ...::test_row_6_a_probe_that_is_not_a_readable_commit_reads_probe_unreadable
1 failed, 49 deselected in 0.69s
```
The test loops over four inputs (a missing sha, the probe's tree sha twice, a blob sha); the loop stops at the first, so
only the missing sha was shown red. The tree and blob inputs are not separately proved red.

**restore:** the inverse edit. **restore receipt:** `    if code != 0 or not isinstance(text, str) or text.strip() != "commit":`.
**raw green:** `1 passed, 49 deselected in 0.79s`.

## E-confirm: git's tree of the probe is the proof's tree (6.5)

**guarded element:** `_union_refusal`, `if probe_tree is None or probe_tree != tree`. **Axis:** the tree the receipt tested
is git's tree of the probe, never the proof's own word for it.

**neutralization:** that `if <condition>:` became `if False and (<condition>):`.

**raw red** (`-k tree_unconfirmed`):
```
F                                                                        [100%]
E   AssertionError: {'answer': 'proven', 'why': ["proven-union: the head's tree is git's tree of the vet's tested union probe 6c6b6391 of ...s)"], ... }
    assert 'proven' == 'needs-review'
FAILED ...::test_row_6_a_tree_claim_git_does_not_confirm_reads_tree_unconfirmed
1 failed, 49 deselected in 0.59s
```

**restore:** the inverse edit. **restore receipt:** `    if probe_tree is None or probe_tree != tree:`.
**raw green:** `1 passed, 49 deselected in 0.56s`.

## E-parent: the probe merges the base and a covered commit (6.6)

**guarded element:** `_union_refusal`, the `if other is None or not (other == got["certified"] or _check_rewritten(...)["answer"] == PROVEN)`
refusal (`return "other-commit", None`). **Axis:** a probe of unreviewed code, a one-parent probe, a probe whose two parents
are the base, one with no base parent and one with three parents prove nothing.

**neutralization:** the line `return "other-commit", None` became `pass  # NEUTRALIZED return "other-commit", None`.

**raw red** (`-k "test_row_7 or both_the_base"`):
```
FFF                                                                      [100%]
E   AssertionError: {'answer': 'proven', 'why': ["proven-union: the head's tree is git's tree of the vet's tested union probe 49442c3a of ...s)"], ... }
    assert 'proven' == 'needs-review'          (the unreviewed later commit)
E   ... 'proven' == 'needs-review'              (the one-parent probe)
E   ... 'proven' == 'needs-review'              (the first input of the loop over three probes; the other two are not separately shown red)
FAILED ...::test_row_7_a_probe_of_an_unreviewed_later_commit_reads_other_commit
FAILED ...::test_row_7_a_one_parent_probe_reads_other_commit
FAILED ...::test_a_probe_whose_parents_are_both_the_base_or_that_lacks_the_base_reads_other_commit
3 failed, 47 deselected in 1.05s
```
Row 13's control (the one-byte-different resolution at the head) does not reach this guard: it refuses at `other-tree`
(6.8), after a probe that passes 6.6 honestly, so it is not a red for this element and is not claimed as one.

**restore:** the inverse edit. **restore receipt:** `        return "other-commit", None`.
**raw green:** `3 passed, 47 deselected in 1.21s`.

## E-current: the base is an ancestor of the head (6.7)

**guarded element:** `_union_refusal`, `if code != 0: return "head-not-current", other` after
`merge-base --is-ancestor base head`. **Axis:** a head that only holds the probe's files, as a single-parent commit that
does not contain the base, is not the tested merge.

**neutralization:** `if code != 0:` (before the `head-not-current` return) became `if False and code != 0:`.

**raw red** (`-k test_row_8`):
```
F                                                                        [100%]
E   AssertionError: {'answer': 'proven', 'why': ["proven-union: the head's tree is git's tree of the vet's tested union probe ecfde489 of ...s)"], ... }
    assert 'proven' == 'needs-review'
FAILED ...::test_row_8_a_head_that_holds_the_probes_files_but_not_the_base_reads_head_not_current
1 failed, 49 deselected in 0.68s
```

**restore:** the inverse edit. **restore receipt:** `    if code != 0:` then `        return "head-not-current", other`.
**raw green:** `1 passed, 49 deselected in 0.61s`.

## E-tree: the head's tree is git's tree of the probe (6.8)

**guarded element:** `_union_refusal`, `if head_tree is None or head_tree != probe_tree`. **Axis:** a head that differs
from the tested tree by one byte, or by a file mode only, was not tested.

**neutralization:** that `if <condition>:` became `if False and (<condition>):`.

**raw red** (`-k "test_row_2 or test_row_3 or one_byte_different_resolution"`):
```
FFF                                                                      [100%]
E   AssertionError: {'answer': 'proven', 'why': ["proven-union: the head's tree is git's tree of the vet's tested union probe 3a27bc56 of ...s)"], ... }
    assert 'proven' == 'needs-review'          (row 2: one byte)
E   ...    assert 'proven' == 'needs-review'   (row 3: mode only)
E   AssertionError: assert ('proven' == 'needs-review'   (row 13: the carry/coverage control with one byte changed)
FAILED ...::test_row_2_one_byte_different_in_the_builders_resolution_reads_other_tree
FAILED ...::test_row_3_a_mode_difference_only_reads_other_tree
FAILED ...::test_row_13_a_one_byte_different_resolution_takes_the_sheet_down
3 failed, 47 deselected in 1.13s
```

**restore:** the inverse edit. **restore receipt:** `    if head_tree is None or head_tree != probe_tree:`.
**raw green:** `3 passed, 47 deselected in 1.08s`.

## Green

After the last restore the whole file passed (`50 passed`; the run is in the dispatch return). Nothing is redacted.
