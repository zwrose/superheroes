# Bite-proof record — the verify submit resolves the head before it mutates anything

Contract: `rubric/bite-proof.md`. Every proof below ran with the **detector unedited**; each
neutralization was a targeted, reversible edit to the guarded production line through the edit
action, restored by its exact inverse edit (never `git checkout`, never a whole-file rewrite).
Before each neutralization the target literal was asserted unique (`grep -c` → `1`, or a unique
multi-line match), and `git diff --stat` under the neutralization showed exactly one file changed.

**Who ran these, and where.** The build orchestrator (arm D: Claude Opus 5.5, typing its own
implementation), in a **dedicated detached probe worktree** cut at **`198448ae`** — never in the
build worktree, and with no other session reading the probe tree. The landed work was committed
before the first probe (production `7b805dc3`, tests `198448ae`).

Every command was
`/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-probe -m pytest <node-id> -q -p no:cacheprovider`
run from the probe tree; every EXIT is **that runner's own exit code**, never a pipe's; every
detector was selected by its **exact node id**, never `-k`. Tracebacks confirm the probe tree's own
modules were imported (the failing frames name `…/scratchpad/probe/plugins/superheroes/lib/…`).
Captures were bounded to the decisive lines quoted here; temp-directory paths are shortened with
`…` (no secrets, tokens or private URLs appeared in any capture).

**The guarded invariant.** *A verify submit that would advance resolves the head the gate ran
against BEFORE anything mutates; an unresolvable head refuses the submit, leaves the state file,
the pending step and `lastAccepted` untouched, and the same artifact resubmits; the resolved head
travels `_cmd_submit_prepare` → `cmd_submit` → `_fold` → `_fold_verify`, and no fold records a
refusal and then advances.*

**The declared guarded-element set** — posted on the issue before review, carried here verbatim:
E1 the refusal branch · E2 its scoping to advancing results · E3 the exception boundary · E4 the
`P_VERIFY` arm's forwarding · E5 `cmd_submit`'s forwarding · E6 the single `verifiedHead` writer,
exercised through the real loop · E7 the certifier's on-head binding · E8 the accessor's
newest-first order · E9 the accessor answering from a newer result-less record · E10 no refusal
record in `_fold_verify`. **One proof per element**; no equivalence classes, no representatives.

**Baseline** — the nine detector node ids green at `198448ae` (EXIT=0): `9 passed in 136.47s`.

Detector paths below are relative to `plugins/superheroes/lib/tests/`.

---

## BP-E1 — the refusal branch

**Guarded element / axis.** `round_driver.py`, `_cmd_submit_prepare`: a verify result that would
advance with no resolvable head is **refused before anything mutates**.

**Neutralization** (`grep -c` of the literal → `1`):

```python
        if head_err and _verify_result_advances(artifact.get("result"), state["config"]):
```
→
```python
        if False and head_err and _verify_result_advances(artifact.get("result"), state["config"]):  # BP-E1 NEUTRALIZATION
```

**Detector.** `test_verify_submit_head_resolution.py::test_unresolvable_head_refuses_the_verify_submit_and_the_same_artifact_resubmits`

**Expected red, named before the run:** the submit answers `ok: True` (it folded and advanced).
**Raw red** (EXIT=1):

```
E       AssertionError: {'foldLanded': True, 'nextStep': 'terminal', 'ok': True, 'phase': 'run-verify', ...}
E       assert True is False
FAILED …/test_verify_submit_head_resolution.py::test_unresolvable_head_refuses_the_verify_submit_and_the_same_artifact_resubmits
1 failed in 17.36s
```

On-axis: with no head the fold advanced the session all the way to its terminal.
**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` → empty.
**Raw green** (EXIT=0): `1 passed in 18.22s`.

---

## BP-E2 — the refusal is scoped to results that advance

**Guarded element / axis.** The `_verify_result_advances(...)` conjunct: an honest halting result
(`fail`) with no resolvable head **still folds and halts** — it is never refused.

**Neutralization** (same unique line):

```python
        if head_err and _verify_result_advances(artifact.get("result"), state["config"]):
