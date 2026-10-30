"""C1-L9c (#2258): the code-fixer tier role and everything that only served it are gone.

Since C1-L9a the build session applies a review's fixes itself, so the separate fixer's tier role,
its codex pin role, the legacy `fixer` alias machinery, the review-code `fixer` tier, the eval
harness's fixer-vendor override and the subagent-transcript refusal reader have no caller. This file
asserts their absence, and that every family lookup that used the `code-fixer` role answers exactly
as before through `implementer`.
"""
import importlib.util
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_EVAL = os.path.join(os.path.dirname(_LIB), "eval")
for _p in (_LIB, _EVAL):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import core_md  # noqa: E402
import engine_pref  # noqa: E402
import model_registry  # noqa: E402
import model_tier  # noqa: E402
import model_tier_overrides  # noqa: E402
import model_tier_resolve  # noqa: E402
import review_code_config  # noqa: E402
import review_loop_runner  # noqa: E402

_RETIRED = "code-fixer"


# axis: G1 — the registry no longer knows the role on any surface
def test_registry_does_not_know_the_code_fixer_role():
    assert _RETIRED not in model_registry.known_roles()
    assert _RETIRED not in model_registry.model_tier_roles()
    assert _RETIRED not in model_registry.roles()
    assert _RETIRED not in model_registry.codex_pin_roles()
    assert _RETIRED not in model_registry.codex_role_kind()
    assert model_registry.codex_write_pin_roles() == ("implementer",)
    assert model_registry.engine_pref_key(_RETIRED) is None
    assert model_registry.role_read_write(_RETIRED) is None
    assert model_registry.family_for(_RETIRED, "claude") is None


def test_tier_resolution_does_not_know_the_code_fixer_role():
    assert _RETIRED not in model_tier.DEFAULT_TIERS
    assert _RETIRED not in model_tier.ROLES
    assert _RETIRED not in model_tier_resolve._FALLBACK
    assert _RETIRED not in model_tier_overrides.KNOWN_ROLES


def test_resolver_cli_takes_the_unknown_role_path_for_the_retired_role(capsys):
    # an unknown role resolves to the reviewer default (fail-open), never an error
    rc = model_tier_resolve.main(["model_tier_resolve.py", "--role", _RETIRED])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out == {"role": _RETIRED, "model": model_tier.DEFAULT_TIERS["reviewer"],
                   "degraded": False}


# axis: G2 — the review-code config has no fixer tier
def test_review_code_tiers_have_no_fixer_key():
    assert "fixer" not in review_code_config._TIER_ROLE
    assert set(review_code_config._TIER_ROLE) == {"reviewer", "reviewerDeep", "synthesis"}
    assert "fixer" not in review_code_config.resolve_tiers({})


def test_legacy_alias_machinery_is_gone():
    assert not hasattr(engine_pref, "_LEGACY_CODEX_PIN_ALIAS")
    assert not hasattr(engine_pref, "canonical_codex_pin_role")
    assert not hasattr(core_md, "_drop_legacy_codex_pin_aliases")
    assert not hasattr(model_tier_overrides, "_LEGACY_ROLE_ALIAS")


# axis: G3 — the subagent-transcript refusal reader is deleted
def test_observed_refusals_module_is_gone():
    assert importlib.util.find_spec("observed_refusals") is None


def test_eval_harness_ignores_a_fixture_fixer_vendor(tmp_path):
    # "claude" is a value the removed validator used to refuse; the key must now have no effect, so
    # the run completes and the composed seat map's author family stays the build-session vendor's
    assert not hasattr(review_loop_runner, "_validate_fixer_vendor_override")
    assert not hasattr(review_loop_runner, "_EVAL_FIXER_VENDOR")
    assert review_loop_runner._EVAL_BUILD_SESSION_VENDOR == "cursor"
    fixture = {
        "name": "fixer-vendor-ignored",
        "fixerVendor": "claude",
        "reviewerSet": ["security-reviewer"],
        "reviewerEvents": [{"round": 1, "reviewer": "security-reviewer", "findings": [],
                            "usageTotal": 1}],
        "fixEvents": [],
        "maxRounds": 1,
    }
    observed = review_loop_runner.run_fixture(fixture, run_dir=str(tmp_path))
    assert observed["terminal"] != "unexpected-driver-return", observed["terminal"]
    seat_map = observed["_driverReceipt"]["seatMap"]
    expected_family = model_registry.family_for(
        "implementer", review_loop_runner._EVAL_BUILD_SESSION_VENDOR)
    assert expected_family != model_registry.family_for("implementer", "claude")
    assert seat_map["authorFamily"] == expected_family


# axis: G4 — a lookup that used the code-fixer role answers exactly as before through `implementer`.
# Derived from the base: `git show HEAD:plugins/superheroes/lib/model_registry.py` (lines 101-111)
# lists the code-fixer cells identical to the implementer cells, and exec'ing that file at HEAD gave
#   claude: family "anthropic", cell ("sonnet-5.5", "high")
#   codex: family "openai", cell ("gpt-6.1-sol", "high")
#   cursor: family "xai", cell ("composer-2.5", None)
# The cell is pinned beside the family because a model swap inside one maker keeps the family.
_BASE_CODE_FIXER_ANSWER = {
    "claude": ("anthropic", ("sonnet-5.5", "high")),
    "codex": ("openai", ("gpt-6.1-sol", "high")),
    "cursor": ("xai", ("composer-2.5", None)),
}


def test_implementer_answers_exactly_as_the_removed_code_fixer_role_did():
    assert set(_BASE_CODE_FIXER_ANSWER) == set(model_registry.vendors())
    for vendor, (family, cell) in _BASE_CODE_FIXER_ANSWER.items():
        assert model_registry.family_for("implementer", vendor) == family, vendor
        assert tuple(model_registry.matrix_config("implementer", vendor)) == cell, vendor
