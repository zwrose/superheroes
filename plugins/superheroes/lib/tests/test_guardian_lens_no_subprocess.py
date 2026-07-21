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
_BANNED_OS_ATTRS = frozenset({"system", "popen", "posix_spawn", "posix_spawnp"})
_BANNED_OS_ATTR_PREFIXES = ("exec", "spawn")
_BANNED_SUBPROCESS_ATTRS = frozenset({
    "Popen", "run", "call", "check_call", "check_output",
})
_BANNED_OS_FROM_NAMES = frozenset({
    "system", "popen", "posix_spawn", "posix_spawnp",
})
_BANNED_SUBPROCESS_FROM_NAMES = _BANNED_SUBPROCESS_ATTRS


def _lens_module_paths():
    pattern = os.path.join(_LIB, "guardian_lens*.py")
    return sorted(glob.glob(pattern))


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
