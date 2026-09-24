# C14 layer 3a — r3 lane, every bite-proof re-run on the final head (#1273)

**Head proved:** `a9b74eda` (branch `build/1273-c14-layer3a-result-contracts`).
**Who ran it:** the r3 orchestrator (`launch-a4efd1ad37a6ba2c`), not an implementer — verification
authority never delegates, so every red below was planted and every green observed by this session.
**Where:** a dedicated detached probe worktree at `a9b74eda`
(`…/scratchpad/wt-probe2`), never the build tree and never a tree a live seat was reading.
**How:** every neutralization was a **targeted, revertible edit through the host's edit action** and
was undone by its **inverse edit** — no `git` discard, no whole-file rewrite. **The detector itself
was never edited** in any of the 21 proofs. `git status --porcelain` over the probe worktree was
**empty** after the last restore (captured below), and the green half is one run over all 21
proving tests on the fully restored tree.

This record covers **three populations at once**, which is why it exists instead of three:

1. the detectors the **r3 fix** added (`timeout-deadline-unrecorded`, the four deadline-recording
   producers, the cap-vs-poll stamp);
2. the detectors the **r2 review loop** added without records
   (`run-dir-is-symlink`, `run-dir-not-empty-unopened`, `native-result-after-timeout`,
   `admittedAfterTimeout`, flat-legs-vs-`modeLegs`);
3. the **re-runs owed at the final head** for the layer's existing WO-A…WO-D records
   (`c14_l3a_write_admission.md`, `c14_l3a_hollow_member_grade.md`, `c14_l3a_refusal_census.md`)
   and for the cherry-picked WO-4 record (`c14_l2b_probe_mode_legs.md`).

## The 21 guarded elements, red under neutralization

