"""#1947: the native implementer engine's run wrapper (``native_engine.py``).

Invariant: ``native_engine.py`` implements, exactly, the route, open, enroll, wait and close verbs of
the native engine contract — each verb's refusal and forfeit tokens, journal records and result
shapes — and every check runs at the one place the contract names.

Token and string literals are spelled out as strings on purpose: a test that reaches them through
the module constants stays green under any value (rubric/bite-proof.md).

Detector axes (bite-proof):
- E1 test_route_* — mapping: native only for cloud + linux + localSockets, else the calibrated engine
- E2 test_open_refuses_* — refusal: no run opens, nothing is journaled
- E3 test_open_records_* — preservation: the run-opened record and the agent prompt
- E4 test_enroll_* — refusal: the subagent's worktree is clean, isolated, and pinned to the base
- E5 test_close_forfeits_* — ordering: each close check forfeits on its own token, before any apply
- E6 test_close_status_* — mapping: needs_context and blocked collect nothing
- E7 test_close_grading_* — refusal: undelivered items and incomplete collection forfeit
- E8 test_close_success_* — preservation: the subagent's change lands in the builder's index
- E9 test_close_idempotent_* / _interrupted_ / _journal_write_failed — idempotence: no second apply
- E10 test_wait_* — bound: the wait ends at result.json, the deadline, or the cap
"""
import calendar
import json
import os
import subprocess
import time

import pytest

import core_md
import engine_dispatch as ED
import native_engine as NE

_NO_KEY = object()
_SEAT = '{"vendor": "claude", "model": "sonnet", "effort": "high", "role": "implementer"}'
_AGENT = "a1b2c3d4"
_SONNET = "claude-sonnet-5-5"
_OPUS = "claude-opus-5-5"
_CORE_FACTS = {
    "verifyCommand": "npm test",
    "stackTags": ["node"],
    "threatModel": "single-user",
    "patterns": "- x: a.ts:1",
}


