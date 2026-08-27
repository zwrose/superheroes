# Orchestrator re-verification of every #1131 bite-proof on the FIX5 head

**Head:** `bb925b10` (the WO-FIX5 commit — the owner-authorized fifth patch). **Worktree:**
`issue-1131-9219a6ea3a9d86a2`, branch `fix/1131-record-landing-fidelity-r2`.

**Why this record exists.** `orchestrator_fix3_1131.md` re-verified all ten then-existing guarded
elements on head `9f86190d`. Commit `bb925b10` then changed `plugins/superheroes/lib/round_records.py`
— one of the three surfaces those proofs guard — so **as of this commit every one of those records
was again stale relative to the head**, exactly the way they went stale the first time. A proof
verified on an earlier head is not a receipt for this one. The orchestrator therefore re-ran **all
twelve** guarded elements itself on `bb925b10`: the nine inherited, the FIX3 element, and the two new
FIX5 elements (re-run independently of the implementer that produced them — an implementer's claim is
an input to verification, never a substitute for it).

**Method, per element** (the rubric's): with the **detector unedited**, apply the record's own
neutralization as a targeted, reversible edit through the host's edit action; run the named test
scoped by **exact node id**; capture the failure; revert with the **inverse edit**. No `git checkout`,
`git restore`, `git reset`, or `git stash` was used at any point. The implementer's landed work was
committed as `bb925b10` **before** the first neutralization, so no probe revert could reach
uncommitted work.

**Runner** (every run):
`PYTEST_DEBUG_TEMPROOT=/private/tmp/sh1131-fix5-temproot /usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest <node-id> -q -p no:xdist`

`PYTEST_DEBUG_TEMPROOT` is pinned deliberately: without it every run on this surface ends in the
known bare-basename/tmpdir-GC `source_guard.ShippedSourceWrite` false positive plus 200+ GC warning
lines. Exit status is captured directly, never through a pipe.

## Results — 12 of 12 elements bite

| # | record | guarded element | neutralization | test | red |
|---|---|---|---|---|---|
| 1 | wo_A BP-1 | `_refuse("stale-landing", …)` in `sweep_landing` | → `"stale-landing-neutralized"` | `test_sweep_reports_full_envelope_stray_as_stale_landing` | exit 1, `assert 0 == 1` |
| 2 | wo_A BP-2 | `sweep_landing` stray-loop bare-payload arm | `elif bare_suffix …` → `elif False and bare_suffix …` | `test_sweep_reports_bare_payload_stray_as_stale_landing` | exit 1, `assert 0 == 1` |
| 3 | wo_A BP-3 | tiered `results.sort(…)` key in `sweep_landing` | tier term dropped | `test_sweep_journals_roster_seats_before_stale_landing_refusals` | exit 1, index assertion |
| 4 | wo_B BP-B1 | `if sweep and (supersede or expect_sha256 is not None):` | → `if False and sweep and …` | `test_record_result_sweep_supersede_refuses_by_name` | exit 1, `assert (True is False)` |
| 5 | wo_B BP-B2 | `_record_result_recovery_cmd` raw seat key + explicit `--occurrence` | → `_slot_label(...)`, `--occurrence` dropped | `test_record_result_sweep_supersede_recovery_is_occurrence_safe` | exit 1, `assert '--occurrence 1' in "… --seat 'code-reviewer#1' …"` |
| 6 | wo_C BP-1 | `round-driver.md` names literal `stale-landing` | near-miss `stale-landng` | `test_stale_landing_refusal_token_in_round_driver_doc` | exit 1, FAILED |
| 7 | wo_C BP-2 | `round-driver.md` names literal `sweep-supersede-unsupported` | near-miss `sweep-supersede-unsuppored` | `test_sweep_supersede_unsupported_refusal_token_in_round_driver_doc` | exit 1, FAILED |
| 8 | wo_C BP-3 | `round-driver.md` names literal `unknown-seat` | near-miss `unkown-seat` | `test_unknown_seat_addressed_seat_refusal_token_in_round_driver_doc` | exit 1, FAILED |
| 9 | wo_D | the `supersede` term in `validate_landing`'s store-exists gate | `if exists and not supersede:` → `if exists:` | `test_confirmed_verdict_is_never_downgraded_by_sweep_ingest_silence` | exit 1, `assert (False is True)` |
| 10 | wo_FIX3 | `if landing_err is not None:` in the sweep-supersede recovery loop | → `if False:` | `test_record_result_sweep_recovery_reports_unreadable_landing` (4 params) **plus both FIX5 tests** | exit 1, **6 failed** |
| 11 | wo_FIX5 BP-FIX5-1 | `env_exists = os.path.lexists(env_path)` (`round_records.py:531`) | → `os.path.exists(env_path)` | `test_record_result_sweep_recovery_reports_dangling_envelope_symlink` | exit 1, `assert 0 == 1`; **the sibling bare-payload test stayed green** |
| 12 | wo_FIX5 BP-FIX5-2 | `bare_exists = os.path.lexists(bare_path)` (`round_records.py:532`) | → `os.path.exists(bare_path)` | `test_record_result_sweep_recovery_reports_dangling_bare_payload_symlink` | exit 1, `assert 0 == 1`; **the sibling envelope test stayed green** |

**Elements 6–8 were neutralized together** and their three tests run in one invocation. That is
attributable per element and not a batched bite: the three edits touch three disjoint doc tokens
(each appearing exactly once in the file, verified by `grep -c`), and each test asserts only its own
token, so each red is caused by its own element's neutralization and by nothing else. All three
failed, one per element.

**Elements 11 and 12 were neutralized one at a time**, and each run executed **both** new tests. In
each case exactly the test belonging to the neutralized line went red while its sibling stayed green
(`1 failed, 1 passed`). That is the evidence that the two changed lines are two genuinely distinct
guarded elements and that neither test is standing in as a representative for the other.

**Element 10 also reds both FIX5 tests**, which is expected and not a defect in the proof: the FIX5
tests assert the *truthfulness of the recovery entry*, which the FIX3 branch is what emits. Their
own lines are pinned separately by elements 11 and 12 above, where the attribution is one-to-one.

## Restore receipt

After the last inverse edit, on head `bb925b10`:

```
$ git status --porcelain
(0 bytes — no output)
$ git rev-parse HEAD
bb925b108ee3521fb34600f0422f7bba5b8530d0
```

Green across every surface any proof touched, with all neutralizations reverted:

```
$ PYTEST_DEBUG_TEMPROOT=… /usr/bin/python3 -B -X pycache_prefix=… -m pytest \
    plugins/superheroes/lib/tests/test_round_records.py \
    plugins/superheroes/lib/tests/test_ssot_drift.py \
    plugins/superheroes/lib/tests/test_round_driver_advance.py -q -p no:xdist
434 passed in 281.95s (0:04:41)
EXIT=0
```

## Known limit, carried forward unchanged

The three remaining `os.path.exists` sites in `round_records.py` — `sweep_landing`'s `has_landing`
(line 754) and the two store-path checks (653, 757) — still follow symlinks and are **not** covered by
any proof here. They are outside the owner-set bound of this patch and are disclosed as a residual in
the PR body, not silently.
