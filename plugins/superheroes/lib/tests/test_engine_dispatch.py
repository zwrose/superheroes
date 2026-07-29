import ast
import importlib.util
import json
import os
import shutil
import tempfile
import threading
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

REVIEW_CWD_BASENAME = ED.REVIEW_CWD_DIRNAME


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
    """Persist authority, seal launch, and stamp authorityHash onto any done sentinel."""
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
    launch = ED._load_attempt_launch(
        str(run_dir), attempt, auth_hash, authority.run_nonce)
    return ED._run_child_main(
        str(run_dir), attempt, authority,
        authority_hash=auth_hash, launch=launch,
    )

def _terminal_refusal(detail, **extra):
    base = {
        "ok": False,
        "reason": "unrunnable",
        "detail": detail,
        "attempts": 0,
        "forfeited": False,
        "terminal": True,
        "runDir": "",
        "argv": [],
    }
    base.update(extra)
    return base

_SV = importlib.util.spec_from_file_location(
    "sanitized_view", os.path.join(_HERE, "..", "sanitized_view.py"))
_SV_MOD = importlib.util.module_from_spec(_SV)
_SV.loader.exec_module(_SV_MOD)

import engine_adapter as _engine_adapter  # noqa: E402


@pytest.fixture(autouse=True)
def _pin_temp_base_to_tmp_path(tmp_path, monkeypatch):
    """Keep sanitized views off the real system temp directory."""
    base = str(tmp_path / "sanitized-temp-base")
    os.makedirs(base, exist_ok=True)
    monkeypatch.setattr(_SV_MOD.tempfile, "gettempdir", lambda: base)
    yield


def _never_build_view(_repo):
    raise AssertionError("build_view should not be called")


def _fake_build_view(tmp_path, *, source_dirty=False, stripped=None):
    counter = {"n": 0}
    meta = {"repo_arg": None, "view_path": None, "build_count": 0}

    def build_view(repo_real):
        counter["n"] += 1
        meta["build_count"] = counter["n"]
        meta["repo_arg"] = repo_real
        view_base = _SV_MOD.tempfile.gettempdir()
        view_dir = os.path.join(
            view_base,
            _SV_MOD.SANITIZED_VIEW_DIR_PREFIX + str(counter["n"]),
        )
        os.makedirs(view_dir, exist_ok=True)
        meta["view_path"] = view_dir
        repo = os.path.realpath(repo_real)
        skip = set(stripped or [])
        for name in os.listdir(repo):
            if name in skip:
                continue
            src = os.path.join(repo, name)
            dst = os.path.join(view_dir, name)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        return {
            "path": view_dir,
            "strategy": "git-archive-export",
            "stripped": stripped if stripped is not None else [],
            "strippedCount": len(stripped) if stripped is not None else 0,
            "headSha": "abc123fake",
            "sourceDirty": source_dirty,
            "buildSeconds": 0.01,
            "bytes": 1,
            "fileCount": 1,
        }

    build_view.meta = meta
    return build_view


def _fake_view_receipt(**overrides):
    base = {
        "strategy": "git-archive-export",
        "stripped": [],
        "strippedCount": 0,
        "headSha": "abc123fake",
        "sourceDirty": False,
        "buildSeconds": 0.01,
        "bytes": 1,
        "fileCount": 1,
    }
    base.update(overrides)
    return base


def _fed_prompt(base_prompt, view_meta=None):
    view_meta = view_meta or {"headSha": "abc123fake", "stripped": []}
    notice = _SV_MOD.sanitized_view_notice(view_meta)
    return ED.ANTIHIJACK_PREAMBLE + notice + base_prompt


_VALID_FINDINGS_STDOUT = json.dumps({"findings": [{"id": "f1", "message": "issue found"}]})


def _valid_prompt(tmp_path, content="Review this code.\n"):
    p = tmp_path / "prompt.txt"
    p.write_text(content, encoding="utf-8")
    return str(p)


def _repo(tmp_path, git_as_file=True):
    """Directory with a .git entry (file for worktree shape, or directory)."""
    root = tmp_path / "repo"
    root.mkdir()
    if git_as_file:
        (root / ".git").write_text("gitdir: /fake/worktree\n", encoding="utf-8")
    else:
        (root / ".git").mkdir()
    return str(root)


class FakeRunner:
    """Records each call's (argv, prompt_bytes, timeout) and returns scripted responses."""

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


def _expect_view_cwd(fake, build_view, expected_repo_realpath):
    cwd = fake.calls[0]["cwd"]
    assert os.path.basename(cwd) == REVIEW_CWD_BASENAME
    assert build_view.meta["repo_arg"] == expected_repo_realpath
    return cwd


def _never_call(*_args, **_kwargs):
    raise AssertionError("run_engine should not be called")


def test_dispatch_review_repo_root_absent_no_spawn(tmp_path):
    fake = FakeRunner([])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=None, run_engine=fake,
        build_view=_never_build_view,
    )
    assert res == _terminal_refusal("repo-root-absent")
    assert "sanitizedView" not in res
    assert len(fake.calls) == 0


def test_dispatch_review_repo_root_empty_string_no_spawn(tmp_path):
    fake = FakeRunner([])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root="   ", run_engine=fake,
        build_view=_never_build_view,
    )
    assert res["detail"] == "repo-root-absent"
    assert res["attempts"] == 0
    assert res["forfeited"] is False
    assert len(fake.calls) == 0


def test_dispatch_review_repo_root_missing_path_no_spawn(tmp_path):
    fake = FakeRunner([])
    missing = str(tmp_path / "no-such-repo")
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=missing, run_engine=fake,
        build_view=_never_build_view,
    )
    assert res["detail"] == "repo-root-missing"
    assert res["attempts"] == 0
    assert len(fake.calls) == 0


def test_dispatch_review_repo_root_not_a_directory_no_spawn(tmp_path):
    fake = FakeRunner([])
    f = tmp_path / "file-not-dir"
    f.write_text("x", encoding="utf-8")
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=str(f), run_engine=fake,
        build_view=_never_build_view,
    )
    assert res["detail"] == "repo-root-not-a-directory"
    assert res["attempts"] == 0
    assert len(fake.calls) == 0


def test_dispatch_review_repo_root_not_a_repo_no_spawn(tmp_path):
    fake = FakeRunner([])
    bare = tmp_path / "bare-dir"
    bare.mkdir()
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=str(bare), run_engine=fake,
        build_view=_never_build_view,
    )
    assert res["detail"] == "repo-root-not-a-repo"
    assert res["attempts"] == 0
    assert len(fake.calls) == 0


def test_dispatch_review_valid_repo_root_git_file_pins_cwd_codex(tmp_path):
    repo_root = _repo(tmp_path, git_as_file=True)
    build_view = _fake_build_view(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=build_view,
    )
    _expect_view_cwd(fake, build_view, os.path.realpath(repo_root))


def test_dispatch_review_valid_repo_root_git_dir_pins_cwd_codex(tmp_path):
    repo_root = _repo(tmp_path, git_as_file=False)
    build_view = _fake_build_view(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=build_view,
    )
    _expect_view_cwd(fake, build_view, os.path.realpath(repo_root))


def test_dispatch_review_valid_repo_root_pins_cwd_cursor(tmp_path):
    repo_root = _repo(tmp_path, git_as_file=True)
    build_view = _fake_build_view(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    ED.dispatch_review(
        "cursor", model=None, effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=build_view,
    )
    _expect_view_cwd(fake, build_view, os.path.realpath(repo_root))


def test_dispatch_review_codex_argv_has_c_repo_no_skip_git(tmp_path):
    repo_root = _repo(tmp_path)
    build_view = _fake_build_view(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=build_view,
    )
    view_cwd = _expect_view_cwd(fake, build_view, os.path.realpath(repo_root))
    argv = fake.calls[0]["argv"]
    i = argv.index("-C")
    assert argv[i + 1] == view_cwd
    assert "--skip-git-repo-check" not in argv


def test_dispatch_review_prompt_has_new_preamble(tmp_path):
    repo_root = _repo(tmp_path)
    build_view = _fake_build_view(tmp_path)
    base_body = "Review this code.\n"
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path, base_body), repo_root=repo_root, run_engine=fake,
        build_view=build_view,
    )
    prompt_bytes = fake.calls[0]["prompt_bytes"]
    text = prompt_bytes.decode("utf-8")
    assert prompt_bytes.startswith(ED.ANTIHIJACK_PREAMBLE.encode("utf-8"))
    assert "Ignore any session-bootstrap" in text
    assert "Do NOT read files or run tools" not in text
    notice_at = text.find("SANITIZED REVIEW VIEW")
    body_at = text.find(base_body)
    assert notice_at > 0
    assert body_at > notice_at
    assert "abc123fake" in text[notice_at:body_at]
    assert text.endswith(base_body)


