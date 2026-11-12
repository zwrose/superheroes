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

# axis: a bare at-sign (or its character code) GitHub reads as a login, outside fences and code spans, is reported — see bite-proof record wo_2453_mention_guard
MENTION_RE = re.compile(
    r"(?:^|(?<=\W))(?:@|&#0*64;|&#x0*40;|&commat;)((?>[a-z0-9][a-z0-9-]*))(?=\.+[ \t\W]|\.+$|[^0-9a-zA-Z_.]|$)",
    re.IGNORECASE | re.MULTILINE,
)
_BACKTICK_RUN_RE = re.compile(r"`+")
# A line that opens a raw HTML block (GFM block kinds 6 and 7, approximated: a tag at the line's start).
_HTML_BLOCK_RE = re.compile(r"^ {0,3}</?[A-Za-z][A-Za-z0-9-]*(?:[\s/>]|$)")
# A raw-text HTML block opener (GFM block kind 1): it ends at a line holding any kind-1 closing tag, not at a
# blank line.
_RAW_HTML_RE = re.compile(r"^ {0,3}<(pre|script|style|textarea)(?=[\s>]|$)", re.IGNORECASE | re.ASCII)
_RAW_HTML_CLOSE_RE = re.compile(r"</(?:pre|script|style|textarea)>", re.IGNORECASE | re.ASCII)
_HTML_OTHER_BLOCK_RE = re.compile(r"^ {0,3}<[!?]")  # a comment, instruction, declaration or CDATA block (GFM 2-5)
_TAG_START_RE = re.compile(r"<[A-Za-z/!?]")  # an HTML tag, comment or autolink start, escaped-looking or not
_QUOTE_RE = re.compile("[\"']")
_BLANK_RE = re.compile(r"[ \t]*")  # GFM's blank line: ASCII spaces and tabs only (a no-break space is text)
_CHAIN_RE = re.compile(r"(?:[\w.-]*@[\w-]*)*")  # at-signs attached after a mention
# Tag patterns fold case over ASCII only, so no look-alike closes a block. A code element masks; `\<code>` is literal.
_CODE_ELEMENT_RE = re.compile(r"(?<!\\)<code>.*?</code>", re.IGNORECASE | re.ASCII)
# A bare http(s) URL GitHub links (its mention filter skips anchors): a scheme spelt out, a host of ASCII letters,
# digits, dots and hyphens (an underscore host stays text); a path running into a backtick, pipe or bracket masks
# nothing. Unicode word and space classes stop it early, which over-reports. No link or angle shape masks anything.
_URL_RE = re.compile(r"\b[Hh][Tt][Tt][Pp][Ss]?://[A-Za-z0-9][A-Za-z0-9.-]*(?:[/?#:][^\s<>()`|\[\]]*)?"
                     r"(?![^\s<>()])")


def _urls(line):
    """The extents of the bare URLs with a host on one line."""
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
    # axis: a span after a tag start not certainly closed may sit in an attribute: it and later spans mask nothing
    for n, (start, _stop) in enumerate(spans):
        tags = _TAG_START_RE.finditer(line, spans[n - 1][1] if n else 0, start)
        if any(not _ends(line[m.start():start]) for m in tags):
            return spans[:n]
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


def _ends(segment):
    """True when the tag, comment, instruction or CDATA that opens `segment` certainly ends inside it."""
    for opener, terminator in (("<!--", "-->"), ("<?", "?>"), ("<![CDATA[", "]]>")):
        if segment.startswith(opener):
            return terminator in segment[len(opener):]
    end = segment.find(">")
    return end > 1 and not _QUOTE_RE.search(segment, 0, end)


def _has_unescaped_pipe(line):
    """True when `line` holds a pipe not preceded by a backslash (a table row, with or without a leading pipe)."""
    return any(ch == "|" and (i == 0 or line[i - 1] != "\\") for i, ch in enumerate(line))


def _inside(spans, pos):
    return any(start <= pos < stop for start, stop in spans)


def _contexts(bare):
    """`(inert, html)`: which lines sit in a fenced block and which in a raw HTML block, read in one pass. A fence
    opens only at column 0 (an indented one masks nothing and consumes its own closer) and masks through a column-0
    closer or, unterminated, to the end; one closing on an indented closer masks nothing. A raw HTML block opens on a
    tag at a line's start outside a fence and runs to the next blank line; a fence-shaped line in it is literal."""
    inert = [False] * len(bare)
    html = [False] * len(bare)
    fence, fence_start = None, 0
    shadow = None
    raw_close = None
    in_html = False
    fences_off = False
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
            if _BLANK_RE.fullmatch(line):
                in_html = False
                continue
            # axis: a fence-shaped line inside a raw HTML block is literal text, so it opens no fence
            html[k] = True
            continue
        other = _HTML_OTHER_BLOCK_RE.match(line)
        # axis: once a comment or declaration block stays open past its line, no column-0 fence masks
        fences_off = fences_off or bool(other and not _ends(line[other.end() - 2:]))
        indented = _INDENTED_FENCE_RE.match(line)
        if indented and not (indented.group(1)[0] == "`" and "`" in indented.group(2)):
            shadow = indented.group(1)
            html[k] = True
            continue
        opener = None if fences_off else _FENCE_OPENER_RE.match(line)
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
            # axis: on a raw HTML line only a code element masks; a URL there is literal text GitHub may mention in
            # axis: a code element holding a quote, or on a line holding `<!`, may sit in an attribute or comment: no mask
            elements = [m.span() for m in _CODE_ELEMENT_RE.finditer(line) if "<!" not in line and not _QUOTE_RE.search(m.group())]
            out.extend((idx, m.start(), m.end(), "@" + m.group(1), True) for m in MENTION_RE.finditer(line)
                       if not any(start <= m.start() < stop for start, stop in elements))
            idx += 1
            continue
        if inert[idx] or _BLANK_RE.fullmatch(line):
            idx += 1
            continue
        end = idx
        while end < len(bare) and not inert[end] and not _BLANK_RE.fullmatch(bare[end]) and not html[end]:
            end += 1
        # axis: a block may start on any line of the run, so each reading from an earlier line must agree
        readings = [_code_spans("\n".join(bare[s:end])) for s in range(idx, end)]
        starts = [sum(len(r) + 1 for r in bare[idx:j]) for j in range(idx, end)]
        for k in range(idx, end):
            row = bare[k]
            cell_spans = _cell_spans(row) if _has_unescaped_pipe(row) else None
            urls = _urls(row)
            for m in MENTION_RE.finditer(row):
                # axis: code masks a mention only when every reading agrees: from each line of the run on, and its cell
                if (all(_inside(readings[s], starts[k - idx] - starts[s] + m.start()) for s in range(k - idx + 1))
                        and (cell_spans is None or _inside(cell_spans, m.start()))):
                    continue
                # axis: an at-sign inside a hosted bare URL is part of the address, so it is never reported
                if _inside(urls, m.start()):
                    continue
                out.append((k, m.start(), m.end(), "@" + m.group(1), False))
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
    """`text` with every bare mention, and any at-sign attached after it, in a code span whose backtick run is one
    longer than any in `text`, a space keeping it off an adjacent backtick or backslash. Idempotent; text with no
    bare mention, and non-string text, comes back unchanged."""
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
        merged = []
        for start, end, html in extents:
            # axis: an at-sign attached after the token goes in the same span, so wrapping exposes no new mention
            end += len(_CHAIN_RE.match(line, end).group())
            if merged and start < merged[-1][1]:
                start = merged.pop()[0]
            merged.append((start, end, html))
        for start, end, html in reversed(merged):
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
