# Bite-proof record — #1272 WO-1 (seat provenance derives from runner record)

Contract: `rubric/bite-proof.md`. Every proof below ran with the **detector unedited**; the
neutralization was applied as a targeted, reversible edit to the **production guarded element**, and
reverted by its exact inverse.

| # | Guarded element | Axis |
|---|---|---|
| G1 | `round_records.validate_landing` dispatch-observed branch | an audits envelope without minted evidence is refused |
| G2 | `validate_landing` hand-landed branch | a hand-landed audits envelope without evidence is refused |
| G2b | `validate_landing` source-is-a-vendor check | a source that names no vendor is refused |
| G3 (WO-R2) | `_fold_audits` `audit-provenance-fail` decision | unauthenticated decision names expected key and found keys |
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
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_audit_seat_missing_journal_record_refuses_at_record_time _________

    def test_audit_seat_missing_journal_record_refuses_at_record_time(tmp_path):
        ...
        out = RD.cmd_record_result(session_dir, seat)
>       assert out["ok"] is False
E       assert True is False

plugins/superheroes/lib/tests/test_seat_provenance_1272.py:133: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_provenance_1272.py::test_audit_seat_missing_journal_record_refuses_at_record_time
1 failed in 3.28s
```

**Restore:** `and False` → `and not evidence_minted`.

**Restore receipt (quoted lines):**

```python
                if provenance == PROVENANCE_DISPATCH_OBSERVED and not evidence_minted:
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 3.23s
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
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_hand_landed_audits_without_evidence_refuses _______________

    def test_hand_landed_audits_without_evidence_refuses(tmp_path):
        ...
        out = RD.cmd_record_result(session_dir, seat)
>       assert out["ok"] is False and out["reason"] == "provenance-underivable"
E       assert (True is False)

plugins/superheroes/lib/tests/test_seat_provenance_1272.py:177: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_provenance_1272.py::test_hand_landed_audits_without_evidence_refuses
1 failed in 3.29s
```

**Restore:** `and False` → `and "executionEvidence" not in envelope`.

**Restore receipt (quoted lines):**

```python
                if provenance == PROVENANCE_HAND_LANDED and "executionEvidence" not in envelope:
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 3.21s
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
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_audit_source_not_in_vendor_registry_refuses _______________

    def test_audit_source_not_in_vendor_registry_refuses(tmp_path):
        ...
        out = RD.cmd_record_result(session_dir, seat)
>       assert out["ok"] is False and out["reason"] == "provenance-underivable"
E       assert (True is False)

plugins/superheroes/lib/tests/test_seat_provenance_1272.py:203: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_provenance_1272.py::test_audit_source_not_in_vendor_registry_refuses
1 failed in 3.25s
```

**Restore:** `if False:` → `if source not in model_registry.VENDORS:`.

**Restore receipt (quoted lines):**

```python
                    if source not in model_registry.VENDORS:
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 3.23s
```

---

## G3 (WO-R2) — hand submit missing manifest key names expected/found

**Neutralization** (`round_driver.py`):

```python
-            detail = ("audit result for %s could not be authenticated — expected a "
-                      "collectionManifest entry keyed %r (payload.targets[].id); manifest keys "
-                      "found: %s — not-discharged"
-                      % (pid, pid, found_keys))
+            detail = ("audit result for %s could not be authenticated against the recorded dispatch "
+                      "provenance (missing entry or wrong vendor) — not-discharged" % pid)
```

**Raw red** — `test_hand_submit_missing_manifest_key_names_expected_and_found`:

```
FAILED plugins/superheroes/lib/tests/test_seat_provenance_1272.py::test_hand_submit_missing_manifest_key_names_expected_and_found
AssertionError: assert 'expected a collectionManifest entry keyed' in ...
1 failed
```

**Restore:** revert the `detail =` assignment to the expected-key/found-keys wording.

**Restore receipt (quoted lines):**

```python
            detail = ("audit result for %s could not be authenticated — expected a "
                      "collectionManifest entry keyed %r (payload.targets[].id); manifest keys "
                      "found: %s — not-discharged"
                      % (pid, pid, found_keys))
```

**Raw green:**

```
.                                                                        [100%]
1 passed
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

---

## G5 (WO-1f) — auditProvenance basis follows the fold path

**Neutralization** (`round_driver.py`):

```python
-                  if (_seat_result_schema(state) == round_records.SEAT_RESULT_SCHEMA_V2
-                      and not state.get("_submitUsed"))
+                  if (_seat_result_schema(state) == round_records.SEAT_RESULT_SCHEMA_V2)
```

**Raw red** — `test_audit_provenance_basis_follows_the_fold_path` (second half):

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_audit_provenance_basis_follows_the_fold_path _______________

    def test_audit_provenance_basis_follows_the_fold_path(tmp_path):
        ...
        RD._fold_audits(state2, state2["config"], {"results": [], "collectionManifest": {}})
>       assert state2["rounds"][str(hand_round)]["auditProvenance"] == "collection-manifest"
E       AssertionError: assert 'runner-record' == 'collection-manifest'
E         
E         - collection-manifest
E         + runner-record

plugins/superheroes/lib/tests/test_seat_provenance_1272.py:399: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_provenance_1272.py::test_audit_provenance_basis_follows_the_fold_path
1 failed in 8.43s
```

**Restore:** re-add `and not state.get("_submitUsed")` to the v2 branch condition.

**Restore receipt (quoted lines):**

```python
                  if (_seat_result_schema(state) == round_records.SEAT_RESULT_SCHEMA_V2
                      and not state.get("_submitUsed"))
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 7.05s
```
