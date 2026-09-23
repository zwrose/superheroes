"""#1386 WO-B: gate-policy write refusal and resolve_judgment followUp shape."""
import hashlib
import importlib.util
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RGP = _load("review_gate_policy")

_WELL_FORMED = {
    "item": "defer auth redesign",
    "revisitTrigger": "when #1300 lands",
    "classClosure": "tracked separately",
}


def _overlay(policy, *, source="calibration/test.json"):
    raw = json.dumps(policy, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "identity": {
            "source": source,
            "schema": RGP.GATE_POLICY_SCHEMA,
            "sha256": hashlib.sha256(raw).hexdigest(),
        },
        "policy": policy,
    }


def test_d2_follow_up_on_judgment_fix_not_allowed_for_write():
    # axis: D-2 — followUp on judgment fix rule refused at calibration write
    cls = sorted(RGP.judgment_finding_classes())[0]
    policy = {
        "schema": RGP.GATE_POLICY_SCHEMA,
        "default": "park",
        "rules": [{
            "gate": RGP.GATE_PRESENT_JUDGMENT,
            "findingClass": cls,
            "disposition": "fix-as-suggested",
            "followUp": dict(_WELL_FORMED),
        }],
    }
    refusal = RGP.validate_policy_for_write(policy)
    assert refusal is not None
    assert "rules[0].followUp" in refusal
    assert "not allowed for disposition" in refusal


def test_d1_resolve_judgment_follow_up_on_matches_not_dispositions():
    # axis: D-1 — followUp stays on matches[].rule, not action.dispositions[]
    cls = sorted(RGP.judgment_finding_classes())[0]
    rule_follow_up = dict(_WELL_FORMED)
    overlay = _overlay({
        "schema": RGP.GATE_POLICY_SCHEMA,
        "default": "park",
        "rules": [{
            "gate": RGP.GATE_PRESENT_JUDGMENT,
            "findingClass": cls,
            "disposition": "skip",
            "followUp": rule_follow_up,
        }],
    })
    result = RGP.resolve_judgment([{"findingClass": cls, "id": "a"}], overlay)
    for disp in result["action"]["dispositions"]:
        assert "followUp" not in disp
    assert result["matches"][0]["rule"]["followUp"] == rule_follow_up
