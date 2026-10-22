"""The JS/TS front for the break-it body match (#2053).

`parse(text)` reads a JavaScript or TypeScript test file into one record per module-level statement.
Two texts give equal keys, statement for statement, only when they differ by formatting a code formatter
(prettier) would apply, or by a test title in a proven title slot. Every text the scanner cannot read
raises ValueError; a mis-scan may make two formattings unequal (fail closed) but never erases text,
because comments are kept as tokens and every other character lands in a token.

The front contract, shared with the core: EXTENSIONS, TITLE and parse(). Stdlib only; imports no other
lib module.
"""

EXTENSIONS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts")
TITLE = "\x00title"

_BREAKS = "\n\r  "
_DIGITS = "0123456789"
_PUNCT_MULTI = {
    4: frozenset((">>>=",)),
    3: frozenset(("...", "===", "!==", "**=", "<<=", ">>=", ">>>", "&&=", "||=", "??=")),
    2: frozenset(("=>", "==", "!=", "<=", ">=", "&&", "||", "??", "?.", "++", "--", "+=", "-=", "*=", "/=",
                  "%=", "&=", "|=", "^=", "**", "<<", ">>")),
}
_PUNCT_SINGLE = frozenset("{}()[];,<>+-*/%&|^!~?:=.@")
_OPEN = frozenset("([{")
_CLOSE_TO_OPEN = {")": "(", "]": "[", "}": "{"}
_SEMI = ("punct", ";")
_COMMA = ("punct", ",")
_LBRACE = ("punct", "{")
_STAR = ("punct", "*")
_MEMBER = (("punct", "."), ("punct", "?."))

_REGEX_IDS = frozenset(("return typeof case do else in instanceof new delete void throw yield await of").split())
_RESTRICTED = frozenset(("return", "throw", "break", "continue", "yield"))
_HEAD_IDS = frozenset(("if", "for", "while", "with", "catch"))
_NOT_END_IDS = frozenset((
    "if else for while do switch case default try catch finally function class const let var new delete typeof "
    "void in instanceof of import export extends implements await async as satisfies").split())
_NOT_START_IDS = frozenset(("else catch finally in of instanceof as satisfies extends implements").split())
_START_PUNCT = frozenset(("++", "--", "!", "~", "@"))

_DECL_PREFIX = frozenset(("export", "default", "declare", "abstract", "async"))
_NAMED_DECLS = frozenset(("enum", "interface", "type", "namespace", "module"))
_DECLARING = frozenset(("const", "let", "var", "function", "class"))
_HOOKS = frozenset(("beforeEach", "beforeAll", "afterEach", "afterAll"))
_HOOK_OBJECTS = frozenset(("vi", "jest"))
_TITLE_CALLEES = ("it", "test", "describe")
_FRAMEWORK_MODULES = frozenset(("vitest", "@jest/globals", "node:test", "bun:test"))
_STATEMENT_START = frozenset((_SEMI, _LBRACE, ("punct", "}")))


def _is_digit(ch):
    return ch != "" and ch in _DIGITS


def _id_start(ch):
    return ch == "$" or ch == "_" or ch.isidentifier()


def _id_part(ch):
    return ch == "$" or ("a" + ch).isidentifier()


def _normalise_comment(body, block):
    parts = []
    for line in body.splitlines():
        line = line.strip()
        if block:
            line = line.lstrip("*").strip()
        if line:
            parts.append(line)
    return " ".join(parts)


def _read_string(text, i):
    """Return (end, body) for the quoted string at text[i]; the body reads \\' and \\" as the bare quote."""
    quote, n, j, parts = text[i], len(text), i + 1, []
    while True:
        ch = text[j] if j < n else ""
        if ch == quote:
            return j + 1, "".join(parts)
        # axis: an unterminated string, or one cut by a line break, raises instead of reading as text — see bite-proof record wo_b_2053_break_it_body_js
        if ch == "" or ch in _BREAKS:
            raise ValueError("unterminated string")
        if ch == "\\":
            nxt = text[j + 1:j + 2]
            if nxt in ("'", '"'):
                parts.append(nxt)
            elif nxt == "\r" and text[j + 2:j + 3] == "\n":
                parts.append("\\\r\n")
                j += 3
                continue
            else:
                parts.append(ch + nxt)
            j += 2
            continue
        parts.append(ch)
        j += 1


