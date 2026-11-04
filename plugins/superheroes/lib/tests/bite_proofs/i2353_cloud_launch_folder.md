# I2353 cloud-launch-folder bite-proof record (launch layer)

Invariant: a cloud launch never reads-for-write, moves, or writes any checkout except the launcher's
own folder; the cloud command runs with `cwd` = that folder; and the command runs only while the folder
is (under a held folder lock, held continuously from the final check through the cloud command) on a
named branch whose local head and whose tip on `origin` both equal the launch's target commit.

This record covers the launch layer only. The folder-setup elements (the symlink check, the common-dir
check, the folder path, the detached start) live in layer 1's functions and are proven in
`i2353_l1_cloud_launch_folder.md`.

Guarded-element set (declared by the order): E1 to E4, E7 to E9, E11 to E13 below, all in
`plugins/superheroes/lib/launcher.py`; detectors are in
`plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py` (E11's is in
`plugins/superheroes/lib/tests/test_i2272_launcher.py`). Each node was run alone as
`scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-l2 -m pytest "<node>" -q -p no:cacheprovider`
with the detector unedited. Every capture below is the full output of that command; each begins with
the same harness warning line (`UV_NATIVE_TLS`), which is not part of the test. Nothing is redacted
(there is no secret in any capture; the paths are pytest temp directories). Every neutralization was a
targeted edit and every restore its inverse edit (no `git checkout`/`restore`/`reset`/`stash`); the
restored lines were read back from the file after the last restore and are quoted at the end.

