# Bite-proof record — #1272 layer 2e (the C13 folds: follow-ups, legacy-key collision, staged-id resolution, coverage, the ceiling gate)

Contract: `rubric/bite-proof.md`. Every proof below ran with the **detector unedited**. Each
neutralization was one targeted, reversible edit to a production line, applied with the edit tool
and restored by its exact inverse edit — never `git checkout`, never a whole-file rewrite. After
every restore, `git status --porcelain` over the probe tree printed **empty**.

**Order gap, flagged.** Layer 2e's orders did **not** declare a guarded-element set up front. Per
`rubric/bite-proof.md` ("when the order declared no set … enumerate every independently
neutralizable element the detector guards, **flag the order gap**, and apply the ceilings over that
enumeration"), the enumeration below was derived at verification from the layer's own source diff
(`ef86ad8a..551a36dc`, the five changed non-test modules) rather than inherited from an order. A
grader reading the set one level finer records the finer reading as a signal, never a rework demand.

**Who ran these, and where.** The **workhorse orchestrator** ran every proof itself (the r3 adoption
lane lands no code, so there were no implementer proofs to re-run). All runs were in a dedicated
**detached probe worktree** at the final head `551a36dc`, outside the build worktree and outside any
tree a live seat was reading. Command shape, every run:
`/usr/bin/python3 -B -X pycache_prefix=<scratch> -m pytest <node-id …> -q -p no:randomly`, with the
runner's **own** exit code captured (never a pipe's). Detectors were selected by **exact node id**,
never by `-k`, except where a whole test file is named. Nothing is redacted; the captures hold only
temporary paths.

**Baseline at `551a36dc`, detector-unedited:** the four layer-2e test files → `69 passed in 28.57s`
(EXIT=0). **Final green sweep after every restore:** those four files plus
`test_round_driver_round_economy_1272.py` → `98 passed in 118.12s` (EXIT=0), and
`git diff --stat` over the probe tree printed **nothing** — the tree is byte-identical to
`551a36dc`.

---

## The declared guarded-element set — 46 elements

Derived at verification (see the order gap above). Every guard with more than one independently
neutralizable operand or branch is split into one element per operand or branch.

| | Element | Home | Proof |
|---|---|---|---|
| **A1** | `follow_up_shape_fault` — non-dict `followUp` | `session_contract.py` | proven |
| **A2** | `follow_up_shape_fault` — `require_item` missing-`item` leg | `session_contract.py` | proven |
| **A3** | `follow_up_shape_fault` — present-but-empty / non-string `item` | `session_contract.py` | proven |
| **A4** | `follow_up_shape_fault` — missing / blank `revisitTrigger` | `session_contract.py` | proven |
| **A5** | `follow_up_shape_fault` — the forbidden `documented` token | `session_contract.py` | proven |
| **A6** | `follow_up_shape_fault` — missing / blank `classClosure` | `session_contract.py` | proven |
| **B1** | `legacy_key_collision` — the minted-twin lookup | `session_contract.py` | proven |
| **B2** | collision refusal, ledger-owner branch | `round_certification.py` | proven |
| **B3** | collision refusal, legacy branch | `round_certification.py` | proven |
| **B4** | non-colliding rows are **not** refused | `session_contract.py` | proven (negative control) |
| **C1** | `evidence_binding` — write kind → `execution-only` | `session_contract.py` | proven |
| **C2** | the `WRITE_RESULT_KIND` comparison census | `test_layer2e_ledger_evidence_1272.py` | proven |
| **C3** | `_hand_landed_evidence_qualifies` reads the one derivation | `round_certification.py` | proven (with C2) |
| **D1** | certification grades persisted follow-ups with `require_item=False` | `round_certification.py` | proven |
| **E1** | `build_receipt` `findingKey` projection, schema-version gate | `round_driver.py` | proven |
| **E2** | the `or 0` absent-`schemaVersion` guard on that gate | `round_driver.py` | proven |
| **F1** | `judgment_follow_up_fault` — submit-chokepoint wiring | `round_driver.py` | proven |
| **F2** | `judgment_follow_up_fault` — the `!= "skip"` scope operand | `round_driver.py` | proven (inclusion half; see disclosure D-3) |
| **F3** | `judgment_follow_up_fault` — the non-list `dispositions` guard | `round_driver.py` | proven |
| **F4** | `stall_follow_up_fault` — the `ACCEPT_RISK_CHOICE` scope operand | `round_driver.py` | proven by A/B (disclosure D-4) |
| **F5** | `stall_follow_up_fault` — submit-chokepoint wiring | `round_driver.py` | proven |
| **G1** | `_judgment_skip_equiv` — the `followUp` equality leg | `round_driver.py` | proven |
| **G2** | `_fold_judgment`'s skip/skip `reason` collision branch | `round_driver.py` | **unproven** — disclosure D-5 |
| **G3** | `_fold_judgment`'s skip/skip `followUp` collision branch | `round_driver.py` | **unproven** — disclosure D-5 |
| **H1** | `_judgment_artifact_from_resolution` carries `followUp` | `round_driver.py` | proven |
| **H2** | `resolve_stall` carries `followUp` into `action` | `review_gate_policy.py` | proven |
| **H3** | `resolve_judgment` carries `followUp` into `action.dispositions` | `review_gate_policy.py` | **unproven, unconsumed** — disclosure D-1 |
| **I1** | `_validate_layer` — `layer-follow-up-not-allowed` | `review_gate_policy.py` | proven |
| **I2** | `_validate_layer` — `layer-follow-up-malformed` | `review_gate_policy.py` | proven |
| **I3** | `validate_policy_for_write` — the allow-list leg | `review_gate_policy.py` | proven by A/B (disclosure D-2) |
| **I4** | `validate_policy_for_write` — the malformed leg | `review_gate_policy.py` | proven |
| **J1** | `_staged_by_id_map` — duplicate staged id | `round_driver.py` | proven |
| **J2** | `_staged_id_resolution_fault` — missing staged id | `round_driver.py` | proven |
| **J3** | `_staged_id_resolution_fault` — maps to no entry | `round_driver.py` | proven |
| **J4** | `_staged_id_resolution_fault` — no derivable finding key | `round_driver.py` | proven |
| **J5** | `verifier_drop_staged_id_fault` — submit wiring | `round_driver.py` | proven |
| **J6** | `synthesis_staged_id_fault` — submit wiring | `round_driver.py` | proven |
| **J7** | `_fold_verifiers` — park on an unresolvable drop id | `round_driver.py` | proven |
| **J8** | `_fold_synthesis` — park on an unresolvable author-justified drop id | `round_driver.py` | proven |
| **K1** | `synthesis_results_fault` — non-dict artifact | `round_driver.py` | proven |
| **K2** | `synthesis_results_fault` — the missing-`grouping`-key leg | `round_driver.py` | proven by A/B (disclosure D-6) |
| **K3** | `synthesis_results_fault` — submit wiring | `round_driver.py` | proven |
| **L1** | `grouping_coverage_fault` — `duplicate_member` | `verification.py` | proven |
| **L2** | `_coverage_fault_from_seen` — the exact-once rule | `verification.py` | proven |
| **L3** | `grouping_coverage_fault` — empty / absent grouping carries no obligation | `verification.py` | proven |
| **M1** | `_try_reuse_ceiling_verify_gate` — reuse requires a recorded `pass` | `round_driver.py` | proven |
| **M2** | `_enter_post_fix` — the reuse call | `round_driver.py` | proven |
| **M3** | the deleted `ceilingGateSkipped` branch (walk-5 ruling 33 = a) | `round_driver.py` | proven |
| **M4** | `_fold_fixer` threads `session_dir` into `_enter_post_fix` | `round_driver.py` | proven |
| **M5** | `_try_reuse_ceiling_verify_gate` — the `head_err or not post_fix_head` operand | `round_driver.py` | **unproven** — disclosure D-7 |
| **N1** | the surviving relocation non-object guard, now provable alone | `round_driver.py` | proven |
| **O1** | `verified_head_for_round` / `verify_result_for_round` | `session_contract.py` | **unproven, unconsumed** — disclosure D-8 |

