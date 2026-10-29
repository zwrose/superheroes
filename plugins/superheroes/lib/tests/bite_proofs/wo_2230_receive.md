# Bite-proof record: a cloud detective is received, noted and watched (#2230, receiving side)

Detectors: `plugins/superheroes/lib/tests/test_cloud_builder.py` (`T1`), `plugins/superheroes/lib/tests/test_wave_watch_cloud_detective.py` (`T2`).
Guarded elements (declared by the order): (C1) the detective match in `cloud_builder.launch_charter`; (C2) the builder text kept for
non-detective launches; (C3) the detective intake note is not misread as an ending; (C4) the wave watch reads a detective lane's terminal
comment; (C5) the wave watch reads a detective lane's progress comment.
Each was neutralized by a targeted edit in the production file, the detector run alone as one test node, then restored by the inverse
edit. C4 and C5 edited `plugins/superheroes/lib/wave_watch.py` temporarily; it is unmodified in the final tree. No test file was edited
during the proofs.

Every command was run from `<worktree>` as `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2230 -m pytest <file>::<test> -q -p no:cacheprovider`.
The `UV_NATIVE_TLS` deprecation warning that heads every run is omitted below. Long `where` lines are shown as pytest printed them;
nothing else is elided. Pytest's own tmp paths (`/tmp/claude-0/pytest-of-root/...`) are session scratch, not the worktree.

## 1. C1: the detective match

Axis: a launch whose first non-blank line is the detective command is read as a detective launch. Class: "detective launch read as
workhorse". Representative node: `T1::test_a_detective_intake_succeeds_with_the_detective_note_and_the_same_git_calls`. The integration
node `T1::test_the_launchers_detective_cloud_prompt_passes_intake` (asserts `launch_charter(prompt) == "detective"`) and
`T1::test_launch_charter_reads_the_first_non_blank_line` belong to the class and were not run red alone.

- Neutralization (`cloud_builder.py:226`, `launch_charter`): `return "detective" if first == _sibling("launcher")._CHARTER_COMMANDS["detective"] else "workhorse"` became `return "workhorse"`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_detective_intake_succeeds_with_the_detective_note_and_the_same_git_calls _

    def test_a_detective_intake_succeeds_with_the_detective_note_and_the_same_git_calls():
        run = FakeRun()
        result = _intake(run, launch=_detective_launch())
>       assert result == {"ok": True, "outcome": None, "reason": None, "startedFrom": SHA,
                          "comment": cb.DETECTIVE_INTAKE_TEXT.format(v=VERSION, sha=SHA),
                          "pluginVersion": VERSION, "branch": None}
E       assert {'ok': True, ...aaaaaaa', ...} == {'ok': True, ...aaaaaaa', ...}
E         
E         Omitting 6 identical items, use -vv to show
E         Differing items:
E         {'comment': "Builder intake (cloud build). Plugin 9.8.7. Commits from this build carry the cloud's own author name; th...e under the owner's name.\n\nStarted from aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, the base commit the launch named."} != {'comment': 'Detective intake (cloud session). Plugin 9.8.7. This lane diagnoses only: it pushes no branch and opens n...nside this cloud session.\n\nStarted from aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, the base commit the launch named.'}
E         Use -v to get more diff

<worktree>/plugins/superheroes/lib/tests/test_cloud_builder.py:722: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_builder.py::test_a_detective_intake_succeeds_with_the_detective_note_and_the_same_git_calls
1 failed in 4.22s
```

- Restore: the inverse edit.
- Restore receipt (`cloud_builder.py:224-226`, read back after the restore): `        return "workhorse"` (the non-string early return, never edited) / `    first = next((line.strip() for line in text.splitlines() if line.strip()), None)` / `    return "detective" if first == _sibling("launcher")._CHARTER_COMMANDS["detective"] else "workhorse"`.
- Green:

```
.                                                                        [100%]
1 passed in 3.47s
```

## 2. C2: the builder text is kept for non-detective launches

Axis: a launch whose first non-blank line is not the detective command gets the builder's intake note, byte for byte.

- Neutralization (`cloud_builder.py:226`, `launch_charter`): the same return line became `return "detective"`.
- Node: `T1::test_intake_success_runs_the_checks_in_order_and_returns_the_board_text` (an existing test, unedited).
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_intake_success_runs_the_checks_in_order_and_returns_the_board_text ____

    def test_intake_success_runs_the_checks_in_order_and_returns_the_board_text():
        run = FakeRun()
        result = _intake(run)
>       assert result == {"ok": True, "outcome": None, "reason": None, "startedFrom": SHA,
                          "comment": cb.INTAKE_TEXT.format(v=VERSION, sha=SHA),
                          "pluginVersion": VERSION, "branch": None}
E       assert {'ok': True, ...aaaaaaa', ...} == {'ok': True, ...aaaaaaa', ...}
E         
E         Omitting 6 identical items, use -vv to show
E         Differing items:
E         {'comment': 'Detective intake (cloud session). Plugin 9.8.7. This lane diagnoses only: it pushes no branch and opens n...nside this cloud session.\n\nStarted from aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, the base commit the launch named.'} != {'comment': "Builder intake (cloud build). Plugin 9.8.7. Commits from this build carry the cloud's own author name; th...e under the owner's name.\n\nStarted from aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, the base commit the launch named."}
E         Use -v to get more diff

<worktree>/plugins/superheroes/lib/tests/test_cloud_builder.py:348: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_builder.py::test_intake_success_runs_the_checks_in_order_and_returns_the_board_text
1 failed in 3.61s
```

