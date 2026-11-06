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

K7's guard is now the narrower pattern below (K8); a `<!` line still starts no raw run, and the K7 tests stay green.

## Review fix round 2: raw-run boundaries (K8–K10)

Added at the second `apply-fixes` step for the round-2 findings "Do not classify Markdown autolinks as raw HTML",
"Do not start raw HTML from text inside a comment" and "Recognize blank lines inside Markdown containers" (each a
false refusal of a valid description). Same method as above, in the probe worktree at `1dd13b60`, selector
`-k "c11 or c12"`, `git status --porcelain` empty after the last restore; nothing cut or redacted.

The guarded-element set declared before the probes: K8 the tag-only start pattern, K9 no start inside a comment, K10 a
quoted blank line ends the run.

### K8: an autolink is not a tag

- **Neutralization:** `_RAW_HTML_START_RE` back to `^[ \t>*+\-0-9.)]*<[A-Za-z/?]`.
- **Red:** `2 failed, 16 passed, 20 deselected` — `test_c12_an_autolink_line_is_not_raw_html_so_a_later_quoted_opener_is_text`,
  `test_c12_comment_scan_raw_run_boundaries[autolink]`.
- **Restore:** inverse Edit; the autolink tests pass in K9's run and in the green below.

### K9: a tag inside a comment starts no run

- **Neutralization:** `elif not dead and not starts_in_comment and _RAW_HTML_START_RE.match(line):` lost
  `not starts_in_comment and`.
- **Red:** `2 failed, 16 passed, 20 deselected` — `test_c12_a_tag_inside_a_comment_starts_no_raw_run`,
  `test_c12_comment_scan_raw_run_boundaries[tag-in-comment]`.
- **Restore:** inverse Edit. **Green:** `18 passed, 20 deselected`.

### K10: a quoted blank line ends the run

- **Neutralization:** `if not line.strip(" \t>"):` became `if not line.strip():`.
- **Red:** `2 failed, 16 passed, 20 deselected` — `test_c12_a_quoted_blank_line_ends_a_quoted_raw_run`,
  `test_c12_comment_scan_raw_run_boundaries[quoted-blank]`.
- **Restore:** inverse Edit. **Green:** `38 passed` (the whole file).

K10's guard is now the depth-aware check below (K11); the quoted-blank tests stay green under it.

## Review fix round 3: the quote depth of a raw run (K11–K12)

Added at the third `apply-fixes` step for the round-3 findings (the auditors and the scoped finder): stripping every
`>` from a line ended an **unquoted** raw block at a literal `>` line, letting a real comment opener after it pass as
inline code — a fail-open of the owner-half guard. Same method, probe worktree at `7ce74854`, selector
`-k "c11 or c12 or c13"`, `git status --porcelain` empty after the last restore; nothing cut or redacted.

The guarded-element set declared before the probes: K11 the run ends only at a line blank inside its starting quote
depth, K12 a tag line inside a running block keeps that depth.

### K11: blank inside the starting quote depth

- **Neutralization:** `if not _strip_quote_marks(line, raw_depth if raw_html else 0).strip():` became
  `if not line.strip(" \t>"):` (the round-2 rule).
- **Red:** `5 failed, 19 passed, 20 deselected` — `test_c13_a_literal_gt_line_inside_an_unquoted_div_keeps_the_owner_half_hidden_body_emptied`
  (the `body-emptied` guard), `test_c13_a_literal_gt_line_inside_an_unquoted_div_still_refuses_a_bot_write` (the slot
  path), `test_c13_comment_scan_raw_run_depth[gt-in-unquoted-div]`, `[nested-tag-keeps-depth]`, `[deeper-gt-in-quoted-div]`.
- **Restore:** inverse Edit. **Green:** `24 passed, 20 deselected`.

### K12: a nested tag line keeps the depth

