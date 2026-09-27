# #1452 bite-proof — the guardian sweep collects what it reports

Per-element bite-proofs for the four collection faults (duplication census, coupling invocation, the verify placeholder, silent deps coverage) and for the advisor-ruled review fixes that ride with them. For each element, the production code was neutralized with one targeted edit, the named test(s) ran and went red on the guarded axis, and then the edit was reverted with the inverse edit. The detectors were unedited throughout.

**Head proven:** `2411912d`, the final code head. The proofs ran in a detached probe worktree at that commit, not in the build worktree. After the last revert, `git status --porcelain` in the probe tree was empty and no `BP-` marker was left in any file.

**Provenance:** the orchestrator ran these proofs (workhorse, Claude Opus 5.5, launch-25de1da591b0346b), at the final head after review session 2 ended.

**Command:** each run used the exact node ids below, never `-k`:

```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/bite-pyc-1452 -m pytest <node ids> -q -p no:cacheprovider
```

Test files: `D` = `plugins/superheroes/lib/tests/test_guardian_lens_duplication.py`, `C` = `.../test_guardian_lens_coupling.py`, `S` = `.../test_guardian_sweep.py`, `V` = `.../test_guardian_vitals.py`. Line numbers are at `2411912d`. Temp paths in red output are shortened to `<tmp>`.

## Declared guarded-element set

The build brief declared seven elements: A1, A2, B1, B2, C1, C2, C3. The advisor's rulings added more: M1–M3 (the `--max-depth 1` swap, 07:48Z), V9 (08:44Z→10:45Z), V10 (08:44Z) and V8 (13:06Z). The review rounds added R7, R9, V0 and V3 as confirmed findings with tests. A3 and A1e2e prove the DoD's end-to-end duplication pin. B1 now proves the census-file operands, the shape the swap replaced B1's first design with.

## Summary

