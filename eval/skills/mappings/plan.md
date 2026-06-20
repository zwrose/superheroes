# plan relocation mapping (Task 17)

## Pre-change line count
391

## Post-change line count
351

## Relocated blocks

| Source location in SKILL.md (pre-change) | Destination |
| ----------------------------------------- | ----------- |
| `### 5. Self-review` checklist body (design-quality hard gates, LLM failure-mode guards, doc quality markers, coverage & cleanup items) | `plugins/the-architect/skills/plan/reference/method-detail.md` |

## Pointer placed in SKILL.md

Replaced the self-review checklist body with a single paragraph under `### 5. Self-review`
pointing at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/plan/reference/method-detail.md`.

## UFR-2 attestation

The relocated checklist is verbatim in `method-detail.md`. No decision or routing logic
was moved — only the reference checklist items used during the self-review pass.
