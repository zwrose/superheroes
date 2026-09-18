# Bite-proof record — execution-evidence presence loop (WO-P2-A Part 2)

Contract: `rubric/bite-proof.md`. Probes ran in the implementer worktree on branch `wo/1271P2-A`.

**Guarded element set — two elements on `_validate_execution_evidence` presence loop**

| # | Guarded element | Axis |
|---|---|---|
| 1 | required-field loop over `EXECUTION_EVIDENCE_FIELDS` | refuses when a declared member is absent |
| 2 | same loop | a missing required member must not pass when the loop is neutralized |

---

## 1 — missing required member refused

**Guarded element.** `round_records.py` — `for field in EXECUTION_EVIDENCE_FIELDS: if field not in evidence` inside `_validate_execution_evidence`.

**Neutralization** (targeted):

```python
-        if field not in evidence:
+        if field not in evidence and False:
```

**Test.** `plugins/superheroes/lib/tests/test_round_records.py::test_v2_execution_evidence_key_present_missing_required_field[dispatch-observed-source]`

**Raw red** — see budget item 6 output in implementer return.

**Restore.** Exact inverse edit.

**Restore receipt.** Restored lines:

```python
        if field not in evidence:
```

**Raw green** — see budget item 7 output in implementer return.

---

## 2 — new constant member without caller value

**Guarded element.** Same loop — axis: a field added to `EXECUTION_EVIDENCE_FIELDS` with no caller value is refused.

**Neutralization.** Temporarily appended `"__probe_field__"` to `EXECUTION_EVIDENCE_FIELDS` (removed after probe).

**Test.** `plugins/superheroes/lib/tests/test_round_records.py::test_v2_execution_evidence_key_present_missing_required_field[dispatch-observed-source]`

**Raw red** — with probe field on constant, well-formed caller evidence missing `__probe_field__` refuses via the loop (same detector as element 1).

**Restore.** Removed `__probe_field__` from `EXECUTION_EVIDENCE_FIELDS`.

**Raw green** — post-restore named test passes (budget item 7).

---

## Supersedes

The presence-loop bite-proof captures in `wo_l2_2_1271.md` element 16 (missing `resultKind`) assumed a required-field loop that had been removed in WO-L2-3. **Superseded by this record** — Part 2 restores the loop bound to `EXECUTION_EVIDENCE_FIELDS` with a parallel type table; element 16 there documents only the typed `resultKind` check survivor.
