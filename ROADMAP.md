# superheroes — roadmap

Where this is going: a band of Claude Code plugins that, once set up, runs much of a
project's development loop — Discovery → Plan → Tasks → Build → Verify → Ship — on
your behalf, so a product-minded owner can live in the *what* while the heroes handle the
*how*. The band now ships the-architect, review-crew, and test-pilot; the phases below add
the rest (producer, coordinator, audit-debt) and harden the loop.

Phases are sequential capability milestones, each gated (from Phase 1 on, a change must
clear the eval harness before it lands). Conventions deferred in
[CONVENTIONS.md §7](CONVENTIONS.md) are bound to the phase that delivers them — noted in
each row.

**Status:** Phases 0–1 complete and released. **Phase 2a-core is in progress:** the escalation
policy (F5) and the producer — **Workhorse** (F3) — are built, hardened, and **released**
(2026-06-19: the-architect `v0.3.0`, review-crew `v0.6.0`, workhorse `v0.1.0`), so a single
work-item now runs Build→Verify→Ship on its own. The **resilience slice** (durable
disk-state-as-truth, idempotent steps, the fenced-lease lock + crash/compaction recovery) is
what remains to close 2a-core, and is **next**. The *Carried follow-ups* table below records the
specific debt each upcoming slice clears, so nothing is lost between slices.

| Phase | Goal | Delivers | Heroes | Conventions it locks (CONVENTIONS §7) |
| --- | --- | --- | --- | --- |
| **0 · Foundations** *(done)* | a clean brand + the contracts everything builds on | rebrand to `superheroes`; [CONVENTIONS.md](CONVENTIONS.md) (calibration, definition-docs, state tiers, disk-state); the eval-harness skeleton | review-crew, test-pilot | — |
| **1 · One issue, supervised** *(landing)* | prove the front half on a single real work-item, with a human watching | the-architect + the review trio, **validated end-to-end on a real issue** (Discovery→Build proven; Verify→Ship driven by hand until the producer exists); evals gate every step | + **the-architect** (spec/plan/tasks), the **review trio** (review-spec/plan/tasks) | — |
| **2a-core · Close the loop (autonomously)** *(escalation + producer shipped; resilience next)* | the producer runs a single work-item Build→Verify→Ship on its own, and survives interruption | **the escalation policy first** (`escalation-base.md` — when to act autonomously vs. ask the owner; authority + reversibility, not "consequence" alone); then the **producer orchestrating Build→Verify→Ship** (the gap the proof exposed — nothing chains Build to review-code today); then resilience — disk-state-as-source-of-truth, idempotent steps, the fenced-lease lock + exactly-once recovery, a crash/compaction spike | + **producer** (core) | **owner-interaction / approval-gate contract**; loop failure / retry / cascade semantics; `resume-brief.md` + `events.jsonl` schemas |
| **2a-plus · Unattended queue** | run a queue of work-items walk-away, across sessions | self-pacing controller; per-checkout isolation; the keepalive daemon; walk-away durability via the state remote | + **coordinator** (issue writes) | GitHub-issue ↔ work-item schema; auth / scopes; cleanup / retention (start) |
| **2b · Define depth** | the front half gets serious: deeper Plan + recursion | richer Plan + the review trio deepened (a dedicated **traceability** reviewer; right-sized per-artifact panels); recursive human-approved decomposition; living calibration that evolves with the project | the-architect, review-crew (deepened) | — |
| **3 · Scale** | lean on native primitives instead of reinventing them | integrate native Dynamic Workflows as the per-issue engine; **convert the model-driven control loops (review-crew's auto-fix loop, the-architect's review loops, test-pilot's execute loop) from prose-orchestrated to deterministic Workflow-style controllers** — control flow in code, judgment in the model; evaluate Agent Teams | producer (deepened), review-crew, test-pilot | — |
| **4 · Polish & onramps** | meet people where they are | greenfield + "productionize a prototype" onramps; audit-debt reconceived as a maintainability guardian; cleanup / GC finished | + **audit-debt** (guardian) | plugin-version / band-compatibility; cleanup / retention (finish) |

## Carried follow-ups (where each lands)

Tracked here so nothing slips between slices:

| Follow-up | Where it's addressed |
| --- | --- |
| **Workhorse dev-server lifecycle** — orphan-on-crash (no persisted PID / scripted teardown) and the unbounded health-poll (no bounded `poll_healthy` helper). | **2a-core · resilience** — durable-lifecycle / liveness work; the slice's core theme. |
| **Systemic `subprocess` timeouts** — none of the five band subprocess seams (`enforcer.classify_path`, `model_tier_resolve`, `reset.engine_json`, `readout.scrub`, `review_result`) pass `timeout=`; a hung sibling stalls the producer. | **2a-core · resilience** — add `timeout=` and treat `TimeoutExpired` as fail-closed (deny / gate) across all five. |
| **Workhorse end-to-end dogfood** — run the producer on a real approved `tasks` item with the band installed (the F3 acceptance gate; the deterministic safety invariants already pass). | **2a-core · resilience** *(open)* — the first acceptance run once the band is installed; validates the shipped producer before the unattended queue. |
| **review-profile Verify-command staleness** — `.claude/review-profile.md`'s `## Verify` omits `plugins/workhorse/lib/tests/`; `repo_doctor` doesn't watch verify-command paths. | **near-term housekeeping** — a `/review-crew:review-init` reconcile; do before the next review-crew run on this repo. |
| **Bare-colon YAML in SKILL.md `description:`** — tolerated today, but strict `yaml.safe_load` can choke (repo-wide: workhorse, review-\*). | **near-term housekeeping** — quote the description values; cheap, no phase dependency. |

This roadmap is a direction, not a contract — phases and scope will move as we learn. The
narrow, *locked* part is [CONVENTIONS.md](CONVENTIONS.md).
