---
name: review-code
description: Use when reviewing code changes on a local branch or an open pull request before merging — including when you want the review's findings auto-fixed locally or posted to GitHub.
user-invocable: true
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# Review Code

Run a multi-dimensional code review on either an open pull request or a local branch (vs the default branch), then **autonomously fix what it finds**. The main context is an **orchestrator** — it fetches metadata, dispatches five specialist agents in parallel, compiles their findings, triages each into auto-fixable vs needs-your-judgment, applies fixes via a fixer subagent, and re-reviews — looping until no Critical/Important findings remain or a circuit breaker halts. Subagents do all heavy reading and write structured results to disk; it never loads the full diff or any agent's raw output into its own conversation.

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

**Auto-detection rule.** Run `gh pr list --head "$(git rev-parse --abbrev-ref HEAD)" --json number,headRefOid,headRefName --limit 1`. If the result is non-empty, default to PR mode. Otherwise default to branch mode. If the user passed `branch` explicitly, skip the lookup. If the user passed `pr <N>` explicitly, use `<N>` and don't auto-detect.

**`--post` only applies to PR mode.** If the user passes `--post` without a PR (and auto-detection finds none), stop and tell them — branch mode has nothing to post against.

## Session Directory

All review artifacts live in a per-invocation temp directory so parallel reviews don't collide:

```bash
SESSION_DIR=$(mktemp -d /tmp/review-XXXXXXXX)
```

Files written during the review. **Per-round artifacts live under `$SESSION_DIR/round-<N>/`** in the auto-fix loop (round 1, 2, …); the read-only paths (`--review-only`, `--post`) run a single pass and write that pass's artifacts under `round-1/` as well. Only `meta.json` lives at the session-dir root.

The full artifact table — every path, the component that writes it, and its purpose — is in `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/review-code/reference/setup.md` § Session artifacts.

**CRITICAL:** The main context only ever runs `wc -l < $SESSION_DIR/round-<N>/diff.txt` to size the diff. It never `cat`s the diff, never reads the full thing, never echoes it back. Subagents read the diff from disk and write structured findings; the orchestrator reads the findings JSON, not the diff.

## Workflow

### 1. Setup

Decide mode (auto-detected or explicit, per `## Invocation`). Create the session directory.

**Resolve the run's inputs before dispatching anything.** In order: the base rubric path, the escalation-guard wrapper and repo root, the calibration paths, the plugin and rubric versions, the model tiers, the per-role engine, the panel seat map, then the staleness self-check, the profile bootstrap, the verify story, and the post-bootstrap refresh of the dispatch paths. The exact commands, the variable each one sets, and the tier→model dispatch mapping are in `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/review-code/reference/setup.md` § Setup resolution — read it and run the blocks in the order given.

Everything below depends on the variables that file sets: `$ROOT_DIR`, `$RUBRIC`, `$ESC_WRAPPER`, `$REPO_ROOT`, `$CORE`, `$LAYER`, `$PROFILE`, `$LOCATION`, `$EXISTS`, `$DECISIONS`, `$PLUGIN_VERSION`, `$RUBRIC_VERSION`, `$REVIEWER_MODEL`, `$DEEP_MODEL`, `$MECH_MODEL`, `$SYNTH_MODEL`, `$VERIFIER_MODEL`, `$FIXER_MODEL`, `$EP`, `$REVIEWER_ENGINE`, `$IMPL_ENGINE`, `$CONFIGURED`, `$AUTHOR_FAMILY`, `$SEAT_PINS`, `$PINS_ARGS`, `$PROBE_MODE`, `$SEAT_MAP`, `$DOCTOR_JSON`, `$VERIFY_JSON`, `$VERIFY_CMD`, `$VERIFY_MODE`, `$REFUSAL`. A step below that reads one of these without that file having been run is a bug in the step; the shell defaults that do appear (`${VERIFY_CMD:-unverified}`, `${VERIFY_CMD:-none}`) are deliberate value fallbacks for an unset-but-legitimate verify story, not a licence to skip the setup file.

**PR mode:**

