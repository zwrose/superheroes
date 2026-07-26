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
    m1 = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "xai", "anthropic", seed)
    m2 = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "xai", "anthropic", seed)
    assert m1["seats"] == m2["seats"]


def test_rotation_different_seeds():
    maps = []
    for seed in (0, 1, 2, 3, 4, 5):
        m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "xai", "anthropic", seed)
        maps.append(tuple(m["seats"][s]["vendor"] for s in SM.PANEL_ROSTER))
    assert len(set(maps)) > 1


def test_three_vendor_happy_path():
    seed = SM.seed_from(510, None)
    m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "xai", "anthropic", seed)
    grounding = m["seats"][SM.GROUNDING_SEAT]
    assert grounding["family"] not in {"xai", "anthropic"}
    critical_families = {
        m["seats"][s]["family"] for s in SM.CRITICAL_SEATS if s in m["seats"]
    }
    assert len(critical_families) >= 2
    assert SM.verify(m, "xai") == []


def test_claude_implemented_build():
    seed = SM.seed_from(99, None)
    m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "anthropic", "anthropic", seed)
    for seat in SM.STRONG_TIER_SEATS:
        assert m["seats"][seat]["family"] != "anthropic"
    assert m["seats"][SM.GROUNDING_SEAT]["family"] != "anthropic"
    assert SM.verify(m, "anthropic") == []


def test_single_vendor_floor():
    m = SM.build(SM.PANEL_ROSTER, ["claude"], "xai", "anthropic", 0)
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
        SM.PANEL_ROSTER, THREE_VENDORS, "xai", "anthropic", seed, pins=pins
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
        SM.PANEL_ROSTER, THREE_VENDORS, "xai", "anthropic", 0, pins=pins
    )
    pin_degs = [d for d in m["degradations"] if d["constraint"] == "pin"]
    assert any("not honorable" in d["reason"] for d in pin_degs)
    assert m["seats"]["code-reviewer"]["source"] != "pinned"


def test_pin_unknown_seat():
    pins = {"nonexistent-seat": {"vendor": "claude"}}
    m = SM.build(
        SM.PANEL_ROSTER, THREE_VENDORS, "xai", "anthropic", 0, pins=pins
    )
    pin_degs = [d for d in m["degradations"] if d["constraint"] == "pin"]
    assert any("unknown seat" in d["reason"] for d in pin_degs)


def test_fail_closed_empty_live_vendors():
    m = SM.build(SM.PANEL_ROSTER, [], "xai", "anthropic", 0)
    assert m["liveVendors"] == ["claude"]
    assert any(d["constraint"] == "live-vendors" for d in m["degradations"])


def test_fail_closed_grounding_provenance():
    m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, None, "anthropic", 0)
    assert any(d["constraint"] == "grounding-provenance" for d in m["degradations"])


def test_fail_closed_missing_tier():
    custom_roster = ("custom-seat",)
    m = SM.build(custom_roster, THREE_VENDORS, "xai", "anthropic", 0)
    assert any(d["constraint"] == "tier" for d in m["degradations"])
    assert m["seats"]["custom-seat"]["tier"] == "reviewer"


def test_fail_closed_malformed_verify():
    assert SM.verify({}, "xai") == [{"constraint": "malformed"}]
    assert SM.verify({"not_seats": {}}, "xai") == [{"constraint": "malformed"}]


