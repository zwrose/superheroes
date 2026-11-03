# Bite-proof record: #2323 item 1 the wave watch keeps watching a resumed (dormant) cloud lane

Detector under proof: `plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py`.
Guarded code: `plugins/superheroes/lib/wave_watch.py` and `plugins/superheroes/lib/launch_ledger.py`.
Base: `ef379cdd6a45aea25971f4927ff1fe595083c862`. Declared guarded-element set: the six below (one neutralization
and one red each, no grouping). Every neutralization was a targeted edit made with the Edit tool, undone by the
inverse Edit before the next element, each Edit and each run in its own tool call. No `git checkout`, `restore`,
`reset` or `stash` was used. Command prefix for every run below (worktree root):
`timeout 900 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py -q -p no:cacheprovider -k "<selector>"`.
The selector differs per run and is named in each entry; every selector is the planned one, none was changed.
Captures are raw pytest output, nothing trimmed (the `UV_NATIVE_TLS` warning line is kept) and nothing redacted
(temp paths only); each is under 32 KiB. The red runs exit 1 by design (bite-proof reds, not failures). The
production sites cite this record with `# axis:` comments. After each restore, before the green run,
`git diff HEAD --stat -- plugins/superheroes/lib/wave_watch.py plugins/superheroes/lib/launch_ledger.py` printed
nothing; that is the restore receipt for every entry, alongside the restored text quoted.

Disclosures:
- Element 4's selector `row8` selects 6 tests: the 5 `test_row8_a_progress_edit_inside_the_grace_or_reading_ended_is_not_activity`
  parametrizations and `test_row8_a_phase_reading_handed_back_but_resumed_is_activity`. Under this neutralization
  2 are red (the `handed back` and `handback` phases) and 4 pass (the in-grace `resumed` edit, the `parked` and
  `stopped` phases, and the `..._but_resumed_is_activity` test). The green run used the same selector.
- Element 5's selector `row6 or row8_a_progress` selects 6 tests: the 5 `row8_a_progress_edit...` parametrizations
  are red; the one `row6` test (`test_row6_a_dormant_lane_with_no_activity_after_its_basis_is_quiet_and_not_listed`)
  passes under this neutralization, so it does not discriminate it. The green run used the same selector.
- Element 1's selector selected 3 tests, all red.

## 1. Dormant lanes join the live set (`_derive_batch_lanes`, `wave_watch.py:631`)

