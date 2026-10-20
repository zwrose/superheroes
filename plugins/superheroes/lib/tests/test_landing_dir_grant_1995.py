"""#1995: a claude `dispatch-write` run opened with --landing-dir grants the child one directory.

Invariant: the grant is exactly one extra directory, the realpath of a review landing slot
(`<session>/round-<N>/landing/<phase>`) that overlaps no deny entry; anything else refuses at open
with nothing opened. A run opened without the flag builds today's argv and settings."""
import json
import os
import shutil

import pytest

# The write-dispatch suite's helpers and its autouse tmp-base/journal-root/uv-absent fixture.
from test_engine_dispatch_write import (  # noqa: F401
    ED,
    EA,
    RR,
    FakeRunner,
    _ClaudeStdoutWriteFakeRunner,
    _build_ok_stdout,
    _claude_write_runner,
    _dispatch_write,
    _ensure_claude_config_dir,
    _implementer_claude_seat,
    _linked_worktree,
    _pin_temp_base_to_tmp_path,
    _write_opened_record,
)

PHASE = "dispatch-fixer"
SESSION = "s" * 32
SEAT = "fixer-1"
INVALID = "engine-config:sandbox-landing-dir-invalid"
DENIED = "engine-config:sandbox-landing-dir-denied"
MISMATCH = "engine-config:sandbox-landing-dir-mismatch"

_SANDBOX = {
    "writeRoots": ["/work/wt", "/work/main/.git/worktrees/wt", "/work/main/.git"],
    "denyWrite": ["/work/main/.git/hooks", "/work/main/.git/config"],
    "uvCacheDir": None,
}
_LANDING = "/tmp/review-x/round-1/landing/dispatch-fixer"


def _session(tmp_path, name="session"):
    sd = str(tmp_path / name)
    os.makedirs(sd, exist_ok=True)
    RR.atomic_write_json(os.path.join(sd, "meta.json"), {"sessionId": SESSION})
    return sd


def _landing(tmp_path, name="session"):
    sd = _session(tmp_path, name)
    path = RR.landing_dir(sd, 1, PHASE)
    os.makedirs(path, exist_ok=True)
    return sd, path


def _write_argv(sandbox):
    return EA.build_argv_result(
        {"vendor": "claude", "model": "sonnet-5.5", "effort": "high", "role": "implementer"},
        "build", {"claudeWriteSandbox": sandbox})


def _settings_of(argv):
    return json.loads(argv[argv.index("--settings") + 1])


def _open(tmp_path, monkeypatch, wt=None, run_dir=None, **kw):
    _ensure_claude_config_dir(tmp_path, monkeypatch)
    if wt is None:
        wt, _main = _linked_worktree(tmp_path)
    run_dir = run_dir or str(tmp_path / "run")
    fake = _ClaudeStdoutWriteFakeRunner([_claude_write_runner()])
    res = _dispatch_write(tmp_path, fake, cwd=wt, run_dir=run_dir,
                          seat=_implementer_claude_seat(), **kw)
    return wt, run_dir, res, fake


def _assert_refused_unopened(res, fake, run_dir, detail):
    assert res["detail"] == detail, res
    assert res["attempts"] == 0
    assert fake.calls == []
    records = ED._journal_read(run_dir)[0] if os.path.isdir(run_dir) else []
    assert all(r.get("kind") != "run-opened" for r in records)


# --- T1: argv and settings ------------------------------------------------------------------


def test_argv_carries_add_dir_before_settings_and_allow_write():
    sandbox = dict(_SANDBOX, landingDir=_LANDING)
    argv = _write_argv(sandbox)["argv"]
    i = argv.index("--add-dir")
    assert argv[i + 1] == _LANDING
    # variadic flag: the next token must be a flag or it swallows the prompt
    assert argv[i + 2] == "--settings"
    assert _LANDING in _settings_of(argv)["sandbox"]["filesystem"]["allowWrite"]


def test_argv_without_landing_dir_is_unchanged():
    base = _write_argv(_SANDBOX)["argv"]
    assert "--add-dir" not in base
    with_landing = _write_argv(dict(_SANDBOX, landingDir=_LANDING))["argv"]
    i = with_landing.index("--add-dir")
    stripped = with_landing[:i] + with_landing[i + 2:]
    assert stripped[:-1] == base[:-1]
    base_allow = _settings_of(base)["sandbox"]["filesystem"]["allowWrite"]
    assert base_allow == _SANDBOX["writeRoots"]
    grant_settings = _settings_of(with_landing)
    assert grant_settings["sandbox"]["filesystem"]["allowWrite"] == base_allow + [_LANDING]
    grant_settings["sandbox"]["filesystem"]["allowWrite"] = base_allow
    assert grant_settings == _settings_of(base)


