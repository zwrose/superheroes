"""CONVENTIONS-style contract enforcement for lens-contract 'Tool invocation'.

Statically scans every guardian lens module and asserts none import or call
subprocess/os spawn primitives directly — external invocation must route through
guardian_tools (the seam module itself is exempt).

Sanctioned spawners outside the lens set: guardian_sweep.py (orchestrator) and
guardian_tools.py (invocation seam).
"""
import ast
import glob
import os
import sys

import pytest

_LIB = os.path.join(os.path.dirname(__file__), "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

_BANNED_MODULES = frozenset({"subprocess"})
# fork / forkpty do not start with an exec/spawn prefix and are not posix_spawn(p), so they
# must be banned by exact name — the runtime patch (test_guardian_conformance) already
# guards them; this is the fail-closed static complement (H5).
_BANNED_OS_ATTRS = frozenset(
    {"system", "popen", "fork", "forkpty", "posix_spawn", "posix_spawnp"})
_BANNED_OS_ATTR_PREFIXES = ("exec", "spawn")
_BANNED_SUBPROCESS_ATTRS = frozenset({
    "Popen", "run", "call", "check_call", "check_output",
})
_BANNED_OS_FROM_NAMES = frozenset({
    "system", "popen", "fork", "forkpty", "posix_spawn", "posix_spawnp",
})
_BANNED_SUBPROCESS_FROM_NAMES = _BANNED_SUBPROCESS_ATTRS


def _lens_module_paths():
    pattern = os.path.join(_LIB, "guardian_lens*.py")
    paths = sorted(glob.glob(pattern))
    census = os.path.join(_LIB, "guardian_census.py")
    if census not in paths:
        paths.append(census)
    return sorted(paths)


def _os_attr_is_banned(attr):
    if attr in _BANNED_OS_ATTRS:
        return True
    return any(attr.startswith(prefix) for prefix in _BANNED_OS_ATTR_PREFIXES)


def _os_from_name_is_banned(name):
    if name in _BANNED_OS_FROM_NAMES:
        return True
    return any(name.startswith(prefix) for prefix in _BANNED_OS_ATTR_PREFIXES)


def _collect_module_aliases(tree):
    """Map import aliases to canonical module roots (os, subprocess)."""
    aliases = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Import):
            continue
        for alias in node.names:
            root = alias.name.split(".")[0]
            if root in ("os", "subprocess"):
                aliases[alias.asname or root] = root
    return aliases


def _collect_imported_spawn_names(tree):
    """Map bare names imported from os/subprocess to their spawn primitives."""
    imported = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        mod_root = node.module.split(".")[0]
        if mod_root == "os":
            for alias in node.names:
                if _os_from_name_is_banned(alias.name):
                    imported[alias.asname or alias.name] = "os.%s" % alias.name
        elif mod_root == "subprocess":
            for alias in node.names:
                if alias.name in _BANNED_SUBPROCESS_FROM_NAMES:
                    imported[alias.asname or alias.name] = "subprocess.%s" % alias.name
    return imported


def _imports_banned(node):
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name.split(".")[0] in _BANNED_MODULES:
                return alias.name
    if isinstance(node, ast.ImportFrom) and node.module:
        if node.module.split(".")[0] in _BANNED_MODULES:
            return node.module
    return None


def _call_is_banned(node, imported_spawn_names, module_aliases):
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        receiver = func.value.id
        os_receiver = receiver == "os" or module_aliases.get(receiver) == "os"
        subprocess_receiver = (
            receiver == "subprocess" or module_aliases.get(receiver) == "subprocess")
        if os_receiver and _os_attr_is_banned(func.attr):
            return "os.%s" % func.attr
        if subprocess_receiver and func.attr in _BANNED_SUBPROCESS_ATTRS:
            return "subprocess.%s" % func.attr
    if isinstance(func, ast.Name):
        if func.id == "Popen":
            return "Popen"
        if func.id in imported_spawn_names:
            return "call %s (imported spawn)" % imported_spawn_names[func.id]
    return None


def _find_spawn_offenders(source, filename="<memory>"):
    tree = ast.parse(source, filename=filename)
    imported_spawn_names = _collect_imported_spawn_names(tree)
    module_aliases = _collect_module_aliases(tree)
    offenders = []
    for node in ast.walk(tree):
        banned_import = _imports_banned(node)
        if banned_import:
            offenders.append("import %s" % banned_import)
            break
        banned_call = _call_is_banned(node, imported_spawn_names, module_aliases)
        if banned_call:
            offenders.append("call %s" % banned_call)
    return offenders


