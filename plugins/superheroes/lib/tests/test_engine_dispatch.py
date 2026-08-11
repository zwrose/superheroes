import ast
import importlib.util
import json
import os
import shutil
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

_SV = importlib.util.spec_from_file_location(
    "sanitized_view", os.path.join(_HERE, "..", "sanitized_view.py"))
_SV_MOD = importlib.util.module_from_spec(_SV)
_SV.loader.exec_module(_SV_MOD)


@pytest.fixture(autouse=True)
def _pin_temp_base_to_tmp_path(tmp_path, monkeypatch):
    """Keep sanitized views and dispatch journals off the real system temp directory."""
    base = str(tmp_path / "sanitized-temp-base")
    os.makedirs(base, exist_ok=True)
    monkeypatch.setattr(_SV_MOD.tempfile, "gettempdir", lambda: base)
    journal_root = str(tmp_path / "dispatch-journal-root")
    os.makedirs(journal_root, exist_ok=True)
    monkeypatch.setenv(ED.JOURNAL_ROOT_ENV, journal_root)
    yield


def _never_build_view(_repo):
    raise AssertionError("build_view should not be called")


def _fake_build_view(tmp_path, *, source_dirty=False, stripped=None):
    counter = {"n": 0}
    meta = {"repo_arg": None, "view_path": None, "build_count": 0}

    def build_view(repo_real, *, diff_base=None):
        counter["n"] += 1
        meta["build_count"] = counter["n"]
        meta["repo_arg"] = repo_real
        meta["diff_base"] = diff_base
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
        "diffBase": None,
        "diffPath": None,
        "diffBytes": None,
        "diffWithheldCount": None,
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
    root.mkdir(exist_ok=True)
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
        "attempts": 0, "forfeited": False, "terminal": True, "runDir": "", "argv": [],
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


def test_main_dispatch_review_without_repo_root_argparse_refusal(tmp_path):
    prompt = _valid_prompt(tmp_path)
    with pytest.raises(SystemExit) as excinfo:
        ED.main([
            "dispatch-review",
            "--engine", "codex",
            "--effort", "high",
            "--prompt-path", prompt,
        ])
    assert excinfo.value.code == 2


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

    def fail_build(_repo, *, diff_base=None):
        raise ED.sanitized_view.SanitizedViewError("sanitized-view-export-failed")

    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=fail_build,
    )
    assert res["ok"] is False
    assert res["reason"] == "unrunnable"
    assert res["detail"] == "sanitized-view-export-failed"
    assert res["attempts"] == 0
    assert res["forfeited"] is False
    assert res["terminal"] is True
    assert res["runDir"] == ""
    assert res["argv"] == []
    assert "ledger" in res
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

    def capture_build(repo_real, *, diff_base=None):
        view = _fake_build_view(tmp_path)(repo_real, diff_base=diff_base)
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

    def capture_build(repo_real, *, diff_base=None):
        view = build_view_fn(repo_real, diff_base=diff_base)
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


def _manual_open_review_run(tmp_path, run_dir):
    """Journal run-opened without spawning — for supervision primitive tests."""
    repo_root = _repo(tmp_path)
    build_view = _fake_build_view(tmp_path)
    view = build_view(os.path.realpath(repo_root))
    cwd = os.path.realpath(view["path"])
    built = __import__("engine_adapter").build_argv_result(
        "codex", "review", "high", {"model": "sonnet", "cwd": cwd},
    )
    argv = built["argv"]
    prompt_path = _valid_prompt(tmp_path)
    with open(prompt_path, encoding="utf-8") as fh:
        base = fh.read()
    fed = ED.ANTIHIJACK_PREAMBLE + _SV_MOD.sanitized_view_notice(view) + base
    os.makedirs(run_dir, exist_ok=True)
    ok, detail = ED._open_review_run(
        run_dir, engine="codex", argv=argv, cwd=cwd,
        timeout=ED.RETRY_MIN_TIMEOUT, retry_timeout=ED.RETRY_MIN_TIMEOUT,
        prompt_path=prompt_path, view_path=view["path"], view_meta=view,
        fed_prompt=fed, order_id="test-order", progress_path=os.path.join(run_dir, "progress.jsonl"),
        repo_root=os.path.realpath(repo_root),
    )
    assert ok, detail
    return repo_root, view


def test_run_lock_serializes_concurrent_spawn(tmp_path, monkeypatch):
    """A3: two concurrent supervisors cannot both spawn attempt 1."""
    import subprocess
    import sys

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_codex = fake_bin / "codex"
    fake_codex.write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(120)\n", encoding="utf-8")
    fake_codex.chmod(0o755)
    path_env = str(fake_bin) + os.pathsep + "/usr/bin" + os.pathsep + "/bin"

    run_dir = str(tmp_path / "run")
    _manual_open_review_run(tmp_path, run_dir)
    mod_path = os.path.join(_HERE, "..", "engine_dispatch.py")
    journal_env = os.environ.get(ED.JOURNAL_ROOT_ENV, "")
    child = r"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(%(mod)r))
os.environ[%(jenv)r] = %(jval)r
os.environ["PATH"] = %(path)r
import importlib.util
spec = importlib.util.spec_from_file_location("engine_dispatch", %(mod)r)
ed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ed)
deadline = time.monotonic() + 2
res = ed._supervise(%(run_dir)r, run_kind=ed.RUN_KIND_REVIEW, deadline=deadline)
print(json.dumps({"detail": res.get("detail"), "attempts": res.get("attempts")}))
""" % {"mod": mod_path, "jenv": ED.JOURNAL_ROOT_ENV, "jval": json.dumps(journal_env),
       "run_dir": run_dir, "path": json.dumps(path_env)}
    p1 = subprocess.Popen([sys.executable, "-c", child], stdout=subprocess.PIPE, text=True)
    p2 = subprocess.Popen([sys.executable, "-c", child], stdout=subprocess.PIPE, text=True)
    out1 = p1.communicate(timeout=60)[0]
    out2 = p2.communicate(timeout=60)[0]
    details = {json.loads(out1).get("detail"), json.loads(out2).get("detail")}
    assert "run-locked" in details
    records, _ = ED._journal_read(run_dir)
    started = [r for r in records if r.get("kind") == "attempt-started" and r.get("attempt") == 1]
    assert len(started) == 1


def test_journal_torn_tail_discarded_valid_prefix_kept(tmp_path):
    run_dir = str(tmp_path / "run")
    _manual_open_review_run(tmp_path, run_dir)
    records_before, _ = ED._journal_read(run_dir)
    path = ED._journal_path(run_dir)
    with open(path, "ab") as fh:
        fh.write(b'{"kind":"run-folded","result":{"ok":true},"at":1.0}')  # no newline
    records, corrupt = ED._journal_read(run_dir)
    assert corrupt is False
    assert records == records_before


def test_journal_interior_corruption_fails_closed(tmp_path):
    run_dir = str(tmp_path / "run")
    _manual_open_review_run(tmp_path, run_dir)
    path = ED._journal_path(run_dir)
    with open(path, "ab") as fh:
        fh.write(b"not-json\n")
    records, corrupt = ED._journal_read(run_dir)
    assert corrupt is True
    res = ED._supervise(
        run_dir, run_kind=ED.RUN_KIND_REVIEW,
        deadline=time.monotonic() + 5,
    )
    assert res["terminal"] is True
    assert res["detail"] == "journal-corrupt"
    started = [r for r in ED._journal_read(run_dir)[0] if r.get("kind") == "attempt-started"]
    assert started == []


def test_journal_root_pointer_survives_env_removal(tmp_path, monkeypatch):
    run_dir = str(tmp_path / "run")
    _manual_open_review_run(tmp_path, run_dir)
    pointer = os.path.join(run_dir, "journal-root.txt")
    assert os.path.isfile(pointer)
    monkeypatch.delenv(ED.JOURNAL_ROOT_ENV, raising=False)
    records, _ = ED._journal_read(run_dir)
    assert any(r.get("kind") == "run-opened" for r in records)


def test_run_dir_not_empty_unopened_refused(tmp_path):
    repo_root = _repo(tmp_path)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "stale.txt").write_text("leftover\n", encoding="utf-8")
    fake = FakeRunner([])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path), run_dir=str(run_dir),
    )
    assert res["detail"] == "run-dir-not-empty-unopened"
    assert res["attempts"] == 0
    assert len(fake.calls) == 0


def test_review_run_dir_inside_repo_root_refused(tmp_path):
    repo_root = _repo(tmp_path)
    run_dir = os.path.join(repo_root, "dispatch-run")
    os.makedirs(run_dir)
    fake = FakeRunner([])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path), run_dir=run_dir,
    )
    assert res["detail"] == "run-dir-inside-repo-root"
    assert res["attempts"] == 0
    assert len(fake.calls) == 0


def test_dispatch_abandon_idempotent_terminal(tmp_path):
    run_dir = str(tmp_path / "run")
    _manual_open_review_run(tmp_path, run_dir)
    first = ED.dispatch_abandon(run_dir)
    second = ED.dispatch_abandon(run_dir)
    assert first["terminal"] is True
    assert first["detail"] == "run-abandoned"
    assert second["detail"] == "run-abandoned"
    records, _ = ED._journal_read(run_dir)
    abandoned = [r for r in records if r.get("kind") == "run-abandoned"]
    assert len(abandoned) == 1


def test_dispatch_poll_never_spawns(tmp_path):
    run_dir = str(tmp_path / "run")
    _manual_open_review_run(tmp_path, run_dir)
    res = ED.dispatch_poll(run_dir)
    assert res["reason"] == "running"
    records, _ = ED._journal_read(run_dir)
    assert not any(r.get("kind") == "attempt-started" for r in records)


def test_supervise_run_not_opened(tmp_path):
    run_dir = str(tmp_path / "empty-run")
    os.makedirs(run_dir)
    res = ED._supervise(
        run_dir, run_kind=ED.RUN_KIND_REVIEW, deadline=time.monotonic() + 5,
    )
    assert res["detail"] == "run-not-opened"
    assert res["attempts"] == 0


def test_supervise_run_kind_mismatch(tmp_path):
    run_dir = str(tmp_path / "run")
    _manual_open_review_run(tmp_path, run_dir)
    res = ED._supervise(
        run_dir, run_kind=ED.RUN_KIND_WRITE, deadline=time.monotonic() + 5,
    )
    assert res["detail"] == "run-kind-mismatch"
    assert res["attempts"] == 0
    records, _ = ED._journal_read(run_dir)
    assert not any(r.get("kind") == "attempt-started" for r in records)


def _engine_dispatch_source_path():
    return os.path.join(_HERE, "..", "engine_dispatch.py")


def _subprocess_popen_census():
    path = _engine_dispatch_source_path()
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)

    popen_counts = {}
    run_engine_files_has_cwd = False

    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        count = 0
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            func = child.func
            if not (isinstance(func, ast.Attribute) and func.attr == "Popen"
                    and isinstance(func.value, ast.Name) and func.value.id == "subprocess"):
                continue
            count += 1
            if node.name == "_run_engine_files":
                run_engine_files_has_cwd = any(kw.arg == "cwd" for kw in child.keywords)
        if count:
            popen_counts[node.name] = count

    return popen_counts, run_engine_files_has_cwd


def test_subprocess_popen_census():
    popen_counts, run_engine_files_has_cwd = _subprocess_popen_census()
    assert popen_counts == {"_run_engine": 1, "_run_engine_files": 1, "_spawn_attempt": 1}
    assert run_engine_files_has_cwd


def _linked_worktree(tmp_path):
    main = str(tmp_path / "main")
    os.makedirs(main, exist_ok=True)
    subprocess.run(["git", "-C", main, "init", "-q"], check=True)
    readme = os.path.join(main, "README.md")
    with open(readme, "w", encoding="utf-8") as fh:
        fh.write("hello\n")
    subprocess.run(["git", "-C", main, "add", "README.md"], check=True)
    subprocess.run(
        ["git", "-C", main, "-c", "user.email=t@t.local", "-c", "user.name=t",
         "commit", "-qm", "init"],
        check=True,
    )
    wt = str(tmp_path / "wt")
    subprocess.run(["git", "-C", main, "worktree", "add", "-q", wt], check=True)
    return wt


def _contracted_fed_prompt(base):
    if base and not base.endswith("\n"):
        return base + "\n" + EA.WRITE_REPORT_CONTRACT
    return base + EA.WRITE_REPORT_CONTRACT


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


def test_write_fixture_stdout_gradeable_by_runner():
    fed = _contracted_fed_prompt("Review this code.\n")
    ok_res = EA.grade_write_report("codex", "build", _build_ok_stdout(), fed)
    assert ok_res["ok"] is True
    assert ok_res["signal"] == "ok"
    refusal_res = EA.grade_write_report("codex", "build", _honest_refusal_stdout(), fed)
    assert refusal_res["ok"] is False
    assert refusal_res["signal"] == "plan_wrong"


# --- WO F1: continuation owns argv/cwd/view; journal before build_view -------------


def test_review_continuation_builds_no_second_view(tmp_path):
    run_dir = str(tmp_path / "run")
    repo_root, _ = _manual_open_review_run(tmp_path, run_dir)
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        start_new_session=True,
    )
    ED._journal_append(run_dir, {
        "kind": "attempt-started", "attempt": 1, "childPid": proc.pid, "at": time.time(),
    })
    ED._journal_append(run_dir, {
        "kind": "engine-started", "attempt": 1, "enginePgid": proc.pid, "at": time.time(),
    })
    build_view = _fake_build_view(tmp_path)
    try:
        first = ED.dispatch_review(
            "codex", model="sonnet", effort="high",
            prompt_path=_valid_prompt(tmp_path), repo_root=repo_root,
            run_engine=FakeRunner([]), build_view=build_view, run_dir=run_dir,
            order_id="test-order", max_wait=1,
        )
        assert first.get("terminal") is False
        assert build_view.meta["build_count"] == 0

        second = ED.dispatch_review(
            "codex", model="sonnet", effort="high",
            prompt_path=_valid_prompt(tmp_path), repo_root=repo_root,
            run_engine=FakeRunner([]), build_view=build_view, run_dir=run_dir,
            order_id="test-order", max_wait=1,
        )
        assert second.get("terminal") is False
        assert build_view.meta["build_count"] == 0
    finally:
        ED._terminate_process_group(proc.pid)
        proc.wait(timeout=2)


def test_review_continuation_argv_matches_journal(tmp_path):
    run_dir = str(tmp_path / "run")
    repo_root, _ = _manual_open_review_run(tmp_path, run_dir)
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        start_new_session=True,
    )
    ED._journal_append(run_dir, {
        "kind": "attempt-started", "attempt": 1, "childPid": proc.pid, "at": time.time(),
    })
    ED._journal_append(run_dir, {
        "kind": "engine-started", "attempt": 1, "enginePgid": proc.pid, "at": time.time(),
    })
    records, _ = ED._journal_read(run_dir)
    opened = next(r for r in records if r.get("kind") == "run-opened")
    journalled_argv = opened["argv"]
    build_view = _fake_build_view(tmp_path)
    try:
        res = ED.dispatch_review(
            "codex", model="sonnet", effort="high",
            prompt_path=_valid_prompt(tmp_path), repo_root=repo_root,
            run_engine=FakeRunner([]), build_view=build_view, run_dir=run_dir,
            order_id="test-order", max_wait=1,
        )
        assert res["argv"] == journalled_argv
    finally:
        ED._terminate_process_group(proc.pid)
        proc.wait(timeout=2)


def test_review_continuation_non_terminal_leaves_no_extra_view(tmp_path):
    run_dir = str(tmp_path / "run")
    repo_root, view = _manual_open_review_run(tmp_path, run_dir)
    view_path = view["path"]
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        start_new_session=True,
    )
    ED._journal_append(run_dir, {
        "kind": "attempt-started", "attempt": 1, "childPid": proc.pid, "at": time.time(),
    })
    ED._journal_append(run_dir, {
        "kind": "engine-started", "attempt": 1, "enginePgid": proc.pid, "at": time.time(),
    })
    build_view = _fake_build_view(tmp_path)
    try:
        ED.dispatch_review(
            "codex", model="sonnet", effort="high",
            prompt_path=_valid_prompt(tmp_path), repo_root=repo_root,
            run_engine=FakeRunner([]), build_view=build_view, run_dir=run_dir,
            order_id="test-order", max_wait=1,
        )
        assert os.path.isdir(view_path)
        ED.dispatch_review(
            "codex", model="sonnet", effort="high",
            prompt_path=_valid_prompt(tmp_path), repo_root=repo_root,
            run_engine=FakeRunner([]), build_view=build_view, run_dir=run_dir,
            order_id="test-order", max_wait=1,
        )
        assert build_view.meta["build_count"] == 0
        assert os.path.isdir(view_path)
    finally:
        ED._terminate_process_group(proc.pid)
        proc.wait(timeout=2)


def test_review_resume_order_id_mismatch(tmp_path):
    run_dir = str(tmp_path / "run")
    repo_root, _ = _manual_open_review_run(tmp_path, run_dir)
    build_view = _fake_build_view(tmp_path)
    fake = FakeRunner([])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=build_view, run_dir=run_dir, order_id="order-2", max_wait=0,
    )
    assert res["detail"] == "run-dir-reused"
    assert res["attempts"] == 0


# --- WO F1 1b: blocking supervise loop must not busy-spin ----------------------


def test_blocking_supervise_loop_bounded_under_held_lock(tmp_path, monkeypatch):
    import threading
    import file_lock

    run_dir = str(tmp_path / "run")
    repo_root, _ = _manual_open_review_run(tmp_path, run_dir)
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
            ED.dispatch_review(
                "codex", model="sonnet", effort="high",
                prompt_path=_valid_prompt(tmp_path), repo_root=repo_root,
                run_engine=FakeRunner([]),
                build_view=_fake_build_view(tmp_path), run_dir=run_dir,
                order_id="test-order", max_wait=None,
            )

        t = threading.Thread(target=run_dispatch, daemon=True)
        t.start()
        time.sleep(0.3)
        assert calls["n"] <= 8
    finally:
        file_lock.release(lock_path)


def test_run_child_waits_for_late_attempt_started(tmp_path, monkeypatch):
    """Run-child must wait for attempt-started when spawned before the journal record lands."""
    import threading

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_codex = fake_bin / "codex"
    fake_codex.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "sys.stdout.write(%r)\n" % _build_ok_stdout(),
        encoding="utf-8",
    )
    fake_codex.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin) + os.pathsep + "/usr/bin" + os.pathsep + "/bin")

    wt = _linked_worktree(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    baseline = ED._worktree_baseline(os.path.realpath(wt))
    _EA = importlib.util.spec_from_file_location(
        "engine_adapter", os.path.join(_HERE, "..", "engine_adapter.py"))
    EA = importlib.util.module_from_spec(_EA)
    _EA.loader.exec_module(EA)
    built = EA.build_argv_result(
        "codex", "build", "high", {"model": "sonnet", "cwd": os.path.realpath(wt)},
    )
    ED._open_write_run(
        run_dir, engine="codex", argv=built["argv"], cwd=os.path.realpath(wt),
        timeout=ED.RETRY_MIN_TIMEOUT, retry_timeout=ED.RETRY_MIN_TIMEOUT,
        prompt_path=_valid_prompt(tmp_path), order_id="race-1", base_sha="abc",
        worktree_baseline=baseline,
        progress_path=os.path.join(run_dir, "progress.jsonl"),
    )

    mod_path = os.path.join(_HERE, "..", "engine_dispatch.py")
    journal_env = os.environ.get(ED.JOURNAL_ROOT_ENV, "")
    child = subprocess.Popen(
        [sys.executable, "-B", mod_path, "run-child", "--run-dir", run_dir],
        cwd=run_dir, start_new_session=True,
        env={k: v for k, v in os.environ.items() if k != ED.JOURNAL_ROOT_ENV}
        | {ED.JOURNAL_ROOT_ENV: journal_env},
    )

    def _late_journal():
        time.sleep(0.15)
        ED._journal_append(run_dir, {
            "kind": "attempt-started", "attempt": 1,
            "childPid": child.pid, "at": time.time(),
        })

    threading.Thread(target=_late_journal, daemon=True).start()
    rc = child.wait(timeout=30)
    assert rc == 0
    records, _ = ED._journal_read(run_dir)
    kinds = [r.get("kind") for r in records]
    assert "engine-started" in kinds
    assert "attempt-ended" in kinds


def test_stale_run_lock_reclaimed(tmp_path):
    """A dead supervisor's run.lock older than RUN_LOCK_TTL is reclaimed on next acquire."""
    import file_lock
    import hostinfo
    import socket

    run_dir = str(tmp_path / "run")
    _manual_open_review_run(tmp_path, run_dir)
    lock_path = os.path.join(run_dir, ED.RUN_LOCK_NAME)
    stale_holder = {
        "pid": 99999999,
        "host": socket.gethostname(),
        "acquiredAt": "2000-01-01T00:00:00Z",
        "bootId": hostinfo.boot_id(),
        "ttl": ED.RUN_LOCK_TTL,
    }
    with open(lock_path, "w", encoding="utf-8") as fh:
        json.dump(stale_holder, fh)

    file_lock.acquire(lock_path, ttl=ED.RUN_LOCK_TTL)
    file_lock.release(lock_path)


