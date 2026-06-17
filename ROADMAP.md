# superheroes — roadmap

Where this is going: a band of Claude Code plugins that, once set up, runs much of a
project's development loop — Discovery → Plan → Tasks → Build → Verify → Integrate — on
your behalf, so a product-minded owner can live in the *what* while the heroes handle the
*how*. The band now ships the-architect, review-crew, and test-pilot; the phases below add
the rest (producer, coordinator, audit-debt) and harden the loop.

Phases are sequential capability milestones, each gated (from Phase 1 on, a change must
clear the eval harness before it lands). Conventions deferred in
[CONVENTIONS.md §7](CONVENTIONS.md) are bound to the phase that delivers them — noted in
each row.

**Status:** Phase 0 complete. Phase 1 **landing** — the-architect + the review trio are built
and were validated end-to-end on a real issue (the trio caught a Critical + 14 Important across
spec/plan/tasks; the cross-plugin gate-writes and loop-enforcement held in a shipped-band run).
Finalizing as review-crew `0.4.0`. **Phase 2a-core (close the loop) is next.**

| Phase | Goal | Delivers | Heroes | Conventions it locks (CONVENTIONS §7) |
| --- | --- | --- | --- | --- |
| **0 · Foundations** *(done)* | a clean brand + the contracts everything builds on | rebrand to `superheroes`; [CONVENTIONS.md](CONVENTIONS.md) (calibration, definition-docs, state tiers, disk-state); the eval-harness skeleton | review-crew, test-pilot | — |
| **1 · One issue, supervised** *(landing)* | prove the front half on a single real work-item, with a human watching | the-architect + the review trio, **validated end-to-end on a real issue** (Discovery→Build proven; Verify→Integrate driven by hand until the producer exists); evals gate every step | + **the-architect** (spec/plan/tasks), the **review trio** (review-spec/plan/tasks) | — |
| **2a-core · Close the loop (autonomously)** | the producer runs a single work-item Build→Verify→Integrate on its own, and survives interruption | **the escalation policy first** (`escalation-base.md` — when to act autonomously vs. ask the owner; authority + reversibility, not "consequence" alone); then the **producer orchestrating Build→Verify→Integrate** (the gap the proof exposed — nothing chains Build to review-code today); then resilience — disk-state-as-source-of-truth, idempotent steps, the fenced-lease lock + exactly-once recovery, a crash/compaction spike | + **producer** (core) | **owner-interaction / approval-gate contract**; loop failure / retry / cascade semantics; `resume-brief.md` + `events.jsonl` schemas |
| **2a-plus · Unattended queue** | run a queue of work-items walk-away, across sessions | self-pacing controller; per-checkout isolation; the keepalive daemon; walk-away durability via the state remote | + **coordinator** (issue writes) | GitHub-issue ↔ work-item schema; auth / scopes; cleanup / retention (start) |
| **2b · Define depth** | the front half gets serious: deeper Plan + recursion | richer Plan + the review trio deepened (a dedicated **traceability** reviewer; right-sized per-artifact panels); recursive human-approved decomposition; living calibration that evolves with the project | the-architect, review-crew (deepened) | — |
| **3 · Scale** | lean on native primitives instead of reinventing them | integrate native Dynamic Workflows as the per-issue engine; **convert the model-driven control loops (review-crew's auto-fix loop, the-architect's review loops, test-pilot's execute loop) from prose-orchestrated to deterministic Workflow-style controllers** — control flow in code, judgment in the model; evaluate Agent Teams | producer (deepened), review-crew, test-pilot | — |
| **4 · Polish & onramps** | meet people where they are | greenfield + "productionize a prototype" onramps; audit-debt reconceived as a maintainability guardian; cleanup / GC finished | + **audit-debt** (guardian) | plugin-version / band-compatibility; cleanup / retention (finish) |

This roadmap is a direction, not a contract — phases and scope will move as we learn. The
narrow, *locked* part is [CONVENTIONS.md](CONVENTIONS.md).
