---
name: review-code
description: Use when reviewing code changes on a local branch or an open pull request before merging — including when you want the review's findings auto-fixed locally or posted to GitHub.
user-invocable: true
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# Review Code

Run a multi-dimensional code review on either an open pull request or a local branch (vs the default branch), then **autonomously fix what it finds**. The main context is an **orchestrator** — it fetches metadata, dispatches five specialist agents in parallel, compiles their findings, triages each into auto-fixable vs needs-your-judgment, applies fixes via a fixer subagent, and re-reviews — looping until no Critical/Important findings remain or a circuit breaker halts. It never loads the full diff or any agent's raw output into its own conversation; subagents do all heavy reading and write structured results to disk.

The skill auto-detects whether you're reviewing a PR or a local branch, always dispatches the full set of specialists (architecture, code, security, test, premortem) so coverage is uniform across reviews, enforces the severity and verification rules in the base rubric at compile time (not just by hope), and — by default — drives an auto-fix loop that commits fixes locally (never pushes). Two read-only behaviors are preserved as flags.

There are three top-level paths, chosen at invocation:

- **`--post`** → one review pass, then read-only GitHub posting (push approved findings to GitHub through `resolve_diff_lines.py` so out-of-hunk anchors never trigger 422 errors). Never touches the working tree.
- **`--review-only`** → one review pass, then a read-only interactive terminal presentation. No commits.
- **otherwise (default)** → the auto-fix loop: review → triage → fix → re-review, committing locally until clean or halted.

The five specialist agents are bundled plugin agents (`architecture-reviewer`, `code-reviewer`, `security-reviewer`, `test-reviewer`, `premortem-reviewer`); the orchestrator dispatches each reviewer by name (resolve dispatch via the host tool map). Each agent's review methodology lives in its own system prompt; the orchestrator's dispatch passes it the base rubric (severity/verification/format), the project calibration (`core.md` for threat model + canonical patterns, `review-crew.md` layer for scope/focus/conventions), `CLAUDE.md`, the diff, and the findings output path. Every finding they emit must cite a `file:line` and target a `+`/`-` line in the diff — context-line and unchanged-code findings are dropped at compile time. Each specialist runs once per round; the orchestrator never re-runs a specialist or chains a second **finder** pass within a round, because a finder that has exhausted the real issues starts fabricating (base rubric, "In-pass Chain-of-Verification & single-pass discipline"). It does run a fail-closed **per-finding verification** pass over the *already-emitted* findings at compile time — 3-state CONFIRMED/PLAUSIBLE/REFUTED verdicts with quoted evidence that never searches for new issues, distinct from re-running a finder (see `## Compile + Dedupe`). The loop re-reviews from scratch each round on a fresh diff, which is different from re-running a specialist on its own output.

## Invocation

| Form                                       | Behavior                                                                                                                                                              |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/superheroes:review-code`                 | **Auto-fix loop (default).** Review → triage → fix → re-review until no Critical/Important findings remain, or a halt condition fires. Commits locally; never pushes. |
| `/superheroes:review-code --review-only`   | One review pass, interactive tiered presentation, no commits.                                                                                                         |
| `/superheroes:review-code pr <N> --post`   | One review pass, read-only, post inline findings to GitHub. Never touches the tree.                                                                                   |
| `/superheroes:review-code branch` / `pr <N>` | Force branch or PR mode; still runs the auto-fix loop unless combined with `--review-only`/`--post`.                                                                |
| `/superheroes:review-code --focus <notes>` | Pass focus notes to every specialist. Combinable with any form.                                                                                                       |
| `/superheroes:review-code --result-file <path>` | Write the terminal decision (`action`, `round`, `reason`) to `<path>` as JSON on **every** terminal exit (step-5 clean, step-10 all-skipped, step-11/12 HALT, step-14 gate), for a programmatic caller (e.g. Workhorse step 2). Combinable with any form; absent → no file written (backward-compatible). |

The three top-level paths: `--post` → read-only GitHub posting; `--review-only` → read-only terminal presentation; otherwise → auto-fix loop.

**Auto-detection rule.** Run `gh pr list --head "$(git rev-parse --abbrev-ref HEAD)" --json number,headRefOid,headRefName --limit 1`. If the result is non-empty, default to PR mode. Otherwise default to branch mode. If the user passed `branch` explicitly, skip the lookup. If the user passed `pr <N>` explicitly, use `<N>` and don't auto-detect.

**`--post` only applies to PR mode.** If the user passes `--post` without a PR (and auto-detection finds none), stop and tell them — branch mode has nothing to post against.

## Session Directory

All review artifacts live in a per-invocation temp directory so parallel reviews don't collide:

```bash
SESSION_DIR=$(mktemp -d /tmp/review-XXXXXXXX)
```

Files written during the review. **Per-round artifacts live under `$SESSION_DIR/round-<N>/`** in the auto-fix loop (round 1, 2, …); the read-only paths (`--review-only`, `--post`) run a single pass and write that pass's artifacts under `round-1/` as well. Only `meta.json` lives at the session-dir root.

| Path                                                | Written by     | Purpose                                                                                     |
| --------------------------------------------------- | -------------- | ------------------------------------------------------------------------------------------- |
| `$SESSION_DIR/meta.json`                            | orchestrator   | Mode, PR number (if any), repo, branch, head SHA, base ref, verify story, focus notes       |
| `$SESSION_DIR/repo/`                                | orchestrator   | `--post`/`--review-only` PR paths only: detached `git worktree` at the PR head SHA          |
| `$SESSION_DIR/prior-comments.json`                  | orchestrator   | PR-mode only: prior review comments + threads (for author justifications)                   |
| `$SESSION_DIR/round-<N>/diff.txt`                   | orchestrator   | Round `<N>` unified diff (`git diff <baseRef>...HEAD`). **Never read by the main context.** |
| `$SESSION_DIR/round-<N>/findings-architecture.json` | arch agent     | Architecture-reviewer findings array                                                        |
| `$SESSION_DIR/round-<N>/findings-code.json`         | code agent     | Code-reviewer findings array                                                                |
| `$SESSION_DIR/round-<N>/findings-security.json`     | sec agent      | Security-reviewer findings array                                                            |
| `$SESSION_DIR/round-<N>/findings-test.json`         | test agent     | Test-reviewer findings array                                                                |
| `$SESSION_DIR/round-<N>/findings-premortem.json`    | premortem agent | Premortem-reviewer (Failure-Mode) findings array                                            |
| `$SESSION_DIR/round-<N>/compiled.json`              | orchestrator   | Deduplicated, verified findings + summary + verdict (read by `circuit_breaker.py`)          |
| `$SESSION_DIR/round-<N>/triage.json`                | triage agent   | Per-finding `mechanical`/`judgment` classification + POV for every finding (loop only)      |
| `$SESSION_DIR/round-<N>/resolutions.json`           | orchestrator   | User decisions on `present-set` findings (loop only; read by `circuit_breaker.py`)          |
| `$SESSION_DIR/round-<N>/fix-batch.json`             | orchestrator   | Findings handed to the fixer this round (loop only)                                         |
| `$SESSION_DIR/round-<N>/review.json`                | orchestrator   | `--post` only: review body + approved comments (pre-resolve)                                |
| `$SESSION_DIR/round-<N>/review-resolved.json`       | resolve script | `--post` only: comments after line-anchor resolution                                        |

**CRITICAL:** The main context only ever runs `wc -l < $SESSION_DIR/round-<N>/diff.txt` to size the diff. It never `cat`s the diff, never reads the full thing, never echoes it back. Subagents read the diff from disk and write structured findings; the orchestrator reads the findings JSON, not the diff.

## Workflow

### 1. Setup

Decide mode (auto-detected or explicit, per `## Invocation`). Create the session directory.

