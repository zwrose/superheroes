"""Tests for dispatch-write (#702) and write-specific supervision edges."""
import importlib.util
import hashlib
import inspect
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import engine_adapter as EA  # noqa: E402
import model_registry as MR  # noqa: E402


def _load_ed():
    spec = importlib.util.spec_from_file_location(
        "engine_dispatch", os.path.join(_HERE, "..", "engine_dispatch.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ED = _load_ed()



def _authority_from_state(run_dir, state, **kw):
    run_dir = str(run_dir)
    kind = (
        ED.RUN_KIND_WRITE
        if state.get("dispatchMode") == ED.WRITE_DISPATCH_MODE
        else ED.RUN_KIND_REVIEW
    )
    nonce = kw.get("run_nonce", state.get("runNonce", "test-nonce"))
    order_id = kw.get("order_id", state.get("orderId") or "")
    launch_argv = list(kw.get("launch_argv", state.get("argv") or []))
    if "launch_cwd" in kw:
        launch_cwd = kw["launch_cwd"]
    elif kind == ED.RUN_KIND_WRITE:
        launch_cwd = state.get("cwd")
    else:
        launch_cwd = os.path.join(run_dir, ED.REVIEW_CWD_DIRNAME)
    role_kind = state.get("roleKind") or ("build" if kind == ED.RUN_KIND_WRITE else "review")
    return ED.LaunchAuthority(
        role_kind=role_kind,
        run_kind=kind,
        engine=state.get("engine") or "codex",
        effort=state.get("effort") or "high",
        model=state.get("model"),
        engine_model=state.get("engineModel"),
        schema_path=state.get("schemaPath"),
        argv=tuple(launch_argv),
        spawned_argv=tuple(state.get("spawnedArgv") or launch_argv),
        engine_binary=kw.get("engine_binary", state.get("engineBinary") or ""),
        cwd=str(launch_cwd),
        order_id=order_id or "",
        run_nonce=nonce or "test-nonce",
        run_dir=run_dir,
        timeout=int(state.get("attemptTimeout") or state.get("timeout") or 5),
        retry_timeout=int(state.get("retryTimeout") or 5),
        lease_token=state.get("worktreeLeaseToken"),
        lease_holder=state.get("worktreeLeaseHolder"),
        cleanup_roots=tuple(state.get("cleanupRoots") or ()),
        fed_prompt=state.get("fedPrompt") or "",
        view_receipt=state.get("viewReceipt") or {},
        repo_root=state.get("repoRoot"),
        prompt_path=state.get("promptPath"),
        progress_path=state.get("progressPath"),
        base_sha=state.get("baseSha"),
        prompt_sha256=kw.get("prompt_sha256", state.get("promptSha256")),
    )


def _persist_test_authority(run_dir, state, **kw):
    run_dir = os.path.realpath(str(run_dir))
    authority = _authority_from_state(run_dir, state, **kw)
    try:
        auth_hash = ED._persist_authority(authority)
    except FileExistsError:
        auth_hash = ED._authority_file_hash(str(run_dir))
    except OSError:
        auth_hash = ED._authority_file_hash(str(run_dir))
    if auth_hash and isinstance(state, dict):
        state["authorityHash"] = auth_hash
        state_path = os.path.join(str(run_dir), ED.STATE_NAME)
        if os.path.isfile(state_path):
            try:
                cur = json.loads(open(state_path, encoding="utf-8").read())
            except (OSError, ValueError):
                cur = dict(state)
            if isinstance(cur, dict):
                cur["authorityHash"] = auth_hash
                open(state_path, "w", encoding="utf-8").write(json.dumps(cur))
    if auth_hash:
        try:
            ED._ledger_init(authority, auth_hash)
        except FileExistsError:
            pass
    return authority


def _seal_test_launch(run_dir, attempt, state, **kw):
    """Seal a per-attempt launch record for tests that drive run-child / mid-flight."""
    run_dir = os.path.realpath(str(run_dir))
    authority = _authority_from_state(run_dir, state, **kw)
    auth_hash = state.get("authorityHash") or ED._authority_file_hash(str(run_dir))
    if not auth_hash:
        authority = _persist_test_authority(run_dir, state, **kw)
        auth_hash = state.get("authorityHash") or ED._authority_file_hash(str(run_dir))
    timeout = int(
        state.get("attemptTimeout") or state.get("timeout")
        or (authority.timeout if int(attempt) == 1 else authority.retry_timeout)
        or 5)
    wt_snap = state.get("worktreeSnapshot")
    if wt_snap is not None:
        wt_snap = list(wt_snap)
    try:
        ED._ledger_seal_attempt_intent(
            run_dir, attempt, auth_hash, authority.run_nonce, timeout, wt_snap)
    except FileExistsError:
        pass
    try:
        ED._seal_attempt_launch(str(run_dir), attempt, authority, auth_hash, timeout)
    except FileExistsError:
        pass
    return authority, auth_hash


def _bind_inflight(run_dir, state, attempt=1, **kw):
    """Persist authority, seal launch/intent, and stamp authorityHash onto any done sentinel."""
    run_dir = os.path.realpath(str(run_dir))
    authority = _persist_test_authority(run_dir, state, **kw)
    auth_hash = state.get("authorityHash")
    _seal_test_launch(run_dir, attempt, state, **kw)
    done_path = os.path.join(str(run_dir), "attempt-%d.done" % int(attempt))
    if os.path.isfile(done_path):
        try:
            done = json.loads(open(done_path, encoding="utf-8").read())
        except (OSError, ValueError):
            done = None
        if isinstance(done, dict) and auth_hash:
            done["authorityHash"] = auth_hash
            if not done.get("runNonce"):
                done["runNonce"] = state.get("runNonce") or authority.run_nonce
            open(done_path, "w", encoding="utf-8").write(json.dumps(done))
        nonce = state.get("runNonce") or authority.run_nonce
        # Only seal ledger completion for a trusted same-nonce done — a stale
        # prior-run sentinel must not count as complete.
        if (isinstance(done, dict) and auth_hash
                and done.get("runNonce") == nonce):
            claim_path = ED._ledger_attempt_path(run_dir, attempt, "claim")
            if claim_path and not os.path.isfile(claim_path):
                try:
                    ED._ledger_seal(claim_path, {
                        "schemaVersion": ED.LEDGER_SCHEMA_VERSION,
                        "attempt": int(attempt),
                        "authorityHash": auth_hash,
                        "runNonce": nonce,
                        "childPid": state.get("supervisorPid") or state.get(
                            "completedAttemptSupervisorPid"),
                        "childStart": state.get("supervisorStart") or "",
                    })
                except FileExistsError:
                    pass
            try:
                ED._ledger_seal_attempt_complete(
                    run_dir, attempt, auth_hash, nonce)
            except FileExistsError:
                pass
    return authority, auth_hash


def _invoke_run_child(run_dir, attempt, state, **kw):
    authority, auth_hash = _seal_test_launch(run_dir, attempt, state, **kw)
    run_dir = os.path.realpath(str(run_dir))
    try:
        ED._ledger_claim_attempt(
            run_dir, attempt, auth_hash, authority.run_nonce)
    except OSError:
        pass
    launch = ED._load_attempt_launch(
        str(run_dir), attempt, auth_hash, authority.run_nonce)
    return ED._run_child_main(
        str(run_dir), attempt, authority,
        authority_hash=auth_hash, launch=launch,
    )

def _git(repo, *args, check=True):
    return subprocess.run(
        ["git", "-C", repo, *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _init_repo(path, *, commit=True, files=None):
    path = str(path)
    os.makedirs(path, exist_ok=True)
    _git(path, "init", "-q")
    for rel, content in (files or {"README.md": "hello\n"}).items():
        full = os.path.join(path, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(content)
    if commit:
        _git(path, "add", "-A")
        _git(
            path,
            "-c",
            "user.email=test@test.local",
            "-c",
            "user.name=test",
            "commit",
            "-q",
            "-m",
            "init",
        )
    return path


def _linked_pair(tmp_path):
    main = _init_repo(tmp_path / "main")
    linked = tmp_path / "linked"
    _git(main, "worktree", "add", str(linked), "-q")
    return main, str(linked)


def _two_linked_worktrees(tmp_path):
    main = _init_repo(tmp_path / "main")
    wt1 = tmp_path / "wt1"
    wt2 = tmp_path / "wt2"
    _git(main, "worktree", "add", str(wt1), "-q")
    _git(main, "worktree", "add", str(wt2), "-q", "-b", "second-wt")
    return main, str(wt1), str(wt2)


def _quick_write_stdout_py():
    return [
        "python3",
        "-c",
        "import sys; sys.stdout.write(%r)" % _WRITE_OK_STDOUT,
    ]


def _install_fake_codex_on_path(monkeypatch, tmp_path, *, ok_stdout=None, slow_first_seconds=60,
                                 slow_by_attempt=None):
    """Detached run-child resolves codex via PATH; fake engine counts invocations in cwd."""
    ok_stdout = ok_stdout or _WRITE_OK_STDOUT
    slow_by_attempt = dict(slow_by_attempt or {})
    if slow_first_seconds is not None and 1 not in slow_by_attempt:
        slow_by_attempt[1] = slow_first_seconds
    bin_dir = tmp_path / "fake-bin"
    bin_dir.mkdir(mode=0o700)
    marker = ".fake-codex-invokes"
    slow_map = json.dumps({str(k): v for k, v in slow_by_attempt.items()})
    script = (
        "#!/usr/bin/env python3\n"
        "import json, os, sys, time\n"
        "slow_by_attempt = %s\n"
        "marker = os.path.join(os.getcwd(), %r)\n"
        "n = 0\n"
        "if os.path.isfile(marker):\n"
        "    n = int(open(marker).read().strip() or '0')\n"
        "n += 1\n"
        "open(marker, 'w').write(str(n))\n"
        "delay = slow_by_attempt.get(str(n), 0)\n"
        "if delay:\n"
        "    time.sleep(delay)\n"
        "    sys.exit(0)\n"
        "sys.stdout.write(%r)\n"
        "sys.exit(0)\n"
    ) % (slow_map, marker, ok_stdout)
    codex = bin_dir / "codex"
    codex.write_text(script, encoding="utf-8")
    codex.chmod(0o755)
    monkeypatch.setenv(
        "PATH",
        str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
    )
    return bin_dir


def _assert_spawn_detached(proc):
    assert proc is not None
    assert isinstance(proc, subprocess.Popen)
    assert proc.pid != os.getpid()
    # Detached own-session child: must not share the caller's session/pgroup.
    child_sid = os.getsid(proc.pid)
    child_pgid = os.getpgid(proc.pid)
    assert child_sid != os.getsid(os.getpid()), (
        "child sid %s equals caller sid %s — not a new session" % (
            child_sid, os.getsid(os.getpid())))
    assert child_pgid != os.getpgid(os.getpid()), (
        "child pgid %s equals caller pgid %s — not a new process group" % (
            child_pgid, os.getpgid(os.getpid())))
    assert child_pgid == proc.pid, (
        "child pgid %s should equal child pid %s (session leader)" % (
            child_pgid, proc.pid))


def _wait_process_dead(pid, timeout_s=60):
    """Wait until real ``_process_alive`` reports dead — no mock."""
    if not pid:
        return
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if not ED._process_alive(pid):
            return
        time.sleep(0.25)
    raise AssertionError("pid %s still alive after %.1fs" % (pid, timeout_s))


def _spy_run_engine_files_quick_ok(monkeypatch, captured):
    real = ED._run_engine_files

    def _spy(argv, *args, **kwargs):
        captured.append(list(argv))
        return real(_quick_write_stdout_py(), *args, **kwargs)

    monkeypatch.setattr(ED, "_run_engine_files", _spy)
    return captured


def _inline_run_child_spawn(monkeypatch, *, children=None):
    """Replace supervisor Popen with in-process run-child so _run_engine_files spies apply."""
    if children is None:
        children = []

    def _inline(rd, attempt, authority, authority_hash=None):
        children.append(attempt)
        ED._run_child_main(
            str(rd), attempt, authority, authority_hash=authority_hash)

        class _Proc:
            pid = os.getpid()

        return _Proc()

    monkeypatch.setattr(ED, "_spawn_run_child", _inline)
    return children


def _prompt(tmp_path, text="build this\n"):
    p = tmp_path / "prompt.txt"
    p.write_text(text, encoding="utf-8")
    return str(p)


class FakeWriteRunner:
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


def _write_argv_combinations():
    combos = []
    for engine in ("codex", "cursor"):
        for model_id in MR._MODELS[engine]:
            if MR._MODELS[engine][model_id].get("override_only"):
                continue
            if engine == "cursor" and model_id == "composer-2.5":
                ok, _ = MR.validate_config(engine, model_id, None)
                if ok:
                    combos.append((engine, model_id, None))
                continue
            for effort in MR._EFFORT_ENUM[engine]:
                if effort in MR.OVERRIDE_ONLY_EFFORTS.get(engine, ()):
                    continue
                ok, _ = MR.validate_config(engine, model_id, effort)
                if ok:
                    combos.append((engine, model_id, effort))
    return combos


def test_dispatch_write_signature_has_no_widening_params():
    sig = inspect.signature(ED.dispatch_write)
    forbidden = {"role", "role_kind", "sandbox", "argv", "binary", "extra_args"}
    assert forbidden.isdisjoint(sig.parameters.keys())


def test_dispatch_write_body_uses_build_role_literal():
    import ast
    path = os.path.join(_HERE, "..", "engine_dispatch.py")
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_dispatch_write_impl":
            for child in ast.walk(node):
                if isinstance(child, ast.Assign):
                    for target in child.targets:
                        if isinstance(target, ast.Name) and target.id == "role_kind":
                            assert isinstance(child.value, ast.Constant) and child.value.value == "build"
                            return
    pytest.fail("role_kind = build literal not found in _dispatch_write_impl")


def _assert_write_workspace_argv(argv, engine):
    if engine == "codex":
        assert "--sandbox" in argv
        idx = argv.index("--sandbox")
        assert argv[idx + 1] == "workspace-write"
        assert "read-only" not in argv
        assert "--output-schema" not in argv
    else:
        assert "-f" in argv
        assert "--mode" not in argv or argv[argv.index("--mode") + 1] != "plan"


def test_build_argv_sweep_workspace_write_from_registry():
    """Builder-level: argv shape when role_kind is explicitly build."""
    for engine, model_id, effort in _write_argv_combinations():
        opts = {"engine_model": model_id, "cwd": "/tmp"}
        built = EA.build_argv_result(engine, "build", effort, opts)
        assert built.get("reason") is None, (engine, model_id, effort, built)
        argv = built["argv"]
        assert argv[0] in ("codex", "cursor-agent")
        _assert_write_workspace_argv(argv, engine)


_WRITE_OK_STDOUT = json.dumps({"ok": True, "signal": "ok", "evidence": {}})


def test_dispatch_write_argv_sweep_reports_workspace_write(tmp_path):
    """Write API end-to-end: dispatch_write must emit workspace-write argv, not read-only."""
    main, linked = _linked_pair(tmp_path)
    prompt = _prompt(tmp_path)
    for i, (engine, model_id, effort) in enumerate(_write_argv_combinations()):
        run_dir = tmp_path / "write-sweep" / str(i)
        run_dir.mkdir(parents=True)
        fake = FakeWriteRunner([(_WRITE_OK_STDOUT, False, 0, "")])
        res = ED.dispatch_write(
            engine,
            engine_model=model_id,
            effort=effort,
            prompt_path=prompt,
            cwd=linked,
            order_id="write-sweep-%d" % i,
            run_engine=fake,
            max_wait=60,
            run_dir=str(run_dir),
        )
        assert res.get("ok") is True, (engine, model_id, effort, res)
        assert len(fake.calls) == 1
        _assert_spawned_argv_pair(res)
        assert res["argv"][0] in ("codex", "cursor-agent")
        _assert_write_workspace_argv(res["argv"], engine)
        _assert_write_workspace_argv(res["spawnedArgv"], engine)
        _assert_write_workspace_argv(fake.calls[0]["argv"], engine)


def _review_argv_combinations():
    combos = []
    for engine in ("codex", "cursor"):
        for model in MR.known_claude_models():
            if model == "fable":
                continue
            for effort in MR._EFFORT_ENUM[engine]:
                if effort in MR.OVERRIDE_ONLY_EFFORTS.get(engine, ()):
                    continue
                built = EA.build_argv_result(engine, "review", effort, {"model": model})
                if built.get("reason") is None:
                    combos.append((engine, model, effort))
    return combos


def test_review_argv_never_workspace_write():
    built = EA.build_argv_result("codex", "review", "high", {"model": "sonnet"})
    argv = built["argv"]
    idx = argv.index("--sandbox")
    assert argv[idx + 1] == "read-only"


def test_cwd_refusals_before_spawn(tmp_path):
    fake = FakeWriteRunner([])
    prompt = _prompt(tmp_path)
    main, linked = _linked_pair(tmp_path)

    cases = [
        (None, "cwd-absent"),
        ("", "cwd-absent"),
        (str(tmp_path / "missing"), "cwd-missing"),
    ]
    f = tmp_path / "file"
    f.write_text("x", encoding="utf-8")
    cases.append((str(f), "cwd-not-a-directory"))

    bare = tmp_path / "bare"
    bare.mkdir()
    cases.append((str(bare), "cwd-not-a-repo"))

    sub = linked + "/sub"
    os.makedirs(sub, exist_ok=True)
    cases.append((sub, "cwd-not-worktree-root"))

    cases.append((main, "cwd-primary-checkout"))

    for cwd_val, detail in cases:
        res = ED.dispatch_write(
            "codex", engine_model="gpt-5.6-terra", effort="high",
            prompt_path=prompt, cwd=cwd_val, order_id="o1", run_engine=fake,
        )
        assert res["terminal"] is True
        assert res["attempts"] == 0
        assert res["forfeited"] is False
        assert res["detail"] == detail

    assert len(fake.calls) == 0


def test_separate_git_dir_primary_refused(tmp_path):
    main = tmp_path / "sep"
    gitdir = tmp_path / "gitdir"
    os.makedirs(main)
    subprocess.run(
        ["git", "init", "--separate-git-dir", str(gitdir), str(main)],
        check=True,
        capture_output=True,
    )
    _git(main, "add", "-A")
    _git(
        main,
        "-c",
        "user.email=test@test.local",
        "-c",
        "user.name=test",
        "commit",
        "-q",
        "-m",
        "init",
        "--allow-empty",
    )
    fake = FakeWriteRunner([])
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=_prompt(tmp_path), cwd=str(main), order_id="o1", run_engine=fake,
    )
    assert res["detail"] == "cwd-primary-checkout"
    assert res["attempts"] == 0
    assert len(fake.calls) == 0


def test_submodule_worktree_refused(tmp_path):
    main = _init_repo(tmp_path / "super")
    sub_repo = _init_repo(tmp_path / "subrepo")
    _git(
        main,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        "-q",
        str(sub_repo),
        "sub",
    )
    sub_path = os.path.join(main, "sub")
    fake = FakeWriteRunner([])
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=_prompt(tmp_path), cwd=sub_path, order_id="o1", run_engine=fake,
    )
    assert res["detail"] == "cwd-primary-checkout"
    assert len(fake.calls) == 0


def test_git_env_cannot_bypass_cwd_validation(tmp_path, monkeypatch):
    main, linked = _linked_pair(tmp_path)
    monkeypatch.setenv("GIT_DIR", main)
    monkeypatch.setenv("GIT_WORK_TREE", linked)
    fake = FakeWriteRunner([])
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=_prompt(tmp_path), cwd=main, order_id="o1", run_engine=fake,
    )
    assert res["detail"] == "cwd-primary-checkout"
    assert len(fake.calls) == 0


def test_run_dir_inside_cwd_refused(tmp_path):
    main, linked = _linked_pair(tmp_path)
    run_inside = os.path.join(linked, "nested-run")
    fake = FakeWriteRunner([])
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=_prompt(tmp_path), cwd=linked, order_id="o1",
        run_dir=run_inside, run_engine=fake,
    )
    assert res["detail"] == "run-dir-inside-cwd"
    assert res["attempts"] == 0
    assert len(fake.calls) == 0


def test_engine_binary_inside_cwd_refused(tmp_path, monkeypatch):
    main, linked = _linked_pair(tmp_path)
    fake_bin = os.path.join(linked, "codex")
    with open(fake_bin, "w", encoding="utf-8") as fh:
        fh.write("#!/bin/sh\nexit 0\n")
    os.chmod(fake_bin, 0o755)

    def _which(cmd):
        if cmd == "codex":
            return fake_bin
        return shutil.which(cmd)

    monkeypatch.setattr(ED.shutil, "which", _which)
    fake = FakeWriteRunner([])
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=_prompt(tmp_path), cwd=linked, order_id="o1", run_engine=fake,
    )
    assert res["detail"] == "engine-binary-inside-cwd"
    assert len(fake.calls) == 0