- Restore: the inverse edit.
- Restore receipt (`cloud_builder.py:224-226`, read back after the restore): `        return "workhorse"` / `    first = next((line.strip() for line in text.splitlines() if line.strip()), None)` / `    return "detective" if first == _sibling("launcher")._CHARTER_COMMANDS["detective"] else "workhorse"`.
- Green:

```
.                                                                        [100%]
1 passed in 0.73s
```

## 3. C3: the detective intake note is not misread as an ending (E9)

Axis: the detective intake note opens with no header the wave watch reads, so a lane-terminal never fires on it.

- Neutralization (`cloud_builder.py:70-71`, `DETECTIVE_INTAKE_TEXT`): a first piece `"Builder stop (cloud build).\n\n"` was added before `"Detective intake (cloud session). ..."` (the stop header hard-coded; `STOP_HEADER + "\n\n"`).
- Node: `T2::test_a_detective_intake_note_is_neither_lane_terminal_nor_a_builder_note[bare-started]`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_detective_intake_note_is_neither_lane_terminal_nor_a_builder_note[bare-started] _

repo = '/tmp/claude-0/pytest-of-root/pytest-20/test_a_detective_intake_note_i0/repo'
make = <function _intake_note at 0x7f1b3b7b14e0>, footered = False

    @pytest.mark.parametrize("make", [_intake_note, _adopt_note], ids=["started", "adopted"])
    @pytest.mark.parametrize("footered", [False, True], ids=["bare", "footered"])
    def test_a_detective_intake_note_is_neither_lane_terminal_nor_a_builder_note(repo, make, footered):
        # axis: the intake note opens with no header the watch reads, so it is never an ending or a note
        body = make() + ("\n\n" + cb.CLOUD_FOOTER if footered else "")
        _detective_lane(repo, "cloud-a", 101)
>       assert _arm(repo, _ProgressGh([_comment(7, 101, body)], activity_age=_FRESH))["event"] == ww.EVENT_TIMER
E       AssertionError: assert 'lane-terminal' == 'timer'
E         
E         - timer
E         + lane-terminal

