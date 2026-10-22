"""The JS/TS front for the break-it body match (#2053).

`parse(text)` reads a JavaScript or TypeScript test file into one record per module-level statement.
Two texts give equal keys, statement for statement, only when they differ by formatting a code formatter
(prettier) would apply, or by a test title in a proven title slot. Every text the scanner cannot read
raises ValueError; a mis-scan may make two formattings unequal (fail closed) but never erases text,
because comments are kept as tokens and every other character lands in a token.

The front contract, shared with the core: EXTENSIONS, TITLE and parse(). Stdlib only; imports no other
lib module.
"""
import itertools
import re

EXTENSIONS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts")
TITLE = "\x00title"

_BREAKS = "\n\r\u2028\u2029"
_PUNCTS = (">>>= ... === !== **= <<= >>= >>> &&= ||= ??= => == != <= >= && || ?? ?. ++ -- += -= *= /= %= &= |= ^= "
           "** << >>").split()
_PUNCT_SINGLE = frozenset("{}()[];,<>+-*/%&|^!~?:=.@")
_OPEN = frozenset("([{")
_CLOSE_TO_OPEN = {")": "(", "]": "[", "}": "{"}
_OPENERS = frozenset(("punct", c) for c in "([{")
_SEMI, _COMMA, _LBRACE, _RBRACE, _LPAREN, _RPAREN, _STAR, _DOT, _ARROW = (
    ("punct", c) for c in (";", ",", "{", "}", "(", ")", "*", ".", "=>"))
_MEMBER = (_DOT, ("punct", "?."))
_TYPE, _AS, _FROM, _IMPORT = (("id", word) for word in ("type", "as", "from", "import"))

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
_EXPORT, _DEFAULT, _DECLARE, _ASYNC, _ABSTRACT, _FUNCTION, _CLASS, _STATIC, _INTERFACE = (
    ("id", word) for word in ("export default declare async abstract function class static interface").split())
_COLON, _EQUALS, _BANG, _AT = (("punct", c) for c in (":", "=", "!", "@"))
_VAR_KEYWORDS = frozenset(("const", "let", "var"))
_ASSIGNING = frozenset(("= += -= *= /= %= **= <<= >>= >>>= &= |= ^= &&= ||= ??= ++ --").split())
_RUNS_AT_LOAD = frozenset(("new", "await", "yield", "delete"))
_CALLEE_END = frozenset(("punct", c) for c in (")", "]", "}", ">", ">>", ">>>", "?."))
_ANGLES = {"<": 1, ">": -1, ">>": -2, ">>>": -3}
_MEMBER_START = frozenset(("punct", c) for c in (";", "}", "*"))
_MEMBER_MODIFIERS = frozenset(("get set async readonly public private protected override declare abstract accessor").split())
_TITLE_CALLEES = ("it", "test", "describe")
_FRAMEWORK_MODULES = frozenset(("vitest", "@jest/globals", "node:test", "bun:test"))
_TYPE_OPERATORS = frozenset(("keyof readonly infer new unique extends is asserts typeof abstract in").split())
_TYPE_ENDING = frozenset((") ] } > >> >>> ++ -- ! ; ?.").split())
_TYPE_CONTINUERS = frozenset(("| & ? : => . , = ) ] } >").split())
_NEVER_START = frozenset(("extends", "in", "instanceof", "else", "catch", "finally"))
_STATEMENT_START = frozenset((_SEMI, _LBRACE, _RBRACE))

_LINE_END = re.compile("[%s]" % _BREAKS)
_ESCAPE = re.compile(r"\\([\s\S])")
_STRINGS = {q: re.compile(r"%s(?:[^%s\\%s]|\\\r\n|\\[\s\S])*%s" % (q, q, _BREAKS, q)) for q in "\"'"}
_STOPS = {False: re.compile(r"[\\`$]"), True: re.compile(r"[\"'`/{}]")}
_REGEX = re.compile(r"/(?:\\[^{0}]|\[(?:\\[^{0}]|[^\]\\{0}])*\]|[^/\\\[{0}])*/".format(_BREAKS))
_NUMBER = re.compile(r"0[xX][0-9a-zA-Z_.]*|(?:[0-9]|\.(?=[0-9]))(?:[0-9a-zA-Z_.]|(?<=[eE])[+-])*")


