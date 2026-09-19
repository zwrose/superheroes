"""Deterministic half of order lint (#1339); semantic half is a Haiku seat
(prompt: ``rubric/orders/order-lint-semantic.md``).

Reads the authored order text only — never the runner-augmented prompt.
``--expect-item`` paths arrive as declarations, not as citations to resolve.
Tokens (one finding each when triggered):
- ``order-unreadable`` — the order file is missing, empty, or not UTF-8 text.
- ``order-repo-root-unresolved`` — ``--repo-root`` or ``--alt-root`` is absent or unreadable.
- ``order-path-unresolved`` — a cited repo-relative path with a known extension does not exist.
- ``order-placeholder-unfilled`` — a ``{{NAME}}`` or ``{name}`` placeholder remains in the text.
- ``order-result-shape-ambiguous`` — the order names more than one result contract.
- ``order-budget-missing`` — an implementer order lacks a command-budget declaration.
- ``order-kind-unknown`` — ``--kind`` is not ``implementer`` or ``fixer``.
Per-kind table:
| check | implementer | fixer |
|---|---|---|
| order-unreadable | yes | yes |
| order-repo-root-unresolved | yes | yes |
| order-path-unresolved | yes | yes |
| order-placeholder-unfilled | yes | yes |
| order-result-shape-ambiguous | yes | yes |
| order-budget-missing | yes | no |
| order-kind-unknown | other kind; alone | |

Limitations: no-slash/extensionless tokens skip the path check; a ``budget`` word
within 60 characters of any integer satisfies the budget rule.
"""
from __future__ import annotations

import argparse
import json
import os
import posixpath
import re
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

TOKEN_UNREADABLE = "order-unreadable"
TOKEN_REPO_ROOT_UNRESOLVED = "order-repo-root-unresolved"
TOKEN_PATH_UNRESOLVED = "order-path-unresolved"
TOKEN_PLACEHOLDER_UNFILLED = "order-placeholder-unfilled"
TOKEN_RESULT_SHAPE_AMBIGUOUS = "order-result-shape-ambiguous"
TOKEN_BUDGET_MISSING = "order-budget-missing"
TOKEN_KIND_UNKNOWN = "order-kind-unknown"
TOKENS = (
    TOKEN_UNREADABLE, TOKEN_REPO_ROOT_UNRESOLVED, TOKEN_PATH_UNRESOLVED,
    TOKEN_PLACEHOLDER_UNFILLED, TOKEN_RESULT_SHAPE_AMBIGUOUS, TOKEN_BUDGET_MISSING,
    TOKEN_KIND_UNKNOWN,
)
KINDS = ("implementer", "fixer")
EXTENSIONS = (
    ".py", ".md", ".json", ".yml", ".yaml", ".txt", ".sh", ".toml", ".ini", ".cfg",
    ".js", ".ts", ".tsx", ".jsx", ".css", ".html", ".sql", ".csv", ".jsonl",
)
_EMPTY = {"paths": 0, "placeholders": 0}
_DBL_PH = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")
_SGL_PH = re.compile(r"(?<![{$])\{([A-Za-z_][A-Za-z0-9_.-]*)\}(?!\})")
_BTICK = re.compile(r"`([^`\n]+)`")
_FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
_SUFFIX = re.compile(r":(?:\d+(?:-\d+)?|:[\w.-]+)$")
_EX_AFTER = re.compile(r"\((?:new file|new|create|created)\)", re.I)
_BUDGET = re.compile(r"budget.{0,60}(\d+)|(\d+).{0,60}budget", re.I | re.DOTALL)
_BUDGET_AT = re.compile(r"at most \d+ (?:command|invocation)", re.I)
# Prose aliases for result-channel lint — not protocol values.
_STDOUT_ALIASES = ("marker channel", "marker parser")
_NATIVE = ('"resultKind"', "--output-schema")
# Driver-bound verify-command token — not an unfilled order placeholder.
_DRIVER_PH = frozenset({"baseRef"})


def _load_result_vocab():
    try:
        import engine_adapter
        import payload_contracts
        contract, reason = payload_contracts.payload_contract(payload_contracts.P_FIXER)
        if reason:
            raise RuntimeError(reason)
        key = contract["required"][0]
        return (
            engine_adapter.WRITE_REPORT_SENTINEL,
            '{"' + key + '"',
            "canonical",
        )
    except Exception:
        return "<<<SUPERHEROES-WRITE-REPORT>>>", '{"fixes"', "fallback"


_WRITE_SENTINEL, _FIXER_LITERAL, _VOCAB_SOURCE = _load_result_vocab()
_STDOUT_PROTOCOL = (_WRITE_SENTINEL, _FIXER_LITERAL)


def _mask_fences(text):
    return _FENCE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def _f(token, detail=""):
    return {"token": token, "detail": detail}


