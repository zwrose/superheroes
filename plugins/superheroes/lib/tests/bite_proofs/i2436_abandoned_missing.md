# Bite-proof record: an abandoned session lists every planned seat that produced no result (#2436)

Detector: `plugins/superheroes/lib/tests/test_review_record_abandoned_missing_2436.py` (26 tests) and the account
check in `review_record._validate`. Every neutralization was one targeted `Edit` on the build tree and was undone by
the inverse `Edit`; no `git checkout`, `restore`, `reset` or `stash` was used. Command for every red and green:
`scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/pyc-2436 -m pytest
plugins/superheroes/lib/tests/test_review_record_abandoned_missing_2436.py -q -p no:cacheprovider` (the batch B, C
and D reds added `--tb=line` or `--tb=short` to shorten the failure text; nothing is filtered). The `warning:
The UV_NATIVE_TLS ...` line is the launcher's. Nothing below is redacted: the captures hold no secret, token or
private URL.

Baseline before any neutralization: `26 passed`. Restore receipt for every batch, the same
`git diff --stat -- review_record.py review_record_session.py round_records.py` before and after:

```
 plugins/superheroes/lib/review_record.py         |  24 ++++-
 plugins/superheroes/lib/review_record_session.py | 111 ++++++++++++++++++++++-
 plugins/superheroes/lib/round_records.py         |   3 +
 3 files changed, 131 insertions(+), 7 deletions(-)
```

