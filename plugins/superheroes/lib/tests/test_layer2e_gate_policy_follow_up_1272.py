"""#1272 layer 2e WO-B2: gate-policy rules may carry a validated followUp.

The `advance` owner-gate route that applied these rules is retired; the gate-policy library
(`review_gate_policy`) and its followUp validation stay until the calibration is retired."""
import hashlib
import importlib.util
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

_WELL_FORMED = {
    "item": "defer auth redesign",
    "revisitTrigger": "when #1300 lands",
    "classClosure": "tracked separately",
}


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RGP = _load("review_gate_policy")


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


def test_e3_follow_up_item_less_refused_at_load_and_write():
    # axis: e3 — item-less followUp refused for new gate-policy rules
    cls = sorted(RGP.judgment_finding_classes())[0]
    policy = {
        "schema": RGP.GATE_POLICY_SCHEMA,
        "default": "park",
        "rules": [{
            "gate": RGP.GATE_PRESENT_JUDGMENT,
            "findingClass": cls,
            "disposition": "skip",
            "followUp": {"revisitTrigger": "later", "classClosure": "none"},
        }],
    }
    loaded = RGP.parse_overlay(_overlay(policy))
    assert loaded["ok"] is False
    assert loaded["reason"] == "layer-follow-up-malformed"
    refusal = RGP.validate_policy_for_write(policy)
    assert refusal is not None and "rules[0].followUp" in refusal


def test_e3b_follow_up_present_empty_item_refused_at_load_and_write():
    # axis: e3b — present-but-empty item refused at load and write
    cls = sorted(RGP.judgment_finding_classes())[0]
    policy = {
        "schema": RGP.GATE_POLICY_SCHEMA,
        "default": "park",
        "rules": [{
            "gate": RGP.GATE_PRESENT_JUDGMENT,
            "findingClass": cls,
            "disposition": "skip",
            "followUp": {"item": "", "revisitTrigger": "later", "classClosure": "none"},
        }],
    }
    loaded = RGP.parse_overlay(_overlay(policy))
    assert loaded["reason"] == "layer-follow-up-malformed"
    assert loaded["ok"] is False
    refusal = RGP.validate_policy_for_write(policy)
    assert refusal is not None and "rules[0].followUp" in refusal


def test_e4_follow_up_on_judgment_fix_not_allowed():
    # axis: e4 — followUp on judgment fix rule refused
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
    loaded = RGP.parse_overlay(_overlay(policy))
    assert loaded["reason"] == "layer-follow-up-not-allowed"
    assert loaded["ok"] is False


def test_e5_follow_up_on_stall_hold_not_allowed():
    # axis: e5 — followUp on stall hold rule refused
    policy = {
        "schema": RGP.GATE_POLICY_SCHEMA,
        "default": "park",
        "rules": [{
            "gate": RGP.GATE_PRESENT_STALL_MENU,
            "findingClass": RGP.STALL_CLASS_ELIGIBLE,
            "disposition": "hold",
            "followUp": dict(_WELL_FORMED),
        }],
    }
    loaded = RGP.parse_overlay(_overlay(policy))
    assert loaded["ok"] is False
    assert loaded["reason"] == "layer-follow-up-not-allowed"


def test_e4b_follow_up_on_not_allowed_disposition_refused_at_write():
    # axis: e4b — followUp on not-allowed disposition refused at write with rule-scoped message
    cls = sorted(RGP.judgment_finding_classes())[0]
    policy_bad = {
        "schema": RGP.GATE_POLICY_SCHEMA,
        "default": "park",
        "rules": [{
            "gate": RGP.GATE_PRESENT_JUDGMENT,
            "findingClass": cls,
            "disposition": "fix-as-suggested",
            "followUp": dict(_WELL_FORMED),
        }],
    }
    refusal = RGP.validate_policy_for_write(policy_bad)
    assert refusal is not None and "rules[0].followUp" in refusal
    assert "fix-as-suggested" in refusal
    policy_ok = {
        "schema": RGP.GATE_POLICY_SCHEMA,
        "default": "park",
        "rules": [{
            "gate": RGP.GATE_PRESENT_JUDGMENT,
            "findingClass": cls,
            "disposition": "skip",
            "followUp": dict(_WELL_FORMED),
        }],
    }
    assert RGP.validate_policy_for_write(policy_ok) is None


def test_e6_null_follow_up_malformed():
    # axis: e6 — followUp null refused as malformed
    cls = sorted(RGP.judgment_finding_classes())[0]
    policy = {
        "schema": RGP.GATE_POLICY_SCHEMA,
        "default": "park",
        "rules": [{
            "gate": RGP.GATE_PRESENT_JUDGMENT,
            "findingClass": cls,
            "disposition": "skip",
            "followUp": None,
        }],
    }
    loaded = RGP.parse_overlay(_overlay(policy))
    assert loaded["ok"] is False
    assert loaded["reason"] == "layer-follow-up-malformed"


def test_e7_rule_without_follow_up_normalizes_unchanged():
    # axis: e7 — rule without followUp normalizes exactly as before
    cls = sorted(RGP.judgment_finding_classes())[0]
    policy = {
        "schema": RGP.GATE_POLICY_SCHEMA,
        "default": "park",
        "rules": [{
            "gate": RGP.GATE_PRESENT_JUDGMENT,
            "findingClass": cls,
            "disposition": "skip",
        }],
    }
    loaded = RGP.parse_overlay(_overlay(policy))
    assert loaded["ok"] is True
    rule = loaded["layer"]["rules"][0]
    assert rule == {
        "gate": RGP.GATE_PRESENT_JUDGMENT,
        "findingClass": cls,
        "disposition": "skip",
    }
    assert "followUp" not in rule


def test_e9_layer_identity_sha256_covers_follow_up():
    # axis: e9 — changed followUp changes layer identity sha256
    cls = sorted(RGP.judgment_finding_classes())[0]
    base_rule = {
        "gate": RGP.GATE_PRESENT_JUDGMENT,
        "findingClass": cls,
        "disposition": "skip",
        "followUp": dict(_WELL_FORMED),
    }
    policy_a = {"schema": RGP.GATE_POLICY_SCHEMA, "default": "park", "rules": [base_rule]}
    policy_b = {
        "schema": RGP.GATE_POLICY_SCHEMA,
        "default": "park",
        "rules": [dict(base_rule, followUp=dict(_WELL_FORMED, item="other item"))],
    }
    a = RGP.parse_overlay(_overlay(policy_a))
    b = RGP.parse_overlay(_overlay(policy_b))
    assert a["ok"] and b["ok"]
    assert a["layer"]["identity"]["sha256"] != b["layer"]["identity"]["sha256"]
    forged = {"identity": dict(a["layer"]["identity"]), "policy": policy_b}
    out = RGP.parse_overlay(forged)
    assert out["ok"] is False, out
    assert out["reason"] == "overlay-digest-mismatch"
