# Place call WO-C bite-proof: the failed-check marker, the cloud prompt's two lines and the named base on the remote

> Note (2026-10-31, #2296): owner-machine paths and the name of a consuming project in this record were replaced with neutral placeholders after capture; nothing else changed.

Bite-proof record for `plugins/superheroes/lib/cloud_ready.py` (C1 to C5), `plugins/superheroes/lib/launch_place.py` (C6) and `plugins/superheroes/lib/launcher.py` (C7 to C11). Detectors are in `plugins/superheroes/lib/tests/test_cloud_ready.py`, `test_launch_place.py` and `test_launcher_cloud.py`. C9 to C11 were rewritten in C8a WO1 against the current check: `_base_on_remote` asks GitHub through `_gh_commit_lookup`, and `_cloud_base_refusal` maps the answer.

**Status.** The implementer ran every proof (C1 to C11): each neutralization is a targeted Edit in the shipped file, the red is the single named test node run alone, the restore is the inverse Edit, and the green is the same node. Reds and greens below are the pytest output of each run (the harness's certificate-trust lines are filtered out of the capture; every pytest line is as printed); the absolute `tmp_path` prefixes and the worktree path are as printed. No fixture holds a real secret, so nothing is redacted.

- **Run command.** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<T>::<node>" -q`.
- **Restore receipt, every element.** The restored line is quoted back from the shipped file after the inverse Edit, and a closing run of the five test files with every neutralization undone is recorded in the implementer's return.
- **One two-node run.** C5 has one neutralization and two detectors, the unknown-parts case and the damaged-marker case; both nodes ran in one command, red and green.
- **Pinned condition.** The readiness tests build their store, account and record under `tmp_path` and give readiness a fixed `today`, advisor version and calibration stamp; the failed-check marker is written by the test beside the record. The launcher tests build the working repository and the bare "remote" under `tmp_path` and reach the remote by path or file URL, and the platform command is a stand-in. The pin makes unobservable: the real home directory, the process environment's account, the network and the real wall clock.

## Declared guarded-element set

C1 any marker present means not ready; C2 the `reviewer` part maps to `passPresent`; C3 the `version` part maps to `version`; C4 the `calibration` part maps to `calibration`; C5 any other part, or a damaged marker, maps to `setup`; C6 `fix_text` adds "check again" for a failed check; C7 the `Cloud environment:` prompt line; C8 the `Base commit:` prompt line; C9 the base check asks the server (GitHub's commits endpoint through `gh`), not local tracking refs; C10 only the HTTP 422 no-commit answer reads as absent, and any other `gh` failure is unchecked; C11 an unchecked remote refuses.

Not neutralized, and so unproven by a run in this record: the exact `fix_text` strings for `no-setup` (C6's one neutralization turns off the whole failed-check branch, and the version assertion and the `no-setup` assertion both sit in the one detector node, which stops at the first); the no-origin, non-GitHub-origin, `gh`-cannot-run and timeout edges of `_base_on_remote` (tested by `test_an_origin_that_is_not_a_github_address_is_unchecked_without_asking`, `test_a_gh_that_cannot_run_or_times_out_is_unchecked` and `test_any_other_gh_failure_is_unchecked`, each mapping to `None` by the same `if found is None` branch that C11 neutralizes).

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

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_ready.py:427: AssertionError
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

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_ready.py:439: 
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

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_ready.py:84: AssertionError
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

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_ready.py:439: 
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

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_ready.py:84: AssertionError
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

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_ready.py:439: 
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

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_ready.py:84: AssertionError
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

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_ready.py:466: AssertionError
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

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_ready.py:483: AssertionError
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

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launch_place.py:296: AssertionError
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

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_cloud.py:292: AssertionError
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

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_cloud.py:304: AssertionError
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

### C9: the base check asks the server. Axis: the source of the answer

- **Guarded code.** `_base_on_remote` reads `origin`'s owner and repository and calls `_gh_commit_lookup`, which runs `gh api repos/<owner>/<repo>/commits/<sha> --jq .sha`; `_cloud_base_refusal` takes its answer from `_base_on_remote_fn`. No local tracking ref is read. The axis comment is at `_cloud_base_refusal` ("the named base is on the remote, read fresh from the server and never from local tracking refs").
- **Named node.** `test_launcher_cloud.py::test_the_default_gh_call_asks_the_commits_endpoint`. It pins the argv of `_gh_commit_lookup`, which sits outside the functions this proof may neutralize (`_base_on_remote`, `_cloud_base_refusal`), so no neutralization inside them can turn it red. It was not run red.
- **Neutralization chosen.** In `_base_on_remote`, the `_gh_commit_lookup(...)` call and its `None` check replaced with `return True if _git_scrubbed(repo_root, "branch", "-r", "--contains", base, env=env, timeout=_WORKTREE_GIT_TIMEOUT).stdout.strip() else None`, re-introducing a read of local tracking refs. The node that reaches it is `test_launcher_cloud.py::test_a_pushed_commit_is_on_the_remote`.
- **Unrunnable here.** The red run stopped in the fixture, at `git commit` in `test_launcher._init_repo`, before reaching the neutralized line. The commit signer listens on localhost and the sandbox blocks it, and `conftest.py` deletes every `GIT_*` variable per test, so the wrapper's `GIT_CONFIG_*` override never reaches this fixture. That output is not a red. It was captured as the run printed it, and the neutralization was restored by the inverse Edit (launcher.py unchanged from HEAD).

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________________ test_a_pushed_commit_is_on_the_remote _____________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-78/test_a_pushed_commit_is_on_the0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fc07e232b40>

    def test_a_pushed_commit_is_on_the_remote(tmp_path, monkeypatch):
        # axis: the base is asked of GitHub afresh
>       repo = _origin(tmp_path, "git@github.com:acme/widgets.git")
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/c8a-wo1/plugins/superheroes/lib/tests/test_launcher_cloud.py:670: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/c8a-wo1/plugins/superheroes/lib/tests/test_launcher_cloud.py:655: in _origin
    repo = _init_repo(tmp_path / "repo")
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/c8a-wo1/plugins/superheroes/lib/tests/test_launcher.py:57: in _init_repo
    subprocess.run(
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

input = None, capture_output = False, timeout = None, check = True
popenargs = (['git', '-C', '/tmp/claude-0/pytest-of-root/pytest-78/test_a_pushed_commit_is_on_the0/repo', '-c', 'user.email=test@test.local', '-c', ...],)
kwargs = {}

    def run(*popenargs,
            input=None, capture_output=False, timeout=None, check=False, **kwargs):
        """Run command with arguments and return a CompletedProcess instance.
    
        The returned instance will have attributes args, returncode, stdout and
        stderr. By default, stdout and stderr are not captured, and those attributes
        will be None. Pass stdout=PIPE and/or stderr=PIPE in order to capture them,
        or pass capture_output=True to capture both.
    
        If check is True and the exit code was non-zero, it raises a
        CalledProcessError. The CalledProcessError object will have the return code
        in the returncode attribute, and output & stderr attributes if those streams
        were captured.
    
        If timeout (seconds) is given and the process takes too long,
         a TimeoutExpired exception will be raised.
    
        There is an optional argument "input", allowing you to
        pass bytes or a string to the subprocess's stdin.  If you use this argument
        you may not also use the Popen constructor's "stdin" argument, as
        it will be used internally.
    
        By default, all communication is in bytes, and therefore any "input" should
        be bytes, and the stdout and stderr will be bytes. If in text mode, any
        "input" should be a string, and stdout and stderr will be strings decoded
        according to locale encoding, or by "encoding" if set. Text mode is
        triggered by setting any of text, encoding, errors or universal_newlines.
    
        The other arguments are the same as for the Popen constructor.
        """
        if input is not None:
            if kwargs.get('stdin') is not None:
                raise ValueError('stdin and input arguments may not both be used.')
            kwargs['stdin'] = PIPE
    
        if capture_output:
            if kwargs.get('stdout') is not None or kwargs.get('stderr') is not None:
                raise ValueError('stdout and stderr arguments may not be used '
                                 'with capture_output.')
            kwargs['stdout'] = PIPE
            kwargs['stderr'] = PIPE
    
        with Popen(*popenargs, **kwargs) as process:
            try:
                stdout, stderr = process.communicate(input, timeout=timeout)
            except TimeoutExpired as exc:
                process.kill()
                if _mswindows:
                    # Windows accumulates the output in a single blocking
                    # read() call run on child threads, with the timeout
                    # being done in a join() on those threads.  communicate()
                    # _after_ kill() is required to collect that and add it
                    # to the exception.
                    exc.stdout, exc.stderr = process.communicate()
                else:
                    # POSIX _communicate already populated the output so
                    # far into the TimeoutExpired exception.
                    process.wait()
                raise
            except:  # Including KeyboardInterrupt, communicate handled that.
                process.kill()
                # We don't call process.wait() as .__exit__ does that for us.
                raise
            retcode = process.poll()
            if check and retcode:
>               raise CalledProcessError(retcode, process.args,
                                         output=stdout, stderr=stderr)
E               subprocess.CalledProcessError: Command '['git', '-C', '/tmp/claude-0/pytest-of-root/pytest-78/test_a_pushed_commit_is_on_the0/repo', '-c', 'user.email=test@test.local', '-c', 'user.name=test', 'commit', '-q', '-m', 'init']' returned non-zero exit status 128.

/root/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/lib/python3.12/subprocess.py:571: CalledProcessError
----------------------------- Captured stderr call -----------------------------
error: Debug: Namespace set to "git" (ignored)
Debug: Key file set to "/home/claude/.ssh/commit_signing_key.pub" (ignored, using server key)
MCP server request failed (attempt 1/3), retrying in 120.009226ms: failed to send request: Post "http://127.0.0.1:37799/mcp": dial tcp 127.0.0.1:37799: connect: connection refused
MCP server request failed (attempt 2/3), retrying in 251.713788ms: failed to send request: Post "http://127.0.0.1:37799/mcp": dial tcp 127.0.0.1:37799: connect: connection refused
Error: failed to call MCP server: MCP server request failed after 2 retries: failed to send request: Post "http://127.0.0.1:37799/mcp": dial tcp 127.0.0.1:37799: connect: connection refused
Usage:
  environment-runner code-sign [flags]

Flags:
  -h, --help   help for code-sign

Error: failed to call MCP server: MCP server request failed after 2 retries: failed to send request: Post "http://127.0.0.1:37799/mcp": dial tcp 127.0.0.1:37799: connect: connection refused

fatal: failed to write commit object
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_a_pushed_commit_is_on_the_remote
1 failed in 5.16s
```

### C10: only the HTTP 422 no-commit answer reads as absent. Axis: the failure class decides

- **Guarded code.** In `_base_on_remote`, a non-zero `gh` exit is `False` (not on the remote) only when stderr carries `no commit found for sha` and `http 422`; every other failure (404, 401, a dropped connection, 500) is `None`, unchecked.
- **Node.** `test_launcher_cloud.py::test_only_the_422_no_commit_answer_is_absent`
- **Neutralization chosen.** `if _BASE_ABSENT_MARKER in said and "http 422" in said:` replaced with `if _BASE_ABSENT_MARKER in said and "http 404" in said:`, so the 422 answer no longer reads as absent and comes back `None`.
- **Unrunnable here.** Not run. The node's fixture `_origin` calls the same `_init_repo` that stopped C9 at `git commit`, so a run would stop in the fixture and could not show a bite. No receipt exists for this element.

### C11: an unchecked remote refuses. Axis: the check fails closed

- **Guarded code.** In `_cloud_base_refusal`, a `None` answer from `_base_on_remote_fn` maps to `launch-cloud-base-remote-unchecked`.
- **Node.** `test_launcher_cloud.py::test_cloud_base_refusal_maps_the_round_trip_to_its_token`
- **Neutralization applied.** In `_cloud_base_refusal`, `return "launch-cloud-base-remote-unchecked"` (under `if found is None:`) replaced with `return None`, so a remote that could not be asked lets the launch through.
- **Red:**

```
.F.                                                                      [100%]
=================================== FAILURES ===================================
_ test_cloud_base_refusal_maps_the_round_trip_to_its_token[None-launch-cloud-base-remote-unchecked] _

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f87b46b3530>
answer = None, reason = 'launch-cloud-base-remote-unchecked'

    @pytest.mark.parametrize("answer,reason", [
        (False, "launch-cloud-base-not-on-remote"),
        (None, "launch-cloud-base-remote-unchecked"),
        (True, None),
    ])
    def test_cloud_base_refusal_maps_the_round_trip_to_its_token(monkeypatch, answer, reason):
        seen = []
    
        def asked(repo_root, base, env):
            seen.append((repo_root, base))
            return answer
    
        monkeypatch.setattr(L, "_base_on_remote_fn", asked)
>       assert L._cloud_base_refusal("/repo", {"baseCommit": "abc123"}, None) == reason
E       AssertionError: assert None == 'launch-cloud-base-remote-unchecked'
E        +  where None = <function _cloud_base_refusal at 0x7f87b1b323e0>('/repo', {'baseCommit': 'abc123'}, None)
E        +    where <function _cloud_base_refusal at 0x7f87b1b323e0> = L._cloud_base_refusal

/home/user/c8a-wo1/plugins/superheroes/lib/tests/test_launcher_cloud.py:634: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_cloud_base_refusal_maps_the_round_trip_to_its_token[None-launch-cloud-base-remote-unchecked]
1 failed, 2 passed in 3.58s
```

- **Restore.** The inverse Edit; quoted from launcher.py: `        return "launch-cloud-base-remote-unchecked"`
- **Green:**

```
...                                                                      [100%]
3 passed in 1.20s
```
