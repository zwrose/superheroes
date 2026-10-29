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

import model_registry as MR

_PIN_ONLY_CODEX = MR.pin_only_models("codex")[0]
_SECOND_CODEX_MODEL = MR.codex_peer_for_claude_tier("opus")

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
    m1 = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "xai", seed)
    m2 = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "xai", seed)
    assert m1["seats"] == m2["seats"]


def test_rotation_different_seeds():
    maps = []
    for seed in (0, 1, 2, 3, 4, 5):
        m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "xai", seed)
        maps.append(tuple(m["seats"][s]["vendor"] for s in SM.PANEL_ROSTER))
    assert len(set(maps)) > 1


def test_three_vendor_happy_path():
    seed = SM.seed_from(510, None)
    m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "xai", seed)
    critical_families = {
        m["seats"][s]["family"] for s in SM.CRITICAL_SEATS if s in m["seats"]
    }
    assert len(critical_families) >= 2
    assert SM.verify(m, "xai") == []


def test_claude_implemented_build():
    seed = SM.seed_from(99, None)
    m = SM.build(SM.KNOWN_SEATS, THREE_VENDORS, "anthropic", seed)
    for seat in SM.STRONG_TIER_SEATS:
        assert m["seats"][seat]["family"] != "anthropic"
    assert SM.verify(m, "anthropic") == []


def test_single_vendor_floor():
    m = SM.build(SM.PANEL_ROSTER, ["claude"], "xai", 0)
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
        SM.PANEL_ROSTER, THREE_VENDORS, "xai", seed, pins=pins
    )
    assert m["seats"]["code-reviewer"]["source"] == "pinned"
    assert m["seats"]["code-reviewer"]["vendor"] == "claude"


def test_pin_unhonorable_model():
    pins = {
        "code-reviewer": {
            "vendor": "cursor",
            "model": _SECOND_CODEX_MODEL,
            "effort": "high",
        },
    }
    m = SM.build(
        SM.PANEL_ROSTER, THREE_VENDORS, "xai", 0, pins=pins
    )
    pin_degs = [d for d in m["degradations"] if d["constraint"] == "pin"]
    assert any("not honorable" in d["reason"] for d in pin_degs)
    assert m["seats"]["code-reviewer"]["source"] != "pinned"


def test_pin_unknown_seat():
    pins = {"nonexistent-seat": {"vendor": "claude"}}
    m = SM.build(
        SM.PANEL_ROSTER, THREE_VENDORS, "xai", 0, pins=pins
    )
    pin_degs = [d for d in m["degradations"] if d["constraint"] == "pin"]
    assert any("unknown seat" in d["reason"] for d in pin_degs)


def test_fail_closed_empty_live_vendors():
    m = SM.build(SM.PANEL_ROSTER, [], "xai", 0)
    assert m["liveVendors"] == ["claude"]
    assert any(d["constraint"] == "live-vendors" for d in m["degradations"])


def test_fail_closed_missing_tier():
    custom_roster = ("custom-seat",)
    m = SM.build(custom_roster, THREE_VENDORS, "xai", 0)
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
                "model": "opus-5.5",
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
    m = SM.build(SM.KNOWN_SEATS, THREE_VENDORS, "openai", seed)
    strong_critical = SM.STRONG_TIER_SEATS | SM.CRITICAL_SEATS
    for seat in strong_critical:
        assert m["seats"][seat]["family"] != "openai"
    assert SM.verify(m, "openai") == []


def test_isolate_strong_seat_exclusion_with_pins():
    pins = {
        "code-reviewer": {"vendor": "claude"},
        "test-role": {"vendor": "claude"},
        "premortem-reviewer": {"vendor": "claude"},
    }
    m = SM.build(
        SM.KNOWN_SEATS, THREE_VENDORS, "anthropic", 0, pins=pins
    )
    for seat in SM.STRONG_TIER_SEATS:
        assert m["seats"][seat]["family"] != "anthropic"


def test_pinned_maker_seats_report_pin_breaks_constraint_not_author_minority():
    """A pin to a maker-family vendor cannot seat the maker: the seat is recorded unfilled and
    disclosed as pin-breaks-constraint. The numeric author-minority cap is a separate constraint
    and was not breached here.
    """
    pins = {
        "code-reviewer": {"vendor": "claude"},
        "test-role": {"vendor": "claude"},
        "premortem-reviewer": {"vendor": "claude"},
    }
    m = SM.build(
        SM.KNOWN_SEATS, THREE_VENDORS, "anthropic", 0, pins=pins
    )
    assert not any(d.get("constraint") == "author-minority" for d in m["degradations"])
    for seat in (
        "code-reviewer",
        "test-role",
        "premortem-reviewer",
    ):
        assert m["seats"][seat]["source"] == "unfilled", seat
        assert m["seats"][seat]["family"] is None, seat
        assert any(
            d.get("constraint") == "pin-breaks-constraint" and d.get("seat") == seat
            for d in m["degradations"]
        )
    for seat in SM.STRONG_TIER_SEATS:
        assert m["seats"][seat]["family"] not in (None, "anthropic"), seat
    violations = SM.verify(m, "anthropic")
    assert not any(v.get("constraint") == "maker-family" for v in violations)


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
            "model": "opus-5.5",
            "effort": "xhigh",
            "tier": "reviewer-deep",
            "family": "anthropic",
            "source": "rotated",
        },
        "test-role": {
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
    }
    base.update(overrides)
    return base


def _assert_no_unexpected_maker_family(seat_map, driver_author_family=None):
    derived = SM.derived_violations(seat_map, driver_author_family)
    assert not any(
        v.get("constraint") == "maker-family" and v.get("derived") is True
        for v in derived
    ), derived


def _seats_without_maker_collision(maker_family):
    """Template roster with no seat whose registry family equals ``maker_family``."""
    seats = _full_seats_template()
    anthropic_cfg = {
        "vendor": "claude",
        "model": "opus-5.5",
        "effort": "xhigh",
        "tier": "reviewer-deep",
        "family": "anthropic",
        "source": "rotated",
    }
    openai_cfg = {
        "vendor": "codex",
        "model": "gpt-5.6-sol",
        "effort": "xhigh",
        "tier": "reviewer-deep",
        "family": "openai",
        "source": "rotated",
    }
    overrides = {}
    if maker_family == "anthropic":
        overrides["security-reviewer"] = dict(openai_cfg)
    elif maker_family == "xai":
        for seat in ("code-reviewer", "test-role", "premortem-reviewer"):
            if SM._seat_family(seat, seats[seat]) == maker_family:
                overrides[seat] = dict(anthropic_cfg)
    elif maker_family == "openai":
        overrides["architecture-reviewer"] = dict(anthropic_cfg)
    return _full_seats_template(**overrides)


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


def test_verify_strong_tier_violation():
    seats = _full_seats_template()
    seats["security-reviewer"] = {
        "vendor": "claude",
        "model": "sonnet-5.5",
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
        "model": "opus-5.5",
        "effort": "xhigh",
        "tier": "reviewer-deep",
        "family": "anthropic",
        "source": "rotated",
    }
    seats["premortem-reviewer"] = {
        "vendor": "claude",
        "model": "opus-5.5",
        "effort": "xhigh",
        "tier": "reviewer-deep",
        "family": "anthropic",
        "source": "rotated",
    }
    seats["code-reviewer"] = {
        "vendor": "claude",
        "model": "opus-5.5",
        "effort": "xhigh",
        "tier": "reviewer-deep",
        "family": "anthropic",
        "source": "rotated",
    }
    violations = SM.verify({"seats": seats}, "xai")
    assert any(v.get("constraint") == "critical-diversity" for v in violations)


def test_verify_missing_seat():
    seats = _full_seats_template()
    del seats["test-role"]
    violations = SM.verify({"seats": seats}, "xai")
    assert any(
        v.get("constraint") == "missing-seat" and v.get("seat") == "test-role"
        for v in violations
    )


# --- LOGIC-3 backfill non-empty family ---------------------------------------------------------


def test_backfill_never_empty_family():
    for live in (THREE_VENDORS, ["claude"], ["claude", "codex"], []):
        m = SM.build(SM.PANEL_ROSTER, live, "anthropic", 0)
        for seat, cfg in m["seats"].items():
            assert cfg["family"] != "", f"seat {seat} has empty family with live={live}"
            # a seat carries a non-maker family, or is recorded unfilled with no family at all
            if cfg["source"] == "unfilled":
                assert cfg["family"] is None and cfg["vendor"] is None, (seat, live)
            else:
                assert cfg["family"] not in (None, "anthropic"), (seat, live)


# --- CLI --------------------------------------------------------------------------------------


def test_pure_functions_still_importable():
    assert callable(SM.build)
    assert callable(SM.verify)
    assert callable(SM.to_receipt)
    assert callable(SM.seed_from)
    assert callable(SM.main)


def test_cli_compose_probed_path_retains_codex_cell_through_receipt(monkeypatch, capsys):
    # axis: CLI serialization boundary — probed live_cells survives main→build→to_receipt
    import model_registry as MRG
    import preflight_probe as pp

    reviewer_deep_model, reviewer_deep_effort = MRG.matrix_config("reviewer-deep", "codex")
    aug15_cells = [
        ["codex", reviewer_deep_model, reviewer_deep_effort],
        ["cursor", "cursor-grok-4.6", "xhigh"],
    ]
    live_vendors = ["claude", "cursor"]

    def fake_live_vendors_for_composition(*_args, **_kwargs):
        return (live_vendors, aug15_cells, {}, [], "probed", {
            "servedFromCache": False,
            "probedAt": None,
            "remainingTtl": None,
        })

    monkeypatch.setattr(pp, "live_vendors_for_composition", fake_live_vendors_for_composition)

    rc = SM.main(
        [
            "x",
            "compose",
            "--configured-engines",
            "codex,cursor",
            "--author-family",
            "xai",
            "--pr-number",
            "795",
        ]
    )
    assert rc == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["liveCellsSource"] == "probed"
    assert ["codex", reviewer_deep_model, reviewer_deep_effort] in receipt["liveCells"]
    assert "codex" not in receipt["liveVendors"]
    codex_deep = [
        s
        for s in SM.PANEL_ROSTER
        if receipt["seats"][s]["vendor"] == "codex"
        and receipt["seats"][s]["model"] == reviewer_deep_model
        and receipt["seats"][s]["effort"] == reviewer_deep_effort
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
            "--pr-number",
            "510",
        ]
    )
    assert rc == 0
    receipt = json.loads(capsys.readouterr().out)
    assert len(receipt["seats"]) == len(SM.PANEL_ROSTER)
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


def _review_code_skill_and_setup_text():
    import os
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "skills", "review-code"))
    with open(os.path.join(root, "SKILL.md"), encoding="utf-8") as fh:
        skill = fh.read()
    with open(os.path.join(root, "reference", "setup.md"), encoding="utf-8") as fh:
        setup = fh.read()
    return skill, setup


def _compose_line(setup):
    compose_at = setup.index("SEAT_MAP=$(python3")
    return setup[compose_at:setup.index("\n", compose_at)]


def test_review_code_skill_composes_after_the_base_pin_and_leaves_pins_to_core_md():
    skill, setup = _review_code_skill_and_setup_text()
    compose_line = _compose_line(setup)
    assert "seat_map.py" in compose_line and " compose " in compose_line
    # compose reads seatPins from core.md itself: nothing hands it the pins from $EP
    assert "--pins" not in compose_line and "PINS_ARGS" not in compose_line
    assert "SEAT_PINS" not in skill + setup and "PINS_ARGS" not in skill + setup
    # the lane call needs the pinned base and the reviewed head, so compose runs after the base pin
    assert '--base-ref "$BASE_REF"' in compose_line and '--head-sha "$COMPOSE_HEAD"' in compose_line
    # the compose head is the commit the review diff reads: local HEAD on every path (both diff
    # "$BASE_REF"...HEAD) (#1797)
    head_pick = setup[:setup.index("SEAT_MAP=$(python3")].rsplit("\n", 3)
    head_pick = "\n".join(head_pick)
    assert 'COMPOSE_HEAD=$(git rev-parse HEAD)' in head_pick and 'COMPOSE_HEAD="$HEAD_SHA"' not in head_pick and "REVIEW_PATH" not in head_pick
    assert '--head-sha "$HEAD_SHA"' not in compose_line
    assert '--repo-root "$REPO_ROOT"' in compose_line
    # the compose block lives in setup.md under its own heading, and SKILL.md points at it right after the base pin
    assert "\n## Compose the panel seat map\n" in setup
    assert "SEAT_MAP=$(python3" not in skill
    base_pin_at = skill.index('BASE_REF=$(git rev-parse --verify --quiet "$BASE_REF^{commit}")')
    pointer_at = skill.index("reference/setup.md` § Compose the panel seat map")
    assert base_pin_at < pointer_at
    assert "$SEAT_MAP" in skill and "$AUTHOR_FAMILY" in skill


def test_review_code_skill_wires_repo_root_to_compose():
    _skill, setup = _review_code_skill_and_setup_text()
    compose_at = setup.index("SEAT_MAP=$(python3")
    compose_line = setup[compose_at:compose_at + 500]
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


def test_composer_authored_diff_excludes_cursor_from_strong_and_critical():
    """#651: a composer-made diff derives authorFamily 'xai' straight from the registry, so grok —
    now the same family — is excluded from every strong-tier and critical seat.
    Before the family merge this exclusion was vacuous: composer's family ('cursor') was one no
    reviewer cell ever produced, so grok could seat anywhere on a composer-made diff."""
    import model_registry as MRG

    author = MRG.family_for("code-fixer", "cursor")
    assert author == "xai"
    m = SM.build(SM.KNOWN_SEATS, THREE_VENDORS, author, SM.seed_from(651, None))
    for seat in sorted(SM.STRONG_TIER_SEATS | SM.CRITICAL_SEATS):
        assert m["seats"][seat]["family"] != "xai", seat
    assert SM.verify(m, author) == []


def test_cursor_only_panel_on_composer_diff_is_visibly_degraded():
    """A cursor-only panel on a composer-made diff (author family 'cursor', every seat's family
    'xai') must never read as clean. No reviewer outside the maker's family is live, so every roster
    seat is recorded `unfilled` with a `seat-unfilled` degradation, no seat carries the maker's
    family, and verify reports no maker-family violation for a seat that does not run.

    The author family is READ FROM THE REGISTRY, never hardcoded: hardcoding 'xai' would leave this
    test green if `composer-2.5`'s family ever regressed, which is the one regression it exists to
    catch."""
    import model_registry as MRG

    author = MRG.family_for("code-fixer", "cursor")
    m = SM.build(SM.PANEL_ROSTER, ["cursor"], author, SM.seed_from(651, None))
    unfilled = {
        d.get("seat") for d in m["degradations"] if d.get("constraint") == "seat-unfilled"
    }
    for seat in SM.PANEL_ROSTER:
        assert seat in unfilled, seat
        assert m["seats"][seat]["source"] == "unfilled", seat
        assert m["seats"][seat]["family"] is None, seat
    assert not any(d.get("constraint") == "same-family" for d in m["degradations"])
    assert not any(
        v.get("constraint") == "maker-family" for v in SM.verify(m, author)
    )


def test_maker_family_barred_from_test_seat():
    for seed in range(40):
        m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "openai", seed)
        assert m["seats"]["test-role"]["family"] != "openai", seed
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
            m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, author, seed)
            for seat in SM.PANEL_ROSTER:
                assert m["seats"][seat]["family"] != author, (seed, author, seat)