```
→
```python
        if head_err:  # BP-E2 NEUTRALIZATION: refusal no longer scoped to advancing results
```

**Detector.** `test_verify_submit_head_resolution.py::test_halting_verify_result_with_unresolvable_head_still_halts`

**Expected red:** the `fail` submit is refused `verified-head-unresolved`. **Raw red** (EXIT=1):

```
E       AssertionError: {'detail': "fix-fold head: git rev-parse HEAD failed in '/private/var/folders/…/test_halting_verify_result_wit0/not-a-repo'", 'ok': False, 'reason': 'verified-head-unresolved'}
E       assert False is True
FAILED …/test_verify_submit_head_resolution.py::test_halting_verify_result_with_unresolvable_head_still_halts
1 failed in 17.66s
```

**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` → empty.
**Raw green** (EXIT=0): `1 passed in 20.83s`.

---

## BP-E3 — the exception boundary

**Guarded element / axis.** `except (OSError, ValueError) as exc:` around the resolution call: a
resolver that **raises** (the fix-fold pin write) maps to the same structured refusal.

**Neutralization** (the literal occurs 5 times in the module; matched uniquely together with the
preceding `verified_head, head_err = _verified_head_at_fold(session_dir, state)` line):

```python
        except (OSError, ValueError) as exc:
```
→
```python
        except () as exc:  # BP-E3 NEUTRALIZATION: the boundary catches nothing
```

**Detector.** `test_verify_submit_head_resolution.py::test_resolver_raise_maps_to_the_structured_refusal`

**Expected red:** the injected `OSError` escapes `cmd_submit`. **Raw red** (EXIT=1):

```
E           OSError: injected meta write failure
FAILED …/test_verify_submit_head_resolution.py::test_resolver_raise_maps_to_the_structured_refusal
1 failed in 20.50s
```

**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` → empty.
**Raw green** (EXIT=0): `1 passed in 19.34s`.

---

## BP-E4 — the `P_VERIFY` arm forwards the head

**Guarded element / axis.** `_fold`'s verify arm passes `verified_head=verified_head` to
`_fold_verify`; drop it and the head `cmd_submit` resolved never reaches the record.

**Neutralization** (`grep -c` → `1`):

```python
        _fold_verify(state, config, artifact, verified_head=verified_head)
```
→
```python
        _fold_verify(state, config, artifact)  # BP-E4 NEUTRALIZATION: the arm forwards no head
```

**Detector.** `test_verify_submit_head_resolution.py::test_verify_submit_records_the_resolved_head_through_cmd_submit`

**Expected red:** the verify round records no `verifiedHead`. **Raw red** (EXIT=1):

```
E       AssertionError: assert None == '2109b450c1ef764c89edbb68467b82308520aa18'
E        +  where None = <built-in method get of dict object at 0x…>('verifiedHead')
E        +    and   'verifiedHead' = <module 'session_contract' from '…/scratchpad/probe/plugins/superheroes/lib/session_contract.py'>.VERIFIED_HEAD_FIELD
FAILED …/test_verify_submit_head_resolution.py::test_verify_submit_records_the_resolved_head_through_cmd_submit
1 failed in 17.59s
```

**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` → empty.
**Raw green** (EXIT=0): `1 passed in 16.24s`.

---

## BP-E5 — `cmd_submit` forwards the head

**Guarded element / axis.** `cmd_submit` hands `_fold` the head `_cmd_submit_prepare` resolved.

**Neutralization** (`grep -c` → `1`):

```python
                      verified_head=prep.get("verified_head"))
```
→
```python
                      verified_head=None)  # BP-E5 NEUTRALIZATION: submit drops the resolved head
```

**Detector.** Same node id as E4. **Expected red:** no `verifiedHead` recorded. **Raw red** (EXIT=1):

