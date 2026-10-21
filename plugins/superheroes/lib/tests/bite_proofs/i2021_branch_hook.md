# #2021 — cloud readiness checks the dependency hook on the commit the build starts from: bite-proof record

Implementer-run record (work order `wo-a-2021`). Method: an exact-string mutation of each guarded element
with `count(old) == 1` asserted, the one detector run alone with `-k` (red), the inverse edit, the same
detector again (green), and the file's sha256 compared before and after. Test file:
`plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py`. The work is uncommitted in the worktree, so
`git diff --stat` cannot show a restore; the sha256 pair and the quoted restored lines are the receipt.
Raw captures drop only pytest's `UV_NATIVE_TLS` deprecation warning line.

Declared guarded-element set: G1-G20 (one entry each below; no equivalence classes, none unproven),
including G19, added by the F5 fix batch for the fixture-isolation regression test (the order named no bite-proof for it), and G20, added by the #2021 nounset amendment.

Disclosure: G4's, G5's and G6's detectors are the edge tests; the parity census
(`test_the_registration_rule_agrees_with_the_record_mode_snippet`) is a second detector for the same
legs. G12's detector removes `.git` from a configured project so a git read has nothing to answer.

## G1 — branch_gap script-missing return

- **guarded element:** `plugins/superheroes/lib/cloud_dependency_hook.py:142`
- **axis:** a commit without the script is not ready as script-missing
- **detector:** `test_cloud_branch_hook_2021.py::test_edge3_a_missing_script` (selected with `-k "test_edge3_a_missing_script"`)
- **neutralization (exact string, count(old)=1):**

```diff
-    if script is None:
-        return "script-missing"
+    if script is None and False:
+        return "script-missing"
```

- **raw red (rc 1):**

```
F
=================================== FAILURES ===================================
_________________________ test_edge3_a_missing_script __________________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-12/test_edge3_a_missing_script0')

    def test_edge3_a_missing_script(tmp_path):
        repo, commit = _edge_repo(tmp_path, script="absent")
>       assert _gap(repo, commit) == "script-missing"
E       AssertionError: assert 'script-differs' == 'script-missing'
E         
E         - script-missing
E         + script-differs

/home/user/wt-2021/plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py:398: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py::test_edge3_a_missing_script
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed, 62 deselected in 0.47s
```

- **restore:** the inverse edit (the neutralized text replaced by the original, count 1). Restore receipt: sha256 of `plugins/superheroes/lib/cloud_dependency_hook.py` before the neutralization `229b46e815487408d4e398b5590c656e2a50cb72bfeda06c932e9f4e4d62b0e2`, after the restore `229b46e815487408d4e398b5590c656e2a50cb72bfeda06c932e9f4e4d62b0e2` — identical; the restored lines quoted back:

```
    if script is None:
        return "script-missing"
```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed, 62 deselected in 0.59s
```

- **verdict:** RED->GREEN

## G2 — branch_gap script-differs (bytes) return

- **guarded element:** `plugins/superheroes/lib/cloud_dependency_hook.py:147`
- **axis:** script bytes that differ from configure's are refused
- **detector:** `test_cloud_branch_hook_2021.py::test_edge5_a_script_written_for_other_commands_differs` (selected with `-k "test_edge5_a_script_written_for_other_commands_differs"`)
- **neutralization (exact string, count(old)=1):**

```diff
-    if _blob(repo_root, script) != wanted:
-
+    if False and _blob(repo_root, script) != wanted:
+
```

- **raw red (rc 1):**

```
F
=================================== FAILURES ===================================
____________ test_edge5_a_script_written_for_other_commands_differs ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-14/test_edge5_a_script_written_fo0')

    def test_edge5_a_script_written_for_other_commands_differs(tmp_path):
        repo, commit = _edge_repo(tmp_path, script="other-commands")
>       assert _gap(repo, commit) == "script-differs"
E       AssertionError: assert None == 'script-differs'
E        +  where None = _gap('/tmp/claude-0/pytest-of-root/pytest-14/test_edge5_a_script_written_fo0/edge', '430aa0144c86c8d4c91a763bfb68a33b7fe351d6')

/home/user/wt-2021/plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py:409: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py::test_edge5_a_script_written_for_other_commands_differs
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed, 62 deselected in 1.53s
```

- **restore:** the inverse edit (the neutralized text replaced by the original, count 1). Restore receipt: sha256 of `plugins/superheroes/lib/cloud_dependency_hook.py` before the neutralization `229b46e815487408d4e398b5590c656e2a50cb72bfeda06c932e9f4e4d62b0e2`, after the restore `229b46e815487408d4e398b5590c656e2a50cb72bfeda06c932e9f4e4d62b0e2` — identical; the restored lines quoted back:

```
    if _blob(repo_root, script) != wanted:

```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed, 62 deselected in 0.60s
```

- **verdict:** RED->GREEN

## G3 — branch_gap script-differs (non-regular entry) return

- **guarded element:** `plugins/superheroes/lib/cloud_dependency_hook.py:144`
- **axis:** a symlink or tree at the script path is refused whatever its bytes
- **detector:** `test_cloud_branch_hook_2021.py::test_edge4_a_script_that_is_not_a_regular_file_differs` (selected with `-k "test_edge4_a_script_that_is_not_a_regular_file_differs and symlink"`)
- **neutralization (exact string, count(old)=1):**

```diff
-    if not _regular(script):
-
+    if False and not _regular(script):
+
```

- **raw red (rc 1):**

```
F
=================================== FAILURES ===================================
_______ test_edge4_a_script_that_is_not_a_regular_file_differs[symlink] ________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-38/test_edge4_a_script_that_is_no0')
kind = 'symlink'

    @pytest.mark.parametrize("kind", ["symlink", "directory"])
    def test_edge4_a_script_that_is_not_a_regular_file_differs(tmp_path, kind):
        repo, commit = _edge_repo(tmp_path, script=kind)
>       assert _gap(repo, commit) == "script-differs"
E       AssertionError: assert None == 'script-differs'
E        +  where None = _gap('/tmp/claude-0/pytest-of-root/pytest-38/test_edge4_a_script_that_is_no0/edge', '4bf240e879dde13253af6a27aa4b282a1d843103')

/home/user/wt-2021/plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py:407: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py::test_edge4_a_script_that_is_not_a_regular_file_differs[symlink]
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed, 62 deselected in 0.51s
```

- **restore:** the inverse edit (the neutralized text replaced by the original, count 1). Restore receipt: sha256 of `plugins/superheroes/lib/cloud_dependency_hook.py` before the neutralization `229b46e815487408d4e398b5590c656e2a50cb72bfeda06c932e9f4e4d62b0e2`, after the restore `229b46e815487408d4e398b5590c656e2a50cb72bfeda06c932e9f4e4d62b0e2` — identical; the restored lines quoted back:

