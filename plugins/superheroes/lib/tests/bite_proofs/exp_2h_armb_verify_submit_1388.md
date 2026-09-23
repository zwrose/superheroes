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