- **Axis:** a started, outcome-terminal cloud lane that was not relaunched stays in the watch set as a dormant lane.
- **Neutralization:** `live_lanes[lid] = {**info, "dormantSince": basis}` (line 632) became `pass`.
- **Raw red** (`-k "row3_a_builder or row1_a_lane or row2_a_handback"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_row1_a_lane_resumed_by_a_progress_edit_and_handing_back_again_is_lane_terminal _

repo = '/tmp/claude-0/pytest-of-root/pytest-20/test_row1_a_lane_resumed_by_a_0/repo'

    def test_row1_a_lane_resumed_by_a_progress_edit_and_handing_back_again_is_lane_terminal(repo):
        _handed_back(repo, start_age=_LONG_AGO)
        comments = [
            _later(3, _ending("handback"), secs=-600),  # the first handback, before the basis
            _progress(9, 101, updated_age=-400, created_age=_LONG_AGO, phase="resumed: fixing the gate"),
            _later(7, _ending("handback"), secs=450),
        ]
>       launch = _only_launch(_run(repo, comments))
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2323-a/plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py:59: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': []}

    def _only_launch(result):
>       assert result["event"] == ww.EVENT_LANE_TERMINAL, result
E       AssertionError: {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': []}
E       assert 'timer' == 'lane-terminal'
E         
E         - lane-terminal
E         + timer

/home/user/wt-2323-a/plugins/superheroes/lib/tests/test_wave_watch_fix_order.py:60: AssertionError
_ test_row2_a_handback_after_the_basis_is_reported_with_no_progress_edit_at_all _

repo = '/tmp/claude-0/pytest-of-root/pytest-20/test_row2_a_handback_after_the0/repo'

    def test_row2_a_handback_after_the_basis_is_reported_with_no_progress_edit_at_all(repo):
        _handed_back(repo, start_age=_LONG_AGO)
        # The lane's progress comment still reads handback from its first ending, edited before the basis.
        comments = [
            _progress(9, 101, updated_age=600, created_age=_LONG_AGO, phase="handback"),
            _later(7, _ending("handback")),
        ]
>       launch = _only_launch(_run(repo, comments))
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-2323-a/plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py:70: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': []}

    def _only_launch(result):
>       assert result["event"] == ww.EVENT_LANE_TERMINAL, result
E       AssertionError: {'ok': True, 'event': 'timer', 'batchId': 'batch-cloud', 'degraded': []}
E       assert 'timer' == 'lane-terminal'
E         
E         - lane-terminal
E         + timer

/home/user/wt-2323-a/plugins/superheroes/lib/tests/test_wave_watch_fix_order.py:60: AssertionError
__________ test_row3_a_builder_note_after_the_basis_is_a_builder_note __________

repo = '/tmp/claude-0/pytest-of-root/pytest-20/test_row3_a_builder_note_after0/repo'

    def test_row3_a_builder_note_after_the_basis_is_a_builder_note(repo):
        _handed_back(repo, start_age=_LONG_AGO)
        result = _run(repo, [_later(7)])
>       assert result["event"] == ww.EVENT_BUILDER_NOTE
E       AssertionError: assert 'timer' == 'builder-note'
E         
E         - builder-note
E         + timer

/home/user/wt-2323-a/plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py:77: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py::test_row1_a_lane_resumed_by_a_progress_edit_and_handing_back_again_is_lane_terminal
FAILED plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py::test_row2_a_handback_after_the_basis_is_reported_with_no_progress_edit_at_all
FAILED plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py::test_row3_a_builder_note_after_the_basis_is_a_builder_note
3 failed, 19 deselected in 1.86s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored lines, `            # axis: a started, outcome-terminal cloud lane that was not relaunched stays in the watch set as a dormant lane — see bite-proof record i2323_resumed_lane.md` / `            live_lanes[lid] = {**info, "dormantSince": basis}`; the `git diff HEAD --stat` over both guarded files printed nothing.
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
...                                                                      [100%]
3 passed, 19 deselected in 1.06s
```

## 2. The relaunch exclusion (`_dormant_basis`, `wave_watch.py:650`)

- **Axis:** a lane relaunched on its issue, in any batch, is never resumed; the newer launch is the one watched.
- **Neutralization:** the `return None` at line 654, inside the relaunch loop, became `continue`.
- **Raw red** (`-k "row9 or test_e2"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_row9_a_newer_launch_on_the_same_issue_in_another_batch_makes_the_older_lane_not_dormant _

repo = '/tmp/claude-0/pytest-of-root/pytest-22/test_row9_a_newer_launch_on_th0/repo'

    def test_row9_a_newer_launch_on_the_same_issue_in_another_batch_makes_the_older_lane_not_dormant(repo):
        _handed_back(repo, start_age=_LONG_AGO)
        newer = [_later(7, _ending("handback")), _later(8, secs=40)]
        # Control: without the newer launch the older lane is resumed and reports the handback.
        assert _only_launch(_run(repo, newer))["commentId"] == 7
        ll.append(repo, _reserved(
            "cloud-b", 101, "plugins/cloud-101", repo, batchId="other-batch",
            place=ll.PLACE_CLOUD, cloudEnvironment="env-1", pluginVersion="1.2.3", ts=time.time(),
        ))
        result = _run(repo, newer)
>       assert result["event"] == ww.EVENT_TIMER
E       AssertionError: assert 'lane-terminal' == 'timer'
E         
E         - timer
E         + lane-terminal

/home/user/wt-2323-a/plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py:154: AssertionError
___ test_e2_a_launch_reserved_later_on_the_issue_in_any_batch_means_no_basis ___

    def test_e2_a_launch_reserved_later_on_the_issue_in_any_batch_means_no_basis():
        later = {"b": {"issue": 101, "reservedTs": 101.0, "batchId": "other"}}
>       assert ww._dormant_basis("a", _dormant_info(), later) is None
E       AssertionError: assert 500.0 is None
E        +  where 500.0 = <function _dormant_basis at 0x7f7e3d08d300>('a', {'place': 'cloud', 'started': True, 'terminal': True, 'terminalKind': 'outcome', ...}, {'b': {'issue': 101, 'reservedTs': 101.0, 'batchId': 'other'}})
E        +    where <function _dormant_basis at 0x7f7e3d08d300> = ww._dormant_basis
E        +    and   {'place': 'cloud', 'started': True, 'terminal': True, 'terminalKind': 'outcome', ...} = _dormant_info()

/home/user/wt-2323-a/plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py:244: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py::test_row9_a_newer_launch_on_the_same_issue_in_another_batch_makes_the_older_lane_not_dormant
FAILED plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py::test_e2_a_launch_reserved_later_on_the_issue_in_any_batch_means_no_basis
2 failed, 20 deselected in 0.85s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `            return None` (directly under `and _finite_number(other.get("reservedTs")) and other["reservedTs"] > reserved):`); the `git diff HEAD --stat` over both guarded files printed nothing.
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..                                                                       [100%]
2 passed, 20 deselected in 0.83s
```

## 3. The basis window (`_in_window`, `wave_watch.py:1743`)

- **Axis:** a dormant lane's comments from before its basis are not its own, so an old handback or note never re-fires.
- **Neutralization:** `if "dormantSince" in info and key[0] < info["dormantSince"]:` (line 1744) became `if False and "dormantSince" in info and key[0] < info["dormantSince"]:`.
- **Raw red** (`-k "row7_a_handback_created or row5_two"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_row5_two_activity_only_cycles_then_a_vet_amendment_moves_the_basis_for_the_third _

repo = '/tmp/claude-0/pytest-of-root/pytest-24/test_row5_two_activity_only_cy0/repo'

    def test_row5_two_activity_only_cycles_then_a_vet_amendment_moves_the_basis_for_the_third(repo):
        _dormant_at(repo, 3000)
        cycles = [_later(5, _ending("handback"), secs=-2000), _later(6, _ending("handback"), secs=-1000)]
        # Two handbacks after the recorded outcome, neither answered: the newest one fires, not the first.
        assert _only_launch(_run(repo, cycles))["commentId"] == 6
        # The advisor vets the resumed handback: the amendment moves the basis past both.
        _amend_at(repo, "cloud-a", "ready", 500)
>       assert _run(repo, cycles)["event"] == ww.EVENT_TIMER
E       AssertionError: assert 'lane-terminal' == 'timer'
E         
E         - timer
E         + lane-terminal

/home/user/wt-2323-a/plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py:99: AssertionError
________ test_row7_a_handback_created_before_the_basis_is_not_reported _________

repo = '/tmp/claude-0/pytest-of-root/pytest-24/test_row7_a_handback_created_b0/repo'

    def test_row7_a_handback_created_before_the_basis_is_not_reported(repo):
        _dormant_at(repo, 100)
        result = _run(repo, [_later(3, _ending("handback"), secs=-500), _later(4, secs=-400)])
>       assert result["event"] == ww.EVENT_TIMER
E       AssertionError: assert 'lane-terminal' == 'timer'
E         
E         - timer
E         + lane-terminal

/home/user/wt-2323-a/plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py:118: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py::test_row5_two_activity_only_cycles_then_a_vet_amendment_moves_the_basis_for_the_third
FAILED plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py::test_row7_a_handback_created_before_the_basis_is_not_reported
2 failed, 20 deselected in 1.21s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `    if "dormantSince" in info and key[0] < info["dormantSince"]:`; the `git diff HEAD --stat` over both guarded files printed nothing.
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..                                                                       [100%]
2 passed, 20 deselected in 1.06s
```

## 4. The `hand`-word exclusion (`_dormant_active`'s progress clause, `wave_watch.py:1876`)

- **Axis:** a progress edit whose phase reads handed back is the lane ending again, not working again, so it does not make a dormant lane active.
- **Neutralization:** `and not _phase_reads_handed_back(progress_entry.get("phase"))):` (line 1877) became `and True):`.
- **Raw red** (`-k row8`; 2 red, 4 passing, see the disclosure above):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.FF...                                                                   [100%]
=================================== FAILURES ===================================
_ test_row8_a_progress_edit_inside_the_grace_or_reading_ended_is_not_activity[-400-handed back] _

repo = '/tmp/claude-0/pytest-of-root/pytest-26/test_row8_a_progress_edit_insi1/repo'
updated_age = -400, phase = 'handed back'

    @pytest.mark.parametrize("updated_age, phase", [
        (-200, "resumed: fixing the gate"),  # inside the grace window
        (-400, "handed back"),
        (-400, "handback"),
        (-400, "parked: waiting on the owner"),
        (-400, "stopped"),
    ])
    def test_row8_a_progress_edit_inside_the_grace_or_reading_ended_is_not_activity(repo, updated_age, phase):
        _handed_back(repo, start_age=_LONG_AGO)
        # A future-dated progress comment would read a watched lane stale at once (negative age).
        result = _run(repo, [_progress(9, 101, updated_age=updated_age, created_age=_LONG_AGO, phase=phase)])
>       assert result["event"] == ww.EVENT_TIMER
E       AssertionError: assert 'lane-stale' == 'timer'
E         
E         - timer
E         + lane-stale

/home/user/wt-2323-a/plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py:133: AssertionError
_ test_row8_a_progress_edit_inside_the_grace_or_reading_ended_is_not_activity[-400-handback] _

repo = '/tmp/claude-0/pytest-of-root/pytest-26/test_row8_a_progress_edit_insi2/repo'
updated_age = -400, phase = 'handback'

    @pytest.mark.parametrize("updated_age, phase", [
        (-200, "resumed: fixing the gate"),  # inside the grace window
        (-400, "handed back"),
        (-400, "handback"),
        (-400, "parked: waiting on the owner"),
        (-400, "stopped"),
    ])
    def test_row8_a_progress_edit_inside_the_grace_or_reading_ended_is_not_activity(repo, updated_age, phase):
        _handed_back(repo, start_age=_LONG_AGO)
        # A future-dated progress comment would read a watched lane stale at once (negative age).
        result = _run(repo, [_progress(9, 101, updated_age=updated_age, created_age=_LONG_AGO, phase=phase)])
>       assert result["event"] == ww.EVENT_TIMER
E       AssertionError: assert 'lane-stale' == 'timer'
E         
E         - timer
E         + lane-stale

/home/user/wt-2323-a/plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py:133: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py::test_row8_a_progress_edit_inside_the_grace_or_reading_ended_is_not_activity[-400-handed back]
FAILED plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py::test_row8_a_progress_edit_inside_the_grace_or_reading_ended_is_not_activity[-400-handback]
2 failed, 4 passed, 16 deselected in 1.73s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `            and not _phase_reads_handed_back(progress_entry.get("phase"))):`; the `git diff HEAD --stat` over both guarded files printed nothing.
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
......                                                                   [100%]
6 passed, 16 deselected in 1.53s
```