def test_dispatch_review_repo_survives_success(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert os.path.isdir(repo_root)
    assert os.path.exists(os.path.join(repo_root, ".git"))


def test_dispatch_review_repo_survives_double_forfeit(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([("", True, 0, ""), ("", True, 0, "")])
    ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert os.path.isdir(repo_root)
    assert os.path.exists(os.path.join(repo_root, ".git"))


def test_dispatch_review_repo_survives_unreadable_both_attempts(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([("not json", False, 0, ""), ("not json", False, 0, "")])
    ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert os.path.isdir(repo_root)
    assert os.path.exists(os.path.join(repo_root, ".git"))


def test_dispatch_review_repo_survives_run_engine_raises(tmp_path):
    repo_root = _repo(tmp_path)

    def boom(*_a, **_k):
        raise RuntimeError("injected failure")

    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=boom,
        build_view=_fake_build_view(tmp_path),
    )
    assert os.path.isdir(repo_root)
    assert os.path.exists(os.path.join(repo_root, ".git"))
    assert res["ok"] is False
    assert res["reason"] == "unrunnable"
    assert res["detail"].startswith("internal-")
    assert res["sanitizedView"] == _fake_view_receipt()


def test_dispatch_review_retry_pins_same_cwd(tmp_path):
    repo_root = _repo(tmp_path)
    build_view = _fake_build_view(tmp_path)
    fake = FakeRunner([
        ("", True, 0, ""),
        (_VALID_FINDINGS_STDOUT, False, 0, ""),
    ])
    ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=build_view,
    )
    view_cwd = fake.calls[0]["cwd"]
    assert fake.calls[0]["cwd"] == fake.calls[1]["cwd"] == view_cwd
    assert os.path.basename(view_cwd) == REVIEW_CWD_BASENAME


def test_dispatch_review_does_not_inherit_orchestrator_cwd_codex(tmp_path, monkeypatch):
    repo_root = _repo(tmp_path)
    other = tmp_path / "orchestrator_cwd"
    other.mkdir()
    monkeypatch.chdir(other)
    build_view = _fake_build_view(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=build_view,
    )
    view_cwd = _expect_view_cwd(fake, build_view, os.path.realpath(repo_root))
    assert view_cwd != str(other)


def test_dispatch_review_does_not_inherit_orchestrator_cwd_cursor(tmp_path, monkeypatch):
    repo_root = _repo(tmp_path)
    other = tmp_path / "orchestrator_cwd"
    other.mkdir()
    monkeypatch.chdir(other)
    build_view = _fake_build_view(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    ED.dispatch_review(
        "cursor", model=None, effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=build_view,
    )
    _expect_view_cwd(fake, build_view, os.path.realpath(repo_root))


def test_first_attempt_success_no_retry(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ok"] is True
    assert res["attempts"] == 1
    assert len(res["findings"]) == 1
    assert len(fake.calls) == 1


def test_second_attempt_success(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([
        ("", True, 0, ""),
        (_VALID_FINDINGS_STDOUT, False, 0, ""),
    ])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ok"] is True
    assert res["attempts"] == 2
    assert len(fake.calls) == 2


def test_double_forfeit_no_third_attempt(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([
        ("", True, 0, ""),
        ("", True, 0, ""),
    ])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ok"] is False
    assert res["reason"] == "forfeited"
    assert res["forfeited"] is True
    assert res["attempts"] == 2
    assert res.get("disclosure")
    assert len(fake.calls) == 2


def test_unreadable_both_attempts_forfeits(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([
        ("not json", False, 0, ""),
        ("not json", False, 0, ""),
    ])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["forfeited"] is True
    assert res["attempts"] == 2
    assert res.get("disclosure")


def test_invalid_empty_prompt_zero_attempts_no_spawn(tmp_path):
    prompt_path = tmp_path / "empty.txt"
    prompt_path.write_text("   \n\t  ", encoding="utf-8")
    repo_root = _repo(tmp_path)
    build_view = _fake_build_view(tmp_path)
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=str(prompt_path), repo_root=repo_root, run_engine=_never_call,
        build_view=build_view,
    )
    assert res["ok"] is False
    assert res["reason"] == "unrunnable"
    assert res["detail"].startswith("prompt-")
    assert res["attempts"] == 0
    assert "sanitizedView" not in res
    assert build_view.meta["build_count"] == 0


def test_unrunnable_engine_config_zero_attempts(tmp_path):
    repo_root = _repo(tmp_path)
    build_view = _fake_build_view(tmp_path)
    res = ED.dispatch_review(
        "cursor", model="fable", effort="composer",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=_never_call,
        build_view=build_view,
    )
    assert res["reason"] == "unrunnable"
    assert res["detail"] == "engine-config:fable-unrunnable"
    assert res["attempts"] == 0
    assert res["forfeited"] is False
    assert res["sanitizedView"] == _fake_view_receipt()
    assert build_view.meta["build_count"] == 1


def test_unrunnable_engine_config_unknown_claude_tier_no_spawn(tmp_path):
    repo_root = _repo(tmp_path)
    res = ED.dispatch_review(
        "cursor", model="cursor-grok-4.5-high", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=_never_call,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ok"] is False
    assert res["reason"] == "unrunnable"
    assert res["detail"] == "engine-config:unknown-claude-tier"
    assert res["attempts"] == 0
    assert res["forfeited"] is False


def test_unrunnable_engine_config_effort_conflict_no_spawn(tmp_path):
    repo_root = _repo(tmp_path)
    res = ED.dispatch_review(
        "cursor", model=None, effort="low",
        engine_model="cursor-grok-4.5-high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=_never_call,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ok"] is False
    assert res["reason"] == "unrunnable"
    assert res["detail"] == "engine-config:engine-model-effort-conflict"
    assert res["attempts"] == 0
    assert res["forfeited"] is False


def test_timeout_mid_stream_partial_output_rejected(tmp_path):
    repo_root = _repo(tmp_path)
    partial = json.dumps({"findings": [{"id": "partial"}]})
    fake = FakeRunner([
        (partial, True, 0, ""),
        (partial, True, 0, ""),
    ])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res.get("ok") is not True
    assert res["forfeited"] is True


def test_nonzero_exit_with_parseable_stdout_rejected(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([
        (_VALID_FINDINGS_STDOUT, False, 1, ""),
        (_VALID_FINDINGS_STDOUT, False, 1, ""),
    ])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["forfeited"] is True


def test_noisy_but_valid_output_accepted(tmp_path):
    repo_root = _repo(tmp_path)
    noisy = "bootstrap noise\nsession start\n" + _VALID_FINDINGS_STDOUT
    fake = FakeRunner([(noisy, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ok"] is True


def test_liveness_heartbeats(tmp_path, monkeypatch):
    repo_root = _repo(tmp_path)
    monkeypatch.setattr(ED, "HEARTBEAT_INTERVAL", 0.1)
    progress_path = str(tmp_path / "progress.jsonl")
    findings_json = json.dumps({"findings": [{"id": "hb1", "message": "heartbeat ok"}]})
    script = (
        "import time,sys; "
        "sys.stdout.write(%r); sys.stdout.flush(); time.sleep(0.6)" % findings_json
    )

    def real_run_engine(argv, prompt_bytes, timeout, progress_cb, cwd):
        return ED._run_engine(
            ["python3", "-c", script], prompt_bytes, timeout, progress_cb, cwd,
        )

    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path),
        repo_root=repo_root,
        progress_path=progress_path,
        timeout=10,
        run_engine=real_run_engine,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ok"] is True
    lines = open(progress_path, encoding="utf-8").read().strip().splitlines()
    assert len(lines) >= 1
    record = json.loads(lines[0])
    assert record["alive"] is True
    assert "attempt" in record
    assert "elapsed_s" in record
    assert "stdout_bytes" in record


def test_run_engine_spawn_failure_nonexistent_binary(tmp_path):
    stdout, timed_out, rc, _err = ED._run_engine(
        ["this-binary-does-not-exist-563"], b"", 5, lambda _e, _n: None, str(tmp_path),
    )
    assert timed_out is False
    assert rc == 127


def test_run_engine_timeout_kills_descendants(tmp_path):
    # child creates a grandchild (same session) that ignores SIGTERM and sleeps; on timeout the
    # whole group must die (Fix 1 escalates to SIGKILL for the group, not just the leader).
    marker = tmp_path / "gc.pid"
    code = (
        "import os,signal,time,sys\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "pid=os.fork()\n"
        "if pid==0:\n"
        "    signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "    open(%r,'w').write(str(os.getpid()))\n"
        "    time.sleep(60)\n"
        "else:\n"
        "    time.sleep(60)\n" % str(marker)
    )
    out, timed_out, rc, err = ED._run_engine(
        ["python3", "-c", code], b"", 2, lambda e, n: None, str(tmp_path),
    )
    assert timed_out is True
    import time as _t
    _t.sleep(1)
    gc = int(marker.read_text())
    dead = False
    try:
        os.kill(gc, 0)
    except OSError:
        dead = True
    assert dead, "descendant survived the group kill"


def test_reviewer_only_no_write_dispatch_reachable(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    argv = fake.calls[0]["argv"]
    assert "--sandbox" in argv
    assert argv[argv.index("--sandbox") + 1] == "read-only"
    assert "workspace-write" not in argv


def test_retry_uses_900s_floor(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([
        ("", True, 0, ""),
        (_VALID_FINDINGS_STDOUT, False, 0, ""),
    ])
    ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root,
        retry_timeout=1, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert fake.calls[1]["timeout"] == ED.RETRY_MIN_TIMEOUT


def test_antihijack_preamble_and_codex_c_flag(tmp_path):
    repo_root = _repo(tmp_path)
    build_view = _fake_build_view(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=build_view,
    )
    prompt_bytes = fake.calls[0]["prompt_bytes"]
    assert prompt_bytes.startswith(ED.ANTIHIJACK_PREAMBLE.encode("utf-8"))
    view_cwd = _expect_view_cwd(fake, build_view, os.path.realpath(repo_root))
    argv = fake.calls[0]["argv"]
    assert "-C" in argv
    assert argv[argv.index("-C") + 1] == view_cwd
    assert "--skip-git-repo-check" not in argv


def _prompt_with_shape_contract(tmp_path):
    content = (
        "Review the diff.\nRespond with JSON only:\n"
        '{"findings": [...]}\n'
        '{"findings": []}\n'
    )
    return _valid_prompt(tmp_path, content)


def test_dispatch_echo_only_stdout_forfeits_not_clean_review(tmp_path):
    """#668 regression: echoed prompt must not certify empty findings."""
    repo_root = _repo(tmp_path)
    prompt_path = _prompt_with_shape_contract(tmp_path)
    with open(prompt_path, encoding="utf-8") as fh:
        base = fh.read()
    fed = _fed_prompt(base)
    fake = FakeRunner([(fed, False, 0, ""), (fed, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=prompt_path, repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ok"] is False
    assert res["reason"] == "forfeited"
    assert res["attempts"] == 2
    assert len(fake.calls) == 2


def test_dispatch_genuine_finding_quoting_the_prompt_survives(tmp_path):
    """#668: conditional echo strip must not mangle a finding that quotes the prompt tail."""
    repo_root = _repo(tmp_path)
    marker = "PROMPT_TAIL_MARKER_668"
    shape = (
        "Review the diff.\nRespond with JSON only:\n"
        '{"findings": [...]}\n'
        '{"findings": []}\n'
    )
    pad_lines = []
    while len("".join(pad_lines) + shape) < 3000:
        pad_lines.append(f"{marker} padding line {len(pad_lines)}\n")
    content = "".join(pad_lines) + shape
    assert len(content) >= 3000
    prompt_path = _valid_prompt(tmp_path, content)
    with open(prompt_path, encoding="utf-8") as fh:
        base = fh.read()
    fed = _fed_prompt(base)
    tail = fed[-2000:]
    assert marker in tail
    finding_body = "context:\n" + tail
    stdout = json.dumps({"findings": [
        {"severity": "Important", "title": "quoted prompt in body",
         "body": finding_body, "suggestion": "s"}]})
    fake = FakeRunner([(stdout, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=prompt_path, repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ok"] is True
    assert res["attempts"] == 1
    assert len(res["findings"]) == 1
    body = res["findings"][0].get("body") or ""
    assert body
    assert marker in body


def test_dispatch_success_includes_engagement_fields(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    eng = res["engagement"]
    assert "stdoutBytes" in eng and "wallSeconds" in eng and "source" in eng
    assert eng["stdoutBytes"] == len(_VALID_FINDINGS_STDOUT)


def test_dispatch_codex_engagement_tokens_from_stderr(tmp_path):
    repo_root = _repo(tmp_path)
    stderr_tail = "log line\ntokens used\n1,234\n"
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, stderr_tail)])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ok"] is True
    assert res["engagement"]["tokens"] == 1234
    assert res["engagement"]["source"] == "codex-stderr"


def test_dispatch_cursor_engagement_tool_calls(tmp_path):
    repo_root = _repo(tmp_path)
    stream = "\n".join([
        '{"type":"tool_call","call_id":"c1","subtype":"started"}',
        '{"type":"tool_call","call_id":"c2","subtype":"started"}',
        '{"type":"tool_call","call_id":"c1","subtype":"completed"}',
        '{"type":"result","findings":[{"id":"f1","message":"ok"}]}',
    ])
    fake = FakeRunner([(stream, False, 0, "")])
    res = ED.dispatch_review(
        "cursor", model=None, effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ok"] is True
    assert res["engagement"]["toolCalls"] == 2
    assert res["engagement"]["source"] == "cursor-stream"


def test_dispatch_empty_findings_no_investigated_is_vacuous_forfeit(tmp_path):
    """#666: empty findings without a verifiable investigation record must not certify clean."""
    repo_root = _repo(tmp_path)
    empty = json.dumps({"findings": []})
    fake = FakeRunner([(empty, False, 0, ""), (empty, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ok"] is False
    assert res["reason"] == "vacuous"
    assert res["forfeited"] is True
    assert res["attempts"] == 2
    assert "engagement" in res
    assert "codex" in res["disclosure"]
    assert "vacuous" in res["disclosure"]


def test_dispatch_empty_findings_with_valid_investigated_accepted(tmp_path):
    repo_root = _repo(tmp_path)
    real_file = os.path.join(repo_root, "src", "main.py")
    os.makedirs(os.path.dirname(real_file), exist_ok=True)
    with open(real_file, "w", encoding="utf-8") as fh:
        fh.write("# main\n")
    rel = "src/main.py"
    stdout = json.dumps({"findings": [], "investigated": [rel]})
    fake = FakeRunner([(stdout, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ok"] is True
    assert res["findings"] == []
    assert res["investigated"] == [rel]
    assert res["attempts"] == 1


def test_dispatch_empty_findings_all_investigated_rejected_is_vacuous(tmp_path):
    repo_root = _repo(tmp_path)
    stdout = json.dumps({"findings": [], "investigated": ["/abs/path", "missing.py"]})
    fake = FakeRunner([(stdout, False, 0, ""), (stdout, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ok"] is False
    assert res["reason"] == "vacuous"
    assert res["attempts"] == 2
    assert res["investigatedRejected"] == ["absolute", "missing"]


def test_dispatch_whitespace_padded_repo_root_accepts_honest_investigated(tmp_path):
    repo_root = _repo(tmp_path)
    real_file = os.path.join(repo_root, "src", "main.py")
    os.makedirs(os.path.dirname(real_file), exist_ok=True)
    with open(real_file, "w", encoding="utf-8") as fh:
        fh.write("# main\n")
    rel = "src/main.py"
    padded = "  " + repo_root + "  "
    stdout = json.dumps({"findings": [], "investigated": [rel]})
    build_view = _fake_build_view(tmp_path)
    fake = FakeRunner([(stdout, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=padded, run_engine=fake,
        build_view=build_view,
    )
    assert res["ok"] is True
    assert res["investigated"] == [rel]
    _expect_view_cwd(fake, build_view, os.path.realpath(repo_root.strip()))


def test_dispatch_relative_repo_root_absolutized_for_cwd_and_codex_c(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _repo(tmp_path)
    rel_root = "repo"
    expected_real = os.path.realpath(os.path.join(str(tmp_path), "repo"))
    build_view = _fake_build_view(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=rel_root, run_engine=fake,
        build_view=build_view,
    )
    view_cwd = _expect_view_cwd(fake, build_view, expected_real)
    argv = fake.calls[0]["argv"]
    i = argv.index("-C")
    assert argv[i + 1] == view_cwd


def test_main_dispatch_review_without_repo_root_json_refusal(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ED, "_run_engine", _never_call)
    prompt = _valid_prompt(tmp_path)
    rc = ED.main([
        "dispatch-review",
        "--engine", "codex",
        "--effort", "high",
        "--prompt-path", prompt,
    ])
    assert rc == 0
    res = json.loads(capsys.readouterr().out.strip())
    assert res == _terminal_refusal("repo-root-absent")


def test_dispatch_vacuous_then_valid_investigated_succeeds_on_retry(tmp_path):
    repo_root = _repo(tmp_path)
    real_file = os.path.join(repo_root, "a.py")
    with open(real_file, "w", encoding="utf-8") as fh:
        fh.write("x")
    bad = json.dumps({"findings": []})
    good = json.dumps({"findings": [], "investigated": ["a.py"]})
    fake = FakeRunner([(bad, False, 0, ""), (good, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ok"] is True
    assert res["attempts"] == 2
    assert res["investigated"] == ["a.py"]


def test_dispatch_nonempty_findings_without_investigated_bypasses_floor(tmp_path):
    repo_root = _repo(tmp_path)
    stdout = json.dumps({"findings": [{"id": "f1", "message": "issue"}]})
    fake = FakeRunner([(stdout, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ok"] is True
    assert res["attempts"] == 1
    assert len(res["findings"]) == 1
    assert "investigated" not in res


def test_dispatch_double_timeout_stays_forfeited_not_vacuous(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([("", True, 0, ""), ("", True, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["reason"] == "forfeited"
    assert res["reason"] != "vacuous"


def test_dispatch_timeout_then_vacuous_reports_vacuous(tmp_path):
    repo_root = _repo(tmp_path)
    empty = json.dumps({"findings": []})
    fake = FakeRunner([("", True, 0, ""), (empty, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ok"] is False
    assert res["reason"] == "vacuous"
    assert res["attempts"] == 2


def test_double_forfeit_has_engagement_unrunnable_does_not(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([("not json", False, 0, ""), ("not json", False, 0, "")])
    forfeited = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert "engagement" in forfeited
    unrunnable = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=None, run_engine=fake,
        build_view=_never_build_view,
    )
    assert "engagement" not in unrunnable
    assert unrunnable["attempts"] == 0


def test_sanitized_view_build_error_refusal_no_spawn(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([])

    def fail_build(_repo):
        raise ED.sanitized_view.SanitizedViewError("sanitized-view-export-failed")

    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=fail_build,
    )
    assert res == _terminal_refusal("sanitized-view-export-failed")
    assert len(fake.calls) == 0
    assert "sanitizedView" not in res


def test_success_includes_sanitized_view_receipt(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ok"] is True
    assert res["sanitizedView"] == _fake_view_receipt()


def test_source_dirty_disclosure_when_view_flags_dirty(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path, source_dirty=True),
    )
    assert res["ok"] is True
    assert res["sanitizedView"]["sourceDirty"] is True
    assert "sourceDirtyDisclosure" in res
    assert "abc123fake" in res["sourceDirtyDisclosure"]


def test_clean_source_has_no_dirty_disclosure(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path, source_dirty=False),
    )
    assert "sourceDirtyDisclosure" not in res


def test_view_destroyed_after_dispatch(tmp_path):
    repo_root = _repo(tmp_path)
    captured_path = []

    def capture_build(repo_real):
        view = _fake_build_view(tmp_path)(repo_real)
        captured_path.append(view["path"])
        return view

    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=capture_build,
    )
    assert captured_path
    assert not os.path.exists(captured_path[0])


@pytest.mark.parametrize(
    "case,run_engine,kwargs",
    [
        (
            "success",
            FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")]),
            {},
        ),
        (
            "double_timeout",
            FakeRunner([("", True, 0, ""), ("", True, 0, "")]),
            {},
        ),
        (
            "vacuous",
            FakeRunner([(json.dumps({"findings": []}), False, 0, ""),
                        (json.dumps({"findings": []}), False, 0, "")]),
            {},
        ),
        (
            "run_engine_raises",
            None,
            {"run_engine_factory": "boom"},
        ),
        (
            "engine_config_refusal",
            _never_call,
            {"engine": "cursor", "model": "fable", "effort": "composer"},
        ),
    ],
)
def test_view_destroyed_across_dispatch_outcomes(tmp_path, case, run_engine, kwargs):
    repo_root = _repo(tmp_path)
    captured_path = []
    build_view_fn = _fake_build_view(tmp_path)

    def capture_build(repo_real):
        view = build_view_fn(repo_real)
        captured_path.append(view["path"])
        return view

    dispatch_kwargs = {
        "model": kwargs.get("model", "sonnet"),
        "effort": kwargs.get("effort", "high"),
        "prompt_path": _valid_prompt(tmp_path),
        "repo_root": repo_root,
        "build_view": capture_build,
    }
    engine = kwargs.get("engine", "codex")
    if kwargs.get("run_engine_factory") == "boom":
        def boom(*_a, **_k):
            raise RuntimeError("injected failure")
        dispatch_kwargs["run_engine"] = boom
    else:
        dispatch_kwargs["run_engine"] = run_engine

    ED.dispatch_review(engine, **dispatch_kwargs)
    assert captured_path
    assert not os.path.exists(captured_path[0])


def test_dispatch_investigated_stripped_path_is_vacuous_forfeit(tmp_path):
    repo_root = _repo(tmp_path)
    (tmp_path / "repo" / "CLAUDE.md").write_text("# agent\n", encoding="utf-8")
    build_view = _fake_build_view(tmp_path, stripped=["CLAUDE.md"])
    stdout = json.dumps({"findings": [], "investigated": ["CLAUDE.md"]})
    fake = FakeRunner([(stdout, False, 0, ""), (stdout, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=build_view,
    )
    assert res["ok"] is False
    assert res["reason"] == "vacuous"
    assert res["forfeited"] is True
    assert res["attempts"] == 2
    assert res["investigatedRejected"]


@pytest.mark.parametrize("repo_root,detail", [
    (None, "repo-root-absent"),
    ("   ", "repo-root-absent"),
    ("missing", "repo-root-missing"),
])
def test_pre_view_repo_root_refusals_have_no_sanitized_view(tmp_path, repo_root, detail):
    if repo_root == "missing":
        repo_root = str(tmp_path / "no-such-repo")
    fake = FakeRunner([])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_never_build_view,
    )
    assert res["attempts"] == 0
    assert res["detail"] == detail or detail in res["detail"]
    assert "sanitizedView" not in res
    assert len(fake.calls) == 0


def test_pre_view_repo_root_not_a_directory_no_sanitized_view(tmp_path):
    f = tmp_path / "file-not-dir"
    f.write_text("x", encoding="utf-8")
    fake = FakeRunner([])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=str(f), run_engine=fake,
        build_view=_never_build_view,
    )
    assert res["detail"] == "repo-root-not-a-directory"
    assert res["attempts"] == 0
    assert "sanitizedView" not in res


def test_pre_view_repo_root_not_a_repo_no_sanitized_view(tmp_path):
    bare = tmp_path / "bare-dir"
    bare.mkdir()
    fake = FakeRunner([])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=str(bare), run_engine=fake,
        build_view=_never_build_view,
    )
    assert res["detail"] == "repo-root-not-a-repo"
    assert res["attempts"] == 0
    assert "sanitizedView" not in res


# --- #702 supervision primitive edges ---


def test_forged_state_json_paths_not_used_for_kill_or_delete(tmp_path):
    """Edge 1: poisoned state.json cannot steer abandon kill/delete."""
    run_dir = tmp_path / "run"
    run_dir.mkdir(mode=0o700)
    victim = tmp_path / "victim.txt"
    victim.write_text("keep", encoding="utf-8")
    state = {
        "engine": "codex",
        "roleKind": "review",
        "effort": "high",
        "argv": ["codex"],
        "viewPath": str(victim),
        "supervisorPid": os.getpid(),
        "pid": os.getpid(),
    }
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    res = ED.dispatch_abandon(str(run_dir))
    assert victim.read_text(encoding="utf-8") == "keep"
    assert res.get("terminal") is True


def test_run_child_argv_rederivation_mismatch(tmp_path):
    """Edge 2: run-child refuses argv drift."""
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
        "runNonce": "n1",
        "orderId": "",
    }
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    rc = _invoke_run_child(run_dir, 1, state)
    assert rc != 0
    done = json.loads((run_dir / "attempt-1.done").read_text(encoding="utf-8"))
    assert done.get("refusal") == "argv-rederivation-mismatch"


def test_run_child_engine_binary_mismatch(tmp_path):
    """Edge 3: re-resolved binary must match parent record."""
    run_dir = tmp_path / "run"
    run_dir.mkdir(mode=0o700)
    (run_dir / "prompt.txt").write_bytes(b"x")
    cwd = run_dir / "review-cwd"
    cwd.mkdir()
    built = _engine_adapter.build_argv_result(
        "codex", "review", "high",
        {"model": "sonnet", "cwd": str(cwd)},
    )
    argv = built["argv"]
    resolved = shutil.which(argv[0])
    (run_dir / "state.json").write_text(json.dumps({
        "engine": "codex",
        "roleKind": "review",
        "effort": "high",
        "model": "sonnet",
        "argv": argv,
        "engineBinary": "/definitely/not/the/engine",
        "attemptTimeout": 5,
        "runNonce": "n2",
        "orderId": "",
    }), encoding="utf-8")
    _invoke_run_child(run_dir, 1, json.loads((run_dir / "state.json").read_text(encoding="utf-8")))
    done = json.loads((run_dir / "attempt-1.done").read_text(encoding="utf-8"))
    assert done.get("refusal") == "engine-binary-mismatch"
    assert resolved  # sanity


def test_stale_done_sentinel_removed_before_launch(tmp_path):
    """Edge 4: stale attempt-1.done is not accepted for a fresh attempt."""
    run_dir = tmp_path / "run"
    run_dir.mkdir(mode=0o700)
    stale = {"exit": 0, "timedOut": False, "signal": None,
             "endedAt": 0.0, "refusal": None}
    (run_dir / "attempt-1.done").write_text(json.dumps(stale), encoding="utf-8")
    (run_dir / "attempt-1.stdout").write_text(_VALID_FINDINGS_STDOUT, encoding="utf-8")
    repo_root = _repo(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path), run_dir=str(run_dir),
    )
    assert res["ok"] is True
    assert len(fake.calls) == 1


def test_stale_done_sentinel_ignored_on_resume_with_inflight(tmp_path):
    """Resume with in-flight attempt must not accept a prior run's successful sentinel."""
    run_dir = tmp_path / "run"
    run_dir.mkdir(mode=0o700)
    current_nonce = "current-run-nonce-702"
    stale_stdout = _VALID_FINDINGS_STDOUT
    (run_dir / "attempt-1.done").write_text(json.dumps({
        "exit": 0, "timedOut": False, "runNonce": "stale-previous-nonce",
    }), encoding="utf-8")
    (run_dir / "attempt-1.stdout").write_text(stale_stdout, encoding="utf-8")
    state = {
        "engine": "codex",
        "roleKind": "review",
        "effort": "high",
        "model": "sonnet",
        "argv": ["codex"],
        "engineBinary": "/bin/true",
        "runNonce": current_nonce,
        "repoRoot": str(tmp_path / "repo"),
        "promptPath": str(run_dir / "prompt.txt"),
        "viewReceipt": _fake_view_receipt(),
        "fedPrompt": "",
        "inFlightAttempt": 1,
        "completedAttempts": 0,
        "attemptStartedAt": time.time(),
        "timeout": 5,
        "retryTimeout": 5,
    }
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    _bind_inflight(run_dir, state)
    res = ED.dispatch_poll(str(run_dir), max_wait=0)
    assert res.get("terminal") is False
    assert not (run_dir / "result.json").exists()
    (run_dir / "attempt-1.done").write_text(json.dumps({
        "exit": 0, "timedOut": False, "runNonce": current_nonce,
        "authorityHash": state["authorityHash"],
    }), encoding="utf-8")
    # Ledger completion is the authority fact; the run-dir .done alone is not.
    ED._ledger_seal_attempt_complete(
        os.path.realpath(str(run_dir)), 1, state["authorityHash"], current_nonce)
    res2 = ED.dispatch_poll(str(run_dir), max_wait=1)
    assert res2.get("terminal") is True
    assert (run_dir / "result.json").is_file()


def test_stdout_without_sentinel_is_incomplete_not_result(tmp_path):
    """Edge 5: output without done sentinel is not a terminal fold."""
    run_dir = tmp_path / "run"
    run_dir.mkdir(mode=0o700)
    (run_dir / "attempt-1.stdout").write_text(_VALID_FINDINGS_STDOUT, encoding="utf-8")
    state = {
        "engine": "codex",
        "roleKind": "review",
        "effort": "high",
        "argv": [],
        "engineBinary": "/bin/true",
        "runNonce": "stdout-only-n",
        "inFlightAttempt": 1,
        "attemptStartedAt": time.time(),
        "viewReceipt": _fake_view_receipt(),
        "fedPrompt": "",
        "completedAttempts": 0,
        "timeout": 5,
        "retryTimeout": 5,
    }
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    _bind_inflight(run_dir, state)
    res = ED.dispatch_poll(str(run_dir), max_wait=0)
    assert res.get("running") is True
    assert res.get("terminal") is False
    assert not (run_dir / "result.json").exists()


def test_deadline_exceeded_before_spawn_during_view_build(tmp_path, monkeypatch):
    """Edge 6: view build consumes deadline → named refusal, no spawn."""
    repo_root = _repo(tmp_path)
    t = {"n": 0}

    def slow_build(_repo):
        t["n"] += 1
        time.sleep(0.05)
        return _fake_build_view(tmp_path)(_repo)

    fake = FakeRunner([])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=slow_build, max_wait=0,
    )
    assert res["detail"] == "deadline-exceeded-before-spawn"
    assert res["attempts"] == 0
    assert len(fake.calls) == 0


def test_running_result_not_forfeit_or_success(tmp_path):
    """Edge 7: non-terminal running is distinct from forfeit/success."""
    run_dir = tmp_path / "run"
    run_dir.mkdir(mode=0o700)
    state = {
        "engine": "codex", "roleKind": "review", "effort": "high",
        "argv": [], "engineBinary": "/bin/true", "runNonce": "run-n",
        "inFlightAttempt": 1, "attemptStartedAt": time.time(),
        "viewReceipt": {}, "timeout": 5, "retryTimeout": 5,
    }
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    _persist_test_authority(run_dir, state)
    res = ED.dispatch_poll(str(run_dir), max_wait=0)
    assert res["ok"] is False
    assert res["terminal"] is False
    assert res["forfeited"] is False
    assert res.get("running") is True
    assert res.get("reason") == "running"


def test_dispatch_poll_never_spawns(tmp_path):
    """Edge 8: poll never creates attempt artifacts (no spawn)."""
    run_dir = tmp_path / "run"
    run_dir.mkdir(mode=0o700)
    state = {
        "engine": "codex", "roleKind": "review", "effort": "high",
        "argv": [], "engineBinary": "/bin/true", "runNonce": "poll-n",
        "completedAttempts": 0, "viewReceipt": _fake_view_receipt(),
        "fedPrompt": "", "timeout": 5, "retryTimeout": 5,
    }
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    _persist_test_authority(run_dir, state)
    ED.dispatch_poll(str(run_dir), max_wait=0)
    assert not (run_dir / "attempt-1.stdout").exists()
    assert not (run_dir / "attempt-1.done").exists()


def test_concurrent_run_dir_lock_prevents_duplicate_spawn(tmp_path, monkeypatch):
    """Two dispatch calls on one run-dir: one child, loser gets resumable non-terminal."""
    repo_root = _repo(tmp_path)
    run_dir = tmp_path / "run"
    run_dir.mkdir(mode=0o700)
    hold_spawn = threading.Event()
    release_spawn = threading.Event()
    real_spawn = ED._spawn_run_child

    def _gated_spawn(rd, att, launch, authority_hash=None):
        if att == 1:
            hold_spawn.set()
            assert release_spawn.wait(timeout=20)
        return real_spawn(rd, att, launch, authority_hash=authority_hash)

    monkeypatch.setattr(ED, "_spawn_run_child", _gated_spawn)
    results = {}

    def _start():
        results["a"] = ED.dispatch_review(
            "codex", model="sonnet", effort="high",
            prompt_path=_valid_prompt(tmp_path), repo_root=repo_root,
            run_engine=ED._run_engine, build_view=_fake_build_view(tmp_path),
            run_dir=str(run_dir), max_wait=120,
        )

    t = threading.Thread(target=_start, daemon=True)
    t.start()
    assert hold_spawn.wait(timeout=30)
    results["b"] = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root,
        run_engine=ED._run_engine, build_view=_fake_build_view(tmp_path),
        run_dir=str(run_dir), max_wait=5,
    )
    assert results["b"].get("detail") == "lock-held"
    assert results["b"].get("terminal") is False
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state.get("inFlightAttempt") == 1
    release_spawn.set()
    t.join(timeout=60)


def _minimal_review_authority(run_dir, cleanup_roots):
    """Minimal LaunchAuthority for run-dir cleanup unit tests."""
    return ED.LaunchAuthority(
        role_kind="review",
        run_kind=ED.RUN_KIND_REVIEW,
        engine="codex",
        effort="high",
        model=None,
        engine_model=None,
        schema_path=None,
        argv=(),
        spawned_argv=(),
        engine_binary="",
        cwd=str(run_dir),
        order_id="",
        run_nonce="test-nonce",
        run_dir=str(run_dir),
        timeout=5,
        retry_timeout=5,
        lease_token=None,
        lease_holder=None,
        cleanup_roots=tuple(cleanup_roots),
        fed_prompt="",
        view_receipt={},
        repo_root=None,
        prompt_path=None,
        progress_path=None,
        base_sha=None,
    )


def test_result_json_persisted_before_view_destroyed(tmp_path, monkeypatch):
    """result.json must exist and parse before review-cwd destruction runs."""
    repo_root = _repo(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    destroy_moments = []
    real_destroy = ED._destroy_run_dir_path

    def _spy_run_dir_destroy(path, authority):
        result_path = os.path.join(authority.run_dir, ED.RESULT_NAME)
        assert os.path.isfile(result_path), "result.json missing at destroy"
        parsed = json.loads(open(result_path, encoding="utf-8").read())
        assert parsed.get("ok") is True
        destroy_moments.append(result_path)
        return real_destroy(path, authority)

    monkeypatch.setattr(ED, "_destroy_run_dir_path", _spy_run_dir_destroy)
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ok"] is True, res
    assert destroy_moments
    run_dir = res["runDir"]
    assert not os.path.exists(os.path.join(run_dir, REVIEW_CWD_BASENAME))


def test_run_dir_cleanup_survives_temp_base_change(tmp_path, monkeypatch):
    """Edge 1 isolation: cleanup succeeds after process temp base changes."""
    run_dir = tmp_path / "run-under-original-temp"
    run_dir.mkdir()
    review_cwd = run_dir / REVIEW_CWD_BASENAME
    review_cwd.mkdir()
    (review_cwd / "keep-me.txt").write_text("x", encoding="utf-8")
    (run_dir / ED.RESULT_NAME).write_text(
        json.dumps({"ok": True}), encoding="utf-8")
    authority = _minimal_review_authority(run_dir, (str(review_cwd),))
    other_base = tmp_path / "other-temp-base"
    other_base.mkdir()
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(other_base))
    monkeypatch.setattr(_SV_MOD.tempfile, "gettempdir", lambda: str(other_base))
    ED._destroy_review_views(str(run_dir), authority)
    assert not os.path.exists(str(review_cwd))


def test_run_dir_cleanup_refuses_outside_cleanup_roots(tmp_path):
    """Edge 3: run-dir cleanup refuses a target outside authority.cleanup_roots."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    review_cwd = run_dir / REVIEW_CWD_BASENAME
    review_cwd.mkdir()
    outside = tmp_path / "outside-victim"
    outside.mkdir()
    marker = outside / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    authority = _minimal_review_authority(run_dir, (str(review_cwd),))
    assert ED._cleanup_path_permitted(str(outside), authority) is False
    assert ED._destroy_run_dir_path(str(outside), authority) is False
    assert outside.is_dir()
    assert marker.read_text(encoding="utf-8") == "keep"


def test_run_dir_cleanup_refuses_symlink(tmp_path):
    """Edge 4: run-dir cleanup refuses a symlink even if it resolves into a root."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    real_target = tmp_path / "real-target"
    real_target.mkdir()
    marker = real_target / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    link = run_dir / REVIEW_CWD_BASENAME
    try:
        os.symlink(str(real_target), str(link))
    except OSError as exc:
        pytest.skip("symlink not supported: %s" % exc)
    authority = _minimal_review_authority(run_dir, (str(link),))
    assert ED._cleanup_path_permitted(str(link), authority) is False
    assert ED._destroy_run_dir_path(str(link), authority) is False
    assert os.path.lexists(str(link))
    assert real_target.is_dir()
    assert marker.read_text(encoding="utf-8") == "keep"


def test_destroy_sanitized_view_never_called_with_run_dir_path(tmp_path, monkeypatch):
    """Edges 5–6: destroy_sanitized_view only sees prefix/temp views; source is gone."""
    repo_root = _repo(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    build_view = _fake_build_view(tmp_path)
    called_paths = []
    real_destroy = ED.sanitized_view.destroy_sanitized_view

    def _spy_destroy(path):
        called_paths.append(path)
        return real_destroy(path)

    monkeypatch.setattr(ED.sanitized_view, "destroy_sanitized_view", _spy_destroy)
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=build_view,
    )
    assert res["ok"] is True, res
    assert called_paths, "expected destroy_sanitized_view on the source view"
    tmp_base = os.path.realpath(_SV_MOD.tempfile.gettempdir())
    prefix = _SV_MOD.SANITIZED_VIEW_DIR_PREFIX
    run_dir_real = os.path.realpath(res["runDir"])
    for path in called_paths:
        real = os.path.realpath(path)
        assert os.path.basename(real).startswith(prefix), path
        assert os.path.commonpath([real, tmp_base]) == tmp_base, path
        assert os.path.basename(real) != REVIEW_CWD_BASENAME
        assert not real.startswith(run_dir_real + os.sep), path
    source = build_view.meta["view_path"]
    assert source, "fake build_view must record its path"
    assert not os.path.exists(source)
    assert not os.path.exists(os.path.join(res["runDir"], REVIEW_CWD_BASENAME))


def test_dispatch_review_private_run_dir_argv_cwd_canonical(tmp_path, monkeypatch):
    """Recorded codex -C must match run-child re-derivation (realpath) for auto run dirs."""
    repo_root = _repo(tmp_path)
    outer = tempfile.mkdtemp(prefix="superheroes-dispatch-")
    if os.path.realpath(outer) == outer:
        pytest.skip("need macOS /var TMPDIR alias layout")
    monkeypatch.setattr(ED, "_private_run_dir", lambda: outer)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path), max_wait=60,
    )
    state = json.loads(open(os.path.join(outer, "state.json"), encoding="utf-8").read())
    argv = state["argv"]
    cwd_arg = argv[argv.index("-C") + 1]
    review_cwd = os.path.join(outer, REVIEW_CWD_BASENAME)
    assert cwd_arg == os.path.realpath(review_cwd)


# --- WO-702-Q: B-2 authority-carrying sink invariant (AST) ---


def _b2_engine_dispatch_path():
    return os.path.join(_HERE, "..", "engine_dispatch.py")


_B2_FORBIDDEN_DICT_NAMES = frozenset({
    "state", "sentinel", "result", "receipt", "cached", "body",
    "view_receipt", "last_engagement", "engagement", "data",
    "payload", "holder", "snap", "snap_before", "cur",
})


def _b2_call_name(node):
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _b2_expr_mentions_forbidden_dict(node):
    """True when expr reads via subscript/.get on a forbidden dict name."""
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        if node.value.id in _B2_FORBIDDEN_DICT_NAMES:
            return True
    if isinstance(node, ast.Call):
        func = node.func
        if (isinstance(func, ast.Attribute) and func.attr == "get"
                and isinstance(func.value, ast.Name)
                and func.value.id in _B2_FORBIDDEN_DICT_NAMES):
            return True
    for child in ast.iter_child_nodes(node):
        if _b2_expr_mentions_forbidden_dict(child):
            return True
    return False


def _b2_is_module_constant_name(name):
    """True for ALL_CAPS module constants (e.g. RETRY_MIN_TIMEOUT)."""
    if not name or not name[0].isupper():
        return False
    return all(c.isupper() or c.isdigit() or c == "_" for c in name)


def _b2_classify_authority_expr(node, authority_names, derived_names, tainted_names=None):
    """Return 'authority', 'forbidden', or 'unclassified' for an expression."""
    tainted_names = tainted_names or frozenset()
    if _b2_expr_mentions_forbidden_dict(node):
        return "forbidden"
    if isinstance(node, ast.Name):
        if node.id in tainted_names:
            return "forbidden"
        if node.id in authority_names or node.id in derived_names:
            return "authority"
        if node.id in _B2_FORBIDDEN_DICT_NAMES:
            return "forbidden"
        if _b2_is_module_constant_name(node.id):
            return "authority"
        return "unclassified"
    if isinstance(node, ast.Attribute):
        if isinstance(node.value, ast.Name) and node.value.id in tainted_names:
            return "forbidden"
        if isinstance(node.value, ast.Name) and node.value.id in authority_names:
            return "authority"
        return _b2_classify_authority_expr(
            node.value, authority_names, derived_names, tainted_names)
    if isinstance(node, ast.Call):
        # Sealed-ledger / sealed-launch helpers are authority sources (never state.json).
        cname = _b2_call_name(node)
        if cname in (
                "_ledger_expected_hash",
                "_find_pending_launch",
                "_completed_attempts_from_seals",
                "_ledger_attempt_claim"):
            return "authority"
        # list(authority.argv), tuple(...), _resolve_argv_binary(recorded), etc.
        if not node.args:
            return "unclassified"
        kinds = [
            _b2_classify_authority_expr(
                a, authority_names, derived_names, tainted_names) for a in node.args
        ]
        if "forbidden" in kinds:
            return "forbidden"
        if all(k == "authority" for k in kinds):
            return "authority"
        return "unclassified"
    if isinstance(node, (ast.List, ast.Tuple)):
        if not node.elts:
            return "authority"
        kinds = [
            _b2_classify_authority_expr(
                e, authority_names, derived_names, tainted_names) for e in node.elts
        ]
        if "forbidden" in kinds:
            return "forbidden"
        if all(k == "authority" for k in kinds):
            return "authority"
        return "unclassified"
    if isinstance(node, ast.BinOp):
        left = _b2_classify_authority_expr(
            node.left, authority_names, derived_names, tainted_names)
        right = _b2_classify_authority_expr(
            node.right, authority_names, derived_names, tainted_names)
        if "forbidden" in (left, right):
            return "forbidden"
        if left == "authority" or right == "authority":
            # Conservatively require both sides authority for arithmetic/concat.
            if left == "authority" and right == "authority":
                return "authority"
        return "unclassified"
    if isinstance(node, ast.IfExp):
        for part in (node.body, node.orelse, node.test):
            k = _b2_classify_authority_expr(
                part, authority_names, derived_names, tainted_names)
            if k == "forbidden":
                return "forbidden"
        # Ternary is unclassified unless both branches are authority.
        b = _b2_classify_authority_expr(
            node.body, authority_names, derived_names, tainted_names)
        e = _b2_classify_authority_expr(
            node.orelse, authority_names, derived_names, tainted_names)
        if b == "authority" and e == "authority":
            return "authority"
        return "unclassified"
    if isinstance(node, ast.UnaryOp):
        return _b2_classify_authority_expr(
            node.operand, authority_names, derived_names, tainted_names)
    if isinstance(node, ast.Constant):
        return "authority"
    if isinstance(node, ast.BoolOp):
        kinds = [
            _b2_classify_authority_expr(
                v, authority_names, derived_names, tainted_names) for v in node.values
        ]
        if "forbidden" in kinds:
            return "forbidden"
        # `authority.x or authority.y` OK; `x or authority.y` unclassified.
        if all(k == "authority" for k in kinds):
            return "authority"
        return "unclassified"
    return "unclassified"


def _b2_bind_name(name, value_node, authority_names, derived, tainted):
    """Update derived/tainted for an ordered name binding (reassignment-aware).

    A forbidden (receipt/state) binding taints the name whether or not it was
    previously authority-derived — a fresh ``authority_hash = state.get(...)``
    must not reach a sink. Unclassified rebinds drop derived provenance without
    tainting so builder assignments like ``authority = _build_*_authority(...)``
    stay usable at sinks via the ``authority`` parameter name.
    """
    kind = _b2_classify_authority_expr(value_node, authority_names, derived, tainted)
    if kind == "authority":
        derived.add(name)
        tainted.discard(name)
        return
    if kind == "forbidden":
        tainted.add(name)
        derived.discard(name)
        return
    # unclassified — drop derived bit; do not taint
    derived.discard(name)


def _b2_collect_derived(func_node, authority_names):
    """Names assigned from authority-derived expressions inside func_node.

    Walks statements in source order so a later reassignment from a receipt/state
    dict taints a name that was earlier bound from authority.
    """
    derived = set()
    tainted = set()

    def visit_stmt(stmt):
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            target = stmt.targets[0]
            if isinstance(target, ast.Name):
                _b2_bind_name(
                    target.id, stmt.value, authority_names, derived, tainted)
            elif isinstance(target, ast.Tuple):
                if isinstance(stmt.value, ast.Call) and len(target.elts) >= 1:
                    kind = _b2_classify_authority_expr(
                        stmt.value, authority_names, derived, tainted)
                    for elt in target.elts:
                        if not isinstance(elt, ast.Name):
                            continue
                        if kind == "authority":
                            derived.add(elt.id)
                            tainted.discard(elt.id)
                        else:
                            _b2_bind_name(
                                elt.id, stmt.value, authority_names, derived, tainted)
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            if stmt.value is not None:
                _b2_bind_name(
                    stmt.target.id, stmt.value, authority_names, derived, tainted)
        elif isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name):
            _b2_bind_name(
                stmt.target.id, stmt.value, authority_names, derived, tainted)
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            if (isinstance(call.func, ast.Attribute)
                    and call.func.attr == "append"
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id in derived
                    and call.args):
                kind = _b2_classify_authority_expr(
                    call.args[0], authority_names, derived, tainted)
                if kind != "authority":
                    tainted.add(call.func.value.id)
                    derived.discard(call.func.value.id)
        elif isinstance(stmt, ast.For):
            if isinstance(stmt.target, ast.Name):
                _b2_bind_name(
                    stmt.target.id, stmt.iter, authority_names, derived, tainted)
            for child in stmt.body:
                visit_stmt(child)
            for child in stmt.orelse:
                visit_stmt(child)
        elif isinstance(stmt, ast.If):
            for child in stmt.body:
                visit_stmt(child)
            for child in stmt.orelse:
                visit_stmt(child)
        elif isinstance(stmt, ast.While):
            for child in stmt.body:
                visit_stmt(child)
            for child in stmt.orelse:
                visit_stmt(child)
        elif isinstance(stmt, ast.With):
            for child in stmt.body:
                visit_stmt(child)
        elif isinstance(stmt, ast.Try):
            for child in stmt.body:
                visit_stmt(child)
            for handler in stmt.handlers:
                for child in handler.body:
                    visit_stmt(child)
            for child in stmt.orelse:
                visit_stmt(child)
            for child in stmt.finalbody:
                visit_stmt(child)

    for stmt in func_node.body:
        visit_stmt(stmt)
    return derived, tainted


def _b2_sink_args(call):
    """Yield (label, expr) for authority-carrying arguments at a sink call."""
    name = _b2_call_name(call)
    if name == "_spawn_run_child":
        # (run_dir, attempt, authority, authority_hash=...)
        if len(call.args) >= 2:
            yield "attempt", call.args[1]
        if len(call.args) >= 3:
            yield "authority", call.args[2]
        for kw in call.keywords:
            if kw.arg in ("attempt", "authority"):
                yield kw.arg, kw.value
    elif name == "_run_engine_files":
        # argv, timeout, attempt, cwd (positional 0, 4, 6, 7);
        # authority / authority_hash kw; authority_hash also positional 11.
        if len(call.args) >= 1:
            yield "argv", call.args[0]
        if len(call.args) >= 5:
            yield "timeout", call.args[4]
        if len(call.args) >= 7:
            yield "attempt", call.args[6]
        if len(call.args) >= 8:
            yield "cwd", call.args[7]
        if len(call.args) >= 12:
            yield "authority_hash", call.args[11]
        for kw in call.keywords:
            if kw.arg in (
                    "argv", "cwd", "authority", "timeout", "authority_hash",
                    "attempt"):
                yield kw.arg, kw.value
    elif name == "_seal_attempt_launch":
        # (run_dir, attempt, authority, authority_hash, timeout)
        if len(call.args) >= 2:
            yield "attempt", call.args[1]
        if len(call.args) >= 3:
            yield "authority", call.args[2]
        if len(call.args) >= 4:
            yield "authority_hash", call.args[3]
        if len(call.args) >= 5:
            yield "timeout", call.args[4]
        for kw in call.keywords:
            if kw.arg in ("attempt", "authority", "authority_hash", "timeout"):
                yield kw.arg, kw.value
    elif name == "_execute_injected_attempt":
        # attempt at 2; authority at 3; timeout at 6; cwd at 7; authority_hash at 8
        if len(call.args) >= 3:
            yield "attempt", call.args[2]
        if len(call.args) >= 4:
            yield "authority", call.args[3]
        if len(call.args) >= 7:
            yield "timeout", call.args[6]
        if len(call.args) >= 8:
            yield "cwd", call.args[7]
        if len(call.args) >= 9:
            yield "authority_hash", call.args[8]
        for kw in call.keywords:
            if kw.arg in (
                    "attempt", "authority", "timeout", "cwd", "argv",
                    "authority_hash"):
                yield kw.arg, kw.value
    elif name in (
            "_ledger_seal_attempt_intent",
            "_ledger_claim_attempt",
            "_ledger_seal_attempt_complete"):
        # (run_dir_real, attempt, authority_hash, run_nonce, ...)
        if len(call.args) >= 2:
            yield "attempt", call.args[1]
        if len(call.args) >= 3:
            yield "authority_hash", call.args[2]
        if len(call.args) >= 4:
            yield "run_nonce", call.args[3]
        for kw in call.keywords:
            if kw.arg in ("attempt", "authority_hash", "run_nonce"):
                yield kw.arg, kw.value
    elif name == "_release_worktree_lease":
        if call.args:
            yield "authority", call.args[0]
        for kw in call.keywords:
            if kw.arg == "authority":
                yield "authority", kw.value
    elif name == "_release_worktree_lease_for_cwd":
        labels = ("cwd", "lease_token", "lease_holder")
        for i, arg in enumerate(call.args):
            if i < len(labels):
                yield labels[i], arg
        for kw in call.keywords:
            if kw.arg in labels:
                yield kw.arg, kw.value
    elif name == "_destroy_review_views":
        if len(call.args) >= 2:
            yield "authority", call.args[1]
        for kw in call.keywords:
            if kw.arg == "authority":
                yield "authority", kw.value
    elif name == "_destroy_run_dir_path":
        if call.args:
            yield "path", call.args[0]
        if len(call.args) >= 2:
            yield "authority", call.args[1]
        for kw in call.keywords:
            if kw.arg in ("path", "authority"):
                yield kw.arg, kw.value
    elif name == "rmtree":
        if call.args:
            yield "rmtree_target", call.args[0]
        for kw in call.keywords:
            if kw.arg in (None, "path") or kw.arg == "path":
                yield "rmtree_target", kw.value


def _b2_enclosing_function(tree, node):
    """Find the FunctionDef that contains node (by lineage walk)."""
    parent_map = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parent_map[child] = parent
    cur = node
    while cur in parent_map:
        cur = parent_map[cur]
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cur
    return None


def _b2_parent_map(tree):
    parent_map = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parent_map[child] = parent
    return parent_map


def _b2_guarding_if(parent_map, node):
    """Nearest enclosing ``If`` whose body (not orelse) contains node."""
    cur = node
    while cur in parent_map:
        parent = parent_map[cur]
        if isinstance(parent, ast.If):
            # Only treat as a spawn-decision guard when node is under body.
            for stmt in parent.body:
                if cur is stmt or cur in ast.walk(stmt):
                    return parent
            return None
        cur = parent
    return None


def _b2_spawn_control_tests(func_node, call, parent_map):
    """Yield (test_expr, lineno) for enclosing ``if`` tests that gate reaching call.

    Only enclosing ``if`` tests at any nesting depth (body branch only). Early-return
    gates earlier in the function are intentionally not treated as spawn control
    dependencies: in this module they can only stop a run (the downgrade-only
    direction), the enabling shape is covered at the sinks (``attempt`` inspected),
    and fall-through bypass coverage lives in ``test_engine_dispatch_write.py``.
    """
    seen = set()
    # Enclosing ifs at any depth (body only — orelse is not a spawn-enable guard).
    cur = call
    while cur in parent_map:
        parent = parent_map[cur]
        if isinstance(parent, ast.If):
            under_body = False
            for stmt in parent.body:
                if cur is stmt or cur in ast.walk(stmt):
                    under_body = True
                    break
            if under_body:
                key = id(parent.test)
                if key not in seen:
                    seen.add(key)
                    yield parent.test, parent.lineno
            else:
                # Under orelse — stop treating outer ifs via this walk step.
                pass
        cur = parent


_B2_SINK_NAMES = frozenset({
    "_spawn_run_child", "_run_engine_files", "_seal_attempt_launch",
    "_execute_injected_attempt",
    "_ledger_seal_attempt_intent", "_ledger_claim_attempt",
    "_ledger_seal_attempt_complete",
    "_release_worktree_lease", "_release_worktree_lease_for_cwd",
    "_destroy_review_views", "_destroy_run_dir_path",
})

_B2_AUTHORITY_PARAM_NAMES = frozenset({
    "authority", "launch", "authority_hash", "run_nonce", "attempt",
})


def _b2_authority_names_for_call(parent_map, call, enc):
    """Authority-carrying parameter names visible at call (incl. outer scopes)."""
    authority_names = {"authority"}
    # Walk every enclosing function so nested helpers closing over
    # authority_hash / run_nonce still see them as authority params.
    cur = call
    funcs = []
    while cur in parent_map:
        cur = parent_map[cur]
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append(cur)
    if enc is not None and enc not in funcs:
        funcs.append(enc)
    for func in funcs:
        for arg in list(func.args.args) + list(func.args.kwonlyargs):
            if arg.arg in _B2_AUTHORITY_PARAM_NAMES:
                authority_names.add(arg.arg)
    return authority_names


def _b2_find_violations(source):
    """Return list of (lineno, message) for B-2 authority-carrying sink violations."""
    tree = ast.parse(source)
    violations = []
    parent_map = _b2_parent_map(tree)
    # rmtree sites inside _destroy_run_dir_path / _destroy_review_views /
    # _cleanup_path_permitted are authority-gated; pre-authority create-path
    # rmtrees of sanitized views are not authority-carrying (view path from
    # build_view, not engine). Scope rmtree checks to those helpers only.
    for call in [n for n in ast.walk(tree) if isinstance(n, ast.Call)]:
        name = _b2_call_name(call)
        if name == "rmtree":
            enc = _b2_enclosing_function(tree, call)
            if enc is None or enc.name not in (
                    "_destroy_review_views", "_destroy_run_dir_path",
                    "_cleanup_path_permitted"):
                continue
        elif name not in _B2_SINK_NAMES:
            continue
        enc = _b2_enclosing_function(tree, call)
        authority_names = _b2_authority_names_for_call(parent_map, call, enc)
        derived = set()
        tainted = set()
        if enc is not None:
            derived, tainted = _b2_collect_derived(enc, authority_names)
            # engine_cwd validated from authority.cwd is authority-derived when
            # assigned in the write/review branches — collected via loop above
            # when the RHS classifies. Also treat common locals set from authority.
        # Spawn-decision (Miss 3): only enclosing ``if`` tests at any depth.
        # Early-return / fall-through gates earlier in the function are not
        # flagged — in this module they can only stop a run (downgrade-only);
        # reintroduction of receipt-selected attempt is caught at sinks via the
        # inspected ``attempt`` argument; fall-through bypass coverage lives in
        # test_engine_dispatch_write.py. No production line-number allowlist.
        if name == "_spawn_run_child" and enc is not None:
            for test, lineno in _b2_spawn_control_tests(enc, call, parent_map):
                kind = _b2_classify_authority_expr(
                    test, authority_names, derived, tainted)
                if kind == "forbidden":
                    snippet = (
                        ast.unparse(test) if hasattr(ast, "unparse")
                        else ast.dump(test))
                    violations.append((
                        lineno,
                        "B-2 violation: spawn-decision fed from forbidden dict at "
                        "%s:%d: %s"
                        % ("engine_dispatch.py", lineno, snippet),
                    ))
        for label, expr in _b2_sink_args(call):
            kind = _b2_classify_authority_expr(
                expr, authority_names, derived, tainted)
            snippet = ast.unparse(expr) if hasattr(ast, "unparse") else ast.dump(expr)
            if kind == "forbidden":
                violations.append((
                    call.lineno,
                    "B-2 violation: %s %s fed from forbidden dict at %s:%d: %s"
                    % (name, label, "engine_dispatch.py", call.lineno, snippet),
                ))
            elif kind == "unclassified":
                violations.append((
                    call.lineno,
                    "B-2 unclassified authority-carrying arg: %s %s at %s:%d: %s "
                    "(make the provenance explicit)"
                    % (name, label, "engine_dispatch.py", call.lineno, snippet),
                ))
    return violations


def test_b2_authority_carrying_sinks_never_read_engine_authored_dicts():
    """Ruling B-2: spawn/lease/cleanup sinks take values from authority, never state."""
    path = _b2_engine_dispatch_path()
    source = open(path, encoding="utf-8").read()
    violations = _b2_find_violations(source)
    assert not violations, "\n".join(msg for _, msg in violations)


def test_b2_ast_check_fails_on_unclassified_expression():
    """Edge 2: unrecognised provenance fails closed rather than passing."""
    # Synthetic snippet: sink arg is a bare Name with no authority binding.
    snippet = (
        "def _continue_run(run_dir, authority):\n"
        "    mystery = something_else()\n"
        "    _spawn_run_child(run_dir, 1, mystery)\n"
    )
    violations = _b2_find_violations(snippet)
    assert violations, "expected unclassified failure, got none"
    assert any("unclassified" in msg for _, msg in violations)


def test_b2_ast_check_fails_on_receipt_fed_attempt_timeout():
    """Edge 4: receipt-fed execution timeout at an engine sink is a B-2 violation."""
    snippet = (
        "def _run_child_main(run_dir, authority, state):\n"
        "    _run_engine_files(\n"
        "        list(authority.argv), 'p', 'o', 'e',\n"
        "        state['attemptTimeout'], 'prog', 1, authority.cwd)\n"
    )
    violations = _b2_find_violations(snippet)
    assert violations, "expected receipt-fed timeout failure, got none"
    assert any("timeout" in msg and "forbidden" in msg for _, msg in violations)


def test_b2_ast_check_fails_on_receipt_fed_spawn_decision():
    """Edge 5: a spawn gated by a receipt/state dict is a B-2 violation."""
    snippet = (
        "def _continue_run(run_dir, authority, state):\n"
        "    if state.get('allowSpawn'):\n"
        "        _spawn_run_child(run_dir, 1, authority)\n"
    )
    violations = _b2_find_violations(snippet)
    assert violations, "expected receipt-fed spawn-decision failure, got none"
    assert any("spawn-decision" in msg for _, msg in violations)


def test_b2_ast_check_fails_on_authority_var_reassigned_from_receipt():
    """Edge 6: authority-derived name later rebound from a receipt is not trusted."""
    snippet = (
        "def _run_child_main(run_dir, authority, state):\n"
        "    cwd = authority.cwd\n"
        "    cwd = state.get('cwd')\n"
        "    _run_engine_files(\n"
        "        list(authority.argv), 'p', 'o', 'e', 5, 'prog', 1, cwd)\n"
    )
    violations = _b2_find_violations(snippet)
    assert violations, "expected reassignment taint failure, got none"
    assert any("cwd" in msg and "forbidden" in msg for _, msg in violations)


def test_b2_ast_check_fails_on_fresh_receipt_alias_at_seal_launch():
    """Miss 1: a brand-new name bound from state.get is tainted at a sink."""
    snippet = (
        "def _continue_run(run_dir, authority, state):\n"
        "    authority_hash = state.get('authorityHash')\n"
        "    _seal_attempt_launch(run_dir, 1, authority, authority_hash, 5)\n"
    )
    violations = _b2_find_violations(snippet)
    assert violations, "expected fresh receipt-alias failure, got none"
    assert any(
        "authority_hash" in msg and ("forbidden" in msg or "B-2 violation" in msg)
        for _, msg in violations
    ), violations


def test_b2_ast_check_fails_on_fresh_receipt_alias_at_ledger_and_engine_sinks():
    """Miss 2: authority_hash is an inspected sink arg (ledger + engine files)."""
    snippet = (
        "def _run_child_main(run_dir, authority, state):\n"
        "    authority_hash = state.get('authorityHash')\n"
        "    _ledger_claim_attempt(run_dir, 1, authority_hash, authority.run_nonce)\n"
        "    _run_engine_files(\n"
        "        list(authority.argv), 'p', 'o', 'e', 5, 'prog', 1, authority.cwd,\n"
        "        authority_hash=authority_hash)\n"
    )
    violations = _b2_find_violations(snippet)
    assert violations, "expected authority_hash sink failure, got none"
    assert any(
        "authority_hash" in msg and ("forbidden" in msg or "B-2 violation" in msg)
        for _, msg in violations
    ), violations


def test_b2_ast_check_fails_on_receipt_selected_attempt_at_spawn():
    """Miss 3 sink: receipt-bound attempt at _spawn_run_child is a violation."""
    snippet = (
        "def _continue_run(run_dir, authority, state):\n"
        "    in_flight = state.get('inFlightAttempt')\n"
        "    _spawn_run_child(run_dir, in_flight, authority)\n"
    )
    violations = _b2_find_violations(snippet)
    assert violations, "expected receipt-selected attempt failure, got none"
    assert any(
        "attempt" in msg and ("forbidden" in msg or "B-2 violation" in msg)
        for _, msg in violations
    ), violations


def test_b2_ast_check_fails_on_receipt_selected_attempt_at_ledger_claim():
    """Miss 3 sink: receipt-bound attempt at _ledger_claim_attempt is a violation."""
    snippet = (
        "def _continue_run(run_dir, authority, state, authority_hash, run_nonce):\n"
        "    in_flight = state.get('inFlightAttempt')\n"
        "    _ledger_claim_attempt(run_dir, in_flight, authority_hash, run_nonce)\n"
    )
    violations = _b2_find_violations(snippet)
    assert violations, "expected receipt-selected attempt at ledger claim, got none"
    assert any(
        "attempt" in msg and ("forbidden" in msg or "B-2 violation" in msg)
        for _, msg in violations
    ), violations


def test_b2_ast_check_fails_on_receipt_selected_attempt_keyword():
    """Miss 3 sink: keyword attempt= from a receipt alias is a violation."""
    snippet = (
        "def _continue_run(run_dir, authority, state):\n"
        "    in_flight = state.get('inFlightAttempt')\n"
        "    _spawn_run_child(run_dir, authority=authority, attempt=in_flight)\n"
    )
    violations = _b2_find_violations(snippet)
    assert violations, "expected keyword attempt= failure, got none"
    assert any(
        "attempt" in msg and ("forbidden" in msg or "B-2 violation" in msg)
        for _, msg in violations
    ), violations


def test_b2_ast_check_fails_on_receipt_arithmetic_attempt_at_seal():
    """Miss 3 sink: state['completedAttempts'] + 1 at _seal_attempt_launch taints."""
    snippet = (
        "def _continue_run(run_dir, authority, state, authority_hash):\n"
        "    attempt = state['completedAttempts'] + 1\n"
        "    _seal_attempt_launch(run_dir, attempt, authority, authority_hash, 5)\n"
    )
    violations = _b2_find_violations(snippet)
    assert violations, "expected receipt-arithmetic attempt failure, got none"
    assert any(
        "attempt" in msg and ("forbidden" in msg or "B-2 violation" in msg)
        for _, msg in violations
    ), violations


def test_b2_ast_check_clean_on_early_return_receipt_gate_before_spawn():
    """Miss 3 limit: early-return gate on a receipt value is not a spawn-decision.

    Deliberate — not an oversight. Early-return / fall-through gates on receipt
    values can only stop a run in this module (downgrade-only). Reintroduction of
    receipt-selected attempt is caught at the inspected attempt sink argument;
    fall-through bypass behavioural coverage lives in test_engine_dispatch_write.py.
    """
    snippet = (
        "def _continue_run(run_dir, authority, state):\n"
        "    if state.get('inFlightAttempt'):\n"
        "        return {'ok': False}\n"
        "    _spawn_run_child(run_dir, 1, authority)\n"
    )
    violations = _b2_find_violations(snippet)
    assert not violations, "\n".join(msg for _, msg in violations)


def test_b2_ast_check_clean_on_ledger_helper_authority_hash_at_sinks():
    """Positive: authority_hash from _ledger_expected_hash is clean at sinks."""
    snippet = (
        "def _continue_run(run_dir, authority):\n"
        "    authority_hash = _ledger_expected_hash(\n"
        "        run_dir, authority.run_nonce, authority.order_id)\n"
        "    _seal_attempt_launch(run_dir, 1, authority, authority_hash, 5)\n"
        "    _ledger_claim_attempt(\n"
        "        run_dir, 1, authority_hash, authority.run_nonce)\n"
        "    _run_engine_files(\n"
        "        list(authority.argv), 'p', 'o', 'e', 5, 'prog', 1, authority.cwd,\n"
        "        authority_hash=authority_hash)\n"
    )
    violations = _b2_find_violations(snippet)
    assert not violations, "\n".join(msg for _, msg in violations)


def test_b2_ast_check_clean_on_sealed_attempt_sources_at_sinks():
    """Positive: attempt from sealed launch/seals/ledger helpers is clean at sinks."""
    snippet = (
        "def _continue_run(run_dir, authority, authority_hash, run_nonce):\n"
        "    attempt, launch = _find_pending_launch(\n"
        "        run_dir, authority_hash, run_nonce)\n"
        "    _spawn_run_child(run_dir, attempt, authority)\n"
        "    completed = _completed_attempts_from_seals(\n"
        "        run_dir, authority_hash, run_nonce)\n"
        "    next_attempt = completed + 1\n"
        "    _seal_attempt_launch(\n"
        "        run_dir, next_attempt, authority, authority_hash, 5)\n"
        "    record = _ledger_attempt_claim(\n"
        "        run_dir, attempt, authority_hash, run_nonce)\n"
        "    sealed_attempt = record.get('attempt')\n"
        "    _ledger_claim_attempt(\n"
        "        run_dir, sealed_attempt, authority_hash, run_nonce)\n"
    )
    violations = _b2_find_violations(snippet)
    assert not violations, "\n".join(msg for _, msg in violations)


def test_b2_ast_check_clean_on_authority_attr_spawn_without_receipt_gate():
    """Positive: spawn reached without a receipt-fed control gate is clean."""
    snippet = (
        "def _continue_run(run_dir, authority):\n"
        "    if not allow_spawn:\n"
        "        return {'ok': False}\n"
        "    _spawn_run_child(run_dir, 1, authority)\n"
    )
    violations = _b2_find_violations(snippet)
    assert not violations, "\n".join(msg for _, msg in violations)


def test_b2_ast_check_clean_on_unclassified_rebind_of_authority_param():
    """Edge 2: unclassified rebind of authority drops derived but does not taint."""
    snippet = (
        "def _continue_run(run_dir, authority):\n"
        "    authority = _build_write_authority(run_dir)\n"
        "    _spawn_run_child(run_dir, 1, authority)\n"
    )
    violations = _b2_find_violations(snippet)
    assert not violations, "\n".join(msg for _, msg in violations)