# --- T2: open-time validation (E1-E10, E13) ---------------------------------------------------


def _refuse_rows(tmp_path):
    sd, landing = _landing(tmp_path)
    rows = {}
    rows["E1-relative"] = ("round-1/landing/dispatch-fixer", INVALID)
    rows["E2-glob-raw"] = (os.path.join(str(tmp_path), "se*ssion", "round-1", "landing", PHASE),
                           INVALID)
    star = tmp_path / "s[1]"
    (star / "round-1" / "landing" / PHASE).mkdir(parents=True)
    link = tmp_path / "globlink"
    link.symlink_to(star / "round-1" / "landing" / PHASE)
    rows["E3-glob-realpath"] = (str(link), INVALID)
    root = tmp_path / "rootlink"
    root.symlink_to("/")
    rows["E4-root"] = (str(root), INVALID)
    rows["E5-missing"] = (os.path.join(sd, "round-2", "landing", PHASE), INVALID)
    fsd = _session(tmp_path, "filesession")
    os.makedirs(os.path.join(fsd, "round-1", "landing"))
    afile = os.path.join(fsd, "round-1", "landing", PHASE)
    with open(afile, "w", encoding="utf-8") as fh:
        fh.write("x")
    rows["E6-file"] = (afile, INVALID)
    rows["E7-session-dir"] = (sd, INVALID)
    rows["E7-tmp-path"] = (str(tmp_path), INVALID)
    rows["E7-round-dir"] = (os.path.join(sd, "round-1"), INVALID)
    rows["E7-landing-parent"] = (os.path.join(sd, "round-1", "landing"), INVALID)
    rows["E7-bad-round-name"] = (
        os.path.join(_landing_named(tmp_path, "round-x")), INVALID)
    plain = tmp_path / "plain"
    plain.mkdir()
    bad = tmp_path / "s2" / "round-1" / "landing"
    bad.mkdir(parents=True)
    (bad / PHASE).symlink_to(plain)
    rows["E8-layout-spelled-target-lacks"] = (str(bad / PHASE), INVALID)
    return rows


def _landing_named(tmp_path, round_name):
    path = tmp_path / "s3" / round_name / "landing" / PHASE
    path.mkdir(parents=True)
    return str(path)


_ROW_IDS = [
    "E1-relative", "E2-glob-raw", "E3-glob-realpath", "E4-root", "E5-missing", "E6-file",
    "E7-session-dir", "E7-tmp-path", "E7-round-dir", "E7-landing-parent", "E7-bad-round-name",
    "E8-layout-spelled-target-lacks",
]


@pytest.mark.parametrize("row", _ROW_IDS)
def test_open_refuses_invalid_landing_dir(tmp_path, monkeypatch, row):
    path, detail = _refuse_rows(tmp_path)[row]
    run_dir = str(tmp_path / "run")
    _wt, _rd, res, fake = _open(tmp_path, monkeypatch, run_dir=run_dir, landing_dir=path)
    _assert_refused_unopened(res, fake, run_dir, detail)


def test_open_accepts_symlink_whose_target_has_the_layout_and_journals_realpath(
        tmp_path, monkeypatch):
    _sd, landing = _landing(tmp_path)
    alias = tmp_path / "alias"
    alias.symlink_to(landing)
    _wt, run_dir, res, fake = _open(tmp_path, monkeypatch, landing_dir=str(alias))
    assert res["ok"] is True, res
    opened = _write_opened_record(run_dir)
    assert opened["claudeWriteSandbox"]["landingDir"] == os.path.realpath(landing)
    argv = opened["argv"]
    assert argv[argv.index("--add-dir") + 1] == os.path.realpath(landing)
    assert fake.calls[0]["argv"][fake.calls[0]["argv"].index("--add-dir") + 1] == (
        os.path.realpath(landing))


def test_open_refuses_landing_dir_overlapping_the_run_dir(tmp_path, monkeypatch):
    # equal to the run dir
    sd, landing = _landing(tmp_path)
    wt, _rd, res, fake = _open(tmp_path, monkeypatch, run_dir=landing, landing_dir=landing)
    _assert_refused_unopened(res, fake, landing, DENIED)
    # inside the run dir
    inner = os.path.join(str(tmp_path / "run-in"), "round-1", "landing", PHASE)
    os.makedirs(inner)
    _wt, _rd, res, fake = _open(tmp_path, monkeypatch, wt=wt, run_dir=str(tmp_path / "run-in"),
                                landing_dir=inner)
    _assert_refused_unopened(res, fake, str(tmp_path / "run-in"), DENIED)
    # containing the run dir
    run_inside = os.path.join(landing, "run")
    _wt, _rd, res, fake = _open(tmp_path, monkeypatch, wt=wt, run_dir=run_inside,
                                landing_dir=landing)
    _assert_refused_unopened(res, fake, run_inside, DENIED)


