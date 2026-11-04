# Bite-proof record: i2342_comment_scan_inline_code (#2342 fix round, review finding code-001) `_comment_scan` ignores a comment opener inside inline code

Detector under proof: `plugins/superheroes/lib/tests/test_vet_slot_comment_scan_inline_code_2342.py`.
Guarded code: `plugins/superheroes/lib/vet_slot.py` (`_comment_scan` only; its two consumers are `_unrendered_slot`
and `check_not_emptied` through `_live_heading_offsets`). Base: `6ac969c5`. Every neutralization was a targeted edit
made with the Edit tool, undone by the inverse Edit before the next element. No `git checkout`, `restore`, `reset` or
`stash` was used.
Command prefix for every run below (worktree root), with `-k` as named per entry:
`timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_vet_slot_comment_scan_inline_code_2342.py -q -p no:cacheprovider --tb=short -k <selector>`
The production sites cite this record with `# axis:` comments. Restore receipts are the restored lines, quoted.

Disclosures:
- The red captures are **condensed by hand, not verbatim**: pytest's repeated `E` lines, the `Full output truncated`
  line, the full `FAILED` path prefix and uv's one deprecation warning line are dropped. Every line shown is the
  runner's text; the pass/fail counts and the `FAILED` node ids are exact. The green captures are verbatim minus uv's
  warning line. Nothing was redacted; each capture is far under 32 KiB.
- Guarded-element set: the four the order declared (K1 to K4), no others. The `dead` (fenced line) guard is the
  pre-existing behaviour (C9) and was not neutralized here: it carries no new guard site.
- K1 is one site with two consumers: the one neutralization turned both the C1 (slot-visibility) and the C2
  (`body-emptied`) tests red.
- `-k` selectors name test-function substrings: `c1 or c2 or c3 or span or unclosed_run` also selects the two
  `test_comment_scan_starts_in_comment_per_line` cases `span` and `double-span`.

## 1. K1: the code-span skip

- **Axis:** a backtick run closed by a run of its own length on the line is literal text, so a `<!--` inside it opens
  no comment, for both consumers.
- **Neutralization:** `elif line[pos] == "`":` became `elif False and line[pos] == "`":` (the backtick falls through
  to plain-character handling).
- **Raw red** (`-k "c1 or c2 or c3 or span or unclosed_run"`):

```
FFFFFFF                                                                  [100%]
___ test_c1_run_verb_writes_a_bot_body_that_quotes_the_opener_in_inline_code ___
E   AssertionError: assert {'ok': False,...d not render'} == {'ok': True, ...ttps://x/c/1'}
E     {'detail': 'the advisor-vet marker sits inside an unclosed HTML comment, so the slot would not render', 'reason': 'write-failed'}
___________________ test_c1_evaluate_composes_the_same_body ____________________
E   AssertionError: {'ok': False, 'reason': 'write-failed', 'detail': 'the advisor-vet marker sits inside an unclosed HTML comment, so the slot would not render'}
_ test_c2_run_verb_does_not_refuse_body_emptied_for_an_inline_code_opener_above_the_heading _
E     {'detail': 'PR body has no "What\'s changing, and why" heading above the advisor-vet marker; restore the builder\'s body from the PR\'s edit history before writing the slot', 'reason': 'body-emptied'}
________________ test_c2_evaluate_does_not_refuse_body_emptied _________________
E   AssertionError: {'ok': False, 'reason': 'body-emptied', 'detail': 'PR body has no "What\'s changing, and why" heading above the advisor-vet marker; restore the builder\'s body from the PR\'s edit history before writing the slot'}
___________ test_c3_a_double_backtick_span_holding_the_opener_writes ___________
E   AssertionError: {'ok': False, 'reason': 'write-failed', 'detail': 'the advisor-vet marker sits inside an unclosed HTML comment, so the slot would not render'}
______________ test_comment_scan_starts_in_comment_per_line[span] ______________
E   assert [False, True] == [False, False]
__________ test_comment_scan_starts_in_comment_per_line[double-span] ___________
E   assert [False, True] == [False, False]
FAILED test_c1_run_verb_writes_a_bot_body_that_quotes_the_opener_in_inline_code
FAILED test_c1_evaluate_composes_the_same_body
FAILED test_c2_run_verb_does_not_refuse_body_emptied_for_an_inline_code_opener_above_the_heading
FAILED test_c2_evaluate_does_not_refuse_body_emptied
FAILED test_c3_a_double_backtick_span_holding_the_opener_writes
FAILED test_comment_scan_starts_in_comment_per_line[span]
FAILED test_comment_scan_starts_in_comment_per_line[double-span]
7 failed, 13 deselected in 0.54s
```

  C1 reds with `write-failed` and C2 with `body-emptied`: both consumers of the one site.
- **Restore:** inverse Edit, `elif False and line[pos] == "`":` back to `elif line[pos] == "`":`.
- **Restore receipt:** the restored line reads `                elif line[pos] == "`":` (`vet_slot.py:205`).
- **Raw green** (same `-k`):

```
.......                                                                  [100%]
7 passed, 13 deselected in 0.51s
```

## 2. K2: the escape skip

- **Axis:** a backslash-escaped character is literal text, so an escaped `<!--` opens no comment.
- **Neutralization:** `if line[pos] == "\\" and pos + 1 < len(line):` became
  `if False and line[pos] == "\\" and pos + 1 < len(line):`.
- **Raw red** (`-k test_c5_an_escaped_opener_writes`):