- **Neutralization:** `elif not raw_html and not dead and …` lost `not raw_html and`.
- **Red:** `1 failed, 23 passed, 20 deselected` — `test_c13_comment_scan_raw_run_depth[nested-tag-keeps-depth]`.
- **Restore:** inverse Edit. **Green:** `44 passed` (the whole file).

## Fix round: ASCII blank lines and list-aware quote depth (K13–K14)

Added for the two confirmed defects left at the round cap (PR #2347): a non-breaking-space line ended a raw run
(fail-open: `body-emptied` not raised) and the run's quote depth missed list markers and extra spaces (false
`write-failed`). Method: Edit-tool neutralizations in the build worktree at `162a826b` plus this fix, inverse-Edit
restores, command prefix `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest
plugins/superheroes/lib/tests/test_vet_slot_comment_scan_inline_code_2342.py -q -p no:cacheprovider --tb=short`,
selector `-k c14`. The captures are the runner's output with the `UV_NATIVE_TLS` warning line and the traceback bodies
cut; nothing redacted. The pre-fix run (before any guard edit) was `6 failed, 1 passed, 44 deselected`: E1 (both
callers merged in one test then), E2, E3 and the three rows.

The guarded-element set declared before the probes: K13 the ASCII-only blank test, K14 the list-aware quote depth (two
lines: K14a the start line's depth count, K14b the one-mark remover).

### K13: a blank line is only ASCII spaces and tabs

- **Guarded element / axis:** `_comment_scan`'s run-end test `.strip(" \t")` (`vet_slot.py:211`); a U+00A0 line is
  raw HTML text, not a Markdown blank line.
- **Neutralization:** `.strip(" \t")` became `.strip()`.
- **Raw red** (`-k c14`):

```
FF...F..                                                                 [100%]
FAILED ...::test_c14_a_non_breaking_space_line_does_not_end_a_raw_run_body_emptied
  E   AssertionError: {'ok': True, 'verb': 'write', 'followups': ['FU1', 'FU2'], 'receipt': 'https://x/c/1'}
FAILED ...::test_c14_evaluate_also_refuses_body_emptied_for_a_non_breaking_space_line_in_a_raw_run
  E   KeyError: 'reason'
FAILED ...::test_c14_comment_scan_raw_run_blankness_and_depth[nbsp-is-not-blank]
  E   assert [False, False, False, False] == [False, False, False, True]
3 failed, 5 passed, 44 deselected in 0.38s
```

- **Restore:** inverse Edit.
- **Restore receipt:** `vet_slot.py:211` reads `        if not _strip_quote_marks(line, raw_depth if raw_html else 0).strip(" \t"):`.
- **Raw green:**

```
........                                                                 [100%]
8 passed, 44 deselected in 0.41s
```

### K14a: the start line's depth counts the whole container prefix

- **Guarded element / axis:** `_QUOTE_PREFIX_RE` (`vet_slot.py:100`); the depth counts every `>` in the prefix
  `_RAW_HTML_START_RE` accepts, through list markers and extra spaces.
- **Neutralization:** `_QUOTE_PREFIX_RE` back to `^[ \t]*((?:>[ \t]?)*)`.
- **Raw red** (`-k c14`):

```
..FF..FF                                                                 [100%]
FAILED ...::test_c14_a_list_item_quoted_raw_run_ends_at_its_quoted_blank_so_the_bot_body_writes
  E   AssertionError: {'ok': False, 'reason': 'write-failed', 'detail': 'the advisor-vet marker sits inside an unclosed HTML comment, so the slot would not render'}
FAILED ...::test_c14_a_double_spaced_quote_prefix_ends_at_its_quoted_blank_so_the_bot_body_writes
  E   AssertionError: {'ok': False, 'reason': 'write-failed', 'detail': 'the advisor-vet marker sits inside an unclosed HTML comment, so the slot would not render'}
FAILED ...::test_c14_comment_scan_raw_run_blankness_and_depth[list-marker-quote-depth]
FAILED ...::test_c14_comment_scan_raw_run_blankness_and_depth[double-space-quote-depth]
4 failed, 4 passed, 44 deselected in 0.49s
```

- **Restore:** inverse Edit.
- **Restore receipt:** `vet_slot.py:100` reads `_QUOTE_PREFIX_RE = re.compile(r"^([ \t>*+\-0-9.)]*)")`.
- **Raw green:**

```
........                                                                 [100%]
8 passed, 44 deselected in 0.47s
```

### K14b: removing one mark takes indentation and list markers with it

- **Guarded element / axis:** `_ONE_QUOTE_MARK_RE` (`vet_slot.py:102`); a continuation line `  >` and a list line
  `- >` both lose their mark.
- **Neutralization:** `_ONE_QUOTE_MARK_RE` back to `^[ \t]*>[ \t]?`.
- **First red run, honest note:** with only the first eight C14 tests the neutralization did **not** bite
  (`8 passed, 44 deselected`): E2 and E3 use `  >` continuation lines, which the old
  remover also strips. The row `list-marker-quoted-blank` (`"- > <div>\n- >\n- > `<!--`\nnext\n"`) was added to
  the C14 rows test, and the neutralization re-run:
- **Raw red** (`-k c14`, with the added row):

```
........F                                                                [100%]
FAILED ...::test_c14_comment_scan_raw_run_blankness_and_depth[list-marker-quoted-blank]
  E   assert [False, False, False, True] == [False, False, False, False]
1 failed, 8 passed, 44 deselected in 0.47s
```

- **Restore:** inverse Edit.
- **Restore receipt:** `vet_slot.py:102` reads `_ONE_QUOTE_MARK_RE = re.compile(r"^[ \t*+\-0-9.)]*>[ \t]?")`.
- **Raw green** (the whole file):

```
.....................................................                    [100%]
53 passed in 0.54s
```

## Vet-816 redesign: the body-level gate (G-gate)

Vet 816 of PR #2347 found fail-opens in the raw-run tracking: an HTML tag line ending in U+2028, U+0085 or a form feed,
and declaration, CDATA and processing-instruction blocks, hid the owner half in a comment the line scanner could not
see. A line scanner cannot track CommonMark's HTML blocks, so the design was replaced: `_comment_scan` exempts a
`<!--` inside an inline code span or after a backslash escape only in a body with no line that could open an HTML
block (`_could_open_html_block`); in every other body every `<!--` outside a fenced code block opens a comment, as on
`main`. On a line where a comment closes, the rest of that line is matched plainly even in an exempt body.

**K5–K14's guarded code was removed**: `_RAW_HTML_START_RE`, `_QUOTE_PREFIX_RE`, `_ONE_QUOTE_MARK_RE`,
`_strip_quote_marks`, the `raw_html` / `raw_depth` state and the `if raw_html:` branch, with their `# axis:` comments.
The K5–K14 entries above are history of that code and prove nothing on the current head; the surviving elements are K1
to K4 (code-span skip, escape skip, unclosed-run rule, in-comment closer) and G1 to G6 below. The tests that asserted a
write through the raw-run tracking or through the exemption in a body with an HTML-block line were rewritten to the
refusal they now give (V7), each with a one-line comment; none was deleted.

Method: Edit-tool neutralizations, inverse-Edit restores; no `git checkout`, `restore`, `reset` or `stash`. Command
prefix as above (`--tb=short`). The captures below are the runner's lines with the `UV_NATIVE_TLS` warning line, the
traceback bodies and the repeated `E` lines cut by hand; counts and `FAILED` node ids are exact. Nothing was redacted;
each capture is far under 32 KiB. Guarded-element set (declared by the order): G1 to G6.

### Pre-change red receipts of V1–V3, V5, V6 (head `117c1037`, before any `vet_slot.py` edit)

The C15 tests were written first and run on the unchanged head, `-k "c15 and not could_open_html_block"`.

A first run used `"<div> " + SEP + "`<!--`…"` with the separator inline: the u2028, u0085 and form-feed cases passed
there (`12 failed, 15 passed`), because the old scan split the line at the separator and kept the raw run going. The
shape that matches the orchestrator's measured fail-open is the separator **followed by a real newline** (the old scan
then saw a blank line and ended the raw run; CommonMark sees one tag line that carries on). The C15 openers use that
shape (the inline form stays as the `u2028-inline` row).