def test_verify_maker_family_violation():
    hand_built = {
        "seats": {
            "security-reviewer": {
                "vendor": "claude",
                "model": "opus-5",
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
        "xai",
        "anthropic",
        SM.seed_from(510, None),
    )
    receipt = SM.to_receipt(m)
    serialized = json.dumps(receipt)
    parsed = json.loads(serialized)
    assert parsed["seats"] == receipt["seats"]
    assert "violations" in parsed


# --- LOGIC-1 biting maker-family (openai author) ----------------------------------------------


def test_biting_maker_family_openai_author():
    seed = SM.seed_from(510, None)
    m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "openai", "anthropic", seed)
    strong_critical = SM.STRONG_TIER_SEATS | SM.CRITICAL_SEATS
    for seat in strong_critical:
        assert m["seats"][seat]["family"] != "openai"
    assert SM.verify(m, "openai") == []


def test_isolate_strong_seat_exclusion_with_pins():
    pins = {
        "code-reviewer": {"vendor": "claude"},
        "test-reviewer": {"vendor": "claude"},
        "premortem-reviewer": {"vendor": "claude"},
    }
    m = SM.build(
        SM.PANEL_ROSTER, THREE_VENDORS, "anthropic", "openai", 0, pins=pins
    )
    for seat in SM.STRONG_TIER_SEATS:
        assert m["seats"][seat]["family"] != "anthropic"


def test_middle_relaxation_author_minority_without_critical_diversity():
    pins = {
        "code-reviewer": {"vendor": "claude"},
        "test-reviewer": {"vendor": "claude"},
        "premortem-reviewer": {"vendor": "claude"},
        "grounding-seat": {"vendor": "claude"},
    }
    m = SM.build(
        SM.PANEL_ROSTER, THREE_VENDORS, "anthropic", "openai", 0, pins=pins
    )
    assert any(d["constraint"] == "author-minority" for d in m["degradations"])
    violations = SM.verify(m, "anthropic")
    assert not any(v.get("constraint") == "critical-diversity" for v in violations)


# --- verify direction (hand-built maps) -------------------------------------------------------


def _full_seats_template(**overrides):
    """Minimal valid seat configs for all PANEL_ROSTER seats."""
    base = {
        "architecture-reviewer": {
            "vendor": "codex",
            "model": "gpt-5.6-sol",
            "effort": "xhigh",
            "tier": "reviewer-deep",
            "family": "openai",
            "source": "rotated",
        },
        "code-reviewer": {
            "vendor": "cursor",
            "model": "cursor-grok-4.5",
            "effort": "high",
            "tier": "reviewer-deep",
            "family": "xai",
            "source": "rotated",
        },
        "security-reviewer": {
            "vendor": "claude",
            "model": "opus-5",
            "effort": "xhigh",
            "tier": "reviewer-deep",
            "family": "anthropic",
            "source": "rotated",
        },
        "test-reviewer": {
            "vendor": "cursor",
            "model": "cursor-grok-4.5",
            "effort": "high",
            "tier": "reviewer-deep",
            "family": "xai",
            "source": "rotated",
        },
        "premortem-reviewer": {
            "vendor": "cursor",
            "model": "cursor-grok-4.5",
            "effort": "high",
            "tier": "reviewer-deep",
            "family": "xai",
            "source": "rotated",
        },
        "grounding-seat": {
            "vendor": "cursor",
            "model": "cursor-grok-4.5",
            "effort": "high",
            "tier": "reviewer",
            "family": "xai",
            "source": "rotated",
        },
    }
    base.update(overrides)
    return base


def test_verify_critical_maker_family_violation():
    seats = _full_seats_template()
    seats["premortem-reviewer"] = {
        "vendor": "codex",
        "model": "gpt-5.6-sol",
        "effort": "xhigh",
        "tier": "reviewer-deep",
        "family": "openai",
        "source": "rotated",
    }
    violations = SM.verify({"seats": seats}, "openai")
    assert any(
        v.get("constraint") == "maker-family" and v.get("seat") == "premortem-reviewer"
        for v in violations
    )


def test_verify_grounding_maker_family_violation():
    seats = _full_seats_template()
    seats["grounding-seat"] = {
        "vendor": "claude",
        "model": "sonnet-5",
        "effort": "high",
        "tier": "reviewer",
        "family": "anthropic",
        "source": "rotated",
    }
    violations = SM.verify({"seats": seats}, "anthropic")
    assert any(
        v.get("constraint") == "maker-family" and v.get("seat") == "grounding-seat"
        for v in violations
    )


def test_verify_strong_tier_violation():
    seats = _full_seats_template()
    seats["security-reviewer"] = {
        "vendor": "claude",
        "model": "sonnet-5",
        "effort": "high",
        "tier": "reviewer",
        "family": "anthropic",
        "source": "rotated",
    }
    violations = SM.verify({"seats": seats}, "xai")
    assert any(
        v.get("constraint") == "strong-tier" and v.get("seat") == "security-reviewer"
        for v in violations
    )


def test_verify_critical_diversity_violation():
    seats = _full_seats_template()
    seats["security-reviewer"] = {
        "vendor": "claude",
        "model": "opus-5",
        "effort": "xhigh",
        "tier": "reviewer-deep",
        "family": "anthropic",
        "source": "rotated",
    }
    seats["premortem-reviewer"] = {
        "vendor": "claude",
        "model": "opus-5",
        "effort": "xhigh",
        "tier": "reviewer-deep",
        "family": "anthropic",
        "source": "rotated",
    }
    seats["code-reviewer"] = {
        "vendor": "claude",
        "model": "opus-5",
        "effort": "xhigh",
        "tier": "reviewer-deep",
        "family": "anthropic",
        "source": "rotated",
    }
    violations = SM.verify({"seats": seats}, "xai")
    assert any(v.get("constraint") == "critical-diversity" for v in violations)


def test_verify_missing_seat():
    seats = _full_seats_template()
    del seats["test-reviewer"]
    violations = SM.verify({"seats": seats}, "xai")
    assert any(
        v.get("constraint") == "missing-seat" and v.get("seat") == "test-reviewer"
        for v in violations
    )


# --- grounding-independence degradation -------------------------------------------------------


def test_grounding_independence_degradation_two_vendor():
    m = SM.build(SM.PANEL_ROSTER, ["claude", "codex"], "anthropic", "openai", 0)
    assert any(
        d["constraint"] == "grounding-independence" for d in m["degradations"]
    )


def test_grounding_independence_degradation_single_vendor():
    m = SM.build(SM.PANEL_ROSTER, ["claude"], "anthropic", "openai", 0)
    assert any(
        d["constraint"] == "grounding-independence" for d in m["degradations"]
    )


# --- LOGIC-2 pin-breaks-constraint -------------------------------------------------------------


def test_pin_breaks_grounding_constraint_still_honored():
    pins = {"grounding-seat": {"vendor": "codex"}}
    m = SM.build(
        SM.PANEL_ROSTER, THREE_VENDORS, "anthropic", "openai", 0, pins=pins
    )
    assert any(d["constraint"] == "pin-breaks-constraint" for d in m["degradations"])
    assert m["seats"]["grounding-seat"]["source"] == "pinned"
    assert m["seats"]["grounding-seat"]["vendor"] == "codex"


# --- LOGIC-3 backfill non-empty family ---------------------------------------------------------


def test_backfill_never_empty_family():
    for live in (THREE_VENDORS, ["claude"], ["claude", "codex"], []):
        m = SM.build(SM.PANEL_ROSTER, live, "anthropic", "openai", 0)
        for seat, cfg in m["seats"].items():
            assert cfg["family"] != "", f"seat {seat} has empty family with live={live}"


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
            "xai",
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
        "xai",
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


def test_cli_compose_with_pins(capsys):
    rc = SM.main(
        [
            "x",
            "compose",
            "--live-vendors",
            "claude,codex,cursor",
            "--author-family",
            "openai",
            "--narrative-family",
            "anthropic",
            "--pins",
            '{"security-reviewer":{"vendor":"claude"}}',
            "--pr-number",
            "510",
        ]
    )
    assert rc == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["seats"]["security-reviewer"]["vendor"] == "claude"
    assert receipt["seats"]["security-reviewer"]["source"] == "pinned"


def test_review_code_skill_wires_seat_pins_from_ep_to_compose():
    skill_path = os.path.normpath(os.path.join(
        _HERE, "..", "..", "skills", "review-code", "SKILL.md"))
    with open(skill_path, encoding="utf-8") as fh:
        text = fh.read()
    assert ".seatPins" in text
    assert "(.seatPins // {}) == {} then empty" in text
    assert '[ -n "$SEAT_PINS" ]' in text
    assert "PINS_ARGS" in text
    assert "--pins" in text
    assert '"${PINS_ARGS[@]}"' in text
    seat_pins_idx = text.index("SEAT_PINS")
    assert 'echo "$EP"' in text[seat_pins_idx - 120:seat_pins_idx + 80]
    compose_line = text[text.index("SEAT_MAP=$(python3"):text.index("SEAT_MAP=$(python3") + 500]
    assert "SEAT_PINS" in compose_line or "PINS_ARGS" in compose_line
    assert "seat_map.py" in compose_line and '"${PINS_ARGS[@]}"' in compose_line


def test_cli_compose_pins_json_error(capsys):
    rc = SM.main(
        [
            "x",
            "compose",
            "--live-vendors",
            "claude",
            "--pins",
            "not-valid-json",
        ]
    )
    assert rc != 0
    assert capsys.readouterr().err


# --- reachable_configs + liveness cache (#610) ------------------------------------------------


def test_reachable_configs_equivalent_to_needed_configs_without_pins():
    import preflight_probe as pp

    vs = ["codex", "cursor"]
    rc = SM.reachable_configs(vs, None)
    full = pp.needed_configs_for(("reviewer-deep", "reviewer"), vs)
    for v in vs:
        assert {tuple(x) for x in rc[v]} == set(full[v])


def test_reachable_configs_narrows_when_all_seats_pinned_codex():
    pins = {seat: {"vendor": "codex"} for seat in SM.PANEL_ROSTER}
    rc = SM.reachable_configs(["codex", "cursor"], pins)
    assert rc["cursor"] == []
    assert rc["codex"]


def test_reachable_configs_conservative_unknown_vendor_pin():
    pins = {"code-reviewer": {"vendor": "unknown-vendor"}}
    rc = SM.reachable_configs(["codex", "cursor"], pins)
    assert {tuple(x) for x in rc["cursor"]}
    assert {tuple(x) for x in rc["codex"]}


def test_reachable_configs_malformed_pin_model_rotates():
    pins = {"code-reviewer": {"vendor": "codex", "model": 123}}
    rc = SM.reachable_configs(["codex", "cursor"], pins)
    assert rc["cursor"]
    assert rc["codex"]


def test_reachable_configs_pin_not_allowed_rotates(monkeypatch):
    real_is_allowed = SM.is_allowed

    def _fake_allowed(tier, vendor, model, effort):
        if vendor == "codex" and model == "custom-blocked":
            return False
        return real_is_allowed(tier, vendor, model, effort)

    monkeypatch.setattr(SM, "is_allowed", _fake_allowed)
    pins = {"code-reviewer": {"vendor": "codex", "model": "custom-blocked", "effort": "medium"}}
    rc = SM.reachable_configs(["codex", "cursor"], pins)
    default_cell = list(SM.matrix_config("reviewer-deep", "codex"))
    assert default_cell in rc["codex"]


def test_cli_compose_cache_only_ignores_live_vendors(monkeypatch, tmp_path, capsys):
    import liveness_cache

    cache_file = tmp_path / "empty-cache-dir" / "composition-liveness.json"
    monkeypatch.setattr(liveness_cache, "receipt_path", lambda cwd=None, root=None: str(cache_file))

    rc = SM.main(
        [
            "x",
            "compose",
            "--probe-mode",
            "cache-only",
            "--live-vendors",
            "claude,codex,cursor",
            "--configured-engines",
            "codex,cursor",
            "--author-family",
            "cursor",
            "--narrative-family",
            "anthropic",
            "--pr-number",
            "610",
        ]
    )
    assert rc == 0
    receipt = json.loads(capsys.readouterr().out)
    assert any(d.get("constraint") == "preflight-cache-only" for d in receipt["degradations"])
    assert receipt["liveVendors"] == ["claude"]


def test_cli_compose_cache_only_no_live_vendors(monkeypatch, tmp_path, capsys):
    import liveness_cache

    cache_file = tmp_path / "composition-liveness.json"
    monkeypatch.setattr(liveness_cache, "receipt_path", lambda cwd=None, root=None: str(cache_file))

    rc = SM.main(
        [
            "x",
            "compose",
            "--probe-mode",
            "cache-only",
            "--configured-engines",
            "codex,cursor",
            "--author-family",
            "cursor",
            "--narrative-family",
            "anthropic",
            "--pr-number",
            "610",
        ]
    )
    assert rc == 0
    receipt = json.loads(capsys.readouterr().out)
    assert any(d.get("constraint") == "preflight-cache-only" for d in receipt["degradations"])
    assert receipt["liveVendors"] == ["claude"]
    for seat_cfg in receipt["seats"].values():
        assert seat_cfg["vendor"] == "claude"


def test_composer_authored_diff_excludes_cursor_from_strong_critical_and_grounding():
    """#651: a composer-made diff derives authorFamily 'xai' straight from the registry, so grok —
    now the same family — is excluded from every strong-tier and critical seat and from grounding.
    Before the family merge this exclusion was vacuous: composer's family ('cursor') was one no
    reviewer cell ever produced, so grok could seat anywhere on a composer-made diff."""
    import model_registry as MRG

    author = MRG.family_for("code-fixer", "cursor")
    assert author == "xai"
    m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, author, "anthropic", SM.seed_from(651, None))
    for seat in sorted(SM.STRONG_TIER_SEATS | SM.CRITICAL_SEATS):
        assert m["seats"][seat]["family"] != "xai", seat
    assert m["seats"][SM.GROUNDING_SEAT]["family"] != "xai"
    assert SM.verify(m, author) == []


