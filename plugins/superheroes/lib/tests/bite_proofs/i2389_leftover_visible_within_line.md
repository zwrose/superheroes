# Bite-proof record: i2389_leftover_visible_within_line (#2389 V847-1, BR684-2, BR684-3; fix leg of vet 847) `_visible` never keeps text GitHub hides within a line

Detector under proof: `plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py` (unedited between the red and the green of every entry).
Guarded code: `plugins/superheroes/lib/leftover_accepting.py` (`_visible`, the char loop and the fenced-line branch). Base head `e18731af`.
Every neutralization was one targeted edit made with the Edit tool and undone by the inverse Edit before the next element.
No `git checkout`, `restore`, `reset`, `stash` or `sed` was used.
Command prefix for every run (worktree root), `-k` as per entry:
`timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py -q -p no:cacheprovider --tb=line -k test_gN_`
Restore receipts are the restored lines, quoted back by a `grep -n` after each inverse Edit.

Guarded-element set (declared by the order): G1 rule 1 (a backslash before an opener); G2 rule 2 (a code span holding an opener);
G3 rule 3 (an unescaped, unquoted `<?`, `<!` + letter or `<![`); G4 rule 4 (a line `md_fence` calls fenced). No others.

Disclosures:
- Captures are the runner's output with uv's one `UV_NATIVE_TLS` deprecation warning line dropped (it begins every run). Nothing was
  redacted. The failure bodies are `--tb=line` output, quoted in part where one test repeats (the elision is only for repetition; each
  capture was far under the 32 KiB ceiling).
- Every red below includes the READY write (`run_verb`) or `missing` reporting the wrong answer on a GitHub-render row, so the red is on the
  axis: the leftover check counts F-1 accepted where GitHub hides it.
- G3: seven of the eleven class rows bite (`decl_1`, `pi_1`, `pi_2`, `cdata_1`, `cdata_2`, `decl_3`, `pi_7`). Four stay green with rule 3
  neutralized (`pi_3`, `pi_4`, `pi_5`, `pi_6`): `md_hidden` already reads their line start not VISIBLE, so `_visible` blanks the line before
  rule 3 is reached. They are same-answer rows for this guard, not the discriminating ones.
- The two unclosed V847-1 twins (`f1_div_escaped_unclosed`, `f1_div_codespan_unclosed`) do not reach the leftover check through
  `run_verb`: the open comment makes `md_hidden` read the composed body's marker line hidden, so `evaluate` refuses `write-failed` first.
  Their G1 and G2 write tests accept either reason, and the bite is carried by the closed-shape write tests and by `missing` on every row.
- FU3 (`test_vet_slot_md_hidden_2389.py`, `test_g5_..._an_internal_md_hidden_error_refuses_never_passes`) is a tightening of an existing
  test, not in the declared set; its neutralization would be in `vet_slot.py`, outside this order's surface, so it is **unproven here**.

## G1: a backslash before an opener keeps both, then cuts the line

- **Guarded element / axis:** `leftover_accepting.py:162`, `escaped = _OPENER.match(line, i + 1)` (axis comment at `:160`-`:161`).
  Axis: an escaped opener (`\<!--`, `\<?`, `\<!X`, `\<![`) is kept as text and the rest of the line is cut, because inside an HTML block GitHub
  honours no escape and the opener hides the rest of the line.
- **Neutralization:** `escaped = _OPENER.match(line, i + 1)` became `escaped = None` (every backslash is the old two-character escape).
- **Raw red** (`-k test_g1_`), summary and the decisive failures (middle failures are the same assertion on the other openers):

