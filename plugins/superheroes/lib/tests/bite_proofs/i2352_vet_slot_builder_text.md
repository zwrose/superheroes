# Bite-proof record: i2352_vet_slot_builder_text (#2352) `vet_slot.py write` refuses builder text in the slot span

Detector under proof: `plugins/superheroes/lib/tests/test_vet_slot_builder_text_2352.py`.
Guarded code: `plugins/superheroes/lib/vet_slot.py` (`_span_owned_problem`, `check_span_owned`, `_SLOT_HEADING_RE`,
`_REMINDER_OPENER`, and the three call sites: `evaluate` before the compose, `evaluate` after the compose (the round
trip), and `_run_verb`).
Base: `45f8834fd9de84de3fa68447f64a7e240524b21d`. Every neutralization was a targeted edit made with the Edit tool,
undone by the inverse Edit before the next element. No `git checkout`, `restore`, `reset` or `stash` was used.
Command prefix for every run below (worktree root), with `-k` as named per entry:
`timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_vet_slot_builder_text_2352.py -q -p no:cacheprovider --tb=short -k <selector>`
(the G4 red ran with `--tb=line`). Nothing in the captures was redacted; each is far under 32 KiB. The production
sites cite this record with `# axis:` comments. Restore receipts are the restored line, quoted from the file after the
inverse edit.

Disclosures:
- The captures are the runner's text minus uv's one `UV_NATIVE_TLS` deprecation warning line, which is dropped. Red
  captures with several failures are **condensed by hand**: repeated `where True = ...` and traceback-location lines
  are dropped and the long parametrized node ids are cut at the first 60 characters; the counts and the number of
  `FAILED` nodes are exact.