def test_lens_modules_do_not_spawn_directly():
    """Every guardian_lens*.py module must route external invocation through guardian_tools."""
    paths = _lens_module_paths()
    assert paths, "expected at least guardian_lens.py in the lib package"
    offenders = []
    for path in paths:
        if os.path.basename(path) == "guardian_tools.py":
            continue
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        for hit in _find_spawn_offenders(source, filename=path):
            offenders.append((path, hit))
    assert offenders == [], (
        "lens modules must not spawn directly — use guardian_tools.invoke: %s"
        % offenders
    )


def test_spawn_detector_flags_imported_os_system():
    """Non-vacuity: broadened detector must catch `from os import system` + bare call."""
    source = "from os import system\nsystem('x')\n"
    offenders = _find_spawn_offenders(source)
    assert offenders, "expected imported os.system to be flagged"
    assert any("system" in hit for hit in offenders)


def test_spawn_detector_flags_aliased_os_system_and_exec_spawn():
    """Non-vacuity: alias imports and exec/spawn attribute calls must be flagged."""
    alias_source = "import os as _p\n_p.system('x')\n"
    offenders = _find_spawn_offenders(alias_source)
    assert offenders, "expected aliased os.system to be flagged"
    assert any("system" in hit for hit in offenders)

    exec_source = "import os\nos.execv('/bin/sh', ['sh'])\n"
    offenders = _find_spawn_offenders(exec_source)
    assert offenders, "expected os.execv to be flagged"
    assert any("execv" in hit for hit in offenders)

    spawn_source = "import os\nos.spawnv(os.P_WAIT, '/bin/sh', ['sh'])\n"
    offenders = _find_spawn_offenders(spawn_source)
    assert offenders, "expected os.spawnv to be flagged"
    assert any("spawnv" in hit for hit in offenders)


def test_spawn_detector_flags_os_fork_and_forkpty():
    """H5 non-vacuity: os.fork / os.forkpty evade the exec/spawn prefixes and are not
    posix_spawn(p) — a planted os.fork() in a fake lens must be caught, direct + aliased +
    `from os import fork`."""
    direct_source = "import os\nos.fork()\n"
    offenders = _find_spawn_offenders(direct_source)
    assert offenders, "expected os.fork to be flagged"
    assert any("fork" in hit for hit in offenders)

    forkpty_source = "import os\nos.forkpty()\n"
    offenders = _find_spawn_offenders(forkpty_source)
    assert offenders, "expected os.forkpty to be flagged"
    assert any("forkpty" in hit for hit in offenders)

    alias_source = "import os as _p\n_p.fork()\n"
    offenders = _find_spawn_offenders(alias_source)
    assert offenders, "expected aliased os.fork to be flagged"
    assert any("fork" in hit for hit in offenders)

    from_source = "from os import fork\nfork()\n"
    offenders = _find_spawn_offenders(from_source)
    assert offenders, "expected `from os import fork` + bare call to be flagged"
    assert any("fork" in hit for hit in offenders)


def test_spawn_detector_flags_posix_spawn_direct_and_aliased():
    """Non-vacuity: posix_spawn / posix_spawnp evade exec/spawn prefixes — must flag."""
    direct_source = "import os\nos.posix_spawn('/bin/sh', ['sh'], os.environ)\n"
    offenders = _find_spawn_offenders(direct_source)
    assert offenders, "expected os.posix_spawn to be flagged"
    assert any("posix_spawn" in hit for hit in offenders)

    alias_source = "import os as _p\n_p.posix_spawn('/bin/sh', ['sh'], _p.environ)\n"
    offenders = _find_spawn_offenders(alias_source)
    assert offenders, "expected aliased posix_spawn to be flagged"
    assert any("posix_spawn" in hit for hit in offenders)


# --- lens argv guard: no npx --yes / acquisition / repo-local executables ----------
# The no-fetch scanners above cover guardian_tools.py, NOT lens argv. A lens could still
# call run_tool(["npx","--yes",…]) or name a repo-local executable as argv[0]. This guard
# statically scans every guardian_lens*.py tool-invocation argv literal and fails closed
# on an acquisition verb, an npx invocation, or a path-shaped argv[0] (a repo-local or
# relative executable, which the PATH-only resolution constraint forbids).

