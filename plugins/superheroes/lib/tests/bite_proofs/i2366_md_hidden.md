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

## Vet 845 fix leg (F1–F4)

Detector under proof: the `test_vet845_*` tests of `plugins/superheroes/lib/tests/test_md_hidden_2366.py` (added at
`db9b09ee`). Guarded code: `plugins/superheroes/lib/md_hidden.py` at `db9b09ee`, F1–F4. Worktree `/home/user/wt-2366`.
Every neutralization was one targeted Edit-tool edit to `md_hidden.py`, undone by the inverse Edit before the next
element; no `git checkout`, `restore`, `reset` or `stash`. Each run is the single test function's node id (all of its
parametrized cases), command prefix (worktree root):
`scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_md_hidden_2366.py::<test> -q`
Restore receipts are the restored lines quoted back with the file-search tool after each inverse Edit. A final
`git diff db9b09ee --stat -- plugins/superheroes/lib/md_hidden.py` printed nothing: the file is byte-identical to `db9b09ee`.

Guarded-element set (declared by the order): B1 to B6, no others.

Disclosures:
- Every capture is the runner's output with uv's one `UV_NATIVE_TLS` deprecation warning line dropped. Nothing was redacted.
- Where a red repeats the same traceback for each parametrized case, only the first traceback is quoted and the repeats are
  marked `[N repeated tracebacks elided]`; the `FAILED` list and the summary line are quoted whole. In two runs (B1, B3)
  the tool output itself arrived with a middle part cut off (`... [4546 characters truncated] ...`, `... [1165 characters
  truncated] ...`); those two captures are **incomplete** by that much, and the summary lists, which are whole, are what
  the red rests on.
- The neutralization of B2, B3, B4, B5 and B6 each left the module importable; B1 restored the old clause as two lines.

## B1: F1 no `script`/`style`/`pre` exclusion on a type-7 start

- **Guarded element / axis:** `md_hidden.py:460-461`, `if _HTML_T7.match(rest): return 7` in `_html_start_type`; a
  closing or self-closing `pre` tag alone on a line starts a type-7 block (cmark-gfm has no such exclusion), so a `<!--`
  after it opens a comment. The axis is a hidden heading read VISIBLE.
- **Neutralization:** the two lines became `m = _HTML_T7.match(rest)` /
  `if m and (m.group(1) or m.group(2)).lower() not in ("script", "style", "pre"):` (the exclusion clause restored).
- **Raw red** (`test_vet845_f1_a_pre_tag_alone_on_a_line_starts_a_type7_block` and
  `test_vet845_f1_the_builder_body_shape_does_not_read_visible`, one command), incomplete as disclosed:

```
FFFFFFFFFFFFF                                                            [100%]
=================================== FAILURES ===================================
___ test_vet845_f1_a_pre_tag_alone_on_a_line_starts_a_type7_block[top-close] ___

tag = '</pre>', where = 'top'

    @pytest.mark.parametrize("tag", _F1_TAGS, ids=["close", "CLOSE", "close-space", "selfclose"])
    @pytest.mark.parametrize("where", ["top", "item", "quote"])
    def test_vet845_f1_a_pre_tag_alone_on_a_line_starts_a_type7_block(tag, where):
        """vet 845 receipt on PR #2390 (comment 6709845874), ``POST /markdown``: GitHub hid everything below the ``x <!--``
        line. cmark-gfm's type-7 scanner has no script/style/pre exclusion."""
        body = _F1_SHAPES[where].format(tag=tag)
        got = _state(body, "## H")
>       assert got != V, "## H reads VISIBLE in %r; unsure=%r" % (body, md.scan(body).unsure)
E       AssertionError: ## H reads VISIBLE in 'x\n\n</pre>\nx <!--\n\n## H\n'; unsure=()
E       assert 'visible' != 'visible'

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:730: AssertionError
[10 repeated tracebacks elided, and the tool's own truncation: top-CLOSE ... quote-selfclose, same assertion]
_________ test_vet845_f1_the_builder_body_shape_does_not_read_visible __________

    def test_vet845_f1_the_builder_body_shape_does_not_read_visible():
        """vet 845 receipt on PR #2390 (comment 6709845874), ``POST /markdown``: GitHub hid ``## What we're accepting``."""
        body = (
            "## What's changing, and why\n\nText.\n\n</pre>\nQuotes `<!--` in code.\n\n"
            "## What we're accepting\n\nNone.\n"
        )
>       assert _state(body, "## What we're accepting") != V
E       assert 'visible' != 'visible'
E        +  where 'visible' = _state("## What's changing, and why\n\nText.\n\n</pre>\nQuotes `<!--` in code.\n\n## What we're accepting\n\nNone.\n", "## What we're accepting")

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:741: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f1_a_pre_tag_alone_on_a_line_starts_a_type7_block[top-close]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f1_a_pre_tag_alone_on_a_line_starts_a_type7_block[top-CLOSE]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f1_a_pre_tag_alone_on_a_line_starts_a_type7_block[top-close-space]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f1_a_pre_tag_alone_on_a_line_starts_a_type7_block[top-selfclose]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f1_a_pre_tag_alone_on_a_line_starts_a_type7_block[item-close]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f1_a_pre_tag_alone_on_a_line_starts_a_type7_block[item-CLOSE]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f1_a_pre_tag_alone_on_a_line_starts_a_type7_block[item-close-space]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f1_a_pre_tag_alone_on_a_line_starts_a_type7_block[item-selfclose]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f1_a_pre_tag_alone_on_a_line_starts_a_type7_block[quote-close]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f1_a_pre_tag_alone_on_a_line_starts_a_type7_block[quote-CLOSE]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f1_a_pre_tag_alone_on_a_line_starts_a_type7_block[quote-close-space]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f1_a_pre_tag_alone_on_a_line_starts_a_type7_block[quote-selfclose]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f1_the_builder_body_shape_does_not_read_visible
13 failed in 0.57s
```

  All 12 parametrized cases (four tags in three containers) and the builder-body shape go red on `visible` read where
  not-`visible` is owed.
- **Restore:** inverse Edit, the two lines back to `if _HTML_T7.match(rest):` / `return 7`.
- **Restore receipt:** the file search returned `460: if _HTML_T7.match(rest):` / `461: return 7`
  (the comment on `:459` is unchanged).
- **Raw green** (same node ids):

```
.............                                                            [100%]
13 passed in 0.40s
```

## B2: F2 a line that starts inside a tag or bogus comment reads unsure

- **Guarded element / axis:** `md_hidden.py:672-674`, the line-start unsure point in `_scan`'s comment pass; a line that
  starts with the tokenizer in a tag or bogus-comment state reads UNSURE (never HIDDEN), where the head read it VISIBLE.
- **Neutralization:** `md_hidden.py:672` `        if state not in _OPEN_STATES:` became `        if False and state not in _OPEN_STATES:`
  (the end-of-block rule at `:677` was left alone).
- **Raw red** (`test_vet845_f2_a_line_inside_an_attribute_value_of_the_bot_path_reads_unsure`,
  `test_vet845_f2_a_line_inside_an_open_bogus_comment_reads_unsure_never_hidden` and
  `test_vet845_f2_a_line_inside_an_unclosed_attribute_value_reads_unsure`, one command):

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_vet845_f2_a_line_inside_an_attribute_value_of_the_bot_path_reads_unsure _

    def test_vet845_f2_a_line_inside_an_attribute_value_of_the_bot_path_reads_unsure():
        """vet 845 receipt on PR #2390 (comment 6709845874), ``POST /markdown``: GitHub put the marker and the verdict line
        inside the ``title`` attribute (hidden); the head read them VISIBLE."""
        body = 'Bumps x.\n\n## Advisor vet\n<div title="a\n<!-- superheroes:advisor-vet -->\n**Verdict: READY** · abc\n">\n'
>       assert _state(body, "<!-- superheroes:advisor-vet -->") == U
E       AssertionError: assert 'visible' == 'unsure'
E         
E         - unsure
E         + visible

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:758: AssertionError
_ test_vet845_f2_a_line_inside_an_open_bogus_comment_reads_unsure_never_hidden _

    def test_vet845_f2_a_line_inside_an_open_bogus_comment_reads_unsure_never_hidden():
        """vet 845 receipt on PR #2390 (comment 6709845874), ``POST /markdown``: GitHub showed ``after`` (the ``>`` ended the
        bogus comment) - so neither line may read HIDDEN, and ``middle`` must not read VISIBLE."""
        body = "<div>\n<? a\nmiddle\n> after\n</div>\n"
>       assert _state(body, "middle") == U
E       AssertionError: assert 'visible' == 'unsure'
E         
E         - unsure
E         + visible

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:766: AssertionError
____ test_vet845_f2_a_line_inside_an_unclosed_attribute_value_reads_unsure _____

    def test_vet845_f2_a_line_inside_an_unclosed_attribute_value_reads_unsure():
        """vet 845 receipt on PR #2390 (comment 6709845874), ``POST /markdown``: GitHub hid ``middle`` (inside the quoted
        ``title`` value that closes on the next line)."""
        body = '<div title="x\nmiddle\n">\n\n## H\n'
>       assert _state(body, "middle") == U
E       AssertionError: assert 'visible' == 'unsure'
E         
E         - unsure
E         + visible

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:774: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f2_a_line_inside_an_attribute_value_of_the_bot_path_reads_unsure
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f2_a_line_inside_an_open_bogus_comment_reads_unsure_never_hidden
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f2_a_line_inside_an_unclosed_attribute_value_reads_unsure
3 failed in 0.44s
```

  Each test goes red on its first assertion. The second assertions of the first two tests (the verdict line, `> after`)
  were not reached. The control `test_vet845_f2_control_plain_lines_in_a_closed_block_stay_visible` was not run in this
  proof: it asserts a line stays VISIBLE, which this neutralization cannot break.
- **Restore:** inverse Edit, `if False and state not in _OPEN_STATES:` back to `if state not in _OPEN_STATES:`.
- **Restore receipt:** the file search returned `672: if state not in _OPEN_STATES:` and `677: if i in html_last and state not in _OPEN_STATES:`.
- **Raw green** (same node ids):

```
...                                                                      [100%]
3 passed in 0.30s
```

## B3: F3(a) a vertical tab inside an inline tag reads unsure

- **Guarded element / axis:** `md_hidden.py:687`, `if _tag_holds_vtab(joined):` (the helper at `:633-639`, the regex
  `_VTAB_TAG` at `:65`); a paragraph, heading, list item or table cell holding an inline tag with a `\v` before the next
  `>` reads UNSURE from its first line, where the head read it VISIBLE.
- **Neutralization:** `md_hidden.py:687` `            if _tag_holds_vtab(joined):` became `            if False and _tag_holds_vtab(joined):`.
- **Raw red** (`test_vet845_f3a_a_vertical_tab_inside_an_inline_tag_reads_unsure`), incomplete as disclosed (the
  tool cut the output between the `atx-vtab-value` and `item-vtab-value` tracebacks):

```
FFFFFFFF                                                                 [100%]
=================================== FAILURES ===================================
_ test_vet845_f3a_a_vertical_tab_inside_an_inline_tag_reads_unsure[para-vtab-name] _

