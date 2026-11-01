# C8c WO-B bite-proof — test-only fixes (issue #1862)

> Note (2026-10-31, #2296): owner-machine paths and the name of a consuming project in this record were replaced with neutral placeholders after capture; nothing else changed.

**Provenance:** claude write channel. Each detector was run alone, as one node, from the worktree root:
`scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest '<node>' -q -p no:cacheprovider --tb=short`.
Each neutralization was a targeted edit; each restore was the inverse edit (no `git checkout`, `restore`,
`reset` or `stash`). The `...` marks nothing: every line below is as printed, except where a line says it was
redacted.

**Declared guarded-element set:** B1 (plus its second receipt), B2, B4, B5, B6a, B6b, B7.
B3 (quoting a path in an `sh -c` script) and B8 (a record refresh) are not detector changes and carry no proof.

## Summary

| Element | Axis | Detector | Verdict |
|---|---|---|---|
| B1 | the root conftest leaves `CLAUDE_CODE_REMOTE` unset for a module-scoped fixture and after `monkeypatch.undo()` | `test_root_conftest_cloud_env.py::test_root_conftest_unsets_claude_code_remote_for_module_scope_and_undo` | proven |
| B1, second receipt | the measured-cause run, with the fixture in place, is green | `test_launch_place.py` and two `test_core_md.py` nodes under `CLAUDE_CODE_REMOTE=true` | Unrunnable here |
| B2 | the history time comes off the first slice by exactly the time history took | `test_dispatch_review_cloud_history.py::test_history_time_is_charged_to_the_first_wait_slice_only` | proven |
| B4 | `atomic_write` names UTF-8 itself, whatever the default text encoding is | `test_calibration_paths.py::test_atomic_write_encodes_utf8_when_the_default_text_encoding_is_not` | proven |
| B5 | a path through a symlink to an intermediate directory is classified by where it resolves | `test_calibration_paths.py::test_classification_follows_a_symlink_to_an_intermediate_directory` | proven |
| B5, `..` alias | a `..` segment is collapsed before the layout rule reads the path | `test_calibration_paths.py::test_classification_collapses_a_dotdot_alias_back_to_the_calibration_file` | proven only for both steps neutralized together (shared failure mode, below) |
| B6a | the picker row says the compare comes before `make`, `start`, `judge`, in that order | `test_c8b_doctrine_wording.py::test_the_picker_row_compares_before_make_start_and_judge` | proven |
| B6b | the parked-build row names the three send-back runs in order, then the duplicate window | `test_c8b_doctrine_wording.py::test_the_parked_build_row_names_the_three_runs_and_the_duplicate_window` | proven |
| B7 | a sandbox-tools install that fails once is retried after `apt-get update` | `test_cloud_setup_text.py::test_a_sandbox_tools_install_that_fails_once_is_retried_after_apt_update` | proven |

---

## B1 — `CLAUDE_CODE_REMOTE` never reaches a test

**guarded element:** the session-scoped autouse fixture `_no_cloud_session_env` in the root `conftest.py`.
**axis:** for the whole session, `os.environ` holds no `CLAUDE_CODE_REMOTE` unless a test sets it itself, for a
module-scoped fixture (set up before any function-scoped fixture) and after a test calls `monkeypatch.undo()`.
The detector runs the real root wiring (`pytest.ini`, `conftest.py`, `source_guard.py`) in a throwaway
micro-repository as a child pytest with `CLAUDE_CODE_REMOTE=true`; the nested
`plugins/superheroes/lib/tests/conftest.py` is not in that tree, so the root fixture alone is under test.

**neutralization:** in `conftest.py` the fixture body

```
    original = os.environ.pop("CLAUDE_CODE_REMOTE", None)
    try:
        yield
    finally:
        if original is not None:
            os.environ["CLAUDE_CODE_REMOTE"] = original
```

became `    yield` (the fixture stays declared and does nothing: the same as deleting it).

**raw red** (the child's environment dump inside the assertion message is redacted to `environ({...})`: it
carried the sandbox's proxy settings):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_root_conftest_unsets_claude_code_remote_for_module_scope_and_undo ____
/path/to/home/.superheroes-worktrees/superheroes/issue-1862-c8c-wo-b/plugins/superheroes/lib/tests/test_root_conftest_cloud_env.py:78: in test_root_conftest_unsets_claude_code_remote_for_module_scope_and_undo
    assert proc.returncode == 0, combined
E   AssertionError: FF                                                                       [100%]
E     =================================== FAILURES ===================================
E     ______________ test_module_scoped_fixture_saw_the_variable_unset _______________
E     
E     seen_at_module_scope = 'true'
E     
E         def test_module_scoped_fixture_saw_the_variable_unset(seen_at_module_scope):
E     >       assert seen_at_module_scope is None
E     E       AssertionError: assert 'true' is None
E     
E     test_cloud_env.py:12: AssertionError
E     _______________ test_variable_stays_unset_after_monkeypatch_undo _______________
E     
E     monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x108532c30>
E     
E         def test_variable_stays_unset_after_monkeypatch_undo(monkeypatch):
E             monkeypatch.setenv("CLAUDE_CODE_REMOTE", "set-by-the-test")
E             assert os.environ["CLAUDE_CODE_REMOTE"] == "set-by-the-test"
E             monkeypatch.undo()
E     >       assert "CLAUDE_CODE_REMOTE" not in os.environ
E     E       AssertionError: assert 'CLAUDE_CODE_REMOTE' not in environ({...})
E     E        +  where environ({...}) = os.environ
E     
E     test_cloud_env.py:19: AssertionError
E     =========================== short test summary info ============================
E     FAILED test_cloud_env.py::test_module_scoped_fixture_saw_the_variable_unset
E     FAILED test_cloud_env.py::test_variable_stays_unset_after_monkeypatch_undo - ...
E     2 failed in 0.02s
E     
E   assert 1 == 0
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_root_conftest_cloud_env.py::test_root_conftest_unsets_claude_code_remote_for_module_scope_and_undo
1 failed in 0.49s
```

**restore:** the inverse edit (`    yield` back to the six-line body).

**restore receipt** (`conftest.py` lines 8 to 18 read back after the restore):
```
@pytest.fixture(autouse=True, scope="session")
def _no_cloud_session_env():
    # axis: no CLAUDE_CODE_REMOTE in os.environ for the whole session (module-scoped
    # fixtures and tests that call monkeypatch.undo() included) — see bite-proof
    # record c8c_wo_b.md
    original = os.environ.pop("CLAUDE_CODE_REMOTE", None)
    try:
        yield
    finally:
        if original is not None:
            os.environ["CLAUDE_CODE_REMOTE"] = original
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.38s
```

Edges (per the order): variable absent at start: `pop(..., None)` removes nothing and `original is None`,
so nothing is put back; present as `true` or another value: removed at start, the original value put back at
session end; a test that sets it itself: its own `monkeypatch.setenv` works and its own monkeypatch undoes it
(the child's second test does exactly this); a test that calls `monkeypatch.undo()`: it restores the absence the
session fixture left, so the variable stays unset (the child's second test); a module-scoped fixture: set up
after the session fixture, sees it unset (the child's first test); `pytest-xdist` workers: each worker is its
own pytest session and runs the session-scoped fixture (the scoped self-check ran with `-n auto`).

## B1, second receipt — the measured cause, with the fixture in place

**Unrunnable here.** The command, as the order wrote it:

```
CLAUDE_CODE_REMOTE=true scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_launch_place.py 'plugins/superheroes/lib/tests/test_core_md.py::test_write_deferred_marks_pending_then_written_clears_it' 'plugins/superheroes/lib/tests/test_core_md.py::test_write_show_it_surface_pending_cleared_only_on_real_write' -q -n 4 -p no:cacheprovider
```

**What refused it**, quoted (the environment-variable prefix, run as a command alone):
`This Bash command contains multiple operations. The following part requires approval: CLAUDE_CODE_REMOTE=true scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest ...`
It was not retried in another shape. **The environment that can run it:** the orchestrator's shell on the owner's
machine, from the worktree root, with the fixture in place; the order expects it to pass.
**Substitute evidence produced:** the child-run detector above, which puts `CLAUDE_CODE_REMOTE=true` in a child
pytest's environment and goes red without the fixture and green with it. **Cases it does not discriminate:** the
real `test_launch_place.py` module-scoped `_world(...)` fixture and the two real `test_core_md.py`
`monkeypatch.undo()` tests, which run under the nested `conftest.py` as well; the child tree has no nested
conftest. **Owner of the outstanding receipt:** the orchestrator.

## B2 — the history time is charged to the first slice by exactly what history took

**guarded element:** the `slice_wait = max(0.0, slice_wait - history_spent)` charge in
`engine_dispatch` (the test's fake history charges 100 s through `shim.offset`). **axis:** the first
supervise slice is `MAX_SYNC_WAIT - 100` exactly and every later slice is `MAX_SYNC_WAIT` exactly. The shim's
clock is now a fixed base (1000.0) plus the offset the test pushes; `sleep` neither waits nor advances it,
because the wait loop takes each slice's deadline fresh after its sleep, so a sleep cannot change a slice.
The three slice assertions are one exact list equality: `slices == [full - 100, full, full]`.

**neutralization:** in the test's fake, `        shim.offset += 100.0 ` became `        shim.offset += 99.0 ` (the code
under test is charged 99 s of history instead of 100 s).

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_history_time_is_charged_to_the_first_wait_slice_only ___________
/path/to/home/.superheroes-worktrees/superheroes/issue-1862-c8c-wo-b/plugins/superheroes/lib/tests/test_dispatch_review_cloud_history.py:247: in test_history_time_is_charged_to_the_first_wait_slice_only
    assert slices == [full - 100, full, full], slices
E   AssertionError: [441.0, 540.0, 540.0]
E   assert [441.0, 540.0, 540.0] == [440, 540, 540]
E     
E     At index 0 diff: 441.0 != 440
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_dispatch_review_cloud_history.py::test_history_time_is_charged_to_the_first_wait_slice_only
1 failed in 1.34s
```

**old tolerance:** `abs(slices[0] - (full - 100)) < 5` would **not** have caught this: `abs(441 - 440) = 1 < 5`.
The old assertion also depended on the runner's speed, since the shim added real elapsed time to the clock.

**restore:** the inverse edit (`99.0` back to `100.0`).

**restore receipt** (`test_dispatch_review_cloud_history.py` line 220 read back):
`        shim.offset += 100.0                             # and history took about 100 s`

**raw green:**
```
.                                                                        [100%]
1 passed in 1.49s
```

## B4 — `atomic_write` writes UTF-8 whatever the default text encoding is

**guarded element:** `os.fdopen(fd, "w", encoding="utf-8")` in `store_core.atomic_write`
(`store_core.py:486`). **axis:** the bytes on disk are UTF-8 even when the default text encoding is not.
**Mechanism:** the test replaces the `os` that `store_core` sees (`monkeypatch.setattr(sc, "os", ...)`) with a
proxy that delegates every name to the real `os` except `fdopen`, which fills in `encoding="latin-1"` when the
caller named none. A missing `encoding="utf-8"` then writes latin-1 or raises on the em dash; nothing depends on
the machine's locale. The test also asserts the proxy saw exactly one open with `encoding == "utf-8"`.

**neutralization:** `        with os.fdopen(fd, "w", encoding="utf-8") as fh:` became
`        with os.fdopen(fd, "w") as fh:` in `plugins/superheroes/lib/store_core.py`.

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_atomic_write_encodes_utf8_when_the_default_text_encoding_is_not _____
/path/to/home/.superheroes-worktrees/superheroes/issue-1862-c8c-wo-b/plugins/superheroes/lib/tests/test_calibration_paths.py:275: in test_atomic_write_encodes_utf8_when_the_default_text_encoding_is_not
    sc.atomic_write(str(path), "café — ok\n")
/path/to/home/.superheroes-worktrees/superheroes/issue-1862-c8c-wo-b/plugins/superheroes/lib/store_core.py:487: in atomic_write
    fh.write(text)
E   UnicodeEncodeError: 'latin-1' codec can't encode character '—' in position 5: ordinal not in range(256)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_paths.py::test_atomic_write_encodes_utf8_when_the_default_text_encoding_is_not
1 failed in 0.13s
```

**restore:** the inverse edit.

**restore receipt** (`grep -n 'os.fdopen' plugins/superheroes/lib/store_core.py`, then `git status --porcelain`
listing no `store_core.py`):
`486:        with os.fdopen(fd, "w", encoding="utf-8") as fh:`

**raw green:**
```
.                                                                        [100%]
1 passed in 0.12s
```

## B5 — classification through a directory alias

**Expected answers, from the module docstring and `_classify`:** `<root>/projects/<key>/registry.json` is a
calibration file; `<root>/projects/<key>/reviews/x.json` is not (only `registry.json`, `meta.json`,
`doc-policy.json`, `config/*.md`, `permission/rules.json` are). `is_calibration_path` classifies both the
resolved path and the path as given, so a file "reached through a symlinked directory" is caught. The alias
`tmp_path/alias -> tmp_path/store/projects/k` resolves to `projects/k`, so `alias/registry.json` is True and
`alias/reviews/x.json` is False. The code returned exactly these; nothing contradicts its docstring.

**guarded element:** `real = os.path.realpath(given)` in `calibration_paths.is_calibration_path`
(`calibration_paths.py:67`). **axis:** a path whose own name looks like no calibration location is classified by
where it resolves, not by its lexical path.

**neutralization:** `        real = os.path.realpath(given)` became `        real = given`.

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_classification_follows_a_symlink_to_an_intermediate_directory ______
/path/to/home/.superheroes-worktrees/superheroes/issue-1862-c8c-wo-b/plugins/superheroes/lib/tests/test_calibration_paths.py:107: in test_classification_follows_a_symlink_to_an_intermediate_directory
    assert cp.is_calibration_path(str(alias / "registry.json")) is True
E   AssertionError: assert False is True
E    +  where False = <function is_calibration_path at 0x106be3ec0>('/private/tmp/claude-501/pytest-of-zwrose/pytest-1576/test_classification_follows_a_0/alias/registry.json')
E    +    where <function is_calibration_path at 0x106be3ec0> = cp.is_calibration_path
E    +    and   '/private/tmp/claude-501/pytest-of-zwrose/pytest-1576/test_classification_follows_a_0/alias/registry.json' = str((PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1576/test_classification_follows_a_0/alias') / 'registry.json'))
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_paths.py::test_classification_follows_a_symlink_to_an_intermediate_directory
1 failed in 0.17s
```

**restore:** the inverse edit.

**restore receipt** (`calibration_paths.py` lines 65 to 70 read back, and `git status --porcelain` listing no
`calibration_paths.py`):
```
    given = os.path.abspath(path)
    try:
        real = os.path.realpath(given)
    except (OSError, ValueError):
        real = given
    return _classify(real) or _classify(given)
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.12s
```

### B5, the `..` alias — a shared failure mode

`store/projects/k/../k/registry.json` (expected True: it is the calibration file). The classifier has no step
that handles `..` separately from the realpath step: `os.path.abspath(path)` (line 65) collapses `..`
lexically and `os.path.realpath` (line 67) also resolves it, so **either step alone keeps the test green** and
only losing both reads the lexical `..` path. Both neutralizations were measured:

- `real = given` alone (realpath step off, abspath on): the `..` test **passed** (`1 passed in 0.12s`), as the
  intermediate-alias test above went red.
- `real = given` and `    given = os.path.abspath(path)` became `    given = path` together: red:
```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_classification_collapses_a_dotdot_alias_back_to_the_calibration_file ___
/path/to/home/.superheroes-worktrees/superheroes/issue-1862-c8c-wo-b/plugins/superheroes/lib/tests/test_calibration_paths.py:118: in test_classification_collapses_a_dotdot_alias_back_to_the_calibration_file
    assert cp.is_calibration_path(path) is True
E   AssertionError: assert False is True
E    +  where False = <function is_calibration_path at 0x108f6fec0>('/private/tmp/claude-501/pytest-of-zwrose/pytest-1578/test_classification_collapses_0/store/projects/k/../k/registry.json')
E    +    where <function is_calibration_path at 0x108f6fec0> = cp.is_calibration_path
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_calibration_paths.py::test_classification_collapses_a_dotdot_alias_back_to_the_calibration_file
1 failed in 0.13s
```

**restore:** both inverse edits (`    given = path` back to `    given = os.path.abspath(path)`; the `try:` body
`        real = given` back to `        real = os.path.realpath(given)`). **restore receipt:** the six lines quoted
in the B5 entry above, read back after both restores. **raw green** (the `..` test after the restore):
```
.                                                                        [100%]
1 passed in 0.12s
```

## B6a — the picker row's order

**guarded element:** the ledger row `Cloud environment picker reader` in `LEDGERS.md`, text
`before `make`, before `start` and before `judge``. **axis:** the compare comes before each of the three
commands, in the order make, start, judge. The detector pins each `before `verb`` phrase (the row's earlier
"before and after the pick" would satisfy a bare index of `before`, so a bare index would bite on nothing).

**neutralization:** `before `make`, before `start` and before `judge`` became
`before `judge`, before `start` and before `make``.

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_the_picker_row_compares_before_make_start_and_judge ___________
/path/to/home/.superheroes-worktrees/superheroes/issue-1862-c8c-wo-b/plugins/superheroes/lib/tests/test_c8b_doctrine_wording.py:66: in test_the_picker_row_compares_before_make_start_and_judge
    assert places == sorted(places), places
E   AssertionError: [434, 415, 399]
E   assert [434, 415, 399] == [399, 415, 434]
E     
E     At index 0 diff: 434 != 399
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c8b_doctrine_wording.py::test_the_picker_row_compares_before_make_start_and_judge
1 failed in 0.08s
```

**restore:** the inverse edit.

**restore receipt** (`grep -o` over `LEDGERS.md`, and `git status --porcelain LEDGERS.md` empty):
`before `make`, before `start` and before `judge``

**raw green:**
```
.                                                                        [100%]
1 passed in 0.08s
```

## B6b — the parked-build row's order

**guarded element:** the ledger row `Parked cloud build recovery` in `LEDGERS.md`. **axis:** the three
`send-back` runs come in the order a parked build meets them (after a confirmation of a renewed pass, after a
passed check, at each gardening pass), and the accepted one-duplicate-message window is named after them. The
claim depends on that sequence: it is the order in which a parked build is sent back, and the window is the
cost of the sequence.

**neutralization:** `after a confirmation of a renewed pass, after a passed check and at each gardening pass`
became `at each gardening pass, after a passed check and after a confirmation of a renewed pass`.

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_the_parked_build_row_names_the_three_runs_and_the_duplicate_window ____
/path/to/home/.superheroes-worktrees/superheroes/issue-1862-c8c-wo-b/plugins/superheroes/lib/tests/test_c8b_doctrine_wording.py:91: in test_the_parked_build_row_names_the_three_runs_and_the_duplicate_window
    assert places == sorted(places), places
E   AssertionError: [424, 399, 375, 767]
E   assert [424, 399, 375, 767] == [375, 399, 424, 767]
E     
E     At index 0 diff: 424 != 375
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c8b_doctrine_wording.py::test_the_parked_build_row_names_the_three_runs_and_the_duplicate_window
1 failed in 0.08s
```

**restore:** the inverse edit.

**restore receipt** (`grep -o` over `LEDGERS.md`, and `git status --porcelain LEDGERS.md` empty):
`after a confirmation of a renewed pass, after a passed check and at each gardening pass`

**raw green:**
```
.                                                                        [100%]
1 passed in 0.07s
```

## B7 — a sandbox-tools install that fails once is retried after `apt-get update`

**guarded element:** the `|| { apt-get update && apt-get install -y %s; }` retry in the sandbox-tools line of
`cloud_setup_text.py` (line 335). **axis:** the first `apt-get install` failing does not fail the step: the
script runs `apt-get update` once, then installs again, exits 0, and logs `sandbox tools ok`. The stub's
`apt-get install` fails the first time and succeeds after (a counter file); `update` always succeeds; the
detector asserts the exact `apt-get` call sequence `install, update, install`.

**neutralization:** in `plugins/superheroes/lib/cloud_setup_text.py`
```
        '  apt-get install -y %s || { apt-get update && apt-get install -y %s; } \\'
        % (SANDBOX_TOOL_PACKAGES, SANDBOX_TOOL_PACKAGES),
```
became
```
        '  apt-get install -y %s || false \\'
        % SANDBOX_TOOL_PACKAGES,
```

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_a_sandbox_tools_install_that_fails_once_is_retried_after_apt_update ___
/path/to/home/.superheroes-worktrees/superheroes/issue-1862-c8c-wo-b/plugins/superheroes/lib/tests/test_cloud_setup_text.py:357: in test_a_sandbox_tools_install_that_fails_once_is_retried_after_apt_update
    assert "sandbox tools ok" in setup_log
E   AssertionError: assert 'sandbox tools ok' in 'reviewer cli ok\nduplication checker ok\nsandbox tools FAILED\npinned python ok\ncat: /private/tmp/claude-501/pytest-...a_sandbox_tools_install_t0/opt/src/plugins/superheroes/version.txt: No such file or directory\nplugin ok \nsetup end\n'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_a_sandbox_tools_install_that_fails_once_is_retried_after_apt_update
1 failed in 1.05s
```

**restore:** the inverse edit.

**restore receipt** (`grep -n 'apt-get install -y %s' plugins/superheroes/lib/cloud_setup_text.py`, and
`git status --porcelain` listing no `cloud_setup_text.py`):
`335:        '  apt-get install -y %s || { apt-get update && apt-get install -y %s; } \\'`

**raw green:**
```
.                                                                        [100%]
1 passed in 1.10s
```
