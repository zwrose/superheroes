# Spec checks record

- Work item: a-review-loop-that-converges-in-few-rounds-and-sta-3f628c
- Author engine and family: claude (Opus 5.5), anthropic
- Seat: codex, gpt-6.1-sol, xhigh, openai
- Same family: no

## The first review

### Round 1

Reviewed spec: commit c184da18d. Fixes landed in the next commit on this branch.

#### Gap check
- Run directory: scratchpad checks/r1/run-gap
- Result: real (codex, 41+ tool calls, engaged)
- Confirmations: none (round 1)

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| GAP-1 | gap | The 4-round invariant forbids the extra audit round the advisor may order | craft | FR-36 acceptance now names the one extra audit round as the exception, labelled as such (Canon 2026-10-27-5692f27d-11) | fixed |
| GAP-2 | gap | A repeat of a finding closed as wrong keeps "wrong" even after the code it was judged on changed | owner's | Adds behaviour (taxonomy adds-behaviour). Recommendation: let the verifier re-judge such a repeat | queued |
| GAP-3 | gap | The board's "test passed down the finding's path, so the finding was wrong" outcome is missing | craft | New FR-15 from board panel 1 | fixed |
| GAP-4 | gap | The board's removal of throwaway test copies is missing | craft | New FR-49 from board panel 8 | fixed |
| GAP-5 | gap | The outside-list cap conflicts with keeping every sweep hit | craft | FR-27 acceptance: the cap limits what a reviewer raises; sweep hits are not reviewer findings and are kept whole (Canon 2026-10-26-5692f27d-8, 2026-10-27-5692f27d-9, the no-silent-loss requirement) | fixed |
| GAP-6 | gap | Canon ids misnumbered | craft | All dated ids remapped to the actual entries | fixed |

#### Source check
- Run directory: scratchpad checks/r1/run-source
- Result: real
- Approved board, for the source check: board/build-board.html (version 4)
- Confirmations: none (round 1)

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| SRC-01 | source | Throwaway test copies' removal not carried over | craft | Same fix as GAP-4 (FR-49) | fixed |
| SRC-02 | source | Any independent reviewer may close a finding as wrong; only the verifier may | craft | FR-2 names the verifier (Canon 2026-10-27-5692f27d-3, board panel 2) | fixed |
| SRC-03 | source | Reached-path branch missing | craft | Same fix as GAP-3 (FR-15) | fixed |
| SRC-04 | source | UFR-2 misses a lower layer that moved before the session started | craft | UFR-2 reworded to "ahead of what the upper layer was last brought current with" (board panel 6) | fixed |
| SRC-05 | source | A clean round 1 could not hand back | craft | New FR-35 (board panel 4); FR-33's acceptance limited to reviews that needed fixes | fixed |
| SRC-06 | source | The test role's retained checks are missing | craft | New FR-12 (Canon 2026-10-27-5692f27d-3) | fixed |
| SRC-07 | source | Canon ids misnumbered | craft | Same fix as GAP-6 | fixed |
| SRC-08 | source | The condition on retiring the grounding reviewer is missing | craft | Added under Assumptions (Canon 2026-10-27-5692f27d-1) | fixed |
| SRC-09 | source | Separate PRs stay the first answer to a big change | craft | FR-5 acceptance added (Canon 2026-10-27-5692f27d-4) | fixed |
| SRC-10 | source | The DoD added an adoption-timing condition with no source | craft | DoD now states only the ruling (Canon 2026-10-27-5692f27d-6) | fixed |
| SRC-11 | source | A consuming project's policy in a plugin spec | craft | Line removed (Canon 2026-10-09-d6064e1d-10, 2026-10-10-dcc2b5e5-2) | fixed |
| SRC-12 | source | Purpose facts and the 397 decline tagged to the framing, which lacks them | craft | Retagged to the assessment (new source kind) and the revisit registry; the owner's cost-ranking sentence removed; the round figure corrected to the assessment's p90 (9 or 10) and max (about 30) | fixed |

#### Grounding check
- Run directory: scratchpad checks/r1/run-grounding
- Result: real
- Grounding base, for grounding: origin/main, 98a859f0aa7b3b3891d4ddb8b60f76ba073b3e45
- Confirmations: none (round 1)

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| G-1 | grounding | "As today" misdescribes the stall menu: today one automatic recovery comes first | craft | FR-34 now describes today's order, with a citation | fixed |

#### Citation check
[] (against the grounding base, before the fixes); [] (after the fixes, against the same base)

## The owner's queue

- GAP-2: a repeat of a finding closed as wrong, after the code it was judged on has changed. Recommendation: the verifier re-judges it.
