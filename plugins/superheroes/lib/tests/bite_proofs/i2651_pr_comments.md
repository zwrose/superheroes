# Bite-proof record: #2651 the wave watch attributes a builder note or cloud terminal comment on a watched lane's own PR to that lane

Detector under proof: `plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py` (plus, for element 6, the
existing `test_wave_watch_builder_note.py::test_a_lane_with_no_numeric_started_ts_is_not_watched_and_the_rest_still_count`).
Guarded code: `plugins/superheroes/lib/wave_watch.py`.
Base: `7d10cb4ee5eac77aaf78ba7bc274f403f6b40cd1`; this record is the order A2 rewrite (a PR-comment candidate is a
pull-request comment, never a plain-issue comment: `_pr_candidate` requires an `html_url` ending
`/pull/<n>#issuecomment-<id>` with `<n>` equal to the `issue_url` number). Declared guarded-element set: the six
below (one neutralization and one red each, no grouping). Every neutralization was a targeted edit made with the Edit
tool, undone by the inverse Edit before the next element, each Edit and each run in its own tool call. No `git
checkout`, `restore`, `reset` or `stash` was used. Command prefix for every run below (worktree root):
`timeout 900 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py -q -p no:cacheprovider -k "<selector>"`
(element 6 adds the existing test file as a second path argument). The selector is named in each entry; every
selector is the planned one, none was changed. Captures are raw pytest output, nothing trimmed (the `UV_NATIVE_TLS`
warning line is kept) and nothing redacted (temp paths only); each is under 32 KiB. The red runs exit 1 by design
(bite-proof reds, not failures). The production sites cite this record with `# axis:` comments. The file is
uncommitted, so the restore receipt is the restored text quoted; `git diff --stat` taken once after all six restores
(against commit A, which holds order A's work) printed `plugins/superheroes/lib/wave_watch.py | 15 +++-` (the A2
change itself, not residue of a neutralization).

Disclosures:
- Element 4's selector `row8` selects 5 tests (the progress-comment test, the handover test, and the 3 free-form
  parametrizations); all 5 are red under the neutralization. The progress comment is given a `/pull/` html_url
  (`_as_pr`) so it reaches the kind filter; with an `/issues/` url it would never be a candidate and this element
  could not bite.
- Element 5's selector `row11` selects 3 tests: 2 are red; the control (`..._a_resolved_pr_comment_sets_the_closed_slot`)
  passes under this neutralization by design, so it does not discriminate it. The green run used the same selector.
- Element 2's red is rows 5 and 7; element 3's red is row 7 alone.
- Element 6's neutralization replaces only the number/page-shape condition (`if pull is None or int(...) != number:`
  became `if False:`); the `isinstance(html_url, str)` check just above it stays, so a comment with no string
  `html_url` is still no candidate under it (that edge is covered by the two `html_url` rows added to
  `test_a_malformed_element_is_skipped_and_the_rest_still_count`, not proven by a separate neutralization). Its red
  is three tests: row 9, the page-number-differs test, and the existing builder-note test. The page-number-differs
  test is red because the `/pull/502` page number differing from the `issue_url` number 501 is then no longer
  rejected (red: `lane-terminal` instead of `timer`).
- The tests that assert a degradation use `ww.run` (one tick), not `watch_arm`: a multi-tick arm that ends on `timer`
  reports `builder-note-unavailable` on its last tick for want of budget with an issue-only comment too (observed on
  this tree, with a PR-free comment list), so the arm cannot show the absence of a disclosure.

## 1. The re-key (`_attribute_pr_comments`, `wave_watch.py:2449`)

