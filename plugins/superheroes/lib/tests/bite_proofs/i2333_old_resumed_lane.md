# Bite-proof record: #2333 the wave watch reads an old resumed lane's own issue

Detector under proof: `plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py`.
Guarded code: `plugins/superheroes/lib/wave_watch.py` (`_evaluate_cloud_comments`, `_merge_comments`, `_cloud_note_times`).
Base: `73cae632b81aef4ead00de254f313783e0003415`. Declared guarded-element set: the eleven below, G1-G11 (one
neutralization and one red each, no grouping). G1-G5 were captured at the earlier head; G6-G11 were added by the
fix leg (WO-B, head `27b6f0bc2c044c3e55ceba9fc8a582d6730c311c` plus the V1 edit) and are captured against it. The
`wave_watch.py:<line>` numbers in G1-G5's restore receipts are from the earlier head and have since shifted. Every neutralization was a targeted edit made with the Edit tool, undone by the
inverse Edit before the next element, each Edit and each run in its own tool call. No `git checkout`, `restore`,
`reset` or `stash` was used. Command prefix for every run below (worktree root):
`timeout 900 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py -k "<selector>"`.
Captures are raw pytest output, nothing trimmed (the `UV_NATIVE_TLS` warning line is kept) and nothing redacted
(temp paths only); each is under 32 KiB. The red runs exit 1 by design (bite-proof reds, not failures). The
production sites cite this record with `# axis:` comments. The restore receipt for every entry is the restored text
quoted below (read back from the file after the inverse Edit); each green run follows it.

## 1. G1: per-lane admission (`_evaluate_cloud_comments`, the loop `for lid in sorted(old_dormant):`)