**Resolve the base rubric path once.** The base rubric is bundled at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/rubric/review-base.md`. Capture the rubric path so it can be embedded — **expanded to an absolute path** — into subagent prompts (subagents may not inherit `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}`):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
RUBRIC="$ROOT_DIR/rubric/review-base.md"   # absolute; embed the expanded value in subagent prompts
```

**Resolve the escalation guard wrapper and repo root once.** Subagents do not inherit `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}` or `$REPO_ROOT`, so compute both absolute values here (in the orchestrator's context, where they expand) for embedding into the fixer prompt's `## Input` block — the same way `RUBRIC`/`PROFILE` are embedded as expanded absolute paths:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
ESC_WRAPPER="$ROOT_DIR/lib/escalation_resolve.py"   # absolute; embed the expanded value in the fixer prompt
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)  # absolute; the canonical safe-capture pattern, anchors the in-repo (dogfood) safety files
```

**Resolve calibration paths.** `calibration_resolve.py` returns `$CORE`, `$LAYER`, `$PROFILE`, `$LOCATION`, `$EXISTS`, `$DECISIONS`:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
CAL=$(python3 "$ROOT_DIR/lib/calibration_resolve.py" resolve) \
  || CAL='{"location":"none","exists":false}'
CORE=$(printf '%s' "$CAL" | jq -r '.dispatch_core // empty')
LAYER=$(printf '%s' "$CAL" | jq -r '.dispatch_layer // empty')
PROFILE="${LAYER:-$(printf '%s' "$CAL" | jq -r '.legacy_path // empty')}"
LOCATION=$(printf '%s' "$CAL" | jq -r .location)
EXISTS=$(printf '%s' "$CAL" | jq -r .exists)
DRES=$(python3 "$ROOT_DIR/lib/review_store.py" resolve --kind decisions) \
  || DRES='{"path":null}'
DECISIONS=$(printf '%s' "$DRES" | jq -r '.path // empty')
# FR-7/8: surface the single coalesced storage-mode reconcile nudge (non-blocking, ack-gated).
NUDGE_MSG=$(python3 "$ROOT_DIR/lib/mode_reconcile.py" signals 2>/dev/null | jq -r 'if . == null then empty else .message end' 2>/dev/null)
[ -n "$NUDGE_MSG" ] && echo "⚠ storage-mode: $NUDGE_MSG"
```

Also resolve the engine versions the staleness self-check (next) needs — the **plugin version** from `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/.claude-plugin/plugin.json` (`version`) and the **rubric-version** from the first line of `$RUBRIC` (`<!-- rubric-version: N -->`):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
PLUGIN_VERSION=$(python3 -c "import json;print(json.load(open('$ROOT_DIR/.claude-plugin/plugin.json'))['version'])")
RUBRIC_VERSION=$(sed -n 's/.*rubric-version: *\([0-9][0-9]*\).*/\1/p' "$RUBRIC" | head -1)
```

**Resolve model tiers.** Specialists at `reviewer` (`reviewer-deep` for security/architecture); triage + fixer at `mechanical`:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
MT="$ROOT_DIR/lib/model_tier_resolve.py"   # resolved like $RUBRIC
OV=$(python3 "$ROOT_DIR/lib/model_tier_overrides.py" --profile "$PROFILE")  # {role:model} or {}
REVIEWER_MODEL=$(python3 "$MT" --role reviewer --overrides "$OV" | jq -r '.model // empty')
DEEP_MODEL=$(python3 "$MT" --role reviewer-deep --overrides "$OV" | jq -r '.model // empty')
MECH_MODEL=$(python3 "$MT" --role mechanical --overrides "$OV" | jq -r '.model // empty')
SYNTH_MODEL=$(python3 "$MT" --role synthesis --overrides "$OV" | jq -r '.model // empty')  # fail-closed synthesis judge
VERIFIER_MODEL=$(python3 "$MT" --role verifier --overrides "$OV" | jq -r '.model // empty')  # per-finding verification tier
```

**Resolve per-role engine (FR-15).** Default `claude` when unset.

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
EP=$(python3 "$ROOT_DIR/lib/engine_pref_load.py")            # {"reviewer","implementation"} (both "claude" if unset)
REVIEWER_ENGINE=$(echo "$EP" | jq -r '.reviewer // "claude"')
IMPL_ENGINE=$(echo "$EP" | jq -r '.implementation // "claude"')
```

When dispatching specialists, map each `dims_to_run` entry's **tier** to a model — `reviewer-deep` → `model: $DEEP_MODEL`, `reviewer` → `model: $REVIEWER_MODEL` (the per-round schedule is script-owned; see the round scheduler). Triage and fixer subagents use `model: $MECH_MODEL`. An empty value means "inherit the session model" — omit the `model` arg in that case.

**Staleness self-check (first action).** Before the profile bootstrap and before dispatching anything, run the deterministic staleness/degraded self-check. It soft-fails (always exit 0) and **must never block the review** on drift — it only produces a non-blocking nudge surfaced at end of run. The root depends on the path: `--post` reads the PR-head worktree (`--root "$SESSION_DIR/repo"`), while branch/default paths read the working tree (default root, `.`). Run it only when a profile already resolved (`$EXISTS` is `true`) — a MISSING profile (`$LOCATION` is `none`) routes to the profile bootstrap below (which runs review-init/bootstrap), not to staleness:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
if [ "$EXISTS" = "true" ]; then
  # --post path: --root "$SESSION_DIR/repo" (PR-head worktree). branch/default: omit --root (working tree).
  DOCTOR_JSON=$(python3 "$ROOT_DIR/lib/repo_doctor.py" \
    "$PROFILE" "$PLUGIN_VERSION" "$RUBRIC_VERSION" ${DOCTOR_ROOT_ARG})
fi
```

(`DOCTOR_ROOT_ARG` is `--root "$SESSION_DIR/repo"` on `--post` once the worktree exists; empty otherwise.) Capture `DOCTOR_JSON`; on `readable: false`, tell the user to re-run `/superheroes:configure` and continue. Retain `message`, `signal_hash`, `nudge_acked` for the end-of-run staleness nudge. Do NOT act on `drift` here.

