# Bite-proof record: #2333 the wave watch reads an old resumed lane's own issue

Detector under proof: `plugins/superheroes/lib/tests/test_wave_watch_lookback_2333.py`.
Guarded code: `plugins/superheroes/lib/wave_watch.py` (`_evaluate_cloud_comments`, `_merge_comments`, `_cloud_note_times`).
Base: `73cae632b81aef4ead00de254f313783e0003415`. Declared guarded-element set: the five below (one neutralization
and one red each, no grouping). Every neutralization was a targeted edit made with the Edit tool, undone by the
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

- **Axis:** a per-lane read that was skipped, failed or partial is disclosed for that lane alone, never read as quiet.
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

## Disclosures

- T4 (the F3 mixed-lane test) and the lone-lane half of T3 carry no neutralization of their own: they are not in the
  declared guarded-element set, so no red was run for them.
- The `# axis:` comments on `_merge_comments` and on the `shared` split cite this record from the production sites.
