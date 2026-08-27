import importlib.util
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import version_skew

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


def test_pinned_maker_seats_report_pin_breaks_constraint_not_author_minority():
    """Pinned maker-family seats are owner overrides disclosed as pin-breaks-constraint.

    The numeric author-minority cap is a separate constraint and was not breached here.
    """
    pins = {
        "code-reviewer": {"vendor": "claude"},
        "test-reviewer": {"vendor": "claude"},
        "premortem-reviewer": {"vendor": "claude"},
        "grounding-seat": {"vendor": "claude"},
    }
    m = SM.build(
        SM.PANEL_ROSTER, THREE_VENDORS, "anthropic", "openai", 0, pins=pins
    )
    assert not any(d.get("constraint") == "author-minority" for d in m["degradations"])
    for seat in (
        "code-reviewer",
        "test-reviewer",
        "premortem-reviewer",
        "grounding-seat",
    ):
        assert any(
            d.get("constraint") == "pin-breaks-constraint" and d.get("seat") == seat
            for d in m["degradations"]
        )
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
            "model": "cursor-grok-4.6",
            "effort": "xhigh",
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
            "model": "cursor-grok-4.6",
            "effort": "xhigh",
            "tier": "reviewer-deep",
            "family": "xai",
            "source": "rotated",
        },
        "premortem-reviewer": {
            "vendor": "cursor",
            "model": "cursor-grok-4.6",
            "effort": "xhigh",
            "tier": "reviewer-deep",
            "family": "xai",
            "source": "rotated",
        },
        "grounding-seat": {
            "vendor": "cursor",
            "model": "cursor-grok-4.6",
            "effort": "xhigh",
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


def test_cli_compose_probed_path_retains_codex_cell_through_receipt(monkeypatch, capsys):
    # axis: CLI serialization boundary — probed live_cells survives main→build→to_receipt
    import preflight_probe as pp

    aug15_cells = [
        ["codex", "gpt-5.6-sol", "xhigh"],
        ["cursor", "cursor-grok-4.6", "xhigh"],
    ]
    live_vendors = ["claude", "cursor"]

    def fake_live_vendors_for_composition(*_args, **_kwargs):
        return (live_vendors, aug15_cells, {}, [], "probed")

    monkeypatch.setattr(pp, "live_vendors_for_composition", fake_live_vendors_for_composition)

    rc = SM.main(
        [
            "x",
            "compose",
            "--configured-engines",
            "codex,cursor",
            "--author-family",
            "xai",
            "--narrative-family",
            "anthropic",
            "--pr-number",
            "795",
        ]
    )
    assert rc == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["liveCellsSource"] == "probed"
    assert ["codex", "gpt-5.6-sol", "xhigh"] in receipt["liveCells"]
    assert "codex" not in receipt["liveVendors"]
    codex_deep = [
        s
        for s in SM.LENS_SEATS
        if receipt["seats"][s]["vendor"] == "codex"
        and receipt["seats"][s]["model"] == "gpt-5.6-sol"
        and receipt["seats"][s]["effort"] == "xhigh"
        and receipt["seats"][s]["tier"] == "reviewer-deep"
    ]
    assert codex_deep, "codex deep-review seat not retained through CLI path"


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
    from skill_surface import surface_text
    text = surface_text("review-code")
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
    assert '--repo-root "$REPO_ROOT"' in compose_line


def test_review_code_skill_wires_repo_root_to_compose():
    from skill_surface import surface_text
    text = surface_text("review-code")
    compose_line = text[text.index("SEAT_MAP=$(python3"):text.index("SEAT_MAP=$(python3") + 500]
    assert '--repo-root "$REPO_ROOT"' in compose_line


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
            "liveCellsSource": "synthesized",
            "livenessPinScoped": False,
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
        "model": "cursor-grok-4.6",
        "effort": "xhigh",
        "tier": "reviewer-deep",
        "family": author,
        "source": "rotated",
    }
    sm = {
        "seats": {**_full_seats_template(), "test-reviewer": seat_cfg},
        "liveVendors": ["cursor"],
        "liveCellsSource": "synthesized",
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
        "model": "cursor-grok-4.6",
        "effort": "xhigh",
        "tier": "reviewer-deep",
        "family": author,
        "source": "rotated",
    }
    sm = {
        "seats": {**_full_seats_template(), "test-reviewer": seat_cfg},
        "liveVendors": ["cursor"],
        "liveCellsSource": "synthesized",
        "livenessPinScoped": True,
    }
    receipt = SM.to_receipt(sm, author)
    assert receipt["livenessPinScoped"] is True
    round_trip = SM.to_receipt(receipt, author)
    assert any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-reviewer"
        for v in round_trip["violations"]
    )

    bare = {
        "seats": _full_seats_template(),
        "liveVendors": THREE_VENDORS,
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
    }
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


def test_unexcused_maker_family_under_liveness_read_error_degradation():
    # axis: crashed liveness read examined an unknown subset — silence is not proof
    base = {
        "seats": {
            "test-reviewer": {
                "vendor": "claude",
                "model": "opus-5",
                "effort": "xhigh",
                "tier": "reviewer-deep",
                "family": "anthropic",
                "source": "rotated",
            },
        },
        "liveVendors": ["claude"],
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
        "authorFamily": "anthropic",
    }
    receipt = SM.to_receipt(
        {
            **base,
            "degradations": [
                {"constraint": "liveness-read-error", "reason": "read crashed"},
            ],
        },
        "anthropic",
    )
    unexcused = SM.unexcused_violations(receipt)
    assert any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-reviewer"
        for v in unexcused
    )


def test_build_empty_live_cells_source_fail_closed():
    # axis: falsey malformed liveCellsSource must not be laundered to synthesized
    m = SM.build(
        SM.PANEL_ROSTER,
        THREE_VENDORS,
        "xai",
        "anthropic",
        0,
        live_cells=None,
        live_cells_source="",
    )
    assert m["liveCellsSource"] == ""
    seat = "security-reviewer"
    cfg = m["seats"][seat]
    assert SM._resolvable_families_for_seat(m, seat, cfg) is None
    receipt = {**m, "violations": [{"constraint": "critical-diversity"}]}
    assert SM.unexcused_violations(receipt) == [
        {"constraint": "critical-diversity", "evidence": "unproven-liveness"},
    ]