Second run, openers `"<div> " + SEP + "\n"`, `<!DOCTYPE html>\n`, `<![CDATA[ x ]]>\n`, `<?xml x?>\n`:

```
FFFFF.FFFFF.FFF.FFF.FF.FFF..                                             [100%]
FAILED ...::test_c15_a_builder_body_...refuses_body_emptied[u2028]
FAILED ...::test_c15_a_builder_body_...refuses_body_emptied[u0085]
FAILED ...::test_c15_a_builder_body_...refuses_body_emptied[formfeed]
FAILED ...::test_c15_a_builder_body_...refuses_body_emptied[doctype]
FAILED ...::test_c15_a_builder_body_...refuses_body_emptied[cdata]
FAILED ...::test_c15_a_bot_body_...refuses_write_failed[u2028]
FAILED ...::test_c15_a_bot_body_...refuses_write_failed[u0085]
FAILED ...::test_c15_a_bot_body_...refuses_write_failed[formfeed]
FAILED ...::test_c15_a_bot_body_...refuses_write_failed[doctype]
FAILED ...::test_c15_a_bot_body_...refuses_write_failed[cdata]
FAILED ...::test_c15_a_comment_closing_mid_line_then_a_quoted_opener_refuses_write_failed
FAILED ...::test_c15_a_format_character_before_a_tag_still_gates_the_body[bom]
FAILED ...::test_c15_a_format_character_before_a_tag_still_gates_the_body[zwsp]
FAILED ...::test_c15_comment_scan_gate_rows[u2028] [u0085] [formfeed] [doctype] [cdata] [bom] [zwsp] [comment-tail]
21 failed, 7 passed, 70 deselected in 0.77s
```

