---
superheroes: doc
schemaVersion: 1
docType: spec
workItem: front-half-sdlc-core-6181ee
issue: null
size: large
status: approved
approved: "2026-08-07"
gates: {review: passed}
producedBy: "the-architect@0.24.0"
created: "2026-08-07"
updated: "2026-08-07"
---
# Front-half SDLC core

## Purpose

In July the owner stopped writing specs, spikes became de-facto specs, and builds shipped
things the owner never decided — the "WTF handback" pattern. This spec fixes the front half
of the loop: every build becomes downstream of a decision the owner actually made, discovery
becomes the one front door for requirements, specs become the durable decision store, and a
spec's delivery is verified end-to-end before it closes. It consolidates the owner-ratified
2026-08-03 scenario-map walkthrough (all rulings closed there) plus the in-sitting rulings
of 2026-08-07 (issue contract, DoD bar, prose elicitation, epic contract).

## Who it's for

- **The owner** — a product-minded decision-maker who approves specs, rules on parked
  questions, and accepts deliveries, and who should never have to read issues, briefs, or
  review internals to stay safe.
- **The plugin's working roles** — the advisor routing and vetting, discovery eliciting,
  builders executing — who need one unambiguous contract for what each artifact owes them.

## Functional requirements

### The anchor invariant

**FR-1.** The plugin shall require every build-ready issue to cite an anchor — the
owner-approved decision it is downstream of: a spec section, a receipt (a review finding,
an incident record, a bug report, or a gate result), or a dated owner ruling.
  - *Acceptance (rule):* an issue citing none of the three anchor kinds cannot be marked
    build-ready.

**FR-2.** When the advisor marks an issue build-ready, the advisor shall record the anchor
in the issue's Anchor slot at filing time.
  - *Acceptance:* Given an issue being routed build-ready, when it is filed, then its body
    carries a filled Anchor slot naming one of the three anchor kinds.

**FR-3.** When a build picks up a routed issue, the builder shall confirm the cited anchor
resolves before spending any build effort. Each anchor kind has its own resolution test:
a spec-section anchor resolves when the spec is **owner-approved** and the cited section is
not superseded — supersession is readable from the spec's Amendments log, whose entries
name the sections they touched (FR-22); a receipt anchor resolves when the receipt link is
live; a ruling anchor resolves when the dated, owner-attributed record is reachable where
the ruling was made and no later owner decision supersedes it.
  - *Acceptance:* Given an issue whose cited spec section was since superseded, when a build
    picks it up, then the build stops and reports the stale anchor without changing any file.
  - *Acceptance:* Given an issue citing a section of a spec still in draft — never
    owner-approved — when a build picks it up, then the build stops and reports an
    unapproved anchor.