def test_plan_wrong_refusal_terminal_no_retry(tmp_path):
    main, linked = _linked_pair(tmp_path)
    refusal_stdout = json.dumps({"ok": False, "signal": "plan_wrong"})
    fake = FakeWriteRunner([(refusal_stdout, False, 0, "")])
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=_prompt(tmp_path), cwd=linked, order_id="o1", run_engine=fake,
        max_wait=60,
    )
    assert res["terminal"] is True
    assert res["ok"] is False
    assert res.get("signal") == "plan_wrong"
    assert res["forfeited"] is False
    assert res["attempts"] == 1
    assert len(fake.calls) == 1


def test_forfeit_retries_once_then_terminal(tmp_path):
    main, linked = _linked_pair(tmp_path)
    ok_stdout = json.dumps({"ok": True, "signal": "ok", "evidence": {}})
    fake = FakeWriteRunner([
        ("", True, 0, ""),
        (ok_stdout, False, 0, ""),
    ])
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=_prompt(tmp_path), cwd=linked, order_id="o1", run_engine=fake,
        max_wait=120,
    )
    assert res["ok"] is True
    assert res["attempts"] == 2
    assert len(fake.calls) == 2


def test_retry_unsafe_dirty_worktree(tmp_path):
    main, linked = _linked_pair(tmp_path)
    dirty_marker = os.path.join(linked, "dirty.txt")

    def _run(argv, prompt_bytes, timeout, progress_cb, cwd):
        with open(dirty_marker, "w", encoding="utf-8") as fh:
            fh.write("mutated\n")
        return "", True, 0, ""

    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=_prompt(tmp_path), cwd=linked, order_id="o1", run_engine=_run,
        max_wait=120,
    )
    assert res["terminal"] is True
    assert res["detail"] == "retry-unsafe-dirty-worktree"
    assert res["forfeited"] is True
    assert res["attempts"] == 1


def test_worktree_lease_held_non_terminal(tmp_path):
    main, linked = _linked_pair(tmp_path)
    lease_path = ED._worktree_lease_path(os.path.realpath(linked))
    import file_lock
    file_lock.acquire(lease_path)
    try:
        fake = FakeWriteRunner([])
        res = ED.dispatch_write(
            "codex", engine_model="gpt-5.6-terra", effort="high",
            prompt_path=_prompt(tmp_path), cwd=linked, order_id="o1", run_engine=fake,
        )
        assert res.get("running") is True
        assert res["terminal"] is False
        assert res.get("detail") == "worktree-lease-held"
        assert len(fake.calls) == 0
    finally:
        file_lock.release(lease_path)


def _seed_write_dispatch_completed_attempt(tmp_path, *, engine, linked1, prompt, run_dir, order_id):
    run_dir = Path(run_dir)
    run_dir.mkdir(mode=0o700, parents=True)
    if engine == "codex":
        dispatch_kw = {
            "engine_model": "gpt-5.6-terra",
            "effort": "high",
        }
    else:
        dispatch_kw = {
            "engine_model": "composer-2.5",
            "effort": None,
        }
    fake = FakeWriteRunner([(_WRITE_OK_STDOUT, False, 0, "")])
    res = ED.dispatch_write(
        engine,
        prompt_path=prompt,
        cwd=linked1,
        order_id=order_id,
        run_engine=fake,
        max_wait=60,
        run_dir=str(run_dir),
        **dispatch_kw,
    )
    assert res.get("ok") is True, res
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    return state


def _prepare_forged_cwd_retry_state(state, run_dir, linked1, linked2, *, argv=None):
    state = dict(state)
    state["cwd"] = linked2
    if argv is not None:
        state["argv"] = argv
        _, forged_spawned = ED._resolve_argv_binary(argv)
        state["spawnedArgv"] = forged_spawned
        state["engineBinary"] = forged_spawned[0]
    state["inFlightAttempt"] = None
    state["completedAttempts"] = 1
    state["pendingTerminal"] = "forfeited"
    state["completedAttemptSupervisorPid"] = 999999998
    state["supervisorStart"] = "Mon Jan  1 00:00:00 2020"
    state["worktreeSnapshot"] = list(ED._worktree_snapshot(os.path.realpath(linked1)))
    try:
        (run_dir / "result.json").unlink()
    except FileNotFoundError:
        pass
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return state


def _spy_engine_files_no_spawn(monkeypatch):
    spawned = []
    real = ED._run_engine_files

    def _spy(argv, *args, **kwargs):
        spawned.append(list(argv))
        return real(argv, *args, **kwargs)

    monkeypatch.setattr(ED, "_run_engine_files", _spy)
    return spawned


def test_run_child_rejects_forged_cwd(tmp_path, monkeypatch):
    """Re-invoke with a cwd other than launch authority → cwd-authorization-mismatch."""
    main, linked1, linked2 = _two_linked_worktrees(tmp_path)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "forge-run"
    state = _seed_write_dispatch_completed_attempt(
        tmp_path, engine="codex", linked1=linked1, prompt=prompt,
        run_dir=run_dir, order_id="forge-o",
    )
    # Poison the receipt; authority remains bound to linked1.
    forged = EA.build_argv_result(
        "codex", "build", "high",
        {"engine_model": "gpt-5.6-terra", "cwd": linked2},
    )
    _prepare_forged_cwd_retry_state(
        state, run_dir, linked1, linked2, argv=forged["argv"],
    )
    spawned = []
    monkeypatch.setattr(ED, "_spawn_run_child", lambda *a, **k: spawned.append(1))
    # Attack: resume with the forged worktree as --cwd.
    res2 = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked2, order_id="forge-o",
        run_engine=ED._run_engine, max_wait=60, run_dir=str(run_dir),
    )
    assert spawned == [], res2
    assert res2.get("terminal") is True
    assert res2.get("detail") == "cwd-authorization-mismatch"


def test_run_child_rejects_forged_cwd_codex_argv_consistent(tmp_path, monkeypatch):
    """Forged receipt cwd cannot redirect the child — authority.cwd wins."""
    from dataclasses import replace
    main, linked1, linked2 = _two_linked_worktrees(tmp_path)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "forge-codex-argv-ok"
    state = _seed_write_dispatch_completed_attempt(
        tmp_path, engine="codex", linked1=linked1, prompt=prompt,
        run_dir=run_dir, order_id="forge-codex-argv",
    )
    authority = ED._load_authority(str(run_dir))
    assert authority is not None
    authorized_argv = list(authority.argv)
    _prepare_forged_cwd_retry_state(
        state, run_dir, linked1, linked2, argv=authorized_argv,
    )
    captured = []

    def _spy(argv, prompt_path, stdout_path, stderr_path, timeout, progress_path, attempt, cwd,
             **kwargs):
        captured.append(cwd)
        return {
            "exit": 0, "timedOut": False, "signal": None,
            "endedAt": time.time(), "refusal": None,
        }

    monkeypatch.setattr(ED, "_run_engine_files", _spy)
    lease_token, lease_holder = ED._acquire_worktree_lease_for_cwd(os.path.realpath(linked1))
    try:
        auth = replace(authority, lease_token=lease_token, lease_holder=lease_holder)
        auth_hash = state.get("authorityHash") or ED._authority_file_hash(str(run_dir))
        # Re-persist with lease credentials so child refresh succeeds.
        try:
            os.unlink(os.path.join(str(run_dir), ED.AUTHORITY_NAME))
        except FileNotFoundError:
            pass
        auth = replace(auth, run_dir=str(run_dir))
        auth_hash = ED._persist_authority(auth)
        state["authorityHash"] = auth_hash
        open(run_dir / "state.json", "w", encoding="utf-8").write(json.dumps(state))
        ED._seal_attempt_launch(str(run_dir), 2, auth, auth_hash, 5)
        ED._run_child_main(str(run_dir), 2, auth, authority_hash=auth_hash)
        assert captured, "engine should run under authority cwd"
        assert os.path.realpath(captured[0]) == os.path.realpath(linked1)
        assert os.path.realpath(captured[0]) != os.path.realpath(linked2)
    finally:
        ED._release_worktree_lease_for_cwd(
            os.path.realpath(linked1), lease_token, lease_holder)


def test_run_child_rejects_forged_cwd_cursor(tmp_path, monkeypatch):
    """Cursor: forged receipt cwd cannot redirect; authority.cwd is sole launch cwd."""
    from dataclasses import replace
    main, linked1, linked2 = _two_linked_worktrees(tmp_path)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "forge-cursor"
    state = _seed_write_dispatch_completed_attempt(
        tmp_path, engine="cursor", linked1=linked1, prompt=prompt,
        run_dir=run_dir, order_id="forge-cursor-o",
    )
    authority = ED._load_authority(str(run_dir))
    assert authority is not None
    original_argv = list(authority.argv)
    state = _prepare_forged_cwd_retry_state(state, run_dir, linked1, linked2)
    assert state["argv"] == original_argv
    captured = []

    def _spy(argv, prompt_path, stdout_path, stderr_path, timeout, progress_path, attempt, cwd,
             **kwargs):
        captured.append(cwd)
        return {
            "exit": 0, "timedOut": False, "signal": None,
            "endedAt": time.time(), "refusal": None,
        }

    monkeypatch.setattr(ED, "_run_engine_files", _spy)
    lease_token, lease_holder = ED._acquire_worktree_lease_for_cwd(os.path.realpath(linked1))
    try:
        auth = replace(authority, lease_token=lease_token, lease_holder=lease_holder,
                       run_dir=str(run_dir))
        try:
            os.unlink(os.path.join(str(run_dir), ED.AUTHORITY_NAME))
        except FileNotFoundError:
            pass
        auth_hash = ED._persist_authority(auth)
        state["authorityHash"] = auth_hash
        open(run_dir / "state.json", "w", encoding="utf-8").write(json.dumps(state))
        ED._seal_attempt_launch(str(run_dir), 2, auth, auth_hash, 5)
        ED._run_child_main(str(run_dir), 2, auth, authority_hash=auth_hash)
        assert captured
        assert os.path.realpath(captured[0]) == os.path.realpath(linked1)
        assert os.path.realpath(captured[0]) != os.path.realpath(linked2)
    finally:
        ED._release_worktree_lease_for_cwd(
            os.path.realpath(linked1), lease_token, lease_holder)


def test_authorized_cwd_write_dispatch_codex_and_cursor(tmp_path):
    """Happy path: authorized linked worktree cwd is not refused for codex or cursor."""
    cases = (
        ("codex", "gpt-5.6-terra", "high"),
        ("cursor", "composer-2.5", None),
    )
    for i, (engine, engine_model, effort) in enumerate(cases):
        main, linked1, linked2 = _two_linked_worktrees(tmp_path / ("happy-%d" % i))
        prompt = _prompt(tmp_path / ("happy-%d" % i))
        run_dir = tmp_path / ("happy-%d" % i) / "run"
        fake = FakeWriteRunner([(_WRITE_OK_STDOUT, False, 0, "")])
        res = ED.dispatch_write(
            engine,
            engine_model=engine_model,
            effort=effort,
            prompt_path=prompt,
            cwd=linked1,
            order_id="happy-%s" % engine,
            run_engine=fake,
            max_wait=60,
            run_dir=str(run_dir),
        )
        assert res.get("ok") is True, (engine, res)
        assert res.get("detail") not in (
            "cwd-authorization-mismatch",
            "argv-rederivation-mismatch",
        )
        assert len(fake.calls) == 1


def test_run_child_rejects_argv_drift_write(tmp_path):
    main, linked = _linked_pair(tmp_path)
    run_dir = tmp_path / "run"
    run_dir.mkdir(mode=0o700)
    (run_dir / "prompt.txt").write_bytes(b"x")
    state = {
        "engine": "codex",
        "roleKind": "build",
        "dispatchMode": ED.WRITE_DISPATCH_MODE,
        "effort": "high",
        "engineModel": "gpt-5.6-terra",
        "cwd": linked,
        "argv": ["codex", "exec", "--sandbox", "read-only", "-m", "gpt-5.6-terra",
                 "-c", "model_reasoning_effort=high", "-C", linked, "-"],
        "engineBinary": shutil.which("codex") or "/usr/bin/false",
        "attemptTimeout": 5,
        "runNonce": "drift-w",
        "orderId": "o-drift",
    }
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    _invoke_run_child(run_dir, 1, state)
    done = json.loads((run_dir / "attempt-1.done").read_text(encoding="utf-8"))
    assert done.get("refusal") == "argv-rederivation-mismatch"


def test_is_supervisor_process_requires_matching_lstart():
    pid = os.getpid()
    actual = ED._supervisor_lstart(pid)
    assert ED._is_supervisor_process("/fake/run", pid, "not-the-real-start") is False
    if actual:
        assert ED._is_supervisor_process("/fake/run", pid, actual) is False


def test_retry_unsafe_attempt_still_live(tmp_path):
    """Still-live forfeit uses real ``_process_alive`` against a genuinely live pid."""
    main, linked = _linked_pair(tmp_path)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "still-live"
    run_dir.mkdir(mode=0o700)
    (run_dir / "prompt.txt").write_bytes(b"build\n")
    built = EA.build_argv_result(
        "codex", "build", "high",
        {"engine_model": "gpt-5.6-terra", "cwd": linked},
    )
    argv = built["argv"]
    lease_token, lease_holder = ED._acquire_worktree_lease_for_cwd(
        os.path.realpath(linked))
    # Hold a real process so _process_alive is True without mocking the seam.
    holder = subprocess.Popen(
        ["python3", "-c", "import time; time.sleep(120)"],
        start_new_session=True,
    )
    try:
        state = {
            "engine": "codex",
            "roleKind": "build",
            "dispatchMode": ED.WRITE_DISPATCH_MODE,
            "effort": "high",
            "engineModel": "gpt-5.6-terra",
            "cwd": os.path.realpath(linked),
            "argv": argv,
            "spawnedArgv": argv,
            "engineBinary": shutil.which(argv[0]) or "/bin/true",
            "timeout": 5,
            "retryTimeout": 5,
            "orderId": "still-live-o",
            "runNonce": "still-live-n",
            "worktreeLeaseToken": lease_token,
            "worktreeLeaseHolder": lease_holder,
            "worktreeSnapshot": list(ED._worktree_snapshot(linked)),
            "completedAttempts": 0,
            "inFlightAttempt": 1,
            "attemptStartedAt": time.time() - 10,
            "supervisorPid": holder.pid,
            "supervisorStart": ED._supervisor_lstart(holder.pid) or "live",
            "promptPath": str(run_dir / "prompt.txt"),
            "fedPrompt": "build\n",
        }
        (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
        (run_dir / "attempt-1.done").write_text(json.dumps({
            "exit": None, "timedOut": True, "runNonce": "still-live-n",
            "endedAt": time.time(),
        }), encoding="utf-8")
        (run_dir / "attempt-1.stdout").write_text("", encoding="utf-8")
        (run_dir / "attempt-1.stderr").write_text("", encoding="utf-8")
        _bind_inflight(run_dir, state)
        assert ED._process_alive(holder.pid) is True
        res = ED.dispatch_write(
            "codex", engine_model="gpt-5.6-terra", effort="high",
            prompt_path=prompt, cwd=linked, order_id="still-live-o",
            run_engine=FakeWriteRunner([]),
            max_wait=120, run_dir=str(run_dir),
        )
        assert res["terminal"] is True, res
        assert res["detail"] == "retry-unsafe-attempt-still-live"
        assert res["forfeited"] is True
        assert res["attempts"] == 1
    finally:
        try:
            os.killpg(holder.pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            holder.wait(timeout=2)
        except Exception:
            pass


def test_unknown_engine_refused(tmp_path):
    main, linked = _linked_pair(tmp_path)
    fake = FakeWriteRunner([])
    res = ED.dispatch_write(
        "openai", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=_prompt(tmp_path), cwd=linked, order_id="o1", run_engine=fake,
    )
    assert res["detail"] == "unknown-engine"
    assert len(fake.calls) == 0


def _assert_spawned_argv_pair(res):
    argv = res["argv"]
    spawned = res["spawnedArgv"]
    assert argv[0] in ("codex", "cursor-agent")
    assert os.path.isabs(spawned[0])
    assert os.path.isfile(spawned[0])
    resolved = shutil.which(argv[0])
    assert resolved
    assert spawned[0] == resolved
    assert spawned[1:] == argv[1:]


def test_dispatch_write_spawned_argv_echo(tmp_path, monkeypatch):
    main, linked = _linked_pair(tmp_path)
    run_dir = tmp_path / "run"
    run_dir.mkdir(mode=0o700)
    captured = _spy_run_engine_files_quick_ok(monkeypatch, [])
    _inline_run_child_spawn(monkeypatch)
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=_prompt(tmp_path), cwd=linked, order_id="o1",
        run_engine=ED._run_engine, max_wait=120, run_dir=str(run_dir),
    )
    assert res["ok"] is True, res
    assert len(captured) == 1
    assert captured[0] == res["spawnedArgv"]
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["spawnedArgv"] == res["spawnedArgv"]
    assert captured[0] == state["spawnedArgv"]


def _review_repo(tmp_path):
    base = Path(tmp_path)
    base.mkdir(parents=True, exist_ok=True)
    root = base / "repo"
    root.mkdir()
    (root / ".git").write_text("gitdir: /fake/worktree\n", encoding="utf-8")
    return str(root)


def _fake_review_build_view(tmp_path):
    def build_view(repo_real):
        view_dir = tmp_path / "sanitized-view"
        view_dir.mkdir(parents=True, exist_ok=True)
        return {
            "path": str(view_dir),
            "strategy": "git-archive-export",
            "stripped": [],
            "strippedCount": 0,
            "headSha": "abc123fake",
            "sourceDirty": False,
            "buildSeconds": 0.01,
            "bytes": 1,
            "fileCount": 1,
        }
    return build_view


class _ReviewFakeRunner:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, argv, prompt_bytes, timeout, progress_cb, cwd):
        self.calls.append({"argv": list(argv), "cwd": cwd})
        idx = len(self.calls) - 1
        return self.responses[idx]


_VALID_REVIEW_STDOUT = json.dumps({"findings": [{"id": "f1", "message": "issue found"}]})


def test_dispatch_review_spawned_argv_echo(tmp_path, monkeypatch):
    repo_root = _review_repo(tmp_path)
    build_view = _fake_review_build_view(tmp_path)
    run_dir = tmp_path / "run-review"
    run_dir.mkdir(mode=0o700)
    captured = []
    real_files = ED._run_engine_files

    def _spy(argv, *args, **kwargs):
        captured.append(list(argv))
        return real_files(
            [
                "python3",
                "-c",
                "import sys; sys.stdout.write(%r)" % _VALID_REVIEW_STDOUT,
            ],
            *args,
            **kwargs,
        )

    monkeypatch.setattr(ED, "_run_engine_files", _spy)
    _inline_run_child_spawn(monkeypatch)
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_prompt(tmp_path), repo_root=repo_root, run_engine=ED._run_engine,
        build_view=build_view, run_dir=str(run_dir), max_wait=120,
    )
    assert res["ok"] is True, res
    assert len(captured) == 1
    assert captured[0] == res["spawnedArgv"]
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["spawnedArgv"] == res["spawnedArgv"]
    assert captured[0] == state["spawnedArgv"]


