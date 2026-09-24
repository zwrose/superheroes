"""Static census: claude process argv literals only in engine_adapter (#1273, c14-l4a-D1)."""
import ast
import os
import shlex
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
_VENDOR_STRINGS = frozenset(model_registry.VENDORS)
_SPAWNER_SUFFIXES = ("Popen", "run", "call", "check_call", "check_output", "system", "popen")
_SPAWNER_PREFIXES = ("os.exec", "os.spawn", "os.posix_spawn")
_MUTATOR_SUFFIXES = (".append", ".extend", ".insert")
_SPAWN_KEYWORDS = frozenset(("executable", "args", "argv", "cmd", "command"))


def _is_claude_literal(value):
    return isinstance(value, str) and (value == "claude" or value.endswith("/claude"))


_FSTRING_PLACEHOLDER = "\x00"


def _tokenize_command_string(value):
    try:
        return shlex.split(value)
    except ValueError:
        return value.split()


def _is_assignment_token(token, placeholder=None):
    if placeholder and placeholder in token:
        return "=" in token.split(placeholder)[0]
    return "=" in token and not token.startswith("=")


def _is_env_wrapper_token(token):
    return token == "env" or token.endswith("/env")


def _command_word_from_tokens(tokens, placeholder=None):
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if _is_assignment_token(token, placeholder):
            i += 1
            continue
        if _is_env_wrapper_token(token):
            i += 1
            while i < len(tokens):
                inner = tokens[i]
                if _is_assignment_token(inner, placeholder) or inner.startswith("-"):
                    i += 1
                else:
                    break
            continue
        return token
    return None


def _command_word_is_claude(value, placeholder=None):
    if not isinstance(value, str) or not value.strip():
        return False
    word = _command_word_from_tokens(_tokenize_command_string(value), placeholder)
    if word is None:
        return False
    return word == "claude" or word.endswith("/claude")


def _render_joinedstr_for_command(node):
    parts = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            parts.append(value.value)
        elif isinstance(value, ast.FormattedValue):
            parts.append(_FSTRING_PLACEHOLDER)
    return "".join(parts)


def _joined_str_first_token_is_claude(node):
    if not isinstance(node, ast.JoinedStr) or not node.values:
        return False
    first = node.values[0]
    if isinstance(first, ast.FormattedValue):
        return False
    rendered = _render_joinedstr_for_command(node)
    return _command_word_is_claude(rendered, placeholder=_FSTRING_PLACEHOLDER)


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


def _vendor_source_pair_tuple(node):
    """Shape at round_driver.py:5985/:5992 — return \"claude\", <non-str-constant>."""
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


def _collect_name_sources(node):
    names = set()
    if isinstance(node, ast.Name):
        names.add(node.id)
    elif isinstance(node, (ast.List, ast.Tuple)):
        for elt in node.elts:
            names |= _collect_name_sources(elt)
    elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        names |= _collect_name_sources(node.left)
        names |= _collect_name_sources(node.right)
    return names


def _scope_tainted_names(body):
    tainted = set()
    assign_sources = {}

    def note_spawner_arg(node):
        tainted.update(_collect_name_sources(node))

    def scan_stmt(stmt):
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return
        if isinstance(stmt, ast.Assign):
            if len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                assign_sources[stmt.targets[0].id] = _collect_name_sources(stmt.value)
        elif isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name):
            target = stmt.target.id
            sources = _collect_name_sources(stmt.value)
            sources.add(target)
            assign_sources[target] = assign_sources.get(target, set()) | sources
        for node in ast.walk(stmt):
            if not isinstance(node, ast.Call):
                continue
            callee = _dotted_name(node.func)
            if _is_spawner(callee):
                for arg in node.args:
                    note_spawner_arg(arg)
                for kw in node.keywords:
                    note_spawner_arg(kw.value)

    for stmt in body:
        scan_stmt(stmt)

    changed = True
    while changed:
        changed = False
        for name, sources in assign_sources.items():
            if sources & tainted and name not in tainted:
                tainted.add(name)
                changed = True
    return tainted


