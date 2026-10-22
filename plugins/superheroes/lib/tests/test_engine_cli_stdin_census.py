"""Best-effort census (#777): an engine CLI spawn in shipped plugin code must not inherit stdin.

The scan is an AST pass over every shipped ``.py`` under ``plugins/superheroes/`` (minus ``tests/``,
``__pycache__`` and ``fixtures``). A file is an *engine file* when it holds an engine argv source: a
list/tuple display of two or more elements whose first element is the string ``codex``,
``cursor-agent`` or ``claude`` (or a path ending ``/codex``, ``/cursor-agent``, ``/claude``), or a call
to an ``engine_adapter`` argv builder (a public ``*_argv`` function of ``engine_adapter`` or
``build_argv_result``) whatever its receiver. In an engine file every *spawner call* must be
compliant. Spawners are the ``subprocess`` ``run``/``Popen``/``call``/``check_call``/``check_output``
attributes and the module-local names bound to one (an assignment from a spawner, a conditional or
``or``/``and`` with a spawner operand, a parameter whose default is a spawner or that the body rebinds
from one, or a parameter some call in the module passes a spawner-bound name into), resolved scope by
scope to a fixpoint. ``run_engine_cli`` is never a spawner call. ``lib/engine_adapter.py`` and
``lib/engine_dispatch.py`` own their stdin explicitly and are allowlisted by relative path.

A spawner call is compliant when its first argument is a list/tuple display led by a string literal that
is not an engine word (``git``, ``gh``, ``xcrun``), or it passes ``input=`` with anything but the
constant ``None``, or it passes ``stdin=`` with anything but the constant ``None``, the constant ``0`` or
``sys.stdin``. A call carrying ``**kwargs`` and no explicit ``stdin=``/``input=`` is non-compliant
(fail closed). The census therefore accepts ``stdin=subprocess.PIPE``: a pipe the caller owns is not an
inherited stdin. This deliberately differs from ``engine_adapter.run_engine_cli``, which accepts only
``subprocess.DEVNULL`` (or ``input=``) and refuses every other ``stdin=``.

Residuals this census does not see: an argv built in a helper outside ``engine_adapter`` and returned
into a file with no other engine source; argv taken from config or another module in such a file; a
spawner reached through an alias the module scope does not show (imported from elsewhere,
``functools.partial``, ``getattr``); a runtime ``None`` passed as ``input=``/``stdin=`` through a
variable; shell-string commands (``os.system``, ``os.popen``, ``shell=True``); other process starters
outside the spawner set (``os.exec*``, ``os.spawn*``, ``os.posix_spawn*``, ``pty.spawn``/``pty.fork``,
``asyncio.create_subprocess_exec``/``_shell``); and the two allowlisted files.
"""
import ast
import inspect
import os
import sys
from pathlib import Path

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
_PLUGIN_ROOT = os.path.realpath(os.path.join(_LIB, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import engine_adapter  # noqa: E402

_ALLOWLIST = frozenset(("lib/engine_adapter.py", "lib/engine_dispatch.py"))
_ENGINE_WORDS = ("codex", "cursor-agent", "claude")
_SPAWN_ATTRS = frozenset(("run", "Popen", "call", "check_call", "check_output"))
_HELPER_NAME = "run_engine_cli"
_FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef)
_SKIP_DIRS = frozenset(("tests", "__pycache__", "fixtures"))

# The builders are computed from the adapter itself, so a new `*_argv` builder is covered unasked.
_BUILDERS = frozenset(
    {name for name, obj in vars(engine_adapter).items()
     if inspect.isfunction(obj) and not name.startswith("_") and name.endswith("_argv")}
    | {"build_argv_result"})


def _is_engine_word(value):
    return isinstance(value, str) and any(
        value == word or value.endswith("/" + word) for word in _ENGINE_WORDS)


def _first_literal(node):
    """The first element's string value of a non-empty list/tuple display; None for anything else."""
    if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
        first = node.elts[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
    return None


def _callee_name(call):
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _is_engine_file(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.List, ast.Tuple)) and len(node.elts) >= 2:
            if _is_engine_word(_first_literal(node)):
                return True
        if isinstance(node, ast.Call) and _callee_name(node) in _BUILDERS:
            return True
    return False


class _Scope:
    def __init__(self, node, parent):
        self.node = node
        self.parent = parent
        self.defined = set()
        self.bound = set()
        self.own = []


def _build_scopes(tree):
    module = _Scope(tree, None)
    scopes = [module]
    by_name = {}

    def visit(node, scope):
        if isinstance(node, _FUNCS):
            scope.defined.add(node.name)
            inner = _Scope(node, scope)
            scopes.append(inner)
            by_name.setdefault(node.name, []).append(inner)
            args = node.args
            for param in _all_params(args):
                inner.defined.add(param.arg)
            for expr in node.decorator_list + args.defaults + [d for d in args.kw_defaults if d]:
                visit(expr, scope)
            for stmt in node.body:
                visit(stmt, inner)
            return
        scope.own.append(node)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            scope.defined.add(node.id)
        elif isinstance(node, ast.ClassDef):
            scope.defined.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                scope.defined.add((alias.asname or alias.name).split(".")[0])
        for child in ast.iter_child_nodes(node):
            visit(child, scope)

    for stmt in tree.body:
        visit(stmt, module)
    return scopes, by_name


def _all_params(args):
    params = list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)
    if args.vararg:
        params.append(args.vararg)
    if args.kwarg:
        params.append(args.kwarg)
    return params


