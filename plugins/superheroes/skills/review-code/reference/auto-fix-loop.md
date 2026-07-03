<!-- auto-fix-loop-version: 1 -->
## Contents

1. [Specialist Dispatch Prompt Template](#specialist-dispatch-prompt-template)
2. [Triage Subagent Prompt](#triage-subagent-prompt)
3. [Fixer Subagent Prompt](#fixer-subagent-prompt)
4. [Verification Rules (for subagents)](#verification-rules-for-subagents)
5. [Common Mistakes](#common-mistakes)
6. [--post API Commands](#--post-api-commands)

---

## Specialist Dispatch Prompt Template

Each specialist receives the same prompt template, parameterized by reviewer name, dimension label, and findings filename. Embed the **absolute** base-rubric path (the expanded value of `RUBRIC`), `$CORE` (threat model + canonical patterns), and `$LAYER` (scope, focus, conventions). When both point at the same legacy file, read all sections from that path. Subagents do not inherit shell vars.

```
You are reviewing <mode> for repo <repo>, target <pr-or-branch>.

## Your assignment
Review the diff at $SESSION_DIR/round-<round>/diff.txt for your dimension.
Read the base rubric (absolute path below) for severity calibration,
verification rules, and the findings output format. Read the project calibration
and CLAUDE.md for threat model, scope, focus hints, canonical patterns, and
conventions. Apply the diff-scope rule: only flag code in `+` or
`-` lines.

## Context files
- Diff: $SESSION_DIR/round-<round>/diff.txt
- Base rubric (severity, verification rules, findings format): <absolute RUBRIC path>
- Core calibration (threat model, canonical patterns): <CORE_PATH>
- Review-crew layer (scope exclusions, focus hints, conventions): <LAYER_PATH>
- CLAUDE.md (project conventions): CLAUDE.md
- <PR read-only paths only> PR branch checkout: $SESSION_DIR/repo/
- <PR mode only> Prior comments + author justifications: $SESSION_DIR/prior-comments.json
- <if focus notes> Focus: <focus notes>

## Calibration precedence
Base rubric (binding) > CLAUDE.md (conventions) > core + layer (adder over CLAUDE.md)
> strict fallback when a needed field is absent in all of them.

## PR branch checkout (--post / --review-only PR paths only)
On the read-only PR paths the PR branch is checked out at $SESSION_DIR/repo/.
This is the ONLY source of truth for verifying code. Use Read, Grep, and Glob
against this directory, NOT the main repo working directory — it may be on a
different branch with stale or missing code. (On the auto-fix loop there is no
detached checkout: the PR branch IS the current working tree, so verify against
the working tree directly.)

## Diff-scope rule — CRITICAL
You are reviewing CHANGES MADE BY THIS PR/BRANCH. Do NOT flag pre-existing
issues. Only flag code in `+` or `-` lines of the diff. Context lines
(no prefix) and unchanged code in modified files are pre-existing — SKIP
them, even if they violate conventions. That's the #1 source of false
findings.

## Verification rules
- `file:line` citation required. No citation → drop your own finding
  before writing it out.
- Before flagging "missing X", grep the codebase (PR checkout, in PR mode)
  for X under different names. Don't flag a missing helper that exists
  under a slightly different name.
- For Important findings, check callers / reachability before asserting.
  If the only caller already guards the edge case, downgrade or drop.
- For docs/spec changes, spot-check factual claims (function signatures,
  error types, file paths) against actual source.

## Author-justification rule (PR mode only)
$SESSION_DIR/prior-comments.json contains prior review comments and their
threads. If a previous review flagged a finding and the author replied
with substantive explanatory text (not just "ok" or an emoji) explaining
why it's intentional, do NOT re-raise the same finding unless the
justification contains a technical error. Outdated comments (where
`position == null`) still count — the explanation may apply even if the
code anchor moved.

## Output
Write findings to $SESSION_DIR/round-<round>/findings-<agent>.json as a JSON
array per the base rubric's "Findings output format" section. Set `tradeoff:
true` only when a finding has multiple valid fix approaches (a judgment call);
omit it otherwise (see the base rubric's "Triage rubric"). Set `dimension` to
"<dimension>" on every entry. Severity caps from the base rubric apply (Nits at
most 5 reported per agent). If you have nothing to flag, write an empty array
(`[]`) — do not skip writing the file.
```

After dispatch, wait for all five agents to return. Each writes its findings file to `$SESSION_DIR/round-<round>/`. The orchestrator does not read agent transcripts — only the JSON files.

---

## Triage Subagent Prompt

```
You are triaging code-review findings for one round of an auto-fix loop.

## Input
- Findings to classify: $SESSION_DIR/round-<N>/compiled.json (use only the
  findings whose ids are in this list: <ids of effective findings>)
- Triage rubric: the base rubric's "Triage rubric (mechanical vs judgment)"
  section (absolute path: <absolute RUBRIC path>)
- Project profile: <PROFILE_PATH> (threat model, scope, focus hints)
- Project conventions: CLAUDE.md
- Code to inspect: the current working tree (read the cited files to judge
  whether a fix is mechanical or a judgment call)

## Your job
For EACH listed finding, emit TWO things — a fix-complexity classification AND an
orchestrator POV. Read the cited file before deciding; use what you read for both.

### 1. classification: "mechanical" or "judgment"
Apply the base rubric's "Triage rubric" — this is about the FIX, not whether to
fix. Mark "judgment" ONLY when applying the fix involves a real choice
(`finding.tradeoff === true`; a UX/design call with more than one reasonable
option; or a change to established product behavior the user may have an opinion
on). Everything else (one determinate, obviously-correct fix) → mechanical. Bias
hard toward mechanical.

### 2. recommendation (orchestrator POV) — EVERY finding
Per the base rubric's "Orchestrator POV", emit for every finding (this drives
whether the loop fixes it silently or stops to ask the user):
- recommendation: "Fix" | "Skip" | "Defer"
  - Fix = correct and worth the change here.
  - Skip = good reason not to (correct-but-not-worth-it for this project per the
    profile's threat model/scope, cost > benefit, or borderline/likely-false-
    positive on a closer read).
  - Defer = real but not now/not here (big-job, out of scope for this change).
- rationale: one sentence saying why.
- confidence: "High" | "Low" (Low = genuinely unsure; flags it for scrutiny).

## Output
Write $SESSION_DIR/round-<N>/triage.json — every listed finding id exactly once:
[ { "id": "<id>", "classification": "mechanical" | "judgment", "reason": "<one sentence>",
    "recommendation": "Fix" | "Skip" | "Defer", "rationale": "<one sentence>", "confidence": "High" | "Low" } ]
(All four POV-related fields are present on EVERY entry.)
```

---

## Fixer Subagent Prompt

**Fixer file-scope guard (`escalation-base.md` hard floor — runtime self-modification).** The guard runs
in the **fixer subagent** context, which does NOT inherit `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}` or `$REPO_ROOT`. So the
orchestrator embeds both absolute values into the fixer prompt's `## Input` block (the expanded `ESC_WRAPPER`
and `REPO_ROOT` resolved in setup), exactly as it embeds the absolute `RUBRIC`/`PROFILE` paths. Before the
fixer edits any file, it gates it with those embedded absolute values:
`python3 "<absolute ESC_WRAPPER path>" guard --root "<absolute REPO_ROOT>" --path "<file>"`.
If `allow` is false, the fixer MUST NOT edit that file (it is safety machinery — the authoritative
membership is the `SAFETY_MACHINERY` tuple in `escalation.py`); surface it as a finding for the owner instead. A `degraded:true`
result also refuses (fail-closed). The fixer never pushes/merges/deploys (those stay user-gated).

> **Enforcement boundary (review-flagged residual, design-consistent).** In F5 this guard is invoked
> by skill prose — a subagent *could* skip it, the same rationalize-past-prose risk `loop_state` was
> built to remove. F5 deliberately ships the deterministic guard *function* (tested, §8) + this
> wiring; the **non-bypassable** enforcement at the action boundary is the F3 producer's job (§4
> bound-2, §12). `REPO_ROOT` must be defined in setup and embedded wherever this guard is wired: an
> *empty* `--root` does **not** fail the guard open — `_band_roots("")` still returns `[_PLUGIN_ROOT]`
> and an empty `--root` still anchors against `[_PLUGIN_ROOT, resolved the-architect root]`; it only
> drops the **in-repo the-architect anchor**, and refuses (`allow:false, degraded:true`) only when
> `escalation.py` is itself unresolvable. Define `REPO_ROOT` to keep that anchor.

```
You are the fixer for one round of an auto-fix code-review loop.

## Input
- Findings to fix: $SESSION_DIR/round-<N>/fix-batch.json (array; each has
  id, severity, dimension, file, line, body, suggestion, and optional
  userGuidance)
- Conventions: CLAUDE.md and the project profile (<PROFILE_PATH>);
  severity/format from the base rubric (<absolute RUBRIC path>)
- Work in the current branch's working tree at <cwd>
- Repo root: <absolute REPO_ROOT>
- Escalation guard: <absolute ESC_WRAPPER path>
- Verify command: <VERIFY_CMD, or the literal "none" when the profile is mode: unverified>

## Your job
1. Apply a fix for EACH finding. Follow CLAUDE.md conventions and the profile's
   canonical patterns. When a finding has userGuidance, follow it over the
   original suggestion. BEFORE editing any file, gate it with the fixer
   file-scope guard, using the absolute "Escalation guard" and "Repo root"
   values from ## Input:
   `python3 "<absolute ESC_WRAPPER path>" guard --root "<absolute REPO_ROOT>" --path "<file>"`
   — if `allow` is false (or `degraded` is true), DO NOT edit that file (it is
   safety machinery); report it under "escalated" for the owner instead. Never
   push/merge/deploy (those stay user-gated).
2. Fix ONLY what the findings call for. No unrelated refactors (YAGNI).
3. If a verify command was provided, run it. If it fails, fix the failure and
   retry ONCE. If it still fails, STOP and report CHECK_FAILED with the failing
   output — never commit broken code. If the verify command is "none"
   (unverified profile), skip this check entirely.
4. Commit ALL changes in ONE commit (after the check passes, or immediately when
   unverified): `git commit -m "Auto-fix round <N>: <count> findings (<dimensions>)"`
5. Report back.

## Escalation
If a finding you were told to auto-fix actually requires a judgment call you
cannot make (multiple valid approaches, ambiguous intent), do NOT guess.
Report it under "escalated" with the id and why.

## Report format
- Status: DONE | CHECK_FAILED | ESCALATED
- fixed: [ids]
- escalated: [ { id, why } ]
- newIssuesNoticed: [brief notes on anything seen but not fixed]
- commit: <sha or "none">
- checkOutput: <tail of the verify command, only if CHECK_FAILED>
```

---

## Verification Rules (for subagents)

These are the base rubric's binding verification rules; they are restated in every subagent prompt and enforced again at compile time. See the base rubric's "Verification rules" and "In-pass verification & single-pass discipline" sections for the authoritative statement. Subagents that violate them produce findings that get dropped before the user ever sees them.

1. **`file:line` citation required.** No citation → finding is dropped at compile time, before presentation.
2. **Diff-scope rule.** Only `+` and `-` lines of `$SESSION_DIR/round-<N>/diff.txt` are in scope. Context lines (no prefix) and unchanged code in modified files are pre-existing — flagging them is the #1 source of false findings.
3. **Grep-before-flag.** Before flagging "missing X", search for X under variant names. In PR mode, grep `$SESSION_DIR/repo/`, not the main working tree.
4. **Reachability check on Important findings.** Read the caller(s) of the affected symbol. If the only caller already guards the edge case, downgrade or drop.
5. **Worktree-as-source-of-truth (PR mode).** All code verification reads go through `$SESSION_DIR/repo/`. The main working tree may be on a different branch with stale or missing code; using it for verification produces false findings against code that doesn't exist on the PR.
6. **Trust nothing from project docs without spot-checking.** Project docs (`CLAUDE.md`, the profile, `docs/*`) can be outdated. If a finding's rationale depends on a doc claim, verify against source code or flag uncertainty.
7. **Single-pass discipline.** Each specialist runs once per review. The orchestrator does not chain a verifier agent or re-run a specialist — published research on multi-turn agentic review shows F1 degrades and agents fabricate findings as real ones get exhausted.

---

## Common Mistakes

| Mistake                                                 | Fix                                                                                                                                                                |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Flagging pre-existing code as a PR issue**            | **The #1 mistake.** Diff-scope rule: only flag `+`/`-` lines. Context lines and unchanged code are out of scope even if they violate conventions.                  |
| Loading the full diff into main context                 | The orchestrator only ever runs `wc -l < $SESSION_DIR/round-<N>/diff.txt`. Subagents read the diff from disk; the orchestrator reads JSON findings.                |
| Finding based on assumed code state                     | Subagents must verify against `$SESSION_DIR/repo/` (PR mode) or the working tree (branch mode). No "I think this calls X" — open the file and confirm.             |
| Marking test issues as Critical                         | Critical is reserved for production bugs, data loss, security vulns. Test anti-patterns are Important at most — see the base rubric's "Severity tiers".            |
| Severity miscalibrated to deployment context            | Calibrate to the profile's threat model (strict / multi-user when the profile is absent). Don't raise threats the profile declares out of scope.                  |
| Posting without interactive approval                    | Every finding goes through `AskUserQuestion` (individually for Critical/Important, batched for Minor/Nit). Never auto-post anything from raw subagent output.      |
| Not using `resolve_diff_lines.py` before posting        | Always run the script before `gh api ... reviews`. It moves out-of-hunk comments to valid lines and drops comments for files not in the diff. Skipping it → 422.   |
| Not verifying the review was actually posted            | After `gh api ... reviews` returns success, fetch the last review and confirm `state` and `submitted_at`. Silent failures and duplicate posts have happened.       |
| Re-flagging issues the author already justified         | PR mode: check `prior-comments.json` for substantive author replies. If the explanation is sound, don't re-raise. Outdated comments still count.                   |
| Using diff.txt line numbers as file line numbers        | Diff line numbers and file line numbers are different. `resolve_diff_lines.py` parses `@@` hunk headers to map between them; trust the script.                     |
| Dropping resolved Important findings silently           | If the reachability check or author-justification filter drops an Important, mention it to the user — they may want to see what was filtered.                      |
| Skipping `--post` verification when GH returns success  | `gh api` can return 200 on a malformed body that GitHub silently treats as a no-op. Always run the post-submit verify call.                                        |
| Trying to delete a bad review via API                   | Submitted reviews cannot be deleted via the GitHub API. Never iterate by re-posting — fix `review-resolved.json` and retry only after the resolve script is clean. |
| Tiering or skipping specialists based on "what changed" | All five specialists always run. Coverage uniformity beats saving one agent dispatch — the agent returns `[]` if there's nothing to flag.                          |
| Using `gh pr diff` inside the loop                      | Rounds 2+ have local fix commits not on the remote. Always recompute `git diff <baseRef>...HEAD` locally each round.                                               |
| Auto-fixing a PR you don't have checked out             | Auto-fix needs the PR's branch as the current branch. If it isn't, stop and direct the user to `--post` or `--review-only`.                                        |
| Re-reviewing on a broken tree                           | If `VERIFY_CMD` fails after a fix, HALT. Never run the next review round on code that doesn't pass verification. (No gate when the profile is `mode: unverified`.) |
| Re-raising a finding the user skipped                   | Skipped identities go in the skip-set and are excluded from every later round's effective findings AND the circuit breaker.                                        |
| Eyeballing "are we stuck?" by hand                      | Always call `circuit_breaker.py`. Finding-identity comparison across rounds is deterministic; manual judgment drifts after compaction.                             |
| Exiting the loop early because a fix "looks done"       | The continue decision is `loop_state.py`'s, not yours (step 14). A blocking fix → another round is **mandatory**. "Trivial fix / it'll be clean / save the tokens / I'll offer it as optional" are the rationalizations it overrides — unverified fixes ship exactly this way. |
| Pushing automatically at loop end                       | The loop commits locally only. Pushing is always a separate, user-confirmed step.                                                                                 |
| Dispatching reviewers by reading an agent file          | The five reviewers are bundled plugin agents — dispatch the `<name>` reviewer with its methodology (resolve dispatch via the host tool map (`hosts/<host>-tools.md` at the plugin root)).                  |
| Skipping the profile bootstrap                           | If `.claude/review-profile.md` is absent, run review-init's create procedure inline first. Headless runs get a provisional strict profile.                         |

---

## --post API Commands

The exact commands for building the review payload, running the anchor validator, posting to GitHub, and verifying the post (referenced from `### --post` in `SKILL.md`).

**Build the review JSON** from approved findings:

```bash
cat > "$SESSION_DIR/round-1/review.json" <<EOF
{
  "commit_id": "<HEAD_SHA from meta.json>",
  "body": "<summary from compiled.json + verdict label>",
  "event": "<user's choice>",
  "comments": [
    {"path": "<file>", "line": <N>, "side": "RIGHT", "body": "<severity tag + finding body + suggestion>"}
  ]
}
EOF
```

> **External-engine secret hygiene (#38).** When the reviewer engine is Codex or Cursor, each
> finding's `body`/`suggestion` free-text is **already secret-scrubbed** at the adapter boundary
> (`engine_adapter.parse_result` runs `readout.scrub` before the finding enters the standard form),
> so this `--post` payload — which copies `body`/`suggestion` straight into the public PR comment via
> `gh api … /reviews` with no scrub of its own — carries no external secret in the clear. This is the
> one surface the native `readout.build_readout` handoff does not gate; the adapter pre-scrub covers it.

**Run `resolve_diff_lines.py`** to validate every comment anchor against the diff. This is non-optional — GitHub returns 422 "Line could not be resolved" for any inline comment whose `(file, line)` doesn't land on a `+` or context line inside a hunk; the script moves out-of-hunk comments to the nearest valid line (prefixing the body with `(Re: line N)`) and drops comments for files not in the diff:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 "$ROOT_DIR/lib/resolve_diff_lines.py" \
  "$SESSION_DIR/round-1/diff.txt" \
  "$SESSION_DIR/round-1/review.json" \
  --output "$SESSION_DIR/round-1/review-resolved.json"
```

**Post the review:**

```bash
gh api "repos/$REPO/pulls/$PR_NUMBER/reviews" \
  --input "$SESSION_DIR/round-1/review-resolved.json"
```

**Post-submit verification — non-optional.** Fetch the last review to confirm it actually landed (silent failures and accidental duplicates have happened):

```bash
gh api "repos/$REPO/pulls/$PR_NUMBER/reviews" \
  --jq '.[-1] | {id, state, submitted_at, html_url}'
```

If the post returns 422 despite running `resolve_diff_lines.py`, the script's stderr will have logged which comments were moved or dropped — re-check those, fix manually in `review-resolved.json`, and retry the `gh api ... reviews` call. Do **not** test line validity by posting real reviews iteratively; submitted reviews cannot be deleted via API.
