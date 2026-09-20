# C14 layer 1 — command-line Claude, print mode: bite-proof record (#1273, PR #1346)

Orchestrator-run record. Method: an exact-string neutralization of the guarded element with `count(old) == 1` asserted, the detector(s) run alone by exact node id (red), the file restored from the captured pre-mutation bytes (never an inverse replace and never a git discard), `git status --porcelain` asserted empty after the restore, the detector run again (green). Elements A1–A10 and B1–B13 ran in a detached probe worktree at the integration head `4da849dc`; B2 (whose discriminating test WO-D added after the first pass read NOT-RED), F1 and F2 (the review-round fixes) ran at the final code head `69651e44`. One shared green run over every A/B detector closed the first pass (`rc 0`, tree clean); B2/F1/F2 carry their own green. Raw captures are bounded to the decisive tail; scratch paths are elided as `<scratch>`. No secrets, tokens, private URLs or PII appear in the captures. **26 elements, 26 RED→GREEN.** The implementer-written records `c14_l1_wo_a.md` (WO-A, no restore receipts) and `c14_l1_wo_d.md` (WO-D) are superseded by this one for every element they name; they stay in the tree as the implementers' own receipts.

## Disclosures

- **B2 first pass NOT-RED (2026-09-19, head `4da849dc`):** with the write-side gate call deleted, every existing claude write test still passed — a coverage gap, not a detector defect. WO-D added `test_claude_write_planted_valid_result_without_stdout_result_forfeits_occupied`; B2 below is the re-run on the final head with that detector.
- **A5** neutralized the `--permission-mode acceptEdits` half of the write argv on the integration head (the `--allowedTools Bash` half was later removed by the review fix; F1 proves the final shape).
- No element was `Unreachable through this entry point`, `Unprovable as placed`, or `Unrunnable here`.

## A1 — claude declares the native channel

- **site:** `plugins/superheroes/lib/engine_result_channel.py`
- **detector(s):** `plugins/superheroes/lib/tests/test_engine_result_channel.py::test_every_dispatchable_vendor_has_channel_delivery_pin_and_argv`
- **neutralization (exact string, count(old)=1):**

```diff
-    "claude": CHANNEL_NATIVE,
+    "claude": CHANNEL_MARKER,
```

- **raw red (rc 1):**

```
# axis: BUILD_ARGV_VENDORS chokepoint — every member has channel, delivery, and argv (#1273)
        matrix_cells = {
            "codex": ("gpt-5.6-terra", "high"),
            "cursor": ("cursor-grok-4.6", "xhigh"),
            "claude": ("sonnet-5", "high"),
        }
        for vendor in EA.BUILD_ARGV_VENDORS:
>           assert ERC.channel_for(vendor) == ERC.CHANNEL_NATIVE
E           AssertionError: assert 'marker' == 'native'
E             
E             - native
E             + marker

plugins/superheroes/lib/tests/test_engine_result_channel.py:462: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_result_channel.py::test_every_dispatchable_vendor_has_channel_delivery_pin_and_argv
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.34s
```
- **restore:** pre-mutation bytes written back; file identical to the original: True; `git status --porcelain` empty: True
- **raw green (rc 0):** see the shared green run below

- **verdict:** RED->GREEN

## A2 — claude is a dispatchable vendor (BUILD_ARGV_VENDORS)

- **site:** `plugins/superheroes/lib/engine_adapter.py`
- **detector(s):** `plugins/superheroes/lib/tests/test_seat_bundle.py::test_claude_vendor_passes_dispatch_chokepoint_for_on_allowlist_cell`, `plugins/superheroes/lib/tests/test_conformance_probe.py::test_dispatchable_engines_include_claude`
- **neutralization (exact string, count(old)=1):**

```diff
-BUILD_ARGV_VENDORS = ("codex", "cursor", "claude")
+BUILD_ARGV_VENDORS = ("codex", "cursor")
```

- **raw red (rc 1):**

```
t.mark.parametrize("verb", ["dispatch-review", "dispatch-write"])
    def test_claude_vendor_passes_dispatch_chokepoint_for_on_allowlist_cell(verb):
        # axis: claude is now in BUILD_ARGV_VENDORS — passes vendor gate (#1273 WO-A)
        role = _REVIEW_ROLE if verb == "dispatch-review" else _WRITE_ROLE
        resolved = SB.resolve_entry(
            _seat_json("claude", "sonnet-5", "high", role),
            verb=verb,
        )
>       assert resolved["ok"] is True
E       assert False is True

plugins/superheroes/lib/tests/test_seat_bundle.py:507: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_claude_vendor_passes_dispatch_chokepoint_for_on_allowlist_cell[dispatch-review]
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 2.54s
```
- **restore:** pre-mutation bytes written back; file identical to the original: True; `git status --porcelain` empty: True
- **raw green (rc 0):** see the shared green run below