def _default_pairs(args):
    positional = list(args.posonlyargs) + list(args.args)
    pairs = list(zip(positional[len(positional) - len(args.defaults):], args.defaults))
    pairs += [(p, d) for p, d in zip(args.kwonlyargs, args.kw_defaults) if d is not None]
    return pairs


def _subprocess_names(tree):
    names = {"subprocess"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "subprocess" and alias.asname:
                    names.add(alias.asname)
    return names


def _resolve(name, scope):
    while scope is not None:
        if name in scope.defined:
            return name in scope.bound
        scope = scope.parent
    return False


def _is_spawner_expr(expr, scope, sp_names):
    if isinstance(expr, ast.Attribute):
        return (isinstance(expr.value, ast.Name) and expr.value.id in sp_names
                and expr.attr in _SPAWN_ATTRS)
    if isinstance(expr, ast.Name):
        return _resolve(expr.id, scope)
    if isinstance(expr, ast.IfExp):
        return (_is_spawner_expr(expr.body, scope, sp_names)
                or _is_spawner_expr(expr.orelse, scope, sp_names))
    if isinstance(expr, ast.BoolOp):
        return any(_is_spawner_expr(v, scope, sp_names) for v in expr.values)
    return False


def _propagate(scopes, by_name, sp_names):
    changed = True
    while changed:
        changed = False
        for scope in scopes:
            if isinstance(scope.node, _FUNCS):
                for param, default in _default_pairs(scope.node.args):
                    if param.arg not in scope.bound and _is_spawner_expr(
                            default, scope.parent, sp_names):
                        scope.bound.add(param.arg)
                        changed = True
            for node in scope.own:
                if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                    value = node.value
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    if value is not None and _is_spawner_expr(value, scope, sp_names):
                        for target in targets:
                            if isinstance(target, ast.Name) and target.id not in scope.bound:
                                scope.bound.add(target.id)
                                changed = True
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    for callee in by_name.get(node.func.id, ()):
                        changed |= _bind_call_args(node, callee, scope, sp_names)


def _bind_call_args(call, callee, scope, sp_names):
    changed = False
    positional = list(callee.node.args.posonlyargs) + list(callee.node.args.args)
    names = {p.arg for p in _all_params(callee.node.args)}
    for index, arg in enumerate(call.args):
        if isinstance(arg, ast.Starred) or index >= len(positional):
            break
        if _is_spawner_expr(arg, scope, sp_names) and positional[index].arg not in callee.bound:
            callee.bound.add(positional[index].arg)
            changed = True
    for kw in call.keywords:
        if kw.arg in names and _is_spawner_expr(kw.value, scope, sp_names) \
                and kw.arg not in callee.bound:
            callee.bound.add(kw.arg)
            changed = True
    return changed


def _keyword(call, name):
    for kw in call.keywords:
        if kw.arg == name:
            return kw
    return None


def _is_none(node):
    return isinstance(node, ast.Constant) and node.value is None


def _is_inherited_stdin(node):
    if _is_none(node):
        return True
    if isinstance(node, ast.Constant) and node.value == 0 and node.value is not False:
        return True
    return (isinstance(node, ast.Attribute) and node.attr == "stdin"
            and isinstance(node.value, ast.Name) and node.value.id == "sys")


def _compliant(call):
    first = _first_literal(call.args[0]) if call.args else None
    if first is not None and not _is_engine_word(first):
        return True
    input_kw = _keyword(call, "input")
    if input_kw is not None and not _is_none(input_kw.value):
        return True
    stdin_kw = _keyword(call, "stdin")
    if stdin_kw is not None and not _is_inherited_stdin(stdin_kw.value):
        return True
    if any(kw.arg is None for kw in call.keywords):
        return False  # **kwargs may carry input=None / stdin=None: fail closed
    return False


def violations(source_text, relpath):
    """Every engine-file spawner call whose stdin is not closed, as "relpath:line" strings."""
    if relpath in _ALLOWLIST:
        return []
    try:
        tree = ast.parse(source_text, filename=relpath)
    except SyntaxError:
        return ["%s:0" % relpath]
    if not _is_engine_file(tree):
        return []
    sp_names = _subprocess_names(tree)
    scopes, by_name = _build_scopes(tree)
    _propagate(scopes, by_name, sp_names)
    found = []
    for scope in scopes:
        for node in scope.own:
            if not isinstance(node, ast.Call) or _callee_name(node) == _HELPER_NAME:
                continue
            if _is_spawner_expr(node.func, scope, sp_names) and not _compliant(node):
                found.append("%s:%d" % (relpath, node.lineno))
    return sorted(set(found))


def _shipped_files():
    root = Path(_PLUGIN_ROOT)
    files = []
    for path in root.rglob("*.py"):
        parts = path.relative_to(root).parts
        if _SKIP_DIRS.intersection(parts):
            continue
        files.append(path.relative_to(root).as_posix())
    return sorted(files)


# --- the real tree -------------------------------------------------------------------------------

def test_builder_set_covers_the_known_adapter_builders():
    assert {"build_argv", "build_argv_result", "claude_builder_argv", "claude_cloud_builder_argv",
            "claude_agents_list_argv", "claude_relay_argv"} <= _BUILDERS


def test_repo_has_no_engine_spawn_that_inherits_stdin():
    files = _shipped_files()
    assert "lib/launcher.py" in files and "lib/cloud_relay.py" in files
    assert not any("/tests/" in "/" + rel for rel in files)
    problems = []
    for rel in files:
        problems.extend(violations(Path(_PLUGIN_ROOT, rel).read_text(encoding="utf-8"), rel))
    assert problems == [], "\n".join(problems)


# --- fixtures ------------------------------------------------------------------------------------

_FLAG = [
    ("raw-codex-run",
     'import subprocess\nsubprocess.run(["codex", "exec", "x"], capture_output=True)\n', 2),
    ("raw-cursor-popen", 'import subprocess\nsubprocess.Popen(["cursor-agent", "-p", "x"])\n', 2),
    ("alias-run-name",
     'import subprocess\nrun = subprocess.run\nrun(["claude", "-p", "x"])\n', 3),
    ("builder-argv-into-run",
     'import subprocess\nimport engine_adapter\n'
     'subprocess.run(engine_adapter.claude_agents_list_argv()["argv"])\n', 3),
    ("input-none", 'import subprocess\nsubprocess.run(["codex", "exec", "x"], input=None)\n', 2),
    ("stdin-none", 'import subprocess\nsubprocess.run(["codex", "exec", "x"], stdin=None)\n', 2),
    ("stdin-sys-stdin",
     'import subprocess\nimport sys\nsubprocess.run(["codex", "exec", "x"], stdin=sys.stdin)\n', 3),
    ("stdin-fd-zero", 'import subprocess\nsubprocess.run(["codex", "exec", "x"], stdin=0)\n', 2),
    ("star-kwargs", 'import subprocess\nsubprocess.run(["codex", "exec", "x"], **kw)\n', 2),
    ("passed-in-runner",
     'import subprocess\n'
     'def probe(run=None):\n'
     '    run = run or subprocess.run\n'
     '    return one(run)\n'
     'def one(run):\n'
     '    return run(["codex", "login", "status"])\n', 6),
    ("default-param-spawner",
     'import subprocess\ndef go(run=subprocess.run):\n    return run(["codex", "x"])\n', 3),
    ("unparseable", 'def f(:\n', 0),
]

_PASS = [
    ("helper-call",
     'import engine_adapter\nengine_adapter.run_engine_cli(["codex", "exec", "x"], run=run)\n'),
    ("git-in-engine-file",
     'import subprocess\nENGINE = ["codex", "exec"]\nsubprocess.run(["git", "status"])\n'),
    ("devnull-in-engine-file",
     'import subprocess\nENGINE = ["codex", "exec"]\nsubprocess.Popen(argv, stdin=subprocess.DEVNULL)\n'),
    ("input-empty-string", 'import subprocess\nsubprocess.run(["codex", "exec", "x"], input="")\n'),
    ("stdin-pipe-caller-owned",
     'import subprocess\nsubprocess.Popen(["codex", "exec", "x"], stdin=subprocess.PIPE)\n'),
    ("no-engine-source", 'import subprocess\nsubprocess.run(argv)\n'),
    ("unbound-run-name", 'ENGINE = ["codex", "exec"]\ndef f(run):\n    return run(["codex", "x"])\n'),
]


@pytest.mark.parametrize("source,line", [(s, n) for _i, s, n in _FLAG], ids=[c[0] for c in _FLAG])
def test_census_flags(source, line):
    assert violations(source, "lib/synthetic.py") == ["lib/synthetic.py:%d" % line]


@pytest.mark.parametrize("source", [s for _i, s in _PASS], ids=[c[0] for c in _PASS])
def test_census_passes(source):
    assert violations(source, "lib/synthetic.py") == []


@pytest.mark.parametrize("relpath", sorted(_ALLOWLIST))
def test_census_allowlists_the_two_files_by_relative_path(relpath):
    source = 'import subprocess\nsubprocess.run(["codex", "exec", "x"])\n'
    assert violations(source, relpath) == []
    assert violations(source, "lib/other.py") == ["lib/other.py:2"]


# --- break-it on the real sources ----------------------------------------------------------------

def _sp(count):
    return " " * count


# (file, [(current text, original main-78e025e3 text)...], marker of the restored call)
_BREAK_IT = [
    ("lib/engine_authz.py",
     [("proc = engine_adapter.run_engine_cli(argv, run=run, capture_output=True, text=True,\n"
       + _sp(45) + "timeout=timeout, cwd=cwd)",
       "proc = run(argv, capture_output=True, text=True, timeout=timeout, cwd=cwd)")],
     "proc = run(argv,"),
    ("lib/engine_detect.py",
     [("proc = engine_adapter.run_engine_cli(auth_argv, run=run, capture_output=True, text=True,\n"
       + _sp(45) + "timeout=10, cwd=root)",
       "proc = run(auth_argv, capture_output=True, text=True, timeout=10, cwd=root)")],
     "proc = run(auth_argv,"),
    ("lib/cloud_relay.py",
     [('when it could not run at all."""\n',
       'when it could not run at all."""\n' + _sp(4) + "runner = subprocess.run if run is None else run\n"),
      ('proc = _sibling("engine_adapter").run_engine_cli(\n'
       + _sp(12) + "argv, run=run, capture_output=True, text=True, timeout=timeout, env=env, cwd=cwd)",
       "proc = runner(list(argv), capture_output=True, text=True, timeout=timeout, env=env,\n"
       + _sp(22) + "cwd=cwd)")],
     "proc = runner(list(argv),"),
    ("lib/preflight_probe.py",
     [("proc = engine_adapter.run_engine_cli(argv, run=run, **run_kw)",
       "proc = run(list(argv), **run_kw)")],
     "proc = run(list(argv), **run_kw)"),
]


@pytest.mark.parametrize("relpath,edits,marker", _BREAK_IT, ids=[c[0] for c in _BREAK_IT])
def test_census_flags_each_site_restored_to_its_original_spawn(relpath, edits, marker):
    text = Path(_PLUGIN_ROOT, relpath).read_text(encoding="utf-8")
    assert violations(text, relpath) == []
    for current, original in edits:
        assert text.count(current) == 1, current
        text = text.replace(current, original)
    assert text.count(marker) == 1, marker
    line = text[:text.index(marker)].count("\n") + 1
    assert violations(text, relpath) == ["%s:%d" % (relpath, line)]
