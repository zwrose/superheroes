import hashlib
import importlib.util
import json
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_MOD = os.path.join(_HERE, "..", "review_gate_policy.py")
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SHIPPED = os.path.join(_PLUGIN_ROOT, "rubric", "review-gate-policy.json")


def _load():
    spec = importlib.util.spec_from_file_location("review_gate_policy", _MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RGP = _load()


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


def _judgment_rule(finding_class, disposition):
    return {
        "gate": RGP.GATE_PRESENT_JUDGMENT,
        "findingClass": finding_class,
        "disposition": disposition,
    }


def _stall_rule(finding_class, disposition):
    return {
        "gate": RGP.GATE_PRESENT_STALL_MENU,
        "findingClass": finding_class,
        "disposition": disposition,
    }


def test_judgment_finding_class_census_matches_source_vocabularies():
    expected = {
        "judgment:%s:%s" % (cls, sev)
        for cls in RGP.judgment_classifications()
        for sev in RGP.judgment_severities()
    }
    assert set(RGP.judgment_finding_classes()) == expected


def test_overlay_precedes_shipped():
    cls = sorted(RGP.judgment_finding_classes())[0]
    overlay = _overlay(
        {
            "schema": RGP.GATE_POLICY_SCHEMA,
            "default": "park",
            "rules": [_judgment_rule(cls, "skip")],
        }
    )
    shipped_cls = sorted(RGP.judgment_finding_classes())[-1]
    # Shipped empty rules would park; overlay skip must win for the overlaid class.
    result = RGP.resolve_judgment([{"findingClass": cls, "id": "a"}], overlay)
    assert result["action"] == {"dispositions": [{"findingClass": cls, "disposition": "skip"}]}
    assert result["matches"][0]["layer"]["source"] == "calibration/test.json"

    # A class with no overlay rule still parks even if we imagined shipped had rules.
    parked = RGP.resolve_judgment([{"findingClass": shipped_cls, "id": "b"}], overlay)
    assert parked["action"] == RGP.PARK


def test_judgment_all_or_nothing_when_partial_match():
    classes = sorted(RGP.judgment_finding_classes())
    overlay = _overlay(
        {
            "schema": RGP.GATE_POLICY_SCHEMA,
            "default": "park",
            "rules": [_judgment_rule(classes[0], "skip")],
        }
    )
    result = RGP.resolve_judgment(
        [
            {"findingClass": classes[0], "id": "a"},
            {"findingClass": classes[1], "id": "b"},
        ],
        overlay,
    )
    assert result["action"] == RGP.PARK
    assert result["reason"] == "gate-policy-unmatched-class:%s" % classes[1]


def test_layer_identities_include_sha256_for_overlay_and_shipped():
    cls = sorted(RGP.judgment_finding_classes())[0]
    overlay = _overlay(
        {
            "schema": RGP.GATE_POLICY_SCHEMA,
            "default": "park",
            "rules": [_judgment_rule(cls, "skip")],
        }
    )
    result = RGP.resolve_judgment([{"findingClass": cls, "id": "a"}], overlay)
    identities = [layer["identity"] for layer in result["layers"] if layer["ok"]]
    assert len(identities) == 2
    for ident in identities:
        assert ident["schema"] == RGP.GATE_POLICY_SCHEMA
        assert len(ident["sha256"]) == 64
        assert all(c in "0123456789abcdef" for c in ident["sha256"])


def test_shipped_empty_rules_park_every_judgment_class():
    for finding_class in sorted(RGP.judgment_finding_classes()):
        result = RGP.resolve_judgment([{"findingClass": finding_class, "id": "x"}])
        assert result["action"] == RGP.PARK
        assert result["reason"].startswith("gate-policy-unmatched-class:")


def test_shipped_empty_rules_park_every_stall_class():
    for stall_class in sorted(RGP.stall_finding_classes()):
        result = RGP.resolve_stall(stall_class)
        assert result["action"] == RGP.PARK
        assert result["reason"].startswith("gate-policy-unmatched-class:")


def test_fail_closed_shipped_file_missing(tmp_path, monkeypatch):
    missing = str(tmp_path / "missing.json")
    loaded = RGP.load_shipped_layer(missing)
    assert loaded["ok"] is False
    assert loaded["reason"] == "gate-policy-shipped-missing"
    monkeypatch.setattr(RGP, "gate_policy_path", lambda root=None: missing)
    result = RGP.resolve_judgment(
        [{"findingClass": sorted(RGP.judgment_finding_classes())[0], "id": "a"}],
    )
    assert result["action"] == RGP.PARK
    assert result["reason"] == "gate-policy-no-valid-layer"


def test_fail_closed_shipped_file_unparseable(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    loaded = RGP.load_shipped_layer(str(bad))
    assert loaded["ok"] is False
    assert loaded["reason"] == "gate-policy-shipped-unparseable"


def test_fail_closed_unknown_schema(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(
        json.dumps({"schema": "gate-policy/2", "rules": [], "default": "park"}),
        encoding="utf-8",
    )
    loaded = RGP.load_shipped_layer(str(path))
    assert loaded["ok"] is False
    assert loaded["reason"] == "layer-invalid-schema"


def test_fail_closed_overlay_one_invalid_rule_drops_whole_layer():
    cls = sorted(RGP.judgment_finding_classes())[0]
    overlay = _overlay(
        {
            "schema": RGP.GATE_POLICY_SCHEMA,
            "default": "park",
            "rules": [
                _judgment_rule(cls, "skip"),
                {"gate": RGP.GATE_PRESENT_JUDGMENT, "findingClass": cls, "disposition": "bogus"},
            ],
        }
    )
    result = RGP.resolve_judgment([{"findingClass": cls, "id": "a"}], overlay)
    assert result["action"] == RGP.PARK
    overlay_records = [layer for layer in result["layers"] if layer["identity"] and "calibration" in layer["identity"]["source"]]
    assert len(overlay_records) == 1
    assert overlay_records[0]["ok"] is False
    assert overlay_records[0]["reason"] == "layer-disposition-not-allowed"


def test_fail_closed_overlay_only_other_gate_rules():
    cls = sorted(RGP.judgment_finding_classes())[0]
    overlay = _overlay(
        {
            "schema": RGP.GATE_POLICY_SCHEMA,
            "default": "park",
            "rules": [_stall_rule(RGP.STALL_CLASS_ELIGIBLE, "hold")],
        }
    )
    result = RGP.resolve_judgment([{"findingClass": cls, "id": "a"}], overlay)
    assert result["action"] == RGP.PARK
    assert result["reason"] == "gate-policy-unmatched-class:%s" % cls


def test_fail_closed_stall_accept_risk_on_ineligible_class():
    overlay = _overlay(
        {
            "schema": RGP.GATE_POLICY_SCHEMA,
            "default": "park",
            "rules": [
                _stall_rule(RGP.STALL_CLASS_INELIGIBLE, RGP._ACCEPT_RISK),
            ],
        }
    )
    loaded = RGP._parse_overlay(overlay)
    assert loaded["ok"] is False
    assert loaded["reason"] == "layer-disposition-not-allowed"


def test_stall_eligible_can_accept_disclosed_risk():
    overlay = _overlay(
        {
            "schema": RGP.GATE_POLICY_SCHEMA,
            "default": "park",
            "rules": [_stall_rule(RGP.STALL_CLASS_ELIGIBLE, RGP._ACCEPT_RISK)],
        }
    )
    result = RGP.resolve_stall(RGP.STALL_CLASS_ELIGIBLE, overlay)
    assert result["action"] == {"choice": RGP._ACCEPT_RISK}


def test_stall_ineligible_matching_accept_risk_rule_drops_layer():
    """Edge 7: only matching rule offers accept-the-disclosed-risk on ineligible class."""
    overlay = _overlay(
        {
            "schema": RGP.GATE_POLICY_SCHEMA,
            "default": "park",
            "rules": [
                {
                    "gate": RGP.GATE_PRESENT_STALL_MENU,
                    "findingClass": RGP.STALL_CLASS_INELIGIBLE,
                    "disposition": "hold",
                },
                _stall_rule(RGP.STALL_CLASS_INELIGIBLE, RGP._ACCEPT_RISK),
            ],
        }
    )
    parsed = RGP._parse_overlay(overlay)
    assert parsed["ok"] is False
    assert parsed["reason"] == "layer-disposition-not-allowed"


def test_whole_layer_drop_one_invalid_rule_discards_entire_layer():
    cls = sorted(RGP.judgment_finding_classes())[0]
    overlay = _overlay(
        {
            "schema": RGP.GATE_POLICY_SCHEMA,
            "default": "park",
            "rules": [
                _judgment_rule(cls, "skip"),
                "not-an-object",
            ],
        }
    )
    parsed = RGP._parse_overlay(overlay)
    assert parsed["ok"] is False
    assert parsed["reason"] == "layer-rule-not-object"
    result = RGP.resolve_judgment([{"findingClass": cls, "id": "a"}], overlay)
    assert result["action"] == RGP.PARK
