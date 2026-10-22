#!/usr/bin/env python3
"""Find a break-it test by what it checks, not by its bytes (#2053).

Stdlib only. ``locate`` takes the test file the loop ran and the files the final diff carries, and
says whether the test's statements (its fixture and assertions) appear unchanged, up to formatting
and the test's title, exactly once at module level of one of them. The language fronts
(``break_it_body_py``, ``break_it_body_js``) parse a file into one record per module-level statement;
this module compares the records and refuses whatever it cannot compare: every unreadable file, every
second copy, every binding the host file changes and every module-level test setup the host adds.
Nothing is raised, and a result that is not ``found`` never reads as kept."""
import importlib
import io
import os
import posixpath
import sys
import tokenize

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

_FRONTS = ("break_it_body_py", "break_it_body_js")


def _fronts():
    """The loaded fronts; one that is missing is skipped, so its suffixes read unsupported."""
    loaded = []
    for name in _FRONTS:
        try:
            loaded.append(importlib.import_module(name))
        except ImportError:
            continue
    return loaded


def supported_suffixes():
    return frozenset(suffix for front in _fronts() for suffix in front.EXTENSIONS)


def _suffix(path):
    return posixpath.splitext(path.lower())[1] if isinstance(path, str) else ""


def pytest_collected(path):
    """True only when the front that reads ``path`` declares ``PYTEST_COLLECTION`` (the Python front): its titles are
    function names pytest collects by pattern, so a caller gates repository pytest configuration on it. False for a
    path no front reads and for any front that does not declare the flag."""
    return bool(getattr(_front_for(_suffix(path)), "PYTEST_COLLECTION", False))


def js_collected(path):
    """True only when the front that reads ``path`` declares ``JS_COLLECTION`` (the JS/TS front): its titles are
    ``it``/``test``/``describe`` strings a vitest or jest configuration can filter by name, so a caller gates
    repository vitest/vite/jest configuration on it. False for a path no front reads and for any front that does
    not declare the flag."""
    return bool(getattr(_front_for(_suffix(path)), "JS_COLLECTION", False))


def _type_names(rec):
    """The local names ``rec`` binds by a TypeScript type-only import (its own specifier, or the whole statement,
    is marked ``type``): TypeScript erases them, so they bind no runtime value."""
    return {local for local, target in rec["imports"] if local is not None and len(target) == 3 and target[2] == "type"}


def _result(status, reason=None, path=None, titles=None):
    return {"status": status, "reason": reason, "path": path, "titles": titles or []}


def _unresolved(reason):
    return _result("unresolved", reason)


def _front_for(suffix):
    for front in _fronts():
        if suffix in front.EXTENSIONS:
            return front
    return None


def _relative(rec):
    return bool(rec.get("relative", False))


def _source_names(content, front=None):
    """The identifiers that appear as names in ``content``, outside comments and strings, read by the selected
    front when it declares ``source_names`` (a JS comment or regular expression is not Python), else by Python's
    tokenizer."""
    reader = getattr(front, "source_names", None)
    if reader is not None:
        return reader(content)
    return {tok.string for tok in tokenize.generate_tokens(io.StringIO(content).readline) if tok.type == tokenize.NAME}


def _futures(records, python=True):
    """The ``__future__`` features the module's records import. Only the Python front's import targets have the
    ``("from", level, module, name)`` shape; a JS target starts with its module name, so a module literally named
    ``from`` or ``__future__`` is never read here (``python`` is false for any front that is not pytest-collected)."""
    if not python:
        return set()
    return {pair[1][3] for rec in records for pair in rec["imports"]
            if pair[1][0] == "from" and pair[1][1] == 0 and pair[1][2] == "__future__"}


