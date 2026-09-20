# C14 layer 3a-b — the orchestrator's bite-proof re-run at the final head

**Head:** `9b9d6c0c` (`merge(superheroes): C14 layer 3a-b WO-G — suite-wide fixture repair (#1273)`), the branch head at the time of this re-run.
**Who:** the layer 3a-b build orchestrator (`launch-fd24fcb829c3545b`), not an implementer. Every implementer's own proof was produced against that order's own working head; **this file is the re-run of every guarded element against the head that actually ships**, which is what catches detector-narrowing staleness — a later order tightening or relocating a branch can leave an earlier proof describing a detector that no longer exists in that shape.

**Method, uniform across all thirteen elements.** The landed work was committed first, so the tree was clean before any probe. Each neutralization was applied as a **targeted, revertible edit through the host's edit action** — never a whole-file rewrite, never a shell edit, never `git checkout` to revert (the worktree guard refuses that here, by design: issue #682). The proving test was run **unedited** and observed red; the neutralization was then removed by the **inverse edit**; and the tree was confirmed byte-clean at the end by `git status --porcelain` returning empty, followed by a green run of all four affected test files together.

**Closing receipt — the two lines that make this record checkable:**

```
$ git status --porcelain
                                   (empty)
$ /usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest \
    plugins/superheroes/lib/tests/test_engine_result_channel.py \
    plugins/superheroes/lib/tests/test_engine_dispatch.py \
    plugins/superheroes/lib/tests/test_admission_clock_census.py \
    plugins/superheroes/lib/tests/test_conformance_probe.py -q -n auto
1055 passed in 34.23s
```

## The thirteen guarded elements, and how each bit

| # | element | neutralization (inverse edit reverted it) | proving test | red observed |
| --- | --- | --- | --- | --- |
| BP-A1 | `completion_window` step 1 — unusable completion stamp | the `complete_at` type guard returns `("admit", None)` | `test_completion_window_empty_dict_forfeits_unrecorded` | `1 failed` |
| BP-A2 | `completion_window` step 2 — payload digest | both digest legs return `("admit", None)` | `test_completion_window_bad_payload_sha256_forfeits_mismatch` | `4 failed` (all params) |
| BP-A3 | `completion_window` step 5 — after the cap | the after-deadline branch returns `("admit", None)` | `test_completion_window_after_deadline_forfeits` | `1 failed` |
| BP-A4 | `completion_window` step 4 — epoch equality | the epoch leg returns `("admit", None)` | `test_completion_window_epoch_mismatch_forfeits_unrecorded` | `1 failed` |
| BP-B1 | per-poll completion observation in `_run_engine_files` | observation moved into the heartbeat block **and** removed from the `rc is not None` branch | `test_completion_producer_stdout_delivery_fast_exit_records_stamp` | `1 failed` |
| BP-B2 | `_observe_native_file_completion` once-only rule | the `if obs_state.get("stamp") is not None: return` guard removed | `test_completion_producer_rewrite_keeps_first_digest` | `1 failed` |
| BP-C1 / BP-D1 | the completion window inside `_load_native_result_json` | the forfeit mapping gated to `if False` | `test_review_admission_no_completion_stamp_forfeits` **and** `test_probe_completion_after_cap_forfeits` (4 cells) | `8 failed` across both files |
| BP-C2 | the payload-digest binding | `completion_window` handed the **recorded** digest instead of the loaded payload's | `test_admission_payload_rewrite_forfeits_mismatch` | `1 failed` |
| BP-C3 | the `timedOut`-without-`deadlineMono` guard | the guard gated to `if False and ended.get("timedOut")` | `test_timed_out_write_without_recorded_deadline_forfeits` | `4 failed` (all params) |
| BP-C4 | the admission-path census detects a timestamp read | `os.path.getmtime(run_dir_real)` planted inside `_load_native_result_json` | `test_admission_path_does_not_read_filesystem_timestamps` | `1 failed`, naming `('_load_native_result_json', 'getmtime')` |
| BP-C5 | the census's vacuity guard | one `ENTRY_POINTS` name changed to `_load_native_result_json_renamed` | `test_admission_path_closure_covers_entry_points` | `1 failed` |
| BP-D2 | `probe()`'s all-mode preflight abort | the `any_reused` short-circuit gated to `if False and any_reused` | `test_probe_preflight_aborts_all_modes_when_one_mode_reused` | `1 failed` |

**BP-C1 and BP-D1 share one production element** — the completion window inside `_load_native_result_json` — and are recorded as one neutralization proving two independent test sets, rather than as two probes of the same line. That is stated rather than quietly collapsed, because "thirteen elements, twelve neutralizations" is exactly the kind of arithmetic a reader should not have to reconstruct.

## One proof that did not bite on the first attempt, and why that is in the record

BP-B1 was first neutralized by deleting **only** the `rc is not None` branch's observation call. The test stayed **green** (`1 passed`), because the top-of-loop observation still fired on the iteration before the exit was noticed. The element's real shape is the **pair** — per-poll observation *plus* the natural-exit observation — so the proof was redone as the implementer's record describes it: observation moved into the heartbeat block (restoring the 10-second cadence the defect lived in) *and* removed from the break branch. It then went red.

This is recorded rather than quietly corrected because a first attempt that fails to bite is evidence about the *element*, not noise: it says the guard has redundancy in it, and that a future change removing only one half would not be caught by this test alone. That is a real, narrow residual and it belongs where the next reader will find it.

## What this re-run does not claim

It re-proves that each detector **bites at this head**. It does not re-derive that the detectors are the *right* ones, and it is not a substitute for the layer's review. Where a proof runs against a normalized or synthesized input rather than a live engine — every cell of BP-D1's boundary matrix, whose emission is synthesized through the probe's injected `run_engine` seam — that is the disclosed design fork stated in the build brief and the PR body, not a property of this re-run.
