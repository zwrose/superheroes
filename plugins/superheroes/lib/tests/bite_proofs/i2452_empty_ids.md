# i2452 bite-proof: an empty identifier never counts as a match

Bite-proof record `i2452_empty_ids` for the detectors in `plugins/superheroes/lib/tests/test_empty_ids_2452.py` (issue 2452). Six guarded elements, each neutralized alone in production code, run red on one named node, restored by the inverse edit, run green on the same node.

**Run command.** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2452 -m pytest <node> -q -p no:cacheprovider`. The harness's `UV_NATIVE_TLS` deprecation line is left out of each capture; every pytest line is as printed. Each neutralization is a targeted Edit and each restore is the inverse Edit. No capture is near the 32 KiB ceiling. Nothing in the captures needed redaction: they hold only temporary test paths.

**Order of work (disclosed).** The order asked for one run of the new module on the base code before the change. The production edits were made before the test module existed, so no base-code run was made. Each red below is the node run against the base form of its one guarded line, which is the same evidence for that element. D3 and the healthy-sibling nodes were not run against base.

## Summary

| Element | Axis | Proving node | Verdict |
|---|---|---|---|
| N1 | `cloud_parked._lapses` refuses an `environment` that is present but empty or not a string | `test_d1_an_empty_environment_reads_no_lapse_date_even_when_a_record_has_one` | proven |
| N2 | `cloud_recover._push_time` counts an event only when its `ref` is the branch's own string | `test_d4_a_push_event_with_no_ref_gives_no_push_time` | proven |
| N3 | `launcher._listing_row_ok` needs a non-empty string `id` | `test_d5_a_listing_row_with_an_empty_id_is_not_ok` | proven |
| N4 | `launcher._page_created_by_environment` leaves an empty `environment_id` out of the map | `test_d6_a_row_with_an_empty_environment_id_is_left_out_of_the_map` | proven |
| N5 | the lane side: an empty `cloudEnvironment` gives no `newest` | `test_d7_a_lane_with_an_empty_cloud_environment_is_not_proven_gone_whatever_the_map_holds` | proven, see the note on N5 |
| N6 | the lane side: an empty `cloudSessionId` is unconfirmed (title match, absence never proves it gone) | `test_d8_a_lane_with_an_empty_session_id_is_never_proven_gone` | proven |

## N1: `_lapses` refuses a present-but-empty environment

- **Guarded element and axis.** `cloud_parked.py` `_lapses`, the early `if environment is not None and not (isinstance(environment, str) and environment): return None`. A present but empty (or non-string) environment is unread and matches no record; `None` (the no-lane caller) is untouched.
- **Neutralization applied.** `if environment is not None and not (isinstance(environment, str) and environment):` replaced with `if False and environment is not None and not (isinstance(environment, str) and environment):`.
- **Node.** `plugins/superheroes/lib/tests/test_empty_ids_2452.py::test_d1_an_empty_environment_reads_no_lapse_date_even_when_a_record_has_one`
- **Note.** The later record check (`isinstance(environment, str) and environment and record.get(...) != environment`) is kept in its base form, so the early guard is the only thing that refuses `""`.
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_d1_an_empty_environment_reads_no_lapse_date_even_when_a_record_has_one __

w = namespace(repo='/tmp/claude-0/pytest-of-root/pytest-10/test_d1_an_empty_environment_r0/repo', store='/tmp/claude-0/pyt..._empty_environment_r0/home'), root=PosixPath('/tmp/claude-0/pytest-of-root/pytest-10/test_d1_an_empty_environment_r0'))

    def test_d1_an_empty_environment_reads_no_lapse_date_even_when_a_record_has_one(w):
        # axis: an environment that is present but empty is unread and matches no record — see bite-proof record i2452_empty_ids
        assert CP._lapses(w.repo, w.env, None, ENVIRONMENT) == PAST  # the record exists and has a date
>       assert CP._lapses(w.repo, w.env, None, "") is None
E       AssertionError: assert '2026-10-05' is None
E        +  where '2026-10-05' = <function _lapses at 0x7fcdfd3d1f80>('/tmp/claude-0/pytest-of-root/pytest-10/test_d1_an_empty_environment_r0/repo', {'HOME': '/tmp/claude-0/pytest-of-root/pytest-10/test_d1_an_empty_environment_r0/home', 'PATH': '/root/.cache/uv/build...'SUPERHEROES_LAUNCH_LEDGER_ROOT': '/tmp/claude-0/pytest-of-root/pytest-10/test_d1_an_empty_environment_r0/ledger-root'}, None, '')
E        +    where <function _lapses at 0x7fcdfd3d1f80> = CP._lapses
E        +    and   '/tmp/claude-0/pytest-of-root/pytest-10/test_d1_an_empty_environment_r0/repo' = namespace(repo='/tmp/claude-0/pytest-of-root/pytest-10/test_d1_an_empty_environment_r0/repo', store='/tmp/claude-0/pyt..._empty_environment_r0/home'), root=PosixPath('/tmp/claude-0/pytest-of-root/pytest-10/test_d1_an_empty_environment_r0')).repo
E        +    and   {'HOME': '/tmp/claude-0/pytest-of-root/pytest-10/test_d1_an_empty_environment_r0/home', 'PATH': '/root/.cache/uv/build...'SUPERHEROES_LAUNCH_LEDGER_ROOT': '/tmp/claude-0/pytest-of-root/pytest-10/test_d1_an_empty_environment_r0/ledger-root'} = namespace(repo='/tmp/claude-0/pytest-of-root/pytest-10/test_d1_an_empty_environment_r0/repo', store='/tmp/claude-0/pyt..._empty_environment_r0/home'), root=PosixPath('/tmp/claude-0/pytest-of-root/pytest-10/test_d1_an_empty_environment_r0')).env

/home/user/wt-2452-wo3/plugins/superheroes/lib/tests/test_empty_ids_2452.py:50: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_empty_ids_2452.py::test_d1_an_empty_environment_reads_no_lapse_date_even_when_a_record_has_one
1 failed in 3.04s
```

