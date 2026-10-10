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

## The owner's queue

- O-1 (from cloud-gap-4): a cloud builder that stops with work it never pushed, or before its first push, has no stated outcome. Recommendation: the advisor first tries to get the stopped builder's unpushed work pushed; what cannot be saved is redone, the advisor says how much, and a build that never pushed restarts from the beginning. Marks: none.
- O-2 (from SC-2): the spec says the build should make the cloud pick up the advisor's plugin version with no hand step after each release, and the approved journeys leave hands-off upkeep of the setup to the later piece. Recommendation: keep it in this piece as an aim, with the pasted setup text as the fallback the boards already show, because the plugin releases often and each release would otherwise send builds back to the owner's machine until the owner pastes. Marks: none.
- N-1 (statements the author added at spec time, tagged "craft, for your veto", that the owner has not yet seen): FR-18 no owner step between launch and ready PR; FR-27 a cloud builder does not change calibration; FR-31 a build's pushed branch is kept until its PR is merged or closed; FR-32 the same cleanup when a PR is closed unmerged; UFR-7's rule that a review finished before a lapse stays as recorded; UFR-9's rule that a recovery never leaves two builders on one issue; UFR-12 a builder with no answer parks with its work pushed; FR-36's rule that a parked PR closed before the renewal is not sent back; UFR-8's rule that a review that did not run for another reason gets no advice to renew. Recommendation: keep all nine. Marks: none.
