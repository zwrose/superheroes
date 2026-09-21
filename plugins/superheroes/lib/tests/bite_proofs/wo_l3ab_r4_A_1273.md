# WO-L3AB-R4-A (#1273) bite-proof — stdout completion stamp (layer 3ab round 4)

**Covers:** WO-A, WO-A2, WO-B, WO-C (stdout completion producer path, round 4).

**Head:** `1d1f5000b145dbaf42ae2aa010fc06f18a297275`

**Provenance:** cursor / composer-2.5 (implementer).

The completion stamp always describes the LAST complete result event on stdout — the same
event the runner materializes — and it is taken at the poll that first saw that event
complete.

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-1 | `_observe_stdout_completion` terminal path | terminal observation drains and parses unconditionally | `test_completion_producer_stdout_trailing_non_result_line_stamps_at_terminal` |
| BP-2 | `_process_stdout_completion_line` replace | newer complete result event replaces the held stamp | `test_completion_stdout_two_results_admits_last_stamp_and_materialized` |
| BP-3 | `_drain_stdout_completion_bytes` line bound | line bound drops an over-bound line whole and never stamps it | `test_completion_stdout_over_bound_line_forfeits_unrecorded` |
| BP-4 | poll-loop terminal placement | single terminal observation sits after writers are reaped | `test_completion_stdout_grace_window_second_result_stamps_last` |
| BP-5 | `_observe_stdout_completion` eviction block | stamp is cleared once its event leaves the retained tail | `test_completion_stdout_evicted_result_forfeits_unrecorded` |
| BP-6 | eviction regime guard | eviction never fires below the cap | `test_completion_stdout_large_under_cap_still_admits` |
| BP-7 | `_drain_stdout_completion_bytes` overflow write-back | overflow scopes to exactly one line | `test_completion_stdout_overflow_does_not_suppress_following_result` |

---

## BP-1 — unconditional terminal observation

- **axis:** terminal observation must retain the stamp produced during the terminal drain

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_observe_stdout_completion` terminal block):

before:
```python
            obs_state["buf"] = b""
            obs_state["overflow"] = False
