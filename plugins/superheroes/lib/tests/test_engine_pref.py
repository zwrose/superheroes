import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    spec = importlib.util.spec_from_file_location(
        "engine_pref", os.path.join(_HERE, "..", "engine_pref.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


EP = _load()


def test_resolve_engine_maps_role_to_key():
    prefs = {"reviewer": "codex", "implementation": "cursor"}
    assert EP.resolve_engine("review", prefs) == "codex"
    assert EP.resolve_engine("build", prefs) == "cursor"
    assert EP.resolve_engine("fix", prefs) == "cursor"   # fix follows implementation


def test_resolve_engine_mixed_reviewer_ne_implementation():
    prefs = {"reviewer": "codex", "implementation": "cursor"}
    assert EP.resolve_engine("review", prefs) == "codex"
    assert EP.resolve_engine("build", prefs) == "cursor"


def test_resolve_engine_falls_open_to_claude():
    assert EP.resolve_engine("review", {}) == "claude"                    # absent key
    assert EP.resolve_engine("review", {"reviewer": "bogus"}) == "claude" # unknown engine
    assert EP.resolve_engine("review", {"reviewer": 7}) == "claude"        # non-str
    assert EP.resolve_engine("review", "not-a-dict") == "claude"           # non-dict prefs
    assert EP.resolve_engine("review", None) == "claude"
    assert EP.resolve_engine("bogus-role", {"reviewer": "codex"}) == "claude"  # unknown role


def test_resolve_effort_defaults():
    assert EP.resolve_effort("codex", "review") == "high"
    assert EP.resolve_effort("codex", "build") == "high"
    assert EP.resolve_effort("codex", "fix") == "low"
    assert EP.resolve_effort("cursor", "review") == "composer"
    assert EP.resolve_effort("cursor", "fix") == "composer"
    assert EP.resolve_effort("claude", "build") is None
    assert EP.resolve_effort("bogus", "build") is None   # unknown engine → None


def test_resolve_effort_override_wins_else_default():
    assert EP.resolve_effort("codex", "review", {"review": "medium"}) == "medium"
    assert EP.resolve_effort("codex", "review", {"review": ""}) == "high"    # empty → default
    assert EP.resolve_effort("codex", "review", {"review": 7}) == "high"      # non-str → default
    assert EP.resolve_effort("codex", "review", "not-a-dict") == "high"
    assert EP.resolve_effort("codex", "review", ["review"]) == "high"         # list (non-dict) → default


def test_resolve_timeout_default_and_override():
    assert EP.resolve_timeout() == EP.DEFAULT_STALL_LIMIT_SECONDS == 300
    assert EP.resolve_timeout({"timeout": 5}) == 5
    assert EP.resolve_timeout({"timeout": 0}) == 300       # non-positive → default
    assert EP.resolve_timeout({"timeout": -1}) == 300
    assert EP.resolve_timeout({"timeout": "5"}) == 300      # non-int → default
    assert EP.resolve_timeout("not-a-dict") == 300


def test_never_raises_on_garbage():
    assert EP.resolve_engine(None, None) == "claude"
    assert EP.resolve_effort(None, None, None) is None
    assert EP.resolve_timeout(None) == 300


import subprocess
import sys

_LIB = os.path.join(_HERE, "..")


def _write_core_with_prefs(repo, prefs):
    import importlib.util as _u
    spec = _u.spec_from_file_location("core_md", os.path.join(_LIB, "core_md.py"))
    cm = _u.module_from_spec(spec)
    spec.loader.exec_module(cm)
    cm.write(repo, {"verifyCommand": "npm test", "stackTags": [], "threatModel": "x",
                    "patterns": "", "enginePreferences": prefs}, "confirmed",
             root=os.path.join(repo, "store"), now="2026-06-30")


def test_load_engine_prefs_reads_core_md(tmp_path):
    repo = str(tmp_path)
    _write_core_with_prefs(repo, {"reviewer": "codex", "implementation": "cursor"})
    got = EP.load_engine_prefs(repo, root=os.path.join(repo, "store"))
    assert got == {"reviewer": "codex", "implementation": "cursor", "effort": {}}


def test_load_engine_prefs_absent_is_both_claude(tmp_path):
    repo = str(tmp_path)
    _write_core_with_prefs(repo, {})   # core.md exists but no engine prefs
    assert EP.load_engine_prefs(repo, root=os.path.join(repo, "store")) == \
        {"reviewer": "claude", "implementation": "claude", "effort": {}}


def test_load_engine_prefs_greenfield_is_both_claude(tmp_path):
    # no core.md at all → both claude (fail-open, never raises)
    assert EP.load_engine_prefs(str(tmp_path), root=str(tmp_path / "store")) == \
        {"reviewer": "claude", "implementation": "claude", "effort": {}}


def test_load_engine_prefs_normalizes_bad_values(tmp_path):
    repo = str(tmp_path)
    _write_core_with_prefs(repo, {"reviewer": "bogus", "implementation": "cursor"})
    assert EP.load_engine_prefs(repo, root=os.path.join(repo, "store")) == \
        {"reviewer": "claude", "implementation": "cursor", "effort": {}}


def test_load_engine_prefs_surfaces_effort_submap_and_resolve_effort_honors_it(tmp_path):
    # FR-9 round-trip: an effort override written into core.md's enginePreferences.effort is
    # surfaced by load_engine_prefs and honored by resolve_effort keyed by role_kind.
    repo = str(tmp_path)
    _write_core_with_prefs(repo, {"reviewer": "codex", "implementation": "codex",
                                  "effort": {"review": "medium", "fix": "high"}})
    got = EP.load_engine_prefs(repo, root=os.path.join(repo, "store"))
    assert got["effort"] == {"review": "medium", "fix": "high"}
    # resolve_effort keyed by role_kind reads THIS effort sub-map (not the model-tier overrides).
    assert EP.resolve_effort("codex", "review", got["effort"]) == "medium"   # override wins
    assert EP.resolve_effort("codex", "fix", got["effort"]) == "high"        # override wins
    assert EP.resolve_effort("codex", "build", got["effort"]) == "high"      # no override -> default


def test_load_engine_prefs_effort_non_dict_normalizes_to_empty(tmp_path):
    repo = str(tmp_path)
    _write_core_with_prefs(repo, {"reviewer": "codex", "implementation": "codex",
                                  "effort": "not-a-dict"})
    assert EP.load_engine_prefs(repo, root=os.path.join(repo, "store"))["effort"] == {}


def test_cli_engine_pref_load_emits_json(tmp_path):
    repo = str(tmp_path)
    _write_core_with_prefs(repo, {"reviewer": "codex", "implementation": "claude",
                                  "effort": {"build": "low"}})
    out = subprocess.run(
        [sys.executable, os.path.join(_LIB, "engine_pref_load.py"),
         "--cwd", repo, "--root", os.path.join(repo, "store")],
        capture_output=True, text=True)
    assert out.returncode == 0
    assert json.loads(out.stdout) == {"reviewer": "codex", "implementation": "claude",
                                      "effort": {"build": "low"}}
