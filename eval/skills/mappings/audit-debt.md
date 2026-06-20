# audit-debt relocation mapping (Task 17)

## Pre-change line count
479

## Post-change line count
443

## Relocated blocks

| Source location in SKILL.md (pre-change) | Destination |
| ----------------------------------------- | ----------- |
| `## Severity Recalibration for Debt Context` section (tier table + note) | `plugins/review-crew/skills/audit-debt/reference/sweep-detail.md` |
| `## Effort Labels` section (label table + sort note) | `plugins/review-crew/skills/audit-debt/reference/sweep-detail.md` |
| `## Common Mistakes` section (mistake table) | `plugins/review-crew/skills/audit-debt/reference/sweep-detail.md` |

## Pointer placed in SKILL.md

Replaced the three sections with a single `## Scoring Reference` paragraph pointing at
`${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/audit-debt/reference/sweep-detail.md`.

## UFR-2 attestation

All three relocated sections are verbatim in `sweep-detail.md`. No decision or routing
logic was moved — only reference tables used after findings are compiled.