def _id_start(ch):
    return ch in ("$", "_") or ch.isidentifier()


def _id_end(text, j):
    while j < len(text) and (text[j] == "$" or ("a" + text[j]).isidentifier()):
        j += 1
    return j


def _normalise_comment(body, block):
    lines = (line.strip().lstrip("*").strip() if block else line.strip() for line in body.splitlines())
    return " ".join(filter(None, lines))


def _read_comment(text, i):
    """Return (end, body, block) for the comment at text[i]."""
    if text.startswith("//", i):
        line_end = _LINE_END.search(text, i)
        end = line_end.start() if line_end else len(text)
        return end, text[i + 2:end], False
    end = text.find("*/", i + 2)
    if end < 0:
        raise ValueError("unterminated block comment")
    return end + 2, text[i + 2:end], True


def _read_string(text, i):
    """Return (end, body) for the quoted string at text[i]; the body reads \\' and \\" as the bare quote."""
    found = _STRINGS[text[i]].match(text, i)
    # axis: an unterminated string, or one cut by a line break, raises instead of reading as text — see bite-proof record wo_b_2061_break_it_body_js
    if found is None:
        raise ValueError("unterminated string")
    return found.end(), _ESCAPE.sub(lambda e: e.group(1) if e.group(1) in "'\"" else e.group(), found.group()[1:-1])


def _skip_template(text, j, sub=False):
    """Return the index just past the template literal whose body starts at text[j]; with `sub`, past the
    `${ ... }` substitution whose body starts there."""
    depth = 1
    while True:
        stop = _STOPS[sub].search(text, j)
        if stop is None:
            raise ValueError("unterminated template literal")
        j, ch = stop.start(), stop.group()
        if ch == "\\":
            j += 2
        elif ch in "\"'":
            j = _read_string(text, j)[0]
        elif ch == "`":
            if not sub:
                return j + 1
            j = _skip_template(text, j + 1)
        elif ch == "$":
            j = _skip_template(text, j + 2, True) if text.startswith("${", j) else j + 1
        elif ch == "/":
            j = _read_comment(text, j)[0] if text.startswith(("//", "/*"), j) else j + 1
        else:
            depth += 1 if ch == "{" else -1
            j += 1
            if depth == 0:
                return j


class _Tok(tuple):
    """A token (type, text) that remembers whether a line break came before it; equality and hashing are the tuple's."""
    bol = False


