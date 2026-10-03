"""#1554: the claude write channel runs a sandboxed shell, roots frozen at run open.

Invariant: a claude write argv is always the sandboxed shape, built only from sandbox inputs the
dispatcher resolved once at open and journaled; never re-derived at continuation or spawn."""
import json
import os
import subprocess

import pytest

# The write-dispatch suite's helpers and its autouse tmp-base/journal-root/uv-absent fixture.
from test_engine_dispatch_write import (  # noqa: F401
    ED,
    EA,
    _ClaudeStdoutWriteFakeRunner,
    _claude_write_runner,
    _dispatch_write,
    _ensure_claude_config_dir,
    _implementer_claude_seat,
    _linked_worktree,
    _init_repo,
    _pin_temp_base_to_tmp_path,
    _prompt,
    _seat,
    _write_opened_record,
)

_SANDBOX = {
    "writeRoots": ["/work/wt", "/work/main/.git/worktrees/wt", "/work/main/.git"],
    "denyWrite": ["/work/main/.git/hooks", "/work/main/.git/config",
                  "/work/main/.git/worktrees/wt/config.worktree"],
    "uvCacheDir": None,
}


def _claude_seat():
    return _seat("claude", "sonnet-5.5", "high")


def _write_argv(sandbox=_SANDBOX, **extra):
    opts = {"claudeWriteSandbox": sandbox}
    opts.update(extra)
    return EA.build_argv_result(_claude_seat(), "build", opts)


def _settings_of(argv):
    return json.loads(argv[argv.index("--settings") + 1])


def _assert_sandboxed_shape(argv):
    """The invariant, asserted over a built argv rather than any one call site's end state."""
    assert argv[0] == "claude"
    for flag in ("--restricted", "--strict-mcp-config", "--tools", "--settings"):
        assert flag in argv, (flag, argv)
    assert argv[argv.index("--tools") + 1] == "Bash,Edit,Write,Read,Grep,Glob"
    assert argv[argv.index("--permission-mode") + 1] == "acceptEdits"
    sb = _settings_of(argv)["sandbox"]
    assert sb["enabled"] is True and sb["failIfUnavailable"] is True
    assert sb["allowUnsandboxedCommands"] is False


def _fake_uv(tmp_path, monkeypatch):
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir(exist_ok=True)
    uv = bin_dir / "uv"
    uv.write_text(
        '#!/bin/sh\nif [ "$1" = cache ]; then echo "$FAKE_UV_CACHE"; exit "${FAKE_UV_RC:-0}"; fi\n'
        "exit 2\n", encoding="utf-8")
    uv.chmod(0o755)
    real_which = ED.shutil.which
    monkeypatch.setattr(
        ED.shutil, "which",
        lambda cmd, *a, **k: str(uv) if cmd == "uv" else real_which(cmd, *a, **k),
    )
    return str(uv)


# --- adapter: exact argv and settings -------------------------------------------------------


def test_claude_write_exact_argv():
    res = _write_argv()
    assert res["reason"] is None
    assert res["argv"] == [
        "claude", "-p", "--model", "sonnet", "--effort", "high",
        "--output-format", "stream-json", "--verbose",
        "--permission-mode", "acceptEdits", "--restricted",
        "--tools", "Bash,Edit,Write,Read,Grep,Glob",
        "--strict-mcp-config",
        "--settings", EA.claude_write_sandbox_settings(_SANDBOX),
    ]
    _assert_sandboxed_shape(res["argv"])


def test_settings_json_keys():
    raw = EA.claude_write_sandbox_settings(_SANDBOX)
    assert raw == json.dumps(json.loads(raw), sort_keys=True, separators=(",", ":"))
    obj = json.loads(raw)
    assert obj == {
        "env": {"UV_OFFLINE": "1"},
        "permissions": {
            "allow": ["Bash(python:*)", "Bash(python3:*)", "Bash(pytest:*)",
                      "Bash(scripts/pinned-python:*)", "Bash(echo:*)",
                      "Bash(npm:*)", "Bash(npx:*)", "Bash(node:*)", "Bash(pnpm:*)",
                      "Bash(yarn:*)", "Bash(ps:*)"],
            "deny": ["WebFetch", "WebSearch"],
        },
        "sandbox": {
            "enabled": True,
            "failIfUnavailable": True,
            "autoAllowBashIfSandboxed": True,
            "allowUnsandboxedCommands": False,
            "network": {"allowedDomains": [], "strictAllowlist": True},
            "filesystem": {
                "allowWrite": _SANDBOX["writeRoots"],
                "denyWrite": _SANDBOX["denyWrite"],
            },
        },
    }


