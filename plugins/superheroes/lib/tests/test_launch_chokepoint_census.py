"""Static AST census tests for launch-ledger Class-1, Class-2, and Class-3 chokepoints."""
import ast
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import launch_ledger  # noqa: E402

_LAUNCHER_PY = os.path.join(_LIB, "launcher.py")
_LEDGER_PY = os.path.join(_LIB, "launch_ledger.py")

_LEDGER_READ_WRITE_FUNCS = frozenset({"append", "read"})
_LEDGER_PATH_CONSTANTS = frozenset({
    "LEDGER_NAME",
    "LEDGER_DIR_NAME",
})
_TERMINAL_EVENT_KINDS = frozenset(launch_ledger.TERMINAL_EVENTS)
_TERMINAL_WRITE_ALLOWLIST = {
    "launch_ledger.py": frozenset({"terminalize"}),
}
# Raw ll./launch_ledger.-qualified append is legitimate only inside functions
# that acquire the ledger lock before appending and release it in finally.
_CLASS3_APPEND_ALLOWLIST = {
    "launch_ledger.py": frozenset({
        "append",             # validated pass-through to _append_raw; callers censused
        "append_under_lock",  # holds lock around append(repo_root, ...)
        "declare_batch",      # holds lock around append(repo_root, ...)
        "reserve",            # holds lock around append(repo_root, ...)
        "terminalize",        # holds lock around repair started + terminal append
        "amend",              # holds lock around append(repo_root, ...)
    }),
}
# Allowlisted writers that must genuinely take the ledger lock. `append` is deliberately
# absent: it is the validated pass-through whose callers are censused, not a lock holder.
_CLASS3_LOCK_HOLDING = frozenset({
    "append_under_lock", "declare_batch", "reserve", "terminalize", "amend",
})
_DEFAULT_LEDGER_MODULE_IDS = frozenset({"ll", "launch_ledger"})

# Modules known to import launch_ledger today; population must include them
# or the derived census has collapsed (wrong path, bad scan, changed layout).
_CLASS1_REQUIRED_BASENAMES = ("launcher.py",)
_CLASS2_REQUIRED_BASENAMES = ("launcher.py", "launch_ledger.py")

_TAINT_FIXPOINT_CAP = 10


def _lineno(source_path, node):
    return "%s:%d" % (os.path.basename(source_path), node.lineno)


def _collect_ledger_module_aliases(tree):
    """Module-level import aliases that spell the launch_ledger module."""
    aliases = set(_DEFAULT_LEDGER_MODULE_IDS)
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "launch_ledger":
                    aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "launch_ledger":
                    aliases.add(alias.asname or alias.name)
    return frozenset(aliases)


def _is_ledger_module_expr(node, ledger_module_ids):
    if isinstance(node, ast.Name):
        return node.id in ledger_module_ids
    if isinstance(node, ast.Attribute):
        return (
            isinstance(node.value, ast.Name)
            and node.value.id in ledger_module_ids
        )
    return False


def _first_positional_arg(call_node):
    for arg in call_node.args:
        return arg
    return None


def _arg_looks_like_repo_root(arg):
    """True when the first append/read argument is plausibly a repository root."""
    if arg is None:
        return False
    if isinstance(arg, ast.Name):
        return arg.id in ("repo_root", "repo")
    if isinstance(arg, ast.Attribute):
        return arg.attr == "repo_root"
    return False


def _arg_looks_like_ledger_path(arg):
    """True when the first append/read argument is a derived ledger pathname."""
    if arg is None:
        return False
    if isinstance(arg, ast.Name) and arg.id == "path":
        return True
    if isinstance(arg, ast.Subscript):
        if isinstance(arg.slice, ast.Constant) and arg.slice.value == "path":
            return True
        if isinstance(arg.slice, ast.Index):  # py<3.9 compat
            sl = arg.slice.value
            if isinstance(sl, ast.Constant) and sl.value == "path":
                return True
    if isinstance(arg, ast.Call):
        func = arg.func
        if isinstance(func, ast.Attribute) and func.attr == "ledger_path":
            return True
        if isinstance(func, ast.Name) and func.id == "ledger_path":
            return True
    return False


def _expr_references_ledger_constant(node):
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute):
            if child.attr in _LEDGER_PATH_CONSTANTS:
                return True
        if isinstance(child, ast.Name) and child.id in _LEDGER_PATH_CONSTANTS:
            return True
        if isinstance(child, ast.Constant) and child.value == "launch-ledger.jsonl":
            return True
    return False


def _slice_is_constant_string(slice_node, value):
    if isinstance(slice_node, ast.Constant) and slice_node.value == value:
        return True
    if isinstance(slice_node, ast.Index):
        inner = slice_node.value
        if isinstance(inner, ast.Constant) and inner.value == value:
            return True
    return False


def _is_path_join_call(node):
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr != "join":
        return False
    base = func.value
    if isinstance(base, ast.Attribute) and base.attr == "path":
        mod = base.value
        if isinstance(mod, ast.Name) and mod.id in ("os", "posixpath"):
            return True
    if isinstance(base, ast.Name) and base.id == "posixpath":
        return True
    return False