def test_legacy_cache_only_constraint_still_marks_liveness_synthesized():
    # The `preflight-cache-only` producer was reaped (#1138), but seat maps are persisted and
    # re-read, so a map written by an OLDER plugin version can still carry the constraint. It
    # must keep reading as unproven liveness — dropping the deny-list member would fall open.
    base = {
        "seats": {
            "test-reviewer": {
                "vendor": "claude",
                "model": "opus-5",
                "effort": "xhigh",
                "tier": "reviewer-deep",
                "family": "anthropic",
                "source": "rotated",
            },
        },
        "liveVendors": ["claude"],
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
    }
    with_note = {
        **base,
        "degradations": [
            {"constraint": "preflight-cache-only", "reason": "cache miss — defaulted"},
        ],
    }
    violations = SM.verify(with_note, "anthropic")
    assert any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-reviewer"
        for v in violations
    )
    without_note = dict(base)
    no_violation = SM.verify(without_note, "anthropic")
    assert not any(v.get("constraint") == "maker-family" for v in no_violation)


def test_compose_merges_probe_notes_before_deriving_the_receipt(monkeypatch, tmp_path, capsys):
    # axis: a note the preflight returns is in `degradations` BEFORE violations are derived,
    # so a fell-open panel reads as unproven liveness rather than a clean maker-family pass.
    import liveness_cache
    import preflight_probe

    cache_file = tmp_path / "composition-liveness.json"
    monkeypatch.setattr(liveness_cache, "receipt_path", lambda cwd=None, root=None: str(cache_file))

    def _fell_open(configured, **kwargs):
        return (
            ["claude"],
            [],
            {"claude": {"live": True, "models": {}, "cells": []}},
            [{"constraint": "compose-failed", "reason": "probe unavailable"}],
            liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED,
        )

    monkeypatch.setattr(preflight_probe, "live_vendors_for_composition", _fell_open)

    rc = SM.main(
        [
            "x",
            "compose",
            "--configured-engines",
            "codex,cursor",
            "--author-family",
            "anthropic",
            "--narrative-family",
            "openai",
            "--pr-number",
            "670",
        ]
    )
    assert rc == 0
    receipt = json.loads(capsys.readouterr().out)
    assert any(d.get("constraint") == "compose-failed" for d in receipt["degradations"])
    assert any(v.get("constraint") == "maker-family" for v in receipt["violations"])


def _seat_in_both_same_family_and_maker_family(receipt):
    same = {d.get("seat") for d in receipt["degradations"] if d.get("constraint") == "same-family"}
    maker = {v.get("seat") for v in receipt["violations"] if v.get("constraint") == "maker-family"}
    return same & maker


def test_receipt_never_asserts_same_family_and_maker_family_for_one_seat():
    import model_registry as MRG

    seed = SM.seed_from(670, None)
    author = "anthropic"
    sm = SM.build(
        SM.PANEL_ROSTER,
        ["claude"],
        author,
        "anthropic",
        seed,
        liveness_pin_scoped=False,
    )
    sm["degradations"] = list(sm["degradations"]) + [
        {
            "constraint": "preflight-cache-only",
            "reason": "vendors not probed; panel falls open to Claude",
        }
    ]
    receipt = SM.to_receipt(sm)

    both = _seat_in_both_same_family_and_maker_family(receipt)
    assert not both, f"seats asserting both ways: {sorted(both)}"

    maker_seats = {
        v.get("seat")
        for v in receipt["violations"]
        if v.get("constraint") == "maker-family"
    }
    for seat in SM.PANEL_ROSTER:
        assert seat in maker_seats, seat

    same_family_seats = {
        d.get("seat")
        for d in receipt["degradations"]
        if d.get("constraint") == "same-family"
    }
    assert not same_family_seats, f"unexpected same-family: {sorted(same_family_seats)}"

    assert any(
        d.get("constraint") == "preflight-cache-only" for d in receipt["degradations"]
    )

    cursor_author = MRG.family_for("code-fixer", "cursor")
    collapse = SM.build(
        SM.PANEL_ROSTER,
        ["cursor"],
        cursor_author,
        "anthropic",
        seed,
        liveness_pin_scoped=False,
    )
    collapse_receipt = SM.to_receipt(collapse)
    for seat in SM.PANEL_ROSTER:
        assert any(
            d.get("constraint") == "same-family" and d.get("seat") == seat
            for d in collapse_receipt["degradations"]
        ), seat
    assert not any(
        v.get("constraint") == "maker-family" for v in collapse_receipt["violations"]
    )


def test_build_and_verify_agree_on_the_same_seat():
    pins = {"test-reviewer": {"vendor": "claude"}}
    pin_scoped = SM.build(
        SM.PANEL_ROSTER,
        THREE_VENDORS,
        "anthropic",
        "openai",
        0,
        pins=pins,
        liveness_pin_scoped=True,
    )
    receipt_pin = SM.to_receipt(pin_scoped, "anthropic")
    assert not _seat_in_both_same_family_and_maker_family(receipt_pin)

    synthesized = SM.build(SM.PANEL_ROSTER, [], "xai", "anthropic", 0)
    receipt_syn = SM.to_receipt(synthesized, "xai")
    assert not _seat_in_both_same_family_and_maker_family(receipt_syn)


def test_pinned_maker_seat_does_not_claim_author_minority():
    pins = {"test-reviewer": {"vendor": "claude"}}
    m = SM.build(
        SM.PANEL_ROSTER, THREE_VENDORS, "anthropic", "openai", 0, pins=pins
    )
    assert not any(d.get("constraint") == "author-minority" for d in m["degradations"])
    assert any(
        d.get("constraint") == "pin-breaks-constraint" and d.get("seat") == "test-reviewer"
        for d in m["degradations"]
    )
    violations = SM.verify(m, "anthropic")
    assert any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-reviewer"
        for v in violations
    )


def test_build_carries_liveness_pin_scoped():
    import model_registry as MRG

    author = MRG.family_for("code-fixer", "cursor")
    m_default = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, author, "anthropic", 0)
    assert m_default.get("livenessPinScoped") is False

    m_scoped = SM.build(
        SM.PANEL_ROSTER, THREE_VENDORS, author, "anthropic", 0, liveness_pin_scoped=True
    )
    assert m_scoped.get("livenessPinScoped") is True
    seat_cfg = dict(m_scoped["seats"]["test-reviewer"])
    seat_cfg["family"] = author
    m_scoped["seats"] = {**m_scoped["seats"], "test-reviewer": seat_cfg}
    violations = SM.verify(m_scoped, author)
    assert any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-reviewer"
        for v in violations
    )


def test_absent_liveness_pin_scoped_is_unknown_and_fails_closed():
    import model_registry as MRG

    author = MRG.family_for("code-fixer", "cursor")
    seat_cfg = {
        "vendor": "cursor",
        "model": "cursor-grok-4.6",
        "effort": "xhigh",
        "tier": "reviewer-deep",
        "family": author,
        "source": "rotated",
    }
    absent = {
        "seats": {**_full_seats_template(), "test-reviewer": seat_cfg},
        "liveVendors": ["cursor"],
    }
    violations_absent = SM.verify(absent, author)
    assert any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-reviewer"
        for v in violations_absent
    )

    explicit = {**absent, "livenessPinScoped": False, "liveCellsSource": "synthesized"}
    violations_explicit = SM.verify(explicit, author)
    assert not any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-reviewer"
        for v in violations_explicit
    )


