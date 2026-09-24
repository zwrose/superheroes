# WO-L3AB-C (#1273) bite-proof — `_load_native_result_json` admission chokepoint

**Provenance:** cursor / composer-2.5 (implementer).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-C1 | `_load_native_result_json` completion window | completion stamp must bind before admit | `test_review_admission_no_completion_stamp_forfeits[argv]` |
| BP-C2 | `_load_native_result_json` payload digest binding | rewritten payload must not admit against old stamp | `test_admission_payload_rewrite_forfeits_mismatch` |
| BP-C3 | `_load_native_result_json` timedOut deadline guard | timed-out load without deadline fields forfeits | `test_timed_out_write_without_recorded_deadline_forfeits[absent]` |
| BP-C4 | admission-path census | closure must detect getmtime in admission functions | `test_admission_path_does_not_read_filesystem_timestamps` |
| BP-C5 | census vacuity guard | renamed entry point must fail closure, not silently shrink census | `test_admission_path_closure_covers_entry_points` |

---

## BP-C1 — completion window inside `_load_native_result_json`

- **axis:** completion stamp must bind before the loader returns the object

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_load_native_result_json`):
```python
        verdict, detail = engine_result_channel.completion_window(ended, digest)
        # if verdict == "forfeit":
        #     return None, detail
        return obj, None  # bite-proof BP-C1 neutralization
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest 'plugins/superheroes/lib/tests/test_engine_dispatch.py::test_review_admission_no_completion_stamp_forfeits[argv]' -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_review_admission_no_completion_stamp_forfeits[argv] ___________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-3364/test_review_admission_no_compl0')
delivery = 'argv'
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x10b1ebd30>

    @pytest.mark.parametrize("delivery", _REVIEW_ADMISSION_DELIVERIES)
    def test_review_admission_no_completion_stamp_forfeits(tmp_path, delivery, monkeypatch):
        envelope = _review_payload_envelope()
        ended = {"exit": 0, "timedOut": False, "refusal": None}
        if delivery == "argv":
            run_dir, state = _review_admission_codex_argv(tmp_path, ended, envelope)
        elif delivery == "prompt":
            run_dir, state = _review_admission_cursor_prompt(tmp_path, ended, envelope)
        elif delivery == "stdout":
            run_dir, state = _review_admission_claude_stdout(tmp_path, monkeypatch, ended, envelope)
        else:
            run_dir, state = _review_admission_claude_transcript(tmp_path, monkeypatch, ended, envelope)
        grade = ED._grade_review_attempt(run_dir, state, 1)