---

## A — `session_contract.follow_up_shape_fault`, six branches

### A1 — non-dict `followUp`

**Guarded element.** `session_contract.follow_up_shape_fault`, the `if not isinstance(follow_up, dict):` branch.
**Axis:** a `followUp` that is not an object is a fault, not an absent follow-up.

**Neutralization.** `return (None, "out-of-scope disposition lacks named follow-up item")` → `return None`.

**Detector.** `test_layer2e_follow_up_1272.py::test_rule_1_not_dict`.

**Red** (EXIT=1):

```
        fault = SC.follow_up_shape_fault(None)
>       assert fault == (None, "out-of-scope disposition lacks named follow-up item")
E       AssertionError: assert None == (None, 'out-of-scope disposition lacks named follow-up item')
1 failed in 0.66s
```

**Restore.** Inverse edit. **Restore receipt:** `git status --porcelain` over the probe tree → empty.
**Green** (EXIT=0): `1 passed in 0.65s`.

### A2 — the `require_item` missing-`item` leg

**Guarded element.** `if require_item and "item" not in follow_up:`.
**Axis:** a **new** ruling must name its follow-up item; a **persisted** record need not.

**Neutralization.** `if require_item and "item" not in follow_up:` → `if False and require_item and "item" not in follow_up:`.

**Detectors.** `test_rule_2_item_absent_refused_when_required` (expected red) **and**
`test_rule_2_legacy_item_absent_passes` (expected to stay green — the discriminating control that
shows the mutation hit the `require_item=True` leg and not the helper as a whole).

**Red** (EXIT=1):

```
        fault = SC.follow_up_shape_fault({"revisitTrigger": "later", "classClosure": "none"})
>       assert fault == ("missing-follow-up-item", "out-of-scope follow-up lacks named item")
E       AssertionError: assert None == ('missing-follow-up-item', 'out-of-scope follow-up lacks named item')
1 failed, 1 passed in 0.65s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): `2 passed in 0.63s`.

### A3 — present-but-empty or non-string `item`

**Guarded element.** `if not isinstance(item, str) or not item.strip():` inside the `"item" in follow_up` branch.
**Axis:** an empty `item` is refused on **every** path, including the lenient persisted-record path.

**Neutralization.** that condition → `if False:`.

**Detectors** — all three consumer entry points: `test_rule_2b_present_empty_item_refused` (helper),
`test_e9b_present_empty_item_refused_at_certification` (certification),
`test_e2b_judgment_skip_present_empty_item_refused_at_submit` (submit chokepoint).

**Red** (EXIT=1) — decisive line from the submit case:

```
        out = _pending_submit(session_dir, bad)
>       assert out["ok"] is False, out
E       AssertionError: {'foldLanded': True, 'nextStep': 'terminal', 'ok': True, 'phase': 'present-judgment', ...}
3 failed in 0.68s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): `3 passed in 0.79s`.

### A4 — missing or blank `revisitTrigger`

**Guarded element.** the `("missing-revisit-trigger", …)` return.
**Axis:** a follow-up with no revisit trigger is refused under that named binding failure.

**Neutralization.** `return ("missing-revisit-trigger", "out-of-scope follow-up lacks revisit trigger")` → `return None`.

**Detector.** `test_rule_3_missing_revisit_trigger`.

**Red** (EXIT=1):

```
        fault = SC.follow_up_shape_fault({"item": "defer", "classClosure": "none"})
>       assert fault == ("missing-revisit-trigger", "out-of-scope follow-up lacks revisit trigger")
E       AssertionError: assert None == ('missing-revisit-trigger', 'out-of-scope follow-up lacks revisit trigger')
1 failed in 0.66s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): `1 passed in 0.66s`.

### A5 — the forbidden `documented` token

**Guarded element.** `if "documented" in trigger.lower():`.
**Axis:** "documented" is not a revisit trigger — the word alone never discharges the obligation.

**Neutralization.** → `if False and "documented" in trigger.lower():`.

**Detectors.** `test_rule_4_documented_trigger` (helper) and
`test_e7_stall_accept_risk_malformed_follow_up_refused` (the stall submit chokepoint, which carries
exactly this trigger).

**Red** (EXIT=1):

```
        out = _pending_submit(session_dir, artifact)
>       assert out["ok"] is False, out
E       AssertionError: {'foldLanded': True, 'nextStep': 'terminal', 'ok': True, 'phase': 'present-stall-menu', ...}
2 failed in 0.69s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): `2 passed in 0.67s`.

### A6 — missing or blank `classClosure`

**Guarded element.** the `("missing-class-closure", …)` return.
**Axis:** a follow-up with no class-closure line is refused under that named binding failure.

**Neutralization.** that return → `return None`.

**Detector.** `test_rule_5_missing_class_closure`.

**Red** (EXIT=1):

```
        fault = SC.follow_up_shape_fault({"item": "defer", "revisitTrigger": "2026-12-01"})
>       assert fault == ("missing-class-closure", "out-of-scope follow-up lacks class-closure line")
E       AssertionError: assert None == ('missing-class-closure', 'out-of-scope follow-up lacks class-closure line')
1 failed in 0.68s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): `1 passed in 0.67s`.

---

## B — the legacy/minted key collision

### B1 — `legacy_key_collision`, the minted-twin lookup

**Guarded element.** `session_contract.legacy_key_collision`, `if minted in identity_keys: return bare, minted`.
**Axis:** a legacy bare-keyed row that collides with a minted-key twin is reported, so certification refuses.

**Neutralization.** → `if False and minted in identity_keys:`.

**Detectors.** all four collision cases in `test_layer2e_ledger_evidence_1272.py`:
`test_e1_ledger_bare_live_minted_refuses`, `test_e2_ledger_minted_live_bare_refuses`,
`test_e3_two_ledger_rows_bare_and_minted_refuses`, `test_e4_legacy_branch_records_bare_live_minted_refuses`.

**Red** (EXIT=1) — decisive lines (all four the same shape):

```
>       assert by_key == {}
E       AssertionError: assert {'f.py::xxxxx...ortant', ...}} == {}
4 failed in 0.18s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty.
**Green** (EXIT=0): whole file, `21 passed in 0.18s`.

### B2 — the refusal at the ledger-owner branch

