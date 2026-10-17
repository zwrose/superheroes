# WO-3 (#1910) bite-proof — break-it python runs execute under the project's launcher, or read not-run

**Provenance:** claude / sonnet-5.5 (implementer, WO-3), `plugins/superheroes/lib/break_it.py` and `round_driver.py` (`_fold_panel`); detector file `plugins/superheroes/lib/tests/test_break_it_interpreter_1910.py`.

Declared guarded-element set (from the order): **B1-B5**. Each was neutralized by one targeted edit (the Edit tool, an exact old-string to new-string swap), its single detector node(s) run, the inverse edit applied, and the same node(s) run again. No `git checkout`, `git restore`, `git reset` or `git stash` was used. Command: `scripts/pinned-python -B -X pycache_prefix=/tmp/pyc-wo3 -m pytest -q -p no:cacheprovider <node>`.

## Guarded elements

| ID | Guarded element | Axis | Proving node(s) |
|---|---|---|---|
| B1 | the python-program substitution in `run_one` (`argv = [interpreter] + argv[1:]`) | a python run executes under the supplied launcher | `test_break_it_interpreter_1910.py::test_t1_run_one_runs_a_python_command_under_the_supplied_launcher` |
| B2 | the `interpreter-unresolved` branch in `run_one` | no launcher means not-run, never a PATH python | `test_t2_the_driver_reads_not_run_when_the_verify_command_names_no_launcher`, `test_t2_each_unresolvable_verify_command_reads_not_run_never_failed` |
| B3 | the readiness probe (`if interpreter:` block in `_run_in_copy`) | a launcher that cannot start reads not-run, never failed | `test_t3_a_launcher_that_does_not_start_reads_not_run_never_failed`, `test_t3_the_broken_launchers_output_tail_is_recorded` |
| B4 | the driver's threading in `_fold_panel` (`interpreter=` at the `break_it.intercept` call) | the session's verify command reaches the intercept | `test_t1_the_driver_threads_the_verify_commands_launcher_into_the_run` |
| B5 | the resolver's command-position walk (`project_interpreter`, a separator sets `at_command`) | a launcher after `then`/`&&` in a shell-shaped command is found | `test_t4_project_interpreter` |

## Disclosures

- All five elements went red under their neutralization (pytest exit 1) and green after the restore (exit 0).
- B3: `test_t3_the_broken_launchers_output_tail_is_recorded` stayed green under the neutralization (the broken launcher prints `launcher-is-broken` in the real run too), so it does not discriminate the probe; the parametrized `test_t3_a_launcher_that_does_not_start_reads_not_run_never_failed` is the B3 detector.
- B2's neutralization lets a falsy interpreter fall through to run as written (`and interpreter` added to the substitution condition).
- B4 is proven only on the `_fold_panel` call; the `_break_it_kept_step` call (`check_kept`) is not separately neutralized, so that threading is unproven here (the `check_kept` argument itself is covered by `test_t5_check_kept_reruns_under_the_launcher`).
- The fixture commits ran in the sandbox without `failed to write commit object`; no git-config pin was needed.
- Red captures are well under 32 KiB; none is written off-repo.
- Restore receipts: the restored lines are quoted back from the file after the inverse edit (a targeted Grep read, with line numbers as they stand).

---

## B1 — the python-program substitution in `run_one`

- **axis:** a python run executes under the supplied launcher

**neutralization** (`plugins/superheroes/lib/break_it.py`):
```diff
-        argv = [interpreter] + argv[1:]
+        argv = argv
```

**raw red** (exit 1):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_t1_run_one_runs_a_python_command_under_the_supplied_launcher _______

launcher_repo = PosixPath('/tmp/claude-0/pytest-of-root/pytest-12/test_t1_run_one_runs_a_python_0/repo')

    def test_t1_run_one_runs_a_python_command_under_the_supplied_launcher(launcher_repo):
        record = break_it.run_one(str(launcher_repo), TB._head(launcher_repo), _python_block(),
                                  interpreter=FAKE)
        assert record["outcome"] == "failed"
>       assert MARKER in record["output"]
E       AssertionError: assert 'PINNED-LAUNCHER' in ''