def _skip_template(text, j):
    """Return the index just past the template literal whose body starts at text[j]."""
    n = len(text)
    while True:
        if j >= n:
            raise ValueError("unterminated template literal")
        ch = text[j]
        if ch == "\\":
            j += 2
        elif ch == "`":
            return j + 1
        elif ch == "$" and text.startswith("${", j):
            j = _skip_substitution(text, j + 2)
        else:
            j += 1


def _skip_substitution(text, j):
    """Return the index just past the `${ ... }` substitution whose body starts at text[j]."""
    n, depth = len(text), 1
    while True:
        if j >= n:
            raise ValueError("unterminated template literal")
        ch = text[j]
        if ch in "\"'":
            j = _read_string(text, j)[0]
        elif ch == "`":
            j = _skip_template(text, j + 1)
        elif text.startswith("//", j):
            while j < n and text[j] not in _BREAKS:
                j += 1
        elif text.startswith("/*", j):
            end = text.find("*/", j + 2)
            if end < 0:
                raise ValueError("unterminated block comment")
            j = end + 2
        elif ch == "{":
            depth += 1
            j += 1
        elif ch == "}":
            depth -= 1
            j += 1
            if depth == 0:
                return j
        else:
            j += 1


def _ends_expression(tok, head_close):
    typ, txt = tok
    if typ == "id":
        return txt not in _NOT_END_IDS
    if typ in ("num", "str", "tpl", "re"):
        return True
    if typ == "punct":
        if txt == ")":
            return not head_close
        return txt in ("]", "}", "++", "--")
    return False


def _starts_expression(tok):
    typ, txt = tok
    if typ == "id":
        return txt not in _NOT_START_IDS
    if typ in ("num", "str"):
        return True
    return typ == "punct" and txt in _START_PUNCT


