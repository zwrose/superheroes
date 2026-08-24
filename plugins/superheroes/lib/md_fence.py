"""CommonMark §4.5 fenced-code-block line classifier (subset).

Classifies each line of markdown source as ``text``, ``opener``, ``content``, or
``closer`` according to the fence-marker rules in CommonMark §4.5. Consumers
use the precomputed ``inert`` tuple to skip lines that belong to a fence.

Implemented: indent width 0–3 (space/tab column counting), `` ` `` and ``~``
openers with run length ≥ 3, backtick info-string backtick prohibition,
closer run length ≥ opener run length, whitespace-only text after a closer
run, no nested openers while inside a fence, unterminated-opener reporting,
and trailing ``\\r`` stripping per line.

Deliberately out of scope: fences inside blockquote or list-item containers
(a line like ``> ```py`` is ordinary ``text`` here because ``>`` is not
whitespace), content or info-string extraction beyond the backtick restriction,
HTML blocks, and indented (non-fenced) code blocks. Indented code blocks are not
implemented here; a consumer that must accept indented content must apply
``indent_width`` itself.
"""
import collections

KIND_TEXT = "text"
KIND_OPENER = "opener"
KIND_CONTENT = "content"
KIND_CLOSER = "closer"
KINDS = frozenset({KIND_TEXT, KIND_OPENER, KIND_CONTENT, KIND_CLOSER})

FenceScan = collections.namedtuple(
    "FenceScan", ("kinds", "inert", "unterminated_opener_line")
)

TEXT = "TEXT"
FENCE_OPENER = "FENCE_OPENER"
FENCE_CONTENT = "FENCE_CONTENT"
FENCE_CLOSER = "FENCE_CLOSER"
HTML_OPEN = "HTML_OPEN"
HTML_CONTENT = "HTML_CONTENT"
HTML_CLOSE = "HTML_CLOSE"
CONTEXT_KINDS = frozenset({
    TEXT,
    FENCE_OPENER,
    FENCE_CONTENT,
    FENCE_CLOSER,
    HTML_OPEN,
    HTML_CONTENT,
    HTML_CLOSE,
})

ContextScan = collections.namedtuple(
    "ContextScan",
    ("kinds", "inert", "unterminated_opener_line", "unterminated_html_line"),
)

# CommonMark raw-text containers — contents are displayed literally, not interpreted.
# <details>, <summary>, and every other HTML tag stay live so the workhorse PR
# template can nest <!-- superheroes:degradations --> inside <details>.
RAW_TEXT_TAGS = frozenset({"pre", "script", "style", "textarea"})

INDENT_CODE_BLOCK_COLUMNS = 4


def indent_width(line):
    """Column width of `line`'s leading whitespace (space = 1, tab to the next multiple of 4)."""
    if line.endswith("\r"):
        line = line[:-1]
    width, _ = _split_indent(line)
    # axis: indent column width — spaces count 1, tabs advance to the next multiple of 4.
    return width


