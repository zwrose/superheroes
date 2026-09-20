# C14 layer 2 bite-proof — background attempt flow (#1273 WO-B2)

## background-launch-unacknowledged

- **axis:** unparseable acknowledgement refuses background-launch-unacknowledged
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_background_launch_refusals[-0-background-launch-unacknowledged]`

**raw red (exit 1):**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_claude_background_launch_refusals[-0-background-launch-unacknowledged] __

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-1929/test_claude_background_launch_0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x101ce5c40>
ack_stdout = '', launch_exit = 0, refusal = 'background-launch-unacknowledged'

    @pytest.mark.parametrize(
        "ack_stdout,launch_exit,refusal",
        [
            ("", 0, "background-launch-unacknowledged"),
            ("error: failed\n", 0, "background-launch-unacknowledged"),
            ("backgrounded · abcdefg\n", 0, "background-launch-unacknowledged"),
            ("backgrounded · %s\n" % _bg_launch_id(), 1, "background-launch-failed"),
        ],
    )
    def test_claude_background_launch_refusals(
        tmp_path, monkeypatch, ack_stdout, launch_exit, refusal,
    ):
        cfg, launch_id, _session_id, harness = _bg_harness(tmp_path, monkeypatch)
        harness["ack_stdout"] = ack_stdout
        harness["launch_exit"] = launch_exit
        repo_root = _repo(tmp_path)
        run_dir = str(tmp_path / ("bg-launch-%s" % refusal))
        opened = _plant_claude_background_journal(
            tmp_path, run_dir, repo_root, _reviewer_claude_seat(), config_dir=cfg,
        )
        _run_bg_engine_files(tmp_path, run_dir, opened)
        ended = _bg_attempt_ended(run_dir)
>       assert ended["refusal"] == refusal
E       AssertionError: assert 'background-session-unlisted' == 'background-l...nacknowledged'
E         
E         - background-launch-unacknowledged
E         + background-session-unlisted

plugins/superheroes/lib/tests/test_engine_dispatch.py:14738: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_background_launch_refusals[-0-background-launch-unacknowledged]
1 failed in 1.24s
```

**raw green:**

```
.                                                                        [100%]
1 passed in 1.06s
```

## background-launch-failed

- **axis:** non-zero launch child exit refuses background-launch-failed
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_background_launch_refusals[backgrounded \xb7 a1b2c3d4\n-1-background-launch-failed]`

**raw red (exit 1):**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_claude_background_launch_refusals[backgrounded \xb7 a1b2c3d4\n-1-background-launch-failed] _

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-1931/test_claude_background_launch_0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x1042d2ca0>
ack_stdout = 'backgrounded · a1b2c3d4\n', launch_exit = 1
refusal = 'background-launch-failed'

    @pytest.mark.parametrize(
        "ack_stdout,launch_exit,refusal",
        [
            ("", 0, "background-launch-unacknowledged"),
            ("error: failed\n", 0, "background-launch-unacknowledged"),
            ("backgrounded · abcdefg\n", 0, "background-launch-unacknowledged"),
            ("backgrounded · %s\n" % _bg_launch_id(), 1, "background-launch-failed"),
        ],
    )
    def test_claude_background_launch_refusals(
        tmp_path, monkeypatch, ack_stdout, launch_exit, refusal,
    ):
        cfg, launch_id, _session_id, harness = _bg_harness(tmp_path, monkeypatch)
        harness["ack_stdout"] = ack_stdout
        harness["launch_exit"] = launch_exit
        repo_root = _repo(tmp_path)
        run_dir = str(tmp_path / ("bg-launch-%s" % refusal))
        opened = _plant_claude_background_journal(
            tmp_path, run_dir, repo_root, _reviewer_claude_seat(), config_dir=cfg,
        )
        _run_bg_engine_files(tmp_path, run_dir, opened)
        ended = _bg_attempt_ended(run_dir)
>       assert ended["refusal"] == refusal
E       AssertionError: assert None == 'background-launch-failed'

plugins/superheroes/lib/tests/test_engine_dispatch.py:14738: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_background_launch_refusals[backgrounded \xb7 a1b2c3d4\n-1-background-launch-failed]
1 failed in 1.32s
```

**raw green:**

```
.                                                                        [100%]
1 passed in 1.06s
```

