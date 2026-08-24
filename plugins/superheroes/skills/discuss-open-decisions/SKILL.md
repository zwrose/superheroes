---
name: discuss-open-decisions
description: "Use when the owner needs to rule on open decisions — asking what is waiting on them, returning from time away, or when undelivered calls have piled up. Sweeps the standing-proposals collector, open parks, and in-session pending items; applies the owner-needed filter; delivers batch 1 (decisions blocking the advisor, never new-issue filings) as numbered chat prose, pauses for rulings, executes what they unblocked, then delivers batch 2. Not routing, vetting, or building."
user-invocable: true
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# discuss-open-decisions

Owner-invoked on-demand delivery of open owner decisions. Reach for `/superheroes:discuss-open-decisions` when returning from time away, when undelivered calls may have piled up, or when you want every open decision walked through now.

This skill is deliberately not the only path. The showrunner advisor delivers owner decisions as a standing duty without waiting for this invocation.

## Invocation

| Form | Behavior |
| --- | --- |
| `/superheroes:discuss-open-decisions` | Read the owner-decisions contract from disk, sweep the three bounded sources, filter, deliver batch 1, pause for batch-1 rulings, deliver batch 2, execute what batch 1 unblocked alongside batch-2 rulings. Works in a showrunner charter or any session where the owner explicitly invokes it. |

## Step 1 — Read the contract

Read `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/showrunner/reference/owner-decisions.md` from disk — first action, every invocation.

When this session is not already running the showrunner charter, also read duty 4 in `skills/showrunner/SKILL.md`.

This skill executes the contract at delivery time rather than carrying it.

If the file is missing, stop and report — never substitute prose from this skill or from memory.

## Step 2 — Sweep

Gather candidate items per `## Where the items come from, and the bound on that sweep`.

Refresh the collector preamble per `## The collector preamble — canonical snippet` when it has drifted or is missing.

Read the project's revisit-trigger registry per `## The revisit-trigger registry` before proposing a decline, so a decline already ruled on is cited rather than re-argued.

Resolve the collector's issue pointer from the advisor's durable memory (showrunner duty 4); when the pointer cannot be resolved, ask the owner for the issue number and never open a second collector; record the pointer once found.

Read the collector before searching parks — it is authoritative and may already subsume an in-session duplicate.

## Step 3 — Filter

Apply `## The filter — what is the owner's, and on what grounds`; present filtered items per that section before batch 1.

## Step 4 — Deliver batch 1

Deliver per `## Delivery mechanics`, `## The per-item spine`, and `## Formatting — one block per spine section`; write the numbered batch-1 list to a durable artifact now — the collector entry where the item has one, otherwise a durable note on the issue or PR it belongs to — and resume from that record, not session memory.

## Step 5 — Pause for rulings

Stop here and wait; record each ruling to the durable artifact as it lands.

If batch 1 is empty after filtering, skip to Step 6 per `## Delivery mechanics`.

When a ruling closes or declines a collector-backed item, strike it from the collector per showrunner duty 4.

Partial batch-1 answers still block batch-1 execution for the items left unanswered.

## Step 6 — Deliver batch 2

Deliver batch 2 as soon as batch-1 rulings land — batch-1 execution runs alongside batch-2 rulings, not ahead of them — per `## Delivery mechanics`, `## The per-item spine`, and `## Formatting — one block per spine section`; extend the durable numbered list with batch-2 items before presenting them.

## Step 7 — Execute and close

Execute what batch 1 unblocked per `## What batch-1 execution may and may not do` while the owner rules on batch 2; receipt what you executed, in plain language.

This skill is owner-present by construction, so every Tier-2 item is appended at vet time and then proposed inline and discussed, with items the owner rules on struck immediately.

Apply `## The worth-it gate and the venue ladder` to each proposed follow-up and record each batch-2 ruling to the durable artifact as it lands.

When a batch-2 ruling closes or declines a collector-backed item, strike it from the collector per showrunner duty 4.

## When you're tempted

| Excuse | Reality |
|---|---|
| "I'll deliver everything in one batch" | see `## Delivery mechanics` |
| "Structured questions will be clearer than chat prose" | see `## Delivery mechanics` |
| "That item isn't really the owner's — I'll skip it" | see `## The filter — what is the owner's, and on what grounds` |
| "I'll renumber for clarity in batch 2" | see `## Delivery mechanics` |
| "The contract is long — I'll work from what I remember" | Step 1 reads the file every invocation. |
| "I'll deliver batch 2 after execution finishes" | see `## Delivery mechanics` |
| "The numbers live in the chat — I'll remember" | see Step 4 |
| "I'll append follow-ups to the collector — the owner can review them later" | see `## The worth-it gate and the venue ladder` and showrunner duty 4 — every Tier-2 item is appended at vet time regardless; when the owner is present the item is also proposed in the vet-delivery message and discussed now. |