Each red is a write where a refusal is owed (`assert result["ok"] is False` met `{'ok': True, 'verb': 'write', ...}`),
or a `starts_in_comment` row reading `False` where `True` is owed. The two `[pi]` cases (builder and bot) **passed** on
the old head, as the orchestrator measured (the raw-run start pattern caught `<?`); they must still refuse, and do. The
V1 u2028, u0085, form-feed, V2 doctype, cdata, V3 (five openers), V5 and V6 (bom, zwsp) cases were red: the measured
`True None` rows reproduced. (The first run's `V5` red also reproduced: `[False, False] == [False, True]` on the
comment-tail row.)

### G1: the gate

- **Guarded element / axis:** `exempt = not _could_open_html_block(body)` (`vet_slot.py:223`); a body with a line that
  could open an HTML block gets no escape or code-span exemption (V1, V2, V3, both callers).
- **Neutralization:** `exempt = not _could_open_html_block(body)` became `exempt = True`.
- **Raw red** (`-k "test_c15_a_builder or test_c15_a_bot"`):

```
FFFFFFFFFFFF                                                             [100%]
FAILED ...::test_c15_a_builder_body_...refuses_body_emptied[u2028] [u0085] [formfeed] [doctype] [cdata] [pi]
FAILED ...::test_c15_a_bot_body_...refuses_write_failed[u2028] [u0085] [formfeed] [doctype] [cdata] [pi]
  E   AssertionError: {'ok': True, 'verb': 'write', 'followups': ['FU1', 'FU2'], 'receipt': 'https://x/c/1'}
  E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1'}
12 failed, 86 deselected in 0.55s
```

- **Restore:** inverse Edit.
- **Restore receipt:** `vet_slot.py:223` reads `    exempt = not _could_open_html_block(body)`.
- **Raw green** (same selector):

```
............                                                             [100%]
12 passed, 86 deselected in 0.54s
```

