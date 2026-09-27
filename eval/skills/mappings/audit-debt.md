# audit-debt relocation mapping (Task 17)

> **Note (plugin-root form).** Paths quoted below are shown in the current `${CLAUDE_PLUGIN_ROOT}` form; when this record was written they carried a fallback form of the root variable, since retired.

## Pre-change line count
479

## Post-change line count
443

## Relocated blocks

| Source location in SKILL.md (pre-change) | Destination |
| ----------------------------------------- | ----------- |
| `## Severity Recalibration for Debt Context` section (tier table + note) | `plugins/superheroes/skills/audit-debt/reference/sweep-detail.md` |
| `## Effort Labels` section (label table + sort note) | `plugins/superheroes/skills/audit-debt/reference/sweep-detail.md` |
| `## Common Mistakes` section (mistake table) | `plugins/superheroes/skills/audit-debt/reference/sweep-detail.md` |

## Pointer placed in SKILL.md

Replaced the three sections with a single `## Scoring Reference` paragraph pointing at
`${CLAUDE_PLUGIN_ROOT}/skills/audit-debt/reference/sweep-detail.md`.

## UFR-2 attestation

All three relocated sections are verbatim in `sweep-detail.md`. No decision or routing
logic was moved — only reference tables used after findings are compiled.
