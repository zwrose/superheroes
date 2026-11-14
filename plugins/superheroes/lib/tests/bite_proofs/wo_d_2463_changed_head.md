# Bite-proof record — a changed test on the reviewed head never reaches the stack search (#2463)

Detector: `plugins/superheroes/lib/tests/test_break_it_stack_layers_2463.py::test_12_a_changed_test_on_the_reviewed_head_never_reaches_the_stack_search`, unedited between red and green. The implementer recorded G12 in its own worktree; the build session re-ran it in a detached probe worktree at `ae75d0d`, and the captures below are from that re-run. The neutralization is one targeted Edit, restored by the inverse Edit; `git status --porcelain` on the probe worktree was empty after the restore.

Command, from the probe worktree root: `scripts/pinned-python -B -X pycache_prefix=<scratch>/pyc-probe -m pytest plugins/superheroes/lib/tests/test_break_it_stack_layers_2463.py -q -p no:cacheprovider`, its output filtered to the `FAILED` lines and the count line (partial captures). Nothing was redacted.

The declared guarded-element set is G12 (work order WO-D).

## G12. Only a not-in-head miss reaches the stack search (`round_driver.py`, `_break_it_kept_step`)

- **Axis:** a reviewed head holding a changed copy of the test keeps its `changed` row and never reads the stack, even when a higher layer holds the original passing test.
- **Neutralization:** `if got.get("outcome") == break_it.KEPT_MISSING and got.get("reason") == "not-in-head":` became `if got.get("outcome") != break_it.KEPT:`.
- **Raw red:**
```
FAILED plugins/superheroes/lib/tests/test_break_it_stack_layers_2463.py::test_12_a_changed_test_on_the_reviewed_head_never_reaches_the_stack_search
1 failed, 27 passed in 4.94s
```
  With the guard broadened, the changed row went to the stack search, the higher layer's copy was credited and the step did not park.
- **Restore:** the inverse Edit. Green: `28 passed in 4.44s`.
