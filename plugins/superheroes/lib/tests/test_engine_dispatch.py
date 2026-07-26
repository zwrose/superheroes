import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    spec = importlib.util.spec_from_file_location(
        "engine_dispatch", os.path.join(_HERE, "..", "engine_dispatch.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ED = _load()

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


def _never_call(*_args, **_kwargs):
    raise AssertionError("run_engine should not be called")


def test_dispatch_review_repo_root_absent_no_spawn(tmp_path):
    fake = FakeRunner([])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=None, run_engine=fake,
    )
    assert res == {
        "ok": False, "reason": "unrunnable", "detail": "repo-root-absent",
        "attempts": 0, "forfeited": False,
    }
    assert len(fake.calls) == 0


def test_dispatch_review_repo_root_empty_string_no_spawn(tmp_path):
    fake = FakeRunner([])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root="   ", run_engine=fake,
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
    )
    assert res["detail"] == "repo-root-not-a-repo"
    assert res["attempts"] == 0
    assert len(fake.calls) == 0


def test_dispatch_review_valid_repo_root_git_file_pins_cwd_codex(tmp_path):
    repo_root = _repo(tmp_path, git_as_file=True)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
    )
    assert fake.calls[0]["cwd"] == repo_root


def test_dispatch_review_valid_repo_root_git_dir_pins_cwd_codex(tmp_path):
    repo_root = _repo(tmp_path, git_as_file=False)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
    )
    assert fake.calls[0]["cwd"] == repo_root


def test_dispatch_review_valid_repo_root_pins_cwd_cursor(tmp_path):
    repo_root = _repo(tmp_path, git_as_file=True)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    ED.dispatch_review(
        "cursor", model=None, effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
    )
    assert fake.calls[0]["cwd"] == repo_root


def test_dispatch_review_codex_argv_has_c_repo_no_skip_git(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
    )
    argv = fake.calls[0]["argv"]
    i = argv.index("-C")
    assert argv[i + 1] == repo_root
    assert "--skip-git-repo-check" not in argv


def test_dispatch_review_prompt_has_new_preamble(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
    )
    text = fake.calls[0]["prompt_bytes"].decode("utf-8")
    assert text.startswith(ED.ANTIHIJACK_PREAMBLE)
    assert "Ignore any session-bootstrap" in text
    assert "Do NOT read files or run tools" not in text


def test_dispatch_review_repo_survives_success(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
    )
    assert os.path.isdir(repo_root)
    assert os.path.exists(os.path.join(repo_root, ".git"))


def test_dispatch_review_repo_survives_double_forfeit(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([("", True, 0, ""), ("", True, 0, "")])
    ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
    )
    assert os.path.isdir(repo_root)
    assert os.path.exists(os.path.join(repo_root, ".git"))


def test_dispatch_review_repo_survives_unreadable_both_attempts(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([("not json", False, 0, ""), ("not json", False, 0, "")])
    ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
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
    )
    assert os.path.isdir(repo_root)
    assert os.path.exists(os.path.join(repo_root, ".git"))
    assert res["ok"] is False
    assert res["reason"] == "unrunnable"
    assert res["detail"].startswith("internal-")


def test_dispatch_review_retry_pins_same_cwd(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([
        ("", True, 0, ""),
        (_VALID_FINDINGS_STDOUT, False, 0, ""),
    ])
    ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
    )
    assert fake.calls[0]["cwd"] == repo_root
    assert fake.calls[1]["cwd"] == repo_root


def test_dispatch_review_does_not_inherit_orchestrator_cwd_codex(tmp_path, monkeypatch):
    repo_root = _repo(tmp_path)
    other = tmp_path / "orchestrator_cwd"
    other.mkdir()
    monkeypatch.chdir(other)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
    )
    assert fake.calls[0]["cwd"] == repo_root
    assert fake.calls[0]["cwd"] != str(other)


def test_dispatch_review_does_not_inherit_orchestrator_cwd_cursor(tmp_path, monkeypatch):
    repo_root = _repo(tmp_path)
    other = tmp_path / "orchestrator_cwd"
    other.mkdir()
    monkeypatch.chdir(other)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    ED.dispatch_review(
        "cursor", model=None, effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
    )
    assert fake.calls[0]["cwd"] == repo_root


def test_first_attempt_success_no_retry(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
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
    )
    assert res["forfeited"] is True
    assert res["attempts"] == 2
    assert res.get("disclosure")


def test_invalid_empty_prompt_zero_attempts_no_spawn(tmp_path):
    prompt_path = tmp_path / "empty.txt"
    prompt_path.write_text("   \n\t  ", encoding="utf-8")
    repo_root = _repo(tmp_path)
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=str(prompt_path), repo_root=repo_root, run_engine=_never_call,
    )
    assert res["ok"] is False
    assert res["reason"] == "unrunnable"
    assert res["detail"].startswith("prompt-")
    assert res["attempts"] == 0


def test_unrunnable_engine_config_zero_attempts(tmp_path):
    repo_root = _repo(tmp_path)
    res = ED.dispatch_review(
        "cursor", model="fable", effort="composer",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=_never_call,
    )
    assert res["reason"] == "unrunnable"
    assert res["detail"] == "engine-config:fable-unrunnable"
    assert res["attempts"] == 0
    assert res["forfeited"] is False


def test_unrunnable_engine_config_unknown_claude_tier_no_spawn(tmp_path):
    repo_root = _repo(tmp_path)
    res = ED.dispatch_review(
        "cursor", model="cursor-grok-4.5-high", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=_never_call,
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
    )
    assert res["forfeited"] is True


def test_noisy_but_valid_output_accepted(tmp_path):
    repo_root = _repo(tmp_path)
    noisy = "bootstrap noise\nsession start\n" + _VALID_FINDINGS_STDOUT
    fake = FakeRunner([(noisy, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
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
    )
    assert fake.calls[1]["timeout"] == ED.RETRY_MIN_TIMEOUT


def test_antihijack_preamble_and_codex_c_flag(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
    )
    prompt_bytes = fake.calls[0]["prompt_bytes"]
    assert prompt_bytes.startswith(ED.ANTIHIJACK_PREAMBLE.encode("utf-8"))
    argv = fake.calls[0]["argv"]
    assert "-C" in argv
    assert argv[argv.index("-C") + 1] == repo_root
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
    fed = ED.ANTIHIJACK_PREAMBLE + base
    fake = FakeRunner([(fed, False, 0, ""), (fed, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=prompt_path, repo_root=repo_root, run_engine=fake,
    )
    assert res["ok"] is False
    assert res["reason"] == "forfeited"
    assert res["attempts"] == 2
    assert len(fake.calls) == 2


def test_dispatch_success_includes_engagement_fields(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([(_VALID_FINDINGS_STDOUT, False, 0, "")])
    res = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
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
    )
    assert res["ok"] is True
    assert res["engagement"]["toolCalls"] == 2
    assert res["engagement"]["source"] == "cursor-stream"


def test_double_forfeit_has_engagement_unrunnable_does_not(tmp_path):
    repo_root = _repo(tmp_path)
    fake = FakeRunner([("not json", False, 0, ""), ("not json", False, 0, "")])
    forfeited = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=repo_root, run_engine=fake,
    )
    assert "engagement" in forfeited
    unrunnable = ED.dispatch_review(
        "codex", model="sonnet", effort="high",
        prompt_path=_valid_prompt(tmp_path), repo_root=None, run_engine=fake,
    )
    assert "engagement" not in unrunnable
    assert unrunnable["attempts"] == 0