```
    if not _regular(script):

```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed, 62 deselected in 0.50s
```

- **verdict:** RED->GREEN

## G4 — _REGISTERS_LINES disableAllHooks leg

- **guarded element:** `plugins/superheroes/lib/cloud_dependency_hook.py:71` (a line of `_REGISTERS_LINES`, the one home of the registration rule)
- **axis:** disableAllHooks true means the hook never runs
- **detector:** `test_cloud_branch_hook_2021.py::test_edge8_disable_all_hooks_refuses` (selected with `-k "test_edge8_disable_all_hooks_refuses"`)
- **neutralization (exact string, count(old)=1; this line is shared, so the same edit also changes the generated script's record mode):**

```diff
-isinstance(data, dict) and data.get('disableAllHooks') is not True",
+isinstance(data, dict)",
```

- **raw red (rc 1):**

```
F
=================================== FAILURES ===================================
_____________________ test_edge8_disable_all_hooks_refuses _____________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-83/test_edge8_disable_all_hooks_r0')

    def test_edge8_disable_all_hooks_refuses(tmp_path):
        settings = {"disableAllHooks": True, "hooks": {"SessionStart": [{"hooks": [_hook_entry()]}]}}
        repo, commit = _edge_repo(tmp_path, settings=settings)
>       assert _gap(repo, commit) == "settings-not-registered"
E       AssertionError: assert None == 'settings-not-registered'
E        +  where None = _gap('/tmp/claude-0/pytest-of-root/pytest-83/test_edge8_disable_all_hooks_r0/edge', 'e64c774e4d9e989fd2dbece3e7d30c6e5b6c54b3')

/home/user/wt-2021/plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py:492: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py::test_edge8_disable_all_hooks_refuses
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed, 71 deselected in 0.64s
```

- **restore:** the inverse edit (the neutralized text replaced by the original, count 1). Restore receipt: sha256 of `plugins/superheroes/lib/cloud_dependency_hook.py` before the neutralization `8c40b85ddf86ba6acde229a95055bb688188411f11529f7830b1b511069f8b42`, after the restore `8c40b85ddf86ba6acde229a95055bb688188411f11529f7830b1b511069f8b42` — identical; the restored line quoted back:

```
isinstance(data, dict) and data.get('disableAllHooks') is not True",
```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed, 71 deselected in 6.57s
```

- **verdict:** RED->GREEN

## G5 — _REGISTERS_LINES startup-matcher leg