def test_settings_uv_cache_present_only_when_set():
    none_obj = json.loads(EA.claude_write_sandbox_settings(_SANDBOX))
    assert "UV_CACHE_DIR" not in none_obj["env"]
    assert none_obj["sandbox"]["filesystem"]["allowWrite"] == _SANDBOX["writeRoots"]
    with_cache = dict(_SANDBOX, uvCacheDir="/cache/uv")
    obj = json.loads(EA.claude_write_sandbox_settings(with_cache))
    assert obj["env"] == {"UV_OFFLINE": "1", "UV_CACHE_DIR": "/cache/uv"}
    assert obj["sandbox"]["filesystem"]["allowWrite"] == _SANDBOX["writeRoots"] + ["/cache/uv"]


# --- adapter refusals (E1, E2, E6, E9) ----------------------------------------------------


def test_claude_write_without_sandbox_refuses_roots_missing():
    for opts in ({}, {"cwd": "/work/wt"}, {"claudeWriteSandbox": None}):
        res = EA.build_argv_result(_claude_seat(), "build", opts)
        assert res["reason"] == "sandbox-roots-missing", opts
        assert res["argv"] == []


@pytest.mark.parametrize("bad", [
    pytest.param("not-a-dict", id="not-a-dict"),
    pytest.param(dict(_SANDBOX, writeRoots=[]), id="empty-roots"),
    pytest.param(dict(_SANDBOX, writeRoots="/work/wt"), id="roots-not-list"),
    pytest.param(dict(_SANDBOX, writeRoots=["relative/wt"]), id="roots-relative"),
    pytest.param(dict(_SANDBOX, denyWrite="/x"), id="deny-not-list"),
    pytest.param(dict(_SANDBOX, denyWrite=["rel/hooks"]), id="deny-relative"),
    pytest.param(dict(_SANDBOX, uvCacheDir="rel/cache"), id="uv-relative"),
    pytest.param(dict(_SANDBOX, uvCacheDir=7), id="uv-not-str"),
    pytest.param({k: v for k, v in _SANDBOX.items() if k != "denyWrite"}, id="deny-absent"),
])
def test_claude_write_malformed_sandbox_refuses_roots_missing(bad):
    res = _write_argv(bad)
    assert res["reason"] == "sandbox-roots-missing"
    assert res["argv"] == []


def test_requires_process_listing_refuses_claude_write_only():
    refused = _write_argv(requiresProcessListing=True)
    assert refused["reason"] == "sandbox-process-listing-unavailable"
    assert refused["argv"] == []
    # the declared reason wins over missing roots
    both = EA.build_argv_result(_claude_seat(), "build", {"requiresProcessListing": True})
    assert both["reason"] == "sandbox-process-listing-unavailable"
    # cursor/codex ignore the flag: argv byte-identical
    for vendor, model, effort in (("codex", "gpt-5.6-sol", "high"),
                                  ("cursor", "composer-2.5", None)):
        seat = _seat(vendor, model, effort)
        plain = EA.build_argv_result(seat, "build", {})
        flagged = EA.build_argv_result(seat, "build", {"requiresProcessListing": True})
        assert flagged == plain
        assert flagged["reason"] is None, (vendor, flagged)


def test_claude_review_argv_unchanged_by_sandbox_inputs():
    plain = EA.build_argv_result(_claude_seat(), "review", {})
    assert plain["argv"] == [
        "claude", "-p", "--model", "sonnet", "--effort", "high",
        "--output-format", "stream-json", "--verbose", "--restricted",
    ]
    loaded = EA.build_argv_result(
        _claude_seat(), "review",
        {"claudeWriteSandbox": _SANDBOX, "requiresProcessListing": True},
    )
    assert loaded == plain
    assert "--settings" not in loaded["argv"]