def test_verify_mixed_valid_and_unknown_liveness_is_a_violation():
    import model_registry as MRG

    author = MRG.family_for("code-fixer", "cursor")
    seat_cfg = {
        "vendor": "cursor",
        "model": "cursor-grok-4.6",
        "effort": "xhigh",
        "tier": "reviewer-deep",
        "family": author,
        "source": "rotated",
    }
    mixed = {
        "seats": {**_full_seats_template(), "test-reviewer": seat_cfg},
        "liveVendors": ["cursor", "not-a-real-vendor"],
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
    }
    violations_mixed = SM.verify(mixed, author)
    assert any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-reviewer"
        for v in violations_mixed
    )

    clean = {**mixed, "liveVendors": ["cursor"], "liveCellsSource": "synthesized"}
    violations_clean = SM.verify(clean, author)
    assert not any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-reviewer"
        for v in violations_clean
    )


def test_to_receipt_records_the_author_family_it_verified():
    import model_registry as MRG

    author = MRG.family_for("code-fixer", "cursor")
    seat_cfg = {
        "vendor": "cursor",
        "model": "cursor-grok-4.6",
        "effort": "xhigh",
        "tier": "reviewer-deep",
        "family": author,
        "source": "rotated",
    }
    stale_map = {
        "seats": {**_full_seats_template(), "test-reviewer": seat_cfg},
        "liveVendors": ["cursor"],
        "livenessPinScoped": True,
        "authorFamily": "stale-family",
    }
    receipt = SM.to_receipt(stale_map, author)
    assert receipt["authorFamily"] == author
    round_trip = SM.to_receipt(receipt)
    assert any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-reviewer"
        for v in round_trip["violations"]
    )


def test_to_receipt_tolerates_null_degradations():
    r1 = SM.to_receipt({"seats": {}, "degradations": None})
    assert r1["degradations"] == []
    r2 = SM.to_receipt({"seats": {}, "degradations": "not-a-list"})
    assert r2["degradations"] == []


def test_verify_unresolvable_tier_is_a_violation():
    import model_registry as MRG

    author = MRG.family_for("code-fixer", "cursor")
    seat_cfg = {
        "vendor": "cursor",
        "model": "cursor-grok-4.6",
        "effort": "xhigh",
        "tier": "not-a-tier",
        "family": author,
        "source": "rotated",
    }
    sm = {
        "seats": {**_full_seats_template(), "test-reviewer": seat_cfg},
        "liveVendors": ["cursor"],
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
    }
    violations = SM.verify(sm, author)
    assert any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-reviewer"
        for v in violations
    )


# --- unexcused_violations (#680) --------------------------------------------------------------


def test_unexcused_maker_family_violation_is_unexcused():
    sm = {
        "seats": _full_seats_template(),
        "liveVendors": list(THREE_VENDORS),
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
        "degradations": [],
    }
    receipt = SM.to_receipt(sm, "anthropic")
    unexcused = SM.unexcused_violations(receipt)
    assert any(v.get("constraint") == "maker-family" for v in unexcused)


def test_unexcused_critical_diversity_claude_codex_is_excused():
    m = SM.build(SM.PANEL_ROSTER, ["claude", "codex"], "anthropic", "anthropic", 0)
    receipt = SM.to_receipt(m, "anthropic")
    assert any(v.get("constraint") == "critical-diversity" for v in receipt["violations"])
    assert SM.unexcused_violations(receipt) == []


def test_unexcused_critical_diversity_pinned_critical_seats_excused_by_pin():
    pins = {
        "code-reviewer": {"vendor": "claude"},
        "security-reviewer": {"vendor": "claude"},
        "premortem-reviewer": {"vendor": "claude"},
    }
    m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "xai", "anthropic", 0, pins=pins)
    receipt = SM.to_receipt(m, "xai")
    assert any(v.get("constraint") == "critical-diversity" for v in receipt["violations"])
    classified = SM.classify_violations(receipt)
    assert SM.unexcused_violations(receipt) == []
    assert any(
        r.get("constraint") == "critical-diversity" for r in classified["excusedByPin"]
    )


def test_unexcused_e1_unrecognised_constraint_never_excused():
    receipt = {
        "seats": _full_seats_template(),
        "degradations": [{"constraint": "maker-family", "seat": "code-reviewer"}],
        "violations": [{"constraint": "maker-family", "seat": "code-reviewer"}],
    }
    unexcused = SM.unexcused_violations(receipt)
    assert unexcused == [{"constraint": "maker-family", "seat": "code-reviewer"}]


def test_unexcused_e2_non_dict_violation_entry():
    receipt = {
        "seats": _full_seats_template(),
        "degradations": [],
        "violations": [42, {"constraint": "critical-diversity"}],
    }
    unexcused = SM.unexcused_violations(receipt)
    assert {"constraint": "malformed-violation-record"} in unexcused


def test_unexcused_e3_non_list_degradations():
    receipt = {
        "seats": _full_seats_template(),
        "degradations": "not-a-list",
        "violations": [{"constraint": "critical-diversity"}],
    }
    assert SM.unexcused_violations(receipt) == [
        {"constraint": "critical-diversity", "evidence": "unproven-liveness"},
    ]


def test_unexcused_e4_seatless_degradation_does_not_excuse_per_seat():
    receipt = {
        "seats": _full_seats_template(),
        "degradations": [{"constraint": "strong-tier"}],
        "violations": [{"constraint": "strong-tier", "seat": "security-reviewer"}],
    }
    unexcused = SM.unexcused_violations(receipt)
    assert unexcused == [
        {"constraint": "strong-tier", "seat": "security-reviewer", "evidence": "unproven-liveness"},
    ]


def test_unexcused_e5_pinned_seat_excuses_strong_tier_via_pin():
    seats = _full_seats_template()
    seats["architecture-reviewer"] = {
        "vendor": "claude",
        "model": "sonnet-5",
        "effort": "high",
        "tier": "reviewer",
        "family": "anthropic",
        "source": "pinned",
    }
    receipt = {
        "seats": seats,
        "liveVendors": list(THREE_VENDORS),
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
        "authorFamily": "xai",
        "degradations": [
            {"constraint": "strong-tier", "seat": "architecture-reviewer"},
        ],
        "violations": [{"constraint": "strong-tier", "seat": "architecture-reviewer"}],
    }
    classified = SM.classify_violations(receipt)
    assert SM.unexcused_violations(receipt) == []
    assert classified["excusedByPin"] == [
        {
            "constraint": "strong-tier",
            "seat": "architecture-reviewer",
            "excusedSeats": ["architecture-reviewer"],
        },
    ]


