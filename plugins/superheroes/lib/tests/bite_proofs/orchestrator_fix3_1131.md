# Orchestrator re-verification of every #1131 bite-proof on the final head

**Head:** `9f86190d` (the FIX3 commit). **Worktree:** `issue-1131-9219a6ea3a9d86a2`, branch
`fix/1131-record-landing-fidelity-r2`.

**Why this record exists.** The four earlier #1131 bite-proof records (`wo_A`, `wo_B`, `wo_C`,
`wo_D`) were recorded and re-verified at head `723c9b48`. Commit `b1c63f22` then changed
`round_driver.py`, `round_records.py`, and `round-driver.md` — the very surfaces those proofs
guard — so as of adoption **every one of those proofs was stale relative to the head**. A proof
verified on an earlier head is not a receipt for this one. The orchestrator therefore re-ran all
nine guarded elements itself on `9f86190d`, plus the new FIX3 element.

**Method, per element** (identical to the rubric's): with the **detector unedited**, apply the
record's own neutralization as a targeted, reversible edit through the host's edit action; run the
named test scoped by **exact node id**; capture the failure; revert with the **inverse edit**. No
`git checkout`, `git restore`, `git reset`, or `git stash` was used at any point. The landed
implementer work was committed (`9f86190d`) **before** the first neutralization, so no probe revert
could reach uncommitted work.

**Runner** (every run):
`PYTEST_DEBUG_TEMPROOT=/private/tmp/sh1131-fix3-temproot /usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest <node-id> -q`

`PYTEST_DEBUG_TEMPROOT` is pinned deliberately: without it every run on this surface ends in the
known bare-basename/tmpdir-GC `source_guard.ShippedSourceWrite` false positive plus 200+ GC warning
lines. With the temproot pinned, all captures below are clean and the exit status is the runner's
own (no pipe — see the pipeline-exit-status trap).

## Results — 10 of 10 elements bite

| # | record | guarded element | neutralization | test | red | green |
|---|---|---|---|---|---|---|
| 1 | wo_A BP-1 | `_refuse("stale-landing", …)` reason string in `sweep_landing` | → `"stale-landing-neutralized"` | `test_sweep_reports_full_envelope_stray_as_stale_landing` | exit 1, `assert 0 == 1` | exit 0 |
| 2 | wo_A BP-2 | `sweep_landing` stray-loop **bare-payload** suffix branch | removed the `elif bare_suffix …` arm | `test_sweep_reports_bare_payload_stray_as_stale_landing` | exit 1, `assert 0 == 1` | exit 0 |
| 3 | wo_A BP-3 | `results.sort(…)` **tier** key in `sweep_landing` | tier term → constant `0` | `test_sweep_journals_roster_seats_before_stale_landing_refusals` | exit 1, `assert 1 < 0` | exit 0 |
| 4 | wo_B BP-B1 | the `if sweep and (supersede or expect_sha256 is not None):` guard | → `if False and sweep and …` | `test_record_result_sweep_supersede_refuses_by_name` | exit 1, `assert (True is False)` | exit 0 |
| 5 | wo_B BP-B2 | `_record_result_recovery_cmd` emits raw seat key + explicit `--occurrence` | → `_slot_label(...)`, `--occurrence` dropped | `test_record_result_sweep_supersede_recovery_is_occurrence_safe` | exit 1, `assert '--occurrence 1' in "… --seat 'code-reviewer#1' --attempt 0 …"` | exit 0 |
| 6 | wo_C BP-1 | `round-driver.md` names the literal `stale-landing` | near-miss `stale-landng` | `test_stale_landing_refusal_token_in_round_driver_doc` | exit 1, FAILED | exit 0 |
| 7 | wo_C BP-2 | `round-driver.md` names the literal `sweep-supersede-unsupported` | near-miss `sweep-supersede-unsuppored` | `test_sweep_supersede_unsupported_refusal_token_in_round_driver_doc` | exit 1, FAILED | exit 0 |
| 8 | wo_C BP-3 | `round-driver.md` names the literal `unknown-seat` | near-miss `unkown-seat` | `test_unknown_seat_addressed_seat_refusal_token_in_round_driver_doc` | exit 1, FAILED | exit 0 |
| 9 | wo_D | the `supersede` term in `validate_landing`'s store-exists gate | `if exists and not supersede:` → `if exists:` | `test_confirmed_verdict_is_never_downgraded_by_sweep_ingest_silence` | exit 1, `assert (False is True)` | exit 0 |
| 10 | wo_FIX3 (new) | the `if landing_err is not None:` branch in the sweep-supersede recovery loop | → `if False:` | `test_record_result_sweep_recovery_reports_unreadable_landing` (4 params) | exit 1, all 4 fail `assert 0 == 1` / `len([])` | exit 0, `4 passed` |

Elements 6–8 were neutralized together and their three tests run in one invocation. That is
attributable per element and not a batched bite: the three edits touch three disjoint doc tokens,
and each test asserts only its own token, so each red is caused by its own element's neutralization
and by nothing else. All three failed, one per element.

## Restore receipt

After the last inverse edit, on head `9f86190d`:

```
$ git status --porcelain
(empty)
$ grep -rn "if False" plugins/superheroes/lib/round_driver.py plugins/superheroes/lib/round_records.py | wc -l
0
```

The empty `git status` is the ground truth here: this tree carries no intentionally-uncommitted
work, so **any** residue from any of the ten neutralizations would show.

## Known limit — carried forward, still unproven

`wo_FIX3_1131.md` records that the new branch's **`landing-missing` carve-out** is not separately
reddened: reddening it would mean deleting that arm and running
`test_record_result_sweep_recovery_omits_recorded_missing_slot_with_no_replacement` (F2), which sits
outside the dispatched order's command budget. F2 is green in the full targeted run below, which is
consistent with the carve-out holding but is **not** a proof that it bites. Disclosed, not claimed.

## Green batch on the final head

```
$ … -m pytest plugins/superheroes/lib/tests/test_round_driver_advance.py \
      plugins/superheroes/lib/tests/test_round_records.py \
      plugins/superheroes/lib/tests/test_ssot_drift.py -q -n auto
432 passed in 39.15s
PYTEST_EXIT=0
```

Four validators on the same head: `validate_marketplace.py`, `validate_hosts.py`,
`validate_skills.py`, `validate_stubs.py` — all exit 0.