@pytest.fixture(autouse=True)
def _pin_env(tmp_path, monkeypatch):
    store = str(tmp_path / "store-root")
    os.makedirs(store, exist_ok=True)
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", store)
    monkeypatch.delenv("WORKHORSE_STORE_ROOT", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_REMOTE", raising=False)
    monkeypatch.setenv("SUPERHEROES_DISPATCH_JOURNAL_ROOT", str(tmp_path / "journals"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _host(monkeypatch, remote, platform):
    if remote is None:
        monkeypatch.delenv("CLAUDE_CODE_REMOTE", raising=False)
    else:
        monkeypatch.setenv("CLAUDE_CODE_REMOTE", remote)
    monkeypatch.setattr(ED, "_host_platform", lambda: platform)


def _routed(monkeypatch):
    _host(monkeypatch, "true", "linux")


# --- harness: a real main repo, the builder's worktree B, the subagent's worktree T -----------


def _git(cwd, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    proc = subprocess.run(
        ["git", "-C", cwd, "-c", "user.name=t", "-c", "user.email=t@invalid", *args],
        capture_output=True, text=True, env=env, timeout=60)
    assert proc.returncode == 0, "git %s failed: %s" % (" ".join(args), proc.stderr)
    return proc.stdout


def _core_text(block, prefs=None):
    facts = dict(_CORE_FACTS)
    if prefs:
        facts["enginePreferences"] = prefs
    if block is not _NO_KEY:
        facts["sandboxAccess"] = block
    return core_md.render_core(facts, "confirmed", "2026-06-26", "2026-06-26")


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class Repo:
    pass


def _make_repo(tmp_path, block=None, prefs=None):
    """main (with a base commit holding core.md), B (builder), T and T2 (subagent candidates)."""
    block = {"localSockets": True} if block is None else block
    root = os.path.realpath(str(tmp_path))
    r = Repo()
    r.main = os.path.join(root, "main")
    os.makedirs(r.main)
    _git(r.main, "init", "-q", "-b", "main")
    _write(os.path.join(r.main, "a.txt"), "alpha\n")
    _write(os.path.join(r.main, ".gitignore"), "*.log\n")
    _write(os.path.join(r.main, core_md.in_repo_core_rel_path()), _core_text(block, prefs))
    _git(r.main, "add", "-A")
    _git(r.main, "commit", "-q", "-m", "base")
    r.base = _git(r.main, "rev-parse", "HEAD").strip()
    r.B = os.path.join(root, "B")
    _git(r.main, "worktree", "add", "-q", "-b", "build", r.B, r.base)
    r.T = os.path.join(root, "T")
    _git(r.main, "worktree", "add", "-q", "--detach", r.T, r.base)
    r.T2 = os.path.join(root, "T2")
    _git(r.main, "worktree", "add", "-q", "--detach", r.T2, r.base)
    r.run = os.path.join(root, "run")
    r.order = os.path.join(root, "order.md")
    _write(r.order, "# Order\nChange a.txt.\n")
    r.transcript = os.path.join(root, "transcripts", "agent-%s.jsonl" % _AGENT)
    return r


def _cli(capsys, *argv):
    code = NE.main(list(argv))
    out = capsys.readouterr().out
    return code, json.loads(out.strip().splitlines()[-1])


def _open(capsys, r, deadline=600, items=(), seat=_SEAT, base=None, order=None):
    argv = ["open", "--run-dir", r.run, "--order-path", order or r.order, "--cwd", r.B,
            "--base-sha", base or r.base, "--deadline-seconds", str(deadline), "--seat", seat]
    for item in items:
        argv += ["--expect-item", item]
    return _cli(capsys, *argv)


def _records(r):
    return ED._journal_read_raw(os.path.realpath(r.run))[0]


def _kinds(r):
    return [rec.get("kind") for rec in _records(r)]


def _enrolled(r, worktree=None, agent=_AGENT):
    """Stands in for the hook's ``native-enrolled`` record."""
    assert ED._journal_append(os.path.realpath(r.run), {
        "kind": "native-enrolled", "agentId": agent,
        "worktree": os.path.realpath(worktree or r.T), "at": "2026-10-18T00:00:00Z"})


def _re_enroll(r, worktree):
    """Replace the stand-in enrolled record with one naming another worktree."""
    run = os.path.realpath(r.run)
    kept = [rec for rec in _records(r) if rec["kind"] != "native-enrolled"]
    with open(ED._journal_path(run), "w", encoding="utf-8") as fh:
        for rec in kept:
            fh.write(json.dumps(rec) + "\n")
    _enrolled(r, worktree=worktree)


def _transcript(r, models=(_SONNET, _SONNET), name=None):
    lines = ['{"type": "user", "message": {"content": "go"}}', "not json at all"]
    for model in models:
        message = {} if model is None else {"model": model}
        lines.append(json.dumps({"type": "assistant", "message": message}))
    path = name or r.transcript
    _write(path, "\n".join(lines) + "\n")
    return path


def _result(r, status="done", summary="built it"):
    _write(os.path.join(r.run, "result.json"), json.dumps({"status": status, "summary": summary}))


def _close(capsys, r, worktree=None, transcript=None, into=None, forfeit=False):
    argv = ["close", "--run-dir", r.run, "--worktree", worktree or r.T,
            "--transcript", transcript or r.transcript, "--into", into or r.B]
    if forfeit:
        argv += ["--forfeit", "deadline"]
    return _cli(capsys, *argv)


def _ready(capsys, monkeypatch, r, items=(), edit=True):
    """Opened, enrolled, edited, result done, a sonnet transcript: close would succeed."""
    _routed(monkeypatch)
    code, opened = _open(capsys, r, items=items)
    assert code == 0, opened
    _enrolled(r)
    if edit:
        _write(os.path.join(r.T, "a.txt"), "alpha\nbeta\n")
    _result(r)
    _transcript(r)


def _b_clean(r):
    assert _git(r.B, "status", "--porcelain") == ""
    assert _git(r.B, "diff", "--cached", "--name-only") == ""


def _forfeited(code, out, token):
    assert code == 1
    assert out["ok"] is False and out["forfeited"] is True
    assert out["reason"] == "forfeited" and out["detail"] == token
    assert out["engine"] == "native"


# --- E1 route ------------------------------------------------------------------------------


def test_route_native_when_cloud_linux_and_local_sockets(tmp_path, monkeypatch, capsys):
    # axis: mapping — native needs all three of cloud, linux and a calibration with localSockets
    r = _make_repo(tmp_path)
    _routed(monkeypatch)
    code, out = _cli(capsys, "route", "--cwd", r.B)
    assert code == 0
    assert out == {
        "ok": True, "engine": "native", "reason": "cloud-local-sockets",
        "why": "a cloud session on Linux whose calibration turns on localSockets, "
               "which the Linux sandbox cannot serve"}


@pytest.mark.parametrize("engine", ["codex", "cursor"])
def test_route_non_claude_implementer_keeps_its_engine_with_local_sockets(
        tmp_path, monkeypatch, capsys, engine):
    # axis: mapping — a cloud linux localSockets build with a non-claude implementer never routes native
    r = _make_repo(tmp_path)
    _routed(monkeypatch)
    monkeypatch.setattr(
        NE.preflight_probe, "dispatch_calibration",
        lambda cwd=None, **kw: [{"role": "implementer", "engine": engine}])
    code, out = _cli(capsys, "route", "--cwd", r.B)
    assert code == 0
    assert out == {"ok": True, "engine": engine, "reason": "calibrated"}


@pytest.mark.parametrize("remote", ["True", "1", " true", None])
def test_route_calibrated_unless_remote_is_exactly_true(tmp_path, monkeypatch, capsys, remote):
    # axis: mapping — only the exact string "true" is a cloud session
    r = _make_repo(tmp_path)
    _host(monkeypatch, remote, "linux")
    code, out = _cli(capsys, "route", "--cwd", r.B)
    assert code == 0
    assert out == {"ok": True, "engine": "claude", "reason": "calibrated"}


@pytest.mark.parametrize("platform", ["darwin", "win32", "freebsd13"])
def test_route_calibrated_off_linux(tmp_path, monkeypatch, capsys, platform):
    # axis: mapping — a host whose sandbox can serve sockets (or is not linux) never routes native
    r = _make_repo(tmp_path)
    _host(monkeypatch, "true", platform)
    code, out = _cli(capsys, "route", "--cwd", r.B)
    assert code == 0
    assert out == {"ok": True, "engine": "claude", "reason": "calibrated"}


@pytest.mark.parametrize("block", [{"localSockets": False}, {"localPorts": True}, _NO_KEY])
def test_route_calibrated_without_local_sockets(tmp_path, monkeypatch, capsys, block):
    # axis: mapping — localSockets false or absent keeps the calibrated engine
    r = _make_repo(tmp_path, block)
    _routed(monkeypatch)
    code, out = _cli(capsys, "route", "--cwd", r.B)
    assert code == 0
    assert out == {"ok": True, "engine": "claude", "reason": "calibrated"}


def test_route_calibrated_uses_the_configured_implementation_engine(tmp_path, monkeypatch, capsys):
    # axis: mapping — the calibrated engine is the owner's configured one, not a hardcoded claude
    r = _make_repo(tmp_path, prefs={"implementation": "codex", "reviewer": "claude"})
    _host(monkeypatch, None, "linux")
    code, out = _cli(capsys, "route", "--cwd", r.B)
    assert code == 0
    assert out == {"ok": True, "engine": "codex", "reason": "calibrated"}


def test_route_malformed_sandbox_access_is_a_refusal(tmp_path, monkeypatch, capsys):
    # axis: refusal — a malformed sandboxAccess never routes anywhere
    r = _make_repo(tmp_path, {"localSockets": "yes"})
    _routed(monkeypatch)
    code, out = _cli(capsys, "route", "--cwd", r.B)
    assert code == 1
    assert out == {"ok": False, "reason": "sandbox-access-malformed"}


def test_route_unreadable_sandbox_access_is_a_refusal(tmp_path, monkeypatch, capsys):
    # axis: refusal — a core.md that cannot be parsed never routes anywhere
    r = _make_repo(tmp_path)
    _routed(monkeypatch)
    corrupt = core_md._JSON_BLOCK.sub(
        lambda m: "```json superheroes-core\n{not json\n```", _core_text({}))
    _write(os.path.join(r.B, core_md.in_repo_core_rel_path()), corrupt)
    code, out = _cli(capsys, "route", "--cwd", r.B)
    assert code == 1
    assert out == {"ok": False, "reason": "sandbox-access-unreadable"}


# --- E2 open refusals ----------------------------------------------------------------------


def test_open_refuses_when_not_routed(tmp_path, monkeypatch, capsys):
    # axis: refusal — a run that does not route native never opens
    r = _make_repo(tmp_path)
    _host(monkeypatch, "true", "darwin")
    code, out = _open(capsys, r)
    assert code == 1
    assert out["ok"] is False and out["terminal"] is True
    assert out["reason"] == "native-engine-not-routed"
    assert _records(r) == []
    assert not os.path.exists(os.path.join(r.run, "agent-prompt.md"))


def test_open_refuses_a_run_dir_that_is_not_empty(tmp_path, monkeypatch, capsys):
    # axis: refusal — a reused run dir never opens
    r = _make_repo(tmp_path)
    _routed(monkeypatch)
    _write(os.path.join(r.run, "stale.txt"), "x")
    code, out = _open(capsys, r)
    assert code == 1
    assert out == {"ok": False, "terminal": True, "reason": "run-dir-not-empty"}
    assert _records(r) == []


def test_open_refuses_a_short_base_sha(tmp_path, monkeypatch, capsys):
    # axis: refusal — only a full 40-hex sha pins the base
    r = _make_repo(tmp_path)
    _routed(monkeypatch)
    code, out = _open(capsys, r, base=r.base[:12])
    assert code == 1
    assert out == {"ok": False, "terminal": True, "reason": "base-sha-invalid"}
    assert _records(r) == []


@pytest.mark.parametrize("seconds", [59, 7201])
def test_open_refuses_a_deadline_out_of_range(tmp_path, monkeypatch, capsys, seconds):
    # axis: refusal — the deadline lies between 60 and 7200 seconds
    r = _make_repo(tmp_path)
    _routed(monkeypatch)
    code, out = _open(capsys, r, deadline=seconds)
    assert code == 1
    assert out == {"ok": False, "terminal": True, "reason": "deadline-invalid"}
    assert _records(r) == []


@pytest.mark.parametrize("item", ["/abs/file.txt", "../x"])
def test_open_refuses_an_expected_item_outside_the_worktree(tmp_path, monkeypatch, capsys, item):
    # axis: refusal — a declared item is a relative path inside the worktree
    r = _make_repo(tmp_path)
    _routed(monkeypatch)
    code, out = _open(capsys, r, items=[item])
    assert code == 1
    assert out == {"ok": False, "terminal": True, "reason": "expect-item-invalid"}
    assert _records(r) == []


def test_open_refuses_a_model_off_the_allowlist(tmp_path, monkeypatch, capsys):
    # axis: refusal — the model gate's own refusal passes through and journals nothing
    r = _make_repo(tmp_path)
    _routed(monkeypatch)
    seat = '{"vendor": "claude", "model": "haiku", "effort": "high", "role": "implementer"}'
    code, out = _open(capsys, r, seat=seat)
    assert code == 1
    assert out["ok"] is False and out["terminal"] is True
    assert out["reason"] == "allowlist-refused"
    assert _records(r) == []


def test_open_refuses_a_seat_that_is_not_claude(tmp_path, monkeypatch, capsys):
    # axis: refusal — the native subagent is a claude seat; a codex seat never opens it
    r = _make_repo(tmp_path)
    _routed(monkeypatch)
    seat = '{"vendor": "codex", "model": "gpt-6.1-sol", "effort": "high", "role": "implementer"}'
    code, out = _open(capsys, r, seat=seat)
    assert code == 1
    assert out["ok"] is False and out["terminal"] is True
    assert out["reason"] == "native-seat-invalid"
    assert _records(r) == []


# --- E3 the record -------------------------------------------------------------------------


def test_open_records_the_run_and_writes_the_prompt(tmp_path, monkeypatch, capsys):
    # axis: preservation — the run-opened record, the printed agent block and the prompt file
    r = _make_repo(tmp_path)
    _routed(monkeypatch)
    code, out = _open(capsys, r, deadline=600, items=["src/new.txt"])
    run = os.path.realpath(r.run)
    assert code == 0
    assert out == {
        "ok": True, "terminal": False, "runDir": run, "deadlineAt": out["deadlineAt"],
        "agent": {"subagent_type": "superheroes:implementer", "model": "sonnet",
                  "isolation": "worktree", "run_in_background": True,
                  "promptPath": os.path.join(run, "agent-prompt.md")}}
    (rec,) = _records(r)
    assert rec["kind"] == "run-opened" and rec["engine"] == "native"
    assert rec["runKind"] == "write"
    assert rec["cwd"] == os.path.realpath(r.B)
    assert rec["baseSha"] == r.base
    assert rec["expectedItems"] == ["src/new.txt"]
    assert rec["routeReason"] == "cloud-local-sockets"
    assert rec["bounds"] == (
        "no plugin sandbox: the implementer runs as a native subagent in its own isolated "
        "worktree, bounded by the platform's auto mode and the plugin's install and network fence "
        "(a command-prefix fence, not a sandbox), because a cloud session on Linux whose "
        "calibration turns on localSockets, which the Linux sandbox cannot serve")
    assert rec["effectiveEffort"] is None
    assert rec["effortNote"] == (
        "the Agent tool takes no effort; the subagent runs at its default effort")
    assert rec["expectedServedModel"] == "claude-sonnet-5-5"
    assert rec["resolvedSeat"] == {"model_id": "sonnet-5.5", "effort": "high",
                                   "dispatchToken": "sonnet"}
    assert "claudeWriteSandbox" not in rec
    opened_at = calendar.timegm(time.strptime(rec["openedAt"], "%Y-%m-%dT%H:%M:%SZ"))
    deadline_at = calendar.timegm(time.strptime(rec["deadlineAt"], "%Y-%m-%dT%H:%M:%SZ"))
    assert rec["deadlineSeconds"] == 600
    assert deadline_at == opened_at + 600
    assert rec["deadlineAt"] == out["deadlineAt"]
    with open(os.path.join(run, "agent-prompt.md"), encoding="utf-8") as fh:
        prompt = fh.read()
    lib = os.path.dirname(os.path.abspath(NE.__file__))
    assert "python3 -B %s/native_engine.py enroll --run-dir %s" % (lib, run) in prompt
    assert prompt.endswith("# Order\nChange a.txt.\n")
    assert os.path.join(run, "result.json") in prompt
    assert prompt.index("enroll --run-dir") < prompt.index("# Order")


# --- E4 enroll -----------------------------------------------------------------------------


def _enroll(capsys, monkeypatch, r, cwd):
    monkeypatch.chdir(cwd)
    return _cli(capsys, "enroll", "--run-dir", r.run)


def test_enroll_pins_the_base_and_writes_nothing_to_the_journal(tmp_path, monkeypatch, capsys):
    # axis: preservation — a clean isolated worktree ends on the base; the journal is untouched
    r = _make_repo(tmp_path)
    _routed(monkeypatch)
    _open(capsys, r)
    before = _records(r)
    code, out = _enroll(capsys, monkeypatch, r, r.T)
    assert code == 0
    assert out == {"ok": True, "head": r.base}
    assert _git(r.T, "rev-parse", "HEAD").strip() == r.base
    assert _records(r) == before


def test_enroll_checks_out_the_base_when_head_sits_ahead(tmp_path, monkeypatch, capsys):
    # axis: mapping — a worktree cut from a descendant of the base is moved back onto the base
    r = _make_repo(tmp_path)
    _write(os.path.join(r.main, "ahead.txt"), "ahead\n")
    _git(r.main, "add", "-A")
    _git(r.main, "commit", "-q", "-m", "ahead")
    ahead = _git(r.main, "rev-parse", "HEAD").strip()
    _git(r.T, "checkout", "-q", "--detach", ahead)
    assert _git(r.T, "rev-parse", "HEAD").strip() == ahead != r.base
    _routed(monkeypatch)
    _open(capsys, r)
    code, out = _enroll(capsys, monkeypatch, r, r.T)
    assert code == 0
    assert out == {"ok": True, "head": r.base}
    assert _git(r.T, "rev-parse", "HEAD").strip() == r.base


def test_enroll_refuses_a_dirty_worktree(tmp_path, monkeypatch, capsys):
    # axis: refusal — a worktree with uncommitted files never enrolls
    r = _make_repo(tmp_path)
    _routed(monkeypatch)
    _open(capsys, r)
    _write(os.path.join(r.T, "stray.txt"), "x")
    code, out = _enroll(capsys, monkeypatch, r, r.T)
    assert code == 1
    assert out == {"ok": False, "reason": "native-worktree-dirty"}


def test_enroll_refuses_the_builders_own_worktree(tmp_path, monkeypatch, capsys):
    # axis: refusal — the subagent never runs in the run's own cwd, even a linked worktree
    r = _make_repo(tmp_path)
    _routed(monkeypatch)
    _open(capsys, r)
    code, out = _enroll(capsys, monkeypatch, r, r.B)
    assert code == 1
    assert out == {"ok": False, "reason": "native-worktree-not-isolated"}
    assert _git(r.B, "rev-parse", "HEAD").strip() == r.base


def test_enroll_refuses_the_main_checkout(tmp_path, monkeypatch, capsys):
    # axis: refusal — the main checkout is not a linked worktree
    r = _make_repo(tmp_path)
    _routed(monkeypatch)
    _open(capsys, r)
    code, out = _enroll(capsys, monkeypatch, r, r.main)
    assert code == 1
    assert out == {"ok": False, "reason": "native-worktree-not-isolated"}


def test_enroll_refuses_when_no_run_is_open(tmp_path, monkeypatch, capsys):
    # axis: refusal — a run dir with no native run never enrolls
    r = _make_repo(tmp_path)
    _routed(monkeypatch)
    os.makedirs(r.run)
    code, out = _enroll(capsys, monkeypatch, r, r.T)
    assert code == 1
    assert out == {"ok": False, "reason": "native-run-not-open"}


def test_enroll_refuses_a_closed_run(tmp_path, monkeypatch, capsys):
    # axis: refusal — a closed run never enrolls
    r = _make_repo(tmp_path)
    _routed(monkeypatch)
    _open(capsys, r)
    assert ED._journal_append(os.path.realpath(r.run), {"kind": "run-closed", "ok": False})
    code, out = _enroll(capsys, monkeypatch, r, r.T)
    assert code == 1
    assert out == {"ok": False, "reason": "native-run-not-open"}


def test_enroll_refuses_past_the_deadline(tmp_path, monkeypatch, capsys):
    # axis: refusal — an enroll after the deadline is refused
    r = _make_repo(tmp_path)
    _routed(monkeypatch)
    _open(capsys, r, deadline=60)
    monkeypatch.setattr(NE, "_now", lambda: time.time() + 3600)
    code, out = _enroll(capsys, monkeypatch, r, r.T)
    assert code == 1
    assert out == {"ok": False, "reason": "native-deadline"}


# --- E5 close checks, in order -------------------------------------------------------------


def _assert_untouched(r):
    assert "native-collecting" not in _kinds(r)
    _b_clean(r)


def test_close_forfeits_the_deadline_flag(tmp_path, monkeypatch, capsys):
    # axis: ordering — --forfeit deadline closes the run before any other check
    r = _make_repo(tmp_path)
    _ready(capsys, monkeypatch, r)
    code, out = _close(capsys, r, forfeit=True)
    _forfeited(code, out, "native-deadline")
    assert _kinds(r)[-1] == "run-closed"
    _assert_untouched(r)


def test_close_forfeits_a_run_past_its_deadline(tmp_path, monkeypatch, capsys):
    # axis: ordering — a close after deadlineAt forfeits on the clock, without the flag
    r = _make_repo(tmp_path)
    _ready(capsys, monkeypatch, r)
    monkeypatch.setattr(NE, "_now", lambda: time.time() + 10000)
    code, out = _close(capsys, r)
    _forfeited(code, out, "native-deadline")
    _assert_untouched(r)


def test_close_forfeits_a_run_nobody_enrolled(tmp_path, monkeypatch, capsys):
    # axis: ordering — with no native-enrolled record the run forfeits native-not-enrolled
    r = _make_repo(tmp_path)
    _routed(monkeypatch)
    _open(capsys, r)
    _write(os.path.join(r.T, "a.txt"), "alpha\nbeta\n")
    _result(r)
    _transcript(r)
    code, out = _close(capsys, r)
    _forfeited(code, out, "native-not-enrolled")
    _assert_untouched(r)


def test_close_forfeits_a_worktree_other_than_the_enrolled_one(tmp_path, monkeypatch, capsys):
    # axis: ordering — the closed worktree is the one the hook enrolled
    r = _make_repo(tmp_path)
    _ready(capsys, monkeypatch, r)
    code, out = _close(capsys, r, worktree=r.T2)
    _forfeited(code, out, "native-binding-mismatch")
    _assert_untouched(r)


def test_close_forfeits_a_transcript_without_the_agent_id(tmp_path, monkeypatch, capsys):
    # axis: ordering — the transcript belongs to the enrolled agent
    r = _make_repo(tmp_path)
    _ready(capsys, monkeypatch, r)
    other = _transcript(r, name=os.path.join(os.path.dirname(r.transcript), "agent-ffff.jsonl"))
    code, out = _close(capsys, r, transcript=other)
    _forfeited(code, out, "native-binding-mismatch")
    _assert_untouched(r)


def test_close_forfeits_when_the_worktree_is_the_builders(tmp_path, monkeypatch, capsys):
    # axis: ordering — T equal to B is never an isolated worktree
    r = _make_repo(tmp_path)
    _ready(capsys, monkeypatch, r)
    _re_enroll(r, r.B)
    code, out = _close(capsys, r, worktree=r.B)
    _forfeited(code, out, "native-worktree-not-isolated")
    assert "native-collecting" not in _kinds(r)


def test_close_forfeits_a_worktree_the_builder_does_not_list(tmp_path, monkeypatch, capsys):
    # axis: ordering — a directory that is not a linked worktree of B never collects
    r = _make_repo(tmp_path)
    _ready(capsys, monkeypatch, r)
    stray = os.path.join(os.path.realpath(str(tmp_path)), "stray")
    os.makedirs(stray)
    _git(stray, "init", "-q")
    _re_enroll(r, stray)
    code, out = _close(capsys, r, worktree=stray)
    _forfeited(code, out, "native-worktree-not-isolated")
    _assert_untouched(r)


def test_close_forfeits_a_head_that_does_not_contain_the_base(tmp_path, monkeypatch, capsys):
    # axis: ordering — a worktree whose HEAD is an unrelated history never collects
    r = _make_repo(tmp_path)
    _ready(capsys, monkeypatch, r)
    _git(r.T, "checkout", "-q", "--orphan", "orph")
    _git(r.T, "rm", "-rfq", ".")
    _write(os.path.join(r.T, "other.txt"), "unrelated\n")
    _git(r.T, "add", "-A")
    _git(r.T, "commit", "-q", "-m", "unrelated")
    code, out = _close(capsys, r)
    _forfeited(code, out, "native-base-mismatch")
    _assert_untouched(r)


def test_close_forfeits_a_transcript_with_no_model(tmp_path, monkeypatch, capsys):
    # axis: ordering — a transcript whose assistant records carry no model cannot prove the model
    r = _make_repo(tmp_path)
    _ready(capsys, monkeypatch, r)
    _transcript(r, models=(None, None))
    code, out = _close(capsys, r)
    _forfeited(code, out, "native-model-unread")
    assert out["servedModel"] is None
    _assert_untouched(r)


def test_close_forfeits_a_transcript_with_a_different_model(tmp_path, monkeypatch, capsys):
    # axis: ordering — one record served by another model forfeits the whole run
    r = _make_repo(tmp_path)
    _ready(capsys, monkeypatch, r)
    _transcript(r, models=(_SONNET, "claude-opus-5-5", _SONNET))
    code, out = _close(capsys, r)
    _forfeited(code, out, "native-model-mismatch")
    _assert_untouched(r)


def test_close_forfeits_a_missing_result(tmp_path, monkeypatch, capsys):
    # axis: ordering — no result.json, no collection
    r = _make_repo(tmp_path)
    _ready(capsys, monkeypatch, r)
    os.unlink(os.path.join(r.run, "result.json"))
    code, out = _close(capsys, r)
    _forfeited(code, out, "native-result-invalid")
    assert out["servedModel"] == "claude-sonnet-5-5"
    _assert_untouched(r)


@pytest.mark.parametrize("body", ["{not json", '{"status": "ok", "summary": "x"}', "[]"])
def test_close_forfeits_a_malformed_result(tmp_path, monkeypatch, capsys, body):
    # axis: ordering — bad JSON, a status outside the three, or a non-object result forfeits
    r = _make_repo(tmp_path)
    _ready(capsys, monkeypatch, r)
    _write(os.path.join(r.run, "result.json"), body)
    code, out = _close(capsys, r)
    _forfeited(code, out, "native-result-invalid")
    _assert_untouched(r)


# --- E6 status mapping ---------------------------------------------------------------------


@pytest.mark.parametrize("status", ["needs_context", "blocked"])
def test_close_status_other_than_done_collects_nothing(tmp_path, monkeypatch, capsys, status):
    # axis: mapping — needs_context and blocked are terminal, not forfeits, and apply nothing
    r = _make_repo(tmp_path)
    _ready(capsys, monkeypatch, r)
    _result(r, status=status)
    code, out = _close(capsys, r)
    assert code == 0
    assert out["ok"] is False and out["terminal"] is True
    assert out["reason"] == status
    assert out["forfeited"] is False
    assert out["engine"] == "native" and out["servedModel"] == "claude-sonnet-5-5"
    _assert_untouched(r)
    assert _kinds(r)[-1] == "run-closed"


# --- E7 grading ----------------------------------------------------------------------------


def test_close_grading_forfeits_a_missing_declared_item(tmp_path, monkeypatch, capsys):
    # axis: refusal — a declared item the subagent never delivered forfeits items-undelivered
    r = _make_repo(tmp_path)
    _ready(capsys, monkeypatch, r, items=["src/new.txt"])
    code, out = _close(capsys, r)
    _forfeited(code, out, "items-undelivered")
    assert out["itemCheck"]["missing"] == ["src/new.txt"]
    _assert_untouched(r)


def test_close_grading_forfeits_unavailable_item_evidence(tmp_path, monkeypatch, capsys):
    # axis: refusal — evidence the engine cannot read forfeits, with the cause
    r = _make_repo(tmp_path)
    _ready(capsys, monkeypatch, r, items=["a.txt"])
    monkeypatch.setattr(ED, "_item_delivery_check", lambda cwd, opened, timeout=None: {
        "evidenceUnavailable": True, "evidenceCause": "diff-timeout"})
    code, out = _close(capsys, r)
    _forfeited(code, out, "item-evidence-unavailable:diff-timeout")
    _assert_untouched(r)


def test_open_normalizes_declared_items_and_close_credits_them(tmp_path, monkeypatch, capsys):
    # axis: mapping — ./a.txt is recorded in the form git reports
    r = _make_repo(tmp_path)
    _ready(capsys, monkeypatch, r, items=["./a.txt"])
    rec = _records(r)[0]
    assert rec["kind"] == "run-opened" and rec["expectedItems"] == ["a.txt"]
    code, out = _close(capsys, r)
    assert code == 0, out
    assert out["itemCheck"]["missing"] == []


def test_close_accepts_a_declared_deletion(tmp_path, monkeypatch, capsys):
    # axis: preservation — a declared tracked file the subagent deleted is collected, not forfeited
    r = _make_repo(tmp_path)
    _ready(capsys, monkeypatch, r, items=["a.txt"], edit=False)
    os.unlink(os.path.join(r.T, "a.txt"))
    code, out = _close(capsys, r)
    assert code == 0, out
    assert out["collected"]["files"] == ["a.txt"]
    assert not os.path.exists(os.path.join(r.B, "a.txt"))


def test_close_grading_forfeits_a_declared_file_the_patch_cannot_carry(
        tmp_path, monkeypatch, capsys):
    # axis: refusal — an ignored declared file is not in the patch, so collection is incomplete
    r = _make_repo(tmp_path)
    _ready(capsys, monkeypatch, r, items=["out.log"])
    _write(os.path.join(r.T, "out.log"), "built\n")
    code, out = _close(capsys, r)
    _forfeited(code, out, "native-collect-incomplete")
    assert out["itemCheck"]["missing"] == []
    assert _git(r.B, "diff", "--cached", "--name-only").split() == ["a.txt"]
    assert "native-collecting" in _kinds(r)


# --- E8 success ----------------------------------------------------------------------------


def test_close_success_lands_the_change_in_the_builders_index(tmp_path, monkeypatch, capsys):
    # axis: preservation — open, enroll, edit, close: B's index holds exactly the subagent's change
    r = _make_repo(tmp_path)
    _routed(monkeypatch)
    code, opened = _open(capsys, r, items=["a.txt", "src/new.txt"])
    assert code == 0
    code, enrolled = _enroll(capsys, monkeypatch, r, r.T)
    assert code == 0 and enrolled["head"] == r.base
    _enrolled(r)
    _write(os.path.join(r.T, "a.txt"), "alpha\nbeta\n")
    _write(os.path.join(r.T, "src", "new.txt"), "fresh\n")
    _result(r)
    _transcript(r)
    code, out = _close(capsys, r)
    assert code == 0, out
    assert out["ok"] is True and out["terminal"] is True and out["signal"] == "ok"
    assert out["engine"] == "native"
    assert out["servedModel"] == "claude-sonnet-5-5"
    assert out["itemCheck"] == {"declared": True, "expected": 2, "delivered": 2, "missing": []}
    assert out["collected"]["files"] == ["a.txt", "src/new.txt"]
    assert len(out["collected"]["patchSha256"]) == 64
    assert out["bounds"].startswith("no plugin sandbox:")
    assert _git(r.B, "diff", "--cached", "--name-only").split() == ["a.txt", "src/new.txt"]
    for item in ("a.txt", "src/new.txt"):
        with open(os.path.join(r.B, item), "rb") as mine, open(os.path.join(r.T, item), "rb") as theirs:
            assert mine.read() == theirs.read()
    assert _git(r.B, "rev-parse", "HEAD").strip() == r.base
    assert _kinds(r) == ["run-opened", "native-enrolled", "native-collecting", "run-closed"]


# --- E9 idempotence ------------------------------------------------------------------------


def test_close_idempotent_second_close_returns_the_same_result(tmp_path, monkeypatch, capsys):
    # axis: idempotence — a second close replays the journaled result and applies nothing again
    r = _make_repo(tmp_path)
    _ready(capsys, monkeypatch, r)
    code, first = _close(capsys, r)
    assert code == 0 and first["ok"] is True
    staged = _git(r.B, "diff", "--cached")
    kinds = _kinds(r)
    code, second = _close(capsys, r)
    assert code == 0
    assert second == first
    assert _kinds(r) == kinds
    assert _git(r.B, "diff", "--cached") == staged


def test_close_idempotent_a_forfeit_replays_unchanged(tmp_path, monkeypatch, capsys):
    # axis: idempotence — a forfeited run replays its forfeit, whatever the second call asks
    r = _make_repo(tmp_path)
    _ready(capsys, monkeypatch, r)
    code, first = _close(capsys, r, forfeit=True)
    _forfeited(code, first, "native-deadline")
    code, second = _close(capsys, r)
    assert code == 1
    assert second == first


def test_close_interrupted_collection_is_not_reapplied(tmp_path, monkeypatch, capsys):
    # axis: idempotence — native-collecting with no run-closed closes interrupted, applying nothing
    r = _make_repo(tmp_path)
    _ready(capsys, monkeypatch, r)
    assert ED._journal_append(os.path.realpath(r.run), {
        "kind": "native-collecting", "patchSha256": "0" * 64, "at": "2026-10-18T00:00:00Z"})
    code, out = _close(capsys, r)
    _forfeited(code, out, "native-collect-interrupted")
    _b_clean(r)
    assert _kinds(r)[-1] == "run-closed"


def test_close_journal_write_failed_before_the_apply_leaves_b_unchanged(
        tmp_path, monkeypatch, capsys):
    # axis: refusal — when native-collecting cannot be journaled, nothing is applied
    r = _make_repo(tmp_path)
    _ready(capsys, monkeypatch, r)
    real_append = ED._journal_append

    def failing(run_dir, record):
        if record.get("kind") == "native-collecting":
            return False
        return real_append(run_dir, record)

    monkeypatch.setattr(ED, "_journal_append", failing)
    code, out = _close(capsys, r)
    assert code == 1
    assert out["ok"] is False and out["terminal"] is True
    assert out["reason"] == "journal-write-failed"
    _b_clean(r)
    assert "native-collecting" not in _kinds(r)


# --- E10 wait ------------------------------------------------------------------------------


class _Clock:
    """A clock that advances one second per sleep; counts the sleeps."""

    def __init__(self, start):
        self.now = float(start)
        self.sleeps = 0

    def sleep(self, seconds):
        self.sleeps += 1
        self.now += seconds


def _clocked(monkeypatch, start):
    clock = _Clock(start)
    monkeypatch.setattr(NE, "_now", lambda: clock.now)
    monkeypatch.setattr(NE, "_SLEEP", clock.sleep)
    return clock


def _opened_epoch(r):
    return calendar.timegm(time.strptime(_records(r)[0]["openedAt"], "%Y-%m-%dT%H:%M:%SZ"))


def test_wait_returns_when_the_result_exists(tmp_path, monkeypatch, capsys):
    # axis: bound — a present result.json ends the wait at once
    r = _make_repo(tmp_path)
    _routed(monkeypatch)
    _open(capsys, r, deadline=600)
    clock = _clocked(monkeypatch, _opened_epoch(r) + 5)
    _result(r)
    code, out = _cli(capsys, "wait", "--run-dir", r.run, "--max-wait", "540")
    assert code == 0
    assert out == {"ok": True, "resultPresent": True, "deadlinePassed": False, "secondsLeft": 595}
    assert clock.sleeps == 0


def test_wait_reports_a_passed_deadline(tmp_path, monkeypatch, capsys):
    # axis: bound — a deadline already behind the clock reports deadlinePassed
    r = _make_repo(tmp_path)
    _routed(monkeypatch)
    _open(capsys, r, deadline=60)
    _clocked(monkeypatch, _opened_epoch(r) + 500)
    code, out = _cli(capsys, "wait", "--run-dir", r.run, "--max-wait", "540")
    assert code == 0
    assert out == {"ok": True, "resultPresent": False, "deadlinePassed": True, "secondsLeft": 0}


def test_wait_never_loops_past_the_deadline(tmp_path, monkeypatch, capsys):
    # axis: bound — with no result and a long cap, the wait stops within five seconds of the deadline
    r = _make_repo(tmp_path)
    _routed(monkeypatch)
    _open(capsys, r, deadline=60)
    clock = _clocked(monkeypatch, _opened_epoch(r))
    code, out = _cli(capsys, "wait", "--run-dir", r.run, "--max-wait", "540")
    assert code == 0
    assert clock.sleeps <= 60 + 5
    assert out["resultPresent"] is False and out["deadlinePassed"] is True


def test_wait_stops_at_the_max_wait(tmp_path, monkeypatch, capsys):
    # axis: bound — the cap ends a wait whose deadline is far off
    r = _make_repo(tmp_path)
    _routed(monkeypatch)
    _open(capsys, r, deadline=3600)
    clock = _clocked(monkeypatch, _opened_epoch(r))
    code, out = _cli(capsys, "wait", "--run-dir", r.run, "--max-wait", "30")
    assert code == 0
    assert out["resultPresent"] is False and out["deadlinePassed"] is False
    assert clock.sleeps == 30