opener = 'x <a\x0bb="> <!-- "> y', where = 'para'

    @pytest.mark.parametrize("opener", ['x <a\vb="> <!-- "> y', 'x <a b=\v"> <!-- "> y'], ids=["vtab-name", "vtab-value"])
    @pytest.mark.parametrize("where", ["para", "atx", "item", "cell"])
    def test_vet845_f3a_a_vertical_tab_inside_an_inline_tag_reads_unsure(opener, where):
        """vet 845 receipt on PR #2390 (comment 6709845874), ``POST /markdown``: GitHub hid everything below (HTML parsing
        does not count ``\\v`` as tag whitespace, so the tag ended at the ``>`` inside the quoted value)."""
        shapes = {
            "para": "{o}\n\n## H\n",
            "atx": "# {o}\n\n## H\n",
            "item": "- {o}\n\n## H\n",
            "cell": "| a | b |\n| - | - |\n| {o} | z |\n\n## H\n",
        }
        body = shapes[where].format(o=opener)
>       assert _state(body, "## H") == U, "unsure=%r" % (md.scan(body).unsure,)
E       AssertionError: unsure=()
E       assert 'visible' == 'unsure'
E         
E         - unsure
E         + visible

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:796: AssertionError
[7 repeated tracebacks elided, same assertion at :796 with unsure=()]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f3a_a_vertical_tab_inside_an_inline_tag_reads_unsure[para-vtab-name]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f3a_a_vertical_tab_inside_an_inline_tag_reads_unsure[para-vtab-value]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f3a_a_vertical_tab_inside_an_inline_tag_reads_unsure[atx-vtab-name]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f3a_a_vertical_tab_inside_an_inline_tag_reads_unsure[atx-vtab-value]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f3a_a_vertical_tab_inside_an_inline_tag_reads_unsure[item-vtab-name]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f3a_a_vertical_tab_inside_an_inline_tag_reads_unsure[item-vtab-value]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f3a_a_vertical_tab_inside_an_inline_tag_reads_unsure[cell-vtab-name]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f3a_a_vertical_tab_inside_an_inline_tag_reads_unsure[cell-vtab-value]
8 failed in 0.40s
```

  All eight cases (two tag shapes in a paragraph, ATX heading, list item and table cell) read `visible` where `unsure` is owed.
- **Restore:** inverse Edit, `if False and _tag_holds_vtab(joined):` back to `if _tag_holds_vtab(joined):`.
- **Restore receipt:** the file search returned `687: if _tag_holds_vtab(joined):`.
- **Raw green** (same node id):

```
........                                                                 [100%]
8 passed in 0.38s
```

## B4: F3(b) text after the first `>` of an inline `<?` or CDATA holds a `<`

- **Guarded element / axis:** `md_hidden.py:628`, `if close >= 0 and text.find("<", close) >= 0:` in
  `_runs_past_its_end`; an inline `<?` or `<![CDATA[` ended early by HTML parsing at its first `>` makes any later `<`
  (an unclosed attribute quote, not only a comment opener) a hazard, so the block reads UNSURE.
- **Neutralization:** `md_hidden.py:628` `text.find("<", close)` became `text.find("<!--", close)` (the pre-fix search).
- **Raw red** (`test_vet845_f3b_text_after_the_first_gt_of_an_inline_pi_or_cdata_reads_unsure`):

```
FFFF                                                                     [100%]
=================================== FAILURES ===================================
_ test_vet845_f3b_text_after_the_first_gt_of_an_inline_pi_or_cdata_reads_unsure[pi-dq] _

form = 'pi', quote = '"'

    @pytest.mark.parametrize("quote", ['"', "'"], ids=["dq", "sq"])
    @pytest.mark.parametrize("form", ["pi", "cdata"])
    def test_vet845_f3b_text_after_the_first_gt_of_an_inline_pi_or_cdata_reads_unsure(form, quote):
        """vet 845 receipt on PR #2390 (comment 6709845874), ``POST /markdown``: GitHub hid everything below (HTML parsing
        ended the bogus comment at the first ``>``, so the later ``<a title=`` opened an unclosed attribute quote)."""
        if form == "pi":
            body = "x <? > <a title=%s ?> y\n\n## H\n" % quote
        else:
            body = "x <![CDATA[ > <a title=%s ]]> y\n\n## H\n" % quote
>       assert _state(body, "## H") == U, "unsure=%r" % (md.scan(body).unsure,)
E       AssertionError: unsure=()
E       assert 'visible' == 'unsure'
E         
E         - unsure
E         + visible

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:808: AssertionError
[3 repeated tracebacks elided, same assertion at :808 with unsure=()]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f3b_text_after_the_first_gt_of_an_inline_pi_or_cdata_reads_unsure[pi-dq]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f3b_text_after_the_first_gt_of_an_inline_pi_or_cdata_reads_unsure[pi-sq]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f3b_text_after_the_first_gt_of_an_inline_pi_or_cdata_reads_unsure[cdata-dq]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f3b_text_after_the_first_gt_of_an_inline_pi_or_cdata_reads_unsure[cdata-sq]
4 failed in 0.32s
```

  All four cases go red. The bodies hold no `<!--`, so the pre-fix search cannot see their later `<`.
- **Restore:** inverse Edit, `text.find("<!--", close)` back to `text.find("<", close)`.
- **Restore receipt:** the file search returned `628: if close >= 0 and text.find("<", close) >= 0:`.
- **Raw green** (same node id):

```
....                                                                     [100%]
4 passed in 0.28s
```

## B5: F4(a) tag regexes match ASCII only

- **Guarded element / axis:** `md_hidden.py:44`, `_HTML_T6 = re.compile(..., re.I | re.A)`; Unicode case folding
  (`ſ` U+017F, the Kelvin sign U+212A, `İ` U+0130) must not match an ASCII letter of a block tag name (cmark is
  ASCII-only), so `<ſection>`, `<linK>` and `<dİv>` are paragraph text and a `<!--` after them opens no comment.
- **Neutralization:** `md_hidden.py:44` `re.I | re.A)` became `re.I)` on `_HTML_T6` alone (the order's neutralization).
- **Raw red** (`test_vet845_f4a_a_unicode_case_fold_of_an_ascii_tag_letter_is_no_block_start`):

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_vet845_f4a_a_unicode_case_fold_of_an_ascii_tag_letter_is_no_block_start[long-s] _

char = 383

    @pytest.mark.parametrize("char", [0x17F, 0x212A, 0x130], ids=["long-s", "kelvin", "dotted-i"])
    def test_vet845_f4a_a_unicode_case_fold_of_an_ascii_tag_letter_is_no_block_start(char):
        """vet 845 receipt on PR #2390 (comment 6709845874), ``POST /markdown``: GitHub showed ``H`` (cmark is ASCII-only, so
        the opener stays paragraph text and the ``<!--`` is not raw HTML)."""
        tags = {0x17F: "<%section>", 0x212A: "<lin%s>", 0x130: "<d%sv>"}
        body = "a\n" + tags[char] % chr(char) + "\nx <!--\n\n## H\n"
>       assert _state(body, "## H") == V
E       AssertionError: assert 'hidden' == 'visible'
E         
E         - visible
E         + hidden

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:824: AssertionError
[2 repeated tracebacks elided, same assertion at :824: kelvin (char = 8490) and dotted-i (char = 304)]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f4a_a_unicode_case_fold_of_an_ascii_tag_letter_is_no_block_start[long-s]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f4a_a_unicode_case_fold_of_an_ascii_tag_letter_is_no_block_start[kelvin]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f4a_a_unicode_case_fold_of_an_ascii_tag_letter_is_no_block_start[dotted-i]
3 failed in 0.32s
```

  All three characters go red: `hidden` read where `visible` is owed. Only `_HTML_T6` was neutralized; the same `re.A`
  on `_HTML_T1`, `_T1_END`, `_VERSION_TAGS` and `_TAGFILTER` is **not** discriminated by this test (no proof run for those
  four; they are unproven elements of F4(a)).
- **Restore:** inverse Edit, `re.I)` back to `re.I | re.A)` on `_HTML_T6`.
- **Restore receipt:** the file search returned `44: _HTML_T6 = re.compile(r"</?(?:" + "|".join(_BLOCK_TAGS) + r")(?:[ \t\v\f>]|/>|\Z)", re.I | re.A)`.
- **Raw green** (same node id):

```
...                                                                      [100%]
3 passed in 0.25s
```

## B6: F4(b) type 7's trailing whitespace excludes a vertical tab

- **Guarded element / axis:** `md_hidden.py:49`, `+ r"[ \t\f]*\Z"` in `_HTML_T7`; cmark-gfm's type 7 ends in `[\t\n\f ]`, so
  `<span>` + vertical tab is a paragraph (a `<!--` after it opens no comment) and `<span>` + form feed is a type-7 block.
