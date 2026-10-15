---
superheroes: doc
schemaVersion: 1
docType: spec
workItem: collapse-the-showrunner-haiku-courier-surface-to-o-9942f1
issue: 118
size: large
status: draft
gates: {review: pending}
producedBy: "the-architect@0.3.0"
created: "2026-06-29"
updated: "2026-06-29"
---
# Collapse the showrunner haiku-courier surface to one leaf per stretch

## Purpose

The showrunner runs inside a sandbox with no shell and no filesystem. Its only way
to touch the real world — git, the deciders, files — is to dispatch a cheap "courier"
leaf (a haiku model) that runs a command and hands back its output. The courier
carries no judgment, yet it is the run engine's single biggest source of fragility:
across the last build-and-eval campaign it dropped output, returned a field instead
of the whole result, and even *fabricated* a plausible "success" it never read. Those
failures are silent — they either park a perfectly healthy run for no reason, or (the
dangerous twin) let a write that actually *failed* look like it succeeded.

This work collapses that surface. Every stretch of deterministic work between two
genuine model dispatches will make at most **one** trip to the courier (often none),
and every durable write will be confirmed by reading back its real resulting state —
so a dropped, garbled, or fabricated courier answer can never advance the run on a
result that didn't happen. Runs get faster and cheaper, false parks largely disappear,
and the silent "failed-write-looks-fine" hole is closed.

## Who it's for

- **The owner running the showrunner** — wants runs that are quick, cheap, don't park
  for phantom reasons, and never quietly proceed on a write that didn't land.
- **A maintainer adding or changing a phase** — wants one clear, enforced rule for how
  a new phase talks to the real world, so the courier surface stays small by default.

## Functional requirements

