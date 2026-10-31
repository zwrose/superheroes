# C1-L10b (WO-1) bite-proof — the vet-728 fold, items 2 to 6

**Provenance:** implementer WO-1 / `lib/round_driver.py` (item 4), `lib/repeat_marks.py` (item 6), `lib/tests/test_c1l10b_repeat_folds.py`, `lib/tests/test_repeat_marks_c1l8.py` (item 5)

Declared guarded elements (from the order): E1 `_apply_repeat_marks`' per-row append; E2 `decide`'s `changed is None` arm. Each was neutralized with one targeted edit through the edit tool and restored with the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2264` under `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -n auto -p no:cacheprovider` (`--timeout 600` is refused by this pytest: `python -m pytest: error: unrecognized arguments: --timeout`, so it was dropped). The captures are the runner's output for each run with the `UV_NATIVE_TLS` warning line and the `bringing up nodes...` lines left out, and the `[gwN] ... Python 3.12.13` worker line left out; nothing is redacted (no secrets, tokens or URLs appear).

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| E1 | `round_driver._apply_repeat_marks`, the `for row in rows: _record_round_append(state, "repeatMarks", row)` loop | a second synthesis wave of one round appends its marks, never replaces the first wave's | `test_c1l10b_repeat_folds.py::test_4_a_second_synthesis_wave_of_one_round_keeps_the_first_waves_marks` |
| E2 | `repeat_marks.decide`, the `changed is None` arm of the shown-wrong branch | an unknown change reads as a change: the repeat is kept only on a `wrong` grade | `test_c1l10b_repeat_folds.py::test_6_an_unknown_change_keeps_a_shown_wrong_repeat_only_on_a_wrong_grade` (2 cases) |

Not bite-proofed by this record: items 2 and 3 (their red is at this base, the fixes are on another branch; the orchestrator records red and green around the merge), the `_wrong_ungraded` ring / dangling-link / self-link tests (2b, 2c, `test_3e`), which are green at this base and were not neutralized here (the consumer they guard, `review_record._wrong_ungraded`, is outside this order's surface), and the known-change cases of `test_6_edge1`. Item 5 adds no guarded element (test strength only): 5a's proof is its premise assertion that the two verifier heads differ (`RD._verifier_head(state, r.dir, 1) != RD._verifier_head(state, r.dir, 2)`, which passed); 5b's new `synthesis_staged_id_fault` assertion pins that a judge name on a finding with no offered ref is refused at the submit check.

---

## E1 — a second synthesis wave appends to the round's `repeatMarks`

**axis:** both waves' marks are kept, the first wave's first.

**neutralization** (`round_driver.py`, `_apply_repeat_marks`):
```python
-    for row in rows:
-        _record_round_append(state, "repeatMarks", row)
+    if rows:  # BITE-PROOF NEUTRALIZED
+        _record_round(state, "repeatMarks", rows)
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -n auto -p no:cacheprovider "plugins/superheroes/lib/tests/test_c1l10b_repeat_folds.py::test_4_a_second_synthesis_wave_of_one_round_keeps_the_first_waves_marks"`
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_4_a_second_synthesis_wave_of_one_round_keeps_the_first_waves_marks ____

    def test_4_a_second_synthesis_wave_of_one_round_keeps_the_first_waves_marks():
        state = TRM._state()
        first, second = TRM._raw("craft a", line=1), TRM._raw("ruled b", line=2)
        TRM._earlier(state, first, "craft", settledReason="cq")
        TRM._earlier(state, second, "ruling", settledReason="decided")
        state["round"] = 2
        TRM._verify(state, [first], {"craft a": "CONFIRMED"})
        TRM._synth(state, None)  # the panel's wave
        assert [m["repeatOf"]["findingKey"] for m in state["rounds"]["2"]["repeatMarks"]] == [TRM._key(first)]
        TRM._verify(state, [second], {"ruled b": "CONFIRMED"})
        TRM._synth(state, None)  # the gap sweep's wave
        marks = state["rounds"]["2"]["repeatMarks"]
>       assert [m["repeatOf"]["findingKey"] for m in marks] == [TRM._key(first), TRM._key(second)], marks
E       AssertionError: [{'id': 'v0', 'findingKey': 'f.py::ruled b@L2', 'source': 'exact', 'kept': True, ...}]
E       assert ['f.py::ruled b@L2'] == ['f.py::craft...::ruled b@L2']
E         
E         At index 0 diff: 'f.py::ruled b@L2' != 'f.py::craft a@L1'
E         Right contains one more item: 'f.py::ruled b@L2'
E         Use -v to get more diff

/home/user/wt-2264/plugins/superheroes/lib/tests/test_c1l10b_repeat_folds.py:176: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l10b_repeat_folds.py::test_4_a_second_synthesis_wave_of_one_round_keeps_the_first_waves_marks
1 failed in 1.90s
```

**restore:** the inverse edit — the `if rows:` / `_record_round(...)` pair put back as the `for row in rows:` / `_record_round_append(...)` loop.

**restore receipt:** `grep -n -B2 -A2 "_record_round_append(state, \"repeatMarks\"" plugins/superheroes/lib/round_driver.py` printed
```
4074-    # axis: a second synthesis wave of one round appends its marks, never replaces the first wave's — see bite-proof record c1l10b_wo1_repeat_folds
4075-    for row in rows:
4076:        _record_round_append(state, "repeatMarks", row)
4077-
4078-
```

**raw green:** same command.
```
.                                                                        [100%]
1 passed in 2.28s
```

---

