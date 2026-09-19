import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PC = _load("payload_contracts")


def test_payload_contracts_non_empty_string_rejects_blank():
    fault_id = PC.payload_fault(
        PC.P_VERIFIERS,
        {"verdicts": [{"id": "   ", "verdict": "CONFIRMED", "reason": "x"}]},
        "hand-submit",
    )
    assert fault_id is not None
    assert "id" in fault_id
    fault_reason = PC.payload_fault(
        PC.P_VERIFIERS,
        {"verdicts": [{"id": "f-1", "verdict": "CONFIRMED", "reason": "  "}]},
        "hand-submit",
    )
    assert fault_reason is not None
    assert "reason" in fault_reason
    assert PC.payload_fault(
        PC.P_VERIFIERS,
        {"verdicts": [{"id": "f-1", "verdict": "CONFIRMED", "reason": "x"}]},
        "hand-submit",
    ) is None


def test_top_level_non_empty_string_refuses_blank_scalar():
    fault = PC.payload_fault(
        PC.P_PANEL,
        {"findings": [], "tier": "   "},
        "code-reviewer",
    )
    assert fault is not None
    assert "tier" in fault
