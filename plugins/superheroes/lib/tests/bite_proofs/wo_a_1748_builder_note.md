# C7-WO-A (#1748) bite-proof — the builder-note event in the wave watch

**Provenance:** produced by the C7-WO-A implementer (claude, sonnet-5.5), in its own worktree
(`build/1748-wo-a`), against the uncommitted work tree. Verification authority stays with the
orchestrator, which re-runs every proof itself.

**Method.** Each guarded element is neutralized on its own — the *thing the detector guards* in
`plugins/superheroes/lib/wave_watch.py`, never the detector — by a targeted edit, then restored by
the exact inverse edit (no `git checkout`, `git restore`, `git reset` or `git stash`). Each command
selects its test by exact node name, never `-k`. The detector (the test) was unedited between red
and green, with one disclosed exception under element 5. All captures are far below the 32 KiB
ceiling; no secrets or private URLs appear in them (the temp paths are pytest's own).

## Guarded elements

| ID | Guarded element (axis) | Neutralization | Proving test |
|---|---|---|---|
| BP-1 | header match, `_builder_note` (`# bite-axis: HEADER`) — only a body opening with `cloud_builder.NOTE_HEADER` is a note | accept any body | `test_a_comment_that_is_not_a_note_raises_no_event` |
| BP-2 | watched-issue filter, `_builder_note` (`# bite-axis: WATCHED ISSUE`) — a comment on an issue no watched lane has is no note | skip the issue check | `test_a_note_on_an_issue_no_watched_lane_has_raises_no_event` |
| BP-3 | started-time filter, `_builder_note` (`# bite-axis: STARTED`) — a note created before the lane's `startedTs` is not that lane's | skip it | `test_a_note_created_before_the_lane_started_raises_no_event` |
| BP-4 | answered filter, `_builder_note` (`# bite-axis: ANSWERED`) — a note recorded answered stops surfacing | ignore the answered set | `test_a_note_recorded_answered_raises_no_event` |
| BP-5 | sending the stored validator, `_read_issue_comments` (`# bite-axis: VALIDATOR`) — the repeat read within one loop carries `If-None-Match` | never send `If-None-Match` | `test_the_repeat_read_within_one_loop_sends_the_stored_validator` |

Each proving test's fixture creates the condition its assertion discriminates on (trap 4): the
fake `gh` serves the comment regardless of `since`, so the earlier-lane and unwatched-issue notes
do reach `_builder_note`, and the fake answers a request carrying the current ETag with a 304 and
anything else with a 200, so a missing validator shows as a missing `-H`.

## BP-1 — header match

- **Neutralization** (`wave_watch.py:1300`): `if not body.lstrip().startswith(cb.NOTE_HEADER):` → `if False:`
- **Red** (`pytest -q plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_a_comment_that_is_not_a_note_raises_no_event`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_a_comment_that_is_not_a_note_raises_no_event _______________

repo = '/private/tmp/claude-501/pytest-of-zwrose/pytest-1427/test_a_comment_that_is_not_a_n0/repo'

    def test_a_comment_that_is_not_a_note_raises_no_event(repo):
        _cloud_lane(repo, "cloud-a", 101)
        gh = _NoteGh([_comment(7, 101, "Looks good to me.")])
        result = _arm(repo, gh)
>       assert result["event"] == "timer"
E       AssertionError: assert 'builder-note' == 'timer'
E         
E         - timer
E         + builder-note

plugins/superheroes/lib/tests/test_wave_watch_builder_note.py:156: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_a_comment_that_is_not_a_note_raises_no_event
1 failed in 0.44s
```
  Axis check: the red is the ordinary comment "Looks good to me." surfacing as `builder-note`, i.e. the header axis.
- **Restore:** the exact inverse edit (`if False:` → the original line).
- **Restore receipt** (`grep -n` after the restore): `1300:    if not body.lstrip().startswith(cb.NOTE_HEADER):`
- **Green:**
```
.                                                                        [100%]
1 passed in 0.59s
```

## BP-2 — watched-issue filter

- **Neutralization** (`wave_watch.py:1308`): `on_issue = [lid for lid in watched if watched[lid]["issue"] == number]` → `on_issue = list(watched)`
- **Red** (`...::test_a_note_on_an_issue_no_watched_lane_has_raises_no_event`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_a_note_on_an_issue_no_watched_lane_has_raises_no_event __________

repo = '/private/tmp/claude-501/pytest-of-zwrose/pytest-1429/test_a_note_on_an_issue_no_wat0/repo'

    def test_a_note_on_an_issue_no_watched_lane_has_raises_no_event(repo):
        _cloud_lane(repo, "cloud-a", 101)
        gh = _NoteGh([_comment(7, 999)])
        result = _arm(repo, gh)
>       assert result["event"] == "timer"
E       AssertionError: assert 'builder-note' == 'timer'
E         
E         - timer
E         + builder-note

plugins/superheroes/lib/tests/test_wave_watch_builder_note.py:175: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_a_note_on_an_issue_no_watched_lane_has_raises_no_event
1 failed in 0.43s
```
  Axis check: a well-formed note on issue 999, which no watched lane has, was attributed to the issue-101 lane.
- **Restore:** the exact inverse edit.
- **Restore receipt** (`grep -n` after the restore): `1308:    on_issue = [lid for lid in watched if watched[lid]["issue"] == number]`
- **Green:**
```
.                                                                        [100%]
1 passed in 0.66s
```

## BP-3 — started-time filter

- **Neutralization** (`wave_watch.py:1310`): `lanes = [lid for lid in on_issue if created >= watched[lid]["startedTs"]]` → `lanes = on_issue`
- **Red** (`...::test_a_note_created_before_the_lane_started_raises_no_event`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_a_note_created_before_the_lane_started_raises_no_event __________

repo = '/private/tmp/claude-501/pytest-of-zwrose/pytest-1432/test_a_note_created_before_the0/repo'

    def test_a_note_created_before_the_lane_started_raises_no_event(repo):
        _cloud_lane(repo, "cloud-a", 101, start_age=600)
        gh = _NoteGh([_comment(7, 101, age=3000)])
        result = _arm(repo, gh)
>       assert result["event"] == "timer"
E       AssertionError: assert 'builder-note' == 'timer'
E         
E         - timer
E         + builder-note

plugins/superheroes/lib/tests/test_wave_watch_builder_note.py:182: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_a_note_created_before_the_lane_started_raises_no_event
1 failed in 0.49s
```
  Axis check: a note on the lane's own issue, created 3000 s ago against a lane started 600 s ago, surfaced.
- **Restore:** the exact inverse edit.
- **Restore receipt** (`grep -n` after the restore): `1310:    lanes = [lid for lid in on_issue if created >= watched[lid]["startedTs"]]`
- **Green:**
```
.                                                                        [100%]
1 passed in 0.65s
```

## BP-4 — answered filter

- **Neutralization** (`wave_watch.py:1303`): `if comment_id in answered:` → `if False:`
- **Red** (`...::test_a_note_recorded_answered_raises_no_event`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_a_note_recorded_answered_raises_no_event _________________

repo = '/private/tmp/claude-501/pytest-of-zwrose/pytest-1434/test_a_note_recorded_answered_0/repo'

    def test_a_note_recorded_answered_raises_no_event(repo):
        _cloud_lane(repo, "cloud-a", 101)
        assert _note_answered(repo, 7)["ok"] is True
        gh = _NoteGh([_comment(7, 101)])
        result = _arm(repo, gh)
>       assert result["event"] == "timer"
E       AssertionError: assert 'builder-note' == 'timer'
E         
E         - timer
E         + builder-note

plugins/superheroes/lib/tests/test_wave_watch_builder_note.py:190: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_a_note_recorded_answered_raises_no_event
1 failed in 0.52s
```
  Axis check: the note was recorded answered (the call returned ok), yet it surfaced.
- **Restore:** the exact inverse edit.
- **Restore receipt** (`grep -n` after the restore): `1303:    if comment_id in answered:`
- **Green:**
```
.                                                                        [100%]
1 passed in 0.69s
```

## BP-5 — sending the stored validator

- **Neutralization** (`wave_watch.py:1253`): `if page == 1 and stored is not None and stored[1]:` → `if False:`
- **First red, before the test's assertion was tightened** (disclosed): the red was a `ValueError: '-H' is not in list` from `argv.index("-H")` — the right axis, but not a clean assertion. The neutralization was restored, the test gained `assert "-H" in argv, "repeat read sent no validator: ..."` ahead of the `index` call, and the neutralization was re-applied for the red below, so the red and green that follow ran against the final, unedited test.
- **Red** (`...::test_the_repeat_read_within_one_loop_sends_the_stored_validator`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_the_repeat_read_within_one_loop_sends_the_stored_validator ________

repo = '/private/tmp/claude-501/pytest-of-zwrose/pytest-1437/test_the_repeat_read_within_on0/repo'

    def test_the_repeat_read_within_one_loop_sends_the_stored_validator(repo):
        _cloud_lane(repo, "cloud-a", 101)
        gh = _NoteGh()
        result = ww.loop(
            repo, _BATCH, max_seconds=1, interval_seconds=1, max_total_seconds=3, gh_run=gh,
        )
        assert result["event"] == "timer"
        assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE not in result["degraded"]
        calls = gh.note_calls()
        assert len(calls) >= 3
        assert "-H" not in calls[0]
        for argv in calls[1:]:
>           assert "-H" in argv, "repeat read sent no validator: %r" % (argv,)
E           AssertionError: repeat read sent no validator: ['gh', 'api', '-i', 'repos/owner/repo/issues/comments?since=2026-10-12T06:45:14Z&per_page=100']
E           assert '-H' in ['gh', 'api', '-i', 'repos/owner/repo/issues/comments?since=2026-10-12T06:45:14Z&per_page=100']

plugins/superheroes/lib/tests/test_wave_watch_builder_note.py:272: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_the_repeat_read_within_one_loop_sends_the_stored_validator
1 failed in 0.84s
```
  Axis check: the repeat read, in a loop whose stored read was threaded through, went out without `If-None-Match`.
- **Restore:** the exact inverse edit.
- **Restore receipt** (`grep -n` after the restore): `1253:            if page == 1 and stored is not None and stored[1]:`
- **Green:**
```
.                                                                        [100%]
1 passed in 0.80s
```

## Not claimed

The state-threading seam (`watch_arm`/`loop` passing `note_state`) is covered by BP-5 only through
the loop path: dropping `note_state=note_state` from the `run_fn(...)` call in `loop` is expected,
by reading the code, to send no validator on each later arm's first read. That is a second
neutralization of the same test; it was not run, so that expectation is unobserved.
