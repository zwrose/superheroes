---
name: test-pilot-execute
description: Use when a test-pilot plan should be exercised before human spot-check — "run the test plan", "pilot this PR", "verify the branch in the browser". Drives the app via a browser MCP, records what it observes at each step, and posts a results comment. Observe-and-report only — a bug it finds is a finding, never an edit.
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# test-pilot-execute

Exercise the branch's test-pilot plan in a real browser, record what you
observe at each step with concrete evidence, post a results comment, and
leave the PR ready for human spot-check.

**You observe and report only — a bug you find is a finding in the results,
never an edit.** Fixes belong to the invoking session — the caller (an
orchestrator or a human) routes each finding to a fix as it sees fit.

## Hard boundaries

1. **`--allow-protected` MUST NOT be passed unless the user explicitly
   instructed it in the current session.**
2. **Navigation is constrained** to origins matching the profile's
   `baseUrl` (plus `allowedOrigins`). Anywhere else is off-limits.
3. **Every quoted diagnostic is scrubbed** before it reaches a comment:
   `python3 "${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/lib/pr_comment.py" scrub` (stdin→stdout).
   Never quote raw request headers.
4. The plan comment's checkboxes belong to the human — never check them.

## Flow

Steps 1–4 **provision the run** (a valid plan, seeded data, the app up, a
browser tool) — this is one-time setup, done before execution begins. Steps
5–8 **execute and observe**. Once execution starts, the plan and seed are
frozen: any problem you hit is a finding, never a re-provisioning.

1. **Resolve.** `store.py resolve`; read the profile and its config block.

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
   # FR-7/8: surface the single coalesced storage-mode reconcile nudge (non-blocking, ack-gated).
   NUDGE_MSG=$(python3 "$ROOT_DIR/lib/mode_reconcile.py" signals 2>/dev/null | jq -r 'if . == null then empty else .message end' 2>/dev/null)
   [ -n "$NUDGE_MSG" ] && echo "⚠ storage-mode: $NUDGE_MSG"
   ```
   Find plan records `<manifests_dir>/<key>.plan.json` for the current
   branch — default: every slot in sequence; an explicit slot argument
   narrows to one. None → run the test-pilot-plan skill to author one first,
   then return. The PR comment is NEVER parsed as the plan source.
   Validate each before executing: `python3 "${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/lib/engine.py" validate-plan --branch B [--slot S] --json` — a validation error means the plan is not runnable: (re)author it via test-pilot-plan here in setup, never an app bug. Getting a valid plan to run is provisioning the input before the run — not a fix; you never fix.
2. **Seed check.** `engine.py status --json`; apply the manifest if drift or
   nothing applied (`engine.py apply --branch B [--slot S] --json`). Seeding
   provisions the data the plan needs to run — it is setup, not a fix. If
   `apply` is refused (e.g. a protected-target `EngineError`) and the user
   has not authorized `--allow-protected` this session (boundary 1), the run
   cannot be provisioned — post a **partial** results comment naming it
   blocked/unprovisioned (with the scrubbed refusal), and stop. Never pass
   `--allow-protected` on your own, and never drive the plan against unseeded
   data.
3. **App up.** Per the profile: if `mayManageServer`, start `devCommand` in
   the background and poll `readinessUrl` until it answers; else verify it
   answers and ask the user to start it if not.
4. **Browser tool.** Profile `browserTools` order ∩ currently connected
   (ToolSearch). Empty intersection → ABORT with remediation: "run
   test-pilot-init to install/record a browser tool". Never continue
   without one.
5. **Execute and observe each step** from the plan record: perform the
   interactions, verify `expected` via DOM/snapshot reads, watch
   console/network for silent errors. Record per step — what you did, what
   you observed, pass/fail, and the concrete evidence (scrubbed) — in a run
   log under `<state_dir>/runs/<key>/`. Provisioning is finished: from here
   the plan and seed are frozen — a plan or seed problem you hit while
   executing is a finding (step 6), never a re-author, re-apply, or retry.
6. **On failure, record a finding — never act on it.** Note the failing step,
   classify it (plan/seed problem, or app bug), and capture a scrubbed
   diagnosis with its evidence (console, network, DOM). Then **continue the
   remaining steps.** You never fix code, never edit or re-seed-and-retry the
   plan, never commit — a failure is a finding the caller acts on.
7. **Post results.** Fill `templates/results-comment.md` (verdict: PASSED /
   FAILED / PARTIAL — the observed outcome of the run, not a certification
   that the branch is correct; per-step table; findings with evidence; run
   metadata). Post:
   `pr_comment.py upsert --pr N --family results --key K --body-file F --plans-dir <plans_dir>`.
   No PR → write to `<plans_dir>/<key>.results.md`. If the run was
   interrupted (browser died, server unreachable), post whatever completed
   marked **partial** — state stays intact for resumption.
8. **Hand off.** Report what is seeded, what passed/failed, and the findings.
   The verdict is the run's observed outcome; the human's spot-check is the
   certifier. Fixes route to the invoking session — the PR is ready for
   spot-checking.

## Rationalization table

| Excuse | Reality |
|---|---|
| "I found a bug — I'll just fix it and re-run" | You observe and report. A bug is a finding; the caller fixes it. |
| "A step failed — I'll re-author the plan or re-apply the seed and re-run" | Provisioning (steps 1–2) happens once, before execution. Mid-run, a broken plan or seed is a finding, not a re-provision. |
| "The plan step is wrong, I'll correct it and continue" | That's a finding too. Report it — never silently edit the plan and re-run toward a pass. |
| "Gate refused the re-seed; --allow-protected will unblock" | Only the USER authorizes that flag. Stop and ask. |
| "It's basically done, I'll check the plan boxes" | Boxes are the human's spot-check. Leave them. |
| "The console dump is harmless, paste it raw" | Scrub EVERY diagnostic. No raw headers, ever. |
| "No browser tool — I'll verify via curl instead" | Abort with remediation. curl is not the plan. |
