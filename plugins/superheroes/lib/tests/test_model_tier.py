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


def test_builder_role_defaults_to_opus():
    # The native build-phase implementer is a smart leaf; owner model governance defaults it to opus.
    # This is the tier the preflight readout's builder row AND build_phase.js's dispatch both resolve.
    assert MT.resolve_model("builder") == "opus"


def test_builder_override_wins():
    assert MT.resolve_model("builder", {"builder": "sonnet"}) == "sonnet"
    assert MT.resolve_model("reviewer", {"builder": "sonnet"}) == "sonnet"  # untouched -> default


def test_fixer_role_defaults_to_sonnet_code_fixer():
    assert MT.resolve_model("fixer") == "sonnet"          # no context = code-fixer floor
    assert MT.resolve_model("fixer", context="code") == "sonnet"


def test_fixer_role_resolves_opus_for_doc_reviser():
    assert MT.resolve_model("fixer", context="doc") == "opus"


def test_fixer_override_wins_over_context():
    assert MT.resolve_model("fixer", {"fixer": "haiku"}, context="doc") == "haiku"


def test_cli_resolve_fixer_context_doc(capsys):
    rc = MT.main(["model_tier.py", "resolve", "--role", "fixer", "--context", "doc"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out == {"role": "fixer", "model": "opus"}


def test_author_plan_defaults_to_author_tier():
    assert MT.resolve_model("author-plan") == "opus"


def test_author_plan_follows_author_override_when_unset():
    assert MT.resolve_model("author-plan", {"author": "sonnet"}) == "sonnet"


def test_author_plan_own_override_wins_and_does_not_move_author():
    overrides = {"author-plan": "fable"}
    assert MT.resolve_model("author-plan", overrides) == "fable"
    assert MT.resolve_model("author", overrides) == "opus"   # tasks authoring untouched


def test_author_plan_own_override_beats_author_override():
    assert MT.resolve_model("author-plan", {"author": "sonnet", "author-plan": "fable"}) == "fable"


def test_author_plan_none_override_means_inherit_session():
    assert MT.resolve_model("author-plan", {"author-plan": None}) is None


def test_author_plan_malformed_override_falls_back_to_author_resolution():
    assert MT.resolve_model("author-plan", {"author-plan": ""}) == "opus"
    assert MT.resolve_model("author-plan", {"author-plan": 7, "author": "sonnet"}) == "sonnet"


def test_roles_tuple_includes_split_roles():
    assert "author-plan" in MT.ROLES and "author" in MT.ROLES
