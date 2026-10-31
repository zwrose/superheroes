# C3 WO-B — outside-finding doctrine census: bite-proof record

Detector: `plugins/superheroes/lib/tests/test_c3_outside_doctrine.py` (D1 home states the cap, D2 six surfaces state the home's cap, D3 no old skip phrase, D4 vet receipt, D5 glossary and home link). Method for every element: one targeted `Edit` of the doc, the single test node run alone (red), the inverse `Edit`, a grep of the restored text as the restore receipt, the same node again (green). No `git checkout`, `git restore`, `git reset` or `git stash` was used. Each red below is a rung-compliant bite-proof red, not a failure of the order. Every run printed the line `warning: The UV_NATIVE_TLS environment variable is deprecated ...` first; it is dropped from the captures below (the only text removed). Nothing else is redacted (no secrets in these captures). Run time and the temp paths are as printed.

The cap is read from `rubric/review-base.md` only. Surfaces other than the home state it as `at most 3 outside findings`; the neutralization for BP2–BP7 changes `3` to `N` in that file (every occurrence in it, so the file stops stating the number at all).

## BP1 — review-base number (the home)

- **guarded element / axis:** `rubric/review-base.md` Verification rule 2, `at most 3 outside findings, from its own reading` — the one home of the number; the axis is "every other surface states the home's number".
- **neutralization:** `at most 3 outside findings, from its own reading.` → `at most 4 outside findings, from its own reading.` (count 1).
- **raw red (D2, architecture-reviewer case; rc 1):**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_d2_surface_states_the_homes_cap[agents/architecture-reviewer.md] _____
...
>       assert set(numbers) == {home}, f"{surface} states {numbers}, the home states {home}"
E       AssertionError: agents/architecture-reviewer.md states ['3', '3'], the home states 4
E       assert {'3'} == {'4'}
...
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c3_outside_doctrine.py::test_d2_surface_states_the_homes_cap[agents/architecture-reviewer.md]
1 failed in 1.59s
```

- **the one edit reddens all six, and D1 stays green** — one extra run of `-k "d1 or d2"` under the same neutralization (the last 7 result lines of that run, kept by `tail -15`; the head of it was cut by that filter and is not claimed):

```
FAILED plugins/superheroes/lib/tests/test_c3_outside_doctrine.py::test_d2_surface_states_the_homes_cap[agents/architecture-reviewer.md]
FAILED plugins/superheroes/lib/tests/test_c3_outside_doctrine.py::test_d2_surface_states_the_homes_cap[agents/code-reviewer.md]
FAILED plugins/superheroes/lib/tests/test_c3_outside_doctrine.py::test_d2_surface_states_the_homes_cap[agents/security-reviewer.md]
FAILED plugins/superheroes/lib/tests/test_c3_outside_doctrine.py::test_d2_surface_states_the_homes_cap[agents/premortem-reviewer.md]
FAILED plugins/superheroes/lib/tests/test_c3_outside_doctrine.py::test_d2_surface_states_the_homes_cap[agents/test-role.md]
FAILED plugins/superheroes/lib/tests/test_c3_outside_doctrine.py::test_d2_surface_states_the_homes_cap[rubric/orders/dispatch-panel.md]
6 failed, 1 passed, 9 deselected in 1.31s
```

(the 1 passed is `test_d1_home_states_the_cap`, which reads the number from the home itself.)

- **restore:** inverse edit `at most 4 outside findings, from its own reading.` → `at most 3 outside findings, from its own reading.`
- **restore receipt:** `grep -n "at most 3 outside findings, from its own reading" plugins/superheroes/rubric/review-base.md` → `46:   at most 3 outside findings, from its own reading. The review lists every one raised on`
- **raw green:**

```
.                                                                        [100%]
1 passed in 0.15s
```

## BP2 — architecture-reviewer states the number

- **guarded element / axis:** `agents/architecture-reviewer.md` (two sentences, lines 15 and 124); the axis is "this agent states the home's number beside `outside finding`".
- **neutralization:** `replace_all` `at most 3 outside findings` → `at most N outside findings` (2 occurrences).
- **raw red (rc 1):**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_d2_surface_states_the_homes_cap[agents/architecture-reviewer.md] _____
...
>       assert numbers, f"{surface} states no cap beside the words 'outside finding'"
E       AssertionError: agents/architecture-reviewer.md states no cap beside the words 'outside finding'
E       assert []
...
FAILED plugins/superheroes/lib/tests/test_c3_outside_doctrine.py::test_d2_surface_states_the_homes_cap[agents/architecture-reviewer.md]
1 failed in 0.18s
```

- **restore:** inverse `replace_all` `at most N outside findings` → `at most 3 outside findings`.
- **restore receipt:** `grep -o "at most [3N] outside findings"` over the file → two lines, both `at most 3 outside findings`.
- **raw green:**

```
.                                                                        [100%]
1 passed in 0.18s
```

## BP3 — code-reviewer states the number

- **guarded element / axis:** `agents/code-reviewer.md` (three sentences, lines 17, 137, 164); same axis as BP2.
- **neutralization:** `replace_all` `at most 3 outside findings` → `at most N outside findings` (3 occurrences).
- **raw red (rc 1):**

```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_d2_surface_states_the_homes_cap[agents/code-reviewer.md] _________
...
>       assert numbers, f"{surface} states no cap beside the words 'outside finding'"
E       AssertionError: agents/code-reviewer.md states no cap beside the words 'outside finding'
E       assert []
...
FAILED plugins/superheroes/lib/tests/test_c3_outside_doctrine.py::test_d2_surface_states_the_homes_cap[agents/code-reviewer.md]
1 failed in 0.16s
```

- **restore:** inverse `replace_all`.
- **restore receipt:** `grep -o "at most [3N] outside findings"` over the file → three lines, all `at most 3 outside findings`.
- **raw green:**

```
.                                                                        [100%]
1 passed in 0.15s
```

## BP4 — security-reviewer states the number

- **guarded element / axis:** `agents/security-reviewer.md` (three sentences, lines 15, 138, 152); same axis as BP2.
- **neutralization:** `replace_all` `at most 3 outside findings` → `at most N outside findings` (3 occurrences).
- **raw red (rc 1):**

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_d2_surface_states_the_homes_cap[agents/security-reviewer.md] _______
...
>       assert numbers, f"{surface} states no cap beside the words 'outside finding'"
E       AssertionError: agents/security-reviewer.md states no cap beside the words 'outside finding'
E       assert []
...
FAILED plugins/superheroes/lib/tests/test_c3_outside_doctrine.py::test_d2_surface_states_the_homes_cap[agents/security-reviewer.md]
1 failed in 0.16s
```

- **restore:** inverse `replace_all`.
- **restore receipt:** `grep -o "at most [3N] outside findings"` over the file → three lines, all `at most 3 outside findings`.
- **raw green:**

```
.                                                                        [100%]
1 passed in 0.15s
```

## BP5 — premortem-reviewer states the number

- **guarded element / axis:** `agents/premortem-reviewer.md` (one sentence, line 78); same axis as BP2.
- **neutralization:** `at most 3 outside findings` → `at most N outside findings` (1 occurrence).
- **raw red (rc 1):**

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_d2_surface_states_the_homes_cap[agents/premortem-reviewer.md] ______
...
>       assert numbers, f"{surface} states no cap beside the words 'outside finding'"
E       AssertionError: agents/premortem-reviewer.md states no cap beside the words 'outside finding'
E       assert []
...
FAILED plugins/superheroes/lib/tests/test_c3_outside_doctrine.py::test_d2_surface_states_the_homes_cap[agents/premortem-reviewer.md]
1 failed in 0.16s
```

- **restore:** inverse edit.
- **restore receipt:** `grep -o "at most [3N] outside findings"` over the file → one line, `at most 3 outside findings`.
- **raw green:**

```
.                                                                        [100%]
1 passed in 0.15s
```

## BP6 — test-role states the number

- **guarded element / axis:** `agents/test-role.md` (two sentences, lines 17, 230); same axis as BP2.
- **neutralization:** `replace_all` `at most 3 outside findings` → `at most N outside findings` (2 occurrences).
- **raw red (rc 1):**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_d2_surface_states_the_homes_cap[agents/test-role.md] ___________
...
>       assert numbers, f"{surface} states no cap beside the words 'outside finding'"
E       AssertionError: agents/test-role.md states no cap beside the words 'outside finding'
E       assert []
...
FAILED plugins/superheroes/lib/tests/test_c3_outside_doctrine.py::test_d2_surface_states_the_homes_cap[agents/test-role.md]
1 failed in 0.17s
```

- **restore:** inverse `replace_all`.
- **restore receipt:** `grep -o "at most [3N] outside findings"` over the file → two lines, both `at most 3 outside findings`.
- **raw green:**

```
.                                                                        [100%]
1 passed in 0.15s
```

## BP7 — dispatch-panel order states the number

- **guarded element / axis:** `rubric/orders/dispatch-panel.md` § Diff-scope rule (one sentence, wrapped across lines 36–37); same axis as BP2.
- **neutralization:** `at most 3 outside` → `at most N outside` (1 occurrence).
- **raw red (rc 1):**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_d2_surface_states_the_homes_cap[rubric/orders/dispatch-panel.md] _____
...
>       assert numbers, f"{surface} states no cap beside the words 'outside finding'"
E       AssertionError: rubric/orders/dispatch-panel.md states no cap beside the words 'outside finding'
E       assert []
...
FAILED plugins/superheroes/lib/tests/test_c3_outside_doctrine.py::test_d2_surface_states_the_homes_cap[rubric/orders/dispatch-panel.md]
1 failed in 0.28s
```

- **restore:** inverse edit.
- **restore receipt:** `grep -n "at most [3N] outside" plugins/superheroes/rubric/orders/dispatch-panel.md` → `36:defect there while reading, you may add it as an outside finding: at most 3 outside`.
- **raw green:**

```
.                                                                        [100%]
1 passed in 0.18s
```

## BP8 — an old skip phrase reintroduced in one agent

- **guarded element / axis:** the absence of the old skip phrases (D3), checked per file; representative: `agents/test-role.md` line 230.
- **neutralization:** `Pre-existing test smells in context lines are not a finding on the change;` → `Pre-existing test smells in context lines → SKIP;`.
- **raw red (rc 1):**

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_d3_no_surface_still_only_skips_untouched_lines[agents/test-role.md] ___
...
>       assert not left, f"{surface} still says: {left}"
E       AssertionError: agents/test-role.md still says: ['Pre-existing test smells in context lines → SKIP']
E       assert not ['Pre-existing test smells in context lines → SKIP']
...
FAILED plugins/superheroes/lib/tests/test_c3_outside_doctrine.py::test_d3_no_surface_still_only_skips_untouched_lines[agents/test-role.md]
1 failed in 0.19s
```

- **restore:** inverse edit.
- **restore receipt:** `grep -n "Pre-existing test smells in context lines" plugins/superheroes/agents/test-role.md` → `230:8. **Diff-scope rule** (per the base rubric): only flag code on `+`/`-` lines. Pre-existing test smells in context lines are not a finding on the change; at most 3 outside findings from your own r...` (cut at 200 characters).
- **raw green:**

```
.                                                                        [100%]
1 passed in 0.21s
```

## BP9 — the vet field renamed

- **guarded element / axis:** `skills/showrunner/reference/vet-receipt.md` field `**Outside this PR.**` (three occurrences: the prose, the template, the sample); the axis is "the fixed field name the vet writes".
- **neutralization:** `replace_all` `**Outside this PR.**` → `**Outside the PR.**` (3 occurrences).
- **raw red (rc 1):**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_d4_vet_receipt_sorts_the_outside_list __________________
...
>       assert "**Outside this PR.**" in text
E       AssertionError: assert '**Outside this PR.**' in '# Contents\n\n- [The vet receipt — shape](#the-vet-receipt--shape)\n- [The spine — always present, filled or `None`](...```markdown\n<!-- superheroes:advisor-vet -->\n**Verdict: READY** · <40-character head sha> <qualifier, if any>\n```\n'
...
FAILED plugins/superheroes/lib/tests/test_c3_outside_doctrine.py::test_d4_vet_receipt_sorts_the_outside_list
1 failed in 0.18s
```

- **restore:** inverse `replace_all`.
- **restore receipt:** `grep -c '\*\*Outside this PR\.\*\*'` over the file → `3`; `grep -c 'Outside the PR'` → `0`.
- **raw green:**

```
.                                                                        [100%]
1 passed in 0.16s
```

## BP10 — the glossary heading renamed

- **guarded element / axis:** `rubric/glossary.md` `### Outside finding` (the anchor `#outside-finding` the home links); the axis is "the term the home links resolves to a heading".
- **neutralization:** `### Outside finding` → `### Outside note` (1 occurrence).
- **raw red (rc 1):**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_d5_glossary_defines_outside_finding_and_home_links_it __________
...
>       assert "### Outside finding" in _read(GLOSSARY)
E       assert '### Outside finding' in "# Glossary\n\nThe one home for the plugin's ruled vocabulary. Every other surface cites a term by its heading\nanchor...viewer can run there.\n\n### Check session\n\nThe one short cloud session that proves a [cloud setup](#cloud-setup).\n"
...
FAILED plugins/superheroes/lib/tests/test_c3_outside_doctrine.py::test_d5_glossary_defines_outside_finding_and_home_links_it
1 failed in 0.19s
```

- **restore:** inverse edit.
- **restore receipt:** `grep -n "^### Outside" plugins/superheroes/rubric/glossary.md` → `440:### Outside finding`.
- **raw green:**

```
.                                                                        [100%]
1 passed in 0.19s
```

## Not covered

- The second half of D5 (the home links `glossary.md#outside-finding`) and the D4 sub-assertions other than the field name (the triggered row, the `## The outside list` heading, the two choice words, the owner's-word phrase) have no neutralization of their own here; D4 and D5 each went red on one element only. These are listed as unproven.
- The `...` lines inside each red capture stand for pytest's source and traceback lines elided for length (the failing assertion lines are kept).
