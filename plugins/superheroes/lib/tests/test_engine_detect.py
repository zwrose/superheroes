import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    spec = importlib.util.spec_from_file_location(
        "engine_detect", os.path.join(_HERE, "..", "engine_detect.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ED = _load()


class _Proc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _fake_run(script):
    """script: dict mapping the FIRST argv token -> _Proc (or an Exception to raise)."""
    def run(args, capture_output=True, text=True, timeout=10, cwd=None):
        key = args[0]
        val = script.get(key, _Proc(returncode=1))
        if isinstance(val, Exception):
            raise val
        return val
    return run


def test_probe_both_installed_and_authed(monkeypatch):
    monkeypatch.setattr(ED.shutil, "which", lambda name: "/usr/bin/" + name)
    run = _fake_run({"codex": _Proc(0, "logged in"), "cursor-agent": _Proc(0, "user@x")})
    p = ED.probe(".", run=run)
    assert p["codex"]["installed"] is True and p["codex"]["authed"] is True
    assert p["cursor"]["installed"] is True and p["cursor"]["authed"] is True


def test_probe_codex_not_installed(monkeypatch):
    monkeypatch.setattr(ED.shutil, "which", lambda name: None if name == "codex" else "/usr/bin/" + name)
    run = _fake_run({"cursor-agent": _Proc(0, "user@x")})
    p = ED.probe(".", run=run)
    assert p["codex"]["installed"] is False and p["codex"]["authed"] is False
    assert p["cursor"]["installed"] is True and p["cursor"]["authed"] is True


def test_probe_cursor_installed_not_authed(monkeypatch):
    monkeypatch.setattr(ED.shutil, "which", lambda name: "/usr/bin/" + name)
    run = _fake_run({"codex": _Proc(0, "ok"), "cursor-agent": _Proc(1, "", "not signed in")})
    p = ED.probe(".", run=run)
    assert p["cursor"]["installed"] is True and p["cursor"]["authed"] is False


def test_probe_never_raises_on_run_exception(monkeypatch):
    monkeypatch.setattr(ED.shutil, "which", lambda name: "/usr/bin/" + name)
    run = _fake_run({"codex": RuntimeError("boom"), "cursor-agent": _Proc(0, "ok")})
    p = ED.probe(".", run=run)
    assert p["codex"]["authed"] is False and p["codex"]["error"]


def test_decide_ready():
    probe = {"codex": {"installed": True, "authed": True, "error": None},
             "cursor": {"installed": False, "authed": False, "error": None}}
    ok, cause, rem = ED.decide(probe, "codex")
    assert ok is True and cause is None and rem is None


def test_decide_not_installed_gives_remediation():
    probe = {"codex": {"installed": False, "authed": False, "error": None}, "cursor": {}}
    ok, cause, rem = ED.decide(probe, "codex")
    assert ok is False and cause == "not_installed" and rem


def test_decide_not_authed_gives_remediation():
    probe = {"codex": {"installed": True, "authed": False, "error": None}, "cursor": {}}
    ok, cause, rem = ED.decide(probe, "codex")
    assert ok is False and cause == "not_authenticated" and rem


def test_decide_unknown_engine_is_indeterminate():
    ok, cause, rem = ED.decide({"codex": {}, "cursor": {}}, "bogus")
    assert ok is False and cause == "indeterminate"


def test_decide_error_set_is_indeterminate():
    # M2: an otherwise-installed engine whose probe recorded an `error` (timeout/OSError) is
    # indeterminate (fail-closed), NOT reported ready.
    probe = {"codex": {"installed": True, "authed": True, "error": "TimeoutExpired: x"},
             "cursor": {}}
    ok, cause, rem = ED.decide(probe, "codex")
    assert ok is False and cause == "indeterminate" and rem


def test_message_and_main(monkeypatch, capsys):
    monkeypatch.setattr(ED.shutil, "which", lambda name: "/usr/bin/" + name)
    run = _fake_run({"codex": _Proc(0, "ok"), "cursor-agent": _Proc(0, "ok")})
    rc = ED.main(["--engine", "codex", "--root", "."], run=run)
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["ok"] is True and out["engine"] == "codex"


def test_main_no_engine_prints_both_engines_matrix(monkeypatch, capsys):
    # I1 / FR-11: bare `engine_detect.py` (no --engine) prints the readiness matrix configure shows.
    monkeypatch.setattr(ED.shutil, "which",
                        lambda name: None if name == "cursor-agent" else "/usr/bin/" + name)
    run = _fake_run({"codex": _Proc(0, "ok")})
    rc = ED.main(["--root", "."], run=run)
    out = json.loads(capsys.readouterr().out)
    assert set(out.keys()) == {"codex", "cursor"}
    assert out["codex"]["ok"] is True
    assert out["cursor"]["ok"] is False and out["cursor"]["cause"] == "not_installed"
    assert out["cursor"]["remediation"]           # every not-ready engine carries remediation
    assert rc == 0                                 # at least one engine ready -> exit 0
