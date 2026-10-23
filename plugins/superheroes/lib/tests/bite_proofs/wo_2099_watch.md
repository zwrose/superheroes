# WO-B (#2099) bite-proof — a superseded cloud park, and one answered note ignored by id

**Provenance:** work order WO-B, worktree `/home/user/wt-2099-b` (branch `wo-2099-b`), claude implementer, edits left uncommitted on top of `07d4e594`.

**Method.** Each guarded element is neutralized on its own by a targeted `Edit` to the consumer in `plugins/superheroes/lib/wave_watch.py` (never the detector). The detector is run alone by exact node id (`-q`, no `-k`), the neutralization is undone by the inverse `Edit`, the same node ids are re-run green, and the restored lines are quoted back. One neutralization was live at a time. After G8 the file was checked with `git status --porcelain plugins/superheroes/lib/wave_watch.py`: empty output, so the file equals the committed `07d4e594` content (the code was never edited in this dispatch outside the neutralizations). Redaction: pytest temp paths are kept as printed; nothing else needed redacting. Every capture is far under the 32 KiB per-element ceiling and the whole record is far under 128 KiB.

Command for every run (`<nodes>` is the exact node id list given per element; the tool prints the `UV_NATIVE_TLS` warning first, kept below as printed):

```
scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/pyc-wo-b -m pytest <nodes> -q -p no:cacheprovider
```

Guarded-element set (declared by the order): G1 supersession by progress, G2 supersession by a later note, G3 park-only scope, G4 strictly-later comparison, G5 the note-id filter in `_evaluate_tick`, G6 the filter matching launch id and comment id together, G7 the 3-tuple validation (CLI and API), G8 `ignoredNotes` on every non-refusal result.

Line numbers below are in the restored `wave_watch.py`. `T` = `plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py`, `B` = `plugins/superheroes/lib/tests/test_wave_watch_builder_note.py`.

## G1 — supersession by progress (`wave_watch.py:1509-1511`, `_cloud_terminals`; axis: a progress edit after a park means the lane resumed)