# --- WO F1 2a/2b/2e: abandon, fold durability, poll projection -----------------


def test_spawn_attempt_refuses_when_abandon_requested(tmp_path):
    run_dir = str(tmp_path / "run")
    _manual_open_review_run(tmp_path, run_dir)
    ED._journal_append(run_dir, {"kind": "abandon-requested", "at": time.time()})
    state = ED._journal_state(ED._journal_read(run_dir)[0])
    ok, detail = ED._spawn_attempt(run_dir, state, 1, run_engine=FakeRunner([]))
    assert not ok
    assert detail == "abandon-requested"
    records, _ = ED._journal_read(run_dir)
    assert not any(r.get("kind") == "attempt-started" for r in records)


def test_fold_append_failure_leaves_lease(tmp_path, monkeypatch):
    wt = _linked_worktree(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    baseline = ED._worktree_baseline(os.path.realpath(wt))
    _EA = importlib.util.spec_from_file_location(
        "engine_adapter", os.path.join(_HERE, "..", "engine_adapter.py"))
    EA = importlib.util.module_from_spec(_EA)
    _EA.loader.exec_module(EA)
    built = EA.build_argv_result(
        "codex", "build", "high", {"model": "sonnet", "cwd": os.path.realpath(wt)},
    )
    ED._acquire_worktree_lease(os.path.realpath(wt), run_dir)
    ED._open_write_run(
        run_dir, engine="codex", argv=built["argv"], cwd=os.path.realpath(wt),
        timeout=ED.RETRY_MIN_TIMEOUT, retry_timeout=ED.RETRY_MIN_TIMEOUT,
        prompt_path=_valid_prompt(tmp_path), order_id="order-1", base_sha="abc",
        worktree_baseline=baseline,
        progress_path=os.path.join(run_dir, "progress.jsonl"),
    )
    lease_path = ED._worktree_lease_path(os.path.realpath(wt))
    assert os.path.exists(lease_path)
    real_append = ED._journal_append

    def fail_fold(run_dir_real, record):
        if record.get("kind") == "run-folded":
            return False
        return real_append(run_dir_real, record)

    monkeypatch.setattr(ED, "_journal_append", fail_fold)
    records, _ = ED._journal_read(run_dir)
    state = ED._journal_state(records)
    result = ED._fold_run(run_dir, state, {"ok": True, "terminal": True, "attempts": 1})
    assert result["detail"] == "terminal-record-not-durable"
    assert result["terminal"] is False
    assert os.path.exists(lease_path)


def test_abandon_append_failure_leaves_lease(tmp_path, monkeypatch):
    wt = _linked_worktree(tmp_path)
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir, exist_ok=True)
    baseline = ED._worktree_baseline(os.path.realpath(wt))
    _EA = importlib.util.spec_from_file_location(
        "engine_adapter", os.path.join(_HERE, "..", "engine_adapter.py"))
    EA = importlib.util.module_from_spec(_EA)
    _EA.loader.exec_module(EA)
    built = EA.build_argv_result(
        "codex", "build", "high", {"model": "sonnet", "cwd": os.path.realpath(wt)},
    )
    ED._acquire_worktree_lease(os.path.realpath(wt), run_dir)
    ED._open_write_run(
        run_dir, engine="codex", argv=built["argv"], cwd=os.path.realpath(wt),
        timeout=ED.RETRY_MIN_TIMEOUT, retry_timeout=ED.RETRY_MIN_TIMEOUT,
        prompt_path=_valid_prompt(tmp_path), order_id="order-1", base_sha="abc",
        worktree_baseline=baseline,
        progress_path=os.path.join(run_dir, "progress.jsonl"),
    )
    lease_path = ED._worktree_lease_path(os.path.realpath(wt))
    assert os.path.exists(lease_path)
    real_append = ED._journal_append

    def fail_abandon(run_dir_real, record):
        if record.get("kind") == "run-abandoned":
            return False
        return real_append(run_dir_real, record)

    monkeypatch.setattr(ED, "_journal_append", fail_abandon)
    res = ED.dispatch_abandon(run_dir)
    assert res["detail"] == "terminal-record-not-durable"
    assert res["terminal"] is False
    assert os.path.exists(lease_path)


def test_dispatch_poll_projection_excludes_sensitive_fields(tmp_path):
    run_dir = str(tmp_path / "run")
    _manual_open_review_run(tmp_path, run_dir)
    res = ED.dispatch_poll(run_dir)
    raw = json.dumps(res)
    assert "fedPrompt" not in raw
    assert "viewMeta" not in raw
    assert res["poll"]["state"] == "idle"
    assert res["poll"]["runKind"] == ED.RUN_KIND_REVIEW


def test_dispatch_poll_abandoned_state(tmp_path):
    run_dir = str(tmp_path / "run")
    _manual_open_review_run(tmp_path, run_dir)
    ED._journal_append(run_dir, {"kind": "run-abandoned", "detail": "abandoned", "at": time.time()})
    res = ED.dispatch_poll(run_dir)
    assert res["poll"]["terminal"] is True
    assert res["poll"]["state"] == "run-abandoned"
    assert res["detail"] == "run-abandoned"