## E2 — `decide` reads an unknown change as a change

**axis:** a shown-wrong repeat whose change is unknown (`None`, or a callable returning `None`) is not kept unless the new grade is `wrong`.

**neutralization** (`repeat_marks.py`, `decide`):
```python
-        if (changed is None or changed) and grade_verdict != "wrong":
+        if changed and grade_verdict != "wrong":
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -n auto -p no:cacheprovider "plugins/superheroes/lib/tests/test_c1l10b_repeat_folds.py::test_6_an_unknown_change_keeps_a_shown_wrong_repeat_only_on_a_wrong_grade"`
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_6_an_unknown_change_keeps_a_shown_wrong_repeat_only_on_a_wrong_grade[unknown] _

changed = None

    @pytest.mark.parametrize("changed", [None, lambda: None], ids=["unknown", "callable-unknown"])
    def test_6_an_unknown_change_keeps_a_shown_wrong_repeat_only_on_a_wrong_grade(changed):
>       assert repeat_marks.decide("shown-wrong", "confirmed", changed) == (False, None)
E       assert (True, None) == (False, None)
E         
E         At index 0 diff: True != False
E         Use -v to get more diff

/home/user/wt-2264/plugins/superheroes/lib/tests/test_c1l10b_repeat_folds.py:192: AssertionError
_ test_6_an_unknown_change_keeps_a_shown_wrong_repeat_only_on_a_wrong_grade[callable-unknown] _

changed = <function <lambda> at 0x7f06ea6f3240>

    @pytest.mark.parametrize("changed", [None, lambda: None], ids=["unknown", "callable-unknown"])
    def test_6_an_unknown_change_keeps_a_shown_wrong_repeat_only_on_a_wrong_grade(changed):
>       assert repeat_marks.decide("shown-wrong", "confirmed", changed) == (False, None)
E       assert (True, None) == (False, None)
E         
E         At index 0 diff: True != False
E         Use -v to get more diff

/home/user/wt-2264/plugins/superheroes/lib/tests/test_c1l10b_repeat_folds.py:192: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l10b_repeat_folds.py::test_6_an_unknown_change_keeps_a_shown_wrong_repeat_only_on_a_wrong_grade[unknown]
FAILED plugins/superheroes/lib/tests/test_c1l10b_repeat_folds.py::test_6_an_unknown_change_keeps_a_shown_wrong_repeat_only_on_a_wrong_grade[callable-unknown]
2 failed in 1.74s
```

**restore:** the inverse edit — `if (changed is None or changed) and grade_verdict != "wrong":` put back.

**restore receipt:** `grep -n "changed is None" plugins/superheroes/lib/repeat_marks.py` printed
```
57:        if (changed is None or changed) and grade_verdict != "wrong":
```

**raw green:** same command.
```
..                                                                       [100%]
2 passed in 1.52s
```

## W1-E3 — the chain closure repeats until nothing changes

**guarded element:** the fixed-point loop in `_wrong_ungraded` (`review_record.py`, lines 2413-2420: `while grew:` with `grew = True` after a key is added). Axis: a chain of kept repeats listed child-first (`[c, b, a]`) still passes link by link to the verifier-closed root; a single forward pass admits only links listed after their parent. Detectors: `test_2a_reverse_a_chain_listed_child_first_still_passes_link_by_link_to_the_root` and `test_2d_reverse_the_writer_takes_the_whole_chain_listed_child_first` in `plugins/superheroes/lib/tests/test_c1l10b_repeat_folds.py` (the parent-first `test_2a_` and `test_2d_` stay and cannot tell the two apart).

**neutralization** (`review_record.py`, `_wrong_ungraded`): the loop runs one pass only.
```diff
                 passing.add(_key(f))
-                grew = True
+                grew = False
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/wo7-pyc -m pytest plugins/superheroes/lib/tests/test_c1l10b_repeat_folds.py -q -p no:cacheprovider -k reverse --tb=line` (the `--tb=line` flag was added to the order's command form to keep the capture short)
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FF                                                                       [100%]
=================================== FAILURES ===================================
E   assert [0] == []
      
      Left contains one more item: 0
      Use -v to get more diff
/home/user/sh-2264/plugins/superheroes/lib/tests/test_c1l10b_repeat_folds.py:55: assert [0] == []
E   AssertionError: {'ok': False, 'reason': 'review-account-invalid', 'detail': "findings[0] is shown-wrong without the verifier's grade"}
    assert False
/home/user/sh-2264/plugins/superheroes/lib/tests/test_c1l10b_repeat_folds.py:98: AssertionError: {'ok': False, 'reason': 'review-account-invalid', 'detail': "findings[0] is shown-wrong without the verifier's grade"}
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l10b_repeat_folds.py::test_2a_reverse_a_chain_listed_child_first_still_passes_link_by_link_to_the_root
FAILED plugins/superheroes/lib/tests/test_c1l10b_repeat_folds.py::test_2d_reverse_the_writer_takes_the_whole_chain_listed_child_first
2 failed, 19 deselected in 3.95s
```

**restore:** the inverse edit — `grew = True` put back after `passing.add(_key(f))`.

**restore receipt:** `grep -n "grew" plugins/superheroes/lib/review_record.py` printed
```
2413:    grew = True
2414:    while grew:
2415:        grew = False
2420:                grew = True
```
and `git status --porcelain -- plugins/superheroes/lib/review_record.py` printed nothing (byte-identical to `109af679`).

**raw green:** same command as the raw red.
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..                                                                       [100%]
2 passed, 19 deselected in 4.40s
```
