# WO-1 and WO-3 (#1981) bite-proof — a check that did not execute the code under test never dismisses a finding

**Provenance:** claude / sonnet (implementer, WO-1; and WO-3, review round 1 finding `code-001`), `plugins/superheroes/lib/break_it.py` (`_run_in_copy`, `_TailDrain.run`), `plugins/superheroes/lib/verification.py` (`apply_verdicts`); tests in `plugins/superheroes/lib/tests/test_not_executed_1981.py`.

Declared guarded-element set (from the order): **B1**, **B2**, **B3** (WO-1), **B4**, **B5** (WO-3). Each was neutralized by one targeted edit (the Edit tool, exact-text match), only its proving nodes run, the inverse edit applied, and the same selection run again. No `git checkout`, `git restore`, `git reset` or `git stash` was used. The sha256 of the neutralized file was taken before the edit, with the edit in place, and after the restore.

## Guarded elements

| ID | Guarded element | Axis | Proving nodes |
|---|---|---|---|
| B1 | the new `not-run` branch in `break_it.py` `_run_in_copy` (the `if reason:` return) | a setup failure reads not-run, never failed/passed | `test_not_executed_1981.py::test_t2_e1_exit_127_with_empty_output_is_command_not_found`, `::test_t2_e2_exit_1_with_module_not_found_is_not_run`, `::test_t2_e3_exit_0_with_module_not_found_is_not_run_never_passed` |
| B2 | the drain latch in `break_it.py` `_TailDrain.run` (the `self.setup = setup_failure_reason(...)` assignment) | a signature early in a long output is still seen | `test_not_executed_1981.py::test_t2_e4_an_early_signature_survives_a_long_output[0]` and `[1]`, `::test_t3_intercept_keeps_a_break_it_finding_whose_early_signature_scrolled_off` |
| B3 | the not-executed keep in `verification.py` `apply_verdicts` (the `not unrun` term of the drop condition) | a REFUTED resting on a check that did not execute is kept unverified, not dropped | `test_not_executed_1981.py::test_t4_*` (five parametrized rows and the identity-key row), `::test_t6_the_round_driver_keeps_a_not_executed_refutation_and_records_it` |
| B4 | the drain upgrade in `break_it.py` `_TailDrain.run` (the `if self.setup != REASON_COMMAND_NOT_FOUND:` guard together with the `found` assignment) | a later `command not found` read upgrades an earlier module latch | `test_not_executed_1981.py::test_t7_a_later_command_not_found_read_upgrades_an_earlier_module_latch` |
| B5 | the run-level precedence in `break_it.py` `_run_in_copy` (the `REASON_COMMAND_NOT_FOUND in (setup, tail_reason)` condition) | exit 127 beats a latched module reason | `test_not_executed_1981.py::test_t8_e2_module_signature_with_exit_127_is_command_not_found` |

## Disclosures

- Every element went red under its neutralization (pytest exit 1) and green after the restore (exit 0).
- B2 was neutralized on the latch only; B1's tail check (`setup_failure_reason(output, code)`) stayed in place, so E4 and T3 went red on the latch axis alone (the premise assertion in E4 shows the retained tail holds no trace of the signature).
- The `UV_NATIVE_TLS` deprecation warning line that `scripts/pinned-python` prints before each pytest capture is omitted below; everything else is verbatim (default `--tb`, no filter).
- All captures are well under 32 KiB, so none is written off-repo.

---

## B1 — the not-run branch in `_run_in_copy`

- **axis:** a setup failure reads not-run, never failed/passed

**neutralization** (`plugins/superheroes/lib/break_it.py`):
```diff
-    if reason:
+    if False and reason:
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/pyc-wo1-1981 -m pytest -q -p no:cacheprovider plugins/superheroes/lib/tests/test_not_executed_1981.py -k "t2_e1 or t2_e2 or t2_e3"
```

