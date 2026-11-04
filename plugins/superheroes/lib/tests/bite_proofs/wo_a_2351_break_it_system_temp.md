# Work order A (#2351) bite-proof: a break-it run's default per-run folder is the system temp folder

**Provenance:** claude / sonnet-5.5 (implementer, order `wo_a_2351_break_it_system_temp`), maker family anthropic. Production under proof: `plugins/superheroes/lib/break_it.py` (`_scratch_folder`, `_run_in_working_copy`, `_execute`). Tests: `plugins/superheroes/lib/tests/test_break_it_system_temp_2351.py`, and the re-pointed `test_break_it_review_round2_2210.py` (G1) and `test_break_it_working_copy_2210.py` (E9).

Declared guarded-element set (from the order): **E1**, **E2**, **E3**, **E4**, **E5**. Each was neutralized by one targeted edit (the Edit tool, exact-text match), only its proving nodes run by exact node id (never `-k`), the inverse edit applied, and the same ids run again. No `git checkout`, `git restore`, `git reset` or `git stash` was used.

## Guarded elements

| ID | Guarded element | Axis | Proving nodes |
|---|---|---|---|
| E1 | the default base is the system temp folder, `break_it.py` `_scratch_folder` (`base = os.path.abspath(tempfile.gettempdir())`) | with no `scratch`, the per-run folder is not inside the worktree's git directory, so a repository's own base-temp guard lets a kept check certify | `test_break_it_system_temp_2351.py::test_dod_a_kept_check_in_a_linked_worktree_whose_repository_refuses_an_in_repository_base_temp_is_kept`, `test_break_it_working_copy_2210.py::test_e9_without_a_scratch_the_temp_folder_lies_under_the_system_temp_folder_and_is_gone_afterwards`, `test_break_it_review_round2_2210.py::test_g1_the_default_scratch_folder_is_the_system_temp_folder_for_the_main_and_a_linked_worktree` |
| E2 | the outside-every-repository check, `_scratch_folder` (`if done.returncode != 0 and "not a git repository" in ...:`) | a system temp folder inside a work tree or a git directory reads not-run `scratch-unresolved` | `test_break_it_system_temp_2351.py::test_inrepo_a_system_temp_folder_inside_the_work_tree_is_not_run_scratch_unresolved`, `::test_a_system_temp_folder_inside_a_git_directory_is_not_run_scratch_unresolved` |
| E3 | `gettempdir()` raising, `_scratch_folder` (`try`/`except (OSError, ValueError)` around it) | an unresolvable system temp folder reads not-run `scratch-unresolved`, never a `run-error` | `test_break_it_system_temp_2351.py::test_unresolvable_a_system_temp_folder_that_cannot_be_resolved_is_not_run_scratch_unresolved` |
| E4 | the default per-run folder's mode, `_run_in_working_copy` (`mode=0o700 if scratch is None else None`) | the default per-run folder is `0700` | `test_break_it_system_temp_2351.py::test_mode_the_default_per_run_folder_is_private_and_a_given_scratch_folder_keeps_the_plain_mkdir` |
| E5 | the caller-given `scratch` is honoured, `_scratch_folder` (`if scratch is not None:`) | a given session folder holds the per-run folder | `test_break_it_system_temp_2351.py::test_sibling_an_explicit_scratch_holds_the_per_run_folder_and_it_is_gone_afterwards` |
| E6 | the C-locale pin on the outside-every-repository probe, `_scratch_folder` (`_clean_env({"LC_ALL": "C", "LANGUAGE": "C"})`) | a git that translates its diagnostics still proves an outside-every-repository system temp folder | `test_break_it_system_temp_2351.py::test_locale_a_translated_git_still_proves_the_system_temp_folder_outside_every_repository` |

## Disclosures

