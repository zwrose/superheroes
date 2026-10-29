# C1-L5b (#2243 WO-J) bite-proof — two tightened C1-L5 tests (vet 717 fold, #2244 FU4)

**Provenance:** implementer WO-J / `lib/tests/test_read_parts_c1l5.py`, `lib/tests/test_seat_map_c1l5.py`

Declared guarded elements (from the order): E1 the prechange equality in `engine_dispatch._verify_native_schema`, E2 the seating of a fillable seat under a second maker family in `seat_map.py`. Each was neutralized with one targeted edit and restored with the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2243-j`. The captures below are the runner's whole output for each run apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out; nothing is redacted (no secrets, tokens or URLs appear).

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| E1 | `engine_dispatch.py:4861` `on_disk != prechange` | a saved schema that is neither the current nor the prechange one is refused `native-schema-unreadable`, not taken for the prechange schema | `test_replay_still_refuses_a_saved_schema_that_is_neither_current_nor_prechange` |
| E2 | `seat_map.py:780` the maker-emptied seat branch | with a second maker family live beside an independent one, every seat is filled | `test_i2_a_third_family_is_still_seated_beside_the_two_makers` |

---

## E1 — the prechange equality

- **axis:** `_verify_native_schema` returns the prechange schema only when the schema on disk equals it. The test saves `{}` and a branch without `readParts` (so it would validate against the prechange schema if `{}` were wrongly taken for it), and asserts replay returns `None` and the grade of the same attempt is a forfeit with detail `native-schema-unreadable`. `_parse_review_attempt` returns bare `None`; the detail is recorded on the forfeit `_grade_review_attempt` returns.

**neutralization** (`engine_dispatch.py`, `_verify_native_schema`):
```python
-        if prechange is None or on_disk != prechange:
+        if prechange is None:
             return None, "native-schema-unreadable"
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/c1l5b-pyc-j -m pytest plugins/superheroes/lib/tests/test_read_parts_c1l5.py -q -k test_replay_still_refuses_a_saved_schema_that_is_neither_current_nor_prechange`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_replay_still_refuses_a_saved_schema_that_is_neither_current_nor_prechange _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-51/test_replay_still_refuses_a_sa0')

    def test_replay_still_refuses_a_saved_schema_that_is_neither_current_nor_prechange(tmp_path):
        # axis: the prechange equality in _verify_native_schema; the branch has no readParts, so it would validate against the prechange schema if the saved one were wrongly taken for it
        branch = _branch()
        branch.pop("readParts", None)
        run_dir, state = ted._native_review_grade_state(tmp_path, branch, schema={})
>       assert ted.ED._parse_review_attempt(run_dir, state, 1) is None
E       AssertionError: assert {'ok': True, 'resultKind': 'findings', 'findings': [{'id': 'example', 'severity': 'Critical', 'dimension': 'Architecture', 'taxonomy': 'example', ...}], 'investigated': ['path/to/file.py']} is None
E        +  where {'ok': True, 'resultKind': 'findings', 'findings': [{'id': 'example', 'severity': 'Critical', 'dimension': 'Architecture', 'taxonomy': 'example', ...}], 'investigated': ['path/to/file.py']} = <function _parse_review_attempt at 0x7fd705b22d40>('/tmp/claude-0/pytest-of-root/pytest-51/test_replay_still_refuses_a_sa0/run', {'opened': {'engine': 'codex', 'roleKind': 'review', 'cwd': '/tmp/claude-0/pytest-of-root/pytest-51/test_replay_still_...dPrompt': '', ...}, 'attempts': {1: {'ended': {'exit': 0, 'timedOut': False, 'refusal': None, 'stdoutBytes': 0, ...}}}}, 1)
E        +      where <function _parse_review_attempt at 0x7fd705b22d40> = <module 'engine_dispatch' from '/home/user/wt-2243-j/plugins/superheroes/lib/tests/../engine_dispatch.py'>._parse_review_attempt
E        +        where <module 'engine_dispatch' from '/home/user/wt-2243-j/plugins/superheroes/lib/tests/../engine_dispatch.py'> = ted.ED

/home/user/wt-2243-j/plugins/superheroes/lib/tests/test_read_parts_c1l5.py:200: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_read_parts_c1l5.py::test_replay_still_refuses_a_saved_schema_that_is_neither_current_nor_prechange
1 failed, 39 deselected in 4.48s
```

