# Bite-proof record — #1272 WO-1 (seat provenance derives from runner record)

Contract: `rubric/bite-proof.md`. Every proof below ran with the **detector unedited**; the
neutralization was applied as a targeted, reversible edit to the **production guarded element**, and
reverted by its exact inverse.

| # | Guarded element | Axis |
|---|---|---|
| G1 | `round_records.validate_landing` dispatch-observed branch | an audits envelope without minted evidence is refused |
| G2 | `validate_landing` hand-landed branch | a hand-landed audits envelope without evidence is refused |
| G2b | `validate_landing` source-is-a-vendor check | a source that names no vendor is refused |
| G3 | `validate_landing` legacy manifest-key branch | refusal names expected/found keys |
| G4 | `round_adapters._trusted_vendors` v2 branch | the vendor is the runner record, not the manifest |

---

## G1 — dispatch-observed without minted evidence

**Neutralization** (`round_records.py`):

```python
-                if provenance == PROVENANCE_DISPATCH_OBSERVED and not evidence_minted:
+                if provenance == PROVENANCE_DISPATCH_OBSERVED and False:
```

**Raw red** — `test_audit_seat_missing_journal_record_refuses_at_record_time`:

```
FAILED plugins/superheroes/lib/tests/test_seat_provenance_1272.py::test_audit_seat_missing_journal_record_refuses_at_record_time
AssertionError: assert 'head-anchor-mismatch' == 'provenance-underivable'
1 failed in 3.97s
```

**Raw red** — `test_advance_sweep_refuses_dispatch_observed_audits_without_minted_evidence` (E3):

```
FAILED plugins/superheroes/lib/tests/test_seat_provenance_1272.py::test_advance_sweep_refuses_dispatch_observed_audits_without_minted_evidence
AssertionError: assert (False is False and 'head-anchor-mismatch' == 'provenance-underivable')
1 failed in 4.03s
```

**Restore:** `and False` → `and not evidence_minted`.

**Restore receipt (quoted lines):**

```python
                if provenance == PROVENANCE_DISPATCH_OBSERVED and not evidence_minted:
```

**Raw green:**

```
..                                                                       [100%]
2 passed in 7.62s
```

---

## G2 — hand-landed without executionEvidence

**Neutralization** (`round_records.py`):

```python
-                if provenance == PROVENANCE_HAND_LANDED and "executionEvidence" not in envelope:
+                if provenance == PROVENANCE_HAND_LANDED and False:
```

**Raw red** — `test_hand_landed_audits_without_evidence_refuses`:

```
FAILED plugins/superheroes/lib/tests/test_seat_provenance_1272.py::test_hand_landed_audits_without_evidence_refuses
AssertionError: assert (False is False and 'head-anchor-mismatch' == 'provenance-underivable')
1 failed in 3.63s
```

**Restore:** `and False` → `and "executionEvidence" not in envelope`.

**Restore receipt (quoted lines):**

```python
                if provenance == PROVENANCE_HAND_LANDED and "executionEvidence" not in envelope:
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 3.67s
```

---

## G2b — source outside vendor registry

**Neutralization** (`round_records.py`):

```python
-                    if source not in model_registry.VENDORS:
+                    if False:
```

**Raw red** — `test_audit_source_not_in_vendor_registry_refuses`:

```
FAILED plugins/superheroes/lib/tests/test_seat_provenance_1272.py::test_audit_source_not_in_vendor_registry_refuses
AssertionError: assert (False is False and 'head-anchor-mismatch' == 'provenance-underivable')
1 failed in 3.62s
```

**Restore:** `if False:` → `if source not in model_registry.VENDORS:`.

**Restore receipt (quoted lines):**

```python
                    if source not in model_registry.VENDORS:
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 3.60s
```

---

## G3 — legacy manifest-key branch

**Neutralization** (`round_records.py`):

```python
-              and isinstance(dispatch_manifest, dict) and seat_key not in dispatch_manifest):
+              and isinstance(dispatch_manifest, dict) and False):
```

**Raw red** — `test_legacy_manifest_missing_key_refusal_names_expected_and_found`:

```
FAILED plugins/superheroes/lib/tests/test_seat_provenance_1272.py::test_legacy_manifest_missing_key_refusal_names_expected_and_found
AssertionError: assert {'envelope': ...} is None
1 failed in 1.79s
```

**Restore:** `and False` → `and seat_key not in dispatch_manifest`.

**Restore receipt (quoted lines):**

```python
              and isinstance(dispatch_manifest, dict) and seat_key not in dispatch_manifest):
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 1.92s
```

---

## G4 — v2 trusted vendor from runner record

**Neutralization** (`round_adapters.py`):

```python
             source = evidence.get("source") if isinstance(evidence, dict) else None
+            if isinstance(dispatch_manifest, dict):
+                manifest_vendor = (dispatch_manifest.get(seat) or {}).get("vendor")
+                if manifest_vendor:
+                    source = manifest_vendor
             if isinstance(source, str) and source and source in model_registry.VENDORS:
```

**Raw red** — `test_advance_derives_collection_manifest_from_runner_record`:

```
FAILED plugins/superheroes/lib/tests/test_seat_provenance_1272.py::test_advance_derives_collection_manifest_from_runner_record
AssertionError: assert {'src/f00.py:...L3': 'claude'} == {'src/f00.py:...L3': 'cursor'}
1 failed in 3.76s
```

**Restore:** removed the four-line `dispatch_manifest` override block.

**Restore receipt (quoted lines):**

```python
            source = evidence.get("source") if isinstance(evidence, dict) else None
            if isinstance(source, str) and source and source in model_registry.VENDORS:
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 3.86s
```