def test_dispatch_review_argv_never_workspace_write(tmp_path):
    """Review API end-to-end: dispatch_review argv must not carry workspace-write."""
    repo_root = _review_repo(tmp_path)
    build_view = _fake_review_build_view(tmp_path)
    prompt = _prompt(tmp_path)
    for i, (engine, model, effort) in enumerate(_review_argv_combinations()):
        run_dir = tmp_path / "review-sweep" / str(i)
        run_dir.mkdir(parents=True)
        fake = _ReviewFakeRunner([(_VALID_REVIEW_STDOUT, False, 0, "")])
        res = ED.dispatch_review(
            engine,
            model=model,
            effort=effort,
            prompt_path=prompt,
            repo_root=repo_root,
            run_engine=fake,
            build_view=build_view,
            run_dir=str(run_dir),
            max_wait=60,
        )
        assert res.get("ok") is True, (engine, model, effort, res)
        assert len(fake.calls) == 1
        _assert_spawned_argv_pair(res)
        assert "workspace-write" not in res["argv"]
        assert "workspace-write" not in res["spawnedArgv"]
        assert "workspace-write" not in fake.calls[0]["argv"]


def test_run_child_rejects_argv_drift_review(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir(mode=0o700)
    (run_dir / "prompt.txt").write_bytes(b"x")
    (run_dir / "review-cwd").mkdir()
    state = {
        "engine": "codex",
        "roleKind": "review",
        "effort": "high",
        "model": "sonnet",
        "argv": ["codex", "exec", "--sandbox", "read-only", "-m", "wrong",
                 "-c", "model_reasoning_effort=high", "-"],
        "engineBinary": shutil.which("codex") or "/usr/bin/false",
        "attemptTimeout": 5,
        "runNonce": "drift-r",
        "orderId": "",
    }
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    _invoke_run_child(run_dir, 1, state)
    done = json.loads((run_dir / "attempt-1.done").read_text(encoding="utf-8"))
    assert done.get("refusal") == "argv-rederivation-mismatch"


# --- A-1 / A-2 authority-model edges (WO-702 G1) ---


_WRITE_OK = json.dumps({"ok": True, "signal": "ok", "evidence": {}})


def _seed_write_run(tmp_path, linked, prompt, order_id="write-seed"):
    run_dir = tmp_path / "seed-write-run"
    run_dir.mkdir(mode=0o700)
    fake = FakeWriteRunner([(_WRITE_OK, False, 0, "")])
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id=order_id, run_engine=fake,
        max_wait=60, run_dir=str(run_dir),
    )
    assert res.get("ok") is True
    return str(run_dir)


def test_dispatch_review_run_dir_write_run_refuses_kind_mismatch(tmp_path, monkeypatch):
    main, linked = _linked_pair(tmp_path)
    prompt = _prompt(tmp_path)
    write_run = _seed_write_run(tmp_path, linked, prompt)
    spawned = []
    monkeypatch.setattr(ED, "_spawn_run_child", lambda *a, **k: spawned.append(1))
    repo_root = _review_repo(tmp_path)
    build_view = _fake_review_build_view(tmp_path)
    fake = _ReviewFakeRunner([])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=prompt, repo_root=repo_root, run_engine=fake,
        build_view=build_view, run_dir=write_run, max_wait=10,
    )
    assert res["reason"] == "run-kind-mismatch"
    assert res["attempts"] == 0
    assert res["forfeited"] is False
    assert res["terminal"] is True
    assert spawned == []


def test_dispatch_write_run_dir_review_run_refuses_kind_mismatch(tmp_path, monkeypatch):
    main, linked = _linked_pair(tmp_path)
    prompt = _prompt(tmp_path)
    repo_root = _review_repo(tmp_path)
    build_view = _fake_review_build_view(tmp_path)
    review_run = tmp_path / "seed-review-run"
    review_run.mkdir(mode=0o700)
    fake_r = _ReviewFakeRunner([(_VALID_REVIEW_STDOUT, False, 0, "")])
    res_r = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=prompt, repo_root=repo_root, run_engine=fake_r,
        build_view=build_view, run_dir=str(review_run), max_wait=60,
    )
    assert res_r.get("ok") is True
    spawned = []
    monkeypatch.setattr(ED, "_spawn_run_child", lambda *a, **k: spawned.append(1))
    fake_w = FakeWriteRunner([])
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="w1", run_engine=fake_w,
        run_dir=str(review_run), max_wait=10,
    )
    assert res["reason"] == "run-kind-mismatch"
    assert res["attempts"] == 0
    assert spawned == []


def test_run_child_refuses_expected_kind_mismatch(tmp_path):
    """A-1 via authority: review-shaped authority cannot drive a write cwd launch."""
    from dataclasses import replace
    main, linked = _linked_pair(tmp_path)
    run_dir = tmp_path / "run"
    run_dir.mkdir(mode=0o700)
    (run_dir / "prompt.txt").write_bytes(b"x")
    built = EA.build_argv_result(
        "codex", "build", "high",
        {"engine_model": "gpt-5.6-terra", "cwd": linked},
    )
    argv = built["argv"]
    state = {
        "engine": "codex",
        "roleKind": "build",
        "dispatchMode": ED.WRITE_DISPATCH_MODE,
        "effort": "high",
        "engineModel": "gpt-5.6-terra",
        "cwd": linked,
        "argv": argv,
        "engineBinary": shutil.which(argv[0]),
        "attemptTimeout": 5,
        "runNonce": "nonce-a",
        "orderId": "o1",
        "timeout": 5,
        "retryTimeout": 5,
    }
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    authority = _authority_from_state(run_dir, state)
    # Force review kind onto a write-shaped launch — child review path rejects write cwd.
    authority = replace(authority, run_kind=ED.RUN_KIND_REVIEW, role_kind="review")
    # Persist the *replaced* authority so run-child loads the disagreeing kind from seal.
    try:
        os.unlink(os.path.join(str(run_dir), ED.AUTHORITY_NAME))
    except FileNotFoundError:
        pass
    auth_hash = ED._persist_authority(authority)
    state["authorityHash"] = auth_hash
    state["runNonce"] = authority.run_nonce
    ED._seal_attempt_launch(str(run_dir), 1, authority, auth_hash, 5)
    ED._run_child_main(str(run_dir), 1, authority, authority_hash=auth_hash)
    done = json.loads((run_dir / "attempt-1.done").read_text(encoding="utf-8"))
    assert done.get("refusal") == "launch-cwd-mismatch"


def test_wrong_nonce_sentinel_not_terminal(tmp_path):
    main, linked = _linked_pair(tmp_path)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "nonce-run"
    run_dir.mkdir(mode=0o700)
    fake = FakeWriteRunner([(_WRITE_OK, False, 0, "")])
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="nonce-o", run_engine=fake,
        max_wait=60, run_dir=str(run_dir),
    )
    assert res.get("ok") is True
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    try:
        (run_dir / "result.json").unlink()
    except FileNotFoundError:
        pass
    (run_dir / "attempt-1.done").write_text(
        json.dumps({"exit": 0, "timedOut": False, "runNonce": "wrong-nonce"}),
        encoding="utf-8",
    )
    state["inFlightAttempt"] = 1
    state["completedAttempts"] = 0
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    poll = ED.dispatch_poll(str(run_dir), max_wait=0)
    assert poll.get("terminal") is False
    assert not (run_dir / "result.json").exists()


def test_forged_worktree_lease_path_cannot_unlink_victim(tmp_path):
    main, linked = _linked_pair(tmp_path)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "lease-run"
    run_dir.mkdir(mode=0o700)
    victim = tmp_path / "victim-lease.txt"
    victim.write_text("keep", encoding="utf-8")
    fake = FakeWriteRunner([(_WRITE_OK, False, 0, "")])
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="lease-o", run_engine=fake,
        max_wait=60, run_dir=str(run_dir),
    )
    assert res.get("ok") is True
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    state["worktreeLeasePath"] = str(victim)
    state["worktreeLeaseToken"] = None
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    auth = _authority_from_state(run_dir, state)
    ED._release_worktree_lease(auth)
    assert victim.read_text(encoding="utf-8") == "keep"


def test_blank_supervisor_metadata_forfeits_retry(tmp_path):
    main, linked = _linked_pair(tmp_path)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "sup-run"
    run_dir.mkdir(mode=0o700)
    (run_dir / "prompt.txt").write_bytes(b"build\n")
    built = EA.build_argv_result(
        "codex", "build", "high",
        {"engine_model": "gpt-5.6-terra", "cwd": linked},
    )
    argv = built["argv"]
    lease_token, lease_holder = ED._acquire_worktree_lease_for_cwd(
        os.path.realpath(linked))
    state = {
        "engine": "codex",
        "roleKind": "build",
        "dispatchMode": ED.WRITE_DISPATCH_MODE,
        "effort": "high",
        "engineModel": "gpt-5.6-terra",
        "cwd": linked,
        "argv": argv,
        "spawnedArgv": argv,
        "engineBinary": shutil.which(argv[0]),
        "timeout": 900,
        "retryTimeout": 900,
        "orderId": "sup-o",
        "runNonce": "sup-nonce",
        "worktreeLeaseToken": lease_token,
        "worktreeLeaseHolder": lease_holder,
        "worktreeSnapshot": list(ED._worktree_snapshot(linked)),
        "completedAttempts": 1,
        "inFlightAttempt": None,
        "pendingTerminal": "forfeited",
        "supervisorPid": None,
        "supervisorStart": "",
    }
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    # Attempt-1 already completed under a sealed launch — resume sees retry slot.
    (run_dir / "attempt-1.done").write_text(json.dumps({
        "exit": None, "timedOut": True, "runNonce": "sup-nonce",
        "endedAt": time.time(),
    }), encoding="utf-8")
    (run_dir / "attempt-1.stdout").write_text("", encoding="utf-8")
    (run_dir / "attempt-1.stderr").write_text("", encoding="utf-8")
    _bind_inflight(run_dir, state, attempt=1)
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="sup-o", run_engine=FakeWriteRunner([]),
        max_wait=120, run_dir=str(run_dir),
    )
    assert res["terminal"] is True
    assert res["detail"] == "retry-unsafe-missing-supervisor-metadata"
    assert res["forfeited"] is True
    ED._release_worktree_lease_for_cwd(os.path.realpath(linked), lease_token, lease_holder)


def test_run_dir_equals_cwd_refused(tmp_path):
    main, linked = _linked_pair(tmp_path)
    fake = FakeWriteRunner([])
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=_prompt(tmp_path), cwd=linked, order_id="eq-o",
        run_dir=linked, run_engine=fake,
    )
    assert res["detail"] == "run-dir-inside-cwd"
    assert res["attempts"] == 0


def test_symlink_tmp_does_not_truncate_victim(tmp_path):
    main, linked = _linked_pair(tmp_path)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "symlink-run"
    run_dir.mkdir(mode=0o700)
    victim = tmp_path / "victim-state.txt"
    victim.write_text("precious", encoding="utf-8")
    fake = FakeWriteRunner([(_WRITE_OK, False, 0, "")])
    ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="sym-o", run_engine=fake,
        max_wait=60, run_dir=str(run_dir),
    )
    trap = run_dir / "state.json.tmp"
    try:
        os.symlink(victim, trap)
    except OSError:
        pytest.skip("symlink not supported")
    state = {"engine": "codex", "roleKind": "build", "dispatchMode": "write", "effort": "high"}
    ED._atomic_write_json(str(run_dir / "state.json"), state)
    assert victim.read_text(encoding="utf-8") == "precious"


def test_run_dir_reused_order_id_refuses(tmp_path):
    main, linked = _linked_pair(tmp_path)
    prompt = _prompt(tmp_path)
    run_dir = _seed_write_run(tmp_path, linked, prompt, order_id="order-a")
    fake = FakeWriteRunner([])
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="order-b", run_engine=fake,
        run_dir=run_dir, max_wait=10,
    )
    assert res["reason"] == "run-dir-reused"
    assert res["attempts"] == 0


def test_preexisting_review_cwd_refused_not_deleted(tmp_path):
    repo_root = _review_repo(tmp_path)
    build_view = _fake_review_build_view(tmp_path)
    run_dir = tmp_path / "review-pre"
    run_dir.mkdir(mode=0o700)
    review_cwd = run_dir / ED.REVIEW_CWD_DIRNAME
    review_cwd.mkdir()
    marker = review_cwd / "marker.txt"
    marker.write_text("do-not-delete", encoding="utf-8")
    fake = _ReviewFakeRunner([])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=build_view, run_dir=str(run_dir), max_wait=10,
    )
    assert res["detail"] == "review-cwd-exists"
    assert marker.read_text(encoding="utf-8") == "do-not-delete"


# --- WO-702 G2: lifecycle and liveness (rulings A-3, A-4) ---


def _parse_resume_cli(cmd_line):
    import shlex
    parts = shlex.split(cmd_line)
    idx = next(i for i, t in enumerate(parts) if t.startswith("dispatch-"))
    return ED.main(parts[idx:])


def _seed_write_state_for_resume(tmp_path, linked, prompt, order_id="resume-o"):
    run_dir = tmp_path / "resume-run"
    run_dir.mkdir(mode=0o700)
    built = EA.build_argv_result(
        "codex", "build", "high",
        {"engine_model": "gpt-5.6-terra", "cwd": linked},
    )
    state = {
        "engine": "codex",
        "roleKind": "build",
        "dispatchMode": ED.WRITE_DISPATCH_MODE,
        "effort": "high",
        "engineModel": "gpt-5.6-terra",
        "cwd": linked,
        "argv": built["argv"],
        "orderId": order_id,
        "promptPath": prompt,
        "timeout": 900,
        "retryTimeout": 900,
    }
    return str(run_dir), state


def test_abandon_terminates_engine_process_group_not_supervisor_only(tmp_path):
    """Edge 1: abandon kills the authenticated engine process group (non-child)."""
    main, linked = _linked_pair(tmp_path)
    run_dir = tmp_path / "abandon-engine-pg"
    run_dir.mkdir(mode=0o700)
    marker = run_dir / "engine.pid"
    mid = subprocess.Popen(
        ["python3", "-c",
         "import subprocess, time\n"
         "p = subprocess.Popen(['python3', '-c', 'import time; time.sleep(120)'],"
         " start_new_session=True)\n"
         "open(%r, 'w').write(str(p.pid))\n"
         "p.wait()\n" % str(marker)],
        start_new_session=True,
    )
    for _ in range(100):
        if marker.exists() and marker.read_text().strip().isdigit():
            break
        time.sleep(0.05)
    pgid = int(marker.read_text().strip())
    try:
        os.waitpid(pgid, os.WNOHANG)
        raise AssertionError("engine unexpectedly a child of pytest")
    except ChildProcessError:
        pass
    paths = ED._attempt_paths(str(run_dir), 1)
    lease_token, lease_holder = ED._acquire_worktree_lease_for_cwd(os.path.realpath(linked))
    state = {
        "engine": "codex",
        "roleKind": "build",
        "dispatchMode": ED.WRITE_DISPATCH_MODE,
        "effort": "high",
        "cwd": os.path.realpath(linked),
        "argv": [],
        "engineBinary": "/bin/true",
        "runNonce": "abandon-n1",
        "orderId": "abandon-o1",
        "inFlightAttempt": 1,
        "completedAttempts": 0,
        "worktreeLeaseToken": lease_token,
        "worktreeLeaseHolder": lease_holder,
        "timeout": 5,
        "retryTimeout": 5,
    }
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    _persist_test_authority(run_dir, state)
    ED._write_engine_pgid(
        paths["engine_pgid"], pgid,
        run_nonce="abandon-n1", order_id="abandon-o1", attempt=1,
        cwd=os.path.realpath(linked), lease_token=lease_token,
        start_identity="test", authority_hash=state["authorityHash"],
    )
    try:
        res = ED.dispatch_abandon(str(run_dir))
        assert res.get("reason") == "abandoned", res
        time.sleep(0.3)
        try:
            os.killpg(pgid, 0)
            dead = False
        except OSError:
            dead = True
        assert dead
    finally:
        ED._release_worktree_lease_for_cwd(
            os.path.realpath(linked), lease_token, lease_holder)
        for target in (pgid, mid.pid):
            try:
                os.killpg(int(target), signal.SIGKILL)
            except OSError:
                pass



def test_abandon_engine_group_unconfirmed_lease_stays_held(tmp_path, monkeypatch):
    """Edge 2: unconfirmed engine death → lease held, named detail."""
    main, linked = _linked_pair(tmp_path)
    run_dir = tmp_path / "abandon-lease"
    run_dir.mkdir(mode=0o700)
    paths = ED._attempt_paths(str(run_dir), 1)
    lease_token, lease_holder = ED._acquire_worktree_lease_for_cwd(os.path.realpath(linked))
    import file_lock
    lease_path = ED._worktree_lease_path(os.path.realpath(linked))
    state = {
        "engine": "codex",
        "roleKind": "build",
        "dispatchMode": ED.WRITE_DISPATCH_MODE,
        "effort": "high",
        "cwd": os.path.realpath(linked),
        "argv": [],
        "engineBinary": "/bin/true",
        "runNonce": "abandon-n2",
        "orderId": "abandon-o2",
        "inFlightAttempt": 1,
        "worktreeLeaseToken": lease_token,
        "worktreeLeaseHolder": lease_holder,
        "timeout": 5,
        "retryTimeout": 5,
    }
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    _persist_test_authority(run_dir, state)
    ED._write_engine_pgid(
        paths["engine_pgid"], os.getpid(),
        run_nonce="abandon-n2", order_id="abandon-o2", attempt=1,
        cwd=os.path.realpath(linked), lease_token=lease_token,
        start_identity="test", authority_hash=state["authorityHash"],
    )
    monkeypatch.setattr(ED, "_terminate_process_group", lambda _pgid: False)
    try:
        res = ED.dispatch_abandon(str(run_dir))
        assert res.get("detail") == "engine-group-still-live"
        assert res.get("reason") == "abandon-incomplete"
        assert file_lock.read_holder(lease_path)
        assert not (run_dir / "result.json").exists()
    finally:
        ED._release_worktree_lease_for_cwd(
            os.path.realpath(linked), lease_token, lease_holder)


def test_run_engine_files_sweeps_descendants_on_normal_exit(tmp_path):
    """Edge 3: normal engine exit still kills the process group; leader rc preserved."""
    marker = tmp_path / "files_gc.pid"
    code = (
        "import os,signal,time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "pid=os.fork()\n"
        "if pid==0:\n"
        "    signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "    open(%r,'w').write(str(os.getpid()))\n"
        "    time.sleep(60)\n"
        "else:\n"
        "    time.sleep(0.3)\n" % str(marker)
    )
    stdout = tmp_path / "out.stdout"
    stderr = tmp_path / "out.stderr"
    prompt = tmp_path / "prompt.txt"
    prompt.write_bytes(b"x")
    auth = ED.LaunchAuthority(
        role_kind="build", run_kind=ED.RUN_KIND_WRITE, engine="codex", effort="high",
        model=None, engine_model=None, schema_path=None, argv=("python3",),
        spawned_argv=("python3",), engine_binary="/usr/bin/python3",
        cwd=str(tmp_path), order_id="sweep", run_nonce="sweep-n",
        run_dir=str(tmp_path), timeout=30, retry_timeout=30,
        lease_token=None, lease_holder=None, cleanup_roots=(),
        fed_prompt="", view_receipt={}, repo_root=None, prompt_path=None,
        progress_path=None, base_sha=None,
    )
    auth_hash = ED._persist_authority(auth)
    res = ED._run_engine_files(
        ["python3", "-c", code],
        str(prompt), str(stdout), str(stderr),
        30, None, 1, str(tmp_path),
        engine_pgid_path=str(tmp_path / "pgid.json"),
        authority=auth,
        authority_hash=auth_hash,
    )
    assert res.get("timedOut") is False
    assert res.get("exit") == 0
    time.sleep(0.5)
    gc = int(marker.read_text())
    try:
        os.kill(gc, 0)
        dead = False
    except OSError:
        dead = True
    assert dead


