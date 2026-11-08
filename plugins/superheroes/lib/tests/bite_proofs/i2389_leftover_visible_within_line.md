# Bite-proof record: i2389_leftover_visible_within_line (#2389 V847-1, BR684-2, BR684-3; fix leg of vet 847) `_visible` never keeps text GitHub hides within a line

Detector under proof: `plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py` (unedited between the red and the green of every entry).
Guarded code: `plugins/superheroes/lib/leftover_accepting.py` (`_visible`, the char loop and the fenced-line branch). Base head `e18731af`.
Every neutralization was one targeted edit made with the Edit tool and undone by the inverse Edit before the next element.
No `git checkout`, `restore`, `reset`, `stash` or `sed` was used.
Command prefix for every run (worktree root), `-k` as per entry:
`timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py -q -p no:cacheprovider --tb=line -k test_gN_`
Restore receipts are the restored lines, quoted back by a `grep -n` after each inverse Edit (the fix leg 3 entries below were read back with the Grep tool).

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

## #2389 fix leg 2 (vet 849, WO-E2): G12 to G16

Each probe ran in the worktree itself: one targeted edit with the edit tool, run red, the inverse edit, run green. After the last restore the guard lines read `leftover_accepting.py:262` `void = void or any(out[n] != lines[n] and _FIXED_WORD.search(lines[n]) and _ABOVE_WORD.search(lines[n])`, `:283` `void = void or any(shown[n] and _ATX_LINE.match(lines[n]) and out[n] != lines[n] for n in range(len(lines)))`, `:290` `void = any(shown[n] and (out_kinds[n] != fence_kinds[n]`, `:81` `_TAG_ENTRY = re.compile(r"<(?:[!?]|/(?!>)|[A-Za-z])")`, and the (a) block opens with `if not void:` (`:269`). Command for every half, with `N` the guard number: `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py -q -p no:cacheprovider --tb=line -k test_gN_`. No receipt holds a secret, token or private URL; nothing is redacted.

### G12: the block-role guard