### G2: the comment-opener exclusion

- **Guarded element / axis:** `if text.startswith("<!--"): continue` (`vet_slot.py:199`); a comment-opener line is left
  to the comment state and does not gate the body (V4 comment-line test).
- **Neutralization:** `if text.startswith("<!--"):` became `if False and text.startswith("<!--"):`.
- **Raw red** (`-k "test_c11_a_comment_line or test_c15_could_open_html_block"`):

```
F.......FF........                                                       [100%]
FAILED ...::test_c11_a_comment_line_does_not_make_the_next_line_raw
  E   AssertionError: {'ok': False, 'reason': 'write-failed', 'detail': 'the advisor-vet marker sits inside an unclosed HTML comment, so the slot would not render'}
FAILED ...::test_c15_could_open_html_block[comment]
FAILED ...::test_c15_could_open_html_block[quoted-comment]
3 failed, 15 passed, 80 deselected in 0.62s
```

- **Restore:** inverse Edit.
- **Restore receipt:** `vet_slot.py:199` reads `        if text.startswith("<!--"):`.
- **Raw green** (same selector):

```
..................                                                       [100%]
18 passed, 80 deselected in 0.47s
```

### G3: the autolink exclusion

- **Guarded element / axis:** `if _AUTOLINK_RE.match(text): continue` (`vet_slot.py:202`); an autolink line is not an
  HTML-block line (V4 autolink test).
- **Neutralization:** `if _AUTOLINK_RE.match(text):` became `if False and _AUTOLINK_RE.match(text):`.
- **Raw red** (`-k "test_c12_an_autolink or test_c15_could_open_html_block"`):

```
F.........FF......                                                       [100%]
FAILED ...::test_c12_an_autolink_line_is_not_raw_html_so_a_later_quoted_opener_is_text
  E   AssertionError: {'ok': False, 'reason': 'write-failed', 'detail': 'the advisor-vet marker sits inside an unclosed HTML comment, so the slot would not render'}
FAILED ...::test_c15_could_open_html_block[autolink]
FAILED ...::test_c15_could_open_html_block[mailto-autolink]
3 failed, 15 passed, 80 deselected in 0.45s
```

- **Restore:** inverse Edit.
- **Restore receipt:** `vet_slot.py:202` reads `        if _AUTOLINK_RE.match(text):`.
- **Raw green** (same selector):

```
..................                                                       [100%]
18 passed, 80 deselected in 0.46s
```

### G4: the Unicode strip

- **Guarded element / axis:** `line[start].isspace() or unicodedata.category(line[start]) == "Cf"`
  (`vet_slot.py:193`); a byte-order mark, a zero-width space or other whitespace before the tag is skipped, so the line
  still gates the body (V6).
- **Neutralization:** the loop condition became `while start < len(line) and (line[start] in _BLOCK_LEAD_ASCII):`
  (the ASCII set only).
- **Raw red** (`-k "format_character or gate_rows or could_open_html_block"`):

```
FF.......FF................FFF.                                          [100%]
FAILED ...::test_c15_a_format_character_before_a_tag_still_gates_the_body[bom]
FAILED ...::test_c15_a_format_character_before_a_tag_still_gates_the_body[zwsp]
  E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1'}
FAILED ...::test_c15_comment_scan_gate_rows[bom]
FAILED ...::test_c15_comment_scan_gate_rows[zwsp]
  E   assert [False, False, False] == [False, False, True]
FAILED ...::test_c15_could_open_html_block[nbsp]
FAILED ...::test_c15_could_open_html_block[bom]
FAILED ...::test_c15_could_open_html_block[zwsp]
7 failed, 24 passed, 67 deselected in 0.60s
```

- **Restore:** inverse Edit (the two-line condition put back).
- **Restore receipt:** `vet_slot.py:192-193` read `        while start < len(line) and (line[start] in _BLOCK_LEAD_ASCII` /
  `                                     or line[start].isspace() or unicodedata.category(line[start]) == "Cf"):`.
  (`:193` was confirmed by a later grep.)