def test_dispatch_poll_never_spawns_on_retry_pending(tmp_path, monkeypatch):
    """Edge 4: poll stays observational when retry is pending — including write path."""
    main, linked = _linked_pair(tmp_path)
    run_dir = tmp_path / "poll-retry"
    run_dir.mkdir(mode=0o700)
    (run_dir / "prompt.txt").write_bytes(b"x")
    (run_dir / "attempt-1.done").write_text(json.dumps({
        "exit": None, "timedOut": True, "runNonce": "n1",
    }), encoding="utf-8")
    (run_dir / "attempt-1.stdout").write_text("", encoding="utf-8")
    (run_dir / "attempt-1.stderr").write_text("", encoding="utf-8")
    linked_real = os.path.realpath(linked)
    state = {
        "engine": "codex",
        "roleKind": "build",
        "dispatchMode": ED.WRITE_DISPATCH_MODE,
        "effort": "high",
        "engineModel": "gpt-5.6-terra",
        "cwd": linked_real,
        "argv": ["codex", "exec", "--sandbox", "workspace-write", "-"],
        "engineBinary": "/bin/true",
        "runNonce": "n1",
        "orderId": "poll-o",
        "promptPath": str(run_dir / "prompt.txt"),
        "fedPrompt": "",
        "inFlightAttempt": 1,
        "completedAttempts": 0,
        "attemptStartedAt": time.time(),
        "timeout": 5,
        "retryTimeout": 5,
        "worktreeLeaseToken": "tok",
        "worktreeLeaseHolder": {"pid": 1},
    }
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    _bind_inflight(run_dir, state)
    engine_calls = []
    monkeypatch.setattr(
        ED, "_run_engine_files",
        lambda *a, **k: engine_calls.append(1) or {
            "exit": 0, "timedOut": False, "signal": None,
            "endedAt": time.time(), "refusal": None,
        })
    spawned = []
    monkeypatch.setattr(ED, "_spawn_run_child", lambda *a, **k: spawned.append(1) or None)
    res = ED.dispatch_poll(str(run_dir), max_wait=1)
    assert res.get("terminal") is False
    assert ED.RETRY_PENDING_DETAIL in (res.get("detail") or "")
    assert spawned == []
    assert engine_calls == []
    assert not (run_dir / "attempt-2.stdout").exists()
    assert not list(run_dir.glob(".retry-parent-probe.*"))


def test_spawn_run_child_always_detached_review_and_write(tmp_path, monkeypatch):
    """Edge 1: _spawn_run_child returns a real child pid for attempts 1 and 2."""
    main, linked = _linked_pair(tmp_path)
    repo_root = _review_repo(tmp_path)
    (tmp_path / "review-run").mkdir(mode=0o700)
    review_run = str(tmp_path / "review-run")
    (Path(review_run) / ED.REVIEW_CWD_DIRNAME).mkdir()
    built_w = EA.build_argv_result(
        "codex", "build", "high",
        {"engine_model": "gpt-5.6-terra", "cwd": linked},
    )
    write_run = tmp_path / "write-run"
    write_run.mkdir(mode=0o700)
    (write_run / "prompt.txt").write_bytes(b"x")
    wstate = {
        "engine": "codex",
        "roleKind": "build",
        "dispatchMode": ED.WRITE_DISPATCH_MODE,
        "effort": "high",
        "engineModel": "gpt-5.6-terra",
        "cwd": linked,
        "argv": built_w["argv"],
        "runNonce": "spawn-nonce-w",
        "orderId": "spawn-w",
        "timeout": 5,
        "retryTimeout": 5,
    }
    (write_run / "state.json").write_text(json.dumps(wstate), encoding="utf-8")
    built_r = EA.build_argv_result("codex", "review", "high", {"model": "sonnet"})
    rstate = {
        "engine": "codex",
        "roleKind": "review",
        "effort": "high",
        "model": "sonnet",
        "argv": built_r["argv"],
        "runNonce": "spawn-nonce-r",
        "orderId": "",
        "repoRoot": repo_root,
        "timeout": 5,
        "retryTimeout": 5,
    }
    (Path(review_run) / "state.json").write_text(json.dumps(rstate), encoding="utf-8")
    wstate["engineBinary"] = shutil.which(built_w["argv"][0]) or "/bin/true"
    rstate["engineBinary"] = shutil.which(built_r["argv"][0]) or "/bin/true"
    (write_run / "state.json").write_text(json.dumps(wstate), encoding="utf-8")
    (Path(review_run) / "state.json").write_text(json.dumps(rstate), encoding="utf-8")
    procs = []
    try:
        for run_dir, state, launch_cwd in (
            (str(write_run), wstate, linked),
            (review_run, rstate, str(Path(review_run) / ED.REVIEW_CWD_DIRNAME)),
        ):
            authority = _persist_test_authority(run_dir, state, launch_cwd=launch_cwd)
            for attempt in (1, 2):
                ED._seal_attempt_launch(
                    run_dir, attempt, authority, state["authorityHash"], 5)
                proc = ED._spawn_run_child(
                    run_dir, attempt, authority, authority_hash=state["authorityHash"])
                _assert_spawn_detached(proc)
                procs.append(proc)
    finally:
        for proc in procs:
            try:
                proc.terminate()
            except OSError:
                pass
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()


def test_write_retry_supervisor_pid_is_child_not_launcher(tmp_path, monkeypatch):
    """Edge 2: attempt-2 supervisorPid is the detached child's pid."""
    main, linked = _linked_pair(tmp_path)
    _install_fake_codex_on_path(monkeypatch, tmp_path, slow_first_seconds=60)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "retry-sup-pid"
    run_dir.mkdir(mode=0o700)
    spawned_procs = []
    recorded_supervisor = {}
    real_spawn = ED._spawn_run_child
    real_atomic = ED._atomic_write_json

    def _track(rd, att, launch, authority_hash=None):
        proc = real_spawn(rd, att, launch, authority_hash=authority_hash)
        spawned_procs.append(proc)
        return proc

    def _spy_state(path, payload):
        if str(path).endswith("state.json") and isinstance(payload, dict):
            if payload.get("inFlightAttempt") == 2 and payload.get("supervisorPid"):
                recorded_supervisor["pid"] = payload["supervisorPid"]
        return real_atomic(path, payload)

    monkeypatch.setattr(ED, "_spawn_run_child", _track)
    monkeypatch.setattr(ED, "_atomic_write_json", _spy_state)
    first = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="retry-sup",
        run_engine=ED._run_engine, max_wait=1, timeout=5, run_dir=str(run_dir),
    )
    assert first.get("running") is True
    paths = ED._attempt_paths(str(run_dir), 1)
    for _ in range(80):
        if os.path.isfile(paths["done"]):
            break
        time.sleep(0.25)
    poll = ED.dispatch_poll(str(run_dir), max_wait=5)
    assert ED.RETRY_PENDING_DETAIL in (poll.get("detail") or "")
    state_after = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    _wait_process_dead(state_after.get("completedAttemptSupervisorPid"))
    second = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="retry-sup",
        run_engine=ED._run_engine, max_wait=120, timeout=5, run_dir=str(run_dir),
    )
    assert second.get("ok") is True, second
    assert len(spawned_procs) == 2
    assert recorded_supervisor.get("pid") == spawned_procs[1].pid
    assert recorded_supervisor.get("pid") != os.getpid()


def test_write_retry_attempt_two_durable_artifacts_from_child(tmp_path, monkeypatch):
    """Edge 3: attempt 2 writes stdout/stderr and sentinel in the child."""
    main, linked = _linked_pair(tmp_path)
    _install_fake_codex_on_path(monkeypatch, tmp_path, slow_first_seconds=60)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "retry-artifacts"
    run_dir.mkdir(mode=0o700)
    ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="retry-art",
        run_engine=ED._run_engine, max_wait=1, timeout=5, run_dir=str(run_dir),
    )
    paths1 = ED._attempt_paths(str(run_dir), 1)
    for _ in range(80):
        if os.path.isfile(paths1["done"]):
            break
        time.sleep(0.25)
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    nonce = state["runNonce"]
    poll = ED.dispatch_poll(str(run_dir), max_wait=5)
    assert ED.RETRY_PENDING_DETAIL in (poll.get("detail") or "")
    state_after = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    _wait_process_dead(state_after.get("completedAttemptSupervisorPid"))
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="retry-art",
        run_engine=ED._run_engine, max_wait=120, timeout=5, run_dir=str(run_dir),
    )
    assert res.get("ok") is True, res
    paths2 = ED._attempt_paths(str(run_dir), 2)
    assert os.path.isfile(paths2["stdout"])
    assert os.path.isfile(paths2["stderr"])
    assert os.path.isfile(paths2["done"])
    done = json.loads(Path(paths2["done"]).read_text(encoding="utf-8"))
    assert done.get("runNonce") == nonce
    assert done.get("endedAt") is not None


def test_write_retry_reinvoke_respects_max_wait(tmp_path, monkeypatch):
    """Edge 4: re-invoke after forfeit returns running within max_wait while retry is long.

    Exercises real supervisor liveness (wait for death) — no ``_process_alive`` mock.
    """
    main, linked = _linked_pair(tmp_path)
    _install_fake_codex_on_path(
        monkeypatch, tmp_path, slow_first_seconds=60, slow_by_attempt={2: 60})
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "retry-bounded"
    run_dir.mkdir(mode=0o700)
    t0 = time.monotonic()
    first = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="retry-bounded",
        run_engine=ED._run_engine, max_wait=2, timeout=5, run_dir=str(run_dir),
    )
    assert time.monotonic() - t0 < 15, time.monotonic() - t0
    assert first.get("terminal") is False
    assert first.get("running") is True
    paths = ED._attempt_paths(str(run_dir), 1)
    for _ in range(80):
        if os.path.isfile(paths["done"]):
            break
        time.sleep(0.25)
    poll = ED.dispatch_poll(str(run_dir), max_wait=5)
    assert ED.RETRY_PENDING_DETAIL in (poll.get("detail") or "")
    state_after = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    _wait_process_dead(state_after.get("completedAttemptSupervisorPid"))
    t1 = time.monotonic()
    second = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="retry-bounded",
        run_engine=ED._run_engine, max_wait=2, timeout=5, run_dir=str(run_dir),
    )
    elapsed2 = time.monotonic() - t1
    assert elapsed2 < 15, elapsed2
    assert second.get("terminal") is False, second
    assert second.get("running") is True
    assert second.get("resume")
    assert os.path.isfile(ED._attempt_paths(str(run_dir), 2)["supervisor"]) or (
        json.loads((run_dir / "state.json").read_text(encoding="utf-8")).get(
            "inFlightAttempt") == 2)


def test_write_retry_spawns_once_after_poll_then_resume(tmp_path, monkeypatch):
    """Edge 5: poll → retry-pending → re-invoke reaches terminal in exactly one retry."""
    main, linked = _linked_pair(tmp_path)
    _install_fake_codex_on_path(monkeypatch, tmp_path, slow_first_seconds=60)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "retry-detached"
    run_dir.mkdir(mode=0o700)
    spawned_children = []
    real_spawn = ED._spawn_run_child

    def _track_spawn(rd, att, launch, authority_hash=None):
        spawned_children.append(att)
        proc = real_spawn(rd, att, launch, authority_hash=authority_hash)
        _assert_spawn_detached(proc)
        return proc

    monkeypatch.setattr(ED, "_spawn_run_child", _track_spawn)
    t0 = time.monotonic()
    first = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="retry-det",
        run_engine=ED._run_engine, max_wait=1, timeout=5, run_dir=str(run_dir),
    )
    assert time.monotonic() - t0 < 15
    assert first.get("terminal") is False
    assert first.get("running") is True
    assert spawned_children == [1]
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    nonce = state["runNonce"]
    paths = ED._attempt_paths(str(run_dir), 1)
    for _ in range(80):
        if os.path.isfile(paths["done"]):
            break
        time.sleep(0.25)
    assert os.path.isfile(paths["done"])
    poll = ED.dispatch_poll(str(run_dir), max_wait=5)
    assert poll.get("terminal") is False
    assert ED.RETRY_PENDING_DETAIL in (poll.get("detail") or "")
    assert spawned_children == [1]
    state_after = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    _wait_process_dead(state_after.get("completedAttemptSupervisorPid"))
    second = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="retry-det",
        run_engine=ED._run_engine, max_wait=120, timeout=5, run_dir=str(run_dir),
    )
    assert second.get("ok") is True, second
    assert second.get("terminal") is True
    assert spawned_children == [1, 2]
    assert nonce == state["runNonce"]
    assert os.path.isfile(ED._attempt_paths(str(run_dir), 2)["stdout"])


def test_resume_commands_parse_review_write_and_space_run_dir(tmp_path):
    """Edge 5: emitted resume commands parse under the module CLI."""
    main, linked = _linked_pair(tmp_path)
    prompt = _prompt(tmp_path)
    run_dir, wstate = _seed_write_state_for_resume(tmp_path, linked, prompt)
    run_dir_sp = str(tmp_path / "run with spaces")
    os.makedirs(run_dir_sp, mode=0o700)
    wauth = _authority_from_state(run_dir, wstate)
    wauth_sp = _authority_from_state(run_dir_sp, wstate)
    cmd_w = ED._resume_command_write(run_dir_sp, 540, wauth_sp)
    assert _parse_resume_cli(cmd_w) == 0
    rstate = {
        "engine": "codex",
        "roleKind": "review",
        "effort": "high",
        "model": "sonnet",
        "repoRoot": main,
        "promptPath": prompt,
        "orderId": "r1",
        "argv": ["codex"],
        "engineBinary": "/bin/true",
        "runNonce": "r-nonce",
        "timeout": 5,
        "retryTimeout": 5,
    }
    rauth = _authority_from_state(run_dir_sp, rstate)
    cmd_r = ED._resume_command_review(run_dir_sp, 540, rauth)
    assert _parse_resume_cli(cmd_r) == 0
    cmd_w2 = ED._resume_command_write(run_dir, 540, wauth)
    assert _parse_resume_cli(cmd_w2) == 0
    lease_res = ED._running_result(
        run_dir, wauth, 1, list(wauth.argv), 0, 540,
        detail="worktree-lease-held",
    )
    assert _parse_resume_cli(lease_res["resume"]) == 0


def test_supervisor_dead_becomes_forfeit_not_eternal_running(tmp_path, monkeypatch):
    """Edge 6: dead supervisor + grace → synthetic forfeit, not eternal running."""
    monkeypatch.setattr(ED, "SUPERVISOR_DEAD_GRACE_SECONDS", 0)
    run_dir = tmp_path / "sup-dead"
    run_dir.mkdir(mode=0o700)
    (run_dir / "state.json").write_text(json.dumps({
        "engine": "codex",
        "roleKind": "review",
        "effort": "high",
        "model": "sonnet",
        "argv": ["codex"],
        "runNonce": "dead-n",
        "repoRoot": str(tmp_path),
        "promptPath": str(run_dir / "p.txt"),
        "viewReceipt": {},
        "fedPrompt": "x",
        "inFlightAttempt": 1,
        "completedAttempts": 0,
        "supervisorPid": 999999991,
        "supervisorStart": "not-a-real-start",
        "attemptStartedAt": time.time() - 60,
    }), encoding="utf-8")
    (run_dir / "attempt-1.stdout").write_text("", encoding="utf-8")
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    state.setdefault("engineBinary", "/bin/true")
    state.setdefault("timeout", 5)
    state.setdefault("retryTimeout", 5)
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    _bind_inflight(run_dir, state)
    res = ED.dispatch_poll(str(run_dir), max_wait=0)
    assert res.get("terminal") is False
    assert ED.RETRY_PENDING_DETAIL in (res.get("detail") or "")


def test_spawn_failed_compensates_state_and_lease(tmp_path, monkeypatch):
    """Edge 7: failed supervisor spawn persists terminal result and releases write lease.

    A sealed ledger intent alone is not live-child evidence — lease must still release.
    """
    main, linked = _linked_pair(tmp_path)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "spawn-fail"
    run_dir.mkdir(mode=0o700)
    monkeypatch.setattr(ED, "_spawn_run_child", lambda *a, **k: None)
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="sf-o",
        run_engine=ED._run_engine, max_wait=10, run_dir=str(run_dir),
    )
    assert res.get("detail") == "supervisor-spawn-failed"
    assert (run_dir / "result.json").is_file()
    st = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert st.get("inFlightAttempt") is None
    # Intent is sealed before spawn; prove it was present so the release is the
    # live-evidence rule, not the accidental absence of an intent.
    auth = ED._load_authority(str(run_dir))
    assert auth is not None
    run_real = os.path.realpath(str(run_dir))
    auth_hash = ED._ledger_expected_hash(run_real, auth.run_nonce, auth.order_id)
    intent = ED._ledger_attempt_intent(run_real, 1, auth_hash, auth.run_nonce)
    assert intent is not None, "spawn-fail path seals intent before spawn"
    assert ED._ledger_attempt_claim(run_real, 1, auth_hash, auth.run_nonce) is None
    import file_lock
    assert not file_lock.read_holder(ED._worktree_lease_path(os.path.realpath(linked)))


def test_spawn_failed_retains_lease_on_live_claim(tmp_path, monkeypatch):
    """Spawn failure while a ledger claim names a live pid → lease retained."""
    main, linked = _linked_pair(tmp_path)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "spawn-fail-live-claim"
    run_dir.mkdir(mode=0o700)
    live_pid = os.getpid()

    def _spawn_seal_live_claim_then_fail(rd, attempt, authority, authority_hash=None):
        run_real = os.path.realpath(rd)
        claim_path = ED._ledger_attempt_path(run_real, attempt, "claim")
        ED._ledger_seal(claim_path, {
            "schemaVersion": ED.LEDGER_SCHEMA_VERSION,
            "attempt": int(attempt),
            "authorityHash": authority_hash,
            "runNonce": authority.run_nonce,
            "childPid": live_pid,
            "childStart": ED._supervisor_lstart(live_pid) or "test-live",
        })
        return None

    monkeypatch.setattr(ED, "_spawn_run_child", _spawn_seal_live_claim_then_fail)
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="sf-live-o",
        run_engine=ED._run_engine, max_wait=10, run_dir=str(run_dir),
    )
    assert res.get("detail") == "supervisor-spawn-failed", res
    assert "live claimed run-child" in (res.get("disclosure") or ""), res
    assert _lease_held_for(linked)
    auth = ED._load_authority(str(run_dir))
    if auth is not None:
        ED._release_worktree_lease(auth)

def test_read_stdout_file_bounded_tail_read(tmp_path, monkeypatch):
    """Edge 8: stdout fold reads a bounded tail without loading the whole file."""
    monkeypatch.setattr(ED, "MAX_STDOUT_CAPTURE", 128)
    p = tmp_path / "huge.stdout"
    p.write_bytes(b"a" * 10_000 + b"MARKER-TAIL-END")
    out = ED._read_stdout_file(str(p))
    assert "MARKER-TAIL-END" in out
    assert len(out.encode("utf-8")) <= 128


def test_wedged_git_preflight_returns_named_refusal(tmp_path, monkeypatch):
    """Edge 9: git preflight timeout → attempts 0 refusal, no spawn."""
    main, linked = _linked_pair(tmp_path)

    def _timeout_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs.get("timeout"))

    monkeypatch.setattr(ED.subprocess, "run", _timeout_run)
    fake = FakeWriteRunner([])
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=_prompt(tmp_path), cwd=linked, order_id="git-o",
        run_engine=fake, max_wait=30,
    )
    assert res.get("detail") == "git-preflight-timeout"
    assert res.get("attempts") == 0
    assert len(fake.calls) == 0