def test_single_vendor_collapse_is_same_family_degradation_not_violation():
    # only the maker's family is live: every seat is unfilled (a disclosed degradation), never a
    # same-family seat and never a maker-family violation
    import model_registry as MRG

    author = MRG.family_for("code-fixer", "cursor")
    m = SM.build(SM.PANEL_ROSTER, ["cursor"], author, SM.seed_from(670, None))
    for seat in SM.PANEL_ROSTER:
        assert any(
            d.get("constraint") == "seat-unfilled" and d.get("seat") == seat
            for d in m["degradations"]
        ), seat
        assert m["seats"][seat]["source"] == "unfilled", seat
    assert not any(d.get("constraint") == "same-family" for d in m["degradations"])
    assert not any(
        v.get("constraint") == "maker-family" for v in SM.verify(m, author)
    )


def test_single_vendor_collapse_does_not_claim_author_minority():
    import model_registry as MRG

    author = MRG.family_for("code-fixer", "cursor")
    m = SM.build(SM.PANEL_ROSTER, ["cursor"], author, 0)
    assert all(m["seats"][s]["source"] == "unfilled" for s in SM.PANEL_ROSTER)
    assert not any(d.get("constraint") == "author-minority" for d in m["degradations"])


def test_verify_unknown_liveness_is_a_violation():
    seats = _full_seats_template()
    seats["test-role"] = {
        "vendor": "claude",
        "model": "opus-5.5",
        "effort": "xhigh",
        "tier": "reviewer-deep",
        "family": "anthropic",
        "source": "rotated",
    }
    violations = SM.verify({"seats": seats}, "anthropic")
    assert any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-role"
        for v in violations
    )

    seats2 = _full_seats_template()
    seats2["test-role"] = dict(seats["test-role"])
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
        v.get("constraint") == "maker-family" and v.get("seat") == "test-role"
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
        "seats": {**_full_seats_template(), "test-role": seat_cfg},
        "liveVendors": ["cursor"],
        "liveCellsSource": "synthesized",
        "livenessPinScoped": True,
    }
    violations = SM.verify(sm, author)
    assert any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-role"
        for v in violations
    )

    sm["livenessPinScoped"] = False
    violations_off = SM.verify(sm, author)
    assert not any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-role"
        for v in violations_off
    )


def test_verify_malformed_liveness_is_a_violation():
    seats = _full_seats_template()
    seats["code-reviewer"] = {
        "vendor": "claude",
        "model": "opus-5.5",
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
        "seats": {**_full_seats_template(), "test-role": seat_cfg},
        "liveVendors": ["cursor"],
        "liveCellsSource": "synthesized",
        "livenessPinScoped": True,
    }
    receipt = SM.to_receipt(sm, author)
    assert receipt["livenessPinScoped"] is True
    round_trip = SM.to_receipt(receipt, author)
    assert any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-role"
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
    m = SM.build(SM.PANEL_ROSTER, ["cursor"], author, 0)
    m["authorFamily"] = author
    for _ in range(2):
        receipt = SM.to_receipt(m, author)
        counts = {}
        for d in receipt["degradations"]:
            assert d.get("constraint") != "same-family"
            if d.get("constraint") == "seat-unfilled":
                counts[d.get("seat")] = counts.get(d.get("seat"), 0) + 1
        for seat in SM.PANEL_ROSTER:
            assert counts.get(seat, 0) == 1, seat
        m = receipt


def test_pinned_maker_seat_is_still_a_violation():
    # a pin to the maker's family no longer seats it: the seat is unfilled, so there is no
    # maker-family seat for verify to flag, and the pin is disclosed as breaking the constraint
    pins = {"test-role": {"vendor": "claude"}}
    m = SM.build(
        SM.PANEL_ROSTER, THREE_VENDORS, "anthropic", 0, pins=pins
    )
    assert m["seats"]["test-role"]["source"] == "unfilled"
    assert m["seats"]["test-role"]["family"] is None
    assert any(
        d.get("constraint") == "pin-breaks-constraint" and d.get("seat") == "test-role"
        for d in m["degradations"]
    )
    violations = SM.verify(m, "anthropic")
    assert not any(v.get("constraint") == "maker-family" for v in violations)
    assert not any(v.get("seat") == "test-role" for v in violations)


def test_unexcused_maker_family_under_liveness_read_error_degradation():
    # axis: crashed liveness read examined an unknown subset — silence is not proof
    base = {
        "seats": {
            "test-role": {
                "vendor": "claude",
                "model": "opus-5.5",
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
        v.get("constraint") == "maker-family" and v.get("seat") == "test-role"
        for v in unexcused
    )


def test_build_empty_live_cells_source_fail_closed():
    # axis: falsey malformed liveCellsSource must not be laundered to synthesized
    m = SM.build(
        SM.PANEL_ROSTER,
        THREE_VENDORS,
        "xai",
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


def test_to_receipt_empty_live_cells_source_not_laundered():
    # axis: receipt minting must not upgrade unrecognized liveCellsSource to synthesized
    m = SM.build(
        SM.PANEL_ROSTER,
        THREE_VENDORS,
        "xai",
        0,
        live_cells=None,
        live_cells_source="",
    )
    receipt = SM.to_receipt(m, "xai")
    assert receipt["liveCellsSource"] == ""
    assert SM.unexcused_violations(
        {**receipt, "violations": [{"constraint": "critical-diversity"}]}
    ) == [
        {"constraint": "critical-diversity", "evidence": "unproven-liveness"},
    ]


def test_to_receipt_absent_live_cells_source_yields_synthesized():
    # axis: absent liveCellsSource legitimately resolves to synthesized at receipt minting
    bare = {"seats": {}, "liveVendors": ["claude", "codex", "cursor"]}
    receipt = SM.to_receipt(bare, "xai")
    assert receipt["liveCellsSource"] == "synthesized"


def test_legacy_cache_only_constraint_still_marks_liveness_synthesized():
    # The `preflight-cache-only` producer was reaped (#1138), but seat maps are persisted and
    # re-read, so a map written by an OLDER plugin version can still carry the constraint. It
    # must keep reading as unproven liveness — dropping the deny-list member would fall open.
    base = {
        "seats": {
            "test-role": {
                "vendor": "claude",
                "model": "opus-5.5",
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
        v.get("constraint") == "maker-family" and v.get("seat") == "test-role"
        for v in violations
    )
    without_note = dict(base)
    no_violation = SM.verify(without_note, "anthropic")
    assert not any(v.get("constraint") == "maker-family" for v in no_violation)


def test_compose_merges_probe_notes_before_deriving_the_receipt(monkeypatch, tmp_path, capsys):
    # axis: a note the preflight returns is in `degradations` BEFORE violations are derived,
    # so a fell-open panel carries its note beside the unfilled seats.
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
            {"servedFromCache": False, "probedAt": None, "remainingTtl": None},
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
            "--pr-number",
            "670",
        ]
    )
    assert rc == 0
    receipt = json.loads(capsys.readouterr().out)
    assert any(d.get("constraint") == "compose-failed" for d in receipt["degradations"])
    # the fell-open panel has only the maker's family to offer, so no seat is filled with it
    assert not any(v.get("constraint") == "maker-family" for v in receipt["violations"])
    for seat in SM.PANEL_ROSTER:
        assert receipt["seats"][seat]["source"] == "unfilled", seat
        assert any(
            d.get("constraint") == "seat-unfilled" and d.get("seat") == seat
            for d in receipt["degradations"]
        ), seat


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
    assert not maker_seats, f"unexpected maker-family: {sorted(maker_seats)}"
    for seat in SM.PANEL_ROSTER:
        assert receipt["seats"][seat]["source"] == "unfilled", seat

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
        seed,
        liveness_pin_scoped=False,
    )
    collapse_receipt = SM.to_receipt(collapse)
    for seat in SM.PANEL_ROSTER:
        assert any(
            d.get("constraint") == "seat-unfilled" and d.get("seat") == seat
            for d in collapse_receipt["degradations"]
        ), seat
    assert not any(
        d.get("constraint") == "same-family" for d in collapse_receipt["degradations"]
    )
    assert not any(
        v.get("constraint") == "maker-family" for v in collapse_receipt["violations"]
    )


def test_build_and_verify_agree_on_the_same_seat():
    pins = {"test-role": {"vendor": "claude"}}
    pin_scoped = SM.build(
        SM.PANEL_ROSTER,
        THREE_VENDORS,
        "anthropic",
        0,
        pins=pins,
        liveness_pin_scoped=True,
    )
    receipt_pin = SM.to_receipt(pin_scoped, "anthropic")
    assert not _seat_in_both_same_family_and_maker_family(receipt_pin)
    assert receipt_pin["seats"]["test-role"]["source"] == "unfilled"
    assert not any(v.get("seat") == "test-role" for v in receipt_pin["violations"])

    synthesized = SM.build(SM.PANEL_ROSTER, [], "xai", 0)
    receipt_syn = SM.to_receipt(synthesized, "xai")
    assert not _seat_in_both_same_family_and_maker_family(receipt_syn)
    assert not any(v.get("constraint") == "maker-family" for v in receipt_syn["violations"])


def test_pinned_maker_seat_does_not_claim_author_minority():
    pins = {"test-role": {"vendor": "claude"}}
    m = SM.build(
        SM.PANEL_ROSTER, THREE_VENDORS, "anthropic", 0, pins=pins
    )
    assert not any(d.get("constraint") == "author-minority" for d in m["degradations"])
    assert any(
        d.get("constraint") == "pin-breaks-constraint" and d.get("seat") == "test-role"
        for d in m["degradations"]
    )
    assert m["seats"]["test-role"]["source"] == "unfilled"
    violations = SM.verify(m, "anthropic")
    assert not any(v.get("constraint") == "maker-family" for v in violations)


def test_build_carries_liveness_pin_scoped():
    import model_registry as MRG

    author = MRG.family_for("code-fixer", "cursor")
    maker_vendor = next(
        v for v in MRG.vendors()
        if MRG.family_for("reviewer-deep", v) == author
    )
    model, effort = SM.matrix_config("reviewer-deep", maker_vendor)
    m_default = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, author, 0)
    assert m_default.get("livenessPinScoped") is False

    m_scoped = SM.build(
        SM.PANEL_ROSTER, THREE_VENDORS, author, 0, liveness_pin_scoped=True
    )
    assert m_scoped.get("livenessPinScoped") is True
    seat_cfg = {
        "vendor": maker_vendor,
        "model": model,
        "effort": effort,
        "tier": "reviewer-deep",
        "family": author,
        "source": "rotated",
    }
    m_scoped["seats"] = {**m_scoped["seats"], "test-role": seat_cfg}
    violations = SM.verify(m_scoped, author)
    assert any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-role"
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
        "seats": {**_full_seats_template(), "test-role": seat_cfg},
        "liveVendors": ["cursor"],
    }
    violations_absent = SM.verify(absent, author)
    assert any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-role"
        for v in violations_absent
    )

    explicit = {**absent, "livenessPinScoped": False, "liveCellsSource": "synthesized"}
    violations_explicit = SM.verify(explicit, author)
    assert not any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-role"
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
        "seats": {**_full_seats_template(), "test-role": seat_cfg},
        "liveVendors": ["cursor", "not-a-real-vendor"],
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
    }
    violations_mixed = SM.verify(mixed, author)
    assert any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-role"
        for v in violations_mixed
    )

    clean = {**mixed, "liveVendors": ["cursor"], "liveCellsSource": "synthesized"}
    violations_clean = SM.verify(clean, author)
    assert not any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-role"
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
        "seats": {**_full_seats_template(), "test-role": seat_cfg},
        "liveVendors": ["cursor"],
        "livenessPinScoped": True,
        "authorFamily": "stale-family",
    }
    receipt = SM.to_receipt(stale_map, author)
    assert receipt["authorFamily"] == author
    round_trip = SM.to_receipt(receipt)
    assert any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-role"
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
        "seats": {**_full_seats_template(), "test-role": seat_cfg},
        "liveVendors": ["cursor"],
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
    }
    violations = SM.verify(sm, author)
    assert any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-role"
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
    m = SM.build(SM.PANEL_ROSTER, ["claude", "codex"], "anthropic", 0)
    receipt = SM.to_receipt(m, "anthropic")
    assert any(v.get("constraint") == "critical-diversity" for v in receipt["violations"])
    assert SM.unexcused_violations(receipt) == []


def test_unexcused_critical_diversity_pinned_critical_seats_excused_by_pin():
    pins = {
        "code-reviewer": {"vendor": "claude"},
        "security-reviewer": {"vendor": "claude"},
        "premortem-reviewer": {"vendor": "claude"},
    }
    m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "xai", 0, pins=pins)
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
        "vendor": "codex",
        "model": "gpt-5.6-sol",
        "effort": "xhigh",
        "tier": "reviewer",
        "family": "openai",
        "source": "pinned",
    }
    seats["code-reviewer"] = {
        "vendor": "codex",
        "model": "gpt-5.6-sol",
        "effort": "xhigh",
        "tier": "reviewer-deep",
        "family": "openai",
        "source": "rotated",
    }
    seats["premortem-reviewer"] = {
        "vendor": "claude",
        "model": "opus-5.5",
        "effort": "xhigh",
        "tier": "reviewer-deep",
        "family": "anthropic",
        "source": "rotated",
    }
    seats["test-role"] = dict(seats["premortem-reviewer"])
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
    _assert_no_unexpected_maker_family(receipt)
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
    seats = _seats_without_maker_collision("xai")
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
        _assert_no_unexpected_maker_family(receipt)
        assert SM.unexcused_violations(receipt) == breach

    absent = dict(base)
    assert "authorFamily" not in absent
    _assert_no_unexpected_maker_family(absent)
    assert SM.unexcused_violations(absent) == breach

    xai_receipt = dict(base, authorFamily="xai")
    xai_unexcused = SM.unexcused_violations(xai_receipt)
    assert any(
        u.get("constraint") == "critical-diversity"
        and u.get("evidence") == "alternative-live"
        for u in xai_unexcused
    )


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
    seats = _seats_without_maker_collision(maker)
    receipt = {
        "seats": seats,
        "liveVendors": live,
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
        "authorFamily": maker,
        "degradations": [{"constraint": "critical-diversity"}],
        "violations": [{"constraint": "critical-diversity"}],
    }
    _assert_no_unexpected_maker_family(receipt)
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
    seats = _seats_without_maker_collision("anthropic")
    seats["architecture-reviewer"] = {
        "vendor": "codex",
        "model": "gpt-5.6-sol",
        "effort": "xhigh",
        "tier": "reviewer",
        "family": "openai",
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
    _assert_no_unexpected_maker_family(receipt)
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
        "model": "sonnet-5.5",
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
    anthropic_cfg = {
        "vendor": "claude",
        "model": "opus-5.5",
        "effort": "xhigh",
        "tier": "reviewer-deep",
        "family": "anthropic",
        "source": "rotated",
    }
    seats = _seats_without_maker_collision("xai")
    for s in SM.PANEL_ROSTER:
        seats[s] = dict(anthropic_cfg)
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
    _assert_no_unexpected_maker_family(receipt)
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
    m = SM.build(SM.PANEL_ROSTER, ["cursor"], "xai", 0, liveness_pin_scoped=False)
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
    _assert_no_unexpected_maker_family(receipt)
    unexcused = SM.unexcused_violations(receipt)
    assert {"constraint": "malformed-violation-record"} in unexcused
    assert {"constraint": "maker-family", "seat": 5} in unexcused
    # Union keyed by (constraint, seat) dedupes duplicate critical-diversity submissions.
    assert sum(1 for u in unexcused if u.get("constraint") == "critical-diversity") == 1
    assert any(u.get("constraint") == "critical-diversity" for u in unexcused)
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
        "seats": _seats_without_maker_collision("anthropic"),
        "liveVendors": list(THREE_VENDORS),
        "authorFamily": "anthropic",
        "violations": [{"constraint": "critical-diversity"}],
    }
    _assert_no_unexpected_maker_family(receipt)
    unexcused = SM.unexcused_violations(receipt)
    assert unexcused == [
        {"constraint": "critical-diversity", "evidence": "unproven-liveness"},
    ]


