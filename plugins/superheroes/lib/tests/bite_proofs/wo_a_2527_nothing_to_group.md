# WO-A (#2527) bite-proof — an empty synthesis grouping is a valid answer when there was nothing to group

**Provenance:** claude / sonnet-5.5 (implementer, WO-A), `plugins/superheroes/lib/engine_dispatch.py` (`_finish_review_grade_from_parse`), `plugins/superheroes/lib/round_driver.py` (`_assemble_dispatch_evidence`), `plugins/superheroes/lib/round_adapters.py` (`_authenticate_finder`); tests in `plugins/superheroes/lib/tests/test_synthesis_nothing_to_group_2527.py`.

Declared guarded-element set (from the order): **G-I1**, **G-I1b**, **G-I4**, **G-I5**. Each was neutralized by one targeted edit (the Edit tool, exact-text match, the target unique in its file), the one detector selected by its exact test node id (so every parametrized case of it ran), the inverse edit applied, and the same selection run again. No `git checkout`, `git restore`, `git reset` or `git stash` was used. The sha256 of each of the three neutralized files was taken before the first neutralization and after the last restore.

## Guarded elements

| ID | Guarded element | Axis | Proving node |
|---|---|---|---|
| G-I1 | the flag's ok branch (`engine_dispatch.py` `_finish_review_grade_from_parse`, `if (opened.get("nothingToGroup") is True and kind == "grouping" and has_payload`) | a run opened with `--nothing-to-group` grades an empty grouping (`[]` or `null`) from an engaged seat ok, value kept as parsed, instead of vacuous | `test_synthesis_nothing_to_group_2527.py::test_t1_flagged_empty_grouping_from_an_engaged_seat_is_ok_and_keeps_its_value` |
| G-I1b | the engagement floor inside that branch (`engine_dispatch.py`, `if stamped is not None and stamped.get("read") == "engaged":`) | an empty grouping with no observed tool call (`toolCalls` None or 0) stays the vacuous forfeit even in a flagged run | `test_synthesis_nothing_to_group_2527.py::test_t2_flagged_empty_grouping_without_observed_tool_calls_is_vacuous` |
| G-I4 | the record-time binding (`round_driver.py` `_assemble_dispatch_evidence`, `if (phase == P_SYNTHESIS and record.get("nothingToGroup") is True`) | a run opened with `--nothing-to-group` landing on a round with survivors refuses `evidence-nothing-to-group-mismatch` and stores nothing | `test_synthesis_nothing_to_group_2527.py::test_t7_a_flagged_run_cannot_answer_a_round_that_has_survivors` |
| G-I5 | the `no-runner-evidence` branch (`round_adapters.py` `_authenticate_finder`, `if executed is None:`) | a finder landing with no runner execution evidence and an eligible recorded vendor is named `no-runner-evidence`, not `unauthenticated-vendor` | `test_synthesis_nothing_to_group_2527.py::test_t9_a_landing_with_no_runner_evidence_is_named_for_what_is_missing` |

## Disclosures

- All four elements went red under their neutralization (pytest exit 1) and green after the restore (exit 0), on the axis each claims (the red tokens below name it).
- Each detector was selected by exact node id (`bite-proof.md` § Running a proof), not by `-k`; every command carried `--tb=short` so the captures stay short, and the same flags ran for red and green.
- The `UV_NATIVE_TLS` deprecation warning line that `scripts/pinned-python` prints before each pytest capture is omitted below; everything else is verbatim, nothing filtered or trimmed. pytest's own `...` inside a dict repr is pytest's truncation, kept as printed.
- Redaction: none needed; the captures hold no secrets, tokens, private URLs or PII. Temp paths are the pytest temp base.
- Every capture is well under 32 KiB, so none is written off-repo.
- Other tests in the file (T3 unflagged stays vacuous, T4 the flag is grouping-only, T5 journal and continuation, T6 payload key, T8 end to end, the other two T9 cases) are green in the whole-file run and were not separately neutralized; they carry no bite-proof of their own here.
- The file-level sha256 values before the first neutralization and after the last restore are identical for all three files:
  - `plugins/superheroes/lib/engine_dispatch.py` `e09cea89fa860216aba69497498faed86ccbbc7f3a30463c5769347a1fcb0fed`
  - `plugins/superheroes/lib/round_driver.py` `be19a9cfcc1d51904a0a410499a6014316338ca6b125671853f5bbcc39eda140`
  - `plugins/superheroes/lib/round_adapters.py` `9ca77ce3814566356d58f2fe10cfb73e110ad8561d0e1b9b3ffc4f9b954a259a`

