#!/usr/bin/env python3
"""The Python front of the break-it body search (#2053): one record per module-level statement.

Stdlib only. ``break_it_body`` loads this module lazily and compares statements by ``key``, a
normalised syntax tree: quotes, parentheses, line breaks, comments and blank lines drop out, while
decorators, indentation, tuple commas and directive comments (``# type:``, ``# noqa`` ...) stay
semantic. ``parse`` raises ``ValueError`` and only ``ValueError``; it never returns a partial list."""
import ast
import copy
import io
import re
import tokenize

EXTENSIONS = (".py",)
TITLE = "\x00title"

_DIRECTIVE = re.compile(r"^#\s*(type:|pyright:|mypy:|noqa|pragma)", re.IGNORECASE)
_SPACES = re.compile(r"\s+")
_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
_HOOK_NAMES = frozenset(["pytestmark", "pytest_plugins", "setup_module", "teardown_module", "setUpModule",
                         "tearDownModule", "setup_function", "teardown_function", "load_tests"])


def _directives(text):
    """``[(line, normalised comment)]`` for every directive comment in ``text``."""
    found = []
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type == tokenize.COMMENT and _DIRECTIVE.match(tok.string):
            found.append((tok.start[0], _SPACES.sub(" ", tok.string)))
    return found


def _span(node):
    first = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
    return first, node.end_lineno


def _import_pairs(node):
    pairs = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.asname:
                pairs.append((alias.asname, ("import", alias.name)))
            else:
                pairs.append((alias.name.split(".")[0], ("import", alias.name.split(".")[0])))
    elif isinstance(node, ast.ImportFrom):
        for alias in node.names:
            target = ("from", node.level or 0, node.module or "", alias.name)
            pairs.append(("*" if alias.name == "*" else alias.asname or alias.name, target))
    return tuple(pairs)


def _binds(node, out):
    """Names ``node`` binds at module scope, without entering a nested function, lambda, class or comprehension."""
    if isinstance(node, _FUNCTIONS):
        out.add(node.name)
        for sub in node.decorator_list + node.args.defaults + [d for d in node.args.kw_defaults if d]:
            _binds(sub, out)
    elif isinstance(node, ast.ClassDef):
        out.add(node.name)
        for sub in node.decorator_list + node.bases + [k.value for k in node.keywords]:
            _binds(sub, out)
    elif isinstance(node, ast.Lambda):
        for sub in node.args.defaults + [d for d in node.args.kw_defaults if d]:
            _binds(sub, out)
    elif isinstance(node, _COMPREHENSIONS):
        # a walrus inside a comprehension binds in the enclosing scope
        for sub in ast.walk(node):
            if isinstance(sub, ast.NamedExpr) and isinstance(sub.target, ast.Name):
                out.add(sub.target.id)
    elif isinstance(node, ast.Name):
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            out.add(node.id)
    elif isinstance(node, ast.Global):
        out.update(node.names)
    elif isinstance(node, (ast.Import, ast.ImportFrom)):
        out.update(local for local, _ in _import_pairs(node) if local != "*")
    else:
        if isinstance(node, ast.ExceptHandler) and node.name:
            out.add(node.name)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            out.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            out.add(node.rest)
        for sub in ast.iter_child_nodes(node):
            _binds(sub, out)


def _uses(node):
    names = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            names.add(sub.id)
        elif isinstance(sub, ast.arg):
            names.add(sub.arg)
        elif isinstance(sub, _FUNCTIONS + (ast.ClassDef,)):
            names.add(sub.name)
        elif isinstance(sub, (ast.Import, ast.ImportFrom)):
            names.update(local for local, _ in _import_pairs(sub) if local != "*")
    return frozenset(names)


def _autouse(node):
    if not isinstance(node, _FUNCTIONS):
        return False
    for decorator in node.decorator_list:
        for sub in ast.walk(decorator):
            if (isinstance(sub, ast.keyword) and sub.arg == "autouse"
                    and not (isinstance(sub.value, ast.Constant) and sub.value.value is False)):
                return True
    return False


def _normalise(node):
    """``(copy, titles)``: ``node`` with the name of each ``test*`` function that is the statement itself, or a
    direct child of a module-level class, replaced by ``TITLE``."""
    clone = copy.deepcopy(node)
    targets = [clone] if isinstance(clone, _FUNCTIONS) else []
    if isinstance(clone, ast.ClassDef):
        targets = [child for child in clone.body if isinstance(child, _FUNCTIONS)]
    titles = []
    for target in targets:
        # axis: only a function named test* is a title; any other name is part of the compared tree — see bite-proof record wo_a_2053_break_it_body
        if target.name.startswith("test"):
            titles.append(target.name)
            target.name = TITLE
    return clone, tuple(titles)


def _record(node, directives):
    lo, hi = _span(node)
    mine = tuple(text for line, text in directives if lo <= line <= hi)
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        key, titles, kind = (ast.dump(node), mine), (), "import"
    else:
        clone, titles = _normalise(node)
        key, kind = (ast.dump(clone, include_attributes=False), mine), "stmt"
    binds = set()
    _binds(node, binds)
    return {"kind": kind, "key": key, "titles": titles, "imports": _import_pairs(node),
            "binds": frozenset(binds), "uses": _uses(node),
            "hook": _autouse(node) or bool(binds & _HOOK_NAMES)}


def parse(text):
    """One record per module-level statement of ``text``, in source order. Raises ``ValueError`` on any
    text it cannot read."""
    try:
        tree = ast.parse(text)
        # axis: a directive comment inside a statement is part of its key, so an added `# type: ignore` is a different test — see bite-proof record wo_a_2053_break_it_body
        directives = _directives(text)
        return [_record(node, directives) for node in tree.body]
    except Exception as exc:
        raise ValueError("unreadable python: %s" % type(exc).__name__) from exc
