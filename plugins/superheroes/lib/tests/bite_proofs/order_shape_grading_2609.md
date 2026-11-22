# WO-1 (#2609) bite-proof — every order shape the review round driver can emit, graded by the real gate

**Provenance:** claude / sonnet-5.5 (implementer, WO-1); `plugins/superheroes/lib/round_orders.py` (`ORDER_SHAPES`, `order_shape`), tests in `plugins/superheroes/lib/tests/test_order_shape_grading_2609.py`. The neutralized shipped sources are `plugins/superheroes/lib/engine_dispatch.py` (`_finish_review_grade_from_parse`), `plugins/superheroes/lib/round_driver.py` (`_advance`) and `plugins/superheroes/lib/round_orders.py`.

Declared guarded-element set (from the order): **R1**, **R2**, **R3**, **R4**, **R5**, **R6**. Each was neutralized by one targeted edit (the Edit tool, exact-text match, the target unique in its file), the proving test selected by its exact node id (so every parametrized case of it ran), the inverse edit applied, and the same selection run again with the same flags. No `git checkout`, `git restore`, `git reset` or `git stash` was used. The sha256 of each of the three neutralized files was taken before the first neutralization and after the last restore.

## Guarded elements

| ID | Guarded element | Axis | Proving node |
|---|---|---|---|
| R1 | the #2475 exemption (`engine_dispatch.py` `_finish_review_grade_from_parse`, `and kind != engine_adapter.review_payload_key("grouping")):`) | a non-empty grouping in a PR-body run is graded ok with no `investigated` list | `test_order_shape_grading_2609.py::test_d_minimal_answer_grades_ok` |
| R2 | the #2527 flagged-empty branch (`engine_dispatch.py`, `if (opened.get("nothingToGroup") is True and kind == "grouping" and has_payload`) | an engaged seat's empty grouping on a repeat-only order is graded ok | `test_order_shape_grading_2609.py::test_d_minimal_answer_grades_ok` |
| R3 | fixture completeness (`round_orders.ORDER_SHAPES` against `FIXTURES`) | a row with no fixture fails | `test_order_shape_grading_2609.py::test_a_fixtures_are_exactly_the_seat_rows` |
| R4 | the source key census (`round_driver._advance` against the rows' `payloadKeys`) | a payload key `_advance` can write that no row declares fails | `test_order_shape_grading_2609.py::test_c_source_keys_match_the_declared_keys` |
| R5 | the row's `nothingToGroup` against the emitted payload | a wrong flag on a row fails | `test_order_shape_grading_2609.py::test_b_advance_emits_the_row_it_is_declared_as` |
| R6 | the row's `emptyAnswerValid` against the real grade | a flipped emptiness value fails | `test_order_shape_grading_2609.py::test_d_empty_answer_is_graded_as_the_row_declares` |

## Disclosures

- All six elements went red under their neutralization (pytest exit 1) and green after the restore (exit 0), on the axis each claims. The red exit code was a genuine test failure each time (`N failed`); the session-end dirty-tree guard did not make any red exit code ambiguous.
- Each detector was selected by exact node id (`bite-proof.md` § Running a proof), not by `-k`; every command carried `--tb=short`, and the same flags ran for red and green. The command for every element had the shape `scripts/pinned-python -B -X pycache_prefix=/tmp/wo1-2609-pyc -m pytest -q -p no:cacheprovider --tb=short "<node id>"`.
- Redaction: none needed for secrets, tokens or PII. The worktree's absolute path in the captured tracebacks is replaced by `<worktree>`; pytest's own `...` inside a dict repr is pytest's truncation, kept as printed. Nothing else is filtered or trimmed. Every capture is well under 32 KiB, so none is written off-repo.
- R5 and R6 are two of three edits to `round_orders.py`, R3 the third; each was reverted by the inverse edit before the next element, and the file's sha256 after the last restore equals the value taken before the first neutralization (below).
- The file-level sha256 values before the first neutralization and after the last restore are identical for all three files:
  - `plugins/superheroes/lib/engine_dispatch.py` `5d3f761b1b5e2ad9c9a24c7883c40e22b0b0009f92a4d8bd06e7246e17f46cc3`
  - `plugins/superheroes/lib/round_driver.py` `33cc7253aa34f454d8739fa40a6063adaf65d42e3470bfc6e8046befb81acc7d`
  - `plugins/superheroes/lib/round_orders.py` `ec4af360b86a935259e0486cf83859a58cf4c1f9c8601e61b7e01c30a2c9442e`
- Tests in the file that carry no bite-proof of their own here (green in the whole-file run): `test_a_census_states_are_exactly_the_rows`, `test_a_rows_are_well_formed`, `test_classifier_matches_exactly_one_row`, `test_b_every_branch_of_advance_has_a_row`, `test_c_unreadable_constructs_fail_loudly`, `test_c_readable_constructs_are_read`, `test_d_vacuous_answer_is_refused`, `test_d_opened_run_journals_the_row_pin_and_flag`, `test_e_host_reply_rows_are_graded_by_payload_fault`, `test_f_minimal_answers_pass_the_payload_contract`.

---

## R1 — the #2475 exemption (`engine_dispatch.py`)

- **axis:** a non-empty grouping graded in a PR-body run with no `investigated` list is ok, not vacuous

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`):
```diff
-            and kind != engine_adapter.review_payload_key("grouping")):
+            and True):
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/wo1-2609-pyc -m pytest -q -p no:cacheprovider --tb=short "plugins/superheroes/lib/tests/test_order_shape_grading_2609.py::test_d_minimal_answer_grades_ok"
```

**decisive assertion lines (red tokens):** `test_order_shape_grading_2609.py:549`: `assert grade.get("ok") is True, grade` → the grade is `{'forfeit': True, 'reason': 'vacuous', ...}` for `synthesis-survivors-earlier-pr-body-staged` and `synthesis-survivors-pr-body-staged`, the two survivor-synthesis rows in the PR-body mode.

**raw red** (exit 1):
```
....F.F.................                                                 [100%]
=================================== FAILURES ===================================
_ test_d_minimal_answer_grades_ok[synthesis-survivors-earlier-pr-body-staged] __
<worktree>/plugins/superheroes/lib/tests/test_order_shape_grading_2609.py:549: in test_d_minimal_answer_grades_ok
    assert grade.get("ok") is True, grade
