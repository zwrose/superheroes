# Work order WO-B (#2600) bite-proof: a sheet carried across a judged code-conflict fix says so in one line

**Provenance:** claude / sonnet-5.5 (implementer, i2600-wo-b), worktree `/home/user/wt-2600-b`. Production under proof: `plugins/superheroes/lib/pr_sheet.py` (`_check_carry_input`), `plugins/superheroes/theme/sheet.schema.json` (`prSheet.carriedForward.conflictFix`), `plugins/superheroes/theme/review-template.html` (`prHead`), `plugins/superheroes/lib/sheet_prose.py` (`_pr_body`). Detector file: `plugins/superheroes/lib/tests/test_sheet_conflict_fix_2600.py`.

Declared guarded-element set (from the order): **E-cf-type**, **E-cf-key**, **E-cf-line-page**, **E-cf-line-prose**, **E-cf-schema**, and **E-nonote** (re-run green only, not neutralized). Five neutralized entries, one green-only entry; no equivalence class is used.

Every command is `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2600 -m pytest plugins/superheroes/lib/tests/test_sheet_conflict_fix_2600.py -q -p no:cacheprovider --tb=<line|short> -k <expression>`, run from `/home/user/wt-2600-b`. The `--tb` style is named per entry (`line` or `short`); it only trims tracebacks. The leading `warning: The UV_NATIVE_TLS environment variable is deprecated ...` line of every run is left out; it is the launcher's, not pytest's. Each neutralization is one Edit-tool edit, restored by the inverse Edit-tool edit; no `git checkout`, `git restore`, `git reset` or `git stash` was used. Nothing quoted is a secret, token, private URL or personal detail, so nothing is redacted. Every capture is far under the 32 KiB per element and 128 KiB ceilings. The detector file was not edited between a red and its green, except as disclosed under E-cf-line-page.

## E-cf-type: a conflictFix that is empty, whitespace-only or not a string is refused by the builder

- **guarded element:** `pr_sheet.py`, `_check_carry_input`, the line `if "conflictFix" in carry and not _text(carry["conflictFix"]):`.
- **axis:** the optional key, when present, must be a non-empty string; the problem `carriedForward conflictFix must be a non-empty string` is raised and no sheet is built.
- **neutralization:** that line became `    if False and "conflictFix" in carry and not _text(carry["conflictFix"]):`.
- **detector:** `test_a_conflict_fix_that_is_empty_or_not_a_string_is_refused` (5 parameters), run as `-k "empty_or_not_a_string"`, `--tb=line`.

### raw red

```
FFFFF                                                                    [100%]
=================================== FAILURES ===================================
E   Failed: DID NOT RAISE Refusal
/home/user/wt-2600-b/plugins/superheroes/lib/tests/test_pr_sheet_head_2496.py:43: Failed: DID NOT RAISE Refusal
E   Failed: DID NOT RAISE Refusal
/home/user/wt-2600-b/plugins/superheroes/lib/tests/test_pr_sheet_head_2496.py:43: Failed: DID NOT RAISE Refusal
E   Failed: DID NOT RAISE Refusal
/home/user/wt-2600-b/plugins/superheroes/lib/tests/test_pr_sheet_head_2496.py:43: Failed: DID NOT RAISE Refusal
E   Failed: DID NOT RAISE Refusal
/home/user/wt-2600-b/plugins/superheroes/lib/tests/test_pr_sheet_head_2496.py:43: Failed: DID NOT RAISE Refusal
E   Failed: DID NOT RAISE Refusal
/home/user/wt-2600-b/plugins/superheroes/lib/tests/test_pr_sheet_head_2496.py:43: Failed: DID NOT RAISE Refusal
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_sheet_conflict_fix_2600.py::test_a_conflict_fix_that_is_empty_or_not_a_string_is_refused[empty]
FAILED plugins/superheroes/lib/tests/test_sheet_conflict_fix_2600.py::test_a_conflict_fix_that_is_empty_or_not_a_string_is_refused[blank]
FAILED plugins/superheroes/lib/tests/test_sheet_conflict_fix_2600.py::test_a_conflict_fix_that_is_empty_or_not_a_string_is_refused[number]
FAILED plugins/superheroes/lib/tests/test_sheet_conflict_fix_2600.py::test_a_conflict_fix_that_is_empty_or_not_a_string_is_refused[null]
FAILED plugins/superheroes/lib/tests/test_sheet_conflict_fix_2600.py::test_a_conflict_fix_that_is_empty_or_not_a_string_is_refused[list]
5 failed, 12 deselected in 1.77s
```