**decisive assertion lines (red tokens):**
- E1, `test_not_executed_1981.py:70`: `AssertionError: assert ('failed', None, 127) == ('not-run', '...t-found', 127)`
- E2, `test_not_executed_1981.py:77`: `AssertionError: assert ('failed', None, 1) == ('not-run', '...not-found', 1)`
- E3, `test_not_executed_1981.py:83`: `AssertionError: assert ('passed', None, 0) == ('not-run', '...not-found', 0)`

**raw red** (exit 1):
```
FFF                                                                      [100%]
=================================== FAILURES ===================================
__________ test_t2_e1_exit_127_with_empty_output_is_command_not_found __________

repo = PosixPath('/tmp/claude-0/pytest-of-root/pytest-3/test_t2_e1_exit_127_with_empty0/repo')

    def test_t2_e1_exit_127_with_empty_output_is_command_not_found(repo):
        record = _run(repo, "import sys\nsys.exit(127)\n")
>       assert (record["outcome"], record["reason"], record["exitCode"]) == ("not-run", "command-not-found", 127)
E       AssertionError: assert ('failed', None, 127) == ('not-run', '...t-found', 127)
E         
E         At index 0 diff: 'failed' != 'not-run'
E         Use -v to get more diff

/home/user/wt-1981/plugins/superheroes/lib/tests/test_not_executed_1981.py:70: AssertionError
______________ test_t2_e2_exit_1_with_module_not_found_is_not_run ______________

repo = PosixPath('/tmp/claude-0/pytest-of-root/pytest-3/test_t2_e2_exit_1_with_module_0/repo')

    def test_t2_e2_exit_1_with_module_not_found_is_not_run(repo):
        content = "import sys\nsys.stderr.write(%r + '\\n')\nsys.exit(1)\n" % _MODULE_SIGNATURE
        record = _run(repo, content)
>       assert (record["outcome"], record["reason"], record["exitCode"]) == ("not-run", "module-not-found", 1)
E       AssertionError: assert ('failed', None, 1) == ('not-run', '...not-found', 1)
E         
E         At index 0 diff: 'failed' != 'not-run'
E         Use -v to get more diff

/home/user/wt-1981/plugins/superheroes/lib/tests/test_not_executed_1981.py:77: AssertionError
_______ test_t2_e3_exit_0_with_module_not_found_is_not_run_never_passed ________

repo = PosixPath('/tmp/claude-0/pytest-of-root/pytest-3/test_t2_e3_exit_0_with_module_0/repo')

    def test_t2_e3_exit_0_with_module_not_found_is_not_run_never_passed(repo):
        record = _run(repo, "print(\"ModuleNotFoundError: No module named 'x'\")\n")
>       assert (record["outcome"], record["reason"], record["exitCode"]) == ("not-run", "module-not-found", 0)
E       AssertionError: assert ('passed', None, 0) == ('not-run', '...not-found', 0)
E         
E         At index 0 diff: 'passed' != 'not-run'
E         Use -v to get more diff

/home/user/wt-1981/plugins/superheroes/lib/tests/test_not_executed_1981.py:83: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_not_executed_1981.py::test_t2_e1_exit_127_with_empty_output_is_command_not_found
FAILED plugins/superheroes/lib/tests/test_not_executed_1981.py::test_t2_e2_exit_1_with_module_not_found_is_not_run
FAILED plugins/superheroes/lib/tests/test_not_executed_1981.py::test_t2_e3_exit_0_with_module_not_found_is_not_run_never_passed
3 failed, 29 deselected in 3.15s
```

**restore:** the inverse edit on `plugins/superheroes/lib/break_it.py`; sha256 before the neutralization `d934fa43cb94be1009381eac681b67858799331f89de3218399c3c803a206303`, with the neutralization in place `7f102e94df167e16d29b1f51d3881bb85f625a405f01063347cf8e3c83a86b29`, after the restore `d934fa43cb94be1009381eac681b67858799331f89de3218399c3c803a206303` — identical to before.