- **verdict:** RED->GREEN

## A3 — claude result delivery is stdout

- **site:** `plugins/superheroes/lib/engine_result_channel.py`
- **detector(s):** `plugins/superheroes/lib/tests/test_engine_result_channel.py::test_result_delivery_registered_engines`
- **neutralization (exact string, count(old)=1):**

```diff
-    "claude": RESULT_DELIVERY_STDOUT,
+(deleted)
```

- **raw red (rc 1):**

```
Y_ENGINE:
            raise UnknownEngineError(
                "unknown engine %r; registered engines: %s"
                % (engine, ", ".join(model_registry.vendors()))
            )
        channel = _CHANNEL_BY_ENGINE[engine]
        if channel == CHANNEL_MARKER:
            return None
        delivery = _RESULT_DELIVERY_BY_ENGINE.get(engine)
        if delivery is None:
>           raise ValueError("native engine %r has no result delivery entry" % (engine,))
E           ValueError: native engine 'claude' has no result delivery entry

plugins/superheroes/lib/engine_result_channel.py:183: ValueError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_result_channel.py::test_result_delivery_registered_engines
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.03s
```
- **restore:** pre-mutation bytes written back; file identical to the original: True; `git status --porcelain` empty: True
- **raw green (rc 0):** see the shared green run below

- **verdict:** RED->GREEN

## A4 — review argv carries --restricted

- **site:** `plugins/superheroes/lib/engine_adapter.py`
- **detector(s):** `plugins/superheroes/lib/tests/test_engine_adapter.py::test_build_argv_claude_review_exact_shape`
- **neutralization (exact string, count(old)=1):**

```diff
-            argv += ["--restricted"]
+            pass
```

- **raw red (rc 1):**

```
w_exact_shape ___________________

    def test_build_argv_claude_review_exact_shape():
        argv = EA.build_argv(_seat("claude", "sonnet-5", "high"), "review", {})
>       assert argv == [
            "claude", "-p", "--model", "sonnet", "--effort", "high",
            "--output-format", "stream-json", "--verbose", "--restricted",
        ]
E       AssertionError: assert ['claude', '-..., 'high', ...] == ['claude', '-..., 'high', ...]
E         
E         Right contains one more item: '--restricted'
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_engine_adapter.py:641: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_build_argv_claude_review_exact_shape
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.96s
```
- **restore:** pre-mutation bytes written back; file identical to the original: True; `git status --porcelain` empty: True
- **raw green (rc 0):** see the shared green run below

- **verdict:** RED->GREEN

## A5 — write argv carries --permission-mode acceptEdits (final head: + --restricted, see F1)

- **site:** `plugins/superheroes/lib/engine_adapter.py`
- **detector(s):** `plugins/superheroes/lib/tests/test_engine_adapter.py::test_build_argv_claude_write_exact_shape`
- **neutralization (exact string, count(old)=1):**

```diff
-            argv += ["--permission-mode", "acceptEdits", "--allowedTools", "Bash"]
+            argv += ["--allowedTools", "Bash"]
```

- **raw red (rc 1):**

```
", "high"), "build", {})
>       assert argv == [
            "claude", "-p", "--model", "sonnet", "--effort", "high",
            "--output-format", "stream-json", "--verbose",
            "--permission-mode", "acceptEdits", "--allowedTools", "Bash",
        ]
E       AssertionError: assert ['claude', '-..., 'high', ...] == ['claude', '-..., 'high', ...]
E         
E         At index 9 diff: '--allowedTools' != '--permission-mode'
E         Right contains 2 more items, first extra item: '--allowedTools'
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_engine_adapter.py:649: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_build_argv_claude_write_exact_shape
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 2.57s
```
- **restore:** pre-mutation bytes written back; file identical to the original: True; `git status --porcelain` empty: True
- **raw green (rc 0):** see the shared green run below

- **verdict:** RED->GREEN

## A6 — claude_tool_calls excludes the StructuredOutput call

- **site:** `plugins/superheroes/lib/engine_adapter.py`
- **detector(s):** `plugins/superheroes/lib/tests/test_engine_adapter.py::test_claude_tool_calls_fail_closed_edges`
- **neutralization (exact string, count(old)=1):**

```diff
-                if name == "StructuredOutput":
-                    continue
+(deleted)
```

- **raw red (rc 1):**

