# Bite-proof record — a break-it test kept in a higher stack layer counts as kept (#2463)

Detector file: `plugins/superheroes/lib/tests/test_break_it_stack_layers_2463.py` (26 test nodes), unedited between every red and its green. The implementer recorded G1–G8 in its own worktree; the build session re-ran every entry below itself in a detached probe worktree at the pushed head `76d07e9`, and the captures here are from those re-runs. Every neutralization is one targeted Edit to one production file, restored by the inverse Edit (no `git checkout`, `restore`, `reset` or `stash`, and no shell edit); `git status --porcelain` on the probe worktree was empty after the last restore.

Command for every red and green, from the probe worktree root:
`scripts/pinned-python -B -X pycache_prefix=<scratch>/pyc-probe -m pytest plugins/superheroes/lib/tests/test_break_it_stack_layers_2463.py -q -p no:cacheprovider`, its output filtered to the `FAILED` lines, the failing assertion where shown, and the count line (the traceback bodies are cut, so the captures are partial). No secret, token or private URL appears in any capture; nothing was redacted.

The declared guarded-element set is G1–G8 (work order WO-A) and G9 (work order WO-B); none is grouped.

## DoD — the positive case fails before the change, the three negative cases pass before and after

Run on a detached worktree at the base commit `37965f6` with the test file copied in. On the base code, `test_9a` patches the seam it needs with `raising=False` in the probe copy only, so its red is the behaviour, not a missing name:

```
E       AssertionError: {'shape': None, 'reason': 'break-it test not kept: tests/test_charge_once.py (missing: not-in-head)'}
E       assert True is False
1 failed, 25 deselected in 0.47s
```

That is the field symptom: the review parks `cannot-certify` on a test a higher layer holds. `test_1_…` on the base code errors with `AttributeError: module 'break_it' has no attribute 'check_kept_in_layers'`.

The three negative cases (`test_11_n1_…` not a stack layer, `test_11_n2_…` no layer above holds the test, `test_11_n3_…` a layer above holds a non-matching body), with `test_1_…` and `test_9a_…`:

- base code: `2 failed, 3 passed, 21 deselected` (the two failures are `test_1_…` and `test_9a_…`; the three negatives pass);
- head code: `5 passed, 21 deselected in 1.87s`.

## G1. Only a kept result credits a layer (`break_it.py`, `check_kept_in_layers`)

- **Axis:** a layer holding a changed copy of the test is not the test held.
- **Neutralization:** `if got["outcome"] == KEPT:` became `if got["outcome"] in (KEPT, KEPT_CHANGED):`.
- **Raw red:**
```
FAILED plugins/superheroes/lib/tests/test_break_it_stack_layers_2463.py::test_3_a_higher_layer_file_whose_body_differs_is_not_credited
FAILED plugins/superheroes/lib/tests/test_break_it_stack_layers_2463.py::test_11_n3_a_layer_above_holding_a_non_matching_body_parks_not_in_head
2 failed, 24 passed in 3.48s
```
- **Restore:** the inverse Edit.

## G2. An unresolved layer ends the search as a failed read (`check_kept_in_layers`)

- **Axis:** no later layer is credited over a layer whose git read failed.
- **Neutralization:** `return out("failed", "layer-read-failed:" + str(got["reason"]))` became `continue`.
- **Raw red:**
```
>       assert got["read"] == "failed" and got["reason"].startswith("layer-read-failed:"), got
E       assert ('ok' == 'failed'
FAILED plugins/superheroes/lib/tests/test_break_it_stack_layers_2463.py::test_5_e5_an_unresolved_layer_ends_the_search_though_a_later_layer_holds_a_passing_copy
1 failed, 25 passed in 3.61s
```
- **Restore:** the inverse Edit.

## G3. A layer head absent after the fetch fails the read (`break_it.py`, `_layer_present`)

- **Axis:** an unreadable layer head reads `layer-head-unreadable`.
- **Neutralization:** the final `return _git(repo_root, "cat-file", "-e", oid + "^{commit}").returncode == 0` became `return True`.
- **Raw red:**
```
>       assert got["read"] == "failed" and got["reason"] == "layer-head-unreadable", got
E       AssertionError: {'read': 'failed', 'reason': 'layer-checkout-failed', 'foundIn': None, 'result': None, ...}
FAILED plugins/superheroes/lib/tests/test_break_it_stack_layers_2463.py::test_4_e2_a_layer_head_that_exists_nowhere_fails_the_read
1 failed, 25 passed in 3.16s
```
- **Restore:** the inverse Edit. Green after G1–G3: `26 passed in 3.49s`.
- **Note:** with the guard neutralized the read still fails closed one step later (`layer-checkout-failed`); the red is on the reason the record names, not on a credit.

## G4. The search never raises (`check_kept_in_layers`, the outer handler)

- **Axis:** any error inside the search reads as a failed stack read.
- **Neutralization:** `except Exception:` became `except KeyboardInterrupt:`.
- **Raw red:**
```
FAILED plugins/superheroes/lib/tests/test_break_it_stack_layers_2463.py::test_6_e6_an_exception_inside_the_search_is_a_failed_read_and_nothing_is_raised
1 failed, 25 passed in 4.15s
```
- **Restore:** the inverse Edit.

