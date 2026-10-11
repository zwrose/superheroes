"""The write-run phase rule has one definition."""
import importlib.util
import inspect
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)


def test_l3_b1_phase_rule_single_definition():
    spec = importlib.util.spec_from_file_location(
        "session_contract_census", os.path.join(_LIB, "session_contract.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    source = inspect.getsource(mod)
    assert source.count("def execution_only_admissible_for_phase") == 1