>       assert grade.get("forfeit") is True
E       AssertionError: assert None is True
E        +  where None = <built-in method get of dict object at 0x10b0e5400>('forfeit')
E        +    where <built-in method get of dict object at 0x10b0e5400> = {'engagement': {'read': 'engaged', 'source': 'none', 'stdoutBytes': 0, 'telemetry': 'none', ...}, 'findings': [{'body'...stigatedRejected': ['missing'], 'investigatedRejectedRecords': [{'path': 'path/to/file.py', 'reason': 'missing'}], ...}.get

plugins/superheroes/lib/tests/test_engine_dispatch.py:16565: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_review_admission_no_completion_stamp_forfeits[argv]
1 failed in 0.99s
```

**restore** (`plugins/superheroes/lib/engine_dispatch.py`, `_load_native_result_json`):
```python
        verdict, detail = engine_result_channel.completion_window(ended, digest)
        if verdict == "forfeit":
            return None, detail
        return obj, None
```

**restore receipt:** inverse edit applied; production branch restored.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.90s
```

---

## BP-C2 — payload-digest binding

- **axis:** admitted bytes digest must match the recorded completion digest

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_load_native_result_json`):
```python
        recorded_digest = ended.get(engine_result_channel.FIELD_RESULT_COMPLETE_SHA256)
        verdict, detail = engine_result_channel.completion_window(ended, recorded_digest)  # bite-proof BP-C2 neutralization
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_admission_payload_rewrite_forfeits_mismatch -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_admission_payload_rewrite_forfeits_mismatch _______________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-3366/test_admission_payload_rewrite0')

    def test_admission_payload_rewrite_forfeits_mismatch(tmp_path):
        first = _write_payload_obj()
        second = json.loads(_native_write_result_json(report="rewritten after stamp"))
        ended = _ended_with_completion_stamp(
            first, complete_at=5.0, deadline_mono=10.0,
            exit=1, timedOut=True, timeoutAt=1000.0,
        )
        run_dir, state = _write_admission_codex_argv(tmp_path, ended, second)
        grade = ED._grade_write_attempt(run_dir, state, 1)
>       assert grade.get("forfeit") is True
E       AssertionError: assert None is True
E        +  where None = <built-in method get of dict object at 0x1043c9e40>('forfeit')
E        +    where <built-in method get of dict object at 0x1043c9e40> = {'admittedAfterTimeout': True, 'evidence': {'testFailed': False, 'testPassed': True}, 'ok': True, 'report': 'rewritten after stamp', ...}.get

plugins/superheroes/lib/tests/test_engine_dispatch.py:16578: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_admission_payload_rewrite_forfeits_mismatch
1 failed in 1.04s
```

**restore** (`plugins/superheroes/lib/engine_dispatch.py`, `_load_native_result_json`):
```python
        verdict, detail = engine_result_channel.completion_window(ended, digest)
```

**restore receipt:** inverse edit applied; production branch restored.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.86s
```

---

## BP-C3 — timedOut-without-deadlineMono guard

- **axis:** timed-out admission must refuse when deadline mono/epoch are unusable

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_load_native_result_json`):
```python
        if False and ended.get("timedOut"):  # bite-proof BP-C3 neutralization
            deadline_mono = ended.get(engine_result_channel.FIELD_DEADLINE_MONO)
            deadline_epoch = ended.get(engine_result_channel.FIELD_DEADLINE_EPOCH)
            if (
                isinstance(deadline_mono, bool)
                or not isinstance(deadline_mono, (int, float))
                or not isinstance(deadline_epoch, str)
                or not deadline_epoch
            ):
                return None, "timeout-deadline-unrecorded"
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest 'plugins/superheroes/lib/tests/test_engine_dispatch.py::test_timed_out_write_without_recorded_deadline_forfeits[absent]' -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_timed_out_write_without_recorded_deadline_forfeits[absent] ________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-3368/test_timed_out_write_without_r0')
deadline_overrides = {}
request = <FixtureRequest for <Function test_timed_out_write_without_recorded_deadline_forfeits[absent]>>

    @pytest.mark.parametrize(
        "deadline_overrides",
        [
            pytest.param({}, id="absent"),
            pytest.param({ERC.FIELD_DEADLINE_MONO: None}, id="none-deadline-mono"),
            pytest.param({ERC.FIELD_DEADLINE_MONO: "not-a-number"}, id="non-numeric-deadline-mono"),
            pytest.param(
                {ERC.FIELD_DEADLINE_MONO: 10.0, ERC.FIELD_DEADLINE_EPOCH: ""},
                id="empty-deadline-epoch",
            ),
        ],
    )
    def test_timed_out_write_without_recorded_deadline_forfeits(
        tmp_path, deadline_overrides, request,
    ):
        native_write = _native_write_result_json()
        payload = json.loads(native_write)
        ended_overrides = {
            "timedOut": True,
            "timeoutAt": 1000.0,
            "exit": 1,
            "at": time.time(),
            "capSeconds": 1,
        }
        ended_overrides.update(deadline_overrides)
        run_dir = str(tmp_path / request.node.callspec.id)
        run_dir, state, _ended = _codex_native_write_grade_state(
            tmp_path, run_dir, ended_overrides=ended_overrides, payload=payload,
        )
        result_path = ED._native_result_path(run_dir, 1)
        with open(result_path, "w", encoding="utf-8") as fh:
            fh.write(native_write + "\n")
        grade = ED._grade_write_attempt(run_dir, state, 1)
        assert grade.get("forfeit") is True
        assert grade.get("detail") == "timeout-native-result-unadmitted"
>       assert grade.get("admissionDetail") == "timeout-deadline-unrecorded"
E       AssertionError: assert 'result-completion-unrecorded' == 'timeout-deadline-unrecorded'
E         
E         - timeout-deadline-unrecorded
E         + result-completion-unrecorded

plugins/superheroes/lib/tests/test_engine_dispatch.py:3784: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_timed_out_write_without_recorded_deadline_forfeits[absent]
1 failed in 1.02s
```

**restore** (`plugins/superheroes/lib/engine_dispatch.py`, `_load_native_result_json`):
```python
        if ended.get("timedOut"):
            deadline_mono = ended.get(engine_result_channel.FIELD_DEADLINE_MONO)
            deadline_epoch = ended.get(engine_result_channel.FIELD_DEADLINE_EPOCH)
            if (
                isinstance(deadline_mono, bool)
                or not isinstance(deadline_mono, (int, float))
                or not isinstance(deadline_epoch, str)
                or not deadline_epoch
            ):
                return None, "timeout-deadline-unrecorded"
```

**restore receipt:** inverse edit applied; production branch restored.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.85s
```

---

## BP-C4 — census detects getmtime in admission closure

- **axis:** admission-path census must fail when a closure function reads filesystem timestamps

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_load_native_result_json`):
```python
    os.path.getmtime(run_dir_real)  # bite-proof BP-C4 neutralization
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_admission_clock_census.py::test_admission_path_does_not_read_filesystem_timestamps -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_admission_path_does_not_read_filesystem_timestamps ____________

    def test_admission_path_does_not_read_filesystem_timestamps():
        funcs, closure = _admission_closure()
        offenses = []
        for name in sorted(closure):
            for spelling in _forbidden_spellings(funcs[name]):
                offenses.append((name, spelling))
>       assert not offenses, offenses
E       AssertionError: [('_load_native_result_json', 'getmtime')]
E       assert not [('_load_native_result_json', 'getmtime')]

plugins/superheroes/lib/tests/test_admission_clock_census.py:97: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_admission_clock_census.py::test_admission_path_does_not_read_filesystem_timestamps
1 failed in 0.11s
```

**restore:** removed the `os.path.getmtime(run_dir_real)` line from `_load_native_result_json`.

**restore receipt:** inverse edit applied; production branch restored.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.09s
```

---

## BP-C5 — census vacuity guard on renamed entry point

- **axis:** a bogus entry point name must fail the closure census, not silently shrink coverage

**neutralization** (`plugins/superheroes/lib/tests/test_admission_clock_census.py`, `ENTRY_POINTS`):
```python
    "_load_native_result_json_typo",  # bite-proof BP-C5 neutralization
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_admission_clock_census.py::test_admission_path_closure_covers_entry_points -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_admission_path_closure_covers_entry_points ________________

    def test_admission_path_closure_covers_entry_points():
        funcs, closure = _admission_closure()
        assert closure, "admission-path closure is empty"
        for name in ENTRY_POINTS:
>           assert name in closure, "entry point %s missing from closure" % name
E           AssertionError: entry point _load_native_result_json_typo missing from closure
E           assert '_load_native_result_json_typo' in {'_admit_native_review_result', '_admit_native_write_result', '_attach_review_rejection_fields', '_engagement_telemetry', '_engagement_with_read', '_finish_review_grade_from_parse', ...}

plugins/superheroes/lib/tests/test_admission_clock_census.py:88: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_admission_clock_census.py::test_admission_path_closure_covers_entry_points
1 failed in 0.10s
```

**restore** (`plugins/superheroes/lib/tests/test_admission_clock_census.py`, `ENTRY_POINTS`):
```python
    "_load_native_result_json",
```

**restore receipt:** inverse edit applied; test file restored.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.09s
```