class _Scanner:
    """Tokenise one text, applying the emit-time normalisation (statement ends, commas, arrow parens)."""

    def __init__(self, text):
        self.text, self.out, self.stack, self.nl, self.p_ends = text, [], [], False, False

    def _sig_at(self, skip=0):
        """The index in `out` of the `skip`-th token from the end that is not a comment, or -1."""
        sig = (k for k in range(len(self.out) - 1, -1, -1) if self.out[k][0] != "comment")
        return next(itertools.islice(sig, skip, None), -1)

    def _last_sig(self, skip=0):
        k = self._sig_at(skip)
        return self.out[k] if k >= 0 else None

    def _put_semi(self):
        # axis: a semicolon, written or automatic, sits before the comments that precede it — see bite-proof record wo_b_2061_break_it_body_js
        self.out.insert(self._sig_at() + 1, _SEMI)

    def _drop_trailing_comma(self):
        k, m = self._sig_at(), self._sig_at(1)
        # axis: a comma after an opener or another comma is an array hole and stays — see bite-proof record wo_b_2061_break_it_body_js
        if k >= 0 and m >= 0 and self.out[k] == _COMMA and self.out[m] != _COMMA and self.out[m] not in _OPENERS:
            del self.out[k]

    def _emit(self, typ, txt):
        tok, prev = _Tok((typ, txt)), self._last_sig()
        tok.bol = self.nl
        starts = ((typ == "id" and txt not in _NOT_START_IDS) or typ in ("num", "str")
                  or (typ == "punct" and txt in _START_PUNCT))
        if self.nl and prev is not None and prev != _SEMI:
            # axis: after return, throw, break, continue or yield a line break is a statement end whatever follows — see bite-proof record wo_b_2061_break_it_body_js
            if (prev[0] == "id" and prev[1] in _RESTRICTED) or (self.p_ends and starts):
                self._put_semi()
        self.nl = False
        if tok == _SEMI:
            self._put_semi()
            self.p_ends = False
        elif typ == "punct" and txt in _OPEN:
            prev, before = self._last_sig(), self._last_sig(1)
            # axis: the `)` closing an if, for, while, with or catch head does not end an expression, so no automatic semicolon follows it — see bite-proof record wo_b_2061_break_it_body_js
            head = txt == "(" and prev is not None and prev[0] == "id" and (
                (prev[1] in _HEAD_IDS and before not in _MEMBER) or (prev[1] == "await" and before == ("id", "for")))
            self.stack.append((txt, head))
            self.out.append(tok)
            self.p_ends = False
        elif typ == "punct" and txt in _CLOSE_TO_OPEN:
            self._drop_trailing_comma()
            # a semicolon, written or automatic, directly before a closing brace ends nothing, so `{ a() }` and `{ a(); }` read equal
            if txt == "}" and self._last_sig() == _SEMI:
                del self.out[self._sig_at()]
            if not self.stack or self.stack[-1][0] != _CLOSE_TO_OPEN[txt]:
                raise ValueError("unbalanced brackets")
            self.out.append(tok)
            self.p_ends = not self.stack.pop()[1]
        else:
            last3 = self.out[-3:]
            if tok == _ARROW and len(last3) == 3 and last3[0] == _LPAREN and last3[1][0] == "id" and last3[2] == _RPAREN:
                self.out[-3:] = last3[1:2]
            self.out.append(tok)
            self.p_ends = ((typ == "id" and txt not in _NOT_END_IDS) or typ in ("num", "str", "tpl", "re")
                           or (typ == "punct" and txt in (")", "]", "}", "++", "--")))

    def _regex_allowed(self):
        prev = self._last_sig()
        if prev is None:
            return True
        return prev[1] not in (")", "]", "}") if prev[0] == "punct" else prev[0] == "id" and prev[1] in _REGEX_IDS

    def run(self):
        text, n, i = self.text, len(self.text), 0
        while i < n:
            c = text[i]
            if c.isspace() or c == "\ufeff":
                self.nl = self.nl or c in _BREAKS
                i += 1
            elif text.startswith(("//", "/*"), i):
                i, body, block = _read_comment(text, i)
                self.nl = self.nl or (block and any(b in body for b in _BREAKS))
                # axis: comments stay in the key as tokens, so an added or removed directive reads unequal — see bite-proof record wo_b_2061_break_it_body_js
                self.out.append(("comment", _normalise_comment(body, block)))
            elif c in "\"'":
                i, body = _read_string(text, i)
                self._emit("str", body)
            elif c == "`":
                end = _skip_template(text, i + 1)
                self._emit("tpl", text[i + 1:end - 1])
                i = end
            elif c == "/" and self._regex_allowed():
                found = _REGEX.match(text, i)
                if found is None:
                    raise ValueError("unterminated regular expression")
                j = _id_end(text, found.end())
                self._emit("re", text[i:j])
                i = j
            elif _id_start(c) or (c == "#" and _id_start(text[i + 1:i + 2])):
                j = _id_end(text, i + 1 + (c == "#"))
                self._emit("id", text[i:j])
                i = j
            elif (number := _NUMBER.match(text, i)) is not None:
                self._emit("num", number.group())
                i = number.end()
            else:
                punct = next((p for p in _PUNCTS if text.startswith(p, i)), c)
                if len(punct) == 1 and c not in _PUNCT_SINGLE:
                    raise ValueError("unknown character %r" % c)
                self._emit("punct", punct)
                i += len(punct)
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
            depth += (tok[1] in _OPEN) - (tok[1] in _CLOSE_TO_OPEN)
        if tok == _SEMI and depth == 0:
            statements.append(cur)
            cur = []
    return statements + [cur] if cur else statements


