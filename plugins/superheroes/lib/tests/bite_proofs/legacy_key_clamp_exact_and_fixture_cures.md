# Bite-proof record — the clamp-exact legacy-key refusal and three fixture cures

Every entry below was run in a **detached probe worktree** at the head named in the run line, never in
the build tree. Each neutralization was applied as one targeted edit through the host's edit action and
undone by the inverse edit; the restore receipt is the probe tree's `git status --porcelain` after the
green run (empty for every entry). Every run used `/usr/bin/python3 -B -X pycache_prefix=<fresh per
run> -m pytest … -q -p no:cacheprovider`. Raw captures were written to session scratch outside the
repository; the decisive lines are quoted here. Long `f.py::xxx…` keys are elided by pytest itself.
Nothing needed redacting.

## Declared guarded-element set

| # | Guarded element | Axis | Detector(s) |
|---|---|---|---|
| G1 | `session_contract.legacy_key_collision` — the claimant refusal (`if others:`) | a different minted identity claiming a legacy row's bare key refuses | `test_e9`, `test_e10`, `test_e11` |
| G2 | `legacy_key_collision` — the own-identity exclusion (`claimants[bare] - {minted}`) | the legacy row's own minted identity never counts against it | `test_e12` (and `test_e6`) |
| G3 | `legacy_key_collision` — the minted-twin leg (`if minted in identity_keys`) | one finding held under both its bare and minted keys still refuses after the rewrite | `test_e1`–`test_e4`, `test_e8` |
| G4 | `round_certification._certification_findings_by_key` — the ledger-owned branch's refusal return | the ledger-owned read refuses, never joins | `test_e10` |
| G5 | `_certification_findings_by_key` — the legacy branch's refusal return | the legacy read refuses, never joins | `test_e11` |
| G6 | `round_driver.judgment_follow_up_fault` — the `!= "skip"` exclusion half (fixture cure) | a non-skip disposition's `followUp` is never graded | `test_e6_judgment_fix_stray_follow_up_not_checked` |
| G7 | `round_driver.stall_follow_up_fault` — the `ACCEPT_RISK_CHOICE` operand (fixture cure) | a `hold` choice's `followUp` is never graded | `test_e8b_stall_hold_with_malformed_follow_up_not_checked` |
| G8 | `round_driver.synthesis_results_fault` — the missing-`grouping`-key leg (fixture cure) | an absent key is refused **with its own message** at submit | `test_e8b_missing_grouping_key_refused_at_submit`, `test_grouping_absent_refused_null_empty_fall_open_nonempty_incomplete_refused` |
| G9 | `review_gate_policy.validate_policy_for_write` — the allow-list leg (fixture cure) | a `followUp` on a non-skip / non-accept disposition is refused at write by name | `test_e4b_follow_up_not_allowed_refused_at_calibration_write` (both params) |

Tests G1–G5 live in `test_layer2e_ledger_evidence_1272.py`; G6–G7 in `test_layer2e_follow_up_1272.py`;
G8 in `test_layer2e_staged_ids_1272.py`; G9 in `test_layer2e_gate_policy_follow_up_1272.py`.

**Proof head:** `46642eab` (every entry). Re-run at the final head is recorded under *Final-head re-run*.

---

## G1 — the claimant refusal

**Neutralization.** `if others:` → `if False:`.
**Red** (EXIT=1, `3 failed in 0.20s`):

```
E       AssertionError: assert None == LegacyKeyCollision(bare_key='f.py::xxx…@L5', …)      # test_e9
>       assert by_key == {}                                                                  # test_e10
E       AssertionError: assert {'f.py::xxx…ortant', ...}} == {}
E         {'f.py::xxx…@L5': {'disposition': 'fixed', 'dispositionRou…                        # stale disposition joined
E       AssertionError: assert {'f.py::xxx…ortant', ...}} == {}                               # test_e11
```

The red is on the axis: `test_e10`'s by-key map carries the legacy row's `disposition: fixed` joined onto
the short-title finding, the corruption this refusal exists to prevent.
**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green:** `25 passed in 0.23s`, EXIT=0.

## G2 — the own-identity exclusion

**Neutralization.** `sorted(claimants[bare] - {minted})` → `sorted(claimants[bare])`.
**Red** (EXIT=1, `2 failed, 23 passed in 0.24s`):

