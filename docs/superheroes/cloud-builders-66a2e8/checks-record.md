# Spec checks record

- Work item: cloud-builders-66a2e8
- Author engine and family: claude, anthropic
- Seat: codex, gpt-6.1-sol, xhigh, openai
- Same family: no

Run directories are under the discovery session's scratchpad,
`/private/tmp/claude-501/-Users-zwrose-superheroes--claude-worktrees-sweet-agnesi-064837/ca3e7e0d-10c0-4ae3-9d18-d8b46213b542/scratchpad/checks/`,
written below as `<checks>/`.

## The first review

### Round 1

Spec as reviewed: commit 91082742 on branch `claude/superheroes-cloud-settings-f5d054`. Fixes: commit a5a41289.

#### Gap review
- Run directory: `<checks>/r1/gap/run`
- Result: real (terminal, ok, 1 attempt, engaged, 36 tool calls, 25 files read)
- Confirmations: none owed in round 1

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| cloud-gap-1 | gap | FR-30 and FR-32 cleaned up "when a lane ends", which in the existing lane accounting includes handback and park, so a parked or handed-back build would lose its branch. | craft | Cleanup is now tied to the PR being merged (FR-30) or closed unmerged (FR-32), and FR-31 keeps the pushed branch until then. | fixed |
| cloud-gap-2 | gap | FR-35's "only sign of a lapsed pass" contradicted the repeated line (UFR-6) and the parked-PR notice (UFR-8). | craft | FR-35 now forbids only a warning ahead of a lapse and names the three messages that still appear after one. | fixed |
| cloud-gap-3 | gap | UFR-7 parked the PR whenever the pass lapsed during a build, even after its review had finished. | craft | UFR-7 now triggers when the review cannot run because the pass has lapsed, and a finished review stays as recorded. | fixed |
| cloud-gap-4 | gap | UFR-9 and UFR-10 assume pushed work; a builder that stops before its first push has no outcome. The reviewer marks the fix as adding behaviour. | owner's | Queued as O-1. | queued |
| cloud-gap-5 | gap | The spec did not carry Canon 2026-10-10-ca3e7e0d-3 (paid business access tokens ruled out). | craft | Constraints now carries it. | fixed |

#### Source check
- Run directory: `<checks>/r1/source/run`
- Result: real (terminal, ok, 1 attempt, engaged, 18 tool calls, 11 files read)
- Approved board, for the source check: `board/build-board.html` and `board/journeys.html` beside the spec
- Confirmations: none owed in round 1

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| SC-1 | source, backward | Canon 2026-10-10-ca3e7e0d-3 is missing from the spec. | craft | Same fix as cloud-gap-5. | fixed |
| SC-2 | source, forward | The assumption that the build makes the cloud carry the advisor's plugin version with no hand step goes beyond the approved scope: the journeys leave hands-off upkeep of the setup to the later piece. | owner's | Queued as O-2. The sentence is left as written until the owner rules. | queued |
| SC-3 | source, backward | The journeys say the builder pushes its work often; FR-24 checked only handback. | craft | FR-24 now requires pushing often while building. | fixed |
| SC-4 | source, backward | The board promises the advisor sends a parked PR back for review after renewal; UFR-8 only told the owner. | craft | FR-36 added. | fixed |
| SC-5 | source, forward | Same contradiction as cloud-gap-2. | craft | Same fix as cloud-gap-2. | fixed |
| SC-6 | source, backward | The board's pass command and clipboard step were missing. | craft | FR-1 and FR-34 acceptance now carry them. | fixed |
| SC-7 | source, backward | A cloud override in a project with cloud builds switched off had no launch report. | craft | FR-15 and FR-16 now cover a launch word that points a build at the cloud. | fixed |
| SC-8 | source, forward | The pilot claim cited the framing, which does not hold it. | craft | The claim is removed. | fixed |

