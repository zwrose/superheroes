"""Static census: claude process argv literals only in engine_adapter (#1273, c14-l4a-D1)."""
import ast
import os
import sys
from pathlib import Path

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
_PLUGIN_ROOT = os.path.realpath(os.path.join(_LIB, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import model_registry  # noqa: E402

_ENGINE_ADAPTER_REL = "lib/engine_adapter.py"
_LAUNCHER_REL = "lib/launcher.py"
_VENDOR_STRINGS = frozenset(model_registry.VENDORS)
_SPAWNER_SUFFIXES = ("Popen", "run", "call", "check_call", "check_output")
_SPAWNER_PREFIXES = ("os.exec", "os.spawn", "os.posix_spawn")
_MUTATOR_SUFFIXES = (".append", ".extend", ".insert")


def _is_claude_literal(value):
    return isinstance(value, str) and (value == "claude" or value.endswith("/claude"))


def _dotted_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted_name(node.value)
        if base:
            return base + "." + node.attr
        return node.attr
    return None


def _is_spawner(name):
    if not name:
        return False
    if any(name.endswith(suffix) for suffix in _SPAWNER_SUFFIXES):
        return True
    return any(name.startswith(prefix) for prefix in _SPAWNER_PREFIXES)


def _is_mutator(name):
    if not name:
        return False
    return any(name.endswith(suffix) for suffix in _MUTATOR_SUFFIXES)


def _display_all_vendors(node):
    if not isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return False
    if not node.elts:
        return False
    for elt in node.elts:
        if not isinstance(elt, ast.Constant) or not isinstance(elt.value, str):
            return False
        if elt.value not in _VENDOR_STRINGS:
            return False
    return True


def _vendor_pair_tuple(node):
    return (
        isinstance(node, ast.Tuple)
        and len(node.elts) == 2
        and isinstance(node.elts[0], ast.Constant)
        and _is_claude_literal(node.elts[0].value)
        and not (
            isinstance(node.elts[1], ast.Constant)
            and isinstance(node.elts[1].value, str)
        )
    )


class _ParentVisitor(ast.NodeVisitor):
    def __init__(self):
        self.parents = {}

    def visit(self, node):
        for child in ast.iter_child_nodes(node):
            self.parents[child] = node
            self.visit(child)


def _scope_tainted_names(tree):
    tainted = set()

    class ScopeVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            self._scan(node.body, set())

        def visit_AsyncFunctionDef(self, node):
            self.visit_FunctionDef(node)

        def visit_Module(self, node):
            self._scan(node.body, set())

        def _scan(self, body, local):
            for stmt in body:
                self._stmt(stmt, local)

        def _stmt(self, node, local):
            if isinstance(node, ast.Assign):
                if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    name = node.targets[0].id
                    if name in local:
                        local.discard(name)
                self.visit(node)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.generic_visit(node)
            else:
                self.visit(node)

        def visit_AugAssign(self, node):
            if isinstance(node.target, ast.Name):
                tainted.add(node.target.id)
            self.generic_visit(node)

        def visit_Call(self, node):
            callee = _dotted_name(node.func)
            if _is_mutator(callee) and isinstance(node.func, ast.Attribute):
                recv = node.func.value
                if isinstance(recv, ast.Name):
                    tainted.add(recv.id)
            if _is_spawner(callee):
                for arg in node.args:
                    self._mark_names(arg)
            self.generic_visit(node)

        def visit_BinOp(self, node):
            if isinstance(node.op, ast.Add):
                self._mark_names(node.left)
                self._mark_names(node.right)
            self.generic_visit(node)

        def _mark_names(self, node):
            if isinstance(node, ast.Name):
                tainted.add(node.id)
            elif isinstance(node, (ast.List, ast.Tuple)):
                for elt in node.elts:
                    self._mark_names(elt)

    ScopeVisitor().visit(tree)
    return tainted


def _enclosing_function(node, parents):
    current = parents.get(node)
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current.name
        current = parents.get(current)
    return "<module>"


def _has_compare_ancestor(node, parents):
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(current, ast.Compare):
            return True
    return False


def _allowed_constant(node, parent, grandparent, tainted_names, parents):
    if parent is None:
        return False, "orphan"
    if isinstance(parent, ast.Compare) or _has_compare_ancestor(node, parents):
        return True, "compare"
    if isinstance(parent, ast.Dict):
        return True, "dict"
    if isinstance(parent, ast.DictComp) and node in (parent.key, parent.value):
        return True, "dictcomp"
    if isinstance(parent, ast.Subscript) and parent.slice is node:
        return True, "subscript"
    if isinstance(parent, ast.keyword):
        return True, "keyword"
    if isinstance(parent, ast.IfExp):
        return True, "ifexp"
    if isinstance(parent, ast.Call):
        callee = _dotted_name(parent.func)
        if _is_spawner(callee) or _is_mutator(callee):
            return False, "spawner-or-mutator-call"
        if node in parent.args:
            return True, "call-arg"
        return False, "call-non-arg"
    if isinstance(parent, (ast.List, ast.Tuple, ast.Set)):
        if _vendor_pair_tuple(parent):
            return True, "vendor-source-pair"
        if _display_all_vendors(parent):
            if isinstance(grandparent, ast.Return):
                return True, "vendor-enum-return"
            if isinstance(grandparent, ast.Dict):
                return True, "vendor-enum-dict-value"
            if isinstance(grandparent, ast.Compare):
                return True, "vendor-enum-compare"
            if isinstance(grandparent, ast.Assign) and len(grandparent.targets) == 1:
                target = grandparent.targets[0]
                if isinstance(target, ast.Name) and target.id not in tainted_names:
                    return True, "vendor-enum-assign"
            if isinstance(grandparent, ast.IfExp):
                return True, "vendor-enum-ifexp"
            if isinstance(grandparent, ast.BinOp) and isinstance(parent, ast.Set):
                return True, "vendor-enum-binop"
        return False, "display"
    if isinstance(parent, ast.Return) and _vendor_pair_tuple(parent.value):
        return True, "vendor-source-pair-return"
    return False, "disallowed"


def _violations(source_text, relpath):
    try:
        tree = ast.parse(source_text, filename=relpath)
    except SyntaxError:
        return []
    parent_visitor = _ParentVisitor()
    parent_visitor.visit(tree)
    parents = parent_visitor.parents
    tainted_names = _scope_tainted_names(tree)
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not _is_claude_literal(node.value):
            continue
        parent = parents.get(node)
        grandparent = parents.get(parent) if parent is not None else None
        allowed, context = _allowed_constant(node, parent, grandparent, tainted_names, parents)
        if not allowed:
            function = _enclosing_function(node, parents)
            out.append((relpath, node.lineno, context, function))
    return out


def _plugin_py_files():
    root = Path(_PLUGIN_ROOT)
    files = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if "/tests/" in ("/" + rel + "/"):
            continue
        if rel == _ENGINE_ADAPTER_REL:
            continue
        files.append(rel)
    return sorted(files)


def _all_violations():
    violations = []
    for rel in _plugin_py_files():
        path = os.path.join(_PLUGIN_ROOT, rel)
        with open(path, encoding="utf-8") as fh:
            violations.extend(_violations(fh.read(), rel))
    return violations


# Layer 4a-2 deletes this entry when it retires the site; claude-argv-exception-stale forces that.
_RECORDED_EXCEPTIONS = {("lib/launcher.py", "compose_launch"): 1}


def _census_problems(violations):
    groups = {}
    for relpath, lineno, _context, function in violations:
        key = (relpath, function)
        groups.setdefault(key, []).append((relpath, lineno))
    problems = []
    for key, hits in groups.items():
        recorded = _RECORDED_EXCEPTIONS.get(key)
        if recorded is None:
            for relpath, lineno in hits:
                problems.append("claude-argv-outside-adapter:%s:%d" % (relpath, lineno))
        elif len(hits) != recorded:
            if len(hits) > recorded:
                for relpath, lineno in hits:
                    problems.append("claude-argv-outside-adapter:%s:%d" % (relpath, lineno))
    for key in _RECORDED_EXCEPTIONS:
        if key not in groups:
            problems.append("claude-argv-exception-stale:%s:%s" % (key[0], key[1]))
    return sorted(problems)


def test_no_claude_argv_outside_engine_adapter():
    """axis: violation set outside engine_adapter is exactly the one recorded exception."""
    problems = _census_problems(_all_violations())
    assert problems == [], "\n".join(problems)


def test_census_problems_exact_recorded_exception():
    violations = [("lib/launcher.py", 1102, "display", "compose_launch")]
    assert _census_problems(violations) == []


def test_census_problems_exception_plus_other_file():
    violations = [
        ("lib/launcher.py", 1102, "display", "compose_launch"),
        ("lib/other.py", 5, "display", "other_fn"),
    ]
    assert _census_problems(violations) == ["claude-argv-outside-adapter:lib/other.py:5"]


def test_census_problems_exception_plus_other_function():
    violations = [
        ("lib/launcher.py", 1102, "display", "compose_launch"),
        ("lib/launcher.py", 50, "display", "other_fn"),
    ]
    assert _census_problems(violations) == ["claude-argv-outside-adapter:lib/launcher.py:50"]


def test_census_problems_two_hits_in_excepted_function():
    violations = [
        ("lib/launcher.py", 1101, "display", "compose_launch"),
        ("lib/launcher.py", 1102, "display", "compose_launch"),
    ]
    assert _census_problems(violations) == [
        "claude-argv-outside-adapter:lib/launcher.py:1101",
        "claude-argv-outside-adapter:lib/launcher.py:1102",
    ]


def test_census_problems_stale_exception():
    assert _census_problems([]) == ["claude-argv-exception-stale:lib/launcher.py:compose_launch"]


_FLAG_CASES = [
    ('argv = ["claude", "--bg"]', "list-display"),
    ('cmd = ["claude"] + list(args)', "binop-argv"),
    ('cmd = ["claude"]\ncmd += ["--bg"]', "augassign-argv"),
    ('binary = "claude"\ncmd = [binary, "--bg"]', "indirect-argv"),
    ('subprocess.run(["/usr/local/bin/claude", "-p"])', "path-spelling"),
    ('subprocess.run(["env", "FOO=1", "claude", "-p"])', "env-wrapper"),
    ('cmd = []\ncmd.append("claude")', "append-mutator"),
    ('subprocess.Popen("claude")', "popen-string"),
]

_PASS_CASES = [
    ('if vendor == "claude": pass', "compare"),
    ('x = {"claude": 1}', "dict"),
    ('def f():\n return ["claude"]', "return-list"),
    ('family_for(tier, "claude")', "call-arg"),
]


@pytest.mark.parametrize("source,label", _FLAG_CASES, ids=[c[1] for c in _FLAG_CASES])
def test_census_flags_every_argv_spelling(source, label):
    hits = _violations(source, "synthetic.py")
    assert hits, "expected violation for %s: %s" % (label, source)


@pytest.mark.parametrize("source,label", _PASS_CASES, ids=[c[1] for c in _PASS_CASES])
def test_census_allows_non_argv_contexts(source, label):
    hits = _violations(source, "synthetic.py")
    assert hits == [], hits
