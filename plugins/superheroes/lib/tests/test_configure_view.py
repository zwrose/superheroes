import json
import os
import subprocess

import core_md
import configure_view as cv
import guardian_store as gs
import mode_registry as mr
import store_core as sc
from guardian_fixtures import (
    benched_fixture_ledger, init_calibrated_repo, write_guardian_layer, write_ledger,
)


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


def _seed_guardian_view_repo(tmp_path, *, guardian_config=None, ledger_records=None,
                             snapshot=None, vitals_trend=None):
    repo = init_calibrated_repo(tmp_path)
    root = str(tmp_path / "store")
    mr.write_registry(repo, mr.IN_REPO, "rk", root=root)
    if guardian_config is not None:
        write_guardian_layer(tmp_path, guardian_config)
    if ledger_records is not None:
        write_ledger(tmp_path, ledger_records, root=root)
    if snapshot is not None:
        os.makedirs(gs.guardian_dir(repo, root), exist_ok=True)
        sc.atomic_write(gs.snapshot_path(repo, root), json.dumps(snapshot, indent=2) + "\n")
    if vitals_trend is not None:
        os.makedirs(gs.guardian_dir(repo, root), exist_ok=True)
        sc.atomic_write(gs.vitals_path(repo, root), vitals_trend)
    return repo, root


def test_render_guardian_row_with_ledger_and_config(tmp_path):
    repo, root = _seed_guardian_view_repo(
        tmp_path,
        guardian_config={
            "cadence": {"minMerges": 12, "minDays": 7},
            "coverage": [{"path": "README.md", "tool": "renovate"}],
        },
        ledger_records=benched_fixture_ledger(),
        snapshot={"schemaVersion": 1, "sweptSha": "abc1234", "vitals": {}, "lenses": {}},
        vitals_trend=(
            '{"schemaVersion": 1, "file": "guardian-vitals", "created": "2026-07-20"}\n'
            '{"date": "2026-07-20", "sweepId": "s1", "sweptSha": "abc1234", "vitals": {}}\n'
        ),
    )
    screen = cv.render(repo, root=root)
    assert "## Guardian" in screen
    assert "≥12 merges or ≥7 days (tuned)" in screen
    assert "coverage: README.md (renovate)" in screen
    assert "benched lenses:" in screen
    assert "fixture is benched" in screen
    assert "last sweep: abc1234 (2026-07-20)" in screen
    assert "verify command: true" in screen


def test_render_guardian_degrades_without_guardian_store(tmp_path):
    root = _seed_core_and_layer(tmp_path)
    screen = cv.render(str(tmp_path), root=root)
    assert "## Guardian" in screen
    assert "cadence: ≥10 merges or ≥14 days (defaults)" in screen
    assert "coverage: none recorded" in screen
    assert "no sweep history yet" in screen
    assert "## Core" in screen
    assert "verify command: pytest" in screen


def test_render_guardian_degrades_with_empty_config(tmp_path):
    repo, root = _seed_guardian_view_repo(tmp_path, guardian_config={})
    screen = cv.render(repo, root=root)
    assert "cadence: ≥10 merges or ≥14 days (defaults)" in screen
    assert "coverage: none recorded" in screen
    assert "no sweep history yet" in screen


def test_render_guardian_degrades_with_malformed_ledger(tmp_path):
    repo, root = _seed_guardian_view_repo(tmp_path)
    os.makedirs(gs.guardian_dir(repo, root), exist_ok=True)
    sc.atomic_write(gs.ledger_path(repo, root), "# broken\n```json guardian-ledger\n{not json\n```\n")
    screen = cv.render(repo, root=root)
    assert "## Guardian" in screen
    assert "cadence:" in screen
    assert "benched lenses: unknown — ledger unreadable" in screen
    assert "ledger JSON block is malformed" in screen
    assert "benched lenses: none" not in screen
    assert "## Core" in screen
    assert "verify command: true" in screen


def test_render_guardian_partial_ledger_does_not_claim_benched_lenses(tmp_path):
    records = benched_fixture_ledger()
    records.append({
        "id": "invalid-trade",
        "disposition": "accepted",
        "date": "2026-07-01",
        "issue": None,
        "metricAtDisposition": {"metric": 5},
    })
    repo, root = _seed_guardian_view_repo(tmp_path, ledger_records=records)
    screen = cv.render(repo, root=root)
    assert "## Guardian" in screen
    assert "cadence:" in screen
    assert "benched lenses: uncertain — ledger is partial" in screen
    assert "fixture is benched" not in screen
    assert "benched lenses:\n" not in screen


def test_render_guardian_lens_below_floor_not_passing(tmp_path):
    records = [{
        "id": "dup:tool:loc-%d" % i,
        "disposition": "triaged-out",
        "date": "2026-07-01",
        "issue": None,
        "metricAtDisposition": None,
        "reason": None,
        "reraiseWhen": None,
        "adjudicatedIn": "s1",
    } for i in range(3)]
    repo, root = _seed_guardian_view_repo(tmp_path, ledger_records=records)
    screen = cv.render(repo, root=root)
    assert "dup — floor not met" in screen
    assert "dup is active" not in screen
