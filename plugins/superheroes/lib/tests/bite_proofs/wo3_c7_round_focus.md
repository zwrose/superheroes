# Bite-proof record: each round records its focus (wo3_c7_round_focus)

Declared guarded elements (exactly three). Each neutralization was a targeted one-line edit to production code,
undone by the inverse edit. The detector (`plugins/superheroes/lib/tests/test_round_focus_c7.py`) was not edited
between a red and its green. Command shape: `python3 -B -X pycache_prefix=/tmp/claude-0/pyc -m pytest '<node id>' -q -n 0`.

## 1. `focus` on the delta round

- **Guarded element:** `_enter_delta_round` in `plugins/superheroes/lib/round_driver.py`, the `focus` record beside `roundKind = "delta"`.
- **Axis:** a delta round records the fixes it audits (the previous fix batch's finding keys) as its focus.
- **Neutralization:** replaced
  `    _record_round(state, "focus", {"on": "fixes", "fixes": _fix_batch_keys(state)})` with `    pass  # NEUTRALIZED`.
- **Detector:** `test_round_focus_c7.py::test_t1_a_round_that_fixed_two_findings_audits_exactly_those_and_records_them`
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t1_a_round_that_fixed_two_findings_audits_exactly_those_and_records_them _

    def test_t1_a_round_that_fixed_two_findings_audits_exactly_those_and_records_them():
        batch = [_fix("f.py", "bug f"), _fix("g.py", "bug g")]
        keys = [RD._finding_key_of(f) for f in batch]
        state = _round_two_state(batch)
        RD._enter_delta_round(state, _cfg())
        # axis: the delta round records the fixes it audits as its focus — see bite-proof record wo3_c7_round_focus
        assert [t["id"] for t in state["_auditTargets"]] == keys
        assert state["step"] == RD.P_AUDITS
        assert state["rounds"]["2"]["roundKind"] == "delta"
>       assert state["rounds"]["2"]["focus"] == {"on": "fixes", "fixes": keys}
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'focus'

/home/user/wt-l2c/plugins/superheroes/lib/tests/test_round_focus_c7.py:73: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_focus_c7.py::test_t1_a_round_that_fixed_two_findings_audits_exactly_those_and_records_them
1 failed in 1.02s
```

- **Restore:** inverse edit, `    pass  # NEUTRALIZED` back to the line above.
- **Restore receipt (line quoted back, `round_driver.py:5217`):**
  `    _record_round(state, "focus", {"on": "fixes", "fixes": _fix_batch_keys(state)})`
- **Raw green:**

```
.                                                                        [100%]
1 passed in 0.99s
```

## 2. `focus` on the unknown-surface round

- **Guarded element:** `_schedule_full_panel_unknown` in `plugins/superheroes/lib/round_driver.py`, the `focus` record beside `roundKind = "full-panel-unknown-surface"`.
- **Axis:** an unknown-surface round records `wider` with the same detail string the `unknown-surface` decision records.
- **Neutralization:** replaced `    _record_round(state, "focus", {"on": "wider", "why": detail})` with `    pass  # NEUTRALIZED`.
- **Detector:** `test_round_focus_c7.py::test_edge2_an_unknown_surface_round_is_wider_with_the_unknown_surface_detail`
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_edge2_an_unknown_surface_round_is_wider_with_the_unknown_surface_detail _

    def test_edge2_an_unknown_surface_round_is_wider_with_the_unknown_surface_detail():
        state = _unknown_surface_state()
        rec = state["rounds"]["2"]
        detail = [d["detail"] for d in state["decisions"] if d["kind"] == "unknown-surface"]
        assert len(detail) == 1
        assert rec["roundKind"] == "full-panel-unknown-surface"
        # axis: the unknown-surface round records wider with the decision's own detail — see bite-proof record wo3_c7_round_focus
>       assert rec["focus"] == {"on": "wider", "why": detail[0]}
               ^^^^^^^^^^^^
E       KeyError: 'focus'

/home/user/wt-l2c/plugins/superheroes/lib/tests/test_round_focus_c7.py:93: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_focus_c7.py::test_edge2_an_unknown_surface_round_is_wider_with_the_unknown_surface_detail
1 failed in 0.89s
```

- **Restore:** inverse edit, `    pass  # NEUTRALIZED` back to the line above.
- **Restore receipt (line quoted back, `round_driver.py:5134`):**
  `    _record_round(state, "focus", {"on": "wider", "why": detail})`
- **Raw green:**

```
.                                                                        [100%]
1 passed in 0.67s
```

## 3. The `wider` validation in `review_record.py`

- **Guarded element:** `_validate` (the `rounds` check) in `plugins/superheroes/lib/review_record.py`, via `_wider_ok`.
- **Axis:** the account validation refuses a `rounds.wider` that is not a list of `{round: int, why: non-blank str}`, naming `rounds`.
- **Neutralization:** replaced `        and ("wider" not in rounds or _wider_ok(rounds["wider"])), "rounds")` with `        and True, "rounds")`.
- **Detector:** `test_round_focus_c7.py::test_edge3_a_malformed_rounds_wider_is_refused` (the function id, which collects all ten cases: string-round, bool-round, blank-why, empty-why, null-why, missing-why, non-object-entry, string-wider, null-wider, object-wider).
- **Raw red:** the run's last 60 lines (the capture was cut to the tail, so the first cases' traces are not shown); the summary lists all ten cases failed:

```
E       KeyError: 'reason'

/home/user/wt-l2c/plugins/superheroes/lib/tests/test_round_focus_c7.py:161: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_focus_c7.py::test_edge3_a_malformed_rounds_wider_is_refused[string-round]
FAILED plugins/superheroes/lib/tests/test_round_focus_c7.py::test_edge3_a_malformed_rounds_wider_is_refused[bool-round]
FAILED plugins/superheroes/lib/tests/test_round_focus_c7.py::test_edge3_a_malformed_rounds_wider_is_refused[blank-why]
FAILED plugins/superheroes/lib/tests/test_round_focus_c7.py::test_edge3_a_malformed_rounds_wider_is_refused[empty-why]
FAILED plugins/superheroes/lib/tests/test_round_focus_c7.py::test_edge3_a_malformed_rounds_wider_is_refused[null-why]
FAILED plugins/superheroes/lib/tests/test_round_focus_c7.py::test_edge3_a_malformed_rounds_wider_is_refused[missing-why]
FAILED plugins/superheroes/lib/tests/test_round_focus_c7.py::test_edge3_a_malformed_rounds_wider_is_refused[non-object-entry]
FAILED plugins/superheroes/lib/tests/test_round_focus_c7.py::test_edge3_a_malformed_rounds_wider_is_refused[string-wider]
FAILED plugins/superheroes/lib/tests/test_round_focus_c7.py::test_edge3_a_malformed_rounds_wider_is_refused[null-wider]
FAILED plugins/superheroes/lib/tests/test_round_focus_c7.py::test_edge3_a_malformed_rounds_wider_is_refused[object-wider]
10 failed in 0.96s
```

  The failing assertion is the refusal: with the check neutralized the write succeeds (`out` carries no `reason`), where the detector expects `(False, "review-account-invalid", "rounds")`.
- **Restore:** inverse edit, `        and True, "rounds")` back to the line above.
- **Restore receipt (line quoted back, `review_record.py`, in `_validate`):**
  `        and ("wider" not in rounds or _wider_ok(rounds["wider"])), "rounds")`
- **Raw green:**

```
..........                                                               [100%]
10 passed in 0.98s
```
