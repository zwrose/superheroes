# Bite-proof record — #1272 layer 2g, r3 re-shape (the verified-head invariant)

Contract: `rubric/bite-proof.md`. Every proof below ran with the **detector unedited**; each
neutralization was a targeted, reversible edit to the guarded production site, restored by its exact
inverse (never `git checkout`, never a whole-file rewrite), with `git status --porcelain` **empty**
after every restore.

**Who ran these, and where.** The r3 adoption orchestrator (`launch-65d83f688b1cb899`), in a
**dedicated detached probe worktree** (`issue-1272-r3-probe`) cut at the final head
**`5668bb88`** — never in the build worktree, and with no other session reading the probe tree. The
landed work was committed before the first probe (WO-A at `051ef599`, WO-B at `5668bb88`), so no
neutralization or restore could reach uncommitted work.

Every command was run as
`/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-probe -m pytest <node-id> -q`
and every EXIT line is **that runner's own exit code**, not a pipe's. Every detector was selected by
its **exact node id**, never `-k`.

**The guarded invariant.** *The fact "head H was verified, with result R" is recorded once, by
`_fold_verify`, at the moment it folds the verify result; every consumer reads that record through
one accessor; nothing reconstructs it from `verifyResult` and `fixFoldHead` found in round records.*
Four guarded elements follow — the single writer, the accessor's head match, the fail-closed
absent-field leg, and the revocation of a stale stamp. **One proof per guarded element**, not one
representative.

**Baseline before any neutralization** — the whole detector file green at `5668bb88`
(EXIT=0): `27 passed in 65.01s`.

---

## BP-2g-r3-a — the single writer

**Guarded element.** `_fold_verify` is the **only** site that records `verifiedHead`. If it stops
writing, nothing else supplies the fact.

**Neutralization** (`plugins/superheroes/lib/round_driver.py`, in `_fold_verify`; asserted
`count(old) == 1` by `grep -c 'session_contract.VERIFIED_HEAD_FIELD, verified_head'` → `1`). The
literal replaced:

```python
        _record_round(state, session_contract.VERIFIED_HEAD_FIELD, verified_head)
```

replaced by:

```python
        pass  # BP-1 NEUTRALIZATION: the single writer does not write
```

**Detector.** `test_layer2g_terminal_finalization_1272.py::test_verified_post_fix_head_finalizes_and_certifies`

**Raw red** (EXIT=1):

```
E       AssertionError: assert None
E        +  where None = <built-in method get of dict object at 0x10a3d3780>('verifiedHead')
E        +    where <built-in method get of dict object at 0x10a3d3780> = {'roundKind': 'full-panel-unknown-surface', 'verifyResult': 'pass'}.get
E        +    and   'verifiedHead' = SC.VERIFIED_HEAD_FIELD
FAILED plugins/superheroes/lib/tests/test_layer2g_terminal_finalization_1272.py::test_verified_post_fix_head_finalizes_and_certifies
1 failed in 1.11s
```

Note what the failure output shows: the round record holds `verifyResult: 'pass'` and **nothing
else** about the head — the exact shape the retired reconstruction used to read.

**Restore.** The inverse edit: `pass  # BP-1 …` → the original `_record_round(...)` line.

---

## BP-2g-r3-b — the accessor's head match

**Guarded element.** The accessor credits a result to `head` **only** when the record's
`verifiedHead` equals `head` exactly. Drop the comparison and any verified round credits any head.

**Neutralization** (`plugins/superheroes/lib/session_contract.py`, in `verify_result_for_head`;
asserted `count(old) == 1` by `grep -c 'if isinstance(verified, str) and verified and verified == head:'` → `1`).
The literal replaced:

```python
        if isinstance(verified, str) and verified and verified == head:
```

replaced by:

```python
        if isinstance(verified, str) and verified:  # BP-2 NEUTRALIZATION: head match removed
```

`git diff --stat` under the neutralization confirmed exactly one file, one line changed.

**Detector.** `test_layer2g_terminal_finalization_1272.py::test_head_verified_at_h_does_not_credit_h_prime`

**Raw red** (EXIT=1):

```
E       AssertionError: assert None == 'fixed-disposition-finalization-verify-not-pass'
E        +  where None = <built-in method get of dict object at 0x108660140>('fix@L1')
E        +    where <built-in method get of dict object at 0x108660140> = {}.get
E        +  and   'fixed-disposition-finalization-verify-not-pass' = RD.FIXED_DISPOSITION_FINALIZATION_VERIFY_NOT_PASS_CAUSE
FAILED plugins/superheroes/lib/tests/test_layer2g_terminal_finalization_1272.py::test_head_verified_at_h_does_not_credit_h_prime
1 failed in 1.31s
```

