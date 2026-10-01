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
"""
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


def _open_with_core(tmp_path, monkeypatch, core):
    """Open a claude write through the 1554 harness with ``core`` written into the worktree first.

    ``core`` is core.md text, ``None`` (no core.md), or a callable ``(wt, main) -> text``."""
    real_linked_worktree = S1554._linked_worktree

    def linked_worktree_with_core(tp):
        wt, main = real_linked_worktree(tp)
        text = core(wt, main) if callable(core) else core
        if text is not None:
            _write_core(wt, text)
        return wt, main

    monkeypatch.setattr(S1554, "_linked_worktree", linked_worktree_with_core)
    return _open_claude_write(tmp_path, monkeypatch)


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
    cc_tmp = os.path.join(os.path.realpath(str(tmp_path)), "cc-tmp")
    monkeypatch.setenv("CLAUDE_CODE_TMPDIR", cc_tmp)
    wt, run_dir, _res, fake = _open_with_core(
        tmp_path, monkeypatch, _core_text({"localSockets": True}))
    opened, settings = _opened_settings(run_dir, fake)
    expected = os.path.join(cc_tmp, "claude-%d" % os.getuid())
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
    wt, run_dir, first, fake = _open_with_core(
        tmp_path, monkeypatch, _core_text({"localPorts": True}))
    _opened_settings(run_dir, fake)
    assert _settings_of(first["argv"])["sandbox"]["network"]["allowLocalBinding"] is True
    # the calibration changes after open; a continuation must not notice
    _write_core(wt, _core_text({"localPorts": False, "allowedDomains": ["example.org"]}))
    second = _dispatch_write(tmp_path, _ClaudeStdoutWriteFakeRunner([_claude_write_runner()]),
                             cwd=wt, run_dir=run_dir, seat=_implementer_claude_seat())
    settings = _settings_of(second["argv"])
    assert settings["sandbox"]["network"]["allowLocalBinding"] is True
    assert settings["sandbox"]["network"]["allowedDomains"] == []
    assert settings["env"]["UV_OFFLINE"] == "1"
    assert second["argv"] == first["argv"]
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
