"""#1600: the claude write channel grants node toolchains, `ps`, localhost binding and /tmp writes.

Invariant: the settings JSON is a pure function of the journaled `claudeWriteSandbox` dict. A run
opened after this change journals two defaults resolved once at open (`tmpWriteRoots`,
`localBinding`); a journal without those keys emits neither default.

Every rule, key and path is spelled out as a string literal on purpose: a test that reaches them
through the module constant stays green under any value (rubric/bite-proof.md).

Detector axes (bite-proof):
- test_allow_list_is_the_eleven_literal_rules — rule list: exactly the eleven rules, in order
- test_tmp_defaults_reach_allow_write_in_order — mapping: tmpWriteRoots reach allowWrite in place
- test_local_binding_* — mapping: localBinding alone drives allowLocalBinding
- test_pre_change_journal_emits_no_defaults — preservation: no key, no default
- test_open_journals_* — journal: the open resolves and freezes both defaults
- test_continuation_reuses_journaled_defaults — journal reuse: a continuation never re-derives
- test_validity_* — journal validity: a malformed default refuses
- test_process_listing_refusal_unchanged — refusal: `ps` is allowed by rule, still refused
"""
import json
import os

import pytest

# The 1554/1562 suites' harness (and, through them, the write-dispatch suite's autouse fixture).
import test_claude_write_sandbox_1554 as S1554
from test_claude_write_sandbox_1554 import (  # noqa: F401
    ED,
    EA,
    _ClaudeStdoutWriteFakeRunner,
    _SANDBOX,
    _claude_write_runner,
    _dispatch_write,
    _implementer_claude_seat,
    _open_claude_write,
    _pin_temp_base_to_tmp_path,
    _settings_of,
    _write_argv,
    _write_opened_record,
)
from test_sandbox_access_dispatch_1562 import (  # noqa: F401
    _ALL_OFF_ACCESS,
    _core_text,
    _open_with_core,
    _pin_store_root,
)

def _settings(sandbox):
    return json.loads(EA.claude_write_sandbox_settings(sandbox))


def test_allow_list_is_the_eleven_literal_rules():
    # axis: rule list — exactly the eleven rules, in order, with the deny list unchanged
    assert _settings(_SANDBOX)["permissions"] == {
        "allow": [
            "Bash(python:*)", "Bash(python3:*)", "Bash(pytest:*)",
            "Bash(scripts/pinned-python:*)", "Bash(echo:*)",
            "Bash(npm:*)", "Bash(npx:*)", "Bash(node:*)", "Bash(pnpm:*)",
            "Bash(yarn:*)", "Bash(ps:*)",
        ],
        "deny": ["WebFetch", "WebSearch"],
    }


def test_tmp_defaults_reach_allow_write_in_order():
    # axis: mapping — tmpWriteRoots land in allowWrite after the uv cache and before extraWritePaths
    sandbox = dict(
        _SANDBOX,
        uvCacheDir="/cache/uv",
        tmpWriteRoots=["/tmp", "/private/tmp"],
        access={
            "allowedDomains": [], "localPorts": False, "localSocketDirs": [],
            "extraWritePaths": ["/x/extra"],
        },
    )
    fs = _settings(sandbox)["sandbox"]["filesystem"]
    assert fs["allowWrite"] == [
        "/work/wt", "/work/main/.git/worktrees/wt", "/work/main/.git",
        "/cache/uv", "/tmp", "/private/tmp", "/x/extra",
    ]
    assert fs["denyWrite"] == [
        "/work/main/.git/hooks", "/work/main/.git/config",
        "/work/main/.git/worktrees/wt/config.worktree",
    ]


def test_local_binding_default_emits_allow_local_binding():
    sandbox = dict(_SANDBOX, localBinding=True, access=dict(_ALL_OFF_ACCESS))
    assert _settings(sandbox)["sandbox"]["network"] == {
        "allowedDomains": [], "strictAllowlist": True, "allowLocalBinding": True,
    }


def test_local_binding_false_emits_no_key():
    sandbox = dict(_SANDBOX, localBinding=False, access=dict(_ALL_OFF_ACCESS))
    assert _settings(sandbox)["sandbox"]["network"] == {
        "allowedDomains": [], "strictAllowlist": True,
    }


def test_pre_change_journal_emits_no_defaults():
    assert "tmpWriteRoots" not in _SANDBOX and "localBinding" not in _SANDBOX
    obj = _settings(_SANDBOX)
    assert obj["sandbox"]["filesystem"]["allowWrite"] == [
        "/work/wt", "/work/main/.git/worktrees/wt", "/work/main/.git",
    ]
    assert "/tmp" not in obj["sandbox"]["filesystem"]["allowWrite"]
    assert "allowLocalBinding" not in obj["sandbox"]["network"]