def test_open_refuses_landing_dir_only_overlapping_a_symlinked_deny_entry(tmp_path, monkeypatch):
    # the git hooks entry is joined, not resolved: only its realpath meets the landing dir (F1)
    wt, main = _linked_worktree(tmp_path)
    _sd, landing = _landing(tmp_path)
    hooks = os.path.join(main, ".git", "hooks")
    shutil.rmtree(hooks)
    os.symlink(landing, hooks)
    run_dir = str(tmp_path / "run")
    _wt, _rd, res, fake = _open(tmp_path, monkeypatch, wt=wt, run_dir=run_dir,
                                landing_dir=landing)
    _assert_refused_unopened(res, fake, run_dir, DENIED)


@pytest.mark.parametrize("bad", ["relative/dir", "/tmp/x/round-1/landing/[a]"])
def test_malformed_journaled_landing_dir_refuses_roots_missing(tmp_path, monkeypatch, bad):
    _sd, landing = _landing(tmp_path)
    wt, run_dir, _res, _fake = _open(tmp_path, monkeypatch, landing_dir=landing)
    records, _ = ED._journal_read(run_dir)
    with open(ED._journal_path(run_dir), "w", encoding="utf-8") as fh:
        for rec in records:
            if rec.get("kind") == "run-opened":
                rec["claudeWriteSandbox"]["landingDir"] = bad
            fh.write(json.dumps(rec) + "\n")
    assert EA.claude_write_sandbox_valid(
        _write_opened_record(run_dir)["claudeWriteSandbox"]) is False
    fake = _ClaudeStdoutWriteFakeRunner([])
    res = _dispatch_write(tmp_path, fake, cwd=wt, run_dir=run_dir,
                          seat=_implementer_claude_seat())
    assert res["detail"] == "engine-config:sandbox-roots-missing"
    assert res["attempts"] == 0
    assert fake.calls == []


def test_no_flag_opens_with_no_landing_key_and_no_add_dir(tmp_path, monkeypatch):
    _wt, run_dir, res, fake = _open(tmp_path, monkeypatch)
    assert res["ok"] is True, res
    opened = _write_opened_record(run_dir)
    assert "landingDir" not in opened["claudeWriteSandbox"]
    assert "--add-dir" not in opened["argv"]
    assert "--add-dir" not in fake.calls[0]["argv"]


# --- T3: continuation and non-claude engines (E11, E12) -----------------------------------------


def test_continuation_with_a_different_landing_dir_refuses_mismatch(tmp_path, monkeypatch):
    _sd, landing = _landing(tmp_path)
    _sd2, other = _landing(tmp_path, "other")
    wt, run_dir, first, _fake = _open(tmp_path, monkeypatch, landing_dir=landing)
    fake = _ClaudeStdoutWriteFakeRunner([])
    res = _dispatch_write(tmp_path, fake, cwd=wt, run_dir=run_dir,
                          seat=_implementer_claude_seat(), landing_dir=other)
    assert res["detail"] == MISMATCH
    assert res["attempts"] == 0
    assert fake.calls == []
    # the same grant, spelled through a symlink, and an omitted flag, both continue
    alias = tmp_path / "alias"
    alias.symlink_to(landing)
    for kw in ({"landing_dir": str(alias)}, {}):
        again = _dispatch_write(tmp_path, _ClaudeStdoutWriteFakeRunner([]), cwd=wt,
                                run_dir=run_dir, seat=_implementer_claude_seat(), **kw)
        assert again.get("detail") != MISMATCH, again
        assert again["argv"] == first["argv"]


def test_continuation_naming_a_grant_when_none_was_journaled_refuses_mismatch(
        tmp_path, monkeypatch):
    _sd, landing = _landing(tmp_path)
    wt, run_dir, _first, _fake = _open(tmp_path, monkeypatch)
    fake = _ClaudeStdoutWriteFakeRunner([])
    res = _dispatch_write(tmp_path, fake, cwd=wt, run_dir=run_dir,
                          seat=_implementer_claude_seat(), landing_dir=landing)
    assert res["detail"] == MISMATCH
    assert res["attempts"] == 0
    assert fake.calls == []


