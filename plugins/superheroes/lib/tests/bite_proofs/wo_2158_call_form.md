# Bite-proof record: wo-2158 call form (#2158)

Detectors under proof:

- `plugins/superheroes/lib/tests/test_skill_helper_call_form_2158.py` (census, forbidden forms, render-and-decide)
- `plugins/superheroes/lib/tests/test_calibration_root_caller_census.py` (halting-comment rule)
- `plugins/superheroes/lib/tests/test_presence_flag_retired.py` (plain-call decide-location shape)

Declared guarded-element set (from the order): G1 through G9 and the planted defect. Where the order
named several tokens inside one element (G1: `$`, continuation, script token; G2: `$ROOT_DIR` form,
`--session-dir $SESSION_DIR`; G4: the not-approved direction and the excluded flags; G5: the `halt`
word and the next-line acceptance; G7: empty and below-floor; G8: `run-verify` and `rule`; G9: the
halting rule and the admission rule) each token got its own neutralization and its own red, except
where marked unproven.

Method: every neutralization is one Edit on the detector file (or, for the planted defect, on the real
skill doc); every restore is the inverse Edit. No `git checkout`, `git restore`, `git reset`, `git stash`.
Each run is `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest <exact node id> -q`
from `/home/user/wt-2158`, with the detector unedited. Several neutralizations on the same file ran in
sequence: the Edit that restored one element was followed by the Edit that neutralized the next, and
one green command per file after the last restore covers every node that went red (the green
commands are listed under "Greens"). The restore receipt for each element is the restored line
quoted below. The shared `warning: The UV_NATIVE_TLS ...` first line of every run is tool noise and is
omitted from the tails. Receipts hold no secrets, tokens or private URLs; nothing was redacted.

Node-id prefixes: `T1` = `plugins/superheroes/lib/tests/test_skill_helper_call_form_2158.py`,
`T2` = `plugins/superheroes/lib/tests/test_calibration_root_caller_census.py`,
`T3` = `plugins/superheroes/lib/tests/test_presence_flag_retired.py`.

## G1: call-form shape check (`_shape_problems`)

Axis: a call form's own text must have no `$`, no trailing backslash continuation, and the exact script
token `python3 -B <plugin root>/lib/<name>.py`. Red node (all three): `T1::test_shape_check_flags_variable_and_continuation_forms`.

### G1a: the `$` check

- Neutralization: `if "$" in text:` became `if "$never" in text:`.
- Red tail:
  ```
  >       assert "contains $" in problems
  E       AssertionError: assert 'contains $' in ['ends in a backslash continuation', 'script token is not exactly `python3 -B <plugin root>/lib/<name>.py`']
  1 failed in 0.20s
  ```
- Restore: inverse Edit. Restore receipt: `    if "$" in text:` followed by `        problems.append("contains $")`.

### G1b: the continuation check

- Neutralization: `if text.rstrip().endswith("\\"):` became `if text.rstrip().endswith("\\never"):`.
- Red tail:
  ```
  >       assert "ends in a backslash continuation" in problems
  E       AssertionError: assert 'ends in a backslash continuation' in ['contains $', 'script token is not exactly `python3 -B <plugin root>/lib/<name>.py`']
  1 failed in 0.70s
  ```
- Restore: inverse Edit. Restore receipt: `    if text.rstrip().endswith("\\"):` followed by `        problems.append("ends in a backslash continuation")`.

### G1c: the script-token check

- Neutralization: `if _FORM_HEAD.match(text) is None:` became `if False and _FORM_HEAD.match(text) is None:`.
- Red tail:
  ```
  >       assert any("script token" in p for p in problems)
  E       assert False
  1 failed in 0.25s
  ```
- Restore: inverse Edit. Restore receipt: `    if _FORM_HEAD.match(text) is None:` followed by `        problems.append("script token is not exactly ...")`.

## G2: forbidden-form check (`_forbidden_hits`)

