# Bite-proof record — C13 layer 2d, round economy (issue #1272, PR #1344)

Head under proof: **`9e65db72`** (the final head at proof time). Probe checkout: a detached worktree of that head, no live reader; every neutralization a targeted `Edit`, every restore its inverse `Edit`; `git status --porcelain` clean after every pair (checked, last check printed `TREE CLEAN`). Runner: `/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-probe -m pytest <node> -q -p no:cacheprovider`, from `plugins/superheroes`. Each line below is the receipt's own last line plus its first `E ` line, verbatim from the run log (`bite-proofs.log`).

Baseline on the final head, before any probe:

```
baseline-all | exit 0 | 33 passed in 157.42s (0:02:37)
```

| # | Guarded element | Neutralization (targeted edit) | Red | Green |
|---|---|---|---|---|
| 1 | The `verify` slot advertised on the `dispatch-audits` payload (`_advance`, P_AUDITS arm) | `if False and state.get("_verifyThen") == VERIFY_THEN_POST_AUDITS:` | `exit 1 \| 1 failed in 13.68s \| E KeyError: 'verify'` (`test_t1a_verify_before_audits_lands_first`) | `exit 0 \| 1 passed in 11.24s` |
| 2 | The gate runs after the audits fold, before the scoped finder (`_fold_audits`) | `if False and state.get("_verifyThen") == VERIFY_THEN_POST_AUDITS:` | `exit 1 \| 2 failed in 18.29s \| E AssertionError: assert (True and 'dispatch-scoped-finder' == 'run-verify'` (`test_t1c…`, `test_t2…`) | `exit 0 \| 2 passed in 19.67s` |
| 3 | The ceiling round completes its gate before the park (`_enter_post_fix` ceiling branch) | `if False and circuit_breaker.check_round_ceiling(...)` | `exit 1 \| 1 failed in 8.52s \| E AssertionError: {'action': 'terminal', …}` (`test_t3_ceiling_gate_runs_then_parks`) | `exit 0 \| 1 passed in 8.38s` |
| 3b | A ceiling round whose gate already ran does not run a second one (`ceilingGateSkipped`) | `if False and state.get("rounds", {}).get(rnd_key, {}).get("verifyResult") is not None:` | `exit 1 \| 1 failed in 15.16s \| E AssertionError: assert 'run-verify' == 'terminal'` (`test_t3_ceiling_gate_skipped_when_prior_verify`) | `exit 0 \| 1 passed in 13.46s` |
| 4 | The cap slices the batch (`_queue_fix_batch`) | `cap = len(rows) or 1` | `exit 1 \| 2 failed in 22.28s \| E AssertionError: assert 6 == 4` (`test_t5_fix_batch_split_six_findings`, `test_t5_fix_batch_cap_config_governs_slices`) | `exit 0 \| 2 passed in 19.78s` |
| 5 | The round accumulator resets per round (`fixBatch`) — **two guards, proved together** | see the note below | `exit 1 \| 1 failed in 6.40s \| E AssertionError: assert {'f.py', 'newsurf.py'} == {'newsurf.py'}` (`test_t6_fix_batch_resets_per_round`) | `exit 0 \| 1 passed in 6.46s` |
| 6 | The `fixBatchCap` positive-integer refusal (`_default_config`) | `cap_val < 0` in place of `cap_val < 1` | `exit 1 \| 1 failed, 6 passed in 5.91s \| E assert True is False` (`test_t7_fix_batch_cap_validation`, the `0` case) | `exit 0 \| 7 passed in 4.57s` |
| 7 | One `_fixBatch` write site (the chokepoint census) | a second `state["_fixBatch"] = …` line added in `_decision` | `exit 1 \| 1 failed in 0.98s \| E assert 2 == 1` (`test_t8_fix_batch_chokepoint_census`) | `exit 0` (in the combined green run below) |
| 8 | The scoped verify budget replaces the full command (`_fixer_verify_budget`) | `return full` before the composed prose | `exit 1 \| 1 failed in 0.91s \| E AssertionError: assert False` (`test_t10_fixer_verify_budget_placeholder`) | `exit 0 \| 1 passed in 0.93s` |
| 9 | `_decision` refuses an unregistered decision kind | `if False and kind not in decision_kinds.DECISION_KINDS:` | `exit 1 \| 1 failed in 0.98s \| E Failed: DID NOT RAISE <class 'ValueError'>` (`test_t11_decision_refuses_unregistered_kind`) | `exit 0` (combined green run) |
| 10 | Owner-gate guidance is rendered per slice (`_gate_guidance_entries`) | `sliced = False` | `exit 1 \| 1 failed in 0.96s \| E AssertionError: assert {'a.py::findi...ing three@L3'} == {'a.py::findi...nding two@L2'}` (`test_t12_guidance_rendered_per_slice`) | `exit 0 \| 1 passed in 0.93s` |
| 11 | `_escalatedRung` survives across slices (`_fold_fixer` queue branch) | `state.pop("_escalatedRung", None)` added inside the queue branch | `exit 1 \| 1 failed in 9.53s \| E KeyError: 'escalatedRung'` (`test_t5_escalated_split_carries_rung_on_both_slices`) | `exit 0 \| 1 passed in 10.17s` |
| 12 | `_fix_batch_cap` reads the configured cap, not only the default | `if False and isinstance(val, int) …` | `exit 1 \| 1 failed in 5.75s \| E AssertionError: assert 4 == 2` (`test_t5_fix_batch_cap_config_governs_slices`) | `exit 0` (combined green run) |
| P1 | The four finding templates state the line coercion | `dispatch-panel.md`: `is coerced to its integer` → `is rejected` | `exit 1 \| 1 failed, 6 passed in 0.11s \| E AssertionError: assert 'is coerced to its integer' in …` | `exit 0 \| 7 passed in 0.10s` |
| P2 | The fixer template carries `{{VERIFY_BUDGET}}` | `{{VERIFY_BUDGET}}` → `{{VERIFY_COMMAND}}` | `exit 1 \| 1 failed in 0.40s \| E AssertionError: assert '{{VERIFY_BUDGET}}' in …` | `exit 0 \| 7 passed in 0.35s` (final all-pins run) |
| P3 | The reference's `## Round economy` section | heading → `## Round economics` | `exit 1 \| 1 failed, 6 passed in 0.55s \| E AssertionError: assert '## Round economy' in …` | `exit 0 \| 7 passed in 0.35s` |
| P4 | The auto-fix-loop copy's `Verify budget:` line | `Verify budget:` → `Verify command:` | `exit 1 \| 1 failed, 6 passed in 0.47s \| E AssertionError: assert 'Verify budget:' in …` | `exit 0 \| 7 passed in 0.35s` |

**Combined green run for 7, 9 and 12** (their reds were taken individually; the restore was verified in one run over the three nodes):

```
BP7-green chokepoint-census / BP9-green decision-refusal / BP12-green cap-config | exit 0 | 3 passed in 12.58s
```

**Note on element 5 — two guards, one behaviour, disclosed.** The per-round reset of the accumulator is enforced in two places: `_queue_fix_batch`'s `state["fixBatch"] = []` and `_fold_fixer`'s `if index == 0: state["fixBatch"] = list(slice_)` overwrite. Neutralizing **either one alone** leaves `test_t6_fix_batch_resets_per_round` green (recorded: `BP5-red accumulator-reset | exit 0 | 1 passed` and `BP5b-red accumulator-overwrite-at-index-0 | exit 0 | 1 passed`) — the other guard still resets. The proof therefore neutralizes **both** and the detector goes red, which is the honest statement of what T6 guards: *the accumulator is reset by the time a later round's audit targets are derived*, not either individual line. Both single-guard greens are recorded above rather than dropped, because a reader deciding to remove one of the two lines needs to know the test will not stop them.