- **Restore.** The inverse Edit. Restored line, quoted back from `cloud_parked.py:197` (a grep of the file after the edit):

```
    if environment is not None and not (isinstance(environment, str) and environment):
```

- **Raw green:**

```
.                                                                        [100%]
1 passed in 2.96s
```

## N2: `_push_time` requires the event's own string ref

- **Guarded element and axis.** `cloud_recover.py` `_push_time`, the `isinstance(e.get("ref"), str) and e["ref"] == ref` test. An event supplies the push time only when its `ref` is a string equal to `refs/heads/<name>`; a missing, empty, null or non-string `ref` no longer counts.
- **Neutralization applied.** `and isinstance(e.get("ref"), str) and e["ref"] == ref), None)` replaced with `and (not isinstance(e.get("ref"), str) or e["ref"] == ref)), None)` (the base form).
- **Node.** `plugins/superheroes/lib/tests/test_empty_ids_2452.py::test_d4_a_push_event_with_no_ref_gives_no_push_time`
- **Note.** The `""` and `None` rows (parametrized node `test_d4_a_push_event_whose_ref_is_empty_or_not_the_branchs_gives_no_push_time`) were not run under this neutralization. Under the base form a `""` ref fails `e["ref"] == ref` and so already gave no time; only a missing, null or non-string ref was ever let through. The no-ref node is the discriminating one.
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_d4_a_push_event_with_no_ref_gives_no_push_time ______________

    def test_d4_a_push_event_with_no_ref_gives_no_push_time():
        # axis: an event supplies the push time only when its ref is the branch's own; a missing ref does not — see bite-proof record i2452_empty_ids
        event = _event(BRANCH, SHA, _stamp(9, 55))
        del event["ref"]