def _scope_taint_map(tree):
    scopes = {}

    class ScopeVisitor(ast.NodeVisitor):
        def visit_Module(self, node):
            scopes[id(node)] = _scope_tainted_names(node.body)
            self.generic_visit(node)

        def visit_FunctionDef(self, node):
            scopes[id(node)] = _scope_tainted_names(node.body)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node):
            self.visit_FunctionDef(node)

    ScopeVisitor().visit(tree)
    return scopes


def _enclosing_scope(node, parents):
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
            return current
    return None


def _tainted_in_scope(node, parents, scope_taints):
    scope = _enclosing_scope(node, parents)
    if scope is None:
        return set()
    return scope_taints.get(id(scope), set())


def _enclosing_function(node, parents):
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current.name
        current = parents.get(current)
    return "<module>"


def _enclosing_call(node, parents):
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(current, ast.Call):
            return current
        current = parents.get(current)
    return None


def _is_name_binding(node, parent, parents):
    if not isinstance(parent, ast.Assign) or len(parent.targets) != 1:
        return False
    if not isinstance(parent.targets[0], ast.Name):
        return False
    scope = _enclosing_scope(node, parents)
    if scope is None:
        return False
    if parent not in getattr(scope, "body", ()):
        return False
    return True


def _allowed_constant(node, parent, grandparent, scope_taints, parents):
    if parent is None:
        return False, "orphan"
    if _is_name_binding(node, parent, parents):
        return False, "name-binding"
    if isinstance(parent, ast.IfExp):
        if node in (parent.test,):
            return True, "compare"
        ifexp_parent = parents.get(parent)
        ifexp_grandparent = parents.get(ifexp_parent) if ifexp_parent is not None else None
        return _allowed_constant(node, ifexp_parent, ifexp_grandparent, scope_taints, parents)
    if isinstance(parent, ast.Compare):
        return True, "compare"
    if isinstance(grandparent, ast.Compare) and isinstance(parent, (ast.List, ast.Tuple, ast.Set)):
        if parent is grandparent.left or parent in grandparent.comparators:
            return True, "compare"
    if isinstance(parent, ast.Dict):
        return True, "dict"
    if isinstance(parent, ast.DictComp) and node in (parent.key, parent.value):
        return True, "dictcomp"
    if isinstance(parent, ast.Subscript) and parent.slice is node:
        return True, "subscript"
    if isinstance(parent, ast.keyword):
        call = _enclosing_call(parent, parents)
        callee = _dotted_name(call.func) if call is not None else None
        if parent.arg in _SPAWN_KEYWORDS or _is_spawner(callee) or _is_mutator(callee):
            return False, "spawner-keyword"
        return True, "keyword"
    if isinstance(parent, ast.Call):
        callee = _dotted_name(parent.func)
        if _is_mutator(callee) and isinstance(parent.func, ast.Attribute):
            recv = parent.func.value
            tainted = _tainted_in_scope(node, parents, scope_taints)
            if isinstance(recv, ast.Name):
                if recv.id not in tainted:
                    return True, "mutator-untainted"
                return False, "mutator-tainted"
            return False, "mutator-attribute"
        if _is_spawner(callee) or _is_mutator(callee):
            return False, "spawner-or-mutator-call"
        if node in parent.args:
            return True, "call-arg"
        return False, "call-non-arg"
    if isinstance(parent, (ast.List, ast.Tuple, ast.Set)):
        if isinstance(grandparent, ast.Return) and _vendor_source_pair_tuple(parent):
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
                tainted = _tainted_in_scope(node, parents, scope_taints)
                if isinstance(target, ast.Name) and target.id not in tainted:
                    return True, "vendor-enum-assign"
            if isinstance(grandparent, ast.IfExp):
                return True, "vendor-enum-ifexp"
            if isinstance(grandparent, ast.BinOp) and isinstance(parent, ast.Set):
                return True, "vendor-enum-binop"
        return False, "display"
    return False, "disallowed"


