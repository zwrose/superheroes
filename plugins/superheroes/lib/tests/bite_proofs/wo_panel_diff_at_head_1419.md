# WO-B bite-proof — panel diff at head (#1419)

## (iv) `_schedule_full_panel_unknown` assigns git-derived diffs

- **Guarded element:** `round_driver.py` — `_schedule_full_panel_unknown` success path sets `state["headDiff"]` and `state["reviewedDiff"]` from `_derive_panel_diff_at_head`.
- **Axis:** materialized `round-N/diff.txt` reflects commit-2 `git diff <base>...HEAD`, not stale round-1 reviewed diff.
- **Neutralization:** removed the two assignment lines (`state["headDiff"] = diff_text` / `state["reviewedDiff"] = diff_text`) while leaving `panelDiffSource` recording in place.
- **Red command:** `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_panel_diff_at_head_1419.py::test_b1_panel_diff_at_head_after_fixer_without_head_diff -q`
- **Red token:** `assert materialized == diff_commit2` (`test_panel_diff_at_head_1419.py:112`) — materialized round-1 diff (`+new`) vs commit-2 (`+fixed head`).
- **Restore:** re-inserted both assignment lines exactly as before neutralization.
- **Green command:** same node as red.
- **Green token:** `1 passed in 6.68s`

## (v) refusal branch parks instead of scheduling panel

- **Guarded element:** `round_driver.py` — `_schedule_full_panel_unknown` failure branch calls `_park_cannot_certify` with `panel-diff-underivable`.
- **Axis:** fail-closed edges never reach `P_PANEL`.
- **Neutralization:** replaced the `_park_cannot_certify` block with the success scheduling path (`unknown-surface` decision, `full-panel-unknown-surface`, `step=P_PANEL`, `return True`).
- **Red command:** `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_panel_diff_at_head_1419.py::test_b2_git_unavailable_parks -q`
- **Red token:** `assert state["certification"]["reason"].startswith(` — `TypeError: 'NoneType' object is not subscriptable` (no park / no `panel-diff-underivable`).
- **Restore:** restored `_park_cannot_certify(...); return False` failure branch.
- **Green command:** same node as red.
- **Green token:** `1 passed in 1.69s`
