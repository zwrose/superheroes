"""Tests for dispatch-write (#702) and write-specific supervision edges."""
import importlib.util
import inspect
import json
import os
import shutil
import signal
import subprocess
import sys
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


def _invoke_run_child(run_dir, attempt, state, **kw):
    run_dir = str(run_dir)
    kind = (
        ED.RUN_KIND_WRITE
        if state.get("dispatchMode") == ED.WRITE_DISPATCH_MODE
        else ED.RUN_KIND_REVIEW
    )
    nonce = kw.get("run_nonce", state.get("runNonce", "test-nonce"))
    order_id = kw.get("order_id", state.get("orderId") or "")
    launch_argv = kw.get("launch_argv", state.get("argv"))
    if "launch_cwd" in kw:
        launch_cwd = kw["launch_cwd"]
    elif kind == ED.RUN_KIND_WRITE:
        launch_cwd = state.get("cwd")
    else:
        launch_cwd = os.path.join(run_dir, ED.REVIEW_CWD_DIRNAME)
    return ED._run_child_main(
        run_dir,
        attempt,
        expected_kind=kind,
        run_nonce=nonce or "",
        order_id=order_id or "",
        launch_cwd=str(launch_cwd),
        launch_argv=list(launch_argv or []),
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
    real_spawn = ED._spawn_run_child

    def _inline(rd, attempt, launch):
        children.append(attempt)
        ED._run_child_main(
            str(rd),
            attempt,
            expected_kind=launch["kind"],
            run_nonce=launch.get("run_nonce") or "",
            order_id=launch.get("order_id") or "",
            launch_cwd=launch.get("launch_cwd") or "",
            launch_argv=list(launch.get("argv") or []),
        )

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
    """Codex dispatch resume: forged cwd with argv rebuilt for the forged tree."""
    main, linked1, linked2 = _two_linked_worktrees(tmp_path)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "forge-run"
    state = _seed_write_dispatch_completed_attempt(
        tmp_path, engine="codex", linked1=linked1, prompt=prompt,
        run_dir=run_dir, order_id="forge-o",
    )
    forged = EA.build_argv_result(
        "codex", "build", "high",
        {"engine_model": "gpt-5.6-terra", "cwd": linked2},
    )
    _prepare_forged_cwd_retry_state(
        state, run_dir, linked1, linked2, argv=forged["argv"],
    )
    spawned = []
    monkeypatch.setattr(ED, "_spawn_run_child", lambda *a, **k: spawned.append(1))
    res2 = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked1, order_id="forge-o",
        run_engine=ED._run_engine, max_wait=60, run_dir=str(run_dir),
    )
    assert spawned == [], res2
    assert res2.get("terminal") is True
    assert res2.get("detail") == "cwd-authorization-mismatch"


def test_run_child_rejects_forged_cwd_codex_argv_consistent(tmp_path, monkeypatch):
    """Codex run-child: argv re-derives for the authorized cwd; only cwd identity is wrong."""
    main, linked1, linked2 = _two_linked_worktrees(tmp_path)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "forge-codex-argv-ok"
    state = _seed_write_dispatch_completed_attempt(
        tmp_path, engine="codex", linked1=linked1, prompt=prompt,
        run_dir=run_dir, order_id="forge-codex-argv",
    )
    authorized_argv = EA.build_argv_result(
        "codex", "build", "high",
        {"engine_model": "gpt-5.6-terra", "cwd": linked1},
    )["argv"]
    state = _prepare_forged_cwd_retry_state(
        state, run_dir, linked1, linked2, argv=authorized_argv,
    )
    spawned = _spy_engine_files_no_spawn(monkeypatch)
    _invoke_run_child(
        run_dir, 2, state,
        launch_cwd=linked1,
        launch_argv=authorized_argv,
    )
    assert spawned == []
    done = json.loads((run_dir / "attempt-2.done").read_text(encoding="utf-8"))
    assert done.get("refusal") == "cwd-authorization-mismatch"
    assert done.get("refusal") != "argv-rederivation-mismatch"


def test_run_child_rejects_forged_cwd_cursor(tmp_path, monkeypatch):
    """Cursor run-child: forged cwd leaves argv byte-identical; authorization check is sole guard."""
    main, linked1, linked2 = _two_linked_worktrees(tmp_path)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "forge-cursor"
    state = _seed_write_dispatch_completed_attempt(
        tmp_path, engine="cursor", linked1=linked1, prompt=prompt,
        run_dir=run_dir, order_id="forge-cursor-o",
    )
    original_argv = list(state["argv"])
    state = _prepare_forged_cwd_retry_state(state, run_dir, linked1, linked2)
    assert state["argv"] == original_argv
    spawned = _spy_engine_files_no_spawn(monkeypatch)
    _invoke_run_child(
        run_dir, 2, state,
        launch_cwd=linked1,
        launch_argv=original_argv,
    )
    assert spawned == []
    done = json.loads((run_dir / "attempt-2.done").read_text(encoding="utf-8"))
    assert done.get("refusal") == "cwd-authorization-mismatch"
    assert done.get("refusal") != "argv-rederivation-mismatch"


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


