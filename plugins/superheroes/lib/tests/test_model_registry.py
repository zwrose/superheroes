import copy
import importlib.abc
import importlib.util
import json
import os
import re
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
_MOD = os.path.join(_LIB, "model_registry.py")
_DA_MOD = os.path.join(_LIB, "dispatch_allowlist.py")
_DG_MOD = os.path.join(_LIB, "dispatch_guard.py")
_ED_MOD = os.path.join(_LIB, "engine_dispatch.py")
_SM_MOD = os.path.join(_LIB, "seat_map.py")


def _load():
    spec = importlib.util.spec_from_file_location("model_registry", _MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_dispatch_allowlist():
    spec = importlib.util.spec_from_file_location("dispatch_allowlist", _DA_MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_seat_map():
    spec = importlib.util.spec_from_file_location("seat_map", _SM_MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_engine_dispatch():
    spec = importlib.util.spec_from_file_location("engine_dispatch", _ED_MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MR = _load()
DA = _load_dispatch_allowlist()
SM = _load_seat_map()

_EXPECTED_DEFAULT_CLAUDE_TIERS = {
    "orchestrator": None,
    "reviewer": "sonnet",
    "reviewer-deep": "opus",
    "verifier": "opus",
    "mechanical": "haiku",
    "synthesis": "opus",
    "code-fixer": "sonnet",
    "doc-reviser": "opus",
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
        "implementer",
        "pilot",
    )


def test_default_claude_tiers_migration_pin():
    assert MR.default_claude_tiers() == _EXPECTED_DEFAULT_CLAUDE_TIERS


def test_claude_models_matches_source_keys():
    assert MR.claude_models() == tuple(MR._MODELS["claude"])


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
    assert MR.model_family("claude", "opus-5.5") == "anthropic"
    assert MR.model_family("codex", "gpt-5.6-sol") == "openai"
    assert MR.model_family("cursor", "composer-2.5") == "xai"
    assert MR.model_family("cursor", "cursor-grok-4.6") == "xai"
    assert MR.model_family("cursor", "nope") is None


def test_derivation_helpers():
    assert MR.known_claude_models() == ("haiku", "sonnet", "opus", "fable")
    assert MR.codex_models() == ("gpt-5.6-terra", "gpt-5.6-sol", "gpt-6-astra")
    assert MR.codex_model_strength() == ("gpt-5.6-terra", "gpt-5.6-sol", "gpt-6-astra")
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
    assert MR.validate_config("cursor", "cursor-grok-4.6", "xhigh") == (True, None)
    assert MR.validate_config("cursor", "cursor-grok-4.6", "low") == (
        False,
        "effort 'low' is not valid for model 'cursor-grok-4.6'",
    )
    assert MR.validate_config("cursor", "cursor-grok-4.6", "medium") == (
        False,
        "effort 'medium' is not valid for model 'cursor-grok-4.6'",
    )
    assert MR.validate_config("cursor", "cursor-grok-4.6", "high") == (
        False,
        "effort 'high' is not valid for model 'cursor-grok-4.6'",
    )
    ok, reason = MR.validate_config("claude", "fable-5.1", "high", allow_override_only=False)
    assert ok is False and "override" in reason.lower()
    assert MR.validate_config("claude", "fable-5.1", "high", allow_override_only=True) == (True, None)
    ok, reason = MR.validate_config("codex", "fable-5.1", "high")
    assert ok is False and "not registered" in reason


def test_dispatch_token():
    assert MR.dispatch_token("claude", "sonnet-5") == "sonnet"
    assert MR.dispatch_token("codex", "gpt-5.6-sol") == "gpt-5.6-sol"
    assert MR.dispatch_token("cursor", "composer-2.5") == "composer-2.5"
    assert MR.dispatch_token("cursor", "cursor-grok-4.6", "xhigh") == "cursor-grok-4.6-xhigh"
    assert MR.dispatch_token("cursor", "cursor-grok-4.6", None) is None
    assert MR.dispatch_token("cursor", "cursor-grok-4.6", "fast") is None
    assert MR.dispatch_token("cursor", "cursor-grok-4.6", "high") is None
    for vendor in MR.vendors():
        for model_id in MR._MODELS.get(vendor, {}):
            tok = MR.dispatch_token(vendor, model_id, "high" if vendor != "cursor" else None)
            if tok is not None:
                assert "-fast" not in tok


def test_escalate():
    assert MR.escalate("claude", "sonnet-5", "high") == ("claude", "opus-5.5", "high")
    assert MR.escalate("cursor", "cursor-grok-4.6", "xhigh") == ("claude", "haiku-4.5", "medium")
    assert MR.escalate("claude", "fable-5.1", "high") is None


def test_fable_never_default():
    assert MR._MODELS["claude"]["fable-5.1"]["override_only"] is True
    for role in MR.roles():
        for vendor in MR.vendors():
            cell = MR.matrix_config(role, vendor)
            if cell is not None:
                assert cell[0] != "fable-5.1"
    for vendor in MR.vendors():
        for model_id, _ in MR.ladder(vendor):
            assert model_id != "fable-5.1"


_REVIEW_ROLES = ("reviewer", "reviewer-deep", "verifier", "auditor")


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
    assert MR.allowlist("reviewer-deep", "cursor") == (("cursor-grok-4.6", "xhigh"),)
    assert MR.allowlist("implementer", "cursor") == (
        ("composer-2.5", None),
        ("cursor-grok-4.6", "xhigh"),
    )
    impl_claude = MR.allowlist("implementer", "claude")
    assert impl_claude[0] == ("sonnet-5", "high")
    assert ("haiku-4.5", "medium") not in impl_claude
    assert MR.allowlist("synthesis", "codex") == ()


def test_is_allowed():
    assert MR.is_allowed("reviewer-deep", "cursor", "cursor-grok-4.6", "xhigh") is True
    assert MR.is_allowed("reviewer-deep", "cursor", "composer-2.5", None) is False
    assert MR.is_allowed("implementer", "cursor", "composer-2.5", None) is True
    assert MR.is_allowed("reviewer-deep", "cursor", "gpt-5.3-codex", "high") is False
    assert MR.is_allowed("reviewer-deep", "cursor", "cursor-grok-4.6", "low") is False
    assert MR.is_allowed("reviewer-deep", "cursor", "cursor-grok-4.6", "medium") is False
    assert MR.is_allowed("reviewer-deep", "cursor", "cursor-grok-4.6", "high") is False
    assert MR.is_allowed(None, "cursor", "cursor-grok-4.6", "xhigh") is False
    assert MR.is_allowed("reviewer-deep", None, "cursor-grok-4.6", "xhigh") is False
    assert MR.is_allowed("reviewer-deep", "cursor", None, "xhigh") is False
    assert MR.is_allowed("reviewer-deep", "cursor", "cursor-grok-4.6", None) is False


def test_parse_dispatch_token_vendors():
    assert MR.parse_dispatch_token("claude", "opus") == ("opus-5.5", None)
    assert MR.parse_dispatch_token("claude", "fable") == ("fable-5.1", None)
    assert MR.parse_dispatch_token("codex", "gpt-5.6-sol") == ("gpt-5.6-sol", None)
    assert MR.parse_dispatch_token("cursor", "composer-2.5") == ("composer-2.5", None)
    assert MR.parse_dispatch_token("cursor", "cursor-grok-4.6-xhigh") == (
        "cursor-grok-4.6",
        "xhigh",
    )
    assert MR.parse_dispatch_token("cursor", "cursor-grok-4.6") is None
    assert MR.parse_dispatch_token("cursor", "cursor-grok-4.6-max") is None
    assert MR.parse_dispatch_token("cursor", "cursor-grok-4.6-fast") is None
    assert MR.parse_dispatch_token("cursor", "cursor-grok-4.6-low") is None
    assert MR.parse_dispatch_token("cursor", "cursor-grok-4.6-medium") is None
    assert MR.parse_dispatch_token("cursor", "cursor-grok-4.6-high") is None
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
    r = MR.resolve_dispatch("reviewer-deep", "cursor", "cursor-grok-4.6")
    assert r["ok"] is True
    assert (r["model_id"], r["effort"], r["dispatch_token"]) == (
        "cursor-grok-4.6",
        "xhigh",
        "cursor-grok-4.6-xhigh",
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
        "reviewer-deep", "cursor", "cursor-grok-4.6", "low"
    )
    assert r["ok"] is False and "allowlist" in r["reason"]

    r = MR.resolve_dispatch(
        "reviewer-deep", "cursor", "cursor-grok-4.6-xhigh", "low"
    )
    assert r["ok"] is False and "conflicts" in r["reason"]

    r = MR.resolve_dispatch("reviewer", "claude", "fable-5.1", "high")
    assert r["ok"] is False and r["reason"]

    r = MR.resolve_dispatch("reviewer", "claude", "fable", "high")
    assert r["ok"] is False and r["reason"]

    r = MR.resolve_dispatch("reviewer", "cursor", [], None)
    assert r["ok"] is False and r["reason"]
    assert r["candidates"] == list(MR.allowlist("reviewer", "cursor"))

    r = MR.resolve_dispatch("reviewer", "cursor", "cursor-grok-4.6", 99)
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
        assert re.fullmatch(re.escape(expected_prefix) + r"(-\d{8})?", resolved), (
            model_id, resolved, expected_prefix)
    assert MR.CLAUDE_ALIAS_RESOLUTION["harness"].startswith("claude-code/")


# axis: auditor matrix row is derived from verifier, not an independent literal copy
def test_auditor_cells_track_verifier_cells():
    for vendor in MR.vendors():
        assert MR.matrix_config("auditor", vendor) == MR.matrix_config("verifier", vendor)
    cell = MR.matrix_config("auditor", "codex")
    assert cell is not None
    model_id, effort = cell
    seat = {"vendor": "codex", "model": model_id, "effort": effort, "role": "auditor"}
    proc = subprocess.run(
        [sys.executable, _DG_MOD, "check", "--seat", json.dumps(seat)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, (proc.stdout, proc.stderr)


# axis: legacy journaled claude model ids are compared exactly — no translation at continuation
def test_continuation_refuses_legacy_claude_label_mismatch():
    ED = _load_engine_dispatch()
    opened = {
        "resolvedInputs": {
            "engine": "claude",
            "model": "opus-5",
            "effort": "xhigh",
            "role": "reviewer-deep",
        }
    }
    seat = {
        "vendor": "claude",
        "model": "opus-5.5",
        "effort": "xhigh",
        "role": "reviewer-deep",
    }
    assert ED._continuation_seat_mismatch(opened, seat) == ED.SEAT_REFUSAL_RUN_DIR_MISMATCH
    seat_diff = {
        "vendor": "claude",
        "model": "sonnet-5",
        "effort": "xhigh",
        "role": "reviewer-deep",
    }
    assert ED._continuation_seat_mismatch(opened, seat_diff) == ED.SEAT_REFUSAL_RUN_DIR_MISMATCH


# axis: legacy claude model ids stay unregistered and honored nowhere
def test_legacy_claude_model_ids_stay_unregistered():
    assert MR.validate_config("claude", "opus-5", "xhigh")[0] is False


def test_auditor_and_code_fixer_families_match_per_vendor():
    """This invariant is what makes round_driver._auditor_vendor's same-vendor fallback unreachable
    (#652 rider 4a). If a future registry change breaks the invariant, the fallback becomes reachable
    again and the deleted branch must be reconsidered — so this test failing is a design signal,
    not a test to relax."""
    vendors = MR.vendors()
    assert vendors, "model_registry.vendors() must be non-empty for this invariant"
    for vendor in vendors:
        fixer_fam = MR.family_for("code-fixer", vendor)
        auditor_fam = MR.family_for("auditor", vendor)
        assert fixer_fam is not None, (
            f"code-fixer family_for({vendor!r}) returned None — invariant cannot be evaluated"
        )
        assert auditor_fam is not None, (
            f"auditor family_for({vendor!r}) returned None — invariant cannot be evaluated"
        )
        assert auditor_fam == fixer_fam, (
            vendor, fixer_fam, auditor_fam,
        )


_CURSOR_FIRST_PARTY_REGISTRY_IDS = frozenset({"composer-2.5", "cursor-grok-4.6"})


def test_cursor_registered_models_are_exactly_first_party_pair():
    """#650: cursor CLI billing is first-party only; the registry is the enforcing surface."""
    registered = frozenset(MR.cursor_models())
    assert registered == _CURSOR_FIRST_PARTY_REGISTRY_IDS


def test_cursor_first_party_models_are_one_family():
    """#651 (owner-ratified 2026-07-26): independence is never satisfied between two cursor
    first-party models. Both carry `xai`, so no role pairing can present one as independent of the
    other — this is exactly the condition round_driver._auditor_vendor keys on."""
    assert MR.model_family("cursor", "composer-2.5") == "xai"
    assert MR.model_family("cursor", "cursor-grok-4.6") == "xai"
    assert len({MR.model_family("cursor", m) for m in MR.cursor_models()}) == 1
    assert MR.family_for("code-fixer", "cursor") == "xai"
    assert MR.family_for("verifier", "cursor") == "xai"
    assert MR.family_for("implementer", "cursor") == MR.family_for("reviewer-deep", "cursor")


def test_every_ladder_is_family_uniform():
    """The workhorse charter's maker-family rule states that a rung-up inside ONE engine's ladder no
    longer changes the maker family (#651 merged cursor's two first-party rungs; claude and codex
    were already single-family). That is a property of `_LADDERS` + `_MODELS`, restated in prose —
    so pin it here: the moment a ladder spans two families, this fails and both prose copies
    (skills/workhorse/SKILL.md, CONVENTIONS §7.5) must be revisited."""
    for vendor in MR.vendors():
        rungs = MR.ladder(vendor)
        assert rungs, vendor
        families = {MR.model_family(vendor, model_id) for model_id, _effort in rungs}
        assert None not in families, (vendor, rungs)
        assert len(families) == 1, (
            "ladder for %r spans families %r — the maker-family prose in "
            "skills/workhorse/SKILL.md and CONVENTIONS §7.5 assumes it does not"
            % (vendor, sorted(families)))


def test_claude_dispatch_tokens_returns_ladder_ordered_sanctioned_tiers():
    assert MR.claude_dispatch_tokens() == ("haiku", "sonnet", "opus")


def test_claude_dispatch_tokens_excludes_fable_override_only():
    # fable is override-only and absent from the claude ladder — never a launch default.
    assert "fable" not in MR.claude_dispatch_tokens()


def test_claude_dispatch_tokens_round_trip_through_parse_dispatch_token():
    for token in MR.claude_dispatch_tokens():
        assert MR.parse_dispatch_token("claude", token) is not None, token


# Pre-child head of this work item's child.
_PRE_CHILD_HEAD = "aaf27b8089159c2ea4020b03ccbddcd263c57e8a"
_REGISTRY_PATH = "plugins/superheroes/lib/model_registry.py"


class _GitShowLoader(importlib.abc.Loader):
    def __init__(self, source):
        self._source = source

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        exec(compile(self._source, "<git-show>", "exec"), module.__dict__)


def _load_model_registry_at_sha(sha):
    toplevel = subprocess.run(
        ["git", "-C", _HERE, "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    try:
        proc = subprocess.run(
            ["git", "-C", toplevel, "show", f"{sha}:{_REGISTRY_PATH}"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise AssertionError(
            "commit %s is not available in this checkout — "
            "fetch full history (fetch-depth: 0) to run the git-baseline test"
            % sha
        ) from exc
    name = f"_model_registry_snapshot_{sha[:12]}"
    spec = importlib.util.spec_from_loader(name, _GitShowLoader(proc.stdout))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_LEGACY_MATRIX_MODEL_IDS = {"opus-5": "opus-5.5", "fable-5": "fable-5.1"}


def _matrix_cell_after_legacy_translate(vendor, cell):
    if cell is None:
        return None
    model_id, effort = cell
    if vendor == "claude":
        model_id = _LEGACY_MATRIX_MODEL_IDS.get(model_id, model_id)
    return (model_id, effort)


# axis: reviewer-deep, reviewer, and verifier matrix cells at the live registry match the pre-child head baseline.
def test_matrix_cells_reviewer_roles_unchanged_at_base():
    base = _load_model_registry_at_sha(_PRE_CHILD_HEAD)
    compared = 0
    for role in ("reviewer-deep", "reviewer", "verifier"):
        for vendor in ("claude", "codex", "cursor"):
            live = MR.matrix_config(role, vendor)
            baseline = base.matrix_config(role, vendor)
            assert _matrix_cell_after_legacy_translate(vendor, live) == (
                _matrix_cell_after_legacy_translate(vendor, baseline)
            )
            compared += 1
    assert compared == 9


def _plant_probe_pending_astra(monkeypatch):
    models = copy.deepcopy(MR._MODELS)
    astra = dict(models["codex"]["gpt-6-astra"])
    astra["registration"] = "probe-pending"
    models["codex"]["gpt-6-astra"] = astra
    monkeypatch.setattr(MR, "_MODELS", models)


def test_registered_astra_on_reviewer_deep_allowlist_and_probe_role_admits():
    assert MR.allowlist("reviewer-deep", "codex") == (
        MR.matrix_config("reviewer-deep", "codex"),
        ("gpt-6-astra", "high"),
    )
    assert MR.allowlist("registration-probe", "codex") == (("gpt-6-astra", "high"),)
    assert MR.ladder("codex")[-1] == ("gpt-6-astra", "high")
    assert MR.codex_effort_for_kind("review") == MR.matrix_config("reviewer", "codex")[1]
    r = MR.resolve_dispatch("registration-probe", "codex")
    assert r["ok"] is True
    assert r["effort"] == "high"


def test_registered_astra_accepted_on_reviewer_deep_explicit_dispatch():
    r = MR.resolve_dispatch("reviewer-deep", "codex", "gpt-6-astra", None)
    assert r["ok"] is True
    assert r["effort"] == "high"
    assert r["effort_source"] == "resolved-unique"


def test_escalate_from_sol_xhigh_returns_registered_astra():
    result = MR.escalate("codex", "gpt-5.6-sol", "xhigh")
    assert result == ("codex", "gpt-6-astra", "high")


def test_planted_probe_pending_astra_hidden_from_ladder_and_allowlist(monkeypatch):
    _plant_probe_pending_astra(monkeypatch)
    assert ("gpt-6-astra", "high") not in MR.ladder("codex")
    assert MR.allowlist("reviewer-deep", "codex") == (
        MR.matrix_config("reviewer-deep", "codex"),
    )


def test_codex_pin_verdict_planted_pending_astra_on_reviewer_deep(monkeypatch):
    _plant_probe_pending_astra(monkeypatch)
    ok, reason = MR.codex_pin_verdict("reviewer-deep", "gpt-6-astra")
    assert ok is False
    assert reason.startswith("pin-probe-pending:")


def test_codex_pin_verdict_registered_astra_on_reviewer_deep():
    ok, reason = MR.codex_pin_verdict("reviewer-deep", "gpt-6-astra")
    assert ok is True
    assert reason is None
    ok_sol, _ = MR.codex_pin_verdict("reviewer-deep", "gpt-5.6-sol")
    assert ok_sol is True
    r_sol = MR.resolve_dispatch("reviewer-deep", "codex", "gpt-5.6-sol", None)
    assert r_sol["ok"] is True
    assert r_sol["effort"] == "xhigh"


def test_codex_pin_verdict_astra_on_reviewer_refused_pin_role():
    ok, reason = MR.codex_pin_verdict("reviewer", "gpt-6-astra")
    assert ok is False
    assert reason.startswith("pin-role-not-eligible:")


def test_codex_pin_verdict_refuses_pins_off_the_role_allowlist():
    ok, reason = MR.codex_pin_verdict("reviewer-deep", "gpt-5.6-terra")
    assert ok is False
    assert reason.startswith("pin-not-on-allowlist:")
    assert "(gpt-5.6-sol, xhigh)" in reason
    ok, reason = MR.codex_pin_verdict("pilot", "gpt-5.6-terra")
    assert ok is False
    assert reason.startswith("pin-not-on-allowlist:")


@pytest.mark.parametrize("registry_state", ["registered-astra", "planted-probe-pending"])
def test_pin_judges_agree_writer_guard_and_composer(monkeypatch, registry_state):
    # bite-axis: one judge — writer, composer and guard agree on every codex role pin in both registry states
    if registry_state == "planted-probe-pending":
        models = copy.deepcopy(MR._MODELS)
        astra = dict(models["codex"]["gpt-6-astra"])
        astra["registration"] = "probe-pending"
        models["codex"]["gpt-6-astra"] = astra
        monkeypatch.setattr(MR, "_MODELS", models)
        monkeypatch.setattr(SM.model_registry, "_MODELS", models)
        monkeypatch.setattr(DA.model_registry, "_MODELS", models)
    carve_out_count = 0
    for role in MR.codex_pin_roles():
        for model in MR.codex_models():
            ok, reason = MR.codex_pin_verdict(role, model)
            guard_accepts = DA.validate(role, "codex", model, None)["ok"]
            if ok is False and reason.startswith("pin-role-not-eligible:"):
                carve_out_count += 1
            else:
                assert ok == guard_accepts
            if role in SM.panel_pin_tiers():
                _m, _e, info = SM._cell(role, "codex", {role: model})
                assert info["honored"] == ok
    if registry_state == "planted-probe-pending":
        assert carve_out_count == 0
        ok, reason = MR.codex_pin_verdict("reviewer-deep", "gpt-6-astra")
        assert ok is False
        assert reason.startswith("pin-probe-pending:")
        model, effort, info = SM._cell("reviewer-deep", "codex", {"reviewer-deep": "gpt-6-astra"})
        assert (model, effort) == ("gpt-5.6-sol", "xhigh")
        assert info["honored"] is False
    else:
        assert carve_out_count == len(MR.codex_pin_roles()) - 1
        ok, reason = MR.codex_pin_verdict("reviewer-deep", "gpt-6-astra")
        assert ok is True
        assert reason is None
        model, effort, info = SM._cell("reviewer-deep", "codex", {"reviewer-deep": "gpt-6-astra"})
        assert (model, effort) == ("gpt-6-astra", "high")
        assert info["honored"] is True


def test_codex_pin_verdict_non_str_inputs():
    ok, reason = MR.codex_pin_verdict(42, "gpt-5.6-sol")
    assert ok is False
    assert "unknown role" in reason
    ok, reason = MR.codex_pin_verdict("reviewer", 123)
    assert ok is False
    assert "unknown model" in reason


def test_host_family_table():
    assert MR.host_family("claude-opus-5") == "anthropic"
    assert MR.host_family("opus") == "anthropic"
    assert MR.host_family("gpt-6-astra") == "openai"
    assert MR.host_family("composer-2.5") == "xai"
    assert MR.host_family("") is None
    assert MR.host_family(None) is None
    assert MR.host_family(123) is None
    assert MR.host_family("mystery") is None
