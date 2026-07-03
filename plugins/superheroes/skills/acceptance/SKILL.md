---
name: acceptance
description: Use to run the standalone showrunner acceptance harness — "run the acceptance harness", "acceptance-test the showrunner", "verify the showrunner end-to-end on the fixture". Takes NO free-form input — it launches the real showrunner on a canned throwaway fixture, judges the terminal outcome against machine-checkable facts, tears down every artifact on every exit path, and hands back one plain-language pass/fail verdict. It NEVER merges and refuses to nest inside a run.
user-invocable: true
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# Acceptance harness — the owner front door

Durabilize the one-shot manual acceptance run into one owner-invoked command. The skill is
**control-flow narration only**: it takes **no free-form input** (the fixture is canned — UFR-7),
refuses **before any launch or create** when it detects it is running inside a showrunner or
acceptance run (UFR-5), and otherwise delegates the whole invocation to `acceptance_run.invoke`.
Every judgement stays a pure decider; the skill asks no question a decider can answer and **never
merges, releases, or force-pushes** — the launcher structurally denies those owner-authority
actions in the child (UFR-6), and the final verdict is the owner's to act on.

It resolves host-neutral actions via the host tool map like every other skill (CONVENTIONS §7).
Escalation follows the F5 policy (`escalation-base.md`): act autonomously on agent-verifiable /
reversible steps, escalate only owner-authority decisions.

Resolve the plugin lib dir once: `LIB="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/lib"`, and the repo
root: `ROOT=$(git rev-parse --show-toplevel)`.

## Start

1. **Refuse to nest (UFR-5) — before anything else.** Read the execution-context marker and stop
   if it is set. This marker is distinct from the on-disk `active_run` lease state: it is the
   environment flag the launcher sets on the child, so a nested invocation refuses without touching
   any state.

   ```bash
   python3 - <<'PY'
   import os, sys
   sys.path.insert(0, os.environ["LIB"])
   import acceptance_run
   r = acceptance_run.nesting_refusal(os.environ)
   print(r["reason"])
   sys.exit(1 if r["refuse"] else 0)
   PY
   ```

   On a non-zero exit, print the refusal reason — acceptance runs cannot nest inside the pipeline
   they test — and **STOP**. Create nothing, launch nothing.

2. **Refuse on a missing or drifted prerequisite (UFR-7).** The orchestrator runs the deterministic
   pre-flight decider and the committed-fixture drift check as its first in-process steps; a failed
   pre-flight or a drifted fixture (absent, phase-list drift, or a missing target file) refuses
   before launching anything and names what is missing or drifted — the drift is never reported as
   a pipeline failure.

3. **Delegate the whole invocation.** Hand the run to the orchestrator, which sequences the entire
   lifecycle (reclaim/refuse a prior run → materialize the stamped throwaway fixture → pre-flight →
   launch the real showrunner out-of-process → judge the terminal outcome and the readout-vs-reality
   consistency → tear down every stamped artifact on every exit path → write exactly one result
   record → release the lease only after the record is durable):

   ```bash
   python3 "$LIB/acceptance_run.py" --fixture "$LIB/../eval/fixtures/acceptance" --root "$ROOT"
   ```

4. **Render the single verdict report.** Print the orchestrator's one plain-language report — the
   pass/fail verdict, the reason, where the result record lives, and what was cleaned up or left
   behind — and stop. **Never instruct merging**; the run mutates no real state and the verdict is
   yours to act on.

This is a one-shot, unattended command: exactly one record and one report per invocation, never a
merge, and protected against mutating real state by structure.
