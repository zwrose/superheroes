# #1272 layer 2e-b — followUp gate-policy bite-proofs (WO-D)

Declared guarded-element set (three elements, proven separately):

1. `validate_policy_for_write`'s allow-list leg — `if not follow_up_allowed: return "rules[%d].followUp: not allowed for disposition %r"` (D-2).
2. `judgment_follow_up_fault`'s `!= "skip"` scope operand (D-3 exclusion half).
3. `stall_follow_up_fault`'s `choice != ACCEPT_RISK_CHOICE` guard (D-4).

Production files `lib/review_gate_policy.py` and `lib/round_driver.py` are byte-identical to
pre-dispatch state after all proofs (neutralizations restored by inverse edit).

---

## Element 1 — `validate_policy_for_write` allow-list leg

**Guarded element.** `review_gate_policy.py:248`, `if not follow_up_allowed: return "rules[%d].followUp: not allowed for disposition %r"`.
**Axis.** Calibration write names the offending rule index and disposition (not the coarser `layer-follow-up-not-allowed` from `_validate_layer`).

**Neutralization.** `if not follow_up_allowed:` → `if False:`.

**Detector.** `test_layer2e_gate_policy_follow_up_1272.py::test_e4b_follow_up_on_not_allowed_disposition_refused_at_write`.

**Red** (EXIT=1):

```
......F...........................
=================================== FAILURES ===================================
________ test_e4b_follow_up_on_not_allowed_disposition_refused_at_write ________

    def test_e4b_follow_up_on_not_allowed_disposition_refused_at_write():
        ...
        refusal = RGP.validate_policy_for_write(policy_bad)
>       assert refusal is not None and "rules[0].followUp" in refusal
E       AssertionError: assert ('layer-follow-up-not-allowed' is not None and 'rules[0].followUp' in 'layer-follow-up-not-allowed')

plugins/superheroes/lib/tests/test_layer2e_gate_policy_follow_up_1272.py:335: AssertionError
1 failed, 33 passed in 7.22s
```

**Restore.** `if False:` → `if not follow_up_allowed:`.
**Restore receipt.** `git status --porcelain plugins/superheroes/lib/review_gate_policy.py` → empty.

**Green** (EXIT=0):

```
..................................
34 passed in 6.95s
```

---

## Element 2 — `judgment_follow_up_fault` skip scope operand

**Guarded element.** `round_driver.py:7202`, `if not isinstance(disp, dict) or disp.get("disposition") != "skip": continue`.
**Axis.** Only skip dispositions have `followUp` graded; non-skip stray `followUp` is ignored.

**Neutralization.** Removed `or disp.get("disposition") != "skip"` from the guard (skip scope test deleted).

**Detector.** `test_layer2e_follow_up_1272.py::test_e6_judgment_fix_stray_follow_up_not_checked` (fixture fixed: non-skip disposition now carries `reason` so reasonless-skip `continue` cannot mask the scope test).

**Red** (EXIT=1):

```
...........................F......
=================================== FAILURES ===================================
_______________ test_e6_judgment_fix_stray_follow_up_not_checked _______________

    def test_e6_judgment_fix_stray_follow_up_not_checked(tmp_path):
        ...
        out = _pending_submit(session_dir, artifact)
>       assert out["ok"] is True, out
E       AssertionError: {'ok': False, 'reason': 'follow-up-malformed: f.py::widen the api@L1: out-of-scope follow-up lacks revisit trigger'}
E       assert False is True

plugins/superheroes/lib/tests/test_layer2e_follow_up_1272.py:299: AssertionError
1 failed, 33 passed in 6.68s
```

**Restore.** Reinserted `or disp.get("disposition") != "skip"` in the guard.
**Restore receipt.** `git status --porcelain plugins/superheroes/lib/round_driver.py` → empty.

**Green** (EXIT=0):

```
..................................
34 passed in 6.95s
```

---

## Element 3 — `stall_follow_up_fault` choice guard

**Guarded element.** `round_driver.py:7222`, `if artifact.get("choice") != ACCEPT_RISK_CHOICE: return None`.
**Axis.** Only `accept-the-disclosed-risk` has `followUp` graded; hold choice stray `followUp` is ignored.

**Neutralization.** `if artifact.get("choice") != ACCEPT_RISK_CHOICE:` → `if False:`.

**Detector.** `test_layer2e_follow_up_1272.py::test_e8_stall_hold_with_follow_up_not_checked` (fixture fixed: hold carries malformed `followUp` missing `revisitTrigger`).

**Red** (EXIT=1):

```
.............................F....
=================================== FAILURES ===================================
________________ test_e8_stall_hold_with_follow_up_not_checked _________________

    def test_e8_stall_hold_with_follow_up_not_checked(tmp_path):
        ...
        out = _pending_submit(session_dir, artifact)
>       assert out["ok"] is True, out
E       AssertionError: {'ok': False, 'reason': 'follow-up-malformed: stall: out-of-scope follow-up lacks revisit trigger'}
E       assert False is True

plugins/superheroes/lib/tests/test_layer2e_follow_up_1272.py:321: AssertionError
1 failed, 33 passed in 7.06s
```

**Restore.** `if False:` → `if artifact.get("choice") != ACCEPT_RISK_CHOICE:`.
**Restore receipt.** `git status --porcelain plugins/superheroes/lib/round_driver.py` → empty.

**Green** (EXIT=0):

```
..................................
34 passed in 6.95s
```
