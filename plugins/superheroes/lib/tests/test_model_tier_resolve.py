import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MTR = _load(os.path.join(_HERE, "..", "model_tier_resolve.py"), "model_tier_resolve")


def _run(capsys, *args):
    rc = MTR.main(["model_tier_resolve.py", *args])
    return rc, json.loads(capsys.readouterr().out)


def test_resolves_via_core_when_present(capsys):
    # The core is a same-tree sibling now — it always resolves; the call is direct.
    rc, out = _run(capsys, "--role", "mechanical")
    assert rc == 0 and out["role"] == "mechanical" and out["model"] == "haiku"
    assert out["degraded"] is False


def test_core_error_fails_open_to_embedded_default(capsys, monkeypatch):
    # Equivalence note: the old "core absent / subprocess garbage -> fail-open" tests are
    # replaced by the direct-seam core-error branch (the lib is always resolvable in one
    # tree). Posture is UNCHANGED: any core error -> the embedded fallback, degraded True.
    monkeypatch.setattr(MTR.model_tier, "resolve_model",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    rc, out = _run(capsys, "--role", "reviewer")
    assert rc == 0 and out["model"] == "sonnet" and out["degraded"] is True


def test_core_error_fails_open_for_reviewer_deep(capsys, monkeypatch):
    monkeypatch.setattr(MTR.model_tier, "resolve_model",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    rc, out = _run(capsys, "--role", "reviewer-deep")
    assert rc == 0 and out["model"] == "opus" and out["degraded"] is True


def test_embedded_fallback_matches_the_core():
    # _FALLBACK re-encodes the core's DEFAULT_TIERS for the degrade path; guard
    # against silent drift so the fallback never serves a stale tier table. The core
    # is now the in-tree sibling (repointed from plugins/the-architect/lib/model_tier.py).
    core = _load(os.path.join(_HERE, "..", "model_tier.py"), "model_tier_core")
    assert MTR._FALLBACK == core.DEFAULT_TIERS
