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
| `/superheroes:discuss-open-decisions` | Read the owner-decisions contract from disk, sweep the three bounded sources, filter, deliver batch 1 as numbered chat prose, pause for rulings, execute what batch 1 unblocked, then deliver batch 2. Works in a showrunner charter or any session where the owner explicitly invokes it. Not routing, vetting, or building. |

The seven steps below mirror the contract's delivery mechanics — they do not replace reading the file in Step 1.

## Step 1 — Read the contract

**First action, every invocation:** read `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/showrunner/reference/owner-decisions.md` from disk. The contract is never reconstructed from memory — the skill executes what that file says at delivery time, and cites its sections by heading when pointing at a specific rule (`## The filter — what is the owner's, and on what grounds`, `## The per-item spine`, `## Follow-up economics`, `## Delivery mechanics`, `## Formatting — one block per spine section`, `## Where the items come from, and the bound on that sweep`, `## What batch-1 execution may and may not do`, `## The collector preamble — canonical snippet`).

This skill does **not** restate the contract. The showrunner advisor reads the same file as a standing duty; this skill is the owner pulling that delivery forward on demand. If the file is missing, stop and report — do not substitute prose from this skill or from memory.

## Step 2 — Sweep

Gather candidate items from the three sources the contract bounds in `## Where the items come from, and the bound on that sweep`:

1. **The project's standing-proposals collector** — authoritative. Resolve its path the same way other advisor skills do (profile/decisions store); use the collector preamble from `## The collector preamble — canonical snippet` when the collector needs refreshing.
2. **Open parks on issues and PRs** — best-effort, **not exhaustive** (parks carry no marker or index). Search issues and PRs the session already knows about; do not claim a complete park census.
3. **Anything pending in the current session** — decisions raised but not yet delivered, or delivered in a prior turn without a ruling.

Read the collector before searching parks — the collector is authoritative and may already subsume an in-session duplicate. When the same decision appears in more than one source, keep one entry and note the sources — apply the contract's dedup rule from `## Delivery mechanics` before filtering.

**State the bound to the owner in the delivered message**, not only in this skill: the collector is authoritative; parks and in-session items are gathered best-effort; no sweep is exhaustive. An owner returning from time away needs to hear that bound explicitly so they do not treat a short list as proof nothing else exists in the wild.

## Step 3 — Filter

Apply the owner-needed filter from `## The filter — what is the owner's, and on what grounds`. Items that fail it are dispositioned by the advisor per the contract — **filtered, never swallowed**. List each filtered item with a one-line reason so nothing disappears silently. The owner sees what was considered and why it is not in batch 1 or batch 2.

Routing choices, vet judgments, and build work belong to the advisor — they fail the filter and get a reason, not silence. A decision the advisor can make under standing delegation also fails — say so plainly rather than batching it as if it were the owner's call.

Present filtered items in a separate short list before batch 1 — the contract's "filtered, never swallowed" rule means the owner sees disposition, not absence.

## Step 4 — Deliver batch 1

Deliver only what **blocks the advisor's next action** — per `## Delivery mechanics` and batch-1 rules. **Never** batch-1 new-issue filings; those are follow-ups the advisor proposes after rulings, not decisions blocking the next beat.

Present as numbered chat prose using the full per-item spine from `## The per-item spine`, with formatting from `## Formatting — one block per spine section` — one block per spine section, stable numbers starting at 1. Do not use a structured-question widget in place of the spine; the contract's delivery shape is chat prose the owner can answer inline.

## Step 5 — Pause for rulings

**Stop here and wait.** This is the point of the skill: batch 1 is incomplete without the owner's rulings. Do not deliver batch 2 in the same turn and call it two batches — the pause is real. Do not execute batch-1 work before the owner rules unless the contract explicitly allows an exception (it does not for merge, release, publish, or force-push).

The owner may answer inline, defer an item, or ask for more context — record the ruling per item before moving on. Partial batch-1 answers still block Step 6 for the unanswered items.

If batch 1 is empty after filtering, say so plainly — filtered items still get their reasons — and skip to Step 7 when there is nothing blocking. Do not invent batch-1 filler to justify the invocation.

## Step 6 — Execute what batch 1 unblocked

After the owner rules on batch 1, execute advisor-side work the rulings unblock — bounded exactly by `## What batch-1 execution may and may not do` in the contract: advisor-side work only; **never** merge, release, publish, or force-push — those are the owner's click, and this skill's job is to make it one click, not to take it.

For merge-train and release coordination that batch-1 execution may include, follow **showrunner duty 6** rather than restating its conditions here. If a ruling only unblocks batch 2 items, skip execution and proceed to Step 7. Receipt what you executed in plain language so the owner sees batch-1 rulings landed before batch 2 opens.

Owner clicks the merge button, the release merge, the publish action, and any force-push — batch-1 execution prepares those paths; it does not take them.

## Step 7 — Deliver batch 2

Deliver everything else that survived the filter — same per-item spine, same formatting, stable numbering carried forward from batch 1 (do not renumber items between batches). Follow-up economics from `## Follow-up economics` govern what happens after batch 2 rulings — proposed follow-ups land in the collector, not as silent new issues filed by this skill.

Batch 2 may be long; that is fine. The owner asked for the full walkthrough. Do not trim items to save tokens — the filter and batch split already scoped what belongs in each half.

When batch 2 rulings propose follow-ups, append them to the standing-proposals collector per `## Follow-up economics` — the owner sees the proposal; the advisor files nothing silently from this skill.

## When you're tempted

These excuses show up most often when the owner is waiting or the list is long:

| Excuse | Reality |
|---|---|
| "I'll deliver everything in one batch — faster for the owner" | Batch 1 exists because some calls block the advisor's next action; collapsing the batches hides the pause the skill exists to create. |
| "Structured questions will be clearer than chat prose" | The contract delivers numbered chat prose — a structured-question tool is not a substitute for the spine. |
| "That item isn't really the owner's — I'll skip it" | Filtered items get a one-line reason in the delivered message; swallowing them violates the contract. |
| "I'll renumber for clarity in batch 2" | Stable numbering across batches is part of the spine — renumbering breaks follow-up economics. |
| "The contract is long — I'll work from what I remember" | Step 1 reads the file every time; memory drift is how undelivered calls pile up in the first place. |
| "Batch 2 can wait until the next session" | The owner invoked this skill for the full walkthrough — deliver batch 2 in the same charter turn once batch 1 execution completes. |
