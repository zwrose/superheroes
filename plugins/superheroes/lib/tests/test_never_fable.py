"""Never-Fable static tripwire (#299 Phase 3b): Fable must NEVER be reachable from an empty/default
config. The runtime census (dispatch_census) catches a Fable dispatch in a real run; this pins the
STATIC property one layer earlier so a future default can't silently drift to Fable and only surface
in a live harness run.

Covers the three sources the owner named — model_tier DEFAULT_TIERS, the bundle's smart-leaf
resolution chain (__cheapest / __safeSmartDefault / __payloadModel), and KNOWN_MODELS — across BOTH
language twins. The mutation check: setting any default tier to 'fable' (in either twin) fails this
suite; Fable stays a valid-but-explicit-only model (present in KNOWN_MODELS, absent from every
default and every from-empty resolution)."""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import model_tier
import model_tier_overrides

_LIB = os.path.join(os.path.dirname(__file__), "..")


# --- Python twin -----------------------------------------------------------------------------------

def test_no_default_tier_is_fable():
    # THE mutation guard: if anyone sets a DEFAULT_TIERS value to 'fable', this fails.
    assert "fable" not in set(model_tier.DEFAULT_TIERS.values())


def test_every_role_resolves_non_fable_from_empty_config():
    for role in model_tier.ROLES:
        for overrides in (None, {}):
            assert model_tier.resolve_model(role, overrides) != "fable", role
    # the single split/context role too
    for ctx in (None, "code", "doc"):
        assert model_tier.resolve_model("fixer", None, ctx) != "fable"


def test_bundle_smart_leaf_chain_never_fable_py_side():
    # The exact expressions bundle_showrunner.js's wrapper uses, resolved through the Python twin:
    #   __cheapest()        = DEFAULT_TIERS.mechanical
    #   __safeSmartDefault()= resolveModel('synthesis', null, null)
    #   __payloadModel()    = resolveModel('fixer', overrides, 'code')  (base, empty overrides)
    assert model_tier.DEFAULT_TIERS["mechanical"] != "fable"
    assert model_tier.resolve_model("synthesis", None, None) != "fable"
    assert model_tier.resolve_model("fixer", None, "code") != "fable"


def test_fable_is_a_known_but_non_default_model():
    # Fable is VALID (a legit override target) — the invariant is that it's never a DEFAULT, so it can
    # only appear via an explicit profile/override, never from an empty config.
    assert "fable" in model_tier_overrides.KNOWN_MODELS
    assert "fable" not in set(model_tier.DEFAULT_TIERS.values())


def test_fable_reachable_only_via_explicit_override():
    # Proof of the escape hatch: fable requires an EXPLICIT per-role override; without one, never.
    assert model_tier.resolve_model("reviewer", {"reviewer": "fable"}) == "fable"
    assert model_tier.resolve_model("reviewer", {}) != "fable"


# --- JS twin (bundle_showrunner.js's actual resolution home) ---------------------------------------

def _node_model_tier():
    out = subprocess.check_output(["node", "-e", (
        "const m=require('./model_tier.js');"
        "process.stdout.write(JSON.stringify({"
        "defaults:m.DEFAULT_TIERS, known:m.KNOWN_MODELS,"
        "cheapest:m.DEFAULT_TIERS.mechanical,"
        "safeSmartDefault:m.resolveModel('synthesis',null,null),"
        "payload:m.resolveModel('fixer',null,'code')}))")],
        cwd=_LIB, encoding="utf-8")
    return json.loads(out)


def test_js_twin_defaults_and_chain_never_fable():
    m = _node_model_tier()
    assert "fable" not in set(v for v in m["defaults"].values() if v)
    assert m["cheapest"] != "fable"
    assert m["safeSmartDefault"] != "fable"   # this IS bundle __safeSmartDefault's expression
    assert m["payload"] != "fable"
    assert "fable" in m["known"]              # valid-but-explicit-only, mirrors the Python side


def test_bundle_smart_leaf_chain_points_at_non_fable_tiers():
    # Static pin on the bundle preamble so the chain can't be silently repointed at a fable-defaulting
    # tier: __cheapest resolves 'mechanical', __safeSmartDefault resolves 'synthesis' — neither of
    # which may be fable (asserted above). If the bundle repoints these, this test must be revisited.
    with open(os.path.join(_LIB, "bundle_showrunner.js"), encoding="utf-8") as fh:
        src = fh.read()
    assert "DEFAULT_TIERS.mechanical" in src           # __cheapest
    assert "resolveModel('synthesis', null, null)" in src  # __safeSmartDefault
