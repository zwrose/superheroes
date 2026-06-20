# Task 16 Report — review-code split under 500 (FR-9)

## Summary

**Status:** Complete
**Before → After line count:** 784 → 499 lines
**auto-fix-loop.md line count:** 259 lines (TOC present, FR-6 satisfied)

## Blocks Moved

| Block | Origin lines | Destination |
| ----- | ------------ | ----------- |
| Specialist dispatch prompt template | 285–352 | `reference/auto-fix-loop.md` §Specialist Dispatch Prompt Template |
| Per-agent substitution table + closing dispatch note | 354–364 | `reference/auto-fix-loop.md` §Per-Agent Substitutions |
| Triage subagent prompt | 459–503 | `reference/auto-fix-loop.md` §Triage Subagent Prompt |
| Fixer subagent prompt (heading + guard note + template) | 505–572 | `reference/auto-fix-loop.md` §Fixer Subagent Prompt |
| Learning Loop & Staleness Nudge (58 lines) | 687–744 | `reference/review-loop.md` (shared) |
| Verification Rules (for subagents) (11 lines) | 746–756 | `reference/auto-fix-loop.md` §Verification Rules |
| Common Mistakes (27 lines) | 758–784 | `reference/auto-fix-loop.md` §Common Mistakes |

## Validation

- `python3 .github/scripts/validate_skills.py; echo "exit=$?"` → **exit=0**
- `python3 .github/scripts/validate_hosts.py; echo "exit=$?"` → **exit=0**

## Notes

- Learning Loop wording in review-code differed slightly from the canonical review-spec/review-tasks version (more descriptive phrases, extra detail in sub-sections). Pointer uses the shared `reference/review-loop.md` (same as other skills after Task 15).
- Triage and Fixer pointer lines were merged into a single `### Triage and Fixer subagent prompts` section to stay under the 499-line ceiling.
- `review-crew/review-code` removed from `eval/skills/baseline.json` knownRedCeilings.
- Mapping recorded in `eval/skills/mappings/review-code.md`.

---

## Fix subagent addendum — restore structural-guard invariant

**Status:** Complete  
**Commit:** `ee8868a`  
**review-code SKILL.md final line count:** 468 lines (≤ 499 ceiling)

### Problem
Task 16's split moved the per-agent substitution table into `reference/auto-fix-loop.md`. The test `test_dispatch_tables.py::test_full_crew_table_has_one_row_per_agent[review-code]` parses `skills/review-code/SKILL.md` for that table and found it empty, causing 1 failure (187 pass + 1 fail).

### What was moved back
The per-agent substitution table (5 reviewer rows: architecture-reviewer/code-reviewer/security-reviewer/test-reviewer/premortem-reviewer) was restored verbatim into `SKILL.md` under `### 3. Dispatch Specialists in Parallel`, immediately after the dispatch launch instruction. This added 13 lines.

### What was relocated to compensate
The `--post` API command blocks and their surrounding detail prose (review JSON template, `resolve_diff_lines.py` invocation, `gh api` posting call, post-submit verification call, and the 422 error-handling note — 43 lines) were moved from `SKILL.md` into a new `## --post API Commands` section in `reference/auto-fix-loop.md`. These were replaced in `SKILL.md` with a 1-line reference pointer. Net: −42 lines from SKILL.md. The `## Contents` TOC in auto-fix-loop.md was updated accordingly.

### Verification results
- `wc -l SKILL.md` → **468 lines** (≤ 499 ceiling ✓)
- `python3 -m pytest plugins/review-crew/lib/tests/test_dispatch_tables.py -q` → **15 passed** (all dispatch-table tests pass, including review-code ✓)
- `python3 -m pytest plugins/review-crew/lib/tests/ -q` → **188 passed** (was 187 pass + 1 fail; now clean ✓)
- `validate_skills.py` → exit=0 ✓
- `validate_hosts.py` → exit=0 ✓
- FR-5: no `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/<path>` literal in `auto-fix-loop.md` ✓
- `description:` frontmatter in SKILL.md unchanged ✓