- **Detector:** `T::test_p1_a_park_then_a_progress_edit_later_is_not_lane_terminal` (the recorded shape: progress created before the park, updated after it).
- **Neutralization:** the line `progress_at = progress[lid]["updatedEpoch"] if lid in progress else None` replaced by `progress_at = None` (the lane's progress time treated as absent).
- **Raw red:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_p1_a_park_then_a_progress_edit_later_is_not_lane_terminal ________

repo = '/tmp/claude-0/pytest-of-root/pytest-13/test_p1_a_park_then_a_progress0/repo'

    def test_p1_a_park_then_a_progress_edit_later_is_not_lane_terminal(repo):
        # axis: SUPERSEDED by progress — the recorded shape: a progress comment created before the park, edited after it
        _cloud_lane(repo, "cloud-a", 101)
        park = _comment(7, 101, _body("park"), age=300)
        progress = _progress(8, 101, created_age=500, updated_age=100)
        result = _arm(repo, _NoteGh([park, progress]))
>       assert result["event"] == ww.EVENT_TIMER
E       AssertionError: assert 'lane-terminal' == 'timer'
E         
E         - timer
E         + lane-terminal

/home/user/wt-2099-b/plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py:320: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py::test_p1_a_park_then_a_progress_edit_later_is_not_lane_terminal
1 failed in 0.69s
```

- **Restore:** the inverse `Edit`, `progress_at = None` back to the original line.
- **Restore receipt:** `wave_watch.py:1509: progress_at = progress[lid]["updatedEpoch"] if lid in progress else None`; `git status --porcelain plugins/superheroes/lib/wave_watch.py` after G8 printed nothing.
- **Raw green:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.30s
```

## G2 — supersession by a later builder note (`wave_watch.py:1512`; axis: a note created after the park means the lane resumed, answered or not)

- **Detector:** `T::test_p4_a_park_then_a_builder_note_created_later_is_not_lane_terminal`.
- **Neutralization:** `if lid in note_times and note_times[lid] > parked_at:` became `if False and lid in note_times and note_times[lid] > parked_at:` (note activity ignored).
- **Raw red:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_p4_a_park_then_a_builder_note_created_later_is_not_lane_terminal _____

repo = '/tmp/claude-0/pytest-of-root/pytest-15/test_p4_a_park_then_a_builder_0/repo'

    def test_p4_a_park_then_a_builder_note_created_later_is_not_lane_terminal(repo):
        # axis: SUPERSEDED by note — the note itself fires as builder-note
        _cloud_lane(repo, "cloud-a", 101)
        park = _comment(7, 101, _body("park"), age=300)
        note = _comment(8, 101, age=100)
        result = _arm(repo, _NoteGh([park, note]))
>       assert result["event"] == ww.EVENT_BUILDER_NOTE
E       AssertionError: assert 'lane-terminal' == 'builder-note'
E         
E         - builder-note
E         + lane-terminal

/home/user/wt-2099-b/plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py:360: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py::test_p4_a_park_then_a_builder_note_created_later_is_not_lane_terminal
1 failed in 0.46s
```

- **Restore:** the inverse `Edit`, the `False and ` prefix removed.
- **Restore receipt:** `wave_watch.py:1512: if lid in note_times and note_times[lid] > parked_at:`; `git status --porcelain` over the file printed nothing after G8.
- **Raw green:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.45s
```

## G3 — park-only scope (`wave_watch.py:1507`; axis: a handback or stop is never superseded)

- **Detector:** `T::test_p5_a_handback_or_stop_is_never_superseded` (both parameters).
- **Neutralization:** `if kind == "park":` became `if True:` (supersede any kind).
- **Raw red:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FF                                                                       [100%]
=================================== FAILURES ===================================
______ test_p5_a_handback_or_stop_is_never_superseded[handback-handback] _______

kind = 'handback', state = 'handback'

    @pytest.mark.parametrize("kind, state", [("handback", "handback"), ("stop", "stopped")])
    def test_p5_a_handback_or_stop_is_never_superseded(kind, state):
        # axis: PARK ONLY — the supersession applies to a park alone
        ending = _comment(7, 101, _body(kind), age=300)
        progress = _progress(8, 101, created_age=500, updated_age=100)
        note = _comment(9, 101, age=50)
        for later in ([progress], [note], [progress, note]):
>           [only] = _terminals([ending] + later)
            ^^^^^^
E           ValueError: not enough values to unpack (expected 1, got 0)

/home/user/wt-2099-b/plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py:384: ValueError
_________ test_p5_a_handback_or_stop_is_never_superseded[stop-stopped] _________

kind = 'stop', state = 'stopped'

    @pytest.mark.parametrize("kind, state", [("handback", "handback"), ("stop", "stopped")])
    def test_p5_a_handback_or_stop_is_never_superseded(kind, state):
        # axis: PARK ONLY — the supersession applies to a park alone
        ending = _comment(7, 101, _body(kind), age=300)
        progress = _progress(8, 101, created_age=500, updated_age=100)
        note = _comment(9, 101, age=50)
        for later in ([progress], [note], [progress, note]):
>           [only] = _terminals([ending] + later)
            ^^^^^^
E           ValueError: not enough values to unpack (expected 1, got 0)

/home/user/wt-2099-b/plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py:384: ValueError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py::test_p5_a_handback_or_stop_is_never_superseded[handback-handback]
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py::test_p5_a_handback_or_stop_is_never_superseded[stop-stopped]
2 failed in 0.38s
```

- **Restore:** the inverse `Edit`, `if True:` back to `if kind == "park":`.
- **Restore receipt:** `wave_watch.py:1507: if kind == "park":`; `git status --porcelain` over the file printed nothing after G8.
- **Raw green:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..                                                                       [100%]
2 passed in 0.39s
```

## G4 — strictly-later comparison (`wave_watch.py:1510` and `:1512`; axis: a tie keeps the park)

- **Detector:** `T::test_p3_a_park_and_a_progress_edit_in_the_same_second_keeps_the_park` and `T::test_p3_a_park_and_a_builder_note_in_the_same_second_keeps_the_park` (one per comparison; the order names P3, the progress tie; the note tie test was added so the second comparison is also guarded).
- **Neutralization:** both comparisons `>` became `>=`: `progress_at >= parked_at` and `note_times[lid] >= parked_at`.
- **Raw red:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FF                                                                       [100%]
=================================== FAILURES ===================================
_____ test_p3_a_park_and_a_progress_edit_in_the_same_second_keeps_the_park _____

    def test_p3_a_park_and_a_progress_edit_in_the_same_second_keeps_the_park():
        # axis: STRICT — a tie keeps the park
        park = _comment(7, 101, _body("park"), age=100)
        progress = {**_progress(8, 101, created_age=500, updated_age=100), "updated_at": park["created_at"]}
        for order in ([park, progress], [progress, park]):
>           [only] = _terminals(order)
            ^^^^^^
E           ValueError: not enough values to unpack (expected 1, got 0)

/home/user/wt-2099-b/plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py:338: ValueError
_____ test_p3_a_park_and_a_builder_note_in_the_same_second_keeps_the_park ______

    def test_p3_a_park_and_a_builder_note_in_the_same_second_keeps_the_park():
        # axis: STRICT — a tie keeps the park, for a note as for a progress edit
        park = _comment(7, 101, _body("park"), age=100)
        note = {**_comment(8, 101, age=100), "created_at": park["created_at"]}
        for order in ([park, note], [note, park]):
>           [only] = _terminals(order)
            ^^^^^^
E           ValueError: not enough values to unpack (expected 1, got 0)

/home/user/wt-2099-b/plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py:349: ValueError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py::test_p3_a_park_and_a_progress_edit_in_the_same_second_keeps_the_park
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_terminal.py::test_p3_a_park_and_a_builder_note_in_the_same_second_keeps_the_park
2 failed in 0.39s
```

- **Restore:** two inverse `Edit`s, `>=` back to `>` on both lines.
- **Restore receipt:** `wave_watch.py:1510: if progress_at is not None and progress_at > parked_at:` and `:1512: if lid in note_times and note_times[lid] > parked_at:`; `git status --porcelain` over the file printed nothing after G8.
- **Raw green:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..                                                                       [100%]
2 passed in 0.40s
```

## G5 — the note-id filter in `_evaluate_tick` (`wave_watch.py:2517-2521`; axis: a named note is dropped before the event context is built)

- **Detector:** `B::test_n1_two_notes_on_one_lane_with_one_ignored_fires_with_only_the_other` and `B::test_n2_the_only_note_ignored_raises_no_builder_note_and_the_timer_carries_it`.
- **Neutralization:** `if ignore_notes:` became `if False and ignore_notes:` (the filter skipped).
- **Raw red:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FF                                                                       [100%]
=================================== FAILURES ===================================
___ test_n1_two_notes_on_one_lane_with_one_ignored_fires_with_only_the_other ___

repo = '/tmp/claude-0/pytest-of-root/pytest-21/test_n1_two_notes_on_one_lane_0/repo'

    def test_n1_two_notes_on_one_lane_with_one_ignored_fires_with_only_the_other(repo):
        # axis: NOTE IGNORE — the filter drops the named note and keeps every other
        _cloud_lane(repo, "cloud-a", 101)
        gh = _NoteGh([_comment(7, 101, age=120), _comment(8, 101, age=60)])
        for result in (
            ww.run(repo, _BATCH, gh_run=gh, ignore_events=(_ignore("cloud-a", 7),)),
            _arm(repo, gh, ignore_events=(_ignore("cloud-a", 7),)),
        ):
            assert result["event"] == ww.EVENT_BUILDER_NOTE
>           assert _ids(result) == [8]
E           assert [7, 8] == [8]
E             
E             At index 0 diff: 7 != 8
E             Left contains one more item: 8
E             Use -v to get more diff

/home/user/wt-2099-b/plugins/superheroes/lib/tests/test_wave_watch_builder_note.py:708: AssertionError
_ test_n2_the_only_note_ignored_raises_no_builder_note_and_the_timer_carries_it _

repo = '/tmp/claude-0/pytest-of-root/pytest-21/test_n2_the_only_note_ignored_0/repo'

    def test_n2_the_only_note_ignored_raises_no_builder_note_and_the_timer_carries_it(repo):
        # axis: IGNORED NOTES — a suppressed note is never invisible: the timer result carries its id
        _cloud_lane(repo, "cloud-a", 101)
        gh = _NoteGh([_comment(7, 101)])
        ignore = (_ignore("cloud-a", 7),)
        ran = ww.run(repo, _BATCH, gh_run=gh, ignore_events=ignore)
        armed = ww.watch_arm(
            repo, _BATCH, max_seconds=1, interval_seconds=1, gh_run=gh, ignore_events=ignore,
        )
        for result in (ran, armed):
            assert result["ok"] is True
>           assert result["event"] == ww.EVENT_TIMER
E           AssertionError: assert 'builder-note' == 'timer'
E             
E             - timer
E             + builder-note

/home/user/wt-2099-b/plugins/superheroes/lib/tests/test_wave_watch_builder_note.py:724: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_n1_two_notes_on_one_lane_with_one_ignored_fires_with_only_the_other
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_n2_the_only_note_ignored_raises_no_builder_note_and_the_timer_carries_it
2 failed in 0.52s
```

- **Restore:** the inverse `Edit`, the `False and ` prefix removed.
- **Restore receipt:** `wave_watch.py:2517: if ignore_notes:`; `git status --porcelain` over the file printed nothing after G8.
- **Raw green:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..                                                                       [100%]
2 passed in 0.49s
```

## G6 — the filter matches launch id and comment id together (`wave_watch.py:2520`; axis: another lane's note with the same comment id is not suppressed)

- **Detector:** `B::test_n3_the_triple_matches_the_launch_id_and_the_comment_id_together`.
- **Neutralization:** `if (note["launchId"], note["commentId"]) not in ignore_notes` became `if note["commentId"] not in {cid for _lid, cid in ignore_notes}` (comment id only).
- **Raw red:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_n3_the_triple_matches_the_launch_id_and_the_comment_id_together _____

repo = '/tmp/claude-0/pytest-of-root/pytest-23/test_n3_the_triple_matches_the0/repo'

    def test_n3_the_triple_matches_the_launch_id_and_the_comment_id_together(repo):
        # axis: NOTE IGNORE keyed on both — the same comment id on another lane is not suppressed
        _cloud_lane(repo, "cloud-a", 101)
        _cloud_lane(repo, "cloud-b", 202)
        gh = _NoteGh([_comment(7, 101), _comment(9, 202)])
        only_a = ww.run(repo, _BATCH, gh_run=gh, ignore_events=(_ignore("cloud-a", 7),))
        assert only_a["event"] == ww.EVENT_BUILDER_NOTE
        assert _ids(only_a) == [9]
        assert only_a["launchId"] == "cloud-b"
        wrong_lane = ww.run(repo, _BATCH, gh_run=gh, ignore_events=(_ignore("cloud-b", 7),))
>       assert _ids(wrong_lane) == [7, 9]
E       assert [9] == [7, 9]
E         
E         At index 0 diff: 9 != 7
E         Right contains one more item: 9
E         Use -v to get more diff

/home/user/wt-2099-b/plugins/superheroes/lib/tests/test_wave_watch_builder_note.py:758: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_n3_the_triple_matches_the_launch_id_and_the_comment_id_together
1 failed in 0.43s
```

- **Restore:** the inverse `Edit`, back to the `(launchId, commentId)` pair membership test.
- **Restore receipt:** `wave_watch.py:2520: if (note["launchId"], note["commentId"]) not in ignore_notes`; `git status --porcelain` over the file printed nothing after G8.
- **Raw green:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.42s
```

## G7 — the 3-tuple validation, CLI and API (`wave_watch.py:435` in `_validate_ignore_events`, `:3127` in `_parse_ignore_event_cli`; axis: a note ignore needs builder-note and a positive int comment id)

- **Detector:** `B::test_n4_a_malformed_note_ignore_is_refused_from_the_cli`, `B::test_n4_the_cli_parses_the_note_form_splitting_from_the_right`, `B::test_n4_a_malformed_note_ignore_is_refused_from_the_api`.
- **Neutralization (two edits, one element: accept any third part):** in `_validate_ignore_events`, `if event != EVENT_BUILDER_NOTE or not _valid_positive_int(item[2]):` became `if event != EVENT_BUILDER_NOTE:`; in `_parse_ignore_event_cli`, the three lines `comment_id = _parse_comment_id(parts[2])` / `if comment_id is None:` / `return None` became the single line `comment_id = parts[2]`.
- **Raw red — INCOMPLETE:** the tool output was cut by the harness; the line `... [4586 characters truncated] ...` below is the harness's own marker, not mine. What follows is exactly the output I have: the first six CLI failures are cut mid-way through the sixth, and the tail resumes inside the API failure for `bad5`. Result line: `14 failed, 16 passed in 2.95s`. The seven CLI/parse failures and seven API failures are all named in the short summary. The first and last lines are the first and last lines of the capture.

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.FFFFFF......F.FFFFFFF........                                           [100%]
=================================== FAILURES ===================================
_ test_n4_a_malformed_note_ignore_is_refused_from_the_cli[cloud-a:builder-note:0] _

repo = '/tmp/claude-0/pytest-of-root/pytest-25/test_n4_a_malformed_note_ignor1/repo'
capsys = <_pytest.capture.CaptureFixture object at 0x7f521fca28d0>
raw = 'cloud-a:builder-note:0'

    @pytest.mark.parametrize("raw", _BAD_CLI)
    def test_n4_a_malformed_note_ignore_is_refused_from_the_cli(repo, capsys, raw):
        # axis: NOTE ID validation — the CLI form needs a launch id, builder-note and a positive decimal id
        code = ww.main(["wave_watch.py", "run", "--repo-root", repo, "--batch", _BATCH, "--ignore-event", raw])
        printed = json.loads(capsys.readouterr().out)
>       assert code == 1
E       assert 0 == 1

/home/user/wt-2099-b/plugins/superheroes/lib/tests/test_wave_watch_builder_note.py:775: AssertionError
... [4586 characters truncated] ... (harness marker; the middle of the output was lost, not reconstructed)
_wave_watch_builder_note.py:824: AssertionError
________ test_n4_a_malformed_note_ignore_is_refused_from_the_api[bad5] _________

repo = '/tmp/claude-0/pytest-of-root/pytest-25/test_n4_a_malformed_note_ignor18/repo'
bad = ('cloud-a', 'builder-note', True)

    @pytest.mark.parametrize("bad", _BAD_API)
    def test_n4_a_malformed_note_ignore_is_refused_from_the_api(repo, bad):
        # axis: NOTE ID validation — a 3-tuple needs builder-note and a positive int comment id
        for result in (
            ww.run(repo, _BATCH, gh_run=_NoteGh(), ignore_events=(bad,)),
            ww.watch_arm(repo, _BATCH, max_seconds=1, interval_seconds=1, gh_run=_NoteGh(), ignore_events=(bad,)),
            ww.loop(repo, _BATCH, max_seconds=1, interval_seconds=1, max_total_seconds=2, gh_run=_NoteGh(), ignore_events=(bad,)),
        ):
>           assert result["ok"] is False
E           assert True is False

/home/user/wt-2099-b/plugins/superheroes/lib/tests/test_wave_watch_builder_note.py:824: AssertionError
________ test_n4_a_malformed_note_ignore_is_refused_from_the_api[bad6] _________

repo = '/tmp/claude-0/pytest-of-root/pytest-25/test_n4_a_malformed_note_ignor19/repo'
bad = ('cloud-a', 'builder-note', False)

    @pytest.mark.parametrize("bad", _BAD_API)
    def test_n4_a_malformed_note_ignore_is_refused_from_the_api(repo, bad):
        # axis: NOTE ID validation — a 3-tuple needs builder-note and a positive int comment id
        for result in (
            ww.run(repo, _BATCH, gh_run=_NoteGh(), ignore_events=(bad,)),
            ww.watch_arm(repo, _BATCH, max_seconds=1, interval_seconds=1, gh_run=_NoteGh(), ignore_events=(bad,)),
            ww.loop(repo, _BATCH, max_seconds=1, interval_seconds=1, max_total_seconds=2, gh_run=_NoteGh(), ignore_events=(bad,)),
        ):
>           assert result["ok"] is False
E           assert True is False

/home/user/wt-2099-b/plugins/superheroes/lib/tests/test_wave_watch_builder_note.py:824: AssertionError
________ test_n4_a_malformed_note_ignore_is_refused_from_the_api[bad7] _________

repo = '/tmp/claude-0/pytest-of-root/pytest-25/test_n4_a_malformed_note_ignor20/repo'
bad = ('cloud-a', 'builder-note', None)

    @pytest.mark.parametrize("bad", _BAD_API)
    def test_n4_a_malformed_note_ignore_is_refused_from_the_api(repo, bad):
        # axis: NOTE ID validation — a 3-tuple needs builder-note and a positive int comment id
        for result in (
            ww.run(repo, _BATCH, gh_run=_NoteGh(), ignore_events=(bad,)),
            ww.watch_arm(repo, _BATCH, max_seconds=1, interval_seconds=1, gh_run=_NoteGh(), ignore_events=(bad,)),
            ww.loop(repo, _BATCH, max_seconds=1, interval_seconds=1, max_total_seconds=2, gh_run=_NoteGh(), ignore_events=(bad,)),
        ):
>           assert result["ok"] is False
E           assert True is False

/home/user/wt-2099-b/plugins/superheroes/lib/tests/test_wave_watch_builder_note.py:824: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_n4_a_malformed_note_ignore_is_refused_from_the_cli[cloud-a:builder-note:0]
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_n4_a_malformed_note_ignore_is_refused_from_the_cli[cloud-a:builder-note:-3]
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_n4_a_malformed_note_ignore_is_refused_from_the_cli[cloud-a:builder-note:abc]
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_n4_a_malformed_note_ignore_is_refused_from_the_cli[cloud-a:builder-note:+5]
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_n4_a_malformed_note_ignore_is_refused_from_the_cli[cloud-a:builder-note:1.5]
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_n4_a_malformed_note_ignore_is_refused_from_the_cli[cloud-a:builder-note:]
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_n4_the_cli_parses_the_note_form_splitting_from_the_right
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_n4_a_malformed_note_ignore_is_refused_from_the_api[bad1]
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_n4_a_malformed_note_ignore_is_refused_from_the_api[bad2]
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_n4_a_malformed_note_ignore_is_refused_from_the_api[bad3]
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_n4_a_malformed_note_ignore_is_refused_from_the_api[bad4]
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_n4_a_malformed_note_ignore_is_refused_from_the_api[bad5]
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_n4_a_malformed_note_ignore_is_refused_from_the_api[bad6]
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_n4_a_malformed_note_ignore_is_refused_from_the_api[bad7]
14 failed, 16 passed in 2.95s
```

- **Restore:** two inverse `Edit`s: the `or not _valid_positive_int(item[2])` clause back, and the three CLI lines back.
- **Restore receipt:** `wave_watch.py:435: if event != EVENT_BUILDER_NOTE or not _valid_positive_int(item[2]):` and `:3127: comment_id = _parse_comment_id(parts[2])` followed by `if comment_id is None:` / `return None`; `git status --porcelain` over the file printed nothing after G8.
- **Raw green:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..............................                                           [100%]
30 passed in 1.56s
```

## G8 — `ignoredNotes` on every non-refusal result, timer path (`wave_watch.py:2885` in `run`, `:2784` in `watch_arm`; axis: a suppressed note is never invisible)

- **Detector:** `B::test_n2_the_only_note_ignored_raises_no_builder_note_and_the_timer_carries_it`. It checks the `run` timer result and then the `watch_arm` deadline timer result.
- **Neutralization (two edits):** in `run`, the timer return's `), ignore_events)` became `), ())`; in `watch_arm`, `), resolved_ledger_path), ignore_events)` became `), resolved_ledger_path), ())`. `_with_ignored_notes` then sees no ignores and attaches nothing.
- **Raw red:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_n2_the_only_note_ignored_raises_no_builder_note_and_the_timer_carries_it _

repo = '/tmp/claude-0/pytest-of-root/pytest-27/test_n2_the_only_note_ignored_0/repo'

    def test_n2_the_only_note_ignored_raises_no_builder_note_and_the_timer_carries_it(repo):
        # axis: IGNORED NOTES — a suppressed note is never invisible: the timer result carries its id
        _cloud_lane(repo, "cloud-a", 101)
        gh = _NoteGh([_comment(7, 101)])
        ignore = (_ignore("cloud-a", 7),)
        ran = ww.run(repo, _BATCH, gh_run=gh, ignore_events=ignore)
        armed = ww.watch_arm(
            repo, _BATCH, max_seconds=1, interval_seconds=1, gh_run=gh, ignore_events=ignore,
        )
        for result in (ran, armed):
            assert result["ok"] is True
            assert result["event"] == ww.EVENT_TIMER
>           assert result["ignoredNotes"] == [7]
                   ^^^^^^^^^^^^^^^^^^^^^^
E           KeyError: 'ignoredNotes'

/home/user/wt-2099-b/plugins/superheroes/lib/tests/test_wave_watch_builder_note.py:725: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_n2_the_only_note_ignored_raises_no_builder_note_and_the_timer_carries_it
1 failed in 0.43s
```

- **Restore:** two inverse `Edit`s, `())` back to `ignore_events)` in both returns.
- **Restore receipt:** `wave_watch.py:2784: ), resolved_ledger_path), ignore_events)` and `:2885: ), ignore_events)`; `git status --porcelain plugins/superheroes/lib/wave_watch.py` printed nothing (empty output) after this restore.
- **Raw green:**

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.70s
```

**Disclosed limits of this proof.**

- G8's order text expects N6 red "if it goes through the same path". It does not: the loop's final result for N6 is the ceiling timer built by `_ceiling_timer_result`, and the loop attaches `ignoredNotes` to it itself (`_with_ignored_notes(final, ignore_events)` in `loop`), so dropping the attach on the `run` and `watch_arm` timer returns leaves N6 green. N6's own attach is a separate call site; it was not neutralized, because the declared set names only the timer path.
- In G8 the first failing check is the `run` result; the `watch_arm` deadline result is checked after it in the same loop in that test, so with only the `run` return restored that test would still go red on the `watch_arm` result. That was not run as a separate neutralization.
- G7's red capture is incomplete (see above).
