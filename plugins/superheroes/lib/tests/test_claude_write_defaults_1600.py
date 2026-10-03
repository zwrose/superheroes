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
import hashlib
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


def _lease(wt):
    return os.path.realpath(ED._worktree_lease_path(os.path.realpath(wt)))


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


def test_local_ports_alone_emits_allow_local_binding_when_binding_is_false():
    # axis: mapping — access.localPorts drives allowLocalBinding independently of localBinding
    sandbox = dict(_SANDBOX, localBinding=False, access=dict(_ALL_OFF_ACCESS, localPorts=True))
    assert _settings(sandbox)["sandbox"]["network"]["allowLocalBinding"] is True


def test_local_ports_alone_emits_allow_local_binding_when_binding_key_is_absent():
    # a pre-#1600 journal: localPorts True and no localBinding key
    sandbox = dict(_SANDBOX, access=dict(_ALL_OFF_ACCESS, localPorts=True))
    assert "localBinding" not in sandbox
    assert _settings(sandbox)["sandbox"]["network"]["allowLocalBinding"] is True


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


def test_open_denies_the_run_dir_and_the_journal_root(tmp_path, monkeypatch):
    # axis: deny — the /tmp allow must not reach the supervisor journal, so deny wins on every host
    monkeypatch.setattr(ED, "_host_platform", lambda: "linux")
    wt, run_dir, _res, fake = _open_with_core(tmp_path, monkeypatch, _core_text())
    opened = _write_opened_record(run_dir)
    journaled = opened["claudeWriteSandbox"]
    journal_root = os.path.realpath(str(tmp_path / "dispatch-journal-root"))
    assert journaled["denyWrite"][6:] == [os.path.realpath(run_dir), journal_root, _lease(wt)]
    deny = _settings_of(opened["argv"])["sandbox"]["filesystem"]["denyWrite"]
    assert deny == journaled["denyWrite"]
    assert _settings_of(fake.calls[0]["argv"]) == _settings_of(opened["argv"])


def test_open_denies_the_default_temp_journal_root(tmp_path, monkeypatch):
    # the journal root the runner picks with no pointer and no env: tempfile.gettempdir()/name
    monkeypatch.delenv(ED.JOURNAL_ROOT_ENV)
    monkeypatch.setattr(ED, "_host_platform", lambda: "linux")
    wt, run_dir, _res, _fake = _open_with_core(tmp_path, monkeypatch, _core_text())
    journaled = _write_opened_record(run_dir)["claudeWriteSandbox"]
    default_root = os.path.realpath(
        os.path.join(str(tmp_path / "temp-base"), ED.JOURNAL_ROOT_NAME))
    assert journaled["denyWrite"][6:] == [os.path.realpath(run_dir), default_root, _lease(wt)]


def test_open_denies_the_pointer_journal_root(tmp_path, monkeypatch):
    pointed = str(tmp_path / "pointed-root")
    os.makedirs(pointed)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    with open(os.path.join(run_dir, "journal-root.txt"), "w", encoding="utf-8") as fh:
        fh.write(pointed)
    monkeypatch.setattr(ED, "_host_platform", lambda: "linux")
    wt, _main = S1554._linked_worktree(tmp_path)
    sandbox, refusal = ED._resolve_claude_write_sandbox(
        os.path.realpath(wt), timeout=30, run_dir=os.path.realpath(run_dir))
    assert refusal is None
    assert sandbox["denyWrite"][6:] == [
        os.path.realpath(run_dir), os.path.realpath(pointed), _lease(wt)]


def test_open_denies_the_worktree_lease(tmp_path, monkeypatch):
    # axis: deny — the lease is a file in the temp dir; the /tmp allow must not let the engine
    # delete it and so defeat the single-writer guard
    monkeypatch.setattr(ED, "_host_platform", lambda: "linux")
    wt, run_dir, _res, _fake = _open_with_core(tmp_path, monkeypatch, _core_text())
    journaled = _write_opened_record(run_dir)["claudeWriteSandbox"]
    digest = hashlib.sha256(os.path.realpath(wt).encode("utf-8")).hexdigest()
    lease = os.path.realpath(
        os.path.join(str(tmp_path / "temp-base"), "superheroes-worktree-lease-" + digest))
    assert lease in journaled["denyWrite"]