- **Raw green** (same selector):

```
...............................                                          [100%]
31 passed, 67 deselected in 0.49s
```

### G5: the comment-tail rule

- **Guarded element / axis:** `plain = True` after a comment closes (`vet_slot.py:238`); the rest of a line on which a
  comment closes is matched plainly even in an exempt body (V5).
- **Neutralization:** `plain = True` became `plain = plain`.
- **Raw red** (`-k "comment_closing_mid_line or gate_rows"`):

```
F.........F..                                                            [100%]
FAILED ...::test_c15_a_comment_closing_mid_line_then_a_quoted_opener_refuses_write_failed
  E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1'}
FAILED ...::test_c15_comment_scan_gate_rows[comment-tail]
  E   assert [False, False] == [False, True]
2 failed, 11 passed, 85 deselected in 0.49s
```

- **Restore:** inverse Edit.
- **Restore receipt:** `vet_slot.py:238` reads `                plain = True`.
- **Raw green** (same selector):

```
.............                                                            [100%]
13 passed, 85 deselected in 0.45s
```

### G6: the exemption itself (the code-span branch, K1's element)

- **Guarded element / axis:** `elif line[pos] == "`":` (the branch after the backslash branch, `vet_slot.py:251` by
  position); an inline code span hides an opener in an exempt body (V4 C1 test).
- **Neutralization:** `elif line[pos] == "`":` became `elif False and line[pos] == "`":`.
- **Raw red** (`-k "test_c1_"`):

```
FF                                                                       [100%]
FAILED ...::test_c1_run_verb_writes_a_bot_body_that_quotes_the_opener_in_inline_code
FAILED ...::test_c1_evaluate_composes_the_same_body
  E   AssertionError: {'ok': False, 'reason': 'write-failed', 'detail': 'the advisor-vet marker sits inside an unclosed HTML comment, so the slot would not render'}
2 failed, 96 deselected in 0.40s
```

- **Restore:** inverse Edit (`elif False and line[pos] == "`":` back to `elif line[pos] == "`":`).
- **Restore receipt:** disclosed gap: the confirming `grep -n 'elif line\[pos\] == "`"' …vet_slot.py` was **refused**
  twice (once inside a compound, once in plain form: "This command requires approval") and was not retried; the
  restored line is therefore not quoted from the file. The restore is evidenced by the inverse Edit's success report and
  the green run below, which fails on the neutralized line.
- **Raw green** (`-k "test_c1_"`):

```
..                                                                       [100%]
2 passed, 96 deselected in 0.38s
```

### Whole-file and neighbouring-suite runs after the last restore

```
plugins/superheroes/lib/tests/test_vet_slot_comment_scan_inline_code_2342.py
98 passed in 0.67s
```

```
test_vet_slot.py test_vet_slot_emptied_2323.py test_vet_slot_leftovers_2280.py test_vet_slot_owner_commands.py test_vet_slot_no_build_record_2342.py
495 passed in 3.09s
```

### Elements in no class

None: G1 to G6 each have their own neutralization and red. The `dead` (fenced line) guard and K1–K4's other branches are
pre-existing and not re-proved here beyond K1–K4 above.

## Test renames (vet 817)

The captures above keep the names the tests had when they ran (seven of the eight earlier names appear in them).