Axis: a shell-variable form of one of the nine scripts, on a merged logical line, is reported.
Red node (both): `T1::test_forbidden_form_check_flags_a_reintroduced_multiline_block`.

### G2a: the `"$ROOT_DIR/lib/<nine>.py"` form

- Neutralization: `if _FORBIDDEN_ROOT_DIR.search(line):` became `if False and _FORBIDDEN_ROOT_DIR.search(line):`.
- Red tail:
  ```
  >       assert any("fake.md:2: $ROOT_DIR form" in h for h in hits), hits
  E       AssertionError: ['fake.md:2: hook-approved script with --session-dir $SESSION_DIR']
  1 failed in 0.13s
  ```
- Restore: inverse Edit. Restore receipt: `        if _FORBIDDEN_ROOT_DIR.search(line):`.

### G2b: the `--session-dir "$SESSION_DIR"` form

- Neutralization: `if _NAMES_NINE.search(line) and _SESSION_DIR_VAR.search(line):` became the same with `False and ` in front.
- Red tail:
  ```
  >       assert any("fake.md:2: hook-approved script with --session-dir" in h for h in hits), hits
  E       AssertionError: ['fake.md:2: $ROOT_DIR form of a hook-approved script']
  1 failed in 0.13s
  ```
- Restore: inverse Edit. Restore receipt: `        if _NAMES_NINE.search(line) and _SESSION_DIR_VAR.search(line):`.

## G3: render-and-decide approve check (`_judge`, approve direction)

Axis: a form the contract says the hook approves, but the hook does not, is reported as a miss.
- Neutralization: `if expected and not approved:` became `if False and expected and not approved:`.
- Red node: `T1::test_judge_reports_a_form_the_hook_does_not_approve`.
- Red tail:
  ```
  >       assert miss is not None and "not approved but must be" in miss, miss
  E       AssertionError: None
  E       assert (None is not None)
  1 failed in 0.18s
  ```
- Restore: inverse Edit. Restore receipt: `    if expected and not approved:`.

## G4: excluded forms asserted unapproved

Axis: `run-verify`, `rule` and a `round_driver.py` call carrying `--verify-command`,
`--break-it-interpreter` or `--records-path` must be left to the normal permission check.
Red node (both): `T1::test_excluded_driver_forms_are_asserted_unapproved` (all five parametrizations).

### G4a: the approved-but-must-not-be direction of `_judge`

- Neutralization: `if not expected and approved:` became `if False and not expected and approved:`.
- Red tail (all five forms fail; each fails on the same assertion):
  ```
  >       assert miss is not None and "approved but must NOT be" in miss, miss
  E       AssertionError: None
  E       assert (None is not None)
  FAILED ...::test_excluded_driver_forms_are_asserted_unapproved[run-verify --session-dir <session dir>]
  FAILED ...::test_excluded_driver_forms_are_asserted_unapproved[rule --session-dir <session dir> --ruling-file <rulings file> --by '<who>']
  FAILED ...::test_excluded_driver_forms_are_asserted_unapproved[next --session-dir <session dir> --verify-command '<verify command, or none>']
  FAILED ...::test_excluded_driver_forms_are_asserted_unapproved[next --session-dir <session dir> --break-it-interpreter=<value>]
  FAILED ...::test_excluded_driver_forms_are_asserted_unapproved[next --session-dir <session dir> --records-path <records file>]
  5 failed in 0.15s
  ```
- Restore: inverse Edit. Restore receipt: `    if not expected and approved:`.

### G4b: the excluded-flag table in `_expected_approved`

- Neutralization: `_UNAPPROVED_DRIVER_FLAGS = ("--verify-command", "--break-it-interpreter", "--records-path")` became `_UNAPPROVED_DRIVER_FLAGS = ()`.
- Red tail (the three flag forms fail; the `run-verify` and `rule` forms still pass):
  ```
  >       assert _expected_approved(form) is False
  E       assert True is False
  E        +  where True = _expected_approved("python3 -B <plugin root>/lib/round_driver.py next --session-dir <session dir> --verify-command '<verify command, or none>'")
  3 failed, 2 passed in 0.14s
  ```
