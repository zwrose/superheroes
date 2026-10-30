# C1-L11b (WO-H) bite-proof — a fresh report that matches a carried finding is merged into it, and its evidence survives

**Provenance:** implementer WO-H3, re-capturing WO-H's guard on `lib/round_driver.py`, `lib/tests/test_c1l11b_carried_findings.py`

Declared guarded element (from the order): H1 `round_driver._with_carried`, the `merged = _merge_same_finding(rows[id(h)], c)` line (the axis comment at `round_driver.py:1647` cites this record). It was neutralized with one targeted edit and restored with the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2266` (head `af12ff89`) under `timeout 600 scripts/pinned-python -B -m pytest <node ids> -q -p no:cacheprovider`. The captures are the runner's whole output for each run apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out; nothing is redacted (no secrets, tokens or URLs appear in the captures).

| ID | Guarded element | Axis | Proving tests |
|---|---|---|---|
| H1 | `round_driver.py:1648` `_with_carried`, the `merged = _merge_same_finding(rows[id(h)], c)` line | a fresh report that matches a carried finding is merged into it and its evidence survives, under the carried key | `test_c1_a_held_minor_code_quality_finding_merges_with_a_fresh_important_real_report_under_the_held_key` and `test_c4_a_fresh_report_that_carries_a_break_it_test_keeps_it_when_merged_into_the_held_finding` |

Not separately neutralized (the unproven part of this record): the held row's stored key and raised round being kept over the merged row (the `for field in (...)` loop just below the guarded line), the no-held-findings early return, and the fresh-report-under-another-key edge (`test_c3`) are not neutralized here. `test_c2` (a held Important finding stays Important against a fresh Minor report) is not in the proving set and was not run under the neutralization.

---

## H1 — the merge of a fresh report into its carried finding

**axis:** a fresh report that matches a carried finding is merged into it and its evidence survives, under the carried key.

**neutralization** (`round_driver.py`, `_with_carried`: the merge replaced by a copy of the held row, so the fresh report is dropped):
```python
-        merged = _merge_same_finding(rows[id(h)], c)
+        merged = dict(rows[id(h)])
```

**raw red:** `timeout 600 scripts/pinned-python -B -m pytest plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py::test_c1_a_held_minor_code_quality_finding_merges_with_a_fresh_important_real_report_under_the_held_key plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py::test_c4_a_fresh_report_that_carries_a_break_it_test_keeps_it_when_merged_into_the_held_finding -q -p no:cacheprovider`
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_c1_a_held_minor_code_quality_finding_merges_with_a_fresh_important_real_report_under_the_held_key _

    def test_c1_a_held_minor_code_quality_finding_merges_with_a_fresh_important_real_report_under_the_held_key():
        held = _finding(27, severity="Minor", consequenceKind="code-quality")
        fresh = _compiled(held, consequenceKind="real")
        state = {"_carriedToVerify": [held]}
        [row] = RD._with_carried(state, [fresh])
>       assert row["severity"] == "Important" and row["consequenceKind"] == "real", row
E       AssertionError: {'id': 'F-the', 'title': 'the edited value is wrong', 'severity': 'Minor', 'file': 'src/shared.py', ...}
E       assert ('Minor' == 'Important'
E         
E         - Important
E         + Minor)

/home/user/wt-2266/plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py:400: AssertionError
_ test_c4_a_fresh_report_that_carries_a_break_it_test_keeps_it_when_merged_into_the_held_finding _

    def test_c4_a_fresh_report_that_carries_a_break_it_test_keeps_it_when_merged_into_the_held_finding():
        held = _finding(27, severity="Minor", consequenceKind="code-quality")
        run = {"outcome": "failed", "reason": None, "exitCode": 1, "output": "", "path": "tests/test_x.py", "head": "h"}
        fresh = _compiled(held, consequenceKind="real", suggestion=BREAK_IT_BLOCK)
        fresh[RD.break_it.RUN_FIELD] = run
        assert RD.break_it.carries_test(fresh)
        [row] = RD._with_carried({"_carriedToVerify": [held]}, [fresh])
>       assert row["suggestion"] == BREAK_IT_BLOCK and row[RD.break_it.RUN_FIELD] == run, row
               ^^^^^^^^^^^^^^^^^
E       KeyError: 'suggestion'

/home/user/wt-2266/plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py:429: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py::test_c1_a_held_minor_code_quality_finding_merges_with_a_fresh_important_real_report_under_the_held_key
FAILED plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py::test_c4_a_fresh_report_that_carries_a_break_it_test_keeps_it_when_merged_into_the_held_finding
2 failed in 0.48s
```

**restore:** the inverse edit — `merged = dict(rows[id(h)])` put back to `merged = _merge_same_finding(rows[id(h)], c)`.

**restore receipt** (`grep -n "merged = " plugins/superheroes/lib/round_driver.py`, filtered to the guarded line, then `git status --porcelain plugins/superheroes/lib/round_driver.py`, which printed nothing):
```
1648:        merged = _merge_same_finding(rows[id(h)], c)
```

**raw green:** the same command.
```
..                                                                       [100%]
2 passed in 0.28s
```
