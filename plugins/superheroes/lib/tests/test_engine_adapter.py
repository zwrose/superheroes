import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    spec = importlib.util.spec_from_file_location(
        "engine_adapter", os.path.join(_HERE, "..", "engine_adapter.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


EA = _load()


def test_task_id_trailer_constant():
    assert EA.TASK_ID_TRAILER == "Task-Id"


def test_build_argv_codex_review_read_only():
    argv = EA.build_argv("codex", "review", "high",
                         {"cwd": "/wt", "schema_path": "/tmp/s.json"})
    assert argv[0] == "codex" and "exec" in argv
    assert "--sandbox" in argv and argv[argv.index("--sandbox") + 1] == "read-only"
    assert "model_reasoning_effort=high" in argv
    assert "--output-schema" in argv and argv[argv.index("--output-schema") + 1] == "/tmp/s.json"
    assert "-m" in argv  # explicit model, never ambient default
    assert argv[argv.index("-m") + 1] == "gpt-5.5"  # gpt-5-codex is rejected under ChatGPT-account auth
    assert argv[-1] == "-"  # codex reads the prompt from stdin (fed by the Task-10 JS runner)


def test_build_argv_codex_build_workspace_write():
    argv = EA.build_argv("codex", "build", "high", {"cwd": "/wt"})
    assert argv[argv.index("--sandbox") + 1] == "workspace-write"
    assert "-C" in argv and argv[argv.index("-C") + 1] == "/wt"
    assert "model_reasoning_effort=high" in argv


def test_build_argv_codex_fix_low_effort():
    argv = EA.build_argv("codex", "fix", "low", {"cwd": "/wt"})
    assert "model_reasoning_effort=low" in argv
    assert argv[argv.index("--sandbox") + 1] == "workspace-write"


def test_build_argv_cursor_review_plan_mode():
    argv = EA.build_argv("cursor", "review", "composer", {"cwd": "/wt"})
    assert argv[0] == "cursor-agent"
    assert "--mode" in argv and argv[argv.index("--mode") + 1] == "plan"
    # cursor-agent 2026.06.26: --model (not -m); -p (headless) + --trust (clear the trust gate) required.
    assert "--model" in argv and argv[argv.index("--model") + 1] == "composer-2.5-fast"
    assert "-p" in argv and "--trust" in argv
    assert "-m" not in argv                  # the old short flag is rejected by this cursor-agent


def test_build_argv_cursor_build_force_write():
    argv = EA.build_argv("cursor", "build", "composer", {"cwd": "/wt"})
    assert argv[0] == "cursor-agent"
    assert "-f" in argv                      # workspace-write / force
    assert "-p" in argv and "--trust" in argv
    assert argv[argv.index("--model") + 1] == "composer-2.5-fast"


def test_build_argv_cli(capsys):
    rc = EA.main(["build-argv", "--engine", "codex", "--role", "build", "--effort", "high",
                  "--cwd", "/wt"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out[0] == "codex" and "workspace-write" in out


def test_build_state_uses_shared_trailer_constant():
    import importlib.util as _u
    spec = _u.spec_from_file_location(
        "build_state", os.path.join(_HERE, "..", "build_state.py"))
    bs = _u.module_from_spec(spec)
    spec.loader.exec_module(bs)
    body, _ = bs.task_id_from_body("x\n\n%s: 1\n" % EA.TASK_ID_TRAILER, {"1"})
    assert body == "1"


def test_parse_result_codex_review_critical():
    stdout = json.dumps({"findings": [
        {"severity": "Critical", "title": "path traversal",
         "body": "file path built from unsanitized input escapes its dir",
         "suggestion": "sanitize the path"}]})
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    assert res["findings"][0]["severity"] == "Critical"
    assert res["findings"][0]["title"] == "path traversal"


def test_parse_result_cursor_review_stream_json_last_object():
    # stream-json: several line-delimited events; the LAST JSON object carries the findings.
    stream = ('{"type":"progress"}\n'
              '{"type":"result","findings":[{"severity":"Important","title":"x",'
              '"body":"b","suggestion":"s"}]}\n')
    res = EA.parse_result("cursor", "review", stream)
    assert res["ok"] is True
    assert res["findings"][0]["severity"] == "Important"


def test_parse_result_review_empty_is_unreadable():
    assert EA.parse_result("codex", "review", "") == {"ok": False, "reason": "unreadable"}
    assert EA.parse_result("cursor", "review", "   ") == {"ok": False, "reason": "unreadable"}


def test_parse_result_review_garbled_is_unreadable():
    assert EA.parse_result("codex", "review", "{ not json").get("ok") is False
    assert EA.parse_result("codex", "review", "{ not json")["reason"] == "unreadable"


def test_parse_result_scrubs_secret_in_finding_body():
    # Secret-hygiene: an external finding's free-text is scrubbed AT THIS BOUNDARY, so the
    # standalone /review-code --post PR comment (built from body/suggestion, unscrubbed there)
    # carries no external secret in the clear.
    stdout = json.dumps({"findings": [
        {"severity": "Important", "title": "leak",
         "body": "log shows Authorization: Bearer sk-EXAMPLEfakenotarealsecret0",
         "suggestion": "remove the header x-api-key: sk-live-EXAMPLEfakekey0"}]})
    res = EA.parse_result("codex", "review", stdout)
    f = res["findings"][0]
    assert "sk-EXAMPLEfakenotarealsecret0" not in f["body"]
    assert "[REDACTED]" in f["body"]
    assert "sk-live-EXAMPLEfakekey0" not in f["suggestion"]


def test_parse_result_scrubs_secret_in_finding_evidence_and_title():
    # security-001: the spine reviewer's finding schema is {file,line,title,severity,evidence} — a
    # secret quoted in `evidence` or `title` (not just body/suggestion) must ALSO be scrubbed at this
    # boundary, or it leaks unscrubbed into an owner-facing PR comment.
    stdout = json.dumps({"findings": [
        {"severity": "Critical", "title": "leaked token sk-live-EXAMPLEfakenotarealkey00",
         "file": "a.py", "line": 3,
         "evidence": "log shows Authorization: Bearer sk-EXAMPLEfakenotarealsecret0"}]})
    res = EA.parse_result("codex", "review", stdout)
    f = res["findings"][0]
    assert "sk-EXAMPLEfakenotarealsecret0" not in f["evidence"]
    assert "[REDACTED]" in f["evidence"]
    assert "sk-live-EXAMPLEfakenotarealkey00" not in f["title"]
    assert "[REDACTED]" in f["title"]
    # structural keys are untouched
    assert f["file"] == "a.py"
    assert f["line"] == 3
    assert f["severity"] == "Critical"


def test_parse_result_build_evidence_two_booleans():
    stdout = json.dumps({"ok": True, "evidence": {"testFailed": False, "testPassed": True}})
    res = EA.parse_result("codex", "build", stdout)
    assert res["ok"] is True and res["signal"] == "ok"
    assert res["evidence"] == {"testFailed": False, "testPassed": True}
    # evidence carries ONLY the two booleans — no raw stdout leaks into it
    assert set(res["evidence"]) == {"testFailed", "testPassed"}


def test_parse_result_build_unreadable():
    assert EA.parse_result("cursor", "build", "").get("ok") is False


def test_parse_result_cli(capsys):
    import io, sys as _sys
    stdout = json.dumps({"ok": True, "evidence": {"testFailed": False, "testPassed": True}})
    _old = _sys.stdin
    _sys.stdin = io.StringIO(stdout)
    try:
        rc = EA.main(["parse-result", "--engine", "codex", "--role", "build"])
    finally:
        _sys.stdin = _old
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["signal"] == "ok"


def test_build_argv_cursor_author_plan_maps_fable_model():
    argv = EA.build_argv("cursor", "author-plan", "composer", {"cwd": "/wt", "model": "fable"})
    assert argv[0] == "cursor-agent"
    assert argv[argv.index("--model") + 1] == "claude-fable-5-thinking-xhigh"
    assert "-f" in argv                       # author writes the doc: workspace-write
    assert "--mode" not in argv               # not the read-only plan mode


def test_build_argv_cursor_author_plan_maps_opus_model():
    argv = EA.build_argv("cursor", "author-plan", "composer", {"model": "opus"})
    assert argv[argv.index("--model") + 1] == "claude-opus-4-8-thinking-high"


def test_build_argv_cursor_unmapped_model_keeps_composer_default():
    for model in (None, "", "bogus-tier"):
        argv = EA.build_argv("cursor", "author-plan", "composer", {"model": model})
        assert argv[argv.index("--model") + 1] == "composer-2.5-fast"
    # non-author roles without a model override are unchanged
    argv = EA.build_argv("cursor", "review", "composer", {})
    assert argv[argv.index("--model") + 1] == "composer-2.5-fast"


def test_build_argv_codex_author_plan_ignores_model_override():
    argv = EA.build_argv("codex", "author-plan", "xhigh", {"cwd": "/wt", "model": "fable"})
    assert argv[argv.index("-m") + 1] == "gpt-5.5"   # codex has no fable; pinned model stands
    assert argv[argv.index("--sandbox") + 1] == "workspace-write"
    assert "model_reasoning_effort=xhigh" in argv


def test_parse_result_author_plan_surfaces_scrubbed_notify():
    stdout = json.dumps({"status": "ok", "notify": [
        {"identity": "seed-choice",
         "message": "log shows Authorization: Bearer sk-EXAMPLEfakenotarealsecret0"}]})
    res = EA.parse_result("cursor", "author-plan", stdout)
    assert res["ok"] is True
    n = res["notify"][0]
    assert n["identity"] == "seed-choice"
    assert "sk-EXAMPLEfakenotarealsecret0" not in n["message"]
    assert "[REDACTED]" in n["message"]


def test_parse_result_author_plan_no_notify_is_ok_empty():
    # the doc's acceptance gate is the deterministic usableDraft post-check, not this parse
    assert EA.parse_result("cursor", "author-plan", json.dumps({"type": "result"})) == \
        {"ok": True, "notify": []}


def test_parse_result_author_plan_empty_is_unreadable():
    assert EA.parse_result("cursor", "author-plan", "").get("ok") is False


def test_build_argv_cli_author_plan_model(capsys):
    rc = EA.main(["build-argv", "--engine", "cursor", "--role", "author-plan",
                  "--effort", "composer", "--model", "fable"])
    argv = json.loads(capsys.readouterr().out)
    assert rc == 0 and argv[argv.index("--model") + 1] == "claude-fable-5-thinking-xhigh"
