# Review-panel Workflow harness (#86) — agentic wiring proof

**Scope:** prove the *orchestration* wiring of `reviewPanel` + `panel_tally.py` end-to-end with
STUB agents. The deterministic gate/terminal/precedence/deferral matrix is proven by
`plugins/superheroes/lib/tests/test_panel_tally.py` (pytest, CI-gated) — this harness does NOT
re-assert it. Keep it tiny: stub reviewers write canned findings; the stub fix step returns canned
resolved/deferred reports. Assertions are COARSE (which terminal; no double-count) — stub-agent
fidelity makes fine assertions flaky, so the precise logic stays in pytest.

**Run:** on-demand only (not part of the CI verify command — `eval/README.md` confirms the Workflow
harness is the behavioral track). Invoke as a single Workflow; do NOT fan out widely.

**Cases (each a tiny Workflow run; assert the terminal):**
1. **Clean** — 2 stub reviewers write `[]` → expect terminal `clean`.
2. **Blocking → fix → clean** — round 1 stub reviewer writes one `Important`; stub fix returns it
   `resolved`; round 2 reviewers write `[]` → expect terminal `clean`.
3. **Dead reviewer → cannot-certify** — one stub reviewer writes nothing on both dispatches (UFR-1
   re-dispatch exhausted) → expect terminal `cannot-certify`, never `clean`.
4. **Failing fix step → halted** — round 1 has a blocker; the stub fix step returns null (failure)
   → expect terminal `halted`.
5. **Re-invocation overwrite (UFR-4)** — run case 2 to completion, then re-invoke `reviewPanel`
   with the SAME `runKey` and the same stubs → expect the same terminal and no doubled findings in
   the round verdict.

**Pass criteria:** each case's observed terminal matches the expected terminal; case 5 shows the
keyed dir fully overwritten (no duplicate findings). Record results in `eval/RESULTS.md`.

## Shared review-and-fix loop scenarios (#104)

Each row drives the loop with stand-in reviewers/fixers (no real consumer) and asserts the terminal.
The deterministic per-FR assertions are pinned in pytest (test_panel_tally / test_loop_synthesis /
test_verify_gate / test_loop_readout / test_escalation); these end-to-end rows prove the shell wires
them together.

| Scenario | leg | terminal |
| --- | --- | --- |
| clean first round (no findings) | panel-doc | clean |
| blocking finding fixed, verified clean on mandatory re-review | panel-doc | clean |
| non-blocker deferred | panel-doc | clean-with-skips |
| finding deferred then acted on a later round (FR-16) | panel-doc | clean / clean-with-skips |
| reviewer won't report -> one re-dispatch -> cannot-certify | panel-doc | cannot-certify |
| recurring finding / no-net-progress | panel-doc | halted |
| cap reached (panel cap 7) | panel-doc | halted |
| cap reached (whole-branch cap 3) | panel-code | halted |
| unresolvable blocker (fixer escalates) | panel-code | halted |
| code leg verify passes | code-review | clean |
| code leg verify fails / times out (UFR-4) | code-review | halted |
| fixer false-done -> re-surfaced (UFR-5) | panel-doc | (continues, never exits on the claim) |
| fixer silent -> bounded wait (UFR-6) | panel-doc | halted |
| durable write fails (UFR-9) | any | halted (recordMissing if even the halt can't be written) |
| panel synthesis: merge dup / normalize severity / drop-with-reason keep-uncertain | panel | (clean or continue) |
| panel drops a blocking-tagged finding (UFR-10) | panel | drop flagged distinctly in the readout |
| fixer edits a protected component (FR-24) | code-review | refused -> halted |
| escalation traces upstream (FR-21) | any | halted, readout names the phase |
| interrupted run resumes at the round boundary (UFR-7/8) | any | resumes, no fix re-applied |
| plan-doc and tasks-doc runs are independent (FR-22) | doc x2 | neither affects the other |
| fixStep extras (parentOrigin) forwarded to the tally + readout | panel-doc | clean; round-N/extras.json written, --extras passed (#88) |
