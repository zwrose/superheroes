"""What GitHub hides in a PR body (issue #2366).

GitHub renders a PR body with cmark-gfm (CommonMark 0.29 plus GFM), passes raw HTML through, and then parses the result
as HTML, so an HTML comment opened anywhere in raw HTML hides every following rendered element until a raw ``-->``.
Escaped Markdown output (text, code spans, code blocks) renders ``<`` and ``>`` as entities, so it can neither open nor
close a comment: the comment state is decided only by the raw-HTML chunks, in render order.

``scan(body)`` returns a ``Rendering``: one state per Markdown line, the document-level ATX headings, and the points from
which the parse could not be sure. The invariant: a line GitHub renders hidden is never reported ``VISIBLE``; where the
parse cannot be sure a line is visible it reports ``UNSURE``; ``HIDDEN`` is reported only where GitHub certainly hides.

The block parse is a port of cmark's ``blocks.c`` for the subset that matters here (block quotes, lists, ATX headings,
fenced and indented code, HTML blocks of the seven CommonMark 0.29 kinds, setext headings, thematic breaks, paragraphs).
Raw-HTML chunks (the content of HTML blocks) are run through a small HTML tokenizer that tracks only the comment state.
Python standard library only."""
import os
import re
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import md_fence  # noqa: E402

VISIBLE, HIDDEN, UNSURE = "visible", "hidden", "unsure"

_FENCE_CAP = 255  # cmark-gfm stores at most 255 fence characters
_CODE_INDENT = 4

_BLOCK_TAGS = (
    "address article aside base basefont blockquote body caption center col colgroup dd details dialog dir div dl dt "
    "fieldset figcaption figure footer form frame frameset h1 h2 h3 h4 h5 h6 head header hr html iframe legend li link "
    "main menu menuitem nav noframes ol optgroup option p param section summary table tbody td tfoot th thead title "
    "tr track ul"
).split()

# cmark's HTML scanners treat a vertical tab and a form feed as whitespace too (``spacechar`` in scanners.re)
_WS = "[ \t\v\f]"
# cmark is ASCII-only: re.A keeps Unicode case folding (U+017F, the Kelvin sign U+212A, U+0130, U+0131) from matching an
# ASCII tag letter
_HTML_T1 = re.compile(r"<(?:script|pre|style)(?:[ \t\v\f>]|\Z)", re.I | re.A)
_HTML_T4 = re.compile(r"<![A-Z]")
_HTML_T6 = re.compile(r"</?(?:" + "|".join(_BLOCK_TAGS) + r")(?:[ \t\v\f>]|/>|\Z)", re.I | re.A)
_ATTR = (r"(?:" + _WS + r"+[A-Za-z_:][A-Za-z0-9_.:-]*(?:" + _WS + r"*=" + _WS
         + r"""*(?:[^ \t\v\f"'=<>`]+|'[^']*'|"[^"]*"))?)""")
_HTML_T7 = re.compile(
    r"(?:<([A-Za-z][A-Za-z0-9-]*)" + _ATTR + r"*" + _WS + r"*/?>|</([A-Za-z][A-Za-z0-9-]*)" + _WS + r"*>)"
    + r"[ \t\f]*\Z"  # cmark-gfm's type 7 ends in [\t\n\f ]: a vertical tab after the tag is not whitespace here
)
_T1_END = re.compile(r"</(?:script|pre|style)>", re.I | re.A)

_ATX_START = re.compile(r"#{1,6}(?:[ ]+|\Z)")
_SETEXT = re.compile(r"(?:=+|-+)[ ]*\Z")
_THEMATIC = re.compile(r"(?:\*[ ]*){3,}\Z|(?:-[ ]*){3,}\Z|(?:_[ ]*){3,}\Z")
_FENCE_TICK = re.compile(r"(`{3,})([^`]*)\Z")
_FENCE_TILDE = re.compile(r"(~{3,})")
_BULLET = re.compile(r"[-+*](?=[ ]|\Z)")
_ORDERED = re.compile(r"([0-9]{1,9})[.)](?=[ ]|\Z)")
_LIST_START = re.compile(r"(?:[-+*]|[0-9]{1,9}[.)])(?:[ ]|\Z)")
_TABLE_DELIM = re.compile(r"[ ]{0,3}\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?\s*\Z")
_FOOTNOTE = re.compile(r"[ ]{0,3}\[\^[^\]\s]+\]:")
_VERSION_TAGS = re.compile(r"[ ]{0,3}</?(?:textarea|search|source)(?:[ \t\v\f>]|/>|\Z)", re.I | re.A)
_TAGFILTER = re.compile(r"</?(?:script|style|title|textarea|xmp|iframe|noembed|noframes|plaintext)", re.I | re.A)

