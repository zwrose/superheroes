# Bite-proof record — WO-A12-A / WO-A12-B (the two disposition-class guards in `check_disposition_without_receipt`)

Contract: `rubric/bite-proof.md`. Every proof below ran with the **detector unedited** — the
neutralization is a targeted, reversible one-line edit to the *guarded* code in
`round_certification.py`, reverted by exact inverse before each green half, with `git status`
confirming an empty tree between proofs. All four halves were run by the build orchestrator on head
`0d0fc1dd`, in a detached pinned worktree with no live readers.

Why this record exists: before WO-A12-A, `check_disposition_without_receipt` refused a
no-disposition finding at **two** places — the explicit `disposition is None` refusal and the
closed-set `else:` fall-through at the bottom of the chain. Neutralizing either one left the other
still refusing, so the seam test that was supposed to pin the line was **vacuous**: it asserted only
`class` and `artifact`, which both refusals share. Found at vet 227; the shape below is what the
build landed.

## Detector 1 — `test_real_loop_with_finding_refuses_disposition_without_receipt_until_loop_records_dispositions`

**Guarded element.** `plugins/superheroes/lib/round_certification.py`, the
`if disposition is None:` refusal in `check_disposition_without_receipt`.
**Axis.** A finding carried to certification with no disposition recorded must be refused *by that
guard*, with that guard's own detail — not absorbed by a downstream catch-all.

**Neutralization.** `if disposition is None:` → `if False:` (that line only).

**Raw red** — the C13 seam test, `PYTEST_EXIT=1`:

```
        receipt, refusal = round_certification.certify(session_dir)
        assert receipt is None
        assert refusal is not None
        assert refusal["class"] == "disposition-without-receipt"
        assert refusal["artifact"] == finding["title"]
>       assert refusal["detail"] == "finding has no disposition recorded"
E       AssertionError: assert 'unknown disposition None' == 'finding has ...tion recorded'
E         
E         - finding has no disposition recorded
E         + unknown disposition None

plugins/superheroes/lib/tests/test_round_driver_integration.py:991: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver_integration.py::test_real_loop_with_finding_refuses_disposition_without_receipt_until_loop_records_dispositions
1 failed, 19 deselected in 12.68s
```

The red output is itself the evidence for *why the sharpening was needed*: with the named guard gone,
a refusal still comes back with the same `class` and the same `artifact` — only the `detail`
separates them. The pre-WO-A12-A assertions could not tell those two worlds apart.

**Restore.** `if False:` → `if disposition is None:`; `git status --porcelain` empty.

**Raw green** — `PYTEST_EXIT=0`:

```
....................                                                     [100%]
20 passed in 122.87s (0:02:02)
```

## Detector 2 — `test_check_disposition_without_receipt_missing_disposition_refuses`

**Guarded element.** The same `if disposition is None:` refusal, pinned at unit level.
**Axis.** As detector 1, without the full loop's cost.

**Neutralization.** `if disposition is None:` → `if False:`.

**Raw red** — `PYTEST_EXIT=1`:

```
>       assert refusal["detail"] == "finding has no disposition recorded"
E       AssertionError: assert 'unknown disposition None' == 'finding has ...tion recorded'
E         
E         - finding has no disposition recorded
E         + unknown disposition None

plugins/superheroes/lib/tests/test_round_certification.py:870: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_certification.py::test_check_disposition_without_receipt_missing_disposition_refuses
1 failed, 112 deselected in 0.28s
```

**Restore.** Inverse edit; `git status --porcelain` empty.

**Raw green** — the certification modules run raw, `PYTEST_EXIT=0`:

```
........................................................................ [ 54%]
............................................................             [100%]
132 passed in 1.48s
```

## Detector 3 — `test_check_disposition_without_receipt_unknown_disposition_refuses`

**Guarded element.** `plugins/superheroes/lib/round_certification.py`, the closed-set guard
`if disposition not in ("fixed", "refuted", "out-of-scope"):` — the replacement for the removed
`else:` fall-through.
**Axis.** A disposition value outside the closed set must refuse rather than fall through to
`ctx["important_disclosures"] = disclosures` and a `None` return, which certifies.

**Neutralization.** `if disposition not in ("fixed", "refuted", "out-of-scope"):` → `if False:`.

**Raw red** — `PYTEST_EXIT=1`:

```
        ctx, _ = RC._load_context(session_dir)
        refusal = RC.check_disposition_without_receipt(ctx)
>       assert refusal["class"] == "disposition-without-receipt"
E       TypeError: 'NoneType' object is not subscriptable

plugins/superheroes/lib/tests/test_round_certification.py:849: TypeError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_certification.py::test_check_disposition_without_receipt_unknown_disposition_refuses
1 failed, 112 deselected in 0.28s
```

`refusal` is `None`: with that guard neutralized the check **returns clean** on an unknown
disposition. This is the fall-open the guard exists to close, and it is the reason the removed
`else:` arm was replaced rather than simply deleted — a point the vet order left to the builder and
which is disclosed as a design fork in the PR body.

**Restore.** Inverse edit; `git diff --stat` empty.

**Raw green** — `PYTEST_EXIT=0`:

```
..                                                                       [100%]
2 passed, 111 deselected in 0.23s
```

## Fail-closed edge measurement (orchestrator's own, beside the proofs)

`check_disposition_without_receipt` exercised directly at head `0d0fc1dd` over the three edges the
work orders enumerated:

```
disposition absent (None)                  -> refused class=disposition-without-receipt artifact=f-edge detail=finding has no disposition recorded
disposition explicitly None                -> refused class=disposition-without-receipt artifact=f-edge detail=finding has no disposition recorded
disposition "maybe" (outside closed set)   -> refused class=disposition-without-receipt artifact=f-edge detail=unknown disposition 'maybe'
```

No edge falls open. `"fixed"`, `"refuted"` and `"out-of-scope"` continue into their own arms
unchanged, which the eight pre-existing `check_disposition_without_receipt` tests cover.

## Not vacuous, by the four tests in `rubric/bite-proof.md`

- The detector was **unedited** in every red half; only guarded code moved.
- Each red half names a **distinct guarded element**: detectors 1 and 2 pin the `None` guard,
  detector 3 pins the closed-set guard. One representative was not stretched to cover both.
- No red half was produced by a **broken import or a collection error** — each failure is the
  intended assertion (or, for detector 3, the `None` return the assertion dereferences).
- The green halves ran under **no normalization** — same interpreter, same pycache prefix, same
  worktree, immediately after the inverse edit with a verified-empty tree.
