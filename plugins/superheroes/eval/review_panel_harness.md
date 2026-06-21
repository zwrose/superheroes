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
