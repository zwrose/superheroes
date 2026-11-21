# WO-1 (#2536) bite-proofs — dispatch_core reads the core.md the storage mode selects

Guarded-element set (declared by the order, exactly five):

- G1 the mode-selection swap itself.
- G2 the mode direction (in-repo mode picks the in-repo core, anything else the global core).
- G3 branch independence (the swap applies whichever resolve branch won, the legacy-profile branch included).
- G4 the regular-file guard (a dangling symlink is not a core).
- G5 the exception fallback (a failing candidate or mode computation leaves today's value).

All runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/pyc-2536 -m pytest plugins/superheroes/lib/tests/test_mode_selected_core_2536.py -q -p no:cacheprovider`,
from the worktree root, tests unedited between red and green. Every neutralization was a single targeted Edit in
`plugins/superheroes/lib/calibration_resolve.py` and every restore the exact inverse Edit; no `git checkout`,
`git restore`, `git reset` or `git stash`. Nothing in the receipts is a secret, token or private URL; nothing was redacted.
Each green run below is the full file, 11 tests, after the restore. The restore receipt is the restored line(s)
quoted back; the final whole-file `git diff` of `calibration_resolve.py` (in the dispatch report) shows only the intended change.

---

## G1 the mode-selection swap

**Guarded element:** `_with_dispatch_fields`, the `if selected:` swap. Axis: with both cores regular files,
`dispatch_core` is the mode-selected one, not today's branch value.

**Neutralization:** `    if selected:` changed to `    if False and selected:`.

**Raw red** (exit 1; the edge-1 test and the legacy-branch test, both global mode):
```
F..F.......                                                              [100%]
=================================== FAILURES ===================================
____________ test_both_cores_global_mode_dispatches_the_global_core ____________

repo = '/tmp/claude-0/pytest-of-root/pytest-1/test_both_cores_global_mode_di0/repo'

    def test_both_cores_global_mode_dispatches_the_global_core(repo):
        # axis: with both cores regular files and the mode global, dispatch_core is the global core, not the in-repo one
        registry = mode_registry.registry_path(repo)
        before = _bytes(registry)
        info = calibration_resolve.resolve(repo)
        assert info["layout"] == "unified" and info["location"] == mode_registry.IN_REPO  # the in-repo layer won the branch
        assert info["core_path"] == _inrepo_core(repo)  # and the branch's own core_path is left alone
>       assert info["dispatch_core"] == _global_core(repo)
E       AssertionError: assert '/tmp/claude-...eroes/core.md' == '/tmp/claude-...onfig/core.md'
E         
E         Skipping 60 identical leading characters in diff, use -v to show
E         - _mode_di0/home/.claude/superheroes/projects/1e19520cbeb283bf/config/core.md
E         + _mode_di0/repo/.claude/superheroes/core.md

/home/user/wt-2536/plugins/superheroes/lib/tests/test_mode_selected_core_2536.py:126: AssertionError
_____ test_a_legacy_profile_branch_still_dispatches_the_mode_selected_core _____

bare = '/tmp/claude-0/pytest-of-root/pytest-1/test_a_legacy_profile_branch_s0/repo'

    def test_a_legacy_profile_branch_still_dispatches_the_mode_selected_core(bare):
        # axis: the mode-selected core wins whichever resolve branch won, the legacy-profile branch included
        _put_core(_global_core(bare), _GLOBAL_VERIFY)
        _put_core(_inrepo_core(bare), _STALE_VERIFY)
        _put(_legacy_profile(bare), "# legacy review profile\n")
        info = calibration_resolve.resolve(bare)
        assert info["layout"] == "legacy" and info["legacy_path"] == _legacy_profile(bare)  # the legacy branch won
        assert info["core_path"] is None  # so today's dispatch_core would be the legacy profile
>       assert info["dispatch_core"] == _global_core(bare)
E       AssertionError: assert '/tmp/claude-...ew-profile.md' == '/tmp/claude-...onfig/core.md'
E         
E         Skipping 60 identical leading characters in diff, use -v to show
E         - branch_s0/home/.claude/superheroes/projects/9c276fd07ec31a94/config/core.md
E         + branch_s0/repo/.claude/review-profile.md

/home/user/wt-2536/plugins/superheroes/lib/tests/test_mode_selected_core_2536.py:163: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_mode_selected_core_2536.py::test_both_cores_global_mode_dispatches_the_global_core
FAILED plugins/superheroes/lib/tests/test_mode_selected_core_2536.py::test_a_legacy_profile_branch_still_dispatches_the_mode_selected_core
2 failed, 9 passed in 1.05s
```

**Restore:** inverse Edit, `if False and selected:` back to `if selected:`.
**Restore receipt:** `    if selected:` followed by `        out["dispatch_core"] = selected`.

**Raw green** (exit 0):
```
...........                                                              [100%]
11 passed in 1.02s
```

---

## G2 the mode direction

**Guarded element:** `_mode_selected_core`, the final return. Axis: in-repo mode selects the in-repo core, any
other mode the global core.

**Neutralization:** `return in_repo if mode == mode_registry.IN_REPO else global_path` changed to
`return global_path if mode == mode_registry.IN_REPO else in_repo`.

**Raw red** (exit 1; edge 1 and edge 2 are among the four reds):
```
FFFF.......                                                              [100%]
=================================== FAILURES ===================================
____________ test_both_cores_global_mode_dispatches_the_global_core ____________

repo = '/tmp/claude-0/pytest-of-root/pytest-3/test_both_cores_global_mode_di0/repo'

    def test_both_cores_global_mode_dispatches_the_global_core(repo):
        # axis: with both cores regular files and the mode global, dispatch_core is the global core, not the in-repo one
        registry = mode_registry.registry_path(repo)
        before = _bytes(registry)
        info = calibration_resolve.resolve(repo)
        assert info["layout"] == "unified" and info["location"] == mode_registry.IN_REPO  # the in-repo layer won the branch
        assert info["core_path"] == _inrepo_core(repo)  # and the branch's own core_path is left alone
>       assert info["dispatch_core"] == _global_core(repo)
E       AssertionError: assert '/tmp/claude-...eroes/core.md' == '/tmp/claude-...onfig/core.md'
E         
E         Skipping 60 identical leading characters in diff, use -v to show
E         - _mode_di0/home/.claude/superheroes/projects/715a281afb3812ec/config/core.md
E         + _mode_di0/repo/.claude/superheroes/core.md

/home/user/wt-2536/plugins/superheroes/lib/tests/test_mode_selected_core_2536.py:126: AssertionError
___________ test_both_cores_in_repo_mode_dispatches_the_in_repo_core ___________

repo = '/tmp/claude-0/pytest-of-root/pytest-3/test_both_cores_in_repo_mode_d0/repo'

    def test_both_cores_in_repo_mode_dispatches_the_in_repo_core(repo):
        # axis: with both cores regular files and the mode in-repo, dispatch_core is the in-repo core, not the global one
        _record_mode(repo, mode_registry.IN_REPO)
>       assert _dispatch_core(repo) == _inrepo_core(repo)
E       AssertionError: assert '/tmp/claude-...onfig/core.md' == '/tmp/claude-...eroes/core.md'
E         
E         Skipping 60 identical leading characters in diff, use -v to show
E         - o_mode_d0/repo/.claude/superheroes/core.md
E         + o_mode_d0/home/.claude/superheroes/projects/919c8b7e215982e3/config/core.md

/home/user/wt-2536/plugins/superheroes/lib/tests/test_mode_selected_core_2536.py:141: AssertionError
_________________ test_mode_is_read_without_writing_a_registry _________________

unrecorded = '/tmp/claude-0/pytest-of-root/pytest-3/test_mode_is_read_without_writ0/repo'

    def test_mode_is_read_without_writing_a_registry(unrecorded):
        # axis: the mode is read with persist_backfill=False, so evidence alone never writes a registry
        _put_core(_global_core(unrecorded), _GLOBAL_VERIFY)
        _put_core(_inrepo_core(unrecorded), _STALE_VERIFY)
        _put(_inrepo_layer(unrecorded), _LAYER_TEXT)
        assert not os.path.exists(mode_registry.registry_path(unrecorded))
>       assert _dispatch_core(unrecorded) == _inrepo_core(unrecorded)  # the in-repo layer is the evidence: mode in-repo
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AssertionError: assert '/tmp/claude-...onfig/core.md' == '/tmp/claude-...eroes/core.md'
E         
E         Skipping 60 identical leading characters in diff, use -v to show
E         - out_writ0/repo/.claude/superheroes/core.md
E         + out_writ0/home/.claude/superheroes/projects/7744ad74eef17ae5/config/core.md

/home/user/wt-2536/plugins/superheroes/lib/tests/test_mode_selected_core_2536.py:151: AssertionError
_____ test_a_legacy_profile_branch_still_dispatches_the_mode_selected_core _____

bare = '/tmp/claude-0/pytest-of-root/pytest-3/test_a_legacy_profile_branch_s0/repo'

    def test_a_legacy_profile_branch_still_dispatches_the_mode_selected_core(bare):
        # axis: the mode-selected core wins whichever resolve branch won, the legacy-profile branch included
        _put_core(_global_core(bare), _GLOBAL_VERIFY)
        _put_core(_inrepo_core(bare), _STALE_VERIFY)
        _put(_legacy_profile(bare), "# legacy review profile\n")
        info = calibration_resolve.resolve(bare)
        assert info["layout"] == "legacy" and info["legacy_path"] == _legacy_profile(bare)  # the legacy branch won
        assert info["core_path"] is None  # so today's dispatch_core would be the legacy profile
>       assert info["dispatch_core"] == _global_core(bare)
E       AssertionError: assert '/tmp/claude-...eroes/core.md' == '/tmp/claude-...onfig/core.md'
E         
E         Skipping 60 identical leading characters in diff, use -v to show
E         - branch_s0/home/.claude/superheroes/projects/8c22f7c90e2f305a/config/core.md
E         + branch_s0/repo/.claude/superheroes/core.md

/home/user/wt-2536/plugins/superheroes/lib/tests/test_mode_selected_core_2536.py:163: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_mode_selected_core_2536.py::test_both_cores_global_mode_dispatches_the_global_core
FAILED plugins/superheroes/lib/tests/test_mode_selected_core_2536.py::test_both_cores_in_repo_mode_dispatches_the_in_repo_core
FAILED plugins/superheroes/lib/tests/test_mode_selected_core_2536.py::test_mode_is_read_without_writing_a_registry
FAILED plugins/superheroes/lib/tests/test_mode_selected_core_2536.py::test_a_legacy_profile_branch_still_dispatches_the_mode_selected_core
4 failed, 7 passed in 1.03s
```

**Restore:** inverse Edit, back to `in_repo if ... IN_REPO else global_path`.
**Restore receipt:** `    return in_repo if mode == mode_registry.IN_REPO else global_path`.

**Raw green** (exit 0):
```
...........                                                              [100%]
11 passed in 1.17s
```

---

## G3 branch independence

**Guarded element:** `_with_dispatch_fields`, the swap's condition. Axis: the swap applies when the winning branch
has no `core_path` (the legacy-profile branch), not only when it has one.

**Neutralization:** `    if selected:` changed to `    if selected and out.get("core_path"):`.

**Raw red** (exit 1; only the edge-3 test goes red, the edge-1 branch has a `core_path`):
```
...F.......                                                              [100%]
=================================== FAILURES ===================================
_____ test_a_legacy_profile_branch_still_dispatches_the_mode_selected_core _____

bare = '/tmp/claude-0/pytest-of-root/pytest-5/test_a_legacy_profile_branch_s0/repo'

    def test_a_legacy_profile_branch_still_dispatches_the_mode_selected_core(bare):
        # axis: the mode-selected core wins whichever resolve branch won, the legacy-profile branch included
        _put_core(_global_core(bare), _GLOBAL_VERIFY)
        _put_core(_inrepo_core(bare), _STALE_VERIFY)
        _put(_legacy_profile(bare), "# legacy review profile\n")
        info = calibration_resolve.resolve(bare)
        assert info["layout"] == "legacy" and info["legacy_path"] == _legacy_profile(bare)  # the legacy branch won
        assert info["core_path"] is None  # so today's dispatch_core would be the legacy profile
>       assert info["dispatch_core"] == _global_core(bare)
E       AssertionError: assert '/tmp/claude-...ew-profile.md' == '/tmp/claude-...onfig/core.md'
E         
E         Skipping 60 identical leading characters in diff, use -v to show
E         - branch_s0/home/.claude/superheroes/projects/43ca974ae8fabe1e/config/core.md
E         + branch_s0/repo/.claude/review-profile.md

/home/user/wt-2536/plugins/superheroes/lib/tests/test_mode_selected_core_2536.py:163: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_mode_selected_core_2536.py::test_a_legacy_profile_branch_still_dispatches_the_mode_selected_core
1 failed, 10 passed in 1.09s
```

**Restore:** inverse Edit, `if selected and out.get("core_path"):` back to `if selected:`.
**Restore receipt:** `    if selected:` followed by `        out["dispatch_core"] = selected`.

**Raw green** (exit 0):
```
...........                                                              [100%]
11 passed in 1.16s
```

---

## G4 the regular-file guard

**Guarded element:** `_mode_selected_core`, the two `os.path.isfile` checks. Axis: a dangling symlink is not a
core, so a side that is only a dangling symlink leaves `dispatch_core` as it was.

**Neutralization:** `os.path.isfile(in_repo) and os.path.isfile(global_path)` changed to
`os.path.lexists(in_repo) and os.path.lexists(global_path)`.

**Raw red** (exit 1; both dangling-symlink tests go red):
```
....FF.....                                                              [100%]
=================================== FAILURES ===================================
__ test_a_dangling_in_repo_core_is_not_a_core_and_dispatch_keeps_todays_value __

bare = '/tmp/claude-0/pytest-of-root/pytest-7/test_a_dangling_in_repo_core_i0/repo'

    def test_a_dangling_in_repo_core_is_not_a_core_and_dispatch_keeps_todays_value(bare):
        # axis: only a regular file counts as a candidate, so a dangling symlink leaves dispatch_core as it was
        _put_core(_global_core(bare), _GLOBAL_VERIFY)
        _put(_global_layer(bare), _LAYER_TEXT)
        os.makedirs(os.path.dirname(_inrepo_core(bare)), exist_ok=True)
        os.symlink(os.path.join(bare, "no-such-core.md"), _inrepo_core(bare))
        assert os.path.lexists(_inrepo_core(bare)) and not os.path.isfile(_inrepo_core(bare))
        _record_mode(bare, mode_registry.IN_REPO)  # the mode that would select the dangling side
>       assert _dispatch_core(bare) == _global_core(bare)
E       AssertionError: assert '/tmp/claude-...eroes/core.md' == '/tmp/claude-...onfig/core.md'
E         
E         Skipping 60 identical leading characters in diff, use -v to show
E         - o_core_i0/home/.claude/superheroes/projects/45fc7d5aab7f6f76/config/core.md
E         + o_core_i0/repo/.claude/superheroes/core.md

/home/user/wt-2536/plugins/superheroes/lib/tests/test_mode_selected_core_2536.py:177: AssertionError
__ test_a_dangling_global_core_is_not_a_core_and_dispatch_keeps_todays_value ___

bare = '/tmp/claude-0/pytest-of-root/pytest-7/test_a_dangling_global_core_is0/repo'

    def test_a_dangling_global_core_is_not_a_core_and_dispatch_keeps_todays_value(bare):
        # axis: only a regular file counts as a candidate, so a dangling symlink leaves dispatch_core as it was
        _put_core(_inrepo_core(bare), _STALE_VERIFY)
        _put(_inrepo_layer(bare), _LAYER_TEXT)
        os.makedirs(os.path.dirname(_global_core(bare)), exist_ok=True)
        os.symlink(os.path.join(bare, "no-such-core.md"), _global_core(bare))
        assert os.path.lexists(_global_core(bare)) and not os.path.isfile(_global_core(bare))
>       assert _dispatch_core(bare) == _inrepo_core(bare)  # mode global would select the dangling side
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AssertionError: assert '/tmp/claude-...onfig/core.md' == '/tmp/claude-...eroes/core.md'
E         
E         Skipping 60 identical leading characters in diff, use -v to show
E         - _core_is0/repo/.claude/superheroes/core.md
E         + _core_is0/home/.claude/superheroes/projects/5ee21fa5bc7f321f/config/core.md

/home/user/wt-2536/plugins/superheroes/lib/tests/test_mode_selected_core_2536.py:187: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_mode_selected_core_2536.py::test_a_dangling_in_repo_core_is_not_a_core_and_dispatch_keeps_todays_value
FAILED plugins/superheroes/lib/tests/test_mode_selected_core_2536.py::test_a_dangling_global_core_is_not_a_core_and_dispatch_keeps_todays_value
2 failed, 9 passed in 1.21s
```

**Restore:** inverse Edit, `lexists` back to `isfile` on both operands.
**Restore receipt:** `        if not (os.path.isfile(in_repo) and os.path.isfile(global_path)):`.

**Raw green** (exit 0):
```
...........                                                              [100%]
11 passed in 1.22s
```

---

## G5 the exception fallback

**Guarded element:** `_mode_selected_core`, the `try` / `except Exception: return None` around the candidate and
mode computation. Axis: a failing computation never reaches `resolve`'s caller and leaves today's value.

**Neutralization:** the `try:` line and the `except Exception:` / `return None` pair removed, the body dedented one
level (the candidate computation, the `isfile` guard and the mode read stay, unprotected).

**Raw red** (exit 1; both raise tests go red):
```
.........FF                                                              [100%]
=================================== FAILURES ===================================
_________ test_a_candidate_computation_that_raises_leaves_todays_value _________

repo = '/tmp/claude-0/pytest-of-root/pytest-9/test_a_candidate_computation_t0/repo'
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f045cf50950>

    def test_a_candidate_computation_that_raises_leaves_todays_value(repo, monkeypatch):
        # axis: a failure computing the candidates never reaches the caller and never changes dispatch_core
        def boom(cwd, root=None):
            raise core_md.RepoRootUnavailable("git could not be run", git_status=None)
        monkeypatch.setattr(core_md, "_core_candidates", boom)
>       info = calibration_resolve.resolve(repo)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2536/plugins/superheroes/lib/tests/test_mode_selected_core_2536.py:219: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt-2536/plugins/superheroes/lib/calibration_resolve.py:176: in resolve
    return _with_dispatch_fields({
/home/user/wt-2536/plugins/superheroes/lib/calibration_resolve.py:154: in _with_dispatch_fields
    selected = _mode_selected_core(cwd, root) if cwd is not None else None
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2536/plugins/superheroes/lib/calibration_resolve.py:134: in _mode_selected_core
    in_repo, global_path = core_md._core_candidates(cwd, root)
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

cwd = '/tmp/claude-0/pytest-of-root/pytest-9/test_a_candidate_computation_t0/repo'
root = None

    def boom(cwd, root=None):
>       raise core_md.RepoRootUnavailable("git could not be run", git_status=None)
E       store_core.RepoRootUnavailable: git could not be run

/home/user/wt-2536/plugins/superheroes/lib/tests/test_mode_selected_core_2536.py:217: RepoRootUnavailable
_______________ test_a_mode_read_that_raises_leaves_todays_value _______________

repo = '/tmp/claude-0/pytest-of-root/pytest-9/test_a_mode_read_that_raises_l0/repo'
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f045cf51d60>

    def test_a_mode_read_that_raises_leaves_todays_value(repo, monkeypatch):
        # axis: a failure reading the mode never reaches the caller and never changes dispatch_core
        def boom(cwd, root=None, *, persist_backfill=True):
            raise mode_registry.UnknownSchemaVersion("registry newer than this plugin")
        monkeypatch.setattr(mode_registry, "resolve", boom)
>       assert _dispatch_core(repo) == _inrepo_core(repo)
               ^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2536/plugins/superheroes/lib/tests/test_mode_selected_core_2536.py:228: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt-2536/plugins/superheroes/lib/calibration_resolve.py:176: in resolve
    return _with_dispatch_fields({
/home/user/wt-2536/plugins/superheroes/lib/calibration_resolve.py:154: in _with_dispatch_fields
    selected = _mode_selected_core(cwd, root) if cwd is not None else None
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/wt-2536/plugins/superheroes/lib/calibration_resolve.py:137: in _mode_selected_core
    mode = mode_registry.resolve(cwd, root, persist_backfill=False)["mode"]
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

cwd = '/tmp/claude-0/pytest-of-root/pytest-9/test_a_mode_read_that_raises_l0/repo'
root = None, persist_backfill = False

    def boom(cwd, root=None, *, persist_backfill=True):
>       raise mode_registry.UnknownSchemaVersion("registry newer than this plugin")
E       mode_registry.UnknownSchemaVersion: registry newer than this plugin

/home/user/wt-2536/plugins/superheroes/lib/tests/test_mode_selected_core_2536.py:226: UnknownSchemaVersion
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_mode_selected_core_2536.py::test_a_candidate_computation_that_raises_leaves_todays_value
FAILED plugins/superheroes/lib/tests/test_mode_selected_core_2536.py::test_a_mode_read_that_raises_leaves_todays_value
2 failed, 9 passed in 1.22s
```

**Restore:** inverse Edit, the `try:` block and `except Exception: return None` reinstated.
**Restore receipt:** the restored text, quoted back:
```
    try:
        in_repo, global_path = core_md._core_candidates(cwd, root)
        if not (os.path.isfile(in_repo) and os.path.isfile(global_path)):
            return None
        mode = mode_registry.resolve(cwd, root, persist_backfill=False)["mode"]
    except Exception:
        return None
    return in_repo if mode == mode_registry.IN_REPO else global_path
```

**Raw green** (exit 0):
```
...........                                                              [100%]
11 passed in 1.26s
```

---

## G2a the in-repo direction against a disagreeing fallback (review round 1 fix)

The review's test seat found the G2 in-repo test passing without the in-repo override, because its winning layer's
own core was already the in-repo core. The test now lets the global layer win the branch, so the fallback names the
global core. Run by the build session (orchestrator) with the same command; the test unedited between red and green.

**Guarded element:** `_mode_selected_core`, the in-repo arm of the return. Axis: with the mode in-repo, `dispatch_core`
is the in-repo core even when the winning branch's own core is the global one.

**Neutralization:** `    return in_repo if mode == mode_registry.IN_REPO else global_path` changed to
`    return None if mode == mode_registry.IN_REPO else global_path`.

**Raw red:**
```
FAILED plugins/superheroes/lib/tests/test_mode_selected_core_2536.py::test_both_cores_in_repo_mode_dispatches_the_in_repo_core
1 failed, 10 passed in 4.80s
```

**Restore:** inverse Edit. **Restore receipt:** `git status --porcelain plugins/superheroes/lib/calibration_resolve.py`
printed nothing after the restore.

**Raw green:**
```
11 passed in 1.00s
```
