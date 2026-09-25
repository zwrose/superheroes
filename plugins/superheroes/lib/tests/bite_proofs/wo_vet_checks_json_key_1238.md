# WO-A (#1238) bite-proof — `vetChecks` json key

Guarded-element set: E1–E13 per work order (validator branches E1–E6, read malformed E7, confirm carry E8, parse_core membership E9, writer pre-disk E10, structural read E11, view malformed E12, render_core membership E13).

**Command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/wo-a-pyc -m pytest <nodeid> -q -p no:cacheprovider
```

## E1 — `vet-checks-not-a-list`

**neutralization** (`core_md.py` `validate_vet_checks`): replace `return [{"index": None, ...}]` for non-list with `return []`.

**red node:** `test_core_md_vet_checks.py::test_validate_vet_checks_tokens[None-expected0]` — assertion expected `vet-checks-not-a-list`, got `[]`.

**restore:** reinstate `return [{"index": None, "field": None, "reason": "vet-checks-not-a-list"}]`.

**green node:** same — 1 passed.

## E2 — `vet-checks-entry-not-an-object`

**neutralization:** skip `if not isinstance(entry, dict)` append; use `continue` only.

**red node:** `::test_validate_vet_checks_tokens[value3-expected3]` — missing `vet-checks-entry-not-an-object`.

**restore:** restore object guard.

**green node:** same — 1 passed.

## E3 — `vet-checks-entry-missing-field`

**neutralization:** remove missing-field loop body.

**red node:** `::test_validate_vet_checks_tokens[value4-expected4]`.

**restore:** restore loop.

**green node:** 1 passed.

## E4 — `vet-checks-entry-unknown-field`

**neutralization:** remove unknown-key loop.

**red node:** `::test_validate_vet_checks_tokens[value5-expected5]`.

**restore:** restore loop.

**green node:** 1 passed.

## E5 — `vet-checks-field-not-a-nonempty-string`

**neutralization:** remove nonempty-string check loop.

**red node:** `::test_validate_vet_checks_tokens[value6-expected6]`.

**restore:** restore loop.

**green node:** 1 passed.

## E6 — `vet-checks-duplicate-name`

**neutralization:** remove duplicate-name tracking append.

**red node:** `::test_validate_vet_checks_tokens[value7-expected7]`.

**restore:** restore tracking.

**green node:** 1 passed.

## E7 — read malformed leg

**neutralization** (`read_vet_checks`): `malformed = []` instead of `validate_vet_checks(raw)`.

**red node:** `::test_read_vet_checks_malformed_list` — expected `reason` `vet-checks-malformed`, got `None`.

**restore:** `malformed = validate_vet_checks(raw)`.

**green node:** 1 passed.

## E8 — confirm membership carry

**neutralization** (`confirm`): remove `if VET_CHECKS_KEY in existing: facts[VET_CHECKS_KEY] = ...` block.

**red node:** `::test_preservation_matrix[valid-confirm-kwargs0-confirmed]` — `vetChecks` dropped after confirm.

**restore:** reinstate membership block.

**green node:** 1 passed.

## E9 — parse_core membership (present null)

**neutralization** (`parse_core`): use `.get(VET_CHECKS_KEY)` collapse instead of `in block` membership.

**red node:** `::test_read_vet_checks_present_null` — `declared` False or reason not malformed.

**restore:** `if VET_CHECKS_KEY in block: out[...] = deepcopy(...)`.

**green node:** 1 passed.

## E10 — writer pre-disk validation

**neutralization** (`write_vet_checks`): skip `validate_vet_checks` refusal (`malformed = []`).

**red node:** `::test_write_vet_checks_malformed_refused_bytes_unchanged` — action `written` not `refused`.

**restore:** reinstate validation refusal.

**green node:** 1 passed.

## E11 — structural read leg

**neutralization** (`read_vet_checks`): `structural = None` instead of `_structural_refusal_at_path`.

**red node:** `::test_read_vet_checks_two_blocks` — reason not `multiple-core-blocks`.

**restore:** reinstate call.

**green node:** 1 passed.

## E12 — view malformed branch

**neutralization** (`_vet_checks_view_lines`): treat `reason` as absent when `vet-checks-malformed`.

**red node:** `::test_view_malformed_no_none_declared` — prints none-declared line.

**restore:** reinstate malformed branch.

**green node:** 1 passed.

## E13 — render_core membership (present `[]` through confirm)

**neutralization** (`render_core`): `if facts.get(VET_CHECKS_KEY):` truthiness instead of `in facts`.

**red node:** `::test_preservation_matrix[empty_list-confirm-kwargs0-confirmed]` — `vetChecks` key lost.

**restore:** `if VET_CHECKS_KEY in facts:`.

**green node:** 1 passed.
