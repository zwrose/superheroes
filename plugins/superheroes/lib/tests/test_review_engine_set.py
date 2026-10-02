"""The review-code seat-map compose probes every installed cross-vendor engine (plus any a role
names). T5 runs the documented CONFIGURED= line from review-code's setup.md, not the helper."""
import json
import os
import subprocess
import sys

import core_md
import liveness_cache
import preflight_probe as pp
import seat_map

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SETUP_MD = os.path.join(_PLUGIN, "skills", "review-code", "reference", "setup.md")


def _which_resolving(*binaries):
    return lambda name: "/stub/" + name if name in binaries else None


def _repo_with_core(tmp_path, prefs):
    """A throwaway git repo holding an in-repo core.md with the given enginePreferences."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "--quiet", str(repo)], check=True, capture_output=True)
    cal = repo / ".claude" / "superheroes"
    cal.mkdir(parents=True)
    (cal / "core.md").write_text(
        core_md.render_core(
            {"verifyCommand": "npm test", "stackTags": [], "enginePreferences": prefs,
             "threatModel": "t", "patterns": ""},
            "confirmed", "2026-01-01", "2026-01-01"),
        encoding="utf-8")
    return str(repo)


def _documented_configured_line():
    with open(_SETUP_MD, encoding="utf-8") as fh:
        lines = [ln for ln in fh.read().splitlines() if ln.startswith("CONFIGURED=$(")]
    assert len(lines) == 1
    return lines[0]


def _run_compose(tmp_path, monkeypatch, capsys, repo, configured, probed_argvs, failing_first_token=None):
    monkeypatch.setattr(liveness_cache, "receipt_path",
                        lambda cwd=None, root=None: str(tmp_path / "state" / "composition-liveness.json"))
    monkeypatch.setattr(pp, "codex_cli_floor_probe", lambda run=None: None)

    def fake_probe(tool, argv, run, stdin_text):
        probed_argvs.append(list(argv))
        ok = argv[0] != failing_first_token
        return {"tool": tool, "ok": ok, "exit": 0 if ok else 1, "detail": "" if ok else "probe failed"}

    monkeypatch.setattr(pp, "_engine_probe_in_scratch_repo", fake_probe)
    capsys.readouterr()
    rc = seat_map.main([
        "seat_map.py", "compose", "--configured-engines", configured,
        "--implementation-engine", "claude", "--host-model", "claude-opus-5-5",
        "--pr-number", "1", "--head-sha", "abc", "--repo-root", repo])
    assert rc == 0
    return json.loads(capsys.readouterr().out)


def test_documented_configured_line_hands_compose_the_installed_engine(tmp_path, monkeypatch, capsys):
    repo = _repo_with_core(tmp_path, {"reviewer": "codex", "implementation": "claude"})
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    for name in ("codex", "cursor-agent"):
        (stubs / name).write_text("#!/bin/sh\nexit 0\n")
        (stubs / name).chmod(0o755)
    (stubs / "python3").symlink_to(sys.executable)
    env = {
        "ROOT_DIR": _PLUGIN,
        "SUPERHEROES_STORE_ROOT": str(tmp_path / "store"),
        "PATH": "%s:/usr/bin:/bin" % stubs,
    }
    proc = subprocess.run(
        ["bash", "-c", _documented_configured_line() + '; printf %s "$CONFIGURED"'],
        cwd=repo, env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == "codex,cursor"

    probed = []
    receipt = _run_compose(tmp_path, monkeypatch, capsys, repo, proc.stdout, probed)
    assert "cursor" in receipt["liveVendors"]
    assert not [d for d in receipt["degradations"] if d.get("constraint") == "critical-diversity"]


def test_installed_engine_whose_probe_fails_is_not_live(tmp_path, monkeypatch, capsys):
    prefs = {"reviewer": "codex", "implementation": "claude"}
    engines = pp.review_cross_vendor_engines(prefs, which=_which_resolving("codex", "cursor-agent"))
    assert "cursor" in engines
    probed = []
    receipt = _run_compose(tmp_path, monkeypatch, capsys, _repo_with_core(tmp_path, prefs),
                           ",".join(engines), probed, failing_first_token="cursor-agent")
    assert any(argv[0] == "cursor-agent" for argv in probed)
    assert "cursor" not in receipt["liveVendors"]


def test_engine_with_no_role_and_no_cli_is_never_probed(tmp_path, monkeypatch, capsys):
    prefs = {"reviewer": "codex", "implementation": "claude"}
    engines = pp.review_cross_vendor_engines(prefs, which=_which_resolving("codex"))
    assert "cursor" not in engines
    probed = []
    _run_compose(tmp_path, monkeypatch, capsys, _repo_with_core(tmp_path, prefs),
                 ",".join(engines), probed)
    assert probed
    assert not [argv for argv in probed if argv[0] == "cursor-agent"]