- Guarded-element set: the ten the order declared (G1 to G10), plus G11 (the text-after-the-closing-`-->` arm), added
  because its `# axis:` comment cites this record. Elements outside the set carry no neutralization run and are
  **unproven by a red run**: the fence-awareness of sign (c) (`not dead` is neutralized together with the whole line
  in G6, so E13's fenced-heading cases and the fence mark inside a reminder are exercised by passing tests, never
  turned red alone); the reminder-opener normalization (whitespace collapse); and the removal order of several
  reminders (E3's two-reminder case).
- The G1 red shows the first assertion that failed; with only the `evaluate` call skipped, `run_verb` still refuses
  through its own call (G2), so the red is the `evaluate` half of the test.

## 1. G1: the call in `evaluate`

- **Axis:** `evaluate` refuses builder text in the slot span on `write`, after `analyze_body`.
- **Neutralization:** `if verb == "write":` above `check_span_owned(body, advisor_at, build_at)` in `evaluate` became `if False:`.
- **Raw red** (`-k test_e5_a_builder_heading_section_after_the_reminder_refuses`):

```
F                                                                        [100%]
/home/user/wt-2352/plugins/superheroes/lib/tests/test_vet_slot_builder_text_2352.py:127: in test_e5_a_builder_heading_section_after_the_reminder_refuses
    fake = assert_refused_both_ways(span, tmp_path, "slot-span-builder-text",
.../test_vet_slot_builder_text_2352.py:69: in assert_refused_both_ways
    assert_refused(evaluate(body), reason, *details)
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1', ...}
E   assert True is False
FAILED ...::test_e5_a_builder_heading_section_after_the_reminder_refuses
1 failed, 59 deselected in 0.48s
```

- **Restore:** inverse Edit, `if False:` back to `if verb == "write":`.
- **Restore receipt:** the restored lines read `            if verb == "write":` then `                check_span_owned(body, advisor_at, build_at)` (vet_slot.py lines 696-697).
- **Raw green:**

```
.                                                                        [100%]
1 passed, 59 deselected in 0.36s
```

## 2. G2: the call in `_run_verb`

- **Axis:** `_run_verb` refuses builder text before the slot file is read and before any further gh call.
- **Neutralization:** `if verb == "write":` above `check_span_owned(body, advisor_at, build_at)` in `_run_verb` became `if False:`.
- **Raw red** (`-k test_e5_run_verb_refuses_before_the_slot_file_is_read`):

```
F                                                                        [100%]
/home/user/wt-2352/plugins/superheroes/lib/tests/test_vet_slot_builder_text_2352.py:144: in test_e5_run_verb_refuses_before_the_slot_file_is_read
    assert_refused(result, "slot-span-builder-text", "## Test answers")
E   AssertionError: {'ok': False, 'reason': 'write-failed', 'detail': "slot file unreadable: [Errno 2] No such file or directory: '/tmp/claude-0/pytest-of-root/pytest-5/test_e5_run_verb_refuses_befor0/no-such-slot.md'"}
E   assert 'write-failed' == 'slot-span-builder-text'
FAILED ...::test_e5_run_verb_refuses_before_the_slot_file_is_read
1 failed, 59 deselected in 0.39s
```

- **Restore:** inverse Edit, `if False:` back to `if verb == "write":`.
- **Restore receipt:** the restored lines read `        if verb == "write":` then `            check_span_owned(body, advisor_at, build_at)` (vet_slot.py lines 923-924).
- **Raw green:**

```
.                                                                        [100%]
1 passed, 59 deselected in 0.42s
```

## 3. G3: the reminder signature

- **Axis:** only a comment opening `<!-- advisor: BEFORE writing this slot` is the removable reminder; any other advisor comment is span content.
- **Neutralization:** `_REMINDER_OPENER = "<!-- advisor: BEFORE writing this slot"` became `_REMINDER_OPENER = "<!-- advisor:"`.
- **Raw red** (`-k test_e9_a_non_reminder_advisor_comment_alone_refuses`):

```
F                                                                        [100%]
.../test_vet_slot_builder_text_2352.py:191: in test_e9_a_non_reminder_advisor_comment_alone_refuses
    assert_refused_both_ways(span, tmp_path, "slot-span-builder-text", "line 1 of the span",
.../test_vet_slot_builder_text_2352.py:69: in assert_refused_both_ways
    assert_refused(evaluate(body), reason, *details)
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1', ...}
E   assert True is False
FAILED ...::test_e9_a_non_reminder_advisor_comment_alone_refuses
1 failed, 59 deselected in 0.43s
```

- **Restore:** inverse Edit, back to the full opener.
- **Restore receipt:** the restored line reads `_REMINDER_OPENER = "<!-- advisor: BEFORE writing this slot"` (vet_slot.py line 96).
- **Raw green:**

```
.                                                                        [100%]
1 passed, 59 deselected in 0.48s
```

## 4. G4: sign (a), verdict first

- **Axis:** the first remaining line must open with a verdict token of the canonical form.
- **Neutralization:** `if index == 0 and not any(text.startswith(token) for token in tokens):` became `if False and index == 0 and not any(...):`.
- **Raw red** (`-k test_e8`, `--tb=line`):

```
FFFFF                                                                    [100%]
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1', ...}   (x4, test_vet_slot_builder_text_2352.py:59)
E   KeyError: 'detail'   (test_vet_slot_builder_text_2352.py:186)
FAILED ...::test_e8_prose_before_the_verdict_or_no_verdict_refuses[The builder's note on how to test this.\n**Verdict: NOT-READY** \xb7 old\n-sign (a)]
FAILED ...::test_e8_prose_before_the_verdict_or_no_verdict_refuses[Only prose, no verdict at all.\n-sign (a)]
FAILED ...::test_e8_prose_before_the_verdict_or_no_verdict_refuses[    **Verdict: NOT-READY** \xb7 old\n-sign (a)]
FAILED ...::test_e8_prose_after_the_reminder_and_before_the_verdict_refuses
FAILED ...::test_e8_the_detail_quotes_the_first_sixty_characters_of_the_offending_line
5 failed, 55 deselected in 0.45s
```

- **Restore:** inverse Edit, `if False and index == 0 ...` back to `if index == 0 ...`.
- **Restore receipt:** the restored line reads `        if index == 0 and not any(text.startswith(token) for token in tokens):` (vet_slot.py line 294).
- **Raw green** (`-k test_e8`):

```
.....                                                                    [100%]
5 passed, 55 deselected in 0.40s
```

## 5. G5: sign (b), no comment

- **Axis:** no remaining line may hold `<!--` or `-->`, fenced or not.
- **Neutralization:** `if "<!--" in text or "-->" in text:` became `if False and ("<!--" in text or "-->" in text):`.
- **Raw red** (`-k test_e10`):

```
FFFF                                                                     [100%]
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1', ...}   (x4, test_vet_slot_builder_text_2352.py:59, via assert_refused_both_ways)
FAILED ...::test_e10_any_other_comment_after_a_verdict_refuses[<!-- a note for the owner -->]
FAILED ...::test_e10_any_other_comment_after_a_verdict_refuses[<!-- todo\nmore\n-->]
FAILED ...::test_e10_any_other_comment_after_a_verdict_refuses[text --> after]
FAILED ...::test_e10_a_comment_inside_a_fence_still_refuses
4 failed, 56 deselected in 0.40s
```

- **Restore:** inverse Edit, back to `if "<!--" in text or "-->" in text:`.
- **Restore receipt:** the restored line reads `        if "<!--" in text or "-->" in text:` (vet_slot.py line 297).
- **Raw green** (`-k test_e10`):

```
....                                                                     [100%]
4 passed, 56 deselected in 0.37s
```

## 6. G6: sign (c), no heading

- **Axis:** no remaining line outside a code fence may be an ATX heading.
- **Neutralization:** `if not dead and _SLOT_HEADING_RE.match(text):` became `if False and not dead and _SLOT_HEADING_RE.match(text):`.
- **Raw red** (`-k test_e6`):

```
F                                                                        [100%]
.../test_vet_slot_builder_text_2352.py:152: in test_e6_a_builder_heading_section_after_an_earlier_verdict_refuses
    fake = assert_refused_both_ways(span, tmp_path, "slot-span-builder-text",
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1', ...}
E   assert True is False
FAILED ...::test_e6_a_builder_heading_section_after_an_earlier_verdict_refuses
1 failed, 59 deselected in 0.38s
```

- **Restore:** inverse Edit, back to `if not dead and _SLOT_HEADING_RE.match(text):`.
- **Restore receipt:** the restored line reads `        if not dead and _SLOT_HEADING_RE.match(text):` (vet_slot.py line 300).
- **Raw green:**

```
.                                                                        [100%]
1 passed, 59 deselected in 0.37s
```

## 7. G7: the tab arm of the heading pattern

- **Axis:** a tab after the hashes makes a heading.
- **Neutralization:** `(?:[ \t]|$)` became `(?:[ ]|$)` in `_SLOT_HEADING_RE`.
- **Raw red** (`-k test_e7_a_tab_separated`):

```
F                                                                        [100%]
.../test_vet_slot_builder_text_2352.py:160: in test_e7_a_tab_separated_heading_after_a_verdict_refuses
    assert_refused_both_ways(span, tmp_path, "slot-span-builder-text", "line %d of the span" % n, "sign (c)")
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1', ...}
E   assert True is False
FAILED ...::test_e7_a_tab_separated_heading_after_a_verdict_refuses
1 failed, 59 deselected in 0.39s
```

- **Restore:** inverse Edit, `(?:[ ]|$)` back to `(?:[ \t]|$)`.
- **Restore receipt:** the restored line reads `_SLOT_HEADING_RE = re.compile(r"^ {0,3}#{1,6}(?:[ \t]|$)")` (vet_slot.py line 95).
- **Raw green:**

```
.                                                                        [100%]
1 passed, 59 deselected in 0.39s
```

## 8. G8: the unreadable-form fail-closed arm

- **Axis:** a verdict form that cannot be read refuses a non-empty span (and the empty span at the round trip).
- **Neutralization:** the arm's `return rest[0][0], rest[0][1], "(a) verdict first", "the verdict form cannot be read (%s)" % error` became `return None`.
- **Raw red** (`-k test_e14`):

```
FF                                                                       [100%]
.../test_vet_slot_builder_text_2352.py:258: in test_e14_form_unreadable_and_a_non_empty_span_refuses_builder_text
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1', ...}
.../test_vet_slot_builder_text_2352.py:264: in test_e14_form_unreadable_and_an_empty_span_refuses_write_failed_at_the_round_trip
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1', ...}
FAILED ...::test_e14_form_unreadable_and_a_non_empty_span_refuses_builder_text
FAILED ...::test_e14_form_unreadable_and_an_empty_span_refuses_write_failed_at_the_round_trip
2 failed, 58 deselected in 0.37s
```

- **Restore:** inverse Edit, `return None` back to the refusal tuple.
- **Restore receipt:** the restored line reads `        return rest[0][0], rest[0][1], "(a) verdict first", "the verdict form cannot be read (%s)" % error` (vet_slot.py line 290).
- **Raw green** (`-k test_e14`):

```
..                                                                       [100%]
2 passed, 58 deselected in 0.37s
```

## 9. G9: the unclosed-reminder arm

- **Axis:** a reminder with no closing `-->` before the build-record marker makes the span not the advisor's.
- **Neutralization:** the arm's `return number, first, "(b) no comment", "a reminder comment is never closed"` became `del kept[opening:]` then `continue` (an unclosed reminder taken as a reminder to the end of the span).
- **Raw red** (`-k test_e11`):

```
FF                                                                       [100%]
.../test_vet_slot_builder_text_2352.py:219: in test_e11_an_unclosed_reminder_refuses
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1', ...}
.../test_vet_slot_builder_text_2352.py:224: in test_e11_an_unclosed_reminder_with_nothing_after_it_refuses
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1', ...}
FAILED ...::test_e11_an_unclosed_reminder_refuses
FAILED ...::test_e11_an_unclosed_reminder_with_nothing_after_it_refuses
2 failed, 58 deselected in 0.44s
```

- **Restore:** inverse Edit, the two lines back to the `return number, first, ...` line.
- **Restore receipt:** the restored line reads `            return number, first, "(b) no comment", "a reminder comment is never closed"` (vet_slot.py line 277).
- **Raw green** (`-k test_e11`):

```
..                                                                       [100%]
2 passed, 58 deselected in 0.37s
```

## 10. G10: the round trip in `evaluate`

- **Axis:** the composed slot must itself read as the advisor's own (emitter within recogniser), so slot text with a live heading or no verdict token refuses `write-failed`.
- **Neutralization:** `check_span_owned(new_body, new_advisor_at, new_build_at)` inside the `try:` after the composed-body checks became `pass`.
- **Raw red** (`-k test_e17`):

```
FFFFFF.                                                                  [100%]
.../test_vet_slot_builder_text_2352.py:301: in test_e17_slot_text_that_would_not_read_as_the_advisors_own_refuses_write_failed   (x6)
    assert_refused(evaluate(body, slot), "write-failed", "would not read as the advisor's own on the next write",
.../test_vet_slot_builder_text_2352.py:59: in assert_refused   (x6)
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1', ...}   (x6)
E   assert True is False   (x6)
FAILED ...::test_e17_slot_text_that_would_not_read_as_the_advisors_own_refuses_write_failed[...## A heading in the slot]
FAILED ...::test_e17_slot_text_that_would_not_read_as_the_advisors_own_refuses_write_failed[...##\tTabbed heading...]
FAILED ...::test_e17_slot_text_that_would_not_read_as_the_advisors_own_refuses_write_failed[...#\n-sign (c)]
FAILED ...::test_e17_slot_text_that_would_not_read_as_the_advisors_own_refuses_write_failed[Prose first....]
FAILED ...::test_e17_slot_text_that_would_not_read_as_the_advisors_own_refuses_write_failed[A slot with no verdict token....]
FAILED ...::test_e17_slot_text_that_would_not_read_as_the_advisors_own_refuses_write_failed[  **Verdict: NOT-READY**...sign (a)]
6 failed, 1 passed, 53 deselected in 0.44s
```

- **Restore:** inverse Edit, `pass` back to `check_span_owned(new_body, new_advisor_at, new_build_at)`.
- **Restore receipt:** the restored line reads `        check_span_owned(new_body, new_advisor_at, new_build_at)` (vet_slot.py, inside the `try:` that follows the `moved or shadowed slot markers` refusal).
- **Raw green** (`-k test_e17`):

```
.......                                                                  [100%]
7 passed, 53 deselected in 0.50s
```

## 11. G11: text after a reminder's closing `-->` (added element)

- **Axis:** non-whitespace text after the closing `-->` on a reminder's closing line is span content, so the span is not the advisor's.
- **Neutralization:** `if text[at + 3:].strip():` became `if False and text[at + 3:].strip():`.
- **Raw red** (`-k test_e12`):

```
F                                                                        [100%]
.../test_vet_slot_builder_text_2352.py:230: in test_e12_text_after_a_reminders_closing_marker_refuses
    assert_refused_both_ways(span, tmp_path, "slot-span-builder-text", "line 1 of the span", "sign (b)",
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1', ...}
E   assert True is False
FAILED ...::test_e12_text_after_a_reminders_closing_marker_refuses
1 failed, 59 deselected in 0.40s
```

- **Restore:** inverse Edit, back to `if text[at + 3:].strip():`.
- **Restore receipt:** the restored line reads `        if text[at + 3:].strip():` (vet_slot.py line 280).
- **Raw green:**

```
.                                                                        [100%]
1 passed, 59 deselected in 0.39s
```

## 12. G12: a tab inside a builder heading separates its words (`no_build_record`, review fix)

Added at the review's `apply-fixes` steps (finding `normalize internal tabs before classifying builder headings`,
raised by the code reviewer and confirmed by the verifier). The first fix widened the shared `_heading_key`; its
audit found that it also loosened the owner-half check in `check_not_emptied`, so the second fix restored
`_heading_key` and collapses whitespace only where `no_build_record` keys a heading. Detector: the two new tests in
`plugins/superheroes/lib/tests/test_vet_slot_no_build_record_2342.py`. Run by the build session, same command prefix
with that file and `--tb=line`.

