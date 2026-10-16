# Perceivability net (Test 1 default)

The enumerable net for Test 1's default perceivability call. Read this when making the presentation call at routing.

The net decides only whether a change is perceivable, which is the presentation call. Whose call it is gets decided by the [owner-vs-craft line](../../../rubric/owner-vs-craft-line.md) (Test 2), never by this net.

That net is deliberately wide and, **alone, too wide**; Test 2 decides whose call it is.

   **Test 1's net (default)** — a change is perceivable when it moves any of:
   - what it **says** (copy, messages, errors, generated reports);
   - what the user reads to **operate** it (docs, help text, labels);
   - what it **asks of them** (prompts, confirmations, how often it interrupts and why);
   - what it **costs** (latency and spend on paths users actually hit);
   - what it **leaves behind** (files, data, artifacts in the user's space);
   - what it **emits on their behalf** (posts, notifications, third-party calls, public records);
   - **defaults and failure policy** (unconfigured behavior; what happens when something breaks);
   - **visual and interactive surface** (UI, layout, flow).

**Overlap (owner call vs craft call):** fail-direction inside an already-chosen policy is the lenses' craft call; changing what the product does **by default for an unconfigured user** touches categories 4 and 5 of the line ([the ten owner categories](../../../rubric/owner-vs-craft-line.md#the-ten-owner-categories)) and is the owner's.

A duty that first appears at handback is a duty nobody was resourced to discharge; the same holds for the wayfinding half — an entry point is **planned**, not retrofitted after the last dispatch returns.

The mid-build revision valve exists because the call will sometimes be wrong, and a wrong call must not become an undischargeable duty.

**Issue bodies do not adopt the two-half PR template** — an issue's readers ask *is this worth doing*, a different question from *do I merge*.
