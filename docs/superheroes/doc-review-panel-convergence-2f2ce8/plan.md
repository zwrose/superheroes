---
superheroes: doc
schemaVersion: 1
docType: plan
workItem: doc-review-panel-convergence-2f2ce8
issue: 397
size: medium
status: approved
gates: {review: passed}
producedBy: "the-architect@0.12.0"
created: "2026-07-12"
updated: "2026-07-12"
---
# Doc-review panel convergence — Plan

## Overview

The document-review loop already has most of the machinery this spec needs — it is
mis-parameterized and blind, not missing. The showrunner drives plan/tasks review through the
same native panel shell code review uses (`lib/review_panel_shell.js` → the `review_loop_plan.py`
deciders), and that path already implements the #174 confirmation-bar economics (a baseline
panel, then at most two confirmation passes) in `lib/review_round_policy.py` and
`lib/panel_tally.py`. The 2026-07-12 incident happened because (1) the doc panel is wired with
`maxRounds: 7`, so the breaker lets rounds run past where the confirmation economics would have
stopped; (2) the reviewers apply code-review severity to a design document, so plan-level
task/test-granularity findings read as blocking Importants that re-arm the loop; and (3) the
park and the run journal record almost nothing, so a stop is unreadable and no cross-run signal
exists.

The plan therefore does three things, in ascending order of new code: **re-parameterize** the
doc panel to a three-round cap that lines up with the confirmation economics already present;
**re-frame classification** so a finding blocks only when following the document would mislead
the build (FR-1), routing the rest to a durable hand-off (plan→tasks) or the journal (tasks);
and **make the boundaries legible** — a decision-list park (FR-10/11), a convergence record
(FR-15), and acceptance that survives a re-review (FR-14). The single-source-of-truth policy
libs (`review_round_policy.py`, `panel_tally.py`, `circuit_breaker.py`) are shared by the native
showrunner path and the interactive `review-plan`/`review-tasks` skills, so changing them once
gives FR-13 (plan and tasks review behave identically) for free. Boring by default: we tune and
instrument the existing loop rather than build a second one.

## Goals & non-goals

**Goals** (from the spec):
- Classify doc-review findings at document altitude, blocking only what would mislead the build,
  with ambiguity failing closed to blocking (FR-1).
- Cap a document review at three completed rounds — a baseline plus at most two confirmation
  passes — with a ratchet exit that stops once the real blockers are fixed and confirmed
  (FR-6/7/8/9).
- Route non-blocking findings: a plan review's to a durable hand-off list the tasks author
  receives (FR-2/3); a tasks review's to the run journal, never into build instructions
  (FR-4/5).
- Make every stop legible: a decision-list park (FR-10/11), an honest gate (FR-12), acceptance
  that does not re-block unchanged content (FR-14), and a per-review convergence record (FR-15).
- Disclose every failed required write and unreadable hand-off instead of proceeding silently
  (UFR-1/5), and never let a failed round pass or consume the cap (UFR-2/4).

**Non-goals** (things that could be goals but are deliberately excluded):
- Changing code-review convergence. The per-task and whole-branch code reviews keep their
  #174/#382 economics untouched (spec constraint); this work touches the doc leg only.
- Owner notification when findings route forward. Journaling is the requirement; a push/notify is
  explicitly out of scope (spec, owner decision).
- New acceptance UI or a new approval verb. Acceptance rides the existing owner gate-approval
  path (spec constraint).
- Changing how plans/tasks docs are authored. The tasks author *receiving* the hand-off is in
  scope; what it writes with it is not.
- A cap-and-proceed for documents. There is no stronger downstream reviewer, so the cap always
  parks, never auto-passes (spec constraint).

## Architecture

Three seams, all inside the existing doc-review path. Nothing new sits in the request path of a
code review.

1. **Classification seam (FR-1).** The blocking bar for a document is a judgment the panel
   already makes; it is currently made with the wrong rubric. We add a **doc-severity addendum**
   to `rubric/review-base.md` (a new "Document-review severity" section, gated to
   `docType: plan|tasks`) and thread it into the doc reviewer/synthesis framing in
   `showrunner.js` (`docReviewerAgent`, `docSynthesisLeaf`) and the interactive
   `review-plan`/`review-tasks` skills. The bar is anchored with few-shot examples drawn from the
   2026-07-12 incident corpus (its round-1 blockers vs its rounds 5–7 granularity findings). The
   synthesis judge (`loop_synthesis`) remains the second, keep-on-uncertain gate — which
   implements FR-1's "ambiguity fails closed" for us.