def test_claude_builder_argv_unchanged():
    sid = "550e8400-e29b-41d4-a716-446655440000"
    assert EA.claude_builder_argv("sonnet", sid, "p")["argv"] == [
        "claude", "--model", "sonnet", "--session-id", sid, "-p", "p",
    ]


def test_new_refusal_tokens_registered():
    for tok in ("sandbox-roots-missing", "sandbox-process-listing-unavailable",
                "sandbox-roots-unresolvable", "sandbox-uv-cache-unresolvable"):
        assert tok in EA.BUILD_ARGV_REFUSAL_TOKENS


def test_build_argv_cli_claude_write_refuses_roots_missing(capsys):
    seat = json.dumps({"vendor": "claude", "model": "sonnet-5.5", "effort": "high",
                       "role": "implementer"})
    rc = EA.main(["build-argv", "--seat", seat, "--run-kind", "build", "--cwd", "/tmp"])
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert rc != 0
    assert out["detail"] == "sandbox-roots-missing"


# --- dispatcher resolver (E3, E4, E5, E10) -------------------------------------------------


def test_resolver_linked_worktree_roots_and_denies(tmp_path):
    wt, main = _linked_worktree(tmp_path)
    wt_real, main_real = os.path.realpath(wt), os.path.realpath(main)
    sandbox, refusal = ED._resolve_claude_write_sandbox(wt_real, timeout=30)
    assert refusal is None
    git_dir = os.path.join(main_real, ".git", "worktrees", "wt")
    common = os.path.join(main_real, ".git")
    assert os.path.realpath(git_dir) != common
    assert sandbox["writeRoots"] == [wt_real, os.path.realpath(git_dir), common]
    git_dir_real = os.path.realpath(git_dir)
    assert sandbox["denyWrite"] == [
        os.path.join(wt_real, ".git"),
        os.path.join(common, "hooks"),
        os.path.join(common, "config"),
        os.path.join(git_dir_real, "config.worktree"),
        os.path.join(git_dir_real, "commondir"),
        os.path.join(git_dir_real, "gitdir"),
    ]
    assert sandbox["uvCacheDir"] is None  # autouse fixture pins uv absent (E5)


def test_resolver_plain_repo_dedupes_roots(tmp_path):
    repo = _init_repo(str(tmp_path / "plain"))
    repo_real = os.path.realpath(repo)
    sandbox, refusal = ED._resolve_claude_write_sandbox(repo_real, timeout=30)
    assert refusal is None
    assert sandbox["writeRoots"] == [repo_real, os.path.join(repo_real, ".git")]


def test_resolver_git_failure_refuses_roots_unresolvable(tmp_path, monkeypatch):
    not_repo = str(tmp_path / "nogit")
    os.makedirs(not_repo)
    assert ED._resolve_claude_write_sandbox(
        os.path.realpath(not_repo), timeout=30) == (None, "sandbox-roots-unresolvable")
    wt, _main = _linked_worktree(tmp_path)

    def boom(*a, **k):
        raise subprocess.TimeoutExpired("git", 1)

    monkeypatch.setattr(ED, "_git_scrubbed", boom)
    assert ED._resolve_claude_write_sandbox(
        os.path.realpath(wt), timeout=1) == (None, "sandbox-roots-unresolvable")

    class _Out:
        returncode = 0
        stdout = "only-one-line\n"

    monkeypatch.setattr(ED, "_git_scrubbed", lambda *a, **k: _Out())
    assert ED._resolve_claude_write_sandbox(
        os.path.realpath(wt), timeout=1) == (None, "sandbox-roots-unresolvable")


