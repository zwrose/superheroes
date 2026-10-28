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

### Round 2

Reviewed spec: commit 75700a058. Fixes landed in the next commit on this branch.

#### Gap check
- Run directory: scratchpad checks/r2/run-gap
- Result: real
- Confirmations: GAP-1 -> fixed; GAP-2 -> not-fixed (queued for the owner, as recorded); GAP-3 -> fixed; GAP-4 -> fixed; GAP-5 -> fixed; GAP-6 -> fixed

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| GAP-7 | gap | Stall recovery and the stall menu's extra round can run past the 4-round cap | craft | FR-34 acceptance: recovery and the menu run only inside the 4 rounds; a stall at round 4 is handed back at the cap (framing: "the stuck-fix breaker stays inside the cap"; board panel 4) | fixed |

#### Source check
- Run directory: scratchpad checks/r2/run-source
- Result: real
- Approved board, for the source check: board/build-board.html (version 4)
- Confirmations: SRC-01 to SRC-12 -> fixed

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| SRC-13 | source | Same as GAP-7 | craft | Same fix as GAP-7 | fixed |
| SRC-14 | source | The specialist-seating revisit condition is missing | craft | Added under Assumptions & dependencies (Canon 2026-10-27-5692f27d-5) | fixed |

#### Grounding check
- Run directory: scratchpad checks/r2/run-grounding
- Result: real
- Grounding base, for grounding: origin/main, 98a859f0aa7b3b3891d4ddb8b60f76ba073b3e45 (fresh base, same commit)
- Confirmations: G-1 -> fixed

No new findings.

#### Citation check
[]

### Round 3

Reviewed spec: commit 3552f3a5a. The fix landed in the next commit on this branch.

#### Gap check
- Run directory: scratchpad checks/r3/run-gap
- Result: real
- Confirmations: GAP-2 -> not-fixed (still queued for the owner); GAP-7 -> fixed

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| GAP-8 | gap | The specialist-seating revisit line in Assumptions decides something the core does not | craft | Reworded as a plain dependency: the owner's revisit (Canon 2026-10-27-5692f27d-5) reads #2189's existing "finding outcomes by lens" row, and this work builds nothing for it, so a builder reading only the core builds the same thing | fixed |

#### Source check
- Run directory: scratchpad checks/r3/run-source
- Result: real
- Approved board, for the source check: board/build-board.html (version 4)
- Confirmations: SRC-13 -> fixed; SRC-14 -> fixed

No new findings. Clean.

#### Grounding check
- Run directory: scratchpad checks/r3/run-grounding
- Result: real
- Grounding base, for grounding: origin/main, 98a859f0aa7b3b3891d4ddb8b60f76ba073b3e45
- Confirmations: none owed

No new findings. Clean.

#### Citation check
[]

### Round 4

Reviewed spec: commit 359d37e1a. The fix for its two findings landed in the next commit; round 4 was
the last round, so the after-rulings cycle re-reads it.

#### Gap check
- Run directory: scratchpad checks/r4/run-gap
- Result: real
- Confirmations: GAP-2 -> not-fixed (still queued for the owner); GAP-8 -> fixed

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| GAP-9 | gap | The grounding-retirement reopening condition sits only in Assumptions | craft | New FR-53: at each gardening pass the advisor checks both revisit conditions and brings a met one to the owner (Canon 2026-10-27-5692f27d-1, 2026-10-27-5692f27d-5) | fixed, not yet confirmed |

#### Source check
- Run directory: scratchpad checks/r4/run-source
- Result: real
- Approved board, for the source check: board/build-board.html (version 4)
- Confirmations: none owed

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| SRC-15 | source | The round-3 rewording dropped the seating revisit's cost-versus-findings condition | craft | Same fix as GAP-9: FR-53 states the condition | fixed, not yet confirmed |

#### Grounding check
- Run directory: scratchpad checks/r4/run-grounding
- Result: real
- Grounding base, for grounding: origin/main, 98a859f0aa7b3b3891d4ddb8b60f76ba073b3e45
- Confirmations: none owed

No new findings. Clean.

#### Citation check
[] (and [] after the FR-53 fix)

## After rulings 1

Rulings: one spec (Canon 2026-10-28-5692f27d-1); the verifier re-judges a stale "wrong" repeat
(Canon 2026-10-28-5692f27d-2). Reviewed spec: commit 09d7138e6, changed parts only.

### Round 1

#### Gap check
- Run directory: scratchpad checks/ra1/run-gap
- Result: real
- Confirmations: GAP-2 -> fixed (by the owner's ruling, FR-21); GAP-9 -> fixed

No new findings. Clean.

#### Source check
- Run directory: scratchpad checks/ra1/run-source
- Result: real
- Approved board, for the source check: board/build-board.html (version 4)
- Confirmations: SRC-15 -> fixed

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| SRC-16 | source | The one-release lines contradict the core-first ruling | craft | DoD and Constraints now say the core loop ships first in one release and the three add-ons may follow; UFR-8 reads "a release" (Canon 2026-10-28-5692f27d-1) | fixed |

#### Grounding check
- Run directory: scratchpad checks/ra1/run-grounding
- Result: real
- Grounding base, for grounding: origin/main, 98a859f0aa7b3b3891d4ddb8b60f76ba073b3e45
- Confirmations: none owed

No new findings. Clean.

#### Citation check
[]

## The owner's queue

- GAP-2: a repeat of a finding closed as wrong, after the code it was judged on has changed. Recommendation: the verifier re-judges it. Ruled 2026-10-28: a (Canon 2026-10-28-5692f27d-2), now FR-21.
- GAP-9 and SRC-15: the revisit conditions, fixed as FR-54 after round 4; confirmed fixed in
  after-rulings round 1, so they leave the queue.

Owner rulings so far: one spec, not split (Canon 2026-10-28-5692f27d-1); the verifier re-judges a stale "wrong" repeat (Canon 2026-10-28-5692f27d-2, FR-21).; the stall menu is retired (Canon 2026-10-28-5692f27d-3, FR-35).