```
.claude_tool_calls("") is None
        assert EA.claude_tool_calls(None) is None
        # only StructuredOutput → 0
        stream = _claude_event_stream(tool_names=["StructuredOutput"])
>       assert EA.claude_tool_calls(stream) == 0
E       assert 1 == 0
E        +  where 1 = <function claude_tool_calls at 0x10255b5e0>('{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "tool-0", "name": "StructuredOutput", "input": {}}]}}\n')
E        +    where <function claude_tool_calls at 0x10255b5e0> = EA.claude_tool_calls

plugins/superheroes/lib/tests/test_engine_adapter.py:721: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_claude_tool_calls_fail_closed_edges
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 2.42s
```
- **restore:** pre-mutation bytes written back; file identical to the original: True; `git status --porcelain` empty: True
- **raw green (rc 0):** see the shared green run below

- **verdict:** RED->GREEN

## A7 — claude_result_envelope returns the LAST result event

- **site:** `plugins/superheroes/lib/engine_adapter.py`
- **detector(s):** `plugins/superheroes/lib/tests/test_engine_adapter.py::test_claude_result_envelope_fail_closed_edges`
- **neutralization (exact string, count(old)=1):**

```diff
-            last = obj
-        return last
+            if last is None:
+                last = obj
+        return last
```

- **raw red (rc 1):**

```
on.dumps({"type": "result", "subtype": "success", "structured_output": {"a": 1}})
        second = json.dumps({"type": "result", "subtype": "success", "structured_output": {"b": 2}})
        stream = first + "\n" + second + "\n"
        env = EA.claude_result_envelope(stream)
>       assert env["structured_output"] == {"b": 2}
E       AssertionError: assert {'a': 1} == {'b': 2}
E         
E         Left contains 1 more item:
E         {'a': 1}
E         Right contains 1 more item:
E         {'b': 2}
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_engine_adapter.py:742: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_claude_result_envelope_fail_closed_edges
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.83s
```
- **restore:** pre-mutation bytes written back; file identical to the original: True; `git status --porcelain` empty: True
- **raw green (rc 0):** see the shared green run below

- **verdict:** RED->GREEN

## A8 — fable refuses fable-unrunnable on the claude branch

- **site:** `plugins/superheroes/lib/engine_adapter.py`
- **detector(s):** `plugins/superheroes/lib/tests/test_engine_adapter.py::test_build_argv_claude_fail_closed_edges`
- **neutralization (exact string, count(old)=1):**

```diff
-        if engine_model == "fable-5":
-            return _refuse("fable-unrunnable", detail=_fable_unrunnable_detail("fable"))
+(deleted)
```

- **raw red (rc 1):**

```
e, ""):
            res = EA.build_argv_result(_seat("claude", model, "high"), "review", {})
            assert res["reason"] == "unregistered-engine-model"
            assert "haiku-4.5" in res["detail"]
        # 2 fable-5 or token fable → fable-unrunnable
        res = EA.build_argv_result(_seat("claude", "fable-5", "high"), "review", {})
>       assert res["reason"] == "fable-unrunnable"
E       AssertionError: assert 'invalid-model-effort' == 'fable-unrunnable'
E         
E         - fable-unrunnable
E         + invalid-model-effort

plugins/superheroes/lib/tests/test_engine_adapter.py:670: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_build_argv_claude_fail_closed_edges
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 2.59s
```
- **restore:** pre-mutation bytes written back; file identical to the original: True; `git status --porcelain` empty: True
- **raw green (rc 0):** see the shared green run below

- **verdict:** RED->GREEN

## A9 — effort is required on the claude branch (None → invalid-model-effort)

- **site:** `plugins/superheroes/lib/engine_adapter.py`
- **detector(s):** `plugins/superheroes/lib/tests/test_engine_adapter.py::test_build_argv_claude_fail_closed_edges`
- **neutralization (exact string, count(old)=1):**

```diff
-        ok, _reason = model_registry.validate_config("claude", engine_model, effort)
+        ok, _reason = (True, None) if effort is None else model_registry.validate_config("claude", engine_model, effort)
```

- **raw red (rc 1):**

```
assert res["reason"] == "fable-unrunnable"
        # 3 codex id under claude vendor → unregistered-engine-model
        res = EA.build_argv_result(_seat("claude", "gpt-5.6-sol", "high"), "review", {})
        assert res["reason"] == "unregistered-engine-model"
        # 4 effort None or off-enum → invalid-model-effort with claude enum
        res = EA.build_argv_result(_seat("claude", "sonnet-5", None), "review", {})
>       assert res["reason"] == "invalid-model-effort"
E       AssertionError: assert None == 'invalid-model-effort'

plugins/superheroes/lib/tests/test_engine_adapter.py:678: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_build_argv_claude_fail_closed_edges
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 2.10s
```
- **restore:** pre-mutation bytes written back; file identical to the original: True; `git status --porcelain` empty: True
- **raw green (rc 0):** see the shared green run below