#### Grounding
- Run directory: `<checks>/r1/grounding/run`
- Result: real (terminal, ok, 1 attempt, engaged, 38 tool calls, 17 files read)
- Grounding base, for grounding: origin/main, 4e505f3a4865278a8920e93f7ff1fd047f9723a9
- Confirmations: none owed in round 1

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| GND-001 | grounding | Same as cloud-gap-1: "lane ends" clashes with the existing terminal outcomes. | craft | Same fix as cloud-gap-1. | fixed |
| GND-002 | grounding | The cited Canon entries 2026-10-10-ca3e7e0d-* are not in the default branch's Canon. | declined | The finding is wrong. The entries are lines 133 to 148 of `docs/superheroes/canon.md` on the spec's branch, and the spec's "How to read this spec" names Canon as their home. Canon's contract says a ruling rides the pull request of the branch it was committed on, and that a ruling not yet on the default branch binds the sessions on the branch that holds it (`plugins/superheroes/rubric/canon-contract.md`, sections "Writing a ruling" and "Reading Canon"). They reach the default branch with this spec's pull request. | declined |
| GND-003 | grounding | The board files named in the spec are not on the default branch. | declined | The finding is wrong. The spec's "How to read this spec" names `board/build-board.html` and `board/journeys.html` beside the spec; both are in `docs/superheroes/cloud-builders-66a2e8/board/` on the spec's branch (commit 91082742) and reach the default branch with this spec's pull request, as the saved boards of the review spec did. | declined |

#### Citation check
`[]` (run with `--root` set to the grounding base at origin/main 4e505f3a)

### Round 2

Spec as reviewed: commit a5a41289. Fixes: commit 8d949c4d.

