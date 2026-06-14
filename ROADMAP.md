# superheroes — roadmap

Where this is going: a band of Claude Code plugins that, once set up, runs much of a
project's development loop — Discovery → Plan → Tasks → Build → Verify → Integrate — on
your behalf, so a product-minded owner can live in the *what* while the heroes handle the
*how*. Today the band ships two heroes (review-crew, test-pilot); the phases below add the
rest and harden the loop.

Phases are sequential capability milestones, each gated (from Phase 1 on, a change must
clear the eval harness before it lands). Conventions deferred in
[CONVENTIONS.md §7](CONVENTIONS.md) are bound to the phase that delivers them — noted in
each row.

**Status:** Phase 0 complete. Phase 1 (one issue, evals-gated) is next.

| Phase | Goal | Delivers | Heroes | Conventions it locks (CONVENTIONS §7) |
| --- | --- | --- | --- | --- |
| **0 · Foundations** *(done)* | a clean brand + the contracts everything builds on | rebrand to `superheroes`; [CONVENTIONS.md](CONVENTIONS.md) (calibration, define-docs, state tiers, disk-state); the eval-harness skeleton | review-crew, test-pilot | — |
| **1 · One issue, supervised** *(next)* | prove the full loop on a single work-item, with a human watching | one work-item taken Discovery→Integrate end-to-end; evals gate every step | + **the-architect** (spec/plan/tasks), the **review trio** (review-spec/plan/tasks) | — |
| **2a-core · Survive interruption** | the loop can be killed and resumed without losing or duplicating work | disk-state-as-source-of-truth; idempotent steps; the fenced-lease lock + exactly-once recovery; a crash/compaction spike | + **producer** (core) | loop failure / retry / cascade semantics; `resume-brief.md` + `events.jsonl` schemas |
| **2a-plus · Unattended queue** | run a queue of work-items walk-away, across sessions | self-pacing controller; per-checkout isolation; the keepalive daemon; walk-away durability via the state remote | + **coordinator** (issue writes) | GitHub-issue ↔ work-item schema; owner-interaction / approval-gate contract; auth / scopes; cleanup / retention (start) |
| **2b · Define depth** | the front half gets serious: deeper Plan + recursion | richer Plan + the full review trio; recursive human-approved decomposition; living calibration that evolves with the project | the-architect, review-crew (deepened) | — |
| **3 · Scale** | lean on native primitives instead of reinventing them | integrate native Dynamic Workflows as the per-issue engine; evaluate Agent Teams | producer (deepened) | — |
| **4 · Polish & onramps** | meet people where they are | greenfield + "productionize a prototype" onramps; audit-debt reconceived as a maintainability guardian; cleanup / GC finished | + **audit-debt** (guardian) | plugin-version / band-compatibility; cleanup / retention (finish) |

This roadmap is a direction, not a contract — phases and scope will move as we learn. The
narrow, *locked* part is [CONVENTIONS.md](CONVENTIONS.md).