def test_cursor_only_panel_on_composer_diff_is_visibly_degraded():
    """#651: the configuration whose safety actually changed. Pre-merge, a cursor-only panel on a
    composer-made diff (author family 'cursor', every seat's family 'xai') recorded NO grounding
    degradation and NO maker-family violation — a whole panel of the author's own family read as
    clean. Post-merge both fire, so the self-review is visible instead of silent.

    #670 turned this exact configuration from violation into disclosed degradation: when no
    alternative family is live, every roster seat records `same-family` and verify reports no
    maker-family violation.

    The author family is READ FROM THE REGISTRY, never hardcoded: hardcoding 'xai' would leave this
    test green if `composer-2.5`'s family ever regressed, which is the one regression it exists to
    catch."""
    import model_registry as MRG

    author = MRG.family_for("code-fixer", "cursor")
    m = SM.build(SM.PANEL_ROSTER, ["cursor"], author, "anthropic", SM.seed_from(651, None))
    assert "grounding-independence" in {d["constraint"] for d in m["degradations"]}
    same_family = {
        (d["constraint"], d.get("seat"))
        for d in m["degradations"]
        if d.get("constraint") == "same-family"
    }
    for seat in SM.PANEL_ROSTER:
        assert ("same-family", seat) in same_family, seat
    assert not any(
        v.get("constraint") == "maker-family" for v in SM.verify(m, author)
    )