E   AssertionError: {'forfeit': True, 'reason': 'vacuous', 'engagement': {'tokens': 110, 'toolCalls': 1, 'stdoutBytes': 384, 'wallSeconds': 1.0, ...}, 'investigatedRejected': ['not-a-list'], ...}
E   assert None is True
E    +  where None = <built-in method get of dict object at 0x105a39b80>('ok')
E    +    where <built-in method get of dict object at 0x105a39b80> = {'forfeit': True, 'reason': 'vacuous', 'engagement': {'tokens': 110, 'toolCalls': 1, 'stdoutBytes': 384, 'wallSeconds': 1.0, ...}, 'investigatedRejected': ['not-a-list'], ...}.get
_____ test_d_minimal_answer_grades_ok[synthesis-survivors-pr-body-staged] ______
<worktree>/plugins/superheroes/lib/tests/test_order_shape_grading_2609.py:549: in test_d_minimal_answer_grades_ok
    assert grade.get("ok") is True, grade
E   AssertionError: {'forfeit': True, 'reason': 'vacuous', 'engagement': {'tokens': 110, 'toolCalls': 1, 'stdoutBytes': 384, 'wallSeconds': 1.0, ...}, 'investigatedRejected': ['not-a-list'], ...}
E   assert None is True
E    +  where None = <built-in method get of dict object at 0x1092ccd80>('ok')
E    +    where <built-in method get of dict object at 0x1092ccd80> = {'forfeit': True, 'reason': 'vacuous', 'engagement': {'tokens': 110, 'toolCalls': 1, 'stdoutBytes': 384, 'wallSeconds': 1.0, ...}, 'investigatedRejected': ['not-a-list'], ...}.get
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_order_shape_grading_2609.py::test_d_minimal_answer_grades_ok[synthesis-survivors-earlier-pr-body-staged]
FAILED plugins/superheroes/lib/tests/test_order_shape_grading_2609.py::test_d_minimal_answer_grades_ok[synthesis-survivors-pr-body-staged]
2 failed, 22 passed in 4.72s
```

**restore:** the inverse edit on `plugins/superheroes/lib/engine_dispatch.py` (`and True):` back to `and kind != engine_adapter.review_payload_key("grouping")):`).

**restored lines** (as they stand, `grep -n`):
```
5323:            and kind != engine_adapter.review_payload_key("grouping")):
```
sha256 of `engine_dispatch.py` after all restores equals the value before the first neutralization (see Disclosures).

**raw green** (exit 0), same command:
```
........................                                                 [100%]
24 passed in 4.77s
```

---

## R2 — the #2527 flagged-empty branch (`engine_dispatch.py`)

- **axis:** a run opened with `--nothing-to-group` grades an engaged seat's empty grouping ok

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`):
```diff
-    if (opened.get("nothingToGroup") is True and kind == "grouping" and has_payload
+    if (False and opened.get("nothingToGroup") is True and kind == "grouping" and has_payload
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/wo1-2609-pyc -m pytest -q -p no:cacheprovider --tb=short "plugins/superheroes/lib/tests/test_order_shape_grading_2609.py::test_d_minimal_answer_grades_ok"
```