```bash
# Resolve PR number — either provided or auto-detected from current branch
BRANCH=$(git rev-parse --abbrev-ref HEAD); MODE=pr
if [ -z "$PR_NUMBER" ]; then
  PR_NUMBER=$(gh pr list --head "$BRANCH" --json number --jq '.[0].number')
fi

# Metadata: small JSON only — do NOT load the diff yet
gh pr view "$PR_NUMBER" --json number,title,author,headRefName,headRefOid,baseRefName,url,body > "$SESSION_DIR/pr.json"
HEAD_SHA=$(jq -r .headRefOid "$SESSION_DIR/pr.json")
PR_BRANCH=$(jq -r .headRefName "$SESSION_DIR/pr.json")
BASE_BRANCH=$(jq -r .baseRefName "$SESSION_DIR/pr.json")   # PR base branch NAME — pinned to a remote commit below
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

**Auto-fix branch guard (PR mode, default loop only).** Before entering the loop, the orchestrator must be in one of two accepted states so fix commits land where they belong: **standing on the PR's branch** (name match only — **no** `HEAD` freshness check, so a behind checkout still passes), or **an adopted build** (invoke `review-code pr <N>` — auto-detection matches `--head` by branch name, so a renamed local branch never reaches this guard on a bare invocation) tracking remote `origin` with merge ref `refs/heads/<PR branch>` (read from `branch.<name>.remote` / `branch.<name>.merge`, not `@{upstream}` — spoofable by a local-tracking ref) and `HEAD` exactly `$HEAD_SHA`. The fenced block below is extracted by `plugins/superheroes/lib/tests/test_review_code_branch_guard.py` (first `bash` fence after this paragraph). Adopted path only: the config leg proves tracking **`origin`'s** branch of that name with `HEAD` at the PR head — assuming the PR head lives in `origin` (same as `git fetch origin "$PR_BRANCH"` above); a fork PR whose head name collides with an `origin` branch is not distinguished. The SHA leg refuses a stale adopted copy and does **not** apply to the name path.

```bash
CURRENT_BRANCH=$(git symbolic-ref --quiet HEAD); case "$CURRENT_BRANCH" in refs/heads/?*) CURRENT_BRANCH=${CURRENT_BRANCH#refs/heads/};; *) CURRENT_BRANCH=;; esac
LOCAL_HEAD=$(git rev-parse HEAD); TRACK_REMOTE=$(git config --get "branch.$CURRENT_BRANCH.remote"); TRACK_MERGE=$(git config --get "branch.$CURRENT_BRANCH.merge")
case "$PR_BRANCH" in ""|null) echo "Auto-fix: pr.json has no head branch — refusing (fail closed)."; exit 1;; esac
case "$HEAD_SHA"   in ""|null) echo "Auto-fix: pr.json has no head SHA — refusing (fail closed)."; exit 1;; esac
if [ "$CURRENT_BRANCH" != "$PR_BRANCH" ] && ! { [ -n "$CURRENT_BRANCH" ] && [ "$TRACK_REMOTE" = origin ] && [ "$TRACK_MERGE" = "refs/heads/$PR_BRANCH" ] && [ "$LOCAL_HEAD" = "$HEAD_SHA" ]; }; then
  echo "Auto-fix needs the PR's branch '$PR_BRANCH' (currently on '${CURRENT_BRANCH:-<detached HEAD>}'). An ADOPTED build also qualifies, but only when ALL hold: this branch tracks remote 'origin' (found '${TRACK_REMOTE:-none}') and merge ref 'refs/heads/$PR_BRANCH' (found '${TRACK_MERGE:-none}'), AND HEAD is the PR head '$HEAD_SHA' (found '$LOCAL_HEAD')."
  echo "Otherwise check out the branch, or re-run with --post (read-only GitHub) or --review-only (read-only terminal)."; exit 1
fi
```

If the guard fails (detached HEAD, an unrelated branch, or you're reviewing someone else's PR), STOP — do not create the detached worktree and do not enter the loop. A **stale** adopted branch — right tracking config, wrong `HEAD` — refuses; the name path has no freshness check. Missing `pr.json` metadata (`$PR_BRANCH` or `$HEAD_SHA` empty or `null`) refuses fail-closed. Tell the user to use `--post` or `--review-only`. The detached `git worktree add --detach` step above is for the `--post`/`--review-only` PR paths ONLY, never for the auto-fix path. The auto-fix loop **never pushes**; an adopted build must push its fix commits itself with an explicit refspec — `git push origin HEAD:$PR_BRANCH` — because a bare `git push` from an adopted branch fails under git's default `push.default=simple` when the local branch name differs from its upstream (`fatal: The upstream branch of your current branch does not match the name of your current branch.`).

**Branch mode:**

```bash
BRANCH=$(git rev-parse --abbrev-ref HEAD); MODE=branch
HEAD_SHA=$(git rev-parse HEAD)
BASE_BRANCH=$(git symbolic-ref --quiet refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@'); BASE_BRANCH=${BASE_BRANCH:-main}   # branch mode: default branch NAME; the pipeline exits 0 even when symbolic-ref fails, so `|| echo main` inside it would be DEAD
REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || echo "local")