def test_maker_family_barred_from_test_seat():
    for seed in range(40):
        m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "openai", "anthropic", seed)
        assert m["seats"]["test-reviewer"]["family"] != "openai", seed
        assert SM.verify(m, "openai") == [], seed


def test_maker_family_barred_from_every_roster_seat():
    import model_registry as MRG

    families = (
        MRG.family_for("code-fixer", "claude"),
        MRG.family_for("code-fixer", "codex"),
        MRG.family_for("code-fixer", "cursor"),
    )
    for author in families:
        for seed in range(40):
            m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, author, "anthropic", seed)
            for seat in SM.PANEL_ROSTER:
                assert m["seats"][seat]["family"] != author, (seed, author, seat)


def test_single_vendor_collapse_is_same_family_degradation_not_violation():
    import model_registry as MRG

    author = MRG.family_for("code-fixer", "cursor")
    m = SM.build(SM.PANEL_ROSTER, ["cursor"], author, "anthropic", SM.seed_from(670, None))
    for seat in SM.PANEL_ROSTER:
        assert any(
            d.get("constraint") == "same-family" and d.get("seat") == seat
            for d in m["degradations"]
        ), seat
    assert not any(
        v.get("constraint") == "maker-family" for v in SM.verify(m, author)
    )
    assert not any(d.get("constraint") == "seat-unfilled" for d in m["degradations"])


