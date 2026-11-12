"""The one chokepoint for at-sign mentions in text the plugin prepares for GitHub.

GitHub notifies whoever a login after an at-sign names, numeric logins included. A *bare mention* is an
at-sign that GitHub's mention grammar reads as a login, outside a fenced code block and outside an inline code
span. Every plugin writer of GitHub text either refuses such text (`check`, refusal token `bare-mention`, with a
remedy) or neutralizes it (`wrap`, which puts each bare mention in a code span).

Public API (stdlib only, plus the sibling `md_fence`):

- `MENTION_RE`: GitHub's own mention grammar (the html-pipeline mention filter). Unmeasured here: the session
  cannot reach GitHub's render endpoint; the truth table in `tests/test_mention_guard.py` is the contract.
- `bare_mentions(text)`: `[{"line": <1-based>, "mention": "@login"}, ...]` in text order; `[]` for non-string text.
  The invariant: a mention is reported unless every reasonable reading of the text agrees it is not one. A doubt
  about whether an at-sign sits in code reports it (the writers then refuse with a remedy, or `wrap` code-spans it);
  a mask never rests on one parse alone.
- `check(text)`: `{"ok": True}` or `{"ok": False, "reason": "bare-mention", "mentions": [...], "remedy": REMEDY}`.
- `wrap(text)`: `text` with every bare mention in a code span whose delimiter is one backtick longer than the
  longest backtick run anywhere in `text`; idempotent; text with no bare mention comes back unchanged.

CLI: `python3 -B mention_guard.py check --file F` prints the `check` JSON (exit 0 ok, 1 `bare-mention`, 2 usage or
unreadable file); `python3 -B mention_guard.py wrap` reads stdin and writes the wrapped text to stdout (exit 0).
"""
import argparse
import json
import os
import re
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import md_fence  # noqa: E402

REASON = "bare-mention"
REMEDY = ("GitHub notifies whoever a login after an at-sign names. Drop the at-sign (write 'vet 893', "
          "'collector 574' or the bare name), or put the token in a code span; post a mention only when you mean "
          "to notify that person, and then outside the plugin's writers.")

# axis: a bare at-sign GitHub reads as a login, outside fences and code spans, is reported — see bite-proof record wo_2453_mention_guard
MENTION_RE = re.compile(
    r"(?:^|(?<=\W))@((?>[a-z0-9][a-z0-9-]*))(?=\.+[ \t\W]|\.+$|[^0-9a-zA-Z_.]|$)",
    re.IGNORECASE | re.MULTILINE,
)
_BACKTICK_RUN_RE = re.compile(r"`+")
# A line that opens a raw HTML block (GFM block kinds 6 and 7, approximated: a tag at the line's start).
_HTML_BLOCK_RE = re.compile(r"^ {0,3}</?[A-Za-z][A-Za-z0-9-]*(?:[\s/>]|$)")
# A raw-text HTML block opener (GFM block kind 1): it ends at a line holding any kind-1 closing tag, not at a
# blank line.
_RAW_HTML_RE = re.compile(r"^ {0,3}<(pre|script|style|textarea)(?=[\s>]|$)", re.IGNORECASE | re.ASCII)
_RAW_HTML_CLOSE_RE = re.compile(r"</(?:pre|script|style|textarea)>", re.IGNORECASE | re.ASCII)
# Tag patterns fold case over ASCII only (re.ASCII), and the URL scheme spells its case out while keeping
# Unicode word and space classes: GFM does both, so a non-ASCII look-alike never closes a block or masks a span.
# A code element; a backslash-escaped `\<code>` is literal text, so it masks nothing.
_CODE_ELEMENT_RE = re.compile(r"(?<!\\)<code>.*?</code>", re.IGNORECASE | re.ASCII)
# A complete inline link ([label] then a parenthesised destination, closed), an angle autolink or a bare URL; an
# incomplete link shape masks nothing: GitHub renders each as an anchor (or an attribute), and its
# mention filter skips anchors, so an at-sign inside one is part of the address, never a mention. A link destination
# may hold one level of balanced parentheses.
_LINK_RE = re.compile(r"\[[^\]\n]*\](\((?:[^()\s]|\([^()\s]*\))*\))")
_URL_RE = re.compile(r"<[A-Za-z][A-Za-z0-9+.-]*:[^\s<>]*>|\b(?:[Hh][Tt][Tt][Pp][Ss]?|[Ff][Tt][Pp])://[^\s<>()]+")


def _urls(line):
    """The extents of the complete link destinations (the parenthesised part only; the label stays prose) and
    the URLs on one line."""
    return ([m.span(1) for m in _LINK_RE.finditer(line)]
            + [(m.start(), m.end()) for m in _URL_RE.finditer(line)])


def _bare_line(whole):
    """`whole` (one item of `md_fence.split_lines`) without its one terminator: CRLF, LF or a lone CR."""
    if whole.endswith("\r\n"):
        return whole[:-2]
    if whole.endswith(("\n", "\r")):
        return whole[:-1]
    return whole


