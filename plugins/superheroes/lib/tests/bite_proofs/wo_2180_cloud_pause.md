# Bite-proof record: WO-2180-A/A2's cloud-pause detectors (issue #2180)

Detectors: `plugins/superheroes/lib/tests/test_cloud_check.py` (six nodes),
`plugins/superheroes/lib/tests/test_cloud_setup.py` (one node),
`plugins/superheroes/lib/tests/test_launch_report_verbs.py` (one node).
Guarded elements (declared by WO-2180-A3, rows 1 to 8): (1) `judge` writes no setting on a failed result;
(2) `judge` writes no setting on an unread result; (3) a passing check after a failed one routes to the cloud with no owner step;
(4) another account's place call is unaffected by a failed check; (5) switch-on with a marker present writes the setting;
(6) the marker write retries under lock contention; (7) a same-day pass clears the still line; (8) no check message says cloud builds were switched off.
Each was neutralized by a targeted edit in production code only, the detector run alone as one test node id, then restored by the inverse edit
(an edit, never a checkout/restore/reset/stash). Every red below was produced with the detector unedited. No test and no other file was edited.

Run command, each time, from the worktree root, as one plain command:
`timeout 900 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest '<node>' -q -p no:cacheprovider --tb=short`.
No output was filtered beyond dropping the `UV_NATIVE_TLS` deprecation line that heads every run (omitted from the captures below).
Redaction: none needed; the captures hold pytest temp paths under `/tmp/claude-0/pytest-of-root/` and no secrets, tokens, URLs or personal data.

Notes that apply to more than one entry:

- Rows 1 and 2 share one node (`test_judge_edge9_no_failed_or_unread_result_writes_the_setting_through_any_path`). It is not parametrised: it judges a failed, an unread and a passed result in turn and asserts one `calls == []` at the end. The two reds therefore look the same; they are told apart by which branch each neutralization touched (only one branch was neutralized per run, so each red is that branch's alone).
- The `calls` list in rows 1 and 2 is filled by the test's own monkeypatch of `project_config.set_item`, so the neutralization reaches the detector through `project_config.set_item`, the path the detector claims to cover (the test also patches `core_md.write_project_config_item`; that second path was not neutralized).
- Row 4's neutralization is the first option the order gave (a second marker write in `_write_failed_check_once`, to the other account's path), not the `cloud_setup.failed_check_path` option.

## 1. `judge` writes no setting on a failed result

Axis: a failed check writes the failed-check marker and never the cloud-builds setting (`cloud_check.py` `judge`, `if failed:` branch, axis line at `cloud_check.py:745`).

- Neutralization (`cloud_check.py`, `judge`, top of the `if failed:` branch): added
  `import project_config` and
  `project_config.set_item(cwd, project_config.CLOUD_BUILDS_SLUG, False, root=root, project_name=name)`
  (the module does not import `project_config` at the top, so the import went inside the branch).
- Node: `plugins/superheroes/lib/tests/test_cloud_check.py::test_judge_edge9_no_failed_or_unread_result_writes_the_setting_through_any_path`.
- Red (on axis: the assertion that fails is `assert calls == []`, and the extra item is a `set_item(cwd, 'cloudBuilds', False)` call, a setting write):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_judge_edge9_no_failed_or_unread_result_writes_the_setting_through_any_path _
/home/user/wt-2180/plugins/superheroes/lib/tests/test_cloud_check.py:693: in test_judge_edge9_no_failed_or_unread_result_writes_the_setting_through_any_path
    assert calls == []
