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


def test_parse_result_review_bare_array_is_tolerated_and_scrubbed():
    # #196: engines commonly emit the findings list as a bare top-level JSON array instead of
    # {"findings": [...]}. The live failure (PR #190) had five codex reviewers return clean bare
    # arrays and all five slots parse "unreadable" — one step from UFR-7 re-running the whole panel
    # on Claude. The tolerated shape is accepted AND scrubbed exactly like the canonical object.
    stdout = json.dumps([
        {"severity": "Important", "title": "leak",
         "file": "a.py", "line": 7,
         "body": "log shows Authorization: Bearer sk-EXAMPLEfakenotarealsecret0",
         "suggestion": "drop the header"}])
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    f = res["findings"][0]
    assert f["severity"] == "Important" and f["title"] == "leak"
    assert f["file"] == "a.py" and f["line"] == 7          # structural keys untouched
    # scrubbing applied to the tolerated shape, not just passed through
    assert "sk-EXAMPLEfakenotarealsecret0" not in f["body"]
    assert "[REDACTED]" in f["body"]


def test_parse_result_review_bare_empty_array_is_clean_zero_findings():
    # An empty bare array is a clean review with nothing to flag — it must NOT be unreadable
    # (that would forfeit the slot to a needless UFR-7 re-run), it is ok:true with no findings.
    assert EA.parse_result("codex", "review", "[]") == {"ok": True, "findings": []}


def test_parse_result_review_canonical_object_unchanged_by_tolerance():
    # The object path is byte-identical to before the #196 tolerance was added.
    stdout = json.dumps({"findings": [
        {"severity": "Critical", "title": "t", "body": "b", "suggestion": "s"}]})
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    assert res["findings"] == [{"severity": "Critical", "title": "t", "body": "b", "suggestion": "s"}]


def test_parse_result_review_bare_array_of_non_objects_is_unreadable():
    # A bare array whose entries are not finding objects is noise, not findings — fail closed
    # (never a silent empty pass), the same direction as garbage/empty stdout.
    assert EA.parse_result("codex", "review", "[1, 2, 3]") == {"ok": False, "reason": "unreadable"}
    assert EA.parse_result("codex", "review", '["a", "b"]') == {"ok": False, "reason": "unreadable"}
    # a mixed array (some objects, some not) is also rejected — the tolerated shape is a clean
    # array of finding objects, not a scrub-and-hope filter (that stays the object path's behavior).
    assert EA.parse_result("codex", "review", '[{"severity":"Minor"}, 7]') == \
        {"ok": False, "reason": "unreadable"}


def test_parse_result_review_bare_array_via_streaming_scan_is_tolerated_and_scrubbed():
    # #196: the bare array need not be a clean whole-blob parse — the raw_decode scan path in
    # _last_json_array (mirroring the tested object stream-scan) recovers it past leading stream
    # noise. Exercises that branch (not just the whole-blob fast path) and confirms it still scrubs.
    stream = ('codex: starting review\n'
              '[{"severity":"Minor","title":"leak","file":"a.py","line":2,'
              '"body":"log shows Authorization: Bearer sk-EXAMPLEfakenotarealsecret0"}]')
    res = EA.parse_result("codex", "review", stream)
    assert res["ok"] is True
    f = res["findings"][0]
    assert f["severity"] == "Minor" and f["file"] == "a.py"
    assert "sk-EXAMPLEfakenotarealsecret0" not in f["body"]
    assert "[REDACTED]" in f["body"]


def test_parse_result_review_findingsless_object_is_not_rescued_by_a_stray_array():
    # #196 premortem fix: the bare-array tolerance is gated on `obj is None` (no top-level object
    # at all), NOT merely on a missing `findings` key. A present-but-findings-less result object
    # (a crashed/errored reviewer) must stay unreadable and fall open to a Claude re-run — the
    # stream must NOT be hunted for some other array to reinterpret as findings. Otherwise a
    # crashed slot with a stray (esp. empty) array earlier in the stream would be silently
    # certified as a clean, zero-finding review (a fail-OPEN — the exact hazard #196 fixes).
    findingsless_then_stray = ('[{"severity":"Minor","title":"stray","body":"b"}]\n'
                               '{"error":"reviewer crashed"}')
    assert EA.parse_result("codex", "review", findingsless_then_stray) == \
        {"ok": False, "reason": "unreadable"}
    # the scariest variant: an EMPTY stray array must not become a false clean-zero pass
    empty_stray_then_error = '[]\n{"type":"result","status":"error"}'
    assert EA.parse_result("codex", "review", empty_stray_then_error) == \
        {"ok": False, "reason": "unreadable"}