_COMMENT_RUN = re.compile(r"<!--.*?(?:-->|--!>)", re.S)
_TAG_RUN = re.compile(r"<[^>]*>")

_ASCII_LETTERS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
_HTML_SPACE = frozenset(" \t\n\f\r")


class Rendering:
    """The result of ``scan``. ``lines``: ``(offset, state)`` for every Markdown line start, in order. ``headings``:
    ``(offset, text, state)`` for every ATX heading that is a direct child of the document. ``unsure``: ``(offset, why)``
    for each point from which the parse could not be sure (every line at or after the first is ``UNSURE``)."""

    def __init__(self, lines, headings, unsure):
        self.lines = tuple(lines)
        self.headings = tuple(headings)
        self.unsure = tuple(unsure)
        self._by_offset = dict(self.lines)

    def state_at(self, offset):
        """The state of the line that starts at ``offset``; ``ValueError`` when no line starts there."""
        if isinstance(offset, bool) or not isinstance(offset, int) or offset not in self._by_offset:
            raise ValueError("no line starts at offset %r" % (offset,))
        return self._by_offset[offset]


def heading_text(content):
    """An ATX heading's visible text: ``<!--`` ... first ``-->`` (or ``--!>``) removed, then every ``<`` ... ``>`` run
    removed, then stripped. ``content`` is the heading text after the opening ``#`` run, closing ``#`` run removed."""
    return _TAG_RUN.sub("", _COMMENT_RUN.sub("", content)).strip()


def _chop_closing_hashes(content):
    """CommonMark: drop an optional closing ``#`` sequence (preceded by a space, or the whole content) and trim."""
    content = content.rstrip(" ")
    i = len(content)
    while i > 0 and content[i - 1] == "#":
        i -= 1
    if i < len(content) and (i == 0 or content[i - 1] == " "):
        content = content[:i].rstrip(" ")
    return content


# --- The raw-HTML tokenizer (comment state only) ------------------------------------------------------------------

_DATA, _COMMENT, _BOGUS = "data", "comment", "bogus"
_OPEN_STATES = frozenset({_DATA, _COMMENT})  # a block whose content ends in any other state ends inside a tag


def _tokenize(state, text):
    """Run the HTML tokenizer over ``text`` (one line plus its newline) from ``state``; return the state after it.

    States: ``data``; ``comment`` (until the first ``-->`` or ``--!>``); ``bogus`` (a bogus comment, until ``>``); and
    the tag states, where a ``>`` ends the tag except inside a quoted attribute value."""
    i = 0
    n = len(text)
    while i < n:
        if state == _DATA:
            i = text.find("<", i)
            if i < 0:
                return state
            nxt = text[i + 1:i + 2]
            if nxt == "!":
                if text.startswith("--", i + 2):
                    if text.startswith(">", i + 4):  # <!--> is a complete empty comment (abrupt closing)
                        i += 5
                    elif text.startswith("->", i + 4):  # <!---> likewise
                        i += 6
                    else:
                        state = _COMMENT
                        i += 4
                else:
                    state = _BOGUS
                    i += 2
            elif nxt == "?":
                state = _BOGUS
                i += 2
            elif nxt == "/":
                after = text[i + 2:i + 3]
                if after in _ASCII_LETTERS and after:
                    state = "tag_name"
                    i += 3
                elif after == ">":  # </> is nothing
                    i += 3
                else:
                    state = _BOGUS
                    i += 2
            elif nxt and nxt in _ASCII_LETTERS:
                state = "tag_name"
                i += 2
            else:
                i += 1
        elif state == _COMMENT:
            ends = [(at, width) for at, width in ((text.find("-->", i), 3), (text.find("--!>", i), 4)) if at >= 0]
            if not ends:
                return state
            at, width = min(ends)
            i = at + width
            state = _DATA
        elif state == _BOGUS:
            at = text.find(">", i)
            if at < 0:
                return state
            i = at + 1
            state = _DATA
        else:
            c = text[i]
            space = c in _HTML_SPACE
            if state == "tag_name":
                if space:
                    state = "before_attr"
                elif c == "/":
                    state = "self_close"
                elif c == ">":
                    state = _DATA
            elif state == "before_attr":
                if space:
                    pass
                elif c == "/":
                    state = "self_close"
                elif c == ">":
                    state = _DATA
                else:
                    state = "attr_name"
            elif state == "attr_name":
                if space:
                    state = "after_attr_name"
                elif c == "/":
                    state = "self_close"
                elif c == "=":
                    state = "before_value"
                elif c == ">":
                    state = _DATA
            elif state == "after_attr_name":
                if space:
                    pass
                elif c == "/":
                    state = "self_close"
                elif c == "=":
                    state = "before_value"
                elif c == ">":
                    state = _DATA
                else:
                    state = "attr_name"
            elif state == "before_value":
                if space:
                    pass
                elif c == '"':
                    state = "value_dq"
                elif c == "'":
                    state = "value_sq"
                elif c == ">":
                    state = _DATA
                else:
                    state = "value_bare"
            elif state == "value_dq":
                if c == '"':
                    state = "after_value"
            elif state == "value_sq":
                if c == "'":
                    state = "after_value"
            elif state == "after_value":
                if space:
                    state = "before_attr"
                elif c == "/":
                    state = "self_close"
                elif c == ">":
                    state = _DATA
                else:
                    state = "attr_name"
            elif state == "value_bare":
                if space:
                    state = "before_attr"
                elif c == ">":
                    state = _DATA
            else:  # self_close
                if c == ">":
                    state = _DATA
                else:
                    state = "before_attr"
                    continue  # reconsume this character in before_attr
            i += 1
    return state


