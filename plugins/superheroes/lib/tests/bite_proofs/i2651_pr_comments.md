# Bite-proof record: #2651 the wave watch attributes a builder note or cloud terminal comment on a watched lane's own PR to that lane

Detector under proof: `plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py`.
Guarded code: `plugins/superheroes/lib/wave_watch.py`.
Base: `7d10cb4ee5eac77aaf78ba7bc274f403f6b40cd1`. Declared guarded-element set: the five below (one neutralization
and one red each, no grouping). Every neutralization was a targeted edit made with the Edit tool, undone by the
inverse Edit before the next element, each Edit and each run in its own tool call. No `git checkout`, `restore`,
`reset` or `stash` was used. Command prefix for every run below (worktree root):
`timeout 900 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py -q -p no:cacheprovider -k "<selector>"`.
The selector differs per run and is named in each entry; every selector is the planned one, none was changed.
Captures are raw pytest output, nothing trimmed (the `UV_NATIVE_TLS` warning line is kept) and nothing redacted
(temp paths only); each is under 32 KiB. The red runs exit 1 by design (bite-proof reds, not failures). The
production sites cite this record with `# axis:` comments. The file is uncommitted and already differs from the
base, so the restore receipt is the restored text quoted plus `git diff --stat -- plugins/superheroes/lib/wave_watch.py`
taken before any neutralization and after each restore: every one printed the same
`1 file changed, 149 insertions(+), 6 deletions(-)` (155 lines changed).

Disclosures:
- Element 4's selector `row8` selects 5 tests (the progress-comment test, the handover test, and the 3 free-form
  parametrizations); all 5 are red under the neutralization.
- Element 5's selector `row11` selects 3 tests: 2 are red; the control (`..._a_resolved_pr_comment_sets_the_closed_slot`)
  passes under this neutralization by design, so it does not discriminate it. The green run used the same selector.
- Element 2's red is rows 5 and 7; element 3's red is row 7 alone.
- The tests that assert a degradation use `ww.run` (one tick), not `watch_arm`: a multi-tick arm that ends on `timer`
  reports `builder-note-unavailable` on its last tick for want of budget with an issue-only comment too (observed on
  this tree, with a PR-free comment list), so the arm cannot show the absence of a disclosure.

## 1. The re-key (`_attribute_pr_comments`, `wave_watch.py:2440`)

