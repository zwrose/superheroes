# Bite-proof record: i2366_md_hidden (#2388, layer 1 of #2366) `md_hidden.scan` and `md_fence.split_lines`

Detector under proof: `plugins/superheroes/lib/tests/test_md_hidden_2366.py` (unedited; the `test_guard_gN_*` tests).
Guarded code: `plugins/superheroes/lib/md_hidden.py` and `plugins/superheroes/lib/md_fence.py` (`split_lines` only).
Head: `801c9f7d`. Every neutralization was a targeted edit made with the Edit tool and undone by the inverse Edit before
the next element. No `git checkout`, `restore`, `reset` or `stash` was used. Worktree `/home/user/wt-2366`.
Command prefix for every run (worktree root), with `-k` as the order named it per entry:
`scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_md_hidden_2366.py -q -k <test name>`
Restore receipts are the restored lines, quoted back with the file-search and file-read tools after each inverse Edit
(those reads are not shell commands and sit outside the 30-command budget).

Guarded-element set (declared by the order): G1 to G12, no others.

Disclosures:
- Every capture below is the runner's output **verbatim except uv's one `UV_NATIVE_TLS` deprecation warning line**, which
  begins every run and is dropped. Nothing was redacted. Each capture is far under 32 KiB, the whole record under 128 KiB.
- The order selects each test with `-k <name>`, where `rubric/bite-proof.md` § Running a proof asks for the exact node id.
  Each `-k` name here matched exactly the tests expected (the summary line's `N failed/passed, M deselected` shows it:
  1 for most, 8 for G3, 2 for G5, 9 for G6, never 0).
- G2, G4 and the G5 pair neutralize a guard that is **an absence or a spread-out pair of sites** (see each entry), so the
  neutralization adds code or drops two sites; none of them is a one-line flip.
- Findings about the detector (not changed, per the order) are collected at the end: G5 (the opener site is masked), G6
  (the `textarea` case is masked), G8 (one of three disjuncts is exercised), G11 (two clauses in series), G4 (the red
  stops at its first assertion).

## G1: raw HTML-block content drives the comment state

- **Guarded element / axis:** `md_hidden.py:650`, `state = _tokenize(state, html_line[i] + "\n")`; the content of an HTML
  block is raw HTML and decides the comment state, so a `<!--` in it (also one written inside backticks in a `<div>`
  block) hides the lines after it.
- **Neutralization:** `md_hidden.py:650` `            state = _tokenize(state, html_line[i] + "\n")` became `            state = state`
  (HTML-block content leaves the state unchanged). The module still imports.