- **Axis:** a tab between the words of a builder heading (`## Build<TAB>record`) keys as `build record` in
  `no_build_record`, so the body is builder-shaped and the write refuses `body-emptied` instead of writing over the
  section on the no-build-record path.
- **Neutralization:** `key = _heading_key(" ".join(heading.group(1).split()))` became
  `key = _heading_key(heading.group(1))` (the pre-fix line).
- **Raw red** (`-k "tab_inside or tab_in_its_heading"`, condensed by hand: introspection lines dropped):

```
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1'}
FAILED ...::test_a_tab_inside_a_builder_heading_separates_its_words[Build\trecord]
FAILED ...::test_a_tab_inside_a_builder_heading_separates_its_words[Definition\tof Done]
FAILED ...::test_a_tab_inside_a_builder_heading_separates_its_words[Size\t\ttripwire]
FAILED ...::test_a_tab_inside_a_builder_heading_separates_its_words[What's\tchanging, and why]
FAILED ...::test_a_builder_section_with_a_tab_in_its_heading_below_the_marker_is_never_written_over
5 failed, 104 deselected in 0.47s
```

- **Restore:** inverse Edit, back to `key = _heading_key(" ".join(heading.group(1).split()))`.
- **Raw green:**

```
.....                                                                    [100%]
5 passed, 104 deselected in 14.13s
```