**Restore:** the inverse Edit-tool edit (`if False and "conflictFix" in carry ...` back to `if "conflictFix" in carry ...`).
**Restore receipt** (a search of the file after the restore): `888:    if "conflictFix" in carry and not _text(carry["conflictFix"]):`

### raw green

```
.....                                                                    [100%]
5 passed, 12 deselected in 1.74s
```

## E-cf-key: an unknown carriedForward key is still refused

- **guarded element:** `pr_sheet.py`, `_check_carry_input`, the optional tuple `("conflictFix",)` in the `_keys("carriedForward", ...)` call.
- **axis:** the optional tuple names `conflictFix` alone, so any other carry key (here the misspelling `conflictfix`) is refused with `carriedForward has an unknown key conflictfix`.
- **neutralization:** the tuple `("conflictFix",)` became `tuple(carry)`, so every key present is allowed.
- **detector:** `test_an_unknown_carry_key_is_still_refused_beside_a_conflict_fix`, run as `-k "unknown_carry_key"`, `--tb=line`.

### raw red

```
F                                                                        [100%]
=================================== FAILURES ===================================
E   Failed: DID NOT RAISE Refusal
/home/user/wt-2600-b/plugins/superheroes/lib/tests/test_pr_sheet_head_2496.py:43: Failed: DID NOT RAISE Refusal
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_sheet_conflict_fix_2600.py::test_an_unknown_carry_key_is_still_refused_beside_a_conflict_fix
1 failed, 16 deselected in 1.60s
```

**Restore:** the inverse Edit-tool edit (`tuple(carry)` back to `("conflictFix",)`).
**Restore receipt** (a search of the file after the restore): `885:    if not _keys("carriedForward", carry, ("fromSheet", "heads", "date", "moved", "whyNotMaterial"), ("conflictFix",), problems):`

### raw green

```
.                                                                        [100%]
1 passed, 16 deselected in 1.57s
```

## E-cf-line-page: a carried sheet with conflictFix draws the line on the page

- **guarded element:** `review-template.html`, `prHead`, the line `if (prSheet.carriedForward !== undefined && prSheet.carriedForward.conflictFix !== undefined) parts.push(buildConflictFixed(prSheet.carriedForward.conflictFix));`.
- **axis:** a carried sheet with `conflictFix` draws one `pr-conflict-fixed` box directly under What changed, holding the one line from `pr.conflictFixed`.
- **neutralization:** the condition gained a leading `false && `: `if (false && prSheet.carriedForward !== undefined && ...`.
- **detector:** `test_the_page_draws_the_line_of_a_carried_sheet_with_a_conflict_fix` (pr and stack), run as `-k "page_draws_the_line"`, `--tb=short`. The test drives the real template under node, through `_page` of `test_review_template_pr.py` (the mechanism the existing page tests use).
- **disclosure:** a first red run, with the test as first written, failed through a node crash (`TypeError: Cannot read properties of undefined (reading 'children')` at `shape`) because the scenario read a part that was not drawn. The scenario was then changed to report a missing box as `null` (a test edit made with the production line restored), and the neutralization was applied again; the red below is from the edited test, and the green is from the same edited test.

### raw red

