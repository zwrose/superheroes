# I2353 cloud-launch-folder bite-proof record

Invariant: a cloud launch never reads-for-write, moves, or writes any checkout except the launcher's
own folder; the cloud command runs with `cwd` = that folder; and the command runs only while the folder
is (under a held folder lock) on a named branch whose local head and whose tip on `origin` both equal
the launch's target commit.

Guarded-element set (declared by the order): E1 to E10 below, all in
`plugins/superheroes/lib/launcher.py`; detectors are in
`plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py`. Each node was run alone as
`scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo1 -m pytest "<node>" -q -p no:cacheprovider`
with the detector unedited. Every capture below is the full output of that command; each begins with
the same harness warning line (`UV_NATIVE_TLS`), which is not part of the test. Nothing is redacted
(there is no secret in any capture; the paths are pytest temp directories). Every neutralization was a
targeted edit and every restore its inverse edit (no `git checkout`/`restore`/`reset`/`stash`); the
restored lines were read back from the file after the last restore and are quoted at the end.

Reading the reds: a refusal under the wrong token still counts as red (the order's rule); the axis of
each red is stated per entry. Where the neutralized guard lets the launch fall through to the next guard
(E2), the red token is the next guard's.

---

## E1 - clean-tree refusal (`_prepare_cloud_launch_folder`, step 5c)

**Guarded element:** `launcher.py:3192` `if (status.stdout or "").strip():` -> `off-base` / `uncommitted-changes`.
**Axis:** a folder with uncommitted changes refuses, so the repair never discards or carries them.
**Node:** `test_row3_a_folder_with_uncommitted_changes_refuses_and_is_left_as_it_was`.

**Neutralization:** `if (status.stdout or "").strip():` -> `if False and (status.stdout or "").strip():`.

**Raw red** (the launch ran the command: `ok` is True):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_row3_a_folder_with_uncommitted_changes_refuses_and_is_left_as_it_was ___

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-3/test_row3_a_folder_with_uncomm0')

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

/home/user/superheroes/.wt-2353-wo1/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:193: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/superheroes/.wt-2353-wo1/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:131: in _refused
    _assert_refused_cloud_lane(repo, result, reason, "cloud-base")
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-3/test_row3_a_folder_with_uncomm0/repo'
result = {'ok': True, 'reason': None, 'launchId': 'launch-a83cfad87d7d4bf3', 'place': 'cloud', ...}
reason = 'launch-cloud-checkout-off-base', stage = 'cloud-base'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
>       assert result["ok"] is False
E       assert True is False

/home/user/superheroes/.wt-2353-wo1/plugins/superheroes/lib/tests/test_launcher_cloud.py:635: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py::test_row3_a_folder_with_uncommitted_changes_refuses_and_is_left_as_it_was
1 failed in 1.98s
```
**Restore:** inverse edit, `if False and (status.stdout or "").strip():` -> `if (status.stdout or "").strip():`.
**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 2.21s
```

---

## E2 - no branch at the base (`_prepare_cloud_launch_folder`, step 5d)

**Guarded element:** `launcher.py:3198` `if why == "no-branch-at-base":` -> `off-base` / `no-branch-at-base`.
**Axis:** a base the remote holds but no branch tip equals refuses, because a cloud start reads a branch's tip.
**Node:** `test_row4_a_base_no_remote_branch_tip_equals_refuses_and_the_folder_is_unchanged`.

**Neutralization:** `if why == "no-branch-at-base":` -> `if False and why == "no-branch-at-base":`.

**Raw red** (wrong-token red: the neutralized guard falls through; with `branch` None the fetch of `origin/None` fails and the next guard refuses `remote-unchecked`):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_row4_a_base_no_remote_branch_tip_equals_refuses_and_the_folder_is_unchanged _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-5/test_row4_a_base_no_remote_bra0')

    def test_row4_a_base_no_remote_branch_tip_equals_refuses_and_the_folder_is_unchanged(tmp_path):
        # axis: a base the remote holds but no branch tip equals refuses, because a cloud start reads a branch's tip — see bite-proof record i2353_cloud_launch_folder
        repo, folder = _world(tmp_path)
        base = _head_sha(repo)
        branch = _symbolic(folder)
        _remote_commit(tmp_path, repo, [branch, "main"], "beyond.txt", start=base)
        primary_before = _snap(repo)
        folder_before = _snap(folder)
        calls = []
        result = _launch(repo, tmp_path, _spy(calls), premise=_valid_premise(repo, baseCommit=base))
>       _refused(repo, result, OFF_BASE, "no-branch-at-base", folder, calls, primary_before)

/home/user/superheroes/.wt-2353-wo1/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:212: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/superheroes/.wt-2353-wo1/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:131: in _refused
    _assert_refused_cloud_lane(repo, result, reason, "cloud-base")
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-5/test_row4_a_base_no_remote_bra0/repo'
result = {'ok': False, 'reason': 'launch-cloud-checkout-remote-unchecked', 'launchId': 'launch-e7b250ebe8ad0c4a', 'warnings': [], ...}
reason = 'launch-cloud-checkout-off-base', stage = 'cloud-base'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
        assert result["ok"] is False
>       assert result["reason"] == reason
E       AssertionError: assert 'launch-cloud...ote-unchecked' == 'launch-cloud...kout-off-base'
E         
E         - launch-cloud-checkout-off-base
E         + launch-cloud-checkout-remote-unchecked

/home/user/superheroes/.wt-2353-wo1/plugins/superheroes/lib/tests/test_launcher_cloud.py:636: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py::test_row4_a_base_no_remote_branch_tip_equals_refuses_and_the_folder_is_unchanged
1 failed in 2.24s
```
**Restore:** inverse edit, `if False and why == "no-branch-at-base":` -> `if why == "no-branch-at-base":`.
**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.62s
```

---

## E3 - local commits (`_prepare_cloud_launch_folder`, step 5f)

**Guarded element:** `launcher.py:3226` `if ahead is None or ahead.returncode != 0:` -> `off-base` / `local-commits`.
**Axis:** a local branch holding commits the target lacks refuses, so the repair is only ever a fast-forward and never discards a commit.
**Node:** `test_row6_local_commits_on_the_folders_branch_refuse_and_the_branch_is_not_reset`.

**Neutralization:** `if ahead is None or ahead.returncode != 0:` -> `if False and (ahead is None or ahead.returncode != 0):`.

**Raw red** (the launch ran, after `checkout -B` reset the folder's branch off its local commit):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_row6_local_commits_on_the_folders_branch_refuse_and_the_branch_is_not_reset _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-7/test_row6_local_commits_on_the0')

    def test_row6_local_commits_on_the_folders_branch_refuse_and_the_branch_is_not_reset(tmp_path):
        # axis: a local branch holding commits the target lacks refuses, so the repair is only ever a fast-forward — see bite-proof record i2353_cloud_launch_folder
        repo, folder = _world(tmp_path)
        mine = _commit(folder, "local-work.txt")
        primary_before = _snap(repo)
        folder_before = _snap(folder)
        calls = []
        result = _launch(repo, tmp_path, _spy(calls))
>       _refused(repo, result, OFF_BASE, "local-commits", folder, calls, primary_before)

/home/user/superheroes/.wt-2353-wo1/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:245: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/superheroes/.wt-2353-wo1/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:131: in _refused
    _assert_refused_cloud_lane(repo, result, reason, "cloud-base")
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-7/test_row6_local_commits_on_the0/repo'
result = {'ok': True, 'reason': None, 'launchId': 'launch-0ea84448acc69315', 'place': 'cloud', ...}
reason = 'launch-cloud-checkout-off-base', stage = 'cloud-base'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
>       assert result["ok"] is False
E       assert True is False

/home/user/superheroes/.wt-2353-wo1/plugins/superheroes/lib/tests/test_launcher_cloud.py:635: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py::test_row6_local_commits_on_the_folders_branch_refuse_and_the_branch_is_not_reset
1 failed in 2.04s
```
**Restore:** inverse edit, `if False and (ahead is None or ahead.returncode != 0):` -> `if ahead is None or ahead.returncode != 0:`.
**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.74s
```

---

## E4 - `--no-overwrite-ignore` (`_prepare_cloud_launch_folder`, step 5g)

**Guarded element:** `launcher.py:3233` the `--no-overwrite-ignore` argument of `git checkout --quiet ... -B <branch> <target>`.
**Axis:** an ignored local file that the target tracks refuses the switch (`off-base` / `checkout-failed`) instead of being overwritten; the clean-tree check cannot see ignored files.
**Node:** `test_row7_an_ignored_file_the_target_tracks_refuses_the_switch_and_keeps_its_bytes`.

**Neutralization:** `folder, "checkout", "--quiet", "--no-overwrite-ignore", "-B", branch, target,` -> `folder, "checkout", "--quiet", "-B", branch, target,`.

**Raw red** (the launch ran; the ignored file was overwritten by the switch):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_row7_an_ignored_file_the_target_tracks_refuses_the_switch_and_keeps_its_bytes _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-9/test_row7_an_ignored_file_the_0')

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

/home/user/superheroes/.wt-2353-wo1/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:271: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/superheroes/.wt-2353-wo1/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:131: in _refused
    _assert_refused_cloud_lane(repo, result, reason, "cloud-base")
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-9/test_row7_an_ignored_file_the_0/repo'
result = {'ok': True, 'reason': None, 'launchId': 'launch-7e37532a94f2d660', 'place': 'cloud', ...}
reason = 'launch-cloud-checkout-off-base', stage = 'cloud-base'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
>       assert result["ok"] is False
E       assert True is False

/home/user/superheroes/.wt-2353-wo1/plugins/superheroes/lib/tests/test_launcher_cloud.py:635: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py::test_row7_an_ignored_file_the_target_tracks_refuses_the_switch_and_keeps_its_bytes
1 failed in 1.94s
```
**Restore:** inverse edit, `folder, "checkout", "--quiet", "-B", branch, target,` -> `folder, "checkout", "--quiet", "--no-overwrite-ignore", "-B", branch, target,`.
**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.72s
```

---

## E5 - the symlink check (`_validate_cloud_launch_folder`)

**Guarded element:** `launcher.py:3017` `if os.path.islink(folder):` -> `not-launcher-owned`.
**Axis:** a folder path that is a symlink is not the launcher's own folder, whatever it points at.
**Node:** `test_row9_a_symlink_to_a_genuine_launcher_clone_is_not_the_folder`.

Disclosure on the node choice: the order's row 9 symlink case (a symlink to the primary checkout,
`test_row9_a_symlink_to_the_primary_checkout_is_not_the_folder`) is also refused by the common-dir check
(a symlink to the primary shares its common dir) and by the missing marker, so neutralizing the symlink check
alone leaves that node green; it cannot discriminate E5. The node above points the symlink at a genuine launcher
clone that passes every other check, so only the symlink check refuses it. Both nodes ship; the genuine-clone
node is the one that bites E5. The primary-symlink node was not run red.