def test_classify_unproven_liveness_preflight_cache_only_degradation():
    # Legacy-receipt axis: no live producer since #1138; a stale map must still classify unproven.
    receipt = {
        "seats": _seats_without_maker_collision("anthropic"),
        "liveVendors": list(THREE_VENDORS),
        "livenessPinScoped": False,
        "authorFamily": "anthropic",
        "degradations": [{"constraint": "preflight-cache-only"}],
        "violations": [{"constraint": "critical-diversity"}],
    }
    _assert_no_unexpected_maker_family(receipt)
    unexcused = SM.unexcused_violations(receipt)
    assert unexcused == [
        {"constraint": "critical-diversity", "evidence": "unproven-liveness"},
    ]


def test_classify_truthy_non_list_degradations_do_not_raise():
    receipt = {
        "seats": _seats_without_maker_collision("anthropic"),
        "liveVendors": list(THREE_VENDORS),
        "livenessPinScoped": False,
        "authorFamily": "anthropic",
        "degradations": 42,
        "violations": [{"constraint": "critical-diversity"}],
    }
    _assert_no_unexpected_maker_family(receipt)
    assert SM.unexcused_violations(receipt) == [
        {"constraint": "critical-diversity", "evidence": "unproven-liveness"},
    ]


def test_classify_pin_excuses_critical_diversity_collapsed_seats():
    seats = _seats_without_maker_collision("xai")
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
    _assert_no_unexpected_maker_family(receipt)
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


# axis: probed family check resolves codex cells through codexRolePins on the seat map.
def test_resolvable_families_reads_codex_role_pin():
    seat_map = {
        "liveCellsSource": "probed",
        "liveCells": [["codex", "gpt-6-astra", "high"]],
        "degradations": [],
        "livenessPinScoped": False,
        "codexRolePins": {"reviewer-deep": "gpt-6-astra"},
    }
    cfg = {"tier": "reviewer-deep"}
    fams = SM._resolvable_families_for_seat(
        seat_map, "security-reviewer", cfg, tier="reviewer-deep",
    )
    assert "openai" in fams


@pytest.mark.parametrize(
    "bad_pins",
    [
        pytest.param(None, id="null"),
        pytest.param("x", id="non-dict"),
        pytest.param({"not-a-role": "gpt-6-astra"}, id="unknown-role"),
        pytest.param({"reviewer-deep": ""}, id="empty-value"),
        pytest.param({"reviewer-deep": 7}, id="non-string-value"),
    ],
)
def test_resolvable_families_malformed_role_pins_unusable(bad_pins):
    # axis: malformed codexRolePins makes family evidence unusable without raising
    seat_map, seat, cfg = _resolvable_families_fixture()
    seat_map["codexRolePins"] = bad_pins
    assert SM._resolvable_families_for_seat(seat_map, seat, cfg) is None


# axis: build omits codexRolePins when no pins are configured.
def test_build_records_codex_role_pins_only_when_present():
    live_cells = [
        ["codex", "gpt-5.6-sol", "xhigh"],
        ["cursor", "cursor-grok-4.6", "xhigh"],
    ]
    kwargs = dict(
        roster=SM.PANEL_ROSTER,
        live_vendors=THREE_VENDORS,
        author_family="xai",
        seed=0,
        live_cells=live_cells,
        live_cells_source="probed",
    )
    without = SM.build(**kwargs, codex_role_pins={})
    assert "codexRolePins" not in without
    with_pin = SM.build(**kwargs, codex_role_pins={"reviewer-deep": "gpt-6-astra"})
    assert with_pin["codexRolePins"] == {"reviewer-deep": "gpt-6-astra"}


def test_compose_receipt_carries_codex_role_pins(tmp_path, capsys, monkeypatch):
    # axis: compose receipt carries codexRolePins and family check reads it back
    import preflight_probe as pp

    live_vendors = ["claude", "codex", "cursor"]
    live_cells = [
        ["codex", "gpt-6-astra", "high"],
        ["cursor", "cursor-grok-4.6", "xhigh"],
    ]

    def fake_live_vendors_for_composition(*args, **kwargs):
        return (live_vendors, live_cells, {}, [], "probed", {
            "servedFromCache": False,
            "probedAt": None,
            "remainingTtl": None,
        })

    monkeypatch.setattr(pp, "live_vendors_for_composition", fake_live_vendors_for_composition)

    repo = str(tmp_path)
    _write_core_with_prefs(repo, {"codexModels": {"reviewer-deep": "gpt-6-astra"}})
    rc = SM.main(
        [
            "x",
            "compose",
            "--configured-engines",
            "claude,codex,cursor",
            "--implementation-engine",
            "cursor",
            "--host-model",
            "composer-2.5",
            "--repo-root",
            repo,
            "--pr-number",
            "1273",
        ]
    )
    assert rc == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["codexRolePins"] == {"reviewer-deep": "gpt-6-astra"}
    seat_map = dict(receipt)
    seat_map["livenessPinScoped"] = False
    cfg = {"tier": "reviewer-deep"}
    fams = SM._resolvable_families_for_seat(
        seat_map, "security-reviewer", cfg, tier="reviewer-deep",
    )
    assert "openai" in fams


def test_live_cells_sources_closed_set_membership():
    # axis: recognizer keys on the closed tuple — member changes must update this pin
    assert SM.LIVE_CELLS_SOURCES == ("probed", "synthesized", "unprobed")


def test_unexcused_critical_diversity_corrupted_live_cells_source_fail_closed():
    # axis: corrupted liveCellsSource must not excuse critical-diversity via vendor fall-through
    seats = _seats_without_maker_collision("anthropic")
    receipt = {
        "seats": seats,
        "liveVendors": ["claude"],
        "liveCellsSource": "bogus",
        "livenessPinScoped": False,
        "authorFamily": "anthropic",
        "degradations": [{"constraint": "critical-diversity"}],
        "violations": [{"constraint": "critical-diversity"}],
    }
    _assert_no_unexpected_maker_family(receipt)
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
    pins = {"code-reviewer": {"vendor": "codex", "model": _SECOND_CODEX_MODEL, "effort": "high"}}
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
        {"code-reviewer": 5, "security-reviewer": "codex", "test-role": None}
    )
    assert sorted(errors) == ["pins-invalid:code-reviewer", "pins-invalid:test-role"]
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


# axis: pin normalization does not rewrite legacy model ids at the admission boundary
def test_normalize_pins_preserves_legacy_claude_label():
    normalized, errors = SM.normalize_pins(
        {"code-reviewer": {"vendor": "claude", "model": "opus-5", "effort": "xhigh"}}
    )
    assert errors == []
    assert normalized["code-reviewer"]["model"] == "opus-5"


def test_build_string_pin_resolves_as_vendor():
    m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "xai", 0, pins={"code-reviewer": "claude"})
    assert m["seats"]["code-reviewer"]["source"] == "pinned"
    assert m["seats"]["code-reviewer"]["vendor"] == "claude"


def test_build_string_pin_is_identical_to_the_object_pin():
    shorthand = SM.build(
        SM.PANEL_ROSTER, THREE_VENDORS, "xai", 7, pins={"code-reviewer": "claude"}
    )
    longhand = SM.build(
        SM.PANEL_ROSTER, THREE_VENDORS, "xai", 7, pins={"code-reviewer": {"vendor": "claude"}}
    )
    assert shorthand == longhand


def test_build_unusable_pin_shape_degrades_instead_of_raising():
    # axis: loudness — the old behaviour was AttributeError; the new one is a named degradation
    m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "xai", 0, pins={"code-reviewer": 5})
    pin_degs = [d for d in m["degradations"] if d["constraint"] == "pin"]
    assert any(d["reason"] == "pins-invalid:code-reviewer" for d in pin_degs)
    assert m["seats"]["code-reviewer"]["source"] != "pinned"


def test_build_pin_map_that_is_not_an_object_degrades_instead_of_raising():
    m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "xai", 0, pins="claude")
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


def _aug15_reviewer_deep_cell():
    """The registry's reviewer-deep codex matrix cell (model, effort); never a re-spelled literal."""
    import model_registry as MRG

    return MRG.matrix_config("reviewer-deep", "codex")


def _aug15_live_cells():
    """2026-08-15 shape: reviewer-deep's codex matrix cell AND the pin-only fallback model live,
    the ladder's other rungs absent; cursor cells live."""
    model, effort = _aug15_reviewer_deep_cell()
    return [
        ["codex", model, effort],
        ["codex", "gpt-5.6-sol", "xhigh"],
        ["cursor", "cursor-grok-4.6", "xhigh"],
    ]


