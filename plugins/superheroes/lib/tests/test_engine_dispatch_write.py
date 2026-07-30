import importlib.util
import json
import os
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
    return json.dumps({"ok": True, "signal": "ok", "evidence": {"testFailed": False, "testPassed": True}})


def _honest_refusal_stdout():
    return json.dumps({"ok": False, "signal": "plan_wrong", "evidence": {"testFailed": True, "testPassed": False}})


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
        "prompt_path": _prompt(tmp_path),
        "cwd": cwd,
        "run_dir": run_dir,
        "order_id": "order-1",
        "run_engine": fake,
    }
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
    old = time.time() - ED.LEASE_MALFORMED_RECLAIM_SECONDS - 5
    os.utime(lease_path, (old, old))
    fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
    res = _dispatch_write(tmp_path, fake, cwd=wt)
    assert res["ok"] is True
    records, _ = ED._journal_read(str(tmp_path / "run"))
    assert any(r.get("kind") == "lease-reclaimed" for r in records)


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
