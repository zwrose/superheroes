import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    spec = importlib.util.spec_from_file_location(
        "engine_authz", os.path.join(_HERE, "..", "engine_authz.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


AZ = _load()


class _Proc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_authorization_snippet_names_automode_allow_and_location():
    snip = AZ.authorization_snippet("claude-code", "cursor")
    assert "autoMode" in snip and "allow" in snip
    assert ".claude/settings.local.json" in snip


def test_authorization_snippet_covers_both_engines():
    for engine in ("codex", "cursor"):
        snip = AZ.authorization_snippet("claude-code", engine)
        assert engine in snip.lower() or "cursor-agent" in snip.lower() or "codex" in snip.lower()


def test_authorization_snippet_never_writes(tmp_path, monkeypatch):
    # a hard guard: calling the snippet builder touches NO file.
    calls = []
    real_open = open
    monkeypatch.setattr("builtins.open",
                        lambda *a, **k: calls.append(a) or real_open(*a, **k))
    AZ.authorization_snippet("claude-code", "cursor")
    # the snippet builder opened nothing for WRITE
    assert all("w" not in (a[1] if len(a) > 1 else "") for a in calls)


def test_implementation_dispatch_allowed_true_when_probe_succeeds(tmp_path):
    def run(args, **k):
        return _Proc(returncode=0, stdout="wrote")
    assert AZ.implementation_dispatch_allowed(str(tmp_path), "codex", run=run) is True


def test_implementation_dispatch_allowed_false_when_denied_ufr4(tmp_path):
    # a denied write (nonzero exit) → False → implementation role falls open to Claude (UFR-4).
    def run(args, **k):
        return _Proc(returncode=1, stderr="denied by autoMode")
    assert AZ.implementation_dispatch_allowed(str(tmp_path), "cursor", run=run) is False


def test_implementation_dispatch_allowed_false_on_exception(tmp_path):
    def run(args, **k):
        raise RuntimeError("boom")
    assert AZ.implementation_dispatch_allowed(str(tmp_path), "codex", run=run) is False


def test_implementation_dispatch_probes_the_engines_own_write_command(tmp_path):
    # The probe must exercise THAT engine's write command, so the host's per-engine autoMode.allow
    # rule (Bash(codex exec:*) vs Bash(cursor-agent:*)) is what gets tested.
    seen = {}
    def run(args, **k):
        seen["argv"] = args
        return _Proc(returncode=0)
    AZ.implementation_dispatch_allowed(str(tmp_path), "codex", run=run)
    # argv is a LIST of separate tokens (["codex","exec","--sandbox","workspace-write","-C",cwd,prompt]),
    # so no single token contains "codex exec". assert on the JOINED argv, which starts with "codex exec".
    assert " ".join(str(t) for t in seen["argv"]).startswith("codex exec")
    AZ.implementation_dispatch_allowed(str(tmp_path), "cursor", run=run)
    # cursor argv is (["cursor-agent","-f",prompt]) — the joined form starts with "cursor-agent".
    assert " ".join(str(t) for t in seen["argv"]).startswith("cursor-agent")


def test_codex_dispatch_probe_checks_the_gpt_5_6_capability_by_default(tmp_path):
    seen = {}
    def run(args, **k):
        seen["argv"] = args
        return _Proc(returncode=0)
    AZ.implementation_dispatch_allowed(str(tmp_path), "codex", run=run)
    assert seen["argv"][seen["argv"].index("-m") + 1] == "gpt-5.6-sol"


def test_codex_probe_uses_configured_write_pins(tmp_path, monkeypatch):
    # #409: when both codex write roles are pinned, the probe dispatches the strongest of those pins so
    # a project pinned entirely to an older family is not falsely marked not-ready by a hard sol probe.
    import engine_pref
    monkeypatch.setattr(engine_pref, "load_engine_prefs",
                        lambda cwd, root=None: {"codexModels": {"implementer": "gpt-5.5",
                                                                "fixer": "gpt-5.5"}})
    seen = {}
    def run(args, **k):
        seen["argv"] = args
        return _Proc(returncode=0)
    AZ.implementation_dispatch_allowed(str(tmp_path), "codex", run=run)
    assert seen["argv"][seen["argv"].index("-m") + 1] == "gpt-5.5"


def test_codex_probe_clamps_to_sol_floor_when_a_write_role_is_unpinned(tmp_path, monkeypatch):
    # #409 premortem regression: with implementer pinned to gpt-5.5 but fixer UNPINNED (fixer derives
    # a GPT-5.6 tier model), the probe must clamp up to the sol floor — never under-test at gpt-5.5.
    import engine_pref
    monkeypatch.setattr(engine_pref, "load_engine_prefs",
                        lambda cwd, root=None: {"codexModels": {"implementer": "gpt-5.5"}})
    seen = {}
    def run(args, **k):
        seen["argv"] = args
        return _Proc(returncode=0)
    AZ.implementation_dispatch_allowed(str(tmp_path), "codex", run=run)
    assert seen["argv"][seen["argv"].index("-m") + 1] == "gpt-5.6-sol"


def test_codex_probe_clamps_to_sol_floor_when_implementer_is_unpinned(tmp_path, monkeypatch):
    # #409 symmetric to the above: fixer pinned to gpt-5.5, implementer UNPINNED (derives a GPT-5.6
    # tier model) -> the probe clamps up to the sol floor. Exercises the implementer-unpinned axis.
    import engine_pref
    monkeypatch.setattr(engine_pref, "load_engine_prefs",
                        lambda cwd, root=None: {"codexModels": {"fixer": "gpt-5.5"}})
    seen = {}
    def run(args, **k):
        seen["argv"] = args
        return _Proc(returncode=0)
    AZ.implementation_dispatch_allowed(str(tmp_path), "codex", run=run)
    assert seen["argv"][seen["argv"].index("-m") + 1] == "gpt-5.6-sol"


def test_codex_probe_falls_to_sol_floor_when_no_pins(tmp_path, monkeypatch):
    # with no configured pins the probe still checks the sol capability floor (original rationale:
    # an authenticated-but-old CLI that rejects every GPT-5.6 dispatch must not falsely pass).
    import engine_pref
    monkeypatch.setattr(engine_pref, "load_engine_prefs",
                        lambda cwd, root=None: {"reviewer": "claude", "implementation": "claude"})
    seen = {}
    def run(args, **k):
        seen["argv"] = args
        return _Proc(returncode=0)
    AZ.implementation_dispatch_allowed(str(tmp_path), "codex", run=run)
    assert seen["argv"][seen["argv"].index("-m") + 1] == "gpt-5.6-sol"


def test_codex_probe_falls_to_sol_floor_when_prefs_unreadable(tmp_path, monkeypatch):
    # any load failure falls open to the sol floor — the probe never raises on a bad/absent core.md.
    import engine_pref
    def boom(*a, **k):
        raise RuntimeError("unreadable")
    monkeypatch.setattr(engine_pref, "load_engine_prefs", boom)
    seen = {}
    def run(args, **k):
        seen["argv"] = args
        return _Proc(returncode=0)
    AZ.implementation_dispatch_allowed(str(tmp_path), "codex", run=run)
    assert seen["argv"][seen["argv"].index("-m") + 1] == "gpt-5.6-sol"


def test_codex_probe_reads_pin_from_core_md_end_to_end(tmp_path, monkeypatch):
    # end-to-end: a real core.md pinned entirely to gpt-5.5 makes the probe dispatch -m gpt-5.5.
    import importlib.util as u
    import subprocess
    repo = str(tmp_path / "repo")
    store = str(tmp_path / "store")
    os.makedirs(repo)
    subprocess.run(["git", "init", "-q", repo], check=True)
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", store)  # the probe resolves core.md via root=None
    spec = u.spec_from_file_location("core_md", os.path.join(_HERE, "..", "core_md.py"))
    cm = u.module_from_spec(spec)
    spec.loader.exec_module(cm)
    cm.write(repo, {"verifyCommand": "npm test", "stackTags": [], "threatModel": "x",
                    "patterns": "", "enginePreferences": {
                        "implementation": "codex",
                        "codexModels": {"implementer": "gpt-5.5", "fixer": "gpt-5.5"}}},
             "confirmed", root=store, now="2026-06-30")
    seen = {}
    def run(args, **k):
        seen["argv"] = args
        return _Proc(returncode=0)
    AZ.implementation_dispatch_allowed(repo, "codex", run=run)
    assert seen["argv"][seen["argv"].index("-m") + 1] == "gpt-5.5"


def test_implementation_dispatch_unknown_engine_falls_open_false(tmp_path):
    def run(args, **k):
        return _Proc(returncode=0)
    assert AZ.implementation_dispatch_allowed(str(tmp_path), "bogus", run=run) is False


def test_implementation_dispatch_probe_bounded_by_resolve_timeout_default(tmp_path):
    # FR-14: the probe's subprocess timeout must be the SAME configurable limit as UFR-5
    # (engine_pref.resolve_timeout), not a hardcoded value. Default is 300 (DEFAULT_STALL_LIMIT_SECONDS).
    seen = {}
    def run(args, **k):
        seen["timeout"] = k.get("timeout")
        return _Proc(returncode=0)
    AZ.implementation_dispatch_allowed(str(tmp_path), "codex", run=run)
    assert seen["timeout"] == 300


def test_implementation_dispatch_probe_honors_timeout_override(tmp_path):
    # the limit must be test-settable via the same override channel as resolve_timeout.
    seen = {}
    def run(args, **k):
        seen["timeout"] = k.get("timeout")
        return _Proc(returncode=0)
    AZ.implementation_dispatch_allowed(str(tmp_path), "cursor", run=run, overrides={"timeout": 7})
    assert seen["timeout"] == 7


def test_implementation_dispatch_false_on_timeout_expired(tmp_path):
    # a TimeoutExpired (no response within the bounded limit) counts as no-response -> deny/fall-open.
    import subprocess as _subprocess
    def run(args, **k):
        raise _subprocess.TimeoutExpired(cmd=args, timeout=k.get("timeout"))
    assert AZ.implementation_dispatch_allowed(str(tmp_path), "codex", run=run) is False


def test_cli_snippet_subcommand(capsys):
    rc = AZ.main(["snippet", "--host", "claude", "--engine", "cursor"])
    out = capsys.readouterr().out
    assert rc == 0 and "autoMode" in out and ".claude/settings.local.json" in out


def test_cli_test_dispatch_subcommand(capsys):
    def run(args, **k):
        return _Proc(returncode=0)
    rc = AZ.main(["test-dispatch", "--engine", "codex", "--cwd", "."], run=run)
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out == {"engine": "codex", "ok": True}


def test_cli_test_dispatch_denied_reports_false(capsys):
    def run(args, **k):
        return _Proc(returncode=1, stderr="denied")
    rc = AZ.main(["test-dispatch", "--engine", "cursor", "--cwd", "."], run=run)
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out == {"engine": "cursor", "ok": False}


def test_cli_test_dispatch_default_timeout_is_resolve_timeout_default(capsys):
    # no --timeout flag -> the probe uses resolve_timeout(None) == 300, NOT a hardcoded 10.
    seen = {}
    def run(args, **k):
        seen["timeout"] = k.get("timeout")
        return _Proc(returncode=0)
    AZ.main(["test-dispatch", "--engine", "codex", "--cwd", "."], run=run)
    assert seen["timeout"] == 300


def test_cli_test_dispatch_timeout_flag_overrides(capsys):
    seen = {}
    def run(args, **k):
        seen["timeout"] = k.get("timeout")
        return _Proc(returncode=0)
    AZ.main(["test-dispatch", "--engine", "codex", "--cwd", ".", "--timeout", "5"], run=run)
    out = json.loads(capsys.readouterr().out)
    assert seen["timeout"] == 5
    assert out == {"engine": "codex", "ok": True}
