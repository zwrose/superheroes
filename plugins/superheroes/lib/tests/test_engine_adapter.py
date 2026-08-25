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


def test_review_forfeit_vacuous_is_dispatch_outcome_reason_vacuous():
    """Identity drift guard: re-literalisation in engine_adapter must fail."""
    spec = importlib.util.spec_from_file_location(
        "dispatch_outcome", os.path.join(_HERE, "..", "dispatch_outcome.py"))
    dispatch_outcome = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dispatch_outcome)
    assert EA.REVIEW_FORFEIT_VACUOUS is dispatch_outcome.REASON_VACUOUS


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
    argv = EA.build_argv("codex", "review", "high", {"cwd": "/wt"})
    assert argv[0] == "codex" and "exec" in argv
    assert "--sandbox" in argv and argv[argv.index("--sandbox") + 1] == "read-only"
    assert "model_reasoning_effort=high" in argv
    assert "--output-schema" not in argv
    assert "-m" in argv  # explicit model, never ambient default
    assert argv[argv.index("-m") + 1] == "gpt-5.6-sol"  # capable default when no tier fact is supplied
    assert argv[-1] == "-"  # codex reads the prompt from stdin (fed by the Task-10 JS runner)


def test_build_argv_codex_review_with_cwd_pins_repo():
    argv = EA.build_argv("codex", "review", "high", {"cwd": "/repo"})
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
        "ok": True, "resultKind": "findings", "findings": [], "investigated": [],
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
    # Secret-hygiene: an external finding's free-text is scrubbed AT THIS BOUNDARY, so every
    # downstream consumer of body/suggestion inherits a clean value without scrubbing again.
    stdout = json.dumps({"findings": [
        {"severity": "Important", "title": "leak",
         "body": "log shows Authorization: Bearer sk-EXAMPLEfakenotarealsecret0",
         "suggestion": "remove the header x-api-key: sk-live-EXAMPLEfakekey0"}]})
    res = EA.parse_result("codex", "review", stdout)
    f = res["findings"][0]
    assert "sk-EXAMPLEfakenotarealsecret0" not in f["body"]
    assert "[REDACTED]" in f["body"]
    assert "sk-live-EXAMPLEfakekey0" not in f["suggestion"]


def test_parse_result_scrubs_secret_in_finding_id():
    secret = "ghp_EXAMPLEfakenotarealtoken000000000"
    stdout = json.dumps({"findings": [
        {"id": secret, "severity": "Important", "title": "leak", "body": "ok"}]})
    res = EA.parse_result("codex", "review", stdout)
    f = res["findings"][0]
    assert secret not in f["id"]
    assert "[REDACTED]" in f["id"]


def test_parse_result_scrubs_secret_in_verdict_id():
    secret = "ghp_EXAMPLEfakenotarealtoken000000000"
    stdout = json.dumps({"verdicts": [
        {"id": secret, "verdict": "CONFIRMED", "reason": "ok"}]})
    res = EA.parse_result("codex", "review", stdout)
    assert secret not in res["verdicts"][0]["id"]
    assert "[REDACTED]" in res["verdicts"][0]["id"]


def test_parse_result_ordinary_id_survives_on_both_paths():
    stdout_findings = json.dumps({"findings": [
        {"id": "code-001", "severity": "Important", "title": "t", "body": "b"}]})
    res_findings = EA.parse_result("codex", "review", stdout_findings)
    assert res_findings["findings"][0]["id"] == "code-001"
    stdout_verdicts = json.dumps({"verdicts": [
        {"id": "code-001", "verdict": "CONFIRMED", "reason": "ok"}]})
    res_verdicts = EA.parse_result("codex", "review", stdout_verdicts)
    assert res_verdicts["verdicts"][0]["id"] == "code-001"


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
    for model in ("", "bogus-tier", "cursor-grok-4.6-xhigh"):
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
    argv = EA.build_argv("cursor", "review", "xhigh", {"engine_model": "cursor-grok-4.6"})
    assert argv[argv.index("--model") + 1] == "cursor-grok-4.6-xhigh"


def test_build_argv_cursor_engine_model_absent_defaults_composer():
    argv = EA.build_argv("cursor", "review", None, {})
    assert argv[argv.index("--model") + 1] == "composer-2.5"


def test_build_argv_cursor_unregistered_engine_model_returns_empty_argv():
    # present-but-unregistered ⇒ fail loud: gpt-5.6-sol is codex-only, not registered on cursor
    assert EA.build_argv("cursor", "review", "high", {"engine_model": "gpt-5.6-sol"}) == []


def test_build_argv_cursor_registered_engine_model_invalid_effort_returns_empty_argv():
    assert EA.build_argv("cursor", "review", "banana",
                         {"engine_model": "cursor-grok-4.6"}) == []


# ---------------------------------------------------------------------------
# build_argv_result named causes + fail-closed edges (#636)
# ---------------------------------------------------------------------------


def test_build_argv_result_composed_grok_token_effort_adoption():
    """Composed dispatch token supplies effort when orchestrator omits --effort (#636 G1)."""
    model_flag = lambda r: r["argv"][r["argv"].index("--model") + 1]
    r = EA.build_argv_result(
        "cursor", "review", None, {"engine_model": "cursor-grok-4.6-xhigh"}
    )
    assert r["reason"] is None
    assert model_flag(r) == "cursor-grok-4.6-xhigh"
    r_match = EA.build_argv_result(
        "cursor", "review", "xhigh", {"engine_model": "cursor-grok-4.6-xhigh"}
    )
    assert r_match["reason"] is None
    assert model_flag(r_match) == "cursor-grok-4.6-xhigh"
    r_conflict = EA.build_argv_result(
        "cursor", "review", "low", {"engine_model": "cursor-grok-4.6-xhigh"}
    )
    assert r_conflict == {"argv": [], "reason": "engine-model-effort-conflict"}
    r_bare = EA.build_argv_result(
        "cursor", "review", None, {"engine_model": "cursor-grok-4.6"}
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
            "cursor-grok-4.6-xhigh",
        ]
    )
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out[out.index("--model") + 1] == "cursor-grok-4.6-xhigh"


def test_build_argv_result_seven_named_tokens():
    cases = [
        ("bogus", "review", "high", {}, "unknown-engine"),
        ("codex", "review", "high", {"model": "cursor-grok-4.6-xhigh"}, "unknown-claude-tier"),
        ("cursor", "review", "high", {"model": "cursor-grok-4.6-xhigh"}, "unknown-claude-tier"),
        ("codex", "build", "high", {"model": "fable"}, "fable-unrunnable"),
        ("cursor", "build", "composer", {"model": "fable"}, "fable-unrunnable"),
        ("codex", "review", "high", {"engine_model": "gpt-9"}, "unregistered-engine-model"),
        ("cursor", "review", "low", {"engine_model": "cursor-grok-4.6-xhigh"},
         "engine-model-effort-conflict"),
        ("cursor", "review", "max", {"engine_model": "cursor-grok-4.6"}, "invalid-model-effort"),
        ("cursor", "review", "high", {"engine_model": "composer-2.5"}, "invalid-model-effort"),
    ]
    for engine, role, effort, opts, want in cases:
        got = EA.build_argv_result(engine, role, effort, opts)
        assert got["argv"] == [] and got["reason"] == want, (engine, opts, got)


def test_build_argv_result_untokenizable(monkeypatch):
    real = EA.model_registry.dispatch_token

    def _fake(vendor, model_id, effort):
        if vendor == "cursor" and model_id == "cursor-grok-4.6" and effort == "xhigh":
            return None
        return real(vendor, model_id, effort)

    monkeypatch.setattr(EA.model_registry, "dispatch_token", _fake)
    got = EA.build_argv_result("cursor", "review", "xhigh", {"engine_model": "cursor-grok-4.6"})
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
    # 8 grok base + xhigh effort
    r = EA.build_argv_result("cursor", "review", "xhigh", {"engine_model": "cursor-grok-4.6"})
    assert r["argv"][r["argv"].index("--model") + 1] == "cursor-grok-4.6-xhigh"
    # 9 full composed token
    r = EA.build_argv_result("cursor", "review", "xhigh",
                             {"engine_model": "cursor-grok-4.6-xhigh"})
    assert r["argv"][r["argv"].index("--model") + 1] == "cursor-grok-4.6-xhigh"
    # 10 effort conflict — covered
    # 11 invalid effort max on grok base
    assert EA.build_argv_result("cursor", "review", "max",
                                {"engine_model": "cursor-grok-4.6"})["reason"] == "invalid-model-effort"
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
        ("cursor", "review", "xhigh", {"engine_model": "cursor-grok-4.6"}),
        ("cursor", "review", "high", {"model": "opus"}),
        ("bogus", "review", "high", {}),
    ]
    for engine, role, effort, opts in samples:
        assert EA.build_argv(engine, role, effort, opts) == EA.build_argv_result(
            engine, role, effort, opts)["argv"]


