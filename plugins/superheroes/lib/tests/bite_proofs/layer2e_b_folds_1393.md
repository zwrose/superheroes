# Bite-proof record — the clamp-exact collision, the write-path message, and the three fixture fixes

Every guarded element below was neutralized through the host's edit action on a committed head,
the named detector run, the edit reversed by the inverse edit, `git status --porcelain` read empty,
and the detector re-run green. Interpreter `/usr/bin/python3 -B -X pycache_prefix=<scratch>`
(3.9.6), serial runs, `-p no:cacheprovider`. Receipts redacted of nothing (none held secrets).

| id | guarded element | file | status |
|---|---|---|---|
| **P1** | `legacy_key_collision` — the same-key claimant clause | `session_contract.py` | proven |
| ~~P2~~ | `_auditor_vendor` — the runner-backed filter | `round_driver.py` | **built, proven, then removed** — see below |
| ~~P3~~ | `_enter_delta_round` — the compose refusal | `round_driver.py` | **built, proven, then removed** — see below |
| **P4** | `synthesis_results_fault` — the missing-`grouping`-key leg | `round_driver.py` | proven |
| **P5** | `validate_policy_for_write` — the follow-up allow-list leg | `review_gate_policy.py` | proven |
| **P6** | `judgment_follow_up_fault` — the `!= "skip"` exclusion half | `round_driver.py` | proven |
| **P7** | `stall_follow_up_fault` — the choice operand | `round_driver.py` | proven |

---

### P1 — the same-key claimant clause

**Guarded element.** `session_contract.legacy_key_collision`, `if minted in identity_keys or len(claimants[bare]) > 1:`.
**Axis:** a legacy bare-keyed row beside a distinct finding that claims the same bare key (the
clamp-exact short title) is refused, never joined.
**Neutralization.** → `if minted in identity_keys:` (the clause removed; the e1–e4 clause kept).
**Detectors.** `test_layer2e_b_folds_1393.py`: `test_clamp_exact_pair_collides_in_helper`,
`test_clamp_exact_pair_refused_through_certification_ledger_owner`,
`test_clamp_exact_pair_refused_through_certification_legacy_branch` — expected red;
`test_same_finding_duplicate_under_bare_key_admitted` — expected green (the control).

**Red** (EXIT=1):

```
>       assert SC.legacy_key_collision([_legacy_row(long, bare), dict(short)]) == (bare, minted)
E       AssertionError: assert None == ('f.py::word word … word@L5#6ea6371d183c')
>       assert by_key == {}
E       AssertionError: assert {'f.py::word ...ord@L5', ...}} == {}
>       assert by_key == {}
E       AssertionError: assert {'f.py::word ...ord word...'}} == {}
3 failed, 1 passed, 5 deselected in 2.49s
```

The joined `by_key` row carries `'disposition': 'refuted'` — the stale disposition this guards.
**Restore.** Inverse edit; porcelain empty. **Green:** `4 passed, 5 deselected in 1.88s`.

### P4 — the missing-`grouping`-key leg (closes D-6)

