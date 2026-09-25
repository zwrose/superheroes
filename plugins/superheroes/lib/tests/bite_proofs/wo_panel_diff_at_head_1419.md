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

## P1 — producer must not fall back to live HEAD (ruling proof 1)

- **Guarded element:** `review_diff_bytes.py` — `run_git_diff_three_dot` subprocess argv.
- **Axis:** post-verify panel diff stays bound to `verified_head`, not repo HEAD after a later commit.
- **Neutralization:** replaced `"%s...%s" % (base_sha, head_sha)` with `"%s...HEAD" % base_sha`.
- **Red command:** `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_panel_diff_at_head_1419.py::test_b4_commit_after_verify_panel_reviews_verified_head -q`
- **Red token:** `assert state["reviewedDiff"] == diff_at_h1`
- **Restore:** restored `"%s...%s" % (base_sha, head_sha)` in the argv tuple.
- **Green command:** same node as red.
- **Green token:** `1 passed in 7.24s`

## P2 — handback must share the producer (ruling proof 2, 1a)

- **Guarded element:** `handback_gate.py` — `_recompute_diff_sha256` must call the shared producer.
- **Axis:** handback digest matches producer bytes across consumers (`test_b3`).
- **Neutralization:** inlined `subprocess.run(["git", "-C", repo_root, "diff", "--no-renames", "%s...%s" % (base_sha, head_sha)], …)` and hashed `r.stdout + b"\0"` (rename-only fixture bytes matched with/without `--no-renames`; appended byte discriminates digest drift).
- **Red command:** `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_panel_diff_at_head_1419.py::test_b3_review_diff_producer_byte_identical_across_consumers -q`
- **Red token:** `assert handback_digest == hashlib.sha256(panel_bytes).hexdigest()`
- **Restore:** restored `review_diff_bytes.run_git_diff_three_dot(...)` and `hashlib.sha256(r.stdout).hexdigest()`.
- **Green command:** same node as red.
- **Green token:** `1 passed in 6.63s`

## P3 — verify-then-panel must refresh diff at verified head (ruling proof 2, 2a)

- **Guarded element:** `round_driver.py` — `VERIFY_THEN_PANEL` arm of `_fold_verify`.
- **Axis:** panel materializes diff at verify-time head when HEAD moved after pre-verify derivation.
- **Neutralization:** removed the `_refresh_panel_diff_at_verified_head(...)` call (kept `state["step"] = P_PANEL`).
- **Red command:** `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_panel_diff_at_head_1419.py::test_b1_panel_diff_follows_head_moved_between_fixer_and_verify -q`
- **Red token:** `assert materialized == diff_at_verify_head`
- **Restore:** re-inserted the `_refresh_panel_diff_at_verified_head(...)` guard before `P_PANEL`.
- **Green command:** same node as red.
- **Green token:** `1 passed in 21.68s`
