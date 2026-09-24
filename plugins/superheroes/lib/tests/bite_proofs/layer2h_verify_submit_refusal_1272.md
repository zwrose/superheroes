# Bite-proof record — #1272 layer 2h (the verify submit's recoverable head-resolution refusal)

Contract: `rubric/bite-proof.md`. Every proof below ran with the **detector unedited**; each
neutralization was a targeted, reversible edit to the guarded site made through the host's edit
action, restored by its exact inverse edit (never `git checkout`, never a whole-file rewrite), with
`git status --porcelain` **empty** (count `0`) after every restore.

**Who ran these, and where.** The layer 2h orchestrator (`launch-92ba9b590253cab5`), in a dedicated
detached probe worktree (`issue-1272-2h-probe`) cut at **`c68eed96`** — never in the build worktree,
and with no other session reading the probe tree. WO-A (`92568aa7`) and WO-B (`c68eed96`) were
committed before the first probe, so no neutralization or restore could reach uncommitted work.

Every command was run as
`/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-probe2h -m pytest <node-id> -q -p no:cacheprovider`
with output to a file, and every EXIT line is **that runner's own exit code**, not a pipe's. Every
detector was selected by its **exact node id**, never `-k`.

**The guarded invariant.** *The verify submit resolves the head before it mutates anything; a
resolution failure refuses the submit, leaves the pending verify step and `lastAccepted` intact, and
the same artifact can be resubmitted.* Plus the three detector repairs carried from layer 2g's round:
the positive fixture is faithful, the moved-head test grades the moved head, and the accessor's
ordering axes cover the unsafe direction. Seven guarded elements; **one proof per element**.

**Baseline before any neutralization** — both detector files green at `c68eed96` (EXIT=0):
`35 passed in 8.73s`. **After the last restore** — the same two files (EXIT=0): `35 passed in 7.12s`.

---

## BP-2h-a — the fold forwards the resolution

**Guarded element.** `_fold`'s `P_VERIFY` arm hands the resolution decided at the submit chokepoint
to `_fold_verify`. Layer 2g's round showed its predecessor wiring had no detector (204 tests green
with it reverted).

**Neutralization** (`plugins/superheroes/lib/round_driver.py`, `_fold`, one occurrence):
`_fold_verify(state, config, artifact, resolution=verified_head_resolution)` →
`_fold_verify(state, config, artifact)`.

**Detector.** `test_layer2h_verify_submit_refusal_1272.py::test_verify_submit_forwards_the_resolved_head_through_the_fold`
— through the real `cmd_next` + `cmd_submit` path.

**Red** (EXIT=1):

```
E           TypeError: _fold_verify() missing 1 required keyword-only argument: 'resolution'
FAILED plugins/superheroes/lib/tests/test_layer2h_verify_submit_refusal_1272.py::test_verify_submit_forwards_the_resolved_head_through_the_fold
1 failed in 0.92s
```

**Restored → green** (EXIT=0): `1 passed in 0.69s`.

## BP-2h-b — the chokepoint refuses before the fold

**Guarded element.** `cmd_submit`'s verify-phase refusal: a resolution error returns
`verified-head-unresolved` before `_fold`, so nothing is recorded or advanced.

**Neutralization** (`round_driver.py`, `cmd_submit`, one occurrence):
`if phase == P_VERIFY and resolution[1]:` → `if False and phase == P_VERIFY and resolution[1]:` —
the error then flows into the fold, which records `verifiedHeadRefused` and advances (the layer 2g
defect).

**Detectors.** `test_verify_submit_refuses_an_unresolvable_head_and_accepts_the_same_artifact_after`
(hand `submit`) and `test_verify_advance_surfaces_the_refusal_as_fold_refused_and_retries` (public
`advance`), both in `test_layer2h_verify_submit_refusal_1272.py`.

**Red** (EXIT=1):

```
>       assert answer1["ok"] is False
E       assert True is False
>       assert out1["ok"] is False
E       assert True is False
FAILED plugins/superheroes/lib/tests/test_layer2h_verify_submit_refusal_1272.py::test_verify_submit_refuses_an_unresolvable_head_and_accepts_the_same_artifact_after
FAILED plugins/superheroes/lib/tests/test_layer2h_verify_submit_refusal_1272.py::test_verify_advance_surfaces_the_refusal_as_fold_refused_and_retries
2 failed in 0.55s
```

**Restored → green** (EXIT=0): `2 passed in 0.95s`.

## BP-2h-c — a resolver `OSError` is the same refusal

**Guarded element.** The `except OSError` at the chokepoint: the reused resolver persists the head it
read to `meta.json`, and that write can raise.

