# #1562 WO-1 bite-proof — the `sandboxAccess` calibration key

Bite-proof record for the `sandboxAccess` key in `core.md`'s JSON block (`plugins/superheroes/lib/core_md.py`, `plugins/superheroes/lib/configure_view.py`), detectors in `plugins/superheroes/lib/tests/test_sandbox_access_calibration_1562.py` (`T`).

**Status: no proof was produced. Every element below is `Unrunnable here`.** No neutralization was applied and no red or green was observed, so this record carries no raw captures and no restore receipts. Nothing in it is a claim that a run happened.

## Unrunnable here

- **What refused the run.** Every `pytest` invocation the implementer tried was returned by the harness with `This command requires approval` and did not execute. Three attempts, none ran:
  1. `cd <worktree> && scripts/pinned-python -B -X pycache_prefix=/tmp/claude-501/superheroes-pyc-1562 -m pytest plugins/superheroes/lib/tests/test_sandbox_access_calibration_1562.py -q 2>&1 | tail -60` (the pipe was itself a mistake; refused as a compound command needing approval)
  2. the same command without the pipe, with and without the `cd` prefix (`This command requires approval`)
  3. the same with `-X pycache_prefix` pointed into the session scratchpad and `-p no:cacheprovider` added (`This command requires approval`)
  A non-pytest `scripts/pinned-python -c` call ran fine in the same session, so the refusal is on the pytest invocation, not the interpreter.
- **The exact command and environment that can run it.** From the worktree root, with approval for pytest granted:
  `scripts/pinned-python -B -X pycache_prefix=/tmp/claude-501/superheroes-pyc-1562 -m pytest <node id> -q`
  One node id per element, red then green, as the table names.
- **Substitute evidence actually produced.** Only `ast.parse` of the three changed or new Python files (all parsed) and a whitespace grep. Neither discriminates any case below; neither is a bite-proof.
- **Who owns the outstanding receipt.** The orchestrator, at verification (it re-runs proofs itself). Until then the disclosure is unadjudicated.

## Declared guarded-element set and the planned neutralization per element

Neutralize inside `core_md.py` / `configure_view.py` by a targeted Edit; restore by the inverse Edit. None of these was applied.

| Element | Axis | Planned neutralization | Node to run alone (red, then green) |
|---|---|---|---|
| G1 not-an-object | refusal | the not-dict branch of `validate_sandbox_access` returns `[]` | `T::test_validate_not_an_object` |
| G2 unknown field | refusal | skip the `for key in value` unknown-key loop | `T::test_validate_unknown_field` |
| G3 domains not a list | refusal | drop the `isinstance(domains, list)` check | `T::test_validate_domains_not_a_list` |
| G4 domain invalid | refusal | `_sandbox_domain_ok` returns `True` | `T::test_validate_domain_invalid` (ids are the `repr` of each form, so the red names the forms that went through) |
| G5 not a bool | refusal | `type(value[flag]) is not bool` → `not value[flag]` | `T::test_validate_flag_not_a_bool` (the `1` and `"true"` cases) |
| G6 paths not a list | refusal | drop the `isinstance(paths, list)` check | `T::test_validate_paths_not_a_list` |
| G7 path not absolute | refusal | drop the `not os.path.isabs(entry)` leg | `T::test_validate_path_not_absolute` |
| G8 path is root | refusal | drop the `os.path.normpath(entry).strip("/")` root check | `T::test_validate_path_is_root` |
| G19 configure view | display | `_sandbox_access_view_lines` returns only the heading | `T::test_view_all_off_when_key_absent` and, separately, `T::test_view_configured_values_four_lines` |
| G20 carry-forward | preservation | remove the `SANDBOX_ACCESS_KEY` carry in `confirm_all` | `T::test_carry_forward_confirm_all_keeps_key_byte_equal` |

Token literals are spelled out as strings in the tests (and `test_literal_pins` pins the constants), not reached through the module constants.

## Notes the reader of the proof needs

- **G8 and `//`.** The order says `//` normalizes to `/`. Measured on the pinned interpreter: `os.path.normpath("//")` is `"//"` (POSIX keeps exactly two leading slashes). The root check is therefore `not os.path.normpath(entry).strip("/")`, which refuses `/`, `//`, `/.`, `///`, `/..` and `/a/..`. Neutralizing G8 should redden every form in `test_validate_path_is_root`.
- **G20 chokepoint.** The same carry-forward is also covered at `parse_core` / `render_core` (`test_carry_forward_parse_render_round_trip`) and `read` (`test_carry_forward_read_exposes_raw`). Those are extra detectors beyond the declared set and have no proof of their own.