def test_open_journals_the_defaults_on_macos(tmp_path, monkeypatch):
    # axis: journal — the open resolves both defaults and the settings carry them
    monkeypatch.setattr(ED, "_host_platform", lambda: "darwin")
    wt, run_dir, _res, fake = _open_with_core(tmp_path, monkeypatch, _core_text())
    opened = _write_opened_record(run_dir)
    journaled = opened["claudeWriteSandbox"]
    expected = ["/tmp"] if os.path.realpath("/tmp") == "/tmp" else ["/tmp", os.path.realpath("/tmp")]
    assert journaled["tmpWriteRoots"] == expected
    assert journaled["localBinding"] is True
    settings = _settings_of(opened["argv"])
    assert _settings_of(fake.calls[0]["argv"]) == settings
    allow_write = settings["sandbox"]["filesystem"]["allowWrite"]
    assert allow_write == journaled["writeRoots"] + expected
    assert settings["sandbox"]["network"]["allowLocalBinding"] is True


def test_open_journals_no_local_binding_off_macos(tmp_path, monkeypatch):
    monkeypatch.setattr(ED, "_host_platform", lambda: "linux")
    wt, run_dir, _res, fake = _open_with_core(tmp_path, monkeypatch, _core_text())
    opened = _write_opened_record(run_dir)
    journaled = opened["claudeWriteSandbox"]
    expected = ["/tmp"] if os.path.realpath("/tmp") == "/tmp" else ["/tmp", os.path.realpath("/tmp")]
    assert journaled["tmpWriteRoots"] == expected
    assert journaled["localBinding"] is False
    settings = _settings_of(opened["argv"])
    assert _settings_of(fake.calls[0]["argv"]) == settings
    assert "allowLocalBinding" not in settings["sandbox"]["network"]
    assert settings["sandbox"]["filesystem"]["allowWrite"] == journaled["writeRoots"] + expected


def test_continuation_reuses_journaled_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(ED, "_host_platform", lambda: "linux")
    real_resolve = ED._resolve_claude_write_sandbox

    def resolve_with_journaled_defaults(*args, **kwargs):
        sandbox, refusal = real_resolve(*args, **kwargs)
        sandbox["tmpWriteRoots"] = ["/journaled/tmp"]
        sandbox["localBinding"] = False
        return sandbox, refusal

    monkeypatch.setattr(ED, "_resolve_claude_write_sandbox", resolve_with_journaled_defaults)
    # max_wait=0 leaves the run open and unspawned, so the second dispatch is the one that spawns
    wt, run_dir, _first, fake = _open_with_core(
        tmp_path, monkeypatch, _core_text(), max_wait=0)
    assert fake.calls == []
    opened = _write_opened_record(run_dir)
    assert opened["claudeWriteSandbox"]["tmpWriteRoots"] == ["/journaled/tmp"]
    assert opened["claudeWriteSandbox"]["localBinding"] is False
    # the host changes after open; a continuation must not re-derive either default
    monkeypatch.setattr(ED, "_host_platform", lambda: "darwin")
    resumed = _ClaudeStdoutWriteFakeRunner([_claude_write_runner()])
    _dispatch_write(tmp_path, resumed, cwd=wt, run_dir=run_dir, seat=_implementer_claude_seat())
    assert len(resumed.calls) == 1
    settings = _settings_of(resumed.calls[0]["argv"])
    assert "/journaled/tmp" in settings["sandbox"]["filesystem"]["allowWrite"]
    assert "/tmp" not in settings["sandbox"]["filesystem"]["allowWrite"]
    assert "allowLocalBinding" not in settings["sandbox"]["network"]
    assert resumed.calls[0]["argv"] == opened["argv"]


@pytest.mark.parametrize("bad", [
    pytest.param({"tmpWriteRoots": "/tmp"}, id="tmp-not-a-list"),
    pytest.param({"tmpWriteRoots": ["tmp"]}, id="tmp-relative"),
    pytest.param({"tmpWriteRoots": ["/tmp/**"]}, id="tmp-glob"),
    pytest.param({"localBinding": 1}, id="binding-int"),
    pytest.param({"localBinding": "true"}, id="binding-str"),
    pytest.param({"localBinding": None}, id="binding-none"),
])
def test_validity_rejects_malformed_defaults(bad):
    sandbox = dict(_SANDBOX, **bad)
    assert EA.claude_write_sandbox_valid(sandbox) is False
    res = _write_argv(sandbox)
    assert res["reason"] == "sandbox-roots-missing"
    assert res["argv"] == []


def test_validity_accepts_absent_and_wellformed_defaults():
    assert EA.claude_write_sandbox_valid(dict(_SANDBOX)) is True
    assert EA.claude_write_sandbox_valid(dict(_SANDBOX, tmpWriteRoots=[])) is True
    assert EA.claude_write_sandbox_valid(
        dict(_SANDBOX, tmpWriteRoots=["/tmp", "/private/tmp"])) is True
    assert EA.claude_write_sandbox_valid(dict(_SANDBOX, localBinding=True)) is True
    assert EA.claude_write_sandbox_valid(dict(_SANDBOX, localBinding=False)) is True
    both = dict(_SANDBOX, tmpWriteRoots=["/tmp"], localBinding=True)
    res = _write_argv(both)
    assert res["reason"] is None
    assert res["argv"]


def test_process_listing_refusal_unchanged():
    res = _write_argv(dict(_SANDBOX, tmpWriteRoots=["/tmp"], localBinding=True),
                      requiresProcessListing=True)
    assert res["reason"] == "sandbox-process-listing-unavailable"
    assert res["argv"] == []