**decisive assertion lines (red tokens):** `test_order_shape_grading_2609.py:549`: `assert grade.get("ok") is True, grade` → the grade is `{'forfeit': True, 'reason': 'vacuous', ...}` with `'toolCalls': 1` for `synthesis-repeat-only` and `synthesis-repeat-none`, in both modes (four cases): the vacuous forfeit #2527 removed for a flagged, engaged run.

**raw red** (exit 1):
```
........FFFF............                                                 [100%]
=================================== FAILURES ===================================
____ test_d_minimal_answer_grades_ok[synthesis-repeat-only-pr-body-staged] _____
<worktree>/plugins/superheroes/lib/tests/test_order_shape_grading_2609.py:549: in test_d_minimal_answer_grades_ok
    assert grade.get("ok") is True, grade
E   AssertionError: {'forfeit': True, 'reason': 'vacuous', 'engagement': {'tokens': 110, 'toolCalls': 1, 'stdoutBytes': 330, 'wallSeconds': 1.0, ...}, 'investigatedRejected': ['not-a-list'], ...}
E   assert None is True
E    +  where None = <built-in method get of dict object at 0x10aab2e80>('ok')
E    +    where <built-in method get of dict object at 0x10aab2e80> = {'forfeit': True, 'reason': 'vacuous', 'engagement': {'tokens': 110, 'toolCalls': 1, 'stdoutBytes': 330, 'wallSeconds': 1.0, ...}, 'investigatedRejected': ['not-a-list'], ...}.get
__ test_d_minimal_answer_grades_ok[synthesis-repeat-only-pr-body-not-staged] ___
<worktree>/plugins/superheroes/lib/tests/test_order_shape_grading_2609.py:549: in test_d_minimal_answer_grades_ok
    assert grade.get("ok") is True, grade
E   AssertionError: {'forfeit': True, 'reason': 'vacuous', 'engagement': {'tokens': 110, 'toolCalls': 1, 'stdoutBytes': 330, 'wallSeconds': 1.0, ...}, 'investigatedRejected': ['not-a-list'], ...}
E   assert None is True
E    +  where None = <built-in method get of dict object at 0x10aae8ac0>('ok')
E    +    where <built-in method get of dict object at 0x10aae8ac0> = {'forfeit': True, 'reason': 'vacuous', 'engagement': {'tokens': 110, 'toolCalls': 1, 'stdoutBytes': 330, 'wallSeconds': 1.0, ...}, 'investigatedRejected': ['not-a-list'], ...}.get
____ test_d_minimal_answer_grades_ok[synthesis-repeat-none-pr-body-staged] _____
<worktree>/plugins/superheroes/lib/tests/test_order_shape_grading_2609.py:549: in test_d_minimal_answer_grades_ok
    assert grade.get("ok") is True, grade
E   AssertionError: {'forfeit': True, 'reason': 'vacuous', 'engagement': {'tokens': 110, 'toolCalls': 1, 'stdoutBytes': 330, 'wallSeconds': 1.0, ...}, 'investigatedRejected': ['not-a-list'], ...}
E   assert None is True
E    +  where None = <built-in method get of dict object at 0x10aab11c0>('ok')
E    +    where <built-in method get of dict object at 0x10aab11c0> = {'forfeit': True, 'reason': 'vacuous', 'engagement': {'tokens': 110, 'toolCalls': 1, 'stdoutBytes': 330, 'wallSeconds': 1.0, ...}, 'investigatedRejected': ['not-a-list'], ...}.get
__ test_d_minimal_answer_grades_ok[synthesis-repeat-none-pr-body-not-staged] ___
<worktree>/plugins/superheroes/lib/tests/test_order_shape_grading_2609.py:549: in test_d_minimal_answer_grades_ok
    assert grade.get("ok") is True, grade
E   AssertionError: {'forfeit': True, 'reason': 'vacuous', 'engagement': {'tokens': 110, 'toolCalls': 1, 'stdoutBytes': 330, 'wallSeconds': 1.0, ...}, 'investigatedRejected': ['not-a-list'], ...}
E   assert None is True
E    +  where None = <built-in method get of dict object at 0x10aaef880>('ok')
E    +    where <built-in method get of dict object at 0x10aaef880> = {'forfeit': True, 'reason': 'vacuous', 'engagement': {'tokens': 110, 'toolCalls': 1, 'stdoutBytes': 330, 'wallSeconds': 1.0, ...}, 'investigatedRejected': ['not-a-list'], ...}.get
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_order_shape_grading_2609.py::test_d_minimal_answer_grades_ok[synthesis-repeat-only-pr-body-staged]
FAILED plugins/superheroes/lib/tests/test_order_shape_grading_2609.py::test_d_minimal_answer_grades_ok[synthesis-repeat-only-pr-body-not-staged]
FAILED plugins/superheroes/lib/tests/test_order_shape_grading_2609.py::test_d_minimal_answer_grades_ok[synthesis-repeat-none-pr-body-staged]
FAILED plugins/superheroes/lib/tests/test_order_shape_grading_2609.py::test_d_minimal_answer_grades_ok[synthesis-repeat-none-pr-body-not-staged]
4 failed, 20 passed in 4.48s
```

