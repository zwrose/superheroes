# WO-1 (#1961) bite-proof — the `breakItInterpreter` calibration decides the break-it launcher when set

**Provenance:** claude / sonnet-5.5 (implementer, WO-1), `plugins/superheroes/lib/break_it.py` (`launcher_argv`, `resolve_interpreter`, `run_one`) and `round_driver.py` (`_fold_panel`, `_break_it_kept_step`, `next --break-it-interpreter`); detector file `plugins/superheroes/lib/tests/test_break_it_interpreter_key_1961.py`.

Declared guarded-element set (from the order): **G1-G5**. Each was neutralized by one targeted edit (the Edit tool, an exact old-string to new-string swap), its detector node(s) run, the inverse edit applied, and the same node(s) run again. No `git checkout`, `git restore`, `git reset` or `git stash` was used. Command: `scripts/pinned-python -B -X pycache_prefix=/tmp/pyc-wo1 -m pytest -q -p no:cacheprovider <node>`.

## Guarded elements

| ID | Guarded element | Axis | Proving node(s) |
|---|---|---|---|
| G1 | the list-prefix substitution in `run_one` (`argv = interpreter + ... + argv[1:]`) | a python run executes under the calibrated launcher prefix | `test_k1_a_list_prefix_runs_a_python_command_under_the_key` |
| G2 | `resolve_interpreter`'s never-fall-back branch (`return launcher_argv(value) or []`) | a set-but-invalid key resolves to `[]`, never the walker | `test_k5_an_invalid_key_resolves_to_the_empty_prefix_never_the_walker` (6 params) |
| G3 | the pytest mapping (`(["-m", "pytest"] if is_pytest else [])`) | a pytest program under a list prefix runs as `<prefix> -m pytest` | `test_k4_a_pytest_block_runs_as_the_prefix_dash_m_pytest[pytest]` |
| G4a | `_fold_panel` passes `break_it.resolve_interpreter(config)` to `intercept` | the driver fold reads the key | `test_k2_the_key_decides_the_launcher_when_the_verify_command_names_none` |
| G4b | `_break_it_kept_step` passes `break_it.resolve_interpreter(config)` to `check_kept` | the kept-check re-run reads the key | `test_k7_a_fixed_break_it_finding_certifies_under_the_key` |
| G5 | the fresh-state refusal on `next --break-it-interpreter` | the flag on existing state refuses `break-it-interpreter-not-fresh-state` | `test_k8_the_flag_on_an_existing_state_refuses` |

## Disclosures

- All six entries (G4 neutralized at each of its two sites separately) went red under their neutralization (pytest exit 1) and green after the restore (exit 0).
- G1's neutralization (`argv = argv`) drops the whole list-form rewrite, so it would also redden the pytest mapping; the K1 node is the G1 detector and the K4 node (G3) is proven by a separate, narrower neutralization.
- G2's detector is the whole six-parameter function (`""`, `"   "`, `"-x"`, `"'unterminated"`, `5`, `["a"]`); all six went red together.
- G5's neutralization replaces the refusal condition with `if False:`; the second `next` then returned 0.
- The K2 invalid-key driver node, K5's `[]` run nodes, K6 and K3 were not separately neutralized; they are covered by the G1/G2 neutralizations only to the extent those reddened them (not run — only the named single detector node was run per element).
- Red captures are well under 32 KiB; none is written off-repo.
- Restore receipts: the restored lines are quoted back from the file after the inverse edit (a grep read, with line numbers as they stand).

---

## G1 — the list-prefix substitution in `run_one`

- **axis:** a python run executes under the calibrated launcher prefix

**neutralization** (`plugins/superheroes/lib/break_it.py`):
```diff
-            argv = interpreter + (["-m", "pytest"] if is_pytest else []) + argv[1:]
+            argv = argv
```

**raw red** (exit 1):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_k1_a_list_prefix_runs_a_python_command_under_the_key ___________

launcher_repo = PosixPath('/tmp/claude-0/pytest-of-root/pytest-1/test_k1_a_list_prefix_runs_a_p0/repo')

    def test_k1_a_list_prefix_runs_a_python_command_under_the_key(launcher_repo):
        # axis: `run_one` swaps a python program for the calibrated launcher prefix and records the prefix on the run
        record = break_it.run_one(str(launcher_repo), TB._head(launcher_repo), _python_block(),
                                  interpreter=[FAKE])
        assert record["outcome"] == "failed"
>       assert MARKER in record["output"]
E       AssertionError: assert 'PINNED-LAUNCHER' in ''