## 13. G13: the checked span starts where the write's span starts (`check_span_owned`, bring-current)

Added when main was merged in after its own vet-slot change merged: main's write starts the replaced span after the
marker's own `str.splitlines()` line (`_after_marker_line`) and ends it at the build-record marker, so the check now
reads exactly that span. Detector: `test_e5_builder_text_after_a_lone_cr_or_u2028_on_the_marker_line_refuses` in
`plugins/superheroes/lib/tests/test_vet_slot_builder_text_2352.py`. Run by the build session, same command prefix with
`--tb=line`.

- **Axis:** builder text after a lone CR or U+2028 on the marker line, before the next `\n`, is inside the span the
  write replaces, so the check reads it and refuses `slot-span-builder-text`; nothing is pushed.
- **Neutralization:** in `check_span_owned`, `start = _after_marker_line(body, advisor_at)` became
  `start = body.index("\n", advisor_at) + 1` (the pre-merge start).
- **Raw red** (`-k lone_cr`, condensed by hand: introspection lines dropped):

```
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1', ...}
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1', ...}
FAILED ...::test_e5_builder_text_after_a_lone_cr_or_u2028_on_the_marker_line_refuses[\r]
FAILED ...::test_e5_builder_text_after_a_lone_cr_or_u2028_on_the_marker_line_refuses[ ]
2 failed, 60 deselected in 0.41s
```

- **Restore:** inverse Edit, back to `start = _after_marker_line(body, advisor_at)`.
- **Raw green:**

```
..                                                                       [100%]
2 passed, 60 deselected in 16.91s
```
