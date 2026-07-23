# plugins/superheroes/lib/tests/test_escalation.py
import importlib.util
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
_MODULE_PATH = os.path.join(_REPO_ROOT, "plugins/superheroes/lib/escalation.py")


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ESC = _load(_MODULE_PATH, "architect_escalation")


def _axes(**kw):
    base = {"on_floor": False, "ground_truth_locus": "owner",
            "owner_weighable": True, "reversible": True, "confidence": "high"}
    base.update(kw)
    return base


# --- route() truth table ---
def test_on_floor_short_circuits_to_gate():
    # on_floor wins regardless of every other axis (the floor is step 1, unconditional)
    assert ESC.route(_axes(on_floor=True, ground_truth_locus="agent",
                           owner_weighable=False, reversible=True, confidence="high")) == "gate"

def test_agent_verifiable_proceeds():
    assert ESC.route(_axes(ground_truth_locus="agent")) == "proceed"

def test_engineering_internal_proceeds():
    # owner-locus but not owner-weighable = engineering-internal -> record-only proceed
    assert ESC.route(_axes(ground_truth_locus="owner", owner_weighable=False)) == "proceed"

def test_owner_weighable_irreversible_gates():
    assert ESC.route(_axes(owner_weighable=True, reversible=False, confidence="high")) == "gate"

def test_owner_weighable_low_confidence_gates():
    assert ESC.route(_axes(owner_weighable=True, reversible=True, confidence="low")) == "gate"

def test_owner_weighable_reversible_high_confidence_notifies():
    assert ESC.route(_axes(owner_weighable=True, reversible=True, confidence="high")) == "notify"


# --- route() fail-closed on malformed input ---
def test_route_fails_closed_on_non_dict():
    assert ESC.route(None) == "gate"
    assert ESC.route("nope") == "gate"

def test_route_fails_closed_on_missing_locus():
    assert ESC.route({"on_floor": False}) == "gate"

def test_route_fails_closed_on_bad_axis_values():
    assert ESC.route(_axes(ground_truth_locus="owner", owner_weighable="yes")) == "gate"
    assert ESC.route(_axes(ground_truth_locus="owner", confidence="medium")) == "gate"
    assert ESC.route(_axes(on_floor=None, ground_truth_locus="banana")) == "gate"


# --- floor action-classifier (recognizable descriptors -> on_floor) ---
import pytest

@pytest.mark.parametrize("descriptor", [
    "git push origin main",
    "git push --force origin feature",
    "git push -f",
    "git merge release",
    "deploy to production",
    "vercel deploy --prod",
    "DROP COLUMN email",
    "DELETE FROM users",
    "TRUNCATE accounts",
    "rm -rf build/",
    "add a paid Stripe API call",
    "POST the data to an external webhook",
])
def test_classify_floor_recognizes_dangerous_descriptors(descriptor):
    assert ESC.classify_floor(descriptor) is True

@pytest.mark.parametrize("descriptor", [
    "rename a local variable",
    "extract a helper function",
    "git status",
    "git commit -m 'wip'",      # local commit is off-floor (act-then-report)
    "read the config file",
])
def test_classify_floor_passes_ordinary_descriptors(descriptor):
    assert ESC.classify_floor(descriptor) is False


# --- safety-machinery set + fixer file-scope guard ---
def test_safety_machinery_set_members_are_pinned():
    # The set is the single source of truth (§4 bound-2): the names whose edit could disable a
    # floor/gate/halt/escalation guarantee. Pin membership so the guard and the eval fixture
    # can't drift. escalation_resolve.py — the wrapper that OWNS the fail-closed verdict — is
    # included (review caught its omission: without it a fixer could neuter the guard).
    assert set(ESC.SAFETY_MACHINERY) == {
        "escalation.py", "escalation_resolve.py", "loop_state.py", "circuit_breaker.py",
        "gate_write.py", "definition_doc.py",
        "enforcer.py", "allowance.py", "model_tier.py", "model_registry.py",
        "engine_pref.py", "seat_map.py", "hooks.json",
        "precompact.py", "session_start.py",
        "escalation-base.md", "review-base.md",
        # shared review-and-fix loop (#104): deciders, durable record, and the orchestration shell
        "panel_tally.py", "loop_synthesis.py", "verification.py", "verify_gate.py",
        "loop_readout.py",
        "review_result.py", "round_driver.py", "audits.py", "delta_surface.py",
    }