2. **Round-economics seam (FR-6/7/8/9).** The confirmation-bar policy in
   `review_round_policy.py` already caps at `MAX_CONFIRMATIONS = 2` (baseline + 2 = 3 rounds).
   We (a) pass `maxRounds: 3` to the doc panel in `runReviewDocPanel` so the breaker and the
   confirmation cap agree, and (b) add a `docMode` re-arm rule so **any** open blocker (Critical
   or Important), not only a Critical or cross-cutting rework, re-arms the one further
   confirmation FR-8 requires. Code review keeps its existing rule; the divergence is a single
   parameter on `confirmation_followup`.

3. **Legibility seam (FR-2/3/4/5/10/11/12/14/15).** A small set of **routing + record**
   components hang off the doc phase (`reviewDocPhase` in `showrunner.js`): a hand-off writer
   (plan) and a journal router (tasks) for non-blocking findings; a park composer that turns the
   terminal round's open blockers into a decision list; a convergence recorder; and an
   acceptance ledger the re-review consults. These read the run's on-disk `round-records.json`
   and write through the existing durable channels (`journal.py`, the work-item docs dir, the
   gate writer). They are pure add-ons: a failure in any of them discloses (UFR-1) rather than
   corrupting the review.

The interactive skills share seams 1 and 2 through the policy libs and the rubric — plus one
prose seam the libs cannot carry: their shared loop contract, `reference/review-loop.md`,
hard-codes the code-review re-arm rule verbatim (only a Critical or cross-cutting rework
re-arms; new Importants resolve by a scoped round; scoped verify at the cap), so it gains a
doc-mode carve-out stating the doc legs' rule (see Components & interfaces). They get
their own thin adapters for seam 3 (the skills already print findings in chat — they gain the
hand-off write, the park/convergence journal writes, and the acceptance read).

## Components & interfaces

- **`rubric/review-base.md` — "Document-review severity" addendum.** New section, keyed to
  `docType`. Defines *blocking* for a document as "following the document as written would
  mislead the build or cause it to build something unsafe/incorrect, judged against the
  document's own job," lists the plan-vs-tasks asymmetry (task/test granularity is non-blocking
  in a plan, blocking in a tasks doc), and states the fail-closed rule. Consumed by every doc
  reviewer and the synthesis judge. `rubric-version` bumps (staleness signal).

- **`lib/review_round_policy.py::confirmation_followup(..., doc_mode=False)`.** New keyword
  parameter. When `doc_mode` is true, the re-arm trigger becomes "any open blocking finding"
  (Critical **or** Important) rather than "Critical or cross-cutting." The cap
  (`MAX_CONFIRMATIONS`) and the park-at-cap semantics are unchanged. Interface stays
  deterministic — `{rearm, park, atCap, reason}`. This decider has a hand-maintained **JS twin**
  — `lib/review_round_policy.js::confirmationFollowup`, bundled into `showrunner.bundle.js` —
  kept in sync by the fixture-driven parity suite (`lib/tests/test_parity.py` registers the pair
  in `PARITY_TWINS` and runs both implementations against the shared fixtures under
  `lib/tests/parity/review_round_policy/confirmationFollowup/`). The `doc_mode` change is
  therefore a **three-part edit, per CONVENTIONS §11**: the Python decider, the JS twin (plus a
  bundle regeneration), and new `doc_mode` parity fixtures pinning the re-arm-on-any-open-blocker
  rule in both implementations — never the Python side alone.

- **`lib/review_loop_plan.py` (`tally_round_decider`) + `lib/review_panel_shell.js`.** Thread
  `doc_mode` from the doc leg down to `confirmation_followup` (via `_further_confirmation_owed`).
  `maxRounds` becomes 3 for the doc panel; `panel_tally.decide_terminal`/`circuit_breaker`
  consume it unchanged.

- **`lib/showrunner.js::runReviewDocPanel`.** Change `maxRounds: 7` → `3`; pass a `docMode`
  flag into the panel `legKind` so the tally decider selects the doc re-arm rule.

