---
superheroes: doc
schemaVersion: 1
docType: plan
workItem: unattended-safe-permission-posture-for-showrunner-7ff048
issue: 149
size: medium
status: approved
gates: {review: passed}
producedBy: "the-architect@0.6.0"
created: "2026-07-03"
updated: "2026-07-05"
---
# Unattended-safe permission posture for showrunner runs — Plan

## Overview

Showrunner runs stall for hours when a leaf action trips a permission prompt while the owner
is away. The fix is two independent moves layered on the *existing* deterministic gate
(`lib/enforcer.py`, wired as the `PreToolUse` hook) — no new host machinery, no broad
skip-permissions mode.

First, **fewer prompts fire at all.** The enforcer already classifies commands as
`allow`/`ask`/`deny` and floors the owner-role set. We extend its `classify_command` with an
*allowance layer* evaluated after the safety surfaces and before the default `allow`: an
owner-curated set of routine command families, plus two structural allowances — commands whose
working directory is a real managed build worktree under `~/.superheroes-worktrees/` (interpreter
invocations, FR-5), and commands the spine composed byte-for-byte for the current run (FR-8). The
allowance layer is data-driven from an out-of-repo rules store (`projects/<config_key>/permission/`
in the superheroes store — the same store that already holds `registry.json`), so it leaves no
artifact in the repository and reaches every session and fresh worktree of the project. Reviewer
leaves are steered (FR-4) onto the already-allowed test-file route so improvised inline-interpreter
probes — the exact action that caused the 7h33m stall — mostly stop happening; FR-5 is the safety
net for the ones that slip through.

Second, **a prompt that does fire self-resolves within 15 minutes.** The enforcer stays
synchronous — it cannot itself sleep-then-deny — so the *bound* is realized where the wait
actually lives: the native host `ask` prompt (which the Claude app already push-notifies and
blocks on) is annotated, via the reviewer/leaf instructions the spine dispatches, with a
"proceed-without-it after 15 minutes" contract, and the **denial is recorded deterministically**
in the run's quality/journal records so the spine absorbs it — a denied verification probe becomes
a low-confidence check (FR-2), a denied substantive build step becomes incomplete build evidence that
holds the PR draft via the ship gate (UFR-6/UFR-8), and
every denial is named in the readout (UFR-3). The whole timeout behavior is gated on an *active
run* (the `ref_lock` lease), so interactive sessions are untouched (FR-3). The owner-role floor is
never widened: the allowance layer sits strictly *below* the floor's unconditional deny/ask, and
the floor keeps hard-gating merge/release/workflow-run/force-push/push-to-default throughout
(UFR-1).

## Goals & non-goals

**Goals**

- Cut permission prompts during a showrunner run to near-zero for routine, worktree-scoped, and
  spine-composed actions (FR-4 through FR-8), grounded in an audit of what actually prompts (FR-7).
- Bound any prompt that still fires to 15 minutes of visible degradation, not hours of wall-clock,
  during an active run only (FR-1/FR-2/FR-3), with the degradation absorbed and disclosed
  (UFR-3/UFR-6/UFR-8).
- Keep the owner-role floor exactly as strong as today — nothing merges/releases/rewrites-history
  without live approval (UFR-1), even in the face of path tricks (UFR-5) and mid-run rule edits
  (UFR-9).
- Store the posture entirely out-of-repo and make it inspectable/changeable through the one
  configuration front door (FR-6/FR-9).

**Non-goals**

- No new notification wiring — the Claude app's existing push is sufficient (spec Out-of-scope).
- No changes to the host harness (Claude Code) itself — everything rides existing extension
  surfaces (spec Out-of-scope).
- No generic dangerous-command detection in the deterministic layer — a deliberate prior decision
  keeps `rm -rf`/`--prod`/destructive-SQL heuristics out of the enforcer (spec Out-of-scope;
  matches the existing `enforcer.py` scope note).
- No Codex-side permission-flow changes and no cumulative run-total wait cap — both explicitly
  owner-accepted residuals.
- No plugin-wide default or retrofit to other repos — this defines the posture for this project's
  showrunner runs only.

## Architecture

The design is a thin extension of the *existing* single deterministic gate, plus one out-of-repo
data store, plus instruction-level steering, plus run-side bookkeeping. Four seams:

1. **Enforcer allowance layer (`lib/enforcer.py` + new `lib/permission_rules.py`).** The hook's
   `classify_command(command, host='codex', in_scope=True)` already runs: non-string → canary →
   safety-write → owner-role gate → default allow. The owner-role gate is itself branched on `in_scope`
   and `host`: when `gated_action(command)` matches, an **out-of-scope** command (cwd not under a
   superheroes repo, `_in_superheroes_repo`) returns `allow`; an **in-scope** command returns `ask` for
   `host == 'claude'` and `deny` for any other host — and on that `deny` the *hook* (not
   `classify_command`) runs the Codex single-use allowance/nonce overlay in `lib/allowance.py`
   (challenge → owner-minted approval → consume). We insert an *allowance evaluation* strictly on the
   **non-gated** branch (step 5, where `gated_action` did NOT match, so `in_scope`/`host` never altered
   the outcome and the result is today's unconditional `allow`): consult
   `permission_rules.evaluate(command, cwd, run_id)`. It returns `allow` when the command matches a
   routine family (FR-6), is confined to a real managed worktree (FR-5), or byte-matches a spine-composed
   command for the current run (FR-8); otherwise it hands control back so the existing default (`allow`,
   or on the Claude host the native `ask` for whatever surface the leaf hits) is preserved. Critically
   the allowance layer sits *only* on the non-gated branch — it is never consulted for the owner-role
   set on any host or scope (all three gated outcomes `allow`/`ask`/`deny` return before step 5), so it
   cannot widen the floor; and because it only ever runs where the pre-existing outcome was `allow`, it
   is definitionally incapable of *loosening* anything — it is purely a **prompt→allow** move on the
   subset of default-allow commands the Claude host would otherwise `ask` about. Any error in the
   allowance layer falls through to the existing path (fail-safe, UFR-2).

2. **Out-of-repo rules store (`projects/<config_key>/permission/rules.json` + `audit.json`).** The
   rules and the FR-7 audit live in the project store (keyed by `mode_registry.config_key`, the same
   common-dir key the storage-mode `registry.json` uses), never in the repo or a checkout. Because the
   store is keyed on the clone's common dir, a fresh build worktree resolves the same rules — solving
   the "settings.local.json never reaches a fresh worktree" problem the discovery flagged. The store
   also holds a per-run *frozen snapshot* so a run evaluates the rules as they stood at run start
   (UFR-9). `permission_rules.py` owns reading, provenance-checking, and freezing this store.

3. **Run-active signal + timeout contract.** "A run is active" is the existing `ref_lock` lease on
   `refs/superheroes/locks/<work-item>` (already the sole mutex for "one live run per work item").
   `permission_rules.evaluate` and the timeout behavior both key on it: no active lease → the
   allowance layer's *timeout* half is inert and prompts wait indefinitely as today (FR-3). The 15-min
   bound itself is delivered as an *instruction contract* embedded in every reviewer/leaf prompt the
   spine dispatches during a run, paired with deterministic denial bookkeeping so the outcome is
   recorded, not merely narrated. Where the *wait* lives depends on the leaf's host, and the contract is
   written to cover both: on a **Claude-hosted** leaf a floor/default prompt surfaces as a synchronous
   native `ask` that blocks and push-notifies, and the contract says "proceed-without-it after 15 min";
   on a **Codex-hosted** leaf a gated action is a hard `deny` with no blocking wait (the `allowance.py`
   nonce flow needs a live owner mint that will not arrive unattended), so the same contract instructs
   the leaf to treat that immediate deny as the timeout outcome — record the denial and continue rather
   than spin re-issuing it. Either way the deterministic denial event is the load-bearing part; the
   15-min figure bounds only the Claude-host blocking case (the sole place a wall-clock wait exists). The
   spec's "no Codex-side permission-flow changes" non-goal holds: we add no new Codex mechanism, we just
   name the existing deny as the leaf's proceed-signal in the instruction contract.

4. **Run-side absorption + readout (`lib/showrunner.js` review loop, `lib/panel_tally.js` gate,
   `lib/journal*.py`, `lib/pr_phase.py`/`lib/ship_phase.py`/`lib/ship_gate.py`, `lib/run_readout.py`).**
   A timeout denial is written to the run journal as a typed event; the review loop reads a denied
   verification probe as `confidence: low` (reusing the existing receipt/low-confidence deep-retry path,
   FR-2). A denied substantive **build** step (UFR-6) is a genuinely new gate concept — *not* one an
   existing gate already represents, and the one place this plan adds gate logic rather than reusing it.
   Two existing gates are load-bearing but neither covers it as-is: `panel_tally.roundGate`'s
   `incomplete`/`cannot-certify` is strictly the *reviewer-roster* completion gap (`expectedRoster` minus
   `completedRoster`) whose `cannot-certify` reason is "a reviewer did not complete after its retry" — a
   review-coverage concept, never a build-step concept; and `ship_gate.decide` gates only on
   `provenance.get('build')` truthiness (the build step *ran*) and `review_result['action']` being the
   terminal action, with no field representing "a build sub-step was denied mid-way." So a denied build
   step is threaded into the **ship gate's build-evidence arm**: the spine records the denial against the
   run's build provenance so `ship_gate.decide` returns `gate` ("build evidence incomplete/tainted," not
   merely "build ran"), which is the gate `pr_phase.mark_ready_action` / `ship_phase.py`'s `revert-draft`
   already read to hold the PR a draft. A denied *reviewer* probe still degrades the review dimension
   (FR-2) and can independently drive `roundGate` low-confidence, but the build-step→draft-hold path is
   the ship gate, not the roster gate — it is *not* a new field on `run_readout.py`. Draft/ready-for-review
   gating (UFR-8) is thus enforced where it already lives:
   `pr_phase.mark_ready_action` returns `gate`/`skip`/`flip` and `ship_phase.py`'s `revert-draft` step
   returns the PR to draft, so a gated ship decision never flips the PR to ready. The
   readout layer (`run_readout.assemble`, which today only maps run state onto the `build_readout`
   context dict — it has no denial list, incomplete-step field, or draft logic) is extended additively
   to *enumerate* the journal's denial events (UFR-3); the incomplete/draft *decisions* stay in
   `panel_tally.js` and the pr/ship phase, which is where they must be wired.