def test_resolver_uv_present_resolves_cache_dir(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)
    cache = str(tmp_path / "uvcache")
    os.makedirs(cache)
    _fake_uv(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_UV_CACHE", cache)
    sandbox, refusal = ED._resolve_claude_write_sandbox(os.path.realpath(wt), timeout=30)
    assert refusal is None
    assert sandbox["uvCacheDir"] == os.path.realpath(cache)


def test_resolver_uv_relative_cache_dir_against_worktree_cwd(tmp_path, monkeypatch):
    """Relative `uv cache dir` output is resolved against cwd_real, not the dispatcher cwd."""
    wt, _main = _linked_worktree(tmp_path)
    wt_real = os.path.realpath(wt)
    rel = "rel-uv-cache"
    cache_expected = os.path.join(wt_real, rel)
    os.makedirs(cache_expected, exist_ok=True)
    _fake_uv(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_UV_CACHE", rel)
    other_cwd = str(tmp_path / "dispatcher-cwd")
    os.makedirs(other_cwd)
    monkeypatch.chdir(other_cwd)
    sandbox, refusal = ED._resolve_claude_write_sandbox(wt_real, timeout=30)
    assert refusal is None
    assert sandbox["uvCacheDir"] == os.path.realpath(cache_expected)
    assert sandbox["uvCacheDir"] != os.path.realpath(os.path.join(other_cwd, rel))


def test_resolver_uv_present_but_cache_dir_fails_refuses(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)
    _fake_uv(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_UV_CACHE", str(tmp_path / "x"))
    monkeypatch.setenv("FAKE_UV_RC", "3")
    assert ED._resolve_claude_write_sandbox(
        os.path.realpath(wt), timeout=30) == (None, "sandbox-uv-cache-unresolvable")
    monkeypatch.setenv("FAKE_UV_RC", "0")
    monkeypatch.setenv("FAKE_UV_CACHE", "")
    assert ED._resolve_claude_write_sandbox(
        os.path.realpath(wt), timeout=30) == (None, "sandbox-uv-cache-unresolvable")


def test_dispatch_write_surfaces_resolver_refusal_as_engine_config(tmp_path, monkeypatch):
    _ensure_claude_config_dir(tmp_path, monkeypatch)
    wt, _main = _linked_worktree(tmp_path)
    _fake_uv(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_UV_RC", "3")
    monkeypatch.setenv("FAKE_UV_CACHE", "x")
    run_dir = str(tmp_path / "run")
    fake = _ClaudeStdoutWriteFakeRunner([_claude_write_runner()])
    res = _dispatch_write(tmp_path, fake, cwd=wt, run_dir=run_dir,
                          seat=_implementer_claude_seat())
    assert res["detail"] == "engine-config:sandbox-uv-cache-unresolvable"
    assert res["attempts"] == 0
    assert fake.calls == []
    assert not os.path.exists(os.path.join(run_dir, "journal.jsonl")) or all(
        r.get("kind") != "run-opened" for r in ED._journal_read(run_dir)[0])


# --- journal: frozen at open (E7, E8) and the invariant at every call site -----------------


def _open_claude_write(tmp_path, monkeypatch, **kw):
    _ensure_claude_config_dir(tmp_path, monkeypatch)
    wt, _main = _linked_worktree(tmp_path)
    run_dir = str(tmp_path / "run")
    fake = _ClaudeStdoutWriteFakeRunner([_claude_write_runner()])
    res = _dispatch_write(tmp_path, fake, cwd=wt, run_dir=run_dir,
                          seat=_implementer_claude_seat(), **kw)
    return wt, run_dir, res, fake


def test_run_opened_record_carries_sandbox_and_argv_is_sandboxed(tmp_path, monkeypatch):
    wt, run_dir, _res, fake = _open_claude_write(tmp_path, monkeypatch)
    opened = _write_opened_record(run_dir)
    sandbox = opened["claudeWriteSandbox"]
    assert sandbox["writeRoots"][0] == os.path.realpath(wt)
    assert sandbox["uvCacheDir"] is None
    argv = opened["argv"]
    _assert_sandboxed_shape(argv)
    assert _settings_of(argv) == json.loads(EA.claude_write_sandbox_settings(sandbox))
    # the spawned argv (what the runner received) is the same sandboxed shape
    assert fake.calls
    _assert_sandboxed_shape(fake.calls[0]["argv"])
    # spawn coherence: the canonical argv derived from the journal equals the stored argv
    canonical, err = ED._canonical_spawn_argv(opened)
    assert err is None
    assert canonical == argv
    _assert_sandboxed_shape(canonical)


def test_continuation_uses_journaled_sandbox_not_environment(tmp_path, monkeypatch):
    cache_a = str(tmp_path / "cache-a")
    cache_b = str(tmp_path / "cache-b")
    os.makedirs(cache_a)
    os.makedirs(cache_b)
    _fake_uv(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_UV_CACHE", cache_a)
    calls = []
    real = ED._resolve_claude_write_sandbox

    def spy(*a, **k):
        calls.append(a)
        return real(*a, **k)

    monkeypatch.setattr(ED, "_resolve_claude_write_sandbox", spy)
    wt, run_dir, first, _fake = _open_claude_write(tmp_path, monkeypatch)
    opened = _write_opened_record(run_dir)
    assert opened["claudeWriteSandbox"]["uvCacheDir"] == os.path.realpath(cache_a)
    assert len(calls) == 1
    # the ambient cache changes; a continuation must not notice
    monkeypatch.setenv("FAKE_UV_CACHE", cache_b)
    fake2 = _ClaudeStdoutWriteFakeRunner([_claude_write_runner()])
    second = _dispatch_write(tmp_path, fake2, cwd=wt, run_dir=run_dir,
                             seat=_implementer_claude_seat())
    assert len(calls) == 1, "a continuation re-resolved the sandbox"
    assert second["argv"] == first["argv"]
    assert _write_opened_record(run_dir)["claudeWriteSandbox"]["uvCacheDir"] == (
        os.path.realpath(cache_a))
    assert os.path.realpath(cache_a) in second["argv"][second["argv"].index("--settings") + 1]


def test_opened_record_without_sandbox_refuses_roots_missing(tmp_path, monkeypatch):
    wt, run_dir, _res, _fake = _open_claude_write(tmp_path, monkeypatch)
    opened = dict(_write_opened_record(run_dir))
    opened.pop("claudeWriteSandbox")
    argv, err = ED._canonical_spawn_argv(opened)
    assert argv is None
    assert err == "engine-config:sandbox-roots-missing"
    # a continuation of an older record (rewritten without the key) refuses, never re-derives
    records, _ = ED._journal_read(run_dir)
    with open(ED._journal_path(run_dir), "w", encoding="utf-8") as fh:
        for rec in records:
            if rec.get("kind") == "run-opened":
                rec.pop("claudeWriteSandbox", None)
            fh.write(json.dumps(rec) + "\n")
    res = _dispatch_write(tmp_path, _ClaudeStdoutWriteFakeRunner([]), cwd=wt, run_dir=run_dir,
                          seat=_implementer_claude_seat())
    assert res["detail"] == "engine-config:sandbox-roots-missing"
    assert res["attempts"] == 0


# --- CLI flag (E6) ---------------------------------------------------------------------------


def _cli_write(tmp_path, capsys, seat, wt, run_dir, *extra):
    argv = ["dispatch-write", "--seat", json.dumps(seat), "--prompt-path", _prompt(tmp_path),
            "--cwd", wt, "--run-dir", run_dir, *extra]
    ED.main(argv)
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_cli_requires_process_listing_refuses_claude_before_open(tmp_path, monkeypatch, capsys):
    _ensure_claude_config_dir(tmp_path, monkeypatch)
    wt, _main = _linked_worktree(tmp_path)
    run_dir = str(tmp_path / "run-pl")
    res = _cli_write(tmp_path, capsys, _implementer_claude_seat(), wt, run_dir,
                     "--requires-process-listing")
    assert res["detail"] == "engine-config:sandbox-process-listing-unavailable"
    assert res["attempts"] == 0
    records, _ = ED._journal_read(run_dir)
    assert all(r.get("kind") != "run-opened" for r in records)


def test_cli_requires_process_listing_does_not_affect_cursor(tmp_path, monkeypatch, capsys):
    wt, _main = _linked_worktree(tmp_path)
    run_dir = str(tmp_path / "run-cursor")
    seat = {"vendor": "cursor", "model": "composer-2.5", "effort": None, "role": "implementer"}
    built = EA.build_argv_result(_seat("cursor", "composer-2.5", None), "build", {})
    flagged = EA.build_argv_result(
        _seat("cursor", "composer-2.5", None), "build", {"requiresProcessListing": True})
    assert flagged == built and flagged["reason"] is None
    # the flag is accepted by the parser and never journaled
    args = ED.build_parser().parse_args([
        "dispatch-write", "--seat", json.dumps(seat), "--prompt-path", "p", "--cwd", wt,
        "--run-dir", run_dir, "--requires-process-listing"])
    assert args.requires_process_listing is True
