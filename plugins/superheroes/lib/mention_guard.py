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
# A code element; a backslash-escaped `\<code>` is literal text, so it masks nothing.
_CODE_ELEMENT_RE = re.compile(r"(?<!\\)<code>.*?</code>", re.IGNORECASE)
# A link destination, an angle autolink or a bare URL: GitHub renders each as an anchor (or an attribute), and its
# mention filter skips anchors, so an at-sign inside one is part of the address, never a mention. A link destination
# may hold one level of balanced parentheses.
_URL_RE = re.compile(r"\]\((?:[^()\s]|\([^()\s]*\))*\)?|<[A-Za-z][A-Za-z0-9+.-]*:[^\s<>]*>|\b(?:https?|ftp)://[^\s<>()]+", re.IGNORECASE)


def _urls(line):
    """The extents of the link destinations and URLs on one line."""
    return [(m.start(), m.end()) for m in _URL_RE.finditer(line)]


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


def _indented(line):
    """True when `line` starts with whitespace."""
    return line[:1] in (" ", "\t")


def _has_unescaped_pipe(line):
    """True when `line` holds a pipe not preceded by a backslash (a table row, with or without a leading pipe)."""
    return any(ch == "|" and (i == 0 or line[i - 1] != "\\") for i, ch in enumerate(line))


def _inside(spans, pos):
    return any(start <= pos < stop for start, stop in spans)


def _html_lines(bare, fenced):
    """Which lines sit in a raw HTML block: from a line that opens one through the line before the next blank
    line. Inside one, fence-shaped lines are literal text and backticks make no code span. A tag on a line
    inside a fenced block (`fenced`, the fence mask read without HTML context) is code, so it opens no block."""
    html = [False] * len(bare)
    in_html = False
    for k, line in enumerate(bare):
        if not line.strip():
            in_html = False
            continue
        # axis: a tag inside a fenced block is code, so it never starts an HTML block
        if in_html or (_HTML_BLOCK_RE.match(line) and not fenced[k]):
            in_html = html[k] = True
    return html


def _inert_lines(bare, html):
    """Which lines sit inside a fenced block that every reading agrees is a fenced block. `md_fence` reads a fence
    inside a list or blockquote as top-level text, so such a fence shows up as a block whose opener or closer is
    indented, and its indented closer can pair with a later column-0 fence. A block masks its lines (opener through
    closer, or through the end when unterminated, which GFM renders as code) only when its opener line has no
    leading whitespace and, when closed, its closer line has none either, and its opener is not inside a raw HTML
    block (`md_fence` does not see HTML blocks); any other block masks nothing."""
    kinds = md_fence.scan(bare).kinds
    n = len(bare)
    inert = [False] * n
    i = 0
    while i < n:
        if kinds[i] != md_fence.KIND_OPENER:
            i += 1
            continue
        j = i + 1
        while j < n and kinds[j] == md_fence.KIND_CONTENT:
            j += 1
        closed = j < n and kinds[j] == md_fence.KIND_CLOSER
        last = j if closed else n - 1
        # axis: a fence masks its lines only when its opener (and, closed, its closer) is at column 0
        # axis: a fence-shaped line inside a raw HTML block is literal text, so it opens no masking fence
        if not html[i] and not _indented(bare[i]) and not (closed and _indented(bare[last])):
            for k in range(i, last + 1):
                inert[k] = True
        i = last + 1
    return inert


def _found(text):
    """Every bare mention of `text` as `(line index, start, end, mention, html)` in text order; `start` is the
    at-sign and `html` says the line sits in a raw HTML block, where a code span is not code."""
    bare = [_bare_line(whole) for whole in md_fence.split_lines(text)]
    html = _html_lines(bare, _inert_lines(bare, [False] * len(bare)))
    inert = _inert_lines(bare, html)
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