def test_dispatch_review_creates_missing_run_dir(tmp_path):
    """Edge 10: dispatch-review creates a not-yet-existing --run-dir like dispatch-write."""
    repo_root = _review_repo(tmp_path)
    build_view = _fake_review_build_view(tmp_path)
    run_dir = tmp_path / "brand new" / "review-run"
    assert not run_dir.exists()
    fake = _ReviewFakeRunner([(_VALID_REVIEW_STDOUT, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=build_view, run_dir=str(run_dir), max_wait=60,
    )
    assert res.get("ok") is True
    assert run_dir.is_dir()


# --- WO-702-N: real run-child end-to-end (no injected run_engine seam) ---


def _var_symlink_dispatch_parent():
    """Run-dir parent under macOS /var spelling that realpath canonicalizes differently."""
    direct = tempfile.mkdtemp(prefix="dispatch-e2e-")
    if direct.startswith("/private/var/"):
        alias = "/var" + direct[len("/private/var"):]
        if os.path.exists(alias) and os.path.samefile(direct, alias):
            return alias
    if direct.startswith("/var/") and os.path.realpath(direct) != direct:
        return direct
    if direct.startswith("/private/var/"):
        pytest.skip("need /var spelling for dispatch parent")
    pytest.skip("need macOS /var -> /private/var TMPDIR layout")


def _sentinel_refusal_tokens(run_dir):
    tokens = []
    rd = Path(run_dir)
    for attempt in (1, 2):
        done = rd / ("attempt-%d.done" % attempt)
        if not done.is_file():
            continue
        data = json.loads(done.read_text(encoding="utf-8"))
        refusal = data.get("refusal")
        if refusal:
            tokens.append(refusal)
    return tokens


def _wait_for_result_json(run_dir, timeout_s=120):
    deadline = time.monotonic() + timeout_s
    result_path = Path(run_dir) / "result.json"
    while time.monotonic() < deadline:
        if result_path.is_file():
            return json.loads(result_path.read_text(encoding="utf-8"))
        time.sleep(0.25)
    return None


def test_e2e_review_run_child_real_spawn_terminal_success(tmp_path, monkeypatch):
    """Real detached run-child + stub codex on PATH; no run_engine injection.

    Proves the real subprocess path ran: supervisor/child artifacts exist, and
    the injected ``_execute_injected_attempt`` seam was never entered.
    """
    _install_fake_codex_on_path(monkeypatch, tmp_path, ok_stdout=_VALID_REVIEW_STDOUT, slow_first_seconds=0)
    injected_calls = []
    real_injected = ED._execute_injected_attempt

    def _track_injected(*a, **k):
        injected_calls.append(1)
        return real_injected(*a, **k)

    monkeypatch.setattr(ED, "_execute_injected_attempt", _track_injected)
    spawned = []
    real_spawn = ED._spawn_run_child

    def _track_spawn(rd, att, auth, authority_hash=None):
        proc = real_spawn(rd, att, auth, authority_hash=authority_hash)
        spawned.append((att, proc.pid if proc is not None else None))
        return proc

    monkeypatch.setattr(ED, "_spawn_run_child", _track_spawn)
    repo_root = _review_repo(tmp_path)
    build_view = _fake_review_build_view(tmp_path)
    res = ED.dispatch_review(
        "codex",
        model="sonnet",
        effort="high",
        prompt_path=_prompt(tmp_path),
        repo_root=repo_root,
        run_engine=ED._run_engine,
        build_view=build_view,
        max_wait=120,
        timeout=30,
    )
    run_dir = res.get("runDir")
    assert run_dir
    if not res.get("ok"):
        polled = _wait_for_result_json(run_dir)
        if polled:
            res = polled
    assert res.get("ok") is True, res
    assert injected_calls == [], "injected run-engine seam must not run on real path"
    assert spawned, "real _spawn_run_child must have been called"
    assert (Path(run_dir) / "supervisor-1.log").is_file(), (
        "real run-child writes supervisor-1.log; missing ⇒ injected seam or bypass")
    assert (Path(run_dir) / "attempt-1.launch.json").is_file()
    assert (Path(run_dir) / "attempt-1.done").is_file()
    engagement = res.get("engagement") or {}
    stdout_bytes = engagement.get("stdoutBytes", 0)
    if stdout_bytes <= 0:
        stdout_path = Path(run_dir) / "attempt-1.stdout"
        if stdout_path.is_file():
            stdout_bytes = stdout_path.stat().st_size
    assert stdout_bytes > 0
    assert os.path.isfile(os.path.join(run_dir, "result.json"))
    mismatch = {
        "argv-rederivation-mismatch",
        "engine-binary-mismatch",
        "cwd-authorization-mismatch",
    }
    for tok in _sentinel_refusal_tokens(run_dir):
        assert tok not in mismatch, tok


def test_e2e_write_run_child_real_spawn_terminal_success(tmp_path, monkeypatch):
    """Real detached run-child for write dispatch; linked worktree + stub codex on PATH."""
    main, linked = _linked_pair(tmp_path)
    parent = _var_symlink_dispatch_parent()
    run_dir = os.path.join(parent, "write-e2e")
    os.makedirs(run_dir, mode=0o700)
    _install_fake_codex_on_path(monkeypatch, tmp_path, slow_first_seconds=0)
    res = ED.dispatch_write(
        "codex",
        engine_model="gpt-5.6-terra",
        effort="high",
        prompt_path=_prompt(tmp_path),
        cwd=linked,
        order_id="e2e-write",
        run_engine=ED._run_engine,
        run_dir=run_dir,
        max_wait=120,
        timeout=30,
    )
    if not res.get("ok"):
        polled = _wait_for_result_json(run_dir)
        if polled:
            res = polled
    assert res.get("ok") is True, res
    engagement = res.get("engagement") or {}
    stdout_bytes = engagement.get("stdoutBytes", 0)
    if stdout_bytes <= 0:
        stdout_path = Path(run_dir) / "attempt-1.stdout"
        if stdout_path.is_file():
            stdout_bytes = stdout_path.stat().st_size
    assert stdout_bytes > 0
    mismatch = {
        "argv-rederivation-mismatch",
        "engine-binary-mismatch",
        "cwd-authorization-mismatch",
    }
    for tok in _sentinel_refusal_tokens(run_dir):
        assert tok not in mismatch, tok


def test_authority_required_structurally():
    """Edge: consumers require LaunchAuthority — omitting raises TypeError, no state fallback."""
    import pytest
    with pytest.raises(TypeError):
        ED._continue_run("/tmp/nope", deadline=0, max_wait=0, allow_spawn=False)
    with pytest.raises(TypeError):
        ED._spawn_run_child("/tmp/nope", 1)
    with pytest.raises(TypeError):
        ED._destroy_review_views("/tmp/nope", None)
    with pytest.raises(TypeError):
        ED._fold_terminal_write("/tmp/nope", None, [], {}, "forfeited", None, 1)


# --- WO-702-Q: B-3 real run-child structural guarantees + survivors ---


def _authority_path(run_dir):
    return os.path.join(str(run_dir), ED.AUTHORITY_NAME)


def _setup_write_fold_ready(tmp_path, linked, *, order_id="fold-hash"):
    """Seal a write run with a success-shaped attempt sentinel ready to fold.

    Returns (run_dir, authority, authority_hash, argv).
    """
    run_dir = tmp_path / ("fold-" + order_id)
    run_dir.mkdir(mode=0o700)
    prompt = _prompt(tmp_path)
    fake = FakeWriteRunner([(_WRITE_OK_STDOUT, False, 0, "")])
    seeded = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id=order_id,
        run_engine=fake, max_wait=60, run_dir=str(run_dir),
    )
    assert seeded.get("ok") is True, seeded
    authority = ED._load_authority(str(run_dir))
    assert authority is not None
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    auth_hash = state.get("authorityHash")
    assert auth_hash
    # Clear terminal result so a subsequent fold can write a new one.
    try:
        (run_dir / "result.json").unlink()
    except FileNotFoundError:
        pass
    return run_dir, authority, auth_hash, list(authority.argv)


def _swap_sealed_authority(run_dir, authority, **replace_fields):
    """Unlink the sealed file and write a different valid authority payload."""
    from dataclasses import replace
    path = _authority_path(run_dir)
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    swapped = replace(authority, **replace_fields)
    return ED._persist_authority(swapped), swapped


def test_fold_refuses_swapped_sealed_authority_hash_mismatch(tmp_path):
    """Edge 1 / B-3: swapped launch-authority.json is refused at fold."""
    main, linked = _linked_pair(tmp_path)
    run_dir, authority, auth_hash, argv = _setup_write_fold_ready(
        tmp_path, linked, order_id="swap-auth")
    # After seal + sentinel, replace sealed bytes with different valid JSON.
    _swap_sealed_authority(
        run_dir, authority, run_kind=ED.RUN_KIND_REVIEW, role_kind="review",
        cwd=os.path.join(str(run_dir), ED.REVIEW_CWD_DIRNAME))
    assert ED._authority_file_hash(str(run_dir)) != auth_hash
    engagement = {"engine": "codex", "stdoutBytes": 1}
    result = ED._fold_terminal_write(
        str(run_dir), authority, argv, engagement, "success",
        {"ok": True, "signal": "ok", "evidence": {}}, 1,
        authority_hash=auth_hash,
    )
    assert result.get("ok") is False, result
    assert result.get("detail") == ED.AUTHORITY_HASH_MISMATCH, result
    assert result.get("reason") == "unrunnable", result
    # Must not produce a trusted success terminal.
    on_disk = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    assert on_disk.get("ok") is not True
    assert on_disk.get("detail") == ED.AUTHORITY_HASH_MISMATCH


def test_fold_refuses_recreated_sealed_authority_nonidentical_bytes(tmp_path):
    """Edge 2 / B-3: unlink+recreate with non-identical bytes refused at fold.

    Identical-byte recreate is pinned as legitimate pass (O_EXCL does not
    prevent recreate; hash equality is the mechanism).
    """
    main, linked = _linked_pair(tmp_path)
    run_dir, authority, auth_hash, argv = _setup_write_fold_ready(
        tmp_path, linked, order_id="recreate-auth")
    path = _authority_path(run_dir)
    original = open(path, "rb").read()

    # Non-identical recreate (different cwd string in payload).
    new_hash, _ = _swap_sealed_authority(
        run_dir, authority, order_id=authority.order_id + "-mutated")
    assert new_hash != auth_hash
    result = ED._fold_terminal_write(
        str(run_dir), authority, argv, {}, "success",
        {"ok": True, "signal": "ok", "evidence": {}}, 1,
        authority_hash=auth_hash,
    )
    assert result.get("ok") is False, result
    assert result.get("detail") == ED.AUTHORITY_HASH_MISMATCH, result

    # Identical-byte recreate: semantics pinned — hash match must pass verify.
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    # Independent write of the same bytes (not the original inode).
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    fd = os.open(path, flags, 0o400)
    try:
        os.write(fd, original)
    finally:
        os.close(fd)
    assert ED._authority_file_hash(str(run_dir)) == auth_hash
    assert ED._verify_authority_hash_at_fold(str(run_dir), auth_hash) is True
    # Fold with matching hash must not refuse on hash mismatch.
    try:
        (run_dir / "result.json").unlink()
    except FileNotFoundError:
        pass
    ok_fold = ED._fold_terminal_write(
        str(run_dir), authority, argv, {"engine": "codex"}, "success",
        {"ok": True, "signal": "ok", "evidence": {}}, 1,
        authority_hash=auth_hash,
    )
    assert ok_fold.get("detail") != ED.AUTHORITY_HASH_MISMATCH, ok_fold
    assert ok_fold.get("ok") is True, ok_fold


def test_fold_refuses_truncated_sealed_authority(tmp_path):
    """Edge 3 / B-3: truncated/torn sealed authority is never trusted at fold."""
    main, linked = _linked_pair(tmp_path)
    run_dir, authority, auth_hash, argv = _setup_write_fold_ready(
        tmp_path, linked, order_id="trunc-auth")
    path = _authority_path(run_dir)
    raw = open(path, "rb").read()
    assert len(raw) > 8
    os.chmod(path, 0o600)
    with open(path, "wb") as fh:
        fh.write(raw[: max(1, len(raw) // 4)])
    os.chmod(path, 0o400)
    assert ED._verify_authority_hash_at_fold(str(run_dir), auth_hash) is False
    result = ED._fold_terminal_write(
        str(run_dir), authority, argv, {}, "success",
        {"ok": True, "signal": "ok", "evidence": {}}, 1,
        authority_hash=auth_hash,
    )
    assert result.get("ok") is False, result
    assert result.get("detail") == ED.AUTHORITY_HASH_MISMATCH, result
    assert result.get("reason") == "unrunnable", result
    on_disk = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    assert on_disk.get("ok") is not True


def test_e2e_a1_kind_mismatch_refuses_pre_spawn_no_engine(tmp_path, monkeypatch):
    """B-3 / A-1: otherwise-valid write run_dir refused by review verb on kind alone.

    The only defect is run_kind (write authority vs review verb). Cwd and other
    launch fields stay valid so the refusal must be ``run-kind-mismatch``, not a
    cwd guard.
    """
    main, linked = _linked_pair(tmp_path)
    _install_fake_codex_on_path(monkeypatch, tmp_path, slow_first_seconds=0)
    prompt = _prompt(tmp_path)
    write_run = _seed_write_run(tmp_path, linked, prompt, order_id="a1-kind-e2e")
    # Clear cache so re-entry hits the kind gate (not a cached success).
    try:
        (Path(write_run) / "result.json").unlink()
    except FileNotFoundError:
        pass
    spawned = []
    real_spawn = ED._spawn_run_child

    def _track_spawn(*a, **k):
        spawned.append(1)
        return real_spawn(*a, **k)

    monkeypatch.setattr(ED, "_spawn_run_child", _track_spawn)
    repo_root = _review_repo(tmp_path)
    build_view = _fake_review_build_view(tmp_path)
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=prompt, repo_root=repo_root, run_engine=ED._run_engine,
        build_view=build_view, run_dir=write_run, max_wait=10,
    )
    assert res["reason"] == "run-kind-mismatch", res
    assert res.get("ok") is False
    assert res.get("terminal") is True
    assert res.get("attempts") == 0
    assert spawned == [], "A-1 must refuse before spawn"
    marker = Path(linked) / ".fake-codex-invokes"
    assert not marker.exists(), "engine process started despite A-1 kind refusal"


def test_e2e_a4_poll_no_spawn_absent_attempt2_artifacts(tmp_path, monkeypatch):
    """B-3 / A-4: forfeited attempt-1 then dispatch-poll creates no attempt-2 artifacts."""
    main, linked = _linked_pair(tmp_path)
    _install_fake_codex_on_path(monkeypatch, tmp_path, slow_first_seconds=60)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "a4-poll"
    run_dir.mkdir(mode=0o700)
    spawned = []
    real_spawn = ED._spawn_run_child

    def _track_spawn(*a, **k):
        spawned.append((a, k))
        return real_spawn(*a, **k)

    monkeypatch.setattr(ED, "_spawn_run_child", _track_spawn)
    first = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="a4-o",
        run_engine=ED._run_engine, max_wait=1, timeout=5, run_dir=str(run_dir),
    )
    assert first.get("running") is True
    paths1 = ED._attempt_paths(str(run_dir), 1)
    for _ in range(80):
        if os.path.isfile(paths1["done"]):
            break
        time.sleep(0.25)
    assert os.path.isfile(paths1["done"])
    spawns_before_poll = len(spawned)
    poll = ED.dispatch_poll(str(run_dir), max_wait=5, order_id="a4-o")
    assert poll.get("terminal") is False, poll
    assert ED.RETRY_PENDING_DETAIL in (poll.get("detail") or ""), poll
    assert len(spawned) == spawns_before_poll, (
        "dispatch_poll must not call _spawn_run_child (spawned=%s)" % spawned)
    assert not any(
        (a[1] if len(a) > 1 else None) == 2 for a, _k in spawned), spawned
    assert not (run_dir / "attempt-2.stdout").exists()
    assert not (run_dir / "attempt-2.stderr").exists()
    assert not (run_dir / "attempt-2.done").exists()
    # Real artifact name from _attempt_paths — not the nonexistent attempt-2.supervisor.
    assert not (run_dir / "supervisor-2.log").exists()
    assert not (run_dir / "attempt-2.launch.json").exists()
    intent2 = ED._ledger_attempt_path(
        os.path.realpath(str(run_dir)), 2, "intent")
    assert intent2 is None or not os.path.isfile(intent2), intent2
    assert not list(run_dir.glob(".retry-parent-probe.*"))
    marker = Path(linked) / ".fake-codex-invokes"
    # Attempt 1 may have started the stub; attempt 2 must not.
    invokes = int(marker.read_text()) if marker.exists() else 0
    assert invokes <= 1, "poll must not start a second engine process (invokes=%s)" % invokes


def test_e2e_b1_authority_wins_over_disagreeing_state(tmp_path, monkeypatch):
    """B-3 / B-1: real child follows launch authority cwd when state names another
    independently valid linked worktree — authority wins over state.
    """
    from dataclasses import replace
    main, linked_auth, linked_state = _two_linked_worktrees(tmp_path)
    _install_fake_codex_on_path(monkeypatch, tmp_path, slow_first_seconds=0)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "b1-auth"
    run_dir.mkdir(mode=0o700)
    # Seed a completed write run bound to linked_auth so authority + argv exist.
    fake = FakeWriteRunner([(_WRITE_OK_STDOUT, False, 0, "")])
    seeded = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked_auth, order_id="b1-o",
        run_engine=fake, max_wait=60, run_dir=str(run_dir),
    )
    assert seeded.get("ok") is True, seeded
    try:
        (run_dir / "result.json").unlink()
    except FileNotFoundError:
        pass
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    authority = ED._load_authority(str(run_dir))
    assert authority is not None
    assert os.path.realpath(authority.cwd) == os.path.realpath(linked_auth)
    # Both cwds are valid linked worktrees; only the *source* differs.
    assert os.path.isdir(linked_state)
    ok_state, _ = ED._validate_linked_build_cwd(linked_state)
    assert ok_state, "forged state cwd must be independently valid"
    ok_auth, _ = ED._validate_linked_build_cwd(linked_auth)
    assert ok_auth, "authority cwd must be independently valid"
    # Forge state cwd to the other valid worktree — authority must still win.
    state["cwd"] = linked_state
    state["orderId"] = "forged-other-order"
    state["inFlightAttempt"] = None
    state["completedAttempts"] = 0
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    forged_poll = ED.dispatch_poll(str(run_dir), max_wait=0, order_id="forged-other-order")
    assert forged_poll.get("reason") == "run-dir-reused", forged_poll
    ok_poll = ED.dispatch_poll(str(run_dir), max_wait=0, order_id="b1-o")
    assert ok_poll.get("reason") != "run-dir-reused", ok_poll

    for stale in run_dir.glob("attempt-1.*"):
        try:
            stale.unlink()
        except OSError:
            pass
    try:
        os.unlink(run_dir / "attempt-1.launch.json")
    except FileNotFoundError:
        pass
    # Re-bind lease on the authority cwd and re-seal for a fresh real spawn.
    lease_token, lease_holder = ED._acquire_worktree_lease_for_cwd(
        os.path.realpath(linked_auth))
    try:
        auth = replace(
            authority,
            lease_token=lease_token,
            lease_holder=lease_holder,
            run_dir=str(run_dir),
            cwd=str(linked_auth),
        )
        try:
            os.unlink(run_dir / ED.AUTHORITY_NAME)
        except FileNotFoundError:
            pass
        auth_hash = ED._persist_authority(auth)
        # Re-seal the supervisor ledger for the replaced authority (same run_dir;
        # ledger records are O_EXCL — drop the prior record so the new hash binds).
        prior_ledger = ED._ledger_run_record_path(os.path.realpath(str(run_dir)))
        if prior_ledger and os.path.isfile(prior_ledger):
            os.chmod(prior_ledger, 0o600)
            os.unlink(prior_ledger)
        ED._ledger_init(auth, auth_hash)
        # Drop prior attempt ledger records (sealed 0400) so _seal_attempt_launch
        # can O_EXCL-seal a fresh intent bound to the new hash — same pattern as
        # the run record above. Without this, FileExistsError preserves the old
        # intent and run-child finds nothing pending for the new hash.
        run_real = os.path.realpath(str(run_dir))
        for suffix in ("intent", "claim", "complete"):
            prior = ED._ledger_attempt_path(run_real, 1, suffix)
            if prior and os.path.isfile(prior):
                os.chmod(prior, 0o600)
                os.unlink(prior)
        # State still names the *other* valid cwd.
        state["cwd"] = linked_state
        state["authorityHash"] = auth_hash
        state["worktreeLeaseToken"] = lease_token
        (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
        ED._seal_attempt_launch(str(run_dir), 1, auth, auth_hash, 30)
        proc = ED._spawn_run_child(
            str(run_dir), 1, auth, authority_hash=auth_hash)
        _assert_spawn_detached(proc)
        try:
            done = Path(run_dir) / "attempt-1.done"
            for _ in range(80):
                if done.is_file():
                    break
                time.sleep(0.25)
            assert done.is_file(), "run-child did not finish"
            data = json.loads(done.read_text(encoding="utf-8"))
            assert data.get("refusal") is None, data
            marker_auth = Path(linked_auth) / ".fake-codex-invokes"
            marker_state = Path(linked_state) / ".fake-codex-invokes"
            assert marker_auth.is_file(), (
                "engine must run in authority cwd; marker missing at %s" % linked_auth)
            assert not marker_state.exists(), (
                "engine must not run in state cwd; marker at %s" % linked_state)
        finally:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
    finally:
        ED._release_worktree_lease_for_cwd(
            os.path.realpath(linked_auth), lease_token, lease_holder)


def test_different_order_id_refuses_on_every_verb_including_poll(tmp_path):
    """Survivor 1: run dir bound to order-a refuses write/review/poll with order-b;
    poll must not return the previous order's cached result."""
    main, linked = _linked_pair(tmp_path)
    prompt = _prompt(tmp_path)
    run_dir = _seed_write_run(tmp_path, linked, prompt, order_id="order-a")
    cached = json.loads((Path(run_dir) / "result.json").read_text(encoding="utf-8"))
    assert cached.get("ok") is True

    fake_w = FakeWriteRunner([])
    write_res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="order-b", run_engine=fake_w,
        run_dir=run_dir, max_wait=10,
    )
    assert write_res["reason"] == "run-dir-reused"
    assert write_res["attempts"] == 0
    assert write_res.get("ok") is False
    assert fake_w.calls == []

    repo_root = _review_repo(tmp_path)
    build_view = _fake_review_build_view(tmp_path)
    review_res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=prompt, repo_root=repo_root, run_engine=_ReviewFakeRunner([]),
        build_view=build_view, run_dir=run_dir, max_wait=10, order_id="order-b",
    )
    # Write-kind authority vs review verb → kind mismatch (still a refuse, not cache).
    assert review_res["reason"] in ("run-dir-reused", "run-kind-mismatch"), review_res
    assert review_res.get("ok") is not True

    poll_res = ED.dispatch_poll(run_dir, max_wait=0, order_id="order-b")
    assert poll_res["reason"] == "run-dir-reused", poll_res
    assert poll_res.get("ok") is False
    # Must not echo the prior order's cached success.
    assert poll_res.get("runNonce") != cached.get("runNonce") or poll_res.get("ok") is False
    assert "engagement" not in poll_res or poll_res.get("ok") is False

    # Matching order_id still sees the cache.
    poll_ok = ED.dispatch_poll(run_dir, max_wait=0, order_id="order-a")
    assert poll_ok.get("ok") is True
    assert poll_ok.get("runNonce") == cached.get("runNonce")


