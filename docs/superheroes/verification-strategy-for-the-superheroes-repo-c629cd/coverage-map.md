# Coverage map — verification-strategy package (spec #1105)

**What this is.** The decomposition's ownership record: every acceptance criterion of
[spec.md](spec.md) owned by **exactly one** owner — none unowned, none owned twice — with
consumers listed where a criterion's output is read by other children. Re-allocated 2026-10-02 to
the spec's amendment #5 (the owner's rulings "8 a"–"11 a", record:
https://github.com/zwrose/superheroes/issues/695#issuecomment-5951960566); the round history of
the earlier allocation is in [package-read.md](package-read.md). Contracts between children live in
[contract-register.md](contract-register.md) (cited as R-numbers); this file allocates, the
register binds.

**Reading the tables.** One row per criterion, or per owner-split piece of one; where a
requirement's acceptance bullets split ownership, the rows say so bullet by bullet. The bracketed
numbers are the re-check's item numbers (the last section lists every surviving criterion and
the two must agree item for item). "Consumers" are readers, never co-owners — **a spec bullet that
requires someone to build or check something is owned by that owner**, never listed as consumption.

## Owners

| Owner | Issue | What it is | Status |
| --- | --- | --- | --- |
| `P1` | #1228 | One Python pin, drift-guarded (FR-12, UFR-8) | shipped |
| `P5-vet` | #1233 (live slice) | The vet-checks encoding in the project's vet-checks calibration section, which F3 (#1238) shipped | live |
| `P5-lens` | #1233 (test-lens slice) | The test-lens calibration: FR-18a–g, FR-4b grading | **parked** under the owner's review hold (@373-8) |
| `P7` | #1235 | The first cut list, the plain rail inventory, the keep-list seed | live |
| `P9` | new, unfiled | The mutation run (FR-20) and the red-then-green script — filed on the owner's word | not yet filed |
| **advisor process** | — | Acts the advisor and owner perform at the vet, the gardening pass or a walk; nothing to build | — |
| **shipped elsewhere** | — | A rule that already lives in a shipped surface (the file is named in the row) | — |
| **done in amendment #5** | — | Spec text this amendment itself settled | — |

Lane-1 items F1 (parked), F2 (shipped), F3 (shipped) and PA–PD (parked) are not children of this
spec — its Out-of-scope excludes the plugin-harvest track; they appear here only where a seam
touches a criterion (R4, R11, R22).

## Functional requirements