def _bad_import():
    raise ValueError("unreadable import statement")


def _specifiers(toks, i, pairs):
    """Read `{ a, b as c, type d }` starting at the `{` at toks[i]; append to pairs; return the index after `}`."""
    end = next((k for k in range(i, len(toks)) if toks[k] == _RBRACE), -1)
    if end < 0:
        _bad_import()
    groups = [[]]
    for tok in toks[i + 1:end]:
        if tok == _COMMA:
            groups.append([])
        elif tok[0] in ("id", "str"):
            groups[-1].append(tok)
        else:
            _bad_import()
    if not all(groups[:-1]):
        _bad_import()
    for group in filter(None, groups):
        type_only = len(group) in (2, 4) and group[0] == _TYPE
        core = group[1:] if type_only else group
        if len(core) == 1:
            imported = local = core[0]
        elif len(core) == 3 and core[1] == _AS:
            imported, local = core[0], core[2]
        else:
            _bad_import()
        if local[0] != "id":
            _bad_import()
        pairs.append((local[1], imported[1], type_only))
    return end + 1


def _parse_import(sig):
    """Return (imports, binds) for an import statement, or raise ValueError for a form it does not read."""
    toks = sig[:-1] if sig[-1] == _SEMI else sig
    n = len(toks)

    def at(k):
        return toks[k] if k < n else ("", "")

    if n < 2:
        _bad_import()
    if at(1)[0] == "str":
        if n != 2:
            _bad_import()
        return ((None, (toks[1][1], None)),), frozenset()
    i, type_only, pairs = 1, False, []
    if at(1) == _TYPE and n > 2:
        after = at(2)
        if after in (_LBRACE, _STAR) or (after[0] == "id" and not (after[1] == "from" and at(3)[0] == "str")):
            type_only, i = True, 2
    if at(i)[0] == "id":
        pairs.append((toks[i][1], "default", False))
        i += 1
        if at(i) == _COMMA:
            i += 1
            if at(i) not in (_LBRACE, _STAR):
                _bad_import()
        elif at(i) != _FROM:
            _bad_import()
    if at(i) == _LBRACE:
        i = _specifiers(toks, i, pairs)
    elif at(i) == _STAR:
        if not (at(i + 1) == _AS and at(i + 2)[0] == "id"):
            _bad_import()
        pairs.append((toks[i + 2][1], "*", False))
        i += 3
    if not (i + 2 == n and at(i) == _FROM and at(i + 1)[0] == "str"):
        _bad_import()
    module = toks[i + 1][1]
    if not pairs:
        return ((None, (module, None)),), frozenset()
    imports = tuple(
        (local, (module, imported, "type") if (type_only or spec_type) else (module, imported))
        for local, imported, spec_type in pairs)
    return imports, frozenset(local for local, _, _ in pairs)


def _name_of(rest):
    return frozenset(t[1] for t in rest[:1] if t[0] == "id" and t[1] not in ("extends", "implements"))


def _declarators(rest):
    """Every id in each declarator's binding part, skipping initialisers and type annotations."""
    names, depth, mode = set(), 0, "bind"
    for typ, txt in rest:
        if typ == "punct":
            depth += (txt in _OPEN) - (txt in _CLOSE_TO_OPEN)
            if depth == 0 and txt == ";":
                break
            if depth == 0 and txt == ",":
                mode = "bind"
            elif depth == 0 and txt == "=" and mode != "skip":
                mode = "skip"
            elif depth == 0 and txt == ":" and mode == "bind":
                mode = "annotation"
        elif mode == "bind" and typ == "id":
            names.add(txt)
    return frozenset(names)


def _binds(sig):
    sig = list(itertools.dropwhile(lambda t: t[0] == "id" and t[1] in _DECL_PREFIX, sig))
    if not sig or sig[0][0] != "id":
        return frozenset()
    kw, rest = sig[0][1], sig[1:]
    if kw == "function" or kw == "class" or kw in _NAMED_DECLS:
        return _name_of(rest[1:] if kw == "function" and rest[:1] == [_STAR] else rest)
    if kw == "const" and rest[:1] == [("id", "enum")]:
        return _name_of(rest[1:])
    if kw in ("const", "let", "var") and rest and (rest[0][0] == "id" or rest[0] in (("punct", "["), _LBRACE)):
        return _declarators(rest)
    return frozenset()


