"""End-to-end wiring of the #299 dispatch census: acceptance_deps.real_dispatch_census assembles the
readout-expected rows from the run's real resolvers, projects the run's journal, and returns the pure
decider's verdict. Drives the SHIPPED path (real assemble + real journal read) against an out-of-repo
calibration fixture — the seam the pure-decider unit tests don't cover."""
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_deps
import control_plane
import core_md
import engine_detect
import journal

WI = "wi"


def _fixture(tmp_path, monkeypatch, prefs, authorized=True):
    """A git repo with an out-of-repo store holding a CONFIRMED core.md carrying `prefs`, so the real
    resolver path (store-base=None) routes exactly as configured — mirrors test_preflight_readout.
    `authorized` stubs engine_detect so the external engines READ as authorized (the host-side state
    the real acceptance harness runs under); otherwise every external row is fallbackToClaude and the
    census skips it (a vacuous pass that would hide regressions)."""
    repo = str(tmp_path / "repo")
    store = str(tmp_path / "store")
    os.makedirs(repo)
    subprocess.run(["git", "init", "-q", repo], check=True)
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", store)
    core_md.write(repo, {"verifyCommand": "npm test", "stackTags": [], "threatModel": "x",
                         "patterns": "", "enginePreferences": prefs}, "confirmed",
                  root=None, now="2026-06-30")
    if authorized:
        monkeypatch.setattr(engine_detect, "decide", lambda authz, eng: (True, None, None))
    return repo


def _events_path(repo):
    return control_plane.paths(repo, WI)["events"]


def _journal_external(repo, engine, role_kind, outcome="ok"):
    journal.append(_events_path(repo), "external_dispatch", root=repo,
                   payload={"engine": engine, "roleKind": role_kind, "outcome": outcome,
                            "effort": "high", "verify": "pending"})


def _journal_phase_cost(repo, phase, by_model):
    journal.append(_events_path(repo), "phase_cost", root=repo,
                   payload={"phase": phase,
                            "dispatches": {"total": sum(by_model.values()), "byModel": by_model},
                            "tokens": {"output": None, "input": None, "measured": False, "source": "none"}})


_EXTERNAL_PREFS = {"reviewer": "codex", "implementation": "cursor"}


def _seed_traversal(repo, workhorse_models):
    for phase in ("plan", "workhorse", "review-code", "ship"):
        _journal_phase_cost(repo, phase, {"haiku": 2, "opus": 1})
    _journal_phase_cost(repo, "workhorse", workhorse_models)


def test_matching_external_run_passes(tmp_path, monkeypatch):
    repo = _fixture(tmp_path, monkeypatch, _EXTERNAL_PREFS)
    _journal_external(repo, "codex", "review")
    _journal_external(repo, "cursor", "build")
    _journal_external(repo, "cursor", "fix")
    _seed_traversal(repo, {"haiku": 4, "sonnet": 2, "opus": 1})
    out = acceptance_deps.real_dispatch_census(repo, lambda: WI)()
    assert out["ok"] is True, out["failures"]


def test_silent_fall_open_fails(tmp_path, monkeypatch):
    # External calibration but the journal has ZERO external_dispatch events — the exact all-Claude
    # fall-open #299 exists to catch. Must FAIL, naming the engines that never dispatched.
    repo = _fixture(tmp_path, monkeypatch, _EXTERNAL_PREFS)
    _seed_traversal(repo, {"haiku": 4, "sonnet": 2, "opus": 1})
    out = acceptance_deps.real_dispatch_census(repo, lambda: WI)()
    assert out["ok"] is False
    joined = " ".join(out["failures"])
    assert "codex" in joined and "cursor" in joined


def test_fable_in_census_fails(tmp_path, monkeypatch):
    repo = _fixture(tmp_path, monkeypatch, _EXTERNAL_PREFS)
    _journal_external(repo, "codex", "review")
    _journal_external(repo, "cursor", "build")
    _journal_external(repo, "cursor", "fix")
    _seed_traversal(repo, {"haiku": 4, "fable": 1})
    out = acceptance_deps.real_dispatch_census(repo, lambda: WI)()
    assert out["ok"] is False
    assert any("Fable" in f for f in out["failures"])


def test_all_claude_calibration_passes_trivially(tmp_path, monkeypatch):
    # No external routing -> nothing to prove even with an empty journal.
    repo = _fixture(tmp_path, monkeypatch, {"reviewer": "claude", "implementation": "claude"})
    out = acceptance_deps.real_dispatch_census(repo, lambda: WI)()
    assert out["ok"] is True and out["failures"] == []


def test_external_calibration_no_journal_fails(tmp_path, monkeypatch):
    # External calibration + no journal evidence at all -> fail-closed (the census cannot confirm the
    # external legs ran; a ready terminal with no dispatch evidence is exactly the blind spot #299
    # closes). Manifests as the silent-fall-open failure naming the unproven engines.
    repo = _fixture(tmp_path, monkeypatch, _EXTERNAL_PREFS)
    out = acceptance_deps.real_dispatch_census(repo, lambda: WI)()
    assert out["ok"] is False
    assert any("no dispatch events" in f for f in out["failures"])


def test_unauthorized_engines_fall_open_is_a_pass(tmp_path, monkeypatch):
    # When the engines are NOT authorized, the readout shows fallbackToClaude and the run legitimately
    # runs native — no external evidence is owed (the fall-open is already visible in the readout).
    repo = _fixture(tmp_path, monkeypatch, _EXTERNAL_PREFS, authorized=False)
    _seed_traversal(repo, {"haiku": 4, "sonnet": 2, "opus": 1})
    out = acceptance_deps.real_dispatch_census(repo, lambda: WI)()
    assert out["ok"] is True, out["failures"]


def test_no_work_item_is_pass(tmp_path, monkeypatch):
    repo = _fixture(tmp_path, monkeypatch, _EXTERNAL_PREFS)
    out = acceptance_deps.real_dispatch_census(repo, lambda: None)()
    assert out["ok"] is True and out["failures"] == []