# --- The block parser (a port of cmark's blocks.c for this subset) ------------------------------------------------

_ACCEPTS_LINES = frozenset({"para", "atx", "setext", "fence", "icode"})


class _Block:
    """One node of the open-block tree. ``kind``: document, quote, list, item, para, atx, setext, fence, icode, html,
    thematic. ``lines`` holds a leaf's text (for an HTML block: ``(line index, content)`` pairs)."""

    def __init__(self, kind, parent, first):
        self.kind = kind
        self.parent = parent
        self.first = first  # index of the line that started it
        self.children = []
        self.open = True
        self.lines = []
        self.moffset = 0  # list item: marker offset
        self.padding = 0  # list item: marker width plus the spaces after it
        self.list_key = None  # list and item: (bullet or ordered, character)
        self.fence_char = ""
        self.fence_len = 0
        self.fence_offset = 0
        self.html_type = 0
        self.table = False  # paragraph: a GFM delimiter row followed its header row
        self.header = None  # paragraph with a table: the index in ``lines`` of the table's header row


def _can_contain(parent_kind, kind):
    if parent_kind in ("document", "quote", "item"):
        return kind != "item"
    if parent_kind == "list":
        return kind == "item"
    return False


def _html_ends(block_type, line):
    """The end condition of an HTML block of ``block_type`` tested on ``line`` (types 6 and 7 end at a blank line)."""
    if block_type == 1:
        return _T1_END.search(line) is not None
    if block_type == 2:
        return "-->" in line
    if block_type == 3:
        return "?>" in line
    if block_type == 4:
        return ">" in line
    if block_type == 5:
        return "]]>" in line
    return False