def _match(toks, i):
    """The index of the bracket that closes the opener at toks[i], or -1."""
    depth = 0
    for k in range(i, len(toks)):
        if toks[k][0] == "punct":
            depth += (toks[k][1] in _OPEN) - (toks[k][1] in _CLOSE_TO_OPEN)
            if depth == 0:
                return k
    return -1


def _split_top(toks, sep):
    """`toks` cut at each `sep` token that sits at bracket depth 0."""
    parts, depth = [[]], 0
    for tok in toks:
        if tok[0] == "punct":
            depth += (tok[1] in _OPEN) - (tok[1] in _CLOSE_TO_OPEN)
            if depth == 0 and tok == sep:
                parts.append([])
                continue
        parts[-1].append(tok)
    return parts


def _past_angles(toks, i):
    """The index just past the `<...>` list that opens at toks[i], or -1."""
    depth = 0
    for k in range(i, len(toks)):
        depth += _ANGLES.get(toks[k][1], 0) if toks[k][0] == "punct" else 0
        if depth <= 0:
            return k + 1 if depth == 0 else -1
    return -1


def _past_params(toks, j):
    """The index just past the parameter list that starts at toks[j], after any type parameters, or -1."""
    if toks[j:j + 1] == [("punct", "<")]:
        j = _past_angles(toks, j)
    if j < 0 or toks[j:j + 1] != [_LPAREN]:
        return -1
    close = _match(toks, j)
    return close + 1 if close >= 0 else -1


def _tail_block(tail):
    """The tokens inside the `{ }` block that is all of `tail` once an optional `: type` is skipped, else None."""
    if tail[:1] == [_COLON]:
        brace = next((k for k, tok in enumerate(tail) if tok == _LBRACE), -1)
        tail = tail[brace:] if brace >= 0 else []
    return tail[1:-1] if tail[:1] == [_LBRACE] and _match(tail, 0) == len(tail) - 1 else None


def _fn_body(toks):
    """For an arrow or `function` expression that is all of `toks`, (True, the tokens inside its `{ }` body, or None
    for an expression body); otherwise (False, None)."""
    i = 1 if toks[:1] == [_ASYNC] else 0
    if toks[i:i + 1] == [_FUNCTION]:
        j = i + 1 + (toks[i + 1:i + 2] == [_STAR])
        j += bool(toks[j:j + 1]) and toks[j][0] == "id"
        past = _past_params(toks, j)
        inner = _tail_block(toks[past:]) if past >= 0 else None
        return inner is not None, inner
    if toks[i:i + 1] and toks[i][0] == "id" and toks[i + 1:i + 2] == [_ARROW]:
        body = toks[i + 2:]
    elif toks[i:i + 1] == [_LPAREN]:
        close = _match(toks, i)
        after = toks[close + 1:] if close >= 0 else []
        if after[:1] == [_COLON]:
            after = after[next((k for k, tok in enumerate(after) if tok == _ARROW), len(after)):]
        body = after[1:] if after[:1] == [_ARROW] else []
    else:
        body = []
    if not body:
        return False, None
    return True, (body[1:-1] if body[0] == _LBRACE and _match(body, 0) == len(body) - 1 else None)


def _plain(toks):
    """True when `toks` evaluate without a call, `new`, `await`, `yield`, `delete`, tagged template or assignment."""
    for k, tok in enumerate(toks):
        typ, txt = tok
        prev, before = (toks[k - 1] if k else ("", "")), (toks[k - 2] if k > 1 else ("", ""))
        called = prev[0] == "id" or prev in _CALLEE_END or (prev == _BANG and (before[0] == "id" or before in _CALLEE_END))
        # axis: a call in an initialiser, a `(` after an identifier or a closing bracket, makes the declaration a hook — see bite-proof record wo_b_2061_break_it_body_js
        if tok == _LPAREN and called:
            return False
        if (typ == "id" and txt in _RUNS_AT_LOAD) or (typ == "punct" and txt in _ASSIGNING):
            return False
        if typ == "tpl" and ("${" in txt or called):
            return False
    return True