def test_build_argv_cli_refusal_object_shape(capsys):
    rc = EA.main(["build-argv", "--engine", "cursor", "--role", "review",
                  "--model", "cursor-grok-4.6-xhigh", "--effort", "high"])
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
    argv = EA.build_argv("cursor", "review", "xhigh", {"engine_model": "cursor-grok-4.6"})
    assert argv == [
        "cursor-agent", "--model", "cursor-grok-4.6-xhigh", "-p", "--trust",
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
    # #196: the rubric is the contract's home; this pin keeps the reference stating the complete
    # shape where an orchestrator composes the dispatch prompt — strengthened from the old incomplete
    # findings-only substring so a seat that omits investigated forfeits vacuously.
    ref = os.path.join(_HERE, "..", "..", "skills", "review-code", "reference", "auto-fix-loop.md")
    with open(ref, encoding="utf-8") as fh:
        text = fh.read()
    # the canonical required shape, verbatim
    assert '{"findings": [...], "investigated": [...]}' in text
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


# ---------------------------------------------------------------------------
# #811: salvage write reports after a forfeited external-engine attempt.


def _write_report(ok=True, signal="ok", test_failed=True, test_passed=True):
    return json.dumps({"ok": ok, "signal": signal,
                       "evidence": {"testFailed": test_failed, "testPassed": test_passed}})


def _contracted_report_tail(ok=True, signal="ok", test_failed=True, test_passed=True):
    """Prose-free tail matching I1 grammar (sentinel line + JSON object)."""
    return EA.WRITE_REPORT_SENTINEL + "\n" + _write_report(ok, signal, test_failed, test_passed)


def _stdout_with_contracted_report(prose="", ok=True, signal="ok", test_failed=True, test_passed=True):
    tail = _contracted_report_tail(ok, signal, test_failed, test_passed)
    if prose:
        return prose.rstrip() + "\n" + tail
    return tail


def test_salvage_write_report_recovers_stream_enveloped_report():
    report = _contracted_report_tail()
    assert EA.salvage_write_report("cursor", "build", _envelope(report), "fed prompt") == {
        "report": {"ok": True, "signal": "ok",
                   "evidence": {"testFailed": True, "testPassed": True}},
        "structured": True,
        "requiresManualRead": False,
        "salvaged": True,
    }


@pytest.mark.parametrize("stdout", [None, "", " \n\t", 7, []])
def test_salvage_write_report_empty_or_non_string_stdout_is_none(stdout):
    assert EA.salvage_write_report("codex", "build", stdout, "prompt") is None


@pytest.mark.parametrize("fed_prompt", [None, "", " \n\t", 7, []])
def test_salvage_write_report_empty_or_non_string_prompt_skips_strip(fed_prompt):
    result = EA.salvage_write_report("codex", "fix", _contracted_report_tail(), fed_prompt)
    assert result is not None and result["report"]["ok"] is True


def test_salvage_write_report_echo_only_residue_is_none():
    prompt = "Please implement this.\n" + _write_report()
    assert EA.salvage_write_report("codex", "build", prompt, prompt) is None


def test_salvage_write_report_rejects_echo_sourced_example():
    # axis: fabrication — a retained prompt example must not become a salvaged engine claim.
    example = _write_report()
    refusal_example = _write_report(False, "plan_wrong", True, False)
    prompt = "Write a report using this example:\n" + example + \
        "\nOr honestly refuse with:\n" + refusal_example
    stdout = "partial prompt echo follows:\n" + example
    assert EA.salvage_write_report("codex", "build", stdout, prompt) is None


def test_salvage_write_report_unreadable_is_none():
    # axis: fail-open on garbage — parse failure cannot mint a report.
    assert EA.salvage_write_report("codex", "build", "{not json", "prompt") is None


# Deliberate fake test credential; it is not a real leak.
_DISPATCH_1_PROSE = """Worktree changes left in:

- `plugins/superheroes/lib/engine_adapter.py`
- `plugins/superheroes/lib/tests/test_engine_adapter.py`

Implemented `salvage_write_report`, E1–E9 coverage, echo-fabrication rejection, refusal recovery,
truncation marking, and the 200-byte pin/absolute 195/205 boundary.

Bite-proofs B1–B4 each produced the expected red test result and were restored with targeted
inverse edits.

Command report:

- `/usr/bin/python3 -m pytest .../test_engine_adapter.py -q` initially ran: `198 passed in 4.40s`
- fake fixture credential: ghp_EXAMPLEfakenotarealtoken000000000
..."""


_DISPATCH_1_PROSE_REDACTED = """Worktree changes left in:

- `plugins/superheroes/lib/engine_adapter.py`
- `plugins/superheroes/lib/tests/test_engine_adapter.py`

Implemented `salvage_write_report`, E1–E9 coverage, echo-fabrication rejection, refusal recovery,
truncation marking, and the 200-byte pin/absolute 195/205 boundary.

Bite-proofs B1–B4 each produced the expected red test result and were restored with targeted
inverse edits.

Command report:

- `/usr/bin/python3 -m pytest .../test_engine_adapter.py -q` initially ran: `198 passed in 4.40s`
- fake fixture credential: [REDACTED]
..."""


def test_salvage_write_report_recovers_real_dispatch_prose_for_manual_read():
    # axis: C1 prose recovery — the measured forfeited artifact must not be written off as garbage.
    salvage = EA.salvage_write_report("codex", "build", _DISPATCH_1_PROSE, "fed prompt")
    prose_bytes = _DISPATCH_1_PROSE.encode("utf-8")
    truncated = len(prose_bytes) > EA.ARTIFACT_EXCERPT_BYTES
    assert salvage == {
        "report": None,
        "structured": False,
        "requiresManualRead": True,
        "excerpt": _DISPATCH_1_PROSE_REDACTED,
        "excerptBytes": len(_DISPATCH_1_PROSE_REDACTED.encode("utf-8")),
        "salvaged": True,
        "truncated": truncated,
    }


def test_salvage_write_report_prose_never_synthesizes_report():
    # axis: C2 fabrication — prose is a human pointer, never a gradeable result.
    salvage = EA.salvage_write_report("codex", "build", _DISPATCH_1_PROSE, "fed prompt")
    assert salvage is not None and salvage["report"] is None


@pytest.mark.parametrize("stdout, prompt", [
    ("Traceback (most recent call last):\n" + "frame\n" * 100, "fed prompt"),
    ("x" * (EA.ARTIFACT_MIN_RESIDUE_BYTES - 1), "fed prompt"),
    (_DISPATCH_1_PROSE, _DISPATCH_1_PROSE),
])
def test_salvage_write_report_rejects_traceback_below_floor_and_prompt_echo(stdout, prompt):
    # axis: C3 noise admission — crash dumps, short residue, and echo cannot become prose salvage.
    assert EA.salvage_write_report("codex", "build", stdout, prompt) is None


def test_salvage_write_report_prose_excerpt_caps_bytes_without_multibyte_failure():
    stdout = (_DISPATCH_1_PROSE + "\N{SNOWMAN}" * EA.ARTIFACT_EXCERPT_BYTES)
    salvage = EA.salvage_write_report("codex", "build", stdout, "fed prompt")
    assert salvage is not None
    assert salvage["excerptBytes"] == EA.ARTIFACT_EXCERPT_BYTES
    assert len(salvage["excerpt"].encode("utf-8")) <= EA.ARTIFACT_EXCERPT_BYTES


def test_salvage_write_report_honest_refusal_is_recovered():
    result = EA.salvage_write_report(
        "cursor", "fix", _contracted_report_tail(False, "plan_wrong", True, False), "prompt")
    assert result == {
        "report": {"ok": False, "signal": "plan_wrong",
                   "evidence": {"testFailed": True, "testPassed": False}},
        "structured": True,
        "requiresManualRead": False,
        "salvaged": True,
    }


def test_salvage_write_report_structured_ignores_partial_json_before_sentinel():
    stdout = 'Working...\n{"still-writing":\n' + _contracted_report_tail()
    result = EA.salvage_write_report("codex", "build", stdout, "prompt")
    assert result is not None and result["structured"] is True
    assert "truncated" not in result


def test_salvage_write_report_partial_json_after_sentinel_report_is_not_structured():
    stdout = _contracted_report_tail() + '\n{"still-writing":'
    result = EA.salvage_write_report("codex", "build", stdout, "prompt")
    assert result is None or result.get("structured") is not True


def test_salvage_write_report_does_not_structured_recover_markdown_checklist_prose():
    # axis: markdown prose before the sentinel tail still yields structured recovery.
    stdout = "Summary of work.\n- [x] tests green\n" + _contracted_report_tail()
    result = EA.salvage_write_report("codex", "build", stdout, "prompt")
    assert result is not None and result["structured"] is True
    assert "truncated" not in result


def test_salvage_write_report_rejects_review_role():
    assert EA.salvage_write_report("codex", "review", _contracted_report_tail(), "prompt") is None


def test_salvage_write_report_never_raises(monkeypatch):
    monkeypatch.setattr(EA, "_unwrap_stream_envelope", lambda _stdout: (_ for _ in ()).throw(RuntimeError()))
    assert EA.salvage_write_report("codex", "build", _contracted_report_tail(), "prompt") is None


# ---------------------------------------------------------------------------
# Write-report contract: extract_write_report, grade_write_report (I1–I4)


@pytest.mark.parametrize("text,expected", [
    ("Summary.\n" + EA.WRITE_REPORT_SENTINEL + '\n{"ok": true, "signal": "ok", "evidence": {}}',
     {"ok": True, "signal": "ok", "evidence": {}}),
    (EA.WRITE_REPORT_SENTINEL + '\n{"ok": true}\n  \n',
     {"ok": True}),
    ("  " + EA.WRITE_REPORT_SENTINEL + '\n{"ok": true, "signal": "ok", "evidence": {}}',
     {"ok": True, "signal": "ok", "evidence": {}}),
    (EA.WRITE_REPORT_SENTINEL + '\n{\n  "ok": true,\n  "signal": "ok",\n  "evidence": {}\n}\n',
     {"ok": True, "signal": "ok", "evidence": {}}),
    ("noise\n" + EA.WRITE_REPORT_SENTINEL + '\n{"ok": true}\n' + EA.WRITE_REPORT_SENTINEL +
     '\n{"ok": false, "signal": "plan_wrong"}',
     {"ok": False, "signal": "plan_wrong"}),
    (EA.WRITE_REPORT_SENTINEL + '\n{"ok": true}\nextra prose', None),
    (EA.WRITE_REPORT_SENTINEL + '\n{"ok": true, "trunc":', None),
    (EA.WRITE_REPORT_SENTINEL + '\n[1, 2]', None),
    (EA.WRITE_REPORT_SENTINEL + "\n", None),
    ('{"ok": true, "signal": "ok"}', None),
    ("text " + EA.WRITE_REPORT_SENTINEL + '\n{"ok": true}', None),
])
def test_extract_write_report_i1_grammar_adversarial(text, expected):
    got = EA.extract_write_report(text)
    assert got == expected


def _write_report_contract_example_tail():
    """The contract's final two lines (sentinel + placeholder object line)."""
    lines = EA.WRITE_REPORT_CONTRACT.split("\n")
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() == EA.WRITE_REPORT_SENTINEL:
            return "\n".join(lines[i:i + 2])
    raise AssertionError("WRITE_REPORT_CONTRACT missing sentinel example tail")


def _contract_echo_stdout_variants(fed_prompt):
    """Stdout shapes that echo all or part of the write-report contract."""
    contract = EA.WRITE_REPORT_CONTRACT
    example_tail = _write_report_contract_example_tail()
    return [
        ("whole_prompt", fed_prompt),
        ("contract_prefix_prose", "I did the work.\n\n" + contract),
        ("contract_suffix_prose", contract + "\n\nI did the work."),
        ("contract_whitespace_collapsed", re.sub(r"\s+", " ", contract)),
        ("contract_reindented", "\n".join("  " + line for line in contract.split("\n"))),
        ("example_tail_only", "Unrelated prose about the task.\n" + example_tail),
    ]


@pytest.mark.parametrize("variant_name,stdout", [
    (name, stdout)
    for name, stdout in _contract_echo_stdout_variants("Do the work.\n" + EA.WRITE_REPORT_CONTRACT)
])
def test_grade_write_report_echo_table_plain(variant_name, stdout):
    fed_prompt = "Do the work.\n" + EA.WRITE_REPORT_CONTRACT
    res = EA.grade_write_report("codex", "build", stdout, fed_prompt)
    assert res.get("ok") is not True, variant_name


@pytest.mark.parametrize("variant_name,stdout", [
    (name, stdout)
    for name, stdout in _contract_echo_stdout_variants("Do the work.\n" + EA.WRITE_REPORT_CONTRACT)
])
def test_grade_write_report_echo_table_stream_envelope(variant_name, stdout):
    fed_prompt = "Do the work.\n" + EA.WRITE_REPORT_CONTRACT
    res = EA.grade_write_report("cursor", "build", _envelope(stdout), fed_prompt)
    assert res.get("ok") is not True, variant_name


@pytest.mark.parametrize("variant_name,stdout", [
    (name, stdout)
    for name, stdout in _contract_echo_stdout_variants("Do the work.\n" + EA.WRITE_REPORT_CONTRACT)
])
def test_salvage_write_report_echo_table_not_structured(variant_name, stdout):
    fed_prompt = "Do the work.\n" + EA.WRITE_REPORT_CONTRACT
    salvage = EA.salvage_write_report("codex", "build", stdout, fed_prompt)
    assert salvage is None or salvage.get("structured") is not True, variant_name


def test_grade_write_report_genuine_ok_tail_still_passes():
    fed_prompt = "Do the work.\n" + EA.WRITE_REPORT_CONTRACT
    tail = EA.WRITE_REPORT_SENTINEL + '\n{"ok": true, "signal": "ok", "evidence": {}}'
    res = EA.grade_write_report("codex", "build", tail, fed_prompt)
    assert res == {"ok": True, "signal": "ok", "evidence": {"testFailed": False, "testPassed": False}}


def test_grade_write_report_genuine_refusal_still_grades():
    fed_prompt = "Do the work.\n" + EA.WRITE_REPORT_CONTRACT
    tail = EA.WRITE_REPORT_SENTINEL + '\n{"ok": false, "signal": "plan_wrong"}'
    res = EA.grade_write_report("codex", "build", tail, fed_prompt)
    assert res["ok"] is False and res["signal"] == "plan_wrong" and res["reason"] == "plan_wrong"


def test_grade_write_report_contract_echo_after_genuine_tail_still_grades():
    fed_prompt = "Do the work.\n" + EA.WRITE_REPORT_CONTRACT
    tail = EA.WRITE_REPORT_SENTINEL + '\n{"ok": true, "signal": "ok", "evidence": {}}'
    stdout = "Receipt prose.\n" + tail + "\n" + EA.WRITE_REPORT_CONTRACT
    res = EA.grade_write_report("codex", "build", stdout, fed_prompt)
    assert res == {"ok": True, "signal": "ok", "evidence": {"testFailed": False, "testPassed": False}}


def test_salvage_write_report_contract_echo_after_genuine_tail_still_structured():
    fed_prompt = "Do the work.\n" + EA.WRITE_REPORT_CONTRACT
    tail = EA.WRITE_REPORT_SENTINEL + '\n{"ok": true, "signal": "ok", "evidence": {}}'
    stdout = ("Long enough prose for salvage.\n" * 20) + tail + "\n" + EA.WRITE_REPORT_CONTRACT
    salvage = EA.salvage_write_report("codex", "build", stdout, fed_prompt)
    assert salvage is not None and salvage.get("structured") is True
    assert salvage["report"]["ok"] is True


def test_grade_write_report_rejects_prompt_decodable_example():
    example = {"ok": True, "signal": "ok", "evidence": {"testFailed": False, "testPassed": True}}
    fed_prompt = (
        "Do the work.\n"
        + EA.WRITE_REPORT_CONTRACT
        + "\nExample:\n"
        + json.dumps(example)
    )
    tail = EA.WRITE_REPORT_SENTINEL + "\n" + json.dumps(example)
    res = EA.grade_write_report("codex", "build", tail, fed_prompt)
    assert res == {"ok": False, "reason": "unreadable"}


def test_grade_write_report_prose_json_echo_from_order_does_not_false_forfeit():
    fed_prompt = (
        'Order: create a config file containing {"name": "widget", "enabled": true}\n'
        + EA.WRITE_REPORT_CONTRACT
    )
    tail = (
        EA.WRITE_REPORT_SENTINEL
        + '\n{"ok": true, "signal": "ok", "evidence": {"testFailed": false, "testPassed": true}}'
    )
    stdout = (
        'I created the config as specified: {"name": "widget", "enabled": true}\n'
        "All tests pass.\n"
        + tail
    )
    res = EA.grade_write_report("codex", "build", stdout, fed_prompt)
    assert res.get("ok") is True


def _salvage_prose_residue_splitting_framing_key(key, secret="supersecretvalue1234567890"):
    """Build prose residue where a raw tail slice would amputate the framing key."""
    marker = key + secret
    suffix_len = EA.ARTIFACT_EXCERPT_BYTES - len(secret)
    prose = marker + ("y" * suffix_len)
    # Tail slice must drop exactly len(key) bytes so the secret is wholly intact.
    assert len(prose.encode("utf-8")) > EA.ARTIFACT_EXCERPT_BYTES
    excerpt_raw = prose.encode("utf-8")[-EA.ARTIFACT_EXCERPT_BYTES:]
    assert excerpt_raw.startswith(secret.encode("utf-8"))
    return prose


@pytest.mark.parametrize("key", ["token=", "password=", "api_key="])
def test_salvage_write_report_prose_excerpt_scrubs_split_framing_keys(key):
    secret = "supersecretvalue1234567890"
    stdout = _salvage_prose_residue_splitting_framing_key(key, secret)
    salvage = EA.salvage_write_report("codex", "build", stdout, "fed prompt")
    assert salvage is not None
    assert secret not in salvage["excerpt"]


def test_salvage_write_report_prose_excerpt_still_scrubs_shape_bearing_token():
    secret = "ghp_" + ("a" * 36)
    stdout = _salvage_prose_residue_splitting_framing_key("token=", secret)
    salvage = EA.salvage_write_report("codex", "build", stdout, "fed prompt")
    assert salvage is not None
    assert secret not in salvage["excerpt"]


def test_write_report_contract_has_no_extractable_report():
    got = EA.extract_write_report(EA.WRITE_REPORT_CONTRACT)
    assert got is None, (
        "WRITE_REPORT_CONTRACT must not carry a decodable example report — "
        "an echoed contract block would grade as a false pass"
    )


def test_grade_write_report_i2_contracted_stray_json_is_unreadable():
    fed_prompt = "Order text.\n" + EA.WRITE_REPORT_CONTRACT
    stdout = 'Prose only.\n{"foo": 1}'
    res = EA.grade_write_report("codex", "build", stdout, fed_prompt)
    assert res == {"ok": False, "reason": "unreadable"}
    assert res.get("signal") != "needs_context"


def test_grade_write_report_i2_uncontracted_matches_parse_result():
    stdout = 'Prose only.\n{"foo": 1}'
    fed_prompt = "plain order without contract"
    legacy = EA.parse_result("codex", "build", stdout)
    assert EA.grade_write_report("codex", "build", stdout, fed_prompt) == legacy


@pytest.mark.parametrize("stdout,expected", [
    ('', {"ok": False, "reason": "unreadable"}),
    (json.dumps({"ok": True, "evidence": {"testFailed": False, "testPassed": True}}),
     {"ok": True, "signal": "ok", "evidence": {"testFailed": False, "testPassed": True}}),
    (json.dumps({"ok": False, "signal": "plan_wrong",
                 "evidence": {"testFailed": True, "testPassed": False}}),
     {"ok": False, "signal": "plan_wrong", "reason": "plan_wrong",
      "evidence": {"testFailed": True, "testPassed": False}}),
    (json.dumps({"ok": "false", "signal": "plan_wrong"}),
     {"ok": False, "signal": "plan_wrong", "reason": "plan_wrong",
      "evidence": {"testFailed": False, "testPassed": False}}),
])
def test_parse_result_i3_build_unchanged(stdout, expected):
    assert EA.parse_result("codex", "build", stdout) == expected


def test_salvage_write_report_i4_prose_fragment_without_sentinel_is_not_structured():
    prose = _DISPATCH_1_PROSE + '\n{"ok": true, "signal": "ok"}'
    salvage = EA.salvage_write_report("codex", "build", prose, "fed prompt")
    assert salvage is not None
    assert salvage["structured"] is not True
    assert salvage["requiresManualRead"] is True


def test_salvage_write_report_i4_sentinel_report_is_structured():
    stdout = _stdout_with_contracted_report("Long enough prose for salvage.\n" * 20)
    salvage = EA.salvage_write_report("codex", "build", stdout, "fed prompt")
    assert salvage is not None and salvage["structured"] is True
    assert salvage["report"]["ok"] is True


def test_grade_write_report_honest_refusal_round_trip():
    fed = EA.WRITE_REPORT_CONTRACT
    tail = EA.WRITE_REPORT_SENTINEL + '\n{"ok": false, "signal": "plan_wrong"}'
    res = EA.grade_write_report("codex", "build", "stopped.\n" + tail, fed)
    assert res["ok"] is False and res["signal"] == "plan_wrong" and res["reason"] == "plan_wrong"
    off = EA.WRITE_REPORT_SENTINEL + '\n{"ok": false, "signal": "owner-please-merge"}'
    res2 = EA.grade_write_report("codex", "build", off, fed)
    assert res2["ok"] is False and res2["signal"] == "needs_context"
    assert res2["reason"] == "needs_context"
    assert "owner" not in str(res2.get("signal", ""))


def test_write_prompt_is_contracted():
    assert EA.write_prompt_is_contracted("") is False
    assert EA.write_prompt_is_contracted("plain") is False
    assert EA.write_prompt_is_contracted("x\n" + EA.WRITE_REPORT_CONTRACT) is True
    assert EA.write_prompt_is_contracted("mentions " + EA.WRITE_REPORT_SENTINEL + " only") is True


def test_salvage_write_report_prose_excerpt_carries_tail_when_report_follows_signoff():
    signoff = "Thanks for reading.\n" * 3
    report_json = '{"ok": true, "signal": "ok", "evidence": {"testFailed": false, "testPassed": true}}'
    stdout = ("Long enough prose for salvage.\n" * 80) + EA.WRITE_REPORT_SENTINEL + "\n" + report_json + "\n" + signoff
    assert len(stdout.encode("utf-8")) > EA.ARTIFACT_EXCERPT_BYTES
    salvage = EA.salvage_write_report("codex", "build", stdout, "fed prompt")
    assert salvage is not None
    assert salvage["structured"] is not True
    assert salvage["requiresManualRead"] is True
    assert EA.WRITE_REPORT_SENTINEL in salvage["excerpt"]
    assert '"testPassed": true' in salvage["excerpt"]
    assert "Thanks for reading." in salvage["excerpt"]


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
    result = EA._last_json_object(blob)
    assert result is not None and result.get("findings")
    # #1132: the guarded property is BOUNDED WORK, not duration. The scan must attempt a decode
    # only at a plausible container start ('{' / '['), so raw_decode calls track the brace count
    # and NOT the blob length — the per-char exception storm of #563 would need one call per
    # character. Both legs below are operation counts against same-input bounds, so they hold
    # identically on an idle and on a loaded machine. The former `elapsed < 20.0` wall-clock
    # assertion measured the machine, not the code: it went red under sibling-build load with
    # this function untouched (two same-day specimens, PRs #1129 / #1130).
    assert calls[0] <= brace_count + 5, (
        "raw_decode count %d should track '{' count (~%d), not blob length (%d chars)"
        % (calls[0], brace_count, len(blob)))


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
    assert res["investigatedRejected"] == ["not-a-string"]
    assert res["investigatedRejectedRecords"][0]["reason"] == "not-a-string"


# ---------------------------------------------------------------------------
# #949: investigated parse boundary + findings fail-open closure


def test_parse_result_review_object_investigated_path_normalized():
    stdout = json.dumps({
        "findings": [],
        "investigated": [{"path": "src/a.py"}, {"file": "src/b.py"}],
    })
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    assert res["investigated"] == ["src/a.py", "src/b.py"]


def test_parse_result_review_object_investigated_path_wins_over_file():
    stdout = json.dumps({
        "findings": [],
        "investigated": [{"path": "from-path", "file": "from-file"}],
    })
    res = EA.parse_result("codex", "review", stdout)
    assert res["investigated"] == ["from-path"]


@pytest.mark.parametrize("entry,reason", [
    (42, "not-a-string"),
    ("", "empty-path"),
    ("   ", "empty-path"),
    ({"other": "x"}, "object-without-path"),
    ({"path": 7}, "invalid-path"),
    ({"path": {}}, "invalid-path"),
    ({"path": None}, "object-without-path"),
])
def test_parse_result_review_investigated_rejection_tokens(entry, reason):
    stdout = json.dumps({"findings": [], "investigated": ["good.py", entry]})
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    assert res["investigated"] == ["good.py"]
    assert reason in res["investigatedRejected"]
    assert any(r["reason"] == reason for r in res["investigatedRejectedRecords"])


def test_parse_result_review_all_findings_rejected_is_not_clean():
    stdout = json.dumps({"findings": [42], "investigated": ["real.py"]})
    assert EA.parse_result("codex", "review", stdout) == {"ok": False, "reason": "unreadable"}


def test_parse_result_review_empty_findings_with_valid_investigated_stays_clean():
    stdout = json.dumps({"findings": [], "investigated": ["src/main.py"]})
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    assert res["findings"] == []
    assert res["investigated"] == ["src/main.py"]


def test_parse_result_review_near_miss_investigated_only_is_clean():
    stdout = json.dumps({"investigated": ["src/main.py"]})
    res = EA.parse_result("codex", "review", stdout)
    assert res == {"ok": True, "resultKind": "findings",
                  "findings": [], "investigated": ["src/main.py"]}


def test_parse_result_review_error_object_with_investigated_stays_unreadable(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    real = repo_root / "existing.py"
    real.write_text("x", encoding="utf-8")
    rel = "existing.py"
    stdout = json.dumps({"type": "result", "status": "error", "investigated": [rel]})
    assert EA.parse_result("codex", "review", stdout) == {"ok": False, "reason": "unreadable"}
    inner = json.dumps({"type": "result", "status": "error", "investigated": [rel]})
    stream = _envelope(inner, subtype="error", is_error=True)
    assert EA.parse_result("cursor", "review", stream) == {"ok": False, "reason": "unreadable"}


def test_parse_result_cursor_error_envelope_near_miss_inner_unreadable(tmp_path):
    """#949 WO-4: outer error metadata must gate near-miss after envelope unwrap."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    real = repo_root / "real.py"
    real.write_text("x", encoding="utf-8")
    rel = "real.py"
    inner = json.dumps({"investigated": [rel]})
    stream = _envelope(inner, subtype="error", is_error=True)
    assert EA.parse_result("cursor", "review", stream) == {"ok": False, "reason": "unreadable"}


def test_parse_result_cursor_error_envelope_empty_findings_with_investigated_unreadable(tmp_path):
    """#949 WO-5: outer error envelope + empty findings must not certify clean."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    real = repo_root / "real.py"
    real.write_text("x", encoding="utf-8")
    rel = "real.py"
    inner = json.dumps({"findings": [], "investigated": [rel]})
    stream = _envelope(inner, subtype="error", is_error=True)
    assert EA.parse_result("cursor", "review", stream) == {"ok": False, "reason": "unreadable"}


def test_parse_result_cursor_error_envelope_real_findings_still_readable():
    inner = json.dumps({
        "findings": [{"id": "f1", "severity": "Minor", "title": "t", "body": "b"}],
        "investigated": ["src/main.py"],
    })
    res = EA.parse_result("cursor", "review", _envelope(inner, subtype="error", is_error=True))
    assert res["ok"] is True
    assert len(res["findings"]) == 1


def test_parse_result_cursor_error_envelope_non_json_inner_unreadable():
    stream = _envelope("not json at all", subtype="error", is_error=True)
    assert EA.parse_result("cursor", "review", stream) == {"ok": False, "reason": "unreadable"}


def test_parse_result_clean_envelope_empty_findings_with_investigated_readable(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    real = repo_root / "existing.py"
    real.write_text("x", encoding="utf-8")
    rel = "existing.py"
    inner = json.dumps({"findings": [], "investigated": [rel]})
    res = EA.parse_result("cursor", "review", _envelope(inner))
    assert res["ok"] is True
    assert res["findings"] == []
    assert res["investigated"] == [rel]


def test_parse_result_cursor_clean_envelope_near_miss_still_readable():
    inner = json.dumps({"investigated": ["src/main.py"]})
    res = EA.parse_result("cursor", "review", _envelope(inner))
    assert res == {"ok": True, "resultKind": "findings",
                  "findings": [], "investigated": ["src/main.py"]}


def test_parse_result_cursor_envelope_real_findings_unchanged():
    inner = json.dumps({"findings": [{"id": "f1", "severity": "Minor", "title": "t", "body": "b"}]})
    res = EA.parse_result("cursor", "review", _envelope(inner))
    assert res["ok"] is True
    assert len(res["findings"]) == 1
    assert res["findings"][0]["id"] == "f1"


def test_parse_result_review_investigated_not_a_list_rejected():
    stdout = json.dumps({"findings": [], "investigated": "not-a-list"})
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    assert res["investigated"] == []
    assert res["investigatedRejected"] == ["not-a-list"]


def test_parse_result_review_findings_not_a_list_unreadable():
    stdout = json.dumps({"findings": "nope", "investigated": ["a.py"]})
    assert EA.parse_result("codex", "review", stdout) == {"ok": False, "reason": "unreadable"}


def test_parse_result_review_neither_findings_nor_investigated_unreadable():
    assert EA.parse_result("codex", "review", json.dumps({"notes": "x"})) == \
        {"ok": False, "reason": "unreadable"}


def test_parse_result_review_empty_investigated_near_miss_unreadable():
    assert EA.parse_result("codex", "review", json.dumps({"investigated": []})) == \
        {"ok": False, "reason": "unreadable"}


def test_parse_result_review_rejected_findings_path_scrubs_secret():
    secret = "ghp_EXAMPLEfakenotarealtoken000000000"
    stdout = json.dumps({
        "findings": [f"leak {secret}", {"id": "f1", "title": "ok"}],
        "investigated": ["ok.py"],
    })
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    assert len(res["findings"]) == 1
    assert res["findings"][0]["id"] == "f1"
    assert res["findingsRejected"] == ["not-a-dict"]
    blob = json.dumps(res["findingsRejectedRecords"])
    assert secret not in blob
    assert "[REDACTED]" in blob


# ---------------------------------------------------------------------------
# #1003: hollow finding members are not findings


_HOLLOW_MEMBER_MALFORMED = {"ok": False, "reason": "unreadable"}


@pytest.mark.parametrize("stdout", [
    json.dumps({"findings": [{}]}),
    json.dumps({"findings": [{}, {}]}),
    json.dumps({"findings": [{}, {"severity": "Minor", "title": "t", "body": "b"}]}),
    json.dumps({"findings": [{}, 42]}),
    json.dumps([{}]),
    json.dumps([{}, {"severity": "Minor", "title": "t", "body": "b"}]),
    json.dumps({"findings": [{"title": "   "}]}),
    json.dumps({"findings": [{"title": False}]}),
    json.dumps({"findings": [{"title": 0}]}),
    json.dumps({"findings": [{"body": []}]}),
    json.dumps({"findings": [{"body": [{}]}]}),
    json.dumps({"findings": [{"line": 3, "severity": "Critical"}]}),
    json.dumps({"findings": [{"tradeoff": False}]}),
])
def test_parse_result_review_hollow_member_classifies_malformed(stdout):
    assert EA.parse_result("codex", "review", stdout) == _HOLLOW_MEMBER_MALFORMED


def _substance_value_quality_cases():
    keys = sorted(EA._FINDING_SUBSTANCE_KEYS_CANONICAL | EA._FINDING_SUBSTANCE_KEYS_TOLERATED)
    cases = []
    for key in keys:
        for value in (None, "", "   ", [], {}, (), 0, False, True):
            cases.append((key, value, False))
        cases.append((key, "x", True))
    return cases


@pytest.mark.parametrize("key,value,substantive", _substance_value_quality_cases())
def test_finding_is_substantive_value_quality_matrix(key, value, substantive):
    finding = {key: value}
    assert EA._finding_is_substantive(finding) is substantive


def test_parse_result_review_edge6_non_dict_plus_survivor_stays_ok():
    stdout = json.dumps({"findings": [42, {"id": "f1", "title": "ok"}]})
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    assert len(res["findings"]) == 1
    assert res["findings"][0]["id"] == "f1"
    assert res["findingsRejected"] == ["not-a-dict"]


def test_parse_result_review_edge7_empty_findings_with_investigated_stays_clean():
    stdout = json.dumps({"findings": [], "investigated": ["a.py"]})
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    assert res["findings"] == []
    assert res["investigated"] == ["a.py"]


def test_parse_result_review_edge8_near_miss_no_findings_stays_clean():
    stdout = json.dumps({"investigated": ["a.py"]})
    res = EA.parse_result("codex", "review", stdout)
    assert res == {"ok": True, "resultKind": "findings",
                  "findings": [], "investigated": ["a.py"]}


def test_parse_result_review_edge13_common_corpus_shape_stays_ok():
    stdout = json.dumps({"findings": [{"body": "b", "severity": "Minor", "title": "t"}]})
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    assert len(res["findings"]) == 1
    assert res["findings"][0]["title"] == "t"


def test_parse_result_review_edge14_error_envelope_hollow_inner():
    inner = json.dumps({"findings": [{}], "investigated": ["real.py"]})
    stream = _envelope(inner, subtype="error", is_error=True)
    assert EA.parse_result("cursor", "review", stream) == _HOLLOW_MEMBER_MALFORMED


def test_parse_result_review_tolerated_summary_alias_parses():
    stdout = json.dumps({"findings": [{"summary": "issue summary"}]})
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    assert len(res["findings"]) == 1
    assert res["findings"][0]["summary"] == "issue summary"


def test_parse_result_review_tolerated_message_alias_parses():
    stdout = json.dumps({"findings": [{"message": "issue found"}]})
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    assert len(res["findings"]) == 1
    assert res["findings"][0]["message"] == "issue found"


def test_parse_result_review_tolerated_description_alias_parses():
    stdout = json.dumps({"findings": [{"description": "a real problem"}]})
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    assert len(res["findings"]) == 1
    assert res["findings"][0]["description"] == "a real problem"


def test_finding_reject_no_substance_constant_matches_wire_value():
    assert EA.FINDING_REJECT_NO_SUBSTANCE == "no-substantive-fields"


def test_scrub_findings_rejects_hollow_with_named_reason():
    accepted, rejected = EA._scrub_findings([{}])
    assert accepted == []
    assert len(rejected) == 1
    assert rejected[0]["reason"] == "no-substantive-fields"


def test_finding_substance_keys_canonical_membership():
    assert EA._FINDING_SUBSTANCE_KEYS_CANONICAL == frozenset(
        {"title", "body", "evidence", "suggestion"}
    )


def test_finding_substance_keys_tolerated_membership():
    assert EA._FINDING_SUBSTANCE_KEYS_TOLERATED == frozenset(
        {"summary", "message", "description"}
    )


def test_finding_substance_keys_canonical_subset_of_schema():
    schema_path = os.path.join(_HERE, "..", "schemas", "review-findings.schema.json")
    with open(schema_path, encoding="utf-8") as fh:
        schema = json.load(fh)
    schema_props = set(schema["properties"]["findings"]["items"]["properties"].keys())
    missing = EA._FINDING_SUBSTANCE_KEYS_CANONICAL - schema_props
    assert not missing, "canonical substance keys drifted from schema: %s" % sorted(missing)


@pytest.mark.parametrize("stdout", [
    json.dumps({"findings": [{}]}),
])
def test_review_payload_shape_hollow_object_branch(stdout):
    res = EA.review_payload_shape(stdout)
    assert res == {
        "parsed": EA.SHAPE_FINDINGS_HOLLOW_MEMBER, "topLevelKeys": [], "keysTruncated": False,
    }


def test_review_payload_shape_hollow_bare_array():
    res = EA.review_payload_shape(json.dumps([{}]))
    assert res == {
        "parsed": EA.SHAPE_FINDINGS_HOLLOW_MEMBER, "topLevelKeys": [], "keysTruncated": False,
    }


def test_salvage_from_artifact_hollow_findings_requires_manual_read():
    stdout = json.dumps({"findings": [{}]})
    salvage = EA.salvage_from_artifact(stdout, "")
    assert salvage["structured"] is False
    assert salvage["requiresManualRead"] is True
    assert salvage["findings"] == []


def test_parse_result_review_rejected_investigated_path_scrubs_secret():
    secret = "ghp_EXAMPLEfakenotarealtoken000000000"
    stdout = json.dumps({
        "findings": [],
        "investigated": [{"path": {"nested": secret}}, "ok.py"],
    })
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    assert res["investigated"] == ["ok.py"]
    assert res["investigatedRejected"] == ["invalid-path"]
    blob = json.dumps(res["investigatedRejectedRecords"])
    assert secret not in blob
    assert "[REDACTED]" in blob


def test_parse_result_review_never_raises_on_fail_closed_edges():
    shapes = [
        (json.dumps({"findings": [], "investigated": None}),
         {"ok": True, "resultKind": "findings", "findings": [], "investigated": [],
          "investigatedRejected": ["not-a-list"]}),
        (json.dumps({"findings": None, "investigated": ["a.py"]}),
         {"ok": False, "reason": "unreadable"}),
        (json.dumps({"findings": 1, "investigated": ["a.py"]}),
         {"ok": False, "reason": "unreadable"}),
        (json.dumps({"investigated": {"path": "a.py"}}),
         {"ok": False, "reason": "unreadable"}),
    ]
    for stdout, expected in shapes:
        res = EA.parse_result("codex", "review", stdout)
        assert isinstance(res, dict)
        for key, val in expected.items():
            assert res.get(key) == val, (stdout, key, res)


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


def test_spot_check_investigated_rejects_embedded_nul(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    hostile = "a.py\x00evil"
    ok, accepted, rejected = EA.spot_check_investigated([hostile], str(root))
    assert ok is False
    assert accepted == []
    assert rejected == [{"path": hostile, "reason": "invalid-path"}]


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


_PATCH_NAME = "SUPERHEROES_REVIEW_DIFF.patch"


def _repo_with_source_and_patch(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    source = root / "src.py"
    source.write_text("x", encoding="utf-8")
    patch = root / _PATCH_NAME
    patch.write_text("diff --git\n", encoding="utf-8")
    return str(root), source, patch


def test_spot_check_generated_artifacts_not_passed_behaves_as_today(tmp_path):
    """E3: omitting generated_artifacts keeps back-compat."""
    root, source, patch = _repo_with_source_and_patch(tmp_path)
    ok, accepted, rejected = EA.spot_check_investigated(
        ["src.py", _PATCH_NAME], root)
    assert ok is True
    assert accepted == ["src.py", _PATCH_NAME]
    assert rejected == []


def test_spot_check_generated_artifacts_none_or_non_iterable_treated_empty(tmp_path):
    """E4: None or non-iterable generated_artifacts never raises."""
    root, source, _patch = _repo_with_source_and_patch(tmp_path)
    for artifacts in (None, 42, object()):
        ok, accepted, rejected = EA.spot_check_investigated(
            ["src.py"], root, generated_artifacts=artifacts)
        assert ok is True and accepted == ["src.py"] and rejected == []


def test_spot_check_generated_artifacts_ignores_bad_entries(tmp_path):
    """E5: non-string or empty-string artifact entries are ignored."""
    root, source, patch = _repo_with_source_and_patch(tmp_path)
    ok, accepted, rejected = EA.spot_check_investigated(
        ["src.py"], root, generated_artifacts=(None, "", 7, _PATCH_NAME))
    assert ok is True and accepted == ["src.py"]
    assert rejected == []


def test_spot_check_nonexistent_artifact_path_ignored(tmp_path):
    """E6: artifact path that does not exist cannot match anything."""
    root, source, _patch = _repo_with_source_and_patch(tmp_path)
    ok, accepted, rejected = EA.spot_check_investigated(
        [_PATCH_NAME], root, generated_artifacts=("no-such.patch",))
    assert ok is True and accepted == [_PATCH_NAME]
    assert rejected == []


def test_spot_check_rejects_artifact_by_plain_name(tmp_path):
    """E7: investigated cites the staged patch by plain name."""
    root, _source, _patch = _repo_with_source_and_patch(tmp_path)
    ok, accepted, rejected = EA.spot_check_investigated(
        [_PATCH_NAME], root, generated_artifacts=(_PATCH_NAME,))
    assert ok is False and accepted == []
    assert rejected == [{"path": _PATCH_NAME, "reason": "generated-artifact"}]


def test_spot_check_rejects_artifact_by_dotdot_spelling(tmp_path):
    """E8: resolved identity, not spelling — ./NAME and sub/../NAME."""
    root, _source, _patch = _repo_with_source_and_patch(tmp_path)
    for entry in ("./%s" % _PATCH_NAME, "sub/../%s" % _PATCH_NAME):
        ok, accepted, rejected = EA.spot_check_investigated(
            [entry], root, generated_artifacts=(_PATCH_NAME,))
        assert ok is False and accepted == []
        assert rejected[0]["reason"] == "generated-artifact"


def test_spot_check_rejects_hard_link_to_artifact(tmp_path):
    """E9: hard-linked spelling rejected via samefile when realpath strings differ."""
    root, _source, patch = _repo_with_source_and_patch(tmp_path)
    link = os.path.join(root, "via-hardlink")
    os.link(patch, link)
    inv_real = os.path.realpath(os.path.join(root, "via-hardlink"))
    art_real = os.path.realpath(os.path.join(root, _PATCH_NAME))
    assert inv_real != art_real
    ok, accepted, rejected = EA.spot_check_investigated(
        ["via-hardlink"], root, generated_artifacts=(_PATCH_NAME,))
    assert ok is False and accepted == []
    assert rejected[0]["reason"] == "generated-artifact"


def test_spot_check_rejects_symlink_to_artifact(tmp_path):
    """E9b: genuine symlink spelling rejected via realpath identity."""
    root, _source, patch = _repo_with_source_and_patch(tmp_path)
    link = os.path.join(root, "via-symlink")
    os.symlink(patch, link)
    ok, accepted, rejected = EA.spot_check_investigated(
        ["via-symlink"], root, generated_artifacts=(_PATCH_NAME,))
    assert ok is False and accepted == []
    assert rejected[0]["reason"] == "generated-artifact"


def test_spot_check_only_artifact_fails_floor(tmp_path):
    """E10: citing only the artifact fails the investigation floor."""
    root, _source, _patch = _repo_with_source_and_patch(tmp_path)
    ok, accepted, rejected = EA.spot_check_investigated(
        [_PATCH_NAME], root, generated_artifacts=(_PATCH_NAME,))
    assert ok is False and accepted == []


def test_spot_check_artifact_plus_source_passes_on_source(tmp_path):
    """E11: artifact rejected but a real source file still clears the floor."""
    root, _source, _patch = _repo_with_source_and_patch(tmp_path)
    ok, accepted, rejected = EA.spot_check_investigated(
        [_PATCH_NAME, "src.py"], root, generated_artifacts=(_PATCH_NAME,))
    assert ok is True and accepted == ["src.py"]
    assert rejected == [{"path": _PATCH_NAME, "reason": "generated-artifact"}]


def test_spot_check_same_name_without_generated_artifacts_accepted(tmp_path):
    """E12: tracked file sharing the patch name is ordinary source when no artifact list."""
    root, _source, _patch = _repo_with_source_and_patch(tmp_path)
    ok, accepted, rejected = EA.spot_check_investigated([_PATCH_NAME], root)
    assert ok is True and accepted == [_PATCH_NAME]
    assert rejected == []


def test_spot_check_samefile_raises_falls_back_to_realpath(tmp_path, monkeypatch):
    """E13: os.path.samefile failure falls back to realpath comparison."""
    root, _source, _patch = _repo_with_source_and_patch(tmp_path)
    real_samefile = os.path.samefile

    def _boom(a, b):
        raise OSError("permission denied")

    monkeypatch.setattr(os.path, "samefile", _boom)
    ok, accepted, rejected = EA.spot_check_investigated(
        [_PATCH_NAME], root, generated_artifacts=(_PATCH_NAME,))
    assert ok is False and accepted == []
    assert rejected[0]["reason"] == "generated-artifact"
    monkeypatch.setattr(os.path, "samefile", real_samefile)


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
    monkeypatch.setattr(EA, "normalize_review_stdout", lambda stdout, fed_prompt=None: {
        "text": '{"error": true}', "rawEnvelopeError": False, "echoOnly": False,
    })
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


# ---------------------------------------------------------------------------
# #747 WO-4a: review_artifact_shape + salvage_from_artifact


def _artifact_pad(text, min_bytes=EA.ARTIFACT_MIN_RESIDUE_BYTES + 20):
    out = text
    while len(out.encode("utf-8")) < min_bytes:
        out += " Additional review context padding."
    return out


def _artifact_corpus_poster_child_1():
    cites = ["src/app/widget.ts:42", "src/lib/util.ts:7", "src/app/model.ts:15",
             "tests/widget.test.ts:88", "src/app/view.ts:3"]
    lines = ["Review of the widget module identified several concerns."]
    lines += ["- %s: null check missing" % c for c in cites[:3]]
    lines += ["Also noted %s and %s in related files." % (cites[3], cites[4])]
    return _artifact_pad("\n".join(lines))


def _artifact_corpus_poster_child_2():
    cites = ["src/core/handler.ts:12", "src/core/router.ts:44", "src/api/route.ts:9"]
    lines = ["Shorter follow-up review after fixes."]
    lines += ["- %s: still racy" % c for c in cites[:2]]
    lines += ["Cross-check %s before merge." % cites[2]]
    return _artifact_pad("\n".join(lines))


def _artifact_corpus_brief_check():
    cites = ["src/a.ts:%d" % i for i in range(1, 10)]
    lines = ["Brief check across the service layer."]
    lines += ["- %s: style" % c for c in cites[:3]]
    lines += ["References: " + ", ".join(cites)]
    return _artifact_pad("\n".join(lines))


def _artifact_corpus_clean_prose_701():
  lines = ["### Findings", "", "The change looks broadly sound but needs polish."]
  lines += ["- missing edge case for empty input"]
  lines += ["- error message could be clearer"]
  lines += ["- consider extracting helper"]
  lines += ["- naming inconsistency in tests"]
  lines += ["- docstring drift on public API"]
  lines += ["- logging level too noisy"]
  lines += ["- follow-up ticket for perf"]
  lines += ["", "### Investigation record", "", "Read the diff and nearby callers."]
  return _artifact_pad("\n".join(lines))


def _artifact_corpus_investigation_record():
  lines = ["INVESTIGATION RECORD", ""]
  lines += ["- checked auth middleware"]
  lines += ["- traced request path"]
  lines += ["- verified test coverage"]
  lines += ["- read config defaults"]
  lines += ["- compared with prior PR"]
  lines += ["- inspected error handling"]
  lines += ["- reviewed logging"]
  lines += ["- scanned for secrets"]
  lines += ["- validated schema"]
  lines += ["- noted TODO markers"]
  lines += ["- checked imports"]
  lines += ["- reviewed types"]
  lines += ["- scanned callers"]
  lines += ["- read related docs"]
  lines += ["- checked feature flag"]
  lines += ["- verified rollback path"]
  lines += ["- noted migration risk"]
  lines += ["- confirmed owner intent"]
  lines += ["- no blocking issues found"]
  return _artifact_pad("\n".join(lines))


def _artifact_corpus_approve_with_reasoning():
  lines = ["## Verdict", "", "Approve with minor notes.", "", "## Findings"]
  lines += ["- doc nit"]
  lines += ["- test name"]
  lines += ["- comment clarity"]
  lines += ["- optional refactor"]
  return _artifact_pad("\n".join(lines))


def _artifact_corpus_json_control():
    return json.dumps({"ok": True, "findings": [
        {"severity": "Minor", "title": "t", "body": "b"}]})


@pytest.mark.parametrize("stdout,expected_basis", [
    (_artifact_corpus_poster_child_1(), ["citations", "enumerations"]),
    (_artifact_corpus_poster_child_2(), ["citations", "enumerations"]),
    (_artifact_corpus_brief_check(), ["citations", "enumerations"]),
    (_artifact_corpus_clean_prose_701(), ["enumerations", "sections"]),
    (_artifact_corpus_investigation_record(), ["enumerations", "sections"]),
    (_artifact_corpus_approve_with_reasoning(), ["enumerations", "sections"]),
])
def test_review_artifact_shape_corpus_specimens_engaged(stdout, expected_basis):
    shape = EA.review_artifact_shape(stdout, "fed prompt not echoed here")
    assert shape["engaged"] is True
    assert shape["basis"] == expected_basis
    assert shape["residueBytes"] >= EA.ARTIFACT_MIN_RESIDUE_BYTES


def test_review_artifact_shape_json_control_not_engaged():
    stdout = _artifact_corpus_json_control()
    shape = EA.review_artifact_shape(stdout, "")
    assert shape["engaged"] is False
    assert shape["basis"] is None


def test_review_artifact_shape_empty_stdout():
    assert EA.review_artifact_shape("", "prompt")["engaged"] is False
    assert EA.review_artifact_shape("", "prompt")["residueBytes"] == 0


def test_review_artifact_shape_whitespace_only_stdout():
    shape = EA.review_artifact_shape("   \n\t", "prompt")
    assert shape["engaged"] is False
    assert shape["residueBytes"] == 0


def test_review_artifact_shape_echo_only_residue_empty():
    prompt = "review this diff carefully\n- src/a.ts:1\n1. first step"
    assert EA.review_artifact_shape(prompt, prompt)["engaged"] is False


def test_review_artifact_shape_one_line_engine_error_under_floor():
    shape = EA.review_artifact_shape("error: model not found", "")
    assert shape["engaged"] is False
    assert shape["residueBytes"] < EA.ARTIFACT_MIN_RESIDUE_BYTES


def test_review_artifact_shape_flat_prose_no_signals():
    prose = " ".join(["flat"] * 80)  # ~400 bytes, no cites/enums/sections
    shape = EA.review_artifact_shape(prose, "")
    assert shape["engaged"] is False
    assert shape["citations"] == 0
    assert shape["enumerations"] == 0
    assert shape["sections"] == []


def test_review_artifact_shape_rejects_partial_prompt_echo():
    # axis: rejection before signals — prompt-echo residue must not score
    middle = (
        "Please review:\n- src/prompt/file.ts:99\n1. step one\n2. step two\n"
        + "Reviewer instructions continue here. " * 8
    )
    assert len(middle.encode("utf-8")) >= EA.ARTIFACT_MIN_RESIDUE_BYTES
    fed = "HEADER\n" + middle + "\nTRAILER"
    fragment = middle
    assert fragment in fed
    shape = EA.review_artifact_shape(fragment, fed)
    assert shape["engaged"] is False
    assert shape["citations"] >= 1
    assert shape["enumerations"] >= 2


def test_review_artifact_shape_rg_output_one_signal_only():
    lines = ["%s/file%d.ts:%d:match" % ("src", i, i) for i in range(20)]
    stdout = "\n".join(lines)
    shape = EA.review_artifact_shape(stdout, "")
    assert shape["engaged"] is False
    assert shape["citations"] >= 1
    assert shape["enumerations"] == 0
    assert shape["sections"] == []


def test_review_artifact_shape_rejects_traceback():
    # axis: rejection before signals — traceback/stack-dump must not score
    tb = "Traceback (most recent call last):\n  File \"src/a.py\", line 1, in <module>\n"
    tb += "    raise RuntimeError('boom')\n" + "- src/a.py:1 note\n" * 5
    shape = EA.review_artifact_shape(_artifact_pad(tb), "")
    assert shape["engaged"] is False


def test_review_artifact_shape_plan_only_stream_log_not_engaged():
    events = [
        {"type": "tool_call", "call_id": "c1", "name": "read", "args": {"path": "src/a.ts"}},
        {"type": "tool_call", "call_id": "c2", "name": "grep", "args": {"pattern": "foo"}},
    ]
    stream = "\n".join(json.dumps(e) for e in events)
    inner = stream + "\nPlanning next steps across src/a.ts:1 and src/b.ts:2."
    envelope = json.dumps({"type": "result", "result": inner})
    shape = EA.review_artifact_shape(envelope, "dispatch prompt")
    assert shape["engaged"] is False


def test_review_artifact_shape_residue_byte_floor():
    # axis: ARTIFACT_MIN_RESIDUE_BYTES floor independent of signal count
    core = "- src/a.ts:1 issue\n- src/b.ts:2 issue\n### Findings\n"
    below = core + "x" * (195 - len(core.encode("utf-8")))
    above = core + "x" * (205 - len(core.encode("utf-8")))
    just_below = core + "x" * (199 - len(core.encode("utf-8")))
    at_floor = core + "x" * (200 - len(core.encode("utf-8")))
    assert len(below.encode("utf-8")) == 195
    assert len(above.encode("utf-8")) == 205
    assert len(just_below.encode("utf-8")) == 199
    assert len(at_floor.encode("utf-8")) == 200
    assert EA.review_artifact_shape(below, "")["engaged"] is False
    assert EA.review_artifact_shape(above, "")["engaged"] is True
    assert EA.review_artifact_shape(just_below, "")["engaged"] is False
    assert EA.review_artifact_shape(at_floor, "")["engaged"] is True


def test_artifact_min_residue_bytes_is_deliberately_pinned():
    # 200 rejects one-line engine errors; changing it is a deliberate calibration change, not a refactor.
    assert EA.ARTIFACT_MIN_RESIDUE_BYTES == 200


def test_review_artifact_shape_requires_two_of_three_signals():
    # axis: how many review signals are required (two-of-three, not one-of-three)
    cites_only = "\n".join("src/f%d.ts:%d" % (i, i) for i in range(30))
    cites_only = _artifact_pad(cites_only)
    shape_one = EA.review_artifact_shape(cites_only, "")
    assert shape_one["engaged"] is False
    assert shape_one["citations"] >= 1
    assert shape_one["enumerations"] == 0
    assert shape_one["sections"] == []
    with_enum = cites_only + "\n- first note\n- second note"
    assert EA.review_artifact_shape(with_enum, "")["engaged"] is True


def test_review_artifact_shape_none_stdout_not_engaged():
    shape = EA.review_artifact_shape(None, "prompt")
    assert shape["engaged"] is False
    assert shape["residueBytes"] == 0


def test_review_artifact_shape_empty_fed_prompt_still_grades():
    stdout = _artifact_corpus_poster_child_1()
    assert EA.review_artifact_shape(stdout, None)["engaged"] is True
    assert EA.review_artifact_shape(stdout, "")["engaged"] is True


def test_review_artifact_shape_stray_bracket_array_parse_and_engaged():
    # Deliberately unchanged: parse_result still treats bare [] as clean zero findings;
    # follow-up routes that false-clean seam through salvage/outcome minting.
    prose = _artifact_pad("### Findings\n\n[]\n\n- real issue at src/x.ts:1\n- second point")
    parsed = EA.parse_result("codex", "review", EA.strip_echoed_prompt(prose, ""))
    assert parsed["ok"] is True
    assert parsed["findings"] == []
    assert EA.review_artifact_shape(prose, "")["engaged"] is True


def test_salvage_from_artifact_false_clean_engaged_empty_parse():
    # axis: whether a parse counts as structured — engaged prose with incidental [] is not structured.
    prose = _artifact_pad("### Findings\n\n[]\n\n- real issue at src/x.ts:1\n- second point")
    salvage = EA.salvage_from_artifact(prose, "")
    assert salvage["structured"] is False
    assert salvage["requiresManualRead"] is True
    assert salvage["findings"] == []
    assert salvage["excerpt"]


def test_salvage_from_artifact_non_engaged_empty_json_structured():
    stdout = json.dumps({"findings": []})
    salvage = EA.salvage_from_artifact(stdout, "")
    assert EA.review_artifact_shape(stdout, "")["engaged"] is False
    assert salvage["structured"] is True
    assert salvage["requiresManualRead"] is False
    assert salvage["findings"] == []


def test_salvage_from_artifact_structured_json():
    stdout = json.dumps({"findings": [
        {"severity": "Minor", "title": "t", "body": "b", "file": "a.py", "line": 1}]})
    salvage = EA.salvage_from_artifact(stdout, "")
    assert salvage["structured"] is True
    assert salvage["requiresManualRead"] is False
    assert len(salvage["findings"]) == 1
    assert salvage["excerpt"]


def test_salvage_from_artifact_prose_manual_read():
    stdout = _artifact_corpus_clean_prose_701()
    salvage = EA.salvage_from_artifact(stdout, "")
    assert salvage["structured"] is False
    assert salvage["requiresManualRead"] is True
    assert salvage["findings"] == []
    assert salvage["excerpt"]
    assert salvage["excerptBytes"] <= EA.ARTIFACT_EXCERPT_BYTES


def test_salvage_from_artifact_excerpt_capped():
    stdout = "x" * (EA.ARTIFACT_EXCERPT_BYTES + 500)
    salvage = EA.salvage_from_artifact(stdout, "")
    assert salvage["excerptBytes"] == EA.ARTIFACT_EXCERPT_BYTES
    assert len(salvage["excerpt"].encode("utf-8")) <= EA.ARTIFACT_EXCERPT_BYTES + 4


def test_sanitized_view_receipt_binds_producer_diff_keys(tmp_path):
    """Producer build_sanitized_view diff keys must reach _sanitized_view_receipt."""
    import subprocess as sp
    import sys

    lib = os.path.join(_HERE, "..")
    if lib not in sys.path:
        sys.path.insert(0, lib)
    import sanitized_view as sv
    ed_spec = importlib.util.spec_from_file_location(
        "engine_dispatch_receipt_bind",
        os.path.join(lib, "engine_dispatch.py"),
    )
    ed = importlib.util.module_from_spec(ed_spec)
    ed_spec.loader.exec_module(ed)

    repo = tmp_path / "receipt-bind"
    os.makedirs(repo, exist_ok=True)
    sp.run(["git", "-C", str(repo), "init", "-q"], check=True)
    with open(repo / "keep.txt", "w", encoding="utf-8") as fh:
        fh.write("k\n")
    sp.run(["git", "-C", str(repo), "add", "-A"], check=True)
    sp.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.email=test@test.local",
            "-c",
            "user.name=test",
            "commit",
            "-q",
            "-m",
            "init",
        ],
        check=True,
    )
    base_sha = sp.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    with open(repo / "keep.txt", "w", encoding="utf-8") as fh:
        fh.write("changed\n")
    sp.run(["git", "-C", str(repo), "add", "keep.txt"], check=True)
    sp.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.email=test@test.local",
            "-c",
            "user.name=test",
            "commit",
            "-q",
            "-m",
            "change",
        ],
        check=True,
    )

    fake_tmp = str(tmp_path / "sanitized-temp-base")
    os.makedirs(fake_tmp, exist_ok=True)
    import tempfile as tf

    orig_gettempdir = tf.gettempdir
    tf.gettempdir = lambda: fake_tmp
    try:
        view = sv.build_sanitized_view(str(repo), diff_base=base_sha)
        receipt = ed._sanitized_view_receipt(view)
        assert receipt["diffBase"] == view["diffBase"]
        assert receipt["diffPath"] == view["diffPath"]
        assert receipt["diffBytes"] == view["diffBytes"]
        assert receipt["diffWithheldCount"] == view["diffWithheldCount"]
        assert receipt["diffBase"] is not None
        assert receipt["diffPath"] is not None
        assert receipt["diffBytes"] is not None
        assert receipt["diffWithheldCount"] is not None
    finally:
        tf.gettempdir = orig_gettempdir
        if "view" in locals():
            sv.destroy_sanitized_view(view["path"])


# ---------------------------------------------------------------------------
# #763: review parse layer — verdicts result kind + normalize_review_stdout


# RETIRED (#1147): `test_verdicts_constant_matches_verification_module` asserted
# `EA.VERDICTS == verification.VERDICTS`. It was written when the two modules each held their own
# literal tuple, so the comparison could catch the vocabularies drifting apart. Since #1123
# collapsed the definition, BOTH names are bindings of the SAME object —
# `engine_adapter.VERDICTS = round_phases.VERDICTS` and `verification.VERDICTS =
# round_phases.VERDICTS` — so the assertion compared a value against itself. Be exact about what
# that means, because the imprecise version of this sentence was itself a review finding: the
# assertion could not fail for ANY EDIT TO THE SHARED DEFINITION it claimed to pin. Mutating
# `round_phases.VERDICTS` moved both operands together and left it green (proved by probe: the
# mutation reddened a real consumer, `test_round_adapters.py::test_verifier_payload_faults`, while
# this test stayed green). It retained exactly one residual bite — an edit REBINDING either alias
# to a fresh literal, re-splitting the vocabulary — which is not the drift it was written for and
# is not what its name claims it covers. A guard that cannot fail on the axis it advertises is
# worse than no guard: it reads as coverage while pinning nothing, so the surface looks watched
# when it is not. Retired rather than repaired, per the owner-ruled scope. KNOWN RESIDUAL, carried
# to the PR: no test now pins either alias to `round_phases.VERDICTS` (the layering suite's
# re-export identity test at `test_payload_contracts_layering.py` covers payload-contract names,
# not this one), so a future re-split would go unflagged here. If one is wanted, the pin belongs at
# the definition as an identity assertion, not as this value comparison. The single definition
# lives in `round_phases.py`, which is itself pinned in `escalation.SAFETY_MACHINERY`.


def _review_base_template_literals():
    path = os.path.join(_HERE, "..", "..", "rubric", "review-base.md")
    text = open(path, encoding="utf-8").read()
    id_literal = None
    severity_literal = None
    for line in text.splitlines():
        if '"id":' in line and id_literal is None:
            id_literal = line.split(":", 1)[1].strip().rstrip(",").strip('"')
        if '"severity":' in line and severity_literal is None:
            severity_literal = line.split(":", 1)[1].strip().rstrip(",").strip('"')
    return id_literal, severity_literal


def test_review_base_template_literals_match_rubric():
    id_lit, sev_lit = _review_base_template_literals()
    assert EA.REVIEW_BASE_TEMPLATE_ID == id_lit
    assert EA.REVIEW_BASE_TEMPLATE_SEVERITY == sev_lit


def test_parse_result_review_verdicts_acceptance():
    stdout = json.dumps({
        "verdicts": [{"id": "v1", "verdict": "CONFIRMED", "reason": "reproduced"}],
        "investigated": ["a.py"],
    })
    res = EA.parse_result("codex", "review", stdout)
    assert res == {
        "ok": True,
        "resultKind": "verdicts",
        "verdicts": [{"id": "v1", "verdict": "CONFIRMED", "reason": "reproduced"}],
        "investigated": ["a.py"],
    }


def test_parse_result_review_verdict_item_predicate_is_kind_specific():
    stdout = json.dumps({"verdicts": [{"id": "v1", "verdict": "PLAUSIBLE"}]})
    assert EA.parse_result("codex", "review", stdout) == {"ok": False, "reason": "unreadable"}
    stdout_ok = json.dumps({
        "verdicts": [{"id": "v1", "verdict": "PLAUSIBLE", "reason": "evidence in log"}],
    })
    res = EA.parse_result("codex", "review", stdout_ok)
    assert res["ok"] is True
    assert res["resultKind"] == "verdicts"
    assert res["verdicts"][0]["verdict"] == "PLAUSIBLE"


def test_parse_result_review_verdicts_empty_list_is_clean():
    stdout = json.dumps({"verdicts": []})
    res = EA.parse_result("codex", "review", stdout)
    assert res == {"ok": True, "resultKind": "verdicts", "verdicts": [], "investigated": []}


def test_parse_result_review_placeholder_literal_refused():
    stdout = json.dumps({"verdicts": [
        {"id": EA.REVIEW_BASE_TEMPLATE_ID, "verdict": "CONFIRMED"}]})
    assert EA.parse_result("codex", "review", stdout) == {"ok": False, "reason": "unreadable"}
    stdout2 = json.dumps({"findings": [
        {"id": "real-1", "severity": EA.REVIEW_BASE_TEMPLATE_SEVERITY,
         "title": "t", "body": "b"}]})
    assert EA.parse_result("codex", "review", stdout2) == {"ok": False, "reason": "unreadable"}


def test_parse_result_review_placeholder_in_body_survives():
    stdout = json.dumps({"findings": [
        {"id": "real-1", "severity": "Minor", "title": "t",
         "body": EA.REVIEW_BASE_TEMPLATE_ID}]})
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    assert res["resultKind"] == "findings"


def test_parse_result_review_both_keys_ambiguity_unreadable():
    stdout = json.dumps({"findings": [], "verdicts": []})
    assert EA.parse_result("codex", "review", stdout) == {"ok": False, "reason": "unreadable"}


def test_parse_result_review_verdicts_not_a_list_unreadable():
    stdout = json.dumps({"verdicts": {}})
    assert EA.parse_result("codex", "review", stdout) == {"ok": False, "reason": "unreadable"}


def test_parse_result_review_verdicts_hollow_member_unreadable():
    stdout = json.dumps({"verdicts": [{"id": "v1", "verdict": "NOT_A_VERDICT"}]})
    assert EA.parse_result("codex", "review", stdout) == {"ok": False, "reason": "unreadable"}


def test_parse_result_review_verdicts_with_reason_scrubbed():
    stdout = json.dumps({"verdicts": [
        {"id": "v1", "verdict": "CONFIRMED",
         "reason": "log shows Authorization: Bearer sk-EXAMPLEfakenotarealsecret0"}]})
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    assert "sk-EXAMPLEfakenotarealsecret0" not in res["verdicts"][0]["reason"]
    assert "[REDACTED]" in res["verdicts"][0]["reason"]


def test_parse_result_cursor_error_envelope_real_verdicts_still_readable():
    inner = json.dumps({
        "verdicts": [{"id": "v1", "verdict": "CONFIRMED", "reason": "confirmed in diff"}],
    })
    res = EA.parse_result("cursor", "review", _envelope(inner, subtype="error", is_error=True))
    assert res["ok"] is True
    assert res["resultKind"] == "verdicts"


def test_normalize_review_stdout_echo_only_diagnosed():
    prompt = _review_prompt_with_shape_contract()
    raw = _envelope(prompt)
    norm = EA.normalize_review_stdout(raw, prompt)
    assert norm["echoOnly"] is True
    assert norm["text"] == ""
    shape = EA.review_payload_shape(raw, prompt)
    assert shape == {
        "parsed": EA.SHAPE_PROMPT_ECHO_ONLY, "topLevelKeys": [], "keysTruncated": False,
    }


def test_review_payload_shape_valid_verdicts_returns_none():
    assert EA.review_payload_shape(json.dumps({"verdicts": [
        {"id": "v1", "verdict": "CONFIRMED", "reason": "ok"}]})) is None
    assert EA.review_payload_shape(json.dumps({"verdicts": []})) is None


def test_review_payload_shape_verdicts_not_a_list():
    res = EA.review_payload_shape(json.dumps({"verdicts": "oops"}))
    assert res == {
        "parsed": EA.SHAPE_OBJECT_VERDICTS_NOT_A_LIST, "topLevelKeys": [], "keysTruncated": False,
    }


def test_review_payload_shape_verdicts_hollow_member():
    res = EA.review_payload_shape(json.dumps({"verdicts": [{"id": "", "verdict": "CONFIRMED"}]}))
    assert res == {
        "parsed": EA.SHAPE_VERDICTS_HOLLOW_MEMBER, "topLevelKeys": [], "keysTruncated": False,
    }


def test_review_payload_shape_placeholder_literal_refusal():
    res = EA.review_payload_shape(json.dumps({"verdicts": [
        {"id": EA.REVIEW_BASE_TEMPLATE_ID, "verdict": "CONFIRMED"}]}))
    assert res == {
        "parsed": EA.SHAPE_PLACEHOLDER_LITERAL_REFUSAL, "topLevelKeys": [], "keysTruncated": False,
    }


def test_review_payload_shapes_includes_verdict_tokens():
    for token in (EA.SHAPE_OBJECT_BOTH_PAYLOAD_KEYS,
                  EA.SHAPE_OBJECT_VERDICTS_NOT_A_LIST,
                  EA.SHAPE_VERDICTS_HOLLOW_MEMBER,
                  EA.SHAPE_PLACEHOLDER_LITERAL_REFUSAL):
        assert token in EA.REVIEW_PAYLOAD_SHAPES


def test_parse_result_review_verdicts_missing_investigated_yields_empty_list():
    stdout = json.dumps({
        "verdicts": [{"id": "v1", "verdict": "CONFIRMED", "reason": "seen in file"}],
    })
    res = EA.parse_result("codex", "review", stdout)
    assert res["investigated"] == []


def test_parse_result_review_verdicts_investigated_not_a_list_rejected():
    stdout = json.dumps({
        "verdicts": [{"id": "v1", "verdict": "CONFIRMED", "reason": "seen in file"}],
        "investigated": "not-a-list",
    })
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    assert res["investigated"] == []
    assert res["investigatedRejected"] == ["not-a-list"]


def test_parse_result_review_verdicts_investigated_all_rejected_stays_ok():
    stdout = json.dumps({
        "verdicts": [],
        "investigated": ["", {"no": "path"}],
    })
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    assert res["investigated"] == []
    assert "empty-path" in res["investigatedRejected"]
    assert "object-without-path" in res["investigatedRejected"]


def test_parse_result_review_verdicts_scrubs_unlisted_free_text_field():
    secret = "sk-EXAMPLEfakenotarealsecret0"
    stdout = json.dumps({"verdicts": [
        {"id": "v1", "verdict": "CONFIRMED", "reason": "ok",
         "note": "log shows Authorization: Bearer %s" % secret}]})
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    assert secret not in res["verdicts"][0]["note"]
    assert "[REDACTED]" in res["verdicts"][0]["note"]


def test_parse_result_review_verdicts_scrubs_nested_string_in_object():
    secret = "sk-EXAMPLEfakenotarealsecret0"
    stdout = json.dumps({"verdicts": [
        {"id": "v1", "verdict": "CONFIRMED", "reason": "ok",
         "detail": {"nested": "log shows Authorization: Bearer %s" % secret}}]})
    res = EA.parse_result("codex", "review", stdout)
    assert secret not in json.dumps(res["verdicts"][0])
    assert "[REDACTED]" in res["verdicts"][0]["detail"]["nested"]


def test_review_payload_shape_both_keys_ambiguous():
    res = EA.review_payload_shape(json.dumps({"findings": [], "verdicts": []}))
    assert res == {
        "parsed": EA.SHAPE_OBJECT_BOTH_PAYLOAD_KEYS,
        "topLevelKeys": ["findings", "verdicts"],
        "keysTruncated": False,
    }


def test_review_payload_shape_both_keys_malformed_verdicts_still_ambiguous():
    res = EA.review_payload_shape(json.dumps({"findings": [], "verdicts": "oops"}))
    assert res["parsed"] == EA.SHAPE_OBJECT_BOTH_PAYLOAD_KEYS


def test_engagement_read_verdicts_engaged():
    assert EA.engagement_read({
        "resultKind": "verdicts",
        "verdicts": [{"id": "v1", "verdict": "CONFIRMED", "reason": "ok"}],
    }) == "engaged"


def test_engagement_read_non_list_verdicts_not_engaged():
    assert EA.engagement_read({"verdicts": "oops"}) == "unknown"


def test_parse_result_review_findings_carry_result_kind():
    stdout = json.dumps({"findings": [
        {"severity": "Minor", "title": "t", "body": "b"}]})
    res = EA.parse_result("codex", "review", stdout)
    assert res["resultKind"] == "findings"


# --- #763-G: review transport hardening ---


def test_parse_result_review_verdict_reason_empty_or_whitespace_unreadable():
    for reason in ("", "   ", "\n"):
        stdout = json.dumps({"verdicts": [{"id": "v1", "verdict": "CONFIRMED", "reason": reason}]})
        assert EA.parse_result("codex", "review", stdout) == {"ok": False, "reason": "unreadable"}


def test_parse_result_review_verdict_severity_secret_scrubbed_tier_survives():
    secret = "ghp_EXAMPLEfakenotarealtoken000000000"
    stdout = json.dumps({"verdicts": [
        {"id": "v1", "verdict": "CONFIRMED", "reason": "ok", "severity": secret}]})
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    assert secret not in json.dumps(res["verdicts"])
    assert "[REDACTED]" in res["verdicts"][0]["severity"]
    stdout_ok = json.dumps({"verdicts": [
        {"id": "v2", "verdict": "PLAUSIBLE", "reason": "ok", "severity": "Important"}]})
    res_ok = EA.parse_result("codex", "review", stdout_ok)
    assert res_ok["verdicts"][0]["severity"] == "Important"


def test_parse_result_review_second_pass_preserves_raw_envelope_error(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "README.md").write_text("x", encoding="utf-8")
    inner = json.dumps({"findings": [], "investigated": ["README.md"]})
    stream = _envelope(inner, subtype="error", is_error=True)
    assert EA.parse_result("cursor", "review", stream) == {"ok": False, "reason": "unreadable"}
    norm = EA.normalize_review_stdout(stream)
    assert EA.parse_result(
        "cursor", "review", norm["text"], raw_envelope_error=norm["rawEnvelopeError"],
    ) == {"ok": False, "reason": "unreadable"}


def test_review_payload_shape_bare_array_placeholder_literal_refusal():
    res = EA.review_payload_shape(json.dumps([{
        "id": EA.REVIEW_BASE_TEMPLATE_ID,
        "severity": "Minor", "title": "t", "body": "b",
    }]))
    assert res == {
        "parsed": EA.SHAPE_PLACEHOLDER_LITERAL_REFUSAL,
        "topLevelKeys": [], "keysTruncated": False,
    }


# ---------------------------------------------------------------------------
# #1109: review payload contract recognition (findings / verdicts / grouping / ruling)


_ENGINE_ADAPTER_REL = "plugins/superheroes/lib/engine_adapter.py"
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))