#### Gap review
- Run directory: `<checks>/r2/gap/run`
- Result: real (terminal, ok, 1 attempt, engaged, 25 tool calls, 25 files read)
- Confirmations: cloud-gap-1 -> fixed; cloud-gap-2 -> fixed; cloud-gap-3 -> fixed; cloud-gap-4 -> not-fixed (it is O-1 in the owner's queue, unfixed until the owner rules); cloud-gap-5 -> fixed

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| cloud-gap-6 | gap | UFR-3's local fallback for a build that needs the owner's machine applied only when the project's setting was on, not when the launch word asked for the cloud. | craft | UFR-3 now applies however the cloud was chosen, and says a launch word does not override what the build needs. | fixed |
| cloud-gap-7 | gap | FR-36 would send a parked PR back for review even after it was closed and cleaned up. | craft | FR-36 now covers only PRs still open. | fixed |
| cloud-gap-8 | gap | UFR-8 promised that renewing the pass helps for every review that did not run, including ones a live pass cannot repair. | craft | UFR-8 now applies only to a PR that UFR-7 parked; other reasons are reported as the review rules already say. | fixed |

#### Source check
- Run directory: `<checks>/r2/source/run`
- Result: real (terminal, ok, 1 attempt, engaged, 17 tool calls, 20 files read)
- Approved board, for the source check: `board/build-board.html` and `board/journeys.html` beside the spec
- Confirmations: SC-1 -> fixed; SC-2 -> not-fixed (it is O-2 in the owner's queue, unfixed until the owner rules); SC-3 -> fixed; SC-4 -> fixed; SC-5 -> fixed; SC-6 -> fixed; SC-7 -> fixed; SC-8 -> fixed

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| SC-9 | source, backward | The gardening-pass check was limited to projects with cloud builds switched on; the board and Canon 2026-10-10-ca3e7e0d-12 do not limit it, and a project with the switch off keeps its setup and can still launch in the cloud by launch word. | craft | FR-33 and Part E's opening now apply to every project that has a cloud setup. | fixed |
| SC-10 | source, forward | FR-18 cited the framing, which does not hold that promise. | craft | FR-18 is now tagged "craft, for your veto"; it is in N-1 for the owner. | fixed |

#### Grounding
- Run directory: `<checks>/r2/grounding/run`
- Result: real (terminal, ok, 1 attempt, engaged, 38 tool calls, 20 files read)
- Grounding base, for grounding: origin/main, 4e505f3a4865278a8920e93f7ff1fd047f9723a9
- Confirmations: GND-001 -> fixed; GND-002 -> decline-accepted; GND-003 -> decline-accepted
- New findings: none. Grounding is clean in this round.

#### Citation check
`[]` (run with `--root` set to the grounding base at origin/main 4e505f3a)

### Round 3

Spec as reviewed: commit 8d949c4d. No fixes were needed.

#### Gap review
- Run directory: `<checks>/r3/gap/run`
- Result: real (terminal, ok, 1 attempt, engaged, 15 tool calls, 26 files read)
- Confirmations: cloud-gap-1, cloud-gap-2, cloud-gap-3, cloud-gap-5, cloud-gap-6, cloud-gap-7, cloud-gap-8 -> fixed; cloud-gap-4 -> not-fixed (it is O-1 in the owner's queue)
- New findings: none. Gap review is clean apart from O-1, which is queued.

#### Source check
- Run directory: `<checks>/r3/source/run`
- Result: real (terminal, ok, 1 attempt, engaged, 15 tool calls, 14 files read)
- Approved board, for the source check: `board/build-board.html` and `board/journeys.html` beside the spec
- Confirmations: SC-1, SC-3, SC-4, SC-5, SC-6, SC-7, SC-8, SC-9, SC-10 -> fixed; SC-2 -> not-fixed (it is O-2 in the owner's queue)
- New findings: none. The source check is clean apart from O-2, which is queued.

#### Grounding
- Run directory: `<checks>/r3/grounding/run`
- Result: real (terminal, ok, 1 attempt, engaged, 25 tool calls, 15 files read)
- Grounding base, for grounding: origin/main, 4e505f3a4865278a8920e93f7ff1fd047f9723a9
- Confirmations: GND-001 -> fixed; GND-002 -> decline-accepted; GND-003 -> decline-accepted
- New findings: none. Grounding is clean.

#### Citation check
`[]` (run with `--root` set to the grounding base at origin/main 4e505f3a)

The first review stopped after round 3: all three checks are clean apart from the items already in
the owner's queue. Three rounds ran and 17 findings were fixed (12 in round 1, 5 in round 2).

## Writing pass

The pass reworded seven statements to name who acts and to split one long sentence: the Purpose
sentence about the two pieces, and one acceptance rule each under FR-13, FR-25, FR-31, FR-36, UFR-4
and UFR-8. It added, dropped and moved no requirement, and every statement kept its source tag.

- Meaning check 1: run directory `<checks>/wp/m1/run`, the same seat (codex, gpt-6.1-sol, xhigh).
  Result: real (terminal, ok, 1 attempt, engaged). Findings: M1 to M7, one for each changed
  statement, every one `meaning:kept`.
- Reconciled: seven changed statements, seven findings, each matching one statement.
- The pass was kept.

## After rulings 1

The owner answered remainder sheet 1 on 2026-10-10 (Canon 2026-10-10-ca3e7e0d-17 to -20). The spec
changed in commit a320fa24: UFR-13 and UFR-10's rule (unpushed work), a new Part F with FR-37 and
the reworded assumption and scope (plugin version pickup), and a new constraint (no over-investment
in recovery machinery). The journeys board was redrawn for the pickup; `board/redraws.md` records it.

### Round 1

Spec as reviewed: commit a320fa24. No fixes were needed.

#### Gap review
- Run directory: `<checks>/ar1r1/gap/run`
- Result: real (terminal, ok, 1 attempt, engaged, 15 tool calls, 11 files read)
- Confirmations: cloud-gap-1 to cloud-gap-8 -> fixed (cloud-gap-4 by the owner's ruling, now UFR-13)
- New findings: none. Gap review is clean.

#### Source check
- Run directory: `<checks>/ar1r1/source/run`
- Result: real (terminal, ok, 1 attempt, engaged, 8 tool calls, 8 files read)
- Approved board, for the source check: `board/build-board.html` and `board/journeys.html` (version 2) beside the spec
- Confirmations: SC-1 to SC-10 -> fixed (SC-2 by the owner's ruling, now FR-37)
- New findings: none. The source check is clean.

#### Grounding
- Run directory: `<checks>/ar1r1/grounding/run`
- Result: real (terminal, ok, 1 attempt, engaged, 15 tool calls, 9 files read)
- Grounding base, for grounding: origin/main, ef8e6d3c049222c26513df581d34f13770b31638
- Confirmations: GND-001 -> fixed; GND-002 -> decline-accepted; GND-003 -> decline-accepted
- New findings: none. Grounding is clean.

#### Citation check
`[]` (run with `--root` set to the grounding base at origin/main ef8e6d3c)

All three checks are clean after the rulings, in one round.

## After vet round 1

The advisor's vet, round 1 (https://github.com/zwrose/superheroes/pull/1740#issuecomment-6101254809),
returned `findings`: eight craft findings (V1.1 to V1.4 and V1.6 to V1.9) and one owner call (V1.5).
The eight were fixed in commit 32ef30c8. The checks then ran on the changed parts.

### Round 1

Spec as reviewed: commit 32ef30c8.

#### Gap review
- Run directory: `<checks>/av1r1/gap/run`
- Result: real (terminal, ok, 1 attempt, engaged, 17 tool calls, 13 files read)
- Confirmations: cloud-gap-1 to cloud-gap-8 -> fixed
- New findings: none. Gap review is clean.

#### Source check
- Run directory: `<checks>/av1r1/source/run`
- Result: real (terminal, ok, 1 attempt, engaged, 13 tool calls, 10 files read)
- Approved board, for the source check: `board/build-board.html` and `board/journeys.html` (version 2) beside the spec
- Confirmations: SC-1 to SC-10 -> fixed

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| SC-11 | source, forward | The fix for vet finding V1.1 makes a parked cloud PR follow the approved review spec, which lets the owner's word send one PR through with a same-family reviewer. The approved cloud boards say "Never a same-family stand-in" (build board, "5 Mid-build trouble"; journeys, journey 3). The two disagree, and no ruling for this piece settles it. | owner's | Two approved sources conflict, so it is queued as O-3 with both sides. | queued |

#### Grounding
- Run directory: `<checks>/av1r1/grounding/run`
- Result: real (terminal, ok, 1 attempt, engaged, 16 tool calls, 14 files read)
- Grounding base, for grounding: origin/main, ef8e6d3c049222c26513df581d34f13770b31638
- Confirmations: GND-001 -> fixed; GND-002 -> decline-accepted; GND-003 -> decline-accepted
- New findings: none. Grounding is clean.

#### Citation check
`[]` (run with `--root` set to the grounding base at origin/main ef8e6d3c)

## After rulings 2

The owner answered remainder sheet 2 on 2026-10-10 (Canon 2026-10-10-ca3e7e0d-21 and -22, and
Aligned on the journeys redraw). The spec changed in commit beacc7aa: UFR-7's rule cites the new
ruling and says the cloud is not stricter than a local build, FR-13 gained the rule for a project
that keeps its Canon or its specs outside the repository, and Out of scope gained a line for it.
Both boards were redrawn for the same-family rule; `board/redraws.md` records the two redraws.

### Round 1

Spec as reviewed: commit beacc7aa. No fixes were needed.

#### Gap review
- Run directory: `<checks>/ar2r1/gap/run`
- Result: real (terminal, ok, 1 attempt, engaged, 19 tool calls, 11 files read)
- Confirmations: cloud-gap-1 to cloud-gap-8 -> fixed
- New findings: none. Gap review is clean.

#### Source check
- Run directory: `<checks>/ar2r1/source/run`
- Result: real (terminal, ok, 1 attempt, engaged, 11 tool calls, 9 files read)
- Approved board, for the source check: `board/build-board.html` (version 2) and `board/journeys.html` (version 3) beside the spec
- Confirmations: SC-1 to SC-11 -> fixed (SC-11 by the owner's ruling and the two redraws)
- New findings: none. The source check is clean.

#### Grounding
- Run directory: `<checks>/ar2r1/grounding/run`
- Result: real (terminal, ok, 1 attempt, engaged, 22 tool calls, 10 files read)
- Grounding base, for grounding: origin/main, ef8e6d3c049222c26513df581d34f13770b31638
- Confirmations: GND-001 -> fixed; GND-002 -> decline-accepted; GND-003 -> decline-accepted
- New findings: none. Grounding is clean.

#### Citation check
`[]` (run with `--root` set to the grounding base at origin/main ef8e6d3c)

All three checks are clean after the second set of rulings, in one round. In all, six check rounds
ran: three in the first review, one after each of the two sets of rulings, and one after the vet's
first round. The checks fixed 17 findings and the vet's first round added 8 craft fixes.

## The owner's queue

Nothing is waiting.

- Settled on remainder sheet 1: O-1 (Canon 2026-10-10-ca3e7e0d-17, now UFR-13), O-2 (Canon
  2026-10-10-ca3e7e0d-18, now FR-37) and N-1 (Canon 2026-10-10-ca3e7e0d-19, all nine stand).
- Settled on remainder sheet 2: O-3 (from SC-11; Canon 2026-10-10-ca3e7e0d-21, the cloud follows the
  review spec's rule and both boards were redrawn) and O-4 (the vet's owner call V1.5; Canon
  2026-10-10-ca3e7e0d-22, such a project's builds run on the owner's machine for now).