def _expr_is_ledger_derived(node, tainted_names, ledger_module_ids):
    """True when an expression is ledger-derived for taint propagation."""
    if isinstance(node, ast.Name) and node.id in tainted_names:
        return True
    if _expr_references_ledger_constant(node):
        return True
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr == "ledger_path":
            if _is_ledger_module_expr(f.value, ledger_module_ids):
                return True
        if _is_path_join_call(node):
            return any(
                _expr_is_ledger_derived(arg, tainted_names, ledger_module_ids)
                for arg in node.args
            )
    if isinstance(node, ast.Subscript):
        if _slice_is_constant_string(node.slice, "path"):
            return _expr_is_ledger_derived(
                node.value, tainted_names, ledger_module_ids
            )
    return False


def _collect_stmts_in_lexical_scope(stmts):
    """Statements in one lexical scope, including control-flow nested blocks."""
    collected = []
    for stmt in stmts:
        collected.append(stmt)
        if isinstance(stmt, ast.If):
            collected.extend(_collect_stmts_in_lexical_scope(stmt.body))
            collected.extend(_collect_stmts_in_lexical_scope(stmt.orelse))
        elif isinstance(stmt, (ast.For, ast.While)):
            collected.extend(_collect_stmts_in_lexical_scope(stmt.body))
            collected.extend(_collect_stmts_in_lexical_scope(stmt.orelse))
        elif isinstance(stmt, ast.With):
            collected.extend(_collect_stmts_in_lexical_scope(stmt.body))
        elif isinstance(stmt, ast.Try):
            collected.extend(_collect_stmts_in_lexical_scope(stmt.body))
            for handler in stmt.handlers:
                collected.extend(_collect_stmts_in_lexical_scope(handler.body))
            collected.extend(_collect_stmts_in_lexical_scope(stmt.orelse))
            collected.extend(_collect_stmts_in_lexical_scope(stmt.finalbody))
        elif type(stmt).__name__ == "Match":
            for case in stmt.cases:
                collected.extend(_collect_stmts_in_lexical_scope(case.body))
    return collected


def _taint_names_in_scope(stmts, ledger_module_ids):
    """
    Fixpoint taint over plain Name assignments in one lexical scope.

    Descends into If/For/While/With/Try/Match nested blocks within the scope;
    does not descend into nested FunctionDef/AsyncFunctionDef/ClassDef bodies.
    Does not cover tuple unpacking, attribute targets, augmented assignment,
    or cross-function flow — a matcher that silently pretends to cover them
    is worse than one with a stated boundary.
    """
    scope_stmts = _collect_stmts_in_lexical_scope(stmts)
    tainted = set()
    for _ in range(_TAINT_FIXPOINT_CAP):
        added = False
        for stmt in scope_stmts:
            if isinstance(stmt, ast.Assign):
                if _expr_is_ledger_derived(stmt.value, tainted, ledger_module_ids):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name):
                            if target.id not in tainted:
                                tainted.add(target.id)
                                added = True
            elif isinstance(stmt, ast.AnnAssign):
                target = stmt.target
                if (
                    isinstance(target, ast.Name)
                    and stmt.value is not None
                    and _expr_is_ledger_derived(
                        stmt.value, tainted, ledger_module_ids
                    )
                ):
                    if target.id not in tainted:
                        tainted.add(target.id)
                        added = True
        if not added:
            break
    return tainted


def _collect_scope_taints(tree, ledger_module_ids):
    scopes = {"module": _taint_names_in_scope(tree.body, ledger_module_ids)}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            scopes[node] = _taint_names_in_scope(node.body, ledger_module_ids)
    return scopes


def _parse_source(source, source_path):
    try:
        return ast.parse(source, filename=source_path)
    except SyntaxError as exc:
        raise RuntimeError(
            "Census cannot parse %s: %s" % (source_path, exc)
        ) from exc


def _open_call_targets_ledger(node, source_path, tainted_names):
    """Detect open()/os.open() calls whose path derives from ledger identity."""
    violations = []
    if not isinstance(node, ast.Call):
        return violations
    func = node.func
    is_open = (
        (isinstance(func, ast.Name) and func.id == "open")
        or (isinstance(func, ast.Attribute) and func.attr == "open")
    )
    if not is_open:
        return violations
    if not node.args:
        return violations
    path_arg = node.args[0]
    if isinstance(path_arg, ast.Name) and path_arg.id in tainted_names:
        violations.append(
            "%s: open()/os.open() on aliased ledger path (clause: no direct ledger open)"
            % _lineno(source_path, node)
        )
        return violations
    if _expr_references_ledger_constant(path_arg):
        violations.append(
            "%s: open()/os.open() on ledger-derived path (clause: no direct ledger open)"
            % _lineno(source_path, node)
        )
        return violations
    if isinstance(path_arg, ast.Call):
        f = path_arg.func
        if isinstance(f, ast.Attribute) and f.attr == "ledger_path":
            violations.append(
                "%s: open()/os.open() on ledger_path() result (clause: no direct ledger open)"
                % _lineno(source_path, node)
            )
        elif isinstance(f, ast.Name) and f.id == "ledger_path":
            violations.append(
                "%s: open()/os.open() on ledger_path() result (clause: no direct ledger open)"
                % _lineno(source_path, node)
            )
    return violations


