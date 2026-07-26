import importlib.util
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_MOD = os.path.join(_HERE, "..", "model_registry.py")


def _load():
    spec = importlib.util.spec_from_file_location("model_registry", _MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MR = _load()

_EXPECTED_DEFAULT_CLAUDE_TIERS = {
    "orchestrator": None,
    "reviewer": "sonnet",
    "reviewer-deep": "opus",
    "verifier": "opus",
    "mechanical": "haiku",
    "synthesis": "opus",
    "code-fixer": "sonnet",
    "doc-reviser": "opus",
    "pr-body": "sonnet",
    "implementer": "sonnet",
    "pilot": "sonnet",
}


def test_matrix_cells_use_registered_models():
    for role in MR.roles():
        for vendor in MR.vendors():
            cell = MR.matrix_config(role, vendor)
            if cell is None:
                continue
            model_id, _effort = cell
            assert MR.is_registered(vendor, model_id), (
                f"matrix cell ({role!r}, {vendor!r}) references unregistered model {model_id!r}"
            )


def test_ladder_rungs_validate():
    for vendor in MR.vendors():
        for model_id, effort in MR.ladder(vendor):
            ok, reason = MR.validate_config(vendor, model_id, effort, allow_override_only=True)
            assert ok, f"ladder rung ({vendor!r}, {model_id!r}, {effort!r}) invalid: {reason}"


def test_roles_covers_matrix_and_model_tier_roles_stable():
    assert set(MR.roles()) == set(MR._MATRIX)
    assert "orchestrator" not in MR.roles()
    assert MR.model_tier_roles() == (
        "orchestrator",
        "reviewer",
        "reviewer-deep",
        "verifier",
        "mechanical",
        "synthesis",
        "code-fixer",
        "doc-reviser",
        "pr-body",
        "implementer",
        "pilot",
    )


def test_default_claude_tiers_migration_pin():
    assert MR.default_claude_tiers() == _EXPECTED_DEFAULT_CLAUDE_TIERS


def test_known_claude_models_matches_source():
    assert MR.known_claude_models() == tuple(
        m["dispatch"] for m in MR._MODELS["claude"].values())


def test_codex_pin_roles_matches_source():
    assert MR.codex_pin_roles() == tuple(
        r for r, meta in MR._ROLE_META.items() if meta["pin_eligible"])


def test_codex_write_pin_roles_matches_source():
    assert MR.codex_write_pin_roles() == tuple(
        r for r, meta in MR._ROLE_META.items()
        if meta["pin_eligible"] and meta["read_write"] == "write")


def test_model_tier_roles_matches_source():
    assert MR.model_tier_roles() == tuple(
        r for r, meta in MR._ROLE_META.items() if meta["model_tier_role"])


def test_codex_role_kind_matches_source():
    for role in MR.codex_pin_roles():
        assert MR.codex_role_kind()[role] == MR._ROLE_META[role]["codex_kind"]


def test_codex_effort_for_kind_matches_matrix_and_pilot_floor():
    expected = {
        MR._ROLE_META[r]["codex_kind"]: MR.matrix_config(r, "codex")[1]
        for r in MR.roles()
        if MR.matrix_config(r, "codex")
    }
    for kind, effort in expected.items():
        assert MR.codex_effort_for_kind(kind) == effort
    # pilot is claude-only — no codex matrix cell; codex effort is an explicit floor.
    assert MR.codex_effort_for_kind("pilot") == "medium"


def test_model_family():
    assert MR.model_family("claude", "opus-5") == "anthropic"
    assert MR.model_family("codex", "gpt-5.6-sol") == "openai"
    assert MR.model_family("cursor", "composer-2.5") == "xai"
    assert MR.model_family("cursor", "cursor-grok-4.5") == "xai"
    assert MR.model_family("cursor", "nope") is None


def test_derivation_helpers():
    assert MR.known_claude_models() == ("haiku", "sonnet", "opus", "fable")
    assert MR.codex_models() == ("gpt-5.6-terra", "gpt-5.6-sol")
    assert MR.codex_model_strength() == ("gpt-5.6-terra", "gpt-5.6-sol")
    assert MR.codex_pin_roles() == (
        "reviewer",
        "reviewer-deep",
        "code-fixer",
        "implementer",
        "pilot",
    )
    assert MR.codex_role_kind() == {
        "reviewer": "review",
        "reviewer-deep": "review-deep",
        "code-fixer": "fix",
        "implementer": "build",
        "pilot": "pilot",
    }
    assert MR.codex_write_pin_roles() == ("code-fixer", "implementer")


def test_codex_effort_for_kind():
    assert MR.codex_effort_for_kind("review") == "high"
    assert MR.codex_effort_for_kind("review-deep") == "xhigh"
    assert MR.codex_effort_for_kind("build") == "high"
    assert MR.codex_effort_for_kind("fix") == "high"
    assert MR.codex_effort_for_kind("brief-check") == "xhigh"
    assert MR.codex_effort_for_kind("pilot") == "medium"
    assert MR.codex_effort_for_kind("unknown-kind") == "high"
    assert MR.codex_effort_for_kind(MR._ROLE_META["reviewer"]["codex_kind"]) == (
        MR.matrix_config("reviewer", "codex")[1]
    )
    assert MR.codex_effort_for_kind(MR._ROLE_META["reviewer-deep"]["codex_kind"]) == (
        MR.matrix_config("reviewer-deep", "codex")[1]
    )


def test_codex_peer_for_claude_tier():
    with pytest.raises(ValueError, match="fable"):
        MR.codex_peer_for_claude_tier("fable")
    assert MR.codex_peer_for_claude_tier("opus") == "gpt-5.6-sol"
    assert MR.codex_peer_for_claude_tier("sonnet") == "gpt-5.6-terra"
    assert MR.codex_peer_for_claude_tier("bogus") == "gpt-5.6-sol"


def test_validate_config_cases():
    assert MR.validate_config("codex", "gpt-5.6-sol", "high") == (True, None)
    ok, reason = MR.validate_config("codex", "gpt-5.6-sol", "banana")
    assert ok is False and reason
    ok, reason = MR.validate_config("codex", "gpt-5.6-sol", "max", allow_override_only=False)
    assert ok is False and "override" in reason.lower()
    assert MR.validate_config("codex", "gpt-5.6-sol", "max", allow_override_only=True) == (True, None)
    ok, reason = MR.validate_config("cursor", "composer-2.5", "high")
    assert ok is False and reason
    assert MR.validate_config("cursor", "composer-2.5", None) == (True, None)
    assert MR.validate_config("cursor", "cursor-grok-4.5", "high") == (True, None)
    ok, reason = MR.validate_config("claude", "fable-5", "high", allow_override_only=False)
    assert ok is False and "override" in reason.lower()
    assert MR.validate_config("claude", "fable-5", "high", allow_override_only=True) == (True, None)
    ok, reason = MR.validate_config("codex", "fable-5", "high")
    assert ok is False and "not registered" in reason


def test_dispatch_token():
    assert MR.dispatch_token("claude", "sonnet-5") == "sonnet"
    assert MR.dispatch_token("codex", "gpt-5.6-sol") == "gpt-5.6-sol"
    assert MR.dispatch_token("cursor", "composer-2.5") == "composer-2.5"
    assert MR.dispatch_token("cursor", "cursor-grok-4.5", "high") == "cursor-grok-4.5-high"
    for vendor in MR.vendors():
        for model_id in MR._MODELS.get(vendor, {}):
            tok = MR.dispatch_token(vendor, model_id, "high" if vendor != "cursor" else None)
            if tok is not None:
                assert "-fast" not in tok


def test_escalate():
    assert MR.escalate("claude", "sonnet-5", "high") == ("claude", "opus-5", "high")
    assert MR.escalate("cursor", "cursor-grok-4.5", "high") == ("claude", "haiku-4.5", "medium")
    assert MR.escalate("claude", "fable-5", "high") is None


def test_fable_never_default():
    assert MR._MODELS["claude"]["fable-5"]["override_only"] is True
    for role in MR.roles():
        for vendor in MR.vendors():
            cell = MR.matrix_config(role, vendor)
            if cell is not None:
                assert cell[0] != "fable-5"
    for vendor in MR.vendors():
        for model_id, _ in MR.ladder(vendor):
            assert model_id != "fable-5"


_REVIEW_ROLES = ("reviewer", "reviewer-deep", "verifier")


def test_family_for_review_roles():
    assert MR.family_for("reviewer-deep", "claude") == "anthropic"
    assert MR.family_for("reviewer-deep", "codex") == "openai"
    assert MR.family_for("reviewer-deep", "cursor") == "xai"
    assert MR.family_for("implementer", "cursor") == "xai"
    assert MR.family_for("synthesis", "codex") is None
    for role in _REVIEW_ROLES:
        for vendor in MR.vendors():
            cell = MR.matrix_config(role, vendor)
            if cell is None:
                assert MR.family_for(role, vendor) is None
                continue
            model_id, _ = cell
            assert MR.family_for(role, vendor) == MR.model_family(vendor, model_id)


def test_allowlist():
    assert MR.allowlist("reviewer-deep", "cursor") == (("cursor-grok-4.5", "high"),)
    assert MR.allowlist("implementer", "cursor") == (
        ("composer-2.5", None),
        ("cursor-grok-4.5", "high"),
    )
    impl_claude = MR.allowlist("implementer", "claude")
    assert impl_claude[0] == ("sonnet-5", "high")
    assert ("haiku-4.5", "medium") not in impl_claude
    assert MR.allowlist("synthesis", "codex") == ()


def test_is_allowed():
    assert MR.is_allowed("reviewer-deep", "cursor", "cursor-grok-4.5", "high") is True
    assert MR.is_allowed("reviewer-deep", "cursor", "composer-2.5", None) is False
    assert MR.is_allowed("implementer", "cursor", "composer-2.5", None) is True
    assert MR.is_allowed("reviewer-deep", "cursor", "gpt-5.3-codex", "high") is False
    assert MR.is_allowed("reviewer-deep", "cursor", "cursor-grok-4.5", "low") is False
    assert MR.is_allowed(None, "cursor", "cursor-grok-4.5", "high") is False
    assert MR.is_allowed("reviewer-deep", None, "cursor-grok-4.5", "high") is False
    assert MR.is_allowed("reviewer-deep", "cursor", None, "high") is False
    assert MR.is_allowed("reviewer-deep", "cursor", "cursor-grok-4.5", None) is False


def test_parse_dispatch_token_vendors():
    assert MR.parse_dispatch_token("claude", "opus") == ("opus-5", None)
    assert MR.parse_dispatch_token("claude", "fable") == ("fable-5", None)
    assert MR.parse_dispatch_token("codex", "gpt-5.6-sol") == ("gpt-5.6-sol", None)
    assert MR.parse_dispatch_token("cursor", "composer-2.5") == ("composer-2.5", None)
    assert MR.parse_dispatch_token("cursor", "cursor-grok-4.5-high") == (
        "cursor-grok-4.5",
        "high",
    )
    assert MR.parse_dispatch_token("cursor", "cursor-grok-4.5") is None
    assert MR.parse_dispatch_token("cursor", "cursor-grok-4.5-max") is None
    assert MR.parse_dispatch_token("nope", "opus") is None
    assert MR.parse_dispatch_token("claude", 42) is None
    assert MR.parse_dispatch_token(None, "opus") is None
    assert MR.parse_dispatch_token("claude", "garbage-token") is None


def test_dispatch_vocabulary_round_trip():
    for role in MR.roles():
        for vendor in MR.vendors():
            for m, e in MR.allowlist(role, vendor):
                tok = MR.dispatch_token(vendor, m, e)
                assert tok is not None
                parsed = MR.parse_dispatch_token(vendor, tok)
                assert parsed is not None
                m2, e2 = parsed
                assert m2 == m
                assert e2 in (None, e)
                if e2 is not None:
                    assert e2 == e
                r_id = MR.resolve_dispatch(role, vendor, m, e)
                assert r_id["ok"] is True
                assert (r_id["model_id"], r_id["effort"], r_id["dispatch_token"]) == (
                    m,
                    e,
                    tok,
                )
                r_tok = MR.resolve_dispatch(role, vendor, tok, e)
                assert r_tok["ok"] is True
                assert (r_tok["model_id"], r_tok["effort"], r_tok["dispatch_token"]) == (
                    m,
                    e,
                    tok,
                )
                r_tok_none = MR.resolve_dispatch(role, vendor, tok, None)
                assert r_tok_none["ok"] is True
                assert (r_tok_none["model_id"], r_tok_none["effort"]) in MR.allowlist(
                    role, vendor
                )


def test_resolve_dispatch_seat_default():
    for role in MR.roles():
        for vendor in MR.vendors():
            pairs = MR.allowlist(role, vendor)
            if not pairs:
                continue
            cell = MR.matrix_config(role, vendor)
            assert cell is not None
            r = MR.resolve_dispatch(role, vendor)
            assert r["ok"] is True
            assert r["effort_source"] == "seat-default"
            assert (r["model_id"], r["effort"]) == cell


def test_resolve_dispatch_reviewer_deep_cursor_registry_id():
    r = MR.resolve_dispatch("reviewer-deep", "cursor", "cursor-grok-4.5")
    assert r["ok"] is True
    assert (r["model_id"], r["effort"], r["dispatch_token"]) == (
        "cursor-grok-4.5",
        "high",
        "cursor-grok-4.5-high",
    )


def test_resolve_dispatch_codex_lowest_rung():
    r = MR.resolve_dispatch("reviewer", "codex", "gpt-5.6-sol")
    assert r["ok"] is True
    assert r["effort"] == "high"
    assert r["effort_source"] == "resolved-lowest-rung"


def test_resolve_dispatch_fail_closed_edges():
    r = MR.resolve_dispatch(42, "cursor")
    assert r["ok"] is False and r["reason"] and r["candidates"] == []

    r = MR.resolve_dispatch("reviewer", 99)
    assert r["ok"] is False and r["reason"] and r["candidates"] == []

    r = MR.resolve_dispatch("reviewer", "nope")
    assert r["ok"] is False and "unknown vendor" in r["reason"]
    assert r["candidates"] == []

    r = MR.resolve_dispatch("not-a-role", "cursor")
    assert r["ok"] is False and "unknown role" in r["reason"]
    assert r["candidates"] == []

    r = MR.resolve_dispatch("synthesis", "codex")
    assert r["ok"] is False and "no sanctioned model" in r["reason"]
    assert r["candidates"] == []

    r = MR.resolve_dispatch("mechanical", "codex")
    assert r["ok"] is False and r["reason"]

    r = MR.resolve_dispatch("reviewer-deep", "cursor", "not-a-model")
    assert r["ok"] is False and "allowlist" in r["reason"]

    r = MR.resolve_dispatch("reviewer-deep", "cursor", "composer-2.5")
    assert r["ok"] is False and "allowlist" in r["reason"]

    r = MR.resolve_dispatch(
        "reviewer-deep", "cursor", "cursor-grok-4.5", "low"
    )
    assert r["ok"] is False and "allowlist" in r["reason"]

    r = MR.resolve_dispatch(
        "reviewer-deep", "cursor", "cursor-grok-4.5-high", "low"
    )
    assert r["ok"] is False and "conflicts" in r["reason"]

    r = MR.resolve_dispatch("reviewer", "claude", "fable-5", "high")
    assert r["ok"] is False and r["reason"]

    r = MR.resolve_dispatch("reviewer", "claude", "fable", "high")
    assert r["ok"] is False and r["reason"]

    r = MR.resolve_dispatch("reviewer", "cursor", [], None)
    assert r["ok"] is False and r["reason"]
    assert r["candidates"] == list(MR.allowlist("reviewer", "cursor"))

    r = MR.resolve_dispatch("reviewer", "cursor", "cursor-grok-4.5", 99)
    assert r["ok"] is False and r["reason"]


def test_claude_alias_resolution_record_matches_registry_ids():
    """#639: a claude model id is a LABEL for what its tier alias serves, so an id bumped without
    re-probing the harness is invisible. Pin the two together: every claude model's dispatch alias
    must appear in the verified resolution record, and the recorded harness model must be that
    registry id in harness spelling (dots become dashes; a date suffix is allowed)."""
    record = MR.CLAUDE_ALIAS_RESOLUTION["resolved"]
    claude_models = MR._MODELS["claude"]
    assert set(record) == {rec["dispatch"] for rec in claude_models.values()}
    for model_id, rec in claude_models.items():
        resolved = record[rec["dispatch"]]
        expected_prefix = "claude-" + model_id.replace(".", "-")
        assert resolved.startswith(expected_prefix), (model_id, resolved, expected_prefix)
    assert MR.CLAUDE_ALIAS_RESOLUTION["harness"].startswith("claude-code/")


def test_cursor_first_party_models_are_one_family():
    """#651 (owner-ratified 2026-07-26): independence is never satisfied between two cursor
    first-party models. Both carry `xai`, so no role pairing can present one as independent of the
    other — this is exactly the condition round_driver._auditor_vendor keys on."""
    assert MR.model_family("cursor", "composer-2.5") == "xai"
    assert MR.model_family("cursor", "cursor-grok-4.5") == "xai"
    assert len({MR.model_family("cursor", m) for m in MR._MODELS["cursor"]}) == 1
    assert MR.family_for("code-fixer", "cursor") == "xai"
    assert MR.family_for("verifier", "cursor") == "xai"
    assert MR.family_for("implementer", "cursor") == MR.family_for("reviewer-deep", "cursor")
