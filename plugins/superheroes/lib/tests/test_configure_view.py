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


def test_render_shows_permission_posture_allow_set(tmp_path, monkeypatch):
    # FR-9: the one-screen view lists the full provenance-valid permission allow set.
    import permission_rules as pr
    import mode_registry as mrmod
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    cdir = os.path.join(str(tmp_path), ".claude", "superheroes")
    os.makedirs(cdir, exist_ok=True)
    sc.atomic_write(os.path.join(cdir, "core.md"),
                    core_md.render_core({"verifyCommand": "pytest", "stackTags": ["py"],
                                         "threatModel": "single-user", "patterns": ""},
                                        "confirmed", "2026-06-27", "2026-06-27"))
    sc.atomic_write(os.path.join(cdir, "review-crew.md"), "<!-- review-crew: v1 -->\nscope\n")
    monkeypatch.setattr(mrmod, "config_key", lambda c: "PKEY")
    pr.set_rule(str(tmp_path), {"family": "test-run", "pattern": r"\bpytest\b"}, root=root)
    screen = cv.render(str(tmp_path), root=root)
    assert "Permission posture" in screen
    assert "test-run" in screen


def test_render_permission_posture_empty_when_no_rules(tmp_path, monkeypatch):
    import mode_registry as mrmod
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    cdir = os.path.join(str(tmp_path), ".claude", "superheroes")
    os.makedirs(cdir, exist_ok=True)
    sc.atomic_write(os.path.join(cdir, "core.md"),
                    core_md.render_core({"verifyCommand": "pytest", "stackTags": ["py"],
                                         "threatModel": "single-user", "patterns": ""},
                                        "confirmed", "2026-06-27", "2026-06-27"))
    sc.atomic_write(os.path.join(cdir, "review-crew.md"), "<!-- review-crew: v1 -->\nscope\n")
    monkeypatch.setattr(mrmod, "config_key", lambda c: "EMPTYKEY")
    screen = cv.render(str(tmp_path), root=root)
    assert "Permission posture" in screen   # section present even with no rules, never a silent skip
    assert "Audit record: none" in screen    # FR-7: no seed yet -> audit absent, surfaced not skipped


def test_render_shows_permission_audit_count_after_seed(tmp_path, monkeypatch):
    # FR-7: once the routine families are seeded, the view surfaces the audit record's count.
    import permission_rules as pr
    import mode_registry as mrmod
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    cdir = os.path.join(str(tmp_path), ".claude", "superheroes")
    os.makedirs(cdir, exist_ok=True)
    sc.atomic_write(os.path.join(cdir, "core.md"),
                    core_md.render_core({"verifyCommand": "pytest", "stackTags": ["py"],
                                         "threatModel": "single-user", "patterns": ""},
                                        "confirmed", "2026-06-27", "2026-06-27"))
    sc.atomic_write(os.path.join(cdir, "review-crew.md"), "<!-- review-crew: v1 -->\nscope\n")
    monkeypatch.setattr(mrmod, "config_key", lambda c: "SEEDKEY")
    pr.seed_default_rules(str(tmp_path), root=root)
    expected = len(pr.audit(str(tmp_path), root=root))
    screen = cv.render(str(tmp_path), root=root)
    assert f"Audit record: {expected} observed command" in screen


def test_render_shows_effective_model_tiers(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    cdir = os.path.join(str(tmp_path), ".claude", "superheroes")
    os.makedirs(cdir, exist_ok=True)
    sc.atomic_write(os.path.join(cdir, "core.md"),
                    core_md.render_core({"verifyCommand": "pytest", "stackTags": ["py"],
                                         "threatModel": "single-user", "patterns": ""},
                                        "confirmed", "2026-06-27", "2026-06-27"))
    sc.atomic_write(os.path.join(cdir, "review-crew.md"),
                    "<!-- review-crew: v1 -->\nscope\n\n## Model tiers\nreviewer: fable\n")
    screen = cv.render(str(tmp_path), root=root)
    assert "## Model tiers" in screen
    assert "reviewer: fable" in screen
    assert "synthesis: opus" in screen
    assert "mechanical: haiku" in screen


def test_render_shows_engine_preferences_and_codex_model_pins(tmp_path):
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    cdir = os.path.join(str(tmp_path), ".claude", "superheroes")
    os.makedirs(cdir, exist_ok=True)
    sc.atomic_write(os.path.join(cdir, "core.md"),
                    core_md.render_core({"verifyCommand": "pytest", "stackTags": ["py"],
                                         "threatModel": "single-user", "patterns": "",
                                         "enginePreferences": {
                                             "reviewer": "codex", "implementation": "claude",
                                             "planAuthor": "codex", "effort": {"review": "high"},
                                             "codexModels": {"reviewer": "gpt-5.5"}}},
                                        "confirmed", "2026-07-12", "2026-07-12"))
    sc.atomic_write(os.path.join(cdir, "review-crew.md"), "<!-- review-crew: v1 -->\nscope\n")
    screen = cv.render(str(tmp_path), root=root)
    assert "## Engine preferences" in screen
    assert "reviewer: codex" in screen and "implementation: claude" in screen
    assert "planAuthor: codex" in screen
    assert "reviewer: gpt-5.5" in screen
    assert "effort overrides: review=high" in screen


def test_render_surfaces_rejected_codex_pins(tmp_path):
    # #409: a hand-edited invalid Codex pin (unknown model, or gpt-5.5 + a max-effort role) must be
    # surfaced as rejected — never displayed as if active. The view mirrors the preflight readout:
    # valid pins under "Codex model pins", rejected ones under a "Rejected Codex model pins" sub-list.
    _init_repo(tmp_path, "git@github.com:o/r.git")
    root = str(tmp_path / "store")
    mr.write_registry(str(tmp_path), mr.IN_REPO, "rk", root=root)
    cdir = os.path.join(str(tmp_path), ".claude", "superheroes")
    os.makedirs(cdir, exist_ok=True)
    sc.atomic_write(os.path.join(cdir, "core.md"),
                    core_md.render_core({"verifyCommand": "pytest", "stackTags": ["py"],
                                         "threatModel": "single-user", "patterns": "",
                                         "enginePreferences": {
                                             "reviewer": "codex", "implementation": "codex",
                                             "planAuthor": "claude", "effort": {"build": "max"},
                                             "codexModels": {"reviewer": "gpt-5.6-sol",
                                                             "builder": "gpt-5.5",
                                                             "bogus-role": "gpt-5.6-sol"}}},
                                        "confirmed", "2026-07-14", "2026-07-14"))
    sc.atomic_write(os.path.join(cdir, "review-crew.md"), "<!-- review-crew: v1 -->\nscope\n")
    screen = cv.render(str(tmp_path), root=root)
    # the one valid pin still shows as active
    assert "Codex model pins:" in screen
    assert "reviewer: gpt-5.6-sol" in screen
    # the rejected pins are surfaced as rejected and flagged
    assert "Rejected Codex model pins" in screen
    assert "builder: gpt-5.5 + max is invalid ⚠" in screen
    assert "bogus-role: unknown role 'bogus-role' rejected ⚠" in screen
    # ...and are NOT shown in the ACTIVE pins block (the exact bug fix #1 removes: rendering the raw
    # core.md map would print `builder`/`bogus-role` as active). Slice the active block and assert.
    active = screen.split("Codex model pins:")[1].split("Rejected Codex model pins")[0]
    assert "reviewer: gpt-5.6-sol" in active
    assert "builder" not in active
    assert "bogus-role" not in active
