# Bite-proof record: WO-2148-1 (#2148) the wave watch keeps watching a lane sent a fix order

Detector under proof: `plugins/superheroes/lib/tests/test_wave_watch_fix_order.py` (the relay tests in
`test_cloud_relay.py` are unit tests of `compose`/`fix_orders` and carry no neutralization of their own here).
Guarded code: `plugins/superheroes/lib/wave_watch.py` and `plugins/superheroes/lib/cloud_relay.py`.
Base: `c038b2ebf0285e88b8b14e5e9401f0ffa0645ca3`. Every neutralization was a targeted edit made with the Edit
tool, undone by the inverse Edit before the next element. No `git checkout`, `restore`, `reset` or `stash`
was used. Command prefix for every run below (worktree root):
`scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_wave_watch_fix_order.py -q -k <selector>`.
Nothing in the captures was redacted (temp paths only); each is under 32 KiB. The selector differs per run and is
named in each entry. The production sites cite this record with `# axis:` comments.

Disclosures:
- Element 1's selector `row1` is a substring match, so it also selected the three `row10_` tests (6 selected:
  4 red, 2 passing). The `row10_an_unreadable_relay_state...` test uses a `vet not-ready` opener and is among
  the reds; the two passing ones (`row10_the_relay_is_not_read...`, `row10_a_local_lane...`) never depend on
  it. The green run used the same selector.
- Element 6's neutralization leaves the first half of its test (the closing handback surfaces) green; the red is
  the second half, a note after the close surfacing.