- **Axis:** a note or ending on a pull request that closes exactly one watched issue is re-keyed to that lane's issue, so the lane's windows, answered record and park supersession read it.
- **Neutralization:** `attributed.append(dict(comment, issue_url=issue_url, prNumber=number))` became `attributed.append(comment)`.
- **Raw red** (`-k "row1_a or row2_a or row6_a"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FFF                                                                      [100%]
=================================== FAILURES ===================================
______ test_row1_a_handback_on_the_lanes_pr_is_lane_terminal_for_the_lane ______

repo = '/tmp/claude-0/pytest-of-root/pytest-15/test_row1_a_handback_on_the_la0/repo'

    def test_row1_a_handback_on_the_lanes_pr_is_lane_terminal_for_the_lane(repo):
        _cloud_lane(repo, "cloud-a", 101)
        gh = _PrGh([_pr_comment(7, 501, _body("handback"))], prs={501: _pr(501, "Closes #101.\n\nThe work.")})
>       launch = _only_launch(_arm(repo, gh))
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:120: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': ['builder-note-unavailable'], ...}

    def _only_launch(result):
>       assert result["event"] == ww.EVENT_LANE_TERMINAL, result
E       AssertionError: {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': ['builder-note-unavailable'], ...}
E       assert 'timer' == 'lane-terminal'
E         
E         - lane-terminal
E         + timer

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:82: AssertionError
__________ test_row2_a_builder_note_on_the_lanes_pr_is_the_lanes_note __________

repo = '/tmp/claude-0/pytest-of-root/pytest-15/test_row2_a_builder_note_on_th0/repo'

    def test_row2_a_builder_note_on_the_lanes_pr_is_the_lanes_note(repo):
        _cloud_lane(repo, "cloud-a", 101)
        gh = _PrGh([_pr_comment(7, 501)], prs={501: _pr(501, "Closes #101.\n\nThe work.")})
        result = _arm(repo, gh)
>       assert result["event"] == ww.EVENT_BUILDER_NOTE
E       AssertionError: assert 'timer' == 'builder-note'
E         
E         - builder-note
E         + timer

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:134: AssertionError
______ test_row6_a_stack_upper_layers_pr_comment_is_the_upper_lanes_only _______

repo = '/tmp/claude-0/pytest-of-root/pytest-15/test_row6_a_stack_upper_layers0/repo'

    def test_row6_a_stack_upper_layers_pr_comment_is_the_upper_lanes_only(repo):
        _cloud_lane(repo, "cloud-lower", 101)
        _cloud_lane(repo, "cloud-upper", 102)
        gh = _PrGh(
            [_pr_comment(7, 502, _body("handback"))],
            prs={502: _pr(502, "Closes #102", base="layer-101-branch")},
        )
        result = _arm(repo, gh)
>       launch = _only_launch(result)
                 ^^^^^^^^^^^^^^^^^^^^

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:251: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': ['builder-note-unavailable'], ...}

    def _only_launch(result):
>       assert result["event"] == ww.EVENT_LANE_TERMINAL, result
E       AssertionError: {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': ['builder-note-unavailable'], ...}
E       assert 'timer' == 'lane-terminal'
E         
E         - lane-terminal
E         + timer

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:82: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row1_a_handback_on_the_lanes_pr_is_lane_terminal_for_the_lane
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row2_a_builder_note_on_the_lanes_pr_is_the_lanes_note
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row6_a_stack_upper_layers_pr_comment_is_the_upper_lanes_only
3 failed, 25 deselected in 1.20s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `            attributed.append(dict(comment, issue_url=issue_url, prNumber=number))` (directly under `issue_url = re.sub(...)`).
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
...                                                                      [100%]
3 passed, 25 deselected in 6.53s
```

## 2. The disclosure (`_evaluate_cloud_comments`, `wave_watch.py:2567`)

- **Axis:** a note or ending on a pull request the watch could not attribute to one lane is disclosed (`builder-note-unavailable`) and names every watched lane, never read as "no note".
- **Neutralization:** the body of `if not pr_complete:` (`degraded.add(DEGRADATION_BUILDER_NOTE_UNAVAILABLE)` and `_record_unread(unread_out, watched)`) became `pass`.
- **Raw red** (`-k "row5 or row7"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FF                                                                       [100%]
=================================== FAILURES ===================================
__________ test_row5_an_unreadable_pr_is_disclosed_and_names_the_lane __________

repo = '/tmp/claude-0/pytest-of-root/pytest-17/test_row5_an_unreadable_pr_is_0/repo'

    def test_row5_an_unreadable_pr_is_disclosed_and_names_the_lane(repo):
        _cloud_lane(repo, "cloud-a", 101)
        gh = _PrGh([_pr_comment(7, 501, _body("handback"))], prs={501: _failed()})
        result = ww.run(repo, _BATCH, gh_run=gh)
        assert result["event"] != ww.EVENT_LANE_TERMINAL
>       assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]
E       AssertionError: assert 'builder-note-unavailable' in []
E        +  where 'builder-note-unavailable' = ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:210: AssertionError
____ test_row7_a_pr_closing_two_watched_issues_is_no_lanes_and_is_disclosed ____

repo = '/tmp/claude-0/pytest-of-root/pytest-17/test_row7_a_pr_closing_two_wat0/repo'

    def test_row7_a_pr_closing_two_watched_issues_is_no_lanes_and_is_disclosed(repo):
        _cloud_lane(repo, "cloud-a", 101)
        _cloud_lane(repo, "cloud-b", 102)
        gh = _PrGh([_pr_comment(7, 503, _body("handback"))], prs={503: _pr(503, "Closes #101\nCloses #102")})
        result = ww.run(repo, _BATCH, gh_run=gh)
        assert result["event"] != ww.EVENT_LANE_TERMINAL
>       assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]
E       AssertionError: assert 'builder-note-unavailable' in []
E        +  where 'builder-note-unavailable' = ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:266: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row5_an_unreadable_pr_is_disclosed_and_names_the_lane
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row7_a_pr_closing_two_watched_issues_is_no_lanes_and_is_disclosed
2 failed, 26 deselected in 0.94s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored lines, `        degraded.add(DEGRADATION_BUILDER_NOTE_UNAVAILABLE)` / `        _record_unread(unread_out, watched)` (directly under the `# axis:` comment of `if not pr_complete:`).
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..                                                                       [100%]
2 passed, 26 deselected in 0.78s
```

## 3. The ambiguity rule (`_attribute_pr_comments`, `wave_watch.py:2448`)

- **Axis:** a pull request that closes two or more watched issues is no lane's and is disclosed, never guessed onto one.
- **Neutralization:** `if len(hits) == 1:` became `if len(hits) >= 1:` (two or more hits re-keyed to `hits[0]`).
- **Raw red** (`-k "row7"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_row7_a_pr_closing_two_watched_issues_is_no_lanes_and_is_disclosed ____

repo = '/tmp/claude-0/pytest-of-root/pytest-19/test_row7_a_pr_closing_two_wat0/repo'

    def test_row7_a_pr_closing_two_watched_issues_is_no_lanes_and_is_disclosed(repo):
        _cloud_lane(repo, "cloud-a", 101)
        _cloud_lane(repo, "cloud-b", 102)
        gh = _PrGh([_pr_comment(7, 503, _body("handback"))], prs={503: _pr(503, "Closes #101\nCloses #102")})
        result = ww.run(repo, _BATCH, gh_run=gh)
>       assert result["event"] != ww.EVENT_LANE_TERMINAL
E       AssertionError: assert 'lane-terminal' != 'lane-terminal'
E        +  where 'lane-terminal' = ww.EVENT_LANE_TERMINAL

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:265: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row7_a_pr_closing_two_watched_issues_is_no_lanes_and_is_disclosed
1 failed, 27 deselected in 0.68s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `        if len(hits) == 1:`.
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 27 deselected in 0.60s
```

## 4. The kind filter (`_pr_candidate`, `wave_watch.py:2371`)

- **Axis:** only a builder note or a handback, stop or park is read onto a lane through its pull request; any other comment on one (progress, handover, free-form) is no lane's.
- **Neutralization:** `if not (body.lstrip().startswith(cb.NOTE_HEADER) or cb.terminal_kind(body) in _PR_ATTRIBUTED_KINDS):` became `if False and not (...same condition...):`, so any string body is a candidate.
- **Raw red** (`-k "row8"`; 5 red, see the disclosure above):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FFFFF                                                                    [100%]
=================================== FAILURES ===================================
____ test_row8_a_progress_comment_on_the_lanes_pr_is_not_the_lanes_progress ____

    def test_row8_a_progress_comment_on_the_lanes_pr_is_not_the_lanes_progress():
        lanes = _lanes({"cloud-a": (101, 600)})
        gh = _PrGh([_as_pr(_progress(9, 501, updated_age=100))], prs={501: _pr(501, "Closes #101.")})
        progress_out = [None]
        _evaluate(lanes, gh, progress_out=progress_out)
>       assert progress_out[0] == {}
E       AssertionError: assert {'cloud-a': {... 'gate', ...}} == {}
E         
E         Left contains 1 more item:
E         {'cloud-a': {'commentId': 9,
E                      'expectedSeconds': 3600,
E                      'phase': 'gate',
E                      'updatedAt': '2026-11-26T14:05:09Z',
E                      'updatedEpoch': 1795701909.0}}
E         Use -v to get more diff

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:280: AssertionError
_ test_row8_a_handover_on_the_lanes_pr_does_not_end_a_stop_on_the_issue _____

repo = '/tmp/claude-0/pytest-of-root/pytest-21/test_row8_a_handover_on_the_la0/repo'

    def test_row8_a_handover_on_the_lanes_pr_does_not_end_a_stop_on_the_issue(repo):
        _cloud_lane(repo, "cloud-a", 101)
        comments = [
            _comment(5, 101, _body("stop"), age=200),
            _pr_comment(6, 501, cb.handover_text("a" * 40), age=100),
        ]
        gh = _PrGh(comments, prs={501: _pr(501, "Closes #101.")})
>       launch = _only_launch(_arm(repo, gh))
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:291: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': ['builder-note-unavailable'], ...}

    def _only_launch(result):
>       assert result["event"] == ww.EVENT_LANE_TERMINAL, result
E       AssertionError: {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': ['builder-note-unavailable'], ...}
E       assert 'timer' == 'lane-terminal'
E         
E         - lane-terminal
E         + timer

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:82: AssertionError
_ test_row8_free_form_text_on_the_lanes_pr_is_no_lanes[Builder stop at intake. The Anchor did not resolve.] _

repo = '/tmp/claude-0/pytest-of-root/pytest-21/test_row8_free_form_text_on_th0/repo'
body = 'Builder stop at intake. The Anchor did not resolve.'

    @pytest.mark.parametrize("body", [
        "Builder stop at intake. The Anchor did not resolve.",
        "Here is my update.\n\n" + cb.HANDBACK_HEADER + "\n\nDone.",
        cb.REFUSAL_HEADER + "\n\nNo.",
    ])
    def test_row8_free_form_text_on_the_lanes_pr_is_no_lanes(repo, body):
        _cloud_lane(repo, "cloud-a", 101)
        gh = _PrGh([_pr_comment(7, 501, body)], prs={501: _pr(501, "Closes #101.")})
        assert _arm(repo, gh)["event"] == ww.EVENT_TIMER
>       assert gh.pr_reads == []
E       assert [501, 501, 501] == []
E         
E         Left contains 3 more items, first extra item: 501
E         Use -v to get more diff

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:306: AssertionError
_ test_row8_free_form_text_on_the_lanes_pr_is_no_lanes[Here is my update.\n\nBuilder handback (cloud build).\n\nDone.] _

repo = '/tmp/claude-0/pytest-of-root/pytest-21/test_row8_free_form_text_on_th1/repo'
body = 'Here is my update.\n\nBuilder handback (cloud build).\n\nDone.'

    @pytest.mark.parametrize("body", [
        "Builder stop at intake. The Anchor did not resolve.",
        "Here is my update.\n\n" + cb.HANDBACK_HEADER + "\n\nDone.",
        cb.REFUSAL_HEADER + "\n\nNo.",
    ])
    def test_row8_free_form_text_on_the_lanes_pr_is_no_lanes(repo, body):
        _cloud_lane(repo, "cloud-a", 101)
        gh = _PrGh([_pr_comment(7, 501, body)], prs={501: _pr(501, "Closes #101.")})
        assert _arm(repo, gh)["event"] == ww.EVENT_TIMER
>       assert gh.pr_reads == []
E       assert [501, 501, 501] == []
E         
E         Left contains 3 more items, first extra item: 501
E         Use -v to get more diff

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:306: AssertionError
_ test_row8_free_form_text_on_the_lanes_pr_is_no_lanes[Builder refusal (cloud build).\n\nNo.] _

repo = '/tmp/claude-0/pytest-of-root/pytest-21/test_row8_free_form_text_on_th2/repo'
body = 'Builder refusal (cloud build).\n\nNo.'

    @pytest.mark.parametrize("body", [
        "Builder stop at intake. The Anchor did not resolve.",
        "Here is my update.\n\n" + cb.HANDBACK_HEADER + "\n\nDone.",
        cb.REFUSAL_HEADER + "\n\nNo.",
    ])
    def test_row8_free_form_text_on_the_lanes_pr_is_no_lanes(repo, body):
        _cloud_lane(repo, "cloud-a", 101)
        gh = _PrGh([_pr_comment(7, 501, body)], prs={501: _pr(501, "Closes #101.")})
        assert _arm(repo, gh)["event"] == ww.EVENT_TIMER
>       assert gh.pr_reads == []
E       assert [501, 501, 501] == []
E         
E         Left contains 3 more items, first extra item: 501
E         Use -v to get more diff

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:306: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row8_a_progress_comment_on_the_lanes_pr_is_not_the_lanes_progress
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row8_a_handover_on_the_lanes_pr_does_not_end_a_stop_on_the_issue
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row8_free_form_text_on_the_lanes_pr_is_no_lanes[Builder stop at intake. The Anchor did not resolve.]
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row8_free_form_text_on_the_lanes_pr_is_no_lanes[Here is my update.\n\nBuilder handback (cloud build).\n\nDone.]
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row8_free_form_text_on_the_lanes_pr_is_no_lanes[Builder refusal (cloud build).\n\nNo.]
5 failed, 23 deselected in 1.23s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `        if not (body.lstrip().startswith(cb.NOTE_HEADER) or cb.terminal_kind(body) in _PR_ATTRIBUTED_KINDS):`.
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.....                                                                    [100%]
5 passed, 23 deselected in 1.13s
```

## 5. The close bookkeeping (`_evaluate_cloud_comments`, `wave_watch.py:2580`)

- **Axis:** an incomplete pull-request attribution is a partial read: it neither replaces the known closes nor sets the closed slot.
- **Neutralization:** `complete = state and pr_complete` became `complete = state`.
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
E       AssertionError: assert {'cloud-a': ((1795701923.0, 7), 'handback')} is None

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:341: AssertionError
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

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:360: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row11_an_unresolved_pr_comment_leaves_the_closed_slot_unset
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_row11_an_unresolved_pr_comment_keeps_the_known_closes
2 failed, 1 passed, 25 deselected in 0.58s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `    complete = state and pr_complete` (directly under its `# axis:` comment).
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
...                                                                      [100%]
3 passed, 25 deselected in 0.49s
```

## 6. PR-only candidate (`_pr_candidate`'s `html_url` check, `wave_watch.py:2363-2369`)

- **Axis:** only a comment whose `html_url` is a `/pull/<n>#issuecomment-<id>` page with the same number as its `issue_url` is a candidate, so a plain issue's comment (an `/issues/` page, even from a handback or builder note) never causes a read and never a disclosure.
- **Neutralization:** `if pull is None or int(pull.group(1)) != number:` became `if False:` (any string `html_url` passes).
- **Raw red** (`plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py plugins/superheroes/lib/tests/test_wave_watch_builder_note.py -k "row9 or page_number or test_a_lane_with_no_numeric_started_ts_is_not_watched_and_the_rest_still_count"`; 3 red, see the disclosure above):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FFF                                                                      [100%]
=================================== FAILURES ===================================
____ test_row9_a_handback_on_a_plain_issue_causes_no_read_and_no_disclosure ____

repo = '/tmp/claude-0/pytest-of-root/pytest-25/test_row9_a_handback_on_a_plai0/repo'

    def test_row9_a_handback_on_a_plain_issue_causes_no_read_and_no_disclosure(repo):
        _cloud_lane(repo, "cloud-a", 101)
        # A plain issue's comment has an `/issues/` html_url; reading 777 would fail here, so a read would be disclosed.
        gh = _PrGh([_comment(7, 777, _body("handback"))], prs={777: _failed()})
        result = ww.run(repo, _BATCH, gh_run=gh)
        assert result["event"] == ww.EVENT_TIMER
>       assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE not in result["degraded"]
E       AssertionError: assert 'builder-note-unavailable' not in ['builder-note-unavailable']
E        +  where 'builder-note-unavailable' = ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:169: AssertionError
_ test_a_pr_comment_whose_page_number_differs_from_its_issue_number_is_no_candidate _

repo = '/tmp/claude-0/pytest-of-root/pytest-25/test_a_pr_comment_whose_page_n0/repo'

    def test_a_pr_comment_whose_page_number_differs_from_its_issue_number_is_no_candidate(repo):
        _cloud_lane(repo, "cloud-a", 101)
        odd = dict(
            _pr_comment(7, 501, _body("handback")),
            html_url="https://github.com/%s/pull/502#issuecomment-7" % _SLUG,
        )
        gh = _PrGh([odd], prs={501: _pr(501, "Closes #101."), 502: _pr(502, "Closes #101.")})
        result = ww.run(repo, _BATCH, gh_run=gh)
>       assert result["event"] == ww.EVENT_TIMER
E       AssertionError: assert 'lane-terminal' == 'timer'
E         
E         - timer
E         + lane-terminal

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py:183: AssertionError
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
FAILED plugins/superheroes/lib/tests/test_wave_watch_pr_comments_2651.py::test_a_pr_comment_whose_page_number_differs_from_its_issue_number_is_no_candidate
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_a_lane_with_no_numeric_started_ts_is_not_watched_and_the_rest_still_count
3 failed, 122 deselected in 1.01s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `        if pull is None or int(pull.group(1)) != number:` (directly under `pull = re.search(r"/pull/(\d+)#issuecomment-\d+$", html_url)`).
- **Raw green** (same command and selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
...                                                                      [100%]
3 passed, 122 deselected in 0.93s
```