def test_unexcused_empty_or_missing_seats_fail_closed():
    assert SM.unexcused_violations({}) == []
    assert SM.unexcused_violations({"violations": [{"constraint": "critical-diversity"}]}) == [
        {"constraint": "critical-diversity"},
    ]
    assert SM.unexcused_violations(
        {"seats": {}, "violations": [{"constraint": "critical-diversity"}]},
    ) == [{"constraint": "critical-diversity"}]
    compose_failed = {
        "seats": {},
        "degradations": [{"constraint": "compose-failed"}],
        "violations": [{"constraint": "missing-seat", "seat": "code-reviewer"}],
    }
    assert SM.unexcused_violations(compose_failed) == compose_failed["violations"]
    receipt = SM.to_receipt({"seats": {}})
    assert SM.unexcused_violations(receipt) == receipt["violations"]


def test_unexcused_critical_diversity_missing_author_family_fail_closed():
    """#680 FIX2: unknown maker family must not excuse critical-diversity via empty alternatives."""
    seats = _full_seats_template()
    base = {
        "seats": seats,
        "liveVendors": list(THREE_VENDORS),
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
        "degradations": [{"constraint": "critical-diversity"}],
        "violations": [{"constraint": "critical-diversity"}],
    }
    breach = [{"constraint": "critical-diversity", "evidence": "unproven-liveness"}]

    for author in (None, "", 42):
        receipt = dict(base)
        if author is None:
            receipt["authorFamily"] = None
        else:
            receipt["authorFamily"] = author
        assert SM.unexcused_violations(receipt) == breach

    absent = dict(base)
    assert "authorFamily" not in absent
    assert SM.unexcused_violations(absent) == breach

    xai_receipt = dict(base, authorFamily="xai")
    assert SM.unexcused_violations(xai_receipt) == [
        {"constraint": "critical-diversity", "evidence": "alternative-live"},
    ]


@pytest.mark.parametrize(
    "live,maker,excused",
    [
        (["claude"], "anthropic", True),
        (["claude", "codex"], "anthropic", True),
        (["claude", "codex", "cursor"], "xai", False),
        (["claude", "codex"], "xai", False),
    ],
)
def test_unexcused_critical_diversity_availability_not_pin_presence(live, maker, excused):
    seats = _full_seats_template()
    receipt = {
        "seats": seats,
        "liveVendors": live,
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
        "authorFamily": maker,
        "degradations": [{"constraint": "critical-diversity"}],
        "violations": [{"constraint": "critical-diversity"}],
    }
    unexcused = SM.unexcused_violations(receipt)
    if excused:
        assert unexcused == []
    else:
        assert unexcused == [{"constraint": "critical-diversity", "evidence": "alternative-live"}]


def test_unexcused_strong_tier_excused_when_reviewer_deep_unavailable(monkeypatch):
    _real_matrix = SM.matrix_config

    def _no_reviewer_deep(tier, vendor):
        if tier == "reviewer-deep":
            return None
        return _real_matrix(tier, vendor)

    monkeypatch.setattr(SM, "matrix_config", _no_reviewer_deep)
    seats = _full_seats_template()
    seats["architecture-reviewer"] = {
        "vendor": "claude",
        "model": "opus-5",
        "effort": "xhigh",
        "tier": "reviewer",
        "family": "anthropic",
        "source": "rotated",
    }
    receipt = {
        "seats": seats,
        "liveVendors": ["claude"],
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
        "authorFamily": "anthropic",
        "degradations": [{"constraint": "strong-tier", "seat": "architecture-reviewer"}],
        "violations": [{"constraint": "strong-tier", "seat": "architecture-reviewer"}],
    }
    classified = SM.classify_violations(receipt)
    assert SM.unexcused_violations(receipt) == []
    assert classified["excusedByLiveness"] == [
        {"constraint": "strong-tier", "seat": "architecture-reviewer"},
    ]


def test_unexcused_strong_tier_stands_when_reviewer_deep_available():
    """FIX-1 counterexample: deep obtainable at claude — collapse not excused by liveness."""
    seats = _full_seats_template()
    seats["security-reviewer"] = {
        "vendor": "claude",
        "model": "sonnet-5",
        "effort": "high",
        "tier": "reviewer",
        "family": "anthropic",
        "source": "rotated",
    }
    receipt = {
        "seats": seats,
        "liveVendors": ["claude"],
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
        "authorFamily": "anthropic",
        "degradations": [{"constraint": "strong-tier", "seat": "security-reviewer"}],
        "violations": [{"constraint": "strong-tier", "seat": "security-reviewer"}],
    }
    assert SM.unexcused_violations(receipt) == [
        {
            "constraint": "strong-tier",
            "seat": "security-reviewer",
            "evidence": "alternative-live",
        },
    ]


def test_unexcused_critical_diversity_pin_not_causal_f3a():
    """FIX-2 F3a: pin on one critical seat does not excuse when diversity was achievable."""
    seats = _full_seats_template()
    for s in SM.PANEL_ROSTER:
        seats[s] = dict(seats[s])
        seats[s]["family"] = "anthropic"
    seats["security-reviewer"]["source"] = "pinned"
    receipt = {
        "seats": seats,
        "liveVendors": list(THREE_VENDORS),
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
        "authorFamily": "xai",
        "degradations": [{"constraint": "critical-diversity"}],
        "violations": [{"constraint": "critical-diversity"}],
    }
    assert SM.unexcused_violations(receipt) == [
        {"constraint": "critical-diversity", "evidence": "alternative-live"},
    ]


def test_unexcused_strong_tier_build_degradation_seat_field_load_bearing(monkeypatch):
    """Kills mutant that drops build()'s per-seat strong-tier degradation (#680 FIX 6)."""
    _real_matrix = SM.matrix_config

    def _no_reviewer_deep(tier, vendor):
        if tier == "reviewer-deep":
            return None
        return _real_matrix(tier, vendor)

    monkeypatch.setattr(SM, "matrix_config", _no_reviewer_deep)
    m = SM.build(SM.PANEL_ROSTER, ["cursor"], "xai", "anthropic", 0, liveness_pin_scoped=False)
    receipt = SM.to_receipt(m, "xai")
    strong_violations = [v for v in receipt["violations"] if v.get("constraint") == "strong-tier"]
    assert strong_violations
    classified = SM.classify_violations(receipt)
    assert all(
        any(
            x.get("constraint") == "strong-tier" and x.get("seat") == v.get("seat")
            for x in classified["excusedByLiveness"]
        )
        for v in strong_violations
    )


