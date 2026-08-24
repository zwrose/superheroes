"""#1107 WO-STALL: structural pins for _handle_stall decomposition — one owner per concern."""
import ast
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_RD_PATH = os.path.join(_LIB, "round_driver.py")

_RD_SOURCE = None
_RD_TREE = None


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")


def _round_driver_source():
    global _RD_SOURCE, _RD_TREE
    if _RD_SOURCE is None:
        with open(_RD_PATH, encoding="utf-8") as fh:
            _RD_SOURCE = fh.read()
        _RD_TREE = ast.parse(_RD_SOURCE, filename=_RD_PATH)
    return _RD_SOURCE


def _round_driver_tree():
    _round_driver_source()
    return _RD_TREE


def _top_level_functions(tree):
    return [n for n in tree.body if isinstance(n, ast.FunctionDef)]


def _top_level_function(tree, name):
    for node in _top_level_functions(tree):
        if node.name == name:
            return node
    return None


def _state_subscript_key(subscript):
    """Return the string key for ``state[<key>]`` or None."""
    if not isinstance(subscript, ast.Subscript):
        return None
    if not isinstance(subscript.value, ast.Name) or subscript.value.id != "state":
        return None
    sl = subscript.slice
    if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
        return sl.value
    if isinstance(sl, ast.Index) and isinstance(sl.value, ast.Constant):
        val = sl.value.value
        return val if isinstance(val, str) else None
    return None


def _subtree_has_bare_name_call(node, name):
    """True if ``node``'s subtree contains ``name(...)``."""
    for child in ast.walk(node):
        if (isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
                and child.func.id == name):
            return True
    return False


def _subtree_has_name_load(node, name):
    """True if ``node``'s subtree contains a load of ``name``."""
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and child.id == name and isinstance(child.ctx, ast.Load):
            return True
    return False


def _subtree_has_state_key_assignment(node, key, value=None):
    """True if ``node``'s subtree assigns to ``state[key]``, optionally with ``value``."""
    for child in ast.walk(node):
        if not isinstance(child, ast.Assign):
            continue
        for target in child.targets:
            if _state_subscript_key(target) != key:
                continue
            if value is None:
                return True
            val = child.value
            if isinstance(val, ast.Constant) and val.value == value:
                return True
    return False


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


def _functions_with_state_key_assignment(tree, key, value=None):
    """Return top-level function names assigning to ``state[key]``."""
    hits = []
    for node in _top_level_functions(tree):
        if _subtree_has_state_key_assignment(node, key, value):
            hits.append(node.name)
    return hits


def _recovery_branch_node(tree):
    """``If`` node for ``if not state.get("selfRecovered"):`` inside _handle_stall."""
    handle = _top_level_function(tree, "_handle_stall")
    if handle is None:
        return None
    for child in handle.body:
        if not isinstance(child, ast.If):
            continue
        test = child.test
        if (isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not)
                and isinstance(test.operand, ast.Call)):
            return child
    return None


def test_guard_owner_is_not_handle_stall():
    # axis: selfRecovered assignment has exactly one owner outside _handle_stall
    tree = _round_driver_tree()
    owners = _functions_with_state_key_assignment(tree, "selfRecovered", True)
    assert owners == ["_commit_stall_self_recovery"], (
        "expected single guard owner _commit_stall_self_recovery, found: %s" % owners)
    assert "_handle_stall" not in owners


def test_escalation_owner_matches_guard_owner():
    # axis: model_registry.escalate has exactly one owner, same as the guard owner
    tree = _round_driver_tree()
    escalate_fns = _functions_with_call(_round_driver_source(), tree, "model_registry", "escalate")
    guard_fns = _functions_with_state_key_assignment(tree, "selfRecovered", True)
    assert escalate_fns == ["_commit_stall_self_recovery"]
    assert escalate_fns == guard_fns
    assert "_handle_stall" not in escalate_fns


def test_handle_stall_has_no_terminal_routing():
    # axis: _handle_stall does not park, converge, or assign _fixBatch directly
    tree = _round_driver_tree()
    handle = _top_level_function(tree, "_handle_stall")
    assert handle is not None
    assert not _subtree_has_bare_name_call(handle, "_park_cannot_certify")
    assert not _subtree_has_bare_name_call(handle, "_park_capped_open")
    assert not _subtree_has_bare_name_call(handle, "_settle_delta_converged")
    assert not _subtree_has_state_key_assignment(handle, "_fixBatch")


def test_composition_owner_calls_stalled_open_targets():
    # axis: fix-batch composition is owned outside _handle_stall recovery branch
    tree = _round_driver_tree()
    compose = _top_level_function(tree, "_compose_stall_fix_batch")
    assert compose is not None
    assert _subtree_has_bare_name_call(compose, "_stalled_open_targets")
    recovery = _recovery_branch_node(tree)
    assert recovery is not None
    assert not _subtree_has_bare_name_call(recovery, "_stalled_open_targets")


def test_routing_owner_is_total():
    # axis: routing owner names all four terminal routes (fixer, both parks, converge)
    tree = _round_driver_tree()
    route = _top_level_function(tree, "_route_stall_self_recovery")
    assert route is not None
    assert _subtree_has_name_load(route, "P_FIXER")
    assert _subtree_has_bare_name_call(route, "_park_cannot_certify")
    assert _subtree_has_bare_name_call(route, "_park_capped_open")
    assert _subtree_has_bare_name_call(route, "_settle_delta_converged")


def test_empty_resolution_converge_never_claims_an_unrun_panel():
    # axis: behavioural — empty-resolution stall self-recovery converges via _terminal_converged
    # and carries fullPanel from state, never hard-codes a panel claim
    cfg = {"leg": "code", "vendors": ["claude", "codex"], "diff": "d", "fixerVendor": "claude"}
    breaker = {"reason": "audit-stall", "detail": "x", "stalledIdentities": ["v0"]}

    state_false = RD.new_state(cfg)
    state_false["fullPanelRan"] = False
    RD._handle_stall(state_false, state_false["config"], breaker)
    assert state_false["step"] == RD.P_TERMINAL
    assert state_false["terminal"] == "converged"
    assert state_false["certification"]["fullPanel"] is False

    state_true = RD.new_state(cfg)
    state_true["fullPanelRan"] = True
    RD._handle_stall(state_true, state_true["config"], breaker)
    assert state_true["certification"]["fullPanel"] is True
