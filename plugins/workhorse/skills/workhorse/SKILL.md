---
name: workhorse
description: Use when an approved tasks doc (gates.review == passed) should be BUILT and shipped to a ready-for-review PR — "run the producer", "build this work item", "take this to a PR", "workhorse it". The per-issue back-half engine: it builds (subagent-driven-development), reviews (review-crew:review-code), opens a draft PR, exercises the change (test-pilot), resets seeded data, gets CI green, and hands you a live dev server + a plain-language readout. It NEVER merges — that is always yours.
---

# Workhorse — the producer (back-half engine)

You are the **producer**: you take ONE approved work item from `tasks` to a
**CI-green, ready-for-review PR** + a **live dev server** + a **"your turn"
readout**. You **never merge, deploy, release, or force-push** — those are the
owner's, and a deterministic enforcer guarantees it.

Resolve the plugin lib dir once: `LIB="${CLAUDE_PLUGIN_ROOT}/lib"`.

**Prerequisites (install the band first).** Workhorse resolves its sibling band
plugins' bundled libs at runtime, so install **the-architect ≥ 0.3.0**,
**review-crew ≥ 0.6.0**, and **test-pilot** alongside workhorse. If they're absent,
the ⓪ self-check reports `escalation_resolved: false` / `armed: false` and refuses
to run — by design (never run the floor unguarded), not a mid-build failure. If you
see `armed: false`, confirm the band siblings are installed before retrying.

## ⓪ Startup self-check + worktree (refuse to run unguarded)

1. **Enforcer self-check (HARD GATE) — config + per-matcher canaries.** First run
   `python3 "$LIB/enforcer.py" selfcheck`; if it exits non-zero (`armed: false`),
   STOP — read the JSON to say WHY: `classifier_ok:false` (deny-list broken),
   `escalation_resolved:false` (the Edit guard can't find escalation.py — a broken
   install that would otherwise wedge ① Build with misdirecting per-edit denials), or
   `hook_config:false` (hooks.json missing). Then run an **end-to-end canary on EACH
   registered matcher** (the hook registers two — `Bash` and `Edit|Write|MultiEdit` —
   and they can load independently; a canary on one does not prove the other):
   - **Bash surface:** issue the harmless no-op `: workhorse-enforcer-canary` through
     the **Bash** tool. The enforcer's deny-list includes that sentinel; if the hook
     is firing the call is **blocked**.
   - **Edit surface:** attempt to **Write a sentinel canary path whose basename is a
     safety-machinery member but which does NOT exist** —
     `${CLAUDE_PLUGIN_ROOT}/lib/loop_state.py` (workhorse has no such file; its basename
     is in `SAFETY_MACHINERY` and it resolves under the workhorse band root, so the
     enforcer must deny it). If firing, it's **blocked**. Targeting a non-existent path
     (rather than rewriting the real `hooks.json`) means that even if the matcher is dead
     and the Write executes, it only creates a **harmless stray file** — never corrupts a
     real safety file — and the orchestrator deletes the stray when it detects the write
     went through.

   If **either** guarded action **executes** instead of being denied, that matcher is
   NOT active — the floor is silent on that surface (e.g. the ⑧ CI-fixer's edits would
   be unguarded) — so **STOP and refuse to run** (tell the owner to reinstall/enable the
   workhorse plugin). The on-disk `selfcheck` can't prove the host loaded the hooks;
   these canaries are what actually prove the floor is live on both surfaces before any
   guarded action runs.
2. **Input precondition.** The input is a `tasks` definition-doc whose
   `gates.review` is `passed`. Read it with the-architect's lib:
   `python3 <the-architect>/lib/definition_doc.py read-gate --doc tasks
   --work-item "$WORK_ITEM" --root "$ROOT"`. If it is not `passed`, STOP (GATE):
   the work isn't approved to build.
3. **Worktree + content-addressed branch.** The producer owns worktree creation
   (CONVENTIONS §3.2). Mint the branch
   `superheroes/<work-item>-<content-hash>` using the-architect's
   `lib/identifiers.py:content_hash(frontmatter, body)` over the approved tasks
   doc (stable fields only). Establish/verify a clean worktree on that branch and
   pre-verify it's clean.