def test_dispatch_poll_not_opened_state(tmp_path):
    run_dir = str(tmp_path / "empty")
    os.makedirs(run_dir)
    res = ED.dispatch_poll(run_dir)
    assert res["poll"]["terminal"] is True
    assert res["poll"]["state"] == "run-not-opened"
    assert res["detail"] == "run-not-opened"


def test_run_engine_files_caps_stdout(tmp_path, monkeypatch):
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    tail_json = json.dumps({"ok": True, "signal": "ok", "evidence": {}})
    over = ED.MAX_STDOUT_CAPTURE + 1024
    script = (
        "import sys\n"
        "sys.stdout.write('x' * %d + %r)\n" % (over, tail_json)
    )
    stdout_path = os.path.join(run_dir, "attempt-1.stdout")
    stderr_path = os.path.join(run_dir, "attempt-1.stderr")
    prompt_path = os.path.join(run_dir, "prompt.txt")
    open(prompt_path, "w").write("go\n")
    ED._journal_append(run_dir, {
        "kind": "run-opened", "runKind": ED.RUN_KIND_WRITE, "engine": "codex",
        "roleKind": "build", "orderId": "x", "argv": ["python3", "-c", "x"],
        "cwd": run_dir, "timeout": 30, "retryTimeout": 30,
        "promptPath": prompt_path, "viewPath": None, "baseSha": "abc",
        "supervisorPid": 1, "at": time.time(),
    })
    ED._journal_append(run_dir, {
        "kind": "engine-launching", "attempt": 1, "childPid": 1, "at": time.time(),
    })
    monkeypatch.setattr(ED, "HEARTBEAT_INTERVAL", 0.01)
    ED._run_engine_files(
        run_dir, 1, [sys.executable, "-c", script], run_dir,
        prompt_path, stdout_path, stderr_path, 30, os.path.join(run_dir, "progress.jsonl"),
    )
    assert os.path.isfile(stdout_path)
    assert os.path.getsize(stdout_path) <= ED.MAX_STDOUT_CAPTURE
    tail_text = ED._read_capped_text(stdout_path)
    assert tail_text.endswith(tail_json)
    parsed = json.loads(tail_json)
    assert parsed["ok"] is True


def test_review_fold_append_failure_leaves_view(tmp_path, monkeypatch):
    run_dir = str(tmp_path / "run")
    repo_root, view = _manual_open_review_run(tmp_path, run_dir)
    view_path = view["path"]
    assert os.path.isdir(view_path)
    real_append = ED._journal_append

    def fail_fold(run_dir_real, record):
        if record.get("kind") == "run-folded":
            return False
        return real_append(run_dir_real, record)

    monkeypatch.setattr(ED, "_journal_append", fail_fold)
    records, _ = ED._journal_read(run_dir)
    state = ED._journal_state(records)
    result = ED._fold_run(
        run_dir, state,
        {"ok": True, "terminal": True, "attempts": 1, "findings": [], "engagement": {}},
    )
    assert result["detail"] == "terminal-record-not-durable"
    assert result["terminal"] is False
    assert os.path.isdir(view_path)


def _install_terminal_observers(monkeypatch):
    events = []
    real_append = ED._journal_append
    real_finalize = ED._finalize_run

    def obs_append(run_dir_real, record):
        ok = real_append(run_dir_real, record)
        if ok and record.get("kind") in ("run-folded", "run-abandoned"):
            events.append("terminal-append-ok")
        return ok

    def obs_finalize(state, terminal=False):
        events.append("cleanup")
        return real_finalize(state, terminal=terminal)

    monkeypatch.setattr(ED, "_journal_append", obs_append)
    monkeypatch.setattr(ED, "_finalize_run", obs_finalize)
    return events


def _assert_no_cleanup_before_terminal_append(events):
    first_terminal = None
    for i, event in enumerate(events):
        if event == "terminal-append-ok":
            if first_terminal is None:
                first_terminal = i
        elif event == "cleanup":
            assert first_terminal is not None, "cleanup before any terminal append"
            assert i > first_terminal


def _linked_worktree(tmp_path):
    repo = str(tmp_path / "main")
    _git_init(repo)
    wt = str(tmp_path / "wt")
    subprocess.run(["git", "-C", repo, "worktree", "add", "-q", wt], check=True)
    return wt


def _git_init(path):
    os.makedirs(path, exist_ok=True)
    subprocess.run(["git", "-C", path, "init", "-q"], check=True)
    readme = os.path.join(path, "README.md")
    with open(readme, "w", encoding="utf-8") as fh:
        fh.write("hello\n")
    subprocess.run(["git", "-C", path, "add", "README.md"], check=True)
    subprocess.run(
        ["git", "-C", path, "-c", "user.email=t@t.local", "-c", "user.name=t", "commit", "-qm", "init"],
        check=True,
    )
    return path


@pytest.mark.parametrize("scenario", [
    "review_success",
    "review_double_forfeit",
    "review_vacuous_forfeit",
    "write_success",
    "write_honest_refusal",
    "write_dirtied_retry",
    "abandon_dead_engine",
    "abandon_live_engine",
    "supervise_internal_exception",
])
def test_terminal_transition_invariant_no_cleanup_before_durable_record(
    tmp_path, monkeypatch, scenario,
):
    events = _install_terminal_observers(monkeypatch)

    if scenario == "review_success":
        repo_root = _repo(tmp_path)
        fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
        res = ED.dispatch_review(
            "codex", model="sonnet", effort="high",
            prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
            build_view=_fake_build_view(tmp_path),
        )
        assert res["ok"] is True
    elif scenario == "review_double_forfeit":
        repo_root = _repo(tmp_path)
        fake = FakeRunner([("", True, 0, ""), ("", True, 0, "")])
        res = ED.dispatch_review(
            "codex", model="sonnet", effort="high",
            prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
            build_view=_fake_build_view(tmp_path),
        )
        assert res.get("forfeited") is True
    elif scenario == "review_vacuous_forfeit":
        repo_root = _repo(tmp_path)
        empty = json.dumps({"findings": []})
        fake = FakeRunner([(empty, False, 0, ""), (empty, False, 0, "")])
        res = ED.dispatch_review(
            "codex", model="sonnet", effort="high",
            prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
            build_view=_fake_build_view(tmp_path),
        )
        assert res["reason"] == "vacuous"
    elif scenario == "write_success":
        wt = _linked_worktree(tmp_path)
        fake = FakeRunner([(_build_ok_stdout(), False, 0, "")])
        res = ED.dispatch_write(
            "codex", model="sonnet", effort="high",
            prompt_path=_valid_prompt(tmp_path), cwd=wt,
            run_dir=str(tmp_path / "run-write"), order_id="inv-1", run_engine=fake,
        )
        assert res["ok"] is True
    elif scenario == "write_honest_refusal":
        wt = _linked_worktree(tmp_path)
        fake = FakeRunner([(_honest_refusal_stdout(), False, 0, "")])
        res = ED.dispatch_write(
            "codex", model="sonnet", effort="high",
            prompt_path=_valid_prompt(tmp_path), cwd=wt,
            run_dir=str(tmp_path / "run-refusal"), order_id="inv-2", run_engine=fake,
        )
        assert res["reason"] == "plan_wrong"
    elif scenario == "write_dirtied_retry":
        wt = _linked_worktree(tmp_path)

        class DirtyTimeoutRunner:
            def __call__(self, argv, prompt_bytes, timeout, progress_cb, cwd):
                with open(os.path.join(cwd, "dirty.txt"), "w", encoding="utf-8") as fh:
                    fh.write("x")
                return "", True, 0, ""

        res = ED.dispatch_write(
            "codex", model="sonnet", effort="high",
            prompt_path=_valid_prompt(tmp_path), cwd=wt,
            run_dir=str(tmp_path / "run-dirty"), order_id="inv-3",
            run_engine=DirtyTimeoutRunner(), max_wait=120,
        )
        assert res["detail"] == "worktree-dirtied-by-attempt"
    elif scenario == "abandon_dead_engine":
        run_dir = str(tmp_path / "run-abandon-dead")
        _manual_open_review_run(tmp_path, run_dir)
        ED._journal_append(run_dir, {
            "kind": "attempt-ended", "attempt": 1,
            "exit": 0, "timedOut": False, "signal": None, "refusal": None, "at": time.time(),
        })
        res = ED.dispatch_abandon(run_dir)
        assert res["detail"] == "run-abandoned"
    elif scenario == "abandon_live_engine":
        run_dir = str(tmp_path / "run-abandon-live")
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(120)"],
            start_new_session=True,
        )
        try:
            _manual_open_review_run(tmp_path, run_dir)
            ED._journal_append(run_dir, {
                "kind": "attempt-started", "attempt": 1, "childPid": proc.pid, "at": time.time(),
            })
            ED._journal_append(run_dir, {
                "kind": "engine-started", "attempt": 1, "enginePgid": proc.pid, "at": time.time(),
            })
            res = ED.dispatch_abandon(run_dir)
            assert res["detail"] == "run-abandoned"
        finally:
            ED._terminate_process_group(proc.pid)
            try:
                proc.wait(timeout=2)
            except Exception:
                pass
    elif scenario == "supervise_internal_exception":
        repo_root = _repo(tmp_path)

        def boom(*_a, **_k):
            raise RuntimeError("supervise-boom")

        monkeypatch.setattr(ED, "_supervise", boom)
        fake = FakeRunner([])
        res = ED.dispatch_review(
            "codex", model="sonnet", effort="high",
            prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
            build_view=_fake_build_view(tmp_path),
        )
        assert res["detail"] == "internal-RuntimeError"

    _assert_no_cleanup_before_terminal_append(events)
    assert "terminal-append-ok" in events
    assert "cleanup" in events


def test_run_engine_files_caps_under_live_writer_stdout_and_stderr(tmp_path, monkeypatch):
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    tail_json = json.dumps({"ok": True, "signal": "ok", "evidence": {}})
    script = (
        "import sys, time\n"
        "for _ in range(25):\n"
        "    sys.stdout.write('x' * 400000)\n"
        "    sys.stdout.flush()\n"
        "    sys.stderr.write('e' * 4000)\n"
        "    sys.stderr.flush()\n"
        "    time.sleep(0.02)\n"
        "sys.stdout.write(%r)\n" % tail_json
    )
    stdout_path = os.path.join(run_dir, "attempt-1.stdout")
    stderr_path = os.path.join(run_dir, "attempt-1.stderr")
    prompt_path = os.path.join(run_dir, "prompt.txt")
    open(prompt_path, "w").write("go\n")
    ED._journal_append(run_dir, {
        "kind": "run-opened", "runKind": ED.RUN_KIND_WRITE, "engine": "codex",
        "roleKind": "build", "orderId": "x", "argv": ["python3", "-c", "x"],
        "cwd": run_dir, "timeout": 30, "retryTimeout": 30,
        "promptPath": prompt_path, "viewPath": None, "baseSha": "abc",
        "supervisorPid": 1, "at": time.time(),
    })
    ED._journal_append(run_dir, {
        "kind": "engine-launching", "attempt": 1, "childPid": 1, "at": time.time(),
    })
    monkeypatch.setattr(ED, "HEARTBEAT_INTERVAL", 0.01)
    ED._run_engine_files(
        run_dir, 1, [sys.executable, "-c", script], run_dir,
        prompt_path, stdout_path, stderr_path, 30, os.path.join(run_dir, "progress.jsonl"),
    )
    assert os.path.getsize(stdout_path) <= ED.MAX_STDOUT_CAPTURE
    assert os.path.getsize(stderr_path) <= ED.MAX_STDERR_CAPTURE
    tail_text = ED._read_capped_text(stdout_path)
    assert tail_text.strip().endswith(tail_json)
    parsed = json.loads(tail_json)
    assert parsed["ok"] is True
    records, _ = ED._journal_read(run_dir)
    state = ED._journal_state(records)
    grade = ED._grade_write_attempt(run_dir, state, 1)
    assert grade["ok"] is True