- Every element went red under its neutralization (pytest exit 1) and green after the restore (exit 0).
- **Refused command, so no byte comparison with the saved copy.** The order asked for `cmp` of `break_it.py` against a copy at `/tmp/wo-a-2351-fixed.py` after each restore. The first such call, `cmp plugins/superheroes/lib/break_it.py /tmp/wo-a-2351-fixed.py && echo "cmp: identical to fixed" && scripts/pinned-python ... (the E1 green run)`, was refused: `cmp in '/tmp/wo-a-2351-fixed.py' was blocked. For security, Claude Code may only compare files from the allowed working directories for this session: '/home/user/wt-2351'.` It was not retried in any other form, and no restore was compared byte for byte. The restore receipt of each element is instead (1) `git diff --stat -- plugins/superheroes/lib/break_it.py` printed after the inverse edit, which read `1 file changed, 31 insertions(+), 22 deletions(-)` before the first neutralization and after every restore, and (2) the restored lines quoted back from the file. That is weaker than `cmp`: an equal stat does not prove equal bytes. The orchestrator can compare against the committed-plus-diff state.
- The E1 red of `test_dod_a_kept_check_in_a_linked_worktree_...` was captured twice: first with the test's original assertion message (`result` only, which pytest elides), then, after the failure message was widened to carry the nested run's output, with that version. The test's assertions did not change; only the message did. The first three-node red below used the earlier message. The green runs all used the final test.
- The E1 neutralization is the old default body restored in front of the new one: `import store_core` and `return os.path.join(store_core.get_worktree_gitdir(root, run=lambda cwd, *a: store_core.run_git_result(cwd, *a, env=_clean_env())), "superheroes"), None`. The nested pytest in the T-DoD red ends `1 error in 0.02s`, an error at setup, which is the fixture guard refusing a base temp inside the linked worktree's git directory. The record's `outcome` there is `failing` (the order's name for it is `kept-failing`).
- The E4 test fixes the umask to `0o022` for the two runs and restores it, so a plain `mkdir` (`0755`) differs from the private mode; the given-`scratch` folder is asserted `0o777 & ~0o022`.
- **Guarded edges with no neutralization (not in the declared set), listed unproven:** (a) git that cannot start (`OSError`) or times out (`subprocess.TimeoutExpired`) in the system temp folder (`::test_git_that_cannot_start_or_times_out_in_the_system_temp_folder_is_not_run_scratch_unresolved`, two parametrizations); (b) a `scratch` that is not an existing directory (`::test_a_scratch_that_is_not_an_existing_directory_is_not_run_scratch_unresolved`, behaviour unchanged from before); (c) the ignored `GIT_DIR` (`test_break_it_review_round2_2210.py::test_g1_the_resolution_ignores_a_git_dir_routed_through_the_environment`, carried by `_git`'s `_clean_env`); (d) the `errors="replace"` decode of git's stderr. These tests pass; none was shown to go red.
- Limit, since closed by E6: git's message is matched as English text (`not a git repository`). As the order first routed the call through `_git`, which does not set `LC_ALL`, a localized git could never match and failed closed to `scratch-unresolved`. The review's round-1 finding "Pin Git's locale before matching its English diagnostic" was fixed by running that one git call under `LC_ALL=C` / `LANGUAGE=C` (`_git_env`), proven as E6 below.
- Redaction: none needed; local paths are kept as printed, no secret, token or private URL appears. Each capture is under 32 KiB and all together under 128 KiB, so none is written off-repo. The `UV_NATIVE_TLS` deprecation warning line that `scripts/pinned-python` prints is not shown; everything else is verbatim (default `--tb`, no filter).
- The command shape is `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest <exact node ids> -q`, followed by `echo "pytest exit: $?"`.

---

## E1: the default base is the system temp folder

- **axis:** with no `scratch`, the per-run folder is not inside the worktree's git directory

**neutralization** (`plugins/superheroes/lib/break_it.py`, in `_scratch_folder`, inserted before the `try:` that calls `gettempdir()`):
```diff
+    import store_core
+    return os.path.join(store_core.get_worktree_gitdir(root, run=lambda cwd, *a: store_core.run_git_result(cwd, *a, env=_clean_env())), "superheroes"), None
     try:
         base = os.path.abspath(tempfile.gettempdir())
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_system_temp_2351.py::test_dod_a_kept_check_in_a_linked_worktree_whose_repository_refuses_an_in_repository_base_temp_is_kept plugins/superheroes/lib/tests/test_break_it_working_copy_2210.py::test_e9_without_a_scratch_the_temp_folder_lies_under_the_system_temp_folder_and_is_gone_afterwards plugins/superheroes/lib/tests/test_break_it_review_round2_2210.py::test_g1_the_default_scratch_folder_is_the_system_temp_folder_for_the_main_and_a_linked_worktree -q
```

**raw red** (exit 1; the T-DoD message is the earlier, elided one):
```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_dod_a_kept_check_in_a_linked_worktree_whose_repository_refuses_an_in_repository_base_temp_is_kept _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-1/test_dod_a_kept_check_in_a_lin0')
systmp = PosixPath('/tmp/claude-0/pytest-of-root/pytest-1/test_dod_a_kept_check_in_a_lin0/systmp')

    def test_dod_a_kept_check_in_a_linked_worktree_whose_repository_refuses_an_in_repository_base_temp_is_kept(tmp_path, systmp):
        main = tmp_path / "fx"
        main.mkdir()
        _git(main, "init", "-q")
        _git(main, "symbolic-ref", "HEAD", "refs/heads/main")
        TB._write(main, "conftest.py", GUARD_CONFTEST)
        TB._write(main, "pytest.ini", "[pytest]\n")
        TB._write(main, "README.md", "fixture\n")
        base = _commit(main, "base")
        linked = tmp_path / "fx-linked"
        _git(main, "worktree", "add", "-q", "-b", "feature", str(linked))
        TB._write(linked, TEST_PATH, PASSING_TEST)
        head = _commit(linked, "head")
        record = {"path": TEST_PATH, "command": "%s -m pytest -q -p no:cacheprovider %s" % (PY, TEST_PATH),
                  "sha256": hashlib.sha256(PASSING_TEST.encode("utf-8")).hexdigest()}
        result = break_it.check_kept(str(linked), base, head, record)
>       assert result["outcome"] == "kept", result
E       AssertionError: {'path': 'tests/test_k.py', 'outcome': 'failing', 'reason': None, 'run': {'schema': 'break-it-run/1', 'role': 'test-ro...', 'command': '/root/.cache/uv/builds-v0/.tmpfFsoAa/bin/python -m pytest -q -p no:cacheprovider tests/test_k.py', ...}}
E       assert 'failing' == 'kept'
E         
E         - kept
E         + failing

/home/user/wt-2351/plugins/superheroes/lib/tests/test_break_it_system_temp_2351.py:144: AssertionError
_ test_e9_without_a_scratch_the_temp_folder_lies_under_the_system_temp_folder_and_is_gone_afterwards _

repo = PosixPath('/tmp/claude-0/pytest-of-root/pytest-1/test_e9_without_a_scratch_the_0/repo')
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-1/test_e9_without_a_scratch_the_0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7ffa45a0a2a0>

    def test_e9_without_a_scratch_the_temp_folder_lies_under_the_system_temp_folder_and_is_gone_afterwards(repo, tmp_path, monkeypatch):
        systmp = tmp_path / "systmp"
        systmp.mkdir()
        monkeypatch.setattr(tempfile, "tempdir", str(systmp))
        record = _run(repo, "tests/test_t.py", PRINT_TMP)
        assert record["outcome"] == "passed", record
        printed = record["output"].split("TMPDIR=", 1)[1].splitlines()[0]
        base = os.path.realpath(str(systmp))
>       assert os.path.realpath(os.path.dirname(printed)) == base, (printed, base)
E       AssertionError: ('/tmp/claude-0/pytest-of-root/pytest-1/test_e9_without_a_scratch_the_0/repo/.git/superheroes/break-it-tmp-eb938c82ff924d859359c12b1650d12f', '/tmp/claude-0/pytest-of-root/pytest-1/test_e9_without_a_scratch_the_0/systmp')
E       assert '/tmp/claude-...t/superheroes' == '/tmp/claude-..._the_0/systmp'
E         
E         Skipping 60 identical leading characters in diff, use -v to show
E         - tch_the_0/systmp
E         + tch_the_0/repo/.git/superheroes

/home/user/wt-2351/plugins/superheroes/lib/tests/test_break_it_working_copy_2210.py:398: AssertionError
_ test_g1_the_default_scratch_folder_is_the_system_temp_folder_for_the_main_and_a_linked_worktree _

repo = PosixPath('/tmp/claude-0/pytest-of-root/pytest-1/test_g1_the_default_scratch_fo0/repo')
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-1/test_g1_the_default_scratch_fo0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7ffa45a087a0>

    def test_g1_the_default_scratch_folder_is_the_system_temp_folder_for_the_main_and_a_linked_worktree(repo, tmp_path, monkeypatch):
        systmp = _private_system_temp(monkeypatch, tmp_path)
        base, reason = break_it._scratch_folder(str(repo), None)
        assert reason is None
>       assert base == os.path.abspath(tempfile.gettempdir()) == systmp
E       AssertionError: assert '/tmp/claude-...t/superheroes' == '/tmp/claude-...ch_fo0/systmp'
E         
E         Skipping 60 identical leading characters in diff, use -v to show
E         - ratch_fo0/systmp
E         + ratch_fo0/repo/.git/superheroes

/home/user/wt-2351/plugins/superheroes/lib/tests/test_break_it_review_round2_2210.py:139: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_system_temp_2351.py::test_dod_a_kept_check_in_a_linked_worktree_whose_repository_refuses_an_in_repository_base_temp_is_kept
FAILED plugins/superheroes/lib/tests/test_break_it_working_copy_2210.py::test_e9_without_a_scratch_the_temp_folder_lies_under_the_system_temp_folder_and_is_gone_afterwards
FAILED plugins/superheroes/lib/tests/test_break_it_review_round2_2210.py::test_g1_the_default_scratch_folder_is_the_system_temp_folder_for_the_main_and_a_linked_worktree
3 failed in 1.88s
pytest exit: 1
```

**raw red, T-DoD alone, with the widened message** (exit 1; same neutralization; only the failure-message tail shown by pytest, the test body as above):
```
>       assert result["outcome"] == "kept", (result["outcome"], run.get("outcome"), run.get("reason"), run.get("output"))
E       AssertionError: ('failing', 'failed', None, 'E                                                                        [100%]
E         ========... /tmp/claude-0/pytest-of-roo...
E         1 error in 0.02s
E         
E         working-directory net skipped: /proc names another PID namespace')
E       assert 'failing' == 'kept'
E         
E         - kept
E         + failing

/home/user/wt-2351/plugins/superheroes/lib/tests/test_break_it_system_temp_2351.py:145: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_system_temp_2351.py::test_dod_a_kept_check_in_a_linked_worktree_whose_repository_refuses_an_in_repository_base_temp_is_kept
1 failed in 1.47s
pytest exit: 1
```
(The `/proc names another PID namespace` line is this sandbox's note that the working-directory net was skipped; it is not part of the failure.)

**restore:** the inverse edit (the two inserted lines removed, so `try:` / `base = os.path.abspath(tempfile.gettempdir())` follow the `scratch` block again).

**restore receipt:** `git diff --stat -- plugins/superheroes/lib/break_it.py` after the inverse edit (`cmp` against the saved copy was refused, see Disclosures):
```
 plugins/superheroes/lib/break_it.py | 53 ++++++++++++++++++++++---------------
 1 file changed, 31 insertions(+), 22 deletions(-)
```
restored lines, quoted back from the file:
```
    try:
        base = os.path.abspath(tempfile.gettempdir())
    except (OSError, ValueError):
        return None, "scratch-unresolved"
    try:
        done = _git(base, "rev-parse", "--show-toplevel")
```

**raw green** (exit 0), same command:
```
...                                                                      [100%]
3 passed in 1.97s
pytest exit: 0
```

---

## E2: the outside-every-repository check

- **axis:** a system temp folder inside a work tree or a git directory reads not-run `scratch-unresolved`

**neutralization** (`plugins/superheroes/lib/break_it.py`, `_scratch_folder`):
```diff
-    if done.returncode != 0 and "not a git repository" in (done.stderr or b"").decode("utf-8", errors="replace"):
+    if True:
         return base, None
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_system_temp_2351.py::test_inrepo_a_system_temp_folder_inside_the_work_tree_is_not_run_scratch_unresolved plugins/superheroes/lib/tests/test_break_it_system_temp_2351.py::test_a_system_temp_folder_inside_a_git_directory_is_not_run_scratch_unresolved -q
```

**raw red** (exit 1):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_inrepo_a_system_temp_folder_inside_the_work_tree_is_not_run_scratch_unresolved _

repo = PosixPath('/tmp/claude-0/pytest-of-root/pytest-5/test_inrepo_a_system_temp_fold0/repo')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fc5d4d53200>

    def test_inrepo_a_system_temp_folder_inside_the_work_tree_is_not_run_scratch_unresolved(repo, monkeypatch):
        (repo / ".git" / "info" / "exclude").write_text("inner-tmp/\n")
        inner = repo / "inner-tmp"
        inner.mkdir()
        monkeypatch.setattr(tempfile, "tempdir", str(inner))
        record = _run(repo, "tests/test_t.py", PRINT_TMP)
>       assert (record["outcome"], record["reason"]) == ("not-run", "scratch-unresolved"), record
E       AssertionError: {'schema': 'break-it-run/1', 'role': 'test-role', 'path': 'tests/test_t.py', 'command': '/root/.cache/uv/builds-v0/.tmp85X3fk/bin/python tests/test_t.py', ...}
E       assert ('passed', None) == ('not-run', '...h-unresolved')
E         
E         At index 0 diff: 'passed' != 'not-run'
E         Use -v to get more diff

/home/user/wt-2351/plugins/superheroes/lib/tests/test_break_it_system_temp_2351.py:180: AssertionError
_ test_a_system_temp_folder_inside_a_git_directory_is_not_run_scratch_unresolved _

repo = PosixPath('/tmp/claude-0/pytest-of-root/pytest-5/test_a_system_temp_folder_insi0/repo')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fc5d4d52f30>

    def test_a_system_temp_folder_inside_a_git_directory_is_not_run_scratch_unresolved(repo, monkeypatch):
        # git answers "must be run in a work tree" there: not the one answer that proves the folder is outside every repository
        inner = repo / ".git" / "inner-tmp"
        inner.mkdir()
        monkeypatch.setattr(tempfile, "tempdir", str(inner))
        record = _run(repo, "tests/test_t.py", PRINT_TMP)
>       assert (record["outcome"], record["reason"]) == ("not-run", "scratch-unresolved"), record
E       AssertionError: {'schema': 'break-it-run/1', 'role': 'test-role', 'path': 'tests/test_t.py', 'command': '/root/.cache/uv/builds-v0/.tmp85X3fk/bin/python tests/test_t.py', ...}
E       assert ('passed', None) == ('not-run', '...h-unresolved')
E         
E         At index 0 diff: 'passed' != 'not-run'
E         Use -v to get more diff

/home/user/wt-2351/plugins/superheroes/lib/tests/test_break_it_system_temp_2351.py:191: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_system_temp_2351.py::test_inrepo_a_system_temp_folder_inside_the_work_tree_is_not_run_scratch_unresolved
FAILED plugins/superheroes/lib/tests/test_break_it_system_temp_2351.py::test_a_system_temp_folder_inside_a_git_directory_is_not_run_scratch_unresolved
2 failed in 0.80s
pytest exit: 1
```

**restore:** the inverse edit (`if True:` back to the `done.returncode != 0 and "not a git repository" in ...` test).

**restore receipt:** `git diff --stat -- plugins/superheroes/lib/break_it.py`:
```
 plugins/superheroes/lib/break_it.py | 53 ++++++++++++++++++++++---------------
 1 file changed, 31 insertions(+), 22 deletions(-)
```
restored line (`grep -n` of the file):
```
1419:    if done.returncode != 0 and "not a git repository" in (done.stderr or b"").decode("utf-8", errors="replace"):
```

**raw green** (exit 0), same command:
```
..                                                                       [100%]
2 passed in 0.46s
pytest exit: 0
```

---

## E3: `gettempdir()` raising reads `scratch-unresolved`

- **axis:** an unresolvable system temp folder reads not-run `scratch-unresolved`, never a `run-error`

**neutralization** (`plugins/superheroes/lib/break_it.py`, `_scratch_folder`):
```diff
-    try:
-        base = os.path.abspath(tempfile.gettempdir())
-    except (OSError, ValueError):
-        return None, "scratch-unresolved"
+    base = os.path.abspath(tempfile.gettempdir())
     try:
         done = _git(base, "rev-parse", "--show-toplevel")
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_system_temp_2351.py::test_unresolvable_a_system_temp_folder_that_cannot_be_resolved_is_not_run_scratch_unresolved -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_unresolvable_a_system_temp_folder_that_cannot_be_resolved_is_not_run_scratch_unresolved _

repo = PosixPath('/tmp/claude-0/pytest-of-root/pytest-7/test_unresolvable_a_system_tem0/repo')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7efe844080b0>

    def test_unresolvable_a_system_temp_folder_that_cannot_be_resolved_is_not_run_scratch_unresolved(repo, monkeypatch):
        def gone():
            raise FileNotFoundError("no usable temporary directory")
    
        monkeypatch.setattr(tempfile, "gettempdir", gone)
        record = _run(repo, "tests/test_t.py", PRINT_TMP)
>       assert (record["outcome"], record["reason"]) == ("not-run", "scratch-unresolved"), record
E       AssertionError: {'schema': 'break-it-run/1', 'role': 'test-role', 'path': 'tests/test_t.py', 'command': '/root/.cache/uv/builds-v0/.tmp0Zho5e/bin/python tests/test_t.py', ...}
E       assert ('not-run', 'run-error') == ('not-run', '...h-unresolved')
E         
E         At index 1 diff: 'run-error' != 'scratch-unresolved'
E         Use -v to get more diff

/home/user/wt-2351/plugins/superheroes/lib/tests/test_break_it_system_temp_2351.py:205: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_system_temp_2351.py::test_unresolvable_a_system_temp_folder_that_cannot_be_resolved_is_not_run_scratch_unresolved
1 failed in 0.31s
pytest exit: 1
```

**restore:** the inverse edit (the `try`/`except (OSError, ValueError)` put back around `gettempdir()`).

**restore receipt:** `git diff --stat -- plugins/superheroes/lib/break_it.py`:
```
 plugins/superheroes/lib/break_it.py | 53 ++++++++++++++++++++++---------------
 1 file changed, 31 insertions(+), 22 deletions(-)
```
restored lines (`grep -n -A3` of the file):
```
1411:        base = os.path.abspath(tempfile.gettempdir())
1412-    except (OSError, ValueError):
1413-        return None, "scratch-unresolved"
1414-    try:
```

**raw green** (exit 0), same command:
```
.                                                                        [100%]
1 passed in 0.28s
pytest exit: 0
```

---

## E4: the default per-run folder is `0700`

- **axis:** the default per-run folder is private

**neutralization** (`plugins/superheroes/lib/break_it.py`, `_run_in_working_copy`):
```diff
-                              mode=0o700 if scratch is None else None)
+                              mode=None)
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_system_temp_2351.py::test_mode_the_default_per_run_folder_is_private_and_a_given_scratch_folder_keeps_the_plain_mkdir -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_mode_the_default_per_run_folder_is_private_and_a_given_scratch_folder_keeps_the_plain_mkdir _

repo = PosixPath('/tmp/claude-0/pytest-of-root/pytest-9/test_mode_the_default_per_run_0/repo')
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-9/test_mode_the_default_per_run_0')
systmp = PosixPath('/tmp/claude-0/pytest-of-root/pytest-9/test_mode_the_default_per_run_0/systmp')

    def test_mode_the_default_per_run_folder_is_private_and_a_given_scratch_folder_keeps_the_plain_mkdir(repo, tmp_path, systmp):
        session = tmp_path / "session"
        session.mkdir()
        old_umask = os.umask(0o022)  # fixed, so a plain mkdir (0755) differs from the private one (0700)
        try:
            default = _run(repo, "tests/test_t.py", PRINT_TMP)
            given = _run(repo, "tests/test_t.py", PRINT_TMP, scratch=str(session))
        finally:
            os.umask(old_umask)
        assert default["outcome"] == "passed" and given["outcome"] == "passed", (default, given)
        assert os.path.realpath(os.path.dirname(_printed(default, "TMPDIR"))) == os.path.realpath(str(systmp))
>       assert _printed(default, "MODE") == "700"
E       AssertionError: assert '755' == '700'
E         
E         - 700
E         + 755

/home/user/wt-2351/plugins/superheroes/lib/tests/test_break_it_system_temp_2351.py:232: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_system_temp_2351.py::test_mode_the_default_per_run_folder_is_private_and_a_given_scratch_folder_keeps_the_plain_mkdir
1 failed in 0.71s
pytest exit: 1
```

**restore:** the inverse edit (`mode=None)` back to `mode=0o700 if scratch is None else None)`).

**restore receipt:** `git diff --stat -- plugins/superheroes/lib/break_it.py`:
```
 plugins/superheroes/lib/break_it.py | 53 ++++++++++++++++++++++---------------
 1 file changed, 31 insertions(+), 22 deletions(-)