>       assert CRV._push_time(REPO, BRANCH, SHA, {}, _push_events([event])) is None
E       AssertionError: assert 1791798900.0 is None
E        +  where 1791798900.0 = <function _push_time at 0x7f49a5fb0d60>('owner/repo', 'issue-17-work', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', {}, <test_cloud_recover.Gh object at 0x7f49a72821e0>)
E        +    where <function _push_time at 0x7f49a5fb0d60> = CRV._push_time
E        +    and   <test_cloud_recover.Gh object at 0x7f49a72821e0> = _push_events([{'after': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'before': '0000000000000000000000000000000000000000', 'timestamp': '2026-10-12T09:55:00Z', 'activity_type': 'push', ...}])

/home/user/wt-2452-wo3/plugins/superheroes/lib/tests/test_empty_ids_2452.py:82: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_empty_ids_2452.py::test_d4_a_push_event_with_no_ref_gives_no_push_time
1 failed in 2.81s
```

- **Restore.** The inverse Edit. Restored line, quoted back from the `git diff` of `cloud_recover.py` taken after all six proofs:

```
+                 and isinstance(e.get("ref"), str) and e["ref"] == ref), None)
```

- **Raw green:**

```
.                                                                        [100%]
1 passed in 2.90s
```

## N3: `_listing_row_ok` needs a non-empty id

- **Guarded element and axis.** `launcher.py` `_listing_row_ok`, the `or not row["id"]` leg. A row whose `id` is empty is not a recorded host shape, so the listing reads as not a host shape (the caller refuses `listing-shape`).
- **Neutralization applied.** `if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:` replaced with `if not isinstance(row, dict) or not isinstance(row.get("id"), str):`.
- **Node.** `plugins/superheroes/lib/tests/test_empty_ids_2452.py::test_d5_a_listing_row_with_an_empty_id_is_not_ok`
- **Note.** The end-to-end node `test_d5_a_listing_holding_a_row_with_an_empty_id_refuses_listing_shape` was not run under this neutralization (budget); the unit node is the one with the red and green below.
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_d5_a_listing_row_with_an_empty_id_is_not_ok _______________

    def test_d5_a_listing_row_with_an_empty_id_is_not_ok():
        # axis: a row whose id is empty is not a recorded host shape — see bite-proof record i2452_empty_ids
>       assert L._listing_row_ok({"id": ""}) is False
E       AssertionError: assert True is False
E        +  where True = <function _listing_row_ok at 0x7fc0bbd802c0>({'id': ''})
E        +    where <function _listing_row_ok at 0x7fc0bbd802c0> = L._listing_row_ok

/home/user/wt-2452-wo3/plugins/superheroes/lib/tests/test_empty_ids_2452.py:102: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_empty_ids_2452.py::test_d5_a_listing_row_with_an_empty_id_is_not_ok
1 failed in 2.83s
```

- **Restore.** The inverse Edit. Restored line, quoted back from the `git diff` of `launcher.py` taken after all six proofs:

```
+    if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
```

- **Raw green:**

```
.                                                                        [100%]
1 passed in 2.55s
```

## N4: `_page_created_by_environment` leaves an empty key out

- **Guarded element and axis.** `launcher.py` `_page_created_by_environment`, the `and env_id` leg. A row whose `environment_id` is empty is left out of the map, like a row with none.
- **Neutralization applied.** `if isinstance(env_id, str) and env_id and stamp > newest.get(env_id, float("-inf")):` replaced with `if isinstance(env_id, str) and stamp >newest.get(env_id, float("-inf")):` (the edit tool dropped the space after `>`; the line still parses and reads as the base condition).
- **Node.** `plugins/superheroes/lib/tests/test_empty_ids_2452.py::test_d6_a_row_with_an_empty_environment_id_is_left_out_of_the_map`
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_d6_a_row_with_an_empty_environment_id_is_left_out_of_the_map _______

    def test_d6_a_row_with_an_empty_environment_id_is_left_out_of_the_map():
        # axis: a row whose environment_id is empty is left out of the map, like a row with none — see bite-proof record i2452_empty_ids
        empty = _unrelated_row(NEWER, "session_01Empty00000000000000", environment_id="")
        real = _unrelated_row("2026-10-24T12:30:00.000000Z", "session_01Real000000000000000", environment_id="env-1")
        got = L._page_created_by_environment([_page_of([empty, real])])
