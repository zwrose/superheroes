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
Read `diff.txt` in bounded chunks (<=800 lines): use Read offset/limit when
available, or an equivalent bounded shell range. Never one whole-file read.
Continue with later offsets until the diff is covered.
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
- <if focus notes> Focus: <focus notes>  <!-- mechanical focus flags from focus_flags.py are appended here too (additions only) — see "Mechanical focus flags" below -->

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
why it's intentional, **raise the finding AND note the prior justification**
in the body — do NOT silently omit it. The **post-verification**
author-justification filter (after `verification.merge_and_rank`) owns the
drop decision: it may drop only a non-CONFIRMED finding (quoting the
justification); a CONFIRMED finding survives stamped
`challenge: "author-justified"`. Outdated comments (where
`position == null`) still count.

## Output
Write findings to $SESSION_DIR/round-<round>/findings-<agent>.json as a JSON
array per the base rubric's "Findings output format" section. Set `tradeoff:
true` only when a finding has multiple valid fix approaches (a judgment call);
omit it otherwise (see the base rubric's "Triage rubric"). Set `dimension` to
"<dimension>" on every entry. Severity caps from the base rubric apply (Nits at
most 5 reported per agent). If you have nothing to flag, write an empty array
(`[]`) — do not skip writing the file.
```

## Mechanical focus flags