E   AssertionError: assert [('set_item',...lds', False))] == []
E     
E     Left contains one more item: ('set_item', ('/tmp/claude-0/pytest-of-root/pytest-18/test_judge_edge9_no_failed_or_0/local/repo', 'cloudBuilds', False))
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check.py::test_judge_edge9_no_failed_or_unread_result_writes_the_setting_through_any_path
1 failed in 1.94s
```

- Restore: the inverse edit, removing the two added lines. Restored text, `cloud_check.py:744-746`: `    if failed:` / `        # axis: a failed check writes the marker and never the setting` / `        # axis: a failed check leaves a marker a later reader can see, and never touches the record`
- Green:

```
.                                                                        [100%]
1 passed in 2.08s
```

## 2. `judge` writes no setting on an unread result

Axis: an unread report writes the failed-check marker and never the cloud-builds setting (`cloud_check.py` `judge`, `if obj is None:` branch, axis line at `cloud_check.py:696`).

- Neutralization (`cloud_check.py`, `judge`, top of the `if obj is None:` branch): added
  `import project_config` and
  `project_config.set_item(cwd, project_config.CLOUD_BUILDS_SLUG, False, root=root, project_name=name)`.
  The failed branch was back in its restored state for this run.
- Node: the same as row 1, `plugins/superheroes/lib/tests/test_cloud_check.py::test_judge_edge9_no_failed_or_unread_result_writes_the_setting_through_any_path` (the unread leg is `unread = _judge(local, "no report here")`; the node has no separate parametrised case).
- Red (on axis: the same `assert calls == []`, one setting write recorded; with the failed branch clean, the one call can only come from the unread judge):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_judge_edge9_no_failed_or_unread_result_writes_the_setting_through_any_path _
/home/user/wt-2180/plugins/superheroes/lib/tests/test_cloud_check.py:693: in test_judge_edge9_no_failed_or_unread_result_writes_the_setting_through_any_path
    assert calls == []
E   AssertionError: assert [('set_item',...lds', False))] == []
E     
E     Left contains one more item: ('set_item', ('/tmp/claude-0/pytest-of-root/pytest-20/test_judge_edge9_no_failed_or_0/local/repo', 'cloudBuilds', False))
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check.py::test_judge_edge9_no_failed_or_unread_result_writes_the_setting_through_any_path
1 failed in 1.74s
```

- Restore: the inverse edit, removing the two added lines. Restored text, `cloud_check.py:695-697`: `    if obj is None:` / `        # axis: an unread report writes the marker and never the setting` / `        # axis: an unread report leaves a marker a later reader can see, and never touches the record`
- Green:

```
.                                                                        [100%]
1 passed in 1.81s
```

## 3. A passing check after a failed one routes to the cloud with no owner step

Axis: a passing check clears the failed-check marker, so the account is no longer paused and the next place call is the cloud. Where the red lands: the node fails at its marker-cleared assertion (`assert not os.path.exists(_marker_path(local))`), which is the marker-removal leg of this element; the last assertion of the test (`resumed["place"] == "cloud"`) was not reached, so the red proves the marker is cleared, and the final routing assertion's own bite follows from the marker's presence pausing the account (shown by the node's earlier `paused` assertions) rather than from a separate red here.

- Neutralization (`cloud_check.py`, `_remove_failed_check`): inserted `return True` on its own line before `try:` / `os.unlink(failed_check_path(cwd, account, root))`.
- Node: `plugins/superheroes/lib/tests/test_cloud_check.py::test_T2_fail_then_pass_pauses_then_resumes_with_no_owner_step`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_T2_fail_then_pass_pauses_then_resumes_with_no_owner_step _________
/home/user/wt-2180/plugins/superheroes/lib/tests/test_cloud_check.py:1965: in test_T2_fail_then_pass_pauses_then_resumes_with_no_owner_step
    assert not os.path.exists(_marker_path(local))
E   AssertionError: assert not True
E    +  where True = <function exists at 0x7f7efd1d40e0>('/tmp/claude-0/pytest-of-root/pytest-22/test_T2_fail_then_pass_pauses_0/local/store-root/projects/238a7b644f5fb344/state/cloud-setup/7326bd603efe1013.failed-check.json')
E    +    where <function exists at 0x7f7efd1d40e0> = <module 'posixpath' (frozen)>.exists
E      where <module 'posixpath' (frozen)> = os.path
E    +    and   '/tmp/claude-0/pytest-of-root/pytest-22/test_T2_fail_then_pass_pauses_0/local/store-root/projects/238a7b644f5fb344/state/cloud-setup/7326bd603efe1013.failed-check.json' = _marker_path(<test_cloud_setup_text.World object at 0x7f7efc4095b0>)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check.py::test_T2_fail_then_pass_pauses_then_resumes_with_no_owner_step
1 failed in 1.97s
```

- Restore: the inverse edit, removing the inserted `return True`. Restored text, `cloud_check.py:607-611`: `            try:` / `                os.unlink(failed_check_path(cwd, account, root))` / `            except FileNotFoundError:` / `                pass` / `            return True`
- Green:

```
.                                                                        [100%]
1 passed in 2.05s
```

## 4. Another account's place call is unaffected

Axis: a failed check for one account writes a marker for that account only; another account's place call and marker read are unchanged. Chosen neutralization: the order's first option (the marker is also written to the other account's path), not the `cloud_setup.failed_check_path` option; both go through production code. The id the test uses for the other account is `OTHER_ACCOUNT = "acct-fixture-two"` (`test_cloud_check.py:1867`). The red is on axis: the other account's place call changes from cloud to local with `failedCheck` set.

- Neutralization (`cloud_check.py`, `_write_failed_check_once`): after `os.replace(tmp, path)` added
  `with open(failed_check_path(cwd, "acct-fixture-two", root), "w", encoding="utf-8") as other:` /
  `    other.write(json.dumps(marker, sort_keys=True, indent=2) + "\n")`.
- Node: `plugins/superheroes/lib/tests/test_cloud_check.py::test_T3_one_accounts_failed_check_leaves_another_accounts_place_call_unchanged`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_T3_one_accounts_failed_check_leaves_another_accounts_place_call_unchanged _
/home/user/wt-2180/plugins/superheroes/lib/tests/test_cloud_check.py:1987: in test_T3_one_accounts_failed_check_leaves_another_accounts_place_call_unchanged
    assert _place(local, env_b) == before
E   AssertionError: assert {'place': 'lo...version', ...} == {'place': 'cl...n': None, ...}
E     
E     Omitting 6 identical items, use -vv to show
E     Differing items:
E     {'environment': None} != {'environment': 'env_01ABCdef'}
E     {'reason': 'version'} != {'reason': None}
E     {'place': 'local'} != {'place': 'cloud'}
E     {'cloudVersion': None} != {'cloudVersion': '0.46.1'}
E     {'failedCheck': ['version']} != {'failedCheck': None}
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check.py::test_T3_one_accounts_failed_check_leaves_another_accounts_place_call_unchanged
1 failed in 1.86s
```

- Restore: the inverse edit, removing the two added lines. Restored text, `cloud_check.py:576-577`: `                os.replace(tmp, path)` / `                tmp = None`
- Green:

```
.                                                                        [100%]
1 passed in 1.83s
```

## 5. Switch-on with a marker present writes the setting

Axis: a failed-check marker never refuses the switch-on; the setting is written and the answer says paused (axis line at `project_config.py:1147`). The red is on axis: the switch-on's `action` is `refused`, not `written`.

- Neutralization (`project_config.py`, `set_item`, the cloud-builds branch): inside `if marker is not None:`, before `paused = True`, added
  `return {"action": "refused", "reason": "cloud-check-failed"}`.
- Node: `plugins/superheroes/lib/tests/test_cloud_setup.py::test_switch_on_goes_ahead_when_the_last_check_failed_and_says_paused`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_switch_on_goes_ahead_when_the_last_check_failed_and_says_paused _____
/home/user/wt-2180/plugins/superheroes/lib/tests/test_cloud_setup.py:187: in test_switch_on_goes_ahead_when_the_last_check_failed_and_says_paused
    got = _switched_on_paused(repo, store, ["version"])
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2180/plugins/superheroes/lib/tests/test_cloud_setup.py:174: in _switched_on_paused
    assert got["action"] == "written"
E   AssertionError: assert 'refused' == 'written'
E     
E     - written
E     + refused
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup.py::test_switch_on_goes_ahead_when_the_last_check_failed_and_says_paused
1 failed in 0.93s
```

- Restore: the inverse edit, removing the added `return`. Restored text, `project_config.py:1150-1151`: `                if marker is not None:` / `                    paused = True`
- Green:

```
.                                                                        [100%]
1 passed in 1.20s
```

## 6. The marker write retries under lock contention

Axis: a held store lock is tried `_MARKER_ATTEMPTS` (5) times, with `_MARKER_WAIT` (0.2 s) between, before the marker is given up (axis line at `cloud_check.py:552`). The red is on axis: the lock was tried once, not five times.

- Neutralization (`cloud_check.py:163`): `_MARKER_ATTEMPTS = 5` became `_MARKER_ATTEMPTS = 1`.
- Node: `plugins/superheroes/lib/tests/test_cloud_check.py::test_a_marker_that_cannot_be_saved_for_a_held_lock_is_tried_five_times_then_not_paused`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_marker_that_cannot_be_saved_for_a_held_lock_is_tried_five_times_then_not_paused _
/home/user/wt-2180/plugins/superheroes/lib/tests/test_cloud_check.py:1080: in test_a_marker_that_cannot_be_saved_for_a_held_lock_is_tried_five_times_then_not_paused
    assert spy.calls == 5 and lock_spy.sleeps == [0.2] * 4
E   assert (1 == 5)
E    +  where 1 = <test_cloud_check._Lock object at 0x7fc1b4263140>.calls
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check.py::test_a_marker_that_cannot_be_saved_for_a_held_lock_is_tried_five_times_then_not_paused
1 failed in 1.36s
```

- Restore: the inverse edit. `cloud_check.py:163` reads `_MARKER_ATTEMPTS = 5`
- Green:

```
.                                                                        [100%]
1 passed in 1.43s
```

## 7. A same-day pass clears the still line

Axis: a still line that came from a failed check is cleared by a passing check on the same day, once the marker is gone and the reason's condition reads true now (axis line at `launch_report.py:254`). The red is on axis: after the same-day passing check the still line still stands (the node's last assertion, `still_line(...) is None`).

- Neutralization (`launch_report.py`, `_fixed`): deleted the whole block
  `if candidate.get("failedCheck") is not None:` / the axis comment line under it / `return now.get("failedCheck") is None and conditions.get(_CONDITION_FOR[reason]) is True`
  (the `if` line, the one axis comment line, and the `return` line).
- Node: `plugins/superheroes/lib/tests/test_launch_report_verbs.py::test_T8_a_same_day_passing_check_clears_the_still_line_after_a_reviewer_failure`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_T8_a_same_day_passing_check_clears_the_still_line_after_a_reviewer_failure _
/home/user/wt-2180/plugins/superheroes/lib/tests/test_launch_report_verbs.py:803: in test_T8_a_same_day_passing_check_clears_the_still_line_after_a_reviewer_failure
    assert LR.still_line(local.cwd, root=local.root, readiness_fn=ready) is None
E   assert 'Still on your machine\nThere is no reviewer pass in the cloud environment. To fix it, run the pass command on your machine, paste the pass into the environment and say "check again".' is None
E    +  where 'Still on your machine\nThere is no reviewer pass in the cloud environment. To fix it, run the pass command on your machine, paste the pass into the environment and say "check again".' = <function still_line at 0x7fce9b956020>('/tmp/claude-0/pytest-of-root/pytest-30/test_T8_a_same_day_passing_che0/local/repo', root='/tmp/claude-0/pytest-of-root/pytest-30/test_T8_a_same_day_passing_che0/local/store-root', readiness_fn=functools.partial(<function readiness at 0x7fce9b90ad40>, advisor_version='0.46.1', today=datetime.date(2026, 10, 10),...maven/bin:/opt/gradle/bin:/opt/rbenv/bin:/root/.bun/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'}))
E    +    where <function still_line at 0x7fce9b956020> = LR.still_line
E    +    and   '/tmp/claude-0/pytest-of-root/pytest-30/test_T8_a_same_day_passing_che0/local/repo' = <test_cloud_setup_text.World object at 0x7fce9d5b2240>.cwd
E    +    and   '/tmp/claude-0/pytest-of-root/pytest-30/test_T8_a_same_day_passing_che0/local/store-root' = <test_cloud_setup_text.World object at 0x7fce9d5b2240>.root
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_report_verbs.py::test_T8_a_same_day_passing_check_clears_the_still_line_after_a_reviewer_failure
1 failed in 3.55s
```

- Restore: the inverse edit, re-inserting the three lines after the `_VERSION_REASON` branch. Restored text, `launch_report.py:253-255`: `    if candidate.get("failedCheck") is not None:` / `        # axis: a fallback that came from a failed check is fixed once a passing check has cleared the marker and its condition reads true now, on the same day too` / `        return now.get("failedCheck") is None and conditions.get(_CONDITION_FOR[reason]) is True`
- Green:

```
.                                                                        [100%]
1 passed in 3.43s
```

## 8. No check message says cloud builds were switched off

Axis: no string a check can show the owner says cloud builds were switched off (`T9_PATTERN`); here, the standing sentence of every check message. The red is on axis: the first sweep over the module's private strings matches `switched them off` in `_PAUSED_STANDING`.

- Neutralization (`cloud_check.py:158-159`, `_PAUSED_STANDING`): the text ended `+ cloud_setup.PAUSED_RESUME)`; it became `+ cloud_setup.PAUSED_RESUME` / `+ " They were on for this project, so I've switched them off.")`.
- Node: `plugins/superheroes/lib/tests/test_cloud_check.py::test_T9_no_check_message_says_cloud_builds_were_switched_off`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_T9_no_check_message_says_cloud_builds_were_switched_off _________
/home/user/wt-2180/plugins/superheroes/lib/tests/test_cloud_check.py:2016: in test_T9_no_check_message_says_cloud_builds_were_switched_off
    assert not T9_PATTERN.search(value), (name, value)
E   AssertionError: ('_PAUSED_STANDING', "Cloud builds are paused for this account until the check passes. They resume by themselves once the check passes. They were on for this project, so I've switched them off.")
E   assert not <re.Match object; span=(153, 170), match='switched them off'>
E    +  where <re.Match object; span=(153, 170), match='switched them off'> = <built-in method search of re.Pattern object at 0x2ad53c50>("Cloud builds are paused for this account until the check passes. They resume by themselves once the check passes. They were on for this project, so I've switched them off.")
E    +    where <built-in method search of re.Pattern object at 0x2ad53c50> = re.compile('(?i)switched (them |cloud builds )?off|switch them off|switching cloud builds off|stay off|still on: I could not', re.IGNORECASE).search
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check.py::test_T9_no_check_message_says_cloud_builds_were_switched_off
1 failed in 0.74s
```

- Restore: the inverse edit. Restored text, `cloud_check.py:158-159`: `_PAUSED_STANDING = ("Cloud builds are paused for this account until the check passes. "` / `                    + cloud_setup.PAUSED_RESUME)`
- Green:

```
.                                                                        [100%]
1 passed in 14.62s
```

## Closing statements

- Run command: `timeout 900 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest '<node>' -q -p no:cacheprovider --tb=short`, one plain command per run, 16 runs (8 red, 8 green).
- No output was filtered beyond dropping the `UV_NATIVE_TLS` deprecation line.
- Redaction: none needed.
- Every row bit: no node stayed green under its neutralization, and no red landed on another axis. Row 3's red lands at the marker-cleared assertion, upstream of the node's final routing assertion (stated in that entry).
