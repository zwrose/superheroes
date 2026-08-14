import ast
import hashlib
import importlib.util
import json
import os
import sys

import panel_tally
import pytest
import round_phases

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


def test_review_gate_policy_never_imports_round_driver():
    """AST guard: no import of round_driver anywhere in the module tree (including lazy imports)."""
    with open(_MOD, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=_MOD)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "round_driver"
        elif isinstance(node, ast.ImportFrom):
            assert node.module != "round_driver"


def test_judgment_finding_class_census_matches_source_vocabularies():
    expected = {"judgment:%s" % sev.lower() for sev in panel_tally.SEV_RANK}
    assert set(RGP.judgment_finding_classes()) == expected


def test_fail_closed_unknown_judgment_class_id():
    """Well-formed class id outside the closed enum must park."""
    result = RGP.resolve_judgment([{"findingClass": "judgment:unknown-severity", "id": "a"}])
    assert result["action"] == RGP.PARK
    assert result["reason"] == "gate-policy-unmatched-class:judgment:unknown-severity"


def test_fail_closed_severity_without_rule_parks():
    """Every SEV_RANK severity with shipped empty rules parks when no layer matches."""
    for sev in panel_tally.SEV_RANK:
        finding_class = "judgment:%s" % sev.lower()
        result = RGP.resolve_judgment([{"findingClass": finding_class, "id": "x"}])
        assert result["action"] == RGP.PARK
        assert result["reason"] == "gate-policy-unmatched-class:%s" % finding_class


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
                _stall_rule(RGP.STALL_CLASS_INELIGIBLE, round_phases.ACCEPT_RISK_CHOICE),
            ],
        }
    )
    loaded = RGP.parse_overlay(overlay)
    assert loaded["ok"] is False
    assert loaded["reason"] == "layer-disposition-not-allowed"
    assert round_phases.ACCEPT_RISK_CHOICE in round_phases.STALL_CHOICES


def test_stall_eligible_can_accept_disclosed_risk():
    overlay = _overlay(
        {
            "schema": RGP.GATE_POLICY_SCHEMA,
            "default": "park",
            "rules": [_stall_rule(RGP.STALL_CLASS_ELIGIBLE, round_phases.ACCEPT_RISK_CHOICE)],
        }
    )
    result = RGP.resolve_stall(RGP.STALL_CLASS_ELIGIBLE, overlay)
    assert result["action"] == {"choice": round_phases.ACCEPT_RISK_CHOICE}


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
                _stall_rule(RGP.STALL_CLASS_INELIGIBLE, round_phases.ACCEPT_RISK_CHOICE),
            ],
        }
    )
    parsed = RGP.parse_overlay(overlay)
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
    parsed = RGP.parse_overlay(overlay)
    assert parsed["ok"] is False
    assert parsed["reason"] == "layer-rule-not-object"
    result = RGP.resolve_judgment([{"findingClass": cls, "id": "a"}], overlay)
    assert result["action"] == RGP.PARK


def test_fail_closed_overlay_digest_mismatch():
    cls = sorted(RGP.judgment_finding_classes())[0]
    policy = {
        "schema": RGP.GATE_POLICY_SCHEMA,
        "default": "park",
        "rules": [_judgment_rule(cls, "skip")],
    }
    overlay = {
        "identity": {
            "source": "calibration/test.json",
            "schema": RGP.GATE_POLICY_SCHEMA,
            "sha256": "deadbeef" + "0" * 56,
        },
        "policy": policy,
    }
    parsed = RGP.parse_overlay(overlay)
    assert parsed["ok"] is False
    assert parsed["reason"] == "overlay-digest-mismatch"


def test_fail_closed_policy_rule_fix_with_guidance_refused():
    cls = sorted(RGP.judgment_finding_classes())[0]
    overlay = _overlay(
        {
            "schema": RGP.GATE_POLICY_SCHEMA,
            "default": "park",
            "rules": [_judgment_rule(cls, "fix-with-guidance")],
        }
    )
    parsed = RGP.parse_overlay(overlay)
    assert parsed["ok"] is False
    assert parsed["reason"] == "layer-disposition-not-allowed"


def test_policy_judgment_dispositions_derived_from_home():
    """Policy-eligible judgment dispositions are home minus owner-input-only members."""
    home = set(round_phases.JUDGMENT_DISPOSITIONS)
    policy = set(RGP.POLICY_JUDGMENT_DISPOSITIONS)
    assert policy <= home
    assert home - policy == {"fix-with-guidance"}
    assert RGP.JUDGMENT_SKIP_DISPOSITION == "skip"
    assert RGP.JUDGMENT_SKIP_DISPOSITION in policy


def test_policy_judgment_dispositions_red_on_home_member_rename():
    """Bite-axis: renaming a home disposition must fail the derived-policy binding."""
    home_path = os.path.join(_HERE, "..", "round_phases.py")
    with open(home_path, encoding="utf-8") as fh:
        source = fh.read()
    probed = source.replace('"skip"', '"skip-renamed-for-census"', 1)
    spec = importlib.util.spec_from_file_location("round_phases_probe", home_path)
    probe_phases = importlib.util.module_from_spec(spec)
    exec(compile(probed, home_path, "exec"), probe_phases.__dict__)  # noqa: S102

    policy_path = _MOD
    with open(policy_path, encoding="utf-8") as fh:
        policy_source = fh.read()

    saved_round_phases = sys.modules.get("round_phases")
    saved_review_gate_policy = sys.modules.get("review_gate_policy")
    probe_policy = importlib.util.module_from_spec(
        importlib.util.spec_from_file_location("review_gate_policy_probe", policy_path)
    )
    try:
        sys.modules["round_phases"] = probe_phases
        if "review_gate_policy" in sys.modules:
            del sys.modules["review_gate_policy"]
        exec(compile(policy_source, policy_path, "exec"), probe_policy.__dict__)  # noqa: S102
        derived = probe_policy.POLICY_JUDGMENT_DISPOSITIONS
        assert "skip" not in derived
        assert "skip-renamed-for-census" in derived
    finally:
        if saved_round_phases is not None:
            sys.modules["round_phases"] = saved_round_phases
        elif "round_phases" in sys.modules:
            del sys.modules["round_phases"]
        if saved_review_gate_policy is not None:
            sys.modules["review_gate_policy"] = saved_review_gate_policy
        elif "review_gate_policy" in sys.modules:
            del sys.modules["review_gate_policy"]
