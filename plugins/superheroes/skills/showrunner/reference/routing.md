# Contents

- [Routing — the lane call and routing detail](#routing--the-lane-call-and-routing-detail)
- [The lane call — the question that governs](#the-lane-call--the-question-that-governs)
- [Parallel lanes that extend a shared set](#parallel-lanes-that-extend-a-shared-set)
- [Two outcomes that look like discovery](#two-outcomes-that-look-like-discovery)
- [Native dependency edges](#native-dependency-edges)
- [Scope exclusions and parity surfaces](#scope-exclusions-and-parity-surfaces)
- [The premises of an order bind you](#the-premises-of-an-order-bind-you)

# Routing — the lane call and routing detail

This page is reference for the advisor at routing time. It holds the guidance behind the lane call
and the routing detail that fires only on some routes. The rules it serves live in duty 3 of the
Showrunner charter; the lane table and the cross-lane invariants live in
`rubric/review-discipline.md`.

## The lane call — the question that governs

**The lane floor comes first, and it is mechanical.** This page's judgment only ever raises a lane
above it (`rubric/review-discipline.md` § The lane floor).

**Ask it concretely:** *if this were wrong, what would break, who would notice, and how soon?*

- **Loud:** a test that fails when this behaviour breaks; a request that errors in front of
  someone; a page that visibly misrenders.
- **Quiet:** a swallowed error; a gate that stops firing; an unattended routine that stops running;
  a detector that can no longer trigger.

Quiet means the full lane at any size, as bounded in `rubric/review-discipline.md`.

**Two answers read as loud and often are not.** Both push the call toward the full lane:

1. **Leaning on a check nobody has watched fire.** "The tests cover it" is a claim *about the
   tests*. Tests have passed against both the old and the new implementation; a typecheck gate has
   turned out not to exist; a required CI job has passed green on exactly the findings it was meant
   to block.
2. **A signal that points the wrong way.** A failure that surfaces but *misattributes the cause*
   behaves like a quiet one. Database outages reported as authentication errors are highly visible
   and still send everyone to the wrong place.

**Weaker considerations** — label them weaker in the recorded reasoning:

- **Expected size** is an unreliable forecast. It is a reason to lean full, never a reason to feel
  safe about something small: silent defects arrive in small and mid-sized diffs.
- **Whether it moves a line or sits inside one already drawn** sharpens the first two answers but is
  not a signal of its own. It is hard to apply consistently, so it belongs in the recorded reasoning, not
  the decision.
- **A flaky review engine** makes the light lane unreliable as the fast option. It is a reason to
  take the full lane, never a reason to cut the review. The single reviewer keeps its normal
  ceiling: a tighter timeout only trades stalls for lost independence.

**This guidance is judgment, not a rule.** The strongest signal available is a good prior and
nothing more, and the guidance stays provisional until recorded lane calls accumulate. That is why
every lane call is recorded with its reasoning: judgment that leaves no trace generates no evidence.

## Parallel lanes that extend a shared set

When you route **parallel lanes that extend a shared registry, kind-set, or enum**, name the
**union coupling** in each issue: every lane extends the same set, so the set is complete only once
all of them have landed. Name the **completeness gate** too — the check that fails until the
extension is exhaustive — so **every lane after the first** expects it to fire and budgets the
integration commit.

## Two outcomes that look like discovery

**Two outcomes are worth naming, because both arrive looking like discovery.** A follow-up the
owner **already ruled on** — a dated, owner-attributed ruling reachable where it was made —
routes **`build-ready`** anchored to that ruling, with **no discovery step**. A follow-up raising
a **product question no approved artifact answers** routes **`discovery`** — the spec-trigger
test decides it, not how small the follow-up looks.

At routing, everything durable belongs in the issue — scope and owner decisions, process
constraints (test right-sizing, E2E policy), and launch context (local export paths,
known-broken links, environment quirks).

## Native dependency edges

An issue's native dependency edges (`blocked_by`, and `blocking`) are where holds live. An issue
body's prose about edges ("Edges:", "blocked by #n") drifts, so the advisor never reads launchability
from the body. When marking an issue build-ready, sizing it, or recommending it (as next, as
launchable, in a wave plan), the advisor reads its native `blocked_by` edges, through
`issue_contract.py check-build-ready --issue --repo` or `check-blockers`. This holds for the
sub-issues of an epic and for each layer of a stack too, each read on its own issue.

**An open blocker holds the issue, unless it is a lower layer of the same stack that is ready to
build on.** The advisor names each held blocker in the recommendation (its reference and title) and
does not call the issue launchable while one holds. An issue whose only open blockers are lower
layers of the same stack is launchable at once, as a stack layer on the layer below. A lower layer
is accepted when it is handed back as a pull request whose vet reads READY at its current head, or
when it is held only for an owner card that rides the same stack's merge sheet. Any other open
blocker still holds the issue. One helper in `lib/issue_contract.py` (`judge_open_blockers`) decides
it, and `check-build-ready --issue --repo`, `check-blockers` and the launch's base-state check
(`dispatch-preflight.md`, check 2) all reach it.

A blocker is a **lower layer of the same stack** when all of these hold:

1. It is in the same repository.
2. It is a sub-issue of the same feature issue as the blocked issue, listed before it in that
   feature's sub-issue list (`native-stacks.md` § Each layer is a sub-issue).
3. It has exactly one open pull request whose first line closes it (`native-stacks.md`, item 6).
   That pull request is the one read. READY is never read from the issue itself.
4. That pull request is not a draft.
5. Its vet reads READY at the pull request's current head, or carries the card mark below at that
   head.
6. Its pull request is in the launch's stack below the launch's `layerPosition` (a premise with
   `stack`). When the stack does not exist yet, it is the launch premise's `dependency` and in no
   stack (a premise with only `dependency`). A premise naming neither a stack nor a dependency holds
   every open blocker.

With no premise (the build-ready marking), the lower layers must all sit in one stack. When none
sits in a stack yet, exactly one may, and the result names its pull request as `requiredDependency`.
The launch premise must then name that pull request as its `dependency`, so the launcher's
dependency gate pins the base to that pull request's head.

**The card mark** is durable and never guessed. The lower layer's vet slot has a verdict line that
reads `**Verdict: PARKED** · <its current head sha> held only for a card on the stack sheet of
#<feature issue>`, where the feature issue is the stack's parent issue. A mark naming another
feature holds, as does a plain PARKED line or a mark at an earlier head. The advisor writes the mark
at vet, in the vet slot, when the owner card on the stack's sheet is the only thing holding that
layer. The launcher's dependency gate pins a card-marked dependency to its head exactly as it pins a
READY one.

The result's `blockers` always carries `checked`, `open` (every open edge), `accepted` (each
accepted layer: `ref`, `title`, `url`, `pr`, `head` its vet covers, `form` `ready` or `stack-card`,
and `stack`), `held` (each blocker that still holds, with `why`), `requiredDependency`, `stack` and
`detail`. `ok` is true when every open blocker is accepted. `blocker-open` means at least one
blocker is held, and `held` names each. An accepted blocker is never silent: it is listed in
`accepted`. Read launchability from `ok` and `reason`, never from a non-empty `open`.

`check-blockers --premise <file>` takes the launch's own premise JSON file (its `stack`,
`layerPosition` and `dependency`). A malformed premise refuses `blockers-unreadable` before any read.

**A read that fails is not "no blockers".** A failed read of the edges, the feature issue and its
sub-issue list, the open pull requests, a vet or stack membership refuses `blockers-unreadable`. The
advisor says the edges could not be read and does not call the issue launchable.

**A stricter owner rule governs.** A project whose owner has ruled a stricter rule about blockers
(for example, no layer launches before the layer below merges) keeps that rule. An accepted blocker
never overrides it.

After launch, when a card's answer sends a lower layer back and its head moves, the upper layer's
lane brings it forward, as `native-stacks.md` § How a stack stays current says.

## Scope exclusions and parity surfaces

**Enumerate audiences and channels rather than trusting recall.** A scope exclusion that leaves an
audience or delivery channel on old behavior is stated at filing as a plain consequence: *who* is
still on the old behavior, and *what they will still experience*. Obviousness is exactly what hides
a missed channel.

**Headless and interactive are parity surfaces.** A launched headless builder composes its prompt
from the byte-pinned rulings block, so a rule shipped only in prose never reaches it: the builder
keeps receiving the superseded wording while the rule reads as shipped. Name that fork as a
consequence whenever a change reaches one surface and not the other.

When no audience or channel stays on old behavior, write no consequence line.

**If it matters to the build, it is an issue line anyone can read** — never a launch line that
evaporates with the session.

## The premises of an order bind you

The premises of an order you send — the base commit, "main will not move", the sequencing you
assumed — **bind you, the dispatcher**, including when an owner merge you coordinated moves the
world under a live order. **Amend the order** when that happens. A builder that parks on a stale
premise did the right thing. Three amendments have a fixed home:

- A continuation or adoption order goes in the **issue body's STATE block**, because comments and
  PR receipts never reach a builder's intake.
- A re-handback premise's `baseCommit` is the **PR branch head**, never the stack base — a stack
  base spawns a duplicate build. A stacked layer's adoption is the exception; its fields follow
  `rubric/launch-doctrine.md` § Recovery, "An adoption of a stack layer keeps the stack fields".
- A fold into a live lane lands in **both** the issue body and an order amendment, so neither the
  builder's intake nor its live order is left stale.

**Never write a wait-for-a-later-message step into a headless builder's order or its amendment.**
"Hold until I relay", "wait for my go" and every step like them ask the builder to hear a message
sent after launch, and a running headless session cannot: it waits for nothing, or ends its turn and
stops. Write the condition into the issue body instead, as something the builder can read for
itself, and have the builder park durably when the condition does not hold. The builder side is
workhorse's park rule (a headless builder parks when an in-turn wait cannot fit). A cloud builder's
own builder note, a question it asks with a bounded reply window, is not such a step.

A mis-routed "ready" issue that turns out unclear is caught by the builder's stop-and-report
safeguard, which the workhorse charter defines. You own the route; the builder owns that safeguard.
