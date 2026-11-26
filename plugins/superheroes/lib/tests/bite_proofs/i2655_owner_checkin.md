# Bite-proof record: issue 2655, the advisor's owner check-in

Detector: `plugins/superheroes/lib/tests/test_owner_checkin_doctrine_2655.py` (unedited throughout).
Guarded-element set (declared by the order, fixed): E1 to E10, one test function each.

How each proof ran: one neutralization, a targeted edit to doc prose and never to the test; the red run by
exact node id (`scripts/pinned-python -B -m pytest <file>::<test> -q`); the inverse edit; the green run by
the same node id. The order named `-k <name>`; the exact node id was used instead because
`rubric/bite-proof.md` says never `-k`. Raw output below is trimmed to the failing test's name and its
assertion line (the pytest source echo, the long text dump and the `UV_NATIVE_TLS` warning are elided).
No secret, token or private URL appears; nothing was redacted.

`O` = `plugins/superheroes/skills/showrunner/reference/orchestration.md`,
`C` = `plugins/superheroes/skills/showrunner/SKILL.md`,
`R` = `plugins/superheroes/skills/showrunner-resume/SKILL.md`.

Restore receipt for every entry: the restored text was read back by the inverse edit (the edit tool
matched the neutralized text exactly once, and the replacement is quoted in each entry), and the final
whole-file run after the last restore reads `10 passed in 0.23s`.

## E1 cadence

- Element and axis: `O` home, the 30-minute floor sentence and "count from the last note you sent"; axis is the cadence, even when nothing changed.
- Neutralization: `30 minutes, even when nothing` / `changed.**` became `30 minutes, only when something` / `changed.**`.
- Raw red: `FAILED ...::test_e1_cadence` with `AssertionError: E1 cadence: orchestration.md home lacks 'While any lane is live, send the owner a status note at least every 30 minutes, even when nothing changed.'`
- Restore: inverse edit back to `30 minutes, even when nothing` / `changed.**`.
- Raw green: `1 passed in 0.22s`

## E2 shape

- Element and axis: `O` home, the note's shape; axis is what a note carries.
- Neutralization: `its phase and its age (the` became `its phase and its duration (the`.
- Raw red: `FAILED ...::test_e2_shape` with `AssertionError: E2 shape: orchestration.md home lacks 'its phase and its age'`
- Restore: inverse edit back to `its phase and its age (the`.
- Raw green: `1 passed in 0.20s`

## E3 every wake

- Element and axis: `O` home, "Every wake sends the note." and the event-or-timer clause; axis is that a `timer` wake sends the note too.
- Neutralization: `whether an event or the loop's own `timer`` became `whether an event or the loop's own `tick``.
- Raw red: `FAILED ...::test_e3_every_wake` with `AssertionError: E3 every wake: orchestration.md home lacks "whether an event or the loop's own `timer`"`
- Restore: inverse edit back to the `timer` wording.
- Raw green: `1 passed in 0.20s`

## E4 max-seconds bound

- Element and axis: `O` home, the `--max-seconds` bound; axis is a number no larger than 1500.
- Neutralization: `` `--max-seconds` at most 1500 and`` became `` `--max-seconds` at most 2400 and`` (the `--max-total-seconds` bound left at 1500).
- Raw red: `FAILED ...::test_e4_max_seconds_bound` with `AssertionError: E4 max-seconds bound: orchestration.md home states `--max-seconds` at most 2400, over 1500` and `assert 2400 <= 1500`
- Restore: inverse edit back to `at most 1500 and`.
- Raw green: `1 passed in 0.23s`

## E5 max-total-seconds bound