```
E       AssertionError: assert None == 'c26ed73bc3f5a695e40c819413cfeec4bc483cef'
E        +  where None = <built-in method get of dict object at 0x…>('verifiedHead')
FAILED …/test_verify_submit_head_resolution.py::test_verify_submit_records_the_resolved_head_through_cmd_submit
1 failed in 14.28s
```

**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` → empty.
**Raw green** (EXIT=0): `1 passed in 14.28s`.

---

## BP-E6 — the single writer, through the real loop

**Guarded element / axis.** `_fold_verify`'s one `verifiedHead` write, as reached by the positive
certification fixture — which now gets to its terminal through the real loop (fixer → audits →
verify folded by `advance` → `cmd_submit`), never a restored snapshot. With the writer silent, the
verify round the loop produced carries no verified head.

**Neutralization** (`grep -c` → `1`):

```python
        _record_round(state, session_contract.VERIFIED_HEAD_FIELD, verified_head)
```
→
```python
        pass  # BP-E6 NEUTRALIZATION: the single writer does not write
```

**Detector.** `test_layer2g_terminal_finalization_1272.py::test_verified_post_fix_head_finalizes_and_certifies`

**Expected red:** the loop's round-2 verify record lacks `verifiedHead`. **Raw red** (EXIT=1):

```
E       AssertionError: assert None == 'c0cd8f48fd5152f0254af475b6c090847ae2e8f0'
E        +  where None = <built-in method get of dict object at 0x…>('verifiedHead')
E        +    where <built-in method get of dict object at 0x…> = {'adapterProvenance': {'byPhase': {'dispatch-audits': {…}}}, 'audits': [{'auditor': 'claude', …, 'file': 'src/guard.py', ...}], ...}.get
FAILED …/test_layer2g_terminal_finalization_1272.py::test_verified_post_fix_head_finalizes_and_certifies
1 failed in 5.32s
```

The record in the failure output is the one the real loop wrote (it carries the audits step's
`adapterProvenance`) — the fixture no longer hand-folds the verify step.
**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` → empty.
**Raw green** (EXIT=0): `1 passed in 5.24s`.

---

## BP-E7 — the certifier's on-head binding

**Guarded element / axis.** `round_certification.py`, the fixed-disposition check: a receipt whose
head is not the certified head refuses **`verify-not-on-head`**. The moved-head test clears the
`fixFoldHeadSha` pin from meta and config, so the certified head really is the moved head.

**Neutralization** (`grep -n` → one site, line 1502):

```python
            if certified_head and head != certified_head:
```
→
```python
            if False and certified_head and head != certified_head:  # BP-E7 NEUTRALIZATION: no on-head binding
```

**Detector.** `test_layer2g_terminal_finalization_1272.py::test_head_verified_at_h_does_not_credit_h_prime`

**Expected red:** the refusal falls through to `verify-not-pass`. **Raw red** (EXIT=1):

```
E       AssertionError: assert 'verify-not-pass' == 'verify-not-on-head'
FAILED …/test_layer2g_terminal_finalization_1272.py::test_head_verified_at_h_does_not_credit_h_prime
1 failed in 4.97s
```

**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` → empty.
**Raw green** (EXIT=0): `1 passed in 4.39s`.

---

## BP-E8 — the accessor reads newest first

**Guarded element / axis.** `session_contract.verify_result_for_head` walks round records newest
first, so an older `pass` never outlives a newer `fail` for the same head.

**Neutralization** (`grep -n` → one site, line 465):

```python
    for rnd in sorted(round_nums, reverse=True):
```
→
```python
    for rnd in sorted(round_nums):  # BP-E8 NEUTRALIZATION: oldest record first