- Restore: inverse Edit. Restore receipt: `_UNAPPROVED_DRIVER_FLAGS = ("--verify-command", "--break-it-interpreter", "--records-path")`.
- Disclosure: the first G4b run was displayed through a `grep -v` that dropped source-context lines; it
  was re-run unfiltered and the unfiltered output is the one above. The first G4a run was likewise
  displayed through a `grep`, and was re-run unfiltered.

## G5: calibration census halting-comment rule (`T2`, `_halting_comment` and `_scan_shell_text_violations`)

Axis: a plain `calibration_resolve.py resolve` call counts as handled only when the next logical line
is a `#` comment naming a non-zero exit and a halt.

### G5a: the `halt` requirement

- Neutralization: `return stripped.startswith("#") and "non-zero exit" in stripped and "halt" in stripped` became the same without `and "halt" in stripped`.
- Red node: `T2::test_shell_census_comment_without_halt_is_not_a_handler`.
- Red tail:
  ```
  >       assert handled == 0
  E       assert 1 == 0
  1 failed in 0.12s
  ```
- Restore: inverse Edit. Restore receipt: `    return stripped.startswith("#") and "non-zero exit" in stripped and "halt" in stripped`.

### G5b: the next-line acceptance

- Neutralization: `elif idx + 1 < len(lines) and _halting_comment(lines[idx + 1]):` became the same with `False and ` after `elif`.
- Red nodes: `T2::test_shell_census_next_line_halting_comment_clean` and the real census `T2::test_shell_census_no_fall_open_on_calibration_resolve`.
- Red tail:
  ```
  >       assert handled == 1
  E       assert 0 == 1
  E           RuntimeError: Calibration-root shell census population collapsed: derived zero calibration_resolve.py invocations with handlers from /home/user/wt-2158/plugins/superheroes/skills
  2 failed in 0.13s
  ```
- Restore: inverse Edit. Restore receipt: `            elif idx + 1 < len(lines) and _halting_comment(lines[idx + 1]):`.

## G6: unreplaced-placeholder check before `decide` (`_judge`)

Axis: a form with a leftover `<` or `>` after rendering is reported, never handed to the hook.
- Neutralization: `if "<" in rendered or ">" in rendered:` became `if False and ("<" in rendered or ">" in rendered):`.
- Red node: `T1::test_an_unreplaced_placeholder_is_never_approved`.
- Red tail:
  ```
  >       assert miss is not None and "unreplaced placeholder" in miss, miss
  E       AssertionError: None
  E       assert (None is not None)
  1 failed in 0.15s
  ```
- Restore: inverse Edit. Restore receipt: `    if "<" in rendered or ">" in rendered:`.

## G7: empty-population and below-floor failure (`_population_problems`)

Axis: the census population must be non-empty and at least `POPULATION_FLOOR`.

### G7a: empty population

- Neutralization: `if not forms:` became `if False and not forms:`.
- Red node: `T1::test_population_check_fails_an_empty_population`.
- Red tail:
  ```
  >       assert any("empty population" in p for p in problems), problems
  E       AssertionError: ['population 0 is below the floor 33', 'no round_driver.py run-verify form in the population', 'no round_driver.py rule form in the population']
  1 failed in 0.13s
  ```
- Restore: inverse Edit. Restore receipt: `    if not forms:` followed by `        problems.append("empty population: no call form found")`.

### G7b: below the floor, at the real population

- Neutralization (raises the threshold so the real population of 35 falls below it): `POPULATION_FLOOR = 33` became `POPULATION_FLOOR = 36`.
- Red node: `T1::test_census_population_is_not_vacuous`.
- Red tail:
  ```
  E       AssertionError: call-form census population: population 35 is below the floor 36
  1 failed in 0.13s
  ```
- Restore: inverse Edit. Restore receipt: `POPULATION_FLOOR = 33`.
- This proves the real census reads the floor. It does not prove the `<` comparison itself; see G7c.