class _Class1Visitor(ast.NodeVisitor):
    def __init__(self, source_path, scope_taints, ledger_module_ids):
        self.source_path = source_path
        self.scope_taints = scope_taints
        self.ledger_module_ids = ledger_module_ids
        self.current_taint = scope_taints["module"]
        self.violations = []

    def visit_FunctionDef(self, node):
        old = self.current_taint
        self.current_taint = self.scope_taints.get(node, set())
        self.generic_visit(node)
        self.current_taint = old

    def visit_AsyncFunctionDef(self, node):
        old = self.current_taint
        self.current_taint = self.scope_taints.get(node, set())
        self.generic_visit(node)
        self.current_taint = old

    def visit_Call(self, node):
        func = node.func
        tainted = self.current_taint
        if isinstance(func, ast.Attribute) and func.attr in _LEDGER_READ_WRITE_FUNCS:
            if _is_ledger_module_expr(func.value, self.ledger_module_ids):
                first = _first_positional_arg(node)
                if isinstance(first, ast.Name) and first.id in tainted:
                    self.violations.append(
                        "%s: %s() first argument is an aliased ledger pathname "
                        "(clause: append/read must receive repository root)"
                        % (_lineno(self.source_path, node), func.attr)
                    )
                elif _arg_looks_like_ledger_path(first):
                    self.violations.append(
                        "%s: %s() first argument is a ledger pathname, not repo_root "
                        "(clause: append/read must receive repository root)"
                        % (_lineno(self.source_path, node), func.attr)
                    )
                elif not _arg_looks_like_repo_root(first):
                    self.violations.append(
                        "%s: %s() first argument is not repository root "
                        "(clause: append/read must receive repository root)"
                        % (_lineno(self.source_path, node), func.attr)
                    )
        self.violations.extend(_open_call_targets_ledger(node, self.source_path, tainted))
        self.generic_visit(node)


def class1_census_violations_from_source(source, source_path):
    tree = _parse_source(source, source_path)
    ledger_module_ids = _collect_ledger_module_aliases(tree)
    violations = []
    if os.path.basename(source_path) != "launch_ledger.py":
        for name in _LEDGER_PATH_CONSTANTS:
            if name in source:
                violations.append(
                    "%s: references ledger constant %s "
                    "(clause: only launch_ledger.py may name ledger paths)"
                    % (os.path.basename(source_path), name)
                )
        if "launch-ledger.jsonl" in source:
            violations.append(
                "%s: references ledger filename literal "
                "(clause: only launch_ledger.py may name ledger paths)"
                % os.path.basename(source_path)
            )
    scope_taints = _collect_scope_taints(tree, ledger_module_ids)
    visitor = _Class1Visitor(source_path, scope_taints, ledger_module_ids)
    visitor.visit(tree)
    violations.extend(visitor.violations)
    return violations


def class1_census_violations(source_path):
    with open(source_path, encoding="utf-8") as fh:
        source = fh.read()
    return class1_census_violations_from_source(source, source_path)


def _lib_python_modules(exclude_basenames=frozenset()):
    """Every .py under lib/, excluding tests/."""
    modules = []
    for root, dirs, files in os.walk(_LIB):
        dirs[:] = [d for d in dirs if d != "tests"]
        for name in files:
            if not name.endswith(".py"):
                continue
            if name in exclude_basenames:
                continue
            modules.append(os.path.join(root, name))
    modules.sort()
    return modules


def class1_census_modules():
    return _lib_python_modules(exclude_basenames=frozenset({"launch_ledger.py"}))


def class2_census_modules():
    return _lib_python_modules(exclude_basenames=frozenset())


def _path_under_tests(path):
    tests_dir = os.path.join(_LIB, "tests")
    try:
        return os.path.commonpath([os.path.realpath(path), tests_dir]) == tests_dir
    except ValueError:
        return False


def _validate_class1_population(modules):
    if not modules:
        raise RuntimeError(
            "Class-1 census population collapsed: derived zero modules from %s "
            "(expected every .py under lib/ except launch_ledger.py and tests/)"
            % _LIB
        )
    basenames = {os.path.basename(p) for p in modules}
    missing = [n for n in _CLASS1_REQUIRED_BASENAMES if n not in basenames]
    if missing:
        raise RuntimeError(
            "Class-1 census population collapsed: derived population missing "
            "known launch_ledger consumer(s): %s" % ", ".join(missing)
        )
    for path in modules:
        if _path_under_tests(path):
            raise RuntimeError(
                "Class-1 census population includes test module: %s" % path
            )


