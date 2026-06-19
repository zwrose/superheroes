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

## ⓪ Startup self-check + store bootstrap + resume reconcile (every run — first or resume)

Run this exact sequence on **every** entry — whether fresh or resuming after
compaction / restart. The control-plane and resilience substrate are initialized
here so every subsequent step is already fenced and journalled.

### ⓪.0 Resolve env + control-plane store

Set `LIB="${CLAUDE_PLUGIN_ROOT}/lib"`. Resolve `ROOT=$(git rev-parse
--show-toplevel)` and `WORK_ITEM` (the work-item slug — from frontmatter or caller
context).

**Store bootstrap (startup lock).**
`control_plane.ensure_store(ROOT)` → `None` ⇒ **park-GATE**:
"durable store unusable — fail closed". Then acquire the startup lock:
`lock.acquire_startup(store)` → `(False, …)` ⇒ **fail closed**
("another loop holds this checkout — will not start a parallel run").

### ⓪.1 Work-item ref-lease

`lock.acquire(store, WORK_ITEM)` → `(ok, generation, reason)`:
on `ok` (reason `created`/`stolen`) record the returned `generation` and emit
`lease_acquired`/`lease_reclaimed`; on ANY non-ok result — `held`, or a
`lost-create-cas`/`lost-steal-cas` CAS race — **GATE** (fail-closed: cannot confirm
exclusive ownership; do not run two loops on one work-item).

`control_plane.set_current(ROOT, WORK_ITEM)`.

### ⓪.2 Re-arm the floor (bounded retry → parked-GATE)

Run the enforcer self-check and both per-matcher canaries. This runs on **every**
entry because resumes frequently re-enter adjacent to a guarded step (③/⑤/⑥/⑦/⑧)
and the floor must be live before any write.

1. **Enforcer self-check (HARD GATE).** `python3 "$LIB/enforcer.py" selfcheck`;
   non-zero (`armed: false`) → STOP. Read the JSON to say WHY:
   `classifier_ok:false` (deny-list broken), `escalation_resolved:false` (Edit guard
   can't find escalation.py — broken install), or `hook_config:false` (hooks.json
   missing).
2. **Bash surface canary.** Issue the harmless no-op `: workhorse-enforcer-canary`
   through the **Bash** tool. The enforcer's deny-list includes that sentinel; if the
   hook is firing the call is **blocked**.
3. **Edit surface canary.** Attempt to **Write** a sentinel canary path whose basename
   is a safety-machinery member but which does NOT exist —
   `${CLAUDE_PLUGIN_ROOT}/lib/loop_state.py`. If firing, it's **blocked**. A stray
   file created by a dead hook is deleted immediately.

Drive the disposition with **`recover.rearm_action(attempt, armed)`**
(`recover.py`): returns `proceed` / `retry` (attempts 1–2) / `park_gate` (the 3rd
attempt). A persistent floor-arm failure is a **parked-GATE** — tear down cleanly and
surface; never resume unguarded, never silent-wedge.

### ⓪.3 Reconcile world → resume or start fresh

Gather world reads:
- `store_ok` — True (store bootstrapped above).
- `current_content_hash` — recompute via the-architect `identifiers.content_hash`
  over the *current* approved tasks doc (unreadable ⇒ `None`).
- `pr` — `gh pr list --head "$BRANCH"` (failed/garbled read ⇒ `"unknown"`). `BRANCH` is the deterministic content-addressed branch (`superheroes/<work-item>-<content-hash>`) derived from the tasks doc and can be computed up front, so this world-read is well-defined before worktree creation.
- `seeded_empty` — test-pilot `engine.py status` (unreadable ⇒ `"unknown"`).
- `ci`, `dev_server`.

Establish paths: `paths = control_plane.paths(ROOT, WORK_ITEM)` returns a dict with
keys `checkpoint`, `events`, `resume_brief` (and others); bind `events = paths["events"]`
here — this is the file path used by all `journal.append(events, …)` and
`journal.ci_attempts(events)` calls below.