- **verdict:** RED->GREEN

## A10 — config_dir.resolve: relative override with no absolute cwd → None

- **site:** `plugins/superheroes/lib/config_dir.py`
- **detector(s):** `plugins/superheroes/lib/tests/test_config_dir.py::test_resolve_relative_override_without_absolute_cwd_returns_none`
- **neutralization (exact string, count(old)=1):**

```diff
-            return os.path.normpath(os.path.join(cwd, path))
-        return None
+            return os.path.normpath(os.path.join(cwd, path))
+        return path
```

- **raw red (rc 1):**

```
_resolve_relative_override_without_absolute_cwd_returns_none _______

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x10621dca0>

    def test_resolve_relative_override_without_absolute_cwd_returns_none(monkeypatch):
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", "relative/config")
>       assert CD.resolve() is None
E       AssertionError: assert 'relative/config' is None
E        +  where 'relative/config' = <function resolve at 0x10649e9d0>()
E        +    where <function resolve at 0x10649e9d0> = CD.resolve

plugins/superheroes/lib/tests/test_config_dir.py:40: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_config_dir.py::test_resolve_relative_override_without_absolute_cwd_returns_none
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.28s
```
- **restore:** pre-mutation bytes written back; file identical to the original: True; `git status --porcelain` empty: True
- **raw green (rc 0):** see the shared green run below

- **verdict:** RED->GREEN

## B1 — review admission runs the stdout-delivery gate first

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector(s):** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_review_planted_result_without_stdout_result_forfeits_occupied`
- **neutralization (exact string, count(old)=1):**

```diff
-    """Single admission authority for the native review channel (codex, cursor). Never raises."""
-    gate = _stdout_delivery_gate(run_dir_real, attempt, opened)
+    """Single admission authority for the native review channel (codex, cursor). Never raises."""
+    gate = None
```

- **raw red (rc 1):**

```
id_prompt(tmp_path),
            repo_root=repo_root,
            run_engine=_ClaudeStdoutFakeRunner([plant_no_result, plant_no_result]),
            build_view=_fake_build_view(tmp_path),
            run_dir=run_dir,
        )
        assert res["forfeited"] is True
>       assert res["detail"] == "native-result-path-occupied"
E       AssertionError: assert 'native-result-malformed' == 'native-result-path-occupied'
E         
E         - native-result-path-occupied
E         + native-result-malformed

plugins/superheroes/lib/tests/test_engine_dispatch.py:13951: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_review_planted_result_without_stdout_result_forfeits_occupied
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 6.32s
```
- **restore:** pre-mutation bytes written back; file identical to the original: True; `git status --porcelain` empty: True
- **raw green (rc 0):** see the shared green run below

- **verdict:** RED->GREEN

## B2 — write admission runs the stdout-delivery gate first (detector added by WO-D)

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector(s):** `plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_claude_write_planted_valid_result_without_stdout_result_forfeits_occupied`
- **neutralization (exact string, count(old)=1):**

```diff
-    """Single admission authority for the native write channel (codex, cursor). Never raises."""
-    gate = _stdout_delivery_gate(run_dir_real, attempt, opened)
+    """Single admission authority for the native write channel (codex, cursor). Never raises."""
+    gate = None
```

- **raw red (rc 1):**

```
UDE_RUN_DIR"], attempt)
            with open(result_path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(valid, separators=(",", ":")) + "\n")
            return "", False, 0, ""
    
        res = _dispatch_write(
            tmp_path,
            _ClaudeStdoutWriteFakeRunner([plant_no_result, plant_no_result]),
            cwd=wt,
            run_dir=run_dir,
            seat=_claude_seat(),
        )
>       assert res["forfeited"] is True
E       KeyError: 'forfeited'

plugins/superheroes/lib/tests/test_engine_dispatch_write.py:3624: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch_write.py::test_claude_write_planted_valid_result_without_stdout_result_forfeits_occupied
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 0.52s
```
- **restore:** pre-mutation bytes written back; file identical to the original: True; `git status --porcelain` empty: True
- **raw green (rc 0):** 

```
.                                                                        [100%]
1 passed in 3.01s
```

- **verdict:** RED->GREEN

## B3 — materializer creates the result path with O_EXCL (a planted file wins → occupied)

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector(s):** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_review_planted_result_with_valid_stdout_forfeits_occupied`
- **neutralization (exact string, count(old)=1):**

```diff
-            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
+            os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
```

- **raw red (rc 1):**