def test_run_engine_files_caps_only_after_terminate_on_timeout(tmp_path, monkeypatch):
    """On timeout, _cap_file_tail must not run until after _terminate_process_group."""
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    script = (
        "import signal, sys, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "while True:\n"
        "    sys.stdout.write('x' * 50000)\n"
        "    sys.stdout.flush()\n"
        "    sys.stderr.write('e' * 1000)\n"
        "    sys.stderr.flush()\n"
    )
    stdout_path = os.path.join(run_dir, "attempt-1.stdout")
    stderr_path = os.path.join(run_dir, "attempt-1.stderr")
    prompt_path = os.path.join(run_dir, "prompt.txt")
    open(prompt_path, "w").write("go\n")
    ED._journal_append(run_dir, {
        "kind": "run-opened", "runKind": ED.RUN_KIND_WRITE, "engine": "codex",
        "roleKind": "build", "orderId": "x", "argv": ["python3", "-c", "x"],
        "cwd": run_dir, "timeout": 1, "retryTimeout": 1,
        "promptPath": prompt_path, "viewPath": None, "baseSha": "abc",
        "supervisorPid": 1, "at": time.time(),
    })
    ED._journal_append(run_dir, {
        "kind": "engine-launching", "attempt": 1, "childPid": 1, "at": time.time(),
    })
    events = []
    real_cap = ED._cap_file_tail
    real_terminate = ED._terminate_process_group

    def obs_cap(path, max_bytes):
        if path == stdout_path:
            events.append("cap-stdout")
        elif path == stderr_path:
            events.append("cap-stderr")
        else:
            events.append("cap-other")
        return real_cap(path, max_bytes)

    def obs_terminate(pgid):
        events.append("terminate")
        return real_terminate(pgid)

    monkeypatch.setattr(ED, "_cap_file_tail", obs_cap)
    monkeypatch.setattr(ED, "_terminate_process_group", obs_terminate)
    monkeypatch.setattr(ED, "HEARTBEAT_INTERVAL", 0.01)
    ED._run_engine_files(
        run_dir, 1, [sys.executable, "-c", script], run_dir,
        prompt_path, stdout_path, stderr_path, 1,
        os.path.join(run_dir, "progress.jsonl"),
    )
    records, _ = ED._journal_read(run_dir)
    attempt_ended = [r for r in records if r.get("kind") == "attempt-ended"][-1]
    assert attempt_ended["timedOut"] is True
    assert "terminate" in events
    cap_events = [e for e in events if e.startswith("cap-")]
    assert cap_events, "expected cap events after timeout: %r" % events
    term_idx = events.index("terminate")
    first_cap_idx = events.index(cap_events[0])
    assert term_idx < first_cap_idx, "caps must run after terminate, got %r" % events


# --- WO-B (#687): production journal timing, schema refusal, payloadShape, engagement.read ---


def _findings_schema(tmp_path, content):
    path = tmp_path / "schema.json"
    path.write_text(json.dumps(content), encoding="utf-8")
    return str(path)


def test_run_engine_files_journals_wall_seconds_and_stdout_bytes(tmp_path, monkeypatch):
    """Production _run_engine_files must journal wallSeconds and stdoutBytes (not the injected seam)."""
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    payload = '{"findings":[{"id":"f1","message":"ok"}]}'
    script = (
        "import time, sys\n"
        "time.sleep(0.2)\n"
        "sys.stdout.write(%r)\n" % payload
    )
    stdout_path = os.path.join(run_dir, "attempt-1.stdout")
    stderr_path = os.path.join(run_dir, "attempt-1.stderr")
    prompt_path = os.path.join(run_dir, "prompt.txt")
    open(prompt_path, "w").write("go\n")
    ED._journal_append(run_dir, {
        "kind": "run-opened", "runKind": ED.RUN_KIND_REVIEW, "engine": "codex",
        "roleKind": ED.RUN_KIND_REVIEW, "orderId": "x",
        "argv": [sys.executable, "-c", "x"],
        "cwd": run_dir, "timeout": 30, "retryTimeout": 30,
        "promptPath": prompt_path, "viewPath": None, "baseSha": "abc",
        "supervisorPid": 1, "at": time.time(),
    })
    ED._journal_append(run_dir, {
        "kind": "engine-launching", "attempt": 1, "childPid": 1, "at": time.time(),
    })
    monkeypatch.setattr(ED, "HEARTBEAT_INTERVAL", 0.05)
    ED._run_engine_files(
        run_dir, 1, [sys.executable, "-c", script], run_dir,
        prompt_path, stdout_path, stderr_path, 30,
        os.path.join(run_dir, "progress.jsonl"),
    )
    records, _ = ED._journal_read(run_dir)
    ended = [r for r in records if r.get("kind") == "attempt-ended"][-1]
    assert ended["wallSeconds"] > 0
    assert ended["stdoutBytes"] == os.path.getsize(stdout_path)


def test_run_engine_files_spawn_failure_omits_timing_keys(tmp_path):
    """E2: spawn-failure attempt-ended records must not invent wallSeconds/stdoutBytes."""
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    stdout_path = os.path.join(run_dir, "attempt-1.stdout")
    stderr_path = os.path.join(run_dir, "attempt-1.stderr")
    prompt_path = os.path.join(run_dir, "prompt.txt")
    open(prompt_path, "w").write("go\n")
    ED._run_engine_files(
        run_dir, 1, ["/no/such/engine-binary-687"], run_dir,
        prompt_path, stdout_path, stderr_path, 30,
        os.path.join(run_dir, "progress.jsonl"),
    )
    records, _ = ED._journal_read(run_dir)
    ended = [r for r in records if r.get("kind") == "attempt-ended"][-1]
    assert "wallSeconds" not in ended
    assert "stdoutBytes" not in ended
    assert ended.get("refusal", "").startswith("spawn-failed:")


def test_run_engine_files_journal_append_failed_omits_timing_keys(tmp_path, monkeypatch):
    """E2: journal-append-failed path must not invent wallSeconds/stdoutBytes."""
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    stdout_path = os.path.join(run_dir, "attempt-1.stdout")
    stderr_path = os.path.join(run_dir, "attempt-1.stderr")
    prompt_path = os.path.join(run_dir, "prompt.txt")
    open(prompt_path, "w").write("go\n")
    real_append = ED._journal_append
    calls = {"n": 0}

    def fail_engine_started(run_dir_real, record):
        if record.get("kind") == "engine-started":
            calls["n"] += 1
            return False
        return real_append(run_dir_real, record)

    monkeypatch.setattr(ED, "_journal_append", fail_engine_started)
    ED._run_engine_files(
        run_dir, 1, [sys.executable, "-c", "print('ok')"], run_dir,
        prompt_path, stdout_path, stderr_path, 30,
        os.path.join(run_dir, "progress.jsonl"),
    )
    records, _ = ED._journal_read(run_dir)
    ended = [r for r in records if r.get("kind") == "attempt-ended"][-1]
    assert ended.get("refusal") == "journal-append-failed"
    assert "wallSeconds" not in ended
    assert "stdoutBytes" not in ended


@pytest.mark.parametrize("schema_path,detail", [
    ("missing", "schema-missing"),
    ("unreadable", "schema-unreadable"),
    ("not-findings", "schema-not-findings-shaped"),
])
def test_dispatch_review_schema_refusal_no_spawn(tmp_path, schema_path, detail):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([])
    if schema_path == "missing":
        path = str(tmp_path / "no-schema.json")
    elif schema_path == "unreadable":
        path = tmp_path / "bad.json"
        path.write_text("{not json", encoding="utf-8")
        path = str(path)
    elif schema_path == "not-findings":
        path = _findings_schema(tmp_path, {"type": "object", "properties": {"verdicts": {}}})
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root,
        schema_path=path, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["reason"] == "unrunnable"
    assert res["detail"] == detail
    assert res["attempts"] == 0
    assert len(fake.calls) == 0


def test_dispatch_review_schema_none_proceeds(tmp_path):
    """E5: schema_path=None is a no-op."""
    repo_root = _repo(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root,
        schema_path=None, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ok"] is True
    assert len(fake.calls) == 1


def test_dispatch_review_schema_whitespace_is_missing(tmp_path):
    """E6: empty/whitespace schema_path is schema-missing."""
    repo_root = _repo(tmp_path)
    fake = FakeRunner([])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root,
        schema_path="   ", run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["detail"] == "schema-missing"
    assert res["attempts"] == 0
    assert len(fake.calls) == 0


def test_dispatch_review_schema_top_level_array_refused(tmp_path):
    """E8: top-level array schema is schema-not-findings-shaped."""
    repo_root = _repo(tmp_path)
    path = _findings_schema(tmp_path, [{"type": "object"}])
    fake = FakeRunner([])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root,
        schema_path=path, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["detail"] == "schema-not-findings-shaped"
    assert len(fake.calls) == 0


def test_dispatch_review_schema_findings_not_required_refused(tmp_path):
    """E9: findings in properties but omitted from required is refused."""
    repo_root = _repo(tmp_path)
    path = _findings_schema(tmp_path, {
        "type": "object",
        "properties": {"findings": {"type": "array"}},
        "required": ["verdicts"],
    })
    fake = FakeRunner([])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root,
        schema_path=path, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["detail"] == "schema-not-findings-shaped"
    assert len(fake.calls) == 0


def test_dispatch_review_schema_minimal_object_accepted(tmp_path):
    """E10: bare {\"type\": \"object\"} is accepted."""
    repo_root = _repo(tmp_path)
    path = _findings_schema(tmp_path, {"type": "object"})
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root,
        schema_path=path, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ok"] is True
    assert len(fake.calls) == 1


def test_dispatch_review_schema_additional_properties_false_without_findings_refused(tmp_path):
    """C1: additionalProperties:false with no findings property is refused."""
    repo_root = _repo(tmp_path)
    path = _findings_schema(tmp_path, {"type": "object", "additionalProperties": False})
    fake = FakeRunner([])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root,
        schema_path=path, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["reason"] == "unrunnable"
    assert res["detail"] == ED.SCHEMA_REFUSAL_NOT_FINDINGS_SHAPED
    assert len(fake.calls) == 0


def test_dispatch_review_schema_additional_properties_object_does_not_trigger_clause(tmp_path):
    """F3: additionalProperties as a schema object does not trigger the false clause."""
    repo_root = _repo(tmp_path)
    path = _findings_schema(tmp_path, {
        "type": "object",
        "additionalProperties": {"type": "string"},
    })
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root,
        schema_path=path, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ok"] is True
    assert len(fake.calls) == 1


def test_dispatch_review_schema_padded_path_refused(tmp_path):
    """C2: a path with trailing whitespace is validated raw — padded path is schema-missing."""
    repo_root = _repo(tmp_path)
    path = _findings_schema(tmp_path, {"type": "object"})
    fake = FakeRunner([])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root,
        schema_path=path + " ", run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["detail"] == ED.SCHEMA_REFUSAL_MISSING
    assert len(fake.calls) == 0


def test_dispatch_review_schema_validated_path_matches_argv(tmp_path):
    """C2: the schema path that passes the gate is the same path in argv."""
    repo_root = _repo(tmp_path)
    path = _findings_schema(tmp_path, {"type": "object"})
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root,
        schema_path=path, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ok"] is True
    argv = res["argv"]
    schema_in_argv = argv[argv.index("--output-schema") + 1]
    assert schema_in_argv == path


def test_dispatch_review_continuation_ignores_vanished_schema_path(tmp_path):
    """C3: continuation must not refuse when a re-passed schema file has been deleted."""
    run_dir = str(tmp_path / "run")
    repo_root, _ = _manual_open_review_run(tmp_path, run_dir)
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        start_new_session=True,
    )
    ED._journal_append(run_dir, {
        "kind": "attempt-started", "attempt": 1, "childPid": proc.pid, "at": time.time(),
    })
    ED._journal_append(run_dir, {
        "kind": "engine-started", "attempt": 1, "enginePgid": proc.pid, "at": time.time(),
    })
    vanished = tmp_path / "vanished-schema.json"
    vanished.write_text(json.dumps({"type": "object"}), encoding="utf-8")
    vanished.unlink()
    build_view = _fake_build_view(tmp_path)
    try:
        res = ED.dispatch_review(
            "codex", model="sonnet", effort="high",
            prompt_path=_valid_prompt(tmp_path), repo_root=repo_root,
            schema_path=str(vanished), run_engine=FakeRunner([]),
            build_view=build_view, run_dir=run_dir,
            order_id="test-order", max_wait=1,
        )
        assert res.get("reason") != "unrunnable" or res.get("detail") not in (
            ED.SCHEMA_REFUSAL_MISSING,
            ED.SCHEMA_REFUSAL_UNREADABLE,
            ED.SCHEMA_REFUSAL_NOT_FINDINGS_SHAPED,
        )
    finally:
        ED._terminate_process_group(proc.pid)
        proc.wait(timeout=2)


def test_run_engine_files_stdout_bytes_is_pre_cap_size(tmp_path, monkeypatch):
    """F: journalled stdoutBytes must be the pre-cap size, not the capped file size."""
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    tail_json = json.dumps({"findings": [{"id": "f1", "message": "ok"}]})
    over = ED.MAX_STDOUT_CAPTURE + 4096
    script = (
        "import sys\n"
        "sys.stdout.write('x' * %d + %r)\n" % (over, tail_json)
    )
    stdout_path = os.path.join(run_dir, "attempt-1.stdout")
    stderr_path = os.path.join(run_dir, "attempt-1.stderr")
    prompt_path = os.path.join(run_dir, "prompt.txt")
    open(prompt_path, "w").write("go\n")
    monkeypatch.setattr(ED, "MAX_STDOUT_CAPTURE", 8192)
    ED._journal_append(run_dir, {
        "kind": "run-opened", "runKind": ED.RUN_KIND_REVIEW, "engine": "codex",
        "roleKind": ED.RUN_KIND_REVIEW, "orderId": "x",
        "argv": [sys.executable, "-c", "x"],
        "cwd": run_dir, "timeout": 30, "retryTimeout": 30,
        "promptPath": prompt_path, "viewPath": None, "baseSha": "abc",
        "supervisorPid": 1, "at": time.time(),
    })
    ED._journal_append(run_dir, {
        "kind": "engine-launching", "attempt": 1, "childPid": 1, "at": time.time(),
    })
    ED._run_engine_files(
        run_dir, 1, [sys.executable, "-c", script], run_dir,
        prompt_path, stdout_path, stderr_path, 30,
        os.path.join(run_dir, "progress.jsonl"),
    )
    capped_size = os.path.getsize(stdout_path)
    assert capped_size <= 8192
    records, _ = ED._journal_read(run_dir)
    ended = [r for r in records if r.get("kind") == "attempt-ended"][-1]
    assert ended["stdoutBytes"] > capped_size