def _validate_class2_population(modules):
    if not modules:
        raise RuntimeError(
            "Class-2 census population collapsed: derived zero modules from %s "
            "(expected every .py under lib/ except tests/)"
            % _LIB
        )
    basenames = {os.path.basename(p) for p in modules}
    missing = [n for n in _CLASS2_REQUIRED_BASENAMES if n not in basenames]
    if missing:
        raise RuntimeError(
            "Class-2 census population collapsed: derived population missing "
            "required module(s): %s" % ", ".join(missing)
        )
    for path in modules:
        if _path_under_tests(path):
            raise RuntimeError(
                "Class-2 census population includes test module: %s" % path
            )


def run_class1_census():
    modules = class1_census_modules()
    _validate_class1_population(modules)
    all_violations = []
    for path in modules:
        all_violations.extend(class1_census_violations(path))
    return all_violations


class _TerminalWriterVisitor(ast.NodeVisitor):
    # Boundaries: dict(**kwargs) with a dynamic event value, and non-constant
    # event expressions, are not matched — only explicit event= keywords and
    # constant terminal kinds are covered.

    def __init__(self):
        self.violations = []

    def visit_FunctionDef(self, node):
        pass

    def visit_AsyncFunctionDef(self, node):
        pass

    def visit_Call(self, node):
        func = node.func
        if isinstance(func, ast.Name) and func.id in ("_record_park", "_record_refused"):
            self.violations.append(func.id)
        elif isinstance(func, ast.Name) and func.id == "dict":
            for kw in node.keywords:
                if (
                    kw.arg == "event"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value in _TERMINAL_EVENT_KINDS
                ):
                    self.violations.append("dict-call:%s" % kw.value.value)
        elif isinstance(func, ast.Attribute) and func.attr == "update":
            for arg in node.args:
                if isinstance(arg, ast.Dict):
                    for key, value in zip(arg.keys, arg.values):
                        if (
                            isinstance(key, ast.Constant)
                            and key.value == "event"
                            and isinstance(value, ast.Constant)
                            and value.value in _TERMINAL_EVENT_KINDS
                        ):
                            self.violations.append("update:%s" % value.value)
            for kw in node.keywords:
                if (
                    kw.arg == "event"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value in _TERMINAL_EVENT_KINDS
                ):
                    self.violations.append("update:%s" % kw.value.value)
        self.generic_visit(node)

    def visit_Assign(self, node):
        for target in node.targets:
            self._check_event_subscript_assign(target, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        if node.target is not None and node.value is not None:
            self._check_event_subscript_assign(node.target, node.value)
        self.generic_visit(node)

    def _check_event_subscript_assign(self, target, value):
        if not isinstance(target, ast.Subscript):
            return
        if not _slice_is_constant_string(target.slice, "event"):
            return
        if isinstance(value, ast.Constant) and value.value in _TERMINAL_EVENT_KINDS:
            self.violations.append("subscript-assign:%s" % value.value)

    def visit_Dict(self, node):
        for key, value in zip(node.keys, node.values):
            if (
                isinstance(key, ast.Constant)
                and key.value == "event"
                and isinstance(value, ast.Constant)
                and value.value in _TERMINAL_EVENT_KINDS
            ):
                self.violations.append("event:%s" % value.value)
        self.generic_visit(node)


def class2_census_violations_from_source(source, source_path):
    tree = _parse_source(source, source_path)
    basename = os.path.basename(source_path)
    allowlist = _TERMINAL_WRITE_ALLOWLIST.get(basename, frozenset())
    violations = {}
    launch_build_direct = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        key = "%s::%s" % (basename, node.name)
        visitor = _TerminalWriterVisitor()
        for stmt in node.body:
            visitor.visit(stmt)
        if visitor.violations:
            if _is_module_level_function(tree, node) and node.name in allowlist:
                continue
            violations[key] = visitor.violations

    if basename == "launcher.py":
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "launch_build":
                for child in ast.walk(node):
                    if (
                        isinstance(child, ast.Call)
                        and isinstance(child.func, ast.Name)
                        and child.func.id in ("_record_park", "_record_refused")
                    ):
                        launch_build_direct.append(
                            "%s:%d: launch_build calls %s directly"
                            % (basename, child.lineno, child.func.id)
                        )
    return violations, launch_build_direct


def class2_census_violations(source_path):
    with open(source_path, encoding="utf-8") as fh:
        source = fh.read()
    return class2_census_violations_from_source(source, source_path)


def run_class2_census():
    modules = class2_census_modules()
    _validate_class2_population(modules)
    all_violations = {}
    all_launch_build = []
    for path in modules:
        violations, launch_build_direct = class2_census_violations(path)
        all_violations.update(violations)
        all_launch_build.extend(launch_build_direct)
    return all_violations, all_launch_build


class _Class3AppendVisitor(ast.NodeVisitor):
    """
    Static call-site census for ll.append / launch_ledger.append.

    Recognises module spellings from _collect_ledger_module_aliases (defaults
    ll and launch_ledger, plus import launch_ledger as <name> aliases).
    Inside launch_ledger.py itself, bare ``append(...)`` calls are also matched
    (the module does not import itself, so every internal append is a Name call).
    Does not catch append reached through a local variable — only qualified
    module.append spellings and the launch_ledger.py bare-name exception above.
    Boundary: ``from launch_ledger import append`` followed by bare ``append(...)``
    in other modules is not matched — only attribute access on a recognised
    module spelling is covered there.
    append_under_lock is intentionally invisible here: the attribute name is not
    append, and that helper holds the ledger lock by construction — the invariant
    is raw lock-free append, not every append-shaped entry point.
    This is not a proof of mutual exclusion; it stops new bypassing writers.
    """

    def __init__(self, source_path, ledger_module_ids):
        self.source_path = source_path
        self.ledger_module_ids = ledger_module_ids
        self.violations = []

    def visit_Call(self, node):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in ("append", "_append_raw"):
            if _is_ledger_module_expr(func.value, self.ledger_module_ids):
                self.violations.append(
                    "%s: append() on ledger module (clause: raw append only under lock)"
                    % _lineno(self.source_path, node)
                )
        elif (
            isinstance(func, ast.Name)
            and func.id in ("append", "_append_raw")
            and os.path.basename(self.source_path) == "launch_ledger.py"
        ):
            self.violations.append(
                "%s: append() on ledger module (clause: raw append only under lock)"
                % _lineno(self.source_path, node)
            )
        self.generic_visit(node)


def _module_level_function_names(tree):
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _is_module_level_function(tree, node):
    return node in tree.body


def _validate_class3_append_allowlist(tree, basename):
    allowlist = _CLASS3_APPEND_ALLOWLIST.get(basename, frozenset())
    if not allowlist:
        return
    defined = _module_level_function_names(tree)
    stale = sorted(name for name in allowlist if name not in defined)
    if stale:
        raise RuntimeError(
            "Class-3 append allowlist names missing from %s: %s"
            % (basename, ", ".join(stale))
        )


def class3_census_violations_from_source(source, source_path):
    tree = _parse_source(source, source_path)
    basename = os.path.basename(source_path)
    ledger_module_ids = _collect_ledger_module_aliases(tree)
    allowlist = _CLASS3_APPEND_ALLOWLIST.get(basename, frozenset())
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _is_module_level_function(tree, node) and node.name in allowlist:
            continue
        visitor = _Class3AppendVisitor(source_path, ledger_module_ids)
        for stmt in node.body:
            visitor.visit(stmt)
        if visitor.violations:
            key = "%s::%s" % (basename, node.name)
            violations.append("%s: %s" % (key, visitor.violations))
    return violations


def class3_census_violations(source_path):
    with open(source_path, encoding="utf-8") as fh:
        source = fh.read()
    basename = os.path.basename(source_path)
    if basename == "launch_ledger.py":
        tree = _parse_source(source, source_path)
        _validate_class3_append_allowlist(tree, basename)
    return class3_census_violations_from_source(source, source_path)


def run_class3_census():
    modules = class2_census_modules()
    _validate_class2_population(modules)
    all_violations = []
    for path in modules:
        all_violations.extend(class3_census_violations(path))
    return all_violations


def test_class1_census_launcher_routes_through_chokepoint():
    violations = run_class1_census()
    assert violations == [], (
        "INVARIANT 1: every ledger read/write goes through open_ledger via repo_root; "
        "violations:\n  " + "\n  ".join(violations)
    )


def test_class2_census_only_terminalize_writes_terminals():
    violations, launch_build_calls = run_class2_census()
    assert launch_build_calls == [], (
        "INVARIANT 2: exactly one function writes terminal ledger events; "
        "launch_build must not call _record_park or _record_refused directly; "
        "found: %s" % launch_build_calls
    )
    assert violations == {}, (
        "INVARIANT 2: exactly one function writes terminal ledger events; "
        "violating functions: %s" % violations
    )


def test_class3_census_raw_append_only_under_lock():
    violations = run_class3_census()
    assert violations == [], (
        "INVARIANT 3: raw ledger append only under lock; violations:\n  "
        + "\n  ".join(violations)
    )


def test_class2_record_outcome_delegates_to_the_door():
    with open(_LEDGER_PY, encoding="utf-8") as fh:
        source = fh.read()
    tree = _parse_source(source, _LEDGER_PY)
    record_outcome = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "record_outcome":
            record_outcome = node
            break
    assert record_outcome is not None

    has_terminalize = False
    has_append = False
    for child in ast.walk(record_outcome):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name) and func.id == "terminalize":
                has_terminalize = True
            if isinstance(func, ast.Name) and func.id == "append":
                has_append = True
            if isinstance(func, ast.Attribute) and func.attr == "append":
                has_append = True

    terminal_visitor = _TerminalWriterVisitor()
    for stmt in record_outcome.body:
        terminal_visitor.visit(stmt)

    assert has_terminalize, "record_outcome must delegate to terminalize"
    assert not has_append, "record_outcome must not call append"
    assert terminal_visitor.violations == [], (
        "record_outcome must not construct terminal event records: %s"
        % terminal_visitor.violations
    )


