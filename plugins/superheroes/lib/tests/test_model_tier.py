import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_MOD = os.path.join(_HERE, "..", "model_tier.py")


def _load():
    spec = importlib.util.spec_from_file_location("model_tier", _MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MT = _load()


def test_defaults_per_role():
    assert MT.resolve_model("orchestrator") is None        # inherit session
    assert MT.resolve_model("reviewer") == "sonnet"
    assert MT.resolve_model("reviewer-deep") == "opus"
    assert MT.resolve_model("mechanical") == "haiku"


def test_verifier_role_defaults_to_opus():
    assert MT.resolve_model("verifier") == "opus"
    assert "verifier" in MT.ROLES and "verifier" in MT.DEFAULT_TIERS


def test_profile_override_wins():
    overrides = {"mechanical": "sonnet"}
    assert MT.resolve_model("mechanical", overrides) == "sonnet"
    assert MT.resolve_model("reviewer", overrides) == "sonnet"   # untouched -> default


def test_unknown_role_falls_back_to_reviewer_default():
    assert MT.resolve_model("bogus") == "sonnet"


def test_malformed_override_falls_open_to_default():
    assert MT.resolve_model("reviewer", {"reviewer": ""}) == "sonnet"     # empty
    assert MT.resolve_model("reviewer", {"reviewer": 7}) == "sonnet"       # non-str
    assert MT.resolve_model("reviewer", "not-a-dict") == "sonnet"          # bad container


def test_cli_resolve(capsys):
    rc = MT.main(["model_tier.py", "resolve", "--role", "mechanical"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out == {"role": "mechanical", "model": "haiku"}


def test_cli_ignores_malformed_overrides_json(capsys):
    rc = MT.main(["model_tier.py", "resolve", "--role", "reviewer",
                  "--overrides", "{not json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["model"] == "sonnet"  # fail-open


def test_docstring_names_real_consumers():
    doc = MT.__doc__ or ""
    assert "Workhorse is the first consumer" not in doc, "false first-consumer claim still present"
    assert "review-code" in doc, "docstring should name review-code as a real consumer"


def test_synthesis_role_is_opus():
    assert MT.resolve_model("synthesis") == "opus"


def test_code_fixer_role_defaults_to_sonnet():
    assert MT.resolve_model("code-fixer") == "sonnet"


def test_doc_reviser_role_defaults_to_opus():
    assert MT.resolve_model("doc-reviser") == "opus"


def test_code_fixer_override_wins():
    assert MT.resolve_model("code-fixer", {"code-fixer": "haiku"}) == "haiku"


def test_pr_body_role_defaults_to_sonnet():
    # #219: the durable draft-PR body composer (showrunner composePrBody) is a Sonnet leaf.
    assert MT.DEFAULT_TIERS["pr-body"] == "sonnet"
    assert MT.resolve_model("pr-body") == "sonnet"
    assert "pr-body" in MT.ROLES


def test_pr_body_override_wins():
    # An explicit override must reach pr-body SPECIFICALLY — proving it is a real distinct role,
    # not the unknown-role reviewer fallback (which also happens to yield 'sonnet').
    assert MT.resolve_model("pr-body", {"pr-body": "opus"}) == "opus"
    assert MT.resolve_model("reviewer", {"pr-body": "opus"}) == "sonnet"  # untouched -> default


def test_implementer_role_defaults_to_sonnet():
    # v2 delegated work-order implementer (owner-ratified default: sonnet).
    assert MT.resolve_model("implementer") == "sonnet"
    assert MT.DEFAULT_TIERS["implementer"] == "sonnet"
    assert "implementer" in MT.ROLES and "implementer" in MT.DEFAULT_TIERS


def test_implementer_override_wins():
    assert MT.resolve_model("implementer", {"implementer": "opus"}) == "opus"
    assert MT.resolve_model("reviewer", {"implementer": "opus"}) == "sonnet"  # untouched -> default


def test_pilot_role_defaults_to_sonnet():
    # v2 test-pilot executor (owner-ratified default: sonnet).
    assert MT.resolve_model("pilot") == "sonnet"
    assert MT.DEFAULT_TIERS["pilot"] == "sonnet"
    assert "pilot" in MT.ROLES and "pilot" in MT.DEFAULT_TIERS


def test_pilot_override_wins():
    assert MT.resolve_model("pilot", {"pilot": "opus"}) == "opus"
    assert MT.resolve_model("reviewer", {"pilot": "opus"}) == "sonnet"  # untouched -> default


def test_fable_is_never_a_default():
    assert "fable" not in MT.DEFAULT_TIERS.values()


def test_orchestrator_still_resolves_to_none_internally():
    # orchestrator remains internal (inherit the session model) — it is simply no longer
    # owner-configurable (see model_tier_overrides.KNOWN_ROLES), which this module doesn't gate.
    assert MT.resolve_model("orchestrator") is None