# No worktree, no prior comments — subagents verify against the current working tree
```

**Resolve the diff base to a PINNED REMOTE commit — BOTH MODES, ONCE, at session setup.** This block runs in PR mode and branch mode alike (it is not part of the branch-mode snippet above); PR mode sets `$BASE_BRANCH` from `baseRefName`, branch mode from `origin/HEAD`, and from here the two are identical. `$BASE_BRANCH` is only a branch *name*, and a worktree's local copy of that branch goes stale as a matter of course in multi-agent setups: three-dot diff walks back to `merge-base($BASE_BRANCH, HEAD)`, so a stale local base drags everyone else's already-merged work into the review as if this branch added it (#637 — observed live: ~6,600 contaminated lines against 2,931 real ones). Fetch through a **fully qualified refspec** (never the DWIM short name — a local branch or tag called `origin/<base>` would shadow it, and a nonstandard remote refspec can leave the fresh object only at `FETCH_HEAD`) and **pin the result to an immutable commit**. Run this block **exactly once per session**, never per round: remote-tracking refs are shared by every worktree of the repo, so re-running it mid-session would re-pin to whatever another agent has since pushed — the very drift the pin exists to prevent. In the fetch refspec, `${BASE_BRANCH}` is braced deliberately because an unbraced `$VAR` immediately before `:` is read by zsh as a history-style modifier (`:r`), which silently corrupts the refspec so fetch fails and the pin falls back to a stale remote-tracking ref—the same #637 class this block exists to prevent.

```bash
BASE_FETCH=fetched; git fetch --quiet origin "+refs/heads/${BASE_BRANCH}:refs/remotes/origin/${BASE_BRANCH}" \
  || BASE_FETCH="fetch-failed ($(git remote get-url origin >/dev/null 2>&1 && echo 'origin configured; fetch failed — unreachable, auth, or base branch absent on the remote' || echo 'no origin remote')); local-vs-last-fetched base divergence behind/ahead $(git rev-list --left-right --count "$BASE_BRANCH...refs/remotes/origin/$BASE_BRANCH" 2>/dev/null | tr '\t' '/' | grep . || echo unknown)"
BASE_REF=$(git rev-parse --verify --quiet "refs/remotes/origin/$BASE_BRANCH^{commit}") \
  || { BASE_REF=$(git rev-parse --verify --quiet "$BASE_BRANCH^{commit}"); BASE_FETCH="$BASE_FETCH; no-remote-ref — diffing the LOCAL base"; }
BASE_REF=$(git rev-parse --verify --quiet "$BASE_REF^{commit}") || { echo "review-code: base '${BASE_BRANCH:-<empty>}' did not resolve to a commit (BASE_FETCH=${BASE_FETCH}) — refusing to review (#637)" >&2; exit 1; }
```

**The base must RESOLVE TO A COMMIT — validated once at Setup, and every consumer uses the guarded command.** This is the only validation, and it is deliberately not a non-emptiness test: `$BASE_REF` reaching `git diff` as an empty string makes argv `...HEAD`, which git reads as `HEAD...HEAD` — a **zero-line diff at exit 0** the loop would certify clean — and reaching it as the literal string `null` (what `jq -r` prints for an absent key) passes any `[ -n … ]` check while `git diff null...HEAD` exits 128 and *still* leaves an empty `diff.txt`. `git rev-parse --verify --quiet "$BASE_REF^{commit}"` rejects both, plus a deleted branch and a non-commit tag. **Every** producer of `$BASE_REF` — the fetch/pin above, the local fallback, the `meta.json` restore below — routes through it; never add a second, weaker guard beside it, and never let a caller "recover" by substituting a branch name. On every auto-fix `next`, `round_driver.py` independently re-checks in code that the base is a *pinned commit id* and that the pin has not moved mid-session, refusing with `base-not-pinned`, `base-unresolved`, or `base-pin-moved` if not (see `reference/round-driver.md` § Base guard).

**Never diff a stale base silently.** Any `$BASE_FETCH` other than `fetched` is a **degradation** — name it in the dispatch summary, record it in `meta.json`, and surface it in the `--post` review body and the `--review-only` presentation *before* any finding is shown. Both modes assume `origin` is the base branch's repository — the same assumption the `git fetch origin "$PR_BRANCH"` above already makes; in PR mode the driver now refuses a fork whose PR base repository differs from `origin` with `base-repo-mismatch` (full fork *support* — resolving or fetching the base by URL — is still deliberately not built).

**Per-round diff — every round, against the pin.** This is the ONLY command that runs per round. Do NOT use `gh pr diff` (rounds 2+ have local fix commits that are not on the remote), and do NOT re-run the setup block above. On fresh state the round-1 artifact passed to the driver is refused in code (`round-diff-unreadable`, `round-diff-empty`, `round-diff-malformed`, `round-diff-required`); rounds 2+ rely on the shell halt above.

```bash
git diff "$BASE_REF"...HEAD > "$SESSION_DIR/round-<round>/diff.txt.tmp" && mv "$SESSION_DIR/round-<round>/diff.txt.tmp" "$SESSION_DIR/round-<round>/diff.txt" || { rm -f "$SESSION_DIR/round-<round>/diff.txt.tmp"; echo "review-code: git diff against $BASE_REF FAILED — refusing to review the artifact it left behind (#637)" >&2; exit 1; }
[ -s "$SESSION_DIR/round-<round>/diff.txt" ] || { echo "review-code: round diff against $BASE_REF is EMPTY — an empty review surface is never certifiable-clean; halt and investigate (#637)" >&2; exit 1; }
```

**If `$BASE_REF` is not in scope** — a resumed or compacted orchestrator, or a fresh shell — restore the pin from the session record rather than re-deriving it: `BASE_REF=$(jq -r '.baseRef // empty' "$SESSION_DIR/meta.json")`, then **re-run the resolve-to-a-commit check from the setup block** (`BASE_REF=$(git rev-parse --verify --quiet "$BASE_REF^{commit}") || exit 1`) before any diff. Use `// empty`, never a bare `.baseRef`: `jq -r` prints the literal string `null` for an absent key, which is non-empty and would sail past a naive check. Re-running the setup block instead would silently re-pin to a moved `origin/<base>`.

