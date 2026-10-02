"""#1562 layer 2: the sandboxAccess calibration is journaled at claude-write run open and mapped
into the sandbox settings.

Invariant: the calibration is read once, at run open, and only there. A continuation or spawn uses
the journaled value; the sandbox settings are a pure function of the journal.

Token and setting-name literals are spelled out as strings on purpose: a test that reaches them
through the module constants stays green under any value (rubric/bite-proof.md).

Detector axes (bite-proof):
- test_all_off_settings_are_byte_identical — preservation: all-off settings equal today's bytes
- test_*_drives_through_open — mapping: each option alone reaches the settings of an opened run
- test_malformed_* / test_unreadable_* — refusal: no run opens on a bad calibration
- test_continuation_* — journal reuse: a continuation never re-reads core.md
- test_access_validity_* — journal validity: a malformed journaled access refuses
- test_deny_write_* — deny wins: extraWritePaths never narrow denyWrite
- test_*_unsupported_platform_* — refusal: local access on a host that cannot grant it
- test_extra_write_path_resolving_to_root_* — refusal: an alias of / never reaches allowWrite
- test_local_socket_dir_* — mapping: the grant follows the CLI's own temp-dir rule
"""
import json
import os

import pytest

# The 1554 suite's harness (and, through it, the write-dispatch suite's autouse fixture).
import test_claude_write_sandbox_1554 as S1554
from test_claude_write_sandbox_1554 import (  # noqa: F401
    ED,
    EA,
    _ClaudeStdoutWriteFakeRunner,
    _SANDBOX,
    _claude_write_runner,
    _dispatch_write,
    _implementer_claude_seat,
    _linked_worktree,
    _open_claude_write,
    _pin_temp_base_to_tmp_path,
    _settings_of,
    _write_argv,
    _write_opened_record,
)

import core_md  # noqa: E402  (sibling; on sys.path through the engine_dispatch import)

_KEY = "sandboxAccess"
_NO_KEY = object()

_CORE_FACTS = {
    "verifyCommand": "npm test",
    "stackTags": ["node"],
    "threatModel": "single-user",
    "patterns": "- x: a.ts:1",
}

_ALL_OFF_ACCESS = {
    "allowedDomains": [], "localPorts": False, "localSocketDirs": [], "extraWritePaths": [],
}

# Today's settings JSON (before #1562) for _BYTE_SANDBOX, spelled out. Emitting no new key at all —
# not `false`, not `[]` — is the contract of an all-off run.
_BYTE_SANDBOX = dict(_SANDBOX, uvCacheDir="/cache/uv")
_TODAYS_SETTINGS = (
    '{"env":{"UV_CACHE_DIR":"/cache/uv","UV_OFFLINE":"1"},'
    '"permissions":{"allow":["Bash(python:*)","Bash(python3:*)","Bash(pytest:*)",'
    '"Bash(scripts/pinned-python:*)","Bash(echo:*)"],"deny":["WebFetch","WebSearch"]},'
    '"sandbox":{"allowUnsandboxedCommands":false,"autoAllowBashIfSandboxed":true,'
    '"enabled":true,"failIfUnavailable":true,'
    '"filesystem":{"allowWrite":["/work/wt","/work/main/.git/worktrees/wt","/work/main/.git",'
    '"/cache/uv"],'
    '"denyWrite":["/work/main/.git/hooks","/work/main/.git/config",'
    '"/work/main/.git/worktrees/wt/config.worktree"]},'
    '"network":{"allowedDomains":[],"strictAllowlist":true}}}'
)
# The same settings as before the claude write channel's Bash allow rules (#1569).
_SETTINGS_0_38_0 = (
    '{"env":{"UV_CACHE_DIR":"/cache/uv","UV_OFFLINE":"1"},'
    '"permissions":{"deny":["WebFetch","WebSearch"]},'
    '"sandbox":{"allowUnsandboxedCommands":false,"autoAllowBashIfSandboxed":true,'
    '"enabled":true,"failIfUnavailable":true,'
    '"filesystem":{"allowWrite":["/work/wt","/work/main/.git/worktrees/wt","/work/main/.git",'
    '"/cache/uv"],'
    '"denyWrite":["/work/main/.git/hooks","/work/main/.git/config",'
    '"/work/main/.git/worktrees/wt/config.worktree"]},'
    '"network":{"allowedDomains":[],"strictAllowlist":true}}}'
)


