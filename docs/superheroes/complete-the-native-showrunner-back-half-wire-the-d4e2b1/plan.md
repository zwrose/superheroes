---
superheroes: doc
schemaVersion: 1
docType: plan
workItem: complete-the-native-showrunner-back-half-wire-the-d4e2b1
issue: 120
size: large
status: approved
gates: {review: passed}
producedBy: "the-architect@0.3.0"
created: "2026-06-29"
updated: "2026-06-30"
---
# Complete the native showrunner back-half — wire the deferred remediation (CI-fix loop, freshen, fence) — Plan

## Overview

The native showrunner's `shipPhase` (`plugins/superheroes/lib/showrunner.js`) today is a happy-path
stub: it reads freshness, and on anything but `up_to_date` it parks; it reads CI, and on anything but
`green`/`none` it parks. The recovery the *manual producer* already performs in `skills/workhorse/SKILL.md`
step 8 — merge the base in (bounded), fix failing checks (bounded), revert to draft on terminal failure,
hand back a structured "your turn" — is simply **not wired** into the native leaf. This work connects it.

The strategy is **mirror the manual producer's step-8 / step-9 orchestration into the native back-half,
reusing the already-parity-locked decision-makers unchanged** (`freshness.decide`, `ci_loop.decide`,
`ci_status.classify`, `pr_phase.mark_ready_action`, `journal.ci_attempts`, `readout.build_readout`). No
new decision logic is authored — the showrunner leaf becomes the *orchestrator* (it gathers world-reads,
performs the mechanical merge / push / fix / flip), and the existing pure functions remain the source of
truth for *what to do*. The native back-half follows the exact split the rest of the spine already uses
(`exec` for IO, a Python entry leaf for irreducible git/gh work, an in-process JS twin or a pure `.py`
decider for judgment), so the wiring lands as new branches inside `shipPhase` plus one Python ship-phase
entry that does the merge/fix/flip mechanics, not as a parallel framework.

Because the recovery introduces *new* autonomous pushes (catch-up merges, fix commits) and a draft-flip,
the **concurrency fence ships in the same change**: every new branch- or PR-mutating boundary does a
renew-then-fence (`fence_cli.py` / `ref_lock`) against the lease generation already threaded past build
(UFR-10), exactly as the producer fences its step-8 pushes. A generic **per-write idempotency primitive**
(read-back-confirms-the-write, append-if-absent) is built here as a reusable seam so #118 can generalize
it spine-wide rather than retrofit a second scheme. The back-half is left with clean per-stretch seams;
folding/relabelling the courier leaves is explicitly #118's job, sequenced after this.

## Goals & non-goals

**Goals (from the spec):**
- Wire base-catch-up into `shipPhase`: on `sync`, merge the base in, push (non-force), re-judge on the
  integrated head; bounded by `freshness.decide` (FR-1, FR-2, FR-5).
- Wire the fix-the-checks loop: on red CI, derive failing signatures, fix + push + re-check, bounded by
  `ci_loop.decide` with the round count replayed from the journal so it survives a crash (FR-3, FR-4, UFR-5).
- Return the PR to draft on terminal check failure (`revert_and_gate`) and hand back (FR-4).
- Fence every new branch-/PR-mutating boundary against the lease generation; fail-closed on an unreadable
  guard read (FR-9, UFR-4).
- Reconcile local↔remote PR head before judging readiness; make create / ready-flip / draft-flip idempotent
  on resume (FR-5, UFR-6).
- Produce the structured "your turn" hand-back via `readout.build_readout`, scrubbed, best-effort-but-surfaced
  (FR-6), carrying the post-review-integration note when a base merge advanced HEAD past the reviewed commit
  (FR-7).
- Honour the hard boundary: never merge the PR (FR-8); only ordinary feature-branch pushes (FR-9).
- Build the per-write idempotency guard as a **generic primitive** for #118 to generalize.

**Non-goals (deliberately excluded here):**
- **Folding/relabelling the courier leaves** — #118 owns the surface collapse *after* this settles. This
  work leaves clean per-stretch seams but does not fold or rename.