**Guarded element.** `round_driver.synthesis_results_fault`, `if "grouping" not in artifact:`.
**Axis:** an artifact with no `grouping` key is refused with the leg's own message, not only by the
payload contract below it.
**Neutralization.** → `if False:`.
**Detector.** `test_layer2e_staged_ids_1272.py::test_e8b_missing_grouping_key_refused_at_submit`,
now asserting the specific message (it previously asserted only the substring `grouping`, which the
contract's fallback message also carries — the fixture could not tell the leg apart).

**Red** (EXIT=1):

```
>       assert "synthesis artifact carries no `grouping` key" in out["reason"]
E       AssertionError: assert 'synthesis artifact carries no `grouping` key' in '`grouping` is missing'
1 failed, 14 deselected in 25.86s
```

The refusal survives under the neutralization (fail-closed below it); the message is what this leg owns.
**Restore.** Inverse edit; porcelain empty. **Green:** `1 passed, 14 deselected in 29.11s`.

### P5 — the write-path allow-list leg (closes D-2)

**Guarded element.** `review_gate_policy.validate_policy_for_write`, `if not follow_up_allowed:`.
**Axis:** a `followUp` on a rule that may not carry one is refused with the rule named.
**Neutralization.** → `if False:`.
**Detector.** `test_layer2e_b_folds_1393.py::test_write_path_names_follow_up_not_allowed` (new).

**Red** (EXIT=1):

```
E       assert 'layer-follow-up-not-allowed' == "rules[0].fol...as-suggested'"
E         - rules[0].followUp: not allowed for disposition 'fix-as-suggested'
E         + layer-follow-up-not-allowed
1 failed, 8 deselected in 2.44s
```

**Restore.** Inverse edit; porcelain empty. **Green:** `1 passed, 8 deselected in 3.49s`.

### P6 — the `!= "skip"` exclusion half (closes D-3)

**Guarded element.** `round_driver.judgment_follow_up_fault`, the `or disp.get("disposition") != "skip"` operand.
**Axis:** a non-skip disposition's stray `followUp` is not graded.
**Neutralization.** the operand removed → `if not isinstance(disp, dict):` — the exact neutralization
that stayed green under the old fixture.
**Detector.** `test_layer2e_follow_up_1272.py::test_e6_judgment_fix_stray_follow_up_not_checked`,
fixture now carrying a `reason`, so the reasonless-skip `continue` can no longer absorb the row.

**Red** (EXIT=1):

```
>       assert out["ok"] is True, out
E       AssertionError: {'ok': False, 'reason': 'follow-up-malformed: f.py::widen the api@L1: out-of-scope follow-up lacks revisit trigger'}
1 failed, 21 deselected in 14.35s
```

**Restore.** Inverse edit; porcelain empty. **Green:** `1 passed, 21 deselected in 15.32s`.

### P7 — the stall choice operand (closes D-4)

**Guarded element.** `round_driver.stall_follow_up_fault`, `if artifact.get("choice") != ACCEPT_RISK_CHOICE: return None`.
**Axis:** only `accept-the-disclosed-risk` has its `followUp` graded; `hold` does not.
**Neutralization.** → `if False:`.
**Detector.** `test_layer2e_follow_up_1272.py::test_e8_stall_hold_with_follow_up_not_checked`,
fixture now carrying a malformed `followUp` (no `revisitTrigger`).

**Red** (EXIT=1):

```
>       assert out["ok"] is True, out
E       AssertionError: {'ok': False, 'reason': 'follow-up-malformed: stall: out-of-scope follow-up lacks revisit trigger'}
1 failed, 21 deselected in 15.63s
```

**Restore.** Inverse edit; porcelain empty. **Green:** `1 passed, 21 deselected in 15.53s`.

---

## P2 / P3 — the audit-seat rule: proven, then removed on measured evidence

P2 and P3 guarded a compose-time rule (durable-record path → only external-engine auditors; none live
→ park `audit-seat-native-on-discharge-phase`). Both went red with their named tokens
(`['claude'] == ['codex']`; `'dispatch-audits' == 'terminal'`) and green on restore — the guards bit.
The rule itself was then run against the 74 lib test files that touch audits, fixers or `advance`
at commit `b89cfd4b`: **58 failed, 4662 passed, 14 skipped** (1243 s). 56 of the 58 are durable-path
fixtures (configured vendors `['claude']`) that the new park stopped before `dispatch-audits` (53 read
"reached a terminal before 'dispatch-audits'", the rest `cannot-certify` with the new cause); the
other 2 were the synthesis-order wording, fixed separately. Inspected one of the 56,
`test_seat_provenance_1272.py::test_dispatch_observed_audit_seat_binds_runner_evidence_end_to_end`:
the driver-selected auditor is claude, yet the audit seat is **dispatched on codex through the
runner** and recorded with runner evidence (`executionEvidence.source == "codex"`,
`provenanceSource == "runner-record"`). So the driver-selected auditor *vendor* does not say whether
the seat is native — the
fault it was meant to close is the *dispatch channel* of the audit seat. The code, its tests and its
prose were removed (`round_driver.py` restored byte-identical to the base); these receipts stay as the
evidence for the drop.

## Removals — no detector owed

D-1 (`resolve_judgment`'s `action.dispositions[].followUp`) and D-8 (`verified_head_for_round`,
`verify_result_for_round`, `_round_record`) are deletions, not guards. Census: no reference in
`plugins/`, `eval/`, `.github/` outside the bite-proof records; the one census allowance naming the
D-1 line is removed from `test_disposition_family_home_1272.py`, and
`test_resolved_judgment_action_carries_no_follow_up` pins the resulting `action` shape.

## Adjudication

The session that typed these proofs also verified them, so per `rubric/bite-proof.md` none of the
above is self-accepted as adjudicated; the record carries no disclosures to accept — every element
went red with its named token.
