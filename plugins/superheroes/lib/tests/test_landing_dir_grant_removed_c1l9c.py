"""C1-L9c (#2258): the claude write sandbox no longer carries a `--landing-dir` grant.

The grant existed so a restricted claude fixer could write into a review landing slot; fix-applying
moved into the build session (C1-L9a) and nothing calls it.

Detector axes (bite-proof):
- test_dispatch_write_parser_has_no_landing_dir_option — absence: the CLI no longer parses it
- test_adapter_has_no_landing_dir_refusal_constants — absence: no constant, no refusal token
- test_no_is_landing_dir_helper — absence: the path helper that only the grant used is gone
- test_no_grant_open_* — preservation: a no-grant open sends the Claude CLI the argv and sandbox
  settings it sent before the removal (values pinned from a run of the base code)
"""
import json
import os

import pytest

import record_paths

# The write-dispatch suite's helpers and its autouse tmp-base/journal-root/uv-absent fixture.
from test_engine_dispatch_write import (  # noqa: F401
    ED,
    EA,
    RR,
    _ClaudeStdoutWriteFakeRunner,
    _claude_write_runner,
    _dispatch_write,
    _ensure_claude_config_dir,
    _implementer_claude_seat,
    _linked_worktree,
    _pin_temp_base_to_tmp_path,
    _write_opened_record,
)

_REMOVED_CONSTANTS = (
    "REFUSAL_SANDBOX_LANDING_DIR_INVALID",
    "REFUSAL_SANDBOX_LANDING_DIR_DENIED",
    "REFUSAL_SANDBOX_LANDING_DIR_MISMATCH",
)


def _dispatch_write_parser():
    parser = ED.build_parser()
    subparsers = [a for a in parser._actions if getattr(a, "choices", None)
                  and "dispatch-write" in a.choices]
    assert len(subparsers) == 1
    return subparsers[0].choices["dispatch-write"]


def test_dispatch_write_parser_has_no_landing_dir_option(capsys):
    write = _dispatch_write_parser()
    option_strings = [s for action in write._actions for s in action.option_strings]
    assert "--landing-dir" not in option_strings
    assert "landing-dir" not in write.format_help()
    assert "--add-dir" not in write.format_help()
    with pytest.raises(SystemExit):
        ED.build_parser().parse_args([
            "dispatch-write", "--seat", "{}", "--prompt-path", "p", "--cwd", ".",
            "--run-dir", "r", "--landing-dir", "/x/round-1/landing/p"])
    assert "--landing-dir" in capsys.readouterr().err


def test_adapter_has_no_landing_dir_refusal_constants():
    for name in _REMOVED_CONSTANTS:
        assert not hasattr(EA, name), name
    assert [n for n in dir(EA) if "LANDING" in n.upper()] == []
    assert [t for t in EA.BUILD_ARGV_REFUSAL_TOKENS if "landing-dir" in t] == []
    assert not hasattr(ED, "_landing_dir_grant")


def test_no_is_landing_dir_helper():
    assert not hasattr(record_paths, "is_landing_dir")
    assert "is_landing_dir" not in record_paths.__all__
    assert not hasattr(RR, "is_landing_dir")
    # the layout itself stays: every review seat lands there
    assert record_paths.landing_dir("/s", 1, "p") == "/s/round-1/landing/p"


# --- characterization: a no-grant open sends what the base commit sent ---------------------------


def _write_argv(sandbox):
    return EA.build_argv_result(
        {"vendor": "claude", "model": "sonnet-5.5", "effort": "high", "role": "implementer"},
        "build", {"claudeWriteSandbox": sandbox})["argv"]