The read-only paths run a single pass and compute the same local diff into `round-1/diff.txt`.

Then write `meta.json` in both modes:

```bash
# The orchestrator sets FOCUS_JSON from the `--focus` argument (if any) before this block runs.
FOCUS_ARG=$(printf '%s' "${FOCUS_JSON:-}" | jq -cs 'if length == 1 and ((.[0]|type) == "object" or (.[0]|type) == "array") then .[0] else empty end' 2>/dev/null); [ -n "$FOCUS_ARG" ] || { [ -n "${FOCUS_JSON:-}" ] && FOCUS_ARG=$(printf '%s' "$FOCUS_JSON" | jq -Rs .) || FOCUS_ARG=null; }   # -s SLURPS, so the encoder can only ever emit ONE document: a lone JSON object/array rides through as JSON, and everything else (free text, a bare scalar, several documents, malformed JSON) becomes one JSON string via stdin — never a multi-document value --argjson would reject, and never a silently truncated note
PR_ARG=$(printf '%s' "${PR_NUMBER:-null}" | jq -cs 'if length == 1 and (.[0]|type) == "number" then .[0] else null end' 2>/dev/null); [ -n "$PR_ARG" ] || PR_ARG=null
jq -n --arg mode "$MODE" --arg path "$REVIEW_PATH" --arg repo "$REPO" --arg branch "$BRANCH" \
  --arg headSha "$HEAD_SHA" --arg baseRef "$BASE_REF" --arg baseBranch "$BASE_BRANCH" --arg repoRoot "$REPO_ROOT" \
  --arg baseFetch "$BASE_FETCH" --arg sessionDir "$SESSION_DIR" --arg verify "${VERIFY_CMD:-unverified}" \
  --argjson pr "$PR_ARG" --argjson focusNotes "$FOCUS_ARG" \
  '{mode:$mode,path:$path,pr:$pr,repo:$repo,branch:$branch,headSha:$headSha,baseRef:$baseRef,baseBranch:$baseBranch,baseFetch:$baseFetch,repoRoot:$repoRoot,sessionDir:$sessionDir,verify:$verify,focusNotes:$focusNotes}' \
  > "$SESSION_DIR/meta.json.tmp" \
  && mv "$SESSION_DIR/meta.json.tmp" "$SESSION_DIR/meta.json" \
  || { rm -f "$SESSION_DIR/meta.json.tmp"; echo "review-code: could not write meta.json — halting rather than continuing without the session record (#637)" >&2; exit 1; }
```

`REVIEW_PATH` is `loop` (default), `review-only`, or `post`, decided from the flags at invocation. It is written to `meta.json` so a cold-resumed orchestrator (after compaction) knows which top-level flow to continue. The `verify` field records the verify command string, or `"unverified"` / `"review-only"`, so a cold-resumed orchestrator recovers the verify story.

Size the round-1 diff for the dispatch summary (after writing it to `round-1/diff.txt` per the command above):

```bash
DIFF_LINES=$(wc -l < "$SESSION_DIR/round-1/diff.txt")
```

**CRITICAL:** The line count is the only thing the orchestrator needs to know about `diff.txt`'s contents — do not `cat`, `head`, `tail`, or otherwise read it from the main context.

### 2. Dispatch Summary

Print this dispatch summary as a plain status message, then dispatch the specialists immediately (no approval gate):

- **Skill:** `review-code`
- **Mode:** PR or branch
- **Target:** `PR #<N> "<title>"` (PR mode) or `<branch> vs <baseRef>` (branch mode) — `<baseRef>` is the **pinned base commit**; when `$BASE_FETCH` is not `fetched`, state that degradation here
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

