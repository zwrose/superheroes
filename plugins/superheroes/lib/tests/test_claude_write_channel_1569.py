"""#1569: the claude write channel runs every sandbox-confined Bash command.

Invariants: (A) the settings allow Bash if and only if the journaled sandbox froze
`managedPolicyPresent` as the boolean False; (B) that bool is computed once at open, and an
unreadable managed-policy location counts as present."""
import json
import os
import sys

import pytest

# The write-dispatch suite's helpers and its autouse tmp-base/journal-root/uv-absent fixture.
from test_engine_dispatch_write import (  # noqa: F401
    ED,
    EA,
    FakeRunner,
    _ClaudeStdoutWriteFakeRunner,
    _build_ok_stdout,
    _claude_write_runner,
    _dispatch_write,
    _ensure_claude_config_dir,
    _implementer_claude_seat,
    _linked_worktree,
    _pin_temp_base_to_tmp_path,
)
from test_claude_write_sandbox_1554 import (
    _SANDBOX,
    _assert_sandboxed_shape,
    _claude_seat,
    _settings_of,
)


def _with_policy(value):
    return dict(_SANDBOX, managedPolicyPresent=value)


# --- Invariant A: the settings allow ---------------------------------------------------------


# axis: a False frozen flag emits exactly the Bash allow beside the unchanged deny list.
def test_settings_allow_bash_when_managed_policy_absent():
    obj = json.loads(EA.claude_write_sandbox_settings(_with_policy(False)))
    assert obj["permissions"] == {"allow": ["Bash"], "deny": ["WebFetch", "WebSearch"]}


# axis: an absent, True, or non-bool flag fails closed to no allow.
@pytest.mark.parametrize("sandbox", [
    pytest.param(dict(_SANDBOX), id="absent"),
    pytest.param(_with_policy(True), id="true"),
    pytest.param(_with_policy(None), id="none"),
    pytest.param(_with_policy(0), id="zero"),
    pytest.param(_with_policy("false"), id="string-false"),
])
def test_settings_no_allow_unless_literal_false(sandbox):
    obj = json.loads(EA.claude_write_sandbox_settings(sandbox))
    assert "allow" not in obj["permissions"]
    assert obj["permissions"] == {"deny": ["WebFetch", "WebSearch"]}


# axis: the allow changes nothing about confinement: the sandbox block is identical.
def test_settings_sandbox_block_unchanged_by_allow():
    absent = json.loads(EA.claude_write_sandbox_settings(dict(_SANDBOX)))
    allowed = json.loads(EA.claude_write_sandbox_settings(_with_policy(False)))
    assert allowed["sandbox"] == absent["sandbox"]
    assert allowed["env"] == absent["env"]
    raw = EA.claude_write_sandbox_settings(_with_policy(False))
    assert raw == json.dumps(json.loads(raw), sort_keys=True, separators=(",", ":"))


# axis: the built argv stays the sandboxed shape and carries the allow.
def test_argv_stays_sandboxed_and_carries_allow():
    res = EA.build_argv_result(
        _claude_seat(), "build", {"claudeWriteSandbox": _with_policy(False)})
    assert res["reason"] is None
    _assert_sandboxed_shape(res["argv"])
    assert _settings_of(res["argv"])["permissions"]["allow"] == ["Bash"]


# --- Invariant B: managed-policy presence ----------------------------------------------------


def _patch_locations(monkeypatch, *pairs):
    monkeypatch.setattr(ED, "_managed_policy_locations", lambda: tuple(pairs))


# axis: absent files and dirs are absent.
def test_presence_all_absent(tmp_path, monkeypatch):
    _patch_locations(monkeypatch, (str(tmp_path / "a.json"), "file"), (str(tmp_path / "a.d"), "dir"))
    assert ED._managed_policy_present() is False


# axis: a present file location is present.
def test_presence_file_present(tmp_path, monkeypatch):
    path = tmp_path / "managed-settings.json"
    path.write_text("{}", encoding="utf-8")
    _patch_locations(monkeypatch, (str(path), "file"))
    assert ED._managed_policy_present() is True