_WELL_FORMED_REVIEW_PAYLOADS = {
    "findings": {"findings": [], "investigated": []},
    "verdicts": {"verdicts": [], "investigated": []},
    "grouping": {"grouping": [{"member_ids": ["f1"]}]},
    "ruling": {"id": "f1", "ruling": "discharged", "reason": "fixed"},
}

_DOUBLE_MATCH_REVIEW_PAYLOADS = {
    "findings": {"findings": [], "verdicts": []},
    "verdicts": {"findings": [], "verdicts": []},
    "grouping": {"grouping": [{"member_ids": ["f1"]}], "findings": []},
    "ruling": {
        "id": "f1",
        "ruling": "discharged",
        "reason": "fixed",
        "grouping": [{"member_ids": ["g1"]}],
    },
}


@pytest.mark.parametrize("kind", EA.REVIEW_RESULT_KINDS)
def test_review_result_kind_census_recognises_declared_contract(kind):
    """Each registered kind is recognised against its own contract and no other."""
    res = EA.parse_result("codex", "review", json.dumps(_WELL_FORMED_REVIEW_PAYLOADS[kind]))
    assert res["ok"] is True
    assert res["resultKind"] == kind


@pytest.mark.parametrize("kind", EA.REVIEW_RESULT_KINDS)
def test_review_result_kind_census_refuses_multiple_contracts(kind):
    """A payload matching more than one registered contract is unreadable."""
    res = EA.parse_result("codex", "review", json.dumps(_DOUBLE_MATCH_REVIEW_PAYLOADS[kind]))
    assert res == {"ok": False, "reason": "unreadable"}


