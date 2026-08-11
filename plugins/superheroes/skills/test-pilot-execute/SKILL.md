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
   `python3 -B "${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/lib/pr_comment.py" scrub` (stdin→stdout).
   Never quote raw request headers.
4. The plan comment's checkboxes belong to the human — never check them.

## Flow

The execution step-body lives at **`${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/test-pilot-execute/reference/execution-steps.md`** — read it and
follow it. That file is the **one home** of the eight steps; this section
points at it rather than restating them, so a dispatched consumer that cannot
reach this skill (the `pilot` build subagent has no Skill tool) cites the same
path instead of keeping a copy that drifts (CONVENTIONS §11.4).

Steps 1–4 provision the run; steps 5–8 execute and observe. **If you cannot
read that file, stop and report it** — never drive the app from memory of
these steps.

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
| "I reproduced it N/N with the same steps — it's an app bug" | N identical runs only test the procedure — before calling it an app bug you must follow the failure-classification and variation rules in `skills/test-pilot-execute/reference/execution-steps.md` (§ Steps 5–8), including the three unconfirmed labels. |
| "The control doesn't respond, so the feature is broken" | A scripted miss or a non-responsive control is not proof of a broken feature until you have followed the interaction-calibration and variation rules in `skills/test-pilot-execute/reference/execution-steps.md` (§ Steps 5–8) — including accessible-name targeting, pointer actions, and `aria-disabled` handling. |
