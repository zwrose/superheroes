import os
import subprocess

import core_md
import configure_view as cv
import mode_registry as mr
import store_core as sc


def _init_repo(d, remote=None):
    subprocess.run(["git", "-C", str(d), "init", "-q"], check=True)
    if remote:
        subprocess.run(["git", "-C", str(d), "remote", "add", "origin", remote], check=True)


def test_render_shows_core_layers_and_is_read_only(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    cdir = os.path.join(str(tmp_path), ".claude", "superheroes")
    os.makedirs(cdir, exist_ok=True)
    sc.atomic_write(os.path.join(cdir, "core.md"),
                    core_md.render_core({"verifyCommand": "pytest", "stackTags": ["py"],
                                         "threatModel": "single-user", "patterns": "x"},
                                        "confirmed", "2026-06-27", "2026-06-27"))
    sc.atomic_write(os.path.join(cdir, "review-crew.md"), "<!-- review-crew: v1 -->\nscope\n")
    before = sorted(os.listdir(cdir))
    screen = cv.render(str(tmp_path), root=root)
    assert "pytest" in screen and "review-crew" in screen and "single-user" in screen
    assert sorted(os.listdir(cdir)) == before   # render wrote nothing (FR-18)


def test_render_shows_storage_health_line(tmp_path):
    import json
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.GLOBAL, "rk", root=root)  # mints the live store
    orphan = os.path.join(root, "projects", "eeee000000000001")
    os.makedirs(orphan)
    sc.atomic_write(os.path.join(orphan, "meta.json"),
                    json.dumps({"schemaVersion": 1, "sourcePath": str(tmp_path / "gone")}))
    screen = cv.render(str(tmp_path), root=root)
    assert "storage health" in screen
    assert "1 orphaned" in screen


def _seed_core_and_layer(tmp_path, engine_preferences=None):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    cdir = os.path.join(str(tmp_path), ".claude", "superheroes")
    os.makedirs(cdir, exist_ok=True)
    facts = {"verifyCommand": "pytest", "stackTags": ["py"], "threatModel": "single-user",
              "patterns": ""}
    if engine_preferences is not None:
        facts["enginePreferences"] = engine_preferences
    sc.atomic_write(os.path.join(cdir, "core.md"),
                    core_md.render_core(facts, "confirmed", "2026-07-19", "2026-07-19"))
    sc.atomic_write(os.path.join(cdir, "review-crew.md"), "<!-- review-crew: v1 -->\nscope\n")
    return root


def test_render_shows_dispatch_calibration_defaults(tmp_path):
    # v2: no enginePreferences block set — every dispatch role falls open to its own default
    # (implementer/pilot -> claude+sonnet; brief-check reviewer -> the ratified cross-vendor
    # codex default). The retired `## Engine preferences` heading (and its planAuthor: line,
    # plan authoring having been retired) must not reappear.
    root = _seed_core_and_layer(tmp_path)
    screen = cv.render(str(tmp_path), root=root)
    assert "Dispatch calibration" in screen
    assert "implementer — claude — sonnet" in screen
    assert "pilot — claude — sonnet" in screen
    assert "brief-check reviewer — codex" in screen
    assert "planAuthor" not in screen
    assert "Permission posture" not in screen


def test_render_mentions_orchestrator_as_session_not_configurable(tmp_path):
    root = _seed_core_and_layer(tmp_path)
    screen = cv.render(str(tmp_path), root=root)
    assert "orchestrator" in screen
    assert "not" in screen
    assert "configurable" in screen


def test_render_shows_brief_check_claude_fallback_when_configured(tmp_path):
    # An owner-configured `briefCheck: claude` (codex opted out of / unavailable) shows the
    # disclosed smart fallback: a Claude reviewer at a tier UP from the sonnet implementer
    # (engine_pref.BRIEF_CHECK_CLAUDE_FALLBACK_TIER == "opus"), never session-inherited.
    root = _seed_core_and_layer(tmp_path, engine_preferences={"briefCheck": "claude"})
    screen = cv.render(str(tmp_path), root=root)
    assert "brief-check reviewer — claude — opus" in screen


def test_collect_threads_root_into_model_tier_resolution(tmp_path, monkeypatch):
    # Regression (#489): collect() reads core/engine prefs with `root`, so it must resolve the
    # model-tier profile with the SAME root — else a global-store / custom-root project reads its
    # tiers from the default store while its core prefs come from the custom one.
    root = _seed_core_and_layer(tmp_path)
    captured = {}
    orig = cv.model_tier_overrides.resolve_profile_path

    def _spy(cwd=None, root=None):
        captured["root"] = root
        return orig(cwd, root)

    monkeypatch.setattr(cv.model_tier_overrides, "resolve_profile_path", _spy)
    cv.collect(str(tmp_path), root=root)
    assert captured["root"] == root