| Criterion | Owner | Consumers / notes |
| --- | --- | --- |
| [1–5] FR-1 — the four removal bases (requirement) and bullets 1–4: shown to bite, cannot-bite, no-raise is suspect, unassessed is retained | **P7** — the cut list is where the policy first executes | P5-vet (UFR-5 re-run encoding). Shared vocabulary bound as R17 |
| [6] FR-1 — retired-subject bullet | **P7** | P5-vet (UFR-5 vet arm) |
| [7] FR-1 — obsolete-expectation bullet (delete on contact, bounded by the keep list and the classification step) | **shipped elsewhere** — `plugins/superheroes/rubric/review-discipline.md` § A behavior test that goes red | the reset's C3 owns the at-contact step; the reset map's FR-F6 n3 split; R22 |
| [8–10] FR-1 — keep-list bullet, split by act: [8] the seed → **P7**; [9] the stamp and removals → **advisor process** (the owner's acts); [10] growth, the advisor adding a file at a pass → **advisor process** | one row, three criteria | R22 (the reset's R28) |
| [11] FR-2 — requirement: rails exempt from retention decisions based on failure frequency | **P7** | — |
| [12] FR-2 — definition bullet, recognition (the lens flags an undeclared or uninventoried rail by what it tests) | **P5-lens** | lane derivation is held — see Held and declined |
| [13] FR-2 — bullet 2: never removed on a "has not failed" basis; must still satisfy FR-1 | **P7** | P5-vet (UFR-5) |
| [14] FR-3 — requirement: the rail inventory is a plain file; "rails intact" is that inventory | **P7** | R3 |
| [15] FR-3 — bullet 1, seed from `rail-census-v3`, advisor corrections (additions and entry metadata only), the entry lands with the rail | **P7** | R3; P5-lens (FR-18c lens arm), advisor (FR-26 rail exclusion) |
| [16] FR-3 — bullet 1, removal of an inventoried file is a defect unless its bar is met | **P7** — stated in the inventory file's header | P5-vet (UFR-5 vet arm) |
| [17] FR-3 — bullet 2, removing an entry carries the file's bar; the `Rail removed: <entry id>` convention | **P7** — stated in the inventory file's header | R3 |
| [18] FR-3 — bullet 2, the vet's check of the `Rail removed` line when the inventory is in the diff | **P5-vet** | — |
| [19] FR-4b — requirement: a written risk profile; the review crew grades proof depth against it | **P5-lens** | parked |
| [20] FR-4b — bullet 1: the risk-profile table is the normative table, each area names a depth | **P5-lens** | the spec stays the table's home |
| [21] FR-4b — bullet 2: grading rule (Full/Medium finding, Light never higher, unnamed area Medium) | **P5-lens** | — |
| [22] FR-4b — bullet 3: rides the test-lens calibration with a named example finding | **P5-lens** | parked under the review hold |
| [23] FR-4b — bullet 4: the amendment bar (an edit to the table is an amendment; any reducing edit carries the owner's recorded approval; never a lane without a vet) | **P5-lens** | — |
| [24] FR-4b — bullet 4, the vet's check of a reducing edit's owner approval | **P5-vet** | — |
| [25] FR-9 — requirement: the hand-written receipt fields in the PR body | **P5-vet** — the vet-check encoding | R4 |
| [26] FR-9 — bullet 1: attempt-number and prior-red fields make a flake visible; elapsed time | **P5-vet** | R4 |
| [27] FR-9 — bullet 2: `gate-receipt/1` is optional | **shipped elsewhere** — `plugins/superheroes/reference/gate-receipt.md` (F2, PR #1551) | R4 |
| [28] FR-9 — bullet 3: a "local gate passed" claim names its commands and quoted output | **P5-vet** | — |
| [29] FR-12 — requirement: one pin, one home, every runner reads it | **P1** | R7 |
| [30] FR-12 — bullet 1: three versions today; the validator-step check at CI | **P1** | R7 |
| [31] FR-12 — bullet 1, the sentence that the out-of-repo calibration home comes into line by calling `scripts/pinned-python` | **advisor process** — the calibrated verify command lives out of repo | R7 |
| [32–34] FR-12 — bullets 2–4: a single provisioning step; refusal with the park route; shipped by P1 | **P1** | R7 |
| [35] FR-13 — requirement: all six false-green channels dispositioned by name | **done in amendment #5** — the channel list is the disposition | — |
| [36] FR-13 — channel 1, interpreter skew | **P1** | — |
| [37] FR-13 — channel 2, stale bytecode | **P1** | — |
| [38] FR-13 — channel 3, git identity in temp repos | **done in amendment #5** — CI at merge is the handler; nothing to build | — |
| [39] FR-13 — channel 4, engine binaries assumed on `PATH` | **shipped elsewhere** — `plugins/superheroes/agents/test-reviewer.md` (the pre-satisfied-precondition rule); CI catches the codex and cursor case | — |
| [40] FR-13 — channel 5, a harness that pre-satisfies a gate | **shipped elsewhere** — `plugins/superheroes/agents/test-reviewer.md` | — |
| [41] FR-13 — channel 6, a sanitized view that strips a file a seat needs | **shipped elsewhere** — `plugins/superheroes/skills/review-code/reference/auto-fix-loop.md` | — |
| [42] FR-13 — traceability bullet | **done in amendment #5** | — |
| [43] FR-13 — no-retry bullet | **P5-vet** | — |
| [44] FR-14 — requirement: proactive deletion only of cannot-bite tests, evidence carried | **P7** | R17 |
| [45] FR-14 — bullet 1: the first cut list (the finding on a deletion resting on none of the four bases is UFR-5's, counted there) | **P7** | R17 |
| [46] FR-14 — bullet 2: the re-run bar (cannot-bite evidence independently re-run at verification) | **P5-vet** — UFR-5's re-run | R17 |
| [47] FR-14 — bullet 3: surviving mutants are cut-list candidates | **P9** — publishes the survivors | the gardening pass consumes (advisor) |
| [48] FR-15 — requirement: the builder brings the whole touched file to standard | **P5-lens** | — |
| [49] FR-15 — Given-When-Then bullet, the lens arm (no cannot-bite case or duplicate pin remains) | **P5-lens** | — |
| [50] FR-15 — Given-When-Then bullet, the whole-touched-file scope check | **P5-vet** — vet-carried until F1 (R11) | F1 (parked) |
| [51] FR-15 — halt-suspension bullet | **P5-vet** | UFR-6; R11 |
| [52] FR-16 — requirement: mechanical-only changes exempt, listed as burndown debt | **P5-lens** | — |
| [53] FR-16 — bullet: the reviewer verifies mechanical status from the diff | **P5-lens** | — |
| [54] FR-17 — requirement: bulk removal of bite-capable tests is an owner decision on hand counts | **advisor process** — an owner decision at a pass; no checkpoint | — |
| [55] FR-17 — bullet: re-opening bulk removal amends FR-1 | **advisor process** | — |
| [56] FR-18g — the declaration and the stage rule (preamble bullet 1: where each rule is checked follows where its evidence lives) | **P5-lens** | P5-vet carries the vet-stage rules |
| [57] FR-18g — birth bite-proofs (preamble bullet 2, first sentence) | each detector's owner — today **P1**, shipped (the pin check) | — |
| [58] FR-18g — named example findings (preamble bullet 2, second sentence) | **P5-lens** | — |
| [59] FR-18a — requirement: a cannot-bite test added raises a finding | **P5-lens** | — |
| [60] FR-18a — bullet: the finding names the structural class | **P5-lens** | — |
| [61] FR-18b — requirement: a duplicate pin raises a finding naming the rail | **P5-lens** | — |
| [62] FR-18b — bullet: a pin of an unguarded fact is not a finding | **P5-lens** | — |
| [63] FR-18c — requirement, lens arm: an undeclared or uninventoried rail raises a finding | **P5-lens** | R3 |
| [64] FR-18c — bullet: the PR body carries the rail's bite-proof receipt; the vet returns a PR lacking it | **P5-vet** | — |
| [65] FR-18d — requirement: a fix names the change it corrects | **P5-lens** (the rule) | R10 |
| [66] FR-18d — bullet, the rule: "fix" means a correction to merged behavior; the fix PR names the merged change or states the defect pre-dates any single change | **P5-lens** | R10 |
| [67] FR-18d — bullet, the pre-dates claim checked by the vet against the history | **P5-vet** | R10 |
| [68] FR-18e — requirement: no numeric ceiling on test share | **P5-lens** | — |
| [69] FR-18e — bullet: no seat raises a finding on test share alone | **P5-lens** | — |
| [70] FR-18f — requirement: burndown when touched | **P5-lens** | R11 |
| [71] FR-18f — bullet 1: the finding names the remaining case or pin | **P5-lens** | — |
| [72] FR-18f — bullet 2: the vet applies the halt exception | **P5-vet** | UFR-6 |
| [73] Instruments paragraph — the escape rate is the gardening pass's hand count | **shipped elsewhere** — owner-decisions duty 7 (`plugins/superheroes/skills/showrunner/reference/owner-decisions.md`) | no instrument stores it |
| [74] FR-20 — requirement: the mutation run, bought not built, scoped, budgeted, sharded, on demand, advisory; publishes per planted defect its subject file, whether any test detected it, and the killing test file(s) where the tool reports per-test results | **P9** | P1 (the pinned interpreter) |
| [75] FR-20 — bullet 1, results consumed at gardening passes (duty 7 records survivors and kills; an uncovered file reads unmeasured; a survivor is a cut-list candidate) | **advisor process** | P9 publishes; [47] |
| [76] FR-20 — bullet 1, a kill earns the file a keep-list line; a kill with no test-file attribution earns none (the file reads as unmeasured for the keep list) | **advisor process** | [10] |
| [77] FR-20 — bullet 2: a run marks defects it did not re-evaluate "not evaluated"; a budget-exhausted run publishes a marked partial result | **P9** | — |
| [78] The red-then-green script — on demand, no storage, never a gate | **P9** | — |
| [79] FR-23 — requirement: a flake is recorded by hand on the collector when seen | **P5-vet** — the vet-as-recorder encoding | R9 |
| [80] FR-23 — bullet: the note names the test, the run and the date; no CI fold or workflow | **P5-vet** | R9 |
| [81] FR-24 — requirement: a listed flake is a vet finding on a PR touching that test | **P5-vet** | R9 |
| [82] FR-24 — bullet 1: the accepted dispositions | **P5-vet** | R9 |
| [83] FR-24 — bullet 2: loosening or skipping a listed test is a finding; no quarantine, no retry-to-green | **P5-vet** | UFR-4 |
| [84] FR-24 — bullet 3: the flake rate is an on-demand reference, never a gate | **P5-vet** | — |
| [85] FR-26 — requirement: the advisor's withdrawal and the owner path | **advisor process** | R9 |
| [86] FR-26 — bullet 1: an owner-authorized removal is an open coverage obligation with a restore-by date | **advisor process** | R17 |
| [87] FR-26 — bullet 2: a product-cause red-then-green is a product defect; no removal for a rail | **advisor process** | — |
| [88] FR-26 — bullet 3: the decision, date and re-runnable diagnosis evidence recorded on the flake's item | **advisor process** | — |

## Unhappy paths

| Criterion | Owner | Consumers / notes |
| --- | --- | --- |
| [89] UFR-4 — requirement, lens arm (the lens flags the weakening it sees in the diff) | **P5-lens** | — |
| [90] UFR-4 — requirement, vet arm (the vet checks the collector listing) | **P5-vet** | R9 |
| [91] UFR-4 — Given-When-Then bullet: the finding names the listing and the PR is returned | **P5-vet** | — |
| [92] UFR-4 — vetted-lane bullet: a change that weakens an assertion in, adds a skip to, or otherwise edits a listed test takes a lane with a vet, whatever its size | **P5-vet** | UFR-5's vetted-lane rule |
| [93] UFR-5 — requirement, lens arm (the lens flags the deletion or de-listing in the diff) | **P5-lens** | P7 (primary subject), R17 |
| [94] UFR-5 — requirement, vet arm (the body's evidence, the owner's approval, the independent re-run) | **P5-vet** | R17 |
| [95] UFR-5 — vetted-lane bullet: a change that removes a test or edits the inventory takes a lane with a vet | **P5-vet** | — |
| [96] UFR-5 — Given-When-Then bullet: the finding names the test and asks for the evidence | **P5-lens** | — |
| [97] UFR-6 — requirement: the rate read, the hand counts brought to the owner, the removal halt | **advisor process** — the rate read and the owner decision | — |
| [98] UFR-6 — Given-When-Then bullet: the vet parks a proactive removal while the rate reads above the baseline | **P5-vet** | — |
| [99] UFR-6 — baseline-pending bullet: until a hand-count baseline is recorded, the rate reads baseline-pending and no halt fires; the investigation's 17.4% is context only | **advisor process** | — |
| [100] UFR-6 — bullet: a halt lifts only by the owner's recorded decision | **advisor process** | — |
| [101] UFR-7 — requirement: no test-lens receipt means unreviewed | **P5-vet** | — |
| [102] UFR-7 — Given-When-Then bullet: a PR body with no test-lens receipt is returned | **P5-vet** | — |
| [103] UFR-7 — bullet: a review receipt is written by the review run itself | **P5-vet** | — |
| [104] UFR-8 — requirement: CI fails at the validator step before any test on a pin disagreement | **P1** | R7 |
| [105] UFR-8 — Given-When-Then bullet: a PR naming a version in the documented gate fails the drift validator | **P1** | R7 |

## Non-functional requirements, risk profile, presentation

| Criterion | Owner | Consumers / notes |
| --- | --- | --- |
| [106] NFR — nothing degrades invisibly | **P5-vet** | FR-9 receipt |
| [107] NFR — escape rate not raised | **advisor process** | UFR-6 |
| [108] NFR — reproducibility (a handback names the interpreter, matching the pin) | **P5-vet** | P1 (the pin) |
| [109] Risk profile — the normative table, the deepest-row rule, the depth vocabulary | **P5-lens** (grading); the spec stays the table's home | [19]–[24] |
| [110] Coverage table — the Show-it row (Visibility & disclosure → the hand-written receipt) | **P5-vet** | FR-9 |

## Held and declined

| Criterion | Owner | Consumers / notes |
| --- | --- | --- |
| Held and declined (spec § Held and declined) — not surviving criteria | not allocated | each row there carries its registry seed or Spec A FR-F6 change |

## Child dispositions (2026-10-02)

| Issue | Child | Disposition | Citation | Home |
| --- | --- | --- | --- | --- |
| #1228 | P1 | shipped | — | closed |
| #1229 | P2 | close as declined | FR-F6 change 1; registry seeds "the nightly catch-and-escape classifier" and "the flake differential" | — |
| #1230 | P3a | close; held on the registry | FR-F6 change 5 (registry seed "the verification tiers, lanes, and local-tier selection with observation mode"); its named-edit form dropped, FR-B1 | — |
| #1231 | P3b | close; held on the registry | FR-F6 change 5, same seed | — |
| #1232 | P4 | close as declined | FR-F6 change 6, FR-B1 | — |
| #1233 | P5 | rewrite to the amended slice: the vet-checks slice live; its test-lens slice parked under the owner's review hold | ruling @373-8 ("11 a") | Backlog, machinery under the dial |
| #1234 | P6 | close as declined | FR-F6 change 4 (the differential to the registry, seed "the flake differential"; vitals to the guardian); the mutation run moves to P9 | — |
| #1235 | P7 | rewrite to the amended slice: first cut list, plain rail inventory, keep-list seed for the owner's stamp | rulings @373-5, @373-6 | Backlog, machinery under the dial |
| #1236 | F1 | park under the owner's review hold | @373-8 | Backlog, parked |
| #1237 | F2 | shipped (`gate-receipt/1`, optional) | PR #1551 | closed |
| #1238 | F3 | shipped | — | closed |
| #1239 | PA | park under the owner's review hold | @373-8 | Backlog, parked |
| #1240 | PB | park under the owner's review hold (PB's wording reconciled to FR-1's four bases, register doctrine mirrors) | @373-8 | Backlog, parked |
| #1241 | PC | park under the owner's review hold | @373-8 | Backlog, parked |
| #1242 | PD | park under the owner's review hold | @373-8 | Backlog, parked |

P9 (new) is filed on the owner's word, into Backlog as machinery under the dial. The "new verification strategy" milestone is retired (@373-7). The advisor propagates this amendment to the child bodies after merge (amendments.md § Propagation).

## Coverage-map re-check (2026-10-02)

1. FR-1 requirement → P7
2. FR-1 bullet 1 (shown to bite) → P7
3. FR-1 bullet 2 (cannot-bite) → P7
4. FR-1 bullet 3 (no-raise is suspect) → P7
5. FR-1 bullet 4 (unassessed is retained) → P7
6. FR-1 retired-subject bullet → P7
7. FR-1 obsolete-expectation bullet → shipped elsewhere
8. FR-1 keep-list bullet, the seed → P7
9. FR-1 keep-list bullet, the stamp and removals → advisor process
10. FR-1 keep-list bullet, growth → advisor process
11. FR-2 requirement → P7
12. FR-2 definition bullet, recognition → P5-lens
13. FR-2 bullet 2 → P7
14. FR-3 requirement → P7
15. FR-3 bullet 1, seed, corrections and entry-lands-with-the-rail → P7
16. FR-3 bullet 1, removal of an inventoried file → P7
17. FR-3 bullet 2, entry-removal bar and the `Rail removed` convention → P7
18. FR-3 bullet 2, the vet's check of the `Rail removed` line → P5-vet
19. FR-4b requirement → P5-lens
20. FR-4b bullet 1 → P5-lens
21. FR-4b bullet 2 → P5-lens
22. FR-4b bullet 3 → P5-lens
23. FR-4b bullet 4, the amendment bar → P5-lens
24. FR-4b bullet 4, the vet's check of a reducing edit's owner approval → P5-vet
25. FR-9 requirement → P5-vet
26. FR-9 bullet 1 → P5-vet
27. FR-9 bullet 2 (`gate-receipt/1` optional) → shipped elsewhere
28. FR-9 bullet 3 (local-gate claim) → P5-vet
29. FR-12 requirement → P1
30. FR-12 bullet 1 → P1
31. FR-12 bullet 1, the calibration-home sentence → advisor process
32. FR-12 bullet 2 → P1
33. FR-12 bullet 3 → P1
34. FR-12 bullet 4 → P1
35. FR-13 requirement → done in amendment #5
36. FR-13 channel 1 → P1
37. FR-13 channel 2 → P1
38. FR-13 channel 3 → done in amendment #5
39. FR-13 channel 4 → shipped elsewhere
40. FR-13 channel 5 → shipped elsewhere
41. FR-13 channel 6 → shipped elsewhere
42. FR-13 traceability bullet → done in amendment #5
43. FR-13 no-retry bullet → P5-vet
44. FR-14 requirement → P7
45. FR-14 bullet 1 (the first cut list) → P7
46. FR-14 bullet 2 (the re-run bar) → P5-vet
47. FR-14 bullet 3 (survivors as candidates) → P9
48. FR-15 requirement → P5-lens
49. FR-15 Given-When-Then bullet, lens arm → P5-lens
50. FR-15 Given-When-Then bullet, whole-touched-file scope → P5-vet
51. FR-15 halt-suspension bullet → P5-vet
52. FR-16 requirement → P5-lens
53. FR-16 bullet → P5-lens
54. FR-17 requirement → advisor process
55. FR-17 bullet → advisor process
56. FR-18g declaration and stage rule → P5-lens
57. FR-18g birth bite-proofs → each detector's owner (P1, shipped)
58. FR-18g named example findings → P5-lens
59. FR-18a requirement → P5-lens
60. FR-18a bullet → P5-lens
61. FR-18b requirement → P5-lens
62. FR-18b bullet → P5-lens
63. FR-18c requirement, lens arm → P5-lens
64. FR-18c bullet, the vet's body check → P5-vet
65. FR-18d requirement → P5-lens
66. FR-18d bullet, the rule → P5-lens
67. FR-18d bullet, the pre-dates check → P5-vet
68. FR-18e requirement → P5-lens
69. FR-18e bullet → P5-lens
70. FR-18f requirement → P5-lens
71. FR-18f bullet 1 → P5-lens
72. FR-18f bullet 2 (the vet applies the halt exception) → P5-vet
73. Instruments paragraph (hand count) → shipped elsewhere
74. FR-20 requirement → P9
75. FR-20 bullet 1, results consumed at gardening passes → advisor process
76. FR-20 bullet 1, a kill earns a keep-list line → advisor process
77. FR-20 bullet 2 → P9
78. The red-then-green script → P9
79. FR-23 requirement → P5-vet
80. FR-23 bullet → P5-vet
81. FR-24 requirement → P5-vet
82. FR-24 bullet 1 → P5-vet
83. FR-24 bullet 2 → P5-vet
84. FR-24 bullet 3 → P5-vet
85. FR-26 requirement → advisor process
86. FR-26 bullet 1 → advisor process
87. FR-26 bullet 2 → advisor process
88. FR-26 bullet 3 → advisor process
89. UFR-4 requirement, lens arm → P5-lens
90. UFR-4 requirement, vet arm → P5-vet
91. UFR-4 Given-When-Then bullet → P5-vet
92. UFR-4 vetted-lane bullet → P5-vet
93. UFR-5 requirement, lens arm → P5-lens
94. UFR-5 requirement, vet arm → P5-vet
95. UFR-5 vetted-lane bullet → P5-vet
96. UFR-5 Given-When-Then bullet → P5-lens
97. UFR-6 requirement → advisor process
98. UFR-6 Given-When-Then bullet (vet park) → P5-vet
99. UFR-6 baseline-pending bullet → advisor process
100. UFR-6 halt-lift bullet → advisor process
101. UFR-7 requirement → P5-vet
102. UFR-7 Given-When-Then bullet → P5-vet
103. UFR-7 receipt-written-by-the-review-run bullet → P5-vet
104. UFR-8 requirement → P1
105. UFR-8 Given-When-Then bullet → P1
106. NFR nothing degrades invisibly → P5-vet
107. NFR escape rate not raised → advisor process
108. NFR reproducibility → P5-vet
109. Risk profile (table, deepest-row rule, vocabulary) → P5-lens
110. Coverage-table Show-it row → P5-vet

Result: 110 surviving criteria; 110 owned exactly once; 0 unowned; 0 owned twice.