- **Neutralization:** `md_hidden.py:49` `+ r"[ \t\f]*\Z"` became `+ _WS + r"*\Z"` (the pre-fix trailing class `[ \t\v\f]`).
- **Raw red** (`test_vet845_f4b_a_vertical_tab_after_a_type7_tag_is_not_trailing_whitespace`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_vet845_f4b_a_vertical_tab_after_a_type7_tag_is_not_trailing_whitespace __

    def test_vet845_f4b_a_vertical_tab_after_a_type7_tag_is_not_trailing_whitespace():
        """vet 845 receipt on PR #2390 (comment 6709845874), ``POST /markdown``: GitHub showed ``H`` after ``<span>\\v`` (a
        paragraph) and hid it after ``<span>\\f`` (a type-7 block)."""
>       assert _state("<span>\v\nx <!--\n\n## H\n", "## H") == V
E       AssertionError: assert 'hidden' == 'visible'
E         
E         - visible
E         + hidden

/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:830: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f4b_a_vertical_tab_after_a_type7_tag_is_not_trailing_whitespace
1 failed in 0.27s
```

  The red is on the first assertion (`:830`); the form-feed assertion (`:831`, `HIDDEN`) holds either way and was not reached.
- **Restore:** inverse Edit, `+ _WS + r"*\Z"` back to `+ r"[ \t\f]*\Z"`.
- **Restore receipt:** the file search returned `49: + r"[ \t\f]*\Z"  # cmark-gfm's type 7 ends in [\t\n\f ]: a vertical tab after the tag is not whitespace here`.
- **Raw green** (same node id):

```
.                                                                        [100%]
1 passed in 0.29s
```

Findings for the builder (detector, not changed): the F1 red covers the three containers and four tags together (a case
of the 12 is not shown to bite alone, since every case went red in this one neutralization); B5 proves the `re.A` on
`_HTML_T6` only; the F2 control and the F3 controls were not neutralized (they guard against false-unsure, which none of
these six neutralizations produces).

## Fix leg 2 (vet 846)

- **Status: bite-proofs C1–C7 run** (work order WO-4b). The two corpus bodies the advisor declined are pinned in
  `test_md_hidden_2366.py` as `_CORPUS_DECLINED` (vet 846 F7: `'x\n\n[ZQ1]: /u\n\n## ZQ2\n'`, a link reference definition)
  and `_CORPUS_DECLINED_FALSE_HIDDEN` (vet 845 F4(c): `'x\n\n<svg>\n\n<![CDATA[ x > <!-- y ]]>\n\n## ZQ1\n'`, CDATA inside
  `<svg>`). Each corpus test asserts its mapping holds exactly that one body, that the body is in the corpus, and that it
  **still fails** the plain check (so an exception never outlives its cause); every other body passes both directions.
  The `xfail` on `test_corpus_no_line_github_shows_reads_hidden` is removed.
- Test of record for the state of the tree: `test_md_hidden_2366.py` ends `469 passed, 28 skipped`;
  `test_md_fence.py` ends `76 passed`. Every neutralization below was restored by the inverse edit; `md_hidden.py` is
  byte-identical to `fda82205` (`git diff --stat` lists only the test file).
- All raw captures below are under the 32 KiB ceiling. Where a capture is shortened, the elision is said in place.

### C1: the inline pass is applied to text blocks

- **Guarded element / axis:** `md_hidden.py:801`, the call `_inline_pass(text_block[i].lines, i, inline_hidden, inline_points, inline_unsure)` (axis C1): every raw-HTML construct inside a paragraph or other text block is read.
- **Neutralization:** the call at `:801` became `pass  # C1 NEUTRALIZED`.
- **Raw red** (`test_corpus_no_line_github_hides_reads_visible`, `test_f5_a_comment_across_paragraph_lines_hides_the_lines_inside`,
  `test_f5_a_comment_across_paragraph_lines_with_two_hidden_lines_and_a_sentinel_after_the_closer`,
  `test_f5_a_setext_heading_paragraph_holding_a_multi_line_comment`, `test_f5_the_leftovers_shape_does_not_read_visible`),
  shortened: the corpus test's list of 61 `fail-open` entries is cut to its first 3 (58 entries elided), and each test's
  source listing is cut to its failing line:

```
FFFFF                                                                    [100%]
E       AssertionError: 61 fail-open (body, line index, line):
E         ('# x <a b=\x0b"> <!-- "> y\n\nZQ1\n\n## ZQ2\n', 2, 'ZQ1\n')
E         ('# x <a b=\x0b"> <!-- "> y\n\nZQ1\n\n## ZQ2\n', 4, '## ZQ2\n')
E         ('## H <!-- a -->\n\nb <!-- c\nZQ1 d -->\n\n## ZQ2\n', 3, 'ZQ1 d -->\n')
E       Left contains 61 more items, first extra item: ('# x <a b=\x0b"> <!-- "> y\n\nZQ1\n\n## ZQ2\n', 2, 'ZQ1\n')
test_md_hidden_2366.py:946: AssertionError
>       assert _state(body, "ZQ1") == H
E       AssertionError: assert 'visible' == 'hidden'
test_md_hidden_2366.py:973: AssertionError
>       assert _state(body, "ZQ1") == H and _state(body, "ZQ2") == H
E       AssertionError: assert ('visible' == 'hidden'
test_md_hidden_2366.py:984: AssertionError
>       assert _state(body, "ZQ1") == H
E       AssertionError: assert 'visible' == 'hidden'
test_md_hidden_2366.py:1026: AssertionError
>       assert _state(body, "F1 the retry loop ZQ1") in (H, U)
E       assert 'visible' in ('hidden', 'unsure')
test_md_hidden_2366.py:1035: AssertionError
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_corpus_no_line_github_hides_reads_visible
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_f5_a_comment_across_paragraph_lines_hides_the_lines_inside
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_f5_a_comment_across_paragraph_lines_with_two_hidden_lines_and_a_sentinel_after_the_closer
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_f5_a_setext_heading_paragraph_holding_a_multi_line_comment
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_f5_the_leftovers_shape_does_not_read_visible
5 failed in 0.62s
```

- **Restore:** inverse Edit, `pass  # C1 NEUTRALIZED` back to the `_inline_pass(...)` call.
- **Restore receipt:** the file search returned `801:                _inline_pass(text_block[i].lines, i, inline_hidden, inline_points, inline_unsure)`.
- **Raw green** (same five node ids):

```
.....                                                                    [100%]
5 passed in 0.57s
```

### C2: code spans are skipped

- **Guarded element / axis:** `md_hidden.py:672`, `i = closed if closed >= 0 else end` (axis C2): a backtick run that closes is skipped whole, so a `<!--` inside a code span is no comment.
- **Neutralization:** `:672` became `i = end` (the scan continues inside the span).
- **Raw red** (`test_f5_c2_a_code_span_opener_is_no_comment_even_with_a_later_closer`), source listing cut to the failing line:

```
F                                                                        [100%]
>       assert _state(body, "ZQ1") == V
E       AssertionError: assert 'hidden' == 'visible'
E         - visible
E         + hidden
test_md_hidden_2366.py:1090: AssertionError
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_f5_c2_a_code_span_opener_is_no_comment_even_with_a_later_closer
1 failed in 0.44s
```

- **Restore:** inverse Edit, `i = end` back to `i = closed if closed >= 0 else end`.
- **Restore receipt:** the file search returned `672:            i = closed if closed >= 0 else end`.
- **Raw green** (same node id):

```
.                                                                        [100%]
1 passed in 0.41s
```

### C3: a comment-state line start inside a construct reads HIDDEN

- **Guarded element / axis:** `md_hidden.py:734-738`, the `state == _COMMENT` branch of the per-line loop in `_inline_pass` (axis C3): a line that starts inside an inline comment is hidden (or unsure per C6).
- **Neutralization:** the branch body (the `_comment_line_state` test, `line_unsure.add`, `hidden_lines.add`) became `pass  # C3 NEUTRALIZED`, so the line keeps the default VISIBLE.
- **Raw red** (the same five node ids as C1), shortened the same way (11 `fail-open` entries, cut to the first 3, 8 elided):

```
FFFFF                                                                    [100%]
E       AssertionError: 11 fail-open (body, line index, line):
E         ('## H <!-- a -->\n\nb <!-- c\nZQ1 d -->\n\n## ZQ2\n', 3, 'ZQ1 d -->\n')
E         ("## What we're accepting\n\nLeftovers: <!-- draft list\nF1 the retry loop ZQ1\n-->\n- F2 ZQ2\n", 3, 'F1 the retry loop ZQ1\n')
E         ('- a <!-- b\n  ZQ1\n  --> c\n\n## ZQ2\n', 1, '  ZQ1\n')
E       Left contains 11 more items, first extra item: ('## H <!-- a -->\n\nb <!-- c\nZQ1 d -->\n\n## ZQ2\n', 3, 'ZQ1 d -->\n')
test_md_hidden_2366.py:946: AssertionError
E       AssertionError: assert 'visible' == 'hidden'      (:973, test_f5_a_comment_across_paragraph_lines_hides_the_lines_inside)
E       AssertionError: assert ('visible' == 'hidden'     (:984, ..._with_two_hidden_lines_and_a_sentinel_after_the_closer)
E       AssertionError: assert 'visible' == 'hidden'      (:1026, test_f5_a_setext_heading_paragraph_holding_a_multi_line_comment)
E       assert 'visible' in ('hidden', 'unsure')          (:1035, test_f5_the_leftovers_shape_does_not_read_visible)
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_corpus_no_line_github_hides_reads_visible
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_f5_a_comment_across_paragraph_lines_hides_the_lines_inside
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_f5_a_comment_across_paragraph_lines_with_two_hidden_lines_and_a_sentinel_after_the_closer
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_f5_a_setext_heading_paragraph_holding_a_multi_line_comment
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_f5_the_leftovers_shape_does_not_read_visible
5 failed in 0.49s
```

  (The four `E` lines after the first block are a compaction of four separate tracebacks, written as `E` line plus node; the
  run printed each with its full source listing.)
- **Restore:** inverse Edit, `pass  # C3 NEUTRALIZED` back to the four-line `if _comment_line_state(lines[k]) == UNSURE: ... else: hidden_lines.add(first + k)`.
- **Restore receipt:** the file read at `:734-738` returned `if state == _COMMENT:` / `if _comment_line_state(lines[k]) == UNSURE:` / `line_unsure.add(first + k)` / `else:` / `hidden_lines.add(first + k)`.
- **Raw green** (same five node ids):

```
.....                                                                    [100%]
5 passed in 0.43s
```

  C1 and C3 turn the same five tests red by different routes (C1 never runs the pass; C3 runs it and drops the comment-line
  result). The tests do not tell the two apart, and the set of reds is the order's own expectation for both.

### C4: a tag or bogus state at a line start inside a construct is unsure

- **Guarded element / axis:** `md_hidden.py:739-740`, `elif state != _DATA: sure_points.add(...)` (axis C4): a line that starts inside a tag or a bogus comment of an inline construct is an unsure point.
- **Neutralization:** `:739` `elif state != _DATA:` became `elif False and state != _DATA:  # C4 NEUTRALIZED`.
- **Raw red** (`test_f5_a_double_quoted_value_across_list_item_lines_reads_unsure`, `test_f5_a_single_quoted_value_across_paragraph_lines_reads_unsure`, `test_f5_an_unquoted_value_ended_by_a_line_break_reads_unsure`), source listings cut to the failing line:

```
FFF                                                                      [100%]
>       assert _state(body, "  ZQ1") == U
E       AssertionError: assert 'visible' == 'unsure'
test_md_hidden_2366.py:992: AssertionError
>       assert _state(body, "ZQ1") == U
E       AssertionError: assert 'visible' == 'unsure'
test_md_hidden_2366.py:1002: AssertionError
>       assert _state(body, "ZQ1") == U
E       AssertionError: assert 'visible' == 'unsure'
test_md_hidden_2366.py:1010: AssertionError
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_f5_a_double_quoted_value_across_list_item_lines_reads_unsure
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_f5_a_single_quoted_value_across_paragraph_lines_reads_unsure
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_f5_an_unquoted_value_ended_by_a_line_break_reads_unsure
3 failed in 0.37s
```

- **Restore:** inverse Edit, `elif False and state != _DATA:  # C4 NEUTRALIZED` back to `elif state != _DATA:`.
- **Restore receipt:** the file search returned `739:                elif state != _DATA:`.
- **Raw green** (same three node ids):

```
...                                                                      [100%]
3 passed in 0.33s
```

  The pi/cdata cross-line test `test_f5_an_inline_pi_or_cdata_across_lines_reads_unsure` was not in the order's list and was not run under C4.

### C5: the end-of-construct disagreement is unsure

- **Guarded element / axis:** `md_hidden.py:745-746`, the `state != _DATA` clause of `if state != _DATA or (is_tag and "\v" in construct): sure_points.add(...)` (axis C5): a construct that HTML parsing ends in a state other than `_DATA` makes the line that holds cmark's end of it an unsure point.
- **Neutralization:** `:745` became `if False or (is_tag and "\v" in construct):  # C5 NEUTRALIZED` (the vertical-tab clause is left, because it is C7's element).
- **Raw red** (`test_vet845_f3a_a_vertical_tab_inside_an_inline_tag_reads_unsure`, `test_vet845_f3b_text_after_the_first_gt_of_an_inline_pi_or_cdata_reads_unsure`, `test_unsure_inline_processing_instruction_ended_early_by_html`), shortened: the four `f3b` tracebacks are the same assertion and each prints its source listing, cut here to the failing line:

```
........FFFFF                                                            [100%]
>       assert _state(body, "## H") == U, "unsure=%r" % (md.scan(body).unsure,)
E       AssertionError: unsure=()
E       assert 'visible' == 'unsure'
test_md_hidden_2366.py:808: AssertionError          (x4: [pi-dq], [pi-sq], [cdata-dq], [cdata-sq])
>       assert any(offset == at for offset, _ in rendering.unsure), rendering.unsure
E       AssertionError: ()
E       assert False
test_md_hidden_2366.py:283: AssertionError          (test_unsure_inline_processing_instruction_ended_early_by_html, via _check_unsure at :407)
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f3b_text_after_the_first_gt_of_an_inline_pi_or_cdata_reads_unsure[pi-dq]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f3b_text_after_the_first_gt_of_an_inline_pi_or_cdata_reads_unsure[pi-sq]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f3b_text_after_the_first_gt_of_an_inline_pi_or_cdata_reads_unsure[cdata-dq]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet845_f3b_text_after_the_first_gt_of_an_inline_pi_or_cdata_reads_unsure[cdata-sq]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_unsure_inline_processing_instruction_ended_early_by_html
5 failed, 8 passed in 0.46s
```

  **The order expected `test_vet845_f3a_*` red; it is not.** All eight `f3a` cases (`para`, `atx`, `item`, `cell` x `vtab-name`, `vtab-value`)
  stay green under C5 alone, because each opener is a tag holding a vertical tab, so C7's clause (`is_tag and "\v" in construct`)
  still raises the unsure point. `f3a` therefore does not discriminate the `state != _DATA` clause: it proves the pair of clauses
  together. Supplementary run, not C5's own proof: with both clauses removed (`:745` became `if False:  # C5+C7 NEUTRALIZED`),
  `f3a` alone (`--tb=line`) went red, all eight cases:

```
FFFFFFFF                                                                 [100%]
E   AssertionError: unsure=()
    assert 'visible' == 'unsure'
test_md_hidden_2366.py:796: AssertionError: unsure=()          (x8, one per case)
FAILED ...::test_vet845_f3a_a_vertical_tab_inside_an_inline_tag_reads_unsure[para-vtab-name]
FAILED ...::test_vet845_f3a_a_vertical_tab_inside_an_inline_tag_reads_unsure[para-vtab-value]
FAILED ...::test_vet845_f3a_a_vertical_tab_inside_an_inline_tag_reads_unsure[atx-vtab-name]
FAILED ...::test_vet845_f3a_a_vertical_tab_inside_an_inline_tag_reads_unsure[atx-vtab-value]
FAILED ...::test_vet845_f3a_a_vertical_tab_inside_an_inline_tag_reads_unsure[item-vtab-name]
FAILED ...::test_vet845_f3a_a_vertical_tab_inside_an_inline_tag_reads_unsure[item-vtab-value]
FAILED ...::test_vet845_f3a_a_vertical_tab_inside_an_inline_tag_reads_unsure[cell-vtab-name]
FAILED ...::test_vet845_f3a_a_vertical_tab_inside_an_inline_tag_reads_unsure[cell-vtab-value]
8 failed in 0.32s
```

  (the `FAILED ...::` lines are shortened from the full `plugins/superheroes/lib/tests/test_md_hidden_2366.py::` prefix.)
  The `state != _DATA` clause is proven by the `f3b` and `test_unsure_inline_processing_instruction_ended_early_by_html` reds
  (5 cases); `f3a` is **unproven for that clause alone** (redundant with C7's clause; the test was not edited).
- **Restore:** inverse Edit, `:745` back to `if state != _DATA or (is_tag and "\v" in construct):`.
- **Restore receipt:** the file search returned `745:        if state != _DATA or (is_tag and "\v" in construct):`.
- **Raw green** (the three C5 node ids, all `f3a` cases included):

```
.............                                                            [100%]
13 passed in 0.34s
```

### C6: F8, a comment-state line with text after its closer reads UNSURE

- **Guarded element / axis:** `md_hidden.py:696`, `return UNSURE` in `_comment_line_state` (axis C6, vet 846 F8): GitHub shows the text after a comment closer, so that line is not HIDDEN.
- **Neutralization:** `:696` `return UNSURE` became `return HIDDEN  # C6 NEUTRALIZED`.
- **Raw red** (`test_f8_a_line_that_closes_a_comment_in_html_block_content_shows_its_tail`, `test_f8_a_closer_with_nothing_after_it_stays_hidden_and_a_bang_closer_counts`), source listings cut to the failing line:

```
FF                                                                       [100%]
>       assert _state(body, "ZQ1 --> ZQ2") == U
E       AssertionError: assert 'hidden' == 'unsure'
test_md_hidden_2366.py:1114: AssertionError
>       assert _state("<div>\n<!-- a\nZQ1 --!> ZQ2\n</div>\n\n## H\n", "ZQ1 --!> ZQ2") == U
E       AssertionError: assert 'hidden' == 'unsure'
test_md_hidden_2366.py:1123: AssertionError
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_f8_a_line_that_closes_a_comment_in_html_block_content_shows_its_tail
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_f8_a_closer_with_nothing_after_it_stays_hidden_and_a_bang_closer_counts
2 failed in 0.36s
```

- **Restore:** inverse Edit, `return HIDDEN  # C6 NEUTRALIZED` back to `return UNSURE`.
- **Restore receipt:** the file read at `:689-697` returned `if line[at + width:].strip(_ASCII_WS):` / `return UNSURE` / `return HIDDEN`.
- **Raw green** (same two node ids):

```
..                                                                       [100%]
2 passed in 0.34s
```

  The same `_comment_line_state` also serves the inline pass, so C6 would also turn the `--> c` assertions of the `test_f5_*`
  comment tests red; those were not run under C6.

### C7: a vertical tab inside a tag construct is unsure

- **Guarded element / axis:** `md_hidden.py:745`, the `(is_tag and "\v" in construct)` clause (axis C7, added in WO-4): a tag construct holding a vertical tab is an unsure point, as the earlier conservative reading (cmark takes `\v` as tag whitespace, HTML parsing does not).
- **Neutralization:** `:745` became `if state != _DATA or (False and is_tag and "\v" in construct):  # C7 NEUTRALIZED`.
- **Raw red** (`test_review_s2_r2_a_vertical_tab_inside_a_quoted_value_still_reads_unsure`), source listing cut to the failing line:

```
F                                                                        [100%]
>       assert _state('x <a title="p\vq"> y\n\n## H\n', "## H") == U
E       AssertionError: assert 'visible' == 'unsure'
test_md_hidden_2366.py:851: AssertionError
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_review_s2_r2_a_vertical_tab_inside_a_quoted_value_still_reads_unsure
1 failed in 0.35s
```

  The red is on the first assertion (`:851`); the later assertions of the test were not reached.
- **Restore:** inverse Edit, `False and ` removed and the `# C7 NEUTRALIZED` comment dropped.
- **Restore receipt:** an end-of-work file search for `NEUTRALIZED|if state != _DATA or` returned only `745:        if state != _DATA or (is_tag and "\v" in construct):` (no neutralization marker left in the file), and `git diff --stat` does not list `md_hidden.py`.
- **Raw green** (same node id):

```
.                                                                        [100%]
1 passed in 0.33s
```

### Findings for the builder (detector, not changed)

- C5 and C7 share one condition (`:745`); `test_vet845_f3a_*` is red only when both are removed, so no test in the order's list proves the `state != _DATA` clause through a vertical-tab tag. The `f3b` and `..._ended_early_by_html` tests prove it through a bogus comment.
- C1 and C3 turn the same five tests red; the tests cannot tell a skipped pass from a dropped comment-line result.

## Link-metadata rule (park ruling, option a)

The rule: a text block that holds a backtick inside a possible link range (`_link_regions`) and also a `<` adds an unsure
point at the block's first line (`_inline_pass`). The park ruling (option a, #2388's STATE) accepts that the
`linkref_div` fixture rows (`[a]: <div>` then `` `<!--` `` on the next line, a `builder` and a `bot` form) read unsure; the
order authorised one assertion change, `"linkref_div"` added to `_UNSURE_SHAPES` in `test_md_hidden_2366.py`. Each
neutralization is a targeted edit of `plugins/superheroes/lib/md_hidden.py`, undone by the inverse edit. Node ids are
relative to `plugins/superheroes/lib/tests/test_md_hidden_2366.py::`. Raw reds are cut to the assertion lines (source
listings of the parametrize decorators left out); the harness also truncated 2896 characters from the middle of the D1 red
output (inside the `displaced-span` / `fake-tag` / `angle-destination` failures), so the D1 capture below is incomplete:
it quotes only the assertion lines that were shown, plus the closing summary, which was shown whole.

### D1: the link-metadata rule adds its unsure point

- **Guarded element / axis:** `md_hidden.py:830-831`, the `sure_points.add((first, "backtick in possible link metadata
  in a block that holds raw HTML"))` guarded by `if any(r0 <= i < r1 ...)` in `_inline_pass` (axis: a backtick in link
  metadata changes cmark's backtick pairing, so the block reads unsure from its first line).
- **Neutralization:** `:830` `if any(r0 <= i < r1 for i in ticks for r0, r1 in regions):` became
  `if False and any(r0 <= i < r1 for i in ticks for r0, r1 in regions):  # D1 NEUTRALIZED` (the unsure point is never added).
- **Raw red** (the nine named node ids, one command; 9 failed; incomplete, see above):

```
FFFFFFFFF                                                                [100%]
>       assert _line_state(body, "ZQ1") != V
E       AssertionError: assert 'visible' != 'visible'
E        +  where 'visible' = _line_state('[a](<u\\>)`v>) <!-- b\nZQ1\n--> c`\n', 'ZQ1')
/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:1221: AssertionError
E        +  where 'visible' = _line_state('[bad](x `` ) `` [a](x`y) <!-- b\nZQ1\n--> c ` ``\n', 'ZQ1')
E        +  where 'visible' = _line_state('[a](x`y)\n[r]: /u\n``one\ntwo`` <!-- b\nZQ1\n--> tail `` `\n', 'ZQ1')
E        +  where 'visible' = _line_state('[a](<u)`v>) <!-- b\nZQ1\n--> c`\n', 'ZQ1')
E       assert 'visible' != 'visible'
E        +  where 'visible' = _line_state('[r]: /u "`"\n`x` <!-- b\nZQ1\n--> c `\n', 'ZQ1')
/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:1203: AssertionError
>       assert _line_state(body, "[a]") == U
E       AssertionError: assert 'visible' == 'unsure'
/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:1238: AssertionError
>       assert got == _UNSURE_SHAPES
E       AssertionError: assert {'decl_block'...256_cap', ...} == frozenset({'d...56_cap', ...})
E         Extra items in the right set:
E         'linkref_div'
/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:166: AssertionError
FAILED test_link_metadata_rule_round4_shapes_read_not_visible[escaped-angle-close]
FAILED test_link_metadata_rule_round4_shapes_read_not_visible[malformed-metadata]
FAILED test_link_metadata_rule_round4_shapes_read_not_visible[ref-def-shaped-line-in-paragraph]
FAILED test_review_s3_r3_link_metadata_that_changes_backtick_pairing_reads_unsure[displaced-span]
FAILED test_review_s3_r3_link_metadata_that_changes_backtick_pairing_reads_unsure[fake-tag]
FAILED test_review_s3_r3_link_metadata_that_changes_backtick_pairing_reads_unsure[angle-destination]
FAILED test_review_s3_r3_link_metadata_that_changes_backtick_pairing_reads_unsure[reference-definition]
FAILED test_link_metadata_rule_puts_the_unsure_point_at_the_blocks_first_line
FAILED test_oracle_rows_with_an_unsure_point_are_the_expected_ones
9 failed in 0.65s
```

  (In the summary lines the path prefix `plugins/superheroes/lib/tests/test_md_hidden_2366.py::` is dropped here; the run
  printed it. The `displaced-span` and `fake-tag` assertion lines were not shown, being in or near the truncated span;
  the summary lists both as FAILED.) All nine named tests went red; none stayed green.
- **Restore:** inverse Edit, `False and ` removed and the `# D1 NEUTRALIZED` comment dropped.
- **Restore receipt:** a file search for `NEUTRALIZED|if any\(r0 <= i` returned only
  `830:        if any(r0 <= i < r1 for i in ticks for r0, r1 in regions):` (no marker left).
- **Raw green** (same nine node ids):

```
.........                                                                [100%]
9 passed in 0.59s
```

### D2: the escaped `>` widening in `_destination_end`

- **Guarded element / axis:** `md_hidden.py:670`, `j += 2 if text[j] == "\\" else 1` in `_destination_end` (axis: an
  angle-bracket destination ends at the first `>` that is not backslash-escaped; a wider range is safe, a narrower one is not).
- **Neutralization:** `:670` became `j += 1  # D2 NEUTRALIZED` (the angle destination ends at the first `>` again).
- **Raw red** (`test_link_metadata_rule_round4_shapes_read_not_visible[escaped-angle-close]`), source listing cut to the
  failing line:

```
F                                                                        [100%]
>       assert _line_state(body, "ZQ1") != V
E       AssertionError: assert 'visible' != 'visible'
E        +  where 'visible' = _line_state('[a](<u\\>)`v>) <!-- b\nZQ1\n--> c`\n', 'ZQ1')
/home/user/wt-2366/plugins/superheroes/lib/tests/test_md_hidden_2366.py:1221: AssertionError
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_link_metadata_rule_round4_shapes_read_not_visible[escaped-angle-close]
1 failed in 0.60s
```