def _code_spans(line):
    """The `(start, end)` extents of the inline code spans of one text block, delimiters included. A backtick
    run of length n opens a span that closes at the next run of exactly length n in the block (line breaks
    included, as GFM pairs them across lines); with no such run the backticks are literal. A backslash before a
    backtick escapes it."""
    runs = [(m.start(), m.end()) for m in _BACKTICK_RUN_RE.finditer(line)]
    spans = []
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch == "\\" and i + 1 < n and line[i + 1] in "`\\":
            i += 2
            continue
        if ch != "`":
            i += 1
            continue
        length = 1
        while i + length < n and line[i + length] == "`":
            length += 1
        close = next((r for r in runs if r[0] >= i + length and r[1] - r[0] == length), None)
        if close is None:
            i += length
            continue
        spans.append((i, close[1]))
        i = close[1]
    return spans


def _cell_spans(line):
    """The code-span extents of one table row: GFM parses each cell on its own, so a span never crosses an
    unescaped pipe."""
    spans = []
    start = 0
    for i, ch in enumerate(line + "|"):
        if ch == "|" and (i == 0 or line[i - 1] != "\\"):
            spans.extend((start + a, start + b) for a, b in _code_spans(line[start:i]))
            start = i + 1
    return spans


_FENCE_OPENER_RE = re.compile(r"^(`{3,}|~{3,})(.*)$")
_FENCE_CLOSER_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*$")
_INDENTED_FENCE_RE = re.compile(r"^[ \t]+(`{3,}|~{3,})(.*)$")
_ANY_CLOSER_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})[ \t]*$")


def _has_unescaped_pipe(line):
    """True when `line` holds a pipe not preceded by a backslash (a table row, with or without a leading pipe)."""
    return any(ch == "|" and (i == 0 or line[i - 1] != "\\") for i, ch in enumerate(line))


def _inside(spans, pos):
    return any(start <= pos < stop for start, stop in spans)


def _contexts(bare):
    """`(inert, html)`: which lines sit inside a fenced block and which in a raw HTML block, read in one pass so
    neither is decided without the other. A fence opens only on a line that starts with three or more backticks
    or tildes at column 0 (an indented one, as a fence inside a list or blockquote looks, masks nothing, and its own
    closer is consumed with it, so that closer can never open a fence); it masks through a column-0 closer (the same character, at least as long) or, unterminated, through
    the end, which GFM renders as code; a block that closes on an indented closer masks nothing. A raw HTML block opens on a
    tag at a line's start outside a fence and runs to the next blank line; inside it a fence-shaped line is
    literal text."""
    inert = [False] * len(bare)
    html = [False] * len(bare)
    fence, fence_start = None, 0
    shadow = None
    raw_close = None
    in_html = False
    for k, line in enumerate(bare):
        if shadow is not None:
            # axis: an indented opener's block masks nothing, and its closer is consumed so it opens no fence
            closer = _ANY_CLOSER_RE.match(line)
            if closer and closer.group(1)[0] == shadow[0] and len(closer.group(1)) >= len(shadow):
                shadow = None
                continue
            # axis: inside an indented opener's block no reading is certain, so its lines take no code-span mask
            html[k] = bool(line.strip())
            continue
        if fence is not None:
            # axis: a line inside a fence is code, so a tag there opens no HTML block
            inert[k] = True
            closer = _FENCE_CLOSER_RE.match(line)
            if closer and closer.group(1)[0] == fence[0] and len(closer.group(1)) >= len(fence):
                if line[:1] in (" ", "\t"):
                    # axis: an indented closer is how a list-contained fence ends, so the readings disagree and the
                    # block masks nothing
                    for j in range(fence_start, k + 1):
                        inert[j] = False
                fence = None
            continue
        if raw_close is not None:
            # axis: a raw-text HTML block (pre, script, style, textarea) runs to its closing tag, blank lines included
            html[k] = bool(line.strip())
            # axis: any type-1 closing tag ends the block, whichever tag opened it
            if _RAW_HTML_CLOSE_RE.search(line):
                raw_close = None
            continue
        if in_html:
            if not line.strip():
                in_html = False
                continue
            # axis: a fence-shaped line inside a raw HTML block is literal text, so it opens no fence
            html[k] = True
            continue
        indented = _INDENTED_FENCE_RE.match(line)
        if indented and not (indented.group(1)[0] == "`" and "`" in indented.group(2)):
            shadow = indented.group(1)
            html[k] = True
            continue
        opener = _FENCE_OPENER_RE.match(line)
        if opener and not (opener.group(1)[0] == "`" and "`" in opener.group(2)):
            # axis: only a column-0 opener masks, so an indented (list or blockquote) fence masks nothing
            inert[k] = True
            fence, fence_start = opener.group(1), k
            continue
        raw = _RAW_HTML_RE.match(line)
        if raw:
            html[k] = True
            if not _RAW_HTML_CLOSE_RE.search(line, raw.end()):
                raw_close = True
            continue
        if _HTML_BLOCK_RE.match(line):
            html[k] = in_html = True
    return inert, html