def test_class2_launcher_terminalize_is_a_pure_delegation():
    with open(_LAUNCHER_PY, encoding="utf-8") as fh:
        source = fh.read()
    tree = _parse_source(source, _LAUNCHER_PY)
    terminalize_fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_terminalize":
            terminalize_fn = node
            break
    assert terminalize_fn is not None, "_terminalize not found in launcher.py"

    has_terminalize = False
    has_forbidden_call = False
    ledger_ids = _DEFAULT_LEDGER_MODULE_IDS
    for child in ast.walk(terminalize_fn):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Attribute) and func.attr == "terminalize":
                if _is_ledger_module_expr(func.value, ledger_ids):
                    has_terminalize = True
            if isinstance(func, ast.Name) and func.id in ("append", "_append_under_lock"):
                has_forbidden_call = True
            if isinstance(func, ast.Attribute) and func.attr == "append":
                if _is_ledger_module_expr(func.value, ledger_ids):
                    has_forbidden_call = True
            if isinstance(func, ast.Attribute) and func.attr == "_append_under_lock":
                has_forbidden_call = True

    terminal_visitor = _TerminalWriterVisitor()
    for stmt in terminalize_fn.body:
        terminal_visitor.visit(stmt)

    assert has_terminalize, "_terminalize must delegate to ll.terminalize"
    assert not has_forbidden_call, (
        "_terminalize must not call append or _append_under_lock"
    )
    assert terminal_visitor.violations == [], (
        "_terminalize must not construct terminal event records: %s"
        % terminal_visitor.violations
    )

    violations, _ = class2_census_violations(_LAUNCHER_PY)
    assert "launcher.py::_terminalize" not in violations, (
        "_terminalize should not trip Class-2 census on its own merits: %s"
        % violations.get("launcher.py::_terminalize")
    )


