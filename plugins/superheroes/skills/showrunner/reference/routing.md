# Routing — the lane call and routing detail

This page is reference for the advisor at routing time. It holds the guidance behind the lane call
and the routing detail that fires only on some routes. The rules it serves live in duty 3 of the
Showrunner charter; the lane table and the cross-lane invariants live in
`rubric/review-discipline.md`.

## The lane call — the question that governs

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

**Weaker considerations** — label them weaker in the conversation:

- **Expected size** is an unreliable forecast. It is a reason to lean full, never a reason to feel
  safe about something small: silent defects arrive in small and mid-sized diffs.
- **Whether it moves a line or sits inside one already drawn** sharpens the first two answers but is
  not a signal of its own. It is hard to apply consistently, so it belongs in the conversation, not
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

A mis-routed "ready" issue that turns out unclear is caught by the builder's stop-and-report
safeguard, which the workhorse charter defines. You own the route; the builder owns that safeguard.