| Earlier name | Current name |
| --- | --- |
| `test_c2_run_verb_does_not_refuse_body_emptied_for_an_inline_code_opener_above_the_heading` | `test_c2_run_verb_refuses_body_emptied_for_an_inline_code_opener_above_the_heading` |
| `test_c2_evaluate_does_not_refuse_body_emptied` | `test_c2_evaluate_refuses_body_emptied` |
| `test_c11_a_blank_line_ends_the_raw_block_so_a_later_quoted_opener_is_text_again` | `test_c11_a_blank_line_after_the_raw_block_still_refuses_write_failed_for_a_later_quoted_opener` |
| `test_c12_a_tag_inside_a_comment_starts_no_raw_run` | `test_c12_a_tag_inside_a_comment_still_refuses_write_failed_for_the_quoted_opener` |
| `test_c12_a_quoted_blank_line_ends_a_quoted_raw_run` | `test_c12_a_quoted_blank_line_raw_run_body_refuses_write_failed` |
| `test_c14_a_list_item_quoted_raw_run_ends_at_its_quoted_blank_so_the_bot_body_writes` | `test_c14_a_list_item_quoted_raw_run_body_refuses_write_failed` |
| `test_c14_a_double_spaced_quote_prefix_ends_at_its_quoted_blank_so_the_bot_body_writes` | `test_c14_a_double_spaced_quote_prefix_body_refuses_write_failed` |
| `test_c14_a_line_of_ascii_spaces_and_tabs_still_ends_a_raw_run` | `test_c14_a_line_of_ascii_spaces_and_tabs_in_an_html_block_body_leaves_the_quoted_opener_a_comment` |

## Review session 7: splitlines-only breaks turn the exemption off (G7)