```
icts_runner()(argv, prompt_bytes, timeout, progress_cb, cwd)
    
        res = ED.dispatch_review(
            seat=_reviewer_claude_seat(),
            prompt_path=_valid_prompt(tmp_path),
            repo_root=repo_root,
            run_engine=_ClaudeStdoutFakeRunner([plant_then_result, plant_then_result]),
            build_view=_fake_build_view(tmp_path),
            run_dir=run_dir,
            expected_result_kind="verdicts",
        )
>       assert res["forfeited"] is True
E       KeyError: 'forfeited'

plugins/superheroes/lib/tests/test_engine_dispatch.py:13981: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_review_planted_result_with_valid_stdout_forfeits_occupied
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 6.14s
```
- **restore:** pre-mutation bytes written back; file identical to the original: True; `git status --porcelain` empty: True
- **raw green (rc 0):** see the shared green run below

- **verdict:** RED->GREEN

## B4 — an errored result event (is_error: true) is never materialized

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector(s):** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_review_errored_result_forfeits_native_result_missing`
- **neutralization (exact string, count(old)=1):**

```diff
-            or env.get("is_error") is True
+            or False
```

- **raw red (rc 1):**

```
ef errored(argv, prompt_bytes, timeout, progress_cb, cwd):
            return json.dumps(bad) + "\n", False, 0, ""
    
        res = ED.dispatch_review(
            seat=_reviewer_claude_seat(),
            prompt_path=_valid_prompt(tmp_path),
            repo_root=repo_root,
            run_engine=_ClaudeStdoutFakeRunner([errored, errored]),
            build_view=_fake_build_view(tmp_path),
            expected_result_kind="verdicts",
        )
>       assert res["forfeited"] is True
E       KeyError: 'forfeited'

plugins/superheroes/lib/tests/test_engine_dispatch.py:13901: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_review_errored_result_forfeits_native_result_missing
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 4.71s
```
- **restore:** pre-mutation bytes written back; file identical to the original: True; `git status --porcelain` empty: True
- **raw green (rc 0):** see the shared green run below

- **verdict:** RED->GREEN

## B5 — attempt-ended records stdoutResult on the production path

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector(s):** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_run_engine_files_hands_popen_the_recorded_env`
- **neutralization (exact string, count(old)=1):**

```diff
-    if stdout_result is not None:
-        ended_record["stdoutResult"] = stdout_result
+    if False:
+        ended_record["stdoutResult"] = stdout_result
```

- **raw red (rc 1):**

```
assert env["CLAUDE_CONFIG_DIR"] == config_dir
        records, _ = ED._journal_read(run_dir)
        started = next(r for r in records if r.get("kind") == "engine-started")
        assert started["env"] == {
            "CLAUDE_CONFIG_DIR": config_dir,
            "CLAUDE_CODE_EFFORT_LEVEL": "xhigh",
        }
        ended = next(
            r for r in records
            if r.get("kind") == "attempt-ended" and r.get("attempt") == 1)
>       assert ended["stdoutResult"] == "materialized"
E       KeyError: 'stdoutResult'

plugins/superheroes/lib/tests/test_engine_dispatch.py:14123: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_run_engine_files_hands_popen_the_recorded_env
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 5.41s
```
- **restore:** pre-mutation bytes written back; file identical to the original: True; `git status --porcelain` empty: True
- **raw green (rc 0):** see the shared green run below

- **verdict:** RED->GREEN

## B6 — child env pins CLAUDE_CODE_EFFORT_LEVEL to the seat effort

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector(s):** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_run_engine_files_hands_popen_the_recorded_env`
- **neutralization (exact string, count(old)=1):**

```diff
-        env["CLAUDE_CODE_EFFORT_LEVEL"] = effort
+        pass
```

- **raw red (rc 1):**

```
stderr_path = os.path.join(run_dir, "attempt-1.stderr")
        ED._run_engine_files(
            run_dir, 1, opened["argv"], opened["cwd"],
            opened["promptPath"], stdout_path, stderr_path,
            ED.RETRY_MIN_TIMEOUT, opened.get("progressPath") or os.path.join(run_dir, "progress.jsonl"),
        )
        assert captured
        env = captured[0]
>       assert env["CLAUDE_CODE_EFFORT_LEVEL"] == "xhigh"
E       AssertionError: assert 'low' == 'xhigh'
E         
E         - xhigh
E         + low

plugins/superheroes/lib/tests/test_engine_dispatch.py:14111: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_run_engine_files_hands_popen_the_recorded_env
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 8.32s
```
- **restore:** pre-mutation bytes written back; file identical to the original: True; `git status --porcelain` empty: True
- **raw green (rc 0):** see the shared green run below

- **verdict:** RED->GREEN

## B6b — child env drops the ambient CLAUDE_EFFORT reflection

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector(s):** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_run_engine_files_hands_popen_the_recorded_env`
- **neutralization (exact string, count(old)=1):**

