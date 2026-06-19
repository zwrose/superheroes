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
    # No --root, real CLAUDE_PLUGIN_ROOT unset: in dogfood the repo root resolves
    # the-architect via --root. Point --root at the repo so the core is found.
    root = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
    rc, out = _run(capsys, "--role", "mechanical", "--root", root)
    assert rc == 0 and out["role"] == "mechanical" and out["model"] == "haiku"
    assert out["degraded"] is False


def test_core_absent_fails_open_to_embedded_default(capsys, tmp_path):
    rc, out = _run(capsys, "--role", "reviewer", "--root", str(tmp_path))
    assert rc == 0 and out["model"] == "sonnet" and out["degraded"] is True


def test_subprocess_garbage_fails_open(capsys, tmp_path, monkeypatch):
    monkeypatch.setattr(MTR, "_resolve", lambda root: "/some/model_tier.py")
    monkeypatch.setattr(MTR, "_subprocess_json", lambda lib, cli: None)
    rc, out = _run(capsys, "--role", "reviewer-deep", "--root", str(tmp_path))
    assert rc == 0 and out["model"] == "opus" and out["degraded"] is True


def test_embedded_fallback_matches_the_core(capsys):
    # _FALLBACK re-encodes the core's DEFAULT_TIERS for the degrade path; guard
    # against silent drift so the fallback never serves a stale tier table.
    root = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
    core = _load(os.path.join(root, "plugins", "the-architect", "lib", "model_tier.py"),
                 "model_tier_core")
    assert MTR._FALLBACK == core.DEFAULT_TIERS