/home/user/wt-1961-wo1/plugins/superheroes/lib/tests/test_break_it_interpreter_key_1961.py:50: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_interpreter_key_1961.py::test_k1_a_list_prefix_runs_a_python_command_under_the_key
1 failed in 0.92s
exit=1
```

**decisive assertion:** `>       assert MARKER in record["output"]` (`E       AssertionError: assert 'PINNED-LAUNCHER' in ''`)

**restore:** the inverse edit (`argv = argv` replaced by the original line).

**restored lines** (as they stand):
```
758:            argv = interpreter + (["-m", "pytest"] if is_pytest else []) + argv[1:]
```

**raw green** (exit 0):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.76s
exit=0
```

---

## G2 — `resolve_interpreter` never falls back to the walker

- **axis:** a set-but-invalid key resolves to `[]`, never the verify command's launcher

**neutralization** (`plugins/superheroes/lib/break_it.py`):
```diff
-        return launcher_argv(value) or []
+        return launcher_argv(value) or project_interpreter(config.get("verifyCommand"))
```

**raw red** (exit 1; the six per-parameter failure bodies differ only in `value`, shown here as printed):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FFFFFF                                                                   [100%]
=================================== FAILURES ===================================
___ test_k5_an_invalid_key_resolves_to_the_empty_prefix_never_the_walker[''] ___

value = ''

    @pytest.mark.parametrize("value", INVALID_VALUES, ids=repr)
    def test_k5_an_invalid_key_resolves_to_the_empty_prefix_never_the_walker(value):
        # axis: a set-but-invalid key resolves to `[]` even when the verify command names a launcher the walker would find
        assert break_it.project_interpreter(PROJECT_COMMAND) == "scripts/pinned-python"
        config = {break_it.INTERPRETER_KEY: value, "verifyCommand": PROJECT_COMMAND}
        assert break_it.launcher_argv(value) is None
>       assert break_it.resolve_interpreter(config) == []
E       AssertionError: assert 'scripts/pinned-python' == []
E        +  where 'scripts/pinned-python' = <function resolve_interpreter at 0x7fa368c35a80>({'breakItInterpreter': '', 'verifyCommand': 'if [ -x scripts/pinned-python ]; then scripts/pinned-python .github/scrip...thub/scripts/validate_marketplace.py && /usr/bin/python3 .github/scripts/verify_touched_tests.py --base {baseRef}; fi'})
E        +    where <function resolve_interpreter at 0x7fa368c35a80> = break_it.resolve_interpreter

/home/user/wt-1961-wo1/plugins/superheroes/lib/tests/test_break_it_interpreter_key_1961.py:137: AssertionError
_ test_k5_an_invalid_key_resolves_to_the_empty_prefix_never_the_walker['   '] __

value = '   '
(same body: assert 'scripts/pinned-python' == [])

__ test_k5_an_invalid_key_resolves_to_the_empty_prefix_never_the_walker['-x'] __

value = '-x'
(same body: assert 'scripts/pinned-python' == [])

_ test_k5_an_invalid_key_resolves_to_the_empty_prefix_never_the_walker["'unterminated"] _

value = "'unterminated"
(same body: assert 'scripts/pinned-python' == [])

___ test_k5_an_invalid_key_resolves_to_the_empty_prefix_never_the_walker[5] ____

value = 5
(same body: assert 'scripts/pinned-python' == [])

_ test_k5_an_invalid_key_resolves_to_the_empty_prefix_never_the_walker[['a']] __

value = ['a']
(same body: assert 'scripts/pinned-python' == [])

=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_interpreter_key_1961.py::test_k5_an_invalid_key_resolves_to_the_empty_prefix_never_the_walker['']
FAILED plugins/superheroes/lib/tests/test_break_it_interpreter_key_1961.py::test_k5_an_invalid_key_resolves_to_the_empty_prefix_never_the_walker['   ']
FAILED plugins/superheroes/lib/tests/test_break_it_interpreter_key_1961.py::test_k5_an_invalid_key_resolves_to_the_empty_prefix_never_the_walker['-x']
FAILED plugins/superheroes/lib/tests/test_break_it_interpreter_key_1961.py::test_k5_an_invalid_key_resolves_to_the_empty_prefix_never_the_walker["'unterminated"]
FAILED plugins/superheroes/lib/tests/test_break_it_interpreter_key_1961.py::test_k5_an_invalid_key_resolves_to_the_empty_prefix_never_the_walker[5]
FAILED plugins/superheroes/lib/tests/test_break_it_interpreter_key_1961.py::test_k5_an_invalid_key_resolves_to_the_empty_prefix_never_the_walker[['a']]
6 failed in 0.97s
exit=1
```

(The five `(same body ...)` lines abbreviate the repeated traceback text in this record; the run printed each in full, with the identical `E   AssertionError: assert 'scripts/pinned-python' == []` line.)

**decisive assertion:** `>       assert break_it.resolve_interpreter(config) == []` (`E       AssertionError: assert 'scripts/pinned-python' == []`)

**restore:** the inverse edit.

**restored lines** (as they stand):
```
441:        return launcher_argv(value) or []
```

**raw green** (exit 0):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
......                                                                   [100%]
6 passed in 0.41s
exit=0
```