```diff
-    env.pop("CLAUDE_EFFORT", None)
+    pass
```

- **raw red (rc 1):**

```
ned.get("progressPath") or os.path.join(run_dir, "progress.jsonl"),
        )
        assert captured
        env = captured[0]
        assert env["CLAUDE_CODE_EFFORT_LEVEL"] == "xhigh"
>       assert "CLAUDE_EFFORT" not in env
E       AssertionError: assert 'CLAUDE_EFFORT' not in {'AI_AGENT': 'claude-code_2-1-277_agent', 'ANTHROPIC_BASE_URL': 'https://api.anthropic.com', 'API_TIMEOUT_MS': '900000...blic_key=2f98127cbffe4740b1f767a2de77d23b,sentry-trace_id=601279b3a43c47db869995a7b19f2409,sentry-org_id=1158394', ...}

plugins/superheroes/lib/tests/test_engine_dispatch.py:14112: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_run_engine_files_hands_popen_the_recorded_env
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.48s
```
- **restore:** pre-mutation bytes written back; file identical to the original: True; `git status --porcelain` empty: True
- **raw green (rc 0):** see the shared green run below

- **verdict:** RED->GREEN

## B7 — child env pins CLAUDE_CONFIG_DIR to the recorded configDir

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector(s):** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_run_engine_files_hands_popen_the_recorded_env`
- **neutralization (exact string, count(old)=1):**

```diff
-        env["CLAUDE_CONFIG_DIR"] = cfg
+        pass
```

- **raw red (rc 1):**

```
),
        )
        assert captured
        env = captured[0]
        assert env["CLAUDE_CODE_EFFORT_LEVEL"] == "xhigh"
        assert "CLAUDE_EFFORT" not in env
>       assert env["CLAUDE_CONFIG_DIR"] == config_dir
E       AssertionError: assert '/Users/zwrose/.claude' == '/private/var...h0/claude-cfg'
E         
E         - /private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-1649/test_claude_run_engine_files_h0/claude-cfg
E         + /Users/zwrose/.claude

plugins/superheroes/lib/tests/test_engine_dispatch.py:14113: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_run_engine_files_hands_popen_the_recorded_env
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.46s
```
- **restore:** pre-mutation bytes written back; file identical to the original: True; `git status --porcelain` empty: True
- **raw green (rc 0):** see the shared green run below

- **verdict:** RED->GREEN

## B8 — open refuses config-dir-unusable when the resolved dir is not a directory

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector(s):** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_review_open_default_config_dir_missing_refuses`
- **neutralization (exact string, count(old)=1):**

```diff
-        if not os.path.isdir(cfg):
-            return False, "config-dir-unusable:not-a-directory"
-    else:
-        cfg = None
-
-    channel = engine_result_channel.channel_for(engine)
+    else:
+        cfg = None
+
+    channel = engine_result_channel.channel_for(engine)
```

- **raw red (rc 1):**

```
DE_CONFIG_DIR", raising=False)
        repo_root = _repo(tmp_path)
        run_dir = str(tmp_path / "run")
        res = ED.dispatch_review(
            seat=_reviewer_claude_seat(),
            prompt_path=_valid_prompt(tmp_path),
            repo_root=repo_root,
            run_engine=_ClaudeStdoutFakeRunner([]),
            build_view=_fake_build_view(tmp_path),
            run_dir=run_dir,
            max_wait=0,
        )
>       assert res["detail"] == "config-dir-unusable:not-a-directory"
E       KeyError: 'detail'

plugins/superheroes/lib/tests/test_engine_dispatch.py:13811: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_review_open_default_config_dir_missing_refuses
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.10s
```
- **restore:** pre-mutation bytes written back; file identical to the original: True; `git status --porcelain` empty: True
- **raw green (rc 0):** see the shared green run below

- **verdict:** RED->GREEN

## B9 — spawn refuses config-dir-unusable when the recorded dir vanished

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector(s):** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_run_engine_files_config_dir_removed_refuses_spawn`
- **neutralization (exact string, count(old)=1):**

```diff
-        if not isinstance(cfg, str) or not cfg or not os.path.isdir(cfg):
-            _journal_prep_refusal
+        if not isinstance(cfg, str) or not cfg:
+            _journal_prep_refusal
```

- **raw red (rc 1):**

```
out_fd, stderr=stderr_fd,
                    cwd=cwd, start_new_session=True, env=child_env,
                )
        except Exception as exc:
            _journal_append(run_dir_real, {
                "kind": "attempt-ended", "attempt": attempt,
                "exit": 127, "timedOut": False, "signal": None,
                "refusal": ("spawn-failed: %s" % exc)[:_STDERR_TAIL], "at": time.time(),
            })
            return
    