- **Axis:** an old dormant lane is read from its own issue, so its handback is seen however old its basis is.
- **Neutralization:** `for lid in sorted(old_dormant):` became `for lid in []:` (no lane gets a per-lane read).
- **Raw red** (`-k "t1_an_old"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_t1_an_old_resumed_lanes_handback_is_reported_from_its_own_issue _____

repo = '/tmp/claude-0/pytest-of-root/pytest-2/test_t1_an_old_resumed_lanes_h0/repo'

    def test_t1_an_old_resumed_lanes_handback_is_reported_from_its_own_issue(repo):
        # axis: an old dormant lane is read from its own issue, so its handback is seen however old its basis — see bite-proof record i2333_old_resumed_lane.md
        _dormant(repo)
        _live(repo)
        handback = _comment(7, 101, _ending("handback"), age=36 * 3600)
        gh = _ScopedGh([handback])
        result = ww.run(repo, _BATCH, gh_run=gh)
>       assert result["event"] == ww.EVENT_LANE_TERMINAL
E       AssertionError: assert 'timer' == 'lane-terminal'
E         
E         - lane-terminal
E         + timer

/home/user/wt-2333/plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py:114: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py::test_t1_an_old_resumed_lanes_handback_is_reported_from_its_own_issue
1 failed, 6 deselected in 0.77s
```

- **Restore:** the inverse Edit, `for lid in []:` back to `for lid in sorted(old_dormant):`.
- **Restore receipt:** `wave_watch.py:2268:    for lid in sorted(old_dormant):`.
- **Raw green** (`-k "t1_an_old"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 6 deselected in 1.00s
```

## 2. G2: per-lane failure disclosure (`_evaluate_cloud_comments`, the `if lane_state is not True:` branch)

- **Axis:** a per-lane read that failed is disclosed for that lane alone, never read as quiet (the detectors are T2 and
  T4, which fail a read; the skipped leg is G6 and the naming rule is G7).
- **Neutralization:** the branch body `degraded.add(DEGRADATION_BUILDER_NOTE_UNAVAILABLE)` and
  `if unread_out is not None: unread_out[lid] = info["issue"]` became `pass`.
- **Raw red** (`-k "t2_a_failed"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_t2_a_failed_per_lane_read_is_disclosed_for_that_lane_alone ________

repo = '/tmp/claude-0/pytest-of-root/pytest-4/test_t2_a_failed_per_lane_read0/repo'

    def test_t2_a_failed_per_lane_read_is_disclosed_for_that_lane_alone(repo):
        # axis: a per-lane read that failed is disclosed for that lane alone, never read as quiet — see bite-proof record i2333_old_resumed_lane.md
        _dormant(repo, "cloud-a", 101)
        _dormant(repo, "cloud-b", 102)
        gh = _ScopedGh([], failing_issues=[101])
        result = ww.run(repo, _BATCH, gh_run=gh)
        assert result["event"] == ww.EVENT_TIMER
>       assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in result["degraded"]
E       AssertionError: assert 'builder-note-unavailable' in []
E        +  where 'builder-note-unavailable' = ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE

/home/user/wt-2333/plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py:130: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py::test_t2_a_failed_per_lane_read_is_disclosed_for_that_lane_alone
1 failed, 6 deselected in 6.04s
```

- **Restore:** the inverse Edit put the two statements back in the branch.
- **Restore receipt:** `wave_watch.py:2279:                unread_out[lid] = info["issue"]` (under the restored
  `degraded.add(DEGRADATION_BUILDER_NOTE_UNAVAILABLE)` and `if unread_out is not None:`).
- **Raw green** (`-k "t2_a_failed"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 6 deselected in 0.80s
```

## 3. G3: the shared bound (`_evaluate_cloud_comments`, the shared `since`)

- **Axis:** no dormant lane pulls the shared repository-wide read further back than `DORMANT_LOOKBACK_SECONDS`
  before the read.
- **Neutralization:** `min(_read_cutoff(info) for info in shared.values())` became
  `min(info["dormantSince"] if "dormantSince" in info else _read_cutoff(info) for info in watched.values())`
  (every dormant lane, old ones included, sets `since` from its unclamped basis).
- **Raw red** (`-k "t3_no_dormant"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_t3_no_dormant_lane_pulls_the_shared_read_past_the_lookback ________

repo = '/tmp/claude-0/pytest-of-root/pytest-6/test_t3_no_dormant_lane_pulls_0/repo'

    def test_t3_no_dormant_lane_pulls_the_shared_read_past_the_lookback(repo):
        # axis: no dormant lane pulls the shared read further back than DORMANT_LOOKBACK_SECONDS — see bite-proof record i2333_old_resumed_lane.md
        assert ww.DORMANT_LOOKBACK_SECONDS == _DAY
        _dormant(repo)
        _live(repo)
        gh = _ScopedGh([])
        before = time.time()
        ww.run(repo, _BATCH, gh_run=gh)
        [shared] = gh.shared_urls()
>       assert _since(shared) >= before - _DAY
E       AssertionError: assert 1793504408.0 >= (1793677208.7133734 - 86400)
E        +  where 1793504408.0 = _since('repos/owner/repo/issues/comments?since=2026-11-01T03:40:08Z&per_page=100')

/home/user/wt-2333/plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py:144: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py::test_t3_no_dormant_lane_pulls_the_shared_read_past_the_lookback
1 failed, 6 deselected in 0.82s
```

- **Restore:** the inverse Edit.
- **Restore receipt:** `wave_watch.py:2245:                min(_read_cutoff(info) for info in shared.values()), tz=timezone.utc,`.
- **Raw green** (`-k "t3_no_dormant"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 6 deselected in 0.87s
```

## 4. G4: newest-revision merge (`_merge_comments`, the `if replace:` branch)

- **Axis:** a repeated comment id keeps the copy changed later, so an edit the per-lane read sees is not shadowed by an
  older copy from the shared read.
- **Neutralization:** `if replace:` became `if False:` (the first copy of a duplicate id is always kept).
- **Raw red** (`-k "t5_a_comment"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_t5_a_comment_in_both_reads_keeps_its_newest_revision ___________

repo = '/tmp/claude-0/pytest-of-root/pytest-8/test_t5_a_comment_in_both_read0/repo'

    def test_t5_a_comment_in_both_reads_keeps_its_newest_revision(repo):
        # axis: a repeated comment id keeps the newest revision, so the per-lane read's edit is not shadowed by an older copy — see bite-proof record i2333_old_resumed_lane.md
        _dormant(repo)
        _live(repo)
        created = 2.5 * _DAY
        parked = _progress(9, 101, updated_age=3000, created_age=created, phase="parked: waiting")
        resumed = _progress(9, 101, updated_age=1800, created_age=created, phase="resumed: fixing")
        gh = _ScopedGh([], shared=[parked], scoped=[resumed])
        result = ww.run(repo, _BATCH, gh_run=gh)
        assert len(gh.shared_urls()) == 1 and len(gh.scoped_urls(101)) == 1
>       assert "cloud-a" in [lane["launchId"] for lane in result.get("cloudLanes", [])]
E       AssertionError: assert 'cloud-a' in ['cloud-live']

/home/user/wt-2333/plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py:187: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py::test_t5_a_comment_in_both_reads_keeps_its_newest_revision
1 failed, 6 deselected in 0.78s
```

- **Restore:** the inverse Edit, `if False:` back to `if replace:`.
- **Restore receipt:** `wave_watch.py:2188:            if replace:`.
- **Raw green** (`-k "t5_a_comment"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 6 deselected in 0.68s
```

## 5. G5: a lane's newest note supersedes a park (`_cloud_note_times`)

- **Axis:** a lane's newest builder note, not its oldest, supersedes a park.
- **Neutralization:** `created > newest[lid]` became `created < newest[lid]` (the oldest note is kept).
- **Raw red** (`-k "t6_a_lanes"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_t6_a_lanes_newest_note_not_its_oldest_supersedes_a_park _________

repo = '/tmp/claude-0/pytest-of-root/pytest-10/test_t6_a_lanes_newest_note_no0/repo'

    def test_t6_a_lanes_newest_note_not_its_oldest_supersedes_a_park(repo):
        # axis: a lane's newest note, not its oldest, supersedes a park — see bite-proof record i2333_old_resumed_lane.md
        _cloud_lane(repo, "cloud-a", 101, start_age=5 * _DAY)
        note_a = _comment(11, 101, age=3000)
        park = _comment(12, 101, _ending("park"), age=2000)
        note_b = _comment(13, 101, age=1000)
        assert _note_answered(repo, 11)["ok"] is True
        assert _note_answered(repo, 13)["ok"] is True
        gh = _ScopedGh([note_b, park, note_a])
        result = ww.run(repo, _BATCH, gh_run=gh)
>       assert result["event"] == ww.EVENT_TIMER
E       AssertionError: assert 'lane-terminal' == 'timer'
E         
E         - timer
E         + lane-terminal

/home/user/wt-2333/plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py:200: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py::test_t6_a_lanes_newest_note_not_its_oldest_supersedes_a_park
1 failed, 6 deselected in 1.00s
```

- **Restore:** the inverse Edit, `<` back to `>`.
- **Restore receipt:** `wave_watch.py:1871:        if lid not in newest or created > newest[lid]:`.
- **Raw green** (`-k "t6_a_lanes"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 6 deselected in 0.72s
```

## 6. G6: the skipped leg (`_evaluate_cloud_comments`, the `if lane_state is not True:` branch)

- **Axis:** a per-lane read skipped for budget after this tick made a request is disclosed and names its lane.
- **Neutralization:** `if lane_state is not True:` became `if lane_state is False:` (a skipped read, `None`, is no longer disclosed).
- **Raw red** (`-k "t9_a_per_lane"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_t9_a_per_lane_read_skipped_after_a_request_names_its_lane ________

repo = '/tmp/claude-0/pytest-of-root/pytest-14/test_t9_a_per_lane_read_skippe0/repo'

    def test_t9_a_per_lane_read_skipped_after_a_request_names_its_lane(repo):
        # axis: a per-lane read skipped for budget after this tick made a request names its lane and records builder-note-unavailable — see bite-proof record i2333_old_resumed_lane.md
        _dormant(repo)
        _live(repo)
        now = [0.0]
        gh = _SpendingGh([], now=now, spend_to=200.0)
        degraded, unread = set(), {}
        _evaluate(repo, gh, deadline=100.0, monotonic=lambda: now[0], degraded=degraded, unread=unread)
        assert len(gh.shared_urls()) == 1
        assert gh.scoped_urls(101) == []
>       assert ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE in degraded
E       AssertionError: assert 'builder-note-unavailable' in set()
E        +  where 'builder-note-unavailable' = ww.DEGRADATION_BUILDER_NOTE_UNAVAILABLE

/home/user/wt-2333/plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py:266: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py::test_t9_a_per_lane_read_skipped_after_a_request_names_its_lane
1 failed, 12 deselected in 0.77s
```

- **Restore:** the inverse Edit, `is False` back to `is not True`.
- **Restore receipt:** `wave_watch.py:2279:        if lane_state is not True:`.
- **Raw green** (`-k "t9_a_per_lane"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 12 deselected in 1.03s
```

## 7. G7: the naming rule (`_evaluate_cloud_comments`, the `unread_out[lid] = info["issue"]` condition)

- **Axis:** a tick that made no comments request names no lane (old resumed ones included) and keeps its disclosure;
  a tick whose per-lane reads all succeeded names none either (the wo_2148 rule).
- **Neutralization:** `if unread_out is not None and (lane_state is False or requested):` became
  `if unread_out is not None:` (the unfixed condition: every lane whose read was not `True` is named).
- **Raw red** (`-k "t7_a_tick or t8_a_tick"`; T7 and T8 both red):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FF                                                                       [100%]
=================================== FAILURES ===================================
____ test_t7_a_tick_whose_reads_all_succeeded_names_no_lane_at_its_deadline ____

repo = '/tmp/claude-0/pytest-of-root/pytest-16/test_t7_a_tick_whose_reads_all0/repo'

    def test_t7_a_tick_whose_reads_all_succeeded_names_no_lane_at_its_deadline(repo):
        # axis: a tick whose reads all succeeded names no old resumed lane, even though its last tick runs at its deadline with no budget — see bite-proof record i2333_old_resumed_lane.md
        _dormant(repo)
        _live(repo)
        gh = _ScopedGh([])
        result = ww.watch_arm(repo, _BATCH, max_seconds=3, interval_seconds=1, gh_run=gh)
        assert result["event"] == ww.EVENT_TIMER
        assert len(gh.scoped_urls(101)) >= 1
>       assert "unreadIssues" not in result
E       AssertionError: assert 'unreadIssues' not in {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': ['builder-note-unavailable'], ...}

/home/user/wt-2333/plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py:241: AssertionError
__ test_t8_a_tick_that_made_no_request_names_no_lane_and_keeps_the_disclosure __

repo = '/tmp/claude-0/pytest-of-root/pytest-16/test_t8_a_tick_that_made_no_re0/repo'

    def test_t8_a_tick_that_made_no_request_names_no_lane_and_keeps_the_disclosure(repo):
        # axis: a tick that made no comments request names no lane, old resumed ones included, and records builder-note-unavailable — see bite-proof record i2333_old_resumed_lane.md
        _dormant(repo)
        _live(repo)
        gh = _ScopedGh([])
        degraded, unread = set(), {}
        _evaluate(repo, gh, deadline=0.0, monotonic=lambda: 1.0, degraded=degraded, unread=unread)
>       assert unread == {}
E       AssertionError: assert {'cloud-a': 101} == {}
E         
E         Left contains 1 more item:
E         {'cloud-a': 101}
E         Use -v to get more diff

/home/user/wt-2333/plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py:251: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py::test_t7_a_tick_whose_reads_all_succeeded_names_no_lane_at_its_deadline
FAILED plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py::test_t8_a_tick_that_made_no_request_names_no_lane_and_keeps_the_disclosure
2 failed, 11 deselected in 6.53s
```

- **Restore:** the inverse Edit, back to `if unread_out is not None and (lane_state is False or requested):`.
- **Restore receipt:** `wave_watch.py:2282:            if unread_out is not None and (lane_state is False or requested):`.
- **Raw green** (`-k "t7_a_tick or t8_a_tick"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..                                                                       [100%]
2 passed, 11 deselected in 1.06s
```

## 8. G8: de-duplication (`_merge_comments`, the `if comment_id not in position:` branch)

- **Axis:** a comment id served by both reads is merged to one copy, so a note is reported once.
- **Neutralization:** `if comment_id not in position:` became `if True:` (a repeated id is appended, not merged).
- **Raw red** (`-k "t11_a_note"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_t11_a_note_served_by_both_reads_is_reported_once _____________

repo = '/tmp/claude-0/pytest-of-root/pytest-18/test_t11_a_note_served_by_both0/repo'

    def test_t11_a_note_served_by_both_reads_is_reported_once(repo):
        # axis: a comment id in both reads is merged to one copy, so a note is reported once, not twice — see bite-proof record i2333_old_resumed_lane.md
        _dormant(repo)
        _live(repo)
        note = _comment(21, 101, age=36 * 3600)
        note["updated_at"] = _iso(1800)
        gh = _ScopedGh([note])
        result = ww.run(repo, _BATCH, gh_run=gh)
        assert result["event"] == ww.EVENT_BUILDER_NOTE
        assert len(gh.shared_urls()) == 1 and len(gh.scoped_urls(101)) == 1
>       assert [n["commentId"] for n in result["notes"]] == [21]
E       assert [21, 21] == [21]
E         
E         Left contains one more item: 21
E         Use -v to get more diff

/home/user/wt-2333/plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py:293: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py::test_t11_a_note_served_by_both_reads_is_reported_once
1 failed, 12 deselected in 0.86s
```

- **Restore:** the inverse Edit, `if True:` back to `if comment_id not in position:`.
- **Restore receipt:** `wave_watch.py:2177:            if comment_id not in position:`.
- **Raw green** (`-k "t11_a_note"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 12 deselected in 0.75s
```

## 9. G9: the age threshold (`_evaluate_cloud_comments`, the `old_dormant` filter)

- **Axis:** only a dormant lane whose basis is older than `DORMANT_LOOKBACK_SECONDS` gets a per-lane read; a recent basis costs no extra request.
- **Neutralization:** `info["dormantSince"] < now - DORMANT_LOOKBACK_SECONDS` became `True` (the filter line read
  `and True`; every dormant lane goes to a per-lane read).
- **Raw red** (`-k "t12_a_dormant"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t12_a_dormant_lane_with_a_recent_basis_is_read_by_the_shared_read_alone _

repo = '/tmp/claude-0/pytest-of-root/pytest-20/test_t12_a_dormant_lane_with_a0/repo'

    def test_t12_a_dormant_lane_with_a_recent_basis_is_read_by_the_shared_read_alone(repo):
        # axis: only a dormant lane whose basis is older than DORMANT_LOOKBACK_SECONDS gets a per-lane read; a recent basis costs no extra request — see bite-proof record i2333_old_resumed_lane.md
        _cloud_lane(repo, "cloud-a", 101, start_age=3 * _DAY)
        _outcome_at(repo, "cloud-a", 3600)
        gh = _ScopedGh([])
        ww.run(repo, _BATCH, gh_run=gh)
>       assert gh.scoped_urls(101) == []
E       AssertionError: assert ['repos/owner...per_page=100'] == []
E         
E         Left contains one more item: 'repos/owner/repo/issues/101/comments?since=2026-11-03T03:52:41Z&per_page=100'
E         Use -v to get more diff

/home/user/wt-2333/plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py:302: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py::test_t12_a_dormant_lane_with_a_recent_basis_is_read_by_the_shared_read_alone
1 failed, 12 deselected in 0.86s
```

- **Restore:** the inverse Edit, `and True` back to `and info["dormantSince"] < now - DORMANT_LOOKBACK_SECONDS`.
- **Restore receipt:** `wave_watch.py:2240:        and info["dormantSince"] < now - DORMANT_LOOKBACK_SECONDS`.
- **Raw green** (`-k "t12_a_dormant"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 12 deselected in 0.90s
```

## 10. G10: reverse-order merge (`_merge_comments`, the `else:` revision comparison)

- **Axis:** a repeated comment id keeps the newest revision even when the shared copy is the newer one; the per-lane copy does not always win.
- **Neutralization:** `replace = new_time > kept_time or (new_time == kept_time and is_lane)` became `replace = is_lane`.
- **Raw red** (`-k "t10_a_comment"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_t10_a_comment_in_both_reads_keeps_the_newer_shared_copy _________

repo = '/tmp/claude-0/pytest-of-root/pytest-22/test_t10_a_comment_in_both_rea0/repo'

    def test_t10_a_comment_in_both_reads_keeps_the_newer_shared_copy(repo):
        # axis: a repeated comment id keeps the newest revision, even when the shared copy is the newer, so the per-lane copy does not always win — see bite-proof record i2333_old_resumed_lane.md
        _dormant(repo)
        _live(repo)
        created = 2.5 * _DAY
        parked = _progress(9, 101, updated_age=3000, created_age=created, phase="parked: waiting")
        resumed = _progress(9, 101, updated_age=1800, created_age=created, phase="resumed: fixing")
        gh = _ScopedGh([], shared=[resumed], scoped=[parked])
        result = ww.run(repo, _BATCH, gh_run=gh)
        assert len(gh.shared_urls()) == 1 and len(gh.scoped_urls(101)) == 1
>       assert "cloud-a" in [lane["launchId"] for lane in result.get("cloudLanes", [])]
E       AssertionError: assert 'cloud-a' in ['cloud-live']

/home/user/wt-2333/plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py:280: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py::test_t10_a_comment_in_both_reads_keeps_the_newer_shared_copy
1 failed, 12 deselected in 0.83s
```

- **Restore:** the inverse Edit, `replace = is_lane` back to the full comparison.
- **Restore receipt:** `wave_watch.py:2189:                replace = new_time > kept_time or (new_time == kept_time and is_lane)`.
- **Raw green** (`-k "t10_a_comment"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 12 deselected in 1.08s
```

## 11. G11: the first-note regression (`_cloud_note_times`)

- **Axis:** a lane's newest note, not the first one seen, supersedes a park; the comments are served oldest first, as GitHub serves them.
- **Neutralization:** `if lid not in newest or created > newest[lid]:` became `if lid not in newest:` (the first note seen is kept).
- **Raw red** (`-k "t6_a_lanes"`, T6 with its comments in oldest-first order):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_t6_a_lanes_newest_note_not_its_oldest_supersedes_a_park _________

repo = '/tmp/claude-0/pytest-of-root/pytest-24/test_t6_a_lanes_newest_note_no0/repo'

    def test_t6_a_lanes_newest_note_not_its_oldest_supersedes_a_park(repo):
        # axis: a lane's newest note, not its oldest, supersedes a park — see bite-proof record i2333_old_resumed_lane.md
        _cloud_lane(repo, "cloud-a", 101, start_age=5 * _DAY)
        note_a = _comment(11, 101, age=3000)
        park = _comment(12, 101, _ending("park"), age=2000)
        note_b = _comment(13, 101, age=1000)
        assert _note_answered(repo, 11)["ok"] is True
        assert _note_answered(repo, 13)["ok"] is True
        # GitHub serves both comment endpoints oldest first, so a "keep the first note seen" regression keeps the oldest note.
        gh = _ScopedGh([note_a, park, note_b])
        result = ww.run(repo, _BATCH, gh_run=gh)
>       assert result["event"] == ww.EVENT_TIMER
E       AssertionError: assert 'lane-terminal' == 'timer'
E         
E         - timer
E         + lane-terminal

/home/user/wt-2333/plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py:205: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py::test_t6_a_lanes_newest_note_not_its_oldest_supersedes_a_park
1 failed, 12 deselected in 0.76s
```

- **Restore:** the inverse Edit, back to `if lid not in newest or created > newest[lid]:`.
- **Restore receipt:** `wave_watch.py:1873:        if lid not in newest or created > newest[lid]:`.
- **Raw green** (`-k "t6_a_lanes"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 12 deselected in 0.80s
```

## Disclosures

- T4 (the F3 mixed-lane test) and the lone-lane half of T3 now carry `# axis:` lines but no neutralization of their
  own: they are not in the declared guarded-element set, so no red was run for them.
- G5's red and green were captured when T6 served its comments newest first (`[note_b, park, note_a]`); T6 now serves
  them oldest first (V3). G5's `<` neutralization was not re-run against the reordered T6 (the fix leg's command
  budget was spent on G6-G11). G11 is the red run against the reordered T6.
- G2's capture is from before V1 (the branch then named every non-`True` lane unconditionally); its neutralization
  text is unchanged, and the branch now reads as described in G6 and G7.
- The `# axis:` comments on `_merge_comments` and on the `shared` split cite this record from the production sites.
