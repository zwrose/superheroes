"""#1107 WO-STALL: structural pins for _handle_stall decomposition — one owner per concern."""
import ast
import importlib.util
import inspect
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_RD_PATH = os.path.join(_LIB, "round_driver.py")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")


def _round_driver_source():
    with open(_RD_PATH, encoding="utf-8") as fh:
        return fh.read()


def _top_level_functions(tree):
    return [n for n in tree.body if isinstance(n, ast.FunctionDef)]


def _functions_with_literal(source, tree, needle):
    hits = []
    for node in _top_level_functions(tree):
        fn_src = ast.get_source_segment(source, node) or ""
        if needle in fn_src:
            hits.append(node.name)
    return hits


def _functions_with_call(source, tree, module_name, attr_name):
    """Return top-level function names containing ``module_name.attr_name(...)``."""
    hits = []
    for node in _top_level_functions(tree):
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            func = child.func
            if (isinstance(func, ast.Attribute) and func.attr == attr_name
                    and isinstance(func.value, ast.Name) and func.value.id == module_name):
                hits.append(node.name)
                break
    return hits


def _recovery_branch_source(source, tree):
    """Source of the ``if not state.get("selfRecovered"):`` block inside _handle_stall."""
    for node in _top_level_functions(tree):
        if node.name != "_handle_stall":
            continue
        for child in node.body:
            if not isinstance(child, ast.If):
                continue
            test = child.test
            if (isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not)
                    and isinstance(test.operand, ast.Call)):
                return ast.get_source_segment(source, child) or ""
    return ""


def test_guard_owner_is_not_handle_stall():
    # axis: selfRecovered assignment has exactly one owner outside _handle_stall
    source = _round_driver_source()
    tree = ast.parse(source, filename=_RD_PATH)
    owners = _functions_with_literal(source, tree, 'state["selfRecovered"] = True')
    assert owners == ["_commit_stall_self_recovery"], (
        "expected single guard owner _commit_stall_self_recovery, found: %s" % owners)
    assert "_handle_stall" not in owners


def test_escalation_owner_matches_guard_owner():
    # axis: model_registry.escalate has exactly one owner, same as the guard owner
    source = _round_driver_source()
    tree = ast.parse(source, filename=_RD_PATH)
    escalate_fns = _functions_with_call(source, tree, "model_registry", "escalate")
    guard_fns = _functions_with_literal(source, tree, 'state["selfRecovered"] = True')
    assert escalate_fns == ["_commit_stall_self_recovery"]
    assert escalate_fns == guard_fns
    assert "_handle_stall" not in escalate_fns


def test_handle_stall_has_no_terminal_routing():
    # axis: _handle_stall does not park, converge, or assign _fixBatch directly
    src = inspect.getsource(RD._handle_stall)
    assert "_park_cannot_certify" not in src
    assert "_park_capped_open" not in src
    assert "_settle_delta_converged" not in src
    assert 'state["_fixBatch"]' not in src


def test_composition_owner_calls_stalled_open_targets():
    # axis: fix-batch composition is owned outside _handle_stall recovery branch
    compose_src = inspect.getsource(RD._compose_stall_fix_batch)
    assert "_stalled_open_targets" in compose_src
    source = _round_driver_source()
    tree = ast.parse(source, filename=_RD_PATH)
    recovery_src = _recovery_branch_source(source, tree)
    assert "_stalled_open_targets" not in recovery_src


def test_routing_owner_is_total():
    # axis: routing owner names all four terminal routes (fixer, both parks, converge)
    route_src = inspect.getsource(RD._route_stall_self_recovery)
    assert "P_FIXER" in route_src
    assert "_park_cannot_certify" in route_src
    assert "_park_capped_open" in route_src
    assert "_settle_delta_converged" in route_src
