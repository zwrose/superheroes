"""Static AST census tests for launch-ledger Class-1 and Class-2 chokepoints."""
import ast
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
_LAUNCHER_PY = os.path.join(_LIB, "launcher.py")
_LEDGER_PY = os.path.join(_LIB, "launch_ledger.py")

_LEDGER_READ_WRITE_FUNCS = frozenset({"append", "read"})
_LEDGER_PATH_CONSTANTS = frozenset({
    "LEDGER_NAME",
    "LEDGER_DIR_NAME",
})
_TERMINAL_EVENT_KINDS = frozenset({"outcome", "refused"})
_TERMINAL_WRITE_ALLOWLIST = frozenset({
    "_terminalize",
    "record_outcome",
    "_cli_record_outcome",
})


def _lineno(source_path, node):
    return "%s:%d" % (os.path.basename(source_path), node.lineno)


def _is_ledger_module_expr(node):
    if isinstance(node, ast.Name):
        return node.id in ("ll", "launch_ledger")
    if isinstance(node, ast.Attribute):
        return isinstance(node.value, ast.Name) and node.value.id == "launch_ledger"
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


def _open_call_targets_ledger(node, source_path):
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
    def __init__(self, source_path):
        self.source_path = source_path
        self.violations = []

    def visit_Call(self, node):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in _LEDGER_READ_WRITE_FUNCS:
            if _is_ledger_module_expr(func.value):
                first = _first_positional_arg(node)
                if _arg_looks_like_ledger_path(first):
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
        self.violations.extend(_open_call_targets_ledger(node, self.source_path))
        self.generic_visit(node)


def class1_census_violations(source_path):
    with open(source_path, encoding="utf-8") as fh:
        source = fh.read()
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
    visitor = _Class1Visitor(source_path)
    visitor.visit(ast.parse(source, filename=source_path))
    violations.extend(visitor.violations)
    return violations


def class1_census_modules():
    modules = []
    for name in ("launcher.py",):
        modules.append(os.path.join(_LIB, name))
    return modules


def run_class1_census():
    all_violations = []
    for path in class1_census_modules():
        all_violations.extend(class1_census_violations(path))
    return all_violations


class _TerminalWriterVisitor(ast.NodeVisitor):
    def __init__(self):
        self.violations = []

    def visit_Call(self, node):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "record_outcome":
            self.violations.append("record_outcome call")
        elif isinstance(func, ast.Name) and func.id in ("_record_park", "_record_refused"):
            self.violations.append(func.id)
        self.generic_visit(node)

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


def class2_census_violations(source_path):
    with open(source_path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=source_path)
    violations = {}
    launch_build_direct = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        visitor = _TerminalWriterVisitor()
        visitor.visit(node)
        if visitor.violations and node.name not in _TERMINAL_WRITE_ALLOWLIST:
            violations[node.name] = visitor.violations
        if node.name == "launch_build":
            for child in ast.walk(node):
                if (
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Name)
                    and child.func.id in ("_record_park", "_record_refused")
                ):
                    launch_build_direct.append(
                        "%s:%d: launch_build calls %s directly"
                        % (os.path.basename(source_path), child.lineno, child.func.id)
                    )
    return violations, launch_build_direct


def run_class2_census():
    return class2_census_violations(_LAUNCHER_PY)


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


if __name__ == "__main__":
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
    print("Both census tests passed.")
    sys.exit(0)