>       pgid = proc.pid
E       AttributeError: 'NoneType' object has no attribute 'pid'

plugins/superheroes/lib/engine_dispatch.py:3043: AttributeError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_run_engine_files_config_dir_removed_refuses_spawn
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.04s
```
- **restore:** pre-mutation bytes written back; file identical to the original: True; `git status --porcelain` empty: True
- **raw green (rc 0):** see the shared green run below

- **verdict:** RED->GREEN

## B10 — _native_channel_suffix carries --json-schema for stdout delivery (argv coherence)

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector(s):** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_review_open_records_native_channel_config_dir_and_json_schema_argv`
- **neutralization (exact string, count(old)=1):**

```diff
-        return ("--json-schema", text)
+        return ()
```

- **raw red (rc 1):**

```
ng="utf-8") as fh:
            schema_text = fh.read().rstrip("\n")
        assert opened["argv"][-2:] == ["--json-schema", schema_text]
>       assert ED._spawn_argv_coherence(opened, opened["argv"])[1] is None
E       assert "spawn argv does not match resolvedInputs snapshot — stored argv ['claude', '-p', '--model', 'sonnet', '--effort', 'hi...effort', 'high', '--output-format', 'stream-json', '--verbose', '--restricted']; re-open the run with a fresh dispatch" is None

plugins/superheroes/lib/tests/test_engine_dispatch.py:13791: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_review_open_records_native_channel_config_dir_and_json_schema_argv[edge2-relative]
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed, 1 passed in 1.09s
```
- **restore:** pre-mutation bytes written back; file identical to the original: True; `git status --porcelain` empty: True
- **raw green (rc 0):** see the shared green run below

- **verdict:** RED->GREEN

