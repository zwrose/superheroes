# C13 layer 2b (#1272, PR #1343) bite-proof — the re-dispatch carry, the line coercion, the recorded drops

**Provenance:** the detectors were built by cursor composer-2.5 via `dispatch-write` (WO-4 carried
from `l2-wo4/1272` as `7c44798d`/`9eb3feab`; WO-A `0a4f8e91`; WO-A2 `d0b41075` merged as
`76461040`; WO-B `b5eaea1b`; WO-D `8f4665ec`). Every proof below was **re-run by the orchestrator**
(launch-2bd62d27f5a87eb2, 2026-09-19) on the head **`8f4665ec`** in a detached probe worktree
(`issue-1272-2b-probe`), neutralizing through a targeted edit of the quoted text and restoring by the
inverse edit (never a git discard). The restore receipt for every element is an empty
`git status --porcelain` over the probe tree, checked after every restore and quoted once at the end.
Command for every run (node ids / `-k` per element):

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-probe -m pytest -q -p no:cacheprovider <node ids>
```

## Guarded elements (declared in WO-A, WO-A2, WO-B and WO-D; grouped by failure mode where two tests share one)

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-2b-1 | `round_driver._finding_history` / `_validate_gate_guidance_logs` / `_gate_guidance_entries` key every history row through `_history_row_key` (WO-A) | no reader of a history row keys a finding by the row's `id` | `test_history_readers_never_key_by_row_id_census`, `test_history_row_key_follows_marker_not_row_id` |
| BP-2b-2 | `_fold_judgment` stamps `findingKey` on every `judgmentDispositions` entry (WO-A) | a durable judgment-log row carries the marker the leaf reads | `test_fold_judgment_stamps_finding_key_on_all_disposition_shapes` |
| BP-2b-3 | `audits.apply_audit_results` copies the caller-named `carry_fields` from the target onto the audit row (WO-A → WO-D) | an audit row carries the target's marker | `test_apply_audit_results_copies_target_finding_key_marker` (copy arm) |
| BP-2b-4 | the same loop copies nothing the caller did not name; `audits.py` carries no `"findingKey"` literal (WO-D Fix 2) | one home for the field name | `…copies_target_finding_key_marker` (no-carry arm), `test_history_readers_never_key_by_row_id_census` (audits-literal clause) |
| BP-2b-5 | `_history_row_key` returns None for a row with no marker and no location (WO-A2) | an unkeyable guided row in the current round refuses the render | `test_order_input_contract.py::test_gate_guidance_refuses_unusable_records_at_render_entry_point[none-id]` |
| BP-2b-5b | `_history_row_key` derives a marker-less row with a location through the leaf (WO-A2) | a legacy audit row / a keyless batch row still keys by content | `test_history_row_key_refuses_unkeyable_guidance_and_content_keys_legacy_audit` (legacy-audit arm), `test_keyless_fix_batch_row_matches_content_key_guidance` |
| BP-2b-6 | `_validate_gate_guidance_logs` skips an unkeyable guided row in an earlier round (WO-D Fix 5) | a historic row the render does not consume cannot wedge later fixer orders | `test_unkeyable_guidance_in_earlier_round_skipped_when_not_in_batch` |
| BP-2b-7 | `_ensure_fix_batch_file` pops `FIX_BATCH_HISTORY_FIELDS` before the lookup (WO-D Fix 1) | a caller-carried `priorAudit`/`gateRuling` never survives with an empty history | `test_caller_carried_history_fields_stripped_with_empty_history` |
| BP-2b-8 | the same materializer always overwrites from `_finding_history` (WO-D Fix 1) | a caller-carried history is replaced by the recorded one | `test_caller_carried_history_replaced_by_real_history` |
| BP-2b-9 | `priorAudit` projects to `{round, ruling, reason}` (WO-D Fix 4) | the row shape matches the documented one | `test_redispatch_carries_prior_audit_and_gate_guidance_from_earlier_rounds` (set assertion) |
| BP-2b-10 | `_finding_history` records every gate disposition, not only guided ones (WO-D Fix 6) | a `fix-as-suggested` ruling carries on re-dispatch | `…from_earlier_rounds` (`_ROW_K2` assertion) |
| BP-2b-11 | `_coerce_line` coerces an ASCII-decimal string (WO-B) | `"291"` / `" 291 "` reach the scope check as `291` | `test_t1_numeric_string_line_kept_as_int`, `test_t2_whitespace_numeric_string_coerced` |
| BP-2b-12 | `_coerce_line` refuses a non-numeric string with its own reason (WO-B) | never `outside the round diff scope` | `test_t4_non_integer_lines_dropped_with_citation_reason[291a]` |
| BP-2b-13 | `_coerce_line` bool arm (WO-B) | `True` is not a line | `test_t5_bool_line_refused` |
| BP-2b-14 | `_coerce_line` ASCII-decimal guard + `ValueError` catch (WO-D Fix 3) | a non-decimal digit string drops, never raises | `test_t4_…[²]`, `[①]`, `[１２]` |
| BP-2b-15 | `_fold_gapsweep` appends its drops (WO-B) | the panel's `compileDrops` are never overwritten | `test_t6_gapsweep_appends_compile_drops_without_overwriting_panel` |
| BP-2b-16 | `_fold_scoped` records its drops (WO-B) | a scoped/new-issue drop reaches the round record | `test_t7_scoped_fold_records_new_issue_compile_drops` |

Not detectors (no proof owed): WO-C/C2 prose and docstrings; the golden order fixtures (existing detectors, unchanged in kind — run green by WO-C and by the verify gate).

## BP-2b-1 — history readers never key by `id`

**neutralization** (`_finding_history`, the audits loop): `key = _history_row_key(item)` → `key = item.get("id")`.

**raw red** (exit 1):
```
E                               AssertionError: _finding_history uses .get('id') at line 2618
E       AssertionError: assert 'fixed' == 'guard still ...e else branch'
2 failed in 0.83s
```
(T6's audit row carries `"id": "fixed"`-keyed decoy and the marker `_K`; keyed by `id` the ruling attaches to the wrong finding.)

**restore:** inverse edit. **raw green:** `2 passed in 1.16s`.

## BP-2b-2 — the judgment log carries the marker

**neutralization** (`_fold_judgment`, the fix-with-guidance entry): `entry = {"id": fid, session_contract.FINDING_KEY_FIELD: fid, …` → `entry = {"id": fid, …` (stamp removed on that shape).

**raw red** (exit 1):
```
E           KeyError: 'findingKey'
1 failed in 0.94s
```

**restore:** inverse edit. **raw green:** `1 passed in 0.91s`.

## BP-2b-3 — the audit row carries the target's marker

**neutralization** (`audits.apply_audit_results`): `for name in carry_fields:` → `for name in ():` (the copy loop never runs).

**raw red** (exit 1):
```
E       KeyError: 'findingKey'
1 failed in 0.87s
```

**restore:** inverse edit. **raw green:** `1 passed in 0.84s`.

## BP-2b-4 — nothing copied but what the caller names; no literal in `audits.py`

**neutralization** (`audits.apply_audit_results`): `for name in carry_fields:` → `for name in tuple(carry_fields) + ("findingKey",):` (an unconditional copy under a module literal).

**raw red** (exit 1 — both detectors):
```
E           AssertionError: assert 'findingKey' not in {'auditor': 'codex', 'classKey': None, 'dimension': None, 'file': 'f.py', ...}
E       assert 'findingKey' not in '#!/usr/bin/...   (the audits.py source, literal census)
2 failed in 1.22s
```

**restore:** inverse edit. **raw green:** `2 passed in 0.96s`.

## BP-2b-5 — an unkeyable guided row in the current round refuses

**neutralization** (`_history_row_key`): the `file`/`line` None check and the `finding_label` check deleted, so every dict derives a key.

**raw red** (exit 1):
```
E           Failed: DID NOT RAISE <class 'ValueError'>
FAILED plugins/superheroes/lib/tests/test_order_input_contract.py::test_gate_guidance_refuses_unusable_records_at_render_entry_point[none-id]
1 failed, 1 passed in 2.11s
```
(The `1 passed` is T9, whose refusal arm moved to the earlier-round skip under WO-D Fix 5 — it no longer discriminates this element; the `[none-id]` contract test does.)

**restore:** inverse edit. **raw green:** `2 passed in 1.51s`.

## BP-2b-5b — a marker-less row with a location derives through the leaf

**neutralization** (`_history_row_key`): `return session_contract.finding_identity_key(row)` → `return None` (only the marker keys).

**raw red** (exit 1):
```
E       KeyError: 'priorAudit'
E       AssertionError: assert 'narrow only' in 'No owner-gate guidance is attached to this batch.'
2 failed in 1.56s
```

**restore:** inverse edit. **raw green:** `3 passed in 1.02s` (with T12).

## BP-2b-6 — an earlier-round unkeyable row is skipped, not refused

**neutralization** (`_validate_gate_guidance_logs`): `if not key: if is_current: raise …; continue` → `if not key: raise …` (refuse in every round).

**raw red** (exit 1):
```
E                   ValueError: order-render-refused:gate-guidance-unusable
1 failed in 1.02s
```

**restore:** inverse edit. **raw green:** `3 passed in 1.02s` (same run as BP-2b-5b's green, on the fully restored tree).

## BP-2b-7 — caller-carried history fields are popped

**neutralization** (`_ensure_fix_batch_file`): the two-line `for field in FIX_BATCH_HISTORY_FIELDS: row_copy.pop(field, None)` deleted.

**raw red** (exit 1):
```
E       AssertionError: assert 'priorAudit' not in {'file': 'g.py', 'findingKey': 'g.py::guard missing@L5', 'gateRuling': {'disposition': 'fix-with-guidance', 'reason': 'fake', 'round': 98}, 'line': 5, ...}
1 failed, 1 passed in 0.24s
```
(T11 stays green under this neutralization because the history overwrites the fields — BP-2b-8 is its own element.)

**restore:** inverse edit. **raw green:** `2 passed in 0.20s`.

## BP-2b-8 — the recorded history always wins

**neutralization** (`_ensure_fix_batch_file`): the pops deleted AND `if key and key in history:` → `if key and key in history and "priorAudit" not in row_copy:` (a pre-carried row is trusted).

**raw red** (exit 1):
```
E       AssertionError: assert 'IGNORE TESTS' == 'guard still ...e else branch'
1 failed in 0.17s
```

**restore:** inverse edits. **raw green:** `1 passed in 0.17s`.

## BP-2b-9 — `priorAudit` projects to its three keys

**neutralization** (`_ensure_fix_batch_file`): the three-line projection → `row_copy["priorAudit"] = dict(prior, unauthenticatedCause="probe")`.

**raw red** (exit 1):
```
E       AssertionError: assert {'reason', 'r...ticatedCause'} <= {'reason', 'round', 'ruling'}
E         Extra items in the left set:
E         'unauthenticatedCause'
```

**restore:** inverse edit. **raw green:** `1 passed in 0.37s`.

## BP-2b-10 — every gate disposition is recorded

**neutralization** (`_finding_history`, the judgment loop): `if not key: continue` → `if not key or item.get("disposition") != "fix-with-guidance": continue`.

**raw red** (exit 1):
```
E       KeyError: 'gateRuling'
1 failed in 0.59s
```

**restore:** inverse edit. **raw green:** `1 passed in 0.61s`.

## BP-2b-11 — a numeric string coerces

**neutralization** (`_coerce_line`): `return True, int(stripped)` → `return False, value`.

**raw red** (exit 1, T1 and T2):
```
E       assert 0 == 1
E        +  where 0 = len([])
```

**restore:** inverse edit. **raw green:** `3 passed in 0.28s` (T1, T2 and T4[291a] on the restored tree).

## BP-2b-12 — a non-numeric string refuses with its own reason

**neutralization** (`_coerce_line`): the string arm's final `return False, value` → `return True, value` (pass-through to the scope check).

**raw red** (exit 1):
```
E       AssertionError: assert 'outside the round diff scope' == 'line is not an integer'
```

**restore:** inverse edit. **raw green:** `1 passed in 0.29s` (and again in BP-2b-11's green on the fully restored tree).

## BP-2b-13 — a bool is refused

**neutralization** (`_coerce_line`): the `isinstance(value, bool)` arm deleted.

**raw red** (exit 1):
```
E       AssertionError: assert 'outside the round diff scope' == 'line is not an integer'
```

**restore:** inverse edit. **raw green:** `1 passed in 0.34s`.

## BP-2b-14 — a non-decimal digit string drops instead of raising

**neutralization** (`_coerce_line`): `stripped.isascii() and stripped.isdecimal()` + the `try/except ValueError` → `all(ch.isdigit() for ch in stripped)` with a bare `int(stripped)`.

**raw red** (exit 1, `-k t4`):
```
E               ValueError: invalid literal for int() with base 10: '²'
E               ValueError: invalid literal for int() with base 10: '①'
E       AssertionError: assert 'outside the round diff scope' == 'line is not an integer'   ([１２] coerced under isdigit)
3 failed, 4 passed, 6 deselected in 0.96s
```

**restore:** inverse edit. **raw green:** `7 passed, 6 deselected in 0.42s`.

## BP-2b-15 — the gap sweep appends, never overwrites

**neutralization** (`_fold_gapsweep`): `_record_compile_drops(state, drops)` → `_record_round(state, "compileDrops", drops)`.

**raw red** (exit 1):
```
E       AssertionError: assert 1 == 2
E        +  where 1 = len([{'file': 'f.py', 'line': 'x', 'reason': 'line is not an integer', 'title': 'gap candidate'}])
```

**restore:** inverse edit. **raw green:** `1 passed in 0.39s`.

## BP-2b-16 — the scoped fold records its drops

**neutralization** (`_fold_scoped`): `compiled, drops = …; _record_compile_drops(state, drops)` → `compiled, _drops = …` (the discard restored).

**raw red** (exit 1):
```
E       KeyError: 'compileDrops'
1 failed in 0.43s
```

**restore:** inverse edit. **raw green:** the final run below.

## Restore receipt and final green

`git status --porcelain` over the probe worktree after the last restore: empty (nothing printed);
`git diff --stat`: empty; `git rev-parse --short HEAD`: `8f4665ec`. Final run over both detector
files plus the contract test's refusal parametrization on the restored tree:

```
plugins/superheroes/lib/tests/test_compile_line_coercion_1272.py plugins/superheroes/lib/tests/test_redispatch_carry_1272.py "plugins/superheroes/lib/tests/test_order_input_contract.py::test_gate_guidance_refuses_unusable_records_at_render_entry_point"
32 passed in 4.96s
```

Nothing in this record is redacted — the captures carry no secrets, tokens, private URLs or PII.