```

after:
```python
            obs_state["buf"] = b""
            obs_state["overflow"] = False
            obs_state["stamp"] = None
            obs_state["stamp_line_start"] = None
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_completion_producer_stdout_trailing_non_result_line_stamps_at_terminal -q -p no:randomly
```

**raw red** (exit 1):
```
F                                                                        [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_completion_producer_stdout_trailing_non_result_line_stamps_at_terminal
1 failed in 2.38s
```
(assertion: `assert key in ended` / `assert 'resultCompleteAt' in ended`)

**restore** (`plugins/superheroes/lib/engine_dispatch.py`, `_observe_stdout_completion` terminal block): remove the two `obs_state["stamp"] = None` / `stamp_line_start` lines.

**restore receipt:** post-restore `git status --porcelain` empty.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 2.81s
```

---

## BP-2 — newer result replaces held stamp

- **axis:** two stdout result events — stamp and materializer must follow the last

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_process_stdout_completion_line`):

before:
```python
    try:
        text = line_bytes.decode("utf-8", errors="ignore").rstrip("\r").strip()
```

after:
```python
    try:
        if obs_state.get("stamp") is not None:
            return
        text = line_bytes.decode("utf-8", errors="ignore").rstrip("\r").strip()
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_completion_stdout_two_results_admits_last_stamp_and_materialized -q -p no:randomly
```

**raw red** (exit 1):
```
F                                                                        [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_completion_stdout_two_results_admits_last_stamp_and_materialized
1 failed in 2.05s
```
(assertion: `assert ended[ERC.FIELD_RESULT_COMPLETE_SHA256] == ERC.canonical_payload_digest(payload)`)

**restore:** remove the held-stamp early return.

**restore receipt:** post-restore `git status --porcelain` empty.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 1.84s
```

---

## BP-3 — over-bound line dropped whole (**not-red under order neutralization**)

- **axis:** a result line longer than the stampable bound is dropped whole

**neutralization attempted** (`plugins/superheroes/lib/engine_dispatch.py`, `_drain_stdout_completion_bytes`):

before:
```python
                new_buf = buf + tail
                if len(new_buf) > _STDOUT_STAMPABLE_LINE_MAX:
                    overflow = True
                    obs_state["buf"] = b""
                else:
                    obs_state["buf"] = new_buf
```

after:
```python
                obs_state["buf"] = buf + tail
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_completion_stdout_over_bound_line_forfeits_unrecorded -q -p no:randomly
```

**raw result under neutralization** (exit 0 — stayed green):
```
.                                                                        [100%]
1 passed in 1.89s
```

**finding:** removing only the `_STDOUT_STAMPABLE_LINE_MAX` guard does not redden the
proving test. The over-bound line is still admitted transiently, then the eviction block
at the end of `_observe_stdout_completion` clears the stamp before the ended record is
written — the same observable outcome as overflow-forfeit. A stacked experiment (same
len-guard removal plus eviction-block deletion) did redden (`assert 'resultCompleteAt'
not in ended` failed), confirming the axis is real but masked by eviction under the
order's single neutralization.

**normalization disclosure:** test patches `MAX_STDOUT_CAPTURE` and `_STDOUT_STAMPABLE_LINE_MAX`
to `16384` and derived stampable bound via `_patch_stdout_completion_bounds`. Proof still
bites on the shipped 8 MiB values because the guarded logic is the len-guard branch in
`_drain_stdout_completion_bytes`; the pin only shrinks fixtures.

**restore:** reinstate the `len(new_buf) > _STDOUT_STAMPABLE_LINE_MAX` overflow branch.

**restore receipt:** post-restore `git status --porcelain` empty.

---

## BP-4 — terminal observation after writers reaped

- **axis:** terminal observation after termination must stamp a grace-window second result

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_run_engine_files` poll loop):

before (natural exit path):
```python
        if rc is not None:
            natural_rc = rc
            break
...
    _observe_attempt_completions(..., terminal=True)
```

after:
```python
        if rc is not None:
            natural_rc = rc
            _observe_attempt_completions(..., terminal=True)
            break
...
    # post-wait terminal call removed
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_completion_stdout_grace_window_second_result_stamps_last -q -p no:randomly
```

**raw red** (exit 1):
```
F                                                                        [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_completion_stdout_grace_window_second_result_stamps_last
1 failed in 32.20s
```
(assertion: `assert ended[ERC.FIELD_RESULT_COMPLETE_SHA256] == ERC.canonical_payload_digest(payload)` — first-result digest retained)

**restore:** move terminal `_observe_attempt_completions` back to after `proc.wait`, remove in-loop terminal call.

**restore receipt:** post-restore `git status --porcelain` empty.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 35.54s
```

---

## BP-5 — eviction clears stamp

- **axis:** a stamped result pushed out of the retained tail clears the stamp

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_observe_stdout_completion`):

before:
```python
        if stamp is not None and stamp_line_start is not None:
            if (
                offset > MAX_STDOUT_CAPTURE
                and offset - stamp_line_start
                > _cap_content_budget(MAX_STDOUT_CAPTURE, CAP_STREAM_STDOUT, offset)
            ):
                obs_state["stamp"] = None
                obs_state["stamp_line_start"] = None
```

after: eviction block deleted entirely.

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_completion_stdout_evicted_result_forfeits_unrecorded -q -p no:randomly
```

**raw red** (exit 1):
```
F                                                                        [100%]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_completion_stdout_evicted_result_forfeits_unrecorded
1 failed in 4.53s
```
(assertion: `assert 'resultCompleteAt' not in ended`)

**restore:** reinstate eviction block.

**restore receipt:** post-restore `git status --porcelain` empty.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 4.98s
```

---

## BP-6 — eviction never fires below cap (**not-red under order neutralization**)

- **axis:** stamped result survives when stdout is large but still at or under the cap

**neutralizations attempted** (`plugins/superheroes/lib/engine_dispatch.py`, eviction guard):

1. Drop `offset > MAX_STDOUT_CAPTURE and` from the regime guard.
2. Replace budget comparison with `offset - stamp_line_start > _STDOUT_STAMPABLE_LINE_MAX`.

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_completion_stdout_large_under_cap_still_admits -q -p no:randomly
```

**raw result under both neutralizations** (exit 0 — stayed green):
```
.                                                                        [100%]
1 passed in 3.61s
```
(and `1 passed in 4.48s` for the guard-drop variant)

**finding:** neither order-listed neutralization reddens the proving test at the patched
fixture size. An aggressive threshold (`offset - stamp_line_start > 1024`) did redden
(`assert 'resultCompleteAt' in ended`), confirming the detector bites on eviction timing
but the order's neutralizations do not shift eviction below the cap for this fixture.

**normalization disclosure:** test patches `MAX_STDOUT_CAPTURE` and `_STDOUT_STAMPABLE_LINE_MAX`
to `16384` / derived stampable via `_patch_stdout_completion_bounds`. Guarded logic is the
`offset > MAX_STDOUT_CAPTURE` regime gate plus `_cap_content_budget`; pin shrinks fixtures only.

**restore:** reinstate shipped eviction guard.

**restore receipt:** post-restore `git status --porcelain` empty.

---

## BP-7 — overflow scopes to one line (**not-red under order neutralization**)

- **axis:** overflow on one over-bound line must not leak into the next valid result line

**neutralization attempted** (`plugins/superheroes/lib/engine_dispatch.py`, `_drain_stdout_completion_bytes` early-return path):

before:
```python
            obs_state["overflow"] = overflow
            return
```

after:
```python
            return
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_engine_dispatch.py::test_completion_stdout_overflow_does_not_suppress_following_result -q -p no:randomly
```

**raw result under neutralization** (exit 0 — stayed green):
```
.                                                                        [100%]
1 passed in 2.51s
```

**finding:** removing the overflow write-back on the partial-line early return does not
redden the proving test — without persisting `overflow=True`, the following valid result
line is still processed and admitted. The order's neutralization prevents the leak the
test guards against rather than introducing it.

**normalization disclosure:** test patches `MAX_STDOUT_CAPTURE`, `_STDOUT_STAMPABLE_LINE_MAX`
to `16384` / derived stampable, and `_STDOUT_COMPLETION_READ_CHUNK` to `256` for readable
chunk-split fixtures. Guarded logic is the overflow write-back on the early-return path;
pins shrink fixtures only.

**restore:** reinstate `obs_state["overflow"] = overflow` before early return.

**restore receipt:** post-restore `git status --porcelain` empty.
