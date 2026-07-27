import importlib.util
import json
import os
import shutil

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    spec = importlib.util.spec_from_file_location(
        "engine_dispatch", os.path.join(_HERE, "..", "engine_dispatch.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ED = _load()

_SV = importlib.util.spec_from_file_location(
    "sanitized_view", os.path.join(_HERE, "..", "sanitized_view.py"))
_SV_MOD = importlib.util.module_from_spec(_SV)
_SV.loader.exec_module(_SV_MOD)


def _never_build_view(_repo):
    raise AssertionError("build_view should not be called")


def _fake_build_view(tmp_path, *, source_dirty=False, stripped=None):
    counter = {"n": 0}
    meta = {"repo_arg": None, "view_path": None, "build_count": 0}

    def build_view(repo_real):
        counter["n"] += 1
        meta["build_count"] = counter["n"]
        meta["repo_arg"] = repo_real
        view_dir = tmp_path / ("sanitized-view-%d" % counter["n"])
        view_dir.mkdir(parents=True, exist_ok=True)
        meta["view_path"] = str(view_dir)
        repo = os.path.realpath(repo_real)
        skip = set(stripped or [])
        for name in os.listdir(repo):
            if name in skip:
                continue
            src = os.path.join(repo, name)
            dst = view_dir / name
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        return {
            "path": str(view_dir),
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
    assert cwd == build_view.meta["view_path"]
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
    assert res == {
        "ok": False, "reason": "unrunnable", "detail": "repo-root-absent",
        "attempts": 0, "forfeited": False,
    }
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
    assert view_cwd == build_view.meta["view_path"]


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
    assert res == {
        "ok": False, "reason": "unrunnable", "detail": "repo-root-absent",
        "attempts": 0, "forfeited": False,
    }


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
    assert res == {
        "ok": False, "reason": "unrunnable", "detail": "sanitized-view-export-failed",
        "attempts": 0, "forfeited": False,
    }
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