def test_parse_result_bare_array_tolerance_is_review_only():
    # The tolerance is scoped to role_kind='review'. A bare array under build/fix/author-plan is
    # not a valid result for those object-shaped contracts and stays unreadable/empty as before.
    assert EA.parse_result("codex", "build", "[]").get("ok") is False
    assert EA.parse_result("codex", "fix", '[{"evidence":{}}]').get("ok") is False
    assert EA.parse_result("cursor", "author-plan", "[]").get("ok") is False


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


# #288: the build|fix branch must HONOR the external leaf's own ok/signal — never launder an honest
# refusal into ok:true. A laundered refusal was committed (the adapter is the sole committer) and
# recorded built:passed upstream of the native build gate (the #275 gate is native-leaf-only and can
# never see a value parse_result already coerced to true) — the exact false-merge-ready class #275
# closed for the native path, still open for the external path.
def test_parse_result_build_honest_refusal_is_not_laundered_to_ok_true():
    stdout = json.dumps({"ok": False, "signal": "plan_wrong",
                         "evidence": {"testFailed": True, "testPassed": False}})
    res = EA.parse_result("codex", "build", stdout)
    assert res["ok"] is False, "an honest ok:false refusal must NOT be coerced to ok:true"
    assert res["signal"] == "plan_wrong"      # the leaf's own signal is carried, not overwritten with 'ok'
    assert res["reason"] == "plan_wrong"      # informative reason so dispatch does not read 'unreadable'
    # evidence is still parsed to the two-boolean shape (the refusal path is not a parse failure)
    assert res["evidence"] == {"testFailed": True, "testPassed": False}


def test_parse_result_fix_honest_refusal_is_not_laundered_to_ok_true():
    stdout = json.dumps({"ok": False, "signal": "needs_context"})
    res = EA.parse_result("cursor", "fix", stdout)
    assert res["ok"] is False and res["signal"] == "needs_context"


def test_parse_result_build_stringified_false_ok_is_a_refusal_not_truthy():
    # #275 class: a truthy stringified "false" must read as a refusal, not launder to ok:true. Strict
    # boolean identity (mirrors the native gate's `worker.ok === true`) — only a genuine bool true wins.
    res = EA.parse_result("codex", "build", json.dumps({"ok": "false", "signal": "plan_wrong"}))
    assert res["ok"] is False


def test_parse_result_build_missing_ok_key_is_a_refusal():
    # No ok key at all -> fail closed (a refusal), defaulting the signal to the native worker-recovery
    # default ('needs_context', mirroring build_phase's `worker.signal || 'needs_context'`).
    res = EA.parse_result("codex", "build", json.dumps({"evidence": {"testPassed": True}}))
    assert res["ok"] is False and res["signal"] == "needs_context"


def test_parse_result_build_ok_true_preserves_success_signal():
    # The happy path is unchanged: a genuine ok:true build reports signal 'ok'.
    res = EA.parse_result("codex", "build", json.dumps({"ok": True, "signal": "ok", "evidence": {}}))
    assert res["ok"] is True and res["signal"] == "ok"


