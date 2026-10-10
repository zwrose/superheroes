# Spec checks record

- Work item: risk-calibrated-review-that-learns-dec0af
- Author engine and family: claude, anthropic
- Seat: codex, gpt-6.1-sol, xhigh, openai
- Same family: no

## The first review

### Round 1

#### Gap review
- Run directory: /private/tmp/claude-501/-Users-zwrose-superheroes--claude-worktrees-showrunner-resume-30e427/d6064e1d-b3f5-4a78-9db3-4fe1e5265200/scratchpad/spec-checks/r1-gap-run
- Result: real (terminal, ok, 1 attempt, engaged: 30 tool calls, 339.3 s)
- Confirmations: untrusted-provenance-review -> decline-accepted

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| untrusted-provenance-review | Gap review | Nit, line 34: Accept the ruled untrusted-provenance exposure. The accepted exposure on #695 applies: reviews of unknown-provenance code are outside the stated trust model. No finding requests restored prompt-injection hardening. The supplied revisit triggers remain #40 going live or a consuming project reviewing outside contributions. | note | Not a finding: the reviewer confirmed that the threat model's accepted exposure applies. Nothing to fix. | noted |
| gap-001 | Gap review | Important, line 253: Require an affirmative verdict before treating “done” as merge authorization. FR-62 treats a saved merge verdict plus “done” as authorization without specifying the verdict's value. The approved board also offers “Not yet” and tells the owner to say “done” after saving the sheets. An owner who accepts the items, saves “Not yet”, and then finishes the batch satisfies the written authorization rule despite explicitly withholding permission to merge. | craft | Fixed. FR-62 now needs a saved "Merge" verdict, and a saved "Not yet" plus "done" is not the merge word. | fixed in round 1 |
| gap-002 | Gap review | Important, line 112: Reconcile reviewer independence with reviewer-written tests. FR-21–22 require the test role to write a test that remains in the PR after its finding is fixed. Under the Maker definition, that reviewer then becomes a maker of the same change, contradicting FR-18's exclusion of every maker family. This also leaves subsequent fix rounds without a defined valid panel. With two existing maker families, the test role can consume the only remaining registered family. | owner's | Queued for the owner. Recommendation: a reviewer's own break-it tests do not make that reviewer a maker of the change; independence is measured against the models that built and fixed the product code, and the generalist still reads the break-it tests for bloat and false passes. | queued |
| gap-003 | Gap review | Important, line 342: Remove the board's merge-order instructions from the index design. The spec makes the approved board authoritative for design and wording, but its index displays “merges second” and “merges first”. Line 376 explicitly excludes showing merge order on the index. A builder following the board would therefore ship a feature that the core scope excludes. | craft | Fixed the other way round: the approved board wins over the spec. The out-of-scope line about merge order is removed, and FR-45 now says a row shows where the PR falls in the merge order the advisor set. The board is unchanged. | fixed in round 1 |

