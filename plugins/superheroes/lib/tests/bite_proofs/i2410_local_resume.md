# Bite-proof record: #2410 the wave watch watches a resumed local lane again

Detector under proof: `plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py`.
Guarded code: `plugins/superheroes/lib/wave_watch.py`.
Base: `79eb51ad4c121787b07b8105203aa5aedbf094c4`. Declared guarded-element set: the seven below (one
neutralization and one red each, no grouping). Every neutralization was a targeted edit made with the Edit
tool, undone by the inverse Edit before the next element, each Edit and each run in its own tool call. No
`git checkout`, `restore`, `reset` or `stash` was used. Command prefix for every run below (worktree root):
`timeout 900 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py -q -p no:cacheprovider --tb=line -k "<selector>"`.
`--tb=line` bounds each failure to one line; the selector differs per run and is named in each entry. Captures
are raw pytest output, nothing trimmed (the `UV_NATIVE_TLS` warning line is kept) and nothing redacted (temp
paths only); each is far under 32 KiB. The red runs exit 1 by design (bite-proof reds, not failures). The
production sites cite this record with `# axis:` comments. After the last restore, the neutralization
residue grep over the diff (`False and`, a bare `pass`, `session_id in parts`, `info.get("pid")`) printed
nothing; that and the restored text quoted in each entry are the restore receipts.

Disclosures:
- Element 3 was run twice. The first red (selector `row4_a_lane_reopened_by_a_heartbeat or row1_the_process_signal`)
  failed the test at its `_derive` assertion, before the end-to-end `builder-exited` assertion was reached. The
  test was reordered so the end-to-end assertion comes first, the neutralization was reverted and re-applied, and
  the red and green below are from that second pass.
- Element 2's selector `row6_a_session_id_anywhere` selects 6 tests; 5 are red under the neutralization and 1
  (`claude --resume other-session-id-0000`, a different id) passes, since a substring match does not match it.
- Element 6's selector `row2` selects 12 tests (the row 2, 2b and no-reopen cases); 5 are red and 7 pass, since
  the cases that must not reopen pass when nothing reopens.
- A scratch copy of element 1's red output was first written with `tee` (a rule breach, reported to the
  orchestrator); the output quoted below is the run's own stdout.

## 1. The local reopen assignment (`_reopen_local_lane`, `wave_watch.py`, `live_lanes[lid] = {...}`)

- **Axis:** a started, outcome-terminal local lane whose builder is running again is added to the live set, so
  it is watched like a live local lane.
- **Neutralization:** `live_lanes[lid] = {**info, "pid": reopened[0], "reopenedAt": basis, "reopenedBy": reopened[1]}`
  became `pass`.
