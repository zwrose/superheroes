# review-loop.md — Relocation Map (UFR-2)

Records every pre-change instruction unit relocated into
`plugins/review-crew/reference/review-loop.md` (Task 15).

## Relocated Blocks

| Block | Origin skills | Origin heading | Destination |
| ----- | ------------- | -------------- | ----------- |
| `## Learning Loop & Staleness Nudge` (59 lines, including sub-sections: Recording decisions, Staleness nudge, Learning-loop proposal, Provisional-profile confirmation, Recording a dismissal) | `review-crew/review-spec` (lines 461–519), `review-crew/review-plan` (lines 456–514), `review-crew/review-tasks` (lines 448–506) | `## Learning Loop & Staleness Nudge` in each SKILL.md | `plugins/review-crew/reference/review-loop.md` lines 2–59 |

## Notes

- review-spec and review-tasks were byte-identical for this block. review-plan had
  4 minor wording differences (more detail in Provisional-profile confirmation and
  Recording a dismissal sub-sections) with no behavioral difference. The canonical
  version (review-spec / review-tasks) was used as the reference content.
- The block contains `ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"` assignments
  but no `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/<path>` literals, so FR-5
  (leaves-only constraint) is satisfied.
- Each SKILL.md now has a one-hop reference line in place of the block:
  `The shared dispatch/compile/revise learning-loop steps and staleness nudge are in
  \`${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/reference/review-loop.md\` — read it and
  apply it where this skill's flow references those steps.`