def test_class1_matcher_catches_aliased_ledger_path():
    bad_source = (
        "import launch_ledger as ll\n"
        "def bypass(repo_root):\n"
        "    p = ll.ledger_path(repo_root)['path']\n"
        "    open(p, 'ab')\n"
    )
    bad_path = os.path.join(_LIB, "fake_bypass.py")
    bad_violations = class1_census_violations_from_source(bad_source, bad_path)
    assert any("aliased ledger path" in v for v in bad_violations), bad_violations

    good_source = (
        "import launch_ledger as ll\n"
        "def ok(repo_root):\n"
        "    p = ll.ledger_path(repo_root)['path']\n"
        "    open(some_unrelated_path, 'ab')\n"
    )
    good_violations = class1_census_violations_from_source(good_source, bad_path)
    assert not any("aliased ledger path" in v for v in good_violations), good_violations


def test_class1_matcher_catches_aliased_path_inside_control_flow():
    """Aliases assigned inside control-flow blocks must taint for open() census."""
    bad_path = os.path.join(_LIB, "fake_bypass.py")
    cases = [
        (
            "import launch_ledger as ll\n"
            "def bypass(repo_root):\n"
            "    if repo_root:\n"
            "        p = ll.ledger_path(repo_root)['path']\n"
            "    open(p, 'ab')\n",
            "if",
        ),
        (
            "import launch_ledger as ll\n"
            "def bypass(repo_root):\n"
            "    try:\n"
            "        p = ll.ledger_path(repo_root)['path']\n"
            "    except OSError:\n"
            "        pass\n"
            "    open(p, 'ab')\n",
            "try",
        ),
        (
            "import launch_ledger as ll\n"
            "def bypass(repo_root):\n"
            "    with open('/dev/null'):\n"
            "        p = ll.ledger_path(repo_root)['path']\n"
            "    open(p, 'ab')\n",
            "with",
        ),
        (
            "import launch_ledger as ll\n"
            "def bypass(repo_root):\n"
            "    for _ in repo_root:\n"
            "        p = ll.ledger_path(repo_root)['path']\n"
            "    open(p, 'ab')\n",
            "for",
        ),
    ]
    for source, label in cases:
        violations = class1_census_violations_from_source(source, bad_path)
        assert any("aliased ledger path" in v for v in violations), (label, violations)


def test_class1_matcher_nested_function_scope_boundary():
    """Alias inside a nested function must not taint the outer scope."""
    source = (
        "import launch_ledger as ll\n"
        "def outer(repo_root):\n"
        "    def inner():\n"
        "        p = ll.ledger_path(repo_root)['path']\n"
        "        return p\n"
        "    open(inner(), 'ab')\n"
    )
    path = os.path.join(_LIB, "fake_bypass.py")
    violations = class1_census_violations_from_source(source, path)
    assert not any("aliased ledger path" in v for v in violations), violations


