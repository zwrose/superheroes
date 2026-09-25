# plan relocation mapping (Task 17)

> **Status (v2): historical.** Maps the retired v1 skill surface (architect-plan, retired in #478/#479). Kept as provenance; the v2 review-eval rebuild rides the S2 lane (#476).

> **Note (plugin-root form).** Paths quoted below are shown in the current `${CLAUDE_PLUGIN_ROOT}` form; when this record was written they carried a fallback form of the root variable, since retired.

## Pre-change line count
391

## Post-change line count
351

## Relocated blocks

| Source location in SKILL.md (pre-change) | Destination |
| ----------------------------------------- | ----------- |
| `### 5. Self-review` checklist body (design-quality hard gates, LLM failure-mode guards, doc quality markers, coverage & cleanup items) | `plugins/superheroes/skills/architect-plan/reference/method-detail.md` |

## Pointer placed in SKILL.md

Replaced the self-review checklist body with a single paragraph under `### 5. Self-review`
pointing at `${CLAUDE_PLUGIN_ROOT}/skills/architect-plan/reference/method-detail.md`.

## UFR-2 attestation

The relocated checklist is verbatim in `method-detail.md`. No decision or routing logic
was moved — only the reference checklist items used during the self-review pass.
