# Bite-proof record: i2389_scanner_line_boundaries (#2389, layer 2 of #2366) leftover and PR-sheet scanners on Markdown lines; `_visible` reads `md_hidden`

Detector under proof: `plugins/superheroes/lib/tests/test_scanner_line_boundaries_2389.py` (unedited between the red and the green of every entry).
Guarded code: `plugins/superheroes/lib/leftover_accepting.py` (`_visible`) and `plugins/superheroes/lib/pr_sheet.py`
(`accepting_listed`, `degradations_listed`, the shared `_markdown_lines`). Base head `03ca874e`.
Every neutralization was a targeted edit made with the Edit tool and undone by the inverse Edit before the next element.
No `git checkout`, `restore`, `reset` or `stash` was used.
Command prefix for every run (worktree root), `-k` as per entry:
`timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_scanner_line_boundaries_2389.py -q -p no:cacheprovider -k test_gN_`
Restore receipts are the restored lines, quoted back by a `grep -n` after each inverse Edit.

Guarded-element set (declared by the order): G1 `_visible`'s split; G2 `_visible`'s md_hidden intersection; G3
`accepting_listed`'s split; G4 `degradations_listed`'s split. No others.

Disclosures:
- Captures are the runner's output with uv's one `UV_NATIVE_TLS` deprecation warning line dropped (it begins every run).
  Nothing was redacted. Pytest prints the test source with the U+2028-class characters as raw bytes; they show here as
  the terminal showed them.
- G1's red capture is quoted in part (the first two failures verbatim, the eight parametrized failures of one test
  collapsed to its summary lines; the full capture was under the 32 KiB ceiling, and the elision is only for repetition). G2's red capture was 84,747 bytes, over the 32 KiB ceiling: it was written to
  `/tmp/claude-0/-home-user-sh-2389-wob/67541316-b25e-4a78-96ba-75c6feb326c0/scratchpad/g2_red.txt` (outside the repository) and the
  decisive lines are quoted below; the elided part is the failure bodies of 44 repetitions of one fixture-row test
  (its `FAILED` lines are summarised by count).
- The CR and CRLF variants of the G1, G3 and G4 tests, and the `-k test_g1_` tests that read `\r`, are same-answer
  tests: `str.splitlines` also breaks on `\r` and `\r\n`, so they stay **green** on the neutralized code. They are not
  the discriminating tests (the U+2028-class ones are); the red counts below show it (G1: 10 of 19 red; G3: 4 of 7; G4: 5 of 5).
- Two G2 tests stay green with the intersection disabled and are not the discriminating ones: the marker-line
  exception test (`...keeps_a_marker_line_whatever_md_hidden_reads`, a keep-direction test) and the no-div READY write.
  They pin the exception and the pass direction, not the cut.

## G1: `_visible` splits on Markdown line endings

- **Guarded element / axis:** `leftover_accepting.py:105`, `lines = md_fence.split_lines(body)` (axis comment at `:106`);
  only CR, LF and CRLF end a line, so a U+2028 (and U+2029, U+0085, VT, FF, FS, GS, RS) inside a line cannot make a fence
  or marker line that the Markdown reading does not have. Axis: a comment is cut (or kept as a marker or fenced line) by
  the Markdown reading of the line, not by a separator character GitHub does not break on.
- **Neutralization:** `leftover_accepting.py:105` `    lines = md_fence.split_lines(body)` became
  `    lines = body.splitlines(keepends=True)`. The module still imports.
- **Raw red** (`-k test_g1_`), summary and first two failures verbatim; the other eight failures are the parametrized
  `test_g1_visible_split_every_other_str_splitlines_break_is_an_ordinary_character[...]` with the same `<!-- c -->` kept:

```
FFFFFFFFFF.........                                                      [100%]
=================================== FAILURES ===================================
____________ test_g1_visible_split_u2028_does_not_make_a_fence_line ____________
E   AssertionError: assert 'x \n<!-- c -->\n' == 'x ```\n\n'
E     - ```
E       
E     + <!-- c -->

___________ test_g1_visible_split_u2028_does_not_make_a_marker_line ____________
E   AssertionError: assert 'a <!-- ...eroes:x -->\n' == 'a \n'
E     - 
E     + <!-- superheroes:x -->
...
FAILED ...::test_g1_visible_split_u2028_does_not_make_a_fence_line
FAILED ...::test_g1_visible_split_u2028_does_not_make_a_marker_line
FAILED ...::test_g1_visible_split_every_other_str_splitlines_break_is_an_ordinary_character[ ]
FAILED ...[ ]  FAILED ...[\x85]  FAILED ...[\x0b]  FAILED ...[\x0c]  FAILED ...[\x1c]  FAILED ...[\x1d]  FAILED ...[\x1e]
10 failed, 9 passed, 145 deselected in 1.34s
```

  The red is on the axis: with `str.splitlines` the separator splits `x<sep>```` into a fence opener (the comment under it is
  shown) and `a<sep><!-- superheroes:x -->` into a kept marker line, where the Markdown reading cuts the comment.
- **Restore:** inverse Edit, `body.splitlines(keepends=True)` back to `md_fence.split_lines(body)`.
- **Restore receipt:** `grep -n` printed `105:    lines = md_fence.split_lines(body)` and, for `splitlines`, only the axis comment at `:106`.
- **Raw green** (same `-k`):

```
...................                                                      [100%]
19 passed, 145 deselected in 1.82s
```

## G2: `_visible` keeps nothing `md_hidden` does not read VISIBLE

- **Guarded element / axis:** `leftover_accepting.py:113`, `shown.append(rendering.state_at(offset) == md_hidden.VISIBLE)`,
  read at the fenced branch (`out.append(line if shown[n] else term)`) and at the end of the loop (`if not shown[n]: text = term`);
  a line whose start `md_hidden` reads hidden or unsure contributes only its terminator (a `_MARKER_LINE` line excepted).
  Axis: text GitHub renders hidden is never kept (the fail direction is the leftover check refusing `leftover-not-accepted`).
  The one neutralization reaches both sites, which read the one `shown` list.
- **Neutralization:** `leftover_accepting.py:113` `            shown.append(rendering.state_at(offset) == md_hidden.VISIBLE)`
  became `            shown.append(True)` (every line reads as visible; the comment cut alone remains). The module still imports.
- **Raw red** (`-k test_g2_`): 49 failed, 79 passed, 36 deselected. Full capture (84,747 bytes) outside the repository at the scratchpad
  path above; decisive lines quoted:

```
F.F.FFF.......FF..FFFF................FF..FFFF..FF................FFFFFF [ 56%]
FF..FFFF....FFFFFF..........FFFF........FF..FFFF..FF....                 [100%]
E       AssertionError: assert ('f-1' not in 'Closes #1.\...</details>\n'
E         'f-1' is contained here:
E           - f-1 the retry loop never backs off: merging accepts slower recovery.
E       AssertionError: assert ('secret' not in 'x\n\n<div>\...`\n\nafter\n'
E       AssertionError: assert 'one\n<!-- su...ee\n```\nlast' == '\n<!-- super...>\r\n\r\n\n\n'
E       AssertionError: assert 'one\ntwo\n' == '\n\n'
E       assert (True is False)          <- the READY write: result["ok"] was True, refusal owed
E               AssertionError: a line md_hidden does not read VISIBLE kept text: '</pre>\n'
E               AssertionError: a line md_hidden does not read VISIBLE kept text: "## What's changing, and why\n"
E               AssertionError: a line md_hidden does not read VISIBLE kept text: '## Advisor vet\n'
FAILED ...::test_g2_visible_md_hidden_drops_an_acceptance_the_comment_cut_alone_would_keep
FAILED ...::test_g2_visible_md_hidden_blanks_a_fenced_line_md_hidden_reads_hidden
FAILED ...::test_g2_visible_md_hidden_scan_failure_keeps_only_markers_and_terminators
FAILED ...::test_g2_visible_md_hidden_a_line_start_md_hidden_does_not_report_reads_as_not_visible
FAILED ...::test_g2_visible_md_hidden_ready_write_refuses_an_acceptance_hidden_after_a_div_plain_closer
FAILED ...::test_g2_visible_md_hidden_github_render_rows_leave_no_hidden_line_behind[...]   (44 rows, builder and bot forms)
49 failed, 79 passed, 36 deselected in 2.75s
```

  The red is on the axis in every shape: the acceptance under the layer-1 `div_plain_closer` shape is kept
  (`f-1 ... merging accepts slower recovery.`) and the READY write succeeds (`result["ok"] is True`) where the refusal
  `leftover-not-accepted` is owed; a fenced hidden line (`secret`) is kept; and 44 GitHub-render fixture rows keep a line
  `md_hidden` does not read VISIBLE.
- **Restore:** inverse Edit, `shown.append(True)` back to `shown.append(rendering.state_at(offset) == md_hidden.VISIBLE)`.
- **Restore receipt:** `grep -n shown.append` printed `113:            shown.append(rendering.state_at(offset) == md_hidden.VISIBLE)` and
  `115:            shown.append(False)  # a line start md_hidden does not report reads as not visible: the cut fails closed`.
- **Raw green** (same `-k`):

```
........................................................................ [ 56%]
........................................................                 [100%]
128 passed, 36 deselected in 0.86s
```

## G3: `accepting_listed` splits on Markdown line endings

- **Guarded element / axis:** `pr_sheet.py:350`, `lines = _outside_comments(_markdown_lines(body))` (axis comment at `:349`);
  a U+2028 inside a line cannot make a synthetic `## ` heading that ends the What we're accepting section.
- **Neutralization:** `pr_sheet.py:350` `    lines = _outside_comments(_markdown_lines(body))` became
  `    lines = _outside_comments(body.splitlines())`. The module still imports.
- **Raw red** (`-k test_g3_`); one of the four failures shown, the other three are the same assertion under `\n`, `\r`, `\r\n`:

```
FFFF...                                                                  [100%]
_ test_g3_accepting_listed_split_u2028_cannot_make_a_heading_that_ends_the_section _
>       assert pr_sheet.accepting_listed(ACCEPTING_U2028) == ACCEPTING_ITEMS
E       AssertionError: assert ['item one'] == ['item one ## Not a heading', 'item two']
E         At index 0 diff: 'item one' != 'item one ## Not a heading'
E         Right contains one more item: 'item two'
FAILED ...::test_g3_accepting_listed_split_u2028_cannot_make_a_heading_that_ends_the_section
FAILED ...::test_g3_accepting_listed_split_same_answer_under_every_line_ending[\n]
FAILED ...::test_g3_accepting_listed_split_same_answer_under_every_line_ending[\r]
FAILED ...::test_g3_accepting_listed_split_same_answer_under_every_line_ending[\r\n]
4 failed, 3 passed, 157 deselected in 0.39s
```

  The red is on the axis: the section ends at the synthetic heading, so `item two` is lost (an acceptance not seen).
  (The `[\n]`, `[\r]`, `[\r\n]` cases carry the U+2028 in their body, so they bite for that reason; the
  pure-line-ending test `test_g3_accepting_listed_split_a_real_heading_still_ends_the_section` stays green, as intended.)
- **Restore:** inverse Edit, `body.splitlines()` back to `_markdown_lines(body)`.
- **Restore receipt:** `grep -n "_markdown_lines\|splitlines"` printed `350:    lines = _outside_comments(_markdown_lines(body))`.
- **Raw green** (same `-k`):

```
.......                                                                  [100%]
7 passed, 157 deselected in 0.39s
```

## G4: `degradations_listed` splits on Markdown line endings

- **Guarded element / axis:** `pr_sheet.py:405`, `lines = _markdown_lines(body)` (axis comment at `:404`); a U+2028 inside a
  line cannot make a synthetic heading that ends the degradations list and drops a costly bullet after it (PRE2389-3).
- **Neutralization:** `pr_sheet.py:405` `    lines = _markdown_lines(body)` became `    lines = body.splitlines()`.
  The module still imports.
- **Raw red** (`-k test_g4_`); the first failure and the `costly_unlisted` one shown, the `\n`, `\r`, `\r\n` cases are the first assertion again:

```
FFFFF                                                                    [100%]
_ test_g4_degradations_listed_split_u2028_cannot_make_a_heading_that_ends_the_list _
>       assert pr_sheet.degradations_listed(DEGRADATIONS_U2028) == DEGRADATIONS_LISTED
E       AssertionError: assert [('harmless', 'note')] == [('harmless',...ly', 'later')]
E         At index 0 diff: ('harmless', 'note') != ('harmless', 'note ## End')
E         Right contains one more item: ('costly', 'later')
___ test_g4_degradations_listed_split_costly_unlisted_sees_the_costly_bullet ___
>       assert pr_sheet.costly_unlisted(DEGRADATIONS_U2028) == [("costly", "later")]
E       AssertionError: assert [] == [('costly', 'later')]
5 failed, 159 deselected in 0.51s
```

  The red is on the axis: the costly bullet after the U+2028 is not listed, so `costly_unlisted` returns `[]`.
- **Restore:** inverse Edit, `body.splitlines()` back to `_markdown_lines(body)`.
- **Restore receipt:** `grep -n "_markdown_lines\|splitlines"` printed `405:    lines = _markdown_lines(body)` (and `982` is the untouched `_vet_record` line).
- **Raw green** (same `-k`):

```
.....                                                                    [100%]
5 passed, 159 deselected in 0.35s
```

## Whole scoped run after the last restore

The eight-file scoped command of the order (`-q -n auto`): `1037 passed in 22.67s`.

## Findings

1. **A hidden or cut last line with no terminator leaves no line.** The order gives `""` for a last line with none, so
   when that last line is blanked the output has one Markdown line fewer than the input (`split_lines("")` is `[]`, and
   a trailing `"x"` becomes `""`). Every line that has a terminator keeps its line. The fixture-row test accounts for
   exactly that one case (`test_g2_visible_md_hidden_github_render_rows_leave_no_hidden_line_behind`); it first failed on 24 of the
   120 rows (rows whose unterminated last line, the Claude Code footer, is hidden) before that allowance was written. It
   cannot matter to a reader of the text, since the line is empty either way.
2. **The CR and CRLF same-answer tests are not discriminating** (see Disclosures): `str.splitlines` breaks on them too.

## Elements in no class

None: G1 to G4 each have their own neutralization and red. Unproven elements: none.