class _Parser:
    """Feeds the (tab-expanded, terminator-free) lines through cmark's per-line algorithm and records what the comment
    pass needs: the HTML blocks, the paragraphs and headings, the ATX headings, and the unsure points."""

    def __init__(self, offsets, texts):
        self.offsets = offsets
        self.texts = texts
        self.root = _Block("document", None, 0)
        self.tip = self.root  # cmark's parser->current: the deepest open block after the previous line
        self.unsure = {}  # (offset, why) -> None, insertion ordered
        self.html_blocks = []
        self.paras = []  # paragraphs, setext headings and ATX headings: the text blocks
        self.atx = []
        self.idx = 0
        self.text = ""
        self.pos = 0
        self.fns = 0
        self.indent = 0
        self.blank = True

    def run(self):
        for idx, text in enumerate(self.texts):
            self._line(idx, text)

    # -- helpers

    def _note(self, why):
        self.unsure[(self.offsets[self.idx], why)] = None

    def _scan_space(self):
        text = self.text
        fns = self.pos
        while fns < len(text) and text[fns] == " ":
            fns += 1
        self.fns = fns
        self.indent = fns - self.pos
        self.blank = fns >= len(text)

    def _finalize(self, block):
        block.open = False
        return block.parent

    def _add_child(self, parent, kind):
        while not _can_contain(parent.kind, kind):
            parent = self._finalize(parent)
        block = _Block(kind, parent, self.idx)
        parent.children.append(block)
        return block

    # -- one line

    def _line(self, idx, text):
        self.idx = idx
        self.text = text
        self.pos = 0
        self._scan_space()
        all_matched, container = self._continue_blocks()
        if container is None:
            return  # a closing fence consumed the line
        self._scan_space()
        self._table_row_check()
        last_matched = container
        container = self._open_blocks(container, all_matched)
        self._add_text(container, last_matched)

    def _continue_blocks(self):
        """Match the open blocks from the document down; return (all_matched, last matched container)."""
        container = self.root
        while True:
            last = container.children[-1] if container.children else None
            if last is None or not last.open:
                return True, container
            container = last
            self._scan_space()
            text = self.text
            kind = container.kind
            matched = True
            if kind == "quote":
                matched = self.indent <= 3 and not self.blank and text[self.fns] == ">"
                if matched:
                    self.pos = self.fns + 1
                    if text.startswith(" ", self.pos):
                        self.pos += 1
            elif kind == "item":
                need = container.moffset + container.padding
                if self.indent >= need:
                    self.pos += need
                elif self.blank and container.children:
                    self.pos = self.fns
                else:
                    matched = False
            elif kind == "fence":
                if self.indent <= 3 and not self.blank and text[self.fns] == container.fence_char:
                    rest = text[self.fns:]
                    run = len(rest) - len(rest.lstrip(container.fence_char))
                    if rest[run:].strip(" ") == "":
                        if run > _FENCE_CAP:
                            self._note("fence run longer than 255")
                        if run >= container.fence_len:
                            self.tip = self._finalize(container)
                            return False, None
                n = 0
                while n < container.fence_offset and self.pos < len(text) and text[self.pos] == " ":
                    self.pos += 1
                    n += 1
            elif kind == "icode":
                if self.indent >= _CODE_INDENT:
                    self.pos += _CODE_INDENT
                elif self.blank:
                    self.pos = self.fns
                else:
                    matched = False
            elif kind == "html":
                if container.html_type in (6, 7) and self.blank:
                    matched = False
            elif kind == "para":
                if self.blank:
                    matched = False
            elif kind in ("atx", "setext", "thematic"):
                matched = False
            if not matched:
                return False, container.parent

    def _table_row_check(self):
        """From a GFM delimiter row on, a row that starts with ``<``, a list marker or a setext underline is unsure."""
        tip = self.tip
        if tip.kind != "para" or not tip.table or self.blank or self.indent > 3:
            return
        rest = self.text[self.fns:]
        if rest.startswith("<") or _LIST_START.match(rest) or _SETEXT.match(rest):
            self._note("GFM table row that starts with <, a list marker or a setext underline")

    def _open_blocks(self, container, all_matched):
        maybe_lazy = self.tip.kind == "para"
        while container.kind not in ("fence", "icode", "html"):
            self._scan_space()
            started = self._start_block(container, all_matched, maybe_lazy)
            if started is None:
                break
            container = started
            if container.kind in _ACCEPTS_LINES:
                break
            maybe_lazy = False
        return container

    def _html_start_type(self, rest, kind, maybe_lazy):
        if _HTML_T1.match(rest):
            return 1
        if rest.startswith("<!--"):
            return 2
        if rest.startswith("<?"):
            return 3
        if _HTML_T4.match(rest):  # an uppercase letter only: GitHub shows <!x is no block start
            return 4
        if rest.startswith("<![CDATA["):
            return 5
        if _HTML_T6.match(rest):
            return 6
        if kind != "para" and not maybe_lazy:
            # no tag-name exclusion: cmark-gfm's type-7 scanner has none, and type 1 already took <script, <pre and <style
            if _HTML_T7.match(rest):
                return 7
        return 0

    def _list_marker(self, rest, interrupts):
        """(marker width, list key) when ``rest`` starts a list item that may start here, else None."""
        m = _BULLET.match(rest)
        ordered = False
        if m:
            width = 1
            key = ("bullet", rest[0])
        else:
            m = _ORDERED.match(rest)
            if not m:
                return None
            ordered = True
            width = m.end()
            key = ("ordered", rest[width - 1])
        if interrupts:
            if rest[width:].strip(" ") == "":
                return None
            if ordered and int(m.group(1)) != 1:  # axis: only an ordered list starting at 1 interrupts a paragraph
                return None
        return width, key

    def _start_block(self, container, all_matched, maybe_lazy):
        """Try each block start in cmark's order; return the new (or converted) container, or None."""
        text = self.text
        fns = self.fns
        rest = text[fns:]
        indented = self.indent >= _CODE_INDENT
        kind = container.kind
        if not indented:
            if rest.startswith(">"):
                self.pos = fns + 1
                if text.startswith(" ", self.pos):
                    self.pos += 1
                return self._add_child(container, "quote")
            m = _ATX_START.match(rest)
            if m:
                self.pos = fns + m.end()
                block = self._add_child(container, "atx")
                self.atx.append(block)
                self.paras.append(block)
                return block
            m = _FENCE_TILDE.match(rest) or _FENCE_TICK.match(rest)
            if m:
                run = len(m.group(1))
                block = self._add_child(container, "fence")
                block.fence_char = rest[0]
                block.fence_len = min(run, _FENCE_CAP)
                block.fence_offset = self.indent
                self.pos = fns + run
                if run > _FENCE_CAP:
                    self._note("fence run longer than 255")
                return block
            html_type = self._html_start_type(rest, kind, maybe_lazy)
            if html_type:
                block = self._add_child(container, "html")
                block.html_type = html_type
                self.html_blocks.append(block)
                return block
            if kind == "para" and _SETEXT.match(rest):
                container.kind = "setext"
                self.pos = len(text)
                return container
            if not (kind == "para" and not all_matched) and _THEMATIC.match(rest):
                self.pos = len(text)
                return self._add_child(container, "thematic")
        if self.indent < _CODE_INDENT:
            marker = self._list_marker(rest, kind == "para")
            if marker:
                width, key = marker
                after = rest[width:]
                spaces = len(after) - len(after.lstrip(" "))
                if spaces == 0 or spaces >= 5 or after.strip(" ") == "":
                    padding = width + 1
                    self.pos = fns + width + (1 if spaces else 0)
                else:
                    padding = width + spaces
                    self.pos = fns + width + spaces
                moffset = self.indent
                if kind != "list" or container.list_key != key:
                    container = self._add_child(container, "list")
                    container.list_key = key
                item = self._add_child(container, "item")
                item.moffset = moffset
                item.padding = padding
                item.list_key = key
                return item
        if indented and not maybe_lazy and not self.blank:
            self.pos += _CODE_INDENT
            return self._add_child(container, "icode")
        return None

    def _add_text(self, container, last_matched):
        self._scan_space()
        rest = self.text[self.pos:]
        lazy = (
            self.tip is not last_matched and container is last_matched and not self.blank and self.tip.kind == "para"
        )
        if lazy:
            self._add_text_line(self.tip, rest, False)
            return
        node = self.tip
        while node is not None and node is not last_matched:
            node = self._finalize(node)
        kind = container.kind
        if kind in ("fence", "icode"):
            pass  # code content: never raw HTML, never a footnote
        elif kind == "html":
            container.lines.append((self.idx, rest))
            self._check_line(rest)
            if _html_ends(container.html_type, self.text[self.fns:]):
                container = self._finalize(container)
        elif self.blank:
            pass
        elif kind in ("para", "atx", "setext"):
            if kind == "atx":
                rest = _chop_closing_hashes(rest)
            self._add_text_line(container, rest, True)
        else:
            container = self._add_child(container, "para")
            self.paras.append(container)
            self._add_text_line(container, rest, True)
        self.tip = container

    def _add_text_line(self, block, rest, matched):
        if (matched and block.kind == "para" and block.lines and "|" in rest and _TABLE_DELIM.match(rest)
                and _cell_count(block.lines[-1]) == _cell_count(rest)):
            # axis: cmark-gfm makes a table only when the header row and the delimiter row hold the same cell count
            block.table = True  # axis: a GFM delimiter row turns on the table-row unsure rule
            block.header = len(block.lines) - 1
        block.lines.append(rest)
        self._check_line(rest)

    def _check_line(self, rest):
        if _FOOTNOTE.match(rest):
            self._note("footnote definition")
        if _VERSION_TAGS.match(rest):
            self._note("tag whose block kind differs between CommonMark versions")
        if _TAGFILTER.search(rest):
            self._note("tag that GitHub's tagfilter escapes")


