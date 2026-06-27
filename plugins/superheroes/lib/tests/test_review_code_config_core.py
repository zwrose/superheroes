# plugins/superheroes/lib/tests/test_review_code_config_core.py
"""review_code_config.resolve prefers core.md (the migration-triggering seam), else legacy."""
import os
import review_code_config as rcc
import core_md as cm


def _write_core(repo, verify="npm test"):
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "core.md"), "w").write(
        cm.render_core({"verifyCommand": verify, "stackTags": ["node"],
                        "threatModel": "x", "patterns": ""}, "confirmed",
                       "2026-06-26", "2026-06-26"))


def test_resolve_prefers_core_md_verify(tmp_path, monkeypatch):
    # core.md-first: a real core.md under a tmp store resolves the verify command (no legacy).
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _write_core(repo, verify="pnpm check")  # writes .claude/superheroes/core.md (in-repo)
    # Isolate the legacy fallback from the real system store, so the asserted value can ONLY
    # come from core.md — a broken core.md-first path can't pass on a machine whose real store
    # happens to resolve a profile.
    monkeypatch.setattr(rcc.review_store, "resolve",
                        lambda cwd, kind, root: {"exists": False, "path": None})
    out = rcc.resolve(repo, root=store)
    assert out["verifyCommand"] == "pnpm check"


def test_resolve_falls_back_to_legacy_when_core_absent(tmp_path, monkeypatch):
    # fallback: NO core.md → resolve_shared yields nothing → the legacy profile parse wins.
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    prof = os.path.join(repo, "review-profile.md")
    open(prof, "w").write("## Verify\ncommand: make test\n")
    monkeypatch.setattr(rcc.review_store, "resolve",
                        lambda cwd, kind, root: {"exists": True, "path": prof})
    out = rcc.resolve(repo, root=store)
    assert out["verifyCommand"] == "make test"