Call `recover.reconcile(checkpoint.read(paths["checkpoint"]), world)` (`recover.py`,
`checkpoint.py`, `control_plane.py`). Branch on `action`:
- `park_gate` / `gate` → surface and park.
- `world_derive` → proceed with no cursor (today's fresh-start behavior).
- `continue` → resume from `from_step` (skip already-completed steps).

Write `journal.render_brief(...)` (`journal.py`) and emit a `resumed` event
(always — even on a fresh start, this anchors the journal).

(Preview: step ③ will use **`recover.pr_action(world)`** (`recover.py`) — adopt an existing PR / create exactly one / gate a merged-or-unknown read — the exactly-once PR anchor as code, not judgment.)

**Input precondition (HARD GATE).** Read the tasks doc gate:
`python3 <the-architect>/lib/definition_doc.py read-gate --doc tasks
--work-item "$WORK_ITEM" --root "$ROOT"`. If not `passed`, STOP.

**Worktree + content-addressed branch.** The producer owns worktree creation
(CONVENTIONS §3.2). Mint the branch `superheroes/<work-item>-<content-hash>`
using the-architect's `lib/identifiers.py:content_hash(frontmatter, body)` over the
approved tasks doc. Establish/verify a clean worktree on that branch.

## ① Build — subagent-driven-development (CLIPPED)

Emit `journal.append(events, "step_entered", step=1, world={…})` at entry and
`journal.append(events, "step_completed", step=1, world={…})` on success; write
`checkpoint.write(…, phase="build", lastGoodStep=1, lockGeneration=generation)`.

Invoke superpowers `subagent-driven-development` to execute the tasks doc,
**clipped** per CONVENTIONS §3.2: the worktree is **pre-made** (do NOT create
one) and you **stop before** `finishing-a-development-branch`. Build keeps
SDD's own Model Selection heuristic. A `BLOCKED` status → GATE.

## ② Review — review-crew:review-code (deterministic terminal read)

Emit step_entered/step_completed journal events; write checkpoint.

Run the review-code auto-fix loop on the branch, capturing its terminal state to
a result file:

```
RESULT="$(mktemp)"
# invoke: /review-crew:review-code --result-file "$RESULT"
# then read the terminal action — fail-closed (missing/garbled/unknown -> "halt"),
# mirroring review-crew's review_result.read_result (a library reader, not a CLI):
ACTION=$(python3 -c "import json; print(json.load(open('$RESULT'))['action'])" 2>/dev/null || echo halt)
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

Emit step_entered journal event. **Before the push/PR write:**
`lock.renew(store, WORK_ITEM, generation)` then **`lock.fence_ok(store, WORK_ITEM, generation)`**
(`lock.py`) — a stale generation means a newer session holds the ref-lease; abort the
write (superseded). Never push under a stale fence.

**First world-READ, then world-WRITE.** Use **`recover.pr_action(world)`** to decide:
- A PR already exists for this branch → **adopt** it (capture its number; if it's
  already non-draft, note that and skip the open) — do not create another.
- No PR exists → push the branch and open a **draft** PR (`gh pr create --draft …`),
  then capture the number.
- Merged or unreadable state → **GATE** (fail-closed).

`gh pr list --head "$BRANCH" --json number,state,isDraft` is the world-read;
the PR-action decision is a code gate, not free-form judgment. Reversible → **NOTIFY**
(report the link in the readout). The enforcer permits `gh pr create`/`git push`
(non-force); it refuses `gh pr merge`.

Write `checkpoint.write(…, phase="verify", lastGoodStep=3, pr=<pr-object: {number, url, isDraft}>, lockGeneration=generation)`
(a dict, not a bare number — `render_brief` reads `pr.get("url")` and the reconcile reads `pr.get("state")`/`number`).

## ④ Dev server (managed) — only when there's a runnable surface

Emit step_entered/step_completed journal events.

Detect the dev-server command: `python3 "$LIB/detect.py"` (`detect_dev_server`).
None detected → no spot-check server; note it and skip ④⑤⑥. Otherwise:

  The sidecar path is `SIDECAR = paths["devserver"]` (`control_plane.paths` →
  `<issue_dir>/devserver.json`) — the **same** stable path on the first run and on
  every resume, so reclaim finds what the prior run wrote.
- **Reclaim first (resume / orphan-after-crash).** Before starting, try
  `devserver.reclaim(SIDECAR, port, command)` (`devserver.py`): if it corroborates
  (port + scrubbed-command + bootId), the handle is only an *identity* match — confirm
  it's actually **alive** with `devserver.poll_healthy(devserver.health_url(port),
  timeout=…, interval=…)` before adopting. Alive → adopt the teardown handle (a managed
  server from a prior run is still up; don't double-start). **Corroborated-but-dead**
  (poll fails — the orphan died between sessions) → tear it down and start fresh, so ⑤
  never runs against a non-responding server. If `reclaim` is `None` but
  `devserver.port_in_use(port)`, **GATE** (an unrecognized process holds the port — do
  not kill what we can't prove is ours). Else start fresh.
- **Start managed:** `devserver.start(command, port)`, then bound the readiness wait
  with `devserver.poll_healthy(devserver.health_url(port), timeout=…, interval=…)`
  (never an unbounded poll). On a fresh start, persist the identity for a later
  reclaim: `devserver.write_sidecar(SIDECAR, handle, command, root=ROOT)` (the
  `command` is scrubbed fail-closed).
- Capture the handle. **Tear it down (`devserver.teardown`) on every terminal state,
  GATE, or error** — no zombie. One server serves ⑤ and the ⑨ spot-check.

## ⑤ Behavioral — test-pilot (two skills) — runnable surface only

Before writing seed data: `lock.renew(store, WORK_ITEM, generation)` then
`lock.fence_ok(store, WORK_ITEM, generation)` — stale generation ⇒ abort (superseded).

Emit step_entered/step_completed journal events; write checkpoint.

Invoke `test-pilot-plan` (seeds scenarios via test-pilot's `engine.py`, posts the
checkbox plan comment to the PR via `pr_comment.py`) then `test-pilot-execute`
(drives the UI, posts the results comment). Workhorse supplies the PR number (③)
and the live dev server (④); it does NOT re-implement seeding or PR posting. A
failure it can fix → fix + re-verify; else → GATE.

## ⑥ Reset — engine clean (state-scoped, protected-gated)

Before the reset write: `lock.renew(store, WORK_ITEM, generation)` then
`lock.fence_ok(store, WORK_ITEM, generation)` — stale generation ⇒ abort.

Emit step_entered/step_completed journal events; write `checkpoint.write(…, phase="verify", lastGoodStep=6, lockGeneration=generation)` after a successful reset/verify_empty.

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

Before flipping draft: `lock.renew(store, WORK_ITEM, generation)` then
`lock.fence_ok(store, WORK_ITEM, generation)` — stale generation ⇒ abort.

Emit step_entered/step_completed journal events; write `checkpoint.write(…, phase="verify", lastGoodStep=7, lockGeneration=generation)`.

Once ⓪–⑥ are clean, **read the PR's current state first** (`gh pr view <N> --json
isDraft`): if it is already non-draft, this step already ran (a prior pass /
pre-compaction) — note it and continue. Only when it is still a draft: flip it
(`gh pr ready <N>`) (NOTIFY). The read-before-write keeps re-entry from churning the
PR state.

## ⑧ CI-green gate — bounded fix loop (write-ahead journal)

Before any fix push: `lock.renew(store, WORK_ITEM, generation)` then
`lock.fence_ok(store, WORK_ITEM, generation)` — stale generation ⇒ abort.

Wait on the PR's checks **whenever CI runs** (this repo's CI runs on drafts):
`gh pr checks <N>`. Detect the provider with `detect.detect_ci`; **none →** the
readout says **"CI not detected"**, never a false ✓.
- Green → write `checkpoint.write(…, phase="verify", lastGoodStep=8, lockGeneration=generation)`, then continue (so a resume after ⑧ advances to ⑨ rather than re-running the CI gate).
- Red → derive the failing-check signatures, then:
  1. **Derive attempt count from the journal (survives restarts):**
     `(rounds, history) = journal.ci_attempts(events)` (`journal.py`).
  2. **Write-ahead before the fix push:**
     `journal.append(events, "ci_fix_attempt", payload={"round": rounds+1, "failing": sigs})`.
     Because this is written *before* the push, parking on a write failure means the
     push never happens → no under-count even across restarts.
  3. Call `ci_loop.decide(sigs, history, rounds+1)` (`ci_loop.py`):
     - `fix` → fix + push + re-wait.
     - `revert_and_gate` (cap reached / recurring set / no actionable failures) →
       `gh pr ready --undo <N>` (revert to draft) + **GATE**.

## ⑨ Handoff — your turn

Emit step_entered/step_completed journal events; write `checkpoint.write(…, phase="ship", lastGoodStep=9, lockGeneration=generation)` (the final checkpoint).

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

Workhorse is a supervised single session (durable/unattended resume is handled by
the resilience substrate above). If a GATE fires and the owner is away, **park safely**:
1. Tear down the dev server.
2. Run ⑥ reset (clean baseline). If a parking step fails (e.g. a held engine lock),
   **report the partial state honestly** rather than assert a baseline that doesn't hold.
3. Leave the PR as **draft**.
4. Release the startup lock: `lock.release_startup(store)` — the ref-lease expires
   naturally (do not release it; a future resume needs to re-evaluate `stolen` vs
   `continue`).
5. Write the parked state to the journal via `journal.render_brief(…)` so any resume
   reconcile sees "parked" as the last known state, not an ambiguous cursor.

**Durable-write failures are fail-closed (park-GATE).** The orchestrator wraps every
`journal.append` / `checkpoint.write`; a `journal.DurableWriteError` (`journal.py`)
or an `atomic_write` `OSError` (e.g. a full disk, from `control_plane.py`) →
**park-GATE**: "durable state write failed — disk?". Because the ⑧ `ci_fix_attempt`
journal entry is *write-ahead* (before the push), parking on its failure means the
push never happens → no under-count.

**SessionStart(compact)** is handled by the hook injecting context (the compact
hook); the orchestrator, on its next turn, re-runs the ⓪ reconcile + floor re-arm
(the cold path is the gated invariant). The control-plane's `control_plane.get_current`
gives the resumed work item; the journal brief gives the last step, so the reconcile
can hand back the right `from_step`.

## Applicability

④⑤⑥ run as one unit **only when the change has a runnable surface**. A
library/CLI change skips to ②③⑦⑧⑨ (PR + CI + readout, no server).
