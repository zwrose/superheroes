# Layer 4d part (i) bite-proof record — stale-diff fail-open (arm D shadow of #1419)

Guarded-element set, declared in the build brief before code: the git derivation (E1), the panel
guard (E2), both together (E3, the issue-named proof), the two admission rules (E4a header, E4b
strict UTF-8), the marker clear (E5), and the one-entry census (E6).

Every neutralization was a targeted edit to `plugins/superheroes/lib/round_driver.py` in a detached
probe worktree at `78577727`, reverted by the inverse edit. Detectors unedited throughout.
Restore receipt for the whole set: `git status --porcelain` in the probe tree after the last
restore printed nothing; green run: `test_layer4d_stale_diff_1419.py` (5) plus
`test_round_driver.py::test_fixer_unreadable_head_diff_path_schedules_full_panel` — `6 passed`.

## E1 — the derivation feeds the panel (`_fold_fixer`)

- **Neutralization:** `if head is None:` → `if False and head is None:`
- **RED:** `test_unknown_head_diff_is_derived_from_git_for_the_full_panel` —
  `AssertionError: {'panels': [1]}` / `assert [1] == [1, 2]` (the loop parked instead of running a
  panel over the derived diff).
- **Restore:** inverse edit.

## E2 — the panel guard (`_enter_panel`), derivation unavailable

- **Neutralization:** `if state.get("_reviewedDiffStale"):` → `if False and state.get("_reviewedDiffStale"):`
- **RED:** `test_underivable_unknown_head_diff_parks_reviewed_diff_stale` —
  `AssertionError: {'panels': [1, 2]}`; `test_fixer_unreadable_head_diff_path_schedules_full_panel` —
  `AssertionError: a panel must never review the pre-fix diff`.
- **Restore:** inverse edit.

## E3 — both neutralized (the issue's named proof)

- **Neutralization:** E1 and E2 together.
- **RED:** `test_unknown_head_diff_is_derived_from_git_for_the_full_panel` —
  `AssertionError: the round-2 panel reviewed the pre-fix diff` (round-2 `diff.txt` equals the
  round-1 diff byte for byte).
- **Restore:** E1 restored first (leaving E2 for its own red), then E2.

## E4a — admission requires a `diff --git ` header

- **Neutralization:** `return text if text.startswith("diff --git ") else None` → `return text`
- **RED:** `test_derivation_admits_only_a_non_empty_utf8_git_diff` — `AssertionError: assert '' is None`
  (the empty base...head diff was admitted).
- **Restore:** inverse edit.

## E4b — strict UTF-8 decode

- **Neutralization:** `proc.stdout.decode("utf-8")` → `proc.stdout.decode("utf-8", errors="replace")`
- **RED:** same test — the latin-1 content diff came back as text (`+s = 'caf�'`) instead of None.
- **Restore:** inverse edit. (A first E4b run was taken while E4a's restore had not yet applied —
  the edit tool refused an ambiguous match; that run is discarded and the decisive run above was
  taken with only E4b neutralized, confirmed by `git diff` showing one changed line.)

## E5 — a known head clears the stale marker (`_advance_reviewed_diff`)

- **Neutralization:** removed `state.pop("_reviewedDiffStale", None)`
- **RED:** `test_a_known_head_diff_clears_the_stale_marker` — `'_reviewedDiffStale' not in {...: True ...}` failed.
- **Restore:** inverse edit.

## E6 — the one-entry census

- **Neutralization:** the verify-then-panel branch `_enter_panel(state)` → `state["step"] = P_PANEL`
- **RED:** `test_only_the_guarded_entry_schedules_a_panel_after_round_one` —
  `AssertionError: {'_enter_panel', '_fold_verify', '_seed_resume'}`.
- **Restore:** inverse edit.