- **Raw red** (`-k test_guard_g1_raw_html_block_content_opens_a_comment`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_guard_g1_raw_html_block_content_opens_a_comment _____________

    def test_guard_g1_raw_html_block_content_opens_a_comment():
>       _reads("x\n\n<pre>\n<!--\n</pre>\n\n## H\n", "## H", H)

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:601: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

body = 'x\n\n<pre>\n<!--\n</pre>\n\n## H\n', heading = '## H'
expected = 'hidden'

    def _reads(body, heading, expected):
        """The heading line reads ``expected``; when HIDDEN its text is also not a VISIBLE entry of ``headings``."""
        got = _state(body, heading)
>       assert got == expected, "heading %r reads %s, expected %s; unsure=%r" % (heading, got, expected, md.scan(body).unsure)
E       AssertionError: heading '## H' reads visible, expected hidden; unsure=()
E       assert 'visible' == 'hidden'
E         
E         - hidden
E         + visible

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:54: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g1_raw_html_block_content_opens_a_comment
1 failed, 418 deselected in 0.35s
```

  The red is on the first assertion (`:601`): the heading reads `visible` where `hidden` is owed (a visible-for-hidden
  fail-open, the axis). The second and third assertions (`:602`, `:603`, the backtick-in-a-`<div>` shapes) were not reached.
- **Restore:** inverse Edit, `state = state` back to `state = _tokenize(state, html_line[i] + "\n")`.
- **Restore receipt:** the restored line reads `            state = _tokenize(state, html_line[i] + "\n")` (`md_hidden.py:650`).
- **Raw green** (same `-k`):

```
.                                                                        [100%]
1 passed, 418 deselected in 0.38s
```

## G2: an escaped `-->` in a paragraph does not close a comment

- **Guarded element / axis:** `md_hidden.py:655-660`, the paragraph branch of the comment pass (`elif i in text_block:`);
  a paragraph's text is escaped output, so a `-->` in it (a backslash-escaped one, a plain one, one in a code span) never
  closes a comment. The guard is an absence: the paragraph branch never calls `_tokenize`.
- **Neutralization:** after `md_hidden.py:656` (`            joined = "\n".join(text_block[i].lines)`) two lines were
  added: `            if hidden and "-->" in joined:` and `                state = _DATA` (a paragraph read in the comment state
  that holds `-->` returns the state to data). The module still imports.
- **Raw red** (`-k test_guard_g2_escaped_closer_in_a_paragraph_does_not_close_a_comment`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_guard_g2_escaped_closer_in_a_paragraph_does_not_close_a_comment _____

    def test_guard_g2_escaped_closer_in_a_paragraph_does_not_close_a_comment():
>       _reads("x\n\n<div>\n<!-- a\n\n\\-->\n\n## H\n", "## H", H)

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:607: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

body = 'x\n\n<div>\n<!-- a\n\n\\-->\n\n## H\n', heading = '## H'
expected = 'hidden'

    def _reads(body, heading, expected):
        """The heading line reads ``expected``; when HIDDEN its text is also not a VISIBLE entry of ``headings``."""
        got = _state(body, heading)
>       assert got == expected, "heading %r reads %s, expected %s; unsure=%r" % (heading, got, expected, md.scan(body).unsure)
E       AssertionError: heading '## H' reads visible, expected hidden; unsure=()
E       assert 'visible' == 'hidden'
E         
E         - hidden
E         + visible

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:54: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g2_escaped_closer_in_a_paragraph_does_not_close_a_comment
1 failed, 418 deselected in 0.28s
```

  The red is on the first assertion (`:607`, the backslash-escaped closer); `:608` and `:609` were not reached.
- **Restore:** inverse Edit, the two added lines removed.
- **Restore receipt:** the restored lines read `            joined = "\n".join(text_block[i].lines)` (`md_hidden.py:656`)
  followed by `            if hidden and _closer_after_lt(joined):` (`:657`).
- **Raw green** (same `-k`):

```
.                                                                        [100%]
1 passed, 418 deselected in 0.24s
```

## G3: lines break only on Markdown endings

- **Guarded element / axis:** `md_fence.py:287-303`, `split_lines` (axis comment at `:287`); only CR, LF and CRLF end a
  line, never U+2028, U+2029, U+0085, VT, FF, FS, GS or RS, so `<!-- a -->` + separator + `~~~` is one HTML line and the
  `~~~` opens no fence.
- **Neutralization:** `md_fence.py:303` `    return out` became `    return text.splitlines(keepends=True)`. The module still imports.
- **Raw red** (`-k test_guard_g3_scan_breaks_lines_only_on_markdown_endings`):

```
FFFFFFFF                                                                 [100%]
=================================== FAILURES ===================================
_______ test_guard_g3_scan_breaks_lines_only_on_markdown_endings[ ] _______

char = ' '

    @pytest.mark.parametrize("char", [" ", " ", "\u0085", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e"])
    def test_guard_g3_scan_breaks_lines_only_on_markdown_endings(char):
        """G3: the false fence. Broken on ``char`` the ``~~~`` would open a fence and swallow the comment opener."""
        body = "x\n\n<!-- a -->" + char + "~~~\n<!--\n\n## H\n"
        rendering = md.scan(body)
>       assert len(rendering.lines) == 6  # x, blank, the one-line html, <!--, blank, ## H
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AssertionError: assert 7 == 6
E        +  where 7 = len(((0, 'visible'), (2, 'visible'), (3, 'visible'), (14, 'visible'), (18, 'visible'), (23, 'visible'), ...))
E        +    where ((0, 'visible'), (2, 'visible'), (3, 'visible'), (14, 'visible'), (18, 'visible'), (23, 'visible'), ...) = <md_hidden.Rendering object at 0x7f1952a81430>.lines

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:263: AssertionError
_______ test_guard_g3_scan_breaks_lines_only_on_markdown_endings[ ] _______

char = ' '

    @pytest.mark.parametrize("char", [" ", " ", "\u0085", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e"])
    def test_guard_g3_scan_breaks_lines_only_on_markdown_endings(char):
        """G3: the false fence. Broken on ``char`` the ``~~~`` would open a fence and swallow the comment opener."""
        body = "x\n\n<!-- a -->" + char + "~~~\n<!--\n\n## H\n"
        rendering = md.scan(body)
>       assert len(rendering.lines) == 6  # x, blank, the one-line html, <!--, blank, ## H
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AssertionError: assert 7 == 6
E        +  where 7 = len(((0, 'visible'), (2, 'visible'), (3, 'visible'), (14, 'visible'), (18, 'visible'), (23, 'visible'), ...))
E        +    where ((0, 'visible'), (2, 'visible'), (3, 'visible'), (14, 'visible'), (18, 'visible'), (23, 'visible'), ...) = <md_hidden.Rendering object at 0x7f1952a7fd70>.lines

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:263: AssertionError
________ test_guard_g3_scan_breaks_lines_only_on_markdown_endings[\x85] ________

char = '\x85'

    @pytest.mark.parametrize("char", [" ", " ", "\u0085", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e"])
    def test_guard_g3_scan_breaks_lines_only_on_markdown_endings(char):
        """G3: the false fence. Broken on ``char`` the ``~~~`` would open a fence and swallow the comment opener."""
        body = "x\n\n<!-- a -->" + char + "~~~\n<!--\n\n## H\n"
        rendering = md.scan(body)
>       assert len(rendering.lines) == 6  # x, blank, the one-line html, <!--, blank, ## H
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AssertionError: assert 7 == 6
E        +  where 7 = len(((0, 'visible'), (2, 'visible'), (3, 'visible'), (14, 'visible'), (18, 'visible'), (23, 'visible'), ...))
E        +    where ((0, 'visible'), (2, 'visible'), (3, 'visible'), (14, 'visible'), (18, 'visible'), (23, 'visible'), ...) = <md_hidden.Rendering object at 0x7f1952a84140>.lines

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:263: AssertionError
________ test_guard_g3_scan_breaks_lines_only_on_markdown_endings[\x0b] ________

char = '\x0b'

    @pytest.mark.parametrize("char", [" ", " ", "\u0085", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e"])
    def test_guard_g3_scan_breaks_lines_only_on_markdown_endings(char):
        """G3: the false fence. Broken on ``char`` the ``~~~`` would open a fence and swallow the comment opener."""
        body = "x\n\n<!-- a -->" + char + "~~~\n<!--\n\n## H\n"
        rendering = md.scan(body)
>       assert len(rendering.lines) == 6  # x, blank, the one-line html, <!--, blank, ## H
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AssertionError: assert 7 == 6
E        +  where 7 = len(((0, 'visible'), (2, 'visible'), (3, 'visible'), (14, 'visible'), (18, 'visible'), (23, 'visible'), ...))
E        +    where ((0, 'visible'), (2, 'visible'), (3, 'visible'), (14, 'visible'), (18, 'visible'), (23, 'visible'), ...) = <md_hidden.Rendering object at 0x7f1952a85430>.lines

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:263: AssertionError
________ test_guard_g3_scan_breaks_lines_only_on_markdown_endings[\x0c] ________

char = '\x0c'

    @pytest.mark.parametrize("char", [" ", " ", "\u0085", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e"])
    def test_guard_g3_scan_breaks_lines_only_on_markdown_endings(char):
        """G3: the false fence. Broken on ``char`` the ``~~~`` would open a fence and swallow the comment opener."""
        body = "x\n\n<!-- a -->" + char + "~~~\n<!--\n\n## H\n"
        rendering = md.scan(body)
>       assert len(rendering.lines) == 6  # x, blank, the one-line html, <!--, blank, ## H
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AssertionError: assert 7 == 6
E        +  where 7 = len(((0, 'visible'), (2, 'visible'), (3, 'visible'), (14, 'visible'), (18, 'visible'), (23, 'visible'), ...))
E        +    where ((0, 'visible'), (2, 'visible'), (3, 'visible'), (14, 'visible'), (18, 'visible'), (23, 'visible'), ...) = <md_hidden.Rendering object at 0x7f1952a84c20>.lines

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:263: AssertionError
________ test_guard_g3_scan_breaks_lines_only_on_markdown_endings[\x1c] ________

char = '\x1c'

    @pytest.mark.parametrize("char", [" ", " ", "\u0085", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e"])
    def test_guard_g3_scan_breaks_lines_only_on_markdown_endings(char):
        """G3: the false fence. Broken on ``char`` the ``~~~`` would open a fence and swallow the comment opener."""
        body = "x\n\n<!-- a -->" + char + "~~~\n<!--\n\n## H\n"
        rendering = md.scan(body)
>       assert len(rendering.lines) == 6  # x, blank, the one-line html, <!--, blank, ## H
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AssertionError: assert 7 == 6
E        +  where 7 = len(((0, 'visible'), (2, 'visible'), (3, 'visible'), (14, 'visible'), (18, 'visible'), (23, 'visible'), ...))
E        +    where ((0, 'visible'), (2, 'visible'), (3, 'visible'), (14, 'visible'), (18, 'visible'), (23, 'visible'), ...) = <md_hidden.Rendering object at 0x7f1952a82510>.lines

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:263: AssertionError
________ test_guard_g3_scan_breaks_lines_only_on_markdown_endings[\x1d] ________

char = '\x1d'

    @pytest.mark.parametrize("char", [" ", " ", "\u0085", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e"])
    def test_guard_g3_scan_breaks_lines_only_on_markdown_endings(char):
        """G3: the false fence. Broken on ``char`` the ``~~~`` would open a fence and swallow the comment opener."""
        body = "x\n\n<!-- a -->" + char + "~~~\n<!--\n\n## H\n"
        rendering = md.scan(body)
>       assert len(rendering.lines) == 6  # x, blank, the one-line html, <!--, blank, ## H
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AssertionError: assert 7 == 6
E        +  where 7 = len(((0, 'visible'), (2, 'visible'), (3, 'visible'), (14, 'visible'), (18, 'visible'), (23, 'visible'), ...))
E        +    where ((0, 'visible'), (2, 'visible'), (3, 'visible'), (14, 'visible'), (18, 'visible'), (23, 'visible'), ...) = <md_hidden.Rendering object at 0x7f1952a86630>.lines

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:263: AssertionError
________ test_guard_g3_scan_breaks_lines_only_on_markdown_endings[\x1e] ________

char = '\x1e'

    @pytest.mark.parametrize("char", [" ", " ", "\u0085", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e"])
    def test_guard_g3_scan_breaks_lines_only_on_markdown_endings(char):
        """G3: the false fence. Broken on ``char`` the ``~~~`` would open a fence and swallow the comment opener."""
        body = "x\n\n<!-- a -->" + char + "~~~\n<!--\n\n## H\n"
        rendering = md.scan(body)
>       assert len(rendering.lines) == 6  # x, blank, the one-line html, <!--, blank, ## H
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AssertionError: assert 7 == 6
E        +  where 7 = len(((0, 'visible'), (2, 'visible'), (3, 'visible'), (14, 'visible'), (18, 'visible'), (23, 'visible'), ...))
E        +    where ((0, 'visible'), (2, 'visible'), (3, 'visible'), (14, 'visible'), (18, 'visible'), (23, 'visible'), ...) = <md_hidden.Rendering object at 0x7f1952a872c0>.lines

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:263: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g3_scan_breaks_lines_only_on_markdown_endings[ ]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g3_scan_breaks_lines_only_on_markdown_endings[ ]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g3_scan_breaks_lines_only_on_markdown_endings[\x85]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g3_scan_breaks_lines_only_on_markdown_endings[\x0b]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g3_scan_breaks_lines_only_on_markdown_endings[\x0c]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g3_scan_breaks_lines_only_on_markdown_endings[\x1c]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g3_scan_breaks_lines_only_on_markdown_endings[\x1d]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g3_scan_breaks_lines_only_on_markdown_endings[\x1e]
8 failed, 411 deselected in 0.35s
```

  All eight characters go red, each on the line-count assertion (`:263`, the consumer `md.scan` reporting 7 lines for a
  body of 6). The `_reads(body, "## H", H)` assertion at `:264` was never reached in the red run, so the red is on the
  line-break axis itself, not on the heading reading. `split_lines` is also the line source of the test helper `_offset`
  (`:36`), but the failing assertion does not go through it.
- **Restore:** inverse Edit, `return text.splitlines(keepends=True)` back to `return out`.
- **Restore receipt:** the restored line reads `    return out` (`md_fence.py:303`; the search `^    return (out|text\.splitlines)`
  returned only that line).
- **Raw green** (same `-k`):

```
........                                                                 [100%]
8 passed, 411 deselected in 0.26s
```

## G4: a comment survives its container's end

- **Guarded element / axis:** the comment pass `md_hidden.py:646-647` (`for i in range(len(texts)):` / `hidden = state == _COMMENT`);
  the comment state is carried across lines and is not reset when a block quote or list item closes (the raw `<!--` is
  in the HTML, which the container does not contain). The guard is an absence: no container-end reset exists.
- **Neutralization (one Edit, one contiguous region `md_hidden.py:632-647`, five lines changed or added):** after
  `parser = _Parser(offsets, texts)` the lines `closes = set()` and `finalize = parser._finalize`, then a nested
  `def record(block):` (body: `if block.kind in ("quote", "item"):` / `closes.add(parser.idx)`, then `return finalize(block)`),
  then `parser._finalize = record`, then `parser.run()` as before; and, as the first lines inside
  `for i in range(len(texts)):`, `if i in closes:` / `state = _DATA`, before `hidden = state == _COMMENT`. (The state is reset
  to data at the line on which a quote or item is finalized.) The module still imports.
- **Raw red** (`-k test_guard_g4_comment_survives_the_end_of_its_container`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_guard_g4_comment_survives_the_end_of_its_container ____________

    def test_guard_g4_comment_survives_the_end_of_its_container():
>       _reads("x\n\n> <!--\n\n## H\n", "## H", H)

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:618: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

body = 'x\n\n> <!--\n\n## H\n', heading = '## H', expected = 'hidden'

    def _reads(body, heading, expected):
        """The heading line reads ``expected``; when HIDDEN its text is also not a VISIBLE entry of ``headings``."""
        got = _state(body, heading)
>       assert got == expected, "heading %r reads %s, expected %s; unsure=%r" % (heading, got, expected, md.scan(body).unsure)
E       AssertionError: heading '## H' reads visible, expected hidden; unsure=()
E       assert 'visible' == 'hidden'
E         
E         - hidden
E         + visible

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:54: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g4_comment_survives_the_end_of_its_container
1 failed, 418 deselected in 0.23s
```

  The red is on the first assertion (`:618`, the block-quote shape). The second assertion (`:619`, the list-item shape) was
  not reached, so this run proves the quote half; the neutralization covered both kinds, but no red is recorded for the
  list-item shape taken alone.
- **Restore:** inverse Edit of the same region (the added lines removed).
- **Restore receipt:** lines `632-633` read `    parser = _Parser(offsets, texts)` / `    parser.run()`, and `646-647` read
  `    for i in range(len(texts)):` / `        hidden = state == _COMMENT` (read back with the file-read tool).
- **Raw green** (same `-k`):

```
.                                                                        [100%]
1 passed, 418 deselected in 0.25s
```

## G5: fence runs over 255 read unsure

- **Guarded element / axis:** two sites of one rule, `md_hidden.py:389-390` (a closing fence line with a run over 255) and
  `md_hidden.py:506-507` (an opening fence line with a run over 255), each `self._note("fence run longer than 255")`; cmark
  stores at most 255 fence characters, so a longer run reads UNSURE from that line on, where a decided parse would read VISIBLE.
- **Neutralization:** both `self._note("fence run longer than 255")` calls became `pass` (the whole >255 unsure point dropped).
  The module still imports. Two edits, one per site, because the rule has two sites; the order's "drop the >255 unsure point"
  was read as the rule, not one site.
- **Opener site dropped alone** (`md_hidden.py:507` only, `-k test_guard_g5_fence_cap_reads_unsure_where_a_decided_parse_would_read_visible`): **stayed green**:

```
..                                                                       [100%]
2 passed, 417 deselected in 0.27s
```

  Why: the first body has a 256 opener and a 256 closer, so the closer site's point still fires and the heading still
  reads UNSURE. The second body has a 3-run opener, so only the closer site matters there. **The named test does not
  discriminate the opener site**; that site is bitten only by tests outside the named one (by reading,
  `test_unsure_fence_run_longer_than_255_opening`; not run). Recorded as a detector finding below; the test was not changed.
- **Raw red** (both sites dropped, same `-k`):

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_guard_g5_fence_cap_reads_unsure_where_a_decided_parse_would_read_visible[~] _

fence = '~'

    @pytest.mark.parametrize("fence", ["~", "`"])
    def test_guard_g5_fence_cap_reads_unsure_where_a_decided_parse_would_read_visible(fence):
        run = fence * 256
        body = "a\n\n" + run + "\nx\n" + run + "\n\n## H\n"
>       assert _state(body, "## H") == U
E       AssertionError: assert 'visible' == 'unsure'
E         
E         - unsure
E         + visible

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:626: AssertionError
_ test_guard_g5_fence_cap_reads_unsure_where_a_decided_parse_would_read_visible[`] _

fence = '`'

    @pytest.mark.parametrize("fence", ["~", "`"])
    def test_guard_g5_fence_cap_reads_unsure_where_a_decided_parse_would_read_visible(fence):
        run = fence * 256
        body = "a\n\n" + run + "\nx\n" + run + "\n\n## H\n"
>       assert _state(body, "## H") == U
E       AssertionError: assert 'visible' == 'unsure'
E         
E         - unsure
E         + visible

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:626: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g5_fence_cap_reads_unsure_where_a_decided_parse_would_read_visible[~]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g5_fence_cap_reads_unsure_where_a_decided_parse_would_read_visible[`]
2 failed, 417 deselected in 0.31s
```

  The red is on the first assertion (`:626`) for both fence characters: UNSURE owed, `visible` read. The closer-only body
  (`:628-630`) was not reached. The closer site alone was not dropped alone either (the run order was opener-only, then
  both), so "the closer site is the one the named test depends on" is an inference from the opener-only green plus the
  both-sites red, not a separate run.
- **Restore:** inverse Edits at both sites, `pass` back to `self._note("fence run longer than 255")` (each with its
  `if run > _FENCE_CAP:` line as context, since the call text occurs at both).
- **Restore receipt:** the file search returned `389:  if run > _FENCE_CAP:` / `390:       self._note("fence run longer than 255")`
  and `506:  if run > _FENCE_CAP:` / `507:       self._note("fence run longer than 255")` (the indentation is 24 and 28
  spaces at 389-390, 16 and 20 at 506-507, as on the head).
- **Raw green** (same `-k`):

```
..                                                                       [100%]
2 passed, 417 deselected in 0.27s
```

## G6: tagfilter names read unsure

- **Guarded element / axis:** `md_hidden.py:591`, `if _TAGFILTER.search(rest):` (the regex at `:58`); a line holding one of
  GitHub's tagfilter tag names (the attribute opener inside it may be escaped away) makes the parse UNSURE.
- **Neutralization:** `md_hidden.py:591` `        if _TAGFILTER.search(rest):` became `        if False and _TAGFILTER.search(rest):`.
  The module still imports.
- **Raw red** (`-k test_guard_g6_tagfilter_names_make_the_attribute_opener_unsure`):

```
FFF.FFFFF                                                                [100%]
=================================== FAILURES ===================================
____ test_guard_g6_tagfilter_names_make_the_attribute_opener_unsure[script] ____

name = 'script'

    @pytest.mark.parametrize("name", ["script", "style", "title", "textarea", "xmp", "iframe", "noembed", "noframes", "plaintext"])
    def test_guard_g6_tagfilter_names_make_the_attribute_opener_unsure(name):
        body = "x\n\n<div title=\"x\">\n<%s title=\"<!--\">\n\n## H\n" % name
>       assert _state(body, "## H") == U
E       AssertionError: assert 'visible' == 'unsure'
E         
E         - unsure
E         + visible

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:636: AssertionError
____ test_guard_g6_tagfilter_names_make_the_attribute_opener_unsure[style] _____

name = 'style'

    @pytest.mark.parametrize("name", ["script", "style", "title", "textarea", "xmp", "iframe", "noembed", "noframes", "plaintext"])
    def test_guard_g6_tagfilter_names_make_the_attribute_opener_unsure(name):
        body = "x\n\n<div title=\"x\">\n<%s title=\"<!--\">\n\n## H\n" % name
>       assert _state(body, "## H") == U
E       AssertionError: assert 'visible' == 'unsure'
E         
E         - unsure
E         + visible

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:636: AssertionError
____ test_guard_g6_tagfilter_names_make_the_attribute_opener_unsure[title] _____

name = 'title'

    @pytest.mark.parametrize("name", ["script", "style", "title", "textarea", "xmp", "iframe", "noembed", "noframes", "plaintext"])
    def test_guard_g6_tagfilter_names_make_the_attribute_opener_unsure(name):
        body = "x\n\n<div title=\"x\">\n<%s title=\"<!--\">\n\n## H\n" % name
>       assert _state(body, "## H") == U
E       AssertionError: assert 'visible' == 'unsure'
E         
E         - unsure
E         + visible

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:636: AssertionError
____ test_guard_g6_tagfilter_names_make_the_attribute_opener_unsure[xmp] ______

name = 'xmp'

    @pytest.mark.parametrize("name", ["script", "style", "title", "textarea", "xmp", "iframe", "noembed", "noframes", "plaintext"])
    def test_guard_g6_tagfilter_names_make_the_attribute_opener_unsure(name):
        body = "x\n\n<div title=\"x\">\n<%s title=\"<!--\">\n\n## H\n" % name
>       assert _state(body, "## H") == U
E       AssertionError: assert 'visible' == 'unsure'
E         
E         - unsure
E         + visible

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:636: AssertionError
____ test_guard_g6_tagfilter_names_make_the_attribute_opener_unsure[iframe] ____

name = 'iframe'

    @pytest.mark.parametrize("name", ["script", "style", "title", "textarea", "xmp", "iframe", "noembed", "noframes", "plaintext"])
    def test_guard_g6_tagfilter_names_make_the_attribute_opener_unsure(name):
        body = "x\n\n<div title=\"x\">\n<%s title=\"<!--\">\n\n## H\n" % name
>       assert _state(body, "## H") == U
E       AssertionError: assert 'visible' == 'unsure'
E         
E         - unsure
E         + visible

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:636: AssertionError
___ test_guard_g6_tagfilter_names_make_the_attribute_opener_unsure[noembed] ____

name = 'noembed'

    @pytest.mark.parametrize("name", ["script", "style", "title", "textarea", "xmp", "iframe", "noembed", "noframes", "plaintext"])
    def test_guard_g6_tagfilter_names_make_the_attribute_opener_unsure(name):
        body = "x\n\n<div title=\"x\">\n<%s title=\"<!--\">\n\n## H\n" % name
>       assert _state(body, "## H") == U
E       AssertionError: assert 'visible' == 'unsure'
E         
E         - unsure
E         + visible

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:636: AssertionError
___ test_guard_g6_tagfilter_names_make_the_attribute_opener_unsure[noframes] ___

name = 'noframes'

    @pytest.mark.parametrize("name", ["script", "style", "title", "textarea", "xmp", "iframe", "noembed", "noframes", "plaintext"])
    def test_guard_g6_tagfilter_names_make_the_attribute_opener_unsure(name):
        body = "x\n\n<div title=\"x\">\n<%s title=\"<!--\">\n\n## H\n" % name
>       assert _state(body, "## H") == U
E       AssertionError: assert 'visible' == 'unsure'
E         
E         - unsure
E         + visible

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:636: AssertionError
__ test_guard_g6_tagfilter_names_make_the_attribute_opener_unsure[plaintext] ___

name = 'plaintext'

    @pytest.mark.parametrize("name", ["script", "style", "title", "textarea", "xmp", "iframe", "noembed", "noframes", "plaintext"])
    def test_guard_g6_tagfilter_names_make_the_attribute_opener_unsure(name):
        body = "x\n\n<div title=\"x\">\n<%s title=\"<!--\">\n\n## H\n" % name
>       assert _state(body, "## H") == U
E       AssertionError: assert 'visible' == 'unsure'
E         
E         - unsure
E         + visible

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:636: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g6_tagfilter_names_make_the_attribute_opener_unsure[script]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g6_tagfilter_names_make_the_attribute_opener_unsure[style]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g6_tagfilter_names_make_the_attribute_opener_unsure[title]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g6_tagfilter_names_make_the_attribute_opener_unsure[xmp]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g6_tagfilter_names_make_the_attribute_opener_unsure[iframe]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g6_tagfilter_names_make_the_attribute_opener_unsure[noembed]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g6_tagfilter_names_make_the_attribute_opener_unsure[noframes]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g6_tagfilter_names_make_the_attribute_opener_unsure[plaintext]
8 failed, 1 passed, 410 deselected in 0.38s
```

  Eight of the nine names go red on the first assertion (`:636`). **The `[textarea]` case stayed green** with the tagfilter
  point dropped: that case does not discriminate the tagfilter point. By code reading (not run separately): the
  `<textarea title="<!--">` line also matches `_VERSION_TAGS` (`md_hidden.py:57`), whose own unsure point (`:589-590`) fires at
  the same line, so the heading reads UNSURE with or without the tagfilter point. Recorded as a detector finding below.
- **Restore:** inverse Edit, `if False and _TAGFILTER.search(rest):` back to `if _TAGFILTER.search(rest):`.
- **Restore receipt:** the restored line reads `        if _TAGFILTER.search(rest):` (`md_hidden.py:591`).
- **Raw green** (same `-k`):

```
.........                                                                [100%]
9 passed, 410 deselected in 0.27s
```

## G7: footnote definitions read unsure

- **Guarded element / axis:** `md_hidden.py:587`, `if _FOOTNOTE.match(rest):`; a footnote definition's body is rendered
  apart from the paragraph structure, so the parse is UNSURE from that line on.
- **Neutralization:** `md_hidden.py:587` `        if _FOOTNOTE.match(rest):` became `        if False and _FOOTNOTE.match(rest):`.
  The module still imports.
- **Raw red** (`-k test_guard_g7_footnote_definition_reads_unsure`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_guard_g7_footnote_definition_reads_unsure ________________

    def test_guard_g7_footnote_definition_reads_unsure():
        body = "x[^1]\n\n[^1]: <div>\n    `<!--`\n\n## H\n"
>       assert _state(body, "## H") == U
E       AssertionError: assert 'visible' == 'unsure'
E         
E         - unsure
E         + visible

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:642: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g7_footnote_definition_reads_unsure
1 failed, 418 deselected in 0.26s
```

- **Restore:** inverse Edit, `if False and _FOOTNOTE.match(rest):` back to `if _FOOTNOTE.match(rest):`.
- **Restore receipt:** the restored line reads `        if _FOOTNOTE.match(rest):` (`md_hidden.py:587`).
- **Raw green** (same `-k`):

```
.                                                                        [100%]
1 passed, 418 deselected in 0.33s
```

## G8: table rows starting `<`, a list marker or a setext line read unsure

- **Guarded element / axis:** `md_hidden.py:422`, `if rest.startswith("<") or _LIST_START.match(rest) or _SETEXT.match(rest):`
  (in `_table_row_check`, after a GFM delimiter row); such a row may be a table row GitHub's table extension handles
  differently, so the parse is UNSURE from it on.
- **Neutralization:** `md_hidden.py:422` became `        if False and (rest.startswith("<") or _LIST_START.match(rest) or _SETEXT.match(rest)):`
  (the whole table unsure point dropped). The module still imports.
- **Raw red** (`-k test_guard_g8_table_row_reads_unsure`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________________ test_guard_g8_table_row_reads_unsure _____________________

    def test_guard_g8_table_row_reads_unsure():
        body = "| a |\n| - |\n<span>\nx <!--\n\n## H\n"
>       assert _state(body, "## H") == U
E       AssertionError: assert 'visible' == 'unsure'
E         
E         - unsure
E         + visible

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:648: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g8_table_row_reads_unsure
1 failed, 418 deselected in 0.26s
```

  The named test's only table row is `<span>`, so it exercises the `startswith("<")` disjunct. By reading the test body
  (not run): the list-marker and setext-underline disjuncts are not exercised by `test_guard_g8_table_row_reads_unsure`;
  `test_unsure_gfm_table_row_after_the_delimiter_row` (`:299-306`) has those rows. Recorded below as a signal.
- **Restore:** inverse Edit, the `False and (...)` wrapper removed.
- **Restore receipt:** the restored line reads `        if rest.startswith("<") or _LIST_START.match(rest) or _SETEXT.match(rest):` (`md_hidden.py:422`).
- **Raw green** (same `-k`):

```
.                                                                        [100%]
1 passed, 418 deselected in 0.24s
```

## G9: in comment state, inline `<` ... `-->` reads unsure

- **Guarded element / axis:** `md_hidden.py:657-658`, `if hidden and _closer_after_lt(joined):`; a paragraph read in the
  comment state that holds a `<` and a later `-->` or `--!>` could close the comment through a raw inline chunk, so the
  parse is UNSURE from it on (and the line before it still reads as it did).
- **Neutralization:** `md_hidden.py:657` `            if hidden and _closer_after_lt(joined):` became
  `            if False and hidden and _closer_after_lt(joined):`. The module still imports.
- **Raw red** (`-k test_guard_g9_comment_state_inline_closer_reads_unsure`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_guard_g9_comment_state_inline_closer_reads_unsure ____________

    def test_guard_g9_comment_state_inline_closer_reads_unsure():
        body = "<div>\n<!-- a\n\nb <!-- c --> e\n\n## H\n"
>       assert _state(body, "## H") == U
E       AssertionError: assert 'hidden' == 'unsure'
E         
E         - unsure
E         + hidden

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:654: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g9_comment_state_inline_closer_reads_unsure
1 failed, 418 deselected in 0.26s
```

  The red is `hidden` read where `unsure` is owed: HIDDEN is reported where the parse cannot be sure, the axis of this guard.
- **Restore:** inverse Edit, the `False and ` prefix removed.
- **Restore receipt:** the restored line reads `            if hidden and _closer_after_lt(joined):` (`md_hidden.py:657`).
- **Raw green** (same `-k`):

```
.                                                                        [100%]
1 passed, 418 deselected in 0.25s
```

## G10: an HTML block ending inside a tag or bogus comment reads unsure

- **Guarded element / axis:** `md_hidden.py:651-653`, the unsure point at `:653`; an HTML block whose last line leaves the
  tokenizer inside a tag or a bogus comment is not decided (the HTML parser carries on past the Markdown block end), so
  the parse is UNSURE from the next line on.
- **Neutralization:** `md_hidden.py:653` `                unsure[(at, "HTML block ends inside a tag or a bogus comment")] = None`
  became `                pass` (the `state = _DATA` reset on the next line stays). The module still imports.
- **Raw red** (`-k test_guard_g10_block_ending_inside_a_tag_reads_unsure`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_guard_g10_block_ending_inside_a_tag_reads_unsure _____________

    def test_guard_g10_block_ending_inside_a_tag_reads_unsure():
        body = "x\n\n<div title=\"\n\n## H\n"
>       assert _state(body, "## H") == U
E       AssertionError: assert 'visible' == 'unsure'
E         
E         - unsure
E         + visible

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:660: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g10_block_ending_inside_a_tag_reads_unsure
1 failed, 418 deselected in 0.33s
```

  The named test's body ends the block inside a quoted attribute value (a tag state); the bogus-comment state shares the
  one condition (`state not in _OPEN_STATES`, `:651`) and has its own tests outside the named one.
- **Restore:** inverse Edit with context (a bare `pass` occurs four times in the file), `pass` back to the `unsure[...] = None` line.
- **Restore receipt:** lines `651-654` read back as `            if i in html_last and state not in _OPEN_STATES:` /
  `                at = offsets[i + 1] if i + 1 < len(texts) else len(body)` /
  `                unsure[(at, "HTML block ends inside a tag or a bogus comment")] = None` / `                state = _DATA`.
- **Raw green** (same `-k`):

```
.                                                                        [100%]
1 passed, 418 deselected in 0.26s
```

## G11: type 7 cannot interrupt a paragraph

- **Guarded element / axis:** `md_hidden.py:451`, `if kind != "para" and not maybe_lazy:` (in `_html_start_type`); an HTML
  block of type 7 (a lone complete tag on a line) cannot interrupt a paragraph, so `a\n<span>` is paragraph text.
- **Neutralization:** `md_hidden.py:451` `        if kind != "para" and not maybe_lazy:` became
  `        if True or kind != "para" and not maybe_lazy:` (type 7 may start in every case). The module still imports. The whole
  condition was neutralized, not only `kind != "para"`: by code reading (not run), `kind == "para"` implies the tip is a
  paragraph, so `maybe_lazy` is already true and the `kind != "para"` clause alone is redundant (an equivalent mutant).
- **Raw red** (`-k test_guard_g11_type7_cannot_interrupt_a_paragraph`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_guard_g11_type7_cannot_interrupt_a_paragraph _______________

    def test_guard_g11_type7_cannot_interrupt_a_paragraph():
        body = "a\n<span>\nx <!--\n\n## H\n"
>       assert _state(body, "## H") == V
E       AssertionError: assert 'hidden' == 'visible'
E         
E         - visible
E         + hidden

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:666: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g11_type7_cannot_interrupt_a_paragraph
1 failed, 418 deselected in 0.26s
```

  The red is `hidden` read where `visible` is owed (the `<span>` became a raw block whose `x <!--` opened a comment).
  The assertions at `:667-671` were not reached.
- **Restore:** inverse Edit, `True or ` removed.
- **Restore receipt:** the restored line reads `        if kind != "para" and not maybe_lazy:` (`md_hidden.py:451`).
- **Raw green** (same `-k`):

```
.                                                                        [100%]
1 passed, 418 deselected in 0.35s
```

## G12: type 4 needs an uppercase letter

- **Guarded element / axis:** `md_hidden.py:39`, `_HTML_T4 = re.compile(r"<![A-Z]")`; an HTML block of type 4 (a
  declaration) starts only with `<!` and an ASCII uppercase letter; `<!x` is paragraph text on GitHub.
- **Neutralization:** `md_hidden.py:39` `_HTML_T4 = re.compile(r"<![A-Z]")` became `_HTML_T4 = re.compile(r"<![A-Za-z]")`
  (any ASCII letter after `<!`). The module still imports.
- **Raw red** (`-k test_guard_g12_type4_needs_an_uppercase_letter`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_guard_g12_type4_needs_an_uppercase_letter ________________

    def test_guard_g12_type4_needs_an_uppercase_letter():
>       assert _state("x\n\n<!x\nfoo > <!--\n\n## H\n", "## H") == V  # lowercase: paragraph text, GitHub shows no block
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AssertionError: assert 'hidden' == 'visible'
E         
E         - visible
E         + hidden

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:675: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_guard_g12_type4_needs_an_uppercase_letter
1 failed, 418 deselected in 0.26s
```

  The red is on the lowercase assertion (`:675`): the `<!x` line became a declaration block and the `<!--` after its `>`
  opened a comment. The uppercase assertion (`:676`) holds either way and is not the one that bit.
- **Restore:** inverse Edit, `[A-Za-z]` back to `[A-Z]`.
- **Restore receipt:** the restored line reads `_HTML_T4 = re.compile(r"<![A-Z]")` (`md_hidden.py:39`).
- **Raw green** (same `-k`):

```
.                                                                        [100%]
1 passed, 418 deselected in 0.25s
```

## Whole-file run after the last restore

`plugins/superheroes/lib/tests/test_md_hidden_2366.py plugins/superheroes/lib/tests/test_md_fence.py -q`:

```
........................................................................ [ 14%]
........................................................................ [ 29%]
.................ss..........................ssss....ssssss..........sss [ 43%]
s........ss..ssss..ss................................................... [ 58%]
........................................................................ [ 72%]
........................................................................ [ 87%]
...............................................................          [100%]
471 passed, 24 skipped in 1.91s
```

The 24 skips are not itemised by this command (no `-rs`); the detector file itself calls `pytest.skip` only in the oracle
(b) test (`:175` setext body, `:178` unsure parse), so some or all of them are those; this was not checked per node.
`git diff --stat` printed nothing: no tracked file differs, so `md_hidden.py` and `md_fence.py` are byte-identical to the head.

## Findings for the builder (detector, not changed)

1. **G5, opener site masked.** `test_guard_g5_*` stays green when only the opener site (`md_hidden.py:507`) is dropped
   (`2 passed`, above): its first body has a 256 closer that fires the same point. Only the closer site is discriminated.
   A body that would bite the opener alone: a 256-run opener closed by a 255-run (a run of 255 closes a fence capped at 255
   and is not over 255, so only the opener's point applies). This body is a suggestion, not run.
2. **G6, `[textarea]` masked.** With the tagfilter point dropped the `textarea` case stays green (`8 failed, 1 passed`):
   `_VERSION_TAGS` fires on the same line (reading). The tagfilter name `textarea` is not discriminated by this test; the
   other eight names are.
3. **G8, one disjunct exercised.** The named test's row is `<span>`; the list-marker and setext-underline disjuncts of the
   condition at `:422` are exercised only by tests outside the named one (reading, not run).
4. **G11, two clauses in series.** `kind != "para"` and `not maybe_lazy` are each redundant with the other for the named
   test's body (reading). The red above is for the condition as a whole; the lazy-continuation case is the
   `not maybe_lazy` clause's own (reading: `test_blockquote_lazy_paragraph_continuation_is_not_a_block_start`, not run).
5. **G4, G1, G2, G11, G12, G5: the red stops at the first assertion**, so the later assertions of those tests were not shown
   to bite. For G4 that is the list-item shape (`:619`), for G1 the backtick-in-`<div>` shapes (`:602-603`), for G2 the
   plain and code-span closers (`:608-609`).

## Elements in no class

None: G1 to G12 each have their own neutralization and red. Unproven elements: none outright. Partially proven, with the
reasons above: G4 (quote shape only), G5 (closer site only by the named test), G6 (eight of nine names), G8 (the `<`
disjunct only), G11 (the condition as a whole, not each clause).