#### Source check
- Run directory: /private/tmp/claude-501/-Users-zwrose-superheroes--claude-worktrees-showrunner-resume-30e427/d6064e1d-b3f5-4a78-9db3-4fe1e5265200/scratchpad/spec-checks/r1-source-run
- Result: real (terminal, ok, 1 attempt, engaged: 29 tool calls, 266.7 s)
- Approved board, for the source check: docs/superheroes/risk-calibrated-review-that-learns-dec0af/board/build-board.html
- Confirmations: none owed

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| SRC-1 | Source check | Important, line 78: Disclosure is not the ruled alternative to a missing record. This acceptance permits handback without a review record merely by explaining its absence. Its cited ruling requires review-record-or-park. The existing driver mandate also distinguishes specific cited exceptions from unrestricted disclosure. This introduces an unsupported exception to the replacement rule, even though FR-8 would subsequently reject the PR at vet. | craft | Fixed. FR-7's acceptance now reads review-record-or-park with no disclosure-only exception. | fixed in round 1 |
| SRC-2 | Source check | Important, line 176: Saved sheet answers do not satisfy the Canon-only promise. FR-38 allows the record to attribute a decision to the owner without a Canon ruling. The cited promise explicitly requires Canon to hold that ruling. The later receipt requirement says to write answers back to the PR, but does not authorize replacing Canon with saved answers. The record can therefore claim owner acceptance under a weaker condition than its source permits. | owner's | Queued for the owner. Recommendation: an acceptance that concerns one PR is on record in that PR's saved answers, which are written back to the PR; an answer that sets a rule for later work is on record in Canon. FR-38 stays as written until the owner rules. | queued |
| SRC-3 | Source check | Important, line 336: Preserve draft treatment until the owner finishes the sheet. The spec requires saving taps and guards merging with “done,” but never carries forward the standing requirement that sheet answers remain drafts and are read together when the owner finishes. Acting on preliminary answers—for example, recording a permanent acceptance under FR-66—would satisfy this spec while violating the owner's batch-submission rule. | craft | Fixed by a standing ruling. New FR-78 carries Canon 2026-10-05-3dbeb858-39: taps save as drafts, the last tap counts, and the plugin acts on a sheet only after "done". | fixed in round 1 |
| SRC-4 | Source check | Important, line 221: Carry forward the rule for notes that contradict an answer. Optional notes are specified, but their existing conflict rule is absent. An owner could tap “Keep it” while writing that it must be fixed before merge, and the specified acceptance count could still unlock merging. The standing source requires a contradictory note to leave the decision open as Discuss. | craft | Fixed by a standing ruling. New FR-79 carries Canon 2026-10-05-3dbeb858-38: a note that disagrees with its answer makes the question Discuss and the advisor asks. | fixed in round 1 |
| SRC-5 | Source check | Important, line 224: The approved walk includes an advisor run before the owner. FR-53 specifies the owner's walk presentation but omits the approved promise that the advisor walked it first and that its pictures came from that run. A sheet containing unexercised instructions and unrelated pictures could meet every listed acceptance while failing that promise. | craft | Fixed from the board. New FR-80: the advisor walks the stops before the sheet is sent, and the walk says so and where its pictures come from. New UFR-9 covers a stop the advisor could not walk. | fixed in round 1 |
| SRC-6 | Source check | Minor, line 376: The merge-order exclusion contradicts the approved index. The spec expressly excludes showing merge order, while the approved index displays “merges second” and “merges first.” Keeping responsibility for merge order with the advisor does not exclude displaying that order. Under the prescribed board-first precedence, these requirements disagree. | craft | Fixed with gap-003: the spec now follows the approved board on merge order. | fixed in round 1 |
| SRC-7 | Source check | Minor, line 92: Include the setup questions when product purpose is unset. The sitting's question list omits who the product is for and what it is for. FR-12 handles an existing who-it's-for answer, but no requirement covers establishing either answer when absent. A new project could complete the specified sitting without the first step of the approved setup. | craft | Fixed. FR-11's acceptance now starts with who the product is for and what it is for. | fixed in round 1 |
| SRC-8 | Source check | Minor, line 257: Retain the promised revisit date on leftover follow-ups. The acceptance requires a follow-up carrying the owner's note, but omits its revisit date. The approved explanation of “Fix in a follow-up” promises an issue with that date. An undated issue would satisfy FR-63 while delivering less than the option tells the owner they are choosing. | craft | Fixed. FR-63 now says a leftover's follow-up carries a date to revisit it. | fixed in round 1 |
| SRC-9 | Source check | Minor, line 187: Require the batch-1 chat link to the index. FR-41 requires duplicating the question in chat and on the index, but omits the link between them. A chat question with no route to its index would pass the acceptance while omitting the approved handoff to the visual decision surface. | craft | Fixed. FR-41 now says the chat links to the index. | fixed in round 1 |

