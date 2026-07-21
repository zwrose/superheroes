"""CONVENTIONS-style contract enforcement for lens-contract 'Tool invocation'.

Statically scans every guardian lens module and asserts none import or call
subprocess/os spawn primitives directly — external invocation must route through
guardian_tools (the seam module itself is exempt).
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
_BANNED_OS_ATTRS = frozenset({"system", "popen"})
_BANNED_SUBPROCESS_ATTRS = frozenset({"Popen", "run", "call", "check_call", "check_output"})


def _lens_module_paths():
    pattern = os.path.join(_LIB, "guardian_lens*.py")
    return sorted(glob.glob(pattern))


def _imports_banned(node):
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name.split(".")[0] in _BANNED_MODULES:
                return alias.name
    if isinstance(node, ast.ImportFrom) and node.module:
        if node.module.split(".")[0] in _BANNED_MODULES:
            return node.module
    return None


def _call_is_banned(node):
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        if func.value.id == "os" and func.attr in _BANNED_OS_ATTRS:
            return "os.%s" % func.attr
        if func.value.id == "subprocess" and func.attr in _BANNED_SUBPROCESS_ATTRS:
            return "subprocess.%s" % func.attr
    if isinstance(func, ast.Name) and func.id == "Popen":
        return "Popen"
    return None


def test_lens_modules_do_not_spawn_directly():
    """Every guardian_lens*.py module must route external invocation through guardian_tools."""
    paths = _lens_module_paths()
    assert paths, "expected at least guardian_lens.py in the lib package"
    offenders = []
    for path in paths:
        if os.path.basename(path) == "guardian_tools.py":
            continue
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
        for node in ast.walk(tree):
            banned_import = _imports_banned(node)
            if banned_import:
                offenders.append((path, "import %s" % banned_import))
                break
            banned_call = _call_is_banned(node)
            if banned_call:
                offenders.append((path, "call %s" % banned_call))
    assert offenders == [], (
        "lens modules must not spawn directly — use guardian_tools.invoke: %s"
        % offenders
    )
