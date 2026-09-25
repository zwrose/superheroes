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

## G5 (WO-R4) — hand-submit `_submitUsed` guard yields collection-manifest

**Guarded element.** `_audit_provenance_basis` — axis: hand-submit fold returns `collection-manifest` only when `_submitUsed` is set, even if adapter provenance names `runner-record`.

**Neutralization** (`round_driver.py`):

```python
-    if state.get("_submitUsed"):
-        return AUDIT_PROVENANCE_COLLECTION_MANIFEST
```

**Raw red** — `test_audit_provenance_basis_follows_the_fold_path` (hand-submit leg):

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_audit_provenance_basis_follows_the_fold_path _______________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-454/test_audit_provenance_basis_fo0')

    def test_audit_provenance_basis_follows_the_fold_path(tmp_path):
        """auditProvenance names the adapter-recorded seat sources, not the fold path alone."""
        session_dir, gitdir, _head_path = _drive_to_audits(tmp_path, name="durable-record")
        seat = _audit_roster(session_dir)[0]
        evidence = _execution_evidence(source="codex")
        _land_audits(session_dir, seat, payload=_audit_payload(seat),
                     provenance=round_records.PROVENANCE_HAND_LANDED, executionEvidence=evidence)
        assert RD.cmd_record_result(session_dir, seat)["ok"] is True
        pend = _pending(session_dir)
        out = RD.cmd_advance(session_dir, git=_fake_git(gitdir))
        assert out["ok"] is True, out
        state = _state(session_dir)
        assert state["rounds"][str(pend["round"])]["auditProvenance"] == "hand-landed-evidence"
    
        session_dir3 = _session(tmp_path, name="runner-record")
        state3 = _state(session_dir3)
        state3["_auditTargets"] = [{"id": seat, "identity": "unchecked index", "auditorVendor": "claude",
                                    "independence": "cross-vendor", "verdict": "blocking",
                                    "evidence": "unchecked index at src/f00.py:2"}]
        state3["auditRounds"] = []
        runner_round = state3["round"]
        RD._fold(state3, state3.get("config") or {}, RD.P_AUDITS, {
            "results": [{"id": seat, "ruling": "discharged", "reason": "r", "auditorVendor": "claude"}],
            "collectionManifest": {seat: "claude"},
            "provenance": {"provenanceSource": {seat: "runner-record"}},
        })
        assert state3["rounds"][str(runner_round)]["auditProvenance"] == "runner-record"
    
        session_dir2 = _session(tmp_path, name="hand-path")
        state2 = _state(session_dir2)
        state2["_submitUsed"] = True
        hand_target = {"id": seat, "identity": "unchecked index", "auditorVendor": "claude",
                       "independence": "cross-vendor", "verdict": "blocking",
                       "evidence": "unchecked index at src/f00.py:2"}
        state2["_auditTargets"] = [hand_target]
        state2["auditRounds"] = []
        hand_round = state2["round"]
        RD._fold_audits(state2, state2["config"], {
            "results": [],
            "collectionManifest": {seat: "claude"},
            "provenance": {"provenanceSource": {seat: "runner-record"}},
        })
>       assert state2["rounds"][str(hand_round)]["auditProvenance"] == "collection-manifest"
E       AssertionError: assert 'runner-record' == 'collection-manifest'
E         
E         - collection-manifest
E         + runner-record

plugins/superheroes/lib/tests/test_seat_provenance_1272.py:538: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_provenance_1272.py::test_audit_provenance_basis_follows_the_fold_path
1 failed in 6.14s
```

**Restore:** reinstate the `_submitUsed` guard at the top of `_audit_provenance_basis`.

**Restore receipt (quoted lines):**

```python
    if state.get("_submitUsed"):
        return AUDIT_PROVENANCE_COLLECTION_MANIFEST
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 6.61s
```

---

## G6 (WO-R3) — auditProvenance follows adapter-recorded seat sources

**Neutralization** (`round_driver.py`):

```python
-    _record_round(state, "auditProvenance", _audit_provenance_basis(state, artifact))
+    _record_round(state, "auditProvenance",
+                  AUDIT_PROVENANCE_RUNNER_RECORD
+                  if (_seat_result_schema(state) == round_records.SEAT_RESULT_SCHEMA_V2
+                      and not state.get("_submitUsed"))
+                  else AUDIT_PROVENANCE_COLLECTION_MANIFEST)
```

**Raw red** — `test_audit_provenance_basis_follows_the_fold_path` (hand-landed durable-record half):

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_audit_provenance_basis_follows_the_fold_path _______________

    def test_audit_provenance_basis_follows_the_fold_path(tmp_path):
        ...
>       assert state["rounds"][str(pend["round"])]["auditProvenance"] == "hand-landed-evidence"
E       AssertionError: assert 'runner-record' == 'hand-landed-evidence'
E         
E         - hand-landed-evidence
E         + runner-record

plugins/superheroes/lib/tests/test_seat_provenance_1272.py:414: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_provenance_1272.py::test_audit_provenance_basis_follows_the_fold_path
1 failed in 4.12s
```