def test_unexcused_malformed_violation_field_types_do_not_raise():
    receipt = {
        "seats": _full_seats_template(),
        "liveVendors": list(THREE_VENDORS),
        "livenessPinScoped": False,
        "degradations": [],
        "violations": [
            {"constraint": None},
            {"constraint": "maker-family", "seat": 5},
            {"constraint": "critical-diversity"},
            {"constraint": "critical-diversity"},
        ],
    }
    unexcused = SM.unexcused_violations(receipt)
    assert {"constraint": "malformed-violation-record"} in unexcused
    assert {"constraint": "maker-family", "seat": 5} in unexcused
    assert sum(1 for u in unexcused if u.get("constraint") == "critical-diversity") == 2
    assert all(
        u.get("evidence") == "unproven-liveness"
        for u in unexcused
        if u.get("constraint") == "critical-diversity"
    )


def test_verify_critical_seat_missing_family_key_does_not_raise():
    seats = _full_seats_template()
    seats["code-reviewer"] = {"vendor": "claude", "tier": "reviewer-deep"}
    seats["security-reviewer"] = {
        "vendor": "claude",
        "tier": "reviewer-deep",
        "family": "anthropic",
    }
    seats["premortem-reviewer"] = {
        "vendor": "claude",
        "tier": "reviewer-deep",
        "family": "anthropic",
    }
    violations = SM.verify({"seats": seats}, "anthropic")
    assert any(v.get("constraint") == "critical-diversity" for v in violations)


def test_classify_unproven_liveness_liveness_pin_scoped_absent():
    receipt = {
        "seats": _full_seats_template(),
        "liveVendors": list(THREE_VENDORS),
        "authorFamily": "anthropic",
        "violations": [{"constraint": "critical-diversity"}],
    }
    unexcused = SM.unexcused_violations(receipt)
    assert unexcused == [
        {"constraint": "critical-diversity", "evidence": "unproven-liveness"},
    ]


def test_classify_unproven_liveness_preflight_cache_only_degradation():
    # Legacy-receipt axis: no live producer since #1138; a stale map must still classify unproven.
    receipt = {
        "seats": _full_seats_template(),
        "liveVendors": list(THREE_VENDORS),
        "livenessPinScoped": False,
        "authorFamily": "anthropic",
        "degradations": [{"constraint": "preflight-cache-only"}],
        "violations": [{"constraint": "critical-diversity"}],
    }
    unexcused = SM.unexcused_violations(receipt)
    assert unexcused == [
        {"constraint": "critical-diversity", "evidence": "unproven-liveness"},
    ]


def test_classify_truthy_non_list_degradations_do_not_raise():
    receipt = {
        "seats": _full_seats_template(),
        "liveVendors": list(THREE_VENDORS),
        "livenessPinScoped": False,
        "authorFamily": "anthropic",
        "degradations": 42,
        "violations": [{"constraint": "critical-diversity"}],
    }
    assert SM.unexcused_violations(receipt) == [
        {"constraint": "critical-diversity", "evidence": "unproven-liveness"},
    ]


def test_classify_pin_excuses_critical_diversity_collapsed_seats():
    seats = _full_seats_template()
    for s in SM.CRITICAL_SEATS:
        seats[s] = dict(seats[s])
        seats[s]["source"] = "pinned"
        seats[s]["family"] = "anthropic"
        seats[s]["vendor"] = "claude"
    receipt = {
        "seats": seats,
        "liveVendors": list(THREE_VENDORS),
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
        "authorFamily": "xai",
        "violations": [{"constraint": "critical-diversity"}],
    }
    classified = SM.classify_violations(receipt)
    assert classified["excusedByPin"]
    assert SM.unexcused_violations(receipt) == []


def _resolvable_families_fixture():
    seat_map = {
        "liveVendors": list(THREE_VENDORS),
        "liveCellsSource": "synthesized",
        "degradations": [],
        "livenessPinScoped": False,
    }
    cfg = _full_seats_template()["security-reviewer"]
    return seat_map, "security-reviewer", cfg


@pytest.mark.parametrize(
    "seat_map_override,cfg_override,expect_empty",
    [
        ({"livenessPinScoped": True}, None, False),
        ({"degradations": [{"constraint": "live-vendors", "reason": "synth"}]}, None, False),
        ({"degradations": [{"constraint": "preflight-cache-only", "reason": "cache"}]}, None, False),
        ({"degradations": [{"constraint": "compose-failed", "reason": "fail"}]}, None, False),
        ({"degradations": [{"constraint": "liveness-read-error", "reason": "crash"}]}, None, False),
        ({"liveVendors": None}, None, False),
        ({"liveVendors": []}, None, False),
        ({"liveVendors": ["not-a-real-vendor"]}, None, False),
        ({"degradations": 42}, None, False),
        (None, {"tier": "no-such-tier"}, True),
    ],
    ids=[
        "pin-scoped-true",
        "degradation-live-vendors",
        "degradation-preflight-cache-only",
        "degradation-compose-failed",
        "degradation-liveness-read-error",
        "live-vendors-absent",
        "live-vendors-empty",
        "unregistered-vendor",
        "degradations-non-list",
        "nothing-resolvable-at-tier",
    ],
)
def test_resolvable_families_for_seat_unusable_shapes(seat_map_override, cfg_override, expect_empty):
    seat_map, seat, cfg = _resolvable_families_fixture()
    cfg = dict(cfg)
    if seat_map_override is not None:
        for key, val in seat_map_override.items():
            if key == "liveVendors" and val is None:
                seat_map.pop("liveVendors", None)
            else:
                seat_map[key] = val
    if cfg_override:
        cfg.update(cfg_override)
    result = SM._resolvable_families_for_seat(seat_map, seat, cfg)
    if expect_empty:
        assert result == set()
    else:
        assert result is None


def test_resolvable_families_pin_scoped_absent_is_unusable():
    seat_map, seat, cfg = _resolvable_families_fixture()
    seat_map.pop("livenessPinScoped", None)
    assert SM._resolvable_families_for_seat(seat_map, seat, cfg) is None


def test_resolvable_families_for_seat_positive_family_set():
    seat_map, seat, cfg = _resolvable_families_fixture()
    seat_map["livenessPinScoped"] = False
    fams = SM._resolvable_families_for_seat(seat_map, seat, cfg)
    assert fams == {"anthropic", "openai", "xai"}


def test_resolvable_families_live_cells_source_probed_vs_synthesized_vs_absent():
    # axis: probed uses cell-level derivation; synthesized uses vendor-level; absent is unusable
    seat_map, seat, cfg = _resolvable_families_fixture()
    seat_map["livenessPinScoped"] = False
    partial_cells = [["cursor", "cursor-grok-4.6", "xhigh"]]
    vendor_level = {"anthropic", "openai", "xai"}
    cell_level = {"anthropic", "xai"}

    probed_map = {
        **seat_map,
        "liveCellsSource": "probed",
        "liveCells": partial_cells,
    }
    assert SM._resolvable_families_for_seat(probed_map, seat, cfg) == cell_level

    synthesized_map = {**seat_map, "liveCellsSource": "synthesized"}
    assert SM._resolvable_families_for_seat(synthesized_map, seat, cfg) == vendor_level

    absent_map = {k: v for k, v in seat_map.items() if k != "liveCellsSource"}
    absent_map.pop("liveCells", None)
    assert SM._resolvable_families_for_seat(absent_map, seat, cfg) is None


