# Bite-proof record: a forfeited slice seat re-run by an unread-part wave counts as recovered (#2334)

Detector: `plugins/superheroes/lib/tests/test_slice_recovery_2334.py`. Guarded code: `_check_slice_reads`, `_slice_recoveries` and the
last-wave branch of `_after_panel_wave` in `plugins/superheroes/lib/round_driver.py`; `_recovered_seats`, `_stamped_recoveries` and the
two row skips in `plugins/superheroes/lib/review_record_session.py`; `_recovery_fault` in `plugins/superheroes/lib/review_record.py`.

Guarded elements, declared up front by the order (E1 to E10), each with one neutralization applied as a targeted `Edit` and reverted by
its inverse `Edit`. Every run is the single test node named by `-k`, tests unedited, run as
`/home/user/wt-2334/scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/shpyc-wo1 -m pytest <test file> -q -p no:cacheprovider -k <name>`
with `git diff --stat` as its own plain call after it (the one-invocation form `cd ... ; git diff --stat` was refused by the shell checker
for its form, so each is a separate plain call; the stat after every restore is the same 8 tracked files, `round_driver.py | 83 +`,
`review_record.py | 38 +-`, `review_record_session.py | 26 +-`, as before each neutralization; the one exception is E10, whose
neutralization added one line, `review_record.py | 39`, and the restore returned it to 38). The new test file is untracked, so it is not in
`git diff --stat`. The `warning: The UV_NATIVE_TLS ...` line is the launcher's, not the test's. Where a capture is shortened below, the
shortening is said. Nothing in these captures is secret-like, so nothing is redacted.