## 5. The inactive-dormant exclusion from the stale set (`_apply_cloud_progress`, `wave_watch.py:2077`)

- **Axis:** a dormant lane that is not active is never stale, whatever its old progress comment says.
- **Neutralization:** `and ("dormantSince" not in live_lanes[lid] or lid in active_dormant)` (line 2081) became `and ("dormantSince" not in live_lanes[lid] or True)`.
- **Raw red** (`-k "row6 or row8_a_progress"`; 5 red, 1 passing, see the disclosure above):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.FFFFF                                                                   [100%]
=================================== FAILURES ===================================
_ test_row8_a_progress_edit_inside_the_grace_or_reading_ended_is_not_activity[-200-resumed: fixing the gate] _

repo = '/tmp/claude-0/pytest-of-root/pytest-28/test_row8_a_progress_edit_insi0/repo'
updated_age = -200, phase = 'resumed: fixing the gate'

    @pytest.mark.parametrize("updated_age, phase", [
        (-200, "resumed: fixing the gate"),  # inside the grace window
        (-400, "handed back"),
        (-400, "handback"),
        (-400, "parked: waiting on the owner"),
        (-400, "stopped"),
    ])
    def test_row8_a_progress_edit_inside_the_grace_or_reading_ended_is_not_activity(repo, updated_age, phase):
        _handed_back(repo, start_age=_LONG_AGO)
        # A future-dated progress comment would read a watched lane stale at once (negative age).
        result = _run(repo, [_progress(9, 101, updated_age=updated_age, created_age=_LONG_AGO, phase=phase)])