**Guarded element.** `round_certification._certification_findings_by_key`, the **ledger-owner** branch's
`if collision is not None:` (the one preceded by `branch_rows = list(ledger_rows)`).
**Axis:** with the ledger owning dispositions, a collision refuses **there**, not one branch later.

**Neutralization.** → `if False:`.

**Detector.** the same four cases; **e1, e2, e3 expected red, e4 expected to stay green** — e4 exercises
the other branch, so its staying green is what attributes the red to this site and not to B1 or B3.

**Red** (EXIT=1):

```
>       assert by_key == {}
E       AssertionError: assert {'f.py::xxxxx...ortant', ...}} == {}
FAILED …::test_e1_ledger_bare_live_minted_refuses
FAILED …::test_e2_ledger_minted_live_bare_refuses
FAILED …::test_e3_two_ledger_rows_bare_and_minted_refuses
3 failed, 18 passed in 0.20s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green:** see B3's green.

### B3 — the refusal at the legacy branch

**Guarded element.** the **legacy** branch's `if collision is not None:` (module-level indentation, after
the `_records` sweep).
**Axis:** with no ledger owner, the same collision refuses on the legacy path.

**Neutralization.** → `if False:`.

**Detector.** the same four cases; **only e4 expected red** — the mirror image of B2, which is what
separates the two sites.

**Red** (EXIT=1):

```
>       assert by_key == {}
E       AssertionError: assert {'f.py::xxxxx...ortant', ...}} == {}
FAILED …::test_e4_legacy_branch_records_bare_live_minted_refuses
1 failed, 20 passed in 0.19s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty.
**Green** (EXIT=0, both files after B2 and B3 restores): `43 passed in 0.77s`.

### B4 — the negative control: non-colliding rows are not refused

**Guarded element.** the same detector, read from the other side.
**Axis:** a clamp-exact bare==minted row, a lone bare-keyed row, and two distinct findings at one
location must **not** be refused.

**Evidence.** `test_e5_short_title_bare_equals_minted_no_collision`,
`test_e6_bare_keyed_row_alone_no_refusal`, `test_e7_two_distinct_findings_same_location_no_collision`
and `test_e8_non_dict_rows_skipped_by_helper` stayed **green under every one of B1–B3's
neutralizations** (they are inside the `18 passed` / `20 passed` counts above) and pass in the final
sweep. **This is a control, not a red-bearing element** — stated here so the record cannot be read as
claiming a red it did not produce.

> **Standing limitation, carried up.** The confirming round's **CONFIRMED Critical** is that this
> collision detector does **not** refuse a **clamp-exact legacy-key collision** — two rows whose
> long/short forms clamp to the same bare key with different minted identities. `test_e5` above pins
> the *current* (non-refusing) behaviour, so this record's green is evidence about the shipped
> behaviour, **not** evidence that the shipped behaviour is right. The fix lands in layer **2e-b**
> as a stack-level hold; see the PR's owner half.

---

## C — the evidence binding, and its census

### C1 — `evidence_binding`

**Guarded element.** `session_contract.evidence_binding`, `if result_kind == WRITE_RESULT_KIND: return EXECUTION_ONLY_BINDING`.
**Axis:** a write run's stamp binds its **execution**, never a transported payload.

**Neutralization.** that `return EXECUTION_ONLY_BINDING` → `return PAYLOAD_BOUND_BINDING`.

**Detectors.** `test_evidence_binding_write_kind_execution_only` (red) and
`test_evidence_binding_review_kind_payload_bound` (stays green — the control).

**Red** (EXIT=1):

```
>       assert SC.evidence_binding(SC.WRITE_RESULT_KIND) == SC.EXECUTION_ONLY_BINDING
E       AssertionError: assert 'payload-bound' == 'execution-only'
1 failed, 1 passed in 0.17s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0, with C2): `43 passed in 0.77s`.

### C2 / C3 — the one-derivation census, and the site that adopted it

**Guarded element.** `test_write_result_kind_comparison_census` — the census that keeps
`WRITE_RESULT_KIND` comparisons inside `session_contract.py` (and `engine_dispatch.py`) — together
with the `round_certification._hand_landed_evidence_qualifies` site that layer 2e converted to
`evidence_binding(...)`.
**Axis:** exactly one derivation of the write-vs-payload binding exists; a second one is a census
violation. **This is an external-contract census, so the neutralization reintroduces the literal
comparison rather than reaching it through a symbol.**

**Neutralization.** in `round_certification._hand_landed_evidence_qualifies`:
`if session_contract.evidence_binding(result_kind) == session_contract.EXECUTION_ONLY_BINDING:`
→ `if result_kind == session_contract.WRITE_RESULT_KIND:`.

**Detector.** `test_write_result_kind_comparison_census`.

**Red** (EXIT=1) — and the red **names the exact re-introduced site**, which is what makes this an
on-axis bite rather than a count:

```
>       assert violations == []
E       AssertionError: assert ['round_certi..._RESULT_KIND'] == []
E         Left contains one more item: 'round_certification.py: == session_contract.WRITE_RESULT_KIND'
1 failed in 0.17s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): `43 passed in 0.77s`.

---

## D1 — certification grades persisted follow-ups leniently on `item`

**Guarded element.** `round_certification.check_disposition_without_receipt`,
`session_contract.follow_up_shape_fault(follow_up, require_item=False)`.
**Axis:** certification grades a **persisted** record, some of which predate the submit-time `item`
check — so a missing `item` certifies, while an **empty** one still refuses.

**Neutralization.** `require_item=False` → `require_item=True`.

**Detectors.** `test_e9_item_less_persisted_follow_up_certifies` (red) and
`test_e9b_present_empty_item_refused_at_certification` (stays green — the control that shows the
strict half is untouched).

**Red** (EXIT=1):

```
        refusal = RC.check_disposition_without_receipt(ctx)
>       assert refusal is None
E       AssertionError: assert {'artifact': 'old', 'bindingFailure': 'missing-follow-up-item', 'class': 'disposition-without-receipt', 'detail': 'out-of-scope follow-up lacks named item'} is None
1 failed, 1 passed in 0.66s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): `43 passed in 0.77s`.

---

## E — the receipt's `findingKey` projection

### E1 — the schema-version gate

**Guarded element.** `round_driver.build_receipt`, `if (_state_version(state) or 0) >= STATE_SCHEMA_VERSION:`.
**Axis:** a **v2** receipt's finding rows stay byte-for-byte as they were — `findingKey` is projected
only at the current schema version.

**Neutralization.** → `if True:`.

**Detectors.** `test_legacy_receipt_omits_finding_key_even_when_state_has_it` (red) and
`test_driver_receipt_finding_key_matches_state_row` (stays green — the control).

**Red** (EXIT=1):

```
>       assert SC.FINDING_KEY_FIELD not in receipt["findings"][0]
E       AssertionError: assert 'findingKey' not in {'challenge': None, 'file': 'a.py', 'findingKey': 'a.py::issue@L1', 'id': 'F1', ...}
1 failed, 1 passed in 0.17s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

### E2 — the `or 0` absent-`schemaVersion` guard

**Guarded element.** the `(… or 0)` in that same condition.
**Axis:** a state with **no** `schemaVersion` must not raise on the projection gate.

