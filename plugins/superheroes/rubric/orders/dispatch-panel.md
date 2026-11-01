You are reviewing {{MODE}} for repo {{REPO}}, target {{TARGET}}.
{{MODE_EVIDENCE}}

## Your assignment
Review the diff at {{DIFF_PATH}} for your dimension.
Read `diff.txt` in bounded chunks (<=800 lines): use Read offset/limit when
available, or an equivalent bounded shell range. Never one whole-file read.
Continue with later offsets until the diff is covered.
Read the base rubric (absolute path below) for severity calibration,
verification rules, and the panel output format. Read the project calibration
and CLAUDE.md for threat model, scope, focus hints, canonical patterns, and
conventions. Apply the diff-scope rule: only flag code in `+` or
`-` lines.

{{SLICE_SCOPE_LINE}}

## Context files
- Diff: {{DIFF_PATH}}
- Base rubric (severity, verification rules, panel output format): {{RUBRIC_PATH}}
- Core calibration (threat model, canonical patterns): {{CORE_PATH}}
- Review-crew layer (scope exclusions, focus hints, conventions): {{LAYER_PATH}}
- CLAUDE.md (project conventions): {{CLAUDE_MD_PATH}}
{{ROLE_BRIEF_LINE}}
{{RISK_AREAS_LINE}}
{{BREAK_IT_GRAMMAR_BLOCK}}
{{PRIOR_COMMENTS_CONTEXT_LINE}}
{{FOCUS_CONTEXT_LINE}}

## Calibration precedence
Base rubric (binding) > CLAUDE.md (conventions) > core + layer (adder over CLAUDE.md)
> strict fallback when a needed field is absent in all of them.

## Diff-scope rule — CRITICAL
You are reviewing CHANGES MADE BY THIS PR/BRANCH. Raise a finding on the change
only on the lines it touched: the `+` lines, and the line on each side of a `-`
line. Context lines (no prefix) and unchanged code in modified files are
untouched; an issue there is not a finding on the change. If you notice a real
defect there while reading, you may add it as an outside finding: at most 3 outside
finding entries, from your own reading, each cited at its real `file:line` with its
consequence stated. They go to the record's "Outside this PR" list and never block.
The base rubric's Verification rule 2 states the rule.

## Verification rules
- `file:line` citation required. No citation → drop your own finding
  before writing it out. Cite `line` as an integer (a JSON number, e.g. `"line": 291`). A numeric
  string (`"291"`) is coerced to its integer; any other non-integer line is refused at compile
  (`line is not an integer`) and the finding is dropped.
- Before flagging "missing X", grep the codebase (PR checkout, in PR mode)
  for X under different names.
- For Important-severity issues, check callers / reachability before asserting.
  If the only caller already guards the edge case, downgrade or drop.
- For docs/spec changes, spot-check factual claims (function signatures,
  error types, file paths) against actual source.

## Author-justification rule (PR mode only)
{{PRIOR_COMMENTS_INSTRUCTION_BLOCK}}
If a previous review flagged a finding and the author replied
with substantive explanatory text (not just "ok" or an emoji) explaining
why it's intentional, **raise the finding AND note the prior justification**
in the body — do NOT silently omit it. The **post-verification**
author-justification filter (after `verification.merge_and_rank`) owns the
drop decision: it may drop only a non-CONFIRMED finding (quoting the
justification); a CONFIRMED finding survives stamped
`challenge: "author-justified"`. Outdated comments (where
`position == null`) still count.

## What you read
Return your read list as the base rubric's panel output-format section defines it,
covering only what you actually read.

## Delivery
Deliver per the base rubric's panel output-format section. Set `tradeoff: true` only when an
issue has multiple valid fix approaches (a judgment call); omit it otherwise (see the base
rubric's "Triage rubric"). Set `dimension` to "{{DIMENSION}}" on every entry. Severity caps
from the base rubric apply (at most 5 code-quality-only Nits reported per review round across all seats; real-consequence Nits are uncapped).
On every finding name its kind of mistake with the other touched places that share it, and write its search description, as the base rubric's panel output-format section defines them.
{{OUTPUT_CHANNEL_BLOCK}}