def _may_import_fixture(pair, python=True):
    """True when ``pair`` (a bound name and its import target) is a ``from`` import, which can bring in a fixture.
    A module name proves nothing (a project-local file can shadow a standard-library name), so every ``from``
    import is suspect, relative or absolute, except the compiler's own absolute ``from __future__``; a relative
    ``from .__future__`` reads a project file like any other. The caller allows one only when the original
    carries the identical binding. A plain ``import x`` binds a module object, which pytest never registers."""
    if not python:
        return False
    target = pair[1]
    # axis: only an absolute (level 0) from-import of exactly __future__ is exempt; a relative one (from .__future__ import x) loads a project-local module that can define an autouse fixture — see bite-proof record wo_a_2053_break_it_body
    return target[0] == "from" and not (target[1] == 0 and target[2] == "__future__")


def _runtime_imports(records):
    """``[(module, pairs)]``, one per import record that still evaluates a module once its type-only bindings are
    dropped, in file order; a record whose every binding is type-only is erased by TypeScript and left out."""
    out = []
    for rec in records:
        types = _type_names(rec)
        pairs = frozenset(pair for pair in rec["imports"] if pair[0] is None or pair[0] not in types)
        if pairs:
            out.append((next(iter(pairs))[1][0], pairs))
    return out


def _rebinds(records):
    """True when a module binds one local name by more than one import, or by an import and any other module-level
    binding: which binding wins then depends on statement order, which the comparison does not model."""
    seen, types = {}, set()
    for index, rec in enumerate(records):
        for local, target in rec["imports"]:
            # an effect-only import binds no name (local None)
            if local == "*" or local is None:
                continue
            if local in seen:
                return True
            seen[local] = index
            # axis: a type-only import (its target ends in "type") binds no runtime value, so a value declaration of the same name does not rebind it — see bite-proof record wo_b_2061_break_it_body_js
            if len(target) == 3 and target[2] == "type":
                types.add(local)
    for index, rec in enumerate(records):
        if any(seen.get(name, index) != index and name not in types for name in rec["binds"]):
            return True
    return False


