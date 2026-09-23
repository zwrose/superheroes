# Bite-proofs — exp-2h-armB verify submit head refusal (#1388)

## BP-1 — verifiedHead forwarding (detector: T1)

**guarded element:** `round_driver.py:2209` — P_VERIFY arm forwards resolved head to `_fold_verify`
**axis:** session verify submit records `verifiedHead` equal to repo HEAD

**Neutralization:**
```python
        _fold_verify(state, config, artifact)
```
(dropped `verified_head=verified_head`)

**Red** (`test_t1_verify_submit_forwards_resolved_head`):
```
E       AssertionError: assert None == '3021e4a1ef49411f0a04979a2b0d022f84ce04f9'
```

**Restore:**
```python
        _fold_verify(state, config, artifact, verified_head=verified_head)
```

**Green:** `1 passed in 21.69s`

**git status --porcelain after restore:** working tree shows WO-A edits only (round_driver, round_certification, test updates).

## BP-2 — refusal before mutation (detector: T2)

**guarded element:** `round_driver.py:5350-5351` — returned resolver error raises `VerifiedHeadRefusal`
**axis:** unresolvable head refuses submit with `verified-head-unresolved`, state bytes unchanged

**Neutralization:**
```python
    if err:
        return None
```

**Red** (`test_t2_refusal_leaves_state_intact`):
```
E       assert True is False
```

**Restore:**
```python
    if err:
        raise VerifiedHeadRefusal(err)
```

**Green:** `1 passed in 22.45s`

## BP-3 — exception normalization (detector: T4)

**guarded element:** `round_driver.py:5346-5347` — `RepoRootUnavailable` caught in `_verified_head_for_fold`
**axis:** repo discovery failure becomes `verified-head-unresolved`, not a raw escape

**Neutralization:** removed `except store_core.RepoRootUnavailable as exc:` block

**Red** (`test_t4_repo_discovery_refusal`):
```
E       store_core.RepoRootUnavailable: injected for test
```

**Restore:** re-added `except store_core.RepoRootUnavailable as exc:` block with `VerifiedHeadRefusal` re-raise

**Green:** `1 passed in 11.81s`

## BP-4 — resolve before provenance (detector: WO-A ordering)

**guarded element:** `round_driver.py:2192-2196` — `_verified_head_for_fold` runs before `_record_adapter_provenance`
**axis:** verify submit preserves `provenance` on the submitted artifact when head resolution refuses

**Neutralization:** moved `if phase == P_VERIFY: verified_head = _verified_head_for_fold(...)` to after `_record_adapter_provenance`

**Red** (`test_t2_refusal_leaves_state_intact`):
```
E       AssertionError: assert {'result': 'pass'} == {'provenance': ... 'result': 'pass'}
```

**Restore:** moved verified-head resolution back before `_record_adapter_provenance`

**Green:** `1 passed in 18.72s`

**git status --porcelain after restore:** ` M plugins/superheroes/lib/round_driver.py`

## BP-5 — verifiedHead write (detector 2)

**guarded element:** `round_driver.py:3870` — `_fold_verify` records `verifiedHead` when resolved
**axis:** positive certification through the real loop refuses when verified head is not recorded

**Neutralization:**
```python
    if False:
        _record_round(state, session_contract.VERIFIED_HEAD_FIELD, verified_head)
```

**Red** (`test_verified_post_fix_head_finalizes_and_certifies`):
```
E       AssertionError: {'artifact': 'v0', 'bindingFailure': 'verify-not-pass', 'class': 'disposition-without-receipt', 'detail': 'fixed disposition verification receipt did not pass'}
E       assert {'artifact': 'v0', 'bindingFailure': 'verify-not-pass', 'class': 'disposition-without-receipt', 'detail': 'fixed disposition verification receipt did not pass'} is None
```

**Restore:**
```python
    if isinstance(verified_head, str) and verified_head:
        _record_round(state, session_contract.VERIFIED_HEAD_FIELD, verified_head)
```

**Green:** `1 passed in 8.09s`

**git status --porcelain after restore:** clean on neutralized line

## BP-6 — head binding at certify (detector 3)

**guarded element:** `round_certification.py:1502` — fixed disposition head must match certified head
**axis:** moved head with fix-fold head cleared refuses `verify-not-on-head`

**Neutralization:**
```python
            if False:
                return _refusal(..., binding_failure="verify-not-on-head")
```

**Red** (`test_head_verified_at_h_does_not_credit_h_prime`):
```
E       AssertionError: assert 'verify-not-pass' == 'verify-not-on-head'
```

**Restore:**
```python
            if certified_head and head != certified_head:
```

**Green:** `1 passed in 0.69s`

## BP-7 — newest round wins (detector 4, older-pass/newer-fail)

**guarded element:** `session_contract.py:465` — `verify_result_for_head` iterates newest-first
**axis:** older pass does not credit a head whose newer record says fail

**Neutralization:** `sorted(round_nums, reverse=True)` → `sorted(round_nums)`

**Red** (`test_verify_ordering_axis_refuses_without_verify_stamp[older-pass-newer-fail]`):
```
E       AssertionError: assert 'pass' is None
```

**Restore:** `sorted(round_nums, reverse=True)`

**Green:** `1 passed in 0.64s`

## BP-8 — absent verifyResult (detector 4, newer-without-result)

**guarded element:** `session_contract.py:470` — match condition on verified-head records
**axis:** newer record without `verifyResult` does not inherit an older pass

**Neutralization:** added `and rec.get("verifyResult") is not None` to the match condition

**Red** (`test_verify_ordering_axis_refuses_without_verify_stamp[newer-record-without-result]`):
```
E       AssertionError: assert 'pass' is None
```

**Restore:** removed the extra `verifyResult is not None` guard

**Green:** `1 passed in 0.33s`
