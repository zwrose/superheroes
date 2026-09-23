# Bite-proof record — the verify submit resolves the head before it mutates anything

Contract: `rubric/bite-proof.md`. Every proof below ran with the **detector unedited**; each
neutralization was a targeted, reversible edit (the host's edit action) to the guarded production
site, restored by its exact inverse edit — never `git checkout`, never a whole-file rewrite — with
`git status --porcelain` **empty** after every restore.

**Who ran these, and where.** The arm-C builder (Opus 5.5, orchestrator-typed), in a **dedicated
detached probe worktree** never read by a live seat. Two passes: first at `71d64519` (the typed
implementation), then — because the review's fix round changed the guarded submit site — **every
proof re-run at the final code head `8d83783a`** (the review fix commit), plus three proofs for the
detectors that fix round added. **The receipts below are the `8d83783a` runs.** Every command was
`/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-probe -m pytest <node-id> -q`,
each detector selected by its **exact node id** (never `-k`); every EXIT is that runner's own exit
code. Object addresses and long dict reprs in the raw output are elided with `...`; nothing else
was redacted.

**Declared guarded-element set** (eleven elements, twelve proofs):

| id | guarded element | axis |
| --- | --- | --- |
| BP-a | `_fold`'s `P_VERIFY` arm forwards `verified_head` to `_fold_verify` | the submit's resolved head reaches the fold's record through the real submit path |
| BP-b | `_cmd_submit_prepare`'s `verified-head-unresolved` refusal of a pass | an unresolvable head refuses a pass — no fold, state untouched |
| BP-c1 | `_fold_verify`'s one `verifiedHead` writer | the real loop records the verified head in its own round |
| BP-c2 | `session_contract.verify_result_for_head` crediting the matching record's result | the real loop's fixed receipt certifies at the verified head |
| BP-d | certification's on-head check (`round_certification`, `verify-not-on-head`) | a receipt at H does not certify at a moved head H' |
| BP-e1 | the accessor reads the **newest** matching record first | an older pass never outranks a newer fail for the same head |
| BP-e2 | the accessor does not skip a newer matching record that has no result | an older pass never outranks a newer result-less record |
| BP-f | `_finalize_fixed_disposition_receipts` returns its residuals (r1: the state field is retired) | the re-pinned residual tests read the return channel |
| BP-g | the refusal is conditioned on `result == "pass"` (review fix, finding v0) | a fail / timeout / skip folds its own outcome when the head cannot resolve — three params, three proofs |
| BP-h | the submit resolves the head through the fixer-fold resolver, not the session-setup head (review fix, finding v3) | the recorded head is the moved head, never meta `headSha` |
| BP-i | the refusal token's literal (review fix, finding v2) | the external contract string is pinned, not only its symbol |

BP-g counts as one element with three proofs (one per parametrized result token).

---

## BP-a — the wiring

**Neutralization** (`round_driver.py`, `_fold`):
`_fold_verify(state, config, artifact, verified_head=verified_head)` →
`_fold_verify(state, config, artifact)  # BP-a NEUTRALIZATION: wire cut`

**Detector.** `test_verify_submit_head_refusal.py::test_verify_submit_records_the_head_it_resolved`

**Raw red** (EXIT=1):
```
>       assert rec.get(session_contract.VERIFIED_HEAD_FIELD) == moved_head
E       AssertionError: assert None == 'ec5ee1eb6902216c50f9c9caa0e2f4b2e383bad1'
E        +  where None = <built-in method get of dict object at ...>('verifiedHead')
1 failed in 29.58s
```
**Restore** by the inverse edit; porcelain `[]`. **Raw green** (EXIT=0): `1 passed in 12.07s`

## BP-b — the refusal of a pass

**Neutralization** (`round_driver.py`, `_cmd_submit_prepare`):
`if head_err and artifact.get("result") == "pass":` → `if False:  # BP-b NEUTRALIZATION: never refuse`

**Detector.** `test_verify_submit_head_refusal.py::test_unresolvable_head_refuses_the_verify_submit_and_the_same_artifact_resubmits`

**Raw red** (EXIT=1) — with the refusal gone, the fold ran and the loop advanced:
```
>       assert out["ok"] is False, out
E       AssertionError: {'brokeLock': None, 'folded': {'attempt': 0, 'phase': 'run-verify', 'round': 2}, 'nextAction': {'action': 'dispatch-sc... 'ok': True, ...}, 'ok': True}
E       assert True is False
1 failed in 13.24s
```
**Restore** by the inverse edit; porcelain `[]`. **Raw green** (EXIT=0): `1 passed in 14.90s`

## BP-c1 — the real loop records the verified head

**Neutralization** (`round_driver.py`, `_fold_verify`):
`_record_round(state, session_contract.VERIFIED_HEAD_FIELD, verified_head)` →
`pass  # BP-c NEUTRALIZATION: the verified head is never recorded`

**Detector.** `test_verify_submit_head_refusal.py::test_real_loop_certifies_the_fixed_finding_at_the_verified_head`

**Raw red** (EXIT=1) — the fix fold's round exists, no round carries a verified head:
```
>       assert fix_rounds and verify_rounds and set(fix_rounds).isdisjoint(verify_rounds), state["rounds"]
E       assert (['1'] and [])
1 failed in 26.34s
```
**Restore** by the inverse edit; porcelain `[]`. **Raw green** (EXIT=0): `1 passed in 25.30s`

## BP-c2 — the real loop certifies at the verified head

**Neutralization** (`session_contract.py`, `verify_result_for_head`):
`return rec.get("verifyResult")` → `return None  # BP-c2 NEUTRALIZATION: the verified head credits no result`

**Detector.** same node id as BP-c1.

**Raw red** (EXIT=1) — the loop still reaches terminal; certification refuses the fixed receipt:
```
>       assert refusal is None, refusal
E       AssertionError: {'artifact': 'v0', 'bindingFailure': 'verify-not-pass', 'class': 'disposition-without-receipt', 'detail': 'fixed disposition verification receipt did not pass'}
1 failed in 25.32s
```
**Restore** by the inverse edit; porcelain `[]`. **Raw green** (EXIT=0): `1 passed in 20.99s`

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
1 failed in 2.75s
```
**Restore** by the inverse edit; porcelain `[]`. **Raw green** (EXIT=0): `1 passed in 2.58s`

## BP-e1 — newest record first

**Neutralization** (`session_contract.py`, `verify_result_for_head`):
`for rnd in sorted(round_nums, reverse=True):` → `for rnd in sorted(round_nums):  # BP-e1 NEUTRALIZATION: oldest record first`

**Detector.** `test_layer2g_terminal_finalization_1272.py::test_ordering_axis_carried_through_finalization[older-pass-newer-fail]`

**Raw red** (EXIT=1) — the older pass re-stamped the receipt at finalization:
```
>       assert residuals.get(FINDING_KEY) == RD.FIXED_DISPOSITION_FINALIZATION_VERIFY_NOT_PASS_CAUSE
E       AssertionError: assert None == 'fixed-disposition-finalization-verify-not-pass'
E        +    where <built-in method get of dict object at ...> = {}.get
1 failed in 1.94s
```
**Restore** by the inverse edit; porcelain `[]`. **Raw green** (EXIT=0): `1 passed in 1.97s`

## BP-e2 — a result-less newer record is not skipped

**Neutralization** (`session_contract.py`, `verify_result_for_head`): the match condition gains
`and rec.get("verifyResult") is not None  # BP-e2 NEUTRALIZATION`.

**Detector.** `test_layer2g_terminal_finalization_1272.py::test_ordering_axis_carried_through_finalization[newer-record-without-a-result]`

**Raw red** (EXIT=1):
```
>       assert residuals.get(FINDING_KEY) == RD.FIXED_DISPOSITION_FINALIZATION_VERIFY_NOT_PASS_CAUSE
E       AssertionError: assert None == 'fixed-disposition-finalization-verify-not-pass'
E        +    where <built-in method get of dict object at ...> = {}.get
1 failed in 2.30s
```
**Restore** by the inverse edit; porcelain `[]`. **Raw green** (EXIT=0): `1 passed in 1.60s`

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
1 failed in 1.63s
```
**Restore** by the inverse edit; porcelain `[]`. **Raw green** (EXIT=0): `1 passed in 1.34s`

## BP-g — only a pass needs a head (three proofs)

**Neutralization** (`round_driver.py`, `_cmd_submit_prepare`):
`if head_err and artifact.get("result") == "pass":` → `if head_err:  # BP-g NEUTRALIZATION: every result refused`

**Detector.** `test_verify_submit_head_refusal.py::test_unresolvable_head_never_blocks_a_result_that_credits_no_head[<p>]`
for `<p>` in `fail`, `timeout`, `skipped-no-command`.

**Raw red** (EXIT=1, each of the three; identical lines):
```
>       assert out["ok"] is True, out
E       AssertionError: {'detail': 'verified-head-unresolved', 'ok': False, 'reason': 'fold-refused'}
E       assert False is True
1 failed in 16.99s   [fail]
1 failed in 20.36s   [timeout]
1 failed in 35.03s   [skipped-no-command]
```
**Restore** by the inverse edit; porcelain `[]`. **Raw green** (EXIT=0): `1 passed in 35.18s`
[fail], `1 passed in 39.60s` [timeout], `1 passed in 39.66s` [skipped-no-command].

## BP-h — the resolved head, never the session-setup head

**Neutralization** (`round_driver.py`, `_cmd_submit_prepare`):
`verified_head, head_err = _resolve_fix_fold_head_sha(session_dir, state)` →
`verified_head, head_err = (_session_meta(session_dir).get("headSha"), None)  # BP-h NEUTRALIZATION: session-setup head`

**Detector.** `test_verify_submit_head_refusal.py::test_verify_submit_records_the_head_it_resolved`

**Raw red** (EXIT=1) — the setup head was stamped instead of the moved head:
```
>       assert rec.get(session_contract.VERIFIED_HEAD_FIELD) == moved_head
E       AssertionError: assert '2f712d6e6f36...57a6e7f516670' == 'd0199b52d79b...fcbc25ae81017'
1 failed in 23.93s
```
**Restore** by the inverse edit; porcelain `[]`. **Raw green** (EXIT=0): `1 passed in 23.59s`

## BP-i — the refusal literal

**Neutralization** (`round_driver.py`, the constant):
`VERIFIED_HEAD_UNRESOLVED = "verified-head-unresolved"` →
`VERIFIED_HEAD_UNRESOLVED = "verified-head-unresolvable"  # BP-i NEUTRALIZATION: literal drift`

**Detector.** `test_verify_submit_head_refusal.py::test_unresolvable_head_refuses_the_verify_submit_and_the_same_artifact_resubmits`

**Raw red** (EXIT=1) — the literal pin, not the symbol, caught the drift:
```
>       assert out["detail"] == "verified-head-unresolved", out
E       AssertionError: {'detail': 'verified-head-unresolvable', 'ok': False, 'reason': 'fold-refused'}
E       assert 'verified-head-unresolvable' == 'verified-head-unresolved'
1 failed in 21.19s
```
**Restore** by the inverse edit; porcelain `[]`. **Raw green** (EXIT=0): `1 passed in 26.68s`

---

**Superseded detector.** The earlier layer's record (`layer2g_r3_verified_head_1272.md`, BP-2g-r3-a)
names `test_verified_post_fix_head_finalizes_and_certifies` as its detector. That test drove the
positive case over a restored terminal snapshot and is removed here; the single writer it guarded
is now proven by BP-c1 above, through the real loop.

**Not proven here (and why).** The open review finding — the head recorded at submit can differ
from the head the gate actually ran against if HEAD moves in between — has no detector in this
change, because it is not fixed here; it is parked for an owner decision (see the PR).