def test_non_claude_engine_accepts_and_ignores_the_flag(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir = str(tmp_path / "run")
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    res = _dispatch_write(tmp_path, fake, cwd=wt, run_dir=run_dir,
                          landing_dir="relative/not/validated")
    assert res.get("detail") is None or "landing-dir" not in res["detail"], res
    assert fake.calls
    assert "--add-dir" not in fake.calls[0]["argv"]
    assert "landingDir" not in _write_opened_record(run_dir)


def test_cli_registers_landing_dir_flag():
    parser = ED.build_parser()
    args = parser.parse_args([
        "dispatch-write", "--seat", "{}", "--prompt-path", "p", "--cwd", ".",
        "--run-dir", "r", "--landing-dir", _LANDING])
    assert args.landing_dir == _LANDING
    assert parser.parse_args([
        "dispatch-write", "--seat", "{}", "--prompt-path", "p", "--cwd", ".",
        "--run-dir", "r"]).landing_dir is None


# --- T4: end to end: the fixer writes its own payload and the driver reads it --------------------


def _emulated_restricted_writer(targets):
    """A fake claude that honours the --restricted contract from the argv it receives.

    Allowed directories are its cwd plus every --add-dir value; a write outside them is refused
    the way the Write tool refuses it, so the file never appears."""
    def runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        allowed = [os.path.realpath(cwd)]
        allowed += [os.path.realpath(argv[i + 1]) for i, tok in enumerate(argv)
                    if tok == "--add-dir"]
        for path, content in targets:
            real = os.path.realpath(path)
            if any(real == a or real.startswith(a + os.sep) for a in allowed):
                os.makedirs(os.path.dirname(real), exist_ok=True)
                with open(real, "w", encoding="utf-8") as fh:
                    json.dump(content, fh)
        return _claude_write_runner()(argv, prompt_bytes, timeout, progress_cb, cwd)
    return runner


def _fixer_session(tmp_path):
    sd, landing = _landing(tmp_path)
    skey = RR.storage_key(SEAT)
    stub = RR.envelope_stub_path(sd, 1, PHASE, skey, 0)
    os.makedirs(os.path.dirname(stub), exist_ok=True)
    RR.atomic_write_json(stub, {
        "schema": RR.SEAT_RESULT_SCHEMA, "session": SESSION, "round": 1, "phase": PHASE,
        "seat": SEAT, "attempt": 0, "vendor": "claude", "model": "sonnet-5.5",
        "dispatchRef": "m" * 64, "orderSha256": RR.NOT_EMITTED,
        "manifestSha256": RR.NOT_EMITTED,
    })
    return sd, landing, skey


def _end_to_end(tmp_path, monkeypatch, **kw):
    _ensure_claude_config_dir(tmp_path, monkeypatch)
    sd, landing, skey = _fixer_session(tmp_path)
    other_sd, _other_landing = _landing(tmp_path, "other-session")
    payload_path = RR.bare_payload_path(sd, 1, PHASE, skey, 0)
    same_session = os.path.join(sd, "round-1", "seats", "x.json")
    os.makedirs(os.path.dirname(same_session), exist_ok=True)
    sibling = RR.bare_payload_path(other_sd, 1, PHASE, skey, 0)
    runner = _emulated_restricted_writer([
        (payload_path, {"findings": ["f1"]}),
        (same_session, {"x": 1}),
        (sibling, {"findings": ["f1"]}),
    ])
    wt, _main = _linked_worktree(tmp_path)
    fake = _ClaudeStdoutWriteFakeRunner([runner])
    res = _dispatch_write(tmp_path, fake, cwd=wt, run_dir=str(tmp_path / "run"),
                          seat=_implementer_claude_seat(), **kw)
    return res, sd, payload_path, same_session, sibling


def test_fixer_writes_its_own_payload_and_the_driver_ingests_it(tmp_path, monkeypatch):
    sd_probe = str(tmp_path / "session")
    landing = RR.landing_dir(sd_probe, 1, PHASE)
    res, sd, payload_path, same_session, sibling = _end_to_end(
        tmp_path, monkeypatch, landing_dir=landing)
    assert res["ok"] is True, res
    assert os.path.isfile(payload_path)
    assert not os.path.exists(same_session)
    assert not os.path.exists(sibling)
    out = RR.ingest_landing(sd, 1, PHASE, SEAT, 0, current_attempt=0, roster=[SEAT],
                            anchor=None)
    assert out["ok"] is True, out


def test_without_the_grant_the_fixer_payload_is_not_written(tmp_path, monkeypatch):
    res, sd, payload_path, same_session, sibling = _end_to_end(tmp_path, monkeypatch)
    assert not os.path.exists(payload_path)
    assert not os.path.exists(same_session)
    assert not os.path.exists(sibling)
    out = RR.ingest_landing(sd, 1, PHASE, SEAT, 0, current_attempt=0, roster=[SEAT],
                            anchor=None)
    assert out["ok"] is False and out["reason"] == "landing-missing", out
