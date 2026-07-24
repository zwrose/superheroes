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
| `$SESSION_DIR/loop-state.json`                      | round driver   | Auto-fix loop only: driver state (`next`/`submit` protocol)                                 |
| `$SESSION_DIR/driver-journal.jsonl`                 | round driver   | Auto-fix loop only: `scriptRan` journal (one line per `next`/`submit`)                      |
| `$SESSION_DIR/round-receipt.json`                   | round driver   | Auto-fix loop only: terminal receipt (`validate_receipt` shape)                             |

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
FIXER_MODEL=$(python3 "$MT" --role code-fixer --overrides "$OV" | jq -r '.model // empty')  # auto-fix loop fixer tier (#510)
```

**Resolve per-role engine (FR-15).** Default `claude` when unset.

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
EP=$(python3 "$ROOT_DIR/lib/engine_pref_load.py")            # {"reviewer","implementation"} (both "claude" if unset)
REVIEWER_ENGINE=$(echo "$EP" | jq -r '.reviewer // "claude"')
IMPL_ENGINE=$(echo "$EP" | jq -r '.implementation // "claude"')
```

**Compose the panel seat map (#510).** Per-seat engine+model over the live vendors — this replaces the single `$REVIEWER_ENGINE`-for-all-seats knob. `$AUTHOR_FAMILY` is the implementation engine's maker family; the narrative family is this orchestrator (`anthropic`). The map (per-seat tiers + resolved models, any pin/degradation disclosures) rides into the receipt; per-seat consumption is in `reference/auto-fix-loop.md`.

```bash
CONFIGURED=$(python3 -c "import sys;sys.path.insert(0,'$ROOT_DIR/lib');import preflight_probe,core_md;p=(core_md.read('.') or {}).get('enginePreferences') or {};print(','.join(preflight_probe.configured_cross_vendor_engines(p)))")
AUTHOR_FAMILY=$(python3 -c "import sys;sys.path.insert(0,'$ROOT_DIR/lib');import model_registry as m;print(m.family_for('code-fixer','$IMPL_ENGINE') or '')")
SEAT_MAP=$(python3 "$ROOT_DIR/lib/seat_map.py" compose --configured-engines "$CONFIGURED" --author-family "$AUTHOR_FAMILY" --narrative-family anthropic --pr-number "${PR_NUMBER:-}" --head-sha "$(git rev-parse HEAD 2>/dev/null)" || echo '{"seats":{},"degradations":[{"constraint":"compose-failed","reason":"seat_map compose failed — every seat falls open to Claude"}]}')
```

When dispatching specialists, map each panel seat's **tier** to a model — `reviewer-deep` → `model: $DEEP_MODEL`, `reviewer` → `model: $REVIEWER_MODEL` (the auto-fix loop's per-round schedule is driver-owned; see `round-driver.md`). Triage subagents use `model: $MECH_MODEL`; the fixer uses `model: $FIXER_MODEL` (the `code-fixer` tier, #510). An empty value means "inherit the session model" — omit the `model` arg in that case.

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
- **Specialists to dispatch (round 1: all five at `reviewer-deep`, in parallel; later rounds: obey `round_driver.py` `next` — delta audits + scoped finder, or a full panel on #174/unknown):**
  - `architecture-reviewer` → `findings-architecture.json`
  - `code-reviewer` → `findings-code.json`
  - `security-reviewer` → `findings-security.json`
  - `test-reviewer` → `findings-test.json`
  - `premortem-reviewer` → `findings-premortem.json`
- **Session directory:** `$SESSION_DIR` (round 1 artifacts under `round-1/`)
- **Focus notes:** the `--focus` argument, if any
- **Path:** default → auto-fix loop (`round_driver.py` next/submit until terminal); `--review-only` → one pass + interactive presentation; `--post` → one pass + post to GitHub
- **What happens after dispatch (default loop):** obey `next`/`submit` — panel/verify/synthesis → fixer → verify gate → delta audits/scoped finder → terminal with certification + receipt. The auto-fix runs on `$IMPL_ENGINE` (FR-15): when it is `codex`/`cursor`, the fix is written by the external engine via `engine_adapter.py` (workspace-write) and committed by the adapter, then the same verify gate runs; when it is `claude`, the fixer subagent runs as today. This standalone path has no run-time `engine_authz.py test-dispatch` preflight (that lives only in the native build leg's `_implWriteAuthorized`); instead it relies on the host classifier's `autoMode.allow` deny to fall open behaviorally — an ungranted external-engine dispatch is denied by the host, the write never happens, and the fix falls open to Claude.

Per-round dispatch is **driver-owned** — round 1 is the full `reviewer-deep` baseline; rounds 2+ are **delta rounds** (fix audits + scoped finder) unless the #174 triggers or an unknown changed surface schedule a full panel. A full `reviewer-deep` confirmation panel is mandatory before certifying exit when economics require it. Obey `round_driver.py` `next`/`submit`; never tier, skip, or exit by eye. Full contract: `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/review-code/reference/round-driver.md`.

### 3. Dispatch Specialists in Parallel

Launch the round's scheduled specialists (round 1: all five) in a **single message with parallel reviewer dispatches** so they run in parallel, each dispatched by its reviewer name (resolve dispatch via the host tool map). The specialist dispatch prompt template and dispatch instructions are in `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/review-code/reference/auto-fix-loop.md` — read it when building each subagent prompt. Dispatch each seat through **its seat-map-assigned engine+model** (`$SEAT_MAP.seats[<reviewer>]` → `.vendor`/`.model`): a `claude` seat runs the named subagent at its tier model; a `codex`/`cursor` seat dispatches through `engine_adapter.py` (read-only sandbox) with that seat's resolved `.model` — persona and `$RUBRIC` unchanged, each returns its dimension's findings JSON. An unreadable or missing slot is the same `cannot-certify` signal, re-run on Claude (UFR-7). Submit the panel with `ranManifest: {<dim>: <vendor>}` built from your OWN dispatch records (which vendor actually produced each seat's folded findings — claude for any seat re-run on Claude after a forfeit); the driver emits the fall-open disclosure from it as machinery, so you do not hand-write it. Omitting the manifest for a cross-vendor panel is itself disclosed (provenance-unavailable). Per-seat dispatch + grounding-seat detail: `reference/auto-fix-loop.md`.

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

On the **read-only paths** (`--post`, `--review-only`), the orchestrator compiles in main context. On the **auto-fix loop**, the same mechanical steps run inside `round_driver.py` when panel/scoped findings are submitted — obey the driver's `next`/`submit` instead of reimplementing compile by hand.

Read the five `$SESSION_DIR/round-<round>/findings-*.json` files (read-only path only). Apply, in order:

1. **Citation check.** Drop any finding with `file == null` or `line == null`.
2. **Diff-scope verification.** Parse `$SESSION_DIR/round-<round>/diff.txt` for `+`/`-` anchor lines (same hunk-walking as `resolve_diff_lines.py`). Drop out-of-scope findings.
3. **Reachability pre-check (read-only path only).** For each remaining `severity == "Important"` finding, confirm the edge case is reachable; when in doubt, downgrade to Minor rather than drop.
4. **Dedupe by `(file, line)`.** Merge same-anchor findings: higher severity wins, dimensions unioned, stable `file::normalized-title` identity, `tradeoff: true` if either input is.
5. **Nit cap.** After dedupe, keep at most 5 Nits; overflow collapses to one summary entry.
6. **Per-finding verification + synthesis merge** (never the session model). Stage ids, cluster, dispatch one verifier per cluster (`model: $VERIFIER_MODEL`, reviewer engine; #230 immunity), apply `verification.apply_verdicts`, then one synthesis judge (`model: $SYNTH_MODEL`) groups root causes and `verification.merge_and_rank` merges under a coverage guarantee — synthesis drops nothing. Full contract: `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/review-code/reference/verification-pass.md`.
7. **Author-justification post-filter (PR mode only, after verification).** Cross-reference `prior-comments.json`. May drop **only** a finding whose verifier `verdict` is present and not **CONFIRMED**, recording the prior justification quoted. A **CONFIRMED** finding with a prior justification **survives**, stamped `challenge: "author-justified"` (ledger-visible). A finding with no verdict is never dropped here. Rules: `round-driver.md`.
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
  "downgrades": [<blocking→non-blocking re-tiers: {id, file, title, from, to, reason?}>],
  "unmatched": [<verifier verdict ids that matched NO finding — the id-transport fidelity signal>],
  "unverified": [<finding ids that got no verdict this round — verifier silence; they survive PLAUSIBLE>],
  "ambiguous": [<finding ids carried by >1 verdict — honored as none (keep-on-uncertain), disclosed not silently dropped>]
}
```

Order findings: Critical → Important → Minor → Nit, then by file path, then by line.

## Auto-Fix Loop (default path)

Runs when neither `--post` nor `--review-only` is set, and the profile's verify story is not `mode: review-only`. The loop is **driver-owned**: every per-round step is `python3 "$ROOT_DIR/lib/round_driver.py" next|submit` — the old `code_loop_plan` plan/record/decide, the manual `circuit_breaker.py` call, and the head-diff step all collapse into obeying `next`. Full contract: `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/review-code/reference/round-driver.md`.

**If context was compacted mid-loop**, re-read `$SESSION_DIR/meta.json`, `$SESSION_DIR/loop-state.json`, and `$SESSION_DIR/driver-journal.jsonl`. Resume by calling `next` — a pending step re-emits idempotently.

**Bootstrap.** `mkdir -p $SESSION_DIR/round-1`. Regenerate the diff: `git diff "$BASE_REF"...HEAD > $SESSION_DIR/round-1/diff.txt` (size with `wc -l` only). First `next` seeds state. Pass **`--vendors`** — the live reviewer/fixer vendors, either a JSON list (`["codex","cursor"]`) or a comma-separated string (`codex,cursor`) — so the driver can seat a **different** auditor vendor for each fix (independent audit). Also pass **`--fixer-vendor`** — the **actual** fix-implementer vendor (`$IMPL_ENGINE` from the calibration / engine resolution) — so the auditor is seated as a **different** vendor than the one that fixed; omitting it leaves the fixer defaulting to `claude`, which mislabels a `codex`-fixed → `codex`-audited run as independent. An unparseable value, an unknown vendor, or either flag on non-fresh state **fails loud** (nonzero exit + `{"ok": false, "reason": ...}`) — never a silent default. **Omitting `--vendors` degrades every run to the single vendor `["claude"]`:** the audit still runs but independence is **lost** and every terminal is stamped `-degraded` (e.g. `audited-chain-degraded`) — reserve that only for an environment that genuinely has one usable vendor. In PR mode also pass **`--prior-comments`** (the author-justification post-filter reads it; ignored when the file is absent):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
# Live vendors from the seat map (family-aware; #510) — the pool the driver seats independent
# fix-auditors from; falls back to the reviewer+impl engines if the seat map is unreadable.
VENDORS=$(echo "$SEAT_MAP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(json.dumps(sorted(d.get("liveVendors") or [])))' 2>/dev/null || python3 -c 'import json,sys; print(json.dumps(sorted({v for v in sys.argv[1:] if v})))' "$REVIEWER_ENGINE" "$IMPL_ENGINE")
python3 "$ROOT_DIR/lib/round_driver.py" next \
  --session-dir "$SESSION_DIR" \
  --diff-path "$SESSION_DIR/round-1/diff.txt" \
  --verify-command "${VERIFY_CMD:-none}" \
  --vendors "$VENDORS" \
  --fixer-vendor "$IMPL_ENGINE" \
  --prior-comments "$SESSION_DIR/prior-comments.json" \
  --max-rounds 7
```

**The loop.** Until `action` is `terminal`:

1. Parse `next` JSON: `{action, round, phase, attempt, expectedStateHash, payload}`.
2. **Dispatch exactly one action** (panel, verifiers, synthesis, gap-sweep, audits, scoped-finder, verify, fixer, judgment gate, or stall menu). Round 1 = full `reviewer-deep` panel; rounds 2+ = delta rounds (fix audits + scoped finder) unless the driver schedules a full panel (#174 re-arm or unknown surface → run-everything). Degraded/single-vendor: same driver, same journal, `independence: "degraded"` stamps — stay on the path.
3. Write the artifact JSON, then `submit` with echoed `phase`, `attempt`, and `expectedStateHash`.
4. On `present-judgment` (a tradeoff/product-choice blocker — an **intervention gate, not a terminal**), present each `payload.findings[]` with its `dispositions` (`fix-as-suggested`, `fix-with-guidance`, `skip`) and submit `{dispositions: [{id, disposition, guidance?, reason?}, ...]}` — `skip` needs a citable `reason`; the driver folds fixes back into the fix leg and rides skips on the exit disclosure (fail-closed: a missing/unknown disposition folds as `fix-as-suggested`). On `present-stall-menu` (the audit-stall terminal), present the four choices from `payload.choices` (`accept-the-disclosed-risk` only when `payload.acceptRiskEligible` — CONFIRMED with receipt). Never judge the dispute yourself.
5. On `terminal`, read `payload.certification` and `round-receipt.json`; map `verdict` to `$ACTION`/`$REASON` for `--result-file` (`converged` → `exit_clean`; `halted`/`held`/`stalled`/`capped-with-open-critical` → `halt`).

```bash
python3 "$ROOT_DIR/lib/round_driver.py" submit \
  --session-dir "$SESSION_DIR" \
  --phase "<phase>" --attempt <attempt> \
  --state-hash "<expectedStateHash>" \
  --artifact "$SESSION_DIR/round-<N>/<phase>-artifact.json"
```

**Terminals to surface honestly:** scoped certifying finish (`audited-chain` / `audited-chain-degraded` — say so, never imply a pristine fresh pass); one invisible self-recovery on audit-stall (journaled, not offered to the owner); the audit-stall stall menu; owner-skipped judgment blockers (ridden on the exit disclosure — a product-choice tradeoff shipped un-fixed, cited by its owner reason); `capped-with-open-critical` park when confirmation budget is exhausted with a Critical still owed.

**Red flags** — if you catch yourself thinking "trivial fix / obviously clean / save tokens / offer another round as optional", call `next` and obey the driver instead.

### Fixer subagent prompt

The fixer subagent prompt template (including the escalation-guard context) is in `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/review-code/reference/auto-fix-loop.md`. Embed `ESC_WRAPPER` and `REPO_ROOT` (absolute) into the fixer prompt's `## Input` block. On `dispatch-fixer`, submit `headDiff` and `changedSubjects` derived from git (`git diff "$BASE_REF"...HEAD`), never the fixer's self-report.

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

(`$ACTION`, `$ROUND`, and `$REASON` are set on **every** terminal exit from the driver (`converged` → `exit_clean`; other terminal verdicts → `halt` with the receipt reason). `$RESULT_FILE` is the path supplied via `--result-file`. When absent, skip this step.)

Print: final verdict, rounds run, commits created, findings fixed by severity, **the driver receipt's `certification` block** (shape, `fullPanel`, `independence`, any `note` — scoped certifying finish vs full-panel-confirmed, degraded disclosures), **the seat map** (`$SEAT_MAP` — per-seat tiers + resolved models + any pin/degradation disclosures), **`scriptRan` from the journal** (`round-receipt.json` → `scriptRan.invocations` and `byPhase` — the vet that the driver actually ran), **findings verification dropped (REFUTED)** as unsubstantiated, `was_blocking_tagged` drops, **findings downgraded from blocking to non-blocking** (`downgrades`; show `from → to`), **PLAUSIBLE-Critical `advisory: true` skips** (disclosed unproven blockers), auto-handled Minor/Nit, `unmatched`/`unverified`/`ambiguous`, and fixer `newIssuesNoticed`. If verify was `unverified`, state fixes were committed without a verify gate. Offer to push locally; do not push without confirmation.

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