>       assert result["event"] == ww.EVENT_TIMER
E       AssertionError: assert 'lane-stale' == 'timer'
E         
E         - timer
E         + lane-stale

/home/user/wt-2323-a/plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py:133: AssertionError
_ test_row8_a_progress_edit_inside_the_grace_or_reading_ended_is_not_activity[-400-handed back] _

repo = '/tmp/claude-0/pytest-of-root/pytest-28/test_row8_a_progress_edit_insi1/repo'
updated_age = -400, phase = 'handed back'

    @pytest.mark.parametrize("updated_age, phase", [
        (-200, "resumed: fixing the gate"),  # inside the grace window
        (-400, "handed back"),
        (-400, "handback"),
        (-400, "parked: waiting on the owner"),
        (-400, "stopped"),
    ])
    def test_row8_a_progress_edit_inside_the_grace_or_reading_ended_is_not_activity(repo, updated_age, phase):
        _handed_back(repo, start_age=_LONG_AGO)
        # A future-dated progress comment would read a watched lane stale at once (negative age).
        result = _run(repo, [_progress(9, 101, updated_age=updated_age, created_age=_LONG_AGO, phase=phase)])
>       assert result["event"] == ww.EVENT_TIMER
E       AssertionError: assert 'lane-stale' == 'timer'
E         
E         - timer
E         + lane-stale