```
F                                                                        [100%]
_______________________ test_c5_an_escaped_opener_writes _______________________
E   AssertionError: {'ok': False, 'reason': 'write-failed', 'detail': 'the advisor-vet marker sits inside an unclosed HTML comment, so the slot would not render'}
E   assert False is True
FAILED test_c5_an_escaped_opener_writes
1 failed, 19 deselected in 0.53s
```

- **Restore:** inverse Edit, the `False and ` prefix removed.
- **Restore receipt:** the restored line reads `                if line[pos] == "\\" and pos + 1 < len(line):` (`vet_slot.py:202`).
- **Raw green:**

```
.                                                                        [100%]
1 passed, 19 deselected in 0.38s
```

## 3. K3: the unclosed-run rule

- **Axis:** a backtick run with no closing run of its length on the line is literal backticks, and the scan continues
  after it, so a later real opener on that line still opens a comment.
- **Neutralization:** `pos = end if end is not None else leftover_accepting._TICKS.match(line, pos).end()` became
  `pos = end if end is not None else len(line)` (an unclosed run swallows the rest of the line as code).
- **Raw red** (`-k test_c4`):

```
F                                                                        [100%]
_ test_c4_an_unclosed_backtick_run_then_a_real_opener_still_refuses_write_failed _
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1'}
E   assert True is False
FAILED test_c4_an_unclosed_backtick_run_then_a_real_opener_still_refuses_write_failed
1 failed, 19 deselected in 0.41s
```

- **Restore:** inverse Edit, `len(line)` back to `leftover_accepting._TICKS.match(line, pos).end()`.
- **Restore receipt:** the restored line reads
  `                    pos = end if end is not None else leftover_accepting._TICKS.match(line, pos).end()` (`vet_slot.py:209`).
- **Raw green:**

```
.                                                                        [100%]
1 passed, 19 deselected in 0.30s
```

## 4. K4: the in-comment closer

- **Axis:** inside a comment the text is not Markdown, so the first `-->` closes it even inside backticks.
- **Neutralization:** `at = line.find("-->", pos)` in the in-comment branch became
  `at = line.find("-->", pos) if "`" not in line else -1` (a `-->` on a line carrying a backtick does not close).
- **Raw red** (`-k test_c8`):

```
F                                                                        [100%]
_ test_c8_a_backtick_quoted_closer_inside_a_comment_closes_it_so_the_heading_is_live _
E   AssertionError: {'ok': False, 'reason': 'body-emptied', 'detail': 'PR body has no "What\'s changing, and why" heading above the advisor-vet marker; restore the builder\'s body from the PR\'s edit history before writing the slot'}
E   assert False is True
FAILED test_c8_a_backtick_quoted_closer_inside_a_comment_closes_it_so_the_heading_is_live
1 failed, 19 deselected in 0.43s
```

- **Restore:** inverse Edit, the ` if "`" not in line else -1` suffix removed.
- **Restore receipt:** the restored line reads `                at = line.find("-->", pos)` (`vet_slot.py:194`).
- **Raw green:**

```
.                                                                        [100%]
1 passed, 19 deselected in 0.42s
```

## Review fix round: raw HTML (K5–K7)

Added at review-code's `apply-fixes` step for the scoped finder's finding "Raw HTML comments now bypass the
owner-half guard" (a `<!--` quoted in inline code inside a raw `<div>` block is a real comment: the HTML block is
not Markdown). The build session wrote the fix and these tests, so it produced and ran this part of the record itself,
in a detached probe worktree at `3bcd84c7`, with Edit-tool neutralizations and inverse-Edit restores; `git status
--porcelain` was empty after the last restore. Command prefix as above, `--tb=no`, selector `-k c11`. The captures are
the runner's result lines; the per-test FAILED lines are listed, nothing else was cut, nothing redacted.

The guarded-element set declared before the probes: K5 the raw-HTML branch, K6 the blank line that ends a raw run, K7
a comment-opener line that does not start a raw run.

### K5: the raw-HTML branch (both callers)

- **Neutralization:** `if raw_html:` became `if False and raw_html:`.
- **Red:** `5 failed, 4 passed, 20 deselected` — `test_c11_the_findings_example_a_div_then_a_quoted_opener_hides_the_owner_half_body_emptied`
  (the `body-emptied` guard), `test_c11_a_bot_body_with_a_quoted_opener_inside_a_raw_div_refuses_write_failed` (the
  slot path), `test_c11_a_raw_block_under_a_blockquote_is_raw_too`, `test_c11_comment_scan_reads_raw_html_runs[div-run]`,
  `test_c11_comment_scan_reads_raw_html_runs[quoted-container-escape]`.
- **Restore:** inverse Edit. **Green:** `9 passed, 20 deselected`.

### K6: a blank line ends the raw run

- **Neutralization:** `if not line.strip():` (the raw-run reset) became `if False and not line.strip():`.
- **Red:** `2 failed, 7 passed, 20 deselected` — `test_c11_a_blank_line_ends_the_raw_block_so_a_later_quoted_opener_is_text_again`,
  `test_c11_comment_scan_reads_raw_html_runs[blank-ends-run]`.
- **Restore:** inverse Edit. **Green:** `9 passed, 20 deselected`.

### K7: a comment-opener line does not start a raw run

- **Neutralization:** `_RAW_HTML_START_RE`'s class `[A-Za-z/?]` became `[A-Za-z/?!]`.
- **Red:** `2 failed, 7 passed, 20 deselected` — `test_c11_a_comment_line_does_not_make_the_next_line_raw`,
  `test_c11_comment_scan_reads_raw_html_runs[comment-line-not-raw]`.
- **Restore:** inverse Edit. **Green:** `29 passed` (the whole file).