class _Scanner:
    """Tokenise one text, applying the emit-time normalisation (statement ends, commas, arrow parens)."""

    def __init__(self, text):
        self.text = text
        self.out = []
        self.stack = []
        self.nl = False
        self.p_ends = False

    def _last_sig(self, skip=0):
        seen = 0
        for k in range(len(self.out) - 1, -1, -1):
            tok = self.out[k]
            if tok[0] == "comment":
                continue
            if seen == skip:
                return tok
            seen += 1
        return None

    def _put_semi(self):
        # axis: a semicolon, written or automatic, sits before the comments that precede it — see bite-proof record wo_b_2053_break_it_body_js
        j = len(self.out)
        while j > 0 and self.out[j - 1][0] == "comment":
            j -= 1
        self.out.insert(j, _SEMI)

    def _comment(self, body, block):
        # axis: comments stay in the key as tokens, so an added or removed directive reads unequal — see bite-proof record wo_b_2053_break_it_body_js
        self.out.append(("comment", _normalise_comment(body, block)))

    def _is_head(self):
        """True when the `(` about to be emitted opens the head of an if, for, while, with or catch."""
        # axis: the `)` closing such a head does not end an expression, so no automatic semicolon follows it — see bite-proof record wo_b_2053_break_it_body_js
        prev = self._last_sig()
        if prev is None or prev[0] != "id":
            return False
        if prev[1] in _HEAD_IDS:
            return self._last_sig(1) not in _MEMBER
        return prev[1] == "await" and self._last_sig(1) == ("id", "for")

    def _needs_semi(self, prev, tok):
        # axis: after return, throw, break, continue or yield a line break is a statement end whatever follows — see bite-proof record wo_b_2053_break_it_body_js
        if prev[0] == "id" and prev[1] in _RESTRICTED:
            return True
        return self.p_ends and _starts_expression(tok)

    def _drop_trailing_comma(self):
        k = len(self.out) - 1
        while k >= 0 and self.out[k][0] == "comment":
            k -= 1
        if k < 0 or self.out[k] != _COMMA:
            return
        m = k - 1
        while m >= 0 and self.out[m][0] == "comment":
            m -= 1
        # axis: a comma after an opener or another comma is an array hole and stays — see bite-proof record wo_b_2053_break_it_body_js
        if m < 0 or self.out[m] == _COMMA or (self.out[m][0] == "punct" and self.out[m][1] in _OPEN):
            return
        del self.out[k]

    def _emit(self, typ, txt):
        tok = (typ, txt)
        prev = self._last_sig()
        if self.nl and prev is not None and prev != _SEMI and self._needs_semi(prev, tok):
            self._put_semi()
        self.nl = False
        if typ == "punct":
            if txt == ";":
                self._put_semi()
                self.p_ends = False
                return
            if txt in _OPEN:
                self.stack.append((txt, txt == "(" and self._is_head()))
                self.out.append(tok)
                self.p_ends = False
                return
            if txt in _CLOSE_TO_OPEN:
                self._drop_trailing_comma()
                if not self.stack or self.stack[-1][0] != _CLOSE_TO_OPEN[txt]:
                    raise ValueError("unbalanced brackets")
                head = self.stack.pop()[1]
                self.out.append(tok)
                self.p_ends = not head
                return
            if txt == "=>" and len(self.out) >= 3 and self.out[-1] == ("punct", ")") \
                    and self.out[-2][0] == "id" and self.out[-3] == ("punct", "("):
                self.out[-3:] = [self.out[-2]]
        self.out.append(tok)
        self.p_ends = _ends_expression(tok, False)

    def _regex_allowed(self):
        prev = self._last_sig()
        if prev is None:
            return True
        if prev[0] == "punct":
            return prev[1] not in (")", "]", "}")
        return prev[0] == "id" and prev[1] in _REGEX_IDS

    def _read_regex(self, i):
        text, n, j, in_class = self.text, len(self.text), i + 1, False
        while True:
            ch = text[j] if j < n else ""
            if ch == "" or ch in _BREAKS:
                raise ValueError("unterminated regular expression")
            if ch == "\\":
                if text[j + 1:j + 2] in _BREAKS:
                    raise ValueError("unterminated regular expression")
                j += 2
                continue
            if ch == "[":
                in_class = True
            elif ch == "]":
                in_class = False
            elif ch == "/" and not in_class:
                break
            j += 1
        j += 1
        while j < n and _id_part(text[j]):
            j += 1
        return j

    def _read_number(self, i):
        text, n = self.text, len(self.text)
        hexlike = text[i:i + 2] in ("0x", "0X")
        j = i + 1
        while j < n:
            ch = text[j]
            if ch.isascii() and (ch.isalnum() or ch in "_."):
                j += 1
            elif ch in "+-" and text[j - 1] in "eE" and not hexlike:
                j += 1
            else:
                break
        return j

    def run(self):
        text, n = self.text, len(self.text)
        i = 0
        while i < n:
            c = text[i]
            if c in _BREAKS:
                self.nl = True
                i += 1
            elif c.isspace() or c == "﻿":
                i += 1
            elif text.startswith("//", i):
                j = i + 2
                while j < n and text[j] not in _BREAKS:
                    j += 1
                self._comment(text[i + 2:j], False)
                i = j
            elif text.startswith("/*", i):
                j = text.find("*/", i + 2)
                if j < 0:
                    raise ValueError("unterminated block comment")
                body = text[i + 2:j]
                if any(b in body for b in _BREAKS):
                    self.nl = True
                self._comment(body, True)
                i = j + 2
            elif c in "\"'":
                i, body = _read_string(text, i)
                self._emit("str", body)
            elif c == "`":
                end = _skip_template(text, i + 1)
                self._emit("tpl", text[i + 1:end - 1])
                i = end
            elif c == "/" and self._regex_allowed():
                j = self._read_regex(i)
                self._emit("re", text[i:j])
                i = j
            elif _id_start(c) or (c == "#" and _id_start(text[i + 1:i + 2] or " ")):
                j = i + 2 if c == "#" else i + 1
                while j < n and _id_part(text[j]):
                    j += 1
                self._emit("id", text[i:j])
                i = j
            elif _is_digit(c) or (c == "." and _is_digit(text[i + 1:i + 2])):
                j = self._read_number(i)
                self._emit("num", text[i:j])
                i = j
            else:
                for size in (4, 3, 2):
                    if text[i:i + size] in _PUNCT_MULTI[size]:
                        self._emit("punct", text[i:i + size])
                        i += size
                        break
                else:
                    if c not in _PUNCT_SINGLE:
                        raise ValueError("unknown character %r" % c)
                    self._emit("punct", c)
                    i += 1
        if self.stack:
            raise ValueError("unbalanced brackets")
        prev = self._last_sig()
        if prev is not None and prev != _SEMI and self.p_ends:
            self._put_semi()
        return self.out


