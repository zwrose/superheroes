"""Drift guard: advance gate-policy park detail vocabulary ↔ round_driver.py.

Copy-holder:
  - plugins/superheroes/skills/review-code/reference/round-driver.md
Authoritative home (derived at runtime — never retyped as literals in this test):
  - round_driver.owner_gate_policy_park_detail_causes
  - round_driver.GATE_POLICY_UNMATCHED_CLASS_PREFIX
"""
import ast
import os
import re

import round_driver as RD

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
_REF = os.path.join(_PLUGIN_ROOT, "skills", "review-code", "reference", "round-driver.md")
_RGP = os.path.join(_LIB, "review_gate_policy.py")
_RD = os.path.join(_LIB, "round_driver.py")

_EXACT_MARKER = "**Advance gate-policy park detail causes**"
_PARAMETERIZED_MARKER = "Parameterized (suffix after `:` is diagnostic detail):"


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _parse_fenced_text_block(text, after_marker):
    """Return stripped non-empty lines from the first ```text block after *after_marker*."""
    idx = text.index(after_marker)
    chunk = text[idx:]
    match = re.search(r"```text\n(.*?)```", chunk, re.DOTALL)
    if not match:
        raise RuntimeError("no ```text block found after marker %r" % after_marker)
    return [line.strip() for line in match.group(1).splitlines() if line.strip()]


def test_round_driver_gate_policy_park_causes_match_docs():
    """round-driver.md park-detail list ↔ owner_gate_policy_park_detail_causes (both directions)."""
    text = _read(_REF)
    documented = set(_parse_fenced_text_block(text, _EXACT_MARKER))
    coded = set(RD.owner_gate_policy_park_detail_causes())

    only_docs = documented - coded
    only_code = coded - documented
    assert not only_docs, (
        "round-driver.md lists park causes the driver cannot emit: %s" % sorted(only_docs))
    assert not only_code, (
        "driver emits park causes missing from round-driver.md: %s" % sorted(only_code))

    parameterized = _parse_fenced_text_block(text, _PARAMETERIZED_MARKER)
    assert parameterized == [RD.GATE_POLICY_UNMATCHED_CLASS_PREFIX + "<findingClass>"], (
        "parameterized park cause pattern drifted from round_driver.GATE_POLICY_UNMATCHED_CLASS_PREFIX")


def _module_string_constants(tree):
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant):
                if isinstance(node.value.value, str):
                    constants[target.id] = node.value.value
    return constants


def _driver_resolver_park_detail_literals(tree):
    """Literal parkDetail tokens returned from ``_resolve_owner_gate_policy``."""
    module_constants = _module_string_constants(tree)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_resolve_owner_gate_policy")
    found = set()

    def _add_park_detail_value(value_node):
        if isinstance(value_node, ast.Constant) and isinstance(value_node.value, str):
            found.add(value_node.value)
        elif isinstance(value_node, ast.Name):
            if value_node.id in module_constants:
                found.add(module_constants[value_node.id])
            else:
                found.add(value_node.id)
        elif isinstance(value_node, ast.BoolOp) and isinstance(value_node.op, ast.Or):
            for operand in value_node.values:
                _add_park_detail_value(operand)

    def _park_detail_from_dict(dict_node):
        if not isinstance(dict_node, ast.Dict):
            return
        for key_node, value_node in zip(dict_node.keys, dict_node.values):
            if not (isinstance(key_node, ast.Constant) and key_node.value == "parkDetail"):
                continue
            _add_park_detail_value(value_node)

    for node in ast.walk(fn):
        if isinstance(node, ast.Return):
            _park_detail_from_dict(node.value)
    return found


def test_driver_resolver_park_causes_bound_to_review_gate_policy():
    """Driver GATE_POLICY_RESOLVER_PARK_CAUSES must include every resolver _park token."""
    import review_gate_policy as RGP

    with open(_RD, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=_RD)
    resolver_only = set(RGP.RESOLVER_PARK_CAUSES)
    assert resolver_only <= set(RD.GATE_POLICY_RESOLVER_PARK_CAUSES), (
        "review_gate_policy.RESOLVER_PARK_CAUSES drifted from round_driver: missing %s"
        % sorted(resolver_only - set(RD.GATE_POLICY_RESOLVER_PARK_CAUSES))
    )
    driver_literals = _driver_resolver_park_detail_literals(tree)
    driver_only = set(RD.GATE_POLICY_RESOLVER_PARK_CAUSES) - resolver_only
    assert driver_literals == driver_only, (
        "_resolve_owner_gate_policy parkDetail literals drifted from driver-only causes: "
        "only-in-function=%s only-in-constant=%s"
        % (sorted(driver_literals - driver_only), sorted(driver_only - driver_literals))
    )


def test_driver_resolver_park_call_sites_match_resolver_park_causes():
    """Every driver-only park cause in _resolve_owner_gate_policy must be in the constant."""
    with open(_RD, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=_RD)
    found = _driver_resolver_park_detail_literals(tree)
    driver_only = set(RD.GATE_POLICY_RESOLVER_PARK_CAUSES) - set(
        __import__("review_gate_policy").RESOLVER_PARK_CAUSES
    )
    assert found <= set(RD.GATE_POLICY_RESOLVER_PARK_CAUSES), (
        "driver parkDetail literals missing from GATE_POLICY_RESOLVER_PARK_CAUSES: %s"
        % sorted(found - set(RD.GATE_POLICY_RESOLVER_PARK_CAUSES))
    )
    assert driver_only <= found, (
        "GATE_POLICY_RESOLVER_PARK_CAUSES carries driver-only tokens with no call site: %s"
        % sorted(driver_only - found)
    )


def test_driver_resolver_park_census_red_on_unbound_driver_cause():
    """Bite-axis: a park cause added in the driver but absent from the constant must fail."""
    with open(_RD, encoding="utf-8") as fh:
        source = fh.read()
    marker = '        return {"authorized": False, "parkDetail": GATE_POLICY_UNKNOWN_PHASE_PARK_CAUSE}\n'
    probe = '        return {"authorized": False, "parkDetail": "gate-policy-probe-unbound"}\n'
    probed = source.replace(marker, marker + probe, 1)
    tree = ast.parse(probed, filename=_RD)
    found = _driver_resolver_park_detail_literals(tree)
    assert "gate-policy-probe-unbound" in found
    assert "gate-policy-probe-unbound" not in RD.GATE_POLICY_RESOLVER_PARK_CAUSES


def test_resolver_park_call_sites_match_resolver_park_causes():
    """Every literal ``_park`` reason in review_gate_policy must be in RESOLVER_PARK_CAUSES."""
    import review_gate_policy as RGP

    with open(_RGP, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=_RGP)
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Name) and func.id == "_park"):
            continue
        if not node.args:
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            found.add(arg.value)
    assert found == set(RGP.RESOLVER_PARK_CAUSES), (
        "review_gate_policy _park call sites drifted from RESOLVER_PARK_CAUSES: "
        "only-in-calls=%s only-in-constant=%s"
        % (sorted(found - set(RGP.RESOLVER_PARK_CAUSES)),
           sorted(set(RGP.RESOLVER_PARK_CAUSES) - found))
    )