#### Grounding
- Run directory: /private/tmp/claude-501/-Users-zwrose-superheroes--claude-worktrees-showrunner-resume-30e427/d6064e1d-b3f5-4a78-9db3-4fe1e5265200/scratchpad/spec-checks/r1-grounding-run
- Result: real (terminal, ok, 1 attempt, engaged: 44 tool calls, 140.2 s)
- Grounding base, for grounding: origin/main, 48a7881e07318177c598deadef2d8bbf96d4894d
- Confirmations: none owed

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| none | Grounding | no new findings | | | |

#### Citation check
[]

### Round 2

#### Gap review
- Run directory: /private/tmp/claude-501/-Users-zwrose-superheroes--claude-worktrees-showrunner-resume-30e427/d6064e1d-b3f5-4a78-9db3-4fe1e5265200/scratchpad/spec-checks/r2-gap-run
- Result: real (terminal, ok, 1 attempt, engaged: 29 tool calls, 359.7 s)
- Confirmations: gap-001 -> fixed; gap-003 -> fixed

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| gap-004 | Gap review | Important, line 328: Define the merge outcome when a required reviewer cannot run. In this specialist-failure scenario, the record can exist, final-commit CI can be green, and the reviewers that ran can leave no findings. FR-8's stated readiness checks and FR-58's unlock conditions then have no explicit failure, while UFR-3 requires only a disclosure inside the folded “How the review went” part. The spec does not settle whether this PR must remain unready or whether the owner must expressly accept the missing required review. A builder can therefore offer the ordinary Merge-plus-done path despite the incomplete panel required by FR-16. | craft | Fixed, following the plugin's standing rule on degraded checks. UFR-3 now says the vet does not return the PR as ready, the PR stays parked until the missing review runs or the owner says in plain words to go ahead, and the sheet then names the review that did not run. | fixed in round 2 |

#### Source check
- Run directory: /private/tmp/claude-501/-Users-zwrose-superheroes--claude-worktrees-showrunner-resume-30e427/d6064e1d-b3f5-4a78-9db3-4fe1e5265200/scratchpad/spec-checks/r2-source-run
- Result: real (terminal, ok, 1 attempt, engaged: 22 tool calls, 232.3 s)
- Approved board, for the source check: docs/superheroes/risk-calibrated-review-that-learns-dec0af/board/build-board.html
- Confirmations: SRC-1 -> fixed; SRC-3 -> fixed; SRC-4 -> fixed; SRC-5 -> fixed; SRC-6 -> fixed; SRC-7 -> fixed; SRC-8 -> fixed; SRC-9 -> fixed

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| SRC-10 | Source check | Important, line 160: The framing does not authorize prohibiting broader re-review. FR-33 categorically prohibits reviewing the whole change after a fix, but its cited framing only promises a fixer scoped to its finding; it does not restrict subsequent review coverage. The existing round contract uses delta rounds with exceptions for Critical findings, cross-cutting rework and an unknown changed surface. This requirement would remove those exceptions without an approved source, changing review coverage rather than merely retaining the scoped fixer. | craft | Fixed. FR-33 now says the next round focuses on the fix and no longer forbids a wider look; a round that looks wider says why in the record. Its source is now marked as the author's choice, for the owner's veto. | fixed in round 2 |
| SRC-11 | Source check | Minor, line 187: Batch-1 decision visuals are not carried into the requirements. The batch-1 ruling requires visuals on the index, but FR-41 specifies only the question's placement and chat link. The picture requirements concern PR sheets and walks; none requires relevant visuals for a blocking index question. A text-only blocking question could satisfy the spec while omitting the visual context the owner ruled should accompany it. | craft | Fixed from the ruling and a standing ruling. FR-41 now says the index shows the pictures that bear on a batch-1 question. | fixed in round 2 |
| SRC-12 | Source check | Minor, line 380: The handback policy loses its ruled revisit trigger. The spec retains the no-automated-handback-gate decision but omits its explicit contingency: revisit that choice if vets start bouncing PRs for missing records. FR-8 specifies rejection, while learning requirements concern escapes and reviewer evidence; neither carries this trigger. Repeated missing-record bounces could therefore continue without the reconsideration the owner required. | craft | Fixed. Constraints now carries the revisit trigger from Canon 2026-10-08-d6064e1d-18. | fixed in round 2 |

