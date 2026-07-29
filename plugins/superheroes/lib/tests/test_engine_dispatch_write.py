"""Tests for dispatch-write (#702) and write-specific supervision edges."""
import importlib.util
import inspect
import json
import os
import shutil
import subprocess
import sys
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


def test_run_child_rejects_forged_cwd(tmp_path):
    main, linked = _linked_pair(tmp_path)
    run_dir = tmp_path / "run"
    run_dir.mkdir(mode=0o700)
    (run_dir / "prompt.txt").write_bytes(b"x")
    built = EA.build_argv_result(
        "codex", "build", "high",
        {"engine_model": "gpt-5.6-terra", "cwd": linked},
    )
    argv = built["argv"]
    resolved = shutil.which(argv[0])
    state = {
        "engine": "codex",
        "roleKind": "build",
        "dispatchMode": ED.WRITE_DISPATCH_MODE,
        "effort": "high",
        "engineModel": "gpt-5.6-terra",
        "cwd": linked,
        "argv": argv,
        "engineBinary": resolved,
        "attemptTimeout": 5,
        "runNonce": "nonce-forged-cwd",
        "orderId": "o-forge",
    }
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    _invoke_run_child(
        run_dir, 1, state,
        launch_cwd=main,
        run_nonce="nonce-forged-cwd",
        order_id="o-forge",
    )
    done = json.loads((run_dir / "attempt-1.done").read_text(encoding="utf-8"))
    assert done.get("refusal") == "cwd-primary-checkout"


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


def test_dispatch_write_spawned_argv_echo(tmp_path):
    main, linked = _linked_pair(tmp_path)
    ok_stdout = json.dumps({"ok": True, "signal": "ok", "evidence": {}})
    fake = FakeWriteRunner([(ok_stdout, False, 0, "")])
    run_dir = tmp_path / "run"
    run_dir.mkdir(mode=0o700)
    res = ED.dispatch_write(
        "codex", engine_model="gpt-5.6-terra", effort="high",
        prompt_path=_prompt(tmp_path), cwd=linked, order_id="o1", run_engine=fake,
        max_wait=60, run_dir=str(run_dir),
    )
    assert res["ok"] is True
    _assert_spawned_argv_pair(res)
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["argv"] == res["argv"]
    assert state["spawnedArgv"] == res["spawnedArgv"]


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


def test_dispatch_review_spawned_argv_echo(tmp_path):
    repo_root = _review_repo(tmp_path)
    build_view = _fake_review_build_view(tmp_path)
    fake = _ReviewFakeRunner([(_VALID_REVIEW_STDOUT, False, 0, "")])
    run_dir = tmp_path / "run-review"
    run_dir.mkdir(mode=0o700)
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=build_view, run_dir=str(run_dir), max_wait=60,
    )
    assert res["ok"] is True
    _assert_spawned_argv_pair(res)
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["argv"] == res["argv"]
    assert state["spawnedArgv"] == res["spawnedArgv"]


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


def test_dispatch_review_kind_check_mutation_probe(tmp_path, monkeypatch):
    """Production-file mutation probe for edge 1 (revert is inverse edit)."""
    main, linked = _linked_pair(tmp_path)
    prompt = _prompt(tmp_path)
    write_run = _seed_write_run(tmp_path, linked, prompt)
    path = os.path.join(_HERE, "..", "engine_dispatch.py")
    anchor = "if _recorded_run_kind(state_probe) != RUN_KIND_REVIEW:"
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    assert anchor in src
    mutated = src.replace(
        anchor,
        "if False and _recorded_run_kind(state_probe) != RUN_KIND_REVIEW:",
        1,
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(mutated)
    try:
        ED_probe = _load_ed()
        spawned = []
        monkeypatch.setattr(ED_probe, "_spawn_run_child", lambda *a, **k: spawned.append(1))
        repo_root = _review_repo(tmp_path)
        build_view = _fake_review_build_view(tmp_path)
        fake = _ReviewFakeRunner([])
        res_mut = ED_probe.dispatch_review(
            "codex", model="sonnet", effort="high",
            prompt_path=prompt, repo_root=repo_root, run_engine=fake,
            build_view=build_view, run_dir=write_run, max_wait=10,
        )
        assert res_mut.get("reason") != "run-kind-mismatch"
    finally:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(src)
    global ED
    ED = _load_ed()
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=prompt, repo_root=_review_repo(tmp_path / "probe-base"),
        run_engine=_ReviewFakeRunner([]),
        build_view=_fake_review_build_view(tmp_path / "probe-view"),
        run_dir=write_run, max_wait=10,
    )
    assert res["reason"] == "run-kind-mismatch"
