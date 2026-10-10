"""Tests for cloud_pass (#1744 WO-A): the reviewer pass module.

Every token below is built at run time from small parts; no test touches the real home
directory, clipboard, network or reviewer tool.
"""
import base64
import builtins
import importlib.util
import io
import json
import os
import stat
import subprocess
import sys
from types import SimpleNamespace

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_setup  # noqa: E402
import mode_registry  # noqa: E402
import store_core  # noqa: E402


def _load():
    spec = importlib.util.spec_from_file_location(
        "cloud_pass", os.path.join(_HERE, "..", "cloud_pass.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CP = _load()

NOW = 1_800_000_000
EXP = NOW + 10 * 86400
EXP_DATE = "2027-01-25"


def _b64u(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _jwt(exp, tag):
    head = _b64u(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    body = _b64u(json.dumps({"exp": exp, "sub": tag}).encode())
    return ".".join([head, body, _b64u(("sig-" + tag).encode())])


ACCESS = _jwt(EXP, "access")
IDENT = _jwt(EXP, "ident")
RENEWAL = _b64u(b"renewal-fixture-key")
OLD_ACCESS = _jwt(EXP + 86400, "older-access")


def _signin(access=ACCESS, ident=IDENT, refresh=RENEWAL, **extra):
    out = {"auth_mode": "chatgpt", "OPENAI_API_KEY": None,
           "tokens": {"id_token": ident, "access_token": access, "refresh_token": refresh,
                      "account_id": "acct-fixture"},
           "last_refresh": "2026-10-10T12:00:00Z"}
    out.update(extra)
    return out


def _pass_obj(access=ACCESS, ident=IDENT, refresh=""):
    return _signin(access=access, ident=ident, refresh=refresh)


def _encode(obj):
    return base64.b64encode(json.dumps(obj).encode()).decode("ascii")


PASS = _encode(_pass_obj())
RENEWABLE_PASS = _encode(_pass_obj(refresh=RENEWAL))
SECRETS = (PASS, RENEWABLE_PASS, ACCESS, IDENT, RENEWAL)


def _home(tmp_path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return home


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(obj if isinstance(obj, str) else json.dumps(obj), encoding="utf-8")
    return path


def _env(tmp_path, **extra):
    env = {"HOME": str(_home(tmp_path))}
    env.update(extra)
    return env


def _cloud_env(tmp_path, pass_value=PASS, **extra):
    env = _env(tmp_path, **extra)
    env[CP.CLOUD_ENV] = "true"
    if pass_value is not None:
        env[CP.PASS_ENV] = pass_value
    return env


def _separate(tmp_path):
    return _home(tmp_path) / ".codex-cloud" / "auth.json"


def _default(tmp_path):
    return _home(tmp_path) / ".codex" / "auth.json"


def _snapshot(root):
    seen = {}
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            full = os.path.join(dirpath, name)
            seen[full] = open(full, "rb").read() if os.path.isfile(full) else None
    return seen


def _decode(block_line):
    return json.loads(base64.b64decode(block_line.split("=", 1)[1]))


# ---------------------------------------------------------------- make: scenarios


def _make_with(tmp_path, signin, **kw):
    if signin is not None:
        _write(_separate(tmp_path), signin)
    calls = []
    result = CP.make(env=kw.pop("env", None) or _env(tmp_path), clipboard=kw.pop("clipboard", calls.append),
                     now=kw.pop("now", NOW))
    return result, calls


def _scn_make_ok(tmp_path):
    return _make_with(tmp_path, _signin())[0]


def _scn_m1(tmp_path):
    return _make_with(tmp_path, None)[0]


def _scn_m2(tmp_path):
    _write(_separate(tmp_path), _signin())
    os.symlink(_separate(tmp_path).parent, _default(tmp_path).parent)
    return _make_with(tmp_path, None)[0]


def _scn_m3(tmp_path):
    return _make_with(tmp_path, "this is not json")[0]


def _scn_m4(tmp_path):
    bad = _signin()
    del bad["tokens"]
    return _make_with(tmp_path, bad)[0]


def _scn_m5(tmp_path):
    return _make_with(tmp_path, _signin(access="not-a-token"))[0]


def _scn_m6(tmp_path):
    return _make_with(tmp_path, _signin(), now=EXP)[0]


def _scn_m7(tmp_path):
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    _write(_separate(tmp_path), _signin())
    return CP.make(env=_env(tmp_path, PATH=str(empty)), now=NOW)


def _scn_m8(tmp_path):
    def boom(_text):
        raise OSError("clipboard exploded")
    return _make_with(tmp_path, _signin(), clipboard=boom)[0]


# ---------------------------------------------------------------- place: scenarios


def _scn_place_ok(tmp_path):
    return CP.place(env=_cloud_env(tmp_path))


def _scn_p1(tmp_path):
    env = _cloud_env(tmp_path)
    del env[CP.CLOUD_ENV]
    return CP.place(env=env)


def _scn_p2(tmp_path):
    return CP.place(env=_cloud_env(tmp_path, pass_value=None))


def _scn_p3(tmp_path):
    return CP.place(env=_cloud_env(tmp_path, pass_value="%%% not base64 %%%"))


def _scn_p4(tmp_path):
    return CP.place(env=_cloud_env(tmp_path, pass_value=RENEWABLE_PASS))


def _scn_p5(tmp_path):
    return CP.place(env=_cloud_env(tmp_path, pass_value=_encode(_pass_obj(access=""))))


def _scn_p6(tmp_path):
    home = _home(tmp_path)
    (home / ".codex").write_text("a file where the directory should be")
    return CP.place(env=_cloud_env(tmp_path))


# ---------------------------------------------------------------- confirm: scenarios


def _fake_run(stdout="READY\n", stderr="OpenAI Codex v0\n", code=0, raises=None,
              version="codex-cli 99.0.0", calls=None):
    def run(argv, **kwargs):
        if calls is not None:
            calls.append((list(argv), kwargs))
        if list(argv) == ["codex", "--version"]:
            return SimpleNamespace(returncode=0, stdout=version + "\n", stderr="")
        if list(argv)[0] != "codex":
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if raises is not None:
            raise raises
        return SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr)
    return run


def _placed_env(tmp_path, signin_obj=None, pass_value=PASS, **extra):
    env = _cloud_env(tmp_path, pass_value=pass_value, **extra)
    obj = _pass_obj() if signin_obj is None else signin_obj
    _write(_default(tmp_path), json.dumps(obj, indent=2))
    return env


def _confirm(tmp_path, env=None, now=NOW, **fake):
    env = _placed_env(tmp_path) if env is None else env
    return CP.confirm(env=env, run=_fake_run(**fake), now=now)


def _scn_c_ok(tmp_path):
    return _confirm(tmp_path)


def _scn_c1(tmp_path):
    env = _placed_env(tmp_path)
    env[CP.CLOUD_ENV] = "1"
    return _confirm(tmp_path, env=env)


def _scn_c2(tmp_path):
    return _confirm(tmp_path, env=_placed_env(tmp_path, pass_value="%%% not base64 %%%"))


def _scn_c3(tmp_path):
    older = _pass_obj(access=OLD_ACCESS)
    return _confirm(tmp_path, env=_placed_env(tmp_path, signin_obj=older))


def _scn_c4(tmp_path):
    garbled = _pass_obj(access="not-a-token")
    env = _placed_env(tmp_path, signin_obj=garbled, pass_value=_encode(garbled))
    return _confirm(tmp_path, env=env)


def _scn_c5(tmp_path):
    return _confirm(tmp_path, now=EXP + 1)


def _scn_c6(tmp_path):
    return _confirm(tmp_path, raises=subprocess.TimeoutExpired("codex", 1))


def _scn_c7(tmp_path):
    return _confirm(tmp_path, code=1)


def _scn_c8(tmp_path):
    return _confirm(tmp_path, stdout="")


SCENARIOS = {
    "make-ok": _scn_make_ok, "M1": _scn_m1, "M2": _scn_m2, "M3": _scn_m3, "M4": _scn_m4,
    "M5": _scn_m5, "M6": _scn_m6, "M7": _scn_m7, "M8": _scn_m8,
    "place-ok": _scn_place_ok, "P1": _scn_p1, "P2": _scn_p2, "P3": _scn_p3, "P4": _scn_p4,
    "P5": _scn_p5, "P6": _scn_p6,
    "confirm-ok": _scn_c_ok, "C1": _scn_c1, "C2": _scn_c2, "C3": _scn_c3, "C4": _scn_c4,
    "C5": _scn_c5, "C6": _scn_c6, "C7": _scn_c7, "C8": _scn_c8,
}


# ---------------------------------------------------------------- make: tests


def test_make_puts_four_line_block_on_clipboard(tmp_path):
    result, calls = _make_with(tmp_path, _signin())
    assert len(calls) == 1
    block = calls[0]
    assert block.endswith("\n")
    lines = block.splitlines()
    assert len(lines) == 4
    assert lines[0].startswith("SUPERHEROES_REVIEWER_PASS=")
    assert lines[1:] == [
        "CLAUDE_CODE_PLUGIN_DIRS=/opt/superheroes/plugin",
        "CODEX_REFRESH_TOKEN_URL_OVERRIDE=http://127.0.0.1:9/",
        "CODEX_REVOKE_TOKEN_URL_OVERRIDE=http://127.0.0.1:9/",
    ]
    decoded = _decode(lines[0])
    assert decoded["tokens"]["refresh_token"] == ""
    assert decoded["tokens"]["access_token"] == ACCESS
    assert decoded["tokens"]["id_token"] == IDENT
    assert decoded["tokens"]["account_id"] == "acct-fixture"
    assert decoded["OPENAI_API_KEY"] is None
    assert decoded["auth_mode"] == "chatgpt"
    assert decoded["last_refresh"] == "2027-01-15T08:00:00Z"
    assert "\n" not in lines[0]
    assert RENEWAL not in block
    assert result == {
        "action": "copied", "reason": None, "passLapses": EXP_DATE, "daysLeft": 10.0,
        "characters": len(block), "message": result["message"]}
    assert "paste" in result["message"] and "replacing" in result["message"]


def test_make_writes_no_file_and_leaves_setup_record_alone(tmp_path):
    _write(_separate(tmp_path), _signin())
    record = _write(tmp_path / "setup-record.json", {"passLapses": "2027-01-25"})
    before = _snapshot(tmp_path)
    CP.make(env=_env(tmp_path), clipboard=lambda _t: None, now=NOW)
    assert _snapshot(tmp_path) == before
    assert json.loads(record.read_text()) == {"passLapses": "2027-01-25"}


def test_make_m1_no_separate_sign_in(tmp_path):
    result, calls = _make_with(tmp_path, None)
    assert result["action"] == "refused" and result["reason"] == "no-separate-sign-in"
    assert calls == []
    assert "CODEX_HOME" in result["message"] and ".codex-cloud" in result["message"]


@pytest.mark.parametrize("variant", ["symlink", "codex-home-points-at-separate"])
def test_make_refuses_when_separate_sign_in_is_the_main_one(tmp_path, variant):
    _write(_separate(tmp_path), _signin())
    env = _env(tmp_path)
    if variant == "symlink":
        os.symlink(_separate(tmp_path).parent, _default(tmp_path).parent)
    else:
        env["CODEX_HOME"] = str(_separate(tmp_path).parent)
    calls = []
    result = CP.make(env=env, clipboard=calls.append, now=NOW)
    assert result["action"] == "refused" and result["reason"] == "separate-sign-in-is-main"
    assert calls == []


def test_make_m3_sign_in_unreadable(tmp_path):
    for content in ("this is not json", "[1, 2]", ""):
        result, calls = _make_with(tmp_path, content)
        assert result["reason"] == "sign-in-unreadable" and calls == []
    _separate(tmp_path).write_bytes(b"\xff\xfe\x00")
    result, calls = _make_with(tmp_path, None)
    assert result["reason"] == "sign-in-unreadable" and calls == []
    if os.geteuid() != 0:
        _write(_separate(tmp_path), _signin())
        os.chmod(_separate(tmp_path), 0)
        try:
            result, calls = _make_with(tmp_path, None)
        finally:
            os.chmod(_separate(tmp_path), 0o600)
        assert result["reason"] == "sign-in-unreadable" and calls == []


def test_make_m4_sign_in_incomplete(tmp_path):
    no_tokens = _signin()
    del no_tokens["tokens"]
    no_access = _signin()
    del no_access["tokens"]["access_token"]
    empty_id = _signin(ident="")
    for bad in (no_tokens, no_access, empty_id, _signin(tokens="nope")):
        result, calls = _make_with(tmp_path, bad)
        assert result["action"] == "refused" and result["reason"] == "sign-in-incomplete"
        assert calls == []


def test_make_m5_expiry_unreadable(tmp_path):
    no_exp = _b64u(json.dumps({"sub": "x"}).encode())
    str_exp = _b64u(json.dumps({"exp": "soon"}).encode())
    for access in ("not-a-token", "a.b.c", "a." + no_exp + ".c", "a." + str_exp + ".c"):
        result, calls = _make_with(tmp_path, _signin(access=access))
        assert result["action"] == "refused" and result["reason"] == "pass-expiry-unreadable"
        assert calls == []


def test_make_m6_sign_in_expired(tmp_path):
    for now in (EXP, EXP + 5):
        result, calls = _make_with(tmp_path, _signin(), now=now)
        assert result["action"] == "refused" and result["reason"] == "sign-in-expired"
        assert calls == []


def test_make_m7_no_clipboard_never_prints_the_pass(tmp_path, capsys):
    result = _scn_m7(tmp_path)
    assert result["action"] == "refused" and result["reason"] == "no-clipboard"
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_make_m8_clipboard_failed(tmp_path, capsys):
    calls = []

    def boom(text):
        calls.append(text)
        raise OSError("clipboard exploded")

    result, _ = _make_with(tmp_path, _signin(), clipboard=boom)
    assert result["action"] == "refused" and result["reason"] == "clipboard-failed"
    assert len(calls) == 1
    assert "exploded" not in json.dumps(result)
    value = calls[0].splitlines()[0].split("=", 1)[1]
    captured = capsys.readouterr()
    assert value and value not in json.dumps(result)
    assert captured.out == "" and captured.err == ""


def _fake_clipboard_bin(tmp_path, name, body):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    script = bin_dir / name
    script.write_text("#!/bin/sh\n" + body)
    script.chmod(0o755)
    return bin_dir


def test_make_default_clipboard_feeds_the_block_on_standard_input(tmp_path):
    sink = tmp_path / "clip.txt"
    bin_dir = _fake_clipboard_bin(tmp_path, "pbcopy", "cat > %s\n" % sink)
    _write(_separate(tmp_path), _signin())
    result = CP.make(env=_env(tmp_path, PATH=str(bin_dir)), now=NOW)
    assert result["action"] == "copied"
    block = sink.read_text()
    assert block.splitlines()[0].startswith("SUPERHEROES_REVIEWER_PASS=")
    assert result["characters"] == len(block)
    assert RENEWAL not in block


def test_make_default_clipboard_nonzero_exit_is_clipboard_failed(tmp_path):
    bin_dir = _fake_clipboard_bin(tmp_path, "xclip", "cat > /dev/null\nexit 3\n")
    _write(_separate(tmp_path), _signin())
    result = CP.make(env=_env(tmp_path, PATH=str(bin_dir)), now=NOW)
    assert result["action"] == "refused" and result["reason"] == "clipboard-failed"


def test_make_separate_home_override_and_tilde_expand_against_supplied_home(tmp_path):
    _write(tmp_path / "elsewhere" / "auth.json", _signin())
    result, calls = _make_with(
        tmp_path, None, env=_env(tmp_path, SUPERHEROES_REVIEWER_PASS_HOME=str(tmp_path / "elsewhere")))
    assert result["action"] == "copied" and len(calls) == 1
    _write(_home(tmp_path) / "sep2" / "auth.json", _signin())
    result, calls = _make_with(
        tmp_path, None, env=_env(tmp_path, SUPERHEROES_REVIEWER_PASS_HOME="~/sep2"))
    assert result["action"] == "copied" and len(calls) == 1


# ---------------------------------------------------------------- place: tests


def _recording_opens(monkeypatch):
    """Record every path opened with a write or create flag or mode, through os.open and open."""
    opened = []
    real_os_open, real_open, real_io_open = os.open, builtins.open, io.open
    write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND

    def os_open(path, flags, *a, **k):
        if flags & write_flags or a or "mode" in k:
            opened.append(os.path.realpath(os.fspath(path)))
        return real_os_open(path, flags, *a, **k)

    def open_(path, mode="r", *a, **k):
        if not isinstance(path, int) and any(ch in str(mode) for ch in "wax+"):
            opened.append(os.path.realpath(os.fspath(path)))
        return real_open(path, mode, *a, **k)

    def io_open(path, mode="r", *a, **k):
        if not isinstance(path, int) and any(ch in str(mode) for ch in "wax+"):
            opened.append(os.path.realpath(os.fspath(path)))
        return real_io_open(path, mode, *a, **k)

    monkeypatch.setattr(os, "open", os_open)
    monkeypatch.setattr(builtins, "open", open_)
    monkeypatch.setattr(io, "open", io_open)
    return opened


@pytest.mark.parametrize("codex_home", [None, "custom"])
def test_place_writes_the_pass_to_the_default_sign_in_with_mode_600(tmp_path, codex_home):
    env = _cloud_env(tmp_path)
    if codex_home:
        env["CODEX_HOME"] = str(tmp_path / "custom-codex")
        dest = tmp_path / "custom-codex" / "auth.json"
    else:
        dest = _default(tmp_path)
    result = CP.place(env=env)
    assert result == {"action": "placed", "reason": None, "passLapses": EXP_DATE}
    assert dest.read_bytes() == base64.b64decode(PASS)
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600
    assert stat.S_IMODE(dest.parent.stat().st_mode) == 0o700


def test_place_writes_only_the_destination(tmp_path, monkeypatch):
    env = _cloud_env(tmp_path)
    opened = _recording_opens(monkeypatch)
    result = CP.place(env=env)
    monkeypatch.undo()
    assert result["action"] == "placed"
    assert set(opened) == {os.path.realpath(str(_default(tmp_path)))}
    stray = [p for p in _snapshot(tmp_path) if os.path.isfile(p) and p != str(_default(tmp_path))]
    assert stray == []


def test_place_replaces_an_existing_sign_in_and_tightens_its_mode(tmp_path):
    dest = _write(_default(tmp_path), _signin(access=OLD_ACCESS))
    os.chmod(dest, 0o644)
    result = CP.place(env=_cloud_env(tmp_path))
    assert result["action"] == "placed"
    assert dest.read_bytes() == base64.b64decode(PASS)
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600


def test_place_writes_nothing_when_the_destination_already_holds_the_bytes(tmp_path, monkeypatch):
    CP.place(env=_cloud_env(tmp_path))
    opened = _recording_opens(monkeypatch)
    result = CP.place(env=_cloud_env(tmp_path))
    monkeypatch.undo()
    assert result["action"] == "placed"
    assert opened == []


@pytest.mark.parametrize("cloud_value", [None, "1", "True", "false", ""])
def test_place_outside_cloud_session_opens_nothing_for_writing(tmp_path, monkeypatch, cloud_value):
    env = _cloud_env(tmp_path)
    del env[CP.CLOUD_ENV]
    if cloud_value is not None:
        env[CP.CLOUD_ENV] = cloud_value
    dest = _write(_default(tmp_path), _signin(access=OLD_ACCESS))
    before = dest.read_bytes()
    opened = _recording_opens(monkeypatch)
    result = CP.place(env=env)
    monkeypatch.undo()
    assert result == {"action": "skipped", "reason": "not-a-cloud-session"}
    assert opened == []
    assert dest.read_bytes() == before


def _refusal_leaves_sign_in_alone(tmp_path, env, expect):
    dest = _write(_default(tmp_path), _signin(access=OLD_ACCESS))
    before = dest.read_bytes()
    result = CP.place(env=env)
    assert {k: result[k] for k in expect} == expect
    assert dest.read_bytes() == before
    return result


def test_place_p2_no_pass_in_environment(tmp_path):
    for blank in (None, "", "   "):
        _refusal_leaves_sign_in_alone(
            tmp_path, _cloud_env(tmp_path, pass_value=blank),
            {"action": "skipped", "reason": "no-pass-in-environment"})


def test_place_p3_pass_unreadable(tmp_path):
    for bad in ("%%% not base64 %%%", base64.b64encode(b"not json").decode(),
                base64.b64encode(b"[1, 2]").decode()):
        _refusal_leaves_sign_in_alone(
            tmp_path, _cloud_env(tmp_path, pass_value=bad),
            {"action": "refused", "reason": "pass-unreadable"})


def test_place_refuses_a_pass_that_can_renew(tmp_path):
    no_key = _pass_obj()
    del no_key["tokens"]["refresh_token"]
    no_tokens = _pass_obj()
    del no_tokens["tokens"]
    for bad in (RENEWABLE_PASS, _encode(no_key), _encode(no_tokens),
                _encode(_pass_obj(refresh=None))):
        result = _refusal_leaves_sign_in_alone(
            tmp_path, _cloud_env(tmp_path, pass_value=bad),
            {"action": "refused", "reason": "pass-can-renew"})
        assert RENEWAL not in json.dumps(result)


def test_place_p5_pass_incomplete(tmp_path):
    for bad in (_pass_obj(access=""), _pass_obj(ident=""), _pass_obj(access=None)):
        _refusal_leaves_sign_in_alone(
            tmp_path, _cloud_env(tmp_path, pass_value=_encode(bad)),
            {"action": "refused", "reason": "pass-incomplete"})
    no_id = _pass_obj()
    del no_id["tokens"]["id_token"]
    _refusal_leaves_sign_in_alone(
        tmp_path, _cloud_env(tmp_path, pass_value=_encode(no_id)),
        {"action": "refused", "reason": "pass-incomplete"})


def test_place_p6_write_failed_carries_only_the_exception_type(tmp_path):
    (_home(tmp_path) / ".codex").write_text("a file where the directory should be")
    result = CP.place(env=_cloud_env(tmp_path))
    assert result["action"] == "refused" and result["reason"] == "write-failed"
    assert result["error"] in {"FileExistsError", "NotADirectoryError"}
    assert str(tmp_path) not in json.dumps(result)


def test_place_lapse_date_none_when_expiry_unreadable(tmp_path):
    result = CP.place(env=_cloud_env(tmp_path, pass_value=_encode(_pass_obj(access="not-a-token"))))
    assert result == {"action": "placed", "reason": None, "passLapses": None}


# ---------------------------------------------------------------- confirm: tests


def test_confirm_all_true_row(tmp_path):
    calls = []
    env = _placed_env(tmp_path)
    result = CP.confirm(env=env, run=_fake_run(calls=calls), now=NOW)
    assert result == {"schema": "cloud-pass-confirmation/1", "reviewerAnswered": True,
                      "passLapses": EXP_DATE, "reason": None}
    assert ["codex", "exec", "--sandbox", "read-only", "-"] in [argv for argv, _ in calls]


def _assert_no(result, reason, lapses=None):
    assert result["schema"] == CP.CONFIRMATION_SCHEMA
    assert result["reviewerAnswered"] is False
    assert result["reason"] == reason
    assert result["passLapses"] == lapses


def test_confirm_c1_not_a_cloud_session(tmp_path):
    calls = []
    env = _placed_env(tmp_path)
    for value in (None, "1", "True", "false"):
        env.pop(CP.CLOUD_ENV, None)
        if value is not None:
            env[CP.CLOUD_ENV] = value
        _assert_no(CP.confirm(env=env, run=_fake_run(calls=calls), now=NOW), "not-a-cloud-session")
    assert calls == []


def test_confirm_c2_pass_missing_or_unreadable(tmp_path):
    _assert_no(_confirm(tmp_path, env=_placed_env(tmp_path, pass_value=None)),
               "no-pass-in-environment")
    _assert_no(_confirm(tmp_path, env=_placed_env(tmp_path, pass_value="  ")),
               "no-pass-in-environment")
    _assert_no(_scn_c2(tmp_path), "pass-unreadable")
    _assert_no(_confirm(tmp_path, env=_placed_env(tmp_path, pass_value=_encode([1]))),
               "pass-unreadable")


def test_confirm_pass_not_placed_when_older_sign_in_on_disk(tmp_path):
    calls = []
    older = _pass_obj(access=OLD_ACCESS)
    env = _placed_env(tmp_path, signin_obj=older)
    result = CP.confirm(env=env, run=_fake_run(calls=calls), now=NOW)
    _assert_no(result, "pass-not-placed")
    assert calls == []


def test_confirm_c3_no_sign_in_file_or_not_json(tmp_path):
    env = _cloud_env(tmp_path)
    _assert_no(CP.confirm(env=env, run=_fake_run(), now=NOW), "pass-not-placed")
    _write(_default(tmp_path), "not json")
    _assert_no(CP.confirm(env=env, run=_fake_run(), now=NOW), "pass-not-placed")


def test_confirm_compares_parsed_objects_and_never_places(tmp_path):
    env = _placed_env(tmp_path)
    dest = _default(tmp_path)
    before = dest.read_bytes()
    assert CP.confirm(env=env, run=_fake_run(), now=NOW)["reviewerAnswered"] is True
    assert dest.read_bytes() == before
    dest.unlink()
    _assert_no(CP.confirm(env=env, run=_fake_run(), now=NOW), "pass-not-placed")
    assert not dest.exists()


def test_confirm_c4_expiry_unreadable(tmp_path):
    _assert_no(_scn_c4(tmp_path), "pass-expiry-unreadable")


def test_confirm_c5_pass_lapsed(tmp_path):
    calls = []
    result = CP.confirm(env=_placed_env(tmp_path), run=_fake_run(calls=calls), now=EXP)
    _assert_no(result, "pass-lapsed", lapses=EXP_DATE)
    assert calls == []


def test_confirm_c6_reviewer_did_not_run(tmp_path):
    _assert_no(_scn_c6(tmp_path), "reviewer-did-not-run", lapses=EXP_DATE)
    _assert_no(_confirm(tmp_path, raises=OSError("no such file")), "reviewer-did-not-run",
               lapses=EXP_DATE)
    _assert_no(_confirm(tmp_path, version="codex-cli 0.0.1"), "reviewer-did-not-run",
               lapses=EXP_DATE)


def test_confirm_c7_reviewer_refused(tmp_path):
    _assert_no(_confirm(tmp_path, code=2), "reviewer-refused", lapses=EXP_DATE)


@pytest.mark.parametrize("fixture", [
    {"stdout": ""},
    {"stdout": "", "stderr": "READY\n"},
    {"stdout": "DONE\n"},
], ids=["empty-stdout", "ready-on-stderr-only", "different-word"])
def test_confirm_unexpected_answer(tmp_path, fixture):
    _assert_no(_confirm(tmp_path, **fixture), "reviewer-answer-unexpected", lapses=EXP_DATE)


def test_confirm_ready_with_surrounding_whitespace_still_answers(tmp_path):
    assert _confirm(tmp_path, stdout="\n READY \n")["reviewerAnswered"] is True


# ---------------------------------------------------------------- invariant


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_invariant_no_result_or_output_carries_the_pass(tmp_path, capsys, name):
    result = SCENARIOS[name](tmp_path)
    captured = capsys.readouterr()
    haystack = json.dumps(result) + captured.out + captured.err
    for secret in SECRETS:
        assert secret not in haystack
    assert isinstance(result, dict)


# ---------------------------------------------------------------- command line


def _cli_env(monkeypatch, tmp_path, cloud=True, pass_value=PASS):
    monkeypatch.setenv("HOME", str(_home(tmp_path)))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv(CP.CLOUD_ENV, raising=False)
    monkeypatch.delenv(CP.PASS_ENV, raising=False)
    if cloud:
        monkeypatch.setenv(CP.CLOUD_ENV, "true")
    if pass_value is not None:
        monkeypatch.setenv(CP.PASS_ENV, pass_value)


def _one_json_line(capsys):
    out = capsys.readouterr().out
    assert out.endswith("\n") and out.count("\n") == 1
    return json.loads(out)


def test_cli_place_prints_one_json_line_and_exits_zero(tmp_path, monkeypatch, capsys):
    _cli_env(monkeypatch, tmp_path)
    assert CP.main(["place"]) == 0
    assert _one_json_line(capsys) == {"action": "placed", "reason": None, "passLapses": EXP_DATE}
    assert _default(tmp_path).read_bytes() == base64.b64decode(PASS)


def test_cli_place_skipped_exits_zero_and_refused_exits_one(tmp_path, monkeypatch, capsys):
    _cli_env(monkeypatch, tmp_path, cloud=False)
    assert CP.main(["place"]) == 0
    assert _one_json_line(capsys) == {"action": "skipped", "reason": "not-a-cloud-session"}
    _cli_env(monkeypatch, tmp_path, pass_value=RENEWABLE_PASS)
    assert CP.main(["place"]) == 1
    assert _one_json_line(capsys)["reason"] == "pass-can-renew"


def test_cli_confirm_prints_one_json_line_and_exits_zero_either_way(tmp_path, monkeypatch, capsys):
    _cli_env(monkeypatch, tmp_path)
    _write(_default(tmp_path), _pass_obj())
    monkeypatch.setattr(subprocess, "run", _fake_run())
    assert CP.main(["confirm"]) == 0
    assert _one_json_line(capsys)["reviewerAnswered"] is True
    _default(tmp_path).unlink()
    assert CP.main(["confirm"]) == 0
    assert _one_json_line(capsys)["reason"] == "pass-not-placed"


def test_cli_make_refused_exits_one(tmp_path, monkeypatch, capsys):
    _cli_env(monkeypatch, tmp_path, cloud=False, pass_value=None)
    assert CP.main(["make"]) == 1
    assert _one_json_line(capsys)["reason"] == "no-separate-sign-in"


@pytest.mark.parametrize("argv", [[], ["bogus"], ["place", "extra"]])
def test_cli_unknown_verb_refuses(capsys, argv):
    assert CP.main(argv) == 1
    assert _one_json_line(capsys)["action"] == "refused"


# ---------------------------------------------------------------- external literals


@pytest.mark.parametrize("name,value", [
    ("PASS_ENV", "SUPERHEROES_REVIEWER_PASS"),
    ("CLOUD_ENV", "CLAUDE_CODE_REMOTE"),
    ("PLUGIN_DIRS_ENV", "CLAUDE_CODE_PLUGIN_DIRS"),
    ("CLOUD_PLUGIN_DIR", "/opt/superheroes/plugin"),
    ("RENEWAL_ENDPOINT_ENVS", ("CODEX_REFRESH_TOKEN_URL_OVERRIDE",
                               "CODEX_REVOKE_TOKEN_URL_OVERRIDE")),
    ("DEAD_ENDPOINT", "http://127.0.0.1:9/"),
    ("SEPARATE_HOME_ENV", "SUPERHEROES_REVIEWER_PASS_HOME"),
    ("SEPARATE_HOME_DEFAULT", "~/.codex-cloud"),
    ("CONFIRMATION_SCHEMA", "cloud-pass-confirmation/1"),
])
def test_external_literal_is_pinned(name, value):
    assert getattr(CP, name) == value


# ---------------------------------------------------------------- record-confirmation

ACCOUNT = "acct-fixture-one"
ENVIRONMENT = "env-fixture-one"
RECORDED_LAPSE = "2026-08-01"
NEW_LAPSE = "2027-01-25"


def _project(tmp_path):
    """A git repository under tmp_path whose store holds a real setup record for ACCOUNT."""
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (("init", "-q"), ("remote", "add", "origin", "https://github.com/acme/shop.git")):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    cwd, root = str(repo), str(tmp_path / "store-root")
    key = store_core.derive_identifiers(cwd)["remote_hash"]
    mode_registry.write_registry(cwd, mode_registry.GLOBAL, key, root=root)
    made = cloud_setup.record_check(
        cwd, account=ACCOUNT, environment=ENVIRONMENT, plugin_version="1.2.3",
        picks_up_version=False, calibration_stamp="none", calibration_date="2026-07-01",
        pass_lapses=RECORDED_LAPSE, checked_at="2026-07-02", root=root)
    assert made == {"action": "written"}
    return cwd, root, cloud_setup.record_path(cwd, ACCOUNT, root)


def _confirmation(answered=True, lapses=NEW_LAPSE, **over):
    out = {"schema": CP.CONFIRMATION_SCHEMA, "reviewerAnswered": answered, "passLapses": lapses,
           "reason": None}
    out.update(over)
    return out


def _record(tmp_path, confirmation, **kw):
    cwd, root, path = _project(tmp_path)
    before = open(path, "rb").read()
    kw = {"account": ACCOUNT, "now": NOW, "root": root, **kw}
    result = CP.record_confirmation(cwd, confirmation, **kw)
    return result, before, open(path, "rb").read()


def test_record_confirmation_moves_the_lapse_date_when_the_reviewer_answered(tmp_path):
    cwd, root, path = _project(tmp_path)
    result = CP.record_confirmation(cwd, _confirmation(), account=ACCOUNT, now=NOW, root=root)
    assert result == {"action": "written"}
    record = cloud_setup.read(cwd, ACCOUNT, root=root)["record"]
    assert record["passLapses"] == NEW_LAPSE and record["environment"] == ENVIRONMENT


def test_record_confirmation_accepts_a_pass_that_lapses_today(tmp_path):
    result, before, after = _record(tmp_path, _confirmation(lapses="2027-01-15"))
    assert result == {"action": "written"} and before != after


def test_record_confirmation_r2_reviewer_did_not_answer_moves_nothing(tmp_path):
    result, before, after = _record(tmp_path, _confirmation(answered=False))
    assert result == {"action": "noop", "reason": "reviewer-did-not-answer"}
    assert after == before


@pytest.mark.parametrize("bad", [
    "not a dict", _confirmation(schema="other/1"), _confirmation(answered="true")],
    ids=["not-a-dict", "wrong-schema", "answered-not-bool"])
def test_record_confirmation_r1_unreadable_confirmation_moves_nothing(tmp_path, bad):
    result, before, after = _record(tmp_path, bad)
    assert result == {"action": "refused", "reason": "confirmation-unreadable"}
    assert after == before


@pytest.mark.parametrize("lapses", [None, 20270125, "2027-1-25", "2027-02-30", "tomorrow", ""])
def test_record_confirmation_r3_unreadable_lapse_date_moves_nothing(tmp_path, lapses):
    result, before, after = _record(tmp_path, _confirmation(lapses=lapses))
    assert result == {"action": "refused", "reason": "confirmation-unreadable"}
    assert after == before


def test_record_confirmation_r4_lapsed_date_moves_nothing(tmp_path):
    result, before, after = _record(tmp_path, _confirmation(lapses="2027-01-14"))
    assert result == {"action": "noop", "reason": "pass-lapsed"}
    assert after == before


def test_record_confirmation_r5_unknown_account_moves_nothing(tmp_path):
    env = {"HOME": str(_home(tmp_path)), "CLAUDE_CONFIG_DIR": str(tmp_path / "no-config")}
    result, before, after = _record(tmp_path, _confirmation(), account=None, env=env)
    assert result == {"action": "refused", "reason": "account-unknown"}
    assert after == before


def test_record_confirmation_reads_the_launching_account_when_none_is_given(tmp_path):
    config = tmp_path / "claude-config"
    _write(config / ".claude.json", {"oauthAccount": {"accountUuid": ACCOUNT}})
    env = {"HOME": str(_home(tmp_path)), "CLAUDE_CONFIG_DIR": str(config)}
    result, before, after = _record(tmp_path, _confirmation(), account=None, env=env)
    assert result == {"action": "written"} and before != after


def test_record_confirmation_r6_environment_mismatch_is_refused_and_moves_nothing(tmp_path):
    result, before, after = _record(tmp_path, _confirmation(), environment="env-other")
    assert result == {"action": "refused", "reason": "environment-mismatch"}
    assert after == before


def test_record_confirmation_r6_account_without_a_record_creates_no_file(tmp_path):
    cwd, root, path = _project(tmp_path)
    other = cloud_setup.record_path(cwd, "acct-fixture-two", root)
    listing = _snapshot(os.path.dirname(path))
    result = CP.record_confirmation(cwd, _confirmation(), account="acct-fixture-two", now=NOW,
                                    root=root)
    assert result == {"action": "refused", "reason": "cloud-setup-missing"}
    assert not os.path.exists(other) and _snapshot(os.path.dirname(path)) == listing


def test_make_leaves_a_real_setup_record_byte_identical(tmp_path):
    _, _, path = _project(tmp_path)
    _write(_separate(tmp_path), _signin())
    before = open(path, "rb").read()
    assert CP.make(env=_env(tmp_path), clipboard=lambda _t: None, now=NOW)["action"] == "copied"
    assert open(path, "rb").read() == before


def test_make_does_not_import_the_setup_record_module(tmp_path):
    _write(_separate(tmp_path), _signin())
    code = ("import importlib.util, json, sys\n"
            "spec = importlib.util.spec_from_file_location('cloud_pass', sys.argv[1])\n"
            "mod = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(mod)\n"
            "out = mod.make(env=json.loads(sys.argv[2]), clipboard=lambda t: None, now=%d)\n"
            "print(out['action'], 'cloud_setup' in sys.modules)\n" % NOW)
    proc = subprocess.run(
        [sys.executable, "-I", "-c", code, os.path.join(_HERE, "..", "cloud_pass.py"),
         json.dumps(_env(tmp_path))], capture_output=True, text=True, timeout=60, cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.split() == ["copied", "False"]


def _record_args(cwd, root, confirmation, *extra):
    return ["record-confirmation", "--cwd", cwd, "--root", root, "--account", ACCOUNT,
            "--confirmation", confirmation, *extra]


def test_cli_record_confirmation_prints_written_and_exits_zero(tmp_path, capsys):
    cwd, root, path = _project(tmp_path)
    assert CP.main(_record_args(cwd, root, json.dumps(_confirmation(lapses="2099-01-01")))) == 0
    assert _one_json_line(capsys) == {"action": "written"}
    assert cloud_setup.read(cwd, ACCOUNT, root=root)["record"]["passLapses"] == "2099-01-01"


def test_cli_record_confirmation_that_is_not_json_exits_one(tmp_path, capsys):
    cwd, root, path = _project(tmp_path)
    before = open(path, "rb").read()
    assert CP.main(_record_args(cwd, root, "{not json")) == 1
    assert _one_json_line(capsys)["reason"] == "confirmation-unreadable"
    assert open(path, "rb").read() == before


# ---------------------------------------------------------------- advisor-guided fixes


def _probe_module():
    sys.path.insert(0, os.path.join(_HERE, ".."))
    import preflight_probe
    return preflight_probe


def test_confirm_expected_word_follows_the_prompt_preflight_probe_sends(tmp_path, monkeypatch):
    probe = _probe_module()
    monkeypatch.setattr(probe, "PROBE_ASK", "Reply with the single word GO and nothing else.\n")
    env = _placed_env(tmp_path)
    assert CP.confirm(env=env, run=_fake_run(stdout="READY\n"), now=NOW)["reason"] == \
        "reviewer-answer-unexpected"
    assert CP.confirm(env=env, run=_fake_run(stdout="GO\n"), now=NOW)["reviewerAnswered"] is True


def test_confirm_fails_closed_when_the_prompt_word_cannot_be_read(tmp_path, monkeypatch):
    monkeypatch.setattr(_probe_module(), "PROBE_ASK", "Say something.\n")
    calls = []
    result = CP.confirm(env=_placed_env(tmp_path), run=_fake_run(calls=calls), now=NOW)
    assert result["reviewerAnswered"] is False and result["reason"] == "reviewer-did-not-answer"
    assert calls == []


@pytest.mark.parametrize("name", ["CODEX_API_KEY", "OPENAI_API_KEY"])
def test_confirm_refuses_an_api_key_in_the_environment(tmp_path, name):
    calls = []
    env = _placed_env(tmp_path, **{name: "key-value"})
    result = CP.confirm(env=env, run=_fake_run(calls=calls), now=NOW)
    assert result["reviewerAnswered"] is False and result["reason"] == "api-key-in-environment"
    assert calls == []


def test_confirm_refuses_an_api_key_in_the_placed_sign_in(tmp_path):
    calls = []
    keyed = _pass_obj()
    keyed["OPENAI_API_KEY"] = "key-value"
    env = _placed_env(tmp_path, signin_obj=keyed, pass_value=_encode(keyed))
    result = CP.confirm(env=env, run=_fake_run(calls=calls), now=NOW)
    assert result["reviewerAnswered"] is False and result["reason"] == "api-key-in-sign-in"
    assert calls == []


def test_clipboard_command_runs_without_captured_pipes(monkeypatch):
    seen = {}

    def fake(argv, **kwargs):
        seen.update(kwargs)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(CP.subprocess, "run", fake)
    CP._run_clipboard(("pbcopy",), "text")
    assert not seen.get("capture_output")
    assert seen["stdout"] == subprocess.DEVNULL and seen["stderr"] == subprocess.DEVNULL
    assert seen["input"] == "text"
