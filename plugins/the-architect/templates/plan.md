{{frontmatter}}
# {{Title}} — Plan

<!-- AUTHOR GUIDANCE — DELETE this comment before the plan is finalized. It must not
     appear in the finished doc.

  The plan is the technical *how* for an approved spec (its parent). Audience: the build
  (engineers/agents), so it MAY use technical language — unlike the spec. Default = decide
  autonomously; escalate only the consequential decisions per the `plan` skill's rubric, and
  record EVERY significant decision below (escalated or not) with its reversibility. Every
  spec requirement must be addressed here; add nothing the spec doesn't justify (no
  gold-plating). Prefer the simplest approach that meets the spec, and reversible/standard/
  swappable choices over one-way doors.
-->

## Overview

{{The technical approach in brief: the strategy for building what the spec asks, and why
this shape. One or two paragraphs.}}

## Architecture

{{How the pieces fit — the overall structure and how it satisfies the spec. Prose or a
diagram. Scoped to THIS work; don't redesign the world.}}

## Components & interfaces

{{The units this work adds or changes — each with one clear responsibility and its
interface (inputs / outputs / contract). What depends on what.}}

## Data flow & data model

{{How data moves through the work, and the shape of any new or changed data. Call out the
data model explicitly — it is a one-way door (see Key decisions).}}

## How the requirements are met

{{Map the plan back to the spec: each functional requirement, each non-functional
requirement, and each significant unhappy path → how this plan satisfies it. The coverage
check: nothing in the spec left unaddressed, nothing here the spec doesn't ask for.}}

## Key decisions & alternatives

{{An ADR-style log of the significant technical decisions. For each: the decision, the
options considered, the choice and why, whether it is reversible (two-way door) or hard to
undo (one-way door), and whether it was ESCALATED to the owner (with their call recorded).
Engineering-internal significant decisions are recorded here too — they simply weren't
escalated.}}

- **Decision:** {{…}} · **Options:** {{…}} · **Choice + why:** {{…}} · **Reversible?** {{two-way / one-way}} · **Escalated?** {{no / yes — owner chose …}}

## Risks & mitigations

{{What could go wrong during build/verify, and how the plan mitigates it. Include
first-of-a-kind / novel work (technical risk) here.}}

## UI / UX

{{For user-facing work: how the UI gets built, referencing the spec's Claude Design handoff
output. Omit this section if the work is not user-facing.}}
