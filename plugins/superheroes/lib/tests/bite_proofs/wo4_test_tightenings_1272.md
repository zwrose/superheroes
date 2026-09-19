# Bite-proof record — #1272 WO-4 (test tightenings)

Contract: `rubric/bite-proof.md`. Every proof below ran with the **detector unedited**; the
neutralization was applied as a targeted, reversible edit to the **production call site**, and
reverted by its exact inverse.

| # | Guarded element | Axis |
|---|---|---|
| T1 | `round_driver._advance_locked` reappend journal row | an advance-produced row missing identity is caught |
| T2 | `round_certification._observation_qualifies` cited-head compare | the certifying case certifies |
| T3 | `round_records.require_complete_revision` | the raised `missing` tuple names the field |
| T4 | `round_driver._assemble_dispatch_evidence` err branch | a non-object journal line is refused |

**Note (T1):** the order named `_sweep_record`, but the WO-4 test's `cmd == "advance"` rows are
produced by the reconcile **reappend** path in `_advance_locked` (after `sweep_landing` creates a
store without a journal entry). Neutralization targets that reappend site.

**Note (T2):** the order named `check_evidence_head_bound`, which has no cited-head equality
compare; the decisive compare lives in `_observation_qualifies`. At base (no neutralization) the
pinned receipt assertion is already red — see findings. Bite-proof red under neutralization is
recorded; green restore cannot make T2 pass at base.

---

## T1 — advance reappend row identity

**Neutralization** (`round_driver.py` `_advance_locked` reappend):

```python
-        revision_fields = round_records.recorded_row_fields(stored_envelope, cited_head)
+        revision_fields = {k: v for k, v in round_records.recorded_row_fields(
+            stored_envelope, cited_head).items() if k != "citedHead"}
```

**Raw red** — `test_real_record_paths_carry_complete_revision_identity`:

```
FAILED plugins/superheroes/lib/tests/test_recorded_row_chokepoint_1272.py::test_real_record_paths_carry_complete_revision_identity
AssertionError: {'detail': "IncompleteRevisionIdentity: incomplete revision identity: missing ('citedHead',)", 'ok': False, 'reason': 'driver-internal-exception', 'tracebackSha256': '365e8113844fa5b18f7e6a6fa63104630890c1e9bce03855ce477018cf3b384d'}
assert False
1 failed in 15.00s
```

**Restore:** restored `revision_fields = round_records.recorded_row_fields(stored_envelope, cited_head)`.

**Restore receipt (quoted lines):**

```python
        revision_fields = round_records.recorded_row_fields(stored_envelope, cited_head)
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 18.09s
```

---

## T2 — certifying case certifies (`Unprovable as placed` at base)

**Base refusal (no neutralization)** — pinned `assert refusal is None` is red before any bite-proof:

```
AssertionError: {'artifact': '...', 'bindingFailure': 'execution-evidence-not-engaged', 'class': 'unrun-review', 'detail': 'hand-landed seat lacks qualifying execution-evidence read engagement'}
```

**Neutralization** (`round_certification.py` `_observation_qualifies` — order cited
`check_evidence_head_bound` but that function has no `!=` compare):

```python
-    if cited_head and certified_head and cited_head != certified_head:
+    if cited_head and certified_head and cited_head == certified_head:
         return False, "execution-evidence-stale-head"
```

**Raw red** — `test_real_loop_dispatch_observed_row_carries_cited_head_matching_certified_head`:

```
FAILED plugins/superheroes/lib/tests/test_recorded_row_chokepoint_1272.py::test_real_loop_dispatch_observed_row_carries_cited_head_matching_certified_head
AssertionError: {'artifact': 'code-reviewer', 'bindingFailure': 'execution-evidence-stale-head', 'class': 'unrun-review', 'detail': 'dispatch-observed seat lacks qualifying execution telemetry'}
assert {'artifact': 'code-reviewer', 'bindingFailure': 'execution-evidence-stale-head', ...} is None
1 failed in 18.41s
```

**Restore:** reverted `==` to `!=`.

**Restore receipt (quoted lines):**

```python
    if cited_head and certified_head and cited_head != certified_head:
        return False, "execution-evidence-stale-head"
```

**Green half:** not runnable — base test remains red after restore (hand-landed read-engagement
refusal). Disclosure: **Unprovable as placed**.

---

## T3 — `missing` tuple names the field

**Neutralization** (`round_records.py` `require_complete_revision`):

```python
-        raise IncompleteRevisionIdentity(missing)
+        raise IncompleteRevisionIdentity(REVISION_IDENTITY_FIELDS)
```

**Raw red** — `test_recorded_row_missing_one_identity_field_refused_at_sinks[citedHead]`:

```
FAILED plugins/superheroes/lib/tests/test_recorded_row_chokepoint_1272.py::test_recorded_row_missing_one_identity_field_refused_at_sinks[citedHead]
AssertionError: assert ('payloadSha2...Present', ...) == ('citedHead',)
1 failed in 14.69s
```

**Restore:** restored `raise IncompleteRevisionIdentity(missing)`.

**Restore receipt (quoted lines):**

```python
        raise IncompleteRevisionIdentity(missing)
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 12.28s
```

---

## T4 — non-object journal line refused

**Neutralization** (`round_driver.py` `_assemble_dispatch_evidence`):

```python
-        return None, "evidence-run-dir-unreadable", {"detail": err}
+        return None, None, {}
```

**Raw red** — `test_journal_line_not_an_object_refuses_evidence_binding`:

```
FAILED plugins/superheroes/lib/tests/test_evidence_journal_shape_1272.py::test_journal_line_not_an_object_refuses_evidence_binding
AssertionError: assert None == 'evidence-run-dir-unreadable'
1 failed in 0.54s
```

**Restore:** restored the refusal return.

**Restore receipt (quoted lines):**

```python
        return None, "evidence-run-dir-unreadable", {"detail": err}
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.66s
```
