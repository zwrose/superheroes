"""Tests for ``seat_map_receipts`` — the leaf projection module (#681)."""
import ast
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_MOD = os.path.join(_LIB, "seat_map_receipts.py")

_FORBIDDEN_UPWARD_IMPORTS = frozenset({
    "round_driver",
    "round_adapters",
    "round_orders",
    "round_records",
    "round_phases",
})


def test_seat_map_receipts_never_imports_upward_modules():
    """AST guard: leaf module must not import any upward layer (#681)."""
    with open(_MOD, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=_MOD)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in _FORBIDDEN_UPWARD_IMPORTS
        elif isinstance(node, ast.ImportFrom):
            if node.module in _FORBIDDEN_UPWARD_IMPORTS:
                raise AssertionError("forbidden import from %r" % node.module)
