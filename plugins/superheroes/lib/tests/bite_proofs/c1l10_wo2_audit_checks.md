# C1-L10 (WO-2) bite-proof — the fix auditor's three checks, and the committed break-it test against the test role's

**Provenance:** implementer WO-2 / `lib/audits.py`, `lib/tests/test_c1l10_audit_checks.py`

Declared guarded elements (from the order): E1 the fold's missing-check refusal (`apply_audit_results` calling `audit_checks_fault`); E2 the `changed-unexplained` block (`apply_audit_results` testing the target's `breakIt.match`). Each was neutralized with one targeted edit and restored with the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2214` under `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -n auto --tb=line -p no:cacheprovider`. The captures are the runner's whole output for each run apart from the `UV_NATIVE_TLS` deprecation warning line and the `bringing up nodes...` lines, which are left out, and the repeated `[gwN] ... Python 3.12.13` worker lines and the repeated assertion block of each failure after its first (the 12 and 6 failures of one test function print the same assertion), which are elided and counted; nothing is redacted (no secrets, tokens or URLs appear).

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| E1 | `audits.py` `apply_audit_results`, the `checks_fault = audit_checks_fault(r, f)` call | a result missing a check, or answering one outside yes/no, or with a blank why, folds malformed and not-discharged whatever its ruling | `test_k2_a_result_missing_a_check_is_malformed_not_discharged_whatever_its_ruling` (12 cases) |
| E2 | `audits.py` `apply_audit_results`, the `if match in _BLOCKING_MATCHES:` test | a target whose committed break-it test is `missing` or `changed-unexplained` folds not-discharged, listed in `testMismatch`, whatever the result says | `test_k5_a_missing_or_unexplained_test_blocks_whatever_the_result_says` (6 cases) |

Not separately neutralized in this order, so unproven by this record: the `weakened` block, the clearing rule (`audit check failed: ...`), the submit-guard refusal, the payload-contract predicate, the strict-schema and parser tests, the `breakIt.match` computation (`_break_it_target_facts`), and the `reviewerTest` store. Their tests exist in the same file; none was reddened here.

---

## E1 — the fold refuses a result missing a check

**axis:** the fold fails closed on a result whose `checks` do not pass `audits.audit_checks_fault`.

**neutralization** (`audits.py`, `apply_audit_results`):
```python
-        checks_fault = audit_checks_fault(r, f)
+        checks_fault = None  # BITE-PROOF NEUTRALIZED: audit_checks_fault(r, f)
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -n auto --tb=line -p no:cacheprovider plugins/superheroes/lib/tests/test_c1l10_audit_checks.py::test_k2_a_result_missing_a_check_is_malformed_not_discharged_whatever_its_ruling`
```
FFFFFFFFFFFF                                                             [100%]
=================================== FAILURES ===================================
E   AssertionError: assert ([] == ['t0']
      
      Right contains one more item: 't0'
      Use -v to get more diff)