- **Restore:** inverse Edit, `j += 1  # D2 NEUTRALIZED` back to `j += 2 if text[j] == "\\" else 1`.
- **Restore receipt:** a file search for `NEUTRALIZED|j \+= 2 if text\[j\]` returned only
  `670:            j += 2 if text[j] == "\\" else 1` (no marker left).
- **Raw green** (same node id):

```
.                                                                        [100%]
1 passed in 0.31s
```

  The order names only `[escaped-angle-close]` red for D2; no other node was run under D2.

**Orchestrator re-run (D1).** The orchestrator applied the same D1 neutralization in a separate probe worktree at
`983b4bed` with this file's `test_md_hidden_2366.py`, ran the whole file, and saw `11 failed, 474 passed, 28 skipped`:
the nine named node ids, plus `test_review_s3_a_backtick_in_a_link_destination_opens_no_code_span` and
`test_review_s3_r2_a_quoted_title_parenthesis_does_not_end_the_link_check`, which also rest on the rule. The probe was
restored by the inverse edit.

## Table ruling and vet-849 amendment

The rulings: the advisor's TABLE RULING (parse each GFM table cell on its own, as cmark-gfm does) and the vet-849
AMENDMENT (a text block whose first line starts with `[` and holds `]:` reads unsure; `[ZQ1]: /u` becomes a passing
case), both in issue #2388's STATE, plus the cmark-shaped `_destination_end`. Each neutralization is a targeted edit of
`plugins/superheroes/lib/md_hidden.py`, undone by the inverse edit. Node ids are relative to
`plugins/superheroes/lib/tests/`. Command prefix (worktree root):
`scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest <node ids> -q`. Captures are verbatim except
uv's `UV_NATIVE_TLS` deprecation warning line, dropped. Nothing was redacted. Guarded-element set: F1, F2, F3.