- **`reference/review-loop.md` — doc-mode carve-out.** The shared loop contract the interactive
  skills defer to (`review-plan`/`review-tasks` SKILL.md both cite it as the loop's authority)
  hard-codes the code-review confirmation-bar prose: Critical/cross-cutting re-arm only, scoped
  rounds for new Importants, scoped verify at the cap. A new, explicitly doc-gated paragraph
  states the doc-review rule — any open blocker (Critical **or** Important) re-arms the one
  further confirmation, there is no cheap scoped tier (doc rounds are full-panel), and at the cap
  the review parks, never scoped-verify-passes — keeping both rules side by side in the one
  shared home (CONVENTIONS §11) rather than forking the file per leg. Without this, the skills'
  prose contradicts the `doc_mode` decider they call.

- **Finding identity — one definition, two uses.** "Finding identity" is the UFR-3 dedupe key
  and the recorded trace half of the FR-14 acceptance key; the spec delegates its mechanism to
  this plan, so it is pinned here. The **deterministic key** is the existing normalization in
  `lib/circuit_breaker.py::finding_identity` (file/doc anchor + clamped, normalized title),
  which moves to a shared single home — a small `lib/finding_identity.py`, imported by the
  breaker, the hand-off writer, and the acceptance ledger (one normalization, CONVENTIONS §11). That key is reword-sensitive by
  construction, so each consumer gets the failure direction that is safe for it:
  - **UFR-3 dedupe (hand-off list)** uses the deterministic key alone. A reworded duplicate can
    appear twice in the advisory hand-off list — a harmless redundant entry, visible in the
    hand-off `counts`, never a dropped finding.
  - **FR-14 acceptance match** must survive rewording (spec), so the deterministic key is
    recorded for traceability but is **not** what suppresses a blocker: candidates are selected
    by concerned `docSection` whose content hash still matches (or, for `docSection: null`
    records, by the whole-doc hash — the acceptance ledger's spanning rule), and sameness is
    confirmed by the
    synthesis judge ("is this re-raised finding the same concern the owner accepted?") with
    keep-on-uncertain failing closed to *not the same* — the finding is judged afresh. The
    failure direction is a possible re-ask, the same safe direction the ledger already accepts
    for boundary failures, never a silently-stale accept.

- **Hand-off writer — `lib/review_handoff.py` (new, small).** `write --work-item <slug> --doc
  plan --findings <path>`: reads the plan review's non-blocking findings for the run, dedupes by
  the deterministic identity key (UFR-3; see "Finding identity" above), and writes
  `plan-handoff.json` into the **work-item docs dir**
  (resolved storage-mode-aware, the same resolution `reviewDocPhase` already uses via
  `docDirFor`/`definition_doc`). Schema: `{schemaVersion, workItem, findings: [{identity,
  planSection, text}], counts}`. `read --work-item <slug>`: returns the list or a structured
  `{ok:false, reason}` when absent/unreadable (UFR-5). Idempotent overwrite (a re-review
  replaces the prior run's list, FR-2's "the revisions have since mooted it" recognizability
  coming from the `planSection` field).

- **Tasks produce leaf (`eval/produce-leaf.md`) + tasks phase.** The tasks author receives the
  hand-off as a **named input** (FR-3): the produce leaf's prompt gains a "Hand-off from the
  plan review" section populated from `review_handoff.py read`; the phase journals that it was
  provided (or, per UFR-5, that it could not be read).

- **Non-blocking router (both doc legs).** On **both** doc legs, non-blocking findings are
  **excluded** from the fixer worklist composition (`compose_fix_context` in
  `review_loop_plan.py`, which today folds all severities) — they route forward instead of
  driving doc revisions, per FR-6/FR-7 (routed findings never run or restart a round). The two
  legs differ only in routing target (FR-13): the plan leg's go to the hand-off writer above
  (FR-2); the tasks leg's are written to the run journal (FR-4) via a `routed_forward` journal
  event and — by construction — never reach the workhorse build, whose contract is the tasks doc
  alone (FR-5). A drift test asserts a tasks-review routed finding appears in no build
  instruction.

- **Park composer — `lib/review_park.py` (new, small).** On a doc-review halt, reads the
  terminal round's open blocking findings from `round-records.json` and composes the FR-10
  decision list: per finding, its plain-language statement, the doc section it concerns, what
  accepting it would mean, and the two owner moves (direct a fix + fresh review, or accept
  through the gate-approval step). Output is the structured `payload` of the `parked` journal
  event (FR-11) and the readout block. Fail-soft: an unreadable record still parks, with the
  reason and a note that the finding list could not be composed (UFR-1).

- **Convergence recorder.** At every doc-review terminal (pass, accepted pass, park), a
  `review_convergence` journal event carries `{doc, roundsUsed, perRound: [{round, blocking,
  routedForward}], outcome}` (FR-15). Written through `journal.append`; a write failure is itself
  disclosed (UFR-1).

- **Acceptance ledger — `lib/review_acceptance.py` (new, small).** On the existing owner
  gate-approval of a parked doc review, records `{identity, docSection, contentHash}` per
  accepted finding into `plan-accept.json`/`tasks-accept.json` in the work-item docs dir. The
  re-review reads it and, in the synthesis/tally step, treats a finding as *accepted*, not
  blocking, when its concerned-section content hash still matches **and** the synthesis judge
  confirms it is the same accepted concern (judged sameness, fail-closed — see "Finding
  identity" above; the recorded `identity` is the deterministic trace key) (FR-14). A changed
  section fails the hash match → the finding is judged afresh (FR-14 second acceptance rule).
  The "concerned section" boundary is drawn **generously, not narrowly**: it is the finding's
  matched heading through the next heading of the same or shallower level — the whole
  subsection, not just the line(s) the finding cited — so an edit anywhere a reader would
  reasonably consider part of the finding's topic still falls inside the hashed span and
  invalidates acceptance. Two isolation failure modes both fail closed to re-judging, never to a
  silently-stale accept: the heading can't be resolved at all (whole-doc hash, existing rule),
  and — the narrower case this ledger must also guard — the heading resolves but the finding's
  substance is known to span more than one subsection (e.g. a cross-cutting or structural
  finding); such a finding is recorded with `docSection: null` and keyed to the whole-doc hash
  from the start, never to a single subsection that could miss a relevant edit made outside it.

- **Journal vocabulary — `lib/journal.py`.** Add `routed_forward`, `review_convergence`, and
  `handoff_provided` to `EVENT_TYPES` (the append writer fail-closes on unknown types, so the
  set is the single source; a drift test asserts the readout/run-watch renderers know the same
  names — CONVENTIONS §11).

## Data flow & data model

New or changed data, all small JSON, all in the work-item docs dir or the run journal:

- **`plan-handoff.json`** (work-item docs dir; forward-carried across phases). Produced by the
  plan review, consumed by the tasks author. One entry per distinct non-blocking finding
  (UFR-3 dedupe by identity). It is *forward* data: a plan re-review overwrites it, and the
  pipeline's existing rule — the tasks phase re-runs after a plan re-review — delivers the fresh
  list (spec Assumptions); no retro-delivery.

- **`plan-accept.json` / `tasks-accept.json`** (work-item docs dir; durable across re-reviews).
  Accepted-finding records carrying `{identity, docSection, contentHash}`, where `identity` is
  the deterministic trace key and the *match* that suppresses a re-raised blocker is
  section-hash + judged sameness (see "Finding identity"). The content hash + sameness rule is
  the one-way-door-ish part (see Key decisions): it decides whether acceptance survives a
  revision.

- **Journal events** (`events.jsonl`, append-only, existing durable channel): `routed_forward`
  (tasks non-blocking), `handoff_provided` (FR-3 receipt), `review_convergence` (FR-15), and the
  enriched `parked` payload (FR-11). Payloads are non-secret structured JSON, written as-is per
  `journal.append`'s contract.

Backward/forward compatibility: `round-records.json` and the deferred-set are read unchanged; no
existing schema field changes type. The new artifacts are additive — an older run with no
hand-off file reads as "absent" (UFR-5 disclosure), never as an error. `journal.py`'s
`schemaVersion` does not bump (additive event types, matching the existing precedent noted in its
`EVENT_TYPES` comments).

## How the requirements are met

- **FR-1 (blocking bar).** Doc-severity addendum + reviewer/synthesis framing + incident-corpus
  anchors. The plan-vs-tasks asymmetry and the "block a class that legitimately blocked round 1"
  and "ambiguity fails closed" rules are stated in the addendum and enforced by the
  keep-on-uncertain synthesis judge.
- **FR-2 (plan hand-off).** `review_handoff.py write` emits `plan-handoff.json` at plan-review
  end (pass or park), each entry naming its `planSection`.
- **FR-3 (tasks author receives it).** The produce leaf reads it as a named input; the phase
  journals `handoff_provided`.
- **FR-4 (tasks non-blocking → journal).** `routed_forward` events carry each.
- **FR-5 (not in build).** Non-blocking tasks findings excluded from `compose_fix_context`; the
  build contract stays the tasks doc; drift test guards it.
- **FR-6 (clean baseline passes immediately).** Already the confirmation economics' behavior; the
  3-round cap does not change a zero-blocker baseline's clean exit.
- **FR-7 (ratchet exit after confirmation).** The #174 confirmation model: fixed blockers +
  a clean confirmation pass → pass; newly-surfaced non-blockers route, they do not restart.
- **FR-8 (one further pass, then park).** `confirmation_followup(doc_mode=True)`: any open
  blocker re-arms exactly one more confirmation, capped by `MAX_CONFIRMATIONS`.
- **FR-9 (three-round cap).** `maxRounds: 3` on the doc panel; breaker + confirmation cap agree.
- **FR-10/11 (readable park + journal payload).** `review_park.py` composes the decision list
  into the `parked` event payload and the readout.
- **FR-12 (honest gate).** `gateForTerminal` never maps a capped/halted terminal to `passed`;
  the only path to `passed` with open blockers is the owner's gate-approval, recorded after the
  park event (the ledger + the park event together make an accepted pass distinguishable from a
  clean one).
- **FR-13 (plan ≡ tasks behavior).** Both legs run the same shared policy libs and rubric
  addendum; they differ only in routing target and the FR-1 asymmetry.
- **FR-14 (accepted findings don't re-block).** `review_acceptance.py` ledger, matched on
  concerned-section content hash + judged sameness (the deterministic identity key is the
  recorded trace; rewording survives via the judge, per the spec), where the concerned section
  is the whole matched subsection (heading-to-next-heading), not the finding's narrower cited
  line(s) — so a relevant edit anywhere in that subsection invalidates acceptance instead of
  silently surviving it.
- **FR-15 (convergence record).** `review_convergence` event at every terminal.
- **UFR-1 (disclose failed required writes).** Every new writer returns a structured result; the
  phase surfaces a write failure to the journal and readout, never proceeds silently.
- **UFR-2 (failed round neither passes nor counts).** The tally already fails closed to `review`
  on unreadable round artifacts and never certifies on a missing/low-confidence result; a failed
  round does not persist a completed round-record, so it does not consume one of the three.
- **UFR-3 (dedupe).** Hand-off writer dedupes by the deterministic identity key across rounds
  and across re-runs (the file is overwritten with the full deduped set); a reword-dup's failure
  direction is a redundant advisory entry, never a dropped finding.
- **UFR-4 (repeated failure parks).** The existing breaker's non-max-iterations halts park; the
  retry bound for repeatedly-failing rounds is set here (see Key decisions) and its exhaustion
  parks with the failure as the reason.
- **UFR-5 (unreadable hand-off disclosed at tasks time).** `review_handoff.py read` returns
  `{ok:false, reason}`; the tasks phase journals and reports it and never claims consumption.
- **NFR bounded cost / consumable hand-off / traceability.** Met by FR-9's cap (bounded rounds),
  UFR-3's dedupe (bounded, once-each hand-off), and FR-11/15's records (every gate outcome
  traces to an on-disk record).

## Key decisions & alternatives

- **Decision:** Where the FR-1 blocking bar lives. · **Options weighed:** (a) a rubric addendum +
  reviewer/synthesis framing anchored to the incident corpus (model judgment, second-gated by
  synthesis); (b) a deterministic post-classifier that reclassifies findings by keyword/topic
  after the panel runs. · **Choice + why:** (a). "Would following this document mislead the
  build" is a semantic judgment a keyword rule cannot make without both false-demoting real
  blockers and false-promoting granularity nits; the panel + keep-on-uncertain synthesis judge
  already exists to make exactly this call, and FR-1's fail-closed rule maps directly onto the
  synthesis judge's keep-on-uncertain default. · **Accepted downside:** classification quality
  depends on model judgment and prompt/corpus quality, so a mis-calibrated run can still
  over-block — mitigated by fail-closed-to-blocking (a readable park, not an invisible miss), the
  incident corpus as anchors, and the FR-15 record making a demotion-wall visible in the first
  runs. · **Reversible?** two-way (rubric/prompt text). · **Mode:** PROCEED. · **Reverse path:**
  revert the addendum + framing. · **Expiry:** n/a. · **Escalated?** no.

- **Decision:** Reuse the #174 confirmation-bar machinery for the doc cap vs build a doc-specific
  loop. · **Options weighed:** (a) reuse `review_round_policy`/`panel_tally`/`circuit_breaker`
  with `maxRounds: 3` and a `doc_mode` re-arm parameter; (b) a separate doc-review loop
  controller. · **Choice + why:** (a). The spec's "baseline + at most two confirmation passes"
  *is* the confirmation-bar shape already implemented; baseline + `MAX_CONFIRMATIONS=2` = 3. A
  second controller would duplicate the breaker, the tally, and every fail-closed path — the
  #211 refactor deliberately made these the single decision path. · **Accepted downside:** the
  doc leg now carries one behavioral divergence (the `doc_mode` re-arm on any open blocker, not
  only Critical/cross-cutting) that must be kept distinct from code review's rule — mitigated by
  making it a single named parameter with its own unit tests, `doc_mode` parity fixtures that pin
  the Python decider and its bundled JS twin to the same rule, and a drift test that pins each
  leg's rule. · **Reversible?** two-way (a parameter). · **Mode:** PROCEED. · **Reverse path:**
  drop the parameter. · **Expiry:** n/a. · **Escalated?** no.

- **Decision:** Hand-off storage location + lifetime. · **Options weighed:** (a) a durable
  `plan-handoff.json` in the work-item docs dir (survives across phases, storage-mode-aware);
  (b) carry the hand-off only in the run journal and reconstruct it at tasks time. · **Choice +
  why:** (a). The tasks author is a *different phase* (often a different process/worktree); a
  first-class artifact in the docs dir is the natural named input, resolved by the same
  `docDirFor`/`definition_doc` path resolution the phase already uses, and it is trivially
  overwritten by a re-review. Reconstructing from journal events couples the tasks author to the
  journal's internal shape. · **Accepted downside:** one more on-disk artifact + schema to
  maintain and clean up — mitigated by reusing the docs-dir resolution and a tiny fixed schema. ·
  **Reversible?** two-way (a file, not a contract others build against yet). · **Mode:** PROCEED.
  · **Reverse path:** delete the writer/reader + the file. · **Expiry:** n/a. · **Escalated?**
  no.

- **Decision:** Acceptance persistence granularity (FR-14). · **Options weighed:** (a) key
  acceptance to `identity + contentHash(the cited section)`, falling back to the whole-doc hash
  when the section cannot be isolated; (b) key acceptance to the whole-doc content hash only. ·
  **Choice + why:** (a). FR-14 says an accepted finding must not re-block *unchanged* content but
  must be re-judged when *the content it concerns* changes; a whole-doc hash would re-open every
  accepted finding on any edit anywhere (defeating "never re-ask a decision they already made"),
  and a section hash tracks the finding's actual subject. The whole-doc fallback fails closed
  (re-judge) when the section is ambiguous. · **Accepted downside:** section isolation is
  heuristic (a doc section boundary), so a finding whose section can't be pinned degrades to
  whole-doc granularity and may be re-asked once — acceptable because the failure direction is
  re-asking (safe), not silently keeping a stale acceptance. That safe-failure-direction claim
  only holds if a *successful* isolation can't itself be too narrow — a section hash scoped to
  just the finding's cited line(s) could miss a relevant edit made elsewhere in the same
  subsection and silently keep a stale accept, which is the unsafe direction. The boundary is
  therefore defined generously (the whole matched subsection, heading-to-next-heading — see
  "Acceptance ledger" above), and a finding whose substance spans more than one subsection is
  keyed to the whole-doc hash outright rather than to any single narrow span. · **Reversible?**
  the *ledger file*
  is two-way; the *acceptance semantics* touch the gate-honesty contract (FR-12), so treat the
  key definition as the one-way-door-ish decision to get right now. · **Mode:** PROCEED (it rides
  the existing gate-approval; no new owner-facing surface). · **Reverse path:** widen/narrow the
  hash key; ledger is regenerable. · **Expiry:** n/a. · **Escalated?** no — it adds no acceptance
  machinery beyond a record of what the existing step accepted (spec constraint honored).

- **Decision:** Finding-identity mechanism (the UFR-3 dedupe key and the FR-14 sameness match;
  the spec delegates the mechanism to this plan). · **Options weighed:** (a) one deterministic
  normalized-string key (the existing `circuit_breaker.finding_identity` shape) for both uses;
  (b) the deterministic key for the dedupe + judged sameness (synthesis judge, keep-on-uncertain
  fail-closed) for the acceptance match; (c) model-minted stable keys (`classKey`) carried
  across rounds as the identity. · **Choice + why:** (b). A normalized string cannot survive
  rewording — the spec's stated requirement for acceptance sameness — and (c)'s model-minted
  keys are not stable across independent re-reviews, so neither lone mechanism serves both
  uses; splitting them assigns each consumer the failure direction that is safe for it (a
  reword-dup in the advisory hand-off list is a harmless extra entry; acceptance sameness gets
  the same judge the panel already trusts for keep-on-uncertain calls). The deterministic
  normalization gets one shared home imported by all consumers (CONVENTIONS §11). · **Accepted
  downside:** the acceptance match adds one bounded judge call per re-review that has candidates,
  and judged sameness is model judgment — mitigated by the deterministic docSection+hash
  prefilter (few, section-scoped candidates) and by fail-closed-to-judged-afresh (a wrong call
  re-asks; it never silently keeps a stale accept). · **Reversible?** two-way (a matching rule;
  the ledger records the deterministic key either way). · **Mode:** PROCEED. · **Reverse path:**
  tighten the match to the deterministic key only. · **Expiry:** n/a. · **Escalated?** no.

- **Decision:** Retry bound before a repeatedly-failing round parks (UFR-4; the spec leaves the
  number to the plan). · **Options weighed:** (a) 2 failed attempts per round before parking; (b)
  no explicit bound, rely on the round cap. · **Choice + why:** (a). A failed round must not
  consume a completed round (UFR-2), so without an attempt bound a flapping reviewer could retry
  unboundedly under the 3-round cap; 2 attempts matches the owner convention of budgeting ≥2× the
  worst observed transient, and when both attempts fail the round parks honestly. · **Accepted downside:** a
  genuinely transient double-failure parks a review that a third try might have completed —
  acceptable because the park is readable and re-launchable, and unbounded retry is the failure
  the spec names. · **Reversible?** two-way (a constant). · **Mode:** NOTIFY — a defaulted
  threshold the owner might want tuned. · **Reverse path:** change the constant before build.
  · **Expiry:** until the build lands. · **Escalated?** no (NOTIFY, recorded here).

## Cross-cutting concerns

- **Security & privacy:** N/A — because this is an internal pipeline stage with no user-facing
  access surface, no new PII, and no new trust boundary (spec Coverage: Access/Misuse are N-A).
  The new artifacts hold review findings (already produced today) and route through the existing
  `journal.append` scrub-fail-closed path for any free-text field.
- **Observability:** the whole point of the legibility seam. On-call at 2am reads: the enriched
  `parked` event (why it stopped + the decision list), the `review_convergence` event (rounds
  used, per-round blocking vs routed counts, outcome), and the `handoff_provided`/`routed_forward`
  events — all in `events.jsonl`, rendered by the readout/run-watch. A park-wall (reviews
  routinely parking at the cap) or demotion-wall (blockers vanishing into the routed stream)
  shows up as data across the first few runs (NFR traceability, FR-15).
- **Reliability & failure modes:** every new writer is non-critical to the *review's correctness*
  and fails closed to disclosure (UFR-1): a hand-off/convergence/park write failure surfaces in
  the journal + readout and does not fabricate a pass. The one place a failure must not relax the
  gate is the tally — it already fails closed toward `review`/`halted` (UFR-2), and the new
  `doc_mode` parameter and `maxRounds: 3` change *when it stops*, never *whether an unresolved
  blocker can pass*.

## Rollout & migration

N/A for data migration — because no existing on-disk schema changes; the new artifacts are
additive and absent-reads are handled (UFR-5). Rollout is a plugin version bump behaving
identically for existing in-flight runs (an older run with no hand-off file simply discloses
"absent"). Kill-switch / rollback: the behavior is gated on the doc leg only; reverting the
`maxRounds` value and the rubric addendum restores the prior behavior, and the new artifacts are
inert if their writers are removed. Because there is no stronger downstream gate, the risky
direction is *under*-reviewing — validated first by the sequencing below (the classification and
cap land with tests against the incident corpus before the legibility add-ons).

## Risks & mitigations

- **Over-demotion hides a real blocker (the spec's demotion-wall).** Six months out, a
  mis-framed reviewer routinely demotes real design blockers into the hand-off and plans ship
  broken. · *Mitigation:* FR-1 fails closed to blocking on ambiguity; the synthesis judge is
  keep-on-uncertain; the incident corpus anchors the bar; FR-15's per-round routed-vs-blocking
  counts make a demotion-wall visible in the first runs as data.
- **The three-round cap parks too eagerly (park-wall).** A legitimately complex plan that needed
  four honest rounds now parks. · *Mitigation:* the spec ratified the strict cap deliberately (a
  doc round is a full-panel spend with no cheap tier); the park is readable and one owner reply
  re-launches; FR-15 surfaces a park-wall early so the cap can be revisited with data, not pain.
- **Hand-off/acceptance artifacts drift from the phase that reads them.** A schema or
  path-resolution mismatch between writer and reader silently drops the hand-off or the
  acceptance record. · *Mitigation:* reuse the single docs-dir resolution both sides already use.
  The two artifacts disclose a missed read differently, and the risk is only closed if both do: a
  missed **hand-off** read is loud under UFR-5, which is scoped precisely to `review_handoff.py
  read` at tasks time; a missed **acceptance-ledger** read has no dedicated UFR but is loud under
  the general seam-3 add-on rule ("a failure in any of them discloses" — UFR-1), since
  `review_acceptance.py` is one of the pure add-ons that rule covers. Neither path silently drops
  the artifact. A smoke test writes then reads across the phase boundary for both artifacts.
- **New journal event types unknown to a renderer.** A `routed_forward`/`review_convergence`
  event that the readout can't render. · *Mitigation:* CONVENTIONS §11 single-source — the
  `EVENT_TYPES` set is the home and a drift test asserts the renderers know the same names.
- **Build risk: the two review surfaces diverge.** The native path and the interactive skills
  drift on classification or the cap. · *Mitigation:* both consume the shared policy libs and the
  one rubric addendum; the skills' `loop_state.py --max-rounds` for the doc legs moves 7→3 and
  `reference/review-loop.md` gains its doc-mode carve-out in the same change; a test pins both
  legs to the same cap, and the `confirmationFollowup` parity fixtures pin the Python decider and
  its bundled JS twin to the same re-arm rule.

## Dependencies & assumptions

**Dependencies:** none external. The work builds entirely on shipped code — the #174
confirmation economics (`review_round_policy.py`), the #211 decider path (`review_loop_plan.py`,
`review_panel_shell.js`), the journal (`journal.py`), and the doc phase (`showrunner.js`). The
incident corpus (2026-07-12 run's real findings) must be available to anchor the FR-1 examples;
the spec states it is (Assumptions).

**Assumptions** (the build/review can check each):
- The existing owner gate-approval step (owner records `gates.review: passed` on a parked doc
  after review) is the acceptance trigger and is unchanged (spec Assumptions/Constraints).
- The pipeline re-runs the tasks phase after a plan re-review, so a fresh hand-off is delivered
  by that re-run — this work does not retro-deliver (spec Assumptions).
- The confirmation-bar cap (`MAX_CONFIRMATIONS = 2`) plus a baseline equals exactly the spec's
  three completed rounds; if a future change to that constant broke the equality, the FR-9 cap
  test would fail loudly (a shaky assumption made into a guarded one).
- Non-blocking tasks-review findings do not already reach the workhorse build (the build's
  contract is the tasks doc); FR-5 is enforced by excluding them from `compose_fix_context` and
  asserted by a drift test rather than assumed.