- **Changing the shared decision-makers' logic** — `freshness.py`, `ci_loop.py`, `ci_status.py`,
  `pr_phase.py` stay byte-for-byte; they are the parity source of truth, not a rewrite target.
- **Changing the manual producer** (`skills/workhorse/SKILL.md`, `build_phase.js`) — it is the behavioral
  reference, mirrored, not edited.
- **Re-running code review or the ship gate after a base integration** — the merged-in base code is reviewed
  on its own branch and CI-vetted on the integrated head; the back-half surfaces a NOTIFY (FR-7) instead.
- **A local pre-check of PR-only checks before the PR exists** — the fix-the-checks loop is the recovery.
- **A live run to a real passing ship as an acceptance gate** — confirmed via dogfooding; the gate is the
  smoke suite.
- **The stale-build-worktree backstop sweep** — routed to #42.

## Architecture

The native pipeline runs `runPhases` over `PHASES` ending in `ship` (`showrunner.js`). `shipPhase(workItem,
pr)` is the back-half. Its current shape — `freshness → ci → park` — is widened into the producer's step-8
shape while keeping the spine's IO/judgment split:

```
shipPhase(workItem, pr)
  └─ reconcile-on-entry: read remote PR head ↔ local HEAD; idempotently push local-ahead (UFR-6)
  └─ catch-up stretch  (bounded by freshness.decide)
       fence → ship_phase.py --step freshen  (gh base read, git merge, conflict-gate, non-force push)
       → re-read freshness on the pushed head
  └─ ci stretch        (bounded by ci_loop.decide, round count from journal.ci_attempts)
       fence → ship_phase.py --step ci (read checks for the reconciled head SHA) → ciStatusTwin.classify
       red → write-ahead ci_fix_attempt → fence → fix+push leaf → re-wait
       terminal → fence → ship_phase.py --step revert-draft (gh pr ready --undo) → park
  └─ hand-back: readout.build_readout(ctx) → readout_post.py (scrubbed, best-effort) → ready | parked
```

Each stretch is a **named seam**: the catch-up stretch, the ci stretch, the revert-to-draft step, and the
hand-back are separable units with their own world-read → fence → mutate → read-back shape, so #118 can fold
them without re-deriving boundaries. The decision *of what to do* never lives in the leaf — it is delegated
to the existing pure deciders (`freshness.decide`, `ci_loop.decide`, `ci_status.classify`,
`pr_phase.mark_ready_action`). The leaf only performs the mechanical git/gh work and the fence reads. This
keeps the native back-half **behaviorally parity-locked** to the producer: the same inputs route to the same
disposition because they call the same functions.

