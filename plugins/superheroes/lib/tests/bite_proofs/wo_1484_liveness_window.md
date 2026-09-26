# Bite-proof record — WO-A4 (#1484) transcript liveness quiet window

**Guarded-element set (declared in the work order):** (1) `_transcript_cold` treats a transcript older than `LIVENESS_QUIET_WINDOW_SECONDS` as stale — detectors `test_lane_stale_cold_transcript_ten_thousand_seconds`, `test_transcript_cold_boundary_inclusive_at_quiet_window`; (2) `_transcript_cold` fail-toward-alert when transcript mtime is None (unresolved/absent/no session id) — detector `test_lane_stale_no_session_id_on_record`.

**Command:** each run used the exact node id(s) below, never `-k`:

```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc-woA4 -m pytest <node id(s)> -q
```

## 1 — quiet-window freshness (outside window is stale)

- **Guarded element:** `plugins/superheroes/lib/wave_watch.py` `_transcript_cold` (~723), axis: FRESHNESS of the transcript against `LIVENESS_QUIET_WINDOW_SECONDS` — written inside the window is live, outside it is wedged.
- **Neutralization:**

```
-        if transcript_age > LIVENESS_QUIET_WINDOW_SECONDS:
+        if False and transcript_age > LIVENESS_QUIET_WINDOW_SECONDS:
```

- **Nodes:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_lane_stale_cold_transcript_ten_thousand_seconds`, `plugins/superheroes/lib/tests/test_wave_watch.py::test_transcript_cold_boundary_inclusive_at_quiet_window`
- **Raw red** (exit 1):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_____________ test_lane_stale_cold_transcript_ten_thousand_seconds _____________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-8226/test_lane_stale_cold_transcrip0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x1071295e0>

    def test_lane_stale_cold_transcript_ten_thousand_seconds(tmp_path, monkeypatch):
        repo = _init_repo(tmp_path / "repo")
        _setup_stale_lane(repo, tmp_path, monkeypatch, transcript_age_seconds=10_000)
        result = ww.watch_arm(
            repo, "batch-982", max_seconds=2, interval_seconds=60, gh_run=_noop_gh_run,
        )
>       assert result["event"] == "lane-stale"
E       AssertionError: assert 'timer' == 'lane-stale'
E         
E         - lane-stale
E         + timer

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1484-0ea554da281732f2/plugins/superheroes/lib/tests/test_wave_watch.py:1308: AssertionError
___________ test_transcript_cold_boundary_inclusive_at_quiet_window ____________

    def test_transcript_cold_boundary_inclusive_at_quiet_window():
        ...
>       assert len(one_past) == 1
E       assert 0 == 1
E        +  where 0 = len([])

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1484-0ea554da281732f2/plugins/superheroes/lib/tests/test_wave_watch.py:1344: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch.py::test_lane_stale_cold_transcript_ten_thousand_seconds
FAILED plugins/superheroes/lib/tests/test_wave_watch.py::test_transcript_cold_boundary_inclusive_at_quiet_window
2 failed in 11.43s
```

- **Restore:** remove `False and ` from the window comparison (inverse of neutralization). Restored line:

```
        if transcript_age > LIVENESS_QUIET_WINDOW_SECONDS:
```

- **Raw green** (exit 0):

```
..                                                                       [100%]
2 passed in 11.07s
```

## 2 — fail toward alert when transcript mtime is None

- **Guarded element:** `plugins/superheroes/lib/wave_watch.py` `_transcript_cold` (~701), axis: DIRECTION of failure — an unresolvable transcript alerts, never suppresses.
- **Neutralization** (replace the `mtime is None` branch body so unresolved counts as fresh):

```
         if mtime is None:
-            still_stale.append({
-                "launchId": lid,
-                "state": hb_states.get(lid),
-                "transcriptAgeSeconds": None,
-                "quietWindowSeconds": LIVENESS_QUIET_WINDOW_SECONDS,
-            })
             continue
```

- **Node:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_lane_stale_no_session_id_on_record`
- **Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_lane_stale_no_session_id_on_record ____________________

    def test_lane_stale_no_session_id_on_record(tmp_path, monkeypatch):
        ...
>       assert result["event"] == "lane-stale"
E       AssertionError: assert 'timer' == 'lane-stale'
E         
E         - lane-stale
E         + timer

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1484-0ea554da281732f2/plugins/superheroes/lib/tests/test_wave_watch.py:1319: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch.py::test_lane_stale_no_session_id_on_record
1 failed in 9.50s
```

- **Restore:** reinstate the `still_stale.append({...})` block before `continue`. Restored lines:

```
        if mtime is None:
            still_stale.append({
                "launchId": lid,
                "state": hb_states.get(lid),
                "transcriptAgeSeconds": None,
                "quietWindowSeconds": LIVENESS_QUIET_WINDOW_SECONDS,
            })
            continue
```

- **Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 8.91s
```

## 3 — startup grace for absent transcript (inside window is not stale)

- **Guarded element:** `plugins/superheroes/lib/wave_watch.py` `_transcript_cold` (~704), axis: STARTUP GRACE — plain absence before the first transcript line is not stale while the lane is still inside the quiet window from start.
- **Neutralization:**

```
-            if not ambiguous and not unresolved:
+            if False and not ambiguous and not unresolved:
```

- **Node:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_absent_transcript_inside_startup_grace_no_lane_stale`
- **Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_absent_transcript_inside_startup_grace_no_lane_stale ___________

    def test_absent_transcript_inside_startup_grace_no_lane_stale(tmp_path, monkeypatch):
        ...
>       assert result["event"] == "timer"
E       AssertionError: assert 'lane-stale' == 'timer'
E         
E         - timer
E         + lane-stale

=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch.py::test_absent_transcript_inside_startup_grace_no_lane_stale
1 failed in 13.77s
```

- **Restore:** remove `False and ` from the grace guard (inverse of neutralization). Restored line:

```
            if not ambiguous and not unresolved:
```

- **Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 9.32s
```

## 4 — startup grace upper bound (past window is stale)

- **Guarded element:** `plugins/superheroes/lib/wave_watch.py` `_transcript_cold` (~713), axis: STARTUP GRACE — absence suppresses only while `0 <= startup_age <= LIVENESS_QUIET_WINDOW_SECONDS`.
- **Neutralization:**

```
-                        if 0 <= startup_age <= LIVENESS_QUIET_WINDOW_SECONDS:
+                        if 0 <= startup_age:
```

- **Node:** `plugins/superheroes/lib/tests/test_wave_watch.py::test_absent_transcript_past_startup_grace_emits_lane_stale`
- **Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_absent_transcript_past_startup_grace_emits_lane_stale __________

    def test_absent_transcript_past_startup_grace_emits_lane_stale(tmp_path, monkeypatch):
        ...
>       assert result["event"] == "lane-stale"
E       AssertionError: assert 'timer' == 'lane-stale'
E         
E         - lane-stale
E         + timer

=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch.py::test_absent_transcript_past_startup_grace_emits_lane_stale
1 failed in 13.60s
```

- **Restore:** reinstate the `<= LIVENESS_QUIET_WINDOW_SECONDS` upper bound. Restored line:

```
                        if 0 <= startup_age <= LIVENESS_QUIET_WINDOW_SECONDS:
```

- **Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 7.11s
```
