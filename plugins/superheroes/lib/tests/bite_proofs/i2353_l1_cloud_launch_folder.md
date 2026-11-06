# #2353 layer 1 bite-proof record: the launcher's cloud launch folder (make it, validate it, trust it once)

Detector file: `plugins/superheroes/lib/tests/test_cloud_launch_folder_setup.py`, over `ensure_cloud_launch_folder`,
`_validate_cloud_launch_folder` and `cloud_launch_folder_path` in `plugins/superheroes/lib/launcher.py`. Every
neutralization was one targeted `Edit`, restored by the inverse `Edit`; no `git checkout`, `restore` or `stash` was used.
Each red is the single test node alone. The `warning: The UV_NATIVE_TLS ...` line is the runner's, not the test's.
Nothing below is redacted: the captures hold no secret, token or private URL (the paths are pytest temp directories).

Command for every red and green: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-l1 -m pytest '<node id>' -q -p no:cacheprovider`
(node ids are under `plugins/superheroes/lib/tests/test_cloud_launch_folder_setup.py::`).

Declared guarded-element set: B1 path from the common dir; B2 the islink check; B3 the common-dir independence check;
B4 the marker check; B5 detach-and-drop (Fix 1); B6 remove-what-this-call-created (Fix 2). One entry each below.

Disclosures up front:

- **B2, first green run failed, and why.** My restore `Edit` for B2 put the `islink` lines back but the edit tool trimmed
  the trailing space of `top = ` so the first restore attempt did not match; I did not see that before running the green,
  and the green failed (output under B2). I then found the file still neutralized (and `top =_git_stdout(` malformed),
  restored it by a corrected inverse edit, and re-ran the green, which passed. The first green is a failed restore, not a
  failure of the detector.
- **B3 red ran twice.** The first red ran while B2 was still (wrongly) neutralized; B3's node involves no symlink, so B2
  could not have caused it, but I restored both and re-ran B3's red clean. Both are quoted.
- **B4: the order's neutralization did not bite row 9 (marker removed).** Making the marker-present condition `False`
  leaves `test_validator_refuses_a_clone_whose_marker_was_removed` green, because the `open(marker)` that follows raises
  `OSError` and refuses the same way. That is *Unprovable as placed* for the *absent marker* sub-case: the distinction
  (absent marker) is also decided by the `except (OSError, ValueError)` below, so no test can tell the condition from the
  handler. What the condition alone decides is a marker that is a **symlink** to a valid marker (`open` follows it, so the
  handler would accept it). I added the test `test_validator_refuses_a_clone_whose_marker_is_a_symlink_to_a_valid_marker`
  (not in the order's row list) and used it as B4's detector. Protection of the plain *absent marker* case rests on the
  handler, which is not separately proven here.

## B1. the path comes from the common dir and the repository identity

- Guarded element: `cloud_launch_folder_path`, the `tag = ...` line (`launcher.py:3017`). Axis: every checkout of one
  repository (primary, linked worktree, symlink alias) names one folder.
- Neutralization: `os.path.basename(os.path.dirname(common))` became `os.path.basename(os.path.abspath(repo_root))`.
- Node: `test_one_path_for_the_primary_a_linked_worktree_and_a_symlink_alias`.
- Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_one_path_for_the_primary_a_linked_worktree_and_a_symlink_alias ______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-27/test_one_path_for_the_primary_0')

    def test_one_path_for_the_primary_a_linked_worktree_and_a_symlink_alias(tmp_path):
        primary = _cloud_repo(tmp_path)
        linked = str(tmp_path / "linked")
        _git(primary, "worktree", "add", "--detach", linked)
        alias = str(tmp_path / "alias")
        os.symlink(primary, alias)
        before = _snapshot(primary)
    
        # axis: the path comes from the common dir and the repository identity, not from the checkout's own basename
        here = L.cloud_launch_folder_path(primary)
        assert here is not None
>       assert L.cloud_launch_folder_path(linked) == here
E       AssertionError: assert '/tmp/claude-...-12fc6edf0a67' == '/tmp/claude-...-12fc6edf0a67'
E         
E         Skipping 69 identical leading characters in diff, use -v to show
E         - 0/wt-root/repo/cloud-launch-12fc6edf0a67
E         ?           ^ ^^
E         + 0/wt-root/linked/cloud-launch-12fc6edf0a67
E         ?           ^^^^ ^

/home/user/superheroes/.wt-2353-l1/plugins/superheroes/lib/tests/test_cloud_launch_folder_setup.py:72: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_launch_folder_setup.py::test_one_path_for_the_primary_a_linked_worktree_and_a_symlink_alias
1 failed in 13.61s
```

- Restore: the inverse edit. Restored line (read back by search): `launcher.py:3017`
  `    tag = _WORKTREE_TAG_UNSAFE.sub("-", os.path.basename(os.path.dirname(common))).strip("-") or "repo"`
  (the only other `tag = _WORKTREE_TAG_UNSAFE` line, `launcher.py:509`, is pre-existing and was never touched).
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 2.22s
```

## B2. a symlink at the folder path is never the launcher's folder

- Guarded element: `_validate_cloud_launch_folder`, the `if os.path.islink(folder): return "not-launcher-owned"` refusal
  (`launcher.py:3039`). Axis: a symlink at the path is not the launcher's own folder, whatever it points at.
- Neutralization: the two lines `if os.path.islink(folder):` / `return "not-launcher-owned"` deleted.
- Node: `test_validator_refuses_a_symlink_to_a_genuine_launcher_clone`.
- Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_validator_refuses_a_symlink_to_a_genuine_launcher_clone _________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-29/test_validator_refuses_a_symli0')

    def test_validator_refuses_a_symlink_to_a_genuine_launcher_clone(tmp_path):
        primary, folder = _made(tmp_path)
        aside = folder + "-aside"
        os.rename(folder, aside)
        os.symlink(aside, folder)
        before = _snapshot(primary)
    
        # axis: a symlink at the path is not the launcher's own folder, whatever it points at
>       assert L._validate_cloud_launch_folder(primary, folder, None) == "not-launcher-owned"
E       AssertionError: assert None == 'not-launcher-owned'
E        +  where None = <function _validate_cloud_launch_folder at 0x7f1efcaf2f20>('/tmp/claude-0/pytest-of-root/pytest-29/test_validator_refuses_a_symli0/repo', '/tmp/claude-0/pytest-of-root/pytest-29/test_validator_refuses_a_symli0/wt-root/repo/cloud-launch-07c90e71d8d7', None)
E        +    where <function _validate_cloud_launch_folder at 0x7f1efcaf2f20> = L._validate_cloud_launch_folder

/home/user/superheroes/.wt-2353-l1/plugins/superheroes/lib/tests/test_cloud_launch_folder_setup.py:156: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_launch_folder_setup.py::test_validator_refuses_a_symlink_to_a_genuine_launcher_clone
1 failed in 2.04s
```

- First restore attempt (failed, see the disclosure): the green run after it **failed**, because the restore edit did
  not apply. That output, word for word:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_validator_refuses_a_symlink_to_a_genuine_launcher_clone _________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-30/test_validator_refuses_a_symli0')

    def test_validator_refuses_a_symlink_to_a_genuine_launcher_clone(tmp_path):
        primary, folder = _made(tmp_path)
        aside = folder + "-aside"
        os.rename(folder, aside)
        os.symlink(aside, folder)
        before = _snapshot(primary)
    
        # axis: a symlink at the path is not the launcher's own folder, whatever it points at
>       assert L._validate_cloud_launch_folder(primary, folder, None) == "not-launcher-owned"
E       AssertionError: assert None == 'not-launcher-owned'
E        +  where None = <function _validate_cloud_launch_folder at 0x7fcca54b2f20>('/tmp/claude-0/pytest-of-root/pytest-30/test_validator_refuses_a_symli0/repo', '/tmp/claude-0/pytest-of-root/pytest-30/test_validator_refuses_a_symli0/wt-root/repo/cloud-launch-0370955be4d2', None)
E        +    where <function _validate_cloud_launch_folder at 0x7fcca54b2f20> = L._validate_cloud_launch_folder

/home/user/superheroes/.wt-2353-l1/plugins/superheroes/lib/tests/test_cloud_launch_folder_setup.py:156: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_launch_folder_setup.py::test_validator_refuses_a_symlink_to_a_genuine_launcher_clone
1 failed in 1.82s
```

- Restore (corrected inverse edit, which also fixed `top =_git_stdout(` back to `top = _git_stdout(`). Restored lines,
  read back from `launcher.py:3038-3044`:

```
    # axis: a folder path that is a symlink is not the launcher's own folder, whatever it points at — see bite-proof record i2353_l1_cloud_launch_folder
    if os.path.islink(folder):
        return "not-launcher-owned"
    identity = ll.repo_identity(repo_root)
    if identity is None:
        return "not-launcher-owned"
    top = _git_stdout(folder, "rev-parse", "--show-toplevel", env=env)
```

- Raw green (after the corrected restore):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.75s
```

## B3. the folder keeps its own object store and git dir

- Guarded element: `_validate_cloud_launch_folder`, the `if common != os.path.realpath(os.path.join(folder, ".git")) or
  common == primary_common:` refusal (`launcher.py:3052`). Axis: a linked worktree or alias shares the primary's common
  dir and is not the launcher's folder, even with a valid marker.
- Neutralization: that condition became `if False:`.
- Node: `test_validator_refuses_a_linked_worktree_even_with_a_valid_marker`.
- Raw red (clean run, B2 restored):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_validator_refuses_a_linked_worktree_even_with_a_valid_marker _______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-33/test_validator_refuses_a_linke0')

    def test_validator_refuses_a_linked_worktree_even_with_a_valid_marker(tmp_path):
        primary = _cloud_repo(tmp_path)
        path = L.cloud_launch_folder_path(primary)
        os.makedirs(os.path.dirname(path))
        _git(primary, "worktree", "add", "--detach", path)
        with open(_marker(path), "w", encoding="utf-8") as fh:
            json.dump({"schema": 1, "repoId": ll.repo_identity(primary)}, fh)
        assert os.path.isfile(_marker(path))
        before = _snapshot(primary)
    
        # axis: the folder keeps its own object store and git dir, independent of the primary's
>       assert L._validate_cloud_launch_folder(primary, path, None) == "not-launcher-owned"
E       AssertionError: assert None == 'not-launcher-owned'
E        +  where None = <function _validate_cloud_launch_folder at 0x7f63567bef20>('/tmp/claude-0/pytest-of-root/pytest-33/test_validator_refuses_a_linke0/repo', '/tmp/claude-0/pytest-of-root/pytest-33/test_validator_refuses_a_linke0/wt-root/repo/cloud-launch-b840f217f0c3', None)
E        +    where <function _validate_cloud_launch_folder at 0x7f63567bef20> = L._validate_cloud_launch_folder

/home/user/superheroes/.wt-2353-l1/plugins/superheroes/lib/tests/test_cloud_launch_folder_setup.py:182: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_launch_folder_setup.py::test_validator_refuses_a_linked_worktree_even_with_a_valid_marker
1 failed in 2.04s
```

  (The earlier red, run while B2 was still neutralized, failed on the same assertion line 182 with
  `assert None == 'not-launcher-owned'`, `1 failed in 1.65s`.)
- Restore: the inverse edit. Restored lines (`launcher.py:3051-3053`):

```
    # axis: the folder keeps its own object store and git dir, independent of the primary's (a linked worktree or an alias shares it) — see bite-proof record i2353_l1_cloud_launch_folder
    if common != os.path.realpath(os.path.join(folder, ".git")) or common == primary_common:
        return "not-launcher-owned"
```

- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.78s
```

## B4. only a folder carrying the launcher's own marker file is its own

- Guarded element: `_validate_cloud_launch_folder`, the `if marker is None or os.path.islink(marker) or not
  os.path.isfile(marker):` refusal (`launcher.py:3056`). Axis: a folder without the launcher's marker file, or with a
  marker that is a link, is not the launcher's own.
- Neutralization: that condition became `if False:`.
- As the order named it (row 9, marker removed), `test_validator_refuses_a_clone_whose_marker_was_removed` stayed
  **green** under this neutralization (see the up-front disclosure: the `open` handler refuses an absent marker too).
  Raw output of that non-red run:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.72s
```

- Detector used instead: `test_validator_refuses_a_clone_whose_marker_is_a_symlink_to_a_valid_marker` (added).
- Raw red (same neutralization, still in the tree):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_validator_refuses_a_clone_whose_marker_is_a_symlink_to_a_valid_marker __

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-36/test_validator_refuses_a_clone0')

    def test_validator_refuses_a_clone_whose_marker_is_a_symlink_to_a_valid_marker(tmp_path):
        primary, folder = _made(tmp_path)
        marker = _marker(folder)
        real = str(tmp_path / "real-marker")
        os.rename(marker, real)
        os.symlink(real, marker)
        assert json.load(open(marker, encoding="utf-8"))["repoId"] == ll.repo_identity(primary)
        before = _snapshot(primary)
    
        # axis: only a folder carrying the launcher's own marker file (not a link to one) is its own
>       assert L._validate_cloud_launch_folder(primary, folder, None) == "not-launcher-owned"
E       AssertionError: assert None == 'not-launcher-owned'
E        +  where None = <function _validate_cloud_launch_folder at 0x7f1e8c1d6f20>('/tmp/claude-0/pytest-of-root/pytest-36/test_validator_refuses_a_clone0/repo', '/tmp/claude-0/pytest-of-root/pytest-36/test_validator_refuses_a_clone0/wt-root/repo/cloud-launch-427c51b1bd2e', None)
E        +    where <function _validate_cloud_launch_folder at 0x7f1e8c1d6f20> = L._validate_cloud_launch_folder

/home/user/superheroes/.wt-2353-l1/plugins/superheroes/lib/tests/test_cloud_launch_folder_setup.py:207: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_launch_folder_setup.py::test_validator_refuses_a_clone_whose_marker_is_a_symlink_to_a_valid_marker
1 failed in 1.76s
```

- Restore: the inverse edit. Restored lines (`launcher.py:3055-3057`):

```
    # axis: only a folder carrying the launcher's marker for this repository is its own — see bite-proof record i2353_l1_cloud_launch_folder
    if marker is None or os.path.islink(marker) or not os.path.isfile(marker):
        return "not-launcher-owned"
```

- Raw green (both the symlink node and the marker-removed node):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..                                                                       [100%]
2 passed in 1.89s
```

## B5. Fix 1: the new clone is detached with no local branch

- Guarded element: `ensure_cloud_launch_folder`, the detach-and-drop block (`launcher.py:3117-3134`, the `checkout
  --quiet --detach`, the `for-each-ref refs/heads/` read and the `branch --quiet -D` loop). Axis: a local clone copies the
  primary's checked-out branch, so without this a primary with unpushed commits leaves the folder on a branch ahead of its
  remote.
- Neutralization: the whole block was wrapped in `if False:` (re-indented one level).
- Node: `test_the_new_clone_is_detached_with_no_local_branch_though_the_primary_has_unpushed_commits`.
- Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_the_new_clone_is_detached_with_no_local_branch_though_the_primary_has_unpushed_commits _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-38/test_the_new_clone_is_detached0')

    def test_the_new_clone_is_detached_with_no_local_branch_though_the_primary_has_unpushed_commits(tmp_path):
        primary = _cloud_repo(tmp_path)
        _git(primary, *_IDENT, "commit", "-q", "--allow-empty", "-m", "unpushed")
        before = _snapshot(primary)
        assert before["head-ref"][0] == 0
    
        got = L.ensure_cloud_launch_folder(primary)
    
        assert got["ok"] is True and got["created"] is True, got
        folder = got["folder"]
        # axis: the clone copies the primary's checked-out branch, so it is detached and every local branch is dropped
>       assert _git(folder, "symbolic-ref", "-q", "HEAD", check=False).returncode != 0
E       AssertionError: assert 0 != 0
E        +  where 0 = CompletedProcess(args=['git', '-C', '/tmp/claude-0/pytest-of-root/pytest-38/test_the_new_clone_is_detached0/wt-root/repo/cloud-launch-033e3c41068d', 'symbolic-ref', '-q', 'HEAD'], returncode=0, stdout='refs/heads/master\n', stderr='').returncode
E        +    where CompletedProcess(args=['git', '-C', '/tmp/claude-0/pytest-of-root/pytest-38/test_the_new_clone_is_detached0/wt-root/repo/cloud-launch-033e3c41068d', 'symbolic-ref', '-q', 'HEAD'], returncode=0, stdout='refs/heads/master\n', stderr='') = _git('/tmp/claude-0/pytest-of-root/pytest-38/test_the_new_clone_is_detached0/wt-root/repo/cloud-launch-033e3c41068d', 'symbolic-ref', '-q', 'HEAD', check=False)

/home/user/superheroes/.wt-2353-l1/plugins/superheroes/lib/tests/test_cloud_launch_folder_setup.py:116: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_launch_folder_setup.py::test_the_new_clone_is_detached_with_no_local_branch_though_the_primary_has_unpushed_commits
1 failed in 1.62s
```

- Restore: the inverse edit (block un-indented, `if False:` removed). Restored lines (`launcher.py:3116-3135`):

```
    # axis: a local clone copies the primary's checked-out branch, so the new folder is detached and every local branch is dropped; otherwise a primary with unpushed commits would make the first launch's repair refuse local-commits — see bite-proof record i2353_l1_cloud_launch_folder
    detached = _git_scrubbed(
        path, "checkout", "--quiet", "--detach", env=env, timeout=_WORKTREE_GIT_TIMEOUT,
    )
    if detached is None or detached.returncode != 0:
        return _create_failed()
    heads = _git_scrubbed(
        path, "for-each-ref", "--format=%(refname)", "refs/heads/",
        env=env, timeout=_WORKTREE_GIT_TIMEOUT,
    )
    if heads is None or heads.returncode != 0:
        return _create_failed()
    for ref in (heads.stdout or "").split():
        short = ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref
        dropped = _git_scrubbed(
            path, "branch", "--quiet", "-D", short, env=env, timeout=_WORKTREE_GIT_TIMEOUT,
        )
        if dropped is None or dropped.returncode != 0:
            return _create_failed()
    marker = _cloud_folder_marker_path(path, env)
```

- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.81s
```

## B6. Fix 2: a failure after the clone began removes the path this call created

- Guarded element: `ensure_cloud_launch_folder._create_failed`, the `shutil.rmtree(path, ignore_errors=True)` under
  `if created_here:` (`launcher.py:3102`). Axis: a failed make leaves no half-made folder, which would otherwise refuse
  `launch-cloud-folder-not-launcher-owned` on every later attempt.
- Neutralization: `shutil.rmtree(path, ignore_errors=True)` became `pass`.
- Node: `test_a_failure_after_the_clone_began_leaves_no_folder_behind`.
- Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_a_failure_after_the_clone_began_leaves_no_folder_behind _________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-40/test_a_failure_after_the_clone0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fe43a249af0>

    def test_a_failure_after_the_clone_began_leaves_no_folder_behind(tmp_path, monkeypatch):
        primary = _cloud_repo(tmp_path)
        path = L.cloud_launch_folder_path(primary)
        before = _snapshot(primary)
        # The clone step succeeds; the step that writes the marker cannot find where to write it.
        monkeypatch.setattr(L, "_cloud_folder_marker_path", lambda folder, env: None)
    
        got = L.ensure_cloud_launch_folder(primary)
    
        # axis: a failure after the clone began removes the path this call created
        assert got["ok"] is False
        assert got["reason"] == "launch-cloud-folder-create-failed"
        assert got["folder"] == path
>       assert not os.path.lexists(path)
E       AssertionError: assert not True
E        +  where True = <function lexists at 0x7fe43b329a80>('/tmp/claude-0/pytest-of-root/pytest-40/test_a_failure_after_the_clone0/wt-root/repo/cloud-launch-e97fbd51ff69')
E        +    where <function lexists at 0x7fe43b329a80> = <module 'posixpath' (frozen)>.lexists
E        +      where <module 'posixpath' (frozen)> = os.path

/home/user/superheroes/.wt-2353-l1/plugins/superheroes/lib/tests/test_cloud_launch_folder_setup.py:243: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_launch_folder_setup.py::test_a_failure_after_the_clone_began_leaves_no_folder_behind
1 failed in 1.87s
```

- Restore: the inverse edit. Restored lines (`launcher.py:3100-3103`):

```
        # axis: a failure after the clone began removes the path this call created, and only that path, so no half-made folder is left to refuse launcher-owned on every later attempt — see bite-proof record i2353_l1_cloud_launch_folder
        if created_here:
            shutil.rmtree(path, ignore_errors=True)
        return _fail("launch-cloud-folder-create-failed", folder=path)
```

- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.74s
```

## After every restore

The whole detector file, all neutralizations restored: `15 passed in 5.75s`. The launcher's existing surface
(`test_launcher.py`, `test_launcher_cloud.py`, `test_launcher_cloud_checkout.py`, `-n auto`): `736 passed in 42.42s`.