def _outside(records, window, original, moved=False, python=True):
    """The refusal reason for the first candidate record outside the matched window that changes what the test
    means, else ``None``. ``moved`` is true when the candidate sits in a different directory than the original."""
    orig_pairs = {pair for rec in original for pair in rec["imports"]}
    names = set()
    for rec in original:
        names |= rec["binds"] | rec["uses"]
    # the matched copy's own bindings (a renamed test's new name) are protected too, so a later definition cannot overwrite it
    for index in window:
        names |= records[index]["binds"]
    window_binds = set()
    for index in window:
        window_binds |= records[index]["binds"]
    # axis: a relative import resolves against its file's package, so a test moved to another directory cannot keep one — see bite-proof record wo_a_2053_break_it_body
    if moved and any(_relative(rec) for rec in original):
        return "binding-conflict"
    # axis: the future compiler features (annotations semantics) of the original and the host must match — see bite-proof record wo_a_2053_break_it_body
    if _futures(original, python) != _futures(records, python):
        return "binding-conflict"
    # axis: a name the original or the host binds by two imports (or an import and another module-level binding) is refused, because import order then decides the binding — see bite-proof record wo_a_2053_break_it_body
    if _rebinds(original):
        return "binding-conflict"
    # axis: every import the original bound is bound the same way in the file that holds the test — see bite-proof record wo_a_2053_break_it_body
    if not orig_pairs <= {pair for rec in records for pair in rec["imports"]}:
        return "binding-conflict"
    for index, rec in enumerate(records):
        if index in window:
            continue
        # axis: a type-only binding (its own specifier, or its whole import, marked "type") binds no runtime value, so the two window-name checks below exempt that binding alone and check every runtime binding of the same record — see bite-proof record wo_b_2061_break_it_body_js
        types = _type_names(rec)
        # axis: module-level test setup the host adds is refused, because it would change the test's run — see bite-proof record wo_a_2053_break_it_body
        # axis: an effect-only import (no bound name) is judged by the in-order comparison after this loop, so a retained one is not host setup — see bite-proof record wo_b_2061_break_it_body_js
        if rec["hook"] and not (rec["kind"] == "import" and rec["imports"] and all(pair[0] is None for pair in rec["imports"])):
            return "host-setup"
        for pair in rec["imports"]:
            if pair in orig_pairs:
                continue
            # axis: a name the host imports with a from-import (any module, relative or not: a project file can shadow a standard-library name) may be a fixture, and pytest registers an imported autouse fixture as module setup, so it is refused — see bite-proof record wo_a_2053_break_it_body
            if _may_import_fixture(pair, python):
                return "host-setup"
            # axis: an import outside the window that rebinds a name the test uses, or star-imports over it, is refused — see bite-proof record wo_a_2053_break_it_body
            if pair[0] == "*" or pair[0] in names:
                return "binding-conflict"
        # axis: a statement outside the window that rebinds a name the test uses is refused — see bite-proof record wo_a_2053_break_it_body
        if rec["kind"] == "stmt" and rec["binds"] & names:
            return "binding-conflict"
        # axis: any record outside the window that binds a name the matched window binds (a renamed test's new name) overwrites or is overwritten by a retained test, so it is refused — see bite-proof record wo_a_2053_break_it_body
        if (rec["binds"] - types) & window_binds:
            return "binding-conflict"
        # axis: any record outside the window that names a definition the window binds can mutate or disable the test (TestR.__unittest_skip__ = True), so it is refused — see bite-proof record wo_a_2053_break_it_body
        if (rec["uses"] - types) & window_binds:
            return "binding-conflict"
    # axis: when either file holds an effect-only import, every runtime import of the original (effect-only and named, by module and binding) appears in the host in the original's order (an effect-only import runs its module's code, so moving one across a named import changes the fixture the test sees), and the host holds no effect-only import the original lacks; an added, repeated or reordered one is host setup. A type-only binding is dropped first, because TypeScript erases it and it evaluates nothing; a module in two runtime records keeps both positions — see bite-proof record wo_b_2061_break_it_body_js
    old_runtime, new_runtime = (_runtime_imports(recs) for recs in (original, records))
    old_all, new_all = ([pair for _, pairs in seq for pair in pairs] for seq in (old_runtime, new_runtime))
    if any(pair[0] is None for pair in old_all + new_all):
        # each original import record is matched, in order, to a later host record of the same module that binds
        # every one of its runtime bindings (specifier order inside one statement evaluates nothing)
        remaining = iter(new_runtime)
        if ([pair for pair in new_all if pair[0] is None] != [pair for pair in old_all if pair[0] is None]
                or not all(any(mod == new_mod and pairs <= new_pairs for new_mod, new_pairs in remaining)
                           for mod, pairs in old_runtime)):
            return "host-setup"
    # the host's own rebinding is checked last, so a more specific refusal above (host-setup) keeps its reason
    if _rebinds(records):
        return "binding-conflict"
    return None


def _namespaces(recs):
    """``{namespace: [names]}``: the names bound by defs and classes, grouped by the module (one namespace) or by each
    record's own class body."""
    spaces = {}
    for pos, rec in enumerate(recs):
        for scope, name in rec.get("defs", ()):
            spaces.setdefault("m" if scope == "m" else pos, []).append(name)
    return spaces


def _collides(original, matched):
    """True when a rename gave two names of one namespace the same spelling that were distinct in the original's
    same namespace. ``original`` and ``matched`` are the equal-keyed statement records, in order."""
    old, new = _namespaces(original), _namespaces(matched)
    for space, olds in old.items():
        news = new.get(space, [])
        if len(news) != len(olds):
            return True
        for i in range(len(olds)):
            for j in range(i + 1, len(olds)):
                if olds[i] != olds[j] and news[i] == news[j]:
                    return True
    return False