def test_resolvable_families_unprobed_empty_degradations_returns_none():
    # axis: provenance alone marks evidence unusable — not the preflight-cache-only note
    seat_map, seat, cfg = _resolvable_families_fixture()
    seat_map["livenessPinScoped"] = False
    seat_map["degradations"] = []
    seat_map["liveCellsSource"] = "unprobed"
    seat_map["liveCells"] = []
    seat_map["liveVendors"] = ["claude", "codex", "cursor"]
    assert SM._resolvable_families_for_seat(seat_map, seat, cfg) is None


@pytest.mark.parametrize(
    "cells_source",
    [
        pytest.param(None, id="absent"),
        pytest.param("", id="empty-string"),
        pytest.param("bogus", id="unrecognized-string"),
        pytest.param("Probed", id="wrong-case"),
        pytest.param(123, id="non-string-int"),
        pytest.param({"source": "probed"}, id="non-string-dict"),
        pytest.param(["probed"], id="non-string-list"),
    ],
)
def test_resolvable_families_unknown_live_cells_source_returns_none(cells_source):
    # axis: only members of LIVE_CELLS_SOURCES are usable evidence
    seat_map, seat, cfg = _resolvable_families_fixture()
    if cells_source is None:
        seat_map.pop("liveCellsSource", None)
    else:
        seat_map["liveCellsSource"] = cells_source
    assert SM._resolvable_families_for_seat(seat_map, seat, cfg) is None


def test_live_cells_sources_closed_set_membership():
    # axis: recognizer keys on the closed tuple — member changes must update this pin
    assert SM.LIVE_CELLS_SOURCES == ("probed", "synthesized", "unprobed")


def test_unexcused_critical_diversity_corrupted_live_cells_source_fail_closed():
    # axis: corrupted liveCellsSource must not excuse critical-diversity via vendor fall-through
    seats = _full_seats_template()
    receipt = {
        "seats": seats,
        "liveVendors": ["claude"],
        "liveCellsSource": "bogus",
        "livenessPinScoped": False,
        "authorFamily": "anthropic",
        "degradations": [{"constraint": "critical-diversity"}],
        "violations": [{"constraint": "critical-diversity"}],
    }
    assert SM.unexcused_violations(receipt) == [
        {"constraint": "critical-diversity", "evidence": "unproven-liveness"},
    ]


def test_live_cells_fields_for_receipt_preserves_unprobed():
    # bite-axis: unprobed source must not be relabelled synthesized or gain synthesized cells
    seat_map = {
        "liveCellsSource": "unprobed",
        "liveCells": [],
        "liveVendors": ["claude", "codex", "cursor"],
        "seats": {s: {} for s in SM.PANEL_ROSTER},
    }
    cells, source = SM._live_cells_fields_for_receipt(seat_map)
    assert source == "unprobed"
    assert cells == []


# --- pin-shape normalization + refusal (#1039) -------------------------------------------------


def test_normalize_pins_string_shorthand_is_exactly_the_vendor_object():
    # axis: a bare string pin resolves as the vendor, with no other key invented
    normalized, errors = SM.normalize_pins({"code-reviewer": "codex"})
    assert normalized == {"code-reviewer": {"vendor": "codex"}}
    assert errors == []


def test_normalize_pins_passes_object_pins_through_unchanged():
    # axis: the existing object shape is untouched by the new chokepoint
    pins = {"code-reviewer": {"vendor": "codex", "model": "gpt-5.6-terra", "effort": "high"}}
    normalized, errors = SM.normalize_pins(pins)
    assert normalized == pins
    assert errors == []


@pytest.mark.parametrize(
    "value",
    [None, 5, True, 1.5, ["codex"], {"vendor": "codex"}.keys()],
    ids=["null", "int", "bool", "float", "list", "non-dict-mapping-view"],
)
def test_normalize_pins_refuses_non_object_non_string_shapes(value):
    # axis: REFUSAL by name — an unusable seat value is named, never dropped and never crashed on
    normalized, errors = SM.normalize_pins({"code-reviewer": value})
    assert errors == ["pins-invalid:code-reviewer"]
    assert normalized == {}


def test_normalize_pins_names_every_unusable_seat_not_just_the_first():
    normalized, errors = SM.normalize_pins(
        {"code-reviewer": 5, "security-reviewer": "codex", "test-reviewer": None}
    )
    assert sorted(errors) == ["pins-invalid:code-reviewer", "pins-invalid:test-reviewer"]
    assert normalized == {"security-reviewer": {"vendor": "codex"}}


@pytest.mark.parametrize(
    "value", ["codex", 5, ["codex"], True], ids=["str", "int", "list", "bool"]
)
def test_normalize_pins_refuses_a_pin_map_that_is_not_an_object(value):
    # axis: REFUSAL by name at the map level — the seatless token, still never a traceback
    normalized, errors = SM.normalize_pins(value)
    assert errors == ["pins-invalid"]
    assert normalized == {}


def test_normalize_pins_absent_map_is_not_a_refusal():
    assert SM.normalize_pins(None) == ({}, [])
    assert SM.normalize_pins({}) == ({}, [])


def test_build_string_pin_resolves_as_vendor():
    m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "xai", "anthropic", 0, pins={"code-reviewer": "claude"})
    assert m["seats"]["code-reviewer"]["source"] == "pinned"
    assert m["seats"]["code-reviewer"]["vendor"] == "claude"


def test_build_string_pin_is_identical_to_the_object_pin():
    shorthand = SM.build(
        SM.PANEL_ROSTER, THREE_VENDORS, "xai", "anthropic", 7, pins={"code-reviewer": "claude"}
    )
    longhand = SM.build(
        SM.PANEL_ROSTER, THREE_VENDORS, "xai", "anthropic", 7, pins={"code-reviewer": {"vendor": "claude"}}
    )
    assert shorthand == longhand


def test_build_unusable_pin_shape_degrades_instead_of_raising():
    # axis: loudness — the old behaviour was AttributeError; the new one is a named degradation
    m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "xai", "anthropic", 0, pins={"code-reviewer": 5})
    pin_degs = [d for d in m["degradations"] if d["constraint"] == "pin"]
    assert any(d["reason"] == "pins-invalid:code-reviewer" for d in pin_degs)
    assert m["seats"]["code-reviewer"]["source"] != "pinned"


def test_build_pin_map_that_is_not_an_object_degrades_instead_of_raising():
    m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "xai", "anthropic", 0, pins="claude")
    pin_degs = [d for d in m["degradations"] if d["constraint"] == "pin"]
    assert any(d["reason"] == "pins-invalid" for d in pin_degs)
    assert set(m["seats"]) == set(SM.PANEL_ROSTER)