- **Axis:** a note or ending on a pull request that closes exactly one watched issue is re-keyed to that lane's issue, so the lane's windows, answered record and park supersession read it.
- **Neutralization:** `attributed.append(dict(comment, issue_url=issue_url, prNumber=number))` (line 2440) became `attributed.append(comment)`.
- **Raw red** (`-k "row1_a or row2_a or row6_a"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FFF                                                                      [100%]
=================================== FAILURES ===================================
______ test_row1_a_handback_on_the_lanes_pr_is_lane_terminal_for_the_lane ______

repo = '/tmp/claude-0/pytest-of-root/pytest-3/test_row1_a_handback_on_the_la0/repo'

    def test_row1_a_handback_on_the_lanes_pr_is_lane_terminal_for_the_lane(repo):
        _cloud_lane(repo, "cloud-a", 101)
        gh = _PrGh([_comment(7, 501, _body("handback"))], prs={501: _pr(501, "Closes #101.\n\nThe work.")})
>       launch = _only_launch(_arm(repo, gh))
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:109: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': ['builder-note-unavailable'], ...}

    def _only_launch(result):
>       assert result["event"] == ww.EVENT_LANE_TERMINAL, result
E       AssertionError: {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': ['builder-note-unavailable'], ...}
E       assert 'timer' == 'lane-terminal'
E         
E         - lane-terminal
E         + timer

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:71: AssertionError
__________ test_row2_a_builder_note_on_the_lanes_pr_is_the_lanes_note __________

repo = '/tmp/claude-0/pytest-of-root/pytest-3/test_row2_a_builder_note_on_th0/repo'

    def test_row2_a_builder_note_on_the_lanes_pr_is_the_lanes_note(repo):
        _cloud_lane(repo, "cloud-a", 101)
        gh = _PrGh([_comment(7, 501)], prs={501: _pr(501, "Closes #101.\n\nThe work.")})
        result = _arm(repo, gh)
>       assert result["event"] == ww.EVENT_BUILDER_NOTE
E       AssertionError: assert 'timer' == 'builder-note'
E         
E         - builder-note
E         + timer

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:123: AssertionError
______ test_row6_a_stack_upper_layers_pr_comment_is_the_upper_lanes_only _______

repo = '/tmp/claude-0/pytest-of-root/pytest-3/test_row6_a_stack_upper_layers0/repo'

    def test_row6_a_stack_upper_layers_pr_comment_is_the_upper_lanes_only(repo):
        _cloud_lane(repo, "cloud-lower", 101)
        _cloud_lane(repo, "cloud-upper", 102)
        gh = _PrGh(
            [_comment(7, 502, _body("handback"))],
            prs={502: _pr(502, "Closes #102", base="layer-101-branch")},
        )
        result = _arm(repo, gh)
>       launch = _only_launch(result)
                 ^^^^^^^^^^^^^^^^^^^^

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:225: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': ['builder-note-unavailable'], ...}

    def _only_launch(result):
>       assert result["event"] == ww.EVENT_LANE_TERMINAL, result
E       AssertionError: {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': ['builder-note-unavailable'], ...}
E       assert 'timer' == 'lane-terminal'
E         
E         - lane-terminal
E         + timer

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:71: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row1_a_handback_on_the_lanes_pr_is_lane_terminal_for_the_lane
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row2_a_builder_note_on_the_lanes_pr_is_the_lanes_note
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row6_a_stack_upper_layers_pr_comment_is_the_upper_lanes_only
3 failed, 24 deselected in 1.30s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `            attributed.append(dict(comment, issue_url=issue_url, prNumber=number))` (directly under `issue_url = re.sub(...)`); `git diff --stat -- plugins/superheroes/lib/wave_watch.py` printed `155 ++++++++++++++++++++++++++++++++--` / `1 file changed, 149 insertions(+), 6 deletions(-)`, as before the neutralization.
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
...                                                                      [100%]
3 passed, 24 deselected in 1.09s
```

## 2. The disclosure (`_evaluate_cloud_comments`, `wave_watch.py:2558`)

- **Axis:** a note or ending on a pull request the watch could not attribute to one lane is disclosed (`builder-note-unavailable`) and names every watched lane, never read as "no note".
- **Neutralization:** the body of `if not pr_complete:` (`degraded.add(DEGRADATION_BUILDER_NOTE_UNAVAILABLE)` and `_record_unread(unread_out, watched)`, lines 2560-2561) became `pass`.
- **Raw red** (`-k "row5 or row7"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FF                                                                       [100%]
=================================== FAILURES ===================================
__________ test_row5_an_unreadable_pr_is_disclosed_and_names_the_lane __________

repo = '/tmp/claude-0/pytest-of-root/pytest-5/test_row5_an_unreadable_pr_is_0/repo'

    def test_row5_an_unreadable_pr_is_disclosed_and_names_the_lane(repo):
        _cloud_lane(repo, "cloud-a", 101)
        gh = _PrGh([_comment(7, 501, _body("handback"))], prs={501: _failed()})
        result = ww.run(repo, _BATCH, gh_run=gh)
        assert result["event"] != ww.EVENT_LANE_TERMINAL
>       assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]
E       AssertionError: assert 'builder-note-unavailable' in []
E        +  where 'builder-note-unavailable' = ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:184: AssertionError
____ test_row7_a_pr_closing_two_watched_issues_is_no_lanes_and_is_disclosed ____

repo = '/tmp/claude-0/pytest-of-root/pytest-5/test_row7_a_pr_closing_two_wat0/repo'

    def test_row7_a_pr_closing_two_watched_issues_is_no_lanes_and_is_disclosed(repo):
        _cloud_lane(repo, "cloud-a", 101)
        _cloud_lane(repo, "cloud-b", 102)
        gh = _PrGh([_comment(7, 503, _body("handback"))], prs={503: _pr(503, "Closes #101\nCloses #102")})
        result = ww.run(repo, _BATCH, gh_run=gh)
        assert result["event"] != ww.EVENT_LANE_TERMINAL
>       assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]
E       AssertionError: assert 'builder-note-unavailable' in []
E        +  where 'builder-note-unavailable' = ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:240: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row5_an_unreadable_pr_is_disclosed_and_names_the_lane
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row7_a_pr_closing_two_watched_issues_is_no_lanes_and_is_disclosed
2 failed, 25 deselected in 0.87s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored lines, `        degraded.add(DEGRADATION_BUILDER_NOTE_UNAVAILABLE)` / `        _record_unread(unread_out, watched)` (directly under the `# axis:` comment of `if not pr_complete:`); `git diff --stat` printed `1 file changed, 149 insertions(+), 6 deletions(-)`, as before.
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..                                                                       [100%]
2 passed, 25 deselected in 0.69s
```

## 3. The ambiguity rule (`_attribute_pr_comments`, `wave_watch.py:2437`)

- **Axis:** a pull request that closes two or more watched issues is no lane's and is disclosed, never guessed onto one.
- **Neutralization:** `if len(hits) == 1:` (line 2437) became `if len(hits) >= 1:` (two or more hits re-keyed to `hits[0]`).
- **Raw red** (`-k "row7"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_row7_a_pr_closing_two_watched_issues_is_no_lanes_and_is_disclosed ____

repo = '/tmp/claude-0/pytest-of-root/pytest-7/test_row7_a_pr_closing_two_wat0/repo'

    def test_row7_a_pr_closing_two_watched_issues_is_no_lanes_and_is_disclosed(repo):
        _cloud_lane(repo, "cloud-a", 101)
        _cloud_lane(repo, "cloud-b", 102)
        gh = _PrGh([_comment(7, 503, _body("handback"))], prs={503: _pr(503, "Closes #101\nCloses #102")})
        result = ww.run(repo, _BATCH, gh_run=gh)
>       assert result["event"] != ww.EVENT_LANE_TERMINAL
E       AssertionError: assert 'lane-terminal' != 'lane-terminal'
E        +  where 'lane-terminal' = ww.EVENT_LANE_TERMINAL

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:239: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row7_a_pr_closing_two_watched_issues_is_no_lanes_and_is_disclosed
1 failed, 26 deselected in 0.63s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `        if len(hits) == 1:`; `git diff --stat` printed `1 file changed, 149 insertions(+), 6 deletions(-)`, as before.
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 26 deselected in 0.62s
```

## 4. The kind filter (`_pr_candidate`, `wave_watch.py:2362`)

- **Axis:** only a builder note or a handback, stop or park is read onto a lane through its pull request; any other comment on one (progress, handover, free-form) is no lane's.
- **Neutralization:** `if not (body.lstrip().startswith(cb.NOTE_HEADER) or cb.terminal_kind(body) in _PR_ATTRIBUTED_KINDS):` (line 2362) became `if False and not (...same condition...):`, so any string body is a candidate.
- **Raw red** (`-k "row8"`; 5 red, see the disclosure above):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FFFFF                                                                    [100%]
=================================== FAILURES ===================================
____ test_row8_a_progress_comment_on_the_lanes_pr_is_not_the_lanes_progress ____

    def test_row8_a_progress_comment_on_the_lanes_pr_is_not_the_lanes_progress():
        lanes = _lanes({"cloud-a": (101, 600)})
        gh = _PrGh([_progress(9, 501, updated_age=100)], prs={501: _pr(501, "Closes #101.")})
        progress_out = [None]
        _evaluate(lanes, gh, progress_out=progress_out)
>       assert progress_out[0] == {}
E       AssertionError: assert {'cloud-a': {... 'gate', ...}} == {}
E         
E         Left contains 1 more item:
E         {'cloud-a': {'commentId': 9,
E                      'expectedSeconds': 3600,
E                      'phase': 'gate',
E                      'updatedAt': '2026-11-26T13:55:59Z',
E                      'updatedEpoch': 1795701359.0}}
E         Use -v to get more diff

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:254: AssertionError
_____ test_row8_a_handover_on_the_lanes_pr_does_not_end_a_stop_on_the_issue _____

repo = '/tmp/claude-0/pytest-of-root/pytest-9/test_row8_a_handover_on_the_la0/repo'

    def test_row8_a_handover_on_the_lanes_pr_does_not_end_a_stop_on_the_issue(repo):
        _cloud_lane(repo, "cloud-a", 101)
        comments = [
            _comment(5, 101, _body("stop"), age=200),
            _comment(6, 501, cb.handover_text("a" * 40), age=100),
        ]
        gh = _PrGh(comments, prs={501: _pr(501, "Closes #101.")})
>       launch = _only_launch(_arm(repo, gh))
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:265: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': ['builder-note-unavailable'], ...}

    def _only_launch(result):
>       assert result["event"] == ww.EVENT_LANE_TERMINAL, result
E       AssertionError: {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': ['builder-note-unavailable'], ...}
E       assert 'timer' == 'lane-terminal'
E         
E         - lane-terminal
E         + timer

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:71: AssertionError
_ test_row8_free_form_text_on_the_lanes_pr_is_no_lanes[Builder stop at intake. The Anchor did not resolve.] _

repo = '/tmp/claude-0/pytest-of-root/pytest-9/test_row8_free_form_text_on_th0/repo'
body = 'Builder stop at intake. The Anchor did not resolve.'

    @pytest.mark.parametrize("body", [
        "Builder stop at intake. The Anchor did not resolve.",
        "Here is my update.\n\n" + cb.HANDBACK_HEADER + "\n\nDone.",
        cb.REFUSAL_HEADER + "\n\nNo.",
    ])
    def test_row8_free_form_text_on_the_lanes_pr_is_no_lanes(repo, body):
        _cloud_lane(repo, "cloud-a", 101)
        gh = _PrGh([_comment(7, 501, body)], prs={501: _pr(501, "Closes #101.")})
        assert _arm(repo, gh)["event"] == ww.EVENT_TIMER
>       assert gh.pr_reads == []
E       assert [501, 501, 501] == []
E         
E         Left contains 3 more items, first extra item: 501
E         Use -v to get more diff

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:280: AssertionError
_ test_row8_free_form_text_on_the_lanes_pr_is_no_lanes[Here is my update.\n\nBuilder handback (cloud build).\n\nDone.] _

repo = '/tmp/claude-0/pytest-of-root/pytest-9/test_row8_free_form_text_on_th1/repo'
body = 'Here is my update.\n\nBuilder handback (cloud build).\n\nDone.'

    @pytest.mark.parametrize("body", [
        "Builder stop at intake. The Anchor did not resolve.",
        "Here is my update.\n\n" + cb.HANDBACK_HEADER + "\n\nDone.",
        cb.REFUSAL_HEADER + "\n\nNo.",
    ])
    def test_row8_free_form_text_on_the_lanes_pr_is_no_lanes(repo, body):
        _cloud_lane(repo, "cloud-a", 101)
        gh = _PrGh([_comment(7, 501, body)], prs={501: _pr(501, "Closes #101.")})
        assert _arm(repo, gh)["event"] == ww.EVENT_TIMER
>       assert gh.pr_reads == []
E       assert [501, 501, 501] == []
E         
E         Left contains 3 more items, first extra item: 501
E         Use -v to get more diff

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:280: AssertionError
_ test_row8_free_form_text_on_the_lanes_pr_is_no_lanes[Builder refusal (cloud build).\n\nNo.] _

repo = '/tmp/claude-0/pytest-of-root/pytest-9/test_row8_free_form_text_on_th2/repo'
body = 'Builder refusal (cloud build).\n\nNo.'

    @pytest.mark.parametrize("body", [
        "Builder stop at intake. The Anchor did not resolve.",
        "Here is my update.\n\n" + cb.HANDBACK_HEADER + "\n\nDone.",
        cb.REFUSAL_HEADER + "\n\nNo.",
    ])
    def test_row8_free_form_text_on_the_lanes_pr_is_no_lanes(repo, body):
        _cloud_lane(repo, "cloud-a", 101)
        gh = _PrGh([_comment(7, 501, body)], prs={501: _pr(501, "Closes #101.")})
        assert _arm(repo, gh)["event"] == ww.EVENT_TIMER
>       assert gh.pr_reads == []
E       assert [501, 501, 501] == []
E         
E         Left contains 3 more items, first extra item: 501
E         Use -v to get more diff

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:280: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row8_a_progress_comment_on_the_lanes_pr_is_not_the_lanes_progress
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row8_a_handover_on_the_lanes_pr_does_not_end_a_stop_on_the_issue
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row8_free_form_text_on_the_lanes_pr_is_no_lanes[Builder stop at intake. The Anchor did not resolve.]
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row8_free_form_text_on_the_lanes_pr_is_no_lanes[Here is my update.\n\nBuilder handback (cloud build).\n\nDone.]
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row8_free_form_text_on_the_lanes_pr_is_no_lanes[Builder refusal (cloud build).\n\nNo.]
5 failed, 22 deselected in 1.36s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `        if not (body.lstrip().startswith(cb.NOTE_HEADER) or cb.terminal_kind(body) in _PR_ATTRIBUTED_KINDS):`; `git diff --stat` printed `1 file changed, 149 insertions(+), 6 deletions(-)`, as before.
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.....                                                                    [100%]
5 passed, 22 deselected in 1.09s
```

## 5. The close bookkeeping (`_evaluate_cloud_comments`, `wave_watch.py:2571`)

- **Axis:** an incomplete pull-request attribution is a partial read: it neither replaces the known closes nor sets the closed slot.
- **Neutralization:** `complete = state and pr_complete` (line 2571) became `complete = state`.
- **Raw red** (`-k "row11"`; 2 red, 1 passing control, see the disclosure above):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F.F                                                                      [100%]
=================================== FAILURES ===================================
_______ test_row11_an_unresolved_pr_comment_leaves_the_closed_slot_unset _______

    def test_row11_an_unresolved_pr_comment_leaves_the_closed_slot_unset():
        lanes, comments = _reopened_lane_and_comments()
        gh = _PrGh(comments, prs={501: _failed()})
        closed_out, unread_out = [None], {}
        _evaluate(lanes, gh, closed_out=closed_out, unread_out=unread_out)
>       assert closed_out[0] is None
E       AssertionError: assert {'cloud-a': ((1795701371.0, 7), 'handback')} is None

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:315: AssertionError
__________ test_row11_an_unresolved_pr_comment_keeps_the_known_closes __________

    def test_row11_an_unresolved_pr_comment_keeps_the_known_closes():
        lanes, comments = _reopened_lane_and_comments()
        known = {"cloud-a": ((time.time() - 300, 7), "handback")}
        gh = _PrGh(comments, prs={501: _failed()})
        (notes, terminals), degraded = _evaluate(lanes, gh, known_closes=known)
        assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in degraded
>       assert terminals == []  # the cached close, not this read's first ending, bounds the window
        ^^^^^^^^^^^^^^^^^^^^^^
E       AssertionError: assert [{'launchId':...e': 101, ...}] == []
E         
E         Left contains one more item: {'launchId': 'cloud-a', 'state': 'handback', 'kind': 'handback', 'issue': 101, ...}
E         Use -v to get more diff

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:334: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row11_an_unresolved_pr_comment_leaves_the_closed_slot_unset
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row11_an_unresolved_pr_comment_keeps_the_known_closes
2 failed, 1 passed, 24 deselected in 0.53s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `    complete = state and pr_complete` (directly under its `# axis:` comment); `git diff --stat` printed `1 file changed, 149 insertions(+), 6 deletions(-)`, as before.
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
...                                                                      [100%]
3 passed, 24 deselected in 0.58s
```