---

## G3 — the pytest mapping

- **axis:** a pytest program under a list prefix runs as `<prefix> -m pytest <args>`

**neutralization** (`plugins/superheroes/lib/break_it.py`):
```diff
-            argv = interpreter + (["-m", "pytest"] if is_pytest else []) + argv[1:]
+            argv = interpreter + argv[1:]
```

**raw red** (exit 1):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_k4_a_pytest_block_runs_as_the_prefix_dash_m_pytest[pytest] ________

launcher_repo = PosixPath('/tmp/claude-0/pytest-of-root/pytest-5/test_k4_a_pytest_block_runs_as0/repo')
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-5/test_k4_a_pytest_block_runs_as0')
program = 'pytest'

    @pytest.mark.parametrize("program", ["pytest", "py.test", "/usr/bin/pytest"])
    def test_k4_a_pytest_block_runs_as_the_prefix_dash_m_pytest(launcher_repo, tmp_path, program):
        # axis: under a list prefix a pytest program runs as `<prefix> -m pytest <args>`, not as the bare program
        script, log = _echo_launcher(tmp_path)
        record = break_it.run_one(str(launcher_repo), TB._head(launcher_repo),
                                  _pytest_block(program=program), interpreter=[script, TAG])
>       assert "ARGV: %s -m pytest %s" % (TAG, PYTEST_PATH) in record["output"]
E       AssertionError: assert ('ARGV: %s -m pytest %s' % ('TAG1', 'tests/test_pytest_block.py')) in 'ARGV: TAG1 tests/test_pytest_block.py\n'

/home/user/wt-1961-wo1/plugins/superheroes/lib/tests/test_break_it_interpreter_key_1961.py:106: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_interpreter_key_1961.py::test_k4_a_pytest_block_runs_as_the_prefix_dash_m_pytest[pytest]
1 failed in 0.77s
exit=1
```

**decisive assertion:** `>       assert "ARGV: %s -m pytest %s" % (TAG, PYTEST_PATH) in record["output"]` (output was `'ARGV: TAG1 tests/test_pytest_block.py\n'`, no `-m pytest`)

**restore:** the inverse edit.

**restored lines** (as they stand):
```
758:            argv = interpreter + (["-m", "pytest"] if is_pytest else []) + argv[1:]
```

**raw green** (exit 0):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.46s
exit=0
```

---

## G4a — `_fold_panel` uses `resolve_interpreter`

- **axis:** the driver fold reads the launcher from the session's `breakItInterpreter` when the verify command names none

**neutralization** (`plugins/superheroes/lib/round_driver.py`, the `break_it.intercept` call):
```diff
-        interpreter=break_it.resolve_interpreter(config))
+        interpreter=break_it.project_interpreter(config.get("verifyCommand")))
```

**raw red** (exit 1):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_k2_the_key_decides_the_launcher_when_the_verify_command_names_none ____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-7/test_k2_the_key_decides_the_la0')

    def test_k2_the_key_decides_the_launcher_when_the_verify_command_names_none(tmp_path):
        # axis: the driver fold reads the launcher from the session's `breakItInterpreter` when the verify command names none
        world = _driver_world(tmp_path / "keyed", "pytest -q")
        world.state["config"][break_it.INTERPRETER_KEY] = FAKE
        world.fold_panel(_python_finding())
        (entry,) = world.round_record["breakItRuns"]
>       assert MARKER in entry["output"]
E       AssertionError: assert 'PINNED-LAUNCHER' in ''

/home/user/wt-1961-wo1/plugins/superheroes/lib/tests/test_break_it_interpreter_key_1961.py:62: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_interpreter_key_1961.py::test_k2_the_key_decides_the_launcher_when_the_verify_command_names_none
1 failed in 0.41s
exit=1
```

**decisive assertion:** `>       assert MARKER in entry["output"]` (`E       AssertionError: assert 'PINNED-LAUNCHER' in ''`)

**restore:** the inverse edit.

**restored lines** (as they stand, with the other site):
```
3311:        interpreter=break_it.resolve_interpreter(config))
6761:                                  interpreter=break_it.resolve_interpreter(config))
```

**raw green** (exit 0):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.02s
exit=0
```

