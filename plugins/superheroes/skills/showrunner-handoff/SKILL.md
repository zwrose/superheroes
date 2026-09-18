---
name: showrunner-handoff
description: "Use in the showrunner advisor seat you are leaving while it is still alive — deliberate handover before the seat goes dark. Parks builders when the account is going dark, stops watch loops, freshens the resume point, says ready. Emits no paste block. Not checkpoint (`/compact`); not showrunner-resume (incoming seat)."
user-invocable: true
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# showrunner-handoff — hand the advisor seat over

Run this in the **showrunner advisor seat you are leaving**, while that seat is still alive and you have time to hand over deliberately. It prepares durable state and says **ready**. It does **not** emit a block of text for the owner to paste — nothing is handed over by text, so nothing can go stale.

**Refuse plainly and stop** when this is not a showrunner advisor session. Emit no partial output.

## Invocation

| Form | Behavior |
| --- | --- |
| `/superheroes:showrunner-handoff` | Ask whether this instance's account is going dark, prepare durable state, stop this seat's watch loops, freshen the resume point if one exists, and say ready with every unresolved lane named. Refuse plainly when this is not a showrunner advisor session. |

## Step 1 — the one question

Ask the owner exactly one question: **is this instance's account going dark?**

Ask nothing else. This is the only fact that changes what happens to the builders — whether they must park and push before the account stops, or keep running untouched.

## Step 2 — the park-and-wait branch

**If yes:** ask every live builder launched from this account to park and push. The request travels through whatever channel this host offers for reaching another session. **Where the host offers none, the request cannot be delivered** — name those lanes and carry them to step 5 as unresolved rather than implying a park was asked for.

Then **wait on durable evidence only**, never on a message being acknowledged:

- a park record on the lane's issue or pull request;
- the lane's builder-liveness heartbeat reaching a terminal state;
- the launch ledger carrying that lane's terminal outcome.

The wait is a **bounded poll** over those artifacts. A lane that does not resolve inside the bound is carried to step 5 **by name** — it is never waited on forever and never assumed parked.

**If no:** the builders keep running, untouched. Say so explicitly. Step 5 will state it, so the new seat is not left guessing whether lanes were stopped.

## Step 3 — stop this seat's watch loops

Stop the watch loops **this session** armed. Use the host-neutral action to stop each background task you started for batch watching.

When a loop cannot be confirmed stopped, name it in step 5 as unresolved. Do not assume it stopped.

## Step 4 — freshen the resume point

**If** this session keeps a resume point at the top of its ledger, bring it up to date and confirm it reflects current reality. **If** it does not keep one, say so plainly and continue. **Do not invent a storage format, path, or filename** — this is the same resume point, found the same way, that `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/checkpoint/SKILL.md` freshens.

## Step 5 — say "ready"

The closing output is one short block that states **ready** and, in the same block, names every lane that did not resolve — a builder that could not be reached, a park whose evidence could not be read, a loop that could not be confirmed stopped.

### Worked example (three lanes, one unresolved)

```text
Ready. Lanes #412 and #415 parked — park records on their issues, heartbeats terminal, ledger outcomes recorded. Lane #418 unresolved: no host channel to reach its builder; park not requested. Watch loops for batch wave-handoff-a stopped. Builders on #412 and #415 left running under the other account; step 2 was no (account not going dark).
```

## No paste block

This skill emits **no block of text for the owner to paste**. A block of text is stale the moment the durable record moves past it, and the incoming seat reads the durable record anyway.

## Failure modes

| Failure | Outcome |
| --- | --- |
| This is not a showrunner advisor session | Refuse plainly. Stop. No partial output. |
| The ledger or resume point cannot be read | Preserve the fact as unresolved. Name it in step 5. Stop the transition. |
| A builder cannot be reached | Preserve the lane as unresolved. Name it in step 5. Stop the transition for that lane. |
| Park evidence cannot be read | Preserve the lane as unresolved. Name it in step 5. Stop the transition for that lane. |
| A watch loop cannot be confirmed stopped | Preserve the batch as unresolved. Name it in step 5. Stop the transition for that batch. |

## Common mistakes

| Mistake | Fix |
| --- | --- |
| Running this in a workhorse or detective session | Refuse plainly — this skill is for the showrunner advisor seat only. |
| Emitting a paste block for the incoming seat | The incoming seat reads durable state; nothing travels by text. |
| Waiting on a builder's acknowledgment | Wait only on durable evidence: park record, terminal heartbeat, ledger outcome. |
| Assuming a lane parked when evidence is missing | Name it unresolved in step 5; never assume. |
| Inventing a resume-point path or format | Only freshen a resume point this session already keeps; cite checkpoint for the shape. |
| Killing watch loops or matching processes to stop them | Stop only background tasks this session armed; a process listing is a read, never a kill. |