def test_class2_matcher_catches_non_literal_terminal_records():
    constructions = [
        ("dict(event='outcome')", "dict-call:outcome"),
        ("rec['event'] = 'refused'", "subscript-assign:refused"),
        ("rec.update(event='outcome')", "update:outcome"),
    ]
    for body_line, expected_kind in constructions:
        source = "def rogue_writer():\n    rec = {}\n    %s\n" % body_line
        path = os.path.join(_LIB, "fake_rogue.py")
        violations, _ = class2_census_violations_from_source(source, path)
        key = "fake_rogue.py::rogue_writer"
        assert key in violations, (body_line, violations)
        assert expected_kind in violations[key], (body_line, violations)

    allowlisted_source = (
        "def terminalize(repo_root, launch_id):\n"
        "    rec = {}\n"
        "    rec['event'] = 'outcome'\n"
        "    rec.update(event='outcome')\n"
        "    d = dict(event='outcome')\n"
    )
    allowlisted_path = os.path.join(_LIB, "launch_ledger.py")
    allowlisted_violations, _ = class2_census_violations_from_source(
        allowlisted_source, allowlisted_path
    )
    assert allowlisted_violations == {}, allowlisted_violations


def test_class2_matcher_catches_launcher_terminalize_regression():
    """A rogue launcher._terminalize must trip Class-2 now that it is not allowlisted."""
    source = (
        "def _terminalize(repo_root, launch_id):\n"
        "    rec = {'event': 'outcome', 'launchId': launch_id}\n"
    )
    path = os.path.join(_LIB, "launcher.py")
    violations, _ = class2_census_violations_from_source(source, path)
    key = "launcher.py::_terminalize"
    assert key in violations, violations
    assert "event:outcome" in violations[key], violations


def test_class3_matcher_catches_rogue_append_with_empty_allowlist():
    """Class-3 clause must still bite when the allowlist is empty for a module."""
    source = (
        "import launch_ledger as ll\n"
        "def rogue_writer(repo_root, record):\n"
        "    ll.append(repo_root, record)\n"
    )
    path = os.path.join(_LIB, "fake_bypass.py")
    violations = class3_census_violations_from_source(source, path)
    assert violations, violations
    assert any("rogue_writer" in v for v in violations), violations


def test_class3_matcher_catches_raw_append_inside_the_ledger_module():
    """launch_ledger.py is censused per-function; only lock-holders are allowlisted."""
    ledger_path = os.path.join(_LIB, "launch_ledger.py")
    bad_source = (
        "def rogue_inside_ledger(repo_root, record):\n"
        "    append(repo_root, record)\n"
    )
    bad_violations = class3_census_violations_from_source(bad_source, ledger_path)
    assert bad_violations, bad_violations
    assert any("rogue_inside_ledger" in v for v in bad_violations), bad_violations

    good_source = (
        "def reserve(repo_root, record):\n"
        "    append(repo_root, record)\n"
    )
    good_violations = class3_census_violations_from_source(good_source, ledger_path)
    assert good_violations == [], good_violations


def test_class3_matcher_catches_append_raw_inside_the_ledger_module():
    """_append_raw is the primitive Class-3 exists to gate; renames must not blind it."""
    ledger_path = os.path.join(_LIB, "launch_ledger.py")
    bad_source = (
        "def rogue_inside_ledger(repo_root, record):\n"
        "    _append_raw(repo_root, record)\n"
    )
    bad_violations = class3_census_violations_from_source(bad_source, ledger_path)
    assert bad_violations, bad_violations
    assert any("rogue_inside_ledger" in v for v in bad_violations), bad_violations

    good_source = (
        "def terminalize(repo_root, launch_id):\n"
        "    _append_raw(repo_root, record)\n"
    )
    good_violations = class3_census_violations_from_source(good_source, ledger_path)
    assert good_violations == [], good_violations


def _ledger_append_writer_functions(tree):
    """Module-level functions that call bare append() or _append_raw() in launch_ledger.py."""
    writers = set()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            func = child.func
            if isinstance(func, ast.Name) and func.id in ("append", "_append_raw"):
                writers.add(node.name)
    return writers


def test_class3_every_ledger_append_writer_is_matched_or_allowlisted():
    """Rename-proof: every module-level ledger writer is censused or explicitly exempt."""
    with open(_LEDGER_PY, encoding="utf-8") as fh:
        source = fh.read()
    tree = _parse_source(source, _LEDGER_PY)
    writers = _ledger_append_writer_functions(tree)
    allowlist = _CLASS3_APPEND_ALLOWLIST.get("launch_ledger.py", frozenset())
    # _append_raw is the primitive itself — it writes via open_ledger, not via append.
    writers.discard("_append_raw")
    uncovered = sorted(writers - allowlist)
    assert uncovered == [], (
        "module-level functions calling append/_append_raw must be allowlisted "
        "or caught by Class-3: %s" % ", ".join(uncovered)
    )


def test_class3_matcher_catches_an_aliased_ledger_module():
    """import launch_ledger as <name> must not bypass Class-3."""
    source = (
        "import launch_ledger as ledger\n"
        "def rogue_writer(repo_root, record):\n"
        "    ledger.append(repo_root, record)\n"
    )
    path = os.path.join(_LIB, "fake_bypass.py")
    violations = class3_census_violations_from_source(source, path)
    assert violations, violations
    assert any("rogue_writer" in v for v in violations), violations