/home/user/wt-2323-a/plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py:133: AssertionError
_ test_row8_a_progress_edit_inside_the_grace_or_reading_ended_is_not_activity[-400-handback] _

repo = '/tmp/claude-0/pytest-of-root/pytest-28/test_row8_a_progress_edit_insi2/repo'
updated_age = -400, phase = 'handback'

    @pytest.mark.parametrize("updated_age, phase", [
        (-200, "resumed: fixing the gate"),  # inside the grace window
        (-400, "handed back"),
        (-400, "handback"),
        (-400, "parked: waiting on the owner"),
        (-400, "stopped"),
    ])
    def test_row8_a_progress_edit_inside_the_grace_or_reading_ended_is_not_activity(repo, updated_age, phase):
        _handed_back(repo, start_age=_LONG_AGO)
        # A future-dated progress comment would read a watched lane stale at once (negative age).
        result = _run(repo, [_progress(9, 101, updated_age=updated_age, created_age=_LONG_AGO, phase=phase)])
>       assert result["event"] == ww.EVENT_TIMER
E       AssertionError: assert 'lane-stale' == 'timer'
E         
E         - timer
E         + lane-stale

/home/user/wt-2323-a/plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py:133: AssertionError
_ test_row8_a_progress_edit_inside_the_grace_or_reading_ended_is_not_activity[-400-parked: waiting on the owner] _

repo = '/tmp/claude-0/pytest-of-root/pytest-28/test_row8_a_progress_edit_insi3/repo'
updated_age = -400, phase = 'parked: waiting on the owner'

    @pytest.mark.parametrize("updated_age, phase", [
        (-200, "resumed: fixing the gate"),  # inside the grace window
        (-400, "handed back"),
        (-400, "handback"),
        (-400, "parked: waiting on the owner"),
        (-400, "stopped"),
    ])
    def test_row8_a_progress_edit_inside_the_grace_or_reading_ended_is_not_activity(repo, updated_age, phase):
        _handed_back(repo, start_age=_LONG_AGO)
        # A future-dated progress comment would read a watched lane stale at once (negative age).
        result = _run(repo, [_progress(9, 101, updated_age=updated_age, created_age=_LONG_AGO, phase=phase)])
>       assert result["event"] == ww.EVENT_TIMER
E       AssertionError: assert 'lane-stale' == 'timer'
E         
E         - timer
E         + lane-stale

/home/user/wt-2323-a/plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py:133: AssertionError
_ test_row8_a_progress_edit_inside_the_grace_or_reading_ended_is_not_activity[-400-stopped] _