_ARGV_ACQUISITION_SUBSTRINGS = (
    "npm install", "npm i ", "npm add", "pip install", "pip3 install",
    "yarn add", "pnpm add", "brew install", "cargo install", "go install",
    "apt install", "apt-get install",
)


def _tool_invocation_calls(tree):
    """Yield (call_name, Call) for every run_tool(...) / invoke(...) call in the tree."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = None
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name in ("run_tool", "invoke"):
            yield name, node


def _list_element_nodes(node):
    """The element AST nodes of a List/Tuple literal, in order (or None if not one)."""
    if not isinstance(node, (ast.List, ast.Tuple)):
        return None
    return list(node.elts)


def _resolve_argv_nodes(node, func_node):
    """Resolve an argv expr to its element AST NODES (or None when unresolvable).

    Handles a direct list literal, the head of a ``[...] + rest`` concatenation, and a
    bare Name bound to a list literal within the enclosing function. Returns the element
    NODES (not just string constants) so argv[0] can be checked for being a statically
    vetted literal — a Name-bound / f-string / call-result head must not be silently
    dropped (that is the fail-open hole this closes).
    """
    direct = _list_element_nodes(node)
    if direct is not None:
        return direct
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _list_element_nodes(node.left)
        if left is not None:
            return left
    if isinstance(node, ast.Name) and func_node is not None:
        for assign in ast.walk(func_node):
            if not (isinstance(assign, ast.Assign) and len(assign.targets) == 1):
                continue
            target = assign.targets[0]
            if isinstance(target, ast.Name) and target.id == node.id:
                got = _resolve_argv_nodes(assign.value, func_node)
                if got is not None:
                    return got
    return None


def _const_str(node, func_node):
    """Statically resolve one element node to its string value, or None.

    A string ``Constant`` resolves directly; a ``Name`` bound to a string ``Constant`` in
    the enclosing function resolves to that constant (the real lenses bind e.g.
    ``tool = "pip-audit"`` then build ``argv = [tool, ...]``). Anything else — an f-string,
    a call result, a starred expr, a Name with no constant binding — is unresolvable.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and func_node is not None:
        for assign in ast.walk(func_node):
            if (isinstance(assign, ast.Assign) and len(assign.targets) == 1
                    and isinstance(assign.targets[0], ast.Name)
                    and assign.targets[0].id == node.id
                    and isinstance(assign.value, ast.Constant)
                    and isinstance(assign.value.value, str)):
                return assign.value.value
    return None