**Restore:** reinstate `_record_round(state, "auditProvenance", _audit_provenance_basis(state, artifact))`.

**Restore receipt (quoted lines):**

```python
    _record_round(state, "auditProvenance", _audit_provenance_basis(state, artifact))
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 7.07s
```

---

## G7 (WO-R4) — ruling evidence digest is the whole ruling record

**Guarded element.** `_evidence_digest_subject` — axis: a ruling's evidence digest is over the whole ruling record, not the `ruling` string token.

**Neutralization** (`round_driver.py`):

```python
     if result_kind == "ruling":
         # engine_dispatch._result_kind_and_content_from_parse hashes res["ruling"], the whole scrubbed record.
-        return envelope_payload, None
+        if "ruling" not in envelope_payload:
+            return None, "evidence-result-mismatch"
+        return envelope_payload["ruling"], None
```

**Raw red** — `test_dispatch_observed_audit_seat_binds_runner_evidence_end_to_end`:

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_dispatch_observed_audit_seat_binds_runner_evidence_end_to_end ______

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-456/test_dispatch_observed_audit_s0')

    def test_dispatch_observed_audit_seat_binds_runner_evidence_end_to_end(tmp_path):
        """Positive-path dispatch-observed audits test the round-1 test seat asked for."""
        session_dir, gitdir, _head_path = _drive_to_audits(tmp_path, name="dispatch-audit-bind")
        state = _state(session_dir)
        pend = state["pending"]
        roster = _audit_roster(session_dir)
        seat = roster[0]
        order_path = round_records.order_prompt_path(
            session_dir, pend["round"], pend["phase"],
            round_records.storage_key(seat), pend["attempt"])
        assert os.path.isfile(order_path), order_path
        run_dir = _audit_execution_run_dir(tmp_path, order_path, seat)
        record, err = engine_dispatch.run_execution_record(run_dir)
        assert err is None, err
        assert record["resultKind"] == "ruling"
        journal_records, _ = engine_dispatch._journal_read(run_dir)
        run_state = engine_dispatch._journal_state(journal_records)
        parse_res = engine_dispatch._parse_review_attempt(run_dir, run_state, 1)
        assert parse_res["ok"] is True, parse_res
        ruling_payload = parse_res["ruling"]
        assert round_records.payload_sha256(ruling_payload) == record["resultDigest"]
        _TDI._dispatch_observed_land(session_dir, state, pend, seat, ruling_payload)
        out = RD.cmd_record_result(session_dir, seat, evidence_run_dir=run_dir)
>       assert out["ok"] is True, out
E       AssertionError: {'ok': False, 'payloadSha256': '137d378e05a91ef222682c55822d4c9efe3dbc6d167cbfd0d887ae0f22281e1d', 'reason': 'evidence-result-mismatch', 'resultDigest': '35960e668b7f1d6d23551afed1c6b048469b8e260d75d80a4c2bfedbefb589bf', ...}
E       assert False is True