### F1: the per-cell inline pass

- **Guarded element / axis:** `md_hidden.py:836`, `if header is None:` in `_inline_pass` (axis: a table's cells are
  parsed one at a time, so a tag opened in one cell cannot absorb a raw comment opener in the next).
- **Neutralization:** `if header is None:` became `if True:` (the table is parsed joined).
- **Raw red** (node ids `test_md_hidden_review_s1_table_raw_boundaries.py::test_cross_cell_tag_cannot_mask_a_raw_comment_opener`
  and `test_md_hidden_review_w2u1_cells.py::test_a_tag_cannot_hide_raw_html_in_another_table_cell`), source listing cut to
  the failing assertion lines:

```
FF                                                                       [100%]
>           assert rendering.state_at(body.index("## ZQ1")) in (md.HIDDEN, md.UNSURE), (
E           AssertionError: ('"', ((0, 'visible'), (10, 'visible'), (20, 'visible'), (55, 'visible'), (56, 'visible')), ())
E           assert 'visible' in ('hidden', 'unsure')
test_md_hidden_review_s1_table_raw_boundaries.py:22: AssertionError
>       assert rendering.state_at(body.index("## ZQ1")) in (md.HIDDEN, md.UNSURE), (
E       AssertionError: (((0, 'visible'), (14, 'visible'), (28, 'visible'), (63, 'visible'), (64, 'visible')), ())
E       assert 'visible' in ('hidden', 'unsure')
test_md_hidden_review_w2u1_cells.py:22: AssertionError
FAILED plugins/superheroes/lib/tests/test_md_hidden_review_s1_table_raw_boundaries.py::test_cross_cell_tag_cannot_mask_a_raw_comment_opener
FAILED plugins/superheroes/lib/tests/test_md_hidden_review_w2u1_cells.py::test_a_tag_cannot_hide_raw_html_in_another_table_cell
2 failed in 0.33s
```

- **Restore:** inverse Edit, `if True:` back to `if header is None:`.
- **Restore receipt:** a file search for `if header is None:|if True:` returned only `836:    if header is None:`.
- **Raw green** (same two node ids):

```
..                                                                       [100%]
2 passed in 0.17s
```

### F2: the reference-definition rule

- **Guarded element / axis:** `md_hidden.py:848`, `if lines and _REF_DEF_START.match(lines[0]) and "]:" in joined:` in
  `_inline_pass` (axis: a block whose first line starts with `[` and holds `]:` reads unsure from its first line).
- **Neutralization:** that line became `    if False:`.
- **Raw red** (one command: the three node ids `test_md_hidden_2366.py::test_amendment_link_reference_definition_lines_read_unsure`,
  `test_md_hidden_2366.py::test_corpus_no_line_github_hides_reads_visible`,
  `test_md_hidden_2366.py::test_unsure_footnote_definition_inside_a_quote_and_not_a_link_label`, plus the whole files
  `test_md_hidden_review_s1_reference_extents.py` and `test_md_hidden_review_w2u1_references.py`). The harness truncated
  10132 characters from the middle of the output (inside the `test_unsure_footnote_definition_inside_a_quote_and_not_a_link_label`
  and `s1_reference_extents` failures), so the capture is **incomplete**: below are the assertion lines that were shown, and
  the closing summary, which was shown whole:

```
FFFFFFFFFFFFF                                                            [100%]
>       assert _line_state(body, needle) == U
E       AssertionError: assert 'visible' == 'unsure'
test_md_hidden_2366.py:1243: AssertionError
E       AssertionError: 1 fail-open (body, line index, line):
E         ('x\n\n[ZQ1]: /u\n\n## ZQ2\n', 2, '[ZQ1]: /u\n')
test_md_hidden_2366.py:940: AssertionError
E       AssertionError: ('[r\nx]: /u`v\n', ((0, 'visible'), (3, 'visible'), (12, 'visible'), (29, 'visible'), (33, 'visible')), ())
test_md_hidden_review_w2u1_references.py:25: AssertionError
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_amendment_link_reference_definition_lines_read_unsure[titled-definition]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_amendment_link_reference_definition_lines_read_unsure[label-with-spaces]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_amendment_link_reference_definition_lines_read_unsure[bare-definition]
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_corpus_no_line_github_hides_reads_visible
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_unsure_footnote_definition_inside_a_quote_and_not_a_link_label
FAILED plugins/superheroes/lib/tests/test_md_hidden_review_s1_reference_extents.py::test_consumed_reference_backtick_cannot_mask_a_comment[label]
FAILED plugins/superheroes/lib/tests/test_md_hidden_review_s1_reference_extents.py::test_consumed_reference_backtick_cannot_mask_a_comment[third-line-title]
FAILED plugins/superheroes/lib/tests/test_md_hidden_review_s1_reference_extents.py::test_consumed_reference_backtick_cannot_mask_a_comment[escaped-label]
FAILED plugins/superheroes/lib/tests/test_md_hidden_review_s1_reference_extents.py::test_consumed_reference_backtick_cannot_mask_a_comment[multiline-label]
FAILED plugins/superheroes/lib/tests/test_md_hidden_review_w2u1_references.py::test_reference_metadata_cannot_mask_an_inline_comment[label-backtick]
FAILED plugins/superheroes/lib/tests/test_md_hidden_review_w2u1_references.py::test_reference_metadata_cannot_mask_an_inline_comment[escaped-bracket-label]
FAILED plugins/superheroes/lib/tests/test_md_hidden_review_w2u1_references.py::test_reference_metadata_cannot_mask_an_inline_comment[multiline-label]
FAILED plugins/superheroes/lib/tests/test_md_hidden_review_w2u1_references.py::test_reference_metadata_cannot_mask_an_inline_comment[multiline-title]
13 failed in 0.67s
```

  (The `:1243` assertion was shown for all three parametrized cases; the `:25` assertion was shown for the
  `multiline-label` and `multiline-title` cases.) All three named test functions went red (five items: three parametrized cases, the corpus test, the footnote test). Every
  reference break-it test in the two whole files went red as well: the summary has `13 failed` and no passed item, so none
  of the four `s1_reference_extents` cases nor the four `w2u1_references` cases stayed green; the link-metadata rule
  (`_link_regions` through `_destination_end`) does not cover any of them on its own.
- **Restore:** inverse Edit, `if False:` back to the `_REF_DEF_START` line.
- **Restore receipt:** a file search for `_REF_DEF_START.match|^    if False:` returned only
  `848:    if lines and _REF_DEF_START.match(lines[0]) and "]:" in joined:`.
- **Raw green** (same command):

```
.............                                                            [100%]
13 passed in 0.75s
```

### F3: the bare destination's parenthesis count

- **Guarded element / axis:** `md_hidden.py:687`, `while j < n and text[j] not in " \t\n":` in `_destination_end` (axis: a
  bare destination runs to whitespace, so a quote does not stop the parenthesis count).
- **Neutralization:** it became `while j < n and text[j] not in " \t\n\"'":`.
- **Raw red** (`test_md_hidden_2366.py::test_destination_quotes_do_not_stop_the_parenthesis_count`):

```
F                                                                        [100%]
>       assert _line_state('[a](u"(x")y`z) <!-- b\nZQ1\n--> c`\n', "ZQ1") != V
E       assert 'visible' != 'visible'
E        +  where 'visible' = _line_state('[a](u"(x")y`z) <!-- b\nZQ1\n--> c`\n', 'ZQ1')
test_md_hidden_2366.py:1251: AssertionError
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_destination_quotes_do_not_stop_the_parenthesis_count
1 failed in 0.32s
```

- **Restore:** inverse Edit, the `\"'` removed.
- **Restore receipt:** a file search for `while j < n and text\[j\] not in` returned only
  `687:        while j < n and text[j] not in " \t\n":`.
- **Raw green** (same node id):

```
.                                                                        [100%]
1 passed in 0.31s
```

**Orchestrator re-run (F1).** The orchestrator applied the same F1 neutralization in a separate probe worktree holding a
byte-identical `md_hidden.py` and the same break-it files, ran the two table break-it files whole, and saw `2 failed, 1
passed` (the two named nodes red; the paragraph control green). The probe was restored by the inverse edit and compared
byte-identical with the build tree's file.

## Vet 851 fix leg