@pytest.mark.parametrize("name", ["journal[1]", "journal*", "journal{a,b}", "journal?"])
def test_open_refuses_a_glob_bearing_journal_root(tmp_path, monkeypatch, name):
    # axis: refusal — a glob spelling in a deny path would match a sibling, not the literal dir
    root = str(tmp_path / name)
    os.makedirs(root)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    monkeypatch.setenv(ED.JOURNAL_ROOT_ENV, root)
    wt, _main = S1554._linked_worktree(tmp_path)
    sandbox, refusal = ED._resolve_claude_write_sandbox(
        os.path.realpath(wt), timeout=30, run_dir=os.path.realpath(run_dir))
    assert sandbox is None
    assert refusal == "sandbox-roots-unresolvable"


def test_open_refuses_a_glob_bearing_run_dir(tmp_path, monkeypatch):
    run_dir = str(tmp_path / "run[1]")
    os.makedirs(run_dir)
    monkeypatch.setenv(ED.JOURNAL_ROOT_ENV, str(tmp_path / "root"))
    wt, _main = S1554._linked_worktree(tmp_path)
    sandbox, refusal = ED._resolve_claude_write_sandbox(
        os.path.realpath(wt), timeout=30, run_dir=os.path.realpath(run_dir))
    assert sandbox is None
    assert refusal == "sandbox-roots-unresolvable"


def test_deny_entries_are_deduplicated(tmp_path, monkeypatch):
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    monkeypatch.setenv(ED.JOURNAL_ROOT_ENV, run_dir)
    wt, _main = S1554._linked_worktree(tmp_path)
    sandbox, refusal = ED._resolve_claude_write_sandbox(
        os.path.realpath(wt), timeout=30, run_dir=os.path.realpath(run_dir))
    assert refusal is None
    assert sandbox["denyWrite"][6:] == [os.path.realpath(run_dir), _lease(wt)]


def test_continuation_reuses_the_journaled_deny_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(ED, "_host_platform", lambda: "linux")
    wt, run_dir, _first, fake = _open_with_core(
        tmp_path, monkeypatch, _core_text(), max_wait=0)
    assert fake.calls == []
    opened = _write_opened_record(run_dir)
    journaled_deny = list(opened["claudeWriteSandbox"]["denyWrite"])
    assert journaled_deny[6:] == [
        os.path.realpath(run_dir), os.path.realpath(str(tmp_path / "dispatch-journal-root")),
        _lease(wt)]
    # the ambient journal root changes after open; a continuation must not re-derive the deny list
    monkeypatch.setenv(ED.JOURNAL_ROOT_ENV, str(tmp_path / "another-root"))
    resumed = _ClaudeStdoutWriteFakeRunner([_claude_write_runner()])
    _dispatch_write(tmp_path, resumed, cwd=wt, run_dir=run_dir, seat=_implementer_claude_seat())
    assert len(resumed.calls) == 1
    settings = _settings_of(resumed.calls[0]["argv"])
    assert settings["sandbox"]["filesystem"]["denyWrite"] == journaled_deny
    assert resumed.calls[0]["argv"] == opened["argv"]


def test_a_tmp_root_resolving_to_slash_is_not_journaled(tmp_path, monkeypatch):
    real_realpath = os.path.realpath
    monkeypatch.setattr(
        ED.os.path, "realpath",
        lambda p, *a, **k: "/" if p == "/tmp" else real_realpath(p, *a, **k))
    wt, _main = S1554._linked_worktree(tmp_path)
    sandbox, refusal = ED._resolve_claude_write_sandbox(real_realpath(wt), timeout=30)
    assert refusal is None
    assert sandbox["tmpWriteRoots"] == []


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
