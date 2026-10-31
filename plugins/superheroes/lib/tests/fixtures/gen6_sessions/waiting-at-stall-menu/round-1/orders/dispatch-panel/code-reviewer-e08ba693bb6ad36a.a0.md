You are reviewing pr for repo unknown, target unknown.
Review session mode was not set in session metadata or driver configuration; defaulting to PR review.

## Your assignment
Review the diff at /tmp/claude-0/-home-user-wt-2239/8976e1b6-81e0-5ce6-a13f-fb94ea2e780c/scratchpad/gen6x/gen6_out/waiting-at-stall-menu/round-1/diff.txt for your dimension.
Read `diff.txt` in bounded chunks (<=800 lines): use Read offset/limit when
available, or an equivalent bounded shell range. Never one whole-file read.
Continue with later offsets until the diff is covered.
Read the base rubric (absolute path below) for severity calibration,
verification rules, and the panel output format. Read the project calibration
and CLAUDE.md for threat model, scope, focus hints, canonical patterns, and
conventions. Apply the diff-scope rule: only flag code in `+` or
`-` lines.

## Context files
- Diff: /tmp/claude-0/-home-user-wt-2239/8976e1b6-81e0-5ce6-a13f-fb94ea2e780c/scratchpad/gen6x/gen6_out/waiting-at-stall-menu/round-1/diff.txt
- Base rubric (severity, verification rules, panel output format): /tmp/claude-0/-home-user-wt-2239/8976e1b6-81e0-5ce6-a13f-fb94ea2e780c/scratchpad/gen6full/gen6/plugins/superheroes/rubric/review-base.md
- Core calibration (threat model, canonical patterns): (Core calibration not resolved for this project)
- Review-crew layer (scope exclusions, focus hints, conventions): (Review-crew layer calibration not resolved for this project)
- CLAUDE.md (project conventions): (this project has no CLAUDE.md at /tmp/claude-0/-home-user-wt-2239/8976e1b6-81e0-5ce6-a13f-fb94ea2e780c/scratchpad/gen6x/gen6_out/waiting-at-stall-menu/checkout)
- Your role brief (read it first; it binds over the generic assignment above): /tmp/claude-0/-home-user-wt-2239/8976e1b6-81e0-5ce6-a13f-fb94ea2e780c/scratchpad/gen6full/gen6/plugins/superheroes/agents/code-reviewer.md


- Prior comments + author justifications: (prior-comments-unavailable — orchestrator did not supply prior-comments.json)


## Calibration precedence
Base rubric (binding) > CLAUDE.md (conventions) > core + layer (adder over CLAUDE.md)
> strict fallback when a needed field is absent in all of them.

## Diff-scope rule — CRITICAL
You are reviewing CHANGES MADE BY THIS PR/BRANCH. Do NOT flag pre-existing
issues. Only flag code in `+` or `-` lines of the diff. Context lines
(no prefix) and unchanged code in modified files are pre-existing — SKIP
them, even if they violate conventions. That's the #1 source of false
positives.

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
No prior-comments.json was supplied for this PR — there are no prior review comments or author justifications to consult.
If a previous review flagged a finding and the author replied
with substantive explanatory text (not just "ok" or an emoji) explaining
why it's intentional, **raise the finding AND note the prior justification**
in the body — do NOT silently omit it. The **post-verification**
author-justification filter (after `verification.merge_and_rank`) owns the
drop decision: it may drop only a non-CONFIRMED finding (quoting the
justification); a CONFIRMED finding survives stamped
`challenge: "author-justified"`. Outdated comments (where
`position == null`) still count.

## Delivery
Deliver per the base rubric's panel output-format section. Set `tradeoff: true` only when an
issue has multiple valid fix approaches (a judgment call); omit it otherwise (see the base
rubric's "Triage rubric"). Set `dimension` to "Code" on every entry. Severity caps
from the base rubric apply (at most 5 code-quality-only Nits reported per review round across all seats; real-consequence Nits are uncapped).
Format only — your findings replace every value; an echoed example grades hollow.
{
  "findings": [
    {
      "body": "body placeholder [RFS-EXAMPLE-SENTINEL-1145]",
      "confidence": "High",
      "consequence": "consequence placeholder [RFS-EXAMPLE-SENTINEL-1145]",
      "consequenceKind": "code-quality",
      "dimension": "Architecture",
      "evidence": "evidence placeholder [RFS-EXAMPLE-SENTINEL-1145]",
      "file": "file placeholder [RFS-EXAMPLE-SENTINEL-1145]",
      "id": "id placeholder [RFS-EXAMPLE-SENTINEL-1145]",
      "line": null,
      "severity": "Critical",
      "suggestion": "suggestion placeholder [RFS-EXAMPLE-SENTINEL-1145]",
      "taxonomy": "taxonomy placeholder [RFS-EXAMPLE-SENTINEL-1145]",
      "title": "title placeholder [RFS-EXAMPLE-SENTINEL-1145]",
      "tradeoff": null
    }
  ],
  "investigated": [
    "investigated-path placeholder [RFS-EXAMPLE-SENTINEL-1145]"
  ]
}

Deliver a single JSON object of this shape on the runner's declared result channel: the runner appends the authoritative result contract at the end of this prompt — when it names a result file, write exactly that file and reply DONE; otherwise emit the object as your final response with nothing after it. Never write a landing file (read-only sandbox). Replace every value in the example above with your own review content — do not echo the example. A review with nothing to flag emits `"findings": []` (an empty list).
List in `investigated` every repo-relative path you actually read to ground this review — always, whether or not you found anything. do not write a findings file (read-only sandbox — nothing reads one).

## What you may run

You review by reading. You may read, list and search files, including with read-only inspection commands. You never run the project's own files, scripts or tests. A run you need is the driver's: name it in your result, and the driver runs the project's declared verify command.

## Ratified residuals

Residuals below are read from the calibration store file (not base-pinned).

Residuals could not be read: core-unreadable-or-absent.

## Project threat model (project calibration, quoted data)

The project's threat model could not be read: core calibration not resolved.

## Standing rulings (recorded this session, quoted data)

No standing rulings are recorded for this session.

## Payload contract

Your result must carry a payload matching this shape:

Required keys: (none)
Optional keys: findings, confidence, tier, receiptMissing, receiptStale, vacuous, reason
confidence type: non-empty-string
findings type: list-of-objects
reason type: string
receiptMissing type: boolean
receiptStale type: boolean
tier type: non-empty-string
vacuous type: boolean
Conditional — findings: required unless the seat declared it did not run (vacuous is True or reason is a not-run outcome token)
Also enforced — findings-unless-not-run: findings is required unless vacuous is True or reason is a not-run outcome token

## Return your result

Deliver the object on the runner's declared result channel: the runner appends the authoritative result contract at the end of this prompt — when it names a result file, write exactly that file and reply DONE; otherwise emit the object as your final response with nothing after it. Never write a landing file (read-only sandbox).
