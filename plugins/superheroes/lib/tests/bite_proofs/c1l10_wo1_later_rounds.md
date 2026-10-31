# C1-L10 (WO-1) bite-proof — later rounds end on the audit and the scoped finder; the finder reads only the fix delta

**Provenance:** implementer WO-1 (continuation) / `lib/round_driver.py`, `lib/tests/test_c1l10_later_rounds.py`

Declared guarded elements (from the order): E1 the chokepoint test that no later round schedules a panel (`_settle_delta_converged` ending on `_terminal_converged`); E2 the sibling-hunk test that the scoped finder's surface and diff are only the round's own fix delta (`_enter_delta_round` building `_newSurface` from `_fix_delta_surface`). Each was neutralized with one targeted edit and restored with the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2214` under `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider`. The captures are the runner's whole output for each run apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out; nothing is redacted (no secrets, tokens or URLs appear).

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| E1 | `round_driver.py` `_settle_delta_converged`, the direct call to `_terminal_converged` | a converged review that needed fixes ends in round 2 on the audit and scoped finder; no panel is scheduled in a round ≥ 2 | `test_i1_a_review_that_needed_fixes_ends_on_a_rounds_audit_and_scoped_finder` |
| E2 | `round_driver.py` `_enter_delta_round`, the `_newSurface` / `_fixDeltaDiff` assignment from `_fix_delta_surface` | the scoped finder's surface and diff hold only the lines the fixes changed, never an untouched sibling hunk of a touched file | `test_i2_a_fix_that_touched_only_line_10_gives_the_scoped_finder_nothing_of_the_hunk_at_line_100` |

Cap precedence (#2214, C1-L10a): a loaded state above its round cap is handed back `round-cap` by the cap guard, never as a retired later panel; `_finish_retired_later_panel` returns False on `_round_above_cap`. Proving test: `test_i4_a_round_two_panel_state_at_its_cap_is_retired_but_above_its_cap_hands_back_round_cap`, with `test_c1l4_cap.py::test_t6_a_loaded_state_edited_to_round_five_hands_back_on_the_next_next`.

The other chokepoint tests of the file (the unknown-surface handbacks of I1, the proven-copy filter of I3, the saved-state handbacks of I4) were not separately neutralized in this order; they are the unproven part of this record.

---

## E1 — a later round schedules no panel

**axis:** a converged review that needed fixes ends on a round's audit and scoped finder.

**neutralization** (`round_driver.py`, `_settle_delta_converged`, before its `_terminal_converged` call: the old confirmation re-arm put back in its simplest form):
```python
+    if _advance_round(state, config, reason="confirmation-rearm"):  # BITE-PROOF NEUTRALIZATION (I1)
+        state["step"] = P_PANEL
+        return
     _terminal_converged(state, config, full_panel=False)
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider "plugins/superheroes/lib/tests/test_c1l10_later_rounds.py::test_i1_a_review_that_needed_fixes_ends_on_a_rounds_audit_and_scoped_finder"`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_i1_a_review_that_needed_fixes_ends_on_a_rounds_audit_and_scoped_finder __

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-5/test_i1_a_review_that_needed_f0')

    def test_i1_a_review_that_needed_fixes_ends_on_a_rounds_audit_and_scoped_finder(tmp_path):
        d, cfg = _start(tmp_path)
        terminal, seen = _drive(d, _respond(), cfg)
        state = _state(d)
>       assert terminal["payload"]["verdict"] == "converged", terminal
E       AssertionError: {'ok': True, 'action': 'terminal', 'round': 3, 'phase': 'terminal', ...}
E       assert 'handed-back' == 'converged'
E         
E         - converged
E         + handed-back

/home/user/wt-2214/plugins/superheroes/lib/tests/test_c1l10_later_rounds.py:108: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l10_later_rounds.py::test_i1_a_review_that_needed_fixes_ends_on_a_rounds_audit_and_scoped_finder
1 failed in 6.51s
```

**restore:** the inverse edit (the three added lines removed).

**restore receipt:** a search of `round_driver.py` for `BITE-PROOF` finds nothing, and the function reads again:
```python
def _settle_delta_converged(state, config):
    """Converged candidate tail shared by `_settle_delta` and stall self-recovery when no open work
    remains: the review ends on this round's audit and scoped finder, never on a further panel."""
    _terminal_converged(state, config, full_panel=False)
```

**raw green:** same command
```
.                                                                        [100%]
1 passed in 5.86s
```

---

## E2 — the scoped finder's surface is the fix delta

**axis:** the scoped hunks and `fix-delta.diff` hold nothing of an untouched sibling hunk (line 100) of a file the fix touched (line 10).

**neutralization** (`round_driver.py`, `_enter_delta_round`: the surface taken from the split's `newSurface`, as before this order):
```python
-    state["_newSurface"], state["_fixDeltaDiff"] = fix_delta
+    state["_newSurface"] = split.get("newSurface") or {}; state["_fixDeltaDiff"] = fix_delta[1]  # BITE-PROOF NEUTRALIZATION (I2)
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider "plugins/superheroes/lib/tests/test_c1l10_later_rounds.py::test_i2_a_fix_that_touched_only_line_10_gives_the_scoped_finder_nothing_of_the_hunk_at_line_100"`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_i2_a_fix_that_touched_only_line_10_gives_the_scoped_finder_nothing_of_the_hunk_at_line_100 _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-7/test_i2_a_fix_that_touched_onl0')

    def test_i2_a_fix_that_touched_only_line_10_gives_the_scoped_finder_nothing_of_the_hunk_at_line_100(tmp_path):
        d, n = _at_the_scoped_finder(tmp_path)
        hunks = _read(d, 2, "scoped-hunks.json")
        fix_delta = _read(d, 2, "fix-delta.diff")
        state = _state(d)
        # the surface is the fix's own change (non-empty, though the fix changed only its own finding's hunk)
        assert list(json.loads(hunks)) == ["big.py"] and n["payload"]["hunks"] == json.loads(hunks)
>       assert [(h["start"], h["end"]) for h in json.loads(hunks)["big.py"]] == [(10, 10)]
E       assert [(97, 103)] == [(10, 10)]
E         
E         At index 0 diff: (97, 103) != (10, 10)
E         Use -v to get more diff

/home/user/wt-2214/plugins/superheroes/lib/tests/test_c1l10_later_rounds.py:220: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l10_later_rounds.py::test_i2_a_fix_that_touched_only_line_10_gives_the_scoped_finder_nothing_of_the_hunk_at_line_100
1 failed in 6.19s
```

**restore:** the inverse edit (the original assignment put back).

**restore receipt:** a search of `round_driver.py` for `BITE-PROOF` finds nothing, and line 6201 reads again:
```python
    state["_newSurface"], state["_fixDeltaDiff"] = fix_delta
```

**raw green:** same command
```
.                                                                        [100%]
1 passed in 2.03s
```