/home/user/wt-2214/plugins/superheroes/lib/tests/test_c1l10_audit_checks.py:252: AssertionError: assert ([] == ['t0']
(the same assertion block, 11 more times, one per remaining case)
=========================== short test summary info ============================
FAILED ...::test_k2_a_result_missing_a_check_is_malformed_not_discharged_whatever_its_ruling[checks1-discharged-but-new-issue]
FAILED ...::test_k2_a_result_missing_a_check_is_malformed_not_discharged_whatever_its_ruling[None-not-discharged]
FAILED ...::test_k2_a_result_missing_a_check_is_malformed_not_discharged_whatever_its_ruling[None-discharged]
FAILED ...::test_k2_a_result_missing_a_check_is_malformed_not_discharged_whatever_its_ruling[checks2-discharged]
FAILED ...::test_k2_a_result_missing_a_check_is_malformed_not_discharged_whatever_its_ruling[checks1-discharged]
FAILED ...::test_k2_a_result_missing_a_check_is_malformed_not_discharged_whatever_its_ruling[checks2-discharged-but-new-issue]
FAILED ...::test_k2_a_result_missing_a_check_is_malformed_not_discharged_whatever_its_ruling[checks1-not-discharged]
FAILED ...::test_k2_a_result_missing_a_check_is_malformed_not_discharged_whatever_its_ruling[None-discharged-but-new-issue]
FAILED ...::test_k2_a_result_missing_a_check_is_malformed_not_discharged_whatever_its_ruling[checks2-not-discharged]
FAILED ...::test_k2_a_result_missing_a_check_is_malformed_not_discharged_whatever_its_ruling[checks3-discharged-but-new-issue]
FAILED ...::test_k2_a_result_missing_a_check_is_malformed_not_discharged_whatever_its_ruling[checks3-discharged]
FAILED ...::test_k2_a_result_missing_a_check_is_malformed_not_discharged_whatever_its_ruling[checks3-not-discharged]
12 failed in 0.94s
```
(`...` stands for `plugins/superheroes/lib/tests/test_c1l10_audit_checks.py`.)

**restore:** the inverse edit — `checks_fault = audit_checks_fault(r, f)` put back.

**restore receipt:** `grep -n "checks_fault = " plugins/superheroes/lib/audits.py` printed `477:        checks_fault = audit_checks_fault(r, f)`.

**raw green:** same command.
```
............                                                             [100%]
12 passed in 14.66s
```

---

## E2 — the fold blocks a `missing` or `changed-unexplained` committed test

**axis:** a target whose committed break-it test is not the test role's version, nor the build session's explained change of it, is not discharged whatever the result says.

**neutralization** (`audits.py`, `apply_audit_results`):
```python
-        if match in _BLOCKING_MATCHES:
+        if False and match in _BLOCKING_MATCHES:  # BITE-PROOF NEUTRALIZED
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -n auto --tb=line -p no:cacheprovider plugins/superheroes/lib/tests/test_c1l10_audit_checks.py::test_k5_a_missing_or_unexplained_test_blocks_whatever_the_result_says`
```
FFFFFF                                                                   [100%]
=================================== FAILURES ===================================
E   AssertionError: assert (['t0'] == []
      
      Left contains one more item: 't0'
      Use -v to get more diff)
/home/user/wt-2214/plugins/superheroes/lib/tests/test_c1l10_audit_checks.py:389: AssertionError: assert (['t0'] == []
(the same assertion block, 3 more times; the `not-discharged` cases fail on the next assertion instead:)
E   AssertionError: assert ([] == ['t0']
      
      Right contains one more item: 't0'
      Use -v to get more diff)
/home/user/wt-2214/plugins/superheroes/lib/tests/test_c1l10_audit_checks.py:390: AssertionError: assert ([] == ['t0']
(the same assertion block, once more)
=========================== short test summary info ============================
FAILED ...::test_k5_a_missing_or_unexplained_test_blocks_whatever_the_result_says[discharged-but-new-issue-missing]
FAILED ...::test_k5_a_missing_or_unexplained_test_blocks_whatever_the_result_says[discharged-changed-unexplained]
FAILED ...::test_k5_a_missing_or_unexplained_test_blocks_whatever_the_result_says[discharged-missing]
FAILED ...::test_k5_a_missing_or_unexplained_test_blocks_whatever_the_result_says[discharged-but-new-issue-changed-unexplained]
FAILED ...::test_k5_a_missing_or_unexplained_test_blocks_whatever_the_result_says[not-discharged-changed-unexplained]
FAILED ...::test_k5_a_missing_or_unexplained_test_blocks_whatever_the_result_says[not-discharged-missing]
6 failed in 14.65s
```
(`...` stands for `plugins/superheroes/lib/tests/test_c1l10_audit_checks.py`.)

**restore:** the inverse edit — `if match in _BLOCKING_MATCHES:` put back.

**restore receipt:** `grep -n "if match in _BLOCKING_MATCHES:\|BITE-PROOF" plugins/superheroes/lib/audits.py` printed `463:        if match in _BLOCKING_MATCHES:` and no `BITE-PROOF` line; `git status --porcelain -- plugins/superheroes/lib/audits.py` printed ` M plugins/superheroes/lib/audits.py` (the file carries this order's other edits).

**raw green:** same command.
```
......                                                                   [100%]
6 passed in 0.87s
```