@pytest.fixture(autouse=True)
def _pin_store_root(tmp_path, monkeypatch):
    """core.md resolution may consult the project store; never the real one."""
    store = str(tmp_path / "store-root")
    os.makedirs(store, exist_ok=True)
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", store)
    monkeypatch.delenv("WORKHORSE_STORE_ROOT", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_TMPDIR", raising=False)
    # local access is macOS-only; the tests that exercise it must not depend on the host running them
    monkeypatch.setattr(ED, "_host_platform", lambda: "darwin")


# --- harness: a core.md in the linked worktree the open resolves from ------------------------


def _core_text(block=_NO_KEY):
    facts = dict(_CORE_FACTS)
    if block is not _NO_KEY:
        facts[_KEY] = block
    return core_md.render_core(facts, "confirmed", "2026-06-26", "2026-06-26")


def _corrupt_core_text():
    return core_md._JSON_BLOCK.sub(
        lambda m: "```json superheroes-core\n{not json\n```", _core_text())


def _write_core(wt, text):
    path = os.path.join(wt, core_md.in_repo_core_rel_path())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _open_with_core(tmp_path, monkeypatch, core, **kw):
    """Open a claude write through the 1554 harness with ``core`` written into the worktree first.

    ``core`` is core.md text, ``None`` (no core.md), or a callable ``(wt, main) -> text``;
    ``kw`` is forwarded to the dispatch (e.g. ``max_wait=0`` to leave the run unfinished)."""
    real_linked_worktree = S1554._linked_worktree

    def linked_worktree_with_core(tp):
        wt, main = real_linked_worktree(tp)
        text = core(wt, main) if callable(core) else core
        if text is not None:
            _write_core(wt, text)
        return wt, main

    monkeypatch.setattr(S1554, "_linked_worktree", linked_worktree_with_core)
    return _open_claude_write(tmp_path, monkeypatch, **kw)


def _no_run_opened(run_dir):
    journal = ED._journal_path(run_dir)
    return not os.path.exists(journal) or all(
        r.get("kind") != "run-opened" for r in ED._journal_read(run_dir)[0])


def _opened_settings(run_dir, fake):
    """The run-opened record's settings; the spawned argv must carry the same ones."""
    opened = _write_opened_record(run_dir)
    settings = _settings_of(opened["argv"])
    assert fake.calls
    assert _settings_of(fake.calls[0]["argv"]) == settings
    return opened, settings


def _assert_options(opened, settings, *, domains=None, ports=False, sockets=None, extra=None):
    """Every option not named stays absent or off in the settings."""
    network = settings["sandbox"]["network"]
    allow_write = settings["sandbox"]["filesystem"]["allowWrite"]
    roots = opened["claudeWriteSandbox"]["writeRoots"]
    if domains is None:
        assert network["allowedDomains"] == []
        assert settings["env"]["UV_OFFLINE"] == "1"
    else:
        assert network["allowedDomains"] == domains
        assert "UV_OFFLINE" not in settings["env"]
    assert network["strictAllowlist"] is True
    if ports:
        assert network["allowLocalBinding"] is True
    else:
        assert "allowLocalBinding" not in network
    if sockets is None:
        assert "allowUnixSockets" not in network
    else:
        assert network["allowUnixSockets"] == sockets
    if extra is None:
        assert allow_write == roots
    else:
        assert allow_write == roots + extra


# --- T1: byte identity (G16) -----------------------------------------------------------------


def test_all_off_settings_are_byte_identical():
    assert EA.claude_write_sandbox_settings(_BYTE_SANDBOX) == _TODAYS_SETTINGS
    assert EA.claude_write_sandbox_settings(dict(_BYTE_SANDBOX, access=None)) == _TODAYS_SETTINGS
    assert EA.claude_write_sandbox_settings(
        dict(_BYTE_SANDBOX, access=dict(_ALL_OFF_ACCESS))) == _TODAYS_SETTINGS


def test_all_off_differs_from_0_38_0_only_by_allow_rules():
    new = json.loads(EA.claude_write_sandbox_settings(_BYTE_SANDBOX))
    assert new["permissions"].pop("allow") == [
        "Bash(python:*)", "Bash(python3:*)", "Bash(pytest:*)",
        "Bash(scripts/pinned-python:*)", "Bash(echo:*)",
    ]
    assert new == json.loads(_SETTINGS_0_38_0)


# --- T2-T5: each option alone, driven through a real open (G12-G15) ---------------------------


def test_domains_drives_through_open(tmp_path, monkeypatch):
    wt, run_dir, _res, fake = _open_with_core(
        tmp_path, monkeypatch, _core_text({"allowedDomains": ["pypi.org"]}))
    opened, settings = _opened_settings(run_dir, fake)
    assert opened["claudeWriteSandbox"]["access"] == {
        "allowedDomains": ["pypi.org"], "localPorts": False,
        "localSocketDirs": [], "extraWritePaths": [],
    }
    assert settings["sandbox"]["network"]["allowedDomains"] == ["pypi.org"]
    assert "UV_OFFLINE" not in settings["env"]
    _assert_options(opened, settings, domains=["pypi.org"])


def test_all_off_run_stays_offline(tmp_path, monkeypatch):
    wt, run_dir, _res, fake = _open_with_core(tmp_path, monkeypatch, _core_text())
    opened, settings = _opened_settings(run_dir, fake)
    assert opened["claudeWriteSandbox"]["access"] == _ALL_OFF_ACCESS
    assert settings["env"]["UV_OFFLINE"] == "1"
    _assert_options(opened, settings)


def test_local_ports_drives_through_open(tmp_path, monkeypatch):
    wt, run_dir, _res, fake = _open_with_core(
        tmp_path, monkeypatch, _core_text({"localPorts": True}))
    opened, settings = _opened_settings(run_dir, fake)
    assert opened["claudeWriteSandbox"]["access"]["localPorts"] is True
    assert settings["sandbox"]["network"]["allowLocalBinding"] is True
    _assert_options(opened, settings, ports=True)


def test_local_sockets_drives_through_open(tmp_path, monkeypatch):
    cc_tmp = "/tmp/cc-tmp"  # short enough for the CLI to honor
    monkeypatch.setenv("CLAUDE_CODE_TMPDIR", cc_tmp)
    wt, run_dir, _res, fake = _open_with_core(
        tmp_path, monkeypatch, _core_text({"localSockets": True}))
    opened, settings = _opened_settings(run_dir, fake)
    expected = os.path.realpath(os.path.join(cc_tmp, "claude-%d" % os.getuid()))
    assert settings["sandbox"]["network"]["allowUnixSockets"] == [expected]
    assert opened["claudeWriteSandbox"]["access"]["localSocketDirs"] == [expected]
    _assert_options(opened, settings, sockets=[expected])


def test_extra_write_paths_drives_through_open(tmp_path, monkeypatch):
    real_dir = tmp_path / "real-cache"
    real_dir.mkdir()
    link = tmp_path / "link-cache"
    link.symlink_to(real_dir)
    wt, run_dir, _res, fake = _open_with_core(
        tmp_path, monkeypatch, _core_text({"extraWritePaths": [str(link)]}))
    opened, settings = _opened_settings(run_dir, fake)
    expected = os.path.realpath(str(real_dir))
    assert expected in settings["sandbox"]["filesystem"]["allowWrite"]
    assert str(link) not in settings["sandbox"]["filesystem"]["allowWrite"]
    _assert_options(opened, settings, extra=[expected])


def test_local_socket_dir_defaults_to_tmp(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    _write_core(wt, _core_text({"localSockets": True}))
    sandbox, refusal = ED._resolve_claude_write_sandbox(os.path.realpath(wt), timeout=30)
    assert refusal is None
    assert sandbox["access"]["localSocketDirs"] == [
        os.path.join(os.path.realpath("/tmp"), "claude-%d" % os.getuid())]


def _socket_dirs_for(tmp_path, monkeypatch, override):
    wt, _main = _linked_worktree(tmp_path)
    _write_core(wt, _core_text({"localSockets": True}))
    if override is not None:
        monkeypatch.setenv("CLAUDE_CODE_TMPDIR", override)
    sandbox, refusal = ED._resolve_claude_write_sandbox(os.path.realpath(wt), timeout=30)
    assert refusal is None
    return sandbox["access"]["localSocketDirs"]


def _tmp_claude_uid_dir():
    return os.path.realpath(os.path.join("/tmp", "claude-%d" % os.getuid()))


def test_local_socket_dir_limit_is_44_bytes():
    # pinned as a literal: the Claude Code 2.1.284 rule this mirrors (rubric/bite-proof.md)
    assert ED._CLAUDE_CODE_TMPDIR_MAX_BYTES == 44


def _override_with_user_dir_bytes(total, filler="a"):
    """A /-rooted override whose <override>/claude-<uid> path is exactly ``total`` UTF-8 bytes."""
    suffix = len(("/claude-%d" % os.getuid()).encode())
    room = total - suffix - 1  # the leading "/"
    unit = len(filler.encode())
    # an odd remainder is padded with one ASCII byte so multi-byte filler still lands exactly
    return "/" + filler * (room // unit) + "a" * (room % unit)


def test_local_socket_dir_uses_an_override_whose_user_dir_fits(tmp_path, monkeypatch):
    override = _override_with_user_dir_bytes(44)  # the whole per-user path is 44 bytes: honored
    assert len(os.path.join(override, "claude-%d" % os.getuid()).encode()) == 44
    assert _socket_dirs_for(tmp_path, monkeypatch, override) == [
        os.path.realpath(os.path.join(override, "claude-%d" % os.getuid()))]


@pytest.mark.parametrize("filler", [
    pytest.param("a", id="45-bytes"),
    pytest.param("\u00e9", id="45-bytes-in-fewer-characters"),
])
def test_local_socket_dir_falls_back_to_tmp_past_the_limit(tmp_path, monkeypatch, filler):
    # a base well under 44 bytes whose per-user path is 45: the shell ignores it
    override = _override_with_user_dir_bytes(45, filler)
    assert len(os.path.join(override, "claude-%d" % os.getuid()).encode()) == 45
    assert len(override.encode()) < 44
    assert _socket_dirs_for(tmp_path, monkeypatch, override) == [_tmp_claude_uid_dir()]


def test_local_socket_dir_unset_override_is_tmp(tmp_path, monkeypatch):
    assert _socket_dirs_for(tmp_path, monkeypatch, None) == [_tmp_claude_uid_dir()]


# --- the temp base is frozen with the socket grant ---------------------------------------------


def _sandbox_for(tmp_path, monkeypatch, override, block=None):
    wt, _main = _linked_worktree(tmp_path)
    _write_core(wt, _core_text(block or {"localSockets": True}))
    if override is not None:
        monkeypatch.setenv("CLAUDE_CODE_TMPDIR", override)
    sandbox, refusal = ED._resolve_claude_write_sandbox(os.path.realpath(wt), timeout=30)
    assert refusal is None
    return sandbox


@pytest.mark.parametrize("override, expected", [
    pytest.param("/tmp/cc-tmp", "/tmp/cc-tmp", id="honored-override"),
    pytest.param(None, "/tmp", id="unset-pins-tmp"),
    pytest.param("/" + "a" * 60, "/tmp", id="too-long-override-pins-tmp"),
])
def test_resolved_sandbox_journals_the_effective_temp_base(tmp_path, monkeypatch, override,
                                                           expected):
    assert _sandbox_for(tmp_path, monkeypatch, override)["claudeTmpBase"] == expected


def test_sandbox_without_local_sockets_journals_no_temp_base(tmp_path, monkeypatch):
    sandbox = _sandbox_for(tmp_path, monkeypatch, "/tmp/cc-tmp", {"localPorts": True})
    assert "claudeTmpBase" not in sandbox


@pytest.mark.parametrize("recovering", [
    pytest.param(None, id="recovering-env-unset"),
    pytest.param("/tmp/b", id="recovering-env-different"),
])
def test_claude_child_env_pins_the_journaled_temp_base(recovering):
    opened = {"engine": "claude", "claudeWriteSandbox": dict(_SANDBOX, claudeTmpBase="/tmp/a")}
    base = {} if recovering is None else {"CLAUDE_CODE_TMPDIR": recovering}
    env, pins = ED._claude_child_env(opened, base=base)
    assert env["CLAUDE_CODE_TMPDIR"] == "/tmp/a"
    assert pins["CLAUDE_CODE_TMPDIR"] == "/tmp/a"


def test_claude_child_env_without_a_journaled_temp_base_leaves_the_environment():
    opened = {"engine": "claude", "claudeWriteSandbox": dict(_SANDBOX)}
    env, pins = ED._claude_child_env(opened, base={"CLAUDE_CODE_TMPDIR": "/tmp/b"})
    assert env["CLAUDE_CODE_TMPDIR"] == "/tmp/b"
    assert "CLAUDE_CODE_TMPDIR" not in pins


@pytest.mark.parametrize("bad", ["rel/base", 7, ""])
def test_journaled_temp_base_must_be_absolute(bad):
    assert EA.claude_write_sandbox_valid(dict(_SANDBOX, claudeTmpBase=bad)) is False
    assert EA.claude_write_sandbox_valid(dict(_SANDBOX, claudeTmpBase="/tmp")) is True


# --- the calibration read ignores ambient Git routing -----------------------------------------


def test_calibration_read_ignores_ambient_git_routing(tmp_path, monkeypatch):
    wt, main = _linked_worktree(tmp_path)
    _write_core(wt, _core_text({"allowedDomains": ["pypi.org"]}))
    other = tmp_path / "other-checkout"
    other.mkdir()
    monkeypatch.setenv("GIT_DIR", os.path.join(main, ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other))
    sandbox, refusal = ED._resolve_claude_write_sandbox(os.path.realpath(wt), timeout=30)
    assert refusal is None
    assert sandbox["access"]["allowedDomains"] == ["pypi.org"]
    # the ambient variables are restored for the caller
    assert os.environ["GIT_DIR"] == os.path.join(main, ".git")
    assert os.environ["GIT_WORK_TREE"] == str(other)


def test_calibration_read_sees_no_git_routing_variables(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)
    seen = {}
    real_read = core_md.read_sandbox_access

    def spy_read(*args, **kwargs):
        seen.update({k: os.environ.get(k) for k in ED._GIT_ROUTING_VARS})
        return real_read(*args, **kwargs)

    monkeypatch.setattr(ED.core_md, "read_sandbox_access", spy_read)
    monkeypatch.setenv("GIT_DIR", "/nonexistent/.git")
    monkeypatch.setenv("GIT_WORK_TREE", "/nonexistent")
    ED._resolve_claude_write_sandbox(os.path.realpath(wt), timeout=30)
    assert seen and set(seen.values()) == {None}


# --- T6, T7: refusals before anything opens (G9, G10) -----------------------------------------


def test_malformed_calibration_refuses_before_open(tmp_path, monkeypatch):
    wt, run_dir, res, fake = _open_with_core(
        tmp_path, monkeypatch, _core_text({"allowedDomains": ["*"]}))
    assert res["detail"] == "engine-config:sandbox-access-malformed"
    assert res["attempts"] == 0
    assert fake.calls == []
    assert _no_run_opened(run_dir)


def test_unreadable_calibration_refuses_before_open(tmp_path, monkeypatch):
    wt, run_dir, res, fake = _open_with_core(tmp_path, monkeypatch, _corrupt_core_text())
    assert res["detail"] == "engine-config:sandbox-access-unreadable"
    assert res["attempts"] == 0
    assert fake.calls == []
    assert _no_run_opened(run_dir)


@pytest.mark.parametrize("block", [
    pytest.param({"localPorts": True}, id="local-ports"),
    pytest.param({"localSockets": True}, id="local-sockets"),
])
def test_local_access_on_unsupported_platform_refuses_before_open(tmp_path, monkeypatch, block):
    monkeypatch.setattr(ED, "_host_platform", lambda: "linux")
    wt, run_dir, res, fake = _open_with_core(tmp_path, monkeypatch, _core_text(block))
    assert res["detail"] == "engine-config:sandbox-access-unsupported-platform"
    assert res["attempts"] == 0
    assert fake.calls == []
    assert _no_run_opened(run_dir)


def test_non_local_access_on_unsupported_platform_still_opens(tmp_path, monkeypatch):
    monkeypatch.setattr(ED, "_host_platform", lambda: "linux")
    wt, run_dir, res, fake = _open_with_core(
        tmp_path, monkeypatch, _core_text({"allowedDomains": ["pypi.org"]}))
    opened, settings = _opened_settings(run_dir, fake)
    _assert_options(opened, settings, domains=["pypi.org"])


def test_extra_write_path_resolving_to_root_refuses_before_open(tmp_path, monkeypatch):
    root_alias = tmp_path / "root-alias"
    root_alias.symlink_to("/")
    wt, run_dir, res, fake = _open_with_core(
        tmp_path, monkeypatch, _core_text({"extraWritePaths": [str(root_alias)]}))
    assert res["detail"] == "engine-config:sandbox-access-malformed"
    assert res["attempts"] == 0
    assert fake.calls == []
    assert _no_run_opened(run_dir)


@pytest.mark.parametrize("spelling", [
    pytest.param("/**", id="root-glob"),
    pytest.param("/*", id="root-star"),
    pytest.param("{cache}/**", id="subtree-glob"),
    pytest.param("{cache}/[ab]", id="bracket-class"),
    pytest.param("{cache}/a?", id="question-mark"),
    pytest.param("{cache}/{{a,b}}", id="brace-alternation"),
])
def test_extra_write_path_glob_refuses_before_open(tmp_path, monkeypatch, spelling):
    path = spelling.format(cache=str(tmp_path / "cache"))
    wt, run_dir, res, fake = _open_with_core(
        tmp_path, monkeypatch, _core_text({"extraWritePaths": [path]}))
    assert res["detail"] == "engine-config:sandbox-access-malformed"
    assert res["attempts"] == 0
    assert fake.calls == []
    assert _no_run_opened(run_dir)


@pytest.mark.parametrize("glob_path", ["/**", "/x/cache/*", "/x/[a]", "/x/a?", "/x/{a,b}"])
def test_access_validity_rejects_a_glob_extra_write_path(glob_path):
    sandbox = dict(_SANDBOX, access=dict(_VALID_ACCESS, extraWritePaths=[glob_path]))
    assert EA.claude_write_sandbox_valid(sandbox) is False
    res = _write_argv(sandbox)
    assert res["reason"] == "sandbox-roots-missing"
    assert res["argv"] == []


def test_absent_core_md_opens_as_all_off(tmp_path, monkeypatch):
    wt, run_dir, res, fake = _open_with_core(tmp_path, monkeypatch, None)
    assert not os.path.exists(os.path.join(wt, core_md.in_repo_core_rel_path()))
    assert not str(res.get("detail") or "").startswith("engine-config:")
    opened, settings = _opened_settings(run_dir, fake)
    assert opened["claudeWriteSandbox"]["access"] == _ALL_OFF_ACCESS
    _assert_options(opened, settings)


def test_read_raising_is_treated_as_unreadable(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)

    def boom(*a, **k):
        raise RuntimeError("read blew up")

    monkeypatch.setattr(ED.core_md, "read_sandbox_access", boom)
    assert ED._resolve_claude_write_sandbox(
        os.path.realpath(wt), timeout=30) == (None, "sandbox-access-unreadable")


def test_no_getuid_with_local_sockets_is_unreadable(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)
    _write_core(wt, _core_text({"localSockets": True}))
    monkeypatch.delattr(os, "getuid")
    assert ED._resolve_claude_write_sandbox(
        os.path.realpath(wt), timeout=30) == (None, "sandbox-access-unreadable")


# --- T8: a continuation uses the journal, never core.md (G11) ---------------------------------


def test_continuation_uses_journaled_access_not_core_md(tmp_path, monkeypatch):
    calls = []
    real_read = core_md.read_sandbox_access

    def spy_read(*args, **kwargs):
        calls.append(args)
        return real_read(*args, **kwargs)

    monkeypatch.setattr(ED.core_md, "read_sandbox_access", spy_read)
    # max_wait=0 leaves the run open and unspawned, so the second dispatch is the one that spawns
    wt, run_dir, first, fake = _open_with_core(
        tmp_path, monkeypatch, _core_text({"localPorts": True}), max_wait=0)
    assert len(calls) == 1
    assert fake.calls == []
    assert not any(r.get("kind") == "run-folded" for r in ED._journal_read(run_dir)[0])
    opened = _write_opened_record(run_dir)
    assert _settings_of(opened["argv"])["sandbox"]["network"]["allowLocalBinding"] is True
    # the calibration changes after open; a continuation must not notice
    _write_core(wt, _core_text({"localPorts": False, "allowedDomains": ["example.org"]}))
    resumed = _ClaudeStdoutWriteFakeRunner([_claude_write_runner()])
    _dispatch_write(tmp_path, resumed, cwd=wt, run_dir=run_dir, seat=_implementer_claude_seat())
    assert len(calls) == 1, "a continuation re-read the sandboxAccess calibration"
    assert len(resumed.calls) == 1
    settings = _settings_of(resumed.calls[0]["argv"])
    assert settings["sandbox"]["network"]["allowLocalBinding"] is True
    assert settings["sandbox"]["network"]["allowedDomains"] == []
    assert settings["env"]["UV_OFFLINE"] == "1"
    assert resumed.calls[0]["argv"] == opened["argv"]
    assert _write_opened_record(run_dir)["claudeWriteSandbox"]["access"] == {
        "allowedDomains": [], "localPorts": True, "localSocketDirs": [], "extraWritePaths": [],
    }


# --- T9: the journaled access is validated (G17, E5, E6) --------------------------------------

_VALID_ACCESS = {
    "allowedDomains": ["pypi.org"], "localPorts": True,
    "localSocketDirs": ["/tmp/claude-501"], "extraWritePaths": ["/x/cache"],
}


def test_access_validity_accepts_absent_none_and_wellformed():
    assert EA.claude_write_sandbox_valid(dict(_SANDBOX)) is True
    assert EA.claude_write_sandbox_valid(dict(_SANDBOX, access=None)) is True
    assert EA.claude_write_sandbox_valid(dict(_SANDBOX, access=dict(_ALL_OFF_ACCESS))) is True
    assert EA.claude_write_sandbox_valid(dict(_SANDBOX, access=dict(_VALID_ACCESS))) is True


@pytest.mark.parametrize("bad", [
    pytest.param("not-a-dict", id="not-a-dict"),
    pytest.param(dict(_VALID_ACCESS, extra="x"), id="unknown-key"),
    pytest.param({k: v for k, v in _VALID_ACCESS.items() if k != "localPorts"}, id="missing-key"),
    pytest.param(dict(_VALID_ACCESS, extraWritePaths=["rel/path"]), id="relative-extra-path"),
    pytest.param(dict(_VALID_ACCESS, localPorts=1), id="ports-int"),
    pytest.param(dict(_VALID_ACCESS, localPorts="true"), id="ports-str"),
    pytest.param(dict(_VALID_ACCESS, localSocketDirs="/tmp/x"), id="socket-dirs-not-list"),
    pytest.param(dict(_VALID_ACCESS, localSocketDirs=["rel"]), id="socket-dir-relative"),
    pytest.param(dict(_VALID_ACCESS, allowedDomains="pypi.org"), id="domains-not-list"),
    pytest.param(dict(_VALID_ACCESS, allowedDomains=[""]), id="domain-empty"),
    pytest.param(dict(_VALID_ACCESS, allowedDomains=[7]), id="domain-not-str"),
])
def test_access_validity_rejects_malformed_and_refuses_roots_missing(bad):
    sandbox = dict(_SANDBOX, access=bad)
    assert EA.claude_write_sandbox_valid(sandbox) is False
    res = _write_argv(sandbox)
    assert res["reason"] == "sandbox-roots-missing"
    assert res["argv"] == []


# --- T10: deny wins (G18) ---------------------------------------------------------------------


def test_deny_write_is_never_filtered_by_extra_write_paths(tmp_path, monkeypatch):
    def core_for(wt, main):
        hooks = os.path.join(os.path.realpath(main), ".git", "hooks")
        return _core_text({"extraWritePaths": [hooks]})

    wt, run_dir, _res, fake = _open_with_core(tmp_path, monkeypatch, core_for)
    opened, settings = _opened_settings(run_dir, fake)
    main = str(tmp_path / "main")
    hooks = os.path.join(os.path.realpath(main), ".git", "hooks")
    deny = settings["sandbox"]["filesystem"]["denyWrite"]
    assert hooks in deny
    assert deny == opened["claudeWriteSandbox"]["denyWrite"]
    assert hooks in settings["sandbox"]["filesystem"]["allowWrite"]


# --- T11: refusal tokens ----------------------------------------------------------------------


def test_refusal_tokens_registered():
    assert "sandbox-access-malformed" in EA.BUILD_ARGV_REFUSAL_TOKENS
    assert "sandbox-access-unreadable" in EA.BUILD_ARGV_REFUSAL_TOKENS
    assert "sandbox-access-unsupported-platform" in EA.BUILD_ARGV_REFUSAL_TOKENS