Reading the reds: a refusal under the wrong token still counts as red (the order's rule); the axis of
each red is stated per entry. Where the neutralized guard lets the launch fall through to the next guard
(E2), the red token is the next guard's.

Disclosure: the E1 green run and the E2 neutralization edit were issued in one tool batch. The E1 green
node (a dirty folder) refuses at E1's line, before it could reach E2's line, so E1's green is the restored
E1 line alone.

---

## E1 - clean-tree refusal (`_prepare_cloud_launch_folder`)

**Guarded element:** `launcher.py:3225` `if (status.stdout or "").strip():` -> `off-base` / `uncommitted-changes` (axis line 3224).
**Axis:** a folder with uncommitted changes refuses, so the repair never discards or carries them.
**Node:** `test_row3_a_folder_with_uncommitted_changes_refuses_and_is_left_as_it_was`.

**Neutralization:** `if (status.stdout or "").strip():` -> `if False and (status.stdout or "").strip():`.

**Raw red** (the launch ran the command: `ok` is True):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_row3_a_folder_with_uncommitted_changes_refuses_and_is_left_as_it_was ___

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-46/test_row3_a_folder_with_uncomm0')

    def test_row3_a_folder_with_uncommitted_changes_refuses_and_is_left_as_it_was(tmp_path):
        # axis: a folder with uncommitted changes refuses and nothing in it is moved or discarded — see bite-proof record i2353_cloud_launch_folder
        repo, folder = _world(tmp_path)
        with open(os.path.join(folder, "scratch.txt"), "w") as fh:
            fh.write("mine\n")
        primary_before = _snap(repo)
        folder_before = _snap(folder)
        calls = []
        result = _launch(repo, tmp_path, _spy(calls))
>       _refused(repo, result, OFF_BASE, "uncommitted-changes", folder, calls, primary_before)

/home/user/superheroes/.wt-2353-l2/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:205: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/superheroes/.wt-2353-l2/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:133: in _refused
    _assert_refused_cloud_lane(repo, result, reason, "cloud-base")
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-46/test_row3_a_folder_with_uncomm0/repo'
result = {'ok': True, 'reason': None, 'launchId': 'launch-52fc604cc3512bfa', 'place': 'cloud', ...}
reason = 'launch-cloud-checkout-off-base', stage = 'cloud-base'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
>       assert result["ok"] is False
E       assert True is False

/home/user/superheroes/.wt-2353-l2/plugins/superheroes/lib/tests/test_launcher_cloud.py:635: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py::test_row3_a_folder_with_uncommitted_changes_refuses_and_is_left_as_it_was
1 failed in 8.80s
```
**Restore:** inverse edit, `if False and (status.stdout or "").strip():` -> `if (status.stdout or "").strip():`.
**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 2.97s
```

---

## E2 - no branch at the base (`_prepare_cloud_launch_folder`)

**Guarded element:** `launcher.py:3231` `if why == "no-branch-at-base":` -> `off-base` / `no-branch-at-base` (axis line 3230).
**Axis:** a base the remote holds but no branch tip equals refuses, because a cloud start reads a branch's tip.
**Node:** `test_row4_a_base_no_remote_branch_tip_equals_refuses_and_the_folder_is_unchanged`.

**Neutralization:** `if why == "no-branch-at-base":` -> `if False and why == "no-branch-at-base":`.

**Raw red** (wrong-token red: the neutralized guard falls through; with `branch` None the fetch of `origin/None` fails and the next guard refuses `remote-unchecked`):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_row4_a_base_no_remote_branch_tip_equals_refuses_and_the_folder_is_unchanged _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-48/test_row4_a_base_no_remote_bra0')

    def test_row4_a_base_no_remote_branch_tip_equals_refuses_and_the_folder_is_unchanged(tmp_path):
        # axis: a base the remote holds but no branch tip equals refuses, because a cloud start reads a branch's tip — see bite-proof record i2353_cloud_launch_folder
        repo, folder = _world(tmp_path)
        base = _head_sha(repo)
        branch = _symbolic(repo)
        _remote_commit(tmp_path, repo, [branch, "main"], "beyond.txt", start=base)
        primary_before = _snap(repo)
        folder_before = _snap(folder)
        calls = []
        result = _launch(repo, tmp_path, _spy(calls), premise=_valid_premise(repo, baseCommit=base))
>       _refused(repo, result, OFF_BASE, "no-branch-at-base", folder, calls, primary_before)

/home/user/superheroes/.wt-2353-l2/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:224: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/superheroes/.wt-2353-l2/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:133: in _refused
    _assert_refused_cloud_lane(repo, result, reason, "cloud-base")
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-48/test_row4_a_base_no_remote_bra0/repo'
result = {'ok': False, 'reason': 'launch-cloud-checkout-remote-unchecked', 'launchId': 'launch-9f41d2c98e982a1a', 'warnings': [], ...}
reason = 'launch-cloud-checkout-off-base', stage = 'cloud-base'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
        assert result["ok"] is False
>       assert result["reason"] == reason
E       AssertionError: assert 'launch-cloud...ote-unchecked' == 'launch-cloud...kout-off-base'
E         
E         - launch-cloud-checkout-off-base
E         + launch-cloud-checkout-remote-unchecked

/home/user/superheroes/.wt-2353-l2/plugins/superheroes/lib/tests/test_launcher_cloud.py:636: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py::test_row4_a_base_no_remote_branch_tip_equals_refuses_and_the_folder_is_unchanged
1 failed in 3.31s
```
**Restore:** inverse edit, `if False and why == "no-branch-at-base":` -> `if why == "no-branch-at-base":`.
**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.67s
```

---

## E3 - local commits (`_prepare_cloud_launch_folder`)

**Guarded element:** `launcher.py:3259` `if ahead is None or ahead.returncode != 0:` -> `off-base` / `local-commits` (axis line 3258).
**Axis:** a local branch holding commits the target lacks refuses, so the repair is only ever a fast-forward and never discards a commit.
**Node:** `test_row6_local_commits_on_the_folders_branch_refuse_and_the_branch_is_not_reset`.

**Neutralization:** `if ahead is None or ahead.returncode != 0:` -> `if False and (ahead is None or ahead.returncode != 0):`.

**Raw red** (the launch ran, after `checkout -B` reset the folder's branch off its local commit):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_row6_local_commits_on_the_folders_branch_refuse_and_the_branch_is_not_reset _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-50/test_row6_local_commits_on_the0')

    def test_row6_local_commits_on_the_folders_branch_refuse_and_the_branch_is_not_reset(tmp_path):
        # axis: a local branch holding commits the target lacks refuses, so the repair is only ever a fast-forward — see bite-proof record i2353_cloud_launch_folder
        repo, folder = _world(tmp_path)
        base = _head_sha(repo)
        # The folder starts detached with no local branch; a first launch creates the branch at the
        # target, and the local commit is then made on that branch inside the folder.
        first_calls = []
        first = _launch(
            repo, tmp_path, _spy(first_calls), issue=657,
            premise=_valid_premise(repo, issue=657, baseCommit=base),
        )
        assert first["ok"] is True, first
        assert _symbolic(folder) == _symbolic(repo)
        mine = _commit(folder, "local-work.txt")
        assert mine != base
        primary_before = _snap(repo)
        folder_before = _snap(folder)
        calls = []
        result = _launch(repo, tmp_path, _spy(calls))
>       _refused(repo, result, OFF_BASE, "local-commits", folder, calls, primary_before)

/home/user/superheroes/.wt-2353-l2/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:268: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/superheroes/.wt-2353-l2/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:133: in _refused
    _assert_refused_cloud_lane(repo, result, reason, "cloud-base")
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-50/test_row6_local_commits_on_the0/repo'
result = {'ok': True, 'reason': None, 'launchId': 'launch-8ffb8abf50fb0aad', 'place': 'cloud', ...}
reason = 'launch-cloud-checkout-off-base', stage = 'cloud-base'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
>       assert result["ok"] is False
E       assert True is False

/home/user/superheroes/.wt-2353-l2/plugins/superheroes/lib/tests/test_launcher_cloud.py:635: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py::test_row6_local_commits_on_the_folders_branch_refuse_and_the_branch_is_not_reset
1 failed in 2.07s
```
**Restore:** inverse edit, `if False and (ahead is None or ahead.returncode != 0):` -> `if ahead is None or ahead.returncode != 0:`.
**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 2.17s
```

---

## E4 - `--no-overwrite-ignore` (`_prepare_cloud_launch_folder`)

**Guarded element:** `launcher.py:3266` the `--no-overwrite-ignore` argument of `git checkout --quiet ... -B <branch> <target>` (axis line 3264).
**Axis:** an ignored local file that the target tracks refuses the switch (`off-base` / `checkout-failed`) instead of being overwritten; the clean-tree check cannot see ignored files.
**Node:** `test_row7_an_ignored_file_the_target_tracks_refuses_the_switch_and_keeps_its_bytes`.

**Neutralization:** `folder, "checkout", "--quiet", "--no-overwrite-ignore", "-B", branch, target,` -> `folder, "checkout", "--quiet", "-B", branch, target,`.

**Raw red** (the launch ran; the ignored file was overwritten by the switch):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_row7_an_ignored_file_the_target_tracks_refuses_the_switch_and_keeps_its_bytes _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-52/test_row7_an_ignored_file_the_0')

    def test_row7_an_ignored_file_the_target_tracks_refuses_the_switch_and_keeps_its_bytes(tmp_path):
        # axis: --no-overwrite-ignore makes an ignored local file that the target tracks refuse the switch instead of being overwritten — see bite-proof record i2353_cloud_launch_folder
        repo, folder = _world(tmp_path)
        base = _head_sha(repo)
        tracked = _remote_commit(
            tmp_path, repo, ["other"], "gen.txt", start=base, text="tracked\n")
        # Ignored through the folder's own exclude file: an untracked .gitignore would itself make
        # the tree dirty and this row would read as uncommitted changes.
        with open(os.path.join(folder, ".git", "info", "exclude"), "a") as fh:
            fh.write("gen.txt\n")
        with open(os.path.join(folder, "gen.txt"), "w") as fh:
            fh.write("localbytes\n")
        assert _git(folder, "status", "--porcelain", "--untracked-files=all") == ""
        primary_before = _snap(repo)
        folder_before = _snap(folder)
        calls = []
        result = _launch(
            repo, tmp_path, _spy(calls), premise=_valid_premise(repo, baseCommit=tracked))
>       _refused(repo, result, OFF_BASE, "checkout-failed", folder, calls, primary_before)

/home/user/superheroes/.wt-2353-l2/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:294: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/superheroes/.wt-2353-l2/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:133: in _refused
    _assert_refused_cloud_lane(repo, result, reason, "cloud-base")
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-52/test_row7_an_ignored_file_the_0/repo'
result = {'ok': True, 'reason': None, 'launchId': 'launch-75effff0ed7050d8', 'place': 'cloud', ...}
reason = 'launch-cloud-checkout-off-base', stage = 'cloud-base'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
>       assert result["ok"] is False
E       assert True is False

/home/user/superheroes/.wt-2353-l2/plugins/superheroes/lib/tests/test_launcher_cloud.py:635: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py::test_row7_an_ignored_file_the_target_tracks_refuses_the_switch_and_keeps_its_bytes
1 failed in 1.94s
```
**Restore:** inverse edit, `folder, "checkout", "--quiet", "-B", branch, target,` -> `folder, "checkout", "--quiet", "--no-overwrite-ignore", "-B", branch, target,`.
**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.83s
```

---

## E5 - the symlink check (`_validate_cloud_launch_folder`)

The element lives in layer 1's functions and is proven in `i2353_l1_cloud_launch_folder.md`.

---

## E6 - common-dir independence (`_validate_cloud_launch_folder`)

The element lives in layer 1's functions and is proven in `i2353_l1_cloud_launch_folder.md`.

---

## E7 - missing-folder refusal and never-create (`_prepare_cloud_launch_folder`)

**Guarded element:** `launcher.py:3214` `if found == "missing": return missing()` -> `launch-cloud-folder-missing` (axis line 3212).
**Axis:** a folder the setup verb has not made refuses, and a launch never creates it (an untrusted new folder hangs the CLI's trust prompt).
**Node:** `test_row8_a_missing_folder_refuses_and_is_never_created`.

**Neutralization:** `return missing()` (under `if found == "missing":`) -> the two lines `ensure_cloud_launch_folder(repo_root, env)` and `found = None` (the launch makes the folder and goes on).

**Raw red** (the launch made the folder and ran the command):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_row8_a_missing_folder_refuses_and_is_never_created ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-54/test_row8_a_missing_folder_ref0')

    def test_row8_a_missing_folder_refuses_and_is_never_created(tmp_path):
        # axis: a folder the setup verb has not made refuses, and a launch never creates it — see bite-proof record i2353_cloud_launch_folder
        repo = _cloud_repo(tmp_path)
        folder = L.cloud_launch_folder_path(repo)
        assert folder is not None and not os.path.lexists(folder)
        primary_before = _snap(repo)
        calls = []
        result = _launch(repo, tmp_path, _spy(calls))
>       _assert_refused_cloud_lane(repo, result, "launch-cloud-folder-missing", "cloud-base")

/home/user/superheroes/.wt-2353-l2/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:311: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-54/test_row8_a_missing_folder_ref0/repo'
result = {'ok': True, 'reason': None, 'launchId': 'launch-ecf25ff07d256bb6', 'place': 'cloud', ...}
reason = 'launch-cloud-folder-missing', stage = 'cloud-base'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
>       assert result["ok"] is False
E       assert True is False

/home/user/superheroes/.wt-2353-l2/plugins/superheroes/lib/tests/test_launcher_cloud.py:635: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py::test_row8_a_missing_folder_refuses_and_is_never_created
1 failed in 1.82s
```
**Restore:** inverse edit, the two lines back to `return missing()`.
**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.58s
```

---

## E8 - lock busy (`_cloud_launch_folder_lock`)

**Guarded element:** `launcher.py:3313` `yield "launch-cloud-folder-busy", {"launchFolder": folder}` / `return` on the wait running out (axis line 3311).
**Axis:** a folder another launch holds refuses after the wait and the command does not run, so two launches never move one folder at once.
**Node:** `test_row11_a_folder_another_launch_holds_refuses_busy_after_the_wait`.

**Neutralization:** the two lines `yield "launch-cloud-folder-busy", {"launchFolder": folder}` and `return` -> `break` (the launch goes on without the lock once the wait is over).

**Raw red** (the launch ran while the test held the lock):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_row11_a_folder_another_launch_holds_refuses_busy_after_the_wait _____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-56/test_row11_a_folder_another_la0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f6fc35d18b0>

    def test_row11_a_folder_another_launch_holds_refuses_busy_after_the_wait(tmp_path, monkeypatch):
        # axis: a folder lock another launch holds refuses after the wait and the command does not run — see bite-proof record i2353_cloud_launch_folder
        repo, folder = _world(tmp_path)
        monkeypatch.setattr(L, "_CLOUD_FOLDER_LOCK_WAIT_SECONDS", 0.3)
        primary_before = _snap(repo)
        folder_before = _snap(folder)
        fd = os.open(folder + ".lock", os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            calls = []
            result = _launch(repo, tmp_path, _spy(calls))
        finally:
            os.close(fd)
>       _assert_refused_cloud_lane(repo, result, "launch-cloud-folder-busy", "cloud-base")

/home/user/superheroes/.wt-2353-l2/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:410: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-56/test_row11_a_folder_another_la0/repo'
result = {'ok': True, 'reason': None, 'launchId': 'launch-afae952bc8d27fd6', 'place': 'cloud', ...}
reason = 'launch-cloud-folder-busy', stage = 'cloud-base'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
>       assert result["ok"] is False
E       assert True is False

/home/user/superheroes/.wt-2353-l2/plugins/superheroes/lib/tests/test_launcher_cloud.py:635: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py::test_row11_a_folder_another_launch_holds_refuses_busy_after_the_wait
1 failed in 2.51s
```
**Restore:** inverse edit, `break` -> the `yield "launch-cloud-folder-busy", {"launchFolder": folder}` and `return` lines.
**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 2.02s
```

Pinned condition (E8, E13 and row 12): the lock wait is monkeypatched to 0.3 seconds in the test and the
holder is the test's own file descriptor in the same process. Production waits up to 600 seconds and the
holder is another launcher process; the pin makes that wait length and cross-process contention
unobservable, and the flock conflict between two descriptors of one process is what stands in for it.

---

## E9 - spawn `cwd` is the folder (`_run_cloud_spawn`)

**Guarded element:** `launcher.py:1923` `spawned = spawn(argv, cwd, log_path, child_env, timeout)` (axis line 1922).
**Axis:** the cloud command runs in the launcher's own folder, never the primary checkout.
**Node:** `test_row1_a_base_that_is_an_unmerged_branch_tip_launches_from_the_folder_on_that_branch`.

**Neutralization:** `spawned = spawn(argv, cwd, log_path, child_env, timeout)` -> `spawned = spawn(argv, repo_root, log_path, child_env, timeout)`.

**Raw red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_row1_a_base_that_is_an_unmerged_branch_tip_launches_from_the_folder_on_that_branch _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-58/test_row1_a_base_that_is_an_un0')

    def test_row1_a_base_that_is_an_unmerged_branch_tip_launches_from_the_folder_on_that_branch(
        tmp_path,
    ):
        # axis: the command runs in the launcher's folder, which is moved to the branch at the base, while the primary checkout stays where it was — see bite-proof record i2353_cloud_launch_folder
        repo, folder = _world(tmp_path)
        main = _head_sha(repo)
        pr = _remote_commit(tmp_path, repo, ["pr"], "pr.txt", start=main)
        assert pr != main
        before = _snap(repo)
        calls = []
        result = _launch(repo, tmp_path, _spy(calls), premise=_valid_premise(repo, baseCommit=pr))
        assert result["ok"] is True, result
        assert len(calls) == 1
>       assert calls[0]["cwd"] == folder
E       AssertionError: assert '/tmp/claude-...s_an_un0/repo' == '/tmp/claude-...-c782b9bfd901'
E         
E         Skipping 61 identical leading characters in diff, use -v to show
E         - is_an_un0/wt-root/repo/cloud-launch-c782b9bfd901
E         + is_an_un0/repo

/home/user/superheroes/.wt-2353-l2/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:156: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py::test_row1_a_base_that_is_an_unmerged_branch_tip_launches_from_the_folder_on_that_branch
1 failed in 1.96s
```
**Restore:** inverse edit, `repo_root` -> `cwd` in that call.
**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.80s
```

---

## E10 - the folder path comes from the common dir (`cloud_launch_folder_path`)

The element lives in layer 1's functions and is proven in `i2353_l1_cloud_launch_folder.md`.

---

## E11 - the final check goes through the one refusal entry point (`launch_build`, final cloud site)

**Guarded element:** `launcher.py:4727` `drift = _cloud_start_refusal(repo_root, stamped, env, lock_held=True)` and the `lock_held` branch at `launcher.py:3386-3388` (axis line 3387).
**Axis:** the final check runs under the lock the caller already holds, through the one refusal entry point, so a test or hook that wraps `_cloud_start_refusal` sees the final lookup.
**Node:** `plugins/superheroes/lib/tests/test_i2272_launcher.py::test_a_limit_that_expires_during_the_final_cloud_checkout_lookup_refuses_and_spawns_nothing`.

**Neutralization:** at the final site, `drift = _cloud_start_refusal(repo_root, stamped, env, lock_held=True)` -> `drift = _cloud_start_check(repo_root, stamped, env)[1]`.

**Raw red** (the wrapped entry point never saw the final lookup, so `lookups` stayed empty):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_limit_that_expires_during_the_final_cloud_checkout_lookup_refuses_and_spawns_nothing _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-60/test_a_limit_that_expires_duri0')
account = <test_i2272_launcher._Account object at 0x7f5976248a70>
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f5976246960>

    def test_a_limit_that_expires_during_the_final_cloud_checkout_lookup_refuses_and_spawns_nothing(
        tmp_path, account, monkeypatch,
    ):
        # axis: the limit the re-check relied on is compared with the clock right before the cloud command with no remote read, so a reset during the final remote lookup refuses limit-expired and spawns nothing — see bite-proof record i2272_launcher
        repo = _adopted_repo(tmp_path)
        _two_bound_lanes(repo)
        account.limited_until()
        clock = _Crossing()
        monkeypatch.setattr(L, "_now_fn", clock)
        real = L._cloud_start_refusal
        real_check = L._original_session_refusal
        rechecked = []
        lookups = []
    
        def check_marks(*args, **kwargs):
            result = real_check(*args, **kwargs)
            rechecked.append(1)
            return result
    
        def lookup_then_cross(*args, **kwargs):
            result = real(*args, **kwargs)
            if len(rechecked) >= 2:  # the final lookup, after the pre-spawn re-check
                lookups.append(1)
                clock.cross()
            return result
    
        monkeypatch.setattr(L, "_original_session_refusal", check_marks)
        monkeypatch.setattr(L, "_cloud_start_refusal", lookup_then_cross)
        result, calls = _adopt(repo, tmp_path, branch=ADOPTED)
>       assert lookups
E       assert []

/home/user/superheroes/.wt-2353-l2/plugins/superheroes/lib/tests/test_i2272_launcher.py:577: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_launcher.py::test_a_limit_that_expires_during_the_final_cloud_checkout_lookup_refuses_and_spawns_nothing
1 failed in 1.98s
```
**Restore:** inverse edit, `drift = _cloud_start_check(repo_root, stamped, env)[1]` -> `drift = _cloud_start_refusal(repo_root, stamped, env, lock_held=True)`.
**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.96s
```

---

## E12 - the lock file cannot be opened (`_cloud_launch_folder_lock`)

**Guarded element:** `launcher.py:3300-3302` the `yield "launch-cloud-checkout-unreadable", {... "folderRepair": "lock-failed" ...}` in the `except OSError:` of the lock open (axis line 3299).
**Axis:** a lock file that cannot be opened refuses, so a launch never runs unguarded.
**Node:** `test_a_lock_file_that_cannot_be_opened_refuses_lock_failed_and_nothing_runs` (new: the folder exists and `<folder>.lock` is a directory, so the open fails; asserts `launch-cloud-checkout-unreadable`, `folderRepair: "lock-failed"`, no spawn, the primary and the folder unchanged).

**Neutralization:** the three-line `yield "launch-cloud-checkout-unreadable", {...}` (under `except OSError:` of the `os.open`) -> `yield None` (the launch goes on without a lock).

**Raw red** (the launch ran with no lock):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_lock_file_that_cannot_be_opened_refuses_lock_failed_and_nothing_runs __

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-62/test_a_lock_file_that_cannot_b0')

    def test_a_lock_file_that_cannot_be_opened_refuses_lock_failed_and_nothing_runs(tmp_path):
        # axis: a lock file that cannot be opened refuses, so a launch never runs unguarded — see bite-proof record i2353_cloud_launch_folder
        repo, folder = _world(tmp_path)
        os.mkdir(folder + ".lock")
        primary_before = _snap(repo)
        folder_before = _snap(folder)
        calls = []
        result = _launch(repo, tmp_path, _spy(calls))
>       _refused(repo, result, UNREADABLE, "lock-failed", folder, calls, primary_before)

/home/user/superheroes/.wt-2353-l2/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:425: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/superheroes/.wt-2353-l2/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:133: in _refused
    _assert_refused_cloud_lane(repo, result, reason, "cloud-base")
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-62/test_a_lock_file_that_cannot_b0/repo'
result = {'ok': True, 'reason': None, 'launchId': 'launch-630eb3691d57f7b1', 'place': 'cloud', ...}
reason = 'launch-cloud-checkout-unreadable', stage = 'cloud-base'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
>       assert result["ok"] is False
E       assert True is False

/home/user/superheroes/.wt-2353-l2/plugins/superheroes/lib/tests/test_launcher_cloud.py:635: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py::test_a_lock_file_that_cannot_be_opened_refuses_lock_failed_and_nothing_runs
1 failed in 1.90s
```
**Restore:** inverse edit, `yield None` -> the three-line `yield "launch-cloud-checkout-unreadable", {"launchFolder": folder, "folderRepair": "lock-failed", "checkout": folder,}`.
**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.50s
```

---

## E13 - the final-site lock refusal (`launch_build`, final cloud site)

**Guarded element:** `launcher.py:4721` `if held is not None:` at the final site, terminalizing at stage `cloud-base` (axis line 4720).
**Axis:** a folder lock that is not held terminalizes the unstarted lane like any drift refusal, and the command does not run.
**Node:** `test_a_lock_the_final_check_cannot_take_terminalizes_the_lane_and_nothing_runs` (new: `_cloud_start_refusal` is wrapped; after its first call, the pre-reservation site, the test takes `flock` on `<folder>.lock` and keeps it; the wait is 0.3 s; the final site cannot take the lock. Asserts the wrapper saw only the first call, a `reserved` record exists, the lane is terminalized `refused` / `cloud-base` / `launch-cloud-folder-busy` and not started, and the spawn spy was never called).

**Neutralization:** at the final site, `if held is not None:` -> `if False and held is not None:` (a lock refusal is treated as held: the launch falls through to the check and the spawn).

**Raw red** (the final site went on to the check: the wrapper saw a second call, `lock_held=True`):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_lock_the_final_check_cannot_take_terminalizes_the_lane_and_nothing_runs _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-64/test_a_lock_the_final_check_ca0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f122c2ccc50>

    def test_a_lock_the_final_check_cannot_take_terminalizes_the_lane_and_nothing_runs(
        tmp_path, monkeypatch,
    ):
        # axis: a folder lock that is not held terminalizes the unstarted lane like any drift refusal, and the command does not run — see bite-proof record i2353_cloud_launch_folder
        repo, folder = _world(tmp_path)
        monkeypatch.setattr(L, "_CLOUD_FOLDER_LOCK_WAIT_SECONDS", 0.3)
        real = L._cloud_start_refusal
        seen = []
        held = []
    
        def wrapper(*args, **kwargs):
            got = real(*args, **kwargs)
            seen.append(kwargs.get("lock_held", False))
            if len(seen) == 1:
                # The pre-reservation check has passed and released the lock; another launch takes it
                # now and keeps it, so only the final site finds it busy.
                fd = os.open(folder + ".lock", os.O_RDWR | os.O_CREAT, 0o600)
                fcntl.flock(fd, fcntl.LOCK_EX)
                held.append(fd)
            return got
    
        monkeypatch.setattr(L, "_cloud_start_refusal", wrapper)
        primary_before = _snap(repo)
        calls = []
        try:
            result = _launch(repo, tmp_path, _spy(calls))
        finally:
            for fd in held:
                os.close(fd)
        assert held, "the pre-reservation check never ran"
        # The refusal came from the final site: the pre-reservation call is the only one that ran
        # the check, and by then the lane was reserved.
>       assert seen == [False]
E       assert [False, True] == [False]
E         
E         Left contains one more item: True
E         Use -v to get more diff

/home/user/superheroes/.wt-2353-l2/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:462: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py::test_a_lock_the_final_check_cannot_take_terminalizes_the_lane_and_nothing_runs
1 failed in 2.20s
```
**Restore:** inverse edit, `if False and held is not None:` -> `if held is not None:`.
**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.95s
```

---

## Restore receipt (restored lines read back from `launcher.py` after the last restore)

```
1923:        spawned = spawn(argv, cwd, log_path, child_env, timeout)
3214:    if found == "missing":
3215:        return missing()
3225:    if (status.stdout or "").strip():
3231:    if why == "no-branch-at-base":
3259:        if ahead is None or ahead.returncode != 0:
3266:        folder, "checkout", "--quiet", "--no-overwrite-ignore", "-B", branch, target,
3300:        yield "launch-cloud-checkout-unreadable", {
3301:            "launchFolder": folder, "folderRepair": "lock-failed", "checkout": folder,
3302:        }
3313:                    yield "launch-cloud-folder-busy", {"launchFolder": folder}
3314:                    return
3386:    if lock_held:
3388:        return _cloud_start_check(repo_root, stamped, env)[1]
4721:            if held is not None:
4727:            drift = _cloud_start_refusal(repo_root, stamped, env, lock_held=True)
```

Axis lines in `launcher.py` that name `i2353_cloud_launch_folder`, each with the element that proves it:
1922 (E9), 3212 (E7), 3224 (E1), 3230 (E2), 3258 (E3), 3264 (E4), 3299 (E12), 3311 (E8), 3387 (E11),
4720 (E13).

## Not proven by this record

- The tests outside the declared set (`test_row13_*`, `test_row14_*`, `test_row2_*`, `test_row5_*`,
  `test_row12_*`, the row 9 and row 10 nodes, and
  `test_the_branch_choice_prefers_the_default_branch_then_the_lexically_first`) were not run red; the
  declared set above is what the order asked proven. The row 9 and row 10 nodes carry axis comments that
  name this record, but their elements are layer 1's (E5, E6, E10) and are proven in
  `i2353_l1_cloud_launch_folder.md`.
- E2's red is a wrong-token red (above), not the expected `no-branch-at-base` token.