Finding test-s4-001 (Important): on the line where a comment closes, `_comment_scan` matches the rest of the line plainly
(`plain = True`), but that state resets at every `str.splitlines()` boundary. U+2028, U+0085, a form feed and the other
splitlines-only separators are not Markdown line endings, so in a body with no HTML-block line (exemption on) a quoted
`<!--` after one was read as inline code, while a browser opens a comment on the comment's closing line over the owner
heading, and the write passed `body-emptied`. Fix (the advisor's option c): the exemption is also off when the body holds
any of the eight characters `_SPLITLINES_ONLY_BREAKS` (U+2028, U+2029, U+0085, `\x0b`, `\x0c`, `\x1c`, `\x1d`, `\x1e`).
`_comment_scan`'s loop, state and signature are unchanged. Base `2538b4cb`. Method as above: Edit-tool neutralizations,
inverse-Edit restores; no `git checkout`, `restore`, `reset` or `stash`. Command prefix as above (`--tb=short`, `--tb=line`
for the G7 red). Guarded-element set (declared by the order): G7 (the clause at the gate) and G7a (the eight characters,
one failure-mode class). Detector: the `J` section of `test_vet_slot_comment_scan_inline_code_2342.py`.

Disclosures:
- Captures are the runner's lines with the `UV_NATIVE_TLS` warning line, the repeated `E` lines and the `FAILED` node-id
  path prefix cut by hand; counts are exact. Nothing was redacted; each capture is far under 32 KiB.
- The G7 red and green runs ran while the constant was still spelled with two literal characters for U+2028 and U+2029
  (the edit tool had turned the two four-digit unicode escapes into the characters). Both were then respelled
  `\N{LINE SEPARATOR}\N{PARAGRAPH SEPARATOR}` (same value), and the G7a run, its green, and the J5 run all ran on the
  escaped spelling.

### Pre-change receipt (head `2538b4cb`, `vet_slot.py` unedited)

The J tests were written first and run on the unedited file, `-k "test_j"`:

```
FFFFFF..FFFFFFFF.F                                                       [100%]
FAILED ...::test_j1_..._refuses_body_emptied[u2028-evaluate]
FAILED ...::test_j1_..._refuses_body_emptied[u2028-run_verb]
FAILED ...::test_j1_..._refuses_body_emptied[nel-evaluate]
FAILED ...::test_j1_..._refuses_body_emptied[nel-run_verb]
FAILED ...::test_j1_..._refuses_body_emptied[ff-evaluate]
FAILED ...::test_j1_..._refuses_body_emptied[ff-run_verb]
FAILED ...::test_j3_each_of_the_eight_splitlines_only_breaks_turns_the_exemption_off[u2028] [u2029] [nel] [vt] [ff] [fs] [gs] [rs]
FAILED ...::test_j4_a_body_without_a_splitlines_only_break_keeps_the_exemption
  E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1'}
  E   assert [False, False, False] == [False, False, True]
15 failed, 3 passed, 98 deselected in 0.69s
```

The three passes are the two LF controls (J2, both entry points) and the premise test (each of the eight characters
splits a line under `splitlines()` and none is CR or LF). The six J1 reds are the orchestrator's measured set.

### G7: the new clause at the gate

- **Guarded element / axis:** `exempt = not _could_open_html_block(body) and not any(ch in body for ch in
  _SPLITLINES_ONLY_BREAKS)` (`vet_slot.py:229`); a body holding a splitlines-only line break gets no escape or code-span
  exemption (J1 through both entry points, J3 for all eight characters, J4 on the scan itself).
- **Neutralization:** the gate line became `    exempt = not _could_open_html_block(body)` (the line the head had).
- **Raw red** (`-k "test_j"`, `--tb=line`):

```
FFFFFF..FFFFFFFF.F                                                       [100%]
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1', ...}
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1'}
E   assert [False, False, False] == [False, False, True]
FAILED ...::test_j1_..._refuses_body_emptied[u2028-evaluate] [u2028-run_verb] [nel-evaluate] [nel-run_verb] [ff-evaluate] [ff-run_verb]
FAILED ...::test_j3_each_of_the_eight_splitlines_only_breaks_turns_the_exemption_off[u2028] [u2029] [nel] [vt] [ff] [fs] [gs] [rs]
FAILED ...::test_j4_a_body_without_a_splitlines_only_break_keeps_the_exemption
15 failed, 3 passed, 98 deselected in 0.72s
```

(Elided: the 15 per-test `E` blocks, repeats of the lines shown.)

- **Restore:** inverse Edit (the clause put back).
- **Restore receipt:** `vet_slot.py:229` reads `    exempt = not _could_open_html_block(body) and not any(ch in body for ch in _SPLITLINES_ONLY_BREAKS)`.
- **Raw green** (same selector): `18 passed, 98 deselected in 0.41s`.

### G7a: the eight characters (one failure-mode class)

- **Class:** each dropped character lets its own separator reopen the exemption in a body that holds it. **Representative:**
  `\x1e`. J3 holds one case per character (ids `u2028 u2029 nel vt ff fs gs rs`), so each of the eight turns its own case
  red when dropped; the representative was run, the other seven are covered by the same shape and not individually
  neutralized.
- **Guarded element / axis:** `_SPLITLINES_ONLY_BREAKS` (`vet_slot.py:104`); every one of the eight splitlines-only
  breaks must be in the constant.
- **Neutralization:** `\x0c\x1c\x1d\x1e"` became `\x0c\x1c\x1d"` (the constant minus `\x1e`).
- **Raw red** (`-k "test_j"`):

```
...............F..                                                       [100%]
FAILED ...::test_j3_each_of_the_eight_splitlines_only_breaks_turns_the_exemption_off[rs]
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1', ...}
E   assert (True is False)
1 failed, 17 passed, 98 deselected in 0.52s
```

- **Restore:** inverse Edit (`\x1e` put back).
- **Restore receipt:** `vet_slot.py:104` reads `_SPLITLINES_ONLY_BREAKS = "\N{LINE SEPARATOR}\N{PARAGRAPH SEPARATOR}\x85\x0b\x0c\x1c\x1d\x1e"`.
- **Raw green** (same selector): `18 passed, 98 deselected in 0.48s`.

### Regression run (J5), after the final edit

```
test_vet_slot.py test_vet_slot_emptied_2323.py test_vet_slot_leftovers_2280.py test_vet_slot_owner_commands.py test_vet_slot_no_build_record_2342.py test_vet_slot_comment_scan_inline_code_2342.py test_vet_slot_builder_path_verdict_read_2342.py
682 passed in 3.27s
```

### Elements in no class

None: G7 and G7a each have a neutralization and a red.
