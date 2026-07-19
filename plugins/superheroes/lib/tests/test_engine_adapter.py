import importlib.util
import hashlib
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
    assert argv[argv.index("-m") + 1] == "gpt-5.6-sol"  # capable default when no tier fact is supplied
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


def test_build_argv_codex_maps_shared_tier_to_gpt_5_6_model():
    expected = {"haiku": "gpt-5.6-luna", "sonnet": "gpt-5.6-terra",
                "opus": "gpt-5.6-sol", "fable": "gpt-5.6-sol"}
    for tier, model in expected.items():
        argv = EA.build_argv("codex", "review", "high", {"model": tier})
        assert argv[argv.index("-m") + 1] == model


def test_build_argv_codex_explicit_engine_model_pin_wins():
    argv = EA.build_argv("codex", "review", "xhigh",
                         {"model": "opus", "engine_model": "gpt-5.5"})
    assert argv[argv.index("-m") + 1] == "gpt-5.5"


def test_build_argv_codex_invalid_engine_model_fails_capable():
    argv = EA.build_argv("codex", "review", "high",
                         {"model": "sonnet", "engine_model": "bogus"})
    assert argv[argv.index("-m") + 1] == "gpt-5.6-terra"


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
                  "--cwd", "/wt", "--model", "opus", "--engine-model", "gpt-5.5"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out[0] == "codex" and "workspace-write" in out
    assert out[out.index("-m") + 1] == "gpt-5.5"


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
    # The tolerance is scoped to role_kind='review'. A bare array under build/fix is
    # not a valid result for those object-shaped contracts and stays unreadable/empty as before.
    assert EA.parse_result("codex", "build", "[]").get("ok") is False
    assert EA.parse_result("codex", "fix", '[{"evidence":{}}]').get("ok") is False


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


def test_build_argv_cursor_fable_tier_maps_fable_model():
    # An owner who overrides a role to the `fable` tier and routes it via cursor dispatches Fable —
    # the map's one deliberate premium exception. Exercised here on a write role.
    argv = EA.build_argv("cursor", "build", "composer", {"cwd": "/wt", "model": "fable"})
    assert argv[0] == "cursor-agent"
    assert argv[argv.index("--model") + 1] == "claude-fable-5-thinking-xhigh"
    assert "-f" in argv                       # workspace-write
    assert "--mode" not in argv               # not the read-only plan mode


def test_build_argv_cursor_work_roles_stay_on_composer_for_every_premium_tier():
    # OWNER POLICY (ratified 2026-07-09): cursor is the token-efficiency engine — composer-2.5 for
    # ALL work roles; premium Claude models are NEVER routed through cursor by default. A threaded
    # opus/sonnet/haiku tier deliberately falls through to the pinned composer default (the map's
    # only entry is the fable tier). This is the policy, not a coverage gap.
    for role in ("review", "build", "fix"):
        for tier in ("opus", "sonnet", "haiku"):
            argv = EA.build_argv("cursor", role, "composer", {"cwd": "/wt", "model": tier})
            assert argv[argv.index("--model") + 1] == "composer-2.5-fast", (role, tier)


def test_build_argv_cursor_fable_is_the_only_mapped_tier():
    # The one deliberate exception: the `fable` tier routed via cursor dispatches Fable. The map
    # contains fable and NOTHING else — adding premium ids would invert the owner policy (see
    # _CURSOR_MODEL_BY_TIER's comment).
    assert EA._CURSOR_MODEL_BY_TIER == {"fable": "claude-fable-5-thinking-xhigh"}


def test_build_argv_cursor_unmapped_model_keeps_composer_default():
    # opus included: only the fable tier gets a premium cursor model — an opus tier stays on composer
    # per the owner policy.
    for model in (None, "", "bogus-tier", "opus"):
        argv = EA.build_argv("cursor", "build", "composer", {"model": model})
        assert argv[argv.index("--model") + 1] == "composer-2.5-fast"
    argv = EA.build_argv("cursor", "review", "composer", {})
    assert argv[argv.index("--model") + 1] == "composer-2.5-fast"


def test_build_argv_codex_fable_tier_maps_capability_to_sol():
    argv = EA.build_argv("codex", "build", "xhigh", {"cwd": "/wt", "model": "fable"})
    assert argv[argv.index("-m") + 1] == "gpt-5.6-sol"
    assert argv[argv.index("--sandbox") + 1] == "workspace-write"
    assert "model_reasoning_effort=xhigh" in argv