def test_review_reentry_none_order_id_refuses_when_authority_bound(tmp_path):
    """Survivor 1: order_id=None no longer skips mismatch against a bound authority."""
    main, linked = _linked_pair(tmp_path)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "review-bound"
    run_dir.mkdir(mode=0o700)
    repo_root = _review_repo(tmp_path)
    build_view = _fake_review_build_view(tmp_path)
    first = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=prompt, repo_root=repo_root,
        run_engine=_ReviewFakeRunner([(_VALID_REVIEW_STDOUT, False, 0, "")]),
        build_view=build_view, run_dir=str(run_dir), max_wait=60,
        order_id="review-order-a",
    )
    assert first.get("ok") is True, first
    # Re-enter with omitted order_id — fail-closed against recorded binding.
    second = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=prompt, repo_root=repo_root,
        run_engine=_ReviewFakeRunner([]),
        build_view=build_view, run_dir=str(run_dir), max_wait=10,
        order_id=None,
    )
    assert second["reason"] == "run-dir-reused", second
    assert second.get("ok") is False


def test_spawn_detached_own_session_attempt_1_and_2(tmp_path, monkeypatch):
    """Survivor 2 / edge 7: attempt 1 and 2 children are each in their own session/pgid."""
    main, linked = _linked_pair(tmp_path)
    _install_fake_codex_on_path(monkeypatch, tmp_path, slow_first_seconds=60)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "detach-sess"
    run_dir.mkdir(mode=0o700)
    spawned = []
    real_spawn = ED._spawn_run_child

    def _track(rd, att, auth, authority_hash=None):
        proc = real_spawn(rd, att, auth, authority_hash=authority_hash)
        _assert_spawn_detached(proc)
        spawned.append((att, proc.pid, os.getsid(proc.pid), os.getpgid(proc.pid)))
        return proc

    monkeypatch.setattr(ED, "_spawn_run_child", _track)
    first = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="detach-o",
        run_engine=ED._run_engine, max_wait=1, timeout=5, run_dir=str(run_dir),
    )
    assert first.get("running") is True
    paths = ED._attempt_paths(str(run_dir), 1)
    for _ in range(80):
        if os.path.isfile(paths["done"]):
            break
        time.sleep(0.25)
    poll = ED.dispatch_poll(str(run_dir), max_wait=5, order_id="detach-o")
    assert ED.RETRY_PENDING_DETAIL in (poll.get("detail") or "")
    state_after = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    _wait_process_dead(state_after.get("completedAttemptSupervisorPid"))
    second = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="detach-o",
        run_engine=ED._run_engine, max_wait=120, timeout=5, run_dir=str(run_dir),
    )
    assert second.get("ok") is True, second
    assert [a for a, *_ in spawned] == [1, 2]
    for att, pid, sid, pgid in spawned:
        assert sid != os.getsid(os.getpid())
        assert pgid != os.getpgid(os.getpid())
        assert pgid == pid


# --- WO-702-B X1: supervisor-owned launch ledger ---


def _lease_held_for(cwd):
    import file_lock
    return bool(file_lock.read_holder(ED._worktree_lease_path(os.path.realpath(cwd))))


def _delete_ledger_record(run_dir):
    path = ED._ledger_run_record_path(os.path.realpath(str(run_dir)))
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    return path


def test_x1_state_hash_bypass_refused_at_reentry(tmp_path, monkeypatch):
    """End-to-end: forging launch-authority.json + state.authorityHash must not pass fold."""
    main, linked = _linked_pair(tmp_path)
    _install_fake_codex_on_path(monkeypatch, tmp_path, slow_first_seconds=60)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "x1-bypass"
    run_dir.mkdir(mode=0o700)
    first = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="x1-bypass",
        run_engine=ED._run_engine, max_wait=1, timeout=30, run_dir=str(run_dir),
    )
    assert first.get("running") is True, first
    assert _lease_held_for(linked), "lease must be held before the forge"
    authority = ED._load_authority(str(run_dir))
    assert authority is not None
    # Forge without touching order_id (that gate is independent of the hash bypass).
    new_hash, _swapped = _swap_sealed_authority(
        run_dir, authority, effort="low", fed_prompt="forged-prompt")
    state_path = run_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["authorityHash"] = new_hash
    state_path.write_text(json.dumps(state), encoding="utf-8")
    marker = Path(linked) / ".fake-codex-invokes"
    invokes_before = int(marker.read_text()) if marker.exists() else 0
    second = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="x1-bypass",
        run_engine=ED._run_engine, max_wait=1, timeout=30, run_dir=str(run_dir),
    )
    assert second.get("terminal") is True, second
    assert second.get("detail") == ED.AUTHORITY_HASH_MISMATCH, second
    invokes_after = int(marker.read_text()) if marker.exists() else 0
    assert invokes_after == invokes_before, "forged re-entry must not spawn an engine"
    assert _lease_held_for(linked), "unverified authority must retain the lease"


def test_x1_ledger_missing_refuses_reentry_poll_abandon(tmp_path, monkeypatch):
    """Ledger record deleted → continue / poll / abandon all refuse; lease retained."""
    main, linked = _linked_pair(tmp_path)
    _install_fake_codex_on_path(monkeypatch, tmp_path, slow_first_seconds=60)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "x1-led-miss"
    run_dir.mkdir(mode=0o700)
    first = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="x1-led-miss",
        run_engine=ED._run_engine, max_wait=1, timeout=30, run_dir=str(run_dir),
    )
    assert first.get("running") is True, first
    assert _lease_held_for(linked)
    _delete_ledger_record(run_dir)
    reenter = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="x1-led-miss",
        run_engine=ED._run_engine, max_wait=1, timeout=30, run_dir=str(run_dir),
    )
    assert reenter.get("terminal") is True, reenter
    assert reenter.get("detail") == ED.AUTHORITY_LEDGER_MISSING, reenter
    assert _lease_held_for(linked)
    poll = ED.dispatch_poll(str(run_dir), max_wait=1, order_id="x1-led-miss")
    assert poll.get("terminal") is True, poll
    assert poll.get("detail") == ED.AUTHORITY_LEDGER_MISSING, poll
    assert _lease_held_for(linked)
    abandon = ED.dispatch_abandon(str(run_dir))
    assert abandon.get("terminal") is True, abandon
    assert abandon.get("reason") == ED.ABANDON_INCOMPLETE, abandon
    assert abandon.get("detail") == ED.AUTHORITY_LEDGER_MISSING, abandon
    assert _lease_held_for(linked)


def test_x1_ledger_wrong_hash_refuses(tmp_path, monkeypatch):
    """Ledger authorityHash disagrees with sealed file → AUTHORITY_HASH_MISMATCH."""
    main, linked = _linked_pair(tmp_path)
    _install_fake_codex_on_path(monkeypatch, tmp_path, slow_first_seconds=60)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "x1-led-hash"
    run_dir.mkdir(mode=0o700)
    first = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="x1-led-hash",
        run_engine=ED._run_engine, max_wait=1, timeout=30, run_dir=str(run_dir),
    )
    assert first.get("running") is True, first
    authority = ED._load_authority(str(run_dir))
    real = os.path.realpath(str(run_dir))
    path = ED._ledger_run_record_path(real)
    record = json.loads(open(path, "rb").read().decode("utf-8"))
    record["authorityHash"] = "0" * 64
    os.chmod(path, 0o600)
    os.unlink(path)
    ED._ledger_seal(path, record)
    # Sealed file + state echo still match each other; only the ledger disagrees.
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="x1-led-hash",
        run_engine=ED._run_engine, max_wait=1, timeout=30, run_dir=str(run_dir),
    )
    assert res.get("detail") == ED.AUTHORITY_HASH_MISMATCH, res
    assert _lease_held_for(linked)


def test_x1_ledger_binding_nonce_rundir_schema(tmp_path, monkeypatch):
    """Disagreement on runNonce / runDir / schemaVersion is not accepted."""
    main, linked = _linked_pair(tmp_path)
    _install_fake_codex_on_path(monkeypatch, tmp_path, slow_first_seconds=60)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "x1-bind"
    run_dir.mkdir(mode=0o700)
    first = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="x1-bind",
        run_engine=ED._run_engine, max_wait=1, timeout=30, run_dir=str(run_dir),
    )
    assert first.get("running") is True, first
    authority = ED._load_authority(str(run_dir))
    real = os.path.realpath(str(run_dir))
    path = ED._ledger_run_record_path(real)
    raw = open(path, "rb").read()
    record = json.loads(raw.decode("utf-8"))

    def _reseal(mutated):
        os.chmod(path, 0o600)
        os.unlink(path)
        ED._ledger_seal(path, mutated)

    # runNonce
    bad = dict(record)
    bad["runNonce"] = "not-the-nonce"
    _reseal(bad)
    assert ED._ledger_expected_hash(
        real, authority.run_nonce, authority.order_id) is None

    # runDir
    bad = dict(record)
    bad["runDir"] = real + "-other"
    _reseal(bad)
    assert ED._ledger_expected_hash(
        real, authority.run_nonce, authority.order_id) is None

    # schemaVersion
    bad = dict(record)
    bad["schemaVersion"] = int(ED.LEDGER_SCHEMA_VERSION) + 99
    _reseal(bad)
    assert ED._ledger_expected_hash(
        real, authority.run_nonce, authority.order_id) is None


def test_x1_load_verified_authority_single_snapshot(tmp_path, monkeypatch):
    """_load_verified_authority hashes and parses the same bytes; one read only."""
    main, linked = _linked_pair(tmp_path)
    run_dir, authority, auth_hash, _argv = _setup_write_fold_ready(
        tmp_path, linked, order_id="x1-snap")
    path = _authority_path(run_dir)
    original = open(path, "rb").read()
    reads = []
    real_open = open

    def _counting_open(file, *args, **kwargs):
        if str(file) == str(path):
            reads.append(1)
            if len(reads) == 1:
                class _First:
                    def read(self, *a, **k):
                        return original

                    def __enter__(self):
                        return self

                    def __exit__(self, *a):
                        return False

                return _First()
            class _Second:
                def read(self, *a, **k):
                    return b'{"role_kind":"review","run_kind":"review",' \
                           b'"engine":"codex","effort":"high","engine_binary":"x",' \
                           b'"cwd":"/tmp","run_nonce":"other","run_dir":"/tmp",' \
                           b'"timeout":1,"retry_timeout":1,"argv":[],' \
                           b'"spawned_argv":[],"order_id":"x"}'

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

            return _Second()
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr("builtins.open", _counting_open)
    verified = ED._load_verified_authority(str(run_dir), auth_hash)
    assert verified is not None
    assert verified.run_nonce == authority.run_nonce
    assert verified.order_id == authority.order_id
    assert verified.run_kind == ED.RUN_KIND_WRITE
    assert len(reads) == 1, "must not re-open the authority path"


def test_x1_ledger_init_failure_releases_lease_no_spawn(tmp_path, monkeypatch):
    """OSError from _ledger_init → AUTHORITY_LEDGER_INIT_FAILED; FileExistsError → reused."""
    main, linked = _linked_pair(tmp_path)
    prompt = _prompt(tmp_path)
    spawned = []
    monkeypatch.setattr(
        ED, "_spawn_run_child",
        lambda *a, **k: spawned.append(1) or (_ for _ in ()).throw(AssertionError("spawn")))

    def _boom(*a, **k):
        raise OSError("ledger boom")

    monkeypatch.setattr(ED, "_ledger_init", _boom)
    run_dir = tmp_path / "x1-init-fail"
    run_dir.mkdir(mode=0o700)
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="x1-init-fail",
        run_engine=FakeWriteRunner([]), max_wait=5, run_dir=str(run_dir),
    )
    assert res.get("detail") == ED.AUTHORITY_LEDGER_INIT_FAILED, res
    assert spawned == []
    assert not _lease_held_for(linked), "init failure must release the lease"

    def _exists(*a, **k):
        raise FileExistsError("ledger exists")

    monkeypatch.setattr(ED, "_ledger_init", _exists)
    run_dir2 = tmp_path / "x1-init-exists"
    run_dir2.mkdir(mode=0o700)
    res2 = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="x1-init-exists",
        run_engine=FakeWriteRunner([]), max_wait=5, run_dir=str(run_dir2),
    )
    assert res2.get("reason") == "run-dir-reused", res2
    assert spawned == []
    assert not _lease_held_for(linked)


def test_x1_reused_run_dir_path_via_existing_ledger(tmp_path, monkeypatch):
    """Emptied run dir whose ledger record still exists → run-dir-reused; no lease leak."""
    main, linked = _linked_pair(tmp_path)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "x1-reuse"
    run_dir.mkdir(mode=0o700)
    first = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="x1-reuse",
        run_engine=FakeWriteRunner([(_WRITE_OK_STDOUT, False, 0, "")]),
        max_wait=60, run_dir=str(run_dir),
    )
    assert first.get("ok") is True, first
    real = os.path.realpath(str(run_dir))
    assert os.path.isfile(ED._ledger_run_record_path(real))
    # Empty the run dir but leave the ledger record.
    for child in run_dir.iterdir():
        if child.is_file():
            child.unlink()
        else:
            shutil.rmtree(child)
    spawned = []
    monkeypatch.setattr(
        ED, "_spawn_run_child",
        lambda *a, **k: spawned.append(1))
    second = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="x1-reuse-2",
        run_engine=FakeWriteRunner([(_WRITE_OK_STDOUT, False, 0, "")]),
        max_wait=5, run_dir=str(run_dir),
    )
    assert second.get("reason") == "run-dir-reused", second
    assert spawned == []
    assert not _lease_held_for(linked)


def test_x1_ledger_root_hygiene(tmp_path, monkeypatch):
    """Symlink / non-directory ledger roots are refused.

    Foreign-uid ownership cannot be constructed without root; that edge is
    covered by the same st_uid != getuid() check as _validate_run_dir and is
    not exercised here (see implementer return).
    """
    # Symlink
    target = tmp_path / "led-real"
    target.mkdir(mode=0o700)
    link = tmp_path / "led-link"
    link.symlink_to(target)
    monkeypatch.setenv("SUPERHEROES_DISPATCH_LEDGER_ROOT", str(link))
    assert ED._ledger_root() is None

    # Non-directory
    file_root = tmp_path / "led-file"
    file_root.write_text("nope", encoding="utf-8")
    monkeypatch.setenv("SUPERHEROES_DISPATCH_LEDGER_ROOT", str(file_root))
    assert ED._ledger_root() is None

    # Missing root is created 0700 and accepted when owned by us.
    missing = tmp_path / "led-missing"
    monkeypatch.setenv("SUPERHEROES_DISPATCH_LEDGER_ROOT", str(missing))
    root = ED._ledger_root()
    assert root is not None
    assert os.path.isdir(root)
    assert stat.S_IMODE(os.stat(root).st_mode) == 0o700


def test_x1_spawned_engine_env_scrubs_ledger_root(monkeypatch):
    """Engine subprocess env must not carry SUPERHEROES_DISPATCH_LEDGER_ROOT."""
    monkeypatch.setenv("SUPERHEROES_DISPATCH_LEDGER_ROOT", "/tmp/secret-led-root")
    scrubbed = ED._scrub_git_env()
    assert "SUPERHEROES_DISPATCH_LEDGER_ROOT" not in scrubbed
    # Also pin via an explicit env dict (the path _run_engine_files uses).
    scrubbed2 = ED._scrub_git_env({
        "SUPERHEROES_DISPATCH_LEDGER_ROOT": "/tmp/secret-led-root",
        "PATH": "/usr/bin",
    })
    assert "SUPERHEROES_DISPATCH_LEDGER_ROOT" not in scrubbed2
    assert scrubbed2.get("PATH") == "/usr/bin"


# --- WO-702-B order X2: authority facts off the engine-writable surface ---


def _x2_write_state(tmp_path, linked, *, order_id, run_nonce, lease_token, lease_holder,
                    run_dir, in_flight=1, completed=0, supervisor_pid=None,
                    supervisor_start="", snapshot=None):
    built = EA.build_argv_result(
        "codex", "build", "high",
        {"engine_model": "gpt-5.6-terra", "cwd": linked},
    )
    argv = built["argv"]
    prompt_bytes = b"build\n"
    (run_dir / "prompt.txt").write_bytes(prompt_bytes)
    state = {
        "engine": "codex",
        "roleKind": "build",
        "dispatchMode": ED.WRITE_DISPATCH_MODE,
        "effort": "high",
        "engineModel": "gpt-5.6-terra",
        "cwd": os.path.realpath(linked),
        "argv": argv,
        "spawnedArgv": argv,
        "engineBinary": shutil.which(argv[0]) or "/bin/true",
        "timeout": 5,
        "retryTimeout": 5,
        "orderId": order_id,
        "runNonce": run_nonce,
        "worktreeLeaseToken": lease_token,
        "worktreeLeaseHolder": lease_holder,
        "worktreeSnapshot": list(snapshot or ED._worktree_snapshot(linked)),
        "completedAttempts": completed,
        "inFlightAttempt": in_flight,
        "attemptStartedAt": time.time() - 5,
        "supervisorPid": supervisor_pid,
        "supervisorStart": supervisor_start,
        "promptPath": str(run_dir / "prompt.txt"),
        "fedPrompt": "build\n",
        "promptSha256": hashlib.sha256(prompt_bytes).hexdigest(),
    }
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return state


# --- WO-702-B order X2b: lease retention keys on live-child evidence ---