def test_parse_result_review_grouping_recognised():
    stdout = json.dumps({"grouping": [{"member_ids": ["f1"]}]})
    res = EA.parse_result("codex", "review", stdout)
    assert res == {
        "ok": True,
        "resultKind": "grouping",
        "grouping": [{"member_ids": ["f1"]}],
        "investigated": [],
    }


@pytest.mark.parametrize("grouping", [
    [{"member_ids": []}],
    [{"member_ids": [1]}],
    [{"member_ids": "not-a-list"}],
    "not-a-list",
])
def test_parse_result_review_grouping_invalid_unreadable(grouping):
    stdout = json.dumps({"grouping": grouping})
    assert EA.parse_result("codex", "review", stdout) == {"ok": False, "reason": "unreadable"}


def test_parse_result_review_grouping_null_is_clean():
    stdout = json.dumps({"grouping": None})
    res = EA.parse_result("codex", "review", stdout)
    assert res == {
        "ok": True,
        "resultKind": "grouping",
        "grouping": None,
        "investigated": [],
    }


def test_parse_result_review_ruling_recognised():
    stdout = json.dumps({"id": "f1", "ruling": "discharged", "reason": "resolved in diff"})
    res = EA.parse_result("codex", "review", stdout)
    assert res == {
        "ok": True,
        "resultKind": "ruling",
        "ruling": {
            "id": "f1",
            "ruling": "discharged",
            "reason": "resolved in diff",
        },
        "investigated": [],
    }