/home/user/wt-1910-wo3/plugins/superheroes/lib/tests/test_break_it_interpreter_1910.py:60: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_interpreter_1910.py::test_t1_run_one_runs_a_python_command_under_the_supplied_launcher
1 failed in 0.39s
```

**decisive assertion:** `>       assert MARKER in record["output"]` (`E       AssertionError: assert 'PINNED-LAUNCHER' in ''`)

**restore:** the inverse edit (`argv = argv` replaced by `argv = [interpreter] + argv[1:]`).

**restored lines** (as they stand):
```
608:        argv = [interpreter] + argv[1:]
```

**raw green** (exit 0):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.49s
```

---

## B2 — the `interpreter-unresolved` branch

- **axis:** no launcher means not-run, never a PATH python

**neutralization** (`plugins/superheroes/lib/break_it.py`):
```diff
-    if interpreter is not _UNSET and _is_python_program(argv[0]):
+    if interpreter is not _UNSET and interpreter and _is_python_program(argv[0]):
```

**raw red** (exit 1):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FFFFFF                                                                   [100%]
=================================== FAILURES ===================================
__ test_t2_the_driver_reads_not_run_when_the_verify_command_names_no_launcher __

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-14/test_t2_the_driver_reads_not_r0')

    def test_t2_the_driver_reads_not_run_when_the_verify_command_names_no_launcher(tmp_path):
        world = _driver_world(tmp_path, "none")
        world.fold_panel(_python_finding())
        (entry,) = world.round_record["breakItRuns"]
>       assert entry["outcome"] == "not-run"
E       AssertionError: assert 'failed' == 'not-run'
E         
E         - not-run
E         + failed

/home/user/wt-1910-wo3/plugins/superheroes/lib/tests/test_break_it_interpreter_1910.py:94: AssertionError
__ test_t2_each_unresolvable_verify_command_reads_not_run_never_failed[None] ___

launcher_repo = PosixPath('/tmp/claude-0/pytest-of-root/pytest-14/test_t2_each_unresolvable_veri0/repo')
verify_command = None

    @pytest.mark.parametrize("verify_command", [None, "", "none", "python3 -m 'pytest", "make test"])
    def test_t2_each_unresolvable_verify_command_reads_not_run_never_failed(launcher_repo, verify_command):
        interpreter = break_it.project_interpreter(verify_command)
        assert interpreter is None
        record = break_it.run_one(str(launcher_repo), TB._head(launcher_repo), _python_block(),
                                  interpreter=interpreter)
>       assert (record["outcome"], record["reason"]) == ("not-run", "interpreter-unresolved")
E       AssertionError: assert ('failed', None) == ('not-run', '...r-unresolved')
E         
E         At index 0 diff: 'failed' != 'not-run'
E         Use -v to get more diff