def test_x2b_completion_payload_absent_releases_lease_without_live_evidence(tmp_path):
    """Ledger completion without .done and no live child → terminal, lease released."""
    main, linked = _linked_pair(tmp_path)
    run_dir = tmp_path / "x2b-cpa-release"
    run_dir.mkdir(mode=0o700)
    lease_token, lease_holder = ED._acquire_worktree_lease_for_cwd(
        os.path.realpath(linked))
    state = _x2_write_state(
        tmp_path, linked, order_id="x2b-cpa-r", run_nonce="x2b-cpa-rn",
        lease_token=lease_token, lease_holder=lease_holder, run_dir=run_dir,
        in_flight=None, completed=0,
        supervisor_pid=999999993, supervisor_start="dead-cpa")
    _persist_test_authority(run_dir, state)
    auth_hash = state["authorityHash"]
    run_real = os.path.realpath(str(run_dir))
    ED._ledger_seal_attempt_intent(
        run_real, 1, auth_hash, "x2b-cpa-rn", 5, list(state["worktreeSnapshot"]))
    ED._ledger_seal(ED._ledger_attempt_path(run_real, 1, "claim"), {
        "schemaVersion": ED.LEDGER_SCHEMA_VERSION,
        "attempt": 1,
        "authorityHash": auth_hash,
        "runNonce": "x2b-cpa-rn",
        "childPid": 999999993,
        "childStart": "dead-cpa",
    })
    ED._ledger_seal_attempt_complete(run_real, 1, auth_hash, "x2b-cpa-rn")
    assert not (run_dir / "attempt-1.done").is_file()
    res = ED.dispatch_poll(str(run_dir), max_wait=0, order_id="x2b-cpa-r")
    assert res.get("detail") == "completion-payload-absent", res
    assert res.get("terminal") is True
    assert not _lease_held_for(linked)


def test_x2b_completion_payload_absent_retains_lease_on_live_claim(tmp_path):
    """Ledger completion without .done but live claim → terminal, lease retained."""
    main, linked = _linked_pair(tmp_path)
    run_dir = tmp_path / "x2b-cpa-retain"
    run_dir.mkdir(mode=0o700)
    lease_token, lease_holder = ED._acquire_worktree_lease_for_cwd(
        os.path.realpath(linked))
    live_pid = os.getpid()
    state = _x2_write_state(
        tmp_path, linked, order_id="x2b-cpa-k", run_nonce="x2b-cpa-kn",
        lease_token=lease_token, lease_holder=lease_holder, run_dir=run_dir,
        in_flight=None, completed=0,
        supervisor_pid=live_pid,
        supervisor_start=ED._supervisor_lstart(live_pid) or "live")
    _persist_test_authority(run_dir, state)
    auth_hash = state["authorityHash"]
    run_real = os.path.realpath(str(run_dir))
    ED._ledger_seal_attempt_intent(
        run_real, 1, auth_hash, "x2b-cpa-kn", 5, list(state["worktreeSnapshot"]))
    ED._ledger_seal(ED._ledger_attempt_path(run_real, 1, "claim"), {
        "schemaVersion": ED.LEDGER_SCHEMA_VERSION,
        "attempt": 1,
        "authorityHash": auth_hash,
        "runNonce": "x2b-cpa-kn",
        "childPid": live_pid,
        "childStart": state["supervisorStart"],
    })
    ED._ledger_seal_attempt_complete(run_real, 1, auth_hash, "x2b-cpa-kn")
    assert not (run_dir / "attempt-1.done").is_file()
    res = ED.dispatch_poll(str(run_dir), max_wait=0, order_id="x2b-cpa-k")
    assert res.get("detail") == "completion-payload-absent", res
    assert res.get("terminal") is True
    assert "live claimed run-child" in (res.get("disclosure") or ""), res
    assert _lease_held_for(linked)
    ED._release_worktree_lease_for_cwd(
        os.path.realpath(linked), lease_token, lease_holder)


def test_x2_forged_completion_does_not_release_or_retry(tmp_path):
    """Forged run-dir .done without ledger completion ⇒ still running, lease held."""
    import hashlib
    main, linked = _linked_pair(tmp_path)
    run_dir = tmp_path / "x2-forged-done"
    run_dir.mkdir(mode=0o700)
    lease_token, lease_holder = ED._acquire_worktree_lease_for_cwd(
        os.path.realpath(linked))
    state = _x2_write_state(
        tmp_path, linked, order_id="x2-fg-o", run_nonce="x2-fg-n",
        lease_token=lease_token, lease_holder=lease_holder, run_dir=run_dir,
        supervisor_pid=999999991, supervisor_start="not-real")
    # Seal intent + launch but NOT completion — attempt genuinely pending.
    _persist_test_authority(run_dir, state)
    _seal_test_launch(run_dir, 1, state)
    auth_hash = state["authorityHash"]
    (run_dir / "attempt-1.done").write_text(json.dumps({
        "exit": 0, "timedOut": False, "runNonce": "x2-fg-n",
        "authorityHash": auth_hash, "endedAt": time.time(),
        "refusal": None,
    }), encoding="utf-8")
    (run_dir / "attempt-1.stdout").write_text(_WRITE_OK_STDOUT, encoding="utf-8")
    (run_dir / "attempt-1.stderr").write_text("", encoding="utf-8")
    assert ED._ledger_attempt_complete(
        os.path.realpath(str(run_dir)), 1, auth_hash, "x2-fg-n") is None
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=_prompt(tmp_path), cwd=linked, order_id="x2-fg-o",
        run_engine=FakeWriteRunner([]), max_wait=0, run_dir=str(run_dir),
    )
    assert res.get("terminal") is False, res
    assert res.get("running") is True or not res.get("ok"), res
    assert not (run_dir / "result.json").is_file()
    assert _lease_held_for(linked)
    ED._release_worktree_lease_for_cwd(
        os.path.realpath(linked), lease_token, lease_holder)


def test_x2_genuine_completion_still_folds(tmp_path):
    """Same scenario with ledger completion present folds normally."""
    main, linked = _linked_pair(tmp_path)
    run_dir = tmp_path / "x2-genuine-done"
    run_dir.mkdir(mode=0o700)
    lease_token, lease_holder = ED._acquire_worktree_lease_for_cwd(
        os.path.realpath(linked))
    state = _x2_write_state(
        tmp_path, linked, order_id="x2-gn-o", run_nonce="x2-gn-n",
        lease_token=lease_token, lease_holder=lease_holder, run_dir=run_dir,
        supervisor_pid=999999992, supervisor_start="injected-dead-supervisor")
    (run_dir / "attempt-1.done").write_text(json.dumps({
        "exit": 0, "timedOut": False, "runNonce": "x2-gn-n",
        "endedAt": time.time(),
    }), encoding="utf-8")
    (run_dir / "attempt-1.stdout").write_text(_WRITE_OK_STDOUT, encoding="utf-8")
    (run_dir / "attempt-1.stderr").write_text("", encoding="utf-8")
    _bind_inflight(run_dir, state)
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=_prompt(tmp_path), cwd=linked, order_id="x2-gn-o",
        run_engine=FakeWriteRunner([]), max_wait=60, run_dir=str(run_dir),
    )
    assert res.get("ok") is True, res
    assert res.get("terminal") is True
    assert res.get("attempts") == 1


def test_x2_retry_liveness_from_ledger_claim(tmp_path):
    """state.json dead-looking pid cannot authorise retry when ledger claim is live."""
    main, linked = _linked_pair(tmp_path)
    run_dir = tmp_path / "x2-live-claim"
    run_dir.mkdir(mode=0o700)
    lease_token, lease_holder = ED._acquire_worktree_lease_for_cwd(
        os.path.realpath(linked))
    holder = subprocess.Popen(
        ["python3", "-c", "import time; time.sleep(120)"],
        start_new_session=True,
    )
    try:
        state = _x2_write_state(
            tmp_path, linked, order_id="x2-lv-o", run_nonce="x2-lv-n",
            lease_token=lease_token, lease_holder=lease_holder, run_dir=run_dir,
            in_flight=None, completed=1,
            # Dead-looking state fields — must NOT authorise retry.
            supervisor_pid=999999993,
            supervisor_start="injected-dead-supervisor")
        state["completedAttemptSupervisorPid"] = 999999993
        state["pendingTerminal"] = "forfeited"
        (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
        (run_dir / "attempt-1.done").write_text(json.dumps({
            "exit": None, "timedOut": True, "runNonce": "x2-lv-n",
            "endedAt": time.time(),
        }), encoding="utf-8")
        (run_dir / "attempt-1.stdout").write_text("", encoding="utf-8")
        (run_dir / "attempt-1.stderr").write_text("", encoding="utf-8")
        # Bind with live claim pid (disagreeing with state).
        state["supervisorPid"] = holder.pid
        state["supervisorStart"] = ED._supervisor_lstart(holder.pid) or "live"
        _bind_inflight(run_dir, state, attempt=1)
        # Put dead-looking values back into state receipt.
        st = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        st["completedAttemptSupervisorPid"] = 999999993
        st["supervisorPid"] = 999999993
        st["supervisorStart"] = "injected-dead-supervisor"
        st["inFlightAttempt"] = None
        st["completedAttempts"] = 1
        st["pendingTerminal"] = "forfeited"
        (run_dir / "state.json").write_text(json.dumps(st), encoding="utf-8")
        assert ED._process_alive(holder.pid) is True
        res = ED.dispatch_write(
            "codex", engine_model="gpt-5.6-terra", effort="high",
            prompt_path=_prompt(tmp_path), cwd=linked, order_id="x2-lv-o",
            run_engine=FakeWriteRunner([]), max_wait=60, run_dir=str(run_dir),
        )
        assert res["terminal"] is True, res
        assert res["detail"] == "retry-unsafe-attempt-still-live"
        assert res["forfeited"] is True
    finally:
        try:
            os.killpg(holder.pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            holder.wait(timeout=2)
        except Exception:
            pass
        ED._release_worktree_lease_for_cwd(
            os.path.realpath(linked), lease_token, lease_holder)


def test_x2_retry_snapshot_from_ledger_intent(tmp_path):
    """Rewriting state worktreeSnapshot cannot authorise a dirty-worktree retry."""
    main, linked = _linked_pair(tmp_path)
    run_dir = tmp_path / "x2-snap"
    run_dir.mkdir(mode=0o700)
    lease_token, lease_holder = ED._acquire_worktree_lease_for_cwd(
        os.path.realpath(linked))
    snap_before = list(ED._worktree_snapshot(linked))
    # completedAttempts=0 so resume-fold processes the sealed completion and
    # hits the in-flight dirty-worktree gate (ledger intent snapshot wins).
    state = _x2_write_state(
        tmp_path, linked, order_id="x2-sn-o", run_nonce="x2-sn-n",
        lease_token=lease_token, lease_holder=lease_holder, run_dir=run_dir,
        in_flight=1, completed=0,
        supervisor_pid=999999994, supervisor_start="injected-dead-supervisor",
        snapshot=snap_before)
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    (run_dir / "attempt-1.done").write_text(json.dumps({
        "exit": None, "timedOut": True, "runNonce": "x2-sn-n",
        "endedAt": time.time(),
    }), encoding="utf-8")
    (run_dir / "attempt-1.stdout").write_text("", encoding="utf-8")
    (run_dir / "attempt-1.stderr").write_text("", encoding="utf-8")
    _bind_inflight(run_dir, state, attempt=1)
    dirty = os.path.join(linked, "x2-dirty.txt")
    with open(dirty, "w", encoding="utf-8") as fh:
        fh.write("mutated\n")
    snap_after = list(ED._worktree_snapshot(linked))
    assert snap_after != snap_before
    st = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    st["worktreeSnapshot"] = snap_after  # forged to match current — must not win
    st["inFlightAttempt"] = 1
    st["completedAttempts"] = 0
    st["supervisorPid"] = 999999994
    st["supervisorStart"] = "injected-dead-supervisor"
    (run_dir / "state.json").write_text(json.dumps(st), encoding="utf-8")
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=_prompt(tmp_path), cwd=linked, order_id="x2-sn-o",
        run_engine=FakeWriteRunner([]), max_wait=60, run_dir=str(run_dir),
    )
    assert res["terminal"] is True, res
    assert res["detail"] == "retry-unsafe-dirty-worktree"
    ED._release_worktree_lease_for_cwd(
        os.path.realpath(linked), lease_token, lease_holder)


def test_x2_forged_inflight_cannot_release_lease(tmp_path):
    """Forged state inFlightAttempt must not drive compensation / lease release."""
    main, linked = _linked_pair(tmp_path)
    run_dir = tmp_path / "x2-forged-if"
    run_dir.mkdir(mode=0o700)
    lease_token, lease_holder = ED._acquire_worktree_lease_for_cwd(
        os.path.realpath(linked))
    state = _x2_write_state(
        tmp_path, linked, order_id="x2-if-o", run_nonce="x2-if-n",
        lease_token=lease_token, lease_holder=lease_holder, run_dir=run_dir,
        in_flight=99,  # invalid forged value
        supervisor_pid=999999995, supervisor_start="not-real")
    _persist_test_authority(run_dir, state)
    _seal_test_launch(run_dir, 1, state)  # real pending attempt 1
    # Confirm pending comes from ledger, not forged state.
    auth_hash = state["authorityHash"]
    pending, _ = ED._find_pending_launch(
        os.path.realpath(str(run_dir)), auth_hash, "x2-if-n")
    assert pending == 1
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=_prompt(tmp_path), cwd=linked, order_id="x2-if-o",
        run_engine=FakeWriteRunner([]), max_wait=0, run_dir=str(run_dir),
    )
    assert res.get("terminal") is False, res
    assert _lease_held_for(linked)
    assert not (run_dir / "result.json").is_file()
    ED._release_worktree_lease_for_cwd(
        os.path.realpath(linked), lease_token, lease_holder)


def test_x2_timeout_cannot_be_widened(tmp_path, monkeypatch):
    """Forged launch.json timeout ⇒ launch-timeout-mismatch; no engine."""
    main, linked = _linked_pair(tmp_path)
    run_dir = tmp_path / "x2-timeout"
    run_dir.mkdir(mode=0o700)
    lease_token, lease_holder = ED._acquire_worktree_lease_for_cwd(
        os.path.realpath(linked))
    state = _x2_write_state(
        tmp_path, linked, order_id="x2-to-o", run_nonce="x2-to-n",
        lease_token=lease_token, lease_holder=lease_holder, run_dir=run_dir)
    authority = _persist_test_authority(run_dir, state)
    auth_hash = state["authorityHash"]
    _seal_test_launch(run_dir, 1, state)
    # Recreate launch.json with widened timeout.
    forged = {
        "attempt": 1,
        "authorityHash": auth_hash,
        "runNonce": "x2-to-n",
        "orderId": "x2-to-o",
        "runKind": ED.RUN_KIND_WRITE,
        "timeout": 99999,
    }
    launch_path = os.path.join(str(run_dir), "attempt-1.launch.json")
    os.chmod(launch_path, 0o600)
    open(launch_path, "w", encoding="utf-8").write(json.dumps(forged))
    os.chmod(launch_path, 0o400)
    engine_calls = []

    def _no_engine(*a, **k):
        engine_calls.append(1)
        raise AssertionError("engine must not run")

    monkeypatch.setattr(ED, "_run_engine_files", _no_engine)
    rc = _invoke_run_child(run_dir, 1, state)
    assert rc == 4
    assert engine_calls == []
    done = json.loads((run_dir / "attempt-1.done").read_text(encoding="utf-8"))
    assert done.get("refusal") == "launch-timeout-mismatch"
    ED._release_worktree_lease_for_cwd(
        os.path.realpath(linked), lease_token, lease_holder)


def test_x2_prompt_swap_refused_and_happy_path_feeds_bytes(tmp_path, monkeypatch):
    """Swapped prompt.txt ⇒ prompt-digest-mismatch; matching path feeds prompt_bytes."""
    main, linked = _linked_pair(tmp_path)
    sealed_bytes = b"sealed-prompt-bytes\n"
    digest = hashlib.sha256(sealed_bytes).hexdigest()

    run_dir = tmp_path / "x2-prompt"
    run_dir.mkdir(mode=0o700)
    lease_token, lease_holder = ED._acquire_worktree_lease_for_cwd(
        os.path.realpath(linked))
    state = _x2_write_state(
        tmp_path, linked, order_id="x2-pr-o", run_nonce="x2-pr-n",
        lease_token=lease_token, lease_holder=lease_holder, run_dir=run_dir)
    state["promptSha256"] = digest
    state["fedPrompt"] = sealed_bytes.decode("utf-8")
    (run_dir / "prompt.txt").write_bytes(sealed_bytes)
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    _persist_test_authority(run_dir, state)
    _seal_test_launch(run_dir, 1, state)

    (run_dir / "prompt.txt").write_bytes(b"ATTACKER-PROMPT\n")
    engine_calls = []

    def _no_engine(*a, **k):
        engine_calls.append(1)
        raise AssertionError("engine must not run on digest mismatch")

    monkeypatch.setattr(ED, "_run_engine_files", _no_engine)
    rc = _invoke_run_child(run_dir, 1, state)
    assert rc == 4
    assert engine_calls == []
    done = json.loads((run_dir / "attempt-1.done").read_text(encoding="utf-8"))
    assert done.get("refusal") == "prompt-digest-mismatch"
    ED._release_worktree_lease_for_cwd(
        os.path.realpath(linked), lease_token, lease_holder)

    run_dir2 = tmp_path / "x2-prompt-ok"
    run_dir2.mkdir(mode=0o700)
    lease_token2, lease_holder2 = ED._acquire_worktree_lease_for_cwd(
        os.path.realpath(linked))
    state2 = _x2_write_state(
        tmp_path, linked, order_id="x2-pr2-o", run_nonce="x2-pr2-n",
        lease_token=lease_token2, lease_holder=lease_holder2, run_dir=run_dir2)
    state2["promptSha256"] = digest
    state2["fedPrompt"] = sealed_bytes.decode("utf-8")
    (run_dir2 / "prompt.txt").write_bytes(sealed_bytes)
    (run_dir2 / "state.json").write_text(json.dumps(state2), encoding="utf-8")
    _persist_test_authority(run_dir2, state2)
    _seal_test_launch(run_dir2, 1, state2)
    seen = {}

    def _capture_engine(argv, prompt_path, stdout_path, stderr_path, timeout,
                        progress_path, attempt, cwd, env=None, engine_pgid_path=None,
                        authority=None, authority_hash=None, prompt_bytes=None):
        seen["prompt_bytes"] = prompt_bytes
        open(stdout_path, "wb").write(_WRITE_OK_STDOUT.encode("utf-8"))
        open(stderr_path, "wb").write(b"")
        return {"exit": 0, "timedOut": False, "signal": None,
                "endedAt": time.time(), "refusal": None}

    monkeypatch.setattr(ED, "_run_engine_files", _capture_engine)
    rc2 = _invoke_run_child(run_dir2, 1, state2)
    assert rc2 == 0, (rc2, seen)
    assert seen.get("prompt_bytes") == sealed_bytes
    ED._release_worktree_lease_for_cwd(
        os.path.realpath(linked), lease_token2, lease_holder2)


def test_x2_double_claim_second_exits_without_engine(tmp_path, monkeypatch):
    """Second run-child on same pending attempt exits 2, no sentinel, no engine."""
    main, linked = _linked_pair(tmp_path)
    run_dir = tmp_path / "x2-dbl"
    run_dir.mkdir(mode=0o700)
    lease_token, lease_holder = ED._acquire_worktree_lease_for_cwd(
        os.path.realpath(linked))
    state = _x2_write_state(
        tmp_path, linked, order_id="x2-db-o", run_nonce="x2-db-n",
        lease_token=lease_token, lease_holder=lease_holder, run_dir=run_dir)
    _persist_test_authority(run_dir, state)
    _seal_test_launch(run_dir, 1, state)
    engine_calls = []

    def _slow_engine(*a, **k):
        engine_calls.append(1)
        time.sleep(0.3)
        return {"exit": 0, "timedOut": False, "signal": None,
                "endedAt": time.time(), "refusal": None}

    monkeypatch.setattr(ED, "_run_engine_files", _slow_engine)
    real = os.path.realpath(str(run_dir))
    auth_hash = state["authorityHash"]
    # First claim succeeds; second run-child entry must refuse.
    assert ED._ledger_claim_attempt(real, 1, auth_hash, "x2-db-n") is True
    engine_calls.clear()
    rc2 = ED._run_child_entry(real)
    assert rc2 == 2
    assert engine_calls == []
    assert not (run_dir / "attempt-1.done").is_file()
    ED._release_worktree_lease_for_cwd(
        os.path.realpath(linked), lease_token, lease_holder)