The stat printed after every restore (identical for E1 to E9; E10's restore reads `review_record.py | 38 +++++++++-` as well):

```
 plugins/superheroes/TRANSITION.md                  | 15 ++++
 plugins/superheroes/lib/decision_kinds.py          |  1 +
 plugins/superheroes/lib/review_record.py           | 38 +++++++++-
 plugins/superheroes/lib/review_record_session.py   | 26 ++++++-
 plugins/superheroes/lib/round_driver.py            | 83 ++++++++++++++++++++++
 .../superheroes/lib/tests/test_unread_waves_c2.py  |  3 +-
 .../skills/review-code/reference/review-record.md  |  5 +-
 .../skills/review-code/reference/round-driver.md   |  2 +-
 8 files changed, 166 insertions(+), 7 deletions(-)
```

## E1: condition 4, no lens obligation left in the last wave's residual

- Guarded element: `_slice_recoveries`, the `lens_seats(lens, [e.get("seat") for e in residual ...])` leg of the first `if`. Axis: a lens
  whose last wave still leaves a part unread is never recovered.
- Order defect found while proving it: the order's red case, DoD 2 (b) (`test_a_wave_two_seat_that_read_nothing_twice_over...`), does not
  bite this element. In it every later lens seat read `[]`, so `recoveredBy` is empty and no recovery is made with or without the
  residual check. Raw, neutralized, test unedited (the first attempt, the one the order named):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 34 deselected in 1.03s
```

  So a test that does bite was added: `test_a_last_wave_seat_that_read_only_part_of_its_slice_leaves_a_residual_of_the_lens_and_the_seat_unrecovered`
  (wave 2 seat reads `[]`, the wave 3 seat reads `[[1, 10]]` of its 1000 lines, so it is not an empty reader and the residual holds the rest).
- Neutralization: replace `if w is None or w >= last or lens_seats(lens, [e.get("seat") for e in residual if isinstance(e, dict)]):` with
  `if w is None or w >= last:`.
- Detector: `test_a_last_wave_seat_that_read_only_part_of_its_slice_leaves_a_residual_of_the_lens_and_the_seat_unrecovered`.
- Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_last_wave_seat_that_read_only_part_of_its_slice_leaves_a_residual_of_the_lens_and_the_seat_unrecovered _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-6/test_a_last_wave_seat_that_rea0')

    def test_a_last_wave_seat_that_read_only_part_of_its_slice_leaves_a_residual_of_the_lens_and_the_seat_unrecovered(tmp_path):
        state = _state(_repo(tmp_path), _three_thousand())
        _run(state, forfeit=(S2,))
        _run(state, reads={"code-reviewer:w2u1": []})
        _run(state, reads={"code-reviewer:w3u1": [{"file": "pkg/f1.py", "lines": [[1, 10]]}]})
        assert state["_sliceReadsChecked"][2] == {"wave": 3, "malformed": [], "empty": []}
        assert [p["file"] for p in state["unreadShare"]["parts"]] == ["pkg/f1.py"]
>       _not_recovered(state)

/home/user/wt-2334/plugins/superheroes/lib/tests/test_slice_recovery_2334.py:157: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

state = {'schemaVersion': 5, 'sessionGeneration': 7, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...}
seat = 'code-reviewer:s2'

    def _not_recovered(state, seat=S2):
>       assert state["_incompletePanel"] is True
E       assert False is True

/home/user/wt-2334/plugins/superheroes/lib/tests/test_slice_recovery_2334.py:67: AssertionError
=========================== short test summary info ============================
FAILED lib/tests/test_slice_recovery_2334.py::test_a_last_wave_seat_that_read_only_part_of_its_slice_leaves_a_residual_of_the_lens_and_the_seat_unrecovered
1 failed, 35 deselected in 1.72s
```

- Restore: the inverse `Edit`, restoring the line quoted next. Restored line:
  `        if w is None or w >= last or lens_seats(lens, [e.get("seat") for e in residual if isinstance(e, dict)]):`
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 35 deselected in 0.97s
```

## E2: condition 2, a malformed read list of a later lens seat

- Guarded element: `_slice_recoveries`, the `lens_seats(lens, c["malformed"])` leg inside the `any(...)`. Axis: a lens seat that ran after
  the forfeit and returned a malformed read list spoils the recovery (fail closed).
- Neutralization: replace `not isinstance(c.get("malformed"), list) or lens_seats(lens, c["malformed"]) for c in seen[v]):` with
  `not isinstance(c.get("malformed"), list) for c in seen[v]):`.
- Detector: `test_a_wave_two_seat_whose_read_list_mixes_a_valid_range_and_an_invalid_one_is_a_malformed_list_and_no_recovery`.
- Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_wave_two_seat_whose_read_list_mixes_a_valid_range_and_an_invalid_one_is_a_malformed_list_and_no_recovery _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-8/test_a_wave_two_seat_whose_rea0')

    def test_a_wave_two_seat_whose_read_list_mixes_a_valid_range_and_an_invalid_one_is_a_malformed_list_and_no_recovery(tmp_path):
        state = _state(_repo(tmp_path), _three_thousand())
        _run(state, forfeit=(S2,))
        covering = copy.deepcopy(_slice(state, "w2u1")["parts"])
        covering[0]["lines"].append([9, 3])
        _run(state, reads={"code-reviewer:w2u1": covering})
        while state["step"] == RD.P_PANEL:
            _run(state)
        assert state["_sliceReadsChecked"][1] == {"wave": 2, "malformed": ["code-reviewer:w2u1"], "empty": []}
>       _not_recovered(state)

/home/user/wt-2334/plugins/superheroes/lib/tests/test_slice_recovery_2334.py:170: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

state = {'schemaVersion': 5, 'sessionGeneration': 7, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...}
seat = 'code-reviewer:s2'

    def _not_recovered(state, seat=S2):
>       assert state["_incompletePanel"] is True
E       assert False is True

/home/user/wt-2334/plugins/superheroes/lib/tests/test_slice_recovery_2334.py:67: AssertionError
=========================== short test summary info ============================
FAILED lib/tests/test_slice_recovery_2334.py::test_a_wave_two_seat_whose_read_list_mixes_a_valid_range_and_an_invalid_one_is_a_malformed_list_and_no_recovery
1 failed, 35 deselected in 0.50s
```