```
FFFFFFFF...F..                                                           [100%]
E   AssertionError: GitHub hides F-1 in f1_div_escaped_unclosed, but the leftover check counts it accepted
E   AssertionError: GitHub hides F-1 in f1_div_escaped_closed, but the leftover check counts it accepted
E   AssertionError: assert 'a \\<!-- tail\n' == 'a \\<!--\n'
E   AssertionError: assert 'a \\<? tail\n' == 'a \\<?\n'
E   AssertionError: assert 'a \\<!X tail\n' == 'a \\<!X\n'
E   AssertionError: assert 'a \\<![CDATA[ tail\n' == 'a \\<![\n'
E   AssertionError: assert 'a \\<!-- tail\nnext -->\nz\n' == 'a \\<!--\nnext -->\nz\n'
E   AssertionError: assert 'a \\<!-- tail' == 'a \\<!--'
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1'}
    assert (True is False)          <- the READY write: result["ok"] was True, the refusal leftover-not-accepted is owed
FAILED ...::test_g1_escaped_opener_github_hides_f1_so_the_check_reports_it_missing[f1_div_escaped_unclosed]
FAILED ...::test_g1_escaped_opener_github_hides_f1_so_the_check_reports_it_missing[f1_div_escaped_closed]
FAILED ...::test_g1_escaped_opener_keeps_the_backslash_and_opener_then_cuts_the_line[...]   (6 cases)
FAILED ...::test_g1_escaped_opener_ready_write_refuses_leftover_not_accepted
9 failed, 5 passed, 88 deselected in 0.71s
```

- **Restore:** inverse Edit, `escaped = None` back to `escaped = _OPENER.match(line, i + 1)`.
- **Restore receipt:** `grep -n "escaped = "` printed `162:                escaped = _OPENER.match(line, i + 1)`.
- **Raw green** (same `-k`):

```
..............                                                           [100%]
14 passed, 88 deselected in 1.41s
```

## G2: a code span holding an opener keeps the span, then cuts the line

- **Guarded element / axis:** `leftover_accepting.py:174`, `quoted = _OPENER.search(line, i + run, end - run) if end is not None else None`
  (axis comment at `:173`); read by the `if quoted is not None: break` that follows. Axis: a code span whose content holds an opener is kept as
  text and the rest of the line is cut, because inside an HTML block GitHub honours no code span.
- **Neutralization:** the `quoted = ...` line became `quoted = None` (a span never cuts).
- **Raw red** (`-k test_g2_`), summary and the decisive failures:

```
FFFFFFFFFFF....F...                                                      [100%]
E   AssertionError: GitHub hides F-1 in f1_details_codespan_closed, but the leftover check counts it accepted
E   AssertionError: GitHub hides F-1 in f1_details_codespan_unclosed, but the leftover check counts it accepted
E   AssertionError: GitHub hides F-1 in f1_div_codespan_unclosed, but the leftover check counts it accepted
E   AssertionError: assert 'a `<!--` tail\n' == 'a `<!--`\n'
E   AssertionError: assert 'a `<?` tail\n' == 'a `<?`\n'
E   AssertionError: assert 'a `<!X` tail\n' == 'a `<!X`\n'
E   AssertionError: assert 'a `<![` tail\n' == 'a `<![`\n'
E   AssertionError: assert 'a `see <?x` tail\n' == 'a `see <?x`\n'
E   AssertionError: assert 'a ``<!-- ` -->`` tail\n' == 'a ``<!-- ` -->``\n'
E   AssertionError: {'ok': True, 'verb': 'write', 'followups': [], 'receipt': 'https://x/c/1'}
    assert (True is False)          <- the READY write: result["ok"] was True, the refusal leftover-not-accepted is owed
12 failed, 7 passed, 83 deselected in 1.49s
```

- **Restore:** inverse Edit, `quoted = None` back to the search expression.
- **Restore receipt:** `grep -n "quoted = "` printed `174:                quoted = _OPENER.search(line, i + run, end - run) if end is not None else None`.
- **Raw green** (same `-k`):

```
...................                                                      [100%]
19 passed, 83 deselected in 0.46s
```

## G3: an unescaped, unquoted processing instruction, declaration or CDATA opener cuts from the `<`

- **Guarded element / axis:** `leftover_accepting.py:181`, `elif _PI_OPENER.match(line, i):` (axis comment at `:180`; `_PI_OPENER` at `:82`).
  Axis: `<?`, `<!` + an ASCII letter and `<![` outside a code span and not escaped cut the rest of the line, because GitHub's HTML parser reads
  them as a bogus comment and hides what is inside.
- **Neutralization:** `elif _PI_OPENER.match(line, i):` became `elif False and _PI_OPENER.match(line, i):`.
- **Raw red** (`-k test_g3_`), summary and the decisive failures:

```
.FFF...FF.FFFFFFFF...FFF.                                                [100%]
E   AssertionError: line 2 of 'decl_1' kept {'<!X', 'a>'}
E   AssertionError: line 2 of 'pi_1' kept {'<?', '?>', 'a'}
E   AssertionError: line 0 of 'pi_2' kept {'<?', '>', 'a'}
E   AssertionError: line 2 of 'cdata_1' kept {'<![CDATA[', 'a', ']]>'}
E   AssertionError: line 0 of 'cdata_2' kept {'<![CDATA[', 'a'}
E   AssertionError: line 0 of 'decl_3' kept {'<!X', 'a'}
E   AssertionError: line 0 of 'pi_7' kept {'<?><![CDATA['}
E   AssertionError: assert 'keep <? hide ?> x\n' == 'keep \n'
E   AssertionError: assert 'keep <!X hide>\n' == 'keep \n'
E   AssertionError: assert 'keep <![CDATA[ hide ]]>\n' == 'keep \n'
E   AssertionError: assert 'keep <!DOCTYPE hide>\n' == 'keep \n'
E   AssertionError: assert 'keep <?\n' == 'keep \n'
E   AssertionError: assert '- list <?x hide' == '- list '
E   AssertionError: assert [] == [{'id': 'F-1'...r backs off'}]        (x3: the BR684-3 PI line, declaration list item and CDATA bodies)
16 failed, 9 passed, 77 deselected in 0.49s
```

  The red is on the axis: the text GitHub hides inside the opener (the class oracle's hidden tokens) is kept, and `missing` counts F-1 accepted on
  each BR684-3 body.
- **Restore:** inverse Edit, `elif False and _PI_OPENER.match(line, i):` back to `elif _PI_OPENER.match(line, i):`.
- **Restore receipt:** `grep -n "_PI_OPENER"` printed `82:_PI_OPENER = re.compile(r"<\?|<![A-Za-z]|<!\[")` and `181:            elif _PI_OPENER.match(line, i):`.
- **Raw green** (same `-k`):

```
.........................                                                [100%]
25 passed, 77 deselected in 0.45s
```

## G4: a line `md_fence` calls fenced is cut at its first opener

- **Guarded element / axis:** `leftover_accepting.py:147`, `opener = _OPENER.search(line)` in the fenced-line branch (axis comment at `:146`),
  read by the `out.append(line if opener is None else line[:opener.start()] + term)` that follows. Axis: a fenced line is not trusted, because
  inside a raw HTML block (`<pre>`) the tildes are text, not a fence, and GitHub hides the comment.
- **Neutralization:** `opener = _OPENER.search(line)` became `opener = None` (a fenced line that md_hidden reads VISIBLE is copied whole).
- **Raw red** (`-k test_g4_`), summary and the decisive failures:

```
FFFFFFF....F                                                             [100%]
E   AssertionError: assert '```\nkeep <!...ut -->\n```\n' == '```\nkeep \n```\n'
E   AssertionError: assert '```\nkeep <? cut ?>\n```\n' == '```\nkeep \n```\n'
E   AssertionError: assert '~~~\nkeep <!X cut>\n~~~\n' == '~~~\nkeep \n~~~\n'
E   AssertionError: assert '```\nkeep <!...ut ]]>\n```\n' == '```\nkeep \n```\n'
E   AssertionError: assert '```\n<!-- fi...ond ?>\n```\n' == '```\n\n```\n'
E   AssertionError: assert '```\nkeep <!...n```\nafter\n' == '```\nkeep \n```\nafter\n'
E   AssertionError: assert '```\nkeep <!-- cut' == '```\nkeep '
E   AssertionError: assert [] == [{'id': 'F-1'...r backs off'}]        <- the BR684-2 <pre>/~~~ body: F-1 counted accepted
8 failed, 4 passed, 90 deselected in 0.38s
```

- **Restore:** inverse Edit, `opener = None` back to `opener = _OPENER.search(line)`.
- **Restore receipt:** `grep -n "opener = "` printed `147:            opener = _OPENER.search(line)`.
- **Raw green** (same `-k`):

```
............                                                             [100%]
12 passed, 90 deselected in 0.45s
```

## Whole scoped run after the last restore

The seven-file scoped command of the order (`-q -n auto`): `1261 passed in 26.70s`.

## Review fixes (#2389 returning review, scoped finder 001-003), proven by the builder

The build session applied these at review-code's `apply-fixes` step, commit `10b1c1b3`. It ran the probes itself in a detached probe worktree at the same tree, with targeted edits each reverted by the inverse edit, and confirmed `git diff --stat` was empty after restore. The command was `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-probe -m pytest plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py -q -p no:cacheprovider --tb=no -k test_gN_`. G4's expectations changed with G7: a fenced line holding an opener is now blanked whole, not shortened.

### G5: a comment the cut tail opens and does not close still opens the comment state

- **Guarded element / axis:** the `if opened >= 0 and tail.find("-->", opened + 4) < 0: inside = True` check after the char loop in `_visible`. Axis: a cut at `<!X>` must not skip a later unclosed `<!--`, which hides the following lines of the paragraph (scoped-finder-001).
- **Neutralization:** the condition became `if False and opened >= 0 and …`.
- **Raw red:** `1 failed, 1 passed, 105 deselected in 0.44s`. `test_g5_tail_comment_a_comment_the_cut_tail_opens_still_hides_later_lines` failed: F-1 was kept and counted accepted.
- **Raw green (restored):** `2 passed, 105 deselected in 0.39s`.

### G6: a cut tail holding a fixed-above claim blanks the whole line

- **Guarded element / axis:** `if FIXED_ABOVE_RE.search(tail): kept = []`. Axis: an acceptance never counts while the `fixed-above` claim that needs stack verification is cut away (scoped-finder-002).
- **Neutralization:** `if False and FIXED_ABOVE_RE.search(tail):`.
- **Raw red:** `1 failed, 1 passed, 105 deselected in 0.45s`. `test_g6_fixed_above_tail_a_claim_cut_from_the_line_blanks_the_whole_acceptance` failed.
- **Raw green (restored):** `2 passed, 105 deselected in 0.37s`.

### G7: a fenced line holding an opener is blanked whole, never shortened

- **Guarded element / axis:** `out.append(line if opener is None else term)` in the fenced-line branch. Axis: a shortened content line (a backtick fence line followed by ` <!-- note -->`) must never become a fence closer when the section reader re-reads it (scoped-finder-003).
- **Neutralization:** `term` became `line[:opener.start()] + term`, which is WO-C's shortening.
- **Raw red:** `1 failed, 106 deselected in 1.85s`. `test_g7_fence_delimiter_a_shortened_fenced_line_never_closes_the_fence` failed.
- **Raw green (restored):** `1 passed, 106 deselected in 0.38s`.

The builder also re-ran G1 to G4 at `611668d2`, before these fixes. Red and green matched the implementer's counts above (G1 9 failed, G2 12 failed, G3 16 failed, G4 8 failed; all green restored).

## Review round 2 fixes (fix audits and round-2 scoped finder), proven by the builder at `4f495de6`

These fixes update G6 and G7 above and add G8. The probes ran in a detached probe worktree at `4f495de6`, each targeted edit reverted by its inverse, with `git diff --stat` empty after restore. The command is the same as above, with `-k` naming the test.

- **G7 delimiter (audit of scoped-finder-003, round-2 finder v2/v0).** Guarded element: `elif fence_kinds[n] == md_fence.KIND_CONTENT:` in the fenced-line branch. A fence content line is blanked; a delimiter line is shortened, so it stays an opener or closer. Neutralization: `elif True or fence_kinds[n] == …`, which blanks every fenced line. Red: `1 failed, 113 deselected` (`test_g7_fence_delimiter_an_opener_line_holding_an_opener_stays_an_opener`). Green: `1 passed, 113 deselected`.
- **G6 block (audit of scoped-finder-002).** Guarded element: the `for m in range(first, last + 1)` loop that blanks a claimed line's whole block. Neutralization: `range(n, n + 1)`, which blanks only the claim line. Red: `1 failed, 113 deselected` (`test_g6_fixed_above_tail_a_claim_on_a_continuation_line_blanks_the_whole_item`). Green: `1 passed, 113 deselected`.
- **G8 comment-state end (round-2 finder v1).** Guarded element: `if inside and shown[n] and (not line.strip() or _ATX_LINE.match(line)): inside = False`. Neutralization: `if False and …`. Red: `2 failed, 1 passed, 111 deselected` (the quoted-tail heading test and the blank-line test; the raw-block test stays green as designed). Green: `3 passed, 111 deselected`.

## Review round 3 fixes (fix audits and round-3 scoped finder), proven by the builder at `981e39c6`

These were probed the same way as round 2: a detached probe worktree, targeted edits reverted by their inverse, and `git diff --stat` empty after restore.

- **G9 heading boundary (round-3 audits of all four targets, and the round-3 finder).** Guarded element: `_ATX_LINE.match(lines[m])` in the `_boundary` helper of the claimed-block walk. The block stops at, and never blanks, an ATX heading. Neutralization: drop that term, so the walk crosses headings. Red: `2 failed, 115 deselected` (`-k test_g9_`). Green: `2 passed, 115 deselected`.
- **G6 wrapped claim (round-3 audit of scoped-finder-002).** Guarded element: `_FIXED_ABOVE_TOKEN.search(tail)`, the token rather than the whole claim. Neutralization: `FIXED_ABOVE_RE.search(tail)`. Red: `1 failed, 116 deselected` (`test_g6_fixed_above_tail_a_claim_wrapped_onto_the_next_line_is_still_seen`). Green: `1 passed, 116 deselected`.

## Elements in no class

None: G1 to G9 each have their own neutralization and red. Unproven elements: none; FU3 is outside the declared set (see Disclosures).

## #2389 second rework (WO-D2): G10, a removed fixed-above claim voids the body (rule B)

The probe ran in the worktree itself, one targeted edit reverted by its inverse. Command for both halves: `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py -q -p no:cacheprovider --tb=line -k test_g10_`.

- **G10 (rule B).** Guarded element: the `if claim_removed: return []` in `_accepting_items`. Axis: a body whose visible text lost a `fixed-above` claim accepts nothing, whichever path removed the claim, so a claim that needs stack verification is never dropped while its acceptance still counts.
- **Neutralization:** `if claim_removed:` became `if False and claim_removed:`.
- **Raw red:** `6 failed, 3 passed, 111 deselected in 1.72s`. The five `test_g10_claim_removed_voids_the_body_so_every_leftover_reads_missing[...]` cases (single_line, continuation_line, wrapped, inside_comment, subheading) and `test_g10_claim_removed_the_exact_bodies_of_the_order_without_the_section_frame` failed with `assert [] == [{'id': 'F-1', ...}]`: F-1 was counted accepted. The three control tests stayed green.
- **Restore:** `if False and claim_removed:` became `if claim_removed:` (the inverse edit). Restored lines (`leftover_accepting.py:329-330`): `if claim_removed:` / `        return []`.
- **Raw green:** `9 passed, 111 deselected in 1.82s`.

Replaced elements. The block-machinery parts of G6 (the `claimed` list and the cut-tail `_FIXED_ABOVE_TOKEN.search(tail)` blanking of the whole line) and of G9 (the `_boundary` helper and the heading boundary of the claimed-block walk) are deleted from `_visible`. G10 replaces them: the whole body is voided when a claim is removed, so there is no block to bound. The G6 and G9 records above describe code that no longer exists. The G6 no-claim test (`test_g6_fixed_above_tail_a_tail_without_a_claim_keeps_the_acceptance`) is kept.

Rule A proposed, then dropped. WO-D proposed rule A (a closed comment's tail survives: on a line whose start md_hidden reads HIDDEN while `_visible`'s own comment state is open, keep the text after the closer, as in `a <!-- x` / `b --> c` showing ` c`). It was dropped on layer 1's F8 (vet 846): `md_hidden._comment_line_state` marks as UNSURE a line that starts inside a comment and holds a closer with text after it, and WO-D measured `b --> c` in `a <!-- x\nb --> c\n` as UNSURE, not HIDDEN. The leftover check does not overrule layer 1's fail-closed call, so there is no rule A, no G11, and no bite-proof for it. Five existing tests whose expected output kept such a tail now expect the blanked line.