def _declaration(rest):
    """True when every declarator after `const`, `let` or `var` binds a name to a function or to a plain expression."""
    if rest[:1] == [("id", "enum")]:
        return False
    for piece in _split_top(rest, _COMMA):
        binding, *init = _split_top(piece, _EQUALS)
        if len(init) > 1 or not binding or not _plain(binding):
            return False
        if not (binding[0][0] == "id" or binding[0] in (("punct", "["), _LBRACE)):
            return False
        if init and not (init[0] and (_fn_body(init[0])[0] or _plain(init[0]))):
            return False
    return True


def _function_decl(rest):
    i = 1 if rest[:1] == [_ASYNC] else 0
    if rest[i:i + 1] != [_FUNCTION]:
        return False
    j = i + 1 + (rest[i + 1:i + 2] == [_STAR])
    if not (rest[j:j + 1] and rest[j][0] == "id"):
        return False
    past = _past_params(rest, j + 1)
    return past >= 0 and _tail_block(rest[past:]) is not None


def _load_free(body):
    """True when a class body has no `static` and no computed member key, the two things that run at class load."""
    depth = 0
    for k, tok in enumerate(body):
        if tok == _STATIC:
            return False
        if tok[0] == "punct":
            prev = body[k - 1] if k else _SEMI
            if tok == ("punct", "[") and depth == 0 and (
                    prev in _MEMBER_START or (prev[0] == "id" and prev[1] in _MEMBER_MODIFIERS)):
                return False
            depth += (tok[1] in _OPEN) - (tok[1] in _CLOSE_TO_OPEN)
    return True


def _class_decl(rest):
    i = 1 if rest[:1] == [_ABSTRACT] else 0
    if rest[i:i + 1] != [_CLASS] or not rest[i + 1:i + 2] or rest[i + 1][0] != "id" or rest[i + 1][1] in ("extends", "implements"):
        return False
    brace = next((k for k in range(i + 2, len(rest)) if rest[k] == _LBRACE), -1)
    if _AT in rest or brace < 0 or _match(rest, brace) != len(rest) - 1:
        return False
    heritage = rest[i + 2:brace]
    return _LPAREN not in heritage and all(tok[0] != "tpl" for tok in heritage) and _load_free(rest[brace + 1:-1])


def _continues(prev):
    """True when the token `prev` cannot end a type, so the next line still belongs to the same type."""
    return (prev[0] == "punct" and prev[1] not in _TYPE_ENDING) or (prev[0] == "id" and prev[1] in _TYPE_OPERATORS)


def _alias_contained(rest):
    """True when the tokens of a `type` alias hold no template literal and no top-level line after the first begins
    with anything but a continuation of the type (an operator after an operator, or `extends`, `in` and the like)."""
    depth = 0
    for k, tok in enumerate(rest):
        if tok[0] == "tpl":
            return False
        if k > 1 and depth == 0 and getattr(tok, "bol", False) and not _continues(rest[k - 1]):
            if not (tok[0] == "punct" and tok[1] in _TYPE_CONTINUERS) and not (tok[0] == "id" and tok[1] in _NEVER_START):
                return False
        if tok[0] == "punct":
            depth += (tok[1] in _OPEN) - (tok[1] in _CLOSE_TO_OPEN)
    return True


def _type_decl(rest):
    if rest[:1] not in ([_TYPE], [_INTERFACE]) or not rest[1:2] or rest[1][0] != "id":
        return False
    if rest[0] == _TYPE:
        # axis: a type alias holds no template literal, and no top-level line after its first starts something that is not a continuation of the type, because ASI inserts no separator before `(`, `[`, `{` or a template and such a line is a separate executable statement; over-refusing an exotic multi-line alias is accepted — see bite-proof record wo_b_2061_break_it_body_js
        return rest[2:3] in ([_EQUALS], [("punct", "<")]) and _alias_contained(rest)
    brace = next((k for k in range(2, len(rest)) if rest[k] == _LBRACE), -1)
    return brace >= 0 and _match(rest, brace) == len(rest) - 1