```
>       assert SC.legacy_key_collision([
E       AssertionError: assert LegacyKeyCollision(bare_key='f.py::xxx…', …) is None           # test_e12
>       assert refusal is None
E       assert {'artifact': 'loop-state.json', 'bindingFailure': 'disposition-ledger-legacy-key-collision', …   # test_e6
FAILED …::test_e6_bare_keyed_row_alone_no_refusal
FAILED …::test_e12_legacy_row_beside_its_own_bare_keyed_copy_still_joins
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green:** `25 passed in 0.22s`, EXIT=0.

## G3 — the minted-twin leg survives the rewrite

**Neutralization.** `if minted in identity_keys:` → `if False:`.
**Red** (EXIT=1, `5 failed, 20 passed in 0.23s`): `test_e1`, `test_e2`, `test_e3`, `test_e4` each
`AssertionError: assert {…} == {}` (the twin joined), and `test_e8`
`AssertionError: assert None == LegacyKeyCollision(…)`. The new claimant leg does not absorb this case.
**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green:** `25 passed in 0.22s`, EXIT=0.

## G4 — ledger-owned branch wiring

**Neutralization.** in the ledger-owned branch, `if collision_refusal is not None:` → `if False:`.
**Red** (EXIT=1, `1 failed, 1 passed in 0.20s`): `FAILED …::test_e10_…` with
`AssertionError: assert {'f.py::xxx…@L5', ...}} == {}`; `test_e11` (other branch) stays green.
**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green:** `25 passed in 0.22s`, EXIT=0.

## G5 — legacy branch wiring

**Neutralization.** in the legacy branch, `if collision_refusal is not None:` → `if False:`.
**Red** (EXIT=1, `1 failed, 1 passed in 0.19s`): `FAILED …::test_e11_…` with
`AssertionError: assert {'f.py::xxx…ortant', ...}} == {}`; `test_e10` stays green.
**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green:** `25 passed in 0.22s`, EXIT=0.

## G6 — the skip-only scope, now discriminated

**The cure.** `test_e6`'s non-skip row gains `"reason": "fix it now"`, so the reasonless-row pass-through
one line below can no longer absorb the neutralization.
**Neutralization.** `if not isinstance(disp, dict) or disp.get("disposition") != "skip":` →
`if not isinstance(disp, dict):`.
**Red** (EXIT=1, `1 failed in 0.79s`) — the exact expected token `follow-up-malformed`:

```
E       AssertionError: {'ok': False, 'reason': 'follow-up-malformed: f.py::widen the api@L1: out-of-scope follow-up lacks revisit trigger'}
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty (confirmed by the next entry's one-file
diff). **Green:** `23 passed in 0.82s`, EXIT=0 (the whole follow-up test file).

## G7 — the stall choice operand, now discriminated

**The cure.** New `test_e8b_…`: a `hold` whose `followUp` is malformed (`revisitTrigger: "documented"`)
must still fold `held`.
**Neutralization.** `if artifact.get("choice") != ACCEPT_RISK_CHOICE:` → `if False:`.
**Red** (EXIT=1, `1 failed, 1 passed in 0.84s`) — exact token `follow-up-malformed`:

```
E       AssertionError: {'ok': False, 'reason': 'follow-up-malformed: stall: revisit trigger must not be the word documented'}
FAILED …::test_e8b_stall_hold_with_malformed_follow_up_not_checked
```

The pre-existing `test_e8` (well-formed `followUp` on `hold`) stayed **green** under the same
neutralization — the fixture gap this entry cures, re-observed.
**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green:** `23 passed in 0.82s`, EXIT=0.

## G8 — the missing-key message, now discriminated

**The cure.** `test_e8b_missing_grouping_key_refused_at_submit` asserts the exact message
(`reason == "synthesis artifact carries no \`grouping\` key; …"`), and the renamed grouping test asserts
`synthesis_results_fault({})` equals it.
**Neutralization.** `if "grouping" not in artifact:` → `if False:`.
**Red** (EXIT=1, `2 failed in 3.32s`) — the absent key is still refused, but by the generic contract:

```
E         - synthesis artifact carries no `grouping` key; expected {"grouping": ...}; resubmit the same phase/attempt/state-hash with a corrected artifact
E         + `grouping` is missing
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green:** `28 passed in 33.39s`, EXIT=0
(this file plus G9's file).

## G9 — the write-path allow-list, now discriminated

**The cure.** New parametrized `test_e4b_…` drives `validate_policy_for_write` with a well-formed
`followUp` on judgment `fix-as-suggested` and on stall `hold`, asserting the exact refusal string.
**Neutralization.** `if not follow_up_allowed:` → `if False:`.
**Red** (EXIT=1, `2 failed in 0.27s`) — the load-path token leaks through instead:

```
E         - rules[0].followUp: not allowed for disposition 'fix-as-suggested'
E         + layer-follow-up-not-allowed
E         - rules[0].followUp: not allowed for disposition 'hold'
E         + layer-follow-up-not-allowed
```

**Restore.** Inverse edit. **Restore receipt:** porcelain empty. **Green:** `28 passed in 33.39s`, EXIT=0.

---

## Removals (no detector left to prove)

- `review_gate_policy.resolve_judgment` no longer copies a rule's `followUp` into
  `action.dispositions[]`. The driver's judgment consumer reads `matches[].rule`, which still carries it.
- `session_contract.verified_head_for_round`, `verify_result_for_round` and their private
  `_round_record` are removed. The sweeps for both names and the `_round_record(` call shape found no
  remaining reference outside these records.

## Final-head re-run

Recorded in the pull request's build record against the final head (G1–G9, same commands, fresh
bytecode prefix per run).