- **guarded element:** `plugins/superheroes/lib/cloud_dependency_hook.py:75` (a line of `_REGISTERS_LINES`, the one home of the registration rule)
- **axis:** a group whose matcher does not cover startup never runs the hook at session start
- **detector:** `test_cloud_branch_hook_2021.py::test_edge9_a_group_that_does_not_cover_startup_refuses` (selected with `-k "test_edge9_a_group_that_does_not_cover_startup_refuses"`)
- **neutralization (exact string, count(old)=1; this line is shared, so the same edit also changes the generated script's record mode):**

```diff
-isinstance(e, dict) and starts(e) for h in
+isinstance(e, dict) for h in
```

- **raw red (rc 1):**

```
F
=================================== FAILURES ===================================
____________ test_edge9_a_group_that_does_not_cover_startup_refuses ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-85/test_edge9_a_group_that_does_n0')

    def test_edge9_a_group_that_does_not_cover_startup_refuses(tmp_path):
        settings = {"hooks": {"SessionStart": [{"matcher": "resume", "hooks": [_hook_entry()]}]}}
        repo, commit = _edge_repo(tmp_path, settings=settings)
>       assert _gap(repo, commit) == "settings-not-registered"
E       AssertionError: assert None == 'settings-not-registered'
E        +  where None = _gap('/tmp/claude-0/pytest-of-root/pytest-85/test_edge9_a_group_that_does_n0/edge', '67490fbf7165ec8548e85442ddc79118e9dc3b03')

/home/user/wt-2021/plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py:498: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py::test_edge9_a_group_that_does_not_cover_startup_refuses
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed, 71 deselected in 0.86s
```

- **restore:** the inverse edit (the neutralized text replaced by the original, count 1). Restore receipt: sha256 of `plugins/superheroes/lib/cloud_dependency_hook.py` before the neutralization `8c40b85ddf86ba6acde229a95055bb688188411f11529f7830b1b511069f8b42`, after the restore `8c40b85ddf86ba6acde229a95055bb688188411f11529f7830b1b511069f8b42` — identical; the restored line quoted back:

```
isinstance(e, dict) and starts(e) for h in
```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed, 71 deselected in 0.55s
```

- **verdict:** RED->GREEN

## G6 — _REGISTERS_LINES type/command leg

- **guarded element:** `plugins/superheroes/lib/cloud_dependency_hook.py:74` (a line of `_REGISTERS_LINES`, the one home of the registration rule)
- **axis:** only a command hook with our exact command is registered
- **detector:** `test_cloud_branch_hook_2021.py::test_edge10_a_hook_entry_of_another_type_or_command_refuses` (selected with `-k "test_edge10_a_hook_entry_of_another_type_or_command_refuses"`)
- **neutralization (exact string, count(old)=1; this line is shared, so the same edit also changes the generated script's record mode):**

```diff
-isinstance(h, dict) and h.get('type') == 'command' and h.get('command') == command
+isinstance(h, dict)
```

- **raw red (rc 1):**

```
F
=================================== FAILURES ===================================
_________ test_edge10_a_hook_entry_of_another_type_or_command_refuses __________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-87/test_edge10_a_hook_entry_of_an0')

    def test_edge10_a_hook_entry_of_another_type_or_command_refuses(tmp_path):
        for n, entry in enumerate([_hook_entry(type="prompt"), _hook_entry(command="bash other.sh")]):
            settings = {"hooks": {"SessionStart": [{"hooks": [entry]}]}}
            repo, commit = _edge_repo(tmp_path, settings=settings, name="e%d" % n)
>           assert _gap(repo, commit) == "settings-not-registered"
E           AssertionError: assert None == 'settings-not-registered'
E            +  where None = _gap('/tmp/claude-0/pytest-of-root/pytest-87/test_edge10_a_hook_entry_of_an0/e0', '854741776a354eb004f93b25cddd8cb197fd5c92')

/home/user/wt-2021/plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py:508: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py::test_edge10_a_hook_entry_of_another_type_or_command_refuses
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed, 71 deselected in 0.59s
```

- **restore:** the inverse edit (the neutralized text replaced by the original, count 1). Restore receipt: sha256 of `plugins/superheroes/lib/cloud_dependency_hook.py` before the neutralization `8c40b85ddf86ba6acde229a95055bb688188411f11529f7830b1b511069f8b42`, after the restore `8c40b85ddf86ba6acde229a95055bb688188411f11529f7830b1b511069f8b42` — identical; the restored line quoted back:

```
isinstance(h, dict) and h.get('type') == 'command' and h.get('command') == command
```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed, 71 deselected in 0.65s
```

- **verdict:** RED->GREEN

## G7 — branch_gap adopted-inputs-differ return

- **guarded element:** `plugins/superheroes/lib/cloud_dependency_hook.py:168`
- **axis:** an input changed by the adopted branch is not refreshed by the hook already started
- **detector:** `test_cloud_branch_hook_2021.py::test_edge11_adopted_inputs_that_differ` (selected with `-k "test_edge11_adopted_inputs_that_differ"`)
- **neutralization (exact string, count(old)=1):**

```diff
-                    and ours[2] == theirs[2]):
+                    and True):
```

- **raw red (rc 1):**

```
F
=================================== FAILURES ===================================
____________________ test_edge11_adopted_inputs_that_differ ____________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-24/test_edge11_adopted_inputs_tha0')

    def test_edge11_adopted_inputs_that_differ(tmp_path):
        repo, commit = _edge_repo(tmp_path)
        assert _gap(repo, commit, adopted=commit) is None
        # bytes differ
        (tmp_path / "edge" / "package-lock.json").write_text("v2\n")
        changed = _commit(repo, "changed")
>       assert _gap(repo, commit, adopted=changed) == "adopted-inputs-differ"
E       AssertionError: assert None == 'adopted-inputs-differ'
E        +  where None = _gap('/tmp/claude-0/pytest-of-root/pytest-24/test_edge11_adopted_inputs_tha0/edge', 'b58bf0ef3543849e16f383474f788c458169e1e7', adopted='6212a87a9f0b84fb4dc3f8ebd533cef377386dc3')

/home/user/wt-2021/plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py:454: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py::test_edge11_adopted_inputs_that_differ
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed, 62 deselected in 0.67s
```

- **restore:** the inverse edit (the neutralized text replaced by the original, count 1). Restore receipt: sha256 of `plugins/superheroes/lib/cloud_dependency_hook.py` before the neutralization `229b46e815487408d4e398b5590c656e2a50cb72bfeda06c932e9f4e4d62b0e2`, after the restore `229b46e815487408d4e398b5590c656e2a50cb72bfeda06c932e9f4e4d62b0e2` — identical; the restored lines quoted back:

```
                    and ours[2] == theirs[2]):
```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed, 62 deselected in 0.64s
```

- **verdict:** RED->GREEN

## G8 — branch_gap commit-unreadable return

- **guarded element:** `plugins/superheroes/lib/cloud_dependency_hook.py:136`
- **axis:** a commit that does not resolve is not ready
- **detector:** `test_cloud_branch_hook_2021.py::test_edge1_a_commit_that_does_not_resolve_is_unreadable` (selected with `-k "test_edge1_a_commit_that_does_not_resolve_is_unreadable"`)
- **neutralization (exact string, count(old)=1):**

```diff
-    if resolved is None:
-        return "commit-unreadable"
+    if False and resolved is None:
+        return "commit-unreadable"
```

- **raw red (rc 1):**

```
F
=================================== FAILURES ===================================
___________ test_edge1_a_commit_that_does_not_resolve_is_unreadable ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-26/test_edge1_a_commit_that_does_0')

    def test_edge1_a_commit_that_does_not_resolve_is_unreadable(tmp_path):
        repo, commit = _edge_repo(tmp_path)
>       assert _gap(repo, "0123456789abcdef0123456789abcdef01234567") == "commit-unreadable"
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2021/plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py:384: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt-2021/plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py:372: in _gap
    return hook.branch_gap(repo, commit, kw.pop("commands", COMMANDS), kw.pop("inputs", INPUTS),
/home/user/wt-2021/plugins/superheroes/lib/cloud_dependency_hook.py:138: in branch_gap
    script = _entry(repo_root, resolved, SCRIPT_REL)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2021/plugins/superheroes/lib/cloud_dependency_hook.py:108: in _entry
    out = _git_out(repo_root, "ls-tree", "-z", resolved, "--", path)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2021/plugins/superheroes/lib/cloud_dependency_hook.py:91: in _git_out
    done = subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True, env=env,
/root/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/lib/python3.12/subprocess.py:548: in run
    with Popen(*popenargs, **kwargs) as process:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^
/root/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/lib/python3.12/subprocess.py:1026: in __init__
    self._execute_child(args, executable, preexec_fn, close_fds,
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <Popen: returncode: None args: ['git', '-C', '/tmp/claude-0/pytest-of-root/p...>
args = ['git', '-C', '/tmp/claude-0/pytest-of-root/pytest-26/test_edge1_a_commit_that_does_0/edge', 'ls-tree', '-z', None, ...]
executable = b'git', preexec_fn = None, close_fds = True, pass_fds = ()
cwd = None
env = {'AI_AGENT': 'claude-code_2-1-306_agent', 'ALL_PROXY': 'http://srt.dG9vbHVfMDFOY2l4NzVTeG9EQmFLZmNVbVNwQVVw:1635ea9ecb...8c0ca28@localhost:3128', 'ANTHROPIC_BASE_URL': 'https://api.anthropic.com', 'AWS_ACCESS_KEY_ID': 'proxy-injected', ...}
startupinfo = None, creationflags = 0, shell = False, p2cread = -1
p2cwrite = -1, c2pread = 12, c2pwrite = 13, errread = 14, errwrite = 15
restore_signals = True, gid = None, gids = None, uid = None, umask = -1
start_new_session = False, process_group = -1

    def _execute_child(self, args, executable, preexec_fn, close_fds,
                       pass_fds, cwd, env,
                       startupinfo, creationflags, shell,
                       p2cread, p2cwrite,
                       c2pread, c2pwrite,
                       errread, errwrite,
                       restore_signals,
                       gid, gids, uid, umask,
                       start_new_session, process_group):
        """Execute program (POSIX version)"""
    
        if isinstance(args, (str, bytes)):
            args = [args]
        elif isinstance(args, os.PathLike):
            if shell:
                raise TypeError('path-like args is not allowed when '
                                'shell is true')
            args = [args]
        else:
            args = list(args)
    
        if shell:
            # On Android the default shell is at '/system/bin/sh'.
            unix_shell = ('/system/bin/sh' if
                      hasattr(sys, 'getandroidapilevel') else '/bin/sh')
            args = [unix_shell, "-c"] + args
            if executable:
                args[0] = executable
    
        if executable is None:
            executable = args[0]
    
        sys.audit("subprocess.Popen", executable, args, cwd, env)
    
        if (_USE_POSIX_SPAWN
                and os.path.dirname(executable)
                and preexec_fn is None
                and not close_fds
                and not pass_fds
                and cwd is None
                and (p2cread == -1 or p2cread > 2)
                and (c2pwrite == -1 or c2pwrite > 2)
                and (errwrite == -1 or errwrite > 2)
                and not start_new_session
                and process_group == -1
                and gid is None
                and gids is None
                and uid is None
                and umask < 0):
            self._posix_spawn(args, executable, env, restore_signals,
                              p2cread, p2cwrite,
                              c2pread, c2pwrite,
                              errread, errwrite)
            return
    
        orig_executable = executable
    
        # For transferring possible exec failure from child to parent.
        # Data format: "exception name:hex errno:description"
        # Pickle is not used; it is complex and involves memory allocation.
        errpipe_read, errpipe_write = os.pipe()
        # errpipe_write must not be in the standard io 0, 1, or 2 fd range.
        low_fds_to_close = []
        while errpipe_write < 3:
            low_fds_to_close.append(errpipe_write)
            errpipe_write = os.dup(errpipe_write)
        for low_fd in low_fds_to_close:
            os.close(low_fd)
        try:
            try:
                # We must avoid complex work that could involve
                # malloc or free in the child process to avoid
                # potential deadlocks, thus we do all this here.
                # and pass it to fork_exec()
    
                if env is not None:
                    env_list = []
                    for k, v in env.items():
                        k = os.fsencode(k)
                        if b'=' in k:
                            raise ValueError("illegal environment variable name")
                        env_list.append(k + b'=' + os.fsencode(v))
                else:
                    env_list = None  # Use execv instead of execve.
                executable = os.fsencode(executable)
                if os.path.dirname(executable):
                    executable_list = (executable,)
                else:
                    # This matches the behavior of os._execvpe().
                    executable_list = tuple(
                        os.path.join(os.fsencode(dir), executable)
                        for dir in os.get_exec_path(env))
                fds_to_keep = set(pass_fds)
                fds_to_keep.add(errpipe_write)
>               self.pid = _fork_exec(
                        args, executable_list,
                        close_fds, tuple(sorted(map(int, fds_to_keep))),
                        cwd, env_list,
                        p2cread, p2cwrite, c2pread, c2pwrite,
                        errread, errwrite,
                        errpipe_read, errpipe_write,
                        restore_signals, start_new_session,
                        process_group, gid, gids, uid, umask,
                        preexec_fn, _USE_VFORK)
E                       TypeError: expected str, bytes or os.PathLike object, not NoneType

/root/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/lib/python3.12/subprocess.py:1885: TypeError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py::test_edge1_a_commit_that_does_not_resolve_is_unreadable
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed, 62 deselected in 0.61s
```

- **restore:** the inverse edit (the neutralized text replaced by the original, count 1). Restore receipt: sha256 of `plugins/superheroes/lib/cloud_dependency_hook.py` before the neutralization `229b46e815487408d4e398b5590c656e2a50cb72bfeda06c932e9f4e4d62b0e2`, after the restore `229b46e815487408d4e398b5590c656e2a50cb72bfeda06c932e9f4e4d62b0e2` — identical; the restored lines quoted back:

```
    if resolved is None:
        return "commit-unreadable"
```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed, 62 deselected in 0.44s
```

- **verdict:** RED->GREEN

## G9 — cloud_ready dependencyHook condition

- **guarded element:** `plugins/superheroes/lib/cloud_ready.py:160`
- **axis:** with the hook on, the start commit must carry it
- **detector:** `test_cloud_branch_hook_2021.py::test_dod1_hook_on_and_head_lacks_the_hook_is_not_ready_for_that_reason_alone` (selected with `-k "test_dod1_hook_on_and_head_lacks_the_hook_is_not_ready_for_that_reason_alone"`)
- **neutralization (exact string, count(old)=1):**

```diff
-conditions["dependencyHook"] = cloud_setup_text.branch_hook_gap(
-            cwd, root, commit, adopted) is None
+conditions["dependencyHook"] = True
```

- **raw red (rc 1):**

```
F
=================================== FAILURES ===================================
_ test_dod1_hook_on_and_head_lacks_the_hook_is_not_ready_for_that_reason_alone _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-28/test_dod1_hook_on_and_head_lac0')

    def test_dod1_hook_on_and_head_lacks_the_hook_is_not_ready_for_that_reason_alone(tmp_path):
        w, bare, with_hook = _hooked(tmp_path)
        assert _ready(w)["ready"] is True
        _drop_hook_files(w)
        got = _ready(w)
>       assert got["ready"] is False and got["reason"] == "dependency-hook"
E       assert (True is False)

/home/user/wt-2021/plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py:141: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py::test_dod1_hook_on_and_head_lacks_the_hook_is_not_ready_for_that_reason_alone
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed, 62 deselected in 1.68s
```

- **restore:** the inverse edit (the neutralized text replaced by the original, count 1). Restore receipt: sha256 of `plugins/superheroes/lib/cloud_ready.py` before the neutralization `3e77026b80d67d463b3c6fc1e8a2d860f60f8944a80adc633f2793cc2c668f5a`, after the restore `3e77026b80d67d463b3c6fc1e8a2d860f60f8944a80adc633f2793cc2c668f5a` — identical; the restored lines quoted back:

```
conditions["dependencyHook"] = cloud_setup_text.branch_hook_gap(
            cwd, root, commit, adopted) is None
```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed, 62 deselected in 1.98s
```

- **verdict:** RED->GREEN

## G10 — CONDITION_ORDER places dependencyHook before calibration

- **guarded element:** `plugins/superheroes/lib/cloud_ready.py:21`
- **axis:** the hook gap is named before a calibration mismatch
- **detector:** `test_cloud_branch_hook_2021.py::test_the_hook_gap_is_named_before_a_calibration_mismatch` (selected with `-k "test_the_hook_gap_is_named_before_a_calibration_mismatch"`)
- **neutralization (exact string, count(old)=1):**

```diff
-"version", "dependencyHook", "calibration",
-                   "platform")
+"version", "calibration", "dependencyHook",
+                   "platform")
```

- **raw red (rc 1):**

```
F
=================================== FAILURES ===================================
___________ test_the_hook_gap_is_named_before_a_calibration_mismatch ___________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-30/test_the_hook_gap_is_named_bef0')

    def test_the_hook_gap_is_named_before_a_calibration_mismatch(tmp_path):
        w, bare, with_hook = _hooked(tmp_path)
        _drop_hook_files(w)
        got = _ready(w, stamp_fn=lambda cwd, root: "other-stamp")
        assert got["conditions"]["dependencyHook"] is False and got["conditions"]["calibration"] is False
>       assert got["reason"] == "dependency-hook"
E       AssertionError: assert 'calibration' == 'dependency-hook'
E         
E         - dependency-hook
E         + calibration

/home/user/wt-2021/plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py:317: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py::test_the_hook_gap_is_named_before_a_calibration_mismatch
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed, 62 deselected in 1.50s
```

- **restore:** the inverse edit (the neutralized text replaced by the original, count 1). Restore receipt: sha256 of `plugins/superheroes/lib/cloud_ready.py` before the neutralization `3e77026b80d67d463b3c6fc1e8a2d860f60f8944a80adc633f2793cc2c668f5a`, after the restore `3e77026b80d67d463b3c6fc1e8a2d860f60f8944a80adc633f2793cc2c668f5a` — identical; the restored lines quoted back:

```
"version", "dependencyHook", "calibration",
                   "platform")
```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed, 62 deselected in 1.86s
```

- **verdict:** RED->GREEN

## G11 — route passes baseCommit

- **guarded element:** `plugins/superheroes/lib/launch_place.py:213`
- **axis:** the session starts on baseCommit, not the checkout's HEAD
- **detector:** `test_cloud_branch_hook_2021.py::test_route_reads_the_startup_commit_not_the_checkout_head` (selected with `-k "test_route_reads_the_startup_commit_not_the_checkout_head"`)
- **neutralization (exact string, count(old)=1):**

```diff
-commit=base if isinstance(base, str) and base else None,
+commit=None,
```

- **raw red (rc 1):**

```
F
=================================== FAILURES ===================================
__________ test_route_reads_the_startup_commit_not_the_checkout_head ___________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-32/test_route_reads_the_startup_c0')

    def test_route_reads_the_startup_commit_not_the_checkout_head(tmp_path):
        w, bare, with_hook = _hooked(tmp_path)
        _record_for_routing(w)
        # HEAD carries the hook, the startup commit does not
        assert _git(w.repo, "rev-parse", "HEAD") == with_hook
        call = _account_route(w, {"baseCommit": bare})
>       assert call["place"] == "local" and call["reason"] == "dependency-hook"
E       AssertionError: assert ('cloud' == 'local'
E         
E         - local
E         + cloud)

/home/user/wt-2021/plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py:190: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py::test_route_reads_the_startup_commit_not_the_checkout_head
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed, 62 deselected in 1.76s
```

- **restore:** the inverse edit (the neutralized text replaced by the original, count 1). Restore receipt: sha256 of `plugins/superheroes/lib/launch_place.py` before the neutralization `f137c133f4a59ab1f03f425b9b706a56f72086a5e0cbb514eb5a4d54b8c46d09`, after the restore `f137c133f4a59ab1f03f425b9b706a56f72086a5e0cbb514eb5a4d54b8c46d09` — identical; the restored lines quoted back:

```
commit=base if isinstance(base, str) and base else None,
```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed, 62 deselected in 2.44s
```

- **verdict:** RED->GREEN

## G12 — branch_hook_gap hook-off short-circuit

- **guarded element:** `plugins/superheroes/lib/cloud_setup_text.py:344`
- **axis:** a hook that is off reads no git
- **detector:** `test_cloud_branch_hook_2021.py::test_hook_off_in_a_directory_that_is_not_a_repository_reads_no_git` (selected with `-k "test_hook_off_in_a_directory_that_is_not_a_repository_reads_no_git"`)
- **neutralization (exact string, count(old)=1):**

```diff
-    if not _dependency_hook_on(cwd, root, commands):
-        return None
-    inputs = _stored_setup_inputs(cwd, root, commands)
-    repo_root
+    if not _dependency_hook_on(cwd, root, commands):
+        pass
+    inputs = _stored_setup_inputs(cwd, root, commands)
+    repo_root
```

- **raw red (rc 1):**

```
F
=================================== FAILURES ===================================
______ test_hook_off_in_a_directory_that_is_not_a_repository_reads_no_git ______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-34/test_hook_off_in_a_directory_t0')

    def test_hook_off_in_a_directory_that_is_not_a_repository_reads_no_git(tmp_path):
        w = _world(tmp_path)
        _set_ok(w, COMMANDS_SLUG, list(COMMANDS))
        _set_ok(w, HOOK_SLUG, False)
        shutil.rmtree(w.repo / ".git")
        assert not (w.repo / ".git").exists()
>       assert CS.branch_hook_gap(w.cwd, w.root) is None
E       AssertionError: assert 'commit-unreadable' is None
E        +  where 'commit-unreadable' = <function branch_hook_gap at 0x7f99060847c0>('/tmp/claude-0/pytest-of-root/pytest-34/test_hook_off_in_a_directory_t0/repo', '/tmp/claude-0/pytest-of-root/pytest-34/test_hook_off_in_a_directory_t0/store-root')
E        +    where <function branch_hook_gap at 0x7f99060847c0> = CS.branch_hook_gap
E        +    and   '/tmp/claude-0/pytest-of-root/pytest-34/test_hook_off_in_a_directory_t0/repo' = <test_cloud_branch_hook_2021.World object at 0x7f990775a2d0>.cwd
E        +    and   '/tmp/claude-0/pytest-of-root/pytest-34/test_hook_off_in_a_directory_t0/store-root' = <test_cloud_branch_hook_2021.World object at 0x7f990775a2d0>.root

/home/user/wt-2021/plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py:290: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py::test_hook_off_in_a_directory_that_is_not_a_repository_reads_no_git
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed, 62 deselected in 1.28s
```

- **restore:** the inverse edit (the neutralized text replaced by the original, count 1). Restore receipt: sha256 of `plugins/superheroes/lib/cloud_setup_text.py` before the neutralization `d3ad8130bd9b1601755820979c893254f23ecf609e6d13d42807d47361c005a7`, after the restore `d3ad8130bd9b1601755820979c893254f23ecf609e6d13d42807d47361c005a7` — identical; the restored lines quoted back:

```
    if not _dependency_hook_on(cwd, root, commands):
        return None
    inputs = _stored_setup_inputs(cwd, root, commands)
    repo_root
```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed, 62 deselected in 1.29s
```

- **verdict:** RED->GREEN

## G13 — _REREAD_REASONS membership

- **guarded element:** `plugins/superheroes/lib/launch_report.py:31`
- **axis:** the Still on your machine line re-reads the dependency-hook condition
- **detector:** `test_cloud_branch_hook_2021.py::test_the_still_line_rereads_the_dependency_hook_reason` (selected with `-k "test_the_still_line_rereads_the_dependency_hook_reason"`)
- **neutralization (exact string, count(old)=1):**

```diff
-for name in ("setup", "passLive", "dependencyHook", "calibration"))
+for name in ("setup", "passLive", "calibration"))
```

- **raw red (rc 1):**

```
F
=================================== FAILURES ===================================
____________ test_the_still_line_rereads_the_dependency_hook_reason ____________

    def test_the_still_line_rereads_the_dependency_hook_reason():
>       assert "dependency-hook" in launch_report._REREAD_REASONS
E       AssertionError: assert 'dependency-hook' in ('no-setup', 'pass-lapsed', 'calibration')
E        +  where ('no-setup', 'pass-lapsed', 'calibration') = launch_report._REREAD_REASONS

/home/user/wt-2021/plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py:577: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py::test_the_still_line_rereads_the_dependency_hook_reason
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed, 62 deselected in 0.44s
```

- **restore:** the inverse edit (the neutralized text replaced by the original, count 1). Restore receipt: sha256 of `plugins/superheroes/lib/launch_report.py` before the neutralization `f1668a2588234f318734d2d6b83399c6b3a3dc250442cfe5508f5840fdd8038a`, after the restore `f1668a2588234f318734d2d6b83399c6b3a3dc250442cfe5508f5840fdd8038a` — identical; the restored lines quoted back:

```
for name in ("setup", "passLive", "dependencyHook", "calibration"))
```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed, 62 deselected in 0.46s
```

- **verdict:** RED->GREEN

## G14 — branch_gap input-path normalization

- **guarded element:** `plugins/superheroes/lib/cloud_dependency_hook.py:165` (the `_entry` lookups take the normalized `norm`, not the raw path)
- **axis:** a listed input written with a leading dot-slash segment is matched to its tree entry and compared, not read as absent at both commits
- **detector:** `test_cloud_branch_hook_2021.py::test_adoption_changing_a_dot_slash_listed_input_differs` (selected with `-k "test_adoption_changing_a_dot_slash_listed_input_differs"`)
- **neutralization (exact string, count(old)=1):**

```diff
-            ours = _entry(repo_root, resolved, norm)
-            theirs = _entry(repo_root, base, norm)
+            ours = _entry(repo_root, resolved, path)
+            theirs = _entry(repo_root, base, path)
```

- **raw red (rc 1):** the pytest `+  where` detail lines under the assertion are omitted in this record only

```
F
=================================== FAILURES ===================================
___________ test_adoption_changing_a_dot_slash_listed_input_differs ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-44/test_adoption_changing_a_dot_s0')

    def test_adoption_changing_a_dot_slash_listed_input_differs(tmp_path):
        w, start = _hooked_with_dot_slash_input(tmp_path)
        _lock(w, "v2\n")
        adopted = _commit(w.cwd, "lock changed")
>       assert CS.branch_hook_gap(w.cwd, w.root, start, adopted) == "adopted-inputs-differ"
E       AssertionError: assert None == 'adopted-inputs-differ'

/home/user/wt-2021/plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py:493: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py::test_adoption_changing_a_dot_slash_listed_input_differs
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed, 66 deselected in 13.54s
```

- **restore:** the inverse edit (the neutralized text replaced by the original, count 1). Restore receipt: sha256 of `plugins/superheroes/lib/cloud_dependency_hook.py` before the neutralization `e0fbd587a224f6228f1851a4e8f5148c3b92e0e2d40087b59e7e1dee9168e625`, after the restore `e0fbd587a224f6228f1851a4e8f5148c3b92e0e2d40087b59e7e1dee9168e625` — identical; the restored lines quoted back:

```
            ours = _entry(repo_root, resolved, norm)
            theirs = _entry(repo_root, base, norm)
```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed, 66 deselected in 3.49s
```

- **verdict:** RED->GREEN

## G15 — branch_gap non-regular input fail-closed leg

- **guarded element:** `plugins/superheroes/lib/cloud_dependency_hook.py:171`
- **axis:** a listed input that is a symlink, tree or submodule at either commit fails closed, because the hook reads it through its target and equal entries prove nothing; the return is `adopted-input-not-a-file` (F5; it was `adopted-inputs-differ`)
- **detectors:** `test_cloud_branch_hook_2021.py::test_edge11_a_symlink_input_with_an_unchanged_target_is_not_a_file` (renamed in F5 from `..._target_differs`) and `test_cloud_branch_hook_symlink_breakit_2021.py::test_adoption_refuses_a_changed_target_of_an_unchanged_input_symlink` (both selected in one run with `-k "test_edge11_a_symlink_input_with_an_unchanged_target_is_not_a_file or test_adoption_refuses_a_changed_target_of_an_unchanged_input_symlink"`)
- **neutralization (exact string, count(old)=1):**

```diff
-            if (ours and not _regular(ours)) or (theirs and not _regular(theirs)):
+            if False:
```

- **raw red (rc 1, taken before the F5 token rename, so the quoted asserts show the old `adopted-inputs-differ` token; not re-run):** the traceback bodies are elided with `...` in this record only

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_________ test_edge11_a_symlink_input_with_an_unchanged_target_differs _________
...
>       assert _gap(repo, linked, adopted=adopted) == "adopted-inputs-differ"
E       AssertionError: assert None == 'adopted-inputs-differ'
...
_____ test_adoption_refuses_a_changed_target_of_an_unchanged_input_symlink _____
...
>       assert CS.branch_hook_gap(
            world.cwd, world.root, startup, adopted
        ) == "adopted-inputs-differ"
E       AssertionError: assert None == 'adopted-inputs-differ'
...
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py::test_edge11_a_symlink_input_with_an_unchanged_target_differs
FAILED plugins/superheroes/lib/tests/test_cloud_branch_hook_symlink_breakit_2021.py::test_adoption_refuses_a_changed_target_of_an_unchanged_input_symlink
2 failed, 66 deselected in 3.56s
```

- **restore:** the inverse edit (the neutralized text replaced by the original, count 1). Restore receipt: sha256 of `plugins/superheroes/lib/cloud_dependency_hook.py` before the neutralization `e0fbd587a224f6228f1851a4e8f5148c3b92e0e2d40087b59e7e1dee9168e625`, after the restore `e0fbd587a224f6228f1851a4e8f5148c3b92e0e2d40087b59e7e1dee9168e625` — identical; the restored line quoted back:

```
            if (ours and not _regular(ours)) or (theirs and not _regular(theirs)):
```

- **raw green (rc 0):**

```
..                                                                       [100%]
2 passed, 66 deselected in 1.95s
```

- **verdict:** RED->GREEN

## G16 — branch_gap ancestor-directory fail-closed leg

- **guarded element:** `plugins/superheroes/lib/cloud_dependency_hook.py:143` (the refusal inside `_ancestor_gap`)
- **axis:** a listed nested input whose ancestor directory is a symlink, file or submodule at either commit fails closed, because `git ls-tree` cannot traverse the link and reads the input as absent while the hook reads it through the link; the return is `adopted-input-not-a-file` (F5; it was `adopted-inputs-differ`)
- **detector:** `test_cloud_branch_hook_2021.py::test_adoption_changing_a_file_behind_a_symlinked_input_directory_differs` (selected with `-k "test_adoption_changing_a_file_behind_a_symlinked_input_directory_differs"`)
- **neutralization (exact string, count(old)=1):**

```diff
-            if entry and entry[1] != "tree":
+            if False:
```

- **raw red (rc 1, taken before the F5 token rename, so the quoted assert shows the old `adopted-inputs-differ` token; not re-run):** the pytest `+  where` detail lines under the assertion are omitted in this record only

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_adoption_changing_a_file_behind_a_symlinked_input_directory_differs ___

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-50/test_adoption_changing_a_file_0')

    def test_adoption_changing_a_file_behind_a_symlinked_input_directory_differs(tmp_path):
        w, start = _hooked_with_nested_input(tmp_path, linked=True)
        (w.repo / "real-deps" / "requirements.txt").write_text("v2\n")
        adopted = _commit(w.cwd, "target file changed")
>       assert CS.branch_hook_gap(w.cwd, w.root, start, adopted) == "adopted-inputs-differ"
E       AssertionError: assert None == 'adopted-inputs-differ'

/home/user/wt-2021/plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py:546: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py::test_adoption_changing_a_file_behind_a_symlinked_input_directory_differs
1 failed, 69 deselected in 1.73s
```

- **restore:** the inverse edit (the neutralized text replaced by the original, count 1). Restore receipt: the restored line quoted back below; sha256 of `plugins/superheroes/lib/cloud_dependency_hook.py` while neutralized `c696fbc32d7338bbc5dd68da0240e3ace6563ff995f0686e7ce291effda9ffe4`, after the restore `1f0b4f38fb595f0db3f75825680f4d6617d35986383fbb6efef3d053b1e20021` (no sha was taken before the neutralization, so there is no before/after pair for this element):

```
            if entry and entry[1] != "tree":
```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed, 69 deselected in 4.49s
```

- **verdict:** RED->GREEN

## G17 — the still line's dependency-hook rule compares the launch's adopted head with the checkout's HEAD

- **guarded element:** `plugins/superheroes/lib/launch_report.py:217-218` (the `dependency-hook` branch in `_fixed`, its `candidate.get("adoptsHead")` argument)
- **axis:** a dependency-hook fallback reads fixed only when readiness's `dependencyHook` reads true now and the check routing ran (`branch_hook_gap` on the checkout's current `HEAD`, against the launch's own `adoptsHead`) returns no gap, so a `HEAD` that carries the hook does not clear a fallback whose adopted head changed a listed input
- **detector:** `test_cloud_branch_hook_2021.py::test_the_still_line_rereads_the_dependency_hook_reason`, case (b) (selected with `-k "test_the_still_line_rereads_the_dependency_hook_reason"`)
- **neutralization (exact string, count(old)=1):**

```diff
-            cwd, root, None, candidate.get("adoptsHead")) is None
+            cwd, root, None, None) is None
```

- **raw red (rc 1):** the new line is replaced by `None) is None` for the adopted head; case (a) passes and case (b) goes red (the pytest `UV_NATIVE_TLS` warning line is dropped)

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_the_still_line_rereads_the_dependency_hook_reason ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-61/test_the_still_line_rereads_th0')

    def test_the_still_line_rereads_the_dependency_hook_reason(tmp_path):
        assert "dependency-hook" in launch_report._REREAD_REASONS
        w, bare, with_hook = _hooked(tmp_path)
        (w.repo / "other.txt").write_text("x\n")
        same_inputs = _commit(w.cwd, "other file")
        _lock(w, "v2\n")
        changed = _commit(w.cwd, "lock changed")
        _git(w.repo, "checkout", "-q", "--detach", same_inputs)
        # the checkout's HEAD carries the hook and the lock file as `with_hook` has it
        assert _git(w.repo, "rev-parse", "HEAD") == same_inputs
        assert CS.branch_hook_gap(w.cwd, w.root) is None
    
        def fixed(base, adopts):
            return launch_report._fixed(_hook_candidate(base, adopts), _NOW_READS_FIXED, w.cwd, w.root)
    
        # (a) the launch's base lacked the hook and the hook has since been committed on HEAD: fixed,
        # with no adopted head and with an adopted head whose listed inputs match HEAD
        assert fixed(bare, None) is True
        assert fixed(bare, with_hook) is True
        # (b) the adopted head changed a listed input relative to HEAD: the fallback stands even though
        # HEAD carries the hook
>       assert fixed(bare, changed) is False
E       AssertionError: assert True is False
E        +  where True = <function test_the_still_line_rereads_the_dependency_hook_reason.<locals>.fixed at 0x7f0eb1824900>('aace2fe712a31a8a410a247990041f8254076bcb', 'fd9da2b18e1bf717a5e928ca1227350ebb25e916')

/home/user/wt-2021/plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py:753: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py::test_the_still_line_rereads_the_dependency_hook_reason
1 failed, 71 deselected in 5.24s
```