On every `next` whose `phase` starts with `dispatch-`, `round_driver.py` **emits** each roster seat's complete order before you dispatch anything: one markdown file per slot, an envelope stub carrying the full known `seat-result/1` header, and a manifest hashed into the session anchor. **Dispatch the emitted order text** — do not hand-compose prompts from templates. Per-seat engine/channel mechanics (stdout vs file, `dispatch-review` runner, canary probes) live in `reference/auto-fix-loop.md`; the prompt bodies live in `rubric/orders/<phase>.md` and are rendered into the session by the driver.

**Where the files are (round `<N>`, phase `<phase>`, attempt `<K>`, storage key `<skey>` — the filename-safe key the manifest uses, not the bare reviewer name):**

| Artifact | Path |
| --- | --- |
| Order (dispatch this) | `$SESSION_DIR/round-<N>/orders/<phase>/<skey>.a<K>.md` |
| Envelope stub (header fields the seat must copy verbatim) | `$SESSION_DIR/round-<N>/orders/<phase>/<skey>.a<K>.envelope.json` |
| Orders manifest (every slot's `orderPath`, `envelopeStubPath`, hashes) | `$SESSION_DIR/round-<N>/orders/<phase>/manifest.a<K>.json` |
| Landing — **engine** seat (`codex`/`cursor`) | `$SESSION_DIR/round-<N>/landing/<phase>/<skey>.a<K>.json` — **orchestrator** writes the **full envelope** (stub header + payload) from the folded `dispatch-review` stdout result; the engine seat emits JSON on stdout only (read-only sandbox) |
| Landing — **host** seat (`claude` native subagent) | `$SESSION_DIR/round-<N>/landing/<phase>/<skey>.a<K>.payload.json` — write **only** the payload; copy every stub header field verbatim into the ingested envelope |

No seat is ever asked to transcribe an `orderSha256`, `manifestSha256`, or storage path — those ride in the stub the driver emitted. After landings exist, either **`record-result` (or `record-missing`) + `advance`**, or a hand **`submit`** — **mutually exclusive, per SESSION** (the first path used is the path the session keeps; see `reference/round-driver.md` § Durable-record path).

Launch the round's scheduled specialists (round 1: all five) **by channel** — see `reference/round-driver.md` § Batch concurrency. **Native-subagent** seats (a `claude` seat) go out as **parallel dispatches in one message**; the harness runs them concurrently and owns their lifecycle. **External-engine** seats (`codex`/`cursor`, through `dispatch-review`) each get their own `--run-dir` (**the runner creates it** on first `dispatch-review`; keep `--progress-file` and result JSON **outside** the run dir or get `run-dir-not-empty-unopened`; continuation reuses the same dir), are launched with a short positive slice, then the originating verb is re-invoked on every non-terminal run in rotation until each is terminal — issuing those calls together in one message does not make them concurrent. Dispatch each seat through **its seat-map-assigned engine+model** (`$SEAT_MAP.seats[<reviewer>]` → `.vendor`/`.model`): a `claude` seat runs the named subagent at its tier model with the **order file contents** as the prompt; a `codex`/`cursor` seat dispatches through `engine_dispatch.py dispatch-review` (read-only sandbox) with that seat's resolved `.model`. An unreadable or missing slot is the same `cannot-certify` signal, re-run on Claude (UFR-7). On the hand path, submit the panel with `ranManifest: {<dim>: <vendor>}` built from your OWN dispatch records **and** the composed `$SEAT_MAP` JSON as `seatMap`. Per-seat dispatch + grounding-seat detail: `reference/auto-fix-loop.md`.

**Per-agent substitutions** (reviewer name → findings filename stem → dimension label):

| reviewer | `<agent>` (findings filename) | `<dimension>` |
| ---------------------------- | ----------------------------- | ------------- |
| architecture-reviewer        | architecture                  | Architecture  |
| code-reviewer                | code                          | Code          |
| security-reviewer            | security                      | Security      |
| test-reviewer                | test                          | Test          |
| premortem-reviewer           | premortem                     | Failure-Mode  |

After dispatch, wait for all five agents to return. **Codex/cursor seats** run the native `dispatch-review` `--run-dir` + `--max-wait 540` continuation loop until terminal; **claude seats** are native subagents with their own lifecycle (the `await-dispatches` ruling's native-subagent exemption — the runner cannot dispatch them). The in-place fixer stays foreground by design (not an oversight). The **hand-rolled engine fallback** (`auto-fix-loop.md`) does not follow that native shape and still owes the limitation disclosure when used. No native-shape limitation disclosure is owed for seats dispatched through the runner or as claude native subagents under this skill. This skill owns the **bounds** of its own dispatches; the builder's `await-dispatches` rule owns the **channel** for what the builder launches. Full contract: `reference/auto-fix-loop.md` (Settled dispatch contract).
A file-channel seat's findings are read from `$SESSION_DIR/round-<round>/findings-<agent>.json`; a stdout-channel seat's findings come from the terminal `dispatch-review` result, which the orchestrator folds. The orchestrator reads only those structured outputs, never agent transcripts.

### 4. Compile + Dedupe (main context)

On the **read-only paths** (`--post`, `--review-only`), the orchestrator compiles in main context — a **prose-driven review** (sanctioned lane; not a shortcut and not available inside the auto-fix loop). It owes a substitute receipt instead of the driver's `round-receipt.json`: the dispositions table plus the durable receipt the workhorse charter requires (`skills/workhorse/SKILL.md` §10 — link review results on the PR). Branch mode has no PR: write both to `$SESSION_DIR/dispositions.md`; when the branch later becomes a PR, that file's content is what the PR body carries. Full contract: `rubric/review-discipline.md` § Prose-driven review.

On the **auto-fix loop**, compile is driver-owned — obey `next`/`submit` instead of reimplementing compile by hand.

Collect findings (read-only path only) from file-channel seats at `$SESSION_DIR/round-<round>/findings-*.json` and from stdout-channel seats via their folded `dispatch-review` results. Apply, in order:

1. **Citation check.** Drop any finding with `file == null` or `line == null`.
2. **Diff-scope verification.** Parse `$SESSION_DIR/round-<round>/diff.txt` for `+`/`-` anchor lines (same hunk-walking as `resolve_diff_lines.py`). Drop out-of-scope findings.
3. **Reachability pre-check (read-only path only).** For each remaining `severity == "Important"` finding, confirm the edge case is reachable; when in doubt, downgrade to Minor rather than drop.
4. **Dedupe by `(file, line)`.** Merge same-anchor findings: higher severity wins, dimensions unioned, stable `file::normalized-title` identity, `tradeoff: true` if either input is.
5. **Nit cap.** After dedupe, keep at most 5 Nits; overflow collapses to one summary entry.
6. **Per-finding verification + synthesis merge** (never the session model). Stage ids, cluster, dispatch one verifier per cluster (`model: $VERIFIER_MODEL`, reviewer engine; #230 immunity), apply `verification.apply_verdicts`, then one synthesis judge (`model: $SYNTH_MODEL`) groups root causes and `verification.merge_and_rank` merges under a coverage guarantee — synthesis drops nothing. Full contract: `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/review-code/reference/verification-pass.md`.
7. **Author-justification post-filter (PR mode only, after verification).** Cross-reference `prior-comments.json`. May drop **only** a finding whose verifier `verdict` is present and not **CONFIRMED**, recording the prior justification quoted. A **CONFIRMED** finding with a prior justification **survives**, stamped `challenge: "author-justified"` (ledger-visible). A finding with no verdict is never dropped here. Rules: `round-driver.md`.
8. **PR-body honesty check (PR mode only).** From `pr.json`'s `body`, the review seat also verifies the PR body carries a valid **DoD disposition table** (the `superheroes:dod-table` marker) against the issue/spec — one row per Definition-of-Done bullet, each `done` (with an evidence pointer) or `deferred` (with a filed issue `#NNN` and a one-line reason). Append an **Important** finding (cited at the PR body, `tradeoff: true`, author-resolved — it is a judgment call the author closes by writing the table, not a mechanical fix) when the table is missing, or a row's evidence or deferral is empty or hollow. A **missing** `<!-- superheroes:build-record -->` boundary marker or a **missing** `<!-- superheroes:degradations -->` section is the same finding shape — not a silent pass; an empty degradation list is only clean when that section says the literal **None** (absence and **None** differ). The seat also checks the owner half (above `<!-- superheroes:build-record -->`) under `## What we're accepting` carries the **omission floor** (CONVENTIONS §10.7): enumerate (1) each deferred DoD row, (2) each blocking or important dispositions-table finding not fixed (by severity, not disposition label), and (3) each disclosed degradation under `<!-- superheroes:degradations -->` (bullets, or **None** when empty) — each must have a matching consequence line in that section; same **Important** / `tradeoff: true` / author-resolved finding when one is missing. Branch mode has no PR body — skip. Contract: CONVENTIONS `§10.7`, `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/rubric/review-discipline.md`.

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

Runs when neither `--post` nor `--review-only` is set, and the profile's verify story is not `mode: review-only`. The loop is **driver-owned**: every per-round step is `python3 -B "$ROOT_DIR/lib/round_driver.py" next|submit` — the old `code_loop_plan` plan/record/decide, the manual `circuit_breaker.py` call, and the head-diff step all collapse into obeying `next`. Full contract: `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/review-code/reference/round-driver.md`.

**If context was compacted mid-loop**, re-read `$SESSION_DIR/meta.json`, `$SESSION_DIR/loop-state.json`, and `$SESSION_DIR/driver-journal.jsonl`. Resume by calling `next` — a pending step re-emits idempotently.

**Bootstrap.** `mkdir -p $SESSION_DIR/round-1`. Regenerate the diff **with the guarded per-round command from Setup** — the same `git diff "$BASE_REF"...HEAD` plus its failed-diff and empty-diff halts, never a bare copy; if `$BASE_REF` is not in this shell, restore and re-validate it first (Setup, "If `$BASE_REF` is not in scope"). Size it with `wc -l` only. First `next` seeds state. Pass **`--vendors`** — the live reviewer/fixer vendors, either a JSON list (`["codex","cursor"]`) or a comma-separated string (`codex,cursor`) — so the driver can seat a **different** auditor vendor for each fix (independent audit). Also pass **`--fixer-vendor`** — the **actual** fix-implementer vendor (`$IMPL_ENGINE` from the calibration / engine resolution) — so the auditor is seated as a **different** vendor than the one that fixed; omitting it leaves the fixer identity **unknown**, which now fails toward a disclosed **degraded** audit (never silently mislabeled independent) — so always pass it when a real fixer vendor is known. An unparseable value, an unknown vendor, or either flag on non-fresh state **fails loud** (nonzero exit + `{"ok": false, "reason": ...}`) — never a silent default. **Omitting `--vendors` degrades every run to the single vendor `["claude"]`:** the audit still runs but independence is **lost** and every terminal is stamped `-degraded` (e.g. `audited-chain-degraded`) — reserve that only for an environment that genuinely has one usable vendor. In PR mode also pass **`--prior-comments`** (the author-justification post-filter reads it; ignored when the file is absent):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
# Live vendors from the seat map (family-aware; #510) — the pool the driver seats independent
# fix-auditors from; falls back to the reviewer+impl engines if the seat map is unreadable.
VENDORS=$(echo "$SEAT_MAP" | python3 -B -c 'import json,sys; d=json.load(sys.stdin); print(json.dumps(sorted(d.get("liveVendors") or [])))' 2>/dev/null || python3 -B -c 'import json,sys; print(json.dumps(sorted({v for v in sys.argv[1:] if v})))' "$REVIEWER_ENGINE" "$IMPL_ENGINE")
SEAT_MAP_ARGS=()
if [ -n "$SEAT_MAP" ] && echo "$SEAT_MAP" | python3 -B -c 'import json,sys
d=json.load(sys.stdin)
sys.exit(0 if isinstance(d, dict) else 1)' 2>/dev/null; then
  printf '%s' "$SEAT_MAP" > "$SESSION_DIR/seat-map.json"
  SEAT_MAP_ARGS=(--seat-map "$SESSION_DIR/seat-map.json")
fi
python3 -B "$ROOT_DIR/lib/round_driver.py" next \
  --session-dir "$SESSION_DIR" \
  --diff-path "$SESSION_DIR/round-1/diff.txt" \
  --verify-command "${VERIFY_CMD:-none}" \
  --vendors "$VENDORS" \
  --fixer-vendor "$IMPL_ENGINE" \
  --prior-comments "$SESSION_DIR/prior-comments.json" \
  --max-rounds 7 \
  "${SEAT_MAP_ARGS[@]}"
```

Round 1 is the round that dispatches the panel, and without the seat map no round-1 seat's vendor resolves, so every seat falls back to the safe stdout contract and the orchestrator must land each payload itself; passing the map keeps native seats on the direct-write path and records real vendor provenance (#1035). The guard above only passes `--seat-map` when `$SEAT_MAP` is non-empty and parses as a JSON object, so a genuinely empty/unset `$SEAT_MAP` never gets written to a file and handed to the driver.

**The loop.** Until `action` is `terminal`:

1. Parse `next` JSON: `{action, round, phase, attempt, expectedStateHash, payload}`.
2. **Dispatch exactly one action** (panel, verifiers, synthesis, gap-sweep, audits, scoped-finder, verify, fixer, judgment gate, or stall menu) — one **driver phase**; when that phase is panel, verifiers, or audits, fan its members out per `reference/round-driver.md` § Batch concurrency — every other phase is fulfilled once. Round 1 = full `reviewer-deep` panel; rounds 2+ = delta rounds (fix audits + scoped finder) unless the driver schedules a full panel (#174 re-arm or unknown surface → run-everything). Degraded/single-vendor: same driver, same journal, `independence: "degraded"` stamps — stay on the path. **Fold path:** roster-bearing `dispatch-*` phases may use the durable-record path (`record-result` / `record-missing` + `advance` per `reference/round-driver.md` § Durable-record path) **or** the hand path (compile artifact + `submit`); owner gates (`present-judgment`, `present-stall-menu`) fold by hand `submit` on a hand-path session and by `advance --owner-artifact` on an advance-path session. The two fold paths are mutually exclusive per session (see §3 above).
3. **Durable-record path:** write each seat's landing (orchestrator writes engine-seat landings from folded `dispatch-review` stdout), then `record-result` / `record-missing` + `advance` — no hand `submit`. **Hand path:** write the artifact JSON, then `submit` with echoed `phase`, `attempt`, and `expectedStateHash`.
4. On `present-judgment` (a tradeoff/product-choice blocker — an **intervention gate, not a terminal**), present each `payload.findings[]` with its `dispositions` (`fix-as-suggested`, `fix-with-guidance`, `skip`) and submit `{dispositions: [{id, disposition, guidance?, reason?}, ...]}` — `skip` needs a citable `reason`; the driver folds fixes back into the fix leg and rides skips on the exit disclosure (fail-closed: a missing/unknown disposition folds as `fix-as-suggested`). On `present-stall-menu` (the audit-stall **owner gate** — reached only after one invisible self-recovery, **not** a terminal), present `payload.choices` — the current stall vocabulary (`one-more-round`, `accept-the-disclosed-risk`, `hold`); `accept-the-disclosed-risk` only when `payload.acceptRiskEligible` (a stalled audit target that is CONFIRMED with evidence); `one-more-round` only when it appears in `payload.choices` (once per session). `hold` → terminal `held`. `one-more-round` → not a terminal; re-enters `dispatch-fixer` → `dispatch-audits`. Never judge the dispute yourself.
5. On `terminal`, read `payload.certification` and `round-receipt.json`; map `verdict` to `$ACTION`/`$REASON` for `--result-file` (`converged` → `exit_clean`; `halted`/`held`/`stalled`/`capped-with-open-critical` → `halt`).

```bash
python3 -B "$ROOT_DIR/lib/round_driver.py" submit \
  --session-dir "$SESSION_DIR" \
  --phase "<phase>" --attempt <attempt> \
  --state-hash "<expectedStateHash>" \
  --artifact "$SESSION_DIR/round-<N>/<phase>-artifact.json"
```

**Terminals to surface honestly:** scoped certifying finish (`audited-chain` / `audited-chain-degraded` — say so, never imply a pristine fresh pass); one invisible self-recovery on audit-stall (journaled, not offered to the owner); the audit-stall stall menu; owner-skipped judgment blockers (ridden on the exit disclosure — a product-choice tradeoff shipped un-fixed, cited by its owner reason); `capped-with-open-critical` park when confirmation budget is exhausted with a Critical still owed.

**Red flags** — if you catch yourself thinking "trivial fix / obviously clean / save tokens / offer another round as optional", call `next` and obey the driver instead.

### Fixer subagent prompt

The fixer subagent prompt template (including the escalation-guard context) is in `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/review-code/reference/auto-fix-loop.md`. Embed `ESC_WRAPPER` and `REPO_ROOT` (absolute) into the fixer prompt's `## Input` block. On `dispatch-fixer`, submit `headDiff` and `changedSubjects` derived from git via the **guarded** per-round command in Setup (`git diff "$BASE_REF"...HEAD` against the pinned base commit, with its failed-diff and empty-diff halts), never the fixer's self-report.

### End-of-Loop Summary

**If `--result-file` was passed**, write the terminal loop_state decision before printing the summary (atomic write via temp file):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -B "$ROOT_DIR/lib/review_result.py" write \
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
- **`mode: unverified` →** there is no verify command. SKIP the verify gate (step 12); tell the fixer to skip checks (verify command `"none"`); commits proceed ungated. State "unverified" in the dispatch summary and the End-of-Loop summary.
- **`mode: review-only` →** the project opted out of auto-fix. The default path degrades to a single review pass + the `--review-only` presentation (no triage, no fixer, no commits, no loop). Note this in the dispatch summary.

`meta.json` records the verify story (`verify`: the command string, or `"unverified"` / `"review-only"`) so a cold-resumed orchestrator recovers it without re-reading the profile.

## Learning Loop & Staleness Nudge

For recurrence handling, coverage decisions, dimension skipping, tier cascade, final confirmation, and telemetry, use `plugins/superheroes/reference/review-loop.md` as the shared loop contract. This skill owns only its leg-specific setup, reviewer framing, and gate-write rules. The subagent prompt templates, verification rules, and common mistakes for this skill are in `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/review-code/reference/auto-fix-loop.md`.