- **Raw red** (`-k "row1_the_process_signal or row2_a_builder_comment_after"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FFFFF                                                                    [100%]
=================================== FAILURES ===================================
E   KeyError: 'local-a'
/home/user/sh-2410/plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py:113: KeyError: 'local-a'
E   KeyError: 'local-a'
/home/user/sh-2410/plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py:135: KeyError: 'local-a'
E   KeyError: 'local-a'
/home/user/sh-2410/plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py:135: KeyError: 'local-a'
E   KeyError: 'local-a'
/home/user/sh-2410/plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py:135: KeyError: 'local-a'
E   KeyError: 'local-a'
/home/user/sh-2410/plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py:135: KeyError: 'local-a'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py::test_row1_the_process_signal_reopens_by_builder_process_and_replaces_the_recorded_pid
FAILED plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py::test_row2_a_builder_comment_after_the_basis_reopens_the_lane_as_builder_comment[note]
FAILED plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py::test_row2_a_builder_comment_after_the_basis_reopens_the_lane_as_builder_comment[handback]
FAILED plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py::test_row2_a_builder_comment_after_the_basis_reopens_the_lane_as_builder_comment[stop]
FAILED plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py::test_row2_a_builder_comment_after_the_basis_reopens_the_lane_as_builder_comment[park]
5 failed, 56 deselected in 1.19s
```

- **Restore:** the inverse Edit put the assignment back.
- **Restore receipt** (restored lines quoted):
  `live_lanes[lid] = {**info, "pid": reopened[0], "reopenedAt": basis, "reopenedBy": reopened[1]}`
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.....                                                                    [100%]
5 passed, 56 deselected in 1.35s
```

## 2. The session-flag identity rule (`_resumed_session_pid`, `_names_session`)

- **Axis:** a process matches only when the session id is the value of a session flag (`--resume`, `-r`,
  `--session-id`, or their `=` forms); a bare id elsewhere, or a longer id it prefixes, is no match.
- **Neutralization:** `if _names_session(parts[1].split(), session_id):` became `if session_id in parts[1]:`
  (the session id anywhere in the command).
- **Raw red** (`-k "row6_a_session_id_anywhere"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FF.FFF                                                                   [100%]
=================================== FAILURES ===================================
E   assert (4242, False) == (None, False)
      
      At index 0 diff: 4242 != None
      Use -v to get more diff
/home/user/sh-2410/plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py:370: assert (4242, False) == (None, False)
E   assert (4242, False) == (None, False)
      
      At index 0 diff: 4242 != None
      Use -v to get more diff
/home/user/sh-2410/plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py:370: assert (4242, False) == (None, False)
E   assert (4242, False) == (None, False)
      
      At index 0 diff: 4242 != None
      Use -v to get more diff
/home/user/sh-2410/plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py:370: assert (4242, False) == (None, False)
E   assert (4242, False) == (None, False)
      
      At index 0 diff: 4242 != None
      Use -v to get more diff
/home/user/sh-2410/plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py:370: assert (4242, False) == (None, False)
E   assert (4242, False) == (None, False)
      
      At index 0 diff: 4242 != None
      Use -v to get more diff
/home/user/sh-2410/plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py:370: assert (4242, False) == (None, False)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py::test_row6_a_session_id_anywhere_but_a_session_flags_value_does_not_match[rg 5f0e8c1a-2b3d-4e6f-8a9b-0c1d2e3f4a5b dir]
FAILED plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py::test_row6_a_session_id_anywhere_but_a_session_flags_value_does_not_match[echo 5f0e8c1a-2b3d-4e6f-8a9b-0c1d2e3f4a5b]
FAILED plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py::test_row6_a_session_id_anywhere_but_a_session_flags_value_does_not_match[claude --model 5f0e8c1a-2b3d-4e6f-8a9b-0c1d2e3f4a5b]
FAILED plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py::test_row6_a_session_id_anywhere_but_a_session_flags_value_does_not_match[claude --resume 5f0e8c1a-2b3d-4e6f-8a9b-0c1d2e3f4a5bX]
FAILED plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py::test_row6_a_session_id_anywhere_but_a_session_flags_value_does_not_match[claude --resume-x=5f0e8c1a-2b3d-4e6f-8a9b-0c1d2e3f4a5b]
5 failed, 1 passed, 55 deselected in 3.39s
```

- **Restore:** the inverse Edit put the call back.
- **Restore receipt** (restored line quoted): `if _names_session(parts[1].split(), session_id):`
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
......                                                                   [100%]
6 passed, 55 deselected in 0.51s
```

## 3. The replaced pre-resume pid (`_reopen_local_lane`, the `"pid"` of the reopened lane)

- **Axis:** a reopened lane's recorded pid is replaced by the resumed process's pid (or None), so the pid
  recorded before the resume never fires `builder-exited`.
- **Neutralization:** `{**info, "pid": reopened[0], "reopenedAt": ...}` became
  `{**info, "pid": info.get("pid"), "reopenedAt": ...}` (keep the recorded pid).
- **Raw red** (`-k "row4_a_lane_reopened_by_a_heartbeat or row1_the_process_signal"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FF                                                                       [100%]
=================================== FAILURES ===================================
E   AssertionError: assert ('builder-process', 999999999) == ('builder-process', 4242)
      
      At index 1 diff: 999999999 != 4242
      Use -v to get more diff
/home/user/sh-2410/plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py:114: AssertionError: assert ('builder-process', 999999999) == ('builder-process', 4242)
E   AssertionError: {'ok': True, 'event': 'builder-exited', 'batchId': 'batch-cloud', 'degraded': [], ...}
    assert 'builder-exited' == 'timer'
      
      - timer
      + builder-exited
/home/user/sh-2410/plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py:232: AssertionError: {'ok': True, 'event': 'builder-exited', 'batchId': 'batch-cloud', 'degraded': [], ...}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py::test_row1_the_process_signal_reopens_by_builder_process_and_replaces_the_recorded_pid
FAILED plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py::test_row4_a_lane_reopened_by_a_heartbeat_does_not_fire_builder_exited_for_the_recorded_pid
2 failed, 59 deselected in 0.97s
```

- **Restore:** the inverse Edit put the replacement back.
- **Restore receipt** (restored text quoted): `{**info, "pid": reopened[0], "reopenedAt": basis, "reopenedBy": reopened[1]}`
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..                                                                       [100%]
2 passed, 59 deselected in 0.76s
```

## 4. The heartbeat guard (`_evaluate_lane_heartbeats`)

- **Axis:** a reopened local lane's heartbeat stamped at or before its basis contributes no terminal, no blocked
  and no `hb_states` entry, so the stamp of the outcome never re-fires.
- **Neutralization:** `if "reopenedAt" in live_lanes[lid] and not _heartbeat_stamped_after(` became
  `if False and "reopenedAt" in live_lanes[lid] and not _heartbeat_stamped_after(`.
- **Raw red** (`-k "row5_a_heartbeat_stamped_before"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FFF                                                                      [100%]
=================================== FAILURES ===================================
E   AssertionError: {'ok': True, 'event': 'lane-terminal', 'batchId': 'batch-cloud', 'degraded': [], ...}
    assert 'lane-terminal' == 'timer'
      
      - timer
      + lane-terminal
/home/user/sh-2410/plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py:307: AssertionError: {'ok': True, 'event': 'lane-terminal', 'batchId': 'batch-cloud', 'degraded': [], ...}
E   AssertionError: {'ok': True, 'event': 'lane-terminal', 'batchId': 'batch-cloud', 'degraded': [], ...}
    assert 'lane-terminal' == 'timer'
      
      - timer
      + lane-terminal
/home/user/sh-2410/plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py:307: AssertionError: {'ok': True, 'event': 'lane-terminal', 'batchId': 'batch-cloud', 'degraded': [], ...}
E   AssertionError: {'ok': True, 'event': 'lane-blocked', 'batchId': 'batch-cloud', 'degraded': [], ...}
    assert 'lane-blocked' == 'timer'
      
      - timer
      + lane-blocked
/home/user/sh-2410/plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py:307: AssertionError: {'ok': True, 'event': 'lane-blocked', 'batchId': 'batch-cloud', 'degraded': [], ...}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py::test_row5_a_heartbeat_stamped_before_the_basis_fires_nothing_for_a_resumed_lane[handback]
FAILED plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py::test_row5_a_heartbeat_stamped_before_the_basis_fires_nothing_for_a_resumed_lane[parked]
FAILED plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py::test_row5_a_heartbeat_stamped_before_the_basis_fires_nothing_for_a_resumed_lane[blocked]
3 failed, 58 deselected in 0.83s
```

- **Restore:** the inverse Edit removed `False and`.
- **Restore receipt** (restored line quoted): `if "reopenedAt" in live_lanes[lid] and not _heartbeat_stamped_after(`
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
...                                                                      [100%]
3 passed, 58 deselected in 0.83s
```

## 5. The retained pid (`_reopen_local_lane`, item 5b)

- **Axis:** a resumed process seen once in a loop is kept at the basis it was seen at, so its exit fires
  `builder-exited` on a later tick or arm; a retained pid of another basis is dropped.
- **Neutralization:** `if isinstance(retained, tuple) and len(retained) == 2 and retained[0] == basis:` became
  `if False and isinstance(retained, tuple) and len(retained) == 2 and retained[0] == basis:` (the retained pid
  is never used).
- **Raw red** (`-k "row4_a_resumed_process_seen_once or row4_a_loop_keeps"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FF                                                                       [100%]
=================================== FAILURES ===================================
E   AssertionError: {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': ['builder-note-unavailable']}
    assert 'timer' == 'builder-exited'
      
      - builder-exited
      + timer
/home/user/sh-2410/plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py:249: AssertionError: {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': ['builder-note-unavailable']}
E   AssertionError: {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': ['builder-note-unavailable'], ...}
    assert 'timer' == 'builder-exited'
      
      - builder-exited
      + timer
/home/user/sh-2410/plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py:269: AssertionError: {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': ['builder-note-unavailable']}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py::test_row4_a_resumed_process_seen_once_fires_builder_exited_with_its_own_pid_when_it_ends
FAILED plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py::test_row4_a_loop_keeps_the_resumed_pid_across_arms
2 failed, 59 deselected in 2.87s
```

- **Restore:** the inverse Edit removed `False and`.
- **Restore receipt** (restored line quoted): `if isinstance(retained, tuple) and len(retained) == 2 and retained[0] == basis:`
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..                                                                       [100%]
2 passed, 59 deselected in 0.83s
```

## 6. The comment signal (`_reopen_local_lane` -> `_local_builder_comment`)

- **Axis:** a builder note, an ending, or a resumed progress edit on the lane's issue after the basis reopens
  the lane as `builder-comment`.
- **Neutralization:** `elif _local_builder_comment(comments, lid, info, basis):` became
  `elif False and _local_builder_comment(comments, lid, info, basis):`.
- **Raw red** (`-k "row2"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FFFF.....F..                                                             [100%]
=================================== FAILURES ===================================
E   KeyError: 'local-a'
/home/user/sh-2410/plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py:135: KeyError: 'local-a'
E   KeyError: 'local-a'
/home/user/sh-2410/plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py:135: KeyError: 'local-a'
E   KeyError: 'local-a'
/home/user/sh-2410/plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py:135: KeyError: 'local-a'
E   KeyError: 'local-a'
/home/user/sh-2410/plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py:135: KeyError: 'local-a'
E   KeyError: 'local-a'
/home/user/sh-2410/plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py:180: KeyError: 'local-a'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py::test_row2_a_builder_comment_after_the_basis_reopens_the_lane_as_builder_comment[note]
FAILED plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py::test_row2_a_builder_comment_after_the_basis_reopens_the_lane_as_builder_comment[handback]
FAILED plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py::test_row2_a_builder_comment_after_the_basis_reopens_the_lane_as_builder_comment[stop]
FAILED plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py::test_row2_a_builder_comment_after_the_basis_reopens_the_lane_as_builder_comment[park]
FAILED plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py::test_row2b_a_progress_comment_updated_after_the_grace_with_a_resumed_phase_reopens
5 failed, 7 passed, 49 deselected in 1.52s
```

- **Restore:** the inverse Edit removed `False and`.
- **Restore receipt** (restored line quoted): `elif _local_builder_comment(comments, lid, info, basis):`
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
............                                                             [100%]
12 passed, 49 deselected in 1.65s
```

## 7. The relaunch exclusion for a local lane (`_dormant_basis`, called with `place=local`)

- **Axis:** a local lane relaunched on its issue (a later launch reserved there, in any batch) is never reopened.
- **Neutralization:** `if (other_id != lid and other.get("issue") == info.get("issue")` became
  `if (False and other_id != lid and other.get("issue") == info.get("issue")`.
- **Raw red** (`-k "row7"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
E   AssertionError: assert {'local-a', 'local-b'} == {'local-b'}
      
      Extra items in the left set:
      'local-a'
      Use -v to get more diff
/home/user/sh-2410/plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py:440: AssertionError: assert {'local-a', 'local-b'} == {'local-b'}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py::test_row7_a_local_lane_relaunched_on_its_issue_is_not_reopened
1 failed, 60 deselected in 0.60s
```

- **Restore:** the inverse Edit removed `False and`.
- **Restore receipt** (restored line quoted): `if (other_id != lid and other.get("issue") == info.get("issue")`
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 60 deselected in 0.69s
```

## 8. One clock sample for a heartbeat's stamp (`_heartbeat_stamped_after`)

Added at review (round 1 finding "Use one clock sample when recovering the heartbeat timestamp"; the round 2
audit showed the first version of the test passed on the original code, so the test was rewritten to sample
the clock inside the fake reader, as `heartbeat.py` does). Run by the build session in a detached probe
worktree at `9b32b704`, with `--tb=line`; captures trimmed to their last lines (the `UV_NATIVE_TLS` line and
the progress dots are dropped).

- **Axis:** the read and the subtraction use one clock sample, so the read's latency never moves an old stamp past the basis.
- **Neutralization:** the helper restored to the original two-sample code: `now = time.time()` removed,
  `hb.read_heartbeat(repo_root, lid, env=env, now=now)` became `hb.read_heartbeat(repo_root, lid, env=env)`,
  and `now - age > basis` became `time.time() - age > basis`.
- **Raw red** (`-k "clock_sample_its_age"`):

```
/home/user/sh-2410-probe/plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py:514: AssertionError: assert True is False
FAILED plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py::test_the_heartbeat_stamp_time_uses_the_clock_sample_its_age_was_read_at
1 failed, 63 deselected in 5.35s
```

- **Restore:** the inverse Edit; `git status --short` in the probe worktree printed nothing.
- **Raw green** (selector of elements 8 and 9 together): `3 passed, 61 deselected in 0.76s`.

## 9. The terminal local lanes' comment-read share (`_evaluate_tick`, `read_lane_comments`)

Added at review (the seams-check finding "Reserve polling time before reading terminal local lanes" and its
sweep hit; the round 2 audit showed a one-second arm still handed the read its whole window). Same probe
worktree and capture rule as element 8.

- **Axis:** a closed local lane's comment reads share a quarter of the tick, and a share under one request's minimum makes no request.
- **Neutralization:** the share check (`if local_share[0] - monotonic() < _MIN_PR_POLL_SECONDS: return None, []`)
  removed and `local_share[0]` passed as `deadline` (the whole tick deadline, the original shape).
- **Raw red** (`-k "quarter_of_the_tick or too_short_to_share"`):

```
/home/user/sh-2410-probe/plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py:500: AssertionError: assert [('/tmp/pytes...4f20f0>, ...)] == []
FAILED plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py::test_a_terminal_local_lanes_comment_read_gets_a_quarter_of_the_tick_not_its_whole_budget
FAILED plugins/superheroes/lib/tests/test_wave_watch_local_resume_2410.py::test_a_tick_too_short_to_share_makes_no_comment_read_and_discloses_it
2 failed, 62 deselected in 8.14s
```

- **Restore:** the inverse Edit; `git status --short` in the probe worktree printed nothing.
- **Raw green:** as element 8.
