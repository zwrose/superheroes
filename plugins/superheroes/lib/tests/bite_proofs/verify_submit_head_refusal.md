# Bite-proof record — the verify submit resolves the head before it mutates anything

Contract: `rubric/bite-proof.md`. Every proof below ran with the **detector unedited**; each
neutralization was a targeted, reversible edit (the host's edit action) to the guarded production
site, restored by its exact inverse edit — never `git checkout`, never a whole-file rewrite — with
`git status --porcelain` **empty** after every restore.

**Who ran these, and where.** The arm-C builder (Opus 5.5, orchestrator-typed), in a **dedicated
detached probe worktree** cut at **`71d64519`** (the committed implementation + tests), never in the
build worktree, with no other session reading the probe tree. Every command was
`/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-probe -m pytest <node-id> -q`,
each detector selected by its **exact node id** (never `-k`); every EXIT is that runner's own exit
code. Baseline at `71d64519`, both detector files (EXIT=0): `33 passed in 28.64s`. Absolute
scratch paths are shortened to `<probe>`; nothing else was redacted.

**Declared guarded-element set** (seven elements):

| id | guarded element | axis |
| --- | --- | --- |
| BP-a | `_fold`'s `P_VERIFY` arm forwards `verified_head` to `_fold_verify` | the submit's resolved head reaches the fold's record through the real submit path |
| BP-b | `_cmd_submit_prepare`'s `verified-head-unresolved` refusal | an unresolvable head refuses the submit — no fold, state untouched |
| BP-c1 | `_fold_verify`'s one `verifiedHead` writer | the real loop records the verified head in its own round |
| BP-c2 | `session_contract.verify_result_for_head` crediting the matching record's result | the real loop's fixed receipt certifies at the verified head |
| BP-d | certification's on-head check (`round_certification`, `verify-not-on-head`) | a receipt at H does not certify at a moved head H' |
| BP-e1 | the accessor reads the **newest** matching record first | an older pass never outranks a newer fail for the same head |
| BP-e2 | the accessor does not skip a newer matching record that has no result | an older pass never outranks a newer result-less record |
| BP-f | `_finalize_fixed_disposition_receipts` returns its residuals (r1: the state field is retired) | the re-pinned residual tests read the return channel |

(BP-c is one detector guarding two elements, so it carries two proofs.)

---

## BP-a — the wiring

**Neutralization** (`round_driver.py`, `_fold`):
`_fold_verify(state, config, artifact, verified_head=verified_head)` →
`_fold_verify(state, config, artifact)  # BP-a NEUTRALIZATION: wire cut`

**Detector.** `test_verify_submit_head_refusal.py::test_verify_submit_records_the_head_it_resolved`

**Raw red** (EXIT=1):
```
E       AssertionError: assert None == '9b6e87e4f1926e998560d68d639b955f7294fb71'
E        +  where None = <built-in method get of dict object at 0x106cb4640>('verifiedHead')
E        +    and   'verifiedHead' = session_contract.VERIFIED_HEAD_FIELD
1 failed in 16.14s
```
**Restore** by the inverse edit; porcelain `[]`. **Raw green** (EXIT=0): `1 passed in 11.93s`

## BP-b — the refusal

**Neutralization** (`round_driver.py`, `_cmd_submit_prepare`): `if head_err:` →
`if False:  # BP-b NEUTRALIZATION: never refuse`

**Detector.** `test_verify_submit_head_refusal.py::test_unresolvable_head_refuses_the_verify_submit_and_the_same_artifact_resubmits`

**Raw red** (EXIT=1) — with the refusal gone, the fold ran and the loop advanced:
```
>       assert out["ok"] is False, out
E       AssertionError: {'brokeLock': None, 'folded': {'attempt': 0, 'phase': 'run-verify', 'round': 2}, 'nextAction': {'action': 'dispatch-sc... 'ok': True, ...}, 'ok': True}
E       assert True is False
1 failed in 12.80s
```
**Restore** by the inverse edit; porcelain `[]`. **Raw green** (EXIT=0): `1 passed in 13.09s`

## BP-c1 — the real loop records the verified head

**Neutralization** (`round_driver.py`, `_fold_verify`):
`_record_round(state, session_contract.VERIFIED_HEAD_FIELD, verified_head)` →
`pass  # BP-c NEUTRALIZATION: the verified head is never recorded`

**Detector.** `test_verify_submit_head_refusal.py::test_real_loop_certifies_the_fixed_finding_at_the_verified_head`

**Raw red** (EXIT=1) — the fix fold's round exists, no round carries a verified head:
```
>       assert fix_rounds and verify_rounds and set(fix_rounds).isdisjoint(verify_rounds), state["rounds"]
E       assert (['1'] and [])
1 failed in 15.66s
```
**Restore** by the inverse edit; porcelain `[]`. **Raw green** (EXIT=0): `1 passed in 17.35s`

## BP-c2 — the real loop certifies at the verified head

**Neutralization** (`session_contract.py`, `verify_result_for_head`):
`return rec.get("verifyResult")` → `return None  # BP-c2 NEUTRALIZATION: the verified head credits no result`

**Detector.** same node id as BP-c1.

**Raw red** (EXIT=1) — the loop still reaches terminal; certification refuses the fixed receipt:
```
>       assert refusal is None, refusal
E       AssertionError: {'artifact': 'v0', 'bindingFailure': 'verify-not-pass', 'class': 'disposition-without-receipt', 'detail': 'fixed disposition verification receipt did not pass'}
1 failed in 15.89s
```
**Restore** by the inverse edit; porcelain `[]`. **Raw green** (EXIT=0): `1 passed in 16.26s`

## BP-d — the moved head

**Neutralization** (`round_certification.py`, the fixed-disposition check):
`if certified_head and head != certified_head:` → `if False:  # BP-d NEUTRALIZATION: the on-head check never fires`

**Detector.** `test_layer2g_terminal_finalization_1272.py::test_head_verified_at_h_does_not_credit_h_prime`
(re-pinned: it now clears `fixFoldHeadSha` from meta and state config after the head moves, so
certification binds to H').

**Raw red** (EXIT=1) — on the named axis, not an adjacent one:
```
>       assert refusal["bindingFailure"] == "verify-not-on-head"
E       AssertionError: assert 'verify-not-pass' == 'verify-not-on-head'
1 failed in 1.73s
```
**Restore** by the inverse edit; porcelain `[]`. **Raw green** (EXIT=0): `1 passed in 1.52s`

## BP-e1 — newest record first

**Neutralization** (`session_contract.py`, `verify_result_for_head`):
`for rnd in sorted(round_nums, reverse=True):` → `for rnd in sorted(round_nums):  # BP-e1 NEUTRALIZATION: oldest record first`

**Detector.** `test_layer2g_terminal_finalization_1272.py::test_ordering_axis_carried_through_finalization[older-pass-newer-fail]`

**Raw red** (EXIT=1) — the older pass re-stamped the receipt at finalization:
```
>       assert residuals.get(FINDING_KEY) == RD.FIXED_DISPOSITION_FINALIZATION_VERIFY_NOT_PASS_CAUSE
E       AssertionError: assert None == 'fixed-disposition-finalization-verify-not-pass'
E        +    where <built-in method get of dict object at 0x1026c7040> = {}.get
1 failed in 1.49s
```
**Restore** by the inverse edit; porcelain `[]`. **Raw green** (EXIT=0): `1 passed in 1.48s`

## BP-e2 — a result-less newer record is not skipped

**Neutralization** (`session_contract.py`, `verify_result_for_head`): the match condition gains
`and rec.get("verifyResult") is not None  # BP-e2 NEUTRALIZATION`.

**Detector.** `test_layer2g_terminal_finalization_1272.py::test_ordering_axis_carried_through_finalization[newer-record-without-a-result]`

**Raw red** (EXIT=1):
```
>       assert residuals.get(FINDING_KEY) == RD.FIXED_DISPOSITION_FINALIZATION_VERIFY_NOT_PASS_CAUSE
E       AssertionError: assert None == 'fixed-disposition-finalization-verify-not-pass'
E        +    where <built-in method get of dict object at 0x104e5a380> = {}.get
1 failed in 0.84s
```
**Restore** by the inverse edit; porcelain `[]`. **Raw green** (EXIT=0): `1 passed in 0.87s`

## BP-f — residuals are returned (r1)

**Neutralization** (`round_driver.py`, `_finalize_fixed_disposition_receipts`):
`return changed, residuals` → `return changed, {}  # BP-f NEUTRALIZATION: residuals dropped`

**Detector.** `test_layer2g_terminal_finalization_1272.py::test_fix_not_at_head_records_residual_without_rebind`
(representative of the re-pinned residual tests, which all read the same return channel through
`_finalize_certification_inputs`).

**Raw red** (EXIT=1):
```
>       assert FINDING_KEY in residuals
E       AssertionError: assert 'fix@L1' in {}
1 failed in 0.95s
```
**Restore** by the inverse edit; porcelain `[]`. **Raw green** (EXIT=0): `1 passed in 0.92s`

---

**Superseded detector.** The earlier layer's record (`layer2g_r3_verified_head_1272.md`, BP-2g-r3-a)
names `test_verified_post_fix_head_finalizes_and_certifies` as its detector. That test drove the
positive case over a restored terminal snapshot and is removed here; the single writer it guarded
is now proven by BP-c1 above, through the real loop.