def test_parse_result_review_ruling_out_of_enum_not_recognised():
    stdout = json.dumps({"id": "f1", "ruling": "maybe-discharged", "reason": "x"})
    assert EA.parse_result("codex", "review", stdout) == {"ok": False, "reason": "unreadable"}


@pytest.mark.parametrize("payload", [
    {"id": "f1", "ruling": "discharged"},
    {"id": "f1", "reason": "x"},
    {"ruling": "discharged", "reason": "x"},
])
def test_parse_result_review_ruling_two_of_three_keys_not_recognised(payload):
    assert EA.parse_result("codex", "review", json.dumps(payload)) == {
        "ok": False, "reason": "unreadable",
    }


def test_parse_result_review_ruling_new_issue_without_usable_new_issues_unreadable():
    stdout = json.dumps({
        "id": "f1",
        "ruling": "discharged-but-new-issue",
        "reason": "introduced regression",
        "newIssues": [],
    })
    assert EA.parse_result("codex", "review", stdout) == {"ok": False, "reason": "unreadable"}


@pytest.mark.parametrize("entry,expected_accepted", [
    (_ENGINE_ADAPTER_REL, _ENGINE_ADAPTER_REL),
    ("./" + _ENGINE_ADAPTER_REL, "./" + _ENGINE_ADAPTER_REL),
    (_ENGINE_ADAPTER_REL + ":77", _ENGINE_ADAPTER_REL),
    ("  " + _ENGINE_ADAPTER_REL + "  ", _ENGINE_ADAPTER_REL),
    ("`" + _ENGINE_ADAPTER_REL + "`", _ENGINE_ADAPTER_REL),
])
def test_spot_check_investigated_entry_format_normalization(entry, expected_accepted):
    ok, accepted, rejected = EA.spot_check_investigated([entry], _REPO_ROOT)
    assert ok is True
    assert accepted == [expected_accepted]
    assert rejected == []