>       assert "" not in got
E       AssertionError: assert '' not in {'': 1792846800.0, 'env-1': 1792845000.0}

/home/user/wt-2452-wo3/plugins/superheroes/lib/tests/test_empty_ids_2452.py:133: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_empty_ids_2452.py::test_d6_a_row_with_an_empty_environment_id_is_left_out_of_the_map
1 failed in 2.89s
```

- **Restore.** The inverse Edit (the first restore attempt did not match because of the dropped space; the second matched the actual text `stamp >newest.get` and replaced it). Restored line, quoted back from the `git diff` of `launcher.py` taken after all six proofs:

```
+        if isinstance(env_id, str) and env_id and stamp > newest.get(env_id, float("-inf")):
```

- **Raw green:**

```
.                                                                        [100%]
1 passed in 2.63s
```

## N5: a lane with an empty `cloudEnvironment` gets no `newest`

- **Guarded element and axis.** `launcher.py` `_original_session_pass`, the `and lane_env` leg in the `newest = (...)` expression. A lane whose `cloudEnvironment` is empty proves nothing by absence.
- **Neutralization applied.** `if created_by_env is not None and isinstance(lane_env, str) and lane_env else None` replaced with `if created_by_env is not None and isinstance(lane_env, str) else None`.
- **Node.** `plugins/superheroes/lib/tests/test_empty_ids_2452.py::test_d7_a_lane_with_an_empty_cloud_environment_is_not_proven_gone_whatever_the_map_holds`
- **Note, an order gap found while proving.** The order's D7 as written (`test_d7_a_lane_with_an_empty_cloud_environment_is_not_proven_gone_by_rows_with_an_empty_environment_id`) fails on the base code but is shielded under N5 alone: with N4's skip in place the by-environment map never holds an empty key, so `created_by_env.get("")` is `None` whatever the lane-side predicate says. The two guards are redundant for that test. The node above stubs `_page_created_by_environment` to return a map that does hold an empty key, so the lane-side predicate is the only guard left. The order's D7 node was not run under N5 (it would stay green); it is the end-to-end node for the pair.
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_d7_a_lane_with_an_empty_cloud_environment_is_not_proven_gone_whatever_the_map_holds _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-19/test_d7_a_lane_with_an_empty_c0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7faedd4a29f0>

    def test_d7_a_lane_with_an_empty_cloud_environment_is_not_proven_gone_whatever_the_map_holds(
        tmp_path, monkeypatch,
    ):
        # axis: a lane whose cloudEnvironment is empty proves nothing by absence on its own, even when the by-environment map holds an empty key (the map's own skip is a second guard that shields the test above) — see bite-proof record i2452_empty_ids
        repo = _cloud_repo(tmp_path)
        _seed_lane(repo)
        _fold_lane_with(monkeypatch, cloudEnvironment="")
        newer = L._listing_created_ts(_unrelated_row(NEWER))
        monkeypatch.setattr(L, "_page_created_by_environment", lambda pages: {"": newer})
        rows = [_unrelated_row(NEWER, environment_id="")]
        result, calls = _adopt(repo, tmp_path, _write_listing(tmp_path, _page_of(rows)))
>       _refused_unread(repo, result, calls, "listing-incomplete")

/home/user/wt-2452-wo3/plugins/superheroes/lib/tests/test_empty_ids_2452.py:177: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt-2452-wo3/plugins/superheroes/lib/tests/test_adopt_original_session.py:149: in _refused_unread
    _assert_refused_cloud_lane(repo, result, TOKEN_UNREAD, "original-session")
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-19/test_d7_a_lane_with_an_empty_c0/repo'
result = {'ok': True, 'reason': None, 'launchId': 'launch-2d672320d61b9650', 'place': 'cloud', ...}
reason = 'adopt-original-session-unread', stage = 'original-session'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
>       assert result["ok"] is False
E       assert True is False

/home/user/wt-2452-wo3/plugins/superheroes/lib/tests/test_launcher_cloud.py:653: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_empty_ids_2452.py::test_d7_a_lane_with_an_empty_cloud_environment_is_not_proven_gone_whatever_the_map_holds
1 failed in 10.69s
```