def test_class1_matcher_catches_aliased_ledger_read():
    """Class-1 must recognise import launch_ledger as <name> for read/append calls."""
    bad_source = (
        "import launch_ledger as ledger\n"
        "def bypass(path):\n"
        "    ledger.read(path)\n"
    )
    bad_path = os.path.join(_LIB, "fake_bypass.py")
    bad_violations = class1_census_violations_from_source(bad_source, bad_path)
    assert any("read()" in v and "repo_root" in v for v in bad_violations), (
        bad_violations
    )


def test_class3_append_allowlist_names_exist_in_launch_ledger():
    """Stale allowlist entries must fail loudly, not silently exempt nothing."""
    with open(_LEDGER_PY, encoding="utf-8") as fh:
        source = fh.read()
    tree = _parse_source(source, _LEDGER_PY)
    _validate_class3_append_allowlist(tree, "launch_ledger.py")


def _module_level_function(tree, name):
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _function_calls_acquire_lock(func_node):
    for node in ast.walk(func_node):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "_acquire_lock":
                return True
    return False


def _function_releases_lock_in_finally(func_node):
    for node in ast.walk(func_node):
        if isinstance(node, ast.Try):
            for stmt in node.finalbody:
                for child in ast.walk(stmt):
                    if isinstance(child, ast.Call):
                        func = child.func
                        if isinstance(func, ast.Name) and func.id == "_release_lock":
                            return True
    return False


def test_class3_allowlisted_lock_holders_take_and_release_the_lock():
    # axis: an allowlisted ledger writer really acquires and releases the ledger lock —
    # allowlisting is not a bypass.
    with open(_LEDGER_PY, encoding="utf-8") as fh:
        source = fh.read()
    tree = _parse_source(source, _LEDGER_PY)
    missing = []
    for name in sorted(_CLASS3_LOCK_HOLDING):
        func_node = _module_level_function(tree, name)
        if func_node is None:
            missing.append("%s: not defined at module level" % name)
            continue
        if not _function_calls_acquire_lock(func_node):
            missing.append("%s: no _acquire_lock call" % name)
        if not _function_releases_lock_in_finally(func_node):
            missing.append("%s: no _release_lock in try/finally" % name)
    assert missing == [], (
        "allowlisted lock-holders must acquire and release the ledger lock: %s"
        % "; ".join(missing)
    )


def test_class3_from_import_append_boundary():
    """from launch_ledger import append — bare append() is a stated Class-3 boundary."""
    source = (
        "from launch_ledger import append\n"
        "def rogue_writer(repo_root, record):\n"
        "    append(repo_root, record)\n"
    )
    path = os.path.join(_LIB, "fake_bypass.py")
    violations = class3_census_violations_from_source(source, path)
    assert violations == [], violations


def test_class1_matcher_two_ledger_import_aliases():
    """Both import aliases for launch_ledger must be recognised for Class-1."""
    source = (
        "import launch_ledger as ll\n"
        "import launch_ledger as ledger\n"
        "def bypass(repo_root):\n"
        "    p = ll.ledger_path(repo_root)['path']\n"
        "    ledger.read(p)\n"
    )
    path = os.path.join(_LIB, "fake_bypass.py")
    violations = class1_census_violations_from_source(source, path)
    assert any("aliased ledger pathname" in v for v in violations), violations


def test_class2_and_class3_catch_a_nested_rogue_terminalize():
    """A method named terminalize must not inherit the module-level allowlist."""
    source = (
        "from launch_ledger import append\n"
        "\n"
        "def terminalize(repo_root, launch_id):\n"
        "    pass\n"
        "\n"
        "class Rogue:\n"
        "    def terminalize(self, repo_root, launch_id):\n"
        "        record = {'event': 'outcome', 'launchId': launch_id}\n"
        "        append(repo_root, record)\n"
    )
    path = os.path.join(_LIB, "launch_ledger.py")
    c2_violations, _ = class2_census_violations_from_source(source, path)
    c3_violations = class3_census_violations_from_source(source, path)
    c2_key = "launch_ledger.py::terminalize"
    c3_key = "launch_ledger.py::terminalize"
    assert c2_key in c2_violations, c2_violations
    assert "event:outcome" in c2_violations[c2_key], c2_violations
    assert any(c3_key in v for v in c3_violations), c3_violations


if __name__ == "__main__":
    c1_modules = class1_census_modules()
    c2_modules = class2_census_modules()
    print(
        "Census populations: Class-1=%d modules, Class-2=%d modules"
        % (len(c1_modules), len(c2_modules))
    )
    c1 = run_class1_census()
    if c1:
        print("Class-1 census FAILED:")
        for v in c1:
            print("  %s" % v)
        sys.exit(1)
    c2_v, c2_lb = run_class2_census()
    if c2_lb or c2_v:
        print("Class-2 census FAILED:")
        for v in c2_lb:
            print("  %s" % v)
        for fn, kinds in sorted(c2_v.items()):
            print("  %s: %s" % (fn, kinds))
        sys.exit(1)
    c3 = run_class3_census()
    if c3:
        print("Class-3 census FAILED:")
        for v in c3:
            print("  %s" % v)
        sys.exit(1)
    print("All census tests passed.")
    sys.exit(0)