def test_reachable_configs_string_pin_narrows_like_the_object_pin():
    shorthand = SM.reachable_configs(["codex", "cursor"], {s: "codex" for s in SM.PANEL_ROSTER})
    longhand = SM.reachable_configs(
        ["codex", "cursor"], {s: {"vendor": "codex"} for s in SM.PANEL_ROSTER}
    )
    assert shorthand == longhand
    assert shorthand["cursor"] == []


def test_reachable_configs_unusable_pin_shape_rotates_conservatively():
    # CHARACTERIZER, not refusal coverage (review round 3, Minor): this passes with or without
    # normalize_pins in reachable_configs, because the pre-existing `isinstance(pin, dict)` guard
    # already rotates an unusable shape. What it pins is the operator-facing property that the
    # liveness-narrowing path stays CONSERVATIVE (over-probes) rather than refusing — the CLI is
    # where refusal lives. The chokepoint coverage for this function is
    # test_reachable_configs_string_pin_narrows_like_the_object_pin, which does go red without it.
    rc = SM.reachable_configs(["codex", "cursor"], {"code-reviewer": 5})
    assert rc["cursor"] != []


def test_cli_compose_string_pin_shorthand(capsys):
    rc = SM.main(
        [
            "x", "compose",
            "--live-vendors", "claude,codex,cursor",
            "--author-family", "openai",
            "--narrative-family", "anthropic",
            "--pins", '{"security-reviewer":"claude"}',
            "--pr-number", "1039",
        ]
    )
    assert rc == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["seats"]["security-reviewer"]["vendor"] == "claude"
    assert receipt["seats"]["security-reviewer"]["source"] == "pinned"


def test_cli_compose_refuses_unusable_pin_shape(capsys):
    rc = SM.main(
        [
            "x", "compose",
            "--live-vendors", "claude,codex,cursor",
            "--pins", '{"security-reviewer":5}',
        ]
    )
    assert rc != 0
    captured = capsys.readouterr()
    assert "pins-invalid:security-reviewer" in captured.err
    assert captured.out == ""


def test_cli_compose_refuses_a_pin_map_that_is_not_an_object(capsys):
    rc = SM.main(["x", "compose", "--live-vendors", "claude", "--pins", '"codex"'])
    assert rc != 0
    captured = capsys.readouterr()
    assert "pins-invalid" in captured.err
    assert captured.out == ""


def test_cli_compose_null_pins_is_not_a_refusal(capsys):
    rc = SM.main(["x", "compose", "--live-vendors", "claude,codex,cursor", "--pins", "null"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["seats"]


def test_review_code_reference_documents_pin_shorthand_and_rerotation():
    from skill_surface import surface_text
    text = surface_text("review-code")
    assert "pins-invalid:<seat>" in text
    assert "bare\nstring is the documented shorthand" in text or "bare string is the documented shorthand" in text
    assert "Pinning one seat\ndoes not hold the others" in text or "Pinning one seat does not hold the others" in text
    # the two boundaries the refusal does NOT cover must stay documented (review round 1, both Minor)
    flat = " ".join(text.split())
    assert "`--pins null` is an **absent** pin map, not a refusal" in flat
    assert "the refusal grades the **value shape** only" in flat


# --- cell-level liveness (#795 WO-B) ----------------------------------------------------------


def _aug15_live_cells():
    """2026-08-15 shape: codex sol/xhigh live, terra/high absent; cursor cells live."""
    return [
        ["codex", "gpt-5.6-sol", "xhigh"],
        ["cursor", "cursor-grok-4.6", "xhigh"],
    ]


def test_dod_aug15_partial_codex_cell_live():
    """DoD row 1: lens seats keep codex at reviewer-deep when only sol/xhigh is live."""
    live_vendors = ["claude", "cursor"]
    live_cells = _aug15_live_cells()
    m = SM.build(
        SM.PANEL_ROSTER,
        live_vendors,
        "xai",
        "anthropic",
        SM.seed_from(795, None),
        live_cells=live_cells,
        live_cells_source="probed",
    )
    assert "codex" not in m["liveVendors"]
    codex_lens = [
        s for s in SM.LENS_SEATS
        if m["seats"][s]["vendor"] == "codex"
        and m["seats"][s]["model"] == "gpt-5.6-sol"
        and m["seats"][s]["effort"] == "xhigh"
    ]
    assert codex_lens, "codex lost from every lens seat despite sol/xhigh live"
    for seat in SM.LENS_SEATS:
        pinned = SM.build(
            SM.PANEL_ROSTER,
            live_vendors,
            "xai",
            "anthropic",
            0,
            pins={seat: {"vendor": "codex"}},
            live_cells=live_cells,
            live_cells_source="probed",
        )
        cfg = pinned["seats"][seat]
        assert cfg["source"] == "pinned", seat
        assert cfg["vendor"] == "codex", seat
        assert cfg["model"] == "gpt-5.6-sol", seat
        assert cfg["effort"] == "xhigh", seat
        assert cfg["tier"] == "reviewer-deep", seat
    grounding = m["seats"][SM.GROUNDING_SEAT]
    assert grounding["vendor"] != "codex"
    assert grounding["model"] != "gpt-5.6-terra"


def test_dod_ab3_arm_g_pinned_codex_sol_honored():
    """DoD row 2: pin to live sol/xhigh is honored when terra is dead."""
    live_vendors = ["claude", "cursor"]
    live_cells = _aug15_live_cells()
    pins = {
        "code-reviewer": {
            "vendor": "codex",
            "model": "gpt-5.6-sol",
            "effort": "xhigh",
        },
    }
    m = SM.build(
        SM.PANEL_ROSTER,
        live_vendors,
        "xai",
        "anthropic",
        0,
        pins=pins,
        live_cells=live_cells,
        live_cells_source="probed",
    )
    pinned = m["seats"]["code-reviewer"]
    assert pinned["source"] == "pinned"
    assert pinned["vendor"] == "codex"
    assert pinned["model"] == "gpt-5.6-sol"
    assert pinned["effort"] == "xhigh"
    pin_degs = [d for d in m["degradations"] if d["constraint"] == "pin"]
    assert not any("not honorable" in d["reason"] for d in pin_degs)


def test_census_seated_cells_appear_in_live_cells():
    # bite-axis: a seated cell absent from the probed live set is caught
    live_cells = [
        ["claude", "opus-5", "xhigh"],
        ["codex", "gpt-5.6-sol", "xhigh"],
        ["cursor", "cursor-grok-4.6", "xhigh"],
    ]
    m = SM.build(
        SM.PANEL_ROSTER,
        THREE_VENDORS,
        "xai",
        "anthropic",
        SM.seed_from(795, None),
        live_cells=live_cells,
        live_cells_source="probed",
    )
    assert m["liveCellsSource"] == "probed"
    live_set = {tuple(c) for c in m["liveCells"]}
    for seat, cfg in m["seats"].items():
        if cfg["vendor"] == "claude":
            continue
        cell = (cfg["vendor"], cfg["model"], cfg["effort"])
        assert cell in live_set, "seat %s seated dead cell %s" % (seat, cell)


def test_to_receipt_always_emits_live_cells_fields():
    # bite-axis: provenance — liveCells and liveCellsSource must appear together on every receipt
    receipts = []
    m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "xai", "anthropic", 0)
    assert "liveCells" in m
    assert m["liveCells"]
    receipts.append(SM.to_receipt(m))

    probed = SM.build(
        SM.PANEL_ROSTER,
        THREE_VENDORS,
        "xai",
        "anthropic",
        0,
        live_cells=[
            ["codex", "gpt-5.6-sol", "xhigh"],
            ["cursor", "cursor-grok-4.6", "xhigh"],
        ],
        live_cells_source="probed",
    )
    probed_receipt = SM.to_receipt(probed)
    assert probed_receipt["liveCellsSource"] == "probed"
    receipts.append(probed_receipt)

    synthesized = SM.build(
        SM.PANEL_ROSTER,
        THREE_VENDORS,
        "xai",
        "anthropic",
        0,
        live_cells=None,
        live_cells_source="synthesized",
    )
    syn_receipt = SM.to_receipt(synthesized)
    assert syn_receipt["liveCellsSource"] == "synthesized"
    receipts.append(syn_receipt)

    bare = {"seats": {}, "liveVendors": ["claude", "codex", "cursor"]}
    bare_receipt = SM.to_receipt(bare, "xai")
    assert bare_receipt["liveCells"] is not None
    assert bare_receipt["liveCellsSource"] == "synthesized"
    receipts.append(bare_receipt)

    for receipt in receipts:
        assert "liveCells" in receipt
        assert "liveCellsSource" in receipt


_PLUGIN_ROOT = os.path.join(_LIB, "..")


def _write_superheroes_fixture_repo(tmp_path, divergent=True):
    repo = tmp_path / "fixture_repo"
    sh = repo / "plugins" / "superheroes"
    manifest = sh / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps({"name": "superheroes", "version": "0.31.0"}),
        encoding="utf-8",
    )
    (sh / "version.txt").write_text("0.31.0\n", encoding="utf-8")
    lib = sh / "lib"
    lib.mkdir(parents=True, exist_ok=True)
    for entry in version_skew.SEMANTICS_FILES:
        src = os.path.join(_PLUGIN_ROOT, entry)
        content = open(src, encoding="utf-8").read()
        if divergent and entry == "lib/model_registry.py":
            content = content + "# fixture skew marker\n"
        (lib / os.path.basename(entry)).write_text(content, encoding="utf-8")
    return str(repo)