def _split(tokens):
    """Split the token list into module-level statements: each ends after a `;` at bracket depth 0."""
    statements, cur, depth = [], [], 0
    for tok in tokens:
        cur.append(tok)
        if tok[0] == "punct":
            if tok[1] in _OPEN:
                depth += 1
            elif tok[1] in _CLOSE_TO_OPEN:
                depth -= 1
            elif tok[1] == ";" and depth == 0:
                statements.append(cur)
                cur = []
    if cur:
        statements.append(cur)
    return statements


def _is_import(sig):
    return bool(sig) and sig[0] == ("id", "import") and (len(sig) < 2 or sig[1] not in (("punct", "("), ("punct", ".")))


def _bad_import():
    raise ValueError("unreadable import statement")


def _read_specifiers(toks, i, pairs):
    """Read `{ a, b as c, type d }` starting at the `{` at toks[i]; append to pairs; return the index after `}`."""
    n, group, groups = len(toks), [], []
    i += 1
    while True:
        if i >= n:
            _bad_import()
        tok = toks[i]
        if tok == ("punct", "}"):
            if group:
                groups.append(group)
            return i + 1 if _flush(groups, pairs) else _bad_import()
        if tok == _COMMA:
            if not group:
                _bad_import()
            groups.append(group)
            group = []
        elif tok[0] in ("id", "str"):
            group.append(tok)
        else:
            _bad_import()
        i += 1


def _flush(groups, pairs):
    for group in groups:
        type_only = False
        if len(group) == 1:
            imported, local = group[0], group[0]
        elif len(group) == 2 and group[0] == ("id", "type") and group[1][0] == "id":
            type_only, imported, local = True, group[1], group[1]
        elif len(group) == 3 and group[1] == ("id", "as"):
            imported, local = group[0], group[2]
        elif len(group) == 4 and group[0] == ("id", "type") and group[2] == ("id", "as"):
            type_only, imported, local = True, group[1], group[3]
        else:
            return False
        if local[0] != "id":
            return False
        pairs.append((local[1], imported[1], type_only))
    return True


def _parse_import(sig):
    """Return (imports, binds) for an import statement, or raise ValueError for a form it does not read."""
    toks = list(sig)
    if toks and toks[-1] == _SEMI:
        toks.pop()
    n = len(toks)
    if n < 2:
        _bad_import()
    if toks[1][0] == "str":
        if n != 2:
            _bad_import()
        return ((None, (toks[1][1], None)),), frozenset()
    i, type_only, pairs = 1, False, []
    if toks[1] == ("id", "type") and n > 2:
        after = toks[2]
        if after in (_LBRACE, _STAR) or (after[0] == "id" and not (after[1] == "from" and n > 3 and toks[3][0] == "str")):
            type_only, i = True, 2
    if i < n and toks[i][0] == "id":
        pairs.append((toks[i][1], "default", False))
        i += 1
        if i < n and toks[i] == _COMMA:
            i += 1
            if i >= n or toks[i] not in (_LBRACE, _STAR):
                _bad_import()
        elif not (i < n and toks[i] == ("id", "from")):
            _bad_import()
    if i < n and toks[i] == _LBRACE:
        i = _read_specifiers(toks, i, pairs)
    elif i < n and toks[i] == _STAR:
        if not (i + 2 < n and toks[i + 1] == ("id", "as") and toks[i + 2][0] == "id"):
            _bad_import()
        pairs.append((toks[i + 2][1], "*", False))
        i += 3
    if not (i + 2 == n and toks[i] == ("id", "from") and toks[i + 1][0] == "str"):
        _bad_import()
    module = toks[i + 1][1]
    if not pairs:
        return ((None, (module, None)),), frozenset()
    imports = tuple(
        (local, (module, imported, "type") if (type_only or spec_type) else (module, imported))
        for local, imported, spec_type in pairs)
    return imports, frozenset(local for local, _, _ in pairs)


def _name_of(rest):
    if rest and rest[0][0] == "id" and rest[0][1] not in ("extends", "implements"):
        return frozenset((rest[0][1],))
    return frozenset()