```
restored line (`grep -n` of the file):
```
1446:                              mode=0o700 if scratch is None else None)
```

**raw green** (exit 0), same command:
```
.                                                                        [100%]
1 passed in 0.90s
pytest exit: 0
```

---

## E5: the caller-given `scratch` is honoured

- **axis:** a given session folder holds the per-run folder

**neutralization** (`plugins/superheroes/lib/break_it.py`, `_scratch_folder`):
```diff
-    if scratch is not None:
+    if False and scratch is not None:
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_break_it_system_temp_2351.py::test_sibling_an_explicit_scratch_holds_the_per_run_folder_and_it_is_gone_afterwards -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_sibling_an_explicit_scratch_holds_the_per_run_folder_and_it_is_gone_afterwards _

repo = PosixPath('/tmp/claude-0/pytest-of-root/pytest-11/test_sibling_an_explicit_scrat0/repo')
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-11/test_sibling_an_explicit_scrat0')
systmp = PosixPath('/tmp/claude-0/pytest-of-root/pytest-11/test_sibling_an_explicit_scrat0/systmp')

    def test_sibling_an_explicit_scratch_holds_the_per_run_folder_and_it_is_gone_afterwards(repo, tmp_path, systmp):
        session = tmp_path / "session"
        session.mkdir()
        record = _run(repo, "tests/test_t.py", PRINT_TMP, scratch=str(session))
        assert record["outcome"] == "passed", record
        printed = _printed(record, "TMPDIR")