def test_parse_result_build_refusal_signal_normalized_to_known_vocabulary():
    # #288 (security + premortem review): the refusal signal is normalized to {plan_wrong,
    # needs_context} — NO engine-controlled free-text may escape this scrub boundary as signal/reason
    # (it flows into the journal outcome + narrator logs), and it must stay disjoint from the #277
    # harness-dead tripwire's reserved reason tokens. Off-contract / empty / non-string / secret-bearing
    # signals all collapse to needs_context; only an exact 'plan_wrong' survives.
    def sig(stdout):
        r = EA.parse_result("codex", "build", stdout)
        assert r["ok"] is False and r["signal"] == r["reason"]
        return r["signal"]
    assert sig(json.dumps({"ok": False, "signal": ""})) == "needs_context"          # empty (the `and sig` half)
    assert sig(json.dumps({"ok": False, "signal": 0})) == "needs_context"            # non-string
    assert sig(json.dumps({"ok": False, "signal": "dispatch-error"})) == "needs_context"  # #277 tripwire-token collision
    assert sig(json.dumps({"ok": False, "signal": "AKIA-SECRET-LEAK"})) == "needs_context"  # arbitrary free-text never escapes
    assert sig(json.dumps({"ok": False, "signal": "plan_wrong"})) == "plan_wrong"    # the one contracted value survives


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


def test_build_argv_cursor_maps_sonnet_model():
    # #308: the reviewer/fixer tiers resolve to sonnet; now that every dispatch threads its model,
    # a cursor reviewer/fixer must run the real Sonnet id, not the composer default.
    for role in ("review", "build", "fix"):
        argv = EA.build_argv("cursor", role, "composer", {"cwd": "/wt", "model": "sonnet"})
        assert argv[argv.index("--model") + 1] == "claude-sonnet-5-thinking-high"


def test_build_argv_cursor_haiku_has_no_cursor_model_falls_to_composer():
    # cursor exposes no Haiku model (verified `cursor-agent models`) — a haiku tier keeps the pinned
    # composer default via the .get() fallback (honest; display_model resolves it identically).
    argv = EA.build_argv("cursor", "review", "composer", {"model": "haiku"})
    assert argv[argv.index("--model") + 1] == "composer-2.5-fast"


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


def test_parse_result_author_plan_scrubs_notify_identity():
    stdout = json.dumps({"status": "ok", "notify": [
        {"identity": "Authorization: Bearer sk-EXAMPLEfakenotarealsecret0",
         "message": "took a default"}]})
    res = EA.parse_result("cursor", "author-plan", stdout)
    assert res["ok"] is True
    n = res["notify"][0]
    assert "sk-EXAMPLEfakenotarealsecret0" not in n["identity"]
    assert "[REDACTED]" in n["identity"]
    assert n["message"] == "took a default"


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


def test_engine_reviewer_stdout_contract_is_stated_in_dispatch_reference():
    # #196: the stdout shape contract must live where orchestrators read it when composing the
    # engine-dispatch prompt — not only in this parser's source. Structural pin so the prose
    # contract can't silently vanish and let orchestrators re-guess the shape per run.
    ref = os.path.join(_HERE, "..", "..", "skills", "review-code", "reference", "auto-fix-loop.md")
    with open(ref, encoding="utf-8") as fh:
        text = fh.read()
    # the canonical required shape, verbatim
    assert '{"findings": [...]}' in text
    # and the tolerated bare-array note (kept in sync with parse_result's #196 tolerance)
    assert "bare" in text and "array" in text


def test_engine_dispatch_timeout_expiry_contract_is_stated_in_dispatch_reference():
    # #202: a wedged engine dispatch is not fail-open (a hang, not a bounded cost). The timeout
    # itself is structural (#204's PreToolUse Bash floor), so this reference does NOT prescribe a
    # prompted watchdog — what it owns is the EXPIRY contract: a killed/timed-out dispatch parses
    # `unreadable` → the reviewer takes UFR-7, the fixer falls open to Claude. Structural pin so
    # that contract (and the "structural, not prompted" framing) can't silently vanish.
    ref = os.path.join(_HERE, "..", "..", "skills", "review-code", "reference", "auto-fix-loop.md")
    with open(ref, encoding="utf-8") as fh:
        text = fh.read()
    # the structural-floor mechanism is named (so no one re-adds a prompted-watchdog claim), with
    # #204 cited as its source
    assert "bash_timeout.py" in text and "#204" in text
    # covers BOTH dispatch types — the fixer is the same hang class as the reviewer
    assert "reviewer" in text and "fixer" in text
    # the expiry contract: an expired slot is `unreadable`, routed to UFR-7
    assert "unreadable" in text and "UFR-7" in text