def _expected_no_grant_settings(sandbox, allow_write):
    network = {"allowedDomains": [], "strictAllowlist": True}
    if sandbox["localBinding"]:
        network["allowLocalBinding"] = True
    return {
        "env": {"UV_OFFLINE": "1"},
        "permissions": {"allow": list(EA.CLAUDE_WRITE_BASH_ALLOW), "deny": ["WebFetch", "WebSearch"]},
        "sandbox": {
            "enabled": True,
            "failIfUnavailable": True,
            "autoAllowBashIfSandboxed": True,
            "allowUnsandboxedCommands": False,
            "network": network,
            "filesystem": {"allowWrite": allow_write, "denyWrite": list(sandbox["denyWrite"])},
        },
    }


def _expected_tmp_roots():
    real = os.path.realpath("/tmp")
    return ["/tmp"] if real == "/tmp" else ["/tmp", real]


def _resolve_no_grant_sandbox(tmp_path, monkeypatch):
    _ensure_claude_config_dir(tmp_path, monkeypatch)
    wt, main = _linked_worktree(tmp_path)
    cwd_real = os.path.realpath(wt)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    sandbox, refusal = ED._resolve_claude_write_sandbox(cwd_real, timeout=30, run_dir=run_dir)
    assert refusal is None
    git_common = os.path.realpath(os.path.join(main, ".git"))
    git_dir = os.path.realpath(os.path.join(main, ".git", "worktrees", "wt"))
    return wt, sandbox, [cwd_real, git_dir, git_common]


def test_no_grant_open_builds_the_base_sandbox_argv_and_settings(tmp_path, monkeypatch):
    _wt, sandbox, write_roots = _resolve_no_grant_sandbox(tmp_path, monkeypatch)
    assert set(sandbox) <= {"writeRoots", "denyWrite", "uvCacheDir", "tmpWriteRoots",
                            "localBinding", "access", "claudeTmpBase"}
    assert sandbox["writeRoots"] == write_roots
    assert sandbox["uvCacheDir"] is None
    assert sandbox["tmpWriteRoots"] == _expected_tmp_roots()
    assert sandbox["access"]["extraWritePaths"] == []
    argv = _write_argv(sandbox)
    assert "--add-dir" not in argv
    # a no-grant argv is exactly the base shape; --settings is last and carries the sandbox
    assert argv[:2] == ["claude", "-p"]
    assert argv[argv.index("--output-format"):argv.index("--output-format") + 3] == [
        "--output-format", "stream-json", "--verbose"]
    assert argv[argv.index("--permission-mode"):-1] == [
        "--permission-mode", "acceptEdits", "--restricted", "--tools", EA.CLAUDE_WRITE_TOOLS,
        "--strict-mcp-config", "--settings"]
    assert len(argv) == 17
    settings = json.loads(argv[-1])
    allow_write = settings["sandbox"]["filesystem"]["allowWrite"]
    assert allow_write == write_roots + _expected_tmp_roots()
    assert settings == _expected_no_grant_settings(sandbox, write_roots + _expected_tmp_roots())


def test_no_grant_open_spawns_the_journaled_argv_without_add_dir(tmp_path, monkeypatch):
    wt, _sandbox, write_roots = _resolve_no_grant_sandbox(tmp_path, monkeypatch)
    run_dir = str(tmp_path / "open-run")
    fake = _ClaudeStdoutWriteFakeRunner([_claude_write_runner()])
    res = _dispatch_write(tmp_path, fake, cwd=wt, run_dir=run_dir,
                          seat=_implementer_claude_seat())
    assert res["ok"] is True, res
    opened = _write_opened_record(run_dir)
    assert "landingDir" not in opened["claudeWriteSandbox"]
    assert "--add-dir" not in opened["argv"]
    assert fake.calls[0]["argv"] == opened["argv"]
    settings = json.loads(opened["argv"][opened["argv"].index("--settings") + 1])
    allow_write = settings["sandbox"]["filesystem"]["allowWrite"]
    # the run dir lives under tmp_path, outside every grant except the /tmp one: the write-allow
    # list is the roots plus the /tmp grants, nothing else
    assert allow_write[:len(write_roots)] == write_roots
    assert allow_write[len(write_roots):] == _expected_tmp_roots()