def _string_command_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return _command_word_is_claude(node.value)
    if isinstance(node, ast.JoinedStr):
        return _joined_str_first_token_is_claude(node)
    return False


def _string_command_violations(tree, parents, relpath):
    out = []
    for node in ast.walk(tree):
        if not _string_command_node(node):
            continue
        parent = parents.get(node)
        if parent is None:
            continue
        if isinstance(parent, ast.Attribute) and parent.attr == "split" and parent.value is node:
            out.append((relpath, node.lineno, "string-split", _enclosing_function(node, parents)))
            continue
        if isinstance(parent, ast.Call):
            callee = _dotted_name(parent.func)
            if callee == "shlex.split" and parent.args and parent.args[0] is node:
                out.append((relpath, node.lineno, "string-shlex", _enclosing_function(node, parents)))
                continue
            if _is_spawner(callee) and node in parent.args:
                out.append((relpath, node.lineno, "string-spawner", _enclosing_function(node, parents)))
                continue
            for kw in parent.keywords:
                if kw.value is node and (
                    kw.arg in _SPAWN_KEYWORDS or _is_spawner(callee) or _is_mutator(callee)
                ):
                    out.append((relpath, node.lineno, "string-spawner", _enclosing_function(node, parents)))
                    break
    return out


def _violations(source_text, relpath):
    try:
        tree = ast.parse(source_text, filename=relpath)
    except SyntaxError:
        return [(relpath, 0, "unparseable", "<module>")]
    parent_visitor = _ParentVisitor()
    parent_visitor.visit(tree)
    parents = parent_visitor.parents
    scope_taints = _scope_taint_map(tree)
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not _is_claude_literal(node.value):
            continue
        parent = parents.get(node)
        grandparent = parents.get(parent) if parent is not None else None
        allowed, context = _allowed_constant(node, parent, grandparent, scope_taints, parents)
        if not allowed:
            function = _enclosing_function(node, parents)
            out.append((relpath, node.lineno, context, function))
    out.extend(_string_command_violations(tree, parents, relpath))
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


def _census_problems(violations):
    problems = []
    for relpath, lineno, _context, _function in violations:
        problems.append("claude-argv-outside-adapter:%s:%d" % (relpath, lineno))
    return sorted(problems)


def test_no_claude_argv_outside_engine_adapter():
    """axis: violation set outside engine_adapter is exactly launcher compose_launch (#1273)."""
    problems = _census_problems(_all_violations())
    expected = ["claude-argv-outside-adapter:lib/launcher.py:1102"]
    assert problems == expected, "\n".join(problems)


_FLAG_CASES = [
    ('argv = ["claude", "--bg"]', "list-display"),
    ('cmd = ["claude"] + list(args)', "binop-argv"),
    ('cmd = ["/usr/local/bin/claude"]\ncmd += ["--bg"]', "augassign-argv"),
    ('binary = "claude"\ncmd = [binary, "--bg"]', "indirect-argv"),
    ('subprocess.run(["/usr/local/bin/claude", "-p"])', "path-spelling"),
    ('subprocess.run(["env", "FOO=1", "claude", "-p"])', "env-wrapper"),
    ('cmd = ["x"]\nsubprocess.run(cmd)\ncmd.append("claude")', "append-mutator-tainted"),
    ('subprocess.Popen("claude")', "popen-string"),
    ('subprocess.Popen(["--bg"], executable="claude")', "popen-executable-keyword"),
    ('cmd = ("claude", arg)\nsubprocess.run(cmd)', "vendor-pair-spawn"),
    ('"claude -p --model opus".split()', "string-split-const"),
    ('m = "opus"\nf"claude -p --model {m}".split()', "string-split-fstring"),
    ('import shlex\nshlex.split("claude -p")', "string-shlex"),
    ('subprocess.run("claude -p", shell=True)', "string-spawner-shell"),
    ('import os\nos.system("claude -p")', "string-os-system"),
    ('argv = ["claude" if x else "claude2"]', "ifexp-display"),
    ('CLAUDE_EXECUTABLE = "claude"', "name-binding"),
    ('bad = ["claude"]\nif x == [["claude"]]: pass', "compare-nested-list"),
    ('import os\nos.system("env FOO=1 claude -p")', "string-os-system-env-wrapper"),
    ('import os\nos.popen("FOO=1 claude -p")', "string-os-popen-assignment"),
    ('import shlex\nshlex.split("env FOO=1 claude -p")', "string-shlex-env-wrapper"),
    ('"env -i /usr/bin/claude -p".split()', "string-split-env-option-path"),
    ('subprocess.run("A=1 B=2 claude", shell=True)', "string-spawner-two-assignments"),
    ('v = "1"\nf"env FOO={v} claude -p".split()', "string-split-fstring-env-assignment"),
]