The configure front door (`configure` skill → its permission sub-init) reads and edits the rules
store (FR-9), and the enforcer is the single place a rule ever takes effect (FR-9/UFR-9).

```
PreToolUse(Bash) ──> enforcer.hook(host) ──> classify_command(command, host, in_scope)
                                          │ non-string / canary / safety-write  -> deny (unconditional)
                                          │ owner-role gated set (FLOOR — never allowance-checked):
                                          │     out-of-scope                    -> allow (not gated in this repo)
                                          │     in-scope + host==claude         -> ask
                                          │     in-scope + other host           -> deny  (hook runs allowance.py nonce overlay)
                                          │ else (non-gated, today = allow) -> permission_rules.evaluate(command, cwd, run_id)
                                          │           routine family (FR-6) │ worktree-confined (FR-5) │ composed-exact (FR-8) -> allow
                                          │           error / no match      -> fall through to default (FR-3/UFR-2)
                                          └ default                             -> allow  (Claude host may native-ask here)
```

## Components & interfaces

- **`lib/permission_rules.py` (new).** One responsibility: decide whether a non-owner-role command is
  auto-allowed for the current run, and own the out-of-repo rules store lifecycle.
  - `evaluate(command, cwd, run_id) -> ("allow"|"ask"|"deny", reason)` — pure decision. `allow` iff a
    routine family matches (FR-6) OR the command's resolved working dir is a real managed worktree and
    the command is an interpreter invocation (FR-5) OR the command byte-equals a composed command
    frozen for `run_id` (FR-8). Any I/O error, unreadable/corrupt store, or path-resolution failure →
    the caller's existing path (fail-safe, UFR-2). It is called **only** on the non-gated branch, so it
    is never reached for the owner-role set on any `host`/`in_scope` combination; a defensive re-check of
    `enforcer.gated_action(command)` inside makes the "never allow a gated command" invariant local to
    this function too (belt-and-suspenders, UFR-1). Note the re-check reproduces only the *gated/not-gated*
    partition, not the floor's full `in_scope`/`host` decision (ask vs. deny vs. the Codex nonce overlay):
    that is sufficient because `evaluate` runs solely where the floor already resolved to the non-gated
    default `allow`, so its only lever is prompt→allow — it never needs to, and never can, reconstruct the
    gated ask/deny/allowance outcome.
  - `worktree_confined(command, cwd) -> bool` — true only when the *realpath* of the working dir is a
    strict descendant of the realpath of `~/.superheroes-worktrees/`, computed after symlink/`..`
    resolution so a lookalike path earns nothing (UFR-5).
  - `freeze_run_rules(run_id, cwd)` / `frozen_rules(run_id)` — snapshot the rules + composed-command
    set at run start and read that snapshot thereafter (UFR-9); a mid-run store edit is invisible to a
    frozen run. After writing the new run's file it also reaps stale sibling `runs/*.json` (no live
    run-lease, older than 30 days) — the crash-tolerant retention bound described under Data flow.
  - `record_composed(run_id, command)` — the spine registers each command it composes so FR-8's
    exact-match set is populated for `evaluate`.
  - `rules() / set_rule() / remove_rule()` — the configure front door's read/write surface (FR-9),
    each writing through `provenance`-stamped records so untraceable rule state is ignored (UFR-9).
