import importlib.util
import json
import os

import band_lib
import enforcer

_PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_REPO = os.path.abspath(os.path.join(_PLUGIN, "..", ".."))
_ESC = os.path.join(_REPO, "plugins", "the-architect", "lib", "escalation.py")
_ENFORCER = os.path.join(_PLUGIN, "lib", "enforcer.py")
_HOOKS = os.path.join(_PLUGIN, "hooks", "hooks.json")


def _esc_mod():
    spec = importlib.util.spec_from_file_location("escalation", _ESC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_enforcer_is_in_safety_machinery():
    assert "enforcer.py" in _esc_mod().SAFETY_MACHINERY


def test_hooks_json_registers_both_matchers_and_is_fail_closed():
    cfg = json.load(open(_HOOKS))
    matchers = {h["matcher"] for h in cfg["hooks"]["PreToolUse"]}
    assert matchers == {"Bash", "Edit|Write|MultiEdit"}
    for h in cfg["hooks"]["PreToolUse"]:
        cmd = h["hooks"][0]["command"]
        assert "enforcer.py" in cmd and "hook" in cmd
        # process-level fail-closed: a non-zero exit must fall back to a deny
        assert "||" in cmd and '"permissionDecision":"deny"' in cmd.replace("\\", "")


def test_enforcer_refuses_edit_to_itself(monkeypatch):
    # the enforcer file, under the workhorse plugin root, is now safety-machinery
    monkeypatch.setattr(band_lib, "resolve_target",
                        lambda *a, **k: _ESC)
    assert enforcer.classify_path(_ENFORCER)[0] == "deny"


def test_selfcheck_armed_now_that_hooks_exist(capsys, monkeypatch):
    # In the installed/dogfood reality escalation.py resolves; simulate that so the
    # new escalation-resolution leg is exercised (pytest's marketplace layout differs).
    monkeypatch.setattr(band_lib, "resolve_target", lambda *a, **k: _ESC)
    rc = enforcer.selfcheck()
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["armed"] is True
    assert out["hook_config"] is True and out["escalation_resolved"] is True


def test_selfcheck_refuses_when_escalation_unresolvable(capsys, monkeypatch):
    # A broken install where the Edit guard can't resolve escalation would deny ALL
    # edits (fail-closed) and wedge ① Build with misdirecting per-edit denials. The
    # startup self-check must catch it HERE: armed:false, escalation_resolved:false.
    monkeypatch.setattr(band_lib, "resolve_target", lambda *a, **k: None)
    rc = enforcer.selfcheck()
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and out["armed"] is False and out["escalation_resolved"] is False


def test_bash_write_guard_covers_every_safety_machinery_basename():
    # The Bash-write deny list must cover everything the Edit/Write guard protects,
    # so no safety file is mutable via `sed -i`/redirection just because it's edited
    # through Bash instead of the Edit tool.
    esc_set = set(_esc_mod().SAFETY_MACHINERY)
    assert esc_set.issubset(set(enforcer._SAFETY_BASENAMES)), \
        esc_set - set(enforcer._SAFETY_BASENAMES)