The fix leg (work order WO-7, issue #2388): V851-1..5 and the per-line hiding rule, applied to
`plugins/superheroes/lib/md_hidden.py` with `git apply` of the builder's diff; the new fixture
`fixtures/md_hidden_github_renders_vet851.json` (215 bodies, GitHub's renders by `POST /markdown`) is checked by the same
fail-open judge in `test_vet851_corpus_no_line_github_hides_reads_visible`. Each neutralization is a targeted edit of
`md_hidden.py`, undone by the inverse edit. Node ids are relative to `plugins/superheroes/lib/tests/test_md_hidden_2366.py::`.
Command prefix (worktree root): `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest <node ids> -q`.
Captures are verbatim except uv's `UV_NATIVE_TLS` deprecation warning line (dropped) and the source listing of the test
bodies and the `Use -v to get more diff` lines (dropped; the assertion lines are kept). Nothing was redacted.
Guarded-element set: H1, H2, H3, H4, H5, H6. Result: H1, H3, H4, H5 and H6 bite; H2 is **unproven** (its tests stay green).

### H1: V851-1, a delimiter row needs a `|` or a `:`

- **Guarded element / axis:** `md_hidden.py:592`, `("|" in rest or ":" in rest)` in `_add_text_line` (axis: a dash-only line
  is a setext underline, not a table delimiter row).
- **Neutralization:** `("|" in rest or ":" in rest)` became `"|" in rest`.
- **Raw red** (`test_vet851_1_a_delimiter_row_without_a_pipe_makes_a_table` and `test_vet851_corpus_no_line_github_hides_reads_visible`):

```
FF                                                                       [100%]
E       AssertionError: fail-open lines: [('a\n:--\n` <? > <!-- ?>\nx `\n\n## ZQ1\n', 5, '## ZQ1\n')]
test_md_hidden_2366.py:1300: AssertionError
E       AssertionError: 6 fail-open (body, line index, line):
E         ('a\n:--\n` <? > <!-- ?>\nx `\n\n## ZQ1\n', 5, '## ZQ1\n')
E         ('ZQ0\n:-:\n` <? > <!-- ?>\nZQ2 `\n\n## ZQ1\n', 3, 'ZQ2 `\n')
E         ('ZQ0\n:-:\n` <? > <!-- ?>\nZQ2 `\n\n## ZQ1\n', 5, '## ZQ1\n')
E         ('| a\n:--\n` <? > <!-- ?>\nx `\n\n## ZQ1\n', 5, '## ZQ1\n')
E         ('> a\n> :--\n> ` <? > <!-- ?>\n> x `\n\n## ZQ1\n', 5, '## ZQ1\n')
E         ('- a\n  :--\n  ` <? > <!-- ?>\n  x `\n\n## ZQ1\n', 5, '## ZQ1\n')
test_md_hidden_2366.py:1311: AssertionError
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet851_1_a_delimiter_row_without_a_pipe_makes_a_table
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet851_corpus_no_line_github_hides_reads_visible
2 failed in 1.31s
```

- **Restore:** inverse Edit, `"|" in rest` back to `("|" in rest or ":" in rest)`.
- **Restore receipt:** a file search for `"\|" in rest` returned only `592:        if (matched and block.kind == "para" and not block.table and block.lines and ("|" in rest or ":" in rest)`.
- **Raw green** (same two node ids):

```
..                                                                       [100%]
2 passed in 0.43s
```

### H2: V851-2, a lone `|` holds 0 cells

- **Guarded element / axis:** `md_hidden.py:745`, `if text == "|":` in `_cell_count` (axis: a lone pipe is no table header).
- **Neutralization:** `if text == "|":` became `if False:`.
- **Raw run** (`test_vet851_2_a_lone_pipe_header_makes_no_table` and `test_vet851_corpus_no_line_github_hides_reads_visible`),
  **not red**:

```
..                                                                       [100%]
2 passed in 0.42s
```

- **Unproven.** Both named tests stay green under the neutralization, so they do not detect the removal of this guard;
  per the order the tests were not edited. Reason (read off `md_hidden.py`, not measured by a further run): without the
  guard, `|` counts 1 cell, so `|` plus `|-|` still makes a table, but the next row `x <!-- a | b` then holds 2 cells, more
  than the header's 1, and the V851-3 rule (`md_hidden.py:432`, H3) reads it unsure; H2's bodies are therefore also covered by
  H3. The guard's own discrimination (a lone pipe makes no table) is observed by no test in this file.
  `md._cell_count("|")` is not asserted anywhere.
- **Restore:** inverse Edit, `if False:` back to `if text == "|":`.
- **Restore receipt:** a file search for `if text == "\|":|if False:` returned only `745:    if text == "|":  # vet 851: a lone pipe holds no cells, so cmark-gfm makes no table`.
- **Raw green** (same two node ids):

```
..                                                                       [100%]
2 passed in 0.44s
```

### H3: V851-3, a table row with more cells than its header reads unsure

- **Guarded element / axis:** `md_hidden.py:432`, `elif _cell_count(rest) > _cell_count(tip.lines[tip.header]):` (axis: a row
  wider than the header is unsure).
- **Neutralization:** that condition became `elif False:`.
- **Raw red** (`test_vet851_3_cells_past_the_header_count_read_unsure` and `test_vet851_corpus_no_line_github_hides_reads_visible`):

```
FF                                                                       [100%]
E       AssertionError: fail-open lines: [('| a |\n|---|\n| | ZQ1 |\n| ZQ2 |\n\n## ZQ3\n', 2, '| | ZQ1 |\n')]
test_md_hidden_2366.py:1300: AssertionError
E       AssertionError: 6 fail-open (body, line index, line):
E         ('||\n|-|\nx <!-- a | ZQ1 --> y\n\n## ZQ2\n', 2, 'x <!-- a | ZQ1 --> y\n')
E         ('a \\|\n|-|\nx <!-- a | ZQ1 --> y\n\n## ZQ2\n', 2, 'x <!-- a | ZQ1 --> y\n')
E         ('a \\\\|\n|-|\nx <!-- a | ZQ1 --> y\n\n## ZQ2\n', 2, 'x <!-- a | ZQ1 --> y\n')
E         ('a\n-:\nx <!-- a | ZQ1 --> y\n\n## ZQ2\n', 2, 'x <!-- a | ZQ1 --> y\n')
E         ('a\n :-- \nx <!-- a | ZQ1 --> y\n\n## ZQ2\n', 2, 'x <!-- a | ZQ1 --> y\n')
E         ('| a |\n|---|\n| | ZQ1 |\n| ZQ2 |\n\n## ZQ3\n', 2, '| | ZQ1 |\n')
test_md_hidden_2366.py:1311: AssertionError
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet851_3_cells_past_the_header_count_read_unsure
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet851_corpus_no_line_github_hides_reads_visible
2 failed in 0.37s
```

- **Restore:** inverse Edit, `elif False:` back to the `_cell_count` comparison.
- **Restore receipt:** a file search for `elif False:|elif _cell_count` returned only `432:        elif _cell_count(rest) > _cell_count(tip.lines[tip.header]):`.
- **Raw green** (same two node ids):

```
..                                                                       [100%]
2 passed in 0.34s
```

### H4: V851-4, an image's alt range is link metadata

- **Guarded element / axis:** `md_hidden.py:674`, `if not (at and text[at - 1] == "<"):` (axis: the `[` of an image
  (`![`) opens link metadata like any link's).
- **Neutralization:** that condition became `if False:`.
- **Raw red** (`test_vet851_4_image_alt_text_across_lines_reads_not_visible` and `test_vet851_corpus_no_line_github_hides_reads_visible`):

```
FF                                                                       [100%]
E       AssertionError: fail-open lines: [('x ![ZQ0\nZQ1\nZQ2](https://example.com/a.png) y\n\n## ZQ3\n', 0, 'x ![ZQ0\n'), ('x ![ZQ0\nZQ1\nZQ2](https://example.com/a.png) y\n\n## ZQ3\n', 1, 'ZQ1\n'), ('x ![ZQ0\nZQ1\nZQ2](https://example.com/a.png) y\n\n## ZQ3\n', 2, 'ZQ2](https://example.com/a.png) y\n')]
test_md_hidden_2366.py:1300: AssertionError
E       AssertionError: 7 fail-open (body, line index, line):
E         ('x ![ZQ0\nZQ1\nZQ2](https://example.com/a.png) y\n\n## ZQ3\n', 0, 'x ![ZQ0\n')
E         ('x ![ZQ0\nZQ1\nZQ2](https://example.com/a.png) y\n\n## ZQ3\n', 1, 'ZQ1\n')
E         ('x ![ZQ0\nZQ1\nZQ2](https://example.com/a.png) y\n\n## ZQ3\n', 2, 'ZQ2](https://example.com/a.png) y\n')
E         ('![ZQ1\nZQ2][r]\n\n## ZQ3\n\n[r]: https://example.com/a.png\n', 0, '![ZQ1\n')
E         ('![ZQ1\nZQ2][r]\n\n## ZQ3\n\n[r]: https://example.com/a.png\n', 1, 'ZQ2][r]\n')
E         ('Leftovers:\n![F-1\nZQ1 the retry loop never backs off](x.png)\n\n## ZQ2\n', 2, 'ZQ1 the retry loop never backs off](x.png)\n')
E         ('- ![F-1\n  ZQ1 the retry loop](https://example.com/a.png)\n\n## ZQ2\n', 1, '  ZQ1 the retry loop](https://example.com/a.png)\n')
test_md_hidden_2366.py:1311: AssertionError
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet851_4_image_alt_text_across_lines_reads_not_visible
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet851_corpus_no_line_github_hides_reads_visible
2 failed in 0.41s
```

- **Restore:** inverse Edit, `if False:` back to `if not (at and text[at - 1] == "<"):`.
- **Restore receipt:** a file search for `if False:|if not \(at and` returned only `674:        if not (at and text[at - 1] == "<"):`.
- **Raw green** (same two node ids):

```
..                                                                       [100%]
2 passed in 0.49s
```

### H5: V851-5, `<video` and `</video` read unsure

- **Guarded element / axis:** `md_hidden.py:608`, `if _DROPPED_TAGS.search(rest):` in `_check_line` (axis: a tag whose
  content GitHub drops reads unsure; `video` is in the set).
- **Neutralization:** that condition became `if False:`.
- **Raw red** (`test_vet851_5_video_reads_unsure` and `test_vet851_corpus_no_line_github_hides_reads_visible`). The two
  long entries for the 34-paragraph body are cut after their first 60 characters (the body is the corpus entry beginning
  `p1 <video>ZQ1</video> q`; elided text marked `[...]`):

```
FF                                                                       [100%]
E       AssertionError: fail-open lines: [('<video>\nZQ1\n</video>\n\n## ZQ2\n', 1, 'ZQ1\n')]
test_md_hidden_2366.py:1300: AssertionError
E       AssertionError: 6 fail-open (body, line index, line):
E         ('x <object>ZQ1</object> <canvas>ZQ2</canvas> <video>ZQ3</video> y\n\n## ZQ4\n', 0, 'x <object>ZQ1</object> <canvas>ZQ2</canvas> <video>ZQ3</video> y\n')
E         ('<video>\nZQ1\n</video>\n\n## ZQ2\n', 1, 'ZQ1\n')
E         ('x <video>\nZQ1\n</video> y\n\n## ZQ2\n', 1, 'ZQ1\n')
E         ('p1 <video>ZQ1</video> q\n\np2 <audio>ZQ2</audio> q\n\n[...]', 0, 'p1 <video>ZQ1</video> q\n')
E         ('p1 <video>ZQ1</video> q\n\np2 <audio>ZQ2</audio> q\n\n[...]', 69, 'ZQ900\n')
E         ('p1 <video>ZQ1</video> q\n\np2 <audio>ZQ2</audio> q\n\n[...]', 73, '<video>ZQ901</video>\n')
test_md_hidden_2366.py:1311: AssertionError
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet851_5_video_reads_unsure
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet851_corpus_no_line_github_hides_reads_visible
2 failed in 0.39s
```

- **Restore:** inverse Edit, `if False:` back to `if _DROPPED_TAGS.search(rest):`.
- **Restore receipt:** a file search for `if False:|_DROPPED_TAGS\.search` returned only `608:        if _DROPPED_TAGS.search(rest):`.
- **Raw green** (same two node ids):

```
..                                                                       [100%]
2 passed in 0.34s
```

### H6: the per-line hiding rule

- **Guarded element / axis:** `md_hidden.py:922`, `if not atx and not is_tag and _HIDING_OPENER.sub(...)` (axis: a line
  where an inline comment, PI, CDATA or declaration hides text reads unsure, on that line only; ATX headings are exempt).
- **Neutralization:** `if not atx and not is_tag and` became `if False and not atx and not is_tag and`.
- **Raw red** (`test_vet851_2_a_lone_pipe_header_makes_no_table`, `test_f5_a_comment_across_paragraph_lines_hides_the_lines_inside`
  and `test_vet851_corpus_no_line_github_hides_reads_visible`):

```
FFF                                                                      [100%]
E       AssertionError: fail-open lines: [(' | \n|-|\nx <!-- a | ZQ1 --> y\n\n## ZQ2\n', 2, 'x <!-- a | ZQ1 --> y\n')]
test_md_hidden_2366.py:1300: AssertionError
E       AssertionError: assert 'visible' == 'unsure'
E         - unsure
E         + visible
test_md_hidden_2366.py:973: AssertionError
E       AssertionError: 4 fail-open (body, line index, line):
E         ('|\n|-|\nx <!-- a | ZQ1 --> y\n\n## ZQ2\n', 2, 'x <!-- a | ZQ1 --> y\n')
E         (' | \n|-|\nx <!-- a | ZQ1 --> y\n\n## ZQ2\n', 2, 'x <!-- a | ZQ1 --> y\n')
E         ('`a|b`\n|-|\nx <!-- a | ZQ1 --> y\n\n## ZQ2\n', 2, 'x <!-- a | ZQ1 --> y\n')
E         ('a | b\n-\t| -\nx <!-- a | ZQ1 --> y\n\n## ZQ2\n', 2, 'x <!-- a | ZQ1 --> y\n')
test_md_hidden_2366.py:1311: AssertionError
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet851_2_a_lone_pipe_header_makes_no_table
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_f5_a_comment_across_paragraph_lines_hides_the_lines_inside
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet851_corpus_no_line_github_hides_reads_visible
3 failed in 0.40s
```

  (In `test_vet851_2_a_lone_pipe_header_makes_no_table` the first body, whose comment spans lines, passed; the second,
  one-line-comment body failed, as the order expected.)
- **Restore:** inverse Edit, `if False and not atx and not is_tag and` back to `if not atx and not is_tag and`.
- **Restore receipt:** a file search for `False and|if not atx and not is_tag and` returned only `922:        if not atx and not is_tag and _HIDING_OPENER.sub("", pieces[0]).strip(_ASCII_WS + "-?]>"):`.
- **Raw green** (same three node ids):

```
...                                                                      [100%]
3 passed in 0.36s
```

**Orchestrator notes (H2, E3).** H2 stays unproven for a reason the orchestrator checked: with the lone-pipe rule
neutralized in a separate probe worktree (byte-identical `md_hidden.py`), a lone `|` header counts one cell, so the next
row's two cells trip V851-3's more-cells-than-header rule and the block reads unsure from that row. The orchestrator ran
every lone-pipe body in `md_hidden_github_renders_vet851.json` under the neutralization: none reads a GitHub-hidden
sentinel visible, so V851-3 masks V851-2 on every rendered shape. The rule stays, since it matches cmark-gfm. The probe
was restored and compared byte-identical. E3's `git apply --reverse --check` was refused to the implementer by the
permission layer; the orchestrator ran it on the build tree after the last restore: exit 0.

## Vet 854 fix leg

The fix leg (work order WO-8, issue #2388): V854-1, V854-2 and V854-4, applied to `plugins/superheroes/lib/md_hidden.py`
with `git apply` of the builder's diff; the new fixture `fixtures/md_hidden_github_renders_vet854.json` (44 renders, GitHub's
renders taken by the advisor) is checked by the same fail-open judge in
`test_vet854_corpus_no_line_github_hides_reads_visible`. Each neutralization is a targeted edit of `md_hidden.py`, undone by
the inverse edit. Node ids are relative to `plugins/superheroes/lib/tests/test_md_hidden_2366.py::`.
Command prefix (worktree root): `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest <node ids> -q`.
Captures are verbatim except uv's `UV_NATIVE_TLS` deprecation warning line (dropped) and the source listing of the test
bodies and the `Use -v to get more diff` lines (dropped; the assertion lines are kept). Nothing was redacted.
Guarded-element set: J1, J2, J3, J4, J5, J6. Result: all six bite. Each of J3, J4 and J5 stops at the first failing id of
`test_vet854_4_attribute_and_title_text_reads_unsure` (the test loops over its ids and stops at the first assertion), so
one red per neutralization names one id, not every id the element covers.

### J1: V854-1, a text block with `![` and a later `]` reads unsure from its first line

- **Guarded element / axis:** `md_hidden.py:940`, `if nl >= 0 and "]" in joined[nl:]:` (axis: an image description that may
  close on a later line puts an unsure point at the block's first line).
- **Neutralization:** that condition became `if False:`.
- **Raw red** (`test_vet854_1_an_image_closing_on_a_later_line_reads_unsure` and `test_vet854_corpus_no_line_github_hides_reads_visible`):

```
FF                                                                       [100%]
E           AssertionError: a1_nested_dest_bracket
E           assert [('![a [b](c]...om/x.png)\n')] == []
E             Left contains one more item: ('![a [b](c]d)\nZQ1](https://example.com/x.png)\n\n## ZQ2\n', 1, 'ZQ1](https://example.com/x.png)\n')
test_md_hidden_2366.py:1458: AssertionError
E       AssertionError: 7 fail-open (body, line index, line):
E         ('![a [b](c]d)\nZQ1](https://example.com/x.png)\n\n## ZQ2\n', 1, 'ZQ1](https://example.com/x.png)\n')
E         ('![a [b](c "]")\nZQ1](https://example.com/x.png)\n\n## ZQ2\n', 1, 'ZQ1](https://example.com/x.png)\n')
E         ('![a [b](<c]>)\nZQ1](https://example.com/x.png)\n\n## ZQ2\n', 1, 'ZQ1](https://example.com/x.png)\n')
E         ('- ![a [b](c]d)\n  ZQ1](https://example.com/x.png)\n\n## ZQ2\n', 1, '  ZQ1](https://example.com/x.png)\n')
E         ("![a [b](c 'x]y')\nZQ1](https://example.com/x.png)\n\n## ZQ2\n", 1, 'ZQ1](https://example.com/x.png)\n')
E         ('![a ![b](c]d)\nZQ1](https://example.com/x.png)\n\n## ZQ2\n', 1, 'ZQ1](https://example.com/x.png)\n')
E         ('![a [b](c (]))\nZQ1](https://example.com/x.png)\n\n## ZQ2\n', 1, 'ZQ1](https://example.com/x.png)\n')
test_md_hidden_2366.py:1445: AssertionError
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet854_1_an_image_closing_on_a_later_line_reads_unsure
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet854_corpus_no_line_github_hides_reads_visible
2 failed in 0.49s
```

- **Restore:** inverse Edit, `if False:` back to `if nl >= 0 and "]" in joined[nl:]:`.
- **Restore receipt:** a file search for `if nl >= 0 and "\]" in joined|^\s+if False:` returned only `940:        if nl >= 0 and "]" in joined[nl:]:`.
- **Raw green** (same two node ids):

```
..                                                                       [100%]
2 passed in 0.53s
```

### J2: V854-2, `</` followed by anything but an ASCII letter or `>` is a bogus comment in an HTML block

- **Guarded element / axis:** `md_hidden.py:868`, `_BLOCK_HIDING`, the alternative `<(?:[?!]|/(?![A-Za-z>]))` (axis: a block
  end-tag-shaped bogus comment hides its line).
- **Neutralization:** `<(?:[?!]|/(?![A-Za-z>]))` became `<(?:[?!])`.
- **Raw red** (`test_vet854_2_a_block_end_tag_bogus_comment_hides_its_text`):

```
F                                                                        [100%]
E           AssertionError: h1_block_endtag_bogus
E           assert [('<div>\n</ ... '</ ZQ1>\n')] == []
E             Left contains one more item: ('<div>\n</ ZQ1>\n</div>\n\n## ZQ2\n', 1, '</ ZQ1>\n')
test_md_hidden_2366.py:1467: AssertionError
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet854_2_a_block_end_tag_bogus_comment_hides_its_text
1 failed in 0.48s
```

- **Restore:** inverse Edit, `<(?:[?!])` back to `<(?:[?!]|/(?![A-Za-z>]))`.
- **Restore receipt:** a file search for `^_BLOCK_HIDING = ` returned `868:_BLOCK_HIDING = re.compile(r"<!--(?:>|->|.*?(?:-->|--!>|\Z))|<(?:[?!]|/(?![A-Za-z>]))[^>]*(?:>|\Z)", re.S)`.
- **Raw green** (same node id):

```
.                                                                        [100%]
1 passed in 0.59s
```

### J3: V854-4, an HTML-block tag with an attribute value reads unsure

- **Guarded element / axis:** `md_hidden.py:1042`, `if raw[-1] == VISIBLE and _ATTR_VALUE.search(html_line[i]):` (axis: an
  HTML-block line holding a tag with an attribute value reads unsure, on that line only).
- **Neutralization:** that condition became `if False:`.
- **Raw red** (`test_vet854_4_attribute_and_title_text_reads_unsure`):

```
F                                                                        [100%]
E           AssertionError: b2_img_alt_block
E           assert [('<img src="...lt="ZQ1">\n')] == []
E             Left contains one more item: ('<img src="https://example.com/x.png" alt="ZQ1">\n\n## ZQ2\n', 0, '<img src="https://example.com/x.png" alt="ZQ1">\n')
test_md_hidden_2366.py:1479: AssertionError
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet854_4_attribute_and_title_text_reads_unsure
1 failed in 0.47s
```

- **Restore:** inverse Edit, `if False:` back to `if raw[-1] == VISIBLE and _ATTR_VALUE.search(html_line[i]):`.
- **Restore receipt:** a file search for `if raw\[-1\] == VISIBLE and _ATTR_VALUE|^\s+if False:` returned only `1042:                if raw[-1] == VISIBLE and _ATTR_VALUE.search(html_line[i]):`.
- **Raw green** (same node id):

```
.                                                                        [100%]
1 passed in 0.27s
```

### J4: V854-4, an inline tag with an attribute value reads unsure (ATX headings exempt)

- **Guarded element / axis:** `md_hidden.py:985`, `if not atx and is_tag and "=" in construct:` (axis: an inline tag holding an
  attribute value puts its lines in the unsure set).
- **Neutralization:** that condition became `if False:`.
- **Raw red** (`test_vet854_4_attribute_and_title_text_reads_unsure`):

```
F                                                                        [100%]
E           AssertionError: b1_span_title_alone
E           assert [('<span titl..."></span>\n')] == []
E             Left contains one more item: ('<span title="ZQ1"></span>\n\n## ZQ2\n', 0, '<span title="ZQ1"></span>\n')
test_md_hidden_2366.py:1479: AssertionError
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet854_4_attribute_and_title_text_reads_unsure
1 failed in 0.35s
```

- **Restore:** inverse Edit, `if False:` back to `if not atx and is_tag and "=" in construct:`.
- **Restore receipt:** a file search for `if not atx and is_tag and "=" in construct:|^\s+if False:` returned only `985:        if not atx and is_tag and "=" in construct:`.
- **Raw green** (same node id):

```
.                                                                        [100%]
1 passed in 0.32s
```

### J5: V854-4, a possible link or image title reads unsure

- **Guarded element / axis:** `md_hidden.py:945`, `if _TITLE_START.search(joined[r0:r1]):` (axis: the lines a possible link or
  image title may span read unsure).
- **Neutralization:** that condition became `if False:`.
- **Raw red** (`test_vet854_4_attribute_and_title_text_reads_unsure`):

```
F                                                                        [100%]
E           AssertionError: b3_empty_link_title
E           assert [('[](https:/...om "ZQ1")\n')] == []
E             Left contains one more item: ('[](https://example.com "ZQ1")\n\n## ZQ2\n', 0, '[](https://example.com "ZQ1")\n')
test_md_hidden_2366.py:1479: AssertionError
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet854_4_attribute_and_title_text_reads_unsure
1 failed in 0.50s
```

- **Restore:** inverse Edit, `if False:` back to `if _TITLE_START.search(joined[r0:r1]):`.
- **Restore receipt:** a file search for `if _TITLE_START.search\(joined\[r0:r1\]\):|^\s+if False:` returned only `945:        if _TITLE_START.search(joined[r0:r1]):`.
- **Raw green** (same node id):

```
.                                                                        [100%]
1 passed in 0.31s
```

### J6: the lone-pipe rule (vet 851 H2 re-proven)

- **Guarded element / axis:** `md_hidden.py:778`, `if text == "|":` in `_cell_count` (axis: a lone pipe holds no cells, so a
  lone-pipe header makes no table). The vet 851 H2 proof was unproven because V851-3 masked it; the f1 and f2 renders hold no
  pipe in their rows, so V851-3 cannot.
- **Neutralization:** `if text == "|":` became `if False:`.
- **Raw red** (`test_vet854_h2_a_lone_pipe_header_with_pipeless_rows`):

```
F                                                                        [100%]
E           AssertionError: f1_h2_lone_pipe_no_row_pipes
E           assert [('|\n|-|\nx ..., 3, 'ZQ1\n')] == []
E             Left contains one more item: ('|\n|-|\nx <!-- a b\nZQ1\n-->\n\n## ZQ2\n', 3, 'ZQ1\n')
test_md_hidden_2366.py:1488: AssertionError
FAILED plugins/superheroes/lib/tests/test_md_hidden_2366.py::test_vet854_h2_a_lone_pipe_header_with_pipeless_rows
1 failed in 0.35s
```

- **Restore:** inverse Edit, `if False:` back to `if text == "|":`.
- **Restore receipt:** a file search for `if text == "\|":|if False:` returned only `778:    if text == "|":  # vet 851: a lone pipe holds no cells, so cmark-gfm makes no table`.
- **Raw green** (same node id):

```
.                                                                        [100%]
1 passed in 0.38s
```

**Orchestrator re-run (J1, E3).** The orchestrator applied J1's neutralization in a separate probe worktree holding a
byte-identical `md_hidden.py`, this file's tests and the vet 854 fixture, ran the whole test file and saw `2 failed, 508
passed, 30 skipped` (the two named nodes); the probe was restored and compared byte-identical. E3's `git apply
--reverse --check` was refused to the implementer by the permission layer; the orchestrator ran it on the build tree:
exit 0.
