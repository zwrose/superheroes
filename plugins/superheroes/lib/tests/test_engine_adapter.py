import importlib.util
import hashlib
import json
import os
import re

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    spec = importlib.util.spec_from_file_location(
        "engine_adapter", os.path.join(_HERE, "..", "engine_adapter.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


EA = _load()


def _help_text_for_substring_match(text: str) -> str:
    """Normalize argparse --help for substring assertions.

    argparse re-wraps help to the terminal width; a raw substring pin is a
    false-failure waiting for a narrow terminal.
    """
    return re.sub(r"\s+", " ", text, flags=re.UNICODE).strip().lower()


def test_task_id_trailer_constant():
    assert EA.TASK_ID_TRAILER == "Task-Id"


def test_review_forfeit_vacuous_token_single_home_no_literal_drift():
    """Drift guard: REVIEW_FORFEIT_VACUOUS is the only home; consumers must import, never restate."""
    assert EA.REVIEW_FORFEIT_VACUOUS == "vacuous"
    lib = os.path.join(_HERE, "..")
    consumers = (
        ("engine_dispatch.py", importlib.util.spec_from_file_location(
            "engine_dispatch_drift", os.path.join(lib, "engine_dispatch.py"))),
        ("round_driver.py", importlib.util.spec_from_file_location(
            "round_driver_drift", os.path.join(lib, "round_driver.py"))),
        ("seat_canary.py", importlib.util.spec_from_file_location(
            "seat_canary_drift", os.path.join(lib, "seat_canary.py"))),
    )
    import re
    _vacuous_lit = re.compile(r'''(?<![\w-])(["'])vacuous\1''')
    _vacuous_get = re.compile(r'''\.get\((["'])vacuous\1\)''')
    for basename, spec in consumers:
        src = open(os.path.join(lib, basename), encoding="utf-8").read()
        # Bare "vacuous" / 'vacuous' string literals (not vacuous-forfeit, vacuousSeats, etc.) re-open #666 drift.
        for i, line in enumerate(src.splitlines(), 1):
            if "import engine_adapter" in line or "REVIEW_FORFEIT_VACUOUS" in line:
                continue
            remainder = _vacuous_get.sub("", line)
            if _vacuous_lit.search(remainder):
                raise AssertionError(
                    "%s:%d restates the vacuous token literally — import engine_adapter.REVIEW_FORFEIT_VACUOUS"
                    % (basename, i))


def test_vacuous_drift_guard_catches_historical_fold_line_shape():
    """Match-granular guard must flag bare reason token beside .get('vacuous')."""
    import re
    _vacuous_lit = re.compile(r'''(?<![\w-])(["'])vacuous\1''')
    _vacuous_get = re.compile(r'''\.get\((["'])vacuous\1\)''')
    historical = (
        '            if seat.get("vacuous") is True or seat.get("reason") == "vacuous":'
    )
    remainder = _vacuous_get.sub("", historical)
    assert _vacuous_lit.search(remainder), "historical fold line must still trip the drift guard"


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


def test_build_argv_codex_review_with_cwd_pins_repo():
    argv = EA.build_argv("codex", "review", "high", {"cwd": "/repo", "schema_path": "/s.json"})
    i = argv.index("-C")
    assert argv[i + 1] == "/repo"


def test_build_argv_codex_build_workspace_write():
    argv = EA.build_argv("codex", "build", "high", {"cwd": "/wt"})
    assert argv[argv.index("--sandbox") + 1] == "workspace-write"
    assert "-C" in argv and argv[argv.index("-C") + 1] == "/wt"
    assert "model_reasoning_effort=high" in argv


def test_build_argv_codex_build_with_cwd_still_has_c_flag():
    argv = EA.build_argv("codex", "build", "high", {"cwd": "/repo"})
    i = argv.index("-C")
    assert argv[i + 1] == "/repo"


def test_build_argv_codex_review_without_cwd_has_no_c_flag():
    argv = EA.build_argv("codex", "review", "high", {})
    assert "-C" not in argv


def test_build_argv_codex_fix_low_effort():
    argv = EA.build_argv("codex", "fix", "low", {"cwd": "/wt"})
    assert "model_reasoning_effort=low" in argv
    assert argv[argv.index("--sandbox") + 1] == "workspace-write"


def test_build_argv_codex_maps_shared_tier_to_gpt_5_6_model():
    expected = {"haiku": "gpt-5.6-terra", "sonnet": "gpt-5.6-terra",
                "opus": "gpt-5.6-sol"}
    for tier, model in expected.items():
        argv = EA.build_argv("codex", "review", "high", {"model": tier})
        assert argv[argv.index("-m") + 1] == model


def test_build_argv_codex_explicit_engine_model_pin_wins():
    argv = EA.build_argv("codex", "review", "xhigh",
                         {"model": "opus", "engine_model": "gpt-5.6-terra"})
    assert argv[argv.index("-m") + 1] == "gpt-5.6-terra"


def test_build_argv_codex_invalid_engine_model_fails_capable():
    res = EA.build_argv_result("codex", "review", "high",
                               {"model": "sonnet", "engine_model": "bogus"})
    assert res == {"argv": [], "reason": "unregistered-engine-model"}
    assert EA.build_argv("codex", "review", "high",
                         {"model": "sonnet", "engine_model": "bogus"}) == []


def test_build_argv_codex_invalid_engine_model_pin_refuses_unregistered():
    res = EA.build_argv_result("codex", "review", "high",
                               {"model": "opus", "engine_model": "gpt-5.5"})
    assert res == {"argv": [], "reason": "unregistered-engine-model"}


def test_build_argv_cursor_review_plan_mode():
    argv = EA.build_argv("cursor", "review", "composer", {"cwd": "/wt"})
    assert argv[0] == "cursor-agent"
    assert "--mode" in argv and argv[argv.index("--mode") + 1] == "plan"
    # cursor-agent 2026.06.26: --model (not -m); -p (headless) + --trust (clear the trust gate) required.
    assert "--model" in argv and argv[argv.index("--model") + 1] == "composer-2.5"
    assert "-p" in argv and "--trust" in argv
    assert "-m" not in argv                  # the old short flag is rejected by this cursor-agent


def test_build_argv_cursor_build_force_write():
    argv = EA.build_argv("cursor", "build", "composer", {"cwd": "/wt"})
    assert argv[0] == "cursor-agent"
    assert "-f" in argv                      # workspace-write / force
    assert "-p" in argv and "--trust" in argv
    assert argv[argv.index("--model") + 1] == "composer-2.5"


def test_build_argv_cli(capsys):
    rc = EA.main(["build-argv", "--engine", "codex", "--role", "build", "--effort", "high",
                  "--cwd", "/wt", "--model", "opus", "--engine-model", "gpt-5.6-terra"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out[0] == "codex" and "workspace-write" in out
    assert out[out.index("-m") + 1] == "gpt-5.6-terra"


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
    assert EA.parse_result("codex", "review", "[]") == {
        "ok": True, "findings": [], "investigated": [],
    }


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


def test_build_argv_cursor_work_roles_stay_on_composer_for_every_premium_tier():
    # OWNER POLICY (ratified 2026-07-09): cursor is the token-efficiency engine — composer-2.5 for
    # ALL work roles; premium Claude models are NEVER routed through cursor by default. A threaded
    # opus/sonnet/haiku tier deliberately falls through to the pinned composer default.
    for role in ("review", "build", "fix"):
        for tier in ("opus", "sonnet", "haiku"):
            argv = EA.build_argv("cursor", role, "composer", {"cwd": "/wt", "model": tier})
            assert argv[argv.index("--model") + 1] == "composer-2.5", (role, tier)


def test_build_argv_cursor_unmapped_model_refuses_non_tier():
    for model in ("", "bogus-tier", "cursor-grok-4.5-high"):
        res = EA.build_argv_result("cursor", "build", "composer", {"model": model})
        assert res["reason"] == "unknown-claude-tier", model
    argv = EA.build_argv("cursor", "build", "composer", {"model": "opus"})
    assert argv[argv.index("--model") + 1] == "composer-2.5"
    argv = EA.build_argv("cursor", "review", "composer", {})
    assert argv[argv.index("--model") + 1] == "composer-2.5"


def test_build_argv_codex_fable_tier_returns_empty_argv():
    assert EA.build_argv("codex", "build", "xhigh", {"cwd": "/wt", "model": "fable"}) == []


def test_build_argv_codex_invalid_effort_returns_empty_argv():
    assert EA.build_argv("codex", "build", "banana", {"model": "opus"}) == []


def test_build_argv_cursor_fable_tier_returns_empty_argv():
    assert EA.build_argv("cursor", "build", "composer", {"cwd": "/wt", "model": "fable"}) == []


def test_build_argv_cursor_engine_model_grok_high():
    argv = EA.build_argv("cursor", "review", "high", {"engine_model": "cursor-grok-4.5"})
    assert argv[argv.index("--model") + 1] == "cursor-grok-4.5-high"


def test_build_argv_cursor_engine_model_absent_defaults_composer():
    argv = EA.build_argv("cursor", "review", None, {})
    assert argv[argv.index("--model") + 1] == "composer-2.5"


def test_build_argv_cursor_unregistered_engine_model_returns_empty_argv():
    # present-but-unregistered ⇒ fail loud: gpt-5.6-sol is codex-only, not registered on cursor
    assert EA.build_argv("cursor", "review", "high", {"engine_model": "gpt-5.6-sol"}) == []


def test_build_argv_cursor_registered_engine_model_invalid_effort_returns_empty_argv():
    assert EA.build_argv("cursor", "review", "banana",
                         {"engine_model": "cursor-grok-4.5"}) == []


# ---------------------------------------------------------------------------
# build_argv_result named causes + fail-closed edges (#636)
# ---------------------------------------------------------------------------


def test_build_argv_result_composed_grok_token_effort_adoption():
    """Composed dispatch token supplies effort when orchestrator omits --effort (#636 G1)."""
    model_flag = lambda r: r["argv"][r["argv"].index("--model") + 1]
    r = EA.build_argv_result(
        "cursor", "review", None, {"engine_model": "cursor-grok-4.5-high"}
    )
    assert r["reason"] is None
    assert model_flag(r) == "cursor-grok-4.5-high"
    r_match = EA.build_argv_result(
        "cursor", "review", "high", {"engine_model": "cursor-grok-4.5-high"}
    )
    assert r_match["reason"] is None
    assert model_flag(r_match) == "cursor-grok-4.5-high"
    r_conflict = EA.build_argv_result(
        "cursor", "review", "low", {"engine_model": "cursor-grok-4.5-high"}
    )
    assert r_conflict == {"argv": [], "reason": "engine-model-effort-conflict"}
    r_bare = EA.build_argv_result(
        "cursor", "review", None, {"engine_model": "cursor-grok-4.5"}
    )
    assert r_bare == {"argv": [], "reason": "invalid-model-effort"}


def test_build_argv_cli_composed_grok_token_without_effort_flag(capsys):
    rc = EA.main(
        [
            "build-argv",
            "--engine",
            "cursor",
            "--role",
            "review",
            "--engine-model",
            "cursor-grok-4.5-high",
        ]
    )
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out[out.index("--model") + 1] == "cursor-grok-4.5-high"


def test_build_argv_result_seven_named_tokens():
    cases = [
        ("bogus", "review", "high", {}, "unknown-engine"),
        ("codex", "review", "high", {"model": "cursor-grok-4.5-high"}, "unknown-claude-tier"),
        ("cursor", "review", "high", {"model": "cursor-grok-4.5-high"}, "unknown-claude-tier"),
        ("codex", "build", "high", {"model": "fable"}, "fable-unrunnable"),
        ("cursor", "build", "composer", {"model": "fable"}, "fable-unrunnable"),
        ("codex", "review", "high", {"engine_model": "gpt-9"}, "unregistered-engine-model"),
        ("cursor", "review", "low", {"engine_model": "cursor-grok-4.5-high"},
         "engine-model-effort-conflict"),
        ("cursor", "review", "max", {"engine_model": "cursor-grok-4.5"}, "invalid-model-effort"),
        ("cursor", "review", "high", {"engine_model": "composer-2.5"}, "invalid-model-effort"),
    ]
    for engine, role, effort, opts, want in cases:
        got = EA.build_argv_result(engine, role, effort, opts)
        assert got["argv"] == [] and got["reason"] == want, (engine, opts, got)


def test_build_argv_result_untokenizable(monkeypatch):
    real = EA.model_registry.dispatch_token

    def _fake(vendor, model_id, effort):
        if vendor == "cursor" and model_id == "cursor-grok-4.5" and effort == "high":
            return None
        return real(vendor, model_id, effort)

    monkeypatch.setattr(EA.model_registry, "dispatch_token", _fake)
    got = EA.build_argv_result("cursor", "review", "high", {"engine_model": "cursor-grok-4.5"})
    assert got == {"argv": [], "reason": "untokenizable"}


def test_build_argv_result_fail_closed_edges():
    # 1 unknown engine
    assert EA.build_argv_result("openai", "review", "high", {})["reason"] == "unknown-engine"
    # 2 empty opts — codex derives sol
    argv = EA.build_argv_result("codex", "review", "high", None)
    assert argv["reason"] is None and argv["argv"][argv["argv"].index("-m") + 1] == "gpt-5.6-sol"
    argv = EA.build_argv_result("codex", "review", "high", {})
    assert argv["reason"] is None
    # 3 fable — covered in seven tokens
    # 4–6 unknown-claude-tier — covered
    assert EA.build_argv_result("cursor", "review", "high",
                                {"model": 123})["reason"] == "unknown-claude-tier"
    # 7 empty engine_model → composer
    r = EA.build_argv_result("cursor", "review", "high", {"engine_model": ""})
    assert r["reason"] is None and "composer-2.5" in r["argv"]
    r = EA.build_argv_result("cursor", "review", "high", {"engine_model": None})
    assert r["reason"] is None
    # 8 grok base + high effort
    r = EA.build_argv_result("cursor", "review", "high", {"engine_model": "cursor-grok-4.5"})
    assert r["argv"][r["argv"].index("--model") + 1] == "cursor-grok-4.5-high"
    # 9 full composed token
    r = EA.build_argv_result("cursor", "review", "high",
                             {"engine_model": "cursor-grok-4.5-high"})
    assert r["argv"][r["argv"].index("--model") + 1] == "cursor-grok-4.5-high"
    # 10 effort conflict — covered
    # 11 invalid effort max on grok base
    assert EA.build_argv_result("cursor", "review", "max",
                                {"engine_model": "cursor-grok-4.5"})["reason"] == "invalid-model-effort"
    # 12 composer + high
    assert EA.build_argv_result("cursor", "review", "high",
                                {"engine_model": "composer-2.5"})["reason"] == "invalid-model-effort"
    # 13 composer + None effort
    r = EA.build_argv_result("cursor", "review", None, {"engine_model": "composer-2.5"})
    assert r["reason"] is None and r["argv"][r["argv"].index("--model") + 1] == "composer-2.5"
    # 14 codex garbage pin
    assert EA.build_argv_result("codex", "review", "high",
                                {"engine_model": "gpt-9"})["reason"] == "unregistered-engine-model"
    # 15 codex sol + max passes
    r = EA.build_argv_result("codex", "review", "max", {"engine_model": "gpt-5.6-sol"})
    assert r["reason"] is None and "model_reasoning_effort=max" in r["argv"]
    # 16 read vs write roles unchanged
    rev = EA.build_argv_result("cursor", "review", "high", {})
    bld = EA.build_argv_result("cursor", "build", "high", {})
    assert "--mode" in rev["argv"] and rev["argv"][rev["argv"].index("--mode") + 1] == "plan"
    assert "-f" in bld["argv"] and "--mode" not in bld["argv"]


def test_build_argv_matches_build_argv_result_argv():
    samples = [
        ("codex", "review", "high", {"cwd": "/wt"}),
        ("codex", "review", "xhigh", {"engine_model": "gpt-5.6-sol"}),
        ("cursor", "build", "high", {}),
        ("cursor", "review", "high", {"engine_model": "cursor-grok-4.5"}),
        ("cursor", "review", "high", {"model": "opus"}),
        ("bogus", "review", "high", {}),
    ]
    for engine, role, effort, opts in samples:
        assert EA.build_argv(engine, role, effort, opts) == EA.build_argv_result(
            engine, role, effort, opts)["argv"]


def test_build_argv_cli_refusal_object_shape(capsys):
    rc = EA.main(["build-argv", "--engine", "cursor", "--role", "review",
                  "--model", "cursor-grok-4.5-high", "--effort", "high"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out == {
        "ok": False, "reason": "engine-config", "detail": "unknown-claude-tier", "argv": [],
    }


def test_build_argv_cli_empty_effort_normalizes_to_none_for_composer_pin(capsys):
    rc = EA.main(["build-argv", "--engine", "cursor", "--role", "review",
                  "--engine-model", "composer-2.5", "--effort", ""])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out[out.index("--model") + 1] == "composer-2.5"


def test_build_argv_must_not_regress_measured_invariants():
    argv = EA.build_argv("cursor", "review", "high", {"engine_model": "cursor-grok-4.5"})
    assert argv == [
        "cursor-agent", "--model", "cursor-grok-4.5-high", "-p", "--trust",
        "--mode", "plan", "--output-format", "stream-json",
    ]
    argv = EA.build_argv("codex", "review", "xhigh", {"engine_model": "gpt-5.6-sol"})
    assert argv == [
        "codex", "exec", "--sandbox", "read-only", "-m", "gpt-5.6-sol",
        "-c", "model_reasoning_effort=xhigh", "-",
    ]
    argv = EA.build_argv("cursor", "build", "high", {})
    assert argv == [
        "cursor-agent", "--model", "composer-2.5", "-p", "--trust", "-f",
        "--output-format", "stream-json",
    ]


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


def test_parse_result_subcommand_help_warns_echo_gap(capsys):
    # #685: the warning must live on the parse-result sub-parser (visible via parse-result -h),
    # not only on the parent engine_adapter help.
    with pytest.raises(SystemExit):
        EA.main(["parse-result", "--help"])
    text = capsys.readouterr().out
    normalized = _help_text_for_substring_match(text)
    assert "never sees the dispatched prompt" in normalized
    assert "empty findings" in normalized and "unverified" in normalized


def test_parse_result_echo_gap_is_stated_in_auto_fix_loop_reference():
    ref = os.path.join(_HERE, "..", "..", "skills", "review-code", "reference", "auto-fix-loop.md")
    with open(ref, encoding="utf-8") as fh:
        text = fh.read()
    assert "empty-findings result from that path is" in text.lower()
    assert "deliberately not built" in text.lower()
    assert "parses raw stdout first" in text.lower()


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


# ---------------------------------------------------------------------------
# #563 DoD 5a: plausible-start scan bounds raw_decode work (no per-char exception storm)


def _counting_raw_decode(monkeypatch):
    """Monkeypatch json.JSONDecoder.raw_decode with a call counter; return (count_getter, restore)."""
    import json as _json
    _orig = _json.JSONDecoder.raw_decode
    calls = [0]

    def _wrapped(self, s, idx=0):
        calls[0] += 1
        return _orig(self, s, idx)

    monkeypatch.setattr(_json.JSONDecoder, "raw_decode", _wrapped)
    return calls


def test_last_json_object_noise_without_braces_bounded_raw_decode(monkeypatch):
    calls = _counting_raw_decode(monkeypatch)
    noise = ("plain noise line with no json chars\n" * 50000)  # ~1.5 MB
    blob = noise + '{"findings": []}'
    result = EA._last_json_object(blob)
    assert result == {"findings": []}
    assert calls[0] <= 5, "raw_decode should run only at trailing '{' (got %d)" % calls[0]


def test_last_json_object_stray_braces_bounded_raw_decode(monkeypatch):
    calls = _counting_raw_decode(monkeypatch)
    noise_line = "log {debug} {trace}\n"
    n_lines = 20000
    blob = noise_line * n_lines + '{"findings": [{"severity":"Minor","title":"t","body":"b"}]}'
    brace_count = blob.count("{") - 1  # exclude the final real object opener from rough bound
    import time
    t0 = time.monotonic()
    result = EA._last_json_object(blob)
    elapsed = time.monotonic() - t0
    assert result is not None and result.get("findings")
    assert calls[0] <= brace_count + 5, (
        "raw_decode count %d should track '{' count (~%d), not chars" % (calls[0], brace_count))
    assert elapsed < 20.0


# ---------------------------------------------------------------------------
# #563 DoD 5b: tail-read with full-file fallback


def test_parse_result_tail_read_recovers_trailing_object(tmp_path, capsys):
    finding = '{"findings":[{"severity":"Minor","title":"t","body":"b"}]}'
    big = ("x" * (600 * 1024)) + finding
    p = tmp_path / "stdout.txt"
    p.write_text(big, encoding="utf-8")
    rc = EA.main(["parse-result", "--engine", "codex", "--role", "review",
                  "--stdout-path", str(p)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["ok"] is True
    assert out["findings"][0]["title"] == "t"


def test_parse_result_tail_read_falls_back_when_object_before_window(tmp_path, capsys):
    finding = '{"findings":[{"severity":"Minor","title":"early","body":"b"}]}'
    big = finding + ("y" * (600 * 1024))
    p = tmp_path / "stdout_early.json"
    p.write_text(big, encoding="utf-8")
    rc = EA.main(["parse-result", "--engine", "codex", "--role", "review",
                  "--stdout-path", str(p)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["ok"] is True
    assert out["findings"][0]["title"] == "early"


def test_parse_result_tail_read_garbled_large_file_is_unreadable(tmp_path, capsys):
    p = tmp_path / "garbled.txt"
    p.write_text(("not json at all\n" * 40000) + "{ not valid json", encoding="utf-8")
    rc = EA.main(["parse-result", "--engine", "codex", "--role", "review",
                  "--stdout-path", str(p)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out == {"ok": False, "reason": "unreadable"}


def test_parse_result_stdout_multibyte_split_at_tail_boundary(tmp_path, capsys):
    # A multibyte char (é = 2 bytes) positioned so the 512KB tail window begins mid-char; the file is
    # > MAX_STDOUT_TAIL_BYTES so the read truncates and is re-read in full — the trailing result JSON
    # must survive intact.
    p = tmp_path / "s.txt"
    filler = "é" * 300000  # ~600KB of 2-byte chars -> forces truncation mid-char
    p.write_text(filler + '{"findings":[{"severity":"Minor","title":"t","body":"b"}]}', encoding="utf-8")
    rc = EA.main(["parse-result", "--engine", "codex", "--role", "review",
                  "--stdout-path", str(p)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["ok"] is True and out["findings"][0]["title"] == "t"


def test_parse_result_truncated_tail_never_trusts_echoed_findings(tmp_path, capsys):
    # #563 tripwire: a >512KB final review object whose 700KB body pad pushes an echoed nested
    # {"findings":[...]} (title "WRONG") into the last MAX_STDOUT_TAIL_BYTES, while the true outer
    # findings (title "RIGHT") sit BEFORE the tail boundary. The old gate
    # (`if _truncated and not res.get("ok")`) trusted the tail and returned ok:true+WRONG; the fix
    # always re-reads the full file and returns RIGHT. Asserting "RIGHT" fails on a regression to the
    # old gate. Measured 2026-07-23: file ~717KB, outer '{' at pos 23 (outside the 512KB tail).
    pad = "P" * (700 * 1024)
    blob = ('codex: starting review\n'
            '{"findings":[{"severity":"Blocker","title":"RIGHT","body":"' + pad + '"}],'
            '"echo":{"findings":[{"severity":"Minor","title":"WRONG","body":"x"}]}}')
    p = tmp_path / "s.txt"
    p.write_text(blob, encoding="utf-8")
    rc = EA.main(["parse-result", "--engine", "codex", "--role", "review",
                  "--stdout-path", str(p)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["ok"] is True
    assert len(out["findings"]) == 1
    assert out["findings"][0]["title"] == "RIGHT"   # full-read wins; NOT the tail's echoed "WRONG"


# ---------------------------------------------------------------------------
# #563 DoD 3: empty-prompt guard on build-argv --prompt-path


def _build_argv_with_prompt(tmp_path, capsys, prompt_path=None, extra_args=None):
    args = ["build-argv", "--engine", "codex", "--role", "review",
            "--effort", "low", "--model", "sonnet"]
    if prompt_path is not None:
        args += ["--prompt-path", str(prompt_path)]
    if extra_args:
        args += extra_args
    rc = EA.main(args)
    return rc, json.loads(capsys.readouterr().out)


def test_build_argv_prompt_path_nonempty_file_emits_argv(tmp_path, capsys):
    p = tmp_path / "prompt.txt"
    p.write_text("review this diff\n", encoding="utf-8")
    rc, out = _build_argv_with_prompt(tmp_path, capsys, p)
    assert rc == 0 and isinstance(out, list) and out[0] == "codex"


def test_build_argv_prompt_path_whitespace_only_fails_closed(tmp_path, capsys):
    p = tmp_path / "empty.prompt"
    p.write_text("   \n\t  ", encoding="utf-8")
    rc, out = _build_argv_with_prompt(tmp_path, capsys, p)
    assert rc == 0
    assert out == {"ok": False, "reason": "empty-prompt", "detail": "empty", "path": str(p)}


def test_build_argv_prompt_path_missing_fails_closed(tmp_path, capsys):
    p = tmp_path / "no_such.prompt"
    rc, out = _build_argv_with_prompt(tmp_path, capsys, p)
    assert rc == 0
    assert out == {"ok": False, "reason": "empty-prompt", "detail": "missing", "path": str(p)}


def test_build_argv_prompt_path_directory_fails_closed(tmp_path, capsys):
    rc, out = _build_argv_with_prompt(tmp_path, capsys, tmp_path)
    assert rc == 0
    assert out == {"ok": False, "reason": "empty-prompt", "detail": "not-regular-file",
                  "path": str(tmp_path)}


def test_build_argv_without_prompt_path_unchanged(capsys):
    rc, out = _build_argv_with_prompt(None, capsys, prompt_path=None)
    assert rc == 0 and isinstance(out, list) and out[0] == "codex"


# ---------------------------------------------------------------------------
# #668: strip echoed prompt before parse; engagement extractors


def _review_prompt_with_shape_contract():
    return (
        "You are reviewing a pull request.\n"
        "Respond with JSON only in this shape:\n"
        '{"findings": [...]}\n'
        "Example empty review:\n"
        '{"findings": []}\n'
        "Each finding must include severity, title, body, suggestion.\n"
    )


def _parse_review_after_strip(stdout, prompt_text):
    stripped = EA.strip_echoed_prompt(stdout, prompt_text)
    return EA.parse_result("codex", "review", stripped)


def test_echo_only_prompt_after_strip_is_unreadable():
    prompt = _review_prompt_with_shape_contract()
    stdout = prompt  # engine echoed the prompt and answered nothing
    assert _parse_review_after_strip(stdout, prompt) == {"ok": False, "reason": "unreadable"}


def test_real_answer_after_echo_survives_strip_and_parse():
    prompt = _review_prompt_with_shape_contract()
    answer = json.dumps({"findings": [
        {"severity": "Important", "title": "t", "body": "b", "suggestion": "s"}]})
    stdout = prompt + "\n" + answer
    res = _parse_review_after_strip(stdout, prompt)
    assert res["ok"] is True
    assert len(res["findings"]) == 1
    assert res["findings"][0]["title"] == "t"


def test_json_escaped_echo_in_stream_envelope_stripped_to_unreadable():
    prompt = _review_prompt_with_shape_contract()
    escaped = json.dumps(prompt)[1:-1]
    stdout = '{"type":"progress","text":"' + escaped + '"}\n'
    assert _parse_review_after_strip(stdout, prompt) == {"ok": False, "reason": "unreadable"}


def test_truncated_echo_tail_still_stripped_to_unreadable():
    head = "x" * 2500
    prompt = head + _review_prompt_with_shape_contract()
    stdout = prompt[-1500:]
    assert _parse_review_after_strip(stdout, prompt) == {"ok": False, "reason": "unreadable"}


def test_middle_tail_slice_with_noise_still_unreadable():
    head = "x" * 2500
    prompt = head + _review_prompt_with_shape_contract()
    tail = prompt[-EA.ECHO_TAIL_CHARS:]
    middle = tail[400:1200]
    stdout = "prefix-noise<<<" + middle + ">>>suffix-noise"
    assert _parse_review_after_strip(stdout, prompt) == {"ok": False, "reason": "unreadable"}


def test_strip_echoed_prompt_empty_or_non_string_inputs_unchanged_no_raise():
    prompt = _review_prompt_with_shape_contract()
    for stdout in (None, "", 123, []):
        assert EA.strip_echoed_prompt(stdout, prompt) == stdout
    for bad_prompt in (None, "", 7):
        assert EA.strip_echoed_prompt("keep", bad_prompt) == "keep"


def test_codex_tokens_used_parses_trailing_block():
    assert EA.codex_tokens_used("noise\ntokens used\n17,417\n") == 17417


def test_codex_tokens_used_takes_last_block():
    tail = "tokens used\n1\nmore\ntokens used\n9,876\n"
    assert EA.codex_tokens_used(tail) == 9876


def test_codex_tokens_used_absent_garbage_empty_returns_none():
    assert EA.codex_tokens_used("") is None
    assert EA.codex_tokens_used("no token line here") is None
    assert EA.codex_tokens_used("tokens used\n") is None
    assert EA.codex_tokens_used("tokens used\nnot-a-number\n") is None


def test_cursor_tool_calls_counts_distinct_call_ids():
    lines = [
        '{"type":"tool_call","call_id":"a","subtype":"started"}',
        '{"type":"tool_call","call_id":"b","subtype":"started"}',
        '{"type":"tool_call","call_id":"a","subtype":"completed"}',
    ]
    assert EA.cursor_tool_calls("\n".join(lines)) == 2


def test_cursor_tool_calls_zero_when_no_tool_calls():
    stream = '{"type":"result","subtype":"success","duration_ms":1}\n'
    assert EA.cursor_tool_calls(stream) == 0


def test_cursor_tool_calls_skips_garbage_no_raise():
    stream = "not json\n" + '{"type":"tool_call","call_id":"z"}\n' + "{broken"
    assert EA.cursor_tool_calls(stream) == 1


def test_cursor_tool_calls_empty_returns_none():
    assert EA.cursor_tool_calls("") is None
    assert EA.cursor_tool_calls(None) is None


# ---------------------------------------------------------------------------
# #666: investigated propagation + spot_check_investigated floor


def test_parse_result_review_propagates_investigated_scrubbed():
    stdout = json.dumps({
        "findings": [],
        "investigated": [
            "a.py",
            42,
            "log shows Authorization: Bearer sk-EXAMPLEfakenotarealsecret0",
        ],
    })
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    assert len(res["investigated"]) == 2
    assert res["investigated"][0] == "a.py"
    assert "sk-EXAMPLE" not in res["investigated"][1]
    assert "[REDACTED]" in res["investigated"][1]


def test_parse_result_review_missing_investigated_key_yields_empty_list():
    stdout = json.dumps({"findings": [{"severity": "Minor", "title": "t", "body": "b"}]})
    res = EA.parse_result("codex", "review", stdout)
    assert res["investigated"] == []


def test_parse_result_review_bare_array_shape_yields_empty_investigated():
    stdout = json.dumps([{"severity": "Minor", "title": "t", "body": "b"}])
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    assert res["investigated"] == []


def _spot_reject_only(repo_root, entry, want_reason):
    ok, accepted, rejected = EA.spot_check_investigated([entry], repo_root)
    assert ok is False and accepted == []
    assert len(rejected) == 1 and rejected[0]["reason"] == want_reason


def test_spot_check_investigated_rejects_not_a_path(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    ok, accepted, rejected = EA.spot_check_investigated([""], str(root))
    assert ok is False and accepted == []
    assert rejected[0]["reason"] == "not-a-path"
    ok, _, rejected = EA.spot_check_investigated([None], str(root))
    assert rejected[0]["reason"] == "not-a-path"


def test_spot_check_investigated_rejects_absolute(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    f = tmp_path / "abs.py"
    f.write_text("x", encoding="utf-8")
    _spot_reject_only(str(root), str(f), "absolute")


def test_spot_check_investigated_rejects_escapes_repo_via_dotdot(tmp_path):
    outer = tmp_path / "outer"
    outer.mkdir()
    (outer / "secret.txt").write_text("x", encoding="utf-8")
    root = tmp_path / "repo"
    root.mkdir()
    _spot_reject_only(str(root), "../outer/secret.txt", "escapes-repo")


def test_spot_check_investigated_rejects_escapes_repo_via_symlink(tmp_path):
    outer = tmp_path / "outside"
    outer.mkdir()
    (outer / "leak.txt").write_text("x", encoding="utf-8")
    root = tmp_path / "repo"
    root.mkdir()
    link = root / "escape"
    link.symlink_to(outer)
    _spot_reject_only(str(root), "escape/leak.txt", "escapes-repo")


def test_spot_check_investigated_rejects_sibling_prefix_path(tmp_path):
    base = tmp_path / "x"
    base.mkdir()
    root = base / "repo"
    root.mkdir()
    evil = base / "repo-evil"
    evil.mkdir()
    (evil / "f").write_text("x", encoding="utf-8")
    _spot_reject_only(str(root), "../repo-evil/f", "escapes-repo")


def test_spot_check_investigated_rejects_missing(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _spot_reject_only(str(root), "no-such-file.py", "missing")


def test_spot_check_investigated_rejects_dot_and_directories(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _spot_reject_only(str(root), ".", "not-a-file")
    sub = root / "plugins"
    sub.mkdir()
    _spot_reject_only(str(root), "plugins", "not-a-file")


def test_spot_check_investigated_mixed_one_valid_three_rejects(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    good = root / "ok.py"
    good.write_text("x", encoding="utf-8")
    ok, accepted, rejected = EA.spot_check_investigated(
        ["ok.py", "/abs", "../x", ""], str(root))
    assert ok is True
    assert accepted == ["ok.py"]
    assert len(rejected) == 3


def test_spot_check_investigated_fail_closed_edges_no_raise(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    f = tmp_path / "notadir"
    f.write_text("x", encoding="utf-8")
    for inv in (None, "a.py"):
        ok, accepted, rejected = EA.spot_check_investigated(inv, str(root))
        assert ok is False and accepted == [] and not rejected
    ok, accepted, rejected = EA.spot_check_investigated(["a.py"], None)
    assert ok is False and rejected[0]["reason"] == "no-repo"
    ok, accepted, rejected = EA.spot_check_investigated(["a.py"], str(f))
    assert ok is False and all(r["reason"] == "no-repo" for r in rejected)


def test_finding_body_quoting_prompt_tail_survives_conditional_strip():
    """Genuine finding quoting the last 2k of the prompt must not be stripped away (#668)."""
    head = "H" * 5000
    prompt = head + _review_prompt_with_shape_contract()
    tail = prompt[-EA.ECHO_TAIL_CHARS:]
    answer = json.dumps({"findings": [
        {"severity": "Important", "title": "quoted prompt in body",
         "body": "context:\n" + tail,
         "suggestion": "s"}]})
    stdout = prompt + "\n" + answer
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    assert len(res["findings"]) == 1
    assert tail[:80] in res["findings"][0]["body"]


# ---------------------------------------------------------------------------
# #687: review_payload_shape + engagement_read


def test_review_payload_shape_empty_stdout():
    assert EA.review_payload_shape("") == {
        "parsed": EA.SHAPE_EMPTY_STDOUT, "topLevelKeys": [], "keysTruncated": False,
    }
    assert EA.review_payload_shape("   \n\t") == {
        "parsed": EA.SHAPE_EMPTY_STDOUT, "topLevelKeys": [], "keysTruncated": False,
    }


def test_review_payload_shape_none_is_empty_stdout():
    assert EA.review_payload_shape(None) == {
        "parsed": EA.SHAPE_EMPTY_STDOUT, "topLevelKeys": [], "keysTruncated": False,
    }


def test_review_payload_shape_object_without_findings():
    res = EA.review_payload_shape(json.dumps({"error": "crashed", "status": "fail"}))
    assert res["parsed"] == EA.SHAPE_OBJECT_WITHOUT_FINDINGS
    assert res["topLevelKeys"] == ["error", "status"]
    assert res["keysTruncated"] is False


def test_review_payload_shape_object_findings_not_a_list():
    res = EA.review_payload_shape(json.dumps({"findings": "oops"}))
    assert res == {
        "parsed": EA.SHAPE_OBJECT_FINDINGS_NOT_A_LIST, "topLevelKeys": [], "keysTruncated": False,
    }


def test_review_payload_shape_array_not_all_objects():
    res = EA.review_payload_shape("[1, 2, 3]")
    assert res == {
        "parsed": EA.SHAPE_ARRAY_NOT_ALL_OBJECTS, "topLevelKeys": [], "keysTruncated": False,
    }


def test_review_payload_shape_no_parseable_json():
    res = EA.review_payload_shape("{ not json")
    assert res == {
        "parsed": EA.SHAPE_NO_PARSEABLE_JSON, "topLevelKeys": [], "keysTruncated": False,
    }


def test_review_payload_shape_valid_object_returns_none():
    assert EA.review_payload_shape(json.dumps({"findings": [
        {"severity": "Minor", "title": "t", "body": "b"}]})) is None


def test_review_payload_shape_valid_empty_findings_returns_none():
    assert EA.review_payload_shape(json.dumps({"findings": []})) is None


def test_review_payload_shape_valid_bare_array_returns_none():
    assert EA.review_payload_shape(json.dumps([
        {"severity": "Minor", "title": "t", "body": "b"}])) is None
    assert EA.review_payload_shape("[]") is None


def test_review_payload_shape_bare_scalar_is_no_parseable_json():
    assert EA.review_payload_shape('"hello"') == {
        "parsed": EA.SHAPE_NO_PARSEABLE_JSON, "topLevelKeys": [], "keysTruncated": False,
    }
    assert EA.review_payload_shape("42") == {
        "parsed": EA.SHAPE_NO_PARSEABLE_JSON, "topLevelKeys": [], "keysTruncated": False,
    }
    assert EA.review_payload_shape("null") == {
        "parsed": EA.SHAPE_NO_PARSEABLE_JSON, "topLevelKeys": [], "keysTruncated": False,
    }
    assert EA.review_payload_shape("true") == {
        "parsed": EA.SHAPE_NO_PARSEABLE_JSON, "topLevelKeys": [], "keysTruncated": False,
    }


def test_review_payload_shape_hostile_key_scrubbed():
    secret_key = "Authorization: Bearer sk-EXAMPLEfakenotarealsecret0"
    res = EA.review_payload_shape(json.dumps({secret_key: "value"}))
    assert res["parsed"] == EA.SHAPE_OBJECT_WITHOUT_FINDINGS
    assert "sk-EXAMPLE" not in res["topLevelKeys"][0]
    assert "[REDACTED]" in res["topLevelKeys"][0]


def test_review_payload_shape_non_string_key_coerced(monkeypatch):
    monkeypatch.setattr(EA, "_last_json_object", lambda _stdout: {1: "x", "ok": "y"})
    res = EA.review_payload_shape('{"ignored": true}')
    assert res["parsed"] == EA.SHAPE_OBJECT_WITHOUT_FINDINGS
    assert "1" in res["topLevelKeys"]


def test_review_payload_shape_keys_truncated_by_count():
    obj = {("k%d" % i): i for i in range(EA.PAYLOAD_SHAPE_MAX_KEYS + 5)}
    res = EA.review_payload_shape(json.dumps(obj))
    assert res["parsed"] == EA.SHAPE_OBJECT_WITHOUT_FINDINGS
    assert len(res["topLevelKeys"]) == EA.PAYLOAD_SHAPE_MAX_KEYS
    assert res["keysTruncated"] is True


def test_review_payload_shape_keys_truncated_by_length():
    long_key = "a" * (EA.PAYLOAD_SHAPE_MAX_KEY_LEN + 20)
    res = EA.review_payload_shape(json.dumps({long_key: 1}))
    assert res["parsed"] == EA.SHAPE_OBJECT_WITHOUT_FINDINGS
    assert len(res["topLevelKeys"][0]) == EA.PAYLOAD_SHAPE_MAX_KEY_LEN
    assert res["keysTruncated"] is True


def test_review_payload_shape_keys_not_truncated_when_within_bounds():
    obj = {"alpha": 1, "beta": 2}
    res = EA.review_payload_shape(json.dumps(obj))
    assert res["keysTruncated"] is False
    assert res["topLevelKeys"] == ["alpha", "beta"]


def test_review_payload_shape_internal_error_returns_none(monkeypatch):
    def _boom(_stdout):
        raise RuntimeError("internal")
    monkeypatch.setattr(EA, "_last_json_object", _boom)
    assert EA.review_payload_shape('{"error": true}') is None


def test_review_payload_shape_parsed_values_are_members_of_home():
    """Every `parsed` label review_payload_shape can return must be in REVIEW_PAYLOAD_SHAPES."""
    cases = [
        "",
        "   ",
        json.dumps({"error": "x"}),
        json.dumps({"findings": "oops"}),
        "[1, 2]",
        "{ not json",
        '"hello"',
    ]
    for stdout in cases:
        shape = EA.review_payload_shape(stdout)
        if shape is not None:
            assert shape["parsed"] in EA.REVIEW_PAYLOAD_SHAPES, stdout


def test_review_payload_shapes_includes_prompt_echo_only():
    assert EA.SHAPE_PROMPT_ECHO_ONLY in EA.REVIEW_PAYLOAD_SHAPES


def test_engagement_read_findings_engaged():
    assert EA.engagement_read({"findings": [{"id": "f"}]}) == "engaged"


def test_engagement_read_investigated_engaged():
    assert EA.engagement_read({"investigated": ["a.py"]}) == "engaged"


def test_engagement_read_tool_calls_engaged():
    assert EA.engagement_read({"engagement": {"toolCalls": 1}}) == "engaged"


def test_engagement_read_none_unknown():
    assert EA.engagement_read(None) == "unknown"


def test_engagement_read_non_mapping_unknown():
    assert EA.engagement_read("oops") == "unknown"
    assert EA.engagement_read([]) == "unknown"


def test_engagement_read_missing_engagement_unknown():
    assert EA.engagement_read({}) == "unknown"


def test_engagement_read_engagement_not_mapping_unknown():
    assert EA.engagement_read({"engagement": "bad"}) == "unknown"


def test_engagement_read_zero_tool_calls_not_engaged():
    assert EA.engagement_read({"engagement": {"toolCalls": 0}}) == "unknown"


def test_engagement_read_non_numeric_tool_calls_not_engaged():
    assert EA.engagement_read({"engagement": {"toolCalls": "five"}}) == "unknown"
    assert EA.engagement_read({"engagement": {"toolCalls": {}}}) == "unknown"


def test_engagement_read_non_list_findings_not_engaged():
    assert EA.engagement_read({"findings": "oops"}) == "unknown"


def test_engagement_read_non_list_investigated_not_engaged():
    assert EA.engagement_read({"investigated": "a.py"}) == "unknown"


def test_engagement_read_forfeit_with_findings_still_engaged():
    assert EA.engagement_read({
        "ok": False, "reason": "vacuous",
        "findings": [{"id": "f"}],
    }) == "engaged"


def test_engagement_read_never_returns_inert():
    outcomes = set()
    for res in (
        {},
        None,
        {"engagement": {"toolCalls": 0}},
        {"findings": [{"id": "f"}]},
        {"investigated": ["a.py"]},
        {"engagement": {"toolCalls": 1}},
    ):
        outcomes.add(EA.engagement_read(res))
    assert outcomes <= {"engaged", "unknown"}
    assert "inert" not in outcomes
