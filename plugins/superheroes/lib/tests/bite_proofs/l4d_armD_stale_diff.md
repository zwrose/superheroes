# Layer 4d part (i) bite-proof record — stale-diff fail-open (arm D shadow of #1419)

**Final head `67449baa`.** This record supersedes the one written at `78577727`. That record's
guard (`_enter_panel` and the `_reviewedDiffStale` marker) was retired by the advisor's
chokepoint rework (tripwire lift, 2026-09-25) and replaced by one staleness rule,
`_reviewed_diff_is_stale`. The rule reads the reviewed diff's bound head (`reviewedDiffHead`)
against the fix-fold head, and it is consulted at three sites:

- panel-order **emission**, reached by `next`, `advance` and `re-emit`;
- the **consumption** of an already-pending panel order, on `next`, `advance` and `submit`;
- **`run_loop`**, before a panel.

Guarded-element set, as declared by the advisor's rulings (STATE 21:xxZ and 22:0xZ):

- F1 — the consumption check, with three cases.
- F2 — `run_loop`.
- F3 — the emission check, on every entry path.
- F4 — the non-string head-diff normalization.
- F5 — the earlier-round shapes: an empty inline diff, and `git-derived` provenance surviving a
  later slice. The pre-marker persisted session is covered by F1 and F3.

Every neutralization was a targeted edit to `plugins/superheroes/lib/round_driver.py` in a detached
probe worktree at `67449baa`, reverted by the inverse edit. Detectors were left unedited.
**Restore receipt:** after the last restore, `git status --porcelain` in the probe tree printed
nothing. **Green:** `test_layer4d_stale_diff_1419.py`, `18 passed`. The exact refusal token every
parked path must carry is `reviewed-diff-stale`, asserted by `_assert_parked` / the certification
reason.

| # | Neutralization | Red (test → raw) |
|---|---|---|
| F1 | `_stale_pending_panel_park`: `if not _reviewed_diff_is_stale(state):` → `if True or ...` | `test_an_already_pending_stale_panel_is_not_replayed_via_next` → `assert (True and 'dispatch-panel' == 'terminal'` (the older driver's pending panel replayed); `..._not_folded_via_advance` → `{'detail': 'no result or missing envelope at attempt 0 for seat(s): architecture-reviewer, ...', 'seats': [...]}` / `assert (False)` (`incomplete-roster`, never parked); `..._not_folded_via_submit` → `{'foldLanded': True, 'nextStep': 'dispatch-verifiers', ...}` (the stale panel folded) |
| F2 | `run_loop`: `if action == P_PANEL and _reviewed_diff_is_stale(state):` → `if False and ...` | `test_run_loop_never_runs_a_panel_over_a_stale_reviewed_diff` → `{1, 2} == {1}` — `Extra items in the left set: 2` (the reviewer seam ran a round-2 panel) |
| F3 | `_refuse_stale_panel_emission`: `if phase == P_PANEL and ...` → `if False and ...` | `test_persisted_pre_count_state_at_the_panel_parks_stale_via_next` → `'dispatch-panel' == 'terminal'` (attempt 0); `test_stale_panel_cannot_be_emitted_via_durable_advance` → `'dispatch-panel' == 'terminal'`; `test_stale_panel_cannot_be_re_emitted` → `{'action': 'dispatch-panel', 'attempt': 1, ...}`; `test_underivable_unknown_head_diff_parks_reviewed_diff_stale`, `test_persisted_pre_count_state_at_verify_parks_stale`, `test_non_text_inline_head_diff_via_hand_submit_parks_stale` → each `{'panels': [1, 2]}` / `assert [1, 2] == [1]` |
| F4 | `_resolve_head_diff`: `if isinstance(inline, str):` → `if inline is not None:` | `test_inline_head_diff_that_is_not_text_is_unknown` → `assert ({}, 'inline') == (None, 'unknown')`; `test_non_text_inline_head_diff_via_hand_submit_parks_stale` → `{'detail': 'order-render-refused:head-diff-unavailable', 'ok': False, ...}` |
| F5a | `_advance_reviewed_diff`: `if isinstance(head, str):` → `if isinstance(head, str) and head:` (the round-1 truthiness bug) | `test_known_empty_head_diff_rearm_panel_reviews_the_empty_diff` → `{'panels': [1]}` / `assert (1 >= 2)`. **Axis note:** under the chokepoint, the old bug can no longer put a stale panel on the pre-fix diff. The reviewed diff stays unbound, so emission **parks** instead, and the test goes red because the correct re-armed panel over the empty diff never runs. Either way the proof bites: the writer must advance on `""`. |
| F5b | `_fold_fixer`: `_clear_round(state, "reviewedDiffSource")` → `pass` | `test_a_later_inline_slice_clears_git_derived_provenance` and `test_a_later_underivable_slice_clears_git_derived_provenance` → `assert 'reviewedDiffSource' not in {... 'headDiffSource': 'inline' ...}` / `'unknown'` |

| F6 | `_fold_fixer`: `if head is None:` (the git derivation) → `if False and head is None:` | `test_unknown_head_diff_is_derived_from_git_for_the_full_panel` → `{'panels': [1]}` / `assert [1] == [1, 2]` (no derivable diff, so the chokepoint parked instead of running the panel over `git diff base...head`) |
| F7 | `_derive_head_diff_from_git`: `return text if text.startswith("diff --git ") else None` → `return text` | `test_derivation_admits_only_a_non_empty_utf8_git_diff` → `assert '' is None` (an empty base...head diff was admitted) |

The strict-UTF-8 admission leg was proven red at `78577727` (`errors="replace"` let the latin-1
diff through as text), and that code is unchanged since. That record is in this file's history at
`deee3bcc`.