def test_dod_aug15_partial_codex_cell_live():
    """DoD row 1: lens seats keep codex at reviewer-deep when only its matrix cell is live."""
    live_vendors = ["claude", "cursor"]
    live_cells = _aug15_live_cells()
    reviewer_deep_model, reviewer_deep_effort = _aug15_reviewer_deep_cell()
    m = SM.build(
        SM.KNOWN_SEATS,
        live_vendors,
        "xai",
        SM.seed_from(795, None),
        live_cells=live_cells,
        live_cells_source="probed",
    )
    assert "codex" not in m["liveVendors"]
    codex_lens = [
        s for s in SM.LENS_SEATS
        if m["seats"][s]["vendor"] == "codex"
        and m["seats"][s]["model"] == reviewer_deep_model
        and m["seats"][s]["effort"] == reviewer_deep_effort
    ]
    assert codex_lens, "codex lost from every lens seat despite its matrix cell live"
    for seat in SM.LENS_SEATS:
        pinned = SM.build(
            SM.KNOWN_SEATS,
            live_vendors,
            "xai",
            0,
            pins={seat: {"vendor": "codex"}},
            live_cells=live_cells,
            live_cells_source="probed",
        )
        cfg = pinned["seats"][seat]
        assert cfg["source"] == "pinned", seat
        assert cfg["vendor"] == "codex", seat
        assert cfg["model"] == reviewer_deep_model, seat
        assert cfg["effort"] == reviewer_deep_effort, seat
        assert cfg["tier"] == "reviewer-deep", seat


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
        ["claude", "opus-5.5", "xhigh"],
        ["codex", "gpt-5.6-sol", "xhigh"],
        ["cursor", "cursor-grok-4.6", "xhigh"],
    ]
    m = SM.build(
        SM.PANEL_ROSTER,
        THREE_VENDORS,
        "xai",
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
    m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "xai", 0)
    assert "liveCells" in m
    assert m["liveCells"]
    receipts.append(SM.to_receipt(m))

    probed = SM.build(
        SM.PANEL_ROSTER,
        THREE_VENDORS,
        "xai",
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


# --- trusted-assert invariants (#1190 WO-1) ---------------------------------------------------


def test_inv1_no_assertion_by_omission():
    seats = _full_seats_template()
    seats["security-reviewer"] = {
        "vendor": "claude",
        "model": "sonnet-5.5",
        "effort": "high",
        "tier": "reviewer",
        "family": "anthropic",
        "source": "rotated",
    }
    seat_map = {"seats": seats, "authorFamily": "xai"}
    derived = SM.derived_violations(seat_map)
    assert any(
        v.get("constraint") == "strong-tier" and v.get("seat") == "security-reviewer"
        for v in derived
    )
    classified = SM.classify_violations(seat_map)
    assert any(
        v.get("constraint") == "strong-tier" and v.get("seat") == "security-reviewer"
        for v in classified["unexcused"]
    )


def test_inv2_monotone_union():
    # Planted constraint must be one the library cannot emit — else we measure mismatch/verify, not union.
    seats = _full_seats_template()
    seats["security-reviewer"] = {
        "vendor": "claude",
        "model": "sonnet-5.5",
        "effort": "high",
        "tier": "reviewer",
        "family": "anthropic",
        "source": "rotated",
    }
    driver = "xai"
    seat_map = {
        "seats": seats,
        "authorFamily": driver,
        "violations": [
            {"constraint": "submitter-only-breach", "seat": "code-reviewer"},
            {
                "constraint": "strong-tier",
                "seat": "security-reviewer",
                "pin": "pinned-model",
            },
        ],
    }
    derived = SM.derived_violations(seat_map, driver)
    derived_keys = {(v.get("constraint"), v.get("seat") or "") for v in derived}
    verified_keys = {
        (v.get("constraint"), v.get("seat") or "") for v in SM.verify(seat_map, driver)
    }

    assert ("submitter-only-breach", "code-reviewer") in derived_keys
    assert ("author-family-mismatch", "") not in derived_keys
    assert verified_keys <= derived_keys

    collision = next(
        v for v in derived
        if v.get("constraint") == "strong-tier" and v.get("seat") == "security-reviewer"
    )
    assert collision.get("pin") == "pinned-model"
    assert collision.get("derived") is not True


def test_inv3_canonical_families():
    seats = {
        seat: {
            "vendor": "claude",
            "model": "opus-5.5",
            "effort": "xhigh",
            "tier": "reviewer-deep",
            "family": f"invented-{i}",
            "source": "rotated",
        }
        for i, seat in enumerate(SM.PANEL_ROSTER)
    }
    seat_map = {"seats": seats, "authorFamily": "xai"}
    derived = SM.derived_violations(seat_map)
    assert any(v.get("constraint") == "critical-diversity" for v in derived)


@pytest.mark.parametrize(
    "seat,vendor,tier,expected",
    [
        ("code-reviewer", "claude", "reviewer-deep", "anthropic"),
        ("code-reviewer", "codex", "reviewer-deep", "openai"),
        ("code-reviewer", "cursor", "reviewer-deep", "xai"),
        ("code-reviewer", "claude", None, "anthropic"),
        ("code-reviewer", "nosuchvendor", "reviewer", None),
        ("code-reviewer", 42, "reviewer-deep", None),
    ],
)
def test_inv3_seat_family_unit_table(seat, vendor, tier, expected):
    cfg = {"vendor": vendor}
    if tier is not None:
        cfg["tier"] = tier
    assert SM._seat_family(seat, cfg) == expected


_INV4_HOSTILE_SHAPES = [
    {},
    {"seats": None},
    {"seats": []},
    {"seats": {"code-reviewer": "claude"}},
    {"seats": {"code-reviewer": 7}},
    {"seats": {"security-reviewer": 7}},
    {"violations": "nope"},
    {"violations": [None, 3, {}, {"constraint": ""}]},
    {"seats": {"code-reviewer": {"vendor": "nosuchvendor"}}},
]


@pytest.mark.parametrize("shape", _INV4_HOSTILE_SHAPES)
def test_inv4_totality_no_raise(shape):
    SM.verify(shape, None)
    SM.verify(shape, "")
    SM.classify_violations(shape)
    SM.unexcused_violations(shape)
    SM.derived_violations(shape)
    SM.effective_author_family(shape)
    SM.violation_basis(shape)


def test_inv5_derived_undeclared_is_unexcusable():
    seats = _full_seats_template()
    seats["architecture-reviewer"] = {
        "vendor": "claude",
        "model": "sonnet-5.5",
        "effort": "high",
        "tier": "reviewer",
        "family": "anthropic",
        "source": "pinned",
    }
    seat_map = {
        "seats": seats,
        "liveVendors": list(THREE_VENDORS),
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
        "authorFamily": "xai",
    }
    classified = SM.classify_violations(seat_map)
    assert any(
        v.get("constraint") == "strong-tier" and v.get("seat") == "architecture-reviewer"
        for v in classified["unexcused"]
    )
    assert not any(
        v.get("constraint") == "strong-tier" and v.get("seat") == "architecture-reviewer"
        for v in classified["excusedByPin"]
    )

    declared = dict(seat_map)
    declared["violations"] = [
        {"constraint": "strong-tier", "seat": "architecture-reviewer"},
    ]
    classified_declared = SM.classify_violations(declared)
    assert any(
        v.get("constraint") == "strong-tier" and v.get("seat") == "architecture-reviewer"
        for v in classified_declared["excusedByPin"]
    )


@pytest.mark.parametrize("seed", [0, 1, 42])
@pytest.mark.parametrize("live_vendors", [THREE_VENDORS, ["claude"], ["claude", "codex"]])
def test_build_roundtrip_honest_maps_do_not_move(seed, live_vendors):
    author = "xai"
    m = SM.build(SM.PANEL_ROSTER, live_vendors, author, seed)
    for seat, cfg in m["seats"].items():
        assert cfg.get("family") == SM._seat_family(seat, cfg)
    receipt = SM.to_receipt(m, author)
    assert SM.derived_violations(receipt) == SM.verify(m, author)
    assert SM.violation_basis(receipt, author) == SM.VIOLATION_BASIS_COMPLETE


# --- trusted-assert invariants (#1190 WO-2a) ---------------------------------------------------


def test_inv6_derived_violations_no_seat_basis():
    assert SM.derived_violations({}) == []
    assert SM.derived_violations({"seats": None}) == []
    assert SM.derived_violations({"seats": []}) == []
    assert SM.derived_violations({"seats": {}}) == []
    submitted = {
        "seats": {},
        "violations": [{"constraint": "critical-diversity"}],
    }
    assert SM.derived_violations(submitted) == [{"constraint": "critical-diversity"}]
    compose_failed = {
        "seats": {},
        "degradations": [
            {
                "constraint": "compose-failed",
                "reason": "seat_map compose failed — every seat falls open to Claude",
            },
        ],
    }
    assert SM.derived_violations(compose_failed) == []


def test_inv7_effective_author_family_in_classify():
    seats = _seats_without_maker_collision("anthropic")
    base = {
        "seats": seats,
        "liveVendors": list(THREE_VENDORS),
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
        "violations": [{"constraint": "critical-diversity"}],
    }
    with_driver = SM.classify_violations(base, "anthropic")
    with_map = SM.classify_violations({**base, "authorFamily": "anthropic"})
    assert with_driver == with_map


def test_author_family_mismatch_derived_unexcused():
    seat_map = {
        "seats": _full_seats_template(),
        "authorFamily": "xai",
    }
    derived = SM.derived_violations(seat_map, "anthropic")
    mismatch = next(v for v in derived if v.get("constraint") == "author-family-mismatch")
    assert mismatch.get("derived") is True
    classified = SM.classify_violations(seat_map, "anthropic")
    assert any(
        v.get("constraint") == "author-family-mismatch" for v in classified["unexcused"]
    )
    assert not any(
        v.get("constraint") == "author-family-mismatch" for v in classified["excusedByPin"]
    )
    assert not any(
        v.get("constraint") == "author-family-mismatch" for v in classified["excusedByLiveness"]
    )


# --- trusted-assert invariants (#1190 WO-R1) ---------------------------------------------------


def _all_claude_roster_seats():
    """Every roster seat on claude (anthropic family) — the measured INV-16/A case substrate."""
    anthropic_cfg = {
        "vendor": "claude",
        "model": "opus-5.5",
        "effort": "xhigh",
        "tier": "reviewer-deep",
        "family": "anthropic",
        "source": "rotated",
    }
    seats = {}
    for seat in SM.PANEL_ROSTER:
        seats[seat] = dict(anthropic_cfg)
    return seats


def test_to_receipt_malformed_codex_role_pins_cannot_excuse_critical_diversity():
    # axis: malformed codexRolePins survives receipt round-trip and cannot launder violations
    seat_map = {
        "seats": _all_claude_roster_seats(),
        "authorFamily": "xai",
        "liveVendors": list(THREE_VENDORS),
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
        "codexRolePins": {"bad-role": "gpt-6-astra"},
    }
    before = SM.classify_violations(seat_map, "xai")
    assert any(
        v.get("constraint") == "critical-diversity" for v in before["unexcused"]
    )
    receipt = SM.to_receipt(seat_map, "xai")
    assert receipt["codexRolePins"] == {"bad-role": "gpt-6-astra"}
    after = SM.classify_violations(receipt, "xai")
    assert any(
        v.get("constraint") == "critical-diversity" for v in after["unexcused"]
    )
    assert not after["excusedByLiveness"]


def test_inv16_a_self_asserted_author_family_basis():
    seat_map = {
        "seats": _all_claude_roster_seats(),
        "authorFamily": "xai",
        "liveVendors": list(THREE_VENDORS),
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
    }
    assert SM.violation_basis(seat_map, None) == SM.VIOLATION_BASIS_SELF_ASSERTED_AUTHOR_FAMILY


def test_inv16_a_driver_family_yields_complete_basis():
    seat_map = {
        "seats": _all_claude_roster_seats(),
        "authorFamily": "xai",
        "liveVendors": list(THREE_VENDORS),
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
    }
    assert SM.violation_basis(seat_map, "anthropic") == SM.VIOLATION_BASIS_COMPLETE


def test_inv16_a_no_author_family_basis():
    seat_map = {
        "seats": _all_claude_roster_seats(),
        "liveVendors": list(THREE_VENDORS),
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
    }
    assert SM.violation_basis(seat_map, None) == SM.VIOLATION_BASIS_NO_AUTHOR_FAMILY


@pytest.mark.parametrize("seat", ["test-role"])
def test_inv16_c_unresolvable_vendor_violation_unexcused(seat):
    seats = _full_seats_template()
    seats[seat] = {
        "vendor": "nosuchvendor",
        "model": "opus-5.5",
        "effort": "xhigh",
        "tier": "reviewer-deep",
        "family": "anthropic",
        "source": "rotated",
    }
    seat_map = {
        "seats": seats,
        "liveVendors": list(THREE_VENDORS),
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
        "authorFamily": "anthropic",
    }
    violations = SM.verify(seat_map, "anthropic")
    assert any(
        v.get("constraint") == "unresolvable-seat-vendor" and v.get("seat") == seat
        for v in violations
    )
    classified = SM.classify_violations(seat_map, "anthropic")
    assert any(
        v.get("constraint") == "unresolvable-seat-vendor" and v.get("seat") == seat
        for v in classified["unexcused"]
    )


def test_inv16_d_same_family_when_canonical_matches_maker_but_declared_differs():
    seats = _full_seats_template()
    for seat in SM.PANEL_ROSTER:
        seats[seat] = {
            "vendor": "cursor",
            "model": "cursor-grok-4.6",
            "effort": "xhigh",
            "tier": "reviewer-deep",
            "family": "openai",
            "source": "rotated",
        }
    seat_map = {
        "seats": seats,
        "liveVendors": ["cursor"],
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
    }
    author = "xai"
    degradations = SM.same_family_degradations(seat_map, author)
    for seat in SM.PANEL_ROSTER:
        assert any(
            d.get("constraint") == "same-family" and d.get("seat") == seat
            for d in degradations
        ), seat


def test_inv16_d_no_same_family_when_canonical_not_maker():
    seats = _full_seats_template()
    for seat in SM.PANEL_ROSTER:
        seats[seat] = {
            "vendor": "codex",
            "model": "gpt-5.6-sol",
            "effort": "xhigh",
            "tier": "reviewer-deep",
            "family": "anthropic",
            "source": "rotated",
        }
    seat_map = {
        "seats": seats,
        "liveVendors": list(THREE_VENDORS),
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
    }
    assert SM.same_family_degradations(seat_map, "xai") == []


def test_inv16_self_asserted_basis_reaches_unjudgeable_receipts():
    import seat_map_receipts as smr

    seat_map = {
        "seats": _all_claude_roster_seats(),
        "authorFamily": "xai",
    }
    state = {
        "seatMapReceipts": [{"round": "1", "map": seat_map}],
    }
    result = smr.unjudgeable_receipts(state, None)
    assert result == [{"round": "1", "basis": SM.VIOLATION_BASIS_SELF_ASSERTED_AUTHOR_FAMILY}]


def _assert_side_family_read_offenders():
    """Return function names outside ``build()`` that read submitted ``family`` via get/subscript."""
    import ast

    with open(_MOD, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=_MOD)
    offenders = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name == "build":
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                func = child.func
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "get"
                    and child.args
                    and isinstance(child.args[0], ast.Constant)
                    and child.args[0].value == "family"
                ):
                    offenders.append(node.name)
                    break
            elif isinstance(child, ast.Subscript):
                sl = child.slice
                if isinstance(sl, ast.Constant) and sl.value == "family":
                    offenders.append(node.name)
                    break
    return offenders


def test_assert_side_no_cfg_family_reads_outside_build():
    offenders = _assert_side_family_read_offenders()
    assert offenders == [], (
        "assert-side family read outside build() in: %s"
        % ", ".join(sorted(set(offenders)))
    )


def _pinned_critical_seats_without_family(seats):
    pin_anthropic = {
        "vendor": "claude",
        "model": "opus-5.5",
        "effort": "xhigh",
        "tier": "reviewer-deep",
        "source": "pinned",
    }
    pin_openai = {
        "vendor": "codex",
        "model": "gpt-5.6-sol",
        "effort": "xhigh",
        "tier": "reviewer-deep",
        "source": "pinned",
    }
    seats["code-reviewer"] = dict(pin_anthropic)
    seats["security-reviewer"] = dict(pin_anthropic)
    seats["premortem-reviewer"] = dict(pin_openai)
    return seats


def test_critical_diversity_pinned_omitted_family_not_excused_by_pin():
    seats = _pinned_critical_seats_without_family(_full_seats_template())
    receipt = {
        "seats": seats,
        "liveVendors": list(THREE_VENDORS),
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
        "authorFamily": "xai",
        "violations": [{"constraint": "critical-diversity"}],
    }
    classified = SM.classify_violations(receipt, "xai")
    unexcused = [v.get("constraint") for v in classified["unexcused"]]
    excused_pin = [v.get("constraint") for v in classified["excusedByPin"]]
    assert "critical-diversity" in unexcused
    assert "critical-diversity" not in excused_pin


def test_critical_diversity_pinned_with_family_still_excused_by_pin():
    seats = _full_seats_template()
    for seat in SM.CRITICAL_SEATS:
        cfg = dict(seats[seat])
        cfg["source"] = "pinned"
        cfg["vendor"] = "claude"
        cfg["family"] = "anthropic"
        seats[seat] = cfg
    receipt = {
        "seats": seats,
        "liveVendors": list(THREE_VENDORS),
        "liveCellsSource": "synthesized",
        "livenessPinScoped": False,
        "authorFamily": "xai",
        "violations": [{"constraint": "critical-diversity"}],
    }
    classified = SM.classify_violations(receipt, "xai")
    assert "critical-diversity" not in [
        v.get("constraint") for v in classified["unexcused"]
    ]
    assert "critical-diversity" in [
        v.get("constraint") for v in classified["excusedByPin"]
    ]


def _collect_backfill_tier_literals_from_source(source=None):
    """AST walk of nested ``_backfill`` — whitelist census of every tier-recording site.

    Collects every ``for`` rotation, every ``[\"tier\"]`` assignment, and every returned
    ``tier`` value. Unresolvable constructs are ``undecidable`` and fail the census test.
    """
    import ast

    if source is None:
        with open(_MOD, encoding="utf-8") as fh:
            source = fh.read()
    tree = ast.parse(source, filename=_MOD)

    module_string_constants: dict[str, str] = {}
    parametric_tier_values = set(SM.DEFAULT_TIER_BY_SEAT.values()) | {"reviewer"}

    def _string_constant(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name) and node.id in module_string_constants:
            return module_string_constants[node.id]
        return None

    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                val = _string_constant(node.value)
                if val is not None:
                    module_string_constants[target.id] = val

    def _strings_from_iterable(node, *, site):
        if isinstance(node, (ast.Tuple, ast.List)):
            out = []
            for idx, elt in enumerate(node.elts):
                val = _string_constant(elt)
                if val is None:
                    return None, "%s[%d]" % (site, idx)
                out.append(val)
            return out, None
        if isinstance(node, ast.Name):
            if node.id == "_BACKFILL_CLAUDE_ROTATION":
                out = []
                for name in ("STRONG_TIER_REQUIRED", "_BACKFILL_DOWNGRADE_TO"):
                    val = module_string_constants.get(name)
                    if val is None:
                        return None, "%s (missing %s)" % (site, name)
                    out.append(val)
                return out, None
            val = _string_constant(node)
            if val is not None:
                return [val], None
            return None, "%s (name %r)" % (site, node.id)
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "_backfill_rotation_tiers":
                downgrade = module_string_constants.get("_BACKFILL_DOWNGRADE_TO")
                if downgrade is None:
                    return None, "%s (_BACKFILL_DOWNGRADE_TO unresolved)" % site
                return sorted(parametric_tier_values | {downgrade}), None
        seg = ast.get_source_segment(source, node) or type(node).__name__
        return None, "%s (%s)" % (site, seg)

    def _subscript_tier_key(target):
        if not isinstance(target, ast.Subscript):
            return False
        sl = target.slice
        return isinstance(sl, ast.Constant) and sl.value == "tier"

    def _resolve_tier_value(node, *, site, loop_tier_sources):
        lit = _string_constant(node)
        if lit is not None:
            return [lit], None
        if isinstance(node, ast.Name):
            if node.id == "tier":
                return sorted(parametric_tier_values), None
            if node.id in loop_tier_sources:
                return loop_tier_sources[node.id], None
            return None, "%s (name %r)" % (site, node.id)
        seg = ast.get_source_segment(source, node) or type(node).__name__
        return None, "%s (%s)" % (site, seg)

    build_fn = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "build"
    )
    backfill_fn = next(
        n for n in ast.walk(build_fn)
        if isinstance(n, ast.FunctionDef) and n.name == "_backfill"
    )

    def _loop_var_records_tier(for_node, var_name):
        for child in ast.walk(for_node):
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if _subscript_tier_key(target):
                        if isinstance(child.value, ast.Name) and child.value.id == var_name:
                            return True
            if isinstance(child, ast.Return) and isinstance(child.value, ast.Dict):
                for key, val in zip(child.value.keys, child.value.values):
                    if isinstance(key, ast.Constant) and key.value == "tier":
                        if isinstance(val, ast.Name) and val.id == var_name:
                            return True
        return False

    loop_tier_sources: dict[str, list[str]] = {}
    collected: set[str] = set()
    undecidable: list[str] = []
    for node in ast.walk(backfill_fn):
        if isinstance(node, ast.For) and isinstance(node.target, ast.Name):
            site = "for %s in" % node.target.id
            tiers, bad = _strings_from_iterable(node.iter, site=site)
            if tiers is not None:
                collected.update(tiers)
                loop_tier_sources[node.target.id] = tiers
            elif _loop_var_records_tier(node, node.target.id):
                undecidable.append(bad)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if _subscript_tier_key(target):
                    tiers, bad = _resolve_tier_value(
                        node.value, site="assign tier", loop_tier_sources=loop_tier_sources,
                    )
                    if bad is not None:
                        undecidable.append(bad)
                    else:
                        collected.update(tiers)
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            for key, val in zip(node.value.keys, node.value.values):
                if isinstance(key, ast.Constant) and key.value == "tier":
                    tiers, bad = _resolve_tier_value(
                        val, site="return tier", loop_tier_sources=loop_tier_sources,
                    )
                    if bad is not None:
                        undecidable.append(bad)
                    else:
                        collected.update(tiers)

    return collected, undecidable


def test_sm6_1269_backfill_tier_census_rejects_planted_shapes():
    """Prove whitelist default-deny: shapes that evaded the old blacklist must fail."""
    planted_rotation = (
        "def build():\n"
        "    def _backfill(seat):\n"
        "        for alt_tier in (\"reviewer-lite\", \"reviewer\"):\n"
        "            return {\"tier\": alt_tier}\n"
        "        return {\"tier\": \"reviewer\"}\n"
    )
    rotation_tiers, rotation_undecidable = _collect_backfill_tier_literals_from_source(
        planted_rotation,
    )
    assert "reviewer-lite" in rotation_tiers
    assert SM.accepted_tiers_for_seat("code-reviewer") != frozenset(rotation_tiers)

    planted_assign = (
        "def build():\n"
        "    def _backfill(seat):\n"
        "        cfg = {}\n"
        "        cfg[\"tier\"] = \"reviewer-lite\"\n"
        "        return cfg\n"
    )
    assign_tiers, assign_undecidable = _collect_backfill_tier_literals_from_source(
        planted_assign,
    )
    assert "reviewer-lite" in assign_tiers
    assert not assign_undecidable
    assert SM.accepted_tiers_for_seat("code-reviewer") != frozenset(assign_tiers)