**restored lines** (as they stand):
```
761:     reason = setup or setup_failure_reason(output, code)
762:     # axis: a run whose output shows a missing command or module, or that exits 127, reads not-run, never failed or passed — see bite-proof record wo_1_1981_not_executed
763:     if reason:
764:         return rec(OUTCOME_NOT_RUN, reason, exit_code=code, output=output)
```

**raw green** (exit 0), same command:
```
...                                                                      [100%]
3 passed, 29 deselected in 3.05s
```

---

## B2 — the drain latch in `_TailDrain.run`

- **axis:** a signature early in a long output is still seen

**neutralization** (`plugins/superheroes/lib/break_it.py`, the latch's guard only, so the assignment never runs):
```diff
-                if self.setup is None:
+                if False and self.setup is None:
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/pyc-wo1-1981 -m pytest -q -p no:cacheprovider plugins/superheroes/lib/tests/test_not_executed_1981.py -k "t2_e4 or t3"
```

**decisive assertion lines (red tokens):**
- E4 exit 0, `test_not_executed_1981.py:94`: `AssertionError: assert ('passed', None, 0) == ('not-run', '...not-found', 0)`
- E4 exit 1, `test_not_executed_1981.py:94`: `AssertionError: assert ('failed', None, 1) == ('not-run', '...not-found', 1)`
- T3, `test_not_executed_1981.py:114`: `AssertionError: []` / `assert 0 == 1` (the passed run was dropped from `kept`)

**raw red** (exit 1):
```
FFF                                                                      [100%]
=================================== FAILURES ===================================
___________ test_t2_e4_an_early_signature_survives_a_long_output[0] ____________

repo = PosixPath('/tmp/claude-0/pytest-of-root/pytest-5/test_t2_e4_an_early_signature_0/repo')
code = 0

    @pytest.mark.parametrize("code", [0, 1])
    def test_t2_e4_an_early_signature_survives_a_long_output(repo, code):
        content = ("import sys\nprint(%r, flush=True)\n"
                   "for _ in range(4000):\n    print('y' * 49)\nsys.exit(%d)\n" % (_MODULE_SIGNATURE, code))
        record = _run(repo, content)
        # the premise: the drain's tail kept no trace of the signature, so only the latch can have seen it
        assert "vitest" not in record["output"], record["output"][:200]
        assert len(record["output"].encode()) <= break_it.OUTPUT_TAIL_BYTES + 64
>       assert (record["outcome"], record["reason"], record["exitCode"]) == ("not-run", "module-not-found", code)
E       AssertionError: assert ('passed', None, 0) == ('not-run', '...not-found', 0)
E         
E         At index 0 diff: 'passed' != 'not-run'
E         Use -v to get more diff

/home/user/wt-1981/plugins/superheroes/lib/tests/test_not_executed_1981.py:94: AssertionError
___________ test_t2_e4_an_early_signature_survives_a_long_output[1] ____________

repo = PosixPath('/tmp/claude-0/pytest-of-root/pytest-5/test_t2_e4_an_early_signature_1/repo')
code = 1

    @pytest.mark.parametrize("code", [0, 1])
    def test_t2_e4_an_early_signature_survives_a_long_output(repo, code):
        content = ("import sys\nprint(%r, flush=True)\n"
                   "for _ in range(4000):\n    print('y' * 49)\nsys.exit(%d)\n" % (_MODULE_SIGNATURE, code))
        record = _run(repo, content)
        # the premise: the drain's tail kept no trace of the signature, so only the latch can have seen it
        assert "vitest" not in record["output"], record["output"][:200]
        assert len(record["output"].encode()) <= break_it.OUTPUT_TAIL_BYTES + 64
>       assert (record["outcome"], record["reason"], record["exitCode"]) == ("not-run", "module-not-found", code)
E       AssertionError: assert ('failed', None, 1) == ('not-run', '...not-found', 1)
E         
E         At index 0 diff: 'failed' != 'not-run'
E         Use -v to get more diff

/home/user/wt-1981/plugins/superheroes/lib/tests/test_not_executed_1981.py:94: AssertionError
_ test_t3_intercept_keeps_a_break_it_finding_whose_early_signature_scrolled_off _

repo = PosixPath('/tmp/claude-0/pytest-of-root/pytest-5/test_t3_intercept_keeps_a_brea0/repo')

    def test_t3_intercept_keeps_a_break_it_finding_whose_early_signature_scrolled_off(repo):
        content = ("print(%r, flush=True)\nfor _ in range(4000):\n    print('y' * 49)\n" % _MODULE_SIGNATURE)
        block = BI._wire(_PATH, "%s %s" % (BI.PY, _PATH), content)
        finding = {"title": "Break-it: %s" % _PATH, "file": _PATH, "line": 1, "taxonomy": break_it.TAXONOMY,
                   "suggestion": block}
        kept, runs, _ = break_it.intercept([finding], str(repo), BI._head(repo))
>       assert len(kept) == 1, kept
E       AssertionError: []
E       assert 0 == 1
E        +  where 0 = len([])

/home/user/wt-1981/plugins/superheroes/lib/tests/test_not_executed_1981.py:114: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_not_executed_1981.py::test_t2_e4_an_early_signature_survives_a_long_output[0]
FAILED plugins/superheroes/lib/tests/test_not_executed_1981.py::test_t2_e4_an_early_signature_survives_a_long_output[1]
FAILED plugins/superheroes/lib/tests/test_not_executed_1981.py::test_t3_intercept_keeps_a_break_it_finding_whose_early_signature_scrolled_off
3 failed, 29 deselected in 3.15s
```

**restore:** the inverse edit on `plugins/superheroes/lib/break_it.py`; sha256 before the neutralization `d934fa43cb94be1009381eac681b67858799331f89de3218399c3c803a206303`, with the neutralization in place `428a78db64378f9387c63d2bd8880e38cbbcc78f09791b5f4f89fe357f2c620f`, after the restore `d934fa43cb94be1009381eac681b67858799331f89de3218399c3c803a206303` — identical to before.

**restored lines** (as they stand):
```
521:                 self.buf += chunk
522:                 # axis: a setup-failure signature printed early in a long output is latched before the tail trim drops it — see bite-proof record wo_1_1981_not_executed
523:                 if self.setup is None:
524:                     self.setup = setup_failure_reason(self.buf.decode("utf-8", errors="replace"))
```

**raw green** (exit 0), same command:
```
...                                                                      [100%]
3 passed, 29 deselected in 2.81s
```

---

## B3 — the not-executed keep in `apply_verdicts`

- **axis:** a REFUTED resting on a check that did not execute is kept unverified, not dropped

**neutralization** (`plugins/superheroes/lib/verification.py`, the `not unrun` term of the drop condition):
```diff
-        if verdict == "REFUTED" and isinstance(reason, str) and reason.strip() and not unrun:
+        if verdict == "REFUTED" and isinstance(reason, str) and reason.strip() and not (False and unrun):
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/pyc-wo1-1981 -m pytest -q -p no:cacheprovider plugins/superheroes/lib/tests/test_not_executed_1981.py -k "t4 or t6"
```

**decisive assertion lines (red tokens):**
- T4 (five rows), `test_not_executed_1981.py:136`: `assert out["drops"] == []` → `AssertionError: assert [{'id': 'v0',...t 127)', ...}] == []` (the finding was dropped)
- T4 identity-key row, `test_not_executed_1981.py:156`: `IndexError: list index out of range` (no survivor)
- T6, `test_not_executed_1981.py:222`: `assert "disposition" not in ledger.get(unrun_key, {})` → `AssertionError` (the not-executed finding was given a disposition)

**raw red** (exit 1):
```
FFFFFFF                                                                  [100%]
=================================== FAILURES ===================================
_ test_t4_a_refutation_resting_on_a_check_that_did_not_run_is_kept_unverified[reason-probe failed: sh: 1: vitest: command not found (exit 127)-command-not-found] _

field = 'reason'
text = 'probe failed: sh: 1: vitest: command not found (exit 127)'
token = 'command-not-found'

    @pytest.mark.parametrize("field, text, token", _PROBE_REASONS)
    def test_t4_a_refutation_resting_on_a_check_that_did_not_run_is_kept_unverified(field, text, token):
        findings = TV._stage([TV._f("a.py", "bug", "Important")])
        verdict = {"id": "v0", "verdict": "REFUTED", "reason": "refuted by the probe", "severity": "Nit"}
        verdict[field] = text
        out = V.apply_verdicts(findings, [verdict])
>       assert out["drops"] == []
E       AssertionError: assert [{'id': 'v0',...t 127)', ...}] == []
E         
E         Left contains one more item: {'id': 'v0', 'file': 'a.py', 'title': 'bug', 'reason': 'probe failed: sh: 1: vitest: command not found (exit 127)', ...}
E         Use -v to get more diff

/home/user/wt-1981/plugins/superheroes/lib/tests/test_not_executed_1981.py:136: AssertionError
_ test_t4_a_refutation_resting_on_a_check_that_did_not_run_is_kept_unverified[reason-the probe printed Error [ERR_MODULE_NOT_FOUND]: Cannot find package 'vitest'-module-not-found] _

field = 'reason'
text = "the probe printed Error [ERR_MODULE_NOT_FOUND]: Cannot find package 'vitest'"
token = 'module-not-found'

    @pytest.mark.parametrize("field, text, token", _PROBE_REASONS)
    def test_t4_a_refutation_resting_on_a_check_that_did_not_run_is_kept_unverified(field, text, token):
        findings = TV._stage([TV._f("a.py", "bug", "Important")])
        verdict = {"id": "v0", "verdict": "REFUTED", "reason": "refuted by the probe", "severity": "Nit"}
        verdict[field] = text
        out = V.apply_verdicts(findings, [verdict])
>       assert out["drops"] == []
E       assert [{'id': 'v0',...itest'", ...}] == []
E         
E         Left contains one more item: {'id': 'v0', 'file': 'a.py', 'title': 'bug', 'reason': "the probe printed Error [ERR_MODULE_NOT_FOUND]: Cannot find package 'vitest'", ...}
E         Use -v to get more diff

/home/user/wt-1981/plugins/superheroes/lib/tests/test_not_executed_1981.py:136: AssertionError
_ test_t4_a_refutation_resting_on_a_check_that_did_not_run_is_kept_unverified[reason-the recorded probe was not-run: module-not-found-module-not-found] _

field = 'reason', text = 'the recorded probe was not-run: module-not-found'
token = 'module-not-found'

    @pytest.mark.parametrize("field, text, token", _PROBE_REASONS)
    def test_t4_a_refutation_resting_on_a_check_that_did_not_run_is_kept_unverified(field, text, token):
        findings = TV._stage([TV._f("a.py", "bug", "Important")])
        verdict = {"id": "v0", "verdict": "REFUTED", "reason": "refuted by the probe", "severity": "Nit"}
        verdict[field] = text
        out = V.apply_verdicts(findings, [verdict])
>       assert out["drops"] == []
E       AssertionError: assert [{'id': 'v0',...-found', ...}] == []
E         
E         Left contains one more item: {'id': 'v0', 'file': 'a.py', 'title': 'bug', 'reason': 'the recorded probe was not-run: module-not-found', ...}
E         Use -v to get more diff

/home/user/wt-1981/plugins/superheroes/lib/tests/test_not_executed_1981.py:136: AssertionError
_ test_t4_a_refutation_resting_on_a_check_that_did_not_run_is_kept_unverified[evidence-ModuleNotFoundError: No module named 'x'-module-not-found] _

field = 'evidence'
text = "ModuleNotFoundError: No module named 'x'"
token = 'module-not-found'

    @pytest.mark.parametrize("field, text, token", _PROBE_REASONS)
    def test_t4_a_refutation_resting_on_a_check_that_did_not_run_is_kept_unverified(field, text, token):
        findings = TV._stage([TV._f("a.py", "bug", "Important")])
        verdict = {"id": "v0", "verdict": "REFUTED", "reason": "refuted by the probe", "severity": "Nit"}
        verdict[field] = text
        out = V.apply_verdicts(findings, [verdict])
>       assert out["drops"] == []
E       AssertionError: assert [{'id': 'v0',... probe', ...}] == []
E         
E         Left contains one more item: {'id': 'v0', 'file': 'a.py', 'title': 'bug', 'reason': 'refuted by the probe', ...}
E         Use -v to get more diff

/home/user/wt-1981/plugins/superheroes/lib/tests/test_not_executed_1981.py:136: AssertionError
_ test_t4_a_refutation_resting_on_a_check_that_did_not_run_is_kept_unverified[reason-the probe exited with status 127 before running anything-command-not-found] _

field = 'reason'
text = 'the probe exited with status 127 before running anything'
token = 'command-not-found'

    @pytest.mark.parametrize("field, text, token", _PROBE_REASONS)
    def test_t4_a_refutation_resting_on_a_check_that_did_not_run_is_kept_unverified(field, text, token):
        findings = TV._stage([TV._f("a.py", "bug", "Important")])
        verdict = {"id": "v0", "verdict": "REFUTED", "reason": "refuted by the probe", "severity": "Nit"}
        verdict[field] = text
        out = V.apply_verdicts(findings, [verdict])
>       assert out["drops"] == []
E       AssertionError: assert [{'id': 'v0',...ything', ...}] == []
E         
E         Left contains one more item: {'id': 'v0', 'file': 'a.py', 'title': 'bug', 'reason': 'the probe exited with status 127 before running anything', ...}
E         Use -v to get more diff

/home/user/wt-1981/plugins/superheroes/lib/tests/test_not_executed_1981.py:136: AssertionError
_______________ test_t4_the_kept_finding_keeps_its_identity_key ________________

    def test_t4_the_kept_finding_keeps_its_identity_key():
        import session_contract
        finding = TV._f("a.py", "bug", "Important")
        out = V.apply_verdicts(TV._stage([finding]), [
            {"id": "v0", "verdict": "REFUTED", "reason": "probe: vitest: command not found"}])
>       assert session_contract.finding_identity_key(out["findings"][0]) == session_contract.finding_identity_key(finding)
E       IndexError: list index out of range

/home/user/wt-1981/plugins/superheroes/lib/tests/test_not_executed_1981.py:156: IndexError
___ test_t6_the_round_driver_keeps_a_not_executed_refutation_and_records_it ____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-7/test_t6_the_round_driver_keeps0')

    def test_t6_the_round_driver_keeps_a_not_executed_refutation_and_records_it(tmp_path):
        # axis: a REFUTED resting on a check that did not execute is kept unverified, not dropped
        session_dir = _drive(tmp_path)
        ok, state = RDT.load_state(session_dir)
        assert ok, state
        contract = RDT.session_contract
        ledger = {contract.finding_identity_key(e): e for e in state[contract.DISPOSITION_LEDGER_KEY]}
        real_key, unrun_key = contract.finding_identity_key(_REAL), contract.finding_identity_key(_UNRUN)
        assert ledger[real_key]["disposition"] == "refuted", ledger
>       assert "disposition" not in ledger.get(unrun_key, {}), ledger
E       AssertionError: {'f.py::real bug@L1': {'classification': 'mechanical', 'consequence': 'a reviewer-found defect stays in the change', '...nsequence': 'a reviewer-found defect stays in the change', 'consequenceKind': None, 'dimension': 'code-reviewer', ...}}
E       assert 'disposition' not in {'classification': 'mechanical', 'consequence': 'a reviewer-found defect stays in the change', 'consequenceKind': None, 'dimension': 'code-reviewer', ...}
E        +  where {'classification': 'mechanical', 'consequence': 'a reviewer-found defect stays in the change', 'consequenceKind': None, 'dimension': 'code-reviewer', ...} = <built-in method get of dict object at 0x7f4dce522240>('f.py::probe bug@L2', {})
E        +    where <built-in method get of dict object at 0x7f4dce522240> = {'f.py::real bug@L1': {'classification': 'mechanical', 'consequence': 'a reviewer-found defect stays in the change', '...nsequence': 'a reviewer-found defect stays in the change', 'consequenceKind': None, 'dimension': 'code-reviewer', ...}}.get

/home/user/wt-1981/plugins/superheroes/lib/tests/test_not_executed_1981.py:222: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_not_executed_1981.py::test_t4_a_refutation_resting_on_a_check_that_did_not_run_is_kept_unverified[reason-probe failed: sh: 1: vitest: command not found (exit 127)-command-not-found]
FAILED plugins/superheroes/lib/tests/test_not_executed_1981.py::test_t4_a_refutation_resting_on_a_check_that_did_not_run_is_kept_unverified[reason-the probe printed Error [ERR_MODULE_NOT_FOUND]: Cannot find package 'vitest'-module-not-found]
FAILED plugins/superheroes/lib/tests/test_not_executed_1981.py::test_t4_a_refutation_resting_on_a_check_that_did_not_run_is_kept_unverified[reason-the recorded probe was not-run: module-not-found-module-not-found]
FAILED plugins/superheroes/lib/tests/test_not_executed_1981.py::test_t4_a_refutation_resting_on_a_check_that_did_not_run_is_kept_unverified[evidence-ModuleNotFoundError: No module named 'x'-module-not-found]
FAILED plugins/superheroes/lib/tests/test_not_executed_1981.py::test_t4_a_refutation_resting_on_a_check_that_did_not_run_is_kept_unverified[reason-the probe exited with status 127 before running anything-command-not-found]
FAILED plugins/superheroes/lib/tests/test_not_executed_1981.py::test_t4_the_kept_finding_keeps_its_identity_key
FAILED plugins/superheroes/lib/tests/test_not_executed_1981.py::test_t6_the_round_driver_keeps_a_not_executed_refutation_and_records_it
7 failed, 25 deselected in 3.52s
```

**restore:** the inverse edit on `plugins/superheroes/lib/verification.py`; sha256 before the neutralization `dce799a68aa1a9d76ebacca61c0183e0e6799122c7d80ff8f55a6631d4caf908`, with the neutralization in place `acbbfeeb7e6a2344a179bbe0c2fc0b6121e418a17a815c621dd9c1c3340fa214`, after the restore `dce799a68aa1a9d76ebacca61c0183e0e6799122c7d80ff8f55a6631d4caf908` — identical to before.

**restored lines** (as they stand):
```
163:         # axis: a REFUTED resting on a check that did not execute is kept unverified, never dropped — see bite-proof record wo_1_1981_not_executed
164:         if verdict == "REFUTED" and isinstance(reason, str) and reason.strip() and not unrun:
```

**raw green** (exit 0), same command:
```
.......                                                                  [100%]
7 passed, 25 deselected in 3.43s
```

---

## B4 — the drain upgrade in `_TailDrain.run` (WO-3)

- **axis:** a later `command not found` read upgrades an earlier module latch

**neutralization** (`plugins/superheroes/lib/break_it.py`, the guard only):
```diff
-                if self.setup != REASON_COMMAND_NOT_FOUND:
+                if self.setup is None:
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/pyc-wo3-1981 -m pytest -q -p no:cacheprovider plugins/superheroes/lib/tests/test_not_executed_1981.py -k "test_t7_a_later_command_not_found_read_upgrades_an_earlier_module_latch"
```

**decisive assertion line (red token):** `test_not_executed_1981.py:271`: `AssertionError: assert 'module-not-found' == 'command-not-found'`

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_t7_a_later_command_not_found_read_upgrades_an_earlier_module_latch ____

    def test_t7_a_later_command_not_found_read_upgrades_an_earlier_module_latch():
>       assert _drain_two_reads(_MODULE_CHUNK, _COMMAND_CHUNK) == "command-not-found"
E       AssertionError: assert 'module-not-found' == 'command-not-found'
E         
E         - command-not-found
E         + module-not-found

/home/user/wt-1981/plugins/superheroes/lib/tests/test_not_executed_1981.py:271: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_not_executed_1981.py::test_t7_a_later_command_not_found_read_upgrades_an_earlier_module_latch
1 failed, 37 deselected in 4.41s
```

**restore:** the inverse edit on `plugins/superheroes/lib/break_it.py`; sha256 before the neutralization `400cea8fcc13ffead2df7dcb474af3ba616db79722282c634d486d40d81be915`, with the neutralization in place `0108e2c496d75f3b6c414363d54d64bb6921099d169222f9099149ac7e0c1ca5`, after the restore `400cea8fcc13ffead2df7dcb474af3ba616db79722282c634d486d40d81be915` — identical to before.

**restored lines** (as they stand):
```
523:                 if self.setup != REASON_COMMAND_NOT_FOUND:
524:                     found = setup_failure_reason(self.buf.decode("utf-8", errors="replace"))
525:                     if found is not None:
526:                         self.setup = found
```

**raw green** (exit 0), same command:
```
.                                                                        [100%]
1 passed, 37 deselected in 2.15s
```

---

## B5 — the run-level precedence in `_run_in_copy` (WO-3)

- **axis:** exit 127 beats a latched module reason

**neutralization** (`plugins/superheroes/lib/break_it.py`):
```diff
-    reason = REASON_COMMAND_NOT_FOUND if REASON_COMMAND_NOT_FOUND in (setup, tail_reason) else (setup or tail_reason)
+    reason = setup or tail_reason
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/pyc-wo3-1981 -m pytest -q -p no:cacheprovider plugins/superheroes/lib/tests/test_not_executed_1981.py -k "test_t8_e2_module_signature_with_exit_127_is_command_not_found"
```

**decisive assertion line (red token):** `test_not_executed_1981.py:286`: `At index 1 diff: 'module-not-found' != 'command-not-found'`

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_t8_e2_module_signature_with_exit_127_is_command_not_found ________

repo = PosixPath('/tmp/claude-0/pytest-of-root/pytest-14/test_t8_e2_module_signature_wi0/repo')

    def test_t8_e2_module_signature_with_exit_127_is_command_not_found(repo):
        content = "import sys\nsys.stderr.write(%r + '\\n')\nsys.exit(127)\n" % _MODULE_SIGNATURE
        record = _run(repo, content)
>       assert (record["outcome"], record["reason"], record["exitCode"]) == ("not-run", "command-not-found", 127)
E       AssertionError: assert ('not-run', '...t-found', 127) == ('not-run', '...t-found', 127)
E         
E         At index 1 diff: 'module-not-found' != 'command-not-found'
E         Use -v to get more diff

/home/user/wt-1981/plugins/superheroes/lib/tests/test_not_executed_1981.py:286: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_not_executed_1981.py::test_t8_e2_module_signature_with_exit_127_is_command_not_found
1 failed, 37 deselected in 3.10s
```

**restore:** the inverse edit on `plugins/superheroes/lib/break_it.py`; sha256 before the neutralization `400cea8fcc13ffead2df7dcb474af3ba616db79722282c634d486d40d81be915`, with the neutralization in place `8726dd228d1e8aa6af7f6d1be856f78d90d02c3dc1a1c164fd3f8d24c43beb24`, after the restore `400cea8fcc13ffead2df7dcb474af3ba616db79722282c634d486d40d81be915` — identical to before.

**restored lines** (as they stand):
```
763:     tail_reason = setup_failure_reason(output, code)
764:     reason = REASON_COMMAND_NOT_FOUND if REASON_COMMAND_NOT_FOUND in (setup, tail_reason) else (setup or tail_reason)
```

**raw green** (exit 0), same command:
```
.                                                                        [100%]
1 passed, 37 deselected in 2.90s
```
