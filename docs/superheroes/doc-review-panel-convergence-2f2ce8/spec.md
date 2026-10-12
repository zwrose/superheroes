---
superheroes: doc
schemaVersion: 1
docType: spec
workItem: doc-review-panel-convergence-2f2ce8
issue: 397
size: medium
status: approved
gates: {review: passed}
producedBy: "the-architect@0.11.2"
created: "2026-07-12"
updated: "2026-07-14"
---
# Doc-review panel convergence

## Purpose

When the pipeline reviews a plan (or a tasks document), the review currently runs to a
fixed 7-round cap on findings that should never have blocked it — a live run on
2026-07-12 spent ~1,000,000 output tokens and 2h20m reviewing a plan that took 22k
tokens to write, then parked with an empty reason ([#397](https://github.com/zwrose/superheroes/issues/397)).
Three defects compose: the review applies code-review-grade severity to a design
document, every revision re-arms the loop with fresh findings, and the final park tells
the owner nothing. This work makes the document review converge — findings are judged at
the right altitude, the loop stops once the real blockers are fixed and confirmed, and
when it must stop unresolved it says exactly why.

## Who it's for

- **The owner** — runs full-route builds and pays the treadmill's token/time cost today;
  when a review parks, they are the one who must decide what to do next, so the park has
  to be readable.
- **The tasks author** (the pipeline stage that writes the task breakdown) — the named
  consumer of the finer-grained findings a plan review surfaces but should not block on.

## Functional requirements

**FR-1.** While reviewing a plan or tasks document, the review shall classify a finding
as **blocking** only if following the document as written would mislead the build or
cause it to build something unsafe or incorrect, judged against the reviewed document's
own job.
  - *Acceptance (rule):* in a plan review, a finding about task- or test-specification
    granularity (e.g. "no named unit test for this option", "this value appears as two
    separate literals", "this test doesn't specify a controlled clock") is classified
    non-blocking — specifying tasks and tests is the tasks document's job, not the
    plan's.
  - *Acceptance (rule):* in a tasks review, a finding that the tasks document
    mis-specifies a task or test the build will follow is judged directly against the
    bar — never categorically demoted as "specification granularity" — because the
    tasks document is the build's contract.
  - *Acceptance (rule):* a finding of the class that legitimately blocked the first
    review round of the 2026-07-12 incident run (an unauthenticated access path, a
    required security exemption missing, a design that would corrupt or lose data) is
    classified blocking.
  - *Acceptance (rule):* a finding the review cannot confidently place on either side
    of the bar is classified blocking — ambiguity fails closed (owner decision,
    2026-07-12): a wrongly-demoted real blocker is invisible, while a wrongly-promoted
    one costs at most a readable park the owner can rule on. Example: a finding that
    the plan's error-handling approach "may be insufficient" without naming what would
    break cannot be confidently placed, so it blocks.

**FR-2.** When a plan review classifies a finding as non-blocking, the review shall
record that finding in a durable hand-off list for the tasks phase.
  - *Acceptance (Given-When-Then):* Given a plan review that surfaced non-blocking
    findings, when the review ends (pass or park), then a durable hand-off list exists
    containing each non-blocking finding in plain language, each entry naming the part
    of the plan it concerns (so an entry the revisions have since mooted is
    recognizable as such).

**FR-3.** When the tasks phase starts for a work item whose plan review recorded a
hand-off list, the tasks author shall receive that list as a named input.
  - *Acceptance (Given-When-Then):* Given a hand-off list from FR-2, when the tasks
    phase runs, then the tasks author's instructions include the list, and the run
    journal shows it was provided.

**FR-4.** When a tasks review classifies a finding as non-blocking, the review shall
record that finding in the run journal.
  - *Acceptance (rule):* the run journal for a tasks review that surfaced non-blocking
    findings contains an event carrying each of them.

**FR-5.** If a tasks review records non-blocking findings, then the build phase's
instructions shall not include them.
  - *Acceptance (rule):* no build instruction contains findings routed from the tasks
    review — the tasks document remains the build's only contract.

**FR-6.** When a baseline review round surfaces no blocking finding, the review shall
end with a passing gate without running further rounds.
  - *Acceptance (Given-When-Then):* Given a document whose first review round surfaces
    only non-blocking findings, when the round completes, then the gate reads passed,
    the non-blocking findings are routed per FR-2/FR-4, and no second round runs.

**FR-7.** When every baseline blocking finding has been resolved and a confirmation pass
surfaces no new blocking finding, the review shall end with a passing gate.
  - *Acceptance (Given-When-Then):* Given a baseline round with blocking findings that
    were then fixed, when the confirmation pass surfaces only non-blocking findings,
    then the gate reads passed and those findings are routed per FR-2/FR-4 — they do
    not restart the loop.

**FR-8.** If a confirmation pass shows any blocking finding open — a previously
identified one not yet resolved, or a newly surfaced one — then the review shall run at
most one further confirmation pass once fixes have been applied, the second and final
one under the FR-9 cap.
  - *Acceptance (Given-When-Then):* Given a first confirmation pass that shows an open
    blocking finding (newly surfaced, or a baseline one a fix did not resolve), when
    fixes have been applied, then exactly one further confirmation pass runs — and if a
    blocking finding is still open after it, the review parks per FR-10; no fourth
    round ever runs.

**FR-9.** The review shall run at most **three completed review rounds** per document
review: one baseline round plus at most two confirmation passes.
  - *Acceptance (rule):* no document-review record shows more than three completed
    review rounds, regardless of document length or finding volume.

**FR-10.** If the round cap is reached with blocking findings still open, then the
review shall park with a plain-language decision list naming each open finding and what
accepting it would mean.
  - *Acceptance (Given-When-Then):* Given a review at its round cap with open blocking
    findings, when it parks, then the owner-facing readout presents each open finding as
    a decision they can rule on in plain language, stating what accepting it would mean.
  - *Acceptance (rule):* the park also names, per finding, the owner's available moves
    and what each leads to — direct a fix and a fresh review (the ordinary path), or
    accept the finding through the existing gate-approval step — so the owner can answer
    in one reply without reconstructing pipeline mechanics.

**FR-11.** When a document review parks, the parked event in the run journal shall carry
the park reason and the open-findings list.
  - *Acceptance (rule):* no parked event from a document review has an empty payload;
    each carries the reason and the decision list from FR-10.

**FR-12.** The review gate shall read "passed" only when the review ended with no open
blocking findings, or the owner accepted the open findings through the existing gate
approval step.
  - *Acceptance (rule):* no path sets the gate to passed while blocking findings are
    open and unaccepted — there is no automatic pass at the cap.
  - *Acceptance (rule):* a pass that followed owner acceptance is distinguishable from
    a clean pass: the run journal's park event (FR-11) names the findings that were
    accepted, and the gate record shows the acceptance came after that park — so the
    trail answers which findings the owner accepted, using the records this work
    already writes.

**FR-13.** The plan review and the tasks review shall follow the same classification,
convergence, and park behavior (FR-1, FR-6 through FR-12, FR-14, FR-15).
  - *Acceptance (rule):* both a plan review and a tasks review exhibit the round cap,
    the ratchet exit, and the readable park; they differ only in where non-blocking
    findings go (FR-2/FR-3 vs FR-4/FR-5) and in how the FR-1 bar reads against each
    document's own job.

**FR-14.** When a review of a document surfaces a finding the owner already accepted for
that document, and the content the finding concerns has not changed, the review shall
treat that finding as accepted rather than as an open blocking finding.
  - *Acceptance (Given-When-Then):* Given a park where the owner accepted one finding
    and directed fixes for the others, when the document is revised and re-reviewed,
    then the accepted finding does not re-block — the re-review can pass with it still
    accepted — and the owner is never re-asked a decision they already made.
  - *Acceptance (rule):* if the content an accepted finding concerns *has* changed, the
    finding is judged afresh under FR-1 — acceptance covers the document the owner saw,
    not whatever it later becomes.

**FR-15.** When a document review ends — pass, accepted pass, or park — the review shall
record in the run journal the rounds used, the per-round counts of blocking and
routed-forward findings, and the outcome.
  - *Acceptance (rule):* for any completed document review, the journal alone shows how
    many rounds ran, how many findings blocked vs routed forward in each, and how the
    review ended — enough to detect, across runs, a park-wall (reviews routinely parking
    at the cap) or a demotion-wall (blocking findings routinely vanishing into the
    routed stream) without reading anything else.

## When things go wrong (significant unhappy paths)

**UFR-1.** If a record this work requires cannot be written — a hand-off entry, the
tasks review's journal record of a routed finding, the journal record that the hand-off
was provided (FR-3), the record of an owner's acceptance (FR-14), or the convergence
record (FR-15) — then the phase involved shall report that failure in the run journal
and the owner-facing readout, rather than proceeding silently.
  - *Acceptance:* Given a required write that fails, when the phase ends, then the
    journal and readout name which record could not be written and what it would have
    carried (e.g. how many findings, or that the hand-off was in fact delivered).

**UFR-2.** If a review round fails to complete, then the review shall count that round
neither as a clean pass nor toward the round cap.
  - *Acceptance:* Given a round that ends without a usable review result, when the
    review continues or stops, then the gate does not read passed on the strength of
    that round, and the failed round does not consume one of the three completed rounds
    (FR-9).

**UFR-3.** If the same finding is surfaced more than once — across rounds within one
review, or across review runs — then the hand-off list shall contain one entry for it.
  - *Acceptance:* Given a finding surfaced in two rounds of one review, and a review
    re-run after a prior run already recorded hand-off findings, when the review ends,
    then each distinct finding appears once in the list the tasks author receives.

**UFR-4.** If review rounds repeatedly fail to complete, then the review shall stop and
park with the failure as the park reason, rather than retrying without bound.
  - *Acceptance:* Given rounds that keep failing, when the review stops, then the
    outcome is a park whose journal event names the failure — never a pass, and never
    unbounded retrying. How many retries are allowed before stopping is the plan's to
    set.

**UFR-5.** If the hand-off list a plan review recorded is absent or unreadable when the
tasks phase starts, then the tasks phase shall report that in the run journal and the
owner-facing readout rather than proceeding silently without it.
  - *Acceptance:* Given a work item whose plan review recorded hand-off findings, when
    the tasks phase starts and cannot read the list, then the journal and readout state
    that the hand-off could not be read — and the tasks phase never claims to have
    consumed it.

## Non-functional requirements

- **Bounded cost (economy):** a document review's total spend is bounded by the round
  cap for every input — fit criterion: on an incident-class plan (a multi-hundred-line
  plan drawing on the order of fifty distinct findings, as the 2026-07-12 run did), the
  review completes (pass or park) within three completed rounds, ending the 7-round /
  ~1,000,000-token failure class. Failed rounds cannot re-open the bound: attempts are
  limited by UFR-4's retry stop, so completed plus failed rounds stay finite for every
  input.
- **Consumable hand-off (economy):** the tasks author receives a readable list, not a
  relocated treadmill — fit criterion: the hand-off list carries each distinct finding
  once (UFR-3), in plain language, its volume bounded by what at most three completed
  rounds can surface; on an incident-class plan that is tens of entries, not hundreds.
- **Traceability (honesty):** every gate outcome — pass, or park — traces to an on-disk
  record the owner's agent can read back; fit criterion: for any completed document
  review, the run journal alone answers "why did the gate end this way?"

## Definition of done / success

A full-route run whose plan draws incident-class finding volume (a multi-hundred-line
plan drawing on the order of fifty distinct findings, as the 2026-07-12 run did) either
passes its plan review within three completed rounds or parks with a readable decision
list. The finer-grained findings that previously fueled rounds 5–7 appear in the tasks
hand-off list — and the tasks author demonstrably receives them — instead of blocking
the plan gate. If the review parks, the journal's parked event carries the reason. The
tasks review shows the same capped, converging behavior with its findings journaled and
kept out of build instructions. At no point does a review pass with open, unaccepted
blocking findings. A resume after a park never re-asks a decision the owner already made
— accepted findings stay accepted (FR-14) — and every review leaves its convergence
record in the journal (FR-15), so a park-wall or demotion-wall would show up in the
first few runs as data rather than as owner pain.

## Assumptions & dependencies

- The confirmation-pass convergence pattern is already ratified and running for code
  review (#174); this work extends the same confirmation economics (at most two
  confirmation passes, restricted re-arm, park at the cap) to document reviews — while
  being deliberately stricter on the total: the three-round cap *replaces* the old
  seven-round loop rather than sitting inside it, because a doc-panel round is a
  full-document, full-panel spend with no cheap scoped tier, so headroom there buys
  treadmill, not convergence.
- The 2026-07-12 incident's real findings — its first round's blockers and its rounds
  5–7 granularity findings — are available as a calibration corpus; the plan is expected
  to anchor the reviewers' and synthesis judge's classification examples to them.
- The existing owner gate-approval step (the manual path by which an owner accepts a
  parked review's residual findings) exists and is unchanged by this work.
- The run journal and owner-facing readout exist as the disclosure channels this work
  writes into.
- The pipeline's existing stage ordering is assumed and unchanged: the tasks phase runs
  only after the plan review's gate has passed (or its residuals were owner-accepted),
  and a plan re-review resets that gate — so re-running what follows, including the
  tasks phase's read of the hand-off list, is the pipeline's existing job, not this
  work's. Hand-off findings recorded by a re-review are delivered by that re-run, not
  retro-delivered to a tasks phase that already finished.

## Constraints

- **No new acceptance machinery.** Owner acceptance of residual findings happens through
  the existing gate-approval step only.
- **Never auto-pass.** Reaching the round cap with open blocking findings always parks;
  there is no cap-and-proceed for document reviews (no stronger reviewer exists
  downstream to catch what this gate waves through).
- **Code review untouched.** The convergence behavior of per-task code review and the
  whole-branch final review stays exactly as ratified by #174/#382.

## Out of scope

- Per-task code-review loops and the whole-branch final review (their convergence
  economics are settled by #174/#382).
- Owner notification when findings are routed forward — journaling is the requirement;
  notification is explicitly not (owner decision, 2026-07-12).
- Changes to how plans or tasks documents are authored — their content and structure
  stay as they are. (The tasks author *receiving* the hand-off list as a named input is
  FR-3 and in scope; what it writes with it is not changed by this work.)

## Open questions

None — all consequential decisions were resolved with the owner during Discovery.

## Glossary

- **Baseline round** — the first full review of a document, which sets the list of
  blocking findings the review must resolve.
- **Confirmation pass** — a follow-up review round run after fixes. Doc rounds are
  full-document, full-panel spends (this spec's Assumptions; there is no cheap scoped
  tier), so a confirmation IS a fresh full-panel round — the three-completed-rounds cap
  (FR-9) is the cost bound, not a narrower review scope. It examines at least the
  resolutions of the previously identified blocking findings and anything newly
  surfaced, each classified under the FR-1 bar; only a blocking finding re-arms the
  review (FR-8). *(Erratum 2026-07-14, owner-authorized: this entry previously said a
  confirmation "is never a fresh, full re-review", contradicting the Assumptions; the
  implementation follows the Assumptions, per review-loop.md.)*
- **Blocking finding** — a finding that meets the FR-1 bar: following the document as
  written would mislead the build or produce something unsafe or incorrect.
- **Hand-off list** — the durable, plain-language list of non-blocking findings a plan
  review passes to the tasks author.
- **Park** — the review stopping honestly with open decisions for the owner, rather
  than passing or failing on its own authority.
- **Same finding** — two findings are the same when they name the same problem with the
  same part of the document, however differently they are worded; otherwise they are
  distinct. (How sameness is detected is the plan's to choose; this is the meaning any
  detection must implement.)

## Coverage

| Area | Disposition | Where / why |
| --- | --- | --- |
| Empty & first-run | Specify | FR-6 — a clean baseline round passes immediately, no extra rounds |
| Invalid & malformed input | Defer-to-plan | a garbled or unusable review result never counts as a clean pass (UFR-2); detection mechanics are the plan's |
| Boundaries & limits | Specify | FR-9 (the round cap) and FR-10 (behavior exactly at the cap) |
| Errors & failures | Specify | UFR-1 (hand-off write failure disclosed), UFR-2 (failed round never passes or consumes the cap), UFR-4 (repeated failure parks honestly), UFR-5 (unreadable hand-off disclosed at tasks time) |
| Access & permissions | N-A | internal pipeline stage; no user-facing access surface |
| Duplicates & double-actions | Specify | UFR-3 — neither repeated rounds nor re-runs duplicate hand-off findings; FR-14 — an accepted finding never re-blocks a re-review of unchanged content |
| Conflicting / simultaneous use | N-A | one run owns a document review at a time by existing pipeline design |
| Misuse & abuse | N-A | no money, private data, or externally reachable surface involved |
| Reach (i18n / a11y) | N-A | internal run artifacts, in the product's existing single working language |