repo = '/tmp/claude-0/pytest-of-root/pytest-28/test_row8_a_progress_edit_insi4/repo'
updated_age = -400, phase = 'stopped'

    @pytest.mark.parametrize("updated_age, phase", [
        (-200, "resumed: fixing the gate"),  # inside the grace window
        (-400, "handed back"),
        (-400, "handback"),
        (-400, "parked: waiting on the owner"),
        (-400, "stopped"),
    ])
    def test_row8_a_progress_edit_inside_the_grace_or_reading_ended_is_not_activity(repo, updated_age, phase):
        _handed_back(repo, start_age=_LONG_AGO)
        # A future-dated progress comment would read a watched lane stale at once (negative age).
        result = _run(repo, [_progress(9, 101, updated_age=updated_age, created_age=_LONG_AGO, phase=phase)])
>       assert result["event"] == ww.EVENT_TIMER
E       AssertionError: assert 'lane-stale' == 'timer'
E         
E         - timer
E         + lane-stale

/home/user/wt-2323-a/plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py:133: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py::test_row8_a_progress_edit_inside_the_grace_or_reading_ended_is_not_activity[-200-resumed: fixing the gate]
FAILED plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py::test_row8_a_progress_edit_inside_the_grace_or_reading_ended_is_not_activity[-400-handed back]
FAILED plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py::test_row8_a_progress_edit_inside_the_grace_or_reading_ended_is_not_activity[-400-handback]
FAILED plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py::test_row8_a_progress_edit_inside_the_grace_or_reading_ended_is_not_activity[-400-parked: waiting on the owner]
FAILED plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py::test_row8_a_progress_edit_inside_the_grace_or_reading_ended_is_not_activity[-400-stopped]
5 failed, 1 passed, 16 deselected in 1.59s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `        and ("dormantSince" not in live_lanes[lid] or lid in active_dormant)`; the `git diff HEAD --stat` over both guarded files printed nothing.
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
......                                                                   [100%]
6 passed, 16 deselected in 1.69s
```

## 6. `terminalTs` in `launch_ledger.fold` (`launch_ledger.py:1505`)

- **Axis:** the fold exposes the outcome record's time, which the wave watch takes as the start of a dormant lane's window.
- **Neutralization:** `info["terminalTs"] = rec["ts"]` (line 1506) became `info["terminalTs"] = None`.
- **Raw red** (`-k "row12 or row3_a_builder"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FF                                                                       [100%]
=================================== FAILURES ===================================
__________ test_row3_a_builder_note_after_the_basis_is_a_builder_note __________

repo = '/tmp/claude-0/pytest-of-root/pytest-30/test_row3_a_builder_note_after0/repo'

    def test_row3_a_builder_note_after_the_basis_is_a_builder_note(repo):
        _handed_back(repo, start_age=_LONG_AGO)
        result = _run(repo, [_later(7)])
>       assert result["event"] == ww.EVENT_BUILDER_NOTE
E       AssertionError: assert 'timer' == 'builder-note'
E         
E         - builder-note
E         + timer

/home/user/wt-2323-a/plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py:77: AssertionError
___________ test_row12_fold_exposes_the_outcome_time_as_terminal_ts ____________

repo = '/tmp/claude-0/pytest-of-root/pytest-30/test_row12_fold_exposes_the_ou0/repo'

    def test_row12_fold_exposes_the_outcome_time_as_terminal_ts(repo):
        _cloud_lane(repo, "cloud-a", 101)
        assert _folded(repo)["cloud-a"]["terminalTs"] is None
        _outcome_at(repo, "cloud-a", 77)
        record = [r for r in ll.read(repo, create=False)["records"] if r.get("event") == "outcome"][0]
>       assert _folded(repo)["cloud-a"]["terminalTs"] == record["ts"]
E       assert None == 1793645797.9110892

/home/user/wt-2323-a/plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py:214: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py::test_row3_a_builder_note_after_the_basis_is_a_builder_note
FAILED plugins/superheroes/lib/tests/test_wave_watch_resumed_2323.py::test_row12_fold_exposes_the_outcome_time_as_terminal_ts
2 failed, 20 deselected in 1.01s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `                info["terminalTs"] = rec["ts"]`; the `git diff HEAD --stat` over both guarded files printed nothing.
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..                                                                       [100%]
2 passed, 20 deselected in 0.91s
```