<worktree>/plugins/superheroes/lib/tests/test_wave_watch_cloud_detective.py:70: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_detective.py::test_a_detective_intake_note_is_neither_lane_terminal_nor_a_builder_note[bare-started]
1 failed in 0.56s
```

- Restore: the inverse edit.
- Restore receipt (`cloud_builder.py:70-72`, read back after the restore): `DETECTIVE_INTAKE_TEXT = (` / `    "Detective intake (cloud session). Plugin {v}. This lane diagnoses only: it pushes no branch "` / `    "and opens no pull request, and its disposable copies live only inside this cloud session.\n\n"`; a search for the stop header text in the constant found none.
- Green:

```
.                                                                        [100%]
1 passed in 0.63s
```

## 4. C4: the wave watch reads a detective lane's terminal comment

Axis: a handback, park or stop comment on a detective lane's issue is lane-terminal (the ending reader skips only a comment that is no ending).

- Neutralization (`wave_watch.py:1798`, `_cloud_endings`; temporary, authorized by the order): `if kind is None:` became `if True:`.
- Node: `T2::test_each_terminal_kind_on_a_detective_lane_is_lane_terminal_through_the_ledger[handback-handback]`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_each_terminal_kind_on_a_detective_lane_is_lane_terminal_through_the_ledger[handback-handback] _

repo = '/tmp/claude-0/pytest-of-root/pytest-22/test_each_terminal_kind_on_a_d0/repo'
kind = 'handback', state = 'handback'

    @pytest.mark.parametrize("kind, state", [("handback", "handback"), ("park", "parked"), ("stop", "stopped")])
    def test_each_terminal_kind_on_a_detective_lane_is_lane_terminal_through_the_ledger(repo, kind, state):
        # axis: the watch reads a detective lane's terminal comment; the ledger path carries the detective record
        _detective_lane(repo, "cloud-a", 101)
        body = _terminal_body(kind) + "\n\n" + cb.CLOUD_FOOTER
        result = _arm(repo, _NoteGh([_comment(7, 101, body)]))
>       assert result["event"] == ww.EVENT_LANE_TERMINAL, result
E       AssertionError: {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': ['builder-note-unavailable'], ...}
E       assert 'timer' == 'lane-terminal'
E         
E         - lane-terminal
E         + timer

<worktree>/plugins/superheroes/lib/tests/test_wave_watch_cloud_detective.py:106: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_detective.py::test_each_terminal_kind_on_a_detective_lane_is_lane_terminal_through_the_ledger[handback-handback]
1 failed in 0.75s
```

- Restore: the inverse edit.
- Restore receipt (`wave_watch.py:1797-1799`, read back after the restore): `        kind = cb.terminal_kind(body)` / `        if kind is None:` / `            continue`; a search for `if True:` in the file found no match.
- Green:

```
.                                                                        [100%]
1 passed in 0.50s
```

## 5. C5: the wave watch reads a detective lane's progress comment

Axis: a progress comment on a detective lane's issue decides staleness with the progress fields (a lane past its step plus the window is stale with `progressExpectedSeconds`, not by activity).

- Neutralization (`wave_watch.py:1908`, `_cloud_progress`; temporary, authorized by the order): `fields = cb.parse_progress(body)` became `fields = None`.
- Node: `T2::test_a_progress_comment_past_its_step_plus_the_window_on_a_detective_lane_is_stale`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_progress_comment_past_its_step_plus_the_window_on_a_detective_lane_is_stale _

repo = '/tmp/claude-0/pytest-of-root/pytest-24/test_a_progress_comment_past_i0/repo'

    def test_a_progress_comment_past_its_step_plus_the_window_on_a_detective_lane_is_stale(repo):
        # axis: a detective lane past its stated step plus the window is stale with the progress fields
        _detective_lane(repo, "cloud-a", 101)
        age = _EXPECTED_60 + _WINDOW + 60
        result = _arm(repo, _ProgressGh([_progress(7, 101, updated_age=age, body=_progress_body())]))
        assert result["event"] == ww.EVENT_LANE_STALE
        [launch] = result["launches"]
        assert launch["launchId"] == "cloud-a"
>       assert launch["progressExpectedSeconds"] == _EXPECTED_60
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'progressExpectedSeconds'

<worktree>/plugins/superheroes/lib/tests/test_wave_watch_cloud_detective.py:92: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_detective.py::test_a_progress_comment_past_its_step_plus_the_window_on_a_detective_lane_is_stale
1 failed in 0.56s
```

  (The neutralized lane still goes lane-stale, by the activity rule, so the red lands on the progress fields, not on the event.)
- Restore: the inverse edit.
- Restore receipt (`wave_watch.py:1908-1909`, read back after the restore): `        fields = cb.parse_progress(body)` / `        if fields is None:`; a search for `fields = None` found no match.
- Green:

```
.                                                                        [100%]
1 passed in 0.60s
```

## Post-restore check

`git status --porcelain` after the last restore lists no `plugins/superheroes/lib/wave_watch.py` entry; the modified production file in the final tree is `plugins/superheroes/lib/cloud_builder.py` (the feature itself). This is a supplementary check, not the restore receipt.

## 6. D1: the composed detective cloud prompt passes intake with the detective note (review round 1, F-v1)

- Guarded element and axis: `test_cloud_builder.py::test_the_launchers_detective_cloud_prompt_passes_intake` — the launcher's composed detective prompt selects the detective charter and, run through `cb.intake`, yields the detective intake note and a detached checkout of the base commit.
- Neutralization (`cloud_builder.py`, `launch_charter`): the return line `return "detective" if first == _sibling("launcher")._CHARTER_COMMANDS["detective"] else "workhorse"` became `return "workhorse"`.
- Red (single node, unedited test; the pytest `UV_NATIVE_TLS` deprecation warning line is omitted from the quote):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_the_launchers_detective_cloud_prompt_passes_intake ____________

    def test_the_launchers_detective_cloud_prompt_passes_intake():
        composed = _composed_detective_prompt()
        parsed = cb.parse_launch(composed["prompt"])
        assert parsed == {"advisorVersion": composed["pluginVersion"],
                          "environment": ENV_ID, "baseCommit": SHA, "adoptsBranch": None, "adoptsHead": None}
>       assert cb.launch_charter(composed["prompt"]) == "detective"
E       AssertionError: assert 'workhorse' == 'detective'
E         
E         - detective
E         + workhorse

/home/user/wt-2230/plugins/superheroes/lib/tests/test_cloud_builder.py:796: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_builder.py::test_the_launchers_detective_cloud_prompt_passes_intake
1 failed in 0.74s
```

  (The red lands on the existing `launch_charter` assertion, which runs before the new intake lines, so this neutralization shows the node bites but does not isolate the new `cb.intake` assertions. Those assertions follow the same selection at `cloud_builder.py:262-263`, which this record did not neutralize separately.)
- Restore: the inverse edit, putting the original return line back.
- Restore receipt (`cloud_builder.py:226`, read back after the restore): `    return "detective" if first == _sibling("launcher")._CHARTER_COMMANDS["detective"] else "workhorse"`. `git status --porcelain` lists no `cloud_builder.py` entry.
- Green:

```
.                                                                        [100%]
1 passed in 3.75s
```
