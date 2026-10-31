# L5 — the open-recorder sees read-and-write handles: bite-proof record

> Note (2026-10-31, #2296): owner-machine paths and the name of a consuming project in this record were replaced with neutral placeholders after capture; nothing else changed.

Implementer-run record (the open-recorder change). Method: one targeted, reversible plant; the detector run alone by its exact node id (red); the inverse edit; the detector again (green).

## R1 — the recorder records read-write opens

- **guarded element and axis:** the open-recorder filter in `plugins/superheroes/lib/tests/test_round_driver_no_records_seed_1721.py` (`_audit`): an open is skipped only when it cannot read (a string mode with no `r` and no `+`, or integer flags whose access mode is `os.O_WRONLY`). Axis: a read-write open (`"r+"`, `"w+"`, `"a+"`, `os.O_RDWR`) of a path is recorded.
- **detector:** `plugins/superheroes/lib/tests/test_session_pickup_and_upgrade_1721.py::test_u4_only_the_saved_state_is_opened_for_reading` (it asserts no certification file of the old session folder is opened for reading, through `_recording`).
- **plant (a targeted, reversible edit):** `plugins/superheroes/lib/round_driver.py:7059`, inside `_upgrade_gate` (the function the detector exercises), after its early `return None`:

```python
    open(os.path.join(session_dir, "certification-receipt.json"), "r+").close()  # PLANT
```

  Under the old filter (`_WRITE_MODE_CHARS = "wax+"`) this `"r+"` open is skipped, so the plant is invisible to the detector; under the new filter it is recorded.

- **red command:** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_session_pickup_and_upgrade_1721.py::test_u4_only_the_saved_state_is_opened_for_reading" -q -p no:cacheprovider -n auto`
- **raw red (rc 1):**

```
bringing up nodes...
bringing up nodes...

F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_u4_only_the_saved_state_is_opened_for_reading ______________
[gw0] darwin -- Python 3.12.13 /path/to/home/.cache/uv/builds-v0/.tmps5iMWW/bin/python

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1080/popen-gw0/test_u4_only_the_saved_state_i0')
capsys = <_pytest.capture.CaptureFixture object at 0x105759850>

    def test_u4_only_the_saved_state_is_opened_for_reading(tmp_path, capsys):
        session_dir = _earlier_version_folder(tmp_path)
        argv = _bootstrap_args(session_dir, str(tmp_path / "guard"), str(tmp_path / "scratch"))
        with _recording() as reads:
            _main(capsys, argv)
            _main(capsys, argv)
        certification = {os.path.realpath(os.path.join(session_dir, name)) for name in _CERT_FILES}
>       assert not (set(reads) & certification)
E       AssertionError: assert not ({'/private/tmp/claude-501/pytest-of-zwrose/pytest-1080/popen-gw0/test_u4_only_the_saved_state_i0/session/certification...private/tmp/claude-501/pytest-of-zwrose/pytest-1080/popen-gw0/test_u4_only_the_saved_state_i0/session/loop-state.json'} & {'/private/tmp/claude-501/pytest-of-zwrose/pytest-1080/popen-gw0/test_u4_only_the_saved_state_i0/session/certification...tmp/claude-501/pytest-of-zwrose/pytest-1080/popen-gw0/test_u4_only_the_saved_state_i0/session/head-content-blobs.json'})
E        +  where {'/private/tmp/claude-501/pytest-of-zwrose/pytest-1080/popen-gw0/test_u4_only_the_saved_state_i0/session/certification...private/tmp/claude-501/pytest-of-zwrose/pytest-1080/popen-gw0/test_u4_only_the_saved_state_i0/session/loop-state.json'} = set(['/private/tmp/claude-501/pytest-of-zwrose/pytest-1080/popen-gw0/test_u4_only_the_saved_state_i0/session/loop-state.js.../claude-501/pytest-of-zwrose/pytest-1080/popen-gw0/test_u4_only_the_saved_state_i0/session/certification-receipt.json'])

/path/to/home/.superheroes-worktrees/superheroes/issue-1723-l5-order-c/plugins/superheroes/lib/tests/test_session_pickup_and_upgrade_1721.py:319: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_session_pickup_and_upgrade_1721.py::test_u4_only_the_saved_state_is_opened_for_reading
1 failed in 8.25s
```

- **restore (the inverse edit):** the single `# PLANT` line was removed. The lines around the plant site, quoted back after the restore (`sed -n 7055,7060p plugins/superheroes/lib/round_driver.py`):

```
    before any commit recovery, journal row, session id, order, record or fold, and writes only the
    once-only marker."""
    if not _earlier_generation_unfinished(session_dir):
        return None
    already_restarted, written = _write_upgrade_marker(session_dir, cmd)
    refusal = {"ok": False, "reason": SESSION_FROM_EARLIER_VERSION,
```

  `grep -c PLANT plugins/superheroes/lib/round_driver.py` → `0`.
- **green command:** the same command line as the red.
- **raw green (rc 0):**

```
bringing up nodes...
bringing up nodes...

.                                                                        [100%]
1 passed in 9.71s
```
- **verdict:** RED->GREEN
