<!-- method-detail-version: 1 -->

## Self-review checklist

Look at the written plan with fresh eyes; fix inline. This is where a *plausible* plan is
caught being a *wrong* one.

**Design-quality hard gates**
- [ ] **≥2 materially different options** (differing on a named axis, each a genuine
  contender — not a strawman) were weighed before each significant choice, and the
  strongest case for the rejected option is stated.
- [ ] **Every recorded decision names its accepted downside** (not just the upside).

**Grounded & verified (the LLM failure-mode guards)**
- [ ] Significant decisions cite a concrete file/symbol they match or depart from; no
  citation → marked an assumption. Designed from the real codebase, not in a vacuum.
- [ ] **Every new package/library is confirmed to exist** and every API/param/config key is
  confirmed against the **installed version's** docs — not plausible-sounding memory. A
  verification miss is a **hard stop**, not a footnote. (Package hallucination is real.)
- [ ] Matches the project's actual stack and conventions; reuses existing abstractions.

**Simple, honest, complete**
- [ ] Solves only the stated task — no abstraction without **three** real call sites
  (the rule of three), no new dependency without a one-line justification; a
  subtraction pass was done.
- [ ] Assumptions are listed; if the spec's implied approach is wrong, the plan says so
  (correctness over agreement).
- [ ] Failure modes and an explicit security/privacy pass are covered (not happy-path only).

**Good-doc quality markers**
- [ ] **Trade-offs present, not an implementation manual** — every significant choice has a
  *why* and the alternatives it beat.
- [ ] **Non-goals stated;** scope boundary explicit.
- [ ] **Operability answered:** "how does on-call debug this at 2am?" and "how do we turn it
  off / roll back?" — or marked N/A with a reason.
- [ ] **Right altitude:** no pasted full schemas, full code, test cases, or dated rollout
  steps — those belong to Tasks. Strategy yes, steps no.
- [ ] **Right-sized** for `size`; situational sections collapsed to "N/A — because …" rather
  than padded or silently dropped.
- [ ] **Reader test:** a build agent could implement from this and not be surprised.

**Coverage & cleanup**
- [ ] Every spec requirement (functional, NFR, unhappy path, constraint) is addressed, and
  nothing in the plan lacks a spec basis.
- [ ] **No open questions left parked** — each is escalated, made a Risk-with-contingency,
  deferred to Tasks, or looped back; no missed escalation (a hard-to-reverse **and**
  owner-weighable decision you decided silently).
- [ ] No `{{…}}` or leftover `<!-- AUTHOR GUIDANCE … -->` comment remains.