The restored lines, quoted from the file after the last restore (`review_record_session.py` line numbers):
`537` `and sc.run_kind_for_phase(phase) == sc.RUN_KIND_REVIEW and phase not in _UNLISTED_PHASES):`; `547`
`row["noResult"] = UNFILLED`; `550` and `563` and `591` `out.append(row)`; `553` `if state.get("_submitUsed"):`; `569`
`if (phase, rnd, seat, occ) in slots:`; `581` `unreadable = refusal.get("reason") != "landing-missing"`; `585`/`588`
`continue` after the result check and after the unfilled branch; `629` `if abandoned and key not in ran:`; `636`
`... **({"noResult": UNFILLED} if abandoned else {}))`. `review_record.py`: `864` `chk("noResult" not in r or (ab is not None
and r.get("planned") is True and r.get("ran") is False`; `1673` `said = ABANDONED_MISSING_LINE.format(name=m["name"],
reason=m["reason"]) if isinstance(m.get("reason"), str) \`; `1926` `missing.append({"name": v["name"], "goAhead": good,
**({"reason": src["noResult"]} if "noResult" in src else {})})`.

Green runs: `26 passed in 0.86s` (after batch A's restore) and `26 passed in 1.00s` (after the last restore, batch D).
Batches B, C and D were each restored in the step that set up the next, so their green is that final run (stated per element).

Batches (each element's red is read off its own node; the failing node sets of one batch are disjoint):
batch A = G2, G3, G4 (two clauses), G5, G6, G7, G8, G11, G12; batch B = G9; batch C = G10; batch D = G1.
Batch A's full red output (the pytest report, 19 failed, 7 passed) was written to scratch outside the repository,
`/tmp/claude-0/-home-user-wt-2436/2b2f172d-f3f9-4183-b4ed-4784f01b7773/scratchpad/redA.txt`; the decisive lines are
quoted per element below, and the scratch file is a working artifact, not the receipt.

## G1. `_pending_without_result` adds a not-run row for a pending seat with no slot

- Axis: a planned seat of the pending review phase with no journaled slot becomes a reviewer row with `ran: false`.
- Neutralization (`review_record_session.py`, both appends): `out.append(row)` became `pass` after
  `row["noResult"] = review_record.LANDING_UNREADABLE if unreadable else _no_result_reason(None, env)`, and after
  `names.add(row["name"])` in the hand-submit branch.
- Red (batch D, 10 failed, 16 passed), among them
  `test_a_pending_seat_with_nothing_landed_is_listed_as_no_result`:
  `E   AssertionError: assert [] == [('test-role ... 'no-result')]` / `Right contains one more item: ('test-role (round 1)', 'no-result')`;
  `test_a_repeated_audit_key_is_two_slots_and_only_the_unrecorded_one_is_listed[0]` and `[1]`:
  `assert [] == [('audits T1 ... 'no-result')]`; `test_a_returning_session_with_no_recorded_seat_lists_its_pending_scoped_finder`:
  `Right contains one more item: ('scoped-finder scoped-finder (round 1)', False, 'no-result')`;
  `test_a_hand_submit_session_lists_only_its_pending_panels_unreported_seats`:
  `Right contains one more item: ('test-role (round 1)', False, 'no-result')`.
- Restore: both `pass` lines edited back to `out.append(row)`. Restore receipt: the diff stat above, and the quoted lines.
- Green: `26 passed in 1.00s`.

## G2. a seat whose stored or landed envelope is a real result is never listed

- Axis: the produced-a-result exclusion runs before every branch, for a landing envelope, a landing bare payload and a stored envelope alike.
- Neutralization: the `continue` under `if isinstance(env, dict) and env.get("schema") != sc.SEAT_MISSING_SCHEMA and not dispatch_outcome.payload_did_not_run(...)` became `pass`.
- Red (batch A): all three cases of `test_a_pending_seat_whose_result_landed_or_was_stored_is_never_listed`
  (`[landed-envelope]`, `[landed-bare-payload]`, `[stored-envelope]`):
  `E       AssertionError: assert ['code-review...le (round 1)'] == ['code-reviewer (round 1)']` / `Left contains one more item: 'test-role (round 1)'`.
- Restore: `pass` edited back to `continue`. Receipt: as above.
- Green: `26 passed in 0.86s`.

## G3. a landing that is present but cannot be read is listed `landing-unreadable`

- Axis: a landing refusal other than `landing-missing` is neither a result nor nothing.
- Neutralization: `unreadable = refusal.get("reason") != "landing-missing"` became `unreadable = False`.
- Red (batch A): `test_a_landing_that_cannot_be_read_is_listed_landing_unreadable[torn]` and `[not-an-object]`:
  `E       At index 0 diff: ('test-role (round 1)', 'no-result') != ('test-role (round 1)', 'landing-unreadable')`.
- Restore: edited back. Receipt: as above.
- Green: `26 passed in 0.86s`.

## G4. the pending-phase eligibility filter (review run kind; not `_UNLISTED_PHASES`)

- Axis: only a pending review phase is read, and synthesis is never listed.
- Neutralization: `and sc.run_kind_for_phase(phase) == sc.RUN_KIND_REVIEW and phase not in _UNLISTED_PHASES):` became `):`
  (both clauses off; each clause's red is on its own case).
- Red (batch A): `test_a_pending_synthesis_or_apply_fixes_phase_lists_nothing[synthesis]`:
  `Left contains one more item: {'goAhead': None, 'name': 'synthesis synthesis (round 1)', 'reason': 'no-result'}` (the unlisted-phases clause);
  `[apply-fixes]`: `Left contains one more item: {'goAhead': None, 'name': 'apply-fixes apply-fixes (round 1)', 'reason': 'no-result'}` (the run-kind clause).
- Restore: the clause line edited back. Receipt: as above.
- Green: `26 passed in 0.86s`.

## G5. the hand-submit gate on `_submitUsed`

- Axis: a hand-submit session lists only its pending panel's seats that no seat status named.
- Neutralization: `if state.get("_submitUsed"):` became `if False:`.
- Red (batch A): `test_a_hand_submit_session_lists_only_its_pending_panels_unreported_seats`:
  `E       At index 1 diff: ('code-reviewer (round 1)', False, 'no-result') != ('test-role (round 1)', False, 'no-result')` / `Left contains one more item: ('test-role (round 1)', False, 'no-result')`
  (the journaled path listed the seat the seat status had run).
- Restore: edited back. Receipt: as above.
- Green: `26 passed in 0.86s`.

## G6. slot-identity reconciliation (occurrence)

- Axis: two audit targets sharing an id are two slots; the recorded one never hides its sibling.
- Neutralization: `if (phase, rnd, seat, occ) in slots:` became `if (phase, rnd, seat, 0) in slots:`.
- Red (batch A): `test_a_repeated_audit_key_is_two_slots_and_only_the_unrecorded_one_is_listed[0]`:
  `E       AssertionError: assert [] == [('audits T1 ... 'no-result')]`; `[1]`:
  `E       Left contains one more item: ('audits T1 (round 1)', 'recorded-missing')` (two entries where one was owed).
- Restore: `0` edited back to `occ`. Receipt: as above.
- Green: `26 passed in 0.86s`.

## G7. `_reviewers` stamps `noResult` on a recorded not-run row

- Axis: a recorded forfeit or a record-missing seat of an abandoned session carries the reason its stored envelope gives.
- Neutralization: `if abandoned and key not in ran:` became `if False:`.
- Red (batch A): `test_a_recorded_forfeit_and_a_recorded_missing_seat_are_listed_once_each_with_their_reasons`:
  `E       At index 0 diff: ('test-role (round 1)', None) != ('test-role (round 1)', 'forfeited')`.
- Restore: edited back. Receipt: as above.
- Green: `26 passed in 0.86s`.

## G8. the account check on `noResult`

- Axis: `noResult` rides only a planned, not-run row of an abandoned account, from the fixed vocabulary.
- Neutralization (`review_record.py`): the whole three-line `chk("noResult" not in r or (...), f"reviewers[{i}].noResult")` became `chk(True, f"reviewers[{i}].noResult")`.
- Red (batch A): all six cases of `test_the_account_refuses_a_no_result_reason_anywhere_but_a_not_run_row_of_an_abandoned_account`
  (`[ended-account]`, `[ran-row]`, `[unplanned-row]`, `[token-outside-vocabulary]`, `[null]`, `[list]`):
  `E       AssertionError: assert {'ok': True, ...arts': 0, ...} == {'ok': False,...[0].noResult'}`.
- Restore: the three lines restored. Receipt: as above, and line 864 quoted.
- Green: `26 passed in 0.86s`.

## G9. `build_record` copies the account row's `noResult` into the missing entry as `reason`

- Axis: the entry carries `reason` exactly when the account row carries `noResult`.
- Neutralization (`review_record.py`): `missing.append({"name": v["name"], "goAhead": good, **({"reason": src["noResult"]} if "noResult" in src else {})})` became `missing.append({"name": v["name"], "goAhead": good})`.
- Red (batch B, `--tb=line`, 12 failed, 14 passed), among them:
  `E   KeyError: 'reason'` at `test_review_record_abandoned_missing_2436.py:98` (`test_a_pending_seat_whose_forfeit_landed_...`);
  `E   AssertionError: assert [('test-role ...nd 1)', None)] == [('test-role ... 'forfeited')]` at `:147`;
  `E   AssertionError: assert [('audits T1 ...nd 1)', None)] == [('audits T1 ... 'no-result')]` at `:266`.
- Restore: the `**({"reason": ...})` term restored. Receipt: as above, and line 1926 quoted.
- Green: no isolated run; G9 was restored in the same step that neutralized G10, so the batch C run (24 passed, 2 failed, the two
  failures G10's alone) shows every G9 node passing, and the final all-restored run is `26 passed in 1.00s`.

## G10. the `ABANDONED_MISSING_LINE` wording branch

- Axis: a missing entry with a `reason` reads in the abandoned wording; one without reads as before.
- Neutralization (`review_record.py`): `said = ABANDONED_MISSING_LINE.format(...) if isinstance(m.get("reason"), str) else f"{m['name']} did not run"` became `said = f"{m['name']} did not run"`.
- Red (batch C, `--tb=short`, 2 failed, 24 passed):
  `test_a_pending_seat_whose_forfeit_landed_is_a_missing_review_with_the_forfeit_reason`:
  `E   assert 'test-role (round 1) did not run (forfeited; the review session was abandoned before this seat produced a result)' in ['no maker is named, so independence cannot be shown', 'test-role (round 1) did not run', ...]`;
  `test_an_owners_go_ahead_attaches_to_the_listed_seat_and_lifts_the_parking`: `E   assert False` over `any(line.startswith(rr.ABANDONED_MISSING_LINE.format(...) + "; go-ahead: ") ...)`.
- Restore: the two-line expression restored. Receipt: as above, and line 1673 quoted.
- Green: no isolated run; G10 was restored in the same step that neutralized G1, so the final all-restored run is the green: `26 passed in 1.00s`.

## G11 (added by the implementer; not in the order's set). `_reviewers` stamps `unfilled` on an unfilled seat's row

- Axis: an abandoned journaled session's seat the map left unfilled carries `noResult: unfilled`, and the pending phase adds no second row for it.
- Neutralization: `**({"noResult": UNFILLED} if abandoned else {})` became `**{}`.
- Red (batch A): `test_a_seat_the_map_left_unfilled_is_listed_once_with_the_unfilled_reason`:
  `E       AssertionError: assert [] == [('test-role ..., 'unfilled')]` / `Right contains one more item: ('test-role (round 1)', False, 'unfilled')`.
- Restore: edited back. Receipt: as above, line 636 quoted.
- Green: `26 passed in 0.86s`.

## G12 (added by the implementer; not in the order's set). the pending function's unfilled row

- Axis: a hand-submit session's pending panel seat whose lens the governing map leaves unfilled reads `unfilled`, not `no-result`.
- Neutralization: the line `row["noResult"] = UNFILLED` in `unfilled_row` was deleted.
- Red (batch A): `test_a_pending_panel_round_with_an_unfilled_seat_lists_it_unfilled_in_a_hand_submit_session`:
  `E         {'test-role (round 2)': None} != {'test-role (round 2)': 'unfilled'}`.
- Restore: the line put back. Receipt: as above, line 547 quoted.
- Green: `26 passed in 0.86s`.