def test_sm4_1269_backfill_tier_census_matches_accepted_tiers():
    """AST census: accepted tiers equal tiers ``_backfill`` can assign — no hand-maintained list.

    If a third rotation is added to ``_backfill`` tomorrow, this test fails without updating it.
    """
    walk_tiers, undecidable = _collect_backfill_tier_literals_from_source()
    assert not undecidable, "undecidable tier constructs in _backfill: %s" % undecidable
    for seat in SM.PANEL_ROSTER:
        accepted = SM.accepted_tiers_for_seat(seat)
        assert accepted == walk_tiers, (
            "accepted_tiers_for_seat(%r)=%s != AST walk %s"
            % (seat, sorted(accepted), sorted(walk_tiers))
        )
        assert not accepted - walk_tiers
        assert not walk_tiers - accepted


def test_accepted_tiers_for_seat_matches_default_override_and_backfill():
    # axis: accepted tier set derives from default, override channel, and backfill rotation
    assert SM.accepted_tiers_for_seat("security-reviewer") == frozenset(
        {"reviewer-deep", "reviewer"},
    )
    assert SM.accepted_tiers_for_seat("not-a-panel-seat") == frozenset(
        {"reviewer-deep", "reviewer"},
    )
    assert SM.accepted_tiers_for_seat(
        "code-reviewer", tier_by_seat={"code-reviewer": "reviewer"},
    ) == frozenset({"reviewer-deep", "reviewer"})


# --- codex role pins + host-model families (#1273 WO-B) -------------------------------------


def _write_core_with_prefs(repo, prefs):
    import importlib.util as _u
    spec = _u.spec_from_file_location("core_md", os.path.join(_LIB, "core_md.py"))
    cm = _u.module_from_spec(spec)
    spec.loader.exec_module(cm)
    cm.write(
        repo,
        {
            "verifyCommand": "npm test",
            "stackTags": [],
            "threatModel": "x",
            "patterns": "",
            "enginePreferences": prefs,
        },
        "confirmed",
        now="2026-06-30",
    )


def test_codex_role_pin_sol_seats_deep_at_xhigh():
    live_cells = [
        ["codex", "gpt-5.6-sol", "xhigh"],
        ["cursor", "cursor-grok-4.6", "xhigh"],
    ]
    m = SM.build(
        SM.KNOWN_SEATS,
        ["claude", "cursor"],
        "xai",
        0,
        codex_role_pins={"reviewer-deep": "gpt-5.6-sol"},
        live_cells=live_cells,
        live_cells_source="probed",
    )
    codex_deep = [
        m["seats"][s]
        for s in SM.LENS_SEATS
        if m["seats"][s]["vendor"] == "codex" and m["seats"][s]["tier"] == "reviewer-deep"
    ]
    assert codex_deep
    for cfg in codex_deep:
        assert cfg["model"] == "gpt-5.6-sol"
        assert cfg["effort"] == "xhigh"
        assert cfg["source"] == "role-pinned"


# axis: registered gpt-6-astra role-pin seats reviewer-deep at high effort from live cells.
def test_codex_role_pin_astra_registered_seats_at_high():
    live_cells = [
        ["codex", "gpt-6-astra", "high"],
        ["cursor", "cursor-grok-4.6", "xhigh"],
    ]
    m = SM.build(
        SM.KNOWN_SEATS,
        ["claude", "cursor"],
        "xai",
        0,
        codex_role_pins={"reviewer-deep": "gpt-6-astra"},
        live_cells=live_cells,
        live_cells_source="probed",
    )
    codex_deep = [
        m["seats"][s]
        for s in SM.LENS_SEATS
        if m["seats"][s]["vendor"] == "codex" and m["seats"][s]["tier"] == "reviewer-deep"
    ]
    assert codex_deep
    for cfg in codex_deep:
        assert cfg["model"] == "gpt-6-astra"
        assert cfg["effort"] == "high"
        assert cfg["source"] == "role-pinned"


# axis: a maker-family pin leaves its seat unfilled whether or not a codex role pin is live.
def test_verify_maker_family_with_unavailable_role_pin_and_live_matrix_cell():
    reviewer_deep_model, reviewer_deep_effort = _aug15_reviewer_deep_cell()
    kw = dict(
        roster=SM.PANEL_ROSTER,
        live_vendors=["claude", "codex"],
        author_family="anthropic",
        seed=0,
        pins={
            "code-reviewer": {"vendor": "claude"},
            "test-role": {"vendor": "claude"},
        },
        live_cells=[["codex", reviewer_deep_model, reviewer_deep_effort]],
        live_cells_source="probed",
    )
    without_pin = SM.build(**kw)
    with_pin = SM.build(**kw, codex_role_pins={"reviewer-deep": "gpt-6-astra"})
    # the claude pins name the maker's family, so those seats are unfilled with or without a role pin
    for built in (without_pin, with_pin):
        assert not any(
            v.get("constraint") == "maker-family" for v in SM.verify(built, "anthropic")
        )
        for seat in ("code-reviewer", "test-role"):
            assert built["seats"][seat]["source"] == "unfilled", seat


# axis: registered gpt-6-astra role-pin falls back to matrix when Astra is not in live cells.
def test_codex_role_pin_astra_not_live_falls_back_to_matrix():
    reviewer_deep_model, reviewer_deep_effort = _aug15_reviewer_deep_cell()
    live_cells = [
        ["codex", reviewer_deep_model, reviewer_deep_effort],
        ["cursor", "cursor-grok-4.6", "xhigh"],
    ]
    m = SM.build(
        SM.KNOWN_SEATS,
        ["claude", "cursor"],
        "xai",
        0,
        codex_role_pins={"reviewer-deep": "gpt-6-astra"},
        live_cells=live_cells,
        live_cells_source="probed",
    )
    matrix_model, matrix_effort, _ = SM._cell("reviewer-deep", "codex", None)
    for seat in SM.STRONG_TIER_SEATS:
        cfg = m["seats"][seat]
        if cfg["vendor"] == "codex":
            assert cfg["model"] == matrix_model
            assert cfg["effort"] == matrix_effort
            assert cfg["source"] != "role-pinned"
    not_live = [d for d in m["degradations"] if d["constraint"] == "role-pin-not-live"]
    assert not_live


# bite-proof axis: a model-only one-run pin seats at its own model's effort, never the role pin's
def test_one_run_model_pin_takes_own_effort_in_build(monkeypatch):
    real_cell = SM._cell

    def fake(tier, vendor, role_pins=None):
        if (tier, vendor) == ("reviewer-deep", "codex"):
            return ("gpt-6-astra", "high", {"pin": "gpt-6-astra", "honored": True})
        return real_cell(tier, vendor, role_pins)

    monkeypatch.setattr(SM, "_cell", fake)
    live_cells = [
        ["codex", "gpt-5.6-sol", "xhigh"],
    ]
    m = SM.build(
        SM.KNOWN_SEATS,
        ["claude", "codex", "cursor"],
        "xai",
        0,
        codex_role_pins={"reviewer-deep": "gpt-6-astra"},
        pins={"architecture-reviewer": {"vendor": "codex", "model": "gpt-5.6-sol"}},
        live_cells=live_cells,
        live_cells_source="probed",
    )
    cfg = m["seats"]["architecture-reviewer"]
    assert cfg["vendor"] == "codex"
    assert cfg["model"] == "gpt-5.6-sol"
    assert cfg["effort"] == "xhigh"
    assert cfg["source"] == "pinned"
    assert not any(
        d.get("reason") == "pin architecture-reviewer not honorable — fell back to rotation"
        for d in m.get("degradations", [])
    )


# bite-proof axis: a model-only one-run pin's needed-set cell uses its own model's effort, never the role pin's
def test_one_run_model_pin_takes_own_effort_in_reachable_configs(monkeypatch):
    real_cell = SM._cell

    def fake(tier, vendor, role_pins=None):
        if (tier, vendor) == ("reviewer-deep", "codex"):
            return ("gpt-6-astra", "high", {"pin": "gpt-6-astra", "honored": True})
        return real_cell(tier, vendor, role_pins)

    monkeypatch.setattr(SM, "_cell", fake)
    result = SM.reachable_configs(
        ["codex", "cursor"],
        {"architecture-reviewer": {"vendor": "codex", "model": "gpt-5.6-sol"}},
        roster=SM.KNOWN_SEATS,
        codex_role_pins={"reviewer-deep": "gpt-6-astra"},
    )
    assert ["gpt-5.6-sol", "xhigh"] in result["codex"]
    assert ["gpt-5.6-sol", "high"] not in result["codex"]


def test_one_run_pin_explicit_effort_still_wins(monkeypatch):
    real_cell = SM._cell

    def fake(tier, vendor, role_pins=None):
        if (tier, vendor) == ("reviewer-deep", "codex"):
            return ("gpt-6-astra", "high", {"pin": "gpt-6-astra", "honored": True})
        return real_cell(tier, vendor, role_pins)

    monkeypatch.setattr(SM, "_cell", fake)
    live_cells = [
        ["codex", "gpt-5.6-sol", "xhigh"],
    ]
    m = SM.build(
        SM.KNOWN_SEATS,
        ["claude", "codex", "cursor"],
        "xai",
        0,
        codex_role_pins={"reviewer-deep": "gpt-6-astra"},
        pins={
            "architecture-reviewer": {
                "vendor": "codex",
                "model": "gpt-5.6-sol",
                "effort": "xhigh",
            }
        },
        live_cells=live_cells,
        live_cells_source="probed",
    )
    cfg = m["seats"]["architecture-reviewer"]
    assert cfg["effort"] == "xhigh"
    assert cfg["source"] == "pinned"


def test_no_codex_role_pins_byte_identical_to_default_kwarg():
    kwargs = dict(
        roster=SM.PANEL_ROSTER,
        live_vendors=THREE_VENDORS,
        author_family="xai",
        seed=SM.seed_from(510, None),
        live_cells=_aug15_live_cells(),
        live_cells_source="probed",
    )
    without = SM.build(**kwargs)
    with_none = SM.build(**kwargs, codex_role_pins=None)
    assert without == with_none


def test_reachable_configs_vendor_pinned_seat_includes_matrix_cell():
    import model_registry as MRG

    reviewer_model, reviewer_effort = MRG.matrix_config("reviewer", "codex")
    rc = SM.reachable_configs(
        ["codex"],
        {"test-role": "codex"},
        roster=("test-role",),
        tier_by_seat={"test-role": "reviewer"},
        codex_role_pins={"reviewer": "gpt-5.6-sol"},
    )
    assert [reviewer_model, reviewer_effort] in rc["codex"]


def test_reachable_configs_in_play_role_pin_tiers_include_matrix_cells():
    role_pins = {"reviewer": "gpt-5.6-sol", "reviewer-deep": "gpt-5.6-sol"}
    vendors = ["codex", "cursor"]
    in_play_tiers = {SM.DEFAULT_TIER_BY_SEAT[seat] for seat in SM.PANEL_ROSTER}
    pins = {seat: "codex" for seat in SM.PANEL_ROSTER}
    for rc in (
        SM.reachable_configs(vendors, None, codex_role_pins=role_pins),
        SM.reachable_configs(vendors, pins, codex_role_pins=role_pins),
    ):
        for tier in SM._PANEL_PIN_TIERS:
            if tier in role_pins and tier in in_play_tiers:
                model, effort, _pin = SM._cell(tier, "codex", None)
                assert [model, effort] in rc["codex"]


def test_codex_role_pin_vendor_pinned_seat_probes_matrix_fallback():
    import model_registry as MRG

    reviewer_model, reviewer_effort = MRG.matrix_config("reviewer", "codex")
    pins = {"test-role": {"vendor": "codex"}}
    needed = SM.reachable_configs(
        ["codex", "cursor"],
        pins,
        tier_by_seat={"test-role": "reviewer"},
        codex_role_pins={"reviewer": "gpt-5.6-sol"},
    )
    live_cells = [
        [vendor, model, effort]
        for vendor, cells in needed.items()
        for model, effort in cells
        if not (vendor == "codex" and model == "gpt-5.6-sol" and effort == "high")
    ]
    # anthropic is made a maker too, so codex is the one family left to seat the reviewer-tier test seat
    m = SM.build(
        ("test-role",),
        ["claude", "codex", "cursor"],
        "xai",
        0,
        pins=pins,
        tier_by_seat={"test-role": "reviewer"},
        codex_role_pins={"reviewer": "gpt-5.6-sol"},
        live_cells=live_cells,
        live_cells_source="probed",
        extra_maker_families=frozenset({"anthropic"}),
    )
    cfg = m["seats"]["test-role"]
    assert cfg["vendor"] == "codex"
    assert cfg["model"] == reviewer_model
    assert cfg["effort"] == reviewer_effort
    not_live = [d for d in m["degradations"] if d["constraint"] == "role-pin-not-live"]
    assert len(not_live) == 1
    assert not_live[0]["seat"] == "test-role"


def test_reachable_configs_includes_role_pinned_cell():
    import model_registry as MRG

    reviewer_model, reviewer_effort = MRG.matrix_config("reviewer", "codex")
    rc = SM.reachable_configs(
        ["codex", "cursor"],
        None,
        tier_by_seat={"test-role": "reviewer"},
        codex_role_pins={"reviewer": "gpt-5.6-sol"},
    )
    assert [reviewer_model, reviewer_effort] in rc["codex"]
    assert ["gpt-5.6-sol", "high"] in rc["codex"]


def test_reachable_configs_role_pinned_cell_absent_without_pin():
    rc = SM.reachable_configs(["codex", "cursor"], None)
    assert ["gpt-5.6-sol", "high"] not in rc["codex"]


def test_codex_role_pin_reviewer_not_live_seats_matrix_with_one_degradation():
    import model_registry as MRG

    reviewer_model, reviewer_effort = MRG.matrix_config("reviewer", "codex")
    live_cells = [
        ["codex", reviewer_model, reviewer_effort],
        ["cursor", "cursor-grok-4.6", "xhigh"],
    ]
    # anthropic is made a maker too, so codex is the one family left to seat the reviewer-tier test seat
    m = SM.build(
        ("test-role",),
        ["claude", "codex", "cursor"],
        "xai",
        0,
        tier_by_seat={"test-role": "reviewer"},
        codex_role_pins={"reviewer": "gpt-5.6-sol"},
        live_cells=live_cells,
        live_cells_source="probed",
        extra_maker_families=frozenset({"anthropic"}),
    )
    cfg = m["seats"]["test-role"]
    assert cfg["vendor"] == "codex"
    assert cfg["model"] == reviewer_model
    assert cfg["effort"] == reviewer_effort
    not_live = [d for d in m["degradations"] if d["constraint"] == "role-pin-not-live"]
    assert len(not_live) == 1
    assert not_live[0]["seat"] == "test-role"


def test_codex_role_pin_no_degradation_when_seat_not_on_codex():
    live_cells = [
        ["codex", _SECOND_CODEX_MODEL, "high"],
        ["cursor", "cursor-grok-4.6", "xhigh"],
    ]
    # openai is made a maker too, so the reviewer-tier test seat cannot land on codex
    m = SM.build(
        ("test-role",),
        ["claude", "codex", "cursor"],
        "xai",
        0,
        tier_by_seat={"test-role": "reviewer"},
        codex_role_pins={"reviewer": "gpt-5.6-sol"},
        live_cells=live_cells,
        live_cells_source="probed",
        extra_maker_families=frozenset({"openai"}),
    )
    cfg = m["seats"]["test-role"]
    assert cfg["vendor"] != "codex"
    pin_degs = [
        d for d in m["degradations"]
        if d.get("constraint") in ("role-pin-not-live", "role-pin-not-honorable")
        and d.get("seat") == "test-role"
    ]
    assert pin_degs == []