plugins/superheroes/lib/tests/test_seat_provenance_1272.py:477: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_provenance_1272.py::test_dispatch_observed_audit_seat_binds_runner_evidence_end_to_end
1 failed in 3.71s
```

**Restore:** return the whole audit-seat payload for the `ruling` kind.

**Restore receipt (quoted lines):**

```python
    if result_kind == "ruling":
        # engine_dispatch._result_kind_and_content_from_parse hashes res["ruling"], the whole scrubbed record.
        return envelope_payload, None
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 3.58s
```

---

## Review round 5 (WO-R5)

| # | Guarded element | Axis |
|---|---|---|
| G8 | `_runner_shaped_result` contract branch | digest subject follows runner semantics |
| G9 | `_fold_audits` missing-entry prefix check | diagnostic names missing key only when key is absent |

---

## G8 (WO-R5) — digest subject follows runner semantics

**Neutralization** (`round_driver.py`):

```python
-    contract, _ = payload_contracts.payload_contract(phase)
-    required = contract.get("required") or ()
-    if len(required) > 1 and result_kind in required:
-        # The seat lands the record itself (the audits contract requires `ruling` at top level).
-        return {"ok": True, "resultKind": result_kind, result_kind: envelope_payload}
-    return {"ok": True, "resultKind": result_kind, **envelope_payload}
+    return {"ok": True, "resultKind": result_kind, **envelope_payload}
```

**Raw red** — `test_dispatch_observed_audit_seat_binds_runner_evidence_end_to_end`:

```
FAILED plugins/superheroes/lib/tests/test_seat_provenance_1272.py::test_dispatch_observed_audit_seat_binds_runner_evidence_end_to_end
AssertionError: {'ok': False, 'reason': 'evidence-result-mismatch', ...}
```

**Raw red** — `test_evidence_digest_subject_follows_runner_semantics` (ruling case):

```
FAILED plugins/superheroes/lib/tests/test_seat_provenance_1272.py::test_evidence_digest_subject_follows_runner_semantics
AssertionError: ('ruling', {'evidence': 'e', 'id': 'a1', 'ok': True, 'reason': 'ok', ...})
assert False
```

**Restore:** reinstate the `payload_contract` contract branch in `_runner_shaped_result`.

**Restore receipt (quoted lines):**

```python
    contract, _ = payload_contracts.payload_contract(phase)
    required = contract.get("required") or ()
    if len(required) > 1 and result_kind in required:
        # The seat lands the record itself (the audits contract requires `ruling` at top level).
        return {"ok": True, "resultKind": result_kind, result_kind: envelope_payload}
    return {"ok": True, "resultKind": result_kind, **envelope_payload}
```

**Raw green:**

```
..                                                                       [100%]
2 passed in 3.87s
```

---

## G9 (WO-R5) — diagnostic names missing key only when absent

**Neutralization** (`round_driver.py`):

```python
-        elif (isinstance(audit_reason, str)
-              and audit_reason.startswith(_MISSING_MANIFEST_ENTRY_REASON_PREFIX)
-              and (not isinstance(collection_manifest, dict)
-                   or pid not in collection_manifest)):
-            ...
-        elif isinstance(audit_reason, str) and audit_reason:
-            detail = "audit result for %s could not be authenticated — %s" % (pid, audit_reason)
         else:
             found_keys = ...
```

**Raw red** — `test_hand_submit_missing_manifest_key_names_expected_and_found` (empty-value case):

```
FAILED plugins/superheroes/lib/tests/test_seat_provenance_1272.py::test_hand_submit_missing_manifest_key_names_expected_and_found
assert 'no dispatch-manifest entry for this target' in "audit result for f.py::bug@L1 could not be authenticated — expected a collectionManifest entry keyed ..."
```

**Restore:** reinstate the `_MISSING_MANIFEST_ENTRY_REASON_PREFIX` branch and verbatim-reason branch.

**Restore receipt (quoted lines):**

```python
        elif (isinstance(audit_reason, str)
              and audit_reason.startswith(_MISSING_MANIFEST_ENTRY_REASON_PREFIX)
              and (not isinstance(collection_manifest, dict)
                   or pid not in collection_manifest)):
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 5.85s
```


## G10 (WO-R6) — `_assemble_dispatch_evidence` non-object payload guard

**Guarded element:** `round_driver._assemble_dispatch_evidence`, the `isinstance(envelope_payload, dict)` guard before `_runner_shaped_result`. **Axis:** a dispatch-observed envelope whose payload is not an object is refused `evidence-result-mismatch`, never raised as `TypeError`. Proof run by the WO-R6 implementer (cursor composer-2.5) with the detector unedited; captures carried here from its return.

**Red** (guard deleted):

**Rule:** Budget slot 2 / bite-proof red half.

Neutralization (deleted guard in `_assemble_dispatch_evidence`):

```python
        if not isinstance(envelope_payload, dict):
            return None, "evidence-result-mismatch", {"resultDigest": result_digest,
                                                       "resultKind": result_kind}
