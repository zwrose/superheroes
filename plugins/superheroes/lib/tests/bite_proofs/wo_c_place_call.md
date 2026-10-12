# Place call WO-C bite-proof: the failed-check marker, the cloud prompt's two lines and the named base on the remote

Bite-proof record for `plugins/superheroes/lib/cloud_ready.py` (C1 to C5), `plugins/superheroes/lib/launch_place.py` (C6) and `plugins/superheroes/lib/launcher.py` (C7 to C11). Detectors are in `plugins/superheroes/lib/tests/test_cloud_ready.py`, `test_launch_place.py` and `test_launcher_cloud.py`.

**Status.** The implementer ran every proof (C1 to C11): each neutralization is a targeted Edit in the shipped file, the red is the single named test node run alone, the restore is the inverse Edit, and the green is the same node. Reds and greens below are the pytest output of each run (the harness's certificate-trust lines are filtered out of the capture; every pytest line is as printed); the absolute `tmp_path` prefixes and the worktree path are as printed. No fixture holds a real secret, so nothing is redacted.

- **Run command.** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<T>::<node>" -q`.
- **Restore receipt, every element.** The restored line is quoted back from the shipped file after the inverse Edit, and a closing run of the five test files with every neutralization undone is recorded in the implementer's return.
- **One two-node run.** C5 has one neutralization and two detectors, the unknown-parts case and the damaged-marker case; both nodes ran in one command, red and green.
- **Pinned condition.** The readiness tests build their store, account and record under `tmp_path` and give readiness a fixed `today`, advisor version and calibration stamp; the failed-check marker is written by the test beside the record. The launcher tests build the working repository and the bare "remote" under `tmp_path` and reach the remote by path or file URL, and the platform command is a stand-in. The pin makes unobservable: the real home directory, the process environment's account, the network and the real wall clock.

## Declared guarded-element set

C1 any marker present means not ready; C2 the `reviewer` part maps to `passPresent`; C3 the `version` part maps to `version`; C4 the `calibration` part maps to `calibration`; C5 any other part, or a damaged marker, maps to `setup`; C6 `fix_text` adds "check again" for a failed check; C7 the `Cloud environment:` prompt line; C8 the `Base commit:` prompt line; C9 the base check reads the remote and not tracking refs; C10 a non-zero fetch refuses; C11 an unchecked remote refuses.

Not neutralized, and so unproven by a run in this record: the exact `fix_text` strings for `no-setup` (C6's one neutralization turns off the whole failed-check branch, and the version assertion and the `no-setup` assertion both sit in the one detector node, which stops at the first); the empty-origin-URL, `git init` failure, timeout and `mkdtemp` failure edges of `_base_on_remote` (each has its own test, and each maps to `None` by the same `if found is None` branch that C11 neutralizes); the scratch-directory removal in the `finally` (tested by `test_E8_E9_the_scratch_directory_is_removed_whatever_the_fetch_says` and `test_E9_the_scratch_directory_is_removed_when_the_fetch_cannot_run`, with no neutralization of its own).

### C1: any marker present means not ready. Axis: marker presence

- **Neutralization applied.** In `cloud_ready._readiness`, `    if failed is not None:` replaced with `    if False and failed is not None:`, so the marker is read but never applied.
- **Node.** `test_cloud_ready.py::test_any_marker_present_means_not_ready`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_any_marker_present_means_not_ready ____________________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1229/test_any_marker_present_means_0')

    def test_any_marker_present_means_not_ready(tmp_path):
        # axis: any failed-check marker present means the latest check failed, so the setup is not ready
        repo, store = _ready(tmp_path)
        _mark(repo, store, ["record"])
        got = _read(repo, store)
>       assert got["ready"] is False and got["reason"] == "no-setup"
E       assert (True is False)

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_ready.py:427: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_ready.py::test_any_marker_present_means_not_ready
1 failed in 8.55s
```

- **Restore.** The inverse Edit; quoted from cloud_ready.py:148: `    if failed is not None:`
- **Green.**

```
.                                                                        [100%]
1 passed in 9.74s
```

### C2: the `reviewer` part maps to `passPresent`. Axis: part-to-condition mapping

- **Neutralization applied.** In `FAILED_PART_CONDITION`, `"reviewer": "passPresent",` replaced with `"reviewer": "platform",`.
- **Node.** `test_cloud_ready.py::test_a_named_part_forces_its_own_condition_false[reviewer-passPresent]`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_a_named_part_forces_its_own_condition_false[reviewer-passPresent] ____

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1233/test_a_named_part_forces_its_o0')
part = 'reviewer', condition = 'passPresent'

    @pytest.mark.parametrize("part,condition", [
        ("reviewer", "passPresent"), ("version", "version"), ("calibration", "calibration")])
    def test_a_named_part_forces_its_own_condition_false(tmp_path, part, condition):
        # axis: the reviewer, version and calibration parts each force their own condition false
        repo, store = _ready(tmp_path)
        _mark(repo, store, [part])
        got = _read(repo, store)
>       _only_false(got, condition)

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_ready.py:439: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'ready': False, 'reason': 'unreachable', 'conditions': {'setup': True, 'passPresent': True, 'passLive': True, 'version': True, ...}, 'setting': False, ...}
name = 'passPresent'

    def _only_false(result, name):
        expected = dict(ALL_TRUE, **{name: False})
>       assert result["conditions"] == expected
E       AssertionError: assert {'setup': Tru...n': True, ...} == {'setup': Tru...n': True, ...}
E         
E         Omitting 4 identical items, use -vv to show
E         Differing items:
E         {'passPresent': True} != {'passPresent': False}
E         {'platform': False} != {'platform': True}
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_ready.py:84: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_ready.py::test_a_named_part_forces_its_own_condition_false[reviewer-passPresent]
1 failed in 6.55s
```

- **Restore.** The inverse Edit; quoted from cloud_ready.py:29: `    "reviewer": "passPresent",`
- **Green.**

```
.                                                                        [100%]
1 passed in 7.08s
```

### C3: the `version` part maps to `version`. Axis: part-to-condition mapping

- **Neutralization applied.** In `FAILED_PART_CONDITION`, `"version": "version",` replaced with `"version": "platform",`.
- **Node.** `test_cloud_ready.py::test_a_named_part_forces_its_own_condition_false[version-version]`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_a_named_part_forces_its_own_condition_false[version-version] _______

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1235/test_a_named_part_forces_its_o0')
part = 'version', condition = 'version'

    @pytest.mark.parametrize("part,condition", [
        ("reviewer", "passPresent"), ("version", "version"), ("calibration", "calibration")])
    def test_a_named_part_forces_its_own_condition_false(tmp_path, part, condition):
        # axis: the reviewer, version and calibration parts each force their own condition false
        repo, store = _ready(tmp_path)
        _mark(repo, store, [part])
        got = _read(repo, store)
>       _only_false(got, condition)

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_ready.py:439: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'ready': False, 'reason': 'unreachable', 'conditions': {'setup': True, 'passPresent': True, 'passLive': True, 'version': True, ...}, 'setting': False, ...}
name = 'version'

    def _only_false(result, name):
        expected = dict(ALL_TRUE, **{name: False})
>       assert result["conditions"] == expected
E       AssertionError: assert {'setup': Tru...n': True, ...} == {'setup': Tru...': False, ...}
E         
E         Omitting 4 identical items, use -vv to show
E         Differing items:
E         {'platform': False} != {'platform': True}
E         {'version': True} != {'version': False}
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_ready.py:84: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_ready.py::test_a_named_part_forces_its_own_condition_false[version-version]
1 failed in 7.98s
```

- **Restore.** The inverse Edit; quoted from cloud_ready.py:31: `    "version": "version",`
- **Green.**

```
.                                                                        [100%]
1 passed in 10.29s
```

### C4: the `calibration` part maps to `calibration`. Axis: part-to-condition mapping

- **Neutralization applied.** In `FAILED_PART_CONDITION`, `"calibration": "calibration",` replaced with `"calibration": "platform",`.
- **Node.** `test_cloud_ready.py::test_a_named_part_forces_its_own_condition_false[calibration-calibration]`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_a_named_part_forces_its_own_condition_false[calibration-calibration] ___

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1237/test_a_named_part_forces_its_o0')
part = 'calibration', condition = 'calibration'

    @pytest.mark.parametrize("part,condition", [
        ("reviewer", "passPresent"), ("version", "version"), ("calibration", "calibration")])
    def test_a_named_part_forces_its_own_condition_false(tmp_path, part, condition):
        # axis: the reviewer, version and calibration parts each force their own condition false
        repo, store = _ready(tmp_path)
        _mark(repo, store, [part])
        got = _read(repo, store)
>       _only_false(got, condition)

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_ready.py:439: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'ready': False, 'reason': 'unreachable', 'conditions': {'setup': True, 'passPresent': True, 'passLive': True, 'version': True, ...}, 'setting': False, ...}
name = 'calibration'

    def _only_false(result, name):
        expected = dict(ALL_TRUE, **{name: False})
>       assert result["conditions"] == expected
E       AssertionError: assert {'setup': Tru...n': True, ...} == {'setup': Tru...n': True, ...}
E         
E         Omitting 4 identical items, use -vv to show
E         Differing items:
E         {'calibration': True} != {'calibration': False}
E         {'platform': False} != {'platform': True}
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_ready.py:84: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_ready.py::test_a_named_part_forces_its_own_condition_false[calibration-calibration]
1 failed in 6.22s
```

- **Restore.** The inverse Edit; quoted from cloud_ready.py:33: `    "calibration": "calibration",`
- **Green.**

```
.                                                                        [100%]
1 passed in 9.80s
```

### C5: any other part, or a damaged marker, maps to `setup`. Axis: unknown parts and unreadable markers fail closed

- **Neutralization applied.** In `_readiness`, `if not failed or any(part not in FAILED_PART_CONDITION for part in failed):` replaced with `if False and (not failed or any(part not in FAILED_PART_CONDITION for part in failed)):`, and `forced = {FAILED_PART_CONDITION[part] for part in failed}` replaced with `forced = {FAILED_PART_CONDITION[part] for part in failed if part in FAILED_PART_CONDITION}`, so an unknown part and an empty (damaged) marker are ignored.
- **Nodes (one command).** `test_cloud_ready.py::test_E3_a_marker_of_unknown_parts_only_is_no_setup` and `test_cloud_ready.py::test_E1_a_damaged_marker_is_present_with_no_parts_and_no_setup[not json]`
- **Red:**

```
FF                                                                       [100%]
=================================== FAILURES ===================================
______________ test_E3_a_marker_of_unknown_parts_only_is_no_setup ______________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1239/test_E3_a_marker_of_unknown_pa0')

    def test_E3_a_marker_of_unknown_parts_only_is_no_setup(tmp_path):
        repo, store = _ready(tmp_path)
        _mark(repo, store, ["unread", "environment"])
        got = _read(repo, store)
>       assert got["conditions"] == ALL_FALSE and got["reason"] == "no-setup"
E       AssertionError: assert ({'setup': Tru...n': True, ...} == {'setup': Fal...': False, ...}
E         
E         Differing items:
E         {'setup': True} != {'setup': False}
E         {'version': True} != {'version': False}
E         {'calibration': True} != {'calibration': False}
E         {'passPresent': True} != {'passPresent': False}
E         {'platform': True} != {'platform': False}
E         {'passLive': True} != {'passLive': False}
E         Use -v to get more diff)

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_ready.py:466: AssertionError
___ test_E1_a_damaged_marker_is_present_with_no_parts_and_no_setup[not json] ___

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1239/test_E1_a_damaged_marker_is_pr0')
raw = 'not json'

    @pytest.mark.parametrize("raw", ["not json", "[]", "{}", '{"schema": "other/9"}', ""])
    def test_E1_a_damaged_marker_is_present_with_no_parts_and_no_setup(tmp_path, raw):
        # axis: a marker that cannot be read is present and damaged, so the setup is not ready
        repo, store = _ready(tmp_path)
        _mark(repo, store, [], raw=raw)
        got = _read(repo, store)
>       assert got["conditions"] == ALL_FALSE and got["reason"] == "no-setup"
E       AssertionError: assert ({'setup': Tru...n': True, ...} == {'setup': Fal...': False, ...}
E         
E         Differing items:
E         {'setup': True} != {'setup': False}
E         {'version': True} != {'version': False}
E         {'calibration': True} != {'calibration': False}
E         {'passPresent': True} != {'passPresent': False}
E         {'platform': True} != {'platform': False}
E         {'passLive': True} != {'passLive': False}
E         Use -v to get more diff)

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_ready.py:483: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_ready.py::test_E3_a_marker_of_unknown_parts_only_is_no_setup
FAILED plugins/superheroes/lib/tests/test_cloud_ready.py::test_E1_a_damaged_marker_is_present_with_no_parts_and_no_setup[not json]
2 failed in 18.33s
```

- **Restore.** Both inverse Edits; quoted from cloud_ready.py:150-152:

```
        if not failed or any(part not in FAILED_PART_CONDITION for part in failed):
            return _result(conditions, failed_check=failed, **fallback)
        forced = {FAILED_PART_CONDITION[part] for part in failed}
```

- **Green.**

```
..                                                                       [100%]
2 passed in 17.49s
```

### C6: `fix_text` adds "check again" for a failed check. Axis: the fix after a failed check

- **Neutralization applied.** In `launch_place.fix_text`, `if fix is None or place_call.get("failedCheck") is None:` replaced with `if True or fix is None or place_call.get("failedCheck") is None:`, so the table's fix is always returned as it stands.
- **Node.** `test_launch_place.py::test_fix_text_after_a_failed_check_asks_for_the_check_again`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_fix_text_after_a_failed_check_asks_for_the_check_again __________

    def test_fix_text_after_a_failed_check_asks_for_the_check_again():
        # axis: after a failed check the fix ends by asking for the check to be run again
>       assert LP.fix_text(_call(reason="no-setup", failed=[])) == CHECK_AGAIN_ONLY
E       assert 'Say "set up ...u through it.' == 'Say "check a... check again.'
E         
E         - Say "check again" and I'll run the check again.
E         + Say "set up cloud builds" and I'll walk you through it.

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launch_place.py:296: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_place.py::test_fix_text_after_a_failed_check_asks_for_the_check_again
1 failed in 1.69s
```

- **Restore.** The inverse Edit; quoted from launch_place.py:281: `        if fix is None or place_call.get("failedCheck") is None:`
- **Green.**

```
.                                                                        [100%]
1 passed in 1.56s
```

### C7: the `Cloud environment:` prompt line. Axis: presence and exact text of the line

- **Neutralization applied.** In `compose_launch`, `environment_line = "Cloud environment: %s" % cloud_environment` replaced with `environment_line = "Cloud environment (unset): %s" % cloud_environment`.
- **Node.** `test_launcher_cloud.py::test_compose_cloud_prompt_names_the_environment_on_its_own_line`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_compose_cloud_prompt_names_the_environment_on_its_own_line ________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1243/test_compose_cloud_prompt_name0')

    def test_compose_cloud_prompt_names_the_environment_on_its_own_line(tmp_path):
        # axis: the cloud prompt names the cloud environment on its own line
        repo = _init_repo(tmp_path / "repo")
        lines = _compose_cloud(repo)["prompt"].split("\n")
>       assert lines.count("Cloud environment: %s" % ENV_ID) == 1
E       AssertionError: assert 0 == 1
E        +  where 0 = <built-in method count of list object at 0x106185b00>(('Cloud environment: %s' % 'env_01AbCdEf'))
E        +    where <built-in method count of list object at 0x106185b00> = ['/superheroes:workhorse', '', 'Issue: #656', '', 'Place: cloud session', 'Advisor plugin version: 0.42.0', ...].count

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_cloud.py:292: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_compose_cloud_prompt_names_the_environment_on_its_own_line
1 failed in 8.01s
```

- **Restore.** The inverse Edit; quoted from launcher.py:1262: `        environment_line = "Cloud environment: %s" % cloud_environment`
- **Green.**

```
.                                                                        [100%]
1 passed in 10.02s
```

### C8: the `Base commit:` prompt line. Axis: presence and exact text of the line

- **Neutralization applied.** In `compose_launch`, `base_line = "Base commit: %s" % base` replaced with `base_line = "Base commit (unset): %s" % base`.
- **Node.** `test_launcher_cloud.py::test_compose_cloud_prompt_names_the_base_commit_on_its_own_line`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_compose_cloud_prompt_names_the_base_commit_on_its_own_line ________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1245/test_compose_cloud_prompt_name0')

    def test_compose_cloud_prompt_names_the_base_commit_on_its_own_line(tmp_path):
        # axis: the cloud prompt names the premise's base commit on its own line
        repo = _init_repo(tmp_path / "repo")
        base = _head_sha(repo)
        lines = _compose_cloud(repo)["prompt"].split("\n")
>       assert lines.count("Base commit: %s" % base) == 1
E       AssertionError: assert 0 == 1
E        +  where 0 = <built-in method count of list object at 0x1060adb00>(('Base commit: %s' % '66dcfc6dad9ee7cb67bf27b2dc159db01f333dd0'))
E        +    where <built-in method count of list object at 0x1060adb00> = ['/superheroes:workhorse', '', 'Issue: #656', '', 'Place: cloud session', 'Advisor plugin version: 0.42.0', ...].count

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_cloud.py:304: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_compose_cloud_prompt_names_the_base_commit_on_its_own_line
1 failed in 7.26s
```

- **Restore.** The inverse Edit; quoted from launcher.py:1264: `        base_line = "Base commit: %s" % base`
- **Green.**

```
.                                                                        [100%]
1 passed in 7.69s
```

### C9: the base check reads the remote and not tracking refs. Axis: the source of the answer (T3c)

- **Neutralization applied.** In `_cloud_base_refusal`, `found = _base_on_remote_fn(repo_root, stamped["baseCommit"], env)` replaced with `found = bool(_git_scrubbed(repo_root, "branch", "-r", "--contains", stamped["baseCommit"], env=env, timeout=_WORKTREE_GIT_TIMEOUT).stdout.strip())`, re-introducing the read of local tracking refs.
- **Node.** `test_launcher_cloud.py::test_edge3_a_stale_tracking_ref_does_not_decide_the_result`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_edge3_a_stale_tracking_ref_does_not_decide_the_result __________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1247/test_edge3_a_stale_tracking_re0')

    def test_edge3_a_stale_tracking_ref_does_not_decide_the_result(tmp_path):
        # axis: the remote is read, not local tracking refs
        repo = _cloud_repo(tmp_path)
        later = _later_commit(tmp_path, repo)
        _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        assert "origin/main" in _git(repo, "branch", "-r", "--contains", later)
        calls = []
        result = _launch(repo, tmp_path, _fake_spawn(calls=calls),
                         premise=_valid_premise(repo, baseCommit=later))
>       _assert_refused_cloud_lane(repo, result, "launch-cloud-base-not-on-remote", "cloud-base")

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_cloud.py:579: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/private/tmp/claude-501/pytest-of-zwrose/pytest-1247/test_edge3_a_stale_tracking_re0/repo'
result = {'ok': True, 'reason': None, 'launchId': 'launch-ec99ed854dd8fc62', 'place': 'cloud', ...}
reason = 'launch-cloud-base-not-on-remote', stage = 'cloud-base'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
>       assert result["ok"] is False
E       assert True is False

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_cloud.py:480: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_edge3_a_stale_tracking_ref_does_not_decide_the_result
1 failed in 10.59s
```

- **Restore.** The inverse Edit; quoted from launcher.py:2328: `    found = _base_on_remote_fn(repo_root, stamped["baseCommit"], env)`
- **Green.**

```
.                                                                        [100%]
1 passed in 10.27s
```

### C10: a non-zero fetch refuses. Axis: the fetch's exit code decides

- **Neutralization applied.** In `_base_on_remote`, `return fetched.returncode == 0` replaced with `return True`.
- **Node.** `test_launcher_cloud.py::test_the_real_round_trip_finds_a_pushed_commit_and_misses_an_unpushed_one`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_the_real_round_trip_finds_a_pushed_commit_and_misses_an_unpushed_one ___

local_remote = namespace(repo='/private/tmp/claude-501/pytest-of-zwrose/pytest-1249/test_the_real_round_trip_finds0/repo', remote=Pos...0/remote.git'), pushed='ebee9b869cac809673074a2460bfb2e4834165e3', unpushed='c100445827e04637d4a624933c60a2fb73f7bcf6')

    def test_the_real_round_trip_finds_a_pushed_commit_and_misses_an_unpushed_one(local_remote):
        # axis: the base is read from the remote afresh, in an empty repository
        assert L._base_on_remote(local_remote.repo, local_remote.pushed, None) is True
>       assert L._base_on_remote(local_remote.repo, local_remote.unpushed, None) is False
E       AssertionError: assert True is False
E        +  where True = <function _base_on_remote at 0x10a812de0>('/private/tmp/claude-501/pytest-of-zwrose/pytest-1249/test_the_real_round_trip_finds0/repo', 'c100445827e04637d4a624933c60a2fb73f7bcf6', None)
E        +    where <function _base_on_remote at 0x10a812de0> = L._base_on_remote
E        +    and   '/private/tmp/claude-501/pytest-of-zwrose/pytest-1249/test_the_real_round_trip_finds0/repo' = namespace(repo='/private/tmp/claude-501/pytest-of-zwrose/pytest-1249/test_the_real_round_trip_finds0/repo', remote=Pos...0/remote.git'), pushed='ebee9b869cac809673074a2460bfb2e4834165e3', unpushed='c100445827e04637d4a624933c60a2fb73f7bcf6').repo
E        +    and   'c100445827e04637d4a624933c60a2fb73f7bcf6' = namespace(repo='/private/tmp/claude-501/pytest-of-zwrose/pytest-1249/test_the_real_round_trip_finds0/repo', remote=Pos...0/remote.git'), pushed='ebee9b869cac809673074a2460bfb2e4834165e3', unpushed='c100445827e04637d4a624933c60a2fb73f7bcf6').unpushed

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_cloud.py:640: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_the_real_round_trip_finds_a_pushed_commit_and_misses_an_unpushed_one
1 failed in 6.33s
```

- **Restore.** The inverse Edit; quoted from launcher.py:2310: `        return fetched.returncode == 0`
- **Green.**

```
.                                                                        [100%]
1 passed in 8.80s
```

### C11: an unchecked remote refuses. Axis: the check fails closed

- **Neutralization applied.** In `_cloud_base_refusal`, `return "launch-cloud-base-remote-unchecked"` replaced with `return None`, so a remote that could not be asked lets the launch through.
- **Node.** `test_launcher_cloud.py::test_edge3_a_checkout_with_no_origin_is_unchecked_and_refuses`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_edge3_a_checkout_with_no_origin_is_unchecked_and_refuses _________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1251/test_edge3_a_checkout_with_no_0')

    def test_edge3_a_checkout_with_no_origin_is_unchecked_and_refuses(tmp_path):
        # axis: a remote that could not be asked refuses
        repo = _init_repo(tmp_path / "repo")
        calls = []
        result = _launch(repo, tmp_path, _fake_spawn(calls=calls))
>       _assert_refused_cloud_lane(repo, result, "launch-cloud-base-remote-unchecked", "cloud-base")

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_cloud.py:538: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/private/tmp/claude-501/pytest-of-zwrose/pytest-1251/test_edge3_a_checkout_with_no_0/repo'
result = {'ok': True, 'reason': None, 'launchId': 'launch-c03453e55275dc4b', 'place': 'cloud', ...}
reason = 'launch-cloud-base-remote-unchecked', stage = 'cloud-base'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
>       assert result["ok"] is False
E       assert True is False

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_cloud.py:480: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_edge3_a_checkout_with_no_origin_is_unchecked_and_refuses
1 failed in 9.09s
```

- **Restore.** The inverse Edit; quoted from launcher.py:2331: `        return "launch-cloud-base-remote-unchecked"`
- **Green.**

```
.                                                                        [100%]
1 passed in 10.02s
```