**Neutralization:** `if os.path.islink(folder):` -> `if False and os.path.islink(folder):`.

**Raw red** (the launch ran with the symlink as the command's folder):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_row9_a_symlink_to_a_genuine_launcher_clone_is_not_the_folder _______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-11/test_row9_a_symlink_to_a_genui0')

    def test_row9_a_symlink_to_a_genuine_launcher_clone_is_not_the_folder(tmp_path):
        # axis: a folder path that is a symlink is not the launcher's own folder even when what it points at passes every other check — see bite-proof record i2353_cloud_launch_folder
        repo, folder = _world(tmp_path)
        real = folder + "-real"
        os.rename(folder, real)
        os.symlink(real, folder)
        primary_before = _snap(repo)
        real_before = _snap(real)
        calls = []
        result = _launch(repo, tmp_path, _spy(calls))
>       _refused(repo, result, UNREADABLE, "not-launcher-owned", folder, calls, primary_before)

/home/user/superheroes/.wt-2353-wo1/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:331: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/superheroes/.wt-2353-wo1/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:131: in _refused
    _assert_refused_cloud_lane(repo, result, reason, "cloud-base")
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-11/test_row9_a_symlink_to_a_genui0/repo'
result = {'ok': True, 'reason': None, 'launchId': 'launch-533cdab64d6e99ec', 'place': 'cloud', ...}
reason = 'launch-cloud-checkout-unreadable', stage = 'cloud-base'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
>       assert result["ok"] is False
E       assert True is False