---

## G-I1 — the flag's ok branch (`engine_dispatch.py` `_finish_review_grade_from_parse`)

- **axis:** an engaged seat's empty grouping, in a run opened with the flag, is graded ok with its value kept, not vacuous

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`):
```diff
-    if (opened.get("nothingToGroup") is True and kind == "grouping" and has_payload
+    if (False and opened.get("nothingToGroup") is True and kind == "grouping" and has_payload
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/wo-a-2527-pyc -m pytest -q -p no:cacheprovider --tb=short "plugins/superheroes/lib/tests/test_synthesis_nothing_to_group_2527.py::test_t1_flagged_empty_grouping_from_an_engaged_seat_is_ok_and_keeps_its_value"
```

**decisive assertion lines (red tokens):** `test_synthesis_nothing_to_group_2527.py:141`: `assert grade.get("ok") is True, grade` → the grade is `{'forfeit': True, 'reason': 'vacuous', ...}` for all three cases, the vacuous forfeit this work order removes for a flagged, engaged run.

**raw red** (exit 1):
```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_t1_flagged_empty_grouping_from_an_engaged_seat_is_ok_and_keeps_its_value[empty-list-one-call] _
/home/user/wt-2527/plugins/superheroes/lib/tests/test_synthesis_nothing_to_group_2527.py:141: in test_t1_flagged_empty_grouping_from_an_engaged_seat_is_ok_and_keeps_its_value
    assert grade.get("ok") is True, grade
E   AssertionError: {'forfeit': True, 'reason': 'vacuous', 'engagement': {'tokens': 110, 'toolCalls': 1, 'stdoutBytes': 330, 'wallSeconds': 1.0, ...}, 'investigatedRejected': ['not-a-list'], ...}
E   assert None is True
E    +  where None = <built-in method get of dict object at 0x7f47f69838c0>('ok')
E    +    where <built-in method get of dict object at 0x7f47f69838c0> = {'forfeit': True, 'reason': 'vacuous', 'engagement': {'tokens': 110, 'toolCalls': 1, 'stdoutBytes': 330, 'wallSeconds': 1.0, ...}, 'investigatedRejected': ['not-a-list'], ...}.get
_ test_t1_flagged_empty_grouping_from_an_engaged_seat_is_ok_and_keeps_its_value[null-one-call] _
/home/user/wt-2527/plugins/superheroes/lib/tests/test_synthesis_nothing_to_group_2527.py:141: in test_t1_flagged_empty_grouping_from_an_engaged_seat_is_ok_and_keeps_its_value
    assert grade.get("ok") is True, grade
E   AssertionError: {'forfeit': True, 'reason': 'vacuous', 'engagement': {'tokens': 110, 'toolCalls': 1, 'stdoutBytes': 332, 'wallSeconds': 1.0, ...}, 'investigatedRejected': ['not-a-list'], ...}
E   assert None is True
E    +  where None = <built-in method get of dict object at 0x7f47f66a9480>('ok')
E    +    where <built-in method get of dict object at 0x7f47f66a9480> = {'forfeit': True, 'reason': 'vacuous', 'engagement': {'tokens': 110, 'toolCalls': 1, 'stdoutBytes': 332, 'wallSeconds': 1.0, ...}, 'investigatedRejected': ['not-a-list'], ...}.get
_ test_t1_flagged_empty_grouping_from_an_engaged_seat_is_ok_and_keeps_its_value[empty-list-five-calls] _
/home/user/wt-2527/plugins/superheroes/lib/tests/test_synthesis_nothing_to_group_2527.py:141: in test_t1_flagged_empty_grouping_from_an_engaged_seat_is_ok_and_keeps_its_value
    assert grade.get("ok") is True, grade
E   AssertionError: {'forfeit': True, 'reason': 'vacuous', 'engagement': {'tokens': 110, 'toolCalls': 5, 'stdoutBytes': 666, 'wallSeconds': 1.0, ...}, 'investigatedRejected': ['not-a-list'], ...}
E   assert None is True
E    +  where None = <built-in method get of dict object at 0x7f47fb666080>('ok')
E    +    where <built-in method get of dict object at 0x7f47fb666080> = {'forfeit': True, 'reason': 'vacuous', 'engagement': {'tokens': 110, 'toolCalls': 5, 'stdoutBytes': 666, 'wallSeconds': 1.0, ...}, 'investigatedRejected': ['not-a-list'], ...}.get
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_synthesis_nothing_to_group_2527.py::test_t1_flagged_empty_grouping_from_an_engaged_seat_is_ok_and_keeps_its_value[empty-list-one-call]
FAILED plugins/superheroes/lib/tests/test_synthesis_nothing_to_group_2527.py::test_t1_flagged_empty_grouping_from_an_engaged_seat_is_ok_and_keeps_its_value[null-one-call]
FAILED plugins/superheroes/lib/tests/test_synthesis_nothing_to_group_2527.py::test_t1_flagged_empty_grouping_from_an_engaged_seat_is_ok_and_keeps_its_value[empty-list-five-calls]
3 failed in 3.67s
```

**restore:** the inverse edit on `plugins/superheroes/lib/engine_dispatch.py` (`if (False and opened.get(` back to `if (opened.get(`).

**restored lines** (as they stand, `grep -n`):
```
5292:    if (opened.get("nothingToGroup") is True and kind == "grouping" and has_payload
```
sha256 of `engine_dispatch.py` after all restores equals the value before the first neutralization (see Disclosures).

**raw green** (exit 0), same command:
```
...                                                                      [100%]
3 passed in 3.71s
```

---

## G-I1b — the engagement floor inside the ok branch (`engine_dispatch.py`)

- **axis:** an empty grouping with no runner-observed tool call (`toolCalls` None or 0) stays the vacuous forfeit even in a flagged run

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`):
```diff
-        if stamped is not None and stamped.get("read") == "engaged":
+        if stamped is not None:
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/wo-a-2527-pyc -m pytest -q -p no:cacheprovider --tb=short "plugins/superheroes/lib/tests/test_synthesis_nothing_to_group_2527.py::test_t2_flagged_empty_grouping_without_observed_tool_calls_is_vacuous"
```

**decisive assertion lines (red tokens):** `test_synthesis_nothing_to_group_2527.py:156`: `assert grade.get("forfeit") is True, grade` → the grade is `{'ok': True, 'resultKind': 'grouping', ...}` with `'toolCalls': None` (two cases) and `'toolCalls': 0` (two cases): an unengaged seat's empty grouping graded ok.

**raw red** (exit 1):
```
FFFF                                                                     [100%]
=================================== FAILURES ===================================
_ test_t2_flagged_empty_grouping_without_observed_tool_calls_is_vacuous[no-telemetry-empty-list] _
/home/user/wt-2527/plugins/superheroes/lib/tests/test_synthesis_nothing_to_group_2527.py:156: in test_t2_flagged_empty_grouping_without_observed_tool_calls_is_vacuous
    assert grade.get("forfeit") is True, grade
E   AssertionError: {'ok': True, 'resultKind': 'grouping', 'grouping': [], 'engagement': {'tokens': None, 'toolCalls': None, 'stdoutBytes': 16, 'wallSeconds': 1.0, ...}, ...}
E   assert None is True
E    +  where None = <built-in method get of dict object at 0x7ff6ebf4d280>('forfeit')
E    +    where <built-in method get of dict object at 0x7ff6ebf4d280> = {'ok': True, 'resultKind': 'grouping', 'grouping': [], 'engagement': {'tokens': None, 'toolCalls': None, 'stdoutBytes': 16, 'wallSeconds': 1.0, ...}, ...}.get
_ test_t2_flagged_empty_grouping_without_observed_tool_calls_is_vacuous[no-telemetry-null] _
/home/user/wt-2527/plugins/superheroes/lib/tests/test_synthesis_nothing_to_group_2527.py:156: in test_t2_flagged_empty_grouping_without_observed_tool_calls_is_vacuous
    assert grade.get("forfeit") is True, grade
E   AssertionError: {'ok': True, 'resultKind': 'grouping', 'grouping': None, 'engagement': {'tokens': None, 'toolCalls': None, 'stdoutBytes': 18, 'wallSeconds': 1.0, ...}, ...}
E   assert None is True
E    +  where None = <built-in method get of dict object at 0x7ff6edf166c0>('forfeit')
E    +    where <built-in method get of dict object at 0x7ff6edf166c0> = {'ok': True, 'resultKind': 'grouping', 'grouping': None, 'engagement': {'tokens': None, 'toolCalls': None, 'stdoutBytes': 18, 'wallSeconds': 1.0, ...}, ...}.get
_ test_t2_flagged_empty_grouping_without_observed_tool_calls_is_vacuous[zero-tool-calls-empty-list] _
/home/user/wt-2527/plugins/superheroes/lib/tests/test_synthesis_nothing_to_group_2527.py:156: in test_t2_flagged_empty_grouping_without_observed_tool_calls_is_vacuous
    assert grade.get("forfeit") is True, grade
E   AssertionError: {'ok': True, 'resultKind': 'grouping', 'grouping': [], 'engagement': {'tokens': 110, 'toolCalls': 0, 'stdoutBytes': 246, 'wallSeconds': 1.0, ...}, ...}
E   assert None is True
E    +  where None = <built-in method get of dict object at 0x7ff6ee0ad240>('forfeit')
E    +    where <built-in method get of dict object at 0x7ff6ee0ad240> = {'ok': True, 'resultKind': 'grouping', 'grouping': [], 'engagement': {'tokens': 110, 'toolCalls': 0, 'stdoutBytes': 246, 'wallSeconds': 1.0, ...}, ...}.get
_ test_t2_flagged_empty_grouping_without_observed_tool_calls_is_vacuous[zero-tool-calls-null] _
/home/user/wt-2527/plugins/superheroes/lib/tests/test_synthesis_nothing_to_group_2527.py:156: in test_t2_flagged_empty_grouping_without_observed_tool_calls_is_vacuous
    assert grade.get("forfeit") is True, grade
E   AssertionError: {'ok': True, 'resultKind': 'grouping', 'grouping': None, 'engagement': {'tokens': 110, 'toolCalls': 0, 'stdoutBytes': 248, 'wallSeconds': 1.0, ...}, ...}
E   assert None is True
E    +  where None = <built-in method get of dict object at 0x7ff6e8f45380>('forfeit')
E    +    where <built-in method get of dict object at 0x7ff6e8f45380> = {'ok': True, 'resultKind': 'grouping', 'grouping': None, 'engagement': {'tokens': 110, 'toolCalls': 0, 'stdoutBytes': 248, 'wallSeconds': 1.0, ...}, ...}.get
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_synthesis_nothing_to_group_2527.py::test_t2_flagged_empty_grouping_without_observed_tool_calls_is_vacuous[no-telemetry-empty-list]
FAILED plugins/superheroes/lib/tests/test_synthesis_nothing_to_group_2527.py::test_t2_flagged_empty_grouping_without_observed_tool_calls_is_vacuous[no-telemetry-null]
FAILED plugins/superheroes/lib/tests/test_synthesis_nothing_to_group_2527.py::test_t2_flagged_empty_grouping_without_observed_tool_calls_is_vacuous[zero-tool-calls-empty-list]
FAILED plugins/superheroes/lib/tests/test_synthesis_nothing_to_group_2527.py::test_t2_flagged_empty_grouping_without_observed_tool_calls_is_vacuous[zero-tool-calls-null]
4 failed in 3.99s
```

**restore:** the inverse edit on `plugins/superheroes/lib/engine_dispatch.py` (`if stamped is not None:` back to `if stamped is not None and stamped.get("read") == "engaged":`).

**restored lines** (as they stand, `grep -n`):
```
5296:        if stamped is not None and stamped.get("read") == "engaged":
```
sha256 of `engine_dispatch.py` after all restores equals the value before the first neutralization (see Disclosures).

**raw green** (exit 0), same command:
```
....                                                                     [100%]
4 passed in 3.38s
```

---

## G-I4 — the record-time binding (`round_driver.py` `_assemble_dispatch_evidence`)

- **axis:** a run opened with `--nothing-to-group` landing on a round with survivors refuses `evidence-nothing-to-group-mismatch`, storing nothing

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
-    if (phase == P_SYNTHESIS and record.get("nothingToGroup") is True
+    if (False and phase == P_SYNTHESIS and record.get("nothingToGroup") is True
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/wo-a-2527-pyc -m pytest -q -p no:cacheprovider --tb=short "plugins/superheroes/lib/tests/test_synthesis_nothing_to_group_2527.py::test_t7_a_flagged_run_cannot_answer_a_round_that_has_survivors"
```

**decisive assertion line (red token):** `test_synthesis_nothing_to_group_2527.py:381`: `assert refused["ok"] is False` → `assert True is False`: the real `record-result` bound the flagged run on a round with a survivor.

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_t7_a_flagged_run_cannot_answer_a_round_that_has_survivors ________
/home/user/wt-2527/plugins/superheroes/lib/tests/test_synthesis_nothing_to_group_2527.py:381: in test_t7_a_flagged_run_cannot_answer_a_round_that_has_survivors
    assert refused["ok"] is False  # ... the driver still refuses it for this round
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   assert True is False
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_synthesis_nothing_to_group_2527.py::test_t7_a_flagged_run_cannot_answer_a_round_that_has_survivors
1 failed in 4.32s
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py` (`if (False and phase == P_SYNTHESIS` back to `if (phase == P_SYNTHESIS`).

**restored lines** (as they stand, `grep -n`):
```
16620:    if (phase == P_SYNTHESIS and record.get("nothingToGroup") is True
```
sha256 of `round_driver.py` after all restores equals the value before the first neutralization (see Disclosures).

**raw green** (exit 0), same command:
```
.                                                                        [100%]
1 passed in 4.46s
```

---

## G-I5 — the `no-runner-evidence` branch (`round_adapters.py` `_authenticate_finder`)

- **axis:** a landing with no runner evidence and an eligible recorded vendor is named for what is missing (`no-runner-evidence`), not as a wrong vendor

**neutralization** (`plugins/superheroes/lib/round_adapters.py`):
```diff
-            if executed is None:
+            if False and executed is None:
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/wo-a-2527-pyc -m pytest -q -p no:cacheprovider --tb=short "plugins/superheroes/lib/tests/test_synthesis_nothing_to_group_2527.py::test_t9_a_landing_with_no_runner_evidence_is_named_for_what_is_missing"
```

**decisive assertion line (red token):** `test_synthesis_nothing_to_group_2527.py:459`: `assert why.startswith("missing-seat-refuse-fold:%s:no-runner-evidence:" % RA.SEAT_SYNTHESIS), why` → `AssertionError: missing-seat-refuse-fold:synthesis:unauthenticated-vendor:executed=None:recorded=claude`, the old spelling.

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_t9_a_landing_with_no_runner_evidence_is_named_for_what_is_missing ____
/home/user/wt-2527/plugins/superheroes/lib/tests/test_synthesis_nothing_to_group_2527.py:459: in test_t9_a_landing_with_no_runner_evidence_is_named_for_what_is_missing
    assert why.startswith("missing-seat-refuse-fold:%s:no-runner-evidence:" % RA.SEAT_SYNTHESIS), why
E   AssertionError: missing-seat-refuse-fold:synthesis:unauthenticated-vendor:executed=None:recorded=claude
E   assert False
E    +  where False = <built-in method startswith of str object at 0x7f447dd37d30>(('missing-seat-refuse-fold:%s:no-runner-evidence:' % 'synthesis'))
E    +    where <built-in method startswith of str object at 0x7f447dd37d30> = 'missing-seat-refuse-fold:synthesis:unauthenticated-vendor:executed=None:recorded=claude'.startswith
E    +    and   'synthesis' = RA.SEAT_SYNTHESIS
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_synthesis_nothing_to_group_2527.py::test_t9_a_landing_with_no_runner_evidence_is_named_for_what_is_missing
1 failed in 3.64s
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_adapters.py` (`if False and executed is None:` back to `if executed is None:`).

**restored lines** (as they stand, `grep -n`):
```
668:            if executed is None:
```
sha256 of `round_adapters.py` after all restores equals the value before the first neutralization (see Disclosures).

**raw green** (exit 0), same command:
```
.                                                                        [100%]
1 passed in 3.36s
```