/home/user/wt-1910-wo3/plugins/superheroes/lib/tests/test_break_it_interpreter_1910.py:105: AssertionError
(the four remaining parametrized cases `[]`, `[none]`, `[python3 -m 'pytest]`, `[make test]` fail with the identical assertion and message; omitted here only to keep the file short — the run's final line was:)
6 failed in 1.45s
```

**decisive assertion lines:** `>       assert entry["outcome"] == "not-run"` (`E       AssertionError: assert 'failed' == 'not-run'`) and `>       assert (record["outcome"], record["reason"]) == ("not-run", "interpreter-unresolved")`

**restore:** the inverse edit (`and interpreter` removed).

**restored lines** (as they stand):
```
602:    if interpreter is not _UNSET and _is_python_program(argv[0]):
```

**raw green** (exit 0):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
......                                                                   [100%]
6 passed in 0.52s
```

---

## B3 — the readiness probe

- **axis:** a launcher that cannot start reads not-run, never failed

**neutralization** (`plugins/superheroes/lib/break_it.py`, `_run_in_copy`):
```diff
-    if interpreter:
+    if False:
```

**raw red** (exit 1; the three failures' assertion lines are quoted, the traceback bodies are the same parametrized function):
```
FFF.                                                                     [100%]
>       assert (record["outcome"], record["reason"]) == ("not-run", "interpreter-unavailable")
E       AssertionError: assert ('not-run', '...nd-not-found') == ('not-run', '...-unavailable')
E       AssertionError: assert ('failed', None) == ('not-run', '...-unavailable')
E       AssertionError: assert ('not-run', 'timeout') == ('not-run', '...-unavailable')
FAILED ...::test_t3_a_launcher_that_does_not_start_reads_not_run_never_failed[scripts/missing-python-kwargs0]
FAILED ...::test_t3_a_launcher_that_does_not_start_reads_not_run_never_failed[scripts/broken-python-kwargs1]
FAILED ...::test_t3_a_launcher_that_does_not_start_reads_not_run_never_failed[scripts/slow-python-kwargs2]
3 failed, 1 passed in 1.93s
```
(This block is an abridged capture of the red run, labelled as such: the full pytest output was seen in the dispatch and the lines above are verbatim from it.)

**decisive assertion line:** `>       assert (record["outcome"], record["reason"]) == ("not-run", "interpreter-unavailable")` (the broken launcher reads `('failed', None)`)

**restore:** the inverse edit (`if False:` replaced by `if interpreter:`).

**restored lines** (as they stand):
```
534:     if interpreter:
535:         # axis: a launcher that cannot start reads not-run, never a failed test — see bite-proof record wo_3_1910_break_it_interpreter
```

**raw green** (exit 0):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
....                                                                     [100%]
4 passed in 1.57s
```

---

## B4 — the driver's threading in `_fold_panel`

- **axis:** the session's verify command reaches the intercept

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
-        break_it_raw, repo_root, head,
-        interpreter=break_it.project_interpreter(config.get("verifyCommand")))
+        break_it_raw, repo_root, head)
```

**raw red** (exit 1):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_t1_the_driver_threads_the_verify_commands_launcher_into_the_run _____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-18/test_t1_the_driver_threads_the0')

    def test_t1_the_driver_threads_the_verify_commands_launcher_into_the_run(tmp_path):
        world = _driver_world(tmp_path, "%s -m pytest" % FAKE)
        world.fold_panel(_python_finding())
        (entry,) = world.round_record["breakItRuns"]
>       assert MARKER in entry["output"]
E       AssertionError: assert 'PINNED-LAUNCHER' in ''

/home/user/wt-1910-wo3/plugins/superheroes/lib/tests/test_break_it_interpreter_1910.py:83: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_interpreter_1910.py::test_t1_the_driver_threads_the_verify_commands_launcher_into_the_run
1 failed in 0.45s
```

**decisive assertion:** `>       assert MARKER in entry["output"]` (`E       AssertionError: assert 'PINNED-LAUNCHER' in ''`)

**restore:** the inverse edit (the two-line `interpreter=` argument put back).

**restored lines** (as they stand, from line 3291):
```
3291:         break_it_raw, repo_root, head,
3292:         interpreter=break_it.project_interpreter(config.get("verifyCommand")))
```

**raw green** (exit 0):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.49s
```

---

## B5 — the resolver's command-position walk

- **axis:** a launcher after `then`/`&&` in a shell-shaped command is found

**neutralization** (`plugins/superheroes/lib/break_it.py`, `project_interpreter`: a separator no longer opens a command position):
```diff
         if _is_separator(tok):
-            at_command = True
             continue
```

**raw red** (exit 1; the two failures' assertion lines, verbatim from the run):
```
F....F                                                                   [100%]
>       assert break_it.project_interpreter(command) == expected
E       AssertionError: assert None == 'scripts/pinned-python'
>       assert break_it.project_interpreter(command) == expected
E       AssertionError: assert None == 'a/b'
FAILED ...::test_t4_project_interpreter[if [ -x scripts/pinned-python ]; then scripts/pinned-python .github/scripts/validate_python_pin.py && ... fi-scripts/pinned-python]
FAILED ...::test_t4_project_interpreter[[ -x a/b ] && a/b c.py-a/b]
2 failed, 4 passed in 0.31s
```
(Abridged capture, labelled as such: the full pytest output was seen in the dispatch; the lines above are verbatim from it.)

**decisive assertion:** `>       assert break_it.project_interpreter(command) == expected` (`E       AssertionError: assert None == 'scripts/pinned-python'`)

**restore:** the inverse edit (`at_command = True` put back).

**restored lines** (as they stand):
```
270:         if _is_separator(tok):
271:             at_command = True
272:             continue
```

**raw green** (exit 0):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
......                                                                   [100%]
6 passed in 0.33s
```