- Each restore receipt below is the inverse edit's text, quoted. Element 1's green run also carried a
  `grep -n` of the restored line in the same shell call (the output's first line).

## 1. Opener `vet not-ready` (`_reopen_candidate`, `wave_watch.py`)

- **Axis:** a `vet not-ready` amendment is a fix order and re-opens a handed-back cloud lane.
- **Neutralization:** `elif kind == "vet" and value == "not-ready" and (opener is None or ts > opener[0]):` became
  `... value == "never-ready" ...` (no amendment opens).
- **Raw red** (`-k row1`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FFFF..                                                                   [100%]
=================================== FAILURES ===================================
________ test_row1_a_note_after_a_fix_order_surfaces_as_a_builder_note _________

repo = '/tmp/claude-0/pytest-of-root/pytest-2/test_row1_a_note_after_a_fix_o0/repo'

    def test_row1_a_note_after_a_fix_order_surfaces_as_a_builder_note(repo):
        _reopened(repo)
        result = _arm(repo, _NoteGh([_later(7)]))
>       assert result["event"] == ww.EVENT_BUILDER_NOTE
E       AssertionError: assert 'timer' == 'builder-note'
E         
E         - builder-note
E         + timer

/home/user/wt-2148/plugins/superheroes/lib/tests/test_wave_watch_fix_order.py:95: AssertionError
__________ test_row1_a_park_after_a_fix_order_is_lane_terminal_parked __________

repo = '/tmp/claude-0/pytest-of-root/pytest-2/test_row1_a_park_after_a_fix_o0/repo'

    def test_row1_a_park_after_a_fix_order_is_lane_terminal_parked(repo):
        _reopened(repo)
>       launch = _only_launch(_arm(repo, _NoteGh([_later(7, _ending("park"))])))
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2148/plugins/superheroes/lib/tests/test_wave_watch_fix_order.py:102: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': []}

    def _only_launch(result):
>       assert result["event"] == ww.EVENT_LANE_TERMINAL, result
E       AssertionError: {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': []}
E       assert 'timer' == 'lane-terminal'
E         
E         - lane-terminal
E         + timer

/home/user/wt-2148/plugins/superheroes/lib/tests/test_wave_watch_fix_order.py:58: AssertionError
_______ test_row1_a_handback_after_a_fix_order_is_lane_terminal_handback _______

repo = '/tmp/claude-0/pytest-of-root/pytest-2/test_row1_a_handback_after_a_f0/repo'

    def test_row1_a_handback_after_a_fix_order_is_lane_terminal_handback(repo):
        _reopened(repo)
>       launch = _only_launch(_arm(repo, _NoteGh([_later(7, _ending("handback"))])))
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2148/plugins/superheroes/lib/tests/test_wave_watch_fix_order.py:108: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': []}

    def _only_launch(result):
>       assert result["event"] == ww.EVENT_LANE_TERMINAL, result
E       AssertionError: {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': []}
E       assert 'timer' == 'lane-terminal'
E         
E         - lane-terminal
E         + timer

/home/user/wt-2148/plugins/superheroes/lib/tests/test_wave_watch_fix_order.py:58: AssertionError
_ test_row10_an_unreadable_relay_state_is_disclosed_and_the_ledger_opener_still_works _

repo = '/tmp/claude-0/pytest-of-root/pytest-2/test_row10_an_unreadable_relay0/repo'

    def test_row10_an_unreadable_relay_state_is_disclosed_and_the_ledger_opener_still_works(repo):
        _reopened(repo)
        with open(_relay_path(repo), "w") as fh:
            fh.write("{not json")
        result = _arm(repo, _NoteGh([_later(7)]))
>       assert result["event"] == ww.EVENT_BUILDER_NOTE
E       AssertionError: assert 'timer' == 'builder-note'
E         
E         - builder-note
E         + timer

/home/user/wt-2148/plugins/superheroes/lib/tests/test_wave_watch_fix_order.py:334: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_fix_order.py::test_row1_a_note_after_a_fix_order_surfaces_as_a_builder_note
FAILED plugins/superheroes/lib/tests/test_wave_watch_fix_order.py::test_row1_a_park_after_a_fix_order_is_lane_terminal_parked
FAILED plugins/superheroes/lib/tests/test_wave_watch_fix_order.py::test_row1_a_handback_after_a_fix_order_is_lane_terminal_handback
FAILED plugins/superheroes/lib/tests/test_wave_watch_fix_order.py::test_row10_an_unreadable_relay_state_is_disclosed_and_the_ledger_opener_still_works
4 failed, 2 passed, 29 deselected in 1.86s
```

- **Restore:** inverse Edit. **Restore receipt** (the restored line, shown by the `grep -n` in the green call):
  `645:        elif kind == "vet" and value == "not-ready" and (opener is None or ts > opener[0]):`
- **Raw green** (`-k row1`; the first line of the call's output was that grep line):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
......                                                                   [100%]
6 passed, 29 deselected in 2.47s
```

## 2. Opener: a fix-order relay record (`_derive_batch_lanes`, `wave_watch.py`)

- **Axis:** a delivered fix-order relay record for the lane's session re-opens it like `not-ready`.
- **Neutralization:** `relay_times = _fix_order_times(repo_root, env, degraded)` became `relay_times = {}`.
- **Raw red** (`-k row7_a_delivered_fix_order_relay`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_row7_a_delivered_fix_order_relay_re_opens_the_lane ____________

repo = '/tmp/claude-0/pytest-of-root/pytest-4/test_row7_a_delivered_fix_orde0/repo'

    def test_row7_a_delivered_fix_order_relay_re_opens_the_lane(repo):
        _handed_back(repo)
        _relay(repo, _delivered())
        result = _arm(repo, _NoteGh([_later(7)]))
>       assert result["event"] == ww.EVENT_BUILDER_NOTE
E       AssertionError: assert 'timer' == 'builder-note'
E         
E         - builder-note
E         + timer

/home/user/wt-2148/plugins/superheroes/lib/tests/test_wave_watch_fix_order.py:212: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_fix_order.py::test_row7_a_delivered_fix_order_relay_re_opens_the_lane
1 failed, 34 deselected in 2.07s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `        relay_times = _fix_order_times(repo_root, env, degraded)` (directly above `    for lid, info in terminal.items():`).
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 34 deselected in 0.76s
```

## 3. Relay decision filter (`fix_orders`, `cloud_relay.py`)

- **Axis:** only a fix order whose `check` decided delivered, or may have reached the builder, opens the watch; a draft (no decision) does not.
- **Neutralization:** the condition `isinstance(entry, dict) and entry.get("fixOrder") is True and isinstance(decision, dict) and (decision.get("delivered") is True or decision.get("reason") in _MAY_HAVE_REACHED)` became `isinstance(entry, dict) and entry.get("fixOrder") is True`, and `"at": decision.get("at")` became `"at": (decision or {}).get("at") or entry.get("sentAfter")` (a draft then carries its `sentAfter` stamp).
- **Raw red** (`-k row7_an_undecided_draft`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_row7_an_undecided_draft_does_not_re_open_the_lane ____________

repo = '/tmp/claude-0/pytest-of-root/pytest-6/test_row7_an_undecided_draft_d0/repo'

    def test_row7_an_undecided_draft_does_not_re_open_the_lane(repo):
        _handed_back(repo)
        _relay(repo, {"msgId": "m1", "fixOrder": True, "decision": None})
>       assert _arm(repo, _NoteGh([_later(7)]))["event"] == ww.EVENT_TIMER
E       AssertionError: assert 'builder-note' == 'timer'
E         
E         - timer
E         + builder-note

/home/user/wt-2148/plugins/superheroes/lib/tests/test_wave_watch_fix_order.py:226: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_fix_order.py::test_row7_an_undecided_draft_does_not_re_open_the_lane
1 failed, 34 deselected in 0.77s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored lines,
  `        if (isinstance(entry, dict) and entry.get("fixOrder") is True and isinstance(decision, dict)` /
  `                and (decision.get("delivered") is True or decision.get("reason") in _MAY_HAVE_REACHED)):` /
  `            records.append({"msgId": msg_id, "session": entry.get("session"),` /
  `                            "configDir": entry.get("configDir"), "at": decision.get("at")})`
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 34 deselected in 0.72s
```

## 4. Closer (`_reopen_candidate`, `wave_watch.py`)

- **Axis:** a later `reoutcome` amendment closes the fix order; the lane is not watched at all.
- **Neutralization:** `if kind == "reoutcome" or (kind == "vet" and value in _CLOSING_VETS):` became `if kind == "never-reoutcome" or ...`.
- **Raw red** (`-k row2_a_later_reoutcome`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_row2_a_later_reoutcome_closes_the_fix_order_and_the_lane_is_not_watched _

repo = '/tmp/claude-0/pytest-of-root/pytest-8/test_row2_a_later_reoutcome_cl0/repo'

    def test_row2_a_later_reoutcome_closes_the_fix_order_and_the_lane_is_not_watched(repo):
        _reopened(repo)
        assert ll.amend(repo, "cloud-a", "reoutcome", "handback", "re-handed back")["ok"] is True
        gh = _NoteGh([_later(7)])
>       assert _arm(repo, gh)["event"] == ww.EVENT_TIMER
E       AssertionError: assert 'builder-note' == 'timer'
E         
E         - timer
E         + builder-note

/home/user/wt-2148/plugins/superheroes/lib/tests/test_wave_watch_fix_order.py:133: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_fix_order.py::test_row2_a_later_reoutcome_closes_the_fix_order_and_the_lane_is_not_watched
1 failed, 34 deselected in 0.66s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `        if kind == "reoutcome" or (kind == "vet" and value in _CLOSING_VETS):`
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 34 deselected in 0.80s
```

## 5. Old-ending cutoff (`_cloud_terminals`, `wave_watch.py`)

- **Axis:** a reopened lane's ending comment created before its fix order is not its ending, with no fallback to it.
- **Neutralization:** in `_cloud_terminals`, `if not _in_window(watched[lid], created, closes.get(lid)):` became `if not _in_window({}, created, closes.get(lid)):` (the `reopenedAt` skip is dropped for endings; notes keep theirs).
- **Raw red** (`-k row4_the_old_handback`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_row4_the_old_handback_comment_does_not_re_fire_after_not_ready ______

repo = '/tmp/claude-0/pytest-of-root/pytest-10/test_row4_the_old_handback_com0/repo'

    def test_row4_the_old_handback_comment_does_not_re_fire_after_not_ready(repo):
        _reopened(repo)
        gh = _NoteGh([_comment(7, 101, _ending("handback"), age=600)])
>       assert _arm(repo, gh)["event"] == ww.EVENT_TIMER
E       AssertionError: assert 'lane-terminal' == 'timer'
E         
E         - timer
E         + lane-terminal

/home/user/wt-2148/plugins/superheroes/lib/tests/test_wave_watch_fix_order.py:161: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_fix_order.py::test_row4_the_old_handback_comment_does_not_re_fire_after_not_ready
1 failed, 34 deselected in 0.85s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `        if not _in_window(watched[lid], created, closes.get(lid)):`
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 34 deselected in 0.79s
```

## 6. The close on the first ending (`_cloud_closes`, `wave_watch.py`)

- **Axis:** a reopened lane's first non-superseded ending closes it: a note after it is not surfaced and the lane is never stale.
- **Neutralization:** in `_cloud_closes`, `if not reopened:` became `if not reopened or True:` (no close is ever found).
- **Raw red** (`-k row2_after_the_closing_handback`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_row2_after_the_closing_handback_a_later_note_is_not_surfaced_and_the_lane_is_not_stale _

repo = '/tmp/claude-0/pytest-of-root/pytest-12/test_row2_after_the_closing_ha0/repo'

    def test_row2_after_the_closing_handback_a_later_note_is_not_surfaced_and_the_lane_is_not_stale(repo):
        _reopened(repo, start_age=_LONG_AGO)
        # The progress comment is future-dated, so a watched lane would read stale on it at once.
        gh = _ProgressGh([
            _later(5, _ending("handback"), secs=10), _later(6, secs=20),
            _progress(9, 101, updated_age=-3000, created_age=3000),
        ])
        # One tick, so the comments read is complete: a tick that cannot read knows no close.
        assert _only_launch(ww.run(repo, _BATCH, gh_run=gh))["commentId"] == 5
        assert _note_answered(repo, 5)["ok"] is True
>       assert ww.run(repo, _BATCH, gh_run=gh)["event"] == ww.EVENT_TIMER
E       AssertionError: assert 'builder-note' == 'timer'
E         
E         - timer
E         + builder-note

/home/user/wt-2148/plugins/superheroes/lib/tests/test_wave_watch_fix_order.py:126: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_fix_order.py::test_row2_after_the_closing_handback_a_later_note_is_not_surfaced_and_the_lane_is_not_stale
1 failed, 34 deselected in 0.71s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored lines, `    if not reopened:` / `        return {}`
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 34 deselected in 0.76s
```

## 7. Progress stale floor (`_apply_cloud_progress`, `wave_watch.py`)

- **Axis:** a reopened lane's progress comment ages from the fix order, not from its last edit before it.
- **Neutralization:** `if _finite_number(decided[lid].get("reopenedAt")):` became `if False and _finite_number(decided[lid].get("reopenedAt")):`.
- **Raw red** (`-k row6_a_progress_comment`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_row6_a_progress_comment_last_edited_before_the_fix_order_is_not_stale __

repo = '/tmp/claude-0/pytest-of-root/pytest-14/test_row6_a_progress_comment_l0/repo'

    def test_row6_a_progress_comment_last_edited_before_the_fix_order_is_not_stale(repo):
        _reopened(repo, start_age=_LONG_AGO)
        gh = _ProgressGh([_progress(7, 101, updated_age=_EXPECTED_60 + _WINDOW + 3600)])
        result = _arm(repo, gh)
>       assert result["event"] == ww.EVENT_TIMER
E       AssertionError: assert 'lane-stale' == 'timer'
E         
E         - timer
E         + lane-stale

/home/user/wt-2148/plugins/superheroes/lib/tests/test_wave_watch_fix_order.py:193: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_fix_order.py::test_row6_a_progress_comment_last_edited_before_the_fix_order_is_not_stale
1 failed, 34 deselected in 0.75s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `        if _finite_number(decided[lid].get("reopenedAt")):`
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 34 deselected in 0.99s
```

## 8. `unreadIssues` (`_record_unread`, `wave_watch.py`)

- **Axis:** a comments read that did not complete names every watched issue it may have left unread.
- **Neutralization:** in `_record_unread`, `if unread_out is not None:` became `if False and unread_out is not None:`.
- **WO-2148-2 update:** the axis now reads "a request that came back partial" (the `since` failure and
  `state is None` calls are gone; see WO-2148-2 element 3). The neutralization is unchanged and still silences
  the partial-read tests below; none of those tests changed. The captures below are WO-2148-1's and were not
  re-run (WO-2148-2's budget covers its four new elements). `-k row9` now also selects the new no-request test,
  which passes under this neutralization (it asserts the key is absent).
- **Raw red** (`-k row9`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FFF.F                                                                    [100%]
=================================== FAILURES ===================================
______________ test_row9_a_partial_read_names_every_watched_issue ______________

repo = '/tmp/claude-0/pytest-of-root/pytest-16/test_row9_a_partial_read_names0/repo'

    def test_row9_a_partial_read_names_every_watched_issue(repo):
        _reopened(repo)
        _cloud_lane(repo, "cloud-b", 202)
        result = _arm(repo, _NoteGh(script=_two_pages_then_failure()))
        assert result["event"] == ww.EVENT_TIMER
        assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]
>       assert result["unreadIssues"] == _UNREAD
               ^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'unreadIssues'

/home/user/wt-2148/plugins/superheroes/lib/tests/test_wave_watch_fix_order.py:290: KeyError
_____________ test_row9_a_single_tick_names_the_unread_issues_too ______________

repo = '/tmp/claude-0/pytest-of-root/pytest-16/test_row9_a_single_tick_names_0/repo'

    def test_row9_a_single_tick_names_the_unread_issues_too(repo):
        _reopened(repo)
        _cloud_lane(repo, "cloud-b", 202)
        result = ww.run(repo, _BATCH, gh_run=_NoteGh(script=_two_pages_then_failure()))
>       assert result["unreadIssues"] == _UNREAD
               ^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'unreadIssues'

/home/user/wt-2148/plugins/superheroes/lib/tests/test_wave_watch_fix_order.py:297: KeyError
_____ test_row9_an_event_found_on_a_partial_read_carries_the_unread_issues _____

repo = '/tmp/claude-0/pytest-of-root/pytest-16/test_row9_an_event_found_on_a_0/repo'

    def test_row9_an_event_found_on_a_partial_read_carries_the_unread_issues(repo):
        _reopened(repo)
        page_one = lambda argv: _ok(argv, [_later(7)], link=True)  # noqa: E731
        result = ww.run(repo, _BATCH, gh_run=_NoteGh(script=[page_one, _two_pages_then_failure()[1]]))
        assert result["event"] == ww.EVENT_BUILDER_NOTE
>       assert result["unreadIssues"] == [{"launchId": "cloud-a", "issue": 101}]
               ^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'unreadIssues'

/home/user/wt-2148/plugins/superheroes/lib/tests/test_wave_watch_fix_order.py:305: KeyError
_ test_row9_a_lane_named_unread_in_an_arm_stays_named_in_the_loop_ceiling_timer _

repo = '/tmp/claude-0/pytest-of-root/pytest-16/test_row9_a_lane_named_unread_0/repo'

    def test_row9_a_lane_named_unread_in_an_arm_stays_named_in_the_loop_ceiling_timer(repo):
        _reopened(repo)
        result = ww.loop(
            repo, _BATCH, max_seconds=2, interval_seconds=1, max_total_seconds=3,
            gh_run=_NoteGh(script=_two_pages_then_failure()),
        )
        assert result["event"] == ww.EVENT_TIMER
>       assert result["unreadIssues"] == [{"launchId": "cloud-a", "issue": 101}]
               ^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'unreadIssues'

/home/user/wt-2148/plugins/superheroes/lib/tests/test_wave_watch_fix_order.py:323: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_fix_order.py::test_row9_a_partial_read_names_every_watched_issue
FAILED plugins/superheroes/lib/tests/test_wave_watch_fix_order.py::test_row9_a_single_tick_names_the_unread_issues_too
FAILED plugins/superheroes/lib/tests/test_wave_watch_fix_order.py::test_row9_an_event_found_on_a_partial_read_carries_the_unread_issues
FAILED plugins/superheroes/lib/tests/test_wave_watch_fix_order.py::test_row9_a_lane_named_unread_in_an_arm_stays_named_in_the_loop_ceiling_timer
4 failed, 1 passed, 30 deselected in 1.79s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `    if unread_out is not None:`
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.....                                                                    [100%]
5 passed, 30 deselected in 1.77s
```

## 9. `fix-order-unavailable` (`_fix_order_times`, `wave_watch.py`)

- **Axis:** an unreadable relay state is disclosed, never a silent "no fix order".
- **Neutralization:** `degraded.add(DEGRADATION_FIX_ORDER_UNAVAILABLE)  # axis: ...` became `pass  # axis: ...`.
- **Raw red** (`-k row10_an_unreadable`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_row10_an_unreadable_relay_state_is_disclosed_and_the_ledger_opener_still_works _

repo = '/tmp/claude-0/pytest-of-root/pytest-18/test_row10_an_unreadable_relay0/repo'

    def test_row10_an_unreadable_relay_state_is_disclosed_and_the_ledger_opener_still_works(repo):
        _reopened(repo)
        with open(_relay_path(repo), "w") as fh:
            fh.write("{not json")
        result = _arm(repo, _NoteGh([_later(7)]))
        assert result["event"] == ww.EVENT_BUILDER_NOTE
>       assert ww.DEGRADATION_FIX_ORDER_UNAVAILABLE in result["degraded"]
E       AssertionError: assert 'fix-order-unavailable' in []
E        +  where 'fix-order-unavailable' = ww.DEGRADATION_FIX_ORDER_UNAVAILABLE

/home/user/wt-2148/plugins/superheroes/lib/tests/test_wave_watch_fix_order.py:335: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_fix_order.py::test_row10_an_unreadable_relay_state_is_disclosed_and_the_ledger_opener_still_works
1 failed, 34 deselected in 0.67s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored text, `        degraded.add(DEGRADATION_FIX_ORDER_UNAVAILABLE)  # axis:`
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 34 deselected in 0.75s
```

## 10. Cloud-only (`_reopen_candidate`, `wave_watch.py`)

- **Axis:** a local lane with a handback and `vet not-ready` is never re-added (its pid is gone: it would fire `builder-exited` at once).
- **Neutralization:** `if not (info.get("place") == ll.PLACE_CLOUD and info.get("started") and info.get("terminal")` became `if not (info.get("started") and info.get("terminal")`. (`_derive_batch_lanes` does not pre-filter candidates by place, so the helper's check is the one chokepoint and the neutralization bites.)
- **Raw red** (`-k row10_a_local_lane`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_row10_a_local_lane_with_a_handback_is_never_re_opened_by_not_ready ____

repo = '/tmp/claude-0/pytest-of-root/pytest-20/test_row10_a_local_lane_with_a0/repo'

    def test_row10_a_local_lane_with_a_handback_is_never_re_opened_by_not_ready(repo):
        _add_local_lane(repo, "local-a", 55, pid=999999999)
        assert ll.record_outcome(repo, "local-a", "handback", "built")["ok"] is True
        assert ll.amend(repo, "local-a", "vet", "not-ready", "needs a fix")["ok"] is True
        result = ww.run(repo, _BATCH, gh_run=_NoteGh())
>       assert result["event"] == ww.EVENT_TIMER
E       AssertionError: assert 'builder-exited' == 'timer'
E         
E         - timer
E         + builder-exited

/home/user/wt-2148/plugins/superheroes/lib/tests/test_wave_watch_fix_order.py:351: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_fix_order.py::test_row10_a_local_lane_with_a_handback_is_never_re_opened_by_not_ready
1 failed, 34 deselected in 0.69s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `    if not (info.get("place") == ll.PLACE_CLOUD and info.get("started") and info.get("terminal")`
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 34 deselected in 0.64s
```

# Bite-proof record: WO-2148-2 (#2148) a closed re-watched lane's close, and `unreadIssues`

Detector under proof: `plugins/superheroes/lib/tests/test_wave_watch_fix_order.py` (four tests added: the three
`row2_*` tests with `closed`/`stored close`/`partial read` in their names, and `row9_a_tick_that_made_no_request...`).
Guarded code: `plugins/superheroes/lib/wave_watch.py`. Base: WO-2148-1's head `8af8f8c8`. Declared guarded-element
set: the four below. Every neutralization was a targeted Edit, undone by the inverse Edit before the next element;
no `git checkout`, `restore`, `reset` or `stash`. Same command prefix as above, with the single test as the selector.
Nothing in the captures was redacted (temp paths only); each is under 32 KiB. The production sites cite this record
with `# axis:` comments. The red runs exit 1 by design (bite-proof reds, not failures).

## WO-2148-2 element 1. Stored-close reuse on a tick with no complete read (`_evaluate_tick`, `wave_watch.py`)

- **Axis:** a re-watched lane the last complete read showed closed stays closed on a later tick that has no complete read.
- **Neutralization:** `stored = closed_state[0] if closed_state is not None else None` became `stored = None` (the stored map is ignored).
- **Raw red** (`-k test_row2_a_closed_lane_stays_closed_on_a_tick_that_makes_no_comments_read`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_row2_a_closed_lane_stays_closed_on_a_tick_that_makes_no_comments_read __

repo = '/tmp/claude-0/pytest-of-root/pytest-24/test_row2_a_closed_lane_stays_0/repo'

    def test_row2_a_closed_lane_stays_closed_on_a_tick_that_makes_no_comments_read(repo):
        # The arm reads on its ticks at 0, 1 and 2 seconds; the tick at its 3-second deadline has no budget.
        result = _arm(repo, _ProgressGh(_closed_by_a_handback(repo)))
>       assert result["event"] == ww.EVENT_TIMER
E       AssertionError: assert 'lane-stale' == 'timer'
E         
E         - timer
E         + lane-stale

/home/user/wt-2148/plugins/superheroes/lib/tests/test_wave_watch_fix_order.py:140: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_fix_order.py::test_row2_a_closed_lane_stays_closed_on_a_tick_that_makes_no_comments_read
1 failed, 38 deselected in 0.89s
```

- **Restore:** inverse Edit. **Restore receipt:** `grep -n` of the restored line, `2934:            stored = closed_state[0] if closed_state is not None else None`
- **Raw green** (same selector; the `grep` line above is the same shell call's first output):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 38 deselected in 7.15s
```

## WO-2148-2 element 2. Stored close keyed by `reopenedAt` (`_evaluate_tick`, `wave_watch.py`)

- **Axis:** a newer opener (a different `reopenedAt`) discards a lane's stored close.
- **Neutralization:** `if lid in live_lanes and live_lanes[lid].get("reopenedAt") == at` became `if lid in live_lanes` (stored closes apply whatever the `reopenedAt`).
- **Raw red** (`-k test_row2_a_stored_close_does_not_outlive_a_newer_fix_order`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_row2_a_stored_close_does_not_outlive_a_newer_fix_order __________

repo = '/tmp/claude-0/pytest-of-root/pytest-26/test_row2_a_stored_close_does_0/repo'
clock = <test_wave_watch_cloud._Clock object at 0x7fc89f5b20f0>

    def test_row2_a_stored_close_does_not_outlive_a_newer_fix_order(repo, clock):
        _handed_back(repo, start_age=_LONG_AGO)
        _amend_at(repo, "cloud-a", "not-ready", 1000)
        assert _note_answered(repo, 5)["ok"] is True
        gh = _ProgressGh([_comment(5, 101, _ending("handback"), age=500),
                          _progress(9, 101, updated_age=-3000, created_age=3000)])
    
        def sleep(duration):
            clock.sleep(duration)
            if clock.now >= 3:  # a second fix order lands before the deadline tick, which makes no read
                _fix_order(repo)
    
        result = _arm(repo, gh, sleep=sleep)
>       assert result["event"] == ww.EVENT_LANE_STALE
E       AssertionError: assert 'timer' == 'lane-stale'
E         
E         - lane-stale
E         + timer

/home/user/wt-2148/plugins/superheroes/lib/tests/test_wave_watch_fix_order.py:157: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_fix_order.py::test_row2_a_stored_close_does_not_outlive_a_newer_fix_order
1 failed, 38 deselected in 1.26s
```

- **Restore:** inverse Edit. **Restore receipt:** `grep -n` of the restored line, `2938:                if lid in live_lanes and live_lanes[lid].get("reopenedAt") == at`
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 38 deselected in 0.76s
```

## WO-2148-2 element 3. `unreadIssues` only on a partial read (`_evaluate_cloud_comments`, `wave_watch.py`)

- **Axis:** `unreadIssues` names watched lanes' issues only when a comments request was made and came back partial; a tick that made no request adds nothing (its `builder-note-unavailable` disclosure is unchanged).
- **Neutralization:** `_record_unread(unread_out, watched)` restored in the `if state is None:` branch, before its `return [], []`.
- **Raw red** (`-k test_row9_a_tick_that_made_no_request_discloses_it_and_names_no_unread_issue`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_row9_a_tick_that_made_no_request_discloses_it_and_names_no_unread_issue _

repo = '/tmp/claude-0/pytest-of-root/pytest-28/test_row9_a_tick_that_made_no_0/repo'

    def test_row9_a_tick_that_made_no_request_discloses_it_and_names_no_unread_issue(repo):
        _reopened(repo)
        result = _arm(repo, _NoteGh([]))  # the deadline tick has no budget to read
        assert result["event"] == ww.EVENT_TIMER
        assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]
>       assert "unreadIssues" not in result
E       AssertionError: assert 'unreadIssues' not in {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': ['builder-note-unavailable'], ...}

/home/user/wt-2148/plugins/superheroes/lib/tests/test_wave_watch_fix_order.py:366: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_fix_order.py::test_row9_a_tick_that_made_no_request_discloses_it_and_names_no_unread_issue
1 failed, 38 deselected in 0.76s
```

- **Restore:** inverse Edit (the call removed again). **Restore receipt:** `sed -n 1986,2004p` of the restored region, showing `if state is None:` / the disclosure comment / `degraded.add(DEGRADATION_BUILDER_NOTE_UNAVAILABLE)` / `return [], []` with no `_record_unread` between them, and the call still under `if not state:`.
- **Raw green** (same selector; the `sed` output above is the same shell call's first output):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 38 deselected in 0.84s
```

## WO-2148-2 element 4. The `closed_out` slot is written only on a complete read (`_evaluate_cloud_comments`, `wave_watch.py`)

- **Axis:** a partial read leaves the closed slot as the caller set it, so it is never taken for a complete read with no closes.
- **Neutralization:** `if state and isinstance(closed_out, list) and closed_out:` became `if isinstance(closed_out, list) and closed_out:`.
- **Raw red** (`-k test_row2_a_partial_read_keeps_the_close_a_complete_read_showed`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_row2_a_partial_read_keeps_the_close_a_complete_read_showed ________

repo = '/tmp/claude-0/pytest-of-root/pytest-30/test_row2_a_partial_read_keeps0/repo'

    def test_row2_a_partial_read_keeps_the_close_a_complete_read_showed(repo):
        comments = _closed_by_a_handback(repo)
        gh = _ProgressGh(comments, script=[
            lambda argv: _ok(argv, comments),
            lambda argv: _ok(argv, comments, link=True),
            lambda argv: _raw(argv, "HTTP/2.0 502 Bad Gateway\r\n\r\n"),
        ])
        # Ticks at 0 (complete), 1 (partial) and 2 seconds (the deadline: no read).
        result = ww.watch_arm(repo, _BATCH, max_seconds=2, interval_seconds=1, gh_run=gh)
>       assert result["event"] == ww.EVENT_TIMER
E       AssertionError: assert 'lane-stale' == 'timer'
E         
E         - timer
E         + lane-stale

/home/user/wt-2148/plugins/superheroes/lib/tests/test_wave_watch_fix_order.py:170: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_fix_order.py::test_row2_a_partial_read_keeps_the_close_a_complete_read_showed
1 failed, 38 deselected in 0.72s
```

- **Restore:** inverse Edit. **Restore receipt:** `grep -n` of the restored line, `2007:    if state and isinstance(closed_out, list) and closed_out:`
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 38 deselected in 0.76s
```
