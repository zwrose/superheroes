# Review-loop golden parity receipt (#507 WO-D)

Fixture-by-fixture comparison of the Python `review_loop_runner.py` harness
(driving `round_driver.run_loop`) against the frozen JS-shell goldens in this
directory. Normalization matches `eval/capture_goldens.py` (basename any
`path`/`dir` string values).

This table is the parity receipt: each row is either **identical**, or lists
every allowlisted deviation with its reason. It must stay in sync with
`eval/tests/test_golden_parity.py` (`ALLOWLIST`).

| Golden | Status |
| --- | --- |
| `telemetry_failure.golden.json` | identical |
| `telemetry_failure.fail-telemetry.golden.json` | identical |
| `plan_120_replay.golden.json` | `roundCount` — #507 audited-chain certifies after delta rounds; JS needed intermediate+confirmation to round 4; `seen` — #507 scoped-finder replaces plan_round intermediate/confirmation seat schedule; `tokenTotal` — fewer reviewer leaves under delta rounds than the JS full-roster schedule; `telemetry` — dimensionCounts/expectedLeaves follow delta-round seats, not JS plan_round skips; `fixContexts` — harness cites file/line for mechanical_compile; JS kept synthesisUnverified uncited findings |
| `code_review_recurring_class.golden.json` | `roundCount` — #507 audited-chain certifies after delta rounds; JS confirmation at round 4; `seen` — #507 scoped-finder replaces plan_round intermediate/confirmation seat schedule; `tokenTotal` — fewer reviewer leaves under delta rounds than the JS full-roster schedule; `telemetry` — dimensionCounts/expectedLeaves follow delta-round seats, not JS plan_round skips; `fixContexts` — harness cites file/line for mechanical_compile; JS kept synthesisUnverified uncited findings |
| `resume_memory.golden.json` | `roundCount` — round_driver.run_loop has no resume seam; seeds replay from round 1 then continue; `seen` — seed replay starts at baseline round 1 rather than JS resume at round 2; `telemetry` — expectedLeaves/dimensionCounts follow seed-replay schedule, not JS resume; `fixContexts` — seed replay yields an extra early fix; finding shape includes cited file/line; `fixResults` — extra fix round under seed replay vs JS single post-resume fix |
| `wrong_principle.golden.json` | `terminal` — #507 audited-chain certifies after discharge; JS confirmation parked on challenged principle; `roundCount` — delta rounds continue fixing rather than parking at confirmation; `seen` — #507 scoped-finder schedule replaces JS confirmation challenge path; `tokenTotal` — more fix rounds under delta path than JS halt-at-3; `telemetry` — terminal/leaves differ under audited-chain vs JS halted confirmation; `fixContexts` — more fixes + cited finding shape vs JS synthesisUnverified; `fixResults` — more fix rounds under delta path |
| `skipped_dimension_regression.golden.json` | `terminal` — #507 Important-only path certifies audited-chain before the Critical confirmation event runs; `roundCount` — audited-chain ends earlier than JS confirmation-cap park; `seen` — Critical lived on JS confirmation seats that delta rounds never schedule; `tokenTotal` — fewer rounds than JS confirmation-cap path; `telemetry` — terminal/leaves differ under audited-chain vs JS halted; `fixContexts` — single fix + cited finding shape vs JS two-fix confirmation path; `fixResults` — single fix vs JS two-fix confirmation path |
| `confirmation_important_certifies.golden.json` | `roundCount` — #507 Important certifies via audited-chain without JS confirmation+scope-verify rounds; `seen` — no confirmation panel under Important-only delta path; `tokenTotal` — fewer seats than JS confirmation schedule; `telemetry` — dimensionCounts follow delta seats, not JS confirmation; `fixContexts` — single fix + cited finding shape vs JS two-fix path; `fixResults` — single fix vs JS two-fix path |
| `confirmation_postscoped_rework_rearms.golden.json` | `roundCount` — #507 Important-only path certifies before JS post-confirmation cross-cutting rework; `seen` — cross-cutting subjects on a later JS fix never reached under early audited-chain; `tokenTotal` — fewer seats than JS two-confirmation schedule; `telemetry` — dimensionCounts follow delta seats, not JS confirmation re-arm; `fixContexts` — single fix + cited finding shape vs JS three-fix path; `fixResults` — single fix vs JS three-fix path |
| `confirmation_postscoped_narrow_certifies.golden.json` | `seen` — R1 cross-cutting subjects re-arm confirmation under driver last-fix rule; seat order differs from JS; `tokenTotal` — delta+confirmation hybrid token mix differs from JS schedule; `telemetry` — dimensionCounts/leaves differ under delta+confirmation hybrid; `fixContexts` — cited finding shape vs JS synthesisUnverified; classKey stamping differs |
| `confirmation_postscoped_critical_rearms.golden.json` | `roundCount` — #507 Important-only path certifies before the post-confirmation Critical scoped event; `seen` — Critical on JS post-confirmation scoped seat never scheduled under early audited-chain; `tokenTotal` — fewer seats than JS two-confirmation schedule; `telemetry` — dimensionCounts follow delta seats, not JS Critical re-arm; `fixContexts` — single fix + cited finding shape vs JS three-fix path; `fixResults` — single fix vs JS three-fix path |
| `confirmation_degraded_panel_not_counted.golden.json` | `roundCount` — no resume seam: seeds replay from round 1 rather than JS resume at confirmation round 3; `seen` — seed replay emits baseline seats instead of JS resumed confirmation seats; `tokenTotal` — seed-replay schedule differs from JS resume; `telemetry` — expectedLeaves/dimensionCounts follow seed replay, not JS resume; `fixContexts` — seed replay reaches a fix the JS resume path did not; `fixResults` — seed replay reaches a fix the JS resume path did not |

## Identical fields worth noting

Across the migration fixtures, these top-level fields stay aligned with the goldens
when the allowlist does not name them (receipt-coverage meaning):

- `terminal` — clean/halted mapping from driver verdicts (`converged`→`clean`, park/stall→`halted`) where not allowlisted
- `coverageDecisionIds` — fixEvent coverage ids still recorded on the same fixtures
- `benchmarkValid` — telemetry completeness / `--fail-telemetry` behavior
- `fixResults` — where the fix-round count matches