def _plain_params(toks):
    """True when the parameters of the arrow or `function` expression `toks` are bare names: no default value, pattern,
    rest element or type, which would evaluate (or be unreadable) when the framework calls the callback."""
    i = 1 if toks[:1] == [_ASYNC] else 0
    if toks[i:i + 1] == [_FUNCTION]:
        j = i + 1 + (toks[i + 1:i + 2] == [_STAR])
        j += bool(toks[j:j + 1]) and toks[j][0] == "id"
    elif toks[i:i + 1] == [_LPAREN]:
        j = i
    else:
        return True
    if toks[j:j + 1] != [_LPAREN]:
        return False
    close = _match(toks, j)
    return close >= 0 and all(tok[0] == "id" or tok == _COMMA for tok in toks[j + 1:close])


def _registration(toks, frameworks):
    """A top-level `it`, `test` or `describe` call: a plain title, one function and an optional timeout. A `describe`
    callback runs at collection, so each statement in its body must itself be allowed."""
    if _LPAREN not in toks:
        return False
    opening = toks.index(_LPAREN)
    callee = toks[:opening]
    # axis: a registration's callee is the bare framework name, so `it.only` and `describe.skip` are hooks — see bite-proof record wo_b_2061_break_it_body_js
    if len(callee) != 1 or callee[0][0] != "id" or callee[0][1] not in frameworks:
        return False
    if _match(toks, opening) != len(toks) - 1:
        return False
    args = _split_top(toks[opening + 1:-1], _COMMA)
    if len(args) not in (2, 3) or len(args[0]) != 1 or (len(args) == 3 and [t[0] for t in args[2]] != ["num"]):
        return False
    (typ, txt), = args[0]
    if typ != "str" and not (typ == "tpl" and "${" not in txt):
        return False
    is_fn, body = _fn_body(args[1])
    if not is_fn or callee[0][1] != "describe":
        return is_fn
    # axis: a describe callback's parameter list runs at collection before its body, so a default or pattern in it is a hook — see bite-proof record wo_b_2061_break_it_body_js
    return _plain_params(args[1]) and body is not None and all(
        _allowed_host(stmt, frameworks) for stmt in _split([tok for tok in body if tok[0] != "comment"]))


def _allowed_host(sig, frameworks):
    """True when a module-level statement outside the moved test only adds plain code or its own tests: a binding
    import, a function, class, variable or type declaration, or a test registration. Everything else is a hook."""
    toks = sig[:-1] if sig[-1:] == [_SEMI] else list(sig)
    if not toks:
        return True
    if toks[0] == _IMPORT and toks[1:2] not in ([_LPAREN], [_DOT]):
        try:
            imports = _parse_import(sig)[0]
        except ValueError:
            return False
        # axis: an import that binds no name runs the module for its effects, so it is a hook — see bite-proof record wo_b_2061_break_it_body_js
        return any(local is not None for local, _ in imports)
    exported = toks[0] == _EXPORT
    rest = toks[1:] if exported else toks
    default = rest[:1] == [_DEFAULT]
    rest = rest[1:] if default else rest
    first = rest[0] if rest else ("", "")
    if first in (_ASYNC, _FUNCTION):
        return _function_decl(rest)
    if first in (_ABSTRACT, _CLASS):
        return _class_decl(rest)
    if default:
        return False
    if first[0] == "id" and first[1] in _VAR_KEYWORDS:
        return _declaration(rest[1:])
    if first == _DECLARE:
        return _type_decl(rest[1:])
    if first in (_TYPE, _INTERFACE):
        return _type_decl(rest)
    return not exported and _registration(rest, frameworks)


