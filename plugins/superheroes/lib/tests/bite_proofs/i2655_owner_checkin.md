# Bite-proof record: the advisor's owner check-in home

Detector: `plugins/superheroes/lib/tests/test_owner_checkin_doctrine_2655.py` (unedited throughout).

The detector pins structure only (`rubric/review-discipline.md` § The pin rule): the home heading,
its Contents entry, and the two citations of the home. An earlier version pinned the home's
sentences and numbers; review round 1 found that it broke the pin rule, so it was cut back to
structure, and this record replaces that version's record.

Guarded-element set (fixed): S1 home heading, S2 Contents entry, S3 charter duty 9 citation,
S4 showrunner-resume Step 6 citation.

How the proof ran: each neutralization was a targeted edit to doc prose with the edit tool, never to
the test. All four ran in one red run on distinct sites, and each red names its own element. Each was
undone by the inverse edit, and the green is the whole-file run after the restore with a clean
`git status --short`. Command: `scripts/pinned-python -B -m pytest <the detector> -q --tb=line`.
Raw output is trimmed to each failing test's name and its assertion line. Nothing was redacted.

`O` = `plugins/superheroes/skills/showrunner/reference/orchestration.md`,
`C` = `plugins/superheroes/skills/showrunner/SKILL.md`,
`R` = `plugins/superheroes/skills/showrunner-resume/SKILL.md`.

## S1 home heading

- Element and axis: `O`, `## Owner check-in while lanes run` as a real level-2 heading, once, outside any code fence.
- Neutralization (name): `## Owner check-in while lanes run` became `## Owner check-ins while lanes run`.
- Raw red: `FAILED ...::test_home_heading_exists_once` with `AssertionError: orchestration.md must carry '## Owner check-in while lanes run' once` (`assert 0 == 1`).
- Neutralization (fence, a separate run): the heading wrapped in a `markdown` code fence.
- Raw red: `1 failed, 3 passed`, `FAILED ...::test_home_heading_exists_once` with the same assertion line.
- Restore: inverse edits back to the bare heading.

## S2 Contents entry

- Element and axis: `O` `# Contents`, the link `[Owner check-in while lanes run](#owner-check-in-while-lanes-run)`.
- Neutralization: the anchor `(#owner-check-in-while-lanes-run)` became `(#owner-checkin)`.
- Raw red: `FAILED ...::test_contents_lists_home` with `AssertionError: orchestration.md # Contents lacks the home's entry`.
- Restore: inverse edit back to `(#owner-check-in-while-lanes-run)`.

## S3 charter duty 9 citation

- Element and axis: `C` duty 9, the citation `orchestration.md` § Owner check-in while lanes run.
- Neutralization: `§ Owner check-in while lanes run.**` became `§ Liveness sweep and wave watch.**`.
- Raw red: `FAILED ...::test_charter_duty_9_cites_home` with `AssertionError: showrunner SKILL.md duty 9 does not cite the check-in home`.
- Restore: inverse edit back to `§ Owner check-in while lanes run.**`.

## S4 resume Step 6 citation

- Element and axis: `R` Step 6, the citation `orchestration.md` § Owner check-in while lanes run.
- Neutralization: `§ Owner check-in while lanes run, in place` became `§ Liveness sweep and wave watch, in place`.
- Raw red: `FAILED ...::test_resume_step_6_cites_home` with `AssertionError: showrunner-resume SKILL.md Step 6 does not cite the check-in home`.
- Restore: inverse edit back to `§ Owner check-in while lanes run, in place`.

## Green

After every restore: `4 passed`, and `git status --short` clean.