**Neutralization** (`round_driver.py`, `cmd_submit`, the `except` directly under
`resolution = _verified_head_at_fold(session_dir, state)`): `except OSError as exc:` →
`except KeyError as exc:`.

**Detector.** `test_verify_submit_refuses_when_persisting_the_resolved_head_raises`.

**Red** (EXIT=1):

```
E       OSError: disk full
FAILED plugins/superheroes/lib/tests/test_layer2h_verify_submit_refusal_1272.py::test_verify_submit_refuses_when_persisting_the_resolved_head_raises
1 failed in 1.04s
```

**Restored → green** (EXIT=0): `1 passed in 0.62s`.

## BP-2h-d — the positive fixture reaches its terminal through the real chain

**Guarded element.** `_certifiable_session`'s faithfulness: its terminal state is whatever the verify
fold's own continuation produced, never a restored snapshot that predates later evidence. The guarded
thing here is the fixture itself, so the neutralization goes into the fixture and the detector
assertion (`_assert_no_evidence_postdates_terminal`, plus the positive test's own assertions) stays
unedited.

**Neutralization** (`tests/test_layer2g_terminal_finalization_1272.py`, `_certifiable_session`,
directly after `_drive_faithful_two_round_verify(...)`): insert `loaded["round"] = 1` — the restore
layer 2g's round flagged.

**Detector.** `test_layer2g_terminal_finalization_1272.py::test_verified_post_fix_head_finalizes_and_certifies`.

**Red** (EXIT=1):

```
E               AssertionError: ('2', 1, {'confirmationFollowup': {...}, ... 'scopedFinder': 'skipped-empty-surface', 'verifiedHead': '64d8b0a9…', ...})
E               assert 2 <= 1
FAILED plugins/superheroes/lib/tests/test_layer2g_terminal_finalization_1272.py::test_verified_post_fix_head_finalizes_and_certifies
1 failed in 0.79s
```

**Restored → green** (EXIT=0): `1 passed in 0.92s`.

## BP-2h-e — certification grades the moved head

**Guarded element.** The certification-side head binding in `round_certification.py`
(`if certified_head and head != certified_head:` → `binding_failure="verify-not-on-head"`). With
`fixFoldHeadSha` cleared, certification resolves the moved head H′ and must refuse a receipt bound
to H on that ground — not on the incidental `verify-not-pass` the 2g version graded.

**Neutralization** (`plugins/superheroes/lib/round_certification.py`, one occurrence): the condition
gains a leading `False and`.

**Detector.** `test_layer2g_terminal_finalization_1272.py::test_head_verified_at_h_does_not_credit_h_prime`.

**Red** (EXIT=1):

```
E       AssertionError: assert 'verify-not-pass' == 'verify-not-on-head'
E         - verify-not-on-head
E         + verify-not-pass
FAILED plugins/superheroes/lib/tests/test_layer2g_terminal_finalization_1272.py::test_head_verified_at_h_does_not_credit_h_prime
1 failed in 0.90s
```

**Restored → green** (EXIT=0): `1 passed in 0.80s`.

## BP-2h-f — the highest round decides (newer fail over older pass)

**Guarded element.** `session_contract.verify_result_for_head` reads rounds newest first.

**Neutralization** (`plugins/superheroes/lib/session_contract.py`, one occurrence):
`for rnd in sorted(round_nums, reverse=True):` → `for rnd in sorted(round_nums):`.

**Detectors.** `test_verify_result_for_head_accessor_axes[older-pass-newer-fail]` and
`test_ordering_axes_carry_through_finalization[older-pass-newer-fail]`.

**Red** (EXIT=1):

```
E       AssertionError: assert 'pass' == 'fail'
E       AssertionError: assert 'pass' != 'pass'
E        +  where 'pass' = <built-in method get of dict object ...>('verifyResult')
FAILED ...::test_verify_result_for_head_accessor_axes[older-pass-newer-fail]
FAILED ...::test_ordering_axes_carry_through_finalization[older-pass-newer-fail]
2 failed in 0.81s
```

**Restored → green** (EXIT=0): `2 passed in 0.77s`.

## BP-2h-g — a newer same-head record decides even with no result

**Guarded element.** The accessor stops at the newest record for the head whatever it carries; it
never skips past a result-less record to an older pass.

**Neutralization** (`session_contract.py`, the match condition, one occurrence): gains
`and rec.get("verifyResult") is not None`.

**Detectors.** `test_verify_result_for_head_accessor_axes[newer-record-without-result]` and
`test_ordering_axes_carry_through_finalization[newer-record-without-result]`.

**Red** (EXIT=1):

```
E       AssertionError: assert 'pass' == None
E       AssertionError: assert 'pass' != 'pass'
FAILED ...::test_verify_result_for_head_accessor_axes[newer-record-without-result]
FAILED ...::test_ordering_axes_carry_through_finalization[newer-record-without-result]
2 failed in 0.77s
```

**Restored → green** (EXIT=0): `2 passed in 0.70s`.

---

## Disclosures

- **The `ValueError` guard at the top of `_fold_verify` has no proof of its own.** A forwarded
  `None` is refused by the guard; with the guard removed, unpacking `None` raises `TypeError` at the
  same line, still before anything is recorded — so no test can tell the two apart, and the guard is
  a clearer message rather than a separately load-bearing element. The element that matters, the
  forward itself, is BP-2h-a.
- **The `run_loop` leg's explicit resolution has no new proof.** It keeps its behaviour byte-for-byte
  (the existing `test_fold_verify_without_session_dir_records_no_verified_head` and
  `test_run_loop_leg_does_not_synthesize_a_pass_receipt` cover it).
- Hex digests in the red excerpts are elided with `…`; nothing else was redacted.

---

## Adoption r3 — the advance retry proves the same artifact survives

The review of this layer found that `test_verify_advance_surfaces_the_refusal_as_fold_refused_and_retries`
wrote the verify payload a second time before the retry, so it stayed green even if the refusal had
destroyed the original. The test now captures the first payload's path and bytes, asserts both are
unchanged after the refused `advance`, and retries with no second write. Production code is
unchanged; four layer 2g tests were also renamed (bodies untouched), and none of them is a detector
on any bite-proof record.

**Who ran these, and where.** The r3 adoption orchestrator (`launch-93b781943aa4e175`), in two
dedicated detached probe worktrees cut for this purpose and read by no other session:
`issue-1272-2h-r3-probe` at **`7b93d0ba`** (the test fix, committed before the first probe) and
`issue-1272-2h-r3-probe-old` at **`8b82181d`** (the test as it stood before the fix). Same command
shape as above, pycache prefixes `/private/tmp/superheroes-pyc-r3probe` and
`…-r3probe-old`; every detector selected by exact node id; every EXIT the runner's own;
`git status --porcelain` empty after every restore in both trees. The commits after `7b93d0ba`
touch this record only, so these runs hold for the final head.

**Baseline** at `7b93d0ba`, both BP-2h-b detectors (EXIT=0): `2 passed in 0.31s`. **After the last
restore**, both detector files (EXIT=0): `35 passed in 4.99s`.

### BP-2h-b re-run — the chokepoint refuses before the fold (a detector changed)

Neutralization unchanged from BP-2h-b: `if phase == P_VERIFY and resolution[1]:` →
`if False and phase == P_VERIFY and resolution[1]:`.

**Red** (EXIT=1):

```
>       assert answer1["ok"] is False
E       assert True is False
>       assert out1["ok"] is False
E       assert True is False
FAILED plugins/superheroes/lib/tests/test_layer2h_verify_submit_refusal_1272.py::test_verify_submit_refuses_an_unresolvable_head_and_accepts_the_same_artifact_after
FAILED plugins/superheroes/lib/tests/test_layer2h_verify_submit_refusal_1272.py::test_verify_advance_surfaces_the_refusal_as_fold_refused_and_retries
2 failed in 0.20s
```

**Restored → green** (EXIT=0): `2 passed in 0.49s`.

### BP-2h-h — the refused advance leaves the artifact for the retry

**Guarded element.** The refusal returns with the verify payload untouched, so the retry folds the
same artifact rather than one written again.

**Neutralization** (`round_driver.py`, `cmd_submit`, the `verified-head-unresolved` refusal branch,
one line inserted directly after its journal append):
`os.remove(round_records.bare_payload_path(session_dir, round_no, phase, round_records.storage_key("verify"), attempt))`
— the refusal destroys the artifact it promises can be resubmitted.

**Detector.** `test_verify_advance_surfaces_the_refusal_as_fold_refused_and_retries`.

**Red at `7b93d0ba`** (EXIT=1), at the new assertion:

```
>       assert os.path.isfile(payload_path)
E       AssertionError: assert False
plugins/superheroes/lib/tests/test_layer2h_verify_submit_refusal_1272.py:297: AssertionError
FAILED plugins/superheroes/lib/tests/test_layer2h_verify_submit_refusal_1272.py::test_verify_advance_surfaces_the_refusal_as_fold_refused_and_retries
1 failed in 0.18s
```

**Restored → green** (EXIT=0): `1 passed in 0.24s`.

**The same neutralization against the test before the fix** (`8b82181d`, probe tree `…-r3probe-old`)
— EXIT=0, `1 passed in 0.24s`: the old test rewrote the payload and so could not see the loss. That
is the review finding, reproduced; restored by the inverse edit, tree clean.

Nothing was redacted in this section; the pytest temp path in the red excerpt is trimmed to the
assertion line.