def _matrix_config_offenders(source: str) -> list[int]:
    import ast
    tree = ast.parse(source)
    cell_nodes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_cell":
            cell_nodes.append(node)
    assert len(cell_nodes) == 1
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_matrix_config = (
            isinstance(func, ast.Name) and func.id == "matrix_config"
        ) or (
            isinstance(func, ast.Attribute) and func.attr == "matrix_config"
        )
        if is_matrix_config:
            if not any(node in ast.walk(cn) for cn in cell_nodes):
                offenders.append(node.lineno)
    return offenders


def test_matrix_config_calls_only_inside_cell():
    with open(_MOD, encoding="utf-8") as fh:
        source = fh.read()
    assert _matrix_config_offenders(source) == []


def test_matrix_config_offenders_detects_outside_bare_and_qualified():
    source = """\
def _cell():
    matrix_config("reviewer", "codex")

def outside():
    matrix_config("reviewer", "claude")
    model_registry.matrix_config("reviewer", "codex")
"""
    assert _matrix_config_offenders(source) == [5, 6]


def test_cli_compose_host_model_known(capsys):
    rc = SM.main(
        [
            "x",
            "compose",
            "--live-vendors",
            "claude,codex,cursor",
            "--implementation-engine",
            "cursor",
            "--host-model",
            "claude-opus-5",
            "--pr-number",
            "1273",
        ]
    )
    assert rc == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["authorFamily"] == "xai"


def test_cli_compose_host_model_unknown_degrades(capsys):
    rc = SM.main(
        [
            "x",
            "compose",
            "--live-vendors",
            "claude,codex,cursor",
            "--implementation-engine",
            "claude",
            "--host-model",
            "",
            "--pr-number",
            "1273",
        ]
    )
    assert rc == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["authorFamily"] == "anthropic"
    host_unknown = [
        d for d in receipt["degradations"] if d["constraint"] == "host-model-unknown"
    ]
    assert len(host_unknown) == 1
    assert "claude" in host_unknown[0]["reason"]
    assert "the claude implementation engine's (anthropic)" in host_unknown[0]["reason"]
    assert all(
        seat_cfg.get("family") != "anthropic"
        for seat_cfg in receipt["seats"].values()
    )


def test_cli_compose_host_model_unknown_cursor_impl_degrades(capsys):
    rc = SM.main(
        [
            "x",
            "compose",
            "--live-vendors",
            "claude,codex,cursor",
            "--implementation-engine",
            "cursor",
            "--host-model",
            "",
            "--pr-number",
            "1273",
        ]
    )
    assert rc == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["authorFamily"] == "xai"
    host_unknown = [
        d for d in receipt["degradations"] if d["constraint"] == "host-model-unknown"
    ]
    assert len(host_unknown) == 1
    assert "cursor" in host_unknown[0]["reason"]
    assert all(cfg.get("family") != "xai" for cfg in receipt["seats"].values())


def test_host_family_bracket_suffix():
    import model_registry as MR
    assert MR.host_family("claude-opus-5[1m]") == "anthropic"


def test_panel_pin_tiers_derived_from_registry():
    import model_registry as MR
    # `reviewer` joins through the backfill downgrade tier: no seat defaults to it any more
    derived = frozenset(MR.codex_pin_roles()) & (
        frozenset(SM.DEFAULT_TIER_BY_SEAT.values()) | {SM._BACKFILL_DOWNGRADE_TO}
    )
    assert derived == {"reviewer", "reviewer-deep"}
    assert SM._PANEL_PIN_TIERS == derived
    assert SM.panel_pin_tiers() == derived


def test_compose_role_pin_without_seat_pins_liveness_not_scoped(tmp_path, capsys, monkeypatch):
    import preflight_probe as pp

    live_vendors = ["claude", "codex", "cursor"]
    live_cells = [
        ["claude", "claude-opus-5", "high"],
        ["codex", "gpt-5.6-sol", "high"],
        ["cursor", "composer-2.5", "high"],
    ]
    probe_calls: list[tuple] = []

    def fake_live_vendors_for_composition(*args, **kwargs):
        probe_calls.append((args, kwargs))
        return (live_vendors, live_cells, {}, [], "probed", {
            "servedFromCache": False,
            "probedAt": None,
            "remainingTtl": None,
        })

    monkeypatch.setattr(pp, "live_vendors_for_composition", fake_live_vendors_for_composition)

    repo = str(tmp_path)
    _write_core_with_prefs(repo, {"codexModels": {"reviewer": "gpt-5.6-sol"}})
    rc = SM.main(
        [
            "x",
            "compose",
            "--configured-engines",
            "claude,codex,cursor",
            "--implementation-engine",
            "cursor",
            "--host-model",
            "composer-2.5",
            "--repo-root",
            repo,
            "--pr-number",
            "1273",
        ]
    )
    assert rc == 0
    receipt = json.loads(capsys.readouterr().out)
    assert probe_calls
    _, kwargs = probe_calls[0]
    assert kwargs["needed_override"] is not None
    assert ["gpt-5.6-sol", "high"] in kwargs["needed_override"]["codex"]
    assert receipt["livenessPinScoped"] is False


def test_compose_role_pin_not_on_allowlist_refused_with_named_reason(tmp_path, capsys, monkeypatch):
    # Every currently-registered non-retired codex model that is pin-eligible for reviewer-deep
    # is also on its allowlist, so a real off-allowlist pin can no longer be constructed from
    # registry data alone (#1435 WO-2b registry rewrite). Force `resolve_dispatch` not-ok for
    # ONE otherwise-eligible pin (gpt-6-astra, whose pin_roles already include reviewer-deep) so
    # the seat map's own "pin resolved but not on the tier's allowlist" path still gets proven —
    # everything else still resolves through the real registry.
    import model_registry as MRG

    real_resolve_dispatch = MRG.resolve_dispatch

    def _fake_resolve_dispatch(role, vendor, model, effort):
        if role == "reviewer-deep" and vendor == "codex" and model == "gpt-6-astra":
            return {"ok": False, "reason": "forced-off-allowlist-for-test"}
        return real_resolve_dispatch(role, vendor, model, effort)

    monkeypatch.setattr(MRG, "resolve_dispatch", _fake_resolve_dispatch)

    repo = str(tmp_path)
    _write_core_with_prefs(repo, {"codexModels": {"reviewer-deep": "gpt-6-astra"}})
    rc = SM.main(
        [
            "x",
            "compose",
            "--live-vendors",
            "claude,codex,cursor",
            "--implementation-engine",
            "cursor",
            "--host-model",
            "composer-2.5",
            "--repo-root",
            repo,
            "--pr-number",
            "1273",
        ]
    )
    assert rc == 0
    receipt = json.loads(capsys.readouterr().out)
    honorable = [
        d for d in receipt["degradations"] if d["constraint"] == "role-pin-not-honorable"
    ]
    assert len(honorable) == 1
    assert honorable[0]["reason"].startswith("pin-not-on-allowlist:")
    for seat_cfg in receipt["seats"].values():
        if isinstance(seat_cfg, dict) and seat_cfg.get("vendor") == "codex":
            assert seat_cfg.get("model") != "gpt-6-astra"


def test_compose_invalid_codex_role_pin_disclosed(tmp_path, capsys):
    repo = str(tmp_path)
    _write_core_with_prefs(repo, {"codexModels": {"reviewer": "gpt-6-astra"}})
    rc = SM.main(
        [
            "x",
            "compose",
            "--live-vendors",
            "claude,codex,cursor",
            "--implementation-engine",
            "cursor",
            "--host-model",
            "composer-2.5",
            "--repo-root",
            repo,
            "--pr-number",
            "1273",
        ]
    )
    assert rc == 0
    receipt = json.loads(capsys.readouterr().out)
    honorable = [
        d for d in receipt["degradations"] if d["constraint"] == "role-pin-not-honorable"
    ]
    assert len(honorable) == 1
    assert honorable[0]["reason"].startswith("pin-role-not-eligible:")


def test_cli_compose_claude_impl_unknown_host_exits_zero(capsys):
    rc = SM.main(
        [
            "x",
            "compose",
            "--live-vendors",
            "claude,codex,cursor",
            "--implementation-engine",
            "claude",
            "--host-model",
            "mystery-model",
            "--pr-number",
            "1273",
        ]
    )
    assert rc == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["authorFamily"] == "anthropic"
    assert any(d["constraint"] == "host-model-unknown" for d in receipt["degradations"])


def test_cli_compose_claude_impl_openai_host_author_is_anthropic(capsys):
    rc = SM.main(
        [
            "x",
            "compose",
            "--live-vendors",
            "claude,codex,cursor",
            "--implementation-engine",
            "claude",
            "--host-model",
            "gpt-6.1-sol",
            "--pr-number",
            "1273",
        ]
    )
    assert rc == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["authorFamily"] == "anthropic"
    assert not any(
        d["constraint"] == "host-model-unknown" for d in receipt["degradations"]
    )
    splits = [d for d in receipt["degradations"] if d["constraint"] == "maker-family-split"]
    assert len(splits) == 1
    assert "anthropic" in splits[0]["reason"]
    assert "openai" in splits[0]["reason"]
    maker_seats = set(SM.PANEL_ROSTER)
    for seat in maker_seats:
        fam = receipt["seats"][seat]["family"]
        assert fam not in ("anthropic", "openai"), (seat, fam)


def test_build_extra_maker_family_falls_back_and_discloses():
    # author anthropic plus extra maker openai, and nothing else live: no seat is filled with
    # either maker family, and each seat is disclosed as unfilled
    m = SM.build(
        SM.PANEL_ROSTER,
        ["claude", "codex"],
        "anthropic",
        1,
        extra_maker_families=frozenset({"openai"}),
    )
    for seat in SM.PANEL_ROSTER:
        assert m["seats"][seat]["source"] == "unfilled", seat
        assert m["seats"][seat]["family"] is None, seat
        assert any(
            d.get("constraint") == "seat-unfilled" and d.get("seat") == seat
            for d in m["degradations"]
        ), seat
    assert not any(
        d.get("constraint") == "secondary-maker-seated" for d in m["degradations"]
    )


def test_build_extra_maker_families_default_unchanged():
    for seed in range(21):
        base = SM.build(
            SM.PANEL_ROSTER, THREE_VENDORS, "anthropic", seed
        )
        with_extra = SM.build(
            SM.PANEL_ROSTER,
            THREE_VENDORS,
            "anthropic",
            seed,
            extra_maker_families=None,
        )
        assert base == with_extra


def test_cli_compose_claude_impl_anthropic_host_no_maker_family_split(capsys):
    rc = SM.main(
        [
            "x",
            "compose",
            "--live-vendors",
            "claude,codex,cursor",
            "--implementation-engine",
            "claude",
            "--host-model",
            "claude-opus-5",
            "--pr-number",
            "1273",
        ]
    )
    assert rc == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["authorFamily"] == "anthropic"
    assert not any(
        d["constraint"] == "maker-family-split" for d in receipt["degradations"]
    )


def test_cli_compose_cursor_impl_openai_host_author_is_xai(capsys):
    rc = SM.main(
        [
            "x",
            "compose",
            "--live-vendors",
            "claude,codex,cursor",
            "--implementation-engine",
            "cursor",
            "--host-model",
            "gpt-6.1-sol",
            "--pr-number",
            "1273",
        ]
    )
    assert rc == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["authorFamily"] == "xai"


def test_cli_compose_family_flags_conflict(capsys):
    rc = SM.main(
        [
            "x",
            "compose",
            "--live-vendors",
            "claude",
            "--implementation-engine",
            "cursor",
            "--author-family",
            "xai",
        ]
    )
    assert rc == 1
    assert "family-flags-conflict" in capsys.readouterr().err


def test_cli_compose_reads_codex_models_from_repo(tmp_path, capsys):
    repo = str(tmp_path)
    _write_core_with_prefs(
        repo,
        {"codexModels": {"reviewer-deep": _PIN_ONLY_CODEX, "implementer": _SECOND_CODEX_MODEL}},
    )
    live_cells = [
        ["codex", "gpt-5.6-sol", "xhigh"],
        ["cursor", "cursor-grok-4.6", "xhigh"],
    ]
    rc = SM.main(
        [
            "x",
            "compose",
            "--live-vendors",
            "claude,codex,cursor",
            "--implementation-engine",
            "cursor",
            "--host-model",
            "composer-2.5",
            "--repo-root",
            repo,
            "--pr-number",
            "1273",
        ]
    )
    assert rc == 0
    receipt = json.loads(capsys.readouterr().out)
    codex_deep = [
        receipt["seats"][s]
        for s in SM.PANEL_ROSTER
        if receipt["seats"][s]["vendor"] == "codex"
        and receipt["seats"][s]["tier"] == "reviewer-deep"
    ]
    assert codex_deep
    for cfg in codex_deep:
        assert cfg["model"] == "gpt-5.6-sol"
        assert cfg["source"] == "role-pinned"


# --- unfilled seats: the panel never seats a maker family -------------------------------------


def _assert_all_unfilled(m, roster=None):
    for seat in roster or SM.PANEL_ROSTER:
        cfg = m["seats"][seat]
        assert cfg["source"] == "unfilled", seat
        assert cfg["vendor"] is None and cfg["model"] is None, seat
        assert cfg["effort"] is None and cfg["family"] is None, seat
        assert cfg["tier"] == SM.DEFAULT_TIER_BY_SEAT[seat], seat
        records = [
            d for d in m["degradations"]
            if d.get("constraint") == "seat-unfilled" and d.get("seat") == seat
        ]
        assert len(records) == 1, seat
        assert "recorded unfilled, not run" in records[0]["reason"], seat


def test_e1_only_author_family_live_leaves_every_seat_unfilled():
    m = SM.build(SM.PANEL_ROSTER, ["claude"], "anthropic", 0)
    _assert_all_unfilled(m)
    assert not any(cfg["family"] == "anthropic" for cfg in m["seats"].values())
    assert not any(d.get("constraint") == "same-family" for d in m["degradations"])
    assert not any(d.get("constraint") == "secondary-maker-seated" for d in m["degradations"])
    assert m["makerFamilies"] == ["anthropic"]


def test_e2_author_plus_extra_maker_live_leaves_every_seat_unfilled():
    m = SM.build(
        SM.PANEL_ROSTER,
        ["claude", "codex"],
        "anthropic",
        3,
        extra_maker_families=frozenset({"openai"}),
    )
    _assert_all_unfilled(m)
    assert not any(d.get("constraint") == "secondary-maker-seated" for d in m["degradations"])
    assert m["makerFamilies"] == ["anthropic", "openai"]
    assert "anthropic, openai" in next(
        d["reason"] for d in m["degradations"] if d.get("constraint") == "seat-unfilled"
    )


def test_e3_maker_family_pin_leaves_its_seat_unfilled_and_others_compose():
    pins = {"code-reviewer": {"vendor": "claude"}}
    m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "anthropic", 0, pins=pins)
    assert m["seats"]["code-reviewer"]["source"] == "unfilled"
    pin_records = [
        d for d in m["degradations"]
        if d.get("constraint") == "pin-breaks-constraint" and d.get("seat") == "code-reviewer"
    ]
    assert len(pin_records) == 1
    assert "maker family" in pin_records[0]["reason"]
    for seat in SM.PANEL_ROSTER:
        if seat == "code-reviewer":
            continue
        assert m["seats"][seat]["source"] != "unfilled", seat
        assert m["seats"][seat]["family"] not in (None, "anthropic"), seat
    assert not any(
        d.get("constraint") == "seat-unfilled" and d.get("seat") != "code-reviewer"
        for d in m["degradations"]
    )