### G7c: the `len(forms) < POPULATION_FLOOR` comparison itself: UNPROVEN, no detector bites it

- Neutralization tried: `if len(forms) < POPULATION_FLOOR:` became `if False and len(forms) < POPULATION_FLOOR:`.
- Nodes run: `T1::test_census_population_is_not_vacuous`, `T1::test_population_check_fails_an_empty_population`, `T1::test_population_check_needs_a_run_verify_and_a_rule_form`.
- Result (no red; this is the finding):
  ```
  ...                                                                      [100%]
  3 passed in 0.12s
  ```
- Reason: the real population (35) is above the floor and every synthetic population is either empty
  (which the G7a message covers) or exactly `POPULATION_FLOOR` forms. No test builds a population
  between 1 and `POPULATION_FLOOR - 1` forms, so removing the comparison turns nothing red. Making it
  bite needs one more synthetic test in `test_skill_helper_call_form_2158.py`, which the order did not
  list as a deliverable. The comparison's protection is unverified until that test exists.
- Restore: inverse Edit. Restore receipt: `    if len(forms) < POPULATION_FLOOR:`.

## G8: at least one `run-verify` and one `rule` form in the population

Axis: `_population_problems` reports a population with no `round_driver.py run-verify` form, and one
with no `round_driver.py rule` form. Red node (both): `T1::test_population_check_needs_a_run_verify_and_a_rule_form`.

### G8a: `run-verify` dropped from the required verbs

- Neutralization: `_UNAPPROVED_DRIVER_VERBS = ("run-verify", "rule")` became `_UNAPPROVED_DRIVER_VERBS = ("rule",)`.
- Red tail:
  ```
  >       assert any("run-verify" in p for p in problems), problems
  E       AssertionError: ['no round_driver.py rule form in the population']
  1 failed in 0.13s
  ```
- Restore: inverse Edit (receipt in G8b).

### G8b: `rule` dropped from the required verbs

- Neutralization: `_UNAPPROVED_DRIVER_VERBS = ("run-verify", "rule")` became `_UNAPPROVED_DRIVER_VERBS = ("run-verify",)`.
- Red tail:
  ```
  >       assert any("rule" in p for p in problems), problems
  E       AssertionError: ['no round_driver.py run-verify form in the population']
  1 failed in 0.13s
  ```
- Restore: inverse Edit. Restore receipt: `_UNAPPROVED_DRIVER_VERBS = ("run-verify", "rule")`.

## G9: decide-location plain-call halting guard (`T3`, Task 1)

Axis: a surface that runs `decide-location` as its own plain line must show a `#` comment on the next
line naming a non-zero exit and a halt; a surface in neither shape is not admitted.

### G9a: the halting rule (`_plain_call_halts`)

- Neutralization: `if "non-zero exit" in folded and "halt" in folded:` became `if True:`.
- Red node: `T3::test_plain_call_without_halting_comment_fails_guard`.
- Red tail:
  ```
  >       assert not _nonzero_exit_guard_present(_bash_block_of(no_halt))
  E       assert not True
  1 failed in 0.12s
  ```
- Restore: inverse Edit. Restore receipt: `            if "non-zero exit" in folded and "halt" in folded:`.

### G9b: the admission rule (`_is_decide_location_surface`, plain-call branch)

- Neutralization: `return bool(_PLAIN_DECIDE_LOCATION_CALL.search(text) and _DEC_LITERAL_ASSIGNMENT.search(text))` became `return False`.
- Red nodes: `T3::test_plain_call_surface_text_is_discovered` and `T3::test_bootstrap_disclosure_pin_cardinality_floor`.
- Red tail (the second is the original failure that started this work order, reproduced):
  ```
  >       assert _is_decide_location_surface(_PLAIN_CALL_SURFACE_TEXT)
  E       assert False
  E       AssertionError: disclosure pin(s) left behind for surface(s) that no longer call decide-location — remove stale pin (#1136). Stale:
  E         skills/review-code/reference/setup.md
  2 failed in 0.14s
  ```
