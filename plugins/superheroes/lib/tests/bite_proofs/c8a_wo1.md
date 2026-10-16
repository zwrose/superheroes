# C8a WO1 bite-proof: the check session and the failed-check marker

Bite-proof record for the detectors C8a WO1 adds or changes in `test_cloud_check.py`, `test_cloud_setup.py` and `test_launcher_cloud.py` (issue #1749 follow-ups C4 FU7, FU8, FU9, C5 FU2, FU3, FU6).

**Run command.** `scripts/pinned-python -B <nosign_pytest.py> <node> -q -p no:cacheprovider`, where `nosign_pytest.py` runs pytest with commit signing turned off through git's per-process config override. The harness's `UV_NATIVE_TLS` deprecation line is filtered from each capture; every pytest line is as printed. Each neutralization is a targeted Edit, each restore is the inverse Edit, and each green is the same node.

## Summary

| Element | Axis | Proving test | Verdict |
|---|---|---|---|
| FU7-a | the marker clear is guarded by the record write's own answer (`written`) | `test_a_record_write_that_fails_leaves_an_existing_marker_in_place` | proven |
| FU8-a | an inherited `CLAUDE_CODE_EFFORT_LEVEL` outranks the `--effort` flag, so `start` overwrites it and drops the reflection variable | `test_start_pins_the_cells_effort_over_an_inherited_effort_variable` | proven |
| FU9-a | `judge` falls back to `cloud_setup.launching_account(env, cwd)` when `account` is None | `test_judge_resolves_the_launching_account_itself_when_none_is_given` | proven |
| C5FU2-a | a well-formed marker that exists refuses switching cloud builds on | `test_switch_on_refused_when_the_last_check_failed_and_stores_nothing` | proven |
| C5FU2-b | the guard reaches the marker through `cloud_setup` only (source-text check) | `test_project_config_does_not_import_cloud_check` | proven |
| C5FU3-a | bytes still buffered in the pty master when the signal lands are kept, not lost | `test_a_sigterm_keeps_the_bytes_the_child_wrote_after_the_read_that_saw_the_signal` | proven |
| C9 | the base check asks the server (`_base_on_remote` calls `_gh_commit_lookup`) | `test_the_default_gh_call_asks_the_commits_endpoint` | not proven: unrunnable here, see `wo_c_place_call.md` C9 |
| C10 | only the HTTP 422 no-commit answer reads as absent | `test_only_the_422_no_commit_answer_is_absent` | not proven: unrunnable here, see `wo_c_place_call.md` C10 |
| C11 | an unchecked remote refuses | `test_cloud_base_refusal_maps_the_round_trip_to_its_token` | proven; raw red and green in `wo_c_place_call.md` C11 |

## FU7-a: the failed-check marker is cleared only after a written record

- **Guarded element and axis.** the marker clear is guarded by the record write's own answer (`written`).
- **Neutralization applied.** In `cloud_check.py`, `done = written and _remove_failed_check(` replaced with `done = _remove_failed_check(`.
- **Node.** `plugins/superheroes/lib/tests/test_cloud_check.py::test_a_record_write_that_fails_leaves_an_existing_marker_in_place`
- **Note.** The `raises` case passes under the neutralization (control jumps past the line); the `refused` and `none` cases go red.
- **Red:**

```
.FF                                                                      [100%]
=================================== FAILURES ===================================
__ test_a_record_write_that_fails_leaves_an_existing_marker_in_place[refused] __

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-57/test_a_record_write_that_fails1')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f500ba92b40>
record_fn = <function <lambda> at 0x7f500b76aac0>

    @pytest.mark.parametrize("record_fn", [
        _record_write_that_raises,
        lambda *a, **k: {"action": "refused"},
        lambda *a, **k: None,
    ], ids=["raises", "refused", "none"])
    def test_a_record_write_that_fails_leaves_an_existing_marker_in_place(
            tmp_path, monkeypatch, record_fn):
        # axis: the marker is cleared only after a record write that reported written — see bite-proof record c8a_wo1.md
        local, cloud = _pair(tmp_path)
        assert _judge(local, _cloud_report(cloud, pluginVersion="0.0.1"))["action"] == "failed"
        before = open(_marker_path(local)).read()
        seen = []
        removals = []
        real_remove = CC._remove_failed_check
    
        def spying_remove(*a, **k):
            removals.append(a)
            return real_remove(*a, **k)
    
        monkeypatch.setattr(CC, "_remove_failed_check", spying_remove)
    
        def recording(*a, **k):
            # detector: a marker cleared before the record writer is called goes red here
            seen.append(os.path.exists(_marker_path(local)) and open(_marker_path(local)).read() == before)
            return record_fn(*a, **k)
    
        result = _judge(local, _ok_report(cloud), now=LATER, record_fn=recording)
        # detector: a failed record write that clears the failure marker goes red here
        assert seen == [True]
>       assert result["action"] == "failed" and "record" in result["failedParts"]
E       AssertionError: assert ('passed' == 'failed'
E         
E         - failed
E         + passed)

/home/user/c8a-wo1/plugins/superheroes/lib/tests/test_cloud_check.py:1162: AssertionError
___ test_a_record_write_that_fails_leaves_an_existing_marker_in_place[none] ____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-57/test_a_record_write_that_fails2')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f500b987d10>
record_fn = <function <lambda> at 0x7f500b76ab60>

    @pytest.mark.parametrize("record_fn", [
        _record_write_that_raises,
        lambda *a, **k: {"action": "refused"},
        lambda *a, **k: None,
    ], ids=["raises", "refused", "none"])
    def test_a_record_write_that_fails_leaves_an_existing_marker_in_place(
            tmp_path, monkeypatch, record_fn):
        # axis: the marker is cleared only after a record write that reported written — see bite-proof record c8a_wo1.md
        local, cloud = _pair(tmp_path)
        assert _judge(local, _cloud_report(cloud, pluginVersion="0.0.1"))["action"] == "failed"
        before = open(_marker_path(local)).read()
        seen = []
        removals = []
        real_remove = CC._remove_failed_check
    
        def spying_remove(*a, **k):
            removals.append(a)
            return real_remove(*a, **k)
    
        monkeypatch.setattr(CC, "_remove_failed_check", spying_remove)
    
        def recording(*a, **k):
            # detector: a marker cleared before the record writer is called goes red here
            seen.append(os.path.exists(_marker_path(local)) and open(_marker_path(local)).read() == before)
            return record_fn(*a, **k)
    
        result = _judge(local, _ok_report(cloud), now=LATER, record_fn=recording)
        # detector: a failed record write that clears the failure marker goes red here
        assert seen == [True]
>       assert result["action"] == "failed" and "record" in result["failedParts"]
E       AssertionError: assert ('passed' == 'failed'
E         
E         - failed
E         + passed)

/home/user/c8a-wo1/plugins/superheroes/lib/tests/test_cloud_check.py:1162: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check.py::test_a_record_write_that_fails_leaves_an_existing_marker_in_place[refused]
FAILED plugins/superheroes/lib/tests/test_cloud_check.py::test_a_record_write_that_fails_leaves_an_existing_marker_in_place[none]
2 failed, 1 passed in 2.22s
```

- **Restore.** The inverse Edit. Restored lines, quoted back from `cloud_check.py`:

```
done = written and _remove_failed_check(cwd, who, root, started)
```

- **Green:**

```
...                                                                      [100%]
3 passed in 2.10s
```

## FU8-a: the check session's environment pins the cell's effort

- **Guarded element and axis.** an inherited `CLAUDE_CODE_EFFORT_LEVEL` outranks the `--effort` flag, so `start` overwrites it and drops the reflection variable.
- **Neutralization applied.** In `cloud_check.py`, `launcher.pin_effort(child_env, cell["effort"])` replaced with `# launcher.pin_effort(child_env, cell["effort"])`.
- **Node.** `plugins/superheroes/lib/tests/test_cloud_check.py::test_start_pins_the_cells_effort_over_an_inherited_effort_variable`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_start_pins_the_cells_effort_over_an_inherited_effort_variable ______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-60/test_start_pins_the_cells_effo0')

    def test_start_pins_the_cells_effort_over_an_inherited_effort_variable(tmp_path):
        # axis: the check session's environment carries the cell's effort, since an inherited variable outranks the flag — see bite-proof record c8a_wo1.md
        local, _ = _pair(tmp_path)
        spawner = Spawner()
        env = dict(local.env, CLAUDE_CODE_EFFORT_LEVEL="low", CLAUDE_EFFORT="low")
        assert _start(local, spawner, env=env)["action"] == "started"
        cell = model_registry.resolve_dispatch("mechanical", "claude", None)
        child_env = spawner.calls[0]["env"]
>       assert child_env["CLAUDE_CODE_EFFORT_LEVEL"] == cell["effort"] != "low"
E       AssertionError: assert 'low' == 'medium'
E         
E         - medium
E         + low

/home/user/c8a-wo1/plugins/superheroes/lib/tests/test_cloud_check.py:1419: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check.py::test_start_pins_the_cells_effort_over_an_inherited_effort_variable
1 failed in 1.13s
```

- **Restore.** The inverse Edit. Restored lines, quoted back from `cloud_check.py`:

```
    launcher.pin_effort(child_env, cell["effort"])
```

- **Green:**

```
.                                                                        [100%]
1 passed in 1.24s
```

## FU9-a: a judgment given no account resolves the launching account itself

- **Guarded element and axis.** `judge` falls back to `cloud_setup.launching_account(env, cwd)` when `account` is None.
- **Neutralization applied.** In `cloud_check.py`, `who = account if account is not None else cloud_setup.launching_account(env, cwd)` replaced with `who = account`.
- **Node.** `plugins/superheroes/lib/tests/test_cloud_check.py::test_judge_resolves_the_launching_account_itself_when_none_is_given`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_judge_resolves_the_launching_account_itself_when_none_is_given ______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-67/test_judge_resolves_the_launch0')

    def test_judge_resolves_the_launching_account_itself_when_none_is_given(tmp_path):
        # axis: a judgment given no account reads the launching account itself and records against it — see bite-proof record c8a_wo1.md
        local, cloud = _pair(tmp_path)
        config = local.env["CLAUDE_CONFIG_DIR"]
        os.makedirs(config, exist_ok=True)
        with open(os.path.join(config, ".claude.json"), "w", encoding="utf-8") as fh:
            json.dump({"oauthAccount": {"accountUuid": ACCOUNT}}, fh)
        result = CC.judge(local.cwd, CC.report_line(_ok_report(cloud)), environment=ENV_ID,
                          nonce=NONCE, root=local.root, env=local.env, now=NOW, project_name="demo")
>       assert result["action"] == "passed"
E       AssertionError: assert 'failed' == 'passed'
E         
E         - passed
E         + failed

/home/user/c8a-wo1/plugins/superheroes/lib/tests/test_cloud_check.py:602: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check.py::test_judge_resolves_the_launching_account_itself_when_none_is_given
1 failed in 1.05s
```

- **Restore.** The inverse Edit. Restored lines, quoted back from `cloud_check.py`:

```
    who = account if account is not None else cloud_setup.launching_account(env, cwd)
```

- **Green:**

```
.                                                                        [100%]
1 passed in 1.10s
```

## C5FU2-a: the switch-on guard reads the failed-check marker

- **Guarded element and axis.** a well-formed marker that exists refuses switching cloud builds on.
- **Neutralization applied.** In `project_config.py`, `check_failed = cloud_setup.read_failed_check(cwd, account, root=root) is not None` replaced with `check_failed = False`.
- **Node.** `plugins/superheroes/lib/tests/test_cloud_setup.py::test_switch_on_refused_when_the_last_check_failed_and_stores_nothing`
- **Note.** The marker-present test already existed (it writes a well-formed marker with `CC._write_failed_check`); no fourth change was needed in `test_cloud_setup.py`.
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_switch_on_refused_when_the_last_check_failed_and_stores_nothing _____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-70/test_switch_on_refused_when_th0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f90189108f0>

    def test_switch_on_refused_when_the_last_check_failed_and_stores_nothing(tmp_path, monkeypatch):
        # axis: a failed-check marker that is present keeps cloud builds from switching on — see bite-proof record wo_d_place_call
        repo, store = _setup_repo(tmp_path)
        _check(repo, store)
        assert CC._write_failed_check(repo, ACCOUNT, store, ENVIRONMENT, ["version"], 0) is True
        assert CS.REASON_CHECK_FAILED == "cloud-check-failed"
>       _refused_for_a_failed_check(repo, store, monkeypatch)

/home/user/c8a-wo1/plugins/superheroes/lib/tests/test_cloud_setup.py:190: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-70/test_switch_on_refused_when_th0'
store = '/tmp/claude-0/pytest-of-root/pytest-70/test_switch_on_refused_when_th0/store'
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f90189108f0>

    def _refused_for_a_failed_check(repo, store, monkeypatch):
        got = PC.set_item(repo, "cloudBuilds", True, root=store, account=ACCOUNT, project_name="fixture")
>       assert got == {
            "action": "refused",
            "reason": CS.REASON_CHECK_FAILED,
            "message": CS.switch_message("check-failed", "fixture"),
        }
E       assert {'action': 'w...our machine.'} == {'action': 'r...heck again".'}
E         
E         Differing items:
E         {'message': 'Cloud builds are on for fixture. From the next launch, every build that can run in the cloud will.\n\nSay "this one local" at any launch to keep a build on your machine.'} != {'message': 'Cloud builds can\'t be switched on yet: the last check of this project\'s cloud setup failed. Fix what it named, then say "check again".'}
E         {'action': 'written'} != {'action': 'refused'}
E         Right contains 1 more item:
E         {'reason': 'cloud-check-failed'}
E         Use -v to get more diff

/home/user/c8a-wo1/plugins/superheroes/lib/tests/test_cloud_setup.py:174: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup.py::test_switch_on_refused_when_the_last_check_failed_and_stores_nothing
1 failed in 1.32s
```

- **Restore.** The inverse Edit. Restored lines, quoted back from `project_config.py`:

```
                check_failed = cloud_setup.read_failed_check(cwd, account, root=root) is not None
```

- **Green:**

```
.                                                                        [100%]
1 passed in 0.75s
```

## C5FU2-b: `project_config.py` does not import `cloud_check`

- **Guarded element and axis.** the guard reaches the marker through `cloud_setup` only (source-text check).
- **Neutralization applied.** In `project_config.py`, `try: # axis: a failed-check marker that is present` replaced with `try: import cloud_check # axis: a failed-check marker that is present`.
- **Node.** `plugins/superheroes/lib/tests/test_cloud_setup.py::test_project_config_does_not_import_cloud_check`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_project_config_does_not_import_cloud_check ________________

    def test_project_config_does_not_import_cloud_check():
        # axis: the switch-on guard reads the marker through cloud_setup and never imports cloud_check — see bite-proof record c8a_wo1.md
        with open(os.path.join(_LIB, "project_config.py"), encoding="utf-8") as fh:
            source = fh.read()
>       assert "import cloud_check" not in source
E       AssertionError: assert 'import cloud_check' not in '#!/usr/bin/...argv[1:]))\n'
E         
E         'import cloud_check' is contained here:
E                     import cloud_check
E                           # axis: a failed-check marker that is present, or damaged, or cannot be read keeps cloud builds from switching on — see bite-proof record wo_d_place_call
E                           check_failed = cloud_setup.read_failed_check(cwd, account, root=root) is not None
E                       except Exception:
E                           # axis: a marker read that raises refuses the switch-on, never proceeds — see bite-proof record wo_d_place_call...
E         
E         ...Full output truncated (821 lines hidden), use '-vv' to show

/home/user/c8a-wo1/plugins/superheroes/lib/tests/test_cloud_setup.py:230: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup.py::test_project_config_does_not_import_cloud_check
1 failed in 0.31s
```

- **Restore.** The inverse Edit. Restored lines, quoted back from `project_config.py`:

```
            try:
                # axis: a failed-check marker that is present
```

- **Green:**

```
.                                                                        [100%]
1 passed in 0.40s
```

## C5FU3-a: the read loop drains the pty before raising on a signal

- **Guarded element and axis.** bytes still buffered in the pty master when the signal lands are kept, not lost.
- **Neutralization applied.** In `launcher.py`, `if term_state["pending"]: _drain_pty(master, chunks) raise _LauncherTerminated() remaining = deadline - time.monotonic()` replaced with `if term_state["pending"]: # _drain_pty(master, chunks) raise _LauncherTerminated() remaining = deadline - time.monotonic()`.
- **Node.** `plugins/superheroes/lib/tests/test_launcher_cloud.py::test_a_sigterm_keeps_the_bytes_the_child_wrote_after_the_read_that_saw_the_signal`
- **Note.** Both parametrizations (real pty and the pipe stand-in) went red and green.
- **Red:**

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_a_sigterm_keeps_the_bytes_the_child_wrote_after_the_read_that_saw_the_signal[real-pty] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-74/test_a_sigterm_keeps_the_bytes0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f2987737170>
terminal = True

    def test_a_sigterm_keeps_the_bytes_the_child_wrote_after_the_read_that_saw_the_signal(
        tmp_path, monkeypatch, terminal,
    ):
        # axis: bytes still buffered in the pty master when the signal lands are drained before the
        # raise, not lost — see bite-proof record c8a_wo1.md
        import os as _os
        import select as _select
        import signal as _signal
    
        gate = tmp_path / "go"
        real_read = _os.read
        sent = []
    
        def read_then_signal_then_open_the_gate(fd, length):
            data = real_read(fd, length)
            if not sent and b"head" in data:
                sent.append(fd)
                _os.kill(_os.getpid(), _signal.SIGTERM)
                # The child writes `tail` only once this file exists, which is after the signal is
                # recorded, so the line can never have been read ahead of the cancellation.
                gate.write_text("go")
                # Hold the return until `tail` is buffered in the master, so the test never races the
                # child: the loop then sees the signal with unread bytes waiting, whatever the load.
                _select.select([fd], [], [], 10)
            return data
    
        monkeypatch.setattr(L.os, "read", read_then_signal_then_open_the_gate)
        script = f"echo head; while [ ! -e {gate} ]; do sleep 0.01; done; echo tail; sleep 30"
        result = L.default_cloud_spawn(
            ["sh", "-c", script], str(tmp_path), str(tmp_path / "t.stdout"), dict(_os.environ), 20,
        )
        assert sent
        assert result["readError"] == "_LauncherTerminated"
        assert "head" in result["output"]
>       assert "tail" in result["output"]
E       AssertionError: assert 'tail' in 'head\r\n'

/home/user/c8a-wo1/plugins/superheroes/lib/tests/test_launcher_cloud.py:1632: AssertionError
_ test_a_sigterm_keeps_the_bytes_the_child_wrote_after_the_read_that_saw_the_signal[pipe-standin] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-74/test_a_sigterm_keeps_the_bytes1')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f2987734620>
terminal = False

    def test_a_sigterm_keeps_the_bytes_the_child_wrote_after_the_read_that_saw_the_signal(
        tmp_path, monkeypatch, terminal,
    ):
        # axis: bytes still buffered in the pty master when the signal lands are drained before the
        # raise, not lost — see bite-proof record c8a_wo1.md
        import os as _os
        import select as _select
        import signal as _signal
    
        gate = tmp_path / "go"
        real_read = _os.read
        sent = []
    
        def read_then_signal_then_open_the_gate(fd, length):
            data = real_read(fd, length)
            if not sent and b"head" in data:
                sent.append(fd)
                _os.kill(_os.getpid(), _signal.SIGTERM)
                # The child writes `tail` only once this file exists, which is after the signal is
                # recorded, so the line can never have been read ahead of the cancellation.
                gate.write_text("go")
                # Hold the return until `tail` is buffered in the master, so the test never races the
                # child: the loop then sees the signal with unread bytes waiting, whatever the load.
                _select.select([fd], [], [], 10)
            return data
    
        monkeypatch.setattr(L.os, "read", read_then_signal_then_open_the_gate)
        script = f"echo head; while [ ! -e {gate} ]; do sleep 0.01; done; echo tail; sleep 30"
        result = L.default_cloud_spawn(
            ["sh", "-c", script], str(tmp_path), str(tmp_path / "t.stdout"), dict(_os.environ), 20,
        )
        assert sent
        assert result["readError"] == "_LauncherTerminated"
        assert "head" in result["output"]
>       assert "tail" in result["output"]
E       AssertionError: assert 'tail' in 'head\n'

/home/user/c8a-wo1/plugins/superheroes/lib/tests/test_launcher_cloud.py:1632: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_a_sigterm_keeps_the_bytes_the_child_wrote_after_the_read_that_saw_the_signal[real-pty]
FAILED plugins/superheroes/lib/tests/test_launcher_cloud.py::test_a_sigterm_keeps_the_bytes_the_child_wrote_after_the_read_that_saw_the_signal[pipe-standin]
2 failed in 1.50s
```

- **Restore.** The inverse Edit. Restored lines, quoted back from `launcher.py`:

```
                    if term_state["pending"]:
                        _drain_pty(master, chunks)
                        raise _LauncherTerminated()
                    remaining = deadline - time.monotonic()
```

- **Green:**

```
..                                                                       [100%]
2 passed in 1.34s
```