def test_single_vendor_collapse_does_not_claim_author_minority():
    import model_registry as MRG

    author = MRG.family_for("code-fixer", "cursor")
    m = SM.build(SM.PANEL_ROSTER, ["cursor"], author, "anthropic", 0)
    assert not any(d.get("constraint") == "author-minority" for d in m["degradations"])


def test_grounding_prefers_narrative_family_over_maker():
    m = SM.build(SM.PANEL_ROSTER, ["claude", "codex"], "anthropic", "openai", 0)
    assert m["seats"][SM.GROUNDING_SEAT]["family"] == "openai"
    assert any(d["constraint"] == "grounding-independence" for d in m["degradations"])


def test_verify_unknown_liveness_is_a_violation():
    seats = _full_seats_template()
    seats["test-reviewer"] = {
        "vendor": "claude",
        "model": "opus-5",
        "effort": "xhigh",
        "tier": "reviewer-deep",
        "family": "anthropic",
        "source": "rotated",
    }
    violations = SM.verify({"seats": seats}, "anthropic")
    assert any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-reviewer"
        for v in violations
    )

    seats2 = _full_seats_template()
    seats2["test-reviewer"] = dict(seats["test-reviewer"])
    violations2 = SM.verify(
        {
            "seats": seats2,
            "liveVendors": ["claude"],
            "degradations": [
                {"constraint": "live-vendors", "reason": "no live vendors — defaulted to claude"},
            ],
        },
        "anthropic",
    )
    assert any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-reviewer"
        for v in violations2
    )


