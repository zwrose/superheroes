"""Drift guard: the gate-policy resolver's park-cause census (code ↔ code).

Authoritative home: review_gate_policy.RESOLVER_PARK_CAUSES, against the literal ``_park`` reasons
in review_gate_policy.py. The round driver reads no gate policy any more, so it carries no census.
"""
import ast
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
_RGP = os.path.join(_LIB, "review_gate_policy.py")


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