- **`lib/enforcer.py` (changed).** `classify_command(command, host, in_scope)` gains one call to
  `permission_rules.evaluate` on the **non-gated branch only** — after `gated_action` returns falsy and
  before the final `return ('allow', '')` — guarded so any exception falls through to today's return.
  The owner-role gate (with its `in_scope`→allow, `host=='claude'`→ask, other-host→deny arms), canary,
  and safety-write surfaces are unchanged and still return *before* the allowance call; the hook's Codex
  `allowance.py` nonce overlay is likewise untouched (it fires on the gated `deny`, which the allowance
  layer never sees). `selfcheck` gains assertions that (a) an owner-role command keeps its per-host/scope
  outcome with allowance rules present — `ask` for `host='claude'`/`in_scope`, `deny` for a deny-only
  host/`in_scope`, `allow` when out-of-scope — and (b) a would-be routine command allows only when a
  matching rule exists, so a broken allowance layer is caught at step 0.
- **Rules store schema (data, out-of-repo).** `rules.json`: a list of `{family, pattern, provenance}`
  routine allowances (test-run family, the three validators, worktree-confined VCS excluding the
  owner-role set, draft-PR create/edit/promote). `audit.json`: the FR-7 record of prompt-provoking
  commands observed in a full run and each one's disposition (allow-rule id or "keep prompting").
  `runs/<run_id>.json`: the frozen snapshot + composed-command hashes for one run.
- **Reviewer/leaf instruction blocks (`lib/showrunner.js` prompt strings, `skills/review-code`
  reference).** The reviewer-leaf verification instruction names the throwaway-test-file-in-worktree
  route as the required probe shape and discourages inline interpreter probes (FR-4); every dispatched
  leaf prompt carries the 15-minute contract (proceed-without-it after 15 min; a denied action is
  reported honestly, never as done — FR-1/UFR-6).
- **Run-side absorption (`lib/showrunner.js`, `lib/journal*.py`, `lib/panel_tally.js`,
  `lib/pr_phase.py`/`lib/ship_phase.py`, `lib/run_readout.py`).** A denial is a typed journal event
  (`permission_denied`), which requires adding that literal to `journal.py`'s `EVENT_TYPES` allowlist —
  `journal.append` raises `DurableWriteError` (→ orchestrator park) on any type absent from that set, so
  this is a hard prerequisite, not an optional touch. The
  review loop maps a denied probe to `confidence: low` (FR-2, reusing the existing deep-retry path). A
  denied substantive **build** step (UFR-6) is threaded into `ship_gate.decide`'s build-evidence arm —
  the spine records the denial against the run's build provenance so the gate returns `gate` ("build
  evidence incomplete/tainted," not just "build ran"). This is the *one* new gate input the plan adds:
  neither `panel_tally.roundGate` (whose `incomplete`/`cannot-certify` is strictly the reviewer-roster
  gap, a review-coverage concept) nor today's `ship_gate.decide` (which reads only `provenance['build']`
  truthiness + the terminal `review_result['action']`) represents a denied build sub-step. The draft-hold
  (UFR-8) then reuses the existing path: a `gate` ship decision keeps the PR a draft via
  `pr_phase.mark_ready_action` / `ship_phase.py`'s `revert-draft`. `run_readout.assemble` (which today maps run state onto the
  `build_readout` context dict and has no denial/incomplete/draft fields) gains one additive
  responsibility: enumerate the journal's denial events for the readout (UFR-3). The
  incomplete-and-draft *logic* is not bolted onto `run_readout.py`.
- **Configure front door (`configure` skill + a permission sub-init helper).** Adds the permission
  posture to the one-screen calibration view and routes edits through `permission_rules.set_rule` /
  `remove_rule` (FR-9).

## Data flow & data model