The fence is the `ref_lock` generation threaded past build (UFR-10, already in `reconcile()` →
`workhorseBuildPhase`); the back-half renews-then-fences (`fence_cli.py`) immediately before each push,
merge, draft-flip, or create — fail-closed (an unreadable fence reads as lost → park). The structured
hand-back reuses `readout.build_readout` + `readout.scrub` (test-pilot's `pr_comment.py scrub`) and is
posted by `readout_post.py`, whose `posted`/`recorded` contract already implements FR-6's best-effort-but-
surfaced delivery.

## Components & interfaces

- **`shipPhase` (`showrunner.js`) — extended orchestrator.** Inputs: `workItem`, `pr` (the loaded PR
  world-read). Output unchanged: `{ outcome: 'ready' | 'parked', phase: 'ship', reason }`. It gains the
  catch-up stretch, the ci stretch (fix loop + revert-to-draft), the entry reconcile, the per-boundary
  fence, and the structured hand-back. Error cases: any unreadable world-read or lost fence → `park`
  (never `ready`). Fits the existing `park()` helper (already posts the scrubbed readout, records on a
  failed post — FR-6).

- **`ship_phase.py` (extended Python entry).** Already exposes `--step freshness` and `--step ci`
  (`--emit-checks`). Add the mechanical steps the manual producer performs, each idempotent and
  read-back-confirmed: `--step freshen` (resolve base via `gh pr view --json baseRefName`, `git fetch`,
  `git merge origin/<base>`, conflict-gate, non-force push, return the integrated head SHA),
  `--step fix-push` (commit + non-force push **only a clean worktree carrying exactly the fixer's intended change** — a dirty or unverified tree from a crashed fixer parks fail-closed and pushes nothing; on a non-fast-forward rejection it re-fences, re-reads the **current remote PR head**, and replays the fixer commit onto *that* advanced head — never the base, never a force-push, never dropping the commit — parking if it cannot cleanly replay; returns the new head SHA), `--step
  revert-draft` (`gh pr ready --undo <N>`, idempotent), and `--step reconcile-head` (push local-ahead so
  the remote PR head equals the reconciled local HEAD; idempotent no-op when in sync). Each emits a small
  JSON `{ ok, head, reason }` the JS twin reads — no large payload crosses the pipe. Contract: every step
  **reads back** the remote state it just wrote (head SHA, isDraft) and reports the confirmed value, so the
  orchestrator never asserts a write it cannot confirm (UFR-6, FR-5).

- **Per-write idempotency primitive (new, generic — for #118).** A small reusable seam:
  `idempotent_apply(key, current_reader, apply_fn)` style — *read the current remote/durable state; if it
  already reflects the intended write (matched by a per-write key), it is a no-op; otherwise apply and
  read-back to confirm*. Built so create / ready-flip / draft-flip / push all route through one primitive
  rather than four hand-rolled checks. Interface kept narrow (a key + a reader + an applier); it lives in a
  new small lib module (e.g. `idempotent_write.py`) callable from the back-half steps. **Three real call
  sites** at minimum (ready-flip, draft-flip, the catch-up push-reconcile), satisfying the rule of three;
  #118 generalizes it to the rest of the spine's durable writes.

- **Existing parity-locked deciders — reused unchanged (interfaces are the contract):**
  - `freshness.decide(is_ancestor, attempt, max_attempts=3) -> ('up_to_date'|'sync'|'give_up_notify'|'gate', reason)`.
  - `ci_loop.decide(failing_signatures, history, rnd, max_rounds=5) -> ('fix'|'revert_and_gate', reason)`.
  - `ci_status.classify(checks) -> { status: 'green'|'red'|'none', failing: [...] }` (via `ciStatusTwin`).
  - `pr_phase.mark_ready_action(pr) -> 'skip'|'flip'|'gate'` and `mark_ready_status_action(...)`.
  - `journal.ci_attempts(events) -> (rounds, history)` and `journal.append(..., 'ci_fix_attempt', ...)`
    (write-ahead, fsync'd).
  - `readout.build_readout(ctx) -> markdown` and `readout.scrub(text, root) -> (text, ok)`.

- **`fence_cli.py` / `ref_lock` — reused.** `python3 fence_cli.py --work-item <wi> --generation <g>` →
  `{ ok, reason }`. `ok:false` (lost/stolen/unreadable) → the orchestrator parks **before** any mutation.

- **`enforcer.py` — relied on unchanged.** Permits ordinary feature-branch `git push` and `gh pr ready
  --undo`; gates the owner-authority set (`gh pr merge`, force-push, push-to-default). No change — the new
  pushes are on the permitted side; the plan confirms this rather than touches the enforcer.

## Data flow & data model

No new persistent data model. The data that moves:

- **The lease generation** (an integer) is already threaded from `reconcile()` into the build phase
  (`globalThis`/checkpoint, UFR-10); the back-half reads the same generation for its fences. No schema
  change — it is the existing `lockGeneration` already on the checkpoint.
- **The journal `ci_fix_attempt` events** (existing event type, `journal.py`) carry `{ round, failing:
  [sigs] }`; the round count is *replayed* from them (`journal.ci_attempts`), not stored as a counter —
  this is why a crash cannot reset the fix-loop bound (UFR-5). No new event type is introduced.
- **The reconciled head SHA** flows leaf → twin within a single `shipPhase` invocation as a JSON field; it
  is not persisted beyond the checkpoint's existing `pr` object.
- **The per-write idempotency key** is derived from the intended action + target (e.g. the PR number + the
  desired draft state), read against the live remote state — it is *not* a stored ledger row; idempotency
  is achieved by reading reality, consistent with the spine's reality-wins rule (CONVENTIONS §4.7). This is
  a deliberate one-way-door-avoidance: no durable idempotency table to migrate later.

Backward/forward compatibility: the checkpoint shape is unchanged (existing `lockGeneration`, `pr` fields);
an in-flight run resumed mid-back-half re-derives freshness from reality and replays the ci round count, so
an old checkpoint resumes correctly with no migration.

## How the requirements are met

- **FR-1 (freshen behind branch before judging checks):** the catch-up stretch — `freshness.decide` →
  `sync` → `ship_phase.py --step freshen` merges the base in, non-force-pushes, and the re-judge runs on the
  integrated, pushed head.
- **FR-2 (catch-up bound, reality-derived on resume):** `freshness.decide(is_ancestor, attempt,
  DEFAULT_MAX_SYNCS=3)`; `give_up_notify` stops chasing and the hand-back states the branch is behind. The
  `attempt` counter is in-session and re-derived from `git merge-base --is-ancestor` on resume (a merge
  converges, so no stored counter is needed — matches §4.7).
- **FR-3 (fix-and-re-check before hand-back):** red CI → derive signatures → `ci_loop.decide` → `fix` →
  `ship_phase.py --step fix-push` → re-wait, at least one attempt before any hand-back.
- **FR-4 (terminal failure → revert to draft + hand back):** `ci_loop.decide` returns `revert_and_gate` on
  the round cap or a recurring failing set → `ship_phase.py --step revert-draft` (`gh pr ready --undo`) +
  park with "checks could not be made to pass." "Same set" = `tuple(sorted(failing_signatures))` equality,
  as `ci_loop.decide` already implements.
- **FR-5 (judge on the ready, integrated head; reject stale pass):** the entry reconcile and the
  push-reconcile ensure the remote PR head equals the integrated local HEAD; CI is read for that head SHA,
  and a rollup belonging to an earlier commit is not accepted (the leaf reports the head SHA it read checks
  for; a mismatch reads as "no checks yet," never an older green).
- **FR-6 (structured "your turn" hand-back, durable):** `readout.build_readout(ctx)` (PR link,
  built-vs-asked, test results, CI status, spot-check list, "never merges") posted by `readout_post.py`;
  `posted`/`recorded` make it best-effort-but-surfaced (a delivery that reaches neither PR nor record is
  warned in the reason — `park()` already does this). On resume after a crash post-work-pre-handback, the
  reconcile re-enters the hand-back rather than ending silently.
- **FR-7 (post-review-integration note):** when the freshen stretch added a merge/conflict-resolution
  commit after review, the hand-back carries a NOTIFY that the final head differs from the reviewed commit
  due to base integration (mirrors workhorse step 8's review-coverage boundary).
- **FR-8 (never merge the PR):** no path calls `gh pr merge`/the API merge forms; the enforcer gates them
  unconditionally as a backstop. The hand-back ends "Merge is yours."
- **FR-9 (only ordinary pushes, never force / never default):** all pushes are non-force to the work-item's
  own branch; force-push and push-to-default are never issued and remain enforcer-gated.
- **UFR-1 (conflict → confidence-gated auto-resolve or abort):** `--step freshen` resolves only a
  trivially-correct, high-confidence conflict (commit + push, CI re-vets); anything uncertain → `git merge
  --abort` (branch head unchanged) + park asking the owner. The two observable guarantees hold: an aborted
  integration leaves the head unchanged; an auto-resolved one is pushed and re-checked before "ready."
- **UFR-2 (unreadable freshness/check read → park, not false ready):** `freshness.decide` returns `gate` on
  an undetermined ancestor read; `ship_phase.py` CI read is fail-closed (`{error}`/non-JSON → park). The
  hand-back says the state could not be confirmed.
- **UFR-3 (provider exists but no checks on the ready head → honest hand-back):** `ci_status.classify`
  `none` plus a provider-detected check yields the "checks did not run on the ready PR" message, never a
  false all-clear. Smoke: a detected provider with zero checks on the ready head → the honest "checks did
  not run" hand-back, never a green.
- **UFR-4 (concurrency guard, fail-closed):** every PR-/branch-mutating step renews-then-fences the lease
  generation (`fence_cli.py`); a lost/unreadable fence parks before the mutation — no duplicate PR, no
  undone ready-flip, no superseded push.
- **UFR-5 (fix-loop count survives crash):** the round count is replayed from the write-ahead, fsync'd
  `ci_fix_attempt` journal events (`journal.ci_attempts`), written *before* each fix push, so a resume
  continues the count rather than resetting to one.
- **UFR-6 (reconcile before proceeding; create/flip idempotent on resume):** every mutating step reads back
  the remote state and reconciles the remote PR head to the local integrated head before judging readiness;
  create / ready-flip / draft-flip route through the per-write idempotency primitive so re-issuing a
  succeeded step is a no-op.
- **NFRs:** *Safety (no false ready)* — every "ready" is backed by a confirmed-passing check on the current
  head and a base-containing branch (the reconcile + head-SHA-matched read). *Concurrency safety* — the
  fence. *Bounded autonomy* — `freshness.decide` + `ci_loop.decide` caps, plus a bounded check-wait that
  ends in an honest "checks did not complete" hand-back. *Secret hygiene* — `readout.scrub` (unscrubbable →
  dropped). *Behavior parity* — the reused deciders + the producer's existing parity fixtures.

## Key decisions & alternatives

- **Decision:** Wire the producer's recovery into the native leaf vs. invoke the manual producer skill from
  the showrunner. · **Options weighed:** (a) *Mirror* the step-8/9 orchestration in the native back-half,
  reusing the pure deciders [chosen]; (b) have the native back-half *shell out to / dispatch* the
  `workhorse` skill for the back-half. · **Choice + why:** (a) — the spine is deliberately native/
  code-execution (#115); dispatching the prose skill reintroduces the per-op agent overhead #115 removed and
  couples the two pipelines. The strongest case for (b): zero duplication and guaranteed parity by
  construction. We beat it by reusing the *same pure deciders* (parity by shared function, not by shared
  prose) — duplication is only the thin mechanical orchestration, which is exactly the seam #118 will fold.
  · **Accepted downside:** the mechanical merge/fix/flip orchestration exists in two places (producer prose
  + native leaf) until #118; a producer-side behavior change must be mirrored. · **Reversible?** two-way (the
  native back-half is a contained leaf). · **Mode:** PROCEED. · **Reverse path:** revert the leaf change. ·
  **Expiry:** n/a. · **Escalated?** no — engineering-internal, the spec mandates parity-via-reuse.

- **Decision:** Idempotency by reading reality vs. a durable per-write ledger. · **Options weighed:** (a)
  derive idempotency from the live remote/durable state read-back (no stored ledger) [chosen]; (b) a durable
  applied-writes ledger keyed per write. · **Choice + why:** (a) matches the spine's reality-wins rule
  (CONVENTIONS §4.7) and avoids a new persistent data model that would be a one-way door to migrate; the PR's
  actual `isDraft`/`headRefOid` *is* the truth. Strongest case for (b): an explicit audit trail of writes.
  We beat it because the remote state is already authoritative and a ledger would need its own crash-safety
  + migration. · **Accepted downside:** idempotency depends on a readable remote state; an unreadable read
  fails closed to a park (acceptable — never a false ready). · **Reversible?** two-way (the primitive is a
  narrow seam). · **Mode:** PROCEED. · **Reverse path:** swap the primitive's internals. · **Expiry:** n/a.
  · **Escalated?** no.

- **Decision:** Build the idempotency guard as a generic primitive now vs. hand-roll per step and let #118
  generalize. · **Options weighed:** (a) one generic `idempotent_apply` seam with ≥3 call sites here
  [chosen]; (b) four hand-rolled checks, #118 unifies later. · **Choice + why:** the spec explicitly asks
  this work to build the guard as a generic primitive so #118 generalizes rather than retrofits a divergent
  scheme; the rule of three is met (ready-flip, draft-flip, push-reconcile). Strongest case for (b): less
  abstraction up front. We beat it because the spec names the cross-reference and three real call sites exist
  today. · **Accepted downside:** a small new module before #118 consumes it spine-wide. · **Reversible?**
  two-way. · **Mode:** PROCEED. · **Reverse path:** inline it. · **Expiry:** n/a. · **Escalated?** no.

- **Decision:** Re-derive the catch-up bound from reality (no stored counter) but persist the fix-loop
  round count. · **Options weighed:** (a) freshness re-derives from `is_ancestor` on resume, ci replays from
  the journal [chosen]; (b) store both counters durably. · **Choice + why:** a base merge *converges*
  (monotonically toward containing the base), so freshness cannot crash-loop and needs no stored counter
  (FR-2 note); a CI fix can recur identically, so its bound MUST survive a crash (UFR-5) — hence the
  write-ahead journal. Strongest case for (b): symmetry. We beat it because the two loops have genuinely
  different crash semantics; a stored freshness counter would be dead weight that could *under*-count on a
  reality change. · **Accepted downside:** the two loops bound themselves differently (asymmetry to
  understand). · **Reversible?** two-way. · **Mode:** PROCEED. · **Escalated?** no.

- **Decision:** Conflict auto-resolution scope (UFR-1's "trivially-correct, high-confidence" class). ·
  **Options weighed:** (a) restrict auto-resolve to conflicts the cooperative layer is highly confident are
  trivially correct, abort everything else [chosen, fail-closed default]; (b) attempt a broader
  auto-resolution. · **Choice + why:** the spec fixes the fail-closed default (uncertain → abort + hand
  back) and the two observable guarantees (aborted = head unchanged; auto-resolved = pushed + re-checked);
  the precise class is a plan call left deliberately narrow — a wrong auto-resolve must surface as a failing
  check, never ship as ready. Strongest case for (b): fewer owner hand-backs. We beat it because a guessed
  merge is the exact failure the spec forbids. · **Accepted downside:** more owner hand-backs on
  non-trivial conflicts. · **Reversible?** two-way. · **Mode:** PROCEED (fail-closed). · **Escalated?** no —
  the spec pre-authorizes the fail-closed default.

- **Decision (NOTIFY):** Reuse the producer's default bounds (`DEFAULT_MAX_SYNCS=3`, `DEFAULT_MAX_ROUNDS=5`)
  rather than introduce new native-specific limits. · **Choice + why:** parity demands the same disposition
  for the same inputs; new limits would diverge native from manual. · **Accepted downside:** if the owner
  wants a different native bound, it is a config change later. · **Reversible?** two-way. · **Mode:**
  NOTIFY. · **Reverse path:** thread a config override before build. · **Expiry:** before build. ·
  **Escalated?** no — surfaced as a heads-up, reversible.

## Cross-cutting concerns

- **Security & privacy:** No new PII, no new trust boundary, no authn/authz change. The one privacy surface
  is **secret leakage in the hand-back**: any CI-log excerpt passes through `readout.scrub` (backed by
  test-pilot's `pr_comment.py scrub`); unscrubbable text is dropped, never shown (NFR secret hygiene). The
  new pushes stay on the enforcer's permitted side; the owner-authority set (merge / force-push /
  push-to-default) remains enforcer-gated as a deterministic backstop — the fixer cannot widen its own push
  surface. **Secret hygiene covers *every* PR-bound sink, not just the hand-back:** the only text the
  back-half interpolates from CI logs is the hand-back excerpt (scrubbed above); the CI-fixer commits **code
  changes only** and never writes raw CI-log content into a commit, and the existing review-code pass + CI
  secret-scan vet the fixer's diff as a backstop — so neither the hand-back nor a fixer commit becomes an
  unscrubbed secret sink.

- **Observability:** The journal (`journal.py`) is the 2am-debug surface — `step_entered`/`step_completed`,
  `ci_fix_attempt` (round + failing set), `parked`, lease events — replayable to reconstruct exactly why a
  run caught up N times, fixed M rounds, or reverted to draft. The hand-back readout itself is the
  owner-facing signal (PR link, CI status, what blocked it). On-call reads the journal + the parked
  reason + the PR comment; no new telemetry system is needed.

- **Reliability & failure modes:** Critical dependencies that *fail-closed to a park*: the control-plane
  store / lease (`ref_lock`), `gh` reads (freshness, checks, PR head), and the fence. Each unreadable or
  lost read parks rather than asserting "ready" — the spine's reality-wins posture (§4.7). The bounded
  check-wait degrades to an honest "checks did not complete" hand-back rather than hanging. The hand-back
  delivery is the one *non-critical* write: it is best-effort-but-surfaced and the run does **not** advance
  or ship-gate on it landing (matches #118's readout carve-out).

- **One rule governs every back-half push (the fix-push partial-failure invariant).** A push happens only
  for a **clean worktree carrying exactly the intended change**; on a non-fast-forward rejection it
  reconciles against the **current remote PR head** (re-fence, re-read, replay onto that head) or **parks
  fail-closed** — never the base, never a force-push, never dropping or fabricating a commit, never pushing
  a dirty tree. This single invariant covers the whole class of fix-push partial failures (a crashed fixer,
  an advanced remote head, a partial prior apply): anything that cannot be made clean-and-fast-forward parks
  rather than guesses, consistent with the spine's reality-wins, fail-closed posture (§4.7).

- **Verification — every requirement gets a smoke (no per-requirement gap).** The tasks doc enumerates one
  node smoke (or assertion) **per FR and UFR** (FR-1..FR-9, UFR-1..UFR-6), plus the partial-failure smokes
  named in Risks (dirty-tree-at-fix-push; advanced-remote-head-at-fix-push; stale-generation fence;
  crash-replayed ci-count; already-succeeded create/flip; the UFR-3 zero-checks-on-ready-head honest
  hand-back). The deciders stay parity-locked to their existing fixtures; the new showrunner-level wiring is
  what the smokes exercise — each one drives the requirement's **observable behavior**, not merely a flag.
  This is the convergence floor: no requirement ships without its smoke, so coverage is complete by
  construction rather than chased finding-by-finding.

## Rollout & migration

N/A — no schema migration. This is an internal engine change behind the existing showrunner entry; there is
no user-facing surface and no stored data shape change (the checkpoint's `lockGeneration`/`pr` fields are
reused as-is). **Rollback:** revert the `showrunner.js` + `ship_phase.py` + new-primitive commit; the
back-half returns to its current happy-path-park behavior with no residue (no migration to unwind, no flag
to flip). An in-flight run resumed across the rollback boundary re-derives freshness from reality and
replays the ci count, so neither direction corrupts a run. There is no kill-switch flag because the change
*is* the back-half wiring — disabling it means reverting it; that is acceptable for an internal,
behind-the-entry engine change validated by the smoke suite before merge.

## Risks & mitigations

**Pre-mortem — "it's six months out and this failed in production, why?":**

- **Parity drift** — a producer-side step-8 change isn't mirrored into the native leaf, so the two diverge.
  *Mitigation:* the native back-half calls the *same* pure deciders (`freshness.decide`, `ci_loop.decide`,
  `ci_status.classify`), held to the existing parity fixtures; only the thin mechanical orchestration is
  duplicated, and #118 will fold it. A parity smoke asserts same-input → same-disposition.
- **A false "ready" from a stale check rollup** — a green read adopted for an earlier commit. *Mitigation:*
  the leaf reports the head SHA it read checks for; a rollup belonging to a different SHA reads as "no checks
  yet," never an older green (FR-5); the entry/push reconcile guarantees the judged head is the remote head.
- **A concurrent run corrupts the PR** — a superseded run pushes or re-flips. *Mitigation:* renew-then-fence
  before every mutating step, fail-closed on an unreadable fence (UFR-4). Smoke: a stale-generation fence →
  park before write.
- **A crash resets the fix-loop bound, letting it exceed the cap** — *Mitigation:* write-ahead, fsync'd
  `ci_fix_attempt` events replayed on resume (UFR-5). Smoke: prior rounds in the journal → the next round
  respects the cap.
- **A guessed merge ships** — a non-trivial conflict auto-resolved wrong. *Mitigation:* confidence-gated
  auto-resolve, abort-to-unchanged-head + park otherwise; any auto-resolve is pushed and re-checked so a
  wrong one surfaces as a failing check (UFR-1).
- **The hand-back silently vanishes** — disk full fails both the post and the record. *Mitigation:*
  `readout_post.py`'s `posted`/`recorded` contract; neither → the parked reason carries a warning, never
  dropped (FR-6); the run still parks honestly.
- **An idempotency miss double-creates / double-flips on resume** — *Mitigation:* the per-write primitive
  reads the live state and no-ops when it already reflects the intended write (UFR-6). Smoke:
  already-succeeded create/flip on resume → no-op.
- **A crashed fixer's dirty tree gets pushed as "the fix"** — the fix step commits whatever is in the
  worktree, so a fixer that dies mid-edit ships a partial or garbage commit. *Mitigation:* `--step fix-push`
  has a **clean-tree precondition** — it commits and pushes only a clean worktree carrying exactly the
  fixer's intended change; a dirty or unverified tree parks fail-closed (the fixer's failure surfaces; no
  commit is pushed). Smoke: a dirty worktree at fix-push → park, no push.
- **The fixer commit is dropped on a non-fast-forward push** — the push is rejected because the remote PR
  head advanced (a concurrent push, or a partial prior apply), and a naive recovery reconciles against the
  *base*, discarding the fixer's commit. *Mitigation:* on a non-fast-forward rejection `--step fix-push`
  re-fences, re-reads the **current remote PR head**, and replays the fixer commit onto *that* head (never
  the base, never a force-push); if it cannot cleanly replay, it parks fail-closed rather than drop the
  commit or force. Smoke: an advanced remote head at fix-push → replay-onto-PR-head or park, never a
  base-reset, never a force-push.

## Dependencies & assumptions

**Dependencies (built elsewhere, relied on here):**
- The parity-locked deciders already exist and are the source of truth: `freshness.py`, `ci_loop.py`,
  `ci_status.py`, `pr_phase.py`, `journal.ci_attempts`, `readout.build_readout`/`scrub`,
  `readout_post.py` — this work *connects* them, not redesigns them.
- The lease generation is already threaded past build (UFR-10, `reconcile()` → `workhorseBuildPhase`); the
  back-half consumes the same generation. `fence_cli.py` / `ref_lock` provide renew-then-fence.
- `enforcer.py` already permits ordinary feature-branch pushes and `gh pr ready --undo` and gates the
  owner-authority set; this work relies on that behavior unchanged.
- The control-plane store / journal / checkpoint substrate is in place (`control_plane.py`, `journal.py`,
  `checkpoint.py`).

**Sequencing:** lands **before #118**, which folds/relabels the same back-half leaves *after* this surface
settles. This work leaves clean per-stretch seams and documents the fence seam, but does **not** fold
couriers or relabel leaves. The per-write idempotency primitive is built generic here for #118 to
generalize spine-wide (#118 FR-4) — its design is owned by this plan.

**Assumptions (the build/review can check):**
- The remote PR head (`headRefOid`) and `isDraft` are readable via `gh pr view` at each step (an unreadable
  read fails closed to a park — not a parked question, a designed behavior).
- The repo runs CI on ready/non-draft PRs; if a provider exists but no checks run on the ready head, the
  hand-back is honest (UFR-3), not a false all-clear.
- The producer's default bounds (3 syncs, 5 ci rounds) are the right native bounds (NOTIFY above — reversible
  before build if the owner prefers different native limits).

## UI / UX

N/A — this is an internal engine change with no user-facing interface. The only owner-facing surface is the
hand-back, a plain-text PR comment produced by `readout.build_readout` (PR link, built-vs-asked, test
results, CI status, a spot-check checklist, and "Merge is yours — the showrunner never merges"); its content
and durable-delivery behavior are specified under FR-6 and reuse the existing readout/scrub/post path, so no
new UI is designed here.