- Restore: inverse Edit. Restore receipt: `    return bool(_PLAIN_DECIDE_LOCATION_CALL.search(text) and _DEC_LITERAL_ASSIGNMENT.search(text))`.

## Planted defect: the real census against the real skill doc

Axis: a `$ROOT_DIR` / `$SESSION_DIR` call line in a fenced bash block of a real skill doc fails the census.
- Neutralization: one Edit on `plugins/superheroes/skills/review-code/reference/round-driver.md` inserted, inside the fenced bash block that follows "Every step thereafter:", the line
  `python3 -B "$ROOT_DIR/lib/round_driver.py" next --session-dir "$SESSION_DIR"`
  directly under the existing `python3 -B <plugin root>/lib/round_driver.py next --session-dir <session dir>` line (it landed on line 66).
- Red nodes: `T1::test_no_forbidden_forms_in_the_skill_text`, `T1::test_call_form_shape` (all parametrizations), `T1::test_rendered_call_forms_get_the_hooks_decision`.
- Red tail:
  ```
  E         skills/review-code/reference/round-driver.md:66: $ROOT_DIR form of a hook-approved script
  E         skills/review-code/reference/round-driver.md:66: hook-approved script with --session-dir $SESSION_DIR
  E       AssertionError: skills/review-code/reference/round-driver.md:66: contains $; script token is not exactly `python3 -B <plugin root>/lib/<name>.py`: python3 -B "$ROOT_DIR/lib/round_driver.py" next --session-dir "$SESSION_DIR"
  E         skills/review-code/reference/round-driver.md:66: not approved but must be: python3 -B "$ROOT_DIR/lib/round_driver.py" next --session-dir "$SESSION_DIR"
  FAILED ...::test_no_forbidden_forms_in_the_skill_text
  FAILED ...::test_call_form_shape[skills/review-code/reference/round-driver.md:66]
  FAILED ...::test_rendered_call_forms_get_the_hooks_decision
  3 failed, 35 passed in 1.42s
  ```
- Restore: inverse Edit removed the inserted line. Restore receipt: the block reads again
  `python3 -B <plugin root>/lib/round_driver.py next --session-dir <session dir>` then the closing fence, and
  `git status --porcelain plugins/` after the revert listed no `round-driver.md` entry.

## Greens (after the last restore of each file)

- `T1` nodes: `test_shape_check_flags_variable_and_continuation_forms`, `test_forbidden_form_check_flags_a_reintroduced_multiline_block`, `test_judge_reports_a_form_the_hook_does_not_approve`, `test_excluded_driver_forms_are_asserted_unapproved`, `test_an_unreplaced_placeholder_is_never_approved`, `test_population_check_fails_an_empty_population`, `test_census_population_is_not_vacuous`, `test_population_check_needs_a_run_verify_and_a_rule_form`:
  ```
  ............                                                             [100%]
  12 passed in 0.19s
  ```
  `git status --porcelain plugins/` after this run listed only ` M plugins/superheroes/lib/tests/test_presence_flag_retired.py`, so `T1` is byte-clean against `HEAD`.
- `T2` nodes: `test_shell_census_comment_without_halt_is_not_a_handler`, `test_shell_census_next_line_halting_comment_clean`, `test_shell_census_no_fall_open_on_calibration_resolve`:
  ```
  ...                                                                      [100%]
  3 passed in 0.13s
  ```
- `T3` nodes and the planted-defect nodes, after the planted line was reverted: `T1::test_no_forbidden_forms_in_the_skill_text`, `T1::test_call_form_shape`, `T1::test_rendered_call_forms_get_the_hooks_decision`, `T3::test_plain_call_without_halting_comment_fails_guard`, `T3::test_plain_call_with_halting_comment_passes_guard`, `T3::test_plain_call_surface_text_is_discovered`, `T3::test_bootstrap_disclosure_pin_cardinality_floor`:
  ```
  .........................................                                [100%]
  41 passed in 1.47s
  ```