## background-session-unlisted

- **axis:** missing agents row refuses background-session-unlisted
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_background_session_unlisted_refused`

**raw red (exit 1):**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_claude_background_session_unlisted_refused ________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-1933/test_claude_background_session0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x1027ebbb0>

    def test_claude_background_session_unlisted_refused(tmp_path, monkeypatch):
        cfg, launch_id, _session_id, harness = _bg_harness(tmp_path, monkeypatch, agents_rows=[])
        repo_root = _repo(tmp_path)
        run_dir = str(tmp_path / "bg-unlisted")
        opened = _plant_claude_background_journal(
            tmp_path, run_dir, repo_root, _reviewer_claude_seat(), config_dir=cfg,
        )
        _run_bg_engine_files(tmp_path, run_dir, opened)
        ended = _bg_attempt_ended(run_dir)
>       assert ended["refusal"] == "background-session-unlisted"
E       AssertionError: assert 'background-s...ithout-result' == 'background-session-unlisted'
E         
E         - background-session-unlisted
E         + background-session-ended-without-result

plugins/superheroes/lib/tests/test_engine_dispatch.py:14752: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_background_session_unlisted_refused
1 failed in 1.08s
```

**raw green:**

```
.                                                                        [100%]
1 passed in 0.87s
```

## background-transcript-ambiguous

- **axis:** multiple transcript globs refuses background-transcript-ambiguous
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_background_transcript_ambiguous_refused`

**raw red (exit 1):**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_claude_background_transcript_ambiguous_refused ______________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-1935/test_claude_background_transcr0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x10430f2e0>

    def test_claude_background_transcript_ambiguous_refused(tmp_path, monkeypatch):
        cfg, launch_id, session_id, _harness = _bg_harness(tmp_path, monkeypatch)
        repo_root = _repo(tmp_path)
        run_dir = str(tmp_path / "bg-ambiguous")
        opened = _plant_claude_background_journal(
            tmp_path, run_dir, repo_root, _reviewer_claude_seat(), config_dir=cfg,
        )
        _write_bg_transcript(cfg, session_id, _bg_transcript_rows({"ok": True}))
        alt = os.path.join(cfg, "projects", "other", session_id + ".jsonl")
        os.makedirs(os.path.dirname(alt), exist_ok=True)
        shutil.copyfile(
            os.path.join(cfg, "projects", "mangled-cwd", session_id + ".jsonl"), alt,
        )
        _run_bg_engine_files(tmp_path, run_dir, opened, timeout=10)
        ended = _bg_attempt_ended(run_dir)
>       assert ended["refusal"] == "background-transcript-ambiguous"
E       AssertionError: assert None == 'background-transcript-ambiguous'

plugins/superheroes/lib/tests/test_engine_dispatch.py:14771: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_background_transcript_ambiguous_refused
1 failed in 1.01s
```

**raw green:**

```
.                                                                        [100%]
1 passed in 1.02s
```

## background-agents-unreadable

- **axis:** unreadable agents listing during poll refuses background-agents-unreadable
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_background_agents_unreadable_refused`

**raw red (exit 1):**

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_claude_background_agents_unreadable_refused ___________

    def test_claude_background_agents_unreadable_refused(tmp_path, monkeypatch):
        ...
>       assert ended["refusal"] == "background-agents-unreadable"
E       AssertionError: assert None == 'background-agents-unreadable'

plugins/superheroes/lib/tests/test_engine_dispatch.py:15130: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_background_agents_unreadable_refused
1 failed in 1.19s
```

**raw green:**

```
.                                                                        [100%]
1 passed in 1.06s
```

## background-session-ended-without-result

- **axis:** stopped session without result refuses background-session-ended-without-result
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_background_session_ended_without_result_refused`

**raw red (exit 1):**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_claude_background_session_ended_without_result_refused __________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-1937/test_claude_background_session0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x105c80b80>

    def test_claude_background_session_ended_without_result_refused(tmp_path, monkeypatch):
        cfg, launch_id, session_id, harness = _bg_harness(tmp_path, monkeypatch)
        harness["agents_rows"] = [_bg_agent_row(launch_id, session_id, state="stopped")]
        repo_root = _repo(tmp_path)
        run_dir = str(tmp_path / "bg-ended")
        opened = _plant_claude_background_journal(
            tmp_path, run_dir, repo_root, _reviewer_claude_seat(), config_dir=cfg,
        )
        _run_bg_engine_files(tmp_path, run_dir, opened, timeout=10)
        ended = _bg_attempt_ended(run_dir)
>       assert ended["refusal"] == "background-session-ended-without-result"
E       AssertionError: assert None == 'background-session-ended-without-result'

plugins/superheroes/lib/tests/test_engine_dispatch.py:14784: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_background_session_ended_without_result_refused
1 failed in 1.19s
```