_PASS_CASES = [
    ('if vendor == "claude": pass', "compare"),
    ('x = {"claude": 1}', "dict"),
    ('def f():\n return ["claude"]', "return-list"),
    ('family_for(tier, "claude")', "call-arg"),
    ('live = []\nif "claude" not in live:\n live.append("claude")', "mutator-untainted"),
    ('print("claude session ended")', "log-message"),
    ('print(input="claude")', "keyword-non-spawn"),
    ('def f():\n return "claude", VENDOR_SOURCE_DEFAULTED', "vendor-source-pair"),
    ('f"{x} claude".split()', "fstring-formatted-first"),
    ('import os\nos.system("env FOO=1 echo claude")', "string-env-wrapper-other-command"),
    ('"FOO=claude run".split()', "string-assignment-value-not-command"),
]

_EDGE_FLAG_CASES = [
    ('def f():\n pass\n+\n', "syntax-error"),
    ('x = [["claude"]]', "nested-display"),
    ('a = "claude" if x else "other"\nb = "other" if x else "claude"', "ifexp-nested"),
    ('a = b\nb = c\nc = "claude"\nsubprocess.run([a])', "taint-chain"),
    ('class C:\n def m(self):\n  self.cmd.append("claude")', "mutator-attribute"),
    ('"/opt/bin/claude -p".split()', "path-spelling-split"),
]

_EDGE_PASS_CASES = [
    ('f"{x} claude"', "fstring-formatted-first-bare"),
    (
        'def outer():\n def inner():\n  cmd = ["x"]\n  subprocess.run(cmd)\n inner()\n live = []\n live.append("claude")',
        "nested-scope-no-leak",
    ),
]


@pytest.mark.parametrize("source,label", _FLAG_CASES, ids=[c[1] for c in _FLAG_CASES])
def test_census_flags_every_argv_spelling(source, label):
    hits = _violations(source, "synthetic.py")
    assert hits, "expected violation for %s: %s" % (label, source)


@pytest.mark.parametrize("source,label", _PASS_CASES, ids=[c[1] for c in _PASS_CASES])
def test_census_allows_non_argv_contexts(source, label):
    hits = _violations(source, "synthetic.py")
    assert hits == [], hits


@pytest.mark.parametrize("source,label", _EDGE_FLAG_CASES, ids=[c[1] for c in _EDGE_FLAG_CASES])
def test_census_fail_closed_edges(source, label):
    hits = _violations(source, "synthetic.py")
    assert hits, "expected violation for %s: %s" % (label, source)


@pytest.mark.parametrize("source,label", _EDGE_PASS_CASES, ids=[c[1] for c in _EDGE_PASS_CASES])
def test_census_edge_pass_cases(source, label):
    hits = _violations(source, "synthetic.py")
    assert hits == [], hits