def test_retry_unsafe_attempt_still_live(tmp_path, monkeypatch):
    main, linked = _linked_pair(tmp_path)
    ok_stdout = json.dumps({"ok": True, "signal": "ok", "evidence": {}})
    fake = FakeWriteRunner([
        ("", True, 0, ""),
        (ok_stdout, False, 0, ""),
    ])
    monkeypatch.setattr(ED, "_process_alive", lambda pid: True)
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=_prompt(tmp_path), cwd=linked, order_id="o1", run_engine=fake,
        max_wait=120,
    )
    assert res["terminal"] is True
    assert res["detail"] == "retry-unsafe-attempt-still-live"
    assert res["forfeited"] is True
    assert res["attempts"] == 1
    assert len(fake.calls) == 1


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
    }
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    ED._run_child_main(
        str(run_dir), 1,
        expected_kind=ED.RUN_KIND_REVIEW,
        run_nonce="nonce-a",
        order_id="o1",
        launch_cwd=linked,
        launch_argv=argv,
    )
    done = json.loads((run_dir / "attempt-1.done").read_text(encoding="utf-8"))
    assert done.get("refusal") == "run-kind-mismatch"


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
    ED._release_worktree_lease(state)
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
    """Edge 1: abandon kills the engine process group recorded by the supervisor."""
    main, linked = _linked_pair(tmp_path)
    run_dir = tmp_path / "abandon-engine-pg"
    run_dir.mkdir(mode=0o700)
    code = (
        "import time\n"
        "time.sleep(120)\n"
    )
    proc = subprocess.Popen(
        ["python3", "-c", code], start_new_session=True,
    )
    pgid = proc.pid
    paths = ED._attempt_paths(str(run_dir), 1)
    ED._write_engine_pgid(paths["engine_pgid"], pgid)
    lease_token, lease_holder = ED._acquire_worktree_lease_for_cwd(os.path.realpath(linked))
    try:
        (run_dir / "state.json").write_text(json.dumps({
            "engine": "codex",
            "dispatchMode": ED.WRITE_DISPATCH_MODE,
            "cwd": linked,
            "argv": [],
            "inFlightAttempt": 1,
            "completedAttempts": 0,
            "worktreeLeaseToken": lease_token,
            "worktreeLeaseHolder": lease_holder,
        }), encoding="utf-8")
        res = ED.dispatch_abandon(str(run_dir))
        assert res.get("reason") == "abandoned"
        time.sleep(0.5)
        try:
            os.killpg(pgid, 0)
            dead = False
        except OSError:
            dead = True
        assert dead
    finally:
        ED._release_worktree_lease_for_cwd(
            os.path.realpath(linked), lease_token, lease_holder)
        try:
            os.killpg(pgid, signal.SIGKILL)
        except OSError:
            pass


