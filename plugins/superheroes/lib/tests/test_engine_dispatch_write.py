import importlib.util
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    spec = importlib.util.spec_from_file_location(
        "engine_dispatch", os.path.join(_HERE, "..", "engine_dispatch.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ED = _load()

import file_lock as _file_lock

_EA = importlib.util.spec_from_file_location(
    "engine_adapter", os.path.join(_HERE, "..", "engine_adapter.py"))
EA = importlib.util.module_from_spec(_EA)
_EA.loader.exec_module(EA)


@pytest.fixture(autouse=True)
def _pin_temp_base_to_tmp_path(tmp_path, monkeypatch):
    base = str(tmp_path / "temp-base")
    os.makedirs(base, exist_ok=True)
    monkeypatch.setattr(ED.tempfile, "gettempdir", lambda: base)
    journal_root = str(tmp_path / "dispatch-journal-root")
    os.makedirs(journal_root, exist_ok=True)
    monkeypatch.setenv(ED.JOURNAL_ROOT_ENV, journal_root)
    yield


def _git(cwd, *args, check=True):
    return subprocess.run(
        ["git", "-C", cwd, *args], capture_output=True, text=True, check=check,
    )


def _init_repo(path):
    os.makedirs(path, exist_ok=True)
    _git(path, "init", "-q")
    readme = os.path.join(path, "README.md")
    with open(readme, "w", encoding="utf-8") as fh:
        fh.write("hello\n")
    _git(path, "add", "README.md")
    _git(path, "-c", "user.email=t@t.local", "-c", "user.name=t", "commit", "-qm", "init")
    return path


def _linked_worktree(tmp_path):
    main = str(tmp_path / "main")
    _init_repo(main)
    wt = str(tmp_path / "wt")
    _git(main, "worktree", "add", "-q", wt)
    return wt, main


def _prompt(tmp_path, content="Build this.\n"):
    p = tmp_path / "prompt.txt"
    p.write_text(content, encoding="utf-8")
    return str(p)


def _build_ok_stdout():
    body = json.dumps({
        "ok": True, "signal": "ok",
        "evidence": {"testFailed": False, "testPassed": True},
    })
    return "Receipt prose.\n" + EA.WRITE_REPORT_SENTINEL + "\n" + body


def _honest_refusal_stdout():
    body = json.dumps({
        "ok": False, "signal": "plan_wrong",
        "evidence": {"testFailed": True, "testPassed": False},
    })
    return "Stopped per order.\n" + EA.WRITE_REPORT_SENTINEL + "\n" + body


def _legacy_build_ok_stdout():
    return json.dumps({"ok": True, "signal": "ok", "evidence": {"testFailed": False, "testPassed": True}})


def _contracted_fed_prompt(base):
    if base and not base.endswith("\n"):
        return base + "\n" + EA.WRITE_REPORT_CONTRACT
    return base + EA.WRITE_REPORT_CONTRACT


class FakeRunner:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, argv, prompt_bytes, timeout, progress_cb, cwd):
        self.calls.append({
            "argv": list(argv),
            "prompt_bytes": prompt_bytes,
            "timeout": timeout,
            "cwd": cwd,
        })
        idx = len(self.calls) - 1
        if idx >= len(self.responses):
            raise AssertionError("fake called too many times")
        return self.responses[idx]


_NO_CWD = object()


def _dispatch_write(tmp_path, fake, *, cwd=_NO_CWD, run_dir=None, engine="codex", **kwargs):
    if cwd is _NO_CWD:
        cwd, _main = _linked_worktree(tmp_path)
    if run_dir is None:
        run_dir = str(tmp_path / "run")
    defaults = {
        "model": "sonnet",
        "effort": "high",
        "cwd": cwd,
        "run_dir": run_dir,
        "order_id": "order-1",
        "run_engine": fake,
    }
    if "prompt_path" not in kwargs:
        defaults["prompt_path"] = _prompt(tmp_path)
    defaults.update(kwargs)
    return ED.dispatch_write(engine, **defaults)


# --- cwd validation refusals ---------------------------------------------------


@pytest.mark.parametrize("cwd,detail", [
    (None, "cwd-absent"),
    ("   ", "cwd-absent"),
    ("missing", "cwd-missing"),
])
def test_validate_linked_build_cwd_absent_missing(tmp_path, cwd, detail):
    if cwd == "missing":
        cwd = str(tmp_path / "no-such")
    fake = FakeRunner([])
    res = _dispatch_write(tmp_path, fake, cwd=cwd)
    assert res["detail"] == detail
    assert res["attempts"] == 0
    assert len(fake.calls) == 0


def test_validate_linked_build_cwd_not_a_directory(tmp_path):
    f = tmp_path / "file"
    f.write_text("x", encoding="utf-8")
    fake = FakeRunner([])
    res = _dispatch_write(tmp_path, fake, cwd=str(f))
    assert res["detail"] == "cwd-not-a-directory"
    assert res["attempts"] == 0


def test_validate_linked_build_cwd_not_a_repo(tmp_path):
    bare = tmp_path / "bare"
    bare.mkdir()
    fake = FakeRunner([])
    res = _dispatch_write(tmp_path, fake, cwd=str(bare))
    assert res["detail"] == "cwd-not-a-repo"
    assert res["attempts"] == 0


def test_validate_linked_build_cwd_not_linked_worktree(tmp_path, monkeypatch):
    d = tmp_path / "fake"
    d.mkdir()
    (d / ".git").mkdir()

    def fake_git(cwd, *args, timeout=None):
        if args == ("rev-parse", "--show-toplevel"):
            return subprocess.CompletedProcess(args, 0, str(d) + "\n", "")
        if args == ("rev-parse", "--git-dir"):
            return subprocess.CompletedProcess(args, 0, "/gitdir-a\n", "")
        if args == ("rev-parse", "--git-common-dir"):
            return subprocess.CompletedProcess(args, 0, "/gitdir-b\n", "")
        return subprocess.CompletedProcess(args, 1, "", "")

    monkeypatch.setattr(ED, "_git_scrubbed", fake_git)
    ok, detail = ED._validate_linked_build_cwd(str(d))
    assert not ok
    assert detail == "cwd-not-a-linked-worktree"


def test_validate_linked_build_cwd_primary_checkout(tmp_path):
    _wt, main = _linked_worktree(tmp_path)
    fake = FakeRunner([])
    res = _dispatch_write(tmp_path, fake, cwd=main)
    assert res["detail"] == "cwd-primary-checkout"
    assert res["attempts"] == 0


def test_validate_linked_build_cwd_not_worktree_root(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    sub = os.path.join(wt, "sub")
    os.makedirs(sub)
    fake = FakeRunner([])
    res = _dispatch_write(tmp_path, fake, cwd=sub)
    assert res["detail"] == "cwd-not-worktree-root"
    assert res["attempts"] == 0


def test_validate_linked_build_cwd_not_registered(tmp_path):
    wt, main = _linked_worktree(tmp_path)
    orphan = str(tmp_path / "orphan")
    os.makedirs(orphan)
    gitfile = os.path.join(wt, ".git")
    with open(gitfile, encoding="utf-8") as fh:
        content = fh.read()
    with open(os.path.join(orphan, ".git"), "w", encoding="utf-8") as fh:
        fh.write(content)
    fake = FakeRunner([])
    res = _dispatch_write(tmp_path, fake, cwd=orphan)
    assert res["detail"] == "cwd-not-registered"
    assert res["attempts"] == 0


def test_validate_linked_build_cwd_git_preflight_timeout(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)

    def slow_git(cwd, *args, timeout=None):
        raise subprocess.TimeoutExpired(cmd="git", timeout=timeout or 0)

    monkeypatch.setattr(ED, "_git_scrubbed", slow_git)
    fake = FakeRunner([])
    res = _dispatch_write(tmp_path, fake, cwd=wt)
    assert res["detail"] == "git-preflight-timeout"
    assert res["attempts"] == 0


def test_run_dir_inside_cwd_refused(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir = os.path.join(wt, "dispatch-run")
    os.makedirs(run_dir)
    fake = FakeRunner([])
    res = _dispatch_write(tmp_path, fake, cwd=wt, run_dir=run_dir)
    assert res["detail"] == "run-dir-inside-cwd"
    assert res["attempts"] == 0


def test_worktree_lease_held_no_spawn(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    lease_path = ED._worktree_lease_path(os.path.realpath(wt))
    os.makedirs(os.path.dirname(lease_path), exist_ok=True)
    import file_lock
    file_lock.acquire(lease_path)
    try:
        fake = FakeRunner([])
        res = _dispatch_write(tmp_path, fake, cwd=wt, run_dir=str(tmp_path / "run-a"))
        assert res["detail"] == "worktree-lease-held"
        assert res["attempts"] == 0
        assert len(fake.calls) == 0
        assert os.path.exists(lease_path)
    finally:
        file_lock.release(lease_path)


def test_lease_journal_append_failed_releases(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)
    lease_path = ED._worktree_lease_path(os.path.realpath(wt))
    real_append = ED._journal_append

    def fail_lease_acquire(run_dir_real, record):
        if record.get("kind") == "lease-acquired":
            return False
        return real_append(run_dir_real, record)

    monkeypatch.setattr(ED, "_journal_append", fail_lease_acquire)
    fake = FakeRunner([])
    res = _dispatch_write(tmp_path, fake, cwd=wt)
    assert res["detail"] == "journal-append-failed"
    assert res["attempts"] == 0
    assert not os.path.exists(lease_path)


def test_resume_cwd_authorization_mismatch(tmp_path):
    wt1, main = _linked_worktree(tmp_path)
    wt2 = str(tmp_path / "wt2")
    _git(main, "worktree", "add", "-q", wt2)
    run_dir = str(tmp_path / "run")
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    _dispatch_write(tmp_path, fake, cwd=wt1, run_dir=run_dir)
    res = _dispatch_write(tmp_path, fake, cwd=wt2, run_dir=run_dir, order_id="order-1")
    assert res["detail"] == "cwd-authorization-mismatch"
    assert res["attempts"] == 0


def test_resume_order_id_mismatch(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir = str(tmp_path / "run")
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    _dispatch_write(tmp_path, fake, cwd=wt, run_dir=run_dir, order_id="order-1")
    res = _dispatch_write(tmp_path, fake, cwd=wt, run_dir=run_dir, order_id="order-2")
    assert res["detail"] == "run-dir-reused"
    assert res["attempts"] == 0


def test_run_kind_mismatch_both_directions(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    baseline = ED._worktree_baseline(os.path.realpath(wt))
    built = EA.build_argv_result("codex", "build", "high", {"model": "sonnet", "cwd": os.path.realpath(wt)})
    ED._acquire_worktree_lease(os.path.realpath(wt), run_dir)
    ED._open_write_run(
        run_dir, engine="codex", argv=built["argv"], cwd=os.path.realpath(wt),
        timeout=ED.RETRY_MIN_TIMEOUT, retry_timeout=ED.RETRY_MIN_TIMEOUT,
        prompt_path=_prompt(tmp_path), order_id="order-1", base_sha="abc",
        worktree_baseline=baseline, progress_path=os.path.join(run_dir, "progress.jsonl"),
    )
    res = ED._supervise(
        run_dir, run_kind=ED.RUN_KIND_REVIEW, deadline=time.monotonic() + 5,
    )
    assert res["detail"] == "run-kind-mismatch"
    assert res["attempts"] == 0
    run_dir2 = str(tmp_path / "run2")
    os.makedirs(run_dir2, exist_ok=True)
    ED._journal_append(run_dir2, {
        "kind": "run-opened", "runKind": ED.RUN_KIND_REVIEW, "engine": "codex",
        "roleKind": "review", "orderId": "x", "argv": ["codex"], "cwd": os.path.realpath(wt),
        "timeout": 60, "retryTimeout": 60,
        "promptPath": os.path.join(run_dir2, "prompt.txt"),
        "viewPath": None, "baseSha": "abc", "supervisorPid": 1, "at": time.time(),
    })
    res2 = ED._supervise(
        run_dir2, run_kind=ED.RUN_KIND_WRITE, deadline=time.monotonic() + 5,
    )
    assert res2["detail"] == "run-kind-mismatch"
    assert res2["attempts"] == 0


def test_honest_refusal_terminal_not_retried(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    fake = FakeRunner([
        (_honest_refusal_stdout(), False, 0, ""),
        (_build_ok_stdout(), False, 0, ""),
    ])
    res = _dispatch_write(tmp_path, fake, cwd=wt)
    assert res["ok"] is False
    assert res["terminal"] is True
    assert res["forfeited"] is False
    assert res["reason"] == "plan_wrong"
    assert res["attempts"] == 1
    assert len(fake.calls) == 1


def test_lease_not_released_when_token_mismatch(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir = str(tmp_path / "run")
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    res = _dispatch_write(tmp_path, fake, cwd=wt, run_dir=run_dir)
    assert res["ok"] is True
    lease_path = ED._worktree_lease_path(os.path.realpath(wt))
    assert not os.path.exists(lease_path)
    import file_lock
    file_lock.acquire(lease_path)
    holder = file_lock.read_holder(lease_path)
    holder["dispatchToken"] = "wrong-token"
    with open(lease_path, "w", encoding="utf-8") as fh:
        json.dump(holder, fh)
    state = {"opened": {"runKind": ED.RUN_KIND_WRITE, "cwd": os.path.realpath(wt)},
             "leaseToken": "our-token"}
    ED._release_worktree_lease(state)
    assert os.path.exists(lease_path)
    file_lock.release(lease_path)


def test_dispatch_write_never_raises(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)

    def boom(*_a, **_k):
        raise ValueError("boom")

    monkeypatch.setattr(ED, "_validate_linked_build_cwd", boom)
    res = ED.dispatch_write(
        "codex", model="sonnet", effort="high", prompt_path=_prompt(tmp_path),
        cwd=wt, run_dir=str(tmp_path / "run"),
    )
    assert res["detail"] == "internal-ValueError"
    assert res["attempts"] == 0
    assert res["terminal"] is True


def test_supervise_exception_releases_lease(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)
    run_dir = str(tmp_path / "run")
    lease_path = ED._worktree_lease_path(os.path.realpath(wt))

    def boom(*_a, **_k):
        raise RuntimeError("supervise-boom")

    monkeypatch.setattr(ED, "_supervise", boom)
    fake = FakeRunner([])
    res = _dispatch_write(tmp_path, fake, cwd=wt, run_dir=run_dir)
    assert res["detail"] == "internal-RuntimeError"
    assert not os.path.exists(lease_path)


def test_lease_blocks_second_run_dir_same_cwd(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    fake1 = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    run_a = str(tmp_path / "run-a")
    res_a = _dispatch_write(tmp_path, fake1, cwd=wt, run_dir=run_a, max_wait=0)
    assert res_a.get("reason") in ("running", None) or res_a.get("terminal") is False or res_a["ok"]
    lease_path = ED._worktree_lease_path(os.path.realpath(wt))
    assert os.path.exists(lease_path)
    fake2 = FakeRunner([])
    res_b = _dispatch_write(tmp_path, fake2, cwd=wt, run_dir=str(tmp_path / "run-b"))
    assert res_b["detail"] == "worktree-lease-held"
    assert res_b["attempts"] == 0
    ED.dispatch_abandon(run_a)


def test_spawn_blocked_by_live_engine_pgroup(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        start_new_session=True,
    )
    try:
        ED._journal_append(run_dir, {
            "kind": "run-opened", "runKind": ED.RUN_KIND_WRITE, "engine": "codex",
            "roleKind": "build", "orderId": "x", "argv": ["codex"], "cwd": os.path.realpath(wt),
            "timeout": 60, "retryTimeout": 60,
            "promptPath": os.path.join(run_dir, "prompt.txt"),
            "viewPath": None, "baseSha": "abc", "supervisorPid": 1, "at": time.time(),
        })
        ED._journal_append(run_dir, {
            "kind": "attempt-started", "attempt": 1, "childPid": 999999, "at": time.time(),
        })
        ED._journal_append(run_dir, {
            "kind": "engine-started", "attempt": 1, "enginePgid": proc.pid, "at": time.time(),
        })
        state = ED._journal_state(ED._journal_read(run_dir)[0])
        ok, detail = ED._spawn_attempt(run_dir, state, 2)
        assert not ok
        assert detail == "attempt-already-live:engine-pgroup"
    finally:
        ED._terminate_process_group(proc.pid)
        try:
            proc.wait(timeout=2)
        except Exception:
            pass


def test_malformed_lease_reclaim(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    lease_path = ED._worktree_lease_path(os.path.realpath(wt))
    os.makedirs(os.path.dirname(lease_path), exist_ok=True)
    with open(lease_path, "wb"):
        pass
    old = time.time() - _file_lock.MALFORMED_GRACE_SECONDS - 5
    os.utime(lease_path, (old, old))
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    res = _dispatch_write(tmp_path, fake, cwd=wt)
    assert res["ok"] is True
    records, _ = ED._journal_read(str(tmp_path / "run"))
    reclaimed = [r for r in records if r.get("kind") == "lease-reclaimed"]
    assert len(reclaimed) == 1
    assert reclaimed[0].get("reason") == "malformed-holder"


def test_boot_id_mismatch_lease_reclaim_journal_reason(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)
    lease_path = ED._worktree_lease_path(os.path.realpath(wt))
    os.makedirs(os.path.dirname(lease_path), exist_ok=True)
    monkeypatch.setattr(_file_lock.hostinfo, "boot_id", lambda: "boot-A")
    with open(lease_path, "w", encoding="utf-8") as fh:
        json.dump({
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "acquiredAt": "1970-01-01T00:00:00Z",
            "bootId": "boot-OLD",
        }, fh)
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    res = _dispatch_write(tmp_path, fake, cwd=wt)
    assert res["ok"] is True
    records, _ = ED._journal_read(str(tmp_path / "run"))
    reclaimed = [r for r in records if r.get("kind") == "lease-reclaimed"]
    assert len(reclaimed) == 1
    assert reclaimed[0].get("reason") == "boot-id-mismatch"


def test_expired_dead_holder_lease_reclaim_journal_reason(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    lease_path = ED._worktree_lease_path(os.path.realpath(wt))
    os.makedirs(os.path.dirname(lease_path), exist_ok=True)
    with open(lease_path, "w", encoding="utf-8") as fh:
        json.dump({
            "pid": 99999999,
            "host": socket.gethostname(),
            "acquiredAt": "1970-01-01T00:00:00Z",
            "bootId": None,
        }, fh)
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    res = _dispatch_write(tmp_path, fake, cwd=wt)
    assert res["ok"] is True
    records, _ = ED._journal_read(str(tmp_path / "run"))
    reclaimed = [r for r in records if r.get("kind") == "lease-reclaimed"]
    assert len(reclaimed) == 1
    assert reclaimed[0].get("reason") == "expired-dead-holder"


def test_worktree_dirtied_refuses_retry(tmp_path):
    wt, _main = _linked_worktree(tmp_path)

    class DirtyTimeoutRunner:
        def __call__(self, argv, prompt_bytes, timeout, progress_cb, cwd):
            with open(os.path.join(cwd, "dirty.txt"), "w", encoding="utf-8") as fh:
                fh.write("x")
            return "", True, 0, ""

    fake = DirtyTimeoutRunner()
    res = _dispatch_write(tmp_path, fake, cwd=wt, max_wait=120)
    assert res["terminal"] is True
    assert res["detail"] == "worktree-dirtied-by-attempt"
    assert res["forfeited"] is True
    assert res["attempts"] == 1


# --- WO-B: write report recovery ---------------------------------------------


def _install_write_salvage(monkeypatch, recover):
    monkeypatch.setattr(ED.engine_adapter, "salvage_write_report", recover, raising=False)


def _write_report(*, ok=True):
    return {
        "report": {
            "ok": ok,
            "signal": "ok" if ok else "tests_failed",
            "evidence": {"testFailed": not ok, "testPassed": ok},
        },
        "structured": True,
        "requiresManualRead": False,
        "salvaged": True,
    }


def _prose_write_report():
    return {
        "report": None,
        "structured": False,
        "requiresManualRead": True,
        "excerpt": "scrubbed prose pointer",
        "excerptBytes": 22,
        "salvaged": True,
        "truncated": False,
    }


def test_write_forfeit_attaches_salvage_without_upgrading_outcome(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)
    calls = []

    def recover(engine, role_kind, stdout, fed_prompt):
        if stdout == "unrecoverable":
            return None
        calls.append((engine, role_kind, stdout, fed_prompt))
        return _write_report()

    _install_write_salvage(monkeypatch, recover)
    res = _dispatch_write(tmp_path, FakeRunner([
        ("unrecoverable", True, 0, ""),
        (_build_ok_stdout(), True, 0, ""),
    ]), cwd=wt)

    assert res["ok"] is False
    assert res["terminal"] is True
    assert res["forfeited"] is True
    assert res["reason"] == ED.dispatch_outcome.REASON_FORFEITED
    assert res["salvage"] == {
        "attempt": 2,
        "stdoutPath": os.path.join(str(tmp_path / "run"), "attempt-2.stdout"),
        **_write_report(),
    }
    assert "still a forfeit" in res["disclosure"]
    assert "independently verified" in res["disclosure"]
    assert calls == [("codex", "build", _build_ok_stdout(), _contracted_fed_prompt("Build this.\n"))]


def test_write_run_opened_records_fed_prompt(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    prompt_text = "Implement exactly the assigned work order.\n"
    prompt_path = _prompt(tmp_path, prompt_text)
    res = _dispatch_write(
        tmp_path,
        FakeRunner([(_build_ok_stdout(), False, 0, "")]),
        cwd=wt,
        prompt_path=prompt_path,
    )

    assert res["ok"] is True
    records, _ = ED._journal_read(str(tmp_path / "run"))
    opened = next(record for record in records if record.get("kind") == "run-opened")
    assert opened["fedPrompt"] == _contracted_fed_prompt(prompt_text)


def test_write_salvage_uses_latest_report_and_records_earlier_attempt(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)

    def recover(_engine, _role_kind, stdout, _fed_prompt):
        return _write_report(ok=stdout == "second report") if stdout in {"first report", "second report"} else None

    _install_write_salvage(monkeypatch, recover)
    res = _dispatch_write(tmp_path, FakeRunner([
        ("first report", True, 0, ""),
        ("second report", True, 0, ""),
    ]), cwd=wt)

    assert res["forfeited"] is True
    assert res["salvage"]["attempt"] == 2
    assert res["salvage"]["alsoRecovered"] == [{
        "attempt": 1,
        "stdoutPath": os.path.join(str(tmp_path / "run"), "attempt-1.stdout"),
    }]


def test_write_salvage_prefers_structured_report_over_later_prose(tmp_path, monkeypatch):
    # axis: C4 structure must beat recency; prose remains visible in alsoRecovered.
    wt, _main = _linked_worktree(tmp_path)

    def recover(_engine, _role_kind, stdout, _fed_prompt):
        if stdout == "structured report":
            return _write_report()
        if stdout == "prose report":
            return _prose_write_report()
        return None

    _install_write_salvage(monkeypatch, recover)
    res = _dispatch_write(tmp_path, FakeRunner([
        ("structured report", True, 0, ""),
        ("prose report", True, 0, ""),
    ]), cwd=wt)

    assert res["salvage"]["attempt"] == 1
    assert res["salvage"]["structured"] is True
    assert res["salvage"]["alsoRecovered"] == [{
        "attempt": 2,
        "stdoutPath": os.path.join(str(tmp_path / "run"), "attempt-2.stdout"),
    }]


def test_write_salvage_prose_survives_ledger_scrubbing(tmp_path):
    salvage = _prose_write_report()
    # Deliberate fake token fixture; it must never resemble a real credential leak.
    fake_token = "ghp_EXAMPLEfakenotarealtoken000000000"
    salvage["excerpt"] = "token %s" % fake_token
    row = ED._build_ledger_row(str(tmp_path), {"opened": {}, "attempts": {}}, {
        "ok": False,
        "salvage": salvage,
    })
    assert row["salvage"]["report"] is None
    assert row["salvage"]["structured"] is False
    assert row["salvage"]["requiresManualRead"] is True
    assert "[REDACTED]" in row["salvage"]["excerpt"]
    assert fake_token not in row["salvage"]["excerpt"]


def test_write_dirty_tree_forfeit_attaches_salvage(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)

    class DirtyTimeoutRunner:
        def __call__(self, argv, prompt_bytes, timeout, progress_cb, cwd):
            with open(os.path.join(cwd, "dirty.txt"), "w", encoding="utf-8") as fh:
                fh.write("x")
            return _build_ok_stdout(), True, 0, ""

    _install_write_salvage(monkeypatch, lambda *_args: _write_report())
    res = _dispatch_write(tmp_path, DirtyTimeoutRunner(), cwd=wt, max_wait=120)

    assert res["detail"] == "worktree-dirtied-by-attempt"
    assert res["forfeited"] is True
    assert res["salvage"]["attempt"] == 1
    assert "report was not gradeable" in res["disclosure"]


def test_write_salvage_scan_exception_leaves_terminal_forfeit_unchanged(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)

    def boom(*_args):
        raise RuntimeError("salvage boom")

    _install_write_salvage(monkeypatch, boom)
    res = _dispatch_write(tmp_path, FakeRunner([
        (_build_ok_stdout(), True, 0, ""),
        (_build_ok_stdout(), True, 0, ""),
    ]), cwd=wt)

    assert res["forfeited"] is True
    assert "salvage" not in res


def test_write_salvage_marks_ledger_engaged_but_not_delivered(tmp_path):
    result = {"ok": False, "salvage": {"report": _write_report()["report"]}}
    stages = ED._ledger_stages(
        result,
        {"attempts": {}},
        str(tmp_path),
        {"runKind": ED.RUN_KIND_WRITE},
    )

    assert stages == {"engaged": True, "delivered": False}


def test_write_forfeit_without_salvage_leaves_ledger_unengaged(tmp_path):
    stages = ED._ledger_stages(
        {"ok": False},
        {"attempts": {}},
        str(tmp_path),
        {"runKind": ED.RUN_KIND_WRITE},
    )

    assert stages == {"engaged": None, "delivered": False}


def test_write_success_terminal(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    res = _dispatch_write(tmp_path, fake, cwd=wt)
    assert res["ok"] is True
    assert res["terminal"] is True
    assert res["signal"] == "ok"
    assert res["attempts"] == 1
    assert res["evidence"]["testPassed"] is True


def test_write_argv_shape_codex(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)
    cwd_real = os.path.realpath(wt)
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    res = _dispatch_write(tmp_path, fake, cwd=wt, engine="codex", effort="high", model="sonnet")
    assert res["ok"] is True
    argv = fake.calls[0]["argv"]
    built = EA.build_argv_result("codex", "build", "high", {"model": "sonnet", "cwd": cwd_real})
    assert argv == built["argv"]
    assert argv == [
        "codex", "exec", "--sandbox", "workspace-write", "-m", argv[5],
        "-c", "model_reasoning_effort=high", "-C", cwd_real, "-",
    ]
    assert "read-only" not in argv
    review_built = EA.build_argv_result("codex", "review", "high", {"model": "sonnet", "cwd": cwd_real})
    assert review_built["argv"] != argv
    assert "read-only" in review_built["argv"]

    real_build = ED.engine_adapter.build_argv_result

    def neutralized(engine, role_kind, effort, opts):
        if role_kind == "build":
            role_kind = "review"
        return real_build(engine, role_kind, effort, opts)

    monkeypatch.setattr(ED.engine_adapter, "build_argv_result", neutralized)
    fake2 = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    _dispatch_write(tmp_path, fake2, cwd=wt, run_dir=str(tmp_path / "run2"))
    bad_argv = fake2.calls[0]["argv"]
    with pytest.raises(AssertionError):
        assert bad_argv == [
            "codex", "exec", "--sandbox", "workspace-write", "-m", bad_argv[5],
            "-c", "model_reasoning_effort=high", "-C", cwd_real, "-",
        ]


def test_write_argv_shape_cursor(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    res = _dispatch_write(
        tmp_path, fake, cwd=wt, engine="cursor",
        engine_model="composer-2.5", effort=None, model=None,
    )
    assert res["ok"] is True
    argv = fake.calls[0]["argv"]
    assert argv == [
        "cursor-agent", "--model", "composer-2.5", "-p", "--trust", "-f",
        "--output-format", "stream-json",
    ]
    built = EA.build_argv_result(
        "cursor", "build", None, {"engine_model": "composer-2.5", "cwd": os.path.realpath(wt)},
    )
    assert argv == built["argv"]
    assert argv[0] == "cursor-agent"
    assert "-f" in argv
    assert "--mode" not in argv
    review_built = EA.build_argv_result("cursor", "review", None, {"engine_model": "composer-2.5"})
    assert "-f" not in review_built["argv"]
    assert "--mode" in review_built["argv"]


def test_dispatch_write_codex_effort_none_refuses_no_lease(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    lease_path = ED._worktree_lease_path(os.path.realpath(wt))
    fake = FakeRunner([])
    res = _dispatch_write(tmp_path, fake, cwd=wt, engine="codex", effort=None)
    assert res["ok"] is False
    assert res["terminal"] is True
    assert res["reason"] == "unrunnable"
    assert res["detail"] == "engine-config:invalid-model-effort"
    assert res["attempts"] == 0
    assert len(fake.calls) == 0
    assert not os.path.exists(lease_path)


def test_dispatch_write_cursor_grok_effort_none_refuses(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    fake = FakeRunner([])
    res = _dispatch_write(
        tmp_path, fake, cwd=wt, engine="cursor",
        engine_model="cursor-grok-4.5", effort=None, model=None,
    )
    assert res["ok"] is False
    assert res["terminal"] is True
    assert res["reason"] == "unrunnable"
    assert res["detail"] == "engine-config:invalid-model-effort"
    assert res["attempts"] == 0
    assert len(fake.calls) == 0
    built = EA.build_argv_result(
        "cursor", "build", None, {"engine_model": "cursor-grok-4.5", "cwd": os.path.realpath(wt)},
    )
    assert built["reason"] == "invalid-model-effort"


def test_dispatch_write_cli_effort_optional(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir = str(tmp_path / "run")
    prompt = _prompt(tmp_path)
    argv = [
        "dispatch-write",
        "--engine", "cursor",
        "--engine-model", "composer-2.5",
        "--prompt-path", prompt,
        "--cwd", wt,
        "--run-dir", run_dir,
        "--max-wait", "0",
    ]
    code = ED.main(argv)
    assert code == 0


# --- process-group liveness + abandon confirmation -----------------------------


def test_process_group_alive_zombie_only_is_dead():
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        start_new_session=True,
    )
    pgid = proc.pid
    ED._terminate_process_group(pgid)
    try:
        assert not ED._process_group_alive(pgid)
    finally:
        proc.wait(timeout=2)


def test_process_group_alive_live_member():
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        start_new_session=True,
    )
    try:
        assert ED._process_group_alive(proc.pid)
    finally:
        ED._terminate_process_group(proc.pid)
        proc.wait(timeout=2)


def test_process_group_alive_ps_probe_fail_closed(monkeypatch):
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        start_new_session=True,
    )
    try:
        def boom(*_a, **_k):
            raise OSError("ps unavailable")

        monkeypatch.setattr(ED.subprocess, "run", boom)
        assert ED._process_group_alive(proc.pid) is True
    finally:
        ED._terminate_process_group(proc.pid)
        proc.wait(timeout=2)


def test_process_group_alive_none_and_zero_never_killpg_zero(monkeypatch):
    calls = []
    real_killpg = os.killpg

    def track(pgid, sig):
        calls.append((pgid, sig))
        return real_killpg(pgid, sig)

    monkeypatch.setattr(os, "killpg", track)
    assert ED._process_group_alive(None) is False
    assert ED._process_group_alive(0) is False
    assert all(c[0] != 0 for c in calls)


def test_dispatch_abandon_alive_engine_releases_lease(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        start_new_session=True,
    )
    try:
        ED._acquire_worktree_lease(os.path.realpath(wt), run_dir)
        ED._journal_append(run_dir, {
            "kind": "run-opened", "runKind": ED.RUN_KIND_WRITE, "engine": "codex",
            "roleKind": "build", "orderId": "abandon-test", "argv": ["codex"],
            "cwd": os.path.realpath(wt), "timeout": 60, "retryTimeout": 60,
            "promptPath": os.path.join(run_dir, "prompt.txt"),
            "viewPath": None, "baseSha": "abc", "supervisorPid": 1, "at": time.time(),
        })
        ED._journal_append(run_dir, {
            "kind": "attempt-started", "attempt": 1, "childPid": proc.pid, "at": time.time(),
        })
        ED._journal_append(run_dir, {
            "kind": "engine-started", "attempt": 1, "enginePgid": proc.pid, "at": time.time(),
        })
        lease_path = ED._worktree_lease_path(os.path.realpath(wt))
        assert os.path.exists(lease_path)
        res = ED.dispatch_abandon(run_dir)
        assert res["detail"] == "run-abandoned"
        assert not os.path.exists(lease_path)
        records, _ = ED._journal_read(run_dir)
        assert records[-1]["kind"] == "run-abandoned"
    finally:
        ED._terminate_process_group(proc.pid)
        try:
            proc.wait(timeout=2)
        except Exception:
            pass


# --- WO F1 1b/1c/2c/2d: write-path seams ---------------------------------------


def test_write_blocking_supervise_loop_bounded_under_held_lock(tmp_path, monkeypatch):
    import threading
    import file_lock

    wt, _main = _linked_worktree(tmp_path)
    run_dir = str(tmp_path / "run")
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    _dispatch_write(tmp_path, fake, cwd=wt, run_dir=run_dir, max_wait=1)
    lock_path = os.path.join(run_dir, ED.RUN_LOCK_NAME)
    file_lock.acquire(lock_path)
    try:
        calls = {"n": 0}
        real_supervise = ED._supervise

        def counting_supervise(*args, **kwargs):
            calls["n"] += 1
            return real_supervise(*args, **kwargs)

        monkeypatch.setattr(ED, "_supervise", counting_supervise)
        monkeypatch.setattr(ED, "SUPERVISOR_POLL_INTERVAL", 0.05)

        def run_dispatch():
            _dispatch_write(tmp_path, FakeRunner([]), cwd=wt, run_dir=run_dir, max_wait=None)

        t = threading.Thread(target=run_dispatch, daemon=True)
        t.start()
        time.sleep(0.3)
        assert calls["n"] <= 8
    finally:
        file_lock.release(lock_path)


def test_write_git_preflight_bounded_by_max_wait(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)

    def slow_validate(cwd, timeout=None):
        time.sleep(2)
        return False, "git-preflight-timeout"

    monkeypatch.setattr(ED, "_validate_linked_build_cwd", slow_validate)
    fake = FakeRunner([])
    res = _dispatch_write(tmp_path, fake, cwd=wt, max_wait=1)
    assert res["detail"] == "git-preflight-timeout"
    assert res["attempts"] == 0
    assert len(fake.calls) == 0


def test_lease_not_reclaimed_when_engine_pgroup_alive(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    lease_path = ED._worktree_lease_path(os.path.realpath(wt))
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        start_new_session=True,
    )
    try:
        import file_lock
        file_lock.acquire(lease_path)
        holder = file_lock.read_holder(lease_path)
        holder["enginePgid"] = proc.pid
        holder["dispatchToken"] = "stale-token"
        holder["pid"] = 999999
        holder["acquiredAt"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime(time.time() - file_lock.DEFAULT_TTL - 60),
        )
        with open(lease_path, "w", encoding="utf-8") as fh:
            json.dump(holder, fh)
        assert file_lock.is_stale(lease_path)
        fake = FakeRunner([])
        res = _dispatch_write(tmp_path, fake, cwd=wt, run_dir=str(tmp_path / "run-b"))
        assert res["detail"] == "worktree-lease-held"
        assert res["attempts"] == 0
    finally:
        file_lock.release(lease_path)
        ED._terminate_process_group(proc.pid)
        try:
            proc.wait(timeout=2)
        except Exception:
            pass


def test_engine_started_append_failure_terminates_engine(tmp_path, monkeypatch):
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    prompt_path = os.path.join(run_dir, "prompt.txt")
    open(prompt_path, "w").write("go\n")
    stdout_path = os.path.join(run_dir, "attempt-1.stdout")
    stderr_path = os.path.join(run_dir, "attempt-1.stderr")
    ED._journal_append(run_dir, {
        "kind": "run-opened", "runKind": ED.RUN_KIND_WRITE, "engine": "codex",
        "roleKind": "build", "orderId": "x", "argv": [sys.executable, "-c", "import time; time.sleep(120)"],
        "cwd": run_dir, "timeout": 30, "retryTimeout": 30,
        "promptPath": prompt_path, "viewPath": None, "baseSha": "abc",
        "supervisorPid": 1, "at": time.time(),
    })
    ED._journal_append(run_dir, {
        "kind": "engine-launching", "attempt": 1, "childPid": 1, "at": time.time(),
    })
    real_append = ED._journal_append

    def fail_engine_started(rd, record):
        if record.get("kind") == "engine-started":
            return False
        return real_append(rd, record)

    monkeypatch.setattr(ED, "_journal_append", fail_engine_started)
    ED._run_engine_files(
        run_dir, 1, [sys.executable, "-c", "import time; time.sleep(120)"], run_dir,
        prompt_path, stdout_path, stderr_path, 30, os.path.join(run_dir, "progress.jsonl"),
    )
    records, _ = ED._journal_read(run_dir)
    ended = [r for r in records if r.get("kind") == "attempt-ended"]
    assert ended
    assert ended[-1].get("refusal") == "journal-append-failed"
    assert not any(r.get("kind") == "engine-started" for r in records)


# --- #862: --max-wait boundary on the write path -------------------------------
# axis: refusal vs clamp on the slice bound — an out-of-range value opens no run directory,
# takes no worktree lease, and spawns nothing.


@pytest.mark.parametrize("value", [ED.MAX_SYNC_WAIT + 1, 900, -1])
def test_write_out_of_range_max_wait_refuses_before_anything_opens(tmp_path, value):
    wt, _main = _linked_worktree(tmp_path)
    run_dir = str(tmp_path / "run")
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    res = _dispatch_write(tmp_path, fake, cwd=wt, run_dir=run_dir, max_wait=value)
    assert res["ok"] is False
    assert res["terminal"] is True
    assert res["reason"] == "unrunnable"
    assert res["detail"] == "max-wait-out-of-range:%d:allowed=0..%d" % (value, ED.MAX_SYNC_WAIT)
    assert res["attempts"] == 0
    assert fake.calls == []
    assert not os.path.exists(run_dir), "a refused slice must not open a run directory"
    assert not os.path.exists(ED._worktree_lease_path(os.path.realpath(wt))), (
        "a refused slice must not take the worktree lease")


def test_write_non_integer_max_wait_refuses(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    res = _dispatch_write(tmp_path, fake, cwd=wt, max_wait="540")
    assert res["detail"] == ED.MAX_WAIT_REFUSAL_TYPE
    assert res["terminal"] is True
    assert fake.calls == []


@pytest.mark.parametrize("value", [0, 3, ED.MAX_SYNC_WAIT])
def test_write_in_range_max_wait_is_honored_not_clamped(tmp_path, monkeypatch, value):
    wt, _main = _linked_worktree(tmp_path)
    seen = {}

    def fake_supervise(run_dir_real, *, run_kind, deadline, run_engine=None):
        seen["slice"] = deadline - time.monotonic()
        return ED._with_run_fields(
            {"ok": False, "terminal": False, "reason": "running", "detail": "captured",
             "attempts": 0, "forfeited": False},
            run_dir=run_dir_real, argv=[],
        )

    monkeypatch.setattr(ED, "_supervise", fake_supervise)
    res = _dispatch_write(tmp_path, FakeRunner([]), cwd=wt, max_wait=value)
    assert res["terminal"] is False
    assert abs(seen["slice"] - value) < 1.0, (
        "requested %s s slice, supervisor got %.1f s" % (value, seen["slice"]))


def test_write_cli_out_of_range_max_wait_prints_named_refusal(tmp_path, capsys):
    wt, _main = _linked_worktree(tmp_path)
    run_dir = str(tmp_path / "run")
    argv = [
        "dispatch-write",
        "--engine", "cursor",
        "--engine-model", "composer-2.5",
        "--prompt-path", _prompt(tmp_path),
        "--cwd", wt,
        "--run-dir", run_dir,
        "--max-wait", str(ED.MAX_SYNC_WAIT + 1),
    ]
    assert ED.main(argv) == 0
    res = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert res["ok"] is False
    assert res["terminal"] is True
    assert res["detail"] == "max-wait-out-of-range:%d:allowed=0..%d" % (
        ED.MAX_SYNC_WAIT + 1, ED.MAX_SYNC_WAIT)
    assert not os.path.exists(run_dir)


# --- WO-1 (#907): open-time declared-item contract -----------------------------


@pytest.mark.parametrize("raw,token", [
    (None, "expected-item-empty"),
    ("", "expected-item-empty"),
    ("   ", "expected-item-empty"),
    (123, "expected-item-empty"),
    ("foo\\bar", "expected-item-backslash"),
    ("/abs/path", "expected-item-absolute"),
    ("dir/", "expected-item-directory"),
    (".", "expected-item-escapes-worktree"),
    ("..", "expected-item-escapes-worktree"),
    ("../escape", "expected-item-escapes-worktree"),
    ("foo/..", "expected-item-escapes-worktree"),
])
def test_normalize_expected_item_refusals(raw, token):
    ok, detail = ED._normalize_expected_item(raw)
    assert not ok
    assert detail == token


@pytest.mark.parametrize("raw,expected", [
    ("foo/bar", "foo/bar"),
    ("./foo", "foo"),
    ("foo//bar", "foo/bar"),
    ("README.md", "README.md"),
    ("CaseSensitive.MD", "CaseSensitive.MD"),
])
def test_normalize_expected_item_accepts(raw, expected):
    ok, detail = ED._normalize_expected_item(raw)
    assert ok
    assert detail == expected


def test_read_expected_items_undeclared():
    ok, items = ED._read_expected_items(None, None)
    assert ok
    assert items is None


def test_read_expected_items_union_dedup_sort(tmp_path):
    items_file = tmp_path / "items.txt"
    items_file.write_text("# comment\n\nfoo/bar\n  baz \n", encoding="utf-8")
    ok, items = ED._read_expected_items(["foo/bar", "alpha"], str(items_file))
    assert ok
    assert items == ["alpha", "baz", "foo/bar"]


def test_read_expected_items_file_unreadable(tmp_path):
    ok, detail = ED._read_expected_items(None, str(tmp_path / "missing.txt"))
    assert not ok
    assert detail == "expected-items-file-unreadable"


@pytest.mark.parametrize("base_sha,ok", [
    (None, True),
    ("a" * 40, True),
    ("a" * 64, True),
    ("not-a-sha", False),
    ("A" * 40, False),
    ("abc", False),
])
def test_validate_base_sha(base_sha, ok):
    result_ok, detail = ED._validate_base_sha(base_sha)
    assert result_ok is ok
    if not ok:
        assert detail == "base-sha-not-an-object-id"
    elif base_sha is not None:
        assert detail == base_sha


def test_baseline_dirty_map_clean_worktree(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    dirty = ED._baseline_dirty_map(os.path.realpath(wt), ["any.txt"])
    assert dirty == {}


def test_baseline_dirty_map_tracks_dirty_and_absent(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    wt_real = os.path.realpath(wt)
    dirty_path = os.path.join(wt, "dirty.txt")
    with open(dirty_path, "w", encoding="utf-8") as fh:
        fh.write("changed\n")
    deleted = os.path.join(wt, "gone.txt")
    with open(deleted, "w", encoding="utf-8") as fh:
        fh.write("bye\n")
    _git(wt, "add", "gone.txt")
    os.remove(deleted)
    declared = ["dirty.txt", "gone.txt"]
    dirty = ED._baseline_dirty_map(wt_real, declared)
    assert "dirty.txt" in dirty
    assert dirty["dirty.txt"] == hashlib.sha256(b"changed\n").hexdigest()
    assert dirty["gone.txt"] == "<absent>"


def test_baseline_dirty_map_rename_consumes_both_paths(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    wt_real = os.path.realpath(wt)
    old = os.path.join(wt, "old-name.txt")
    with open(old, "w", encoding="utf-8") as fh:
        fh.write("rename-me\n")
    _git(wt, "add", "old-name.txt")
    _git(wt, "-c", "user.email=t@t.local", "-c", "user.name=t", "commit", "-qm", "add old")
    _git(wt, "mv", "old-name.txt", "new-name.txt")
    declared = ["new-name.txt", "old-name.txt"]
    dirty = ED._baseline_dirty_map(wt_real, declared)
    assert "new-name.txt" in dirty
    assert "old-name.txt" in dirty


def test_baseline_dirty_map_git_failure_returns_none(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)

    def fail_git(cwd, *args, timeout=None):
        return subprocess.CompletedProcess(args, 1, "", "err")

    monkeypatch.setattr(ED, "_git_scrubbed", fail_git)
    assert ED._baseline_dirty_map(os.path.realpath(wt), ["a.txt"]) is None


def test_write_open_persists_expected_items_and_baseline(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    wt_real = os.path.realpath(wt)
    dirty_path = os.path.join(wt, "track.txt")
    with open(dirty_path, "w", encoding="utf-8") as fh:
        fh.write("x\n")

    class DeliverExpectedRunner:
        def __call__(self, argv, prompt_bytes, timeout, progress_cb, cwd):
            with open(os.path.join(cwd, "track.txt"), "w", encoding="utf-8") as fh:
                fh.write("y\n")
            return _build_ok_stdout(), False, 0, ""

    res = _dispatch_write(
        tmp_path, DeliverExpectedRunner(), cwd=wt,
        expected_items=["track.txt"],
    )
    assert res["ok"] is True
    records, _ = ED._journal_read(str(tmp_path / "run"))
    opened = next(r for r in records if r.get("kind") == "run-opened")
    assert opened["expectedItems"] == ["track.txt"]
    assert isinstance(opened["baselineDirty"], dict)
    assert opened["baselineDirty"]["track.txt"] == hashlib.sha256(b"x\n").hexdigest()


def test_write_undeclared_expected_items_none_in_journal(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    res = _dispatch_write(tmp_path, fake, cwd=wt)
    assert res["ok"] is True
    assert "itemCheck" not in res
    records, _ = ED._journal_read(str(tmp_path / "run"))
    opened = next(r for r in records if r.get("kind") == "run-opened")
    assert opened["expectedItems"] is None
    assert opened["baselineDirty"] is None


def test_write_invalid_base_sha_refuses_before_open(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    fake = FakeRunner([])
    res = _dispatch_write(tmp_path, fake, cwd=wt, base_sha="not-valid")
    assert res["detail"] == "base-sha-not-an-object-id"
    assert res["attempts"] == 0
    assert fake.calls == []


def test_write_malformed_expected_item_refuses_before_open(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    fake = FakeRunner([])
    res = _dispatch_write(tmp_path, fake, cwd=wt, expected_items=["/abs"])
    assert res["detail"] == "expected-item-absolute"
    assert res["attempts"] == 0
    assert fake.calls == []


def test_write_unreadable_expect_items_file_refuses(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    fake = FakeRunner([])
    res = _dispatch_write(
        tmp_path, fake, cwd=wt,
        expected_items_file=str(tmp_path / "missing-items.txt"),
    )
    assert res["detail"] == "expected-items-file-unreadable"
    assert res["attempts"] == 0


def test_write_baseline_capture_failed_refuses(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)
    monkeypatch.setattr(ED, "_baseline_dirty_map", lambda *_a, **_k: None)
    fake = FakeRunner([])
    res = _dispatch_write(tmp_path, fake, cwd=wt, expected_items=["a.txt"])
    assert res["detail"] == "baseline-capture-failed"
    assert res["attempts"] == 0
    assert fake.calls == []


def test_write_resume_expected_items_mismatch(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir = str(tmp_path / "run")
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    _dispatch_write(tmp_path, fake, cwd=wt, run_dir=run_dir, expected_items=["a.txt"], max_wait=0)
    res = _dispatch_write(
        tmp_path, FakeRunner([]), cwd=wt, run_dir=run_dir,
        expected_items=["b.txt"], max_wait=0,
    )
    assert res["detail"] == "expected-items-mismatch"
    assert res["attempts"] == 0


def test_write_resume_omitted_expected_items_inherit(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir = str(tmp_path / "run")
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    first = _dispatch_write(
        tmp_path, fake, cwd=wt, run_dir=run_dir,
        expected_items=["keep.txt"], max_wait=0,
    )
    assert first.get("terminal") is False
    res = _dispatch_write(
        tmp_path, FakeRunner([(_build_ok_stdout(), False, 0, "")]),
        cwd=wt, run_dir=run_dir, max_wait=120,
    )
    assert res["ok"] is False
    assert res["detail"] == ED.ITEM_DETAIL_UNDELIVERED
    assert res["itemCheck"]["missing"] == ["keep.txt"]
    records, _ = ED._journal_read(run_dir)
    opened = next(r for r in records if r.get("kind") == "run-opened")
    assert opened["expectedItems"] == ["keep.txt"]


def test_write_terminal_folded_returns_stored_before_expectation_check(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)
    run_dir = str(tmp_path / "run")
    fake = FakeRunner([(_honest_refusal_stdout(), False, 0, "")])
    first = _dispatch_write(tmp_path, fake, cwd=wt, run_dir=run_dir, expected_items=["a.txt"])
    assert first["terminal"] is True
    assert "itemCheck" not in first
    res = _dispatch_write(
        tmp_path, FakeRunner([]), cwd=wt, run_dir=run_dir,
        expected_items=["different.txt"],
    )
    assert res["reason"] == "plan_wrong"
    assert res.get("detail") != "expected-items-mismatch"
    assert "itemCheck" not in res


def test_write_cli_expect_item_and_file(tmp_path, capsys):
    wt, _main = _linked_worktree(tmp_path)
    run_dir = str(tmp_path / "run")
    items_file = tmp_path / "items.txt"
    items_file.write_text("from-file.txt\n", encoding="utf-8")
    argv = [
        "dispatch-write",
        "--engine", "cursor",
        "--engine-model", "composer-2.5",
        "--prompt-path", _prompt(tmp_path),
        "--cwd", wt,
        "--run-dir", run_dir,
        "--max-wait", "0",
        "--expect-item", "cli-item.txt",
        "--expect-items-file", str(items_file),
    ]
    assert ED.main(argv) == 0
    records, _ = ED._journal_read(run_dir)
    opened = next(r for r in records if r.get("kind") == "run-opened")
    assert opened["expectedItems"] == ["cli-item.txt", "from-file.txt"]


# --- WO-2 (#907): collection-time declared-item delivery check -----------------


def test_write_undeclared_skips_baseline_capture(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)
    calls = []

    def track(cwd_real, timeout=None):
        calls.append(cwd_real)
        return {}

    monkeypatch.setattr(ED, "_baseline_dirty_map", track)
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    res = _dispatch_write(tmp_path, fake, cwd=wt)
    assert res["ok"] is True
    assert "itemCheck" not in res
    assert calls == []


def test_write_all_delivered_ok_with_item_check(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    target = os.path.join(wt, "delivered.txt")

    class DeliverRunner:
        def __call__(self, argv, prompt_bytes, timeout, progress_cb, cwd):
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("done\n")
            return _build_ok_stdout(), False, 0, ""

    res = _dispatch_write(
        tmp_path, DeliverRunner(), cwd=wt,
        expected_items=["delivered.txt"],
    )
    assert res["ok"] is True
    assert res["itemCheck"] == {
        "declared": True,
        "expected": 1,
        "delivered": 1,
        "missing": [],
    }


def test_write_missing_item_forfeits(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    res = _dispatch_write(
        tmp_path, fake, cwd=wt,
        expected_items=["missing.txt", "also-missing.txt"],
    )
    assert res["ok"] is False
    assert res["terminal"] is True
    assert res["forfeited"] is True
    assert res["reason"] == ED.dispatch_outcome.REASON_FORFEITED
    assert res["detail"] == "items-undelivered"
    assert res["itemCheck"]["missing"] == ["also-missing.txt", "missing.txt"]
    assert res["itemCheck"]["delivered"] == 0
    assert res["itemCheck"]["expected"] == 2


def test_write_pre_dirty_unchanged_not_credited(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    dirty_path = os.path.join(wt, "pre-dirty.txt")
    with open(dirty_path, "w", encoding="utf-8") as fh:
        fh.write("unchanged\n")
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    res = _dispatch_write(
        tmp_path, fake, cwd=wt,
        expected_items=["pre-dirty.txt"],
    )
    assert res["ok"] is False
    assert res["detail"] == "items-undelivered"
    assert res["itemCheck"]["missing"] == ["pre-dirty.txt"]


def test_write_rename_contributes_both_paths(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    old = os.path.join(wt, "old-name.txt")
    with open(old, "w", encoding="utf-8") as fh:
        fh.write("rename-me\n")
    _git(wt, "add", "old-name.txt")
    _git(wt, "-c", "user.email=t@t.local", "-c", "user.name=t", "commit", "-qm", "add old")
    base_sha = _git(wt, "rev-parse", "HEAD").stdout.strip()

    class RenameRunner:
        def __call__(self, argv, prompt_bytes, timeout, progress_cb, cwd):
            _git(cwd, "mv", "old-name.txt", "new-name.txt")
            return _build_ok_stdout(), False, 0, ""

    res = _dispatch_write(
        tmp_path, RenameRunner(), cwd=wt,
        base_sha=base_sha,
        expected_items=["old-name.txt", "new-name.txt"],
    )
    assert res["ok"] is True
    assert res["itemCheck"]["delivered"] == 2
    assert res["itemCheck"]["missing"] == []


def test_write_item_evidence_unavailable_forfeits(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)

    def fail_delivered(*_a, **_k):
        return ED.ITEM_EVIDENCE_CAUSE_DIFF_FAILED

    monkeypatch.setattr(ED, "_delivered_paths", fail_delivered)
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    res = _dispatch_write(
        tmp_path, fake, cwd=wt,
        expected_items=["a.txt"],
    )
    assert res["ok"] is False
    assert res["forfeited"] is True
    assert res["detail"] == "%s:%s" % (
        ED.ITEM_DETAIL_EVIDENCE_UNAVAILABLE, ED.ITEM_EVIDENCE_CAUSE_DIFF_FAILED,
    )
    assert "itemCheck" not in res
    assert "not an engine forfeit" in res["disclosure"]


def test_write_item_evidence_timeout_forfeits(tmp_path, monkeypatch):
    wt, _main = _linked_worktree(tmp_path)
    real_git = ED._git_scrubbed

    def timeout_on_evidence_git(cwd, *args, timeout=None):
        if args[:3] == ("diff", "--name-status", "-z"):
            raise subprocess.TimeoutExpired(cmd="git", timeout=timeout or 0)
        return real_git(cwd, *args, timeout=timeout)

    monkeypatch.setattr(ED, "_git_scrubbed", timeout_on_evidence_git)
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    res = _dispatch_write(
        tmp_path, fake, cwd=wt,
        expected_items=["a.txt"],
    )
    assert res["ok"] is False
    assert res["forfeited"] is True
    assert res["detail"] == "%s:%s" % (
        ED.ITEM_DETAIL_EVIDENCE_UNAVAILABLE, ED.ITEM_EVIDENCE_CAUSE_DIFF_TIMEOUT,
    )
    assert "itemCheck" not in res


def test_write_forfeit_paths_carry_no_item_check(tmp_path):
    wt, _main = _linked_worktree(tmp_path)

    class DirtyTimeoutRunner:
        def __call__(self, argv, prompt_bytes, timeout, progress_cb, cwd):
            with open(os.path.join(cwd, "dirty.txt"), "w", encoding="utf-8") as fh:
                fh.write("x")
            return "", True, 0, ""

    res = _dispatch_write(
        tmp_path, DirtyTimeoutRunner(), cwd=wt,
        expected_items=["should-not-appear.txt"], max_wait=120,
    )
    assert res["detail"] == "worktree-dirtied-by-attempt"
    assert res["forfeited"] is True
    assert "itemCheck" not in res


def test_delivered_paths_union_committed_and_working_tree(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    wt_real = os.path.realpath(wt)
    head = _git(wt, "rev-parse", "HEAD").stdout.strip()
    staged = os.path.join(wt, "staged.txt")
    with open(staged, "w", encoding="utf-8") as fh:
        fh.write("staged\n")
    _git(wt, "add", "staged.txt")
    _git(wt, "-c", "user.email=t@t.local", "-c", "user.name=t", "commit", "-qm", "add staged")
    unstaged = os.path.join(wt, "unstaged.txt")
    with open(unstaged, "w", encoding="utf-8") as fh:
        fh.write("unstaged\n")
    paths = ED._delivered_paths(wt_real, head)
    assert isinstance(paths, set)
    assert "staged.txt" in paths
    assert "unstaged.txt" in paths


_DISPATCH_MECHANICS = os.path.join(
    _HERE, "..", "..", "skills", "workhorse", "reference", "dispatch-mechanics.md",
)


def test_dispatch_mechanics_names_item_check_constants():
    """axis: itemCheck detail tokens and field names are named in dispatch-mechanics.md."""
    with open(_DISPATCH_MECHANICS, encoding="utf-8") as fh:
        doc = fh.read()

    item_check_match = re.search(r"`itemCheck`\s*\(([^)]+)\)", doc)
    assert item_check_match, "itemCheck field list not found in dispatch-mechanics.md"
    doc_fields = frozenset(re.findall(r"`([^`]+)`", item_check_match.group(1)))
    assert doc_fields == ED.ITEM_CHECK_FIELDS, (
        "itemCheck field list mismatch: doc=%s code=%s"
        % (sorted(doc_fields), sorted(ED.ITEM_CHECK_FIELDS))
    )

    tokens_start = doc.find("Terminal detail tokens:")
    assert tokens_start != -1, "Terminal detail tokens section not found"
    tokens_end = doc.find("\n\n", tokens_start)
    tokens_span = doc[tokens_start:tokens_end]
    assert "`%s`" % ED.ITEM_DETAIL_UNDELIVERED in tokens_span
    assert "`%s`" % ED.ITEM_DETAIL_REPORT_MISSING_ITEMS_DELIVERED in tokens_span
    assert "`%s:<cause>`" % ED.ITEM_DETAIL_EVIDENCE_UNAVAILABLE in tokens_span

    causes_start = doc.find("causes include", tokens_start)
    assert causes_start != -1, "item-evidence-unavailable causes list not found"
    causes_end = doc.find(").", causes_start)
    causes_span = doc[causes_start:causes_end]
    doc_causes = frozenset(re.findall(r"`([^`]+)`", causes_span))
    expected_causes = frozenset({
        ED.ITEM_EVIDENCE_CAUSE_FALSY_BASE,
        ED.ITEM_EVIDENCE_CAUSE_DIFF_TIMEOUT,
        ED.ITEM_EVIDENCE_CAUSE_DIFF_FAILED,
        ED.ITEM_EVIDENCE_CAUSE_STATUS_TIMEOUT,
        ED.ITEM_EVIDENCE_CAUSE_STATUS_FAILED,
    })
    assert doc_causes == expected_causes, (
        "item-evidence causes mismatch: doc=%s code=%s"
        % (sorted(doc_causes), sorted(expected_causes))
    )

    assert "`%s`" % ED.BASE_SHA_UNRESOLVABLE in doc

    sentinel_match = re.search(
        r"sentinel line \(`([^`]+)`\)", doc,
    )
    assert sentinel_match, "write-report sentinel not found in dispatch-mechanics.md"
    assert sentinel_match.group(1) == EA.WRITE_REPORT_SENTINEL, (
        "dispatch-mechanics.md sentinel drift from engine_adapter.WRITE_REPORT_SENTINEL"
    )


def test_read_expected_items_non_utf8_file(tmp_path):
    bad = tmp_path / "bad-items.txt"
    bad.write_bytes(b"\xff\xfe")
    ok, detail = ED._read_expected_items(None, str(bad))
    assert not ok
    assert detail == "expected-items-file-unreadable"


def test_write_base_sha_unresolvable_refuses_before_spawn(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    fake = FakeRunner([])
    res = _dispatch_write(
        tmp_path, fake, cwd=wt,
        base_sha="a" * 40,
        expected_items=["missing.txt"],
    )
    assert res["detail"] == ED.BASE_SHA_UNRESOLVABLE
    assert res["attempts"] == 0
    assert fake.calls == []


def test_write_baseline_dirty_scoped_to_declared_paths(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    declared_path = os.path.join(wt, "declared-dirty.txt")
    with open(declared_path, "w", encoding="utf-8") as fh:
        fh.write("declared\n")
    undeclared_path = os.path.join(wt, "undeclared-dirty.txt")
    with open(undeclared_path, "w", encoding="utf-8") as fh:
        fh.write("undeclared\n")
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    res = _dispatch_write(
        tmp_path, fake, cwd=wt,
        expected_items=["declared-dirty.txt"],
        max_wait=0,
    )
    assert res.get("terminal") is False
    records, _ = ED._journal_read(str(tmp_path / "run"))
    opened = next(r for r in records if r.get("kind") == "run-opened")
    baseline = opened["baselineDirty"]
    assert "declared-dirty.txt" in baseline
    assert "undeclared-dirty.txt" not in baseline
    assert set(baseline.keys()) == {"declared-dirty.txt"}


def test_write_undeclared_unresolvable_base_sha_proceeds_declared_refuses(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    unresolvable = "a" * 40
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    undeclared = _dispatch_write(tmp_path, fake, cwd=wt, base_sha=unresolvable)
    assert undeclared["ok"] is True
    assert undeclared.get("detail") != ED.BASE_SHA_UNRESOLVABLE
    assert undeclared["attempts"] == 1
    declared_fake = FakeRunner([])
    declared = _dispatch_write(
        tmp_path, declared_fake, cwd=wt,
        run_dir=str(tmp_path / "run-declared"),
        base_sha=unresolvable,
        expected_items=["missing.txt"],
    )
    assert declared["detail"] == ED.BASE_SHA_UNRESOLVABLE
    assert declared["attempts"] == 0
    assert declared_fake.calls == []


def test_write_untracked_dir_file_delivered(tmp_path):
    wt, _main = _linked_worktree(tmp_path)

    class DeliverRunner:
        def __call__(self, argv, prompt_bytes, timeout, progress_cb, cwd):
            target_dir = os.path.join(cwd, "newdir")
            os.makedirs(target_dir)
            with open(os.path.join(target_dir, "file.txt"), "w", encoding="utf-8") as fh:
                fh.write("new\n")
            return _build_ok_stdout(), False, 0, ""

    res = _dispatch_write(
        tmp_path, DeliverRunner(), cwd=wt,
        expected_items=["newdir/file.txt"],
    )
    assert res["ok"] is True
    assert res["itemCheck"]["missing"] == []


def test_write_gitignored_declared_path_delivered(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    gitignore = os.path.join(wt, ".gitignore")
    with open(gitignore, "w", encoding="utf-8") as fh:
        fh.write("docs/\n")
    _git(wt, "add", ".gitignore")
    _git(wt, "-c", "user.email=t@t.local", "-c", "user.name=t", "commit", "-qm", "ignore docs")

    class DeliverRunner:
        def __call__(self, argv, prompt_bytes, timeout, progress_cb, cwd):
            docs = os.path.join(cwd, "docs")
            os.makedirs(docs, exist_ok=True)
            with open(os.path.join(docs, "spec.md"), "w", encoding="utf-8") as fh:
                fh.write("spec\n")
            return _build_ok_stdout(), False, 0, ""

    res = _dispatch_write(
        tmp_path, DeliverRunner(), cwd=wt,
        expected_items=["docs/spec.md"],
    )
    assert res["ok"] is True
    assert res["itemCheck"]["missing"] == []


def test_delivered_paths_committed_rename(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    wt_real = os.path.realpath(wt)
    old = os.path.join(wt, "old-name.txt")
    with open(old, "w", encoding="utf-8") as fh:
        fh.write("x\n")
    _git(wt, "add", "old-name.txt")
    _git(wt, "-c", "user.email=t@t.local", "-c", "user.name=t", "commit", "-qm", "add old")
    base = _git(wt, "rev-parse", "HEAD").stdout.strip()
    _git(wt, "mv", "old-name.txt", "new-name.txt")
    _git(wt, "-c", "user.email=t@t.local", "-c", "user.name=t", "commit", "-qm", "rename")
    paths = ED._delivered_paths(wt_real, base)
    assert isinstance(paths, set)
    assert "old-name.txt" in paths
    assert "new-name.txt" in paths


def test_write_committed_then_reverted_not_credited(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    base = _git(wt, "rev-parse", "HEAD").stdout.strip()

    class CommitThenRevertRunner:
        def __call__(self, argv, prompt_bytes, timeout, progress_cb, cwd):
            reverted = os.path.join(cwd, "reverted.txt")
            with open(reverted, "w", encoding="utf-8") as fh:
                fh.write("temp\n")
            _git(cwd, "add", "reverted.txt")
            _git(cwd, "-c", "user.email=t@t.local", "-c", "user.name=t", "commit", "-qm", "add temp")
            os.remove(reverted)
            return _build_ok_stdout(), False, 0, ""

    res = _dispatch_write(
        tmp_path, CommitThenRevertRunner(), cwd=wt,
        base_sha=base,
        expected_items=["reverted.txt"],
    )
    assert res["detail"] == ED.ITEM_DETAIL_UNDELIVERED
    assert "reverted.txt" in res["itemCheck"]["missing"]


def test_write_folded_malformed_expectation_returns_stored_terminal(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir = str(tmp_path / "run")
    fake = FakeRunner([(_honest_refusal_stdout(), False, 0, "")])
    first = _dispatch_write(tmp_path, fake, cwd=wt, run_dir=run_dir, expected_items=["a.txt"])
    assert first["terminal"] is True
    res = _dispatch_write(
        tmp_path, FakeRunner([]), cwd=wt, run_dir=run_dir,
        expected_items=["/abs/path"],
    )
    assert res["reason"] == "plan_wrong"
    assert res.get("detail") != "expected-item-absolute"


def test_baseline_dirty_map_fifo_and_symlink(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    wt_real = os.path.realpath(wt)
    fifo = os.path.join(wt, "pipe.fifo")
    os.mkfifo(fifo)
    symlink = os.path.join(wt, "link.txt")
    os.symlink("README.md", symlink)
    assert ED._path_content_identity(wt_real, "pipe.fifo") == "<absent>"
    dirty = ED._baseline_dirty_map(wt_real, ["link.txt", "pipe.fifo"])
    assert dirty["link.txt"] == "<absent>"


def test_baseline_dirty_map_pathspec_magic_literal_filename(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    wt_real = os.path.realpath(wt)
    magic_name = ":(literal)foo"
    magic_path = os.path.join(wt, magic_name)
    with open(magic_path, "w", encoding="utf-8") as fh:
        fh.write("magic\n")
    dirty = ED._baseline_dirty_map(wt_real, [magic_name])
    assert magic_name in dirty
    assert dirty[magic_name] == hashlib.sha256(b"magic\n").hexdigest()


def test_write_pathspec_magic_pre_dirty_unchanged_not_credited(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    magic_name = ":(weird)name.txt"
    magic_path = os.path.join(wt, magic_name)
    with open(magic_path, "w", encoding="utf-8") as fh:
        fh.write("unchanged\n")
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    res = _dispatch_write(
        tmp_path, fake, cwd=wt,
        expected_items=[magic_name],
    )
    assert res["ok"] is False
    assert res["detail"] == "items-undelivered"
    assert res["itemCheck"]["missing"] == [magic_name]


def test_write_expected_items_too_many_refuses_before_spawn(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    fake = FakeRunner([])
    too_many = ["item-%04d.txt" % i for i in range(ED.MAX_EXPECTED_ITEMS + 1)]
    res = _dispatch_write(tmp_path, fake, cwd=wt, expected_items=too_many)
    assert res["reason"] == "unrunnable"
    assert res["detail"] == "expected-items-too-many"
    assert res["attempts"] == 0
    assert res["forfeited"] is False
    assert fake.calls == []


@pytest.mark.parametrize("cause,neutralize", [
    (ED.ITEM_EVIDENCE_CAUSE_FALSY_BASE, lambda *_a, **_k: ED.ITEM_EVIDENCE_CAUSE_FALSY_BASE),
    (ED.ITEM_EVIDENCE_CAUSE_DIFF_TIMEOUT, "diff-timeout"),
    (ED.ITEM_EVIDENCE_CAUSE_DIFF_FAILED, "diff-failed"),
    (ED.ITEM_EVIDENCE_CAUSE_STATUS_TIMEOUT, "status-timeout"),
    (ED.ITEM_EVIDENCE_CAUSE_STATUS_FAILED, "status-failed"),
])
def test_write_item_evidence_cause_forfeits(tmp_path, monkeypatch, cause, neutralize):
    wt, _main = _linked_worktree(tmp_path)
    if callable(neutralize):
        monkeypatch.setattr(ED, "_delivered_paths", neutralize)
    else:
        real_git = ED._git_scrubbed
        status_calls = {"n": 0}

        def fail_git(cwd, *args, timeout=None):
            if neutralize == "diff-timeout" and args[:3] == ("diff", "--name-status", "-z"):
                raise subprocess.TimeoutExpired(cmd="git", timeout=timeout or 0)
            if neutralize == "diff-failed" and args[:3] == ("diff", "--name-status", "-z"):
                return subprocess.CompletedProcess(args, 1, "", "err")
            if args and args[0] == "status":
                status_calls["n"] += 1
                if neutralize == "status-timeout" and status_calls["n"] > 1:
                    raise subprocess.TimeoutExpired(cmd="git", timeout=timeout or 0)
                if neutralize == "status-failed" and status_calls["n"] > 1:
                    return subprocess.CompletedProcess(args, 1, "", "err")
            return real_git(cwd, *args, timeout=timeout)

        monkeypatch.setattr(ED, "_git_scrubbed", fail_git)

    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    res = _dispatch_write(tmp_path, fake, cwd=wt, expected_items=["a.txt"])
    assert res["detail"] == "%s:%s" % (ED.ITEM_DETAIL_EVIDENCE_UNAVAILABLE, cause)
    assert "itemCheck" not in res


# --- WO-2 (#907): write-report contract wiring + report-missing classifier ----------


def test_write_open_contracts_prompt_once_to_journal_file_and_engine(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    base = "Implement exactly the assigned work order.\n"
    prompt_path = _prompt(tmp_path, base)
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    res = _dispatch_write(tmp_path, fake, cwd=wt, prompt_path=prompt_path)
    assert res["ok"] is True
    expected = _contracted_fed_prompt(base)
    run_dir = str(tmp_path / "run")
    records, _ = ED._journal_read(run_dir)
    opened = next(r for r in records if r.get("kind") == "run-opened")
    assert opened["fedPrompt"] == expected
    assert expected.endswith(EA.WRITE_REPORT_CONTRACT)
    assert base in opened["fedPrompt"]
    with open(os.path.join(run_dir, ED.PROMPT_NAME), encoding="utf-8") as fh:
        assert fh.read() == expected
    assert fake.calls[0]["prompt_bytes"] == expected.encode("utf-8")


def test_write_contracted_report_success_end_to_end(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    target = os.path.join(wt, "delivered.txt")

    class DeliverAndReportRunner:
        def __call__(self, argv, prompt_bytes, timeout, progress_cb, cwd):
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("done\n")
            return _build_ok_stdout(), False, 0, ""

    res = _dispatch_write(
        tmp_path, DeliverAndReportRunner(), cwd=wt,
        expected_items=["delivered.txt"],
    )
    assert res["ok"] is True
    assert res["terminal"] is True
    assert res["signal"] == "ok"
    assert res["itemCheck"]["missing"] == []


def _report_missing_base_state(tmp_path, wt, *, expected_items=None, fed_prompt=None,
                               deliver_expected_items=True):
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    wt_real = os.path.realpath(wt)
    baseline = ED._worktree_baseline(wt_real)
    base_prompt = "Build this.\n"
    if fed_prompt is None:
        fed_prompt = _contracted_fed_prompt(base_prompt)
    opened = {
        "runKind": ED.RUN_KIND_WRITE,
        "engine": "codex",
        "roleKind": "build",
        "cwd": wt_real,
        "fedPrompt": fed_prompt,
        "baseSha": _git(wt, "rev-parse", "HEAD").stdout.strip(),
        "expectedItems": expected_items,
        "baselineDirty": {},
    }
    if expected_items:
        opened["baselineDirty"] = ED._baseline_dirty_map(wt_real, expected_items) or {}
        if deliver_expected_items:
            for item in expected_items:
                target = os.path.join(wt_real, item)
                parent = os.path.dirname(target)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                with open(target, "w", encoding="utf-8") as fh:
                    fh.write("new\n")
    state = {
        "opened": opened,
        "attempts": {
            1: {
                "ended": {
                    "exit": 0,
                    "timedOut": False,
                    "refusal": None,
                },
            },
        },
    }
    stdout_path = os.path.join(run_dir, "attempt-1.stdout")
    with open(stdout_path, "w", encoding="utf-8") as fh:
        fh.write("prose only, no report tail\n")
    return run_dir, state


def _missing_items_delivered_detail(run_dir, state, attempt):
    got = ED._write_report_missing_items_delivered_detail(run_dir, state, attempt)
    if got is None:
        return None
    return got[0]


def test_report_missing_classifier_clause1_timed_out_not_emitted(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir, state = _report_missing_base_state(
        tmp_path, wt, expected_items=["item.txt"],
    )
    state["attempts"][1]["ended"]["timedOut"] = True
    assert ED._write_report_missing_items_delivered_detail(run_dir, state, 1) is None


def test_report_missing_classifier_clause1_refusal_not_emitted(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir, state = _report_missing_base_state(
        tmp_path, wt, expected_items=["item.txt"],
    )
    state["attempts"][1]["ended"]["refusal"] = "attempt-died-unrecorded"
    assert ED._write_report_missing_items_delivered_detail(run_dir, state, 1) is None


def test_report_missing_classifier_clause1_exit_not_emitted(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir, state = _report_missing_base_state(
        tmp_path, wt, expected_items=["item.txt"],
    )
    state["attempts"][1]["ended"]["exit"] = 1
    assert ED._write_report_missing_items_delivered_detail(run_dir, state, 1) is None


def test_report_missing_classifier_clause2_uncontracted_not_emitted(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir, state = _report_missing_base_state(
        tmp_path, wt, expected_items=["item.txt"],
        fed_prompt="Build this.\n",
    )
    assert ED._write_report_missing_items_delivered_detail(run_dir, state, 1) is None


def test_report_missing_classifier_clause4_empty_expected_not_emitted(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir, state = _report_missing_base_state(
        tmp_path, wt, expected_items=[],
    )
    assert ED._write_report_missing_items_delivered_detail(run_dir, state, 1) is None


def test_report_missing_classifier_clause4_absent_expected_not_emitted(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir, state = _report_missing_base_state(
        tmp_path, wt, expected_items=None,
    )
    assert ED._write_report_missing_items_delivered_detail(run_dir, state, 1) is None


def test_report_missing_classifier_clause5_missing_path_not_emitted(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir, state = _report_missing_base_state(
        tmp_path, wt, expected_items=["missing.txt"],
        deliver_expected_items=False,
    )
    assert ED._write_report_missing_items_delivered_detail(run_dir, state, 1) is None


def test_report_missing_classifier_clause3_gradeable_report_not_emitted(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir, state = _report_missing_base_state(
        tmp_path, wt, expected_items=["item.txt"],
    )
    stdout_path = os.path.join(run_dir, "attempt-1.stdout")
    with open(stdout_path, "w", encoding="utf-8") as fh:
        fh.write(_build_ok_stdout())
    assert ED._write_report_missing_items_delivered_detail(run_dir, state, 1) is None


def test_report_missing_classifier_bite_proof_clause1_timed_out(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir, state = _report_missing_base_state(
        tmp_path, wt, expected_items=["item.txt"],
    )
    target = os.path.join(wt, "item.txt")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("new\n")
    # green baseline
    assert _missing_items_delivered_detail(run_dir, state, 1) == (
        ED.ITEM_DETAIL_REPORT_MISSING_ITEMS_DELIVERED
    )
    # red: neutralize clause 1
    state["attempts"][1]["ended"]["timedOut"] = True
    assert ED._write_report_missing_items_delivered_detail(run_dir, state, 1) is None
    # restore
    state["attempts"][1]["ended"]["timedOut"] = False
    assert _missing_items_delivered_detail(run_dir, state, 1) == (
        ED.ITEM_DETAIL_REPORT_MISSING_ITEMS_DELIVERED
    )


def test_report_missing_classifier_bite_proof_clause1_refusal(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir, state = _report_missing_base_state(
        tmp_path, wt, expected_items=["item.txt"],
    )
    target = os.path.join(wt, "item.txt")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("new\n")
    assert _missing_items_delivered_detail(run_dir, state, 1) == (
        ED.ITEM_DETAIL_REPORT_MISSING_ITEMS_DELIVERED
    )
    state["attempts"][1]["ended"]["refusal"] = "attempt-died-unrecorded"
    assert ED._write_report_missing_items_delivered_detail(run_dir, state, 1) is None
    state["attempts"][1]["ended"]["refusal"] = None
    assert _missing_items_delivered_detail(run_dir, state, 1) == (
        ED.ITEM_DETAIL_REPORT_MISSING_ITEMS_DELIVERED
    )


def test_report_missing_classifier_bite_proof_clause1_exit(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir, state = _report_missing_base_state(
        tmp_path, wt, expected_items=["item.txt"],
    )
    target = os.path.join(wt, "item.txt")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("new\n")
    assert _missing_items_delivered_detail(run_dir, state, 1) == (
        ED.ITEM_DETAIL_REPORT_MISSING_ITEMS_DELIVERED
    )
    state["attempts"][1]["ended"]["exit"] = 1
    assert ED._write_report_missing_items_delivered_detail(run_dir, state, 1) is None
    state["attempts"][1]["ended"]["exit"] = 0
    assert _missing_items_delivered_detail(run_dir, state, 1) == (
        ED.ITEM_DETAIL_REPORT_MISSING_ITEMS_DELIVERED
    )


def test_report_missing_classifier_bite_proof_clause2_uncontracted(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir, state = _report_missing_base_state(
        tmp_path, wt, expected_items=["item.txt"],
    )
    target = os.path.join(wt, "item.txt")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("new\n")
    assert _missing_items_delivered_detail(run_dir, state, 1) == (
        ED.ITEM_DETAIL_REPORT_MISSING_ITEMS_DELIVERED
    )
    state["opened"]["fedPrompt"] = "Build this.\n"
    assert ED._write_report_missing_items_delivered_detail(run_dir, state, 1) is None
    state["opened"]["fedPrompt"] = _contracted_fed_prompt("Build this.\n")
    assert _missing_items_delivered_detail(run_dir, state, 1) == (
        ED.ITEM_DETAIL_REPORT_MISSING_ITEMS_DELIVERED
    )


def test_report_missing_classifier_bite_proof_clause3_gradeable_report(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir, state = _report_missing_base_state(
        tmp_path, wt, expected_items=["item.txt"],
    )
    target = os.path.join(wt, "item.txt")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("new\n")
    assert _missing_items_delivered_detail(run_dir, state, 1) == (
        ED.ITEM_DETAIL_REPORT_MISSING_ITEMS_DELIVERED
    )
    stdout_path = os.path.join(run_dir, "attempt-1.stdout")
    with open(stdout_path, "w", encoding="utf-8") as fh:
        fh.write(_build_ok_stdout())
    assert ED._write_report_missing_items_delivered_detail(run_dir, state, 1) is None
    with open(stdout_path, "w", encoding="utf-8") as fh:
        fh.write("prose only, no report tail\n")
    assert _missing_items_delivered_detail(run_dir, state, 1) == (
        ED.ITEM_DETAIL_REPORT_MISSING_ITEMS_DELIVERED
    )


def test_report_missing_classifier_bite_proof_clause4_empty_expected(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir, state = _report_missing_base_state(
        tmp_path, wt, expected_items=["item.txt"],
    )
    target = os.path.join(wt, "item.txt")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("new\n")
    assert _missing_items_delivered_detail(run_dir, state, 1) == (
        ED.ITEM_DETAIL_REPORT_MISSING_ITEMS_DELIVERED
    )
    state["opened"]["expectedItems"] = []
    assert ED._write_report_missing_items_delivered_detail(run_dir, state, 1) is None
    state["opened"]["expectedItems"] = ["item.txt"]
    assert _missing_items_delivered_detail(run_dir, state, 1) == (
        ED.ITEM_DETAIL_REPORT_MISSING_ITEMS_DELIVERED
    )


def test_report_missing_classifier_bite_proof_clause4_absent_expected(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir, state = _report_missing_base_state(
        tmp_path, wt, expected_items=["item.txt"],
    )
    target = os.path.join(wt, "item.txt")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("new\n")
    assert _missing_items_delivered_detail(run_dir, state, 1) == (
        ED.ITEM_DETAIL_REPORT_MISSING_ITEMS_DELIVERED
    )
    state["opened"]["expectedItems"] = None
    assert ED._write_report_missing_items_delivered_detail(run_dir, state, 1) is None
    state["opened"]["expectedItems"] = ["item.txt"]
    assert _missing_items_delivered_detail(run_dir, state, 1) == (
        ED.ITEM_DETAIL_REPORT_MISSING_ITEMS_DELIVERED
    )


def test_report_missing_classifier_bite_proof_clause5_missing_path(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir, state = _report_missing_base_state(
        tmp_path, wt, expected_items=["item.txt"],
    )
    target = os.path.join(wt, "item.txt")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("new\n")
    assert _missing_items_delivered_detail(run_dir, state, 1) == (
        ED.ITEM_DETAIL_REPORT_MISSING_ITEMS_DELIVERED
    )
    os.remove(target)
    assert ED._write_report_missing_items_delivered_detail(run_dir, state, 1) is None
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("new\n")
    assert _missing_items_delivered_detail(run_dir, state, 1) == (
        ED.ITEM_DETAIL_REPORT_MISSING_ITEMS_DELIVERED
    )


def test_report_missing_classifier_all_five_emit_token(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir, state = _report_missing_base_state(
        tmp_path, wt, expected_items=["item.txt"],
    )
    target = os.path.join(wt, "item.txt")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("new\n")
    detail = _missing_items_delivered_detail(run_dir, state, 1)
    assert detail == ED.ITEM_DETAIL_REPORT_MISSING_ITEMS_DELIVERED


def test_report_missing_dirty_tree_path(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    target = os.path.join(wt, "delivered.txt")

    class DirtyNoReportRunner:
        def __call__(self, argv, prompt_bytes, timeout, progress_cb, cwd):
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("done\n")
            return "prose only\n", False, 0, ""

    res = _dispatch_write(
        tmp_path, DirtyNoReportRunner(), cwd=wt,
        expected_items=["delivered.txt"],
    )
    assert res["ok"] is False
    assert res["forfeited"] is True
    assert res["detail"] == ED.ITEM_DETAIL_REPORT_MISSING_ITEMS_DELIVERED
    assert res["itemCheck"]["missing"] == []
    assert "reconstruct the change from the diff" in res["disclosure"]
    assert "not authorship" in res["disclosure"]
    assert "inspect and clean it yourself" in res["disclosure"]


def test_report_missing_double_forfeit_path(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    target = os.path.join(wt, "delivered.txt")

    class DoubleNoReportRunner:
        def __init__(self):
            self.calls = 0

        def __call__(self, argv, prompt_bytes, timeout, progress_cb, cwd):
            self.calls += 1
            if self.calls == 2:
                with open(target, "w", encoding="utf-8") as fh:
                    fh.write("done\n")
            return "prose only\n", False, 0, ""

    res = _dispatch_write(
        tmp_path, DoubleNoReportRunner(), cwd=wt,
        expected_items=["delivered.txt"],
    )
    assert res["ok"] is False
    assert res["forfeited"] is True
    assert res["detail"] == ED.ITEM_DETAIL_REPORT_MISSING_ITEMS_DELIVERED
    assert res["attempts"] == 2
    assert res["itemCheck"]["missing"] == []


def test_write_legacy_uncontracted_resume_grades_like_parse_result(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    wt_real = os.path.realpath(wt)
    baseline = ED._worktree_baseline(wt_real)
    legacy_stdout = _legacy_build_ok_stdout()
    fed_prompt = "Build this.\n"
    ED._acquire_worktree_lease(wt_real, run_dir)
    ED._open_write_run(
        run_dir, engine="codex", argv=["codex"], cwd=wt_real,
        timeout=ED.RETRY_MIN_TIMEOUT, retry_timeout=ED.RETRY_MIN_TIMEOUT,
        prompt_path=_prompt(tmp_path), order_id="legacy-1", base_sha="abc",
        worktree_baseline=baseline, progress_path=os.path.join(run_dir, "progress.jsonl"),
    )
    records, _ = ED._journal_read(run_dir)
    ED._journal_append(run_dir, {
        "kind": "attempt-started", "attempt": 1, "childPid": 1, "at": time.time(),
    })
    ED._journal_append(run_dir, {
        "kind": "attempt-ended", "attempt": 1,
        "ended": {"exit": 0, "timedOut": False},
        "at": time.time(),
    })
    with open(os.path.join(run_dir, "attempt-1.stdout"), "w", encoding="utf-8") as fh:
        fh.write(legacy_stdout)
    records, _ = ED._journal_read(run_dir)
    for record in records:
        if record.get("kind") == "run-opened":
            record["fedPrompt"] = fed_prompt
    state = ED._journal_state(records)
    grade = ED._grade_write_attempt(run_dir, state, 1)
    assert grade["ok"] is True
    assert grade["signal"] == "ok"