def _declarators(rest):
    """Every id in each declarator's binding part, skipping initialisers and type annotations."""
    names, depth, mode = set(), 0, "bind"
    for typ, txt in rest:
        if typ == "punct":
            if txt in _OPEN:
                depth += 1
            elif txt in _CLOSE_TO_OPEN:
                depth -= 1
            elif depth == 0 and txt == ";":
                break
            elif depth == 0 and txt == ",":
                mode = "bind"
                continue
            elif depth == 0 and txt == "=" and mode != "skip":
                mode = "skip"
                continue
            elif depth == 0 and txt == ":" and mode == "bind":
                mode = "annotation"
                continue
        if mode == "bind" and typ == "id":
            names.add(txt)
    return frozenset(names)


def _binds(sig):
    i = 0
    while i < len(sig) and sig[i][0] == "id" and sig[i][1] in _DECL_PREFIX:
        i += 1
    if i >= len(sig) or sig[i][0] != "id":
        return frozenset()
    kw, rest = sig[i][1], sig[i + 1:]
    if kw == "function":
        return _name_of(rest[1:] if rest and rest[0] == _STAR else rest)
    if kw == "class" or kw in _NAMED_DECLS:
        return _name_of(rest)
    if kw in ("const", "let", "var") and rest:
        if kw == "const" and rest[0] == ("id", "enum"):
            return _name_of(rest[1:])
        if rest[0][0] == "id" or (rest[0][0] == "punct" and rest[0][1] in ("[", "{")):
            return _declarators(rest)
    return frozenset()


def _is_hook(sig):
    if len(sig) < 2 or sig[0][0] != "id":
        return False
    if sig[0][1] in _HOOKS:
        return sig[1] == ("punct", "(")
    return sig[0][1] in _HOOK_OBJECTS and sig[1] == ("punct", ".")


def _uses(sig):
    return frozenset(
        tok[1] for k, tok in enumerate(sig)
        if tok[0] == "id" and not (k > 0 and sig[k - 1] in _MEMBER))


def _framework_names(infos):
    """The title callees (it, test, describe) that name the test framework in this file."""
    # axis: a callee the file binds or imports from a non-framework module is not a framework name — see bite-proof record wo_b_2053_break_it_body_js
    bound, imported = set(), {}
    for kind, _toks, sig, imports, binds in infos:
        if kind == "stmt":
            bound |= binds
        else:
            for local, target in imports:
                if local is not None:
                    imported.setdefault(local, set()).add(target[0])
        for here, after in zip(sig, sig[1:]):
            if here[0] == "id" and here[1] in _DECLARING and after[0] == "id":
                bound.add(after[1])
    return frozenset(
        name for name in _TITLE_CALLEES
        if name not in bound and imported.get(name, set()) <= _FRAMEWORK_MODULES)


def _is_title_slot(toks, i):
    if i + 3 >= len(toks) or toks[i + 1] != ("punct", "(") or toks[i + 2][0] not in ("str", "tpl"):
        return False
    if toks[i + 3] not in (_COMMA, ("punct", ")")):
        return False
    j = i - 1
    while j >= 0 and toks[j][0] == "comment":
        j -= 1
    # axis: a title slot is a call at statement start, not an expression that happens to be named it — see bite-proof record wo_b_2053_break_it_body_js
    return j < 0 or toks[j] in _STATEMENT_START


def _keyed(toks, frameworks):
    key, titles = list(toks), []
    for i, tok in enumerate(toks):
        if tok[0] == "id" and tok[1] in frameworks and _is_title_slot(toks, i):
            titles.append(toks[i + 2][1])
            key[i + 2] = ("str", TITLE)
    return tuple(key), tuple(titles)


def _parse(text):
    infos = []
    for toks in _split(_Scanner(text).run()):
        sig = [t for t in toks if t[0] != "comment"]
        if _is_import(sig):
            imports, binds = _parse_import(sig)
            infos.append(("import", toks, sig, imports, binds))
        else:
            infos.append(("stmt", toks, sig, (), _binds(sig)))
    frameworks = _framework_names(infos)
    records = []
    for kind, toks, sig, imports, binds in infos:
        key, titles = _keyed(toks, frameworks)
        records.append({
            "kind": kind,
            "key": key,
            "titles": titles,
            "imports": imports,
            "binds": binds,
            "uses": _uses(sig),
            "hook": kind == "stmt" and _is_hook(sig),
        })
    return records


def parse(text):
    """Return one record per module-level statement of `text`; raise ValueError for any text it cannot read."""
    if not isinstance(text, str):
        raise ValueError("source text must be a string")
    try:
        return _parse(text)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("unreadable JS/TS source: %s" % exc) from exc