**restore:** the inverse edit on `plugins/superheroes/lib/engine_dispatch.py` (`if (False and opened.get(` back to `if (opened.get(`).

**restored lines** (as they stand, `grep -n`):
```
5292:    if (opened.get("nothingToGroup") is True and kind == "grouping" and has_payload
```
sha256 of `engine_dispatch.py` after all restores equals the value before the first neutralization (see Disclosures).

**raw green** (exit 0), same command:
```
........................                                                 [100%]
24 passed in 4.68s
```

---

## R3 — fixture completeness (`round_orders.py`, a throwaway row with no fixture)

- **axis:** a new fixture-less row fails the fixture-completeness test and names the id

**neutralization** (`plugins/superheroes/lib/round_orders.py`, a row added inside `ORDER_SHAPES`):
```diff
+    _shape("throwaway", round_phases.P_SWEEP, CHANNEL_HOST_REPLY, ("throwaway",), empty_answer_valid=True),
     _shape("run-verify", round_phases.P_VERIFY, CHANNEL_ORCHESTRATOR, ("command",)),
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/wo1-2609-pyc -m pytest -q -p no:cacheprovider --tb=short "plugins/superheroes/lib/tests/test_order_shape_grading_2609.py::test_a_fixtures_are_exactly_the_seat_rows"
```

**decisive assertion lines (red tokens):** `test_order_shape_grading_2609.py:215`: `assert set(FIXTURES) == seat_ids, ...` → `no fixture for ['throwaway']; no row for fixture []`.

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_a_fixtures_are_exactly_the_seat_rows ___________________
<worktree>/plugins/superheroes/lib/tests/test_order_shape_grading_2609.py:215: in test_a_fixtures_are_exactly_the_seat_rows
    assert set(FIXTURES) == seat_ids, "no fixture for %s; no row for fixture %s" % (
E   AssertionError: no fixture for ['throwaway']; no row for fixture []
E   assert {'audits', 'a...nd-test', ...} == {'audits', 'a...nd-test', ...}
E     
E     Extra items in the right set:
E     'throwaway'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_order_shape_grading_2609.py::test_a_fixtures_are_exactly_the_seat_rows
1 failed in 3.84s
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_orders.py` (the `throwaway` row line removed).

**restored lines** (as they stand, `grep -n throwaway round_orders.py`): no match, so the row is gone; the table reads as before the neutralization. sha256 of `round_orders.py` after all restores equals the value before the first neutralization (see Disclosures).

**raw green** (exit 0), same command:
```
.                                                                        [100%]
1 passed in 3.07s
```

---

## R4 — the source key census (`round_driver.py`, a new conditional payload key)

- **axis:** a payload key `_advance` can write that no row declares fails, so a new driver variant cannot ship unnoticed

**neutralization** (`plugins/superheroes/lib/round_driver.py`, panel branch of `_advance`):
```diff
                    "ceilings": _panel_ceilings(state, roster)}