| ID | Guarded element (file:line) and axis | Neutralization | Proving node(s) | Exact red |
|---|---|---|---|---|
| A1 | `guardian_lens_duplication.py:843`. **Axis:** a source-unit count above the file count never degrades. | Re-add the removed gate before `scan_ratio`: `if scanned > tracked_count: return … not_collected("jscpd scanned %d files but only %d were in the tracked-file config path list …")` | `D::test_source_unit_count_above_tracked_still_collects[3]`, `[5]` | `assert 'not-collected' == 'collected'` (both) |
| A1e2e | Same gate, end to end with real jscpd 5.0.12. | Same edit. | `D::test_jscpd_scanned_set_equals_tracked_list_end_to_end` | `('not-collected', 'jscpd scanned 4 files but only 3 were in the tracked-file config path list — the census file list was not honored', None)`. This is the production fault's exact shape: a markdown file with a fenced block counts twice. |
| A2 | `guardian_lens_duplication.py:850`, the reported-path membership check. **Axis:** an escaped path degrades. | Insert `escaped = None` before `if escaped is not None:` | `D::test_reported_path_outside_census_degrades`, `D::test_self_clone_outside_census_degrades` | `assert 'collected' == 'not-collected'` (both) |
| A3 | `guardian_lens_duplication.py:788`, jscpd fed the tracked list only. **Axis:** an untracked tree never reaches a candidate. | `json.dump({"path": abs_paths}, …)` → `json.dump({"path": [os.path.realpath(cwd)]}, …)` (a directory scan, the pre-census shape) | `D::test_jscpd_scanned_set_equals_tracked_list_end_to_end` | `('not-collected', 'jscpd reported a path outside the tracked-file census (checkouts/junk/a.py) — the census file list was not honored', None)` |
| B1 | `guardian_lens_coupling.py:1649`, `_js_targets`. **Axis:** operands are the tracked census files, never a directory or `"."`. | `return sorted({rel_file …})` → `return ["."]` | `C::test_js_targets_are_the_census_files`, `C::test_collect_argv_passes_only_tracked_files` | `assert ['.'] == ['next.config... 'src/app.ts']`; argv `['<tmp>/test_collect_argv_passes_only_0'] == ['<tmp>/…/src/app.ts']` |
| B2 | `guardian_lens_coupling.py:1043`, the crash reason. **Axis:** it names the fatal stderr line, not a stack frame. | `if any(m in low …)` → `if False and any(m in low …)` | `C::test_depcruise_crash_reason_names_fatal_cause` | `assert 'heap out of memory' in 'coupling js: depcruise exited -6 — 79: 0x18cf504e4 start (/usr/lib/dyld) (killed by sigabrt)'`. This is the illegible reason weekly-eats saw. |
| M1 | `guardian_coupling_adapters.py:206`, `"--max-depth", "1"`. **Axis:** an untracked import chain is not followed. | Delete the `"--max-depth", "1",` line | `C::test_untracked_import_chain_is_not_followed_end_to_end` (real depcruise), `C::test_depcruise_argv_is_constant_size_with_max_depth` | `AssertionError: src/v.ts` / `assert not True` (real depcruise walked u→v); `ValueError: '--max-depth' is not in list` |
| M2 | `guardian_lens_coupling.py:1670–1671`, the edge post-filter. **Axis:** an edge with an untracked endpoint never counts. | `and _rel_posix(repo, t_abs) in tracked_rel` → `or …` | `C::test_tracked_to_untracked_edge_is_dropped` | `assert 2 == 1` |
| M3 | `guardian_coupling_adapters.py:210`, the argv shape. **Axis:** never a per-file regex. | Before `return append_repo_operands(…)`: `argv += ["--include-only", "\|".join(targets)]` | `C::test_depcruise_argv_is_constant_size_with_max_depth` | `assert ['depcruise',...x-depth', ...] == [...]` / `At index 12 diff: '<tmp>/src/a.ts\|<tmp>/…'` (the 3-operand and 300-operand prefixes diverge) |
| V9a | `guardian_lens_coupling.py:1015–1020`, the over-budget reason. **Axis:** it names the budget, the usage and the remedy. | Drop `— remedy: batch the depcruise into budget-sized runs` from the reason | `C::test_operand_budget_exceeded_degrades_without_invoking_depcruise` | `assert 'remedy: batch the depcruise into budget-sized runs' in 'coupling js: tracked-file operand payload is 159 bytes across 1 files, exceeding the derived 1-byte operand budget (platform ARG_MAX 1048576 after child env and fixed argv); not measured'` |
| V9b | `guardian_lens_coupling.py:1129`. **Axis:** the collected JS section records the budget on every run. | Delete `"argvOperandBudgetBytes": budget,` | `C::test_js_collected_section_records_operand_payload_and_argv_budget` | `KeyError: 'argvOperandBudgetBytes'` |
| C1 | `guardian_sweep.py:457`, `{baseRef}` substitution. **Axis:** the command runs with a pinned commit, never the raw token. | `vcmd = vcmd.replace(VERIFY_BASE_TOKEN, pin)` → `pass` | `S::test_verify_command_binds_base_ref_to_origin_head` | `assert ['echo --base {baseRef}'] == ['echo --base cb005d91…']` |
| C2 | `guardian_sweep.py:435`, an unresolvable base. **Axis:** the command is `not-run`, never run raw. | `if pin is None:` → `if False and pin is None:` and the paired `else:` → `elif pin is not None:` (the unresolved command falls through and runs raw) | `S::test_verify_command_unresolvable_base_ref_is_not_run` | `assert ['echo --base {baseRef}'] == []` |
| C3 | `guardian_sweep.py:367`, `_coverage_entry_unbound`. **Axis:** a tool-named entry with no lens is reported. | Insert `return False` as the first line | `S::test_coverage_entry_with_tool_but_no_lens_is_reported` | `assert 'present' == 'unbound'` |
| V8 | `guardian_sweep.py:456`. **Axis:** a bound run with HEAD ahead of base is diff-scoped. | `verify_diff_scoped = True` → `False` | `S::test_verify_diff_scoped_head_ahead_of_base_pytest_summary_not_suite_vitals` | `assert 4 is None` (the selected tests' `3 passed, 1 skipped` published as `suiteTestCount`) |
| V8v | `guardian_vitals.py:496`. **Axis:** diff-scoped verify output never becomes suite vitals. | `if verify_result.get("diffScoped") is True:` → `if False and …` | `V::test_diff_scoped_verify_skips_suite_vitals_despite_pytest_summary` | `AssertionError: suiteRuntimeSeconds` / `assert 1.23 is None` |
| R7 | `guardian_sweep.py:348`. **Axis:** a dirty tree at base-equals-HEAD is diff-scoped. | `return bool(paths)` → `return False` | `S::test_verify_diff_scoped_dirty_worktree_at_head_pytest_summary_not_suite_vitals` | `KeyError: 'diffScoped'` |
| R9 | `guardian_sweep.py:346–347`. **Axis:** an unreadable worktree state fails closed to diff-scoped. | `if paths is None: return True` → `return False` | `S::test_verify_diff_scoped_git_unavailable_at_head_pytest_summary_not_suite_vitals` | `KeyError: 'diffScoped'` |
| V10 | `guardian_sweep.py:359`, the base-equals-HEAD stamp. **Axis:** zero selected tests, with the named note. | `return {"testsSelected": 0, "note": …}` → `return {}` | `S::test_verify_command_binds_base_ref_to_origin_head` | `KeyError: 'testsSelected'` |
| V10v | `guardian_vitals.py:513`. **Axis:** at base-equals-HEAD, the verify wall clock is never the suite runtime. | `if (base_equals_head_note == …` → `if (False and base_equals_head_note == …` | `V::test_base_equals_head_verify_skips_suite_runtime_wall_clock` | `assert 4.2 is None` |
| V0 | `guardian_sweep.py:279`, the base pin. **Axis:** a local tag named `origin/<base>` never shadows `refs/remotes/origin/<base>`. | `"refs/remotes/origin/%s" % name` → `"origin/%s" % name` | `S::test_verify_command_base_ref_ignores_shadowing_origin_tag` | `At index 0 diff: 'echo --base c8b2e92a…' != 'echo --base 0ee0595c…'` (the tag's older commit was bound) |
| V3 | `store_core.py:312`, the gh-merge-base lookup. **Axis:** a configured gh-merge-base wins over origin/HEAD. | `if merge_base:` → `if False and merge_base:` | `S::test_verify_command_binds_base_ref_to_gh_merge_base` | `At index 0 diff: 'echo --base f7899074…' != 'echo --base aa2ec086…'` (bound to origin/HEAD's commit) |

## Green

After each element, its node(s) ran green following the inverse edit. The exceptions are R7, V9b, V10 (sweep side) and V3. R7's node ran green inside the R9 red run (`1 failed, 1 passed`); the other three are covered by the combined run. The combined run at the end covered every proving node above: **23 passed** (`ALL-green`). A baseline run of the same 23 nodes before any mutation was green too: **23 passed**, none skipped. Real depcruise and jscpd were present, so the real-seam nodes ran.

## Disclosures

- **C2, first attempt, rejected (wrong axis).** Flipping only `if pin is None:` went red with `TypeError: replace() argument 2 must be str, not None`, which is a crash rather than the command running. The recorded C2 also routes the `else:` branch, so the unresolved command runs raw (the pre-fix behaviour), and the red is on the not-run axis.
- **V8, one void green.** The first V8 green run happened with V8v's neutralization still applied, so it was recorded as void. Both nodes then ran green together after V8v's restore (`V8-V8v-green`: 2 passed).
- **V8's sweep-level node asserts on vitals.** `S::test_verify_diff_scoped_head_ahead_of_base_…` goes red through `guardian_vitals.collect` (`assert 4 is None`), not on a `diffScoped` key. Both are the same guarantee from the public path: selected-test counts are never published as suite vitals.
- **The bare-name fallback in `_pin_name_to_commit` has no proof.** No element was declared for it. It is unchanged by this build and can still be shadowed when no remote-tracking ref exists. That is listed as a follow-up.