```
FF                                                                       [100%]
=================================== FAILURES ===================================
___ test_the_page_draws_the_line_of_a_carried_sheet_with_a_conflict_fix[pr] ____
/home/user/wt-2600-b/plugins/superheroes/lib/tests/test_sheet_conflict_fix_2600.py:87: in test_the_page_draws_the_line_of_a_carried_sheet_with_a_conflict_fix
    assert page["result"]["order"][:3] == ["pr-what-changed", "pr-conflict-fixed", "pr-walk"]
E   AssertionError: assert ['pr-what-cha...pr-accepting'] == ['pr-what-cha...d', 'pr-walk']
E     
E     At index 1 diff: 'pr-walk' != 'pr-conflict-fixed'
E     Use -v to get more diff
__ test_the_page_draws_the_line_of_a_carried_sheet_with_a_conflict_fix[stack] __
/home/user/wt-2600-b/plugins/superheroes/lib/tests/test_sheet_conflict_fix_2600.py:87: in test_the_page_draws_the_line_of_a_carried_sheet_with_a_conflict_fix
    assert page["result"]["order"][:3] == ["pr-what-changed", "pr-conflict-fixed", "pr-walk"]
E   AssertionError: assert ['pr-what-cha...pr-accepting'] == ['pr-what-cha...d', 'pr-walk']
E     
E     At index 1 diff: 'pr-walk' != 'pr-conflict-fixed'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_sheet_conflict_fix_2600.py::test_the_page_draws_the_line_of_a_carried_sheet_with_a_conflict_fix[pr]
FAILED plugins/superheroes/lib/tests/test_sheet_conflict_fix_2600.py::test_the_page_draws_the_line_of_a_carried_sheet_with_a_conflict_fix[stack]
2 failed, 15 deselected in 2.04s
```

**Restore:** the inverse Edit-tool edit (`if (false && prSheet...` back to `if (prSheet...`).
**Restore receipt** (a search of the file after the restore): `2505:      if (prSheet.carriedForward !== undefined && prSheet.carriedForward.conflictFix !== undefined) parts.push(buildConflictFixed(prSheet.carriedForward.conflictFix));`

### raw green

```
..                                                                       [100%]
2 passed, 15 deselected in 1.85s
```

## E-cf-line-prose: a carried sheet with conflictFix draws the line in the prose

- **guarded element:** `sheet_prose.py`, `_pr_body`, the line `if isinstance(why, str):` guarding `lines += [_fill(PR["conflictFixed"], why=_text(why)), ""]`.
- **axis:** a carried sheet with `conflictFix` has the one line in its chat prose, exactly once.
- **neutralization:** that line became `    if False and isinstance(why, str):`.
- **detector:** `test_the_prose_draws_the_line_of_a_carried_sheet_with_a_conflict_fix` (pr and stack), run as `-k "prose_draws_the_line"`, `--tb=short`.

### raw red

```
FF                                                                       [100%]
=================================== FAILURES ===================================
___ test_the_prose_draws_the_line_of_a_carried_sheet_with_a_conflict_fix[pr] ___
/home/user/wt-2600-b/plugins/superheroes/lib/tests/test_sheet_conflict_fix_2600.py:102: in test_the_prose_draws_the_line_of_a_carried_sheet_with_a_conflict_fix
    assert prose.count(LINE) == 1 and prose.count("A code conflict was fixed") == 1
E   assert (0 == 1)
E    +  where 0 = <built-in method count of str object at 0x1397ec80>('A code conflict was fixed when the base was brought in, and it was judged immaterial: the fix only renamed a local variable')
E    +    where <built-in method count of str object at 0x1397ec80> = "**Reword the receipt page**: 0 items for you.\n\n**What changed**\n\nThe receipt page says 'Thank you for your order'...re done. Merge #211 counts only once every item above is accepted; an answer that sends the PR back is not accepted.\n".count
_ test_the_prose_draws_the_line_of_a_carried_sheet_with_a_conflict_fix[stack] __
/home/user/wt-2600-b/plugins/superheroes/lib/tests/test_sheet_conflict_fix_2600.py:102: in test_the_prose_draws_the_line_of_a_carried_sheet_with_a_conflict_fix
    assert prose.count(LINE) == 1 and prose.count("A code conflict was fixed") == 1
E   AssertionError: assert (0 == 1)
E    +  where 0 = <built-in method count of str object at 0x13547070>('A code conflict was fixed when the base was brought in, and it was judged immaterial: the fix only renamed a local variable')
E    +    where <built-in method count of str object at 0x13547070> = '**Gift cards**: 1 item for you.\n\n**What changed**\n\nCustomers can buy a gift card, spend it at checkout and see wh...one. Merge stack #4 counts only once every item above is accepted; an answer that sends the PR back is not accepted.\n'.count
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_sheet_conflict_fix_2600.py::test_the_prose_draws_the_line_of_a_carried_sheet_with_a_conflict_fix[pr]
FAILED plugins/superheroes/lib/tests/test_sheet_conflict_fix_2600.py::test_the_prose_draws_the_line_of_a_carried_sheet_with_a_conflict_fix[stack]
2 failed, 15 deselected in 1.81s
```