## ① Build — subagent-driven-development (CLIPPED)

Invoke superpowers `subagent-driven-development` to execute the tasks doc,
**clipped** per CONVENTIONS §3.2: the worktree is **pre-made** (do NOT create
one) and you **stop before** `finishing-a-development-branch`. Build keeps
SDD's own Model Selection heuristic. A `BLOCKED` status → GATE.

## ② Review — review-crew:review-code (deterministic terminal read)

Run the review-code auto-fix loop on the branch, capturing its terminal state to
a result file:

```
RESULT="$(mktemp)"
# invoke: /review-crew:review-code --result-file "$RESULT"
python3 <review-crew>/lib/review_result.py  # (the reader; or read $RESULT directly)
```

Read `$RESULT` (via `review_result.read_result`). Branch on `action`:
- `exit_clean` → continue.
- `exit_skipped` (a blocking finding was deliberately skipped) → **GATE**: surface
  the skipped blocker; do not ship it silently.
- `halt` (circuit breaker / round cap) → **GATE**.
- missing/garbled → reads as `halt` → **GATE** (fail-closed).

**Version-skew diagnostic.** `$RESULT` is empty only when review-code did not write
it — most likely an installed review-crew that predates `--result-file`. So when the
file is **empty/unwritten** (distinct from a written `halt`), GATE with a *specific*
message — "review-code did not report a terminal state; your installed `review-crew`
may predate `--result-file` (upgrade it)" — rather than a bare halt, so the owner can
fix the cause instead of seeing an unexplained GATE every run.

## ③ Draft PR (NOTIFY) — world-read before world-write (idempotent)

**First world-READ, then world-WRITE** (this is what makes the step compaction-safe
by construction — on a re-entry after compaction it must NOT open a second PR):
run `gh pr list --head "$BRANCH" --json number,state,isDraft`. If a PR already
exists for this branch, **adopt it** (capture its number; if it's already non-draft,
note that and skip the open) — do not create another. Only when none exists: push the
branch and open a **draft** PR (`gh pr create --draft …`), then capture the number.
Reversible → **NOTIFY** (report the link in the readout). The enforcer permits `gh pr
create`/`git push` (non-force); it refuses `gh pr merge`.

## ④ Dev server (managed) — only when there's a runnable surface

Detect the dev-server command: `python3 "$LIB/detect.py"` (`detect_dev_server`).
None detected → no spot-check server; note it and skip ④⑤⑥. Otherwise start it
managed via `devserver.start(command, port)` (`devserver.py`), health-poll `devserver.health_url`,
capture the handle. **Tear it down (`devserver.teardown`) on every terminal
state, GATE, or error** — no zombie. One server serves ⑤ and the ⑨ spot-check.

## ⑤ Behavioral — test-pilot (two skills) — runnable surface only

Invoke `test-pilot-plan` (seeds scenarios via test-pilot's `engine.py`, posts the
checkbox plan comment to the PR via `pr_comment.py`) then `test-pilot-execute`
(drives the UI, posts the results comment). Workhorse supplies the PR number (③)
and the live dev server (④); it does NOT re-implement seeding or PR posting. A
failure it can fix → fix + re-verify; else → GATE.

## ⑥ Reset — engine clean (state-scoped, protected-gated)

Regardless of ⑤ pass/fail, reset the seeded data via test-pilot's engine (`reset.py`):
1. `python3 <test-pilot>/lib/engine.py status --json` → feed to
   `reset.plan_reset(status)`.
2. `clean` → `engine.py clean --branch "$BRANCH" [--slot S] --json`; then
   re-`status` and assert `reset.verify_empty(status)`.
3. `unlock_then_clean` (stale lock) → `engine.py unlock --json`, then clean.
4. `gate` (live lock held, or unreadable status) → GATE; never claim a clean
   baseline you didn't achieve. **Never pass `--allow-protected`** — that is the
   owner's call (the engine's protected-target gate refuses production-shaped
   targets, by design). *(Residual, deferred: test-pilot's stale-lock detection
   uses `os.kill(pid, 0)`, which a reused PID can spoof, so a lock orphaned by a
   hard kill could read live-and-GATE. Surfacing it honestly to the owner is correct
   here; the durable stale-lock reclaim is the resilience slice — §5.)*