**restore:** the inverse edit, `if prechange is None:` back to `if prechange is None or on_disk != prechange:`.

**restore receipt:** the restored lines quoted back from the file after the edit (Grep on `on_disk != prechange`, `-B3 -A2`):
```
4858-                engine, run_kind, expected_result_kind)
4859-        except Exception:
4860-            prechange = None
4861:        if prechange is None or on_disk != prechange:
4862-            return None, "native-schema-unreadable"
4863-        return prechange, None
```

**raw green:** the same command was run once on the unneutralized tree before the neutralization (the baseline), and the restored tree is covered by the combined run of the three modules named in the order (see the return); no standalone single-node run was made after this restore, because the order's command budget did not leave one.
```
.                                                                        [100%]
1 passed, 39 deselected in 4.36s
```
(the baseline above is the pre-neutralization run, not a post-restore run)

---

## E2 — a fillable seat left unfilled under a second maker family

- **axis:** with makers `anthropic` and `openai` and `xai` live, every roster seat is seated from `xai`; none reads `source: unfilled` and no `seat-unfilled` degradation is recorded.

**neutralization** (`seat_map.py`, the per-seat eligibility loop in `build`; marks `test-role` unfilled whenever more than one maker family is present):
```python
             eligible = [cfg for cfg in eligible if cfg["family"] not in makers]
-            if not eligible:
+            if not eligible or (len(makers) > 1 and seat == "test-role"):
+                eligible = []
                 maker_emptied_seats.add(seat)
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/c1l5b-pyc-j -m pytest plugins/superheroes/lib/tests/test_seat_map_c1l5.py -q -k test_i2_a_third_family_is_still_seated_beside_the_two_makers`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_i2_a_third_family_is_still_seated_beside_the_two_makers _________

capsys = <_pytest.capture.CaptureFixture object at 0x7f5baed49490>

    def test_i2_a_third_family_is_still_seated_beside_the_two_makers(capsys):
        # axis: (a) with an independent family live, the seats are filled from it alone; (b) no seat is left unfilled
        receipt = _compose(capsys, "--live-vendors", "claude,codex,cursor", "--implementation-engine", "codex",
                           "--host-model", "claude-opus-5", "--pr-number", "2209")
        assert receipt["makerFamilies"] == ["anthropic", "openai"]
        assert _filled_families(receipt) == {"xai"}
        assert set(receipt["seats"]) == set(SM.PANEL_ROSTER)
        unfilled = [seat for seat, entry in receipt["seats"].items() if entry["source"] == SM.UNFILLED_SOURCE]
>       assert unfilled == [], unfilled
E       AssertionError: ['test-role']
E       assert ['test-role'] == []
E         
E         Left contains one more item: 'test-role'
E         Use -v to get more diff

/home/user/wt-2243-j/plugins/superheroes/lib/tests/test_seat_map_c1l5.py:292: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map_c1l5.py::test_i2_a_third_family_is_still_seated_beside_the_two_makers
1 failed, 15 deselected in 4.79s
```
The assertion `_filled_families(receipt) == {"xai"}` before it still passes under this neutralization (the other seats stay filled from `xai`), so the new unfilled-seat assertion is what turns the test red.

**restore:** the inverse edit back to `if not eligible:` followed by `maker_emptied_seats.add(seat)`, with the added `eligible = []` line removed.

**restore receipt:** the restored lines quoted back from the file after the edit (Grep on `if not eligible:`, `-B3 -A2`):
```
777-        # with a maker family and never backfilled.
778-        if makers and seat in MAKER_EXCLUDED_SEATS and eligible:
779-            eligible = [cfg for cfg in eligible if cfg["family"] not in makers]
780:            if not eligible:
781-                maker_emptied_seats.add(seat)
```

**raw green:** same command after the restore
```
.                                                                        [100%]
1 passed, 15 deselected in 0.42s
```