A command flows: leaf issues Bash → `PreToolUse` hook → `enforcer.classify_command` → (non-gated)
`permission_rules.evaluate(command, cwd, run_id)` → reads the *frozen* `runs/<run_id>.json` snapshot
(never the live `rules.json`, UFR-9) → returns allow / fall-through. At run start the spine calls
`freeze_run_rules(run_id, cwd)`, copying the current provenance-valid `rules.json` and initializing an
empty composed-command set; each composed command the spine writes is `record_composed`ed into that
same run file. A timeout denial flows the other way: the leaf/spine writes a typed denial event into
the run journal, which the review loop (probe → `confidence: low`), `panel_tally.roundGate` (substantive
build step → recorded against build provenance so `ship_gate.decide` returns `gate`, which
`pr_phase.mark_ready_action` / `ship_phase.py`'s `revert-draft` read to hold the PR draft), and
`run_readout.assemble` (enumerate denials for the readout) each consume — the draft/gating
decisions stay in `ship_gate.py`/`pr_phase.py`/`ship_phase.py`, not in `run_readout.py`. (`roundGate`'s
roster gap is a distinct, review-coverage concern; a denied build step does not travel through it.)

**Data model (new, all out-of-repo, all run-local or config-local — nothing committed):**
`rules.json` (config-local, low-churn, owner-edited via the front door), `audit.json` (config-local,
append-oriented), `runs/<run_id>.json` (run-local frozen snapshot + composed hashes + denial events).
Run files are **reaped lazily at run start**: after `freeze_run_rules(run_id, cwd)` writes the new
run's file, it deletes sibling `runs/*.json` entries that have no live run-lease and are older than a
bounded age (30 days). Run-*end* deletion is deliberately not the mechanism — a crashed or parked run
would leak its file forever, while run-start reap is crash-tolerant (the next run always cleans up);
a project that never runs again holds at most its last few small run files until the store itself is
swept as an orphan (`store_sweep.py`), which bounds accumulation in both the live and abandoned
cases. No existing on-disk data shape is changed — the run journal gains one new
event type (`permission_denied`). Adding it is **not** costless-additive on the *write* side:
`journal.append` (`lib/journal.py`) validates `event_type` against a hardcoded `EVENT_TYPES`
allowlist and raises `DurableWriteError` for anything absent — which the orchestrator treats as a
fail-closed **park**. So the new type MUST be added to `journal.py`'s `EVENT_TYPES` set (a one-line
edit named alongside every other touched symbol below) *before* any denial event is written;
skipping it would park every run that hits a timeout denial — the exact failure this feature
prevents. On the *read* side it is forward/backward compatible: older readers ignore unknown event
types, and denial-unaware consumers (`ci_attempts`, etc.) don't count it.
Provenance: every `rules.json` entry carries a stamp written only by the configure front door; a
record whose provenance can't be traced to a front-door change is ignored at evaluate time and its
would-be coverage falls back to prompting (UFR-9).

## How the requirements are met

- **FR-1 (15-min timeout → deny, leaf continues).** On the Claude host the wait lives in the native
  `ask` and the proceed-after-15-min contract (embedded in every dispatched leaf prompt during an active
  run) flips it to a recorded denial; on a Codex-hosted leaf a gated action is already an immediate
  `deny` (no blocking wait), so the same contract treats that deny as the proceed-signal — no unattended
  hang to bound. Either way the deterministic denial event lets the spine advance the leaf. Per-run scope
  comes from keying the behavior on the run's `ref_lock` lease + `run_id`; per-step finality is enforced
  by recording the denied step so re-dispatch of the same work is treated as a re-attempt, not a fresh
  ask.
- **FR-2 (denied verification check → low-confidence).** The review loop already routes
  `confidence: low` to a deep retry / degraded-dimension report; a denied probe is written as exactly
  that, and the "deep retry also denied → report degraded, don't re-cycle" bound reuses the loop's
  existing single-retry ceiling.
- **FR-3 (no run active → unchanged).** `permission_rules.evaluate`'s timeout half and the leaf
  15-min contract are both gated on an active `ref_lock` lease; with none, prompts wait indefinitely
  exactly as today. (The routine/worktree/composed *allowances* are also naturally inert interactively
  because they are only meaningful inside a run, but the timeout behavior is the FR-3-critical half.)
- **FR-4 (reviewer probes onto the allowed route).** The reviewer-leaf instruction names the
  throwaway-test-file-in-worktree + allowed test-run family as the required probe and explicitly
  discourages inline interpreter probes.
- **FR-5 (managed-worktree interpreter → no prompt).** `worktree_confined` allows interpreter
  invocations whose realpath'd working dir is a strict descendant of realpath'd
  `~/.superheroes-worktrees/`.