```

**Detector.** `test_layer2g_terminal_finalization_1272.py::test_ordering_axis_carried_through_finalization[older-pass-newer-fail]`

**Expected red:** finalization keeps the stale `pass` stamp. **Raw red** (EXIT=1):

```
E       AssertionError: assert 'verifyResult' not in {'fixContentBytes': 18, 'fixContentDigest': 'a184e2c5…', 'fixContentHeadSha': '3782719f…', 'headSha': '3782719f75c65c51ec6309d4a015ab5966d89b5e', ...}
FAILED …/test_layer2g_terminal_finalization_1272.py::test_ordering_axis_carried_through_finalization[older-pass-newer-fail]
1 failed in 4.40s
```

**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` → empty.
**Raw green** (EXIT=0): `1 passed in 3.87s`.

---

## BP-E9 — a newer result-less record decides

**Guarded element / axis.** The accessor answers from the newest record whose `verifiedHead`
matches **even when that record carries no result** — it never falls through to an older pass.

**Neutralization** (`grep -c` → `1`):

```python
        if isinstance(verified, str) and verified and verified == head:
```
→
```python
        if isinstance(verified, str) and verified and verified == head and rec.get("verifyResult") is not None:  # BP-E9 NEUTRALIZATION: result-less records skipped
```

**Detector.** `test_layer2g_terminal_finalization_1272.py::test_ordering_axis_carried_through_finalization[newer-record-without-a-result]`

**Expected red:** finalization keeps the older `pass`. **Raw red** (EXIT=1):

```
E       AssertionError: assert 'verifyResult' not in {'fixContentBytes': 18, 'fixContentDigest': 'a184e2c5…', 'fixContentHeadSha': '6eacd390…', 'headSha': '6eacd390c59f3988504a859f6ace9131cab5622e', ...}
FAILED …/test_layer2g_terminal_finalization_1272.py::test_ordering_axis_carried_through_finalization[newer-record-without-a-result]
1 failed in 3.40s
```

**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` → empty.
**Raw green** (EXIT=0): `1 passed in 3.36s`.

---

## BP-E10 — no refusal record in the fold

**Guarded element / axis.** `_fold_verify` records a head only when handed one and **never**
records a refusal — so no fold can write `verifiedHeadRefused` and then advance.

**Neutralization** (`grep -n` → one site, line 3869) — the retired write re-added as an `else`:

```python
    if isinstance(verified_head, str) and verified_head:
        _record_round(state, session_contract.VERIFIED_HEAD_FIELD, verified_head)
```
→
```python
    if isinstance(verified_head, str) and verified_head:
        _record_round(state, session_contract.VERIFIED_HEAD_FIELD, verified_head)
    else:  # BP-E10 NEUTRALIZATION: the retired refusal record comes back
        _record_round(state, "verifiedHeadRefused", "verified head: none")
```

**Detector.** `test_layer2g_terminal_finalization_1272.py::test_fold_verify_without_a_resolved_head_records_no_verified_head`

**Expected red:** the refusal record is present. **Raw red** (EXIT=1):

```
E       AssertionError: assert 'verifiedHeadRefused' not in {'verifiedHeadRefused': 'verified head: none', 'verifyResult': 'pass'}
FAILED …/test_layer2g_terminal_finalization_1272.py::test_fold_verify_without_a_resolved_head_records_no_verified_head
1 failed in 1.06s
```

**Restore.** Inverse edit (the two added lines removed). **Restore receipt:** `git status
--porcelain` → empty. **Raw green:** carried by the close-out run below, which includes this node
id (EXIT=0).

---

## Close-out

After the last restore, in the probe tree at `198448ae`:

- `git status --porcelain` → **empty** before and after the close-out run.
- Both detector files re-run green (EXIT=0):
  `test_verify_submit_head_resolution.py` + `test_layer2g_terminal_finalization_1272.py` →
  `35 passed in 68.23s`.

**Disclosures.** None. No proof ran under a normalization, none was unavailable, and none was
substituted for by a representative. E4 and E5 share one detector by design (two hops of one
chain); each has its own neutralization and its own red.
