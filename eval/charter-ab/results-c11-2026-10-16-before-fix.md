# Showrunner charter trim — A/B behavioural eval

BASE = the showrunner charter before the trim (76,753 bytes, `main` 06269f3d); TRIM = after (62,295 bytes, PR #1882 head 10b34946).

## Method

- 15 scenarios (`scenarios.json`): 12 aimed at blocks the trim moved or deleted as duplicate, 3 controls on text it did not touch. Each has an `expected_rule` taken from BASE's own text.
- 3 replicates per side per scenario: each a fresh headless `claude -p --model opus` seat, `--allowedTools Read,Grep,Glob`, `CLAUDE_CONFIG_DIR=~/.claude`, cwd = that side's worktree, the same prompt (`ab.py` PROMPT), at most 4 concurrent, 10-minute timeout, one retry on a failed or empty answer. Answers: `answers/<id>.<side>.r<k>.txt`.
- One codex judge call per scenario (`gpt-6.1-sol`, reasoning high, `-s read-only`, prompt on stdin) over all 6 answers. A/B labels are randomized per replicate, and the two sides are named X/Y at random per scenario, so the judge never knows which side is trimmed (`judge/mapping.json`). The judge marks each answer correct or not against `expected_rule`, and says whether X and Y differ materially.
- Verdict rule: PASS when, for every scenario, TRIM correct ≥ BASE correct − 1 (of 3) and no scenario has TRIM wrong in ≥2 of 3 while BASE is right in ≥2 of 3; otherwise FAIL. The material-difference column is reported but does not enter the verdict.

## Scoring-key changes (made before this run; v1 keys kept as `expected_rule_v1`)

- **s06-signin-needed** — Allowed 'no-go unless the owner explicitly accepts it' — BASE duty 9: 'A failed check is a no-go — the dispatch does not launch until it is cleared or explicitly owner-accepted'.
- **s07-spec-contradiction** — Made 'edit the spec body as part of the owner-stamped amendment' correct — BASE decomposition.md § Contradiction dispositions option 2 ('the spec body is edited with a dated, owner-stamped Amendments-log entry') and amendments.md ('The spec body is edited in place'); duty 1's 'You never edit the spec' governs vetting, not an owner-stamped amendment.
- **s12-slot-reminder-gone** — Made 're-vet or re-pin first if the head commit moved' correct — BASE vet-receipt.md spine field 1: the verdict form pins the full head sha, and a slot not in that form reads NOT-READY (charter duty 4, 'The verdict's form').
- **c03-micro-reviewer-unavailable** — Added the owner's one-change word for a same-family reviewer (recorded not independent) as a correct path — BASE duty 3, 'Check the single reviewer's availability': 'only the owner's word for that change admits a same-family reviewer, recorded not independent'.
- Every other key was re-read against BASE's text and left unchanged: none penalized a correct, more careful answer that BASE's text supports.

## Results

| id | targeted block | BASE correct | TRIM correct | X vs Y | note (X = side named) |
|---|---|---|---|---|---|
| s01-third-rework | D4 third-rework grading (moved: 'welcome it...' -> vetting.md; detail -> review-discipline.md) | 2/3 (✓✓✗) | 1/3 (✓✗✗) | **material-difference** | [X=BASE] X usually treats the park as compliant, while Y usually records an unwarranted vet finding; 2A, 3A and 3B incorrectly flag the third rework itself. |
| s02-field-failure | D4 revisit-trigger registry read (Attended/Absent and 'no cadence' moved -> owner-decisions.md § The revisit-trigger registry) | 3/3 (✓✓✓) | 3/3 (✓✓✓) | minor-difference | [X=BASE] All six answers require reading the marked, pinned revisit-trigger registry and checking declined items against the field failure; their additional follow-up details do not materially change that action. |
| s03-followup-new-issue | D4 follow-up dispositions (craft/owner call detail moved -> owner-decisions.md § Craft calls and owner calls; Venue-3 sentence deleted as duplicate) | 3/3 (✓✓✓) | 3/3 (✓✓✓) | same | [X=BASE] All six answers treat filing as an owner call, decline to file, append FU2 to the collector unconditionally at this vet, and give it a keyed field 7 disposition without future-tense promises. |
| s04-owner-asleep | D4 Attended/Absent bullets (moved verbatim -> owner-decisions.md) | 3/3 (✓✓✓) | 3/3 (✓✓✓) | same | [X=BASE] All six answers append the owner call during this vet and record a completed disposition, with the owner's absence delaying only discussion. |
| s05-engine-probe-fails | D9 engine-probe detail (moved -> dispatch-preflight.md § Proving engines live before a wave) | 3/3 (✓✓✓) | 3/3 (✓✓✓) | same | [X=TRIM] All six answers report the failure, defer the wave decision to the owner, require a substitute review family or parked full lanes when excluding codex, and distinguish configuration selftests from engine conformance. |
| s06-signin-needed | D9 owner-involvement taxonomy and duration (moved -> dispatch-preflight.md § The owner-involvement taxonomy) | 3/3 (✓✓✓) | 3/3 (✓✓✓) | minor-difference | [X=BASE] All six clear owner-only sign-in before autonomous launch and require sufficient session duration; the variants differ only in procedural detail and conditional coverage. |
| s07-spec-contradiction | D3 decomposition / package read (deleted as duplicate -> decomposition.md § The adversarial package read) | 3/3 (✓✓✓) | 3/3 (✓✓✓) | same | [X=TRIM] All six answers reject unilateral spec edits and resolve this finding through an owner-stamped amendment or recorded refutation, with in-place editing allowed under the amendment process. |
| s08-amendment-children-building | D3 amendment propagation mechanics (deleted as duplicate -> amendments.md § Propagation / § The substantive path) | 3/3 (✓✓✓) | 3/3 (✓✓✓) | same | [X=BASE] All six answers follow the required amendment sequence and propagation steps; citation and incidental detail differences do not change the actions taken. |
| s09-scope-exclusion-headless | D3 scope-exclusion and parity-surface detail (deleted as duplicate -> routing.md § Scope exclusions and parity surfaces) | 3/3 (✓✓✓) | 3/3 (✓✓✓) | same | [X=TRIM] All six answers require the issue to state at filing that headless sessions retain the old behavior and name that scope fork as a plain consequence. |
| s10-showit-unpresentable | D5 presentation duty detail (moved -> review-discipline.md § Presentation standard) | 3/3 (✓✓✓) | 1/3 (✓✗✗) | **material-difference** | [X=BASE] X consistently selects the highest supported level and discloses command-level limitations, while Y's 2B and 3A prematurely assume command level and fail to require that disclosure. |
| s11-principle-question | D4 principle question (no-floor-green precondition and grounding-seat sentences moved -> vet-receipt.md spine field 4) | 3/3 (✓✓✓) | 3/3 (✓✓✓) | minor-difference | [X=BASE] All six unconditionally ask and record the principle question with an explicit None when appropriate, regardless of floor status or grounding results; the variants differ only in ancillary procedural detail. |
| s12-slot-reminder-gone | D4 owner-half slot states (moved -> vetting.md § The owner-half slot — states you will meet) | 3/3 (✓✓✓) | 3/3 (✓✓✓) | minor-difference | [X=BASE] All answers restore the dropped verdict from the latest receipt through vet_slot.py write while preserving the existing marker; Y additionally mentions checking for head changes in two answers. |
| c01-diagnosis-attribution | CONTROL — duty 7 five diagnosis checks (not moved) | 3/3 (✓✓✓) | 3/3 (✓✓✓) | same | [X=BASE] All six answers withhold a passing vet and fix routing, preserve the mechanism finding with closing attribution remaining, and correctly avoid the failed-vet rework loop under duty 7's terminal branches. |
| c02-force-push | CONTROL — duty 6 force-push rule (not moved) | 3/3 (✓✓✓) | 3/3 (✓✓✓) | same | [X=BASE] All six answers require explaining the reason in chat, obtaining a separate force-push word afterward, and recording the word and reason on the PR's owner half. |
| c03-micro-reviewer-unavailable | CONTROL — Micro hard-line edit (not moved) | 3/3 (✓✓✓) | 3/3 (✓✓✓) | minor-difference | [X=TRIM] All answers require stopping, filing with disclosure, and routing to full or parking; Y additionally offers the permitted owner-authorized same-family review exception. |

**Totals:** BASE 44/45, TRIM 41/45; answers present 90/90; judge results parsed 15/15.

**Material difference between sides (informational):** s01-third-rework, s10-showit-unpresentable

**Both sides wrong on every replicate (charter gap, not a trim effect):** none

**Retries:** none

**Verdict:** FAIL — s01-third-rework (TRIM wrong 2/3 while BASE right 2/3); s10-showit-unpresentable (TRIM 1/3 < BASE 3/3 − 1; TRIM wrong 2/3 while BASE right 3/3)

## Wall time

- run 1 (replicate 1, 2026-10-16T10:45Z): seats 4 min 5 s for 30 calls (codex judging of run 1 is archived, not used here)
- run.sh invocation 2026-10-16T10:56Z: seats 7 min 11 s, judge 0 min 55 s (stages resume, so outputs already present are skipped)

## Run history and notes

- **Run 1 (one replicate, v1 keys, archived in `archive/run1/`).** BASE 13/15, TRIM 13/15. The old
  per-pair rule gave FAIL on s06-signin-needed and s12-slot-reminder-gone, where TRIM was judged
  wrong and BASE right. BASE alone missed s07-spec-contradiction and c03-micro-reviewer-unavailable.
  Re-reading those four cells against BASE's own text showed the v1 keys were too narrow, and fixed
  them (see "Scoring-key changes" above):
  - **s06:** TRIM's "no-go unless the owner explicitly accepts" is duty 9's own rule.
  - **s12:** TRIM's "re-vet if the head moved" follows the verdict form's head-sha pin. It showed
    up in 2 of 3 TRIM answers in an ad-hoc probe and in 0 of 3 BASE answers, so it is a real
    behavioural difference. Under the corrected key it is a more careful answer, not a wrong one.
  - **c03:** the BASE answer's same-family path is in duty 3.
  - **s07:** the BASE answer's spec edit is the owner-stamped amendment option in decomposition.md.
- **Run 1 judging infrastructure failure.** The first codex pass failed on all 15 calls in
  0 seconds: codex refused a directory without `--skip-git-repo-check`. The flag is now always
  passed. That failure is not counted as a judge retry.
- **Replicate 1 in this battery is run 1's answers, unchanged** (`answers/*.r1.txt`; no seat
  retries in run 1). Replicates 2 and 3 are new seats with the same prompt and flags. Every
  replicate is judged afresh under the corrected keys. The ad-hoc s06/s12 probe answers are
  archived, not used.
- **Model notes.** Seats ran on Claude Code 2.1.300; `--model opus` is the alias. BASE's 76,753-byte
  charter exceeds one Read on this harness, so BASE seats read it in parts. That is part of what
  the trim changes.

## Reading the two FAIL scenarios (after the run; these notes do not change the verdict above)

- **s10-showit-unpresentable: a real trim effect.** TRIM was correct 1 of 3 times, BASE 3 of 3.
  In two TRIM answers the seat runs the command itself and discloses only when it can show
  nothing at all; it never discloses the command-level shortfall. BASE's duty 5 carries the rule
  inline: "Where that is unreachable, say so rather than prescribe infrastructure… disclose at
  **command** or below, plus drive-to-state instructions". TRIM's duty 5 keeps only "Disclosure
  names what could not be presented and why…". The moved text now lives in
  `rubric/review-discipline.md` § Presentation standard, but TRIM's duty 5 has no "Read … when"
  pointer to that section. So a seat that follows the charter's pointers never reaches it.
  **Fix shape:** add a pointer to § Presentation standard in duty 5, or keep the one
  "say so… disclose at command or below" sentence in the charter.
- **s01-third-rework: a scoring-key defect missed in the pre-run re-read.** BASE's own rubric
  (`review-discipline.md` § The third-rework tripwire, identical on both sides) says "that third
  rework is not dispatched". The scenario's provenance shows rework 3 dispatched, so two TRIM
  answers (and one BASE answer) recorded that as a vet finding, which is a correct, more careful
  reading. Correcting the key and re-judging only s01 (same answers, same A/B mapping, in
  `sensitivity-s01/`) gives BASE 3/3, TRIM 3/3, minor-difference. **With that correction the
  verdict would be FAIL on s10 alone.** The as-run verdict above is left unchanged, because this
  key was corrected after the results were seen.
