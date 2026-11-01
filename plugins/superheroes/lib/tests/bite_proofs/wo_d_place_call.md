# Place call WO-D bite-proof: the switch-on guard reads the failed-check marker, the single resolved base and the stale cloud version

> Note (2026-10-31, #2296): owner-machine paths and the name of a consuming project in this record were replaced with neutral placeholders after capture; nothing else changed.

Bite-proof record for `plugins/superheroes/lib/project_config.py` (D1, D2), `plugins/superheroes/lib/launcher.py` (D3) and `plugins/superheroes/lib/cloud_ready.py` (D4). Detectors are in `plugins/superheroes/lib/tests/test_cloud_setup.py`, `test_launcher_place.py` and `test_cloud_ready.py`.

**Status.** The implementer ran every proof (D1 to D4): each neutralization is a targeted Edit in the shipped file, the red is the single named test node run alone, the restore is the inverse Edit, and the green is the same node. Each red below is the last 40 lines of that run's output (the top of the output, the first lines of the failure header, was cut by the `tail -40` the command ran through; the assertion, the diff and the pytest summary line are all inside what is shown). Each green is the last 10 lines. The harness's `sysmon` and `pgrep` lines are not shown. The absolute `tmp_path` prefixes and the worktree path are as printed. No fixture holds a real secret, so nothing is redacted.

- **Run command.** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<T>::<node>" -q -n 4`.
- **Restore receipt, every element.** The restored line is quoted back from the shipped file after the inverse Edit.
- **Pinned condition.** The tests build their repository, store, account and record under `tmp_path`; the platform command is a stand-in, and the moved ref is a local branch of the fixture repository. The pin makes unobservable: the real home directory, the process environment's account, the network and the real wall clock.

## Declared guarded-element set

D1 the switch-on marker refusal (the `is not None` test); D2 the fail-closed `except` on the marker read; D3 the single resolved base used by both the cloud attempt and the local fallback; D4 the stale-version suppression after a failed version check.

Not proven by a neutralization here: the cloud-ready tests for the one shared pass-validity helper (a removal; the existing lapse-boundary tests stay green after it), the frozen-clock default-date test and the read-hook signal test (both test-only).

### D1: the switch-on marker refusal. Axis: marker present refuses

- **Neutralization applied.** In `project_config.set_item`, `check_failed = cloud_check.read_failed_check(cwd, account, root=root) is not None` became `... is not None and False`, so the marker never refuses.
- **Node.** `test_cloud_setup.py::test_switch_on_refused_when_the_last_check_failed_and_stores_nothing`
- **Red:**

```
tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1297/popen-gw0/test_switch_on_refused_when_th0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x10ae12d80>

    def test_switch_on_refused_when_the_last_check_failed_and_stores_nothing(tmp_path, monkeypatch):
        # axis: a failed-check marker that is present keeps cloud builds from switching on — see bite-proof record wo_d_place_call
        repo, store = _setup_repo(tmp_path)
        _check(repo, store)
        assert CC._write_failed_check(repo, ACCOUNT, store, ENVIRONMENT, ["version"], 0) is True
        assert CS.REASON_CHECK_FAILED == "cloud-check-failed"
>       _refused_for_a_failed_check(repo, store, monkeypatch)

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_setup.py:191: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/private/tmp/claude-501/pytest-of-zwrose/pytest-1297/popen-gw0/test_switch_on_refused_when_th0'
store = '/private/tmp/claude-501/pytest-of-zwrose/pytest-1297/popen-gw0/test_switch_on_refused_when_th0/store'
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x10ae12d80>

    def _refused_for_a_failed_check(repo, store, monkeypatch):
        monkeypatch.setitem(sys.modules, "cloud_check", CC)
        got = PC.set_item(repo, "cloudBuilds", True, root=store, account=ACCOUNT, project_name="fixture")
>       assert got == {
            "action": "refused",
            "reason": CS.REASON_CHECK_FAILED,
            "message": CS.switch_message("check-failed", "fixture"),
        }
E       assert {'action': 'w...our machine.'} == {'action': 'r...heck again".'}
E         
E         Differing items:
E         {'action': 'written'} != {'action': 'refused'}
E         {'message': 'Cloud builds are on for fixture. From the next launch, every build that can run in the cloud will.\n\nSay "this one local" at any launch to keep a build on your machine.'} != {'message': 'Cloud builds can\'t be switched on yet: the last check of this project\'s cloud setup failed. Fix what it named, then say "check again".'}
E         Right contains 1 more item:
E         {'reason': 'cloud-check-failed'}
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_setup.py:175: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup.py::test_switch_on_refused_when_the_last_check_failed_and_stores_nothing
1 failed in 5.88s
```

- **Restore.** The inverse Edit; quoted from project_config.py:694: `                check_failed = cloud_check.read_failed_check(cwd, account, root=root) is not None`
- **Green.**

```
.                                                                        [100%]
1 passed in 8.98s
```

### D2: the fail-closed `except` on the marker read. Axis: an unreadable marker refuses

- **Neutralization applied.** In `project_config.set_item`, the `except Exception:` branch's `check_failed = True` became `check_failed = False`, so a marker read that raises proceeds.
- **Node.** `test_cloud_setup.py::test_switch_on_refused_when_the_failed_check_marker_cannot_be_read`
- **Red:**

```
    def test_switch_on_refused_when_the_failed_check_marker_cannot_be_read(tmp_path, monkeypatch):
        # axis: a marker read that raises refuses the switch-on, never proceeds — see bite-proof record wo_d_place_call
        repo, store = _setup_repo(tmp_path)
        _check(repo, store)
    
        def _boom(*a, **k):
            raise RuntimeError("the marker read failed")
    
        monkeypatch.setattr(CC, "read_failed_check", _boom)
>       _refused_for_a_failed_check(repo, store, monkeypatch)

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_setup.py:224: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/private/tmp/claude-501/pytest-of-zwrose/pytest-1299/popen-gw0/test_switch_on_refused_when_th0'
store = '/private/tmp/claude-501/pytest-of-zwrose/pytest-1299/popen-gw0/test_switch_on_refused_when_th0/store'
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x108e86930>

    def _refused_for_a_failed_check(repo, store, monkeypatch):
        monkeypatch.setitem(sys.modules, "cloud_check", CC)
        got = PC.set_item(repo, "cloudBuilds", True, root=store, account=ACCOUNT, project_name="fixture")
>       assert got == {
            "action": "refused",
            "reason": CS.REASON_CHECK_FAILED,
            "message": CS.switch_message("check-failed", "fixture"),
        }
E       assert {'action': 'w...our machine.'} == {'action': 'r...heck again".'}
E         
E         Differing items:
E         {'message': 'Cloud builds are on for fixture. From the next launch, every build that can run in the cloud will.\n\nSay "this one local" at any launch to keep a build on your machine.'} != {'message': 'Cloud builds can\'t be switched on yet: the last check of this project\'s cloud setup failed. Fix what it named, then say "check again".'}
E         {'action': 'written'} != {'action': 'refused'}
E         Right contains 1 more item:
E         {'reason': 'cloud-check-failed'}
E         Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_setup.py:175: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup.py::test_switch_on_refused_when_the_failed_check_marker_cannot_be_read
1 failed in 7.74s
```

- **Restore.** The inverse Edit; quoted from project_config.py:697: `                check_failed = True`
- **Green.**

```
.                                                                        [100%]
1 passed in 4.51s
```

### D3: the single resolved base. Axis: one commit for both attempts

- **Neutralization applied.** In `launcher._cli_launch`, `premise = _premise_with_resolved_base(args.repo_root, premise)` became `premise = premise`, so the fallback launches from the original premise and resolves the ref again.
- **Node.** `test_launcher_place.py::test_a_base_ref_that_moves_between_the_cloud_attempt_and_the_fallback_builds_the_first_commit`
- **Red:**

```
capsys = <_pytest.capture.CaptureFixture object at 0x10963c5f0>
machine = <test_launcher_place._Machine object at 0x1097b4ef0>

    def test_a_base_ref_that_moves_between_the_cloud_attempt_and_the_fallback_builds_the_first_commit(
        tmp_path, monkeypatch, capsys, machine,
    ):
        # axis: a premise's base names one commit for the cloud attempt and the local fallback alike — see bite-proof record wo_d_place_call
        world = _world(tmp_path, monkeypatch)
        _git(world.repo, "branch", "moving")
        first = _git(world.repo, "rev-parse", "moving").strip()
        cloud_calls = []
    
        def spawn_that_moves_the_ref_then_fails(argv, cwd, log_path, child_env, timeout):
            cloud_calls.append(argv)
            tree = _git(world.repo, "rev-parse", "moving^{tree}").strip()
            second = _git(
                world.repo, "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
                "commit-tree", tree, "-p", first, "-m", "the ref moved").strip()
            _git(world.repo, "update-ref", "refs/heads/moving", second)
            raise OSError("no platform")
    
        monkeypatch.setattr(L, "default_cloud_spawn", spawn_that_moves_the_ref_then_fails)
        code, result = _launch(world, capsys, 232, baseCommit="moving")
    
        assert code == 0, result
        assert result["ok"] is True and result["fellBack"] is True
        assert len(cloud_calls) == 1 and len(machine.calls) == 1
        assert _git(world.repo, "rev-parse", "moving").strip() != first
        attempt = result["cloudAttempt"]
        assert _reserved(world.repo, attempt["launchId"])["premise"]["baseCommit"] == first
>       assert _reserved(world.repo, result["launchId"])["premise"]["baseCommit"] == first
E       AssertionError: assert '9efd8a25a8bf...8d76c524642a5' == '0f2f3ff9ba1f...5cdc4319434c7'
E         
E         - 0f2f3ff9ba1ff036ba06cdd50665cdc4319434c7
E         + 9efd8a25a8bf870c6593383507b8d76c524642a5

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_launcher_place.py:370: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_place.py::test_a_base_ref_that_moves_between_the_cloud_attempt_and_the_fallback_builds_the_first_commit
1 failed in 7.41s
```

- **Restore.** The inverse Edit; quoted from launcher.py:3360: `    premise = _premise_with_resolved_base(args.repo_root, premise)`
- **Green.**

```
.                                                                        [100%]
1 passed in 8.83s
```

### D4: the stale-version suppression. Axis: a failed version check leaves no cloud version

- **Neutralization applied.** In `cloud_ready._readiness`, `if failed is not None and "version" in failed:` became `if False and failed is not None and "version" in failed:`, so the record's version stays as the cloud's.
- **Node.** `test_cloud_ready.py::test_a_failed_version_check_leaves_no_cloud_version_unless_the_cloud_reported_one`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_failed_version_check_leaves_no_cloud_version_unless_the_cloud_reported_one _
[gw0] darwin -- Python 3.12.13 /path/to/home/.cache/uv/builds-v0/.tmp8x2U46/bin/python

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1303/popen-gw0/test_a_failed_version_check_le0')

    def test_a_failed_version_check_leaves_no_cloud_version_unless_the_cloud_reported_one(tmp_path):
        # axis: a failed version check leaves the old record in place, so its version is not the cloud's current one — see bite-proof record wo_d_place_call
        repo, store = _ready(tmp_path, plugin_version="1.2.2")
        _mark(repo, store, ["version"])
        got = _read(repo, store)
        _only_false(got, "version")
>       assert got["cloudVersion"] is None and got["failedCheck"] == ["version"]
E       AssertionError: assert ('1.2.2' is None)

/path/to/home/.superheroes-worktrees/superheroes/issue-1746-9ec121c90cfeb086/plugins/superheroes/lib/tests/test_cloud_ready.py:461: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_ready.py::test_a_failed_version_check_leaves_no_cloud_version_unless_the_cloud_reported_one
1 failed in 4.52s
```

- **Restore.** The inverse Edit; quoted from cloud_ready.py:156: `        if failed is not None and "version" in failed:`
- **Green.**

```
.                                                                        [100%]
1 passed in 4.78s
```