**Profile bootstrap (run before dispatching anything).** The review engine reads its per-project calibration (threat model, verify command, scope, focus hints, canonical patterns) from the resolved profile. If nothing resolved (`$LOCATION` is `none`), decide where to store it, create it, then write it:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
if [ "$LOCATION" = "none" ]; then
  # Decide location: env override > ask (interactive) > global (headless).
  INTERACTIVE=true   # the orchestrator sets this to false on a headless/non-interactive run (no human to answer), so decide-location returns "global" deterministically instead of "ask"
  LOC=$(python3 "$ROOT_DIR/lib/review_store.py" decide-location --interactive "$INTERACTIVE")
  # If LOC is "ask" → AskUserQuestion, set LOC to owner's pick, then record band-wide (FR-3).
  # If LOC is already in-repo/global → skip record, go straight to create.
  REC=$(python3 "$ROOT_DIR/lib/mode_reconcile.py" reconcile --mode "$LOC" 2>/dev/null) || REC=""
  if [ -z "$REC" ] || printf '%s' "$REC" | jq -e '.written == false' >/dev/null 2>&1; then
    echo "note: couldn't record the band storage mode this run — you'll be asked again next time."
  fi
  PROFILE=$(python3 "$ROOT_DIR/lib/review_store.py" create --kind profile --location "$LOC")
  DECISIONS=$(python3 "$ROOT_DIR/lib/review_store.py" create --kind decisions --location "$LOC")
fi
```

When `decide-location` returns `ask`, present the in-repo-vs-global `AskUserQuestion` and use the answer as `$LOC`. When `$LOCATION` was `none`, run review-init inline (`plugins/superheroes/skills/review-init/SKILL.md`, Steps 1–4) before the re-resolve above. Headless runs get a provisional profile from detected defaults.

**Read the verify story from core calibration** via `review_code_config.py` (uses `$CORE`'s `verifyCommand`, else legacy `$PROFILE`'s `## Verify`). Sets `VERIFY_CMD` for the verify gate and fixer:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
VERIFY_JSON=$(python3 "$ROOT_DIR/lib/review_code_config.py" 2>/dev/null) || VERIFY_JSON='{}'
VERIFY_CMD=$(printf '%s' "$VERIFY_JSON" | jq -r '.verifyCommand // empty')
VERIFY_MODE=$(printf '%s' "$VERIFY_JSON" | jq -r '.verifyMode // empty')
[ "$VERIFY_CMD" = "none" ] && VERIFY_CMD=""
```

When `VERIFY_MODE` is `unverified`, skip the verify gate. When `VERIFY_MODE` is `review-only`, degrade to one pass + presentation.

**Refresh dispatch paths before specialists.** Re-run the `calibration_resolve.py` jq block above once after bootstrap.

**PR mode:**

```bash
# Resolve PR number — either provided or auto-detected from current branch
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ -z "$PR_NUMBER" ]; then
  PR_NUMBER=$(gh pr list --head "$BRANCH" --json number --jq '.[0].number')
fi

# Metadata: small JSON only — do NOT load the diff yet
gh pr view "$PR_NUMBER" --json number,title,author,headRefName,headRefOid,baseRefName,url > "$SESSION_DIR/pr.json"
HEAD_SHA=$(jq -r .headRefOid "$SESSION_DIR/pr.json")
PR_BRANCH=$(jq -r .headRefName "$SESSION_DIR/pr.json")
BASE_REF=$(jq -r .baseRefName "$SESSION_DIR/pr.json")   # PR base branch — used as the diff base
REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner)

# Prior review comments — used for author-justification handling
gh api "repos/$REPO/pulls/$PR_NUMBER/comments" \
  --jq '[.[] | {id, in_reply_to_id, path, line, position, body, user: .user.login}]' \
  > "$SESSION_DIR/prior-comments.json"

# Read-only paths ONLY (--post / --review-only): a detached worktree at the PR head
# gives subagents a clean source of truth to verify against. NOT used on the
# auto-fix path — that path edits and commits on the current branch directly.
git fetch origin "$PR_BRANCH"
git worktree add --detach "$SESSION_DIR/repo" "$HEAD_SHA"   # --post / --review-only ONLY
```

**Auto-fix branch guard (PR mode, default loop only).** Before entering the loop, the orchestrator must be standing on the PR's own branch so fix commits land where they belong:

```bash
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "$PR_BRANCH" ]; then
  echo "Auto-fix needs PR branch '$PR_BRANCH' checked out (currently on '$CURRENT_BRANCH')."
  echo "Check out the branch, or re-run with --post (read-only GitHub) or --review-only (read-only terminal)."
  exit 1
fi
```

If the guard fails (detached HEAD, or you're reviewing someone else's PR), STOP — do not create the detached worktree and do not enter the loop. Tell the user to use `--post` or `--review-only`. The detached `git worktree add --detach` step above is for the `--post`/`--review-only` PR paths ONLY, never for the auto-fix path.

**Branch mode:**

```bash
BRANCH=$(git rev-parse --abbrev-ref HEAD)
HEAD_SHA=$(git rev-parse HEAD)
BASE_REF=$(git symbolic-ref --quiet refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo main)   # branch mode diffs against the default branch
REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || echo "local")

# No worktree, no prior comments — subagents verify against the current working tree
```

**Per-round diff is ALWAYS local.** Do NOT use `gh pr diff` to fetch the diff. Each round computes the diff locally from `<baseRef>` (PR mode: the PR's `baseRefName`; branch mode: the default branch), because rounds 2+ have local fix commits that are not on the remote — `gh pr diff` would miss them. The per-round command (run inside the loop, see `## Auto-Fix Loop`) is:

```bash
git diff "$BASE_REF"...HEAD > "$SESSION_DIR/round-<round>/diff.txt"
```

The read-only paths run a single pass and compute the same local diff into `round-1/diff.txt`.

Then write `meta.json` in both modes:

```bash
cat > "$SESSION_DIR/meta.json" <<EOF
{
  "mode": "${MODE}",
  "path": "${REVIEW_PATH}",
  "pr": ${PR_NUMBER:-null},
  "repo": "${REPO}",
  "branch": "${BRANCH}",
  "headSha": "${HEAD_SHA}",
  "baseRef": "${BASE_REF}",
  "sessionDir": "${SESSION_DIR}",
  "verify": "${VERIFY_CMD:-unverified}",
  "focusNotes": ${FOCUS_JSON:-null}
}
EOF
```

`REVIEW_PATH` is `loop` (default), `review-only`, or `post`, decided from the flags at invocation. It is written to `meta.json` so a cold-resumed orchestrator (after compaction) knows which top-level flow to continue. The `verify` field records the verify command string, or `"unverified"` / `"review-only"`, so a cold-resumed orchestrator recovers the verify story.

Size the round-1 diff for the dispatch summary (after writing it to `round-1/diff.txt` per the command above):

```bash
DIFF_LINES=$(wc -l < "$SESSION_DIR/round-1/diff.txt")
```