# --- The comment pass and the public entry point ------------------------------------------------------------------

def _terminator_free(item):
    if item.endswith("\r\n"):
        return item[:-2]
    if item.endswith("\n") or item.endswith("\r"):
        return item[:-1]
    return item


def _closer_after_lt(text):
    """True when ``text`` holds a ``<`` with a ``-->`` or ``--!>`` after it (a raw inline chunk could close a comment)."""
    at = text.find("<")
    return at >= 0 and (text.find("-->", at) >= 0 or text.find("--!>", at) >= 0)


# --- The inline raw-HTML pass (fix leg 2, vet 846 F5/F6/F8) -------------------------------------------------------------

# cmark-gfm 0.29 inline grammar. Whitespace is ``[ \t\n\v\f\r]``, so a construct may span lines.
_IWS = "[ \t\n\v\f\r]"
_ASCII_PUNCT = frozenset("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")
_AUTOLINK_URI = re.compile(r"<[A-Za-z][A-Za-z0-9.+-]{1,31}:[^\x00-\x20<>]*>")
_AUTOLINK_EMAIL = re.compile(
    r"<[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*>"
)
_INLINE_OPEN_TAG = re.compile(
    r"<[A-Za-z][A-Za-z0-9-]*(?:" + _IWS + r"+[A-Za-z_:][A-Za-z0-9_.:-]*(?:" + _IWS + r"*=" + _IWS
    + r"""*(?:[^ \t\n\v\f\r"'=<>`]+|'[^']*'|"[^"]*"))?)*""" + _IWS + r"*/?>"
)
_INLINE_CLOSE_TAG = re.compile(r"</[A-Za-z][A-Za-z0-9-]*" + _IWS + r"*>")
_INLINE_COMMENT = re.compile(r"<!--.*?-->", re.S)
_INLINE_PI = re.compile(r"<\?.*?\?>", re.S)
_INLINE_CDATA = re.compile(r"<!\[CDATA\[.*?\]\]>", re.S)
# cmark-gfm's declaration: <! then an uppercase name, whitespace, anything but >, then >
_INLINE_DECL = re.compile(r"<![A-Z]+" + _IWS + r"+[^>]*>")
_REF_DEF = re.compile(r"(?m)^[ ]{0,3}\[[^\]\n]+\]:")  # a line that may be a link reference definition
_REF_DEF_START = re.compile(r"[ ]{0,3}\[")  # a block's first line that may open a link reference definition
_MAX_BACKTICKS = 80  # cmark-gfm: a backtick run longer than this opens no code span (scan_to_closing_backticks)