The red is in the **dangerous** direction: with the head match gone the residual set is empty —
a head verified at `H` was credited at `H'` and finalization re-bound rather than refusing. This is
the failure the detector exists for, not a cosmetic assertion.

**Restore.** The inverse edit back to the `and verified == head` form.

---

## BP-2g-r3-c — the fail-closed absent-field leg

**Guarded element.** A round record carrying `verifyResult` but **no** `verifiedHead` reads as
**not verified**. This is the leg that makes the retired reconstruction unreachable: if the accessor
ever falls back to the `verifyResult` + `fixFoldHead` pair, the whole class returns.

**Neutralization** (`plugins/superheroes/lib/session_contract.py`, in `verify_result_for_head`).
The literal replaced:

```python
        verified = rec.get(VERIFIED_HEAD_FIELD)
```

replaced by:

```python
        verified = rec.get(VERIFIED_HEAD_FIELD) or rec.get("fixFoldHead")  # BP-3 NEUTRALIZATION: absent field falls back to the retired pair
```

**Detector.** `test_layer2g_terminal_finalization_1272.py::test_round_record_lacking_verified_head_refuses`

**Raw red** (EXIT=1):

```
E       AssertionError: assert 'pass' is None
E        +  where 'pass' = <function verify_result_for_head at 0x106b0da60>({'_records': [], 'certification': {'base': 'fetched', 'fullPanel': True, 'independence': 'independent', 'shape': 'full...2040f78ff65fa18276f76add3aecea32b7b7b9'}, 'decisions': [{'detail': 'certified', 'kind': 'converged', 'round': 1}], ...}, '992040f78ff65fa18276f76add3aecea32b7b7b9')
E        +    where <function verify_result_for_head at 0x106b0da60> = SC.verify_result_for_head
FAILED plugins/superheroes/lib/tests/test_layer2g_terminal_finalization_1272.py::test_round_record_lacking_verified_head_refuses
1 failed in 0.81s
```

The neutralization is literally the reconstruction coming back, and the detector reddens on it. That
is the point of this proof: it is a standing guard against the defect class, not only against this
one bug.

**Restore.** The inverse edit back to the bare `rec.get(VERIFIED_HEAD_FIELD)`.

---

## BP-2g-r3-d — the revocation of a stale stamp

**Guarded element.** When the accessor cannot establish a `pass` for the certified head, terminal
finalization **removes** any existing `verifyResult` from the receipt — through the whole-family
writer, so `mergedInto` and the reason fields survive — before recording the residual. Without it
the residual is written to state that **nothing reads** (`_fixedDispositionFinalizationResiduals`
has exactly one occurrence in `lib/`: its write), and certification certifies on the stale stamp.

**Neutralization** (`plugins/superheroes/lib/round_driver.py`, in
`_finalize_fixed_disposition_receipts`; asserted `count(old) == 1` by
`grep -c 'revoked.pop("verifyResult", None)'` → `1`). The eleven-line revoke block was replaced by:

```python
            # BP-4 NEUTRALIZATION: the stale stamp is not revoked
            residuals[key] = FIXED_DISPOSITION_FINALIZATION_VERIFY_NOT_PASS_CAUSE
```

**Detector.** `test_layer2g_terminal_finalization_1272.py::test_stale_pass_stamp_at_certified_head_is_revoked`

**Raw red** (EXIT=1):

```
E       AssertionError: assert 'verifyResult' not in {'fixContentDigest': 'a184e2c5390d6cd4eea2ffb354e93d2145be940c7591ceb6e9e44ce6b2c80c70', 'headSha': '49e00c0078d0fd69b01f89ce39caf43cd4b0f9ff', 'verifyResult': 'pass'}
FAILED plugins/superheroes/lib/tests/test_layer2g_terminal_finalization_1272.py::test_stale_pass_stamp_at_certified_head_is_revoked
1 failed in 1.18s
```

**Restore.** The inverse edit: the eleven-line revoke block restored verbatim.

---

## Close-out

After the last restore, in the probe worktree:

- `git status --porcelain` → **empty** (no residue from any of the four neutralizations).
- The whole detector file re-run green at the final head `5668bb88` (EXIT=0): `27 passed in 7.19s`.

**Every proof was run at the final head** — `5668bb88` is the head this record's own baseline and
close-out runs were taken at, and no production or test file changed after the last restore.

**Disclosures.** None. No proof ran under a normalization, none was unavailable, and none was
substituted for by a representative.
