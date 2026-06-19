# .github/scripts/tests/test_validate_hosts.py
import importlib.util, os
_HERE = os.path.dirname(os.path.abspath(__file__))
_V = os.path.join(_HERE, "..", "validate_hosts.py")
spec = importlib.util.spec_from_file_location("validate_hosts", _V)
VH = importlib.util.module_from_spec(spec); spec.loader.exec_module(VH)

# Full pointer line — must contain `hosts/<your-host>-tools.md` so POINTER_RE matches.
POINTER = "Resolve actions via `hosts/<your-host>-tools.md` — `claude-tools.md` on Claude, `codex-tools.md` on Codex."

def test_lint_flags_banned_prose():
    bad = "# S\n\nUse the Agent tool with subagent_type: review-crew:code-reviewer.\n" + POINTER
    assert any("subagent_type" in v for v in VH.lint_skill(bad))

def test_lint_allows_portable_seam_and_requires_pointer():
    good = '# S\n\n' + POINTER + '\n\n```bash\nROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"\npython3 "$ROOT_DIR/lib/x.py"\n```\n'
    assert VH.lint_skill(good) == []

def test_lint_flags_missing_pointer():
    nopointer = '# S\n\n```bash\nROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"\n```\n'
    assert any("pointer" in v.lower() for v in VH.lint_skill(nopointer))

def test_lint_flags_bare_claude_plugin_root():
    bare = '# S\n\n' + POINTER + '\n\n```bash\npython3 "${CLAUDE_PLUGIN_ROOT}/lib/x.py"\n```\n'
    assert any("CLAUDE_PLUGIN_ROOT" in v for v in VH.lint_skill(bare))

# --- fixture-driven tests for the CI-gating paths (containment / identity / byte-equality / main exit) ---
import json

def _scaffold(tmp):
    (tmp / "hosts").mkdir()
    (tmp / "hosts" / "claude-tools.md").write_text("CLAUDE MAP\n")
    (tmp / "hosts" / "codex-tools.md").write_text("CODEX MAP\n")
    p = tmp / "plugins" / "p"
    (p / ".claude-plugin").mkdir(parents=True); (p / ".codex-plugin").mkdir(parents=True)
    (p / "hosts").mkdir(parents=True); (p / "skills" / "s").mkdir(parents=True)
    (p / ".claude-plugin" / "plugin.json").write_text(json.dumps(
        {"name": "p", "version": "1.0.0", "author": {"name": "z"}, "description": "d"}))
    (p / ".codex-plugin" / "plugin.json").write_text(json.dumps(
        {"name": "p", "version": "1.0.0", "author": {"name": "z"}, "description": "d",
         "skills": "./skills/", "interface": {"displayName": "P"}}))
    (p / "hosts" / "claude-tools.md").write_text("CLAUDE MAP\n")
    (p / "hosts" / "codex-tools.md").write_text("CODEX MAP\n")
    (p / "skills" / "s" / "SKILL.md").write_text("# s\n\n" + POINTER + "\n")
    (tmp / ".claude-plugin").mkdir()
    (tmp / ".claude-plugin" / "marketplace.json").write_text(json.dumps(
        {"name": "superheroes", "plugins": [{"name": "p"}]}))
    (tmp / ".agents" / "plugins").mkdir(parents=True)
    (tmp / ".agents" / "plugins" / "marketplace.json").write_text(json.dumps(
        {"name": "superheroes", "plugins": [{"name": "p",
         "source": {"source": "local", "path": "./plugins/p"},
         "policy": {"installation": "AVAILABLE", "authentication": "ON_USE"}}]}))
    return tmp

def _run_main(tmp, monkeypatch):
    monkeypatch.setattr(VH, "REPO", str(tmp))
    monkeypatch.setattr(VH, "PLUGINS", str(tmp / "plugins"))
    return VH.main([])

def test_valid_scaffold_passes(tmp_path, monkeypatch):
    _scaffold(tmp_path)
    assert _run_main(tmp_path, monkeypatch) == 0

def test_codex_source_traversal_rejected(tmp_path, monkeypatch, capsys):
    _scaffold(tmp_path)
    mp = tmp_path / ".agents" / "plugins" / "marketplace.json"
    d = json.loads(mp.read_text()); d["plugins"][0]["source"]["path"] = "./plugins/p/../../../tmp/evil"
    mp.write_text(json.dumps(d))
    assert _run_main(tmp_path, monkeypatch) == 1
    assert "contained" in capsys.readouterr().err

def test_identity_drift_rejected(tmp_path, monkeypatch, capsys):
    _scaffold(tmp_path)
    cm = tmp_path / "plugins" / "p" / ".codex-plugin" / "plugin.json"
    d = json.loads(cm.read_text()); d["version"] = "9.9.9"; cm.write_text(json.dumps(d))
    assert _run_main(tmp_path, monkeypatch) == 1
    assert "drifts" in capsys.readouterr().err

def test_map_byte_equality_enforced(tmp_path, monkeypatch, capsys):
    _scaffold(tmp_path)
    (tmp_path / "plugins" / "p" / "hosts" / "codex-tools.md").write_text("DRIFTED\n")
    assert _run_main(tmp_path, monkeypatch) == 1
    assert "drifts from canonical" in capsys.readouterr().err

def test_map_crlf_drift_rejected(tmp_path, monkeypatch, capsys):
    """CRLF line endings must be detected as drift even though text mode normalises them."""
    _scaffold(tmp_path)
    # Canonical has LF ("\n"); overwrite plugin map with identical text but CRLF endings.
    (tmp_path / "plugins" / "p" / "hosts" / "codex-tools.md").write_bytes(b"CODEX MAP\r\n")
    assert _run_main(tmp_path, monkeypatch) == 1
    assert "drifts from canonical" in capsys.readouterr().err