def test_abandon_engine_group_unconfirmed_lease_stays_held(tmp_path, monkeypatch):
    """Edge 2: unconfirmed engine death → lease held, named detail."""
    main, linked = _linked_pair(tmp_path)
    run_dir = tmp_path / "abandon-lease"
    run_dir.mkdir(mode=0o700)
    paths = ED._attempt_paths(str(run_dir), 1)
    ED._write_engine_pgid(paths["engine_pgid"], os.getpid())
    lease_token, lease_holder = ED._acquire_worktree_lease_for_cwd(os.path.realpath(linked))
    import file_lock
    lease_path = ED._worktree_lease_path(os.path.realpath(linked))
    monkeypatch.setattr(ED, "_terminate_process_group", lambda _pgid: False)
    try:
        (run_dir / "state.json").write_text(json.dumps({
            "engine": "codex",
            "dispatchMode": ED.WRITE_DISPATCH_MODE,
            "cwd": linked,
            "argv": [],
            "inFlightAttempt": 1,
            "worktreeLeaseToken": lease_token,
            "worktreeLeaseHolder": lease_holder,
        }), encoding="utf-8")
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
    res = ED._run_engine_files(
        ["python3", "-c", code],
        str(prompt), str(stdout), str(stderr),
        30, None, 1, str(tmp_path),
        engine_pgid_path=str(tmp_path / "pgid.json"),
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
    """Edge 4: poll stays observational when retry is pending."""
    run_dir = tmp_path / "poll-retry"
    run_dir.mkdir(mode=0o700)
    (run_dir / "attempt-1.done").write_text(json.dumps({
        "exit": None, "timedOut": True, "runNonce": "n1",
    }), encoding="utf-8")
    (run_dir / "attempt-1.stdout").write_text("", encoding="utf-8")
    (run_dir / "attempt-1.stderr").write_text("", encoding="utf-8")
    (run_dir / "state.json").write_text(json.dumps({
        "engine": "codex",
        "roleKind": "review",
        "effort": "high",
        "model": "sonnet",
        "argv": ["codex"],
        "runNonce": "n1",
        "repoRoot": str(tmp_path / "repo"),
        "promptPath": str(run_dir / "prompt.txt"),
        "viewReceipt": {},
        "fedPrompt": "",
        "inFlightAttempt": 1,
        "completedAttempts": 0,
        "attemptStartedAt": time.time(),
    }), encoding="utf-8")
    spawned = []
    monkeypatch.setattr(ED, "_spawn_run_child", lambda *a, **k: spawned.append(1) or None)
    res = ED.dispatch_poll(str(run_dir), max_wait=1)
    assert res.get("terminal") is False
    assert ED.RETRY_PENDING_DETAIL in (res.get("detail") or "")
    assert spawned == []
    assert not (run_dir / "attempt-2.stdout").exists()


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
    procs = []
    try:
        for run_dir, kind, launch_cwd, argv in (
            (str(write_run), ED.RUN_KIND_WRITE, linked, built_w["argv"]),
            (review_run, ED.RUN_KIND_REVIEW, str(Path(review_run) / ED.REVIEW_CWD_DIRNAME), built_r["argv"]),
        ):
            for attempt in (1, 2):
                launch = {
                    "kind": kind,
                    "run_nonce": "spawn-nonce-w" if kind == ED.RUN_KIND_WRITE else "spawn-nonce-r",
                    "order_id": "spawn-w" if kind == ED.RUN_KIND_WRITE else "",
                    "launch_cwd": launch_cwd,
                    "argv": argv,
                }
                proc = ED._spawn_run_child(run_dir, attempt, launch)
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

    def _track(rd, att, launch):
        proc = real_spawn(rd, att, launch)
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
    monkeypatch.setattr(ED, "_process_alive", lambda _pid: False)
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
    monkeypatch.setattr(ED, "_process_alive", lambda _pid: False)
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
    """Edge 4: one dispatch-write call returns running within max_wait while retry is long."""
    main, linked = _linked_pair(tmp_path)
    _install_fake_codex_on_path(monkeypatch, tmp_path, slow_first_seconds=60)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "retry-bounded"
    run_dir.mkdir(mode=0o700)
    t0 = time.monotonic()
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=prompt, cwd=linked, order_id="retry-bounded",
        run_engine=ED._run_engine, max_wait=2, timeout=5, run_dir=str(run_dir),
    )
    elapsed = time.monotonic() - t0
    assert elapsed < 15, elapsed
    assert res.get("terminal") is False
    assert res.get("running") is True
    assert res.get("resume")


def test_write_retry_spawns_once_after_poll_then_resume(tmp_path, monkeypatch):
    """Edge 5: poll → retry-pending → re-invoke reaches terminal in exactly one retry."""
    main, linked = _linked_pair(tmp_path)
    _install_fake_codex_on_path(monkeypatch, tmp_path, slow_first_seconds=60)
    prompt = _prompt(tmp_path)
    run_dir = tmp_path / "retry-detached"
    run_dir.mkdir(mode=0o700)
    spawned_children = []
    real_spawn = ED._spawn_run_child

    def _track_spawn(rd, att, launch):
        spawned_children.append(att)
        proc = real_spawn(rd, att, launch)
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
    monkeypatch.setattr(ED, "_process_alive", lambda _pid: False)
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
    wstate_sp = dict(wstate)
    cmd_w = ED._resume_command_write(run_dir_sp, 540, wstate_sp)
    assert _parse_resume_cli(cmd_w) == 0
    rstate = {
        "engine": "codex",
        "effort": "high",
        "model": "sonnet",
        "repoRoot": main,
        "promptPath": prompt,
        "orderId": "r1",
    }
    cmd_r = ED._resume_command_review(run_dir_sp, 540, rstate)
    assert _parse_resume_cli(cmd_r) == 0
    cmd_w2 = ED._resume_command_write(run_dir, 540, wstate)
    assert _parse_resume_cli(cmd_w2) == 0
    lease_res = ED._running_result(
        run_dir, wstate, 1, wstate["argv"], 0, 540,
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
    res = ED.dispatch_poll(str(run_dir), max_wait=0)
    assert res.get("terminal") is False
    assert ED.RETRY_PENDING_DETAIL in (res.get("detail") or "")


def test_spawn_failed_compensates_state_and_lease(tmp_path, monkeypatch):
    """Edge 7: failed supervisor spawn persists terminal result and releases write lease."""
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
    import file_lock
    assert not file_lock.read_holder(ED._worktree_lease_path(os.path.realpath(linked)))

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