def test_spot_check_investigated_directory_stays_rejected():
    ok, accepted, rejected = EA.spot_check_investigated(
        ["plugins/superheroes/lib"], _REPO_ROOT)
    assert ok is False
    assert accepted == []
    assert any(r["reason"] == "not-a-file" for r in rejected)


def test_spot_check_investigated_absolute_path_stays_rejected():
    ok, accepted, rejected = EA.spot_check_investigated(
        [os.path.join(_REPO_ROOT, _ENGINE_ADAPTER_REL)], _REPO_ROOT)
    assert ok is False
    assert accepted == []
    assert any(r["reason"] == "absolute" for r in rejected)


@pytest.mark.parametrize("stdout", [
    json.dumps({"findings": [], "investigated": ["plugins/superheroes/lib"]}),
    json.dumps({"verdicts": [], "investigated": ["plugins/superheroes/lib"]}),
    json.dumps({"grouping": None, "investigated": ["plugins/superheroes/lib"]}),
    json.dumps({
        "id": "f1",
        "ruling": "discharged",
        "reason": "ok",
        "investigated": ["plugins/superheroes/lib"],
    }),
])
def test_spot_check_empty_kind_only_directory_does_not_clear_floor(stdout):
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    ok, accepted, rejected = EA.spot_check_investigated(res["investigated"], _REPO_ROOT)
    assert ok is False
    assert accepted == []
    assert any(r["reason"] == "not-a-file" for r in rejected)