**Neutralization.** `(_state_version(state) or 0) >= STATE_SCHEMA_VERSION` → `_state_version(state) >= STATE_SCHEMA_VERSION`.

**Detector.** `test_receipt_with_absent_schema_version_does_not_raise`.

**Red** (EXIT=1):

```
>           if _state_version(state) >= STATE_SCHEMA_VERSION:
E           TypeError: '>=' not supported between instances of 'NoneType' and 'int'
1 failed in 0.25s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

---

## F — follow-ups at the submit chokepoint

### F1 — `judgment_follow_up_fault`'s wiring

**Guarded element.** `round_driver._cmd_submit_prepare`, the `P_JUDGMENT` block's
`fault = judgment_follow_up_fault(artifact)` / `if fault:`.
**Axis:** a malformed `followUp` on a judgment skip is refused **before** fold — the state file never moves.

**Neutralization.** `if fault:` → `if False:`.

**Detectors.** `test_e2_judgment_skip_item_less_follow_up_refused_at_submit`,
`test_e3_judgment_skip_documented_trigger_refused`, `test_e4_judgment_skip_null_follow_up_refused`,
`test_e10_advance_owner_artifact_malformed_follow_up_refused` (the last one proving `advance --owner-artifact`
shares this gate).

**Red** (EXIT=1):

```
>       assert out["ok"] is False, out
E       AssertionError: {'brokeLock': None, 'folded': {…}, 'ok': True, …}
4 failed in 0.70s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

### F2 — the `!= "skip"` scope operand

**Guarded element.** `judgment_follow_up_fault`, `if not isinstance(disp, dict) or disp.get("disposition") != "skip": continue`.
**Axis:** only **skip** dispositions have their `followUp` graded.

**Neutralization.** the operand **inverted**: `!= "skip"` → `== "skip"`.

**Detectors.** `test_e2_judgment_skip_item_less_follow_up_refused_at_submit` (red — the inclusion half)
and `test_e6_judgment_fix_stray_follow_up_not_checked` (stays green).

**Red** (EXIT=1):

```
        out = _pending_submit(session_dir, artifact)
>       assert out["ok"] is False, out
E       AssertionError: {'foldLanded': True, 'nextStep': 'terminal', 'ok': True, 'phase': 'present-judgment', ...}
1 failed, 1 passed in 0.67s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

**Disclosure D-3 — the exclusion half is not discriminated by a committed detector.** A first
neutralization that *removed* the skip test outright (`!= "skip"` → dropped) left `test_e6` **green**:
`e6`'s non-skip fixture carries no `reason`, so the reasonless-skip `continue` one line below absorbs
it before the `followUp` check is reached. That is `rubric/bite-proof.md` trap 4's second face **in the
existing fixture**, not in this probe — and the cure named there is to fix the fixture, which this
lane lands no code to do. **Owed:** a fixture whose non-skip disposition carries both a `reason` and a
malformed `followUp`. Carried to layer 2e-b as a follow-up; **unadjudicated** (the actor who verified
also typed this record — see "Adjudication" below).

### F3 — the non-list `dispositions` guard

**Guarded element.** `judgment_follow_up_fault`, `raw = artifact.get("dispositions") if isinstance(artifact.get("dispositions"), list) else []`.
**Axis:** a truthy non-list `dispositions` returns a structured refusal, never a `TypeError` out of the
submit chokepoint. **This is the r1 open finding's fix, re-proven at the final head.**

**Neutralization.** → `raw = artifact.get("dispositions") or []`.

**Detector.** `test_layer2e_gate_policy_follow_up_1272.py::test_judgment_follow_up_fault_nonlist_dispositions`.

**Red** (EXIT=1):

```
        raw = artifact.get("dispositions") or []
>       for disp in raw:
E       TypeError: 'int' object is not iterable
1 failed in 0.32s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

### F4 — `stall_follow_up_fault`'s choice operand

**Guarded element.** `stall_follow_up_fault`, `if artifact.get("choice") != ACCEPT_RISK_CHOICE: return None`.
**Axis:** only **accept-the-disclosed-risk** has its `followUp` graded; `hold` does not.

**Neutralization.** → `if False:`.

