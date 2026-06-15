{{frontmatter}}
# {{Title}} — Plan

<!-- AUTHOR GUIDANCE — DELETE this comment before the plan is finalized. It must not
     appear in the finished doc.

  The plan is the technical *how* for an approved spec (its parent). Audience: the build
  (engineers/agents), so it MAY use technical language — unlike the spec.

  - Decide autonomously; escalate only the consequential decisions per the `plan` skill's
    rubric. Record EVERY significant decision in Key decisions with its reversibility and a
    named accepted downside; ≥2 materially different options must have been weighed.
  - Cover every spec requirement; add nothing the spec doesn't justify (no gold-plating).
    Prefer the simplest, most boring approach and reversible/swappable choices.
  - RIGHT-SIZE to the spec's `size`: small → fill the core sections, collapse the
    situational ones (Cross-cutting, Rollout & migration, Dependencies & assumptions) to a
    line or "N/A — because …"; large → every section substantive. A situational section is
    always present as a heading, marked "N/A — because …", never silently dropped.
  - ALTITUDE: strategy here, steps in Tasks. No pasted full schemas, full code, test cases,
    or dated rollout sequences — those belong to the `tasks` doc.
  - The loop RESOLVES, it does not park: there are no "open questions" — escalate, make it a
    Risk-with-contingency, defer it to Tasks, or loop back.
-->

## Overview

{{The technical approach in brief: the strategy for building what the spec asks, and why
this shape. One or two paragraphs.}}

## Goals & non-goals

{{**Goals:** what this plan sets out to achieve (from the spec). **Non-goals:** things that
could reasonably be goals but are deliberately excluded here (e.g. "offline support is a
non-goal"; "multi-tenant is a non-goal"). Non-goals are the cheapest scope control — name
them.}}

## Architecture

{{How the pieces fit — the overall structure and how it satisfies the spec. A system-context
sketch or prose, kept higher than code. Scoped to THIS work; don't redesign the world.}}

## Components & interfaces

{{The units this work adds or changes — each with one clear responsibility and its interface
(inputs / outputs / contract / error cases), and how it fits existing interfaces. What
depends on what. Interfaces at design altitude — don't paste full formal definitions.}}

## Data flow & data model

{{How data moves through the work, and the shape of any new or changed data. Call out the
data model explicitly — it is a one-way door (see Key decisions), so note backward/forward
compatibility if existing data is touched.}}

## How the requirements are met

{{Map the plan back to the spec: each functional requirement, each non-functional
requirement, and each significant unhappy path → how this plan satisfies it. The coverage
check: nothing in the spec left unaddressed, nothing here the spec doesn't ask for.}}

## Key decisions & alternatives

{{An ADR-style log of the significant technical decisions. For each: the decision, the
**≥2 options** considered, the choice and why, the **accepted downside**, whether it is
reversible (two-way door) or hard to undo (one-way door), and whether it was ESCALATED to
the owner (with their call recorded). Engineering-internal significant decisions are
recorded here too — they simply weren't escalated.}}

- **Decision:** {{…}} · **Options weighed:** {{≥2, materially different}} · **Choice + why:** {{…}} · **Accepted downside:** {{…}} · **Reversible?** {{two-way / one-way}} · **Escalated?** {{no / yes — owner chose …}}

## Cross-cutting concerns

{{Each subsection: a short "how the design addresses it", or "N/A — because …". Keep it to
the *what/strategy*, not the wiring (that's Tasks).}}

- **Security & privacy:** {{new PII? new trust boundary? authn/authz change? injection/
  validation surface? If none: "N/A — because …".}}
- **Observability:** {{what to measure, and the answer to "how does on-call debug this at
  2am?" — what signals, what they'd look at. If none: "N/A — because …".}}
- **Reliability & failure modes:** {{the dependencies this relies on (critical = fail vs
  non-critical = degrade), and the degraded behaviour. If trivial: "N/A — because …".}}

## Rollout & migration

{{*(Conditional — required for anything stateful, API-facing, or user-visible; "N/A —
because …" for a pure internal refactor.)* The rollout **strategy** (flag / canary) and the
**rollback / kill-switch** mechanism; for data, the migration **approach**
(expand–migrate–contract) and backwards-compatibility. The dated steps go to Tasks.}}

## Risks & mitigations

{{**Pre-mortem:** "it's six months out and this failed in production — why?" List the top
failure/build risks (novel work, hard integration, partial failure, concurrency, resource
exhaustion) and the mitigation for each. Build/verify risks live here; runtime failure
*modes* live in Cross-cutting → Reliability.}}

## Dependencies & assumptions

{{**Dependencies:** what this work relies on that isn't built here — other work-items/PRs
that must land first, external services, owner-provided data/accounts. (Surfaces blockers
for sequencing.) **Assumptions:** the premises this plan commits to (e.g. "the existing
rate limit is sufficient"); the build and review can check them. A shaky assumption is a
Risk or an escalation, not a parked question.}}

## UI / UX

{{For user-facing work: how the UI gets built, referencing the spec's Claude Design handoff
output. Omit this section if the work is not user-facing.}}
