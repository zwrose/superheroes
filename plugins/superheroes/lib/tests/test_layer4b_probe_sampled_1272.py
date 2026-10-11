"""#1272 layer 4b: record-only disclosure channels are never read into degraded prose."""
import ast
import inspect
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import receipt_disclosures as RD_DISCLOSURES

from test_round_driver import _load

RD = _load("round_driver")


def _literal_get_keys_in_build_degraded_prose():
    source = inspect.getsource(RD_DISCLOSURES.build_degraded_prose)
    tree = ast.parse(source)
    fn_node = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "build_degraded_prose")
    keys = []
    for node in ast.walk(fn_node):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "get":
            continue
        if len(node.args) != 1 or not isinstance(node.args[0], ast.Constant):
            continue
        if isinstance(node.args[0].value, str):
            keys.append(node.args[0].value)
    return keys


def test_record_only_channels_never_read_in_build_degraded_prose():
    """Record-only disclosure channels must not be read into degraded prose."""
    record_only = set(RD.RECORD_ONLY_DISCLOSURE_CHANNELS)
    literal_gets = _literal_get_keys_in_build_degraded_prose()
    assert len(literal_gets) >= 5, (
        "build_degraded_prose census must find literal .get() reads (e.g. vacuousSeats)")
    assert "vacuousSeats" in literal_gets
    offenders = [k for k in literal_gets if k in record_only]
    assert not offenders, (
        "record-only channels must not be read in build_degraded_prose: %s" % offenders)