**Detector attempted.** `test_e8_stall_hold_with_follow_up_not_checked` — **NOT RED** (EXIT=0,
`1 passed in 0.66s`). `e8`'s `hold` fixture carries a **well-formed** `followUp`, so removing the choice
guard changes nothing observable through it (trap 4's second face again, in the existing fixture).

**Substitute evidence — a direct A/B at the guard**, run in the probe tree, same head, same
interpreter, fresh bytecode caches per arm:

```
ARM A (guard neutralized):
HOLD + malformed followUp   -> 'follow-up-malformed: stall: out-of-scope follow-up lacks revisit trigger'
ACCEPT + malformed followUp -> 'follow-up-malformed: stall: out-of-scope follow-up lacks revisit trigger'

ARM B (guard restored):
HOLD + malformed followUp   -> None
ACCEPT + malformed followUp -> 'follow-up-malformed: stall: out-of-scope follow-up lacks revisit trigger'
```

The A/B discriminates exactly the guarded axis. **Cases it does not discriminate:** anything about how
a refused `hold` would behave downstream of `cmd_submit` — the A/B calls the fault function directly.
**Restore.** Inverse edit. **Restore receipt:** porcelain empty.
**Owed (disclosure D-4):** a committed test that passes a **malformed** `followUp` on a `hold` choice.
Carried to 2e-b; **unadjudicated**.

### F5 — `stall_follow_up_fault`'s wiring

**Guarded element.** `_cmd_submit_prepare`, the `P_STALL` block's `fault = stall_follow_up_fault(artifact)` / `if fault:`.
**Axis:** the stall gate refuses at the chokepoint, not at fold.

**Neutralization.** `if fault:` → `if False:`.

**Detector.** `test_e7_stall_accept_risk_malformed_follow_up_refused`.

**Red** (EXIT=1):

```
        out = _pending_submit(session_dir, artifact)
>       assert out["ok"] is False, out
E       AssertionError: {'foldLanded': True, 'nextStep': 'terminal', 'ok': True, 'phase': 'present-stall-menu', ...}
1 failed in 0.67s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

---

## G — the judgment duplicate-id collision

### G1 — `_judgment_skip_equiv`'s `followUp` equality leg

**Guarded element.** `round_driver._judgment_skip_equiv`, the canonical-`followUp` comparison.
**Axis:** two `skip` rulings for one id with **different** follow-ups are a collision, even when their
reasons match.

**Neutralization.** the final `return session_contract.canonical(...) == session_contract.canonical(...)` → `return True`.

**Detector.** `test_e2c_duplicate_skip_conflicting_follow_up_refused_at_submit`.

**Red** (EXIT=1):

```
        out = _pending_submit(session_dir, artifact)
>       assert out["ok"] is False, out
E       AssertionError: {'foldLanded': True, 'nextStep': 'terminal', 'ok': True, 'phase': 'present-judgment', ...}
1 failed in 0.67s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

### G2 / G3 — the same two comparisons inside `_fold_judgment`

**Guarded elements.** `_fold_judgment`'s skip/skip `reason` branch and its skip/skip `followUp` branch.
**Axis:** the same collision, caught at fold.

**Proof status: UNPROVEN — disclosure D-5, "unreachable through this entry point".**
**The public path that strips the input:** `_cmd_submit_prepare`'s `P_JUDGMENT` block calls
`judgment_disposition_collision_fault` **before** any fold, so a colliding artifact is refused at the
chokepoint and never reaches `_fold_judgment`'s copies. **The seam that does bite:**
`round_driver.judgment_disposition_collision_fault` via `_judgment_skip_equiv` — proven at **G1** above.
These two branches are a **defense-in-depth backstop** behind a proven chokepoint; their protection at
that site is unverified. **Unadjudicated.**

---

## H — carrying a calibrated `followUp` through

### H1 — the judgment artifact carries it

**Guarded element.** `round_driver._judgment_artifact_from_resolution`,
`follow_up = rule.get("followUp")` / `if follow_up is not None: entry["followUp"] = dict(follow_up)`.
**Axis:** a gate-policy `skip` rule's calibrated follow-up reaches the disposition ledger.

**Neutralization.** `if follow_up is not None:` → `if False:`.

**Detector.** `test_layer2e_gate_policy_follow_up_1272.py::test_e1_judgment_skip_follow_up_loads_and_folds`.

**Red** (EXIT=1):

```
>       assert entries[0].get("followUp") == _WELL_FORMED
E       AssertionError: assert None == {'classClosure': 'tracked separately', 'item': 'defer auth redesign', 'revisitTrigger': 'when #1300 lands'}
1 failed in 1.98s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

### H2 — `resolve_stall` carries it into `action`

**Guarded element.** `review_gate_policy.resolve_stall`, `if "followUp" in rule: action["followUp"] = dict(rule["followUp"])`.
**Axis:** the stall resolution's action carries the calibrated follow-up to its consumer.

**Neutralization.** → `if False:`.

**Detector.** `test_e2_stall_accept_risk_follow_up_loads_and_folds`.

**Red** (EXIT=1):

```
>       assert out["policyApplied"]["action"].get("followUp") == _WELL_FORMED
E       AssertionError: assert None == {'classClosure': 'tracked separately', 'item': 'defer auth redesign', 'revisitTrigger': 'when #1300 lands'}
1 failed in 2.01s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

### H3 — `resolve_judgment` carries it into `action.dispositions`

**Guarded element.** `review_gate_policy.resolve_judgment`, `if "followUp" in rule: disp["followUp"] = dict(rule["followUp"])`.

**Proof status: UNPROVEN — disclosure D-1, "unprovable as placed", and the cause is that it has no consumer.**
**Neutralization applied:** → `if False:`. **Detector attempted:** first
`test_e1_judgment_skip_follow_up_loads_and_folds` + `test_e2_stall_accept_risk_follow_up_loads_and_folds`
(**NOT RED**, EXIT=0, `2 passed in 3.68s`), then a **broad sweep** over the whole lib test tree
(`-k "follow_up or followup or gate_policy"`): **NOT RED**, EXIT=0, `126 passed, 14945 deselected`.
**Why:** the driver's only judgment consumer, `_judgment_artifact_from_resolution`, reads
`matches[].rule`, never `action.dispositions` — a symbol census over `plugins/superheroes/lib/` and
`plugins/superheroes/skills/` finds `resolve_judgment` called at exactly one site
(`round_driver.py:10264`), which takes the `matches` path. **What would make it provable:** a consumer,
or removal. **Plain statement: the protection this line claims is unverified, because nothing reads
what it writes.** Carried to 2e-b as a follow-up (keep-with-a-consumer or remove); **unadjudicated**.

---

## I — the gate-policy follow-up allow-list

### I1 — `_validate_layer`, `layer-follow-up-not-allowed`

**Guarded element.** `review_gate_policy._validate_layer`, `if not allowed: return None, "layer-follow-up-not-allowed"`.
**Axis:** a `followUp` may ride only a judgment **skip** or a stall **accept-the-disclosed-risk** rule.

**Neutralization.** → `if False:`.

**Detectors.** `test_e4_follow_up_on_judgment_fix_not_allowed`, `test_e5_follow_up_on_stall_hold_not_allowed`.

**Red** (EXIT=1):

```
        loaded = RGP.parse_overlay(_overlay(policy))
>       assert loaded["ok"] is False
E       assert True is False
2 failed in 0.24s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

### I2 — `_validate_layer`, `layer-follow-up-malformed`

**Guarded element.** the `if fault is not None: return None, "layer-follow-up-malformed"` leg.
**Axis:** a calibrated follow-up must itself be fully shaped, or the overlay is refused at load.

**Neutralization.** → `if False:`.

**Detectors.** `test_e3_follow_up_item_less_refused_at_load_and_write`,
`test_e3b_follow_up_present_empty_item_refused_at_load_and_write`, `test_e6_null_follow_up_malformed`
(red), and `test_e8_invalid_overlay_follow_up_falls_back_to_shipped_default` (stays green — the
fallback control).

**Red** (EXIT=1):

```
        loaded = RGP.parse_overlay(_overlay(policy))
>       assert loaded["ok"] is False
E       assert True is False
3 failed, 1 passed in 1.89s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

### I3 — `validate_policy_for_write`, the allow-list leg

**Guarded element.** `validate_policy_for_write`, `if not follow_up_allowed: return "rules[%d].followUp: not allowed for disposition %r"`.
**Axis:** the calibration **write** check names the offending rule index and disposition.

**Neutralization.** → `if False:`.

**Detector attempted.** `test_e4_follow_up_on_judgment_fix_not_allowed` +
`test_e5_follow_up_on_stall_hold_not_allowed` — **NOT RED** (EXIT=0, `2 passed in 0.22s`). Those two
tests exercise `parse_overlay` only; **no committed test passes a not-allowed `followUp` through the
write path.** The write path additionally ends in `_validate_layer`, which refuses the same policy with
the coarser `layer-follow-up-not-allowed` token — so removing this leg loses the **message**, not the refusal.

**Substitute evidence — a direct A/B on `validate_policy_for_write`** (same head, fresh bytecode per arm):

```
ARM A (leg neutralized): 'layer-follow-up-not-allowed'
ARM B (leg restored):    "rules[0].followUp: not allowed for disposition 'fix-as-suggested'"
```

**Cases it does not discriminate:** the refusal itself — the write path refuses under either arm; only
the operator-facing message differs. **Restore.** Inverse edit. **Restore receipt:** porcelain empty.
**Owed (disclosure D-2):** a committed test asserting `"rules[0].followUp"` through
`validate_policy_for_write` for a not-allowed disposition. Carried to 2e-b; **unadjudicated**.

### I4 — `validate_policy_for_write`, the malformed leg

**Guarded element.** the `if fault is not None: … return "rules[%d].followUp: %s"` leg.
**Axis:** same, for a malformed follow-up — and here a committed detector **does** discriminate,
because `test_e3`/`test_e3b` assert the `"rules[0].followUp"` substring.

**Neutralization.** → `if False:`.

**Detectors.** `test_e3_follow_up_item_less_refused_at_load_and_write`, `test_e3b_follow_up_present_empty_item_refused_at_load_and_write`.

**Red** (EXIT=1) — and the red is precisely the coarse-token fall-through described in I3, which is
what makes it on-axis:

```
        refusal = RGP.validate_policy_for_write(policy)
>       assert refusal is not None and "rules[0].followUp" in refusal
E       AssertionError: assert ('layer-follow-up-malformed' is not None and 'rules[0].followUp' in 'layer-follow-up-malformed')
2 failed in 0.24s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

---

## J — staged-id resolution

### J1 — duplicate staged id

**Guarded element.** `round_driver._staged_by_id_map`, `if staged_id in by_id: return None, "… duplicate staged id …"`.
**Axis:** two staged findings sharing one id make **every** id lookup unresolvable, not just theirs.

**Neutralization.** → `if False:`.

**Detector.** `test_layer2e_staged_ids_1272.py::test_e3_duplicate_staged_id_refused`.

**Red** (EXIT=1):

```
        by_id, fault = RD._staged_by_id_map(staged)
>       assert by_id is None
E       AssertionError: assert {'dup': {'file': 'a.py', 'id': 'dup', 'line': 1, 'severity': 'Important', ...}} is None
1 failed in 0.65s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

### J2 — missing staged id

**Guarded element.** `_staged_id_resolution_fault`, `if staged_id is None: return "… missing staged id"`.
**Axis:** a verdict carrying no id is named as *missing*, not as *unknown* — the two causes are distinct.

**Neutralization.** → `if False:`.

**Detector.** `test_e1_verifier_drop_missing_staged_id_refused_at_fold`.

**Red** (EXIT=1) — the red lands on the **cause string**, which is exactly the axis:

```
>       assert "missing staged id" in state["certification"]["reason"]
E       AssertionError: assert 'missing staged id' in 'staged-id-unresolvable: staged id None maps to no entry'
1 failed in 0.66s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

### J3 — maps to no entry

**Guarded element.** `_staged_id_resolution_fault`, `if finding is None: return "… maps to no entry"`.
**Axis:** an id that resolves to nothing is named as *unknown*, distinct from *unkeyed*.

**Neutralization.** → `if False:`.

**Detectors.** `test_e2_verifier_drop_unknown_id_refused_at_submit` (red);
`test_e6_synthesis_one_bad_member_refused_at_submit` and `test_e10_synthesis_non_string_member_refused_at_submit`
stay green (they fall through to the next leg, which is the discrimination).

**Red** (EXIT=1):

```
>       assert "maps to no entry" in out["reason"]
E       assert 'maps to no entry' in "staged-id-unresolvable: staged id 'v99' has no derivable finding key"
1 failed, 2 passed in 6.70s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

### J4 — no derivable finding key

**Guarded element.** `_staged_id_resolution_fault`, `if not _finding_identity_key(finding): return "… has no derivable finding key"`.
**Axis:** a staged finding whose identity cannot be derived is refused rather than silently skipped.

**Neutralization.** → `if False:`.

**Detectors.** `test_e4_staged_finding_no_derivable_key_refused` (red);
`test_e5_synthesis_merge_kept_id_unresolvable_refused_at_submit` stays green.

**Red** (EXIT=1):

```
        out = RD.cmd_submit(…, {"verdicts": [{"id": "v0", "verdict": "REFUTED", "reason": "bad key"}]})
>       assert out["ok"] is False
E       assert True is False
1 failed, 1 passed in 4.64s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

### J5 — `verifier_drop_staged_id_fault`'s submit wiring

**Guarded element.** `_cmd_submit_prepare`, the `P_VERIFIERS` block's
`fault = verifier_drop_staged_id_fault(state, artifact)` / `if fault:`.
**Axis:** an unresolvable verifier drop is refused at the chokepoint, before the state file moves.

**Neutralization.** `if fault:` → `if False:`.

**Detectors.** `test_e2_verifier_drop_unknown_id_refused_at_submit`, `test_e4_staged_finding_no_derivable_key_refused`.

**Red** (EXIT=1):

```
>       assert out["ok"] is False
E       assert True is False
2 failed in 4.56s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

### J6 — `synthesis_staged_id_fault`'s submit wiring

**Guarded element.** `_cmd_submit_prepare`, the `P_SYNTHESIS` block's
`fault = synthesis_staged_id_fault(state, artifact)` / `if fault:`.
**Axis:** an unresolvable merge member, kept id, grouping member or author-justified drop is refused
before fold.

**Neutralization.** `if fault:` → `if False:`.

**Detectors.** `test_e5_synthesis_merge_kept_id_unresolvable_refused_at_submit`,
`test_e6_synthesis_one_bad_member_refused_at_submit`, `test_e7_duplicate_member_id_refused_at_submit`,
`test_e7b_grouping_omits_survivor_refused_at_submit` (four red);
`test_e10_synthesis_non_string_member_refused_at_submit` stays green (a non-string member is refused by
the payload contract upstream — noted, not claimed as a red).

**Red** (EXIT=1):

```
>       assert out["ok"] is False
E       assert True is False
4 failed, 1 passed in 11.41s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

### J7 — `_fold_verifiers` parks on an unresolvable drop id

**Guarded element.** `_fold_verifiers`, `staged_finding, fault = _resolve_staged_finding(staged, d.get("id"))` / `if fault:` → `_park_cannot_certify`.
**Axis:** at fold, an unresolvable drop **parks the session at terminal**; it never advances silently.

**Neutralization.** `if fault:` → `if False:`.

**Detector.** `test_e1_verifier_drop_missing_staged_id_refused_at_fold`.

**Red** (EXIT=1):

```
>       assert state["step"] == RD.P_TERMINAL
E       AssertionError: assert 'dispatch-synthesis' == 'terminal'
1 failed in 0.66s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

### J8 — `_fold_synthesis` parks on an unresolvable author-justified drop id

**Guarded element.** `_fold_synthesis`, the author-justification loop's
`staged_finding, fault = _resolve_staged_finding(verified, d.get("id"))` / `if fault:` → `_park_cannot_certify`.
**Axis:** an author-justified drop whose id does not resolve parks rather than dropping a finding
without a recorded disposition.

**Neutralization.** `if fault:` → `if False:`.

**Detector.** `test_author_justified_drop_unresolvable_id_parks_at_fold`.

**Red** (EXIT=1):

```
>       assert RD.STAGED_ID_UNRESOLVABLE_CAUSE in state["certification"]["reason"]
E       KeyError: 'reason'
1 failed in 0.70s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

---

## K — the synthesis payload contract

### K1 — non-dict artifact

**Guarded element.** `round_driver.synthesis_results_fault`, `if not isinstance(artifact, dict): return "synthesis artifact is %s, …"`.
**Axis:** a non-object synthesis artifact is named **as a type**, before any staged-id lookup.

**Neutralization.** → `if False:`.

**Detector.** `test_e9_synthesis_non_object_artifact_refused_at_submit`.

**Red** (EXIT=1) — on the message axis, since the next leg still refuses:

```
>       assert "synthesis artifact is list" in out["reason"]
E       assert 'synthesis artifact is list' in 'synthesis artifact carries no `grouping` key; expected {"grouping": ...}; resubmit the same phase/attempt/state-hash with a corrected artifact'
1 failed in 2.78s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

### K2 — the missing-`grouping`-key leg

**Guarded element.** `synthesis_results_fault`, `if "grouping" not in artifact: return "synthesis artifact carries no \`grouping\` key; …"`.
**Axis:** an **absent** `grouping` key is refused (while `grouping: null` is a real answer and folds).

**Neutralization.** → `if False:`.

**Detector attempted.** `test_e8b_missing_grouping_key_refused_at_submit` — **NOT RED** (EXIT=0,
`1 passed in 2.77s`): `payload_contracts.payload_fault` below it refuses the same artifact with
`` `grouping` is missing ``, so the refusal survives and only the message changes.

**Substitute evidence — a direct A/B on `synthesis_results_fault`** (same head, fresh bytecode per arm):

```
ARM A (leg neutralized):  no grouping key -> '`grouping` is missing'
ARM B (leg restored):     no grouping key -> 'synthesis artifact carries no `grouping` key; expected {"grouping": ...}; resubmit the same phase/attempt/state-hash with a corrected artifact'
both arms:                non-dict        -> 'synthesis artifact is list, not a grouping object; …'
both arms:                grouping null   -> None
```

The third line is the **fail-direction control**: `grouping: null` folds under both arms, which is the
answer the layer's prose and the gate agree on.
**Cases it does not discriminate:** the refusal itself — the submit chokepoint refuses under either arm.
**Restore.** Inverse edit. **Restore receipt:** porcelain empty.
**Owed (disclosure D-6):** a committed test asserting the *specific* message for an absent key.
Carried to 2e-b; **unadjudicated**.

> **Standing limitation, carried up.** One of the confirming round's **four CONFIRMED Importants** is
> that the synthesis prose and `test_grouping_absent_null_empty_falls_open_nonempty_incomplete_refused`
> read an **absent** `grouping` as carrying no coverage obligation, while `synthesis_results_fault`
> hard-refuses it. The advisor's fail-direction call is **fail-closed wins** — the gate keeps refusing,
> and the prose and the test are corrected in **2e-b**. This record's receipts describe the **code as
> shipped**, which is the side that stays.

### K3 — `synthesis_results_fault`'s submit wiring

**Guarded element.** `_cmd_submit_prepare`, the `P_SYNTHESIS` block's `fault = synthesis_results_fault(artifact)` / `if fault:`.
**Axis:** the payload contract is enforced at the chokepoint.

**Neutralization.** `if fault:` → `if False:`.

**Detectors.** `test_e9_synthesis_non_object_artifact_refused_at_submit`, `test_e8b_missing_grouping_key_refused_at_submit`.

**Red** (EXIT=1):

```
        out = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], {})
>       assert out["ok"] is False
E       assert True is False
2 failed in 5.18s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

---

## L — grouping coverage

### L1 — `duplicate_member`

**Guarded element.** `verification.grouping_coverage_fault`, `if member_id in seen: return {"kind": "duplicate_member", …}`.
**Axis:** a member id repeated inside a grouping is named **with the offending id**, not folded into a
generic count mismatch.

**Neutralization.** → `if False:`.

**Detector.** `test_e7_duplicate_member_id_refused_at_submit`.

**Red** (EXIT=1) — the red is exactly the loss of the id, which is the axis:

```
>       assert good_id in out["reason"]
E       AssertionError: assert 'v0' in 'staged-id-unresolvable: grouping does not cover every survivor exactly once'
1 failed in 2.82s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

### L2 — the exact-once rule

**Guarded element.** `verification._coverage_fault_from_seen`, `if seen_set == expected and len(seen) == len(expected): return None`.
**Axis:** a non-empty grouping must cover every id-bearing survivor **exactly once**. This is the shared
helper both `grouping_coverage_fault` and `_valid_grouping` now read, so one neutralization covers both callers.

**Neutralization.** the condition → `if True:` (fall open).

**Detectors.** `test_e7b_grouping_omits_survivor_refused_at_submit` and
`test_grouping_absent_null_empty_falls_open_nonempty_incomplete_refused`.

**Red** (EXIT=1):

```
        fault = RD.synthesis_staged_id_fault(state, incomplete)
>       assert fault is not None
E       assert None is not None
2 failed in 2.80s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

### L3 — an empty or absent grouping carries no obligation

**Guarded element.** `grouping_coverage_fault`, `if not isinstance(grouping, list) or not grouping: return None`.
**Axis:** "no merging proposed" is a real answer — it is **not** a coverage failure. (The fail-direction
control for L2.)

**Neutralization.** → `if False:`.

**Detectors.** `test_e8_empty_grouping_no_fault` (the `empty-list` parameter) and
`test_grouping_absent_null_empty_falls_open_nonempty_incomplete_refused`.

**Red** (EXIT=1):

```
>           assert RD.synthesis_staged_id_fault(state, artifact) is None
E           assert "staged-id-unresolvable: grouping omits staged id 'v0'" is None
FAILED …::test_e8_empty_grouping_no_fault[empty-list]
2 failed, 1 passed in 4.92s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

---

## M — the ceiling gate (walk-5 ruling 33 = a)

### M1 — reuse requires a recorded `pass`

**Guarded element.** `_try_reuse_ceiling_verify_gate`, `if session_contract.verify_result_for_head(state, post_fix_head) != "pass": return False`.
**Axis:** the gate is reused **only** on a recorded pass for that exact post-fix head; every other case
runs the gate (fail closed toward running it).

**Neutralization.** → `if False:`.

**Detectors.** `test_t3b_ceiling_gate_reuse_requires_pass`, `test_t3_ceiling_gate_fail_on_post_fix_head_halts`,
`test_t3_ceiling_gate_runs_on_post_fix_head_after_prior_verify`.

**Red** (EXIT=1):

```
E       assert (True and 'terminal' == 'run-verify'
E         - run-verify
E         + terminal)
3 failed in 9.25s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

### M2 — the reuse call in `_enter_post_fix`

**Guarded element.** `_enter_post_fix`, `if _try_reuse_ceiling_verify_gate(state, config, session_dir): return`.
**Axis:** when the round's gate already passed on this post-fix head, the ceiling round reuses it
instead of running a second identical gate.

**Neutralization.** → `if False and _try_reuse_ceiling_verify_gate(…):`.

**Detectors.** `test_t3_ceiling_gate_reused_when_prior_verify_on_same_head` (red);
`test_t3b_ceiling_gate_reuse_taken_on_pass` stays green (it calls the helper directly).

**Red** (EXIT=1):

```
>       assert n3["action"] == RD.P_TERMINAL, n3
E       assert 'run-verify' == 'terminal'
1 failed, 1 passed in 4.80s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

### M3 — the deleted `ceilingGateSkipped` branch

**Guarded element.** the **absence** of the old `ceilingGateSkipped` early-advance branch in
`_enter_post_fix` (walk-5 ruling 33 = a: the ceiling gate always runs on the post-fix head).
**Axis:** a round whose earlier gate ran on a **different** head still runs the gate on the post-fix
head — it never advances past the ceiling on a stale pass.

**Neutralization.** the deleted branch **reinstated verbatim** (the minimal neutralization of a deletion),
guarded on `state["rounds"][str(round)]["verifyResult"] is not None` and calling `_advance_round`.

**Detectors.** `test_t3_ceiling_gate_runs_on_post_fix_head_after_prior_verify`,
`test_t3_ceiling_gate_fail_on_post_fix_head_halts`.

**Red** (EXIT=1):

```
E       assert (True and 'terminal' == 'run-verify'
E         - run-verify
E         + terminal)
2 failed in 9.11s
```

**Restore.** Inverse edit (the reinstated block removed in full). **Restore receipt:** porcelain empty.
**Green** (EXIT=0): in the `98 passed` sweep.

### M4 — `_fold_fixer` threads `session_dir`

**Guarded element.** `_fold_fixer`, `_enter_post_fix(state, config, session_dir=session_dir)`.
**Axis:** the ceiling logic resolves the post-fix head from the **session directory**, not only from the
config fallback.

**Neutralization.** → `_enter_post_fix(state, config)`.

**Detector.** `test_t3_ceiling_gate_runs_when_post_fix_head_unresolvable`.

**Red** (EXIT=1):

```
>       assert n3["ok"] and n3["phase"] == RD.P_VERIFY, n3
E       assert (True and 'terminal' == 'run-verify'
E         - run-verify
E         + terminal)
1 failed, 28 passed in 87.33s
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green** (EXIT=0): in the `98 passed` sweep.

### M5 — the `head_err or not post_fix_head` operand

**Guarded element.** `_try_reuse_ceiling_verify_gate`, `if head_err or not post_fix_head: return False`.

**Proof status: UNPROVEN — disclosure D-7, "unprovable as placed".**
**Neutralization applied:** → `if False:`. **Detector attempted:**
`test_t3_ceiling_gate_runs_when_post_fix_head_unresolvable` — **NOT RED** (EXIT=0, `1 passed in 4.87s`).
**What makes it unprovable:** when the head does not resolve, `post_fix_head` is falsy and the very next
guard — `verify_result_for_head(state, <falsy>) != "pass"` — returns `False` on the same input, so the
strict operand and its absence behave identically at that site. **What would make it provable:**
restructuring so the two operands cannot both normalize to `return False` (for instance, distinguishing
the outcomes in the recorded round, or recording a reason). **Plain statement: this operand's protection
is unverified; the load-bearing leg is M1, which is proven.** It is a fail-closed redundancy, not a hole.
**Unadjudicated.**

---

## N1 — the surviving relocation non-object guard, now provable alone

**Guarded element.** `round_driver._relocation_after_emission`, the **first** loop's
`if not isinstance(event, dict): return _RELOCATION_EVIDENCE_INDETERMINATE` (the `G8b` of layer 2i-b's record).
**Axis:** a non-object journal row makes relocation evidence **indeterminate**, so every fence caller refuses.

**Why this element is in layer 2e's record.** Layer 2e's ride-along removed the **duplicate**
(`_relocation_lookup`'s pre-scan, 2i-b's `G8a`) and the **unreachable** one (the second loop's check,
2i-b's `G8c`). On PR #1380's record all three were **NOT RED alone** — a redundant pair that only bit
when neutralized together. The owed receipt for this lane is that the surviving guard now bites **by itself**.

**Neutralization.** `return _RELOCATION_EVIDENCE_INDETERMINATE` → `continue`.

**Detectors.** `test_round_driver_re_emit.py::test_relocation_after_emission_predicate` and
`::test_relocation_evidence_faults_refuse_all_callers` (all parameters).

**Red** (EXIT=1) — **20 of 41 red**, where 2i-b's record recorded **0**:

```
journal = [{'appendId': …, 'cmd': 'next', 'fault': 'caller-error', …}, …, None]
    def _re_emit_recorded_slots(journal, rnd, phase, attempt):
        for event in journal:
>           if event.get("outcome") != "recorded":
E           AttributeError: 'NoneType' object has no attribute 'get'
…
FAILED …[record-result-null] … [advance-string]
20 failed, 21 passed in 68.64s
```

**Axis check — the red, read honestly.** The failure surfaces as an `AttributeError` inside
`_re_emit_recorded_slots`, **not** as the `relocation-evidence-indeterminate` refusal. That is still on
the guarded axis — with the guard removed, the callers stop refusing — and it additionally shows what the
guard is load-bearing **for**: it is the only thing standing between a non-object journal row and
unguarded `.get` calls further down the `re-emit` path. **Recorded as an observation, not a claim of a
refusal-shaped red.**

**Also recorded:** `test_relocation_after_emission_predicate` run **alone** under the same neutralization
was **NOT RED** (EXIT=0, `1 passed in 0.30s`) — the unit-level predicate does not reach the non-object
row. The `faults` test is the detector that bites.

**Restore.** Inverse edit. **Restore receipt:** porcelain empty.
**Green** (EXIT=0): `41 passed in 67.09s`.

---

## O1 — `verified_head_for_round` / `verify_result_for_round`

**Guarded elements.** `session_contract.verified_head_for_round` and `session_contract.verify_result_for_round`,
each with two fail-closed legs (missing round record; `verifiedHead` absent or not a non-empty string).

**Proof status: UNPROVEN — disclosure D-8, and the cause is that they have no consumer and no test.**
A symbol census over `plugins/superheroes/lib/` and `plugins/superheroes/skills/` returns **no reference
to either name outside `session_contract.py` itself** — they are exported in `__all__` and read by nothing.
No neutralization can be observed, because there is no path to the guard.
**What would make them provable:** a consumer, or removal.
**Plain statement: the fail-closed protection these two helpers claim is unverified.**
Carried to 2e-b as a follow-up; **unadjudicated**.

---

## Adjudication

Per `rubric/bite-proof.md` § *Who owes what*: this lane's orchestrator both produced and re-ran every
proof, so **no disclosure in this record has been accepted by an independent party**. All eight
disclosures — **D-1** (`resolve_judgment`'s unconsumed carry), **D-2** (the write-path allow-list
message), **D-3** (the `!= "skip"` exclusion half), **D-4** (the stall choice operand), **D-5**
(`_fold_judgment`'s backstop branches), **D-6** (the missing-`grouping`-key message), **D-7** (the
`head_err` operand) and **D-8** (the two unconsumed round helpers) — travel to the **next independent
reader of this record**: the advisor's vet. **Until then they are unadjudicated, which this record states
plainly rather than recording them as accepted.**

**None of the eight is a vacuity-trap defect.** Each is either an *unprovable as placed* or an
*unreachable through this entry point* shape with the disclosure this file requires, or an unconsumed
addition whose protection claim is simply stated as unverified. Where a committed fixture is the reason a
probe stayed green (D-3, D-4, D-6), the cure named in the rubric is **fixing the fixture** — carried to
layer **2e-b**, because the r3 adoption lane lands no code.

## Capture handling

Raw captures were written to session-scoped scratch **outside the repository**, one file per run, each
opening with its own `# ran: pytest <node ids>` line. Decisive lines are quoted above; nothing was
redacted, because the captures hold only temporary paths and test fixtures. The scratch files are working
artifacts and are removed when this verification closes — the quotes above are the durable receipt.