+        if state.get("_throwaway"):
+            payload["throwaway"] = True
     elif step == P_VERIFIERS:
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/wo1-2609-pyc -m pytest -q -p no:cacheprovider --tb=short "plugins/superheroes/lib/tests/test_order_shape_grading_2609.py::test_c_source_keys_match_the_declared_keys"
```

**decisive assertion lines (red tokens):** `test_order_shape_grading_2609.py:407`: `assert written <= declared, ...` → `keys `_advance` writes that no dispatch-panel row declares: ['throwaway']`. The key is conditional (never emitted in any test state), so only the source census sees it.

**raw red** (exit 1):
```
..F.......                                                               [100%]
=================================== FAILURES ===================================
__________ test_c_source_keys_match_the_declared_keys[dispatch-panel] __________
<worktree>/plugins/superheroes/lib/tests/test_order_shape_grading_2609.py:407: in test_c_source_keys_match_the_declared_keys
    assert written <= declared, "keys `_advance` writes that no %s row declares: %s" % (phase, sorted(written - declared))
E   AssertionError: keys `_advance` writes that no dispatch-panel row declares: ['throwaway']
E   assert {'ceilings', ...away', 'tier'} <= {'ceilings', ...ices', 'tier'}
E     
E     Extra items in the left set:
E     'throwaway'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_order_shape_grading_2609.py::test_c_source_keys_match_the_declared_keys[dispatch-panel]
1 failed, 9 passed in 3.27s
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py` (the two added lines removed).

**restored lines** (as they stand, `grep -n -A 1`; no `_throwaway` match remains):
```
3747:                   "ceilings": _panel_ceilings(state, roster)}
3748-    elif step == P_VERIFIERS:
```
sha256 of `round_driver.py` after all restores equals the value before the first neutralization (see Disclosures).

**raw green** (exit 0), same command:
```
..........                                                               [100%]
10 passed in 4.12s
```

---

## R5 — the row's `nothingToGroup` (`round_orders.py`, a wrong flag on a survivor synthesis row)

- **axis:** a row whose `nothingToGroup` disagrees with the emitted payload fails

**neutralization** (`plugins/superheroes/lib/round_orders.py`, the `synthesis-survivors` row):
```diff
-           result_kind="grouping", empty_answer_valid=False, empty_refused_by=REFUSED_BY_RUNNER,
+           result_kind="grouping", nothing_to_group=True, empty_answer_valid=False, empty_refused_by=REFUSED_BY_RUNNER,
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/wo1-2609-pyc -m pytest -q -p no:cacheprovider --tb=short "plugins/superheroes/lib/tests/test_order_shape_grading_2609.py::test_b_advance_emits_the_row_it_is_declared_as"
```

**decisive assertion lines (red tokens):** `test_order_shape_grading_2609.py:288`: `assert row["nothingToGroup"] == (payload.get("nothingToGroup") is True), payload` → `assert True == (None is True)` for `synthesis-survivors`.

**raw red** (exit 1):
```
...F.............                                                        [100%]
=================================== FAILURES ===================================
_____ test_b_advance_emits_the_row_it_is_declared_as[synthesis-survivors] ______
<worktree>/plugins/superheroes/lib/tests/test_order_shape_grading_2609.py:288: in test_b_advance_emits_the_row_it_is_declared_as
    assert row["nothingToGroup"] == (payload.get("nothingToGroup") is True), payload
