# C13 layer 2a (#1272, PR #1330) bite-proof — finding identity and the leaf homes

**Provenance:** the detectors were built by cursor composer-2.5 (WO-1, WO-3 at `442b4dc0`; WO-R1
`3a5fde4a`, WO-R2 `b3ec5fc5`, WO-R3 `9f8c7823`, WO-R4 `6dec1c13`, WO-R5 `c4da4169`, WO-R5b
`dd37c538`, WO-R6 `7237a902`, all via `dispatch-write`). Every proof below was **re-run by the
orchestrator** (launch-7945a36e249a7c38, 2026-09-19) on the head **`7237a902`** in a detached probe
worktree (`issue-1272-2a-verify`), neutralizing through a file-write replace of the quoted text and
restoring by the inverse replace (never a git discard); the restore receipt for every element is an
empty `git status --porcelain` over the probe tree (quoted once at the end — it was empty after every
restore). WO-R5 replaced the identity mint the earlier record (at `6dec1c13`) proved — BP-2a-T10 and
BP-2a-T11 below name the neutralizations that exist on **this** head, not the pre-rebuild lines. Command
for every run (node ids / `-k` per element):

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-1272-bp -m pytest -q -p no:cacheprovider <files> [-k <test>]
```

## Guarded elements (the layer-2a brief, comment 5741176759; WO-R4's order; the WO-R5 addendum, comment 5742438822; WO-R6)

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-2a-A | `session_contract.evidence_digest_subject` review-list arm | the writer's leaf rule equals `engine_adapter.review_payload_carried` per result kind (drift) | `test_evidence_digest_subject_matches_review_payload_carried` |
| BP-2a-B | `round_certification._hand_landed_evidence_qualifies` leaf-rule gate | a hand-landed envelope whose payload does not carry the result kind, or whose digest differs, refuses `execution-evidence-result-mismatch` | `test_hand_landed_review_kind_absent_from_payload_refuses` |
| BP-2a-C1 | `round_driver._assemble_dispatch_evidence` carry requirement + digest comparison (one failure-mode class, both members neutralized together — see note) | `evidence-result-mismatch` on a kind absent from the payload | `test_assemble_dispatch_evidence_review_kind_absent_from_payload_refuses`, `test_assemble_dispatch_evidence_kind_not_in_payload_refuses` |
| BP-2a-C2 | `_assemble_dispatch_evidence` subject-equality refusal (WO-R3) | the runner subject and the writer subject must hash equal, else `evidence-result-mismatch` + `subjectDisagreement` | `test_assemble_dispatch_evidence_refuses_cross_kind_subject_disagreement` (T9) |
| BP-2a-D1 | `audits._reject_unauthenticated` typed `unauthenticatedCause` stamp | every unauthenticated audit carries a typed cause | `test_apply_audit_results_stamps_unauthenticated_cause_{no_auditor,missing_manifest_entry,vendor_mismatch}` |
| BP-2a-D2 | `round_driver._fold_audits` cause branch | the manifest-missing detail derives from the typed cause, never from reason prose | `test_fold_audits_missing_manifest_detail_from_cause_not_prose` |
| BP-2a-T6 | `_mint_finding_keys` loop-owned classification (WO-R1) | loop-owned duplicates merge on carry recombination | `test_carry_recombination_merges_same_anchor_rows_with_different_severity` |
| BP-2a-T8 | `_mint_finding_keys` legacy-owned bridge (WO-R2) | a legacy unsuffixed key bridges to its re-compiled long-title copy | `test_legacy_unsuffixed_key_bridges_to_recompiled_long_title_copy` |
| BP-2a-T10 | `_mint_finding_keys` one-claimant guard (`len(claimants[...]) == 1`, WO-R5's form of WO-R3's guard) | an ambiguous legacy key never collapses two findings | `test_ambiguous_legacy_key_never_collapses_distinct_findings` |
| BP-2a-T11 | the leaf never reads `id` (`session_contract.finding_identity_key`'s minted fallback; WO-R5 removed `_finding_key_of`'s `id` arm) | a positional staging id is never an identity; two `v0` rows stay two audit targets | `test_staged_id_is_never_a_finding_identity`, `test_is_staged_id_shape` |
| BP-2a-T12 | `_merge_same_finding` classification restamp (WO-R4) | a merged row's classification follows its merged tradeoff | `test_merge_same_finding_rederives_classification_from_merged_tradeoff` |
| BP-2a-T13 | `_mint_finding_keys` claimant set — every group that would emit a bare key K counts (WO-R5, dispositions #16) | a legacy long-title row and a clamp-exact new finding stay two rows | `test_legacy_bare_key_with_clamp_exact_new_finding_keeps_two_rows` |
| BP-2a-T13b | the foreign-preset claimant branch of that set (brief-check finding 1) | a foreign row whose preset is K is a claimant of K | `test_foreign_preset_is_a_claimant_of_a_legacy_bare_key` |
| BP-2a-T14 | `session_contract.TRANSIENT_FINDING_FIELDS` in `finding_content_canonical` (WO-R5, #17) | foreign-collision keys are staging-order independent | `test_foreign_collision_keys_are_staging_order_independent` |
| BP-2a-T15 | `finding_identity_key`'s minted fallback (WO-R5, #18) | the driver and certification agree on unkeyed long-title siblings | `test_finding_identity_has_one_home_driver_and_certification_agree` |
| BP-2a-T16 | `_union_open_blockers` one-key dedupe (WO-R5) | persisted targets without a marker dedupe by content; distinct markers survive | `test_persisted_targets_without_marker_dedupe_by_content` |
| BP-2a-CENSUS | the one-home census (WO-R5) | no second derivation in the four loop modules | `test_identity_derivation_has_one_home_census` |
| BP-2a-T17 | `minted_identity_key` hashes `finding_label` (WO-R6, review r1 v0) | summary-only long siblings get distinct keys; the key is label-stable | `test_summary_only_long_findings_key_by_label_not_title` |
| BP-2a-T18 | `"findingKey"` in `review_memory._SKELETON_FIELDS` (WO-R6, review r1 v2) | a durable record row keeps the identity of its live copy | `test_durable_skeleton_carries_finding_key_so_resume_keeps_one_identity` |

T5 (findingKey-over-id precedence) is exercised by BP-2a-T11's arm (the leaf reads `findingKey`
first, and the mutation that reads `id` only reaches a row with no `findingKey`); T7 (foreign
preset re-key) is exercised by BP-2a-T14 (the same collision, both staging orders). Neither has a
separate neutralization here.

---

## BP-2a-A — digest-subject drift

**neutralization** (`session_contract.py`, `evidence_digest_subject`, review-list arm): replace
`if isinstance(value, list): return True, value` / `return False, None` with `return True, value`.

**raw red** (exit 1):
```
E       assert (True, None) == (False, None)
6 failed, 11 passed, 11 deselected in 0.17s
```
(the six failures are the `missing-key` / `wrong-type` / `mismatched-kind` cases for `findings` and `verdicts`)

**restore:** inverse edit. **raw green:** `17 passed, 11 deselected in 0.15s`.

## BP-2a-B — the writer's hand-landed qualification

**neutralization** (`round_certification.py`, `_hand_landed_evidence_qualifies`): replace the
`else:` body (leaf rule + digest compare) with `pass`.

**raw red** (exit 1):
```
E       assert True is False
FAILED …test_round_certification.py::test_hand_landed_review_kind_absent_from_payload_refuses
1 failed, 129 deselected in 0.15s
```

**restore:** inverse edit. **raw green:** `1 passed, 129 deselected in 0.13s`.

## BP-2a-C1 — the driver's carry requirement + digest comparison

**Note (disclosure):** the two refusals are defense-in-depth on the same path — with only the carry
check neutralized, a non-carrying payload's `None` subject still fails the digest comparison, and
with only the digest comparison neutralized the carry check still refuses; neither alone changes the
observable refusal token. They are proven as one failure-mode class, both neutralized together.

**neutralization** (`round_driver.py`, `_assemble_dispatch_evidence`): `if not carried or not
digest_carried:` → `if False:`; `if result_digest != payload_digest:` → `if False:`.

**raw red** (exit 1):
```
E       AssertionError: assert {'envelopeSha256': '9ad87799…', 'executionEvidence': {…}, …} is None
E       AssertionError: assert {'envelopeSha256': 'aa55a04c…', 'executionEvidence': {…}, …} is None
FAILED …test_round_driver_integration.py::test_assemble_dispatch_evidence_review_kind_absent_from_payload_refuses
FAILED …test_round_driver_integration.py::test_assemble_dispatch_evidence_kind_not_in_payload_refuses
2 failed in 0.37s
```

**restore:** inverse edits (both lines, in order). **raw green:** `2 passed in 0.32s`.

## BP-2a-C2 — subject equality (WO-R3, T9)

**neutralization** (`_assemble_dispatch_evidence`): compare
`round_records.payload_sha256(digest_subject)` with itself instead of with `adapter_subject`.

**raw red** (exit 1):
```
E       AssertionError: assert {'envelopeSha256': '2e0dd8b1…', 'executionEvidence': {…}, …} is None
FAILED …test_evidence_journal_shape_1272.py::test_assemble_dispatch_evidence_refuses_cross_kind_subject_disagreement
1 failed, 1 deselected in 0.20s
```

**restore:** inverse edit. **raw green:** `1 passed, 1 deselected in 0.19s`.

## BP-2a-D1 — the typed cause stamp

**neutralization** (`audits.py`, `_reject_unauthenticated`): `base.update(ruling="not-discharged",
reason=reason, unauthenticatedCause=cause)` → drop the `unauthenticatedCause=cause` argument.

**raw red** (exit 1):
```
E       KeyError: 'unauthenticatedCause'   (×3)
3 failed, 25 deselected in 0.16s
```

**restore:** inverse edit. **raw green:** `3 passed, 25 deselected in 0.14s`.

## BP-2a-D2 — `_fold_audits` branches on the cause, not prose

**neutralization** (`round_driver.py`, `_fold_audits`): the first branch condition
`if audit_cause in (audits.UNAUTHENTICATED_MANIFEST_VENDOR_MISMATCH, audits.UNAUTHENTICATED_NO_AUDITOR_RECORDED):`
→ `if True:`.

**raw red** (exit 1):
```
E       assert "expected a collectionManifest entry keyed 't1'" in 'audit result for t1 could not be authenticated — anything'
FAILED …test_evidence_digest_subject_1272.py::test_fold_audits_missing_manifest_detail_from_cause_not_prose
1 failed, 27 deselected in 0.18s
```

**restore:** inverse edit. **raw green:** `1 passed, 27 deselected in 0.18s`.

## BP-2a-T6 — loop-owned merge (WO-R1)

**neutralization** (`_mint_finding_keys`): `elif preset == minted:` → `elif False:`.

**raw red** (exit 1):
```
E       AssertionError: assert 2 == 1
E        +  where 2 = len([{… 'findingKey': 'a.py::t@L1#081cac9f1a7d', …}, …])
1 failed, 18 deselected in 0.20s
```

**restore:** inverse edit. **raw green:** `1 passed, 18 deselected in 0.17s`.

## BP-2a-T8 — legacy-owned bridge (WO-R2)

**neutralization** (`_mint_finding_keys`): `elif preset == bare and minted != bare:` → `elif False:`.

**raw red** (exit 1):
```
E       AssertionError: assert 2 == 1
E        +  where 2 = len([{'file': 'f.py', 'findingKey': 'f.py::xxx…', …}, …])
1 failed, 18 deselected in 0.18s
```

**restore:** inverse edit. **raw green:** `1 passed, 18 deselected in 0.17s`.

## BP-2a-T10 — one-claimant guard (WO-R3, in WO-R5's form)

**neutralization** (`_mint_finding_keys`): `if legacy_keys and len(claimants.get(legacy_keys[0], set())) == 1:`
→ `if legacy_keys:` (always adopt the legacy key).

**raw red** (exit 1):
```
E       AssertionError: assert 1 == 2
E        +  where 1 = len([{… 'findingKey': 'f.py::xxx…@L5', …}])
1 failed, 18 deselected in 0.17s
```

**restore:** inverse edit. **raw green:** `1 passed, 18 deselected in 0.16s`.

## BP-2a-T11 — a staged id is never an identity (WO-R4, re-homed by WO-R5)

On this head `_finding_key_of` is `return session_contract.finding_identity_key(finding)` and the
leaf never consults `id`; the guarded element is that absence. **neutralization**
(`session_contract.py`, `finding_identity_key`): before `return minted_identity_key(finding)` insert
`if isinstance(finding.get("id"), str) and finding.get("id"): return finding["id"]` (a reader that
falls back to the row id).

**raw red** (exit 1):
```
E       AssertionError: assert 'v0' == 'a.py::t@L1'
1 failed, 1 passed, 53 deselected in 0.21s
```
(the pass is `test_is_staged_id_shape`, which pins the `v<N>` shape itself)

**restore:** inverse edit. **raw green:** `2 passed, 53 deselected in 0.20s`.

## BP-2a-T12 — merge-site classification restamp (WO-R4)

**neutralization** (`_merge_same_finding`): replace
`merged["classification"] = "judgment" if merged["tradeoff"] else "mechanical"` with `pass`.

**raw red** (exit 1):
```
E       AssertionError: assert 'mechanical' == 'judgment'
1 failed, 18 deselected in 0.17s
```

**restore:** inverse edit (anchored on the preceding `merged["tradeoff"] = …` line). **raw green:** `1 passed, 18 deselected in 0.16s`.

## BP-2a-T13 — every claimant counts (WO-R5, dispositions #16)

**neutralization** (`_mint_finding_keys`, the claimant loop): drop the `unkeyed`/`loop-owned` and
`foreign` branches so only legacy-owned groups claim a bare key (the pre-WO-R5 `legacy_claims` rule).

**raw red** (exit 1):
```
E       AssertionError: assert 1 == 2
E        +  where 1 = len([{… 'findingKey': 'f.py::xxx…', …}])
1 failed, 18 deselected in 0.17s
```

**restore:** inverse edit. **raw green:** `1 passed, 18 deselected in 0.18s`.

## BP-2a-T13b — a foreign preset is a claimant (brief-check finding 1)

**neutralization** (`_mint_finding_keys`, the claimant loop): delete the
`elif kind == "foreign": claimants.setdefault(identity, set()).add(identity)` branch.

**raw red** (exit 1):
```
E       AssertionError: assert 1 == 2
1 failed, 18 deselected in 0.18s
```

**restore:** inverse edit. **raw green:** `1 passed, 18 deselected in 0.17s`.

## BP-2a-T14 — transient fields never enter the collision hash (WO-R5, #17)

**neutralization** (`session_contract.py`, `finding_content_canonical`): strip only
`FINDING_KEY_FIELD` instead of `TRANSIENT_FINDING_FIELDS` (the pre-WO-R5 rule).

**raw red** (exit 1):
```
E       AssertionError: assert {'caller-cont…e67e5c271fa7'} == {'caller-cont…ad1e99ddcd94'}
1 failed, 18 deselected in 0.18s
```

**restore:** inverse edit. **raw green:** `1 passed, 18 deselected in 0.17s`.

## BP-2a-T15 — one home (WO-R5, #18)

**neutralization** (`session_contract.py`, `finding_identity_key`): `return minted_identity_key(finding)`
→ `return location_key(finding)` (the pre-WO-R5 bare fallback).

**raw red** (exit 1):
```
E       AssertionError: assert 1 == 2
E        +  where 1 = len([{'file': 'f.py', 'line': 5, 'severity': 'Important', 'title': 'xxx…'}])
1 failed, 18 deselected in 0.18s
```
(certification collapses the two unkeyed long-title siblings to one)

**restore:** inverse edit. **raw green:** `1 passed, 18 deselected in 0.16s`.

## BP-2a-T16 — one-key dedupe of the fix batch (WO-R5)

**neutralization** (`_union_open_blockers`): `key = session_contract.finding_identity_key(f)` →
`key = f.get("id") or session_contract.finding_identity_key(f)` (dedupe on the row id when present).

**raw red** (exit 1):
```
E       AssertionError: assert 2 == 1
E        +  where 2 = len([{'file': 'f.py', 'id': 'f.py::same@L4', …}, {'file': 'f.py', 'id': 'f.py::same@L4#1', …}])
1 failed, 18 deselected in 0.17s
```

**restore:** inverse edit. **raw green:** `1 passed, 18 deselected in 0.16s`.

## BP-2a-CENSUS — the one-home census (WO-R5)

**neutralization** (`round_driver.py`): add `def _location_id(f): return session_contract.location_key(f)`
above `_judgment_row_ids` (a second derivation).

**raw red** (exit 1):
```
E                   AssertionError: round_driver defines forbidden _location_id
1 failed, 18 deselected in 0.22s
```

**restore:** inverse edit. **raw green:** `1 passed, 18 deselected in 0.28s`.

## BP-2a-T17 — the minted key hashes the label (WO-R6, review r1 v0)

**neutralization** (`session_contract.py`, `minted_identity_key`):
`full_norm = normalize_title(finding_label(finding))` → `full_norm = normalize_title(str(finding.get("title") or ""))`.

**raw red** (exit 1):
```
E       AssertionError: assert 'f.py::xxxxxx…#e3b0c44298fc' == 'f.py::xxxxxx…#5f9feb4aa688'
1 failed, 18 deselected in 0.18s
```
(`e3b0c442…` is sha256 of the empty string — the summary-only row hashed nothing)

**restore:** inverse edit. **raw green:** `1 passed, 18 deselected in 0.18s`.

## BP-2a-T18 — the durable skeleton keeps `findingKey` (WO-R6, review r1 v2)

**neutralization** (`review_memory.py`, `_SKELETON_FIELDS`): remove `"findingKey"`.

**raw red** (exit 1):
```
E       KeyError: 'findingKey'
1 failed, 18 deselected in 0.18s
```

**restore:** inverse edit. **raw green:** `1 passed, 18 deselected in 0.16s`.

---

**Restore receipt (all elements):** after each restore, `git -C issue-1272-2a-verify status --porcelain`
printed nothing (exit 0); after the last probe `git diff --stat` printed nothing. Two restores needed an
anchored inverse (BP-2a-C1's two identical `if False:` lines restored in order; BP-2a-T12's `pass`
restored by its preceding line) — both confirmed by the empty porcelain afterwards. No residue.
Nothing redacted (no secrets, tokens, private URLs, or PII appear in the captures).
