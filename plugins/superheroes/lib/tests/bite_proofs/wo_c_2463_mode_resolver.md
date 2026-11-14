# Bite-proof record — the stack search reads the session mode through the one resolver (#2463)

Detectors: `plugins/superheroes/lib/tests/test_break_it_stack_layers_2463.py::test_8b_a_session_whose_mode_the_resolver_cannot_resolve_is_not_a_stack_layer` and `plugins/superheroes/lib/tests/test_ssot_drift.py::test_round_driver_and_review_base_guard_raw_mode_read_census`, unedited between each red and its green. The implementer recorded G10–G11 in its own worktree; the build session re-ran both in a detached probe worktree at `219a2c5`, and the captures below are from those re-runs. Each neutralization is one targeted Edit, restored by the inverse Edit; `git status --porcelain` on the probe worktree was empty after the last restore.

Command for every red and green, from the probe worktree root: `scripts/pinned-python -B -X pycache_prefix=<scratch>/pyc-probe -m pytest plugins/superheroes/lib/tests/test_ssot_drift.py plugins/superheroes/lib/tests/test_break_it_stack_layers_2463.py -q -p no:cacheprovider`, its output filtered to the `FAILED` lines, the census diff headers and the count line (the captures are partial). Nothing was redacted.

The declared guarded-element set is G10 and G11 (work order WO-C).

## G10. An unresolved mode is not a pull request session (`round_driver.py`, `_stack_layers_above`)

- **Axis:** a `meta.json` with no mode, or an invalid one, never reaches the stack read (the resolver's fail-closed default reads `pr`, so the `resolved` leg is what stops it).
- **Neutralization:** `if (not mode["resolved"] or mode["mode"] != session_mode.MODE_PR` became `if (mode["mode"] != session_mode.MODE_PR`.
- **Raw red:**
```
E             Extra items in the left set:
E             Extra items in the right set:
FAILED plugins/superheroes/lib/tests/test_ssot_drift.py::test_round_driver_and_review_base_guard_raw_mode_read_census
FAILED plugins/superheroes/lib/tests/test_break_it_stack_layers_2463.py::test_8b_a_session_whose_mode_the_resolver_cannot_resolve_is_not_a_stack_layer
2 failed, 124 passed in 5.00s
```
  The axis red is `test_8b_…`; the census red is a side effect of the changed line.
- **Restore:** the inverse Edit.

## G11. The census lists the new mode-shaped site (`test_ssot_drift.py`, `_EXPECTED_RAW_MODE_READS`)

- **Axis:** a mode-shaped line in `round_driver.py` the census does not list fails the census.
- **Neutralization:** the entry `'if (not mode["resolved"] or mode["mode"] != session_mode.MODE_PR',` removed.
- **Raw red:**
```
E             Extra items in the left set:
FAILED plugins/superheroes/lib/tests/test_ssot_drift.py::test_round_driver_and_review_base_guard_raw_mode_read_census
1 failed, 125 passed in 41.94s
```
- **Restore:** the inverse Edit. Final green after both restores: `126 passed in 5.28s`.