E   AssertionError: {'findings': [{'title': 'bug', 'severity': 'Important', 'file': 'f.py', 'line': 1, ...}], 'refuted': [{'title': 'bug', 'severity': 'Important', 'file': 'f.py', 'line': 1, ...}], 'earlier': []}
E   assert True == (None is True)
E    +  where None = <built-in method get of dict object at 0x10a575940>('nothingToGroup')
E    +    where <built-in method get of dict object at 0x10a575940> = {'findings': [{'title': 'bug', 'severity': 'Important', 'file': 'f.py', 'line': 1, ...}], 'refuted': [{'title': 'bug', 'severity': 'Important', 'file': 'f.py', 'line': 1, ...}], 'earlier': []}.get
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_order_shape_grading_2609.py::test_b_advance_emits_the_row_it_is_declared_as[synthesis-survivors]
1 failed, 16 passed in 2.89s
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_orders.py` (`nothing_to_group=True, ` removed from the row).

**restored lines** (as they stand, `grep -n -A 2`):
```
849:    _shape("synthesis-survivors", round_phases.P_SYNTHESIS, CHANNEL_RUNNER, _SYNTHESIS_KEYS,
850-           result_kind="grouping", empty_answer_valid=False, empty_refused_by=REFUSED_BY_RUNNER,
851-           when=(("findings", "nonempty"), ("earlier", "empty"))),
```
sha256 of `round_orders.py` after all restores equals the value before the first neutralization (see Disclosures).

**raw green** (exit 0), same command:
```
.................                                                        [100%]
17 passed in 3.00s
```

---

## R6 — the row's `emptyAnswerValid` (`round_orders.py`, the panel row flipped to False)

- **axis:** a row whose `emptyAnswerValid` is flipped fails, because the real grade of the empty answer does not match the declaration

**neutralization** (`plugins/superheroes/lib/round_orders.py`, the `panel` row, with `emptyRefusedBy` the runner):
```diff
-           result_kind="findings", expected_result_kind="findings", empty_answer_valid=True),
+           result_kind="findings", expected_result_kind="findings", empty_answer_valid=False,
+           empty_refused_by=REFUSED_BY_RUNNER),
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/wo1-2609-pyc -m pytest -q -p no:cacheprovider --tb=short "plugins/superheroes/lib/tests/test_order_shape_grading_2609.py::test_d_empty_answer_is_graded_as_the_row_declares"
```

**decisive assertion lines (red tokens):** `test_order_shape_grading_2609.py:573`: `assert grade.get("ok") is not True and grade.get("forfeit") is True, grade` → the grade is `{'ok': True, 'resultKind': 'findings', 'findings': [], ...}` for `panel` in both modes: the runner the row names as refusing grades the empty answer ok.

**raw red** (exit 1):
```
FF......................                                                 [100%]
=================================== FAILURES ===================================
___ test_d_empty_answer_is_graded_as_the_row_declares[panel-pr-body-staged] ____
<worktree>/plugins/superheroes/lib/tests/test_order_shape_grading_2609.py:573: in test_d_empty_answer_is_graded_as_the_row_declares
    assert grade.get("ok") is not True and grade.get("forfeit") is True, grade
E   AssertionError: {'ok': True, 'resultKind': 'findings', 'findings': [], 'engagement': {'tokens': 110, 'toolCalls': 1, 'stdoutBytes': 378, 'wallSeconds': 1.0, ...}, ...}
E   assert (True is not True)
E    +  where True = <built-in method get of dict object at 0x108d9a180>('ok')
E    +    where <built-in method get of dict object at 0x108d9a180> = {'ok': True, 'resultKind': 'findings', 'findings': [], 'engagement': {'tokens': 110, 'toolCalls': 1, 'stdoutBytes': 378, 'wallSeconds': 1.0, ...}, ...}.get
_ test_d_empty_answer_is_graded_as_the_row_declares[panel-pr-body-not-staged] __
<worktree>/plugins/superheroes/lib/tests/test_order_shape_grading_2609.py:573: in test_d_empty_answer_is_graded_as_the_row_declares
    assert grade.get("ok") is not True and grade.get("forfeit") is True, grade
E   AssertionError: {'ok': True, 'resultKind': 'findings', 'findings': [], 'engagement': {'tokens': 110, 'toolCalls': 1, 'stdoutBytes': 378, 'wallSeconds': 1.0, ...}, ...}
E   assert (True is not True)
E    +  where True = <built-in method get of dict object at 0x102f9bf40>('ok')
E    +    where <built-in method get of dict object at 0x102f9bf40> = {'ok': True, 'resultKind': 'findings', 'findings': [], 'engagement': {'tokens': 110, 'toolCalls': 1, 'stdoutBytes': 378, 'wallSeconds': 1.0, ...}, ...}.get
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_order_shape_grading_2609.py::test_d_empty_answer_is_graded_as_the_row_declares[panel-pr-body-staged]
FAILED plugins/superheroes/lib/tests/test_order_shape_grading_2609.py::test_d_empty_answer_is_graded_as_the_row_declares[panel-pr-body-not-staged]
2 failed, 22 passed in 5.40s
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_orders.py` (`empty_answer_valid=True),` back on the panel row; the added `empty_refused_by` line removed).

**restored lines** (as they stand): `result_kind="findings", expected_result_kind="findings", empty_answer_valid=True),` on the `panel` row. sha256 of `round_orders.py` after all restores equals the value before the first neutralization (see Disclosures).

**raw green** (exit 0), same command:
```
........................                                                 [100%]
24 passed in 6.03s
```