def locate(content, path, candidates):
    """Find the test ``content`` (the file at ``path``) in ``candidates``, a list of ``(path, text)`` where ``text``
    is the decoded file or ``None`` when it could not be decoded.

    Returns ``{"status", "reason", "path", "titles"}``. ``status`` is ``unsupported`` (no front reads
    ``path``), ``none`` (no candidate holds the test), ``unresolved`` (``reason`` says why the search
    cannot decide) or ``found`` (``path`` is the candidate; ``titles`` the ``(old, new)`` pairs that differ).
    Whether the front is pytest-collected is a property of the front: see ``pytest_collected``."""
    front = _front_for(_suffix(path))
    if front is None:
        return _result("unsupported")
    try:
        original = front.parse(content)
    except ValueError:
        return _unresolved("body-unparseable")
    body = [rec for rec in original if rec["kind"] == "stmt"]
    if not body:
        return _unresolved("body-empty")
    old_titles = [title for rec in body for title in rec["titles"]]
    names = set()
    for rec in body:
        names |= rec["binds"] | rec["uses"]
    names -= set(old_titles)
    # the textual prefilter requires only names that occur in the original's own text: a derived runtime spelling
    # (a mangled private name) never makes an identical candidate fail it
    try:
        spelled = _source_names(content, front)
    except Exception:
        return _unresolved("body-unparseable")
    prefilter = {name for name in names if name in spelled}
    keys = [rec["key"] for rec in body]
    unparseable = False
    matches = []
    for cand_path, text in candidates:
        if _suffix(cand_path) not in front.EXTENSIONS:
            continue
        if text is None:
            unparseable = True
            continue
        if not all(name in text for name in prefilter):
            continue
        try:
            records = front.parse(text)
        except ValueError:
            # axis: a candidate that passes the prefilter and cannot be read leaves the search undecided, even beside a match — see bite-proof record wo_a_2053_break_it_body
            unparseable = True
            continue
        stmts = [index for index, rec in enumerate(records) if rec["kind"] == "stmt"]
        for start in range(len(stmts) - len(body) + 1):
            window = stmts[start:start + len(body)]
            if [records[i]["key"] for i in window] == keys:
                matches.append((cand_path, records, window))
    if unparseable:
        return _unresolved("body-unparseable")
    if not matches:
        return _result("none")
    # axis: a second copy of the test anywhere in the diff makes the match ambiguous, never kept — see bite-proof record wo_a_2053_break_it_body
    if len(matches) > 1:
        return _unresolved("match-ambiguous")
    cand_path, records, window = matches[0]
    moved = posixpath.dirname(cand_path) != posixpath.dirname(path)
    reason = _outside(records, set(window), original, moved, getattr(front, "PYTEST_COLLECTION", False))
    if reason:
        return _unresolved(reason)
    new_titles = [title for i in window for title in records[i]["titles"]]
    # axis: a renamed pytest test must keep the ``test_`` prefix, because a project may collect only ``test_*`` and a rename to ``testing_x`` would leave it uncollected while the host still passes; the rule is a property of the front (``PYTEST_COLLECTION``), since a JS/TS title is an ``it``/``test``/``describe`` string — see bite-proof records wo_a_2053_break_it_body and wo_b_2061_break_it_body_js
    if getattr(front, "PYTEST_COLLECTION", False) and any(old != new and not new.startswith("test_") for old, new in zip(old_titles, new_titles)):
        return _unresolved("binding-conflict")
    # axis: a rename that makes two defs or classes of the matched window share a name inside one namespace (the module, or one class body) runs only the last, so it is refused; the same name in two different classes is fine — see bite-proof record wo_a_2053_break_it_body
    if _collides([rec for rec in original if rec["kind"] == "stmt"], [records[i] for i in window]):
        return _unresolved("binding-conflict")
    return _result("found", None, cand_path, [(old, new) for old, new in zip(old_titles, new_titles) if old != new])
