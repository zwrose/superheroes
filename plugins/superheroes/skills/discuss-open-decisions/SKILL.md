---
name: discuss-open-decisions
description: "Use when the owner needs to rule on open decisions — asking what is waiting on them, returning from time away, or when undelivered calls have piled up. Sweeps the standing-proposals collector, open parks, and in-session pending items; applies the owner-needed filter; delivers batch 1 (decisions blocking the advisor, never new-issue filings) as numbered chat prose, pauses for rulings, executes what they unblocked, then delivers batch 2. Not routing, vetting, or building."
user-invocable: true
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# discuss-open-decisions

Owner-invoked on-demand delivery of **open owner decisions** — the calls that are the owner's to make and that the advisor already owes unprompted as a standing duty. Reach for `/superheroes:discuss-open-decisions` when you are returning from time away, when you suspect undelivered calls have piled up, or when you want every open decision walked through now instead of waiting for the next advisor beat.

This skill is deliberately **not** the only path. The showrunner advisor delivers owner decisions as a standing duty without waiting for this invocation. A standalone-skill-only design was considered and declined at ratification: it would require someone to remember to invoke it, which recreates the very inconsistency the contract exists to fix — this skill is the one-keystroke path on demand, not the whole mechanism.

## Invocation

| Form | Behavior |
| --- | --- |
| `/superheroes:discuss-open-decisions` | Read the owner-decisions contract from disk, sweep the three bounded sources, filter, deliver batch 1 as numbered chat prose, pause for batch-1 rulings, deliver batch 2, execute what batch 1 unblocked alongside batch-2 rulings. Works in a showrunner charter or any session where the owner explicitly invokes it. Not routing, vetting, or building. |

The seven steps below cite the contract by heading — they do not replace reading the file in Step 1.

## Step 1 — Read the contract

**First action, every invocation:** read `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/showrunner/reference/owner-decisions.md` from disk. The contract is never reconstructed from memory — the skill executes what that file says at delivery time, and cites its sections by heading when pointing at a specific rule (`## The filter — what is the owner's, and on what grounds`, `## The per-item spine`, `## Follow-up economics`, `## Delivery mechanics`, `## Formatting — one block per spine section`, `## Where the items come from, and the bound on that sweep`, `## What batch-1 execution may and may not do`, `## The collector preamble — canonical snippet`).

This skill does **not** restate the contract. The showrunner advisor reads the same file as a standing duty; this skill is the owner pulling that delivery forward on demand. If the file is missing, stop and report — do not substitute prose from this skill or from memory.

## Step 2 — Sweep

Gather candidate items per `## Where the items come from, and the bound on that sweep`:

1. **The project's standing-proposals collector** — authoritative. Resolve its issue pointer from the advisor's durable memory (showrunner duty 4); when the pointer cannot be resolved, ask the owner for the issue number and never open a second collector; record the pointer once found. Use the collector preamble from `## The collector preamble — canonical snippet` when the collector needs refreshing.
2. **Open parks on issues and PRs** — reach them from the advisor's own durable pointer and from open issues and PRs in the project (parks carry no marker or index). Apply the contract's bound disclosure in the delivered message — state what was searched and that the park sweep is not exhaustive; the collector is the only authoritative register. An unbounded promise reads as covered when it is not.
3. **Anything pending in the current session** — decisions raised but not yet delivered, or delivered in a prior turn without a ruling.

Read the collector before searching parks — the collector is authoritative and may already subsume an in-session duplicate. When the same decision appears in more than one source, apply the dedup rule from `## Where the items come from, and the bound on that sweep`.

## Step 3 — Filter

Apply `## The filter — what is the owner's, and on what grounds`. Present filtered items in a separate short list before batch 1 — the contract's filtered-never-swallowed rule means the owner sees disposition, not absence.

## Step 4 — Deliver batch 1

Deliver per `## Delivery mechanics` — batch 1 only, never new-issue filings. Present as numbered chat prose using `## The per-item spine` and `## Formatting — one block per spine section`.

Write the numbered batch-1 list to a durable artifact now — collector entry where the item has one, otherwise a durable note on the issue or PR it belongs to. Stable numbering survives only if it survives the session; resume from that record, not session memory.

## Step 5 — Pause for rulings

**Stop here and wait.** This is the point of the skill: batch 1 is incomplete without the owner's rulings. Do not deliver batch 2 in the same turn and call it two batches — the pause is real.

The owner may answer inline, defer an item, or ask for more context — **record each ruling to the durable artifact as it lands**, the same place as the numbered list from Step 4. When a ruling closes or declines a collector-backed item, strike it from the collector per showrunner duty 4 — do not renumber what remains. Partial batch-1 answers still block batch-1 execution for the unanswered items.

If batch 1 is empty after filtering, say so plainly and skip to Step 6 when there is nothing blocking.

## Step 6 — Deliver batch 2

**As soon as batch-1 rulings land**, deliver batch 2 — do not wait for batch-1 execution to finish. `## Delivery mechanics` splits the batches so batch-1 execution and batch-2 rulings overlap; serializing execution ahead of batch 2 defeats the split.

Deliver everything else that survived the filter — same per-item spine, same formatting, stable numbering carried forward from batch 1. Extend the durable numbered list with batch-2 items before presenting them.

Batch 2 may be long; that is fine. The owner asked for the full walkthrough.

## Step 7 — Execute and close

Execute what batch 1 unblocked — bounded by `## What batch-1 execution may and may not do` — **while the owner rules on batch 2**. For merge-train and release coordination that batch-1 execution may include, follow showrunner duty 6. Receipt what you executed in plain language.

When batch-2 rulings propose follow-ups, apply showrunner duty 4's **attended** branch — this skill is owner-present by construction: propose follow-ups inline, discuss, and append to the standing-proposals collector only what genuinely cannot close in this session. Apply `## Follow-up economics` to each proposed filing — earns-its-keep, decline-to-file, tripwire on declined owner-named risks. Record each batch-2 ruling to the durable artifact as it lands; strike collector-backed items per showrunner duty 4.

## When you're tempted

These excuses show up most often when the owner is waiting or the list is long:

| Excuse | Reality |
|---|---|
| "I'll deliver everything in one batch — faster for the owner" | Batch 1 exists because some calls block the advisor's next action; collapsing the batches hides the pause the skill exists to create. |
| "Structured questions will be clearer than chat prose" | The contract delivers numbered chat prose — a structured-question tool is not a substitute for the spine. |
| "That item isn't really the owner's — I'll skip it" | Filtered items get a one-line reason in the delivered message; swallowing them violates the contract. |
| "I'll renumber for clarity in batch 2" | Stable numbering across batches is part of the spine — renumbering breaks follow-up economics. |
| "The contract is long — I'll work from what I remember" | Step 1 reads the file every time; memory drift is how undelivered calls pile up in the first place. |
| "I'll deliver batch 2 after execution finishes" | `## Delivery mechanics` — deliver batch 2 as soon as batch-1 rulings land; execution runs alongside batch-2 rulings. |
| "The numbers live in the chat — I'll remember" | Write the numbered list and each ruling to durable artifacts as they land; resume from the record, not session memory. |
| "I'll append follow-ups to the collector — the owner can review them later" | Showrunner duty 4's attended branch — propose inline, discuss, append only what genuinely cannot close in this session. |
