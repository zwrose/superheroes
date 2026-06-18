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