- **FR-6 (owner-curated routine families → no prompt).** `rules.json` enumerates the test-run,
  three-validator, worktree-confined-VCS (excluding the owner-role set), and draft-PR
  create/edit/promote families; `evaluate` allows a match. Living in the common-dir-keyed store, they
  take effect in every session and fresh worktree with no repo artifact. The excluded owner-role set
  keeps its floor behavior (UFR-1); changing a PR's base branch is deliberately *not* in the family.
- **FR-7 (grounded in an audit).** `audit.json` records the prompt-provoking commands seen in a full
  run and maps each routine family to an allow rule or a recorded "keep prompting" decision; the rules
  are authored from it.
- **FR-8 (spine-composed command → no prompt).** `record_composed` registers each composed command;
  `evaluate` allows a *byte-exact* match scoped to the composing `run_id`. Any character difference, or
  a different run, falls through to the prompt path.
- **FR-9 (view/change via configure).** The configure front door lists the full allow set on one
  screen and edits it through `set_rule`/`remove_rule`; it is the only sanctioned change path.
- **NFRs.** *Unattended completion*: no single request waits >15 min during a run (per-request bound;
  no run-total cap, owner-accepted). *Safety*: the allowance layer is never reached for owner-role
  actions, so no owner-role action auto-executes. *Auditability*: the standing allow set is one-screen
  inspectable (FR-9) and every allowance/denial is in the run's journal/readout.