| # | guarded element | neutralization (targeted edit) | proving test | raw red |
|---|---|---|---|---|
| 1 | `conformance_probe._probe_setup` symlink refusal | `if os.path.islink(stripped):` → `if False and os.path.islink(stripped):` | `test_conformance_probe.py::test_probe_refuses_symlinked_run_dir` | `AssertionError: 'default: auth-or-config-refusal'.endswith('run-dir-is-symlink')` → `1 failed in 0.55s` |
| 2 | parent run-dir unrecognized-entries refusal | `if entries - expected_names:` → `if False and (entries - expected_names):` | `::test_probe_refuses_parent_run_dir_with_unrecognized_entries` | `AssertionError: assert 'auth-or-config-refusal' == 'run-dir-not-empty-unopened'` → `1 failed in 0.51s` |
| 3 | `_validate_probe_record` flat-legs vs `modeLegs` cross-check | `if leg.get("ok") != derived_legs[name]["ok"]:` → `if False and …` | `::test_validate_probe_record_refuses_flat_legs_disagreeing_with_mode_legs` | `AssertionError: assert None == 'probe-result-malformed:/tmp/claude.json'` → `1 failed in 0.37s` |
| 4 | `_payload` `probedModes` / `modeLegs` key equality | `"probedModes": list(probed_modes)` → `"probedModes": ["print"]` | `::test_payload_writer_probed_modes_matches_mode_legs_keys` | `AssertionError: 'probe-result-malformed:/tmp/claude.json' is None` → `1 failed in 0.36s` |
| 5 | `_payload` per-mode leg-name completeness | `mode_legs` rewritten to drop `progressTelemetry` before `_derive_flat_legs` | `::test_payload_writer_mode_legs_carry_all_leg_names` | `Extra items in the right set: 'progressTelemetry'` → `1 failed in 0.60s` |
| 6 | `_admit_native_write_result` mtime gate (`native-result-after-timeout`) | `if mtime is None or mtime > timeout_deadline:` → `if False and (…):` | `test_engine_dispatch.py::test_native_write_timeout_poll_gap_result_after_cap_refused` **and** `::test_native_write_timeout_result_written_after_deadline_rejected` | both fail — `assert True is not True` on the graded `ok` → `2 failed in 2.90s` |
| 7 | `admittedAfterTimeout` marker on an admitted timed-out success | `return dict(admitted, admittedAfterTimeout=True)` → `return dict(admitted)` | `::test_native_write_timeout_with_valid_result_admits` | `KeyError: 'admittedAfterTimeout'` → `1 failed in 2.78s` |
| 8 | `_grade_write_attempt` unrecorded-deadline chokepoint (`timeout-deadline-unrecorded`) | the `_recorded_timeout_deadline` block → the old `timeout_deadline = ended.get("timeoutAt") if …` one-liner | `::test_timed_out_write_without_recorded_deadline_forfeits` (3 params) | `TypeError: '>' not supported between instances of 'float' and 'str'` (non-numeric) and `assert None is True` → `3 failed in 2.32s` |
| 9 | P1 `_run_engine_files` stamp is the recorded cap | `timeout_at = timeout_deadline_wall` → `timeout_at = time.time()` | `::test_native_write_timeout_at_is_cap_not_poll_time` | `assert 2.003516912460327 <= 0.5` → `1 failed in 5.49s` |
| 10 | P3 in-process capture records its deadline | dropped `if timed_out: ended["timeoutAt"] = timeout_deadline_wall` | `::test_injected_capture_timeout_records_timeout_at` | `KeyError: 'timeoutAt'` → `1 failed in 2.05s` |
| 11 | P2 background flow records its deadline | dropped `if timed_out: ended_record["timeoutAt"] = timeout_at` | `::test_background_timeout_records_timeout_at_and_rejects_late_native_write` | `KeyError: 'timeoutAt'` → `1 failed in 1.22s` |
| 12 | P4 budget-exhaustion synth records its observation instant | dropped `"timeoutAt": budget_observed_at,` from the synth record | `::test_supervise_bg_budget_exhaustion_ends_attempt_without_resume` | `KeyError: 'timeoutAt'` → `1 failed in 2.23s` |
| 13 | BP-D1 non-timed-out crash forfeits before admission | `and not ended.get("timedOut")` → `and ended.get("timedOut")` | `::test_native_write_crash_with_valid_result_forfeits` | graded `{'ok': True, …}` instead of a forfeit → `1 failed in 2.37s` |
| 14 | BP-A1 native result admitted before the timeout forfeit | re-inserted the pre-admission `refusal/timedOut/exit` early forfeit | `::test_native_write_timeout_with_valid_result_admits` | `KeyError: 'ok'` → `1 failed in 3.56s` |
| 15 | BP-A2 native payload scrubber scrubs dict **keys** | dict branch restored to `{k: _scrub_native_payload(v) …}` (keys unscrubbed) | `::test_scrub_native_payload_scrubs_dict_keys_and_preserves_collisions` | secret-bearing keys survive in the output mapping → `1 failed in 2.11s` |
| 16 | BP-A3-fold1 budget exhaustion ends without resume | `if _attempt_bg_budget_exhausted(…):` → `if False:  # bite-proof plant` | `::test_supervise_bg_budget_exhaustion_ends_attempt_without_resume` | `assert 0 == 1` (`len([])`) → `1 failed in 2.09s` |
| 17 | BP-A3-fold2 pre-retry stop-unconfirmed refusal | `if _background_stop_unconfirmed(state):` → `if False:  # bite-proof plant` | `::test_supervise_pre_retry_refuses_on_background_stop_unconfirmed` | `'spawn-blocked-for-test' != 'background-stop-unconfirmed'` → `1 failed in 1.89s` |
| 18 | hollow BP1 populated-payload rule | findings branch collapsed to `parsed = SHAPE_FINDINGS_HOLLOW_MEMBER` | `test_engine_adapter.py::test_review_payload_shape_findings_partial_hollow_member` | shape token mismatch → `1 failed in 0.73s` |
| 19 | hollow BP2 `memberShapeWanted` / `memberShapeGot` | both field attachments removed from the constructor's return dict | `::test_hollow_family_diagnostic_carries_member_shape_fields` | `KeyError: 'memberShapeWanted'` → `1 failed in 0.68s` |
| 20 | hollow BP3 single-mint census | planted `_ = SHAPE_FINDINGS_HOLLOW_MEMBER` outside the allowed ranges | `::test_hollow_member_shape_tokens_minted_only_via_constructor` | `Left contains one more item: 'SHAPE_FINDINGS_HOLLOW_MEMBER:2003'` → `1 failed in 0.64s` |
| 21 | background-refusal literal census (widened to every `lib/` module) | planted `_WO1273_BP_PLANT = "background-launch-unacknowledged"` in `engine_adapter.py` | `test_background_outcome_census.py::test_background_refusal_literals_only_in_home[engine_adapter.py]` | `Left contains one more item: ('background-launch-unacknowledged', 1982)` → `1 failed, 161 passed in 0.84s` |

**Every red above is the detector failing with the detector itself unedited.** Each neutralization
was reverted by its inverse edit before the next one was planted, so no two plants were ever in the
tree together.

## The green half — one run, restored tree, final head

Tree state immediately before the run:

```
$ git status --porcelain
$ git diff --stat
(clean above)
```

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-p2 -m pytest \
  <the 21 proving tests named above, by exact node id; test_background_outcome_census.py whole> -q
........................................................................ [ 39%]
........................................................................ [ 78%]
.......................................                                  [100%]
183 passed in 11.52s
```

(183 = the named node ids plus the census module's 162 parametrizations.)

## What this record closes, and one thing it corrects

- The r2 park note's owed item 2 — bite-proof records for the review-loop-added detectors **and**
  re-runs of the existing WO-A…WO-D records at the final head — is **closed by this record**.
- `wo_l3a_E_1273.md` (the implementer's own record for the r3 fix) states that its **BP-E2 green
  half was not captured** within that order's command budget. **It is captured here** — rows 6 and 8
  above, red, and the single green run — re-run by this session at the final head, which is the
  receipt that counts. That record's honest note is left as written rather than edited after the
  fact.
- No probe touched product code as a landed change. Nothing on this branch changed as a result of
  this sweep except this record.