@pytest.mark.parametrize("stdout", [
    json.dumps({"findings": [], "investigated": [os.path.join(_REPO_ROOT, _ENGINE_ADAPTER_REL)]}),
    json.dumps({"verdicts": [], "investigated": [os.path.join(_REPO_ROOT, _ENGINE_ADAPTER_REL)]}),
    json.dumps({
        "grouping": [],
        "investigated": [os.path.join(_REPO_ROOT, _ENGINE_ADAPTER_REL)],
    }),
    json.dumps({
        "id": "f1",
        "ruling": "discharged",
        "reason": "ok",
        "investigated": [os.path.join(_REPO_ROOT, _ENGINE_ADAPTER_REL)],
    }),
])
def test_spot_check_empty_kind_only_absolute_path_does_not_clear_floor(stdout):
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    ok, accepted, rejected = EA.spot_check_investigated(res["investigated"], _REPO_ROOT)
    assert ok is False
    assert accepted == []
    assert any(r["reason"] == "absolute" for r in rejected)


def test_engagement_read_grouping_engaged():
    assert EA.engagement_read({
        "resultKind": "grouping",
        "grouping": [{"member_ids": ["f1"]}],
    }) == "engaged"


def test_engagement_read_ruling_engaged():
    assert EA.engagement_read({
        "resultKind": "ruling",
        "ruling": {
            "id": "f1",
            "ruling": "discharged",
            "reason": "fixed",
        },
    }) == "engaged"