def _enclosing_functions(tree):
    return [n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _nearest_enclosing_function(call, funcs):
    containing = [
        f for f in funcs
        if f.lineno <= call.lineno <= getattr(f, "end_lineno", f.lineno)
    ]
    if not containing:
        return None
    return max(containing, key=lambda f: f.lineno)


def _argv_nodes_for_call(name, call, func_node):
    """(head_node, element_nodes) for a tool-invocation call, or (None, None) when the
    argv is unresolvable (e.g. a helper-returned argv the real vulture/knip lenses use —
    left uninspected here; their literal heads live one function away).

    ``head_node`` is the argv[0] AST node whose literalness must be verified.
    """
    if name == "run_tool":
        if not call.args:
            return (None, None)
        nodes = _resolve_argv_nodes(call.args[0], func_node)
        if not nodes:
            return (None, None)
        return (nodes[0], nodes)
    if name == "invoke":
        # invoke(tool, fixed_args, repo, targets, ...): argv[0] is `tool`, rest fixed_args.
        if not call.args:
            return (None, None)
        head = call.args[0]
        nodes = [head]
        if len(call.args) > 1:
            rest = _resolve_argv_nodes(call.args[1], func_node)
            if rest:
                nodes += rest
        return (head, nodes)
    return (None, None)


def _inspect_tool_call(name, call, func_node):
    head_node, nodes = _argv_nodes_for_call(name, call, func_node)
    if head_node is None:
        return []
    offenders = []
    # FAIL CLOSED: argv[0] must statically resolve to a vetted string literal. A Name-bound
    # non-constant, an f-string, a call result, or a starred head cannot be verified as a
    # PATH-only tool identity — flag it rather than inspecting the wrong element (the prior
    # guard dropped non-constant elements and silently checked argv[1] as if it were argv[0]).
    head = _const_str(head_node, func_node)
    if head is None:
        offenders.append(
            "non-literal argv[0] (%s) — cannot statically verify the tool identity is a "
            "vetted PATH-only literal" % type(head_node).__name__)
        return offenders
    if "/" in head or head.startswith("."):
        offenders.append("path-shaped argv[0] literal %r (repo-local/relative)" % head)
    # Resolve every string element (incl. Name→const) for the npx / acquisition scan.
    elts = [s for s in (_const_str(n, func_node) for n in nodes) if s is not None]
    if "npx" in elts:
        offenders.append("npx invocation in argv %r (fetch/acquisition)" % elts)
    joined = " ".join(elts)
    for verb in _ARGV_ACQUISITION_SUBSTRINGS:
        if verb in joined:
            offenders.append("acquisition verb %r in argv %r" % (verb, elts))
    return offenders


def _find_lens_argv_offenders(source, filename="<memory>"):
    tree = ast.parse(source, filename=filename)
    funcs = _enclosing_functions(tree)
    offenders = []
    for name, call in _tool_invocation_calls(tree):
        func_node = _nearest_enclosing_function(call, funcs)
        offenders += _inspect_tool_call(name, call, func_node)
    return offenders


def test_lens_argv_guard_flags_npx_yes():
    """Non-vacuity: npx --yes in a run_tool argv must be flagged."""
    assert _find_lens_argv_offenders('gc.run_tool(["npx", "--yes", "knip"], ctx=ctx)\n')


def test_lens_argv_guard_flags_acquisition_verb():
    """Non-vacuity: a split installer verb (npm install) in an argv must be flagged."""
    assert _find_lens_argv_offenders('run_tool(["npm", "install", "-g", "knip"])\n')


def test_lens_argv_guard_flags_repo_local_executable():
    """Non-vacuity: a path-shaped argv[0] (repo-local/relative) must be flagged."""
    assert _find_lens_argv_offenders(
        'run_tool(["./node_modules/.bin/knip", "--reporter", "json"])\n')
    assert _find_lens_argv_offenders(
        'run_tool(["/repo/bin/vulture", "src"])\n')


def test_lens_argv_guard_flags_indirect_argv_binding():
    """Non-vacuity: an argv bound to a Name then passed to run_tool is still scanned."""
    src = (
        "def collect(ctx):\n"
        "    argv = ['npx', '--yes', 'vulture']\n"
        "    return gc.run_tool(argv, ctx=ctx)\n"
    )
    assert _find_lens_argv_offenders(src)


def test_lens_argv_guard_flags_name_bound_head():
    """C1 fail-closed: a tool NAME bound to a variable used as argv[0].

    The prior guard dropped the non-constant head element and silently inspected argv[1]
    as if it were the tool — so a Name-bound `npx` slipped through. Now the head resolves
    (Name→const) and the npx scan catches it; a genuinely unresolvable head is flagged
    directly (see the f-string case below)."""
    src = (
        "def collect(ctx):\n"
        "    tool = 'npx'\n"
        "    argv = [tool, '--yes', 'vulture']\n"
        "    return gc.run_tool(argv, ctx=ctx)\n"
    )
    assert _find_lens_argv_offenders(src)


def test_lens_argv_guard_fails_closed_on_fstring_head():
    """C1 fail-closed: an f-string argv[0] cannot be statically vetted as a PATH-only
    literal — flag it rather than inspecting a later element."""
    src = (
        "def collect(ctx, base):\n"
        "    return gc.run_tool([f'{base}/knip', '--reporter', 'json'], ctx=ctx)\n"
    )
    offenders = _find_lens_argv_offenders(src)
    assert offenders and any("non-literal argv[0]" in o for o in offenders)


def test_lens_argv_guard_clears_a_clean_argv():
    """Non-vacuity in the other direction: a plain PATH-tool argv is not flagged."""
    assert _find_lens_argv_offenders('run_tool(["knip", "--reporter", "json"])\n') == []


def test_lens_modules_carry_no_acquisition_or_repo_local_argv():
    """Every guardian_lens*.py tool-invocation argv literal is PATH-only, no acquisition."""
    paths = _lens_module_paths()
    assert paths, "expected at least guardian_lens.py in the lib package"
    offenders = []
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        for hit in _find_lens_argv_offenders(source, filename=path):
            offenders.append((path, hit))
    assert offenders == [], (
        "lens argv must be PATH-only, no acquisition or repo-local executables: %s"
        % offenders
    )