- **Guarded element / axis:** the `void = any(shown[n] and (out_kinds[n] != fence_kinds[n] or bool(_ATX_LINE.match(out[n])) != bool(_ATX_LINE.match(lines[n]))) …)` statement under `if not void:` in `_visible_claim`. Axis: a cut that changes the fence kind or the ATX-heading status of a line `md_hidden` reads VISIBLE accepts nothing, because the section reader re-parses the cut text.
- **Neutralization:** `void = any(shown[n] and (…` became `void = any(False and shown[n] and (…`.
- **Raw red:** `3 failed, 1 passed, 174 deselected in 0.88s`. Failed: `test_g12_structure_a_fence_opener_swallowed_by_a_tail_comment_voids_the_body` (`assert ['Note `'] == []`), `test_g12_structure_a_cut_that_manufactures_a_fence_opener_voids_the_body` (`assert ['None. ```md...acks off ```'] == []`) and `test_g12_structure_heading_half_a_cut_that_makes_a_line_an_atx_heading_voids_the_body` (`assert False is True`). Both halves of the guard (fence kind, heading status) bite: the first two are the fence half, the third is the heading half.
- **Restore:** `void = any(False and shown[n] and (…` became `void = any(shown[n] and (…` (the inverse edit).
- **Raw green:** `4 passed, 174 deselected in 0.44s`.

### G13: the per-line claim guard (b), kept as at `3b85582c`

- **Guarded element / axis:** the statement `void = void or any(out[n] != lines[n] and _FIXED_WORD.search(lines[n]) and _ABOVE_WORD.search(lines[n]) and sorted(FIXED_ABOVE_RE.findall(out[n])) != sorted(FIXED_ABOVE_RE.findall(lines[n])) …)`, restored to exactly the statement at `3b85582c` (lines 249-251 there). Axis: a line the cuts changed whose whole claims differ before and after the cut (a claim manufactured from fragments) voids the body. Guard (b) of rule 3; G16 supersedes only WO-E's bare-word trigger, not this guard.
- **Neutralization:** `any(out[n] != lines[n] and …` became `any(False and out[n] != lines[n] and …`.
- **Raw red:** `1 failed, 2 passed, 175 deselected in 0.39s`. Failed: `test_g13_claim_join_a_claim_manufactured_by_a_comment_cut_alone_voids_the_body` (`assert False is True`).
- **Restore:** `any(False and out[n] != lines[n] and …` became `any(out[n] != lines[n] and …`.
- **Raw green:** `3 passed, 175 deselected in 0.94s`.
- **Why a test was added.** `test_g13_claim_join_a_claim_joined_from_fragments_cannot_balance_a_removed_one` stays green with (b) neutralized: its removed `#98` claim sits on the same changed line, so the new removal guard (a) voids it too. The added test has no removed claim (`fixed-<!-- note -->above #99 abcdef0` alone), so only (b) voids it.

### G14: the one entry condition

- **Guarded element / axis:** `_TAG_ENTRY = re.compile(r"<(?:[!?]|/(?!>)|[A-Za-z])")`, the `<` that GitHub's tokenizer leaves data state on (the entries out of `_DATA` in `md_hidden._tokenize`). Axis: text after such a `<` is hidden whatever the opener (bogus comment, tag, end tag), raw, escaped, code-spanned or on a fenced line.
- **Neutralization:** `r"<(?:…` became `r"<(?!)(?:…`, so the pattern never matches (the plain `<!--` branch is separate and unaffected).
- **Raw red:** `35 failed, 2 passed, 141 deselected in 0.55s`. The tool truncated the middle of the failure listing (8588 characters), so the failure list is incomplete here; the first line of each failure read `assert [] == [{'id': 'F-1', 'title': 'The retry loop never backs off'}]` and the last failing test was `test_g14_tag_entry_the_entry_itself_sets_no_comment_state_but_the_cut_tail_is_read`. The two that stayed green are the two controls (`a < b`, `</>`).
- **Restore:** `r"<(?!)(?:…` became `r"<(?:…`.
- **Raw green:** `37 passed, 141 deselected in 0.51s`.

### G15: the cut-heading guard

- **Guarded element / axis:** `void = void or any(shown[n] and _ATX_LINE.match(lines[n]) and out[n] != lines[n] …)`. Axis: a cut that changes a visible ATX heading in any way voids the body, because the section reader finds the acceptance section by its heading.
- **Neutralization:** `any(shown[n] and …` became `any(False and shown[n] and …`.
- **Raw red:** `2 failed, 1 passed, 175 deselected in 0.41s`. Failed: `test_g15_cut_heading_a_cut_in_a_later_heading_voids_the_body` and `test_g15_cut_heading_a_cut_in_the_accepting_heading_voids_the_body_and_reports_f1_missing` (`assert False is True` each). The control (a heading with no cut) stayed green.
- **Restore:** `any(False and shown[n] and …` became `any(shown[n] and …`.
- **Raw green:** `3 passed, 175 deselected in 0.39s`.

### G16: the claim removal guard (a)

- **Guarded element / axis:** the `if not void:` block that runs `FIXED_ABOVE_RE.finditer("".join(lines))` and voids when a match touches a changed line, unless it lies on one line whose sorted whole claims are unchanged. Axis: a `fixed-above` claim the cuts touch (a wrapped one included) voids the body, so a claim joined elsewhere cannot balance one a cut removed. (a) supersedes WO-E's bare-word trigger (a changed line holding the word "fixed" or "above" voided the body unless its claims were whole and unchanged). That trigger over-refused: the real PR #2348 body quotes the placeholder `` `fixed-above #<layer PR> <commit>` `` in a code span, rule 1 cuts it at `<layer`, and the line changed, so a placeholder that is no claim voided the body. (a) keys on a real `FIXED_ABOVE_RE` match, which a placeholder is not.
- **Neutralization:** `if not void:` became `if False and not void:` on the (a) block.
- **Raw red:** `1 failed, 4 passed, 173 deselected in 0.40s`. Failed: `test_g16_claim_fragment_a_wrapped_claim_cut_on_its_first_line_voids_though_a_joined_wrapped_one_balances_the_counts` (`assert False is True`).
- **Restore:** `if False and not void:` became `if not void:`.
- **Raw green:** `5 passed, 173 deselected in 0.48s`.
- **Why a test was added.** The BR684-E-2 counterexample test (`test_g16_claim_fragment_the_counts_balance_but_the_changed_line_voids_the_body`) stays green with (a) neutralized, because its comment-joined `#99` claim sits on one changed line, which guard (b) voids by itself. The added test joins `#99` across two lines (`fixed-<!-- x -->above #99` / `abcdef0`), so no changed line holds a whole claim on its own, the counts balance, and only (a) voids it. The control `test_g16_claim_fragment_a_quoted_placeholder_cut_by_rule_1_keeps_the_acceptances` stayed green in every run.

## #2389 fix leg 3 (vet 852, WO-F): G17a, G17b, G18, and G2 re-run for FU8

Base head `fbc879bd`. Vet receipt: https://github.com/zwrose/superheroes/pull/2391#issuecomment-6715314903. Each probe ran in the worktree itself: one targeted edit with the edit tool, run red, the exact inverse edit, run green. No `git checkout`, `restore`, `reset`, `stash` or `sed`. Command for every half, with `SEL` the selector: `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py -q -p no:cacheprovider --tb=line -k SEL`. Captures drop uv's one `UV_NATIVE_TLS` warning line; nothing else is dropped or redacted. After the last restore the guard lines read `leftover_accepting.py:235` `quoted = _TAG_ENTRY.search(line, i + run, end - run) if end is not None else None`, `:278` `void = void or sorted(FIXED_ABOVE_RE.findall(text)) != sorted(FIXED_ABOVE_RE.findall(body))`, `:312` `void = void or any(shown[n] and out[n] != lines[n]` and `:321` `void = any(shown[n] and src_fenced[n] != out_fenced[n] for n in range(len(lines)))`.

Guarded-element set (declared by the order): G17a (i), the `fence_line_shape` comparison; G17b (ii), the `fenced_lines` comparison; G18, the whole-text claim comparison; G2, re-run for the FU8 test. No others. `pr_sheet.fence_line_shape` and `pr_sheet.fenced_lines` are the consumer's reading, not detectors; they are covered by `test_g17_fence_shape_fence_line_shape_and_fenced_lines_read_the_walk` and by the `_outside_comments` agreement test.

### G17a: a visible changed line with a different `fence_line_shape` voids the body (1c-i)

- **Guarded element / axis:** the `void = void or any(shown[n] and out[n] != lines[n] and pr_sheet.fence_line_shape(src_bare[n]) != pr_sheet.fence_line_shape(out_bare[n]) …)` statement in `_visible_claim` (`leftover_accepting.py:312`). Axis: a cut that gives a visible line another fence opener/run shape under the section reader's own reading voids the body.
- **Neutralization:** `void = void or any(shown[n] and out[n] != lines[n]` became `void = void or any(False and shown[n] and out[n] != lines[n]`.
- **Raw red** (`-k test_g17_`):

```
....................F.....                                               [100%]
E   assert False is True
/home/user/sh-2389/plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py:701: assert False is True
FAILED ...::test_g17_fence_shape_only_the_shape_a_manufactured_opener_inside_a_list_fence_voids_the_body
1 failed, 25 passed, 181 deselected in 0.97s
```

- **Restore:** the inverse edit, `any(False and shown[n] and out[n] != lines[n]` back to `any(shown[n] and out[n] != lines[n]`. **Restore receipt:** a Grep-tool read of the line printed `312:        void = void or any(shown[n] and out[n] != lines[n]`.
- **Raw green:**

```
..........................                                               [100%]
26 passed, 181 deselected in 0.61s
```

- **What it shows.** Only the (i)-only test bites: it cuts `  - ```x <b> `y`` (no fence: a backtick in the info string) to the opener `  - ```x ` while the walk is already inside the list fence, so no fenced flag changes. The nested, column-0 and ordered forms stay green with (i) off: (ii) also voids them, because the manufactured opener line itself is fenced in the cut text and not in the source. This run was made before one added regression test (`..._br852_1_f1_reads_missing_whether_or_not_the_fence_guard_fires`, which passes either way) joined the file, so the green count is 26 here and 27 in the G17b green.

### G17b: a visible line whose `fenced_lines` flag differs between the source and the cut voids the body (1c-ii)

- **Guarded element / axis:** `void = any(shown[n] and src_fenced[n] != out_fenced[n] for n in range(len(lines)))` (`leftover_accepting.py:321`). Axis: a cut that moves a fence in the walk `accepting_listed` reads, so that a visible line is fenced in one text and not in the other, voids the body.
- **Neutralization:** `void = any(shown[n] and src_fenced[n] != out_fenced[n] …` became `void = any(False and shown[n] and src_fenced[n] != out_fenced[n] …`.
- **Raw red** (`-k test_g17_`, run on the final test file; an earlier red of the same neutralization, run before the added regression test, failed the same three tests and is superseded):

```
..................FF....F..                                              [100%]
E   assert False is True
/home/user/sh-2389/plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py:701: assert False is True      (x3)
FAILED ...::test_g17_fence_shape_closer_a_cut_that_turns_a_content_line_into_the_closer_voids_the_body[backtick]
FAILED ...::test_g17_fence_shape_closer_a_cut_that_turns_a_content_line_into_the_closer_voids_the_body[tilde]
FAILED ...::test_g17_fence_shape_br852_1_a_comment_that_ends_the_item_before_a_fence_voids_the_body
3 failed, 24 passed, 181 deselected in 0.52s
```

- **Restore:** the inverse edit, `any(False and shown[n] and src_fenced[n] …` back to `any(shown[n] and src_fenced[n] …`. **Restore receipt:** a Grep-tool read of the line printed `321:            void = any(shown[n] and src_fenced[n] != out_fenced[n] for n in range(len(lines)))`.
- **Raw green:**

```
...........................                                              [100%]
27 passed, 181 deselected in 0.49s
```

- **What it shows.** The two closer forms (`  ``` <b>` becomes the closer `  ``` `, and the tilde twin) are read alike by `md_fence` and by `fence_line_shape` (both are openers before and after), so only the walk's flags differ: this is the case (i) cannot see. The BR852-1 body is voided by (ii) alone (its heading line is fenced in the source and a heading in the cut text).
- **BR852-1 already read F-1 missing without the guard (reported, test kept).** With (ii) neutralized, the scoped command with `-k br852` gave `1 failed, 1 passed`: `test_g17_fence_shape_br852_1_f1_reads_missing_whether_or_not_the_fence_guard_fires` passed (F-1 reads missing with no void) and `test_g17_fence_shape_br852_1_a_comment_that_ends_the_item_before_a_fence_voids_the_body` failed at `assert la._visible_claim(text)[1] is True` (`assert False is True`). The cut text's blank line (the cut comment) leaves the list item open, so the walk ends the fence at the second accepting heading and that heading ends the section. The guard turns a miss by accident into a void by rule; both tests stay.

### G18: the whole-text claim comparison (V852-2)

- **Guarded element / axis:** `void = void or sorted(FIXED_ABOVE_RE.findall(text)) != sorted(FIXED_ABOVE_RE.findall(body))` (`leftover_accepting.py:278`). Axis: a claim a cut manufactured across lines (or removed or changed) anywhere in the text voids the body, even when no changed line holds a claim on its own and the counts balance.
- **Neutralization:** `void = void or sorted(…` became `void = void or False and sorted(…`.
- **Raw red** (`-k test_g18_`):

```
F..                                                                      [100%]
E   assert False is True
/home/user/sh-2389/plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py:814: assert False is True
FAILED ...::test_g18_whole_text_claims_a_claim_manufactured_across_lines_by_a_cut_voids_the_body
1 failed, 2 passed, 205 deselected in 0.45s
```

- **Restore:** the inverse edit, `void or False and sorted(…` back to `void or sorted(…`. **Restore receipt:** a Grep-tool read of the line printed `278:    void = void or sorted(FIXED_ABOVE_RE.findall(text)) != sorted(FIXED_ABOVE_RE.findall(body))`.
- **Raw green:**

```
...                                                                      [100%]
3 passed, 205 deselected in 0.46s
```

The two controls (an inline comment on a claim line, and the quoted placeholder) stayed green in the red run.

### G2, re-run for FU8 (`test_g2_code_span_opener_text_inside_the_span_after_the_opener_never_counts`)

- **Guarded element / axis:** `quoted = _TAG_ENTRY.search(line, i + run, end - run) if end is not None else None` (`leftover_accepting.py:235`). Axis (as in G2 above): a code span whose content holds an entry `<` is kept only up to that `<` and the rest of the line is cut. FU8 puts the `<div>` on its own line so that the `Quoting` acceptance line is a visible line that reaches this branch.
- **Neutralization:** the `quoted = …` line became `quoted = None`.
- **Raw red** (`-k test_g2_`; the nine parametrized cut cases fail as in G2 above, and the FU8 test now fails on the axis):

```
...FFFFFFFFF........F                                                    [100%]
E   assert 'F-1' not in "## What we'...off -->`\n\n"
      'F-1' is contained here:
        ## What we're accepting
        Quoting `<!-- F-1 The retry loop never backs off -->`
/home/user/sh-2389/plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py:551: assert 'F-1' not in "## What we'...off -->`\n\n"
FAILED ...::test_g2_code_span_opener_text_inside_the_span_after_the_opener_never_counts
10 failed, 11 passed, 187 deselected in 0.50s
```

- **Restore:** the inverse edit, `quoted = None` back to the search expression. **Restore receipt:** a Grep-tool read of `quoted = ` printed `235:                quoted = _TAG_ENTRY.search(line, i + run, end - run) if end is not None else None`.
- **Raw green:**

```
.....................                                                    [100%]
21 passed, 187 deselected in 0.49s
```

- **What it shows.** md_hidden reads the `Quoting` line VISIBLE after a `<div>` line of its own, so the line reaches the code-span cut, and the FU8 test now fails when that cut is off.
### Elements in no class

None. Unproven elements: none.

### Whole scoped run after the last restore

The eight-file scoped command of the order (`-q -n auto`): `1369 passed in 28.24s`.

## #2389 vet 853 (WO-H): the segment-first redesign. Entries G19, G20a, G20b, G21; retired entries

Vet 853 receipt: https://github.com/zwrose/superheroes/pull/2391#issuecomment-6717053345. Guarded code: `plugins/superheroes/lib/leftover_accepting.py`
(`_item_cut`, `_cut_items`) over the item spans of `pr_sheet.accepting_item_spans`. Base head `ab0ca80f`. Each neutralization was one targeted
Edit, undone by the inverse Edit before the next; no `git checkout`, `restore`, `reset`, `stash` or `sed`. Captures drop uv's one
`UV_NATIVE_TLS` warning line; nothing was redacted; each is far under the 32 KiB ceiling. Command prefix (worktree root), `-k` per entry:
`timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py -q -p no:cacheprovider --tb=line -k test_gNN_`
The restore receipts are Grep-tool reads of the restored lines.

### Retired entries (the guard's code and axis comments are removed; its tests stay as regressions of the outcome)

- G12, the block-role guard: retired, because the section is read once from the source structure, so no cut can change a line's fence kind or heading role.
- G13, the per-line claim guard (b): retired, because the claim guards now compare each cut item with the source lines of its own span.
- G15, the cut-heading guard: retired, because a heading is read from the source before any cut, so a cut cannot change it.
- G16, the per-line half (the removal guard (a) over changed lines): retired and replaced by the item-level guards (a) and (c) of `_cut_items` (proven as G21).
- G17a, the fence-shape guard (1c-i): retired, because no cut re-parses the text, so no opener is manufactured or lost.
- G17b, the fenced-state guard (1c-ii): retired with `pr_sheet.fenced_lines`, for the same reason.

### G19: a cut runs to the item's end

- **Guarded element / axis:** `_item_cut`, the `if cut:` / `break` after `_scan_line` (`leftover_accepting.py:206-207`). Axis: a cut inside a line cuts the rest of the item, so a later line of the item cannot join the kept text across the hidden part (V853-1).
- **Neutralization:** the `break` after `if cut:` became `continue` (the scan carries on at the next line after a cut).
- **Raw red** (`-k test_g19_`):

```
FFFFFF....                                                               [100%]
E   AssertionError: assert ['F-1 The ret...er backs off'] == ['F-1 The retry loop']
      At index 0 diff: 'F-1 The retry loop never backs off' != 'F-1 The retry loop'
E   AssertionError: assert ['F-1 The ret...er backs off'] == ['F-1 The retry loop `']
      At index 0 diff: 'F-1 The retry loop ` never backs off' != 'F-1 The retry loop `'
6 failed, 4 passed, 220 deselected in 2.03s
```

(all six V853-1 forms fail with the same assertion; the four controls stay green)
- **Restore:** the inverse Edit (`continue` back to `break`). **Restore receipt:** a Grep read of `parts.append(kept.strip())` printed `205:            parts.append(kept.strip())` / `206:            if cut:` / `207:                break`.
- **Raw green:**

```
..........                                                               [100%]
10 passed, 220 deselected in 1.58s
```

### G20a: a hidden or dropped line inside the item is a stop point

- **Guarded element / axis:** `_item_cut`, `if n >= len(lines) or n >= len(shown) or not shown[n] or kind == "dropped":` / `break` (`leftover_accepting.py:191-192`). Axis: a line md_hidden does not read VISIBLE, or one the reader drops, stops the item, so the lines after it are not joined to the lines before it (BR853-1, BR853-2).
- **Neutralization:** the `break` under that condition became `continue`.
- **Raw red** (`-k test_g20_stop_`):

```
FF                                                                       [100%]
E   AssertionError: assert ['F-1 The ret...er backs off'] == ['F-1 The retry loop']
      At index 0 diff: 'F-1 The retry loop never backs off' != 'F-1 The retry loop'
2 failed, 228 deselected in 1.11s
```

- **Restore:** the inverse Edit. **Restore receipt:** a Grep read of `kind == "dropped":` printed `191:        if n >= len(lines) or n >= len(shown) or not shown[n] or kind == "dropped":` / `192:            break`.
- **Raw green:**

```
..                                                                       [100%]
2 passed, 228 deselected in 0.47s
```

### G20b: fenced lines are literal

- **Guarded element / axis:** `_item_cut`, `if kind == "fenced":` (`leftover_accepting.py:197`). Axis: a fenced line is kept literally and no comment is dropped on it (a code block shows `<!-- XYZ -->`), so the fence's content cannot be skipped to join the text around it (BR853-3).
- **Neutralization:** `if kind == "fenced":` became `if kind == "fenced" and False:` (a fenced line goes through the text-line scan, which drops a closed comment and goes on).
- **Raw red** (`-k test_g20_fenced_literal_`):

```
F                                                                        [100%]
E   AssertionError: assert ['F-1 The ret...er backs off'] == ['F-1 The retry loop ~~~']
      At index 0 diff: 'F-1 The retry loop ~~~ ~~~ never backs off' != 'F-1 The retry loop ~~~'
1 failed, 229 deselected in 0.45s
```

- **Restore:** the inverse Edit. **Restore receipt:** a Grep read of `if kind == "fenced"` printed `197:        if kind == "fenced":`.
- **Raw green:**

```
.                                                                        [100%]
1 passed, 229 deselected in 0.57s
```

### G21: the claim guards read the source lines of the item's span

**Retired in vet 856 (below): the summed guards (a) the whole-claim count and (c) the sorted whole-text claims, with the whole-body void, are replaced by the per-item comparison (G23), because a sum across items lets a claim lost in one item cancel against the same claim made in another.** The source-span read this entry proves stays, and now feeds the per-item comparison.

- **Guarded element / axis:** `_cut_items`, `blanked_lines, source_lines = md_fence.split_lines(blanked), md_fence.split_lines(body)` (`leftover_accepting.py:337`). Axis: the guards compare each cut item with the lines of its span as they stand before blanking, hidden and dropped lines included, so a claim on a hidden line of the item is seen as removed (BR853-4).
- **Neutralization:** `md_fence.split_lines(body)` became `md_fence.split_lines(blanked)` (the span's source is read from the blanked body).
- **Raw red** (`-k test_g21_`):

```
F                                                                        [100%]
E   assert False is True
/home/user/sh-2389/plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py:1044: assert False is True
1 failed, 229 deselected in 0.51s
```

(the guard no longer sees the claim, so the item reads accepted with the claim lost)
- **Restore:** the inverse Edit. **Restore receipt:** a Grep read of `blanked_lines, source_lines` printed `337:    blanked_lines, source_lines = md_fence.split_lines(blanked), md_fence.split_lines(body)`.
- **Raw green:**

```
.                                                                        [100%]
1 passed, 229 deselected in 0.44s
```

**WO-H3 re-run (#2389; the token count dropped from guard (a), so (a) and (c) compare whole claims only; the line is now `leftover_accepting.py:338`).** Same neutralization (`md_fence.split_lines(body)` became `md_fence.split_lines(blanked)`). The `-k test_g21_` run now selects two tests: the claim-on-a-hidden-line test (the one that bites) and `test_g21_source_span_claims_a_prose_mention_after_a_cut_does_not_void_the_body` (the over-refusal guard, which passes under the neutralization because its body holds no claim).

- **Raw red** (`-k test_g21_`):

```
.F                                                                       [100%]
E   assert False is True
/home/user/sh-2389/plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py:1069: assert False is True
FAILED plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py::test_g21_source_span_claims_a_claim_on_a_hidden_line_of_the_item_voids_the_body
1 failed, 1 passed, 229 deselected in 1.06s
```

- **Restore:** the inverse Edit. **Restore receipt:** a Grep read of `blanked_lines, source_lines` printed `338:    blanked_lines, source_lines = md_fence.split_lines(blanked), md_fence.split_lines(body)`.
- **Raw green:**

```
..                                                                       [100%]
2 passed, 229 deselected in 1.52s
```

### Elements in no class (WO-H)

None. Unproven elements: none. The earlier entries G1 to G4, G10, G14 and G18 name line numbers of the code before WO-H and were not re-run here (the order named only the four entries above).

## #2389 vet 856 (WO-J): an item where a cut fires counts as nothing (G22), claims are compared per item (G23)

Guarded code: `plugins/superheroes/lib/leftover_accepting.py` (`_item_cut`, `_cut_items`). Base head `f570ccd9`. Each neutralization was one targeted Edit, undone by the
exact inverse Edit before the next; no `git checkout`, `restore`, `reset`, `stash` or `sed`. Captures drop uv's one `UV_NATIVE_TLS` warning line; nothing was
redacted; each is far under the 32 KiB ceiling. Command (worktree root), `-k` per entry:
`timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py -q -p no:cacheprovider --tb=line -k test_gNN_`
The restore receipts are Grep-tool reads of the restored lines.

### G22: a cut anywhere in an item makes the item count as nothing

- **Guarded element / axis:** `_item_cut`, the `if cut:` / `return ""` after `_scan_line` (`leftover_accepting.py:210-211`). Axis: an item where an entry `<` (plain, escaped or code-spanned) or an unclosed `<!--` fires reads nothing, never the words before the cut, so `f-1<span>-other</span>` (GitHub shows `f-1-other`) does not read as `f-1`, and a title word cut short does not read whole (V856-2).
- **Neutralization:** `if cut:` / `return ""` / `parts.append(kept.strip())` became `parts.append(kept.strip())` / `if cut:` / `break` (the pre-change behaviour: the cut item keeps its prefix).
- **Raw red** (`-k test_g22_`):

```
FFFFF                                                                    [100%]
E   assert not True
     +  where True = any(['f-1'])
/home/user/sh-2389/plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py:1161: assert not True
E   assert not True
     +  where True = any(['f-1'])
/home/user/sh-2389/plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py:1161: assert not True
E   assert not True
     +  where True = any(['f-1`'])
/home/user/sh-2389/plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py:1161: assert not True
E   assert not True
     +  where True = any(['f-1'])
/home/user/sh-2389/plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py:1161: assert not True
E   assert not True
     +  where True = any(['F-1 The retry loop never back'])
/home/user/sh-2389/plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py:1169: assert not True
5 failed, 247 deselected in 2.33s
```

(the `cuts(...)` arguments, which print the whole PR body, are elided from these lines; the four id-glue forms and the title-glue form all fail)
- **Restore:** the exact inverse Edit. **Restore receipt:** a Grep read of `if cut:` printed `210:            if cut:` / `211:                return ""`.
- **Raw green:**

```
.....                                                                    [100%]
5 passed, 247 deselected in 1.17s
```

### G22b: an entry `<` on a fenced line makes the item count as nothing

- **Guarded element / axis:** `_item_cut`, the `if _TAG_ENTRY.search(line, start):` / `return ""` in the `fenced` branch (`leftover_accepting.py:204-205`). Axis: a fenced line holding an entry `<` makes the whole item read nothing (a distinct branch from G22; no `test_g22_` test reaches it, the G4 tests do).
- **Neutralization:** the two lines became `opener = _TAG_ENTRY.search(line, start)` / `parts.append(line[start:opener.start() if opener else len(line)].strip())` / `if opener:` / `break` (the pre-change behaviour: the fenced line keeps the text before its `<`).
- **Raw red** (`-k test_g4_fenced_line_opener_cuts`):

```
FFFFFFFF                                                                 [100%]
E   AssertionError: assert '``` keep' == ''
E   AssertionError: assert '``` keep' == ''
E   AssertionError: assert '~~~ keep' == ''
E   AssertionError: assert '``` keep' == ''
E   AssertionError: assert '```' == ''
E   AssertionError: assert '``` keep' == ''
E   AssertionError: assert '``` keep' == ''
E   AssertionError: assert '~~~ plain' == ''
8 failed, 244 deselected in 0.61s
```

(the per-failure `+ ...` and path lines are elided; all eight fenced-opener rows fail)
- **Restore:** the exact inverse Edit. **Restore receipt:** a Grep read of `_TAG_ENTRY.search(line, start)` printed `204:            if _TAG_ENTRY.search(line, start):` / `205:                return ""` / `206:            parts.append(line[start:].strip())`.
- **Raw green** (`-k test_g4_fenced_line_opener_cuts`):

```
........                                                                 [100%]
8 passed, 244 deselected in 0.46s
```

### G23: claims are compared per item

- **Guarded element / axis:** `_cut_items`, `return [cut if sorted(FIXED_ABOVE_RE.findall(cut)) == sorted(FIXED_ABOVE_RE.findall(source)) else "" for cut, source in zip(cuts, sources)], False` (`leftover_accepting.py:350-351`). Axis: an item whose whole claims differ from its own source span's reads nothing, and claims are never summed across items, so equal claims in two items cannot cancel (V856-1).
- **Neutralization:** `cut if sorted(...) == sorted(...) else ""` became `cut if True or sorted(...) == sorted(...) else ""` (the comparison never fires).
- **Raw red** (`-k test_g23_`):

```
..FF                                                                     [100%]
E   assert not True
     +  where True = any(<generator object test_g23_per_item_claims_equal_claims_cancel_with_no_cut_in_the_item_refuse.<locals>.<genexpr> at 0x7fd6a3e50e10>)
/home/user/sh-2389/plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py:1202: assert not True
E   assert not True
     +  where True = any(<generator object test_g23_per_item_claims_equal_claims_cancel_with_no_cut_in_the_item_refuse.<locals>.<genexpr> at 0x7fd6a3e53100>)
/home/user/sh-2389/plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py:1202: assert not True
FAILED plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py::test_g23_per_item_claims_equal_claims_cancel_with_no_cut_in_the_item_refuse[claim_item_first]
FAILED plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py::test_g23_per_item_claims_equal_claims_cancel_with_no_cut_in_the_item_refuse[hidden_item_first]
2 failed, 2 passed, 248 deselected in 1.02s
```

(Session 9's two bodies, `test_g23_per_item_claims_session_9_claim_cancel_bodies_refuse`, stay green here: their `<b>` item is also blanked by G22, so they are not the bite for G23. The two bodies where the claim is lost to a hidden line, with no entry `<` in the item, are.)
- **Restore:** the exact inverse Edit. **Restore receipt:** a Grep read of `return [cut if` printed `350:    return [cut if sorted(FIXED_ABOVE_RE.findall(cut)) == sorted(FIXED_ABOVE_RE.findall(source)) else ""`.
- **Raw green:**

```
....                                                                     [100%]
4 passed, 248 deselected in 0.48s
```

### Session 9's break-it test fails without the change

`test_review_684_claim_relocation.py` with G22 and G23 neutralized together (both Edits above applied, then both inverse Edits):

```
F                                                                        [100%]
E   Failed: DID NOT RAISE _Refusal
/home/user/sh-2389/plugins/superheroes/lib/tests/test_review_684_claim_relocation.py:23: Failed: DID NOT RAISE _Refusal
1 failed in 0.26s
```

### Elements in no class (WO-J)

None. Unproven elements: none. The G22 neutralization covers the `text`-line cut (`_scan_line`'s cuts: plain, escaped, code-spanned entry `<`, unclosed `<!--`, all reached through `if cut:`); the fenced branch is G22b.

## #2389 vet 859 (WO-K): one line list (G24), a blanked line never detaches a claim (G25), G14 isolation

Guarded code: `plugins/superheroes/lib/leftover_accepting.py` (`_cut_items`, `_TAG_ENTRY`). Base head `94ba12e7`. Each neutralization was one targeted Edit, undone by the
exact inverse Edit before the next; no `git checkout`, `restore`, `reset`, `stash` or `sed`. Captures drop uv's one `UV_NATIVE_TLS` warning line and the repeated
per-failure `+`/`-` diff lines of `--tb=line`; nothing was redacted; each is far under the 32 KiB ceiling. Command (worktree root), `-k` per entry:
`timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py -q -p no:cacheprovider --tb=line -k <selector>`
The restore receipts are Grep-tool reads of the restored lines.

### G24: one line list

- **Guarded element / axis:** `_cut_items`, the `spans = pr_sheet.accepting_item_spans_of([...])` / `cuts = [_item_cut(blanked, span, shown) ...]` pair (`leftover_accepting.py:385-386`). Axis: the spans, the cuts and the sources all index the one `_blanked_lines` list, so blanked line `n` is source line `n`; a blanked unterminated last line keeps its place (EOF) and a lone `\r` before a blanked `\n` line does not join into `\r\n` (`m5`).
- **Neutralization:** the two lines became `spans = pr_sheet.accepting_item_spans("".join(blanked))` / `cuts = [_item_cut(md_fence.split_lines("".join(blanked)), span, shown) for span in spans]` (the blanked lines joined and split again).
- **Raw red** (`-k test_g24_`; the first run of this neutralization, before the position tests were made to read what `_cut_items` passes to `_item_cut`, left the `m5` position test green, so the tests were changed and the red re-run; this is the re-run):

```
FFFF.FFFFF                                                               [100%]
E   assert 9 == 10  (m5_lone_cr: len(lines) 9, len(source) 10)
E   assert 3 == 4   (e1_unterminated_blanked_last_line: len(lines) 3, len(source) 4)
E   assert 5 == 7   (both: len(lines) 5, len(source) 7)
E   assert (4 - 1) in [2]
FAILED ...::test_g24_one_line_list_github_hides_the_claim_so_the_check_reports_f1_missing[e1_eof_unsure_claim]
FAILED ...::test_g24_one_line_list_github_hides_the_claim_so_the_check_reports_f1_missing[e3_eof_custom_el_claim]
FAILED ...::test_g24_one_line_list_github_hides_the_claim_so_the_check_reports_f1_missing[e4_eof_lazy_unsure_claim]
FAILED ...::test_g24_one_line_list_github_hides_the_claim_so_the_check_reports_f1_missing[e6_eof_realistic_wrapped]
FAILED ...::test_g24_one_line_list_hidden_last_line_claim_is_the_first_over_refusal[e2_eof_hidden_claim]
FAILED ...::test_g24_one_line_list_every_span_index_names_the_same_line_in_the_source_and_the_blanked_list[m5_lone_cr]
FAILED ...::test_g24_one_line_list_every_span_index_names_the_same_line_in_the_source_and_the_blanked_list[e1_unterminated_blanked_last_line]
FAILED ...::test_g24_one_line_list_every_span_index_names_the_same_line_in_the_source_and_the_blanked_list[both]
FAILED ...::test_g24_one_line_list_an_unterminated_blanked_last_line_stays_an_entry_and_its_item_keeps_it
9 failed, 1 passed, 275 deselected in 0.58s
```

(The one pass is the `m5` rendered-row verdict `test_g24_one_line_list_github_hides_the_claim_so_the_check_reports_f1_missing[m5_...]`: under this neutralization the shifted indices happen to fail closed on that body, so the row stays `missing`. The `m5` position test is what bites for the lone-CR shape. The EOF tests and the `m5` position test are among the failures, as the order required.)
- **Restore:** the exact inverse Edit. **Restore receipt:** a Grep read printed `385:    spans = pr_sheet.accepting_item_spans_of([line[:len(line) - len(_terminator(line))] for line in blanked])` / `386:    cuts = [_item_cut(blanked, span, shown) for span in spans]`.
- **Raw green** (`-k test_g24_`):

```
..........                                                               [100%]
10 passed, 275 deselected in 0.49s
```

### G25 (source items, #2389 vet 860, WO-M): an item's claims are compared against the source's own items

Base head `6f0aec06` (layer 1 `e4294ef7`). The neutralization was one targeted Edit, undone by the exact inverse Edit; no `git checkout`, `restore`, `reset`, `stash` or `sed`.
Command (worktree root): `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py -q -p no:cacheprovider --tb=line -k test_g25_`

- **Guarded element / axis:** `_cut_items`, `for i in {owner[n] for n in taken if n in owner}:` (`leftover_accepting.py:368`; axis comment at `:366`), which adds to an item's claim source every line of each source item (`src_spans`) that shares a line with it. Axis: an item's claims are compared against the source's own items, so a blanked line never moves a claim out of the item that names the finding (the j rows: the claim in the head of a former join group, F-1 in a joined item; the n rows: an unsure first line holds the claim, F-1 on the next line).
- **Neutralization:** `for i in {owner[n] for n in taken if n in owner}:` became `for i in set():` (each item is compared against its own span only; no lines are added from source items).
- **Raw red** (`-k test_g25_`; tail of the run, the first lines of the `--tb=line` output were not captured, the `FAILED` list is complete):

```
E   AssertionError: assert 'plain-accepted' == 'missing'
      
      - missing
      + plain-accepted
/home/user/sh-2389/plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py:1424: AssertionError: assert 'plain-accepted' == 'missing'
FAILED ...::test_g25_blanked_line_join_github_hides_the_claim_so_the_check_reports_f1_missing[s1_lazy_unsure_then_claim]
FAILED ...::test_g25_blanked_line_join_github_hides_the_claim_so_the_check_reports_f1_missing[s2_paragraph_unsure_then_claim]
FAILED ...::test_g25_blanked_line_join_github_hides_the_claim_so_the_check_reports_f1_missing[s4_indented_unsure_then_lazy_claim]
FAILED ...::test_g25_blanked_line_join_github_hides_the_claim_so_the_check_reports_f1_missing[s6_unsure_custom_el_then_claim]
FAILED ...::test_g25_blanked_line_join_github_hides_the_claim_so_the_check_reports_f1_missing[s7_realistic_wrapped_lazy]
FAILED ...::test_g25_blanked_line_join_github_hides_the_claim_so_the_check_reports_f1_missing[s8_inline_comment_line_then_lazy_claim]
FAILED ...::test_g25_blanked_line_join_paragraph_after_a_hidden_line_is_the_second_over_refusal[s3_hidden_comment_then_claim]
FAILED ...::test_g25_blanked_line_join_a_transitive_chain_refuses
FAILED ...::test_g25_source_items_github_shows_the_claim_with_f1_so_the_check_reports_f1_missing[j1_list_claim_head_unsure_then_lazy_f1]
FAILED ...::test_g25_source_items_github_shows_the_claim_with_f1_so_the_check_reports_f1_missing[j2_para_claim_head_unsure_then_f1]
FAILED ...::test_g25_source_items_github_shows_the_claim_with_f1_so_the_check_reports_f1_missing[j3_chain_f1_middle_claim_head]
FAILED ...::test_g25_source_items_github_shows_the_claim_with_f1_so_the_check_reports_f1_missing[j4_chain_claim_last_f1_middle]
FAILED ...::test_g25_source_items_github_shows_the_claim_with_f1_so_the_check_reports_f1_missing[n1_unsure_first_line_holds_claim_f1_next]
FAILED ...::test_g25_source_items_github_shows_the_claim_with_f1_so_the_check_reports_f1_missing[n2_unsure_first_line_holds_claim_f1_lazy]
FAILED ...::test_g25_source_items_github_shows_the_claim_with_f1_so_the_check_reports_f1_missing[n3_para_unsure_first_line_claim_then_f1]
FAILED ...::test_g25_source_items_a_hidden_first_line_holding_a_claim_is_the_new_over_refusal[n6_hidden_comment_first_line_claim]
16 failed, 300 deselected in 1.16s
```

  The j1 to j4 and n1 to n3 rows are among the failures, as the order required; the vet-859 `test_g25_blanked_line_join_*` regressions fail too, as the run shows.
- **Restore:** the exact inverse Edit. **Restore receipt:** a Grep read printed `368:        for i in {owner[n] for n in taken if n in owner}:`.
- **Raw green** (`-k test_g25_`):

```
................                                                         [100%]
16 passed, 300 deselected in 1.25s
```

### G24 after this change

`-k test_g24_` was run once after the vet-860 change and stays green; its entry above is unchanged:

```
..........                                                               [100%]
10 passed, 306 deselected in 1.09s
```

### G25 (the vet-859 join): RETIRED in #2389 vet 860 (WO-M)

Retired: the join (the `group, head` loop and its `pr_sheet._ITEM` test) is replaced by the source-items rule above, which compares each item against the source's own items and made the join's head-only comparison unnecessary (it left F-1 in a joined item counted plain, rows j1 to j4). The entry below is kept as history; its `-k test_g25_` tests are now regressions of the source-items rule.

- **Guarded element / axis (retired):** `_cut_items`, the join condition `if k > 0 and first > 0 and not shown[first - 1] and pr_sheet._ITEM.match(opener) is None:` (`leftover_accepting.py:393`). Axis: an item with no list marker right after a line md_hidden does not read VISIBLE joins the item before it, and the head is compared against the claims of the whole group's source.
- **Neutralization:** `if k > 0 and first > 0 and ...` became `if False and k > 0 and first > 0 and ...` (no item joins).
- **Raw red** (`-k test_g25_`):

```
FFFFFFFF                                                                 [100%]
E   AssertionError: assert 'plain-accepted' == 'missing'   (seven times: s1, s2, s4, s6, s7, s8 and s3)
E   assert (3 == 3 and 'F-1 The retr...ver backs off' == ''   (the transitive chain)
FAILED ...::test_g25_blanked_line_join_github_hides_the_claim_so_the_check_reports_f1_missing[s1_lazy_unsure_then_claim]
FAILED ...::test_g25_blanked_line_join_github_hides_the_claim_so_the_check_reports_f1_missing[s2_paragraph_unsure_then_claim]
FAILED ...::test_g25_blanked_line_join_github_hides_the_claim_so_the_check_reports_f1_missing[s4_indented_unsure_then_lazy_claim]
FAILED ...::test_g25_blanked_line_join_github_hides_the_claim_so_the_check_reports_f1_missing[s6_unsure_custom_el_then_claim]
FAILED ...::test_g25_blanked_line_join_github_hides_the_claim_so_the_check_reports_f1_missing[s7_realistic_wrapped_lazy]
FAILED ...::test_g25_blanked_line_join_github_hides_the_claim_so_the_check_reports_f1_missing[s8_inline_comment_line_then_lazy_claim]
FAILED ...::test_g25_blanked_line_join_paragraph_after_a_hidden_line_is_the_second_over_refusal[s3_hidden_comment_then_claim]
FAILED ...::test_g25_blanked_line_join_a_transitive_chain_refuses
8 failed, 277 deselected in 0.54s
```
- **Restore:** the exact inverse Edit. **Restore receipt:** a Grep read printed `393:        if k > 0 and first > 0 and not shown[first - 1] and pr_sheet._ITEM.match(opener) is None:`.
- **Raw green** (`-k test_g25_`):

```
........                                                                 [100%]
8 passed, 277 deselected in 0.53s
```

### G14 isolation (session 13's Minor): the plain-line cases drop the `</div>` line, so a bogus opener is the only cut

- **Guarded element / axis:** `_TAG_ENTRY`'s `/(?!>)` branch (`leftover_accepting.py:94`), through `test_g14_tag_entry_a_bogus_comment_opener_hides_the_rest_of_the_line` (`plain_line` cases: body `lead + quoted + " " + TITLE + "\n"`, no `</div>`). Axis: a `</` + non-`>` bogus end-tag opener (`</ `, `</1`) is itself an entry, with no other cut in the body to refuse it.
- **Neutralization:** `r"<(?:[!?]|/(?!>)|[A-Za-z])"` became `r"<(?:[!?]|/[A-Za-z]|[A-Za-z])"`.
- **Raw red** (`-k test_g14_tag_entry_a_bogus`):

```
..................FF...FF...FF                                           [100%]
E   AssertionError: assert [] == [{'id': 'F-1', ... 'The retry loop never backs off'}]   (six times)
FAILED ...::test_g14_tag_entry_a_bogus_comment_opener_hides_the_rest_of_the_line[plain_line-raw-</ ]
FAILED ...::test_g14_tag_entry_a_bogus_comment_opener_hides_the_rest_of_the_line[plain_line-raw-</1]
FAILED ...::test_g14_tag_entry_a_bogus_comment_opener_hides_the_rest_of_the_line[plain_line-escaped-</ ]
FAILED ...::test_g14_tag_entry_a_bogus_comment_opener_hides_the_rest_of_the_line[plain_line-escaped-</1]
FAILED ...::test_g14_tag_entry_a_bogus_comment_opener_hides_the_rest_of_the_line[plain_line-code_span-</ ]
FAILED ...::test_g14_tag_entry_a_bogus_comment_opener_hides_the_rest_of_the_line[plain_line-code_span-</1]
6 failed, 24 passed, 255 deselected in 2.80s
```
- **Restore:** the exact inverse Edit. **Restore receipt:** a Grep read printed `94:_TAG_ENTRY = re.compile(r"<(?:[!?]|/(?!>)|[A-Za-z])")`.
- **Raw green** (`-k test_g14_tag_entry_a_bogus`):

```
..............................                                           [100%]
30 passed, 255 deselected in 1.63s
```

### Elements in no class (WO-K)

None. The two new over-refusals are asserted by `test_g24_one_line_list_hidden_last_line_claim_is_the_first_over_refusal` (G24's neutralization turns it red) and `test_g25_blanked_line_join_paragraph_after_a_hidden_line_is_the_second_over_refusal` (G25's does). The transitive chain is model-only.

## #2389 vet 861 (WO-N): source-item coverage (G26)

### G26 (source-item coverage): an item with a line no source item holds counts as nothing

Base head `c23913c7`. The neutralization was one targeted Edit, undone by the exact inverse Edit; no `git checkout`, `restore`, `reset`, `stash` or `sed`.
Command (worktree root): `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_leftover_visible_within_line_2389.py -q -p no:cacheprovider --tb=no -rf -k test_g26_`
Guarded-element set (declared by the order): the one coverage check. No others.

- **Guarded element / axis:** `_cut_items`, `if any(n not in owner for n, kind in span if kind in ("text", "fenced")):` (`leftover_accepting.py:375`; axis comment at `:374`). Axis: wherever the source reading and the blanked reading disagree about which item, or which section, holds a line, the item fails closed and counts as nothing; the claim compare is skipped (an HTML comment holding a heading at or above the section's level ends the source's section, so the items below it have no source item).
- **Neutralization:** `if any(n not in owner for n, kind in span if kind in ("text", "fenced")):` became `if False:` (no item is checked for coverage).
- **Raw red** (`-k test_g26_`):

```
FFFFFFFFFFFFFFFFFFF                                                      [100%]
=========================== short test summary info ============================
FAILED ...::test_g26_source_item_coverage_github_shows_the_claim_with_f1_so_the_check_reports_f1_missing[a1_comment_h2_before_para_unsure_between]
FAILED ...::test_g26_source_item_coverage_github_shows_the_claim_with_f1_so_the_check_reports_f1_missing[a2_comment_h2_before_list_unsure_lazy_claim]
FAILED ...::test_g26_source_item_coverage_github_shows_the_claim_with_f1_so_the_check_reports_f1_missing[a3_comment_h2_before_para_claim_first]
FAILED ...::test_g26_source_item_coverage_github_shows_the_claim_with_f1_so_the_check_reports_f1_missing[a4_comment_h1_before_para_unsure_between]
FAILED ...::test_g26_source_item_coverage_github_shows_the_claim_with_f1_so_the_check_reports_f1_missing[a8_list_comment_opener_h2_before_unsure_between]
FAILED ...::test_g26_source_item_coverage_github_shows_the_claim_with_f1_so_the_check_reports_f1_missing[a12_comment_h2_between_items_then_para]
FAILED ...::test_g26_source_item_coverage_github_shows_the_claim_with_f1_so_the_check_reports_f1_missing[c1_a1_crlf]
FAILED ...::test_g26_source_item_coverage_github_shows_the_claim_with_f1_so_the_check_reports_f1_missing[c2_a2_crlf]
FAILED ...::test_g26_source_item_coverage_github_shows_the_claim_with_f1_so_the_check_reports_f1_missing[c3_a1_lone_cr]
FAILED ...::test_g26_source_item_coverage_github_shows_the_claim_with_f1_so_the_check_reports_f1_missing[c4_a1_unterminated_claim_at_body_end]
FAILED ...::test_g26_source_item_coverage_github_shows_the_claim_with_f1_so_the_check_reports_f1_missing[c5_comment_h2_in_earlier_item_indented]
FAILED ...::test_g26_source_item_coverage_github_shows_the_claim_with_f1_so_the_check_reports_f1_missing[c6_comment_h2_before_two_unsure_lines]
FAILED ...::test_g26_source_item_coverage_github_shows_the_claim_with_f1_so_the_check_reports_f1_missing[c7_comment_h2_before_nested_f1_lazy_claim]
FAILED ...::test_g26_source_item_coverage_github_shows_the_claim_with_f1_so_the_check_reports_f1_missing[c8_comment_h2_before_ordered_list]
FAILED ...::test_g26_source_item_coverage_github_shows_the_claim_with_f1_so_the_check_reports_f1_missing[c9_comment_h2_before_claim_unsure_first_line]
FAILED ...::test_g26_source_item_coverage_github_shows_the_claim_with_f1_so_the_check_reports_f1_missing[d3_item_comment_h2_after_claim_then_lazy_f1]
FAILED ...::test_g26_source_item_coverage_an_acceptance_below_a_comment_heading_is_the_new_over_refusal[a6_comment_h2_before_no_unsure_control]
FAILED ...::test_g26_source_item_coverage_an_acceptance_below_a_comment_heading_is_the_new_over_refusal[h1_comment_h2_before_plain_f1]
FAILED ...::test_g26_source_item_coverage_an_acceptance_below_a_comment_heading_is_the_new_over_refusal[h2_comment_h2_before_plain_list_f1]
19 failed, 331 deselected in 2.14s
```

  The 16 fail-open rows (a1 to a4, a8, a12, c1 to c9, d3) are among the failures, as the order required; the three over-refusal rows (a6, h1, h2) fail too.
- **Restore:** the exact inverse Edit. **Restore receipt:** a Grep read printed `375:        if any(n not in owner for n, kind in span if kind in ("text", "fenced")):`.
- **Raw green** (`-k test_g26_`):

```
...................                                                      [100%]
19 passed, 331 deselected in 1.14s
```

### FU11 (G2's isolated `item_cut` call)

`test_g2_code_span_opener_text_inside_the_span_after_the_opener_never_counts` isolated call now reads `"Quoting `<!-- F-1 The retry loop never backs off -->`\n"` (the `\n</div>` line dropped, so a `</div>` entry `<` cannot be the cut). It passes in the scoped run. Probe, with the code-span guard neutralized (`leftover_accepting.py:161`, `quoted = _TAG_ENTRY.search(line, i + run, end - run) if end is not None else None` became `quoted = None`), `_cut_items` of the same input under the accepting heading returned `['Quoting `<!-- F-1 The retry loop never backs off -->`']` (the span's text is read); the inverse Edit restored line 161.

### Elements in no class (WO-N)

None.