def _found(text):
    """Every bare mention of `text` as `(line index, start, end, mention, html)` in text order; `start` is the
    at-sign and `html` says the line sits in a raw HTML block, where a code span is not code."""
    bare = [_bare_line(whole) for whole in md_fence.split_lines(text)]
    inert, html = _contexts(bare)
    out = []
    idx = 0
    while idx < len(bare):
        line = bare[idx]
        if html[idx]:
            # axis: a raw HTML block renders no code span, so its backticks mask nothing
            elements = [(m.start(), m.end()) for m in _CODE_ELEMENT_RE.finditer(line)] + _urls(line)
            out.extend((idx, m.start(), m.end(), "@" + m.group(1), True) for m in MENTION_RE.finditer(line)
                       if not any(start <= m.start() < stop for start, stop in elements))
            idx += 1
            continue
        if inert[idx] or not line.strip():
            idx += 1
            continue
        end = idx
        while end < len(bare) and not inert[end] and bare[end].strip() and not html[end]:
            end += 1
        paragraph_spans = _code_spans("\n".join(bare[idx:end]))
        offset = 0
        for k in range(idx, end):
            row = bare[k]
            line_spans = _code_spans(row)
            cell_spans = _cell_spans(row) if _has_unescaped_pipe(row) else None
            urls = _urls(row)
            for m in MENTION_RE.finditer(row):
                # axis: code masks a mention only when every reading agrees: its own line, its paragraph, and its cell
                if (_inside(line_spans, m.start()) and _inside(paragraph_spans, offset + m.start())
                        and (cell_spans is None or _inside(cell_spans, m.start()))):
                    continue
                # axis: an at-sign inside a link destination or a URL is part of the address, so it is never reported
                if _inside(urls, m.start()):
                    continue
                out.append((k, m.start(), m.end(), "@" + m.group(1), False))
            offset += len(row) + 1
        idx = end
    return out


def bare_mentions(text):
    """`[{"line": <1-based int>, "mention": "@login"}, ...]` for every bare mention in `text`, in text order;
    `[]` for non-string text. A closed or unterminated fenced block whose opener (and closer) sits at column 0
    is masked; an inline code span masks only when its own line, its paragraph and (on a line with an unescaped
    pipe) its table cell all pair it as code. A raw HTML block masks no code span."""
    if not isinstance(text, str):
        return []
    return [{"line": idx + 1, "mention": mention} for idx, _start, _end, mention, _html in _found(text)]


def check(text):
    """`{"ok": True}` when `text` carries no bare mention (or is not a string), else the `bare-mention` refusal."""
    mentions = bare_mentions(text)
    if not mentions:
        return {"ok": True}
    return {"ok": False, "reason": REASON, "mentions": mentions, "remedy": REMEDY}


def wrap(text):
    """`text` with every bare mention wrapped in a code span. The delimiter is a backtick run one longer than the
    longest backtick run anywhere in `text` (minimum 1), so it can never pair with an existing run; a space keeps
    it from touching an adjacent backtick or backslash. Idempotent. Text with no bare mention, and non-string
    text, comes back unchanged."""
    if not isinstance(text, str):
        return text
    found = _found(text)
    if not found:
        return text
    ticks = "`" * (max((len(m) for m in _BACKTICK_RUN_RE.findall(text)), default=0) + 1)
    lines = md_fence.split_lines(text)
    by_line = {}
    for idx, start, end, _token, html in found:
        by_line.setdefault(idx, []).append((start, end, html))
    for idx, extents in by_line.items():
        line = lines[idx]
        for start, end, html in reversed(extents):
            if html:
                # axis: in a raw HTML block a backtick is literal, so the token goes in a code element
                line = line[:start] + "<code>" + line[start:end] + "</code>" + line[end:]
                continue
            opener = ticks if start == 0 or line[start - 1] not in "`\\" else " " + ticks
            closer = ticks if end >= len(line) or line[end] != "`" else ticks + " "
            line = line[:start] + opener + line[start:end] + closer + line[end:]
        lines[idx] = line
    return "".join(lines)


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise SystemExit(2)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    parser = _Parser(prog="mention_guard.py")
    sub = parser.add_subparsers(dest="verb", required=True, parser_class=_Parser)
    sub.add_parser("check").add_argument("--file", required=True)
    sub.add_parser("wrap")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        sys.stdout.write(json.dumps({"ok": False, "reason": "usage"}) + "\n")
        return 2
    if args.verb == "wrap":
        try:
            text = sys.stdin.buffer.read().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            sys.stdout.write(json.dumps({"ok": False, "reason": "input-unreadable"}) + "\n")
            return 2
        sys.stdout.buffer.write(wrap(text).encode("utf-8"))
        sys.stdout.buffer.flush()
        return 0
    try:
        with open(args.file, encoding="utf-8", newline="") as fh:
            text = fh.read()
    except (OSError, ValueError):
        sys.stdout.write(json.dumps({"ok": False, "reason": "input-unreadable"}) + "\n")
        return 2
    result = check(text)
    sys.stdout.write(json.dumps(result) + "\n")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
