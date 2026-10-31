# C1-L11b (WO-D2 / WO-D2b) bite-proof — a carried finding is audited, and one the audit does not discharge goes to the verifier

**Provenance:** implementer WO-D2b / `lib/round_driver.py`, `lib/tests/test_c1l11b_carried_findings.py`

Declared guarded elements (from the order): (a) the ledger seeding of carried findings, in `_seed_carried`; (b) the send-back staging, in `_fold_audits`. Each was neutralized with one targeted edit and restored with the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2266` under `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider`. The captures are the runner's whole output for each run apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out and, for (a), the long `state = {...}` dumps in the pytest traceback, which are cut to the lines shown by the runner itself; nothing is redacted (no secrets, tokens or URLs appear).

| ID | Guarded element | Axis | Proving tests |
|---|---|---|---|
| (a) | `round_driver.py` `_seed_carried`, the `_seed_ledger_entry(...)` call (line 1600) | a carried finding is on the ledger under its stored key, with a raised sequence, before its disposition is recorded | `test_t1_a_carried_finding_a_later_commit_fixed_is_settled_fixed_and_the_record_reads_reviewed[changed]` and `[full]` |
| (b) | `round_driver.py` `_fold_audits`, the `state["_carriedToVerify"] = ...` staging (line 7156) | a carried finding the audit does not discharge is staged for the verifier, never left for the fix queue | `test_t2_a_carried_finding_the_audit_does_not_discharge_goes_to_the_verifier_and_stays_open_when_confirmed[changed]` and `[full]` |

Not separately neutralized (the unproven part of this record): the `entry["outcome"] is not None` skip in `_carried_findings` (line 1537, carries an axis comment; its tests are `test_t4_e3_...`, never run red here); the `_with_carried` de-duplication (E2); the T3, T4 and T5 tests.

---

## (a) — the ledger seeding

**axis:** a carried finding is on the ledger under its stored key, with a raised sequence and no disposition, before the audit runs.

**neutralization** (`round_driver.py`, `_seed_carried`: the seeding call replaced by `pass`):
```python
-            _seed_ledger_entry(state, ledger, seen, finding, key, state["round"])
+            pass
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py -k "test_t1_a_carried_finding_a_later_commit_fixed"`
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_t1_a_carried_finding_a_later_commit_fixed_is_settled_fixed_and_the_record_reads_reviewed[changed] _
...
        key = finding[SC.FINDING_KEY_FIELD]
        # seeded under the stored key before the audit ran: a raised sequence and no disposition yet
>       seeded = _row(state, key)
                 ^^^^^^^^^^^^^^^^

/home/user/wt-2266/plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py:152: 
...
    def _row(state, key):
>       [row] = [r for r in state.get(SC.DISPOSITION_LEDGER_KEY) or [] if SC.finding_identity_key(r) == key]
        ^^^^^
E       ValueError: not enough values to unpack (expected 1, got 0)

/home/user/wt-2266/plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py:114: ValueError
_ test_t1_a_carried_finding_a_later_commit_fixed_is_settled_fixed_and_the_record_reads_reviewed[full] _
...
E       ValueError: not enough values to unpack (expected 1, got 0)

/home/user/wt-2266/plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py:114: ValueError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py::test_t1_a_carried_finding_a_later_commit_fixed_is_settled_fixed_and_the_record_reads_reviewed[changed]
FAILED plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py::test_t1_a_carried_finding_a_later_commit_fixed_is_settled_fixed_and_the_record_reads_reviewed[full]
2 failed, 14 deselected in 2.71s
```
(`...` marks the parametrize decorator, the test body above line 152 and the `state = {...}` dumps, which the runner printed and this record leaves out; the `[full]` block repeats the `[changed]` block's failing lines.)

**restore:** the inverse edit (`pass` replaced by the `_seed_ledger_entry(...)` call).

**restore receipt:** a search of `round_driver.py` for `_seed_ledger_entry(state, ledger, seen, finding, key` finds line 1600, which reads again:
```python
            _seed_ledger_entry(state, ledger, seen, finding, key, state["round"])
```

**raw green:** same command
```
..                                                                       [100%]
2 passed, 14 deselected in 4.03s
```

---

## (b) — the send-back staging

**axis:** a carried finding the audit did not discharge is added to `_carriedToVerify`, so it joins the round's candidates at the verifier; without it the round ends with no candidate and goes terminal.

**neutralization** (`round_driver.py`, `_fold_audits`: the list of sent-back findings emptied):
```python
-        state["_carriedToVerify"] = (state.get("_carriedToVerify") or []) + [carried_audited[key] for key in carried_audited if key in carried_back]
+        state["_carriedToVerify"] = (state.get("_carriedToVerify") or []) + []
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py -k "test_t2"`
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_t2_a_carried_finding_the_audit_does_not_discharge_goes_to_the_verifier_and_stays_open_when_confirmed[changed] _
...
        n, seen = _run(s, _respond(audit="not-discharged"), stop_at=RD.P_VERIFIERS)
>       assert n["action"] == RD.P_VERIFIERS and seen[:2] == [(RD.P_AUDITS, 1), (after, 1)], seen
E       AssertionError: [('dispatch-audits', 1), ('dispatch-scoped-finder', 1), ('terminal', 1)]
E       assert ('terminal' == 'dispatch-verifiers'
E         
E         - dispatch-verifiers
E         + terminal)

/home/user/wt-2266/plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py:206: AssertionError
_ test_t2_a_carried_finding_the_audit_does_not_discharge_goes_to_the_verifier_and_stays_open_when_confirmed[full] _
...
        # staged for the verifier under its stored key; not on the fix queue, not fixed
>       assert [SC.finding_identity_key(f) for f in state["_toVerify"]] == [key]
E       AssertionError: assert [] == ['rr1:6830197...4a816d12b05c']
E         
E         Right contains one more item: 'rr1:6830197dfc65d27498e74a816d12b05c'
E         Use -v to get more diff

/home/user/wt-2266/plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py:209: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py::test_t2_a_carried_finding_the_audit_does_not_discharge_goes_to_the_verifier_and_stays_open_when_confirmed[changed]
FAILED plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py::test_t2_a_carried_finding_the_audit_does_not_discharge_goes_to_the_verifier_and_stays_open_when_confirmed[full]
2 failed, 14 deselected in 4.20s
```
(`...` marks the parametrize decorator, the test's setup lines and the monkeypatch/tmp_path fixture dump, which the runner printed and this record leaves out.)

**restore:** the inverse edit (`+ []` replaced by the comprehension over `carried_audited`).

**restore receipt:** a search of `round_driver.py` for `"_carriedToVerify"\] = \(state` finds line 7156, which reads again:
```python
        state["_carriedToVerify"] = (state.get("_carriedToVerify") or []) + [carried_audited[key] for key in carried_audited if key in carried_back]
```

**raw green:** same command
```
..                                                                       [100%]
2 passed, 14 deselected in 4.47s
```