#### Grounding
- Run directory: /private/tmp/claude-501/-Users-zwrose-superheroes--claude-worktrees-showrunner-resume-30e427/d6064e1d-b3f5-4a78-9db3-4fe1e5265200/scratchpad/spec-checks/r2-grounding-run
- Result: real (terminal, ok, 1 attempt, engaged: 19 tool calls, 116.0 s)
- Grounding base, for grounding: origin/main, 48a7881e07318177c598deadef2d8bbf96d4894d
- Confirmations: none owed

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| none | Grounding | no new findings | | | |

#### Citation check
[]

### Round 3

#### Gap review
- Run directory: /private/tmp/claude-501/-Users-zwrose-superheroes--claude-worktrees-showrunner-resume-30e427/d6064e1d-b3f5-4a78-9db3-4fe1e5265200/scratchpad/spec-checks/r3-gap-run
- Result: real (terminal, ok, 1 attempt, engaged: 17 tool calls, 166.0 s)
- Confirmations: gap-001 -> fixed; gap-003 -> fixed; gap-004 -> fixed

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| none | Gap review | no new findings | | | |

#### Source check
- Run directory: /private/tmp/claude-501/-Users-zwrose-superheroes--claude-worktrees-showrunner-resume-30e427/d6064e1d-b3f5-4a78-9db3-4fe1e5265200/scratchpad/spec-checks/r3-source-run
- Result: real (terminal, ok, 1 attempt, engaged: 17 tool calls, 86.0 s)
- Approved board, for the source check: docs/superheroes/risk-calibrated-review-that-learns-dec0af/board/build-board.html
- Confirmations: SRC-10 -> fixed; SRC-11 -> fixed; SRC-12 -> fixed

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| none | Source check | no new findings | | | |

#### Grounding
- Run directory: /private/tmp/claude-501/-Users-zwrose-superheroes--claude-worktrees-showrunner-resume-30e427/d6064e1d-b3f5-4a78-9db3-4fe1e5265200/scratchpad/spec-checks/r3-grounding-run
- Result: real (terminal, ok, 1 attempt, engaged: 19 tool calls, 130.3 s)
- Grounding base, for grounding: origin/main, 48a7881e07318177c598deadef2d8bbf96d4894d
- Confirmations: none owed

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| none | Grounding | no new findings | | | |

#### Citation check
[]

Round 3 closed the first review: all three checks returned real results, confirmed every earlier
fix, and raised nothing new. Two items wait in the owner's queue.

## Writing pass

- What the pass changed: three statements. The list of artboards in UI / UX became a bulleted list, the first line of Definition of done became two sentences and now names the saved "Merge" verdict, and the last sentence of UFR-3's second acceptance was split in two.
- Meaning check: run directory /private/tmp/claude-501/-Users-zwrose-superheroes--claude-worktrees-showrunner-resume-30e427/d6064e1d-b3f5-4a78-9db3-4fe1e5265200/scratchpad/spec-checks/meaning-run1. Result: real (terminal, ok, 1 attempt, engaged). Findings: meaning-001, meaning-002 and meaning-003, each meaning:kept. Every changed statement has exactly one finding.
- The pass was kept.

## After rulings 1

### Round 1

The owner answered remainder sheet 1 on 2026-10-10. The checks re-ran on the parts the rulings changed.

#### Gap review
- Run directory: /private/tmp/claude-501/-Users-zwrose-superheroes--claude-worktrees-showrunner-resume-30e427/d6064e1d-b3f5-4a78-9db3-4fe1e5265200/scratchpad/spec-checks/r4-gap-run
- Result: real (terminal, ok, 1 attempt, engaged: 9 tool calls, 67.9 s)
- Confirmations: gap-002 -> fixed

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| none | Gap review | no new findings | | | |