def _refuse(kind, token, detail):
    return {"ok": False, "kind": kind, "findings": [_f(token, detail)], "checked": _EMPTY}


def _norm_item(raw):
    if not isinstance(raw, str) or not raw.strip():
        return False, "empty"
    s = raw.strip()
    if "\\" in s:
        return False, "backslash"
    if s.startswith("/"):
        return False, "absolute"
    if s.endswith("/"):
        return False, "directory"
    n = posixpath.normpath(s)
    if n in (".", "..") or any(p == ".." for p in n.split("/")):
        return False, "escapes-root"
    return True, n


def _cand(tok):
    if tok.startswith(("http://", "https://")):
        return False
    if "/" not in tok or tok.startswith(("/", "~", "$", "{", "<", "-")):
        return False
    if any(c in tok for c in "*?<>{}|`"):
        return False
    base = tok.rsplit("/", 1)[-1]
    i = base.rfind(".")
    return i > 0 and base[i:] in EXTENSIONS


def _resolve(rel, roots):
    n = posixpath.normpath(rel)
    if n in (".", "..") or any(p == ".." for p in n.split("/")):
        return False, "escapes-root"
    escaped = False
    for root in roots:
        joined = os.path.join(root, n)
        rr, rj = os.path.realpath(root), os.path.realpath(joined)
        if rj != rr and not rj.startswith(rr + os.sep):
            escaped = True
            continue
        if os.path.exists(joined):
            return True, ""
    return False, ("escapes-root" if escaped else "")


def _exempt(line, o, c, tok, expect):
    if posixpath.normpath(tok) in expect:
        return True
    return bool(_EX_AFTER.search(line[c:c + 12]))


def _gather_exempt(text, expect):
    exempt = set()
    inline = _mask_fences(text)
    for m in _BTICK.finditer(inline):
        ls = text.rfind("\n", 0, m.start()) + 1
        le = text.find("\n", m.end())
        line = text[ls:le if le >= 0 else len(text)]
        o_base = m.start() - ls
        for raw in m.group(1).split():
            tok = _SUFFIX.sub("", raw.strip().strip("\"'`,()"))
            if not _cand(tok):
                continue
            o = line.find(raw, o_base)
            if o < 0:
                o = line.find(tok, o_base)
            c = o + len(raw) if o >= 0 else o_base
            if _exempt(line, o, c, tok, expect):
                exempt.add(posixpath.normpath(tok))
    for m in _FENCE.finditer(text):
        for ln in m.group(1).splitlines():
            pos = 0
            for raw in ln.split():
                tok = _SUFFIX.sub("", raw.strip().strip("\"'`,()"))
                if not _cand(tok):
                    continue
                o = ln.find(raw, pos)
                if o < 0:
                    o = ln.find(tok, pos)
                c = o + len(raw) if o >= 0 else pos
                if _exempt(ln, o, c, tok, expect):
                    exempt.add(posixpath.normpath(tok))
                pos = c if o >= 0 else pos + len(raw)
    return exempt


def _region(text, expect, roots, skip, out, seen, exempt, line=None, o=None, c=None):
    for raw in text.split():
        tok = _SUFFIX.sub("", raw.strip().strip("\"'`,()"))
        if not _cand(tok) or tok in seen:
            continue
        if posixpath.normpath(tok) in exempt:
            continue
        seen.add(tok)
        if skip:
            continue
        ok, why = _resolve(tok, roots)
        if not ok:
            out.append(_f(TOKEN_PATH_UNRESOLVED, tok + (":" + why if why else "")))


def _paths(text, expect, roots, skip):
    exempt = _gather_exempt(text, expect)
    out, seen = [], set()
    inline = _mask_fences(text)
    for m in _BTICK.finditer(inline):
        ls = inline.rfind("\n", 0, m.start()) + 1
        le = inline.find("\n", m.end())
        line = inline[ls:le if le >= 0 else len(inline)]
        _region(m.group(1), expect, roots, skip, out, seen, exempt,
                line, m.start() - ls, m.end() - ls)
    for m in _FENCE.finditer(text):
        for ln in m.group(1).splitlines():
            _region(ln, expect, roots, skip, out, seen, exempt)
    prose = _BTICK.sub(" ", inline)
    for ln in prose.splitlines():
        _region(ln, expect, roots, skip, out, seen, exempt)
    return out, len(seen)


def _placeholders(text):
    hits = [(m.start(), m.group(1)) for m in _DBL_PH.finditer(text)]
    hits += [(m.start(), m.group(1)) for m in _SGL_PH.finditer(text)]
    hits.sort()
    out, seen = [], set()
    for _, name in hits:
        if name in _DRIVER_PH or name in seen:
            continue
        seen.add(name)
        out.append(_f(TOKEN_PLACEHOLDER_UNFILLED, name))
    return out, len(seen)


