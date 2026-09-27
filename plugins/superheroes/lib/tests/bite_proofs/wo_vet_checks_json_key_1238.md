# #1238 bite-proof — the `vetChecks` core.md key

Per-element bite-proof for the `vetChecks` key in `core.md`'s JSON block (`plugins/superheroes/lib/core_md.py`, `plugins/superheroes/lib/configure_view.py`). For each element, the production code was neutralized with one targeted edit, the named test(s) ran alone and went red on the guarded axis, and then the edit was reverted. The detectors were unedited throughout.

**Head proven:** `5ced489f`, the final review head. The proofs ran in a detached probe worktree at that commit. After the last revert `git status --porcelain` was empty.

**Provenance:** the orchestrator ran these proofs (workhorse, Claude Opus 5.5). The implementer's first record ran only E1, so it was replaced by this record from final-head runs.

**Command:** each run was the exact node ids below, never `-k`:

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/bite-pyc -m pytest <node ids> -q -p no:cacheprovider
```

Test files: `T` = `plugins/superheroes/lib/tests/test_core_md_vet_checks.py`, `V` = `plugins/superheroes/lib/tests/test_configure_view_vet_checks.py`.

## Summary

| ID | Guarded element (file:line at `5ced489f`) | Neutralization | Proving node(s) | Exact red |
|---|---|---|---|---|
| E1 | core_md.py:135 not-a-list branch | `return []` | `T::test_validate_vet_checks_tokens[None-expected0]` | `assert [] == [{... 'reason': 'vet-checks-not-a-list'}]` |
| E2 | core_md.py:139–141 entry-not-an-object | drop the append, keep `continue` | `T::test_validate_vet_checks_tokens[value3-expected3]` | missing `'vet-checks-entry-not-an-object'` |
| E3 | core_md.py:150–152 missing-field | append → `pass` | `T::test_validate_vet_checks_tokens[value4-expected4]` | `Right contains 3 more items ... 'vet-checks-entry-missing-field'` |
| E4 | core_md.py:145–147 unknown-field | append → `pass` | `T::test_validate_vet_checks_tokens[value5-expected5]` | missing `'vet-checks-entry-unknown-field'` |
| E5 | core_md.py:157 field-not-a-nonempty-string | condition → `False` | `T::test_validate_vet_checks_tokens[value6-expected6]` | missing `'vet-checks-field-not-a-nonempty-string'` |
| E6 | core_md.py:166 duplicate-name | condition → `False` | `T::test_validate_vet_checks_tokens[value7-expected7]` | missing `'vet-checks-duplicate-name'` |
| E7 | core_md.py:1819 read verb's malformed leg | malformed value returned as none declared (`dict(base, behind=behind)`) | `T::test_read_vet_checks_malformed_list` | `assert got["declared"] is True` → `assert False is True` |
| E8 | core_md.py:2388 `confirm` carries the key | condition → `False` | `T::test_preservation_matrix[valid-confirm-kwargs0-confirmed]`, `[malformed-confirm-kwargs0-confirmed]` | `assert '__absent__' == [...]` (both) |
| E9 | core_md.py:286 `parse_core` membership | `in block` → `block.get(...)` truthiness | `T::test_read_vet_checks_present_null`, `T::test_read_vet_checks_present_empty_list` | `assert False is True` on `declared` (both) |
| E10 | core_md.py:1848–1849 writer validates before disk | validation → `[]`, raw value passed through | `T::test_write_vet_checks_malformed_refused_bytes_unchanged` | `assert 'written' == 'refused'` |
| E11 | core_md.py:1769 read verb's structural leg | `structural = None` | `T::test_read_vet_checks_two_blocks`, `T::test_read_vet_checks_duplicate_name_member` | `assert None == 'multiple-core-blocks'`; `assert None == 'duplicate-core-key:name'` |
| E12 | configure_view.py:351 view's unreadable/malformed branch | `if reason and False:` | `V::test_view_malformed_no_none_declared` | `'⚠ vet checks unreadable: vet-checks-malformed' in '### Vet checks\n(declared empty — zero vet checks)\n'` fails |
| E13 | core_md.py:192 `render_core` membership | `in facts` → `facts.get(...)` truthiness | `T::test_preservation_matrix[empty_list-confirm-kwargs0-confirmed]` | `assert '__absent__' == []` |
| E14 | core_md.py:2739 empty stdin refused | refusal → `clear_vet_checks(...)` (the old destructive behaviour) | `T::test_cli_write_vet_checks_empty_stdin_refused` | `assert 'written' == 'refused'` |
| E15 | core_md.py:1693 `[]` persists as declared-empty | `require_mapping and not mapping` → `not mapping` | `T::test_write_vet_checks_declared_empty_persists_key`, `T::test_cli_write_vet_checks_literal_empty_list_declared` | `KeyError: 'vetChecks'` on `parsed[_VET_CHECKS_KEY] == []` (the key was deleted, which is the axis); `assert False is True` on `declared` |
| E16 | configure_view.py:376–378 fields collapsed to one line | `_one_line_prose(...)` removed | `V::test_view_multiline_fields_one_line` | `'- A ## Review gate policy' in '### Vet checks\n- A'` fails |
| E17 | configure_view.py:352 absent core renders "none declared" | condition → `False` | `V::test_view_no_core_branch` | `'(none declared — ...)' in '### Vet checks\n⚠ vet checks unreadable: core-md-absent\n'` fails |
| E18 | core_md.py:1884 `--clear` removes the key | `remove_key=True` → `False` | `T::test_write_vet_checks_clear_removes_key`, `T::test_cli_write_vet_checks_clear_flag` | `assert 'vetChecks' not in {...}` (both) |

## Green

Every edit was reverted with an inverse edit, and `git status --porcelain` in the probe tree was empty afterwards. One combined green run then covered every proving node above, with the whole `test_validate_vet_checks_tokens` parametrization: **25 passed**. Before any mutation, a baseline run of both files was green: **76 passed**.

## Literal pins

The external-contract literals are spelled out in the tests, not reached through the constants. The six malformed tokens appear as literals in `test_validate_vet_checks_tokens`'s expected lists and in `test_validate_vet_checks_multi_problem_ordered`. The key `"vetChecks"` is the test module's `_VET_CHECKS_KEY` literal. `test_literal_pins` pins `vet-checks-malformed`, `vet-checks-input-unparseable`, `vet-checks-round-trip-refused` and the field tuple `("name", "evidence", "records")`.

## Disclosures

- **E10, first attempt.** The first neutralization (validation → `[]` alone) went red with `KeyError: 'evidence'` from the stripping step. That red is on the wrong axis, so it was not accepted. The recorded E10 bypasses validation *and* stripping, so the malformed value reaches the disk writer, and the red is on the refusal axis.
- **E14 is proven against the regression it guards**, not by deleting the guard. Deleting the explicit empty-stdin check alone stays green, because empty stdin then falls through to the JSON parse and gets the same `vet-checks-input-unparseable` refusal. The explicit check is belt-and-braces over that parse. The neutralization restores the destructive clear that round 1 of review removed.