def test_x2_legacy_authority_without_prompt_sha256(tmp_path, monkeypatch):
    """Legacy sealed authority missing prompt_sha256 parses and runs without refusal."""
    main, linked = _linked_pair(tmp_path)
    run_dir = tmp_path / "x2-legacy"
    run_dir.mkdir(mode=0o700)
    lease_token, lease_holder = ED._acquire_worktree_lease_for_cwd(
        os.path.realpath(linked))
    (run_dir / "prompt.txt").write_bytes(b"legacy-prompt\n")
    state = _x2_write_state(
        tmp_path, linked, order_id="x2-lg-o", run_nonce="x2-lg-n",
        lease_token=lease_token, lease_holder=lease_holder, run_dir=run_dir)
    state.pop("promptSha256", None)
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    authority = _authority_from_state(run_dir, state)
    # Force prompt_sha256=None on the sealed file.
    from dataclasses import fields as dc_fields
    kwargs = {f.name: getattr(authority, f.name) for f in dc_fields(authority)}
    kwargs["prompt_sha256"] = None
    authority = ED.LaunchAuthority(**kwargs)
    auth_hash = ED._persist_authority(authority)
    state["authorityHash"] = auth_hash
    ED._ledger_init(authority, auth_hash)
    _seal_test_launch(run_dir, 1, state)
    # Swap prompt — legacy must NOT refuse on digest.
    (run_dir / "prompt.txt").write_bytes(b"swapped-legacy\n")
    seen = {}

    def _capture(argv, prompt_path, stdout_path, stderr_path, timeout,
                 progress_path, attempt, cwd, env=None, engine_pgid_path=None,
                 authority=None, authority_hash=None, prompt_bytes=None):
        seen["prompt_bytes"] = prompt_bytes
        open(stdout_path, "wb").write(b"ok")
        open(stderr_path, "wb").write(b"")
        return {"exit": 0, "timedOut": False, "signal": None,
                "endedAt": time.time(), "refusal": None}

    monkeypatch.setattr(ED, "_run_engine_files", _capture)
    rc = _invoke_run_child(run_dir, 1, state)
    assert rc == 0
    # Legacy path: prompt_bytes is None (path-based open).
    assert seen.get("prompt_bytes") is None
    loaded = ED._load_authority(os.path.realpath(str(run_dir)))
    assert loaded is not None
    assert loaded.prompt_sha256 is None
    ED._release_worktree_lease_for_cwd(
        os.path.realpath(linked), lease_token, lease_holder)


# --- WO-702-X3: mechanism bite tests ---


def test_x3_run_child_parser_option_a_only_run_dir(monkeypatch):
    """Option A: run-child user actions are exactly --run-dir (+ -h/--help).

    Builds the CLI parser via engine_dispatch.main's argparse construction and
    introspects the run-child subparser. Retired authority-bearing flags must
    fail to parse.
    """
    import argparse

    hold = {}

    class _StopAfterParse(Exception):
        pass

    real_parse_args = argparse.ArgumentParser.parse_args

    def spy_parse_args(self, args=None, namespace=None):
        hold["root"] = self
        hold["ns"] = real_parse_args(self, args, namespace)
        raise _StopAfterParse()

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", spy_parse_args)
    with pytest.raises(_StopAfterParse):
        ED.main(["run-child", "--run-dir", "/tmp/x3-rc-parser"])
    root = hold["root"]
    rc = None
    for action in root._actions:
        if isinstance(action, argparse._SubParsersAction):
            rc = action.choices.get("run-child")
            break
    assert rc is not None, "run-child subparser missing from main()"
    option_strings = set()
    for action in rc._actions:
        option_strings.update(action.option_strings)
    assert option_strings == {"--run-dir", "-h", "--help"}, option_strings
    # Representative retired flags must fail to parse on the run-child surface.
    # Restore real parse_args so SystemExit comes from argparse error handling.
    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", real_parse_args)
    for retired in (
            ["--run-dir", "/tmp/x", "--attempt", "1"],
            ["--run-dir", "/tmp/x", "--launch-cwd", "/tmp/y"],
            ["--run-dir", "/tmp/x", "--authority-hash", "0" * 64],
    ):
        with pytest.raises(SystemExit) as exc:
            rc.parse_args(retired)
        assert exc.value.code == 2


def test_x3_bite_fold_verification_refuses_swapped_authority(tmp_path):
    """Bite 1: fold verification via _load_verified_authority / fold path.

    Swapped sealed authority must refuse with AUTHORITY_HASH_MISMATCH. Neutralizing
    _load_verified_authority to return authority unconditionally must break this.
    """
    main, linked = _linked_pair(tmp_path)
    run_dir, authority, auth_hash, argv = _setup_write_fold_ready(
        tmp_path, linked, order_id="x3-fold-bite")
    _swap_sealed_authority(
        run_dir, authority, effort="low", fed_prompt="forged-for-fold-bite")
    assert ED._authority_file_hash(str(run_dir)) != auth_hash
    result = ED._fold_terminal_write(
        str(run_dir), authority, argv, {"engine": "codex"}, "success",
        {"ok": True, "signal": "ok", "evidence": {}}, 1,
        authority_hash=auth_hash,
    )
    assert result.get("ok") is False, result
    assert result.get("detail") == ED.AUTHORITY_HASH_MISMATCH, result
    assert result.get("reason") == "unrunnable", result
    on_disk = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    assert on_disk.get("ok") is not True
    assert on_disk.get("detail") == ED.AUTHORITY_HASH_MISMATCH


def test_x3_bite_ledger_hash_poll_abandon_refuse_state_substitution(
        tmp_path, monkeypatch):
    """Bite 2: ledger-sourced reference on poll + abandon (not the X1 write path).

    Forging launch-authority.json + state.authorityHash while the ledger still
    holds the real hash must make dispatch_poll and dispatch_abandon refuse.
    Replacing _ledger_expected_hash's result with state['authorityHash'] must
    break this test.
    """
    main, linked = _linked_pair(tmp_path)
    _install_fake_codex_on_path(monkeypatch, tmp_path, slow_first_seconds=60)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "x3-led-hash"
    run_dir.mkdir(mode=0o700)
    first = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="x3-led-hash",
        run_engine=ED._run_engine, max_wait=1, timeout=30, run_dir=str(run_dir),
    )
    assert first.get("running") is True, first
    assert _lease_held_for(linked)
    authority = ED._load_authority(str(run_dir))
    assert authority is not None
    ledger_hash = ED._ledger_expected_hash(
        os.path.realpath(str(run_dir)), authority.run_nonce, authority.order_id)
    assert ledger_hash
    new_hash, _swapped = _swap_sealed_authority(
        run_dir, authority, effort="low", fed_prompt="forged-prompt-x3")
    assert new_hash != ledger_hash
    state_path = run_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["authorityHash"] = new_hash
    state_path.write_text(json.dumps(state), encoding="utf-8")
    # Ledger on disk still names the pre-forge hash (read the record directly —
    # do not call _ledger_expected_hash here; that is the mechanism under bite).
    led_path = ED._ledger_run_record_path(os.path.realpath(str(run_dir)))
    led = json.loads(open(led_path, "rb").read().decode("utf-8"))
    assert led.get("authorityHash") == ledger_hash

    poll = ED.dispatch_poll(str(run_dir), max_wait=1, order_id="x3-led-hash")
    assert poll.get("terminal") is True, poll
    assert poll.get("detail") == ED.AUTHORITY_HASH_MISMATCH, poll
    assert _lease_held_for(linked)

    abandon = ED.dispatch_abandon(str(run_dir))
    assert abandon.get("terminal") is True, abandon
    assert abandon.get("reason") == ED.ABANDON_INCOMPLETE, abandon
    assert abandon.get("detail") == ED.AUTHORITY_HASH_MISMATCH, abandon
    assert _lease_held_for(linked)


def test_x3_bite_ledger_completion_not_run_dir_done(tmp_path):
    """Bite 3: _ledger_attempt_complete gates completion — not the .done sentinel.

    Forged run-dir .done without a ledger completion must keep the run non-terminal
    with the lease held. Making _completed_attempts_from_seals / _find_pending_launch
    trust .done again must break this.
    """
    main, linked = _linked_pair(tmp_path)
    run_dir = tmp_path / "x3-done-bite"
    run_dir.mkdir(mode=0o700)
    lease_token, lease_holder = ED._acquire_worktree_lease_for_cwd(
        os.path.realpath(linked))
    state = _x2_write_state(
        tmp_path, linked, order_id="x3-done-o", run_nonce="x3-done-n",
        lease_token=lease_token, lease_holder=lease_holder, run_dir=run_dir,
        supervisor_pid=999999981, supervisor_start="not-real")
    _persist_test_authority(run_dir, state)
    _seal_test_launch(run_dir, 1, state)
    auth_hash = state["authorityHash"]
    (run_dir / "attempt-1.done").write_text(json.dumps({
        "exit": 0, "timedOut": False, "runNonce": "x3-done-n",
        "authorityHash": auth_hash, "endedAt": time.time(),
        "refusal": None,
    }), encoding="utf-8")
    (run_dir / "attempt-1.stdout").write_text(_WRITE_OK_STDOUT, encoding="utf-8")
    (run_dir / "attempt-1.stderr").write_text("", encoding="utf-8")
    assert ED._ledger_attempt_complete(
        os.path.realpath(str(run_dir)), 1, auth_hash, "x3-done-n") is None
    pending, _ = ED._find_pending_launch(
        os.path.realpath(str(run_dir)), auth_hash, "x3-done-n")
    assert pending == 1
    assert ED._completed_attempts_from_seals(
        os.path.realpath(str(run_dir)), auth_hash, "x3-done-n") == 0
    res = ED.dispatch_poll(str(run_dir), max_wait=0, order_id="x3-done-o")
    assert res.get("terminal") is False, res
    assert res.get("running") is True or not res.get("ok"), res
    assert not (run_dir / "result.json").is_file()
    assert _lease_held_for(linked)
    ED._release_worktree_lease_for_cwd(
        os.path.realpath(linked), lease_token, lease_holder)


def test_x3_bite_oneshot_claim_second_refuses(tmp_path, monkeypatch):
    """Bite 4: _ledger_claim_attempt one-shot — second run-child exits 2, no engine.

    Making _ledger_claim_attempt always return True must break this.
    """
    main, linked = _linked_pair(tmp_path)
    run_dir = tmp_path / "x3-claim-bite"
    run_dir.mkdir(mode=0o700)
    lease_token, lease_holder = ED._acquire_worktree_lease_for_cwd(
        os.path.realpath(linked))
    state = _x2_write_state(
        tmp_path, linked, order_id="x3-cl-o", run_nonce="x3-cl-n",
        lease_token=lease_token, lease_holder=lease_holder, run_dir=run_dir)
    _persist_test_authority(run_dir, state)
    _seal_test_launch(run_dir, 1, state)
    engine_calls = []

    def _no_engine(*a, **k):
        engine_calls.append(1)
        raise AssertionError("engine must not run on second claim")

    monkeypatch.setattr(ED, "_run_engine_files", _no_engine)
    real = os.path.realpath(str(run_dir))
    auth_hash = state["authorityHash"]
    assert ED._ledger_claim_attempt(real, 1, auth_hash, "x3-cl-n") is True
    engine_calls.clear()
    rc2 = ED._run_child_entry(real)
    assert rc2 == 2
    assert engine_calls == []
    assert not (run_dir / "attempt-1.done").is_file()
    ED._release_worktree_lease_for_cwd(
        os.path.realpath(linked), lease_token, lease_holder)


def test_x3_bite_prompt_digest_mismatch_refuses(tmp_path, monkeypatch):
    """Bite 5: prompt-digest-mismatch refusal on swapped prompt.txt.

    Making the digest check unconditional-pass must break this.
    """
    main, linked = _linked_pair(tmp_path)
    sealed_bytes = b"x3-sealed-prompt\n"
    digest = hashlib.sha256(sealed_bytes).hexdigest()
    run_dir = tmp_path / "x3-prompt-bite"
    run_dir.mkdir(mode=0o700)
    lease_token, lease_holder = ED._acquire_worktree_lease_for_cwd(
        os.path.realpath(linked))
    state = _x2_write_state(
        tmp_path, linked, order_id="x3-pr-o", run_nonce="x3-pr-n",
        lease_token=lease_token, lease_holder=lease_holder, run_dir=run_dir)
    state["promptSha256"] = digest
    state["fedPrompt"] = sealed_bytes.decode("utf-8")
    (run_dir / "prompt.txt").write_bytes(sealed_bytes)
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    _persist_test_authority(run_dir, state)
    _seal_test_launch(run_dir, 1, state)
    (run_dir / "prompt.txt").write_bytes(b"ATTACKER-X3-PROMPT\n")
    engine_calls = []

    def _no_engine(*a, **k):
        engine_calls.append(1)
        raise AssertionError("engine must not run on digest mismatch")

    monkeypatch.setattr(ED, "_run_engine_files", _no_engine)
    rc = _invoke_run_child(run_dir, 1, state)
    assert rc == 4
    assert engine_calls == []
    done = json.loads((run_dir / "attempt-1.done").read_text(encoding="utf-8"))
    assert done.get("refusal") == "prompt-digest-mismatch", done
    ED._release_worktree_lease_for_cwd(
        os.path.realpath(linked), lease_token, lease_holder)


def test_x3_bite_launch_timeout_mismatch_refuses(tmp_path, monkeypatch):
    """Bite 6: launch-timeout-mismatch when launch.json timeout is widened.

    Accepting the launch record's timeout again must break this.
    """
    main, linked = _linked_pair(tmp_path)
    run_dir = tmp_path / "x3-timeout-bite"
    run_dir.mkdir(mode=0o700)
    lease_token, lease_holder = ED._acquire_worktree_lease_for_cwd(
        os.path.realpath(linked))
    state = _x2_write_state(
        tmp_path, linked, order_id="x3-to-o", run_nonce="x3-to-n",
        lease_token=lease_token, lease_holder=lease_holder, run_dir=run_dir)
    _persist_test_authority(run_dir, state)
    auth_hash = state["authorityHash"]
    _seal_test_launch(run_dir, 1, state)
    forged = {
        "attempt": 1,
        "authorityHash": auth_hash,
        "runNonce": "x3-to-n",
        "orderId": "x3-to-o",
        "runKind": ED.RUN_KIND_WRITE,
        "timeout": 99999,
    }
    launch_path = os.path.join(str(run_dir), "attempt-1.launch.json")
    os.chmod(launch_path, 0o600)
    open(launch_path, "w", encoding="utf-8").write(json.dumps(forged))
    os.chmod(launch_path, 0o400)
    # Also widen the ledger intent timeout so only the launch-vs-derived check
    # (or a neutralized accept-launch path) is in play for the bite.
    intent_path = ED._ledger_attempt_path(
        os.path.realpath(str(run_dir)), 1, "intent")
    intent = json.loads(open(intent_path, "rb").read().decode("utf-8"))
    intent["timeout"] = 5  # keep intent matching authority-derived
    os.chmod(intent_path, 0o600)
    os.unlink(intent_path)
    ED._ledger_seal(intent_path, intent)
    engine_calls = []

    def _no_engine(*a, **k):
        engine_calls.append(1)
        raise AssertionError("engine must not run on timeout mismatch")

    monkeypatch.setattr(ED, "_run_engine_files", _no_engine)
    rc = _invoke_run_child(run_dir, 1, state)
    assert rc == 4
    assert engine_calls == []
    done = json.loads((run_dir / "attempt-1.done").read_text(encoding="utf-8"))
    assert done.get("refusal") == "launch-timeout-mismatch", done
    ED._release_worktree_lease_for_cwd(
        os.path.realpath(linked), lease_token, lease_holder)


def test_x3_bite_live_child_evidence_release_without_live(tmp_path):
    """Bite 7a: _live_child_evidence False → lease released on completion-payload-absent.

    Making _live_child_evidence always return (True, ...) must break this.
    """
    main, linked = _linked_pair(tmp_path)
    run_dir = tmp_path / "x3-live-rel"
    run_dir.mkdir(mode=0o700)
    lease_token, lease_holder = ED._acquire_worktree_lease_for_cwd(
        os.path.realpath(linked))
    state = _x2_write_state(
        tmp_path, linked, order_id="x3-lr-o", run_nonce="x3-lr-n",
        lease_token=lease_token, lease_holder=lease_holder, run_dir=run_dir,
        in_flight=None, completed=0,
        supervisor_pid=999999982, supervisor_start="dead-x3")
    _persist_test_authority(run_dir, state)
    auth_hash = state["authorityHash"]
    run_real = os.path.realpath(str(run_dir))
    ED._ledger_seal_attempt_intent(
        run_real, 1, auth_hash, "x3-lr-n", 5, list(state["worktreeSnapshot"]))
    ED._ledger_seal(ED._ledger_attempt_path(run_real, 1, "claim"), {
        "schemaVersion": ED.LEDGER_SCHEMA_VERSION,
        "attempt": 1,
        "authorityHash": auth_hash,
        "runNonce": "x3-lr-n",
        "childPid": 999999982,
        "childStart": "dead-x3",
    })
    ED._ledger_seal_attempt_complete(run_real, 1, auth_hash, "x3-lr-n")
    assert not (run_dir / "attempt-1.done").is_file()
    res = ED.dispatch_poll(str(run_dir), max_wait=0, order_id="x3-lr-o")
    assert res.get("detail") == "completion-payload-absent", res
    assert res.get("terminal") is True
    assert not _lease_held_for(linked), "no live evidence ⇒ lease must release"


def test_x3_bite_live_child_evidence_retain_on_live_claim(tmp_path):
    """Bite 7b: _live_child_evidence True → lease retained on completion-payload-absent.

    Making _live_child_evidence always return (False, None) must break this.
    """
    main, linked = _linked_pair(tmp_path)
    run_dir = tmp_path / "x3-live-ret"
    run_dir.mkdir(mode=0o700)
    lease_token, lease_holder = ED._acquire_worktree_lease_for_cwd(
        os.path.realpath(linked))
    live_pid = os.getpid()
    state = _x2_write_state(
        tmp_path, linked, order_id="x3-lt-o", run_nonce="x3-lt-n",
        lease_token=lease_token, lease_holder=lease_holder, run_dir=run_dir,
        in_flight=None, completed=0,
        supervisor_pid=live_pid,
        supervisor_start=ED._supervisor_lstart(live_pid) or "live")
    _persist_test_authority(run_dir, state)
    auth_hash = state["authorityHash"]
    run_real = os.path.realpath(str(run_dir))
    ED._ledger_seal_attempt_intent(
        run_real, 1, auth_hash, "x3-lt-n", 5, list(state["worktreeSnapshot"]))
    ED._ledger_seal(ED._ledger_attempt_path(run_real, 1, "claim"), {
        "schemaVersion": ED.LEDGER_SCHEMA_VERSION,
        "attempt": 1,
        "authorityHash": auth_hash,
        "runNonce": "x3-lt-n",
        "childPid": live_pid,
        "childStart": state["supervisorStart"],
    })
    ED._ledger_seal_attempt_complete(run_real, 1, auth_hash, "x3-lt-n")
    assert not (run_dir / "attempt-1.done").is_file()
    res = ED.dispatch_poll(str(run_dir), max_wait=0, order_id="x3-lt-o")
    assert res.get("detail") == "completion-payload-absent", res
    assert res.get("terminal") is True
    assert "live claimed run-child" in (res.get("disclosure") or ""), res
    assert _lease_held_for(linked), "live claim ⇒ lease must retain"
    ED._release_worktree_lease_for_cwd(
        os.path.realpath(linked), lease_token, lease_holder)