- Element and axis: `O` home, the `--max-total-seconds` bound and the sentence "only `--max-total-seconds` ends the loop"; axis is a number no larger than 1500, independent of E4.
- Neutralization: `most 1500 (25 minutes)` became `most 2400 (25 minutes)` (the `--max-seconds` bound left at 1500).
- Raw red: `FAILED ...::test_e5_max_total_seconds_bound` with `AssertionError: E5 max-total-seconds bound: orchestration.md home states `--max-total-seconds` at most 2400, over 1500` and `assert 2400 <= 1500`
- Restore: inverse edit back to `most 1500 (25 minutes)`.
- Raw green: `1 passed in 0.20s`
- Not separately neutralized: the second leg of E5 (the sentence "only `--max-total-seconds` ends the loop") shares this test function; the order declared E5 as one element, so only the number leg has its own red.

## E6 override

- Element and axis: `O` home, "These values replace the example values in `wave-watch.md`" and "on every host"; axis is that the override holds on every host.
- Neutralization: `on every host;` became `on some hosts;`.
- Raw red: `FAILED ...::test_e6_override` with `AssertionError: E6 override: orchestration.md home lacks 'on every host'`
- Restore: inverse edit back to `on every host;`.
- Raw green: `1 passed in 0.21s`

## E7 not-held report

- Element and axis: `O` home, the not-held report sentence; axis is that the advisor tells the owner the check-in is not held, why, and what clears it.
- Neutralization: `the 30-minute check-in is not held, why, and what clears it` became `the 30-minute check-in is late`.
- Raw red: `FAILED ...::test_e7_not_held_report` with `AssertionError: E7 not-held report: orchestration.md home lacks 'the 30-minute check-in is not held, why, and what clears it'`
- Restore: inverse edit back to the full phrase.
- Raw green: `1 passed in 0.20s`

## E8 charter pointer

- Element and axis: `C` duty 9, the new pointer line; axis is the cadence in brief, the resume-first rule, and the pointer to the home.
- Neutralization: ``runs `showrunner-resume` first, resume point or not:`` became ``runs `showrunner-resume` first, if a resume point exists:``.
- Raw red: `FAILED ...::test_e8_charter_pointer` with `AssertionError: E8 charter pointer: SKILL.md duty 9 lacks 'runs `showrunner-resume` first, resume point or not'`
- Restore: inverse edit back to ``first, resume point or not:``.
- Raw green: `1 passed in 0.20s`
- Not separately neutralized: the other two needles in this test (the cadence phrase and the pointer) share this function; the order declared E8 as one element.

## E9 resume re-arm and note

- Element and axis: `R` Step 6, the new paragraph; axis is arming with the home's ceiling, the note right after the Step 7 report, and the not-held report on line 3.
- Neutralization: `right after the Step 7 report` became `before the Step 7 report`.
- Raw red: `FAILED ...::test_e9_resume_rearm_and_note` with `AssertionError: E9 resume re-arm and note: showrunner-resume SKILL.md Step 6 lacks 'right after the Step 7 report'`
- Restore: inverse edit back to `right after the Step 7 report`.
- Raw green: `1 passed in 0.21s`
- Not separately neutralized: the other needles in this test share this function; the order declared E9 as one element.

## E10 one home

- Element and axis: `C` and `R` whole files must not restate the ceiling number or the note's shape; `O` `# Contents` must list the home. Axis is one home.
- Neutralization (restatement leg): in `C`, `with the check-in ceiling; a restarted` became `with the check-in ceiling of 1500; a restarted`.
- Raw red: `FAILED ...::test_e10_one_home` with `AssertionError: E10 one home: showrunner SKILL.md restates '1500'`
- Restore: inverse edit back to `with the check-in ceiling; a restarted`.
- Raw green: `1 passed in 0.20s`
- Neutralization (contents leg, run on a spare invocation): in `O`, `(#owner-check-in-while-lanes-run)` became `(#owner-checkin)` on the `# Contents` line.
- Raw red: `AssertionError: E10 one home: orchestration.md # Contents lacks the home's entry`
- Restore: inverse edit back to `- [Owner check-in while lanes run](#owner-check-in-while-lanes-run)`; the green is the final whole-file run, `10 passed in 0.23s`.
- Not separately neutralized: the `25 minutes`, `its phase and its age` and `anything answered since the last note` needles, and the same needles in `R`; they share the restatement loop with `1500`, which is the representative.
