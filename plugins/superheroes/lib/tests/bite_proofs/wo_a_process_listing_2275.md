# WO-A #2275 bite-proofs: sandbox-only tests (process_listing mark, CLAUDE_PID scrub)

Each entry: guarded element and axis, the neutralization (one targeted edit, reverted by the inverse edit), the
detector run alone (single node, `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest <node> -q -p no:cacheprovider`),
its raw red, the restore with the restored line quoted back, and the raw green. Run inside the claude write
sandbox (Linux, `SANDBOX_RUNTIME=1`, `CLAUDE_PID=17418`). Redaction: the G3 red output echoed the whole process
environment inside an assertion message; the proxy URL (which carries a credential-like token) is cut to `<proxy
URL redacted>` and the elision is marked `...`. Nothing else was altered. `UV_NATIVE_TLS` deprecation warning lines
(first line of every run) are omitted.

Declared guarded-element set: G1 outcome-hook branch, G2 fixture fail-not-skip leg, G3 CLAUDE_PID scrub,
G4 the three marks (three neutralizations). Seven neutralize/restore pairs were run in all (G4 = three).

## G1 - outcome hook's `process_listing` branch (axis: a marked test's skip survives only with the sandbox marker AND a failing probe)

- File: `plugins/superheroes/lib/tests/proc_namespace.py`, `_fail_skip_outside_process_listing`.
- Neutralization: `if not report.skipped or process_listing_skip_allowed():` became `if True or not report.skipped or process_listing_skip_allowed():` (the hook never converts a skip).
- Detector: `test_process_listing_2275.py::test_a_skip_with_no_marker_and_a_working_probe_is_a_failure` and `::test_a_skip_with_the_marker_and_a_working_probe_is_a_failure`.
- Raw red (the child pytest's own summary, quoted inside the assertion message, is the decisive part):

```
FF                                                                       [100%]
...
E       AssertionError: s                                                                        [100%]
E         SKIPPED [1] test_child_process_listing.py:23: forced
E         1 skipped, 1 warning in 0.01s
E       assert 0 == 1
...
E         SKIPPED [1] test_child_process_listing.py:23: forced
E         1 skipped, 1 warning in 0.02s
E       assert 0 == 1
...
FAILED plugins/superheroes/lib/tests/test_process_listing_2275.py::test_a_skip_with_no_marker_and_a_working_probe_is_a_failure
FAILED plugins/superheroes/lib/tests/test_process_listing_2275.py::test_a_skip_with_the_marker_and_a_working_probe_is_a_failure
2 failed in 2.46s
```
(elided: the repeated PytestUnknownMarkWarning blocks in the child output, which the child prints because it runs with `-c /dev/null`.)

- Restore: inverse edit. Restored line quoted back (`grep -n`): `134:    if not report.skipped or process_listing_skip_allowed():`
- Raw green:

```
..                                                                       [100%]
2 passed in 3.56s
```

## G2 - fixture's fail-not-skip leg (axis: a failing probe with no sandbox marker fails with "refuses to skip", never skips)

- File: `proc_namespace.py`, `require_process_listing`.
- Neutralization: `if process_listing_skip_allowed(environ, probe):` became `if True:` (the guard skips everywhere).
- Detector: `test_process_listing_2275.py::test_the_real_guard_fails_a_failing_probe_outside_the_sandbox` (real guard fixture, not shadowed). Note: the outcome hook still converts the guard's skip into a setup ERROR, so the run still exits 1; the detector reddens on the missing `refuses to skip` message, which is the fixture leg's own contract.
- Raw red:

```
F                                                                        [100%]
...
>       assert "refuses to skip" in output, output
E       AssertionError: E                                                                        [100%]
E         ==================================== ERRORS ====================================
E         ________________________ ERROR at setup of test_marked _________________________
E         a process_listing test was skipped while the claude write sandbox condition does not hold, which is not allowed: a skip needs both SANDBOX_RUNTIME=1 and a failing ps probe; original skip reason: Skipped: claude write sandbox: the `ps -g <pgid> -o state=` probe fails here, so a process group cannot be listed and its liveness cannot be observed
...
E         ERROR test_child_process_listing.py::test_marked - a process_listing test was...
E         1 warning, 1 error in 0.01s
...
FAILED plugins/superheroes/lib/tests/test_process_listing_2275.py::test_the_real_guard_fails_a_failing_probe_outside_the_sandbox
1 failed in 1.03s
```

- Restore: inverse edit. Restored line quoted back: `100:    if process_listing_skip_allowed(environ, probe):`
- Raw green:

```
.                                                                        [100%]
1 passed in 0.99s
```

## G3 - `CLAUDE_PID` scrub in `conftest.py` (axis: no lib test inherits the ambient CLAUDE_PID)

**Superseded by the Revision (WO-R1) section below:** the suite-wide scrub and its `test_ambient_claude_pid_is_scrubbed` detector no longer exist; this entry is kept as the original record.

- File: `plugins/superheroes/lib/tests/conftest.py`, `_isolate_store_root`.
- Neutralization: `monkeypatch.delenv("CLAUDE_PID", raising=False)` became `monkeypatch.delenv("CLAUDE_PID_NEUTRALIZED", raising=False)`.
- Precondition (the I1 test can redden only where `CLAUDE_PID` is ambient; on a host without it this proof cannot be produced): `echo "CLAUDE_PID=[$CLAUDE_PID]"` printed `CLAUDE_PID=[17418]`.
- Detector: `test_process_listing_2275.py::test_ambient_claude_pid_is_scrubbed`.
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________________ test_ambient_claude_pid_is_scrubbed ______________________

    def test_ambient_claude_pid_is_scrubbed():
>       assert "CLAUDE_PID" not in os.environ
E       AssertionError: assert 'CLAUDE_PID' not in environ({'AI_AGENT': 'claude-code_2-1-314_agent', 'ALL_PROXY': '<proxy URL redacted>...'TEST_PILOT_STORE_ROOT': '/tmp/claude-0/pytest-of-root/pytest-15/test_ambient_claude_pid_is_scr0/_tp_store_isolation'})
...
FAILED plugins/superheroes/lib/tests/test_process_listing_2275.py::test_ambient_claude_pid_is_scrubbed
1 failed in 0.93s
```

- Restore: inverse edit. Restored line quoted back: `156:    monkeypatch.delenv("CLAUDE_PID", raising=False)`
- Raw green:

```
.                                                                        [100%]
1 passed in 0.86s
```

## G4 - the three marks (axis: exactly the three named tests carry `process_listing`)

Detector for all three: `test_process_listing_2275.py::test_the_mark_selects_exactly_the_three_census_tests` (sub-pytest `--collect-only -m process_listing`); for the two write-file marks the direct `::test_the_two_write_tests_carry_the_process_listing_mark` was run beside it.

### G4a - `test_engine_dispatch_write.py::test_process_group_alive_zombie_only_is_dead`
- Neutralization: deleted the line `@pytest.mark.process_listing` above `def test_process_group_alive_zombie_only_is_dead():`.
- Raw red:

```
FF                                                                       [100%]
...
E       AssertionError: plugins/superheroes/lib/tests/test_engine_dispatch.py::test_terminal_transition_invariant_no_cleanup_before_durable_record[abandon_live_engine]
E         plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_dispatch_abandon_alive_engine_releases_lease
E         2/1056 tests collected (1054 deselected) in 0.95s
...
E         Extra items in the right set:
E         'plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_process_group_alive_zombie_only_is_dead'
...
E           AssertionError: test_process_group_alive_zombie_only_is_dead lacks @pytest.mark.process_listing
...
2 failed in 2.10s
```
- Restore: re-inserted the line. Restored lines quoted back: `987:@pytest.mark.process_listing` / `988:def test_process_group_alive_zombie_only_is_dead():`
- Raw green: `..   [100%]` / `2 passed in 2.11s`

### G4b - `test_engine_dispatch_write.py::test_dispatch_abandon_alive_engine_releases_lease`
- Neutralization: deleted the line `@pytest.mark.process_listing` above `def test_dispatch_abandon_alive_engine_releases_lease(tmp_path):`.
- Raw red:

```
FF                                                                       [100%]
...
E       AssertionError: plugins/superheroes/lib/tests/test_engine_dispatch.py::test_terminal_transition_invariant_no_cleanup_before_durable_record[abandon_live_engine]
E         plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_process_group_alive_zombie_only_is_dead
E         2/1056 tests collected (1054 deselected) in 0.75s
...
E         Extra items in the right set:
E         'plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_dispatch_abandon_alive_engine_releases_lease'
...
E           AssertionError: test_dispatch_abandon_alive_engine_releases_lease lacks @pytest.mark.process_listing
...
2 failed in 1.93s
```
- Restore: re-inserted the line. Restored lines quoted back: `1043:@pytest.mark.process_listing` / `1044:def test_dispatch_abandon_alive_engine_releases_lease(tmp_path):`
- Raw green: `..   [100%]` / `2 passed in 2.22s`

### G4c - `test_engine_dispatch.py` parametrize `abandon_live_engine`
- Neutralization: `pytest.param("abandon_live_engine", marks=pytest.mark.process_listing),` became `"abandon_live_engine",`.
- Raw red:

```
F                                                                        [100%]
...
E       AssertionError: plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_process_group_alive_zombie_only_is_dead
E         plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_dispatch_abandon_alive_engine_releases_lease
E         2/1056 tests collected (1054 deselected) in 2.43s
...
E         Extra items in the right set:
E         'plugins/superheroes/lib/tests/test_engine_dispatch.py::test_terminal_transition_invariant_no_cleanup_before_durable_record[abandon_live_engine]'
...
1 failed in 3.60s
```
- Restore: inverse edit. Restored line quoted back: `3281:    pytest.param("abandon_live_engine", marks=pytest.mark.process_listing),`
- Raw green:

```
.                                                                        [100%]
1 passed in 3.55s
```

Post-restore `git status --porcelain` (excluding the sandbox's untracked dotfiles): modified `conftest.py`, `proc_namespace.py`, `test_engine_dispatch.py`, `test_engine_dispatch_write.py`, `pytest.ini`; new `test_process_listing_2275.py` (and this record). No residue of any neutralization remains.

## Revision (WO-R1)

The verify gate refuses any `conftest.py` change, so `plugins/superheroes/lib/tests/conftest.py` is back at its base text and the two guards merged into one fixture. Changes this revision makes to the guarded set:

- G3 is replaced by G3': the `CLAUDE_PID` scrub is a module-level autouse fixture in `test_launch_roundtrip.py`, guarded by `test_roundtrip_scenario_passes_with_a_stale_ambient_claude_pid`. `test_ambient_claude_pid_is_scrubbed` is deleted.
- G2 is re-run against the merged fixture `_proc_containment_guard` (the separate `_process_listing_guard` is gone; the child test file now shadows `_proc_containment_guard`).
- G1 and G4 are unchanged by this revision and were not re-run.

Environment of the revision runs: the same claude write sandbox (Linux, `SANDBOX_RUNTIME=1`). Detector commands: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest <node> -q -p no:cacheprovider`. The `UV_NATIVE_TLS` warning line of each run is omitted; nothing else is altered or redacted (the G3' child output holds no environment dump).

### G3' - `CLAUDE_PID` scrub in `test_launch_roundtrip.py` (axis: the roundtrip scenarios do not depend on an ambient CLAUDE_PID)

- File: `plugins/superheroes/lib/tests/test_launch_roundtrip.py`, fixture `_no_ambient_claude_pid`.
- Neutralization: `monkeypatch.delenv("CLAUDE_PID", raising=False)` became `monkeypatch.delenv("CLAUDE_PID_NEUTRALIZED", raising=False)`.
- Detector: `test_launch_roundtrip.py::test_roundtrip_scenario_passes_with_a_stale_ambient_claude_pid`. It starts `sys.executable -c "pass"`, waits for it, and runs a child pytest of `test_roundtrip_scenario[compose-refusal]` with `CLAUDE_PID` set to that dead pid, so it reddens in CI as well as in the sandbox (E2).
- Raw red (the child's pytest output is quoted inside the assertion message; the decisive lines are kept, the long parametrize listing and the repeated source echo are elided as `...`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_roundtrip_scenario_passes_with_a_stale_ambient_claude_pid ________
...
>       assert done.returncode == 0, output
E       AssertionError: F                                                                        [100%]
E         ___________________ test_roundtrip_scenario[compose-refusal] ___________________
...
E         >       assert result["reason"] == "model-not-registry-known"
E         E       AssertionError: assert 'launch-seat-...-undetermined' == 'model-not-registry-known'
E         E         - model-not-registry-known
E         E         + launch-seat-instance-undetermined
E         FAILED plugins/superheroes/lib/tests/test_launch_roundtrip.py::test_roundtrip_scenario[compose-refusal]
E         1 failed in 57.23s
...
E       assert 1 == 0
FAILED plugins/superheroes/lib/tests/test_launch_roundtrip.py::test_roundtrip_scenario_passes_with_a_stale_ambient_claude_pid
1 failed in 58.89s
```

- Restore: inverse edit. Restored line quoted back (`grep -n`): `36:    monkeypatch.delenv("CLAUDE_PID", raising=False)`
- Raw green:

```
.                                                                        [100%]
1 passed in 1.99s
```

### G2' - fixture's fail-not-skip leg, merged fixture (axis: a failing probe with no sandbox marker fails with "refuses to skip", never skips)

- File: `proc_namespace.py`, `require_process_listing`, reached through `_proc_containment_guard`.
- Neutralization: `if process_listing_skip_allowed(environ, probe):` became `if True:` (the guard skips everywhere).
- Detector: `test_process_listing_2275.py::test_the_real_guard_fails_a_failing_probe_outside_the_sandbox` (real merged fixture, not shadowed). As in G2, the outcome hook still converts the skip into a setup ERROR, so the run exits 1; the detector reddens on the missing `refuses to skip` message.
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
...
>       assert "refuses to skip" in output, output
E       AssertionError: E                                                                        [100%]
E         ==================================== ERRORS ====================================
E         ________________________ ERROR at setup of test_marked _________________________
E         a process_listing test was skipped while the claude write sandbox condition does not hold, which is not allowed: a skip needs both SANDBOX_RUNTIME=1 and a failing ps probe; original skip reason: Skipped: claude write sandbox: the `ps -g <pgid> -o state=` probe fails here, so a process group cannot be listed and its liveness cannot be observed
...
E         ERROR test_child_process_listing.py::test_marked - a process_listing test was...
E         1 warning, 1 error in 0.02s
...
FAILED plugins/superheroes/lib/tests/test_process_listing_2275.py::test_the_real_guard_fails_a_failing_probe_outside_the_sandbox
1 failed in 0.97s
```

(elided: the PytestUnknownMarkWarning block the child prints because it runs with `-c /dev/null`.)

- Restore: inverse edit. Restored line quoted back: `117:    if process_listing_skip_allowed(environ, probe):`
- Raw green:

```
.                                                                        [100%]
1 passed in 1.01s
```