**CRITICAL:** Do not `cat`, `head`, `tail`, or otherwise read any `diff.txt` from the main context. The line count is the only thing the orchestrator needs to know about its contents.

### 2. Dispatch Summary

Print this dispatch summary as a plain status message, then dispatch the specialists immediately (no approval gate):

- **Skill:** `review-code`
- **Mode:** PR or branch
- **Target:** `PR #<N> "<title>"` (PR mode) or `<branch> vs <baseRef>` (branch mode)
- **Repo:** `<owner>/<repo>`
- **Head SHA:** short hash
- **Diff size:** `<DIFF_LINES>` lines
- **Verify:** `VERIFY_CMD` (the command string), or `unverified` (no gate), or `review-only` (auto-fix disabled — this run degrades to a single pass + presentation)
- **Specialists to dispatch (round 1: all five at `reviewer-deep`, in parallel; later rounds: the scheduler's `dims_to_run`):**
  - `architecture-reviewer` → `findings-architecture.json`
  - `code-reviewer` → `findings-code.json`
  - `security-reviewer` → `findings-security.json`
  - `test-reviewer` → `findings-test.json`
  - `premortem-reviewer` → `findings-premortem.json`
- **Session directory:** `$SESSION_DIR` (round 1 artifacts under `round-1/`)
- **Focus notes:** the `--focus` argument, if any
- **Path:** default → auto-fix loop (compile + dedupe → triage → fix → re-review, committing locally); `--review-only` → one pass + interactive presentation; `--post` → one pass + post to GitHub
- **What happens after dispatch (default loop):** compile + dedupe → triage → user interventions on judgment calls → fixer subagent commits → verify gate (`VERIFY_CMD`, unless `unverified`) → circuit-breaker → re-review or exit. The auto-fix runs on `$IMPL_ENGINE` (FR-15): when it is `codex`/`cursor`, the fix is written by the external engine via `engine_adapter.py` (workspace-write) and committed by the adapter, then the same verify gate runs; when it is `claude`, the fixer subagent runs as today. This standalone path has no run-time `engine_authz.py test-dispatch` preflight (that lives only in the native build leg's `_implWriteAuthorized`); instead it relies on the host classifier's `autoMode.allow` deny to fall open behaviorally — an ungranted external-engine dispatch is denied by the host, the write never happens, and the fix falls open to Claude.

Per-round dispatch is **script-owned** — this **reverses** the former "coverage uniformity" rule (all five specialists at fixed tiers every round). `code_loop_plan.py` emits each round's `dims_to_run`: round 1 is the full `reviewer-deep` panel; later rounds dispatch exactly the emitted schedule, skipping a dimension only on a prior high-confidence-clean result whose subject the fix did not touch — safe because a full `reviewer-deep` confirmation panel is mandatory before any exit (the "no security-relevant files changed" worry, e.g. an IDOR slipping through, is answered by that bound, not by re-running five reviewers every delta round). Obey the emitted schedule; never tier or skip by eye. Full contract: `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/review-code/reference/round-scheduler.md`.

### 3. Dispatch Specialists in Parallel

Launch the round's scheduled specialists (round 1: all five) in a **single message with parallel reviewer dispatches** so they run in parallel, each dispatched by its reviewer name (resolve dispatch via the host tool map). The specialist dispatch prompt template and dispatch instructions are in `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/review-code/reference/auto-fix-loop.md` — read it when building each subagent prompt. When `$REVIEWER_ENGINE` is `codex` or `cursor`, dispatch each of the five specialists through `engine_adapter.py` (read-only sandbox) instead of the named subagent — the persona and `$RUBRIC` are unchanged, and each still returns its dimension's findings JSON; an unreadable or missing specialist slot is the same `cannot-certify` signal, re-run on Claude (UFR-7). When `$REVIEWER_ENGINE` is `claude`, dispatch the named subagents exactly as below.

**Per-agent substitutions** (reviewer name → findings filename stem → dimension label):

| reviewer | `<agent>` (findings filename) | `<dimension>` |
| ---------------------------- | ----------------------------- | ------------- |
| architecture-reviewer        | architecture                  | Architecture  |
| code-reviewer                | code                          | Code          |
| security-reviewer            | security                      | Security      |
| test-reviewer                | test                          | Test          |
| premortem-reviewer           | premortem                     | Failure-Mode  |

After dispatch, wait for all five agents to return. Each writes its findings file to `$SESSION_DIR/round-<round>/`. The orchestrator does not read agent transcripts — only the JSON files.

### 4. Compile + Dedupe (main context)

Read the five `$SESSION_DIR/round-<round>/findings-*.json` files. Apply, in order:

1. **Citation check.** Drop any finding with `file == null` or `line == null` — the base rubric's verification rules require a `file:line` citation.
2. **Diff-scope verification.** Parse `$SESSION_DIR/round-<round>/diff.txt` to identify, for each file, the set of line numbers on `+` or `-` lines (the same hunk-walking logic `resolve_diff_lines.py` uses). Drop findings whose `(file, line)` pair isn't in that set. This is the same rule the subagents are supposed to enforce — duplicating it at compile time catches the cases they slip up on, especially context-line flags.
3. **Reachability pre-check on Important findings.** For each remaining `severity == "Important"` finding, open the cited file (in `$SESSION_DIR/repo/` for the read-only PR paths, working tree otherwise), find the call sites of the affected symbol, and confirm the edge case is reachable. **When in doubt, downgrade to Minor rather than drop** — the user can still see and approve it, but it isn't blocking the verdict.
4. **Dedupe by `(file, line)`.** When two findings target the same `(file, line)`, merge them: concatenate bodies with a separator, keep the higher severity, and list both dimensions (e.g. `"Security + Code"`). The merged finding **keeps the higher-severity input's `title`** (ties → the earlier one in dimension order Architecture, Code, Security, Test, Failure-Mode), so the finding identity (`file::normalized-title`) is deterministic round-to-round — the circuit breaker's recurrence check depends on a stable title. The merged finding is **`tradeoff: true` if either input is** (a judgment call in one facet makes the whole finding a judgment call). This also prevents the visual clutter of two GitHub comments on the same line.
5. **Author-justification filter (PR mode).** Cross-reference `prior-comments.json`. If a prior comment thread on the same `(file, line)` (or with the same finding topic on an outdated anchor) shows a substantive author justification, drop the new finding unless its body identifies a technical error in the justification.
6. **Nit cap.** After dedupe, if more than 5 Nits remain, keep the first 5 and replace the rest with a single summary entry like `"+ 12 more Nits — see $SESSION_DIR/round-<round>/findings-*.json for details"` (the base rubric's severity caps).
7. **Per-finding verification + synthesis merge** (never the session model). Replace the single keep/drop judge with per-finding verification. Stage ids and cluster the merged findings (`verification.py` `stage_ids` + `cluster_findings`), dispatch **one fresh verifier per cluster** (`model: $VERIFIER_MODEL`, resolved `--role verifier`, on the reviewer engine; it reads the diff and the repo but **never the PR narrative** — the #230 immunity), and apply their 3-state verdicts via `verification.apply_verdicts`: **REFUTED** drops with its reason (recorded, `was_blocking_tagged` preserved); **CONFIRMED / PLAUSIBLE** survive with the `verdict` stamped (CONFIRMED carries the executed-receipt evidence); a missing / malformed / reasonless-REFUTED verdict is **KEEP-ON-UNCERTAIN** as PLAUSIBLE at its pre-verification severity — a model's silence never drops a finding; severity is normalized and a blocking→non-blocking change recorded in `downgrades`. Then a **synthesis judge** (`model: $SYNTH_MODEL`, `--role synthesis`) groups same-root-cause survivors, and `verification.merge_and_rank` applies the grouping under a **coverage guarantee** — every survivor kept exactly once, fail-open to unmerged (synthesis can drop nothing). Verifier/synthesis failure or no result → keep the merged findings with **no findings dropped**. Replace `findings` with the survivors (each stamped `verdict`) and record `drops` and `downgrades`. Do **not** judge realness yourself or reimplement the fold. Full contract: `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/review-code/reference/verification-pass.md`.

8. **PR-body honesty check (PR mode only).** The review seat also verifies the PR body carries a valid **DoD disposition table** (the `superheroes:dod-table` marker) against the issue/spec — one row per Definition-of-Done bullet, each `done` (with an evidence pointer) or `deferred` (with a filed issue `#NNN` and a one-line reason). Append an **Important** finding (cited at the PR body, `tradeoff: true`, author-resolved — it is a judgment call the author closes by writing the table, not a mechanical fix) when the table is missing, or a row's evidence or deferral is empty or hollow. Branch mode has no PR body — skip. Contract: CONVENTIONS `§10.7`, `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/rubric/review-discipline.md`.

Determine the verdict per the base rubric's "Verdict labels & mapping" (count post-dedupe, post-synthesis findings). For `/superheroes:review-code` the labels are **READY FOR PR** / **FIX BEFORE PR** / **MAJOR FIXES NEEDED**:

- 0 Critical, 0 Important → **READY FOR PR**
- 0 Critical, 1+ Important → **FIX BEFORE PR**
- 1+ Critical → **MAJOR FIXES NEEDED**
- Only Minor and/or Nit → **READY FOR PR** (Minor/Nit are informational)

Write the result to `$SESSION_DIR/round-<round>/compiled.json` (preserve each finding's `tradeoff` field through dedupe so triage can read it):

```json
{
  "summary": "<1-2 sentence overall summary>",
  "verdict": "READY FOR PR" | "FIX BEFORE PR" | "MAJOR FIXES NEEDED",
  "findings": [<verified survivors, each stamped verdict: "CONFIRMED"|"PLAUSIBLE">],
  "drops": [<verification REFUTED drops: {id, file, title, reason, was_blocking_tagged}>],
  "downgrades": [<blocking→non-blocking re-tiers: {id, file, title, from, to, reason?}>]
}
```

Order findings: Critical → Important → Minor → Nit, then by file path, then by line.

## Auto-Fix Loop (default path)

Runs when neither `--post` nor `--review-only` is set, and the profile's verify story is not `mode: review-only` (a `review-only` profile degrades the default path to a single review pass + the `--review-only` presentation — see `## The verify command`). The orchestrator keeps a **skip-set** of finding identities the user chose to skip (identity = `file::normalized-title`, matching `circuit_breaker.py`). Initialize `round = 1`, `skip-set = {}`.

**If context was compacted mid-loop**, re-read `$SESSION_DIR/meta.json` (its `path` field says whether the loop, `--review-only`, or `--post` is active; its `verify` field restores the verify story), the highest-numbered `round-N/` files, and every `round-*/resolutions.json` (to rebuild the skip-set, and the **skipped-blocking** set from each entry's `severity`). Then resume mid-round by inspecting which `round-<highest>/` artifacts already exist:

| Present in `round-<N>/`                                       | Resume at                            |
| ------------------------------------------------------------- | ------------------------------------ |
| no `compiled.json`                                            | step 1 (restart the round)           |
| `compiled.json`, no `triage.json`                             | step 6                               |
| `triage.json`, no `fix-batch.json`                            | step 7                               |
| `fix-batch.json`, no `Auto-fix round <N>` commit in `git log` | step 11 (re-dispatch the fixer)      |
| `Auto-fix round <N>` commit present                           | step 12 (re-run verify, then breaker) |

Each round:

1. `mkdir -p $SESSION_DIR/round-<round>`. Regenerate the diff locally: `git diff <baseRef>...HEAD > $SESSION_DIR/round-<round>/diff.txt`. Size it with `wc -l` only — never `cat` it.
2. **Review — the round's schedule is script-owned.** Run `python3 "$ROOT_DIR/lib/code_loop_plan.py" plan --session-dir "$SESSION_DIR" --round <round>` and dispatch **exactly** its `dims_to_run` (each at its tier's model, same prompt template as `## Dispatch Specialists in Parallel`), writing `round-<round>/findings-<agent>.json` and pointing them at `round-<round>/diff.txt`. For each `skipped` dimension, copy its last-run `findings-<agent>.json` into `round-<round>/` so compile sees a full five-dimension panel. Then run `python3 "$ROOT_DIR/lib/code_loop_plan.py" record --session-dir "$SESSION_DIR" --round <round>`; if its `escalate` list is non-empty, re-dispatch just those dimensions once at `reviewer-deep` and run `record` again. Round 1 is the full `reviewer-deep` panel. Full contract (plan/record/decide, tier→model, head-diff derivation): `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/review-code/reference/round-scheduler.md`.
3. **Compile + dedupe** into `round-<round>/compiled.json` with verdict (same pipeline as `## Compile + Dedupe`).
4. **Effective findings** = `compiled.findings` whose identity is NOT in the skip-set.
5. If `effective` is empty → this round is clean. Write `round-<round>/fix-batch.json` as `[]`, skip triage/fix/verify/breaker, set `BREAKER_HALT=no`, and go straight to the **continuation gate** (step 14) — do **not** declare success here by eye. The gate returns `exit_clean` **only** off a qualifying full `reviewer-deep` round; off a reduced round it schedules the mandatory full-deep confirmation round first (the confirmation invariant is script-owned, #174).
6. **Triage.** Dispatch the triage subagent (template below) over `effective`, writing `round-<round>/triage.json`.
7. **Interventions — escalate only owner-weighable blockers (per `escalation-base.md`).** For each **Critical/Important** effective finding, route its disposition with the shared rubric (modes PROCEED/NOTIFY/GATE). **GATE** (the consolidated `AskUserQuestion` below) only the blockers whose skip-or-fix is genuinely the owner's call — a product/scope/risk trade-off. For the rest, **verify and proceed**, recording the disposition so `loop_state` still sees it:
   - **Evidence-or-silence (#175/#506).** A Critical/Important finding may **GATE** the owner only when its verifier `verdict` is **CONFIRMED** (an executed receipt). A **PLAUSIBLE Critical never GATEs and never parks**: fix it if safe (fold into the fix batch); else run the **confirming probe** — re-dispatch the verifier (`--role verifier`) for that finding to seek the triggering input, and a CONFIRMED upgrade then becomes GATE-eligible; else record it as a **grounded advisory** (`action: "skip"`, `advisory: true`, its verification-trace being the PLAUSIBLE verdict — a citable ground truth, so it does not GATE) so it rides the handback disclosed through the skipped-blocker channel, never interrupting mid-run.
   - **Fix, one right answer per the project's conventions** → fold into the fix batch (step 8) using the POV's suggested approach (a step-8 auto-fix).
   - **Verifiably-safe skip / believed false-positive** → record a **skip** in `resolutions.json` (`action: "skip"`, **carrying the finding's `severity`**) and add the identity to the skip-set, **with a verification trace** (cite the source / test you checked). A skip with no citable ground truth is **not** eligible — it GATEs. **Never silently drop a blocker** — a skipped blocker is recorded with its severity, so `loop_state` counts it.
   - **NOTIFY (the rubric's middle mode on a blocker)** → act on the best default (the auto-fix when there is one right answer, else the verifiably-safe skip) and record it via `decisions.py` and in the End-of-Loop Summary with its reverse-path/expiry — surfaced, not asked. (Mirrors the trio: record GATE outcomes and NOTIFY decisions in the summary with their reverse-path/expiry, per `escalation-base.md`.)
   - Minor/Nit → never escalated: apply the triage recommendation automatically — `Skip`/`Defer` → add the identity to the skip-set; `Fix` → fold into the fix batch (step 8), using the POV's suggested approach for a judgment-fix — then record each via `decisions.py` and surface them in the End-of-Loop Summary (auto-skipped / auto-fixed).
   Resolve the rubric for this dispatch once via the wrapper (with `REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)` defined in setup): `RUBRIC_RES=$(python3 "${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/lib/escalation_resolve.py" rubric --root "$REPO_ROOT")` — read its `path` and embed it (apply the embedded fail-closed posture if `degraded`: apply the hard floor and GATE anything owner-weighable). Nothing is hidden, just not asked; everything the agent recommends fixing mechanically (any severity) is handled in step 8 without asking.
   - **Write `round-<round>/resolutions.json` whenever this round records ANY disposition** — every autonomous verifiably-safe skip (the bullet above), every NOTIFY-skip, AND every gated answer below. This is the only channel by which step 14 sees a skipped blocker, so it is written even when no `AskUserQuestion` is presented:
     ```json
     { "round": <N>, "resolutions": [
       { "id": "<finding id>", "file": "<file>", "title": "<title>", "severity": "<severity>", "action": "fix" | "fix-with-guidance" | "skip", "guidance": "<text or omitted>" }
     ] }
     ```
     Add every `skip` identity to the skip-set; a skipped Critical/Important finding is recorded with its `severity` so `loop_state` counts it (this survives compaction). `approved` = entries with action `fix`/`fix-with-guidance` (carry `guidance`).
   - **Present the GATE only for the present-set (owner-weighable blockers).** If the present-set is non-empty: present ONE consolidated `AskUserQuestion`. For each finding, **lead with the orchestrator POV** from `triage.json` (per the base rubric's "Orchestrator POV") — show the recommendation, rationale, and confidence right under the finding, e.g. `→ POV: Skip (Low confidence) — correct in theory but this path is never hit concurrently under the profile's threat model`. Then offer **Fix as suggested** / **Fix with my guidance** (free text) / **Skip** — keep the options in this neutral order regardless of the POV; the POV informs, it does not pre-select. List the auto-fix findings (`recommendation` Fix AND `classification` mechanical) in the same prompt as an FYI (no per-item action; they are fixed automatically). Fold each answer into the `resolutions.json` written above. If the present-set is empty, present no `AskUserQuestion` — but `resolutions.json` is still written (above) whenever the round recorded any skip; only a round with no skip at all omits the file.
     **Record decisions (learning loop):** after writing `resolutions.json`, append one `decisions.py` record per resolution to the resolved decisions store (`$DECISIONS`) (`action`: `skip` → `skip`, `fix-with-guidance` → `guidance`, `fix` → `fix`), per `## Learning Loop & Staleness Nudge` → "Recording decisions". Also append a `fix` record for each `auto-fix-set` finding fixed silently this round. This append is non-blocking and never gates the loop.
8. **Fix batch.** `auto-fix-set` = effective findings where `recommendation` is `Fix` AND (`classification` is `mechanical` **OR** severity is `Minor`/`Nit`) — mechanical fixes at any severity, plus non-blocking judgment-fixes applied as the POV suggests (a non-blocking judgment call isn't worth an interrupt). `fix-batch` = `auto-fix-set ∪ approved`. Write `round-<round>/fix-batch.json` (full finding objects; attach `userGuidance` to any with guidance). (Blocking — Critical/Important — judgment-fixes are not auto-added; they arrive via `approved` from step 7.)
9. **Blocking-to-fix** = count of `fix-batch` findings with severity Critical or Important.
10. If `fix-batch` is empty (every effective finding this round was skipped), skip the fixer/verify/breaker, set `BREAKER_HALT=no`, and go to the **continuation gate** (step 14) with the empty `fix-batch` and this round's `resolutions.json`. The gate returns `exit_skipped` **only** off a qualifying full `reviewer-deep` round (list the deliberately-skipped blocker(s), do **not** report a plain success); off a reduced round it schedules the mandatory full-deep confirmation round first — a skipped blocker is not certified until a full panel confirms the rest is clean (#174).
11. **Fix.** Dispatch the fixer subagent (template below) with `fix-batch.json`.
    - Status `CHECK_FAILED` → **HALT** (`ACTION=halt`, `ROUND=<round>`, `REASON="fixer CHECK_FAILED"`) and proceed to the End-of-Loop Summary (which writes `--result-file` if set), then surface the failing `VERIFY_CMD` output. (When the profile is `mode: unverified`, the fixer runs no checks and cannot return `CHECK_FAILED`.)
    - Status `ESCALATED` → for each escalated finding, present it as a `present-set` intervention now (same prompt shape as step 7), then re-dispatch the fixer with the user's decisions folded in. The follow-up dispatch uses this same `CHECK_FAILED`/`ESCALATED` contract; a finding the user has already decided on is no longer eligible to escalate, so it cannot ping-pong. Do NOT add an escalated finding to the skip-set unless the user skips it. After escalation handling resolves the final `fix-batch`, recompute **blocking-to-fix** (step 9) before evaluating step 14.
12. **Verify.** If a `VERIFY_CMD` is set, the orchestrator independently runs it from the user's own working tree (never the PR head), non-interactively, with a timeout. Fail (non-zero exit) → **HALT** (`ACTION=halt`, `ROUND=<round>`, `REASON="verify CHECK_FAILED"`) and proceed to the End-of-Loop Summary (which writes `--result-file` if set), then surface output. (Do not re-review on a broken tree.) If the profile's verify story is `mode: unverified`, **SKIP this gate** — there is no command to run; the round's commit stands ungated.
13. **Circuit breaker.** Run `python3 "${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/lib/circuit_breaker.py" "$SESSION_DIR" 7`. Parse its JSON; **capture `halt`** as `BREAKER_HALT` (`yes`/`no`). Do NOT read or `cat` the diff into the orchestrator context. (Don't act on it yet — step 14 feeds it to the continuation gate so the next action is decided in one place.)
14. **Continuation gate + next schedule — decided by a script, not by you.** Whether to run another round — and **which dimensions run next, at which tier** — is **not yours to judge by eye**: a model rationalizes early exits ("this fix is trivial", "the next round will be clean", "I'll offer it as optional", "save the tokens"). This is the symmetric partner to the circuit breaker — it guards against stopping *too early* the way the breaker guards against looping *too long*. Run `code_loop_plan.py decide` (it wraps `loop_state.py`'s continuation decision, derives the blocking counts from the round artifacts and the changed surface from the git diff so neither is yours to self-report, and emits the next round's `dims_to_run`) and **obey its `action`**:

    ```bash
    ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
    git diff "$BASE_REF"...HEAD > "$SESSION_DIR/round-<N>/head-diff.txt"   # post-fix surface: what ACTUALLY changed (#157/#158), never the fixer's self-report
    python3 "$ROOT_DIR/lib/code_loop_plan.py" decide --session-dir "$SESSION_DIR" --round <N> --max-rounds 7 \
      --breaker-halt "$BREAKER_HALT" \
      --fix-batch "$SESSION_DIR/round-<N>/fix-batch.json" \
      --resolutions "$SESSION_DIR/round-<N>/resolutions.json"
    ```

    (A `resolutions.json` is written whenever the round recorded any skip — autonomous, NOTIFY, or gated; omit `--resolutions` only when no skip occurred at all this round.) Parse its JSON `{action, dims_to_run, reason, ...}` and **do exactly what `action` says — you may not substitute your own judgment for it**:
    - **`review`** → `round += 1` and **repeat from step 1**, dispatching its `dims_to_run` **exactly** (the next round's plan is already persisted; it may be a reduced scoped round or a full `reviewer-deep` confirmation round — `roundKind`). This is **MANDATORY**: you applied a blocking fix (or a reduced round owes a full-deep confirmation) and the loop must re-review to verify it. Do **not** exit, declare success, or present the next round as optional. (The classic skip is to stop here believing it's clean — that belief is exactly what this gate overrides; the last time it was trusted, the "obviously clean" re-review found two real bugs in the fix.)
    - **`exit_clean`** → set `ACTION=exit_clean`, `ROUND=<round>`, `REASON=<gate reason>` and **EXIT SUCCESS** (no blocking fix applied this round and none skipped; any Minor/Nit are now fixed). Surface the gate's `certification` block honestly (how many full `reviewer-deep` confirmation panels ran, and whether the last panel's findings were resolved with scoped verification) — never imply a pristine fresh pass that did not occur (#174).
    - **`exit_skipped`** → set `ACTION=exit_skipped`, `ROUND=<round>`, `REASON=<gate reason>` and **EXIT — CLEAN EXCEPT FOR SKIPPED**: list the deliberately-skipped blocking finding(s); do **not** report a plain SUCCESS verdict.
    - **`halt`** → set `ACTION=halt`, `ROUND=<round>`, `REASON=<gate reason>` and **HALT**: surface the gate's `reason` (plus the breaker's `reason`/`detail` if it halted) + the still-open findings + the commit range (`git log <baseRef>..HEAD --oneline`).

    On `ESCALATED` re-handling (step 11), recompute the fix-batch first, then run this gate on the final `round-<N>/fix-batch.json`. **Red flags that mean you are about to skip the loop** — if you catch yourself thinking any of these, run the gate and obey it instead: "it's a trivial/one-line fix" · "round N+1 will obviously be clean" · "I have full context, I can tell it's done" · "a re-review is diminishing returns / not worth the tokens" · "I'll *offer* another round as optional." None of these is yours to act on; `code_loop_plan.py` decides.

### Triage and Fixer subagent prompts

The triage and fixer subagent prompt templates (including the escalation-guard context and enforcement boundary note) are in `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/review-code/reference/auto-fix-loop.md` — read them when building the respective dispatches. The orchestrator must embed `ESC_WRAPPER` and `REPO_ROOT` (resolved in setup as absolute paths) into the fixer prompt's `## Input` block before dispatching.

### End-of-Loop Summary

**If `--result-file` was passed**, write the terminal loop_state decision before printing the summary (atomic write via temp file):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 "$ROOT_DIR/lib/review_result.py" write \
  --path "$RESULT_FILE" \
  --action "$ACTION" \
  --round "$ROUND" \
  --reason "$REASON"
```

(`$ACTION`, `$ROUND`, and `$REASON` are set on **every** terminal exit path: step-5 (clean) and step-10 (all-skipped) now route **through** the step-14 gate, so their action comes from the gate (`exit_clean`/`exit_skipped`, or a mandatory confirmation round that keeps looping); step-11/12 HALT → `halt`; step-14 → the gate's returned action. Each terminal path sets these variables before jumping to the End-of-Loop Summary, so the write always has defined values. `$RESULT_FILE` is the path supplied via `--result-file`. When `--result-file` is absent, skip this step entirely — no file written, no behavior change.)

Print: final verdict, rounds run, commits created (one per round), findings fixed by severity, any blocking findings deliberately skipped, **the findings verification dropped (REFUTED) as unsubstantiated** (each with its reason) and — distinctly, flagged for your scrutiny — **any dropped finding a reviewer had tagged Critical/Important** (`was_blocking_tagged`; a dropped blocker is always surfaced, never silently gone) **and any finding verification downgraded from blocking to non-blocking** (`downgrades`; show `from → to`, flagged for the same scrutiny — a silent downgrade is a silent-drop equivalent), **any PLAUSIBLE-Critical advisories** (`advisory: true` skips — disclosed, unproven blockers the owner reads at review, never a silently-decided skip), **the Minor/Nit findings auto-handled without asking** (a short list — `auto-fixed` vs `auto-skipped` — so the non-blocking work the loop did silently is visible, not hidden), and any new findings the fixer noticed/introduced along the way (informational). If the verify story was `unverified`, state that fixes were committed **without a verify gate**. Because fixes are local-only, offer to push the branch (or, if this was a PR you don't own, point to `--post`). Do not push without explicit confirmation.

**Then, after the summary**, run the three non-blocking end-of-run steps from `## Learning Loop & Staleness Nudge`, in order: (1) the **staleness nudge** (print the doctor `message` only when non-null and `nudge_acked` is false), (2) the **learning-loop proposal** (`decisions.py analyze` → at most one user-gated `AskUserQuestion`, never auto-applied), then (3) the **provisional-profile confirmation** (interactive only — offer to confirm a `status: provisional` profile; skipped when headless, already stable, or already acked). All three are placed after the review output and none blocks.

## Read-Only Paths

These two paths run a **single review pass** (loop steps 1-3, writing artifacts under `round-1/`) and then diverge. Neither triages, fixes, commits, or loops.

### `--review-only`

After the single pass, run the interactive tiered presentation and a terminal report. No commits. (A profile with `mode: review-only` makes the default path degrade into exactly this presentation.)

**If context was compacted between dispatch and presentation**, re-read `$SESSION_DIR/round-1/compiled.json` and `$SESSION_DIR/meta.json` to restore state. The skill is resumable from disk.

**Form the orchestrator POV before presenting.** Per the base rubric's "Orchestrator POV", for each Critical/Important finding open the cited file at the cited line (in `$SESSION_DIR/repo/` for the PR path, working tree otherwise) and form a **Fix / Skip / Defer + one-sentence rationale + High/Low confidence** take. This is the coordinator's own judgment from a small targeted read — not a re-review. For batched Minor/Nit, derive the POV from the finding text (read the file only if the text is insufficient).

**Apply the review gate.** Partition findings by POV: `auto-include` = `recommendation == Fix` (these enter the report without asking); `ask-set` = `recommendation` is `Skip` or `Defer` (these need your call). Only the `ask-set` is presented below; the `auto-include` set is added to the approved findings silently.

Open with the verdict banner and the one-line summary. If the `ask-set` is empty, skip straight to the report. Otherwise run the tiered presentation over the `ask-set` only:

- **Critical and Important findings (ask-set) — individually.** For each, use `AskUserQuestion`. Header includes severity tag, dimension(s), and `file:line`. Body shows the finding text, the suggested fix, and — on its own line — the **POV**: e.g. `→ POV: Skip (Low confidence) — correct in theory but this path is never hit concurrently under the profile's threat model`. Options (keep this neutral order; the POV informs but does not pre-select):
  - **Approve** — include at current severity.
  - **Modify** — open a free-text edit for the comment body before approval.
  - **Downgrade** — drop one severity tier (Critical → Important, Important → Minor). A downgraded Important → Minor is **auto-approved at Minor** and not re-presented in the Minor batch.
  - **Skip** — exclude entirely.
  - The user may use "Other" to push back, ask a clarifying question, or request a targeted re-verification. Engage. If they question a specific finding, read the relevant file from `$SESSION_DIR/repo/` (or working tree) to re-check that one location — this is a small, targeted read, not loading the full diff.

- **Minor and Nit findings (ask-set) — batched, multi-select.** Present in batches of 4 via `AskUserQuestion` with multi-select. For each finding, show severity, `file:line`, a 2-3 sentence summary, and a compact POV tag (e.g. `POV: Skip (Low)`). Always offer **Include all** and **Skip all** as alternatives at the bottom of the batch.

The approved set = `auto-include` ∪ the findings approved from the `ask-set`. After the last batch, summarize how many of each severity were approved, then print a terminal report grouped by severity. Lead with the verdict label in bold. For each approved finding: severity tag, `file:line`, title, body, and the orchestrator POV line. End with the count summary (e.g. `"3 Critical, 5 Important, 2 Minor approved"`). Save nothing else to disk — `compiled.json` already has the full record.

**Record decisions (learning loop):** as you resolve the `ask-set` findings, append one `decisions.py` record per decision to the resolved decisions store (`$DECISIONS`) (**Approve**/**Modify**/**Downgrade** → `fix`; **Skip** → `skip`), per `## Learning Loop & Staleness Nudge`. Then, after the terminal report, run the three non-blocking end-of-run steps (staleness nudge, then learning-loop proposal, then provisional-profile confirmation) from that section, in order.

### `--post`

After the single pass (PR mode only), post approved findings to GitHub. No triage, no fix, no loop, no commits to the tree. Run the interactive tiered presentation above (including its **review gate**) to select which findings to post: `recommendation == Fix` findings are auto-selected for posting, and only `Skip`/`Defer` findings are presented for your call. The orchestrator POV is shown to **you** during selection, but is **not** included in the posted comment body (the public comment stays the finding + suggestion). Then ask the user the review event type via `AskUserQuestion`:

- **COMMENT** — findings without approval/rejection
- **REQUEST_CHANGES** — blocks merge until resolved
- **APPROVE** — approve with comments

Build the review JSON, run `resolve_diff_lines.py` to validate anchors, post via `gh api`, and verify the post landed — the exact commands and error-handling are in `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/review-code/reference/auto-fix-loop.md` under `## --post API Commands`. Surface `MOVED:`/`DROPPED:` lines from the script's stderr to the user before posting. Report the review URL (`html_url` from the verification call) to the user.

**Record decisions + end-of-run steps (learning loop):** as you resolve the `ask-set` during selection, append one `decisions.py` record per decision to the resolved decisions store (`$DECISIONS`) (a finding selected for posting → `fix`; a **Skip**/**Drop** → `skip`), per `## Learning Loop & Staleness Nudge`. Then, after reporting the review URL, run the three non-blocking end-of-run steps (staleness nudge, then learning-loop proposal, then provisional-profile confirmation) from that section, in order. (On the `--post` path the staleness check ran with `--root "$SESSION_DIR/repo"`.)

## The verify command

The orchestrator's verify gate (loop step 12) and the fixer (prompt step 3) both run the project's own verify command, read from the resolved profile (`$PROFILE`)'s `## Verify` section during Setup. There are three branches:

- **`command: <cmd>` →** `VERIFY_CMD="<cmd>"`. Both the orchestrator's gate and the fixer run `VERIFY_CMD` from the user's own working tree (never the PR head), non-interactively, with a timeout. A non-zero exit is a **HALT / `CHECK_FAILED`** — the orchestrator surfaces the failing output and does not re-review on a broken tree.
- **`mode: unverified` →** there is no verify command. SKIP the verify gate (step 12); tell the fixer not to run checks (verify command `"none"`); commits proceed ungated. State "unverified" in the dispatch summary and the End-of-Loop summary.
- **`mode: review-only` →** the project opted out of auto-fix. The default path degrades to a single review pass + the `--review-only` presentation (no triage, no fixer, no commits, no loop). Note this in the dispatch summary.

`meta.json` records the verify story (`verify`: the command string, or `"unverified"` / `"review-only"`) so a cold-resumed orchestrator recovers it without re-reading the profile.

## Learning Loop & Staleness Nudge

For recurrence handling, coverage decisions, dimension skipping, tier cascade, final confirmation, and telemetry, use `plugins/superheroes/reference/review-loop.md` as the shared loop contract. This skill owns only its leg-specific setup, reviewer framing, and gate-write rules. The subagent prompt templates, verification rules, and common mistakes for this skill are in `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/review-code/reference/auto-fix-loop.md`.
