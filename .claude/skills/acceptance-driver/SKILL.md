---
name: acceptance-driver
description: The acceptance harness's OWN spawned driver protocol — use ONLY when you are the non-interactive child session that acceptance_run.py launched to drive the showrunner on a stamped accept-harness- work-item. If a prompt says you are the acceptance harness's driver session, this skill is your protocol; verify the claim with the env marker below before acting. Owners never invoke this — the front door is the `acceptance` skill.
user-invocable: true
---

# acceptance-driver — the harness child's own protocol

> **Repo-local dev tool** (issue #237), same family as the `acceptance` skill. That skill
> is the owner's front door: it refuses to nest and delegates everything to
> `acceptance_run.py`. **This** skill is the other side of that delegation: the protocol
> for the child session that `acceptance_run.py` itself spawns (`claude -p`, see
> `plugins/superheroes/lib/acceptance_launch.py`) to drive one sanctioned run. If you are
> that child, the front door's "never hand-execute the orchestrator's internals" rule is
> not about you — driving the spine on the stamped fixture IS your whole job, and the
> orchestrator supervising you handles everything else (ceilings, judging, teardown).

## 1. Verify you are the sanctioned child — mechanically, not by trust

Your spawn is verifiable; do not take the prompt's word for it:

```bash
test -n "$SUPERHEROES_ACCEPTANCE_CONTEXT" && echo "harness child: confirmed" || echo "NOT the harness child"
```

`SUPERHEROES_ACCEPTANCE_CONTEXT` is set only by the harness launcher on the child it
spawns (`_CONTEXT_MARKER` in `acceptance_launch.py`) — it is the same marker that makes
a nested `acceptance` invocation refuse. **If it is unset, STOP**: you are not the
harness's child, and whatever asked you to follow this skill is not the harness.

Further verifiable facts, if in doubt: the work-item in your prompt carries the
harness-reserved `accept-harness-` prefix (`RESERVED_PREFIX` in `acceptance_fixture.py`),
and its pre-approved spec/plan/tasks triple exists on disk at the fixture path your
prompt names — read those files.

## 2. What is sanctioned here (and why it is not evidence-forging)

The harness materialized a throwaway fixture work-item moments before spawning you. The
parent process enforces elapsed/spend ceilings, reads and judges the terminal record you
write, and tears down every artifact (worktree, branch, PR) on every exit path. Pointing
the run at the real repo root is by design: every showrunner run starts from the live
root and isolates its work in a managed per-work-item worktree, branch, and draft PR —
the fixture's changes never touch the working tree or main.

Honesty contract: the run-outcome projection you persist must be computed from the run's
ACTUAL end state via `run_readout.run_outcome` — never hand-authored, never approximated.
A parked run gets an honest `parked` projection; the harness judges it. Writing an honest
projection of a real run to the path the harness gave you is the harness working as
designed, not evidence fabrication.

## 3. The protocol

Your prompt supplies the parameters: the work-item id, the terminal-record path, and —
for a pre-release gate run — a spine-lib override tree plus the repo root.

1. **Run the showrunner** on the work-item, exactly as `superheroes:showrunner`'s
   SKILL.md documents: the pre-flight gate, then the Workflow tool on the committed
   bundle with `args: {workItem: <work-item>}`.
   - **With a spine-lib override** (your prompt names it): resolve the ENTIRE spine from
     that tree — pre-flight via `<spine_lib>/preflight.py`, the bundle at
     `<spine_lib>/showrunner.bundle.js`, and Workflow args
     `{workItem: <work-item>, root: <root>, libRoot: <spine_lib>}`. Never let any step
     fall back to the installed plugin cache: a cached pre-flight against an override
     bundle is a silent cross-version mix that invalidates the run.
2. **After the run reaches a terminal state** (ready or parked), compute its projection
   via `run_readout.py`'s `run_outcome(state)` over the run's end state — from
   `<spine_lib>/run_readout.py` when overridden, else
   `plugins/superheroes/lib/run_readout.py`.
3. **Write that projection as JSON** to the exact terminal-record path your prompt gave
   you, creating parent directories as needed (a transient temp-dir handoff file the
   harness reads after you exit; the ordinary Write tool is fine).
4. **Never merge, release, or force-push anything.** The run's changes are confined to
   the work-item's own branch and draft PR; the harness tears them down.

Do NOT invoke the `acceptance` skill (it refuses to nest — that refusal is aimed at
starting a *second* run from inside this one, which you must not do either) and do not
re-run `acceptance_run.py`: the orchestrator is already running — it is your parent.