**FR-1.** The showrunner shall fold every courier leaf a single gather could combine, so each
deterministic stretch (the run of deterministic work between two genuine model dispatches)
issues **at most one courier leaf by default** — zero when the stretch is pure judgment. A
second leaf in a stretch is permitted only as a **deliberate, logged exception**, never as
unremoved redundancy.
  - *Acceptance (rule):* the smoke suite asserts, **per deterministic stretch**, that the
    stretch dispatches ≤1 courier leaf *unless* it carries a recorded justification, and it
    **surfaces** every justified 2-leaf stretch (reports it, rather than silently passing it). A
    2-leaf stretch with no logged justification fails the check. The only admissible
    justifications are (a) isolating the highest-stakes gate — the lease/reconcile world-snapshot,
    kept its own call per the issue's 2a (3→2, not 3→1) — or (b) keeping an idempotent-retry unit
    small enough to stay safe on replay. (A stretch is delimited by the genuine-model dispatches
    that bracket it, so leaves are countable per stretch, not just per phase.)
  - *Acceptance (baseline):* the concrete per-phase leaf counts (the baseline **captured on main
    with #120 merged** → the folded target) are pinned in the **plan** once the folds settle; the
    smokes additionally assert that no phase's total leaf count regresses against that
    #120-inclusive baseline.

**FR-2.** Where a deterministic decision is a pure function of facts already gathered,
the showrunner shall reach that decision in-process, dispatching no courier leaf for it.
  - *Acceptance (Given-When-Then):* Given a test-pilot run whose applicability,
    result-aggregation, budget, and retry decisions are pure functions of gathered facts,
    when the phase runs, then those decisions dispatch zero courier leaves; a
    `not_applicable` test-pilot phase dispatches no courier leaf for any of them.

**FR-3.** When a deterministic stretch needs facts from the real world, the showrunner
shall gather them with a single courier leaf that returns all of that stretch's facts (a
folded read-decide-act leaf may also perform the stretch's writes and read-backs — FR-5).
  - *Acceptance (Given-When-Then):* Given the startup stretch, when it runs, then the spec-gate
    and model-tier-override reads are one gather leaf rather than separate reads (the
    lease/reconcile snapshot stays its own call — FR-1's logged exception). Given a stretch whose
    reads depend on one another (resolve a path, then read at that path), when it gathers, then
    the dependent reads are performed inside that single leaf, not across separate leaves.
  - *Acceptance (per-step facts):* the single leaf returns each step's raw fact as a distinct
    item, not one collapsed blob — so if the leaf drops, the runtime can name which step failed
    (satisfying UFR-1's distinction between a courier-transport failure and a real gate failure)
    and the one-shot retry stays debuggable.

**FR-4.** When the showrunner records a durable result the run's advancement depends on —
any review gate, journal entry, cursor, provenance stamp, created PR, lease acquisition,
or test-pilot status — it shall confirm the write by reading back the resulting persisted
state and checking a content value that uniquely identifies success. This bar applies to
every such write as a class, so a durable write added later inherits it by default.
  - *Acceptance (rule):* the run advances only when a distinctive content value from the
    read-back matches what was expected (for example the resulting commit SHA, the PR
    number, the recorded cursor, or the held lease generation) — never on a bare
    `{"ok":true}` or a single success word.
  - *Acceptance (carve-out):* a best-effort write the run does **not** advance on — the
    deferred-finding set, the carried-minor rollup, the readout post — needs no read-back,
    because its failure is already fail-closed by other means (an under-count keeps a
    finding blocking; an undelivered readout is surfaced in the park reason). The Labels
    section marks which writes are read-back and which are best-effort, so the distinction
    is explicit rather than an accidental omission.
  - *Acceptance (batched write):* a write batch that records more than one durable effect
    (for example gate + journal + cursor) must confirm each effect it claims, or fail
    closed — a read-back of a single value that could pass while another effect in the same
    batch did not land is not sufficient.

**FR-5.** The showrunner shall keep every proceed-or-park decision in the runtime,
derived from gathered facts; a courier leaf shall carry only facts (raw output or
resulting state), never a decision.
  - *Acceptance (Given-When-Then):* Given a deterministic script that reads, decides, and
    acts in one leaf, when it returns, then the run's advance/park is re-derived in-process
    from the returned facts; no control-flow branch trusts a decision word transported by
    the courier.
  - *Acceptance (negative):* Given a courier result that contains a fabricated decision
    word the command never printed (e.g. an injected "proceed"/"ship" token), when the
    runtime evaluates the stretch, then that word changes nothing — the advance/park is
    re-derived from the facts — symmetric to the fabricated-confirmation guard in UFR-2.

**FR-6.** The showrunner shall write each **distinct durable entry exactly once** — no
double-apply on retry or resume — so a phase's journal entry and cursor are never duplicated,
and a legitimate per-round append (for example the ship CI-fix `record CI round`) is written
once per round rather than re-appended when its leaf is retried.
  - *Acceptance (Given-When-Then):* Given a review-plan or review-tasks phase, when it
    completes, then its journal entry and its checkpoint are each written one time (the
    prior duplicate write is gone).
  - *Acceptance (replay):* Given a courier drop after a folded leaf partly applied (a durable
    entry appended) but before its read-back, when FR-8 retries the leaf, then that entry is
    **not** appended a second time — a retried or resumed durable write detects the
    already-applied state rather than blindly re-appending. *(The idempotency mechanism is
    #120's existing `idempotent_apply` primitive generalized to this append; only the
    per-entry design — the append's key and reality-reader — is the plan's, built on that
    primitive. See Assumptions.)*

**FR-7.** While a review loop runs, the showrunner shall hold the set of deferred findings
in memory across rounds — dropping the per-round disk re-read — while keeping the set
durably backed so a mid-loop resume rehydrates it rather than restarting empty.
  - *Acceptance (rule):* a multi-round review loop dispatches no per-round courier *read*
    of the deferred-finding set.
  - *Acceptance (resume):* Given a crash or context-compaction part-way through a review
    loop, when the run resumes, then it continues with the accumulated deferrals intact —
    no already-deferred finding re-blocks and no carried minor is lost — because the set is
    still durably recorded even though it is no longer re-read each round.

**FR-8.** Where a courier leaf returns an empty or unparseable result although its
command ran, the showrunner shall retry that leaf once before deciding.
  - *Acceptance (rule):* every remaining courier read and write site rides a one-shot
    retry on a pure drop; a drop that recovers on retry does not park the run.

**FR-9.** The showrunner's design notes shall state the one-leaf-per-stretch principle
and its read-back safety condition, so a new phase can follow it without re-deriving it.
  - *Acceptance (rule):* `CONVENTIONS.md` §10 (orchestration model) states the principle
    ("one fact-gather per deterministic stretch; the runtime judges from rich facts") and
    the safety condition (durable writes are verified by reading back distinctive content).

**FR-10.** The showrunner shall give every leaf and agent a label that describes what it
does, changing display only and never control flow.
  - *Acceptance (Given-When-Then):* Given the relabel, when a run is displayed, then every
    leaf and agent shows the label listed in the Labels section (several genuine-model
    agents keep their current name, marked *unchanged* there); model resolution and control
    flow are unchanged; smokes that route by label pass under the new labels. The complete
    current→label mapping is the **Labels** section below.

## When things go wrong (significant unhappy paths)

**UFR-1.** If a courier leaf's result is still missing or unparseable after its one
retry, then the showrunner shall park the run rather than advance on unverified state,
with a reason that distinguishes a courier-transport failure from a real gate failure.
  - *Acceptance:* Given a leaf that drops on both attempts, when the stretch needs its
    facts, then the run parks and the readout names a courier-transport failure — not a
    fabricated gate result.

**UFR-2.** If a durable write's read-back content does not match the expected success
value — a write that genuinely failed, or one whose confirmation was fabricated — then
the showrunner shall park the run and shall not treat the write as successful.
  - *Acceptance:* Given a write whose true result is failure (or whose confirmation is a
    plausible fabrication), when the read-back content is checked, then the mismatch parks
    the run, closing the silent path where a failed write looked successful.

**UFR-3.** If a run resumes after a park or crash that happened mid-stretch, then the
showrunner shall re-gather and continue without repeating an already-applied durable
action — whether that action created a PR, stamped provenance, or appended a journal,
cursor, or deferred-set record.
  - *Acceptance:* Given a folded read-and-act step (or a folded write batch) that already
    applied its durable effect, when the run resumes or FR-8 retries, then it adopts the
    existing result rather than duplicating it.

**UFR-4.** If the collapse changes how a stretch gathers its facts, then the
showrunner's observable run behavior — which gates pass, when it parks, the PR it hands
back — shall be unchanged except for the intended improvements (fewer leaves, no false
park on a recovered drop, no silent failed-write, the new labels).
  - *Acceptance:* the existing smoke and gate suite stays green, and new assertions cover
    the per-stretch leaf bar (FR-1), the single journal/cursor write (FR-6), and the
    read-back verification (FR-4).

## Non-functional requirements

- **Efficiency (outcome):** a full run makes fewer courier trips than today — every
  deterministic stretch sits at ≤1 courier leaf by default (any 2-leaf stretch carrying a logged
  justification), and no phase's total leaf count regresses against the #120-inclusive baseline.
  *(Fit: the smoke suite asserts the per-stretch ≤1 default, surfaces each justified exception,
  and runs the per-phase no-regression check.)*
- **Reliability (outcome):** a single courier drop, garble, or fabricated confirmation
  never advances the run on a result that didn't happen, and never parks a healthy run
  that a one-shot retry would have recovered. *(Fit: the UFR-1 and UFR-2 tests pass.)*
- **Maintainability (outcome):** a maintainer can satisfy the one-leaf bar for a new
  phase by following the documented principle alone. *(Fit: the FR-9 design note plus the
  per-phase leaf-count smokes act as a standing regression gate.)*

## Definition of done / success

The showrunner runs end-to-end with every deterministic stretch at ≤1 courier leaf by default
(any 2-leaf stretch carrying a logged justification, e.g. the deliberately-isolated
lease/reconcile gate); the test-pilot pure deciders dispatch no courier leaves; every durable
write the run advances on is confirmed by reading back a distinctive content value — reusing
#120's `idempotent_apply` primitive, generalized to the remaining durable writes — so a retried
or resumed write never double-applies; the review-doc duplicate journal write is gone and the
deferred-finding set is held in memory with a durable backing that survives a mid-loop resume;
every remaining courier site rides a one-shot retry; the one-leaf principle and its read-back
safety condition are documented in `CONVENTIONS.md` §10; every leaf and agent carries its
Labels-section label (label-routed smokes updated); and the full validator + test + node-smoke
gate is green — with the leaf-count baseline captured on main-with-#120 — and new per-stretch
leaf-count (justified exceptions surfaced), no-double-apply, read-back, and resume-idempotency
assertions added.

## Assumptions & dependencies

- This builds on the prior native-spine work (#115) — the in-process judgment twins and the
  courier one-shot-retry — and on the merged back-half (#120), which **settled the courier
  surface this work collapses**. #120 left an explicit **seam map** above `shipPhase` naming
  the four back-half stretches (entry reconcile, base catch-up, CI-fix, hand-back) and their
  shared shape (world-read → renew-then-fence → mutate → read-back-confirm); this work folds
  and relabels those leaves per that map.
- Read-back verification of a *result* write anchors on values that already exist as durable
  content — a commit SHA, a PR number, the recorded cursor — so the runtime always has an
  unfabricatable value to check.
- The per-write idempotency guard **already exists**: #120 landed a generic, reusable
  primitive — `idempotent_write.idempotent_apply` (read-reality / apply-once / fail-closed) —
  already wired at three PR-mutation sites (push-reconcile, draft-flip, ready-flip). FR-4 and
  the journal / cursor / deferred-set / CI-round idempotency **generalize this existing
  primitive** to the remaining durable writes rather than inventing a mechanism — which
  **shrinks this work's scope and risk**. The per-entry *design* for an append-shaped write
  (its key and reality-reader) stays a plan concern, but built **on** the primitive, not from
  scratch. (The one existing content key, §6.3, is per-work-item and cannot by itself tell
  one journal entry from another — the primitive's reality-reader, not that key, is what makes
  an append idempotent.)
- **Fold and idempotency are one package (plan ordering).** A folded read-decide-act leaf
  re-runs *all* its writes on its one-shot retry (FR-8), so a stretch may be folded to a single
  leaf only once every durable write in it is idempotent-on-replay (the FR-4 / FR-6 generalization
  of `idempotent_apply`). The plan must make a stretch's writes idempotent **before** folding that
  stretch — folding first would let a dropped-but-ran leaf double-apply on retry.
- The relabel runs **last**, after the folds settle which leaves survive; its only effect
  is the displayed name and the smokes that route by it.
- The FR-1 leaf-count **baseline is captured on main with #120 merged** (the settled
  back-half), so the no-regression check counts against #120's real leaf set, not the older
  back-half.
- The fold reaches ≤1 per stretch everywhere; the plan **confirms** the folds and sequences
  their preconditions, rather than re-deciding feasibility: (a) the lease/reconcile world-snapshot
  is the one deliberately-isolated leaf (FR-1's logged exception), kept its own call; (b) the fence
  folds into its stretch's single leaf with lease freshness preserved (renew-then-mutate stay
  adjacent inside the one script) — at the per-task site and the four ship sites; and (c) the green
  ship path (reconcile → base catch-up → CI-read → hand-back) folds to one leaf, and each CI-fix
  inter-agent stretch (the `fix-ci` agent is the boundary) folds to one leaf, once their writes
  (the round record, the fences) are made idempotent per the coupling above. See the Coverage table.

## Constraints

- The collapse must not fold across a genuine model dispatch — a worker, a reviewer, a
  synthesis judge, an author, or a fixer is a hard stretch boundary.
- Judgment must never move onto the courier leaf. A deterministic script may read,
  decide, and act in one leaf, but only by returning rich facts the runtime re-verifies —
  it must never return a decision word the runtime then trusts.
- Every read-back must key off a value the courier cannot plausibly fabricate — a commit
  SHA, a PR number, a cursor, or a content hash — never a bare `{"ok":true}` or a single
  status word.
- Run state stays in the runtime's memory; gather-scripts stay thin (self-contained IO
  plus read-back), never fat scripts that re-derive run state from disk on every call.

## Out of scope

- Automatically syncing a branch that is behind its base at ship time — that case still
  parks; it belongs to the separate back-half deepening work (#120).
- Any change to *what* the genuine model agents (worker, reviewer, author, fixer) decide
  — this work is about the plumbing around them, not the quality of their judgment.
- Adding new phases or pipeline steps.

## Open questions

None. The remaining items are plan **confirmations**, not open questions: the fold reaches ≤1
per stretch everywhere (the one deliberately-isolated leaf is the lease/reconcile gate — FR-1's
logged exception), gated on making each stretch's writes idempotent first (the fold↔idempotency
coupling). Recorded under Assumptions and in the Coverage table — not left open here.

## Labels

The relabel (FR-10) is display-only. Two kinds of label exist: **genuine-model agents**
(real judgment) and **courier / dumb-pipe leaves** (run a command, return output). The
courier half below is grouped **by phase** and shows the **fold**: each *current* leaf's fate
is one of **[own leaf]** (it survives as its stretch's single leaf), **[folds into …]** (it
merges into a sibling's read-decide-act leaf — the name in that cell is the surviving leaf you
sign off on), or **[deleted → twin]** (a pure decider becomes in-process judgment, FR-2). Only
the **surviving** leaves get a label. The exact fold boundaries are the plan's to finalize
(the intent is ≤1 leaf per stretch, FR-1) — this table is the intended surviving set + naming
for your sign-off.

### Genuine-model agents (judgment)

| Current | Proposed | What it does |
| --- | --- | --- |
| `produce-plan` / `produce-tasks` | `author-plan` / `author-tasks` | Writes the plan / tasks definition-doc from its approved parent and stamps the completion marker. |
| `architecture-reviewer:r{n}` … `premortem-reviewer:r{n}` | *(unchanged)* | One of the five reviewers reviews the doc against the rubric for round *n*. |
| `synthesis:r{n}` | *(unchanged)* | Panel synthesis judge — decides keep/drop and severity for each merged finding. |
| `doc-reviser` | `revise-doc` | Revises the doc to resolve the round's blocking findings. |
| `worker` | `implement-task` | Implements task *N* test-first; reports done / needs-context / plan-wrong with evidence. |
| `review` | `task-reviewer:r{n}` | Reviews task *N* (spec-compliance + code-quality) for round *n*. |
| `fixer` | `fix-task` | Fixes the per-task review's blocking findings and commits them. |
| `reviewer:{n}` | `branch-reviewer:r{n}` | Whole-branch final review over the new HEAD for round *n*. |
| `final-fixer` | `fix-branch` | Fixes the whole-branch final-review findings. |
| `architecture-reviewer:r{n}` … (code panel) | *(unchanged)* | One of the five code reviewers reviews the built change for round *n*. |
| `synthesis:r{n}` (code panel) | *(unchanged)* | Synthesis judge for code-review findings. |
| `code-fixer` | `fix-code` | Fixes blocking code-review findings and commits to the change under review. |
| `test-pilot-plan` | `plan-tests` | Derives the browser test plan for the branch head. |
| `test-pilot-browser` | `browser-pass` | Runs the browser test pass within the allowed origins. |
| `test-pilot-fixer` | `fix-app-bug` | Fixes app bugs the browser pass surfaced and commits them. |
| `fix` (ship CI-fixer, from #120) | `fix-ci` | Fixes the failing CI checks on the ready PR and commits them. *(Newly surfaced by the #120 merge — a genuine-model agent in the back-half CI-fix loop; naming follows the approved `fix-*` scheme.)* |

### Courier / dumb-pipe leaves (grouped by phase, showing the fold)

Columns: the **current** leaf → the **surviving leaf** it becomes (the label to sign off on) → its **fate**. A read-back leaf is marked *(rb)*; a best-effort leaf *(be)*.

**Every phase — the tail (this is the double-journal fix, FR-6):**

| Current leaf(s) | Surviving leaf | Fate |
| --- | --- | --- |
| `journal_entry` + `checkpoint_entry` (+ `set-gate` at review phases) | `save phase progress` *(rb)* | 3 current writes → **1** (the redundant second journal/cursor is gone) |

**Startup — the one deliberately-two-leaf stretch (FR-1 logged exception):**

| Current leaf | Surviving leaf | Fate |
| --- | --- | --- |
| `recover_entry --snapshot` | `read world-snapshot` *(rb)* | **own leaf** — the isolated highest-stakes lease/reconcile gate (2a) |
| `read-gate spec` + `model_tier_overrides` | `read startup state` | folds → **1** gather |

**Produce (plan / tasks):**

| Current leaf | Surviving leaf | Fate |
| --- | --- | --- |
| `front_half_usable --emit-signals` | `read {plan,tasks} draft` | **own leaf** |
| `front_half append-notify` | folds → `save phase progress` *(be)* | folds into the tail |

**Doc-review (review-plan / review-tasks):**

| Current leaf | Surviving leaf | Fate |
| --- | --- | --- |
| `read-gate` (idempotent skip) | `read gate` | **own leaf** |
| deferred-set re-read (per round) | — | **deleted → in memory** (FR-7) |
| accumulator / extras / terminal-record IO + `record_deferred` | `save round state` *(be)* | folds → **1** per round |

**Build (workhorse):**

| Current leaf(s) | Surviving leaf | Fate |
| --- | --- | --- |
| `build_entry` + `task_list` + `build_state gather` (+ `reset-uncommitted`) | `gather build state` | folds → **1** entry gather |
| `fence_cli` (per task, pre-worker) | folds → its stretch's leaf *(rb)* | **folds in** — like the ship fences (renew→mutate stays tight); it shares its stretch with the entry gather (first task) or the prior task's `record task reviewed`, so it is not alone |
| post-worker `build_state gather` + `journal_entry` | `record task built` *(rb)* | folds → **1** |
| `minor_rollup` + `record-reviewed` | `record task reviewed` *(rb)* | folds → **1** |
| `verify_command` + `minor_rollup` (final) | `read verify + minors` | folds → **1** |
| `record-final-review` + `prov_entry` | `stamp build coverage` *(rb)* | folds → **1** |

**Review-code:**

| Current leaf(s) | Surviving leaf | Fate |
| --- | --- | --- |
| `build_entry` + `rev-parse head` + `review_code_config` + cwd-head | `resolve review target` | folds → **1** gather |
| `verify_gate` (per round) | `run verify` | **own leaf** (per round) |
| deferred-set re-read | — | **deleted → in memory** (FR-7) |
| final-head + `prov_entry` (on clean) | `stamp review coverage` *(rb)* | folds → **1** |

**Draft-PR / mark-ready:**

| Current leaf(s) | Surviving leaf | Fate |
| --- | --- | --- |
| `pr_entry --emit-world` + `pr_entry --step draft` | `open draft PR` *(rb)* | folds → **1** read-decide-act (via `idempotent_apply`) |
| `pr_entry --step mark-ready` | `mark PR ready` *(rb)* | **own leaf** (via `idempotent_apply`) |

**Test-pilot:**

| Current leaf(s) | Surviving leaf | Fate |
| --- | --- | --- |
| `test_pilot_context` (+ `build_entry` + head) | `read test context` | folds → **1** gather |
| `seed` + `artifacts` + `server resolve/launch/finish` | `prepare test run` | folds per stretch |
| `test_pilot_status write` (per milestone) | `write test status` *(rb)* | **own leaf** (one kind, many sites) |
| `test_pilot_publish` | `publish tested head` *(rb)* | **own leaf** |
| `applicability` / `budget` / `aggregate` / `retry` | — | **deleted → twins** (FR-2) |

**Ship (#120 back-half) — where the fold pays off most:**

| Current leaf(s) | Surviving leaf | Fate |
| --- | --- | --- |
| `reconcile-head` + `freshness`/`freshen` (catch-up loop) + `ci --emit-checks` + hand-back + 3 fences | `check ship-readiness` *(rb)* | **the whole green path folds → 1 leaf** (no model dispatch in it) |
| `ci --emit-checks` + `ci-decide` + `ci-record` + fence (+ `revert-draft`) | `prepare CI fix` *(rb)* | folds → **1** per CI-fix pass (before the `fix-ci` agent) |
| `fix-push` + next `ci --emit-checks` | `push CI fix + recheck` *(rb)* | folds → **1** (after the `fix-ci` agent) |

**Cross-cutting:**

| Current leaf | Surviving leaf | Fate |
| --- | --- | --- |
| `readout_post --reason` (park) | `post readout` *(be)* | **own leaf** |
| `readout_post --ctx` (hand-back) | folds → `check ship-readiness` *(be)* | folds in |
| `loop_readout --record` | folds → `post readout` | render + post in one leaf; no standalone leaf |
| `rev-parse HEAD` (`resolveHead`) | absorbed into its stretch's gather (various) | no standalone leaf |

**Net:** ~30 current leaf-kinds → about **22–24 surviving leaf-kinds** (roughly one per stretch), with the 4 test-pilot deciders deleted, the double-journal folded, and the entire green ship path folded to a single leaf. A full run fires **~35–45 leaves total** (was ~100–130) — because each stretch now fires its one gather instead of several. The exact fold boundaries are the plan's to confirm (FR-1).

## Glossary

- **Stretch (deterministic stretch):** the run of deterministic work between two genuine
  model dispatches. The unit the one-leaf bar applies to.
- **Seam:** a genuine model dispatch (worker, reviewer, synthesis judge, author, fixer) —
  a hard boundary between stretches.
- **Courier leaf:** the cheap haiku leaf that runs a command and returns its output. It
  carries no judgment.
- **Fact-gather:** one courier leaf whose job is to return the facts a stretch needs.
- **Twin (in-process judgment):** a deterministic decision made in the runtime from
  gathered facts, dispatching no courier leaf.
- **Read-back:** confirming a durable write by reading the resulting persisted state and
  checking a distinctive content value.

## Coverage

| Area | Disposition | Where / why |
| --- | --- | --- |
| Empty & first-run | N-A | No user-facing surface; the closest analogue (resume after park/crash) is UFR-3. |
| Invalid & malformed input | Specify | UFR-1 — a dropped/garbled courier result fails closed. |
| Boundaries & limits | Specify | FR-8 / UFR-1 — the retry is one-shot; the boundary is "after one retry, park." |
| Errors & failures | Specify | UFR-1 (transport failure) and UFR-2 (failed/fabricated write) — the core cases. |
| Access & permissions | N-A | Internal run engine; no actor-facing permission surface in this work. |
| Duplicates & double-actions | Specify | FR-6 (no duplicate journal) and UFR-3 (no duplicate durable action on resume); the per-write idempotency *mechanism* already **exists** (#120's `idempotent_apply`) — generalizing it to the append-shaped writes (incl. the ship `record CI round`) is defer-to-plan (Assumptions). |
| Conflicting / simultaneous use | Defer-to-plan | The fence folds into its stretch's single leaf (renew-then-mutate adjacent), at the per-task site and the four ship sites; the green ship path and each CI-fix inter-agent stretch each fold to one leaf once their writes are idempotent (the coupling in Assumptions) — plan **confirmations**, not open feasibility. If a run is superseded between a write and its read-back, the mismatch parks (UFR-2) — the park *reason* honesty (superseded vs failed write) is the plan's to phrase. |
| Misuse & abuse | N-A | No sensitive/abusable surface introduced; the safety concern is fail-open, covered by UFR-2. |
| Reach (i18n / a11y) | N-A | No human-facing UI beyond run-readout text, which is unchanged. |
