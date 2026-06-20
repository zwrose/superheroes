# .github/scripts/tests/test_validate_hosts.py
import importlib.util, os
import pytest
_HERE = os.path.dirname(os.path.abspath(__file__))
_V = os.path.join(_HERE, "..", "validate_hosts.py")
spec = importlib.util.spec_from_file_location("validate_hosts", _V)
VH = importlib.util.module_from_spec(spec); spec.loader.exec_module(VH)

# Full pointer line — must contain `hosts/<your-host>-tools.md` so POINTER_RE matches.
POINTER = "Resolve actions via `hosts/<your-host>-tools.md` — `claude-tools.md` on Claude, `codex-tools.md` on Codex."

def test_lint_flags_banned_prose():
    bad = "# S\n\nUse the Agent tool with subagent_type: review-crew:code-reviewer.\n" + POINTER
    assert any("subagent_type" in v for v in VH.lint_skill(bad))

@pytest.mark.parametrize("tok", VH.BANNED)
def test_lint_flags_each_banned_token(tok):
    """Each token in BANNED must be individually flagged by lint_skill."""
    bad = "# S\n\n" + POINTER + "\n" + tok + "\n"
    lints = VH.lint_skill(bad)
    assert any(tok in v for v in lints), f"Token {tok!r} not flagged in lints: {lints}"

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

def test_codex_marketplace_name_mismatch_rejected(tmp_path, monkeypatch, capsys):
    """The Codex marketplace name must match the Claude marketplace name."""
    _scaffold(tmp_path)
    mp = tmp_path / ".agents" / "plugins" / "marketplace.json"
    d = json.loads(mp.read_text()); d["name"] = "not-superheroes"; mp.write_text(json.dumps(d))
    assert _run_main(tmp_path, monkeypatch) == 1
    assert "codex marketplace name" in capsys.readouterr().err

def test_codex_entry_missing_name_guard(tmp_path, monkeypatch, capsys):
    """Guard against Codex marketplace entries with missing 'name' field."""
    _scaffold(tmp_path)
    mp = tmp_path / ".agents" / "plugins" / "marketplace.json"
    d = json.loads(mp.read_text())
    # Add a malformed entry without 'name'
    d["plugins"].append({"source": {"source": "local", "path": "./plugins/p"}})
    mp.write_text(json.dumps(d))
    assert _run_main(tmp_path, monkeypatch) == 1
    assert "missing name" in capsys.readouterr().err

def test_claude_absent_from_codex_rejected(tmp_path, monkeypatch, capsys):
    """A plugin that loads on the Claude side but is missing from the Codex marketplace is rejected."""
    _scaffold(tmp_path)
    # Scaffold a second, real Claude plugin "q" (with a loadable .claude-plugin/plugin.json,
    # so it enters claude_plugins) and register it in the Claude marketplace only.
    q = tmp_path / "plugins" / "q" / ".claude-plugin"
    q.mkdir(parents=True)
    (q / "plugin.json").write_text(json.dumps(
        {"name": "q", "version": "1.0.0", "author": {"name": "z"}, "description": "d"}))
    cm = tmp_path / ".claude-plugin" / "marketplace.json"
    d = json.loads(cm.read_text())
    d["plugins"].append({"name": "q"})
    cm.write_text(json.dumps(d))
    # Do NOT add "q" to the Codex marketplace.
    assert _run_main(tmp_path, monkeypatch) == 1
    assert "absent from codex" in capsys.readouterr().err

def test_lint_reference_files_flags_a_planted_violation(tmp_path):
    ref_dir = tmp_path / "plugins" / "p" / "skills" / "s" / "reference"
    ref_dir.mkdir(parents=True)
    (ref_dir / "leaf.md").write_text("dispatch via subagent_type, the host-coupled token")
    errs = VH.lint_reference_files(str(tmp_path / "plugins"), ["p"])
    assert any("subagent_type" in e and "leaf.md" in e for e in errs)

def test_lint_reference_files_does_not_require_host_pointer(tmp_path):
    ref_dir = tmp_path / "plugins" / "p" / "skills" / "s" / "reference"
    ref_dir.mkdir(parents=True)
    (ref_dir / "leaf.md").write_text("plain neutral relocated prose")
    assert VH.lint_reference_files(str(tmp_path / "plugins"), ["p"]) == []

def test_lint_reference_files_exact_component_match(tmp_path):
    """'references/' (with trailing s) must NOT be linted; 'reference/' MUST be."""
    # File under a directory named 'references' (not 'reference') — should be skipped
    refs_dir = tmp_path / "plugins" / "p" / "skills" / "s" / "references"
    refs_dir.mkdir(parents=True)
    (refs_dir / "sibling.md").write_text("dispatch via subagent_type, the host-coupled token")
    errs_refs = VH.lint_reference_files(str(tmp_path / "plugins"), ["p"])
    assert not any("sibling.md" in e for e in errs_refs), \
        "Files under 'references/' should NOT be linted by lint_reference_files"

    # File under a directory named 'reference' (exact) — should be linted
    ref_dir = tmp_path / "plugins" / "p" / "skills" / "s" / "reference"
    ref_dir.mkdir(parents=True)
    (ref_dir / "leaf.md").write_text("dispatch via subagent_type, the host-coupled token")
    errs_ref = VH.lint_reference_files(str(tmp_path / "plugins"), ["p"])
    assert any("leaf.md" in e for e in errs_ref), \
        "Files under 'reference/' SHOULD be linted by lint_reference_files"
