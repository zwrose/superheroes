# C13 layer 2a (#1272, PR #1330) bite-proof — finding identity and the leaf homes

**Provenance:** the detectors were built by cursor composer-2.5 (WO-1, WO-3 at `442b4dc0`; WO-R1
`3a5fde4a`, WO-R2 `b3ec5fc5`, WO-R3 `9f8c7823`, WO-R4 `6dec1c13`, all via `dispatch-write`). Every
proof below was **re-run by the orchestrator** (launch-0bd2aba7628b34bf, 2026-09-19) on the final
head `6dec1c13` in a detached probe worktree (`issue-1272-2a-verify`), neutralizing through the host
edit action and restoring by the inverse edit; the restore receipt for every element is an empty
`git status --porcelain` over the probe tree (quoted once at the end — it was empty after every
restore). Command for every run (node ids per element):

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-bp-0bd2 -m pytest <node ids> -q -p no:cacheprovider
```

Baseline before any probe: the seven files under proof, `250 passed in 63.23s`.

## Guarded elements (declared in the layer-2a brief, comment 5741176759, plus WO-R4's order)

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-2a-A | `session_contract.evidence_digest_subject` review-list arm | the writer's leaf rule equals `engine_adapter.review_payload_carried` per result kind (drift) | `test_evidence_digest_subject_matches_review_payload_carried` |
| BP-2a-B | `round_certification._hand_landed_evidence_qualifies` leaf-rule gate | a hand-landed envelope whose payload does not carry the result kind, or whose digest differs, refuses `execution-evidence-result-mismatch` | `test_hand_landed_review_kind_absent_from_payload_refuses` |
| BP-2a-C1 | `round_driver._assemble_dispatch_evidence` carry requirement + digest comparison (one failure-mode class: a payload not carrying the result kind gets stamped; both members neutralized together — each alone is shadowed by the other, see note) | `evidence-result-mismatch` on a kind absent from the payload | `test_assemble_dispatch_evidence_review_kind_absent_from_payload_refuses`, `test_assemble_dispatch_evidence_kind_not_in_payload_refuses` |
| BP-2a-C2 | `_assemble_dispatch_evidence` subject-equality refusal (WO-R3) | the runner subject and the writer subject must hash equal, else `evidence-result-mismatch` + `subjectDisagreement` | `test_assemble_dispatch_evidence_refuses_cross_kind_subject_disagreement` (T9) |
| BP-2a-D1 | `audits._reject_unauthenticated` typed `unauthenticatedCause` stamp | every unauthenticated audit carries a typed cause | `test_apply_audit_results_stamps_unauthenticated_cause_{no_auditor,missing_manifest_entry,vendor_mismatch}` |
| BP-2a-D2 | `round_driver._fold_audits` cause branch | the manifest-missing detail derives from the typed cause, never from reason prose | `test_fold_audits_missing_manifest_detail_from_cause_not_prose` |
| BP-2a-T6 | `_mint_finding_keys` loop-owned classification (WO-R1) | loop-owned duplicates merge on carry recombination | `test_carry_recombination_merges_same_anchor_rows_with_different_severity` |
| BP-2a-T8 | `_mint_finding_keys` legacy-owned bridge (WO-R2) | a legacy unsuffixed key bridges to its re-compiled long-title copy | `test_legacy_unsuffixed_key_bridges_to_recompiled_long_title_copy` |
| BP-2a-T10 | `_mint_finding_keys` `legacy_claims == 1` guard (WO-R3) | an ambiguous legacy key never collapses two findings | `test_ambiguous_legacy_key_never_collapses_distinct_findings` |
| BP-2a-T11 | `_finding_key_of` `not verification.is_staged_id(row_id)` conjunct (WO-R4) | a positional staging id is never an identity; two `v0` rows stay two audit targets | `test_staged_id_is_never_a_finding_identity`, `test_is_staged_id_shape` |
| BP-2a-T12 | `_merge_same_finding` classification restamp (WO-R4) | a merged row's classification follows its merged tradeoff | `test_merge_same_finding_rederives_classification_from_merged_tradeoff` |

T5 (findingKey-over-id precedence) and T7 (foreign preset re-key) were proven by the WO-R1 dispatch
record (prior lane, comment 5741943601); they are not re-run here because no later order touched
their arms — listed as **not re-proven on the final head** for the grader.

---

## BP-2a-A — digest-subject drift

**neutralization** (`session_contract.py`, `evidence_digest_subject`, review-list arm): replace
`if isinstance(value, list): return True, value` / `return False, None` with `return True, value`.

**raw red** (exit 1):
```
E       assert (True, None) == (False, None)
E       AssertionError: assert (True, 'x') == (False, None)
6 failed, 11 passed in 0.58s
```
(the six failures are the `missing-key` / `wrong-type` / `mismatched-kind` cases for `findings` and `verdicts`)

**restore:** inverse edit. **raw green:** `17 passed in 0.26s`.

## BP-2a-B — the writer's hand-landed qualification

**neutralization** (`round_certification.py`, `_hand_landed_evidence_qualifies`): replace the
`else:` body (leaf rule + digest compare) with `pass`.

**raw red** (exit 1):
```
E       assert True is False
FAILED …test_round_certification.py::test_hand_landed_review_kind_absent_from_payload_refuses
1 failed, 1 passed in 0.19s
```
(`test_hand_landed_journal_digest_mismatch_refuses` stayed green — it refuses on the journal digest, upstream of this gate)

**restore:** inverse edit. **raw green:** `2 passed in 0.20s`.

## BP-2a-C1 — the driver's carry requirement + digest comparison

**Note (disclosure):** the two refusals are defense-in-depth on the same path — with only the carry
check neutralized, a non-carrying payload's `None` subject still fails the digest comparison, and
with only the digest comparison neutralized the carry check still refuses; neither alone changes the
observable refusal token. They are proven as one failure-mode class, both neutralized together.

**neutralization** (`round_driver.py`, `_assemble_dispatch_evidence`): `if not carried or not
digest_carried:` → `if False:`; `if result_digest != payload_digest:` → `if False:`.

**raw red** (exit 1):
```
E       AssertionError: assert {'envelopeSha256': 'c00aaafa…', 'executionEvidence': {…}, 'orderSha256': '0e51eabb…', 'payload': {'fixes': []}} is None
E       AssertionError: assert {'envelopeSha256': 'f07c6a1c…', 'executionEvidence': {…}, 'payload': {'fixes': [{'description': 'applied fix', 'file': 'src/f00.py'}]}} is None
FAILED …test_round_driver_integration.py::test_assemble_dispatch_evidence_review_kind_absent_from_payload_refuses
FAILED …test_round_driver_integration.py::test_assemble_dispatch_evidence_kind_not_in_payload_refuses
2 failed in 0.52s
```

**restore:** inverse edits (both lines). **raw green:** `2 passed in 0.40s`.

## BP-2a-C2 — subject equality (WO-R3, T9)

**neutralization** (`_assemble_dispatch_evidence`): compare
`round_records.payload_sha256(digest_subject)` with itself instead of with `adapter_subject`.

**raw red** (exit 1):
```
E       AssertionError: assert {'envelopeSha256': '2e0dd8b1…', 'executionEvidence': {…}, 'payload': {'findings': […], 'grouping': [{'group_id': 'g', 'member_ids': ['x']}]}, …} is None
FAILED …test_evidence_journal_shape_1272.py::test_assemble_dispatch_evidence_refuses_cross_kind_subject_disagreement
1 failed in 0.23s
```

**restore:** inverse edit. **raw green:** `1 passed in 0.22s`.

## BP-2a-D1 — the typed cause stamp

**neutralization** (`audits.py`, `_reject_unauthenticated`): `base.update(ruling="not-discharged",
reason=reason, unauthenticatedCause=cause)` → drop the `unauthenticatedCause=cause` argument.

**raw red** (exit 1):
```
E       KeyError: 'unauthenticatedCause'   (×3)
FAILED …::test_apply_audit_results_stamps_unauthenticated_cause_no_auditor
FAILED …::test_apply_audit_results_stamps_unauthenticated_cause_missing_manifest_entry
FAILED …::test_apply_audit_results_stamps_unauthenticated_cause_vendor_mismatch
3 failed, 25 deselected in 0.17s
```

**restore:** inverse edit. **raw green:** `3 passed, 25 deselected in 0.19s`.

## BP-2a-D2 — `_fold_audits` branches on the cause, not prose

**neutralization** (`round_driver.py`, `_fold_audits`): the first branch condition
`if audit_cause in (UNAUTHENTICATED_MANIFEST_VENDOR_MISMATCH, UNAUTHENTICATED_NO_AUDITOR_RECORDED):`
→ `if True:` (every unauthenticated detail becomes the reason prose — the pre-layer behaviour).

**raw red** (exit 1):
```
E       assert "expected a collectionManifest entry keyed 't1'" in 'audit result for t1 could not be authenticated — anything'
FAILED …test_evidence_digest_subject_1272.py::test_fold_audits_missing_manifest_detail_from_cause_not_prose
1 failed in 0.14s
```

**restore:** inverse edit. **raw green:** `1 passed in 0.13s`.

## BP-2a-T6 — loop-owned merge (WO-R1)

**neutralization** (`_mint_finding_keys`): `elif preset == minted:` → `elif False:` (a loop-minted
preset is classified foreign).

**raw red** (exit 1):
```
E       AssertionError: assert 2 == 1
E        +  where 2 = len([{… 'findingKey': 'a.py::t@L1#081cac9f1a7d', …}, {… 'findingKey': 'a.py::t@L1#ab0ab7c0995e', …}])
FAILED …::test_carry_recombination_merges_same_anchor_rows_with_different_severity
1 failed in 0.17s
```

**restore:** inverse edit. **raw green:** `1 passed in 0.14s`.

## BP-2a-T8 — legacy-owned bridge (WO-R2)

**neutralization** (`_mint_finding_keys`): `elif preset == bare and minted != bare:` → `elif False:`.

**raw red** (exit 1):
```
E       AssertionError: assert 2 == 1
E        +  where 2 = len([{'file': 'f.py', 'findingKey': 'f.py::xxx…@L5#5f9feb4aa688', 'line': 5, …}])
FAILED …::test_legacy_unsuffixed_key_bridges_to_recompiled_long_title_copy
1 failed in 0.14s
```

**restore:** inverse edit. **raw green:** `1 passed in 0.13s`.

## BP-2a-T10 — ambiguous-legacy guard (WO-R3)

**neutralization** (`_mint_finding_keys`): `if legacy_keys and legacy_claims.get(legacy_keys[0], 0) == 1:`
→ `if legacy_keys:` (always adopt the legacy key).

**raw red** (exit 1):
```
E       AssertionError: assert 1 == 2
E        +  where 1 = len([{… 'findingKey': 'f.py::xxx…@L5', …}])
FAILED …::test_ambiguous_legacy_key_never_collapses_distinct_findings
1 failed in 0.14s
```

**restore:** inverse edit. **raw green:** `1 passed in 0.13s`.

## BP-2a-T11 — a staged id is never an identity (WO-R4)

**neutralization** (`_finding_key_of`): `if isinstance(row_id, str) and row_id and not
verification.is_staged_id(row_id):` → `if isinstance(row_id, str) and row_id:` (the pre-order line).

**raw red** (exit 1):
```
E       AssertionError: assert 'v0' == 'a.py::t@L1'
FAILED …::test_staged_id_is_never_a_finding_identity
1 failed in 0.14s
```
Arm (b) under the same mutation, exercised directly because the test stops at its first assertion
(two `v0` rows at different locations through `_audit_targets` then `_union_open_blockers`):
```
targets: ['v0'] union: 1
```
— the unresolved target is dropped, which is dispositions #10's failure mode.

**restore:** inverse edit. **raw green:** `2 passed in 0.19s` (T11 + `test_is_staged_id_shape`).

## BP-2a-T12 — merge-site classification restamp (WO-R4)

**neutralization** (`_merge_same_finding`): delete
`merged["classification"] = "judgment" if merged["tradeoff"] else "mechanical"`.

**raw red** (exit 1):
```
E       AssertionError: assert 'mechanical' == 'judgment'
FAILED …::test_merge_same_finding_rederives_classification_from_merged_tradeoff
1 failed in 0.14s
```

**restore:** inverse edit. **raw green:** `1 passed in 0.13s`.

---

**Restore receipt (all elements):** after each restore, `git -C issue-1272-2a-verify status --porcelain`
printed nothing (exit 0); after the last probe `git diff --stat` printed nothing. No residue.
Nothing redacted (no secrets, tokens, private URLs, or PII appear in the captures).
