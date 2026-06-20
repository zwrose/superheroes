# review-code.md — Relocation Map (UFR-2)

Records every pre-change instruction unit relocated out of
`plugins/superheroes/skills/review-code/SKILL.md` (Task 16).

## Relocated Blocks

| Block | Origin heading (SKILL.md) | Origin lines (before) | Destination |
| ----- | ------------------------- | --------------------- | ----------- |
| Specialist dispatch prompt template | `### 3. Dispatch Specialists in Parallel` (inner block) | 285–352 | `plugins/superheroes/skills/review-code/reference/auto-fix-loop.md` §Specialist Dispatch Prompt Template |
| Per-agent substitution table + closing dispatch note | `### 3. Dispatch Specialists in Parallel` (table + closing) | 354–364 | `plugins/superheroes/skills/review-code/reference/auto-fix-loop.md` §Per-Agent Substitutions |
| Triage subagent prompt | `### Triage subagent prompt` | 459–503 | `plugins/superheroes/skills/review-code/reference/auto-fix-loop.md` §Triage Subagent Prompt |
| Fixer subagent prompt (heading + guard note + template) | `### Fixer subagent prompt` | 505–572 | `plugins/superheroes/skills/review-code/reference/auto-fix-loop.md` §Fixer Subagent Prompt |
| `## Learning Loop & Staleness Nudge` (58 lines, all sub-sections) | `## Learning Loop & Staleness Nudge` | 687–744 | `plugins/superheroes/reference/review-loop.md` (shared, already exists from Task 15) |
| `## Verification Rules (for subagents)` (11 lines) | `## Verification Rules (for subagents)` | 746–756 | `plugins/superheroes/skills/review-code/reference/auto-fix-loop.md` §Verification Rules (for subagents) |
| `## Common Mistakes` (27 lines, full table) | `## Common Mistakes` | 758–784 | `plugins/superheroes/skills/review-code/reference/auto-fix-loop.md` §Common Mistakes |

## Notes

- All relocated blocks are verbatim (byte-for-byte from SKILL.md into the reference file).
- The Learning Loop section in review-code's SKILL.md had minor wording differences from the canonical review-spec/review-tasks version (more descriptive phrase "after the review output / end-of-loop summary" vs "after the terminal summary"; "Fix as suggested (and any auto-fix the user implicitly accepted by not skipping)" vs "Apply as suggested (and step-6 auto-revises)"; extra detail in Provisional-profile confirmation and Recording-a-dismissal sub-sections). The shared `review-loop.md` canonical (review-spec wording) is used; the pointer from SKILL.md points to that shared file.
- The fixer guard note (lines 507–525) contained `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}` without a `/<path>` suffix, satisfying FR-5 (leaves-only: no literal `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/<path>` references in the reference file).
- The triage and fixer pointer lines were merged into a single `### Triage and Fixer subagent prompts` section to reduce SKILL.md line count.
- Before: 784 lines. After: 499 lines.
- `auto-fix-loop.md` is 259 lines (>100), opens with `<!-- auto-fix-loop-version: 1 -->` and a `## Contents` TOC (FR-6 satisfied).
- `review-crew/review-code` removed from `eval/skills/baseline.json` `knownRedCeilings`.