def _link_regions(text):
    """``(start, end)`` ranges that may be a link's destination and title, or a link reference definition: from any
    ``](`` (whether or not a ``[`` precedes it) to the ``)`` that closes it (an angle-bracket destination ``<…>``
    skipped whole; quoted ``"…"`` and ``'…'`` skipped; parentheses counted; an unclosed one runs to the end of the
    text), and from a ``]:`` on a line that starts with ``[`` to the end of the next line. The ranges are an
    over-approximation of cmark's, used only to add unsure points: wider is safe, narrower is not."""
    regions = []
    at = text.find("](")
    while at >= 0:
        regions.append((at + 2, _destination_end(text, at + 2)))
        at = text.find("](", at + 2)
    for m in _REF_DEF.finditer(text):
        nl = text.find("\n", m.end())
        nl2 = text.find("\n", nl + 1) if nl >= 0 else -1
        regions.append((m.end(), len(text) if nl2 < 0 else nl2))
    return regions


def _destination_end(text, j):
    """Where a possible link destination and title starting at ``j`` end: just past the closing ``)``, else the end.
    Read as cmark-gfm reads an inline link: an angle-bracket destination ends at the first ``>`` that is not
    backslash-escaped; a bare one counts its parentheses (quotes are ordinary characters there) and ends at
    whitespace; then an optional ``"…"``, ``'…'`` or ``(…)`` title, then ``)``. Anything this reading cannot follow
    runs to the end of the text, so the result is an over-approximation used only to add unsure points."""
    n = len(text)

    def blank(k):
        while k < n and text[k] in " \t\n":
            k += 1
        return k

    j = blank(j)
    if j < n and text[j] == "<":
        j += 1
        while j < n and text[j] != ">":
            j += 2 if text[j] == "\\" else 1
        if j >= n:
            return n
        j += 1
    else:
        depth = 0
        while j < n and text[j] not in " \t\n":
            c = text[j]
            if c == "\\":
                j += 2
                continue
            if c == "(":
                depth += 1
            elif c == ")":
                if depth == 0:
                    return j + 1
                depth -= 1
            j += 1
    j = blank(j)
    if j < n and text[j] in "\"'(":
        close = ")" if text[j] == "(" else text[j]
        j += 1
        while j < n and text[j] != close:
            j += 2 if text[j] == "\\" else 1
        if j >= n:
            return n
        j = blank(j + 1)
    if j < n and text[j] == ")":
        return j + 1
    return n


def _cell_count(row):
    """The number of cells in a GFM table row: split on unescaped ``|``, one leading and one trailing pipe dropped."""
    text = row.strip(" \t")
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|") and not text.endswith("\\|"):
        text = text[:-1]
    count, j = 1, 0
    while j < len(text):
        if text[j] == "\\":
            j += 2
            continue
        if text[j] == "|":
            count += 1
        j += 1
    return count


def _cell_end(text, i):
    """The index of the next unescaped ``|`` or line break at or after ``i`` (the end of a GFM table cell), else the
    text's length."""
    j = i
    while j < len(text):
        if text[j] == "\\":
            j += 2
            continue
        if text[j] in "|\n":
            return j
        j += 1
    return len(text)


_INLINE_RAW = (_INLINE_OPEN_TAG, _INLINE_CLOSE_TAG, _INLINE_COMMENT, _INLINE_PI, _INLINE_CDATA, _INLINE_DECL)
_ASCII_WS = " \t\n\v\f\r"