**FR-4.** When the advisor vets a PR, the vet shall check whether the diff introduces
owner-perceivable new behavior (see Glossary) that cites no approved decision — no spec
section and no dated owner ruling.
  - *Acceptance:* Given a diff introducing owner-perceivable new behavior that no cited
    approved decision covers — whether nothing is cited or the citation's scope does not
    reach the behavior — when vetted, then the vet verdict carries the flag (UFR-2 is this
    rule's failure face); this is a standing vet row and the only anchor layer that
    inspects the diff.

### Routing at intake

**FR-5.** When work arrives at intake, the advisor shall route it to exactly one of four
routes — discovery, the detective, build-ready, or micro — using the spec-trigger test:
*will this work produce sentences a vet could grade a PR against that no approved artifact
contains yet?*
  - *Acceptance:* Given incoming work carrying new product opinion or a genuine unknown,
    when routed, then it goes to discovery; given "why did Y break" work meeting the
    detective spec's fire condition (its separately-valuable test), to the detective; given
    a repair of ratified behavior with a receipt anchor — or work under a recorded ruling
    (FR-11) — to build-ready; given a tiny owner-present item, to micro.
  - *Acceptance (rule):* micro work that turns out to need probing re-routes — anything
    worth probing belongs to discovery.
  - *Acceptance (rule — overlap resolution):* the four cases are tests the advisor
    applies; where more than one matches, the route is the advisor's judgment call,
    recorded with the route and anchor at routing time (FR-6's record); "exactly one
    route" means exactly one is chosen, never that the cases partition.

**FR-6.** When the advisor routes work to `discovery`, the advisor shall not assign a
discovery size, lane, or review weight at routing — a discovery's size, eventual lane, and
review weight are unknowable at intake; `micro` is the only route knowable as small up front;
for work routed `build-ready` or `micro`, the lane and presentation calls attach at routing
per ruling P6 [cite: plugins/superheroes/skills/showrunner/SKILL.md § The call is made at routing, not at handback (ruling P6).], unchanged.
  - *Acceptance (rule):* when routed to `discovery`, routing records the route and the
    anchor, nothing more; review weight first appears on the spec draft (FR-16); for
    `build-ready` and `micro`, lane and presentation calls attach at routing per ruling P6.

### The issue contract

**FR-7.** Every routed issue shall carry a three-slot skeleton: **Anchor** (the approved
decision it is downstream of), **What** (plain-language scope and why), and **DoD** (the
gradable definition of done). Micro-route work is exempt — its safety is the owner's
presence: the owner types the fix or dictates the ruling (FR-5).
  - *Acceptance (rule):* the smallest conforming issue is three filled lines — the skeleton
    adds no further required ceremony; a routed issue missing a skeleton slot is a vet
    finding.

**FR-8.** If an issue's Anchor slot is empty, then the plugin shall block that issue from
being marked build-ready.
  - *Acceptance:* Given a routed issue with an empty Anchor slot, when build-ready marking is
    attempted, then the marking is refused; the What and DoD slots are graded at vet, not
    blocked at filing.

**FR-9.** Every DoD bullet shall name an observable outcome that a vet can grade pass/fail
from the handback's artifacts alone; a bullet describing an activity rather than an outcome
does not qualify.
  - *Acceptance (rule):* a DoD bullet whose grading would require asking a person or
    re-running the build fails the bar and is a vet finding against the issue.

**FR-10.** The plugin shall keep every issue body current such that a reader reaches a
build-ready issue's owner-approved anchor in one hop.
  - *Acceptance:* Given any routed issue, when spot-checked, then its body matches the
    work's current state — and, once the issue is marked build-ready, its Anchor slot's
    link resolves to the approved decision.

### Discovery

**FR-11.** When requirements must be elicited or investigated — the owner's decision does
not yet exist — the work shall enter through discovery; the plugin shall offer no separate
spike or investigation surface. An owner decision already made and recorded as a dated
ruling — a micro dictation, a mid-build ruling (FR-20/FR-22), or a ruling in the advisor's
channel such as a PR follow-up — needs no discovery: the advisor records it where made and
may file build-ready issues anchored to it (FR-1), quoting the dated ruling in the issue's
Anchor slot so FR-3's resolution test has a durable record to read.
  - *Acceptance (rule):* "spike" survives only as the informal name of discovery's
    investigation phase; when an investigation ends, discovery's exit gate is still ahead.
  - *Acceptance:* Given a PR follow-up the owner ruled on in the advisor's channel, when
    the advisor files it, then it routes build-ready anchored to the dated ruling with no
    discovery step; given a follow-up raising a product question no approved artifact
    answers, when routed, then it goes to discovery (FR-5's test decides).

**FR-12.** When a genuine unknown blocks requirements, discovery shall ask the owner's
consent — naming the cost in time and usage, in plain language — before spending on
investigation. Consent names the spend it covers; reaching that bound stops the
investigation, which reports and asks again before any further spend.
  - *Acceptance:* Given an investigation-worthy unknown, when discovery reaches it, then
    investigation spend begins only after the owner grants consent; while the owner is
    unavailable, the item waits or parks (FR-13) — spend never starts on silence. This is
    the only mid-flight consent point.
  - *Acceptance:* Given a consented investigation at its named bound, when the bound is
    reached, then spend stops and the owner is re-asked — or the item parks.

**FR-13.** Discovery shall end in exactly one of three exits, each with a durable artifact
and each reported to the advisor: an owner-approved spec; an owner-ratified findings record
in the work-item folder; or an owner-visible park note.
  - *Acceptance:* Given an investigation that finds no new product surface, when discovery
    exits, then a findings record exists, the owner ratifies the decision, and the advisor
    receives the exit report — no spec is fabricated.
  - *Acceptance (rule):* a park note lands on the owner's reading surface (see
    Non-functional: owner reading load) — a park invisible to the owner is not an exit.

**FR-14.** Discovery shall elicit adaptively — probing each opinion-bearing dimension and
asking whether the owner cares — with no up-front ceremony choice.
  - *Acceptance (rule):* a small surface's discovery closes having asked only the questions
    its Dispositions table needed — no ceremony beyond them, and no lighter process
    selected in advance.

**FR-15.** When discovery puts a consequential choice to the owner, it shall present the
options as prose in the conversation — the decision's stakes, a pro and con per option, and
a recommendation — and shall accept free-form answers; it shall not force the choice through
a pick-one widget.
  - *Acceptance:* Given a consequential choice, when presented, then the owner can respond
    with a clarifying question or a mix of options and the dialogue proceeds without
    re-forcing a single selection.

**FR-16.** When a spec draft is complete, the advisor shall call the review weight on the
draft: at or under 10 gradable requirement lines with no interlocking sections (sections
that cite or constrain one another) calls light weight — one independent review seat, a
light vet, in-channel owner approval; above calls full weight — review panel, full
spec-vet, scheduled owner review. The advisor may override in either direction: an
override is valid only when stated, and one stated sentence is enough.
  - *Acceptance:* Given a completed draft, when the weight is called, then the call names
    the gradable-line count and the resulting weight — and, when overriding, the one
    stated sentence.
  - *Acceptance (rule):* the 10-line bar is a guideline, never a gate — no charter or gate
    turns it into a hard block.

**FR-17.** A light-weight spec shall be the same artifact class as a full one — same
template, same home, same anchor power, same owner approval authority — with empty sections
omitted rather than filled.
  - *Acceptance (rule):* weight changes the process around the artifact, never the artifact
    class.

### Spec content

**FR-18.** Every spec shall carry one merged Dispositions table recording, per probed
dimension: the decision axis (Specify / Defer-to-build / N-A), the presentation axis
(Show-it?), and a where/why pointer.
  - *Acceptance (rule):* the table covers the unhappy-path coverage areas plus the
    happy-path seed dimensions — initially six: wording & tone, workflow shape, placement
    & prominence, limits & defaults, tier & access boundaries, visibility & disclosure —
    as grown by FR-21's learning loop.

**FR-19.** A spec line shall earn its place by the elicitation test — the owner was asked
and cared — never by an author-side filter.
  - *Acceptance (rule):* mechanisms, limits the owner would not enforce, vacuous quality
    lines, design-handoff transcription, test obligations, and non-load-bearing
    mirror-facts do not land in specs.

**FR-20.** Failure semantics shall ride the decision axis: a violated Specify row is a
builder defect; a missing Show-it presentation is a handback omission; an owner's negative
reaction to a shown Defer-to-build choice creates a new ruling, never a defect.
  - *Acceptance:* Given a shown Defer-to-build choice the owner dislikes, when the reaction
    lands, then the outcome is a recorded ruling amending the spec — no defect is charged.

**FR-21.** When a handback review finds an elicitation gap — a dimension the owner was
never asked about — the plugin shall add that dimension to the seed list so later
discoveries probe it.
  - *Acceptance (rule):* "asked and deferred" is a cheap amendment; "never asked" is a
    finding against discovery and grows the checklist.

**FR-22.** When a spec changes after approval, the body shall be edited in place and the
change shall add a one-line dated, owner-stamped entry — naming the sections it touched —
to the spec's Amendments log. The entry also classifies the amendment: **wording** (changes
phrasing; decides nothing a builder could build differently against) or **substantive**
(anything else — the default when ambiguous, failing closed).
  - *Acceptance:* Given an approved spec and a mid-build ruling, when the ruling lands, then
    the body reads correct top-to-bottom and the log carries the dated entry; propagation
    to in-flight children is UFR-4's duty.
  - *Acceptance:* Given an amendment classified wording, when it lands, then the total
    ceremony is the body edit, the dated log entry, and mechanical propagation (UFR-4) —
    no review round runs; a process that demands more for a wording amendment is
    nonconforming.

**FR-23.** When a spec reaches five amendments since its last full approval, the next touch
shall trigger a consolidation re-read and owner re-stamp; the number is a guideline, never
a trip-line.
  - *Acceptance (rule):* nothing blocks at five; the next touch carries the re-read.

**FR-24.** An annex shall elaborate decisions its core already makes and shall never
introduce a new opinion; post-approval opinion amends the core.
  - *Acceptance (rule):* an annex introducing a new opinion is a named review-spec finding
    class.

**FR-25.** Rulings shall live where they were made; specs are the decision store; the
plugin shall maintain no separate rulings ledger, and a surface that accumulates rulings is
absorbed into a spec by advisor judgment, not a mechanical trigger.
  - *Acceptance (rule):* no ledger artifact exists; absorption is a judgment call recorded
    when made; a cited ruling resolves at its original home — FR-3's test reads it there.

### Spec handoff, decomposition, and the epic contract

**FR-26.** When a spec is authored, the advisor shall vet it from its artifacts — review
ran and findings dispositioned, grounding verified, decomposable, no conflict with ratified
surfaces, consequences stated in owner terms — and shall deliver the verdict "ready for
your approval," never approval itself.
  - *Acceptance (rule):* only the owner approves a spec; the vet verdict is advisory by
    construction.
  - *Acceptance (rule):* the sequence is fixed — automated review, then advisor vet, then
    owner review, then owner approval; the owner reads a vetted spec and approves last,
    and nothing re-reviews an approved spec except the downstream nets (FR-4, FR-32's
    spec lens, FR-37), the amendment path (FR-22), and the FR-23 consolidation re-read.
  - *Acceptance (rule):* the approval is recorded with its date; FR-33's
    before/after-approval test reads it.

**FR-27.** When the advisor decomposes a spec into children — only after approval, never
before (FR-33) — it shall produce a coverage map allocating the
spec at acceptance level: every acceptance criterion owned by exactly one named child
issue. The map lives in the work-item's folder beside the spec and the register — one
canonical file home, no size ceiling, no edit races — and the epic body links to it.
(Acceptance-level allocation refines the ratified FR/UFR reverse index — the map from
each requirement to its owning child — per the 2026-08-07 sitting, from the epic-contract
prototype evidence.)
  - *Acceptance:* Given a decomposition, when the coverage map is read against the spec,
    then no acceptance criterion is unowned and none is owned twice, and the epic body
    links to the map's home. Each FR/UFR group marked as faces of one behavior allocates
    as one.

**FR-28.** When a decomposition yields two or more children, the advisor shall record every
cross-child technical decision in a contract register stored beside the spec in the
work-item's folder — numbered entries, each a plain binding sentence with its consuming
children named, owner rulings embedded, amendments dated. An embedded ruling is a dated
copy pointing to where the ruling was made — the register quotes rulings, it does not
become their ledger (FR-25 is unchanged). The advisor owns register edits; a builder never
amends the register it is graded against.
  - *Acceptance (rule):* the register is builder- and advisor-facing; an entry with no
    named consumer, and an entry introducing new product opinion (the spec's job), are
    blocking package-read findings.

**FR-29.** Each register entry shall be either decided at decomposition or explicitly
marked "decide-by" naming the child that owns the decision.
  - *Acceptance (rule):* an epic-scoped decision that is neither decided nor owned is a
    routing defect (UFR-3).

**FR-30.** Where one child creates a seam other children build on, the advisor shall
sequence that child first, so the register's contracts get their real review as working
code rather than as a document.
  - *Acceptance:* Given an epic with a contract-bearing seam, when children are sequenced,
    then the seam child precedes its consumers.

**FR-31.** Child issues shall quote the register text they consume verbatim, injected
mechanically from the register; a paraphrased restatement is a defect.
  - *Acceptance (rule):* register-to-child text agreement is checkable by exact-text
    comparison, and that check is machine work, not model judgment; it runs at filing, at
    each child's build intake, and at the package read's verification pass (FR-32).

**FR-32.** Before an epic's children file, the package — register, slice boundaries, child
bodies — shall pass an adversarial read, performed by seats independent of the package's
author, across five lenses: contradiction with the spec; register-to-child drift;
exactly-once acceptance coverage; child-against-child and cross-epic collisions; DoD
adequacy. The advisor shall call the read's weight — light or full, FR-16's vocabulary —
from the epic's measurables (the number of children and of register entries), naming a
round ceiling with the call; the advisor may override in either direction with one stated
sentence. The read follows the spine of the plugin's shared review-loop contract — a
script-owned round schedule and a durable convergence record
[cite: plugins/superheroes/reference/review-loop.md § Convergent Shared Review Loop] —
and departs from it in named, disclosed ways, each justified: rounds are scoped to
unreviewed text rather than to review dimensions (the package's verbatim units make exact
scoping possible); new findings take the code leg's lenient re-arm posture rather than the
document leg's strict one (the package has downstream nets the document leg lacks — FR-35's
vet row, FR-31's intake check, FR-37's closure recheck); ceilings and seat counts are
named per invocation by the weight call, with UFR-7's park, in place of the contract's
fixed round and confirmation caps and its always-full first panel; and a verification pass
stands in for the full fresh confirmation round (the mechanical sync battery covers what a
fresh panel would re-derive).
  - *Acceptance (rule — scoped rounds):* a round reads the currently-unreviewed parts,
    plus — for the relational lenses (spec contradiction, collisions, coverage) — each
    reviewed part those unreviewed parts directly touch; never a fresh pass over the whole
    package.
  - *Acceptance (rule — convergence):* the read repeats until a round returns only
    mechanical items (fixes that change wording or synchronization and decide nothing).
    Authorship extends the loop; re-flagging does not: a fix that adds a contract or
    redraws a slice boundary makes those parts unreviewed and they are re-read before
    filing, while a blocking finding raised against text unchanged since its last review
    is logged and fixed without further extension unless its fix creates such new
    authorship.
  - *Acceptance (rule — verification pass):* the read ends with a recorded verification
    pass — each fix checked against its finding, plus the mechanical sync check (FR-31) —
    with no new hunting; a fix that fails verification returns its parts to unreviewed,
    and they are re-read before filing; the ceiling is the backstop, not the exit
    mechanism, and exhausting it parks (UFR-7).
  - *Acceptance (rule — seat composition):* the read's seats follow the same independence
    rules as the plugin's code review
    [cite: plugins/superheroes/rubric/review-discipline.md § What never changes in any lane]:
    the package's author is the maker — including the advisor when the advisor authored the
    package — the author's model family is excluded from every seat, and reviewer
    unavailability or mid-run loss follows that rubric's rules; this spec adds no separate
    seat doctrine.
  - *Acceptance (rule — audit):* the round-by-round audit trail is preserved with the
    epic and records: the weight call (its measurables and ceiling), each re-read
    invocation's cause and ceiling, any override sentence, the seats, the lenses run per
    round, the parts each round read with their unreviewed-at-entry status, the findings
    declined further extension under the unchanged-text rule, and each fix's verification
    outcome. A trail missing any of these is nonconforming.

**FR-33.** Decomposition shall begin only after the spec is owner-approved: no coverage
map, register, or child body is drafted against an unapproved spec. When a substantive
amendment (FR-22's classification; a wording amendment takes only the cheap path) lands
while a spec's decomposition or children are in flight, the touched parts of the package
re-enter the read loop (UFR-4's duty), each re-read drawing a fresh ceiling named at its
invocation and requiring a new cause — an owner decision or a recorded amendment, and
since amendments are owner-stamped, every cause passes through the owner: the loop cannot
cycle without an owner decision. Re-read invocations never self-trigger (a failed
verification re-reads within its own invocation's ceiling — FR-32), and one that exhausts
its ceiling parks per UFR-7.
The coverage map is re-checked before affected children file. This re-entry rule and the
review layer's planned owner-delta rounds (zwrose/superheroes#519 — owner edits re-enter
the loop scoped, never silently) are one rule on two surfaces; the review layer's half is
graded under that issue's own work, not by this spec, and the build may implement both on
shared machinery.
  - *Acceptance (rule):* a decomposition artifact dated before its spec's approval is a
    routing defect (owner-ruled 2026-08-07: decomposition never precedes approval).
  - *Acceptance (rule):* a spec-contradiction finding from the package read resolves as a
    package fix, a spec amendment (FR-22, owner-stamped), or a recorded refutation in the
    audit trail — never a silent spec edit.

**FR-34.** Where an epic shares a seam with another epic, the seam shall be recorded
reciprocally: in both registers and in both affected child bodies.
  - *Acceptance (rule):* a seam recorded on one side only is a package-read blocking finding
    (the collisions lens).

**FR-35.** When a child PR is vetted, the vet shall grade one added row: the change
conforms to the epic's register, or the drift is disclosed.
  - *Acceptance:* Given a child PR violating a register entry without disclosure, when
    vetted, then the vet flags it as a blocker (UFR-6 is this rule's failure face).

**FR-36.** A single-issue spec shall skip epic machinery: no register, the in-channel fast
continuation applies — the advisor proposes the single child issue in the same
conversation and the owner approves it there, no separate decomposition sitting — and
closure folds into that PR's vet: the applicable closure elements (FR-37) are graded
there, and the owner's merge decision doubles as delivery acceptance only when the
handback names it as such in so many words — an explicit line, never an inference.
  - *Acceptance (rule):* epic machinery activates at two or more children, never below; a
    single-issue spec still ends with an explicit owner delivery decision.
  - *Acceptance (rule — shared seams):* where a single-issue spec shares a seam with an
    epic, the seam is recorded in the epic's register and quoted verbatim in the single
    child's issue body — the issue body stands in for the missing register on the
    single-issue side; FR-34's reciprocity and UFR-4's amendment propagation read that
    issue body as the single-issue side's register home.

### Spec closure

**FR-37.** When the advisor vets the child PR whose merge will close a spec's last open
child, that same vet shall assemble and carry the closure receipt — closure is never a
separate process or trigger. The vet knows it is final by the present-tense test (every
other child already merged or closed); the advisor sequences candidate closure moments —
concurrent final vets, or a vet racing a sibling's no-PR close — so exactly one carries
the receipt. Where the last open child closes without a PR (declined scope), the closure
receipt is presented to the owner with that close — the same sitting, still no separate
trigger. The receipt carries: coverage map complete; all other children merged with green
vets; amendments reconciled; one end-to-end validation run against the current spec body **and
its result** (for app surfaces, an executed test-pilot run derived from the spec's DoD and
acceptance criteria; for plugin or doctrine surfaces, the plugin's automated conformance
checks exercising the shipped behavior, supplemented by one recorded rehearsal where an
element needs a live run); aggregated Show-it items; delivered versus deferred/declined
named.
  - *Acceptance:* Given the final child PR's vet, when the closure receipt is assembled
    with it, then every listed element is present — or its absence is named with why —
    and the receipt states the validation run's result. A receipt whose validation run is
    absent can close only by the owner's explicit acceptance with the absence disclosed
    (FR-38) — never as an ordinary full delivery.

**FR-38.** The owner shall accept delivery on the closure receipt, presented with the
final child PR's handback — or with the no-PR close where FR-37's edge applies — one
sitting, never a separate process; no spec closes without
either full delivery accepted or an explicit owner acceptance of partial delivery. (A
single-issue spec, per FR-36, is the one-child case of the same rule.)
  - *Acceptance (rule):* nothing closes silently incomplete (UFR-5 is this rule's failure
    face; a failing validation run routes through UFR-8).

### The builder's side of the line

**FR-39.** Builds shall start only from routed issues carrying resolving anchors; the
workhorse shall no longer run discovery inline in a build session — work routed `discovery`
is routed back rather than elicited in-session
[cite: plugins/superheroes/skills/workhorse/SKILL.md § You do not elicit requirements in a build session].
  - *Acceptance:* Given work needing discovery, when it reaches a build entry point, then it
    is routed back to discovery rather than elicited in-session; the build entry point takes
    only routed, anchored issues.

### Adoption

**FR-40.** When a project first adopts this doctrine, the advisor shall surface the
project's open pre-doctrine issues to the owner, and each shall be decided case by case —
re-anchored, re-routed, or closed — with each decision recorded on the issue as a dated
ruling (FR-3's resolution test reads it there).
  - *Acceptance:* Given adoption, when the pass completes, then every open pre-doctrine
    issue carries a resolving anchor, a new route, or a close — none is silently left
    ungated — and the pass's completion is recorded with the project's calibration.
  - *Acceptance (rule):* a project carrying an adoption arrangement the owner ratified
    before this doctrine — a closed list, recorded with that project's advisor seat per
    FR-25's rulings-live-where-made rule — keeps it; the case-by-case pass governs
    everything else.

## When things go wrong (significant unhappy paths)

Each UFR here is the failure face of the FR or FRs it names; the decomposition coverage
map allocates each FR together with its failure faces as one behavior.

**UFR-1.** *(failure face of FR-3)* If a cited anchor fails to resolve at build intake —
the cited spec is unapproved, or its section gone or superseded; the receipt link is dead;
or the ruling's dated, owner-attributed record cannot be found or a later owner decision
superseded it — then the build shall stop and report to the advisor before any spend; the
advisor repairs the route — re-anchor, re-route, or park to the owner.
  - *Acceptance:* Given a stale or unapproved anchor, when intake checks it, then no file
    changes, the report names what failed to resolve, and it reaches the advisor.

**UFR-2.** *(failure face of FR-4)* If a vetted diff introduces owner-perceivable new
behavior citing no approved decision — no spec section and no dated owner ruling — then
the vet shall flag it and the flag shall reach the owner in the vet verdict.
  - *Acceptance:* Given such a diff, when vetted, then the verdict carries the flag in plain
    language — what new behavior, and that no approved decision covers it.

**UFR-3.** *(failure face of FR-27/FR-29)* If a decomposition leaves an acceptance
criterion unallocated or an epic-scoped decision unowned, then the advisor shall treat it
as a routing defect and repair it before any child build starts.
  - *Acceptance:* Given an incomplete coverage map or an unowned decide-by, when the package
    read runs, then filing is held until the defect is repaired.

**UFR-4.** *(failure face of FR-22/FR-28)* If the spec body or the epic's register is
amended while children are in flight, then the amendment shall reach every affected child:
the amended artifact and its dated log first; unstarted children mechanically re-injected
(register text) or re-checked against the coverage map (spec text); children already
building explicitly notified. An amendment that adds or changes a contract — rather than
wording — that is, one classified substantive (FR-22) — passes a touched-parts re-read
using FR-32's lenses and convergence rule before it is injected, with a fresh ceiling
named at invocation (its cause is the amendment itself; UFR-7's park applies). A reciprocal cross-epic seam entry
(FR-34) is one contract in two homes: amending it in either register amends both, and both
epics' affected children are treated as affected. A child that never received an amendment
is a process defect, not a builder defect.
  - *Acceptance:* Given a mid-build amendment, when it lands, then each affected child
    either carries the new text or holds an explicit notice of it, and the coverage map
    still allocates every acceptance criterion.

**UFR-5.** *(failure face of FR-38)* If a spec's children deliver only part of the spec,
then the spec shall stay open unless the owner explicitly accepts the partial delivery on
the closure receipt.
  - *Acceptance:* Given undelivered requirements at the final child's vet, when the
    closure receipt is presented, then delivered and deferred/declined are named and the
    owner's explicit choice decides open-vs-accepted.

**UFR-6.** *(failure face of FR-35)* If a child PR drifts from the register without
disclosure, then the vet shall flag it as a blocker before handback.
  - *Acceptance:* Given undisclosed drift, when the vet's register row is graded, then the
    handback is held until the drift is disclosed or repaired.

**UFR-7.** *(failure face of FR-32)* If a package read invocation fails to converge within
the round ceiling named at its invocation — the initial read's ceiling arrives with the
weight call; a re-read's with its cause (FR-33, UFR-4) — then the package shall park to
the owner — children unfiled — with the open findings named.
  - *Acceptance:* Given a read at its ceiling with non-mechanical findings still open, when
    the ceiling round ends, then the park reaches the owner's reading surface and no child
    files until the owner rules.

**UFR-8.** *(failure face of FR-37)* If the closure receipt's end-to-end validation run
fails, then the spec shall stay open and each failure shall produce a repair issue whose
receipt anchor is the failing run's record, naming the unmet acceptance criterion; the
owner may instead explicitly accept delivery with the failing run disclosed (FR-38). The
repair issues become children, and closure re-rides the vet of whichever PR closes the
new last open child (FR-37) — so each repair cycle ends at FR-38's owner decision, and
the loop cannot cycle without the owner.
  - *Acceptance:* Given a red validation run at closure, when the receipt is presented, then
    the spec is not closed by default and the repair issues carry receipt anchors.

**UFR-9.** *(failure face of FR-3 — a ruling anchor superseded after intake)* If a
recorded owner decision supersedes a ruling that anchors in-flight work, then the advisor
shall notify that build when recording the new decision. Affected work is locatable by its
Anchor slot (FR-7) — the anchor citation is the reverse index, so no rulings ledger is
needed (FR-25 unchanged). Register-embedded copies count as citations too: when recording
a superseding ruling, the advisor also checks open epics' registers (FR-28's copies carry
pointers to the ruling's home), and an affected register is amended under UFR-4.
  - *Acceptance:* Given a superseding ruling, when it is recorded, then any in-flight build
    whose Anchor slot cites the superseded ruling holds an explicit notice; a build that
    merges downstream of a reversed ruling without the notice is a process defect.

**UFR-10.** *(failure face of FR-13 and FR-37)* If a discovery stops without reaching an
exit — the session ends, the owner goes quiet after consenting to spend, or the work is
displaced — then the advisor shall park it: a park note carrying what was elicited so far,
explicitly marked unapproved, so the item stays visible and the owner's answers survive.
Delivery gets the same protection: a spec whose child is abandoned — closed unmerged,
orphaned, or displaced — is re-planned or parked by the advisor rather than left waiting
for a closure moment that cannot come.
  - *Acceptance:* Given an abandoned discovery, when the advisor next reviews open work,
    then the item holds a park note (not silence), and nothing elicited is lost or mistaken
    for approved content.
  - *Acceptance:* Given a spec with an abandoned child, when the advisor next reviews open
    work, then the spec holds a re-plan or a park — not silence.

## Non-functional requirements

- **Owner reading load:** the owner's routine reading surface stays bounded to kickoffs,
  investigation consents, weight calls, spec-vet receipts, specs and amendments, findings
  records, park notes, handback receipts, closure receipts, and merge/delivery decisions —
  roughly 2–5 specs plus a handful of rulings and findings a month. *Fit criterion:* every
  owner gate defined in this spec consumes only artifacts from that list; no gate requires
  reading an issue, brief, work order, or review internals.
- **Plain language:** every owner-facing artifact defined here reads in plain language,
  with ratified vocabulary glossed at first use. *Fit criterion:* an owner-facing artifact
  that requires plugin-internal vocabulary to parse is a review finding.
- **Guidelines over trip-lines:** the two numbers (10 gradable lines; 5 amendments) are
  positioned everywhere as guidelines with disclosed overrides. *Fit criterion:* no charter
  or gate turns either number into a hard block.

## Definition of done / success

Each bullet grades either by reading the shipped plugin surfaces (charters, templates,
gates) or by one recorded run or rehearsal named in the closure receipt — never by
trusting a claim.

- A build-ready issue without a resolving anchor cannot pass filing or build intake, and an
  escape is flagged at vet — demonstrated by exercising each layer once: a filing refusal
  (FR-8), an intake stop-and-report (UFR-1), and a vet flag (UFR-2).
- A spec authored under this doctrine carries the merged Dispositions table and the
  Amendments log, and a light spec is the same artifact class as a full one.
- An epic decomposition produces an acceptance-level coverage map and a contract register
  beside the spec; its children carry verbatim register text; its package read's audit
  trail exists; each child PR vet grades the register row.
- The final child PR's vet carries the closure receipt (validation result stated), and the
  owner's delivery decision rides that handback; a partial delivery is explicitly accepted
  or the spec stays open.
- Discovery presents consequential choices as prose options and never through a pick-one
  widget.

## Assumptions & dependencies

- The owner-ratified scenario map (2026-08-03 walkthrough, §11 ledger) is the decision
  source for this spec; its rulings are owner decisions of record, consolidated here rather
  than re-litigated. In-sitting rulings of 2026-08-07 (issue skeleton anchor-enforced;
  artifact-gradable DoD bar; prose elicitation; the epic-contract pattern and the
  register's home beside the spec) are likewise of record.
- The charter-delta builds implementing this spec sequence after the 0.25 release cut, as
  the opening act of the 0.26 train, and ship coherently across the affected charter
  surfaces.
- The detective ships under its own spec (work-item `the-detective-16c561`); that spec owns
  the detective's fire condition, which this spec's routing route (FR-5) applies.
- Issue zwrose/superheroes#693 is governed by this spec — its open question ("what an issue
  owes its three readers") is resolved here, and it proceeds under the approved spec with
  no independent discovery.
- Per-project adoption arrangements the owner ratified before this doctrine — each a
  closed list carried as a standing note to that project's advisor seat, not plugin
  machinery (owner rulings 2026-08-03/04, recorded in zwrose/superheroes#873) — stay where
  they were made. This spec defines no general legacy exemption and no automatic
  conversion: adoption runs FR-40's case-by-case owner-advisor pass (owner-ruled
  2026-08-07, recorded in zwrose/superheroes#873).
- The epic-contract pattern is informed by two field prototypes in a calibrated downstream
  project and the three-specimen back-test of 2026-08-07; their receipts are recorded with
  the discovery issue zwrose/superheroes#873.

## Constraints

- No new hero and no new artifact class beyond the work-item decomposition documents (the
  contract register and the coverage map); every duty lands on an existing surface
  (advisor, discovery, builder intake, vet, templates).
- Doctrine ships in plugin surfaces — charters, templates, rubric — never only in session
  memory.
- Both calibration storage modes (in-repo and out-of-repo) honor every behavior here.
- Owner-rejected shapes stay rejected: hard size caps, owner-facing summaries at the
  approval gate, a rulings ledger, umbrella program machinery.

## Open questions

None — the adoption boundary was ruled 2026-08-07: no automatic conversion; FR-40's
case-by-case owner-advisor pass over open pre-doctrine issues.

## Glossary

- **Anchor** — the owner-approved decision an issue is downstream of: a spec section, a
  receipt, or a dated owner ruling.
- **Receipt** — durable evidence something happened: a review finding, an incident record,
  a bug report, a gate result.
- **Owner-perceivable behavior** — a change a user of the product could notice in what it
  shows, says, allows, limits, or costs.
- **Vet** — the advisor's from-artifacts check of a PR, spec, diagnosis, or closure; it
  advises, the owner decides.
- **Dispositions table** — the spec's per-dimension record of Specify / Defer-to-build /
  N-A plus Show-it?, with where/why.
- **Show-it** — a flag that the handback must present a dimension (screenshot, walkthrough,
  pilot capture); aggregates into the DoD.
- **Contract register** — the epic's numbered list of cross-child technical decisions,
  stored beside the spec, quoted verbatim by children.
- **Decide-by** — a register entry deferring a decision to a named owning child.
- **Closure receipt** — the artifact, carried by the final child PR's vet, on which the
  owner accepts a spec's delivery end-to-end.
- **Micro** — the tiny owner-present route: the owner types the fix or dictates a ruling;
  no spec, no ceremony.
- **Builder (the workhorse)** — the role that executes a build from a routed issue.
- **Handback** — the moment a ready PR returns to the owner with its receipts.
- **Owner-stamped** — the log entry names the owner decision behind the change (who ruled
  and when), distinguishing owner rulings from editorial edits.
- **EARS** — the constrained requirement grammar used here (When/While/Where/If…then
  sentences, one behavior each).

## Amendments

- **2026-08-08 (owner-stamped, substantive):** FR-5 overlap resolution — the route cases
  are tests, overlaps resolve by recorded advisor judgment, and "exactly one route" means
  one is chosen, not that the cases partition. Cause: the package read (rounds 1–2) showed
  a register-authored precedence was product opinion; the owner walked the overlap cases
  and stamped the judgment rule in-channel. The detective pre-ship transition needs no new
  text — it lives in the detective spec's Assumptions (rulings live where made, FR-25).
  Sections touched: Routing at intake (FR-5), Amendments.
- **2026-08-08 (owner-stamped, substantive):** FR-36 shared seams — a single-issue spec
  sharing a seam with an epic records the seam in the epic's register, quoted verbatim in
  the single child's issue body, which stands in for the missing register on that side.
  Cause: the package read's collisions seat found FR-34 (both registers) unsatisfiable
  against FR-36 (no register) for the detective seam; owner ruled option (a) in-channel.
  Sections touched: FR-36, Amendments.
- **2026-08-08 (owner-stamped, substantive):** FR-32 seat composition — the package read's
  seats follow the same independence rules as code review (maker-family exclusion; the
  advisor-as-author counts as the maker), by citation to review-discipline rather than a
  restated rule. Cause: the first live package read was mis-dispatched to seats sharing the
  author's family and the owner corrected it in-channel; ruled "generally follow the same
  rules as review-code." Sections touched: FR-32, Amendments. Substantive — a builder
  implementing the read protocol builds seat composition differently against it.
- **2026-08-08 (owner-stamped, wording):** recorded the approval date — the owner confirmed in the advisor channel that approval was given 2026-08-07 in the discovery sitting; added the `approved:` frontmatter field. Sections touched: frontmatter, Amendments. Decides nothing a builder could build differently against.
- **2026-08-17 (owner-stamped, wording):** FR-6 scoped to the `discovery` route — for
  `discovery`, the advisor assigns no size, lane, or review weight at routing; for
  `build-ready` and `micro`, lane and presentation calls attach at routing per ruling P6,
  unchanged. Cause: owner ruling in discuss-open-decisions walk 2026-08-17 (#695,
  collector item 29-a). Sections touched: FR-6, Amendments. Classification rationale
  (owner-confirmed 2026-08-18, recorded so R4's reader-facing test is answerable by
  citation): the amendment records FR-6's original intent per ruling 29-a, and no consumer
  built against the prior unscoped reading — ruling P6's lane-at-routing behavior was
  shipped charter text throughout, and the intake machinery (#1068) implements the amended
  reading; four review seats independently flagged `substantive` under R4's text-alone
  test, which this rationale answers rather than disputes. The safety condition this
  precedent carries: an intent-clarifying amendment classifies `wording` only with a
  verified no-consumer-built-on-the-prior-reading receipt like this one.
- **2026-08-17 (owner-stamped, wording):** FR-39 citation repointed — the `needs-discovery`
  anchor removed by #1068 now cites the workhorse charter's discovery intake rule. Cause:
  advisor package-hygiene note on vet 136 / PR #1068 follow-up 5. This touch carried the
  FR-23 consolidation re-read; owner re-stamp of the consolidated body is outstanding.
  Sections touched: FR-39, Amendments.

## Coverage

| Area | Disposition | Show-it? | Where / why |
| --- | --- | --- | --- |
| Empty & first-run | Specify | No | The routes work from zero (FR-5, FR-11) — a project's first spec needs nothing special. Pre-doctrine issues get FR-40's case-by-case adoption pass (owner ruling 2026-08-07). |
| Invalid & malformed input | Specify | No | UFR-1 (unresolvable or unapproved anchor), UFR-6 (undisclosed register drift), FR-9 (ungradable DoD bullet). |
| Boundaries & limits | Specify | No | FR-16 and FR-23 — the two numbers, positioned as guidelines with disclosed overrides; FR-32's round ceiling with UFR-7's park. |
| Errors & failures | Specify | No | UFR-3 (routing defects), UFR-4 (mid-build amendment propagation), UFR-8 (failing closure run), UFR-9 (superseded ruling anchor), UFR-10 (abandoned discovery). |
| Access & permissions | Specify | No | FR-26 and FR-38 — approval and delivery acceptance are owner-only; vets advise by construction; FR-32's read seats are independent of the package author. |
| Duplicates & double-actions | N-A | — | Work-item slugs are minted once and frozen; duplicate filings are ordinary advisor judgment, no doctrine needed. |
| Conflicting / simultaneous use | Specify | No | FR-34 (reciprocal cross-epic seams); register edit races avoided by its single file home (FR-28). |
| Misuse & abuse | Specify | No | FR-24 (annex smuggling), FR-28 acceptance (product opinion in the register), FR-26 (no self-approval), FR-32 (no self-read of one's own package). |
| Reach (i18n / a11y) | N-A | — | Internal doctrine; no end-user language or accessibility surface. |
| Wording & tone | Specify | No | Plain-language NFR; FR-20's failure semantics name what a violated wording row means. |
| Workflow shape | Specify | No | The FR groups define each workflow end-to-end (routing → discovery → spec → decomposition → closure). |
| Placement & prominence | Specify | No | Artifact homes are named: register and coverage map beside the spec (FR-27, FR-28), rulings where made (FR-25), receipts on issues, park notes on the owner surface (FR-13). |
| Limits & defaults | Specify | No | The two guideline numbers (FR-16, FR-23); epic machinery threshold at two children (FR-36). |
| Tier & access boundaries | Specify | No | Authority boundaries: owner-only approval and acceptance (FR-26, FR-38); advisor-only weight calls (FR-16, FR-32). |
| Visibility & disclosure | Specify | No | The owner reading surface (NFR) bounds what the owner sees; every override and drift is disclosed to a named surface (FR-16, FR-32, FR-35, UFR-2). |