- **restore:** the inverse edit (the neutralized text replaced by the original, count 1). Restore receipt: sha256 of `plugins/superheroes/lib/launch_report.py` before the neutralization `06b46a4cff5c6f501eee2a30c9a545d85a5f913117df60b9775211570dea077a`, while neutralized `d63282cd03ebb4aa133b6a754a42c069696c4e2101f8e7bd33a1717577b5ebde`, after the restore `06b46a4cff5c6f501eee2a30c9a545d85a5f913117df60b9775211570dea077a` — before and after identical; the restored lines quoted back:

```
        return conditions.get("dependencyHook") is True and cloud_setup_text.branch_hook_gap(
            cwd, root, None, candidate.get("adoptsHead")) is None
```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed, 71 deselected in 8.03s
```

- **verdict:** RED->GREEN

## G18 — the still line's dependency-hook rule checks the checkout's current HEAD, not the failed launch's baseCommit

- **guarded element:** `plugins/superheroes/lib/launch_report.py:217-218` (the `dependency-hook` branch in `_fixed`, its `None` commit argument)
- **axis:** after a launch fell back because its base lacked the hook, committing the hook on the checkout's `HEAD` clears the reminder, because the check runs on `HEAD` (commit `None`) and never on the launch's immutable `baseCommit`
- **detector:** `test_cloud_branch_hook_2021.py::test_the_still_line_rereads_the_dependency_hook_reason`, case (a) (selected with `-k "test_the_still_line_rereads_the_dependency_hook_reason"`)
- **neutralization (exact string, count(old)=1):**

```diff
-            cwd, root, None, candidate.get("adoptsHead")) is None
+            cwd, root, candidate.get("baseCommit"), candidate.get("adoptsHead")) is None
```

- **raw red (rc 1):** the pytest `UV_NATIVE_TLS` warning line is dropped

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_the_still_line_rereads_the_dependency_hook_reason ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-63/test_the_still_line_rereads_th0')

    def test_the_still_line_rereads_the_dependency_hook_reason(tmp_path):
        assert "dependency-hook" in launch_report._REREAD_REASONS
        w, bare, with_hook = _hooked(tmp_path)
        (w.repo / "other.txt").write_text("x\n")
        same_inputs = _commit(w.cwd, "other file")
        _lock(w, "v2\n")
        changed = _commit(w.cwd, "lock changed")
        _git(w.repo, "checkout", "-q", "--detach", same_inputs)
        # the checkout's HEAD carries the hook and the lock file as `with_hook` has it
        assert _git(w.repo, "rev-parse", "HEAD") == same_inputs
        assert CS.branch_hook_gap(w.cwd, w.root) is None
    
        def fixed(base, adopts):
            return launch_report._fixed(_hook_candidate(base, adopts), _NOW_READS_FIXED, w.cwd, w.root)
    
        # (a) the launch's base lacked the hook and the hook has since been committed on HEAD: fixed,
        # with no adopted head and with an adopted head whose listed inputs match HEAD
>       assert fixed(bare, None) is True
E       AssertionError: assert False is True
E        +  where False = <function test_the_still_line_rereads_the_dependency_hook_reason.<locals>.fixed at 0x7f398a0ac720>('15bae00bb251f7db1cbb843759f92719e80f9349', None)

/home/user/wt-2021/plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py:749: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py::test_the_still_line_rereads_the_dependency_hook_reason
1 failed, 71 deselected in 1.72s
```