def _framework_names(stmts):
    """The title callees (it, test, describe) that name the test framework in this file."""
    bound, imported, loose = set(), {}, set()
    for _toks, sig, is_import, imports, binds in stmts:
        # a callee name that appears anywhere but as a call or member head may be a parameter, binding or value, so it is no framework name
        if not is_import:
            loose.update(here[1] for here, after in zip(sig, sig[1:] + [("", "")])
                         if here[0] == "id" and here[1] in _TITLE_CALLEES and after not in (_LPAREN, _DOT))
        if is_import:
            for local, target in imports:
                if local is not None:
                    imported.setdefault(local, set()).add(target[0])
                    # a local name bound to a different imported name (`expect as test`) or by a default import is never a framework name
                    if target[1] != local:
                        bound.add(local)
        else:
            bound |= binds
        bound.update(after[1] for here, after in zip(sig, sig[1:])
                     if here[0] == "id" and here[1] in _DECLARING and after[0] == "id")
    # axis: a callee the file binds or imports from a non-framework module is not a framework name — see bite-proof record wo_b_2061_break_it_body_js
    return frozenset(
        name for name in _TITLE_CALLEES
        if name not in bound and name not in loose and imported.get(name, set()) <= _FRAMEWORK_MODULES)


def _keyed(toks, frameworks):
    key, titles = list(toks), []
    for i, tok in enumerate(toks):
        slot = toks[i + 1:i + 4]
        if not (tok[0] == "id" and tok[1] in frameworks and len(slot) == 3 and slot[0] == _LPAREN
                and (slot[1][0] == "str" or (slot[1][0] == "tpl" and "${" not in slot[1][1])) and slot[2] in (_COMMA, _RPAREN)):
            continue
        prior = [t for t in toks[:i] if t[0] != "comment"]
        # axis: a title slot is a call at statement start, not an expression that happens to be named it — see bite-proof record wo_b_2061_break_it_body_js
        if not prior or prior[-1] in _STATEMENT_START:
            titles.append(slot[1][1])
            key[i + 2] = ("str", TITLE)
    return tuple(key), tuple(titles)


def _relative(sig, imports):
    """True when the statement imports a module by a `./` or `../` path: an import statement, or a `require(...)` or
    `import(...)` call, whose module string is relative. Such a statement resolves against its own directory."""
    if any(not _bare_module("str", target[0]) for _, target in imports):
        return True
    # axis: only a plain, escape-free bare package name is non-relative; a template (substitution or not) or a string spelled with a backslash escape is never decoded, so it counts as relative and the move is refused — see bite-proof record wo_b_2061_break_it_body_js
    return any(here in (("id", "require"), _IMPORT) and after == _LPAREN
               and mod[0] in ("str", "tpl") and not _bare_module(*mod)
               for here, after, mod in zip(sig, sig[1:], sig[2:]))


def _bare_module(typ, text):
    """True only for a module spelling known to be a bare package name: no backslash, no `${`, no leading `./` or `../`."""
    return "\\" not in text and not (typ == "tpl" and "${" in text) and not text.startswith(("./", "../"))


def source_names(text):
    """The identifiers that appear as names in `text`, outside comments, strings, templates and regular expressions,
    read with the JS/TS scanner; raises ValueError for text it cannot read."""
    return {tok[1] for tok in _Scanner(text).run() if tok[0] == "id"}


def _parse(text):
    stmts = []
    for toks in _split(_Scanner(text).run()):
        sig = [t for t in toks if t[0] != "comment"]
        is_import = sig[:1] == [_IMPORT] and sig[1:2] not in ([_LPAREN], [_DOT])
        imports, binds = _parse_import(sig) if is_import else ((), _binds(sig))
        stmts.append((toks, sig, is_import, imports, binds))
    frameworks = _framework_names(stmts)
    records = []
    for toks, sig, is_import, imports, binds in stmts:
        key, titles = _keyed(toks, frameworks)
        uses = frozenset(tok[1] for prev, tok in zip([None] + sig, sig) if tok[0] == "id" and prev not in _MEMBER)
        records.append({"kind": "import" if is_import else "stmt", "key": key, "titles": titles, "imports": imports,
                        "binds": binds, "uses": uses, "hook": not _allowed_host(sig, frameworks),
                        "relative": _relative(sig, imports)})
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