def _inline_constructs(text):
    """The raw-HTML constructs of a text block, left to right as cmark-gfm's inline parser finds them: a list of
    ``(start, end)`` (end exclusive). A backslash escapes an ASCII punctuation character; a backtick run opens a code
    span that closes at the next run of exactly its length (nothing inside is raw HTML; with no such run the backticks
    are literal); at ``<`` an autolink is text, otherwise one of the six raw-HTML grammars either matches there or the
    ``<`` is literal."""
    found = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2 if text[i + 1:i + 2] in _ASCII_PUNCT and i + 1 < n else 1
        elif c == "`":
            end = i
            while end < n and text[end] == "`":
                end += 1
            width = end - i
            at = end
            closed = -1
            # axis: a run longer than cmark-gfm's 80 backticks is literal text
            if width > _MAX_BACKTICKS:
                at = n
            while at < n:
                at = text.find("`", at)
                if at < 0:
                    break
                run = at
                while run < n and text[run] == "`":
                    run += 1
                if run - at == width:
                    closed = run
                    break
                at = run
            # axis (C2): a code span is skipped whole, so a <!-- inside one is no comment
            i = closed if closed >= 0 else end
        elif c == "<":
            m = _AUTOLINK_URI.match(text, i) or _AUTOLINK_EMAIL.match(text, i)
            if m:
                i = m.end()
                continue
            for pattern in _INLINE_RAW:
                m = pattern.match(text, i)
                if m:
                    found.append((i, m.end()))
                    break
            i = m.end() if m else i + 1
        else:
            i += 1
    return found


def _comment_line_state(line):
    """The state of a line that starts inside a comment: ``HIDDEN``, or ``UNSURE`` when it holds a closer (``-->`` or
    ``--!>``) with text after the first one, since GitHub shows that text (vet 846 F8)."""
    ends = [(at, width) for at, width in ((line.find("-->"), 3), (line.find("--!>"), 4)) if at >= 0]
    if ends:
        at, width = min(ends)
        if line[at + width:].strip(_ASCII_WS):
            return UNSURE
    return HIDDEN