- **restore:** the inverse edit (the neutralized text replaced by the original, count 1). Restore receipt: sha256 of `plugins/superheroes/lib/launch_report.py` before the neutralization `06b46a4cff5c6f501eee2a30c9a545d85a5f913117df60b9775211570dea077a`, while neutralized `0030c23f8ccd70b9f34dd3fc2de11a7b9c164ab339d72f6007db878e68f52030`, after the restore `06b46a4cff5c6f501eee2a30c9a545d85a5f913117df60b9775211570dea077a` — before and after identical; the restored lines quoted back:

```
        return conditions.get("dependencyHook") is True and cloud_setup_text.branch_hook_gap(
            cwd, root, None, candidate.get("adoptsHead")) is None
```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed, 71 deselected in 2.31s
```

- **verdict:** RED->GREEN

## G19 — the fixture Git environment drops every inherited GIT_* variable

(Not named by the order; added because the order added a detector, the regression test for finding v1.)

- **guarded element:** `plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py:36-37` (the `_GIT_ENV` comprehension that filters out names starting with `GIT_`)
- **axis:** inherited Git routing such as `GIT_INDEX_FILE`, `GIT_DIR` or `GIT_WORK_TREE` never reaches a fixture Git command, so a fixture cannot stage into or alter the caller's index or repository
- **detector:** `test_cloud_branch_hook_2021.py::test_inherited_git_index_routing_never_reaches_the_fixture_commands` (selected with `-k "test_inherited_git_index_routing_never_reaches_the_fixture_commands"`); it runs a tiny pytest case in a subprocess with `GIT_INDEX_FILE` pointing at a sentinel path under `tmp_path`, and asserts the sentinel is never created
- **neutralization (exact string, count(old)=1):**

```diff
-_GIT_ENV = {**{k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
+_GIT_ENV = {**os.environ,
```

- **raw red (rc 1):** the pytest `UV_NATIVE_TLS` warning line is dropped

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_inherited_git_index_routing_never_reaches_the_fixture_commands ______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-65/test_inherited_git_index_routi0')

    def test_inherited_git_index_routing_never_reaches_the_fixture_commands(tmp_path):
        here = tmp_path / "probe"
        here.mkdir()
        (here / "test_probe.py").write_text(_ROUTING_PROBE % {"here": _HERE})
        sentinel = tmp_path / "sentinel-index"
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(GIT_INDEX_FILE=str(sentinel), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                   PYTHONDONTWRITEBYTECODE="1")
        ran = subprocess.run(
            [sys.executable, "-m", "pytest", str(here / "test_probe.py"), "-q", "-p", "no:cacheprovider",
             "--rootdir", str(here)],
            capture_output=True, env=env, cwd=str(here))
        assert ran.returncode == 0, ran.stdout.decode("utf-8") + ran.stderr.decode("utf-8")
        assert b"1 passed" in ran.stdout
>       assert not sentinel.exists()
E       AssertionError: assert not True
E        +  where True = exists()
E        +    where exists = PosixPath('/tmp/claude-0/pytest-of-root/pytest-65/test_inherited_git_index_routi0/sentinel-index').exists

/home/user/wt-2021/plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py:168: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py::test_inherited_git_index_routing_never_reaches_the_fixture_commands
1 failed, 71 deselected in 1.18s
```

- **restore:** the inverse edit (the neutralized text replaced by the original, count 1). Restore receipt: sha256 of `plugins/superheroes/lib/tests/test_cloud_branch_hook_2021.py` before the neutralization `368f8f196f19ab608b700513c923a25ff04517013f6ecefdaece8ffbdb9ad45f`, after the restore `368f8f196f19ab608b700513c923a25ff04517013f6ecefdaece8ffbdb9ad45f` — identical (no sha was taken while neutralized); the restored lines quoted back:

```
_GIT_ENV = {**{k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
```

- **raw green (rc 0):**

```
.                                                                        [100%]
1 passed, 71 deselected in 1.23s
```

- **verdict:** RED->GREEN

## G20 — the generated script reads its first argument with a default

(Added by the #2021 amendment order `wo-f7-2021`, which named this bite-proof.)

- **guarded element:** `plugins/superheroes/lib/cloud_dependency_hook.py:256` (the `"${1-}"` default in the `--record` check of `script_text`)
- **axis:** the generated script never ends with an unbound-variable error under an inherited `nounset` (`SHELLOPTS=nounset`), so it keeps its "never fails the session" promise when started with no arguments
- **detector:** `test_cloud_dependency_hook_nounset_2021.py::test_the_script_never_dies_of_an_unbound_variable_under_nounset` (selected with `-k "no-args"`, the two no-argument modes)
- **neutralization (exact string, count(old)=1):**

```diff
-        'if [ "${1-}" = "--record" ]; then',
+        'if [ "$1" = "--record" ]; then',
```

- **raw red (rc 1):** the pytest `UV_NATIVE_TLS` warning line is dropped; the pytest-parametrize source echo is elided from the two tracebacks below only to the lines shown (the output was not otherwise cut)

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_the_script_never_dies_of_an_unbound_variable_under_nounset[no-args-local] _
E       AssertionError: /tmp/claude-0/pytest-of-root/pytest-77/test_the_script_never_dies_of_0/repo/.claude/hooks/superheroes-cloud-dependencies.sh: line 10: $1: unbound variable
_ test_the_script_never_dies_of_an_unbound_variable_under_nounset[no-args-cloud] _
E       AssertionError: /tmp/claude-0/pytest-of-root/pytest-77/test_the_script_never_dies_of_1/repo/.claude/hooks/superheroes-cloud-dependencies.sh: line 10: $1: unbound variable
FAILED plugins/superheroes/lib/tests/test_cloud_dependency_hook_nounset_2021.py::test_the_script_never_dies_of_an_unbound_variable_under_nounset[no-args-local]
FAILED plugins/superheroes/lib/tests/test_cloud_dependency_hook_nounset_2021.py::test_the_script_never_dies_of_an_unbound_variable_under_nounset[no-args-cloud]
2 failed, 3 deselected in 0.43s
```

- **restore:** the inverse edit (the neutralized line replaced by the original, count 1). Restore receipt: sha256 of `plugins/superheroes/lib/cloud_dependency_hook.py` before the neutralization `a78a973af3e27d2af7be9bf12069ee6562d13eaa8cc6e1333b1d21e9ef0e6f13`, while neutralized `a489e659482f9742f488c2b633d08910ec1764343c93822a1b5b022dfa2d3ae5`, after the restore `a78a973af3e27d2af7be9bf12069ee6562d13eaa8cc6e1333b1d21e9ef0e6f13` — identical to before; the restored line quoted back:

```
        'if [ "${1-}" = "--record" ]; then',
```

- **raw green (rc 0):**

```
..                                                                       [100%]
2 passed, 3 deselected in 4.59s
```

- **verdict:** RED->GREEN
