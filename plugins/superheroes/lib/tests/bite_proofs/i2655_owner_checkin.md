# Bite-proof record: the advisor's owner check-in home

Detector: `plugins/superheroes/lib/tests/test_owner_checkin_doctrine_2655.py` (unedited throughout).

The detector pins structure only (`rubric/review-discipline.md` § The pin rule): the home heading,
its Contents entry, and the two citations of the home. An earlier version pinned the home's
sentences and numbers; review found that it broke the pin rule, so it was cut back to structure, and
this record replaces that version's record. Headings are read with `lib/md_hidden.py`, so a heading
inside a code fence or an HTML comment does not count.

Guarded-element set (fixed): S1 home heading, S2 Contents entry, S3 charter duty 9 citation,
S4 showrunner-resume Step 6 citation.

How the proof ran: one neutralization at a time, a targeted edit to doc prose with the edit tool,
never to the test; one red run; the inverse edit; then the next. S2 to S4 ran the whole file, so each
red shows the other three tests still green (`1 failed, 3 passed`): the red is that mutation's alone.
Command: `scripts/pinned-python -B -m pytest <the detector>[::<test>] -q --tb=line`. Raw output is
trimmed to the failing test's name and its assertion line. Nothing was redacted.

`O` = `plugins/superheroes/skills/showrunner/reference/orchestration.md`,
`C` = `plugins/superheroes/skills/showrunner/SKILL.md`,
`R` = `plugins/superheroes/skills/showrunner-resume/SKILL.md`.

## S1 home heading

- Element and axis: `O`, `## Owner check-in while lanes run` as a level-2 heading that renders visible, once.
- Neutralization (fence): the heading placed inside a four-backtick `markdown` fence, after a line of three backticks
  (a shorter run that does not close the fence).
- Raw red: `FAILED ...::test_home_heading_exists_once` with `AssertionError: orchestration.md must carry '## Owner check-in while lanes run' once` (`1 failed`).
- Restore: inverse edit back to the bare heading. Green: `1 passed`.
- After the guard was changed to drop only a heading the scanner reads `HIDDEN` (an `UNSURE` one, after a footnote or a
  reference definition, counts), the fence probe was run again: `1 failed, 3 passed`, the same assertion line.
- Neutralization (duplicate after a footnote, a separate run): a footnote definition `[^probe]: …` and a second
  `## Owner check-in while lanes run` inserted before `## Lapsed-pass parks and the send-back`.
- Raw red: `FAILED ...::test_home_heading_exists_once` with the same assertion line (`1 failed, 3 passed`).
- Restore: inverse edit removing both lines. Green: `4 passed`.
- Neutralization (name): `## Owner check-in while lanes run` became `## Owner check-ins while lanes run`.
- Raw red: `FAILED ...::test_home_heading_exists_once` with the same assertion line (`1 failed`).
- Restore: inverse edit back to the heading.

## S2 Contents entry

- Element and axis: `O` `# Contents`, the link `[Owner check-in while lanes run](#owner-check-in-while-lanes-run)`.
- Neutralization: the anchor `(#owner-check-in-while-lanes-run)` became `(#owner-checkin)`.
- Raw red: `FAILED ...::test_contents_lists_home` with `AssertionError: orchestration.md # Contents lacks the home's entry` (`1 failed, 3 passed`).
- Restore: inverse edit back to `(#owner-check-in-while-lanes-run)`.

## S3 charter duty 9 citation

- Element and axis: `C` duty 9, the citation `orchestration.md` § Owner check-in while lanes run.
- Neutralization: `§ Owner check-in while lanes run.**` became `§ Liveness sweep and wave watch.**`.
- Raw red: `FAILED ...::test_charter_duty_9_cites_home` with `AssertionError: showrunner SKILL.md duty 9 does not cite the check-in home` (`1 failed, 3 passed`).
- Restore: inverse edit back to `§ Owner check-in while lanes run.**`.

## S4 resume Step 6 citation

- Element and axis: `R` Step 6, the citation `orchestration.md` § Owner check-in while lanes run.
- Neutralization: `§ Owner check-in while lanes run, in place` became `§ Liveness sweep and wave watch, in place`.
- Raw red: `FAILED ...::test_resume_step_6_cites_home` with `AssertionError: showrunner-resume SKILL.md Step 6 does not cite the check-in home` (`1 failed, 3 passed`).
- Restore: inverse edit back to `§ Owner check-in while lanes run, in place`.

## Green

After every restore: `4 passed`, and `git status --short` clean.