def test_engagement_read_empty_grouping_not_engaged():
    assert EA.engagement_read({"resultKind": "grouping", "grouping": None}) == "unknown"
    assert EA.engagement_read({"resultKind": "grouping", "grouping": []}) == "unknown"


# ---------------------------------------------------------------------------
# #1109r4-b: review trust-boundary parity (id / scrub / envelope / SSOT)


_REVIEW_SECRET = "sk-EXAMPLEfakenotarealsecret0"

_REVIEW_KIND_SECRET_PAYLOADS = {
    "findings": {
        "findings": [{
            "id": "f1", "severity": "Minor", "title": "t",
            "body": "log shows Authorization: Bearer %s" % _REVIEW_SECRET,
        }],
    },
    "verdicts": {
        "verdicts": [{
            "id": "v1", "verdict": "CONFIRMED",
            "reason": "log shows Authorization: Bearer %s" % _REVIEW_SECRET,
        }],
    },
    "grouping": {
        "grouping": [{
            "member_ids": ["f1"],
            "note": "log shows Authorization: Bearer %s" % _REVIEW_SECRET,
        }],
    },
    "ruling": {
        "id": "f1",
        "ruling": "discharged",
        "reason": "log shows Authorization: Bearer %s" % _REVIEW_SECRET,
    },
}

_REVIEW_KIND_POPULATED_ENVELOPE_PAYLOADS = {
    "findings": {
        "findings": [{"id": "f1", "severity": "Minor", "title": "t", "body": "b"}],
    },
    "verdicts": {
        "verdicts": [{"id": "v1", "verdict": "CONFIRMED", "reason": "ok"}],
    },
    "grouping": {
        "grouping": [{"member_ids": ["f1"]}],
    },
    "ruling": {
        "id": "f1", "ruling": "discharged", "reason": "ok",
    },
}

_REVIEW_KIND_EMPTY_ENVELOPE_PAYLOADS = {
    "findings": [{"findings": []}],
    "verdicts": [{"verdicts": []}],
    "grouping": [{"grouping": None}, {"grouping": []}],
}


@pytest.mark.parametrize("kind", EA.REVIEW_RESULT_KINDS)
def test_review_result_kinds_scrub_known_secret(kind):
    """Every registered review kind routes payload strings through the scrub seam."""
    res = EA.parse_result("codex", "review", json.dumps(_REVIEW_KIND_SECRET_PAYLOADS[kind]))
    assert res["ok"] is True
    assert _REVIEW_SECRET not in json.dumps(res)


@pytest.mark.parametrize("kind", EA.REVIEW_RESULT_KINDS)
def test_review_result_kind_populated_survives_outer_envelope_error(kind):
    """Populated payloads survive the #949 outer-envelope gate for every registered kind."""
    inner = json.dumps(_REVIEW_KIND_POPULATED_ENVELOPE_PAYLOADS[kind])
    stream = _envelope(inner, subtype="error", is_error=True)
    res = EA.parse_result("cursor", "review", stream)
    assert res["ok"] is True
    assert res["resultKind"] == kind


@pytest.mark.parametrize("kind", [k for k in EA.REVIEW_RESULT_KINDS
                                  if k in _REVIEW_KIND_EMPTY_ENVELOPE_PAYLOADS])
def test_review_result_kind_empty_payload_outer_envelope_error_unreadable(kind):
    """Empty payloads stay unreadable under an outer error envelope for every registered kind."""
    for payload in _REVIEW_KIND_EMPTY_ENVELOPE_PAYLOADS[kind]:
        inner = json.dumps(payload)
        stream = _envelope(inner, subtype="error", is_error=True)
        assert EA.parse_result("cursor", "review", stream) == {"ok": False, "reason": "unreadable"}


@pytest.mark.parametrize("bad_id", [None, "", "   ", 42, {}])
def test_parse_result_review_ruling_invalid_id_unreadable(bad_id):
    stdout = json.dumps({"id": bad_id, "ruling": "discharged", "reason": "ok"})
    assert EA.parse_result("codex", "review", stdout) == {"ok": False, "reason": "unreadable"}


def test_parse_result_review_ruling_valid_id_still_parses():
    stdout = json.dumps({"id": "f1", "ruling": "discharged", "reason": "resolved"})
    res = EA.parse_result("codex", "review", stdout)
    assert res["ok"] is True
    assert res["resultKind"] == "ruling"
    assert res["ruling"]["id"] == "f1"
