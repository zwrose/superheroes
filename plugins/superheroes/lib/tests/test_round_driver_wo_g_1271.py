"""#1271 WO-G — disposition ledger and findings-chokepoint guards."""
import ast
import importlib.util
import os
import sys

import pytest

_TESTS = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_TESTS)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")
SC = _load("session_contract")

_ROUND_DRIVER_PY = os.path.join(_LIB, "round_driver.py")


def _cfg(**over):
    base = {"fixerVendor": "claude", "reviewerVendor": "codex", "verifyCommand": None}
    base.update(over)
    return base


def _new_state(**cfg_over):
    state = RD.new_state(_cfg(**cfg_over))
    state["reviewedDiff"] = (
        "diff --git a/src/a.py b/src/a.py\n--- a/src/a.py\n+++ b/src/a.py\n@@ -1 +1 @@\n-x\n+y\n"
    )
    return state


def _is_state_findings_subscript(node):
    if not isinstance(node, ast.Subscript):
        return False
    if not isinstance(node.value, ast.Name) or node.value.id != "state":
        return False
    sl = node.slice
    if isinstance(sl, ast.Constant) and sl.value == "findings":
        return True
    if isinstance(sl, ast.Index) and isinstance(sl.value, ast.Str) and sl.value.s == "findings":
        return True
    return False


def _function_name_for_node(tree, lineno):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            if node.lineno <= lineno <= end:
                return node.name
    return None


def census_findings_assignment_violations():
    """Return (line, enclosing_function) for state['findings'] = outside _set_findings."""
    with open(_ROUND_DRIVER_PY, encoding="utf-8") as fh:
        source = fh.read()
    tree = ast.parse(source, filename=_ROUND_DRIVER_PY)
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not _is_state_findings_subscript(target):
                continue
            func = _function_name_for_node(tree, node.lineno)
            if func != "_set_findings":
                violations.append((node.lineno, func))
    return violations


def test_findings_assignment_chokepoint_census():
    violations = census_findings_assignment_violations()
    assert not violations, (
        "state['findings'] assigned outside _set_findings: %r" % violations
    )


def test_cleared_disposition_findings_remain_in_certification_view():
    fixed = {
        "id": "F-fixed",
        "title": "bounds guard",
        "severity": "Important",
        "file": "src/guard.py",
        "line": 12,
        "disposition": "fixed",
        "dispositionReceipt": {"headSha": "a" * 40, "verifyResult": "pass"},
    }
    open_issue = {
        "id": "F-open",
        "title": "open nit",
        "severity": "Minor",
        "file": "src/other.py",
        "line": 3,
    }
    state = _new_state()
    state["round"] = 2
    state["findings"] = [fixed, open_issue]
    state["_newIssues"] = []
    RD._fold_scoped(state, state["config"], {"findings": []})
    assert state.get("findings") == []
    assert any(
        isinstance(entry, dict) and entry.get("id") == "F-fixed"
        for entry in (state.get("dispositionLedger") or [])
    )
    ledger_rows, ledger_fault = SC.read_disposition_ledger(state)
    assert ledger_fault is None
    certified = ledger_rows + list(state.get("findings") or [])
    ids = {f.get("id") for f in certified if isinstance(f, dict)}
    assert "F-fixed" in ids