Before dispatching the round's specialists, the orchestrator runs the deterministic
mechanical-focus-flag detector over the round diff (design authority: ratified #474,
position 15 — grep-detected **additive** brief flags; **additions only, never
classifier-driven lens removal**):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 "$ROOT_DIR/lib/focus_flags.py" "$SESSION_DIR/round-<round>/diff.txt"
```

It prints zero or more flag lines (a changed migration file → rollback/data-safety
emphasis; a changed dependency lockfile → supply-chain check). **Append** each emitted
line into every specialist's `Focus:` context block, alongside any `--focus` notes — an
addition that never replaces the `--focus` notes and never removes or down-scopes a lens
(that classifier-driven lens-removal is banned by #474). If nothing is emitted, append
nothing. The detector is grep-grounded and has no authority: it can only add emphasis,
never drop a finding or a lens.

> **External-engine reviewers — stdout shape contract (#38, #196).** When `$REVIEWER_ENGINE` is
> `codex` or `cursor`, a specialist is dispatched through `engine_adapter.py` (read-only sandbox)
> instead of a named subagent, and it returns its findings on **stdout** rather than writing the
> findings file. Its final stdout MUST be a single JSON object `{"findings": [...]}` (the same array
> the subagent would have written, wrapped once as the `findings` value) with **nothing printed after
> it** — `engine_adapter.parse_result(role="review")` reads the last top-level JSON value. Emit the
> canonical object; the parser also **tolerates a bare top-level array** `[...]` of finding objects as
> of #196, but anything else (prose, a trailing line, an empty stream, an array of non-objects) parses
> as `unreadable`, which forfeits the slot to a Claude re-run (UFR-7) and silently doubles the round's
> cost. State this shape verbatim in the dispatch prompt so orchestrators stop re-guessing it per run.

> **Reviewer-seat dispatch runs through the dispatch RUNNER (#563 DoD 2/4) — reviewer role ONLY.**
> When `$REVIEWER_ENGINE` is `codex` or `cursor`, dispatch each read-only reviewer seat through
> `lib/engine_dispatch.py dispatch-review` (not a hand-rolled `codex exec` / `cursor-agent` shell
> line). The runner owns the previously per-session dispatch mechanics as **machinery**: it prepends
> the anti-hijack preamble (the mode-7 hardening that stops the codex SessionStart/skill-selection
> derail), feeds the prompt via the `- < realfile` stdin form behind the `_prompt_path_ok`
> empty-prompt guard, runs codex from a non-repo cwd with `--skip-git-repo-check`, bounds the attempt
> and streams liveness heartbeats to `--progress-file`, and on a **terminal forfeit** (timeout OR
> `unreadable` — never intermediate bootstrap noise that still yields a final answer) auto-retries
> ONCE tight-inline with a ≥900 s ceiling before returning
> `{"ok": false, "forfeited": true, "disclosure": …}`. A forfeit → the seat falls open to a Claude
> re-run (UFR-7) and the orchestrator **discloses** the degraded vendor mix (the `disclosure` string);
> making that fall-open loud by machinery in the receipt is #563 PR C.
>
> ```bash
> ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
> python3 "$ROOT_DIR/lib/engine_dispatch.py" dispatch-review \
>   --engine "$REVIEWER_ENGINE" --engine-model "$SEAT_ENGINE_MODEL" --effort "$SEAT_EFFORT" \
>   --prompt-path "$SEAT_PROMPT" --progress-file "$SEAT_PROGRESS" --timeout 900 --retry-timeout 900
> ```
>
> Read-only sandbox is **hard-coded inside the runner API** — it cannot emit a write dispatch. Because
> the runner runs codex from a non-repo cwd under "do not read files", the seat prompt MUST be
> **self-contained** — inline the diff and any context the lens needs. This makes the codex/cursor
> seat a **diff-scoped cross-vendor lens**; lenses that need repo inspection (grep-before-flag, caller
> reachability) stay with the Claude seats, which keep full working-tree access. The **fixer / write
> path is unchanged** — it stays model-driven and host-gated (a Python-spawned subprocess would bypass
> the host permission-classifier the write authz depends on; CONVENTIONS `§7.5`).

> **External-engine dispatches — timeout is structural, an expired slot is `unreadable` (#202, #204).**
> Every engine dispatch — the reviewer (read-only, above) AND the **fixer** (cursor, workspace-write) —
> runs as a Bash tool call, so its timeout is already **structural, not prompted**: the plugin's
> `PreToolUse(Bash)` floor (`hooks/bash_timeout.py`, #204) injects a 600s `timeout` on any dispatch
> that carries none, so a wedged engine CLI is bounded and killed instead of blocking the panel's
> `wait` forever (a hang is **not** fail-open — CONVENTIONS `§7.5`). You do **not** compose a
> per-dispatch watchdog. What this file owns is the **expiry contract**: treat a killed/timed-out
> dispatch as an **expired slot** — its stdout is absent or partial, so `engine_adapter.parse_result`
> returns `unreadable`. A timed-out **reviewer** then takes the existing UFR-7 re-run-on-Claude path;
> a timed-out **fixer** commits no external write and the fix falls open to Claude. A hang becomes a
> bounded cost, never a stuck loop.
>
> **Hand-rolled engine dispatch — stdin form, empty-prompt guard, portable timeout (#563).** When a
> builder hand-rolls an engine CLI dispatch (exactly when the adapter path fails), three verified
> rules keep it from wedging:
> 1. **Always feed the prompt from a real file over redirected stdin — `codex exec … - < promptfile`
>    — never an inherited/open stdin.** codex `exec` reads its prompt from stdin when given `-`, no
>    positional prompt, or even an empty-string positional; if that stdin is an open source that
>    never delivers data or EOF (the inherited stdin of a headless dispatch with no `< file`
>    redirect), codex **hangs forever**. An EOF-closed empty stdin (`< /dev/null`) does not hang — it
>    errors fast. Repro'd 2026-07-23 against codex 0.144.1.
> 2. **Reject an empty/missing prompt before dispatch.** `engine_adapter.py build-argv --prompt-path
>    PATH` fails closed (emitting `{"ok":false,"reason":"empty-prompt",…}` instead of argv) unless
>    PATH is a readable regular file with non-whitespace content. The caller MUST redirect **that same
>    validated file** into the engine's stdin — validating one file and redirecting another (or none)
>    reopens the hang. (The reviewer-scoped dispatch runner of the follow-up work couples validate +
>    redirect in one step, closing the check/use window; a hand-rolled dispatch must couple them by
>    hand.)
> 3. **Bound the run with a portable timeout — macOS has no `timeout(1)`.** Use a perl fork+kill
>    wrapper and a HIGH ceiling (≥900 s for a real engine run; never a borderline limit), redirecting
>    engine output to a **file** (never `| tail`, which buffers a stall to look identical to progress):
>    ```bash
>    perl -e 'my $t=shift; my $to=0; my $p=fork; die unless defined $p; if(!$p){exec @ARGV or die $!}
>      local $SIG{ALRM}=sub{$to=1; kill "KILL",$p}; alarm $t; waitpid $p,0; my $s=$?; alarm 0;
>      exit 124 if $to; exit($s>>8) if ($s&127)==0; exit(128+($s&127))' \
>      900 codex exec … - < promptfile > out.json 2> err.log
>    ```
>    (exit 124 = timed out.) Watch the process's **CPU-time column, not elapsed** — an engine CLI can
>    sit at ~0% CPU for minutes and still be live.
>
> **Dispatch-runner scope boundary (#563).** A follow-up productizes an adapter-owned dispatch runner
> for the **read-only reviewer role only** (auto-retry + liveness as machinery, not builder
> discipline). The **fix/write path stays model-driven and host-gated**: its authorization depends on
> the host permission-classifier gating the literal Bash `codex exec`/`cursor-agent` call, and a
> Python-spawned subprocess would bypass that classification (CONVENTIONS `§7.5` — a completed
> external result fails closed; engine *selection* fails open). Do not fold the write path into a
> Python runner without a fresh authz design.

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

These are the base rubric's binding verification rules; they are restated in every subagent prompt and enforced again at compile time. See the base rubric's "Verification rules" and "In-pass Chain-of-Verification & single-pass discipline" sections for the authoritative statement. Subagents that violate them produce findings that get dropped before the user ever sees them.

1. **`file:line` citation required.** No citation → finding is dropped at compile time, before presentation.
2. **Diff-scope rule.** Only `+` and `-` lines of `$SESSION_DIR/round-<N>/diff.txt` are in scope. Context lines (no prefix) and unchanged code in modified files are pre-existing — flagging them is the #1 source of false findings.
3. **Grep-before-flag.** Before flagging "missing X", search for X under variant names. In PR mode, grep `$SESSION_DIR/repo/`, not the main working tree.
4. **Reachability check on Important findings.** Read the caller(s) of the affected symbol. If the only caller already guards the edge case, downgrade or drop.
5. **Worktree-as-source-of-truth (PR mode).** All code verification reads go through `$SESSION_DIR/repo/`. The main working tree may be on a different branch with stale or missing code; using it for verification produces false findings against code that doesn't exist on the PR.
6. **Trust nothing from project docs without spot-checking.** Project docs (`CLAUDE.md`, the profile, `docs/*`) can be outdated. If a finding's rationale depends on a doc claim, verify against source code or flag uncertainty.
7. **Single-pass discipline.** Each specialist runs once per review and does not propose or chain a follow-up **finder** pass over its own output — a finder that has exhausted the real issues starts fabricating. This bans re-*finding*, not the orchestrator's separate keep/drop **synthesis** pass over the already-emitted findings (a verify stage that never searches for new issues).
8. **Sanctioned probe shape (unattended runs).** To verify by *running* code, write a throwaway test file inside the build worktree and run it with the project test-run family (e.g. `pytest` / the repo test command); do not improvise inline interpreter one-liners (`python3 -c` / `node -e`). Only the sanctioned shapes are on the enforcer's auto-allow path — an inline probe stalls on a permission prompt when the owner is absent. If any action awaits owner permission unanswered for 15 minutes, proceed without it and report the denied action honestly (never as done). This restates the `PROBE_STEERING` / `TIMEOUT_PROCEED_CONTRACT` blocks the dispatched reviewer prompt embeds, so the human-facing doc and the live prompt agree.

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
| Re-flagging issues the author already justified         | PR mode: raise the finding and note the prior justification; the post-verification filter drops only non-CONFIRMED findings (see `round-driver.md`). |
| Using diff.txt line numbers as file line numbers        | Diff line numbers and file line numbers are different. `resolve_diff_lines.py` parses `@@` hunk headers to map between them; trust the script.                     |
| Dropping resolved Important findings silently           | If reachability or the post-verification author-justification filter drops an Important, mention it — the justification is quoted in the record.                      |
| Skipping `--post` verification when GH returns success  | `gh api` can return 200 on a malformed body that GitHub silently treats as a no-op. Always run the post-submit verify call.                                        |
| Trying to delete a bad review via API                   | Submitted reviews cannot be deleted via the GitHub API. Never iterate by re-posting — fix `review-resolved.json` and retry only after the resolve script is clean. |
| Tiering or skipping specialists based on "what changed" | Round 1 is always the full panel; later rounds follow `round_driver.py` `next` (delta audits + scoped finder, or a full panel on #174/unknown). Never skip by eye. |
| Using `gh pr diff` inside the loop                      | Rounds 2+ have local fix commits not on the remote. Always recompute `git diff <baseRef>...HEAD` locally each round.                                               |
| Auto-fixing a PR you don't have checked out             | Auto-fix needs the PR's branch as the current branch. If it isn't, stop and direct the user to `--post` or `--review-only`.                                        |
| Re-reviewing on a broken tree                           | If `VERIFY_CMD` fails after a fix, HALT. Never run the next review round on code that doesn't pass verification. (No gate when the profile is `mode: unverified`.) |
| Re-raising a finding the user skipped                   | Skipped identities go in the skip-set and are excluded from every later round's effective findings AND the circuit breaker.                                        |
| Eyeballing "are we stuck?" by hand                      | The audit-keyed stall breaker lives in `round_driver.py` — never call `circuit_breaker.py` inside the auto-fix loop.                                                 |
| Exiting the loop early because a fix "looks done"       | Obey `round_driver.py` `next`/`submit` — never `code_loop_plan` or manual continuation. "Trivial fix / save tokens / offer optional round" are the rationalizations it overrides. |
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