def _inline_pass(lines, first, hidden_lines, sure_points, line_unsure, header=None):
    """Run the inline raw-HTML pass over one text block (``lines``: its lines after container prefixes; source line
    ``first + k`` is ``lines[k]``).

    Each raw construct is run through ``_tokenize`` from ``_DATA`` piece by piece, the way GitHub's HTML parse reads it.
    For every source line that starts inside the construct, the tokenizer state at the line's start decides it: a
    comment state is ``HIDDEN`` (``UNSURE`` per ``_comment_line_state``, recorded in ``line_unsure``); a tag or bogus
    state is an unsure point at that line; ``_DATA`` leaves it unchanged. A construct that ends with the tokenizer not
    back in ``_DATA`` (or a tag holding a vertical tab) is an unsure point at the line that holds cmark's end of it."""
    joined = "\n".join(lines)
    starts = [0]
    for k, line in enumerate(lines[:-1]):
        starts.append(starts[-1] + len(line) + 1)

    def line_of(position):
        lo, hi = 0, len(starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if starts[mid] <= position:
                lo = mid
            else:
                hi = mid - 1
        return lo

    if header is None:
        constructs = _inline_constructs(joined)
    else:
        # axis: cmark-gfm inline-parses each GFM table cell on its own (the lines above the header row stay one
        # paragraph), so no code span or raw-HTML construct runs from one cell into the next
        constructs = _inline_constructs("\n".join(lines[:header]))
        for k in range(header, len(lines)):
            at, end = starts[k], starts[k] + len(lines[k])
            while at <= end:
                stop = min(_cell_end(joined, at), end)
                constructs += [(at + b, at + e) for b, e in _inline_constructs(joined[at:stop])]
                at = stop + 1
    if lines and _REF_DEF_START.match(lines[0]) and "]:" in joined:
        # axis: cmark consumes link reference definitions at a block's start and GitHub renders nothing for them, so
        # a block that may open with one (a "[" line and a "]:" anywhere: labels may hold escapes and span lines)
        # reads unsure from its first line
        sure_points.add((first, "possible link reference definition"))
    if "<" in joined:
        # axis: cmark reads a link's destination and title (and a reference definition) apart from the inline text, so
        # a backtick there opens no code span and can change how every later backtick pairs; rather than parse links,
        # a block that holds a backtick inside a possible link range and also a "<" reads unsure from its first line
        # (the ranges are an over-approximation used only to add this unsure point; the rule decides no line)
        regions = _link_regions(joined)
        ticks = [i for i, ch in enumerate(joined) if ch == "`"]
        if any(r0 <= i < r1 for i in ticks for r0, r1 in regions):
            sure_points.add((first, "backtick in possible link metadata in a block that holds raw HTML"))
    for begin, end in constructs:
        construct = joined[begin:end]
        first_line = line_of(begin)
        last_line = line_of(end - 1)
        pieces = construct.split("\n")
        state = _DATA
        for offset, piece in enumerate(pieces):
            k = first_line + offset
            if offset:
                # axis (C3, C4, C6): the state at the start of a line inside the construct decides that line
                if state == _COMMENT:
                    if _comment_line_state(lines[k]) == UNSURE:
                        line_unsure.add(first + k)
                    else:
                        hidden_lines.add(first + k)
                elif state != _DATA:
                    sure_points.add((first + k, "line starts inside a tag or a bogus comment of an inline construct"))
            state = _tokenize(state, piece + "\n" if offset < len(pieces) - 1 else piece)
        # axis (C5): the HTML parse disagrees with cmark about where the construct ends
        # (a vertical tab in a tag also counts, as the earlier conservative reading: cmark takes \v as tag whitespace)
        is_tag = _INLINE_OPEN_TAG.fullmatch(construct) or _INLINE_CLOSE_TAG.fullmatch(construct)
        if state != _DATA or (is_tag and "\v" in construct):
            sure_points.add((first + last_line, "inline construct that HTML parsing ends differently than cmark"))


def _scan(body):
    items = md_fence.split_lines(body)
    offsets = []
    texts = []
    offset = 0
    for i, item in enumerate(items):
        offsets.append(offset)
        offset += len(item)
        text = _terminator_free(item)
        # axis: cmark skips one byte-order mark at the start of the document, so a BOM never hides a block start
        if i == 0 and text.startswith("﻿"):
            text = text[1:]
        texts.append(text.expandtabs(_CODE_INDENT))
    parser = _Parser(offsets, texts)
    parser.run()

    html_line = {}
    html_last = set()
    for block in parser.html_blocks:
        for idx, content in block.lines:
            html_line[idx] = content
        html_last.add(block.lines[-1][0])
    text_block = {block.first: block for block in parser.paras}

    unsure = dict(parser.unsure)
    raw = []
    inline_hidden = set()  # source lines that start inside an inline comment
    inline_unsure = set()  # source lines that start inside an inline comment and show text after its closer
    inline_points = set()  # (source line, why)
    state = _DATA
    for i in range(len(texts)):
        hidden = state == _COMMENT
        if hidden:
            # vet 846 F8: a raw closer in HTML-block content shows the text after it
            raw.append(_comment_line_state(html_line[i]) if i in html_line else HIDDEN)
        else:
            raw.append(VISIBLE)
        if state not in _OPEN_STATES:
            # unsure, never hidden: a > early in this line can end the tag or bogus comment, and the rest of the line shows
            unsure[(offsets[i], "line starts inside a tag or a bogus comment")] = None
        if i in html_line:
            state = _tokenize(state, html_line[i] + "\n")
            if i in html_last and state not in _OPEN_STATES:
                at = offsets[i + 1] if i + 1 < len(texts) else len(body)
                unsure[(at, "HTML block ends inside a tag or a bogus comment")] = None
                state = _DATA
        elif i in text_block:
            if hidden:
                if _closer_after_lt("\n".join(text_block[i].lines)):
                    unsure[(offsets[i], "text inside a comment holds < and a later -->")] = None
            else:
                # axis (C1): the inline raw-HTML pass over the text block's content
                _inline_pass(text_block[i].lines, i, inline_hidden, inline_points, inline_unsure, text_block[i].header)

    for line_index, why in inline_points:
        if line_index < len(offsets):
            unsure[(offsets[line_index], why)] = None
    for line_index in inline_hidden:
        if line_index < len(raw):
            raw[line_index] = HIDDEN
    for line_index in inline_unsure:
        if line_index < len(raw):
            raw[line_index] = UNSURE

    first_unsure = min((at for at, _ in unsure), default=None)
    lines = []
    for i, offset in enumerate(offsets):
        if first_unsure is not None and offset >= first_unsure:
            lines.append((offset, UNSURE))
        else:
            lines.append((offset, raw[i]))
    state_of = dict(zip(range(len(lines)), (s for _, s in lines)))

    headings = []
    for block in parser.atx:
        if block.parent is parser.root:
            content = block.lines[0] if block.lines else ""
            headings.append((offsets[block.first], heading_text(content), state_of[block.first]))
    return Rendering(lines, headings, sorted(unsure))


def scan(body):
    """Return a ``Rendering`` for ``body`` (a str). Pure; never raises on any str input (an internal failure is reported
    as an unsure point at offset 0, so every line is ``UNSURE``)."""
    if not isinstance(body, str):
        raise TypeError("body must be a str, got %s" % type(body).__name__)
    try:
        return _scan(body)
    except Exception as exc:  # fail closed: a parser bug must never read as visible
        offsets = []
        offset = 0
        for item in md_fence.split_lines(body):
            offsets.append(offset)
            offset += len(item)
        return Rendering(
            [(o, UNSURE) for o in offsets], (), [(0, "internal error: %s" % type(exc).__name__)]
        )