def test_e3_pin_to_extra_maker_family_leaves_its_seat_unfilled():
    pins = {"test-role": {"vendor": "codex"}}
    m = SM.build(
        SM.PANEL_ROSTER, THREE_VENDORS, "anthropic", 0, pins=pins,
        extra_maker_families=frozenset({"openai"}),
    )
    assert m["seats"]["test-role"]["source"] == "unfilled"
    assert any(
        d.get("constraint") == "pin-breaks-constraint" and d.get("seat") == "test-role"
        for d in m["degradations"]
    )
    assert not any(cfg["family"] == "openai" for cfg in m["seats"].values())


def test_e3_pin_to_non_maker_family_is_unchanged():
    pins = {"code-reviewer": {"vendor": "codex"}}
    m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "anthropic", 0, pins=pins)
    assert m["seats"]["code-reviewer"]["source"] == "pinned"
    assert m["seats"]["code-reviewer"]["vendor"] == "codex"


def test_e4_no_live_vendor_leaves_every_seat_unfilled_with_no_synthetic_cfg():
    m = SM.build(SM.PANEL_ROSTER, [], "anthropic", 0)
    _assert_all_unfilled(m)
    assert not any(cfg["vendor"] is not None for cfg in m["seats"].values())
    assert any(d.get("constraint") == "live-vendors" for d in m["degradations"])


def test_e5_verify_and_receipt_tolerate_unfilled_seats():
    m = SM.build(SM.PANEL_ROSTER, ["claude"], "anthropic", 0)
    violations = SM.verify(m, "anthropic")
    blocked = {"missing-seat", "malformed", "unresolvable-seat-vendor", "maker-family"}
    assert not [v for v in violations if v.get("constraint") in blocked], violations
    assert not any(v.get("seat") for v in violations), violations
    receipt = SM.to_receipt(m, "anthropic")
    assert not [v for v in receipt["violations"] if v.get("constraint") in blocked]
    assert SM.same_family_degradations(m, "anthropic") == []


def test_e5_a_forged_unfilled_record_that_names_a_vendor_is_still_checked():
    m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "anthropic", 0)
    m["seats"]["test-role"] = {
        "vendor": "claude", "model": "opus-5.5", "effort": "xhigh",
        "tier": "reviewer-deep", "family": "anthropic", "source": "unfilled",
    }
    assert any(
        v.get("constraint") == "maker-family" and v.get("seat") == "test-role"
        for v in SM.verify(m, "anthropic")
    )


def test_e6_compose_maker_family_flag_excludes_that_family(capsys):
    argv = [
        "x", "compose",
        "--live-vendors", "claude,codex",
        "--author-family", "anthropic",
        "--pr-number", "1796",
    ]
    assert SM.main(argv) == 0
    without_flag = json.loads(capsys.readouterr().out)
    assert any(cfg["family"] == "openai" for cfg in without_flag["seats"].values())

    assert SM.main(argv + ["--maker-family", "openai"]) == 0
    receipt = json.loads(capsys.readouterr().out)
    for seat in SM.PANEL_ROSTER:
        assert receipt["seats"][seat]["source"] == "unfilled", seat
    assert receipt["makerFamilies"] == ["anthropic", "openai"]
    assert not any(v.get("constraint") == "maker-family" for v in receipt["violations"])


def test_e6_maker_family_flag_is_repeatable_and_accepts_unknown_families(capsys):
    argv = [
        "x", "compose",
        "--live-vendors", "claude,codex,cursor",
        "--author-family", "anthropic",
        "--pr-number", "1796",
        "--maker-family", "openai",
        "--maker-family", "xai",
        "--maker-family", "not-a-registered-family",
    ]
    assert SM.main(argv) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["makerFamilies"] == ["anthropic", "not-a-registered-family", "openai", "xai"]
    for seat in SM.PANEL_ROSTER:
        assert receipt["seats"][seat]["source"] == "unfilled", seat


def test_e6_maker_family_flag_joins_the_host_family_extra(capsys):
    argv = [
        "x", "compose",
        "--live-vendors", "claude,codex,cursor",
        "--implementation-engine", "claude",
        "--host-model", "gpt-5.6-sol",
        "--maker-family", "xai",
        "--pr-number", "1796",
    ]
    assert SM.main(argv) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert "xai" in receipt["makerFamilies"]
    assert "anthropic" in receipt["makerFamilies"]
    assert not any(
        cfg["family"] in receipt["makerFamilies"] for cfg in receipt["seats"].values()
    )


def test_build_and_receipt_name_the_maker_families_and_the_roster():
    m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "anthropic", 0,
                 extra_maker_families=frozenset({"xai"}))
    assert m["makerFamilies"] == ["anthropic", "xai"]
    assert m["roster"] == list(SM.PANEL_ROSTER)
    receipt = SM.to_receipt(m, "anthropic")
    assert receipt["makerFamilies"] == ["anthropic", "xai"]
    assert receipt["roster"] == list(SM.PANEL_ROSTER)
    custom = SM.build(["code-reviewer", "test-role"], THREE_VENDORS, "anthropic", 0)
    assert custom["roster"] == ["code-reviewer", "test-role"]
    assert SM.build(SM.PANEL_ROSTER, THREE_VENDORS, None, 0)["makerFamilies"] == []


def test_unfilled_seats_never_count_toward_the_author_minority_or_critical_checks():
    # one critical seat unfilled by a pin, the rest seated: nothing raises, an unfilled seat is
    # never counted as the author's, and the seated families still decide critical diversity
    pins = {"premortem-reviewer": {"vendor": "claude"}}
    m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "anthropic", 0, pins=pins)
    assert m["seats"]["premortem-reviewer"]["source"] == "unfilled"
    assert not any(d.get("constraint") == "author-minority" for d in m["degradations"])
    assert not any(d.get("constraint") == "critical-diversity" for d in m["degradations"])
    # an unknown author family leaves nothing to count against and never raises either
    unknown_author = SM.build(SM.PANEL_ROSTER, ["claude"], None, 0)
    assert all(cfg["family"] == "anthropic" for cfg in unknown_author["seats"].values())
    assert SM.build(SM.PANEL_ROSTER, [], None, 0)["seats"]


def test_unfilled_seat_invariant_no_seat_carries_a_maker_family():
    vendor_sets = [[], ["claude"], ["codex"], ["claude", "codex"], ["claude", "codex", "cursor"]]
    for live in vendor_sets:
        for author in ("anthropic", "openai", "xai"):
            for extra in (frozenset(), frozenset({"openai"})):
                for seed in (0, 1, 2):
                    m = SM.build(
                        SM.PANEL_ROSTER, live, author, seed,
                        extra_maker_families=extra,
                    )
                    makers = {author} | set(extra)
                    assert m["makerFamilies"] == sorted(makers)
                    for seat in SM.PANEL_ROSTER:
                        cfg = m["seats"][seat]
                        ctx = (live, author, sorted(extra), seed, seat)
                        assert cfg["family"] not in makers, ctx
                        if cfg["source"] == "unfilled":
                            assert cfg["vendor"] is None and cfg["family"] is None, ctx
                            assert any(
                                d.get("constraint") == "seat-unfilled" and d.get("seat") == seat
                                for d in m["degradations"]
                            ), ctx
                    receipt = SM.to_receipt(m, author)
                    assert not any(
                        v.get("constraint") in ("maker-family", "missing-seat", "malformed")
                        for v in receipt["violations"]
                    ), (live, author, sorted(extra))


def test_backfill_for_a_non_maker_reason_never_returns_a_maker_family(monkeypatch):
    # no reviewer-deep cell exists at all, so every strong seat is empty for a reason that is not the
    # maker filter; the reviewer-tier backfill may seat a non-maker but never the author's family
    real_matrix = SM.matrix_config

    def _no_reviewer_deep(tier, vendor):
        if tier == "reviewer-deep":
            return None
        return real_matrix(tier, vendor)

    monkeypatch.setattr(SM, "matrix_config", _no_reviewer_deep)
    only_maker = SM.build(SM.KNOWN_SEATS, ["claude"], "anthropic", 0)
    with_other = SM.build(SM.KNOWN_SEATS, THREE_VENDORS, "anthropic", 0)
    for seat in SM.STRONG_TIER_SEATS:
        assert only_maker["seats"][seat]["source"] == "unfilled", seat
        assert with_other["seats"][seat]["source"] == "backfill", seat
        assert with_other["seats"][seat]["family"] != "anthropic", seat
        assert any(
            d.get("constraint") == "seat-unfilled" and d.get("seat") == seat
            and "backfilled to" in d["reason"]
            for d in with_other["degradations"]
        ), seat


# --- the full-lane roster follows the lane call (axis comments: bite-proof record wo_a_1797_roster) ---

import subprocess

import core_md as CM
import lane_call as LC

RISKY_ROSTER = SM.PANEL_ROSTER
NO_FLOOR_ROSTER = tuple(s for s in SM.PANEL_ROSTER if s in SM.BASE_ROSTER)
_PAYMENTS = {
    "name": "Payments",
    "covers": ["src/payments/*"],
    "why": "Charges customers.",
    "undo": "Hard: a charge needs a refund.",
}
_GIT_ID = ["-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false"]


def _git(repo, *args):
    done = subprocess.run(["git", "-C", str(repo), *_GIT_ID, *args], capture_output=True, text=True, check=True)
    return done.stdout.strip()


def _project(tmp_path, monkeypatch, *, areas=None, prefs=None, corrupt=False):
    """A git repo with a base commit and a head commit that adds src/payments/charge.py and
    docs/notes.md; its core.md (in the store the env points at) holds the given risk areas and
    engine preferences. Returns (repo, base, head)."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    store = str(tmp_path / "store")
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", store)
    _git(repo, "init", "-q")
    (repo / "README.md").write_text("base\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "src" / "payments").mkdir(parents=True)
    (repo / "src" / "payments" / "charge.py").write_text("x = 1\n")
    (repo / "docs").mkdir()
    (repo / "docs" / "notes.md").write_text("notes\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "change")
    head = _git(repo, "rev-parse", "HEAD")
    if corrupt:
        core = repo / ".claude" / "superheroes"
        core.mkdir(parents=True)
        (core / "core.md").write_text("not a core file\n\x00\n")
        return str(repo), base, head
    facts = {"verifyCommand": "npm test", "stackTags": ["node"], "threatModel": "single-user",
             "patterns": "- x: a.ts:1"}
    if prefs is not None:
        facts["enginePreferences"] = prefs
    CM.write(str(repo), facts, "confirmed", root=store, now="2026-06-26")
    if areas is not None:
        assert CM.write_project_config_item(str(repo), CM.RISK_AREAS_KEY, areas, root=store)["action"] == "written"
    return str(repo), base, head


def _docs_commit(repo):
    """A commit on top of the project's head that changes only docs/other.md; returns (parent, sha)."""
    parent = _git(repo, "rev-parse", "HEAD")
    with open(os.path.join(repo, "docs", "other.md"), "w") as fh:
        fh.write("other\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "docs")
    return parent, _git(repo, "rev-parse", "HEAD")


def _compose(capsys, repo, *extra, base=None, head=None, live="claude,codex,cursor"):
    argv = ["x", "compose", "--live-vendors", live, "--author-family", "xai",
            "--pr-number", "1", "--repo-root", repo, *extra]
    if base is not None:
        argv += ["--base-ref", base]
    if head is not None:
        argv += ["--head-sha", head]
    capsys.readouterr()
    assert SM.main(argv) == 0
    return json.loads(capsys.readouterr().out)


def _bases(tmp_path, monkeypatch):
    """One real lane-call basis per way the floor comes out full."""
    repo, _base, _head = _project(tmp_path / "set", monkeypatch, areas=[_PAYMENTS])
    unset, _b, _h = _project(tmp_path / "unset", monkeypatch)
    store, unset_store = str(tmp_path / "set" / "store"), str(tmp_path / "unset" / "store")
    return {
        "touches-a-risk-area": LC.call(repo, ["src/payments/charge.py"], proposed="full", root=store),
        "risk-areas-not-set": LC.call(unset, ["docs/notes.md"], proposed="full", root=unset_store),
        "unmatchable-path": LC.call(repo, ["/abs/outside.py"], proposed="full", root=store),
        "no-paths": LC.call(repo, [], proposed="full", root=store),
        "unavailable": LC.unavailable("lane-basis-unavailable: test", proposed="full"),
    }


def test_roster_for_full_floor_adds_the_specialists(tmp_path, monkeypatch):
    # axis: a basis whose floor is not None gets the security and premortem seats — see bite-proof record wo_a_1797_roster
    for name, basis in _bases(tmp_path, monkeypatch).items():
        assert basis["floor"] == "full", name
        assert SM.roster_for(basis) == RISKY_ROSTER, name


def test_roster_for_no_floor_is_the_generalist_and_the_test_seat(tmp_path, monkeypatch):
    repo, _base, _head = _project(tmp_path, monkeypatch, areas=[_PAYMENTS])
    basis = LC.call(repo, ["docs/notes.md"], proposed="full")
    assert basis["floor"] is None
    assert SM.roster_for(basis) == NO_FLOOR_ROSTER == ("code-reviewer", "test-role")


def test_roster_for_fails_closed_on_a_basis_it_cannot_read():
    # axis: a basis that is missing, not a dict, or has no floor key gets the full risky roster — see bite-proof record wo_a_1797_roster
    for basis in (None, "full", [], 7, {}, {"lane": "full"}, {"floor": "full"}, {"floor": ""}, {"floor": "none"}):
        assert SM.roster_for(basis) == RISKY_ROSTER, basis


def test_architecture_is_never_in_a_composed_roster(tmp_path, monkeypatch):
    for basis in list(_bases(tmp_path, monkeypatch).values()) + [None, {"floor": None}]:
        assert "architecture-reviewer" not in SM.roster_for(basis)
    assert "architecture-reviewer" not in SM.PANEL_ROSTER
    assert set(SM.LENS_SEATS) == {"architecture-reviewer", "code-reviewer", "security-reviewer",
                                  "test-role", "premortem-reviewer"}
    assert SM.KNOWN_SEATS == SM.LENS_SEATS


def test_roster_for_keeps_the_panel_roster_order():
    assert SM.roster_for({"floor": None}) == tuple(s for s in SM.PANEL_ROSTER if s in NO_FLOOR_ROSTER)


def test_effective_roster_is_a_non_empty_list_of_strings_or_none():
    assert SM.effective_roster({"roster": ["a", "b"]}) == ("a", "b")
    for bad in ({}, {"roster": []}, {"roster": "ab"}, {"roster": ("a",)}, {"roster": ["a", 1]}, None, "x"):
        assert SM.effective_roster(bad) is None, bad


def test_compose_roster_follows_the_lane_call(tmp_path, monkeypatch, capsys):
    repo, base, head = _project(tmp_path, monkeypatch, areas=[_PAYMENTS])
    inside = _compose(capsys, repo, base=base, head=head)
    assert tuple(inside["roster"]) == RISKY_ROSTER and set(inside["seats"]) == set(RISKY_ROSTER)
    assert inside["laneBasis"]["floor"] == "full"
    assert inside["laneBasis"]["touched"] == [{"name": "Payments", "matched": 1}]
    # path lists ride as counts, never as the paths
    assert "charge.py" not in json.dumps(inside["laneBasis"])
    parent, docs_head = _docs_commit(repo)
    outside = _compose(capsys, repo, base=parent, head=docs_head)
    assert tuple(outside["roster"]) == NO_FLOOR_ROSTER and set(outside["seats"]) == set(NO_FLOOR_ROSTER)
    assert outside["laneBasis"]["floor"] is None and outside["laneBasis"]["touched"] == []
    assert outside["violations"] == []
    assert not any(d["constraint"] == "critical-diversity" for d in outside["degradations"])


def test_compose_without_a_base_ref_composes_the_risky_roster(tmp_path, monkeypatch, capsys):
    # axis: compose's fail-closed lane basis on a missing base ref — see bite-proof record wo_a_1797_roster
    repo, _base, _head = _project(tmp_path, monkeypatch, areas=[_PAYMENTS])
    _parent, docs_head = _docs_commit(repo)
    receipt = _compose(capsys, repo, head=docs_head)
    assert tuple(receipt["roster"]) == RISKY_ROSTER
    assert receipt["laneBasis"]["floor"] == "full"
    assert any("--base-ref" in w for w in receipt["laneBasis"]["why"])


def test_compose_without_a_head_sha_composes_the_risky_roster(tmp_path, monkeypatch, capsys):
    repo, base, _head = _project(tmp_path, monkeypatch, areas=[_PAYMENTS])
    for head in (None, ""):
        receipt = _compose(capsys, repo, base=base, head=head)
        assert tuple(receipt["roster"]) == RISKY_ROSTER and receipt["laneBasis"]["floor"] == "full"


def test_compose_composes_the_risky_roster_when_git_cannot_answer(tmp_path, monkeypatch, capsys):
    repo, _base, head = _project(tmp_path, monkeypatch, areas=[_PAYMENTS])
    _parent, docs_head = _docs_commit(repo)
    assert tuple(_compose(capsys, repo, base="0" * 40, head=docs_head)["roster"]) == RISKY_ROSTER

    def failing(exc):
        def run(*_a, **_k):
            raise exc
        return run

    for exc in (FileNotFoundError("git"), subprocess.TimeoutExpired("git", 120), OSError("boom")):
        monkeypatch.setattr(subprocess, "run", failing(exc))
        receipt = _compose(capsys, repo, base=head, head=docs_head)
        assert tuple(receipt["roster"]) == RISKY_ROSTER, exc
        assert receipt["laneBasis"]["floor"] == "full"
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, b"\xff\xfe", b""))
    assert tuple(_compose(capsys, repo, base=head, head=docs_head)["roster"]) == RISKY_ROSTER


