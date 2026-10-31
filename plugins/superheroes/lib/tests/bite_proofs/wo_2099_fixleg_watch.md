# WO-E (#2099 fix leg, vet 622 finding 1) bite-proof — a post-park progress edit is not a resume

> Note (2026-10-31, #2296): owner-machine paths and the name of a consuming project in this record were replaced with neutral placeholders after capture; nothing else changed.

**Provenance:** work order WO-E, worktree `/home/user/wt-2099-e` (branch `wo-2099-e`, on top of `ddb34ef4`), claude implementer (sonnet), edits left uncommitted.

**Method.** Each guarded element is neutralized on its own by a targeted `Edit` to the consumer in `plugins/superheroes/lib/wave_watch.py` (never the detector). The detector is run alone by exact node id (`-q`, no `-k`), the neutralization is undone by the inverse `Edit`, the same node ids are re-run green, and the restored lines are quoted back. One neutralization was live at a time. Redaction: pytest temp paths and timestamps are kept as printed; nothing needed redacting. Every capture is far under the 32 KiB per-element ceiling and the whole record is far under 128 KiB. Where a capture is shortened, the record says what was elided.

Command for every run (`<nodes>` is the exact node id list given per element; the tool prints the `UV_NATIVE_TLS` warning first, dropped from the quoted captures below):

```
scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/pyc-wo-e -m pytest <nodes> -q -p no:cacheprovider
```

Guarded-element set (declared by the order): E1 the grace window, E2 the phase veto, E3 the `resum` exception, E4 strict `>`.

`T` = `plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py`. Line numbers are in the restored `wave_watch.py`: the comparison is `:1531-1532` in `_cloud_terminals`, the helper `_phase_reads_resumed` is `:1473-1480`.

**Order defect found while proving E1.** The order expects the field-shape tests (the three recorded rows and the arm test) to go red when the window is dropped. They do not: each recorded row carries a parked or stopped phase, so the phase veto keeps the park on its own and the window is not the only thing holding it. Measured: with E1 live, the four field-shape nodes ran `4 passed` (quoted under E1). The window is therefore proven by a test whose phase reads resumed and whose edit is inside the window (`T::test_p11_…[5-False]`, `[299-False]`, `[300-False]`), not by the field-shape tests. The field-shape tests guard the veto and the window jointly; neither element alone turns them red.

## E1 — the grace window (`wave_watch.py:1531`; axis: a progress edit inside `PARK_SUPERSESSION_GRACE_SECONDS` of the park is not a resume)

- **Detector:** `T::test_p11_a_resumed_progress_edit_supersedes_only_when_strictly_more_than_300_seconds_after[5-False]`, `…[299-False]`, `…[300-False]`.
- **Neutralization:** `and progress_at - parked_at > PARK_SUPERSESSION_GRACE_SECONDS` replaced by `and progress_at > parked_at` (any later edit with a resumed phase supersedes).
- **Raw red** (the three failures have the same shape; the full first failure and the summary are quoted, the second and third failure bodies are elided, about 40 lines, identical but for the parameter):

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_p11_a_resumed_progress_edit_supersedes_only_when_strictly_more_than_300_seconds_after[5-False] _

gap = 5, superseded = False

    @pytest.mark.parametrize("gap, superseded", [(5, False), (299, False), (300, False), (301, True)])
    def test_p11_a_resumed_progress_edit_supersedes_only_when_strictly_more_than_300_seconds_after(gap, superseded):
        # axis: STRICT window — exactly PARK_SUPERSESSION_GRACE_SECONDS keeps the park, one second more supersedes it
        assert ww.PARK_SUPERSESSION_GRACE_SECONDS == 300
        park, progress = _park_then_progress(gap, phase="building WO-2")
        if superseded:
            assert _terminals([park, progress], lane_age=_WIDE) == []
        else:
>           _only_park([park, progress])

/home/user/wt-2099-e/plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py:528: 
...
    def _only_park(comments):
>       [only] = _terminals(comments, lane_age=_WIDE)
        ^^^^^^
E       ValueError: not enough values to unpack (expected 1, got 0)

/home/user/wt-2099-e/plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py:471: ValueError
... (the [299-False] and [300-False] failures: the same assertion and the same ValueError)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py::test_p11_a_resumed_progress_edit_supersedes_only_when_strictly_more_than_300_seconds_after[5-False]
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py::test_p11_a_resumed_progress_edit_supersedes_only_when_strictly_more_than_300_seconds_after[299-False]
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py::test_p11_a_resumed_progress_edit_supersedes_only_when_strictly_more_than_300_seconds_after[300-False]
3 failed in 0.41s
```

- **Field-shape tests with E1 live** (the order-defect measurement; the same neutralization was still in the tree): `T::test_p9_the_recorded_park_then_a_seconds_later_parked_progress_edit_stays_terminal[second-owner-gate]`, `[superheroes-2071]`, `[superheroes-1948]` and `T::test_p9_a_recorded_park_shape_is_lane_terminal_through_the_arm`:

```
....                                                                     [100%]
4 passed in 0.44s
```

- **Restore:** the inverse `Edit`, `and progress_at > parked_at` back to `and progress_at - parked_at > PARK_SUPERSESSION_GRACE_SECONDS`.
- **Restore receipt:** `wave_watch.py:1531: and progress_at - parked_at > PARK_SUPERSESSION_GRACE_SECONDS`; the final `git diff` of the file is quoted in the closing check below.
- **Raw green:**

```
...                                                                      [100%]
3 passed in 0.40s
```

## E2 — the phase veto (`wave_watch.py:1473-1480`, `_phase_reads_resumed`; axis: a parked or stopped phase, or no phase, is not a resume, however late the edit)

- **Detector:** `T::test_p12_a_parked_or_stopped_phase_past_the_window_keeps_the_park` with ids `[parked-on-a-gate]`, `[still-parked]`, `[still-stopped-capitalised]`, `[stopped]`, `[PARKED]`, `[parking-lot]`, and `T::test_p12_a_progress_edit_past_the_window_with_no_phase_or_an_empty_phase_keeps_the_park`.
- **Neutralization:** the helper's body (the non-string/empty guard, the `re.findall` word split and the two-part `return`) replaced by `return True` (every phase reads resumed).
- **Raw red — INCOMPLETE:** the harness cut the middle of the tool output (its own marker line `... [2127 characters truncated] ...`, not mine); what follows is the output I have, shortened by me in this record: the `@pytest.mark.parametrize` decorator lines and the `_ _ _` frame-separator lines are dropped (a `...` marks each), and only the first failure and the last are quoted, the failures between them being the harness-lost and the same-shaped ones. First and last lines are the capture's. The result line is `7 failed in 0.55s`; all seven nodes are named in the short summary.

```
FFFFFFF                                                                  [100%]
=================================== FAILURES ===================================
_ test_p12_a_parked_or_stopped_phase_past_the_window_keeps_the_park[parked-on-a-gate] _

phase = 'parked on a second owner gate'

    def test_p12_a_parked_or_stopped_phase_past_the_window_keeps_the_park(phase):
        # axis: phase veto — an edit long after the park whose phase reads parked or stopped (any case, any word) is not a resume
        park, progress = _park_then_progress(3600, phase=phase)
>       _only_park([park, progress])

/home/user/wt-2099-e/plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py:542: 
...
    def _only_park(comments):
>       [only] = _terminals(comments, lane_age=_WIDE)
        ^^^^^^
E       ValueError: not enough values to unpack (expected 1, got 0)

/home/user/wt-2099-e/plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py:471: ValueError
... [2127 characters truncated] ... (harness marker; the middle of the output was lost, not reconstructed)
_ test_p12_a_progress_edit_past_the_window_with_no_phase_or_an_empty_phase_keeps_the_park _

    def test_p12_a_progress_edit_past_the_window_with_no_phase_or_an_empty_phase_keeps_the_park():
        # axis: phase veto — a missing or empty Phase line never supersedes
        no_phase_body = "\n".join([cb.PROGRESS_HEADER, "", "Now running: the suite", "Expected: 60 minutes"])
        park, missing = _park_then_progress(3600, body=no_phase_body)
        assert ww._cloud_progress([missing], _lanes({"cloud-a": (101, _WIDE)}))["cloud-a"]["phase"] is None
>       _only_park([park, missing])
...
E       ValueError: not enough values to unpack (expected 1, got 0)
=========================== short test summary info ============================
FAILED …::test_p12_a_parked_or_stopped_phase_past_the_window_keeps_the_park[parked-on-a-gate]
FAILED …::test_p12_a_parked_or_stopped_phase_past_the_window_keeps_the_park[still-parked]
FAILED …::test_p12_a_parked_or_stopped_phase_past_the_window_keeps_the_park[still-stopped-capitalised]
FAILED …::test_p12_a_parked_or_stopped_phase_past_the_window_keeps_the_park[stopped]
FAILED …::test_p12_a_parked_or_stopped_phase_past_the_window_keeps_the_park[PARKED]
FAILED …::test_p12_a_parked_or_stopped_phase_past_the_window_keeps_the_park[parking-lot]
FAILED …::test_p12_a_progress_edit_past_the_window_with_no_phase_or_an_empty_phase_keeps_the_park
7 failed in 0.55s
```

(In the summary lines `…` stands for `plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py`, shortened in this record only; the tool printed the full path.)

- **Restore:** the inverse `Edit`, `return True` back to the guard, the word split and the two-part `return`.
- **Restore receipt:** `wave_watch.py:1475-1480` quoted back below under "Restored lines".
- **Raw green:**

```
.......                                                                  [100%]
7 passed in 0.47s
```

## E3 — the `resum` exception (`wave_watch.py:1478-1480`; axis: a phase that names the park but says it resumed still reads resumed)

- **Detector:** `T::test_p10_the_real_resume_two_hours_forty_three_minutes_later_supersedes_the_park` (the field resume shape: +9780 s, phase `resumed after the park; building`).
- **Neutralization:** the clause `or any(word.startswith("resum") for word in words)` (three lines) replaced by `or False`.
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_p10_the_real_resume_two_hours_forty_three_minutes_later_supersedes_the_park _

    def test_p10_the_real_resume_two_hours_forty_three_minutes_later_supersedes_the_park():
        # axis: resum exception — the field resume shape: a phase that names the park but says it resumed supersedes it
        park, progress = _park_then_progress(9780, phase="resumed after the park; building")
>       assert _terminals([park, progress], lane_age=_WIDE) == []
E       AssertionError: assert [{'launchId':...e': 101, ...}] == []
E         
E         Left contains one more item: {'launchId': 'cloud-a', 'state': 'parked', 'kind': 'park', 'issue': 101, ...}
E         Use -v to get more diff

/home/user/wt-2099-e/plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py:517: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py::test_p10_the_real_resume_two_hours_forty_three_minutes_later_supersedes_the_park
1 failed in 0.47s
```

- **Restore:** the inverse `Edit`, `or False` back to the three-line `or any(word.startswith("resum") for word in words)` clause.
- **Restore receipt:** `wave_watch.py:1478-1480` quoted back below.
- **Raw green:**

```
.                                                                        [100%]
1 passed in 0.76s
```

## E4 — strict `>` (`wave_watch.py:1531`; axis: an edit exactly `PARK_SUPERSESSION_GRACE_SECONDS` after the park keeps the park)

- **Detector:** `T::test_p11_a_resumed_progress_edit_supersedes_only_when_strictly_more_than_300_seconds_after[300-False]`.
- **Neutralization:** `progress_at - parked_at > PARK_SUPERSESSION_GRACE_SECONDS` became `progress_at - parked_at >= PARK_SUPERSESSION_GRACE_SECONDS`.
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_p11_a_resumed_progress_edit_supersedes_only_when_strictly_more_than_300_seconds_after[300-False] _

gap = 300, superseded = False

    @pytest.mark.parametrize("gap, superseded", [(5, False), (299, False), (300, False), (301, True)])
    def test_p11_a_resumed_progress_edit_supersedes_only_when_strictly_more_than_300_seconds_after(gap, superseded):
        # axis: STRICT window — exactly PARK_SUPERSESSION_GRACE_SECONDS keeps the park, one second more supersedes it
        assert ww.PARK_SUPERSESSION_GRACE_SECONDS == 300
        park, progress = _park_then_progress(gap, phase="building WO-2")
        if superseded:
            assert _terminals([park, progress], lane_age=_WIDE) == []
        else:
>           _only_park([park, progress])

/home/user/wt-2099-e/plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py:528: 
...
    def _only_park(comments):
>       [only] = _terminals(comments, lane_age=_WIDE)
        ^^^^^^
E       ValueError: not enough values to unpack (expected 1, got 0)

/home/user/wt-2099-e/plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py:471: ValueError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py::test_p11_a_resumed_progress_edit_supersedes_only_when_strictly_more_than_300_seconds_after[300-False]
1 failed in 0.49s
```

- **Restore:** the inverse `Edit`, `>=` back to `>`.
- **Restore receipt:** `wave_watch.py:1531` quoted back below.
- **Raw green:**

```
.                                                                        [100%]
1 passed in 0.41s
```

## Restored lines and the closing check

The restored lines in `wave_watch.py` (quoted from the final file):

```
1473: def _phase_reads_resumed(phase):
1475:     if not isinstance(phase, str) or not phase:
1476:         return False
1477:     words = re.findall(r"[a-z]+", phase.lower())
1478:     return not any(word.startswith(("park", "stop")) for word in words) or any(
1479:         word.startswith("resum") for word in words
1480:     )
1531:                     and progress_at - parked_at > PARK_SUPERSESSION_GRACE_SECONDS
1532:                     and _phase_reads_resumed(progress[lid]["phase"])):
```

**Check that `wave_watch.py` equals the intended change.** After the last restore I ran `git diff plugins/superheroes/lib/wave_watch.py`. Its header line was `index aeb741a7..c2175594`, the same blob id that the diff printed before the first neutralization (`index aeb741a7..c2175594`), and its hunks were the same five (module docstring paragraph, the constant, `_phase_reads_resumed`, the `_cloud_terminals` docstring, the `# bite-axis: SUPERSEDED` comment and the two-condition `if`). The blob id matching before and after all four neutralizations is the byte-clean receipt.

**Disclosed limits of this proof.**

- The E1 order expectation (field-shape tests red) did not hold; see "Order defect" above. The window is guarded by the `[5-False]`, `[299-False]` and `[300-False]` parameters of the p11 test, not by the recorded-shape tests.
- E2's red capture is incomplete (harness truncation, marked in place).
- E2 was neutralized as "always True"; the separate branches inside the helper (non-string, empty string, `park` vs `stop` prefix) are not individually neutralized. They are covered by the direct helper test `T::test_p12_the_phase_helper_reads_resumed_only_for_a_nonempty_string` (twelve parameters), which was run green in the scoped suite but not neutralized branch by branch.
