# Review-loop golden parity receipt (#507 WO-D)

Fixture-by-fixture comparison of the Python `review_loop_runner.py` harness
(driving `round_driver.run_loop`) against the frozen JS-shell goldens in this
directory. Normalization matches `eval/capture_goldens.py` (basename any
`path`/`dir` string values).

This table is the parity receipt: each row is either **identical**, or lists
every allowlisted deviation with its reason. An allowlisted row names ONLY #507
schedule / economics migrations (`seen` seat schedules, `roundCount`, `tokenTotal`,
`telemetry` leaf/dimension counts, `fixContexts` / `fixResults` shape + numbering)
where the tested PROPERTY is preserved, plus one named exception: the `terminal` of
`skipped_dimension_regression.golden.json` (see below). The property-bearing fields
`coverageDecisionIds` and `benchmarkValid` MATCH every golden and are never
allowlisted; `terminal` matches every golden except that one. It stays in sync with
`eval/tests/test_golden_parity.py` (`ALLOWLIST`).

| Golden | Status |
| --- | --- |
| `telemetry_failure.golden.json` | `tokenTotal` — a round whose verification leaves no survivors dispatches no synthesis seat, so the synthesis token leaf is absent; `telemetry` — a round whose verification leaves no survivors dispatches no synthesis seat, so the synthesis token leaf is absent |
| `telemetry_failure.fail-telemetry.golden.json` | `tokenTotal` — a round whose verification leaves no survivors dispatches no synthesis seat, so the synthesis token leaf is absent |
| `plan_120_replay.golden.json` | `roundCount` — audited-chain certifies after delta rounds; the JS shell reached the confirmation panel at a later round; `seen` — driver scoped-finder delta scans + re-armed confirmation panels replace the JS per-dimension intermediate/confirmation seat schedule; `tokenTotal` — the delta schedule dispatches a different set of reviewer leaves than the JS roster schedule; `telemetry` — expectedLeaves / dimensionCounts / roundCount follow the driver's delta-round seats, not the JS schedule; `fixContexts` — harness cites file/line for mechanical_compile scope; fix-context shape + count follow the delta schedule |
| `code_review_recurring_class.golden.json` | `roundCount` — audited-chain certifies after delta rounds; the JS shell reached the confirmation panel at a later round; `seen` — driver scoped-finder delta scans + re-armed confirmation panels replace the JS per-dimension intermediate/confirmation seat schedule; `tokenTotal` — the delta schedule dispatches a different set of reviewer leaves than the JS roster schedule; `telemetry` — expectedLeaves / dimensionCounts / roundCount follow the driver's delta-round seats, not the JS schedule; `fixContexts` — harness cites file/line for mechanical_compile scope; fix-context shape + count follow the delta schedule |
| `wrong_principle.golden.json` | `roundCount` — the challenged-coverage breaker parks at the delta round the class recurs (round 2), earlier than the JS confirmation-cap park at round 3; `seen` — driver scoped-finder delta scans + re-armed confirmation panels replace the JS per-dimension intermediate/confirmation seat schedule; `tokenTotal` — the delta schedule dispatches a different set of reviewer leaves than the JS roster schedule; `telemetry` — expectedLeaves / dimensionCounts / roundCount follow the driver's delta-round seats, not the JS schedule; `fixContexts` — harness cites file/line for mechanical_compile scope; fix-context shape + count follow the delta schedule; `fixResults` — fix-round numbering follows the driver's delta legs, not the JS round numbers |
| `skipped_dimension_regression.golden.json` | `terminal` — no later round runs a confirmation panel, so the Critical this fixture scripts only into confirmation rounds never surfaces and the loop ends clean, where the JS shell halted; `roundCount` — the recurring Critical is scripted only into confirmation-panel rounds, which no longer run, so the loop reaches its end in a different round count than the JS mandatory-confirmation schedule; `seen` — driver scoped-finder delta scans replace the JS per-dimension intermediate/confirmation seat schedule; no later round runs a confirmation panel; `tokenTotal` — the delta schedule dispatches a different set of reviewer leaves than the JS roster schedule; `telemetry` — expectedLeaves / dimensionCounts / roundCount follow the driver's delta-round seats, not the JS schedule; `fixContexts` — harness cites file/line for mechanical_compile scope; fix-context shape + count follow the delta schedule; `fixResults` — fix-round numbering follows the driver's delta legs, not the JS round numbers |
| `confirmation_important_certifies.golden.json` | `roundCount` — an Important certifies via audited-chain without the JS confirmation + scope-verify rounds; `seen` — driver scoped-finder delta scans + re-armed confirmation panels replace the JS per-dimension intermediate/confirmation seat schedule; `tokenTotal` — the delta schedule dispatches a different set of reviewer leaves than the JS roster schedule; `telemetry` — expectedLeaves / dimensionCounts / roundCount follow the driver's delta-round seats, not the JS schedule; `fixContexts` — harness cites file/line for mechanical_compile scope; fix-context shape + count follow the delta schedule; `fixResults` — fix-round numbering follows the driver's delta legs, not the JS round numbers |
| `confirmation_postscoped_rework_rearms.golden.json` | `roundCount` — cross-cutting rework re-arms ONE confirmation over delta rounds — fewer rounds than the JS two-confirmation schedule (no mandatory first confirmation); `seen` — driver scoped-finder delta scans + re-armed confirmation panels replace the JS per-dimension intermediate/confirmation seat schedule; `tokenTotal` — the delta schedule dispatches a different set of reviewer leaves than the JS roster schedule; `telemetry` — expectedLeaves / dimensionCounts / roundCount follow the driver's delta-round seats, not the JS schedule; `fixContexts` — harness cites file/line for mechanical_compile scope; fix-context shape + count follow the delta schedule; `fixResults` — fix-round numbering follows the driver's delta legs, not the JS round numbers |
| `confirmation_postscoped_narrow_certifies.golden.json` | `roundCount` — narrow post-confirmation rework certifies audited-chain — fewer rounds than the JS one-confirmation schedule; `seen` — driver scoped-finder delta scans + re-armed confirmation panels replace the JS per-dimension intermediate/confirmation seat schedule; `tokenTotal` — the delta schedule dispatches a different set of reviewer leaves than the JS roster schedule; `telemetry` — expectedLeaves / dimensionCounts / roundCount follow the driver's delta-round seats, not the JS schedule; `fixContexts` — harness cites file/line for mechanical_compile scope; fix-context shape + count follow the delta schedule; `fixResults` — fix-round numbering follows the driver's delta legs, not the JS round numbers |
| `confirmation_postscoped_critical_rearms.golden.json` | `roundCount` — the Critical re-arms ONE confirmation over delta rounds — fewer rounds than the JS two-confirmation schedule (no mandatory first confirmation); `seen` — driver scoped-finder delta scans + re-armed confirmation panels replace the JS per-dimension intermediate/confirmation seat schedule; `tokenTotal` — the delta schedule dispatches a different set of reviewer leaves than the JS roster schedule; `telemetry` — expectedLeaves / dimensionCounts / roundCount follow the driver's delta-round seats, not the JS schedule; `fixContexts` — harness cites file/line for mechanical_compile scope; fix-context shape + count follow the delta schedule; `fixResults` — fix-round numbering follows the driver's delta legs, not the JS round numbers |

## Property-bearing fields that stay identical to the goldens

These top-level fields match every golden (never allowlisted), except the one
`terminal` exception named below — they are the receipt that the #507 driver
preserves each fixture's safety property:

- `terminal` — the clean/halted verdict (`converged`→`clean`; challenged-park /
  confirmation-cap park / verify-fail → `halted`). wrong_principle is `halted`;
  all clean fixtures `clean`. The one exception is
  `skipped_dimension_regression.golden.json`: the golden is `halted`, but no later
  round runs a confirmation panel, so the Critical that fixture scripts only into
  confirmation rounds never surfaces and the loop ends `clean` (allowlisted).
- `coverageDecisionIds` — every fixture's recorded coverage decisions (RCD-wrong,
  RCD-plan-coverage, RCD-code-test-coverage, …).
- `benchmarkValid` — telemetry completeness / `--fail-telemetry` behaviour.
