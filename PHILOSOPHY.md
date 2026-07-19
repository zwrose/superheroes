# Superheroes — product philosophy

This document answers three questions everything else hangs from: **who this is for, what
they may trust, and what bets we are making to deliver that trust.** It is deliberately
low-churn. Mechanics live in [CONVENTIONS.md](CONVENTIONS.md); the live plan lives in the
[GitHub Project](https://github.com/users/zwrose/projects/1); tactics live in issues. If
this file starts changing often, it has become a status doc and something is wrong.

## 1. Who it's for

Superheroes is built for the **moderately technical builder** — the technical product
manager, the founder, the domain expert who builds. They know their way around
software: they can describe what they want, tell whether the result works, and read
code a little. What they lack is the practiced craft of the *details* — which
third-party contract demands a round-trip test, which green suite is mocking the very
thing it claims to test. That gap is expected, and the system is built around it: **no
part of the system depends on the owner recognizing good engineering** — a guardrail
that leans on the owner to catch an engineering problem is not a guardrail, so the
judgment lives in the structure instead. They cannot audit an agent's work at that
depth, and they should not have to. So the obligation runs the other way: every
decision that routes to the owner arrives as plain consequences — what it costs, what
it risks, what accepting it means — never as a craft call they're presumed able to
judge.

This person is **the owner** — the product's word for the human with the final say.
The owner works through an agent already at their side (it is
where superheroes lives), and delegates **judgment**, not just labor: when they hand
off a build, they are trusting the session to find the gotchas they don't know exist;
when a readout says "reviewed and passing," they will ship on that sentence.

We build superheroes with superheroes. Every promise and guardrail below is one its own
developers run behind daily — the bar is that they hold even for experts, because
guardrails that only protect careful owners are not guardrails.

## 2. The promise

What the owner may trust, in order of what they'd feel most betrayed by if broken:

1. **Work is delegated; commitment is not.** The product codes, designs, and decides
   freely inside its workspace. The acts that bind the owner beyond it — merging,
   releasing, publishing — are never taken on their behalf. It parks rather than
   presume.
2. **It applies the judgment the owner isn't expected to have.** The third-party
   contract that needs a round-trip test before it's trusted, the unhappy path nobody
   specified, the race that only shows up under load, the test suite that mocks the very
   thing it claims to test — caught by default, fixed autonomously where safe, explained
   in plain language. The owner is never the backstop for a trap they couldn't have
   known about.
3. **It builds what the owner meant.** Intent is captured in plain language before work
   begins, consequential decisions come back to the owner instead of being assumed, and
   deviations from the agreed spec are surfaced, never quietly absorbed.
   Plausible-but-wrong is a failure mode, not a deliverable.
4. **It never claims more than it verified.** Every "built," "passed," "reviewed," and
   "ready" traces to a receipt — a test that ran, a gate that evaluated, a journal event
   that exists. A claim without a receipt is a defect, even when the claim is true — and
   a passing test suite is not, by itself, a receipt that the owner got what they asked
   for.
5. **When it degrades or stops, it says so — and the costly trades are the owner's.**
   Harmless workarounds (a retry, a slower path) it takes and discloses. A fallback that
   costs something promised — an independent checker, a skipped verification — follows a
   policy the owner set in advance, or it parks and asks. Nothing degrades invisibly,
   and when it can't deliver truthfully at all, it parks with the reason — it never
   pretends the work happened.
6. **It leaves a trail the owner's agent can read back to them.** Every run's
   decisions, dispatches, and gates are on disk — and the owner is never alone with
   them: their agent follows along, translates, and answers *what happened, and why?*
   in plain language. The same trail serves any expert the owner trusts, and the next
   session.

## 3. The bets

The falsifiable architecture decisions. Each carries its re-check condition — the
evidence that would change our mind. A bet whose condition never gets checked is dogma.

**B1 — Checkpoints at the right altitude, not a deterministic execution spine.**
Discovery → spec → build → review → ship, with checkpoints between the stages — each a
loop with a verifiable stop. The owner personally enters at just two: they approve the
plain-language spec before build, and they do the final review and merge at the end
(merging is always theirs). Everything in between runs autonomously — the build brief
is checked by an independent reviewer before code, and the finished work gets an
independent review before handback; these are checkpoints by construction, not owner
interruptions. The one mid-flight exception is a genuinely consequential or irreversible
decision — a migration, a new dependency, an external contract — which comes to the
owner before the builder commits to it, and even that can be pre-authorized at spec
time. We bet that for an owner who cannot supervise mid-flight, checkpoints at the right
altitude beat both raw flexibility and a deterministic execution spine between them.
*Re-check:* the checkpoints cost the after-the-fact forensic trail a staged execution
would leave; they buy bounded behavior and work the checkers can review *before* it
executes. If a fidelity, honest-failure, or auditability regression ever traces to the
absence of staged execution between the checkpoints, the spine question reopens — the
checkpoints themselves do not.

**B2 — Plain language can carry the contract.** Everything the owner touches — specs,
readouts, park reasons, verdicts — is written in their language, and the spec is the
real contract, not a summary of one. The bet: plain words, plus good elicitation, hold
enough precision to build from.
*Re-check:* builds where the spec was followed and the owner still didn't get what they
meant. If those accumulate, we add precision — acceptance criteria, worked examples,
deeper questions — and keep the words plain.

**B3 — Maker ≠ checker, structurally.** The builder is never the only judge of its own
work. The minimum: a checker with none of the maker's working context, and not outmatched
by what it judges. A different model or vendor buys more independence at more cost —
and whatever the rung, it must be *verified*: a checker that silently falls back to the
maker's model launders confidence, worse than no checker at all.
*Re-check:* the review benchmark (#131) measures what each rung actually catches; the
engine surface grows or shrinks on that evidence, not on vibes.

**B4 — Determinism where trust demands it.** Anything safety- or honesty-critical
(guardrails, gates, preflight, verdicts) is deterministic code; model judgment is reserved
for the creative middle (design, implementation, review findings). A trust property that
depends on a model's mood is not a property.
*Re-check:* when the platform ships a primitive that makes a deterministic layer
redundant, we retire ours (see B6).

**B5 — Degradation is bounded by the owner's trades, and never invisible.** Runs
survive what can be survived without forfeiting anything promised; a fallback that
costs more than that follows an owner-declared policy or doesn't happen. Every
degradation is journaled, counted, and disclosed where the owner actually reads — and
one that recurs 100% of the time isn't degradation, it's a broken subsystem whose
failure nothing is reporting.
*Re-check:* any release whose first real run surfaces a fidelity-class surprise means
this bet's enforcement has a hole; treat it as a broken guarantee, not a bug.

**B6 — Bespoke machinery only where the platform lacks the primitive.** On a platform
that ships monthly and keeps absorbing jobs like ours, every bespoke divergence we keep
is a *named decision with a re-check trigger*, recorded in a ledger — never inertia;
when the platform grows a primitive that makes one of ours redundant, ours retires.
*Re-check:* a standing orientation review — monthly-ish, deliberately independent of
the release path — walks the ledger against the platform's current primitives, retiring
what is no longer earned and citing upstream requests rather than duplicating them.

**B7 — Evidence before machinery.** No producer without a named consumer. No new gate
without an escape that penetrated every existing layer. No growth during stabilization
without the milestone that unlocks it. The anti-opportunities ledger — the list of
things we deliberately do not build — is a first-class artifact, cited instead of
re-litigated.
*Re-check:* the unlock conditions written on the ledger itself.

## 4. When values collide

Section 2 is the contract — what the product owes, each promise binding on its own (its
ordering is a reading aid, not a ranking to trade against). This section is different:
it is the decision rule for the moments a live run cannot keep every good at once —
park honestly or push to ship, spend more or stop. Not everything here is a promise:
delivery and economy are real goods that appear only in this list — and items 1–2 never
yield to either, otherwise delivery pressure quietly wins every collision. Highest
wins:

1. **Owner commitment** — not tradeable. The acts that bind the owner (merge, release,
   publish) never move, under any delivery pressure.
2. **Honesty** — a parked run that tells the truth beats a shipped run that doesn't.
   We will lose deliveries to this. That's the product working.
3. **Economy** — tokens, wall-clock, and owner attention are real budgets, not
   afterthoughts. Spend what the work earns, notice when a run is buying nothing with
   what it burns — and never spend an owner interruption a guardrail could have
   absorbed.
4. **Protection of the work** — fail closed; never clobber, corrupt, or lose the
   owner's work or state.
5. **Delivery** — subject to all the above, runs should *finish* and hand back
   something real. A product that mostly parks is honest and useless.

The order is descriptive of decisions already made (the never-merge rule, the honesty
gate family, fail-closed parks, high-ceilings-plus-monitors) — and prescriptive for the
ones ahead. When a proposal trades a higher value for a lower one, the answer is no.

## 5. How this document stays honest

A philosophy written mid-journey is a promissory note — if the product already kept
every promise above, this document wouldn't have needed writing. Promises are allowed to
precede their receipts; forgetting they're owed is the defect. So, applied to itself,
promise 4 means this file needs receipts:

- **Heroes cite it.** Discovery, the review rubric, and the session covenant reference
  the promise and bets where they enforce them; a hero behavior that can't be traced to
  a promise is a candidate for the anti-opportunities ledger.
- **Releases walk it.** Release evaluation maps each release's headline claims to
  promise 4 (claims carry receipts) — a deferral is stated in the evidence, loudly.
- **Orientation reviews re-check the bets.** On a standing monthly-ish cadence,
  independent of any release, section 3's re-check conditions get looked at against the
  field and the platform. The bets are allowed to lose; the review is how we notice.
- **Changes land by PR with owner approval**, and rarely. Wordsmithing is churn;
  a changed bet or promise is news.