/home/user/superheroes/.wt-2353-wo1/plugins/superheroes/lib/tests/test_launcher_cloud.py:635: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py::test_row9_a_symlink_to_a_genuine_launcher_clone_is_not_the_folder
1 failed in 2.08s
```
**Restore:** inverse edit, `if False and os.path.islink(folder):` -> `if os.path.islink(folder):`.
**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.65s
```

---

## E6 - common-dir independence (`_validate_cloud_launch_folder`)

**Guarded element:** `launcher.py:3030` `if common != os.path.realpath(os.path.join(folder, ".git")) or common == primary_common:` -> `not-launcher-owned`.
**Axis:** the folder keeps its own git dir and object store, independent of the primary's; a linked worktree (or an alias) shares the primary's and is refused even with a valid marker and an equal origin.
**Node:** `test_row9_a_linked_worktree_with_a_valid_marker_is_not_the_folder`.

The check is one condition (own-git-dir equality and difference from the primary's common dir); a linked
worktree's `.git` is a file, so its common dir is the primary's and the condition refuses it. The
neutralization replaces the whole condition, since neutralizing only the "differs from the primary" half
would leave the own-git-dir half refusing the worktree and the proof vacuous.

**Neutralization:** `if common != os.path.realpath(os.path.join(folder, ".git")) or common == primary_common:` -> `if False:`.

**Raw red** (the launch ran with the primary's linked worktree as the folder):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_row9_a_linked_worktree_with_a_valid_marker_is_not_the_folder _______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-13/test_row9_a_linked_worktree_wi0')

    def test_row9_a_linked_worktree_with_a_valid_marker_is_not_the_folder(tmp_path):
        # axis: a folder that shares the primary's git dir is not independent of it, whatever marker and origin it carries — see bite-proof record i2353_cloud_launch_folder
        repo = _cloud_repo(tmp_path)
        folder = L.cloud_launch_folder_path(repo)
        os.makedirs(os.path.dirname(folder))
        _git(repo, "worktree", "add", "--detach", folder)
        gitdir = _git(folder, "rev-parse", "--absolute-git-dir").strip()
        with open(os.path.join(gitdir, MARKER), "w") as fh:
            json.dump({"schema": 1, "repoId": ll.repo_identity(repo)}, fh)
        assert _git(folder, "remote", "get-url", "origin") == _git(repo, "remote", "get-url", "origin")
        primary_before = _snap(repo)
        folder_before = _snap(folder)
        calls = []
        result = _launch(repo, tmp_path, _spy(calls))
>       _refused(repo, result, UNREADABLE, "not-launcher-owned", folder, calls, primary_before)

/home/user/superheroes/.wt-2353-wo1/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:350: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/superheroes/.wt-2353-wo1/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:131: in _refused
    _assert_refused_cloud_lane(repo, result, reason, "cloud-base")
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-13/test_row9_a_linked_worktree_wi0/repo'
result = {'ok': True, 'reason': None, 'launchId': 'launch-c3c7e432fab7a7d1', 'place': 'cloud', ...}
reason = 'launch-cloud-checkout-unreadable', stage = 'cloud-base'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
>       assert result["ok"] is False
E       assert True is False

/home/user/superheroes/.wt-2353-wo1/plugins/superheroes/lib/tests/test_launcher_cloud.py:635: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py::test_row9_a_linked_worktree_with_a_valid_marker_is_not_the_folder
1 failed in 2.16s
```
**Restore:** inverse edit, `if False:` -> `if common != os.path.realpath(os.path.join(folder, ".git")) or common == primary_common:`.
**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.78s
```

---

## E7 - missing-folder refusal and never-create (`_prepare_cloud_launch_folder`, step 5b)

**Guarded element:** `launcher.py:3181` `if found == "missing": return missing()` -> `launch-cloud-folder-missing`.
**Axis:** a folder the setup verb has not made refuses, and a launch never creates it (an untrusted new folder hangs the CLI's trust prompt).
**Node:** `test_row8_a_missing_folder_refuses_and_is_never_created`.

**Neutralization:** `return missing()` (under `if found == "missing":`) -> the two lines `ensure_cloud_launch_folder(repo_root, env)` and `found = None` (the launch makes the folder and goes on).

**Raw red** (the launch made the folder and ran the command):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_row8_a_missing_folder_refuses_and_is_never_created ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-15/test_row8_a_missing_folder_ref0')

    def test_row8_a_missing_folder_refuses_and_is_never_created(tmp_path):
        # axis: a folder the setup verb has not made refuses, and a launch never creates it — see bite-proof record i2353_cloud_launch_folder
        repo = _cloud_repo(tmp_path)
        folder = L.cloud_launch_folder_path(repo)
        assert folder is not None and not os.path.lexists(folder)
        primary_before = _snap(repo)
        calls = []
        result = _launch(repo, tmp_path, _spy(calls))
>       _assert_refused_cloud_lane(repo, result, "launch-cloud-folder-missing", "cloud-base")

/home/user/superheroes/.wt-2353-wo1/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:288: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-15/test_row8_a_missing_folder_ref0/repo'
result = {'ok': True, 'reason': None, 'launchId': 'launch-7fbab44018f8ac89', 'place': 'cloud', ...}
reason = 'launch-cloud-folder-missing', stage = 'cloud-base'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
>       assert result["ok"] is False
E       assert True is False

/home/user/superheroes/.wt-2353-wo1/plugins/superheroes/lib/tests/test_launcher_cloud.py:635: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py::test_row8_a_missing_folder_refuses_and_is_never_created
1 failed in 1.81s
```
**Restore:** inverse edit, the two lines back to `return missing()`.
**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.53s
```

---

## E8 - lock busy (`_cloud_launch_folder_lock`)

**Guarded element:** `launcher.py:3280` `yield "launch-cloud-folder-busy", {"launchFolder": folder}` / `return` on the wait running out.
**Axis:** a folder another launch holds refuses after the wait and the command does not run, so two launches never move one folder at once.
**Node:** `test_row11_a_folder_another_launch_holds_refuses_busy_after_the_wait`.

**Neutralization:** the two lines `yield "launch-cloud-folder-busy", {"launchFolder": folder}` and `return` -> `break` (the launch goes on without the lock once the wait is over).

**Raw red** (the launch ran while the test held the lock):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_row11_a_folder_another_launch_holds_refuses_busy_after_the_wait _____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-17/test_row11_a_folder_another_la0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fc1ee302990>

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

/home/user/superheroes/.wt-2353-wo1/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:387: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-17/test_row11_a_folder_another_la0/repo'
result = {'ok': True, 'reason': None, 'launchId': 'launch-c7904c99b73ea81d', 'place': 'cloud', ...}
reason = 'launch-cloud-folder-busy', stage = 'cloud-base'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
>       assert result["ok"] is False
E       assert True is False

/home/user/superheroes/.wt-2353-wo1/plugins/superheroes/lib/tests/test_launcher_cloud.py:635: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py::test_row11_a_folder_another_launch_holds_refuses_busy_after_the_wait
1 failed in 2.44s
```
**Restore:** inverse edit, `break` -> the `yield "launch-cloud-folder-busy", {"launchFolder": folder}` and `return` lines.
**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 2.19s
```

Pinned condition (E8 and row 12): the lock wait is monkeypatched to 0.3 seconds in the test and the
holder is the test's own file descriptor in the same process. Production waits up to 600 seconds and the
holder is another launcher process; the pin makes that wait length and cross-process contention
unobservable, and the flock conflict between two descriptors of one process is what stands in for it.

---

## E9 - spawn `cwd` is the folder (`_run_cloud_spawn`)

**Guarded element:** `launcher.py:1922` `spawned = spawn(argv, cwd, log_path, child_env, timeout)`.
**Axis:** the cloud command runs in the launcher's own folder, never the primary checkout.
**Node:** `test_row1_a_base_that_is_an_unmerged_branch_tip_launches_from_the_folder_on_that_branch`.

**Neutralization:** `spawned = spawn(argv, cwd, log_path, child_env, timeout)` -> `spawned = spawn(argv, repo_root, log_path, child_env, timeout)`.

**Raw red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_row1_a_base_that_is_an_unmerged_branch_tip_launches_from_the_folder_on_that_branch _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-19/test_row1_a_base_that_is_an_un0')

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
E       AssertionError: assert '/tmp/claude-...s_an_un0/repo' == '/tmp/claude-...-c76cccec3c3b'
E         
E         Skipping 61 identical leading characters in diff, use -v to show
E         - is_an_un0/wt-root/repo/cloud-launch-c76cccec3c3b
E         + is_an_un0/repo

/home/user/superheroes/.wt-2353-wo1/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:154: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py::test_row1_a_base_that_is_an_unmerged_branch_tip_launches_from_the_folder_on_that_branch
1 failed in 2.03s
```
**Restore:** inverse edit, `repo_root` -> `cwd` in that call.
**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 2.01s
```

---

## E10 - the folder path comes from the common dir (`cloud_launch_folder_path`)

**Guarded element:** `launcher.py:2995` the `tag = ...` line, derived from `basename(dirname(common dir))`.
**Axis:** every checkout of one repository (the primary, a linked worktree, a symlink alias) names one folder; the path is never derived from `repo_root`'s own name.
**Node:** `test_row10_every_checkout_of_one_repository_names_the_same_folder`.

**Neutralization:** `tag = _WORKTREE_TAG_UNSAFE.sub("-", os.path.basename(os.path.dirname(common))).strip("-") or "repo"` -> `tag = _repo_tag(repo_root)`.

**Raw red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_row10_every_checkout_of_one_repository_names_the_same_folder _______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-21/test_row10_every_checkout_of_o0')

    def test_row10_every_checkout_of_one_repository_names_the_same_folder(tmp_path):
        # axis: the folder path comes from the git common dir and the repository identity, not from the checkout's own name — see bite-proof record i2353_cloud_launch_folder
        repo = _cloud_repo(tmp_path)
        linked = str(tmp_path / "linked")
        _git(repo, "worktree", "add", "--detach", linked)
        alias = str(tmp_path / "alias")
        os.symlink(repo, alias)
        paths = [L.cloud_launch_folder_path(path) for path in (repo, linked, alias)]
        assert paths[0] is not None
>       assert paths[0] == paths[1] == paths[2]
E       AssertionError: assert '/tmp/claude-...-c9d541807c24' == '/tmp/claude-...-c9d541807c24'
E         
E         Skipping 69 identical leading characters in diff, use -v to show
E         - 0/wt-root/linked/cloud-launch-c9d541807c24
E         ?           ^^^^ ^
E         + 0/wt-root/repo/cloud-launch-c9d541807c24
E         ?           ^ ^^

/home/user/superheroes/.wt-2353-wo1/plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py:366: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud_launch_folder.py::test_row10_every_checkout_of_one_repository_names_the_same_folder
1 failed in 1.62s
```
**Restore:** inverse edit, `tag = _repo_tag(repo_root)` -> the common-dir line above.
**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.64s
```

---

## Restore receipt (restored lines read back from `launcher.py` after the last restore)

```
1922:        spawned = spawn(argv, cwd, log_path, child_env, timeout)
2995:    tag = _WORKTREE_TAG_UNSAFE.sub("-", os.path.basename(os.path.dirname(common))).strip("-") or "repo"
3017:    if os.path.islink(folder):
3030:    if common != os.path.realpath(os.path.join(folder, ".git")) or common == primary_common:
3181:    if found == "missing":
3182:        return missing()
3192:    if (status.stdout or "").strip():
3198:    if why == "no-branch-at-base":
3226:        if ahead is None or ahead.returncode != 0:
3233:        folder, "checkout", "--quiet", "--no-overwrite-ignore", "-B", branch, target,
3280:                    yield "launch-cloud-folder-busy", {"launchFolder": folder}
3281:                    return
```

## Not proven by this record

- The tests outside the declared set (`test_row13_*`, `test_row14_*`, `test_row2_*`, `test_row5_*`, `test_row12_*`,
  `test_the_branch_choice_prefers_the_default_branch_then_the_lexically_first`, and the symlink-to-primary node
  of row 9) were not run red; the declared set E1 to E10 is what the order asked proven.
- E2's red is a wrong-token red (above), not the expected `no-branch-at-base` token.
