# Bite-proof record: #2651 the wave watch attributes a builder note or cloud terminal comment on a watched lane's own PR to that lane, through a link GitHub records

Detector under proof: `plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py` (plus, for element 6, the
existing `test_wave_watch_builder_note.py::test_a_lane_with_no_numeric_started_ts_is_not_watched_and_the_rest_still_count`,
and for element 7 the existing `test_wave_watch_pr_old_resumed_2651.py`). Guarded code:
`plugins/superheroes/lib/wave_watch.py`.
Base: `2f804e8ba99f5f3f050c91e9398d85b5e7519517`; this record is the rewrite for the seam that replaced the body
reader: a pull request belongs to a lane only through a link GitHub records (its closing issue references when it is
based on the default branch, a cross-reference on the lane's issue timeline when it is a stack layer), never through
its body text, and a link that cannot be read is unknown, never "no link". Declared guarded-element set: the eleven
below (one neutralization and one red each, no grouping). Every neutralization was a targeted edit made with the
Edit tool, undone by the inverse Edit before the next element, each Edit and each run in its own tool call. No `git
checkout`, `restore`, `reset` or `stash` was used. Command prefix for every run below (worktree root):
`timeout 900 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py -q -p no:cacheprovider -k "<selector>"`
(elements 6 and 7 name a second path argument in their entry). The selector is named in each entry; every selector
is the planned one, none was changed. Captures are raw pytest output with the `UV_NATIVE_TLS` warning line kept and
nothing redacted (temp paths only); each is under 32 KiB. Elements 1 and 4 shorten blocks that repeat word for
word, and say so in their entries. The red runs exit 1 by design (bite-proof reds, not failures). The production
sites cite this record with `# axis:` comments. The file is uncommitted, so the restore receipt is the restored text
quoted, from a `grep -n` over the restored line.

Disclosures:
- Element 7: an earlier run found the order's named red, `test_wave_watch_pr_old_resumed_2651.py`, passing under the
  neutralization. Its fixture was reworked in review, and the entry carries the refreshed red.
- Element 9: the `row6` fixture was extended after elements 1 to 8 were run, so test-file line numbers in those
  captures for tests after `row6` are 5 lower than in the final file (see the entry).

## 1. The re-key (`_attribute_pr_comments`, the re-keyed copy, `wave_watch.py:2572`)

- **Axis:** a note or ending on a pull request GitHub links to exactly one watched issue is re-keyed to that lane's issue and carries `prNumber`.
- **Neutralization:** `attributed.append(dict(comment, issue_url=issue_url, prNumber=number))` became `attributed.append(comment)`.
- **Raw red** (`-k "row1_a_handback or row2_a_builder"`; 4 red: the three `row1` parametrizations and `row2`). The second and third `row1` blocks repeat the first word for word with their own `kind`/`state`/temp path; they are shortened to one line each, about 2 KiB elided:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FFFF                                                                     [100%]
=================================== FAILURES ===================================
_ test_row1_a_handback_on_the_lanes_pr_is_lane_terminal_for_the_lane[handback-handback] _

repo = '/tmp/claude-0/pytest-of-root/pytest-35/test_row1_a_handback_on_the_la0/repo'
kind = 'handback', state = 'handback'

    @pytest.mark.parametrize("kind, state", [("handback", "handback"), ("stop", "stopped"), ("park", "parked")])
    def test_row1_a_handback_on_the_lanes_pr_is_lane_terminal_for_the_lane(repo, kind, state):
        # axis: every terminal kind (handback, stop, park) on the lane's own PR is the lane's ending
        _cloud_lane(repo, "cloud-a", 101)
        gh = _PrGh([_pr_comment(7, 501, _body(kind))], prs={501: _on_main(101)})
>       launch = _only_launch(_arm(repo, gh))
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:238: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': ['builder-note-unavailable'], ...}

    def _only_launch(result):
>       assert result["event"] == ww.EVENT_LANE_TERMINAL, result
E       AssertionError: {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': ['builder-note-unavailable'], ...}
E       assert 'timer' == 'lane-terminal'
E         
E         - lane-terminal
E         + timer

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:202: AssertionError
_ test_row1_a_handback_on_the_lanes_pr_is_lane_terminal_for_the_lane[stop-stopped] _
(the same failure, for kind 'stop')
_ test_row1_a_handback_on_the_lanes_pr_is_lane_terminal_for_the_lane[park-parked] _
(the same failure, for kind 'park')
__________ test_row2_a_builder_note_on_the_lanes_pr_is_the_lanes_note __________

repo = '/tmp/claude-0/pytest-of-root/pytest-35/test_row2_a_builder_note_on_th0/repo'

    def test_row2_a_builder_note_on_the_lanes_pr_is_the_lanes_note(repo):
        _cloud_lane(repo, "cloud-a", 101)
        gh = _PrGh([_pr_comment(7, 501)], prs={501: _on_main(101)})
        result = _arm(repo, gh)
>       assert result["event"] == ww.EVENT_BUILDER_NOTE
E       AssertionError: assert 'timer' == 'builder-note'
E         
E         - builder-note
E         + timer

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:255: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row1_a_handback_on_the_lanes_pr_is_lane_terminal_for_the_lane[handback-handback]
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row1_a_handback_on_the_lanes_pr_is_lane_terminal_for_the_lane[stop-stopped]
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row1_a_handback_on_the_lanes_pr_is_lane_terminal_for_the_lane[park-parked]
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row2_a_builder_note_on_the_lanes_pr_is_the_lanes_note
4 failed, 79 deselected in 1.43s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored lines, `        attributed.append(dict(comment, issue_url=issue_url, prNumber=number))` / `    return attributed, complete` (a `grep -n -B1 "return attributed, complete"` printed them at lines 2572 and 2573).
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
....                                                                     [100%]
4 passed, 79 deselected in 1.02s
```

## 2. Disclosure (`if not pr_complete:` body, `wave_watch.py:2690`)

- **Axis:** a note or ending on a pull request the watch could not attribute to one lane is disclosed as `builder-note-unavailable` and names every watched lane, never read as no note.
- **Neutralization:** `    if not pr_complete:` became `    if False and not pr_complete:`.
- **Raw red** (`-k "row5"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_row5_an_unreadable_pr_is_disclosed_and_names_the_lane __________

repo = '/tmp/claude-0/pytest-of-root/pytest-37/test_row5_an_unreadable_pr_is_0/repo'

    def test_row5_an_unreadable_pr_is_disclosed_and_names_the_lane(repo):
        _cloud_lane(repo, "cloud-a", 101)
        gh = _PrGh([_pr_comment(7, 501, _body("handback"))], prs={501: _on_main(101)}, fail_pulls={501})
>       _assert_disclosed_unread(ww.run(repo, _BATCH, gh_run=gh))

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:346: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': [], ...}
gh = None

    def _assert_disclosed_unread(result, gh=None):
        assert result["event"] != ww.EVENT_LANE_TERMINAL
>       assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]
E       AssertionError: assert 'builder-note-unavailable' in []
E        +  where 'builder-note-unavailable' = ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:339: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row5_an_unreadable_pr_is_disclosed_and_names_the_lane
1 failed, 82 deselected in 1.35s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `    if not pr_complete:` (a `grep -n -A1 "    if not pr_complete:\|if False"` printed only line 2690 and its axis comment; no `if False` remains in `wave_watch.py`).
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 82 deselected in 0.67s
```

## 3. Ambiguity (two or more watched hits, `_attribute_pr_comments`, `wave_watch.py:2561`)

- **Axis:** a pull request GitHub links to two or more watched issues is no lane's and is disclosed, never guessed onto one.
- **Neutralization:** `        if len(hits) >= 2:` became `        if len(hits) >= 3:` (two hits then fall through and are re-keyed to the lower issue).
- **Raw red** (`-k "row7"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_row7_a_pr_linked_to_two_watched_issues_is_no_lanes_and_is_disclosed ___

repo = '/tmp/claude-0/pytest-of-root/pytest-39/test_row7_a_pr_linked_to_two_w0/repo'

    def test_row7_a_pr_linked_to_two_watched_issues_is_no_lanes_and_is_disclosed(repo):
        _cloud_lane(repo, "cloud-a", 101)
        _cloud_lane(repo, "cloud-b", 102)
        gh = _PrGh([_pr_comment(7, 503, _body("handback"))], prs={503: _on_main(101, 102)})
        result = ww.run(repo, _BATCH, gh_run=gh)
>       assert result["event"] != ww.EVENT_LANE_TERMINAL
E       AssertionError: assert 'lane-terminal' != 'lane-terminal'
E        +  where 'lane-terminal' = ww.EVENT_LANE_TERMINAL

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:531: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row7_a_pr_linked_to_two_watched_issues_is_no_lanes_and_is_disclosed
1 failed, 82 deselected in 0.72s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `        if len(hits) >= 2:` (a `grep -n "len(hits) >="` printed line 2561 only).
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 82 deselected in 0.85s
```

## 4. Kind filter (`_pr_candidate`, `wave_watch.py:2375`)

- **Axis:** only a builder note or a handback, stop or park is read onto a lane through its pull request; any other comment on one is no lane's.
- **Neutralization:** `        if not (body.lstrip().startswith(cb.NOTE_HEADER) or cb.terminal_kind(body) in _pr_attributed_kinds()):` became the same line with `if False and not (...)`.
- **Raw red** (`-k "row8"`; all 5 selected tests red). The second and third `free_form_text` blocks repeat the first word for word with their own `body` and temp path; they are shortened to one line each, about 1 KiB elided:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FFFFF                                                                    [100%]
=================================== FAILURES ===================================
____ test_row8_a_progress_comment_on_the_lanes_pr_is_not_the_lanes_progress ____

    def test_row8_a_progress_comment_on_the_lanes_pr_is_not_the_lanes_progress():
        lanes = _lanes({"cloud-a": (101, 600)})
        gh = _PrGh([_as_pr(_progress(9, 501, updated_age=100))], prs={501: _on_main(101)})
        progress_out = [None]
        _evaluate(lanes, gh, progress_out=progress_out)
>       assert progress_out[0] == {}
E       AssertionError: assert {'cloud-a': {... 'gate', ...}} == {}
E         
E         Left contains 1 more item:
E         {'cloud-a': {'commentId': 9,
E                      'expectedSeconds': 3600,
E                      'phase': 'gate',
E                      'updatedAt': '2026-11-26T16:29:25Z',
E                      'updatedEpoch': 1795710565.0}}
E         Use -v to get more diff

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:546: AssertionError
____ test_row8_a_handover_on_the_lanes_pr_does_not_end_a_stop_on_the_issue _____

repo = '/tmp/claude-0/pytest-of-root/pytest-41/test_row8_a_handover_on_the_la0/repo'

    def test_row8_a_handover_on_the_lanes_pr_does_not_end_a_stop_on_the_issue(repo):
        _cloud_lane(repo, "cloud-a", 101)
        comments = [
            _comment(5, 101, _body("stop"), age=200),
            _pr_comment(6, 501, cb.handover_text("a" * 40), age=100),
        ]
        gh = _PrGh(comments, prs={501: _on_main(101)})
>       launch = _only_launch(_arm(repo, gh))
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:557: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': ['builder-note-unavailable'], ...}

    def _only_launch(result):
>       assert result["event"] == ww.EVENT_LANE_TERMINAL, result
E       AssertionError: {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': ['builder-note-unavailable'], ...}
E       assert 'timer' == 'lane-terminal'
E         
E         - lane-terminal
E         + timer

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:202: AssertionError
_ test_row8_free_form_text_on_the_lanes_pr_is_no_lanes[Builder stop at intake. The Anchor did not resolve.] _

repo = '/tmp/claude-0/pytest-of-root/pytest-41/test_row8_free_form_text_on_th0/repo'
body = 'Builder stop at intake. The Anchor did not resolve.'

    @pytest.mark.parametrize("body", [
        "Builder stop at intake. The Anchor did not resolve.",
        "Here is my update.\n\n" + cb.HANDBACK_HEADER + "\n\nDone.",
        cb.REFUSAL_HEADER + "\n\nNo.",
    ])
    def test_row8_free_form_text_on_the_lanes_pr_is_no_lanes(repo, body):
        _cloud_lane(repo, "cloud-a", 101)
        gh = _PrGh([_pr_comment(7, 501, body)], prs={501: _on_main(101)})
        assert _arm(repo, gh)["event"] == ww.EVENT_TIMER
>       assert gh.pr_reads == []
E       assert [501, 501, 501] == []
E         
E         Left contains 3 more items, first extra item: 501
E         Use -v to get more diff

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:572: AssertionError
_ test_row8_free_form_text_on_the_lanes_pr_is_no_lanes[Here is my update.\n\nBuilder handback (cloud build).\n\nDone.] _
(the same failure, `assert [501, 501, 501] == []`)
_ test_row8_free_form_text_on_the_lanes_pr_is_no_lanes[Builder refusal (cloud build).\n\nNo.] _
(the same failure, `assert [501, 501, 501] == []`)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row8_a_progress_comment_on_the_lanes_pr_is_not_the_lanes_progress
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row8_a_handover_on_the_lanes_pr_does_not_end_a_stop_on_the_issue
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row8_free_form_text_on_the_lanes_pr_is_no_lanes[Builder stop at intake. The Anchor did not resolve.]
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row8_free_form_text_on_the_lanes_pr_is_no_lanes[Here is my update.\n\nBuilder handback (cloud build).\n\nDone.]
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row8_free_form_text_on_the_lanes_pr_is_no_lanes[Builder refusal (cloud build).\n\nNo.]
5 failed, 78 deselected in 1.29s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `        if not (body.lstrip().startswith(cb.NOTE_HEADER) or cb.terminal_kind(body) in _pr_attributed_kinds()):` (a `grep -n "cb.terminal_kind(body) in _pr_attributed_kinds\|if False"` printed line 2375 only).
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.....                                                                    [100%]
5 passed, 78 deselected in 1.13s
```

## 5. Close partial, per unsure lane (`close_kinds` excludes `uncertain`, `wave_watch.py:2730`)

- **Axis:** a lane a pull-request comment the watch could not attribute may belong to is read as on a partial comments read: its stored close only, nothing new stored for it (advisor ruling 584734b4ec02, option a).
- **Refreshed after the ruling** (head `2f63d9e` plus the narrowing, uncommitted at the run). The earlier neutralization (`complete = state and pr_complete`) no longer exists.
- **Neutralization:** `    close_kinds = {lid: value for lid, value in observed.items() if lid not in uncertain}` became `    close_kinds = {lid: value for lid, value in observed.items()}`.
- **Raw red** (`-k "row11"`; 4 red, 4 passing controls; the capture keeps each failure's assertion and error lines):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FF..FF..                                                                 [100%]
=================================== FAILURES ===================================
_____ test_row11_an_unresolved_pr_comment_stores_nothing_new_for_its_lane ______
>       assert closed_out[0] == {}
E       AssertionError: assert {'cloud-a': (..., 'handback')} == {}
______ test_row11_a_refused_graphql_read_stores_nothing_new_for_its_lane _______
>       assert closed_out[0] == {}
E       AssertionError: assert {'cloud-a': (..., 'handback')} == {}
___ test_row11_with_no_stored_close_an_unsure_lane_has_no_bound_and_says_so ____
>       assert [note["commentId"] for note in notes] == [9]
E       assert [] == [9]
_ test_row11_an_observed_park_is_not_a_close_while_a_pr_note_after_it_is_unread _
>       assert [(t["commentId"], t["kind"]) for t in terminals] == [(9, "stop")]
E       AssertionError: assert [(7, 'park')] == [(9, 'stop')]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row11_an_unresolved_pr_comment_stores_nothing_new_for_its_lane
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row11_a_refused_graphql_read_stores_nothing_new_for_its_lane
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row11_with_no_stored_close_an_unsure_lane_has_no_bound_and_says_so
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row11_an_observed_park_is_not_a_close_while_a_pr_note_after_it_is_unread
4 failed, 4 passed, 85 deselected in 1.27s
```

- **Restore:** inverse Edit. **Restore receipt:** a `grep -n` printed `2730:    close_kinds = {lid: value for lid, value in observed.items() if lid not in uncertain}` only.
- **Raw green** (`-k "row11 or stored_park_and_no_pr_candidate"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.........                                                                [100%]
9 passed, 84 deselected in 25.62s
```

## 6. PR-only candidate (`_pr_candidate`'s permalink check, `wave_watch.py:2371`)

- **Axis:** only a comment on a pull request (its `html_url` is a `/pull/<n>` page) is a candidate, so a plain issue's comment causes no read and no disclosure.
- **Neutralization:** `permalink[1] != "pull"` (inside `if permalink is None or permalink[1] != "pull" or permalink[2] != number or ...`) became `False`.
- **Raw red** (one run over both files, `-k "row9 or test_a_lane_with_no_numeric_started_ts_is_not_watched_and_the_rest_still_count"`; the two tests selected are both red):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FF                                                                       [100%]
=================================== FAILURES ===================================
____ test_row9_a_handback_on_a_plain_issue_causes_no_read_and_no_disclosure ____

repo = '/tmp/claude-0/pytest-of-root/pytest-45/test_row9_a_handback_on_a_plai0/repo'

    def test_row9_a_handback_on_a_plain_issue_causes_no_read_and_no_disclosure(repo):
        _cloud_lane(repo, "cloud-a", 101)
        # A plain issue's comment has an `/issues/` html_url; reading 777 would fail here, so a read would be disclosed.
        gh = _PrGh([_comment(7, 777, _body("handback"))], prs={777: _on_main(101)}, fail_pulls={777})
        result = ww.run(repo, _BATCH, gh_run=gh)
        assert result["event"] == ww.EVENT_TIMER
>       assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE not in result["degraded"]
E       AssertionError: assert 'builder-note-unavailable' not in ['builder-note-unavailable']
E        +  where 'builder-note-unavailable' = ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:290: AssertionError
_ test_a_lane_with_no_numeric_started_ts_is_not_watched_and_the_rest_still_count _

    def test_a_lane_with_no_numeric_started_ts_is_not_watched_and_the_rest_still_count():
        gh = _NoteGh([_comment(3, 5), _comment(4, 6)])
        cloud = {"place": ll.PLACE_CLOUD, "started": True}
        lanes = {
            "cloud-x": {**cloud, "issue": 5, "startedTs": None},
            "cloud-y": {**cloud, "issue": 6, "startedTs": time.time() - 3600},
        }
        degraded = set()
        notes = _evaluate_builder_notes(
            "/", lanes, deadline=100.0, env={}, gh_run=gh, monotonic=lambda: 0.0,
            degraded=degraded, note_state=[None], known_slug=_SLUG,
        )
        assert [note["launchId"] for note in notes] == ["cloud-y"]
>       assert degraded == set()
E       AssertionError: assert {'builder-note-unavailable'} == set()
E         
E         Extra items in the left set:
E         'builder-note-unavailable'
E         Use -v to get more diff

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_builder_note.py:243: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row9_a_handback_on_a_plain_issue_causes_no_read_and_no_disclosure
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_a_lane_with_no_numeric_started_ts_is_not_watched_and_the_rest_still_count
2 failed, 178 deselected in 1.01s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `        if permalink is None or permalink[1] != "pull" or permalink[2] != number or permalink[3] != comment["id"] \` (a `grep -n "permalink is None or\|or False or"` printed line 2371 only).
- **Raw green** (same command and selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..                                                                       [100%]
2 passed, 178 deselected in 1.06s
```

## 7. Issue-only lane (`hits[0] in issue_only`, `_attribute_pr_comments`, `wave_watch.py:2625`)

- **Axis:** a resumed lane read only from its own issue never takes a pull-request comment, whichever read returned it.
- **Neutralization:** `        if not hits or hits[0] in issue_only:` became `        if not hits:`.
- **Refreshed in review session 2, round 3** (head `40b5b01` plus the round-3 fix, uncommitted at the run). The earlier
  disclosure is resolved: the test role's `test_wave_watch_pr_old_resumed_2651.py` fixture no longer serves the retired
  `repos/<slug>/issues/501` body read. It answers the repository, pulls and GraphQL closing-references reads the watch
  makes, so PR 501 resolves to the old lane's issue 101 and the test asserts that read (`links.reads["graphql"] == [501]`).
  It now goes red under the neutralization, as the unit test does.
- **Raw red** (both files, `-k "issue_only or old_resumed"`; 2 red, 1 passing control):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F.F                                                                      [100%]
=================================== FAILURES ===================================
_ test_old_resumed_lane_stays_issue_only_when_another_lane_opens_the_shared_read _
>       assert result["event"] == ww.EVENT_TIMER, result
E       AssertionError: {'ok': True, 'event': 'lane-terminal', 'batchId': 'batch-cloud', 'degraded': [], ...}
E       assert 'lane-terminal' == 'timer'
plugins/superheroes/lib/tests/test_wave_watch_pr_old_resumed_2651.py:28: AssertionError
_ test_a_pr_linked_to_an_issue_only_lane_is_not_rekeyed_but_one_linked_to_a_live_lane_is _
>       assert "prNumber" not in out[0] and out[0]["issue_url"] == comments[0]["issue_url"]
E       AssertionError: assert ('prNumber' not in {'id': 7, 'html_url': 'https://github.com/owner/repo/pull/501#issuecomment-7', 'issue_url': 'https://api.github.com/repos/owner/repo/issues/101', 'created_at': '2026-11-26T18:10:03Z', ...})
plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:892: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_old_resumed_2651.py::test_old_resumed_lane_stays_issue_only_when_another_lane_opens_the_shared_read
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_a_pr_linked_to_an_issue_only_lane_is_not_rekeyed_but_one_linked_to_a_live_lane_is
2 failed, 1 passed, 94 deselected in 0.96s
```

  (The capture keeps each failure's assertion and error lines and drops the repeated test source above them.)
- **Restore:** inverse Edit. **Restore receipt:** a `grep -n "hits\[0\] in issue_only\|if not hits"` printed
  `2625:        if not hits or hits[0] in issue_only:` only.
- **Raw green** (same command and selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
...                                                                      [100%]
3 passed, 94 deselected in 1.54s
```

## 8. GitHub link only, default branch (the `closingIssuesReferences` read, `_closing_issue_links`, `wave_watch.py:2427`)

- **Axis:** a pull request based on the default branch belongs to a lane only through the closing issue references GitHub records (same-repository issues only), never through its body text.
- **Neutralization:** the function's final `    return tuple(sorted(linked))` became `    return tuple(sorted(watched_issues))` (every watched issue is returned for a default-base pull request).
- **Raw red** (`-k "github_links_are_empty"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_pr_whose_body_says_closes_but_whose_github_links_are_empty_names_no_lane _

repo = '/tmp/claude-0/pytest-of-root/pytest-49/test_a_pr_whose_body_says_clos0/repo'

    def test_a_pr_whose_body_says_closes_but_whose_github_links_are_empty_names_no_lane(repo):
        # axis: a default-branch PR belongs to a lane only through the closing issue references GitHub records, never through its body text
        _cloud_lane(repo, "cloud-a", 101)
        gh = _PrGh([_pr_comment(7, 501, _body("handback"))], prs={501: _on_main(body="Closes #101.\n\nThe work.")})
        result = ww.run(repo, _BATCH, gh_run=gh)
>       assert result["event"] == ww.EVENT_TIMER
E       AssertionError: assert 'lane-terminal' == 'timer'
E         
E         - timer
E         + lane-terminal

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:386: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_a_pr_whose_body_says_closes_but_whose_github_links_are_empty_names_no_lane
1 failed, 82 deselected in 0.86s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `    return tuple(sorted(linked))` (a `grep -n "return tuple(sorted("` printed line 2427 only).
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 82 deselected in 0.81s
```

## 9. Stack-layer timeline link (the cross-reference match, `_timeline_links`, `wave_watch.py:2450`)

- **Axis:** a stack layer (a pull request based on a branch other than the default) belongs to a lane only through a cross-reference on the lane's issue timeline whose source is this very pull request of this repository.
- **Neutralization:** `        if ref_number == number and full_name.lower() == slug.lower():` became `        if full_name.lower() == slug.lower():` (a cross-reference from any pull request of this repository counts).
- **Fixture note:** the first run of this neutralization showed `row6`'s fixture put a cross-reference only on the upper lane's timeline, so a number check could not bite. `row6` was extended before this red run: the lower layer's own pull request (501, closing 101) is now on 101's timeline too, as GitHub records it. That edit added 5 lines to the test file after `row6`, so the test-file line numbers in elements 3 to 7's red captures above (taken before it) are 5 lower than in the final file for tests after `row6`; the red runs themselves were taken against the code as quoted.
- **Raw red** (`-k "row6"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_row6_a_stack_upper_layers_pr_comment_is_the_upper_lanes_only _______

repo = '/tmp/claude-0/pytest-of-root/pytest-52/test_row6_a_stack_upper_layers0/repo'

    def test_row6_a_stack_upper_layers_pr_comment_is_the_upper_lanes_only(repo):
        _cloud_lane(repo, "cloud-lower", 101)
        _cloud_lane(repo, "cloud-upper", 102)
        # The lower layer's own pull request (501) is cross-referenced on 101's timeline; the upper layer's (502) only on 102's.
        gh = _PrGh(
            [_pr_comment(7, 502, _body("handback"))],
            prs={501: _on_main(101), 502: _stacked(102, body="Closes #101")},
        )
        result = _arm(repo, gh)
>       launch = _only_launch(result)
                 ^^^^^^^^^^^^^^^^^^^^

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:482: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': ['builder-note-unavailable'], ...}

    def _only_launch(result):
>       assert result["event"] == ww.EVENT_LANE_TERMINAL, result
E       AssertionError: {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': ['builder-note-unavailable'], ...}
E       assert 'timer' == 'lane-terminal'
E         
E         - lane-terminal
E         + timer

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:202: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row6_a_stack_upper_layers_pr_comment_is_the_upper_lanes_only
1 failed, 82 deselected in 0.84s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `        if ref_number == number and full_name.lower() == slug.lower():` (a `grep -n "ref_number == number\|full_name.lower()"` printed line 2450 only).
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 82 deselected in 0.63s
```

## 10. Unknown is disclosed (the GraphQL failure branch, `_closing_issue_links`, `wave_watch.py:2402`)

- **Axis:** a closing-references read that exits non-zero (the proxy's GraphQL refusal included) is unknown, never "no link": the candidate resolves to None and is disclosed, with no fallback to another read.
- **Neutralization:** `        raise _PrLinkUnknown("graphql exit %s" % proc.returncode)` became `        return ()` (the failure reads as "no link").
- **Raw red** (`-k "graphql_proxy_refusal"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_a_graphql_proxy_refusal_falls_back_to_nothing_else ____________

repo = '/tmp/claude-0/pytest-of-root/pytest-54/test_a_graphql_proxy_refusal_f0/repo'

    def test_a_graphql_proxy_refusal_falls_back_to_nothing_else(repo):
        _cloud_lane(repo, "cloud-a", 101)
        gh = _PrGh([_pr_comment(7, 501, _body("handback"))], prs={501: _on_main(101)}, graphql="refused")
>       _assert_disclosed_unread(ww.run(repo, _BATCH, gh_run=gh))

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:440: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': [], ...}
gh = None

    def _assert_disclosed_unread(result, gh=None):
        assert result["event"] != ww.EVENT_LANE_TERMINAL
>       assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]
E       AssertionError: assert 'builder-note-unavailable' in []
E        +  where 'builder-note-unavailable' = ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:339: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_a_graphql_proxy_refusal_falls_back_to_nothing_else
1 failed, 82 deselected in 1.51s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored lines, `    if proc.returncode != 0:` / `        raise _PrLinkUnknown("graphql exit %s" % proc.returncode)` (a `grep -n -B1 "graphql exit"` printed lines 2402 and 2403).
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 82 deselected in 0.62s
```


## 11. No crash on a failed comments read with a stored park (`uncertain` is one type, a set, `wave_watch.py`)

- **Axis:** a comments read that fails with a stored park and no pull-request candidate returns the normal degraded result, never `internal-error`.
- **Red without the fix:** the test was written first and run on head `2f63d9e`, where the no-candidate path left `uncertain` a `set()` and the cached-park check called `uncertain.get(...)`. The fix removes that check with the bound code (ruling 584734b4ec02), so `uncertain` is a set on every path.
- **Raw red** (on `2f63d9e`, `-k "stored_park_and_no_pr_candidate"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_failed_comments_read_with_a_stored_park_and_no_pr_candidate_is_a_normal_degraded_result _
>       assert result["ok"] is True, result
E       AssertionError: {'ok': False, 'reason': 'internal-error', 'batchId': 'batch-cloud', 'detail': 'AttributeError'}
E       assert False is True
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_a_failed_comments_read_with_a_stored_park_and_no_pr_candidate_is_a_normal_degraded_result
1 failed, 96 deselected in 0.87s
```

- **Green after the fix:** in the element 5 green run above (the selector includes it).
