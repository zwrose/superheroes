import importlib.util
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

_MOD = os.path.join(_LIB, "seat_map.py")


def _load():
    spec = importlib.util.spec_from_file_location("seat_map", _MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SM = _load()

THREE_VENDORS = ["claude", "codex", "cursor"]


def test_seed_from_pr_precedence_over_sha():
    pr_seed = SM.seed_from(510, "abc123")
    sha_only = SM.seed_from(None, "abc123")
    assert pr_seed != sha_only
    assert SM.seed_from(510, "abc123") == SM.seed_from(510, "different-sha")
    assert SM.seed_from(None, None) == 0


def test_seed_from_stable():
    s1 = SM.seed_from(42, None)
    s2 = SM.seed_from(42, None)
    assert s1 == s2
    assert isinstance(s1, int)


def test_determinism_same_seed():
    seed = SM.seed_from(510, None)
    m1 = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "cursor", "anthropic", seed)
    m2 = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "cursor", "anthropic", seed)
    assert m1["seats"] == m2["seats"]


def test_rotation_different_seeds():
    maps = []
    for seed in (0, 1, 2, 3, 4, 5):
        m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "cursor", "anthropic", seed)
        maps.append(tuple(m["seats"][s]["vendor"] for s in SM.PANEL_ROSTER))
    assert len(set(maps)) > 1


def test_three_vendor_happy_path():
    seed = SM.seed_from(510, None)
    m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "cursor", "anthropic", seed)
    grounding = m["seats"][SM.GROUNDING_SEAT]
    assert grounding["family"] not in {"cursor", "anthropic"}
    critical_families = {
        m["seats"][s]["family"] for s in SM.CRITICAL_SEATS if s in m["seats"]
    }
    assert len(critical_families) >= 2
    assert SM.verify(m, "cursor") == []


def test_claude_implemented_build():
    seed = SM.seed_from(99, None)
    m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "anthropic", "anthropic", seed)
    for seat in SM.STRONG_TIER_SEATS:
        assert m["seats"][seat]["family"] != "anthropic"
    assert m["seats"][SM.GROUNDING_SEAT]["family"] != "anthropic"
    assert SM.verify(m, "anthropic") == []


def test_single_vendor_floor():
    m = SM.build(SM.PANEL_ROSTER, ["claude"], "cursor", "anthropic", 0)
    assert len(m["seats"]) == len(SM.PANEL_ROSTER)
    constraints = {d["constraint"] for d in m["degradations"]}
    assert "critical-diversity" in constraints


def test_pin_honored():
    seed = 0
    pins = {
        "code-reviewer": {
            "vendor": "claude",
        },
    }
    m = SM.build(
        SM.PANEL_ROSTER, THREE_VENDORS, "cursor", "anthropic", seed, pins=pins
    )
    assert m["seats"]["code-reviewer"]["source"] == "pinned"
    assert m["seats"]["code-reviewer"]["vendor"] == "claude"


def test_pin_unhonorable_model():
    pins = {
        "code-reviewer": {
            "vendor": "cursor",
            "model": "gpt-5.6-terra",
            "effort": "high",
        },
    }
    m = SM.build(
        SM.PANEL_ROSTER, THREE_VENDORS, "cursor", "anthropic", 0, pins=pins
    )
    pin_degs = [d for d in m["degradations"] if d["constraint"] == "pin"]
    assert any("not honorable" in d["reason"] for d in pin_degs)
    assert m["seats"]["code-reviewer"]["source"] != "pinned"


def test_pin_unknown_seat():
    pins = {"nonexistent-seat": {"vendor": "claude"}}
    m = SM.build(
        SM.PANEL_ROSTER, THREE_VENDORS, "cursor", "anthropic", 0, pins=pins
    )
    pin_degs = [d for d in m["degradations"] if d["constraint"] == "pin"]
    assert any("unknown seat" in d["reason"] for d in pin_degs)


def test_fail_closed_empty_live_vendors():
    m = SM.build(SM.PANEL_ROSTER, [], "cursor", "anthropic", 0)
    assert m["liveVendors"] == ["claude"]
    assert any(d["constraint"] == "live-vendors" for d in m["degradations"])


def test_fail_closed_grounding_provenance():
    m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, None, "anthropic", 0)
    assert any(d["constraint"] == "grounding-provenance" for d in m["degradations"])


def test_fail_closed_missing_tier():
    custom_roster = ("custom-seat",)
    m = SM.build(custom_roster, THREE_VENDORS, "cursor", "anthropic", 0)
    assert any(d["constraint"] == "tier" for d in m["degradations"])
    assert m["seats"]["custom-seat"]["tier"] == "reviewer"


def test_fail_closed_malformed_verify():
    assert SM.verify({}, "cursor") == [{"constraint": "malformed"}]
    assert SM.verify({"not_seats": {}}, "cursor") == [{"constraint": "malformed"}]


def test_verify_maker_family_violation():
    hand_built = {
        "seats": {
            "security-reviewer": {
                "vendor": "claude",
                "model": "opus-4.8",
                "effort": "xhigh",
                "tier": "reviewer-deep",
                "family": "anthropic",
                "source": "rotated",
            },
        },
    }
    violations = SM.verify(hand_built, "anthropic")
    assert any(
        v.get("constraint") == "maker-family" and v.get("seat") == "security-reviewer"
        for v in violations
    )


def test_to_receipt_json_roundtrip():
    m = SM.build(
        SM.PANEL_ROSTER,
        THREE_VENDORS,
        "cursor",
        "anthropic",
        SM.seed_from(510, None),
    )
    receipt = SM.to_receipt(m)
    serialized = json.dumps(receipt)
    parsed = json.loads(serialized)
    assert parsed["seats"] == receipt["seats"]
    assert "violations" in parsed


# --- CLI --------------------------------------------------------------------------------------


def test_pure_functions_still_importable():
    assert callable(SM.build)
    assert callable(SM.verify)
    assert callable(SM.to_receipt)
    assert callable(SM.seed_from)
    assert callable(SM.main)


def test_cli_compose_with_live_vendors_override(capsys):
    rc = SM.main(
        [
            "x",
            "compose",
            "--live-vendors",
            "claude,codex,cursor",
            "--author-family",
            "cursor",
            "--narrative-family",
            "anthropic",
            "--pr-number",
            "510",
        ]
    )
    assert rc == 0
    receipt = json.loads(capsys.readouterr().out)
    assert len(receipt["seats"]) == 6
    assert "degradations" in receipt
    assert "seed" in receipt
    assert receipt["violations"] == []


def test_cli_compose_deterministic(capsys):
    argv = [
        "x",
        "compose",
        "--live-vendors",
        "claude,codex,cursor",
        "--author-family",
        "cursor",
        "--narrative-family",
        "anthropic",
        "--pr-number",
        "510",
    ]
    rc1 = SM.main(argv)
    out1 = capsys.readouterr().out
    rc2 = SM.main(argv)
    out2 = capsys.readouterr().out
    assert rc1 == rc2 == 0
    assert out1 == out2