>       assert os.path.realpath(os.path.dirname(printed)) == os.path.realpath(str(session)), printed
E       AssertionError: /tmp/claude-0/pytest-of-root/pytest-11/test_sibling_an_explicit_scrat0/systmp/break-it-tmp-85b282fad3bd4f128122204a5c860701
E       assert '/tmp/claude-...scrat0/systmp' == '/tmp/claude-...crat0/session'
E         
E         Skipping 62 identical leading characters in diff, use -v to show
E         - t_scrat0/session
E         + t_scrat0/systmp

/home/user/wt-2351/plugins/superheroes/lib/tests/test_break_it_system_temp_2351.py:159: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_system_temp_2351.py::test_sibling_an_explicit_scratch_holds_the_per_run_folder_and_it_is_gone_afterwards
1 failed in 0.50s
pytest exit: 1
```

**restore:** the inverse edit (`if False and scratch is not None:` back to `if scratch is not None:`).

**restore receipt:** `git diff --stat -- plugins/superheroes/lib/break_it.py`:
```
 plugins/superheroes/lib/break_it.py | 53 ++++++++++++++++++++++---------------
 1 file changed, 31 insertions(+), 22 deletions(-)
```
restored lines (`grep -n 'if scratch is not None:'`; the second hit, line 1584, is `_safe_run`'s own pre-existing line, which the neutralization did not touch):
```
1404:    if scratch is not None:
1584:    if scratch is not None:
```

**raw green** (exit 0), same command:
```
.                                                                        [100%]
1 passed in 0.51s
pytest exit: 0
```

---

## E6: the C-locale pin on the outside-every-repository probe

**Provenance:** orchestrator-typed at the review loop's apply-fixes step (round 1), maker family anthropic; the neutralization, red, restore and green were run by the build session itself.

- **axis:** a git that translates its diagnostics still proves an outside-every-repository system temp folder
- **proving node:** `test_break_it_system_temp_2351.py::test_locale_a_translated_git_still_proves_the_system_temp_folder_outside_every_repository` (a fake `git` first on `PATH` that answers in English only under `LC_ALL=C`; ambient `LC_ALL=de_DE.UTF-8`, `LANGUAGE=de`)

**neutralization** (`plugins/superheroes/lib/break_it.py`, `_scratch_folder`): `_clean_env({"LC_ALL": "C", "LANGUAGE": "C"})` → `_clean_env()` in the `_git_env` call.

**raw red** (exit 1):

```
E       AssertionError: assert (None, 'scratch-unresolved') == ('/tmp/pytest...systmp', None)
E         
E         At index 0 diff: None != '/tmp/pytest-of-root/pytest-13/test_locale_a_translated_git_s0/systmp'
E         Use -v to get more diff
1 failed in 1.20s
pytest exit: 1
```

**restore:** the inverse edit; `git diff --stat -- plugins/superheroes/lib/break_it.py` against the round-1 start head then read `1 file changed, 8 insertions(+), 2 deletions(-)`, the fix as committed.

**raw green** (exit 0):

```
1 passed in 1.15s
pytest exit: 0
```