**Restore:** the inverse Edit-tool edit (`if False and isinstance(why, str):` back to `if isinstance(why, str):`).
**Restore receipt** (a search of the file after the restore): `561:    if isinstance(why, str):`

### raw green

```
..                                                                       [100%]
2 passed, 15 deselected in 1.59s
```

## E-cf-schema: the schema property's minLength

- **guarded element:** `sheet.schema.json`, `$defs/prSheet/properties/carriedForward/properties/conflictFix`, the line `"minLength": 1`.
- **axis:** the built sheet with `conflictFix` validates; the same sheet with `conflictFix` `""` does not.
- **neutralization:** the `"minLength": 1` line (and the comma before it) was removed from the `conflictFix` property, leaving `"type": "string"` alone.
- **detector:** `test_the_built_sheet_validates_and_an_empty_conflict_fix_does_not`, run as `-k "built_sheet_validates"`, `--tb=short`.

### raw red

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_the_built_sheet_validates_and_an_empty_conflict_fix_does_not _______
/home/user/wt-2600-b/plugins/superheroes/lib/tests/test_sheet_conflict_fix_2600.py:129: in test_the_built_sheet_validates_and_an_empty_conflict_fix_does_not
    assert errors_for(bad) != []
E   AssertionError: assert [] != []
E    +  where [] = errors_for({'schema': 'superheroes-sheet/1', 'kind': 'pr', 'title': 'Reword the receipt page', 'prSheet': {'number': 211, 'commit... 'code-reviewer', 'family': 'codex', 'ran': 'engine-record'}], 'caught': [], 'rounds': 1, ...}, 'craft': [], ...}, ...})
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_sheet_conflict_fix_2600.py::test_the_built_sheet_validates_and_an_empty_conflict_fix_does_not
1 failed, 16 deselected in 1.78s
```

**Restore:** the inverse Edit-tool edit (`"type": "string"` back to `"type": "string",` followed by `"minLength": 1`).
**Restore receipt** (a search of the file after the restore, with 4 lines of context):

```
311:            "conflictFix": {
312-              "description": "Present only when a code conflict was fixed when the base was brought in: the vet's one-line reason the fix is immaterial. Alone of the carry's fields, it is shown, as one line on the page and in the chat prose.",
313-              "type": "string",
314-              "minLength": 1
315-            }
```

### raw green

```
.                                                                        [100%]
1 passed, 16 deselected in 1.64s
```

## E-nonote (kept; green only, not neutralized)

The existing E-nonote guards of `i2496_wo_c_sheet_head` (`test_pr_sheet_head_2496.py`, `test_review_template_pr.py`, `test_sheet_prose.py`) are unchanged and pass in the order's one wide run (below), with this change in the tree. The new `test_a_carry_without_a_conflict_fix_and_an_uncarried_sheet_draw_no_line` also passes: a carry without `conflictFix` and an uncarried sheet draw no conflict-fix line on either surface. That new test was not neutralized: no entry in the declared set asks for it, so it is **unproven** by this record (the fix-less and uncarried cases are guarded by the 2496 tests, which this record does not re-prove).

### raw green (tail of the run over the eight files)

```
........................................................................ [ 95%]
..............................................................           [100%]
1358 passed in 71.46s (0:01:11)
```

## Unproven by this record

- `test_the_words_entry_is_the_one_line` and `test_the_builder_keeps_the_conflict_fix_in_the_carry` and `test_the_builder_module_still_refuses_through_the_public_entry`: not neutralized (not in the declared set).
- The `pr_sheet.py` builder line that copies `conflictFix` into the sheet (`sheet["carriedForward"]["conflictFix"] = carry["conflictFix"]`): not neutralized separately. Dropping it would turn E-cf-line-page, E-cf-line-prose and E-cf-schema red through their fixtures, but that was not run.