- Restore: the inverse `Edit`. Restored line:
  `                    not isinstance(c.get("malformed"), list) or lens_seats(lens, c["malformed"]) for c in seen[v]):`
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 35 deselected in 0.56s
```

## E3: condition 2, a later wave with no read evidence on record

- Guarded element: `_slice_recoveries`, the `not seen[v]` leg of the second `if`. Axis: a later wave whose read evidence is not on record
  (a session saved between waves by older code) is never trusted.
- Neutralization: replace `if not seen[v] or not isinstance(unread, list) or any(` with `if not isinstance(unread, list) or any(`.
- Detector: `test_a_session_saved_between_waves_by_code_that_kept_no_read_evidence_gives_no_recovery`.
- Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_session_saved_between_waves_by_code_that_kept_no_read_evidence_gives_no_recovery _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-10/test_a_session_saved_between_w0')

    def test_a_session_saved_between_waves_by_code_that_kept_no_read_evidence_gives_no_recovery(tmp_path):
        state = _state(_repo(tmp_path), _three_thousand())
        _run(state, forfeit=(S2,))
        _run(state, reads={"code-reviewer:w2u1": []})
        state["_sliceReadsChecked"] = [c for c in state["_sliceReadsChecked"] if c["wave"] != 2]
        _run(state)
        assert [c["wave"] for c in state["_sliceReadsChecked"]] == [1, 3]
>       _not_recovered(state)

/home/user/wt-2334/plugins/superheroes/lib/tests/test_slice_recovery_2334.py:229: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

state = {'schemaVersion': 5, 'sessionGeneration': 7, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...}
seat = 'code-reviewer:s2'

    def _not_recovered(state, seat=S2):
>       assert state["_incompletePanel"] is True
E       assert False is True

/home/user/wt-2334/plugins/superheroes/lib/tests/test_slice_recovery_2334.py:67: AssertionError
=========================== short test summary info ============================
FAILED lib/tests/test_slice_recovery_2334.py::test_a_session_saved_between_waves_by_code_that_kept_no_read_evidence_gives_no_recovery
1 failed, 35 deselected in 0.62s
```

- Restore: the inverse `Edit`. Restored line: `            if not seen[v] or not isinstance(unread, list) or any(`
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 35 deselected in 0.64s
```

## E4: condition 3, the lens's later obligations are inside what its slice seats were given

- Guarded element: `_slice_recoveries`, `slicing.unread_obligations({"o": owed}, {"o": given})`. Axis: a later wave whose lens seats were not
  handed every part the lens owed is never a recovery.
- Neutralization: replace `if slicing.unread_obligations({"o": owed}, {"o": given}):` with
  `if False and slicing.unread_obligations({"o": owed}, {"o": given}):`.
- Detector: `test_a_later_wave_whose_slices_were_not_given_the_forfeited_parts_gives_no_recovery`.
- Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_later_wave_whose_slices_were_not_given_the_forfeited_parts_gives_no_recovery _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-12/test_a_later_wave_whose_slices0')

    def test_a_later_wave_whose_slices_were_not_given_the_forfeited_parts_gives_no_recovery(tmp_path):
        state = _state(_repo(tmp_path), _three_thousand())
        _run(state, forfeit=(S2,))
        _slice(state, "w2u1")["parts"] = [{"file": "pkg/f0.py", "lines": [[1, 10]]}]
        _run(state)
        assert state["unreadShare"]["parts"] == []
>       _not_recovered(state)

/home/user/wt-2334/plugins/superheroes/lib/tests/test_slice_recovery_2334.py:251: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

state = {'schemaVersion': 5, 'sessionGeneration': 7, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...}
seat = 'code-reviewer:s2'

    def _not_recovered(state, seat=S2):
>       assert state["_incompletePanel"] is True
E       assert False is True

/home/user/wt-2334/plugins/superheroes/lib/tests/test_slice_recovery_2334.py:67: AssertionError
=========================== short test summary info ============================
FAILED lib/tests/test_slice_recovery_2334.py::test_a_later_wave_whose_slices_were_not_given_the_forfeited_parts_gives_no_recovery
1 failed, 35 deselected in 0.60s
```

- Restore: the inverse `Edit`. Restored line: `            if slicing.unread_obligations({"o": owed}, {"o": given}):`
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 35 deselected in 0.59s
```

## E5: condition 1, the forfeit is in an earlier wave than the last (`w < last`)

- Guarded element: `_slice_recoveries`, the `w >= last` leg of the first `if`. Axis: a forfeit in the last wave is never recovered.
- Neutralization: replace `if w is None or w >= last or lens_seats(` with `if w is None or lens_seats(`.
- Detector tried: `test_a_forfeit_in_the_last_wave_is_never_recovered`.
- Raw run with the neutralization applied, test unedited. **It did not go red:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 34 deselected in 0.64s
```

- **Unprovable as placed.** For a seat whose slice wave `w` equals the last wave, `range(w + 1, last + 1)` is empty, so `top` stays 0 and the
  guard `if top and by` refuses the entry whatever the `w >= last` leg says; the seat's own unread slice also sits in the residual, which the
  residual leg (E1) refuses. The leg is therefore subsumed by two other guards and no input reaches a state where only it decides.
  What would make it provable: drop the `top and by` guard and the residual leg, or compute `recoveredInWave` without the range. Its
  protection is unverified by itself (the invariant's outcome for a last-wave forfeit is held by E1's residual leg and the `top and by`
  guard, whose own removal this record does not neutralize). The order's expectation that this test goes red is not met, and that is a
  finding for the orchestrator.
- Restore: the inverse `Edit`. Restored line: `        if w is None or w >= last or lens_seats(lens, [e.get("seat") for e in residual if isinstance(e, dict)]):`
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 34 deselected in 0.61s
```

## E6: clear `_incompletePanel` only when every missing seat is a recovered slice seat

- Guarded element: `_after_panel_wave`, the `all(m in {r["seat"] for r in recoveries} for m in missingSeats)` gate. Axis: a whole-change
  seat that is missing keeps the panel incomplete.
- Neutralization: replace `if all(m in {r["seat"] for r in recoveries} for m in state["rounds"]["1"].get("missingSeats") or []):` with
  `if True or all(m in {r["seat"] for r in recoveries} for m in state["rounds"]["1"].get("missingSeats") or []):`.
- Detector: `test_a_whole_change_seat_that_is_missing_keeps_the_panel_incomplete_though_the_slice_seats_recovery_is_recorded`.
- Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_whole_change_seat_that_is_missing_keeps_the_panel_incomplete_though_the_slice_seats_recovery_is_recorded _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-16/test_a_whole_change_seat_that_0')

    def test_a_whole_change_seat_that_is_missing_keeps_the_panel_incomplete_though_the_slice_seats_recovery_is_recorded(tmp_path):
        state = _state(_repo(tmp_path), _three_thousand())
        _run(state, forfeit=(S2,), omit=("architecture-reviewer",))
        assert not RP.is_slice_seat("architecture-reviewer") and not RP.is_slice_seat("premortem-reviewer:w2")
        _run(state)
        assert state["rounds"]["1"]["seatStatus"]["architecture-reviewer"] == "missing"
        assert [r["seat"] for r in state["sliceRecoveries"]] == [S2]
>       assert state["_incompletePanel"] is True and state["fullPanelRan"] is False
E       assert (False is True)

/home/user/wt-2334/plugins/superheroes/lib/tests/test_slice_recovery_2334.py:219: AssertionError
=========================== short test summary info ============================
FAILED lib/tests/test_slice_recovery_2334.py::test_a_whole_change_seat_that_is_missing_keeps_the_panel_incomplete_though_the_slice_seats_recovery_is_recorded
1 failed, 35 deselected in 0.67s
```

- Restore: the inverse `Edit`. Restored line:
  `        if all(m in {r["seat"] for r in recoveries} for m in state["rounds"]["1"].get("missingSeats") or []):`
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 35 deselected in 0.48s
```

## E7: the `_incompletePanel = False` clear itself

- Guarded element: `_after_panel_wave`, `state["_incompletePanel"] = False`. Axis: a recovered panel is no longer incomplete.
- Neutralization: replace `            state["_incompletePanel"] = False` (the line before `state.pop("_sliceWave", None)`) with `            pass`.
- Detector: `test_a_forfeited_slice_seat_whose_slice_a_later_wave_read_is_recovered_and_the_panel_is_no_longer_incomplete` (DoD 1).
- Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_forfeited_slice_seat_whose_slice_a_later_wave_read_is_recovered_and_the_panel_is_no_longer_incomplete _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-18/test_a_forfeited_slice_seat_wh0')

    def test_a_forfeited_slice_seat_whose_slice_a_later_wave_read_is_recovered_and_the_panel_is_no_longer_incomplete(tmp_path):
        state, _, _ = _forfeited_then_reread(tmp_path)
        assert state["rounds"]["1"]["seatStatus"][S2] == "missing" and state["rounds"]["1"]["missingSeats"] == [S2]
>       assert state["_incompletePanel"] is False
E       assert True is False

/home/user/wt-2334/plugins/superheroes/lib/tests/test_slice_recovery_2334.py:76: AssertionError
=========================== short test summary info ============================
FAILED lib/tests/test_slice_recovery_2334.py::test_a_forfeited_slice_seat_whose_slice_a_later_wave_read_is_recovered_and_the_panel_is_no_longer_incomplete
1 failed, 35 deselected in 0.57s
```

- Restore: the inverse `Edit`. Restored line: `            state["_incompletePanel"] = False`
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 35 deselected in 0.58s
```

## E8: the journaled path's row skip (`_reviewers`)

- Guarded element: `review_record_session._reviewers`, the `_recovered_seats` skip. Axis: a recovered seat is no reviewer row that did not run.
- Neutralization: replace `        if phase == sc.PANEL_PHASE and key not in ran and seat in _recovered_seats(state, rnd):` with
  `        if False and phase == sc.PANEL_PHASE and key not in ran and seat in _recovered_seats(state, rnd):`.
- Detector: `test_the_account_carries_the_recovery_lists_no_missing_review_for_the_recovered_seat_and_the_record_shows_the_line[journaled]`
  (`-k "the_account_carries and journaled"`).
- Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_the_account_carries_the_recovery_lists_no_missing_review_for_the_recovered_seat_and_the_record_shows_the_line[journaled] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-20/test_the_account_carries_the_r0')
journaled = True

    @pytest.mark.parametrize("journaled", [True, False], ids=["journaled", "hand-submit"])
    def test_the_account_carries_the_recovery_lists_no_missing_review_for_the_recovered_seat_and_the_record_shows_the_line(tmp_path, journaled):
        path, state = _recovered_session(tmp_path, journaled)
        account = rs.account_from_session(path, extras(), Fake().readers())
        assert account["sliceRecoveries"] == [dict(state["sliceRecoveries"][0], commit=EARLIER)]
        names = {r["name"]: r for r in account["reviewers"]}
>       assert (S2 + " (round 1)") not in names
E       AssertionError: assert ('code-reviewer:s2' + ' (round 1)') not in {'architecture-reviewer (round 1)': {'name': 'architecture-reviewer (round 1)', 'planned': True, 'ran': True, 'vendor'...test-role:s1 (round 1)': {'name': 'test-role:s1 (round 1)', 'planned': True, 'ran': True, 'vendor': 'codex', ...}, ...}

/home/user/wt-2334/plugins/superheroes/lib/tests/test_slice_recovery_2334.py:306: AssertionError
=========================== short test summary info ============================
FAILED lib/tests/test_slice_recovery_2334.py::test_the_account_carries_the_recovery_lists_no_missing_review_for_the_recovered_seat_and_the_record_shows_the_line[journaled]
1 failed, 35 deselected in 0.52s
```

- Restore: the inverse `Edit`. Restored line:
  `        if phase == sc.PANEL_PHASE and key not in ran and seat in _recovered_seats(state, rnd):`
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 35 deselected in 0.62s
```

## E9: the hand-submit path's row skip (`_status_reviewers`)

- Guarded element: `review_record_session._status_reviewers`, the `_recovered_seats` skip. Axis: as E8, on the hand-submit path.
- Neutralization: replace `            if not ran and seat in _recovered_seats(state, rnd):` with
  `            if False and not ran and seat in _recovered_seats(state, rnd):`.
- Detector: `test_the_account_carries_the_recovery_lists_no_missing_review_for_the_recovered_seat_and_the_record_shows_the_line[hand-submit]`
  (`-k "the_account_carries and hand"`).
- Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_the_account_carries_the_recovery_lists_no_missing_review_for_the_recovered_seat_and_the_record_shows_the_line[hand-submit] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-22/test_the_account_carries_the_r0')
journaled = False

    @pytest.mark.parametrize("journaled", [True, False], ids=["journaled", "hand-submit"])
    def test_the_account_carries_the_recovery_lists_no_missing_review_for_the_recovered_seat_and_the_record_shows_the_line(tmp_path, journaled):
        path, state = _recovered_session(tmp_path, journaled)
        account = rs.account_from_session(path, extras(), Fake().readers())
        assert account["sliceRecoveries"] == [dict(state["sliceRecoveries"][0], commit=EARLIER)]
        names = {r["name"]: r for r in account["reviewers"]}
>       assert (S2 + " (round 1)") not in names
E       AssertionError: assert ('code-reviewer:s2' + ' (round 1)') not in {'architecture-reviewer (round 1)': {'name': 'architecture-reviewer (round 1)', 'planned': True, 'ran': True, 'vendor'...wer:s3 (round 1)': {'name': 'code-reviewer:s3 (round 1)', 'planned': True, 'ran': True, 'vendor': 'unknown', ...}, ...}

/home/user/wt-2334/plugins/superheroes/lib/tests/test_slice_recovery_2334.py:306: AssertionError
=========================== short test summary info ============================
FAILED lib/tests/test_slice_recovery_2334.py::test_the_account_carries_the_recovery_lists_no_missing_review_for_the_recovered_seat_and_the_record_shows_the_line[hand-submit]
1 failed, 35 deselected in 0.63s
```

- Restore: the inverse `Edit`. Restored lines:
  `            if not ran and seat in _recovered_seats(state, rnd):` then `                continue`
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 35 deselected in 0.68s
```

## E10: `_recovery_fault`

- Guarded element: `review_record._recovery_fault`. Axis: a malformed `sliceRecoveries` part (a wave not after the forfeit, no recoverer, a
  whole-change seat, a bad round, a blank recoverer, an extra key, an empty list, a non-list, a non-dict item) is refused by the account check.
- Neutralization: insert `    return None` as the first line of `_recovery_fault`'s body (before its `if not isinstance(x, dict) ...` line).
- Detector: `test_a_malformed_slice_recovery_part_is_refused_by_the_records_account_check` (10 parameters; `-k malformed_slice_recovery_part`).
- Raw red (incomplete: the tool shortened this capture in the middle, `[3209 characters truncated]`, and the output below is exactly what
  came back; 7 failed, 3 passed, the 3 passing being the empty-list, string and dict cases that `_validate`'s own list check refuses
  before the item check):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FFFFFF...F                                                               [100%]
=================================== FAILURES ===================================
_ test_a_malformed_slice_recovery_part_is_refused_by_the_records_account_check[not-later] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-24/test_a_malformed_slice_recover0')
bad = [{'seat': 'code-reviewer:s2', 'round': 1, 'wave': 2, 'recoveredInWave': 2, ...}]

    def test_a_malformed_slice_recovery_part_is_refused_by_the_records_account_check(tmp_path, bad):
        path, state = _recovered_session(tmp_path, journaled=False)
        session = Session(tmp_path / "bad", rounds=state["rounds"], sliceRecoveries=bad).save()
        account = rs.account_from_session(session, extras(), Fake().readers())
>       with pytest.raises(rr.Refusal) as err:
             ^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE Refusal

/home/user/wt-2334/plugins/superheroes/lib/tests/test_slice_recovery_2334.py:341: Failed

... [3209 characters truncated] ...

=========================== short test summary info ============================
FAILED lib/tests/test_slice_recovery_2334.py::test_a_malformed_slice_recovery_part_is_refused_by_the_records_account_check[not-later]
FAILED lib/tests/test_slice_recovery_2334.py::test_a_malformed_slice_recovery_part_is_refused_by_the_records_account_check[nobody]
FAILED lib/tests/test_slice_recovery_2334.py::test_a_malformed_slice_recovery_part_is_refused_by_the_records_account_check[whole-change]
FAILED lib/tests/test_slice_recovery_2334.py::test_a_malformed_slice_recovery_part_is_refused_by_the_records_account_check[round-zero]
FAILED lib/tests/test_slice_recovery_2334.py::test_a_malformed_slice_recovery_part_is_refused_by_the_records_account_check[blank-reader]
FAILED lib/tests/test_slice_recovery_2334.py::test_a_malformed_slice_recovery_part_is_refused_by_the_records_account_check[extra-key]
FAILED lib/tests/test_slice_recovery_2334.py::test_a_malformed_slice_recovery_part_is_refused_by_the_records_account_check[none-item]
7 failed, 3 passed, 26 deselected in 1.71s
```

  (The first failure body is shortened here from the live output to the lines that carry the failure; the live capture also reprinted the
  full parametrize decorator for each failure. The `[3209 characters truncated]` marker is the tool's, not an edit of mine.)
- Restore: the inverse `Edit`, removing the inserted `    return None`. Restored lines:
  `    if not isinstance(x, dict) or set(x) != {"seat", "round", "wave", "recoveredInWave", "recoveredBy", "commit"}:` then `        return ""`
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..........                                                               [100%]
10 passed, 26 deselected in 1.50s
```

## Unproven and not-bitten

- E5 is **Unprovable as placed** (above): the detector stays green with the element neutralized.
- E1's order-named red case (DoD 2 (b)) does not bite; the case added for it (the partial last-wave read) does.
- The driven end-to-end test (`test_a_real_driven_session_whose_wave_one_slice_seat_forfeits_and_is_re_read_converges`) is a positive-path
  check that the fold-level recovery reaches the driver's `converged` terminal; no element above is proven by it alone.