## ⑦ Ready — world-read before world-write (idempotent)

Once ⓪–⑥ are clean, **read the PR's current state first** (`gh pr view <N> --json
isDraft`): if it is already non-draft, this step already ran (a prior pass /
pre-compaction) — note it and continue. Only when it is still a draft: flip it
(`gh pr ready <N>`) (NOTIFY). The read-before-write keeps re-entry from churning the
PR state.

## ⑧ CI-green gate — bounded fix loop

Wait on the PR's checks **whenever CI runs** (this repo's CI runs on drafts):
`gh pr checks <N>`. Detect the provider with `detect.detect_ci`; **none →** the
readout says **"CI not detected"**, never a false ✓.
- Green → continue.
- Red → derive the failing-check signatures, call
  `ci_loop.decide(failing, history, rnd)` (`ci_loop.py`):
  - `fix` → fix + push + re-wait (append this round's signature to `history`).
  - `revert_and_gate` (cap reached / recurring set / no actionable failures) →
    `gh pr ready --undo <N>` (revert to draft) + **GATE**.

## ⑨ Handoff — your turn

Dev server still up on a clean baseline. Build the readout with
`readout.build_readout(ctx)` (`readout.py`) (live URL, built-vs-acceptance, test-pilot results,
CI status, PR link, smoke checklist). Pass a `ctx` dict with keys `pr_url`,
`dev_url`, `ci_status`, `built_vs_acceptance`, `test_results`, `smoke` (list),
`raw_ci_excerpt`, and **`root`** — set `root` to the repo root
(`git rev-parse --show-toplevel`) so the scrub seam can resolve test-pilot's
`pr_comment.py` in-repo; without it, scrub falls back to the installed cache only.
Any raw CI-log excerpt passes through the scrub seam (`readout.scrub`, backed by
test-pilot's `pr_comment.py scrub`; unscrubbable → dropped). End with
**"Merge is yours — Workhorse never merges."**

## Escalation (F5) + the deterministic floor

Route every seam through F5 (review-crew's `escalation_resolve.py`): **PROCEED**
(routine+reversible), **NOTIFY** (reversible, surfaced in the readout), **GATE**
(owner-weighable / irreversible-or-uncertain / hard-floor). The cooperative layer
routes the UX; the **PreToolUse enforcer** (`enforcer.py`, self-checked in ⓪)
guarantees the floor regardless of judgment — `gh pr merge` (incl. the `gh api`/
GraphQL forms) / `gh release create` / `gh workflow run` / `git push --force` /
deploy / destructive are **denied**, and edits to band safety-machinery are
**refused**.

**Scope of the deterministic floor (explicit).** The enforcer's command deny-list
covers the named *irreversible, repo-shaping* classes above — deliberately NOT the
softer `spend`/`egress` heuristics F5's `classify_floor` also carries (those are
broad and false-positive-prone on a build agent: a command merely mentioning
`stripe`/`upload` isn't an action). Those classes stay on the **cooperative F5
layer** (a GATE via `escalation_resolve`), not the hard hook. This is the design's
two-layer split, made explicit here so the boundary is a deliberate choice, not a
gap.

## Supervised assumption — park safely on a GATE

Workhorse is a supervised single session. If a GATE fires and the owner is away,
**park safely**: tear down the dev server, run ⑥ reset (clean baseline), leave the
PR as **draft**, and wait — never wedge with live resources. If a parking step
fails (e.g. a held engine lock), **report the partial state honestly** rather than
assert a baseline that doesn't hold. (Durable/unattended resume is the resilience
slice; cross-issue queueing is the coordinator's — both out of scope here.)

## Applicability

④⑤⑥ run as one unit **only when the change has a runnable surface**. A
library/CLI change skips to ②③⑦⑧⑨ (PR + CI + readout, no server).
