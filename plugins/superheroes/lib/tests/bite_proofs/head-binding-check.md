# Bite-proof record — #1271 `check_evidence_head_bound` (D28)

Contract: `rubric/bite-proof.md`. Both proofs ran with the **detector unedited** — the
neutralization was a targeted, reversible edit to the guard clause under proof, reverted by its
exact inverse before the green half. Run at the child's final head `ad75c4af` in a **clean detached
pinned worktree** (`/private/tmp/wh1271a13-bp`), never in a tree any live seat was reading.

**Guarded-element set — two independently neutralizable elements.** The check has two refusal legs
and each is proven separately; no representative stands for the other.

---

## 1 — the unresolvable certified head

**Guarded element.** `round_certification.py:1310` — `if not certified_head:` in
`check_evidence_head_bound`.
**Axis.** *Refusal on an unresolvable session head.* A session whose certified head cannot be
resolved must refuse `unrun-review` with binding failure `certified-head-unresolvable`; it must not
no-op both head legs and certify.

**Neutralization** (the leg short-circuited; the refusal body left untouched):

```python
     certified_head = _certified_head_sha(ctx)
-    if not certified_head:
+    if False and not certified_head:
```

**Test.** `plugins/superheroes/lib/tests/test_round_certification.py::test_check_evidence_head_bound_unresolvable_certified_head_refuses`.

**Raw red** — `1 failed` with the detector unedited:

```
        ctx, _ = RC._load_context(session_dir)
        refusal = RC.check_evidence_head_bound(ctx)
>       assert refusal is not None
E       assert None is not None

plugins/superheroes/lib/tests/test_round_certification.py:423: AssertionError
=========================== short test summary item ============================
FAILED plugins/superheroes/lib/tests/test_round_certification.py::test_check_evidence_head_bound_unresolvable_certified_head_refuses
1 failed in 0.21s
```

The red is on the claimed axis: the refusal that vanished is the head-resolution one, at the
assertion that a refusal exists at all.

**Restore.** The exact inverse edit — `if False and not certified_head:` back to
`if not certified_head:`.

**Restore receipt.** `git status --porcelain plugins/superheroes/lib/round_certification.py` →
**empty** (no residue).

**Raw green** — after restore:

```
.                                                                        [100%]
1 passed in 0.18s
```

---

## 2 — the dispatch-observed seat with no cited head

**Guarded element.** `round_certification.py:1325` — `if cited_head: continue` in
`check_evidence_head_bound`'s seat walk.
**Axis.** *Refusal on an absent cited head, not merely on a stale one.* A dispatch-observed seat row
citing no head is not a qualifying result and must refuse `unrun-review` with binding failure
`execution-evidence-head-unbound`, naming the seat; the staleness comparison it would otherwise fall
through to can only compare a head that is present, so an absent one is no check at all.

**Neutralization** (every seat skipped, so the refusal below is unreachable):

```python
     cited_head = seat_entry.get("citedHead")
-    if cited_head:
+    if cited_head or True:
         continue
```

**Test.** `plugins/superheroes/lib/tests/test_round_certification.py::test_check_evidence_head_bound_absent_cited_head_refuses`.

**Raw red** — `1 failed` with the detector unedited:

```
        ctx, _ = RC._load_context(session_dir)
        refusal = RC.check_evidence_head_bound(ctx)
>       assert refusal is not None
E       assert None is not None

plugins/superheroes/lib/tests/test_round_certification.py:399: AssertionError
=========================== short test summary item ============================
FAILED plugins/superheroes/lib/tests/test_round_certification.py::test_check_evidence_head_bound_absent_cited_head_refuses
1 failed in 0.20s
```

The fixture reaches the leg through the real path: its journal row is built with
`_dispatch_journal_with_binding(head_sha=None)`, so the seat is dispatch-observed and its
`citedHead` is genuinely absent — the condition the assertion discriminates on.

**Restore.** The exact inverse edit — `if cited_head or True:` back to `if cited_head:`.

**Restore receipt.** `git status --porcelain` over the whole worktree → **empty** (no residue
anywhere, not only on the neutralized path).

**Raw green** — both legs after restore:

```
..                                                                       [100%]
2 passed, 109 deselected in 0.17s
```

---

**Redaction.** Nothing in these captures was redacted; they carry no secrets, tokens, private URLs
or PII. Capture volume is far under the per-element and per-record ceilings.