def _shape(text, expect_items):
    sh = [s for s in _STDOUT_PROTOCOL + _STDOUT_ALIASES if s in text]
    nt = [s for s in _NATIVE if s in text]
    if sh and nt:
        return _f(TOKEN_RESULT_SHAPE_AMBIGUOUS, "+".join(sh + nt))
    if _FIXER_LITERAL in text and expect_items:
        return _f(TOKEN_RESULT_SHAPE_AMBIGUOUS, _FIXER_LITERAL + "+expect-item")
    return None


def _budget_ok(text):
    return bool(_BUDGET_AT.search(text) or _BUDGET.search(text))


def _root_ok(path):
    return isinstance(path, str) and path and os.path.isdir(path) and os.access(path, os.R_OK)


def check_text(text, repo_root, expect_items=(), alt_roots=(), kind="implementer"):
    if not isinstance(text, str):
        return _refuse(kind, TOKEN_UNREADABLE, "not-text")
    if not text.strip():
        return _refuse(kind, TOKEN_UNREADABLE, "empty")
    if kind not in KINDS:
        return _refuse(kind, TOKEN_KIND_UNKNOWN, kind)
    findings, skip, roots = [], False, []
    if not _root_ok(repo_root):
        findings.append(_f(TOKEN_REPO_ROOT_UNRESOLVED, str(repo_root)))
        skip = True
    else:
        roots.append(repo_root)
    for alt in alt_roots:
        if _root_ok(alt):
            roots.append(alt)
        else:
            findings.append(_f(TOKEN_REPO_ROOT_UNRESOLVED, str(alt)))
    expect = set()
    for item in expect_items:
        ok, res = _norm_item(item)
        if ok:
            expect.add(res)
        else:
            findings.append(_f(TOKEN_PATH_UNRESOLVED, "%s:%s" % (item, res)))
    ph, pc = _placeholders(text)
    findings.extend(ph)
    pf, path_n = _paths(text, expect, roots, skip)
    findings.extend(pf)
    amb = _shape(text, expect_items)
    if amb:
        findings.append(amb)
    if kind == "implementer" and not _budget_ok(text):
        findings.append(_f(TOKEN_BUDGET_MISSING, ""))
    return {"ok": not findings, "kind": kind, "findings": findings,
            "checked": {"paths": path_n, "placeholders": pc},
            "vocabSource": _VOCAB_SOURCE}


def check(order_path, repo_root, expect_items=(), alt_roots=(), kind="implementer"):
    try:
        with open(order_path, encoding="utf-8", errors="strict") as fh:
            text = fh.read()
    except FileNotFoundError:
        return _refuse(kind, TOKEN_UNREADABLE, "missing:%s" % order_path)
    except UnicodeDecodeError as exc:
        return _refuse(kind, TOKEN_UNREADABLE, "utf-8:%s" % exc)
    except OSError as exc:
        return _refuse(kind, TOKEN_UNREADABLE, str(exc))
    if not text.strip():
        return _refuse(kind, TOKEN_UNREADABLE, "empty")
    return check_text(text, repo_root, expect_items, alt_roots, kind)


class _LintArgumentParser(argparse.ArgumentParser):
    """Raise RuntimeError on usage errors so main can emit JSON instead of SystemExit."""

    def error(self, message):
        raise RuntimeError(message)


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    p = _LintArgumentParser(prog="order_lint.py")
    sub = p.add_subparsers(dest="command")
    cp = sub.add_parser("check")
    cp.add_argument("--order", required=True)
    cp.add_argument("--repo-root", required=True)
    cp.add_argument("--expect-item", action="append", default=[])
    cp.add_argument("--expect-items-file")
    cp.add_argument("--alt-root", action="append", default=[])
    cp.add_argument("--kind", default="implementer")
    try:
        args = p.parse_args(argv)
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "findings": [_f(TOKEN_UNREADABLE, "usage:%s" % exc)]}))
        return 1
    if args.command != "check":
        print(json.dumps({"ok": False, "findings": [_f(TOKEN_UNREADABLE, "usage:unknown subcommand")]}))
        return 1
    items = list(args.expect_item)
    if args.expect_items_file:
        try:
            fh = open(args.expect_items_file, encoding="utf-8")
            with fh:
                for line in fh:
                    s = line.strip()
                    if s and not s.startswith("#"):
                        items.append(s)
        except OSError:
            d = "expect-items-file:%s" % args.expect_items_file
            print(json.dumps({"ok": False, "findings": [_f(TOKEN_UNREADABLE, d)]}))
            return 1
    result = check(args.order, args.repo_root, items, tuple(args.alt_root), args.kind)
    print(json.dumps(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