def _split_indent(line):
    """Return (indent_width, remainder) for the leading whitespace prefix."""
    width = 0
    pos = 0
    for ch in line:
        if ch == " ":
            width += 1
            pos += 1
        elif ch == "\t":
            # axis: indent bound — tab advances to the next multiple of 4.
            width = ((width // 4) + 1) * 4
            pos += 1
        else:
            break
    return width, line[pos:]


def _try_opener(line):
    """If ``line`` is a fence opener, return (marker_char, run_length). Else None."""
    indent, rest = _split_indent(line)
    if indent > 3:
        return None
    if not rest:
        return None
    if rest[0] == "`":
        run = 0
        for ch in rest:
            if ch == "`":
                run += 1
            else:
                break
        if run >= 3:
            # axis: run-length bound — opener needs three or more fence chars.
            info = rest[run:]
            if "`" in info:
                # axis: backtick info-string restriction — info may not contain `` ` ``.
                return None
            return ("`", run)
    elif rest[0] == "~":
        run = 0
        for ch in rest:
            if ch == "~":
                run += 1
            else:
                break
        if run >= 3:
            return ("~", run)
    return None


def _is_closer(line, opener_char, opener_len):
    """True when ``line`` closes a fence opened with (opener_char, opener_len)."""
    indent, rest = _split_indent(line)
    if indent > 3:
        return False
    if not rest or rest[0] != opener_char:
        return False
    run = 0
    for ch in rest:
        if ch == opener_char:
            run += 1
        else:
            break
    if run < opener_len:
        # axis: run-length bound — shorter run does not close a longer opener.
        return False
    after = rest[run:]
    # axis: whitespace-only-after-run closer rule — trailing non-ws makes content.
    for ch in after:
        if ch not in (" ", "\t"):
            return False
    return True


def scan(lines):
    """Classify each line of ``lines``. Returns a FenceScan."""
    kinds = []
    in_fence = False
    opener_char = None
    opener_len = 0
    opener_line_no = None
    unterminated_opener_line = None

    for i, raw_line in enumerate(lines):
        if not isinstance(raw_line, str):
            raise TypeError(
                "each line must be a str, got %s" % type(raw_line).__name__
            )
        line = raw_line[:-1] if raw_line.endswith("\r") else raw_line

        if in_fence:
            if _is_closer(line, opener_char, opener_len):
                kinds.append(KIND_CLOSER)
                in_fence = False
                opener_char = None
                opener_len = 0
            else:
                # axis: no-nested-opener rule — openers inside a fence are content.
                kinds.append(KIND_CONTENT)
        else:
            opener = _try_opener(line)
            if opener is not None:
                kinds.append(KIND_OPENER)
                in_fence = True
                opener_char = opener[0]
                opener_len = opener[1]
                opener_line_no = i + 1
            else:
                kinds.append(KIND_TEXT)

    if in_fence:
        # axis: unterminated report — name the opener when input ends inside a fence.
        unterminated_opener_line = opener_line_no

    inert = tuple(kind != KIND_TEXT for kind in kinds)
    return FenceScan(tuple(kinds), inert, unterminated_opener_line)


def _try_html_opener(line):
    """If ``line`` opens a type-1 raw-text HTML block, return the tag name. Else None."""
    indent, rest = _split_indent(line)
    if indent > 3:
        return None
    if not rest or rest[0] != "<":
        return None
    tail = rest[1:]
    lower = tail.lower()
    for tag in RAW_TEXT_TAGS:
        if lower.startswith(tag):
            after = tail[len(tag):]
            if not after or after[0] in (" ", "\t", ">"):
                return tag
    return None


def _line_has_html_close(line):
    """True when ``line`` contains a type-1 raw-text closing tag anywhere."""
    lower = line.lower()
    for tag in RAW_TEXT_TAGS:
        if ("</" + tag + ">") in lower:
            return True
    return False


def scan_contexts(lines):
    """Classify each line as live text or inert fence/HTML context. Returns a ContextScan."""
    kinds = []
    in_fence = False
    in_html = False
    opener_char = None
    opener_len = 0
    opener_line_no = None
    html_opener_line_no = None
    unterminated_opener_line = None
    unterminated_html_line = None

    for i, raw_line in enumerate(lines):
        if not isinstance(raw_line, str):
            raise TypeError(
                "each line must be a str, got %s" % type(raw_line).__name__
            )
        line = raw_line[:-1] if raw_line.endswith("\r") else raw_line

        if in_fence:
            if _is_closer(line, opener_char, opener_len):
                kinds.append(FENCE_CLOSER)
                in_fence = False
                opener_char = None
                opener_len = 0
            else:
                kinds.append(FENCE_CONTENT)
        elif in_html:
            if _line_has_html_close(line):
                kinds.append(HTML_CLOSE)
                in_html = False
            else:
                kinds.append(HTML_CONTENT)
        else:
            # Fence opener is tested before HTML start; the two conditions are disjoint.
            opener = _try_opener(line)
            if opener is not None:
                kinds.append(FENCE_OPENER)
                in_fence = True
                opener_char = opener[0]
                opener_len = opener[1]
                opener_line_no = i + 1
            elif _try_html_opener(line) is not None:
                if _line_has_html_close(line):
                    kinds.append(HTML_OPEN)
                else:
                    kinds.append(HTML_OPEN)
                    in_html = True
                    html_opener_line_no = i + 1
            else:
                kinds.append(TEXT)

    if in_fence:
        unterminated_opener_line = opener_line_no
    if in_html:
        unterminated_html_line = html_opener_line_no

    inert = tuple(kind != TEXT for kind in kinds)
    return ContextScan(
        tuple(kinds), inert, unterminated_opener_line, unterminated_html_line,
    )