- **Restore.** The inverse Edit. Restored lines, quoted back from the `git diff` of `launcher.py` taken after all six proofs:

```
+                if created_by_env is not None and isinstance(lane_env, str) and lane_env else None
```

- **Raw green:**

```
.                                                                        [100%]
1 passed in 2.78s
```

## N6: a lane with an empty `cloudSessionId` is unconfirmed

- **Guarded element and axis.** `launcher.py` `_original_session_pass`, `confirmed = isinstance(session_id, str) and bool(session_id)`, used for both decisions: matched by id only when confirmed (by title otherwise), and `or not confirmed` keeps absence from proving an unconfirmed lane gone.
- **Neutralization applied.** `confirmed = isinstance(session_id, str) and bool(session_id)` replaced with `confirmed = session_id is not None` (the base predicate).
- **Node.** `plugins/superheroes/lib/tests/test_empty_ids_2452.py::test_d8_a_lane_with_an_empty_session_id_is_never_proven_gone`
- **Note.** The title-match node `test_d8_a_lane_with_an_empty_session_id_is_matched_by_title` goes red under the same neutralization by the same reasoning (the empty id is matched by id, finds nothing, absence is then proven) but was not run under it (budget).
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_d8_a_lane_with_an_empty_session_id_is_never_proven_gone _________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-22/test_d8_a_lane_with_an_empty_s0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f02c7562600>

    def test_d8_a_lane_with_an_empty_session_id_is_never_proven_gone(tmp_path, monkeypatch):
        # axis: a lane whose cloudSessionId is empty is unconfirmed, so absence never proves it gone — see bite-proof record i2452_empty_ids
        repo = _cloud_repo(tmp_path)
        _seed_lane(repo)
        _fold_lane_with(monkeypatch, cloudSessionId="")
        rows = [_unrelated_row(NEWER, "session_01Newer00000000000000", "env-1")]
        result, calls = _adopt(repo, tmp_path, _write_listing(tmp_path, _page_of(rows)))
>       _refused_unread(repo, result, calls, "listing-incomplete")

/home/user/wt-2452-wo3/plugins/superheroes/lib/tests/test_empty_ids_2452.py:196: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt-2452-wo3/plugins/superheroes/lib/tests/test_adopt_original_session.py:149: in _refused_unread
    _assert_refused_cloud_lane(repo, result, TOKEN_UNREAD, "original-session")
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-22/test_d8_a_lane_with_an_empty_s0/repo'
result = {'ok': True, 'reason': None, 'launchId': 'launch-8824b2b2012ec766', 'place': 'cloud', ...}
reason = 'adopt-original-session-unread', stage = 'original-session'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
>       assert result["ok"] is False
E       assert True is False

/home/user/wt-2452-wo3/plugins/superheroes/lib/tests/test_launcher_cloud.py:653: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_empty_ids_2452.py::test_d8_a_lane_with_an_empty_session_id_is_never_proven_gone
1 failed in 3.25s
```

- **Restore.** The inverse Edit. Restored line, quoted back from the `git diff` of `launcher.py` taken after all six proofs:

```
+        confirmed = isinstance(session_id, str) and bool(session_id)
```

- **Raw green:**

```
.                                                                        [100%]
1 passed in 3.07s
```