def _band_file(tmp_path, sub, name):
    p = tmp_path / "plugins" / "superheroes" / sub / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x", encoding="utf-8")
    return p

# Files that live under hooks/ in the merged superheroes tree (not lib/)
_HOOKS_FILES = {"hooks.json", "precompact.py", "session_start.py"}

def test_is_safety_machinery_engine_pref_and_seat_map(tmp_path):
    band_root = str(tmp_path / "plugins" / "superheroes")
    for name in ("engine_pref.py", "seat_map.py"):
        p = _band_file(tmp_path, "lib", name)
        assert ESC.is_safety_machinery(str(p), [band_root]) is True, name


def test_guard_refuses_each_safety_file_under_a_band_root(tmp_path):
    band_root = str(tmp_path / "plugins" / "superheroes")
    for name in ESC.SAFETY_MACHINERY:
        if name in _HOOKS_FILES:
            sub = "hooks"
        elif name.endswith(".md"):
            sub = "rubric"
        else:
            sub = "lib"
        p = _band_file(tmp_path, sub, name)
        assert ESC.is_safety_machinery(str(p), [band_root]) is True, name

def test_guard_allows_ordinary_source(tmp_path):
    roots = [str(tmp_path / "plugins" / "superheroes")]
    p = tmp_path / "src" / "feature.py"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x", encoding="utf-8")
    assert ESC.is_safety_machinery(str(p), roots) is False

def test_guard_allows_same_basename_outside_band_roots(tmp_path):
    # The false-positive fix (review): a target repo legitimately containing loop_state.py
    # OUTSIDE the band's plugin tree must NOT be refused — basename alone is not enough.
    roots = [str(tmp_path / "plugins" / "superheroes")]
    p = tmp_path / "their_app" / "loop_state.py"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x", encoding="utf-8")
    assert ESC.is_safety_machinery(str(p), roots) is False

def test_guard_resists_symlink_evasion(tmp_path):
    real = _band_file(tmp_path, "lib", "loop_state.py")
    link = tmp_path / "alias.py"
    os.symlink(str(real), str(link))
    roots = [str(tmp_path / "plugins" / "superheroes")]
    # matched by the RESOLVED real path (basename + under a band root), not the link name
    assert ESC.is_safety_machinery(str(link), roots) is True

def test_guard_fails_closed_without_band_roots(tmp_path):
    p = _band_file(tmp_path, "lib", "loop_state.py")
    assert ESC.is_safety_machinery(str(p), None) is True   # can't anchor -> protect


def _run_cli(*args):
    proc = subprocess.run([sys.executable, _MODULE_PATH, *args],
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()

def test_cli_route_emits_json():
    rc, out, _ = _run_cli("route", "--on-floor", "false", "--ground-truth-locus", "owner",
                          "--owner-weighable", "true", "--reversible", "true",
                          "--confidence", "high")
    assert rc == 0 and json.loads(out)["mode"] == "notify"

def test_cli_route_on_floor_gates():
    rc, out, _ = _run_cli("route", "--on-floor", "true", "--ground-truth-locus", "agent",
                          "--owner-weighable", "false", "--reversible", "true",
                          "--confidence", "high")
    assert rc == 0 and json.loads(out)["mode"] == "gate"

def test_cli_classify_emits_json():
    rc, out, _ = _run_cli("classify", "--action", "git push origin main")
    assert rc == 0 and json.loads(out)["on_floor"] is True

def test_cli_guard_refuses_safety_file(tmp_path):
    p = tmp_path / "plugins" / "superheroes" / "lib" / "loop_state.py"
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text("x", encoding="utf-8")
    rc, out, _ = _run_cli("guard", "--path", str(p),
                          "--band-root", str(tmp_path / "plugins" / "superheroes"))
    assert rc == 0 and json.loads(out)["allow"] is False
