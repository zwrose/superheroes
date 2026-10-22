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
import symtable
import tokenize

EXTENSIONS = (".py",)
TITLE = "\x00title"

_DIRECTIVE = re.compile(r"^#\s*(type:|pyright:|mypy:|noqa|pragma)", re.IGNORECASE)
_SPACES = re.compile(r"\s+")
_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
_VALUE_REFUSED = (ast.Call, ast.Lambda, ast.NamedExpr, ast.Await, ast.Yield, ast.YieldFrom) + _COMPREHENSIONS


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


def _fixture_aliases(tree):
    """Local names the module gives ``pytest.fixture`` through ``from pytest import fixture as <alias>``."""
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and not node.level and node.module == "pytest":
            found.update(alias.asname for alias in node.names if alias.name == "fixture" and alias.asname)
    return frozenset(found)


def _is_fixture(func, aliases=frozenset()):
    """True when ``func`` (a decorator's callee) is ``fixture``, an import alias of it, or ``<anything>.fixture``."""
    return ((isinstance(func, ast.Name) and (func.id == "fixture" or func.id in aliases))
            or (isinstance(func, ast.Attribute) and func.attr == "fixture"))


def _class_globals(body):
    """Names declared ``global`` in a class body (or a nested class body), without entering a function or lambda."""
    names = set()
    stack = list(body)
    while stack:
        node = stack.pop()
        if isinstance(node, ast.Global):
            names.update(node.names)
        elif not isinstance(node, _FUNCTIONS + (ast.Lambda,)):
            stack.extend(ast.iter_child_nodes(node))
    return names


def _binds(node, out, aliases=frozenset()):
    """Names ``node`` binds at module scope, without entering a nested function, lambda, class or comprehension."""
    if isinstance(node, _FUNCTIONS):
        out.add(node.name)
        # a fixture registered under an explicit name binds that name for pytest, whatever the function is called
        for decorator in node.decorator_list:
            if not (isinstance(decorator, ast.Call) and _is_fixture(decorator.func, aliases)):
                continue
            for sub in decorator.keywords:
                if sub.arg == "name" and isinstance(sub.value, ast.Constant) and isinstance(sub.value.value, str):
                    out.add(sub.value.value)
        for sub in node.decorator_list + node.args.defaults + [d for d in node.args.kw_defaults if d]:
            _binds(sub, out, aliases)
    elif isinstance(node, ast.ClassDef):
        out.add(node.name)
        for sub in node.decorator_list + node.bases + [k.value for k in node.keywords]:
            _binds(sub, out, aliases)
        # a class body runs at import: a store, import, def or del of a name it declared global rebinds the module name
        declared = _class_globals(node.body)
        if declared:
            inner = set()
            for sub in node.body:
                _binds(sub, inner, aliases)
            out.update(inner & declared)
    elif isinstance(node, ast.Lambda):
        for sub in node.args.defaults + [d for d in node.args.kw_defaults if d]:
            _binds(sub, out, aliases)
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
            _binds(sub, out, aliases)


def _uses(node):
    """The names ``node`` depends on from outside itself: every name its own level binds or reads, the global
    reads of each nested scope (a nested scope's own locals are not dependencies, and do not hide an outer one),
    and every parameter of a function that sits at module or class level (a pytest fixture request)."""
    names = set()

    def walk(table, parent):
        # a class body's reads fall back to module and builtin names, so a class contributes every name it reads;
        # an assignment-only class attribute is not a dependency, and a compiler-mangled private name keeps both
        # spellings: the runtime name (what a module binding must not override) and the source spelling
        if parent is None:
            names.update(sym.get_name() for sym in table.get_symbols())
        elif table.get_type() == "class":
            prefix = "_" + table.get_name().lstrip("_") + "__"
            for sym in table.get_symbols():
                if sym.is_referenced():
                    sym_name = sym.get_name()
                    if table.get_name().strip("_") and sym_name.startswith(prefix) and len(sym_name) > len(prefix):
                        names.add("__" + sym_name[len(prefix):])
                    names.add(sym_name)
        else:
            names.update(sym.get_name() for sym in table.get_symbols() if sym.is_global())
        # only a real def requests fixtures: a lambda, comprehension or generator scope is a function table whose
        # name is not an identifier (``<genexpr>``) or is ``lambda``, and carries implicit parameters such as ``.0``
        name = table.get_name()
        if (table.get_type() == "function" and parent is not None and parent.get_type() in ("module", "class")
                and name.isidentifier() and name != "lambda"):
            names.update(sym.get_name() for sym in table.get_symbols()
                         if sym.is_parameter() and sym.get_name().isidentifier())
        for child in table.get_children():
            walk(child, table)

    walk(symtable.symtable(ast.unparse(node), "<break-it>", "exec"), None)
    return frozenset(names)


