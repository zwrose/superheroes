# plugins/superheroes/lib/tests/test_verify_command_cli_core.py
"""verify_command_cli + repo_doctor read the verify command from core.md (PURE read, no migration)."""
import os
import core_md as cm
import verify_command_cli as vcc
import repo_doctor as rd


def _write_core(repo, verify="npm test"):
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "core.md"), "w").write(
        cm.render_core({"verifyCommand": verify, "stackTags": ["node"],
                        "threatModel": "x", "patterns": ""}, "confirmed",
                       "2026-06-26", "2026-06-26"))


def test_vcc_prefers_core_md(tmp_path, monkeypatch):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _write_core(repo, verify="pnpm check")
    # capture the REAL read before patching (cm is vcc.core_md — patching read with a lambda
    # that calls cm.read would otherwise recurse into itself).
    _real_read = cm.read
    monkeypatch.setattr(vcc.core_md, "read", lambda cwd, root=None: _real_read(repo, root=store))
    assert vcc.resolve_command(repo) == "pnpm check"


def test_vcc_falls_back_to_legacy(tmp_path, monkeypatch):
    repo = str(tmp_path)
    prof = os.path.join(repo, "p.md")
    open(prof, "w").write("## Verify\ncommand: make test\n")
    monkeypatch.setattr(vcc.core_md, "read", lambda cwd, root=None: None)
    monkeypatch.setattr(vcc, "_profile_path", lambda: prof)
    assert vcc.resolve_command(repo) == "make test"


def test_repo_doctor_prefers_core_md_verify(tmp_path, monkeypatch):
    # repo_doctor.doctor uses core_md.read(root) verify when present; pure read (no migration).
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _write_core(repo, verify="echo ok")
    prof = os.path.join(repo, "profile.md")
    open(prof, "w").write("<!-- x -->\nschema: 1\n## Verify\ncommand: SHOULD_NOT_WIN\n")
    # capture the REAL read before patching (rd.core_md is cm — a lambda calling cm.read would recurse).
    _real_read = cm.read
    monkeypatch.setattr(rd.core_md, "read", lambda cwd, root=None: _real_read(repo, root=store))
    res = rd.doctor(prof, "0.2.0", 3, repo, dict(os.environ))
    # core.md's "echo ok" (a resolvable binary) wins → no "no longer resolves" drift for SHOULD_NOT_WIN
    assert res["readable"] is True
    assert not any("SHOULD_NOT_WIN" in d for d in res["drift"])