# axis: a dangling symlink at a file location is present (E3).
def test_presence_dangling_symlink_is_present(tmp_path, monkeypatch):
    path = tmp_path / "managed-settings.json"
    os.symlink(str(tmp_path / "nowhere"), str(path))
    _patch_locations(monkeypatch, (str(path), "file"))
    assert ED._managed_policy_present() is True


# axis: a directory at a file location is present (E3).
def test_presence_dir_at_file_location_is_present(tmp_path, monkeypatch):
    path = tmp_path / "managed-settings.json"
    path.mkdir()
    _patch_locations(monkeypatch, (str(path), "file"))
    assert ED._managed_policy_present() is True


# axis: a not-a-directory parent is absent (E1).
def test_presence_not_a_directory_parent_is_absent(tmp_path, monkeypatch):
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    _patch_locations(monkeypatch, (str(blocker / "managed-settings.json"), "file"))
    assert ED._managed_policy_present() is False


# axis: a dir location is absent when missing or empty, present with an entry (E1, E5).
def test_presence_dir_location_states(tmp_path, monkeypatch):
    d = tmp_path / "managed-settings.d"
    _patch_locations(monkeypatch, (str(d), "dir"))
    assert ED._managed_policy_present() is False
    d.mkdir()
    assert ED._managed_policy_present() is False
    (d / "10-policy.json").write_text("{}", encoding="utf-8")
    assert ED._managed_policy_present() is True


# axis: a regular file at a dir location is present (E4).
def test_presence_file_at_dir_location_is_present(tmp_path, monkeypatch):
    path = tmp_path / "managed-settings.d"
    path.write_text("x", encoding="utf-8")
    _patch_locations(monkeypatch, (str(path), "dir"))
    assert ED._managed_policy_present() is True


# axis: an lstat error other than not-found counts as present (E2).
def test_presence_lstat_permission_error_is_present(tmp_path, monkeypatch):
    path = str(tmp_path / "managed-settings.json")
    _patch_locations(monkeypatch, (path, "file"))
    real = os.lstat

    def lstat(p, *a, **k):
        if p == path:
            raise PermissionError(13, "denied")
        return real(p, *a, **k)

    monkeypatch.setattr(ED.os, "lstat", lstat)
    assert ED._managed_policy_present() is True


# axis: a listdir error on an existing dir location counts as present (E5).
def test_presence_listdir_permission_error_is_present(tmp_path, monkeypatch):
    d = tmp_path / "managed-settings.d"
    d.mkdir()
    _patch_locations(monkeypatch, (str(d), "dir"))
    real = os.listdir

    def listdir(p="."):
        if p == str(d):
            raise PermissionError(13, "denied")
        return real(p)

    monkeypatch.setattr(ED.os, "listdir", listdir)
    assert ED._managed_policy_present() is True


# axis: the unpatched locations are the literal platform tuple.
def test_managed_policy_locations_literals():
    if sys.platform == "darwin":
        assert ED._managed_policy_locations() == (
            ("/Library/Application Support/ClaudeCode/managed-settings.json", "file"),
            ("/Library/Application Support/ClaudeCode/managed-settings.d", "dir"),
            ("/Library/Managed Preferences/com.anthropic.claudecode.plist", "file"),
        )
    else:
        assert ED._managed_policy_locations() == (
            ("/etc/claude-code/managed-settings.json", "file"),
            ("/etc/claude-code/managed-settings.d", "dir"),
        )


# axis: the resolver freezes the helper's value into the journaled sandbox dict.
@pytest.mark.parametrize("present", [True, False])
def test_resolver_threads_managed_policy_present(tmp_path, monkeypatch, present):
    monkeypatch.setattr(ED, "_managed_policy_present", lambda: present)
    wt, _main = _linked_worktree(tmp_path)
    sandbox, refusal = ED._resolve_claude_write_sandbox(os.path.realpath(wt), timeout=30)
    assert refusal is None
    assert sandbox["managedPolicyPresent"] is present