def test_cli_compose_repo_root_superheroes_skew_emits_plugin_version_skew(tmp_path, capsys):
    repo_root = _write_superheroes_fixture_repo(tmp_path, divergent=True)
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
            "677",
            "--repo-root",
            repo_root,
        ]
    )
    assert rc == 0
    receipt = json.loads(capsys.readouterr().out)
    skew = [d for d in receipt["degradations"] if d.get("constraint") == "plugin-version-skew"]
    assert len(skew) == 1
    assert skew[0]["detail"] == version_skew.DETAIL_SEMANTICS_DIVERGENT
    assert "lib/model_registry.py" in skew[0]["reason"]


def test_cli_compose_repo_root_superheroes_clean_emits_no_skew_degradation(tmp_path, capsys):
    repo_root = _write_superheroes_fixture_repo(tmp_path, divergent=False)
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
            "677",
            "--repo-root",
            repo_root,
        ]
    )
    assert rc == 0
    receipt = json.loads(capsys.readouterr().out)
    skew = [d for d in receipt["degradations"] if d.get("constraint") == "plugin-version-skew"]
    assert skew == []
    assert receipt["pluginVersionSkew"]["status"] == version_skew.STATUS_CHECKED_CLEAN
    assert receipt["pluginVersionSkew"]["detail"] == version_skew.DETAIL_NO_DIVERGENCE


def test_cli_compose_repo_root_not_superheroes_emits_no_plugin_version_skew(tmp_path, capsys):
    repo_root = tmp_path / "other_repo"
    repo_root.mkdir()
    (repo_root / "README.md").write_text("not superheroes\n", encoding="utf-8")
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
            "677",
            "--repo-root",
            str(repo_root),
        ]
    )
    assert rc == 0
    receipt = json.loads(capsys.readouterr().out)
    skew = [d for d in receipt["degradations"] if d.get("constraint") == "plugin-version-skew"]
    assert skew == []
    assert receipt["pluginVersionSkew"]["status"] == version_skew.STATUS_NOT_CHECKED
    assert receipt["pluginVersionSkew"]["detail"] == version_skew.DETAIL_NOT_SOURCE_REPO


_COMPOSE_SKEW_APPEND_CASES = [
    (version_skew.STATUS_CHECKED_CLEAN, version_skew.DETAIL_NO_DIVERGENCE, False),
    (version_skew.STATUS_NOT_CHECKED, version_skew.DETAIL_NOT_SOURCE_REPO, False),
] + [
    (version_skew.STATUS_CHECKED_DEGRADED, degrading_detail, True)
    for degrading_detail in sorted(version_skew.DEGRADING_DETAILS)
]
assert frozenset(
    case_detail for _, case_detail, should_append in _COMPOSE_SKEW_APPEND_CASES if should_append
) == version_skew.DEGRADING_DETAILS


@pytest.mark.parametrize(
    "status,detail,should_append",
    _COMPOSE_SKEW_APPEND_CASES,
)
def test_compose_skew_record_appends_degradation_only_when_degraded(
    monkeypatch, tmp_path, capsys, status, detail, should_append,
):
    repo_root = _write_superheroes_fixture_repo(tmp_path, divergent=False)

    def _fake_detect(_repo_root, _plugin_root):
        return {
            "constraint": version_skew.CONSTRAINT,
            "status": status,
            "detail": detail,
            "reason": "plugin-version-skew: append-rule behavior test",
            "inspectedRoot": repo_root,
        }

    monkeypatch.setattr(version_skew, "detect", _fake_detect)
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
            "677",
            "--repo-root",
            repo_root,
        ]
    )
    assert rc == 0
    receipt = json.loads(capsys.readouterr().out)
    skew = [d for d in receipt["degradations"] if d.get("constraint") == "plugin-version-skew"]
    if should_append:
        assert len(skew) == 1
        assert skew[0]["status"] == status
        assert skew[0]["detail"] == detail
    else:
        assert skew == []