**raw green:**

```
.                                                                        [100%]
1 passed in 0.97s
```

## transcript admission gate

> **Proof upgraded (r2).** The detector named below is an uncommitted one-off `python3 -c` assert,
> which is a session artifact rather than a durable detector (CONVENTIONS §12.1). This element is
> now carried by a committed test, `test_stdout_delivery_gate_transcript_branch`, proved as E1-E3
> in `c14_l2b_r2_gate_coverage.md` and re-run at the final head as elements 24-26 of
> `c14_l2b_r2_final_head_rerun.md`. The entry below stands as the historical receipt.

- **axis:** transcript absent must refuse at _stdout_delivery_gate
- **detector:** `inline gate assert`

**raw red (exit 1):**

```
Traceback (most recent call last):
  File "<string>", line 9, in <module>
AssertionError
```

**raw green:**

```

```

## stop-and-confirm

> **Axis restated at the final head (r2).** `stop-failed` is not an outcome of `_background_stop`
> at this head: WO-2 settled the outcome set at `stopped` / `already-ended` / `stop-unconfirmed`.
> The live axis is *a stop that cannot be confirmed is recorded `stop-unconfirmed`, never
> `stopped`*, re-run as element 7 of `c14_l2b_r2_final_head_rerun.md`. The red below is the
> historical receipt from the head that shipped it.

- **axis:** stop failure surfaces stop-failed not stopped
- **detector:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_background_stop_records_stopped_already_ended_and_stop_failed`

**raw red (exit 1):**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_claude_background_stop_records_stopped_already_ended_and_stop_failed ___

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-1939/test_claude_background_stop_re0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x101dab1c0>

    def test_claude_background_stop_records_stopped_already_ended_and_stop_failed(
        tmp_path, monkeypatch,
    ):
        cfg, launch_id, session_id, harness = _bg_harness(tmp_path, monkeypatch)
        cwd = os.path.realpath(_repo(tmp_path))
    
        harness["agents_rows"] = [_bg_agent_row(launch_id, session_id)]
    
        def cli_stopped(args, config_dir, cwd=None, timeout=30):
            if args[:1] == ["agents"]:
                return 0, json.dumps(harness["agents_rows"]), ""
            harness["agents_rows"] = []
            return 0, "", ""
    
        monkeypatch.setattr(ED, "_claude_cli", cli_stopped)
        assert ED._background_stop(launch_id, cfg, cwd) == "stopped"
    
        harness["agents_rows"] = []
    
        def cli_already_ended(args, config_dir, cwd=None, timeout=30):
            if args[:1] == ["agents"]:
                return 0, json.dumps(harness["agents_rows"]), ""
            return 0, "", ""
    
        monkeypatch.setattr(ED, "_claude_cli", cli_already_ended)
        assert ED._background_stop(launch_id, cfg, cwd) == "already-ended"
    
        harness["agents_rows"] = [_bg_agent_row(launch_id, session_id)]
    
        def cli_stop_failed(args, config_dir, cwd=None, timeout=30):
            if args[:1] == ["agents"]:
                return 0, json.dumps(harness["agents_rows"]), ""
            return 1, "", "stop failed"
    
        monkeypatch.setattr(ED, "_claude_cli", cli_stop_failed)
>       assert ED._background_stop(launch_id, cfg, cwd) == "stop-failed"
E       AssertionError: assert 'stopped' == 'stop-failed'
E         
E         - stop-failed
E         + stopped

plugins/superheroes/lib/tests/test_engine_dispatch.py:14873: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_background_stop_records_stopped_already_ended_and_stop_failed
1 failed in 1.23s
```

**raw green:**

```
.                                                                        [100%]
1 passed in 1.19s
```