def test_compose_ignores_usable_paths_from_a_failed_git_diff(tmp_path, monkeypatch, capsys):
    # axis: the exit-status guard, not the empty path list, is what rejects a failed diff — stdout names
    # a path outside every risk area, so only the guard keeps the risky roster
    repo, base, _head = _project(tmp_path, monkeypatch, areas=[_PAYMENTS])
    _parent, docs_head = _docs_commit(repo)
    real_run = subprocess.run

    def with_exit(code):
        def run(argv, *a, **k):
            if "diff" in argv:
                return subprocess.CompletedProcess(argv, code, b"docs/other.md\0", b"failure")
            return real_run(argv, *a, **k)
        return run

    monkeypatch.setattr(subprocess, "run", with_exit(128))
    failed = _compose(capsys, repo, base=base, head=docs_head)
    assert tuple(failed["roster"]) == RISKY_ROSTER and failed["laneBasis"]["floor"] == "full"
    monkeypatch.setattr(subprocess, "run", with_exit(0))
    clean = _compose(capsys, repo, base=base, head=docs_head)
    assert tuple(clean["roster"]) == NO_FLOOR_ROSTER and clean["laneBasis"]["floor"] is None


def test_compose_with_no_changed_paths_composes_the_risky_roster(tmp_path, monkeypatch, capsys):
    repo, _base, head = _project(tmp_path, monkeypatch, areas=[_PAYMENTS])
    receipt = _compose(capsys, repo, base=head, head=head)
    assert tuple(receipt["roster"]) == RISKY_ROSTER and receipt["laneBasis"]["floor"] == "full"


def test_compose_with_risk_areas_not_set_composes_the_risky_roster(tmp_path, monkeypatch, capsys):
    repo, base, head = _project(tmp_path, monkeypatch)
    receipt = _compose(capsys, repo, base=base, head=head)
    assert tuple(receipt["roster"]) == RISKY_ROSTER and receipt["laneBasis"]["floor"] == "full"


# --- seat pins come from core.md ----------------------------------------------------------------


def test_core_md_seat_pins_bind_a_base_seat_and_a_specialist_with_no_pins_flag(tmp_path, monkeypatch, capsys):
    # axis: compose reads enginePreferences.seatPins from core.md itself — see bite-proof record wo_a_1797_roster
    prefs = {"seatPins": {"code-reviewer": {"vendor": "claude"}, "security-reviewer": {"vendor": "claude"}}}
    repo, _base, _head = _project(tmp_path, monkeypatch, prefs=prefs)
    receipt = _compose(capsys, repo)
    for seat in ("code-reviewer", "security-reviewer"):
        assert receipt["seats"][seat]["source"] == "pinned", seat
        assert receipt["seats"][seat]["vendor"] == "claude", seat


def test_pins_flag_overrides_core_md_for_the_seat_it_names(tmp_path, monkeypatch, capsys):
    prefs = {"seatPins": {"code-reviewer": {"vendor": "claude"}, "security-reviewer": {"vendor": "claude"}}}
    repo, _base, _head = _project(tmp_path, monkeypatch, prefs=prefs)
    receipt = _compose(capsys, repo, "--pins", json.dumps({"code-reviewer": {"vendor": "codex"}}))
    assert receipt["seats"]["code-reviewer"]["vendor"] == "codex"
    assert receipt["seats"]["code-reviewer"]["source"] == "pinned"
    assert receipt["seats"]["security-reviewer"]["source"] == "pinned"
    assert receipt["seats"]["security-reviewer"]["vendor"] == "claude"


def test_core_md_pin_for_a_seat_the_roster_does_not_seat_is_skipped_without_a_degradation(tmp_path, monkeypatch, capsys):
    prefs = {"seatPins": {"security-reviewer": {"vendor": "claude"}, "architecture-reviewer": {"vendor": "claude"},
                          "code-reviewer": {"vendor": "claude"}}}
    repo, _base, _head = _project(tmp_path, monkeypatch, areas=[_PAYMENTS], prefs=prefs)
    parent, docs_head = _docs_commit(repo)
    receipt = _compose(capsys, repo, base=parent, head=docs_head)
    assert tuple(receipt["roster"]) == NO_FLOOR_ROSTER
    assert receipt["seats"]["code-reviewer"]["source"] == "pinned"
    assert not any(d["constraint"] == "pin" for d in receipt["degradations"])


def test_core_md_pin_for_an_unknown_seat_and_an_argv_pin_outside_the_roster_stay_disclosed(tmp_path, monkeypatch, capsys):
    prefs = {"seatPins": {"not-a-seat": {"vendor": "claude"}}}
    repo, _base, _head = _project(tmp_path, monkeypatch, areas=[_PAYMENTS], prefs=prefs)
    parent, docs_head = _docs_commit(repo)
    receipt = _compose(capsys, repo, "--pins", json.dumps({"security-reviewer": {"vendor": "claude"}}),
                       base=parent, head=docs_head)
    assert tuple(receipt["roster"]) == NO_FLOOR_ROSTER
    reasons = [d["reason"] for d in receipt["degradations"] if d["constraint"] == "pin"]
    assert "pin for unknown seat not-a-seat" in reasons
    assert "pin for unknown seat security-reviewer" in reasons


def test_an_unreadable_core_md_composes_unpinned_and_says_so(tmp_path, monkeypatch, capsys):
    repo, _base, _head = _project(tmp_path, monkeypatch, corrupt=True)
    receipt = _compose(capsys, repo)
    pin = [d for d in receipt["degradations"] if d["constraint"] == "pin"]
    assert len(pin) == 1 and "composes unpinned" in pin[0]["reason"]
    assert "core-md-unreadable" in pin[0]["detail"]
    assert all(cfg["source"] != "pinned" for cfg in receipt["seats"].values())


def test_invalid_core_md_pin_entries_are_each_disclosed(tmp_path, monkeypatch, capsys):
    prefs = {"seatPins": {"code-reviewer": "not-a-dict", "security-reviewer": {"model": "x"},
                          "test-role": {"vendor": "claude"}}}
    repo, _base, _head = _project(tmp_path, monkeypatch, prefs=prefs)
    receipt = _compose(capsys, repo)
    pin = {d["reason"]: d["detail"] for d in receipt["degradations"] if d["constraint"] == "pin"}
    assert len(pin) == 2
    assert any("code-reviewer" in r and d == "pin must be an object with a vendor" for r, d in pin.items())
    assert any("security-reviewer" in r and d == "missing or invalid vendor" for r, d in pin.items())
    assert receipt["seats"]["test-role"]["source"] == "pinned"


def test_a_seat_pins_value_that_is_not_an_object_is_disclosed(tmp_path, monkeypatch, capsys):
    for bad, kind in ((["code-reviewer"], "list"), ("claude", "str"), (7, "int")):
        repo, _base, _head = _project(tmp_path / kind, monkeypatch, prefs={"seatPins": bad})
        receipt = _compose(capsys, repo)
        pin = [d for d in receipt["degradations"] if d["constraint"] == "pin"]
        assert len(pin) == 1 and "not an object" in pin[0]["reason"], kind
        assert pin[0]["detail"] == "seatPins is a %s" % kind
        assert all(cfg["source"] != "pinned" for cfg in receipt["seats"].values())


# --- critical diversity scales with the roster --------------------------------------------------


def test_required_critical_families_scales_with_the_critical_seats_the_roster_seats():
    # axis: the critical-diversity bar is the roster's, not a fixed two — see bite-proof record wo_a_1797_roster
    assert SM.required_critical_families(SM.PANEL_ROSTER) == 2
    assert SM.required_critical_families(SM.KNOWN_SEATS) == 2
    assert SM.required_critical_families(NO_FLOOR_ROSTER) == 1


def test_a_valid_no_floor_panel_has_no_critical_diversity_degradation_or_violation():
    # axis: a one-critical-seat roster is not held to two families — see bite-proof record wo_a_1797_roster
    for live in (["claude"], ["claude", "codex"], THREE_VENDORS):
        m = dict(SM.build(NO_FLOOR_ROSTER, live, "xai", 0), laneBasis={"floor": None})
        assert not any(d["constraint"] == "critical-diversity" for d in m["degradations"]), live
        assert SM.verify(m, "xai") == [], live
        classified = SM.classify_violations(m)
        assert classified["unexcused"] == [] and classified["excusedByLiveness"] == [], live
        assert m["roster"] == list(NO_FLOOR_ROSTER)


def test_the_risky_roster_still_needs_two_critical_families():
    m = SM.build(SM.PANEL_ROSTER, ["claude"], "xai", 0)
    assert any(d["constraint"] == "critical-diversity" for d in m["degradations"])
    assert {"constraint": "critical-diversity"} in SM.verify(m, "xai")
    broken = dict(m, roster=[])
    assert {"constraint": "critical-diversity"} in SM.verify(broken, "xai")


def test_classify_violations_holds_the_critical_family_bar_of_the_roster():
    # axis: the classifier reads the roster's critical-family requirement, not a fixed two — see bite-proof record wo_a_1797_roster
    viol = [{"constraint": "critical-diversity"}]
    stands = {"constraint": "critical-diversity", "evidence": "alternative-live"}
    # requirement 1: one reachable family meets the bar, so the violation stands (a fixed two would excuse it)
    reduced = dict(SM.build(NO_FLOOR_ROSTER, ["claude"], "xai", 0),
                   laneBasis={"floor": None}, violations=list(viol))
    assert SM.required_critical_families(NO_FLOOR_ROSTER) == 1
    got = SM.classify_violations(reduced)
    assert got["unexcused"] == [stands] and got["excusedByLiveness"] == []
    # requirement 2: one reachable family cannot meet the bar (excused); two can (stands)
    one = dict(SM.build(SM.PANEL_ROSTER, ["claude"], "xai", 0), violations=list(viol))
    got = SM.classify_violations(one)
    assert stands not in got["unexcused"] and got["excusedByLiveness"]
    two = dict(SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "xai", 0), violations=list(viol))
    assert stands in SM.classify_violations(two)["unexcused"]


# --- the maker's family is barred from every known seat -----------------------------------------


def test_an_architecture_seat_composed_through_an_explicit_roster_cannot_be_pinned_to_a_maker():
    # axis: MAKER_EXCLUDED_SEATS covers every known seat, architecture included — see bite-proof record wo_a_1797_roster
    pins = {"architecture-reviewer": {"vendor": "claude"}}
    m = SM.build(SM.KNOWN_SEATS, THREE_VENDORS, "anthropic", 0, pins=pins)
    assert m["seats"]["architecture-reviewer"]["source"] == "unfilled"
    assert m["seats"]["architecture-reviewer"]["family"] is None
    assert any(d.get("constraint") == "pin-breaks-constraint" and d.get("seat") == "architecture-reviewer"
               for d in m["degradations"])
    assert set(SM.KNOWN_SEATS) == SM.MAKER_EXCLUDED_SEATS


# --- verify checks the map's own roster ---------------------------------------------------------


def test_verify_a_three_seat_map_has_no_missing_seat():
    m = dict(SM.build(NO_FLOOR_ROSTER, THREE_VENDORS, "xai", 0), laneBasis={"floor": None})
    assert SM.verify(m, "xai") == []
    assert not any(v["constraint"] == "missing-seat" for v in SM.to_receipt(m, "xai")["violations"])
    assert SM.to_receipt(m, "xai")["roster"] == list(NO_FLOOR_ROSTER)


@pytest.mark.parametrize("basis", [{"floor": "full"}, None, "unreadable", {}])
def test_verify_holds_a_reduced_roster_to_its_lane_basis(basis):
    # axis: the roster must cover roster_for(laneBasis); a full, absent or unreadable basis needs the risky roster — see bite-proof record wo_a_1797_roster
    m = SM.build(NO_FLOOR_ROSTER, THREE_VENDORS, "xai", 0)
    got = SM.verify(dict(m, laneBasis=basis), "xai")
    for gone in ("security-reviewer", "premortem-reviewer"):
        assert {"constraint": "roster-missing-required", "seat": gone} in got
    reduced = SM.verify(dict(m, laneBasis={"floor": None}), "xai")
    assert not any(v["constraint"] == "roster-missing-required" for v in reduced)


def test_verify_a_roster_that_omits_the_generalist_or_the_test_seat_is_a_violation():
    m = SM.build(NO_FLOOR_ROSTER, THREE_VENDORS, "xai", 0)
    for gone in ("test-role", "code-reviewer"):
        trimmed = dict(m, roster=[s for s in NO_FLOOR_ROSTER if s != gone])
        assert {"constraint": "roster-missing-required", "seat": gone} in SM.verify(trimmed, "xai")


def test_verify_holds_an_unreadable_roster_to_the_full_risky_panel():
    m = SM.build(NO_FLOOR_ROSTER, THREE_VENDORS, "xai", 0)
    for bad in ([], "code-reviewer", None, ["code-reviewer", 3]):
        v = SM.verify(dict(m, roster=bad), "xai")
        missing = {x["seat"] for x in v if x["constraint"] == "missing-seat"}
        assert missing == {"security-reviewer", "premortem-reviewer"}, bad


def test_same_family_scan_covers_every_known_seat_when_the_map_names_no_roster():
    m = SM.build(SM.KNOWN_SEATS, ["claude"], "anthropic", 0)
    m.pop("roster")
    m["seats"] = {s: dict(cfg) for s, cfg in m["seats"].items()}
    seat = "architecture-reviewer"
    m["seats"][seat] = {"vendor": "claude", "model": "opus-5.5", "effort": "xhigh", "tier": "reviewer-deep",
                        "source": "live", "family": "anthropic"}
    assert any(d["seat"] == seat for d in SM.same_family_degradations(m, "anthropic"))
    assert seat in SM.to_receipt(m, "anthropic")["roster"]
