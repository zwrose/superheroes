# C13 layer 1c (#1272, WO-B) bite-proof — runner-observed cited head at record time

**Provenance:** the detectors were built by cursor composer-2.5 (WO-A at `5421ea8d`; WO-B re-pins
and records proofs). Every proof below was run in the WO-B worktree, neutralizing through a targeted
inverse-reversible edit of the quoted text and restoring by the inverse edit (never a git discard).

Command for every run:

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest -q <file>::<test>
```

## Guarded elements (C13 layer 1c, WO-A producer)

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-1c-a | `round_driver._assemble_dispatch_evidence` closed-vocabulary `runKind` branch together with the view-head presence check | unknown or absent `runKind` refuses `view-head-underivable` | `test_assemble_refuses_when_run_kind_absent` |
| BP-1c-b | `round_driver._assemble_dispatch_evidence` `view_head != anchor_cited_head` comparison | a review run whose view head disagrees with the order-bound anchor refuses `view-head-anchor-mismatch` | `test_assemble_refuses_review_when_view_head_differs_from_anchor` |

---

## BP-1c-a — `view-head-underivable`

**neutralization** (`round_driver.py`, `_assemble_dispatch_evidence`, final `else:` branch): replace
`return None, "view-head-underivable", {"runKind": run_kind}, None` with
`cited_head_source = round_records.CITED_HEAD_SOURCE_ORDER_ANCHOR`.

**raw red** (exit 1):
```
E       AssertionError: assert {'envelopeSha256': 'ba1b992a…', 'executionEvidence': {…}, …} is None
FAILED …test_cited_head_1272.py::test_assemble_refuses_when_run_kind_absent
1 failed in 0.65s
```

**restore:** inverse edit (`cited_head_source = …` → the original `return None, "view-head-underivable", …`).
**raw green:** `1 passed in 0.59s`.

## BP-1c-b — `view-head-anchor-mismatch`

**neutralization** (`round_driver.py`, `_assemble_dispatch_evidence`): replace
`if view_head != anchor_cited_head:` with `if False:`.

**raw red** (exit 1):
```
E       AssertionError: assert {'envelopeSha256': 'ba1b992a…', 'executionEvidence': {…}, …} is None
FAILED …test_cited_head_1272.py::test_assemble_refuses_review_when_view_head_differs_from_anchor
1 failed in 0.61s
```

**restore:** inverse edit (`if False:` → `if view_head != anchor_cited_head:`).
**raw green:** `1 passed in 0.61s`.

---

**Restore receipt (all elements):** after each restore, `git status --porcelain` showed only
`plugins/superheroes/lib/tests/test_round_driver_integration.py` and the new bite-proof record —
no shipped-source residue from the neutralizations.
