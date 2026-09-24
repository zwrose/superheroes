"""Census: admission path in engine_dispatch must not read filesystem timestamps (#1273 WO-C)."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ENGINE_DISPATCH_PATH = Path(__file__).resolve().parents[1] / "engine_dispatch.py"

ENTRY_POINTS = (
    "_load_native_result_json",
    "_admit_native_write_result",
    "_admit_native_review_result",
    "_read_native_review_envelope",
    "_stdout_delivery_gate",
    "_grade_write_attempt",
    "_grade_native_review_attempt",
)

_DIRECT_ATTR_SPELLINGS = frozenset({"st_mtime", "st_ctime", "getmtime", "getctime"})


def _module_functions(tree):
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def _callees(func_node):
    out = set()
    for node in ast.walk(func_node):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            out.add(func.id)
        elif isinstance(func, ast.Attribute):
            out.add(func.attr)
    return out


def _transitive_closure(funcs, roots):
    closure = set()
    stack = list(roots)
    while stack:
        name = stack.pop()
        if name in closure or name not in funcs:
            continue
        closure.add(name)
        for callee in _callees(funcs[name]):
            if callee in funcs and callee not in closure:
                stack.append(callee)
    return closure


def _forbidden_spellings(func_node):
    hits = []
    for node in ast.walk(func_node):
        if isinstance(node, ast.Attribute) and node.attr in _DIRECT_ATTR_SPELLINGS:
            hits.append(node.attr)
            continue
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            if func.attr in ("stat", "lstat"):
                if isinstance(func.value, ast.Name) and func.value.id == "os":
                    hits.append("os.%s" % func.attr)
                else:
                    hits.append(".stat(")
    return hits


def _admission_closure():
    source = ENGINE_DISPATCH_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(ENGINE_DISPATCH_PATH))
    funcs = _module_functions(tree)
    return funcs, _transitive_closure(funcs, ENTRY_POINTS)


def test_admission_path_closure_covers_entry_points():
    funcs, closure = _admission_closure()
    assert closure, "admission-path closure is empty"
    for name in ENTRY_POINTS:
        assert name in closure, "entry point %s missing from closure" % name


def test_admission_path_does_not_read_filesystem_timestamps():
    funcs, closure = _admission_closure()
    offenses = []
    for name in sorted(closure):
        for spelling in _forbidden_spellings(funcs[name]):
            offenses.append((name, spelling))
    assert not offenses, offenses


def test_admission_path_vacuity_guard_fails_on_renamed_entry_point():
    source = ENGINE_DISPATCH_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(ENGINE_DISPATCH_PATH))
    funcs = _module_functions(tree)
    closure = _transitive_closure(funcs, ("_load_native_result_json_typo",))
    assert "_load_native_result_json" not in closure
