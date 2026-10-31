# C1 L2 bite-proof record: the grounding seat is retired (#2206)

The builder's own re-run of every detector this layer adds or changes, at head `753b4ec9`, in a detached probe
worktree (`git worktree add --detach`), so no probe touched the build tree. Each neutralization was one targeted
`Edit`, restored by the inverse `Edit`; after the last restore `git status --short` in the probe worktree printed
nothing (the restore receipt), and the green run below is over the restored tree. The implementers' own
red-and-green runs of the same elements are in their dispatch reports (WO-2, WO-2c, WO-3, WO-4); this record is the
builder's independent re-run. The `warning: The UV_NATIVE_TLS ...` line is the launcher's, not the test's. Nothing
below is redacted: the captures hold no secret, token or private URL.

Command for every red and the green: `scripts/pinned-python -B -X pycache_prefix=<scratch> -m pytest
plugins/superheroes/lib/tests/test_grounding_retired_c1l2.py <and, for BP-9/BP-10, the two named test_ssot_drift
nodes> -q -p no:cacheprovider`. Elements in different files were neutralized together in three batches (BP-1, 3, 9,
10; BP-2, 5, 6, 7; BP-4, 8); each element's red is read off its own node and its own assertion below, so every red
is on its own axis.

Green, all elements restored: `60 passed in 5.84s`.

## BP-1. no roster composes the retired seat

- Axis: `seat_map.BASE_ROSTER` holds lens seats only.
- Neutralization (`seat_map.py`): `BASE_ROSTER = ("code-reviewer", "test-role")` became
  `BASE_ROSTER = ("code-reviewer", "test-role", "grounding-seat")`.
- Red: `FAILED ...test_grounding_retired_c1l2.py::test_the_retired_seat_is_gone_from_the_seat_vocabulary`.

## BP-2. a new record carries no not-run seat list

- Axis: `review_record.build_record` emits no `seatsNotRun`.
- Neutralization (`review_record.py`): `"missingReviews": missing,` became
  `"missingReviews": missing, "seatsNotRun": [{"name": "x", "reason": "r", "why": "w"}],`.
- Red: `E       AssertionError: assert 'seatsNotRun' not in {'ok': True, 'url': 'http://c/2', ...}` on both
  `test_a_driver_built_record_from_a_map_naming_the_retired_seat_has_no_not_run_line_and_does_not_park[seated]`
  and `[unfilled]`, and on `test_a_hand_written_account_with_a_never_run_seat_is_a_missing_review_not_a_not_run_line`.

## BP-3. the account refuses `notRunReason` on any row

- Axis: the account check `chk(r.get("notRunReason") is None, ...)`.
- Neutralization: that line became `chk(True, f"reviewers[{i}].notRunReason")`.
- Red: all 18 cases of `test_a_not_run_reason_on_any_reviewer_row_is_refused` (`[0-old-token]` to `[2-false]`),
  `E       AssertionError: assert {'ok': True, ...} == {'ok': False,...notRunReason'}`.

## BP-4. a merge sheet shows nothing of an earlier record's `seatsNotRun`

- Axis: `pr_sheet` renders no not-run line.
- Neutralization (`pr_sheet.py`, the history lines): added
  `lines += [f"{s['name']} did not run: {s['why']}." for s in r.get("seatsNotRun") or []]` before `gaps =`.
- Red: `test_an_earlier_record_with_seats_not_run_builds_and_its_sheet_names_no_such_line`,
  `E       assert ('grounding' not in '{"schema": ..."cards": []}'` with
  `"grounding-seat did not run: no loop phase runs it, so no reviewer checked the pr body's claims."`.

## BP-5. a retired member of a persisted roster never parks the lane (c1l2_wo2_move_up_roster_filter)

- Axis: `review_record._move_up_blocker` reads only roster members in `seat_map.KNOWN_SEATS`.
- Neutralization: `roster = [n for n in roster if n in seat_map_module.KNOWN_SEATS] if isinstance(roster, list) else None`
  became `roster = list(roster) if isinstance(roster, list) else None`.
- Red: `test_reading_next_ignores_a_retired_member_of_a_persisted_roster`, `E       assert 'park' == 'move-up'`
  (`{'next': 'park', 'reason': 'a roster seat in the seat map is unfilled'}`); and
  `test_reading_next_with_only_retired_members_has_no_roster`,
  `{'reason': "the seat map's roster omits a panel seat: code-reviewer, test-role"} != {'reason': 'the seat map has no roster'}`.

## BP-6. `reviewer` stays a codex role-pin tier

- Axis: `seat_map._PANEL_PIN_TIERS` includes the backfill downgrade tier.
- Neutralization: `frozenset(DEFAULT_TIER_BY_SEAT.values()) | {_BACKFILL_DOWNGRADE_TO}` became
  `frozenset(DEFAULT_TIER_BY_SEAT.values())`.
- Red: `test_reviewer_stays_a_codex_role_pin_tier_after_the_retired_seat_took_its_default_with_it`,
  `E       AssertionError: assert ('reviewer' in frozenset({'reviewer-deep'}))`.

## BP-7. an all-pinned roster narrows the backfill tier's cells to the pinned vendors

- Axis: `reachable_configs` adds the backfill tier for pinned vendors only when no seat rotated.
- Neutralization: `if any_seat_rotated:` became `if True:`.
- Red: `test_the_backfill_tier_follows_the_rosters_pins_in_reachable_configs`,
  `Left contains one more item: ['cursor-grok-4.6', 'xhigh']`.

## BP-8. any rotating seat keeps the backfill tier in play for every vendor

- Axis: the same branch, the other way.
- Neutralization: `if any_seat_rotated:` became `if False:`.
- Red: `test_the_backfill_tier_is_in_play_for_a_roster_with_no_reviewer_tier_seat` and
  `test_the_backfill_tier_follows_the_rosters_pins_in_reachable_configs`,
  `E       AssertionError: assert ['gpt-6.1-sol', 'high'] in [['gpt-6.1-sol', 'xhigh']]`.

## BP-9. the relocated region markers still track CONVENTIONS §10.7

- Axis: `test_ssot_drift.py::test_pr_body_regions_markers_match_conventions_10_7` reads `pr_body_regions.REGION_MARKERS`.
- Neutralization (`pr_body_regions.py`): `"advisor-vet": "<!-- superheroes:advisor-vet -->",` became
  `"advisor-vet": "<!-- superheroes:advisor-vetX -->",`.
- Red: `FAILED plugins/superheroes/lib/tests/test_ssot_drift.py::test_pr_body_regions_markers_match_conventions_10_7`.

## BP-10. the renumbered degradation sort's costly rule is pinned by its new wording

- Axis: `test_ssot_drift.py::test_handback_sort_applies_the_costly_test_before_the_named_harmless_causes`.
- Neutralization (`skills/workhorse/reference/handback.md`): `1. A deviation is **costly** when a promised check`
  became `1. A deviation is **costlyX** when a promised check`.
- Red: `E       assert 'A deviation is **costly** when a promised check did not run, or work bypassed its owner engine' in ...`.