## G5. Only layers above the reviewed PR are searched (`round_driver.py`, `_stack_layers_above`)

- **Axis:** a member at or below the queried position is never searched.
- **Neutralization:** `and m["position"] > queried["position"]),` became `and m["position"] > -1),`.
- **Raw red:**
```
FAILED plugins/superheroes/lib/tests/test_break_it_stack_layers_2463.py::test_8_stack_layers_above_reads_only_a_linked_pr_sessions_higher_members
FAILED plugins/superheroes/lib/tests/test_break_it_stack_layers_2463.py::test_9a_the_step_credits_a_copy_held_by_a_higher_layer_and_does_not_park
2 failed, 24 passed in 3.63s
```
- **Restore:** the inverse Edit.

## G6. `not-linked` is the only refusal that means "not a stack" (`_stack_layers_above`)

- **Axis:** every other membership refusal is a failed read the record names.
- **Neutralization:** `if result.get("reason") == stack_check.REASON_NOT_LINKED:` became `if True:`.
- **Raw red:**
```
>       assert row["stack"] == {"read": "failed", "reason": "stack-unreadable"}, row
FAILED plugins/superheroes/lib/tests/test_break_it_stack_layers_2463.py::test_8_stack_layers_above_reads_only_a_linked_pr_sessions_higher_members
FAILED plugins/superheroes/lib/tests/test_break_it_stack_layers_2463.py::test_9c_a_stack_that_cannot_be_read_parks_names_why_and_credits_nothing
2 failed, 24 passed in 4.25s
```
- **Restore:** the inverse Edit.

## G7. The kept step searches the layers above on a not-in-head miss (`round_driver.py`, `_break_it_kept_step`)

- **Axis:** the converge gate credits a copy a higher layer holds, and does not park on it.
- **Neutralization:** `if got.get("outcome") == break_it.KEPT_MISSING and got.get("reason") == "not-in-head":` became `if False and got.get(…) …`.
- **Raw red:**
```
FAILED plugins/superheroes/lib/tests/test_break_it_stack_layers_2463.py::test_9a_the_step_credits_a_copy_held_by_a_higher_layer_and_does_not_park
FAILED plugins/superheroes/lib/tests/test_break_it_stack_layers_2463.py::test_9c_a_stack_that_cannot_be_read_parks_names_why_and_credits_nothing
2 failed, 24 passed in 3.38s
```
- **Restore:** the inverse Edit.

## G8. The review record names the layer and commit (`review_record_session.py`, `account_from_session`)

- **Axis:** the record's `checked` list carries the found layer, PR, branch and commit, or the failed read.
- **Neutralization:** the line `checked += _break_it_stack_checked(rounds)` removed.
- **Raw red:**
```
FAILED plugins/superheroes/lib/tests/test_break_it_stack_layers_2463.py::test_10_the_record_names_the_layer_pr_branch_and_commit_or_the_failed_read
1 failed, 25 passed in 3.98s
```
- **Restore:** the inverse Edit (the line put back after its axis comment).

## G9. The negative cases stay not-in-head when a searched layer does not keep the test (`check_kept_in_layers`)

- **Axis:** n2 and n3 reach the layer search on the head code, and no layer is credited unless it keeps the test.
- **Neutralization:** `if got["outcome"] == KEPT:` became `if True:`.
- **Raw red:**
```
FAILED plugins/superheroes/lib/tests/test_break_it_stack_layers_2463.py::test_1_a_test_held_by_a_higher_layer_is_found_with_the_real_runner_and_nothing_is_left_behind
FAILED plugins/superheroes/lib/tests/test_break_it_stack_layers_2463.py::test_2_no_layer_holding_the_test_reads_ok_and_not_found
FAILED plugins/superheroes/lib/tests/test_break_it_stack_layers_2463.py::test_3_a_higher_layer_file_whose_body_differs_is_not_credited
FAILED plugins/superheroes/lib/tests/test_break_it_stack_layers_2463.py::test_5_e5_an_unresolved_layer_ends_the_search_though_a_later_layer_holds_a_passing_copy
FAILED plugins/superheroes/lib/tests/test_break_it_stack_layers_2463.py::test_11_n2_a_stack_layer_with_no_layer_above_holding_the_test_parks_not_in_head
FAILED plugins/superheroes/lib/tests/test_break_it_stack_layers_2463.py::test_11_n3_a_layer_above_holding_a_non_matching_body_parks_not_in_head
6 failed, 20 passed in 3.69s
```
- **Restore:** the inverse Edit. Final green after every restore: `26 passed in 4.28s`.

## Not proven separately

The malformed-layer validation (e1/e7), the scratch and checkout failures (e3/e4), the fetch path (test 7) and the meta.json gate of `_stack_layers_above` (not a PR session, a bool or missing `pr`, a malformed `repo`) are covered by tests but were not neutralized one by one.