def test_build_argv_cli_cursor_fable_model(capsys):
    rc = EA.main(["build-argv", "--engine", "cursor", "--role", "build",
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


# ---------------------------------------------------------------------------
# #347: the stream-json RESULT-ENVELOPE unwrap. Real cursor-agent stream-json wraps ALL
# leaf text inside the final result event as ONE escaped string — the leaf's verdict:
# {"type":"result","result":"...\n```json\n{\"ok\":true,...}\n```\n\nSummary...","session_id":"..."}
# A top-level scan sees only the envelope (no "ok" key), so before this unwrap every
# in-child cursor build/fix parsed as a refusal (live: run accept-harness-84251c…, 2026-07-10).


def _envelope(inner_text, **extra):
    ev = {"type": "result", "subtype": "success", "is_error": False,
          "duration_ms": 12345, "session_id": "0aae943d", "result": inner_text}
    ev.update(extra)
    return ('{"type":"system","subtype":"init","model":"Composer 2.5 Fast"}\n'
            '{"type":"thinking","text":"..."}\n' + json.dumps(ev) + "\n")


def test_parse_result_cursor_build_verdict_inside_stream_envelope():
    # The live shape: verdict JSON in a fenced block INSIDE the envelope's result string,
    # followed by a prose summary (exactly what Composer emitted in the 2026-07-10 run).
    inner = ('Test failed as expected. Implementing the append.\n```json\n'
             '{"ok":true,"signal":"ok","evidence":{"testFailed":true,"testPassed":true},'
             '"deniedAction":null}\n```\n\n**Task 1 complete.** Summary of the TDD steps.')
    res = EA.parse_result("cursor", "build", _envelope(inner))
    assert res == {"ok": True, "signal": "ok",
                   "evidence": {"testFailed": True, "testPassed": True}}


def test_parse_result_cursor_fix_honest_refusal_inside_stream_envelope():
    # An honest leaf refusal inside the envelope must SURVIVE as a refusal (#288 semantics
    # through the unwrap) — never unreadable, never coerced ok.
    inner = 'I cannot apply this plan.\n{"ok":false,"signal":"plan_wrong","evidence":{}}'
    res = EA.parse_result("cursor", "fix", _envelope(inner))
    assert res["ok"] is False and res["signal"] == "plan_wrong"


def test_parse_result_cursor_review_findings_inside_stream_envelope():
    inner = ('Reviewed the diff.\n{"findings":[{"severity":"Important","title":"t",'
             '"file":"a.py","line":3,"body":"b","suggestion":"s"}]}\nDone.')
    res = EA.parse_result("cursor", "review", _envelope(inner))
    assert res["ok"] is True
    assert res["findings"][0]["severity"] == "Important"


def test_parse_result_error_envelope_with_no_inner_json_is_unreadable():
    # An error envelope whose inner text carries no JSON parses unreadable — the honest
    # fail direction (falls open / UFR-7), never a silent pass.
    res = EA.parse_result("cursor", "build",
                          _envelope("fatal: model quota exceeded", is_error=True, subtype="error"))
    assert res == {"ok": False, "reason": "unreadable"}


def test_parse_result_envelope_unwrap_tolerates_truncated_leading_noise():
    # #347 bounded relay: the watchdog emits only the stdout TAIL, so the first line may be
    # chopped mid-JSON. The noise-tolerant scan must still find the final envelope and unwrap it.
    inner = '{"ok":true,"signal":"ok","evidence":{"testFailed":true,"testPassed":true}}'
    chopped = 'l","text":"...chopped mid-event..."}\n' + _envelope(inner)
    res = EA.parse_result("cursor", "build", chopped)
    assert res["ok"] is True and res["signal"] == "ok"


def test_parse_result_top_level_verdict_with_result_key_is_not_unwrapped():
    # A leaf verdict that happens to carry a type/result-looking shape but HAS an "ok" key is
    # the verdict itself — never unwrapped away.
    stdout = json.dumps({"type": "result", "result": "prose", "ok": True, "signal": "ok",
                         "evidence": {"testFailed": True, "testPassed": True}})
    res = EA.parse_result("cursor", "build", stdout)
    assert res["ok"] is True


def test_parse_result_codex_shapes_are_byte_identical_through_the_unwrap():
    # codex never emits the envelope shape — its parses must be unchanged by #347.
    stdout = json.dumps({"findings": [{"severity": "Minor", "title": "t", "body": "b",
                                       "suggestion": "s"}]})
    assert EA.parse_result("codex", "review", stdout)["ok"] is True
    verdict = json.dumps({"ok": True, "signal": "ok",
                          "evidence": {"testFailed": True, "testPassed": True}})
    assert EA.parse_result("codex", "build", verdict)["ok"] is True


def test_build_argv_verify_match(tmp_path, capsys):
    p = tmp_path / "x.prompt"
    p.write_bytes(b"payload")
    h = hashlib.sha256(b"payload").hexdigest()
    EA.main(["build-argv", "--engine", "codex", "--role", "review",
             "--effort", "high", "--verify", "%s:%s" % (p, h)])
    out = json.loads(capsys.readouterr().out)
    assert isinstance(out, list) and out[0] == "codex"


def test_build_argv_verify_mismatch(tmp_path, capsys):
    p = tmp_path / "x.prompt"
    p.write_bytes(b"tampered")
    h = hashlib.sha256(b"payload").hexdigest()
    EA.main(["build-argv", "--engine", "codex", "--role", "review",
             "--effort", "high", "--verify", "%s:%s" % (p, h)])
    out = json.loads(capsys.readouterr().out)
    assert out == {"ok": False, "reason": "staged-input-mismatch", "path": str(p)}


def test_build_argv_verify_missing_file(tmp_path, capsys):
    p = tmp_path / "absent.prompt"
    h = hashlib.sha256(b"payload").hexdigest()
    EA.main(["build-argv", "--engine", "codex", "--role", "review",
             "--effort", "high", "--verify", "%s:%s" % (p, h)])
    out = json.loads(capsys.readouterr().out)
    assert out == {"ok": False, "reason": "staged-input-mismatch", "path": str(p)}