```

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_dispatch_observed_non_object_payload_refuses_evidence_binding ______

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-490/test_dispatch_observed_non_obj0')

    def test_dispatch_observed_non_object_payload_refuses_evidence_binding(tmp_path):
        """A dispatch-observed envelope whose payload is not a dict is refused, never raised."""
        order_path = str(tmp_path / "panel-order.txt")
        with open(order_path, "w", encoding="utf-8") as fh:
            fh.write("Review the panel findings.\n")
        panel_findings = [{"dimension": "d", "taxonomy": "t", "title": "x"}]
        run_dir = _TDI._execution_run_dir(tmp_path, order_path, panel_findings)
        record, err = engine_dispatch.run_execution_record(run_dir)
        assert err is None, err
        session_dir = str(tmp_path / "session")
        os.makedirs(session_dir, exist_ok=True)
        base_envelope = {"phase": RD.P_PANEL, "orderSha256": record["orderPromptSha256"]}
        for bad_payload in ([], "x", None):
            envelope = dict(base_envelope, payload=bad_payload)
>           assembled, refusal, extra = RD._assemble_dispatch_evidence(
                session_dir, envelope, run_dir)

plugins/superheroes/lib/tests/test_seat_provenance_1272.py:512: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
plugins/superheroes/lib/round_driver.py:7336: in _assemble_dispatch_evidence
    _runner_shaped_result(envelope.get("phase"), result_kind, envelope_payload),
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

phase = 'dispatch-panel', result_kind = 'findings', envelope_payload = []

    def _runner_shaped_result(phase, result_kind, envelope_payload):
        ...
        if declared in ("list-of-objects", "nullable-list-of-objects"):
>           return {"ok": True, "resultKind": result_kind, **envelope_payload}
E           TypeError: 'list' object is not a mapping

plugins/superheroes/lib/round_driver.py:7308: TypeError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_provenance_1272.py::test_dispatch_observed_non_object_payload_refuses_evidence_binding
1 failed in 0.45s
```

**Green** (guard restored by the inverse edit):

**Rule:** Budget slot 3 / bite-proof green half.

**Restore receipt (quoted lines):**

```python
        if not isinstance(envelope_payload, dict):
            return None, "evidence-result-mismatch", {"resultDigest": result_digest,
                                                       "resultKind": result_kind}
```

```
.                                                                        [100%]
1 passed in 0.34s
```

**Supplementary `git status --porcelain` after restore:**

```
 M plugins/superheroes/lib/round_driver.py
 M plugins/superheroes/lib/tests/test_seat_provenance_1272.py
```



## Final-head re-proof by the orchestrator (head `3ba66c30`) — supersedes the G7 and G8 entries above

The G7 (WO-R4) and G8 (WO-R5) entries above quote neutralizations of code that later rounds rewrote (`_evidence_digest_subject` was replaced by `_runner_shaped_result`, whose discriminator became the contract's declared type in WO-R5b). The review's round-6 scoped finder caught the staleness. The orchestrator re-ran both proofs on the final head in a detached probe worktree, detector unedited, neutralization applied through the host edit action and reverted by its exact inverse.

**Guarded element:** `round_driver._runner_shaped_result`, the declared-type branch (line ~7307). **Axis (G7 and G8 together):** a ruling's evidence digest is over the whole ruling record, derived through the runner's own payload semantics; a shape that wraps the ruling under its key must fail to bind.

**Neutralization** (the `if declared in ("list-of-objects", "nullable-list-of-objects"):` test replaced by `if True:` so every kind wraps).

**Raw red** — `test_dispatch_observed_audit_seat_binds_runner_evidence_end_to_end` and `test_evidence_digest_subject_follows_runner_semantics`:

```
E       AssertionError: {'ok': False, 'reason': 'evidence-result-mismatch', 'resultDigest': '35960e668b7f1d6d23551afed1c6b048469b8e260d75d80a4c2bfedbefb589bf', 'resultKind': 'ruling', ...}
E       assert False is True
E           AssertionError: ('ruling', {'evidence': 'e', 'id': 'a1', 'ok': True, 'reason': 'ok', ...})
E           assert False
2 failed in 8.04s
```

**Restore:** the inverse edit (`if declared in ("list-of-objects", "nullable-list-of-objects"):` restored). **Restore receipt:** `git status --porcelain` in the probe worktree printed nothing (0 lines).

**Raw green:**

```
2 passed in 9.14s
```

**Guarded element:** `round_driver._fold_audits`, the missing-manifest-entry branch of the `audit-provenance-fail` decision (line ~3322; G3 of WO-R2 and G9 of WO-R5, re-run together on the final head). **Axis:** the decision names the expected key and the keys found only when the entry is genuinely missing.

**Neutralization:** the `elif (isinstance(audit_reason, str) and audit_reason.startswith(_MISSING_MANIFEST_ENTRY_REASON_PREFIX) and (...))` branch replaced by `elif False:`.

**Raw red** — `test_hand_submit_missing_manifest_key_names_expected_and_found`:

```
E       AssertionError: assert 'expected a collectionManifest entry keyed' in 'audit result for f.py::bug@L1 could not be authenticated — no dispatch-manifest entry for this target — the orchestrator did not record which engine executed the audit; cannot authenticate; treated as not-discharged'
1 failed in 7.19s
```

**Restore:** the inverse edit. **Restore receipt:** `git status --porcelain` printed nothing (0 lines).

**Raw green:**

```
1 passed in 15.28s
```