- **Unhappy paths.** UFR-1 floor overrides all allowances (allowance layer sits below the floor, plus
  a defensive re-check). UFR-2 any allowance-machinery error → prompt, never allow. UFR-3 every denial
  named in the readout. UFR-4 a late owner response after the 15-min denial is not applied (the denial
  event is terminal for that step; the native prompt's late answer has nothing live to act on). UFR-5
  path tricks earn no worktree allowance (realpath + strict-descendant check). UFR-6 a denied
  substantive build step is recorded against build provenance as incomplete/tainted. UFR-7 a crash
  mid-wait resolves to denied on resume (no pending-allowance is ever persisted; a pending request has
  no durable "approved" state to recover).
  UFR-8 a denied build step keeps the PR a draft — enforced by recording the denial against build
  provenance so `ship_gate.decide` returns `gate`, which already blocks the
  `pr_phase.mark_ready_action` draft→ready flip (no new draft logic in `run_readout.py`; and *not* via
  `panel_tally.roundGate`, whose incomplete gate is the distinct reviewer-roster gap). UFR-9 a run
  reads its frozen snapshot; untraceable
  rule state is ignored; direct edits never affect a run.

## Key decisions & alternatives

- **Decision:** Realize the 15-min bound via the native `ask` prompt + a leaf instruction contract +
  deterministic denial bookkeeping, rather than a background watchdog that force-denies a pending host
  prompt. · **Options weighed:** (a) instruction-contract + deterministic bookkeeping *[chosen]*;
  (b) an out-of-band watchdog process that times the pending `ask` and injects a `deny`. · **Choice +
  why:** the host `ask` (the Claude-host case; a Codex-hosted gated action is already an immediate deny
  with no pending prompt to time out) is owned by the harness, which is explicitly out of scope; there is
  no supported surface to cancel a pending prompt from outside, so (b) would require harness changes the
  spec forbids. (a) puts the wait where it already is (the app blocks + push-notifies) and makes the
  *outcome* — not the wait — the deterministic part. · **Accepted downside:** the exact instant of the
  15-min flip depends on the leaf honoring its instruction; the deterministic denial record bounds the
  *cost* (a denial is recorded and absorbed) but not to-the-second timing. · **Reversible?** two-way
  (swap in a watchdog later if the harness grows a cancel surface). · **Mode:** PROCEED (implementation
  shape within the spec's fixed constraint that the harness is untouched). · **Reverse path:** replace
  the instruction leg with a watchdog leg; the bookkeeping stays. · **Expiry:** n/a. · **Escalated?**
  no — the "no harness changes" constraint is owner-fixed in the spec, so this is the only in-scope
  shape.

- **Decision:** Extend the *existing* `enforcer.py` gate with an allowance layer rather than adding a
  second, independent permission hook. · **Options weighed:** (a) one gate, allowance layer inside
  `classify_command` *[chosen]*; (b) a separate `permission_allow` hook wired alongside the enforcer. ·
  **Choice + why:** two hooks on the same `PreToolUse(Bash)` matcher would race and the *most
  restrictive* wins is not guaranteed across independent hooks, risking an allow leaking past the floor
  or a floor deny being masked; one gate keeps the floor unconditionally first and the allowance
  strictly subordinate, which is the whole safety argument. · **Accepted downside:** `enforcer.py`
  grows; the allowance concern is co-located with the floor concern in one file (mitigated by putting
  the allowance logic in a separate `permission_rules.py` the enforcer merely calls). · **Reversible?**
  two-way. · **Mode:** PROCEED (engineering-internal). · **Escalated?** no.

- **Decision:** Store the rules in the *common-dir-keyed project store* (`projects/<config_key>/`),
  not in `.claude/settings.json` or `settings.local.json`. · **Options weighed:** (a) out-of-repo
  project store *[chosen, and owner-locked in discovery Option B]*; (b) checked-in `.claude/
  settings.json`; (c) uncommitted `.claude/settings.local.json`. · **Choice + why:** (b) leaves a repo
  artifact (spec forbids); (c) never reaches a fresh build worktree (the worktree is a clean clone with
  no uncommitted files) — the exact failure discovery identified. The common-dir-keyed store is visible
  from every worktree of the clone and leaves no repo trace. · **Accepted downside:** the rules are
  per-machine and don't travel with the repository (owner-accepted in the spec's Constraints). ·
  **Reversible?** two-way (the store path is an internal detail). · **Mode:** PROCEED (owner already
  locked this in discovery). · **Escalated?** no — already owner-decided (recorded in discovery Option
  B).

- **Decision:** Use the existing `ref_lock` lease as the "run active" signal for FR-3 and per-run
  scoping, rather than a new run-state file or an env var. · **Options weighed:** (a) `ref_lock` lease
  *[chosen]*; (b) a new `RUN_ACTIVE` marker file; (c) a `SUPERHEROES_RUN_ID` env var read by the hook.
  · **Choice + why:** the lease is already the authoritative "one live run per work item per clone"
  mutex and is visible to the hook via the store; (c) is unreliable because `SessionStart` does not
  provision `CLAUDE_ENV_FILE` (confirmed in `session_start.py`) so a hook can't count on env; (b)
  duplicates state the lease already holds and could drift. · **Accepted downside:** the hook takes a
  small git read to consult the lease per gated evaluation (bounded, cached per-run). · **Reversible?**
  two-way. · **Mode:** PROCEED (engineering-internal). · **Escalated?** no.

- **Decision:** Freeze each run's rules at run start (snapshot in `runs/<run_id>.json`) and evaluate
  against the snapshot. · **Options weighed:** (a) freeze at run start *[chosen]*; (b) read live
  `rules.json` on every evaluation. · **Choice + why:** UFR-9 requires a mid-run edit to have no effect
  on the running run; a live read would let an edit broaden (or narrow) a run in flight. · **Accepted
  downside:** an owner narrowing a rule mid-run doesn't take effect until the next run — their immediate
  lever is stopping the run (owner-accepted in Assumptions). · **Reversible?** two-way. · **Mode:**
  PROCEED. · **Escalated?** no — the frozen-snapshot semantics are owner-decided in the spec.

## Cross-cutting concerns

- **Security & privacy:** the central concern is *not weakening the owner-role floor*. The allowance
  layer is structurally subordinate — it is only ever consulted on the non-gated branch, i.e. for
  commands the floor already resolved to the default `allow` on every `host`/`in_scope` combination, so
  the gated arms (out-of-scope allow, `host=='claude'` ask, other-host deny + Codex `allowance.py` nonce
  overlay) all return before it and it can only turn a default prompt into an allow, never any floor
  outcome into an allow; a defensive re-check of `enforcer.gated_action` inside `evaluate` backstops the
  gated/non-gated partition locally (UFR-1). Path
  tricks are defeated by realpath + strict-descendant checks (UFR-5). All new state is out-of-repo and
  local (no new PII, no new network trust boundary). The fail-safe direction is always *toward
  prompting* (UFR-2).
- **Observability:** "how does the owner debug this at 2am?" — every automatic allowance and every
  timeout denial is a typed event in the run journal, and the readout enumerates denials with the
  affected step/check (UFR-3). The FR-7 `audit.json` is the standing record of what prompted and how it
  was dispositioned; the configure front door shows the whole allow set on one screen (FR-9). The
  enforcer `selfcheck` surfaces a broken allowance layer at step 0.
- **Reliability & failure modes:** the rules store is a *non-critical* dependency — unreadable/corrupt/
  missing → fall back to prompting (degrade, never fail-open, UFR-2). The `ref_lock` lease read is
  non-critical — undetectable run state → treat as no active run → prompts wait as today (FR-3). A crash
  mid-wait resolves to denied on resume because no pending allowance is ever persisted (UFR-7).

## Rollout & migration

N/A — because this is internal single-owner tooling with no user-facing surface, no API, and no
data migration: the rules store starts empty (first-run and any additional machine simply has no rules
→ today's normal prompt path, safe by default), the new journal event type is read-side additive
(older readers ignore it) though it does require the one-line `journal.py` `EVENT_TYPES` allowlist
edit on the write side (see Data model — omitting it parks the run), and the change is off by
construction until the owner authors rules through the configure front door. The kill-switch is inherent: an empty or removed `rules.json` reverts every
command to the normal permission path, and stopping the run is the owner's immediate lever for a run in
flight.

## Risks & mitigations

- **The 15-min flip is instruction-dependent, so a leaf could ignore it and still hang.** Mitigation:
  the *cost* is bounded deterministically (a denial is recorded and absorbed regardless of exact
  timing), and FR-4 removes the most common prompt source (improvised probes) so the instruction is
  rarely load-bearing; the app's push keeps the owner able to answer sooner.
- **An allowance rule accidentally overlaps the owner-role set and leaks a merge/push.** Mitigation:
  the allowance layer is never reached for owner-role commands — all three gated arms
  (out-of-scope→allow, Claude-host→ask, other-host→deny) return before the non-gated branch — *and*
  `evaluate` defensively re-checks `enforcer.gated_action` and refuses to allow a gated command — belt
  and suspenders; the `selfcheck` matrix asserts an owner-role command keeps its per-host/scope outcome
  (`ask` for Claude/in-scope, `deny` for a deny-only host/in-scope, `allow` out-of-scope) with rules
  present.
- **A corrupt/partially-written rules store causes an unpredictable allow.** Mitigation: reads are
  fail-safe toward prompting (UFR-2); the frozen per-run snapshot is written once at run start via an
  atomic write, and provenance-invalid entries are ignored (UFR-9).
- **Worktree-confinement is bypassed by symlink/`..` path tricks.** Mitigation: realpath both the
  working dir and the `~/.superheroes-worktrees/` root and require a strict-descendant relationship
  (UFR-5); a covering test exercises symlink and parent-hop cases.
- **The audit under-captures, so a real prompt family is missed and the run still stalls.** Mitigation:
  every residual timeout denial stays visible in the readout (UFR-3), so a repeatedly-prompting run is a
  visible posture gap to fix by extending `rules.json`, not a silent failure — the spec explicitly
  frames this as the intended feedback loop.

## Dependencies & assumptions

**Dependencies:** the owner-role enforcement floor (`enforcer.py` GATED_COMMANDS + hook wiring) is in
place and stays authoritative — this work's allowances are acceptable *because* it exists. The
`ref_lock` lease and the common-dir-keyed project store (`mode_registry.config_key`,
`control_plane`) already exist and are reused as-is. The review loop's existing low-confidence →
deep-retry/degraded-dimension path (FR-2), the ship gate (`ship_gate.decide`'s build-evidence +
review-terminal arms) that the draft/ready flip (`pr_phase.mark_ready_action`, `ship_phase.py`'s
`revert-draft`) already reads, and the run journal/readout (`journal*.py`, `run_readout.py`) are
extended, not rebuilt — the build-step denial is a new *input* threaded into `ship_gate.decide`'s
build-evidence arm, not a reuse of `panel_tally.roundGate`'s reviewer-roster `incomplete` gate. The Claude app's existing push notification reaches the
owner on a pending prompt (no new work). **Assumptions:** spine-composed commands are deterministic and
stable in form for a given run (makes exact-match FR-8 meaningful — stated in the spec). An
auto-allowed worktree interpreter invocation is not confined by its working dir (it can reach the
network/other paths) — owner-accepted; the enforced boundary is the owner-role floor, not the working
dir. Rule changes propagate only at run boundaries in both directions (a mid-run edit confers/narrows
nothing on the running run) — owner-accepted frozen-snapshot residual. The floor operates on the
commands the run itself issues, not on code running *inside* an already-allowed invocation — an
owner-accepted residual inherent to allowing any code execution.