def test_verify_pin_scoped_liveness_is_a_violation():
    import model_registry as MRG

    author = MRG.family_for("code-fixer", "cursor")
    seat_cfg = {
        "vendor": "cursor",
        "model": "cursor-grok-4.5",
        "effort": "high",
        "tier": "reviewer-deep",
        "family": author,
        "source": "rotated",
    }
    sm = {
        "seats": {**_full_seats_template(), "test-reviewer": seat_cfg},
        "liveVendors": ["cursor"],
        "livenessPinScoped": True,
    }
    violations = SM.verify(sm, author)
    assert any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-reviewer"
        for v in violations
    )

    sm["livenessPinScoped"] = False
    violations_off = SM.verify(sm, author)
    assert not any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-reviewer"
        for v in violations_off
    )


def test_verify_malformed_liveness_is_a_violation():
    seats = _full_seats_template()
    seats["code-reviewer"] = {
        "vendor": "claude",
        "model": "opus-5",
        "effort": "xhigh",
        "tier": "reviewer-deep",
        "family": "anthropic",
        "source": "rotated",
    }
    for live in (["not-a-real-vendor"], [None]):
        violations = SM.verify({"seats": seats, "liveVendors": live}, "anthropic")
        assert any(
            v.get("constraint") == "maker-family" and v.get("seat") == "code-reviewer"
            for v in violations
        ), live


def test_to_receipt_carries_liveness_pin_scoped_provenance():
    import model_registry as MRG

    author = MRG.family_for("code-fixer", "cursor")
    seat_cfg = {
        "vendor": "cursor",
        "model": "cursor-grok-4.5",
        "effort": "high",
        "tier": "reviewer-deep",
        "family": author,
        "source": "rotated",
    }
    sm = {
        "seats": {**_full_seats_template(), "test-reviewer": seat_cfg},
        "liveVendors": ["cursor"],
        "livenessPinScoped": True,
    }
    receipt = SM.to_receipt(sm, author)
    assert receipt["livenessPinScoped"] is True
    round_trip = SM.to_receipt(receipt, author)
    assert any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-reviewer"
        for v in round_trip["violations"]
    )

    bare = {"seats": _full_seats_template(), "liveVendors": THREE_VENDORS}
    bare_receipt = SM.to_receipt(bare, "xai")
    assert bare_receipt["livenessPinScoped"] is False
    assert bare_receipt["seats"] == bare["seats"]
    assert bare_receipt["liveVendors"] == bare["liveVendors"]


def test_to_receipt_same_family_derivation_is_idempotent():
    import model_registry as MRG

    author = MRG.family_for("code-fixer", "cursor")
    m = SM.build(SM.PANEL_ROSTER, ["cursor"], author, "anthropic", 0)
    m["authorFamily"] = author
    for _ in range(2):
        receipt = SM.to_receipt(m, author)
        counts = {}
        for d in receipt["degradations"]:
            if d.get("constraint") == "same-family":
                counts[d.get("seat")] = counts.get(d.get("seat"), 0) + 1
        for seat in SM.PANEL_ROSTER:
            assert counts.get(seat, 0) == 1, seat
        m = receipt


def test_pinned_maker_seat_is_still_a_violation():
    pins = {"test-reviewer": {"vendor": "claude"}}
    m = SM.build(
        SM.PANEL_ROSTER, THREE_VENDORS, "anthropic", "openai", 0, pins=pins
    )
    assert m["seats"]["test-reviewer"]["source"] == "pinned"
    assert m["seats"]["test-reviewer"]["family"] == "anthropic"
    violations = SM.verify(m, "anthropic")
    assert any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-reviewer"
        for v in violations
    )