## B11 — the legacy REVIEW_RESULT_CONTRACT is appended for argv delivery only

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector(s):** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_review_prompt_has_schema_contract_not_legacy`
- **neutralization (exact string, count(old)=1):**

```diff
-            if delivery == engine_result_channel.RESULT_DELIVERY_ARGV:
-                fed_prompt += _prompt_section_sep + engine_adapter.REVIEW_RESULT_CONTRACT(
+            if delivery != engine_result_channel.RESULT_DELIVERY_PROMPT:
+                fed_prompt += _prompt_section_sep + engine_adapter.REVIEW_RESULT_CONTRACT(
```

- **raw red (rc 1):**

```
h" not in prompt
E       AssertionError: assert 'Review resu...t must match' not in 'You are a d...it ruling)\n'
E         
E         'Review result cont...d stdout must match' is contained here:
E           o null.
E           
E           
E           Review result contract (your graded stdout must match exactly one of these shapes):
E           The runner accepts these result kinds (4): `findings`, `verdicts`, `grouping`, `ruling`....
E         
E         ...Full output truncated (5 lines hidden), use '-vv' to show

plugins/superheroes/lib/tests/test_engine_dispatch.py:14052: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_review_prompt_has_schema_contract_not_legacy
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.16s
```
- **restore:** pre-mutation bytes written back; file identical to the original: True; `git status --porcelain` empty: True
- **raw green (rc 0):** see the shared green run below

- **verdict:** RED->GREEN

## B12 — no quota leg on the claude path (census detector)

- **site:** `plugins/superheroes/lib/engine_adapter.py`
- **detector(s):** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_no_quota_leg_on_the_claude_dispatch_path`
- **neutralization (exact string, count(old)=1):**

```diff
-    if vendor == "claude":
-        engine_model, _source, refusal_reason, refusal_detail = _resolve_engine_model_pin(
+    if vendor == "claude":
+        # quota leg placeholder
+        engine_model, _source, refusal_reason, refusal_detail = _resolve_engine_model_pin(
```

- **raw red (rc 1):**

```
2), match='quota'>
E            +  where <re.Match object; span=(23897, 23902), match='quota'> = <built-in method search of re.Pattern object at 0x1028f97c0>('#!/usr/bin/env python3\n"""The deterministic engine argv/parse/commit core (kept out of the effectful dispatch layer ...) + "\\n")\n        return 0\n    return 0\n\n\nif __name__ == "__main__":\n    raise SystemExit(main(sys.argv[1:]))\n')
E            +    where <built-in method search of re.Pattern object at 0x1028f97c0> = re.compile('\\bquota\\b', re.IGNORECASE).search

plugins/superheroes/lib/tests/test_engine_dispatch.py:14245: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_no_quota_leg_on_the_claude_dispatch_path
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.12s
```
- **restore:** pre-mutation bytes written back; file identical to the original: True; `git status --porcelain` empty: True
- **raw green (rc 0):** see the shared green run below

- **verdict:** RED->GREEN

## B13 — engagement source is claude-stream

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **detector(s):** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_review_admits_structured_output_through_injected_seam`, `plugins/superheroes/lib/tests/test_conformance_probe.py::test_run_grades_three_legs_ok_on_valid_claude_native_result`
- **neutralization (exact string, count(old)=1):**

```diff
-            source = "claude-stream" if tool_calls is not None else "none"
+            source = "none"
```

- **raw red (rc 1):**

```
w(
            seat=_reviewer_claude_seat(),
            prompt_path=_valid_prompt(tmp_path),
            repo_root=repo_root,
            run_engine=fake,
            build_view=_fake_build_view(tmp_path),
            expected_result_kind="verdicts",
        )
        assert res["ok"] is True
        assert res["resultKind"] == "verdicts"
>       assert res["engagement"]["source"] == "claude-stream"
E       AssertionError: assert 'none' == 'claude-stream'
E         
E         - claude-stream
E         + none

plugins/superheroes/lib/tests/test_engine_dispatch.py:13848: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_claude_review_admits_structured_output_through_injected_seam
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.10s
```
- **restore:** pre-mutation bytes written back; file identical to the original: True; `git status --porcelain` empty: True
- **raw green (rc 0):** see the shared green run below

- **verdict:** RED->GREEN

## F1 — review-round fix: write argv is --permission-mode acceptEdits --restricted, no --allowedTools

- **site:** `plugins/superheroes/lib/engine_adapter.py`
- **detector(s):** `plugins/superheroes/lib/tests/test_engine_adapter.py::test_build_argv_claude_write_exact_shape`, `plugins/superheroes/lib/tests/test_engine_adapter.py::test_build_argv_claude_write_omits_allowed_tools`
- **neutralization (exact string, count(old)=1):**

```diff
-            argv += ["--permission-mode", "acceptEdits", "--restricted"]
+            argv += ["--permission-mode", "acceptEdits", "--allowedTools", "Bash"]
```

- **raw red (rc 1):**

```
= EA.build_argv(_seat("claude", "sonnet-5", "high"), "build", {})
>       assert argv == [
            "claude", "-p", "--model", "sonnet", "--effort", "high",
            "--output-format", "stream-json", "--verbose",
            "--permission-mode", "acceptEdits", "--restricted",
        ]
E       AssertionError: assert ['claude', '-..., 'high', ...] == ['claude', '-..., 'high', ...]
E         
E         At index 11 diff: '--allowedTools' != '--restricted'
E         Left contains one more item: 'Bash'
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_engine_adapter.py:649: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_adapter.py::test_build_argv_claude_write_exact_shape
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 3.32s
```
- **restore:** pre-mutation bytes written back; file identical to the original: True; `git status --porcelain` empty: True
- **raw green (rc 0):** 

```
..                                                                       [100%]
2 passed in 3.07s
```

- **verdict:** RED->GREEN

## F2 — review-round fix: launch-without claude keeps claude out of the preflight seat map

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **detector(s):** `plugins/superheroes/lib/tests/test_conformance_probe.py::test_preflight_entry_launch_without_claude_excludes_from_live_vendors`
- **neutralization (exact string, count(old)=1):**

```diff
-    if "claude" not in owner_map:
-        live_vendors.add("claude")
+    live_vendors.add("claude")
```

- **raw red (rc 1):**

```
= False
        claude_fail["failed"] = ["resultProduction"]
        paths = _ok_dispatchable_probe_paths(tmp_path, repo, claude=claude_fail)
        payload, code = CP.preflight_entry(
            repo,
            paths,
            launch_without=["claude"],
            owner_words=["owner approves"],
            calibration_rows=cal,
        )
        assert code == 0
>       assert "claude" not in captured["live_vendors"]
E       AssertionError: assert 'claude' not in ['claude', 'codex', 'cursor']

plugins/superheroes/lib/tests/test_conformance_probe.py:850: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_preflight_entry_launch_without_claude_excludes_from_live_vendors
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 1.88s
```
- **restore:** pre-mutation bytes written back; file identical to the original: True; `git status --porcelain` empty: True
- **raw green (rc 0):** 

```
.                                                                        [100%]
1 passed in 1.60s
```

- **verdict:** RED->GREEN

## Shared green run (A1–A10, B1, B3–B13, head `4da849dc`)

rc 0; `git status --porcelain` empty: True

```
........................                                                 [100%]
24 passed in 2.64s
```