---

## G4b — `_break_it_kept_step` uses `resolve_interpreter`

- **axis:** the kept-check re-run takes its launcher from the key, so a fixed finding on a launcher-less verify command is kept

**neutralization** (`plugins/superheroes/lib/round_driver.py`, the `break_it.check_kept` call):
```diff
-                                  interpreter=break_it.resolve_interpreter(config))
+                                  interpreter=break_it.project_interpreter(config.get("verifyCommand")))
```

**raw red** (exit 1):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_k7_a_fixed_break_it_finding_certifies_under_the_key ___________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-9/test_k7_a_fixed_break_it_findi0')

    def test_k7_a_fixed_break_it_finding_certifies_under_the_key(tmp_path):
        # axis: the kept-check re-run takes its launcher from the key, so a fixed finding on a launcher-less verify command is kept
        world = _fixed_world(tmp_path)
>       assert RD._break_it_kept_step(world.state, world.state["config"]) is False
E       AssertionError: assert True is False
E        +  where True = <function _break_it_kept_step at 0x7f211c3b8fe0>({'schemaVersion': 5, 'sessionGeneration': 5, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...}, {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...})
E        +    where <function _break_it_kept_step at 0x7f211c3b8fe0> = RD._break_it_kept_step
E        +    and   {'schemaVersion': 5, 'sessionGeneration': 5, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...} = <test_break_it_loop.World object at 0x7f211cd2eba0>.state

/home/user/wt-1961-wo1/plugins/superheroes/lib/tests/test_break_it_interpreter_key_1961.py:235: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_interpreter_key_1961.py::test_k7_a_fixed_break_it_finding_certifies_under_the_key
1 failed in 0.77s
exit=1
```

**decisive assertion:** `>       assert RD._break_it_kept_step(world.state, world.state["config"]) is False` (`E       AssertionError: assert True is False` — the step parked)

**restore:** the inverse edit.

**restored lines** (as they stand):
```
3311:        interpreter=break_it.resolve_interpreter(config))
6761:                                  interpreter=break_it.resolve_interpreter(config))
```

**raw green** (exit 0):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.27s
exit=0
```

---

## G5 — the fresh-state refusal on `next --break-it-interpreter`

- **axis:** the flag on existing state refuses `break-it-interpreter-not-fresh-state`, never silently ignored

**neutralization** (`plugins/superheroes/lib/round_driver.py`, the `next` override block):
```diff
-            if not (st_ok and st is None):
+            if False:
                 sys.stdout.write(json.dumps({"ok": False,
                                              "reason": "break-it-interpreter-not-fresh-state",
```

**raw red** (exit 1):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_k8_the_flag_on_an_existing_state_refuses _________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-11/test_k8_the_flag_on_an_existin0')
capsys = <_pytest.capture.CaptureFixture object at 0x7f2cff1b2150>

    def test_k8_the_flag_on_an_existing_state_refuses(tmp_path, capsys):
        # axis: `--break-it-interpreter` on a non-fresh session refuses `break-it-interpreter-not-fresh-state`, never silently ignored
        d = str(tmp_path / "s")
        os.makedirs(d)
        # A/B: fresh state accepts it
        assert RD.main(["next", "--session-dir", d, "--break-it-interpreter", "python3"] + _guard_argv(d)) == 0
        capsys.readouterr()
        rc = RD.main(["next", "--session-dir", d, "--break-it-interpreter", "python3"]
                     + _guard_argv(d, fresh=False))
        out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
>       assert rc == 1
E       assert 0 == 1

/home/user/wt-1961-wo1/plugins/superheroes/lib/tests/test_break_it_interpreter_key_1961.py:331: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_interpreter_key_1961.py::test_k8_the_flag_on_an_existing_state_refuses
1 failed in 1.32s
exit=1
```

**decisive assertion:** `>       assert rc == 1` (`E       assert 0 == 1`)

**restore:** the inverse edit (`if False:` replaced by `if not (st_ok and st is None):`).

**restored lines** (as they stand):
```
13472:            if not (st_ok and st is None):
13473-                sys.stdout.write(json.dumps({"ok": False,
13474:                                             "reason": "break-it-interpreter-not-fresh-state",
13475-                                             "value": args.break_it_interpreter}) + "\n")
13476-                return 1
```

**raw green** (exit 0):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.09s
exit=0
```