def _hook_name(name):
    """True for a name a test runner treats as module setup: ``pytest_*``, ``setup*`` / ``teardown*`` in any case
    (``setup_module``, ``setUpModule``) and ``load_tests``."""
    return name.lower().startswith(("pytest_", "setup", "teardown")) or name == "load_tests"


def _plain_value(value):
    """True when ``value`` (an expression or ``None``) runs no code at import: no call, lambda, walrus,
    comprehension, generator, await or yield anywhere inside it."""
    return value is None or not any(isinstance(sub, _VALUE_REFUSED) for sub in ast.walk(value))


def _allowed_host(node):
    """True when the module-level statement ``node`` is plain code a host may add around a moved test: an import,
    an undecorated def or class that is no runner hook, a constant assignment or a docstring. Anything else
    (a decorated def or class, control flow, a call statement, an augmented assignment, ``global``, ``del``,
    ``assert``, ``raise``) can change how the test runs and is not allowed."""
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return True
    if isinstance(node, _FUNCTIONS):
        # axis: a decorated def (a fixture under any spelling or alias) is a hook, and so is a runner-named def — see bite-proof record wo_a_2053_break_it_body
        return not node.decorator_list and not _hook_name(node.name)
    if isinstance(node, ast.ClassDef):
        if node.decorator_list:
            return False
        return not any(isinstance(sub, (ast.Global, ast.Nonlocal)) or getattr(sub, "decorator_list", None)
                       for sub in ast.walk(node))
    if isinstance(node, ast.Assign):
        targets, value = node.targets, [node.value]
    elif isinstance(node, ast.AnnAssign):
        targets, value = [node.target], [node.value, node.annotation]
    elif isinstance(node, ast.Expr):
        return isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
    else:
        # axis: module-level control flow, an expression statement, an augmented assignment, global, del, assert and raise are all hooks — see bite-proof record wo_a_2053_break_it_body
        return False
    if not all(isinstance(target, ast.Name) for target in targets):
        return False
    for target in targets:
        name = target.id
        if _hook_name(name) or name.startswith("pytest") or (name.startswith("__") and name.endswith("__")):
            return False
    # axis: a value that runs code at import (a call, lambda, walrus, comprehension, await or yield) is a hook — see bite-proof record wo_a_2053_break_it_body
    return all(_plain_value(part) for part in value)


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


def _record(node, directives, aliases=frozenset()):
    lo, hi = _span(node)
    mine = tuple(text for line, text in directives if lo <= line <= hi)
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        key, titles, kind = (ast.dump(node), mine), (), "import"
    else:
        clone, titles = _normalise(node)
        key, kind = (ast.dump(clone, include_attributes=False), mine), "stmt"
    binds = set()
    _binds(node, binds, aliases)
    return {"kind": kind, "key": key, "titles": titles, "imports": _import_pairs(node),
            "binds": frozenset(binds), "uses": _uses(node),
            "hook": not _allowed_host(node),
            # a relative import at any depth (inside a test function too) resolves against its file's package
            "relative": any(isinstance(sub, ast.ImportFrom) and (sub.level or 0) > 0 for sub in ast.walk(node))}


def parse(text):
    """One record per module-level statement of ``text``, in source order. Raises ``ValueError`` on any
    text it cannot read."""
    try:
        tree = ast.parse(text)
        # axis: a directive comment inside a statement is part of its key, so an added `# type: ignore` is a different test — see bite-proof record wo_a_2053_break_it_body
        directives = _directives(text)
        aliases = _fixture_aliases(tree)
        return [_record(node, directives, aliases) for node in tree.body]
    except Exception as exc:
        raise ValueError("unreadable python: %s" % type(exc).__name__) from exc