def test_dispatch_review_payload_shape_on_unreadable_forfeit(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([
        ('{"verdicts":[]}', False, 0, ""),
        ('{"verdicts":[]}', False, 0, ""),
    ])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["forfeited"] is True
    assert res["reason"] == "forfeited"
    shape = res["payloadShape"]
    assert shape["parsed"] == ED.engine_adapter.SHAPE_OBJECT_WITHOUT_FINDINGS
    assert shape["topLevelKeys"] == ["verdicts"]


def test_dispatch_review_payload_shape_absent_on_vacuous_forfeit(tmp_path):
    repo_root = _repo(tmp_path)
    empty = json.dumps({"findings": []})
    fake = FakeRunner([(empty, False, 0, ""), (empty, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["reason"] == "vacuous"
    assert "payloadShape" not in res


def test_dispatch_review_payload_shape_absent_on_success(tmp_path, monkeypatch):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    monkeypatch.setattr(ED.engine_adapter, "review_payload_shape", lambda _stdout: {"parsed": "x"})
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ok"] is True
    assert "payloadShape" not in res


def test_dispatch_review_engagement_read_on_success(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["engagement"]["read"] == "engaged"


def test_dispatch_review_engagement_read_on_forfeit(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([("not json", False, 0, ""), ("not json", False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["forfeited"] is True
    assert res["engagement"]["read"] == "unknown"


def test_dispatch_review_timeout_forfeit_has_no_engagement(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([("", True, 0, ""), ("", True, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["forfeited"] is True
    assert res.get("engagement") is None


def test_dispatch_review_nonzero_exit_forfeit_has_no_engagement(tmp_path):
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
    assert res.get("engagement") is None


def test_grade_review_attempt_prompt_echo_payload_shape_prompt_echo_only(tmp_path):
    """Prompt-echo-only stdout (echo contains findings contract) yields prompt-echo-only."""
    run_dir = str(tmp_path / "run")
    repo_root = _repo(tmp_path)
    prompt_body = (
        "Review this code.\n"
        "Respond with JSON: {\"findings\": []}\n"
    )
    fed = _fed_prompt(prompt_body)
    os.makedirs(run_dir, exist_ok=True)
    stdout_path = os.path.join(run_dir, "attempt-1.stdout")
    with open(stdout_path, "w", encoding="utf-8") as fh:
        fh.write(fed)
    state = {
        "opened": {
            "engine": "codex",
            "roleKind": ED.RUN_KIND_REVIEW,
            "cwd": repo_root,
            "fedPrompt": fed,
        },
        "attempts": {
            1: {
                "ended": {
                    "exit": 0, "timedOut": False, "refusal": None,
                    "stdoutBytes": len(fed), "wallSeconds": 1.0,
                },
            },
        },
    }
    grade = ED._grade_review_attempt(run_dir, state, 1)
    assert grade.get("forfeit") is True
    shape = grade.get("payloadShape")
    assert shape is not None
    assert shape["parsed"] == ED.engine_adapter.SHAPE_PROMPT_ECHO_ONLY


def test_grade_review_attempt_empty_stdout_payload_shape_empty_stdout(tmp_path):
    """Genuinely empty raw stdout still yields empty-stdout."""
    run_dir = str(tmp_path / "run")
    repo_root = _repo(tmp_path)
    fed = _fed_prompt("Review this code.\n")
    os.makedirs(run_dir, exist_ok=True)
    stdout_path = os.path.join(run_dir, "attempt-1.stdout")
    with open(stdout_path, "w", encoding="utf-8") as fh:
        fh.write("   \n\t")
    state = {
        "opened": {
            "engine": "codex",
            "roleKind": ED.RUN_KIND_REVIEW,
            "cwd": repo_root,
            "fedPrompt": fed,
        },
        "attempts": {
            1: {
                "ended": {
                    "exit": 0, "timedOut": False, "refusal": None,
                    "stdoutBytes": 4, "wallSeconds": 1.0,
                },
            },
        },
    }
    grade = ED._grade_review_attempt(run_dir, state, 1)
    assert grade.get("forfeit") is True
    shape = grade.get("payloadShape")
    assert shape is not None
    assert shape["parsed"] == ED.engine_adapter.SHAPE_EMPTY_STDOUT


# --- WO-2 (#747): per-attempt telemetry + terminal-record supersede (PR #783) ---


def _wo2_open_run(run_dir, prompt_path, **opened_overrides):
    opened = {
        "kind": "run-opened", "runKind": ED.RUN_KIND_REVIEW, "engine": "codex",
        "roleKind": ED.RUN_KIND_REVIEW, "orderId": "wo2",
        "argv": [sys.executable, "-c", "x"],
        "cwd": run_dir, "timeout": 30, "retryTimeout": 30,
        "promptPath": prompt_path, "viewPath": None, "baseSha": "abc",
        "supervisorPid": 1, "at": time.time(),
    }
    opened.update(opened_overrides)
    ED._journal_append(run_dir, opened)
    ED._journal_append(run_dir, {
        "kind": "engine-launching", "attempt": 1, "childPid": 1,
        "argv": opened["argv"], "at": time.time(),
    })


def _wo2_run_engine(run_dir, script, timeout=30, heartbeat=None, monkeypatch=None):
    stdout_path = os.path.join(run_dir, "attempt-1.stdout")
    stderr_path = os.path.join(run_dir, "attempt-1.stderr")
    prompt_path = os.path.join(run_dir, "prompt.txt")
    open(prompt_path, "w").write("go\n")
    _wo2_open_run(run_dir, prompt_path)
    if monkeypatch is not None and heartbeat is not None:
        monkeypatch.setattr(ED, "HEARTBEAT_INTERVAL", heartbeat)
    ED._run_engine_files(
        run_dir, 1, [sys.executable, "-c", script], run_dir,
        prompt_path, stdout_path, stderr_path, timeout,
        os.path.join(run_dir, "progress.jsonl"),
    )
    records, _ = ED._journal_read(run_dir)
    ended = [r for r in records if r.get("kind") == "attempt-ended"][-1]
    return ended, stdout_path, stderr_path


def test_run_engine_files_telemetry_stdout_activity(tmp_path, monkeypatch):
    """axis: which stream is observed for activity sampling (stdout participation)."""
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    script = (
        "import sys, time\n"
        "sys.stdout.write('a')\n"
        "sys.stdout.flush()\n"
        "time.sleep(0.12)\n"
        "sys.stdout.write('b')\n"
    )
    ended, _, _ = _wo2_run_engine(run_dir, script, monkeypatch=monkeypatch, heartbeat=0.05)
    assert ended["exit"] == 0
    assert ended.get("signal") is None
    assert ended.get("signalSource") is None
    assert ended.get("activityStream") == "stdout"
    assert ended.get("silenceSeconds") is not None
    assert ended["silenceSeconds"] < 0.5


def test_run_engine_files_telemetry_stderr_activity(tmp_path, monkeypatch):
    """axis: which stream is observed for activity sampling (stderr participation)."""
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    script = "import sys\nsys.stderr.write('codex-progress')\n"
    ended, _, stderr_path = _wo2_run_engine(run_dir, script, monkeypatch=monkeypatch)
    assert ended.get("activityStream") == "stderr"
    assert ended.get("stderrBytes", 0) > 0
    assert os.path.getsize(stderr_path) > 0


def test_run_engine_files_telemetry_sigkill(tmp_path, monkeypatch):
    """axis: attribution of kill (engine-side signal death vs runner timeout)."""
    import signal
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    script = (
        "import os, signal\n"
        "os.kill(os.getpid(), signal.SIGKILL)\n"
    )
    ended, _, _ = _wo2_run_engine(run_dir, script, monkeypatch=monkeypatch, heartbeat=0.05)
    assert ended["exit"] < 0
    assert ended.get("signal") == signal.SIGKILL
    assert ended.get("signalSource") == "engine"


def test_run_engine_files_telemetry_timeout(tmp_path, monkeypatch):
    """axis: attribution of kill (runner-timeout on cap)."""
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    script = "import time\ntime.sleep(2)\n"
    ended, _, _ = _wo2_run_engine(
        run_dir, script, timeout=0.15, heartbeat=0.05, monkeypatch=monkeypatch,
    )
    assert ended.get("timedOut") is True
    assert ended.get("capSeconds") == 0.15
    assert ended.get("signalSource") == "runner-timeout"


def test_run_engine_files_telemetry_answer_at_exit_stdout(tmp_path, monkeypatch):
    """axis: timing accuracy of silenceSeconds (post-exit final sample, stdout)."""
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    monkeypatch.setattr(ED, "HEARTBEAT_INTERVAL", 0.5)
    script = "import sys\nsys.stdout.write('final')\n"
    ended, _, _ = _wo2_run_engine(run_dir, script, monkeypatch=monkeypatch)
    assert ended.get("silenceSeconds") is not None
    assert ended["silenceSeconds"] < 0.25


def test_run_engine_files_telemetry_answer_at_exit_stderr(tmp_path, monkeypatch):
    """axis: timing accuracy of silenceSeconds (post-exit final sample, stderr)."""
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    monkeypatch.setattr(ED, "HEARTBEAT_INTERVAL", 0.5)
    script = "import sys\nsys.stderr.write('final')\n"
    ended, _, _ = _wo2_run_engine(run_dir, script, monkeypatch=monkeypatch)
    assert ended.get("silenceSeconds") is not None
    assert ended["silenceSeconds"] < 0.25


def test_journal_state_real_attempt_ended_wins_over_synthetic_second():
    """axis: which attempt-ended record wins (real over synthetic, not mere presence)."""
    records = [
        {"kind": "attempt-ended", "attempt": 1, "exit": 0, "refusal": None, "at": 1.0},
        {"kind": "attempt-ended", "attempt": 1, "refusal": "attempt-died-unrecorded", "at": 2.0},
    ]
    state = ED._journal_state(records)
    slot = state["attempts"][1]
    assert slot["ended"]["exit"] == 0
    assert slot["endedSuperseded"]["refusal"] == "attempt-died-unrecorded"


def test_journal_state_real_attempt_ended_wins_over_synthetic_first():
    """axis: which attempt-ended record wins (real over synthetic when real arrives second)."""
    records = [
        {"kind": "attempt-ended", "attempt": 1, "refusal": "attempt-died-unrecorded", "at": 1.0},
        {"kind": "attempt-ended", "attempt": 1, "exit": 0, "refusal": None, "at": 2.0},
    ]
    state = ED._journal_state(records)
    slot = state["attempts"][1]
    assert slot["ended"]["exit"] == 0
    assert slot["endedSuperseded"]["refusal"] == "attempt-died-unrecorded"


def test_journal_state_two_real_attempt_ended_first_wins():
    """axis: which attempt-ended record wins (first real when both are real)."""
    records = [
        {"kind": "attempt-ended", "attempt": 1, "exit": 0, "refusal": None, "at": 1.0},
        {"kind": "attempt-ended", "attempt": 1, "exit": 1, "refusal": None, "at": 2.0},
    ]
    state = ED._journal_state(records)
    slot = state["attempts"][1]
    assert slot["ended"]["exit"] == 0
    assert slot["endedSuperseded"]["exit"] == 1


def test_journal_state_legacy_attempt_ended_keys_grade_unchanged(tmp_path):
    """axis: no-raise on 0.23.0-era attempt-ended keys during fold and grade."""
    run_dir = str(tmp_path / "run")
    repo_root = _repo(tmp_path)
    os.makedirs(run_dir)
    stdout_path = os.path.join(run_dir, "attempt-1.stdout")
    with open(stdout_path, "w", encoding="utf-8") as fh:
        fh.write(_VALID_FINDINGS_STDOUT)
    records = [
        {
            "kind": "run-opened", "runKind": ED.RUN_KIND_REVIEW, "engine": "codex",
            "roleKind": ED.RUN_KIND_REVIEW, "orderId": "legacy",
            "argv": [sys.executable, "-c", "x"], "cwd": repo_root,
            "timeout": 30, "retryTimeout": 30,
            "promptPath": os.path.join(run_dir, "prompt.txt"),
            "baseSha": "abc", "supervisorPid": 1, "at": time.time(),
        },
        {
            "kind": "attempt-ended", "attempt": 1,
            "exit": 0, "timedOut": False, "signal": None, "refusal": None,
            "at": time.time(),
        },
    ]
    state = ED._journal_state(records)
    grade = ED._grade_review_attempt(run_dir, state, 1)
    assert grade.get("ok") is True


# --- #747 WO-4b: forfeit-with-engaged-artifact + ledger wiring ---

_DO = importlib.util.spec_from_file_location(
    "dispatch_outcome", os.path.join(_HERE, "..", "dispatch_outcome.py"))
_DO_MOD = importlib.util.module_from_spec(_DO)
_DO.loader.exec_module(_DO_MOD)

_FL = importlib.util.spec_from_file_location(
    "forfeit_ledger", os.path.join(_HERE, "..", "forfeit_ledger.py"))
_FL_MOD = importlib.util.module_from_spec(_FL)
_FL.loader.exec_module(_FL_MOD)

_LL = importlib.util.spec_from_file_location(
    "launch_ledger", os.path.join(_HERE, "..", "launch_ledger.py"))
_LL_MOD = importlib.util.module_from_spec(_LL)
_LL.loader.exec_module(_LL_MOD)

_EA_WO4B = importlib.util.spec_from_file_location(
    "engine_adapter", os.path.join(_HERE, "..", "engine_adapter.py"))
_EA_WO4B_MOD = importlib.util.module_from_spec(_EA_WO4B)
_EA_WO4B.loader.exec_module(_EA_WO4B_MOD)


def _ledger_env(tmp_path, monkeypatch):
    root = str(tmp_path / "forfeit-ledger-root")
    os.makedirs(root, mode=0o700, exist_ok=True)
    monkeypatch.setenv(_FL_MOD.LEDGER_ROOT_ENV, root)
    return root


def _manual_open_review_run_git(tmp_path, run_dir, repo_root):
    build_view = _fake_build_view(tmp_path)
    view = build_view(os.path.realpath(repo_root))
    cwd = os.path.realpath(view["path"])
    built = __import__("engine_adapter").build_argv_result(
        "codex", "review", "high", {"model": "sonnet", "cwd": cwd},
    )
    argv = built["argv"]
    prompt_path = _valid_prompt(tmp_path)
    with open(prompt_path, encoding="utf-8") as fh:
        base = fh.read()
    fed = ED.ANTIHIJACK_PREAMBLE + _SV_MOD.sanitized_view_notice(view) + base
    os.makedirs(run_dir, exist_ok=True)
    ok, detail = ED._open_review_run(
        run_dir, engine="codex", argv=argv, cwd=cwd,
        timeout=ED.RETRY_MIN_TIMEOUT, retry_timeout=ED.RETRY_MIN_TIMEOUT,
        prompt_path=prompt_path, view_path=view["path"], view_meta=view,
        fed_prompt=fed, order_id="test-order", progress_path=os.path.join(run_dir, "progress.jsonl"),
        repo_root=os.path.realpath(repo_root),
    )
    assert ok, detail
    return repo_root, view


def _artifact_pad(text):
    out = text
    while len(out.encode("utf-8")) < _EA_WO4B_MOD.ARTIFACT_MIN_RESIDUE_BYTES + 20:
        out += " Additional review context padding."
    return out


def _poster_child_attempt1_stdout():
    cites = [
        "src/app/widget.ts:42", "src/lib/util.ts:7", "src/app/model.ts:15",
        "tests/widget.test.ts:88", "src/app/view.ts:3",
    ]
    lines = ["Review of the widget module identified several concerns."]
    lines += ["- %s: null check missing" % c for c in cites[:3]]
    lines += ["Also noted %s and %s in related files." % (cites[3], cites[4])]
    return _artifact_pad("\n".join(lines))


def test_poster_child_engaged_artifact_forfeit_plain_path(tmp_path):
    """axis: which outcome is minted — poster-child regression (attempt-1 engaged, attempt-2 unreadable)."""
    repo_root = _git_init(str(tmp_path / "repo"))
    prose = _poster_child_attempt1_stdout()
    fake = FakeRunner([
        (prose, True, 0, ""),
        ("short echo only", False, 0, ""),
    ])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ok"] is False
    assert res["forfeited"] is True
    assert res["reason"] == _DO_MOD.REASON_FORFEIT_ENGAGED_ARTIFACT
    assert res["salvage"]["attempt"] == 1
    assert "findings" not in res
    assert "not credited" in res["disclosure"].lower()
    assert "independently verified" in res["disclosure"].lower()


def test_engaged_artifact_forfeit_from_vacuous_path(tmp_path):
    """axis: which outcome is minted — vacuous terminal upgraded when earlier attempt engaged."""
    repo_root = _git_init(str(tmp_path / "repo-vac"))
    prose = _poster_child_attempt1_stdout()
    empty = json.dumps({"findings": []})
    fake = FakeRunner([
        (prose, False, 0, ""),
        (empty, False, 0, ""),
    ])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["reason"] == _DO_MOD.REASON_FORFEIT_ENGAGED_ARTIFACT
    assert res["salvage"]["attempt"] == 1


def test_forfeit_without_engaged_artifact_unchanged(tmp_path):
    repo_root = _git_init(str(tmp_path / "repo-plain"))
    fake = FakeRunner([("", True, 0, ""), ("echo", False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["reason"] == _DO_MOD.REASON_FORFEITED
    assert "salvage" not in res


def test_fold_ledger_forfeited_transport_class(tmp_path, monkeypatch):
    repo_root = _git_init(str(tmp_path / "repo-ledger"))
    _ledger_env(tmp_path, monkeypatch)
    prose = _poster_child_attempt1_stdout()
    fake = FakeRunner([
        (prose, False, 0, ""),
        ('{"verdicts":[]}', False, 0, ""),
    ])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ledger"]["written"] is True
    rows, _ = _FL_MOD.read(repo_root)
    assert len(rows) == 1
    assert rows[0]["attribution"]["class"] == _DO_MOD.ATTRIBUTION_TRANSPORT


def test_fold_ledger_success_thin_row(tmp_path, monkeypatch):
    repo_root = _git_init(str(tmp_path / "repo-success"))
    _ledger_env(tmp_path, monkeypatch)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["ok"] is True
    assert res["ledger"]["written"] is True
    rows, _ = _FL_MOD.read(repo_root)
    assert len(rows) == 1
    assert rows[0]["ok"] is True
    thin = rows[0]["attempts"][0]
    assert thin["attempt"] == 1
    assert thin["exit"] == 0
    assert thin["timedOut"] is False
    assert "wallSeconds" not in thin


def test_fold_ledger_idempotent_per_run_id(tmp_path, monkeypatch):
    run_dir = str(tmp_path / "run-idem")
    repo_root = _git_init(str(tmp_path / "repo-idem"))
    _ledger_env(tmp_path, monkeypatch)
    _manual_open_review_run_git(tmp_path, run_dir, repo_root)
    records, _ = ED._journal_read(run_dir)
    state = ED._journal_state(records)
    result = {
        "ok": True, "terminal": True, "attempts": 1,
        "findings": [{"id": "f1", "message": "x"}],
        "engagement": {"read": "engaged"},
    }
    ED._append_fold_ledger(run_dir, state, result)
    ED._append_fold_ledger(run_dir, state, result)
    rows, _ = _FL_MOD.read(repo_root)
    assert len(rows) == 1


def test_fold_ledger_no_repo_root_written_false(tmp_path, monkeypatch):
    run_dir = str(tmp_path / "run-noroot")
    _ledger_env(tmp_path, monkeypatch)
    os.makedirs(run_dir, exist_ok=True)
    ED._journal_append(run_dir, {
        "kind": "run-opened", "runKind": ED.RUN_KIND_REVIEW, "engine": "codex",
        "roleKind": ED.RUN_KIND_REVIEW, "orderId": "x",
        "argv": [], "cwd": run_dir, "timeout": 30, "retryTimeout": 30,
        "promptPath": os.path.join(run_dir, "prompt.txt"),
        "supervisorPid": 1, "at": time.time(),
    })
    records, _ = ED._journal_read(run_dir)
    state = ED._journal_state(records)
    result = {"ok": False, "terminal": True, "reason": "forfeited", "forfeited": True, "attempts": 0}
    receipt = ED._append_fold_ledger(run_dir, state, result)
    assert receipt["written"] is False
    assert receipt["why"] == "repo-root-absent-from-run-opened"


def test_fold_ledger_append_failure_fail_soft(tmp_path, monkeypatch):
    repo_root = _git_init(str(tmp_path / "repo-failsoft"))
    _ledger_env(tmp_path, monkeypatch)
    prose = _poster_child_attempt1_stdout()
    fake = FakeRunner([
        (prose, True, 0, ""),
        ("short", False, 0, ""),
    ])

    def boom(*_a, **_k):
        raise RuntimeError("ledger-boom")

    monkeypatch.setattr(ED.forfeit_ledger, "append", boom)
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["reason"] == _DO_MOD.REASON_FORFEIT_ENGAGED_ARTIFACT
    assert res["ledger"]["written"] is False
    assert res["ledger"]["why"] == "ledger-internal-error"


def test_preflight_unrunnable_appends_ledger_caller_error(tmp_path, monkeypatch):
    """axis: which entry points append — review pre-spawn refusals with repo identity."""
    repo_root = _git_init(str(tmp_path / "repo-preflight"))
    _ledger_env(tmp_path, monkeypatch)
    missing_prompt = str(tmp_path / "missing-prompt.txt")
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=missing_prompt, repo_root=repo_root, run_engine=_never_call,
        build_view=_fake_build_view(tmp_path),
    )
    assert res["reason"] == "unrunnable"
    assert res["detail"] == "prompt-missing"
    assert res["attempts"] == 0
    assert res["ledger"]["written"] is True
    rows, _ = _FL_MOD.read(repo_root)
    assert len(rows) == 1
    assert rows[0]["attribution"]["class"] == _DO_MOD.ATTRIBUTION_CALLER_ERROR


def test_abandon_appends_ledger_row(tmp_path, monkeypatch):
    """axis: which terminal paths append — run-abandoned with repo identity."""
    repo_root = _git_init(str(tmp_path / "repo-abandon"))
    _ledger_env(tmp_path, monkeypatch)
    run_dir = str(tmp_path / "run-abandon")
    _manual_open_review_run_git(tmp_path, run_dir, repo_root)
    res = ED.dispatch_abandon(run_dir)
    assert res["detail"] == "run-abandoned"
    assert res["ledger"]["written"] is True
    rows, _ = _FL_MOD.read(repo_root)
    assert len(rows) == 1
    assert rows[0]["reason"] == "unrunnable"
    assert rows[0]["detail"] == "run-abandoned"


def test_dispatch_abandon_idempotent_equal_results(tmp_path, monkeypatch):
    """axis: that repeat reads return the stored result — not a fresh ledger append."""
    repo_root = _git_init(str(tmp_path / "repo-abandon-idem"))
    _ledger_env(tmp_path, monkeypatch)
    run_dir = str(tmp_path / "run-abandon-idem")
    _manual_open_review_run_git(tmp_path, run_dir, repo_root)
    first = ED.dispatch_abandon(run_dir)
    second = ED.dispatch_abandon(run_dir)
    assert second == first


def test_preflight_run_id_namespaced_from_run_dir_dedupe_key(tmp_path, monkeypatch):
    """axis: that a preflight row cannot take a real run's dedupe key — collision, not presence."""
    repo_root = _git_init(str(tmp_path / "repo-preflight-id"))
    _ledger_env(tmp_path, monkeypatch)
    run_dir = str(tmp_path / "run-preflight-id")
    os.makedirs(run_dir, exist_ok=True)
    _manual_open_review_run_git(tmp_path, run_dir, repo_root)
    wrong_order = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=_never_call,
        build_view=_fake_build_view(tmp_path), run_dir=run_dir, order_id="wrong-order",
    )
    assert wrong_order["detail"] == "run-dir-reused"
    assert wrong_order["ledger"]["written"] is True
    rows, _ = _FL_MOD.read(repo_root)
    preflight_row = rows[-1]
    real_run_id = _FL_MOD.run_id_from_run_dir(run_dir)
    assert preflight_row["runId"] != real_run_id
    assert preflight_row["runId"].startswith("preflight-")


def test_dispatch_abandon_idempotent_after_failed_ledger_append(tmp_path, monkeypatch):
    """axis: that repeat reads return the stored result even when ledger state changed."""
    repo_root = _git_init(str(tmp_path / "repo-abandon-fail"))
    _ledger_env(tmp_path, monkeypatch)
    run_dir = str(tmp_path / "run-abandon-fail")
    _manual_open_review_run_git(tmp_path, run_dir, repo_root)
    calls = {"n": 0}
    real_append = _FL_MOD.append

    def flaky_append(repo_root_arg, row):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"written": False, "path": None, "why": "ledger-lock-busy"}
        return real_append(repo_root_arg, row)

    monkeypatch.setattr(ED.forfeit_ledger, "append", flaky_append)
    first = ED.dispatch_abandon(run_dir)
    assert first["ledger"]["written"] is False
    second = ED.dispatch_abandon(run_dir)
    assert second == first
    assert calls["n"] == 1


def test_write_preflight_unrunnable_appends_ledger_caller_error(tmp_path, monkeypatch):
    """axis: which entry points append — write pre-spawn refusals with repo identity."""
    wt = _linked_worktree(tmp_path)
    _ledger_env(tmp_path, monkeypatch)
    missing_prompt = str(tmp_path / "missing-write-prompt.txt")
    res = ED.dispatch_write(
        "codex", model="sonnet", effort="high",
        prompt_path=missing_prompt, cwd=wt,
        run_dir=str(tmp_path / "run-write-preflight"), order_id="inv-write",
        run_engine=_never_call,
    )
    assert res["reason"] == "unrunnable"
    assert res["detail"] == "prompt-missing"
    assert res["ledger"]["written"] is True
    repo_root = ED._repository_root_from_git_cwd(wt)
    rows, _ = _FL_MOD.read(repo_root)
    assert len(rows) == 1
    assert rows[0]["attribution"]["class"] == _DO_MOD.ATTRIBUTION_CALLER_ERROR
    assert rows[0]["runKind"] == ED.RUN_KIND_WRITE


def test_write_preflight_primary_checkout_ledgers_refusal(tmp_path, monkeypatch):
    """axis: which entry points append — cwd-validation refusals with repo identity."""
    main = _git_init(str(tmp_path / "main-primary"))
    _ledger_env(tmp_path, monkeypatch)
    res = ED.dispatch_write(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), cwd=main,
        run_dir=str(tmp_path / "run-write-primary"), order_id="inv-primary",
        run_engine=_never_call,
    )
    assert res["detail"] == "cwd-primary-checkout"
    assert res["ledger"]["written"] is True
    rows, _ = _FL_MOD.read(os.path.realpath(main))
    assert len(rows) == 1
    assert rows[0]["attribution"]["class"] == _DO_MOD.ATTRIBUTION_CALLER_ERROR
    assert rows[0]["runKind"] == ED.RUN_KIND_WRITE


def test_write_preflight_non_repo_stays_unledgered(tmp_path, monkeypatch):
    """axis: which entry points append — no repo identity means no ledger row."""
    _ledger_env(tmp_path, monkeypatch)
    non_repo = str(tmp_path / "not-a-repo")
    os.makedirs(non_repo)
    res = ED.dispatch_write(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), cwd=non_repo,
        run_dir=str(tmp_path / "run-write-nonrepo"), order_id="inv-nonrepo",
        run_engine=_never_call,
    )
    assert res["detail"] == "cwd-not-a-repo"
    assert "ledger" not in res


def test_run_opened_records_repo_root_and_id(tmp_path):
    run_dir = str(tmp_path / "run-meta")
    repo_root = _git_init(str(tmp_path / "repo-opened"))
    _manual_open_review_run_git(tmp_path, run_dir, repo_root)
    records, _ = ED._journal_read(run_dir)
    opened = next(r for r in records if r.get("kind") == "run-opened")
    assert opened["repoRoot"] == os.path.realpath(repo_root)
    assert opened["repoId"] == _LL_MOD.repo_identity(opened["repoRoot"])


# --- WO B: diff_base threading + investigation-floor artifact hole ---------------


def _capture_build_view(tmp_path, *, diff_keys=None):
    inner = _fake_build_view(tmp_path)
    captured = {"kwargs": []}

    def build_view(repo_real, *, diff_base=None):
        captured["kwargs"].append({"repo": repo_real, "diff_base": diff_base})
        view = inner(repo_real)
        if diff_keys:
            view.update(diff_keys)
        elif diff_base is not None:
            view.update({
                "diffBase": "a" * 40,
                "diffPath": "SUPERHEROES_REVIEW_DIFF.patch",
                "diffBytes": 42,
                "diffWithheldCount": 0,
            })
        return view

    build_view.captured = captured
    build_view.meta = inner.meta
    return build_view


def test_dispatch_review_diff_base_omitted_reaches_build_view(tmp_path):
    """E1: --diff-base omitted → diff_base=None; receipt diff keys are None."""
    repo_root = _repo(tmp_path)
    build_view = _capture_build_view(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=build_view,
    )
    assert build_view.captured["kwargs"][0]["diff_base"] is None
    assert res["sanitizedView"]["diffBase"] is None
    assert res["sanitizedView"]["diffPath"] is None
    assert res["sanitizedView"]["diffBytes"] is None
    assert res["sanitizedView"]["diffWithheldCount"] is None


def test_dispatch_review_diff_base_forwarded_to_build_view(tmp_path):
    repo_root = _repo(tmp_path)
    build_view = _capture_build_view(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
        build_view=build_view, diff_base="origin/main",
    )
    assert build_view.captured["kwargs"][0]["diff_base"] == "origin/main"
    assert res["sanitizedView"]["diffPath"] == "SUPERHEROES_REVIEW_DIFF.patch"
    assert res["sanitizedView"]["diffBytes"] == 42


def test_sanitized_view_receipt_forwards_diff_keys_with_get():
    """E2: old view dict without diff keys yields None in the receipt."""
    old_shape = {
        "strategy": "git-archive-export",
        "stripped": [],
        "strippedCount": 0,
        "headSha": "abc",
        "sourceDirty": False,
        "buildSeconds": 0.1,
        "bytes": 9,
        "fileCount": 2,
    }
    receipt = ED._sanitized_view_receipt(old_shape)
    assert receipt["diffBase"] is None
    assert receipt["diffPath"] is None
    assert receipt["diffBytes"] is None
    assert receipt["diffWithheldCount"] is None

    full = dict(old_shape, diffBase="b" * 40, diffPath="SUPERHEROES_REVIEW_DIFF.patch",
                diffBytes=99, diffWithheldCount=1)
    receipt = ED._sanitized_view_receipt(full)
    assert receipt["diffBase"] == "b" * 40
    assert receipt["diffPath"] == "SUPERHEROES_REVIEW_DIFF.patch"
    assert receipt["diffBytes"] == 99
    assert receipt["diffWithheldCount"] == 1


def test_review_continuation_ignores_diff_base(tmp_path):
    """E14: continuation does not rebuild the view for a differing diff_base."""
    run_dir = str(tmp_path / "run")
    repo_root, _ = _manual_open_review_run(tmp_path, run_dir)
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        start_new_session=True,
    )
    ED._journal_append(run_dir, {
        "kind": "attempt-started", "attempt": 1, "childPid": proc.pid, "at": time.time(),
    })
    ED._journal_append(run_dir, {
        "kind": "engine-started", "attempt": 1, "enginePgid": proc.pid, "at": time.time(),
    })
    build_view = _capture_build_view(tmp_path)
    try:
        ED.dispatch_review(
            "codex", model="sonnet", effort="high",
            prompt_path=_valid_prompt(tmp_path), repo_root=repo_root,
            run_engine=FakeRunner([]), build_view=build_view, run_dir=run_dir,
            order_id="test-order", max_wait=1, diff_base="other-ref",
        )
        assert build_view.meta["build_count"] == 0
        assert build_view.captured["kwargs"] == []
    finally:
        ED._terminate_process_group(proc.pid)
        proc.wait(timeout=2)


def _grade_state_with_view_meta(tmp_path, view_meta, *, omit_view_meta=False, run_name="run"):
    run_dir = str(tmp_path / run_name)
    repo_root, view = _manual_open_review_run(tmp_path, run_dir)
    records, _ = ED._journal_read(run_dir)
    for rec in records:
        if rec.get("kind") == "run-opened":
            if omit_view_meta:
                rec.pop("viewMeta", None)
            else:
                rec["viewMeta"] = view_meta
    path = ED._journal_path(run_dir)
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
    stdout = json.dumps({"findings": [], "investigated": ["SUPERHEROES_REVIEW_DIFF.patch"]})
    with open(os.path.join(run_dir, "attempt-1.stdout"), "w", encoding="utf-8") as fh:
        fh.write(stdout)
    with open(os.path.join(run_dir, "attempt-1.stderr"), "w", encoding="utf-8") as fh:
        fh.write("")
    ED._journal_append(run_dir, {
        "kind": "attempt-started", "attempt": 1, "childPid": 1, "at": time.time(),
    })
    ED._journal_append(run_dir, {
        "kind": "attempt-ended", "attempt": 1,
        "exit": 0, "timedOut": False, "signal": None,
        "refusal": None, "at": time.time(), "wallSeconds": 1.0, "stdoutBytes": len(stdout),
    })
    records, _ = ED._journal_read(run_dir)
    state = ED._journal_state(records)
    patch_path = os.path.join(view["path"], "SUPERHEROES_REVIEW_DIFF.patch")
    with open(patch_path, "w", encoding="utf-8") as fh:
        fh.write("diff\n")
    return run_dir, state


def test_grade_review_view_meta_absent_or_none_passes_empty_artifacts(tmp_path):
    """E15: missing viewMeta does not pass a generated artifact to the floor."""
    run_dir, state = _grade_state_with_view_meta(tmp_path, None)
    grade = ED._grade_review_attempt(run_dir, state, 1)
    assert grade.get("ok") is True
    assert grade.get("investigated") == ["SUPERHEROES_REVIEW_DIFF.patch"]

    run_dir2, state2 = _grade_state_with_view_meta(
        tmp_path, None, omit_view_meta=True, run_name="run2")
    grade2 = ED._grade_review_attempt(run_dir2, state2, 1)
    assert grade2.get("ok") is True
    assert grade2.get("investigated") == ["SUPERHEROES_REVIEW_DIFF.patch"]


def test_grade_review_view_meta_diff_path_rejects_patch_only_investigation(tmp_path):
    run_dir, state = _grade_state_with_view_meta(
        tmp_path,
        {"diffPath": "SUPERHEROES_REVIEW_DIFF.patch", "headSha": "abc"},
    )
    grade = ED._grade_review_attempt(run_dir, state, 1)
    assert grade.get("forfeit") is True
    assert grade.get("reason") == ED.engine_adapter.REVIEW_FORFEIT_VACUOUS
    assert "generated-artifact" in grade.get("investigatedRejected", [])


def test_main_dispatch_review_diff_base_cli_wiring(tmp_path, monkeypatch, capsys):
    captured = {}

    def _capture_dispatch(*_args, **kwargs):
        captured.update(kwargs)
        return {
            "ok": False, "reason": "unrunnable", "detail": "repo-root-absent",
            "attempts": 0, "forfeited": False, "terminal": True, "runDir": "", "argv": [],
        }

    monkeypatch.setattr(ED, "dispatch_review", _capture_dispatch)
    prompt = _valid_prompt(tmp_path)
    repo_root = _repo(tmp_path)
    rc = ED.main([
        "dispatch-review",
        "--engine", "codex",
        "--effort", "high",
        "--prompt-path", prompt,
        "--repo-root", repo_root,
        "--diff-base", "REF",
    ])
    assert rc == 0
    json.loads(capsys.readouterr().out.strip())
    assert captured.get("diff_base") == "REF"


# --- #862: --max-wait is honored as asked or refused by name — never clamped ----
# axis: refusal vs clamp on the slice bound — an in-range value reaches the supervisor
# unshortened, an out-of-range one is a terminal refusal and never a non-terminal `running`.
# The run.lock tests at the end of this block bite on the call site passing the dead-holder
# opt-in (axis: reclaim licensed by holder death, not TTL).


def _running_slice_capture(monkeypatch):
    """Capture the slice length dispatch_* hands the supervisor, without supervising."""
    seen = {}

    def fake_supervise(run_dir_real, *, run_kind, deadline, run_engine=None):
        seen["slice"] = deadline - time.monotonic()
        seen["calls"] = seen.get("calls", 0) + 1
        return ED._with_run_fields(
            {"ok": False, "terminal": False, "reason": ED.dispatch_outcome.REASON_RUNNING,
             "detail": "captured", "attempts": 0, "forfeited": False},
            run_dir=run_dir_real, argv=[],
        )

    monkeypatch.setattr(ED, "_supervise", fake_supervise)
    return seen


def _review_with_max_wait(tmp_path, repo_root, run_dir, max_wait, *, runner=None,
                          build_view=None):
    return ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root,
        run_engine=runner if runner is not None else FakeRunner([]),
        build_view=build_view if build_view is not None else _fake_build_view(tmp_path),
        run_dir=run_dir, order_id="test-order", max_wait=max_wait,
    )


@pytest.mark.parametrize("value", [0, 1, 7, ED.MAX_SYNC_WAIT])
def test_review_in_range_max_wait_is_honored_not_clamped(tmp_path, monkeypatch, value):
    run_dir = str(tmp_path / "run")
    repo_root, _ = _manual_open_review_run(tmp_path, run_dir)
    seen = _running_slice_capture(monkeypatch)
    res = _review_with_max_wait(tmp_path, repo_root, run_dir, value)
    assert res["terminal"] is False
    assert abs(seen["slice"] - value) < 1.0, (
        "requested %s s slice, supervisor got %.1f s" % (value, seen["slice"]))


@pytest.mark.parametrize("value", [ED.MAX_SYNC_WAIT + 1, 600, 3600, -1, -540])
def test_review_out_of_range_max_wait_is_a_named_refusal(tmp_path, monkeypatch, value):
    run_dir = str(tmp_path / "run")
    repo_root, _ = _manual_open_review_run(tmp_path, run_dir)
    seen = _running_slice_capture(monkeypatch)
    runner = FakeRunner([])
    res = _review_with_max_wait(tmp_path, repo_root, run_dir, value,
                                runner=runner, build_view=_never_build_view)
    assert res["ok"] is False
    assert res["terminal"] is True
    assert res["reason"] == ED.dispatch_outcome.REASON_UNRUNNABLE
    assert res["detail"] == "max-wait-out-of-range:%d:allowed=0..%d" % (value, ED.MAX_SYNC_WAIT)
    assert res["attempts"] == 0
    assert runner.calls == []
    assert "calls" not in seen, "a refused slice must not reach the supervisor"


@pytest.mark.parametrize("value", ["540", 1.5, True, [540]])
def test_review_non_integer_max_wait_is_a_named_refusal(tmp_path, value):
    run_dir = str(tmp_path / "run")
    repo_root, _ = _manual_open_review_run(tmp_path, run_dir)
    runner = FakeRunner([])
    res = _review_with_max_wait(tmp_path, repo_root, run_dir, value,
                                runner=runner, build_view=_never_build_view)
    assert res["detail"] == ED.MAX_WAIT_REFUSAL_TYPE
    assert res["terminal"] is True
    assert runner.calls == []


def test_over_cap_max_wait_never_returns_running_sooner_than_in_range(tmp_path, monkeypatch):
    """#862 regression — the flag must not invert at the boundary.

    An over-cap value used to be clamped to MAX_SYNC_WAIT and then, because any explicit
    --max-wait returns after one slice, handed back non-terminal `running` *sooner* than the
    caller asked to wait. Pinned here: the at-cap value gets exactly the slice it asked for,
    and the over-cap value yields no non-terminal result at all — so it cannot come back
    sooner."""
    run_dir_ok = str(tmp_path / "run-ok")
    repo_ok, _ = _manual_open_review_run(tmp_path, run_dir_ok)
    seen = _running_slice_capture(monkeypatch)
    at_cap = _review_with_max_wait(tmp_path, repo_ok, run_dir_ok, ED.MAX_SYNC_WAIT)
    assert at_cap["terminal"] is False
    assert at_cap["reason"] == ED.dispatch_outcome.REASON_RUNNING
    in_range_slice = seen["slice"]
    assert abs(in_range_slice - ED.MAX_SYNC_WAIT) < 1.0

    run_dir_over = str(tmp_path / "run-over")
    repo_over, _ = _manual_open_review_run(tmp_path, run_dir_over)
    over_cap = _review_with_max_wait(tmp_path, repo_over, run_dir_over, ED.MAX_SYNC_WAIT + 60,
                                     build_view=_never_build_view)
    assert over_cap["reason"] != ED.dispatch_outcome.REASON_RUNNING
    assert over_cap["terminal"] is True
    assert over_cap["detail"].startswith(ED.MAX_WAIT_REFUSAL_RANGE)


def test_omitted_max_wait_still_polls_to_terminal_in_capped_slices(tmp_path, monkeypatch):
    """The documented way to wait longer than the cap is to omit the flag and keep polling —
    not to pass a bigger number."""
    run_dir = str(tmp_path / "run")
    repo_root, _ = _manual_open_review_run(tmp_path, run_dir)
    slices = []

    def fake_supervise(run_dir_real, *, run_kind, deadline, run_engine=None):
        slices.append(deadline - time.monotonic())
        terminal = len(slices) >= 3
        return ED._with_run_fields(
            {"ok": terminal, "terminal": terminal,
             "reason": None if terminal else ED.dispatch_outcome.REASON_RUNNING,
             "detail": "captured", "attempts": 1, "forfeited": False},
            run_dir=run_dir_real, argv=[],
        )

    monkeypatch.setattr(ED, "_supervise", fake_supervise)
    monkeypatch.setattr(ED, "SUPERVISOR_POLL_INTERVAL", 0.01)
    res = _review_with_max_wait(tmp_path, repo_root, run_dir, None)
    assert res["terminal"] is True
    assert len(slices) == 3
    assert all(abs(s - ED.MAX_SYNC_WAIT) < 1.0 for s in slices)


def test_run_lock_reclaimed_from_dead_holder_without_ttl_wait(tmp_path):
    """#862: a builder killed mid-slice leaves run.lock held by its dead pid. The next call
    reclaims it as soon as the holder is confirmed dead, instead of blocking re-attach for up
    to RUN_LOCK_TTL (1080 s) — while a LIVE holder still blocks."""
    import file_lock
    import hostinfo
    import socket

    run_dir = str(tmp_path / "run")
    _manual_open_review_run(tmp_path, run_dir)
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        start_new_session=True,
    )
    ED._journal_append(run_dir, {
        "kind": "attempt-started", "attempt": 1, "childPid": proc.pid, "at": time.time(),
    })
    ED._journal_append(run_dir, {
        "kind": "engine-started", "attempt": 1, "enginePgid": proc.pid, "at": time.time(),
    })
    lock_path = os.path.join(run_dir, ED.RUN_LOCK_NAME)
    fresh_dead_holder = {
        "pid": 99999999,
        "host": socket.gethostname(),
        "acquiredAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),  # well inside the TTL
        "bootId": hostinfo.boot_id(),
        "ttl": ED.RUN_LOCK_TTL,
    }
    with open(lock_path, "w", encoding="utf-8") as fh:
        json.dump(fresh_dead_holder, fh)
    try:
        res = ED._supervise(run_dir, run_kind=ED.RUN_KIND_REVIEW,
                            deadline=time.monotonic() + 1, run_engine=FakeRunner([]))
        assert res.get("detail") != "run-locked", (
            "a dead mid-slice holder must not block re-attach for the TTL")
        assert file_lock.read_holder(lock_path).get("pid") in (os.getpid(), None)
    finally:
        file_lock.release(lock_path)
        ED._terminate_process_group(proc.pid)
        proc.wait(timeout=5)


def test_run_lock_live_holder_still_blocks_reattach(tmp_path):
    """The other direction of the same reclaim rule: a LIVE run.lock holder is never stolen."""
    import file_lock

    run_dir = str(tmp_path / "run")
    _manual_open_review_run(tmp_path, run_dir)
    lock_path = os.path.join(run_dir, ED.RUN_LOCK_NAME)
    file_lock.acquire(lock_path, ttl=ED.RUN_LOCK_TTL)            # held by THIS live pid
    try:
        res = ED._supervise(run_dir, run_kind=ED.RUN_KIND_REVIEW,
                            deadline=time.monotonic() + 1, run_engine=FakeRunner([]))
        assert res["detail"] == "run-locked"
        assert res["terminal"] is False
        assert file_lock.read_holder(lock_path)["pid"] == os.getpid()
    finally:
        file_lock.release(lock_path)


# --- #830 WO-3: child-stood-down reader ---


def test_journal_state_child_stood_down_returns_both_in_order():
    """axis: stand-down records are folded in journal order with all four fields."""
    records = [
        {
            "kind": "child-stood-down", "attempt": 1,
            "childPid": 100, "recordedPid": 200, "at": 1.0,
        },
        {
            "kind": "child-stood-down", "attempt": 1,
            "childPid": 101, "recordedPid": 200, "at": 2.0,
        },
    ]
    state = ED._journal_state(records)
    assert state["stoodDown"] == [
        {"attempt": 1, "childPid": 100, "recordedPid": 200, "at": 1.0},
        {"attempt": 1, "childPid": 101, "recordedPid": 200, "at": 2.0},
    ]


def test_journal_state_no_stand_down_returns_empty_list():
    """axis: stoodDown key is always present, never missing."""
    records = [
        {"kind": "run-opened", "runKind": ED.RUN_KIND_REVIEW, "at": 1.0},
    ]
    state = ED._journal_state(records)
    assert state["stoodDown"] == []


def test_journal_state_child_stood_down_missing_field_kept_with_none():
    """axis: malformed stand-down records are kept, not dropped."""
    records = [
        {
            "kind": "child-stood-down", "attempt": 1,
            "childPid": 100, "at": 1.0,
        },
    ]
    state = ED._journal_state(records)
    assert state["stoodDown"] == [
        {"attempt": 1, "childPid": 100, "recordedPid": None, "at": 1.0},
    ]


def test_journal_state_other_keys_unchanged_when_stand_down_present():
    """axis: stand-down fold is purely additive — every other key unchanged."""
    base_records = [
        {"kind": "run-opened", "runKind": ED.RUN_KIND_REVIEW, "at": 1.0},
        {"kind": "lease-acquired", "leaseToken": "tok", "at": 2.0},
        {"kind": "attempt-started", "attempt": 1, "childPid": 200, "at": 3.0},
        {"kind": "attempt-ended", "attempt": 1, "exit": 0, "at": 4.0},
        {"kind": "run-folded", "result": {"ok": True}, "at": 5.0},
    ]
    with_stand_down = base_records + [
        {
            "kind": "child-stood-down", "attempt": 1,
            "childPid": 100, "recordedPid": 200, "at": 6.0,
        },
    ]
    base_state = ED._journal_state(base_records)
    full_state = ED._journal_state(with_stand_down)
    for key in base_state:
        if key != "stoodDown":
            assert full_state[key] == base_state[key], key
    assert full_state["stoodDown"] == [
        {"attempt": 1, "childPid": 100, "recordedPid": 200, "at": 6.0},
    ]


def test_ledger_evidence_carries_stood_down_and_preserves_existing_keys(tmp_path):
    """axis: ledger evidence includes stand-downs without altering path keys."""
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    opened = {"promptPath": os.path.join(run_dir, "prompt.txt")}
    state = {
        "attempts": {1: {"childPid": 200, "enginePgid": None, "ended": None}},
        "stoodDown": [
            {"attempt": 1, "childPid": 100, "recordedPid": 200, "at": 1.0},
        ],
    }
    evidence = ED._ledger_evidence(run_dir, state, opened)
    assert evidence["stoodDownCount"] == 1
    assert evidence["stoodDown"] == [
        {"attempt": 1, "childPid": 100, "recordedPid": 200, "at": 1.0},
    ]
    assert evidence["stoodDownTruncated"] is False
    assert evidence["stdoutPaths"] == [os.path.join(run_dir, "attempt-1.stdout")]
    assert evidence["stderrPaths"] == [os.path.join(run_dir, "attempt-1.stderr")]
    assert evidence["journalPath"] == ED._journal_path(run_dir)
    assert evidence["promptPath"] == opened["promptPath"]


def _stood_down_records(n):
    return [
        {
            "kind": "child-stood-down", "attempt": 1,
            "childPid": 100 + i, "recordedPid": 200, "at": float(i),
        }
        for i in range(n)
    ]


def test_ledger_evidence_stood_down_truncated_at_twenty(tmp_path):
    """axis: ledger evidence caps stand-down list at 20 with truncation flag."""
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    opened = {"promptPath": None}
    state = {"attempts": {}, "stoodDown": []}
    for rec in _stood_down_records(25):
        state["stoodDown"].append({
            "attempt": rec["attempt"],
            "childPid": rec["childPid"],
            "recordedPid": rec["recordedPid"],
            "at": rec["at"],
        })
    evidence = ED._ledger_evidence(run_dir, state, opened)
    assert evidence["stoodDownCount"] == 25
    assert len(evidence["stoodDown"]) == 20
    assert evidence["stoodDownTruncated"] is True
    assert evidence["stoodDown"][0]["childPid"] == 100
    assert evidence["stoodDown"][-1]["childPid"] == 119


def test_ledger_evidence_stood_down_at_boundary_not_truncated(tmp_path):
    """axis: exactly 20 stand-downs fit without truncation."""
    run_dir = str(tmp_path / "run")
    os.makedirs(run_dir)
    opened = {"promptPath": None}
    state = {"attempts": {}, "stoodDown": []}
    for rec in _stood_down_records(20):
        state["stoodDown"].append({
            "attempt": rec["attempt"],
            "childPid": rec["childPid"],
            "recordedPid": rec["recordedPid"],
            "at": rec["at"],
        })
    evidence = ED._ledger_evidence(run_dir, state, opened)
    assert evidence["stoodDownCount"] == 20
    assert len(evidence["stoodDown"]) == 20
    assert evidence["stoodDownTruncated"] is False


# --- #862 review finding: only the recorded child runs the attempt --------------
# axis: WHICH child owns the attempt (identity), not whether one is alive.


def test_run_child_stands_down_when_the_attempt_names_another_child(tmp_path, monkeypatch):
    """A supervisor that died between Popen and its journal append leaves an orphan child
    waiting for a pending attempt. Once a fresh supervisor records its OWN child, the orphan
    must stand down instead of launching a second engine on the same run dir."""
    run_dir = str(tmp_path / "run")
    _manual_open_review_run(tmp_path, run_dir)
    ED._journal_append(run_dir, {
        "kind": "attempt-started", "attempt": 1, "childPid": 99999999, "at": time.time(),
    })
    launched = []
    monkeypatch.setattr(ED, "_run_engine_files", lambda *a, **k: launched.append(a))

    assert ED._run_child_main(run_dir) == 0

    assert launched == [], "orphan child launched the engine for another child's attempt"
    kinds = [r.get("kind") for r in ED._journal_read(run_dir)[0]]
    assert "engine-launching" not in kinds
    assert "child-stood-down" in kinds


def test_run_child_runs_the_attempt_recorded_for_it(tmp_path, monkeypatch):
    """The other direction: the child the record names does run it."""
    run_dir = str(tmp_path / "run")
    _manual_open_review_run(tmp_path, run_dir)
    ED._journal_append(run_dir, {
        "kind": "attempt-started", "attempt": 1, "childPid": os.getpid(), "at": time.time(),
    })
    launched = []
    monkeypatch.setattr(ED, "_run_engine_files", lambda *a, **k: launched.append(a))

    assert ED._run_child_main(run_dir) == 0

    assert len(launched) == 1
    kinds = [r.get("kind") for r in ED._journal_read(run_dir)[0]]
    assert "engine-launching" in kinds
    assert "child-stood-down" not in kinds