#### Source check
- Run directory: /private/tmp/claude-501/-Users-zwrose-superheroes--claude-worktrees-showrunner-resume-30e427/d6064e1d-b3f5-4a78-9db3-4fe1e5265200/scratchpad/spec-checks/r4-source-run
- Result: real (terminal, ok, 1 attempt, engaged: 7 tool calls, 57.4 s)
- Approved board, for the source check: docs/superheroes/risk-calibrated-review-that-learns-dec0af/board/build-board.html
- Confirmations: SRC-2 -> fixed

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| none | Source check | no new findings | | | |

#### Grounding
- Run directory: /private/tmp/claude-501/-Users-zwrose-superheroes--claude-worktrees-showrunner-resume-30e427/d6064e1d-b3f5-4a78-9db3-4fe1e5265200/scratchpad/spec-checks/r4-grounding-run
- Result: real (terminal, ok, 1 attempt, engaged: 9 tool calls, 76.2 s)
- Grounding base, for grounding: origin/main, 48a7881e07318177c598deadef2d8bbf96d4894d
- Confirmations: none owed

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| none | Grounding | no new findings | | | |

#### Citation check
[]

This round closed the cycle: all three checks returned real results, the two reviewers confirmed the rulings were carried in right, and none raised anything new.

## After vet round 1

### Round 1

The advisor's vet, round 1, raised 23 craft findings and 3 owner calls. The craft findings were fixed in the spec and the requirements renumbered into document order. The checks re-ran on the changed parts, with the journeys board and the vet record added to the source check's inputs.

#### Gap review
- Run directory: /private/tmp/claude-501/-Users-zwrose-superheroes--claude-worktrees-showrunner-resume-30e427/d6064e1d-b3f5-4a78-9db3-4fe1e5265200/scratchpad/spec-checks/r5-gap-run
- Result: real (terminal, ok, 1 attempt, engaged: 31 tool calls, 275.2 s)
- Confirmations: none owed

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| gap-read-evidence-unknown | Gap review | Important, line 124: Cover unknown read evidence in the retry rule. The new retry rule requires an engine record showing that the reviewer did not read the change, but the retained engine evidence distinguishes only `engaged` from `unknown` and expressly never proves inaction. A completed review with empty findings, an accepted investigated path and unavailable tool telemetry can return `ok: true` with reading still unknown. After the planted probe retires, this reachable case has no specified retry or escalation outcome, although it cannot satisfy FR-18's requirement to demonstrate reading. Builders must choose between an unspecified recovery and accepting insufficient evidence. | craft | Fixed. FR-18's acceptance now turns on an engine record that does not show the reviewer read the change, so a missing or unknown reading takes the same retry and move-up path as a known failure to read. | fixed in round 1 of this cycle |

#### Source check
- Run directory: /private/tmp/claude-501/-Users-zwrose-superheroes--claude-worktrees-showrunner-resume-30e427/d6064e1d-b3f5-4a78-9db3-4fe1e5265200/scratchpad/spec-checks/r5-source-run
- Result: real (terminal, ok, 1 attempt, engaged: 41 tool calls, 395.3 s)
- Approved board, for the source check: docs/superheroes/risk-calibrated-review-that-learns-dec0af/board/build-board.html
- Confirmations: none owed

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| none | Source check | no new findings | | | |

#### Grounding
- Run directory: /private/tmp/claude-501/-Users-zwrose-superheroes--claude-worktrees-showrunner-resume-30e427/d6064e1d-b3f5-4a78-9db3-4fe1e5265200/scratchpad/spec-checks/r5-grounding-run
- Result: real (terminal, ok, 1 attempt, engaged: 32 tool calls, 249.4 s)
- Grounding base, for grounding: origin/main, 48a7881e07318177c598deadef2d8bbf96d4894d
- Confirmations: none owed

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| none | Grounding | no new findings | | | |

#### Citation check
[]
