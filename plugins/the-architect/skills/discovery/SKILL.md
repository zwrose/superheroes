---
name: discovery
description: Use at the START of any new piece of work in a superheroes project — when the owner has a fuzzy idea, feature request, bug, or "let's build / add / change / fix X" and it needs to become an owner-approved requirements spec. This is superheroes' Discovery phase: it OWNS the requirements front-half — the *what*, in plain language, no technical implementation — and supersedes generic brainstorming here. Elicits requirements (incl. significant unhappy paths) with the owner, optionally researches prior art, captures UI/UX via Claude Design, produces the `spec` definition-doc, runs it through review-spec, and ends with the owner's approval. Not for technical approach (that is `plan`) or steps (that is `tasks`).
---

# Discovery

Turn a fuzzy idea into an owner-approved **`spec`** definition-doc: the requirements
for one piece of work, in plain language, with **no technical *how***. This is the
front half of the superheroes loop (Discovery → Plan → Tasks → Build → Verify →
Integrate). You own the **what**; the `plan` skill owns the **how**.

The audience is a product-minded owner who may not be technical. Speak their
language. Translate every non-functional concern into a plain-language outcome.
When a genuine choice needs the owner, present it with approachable pros/cons —
never with jargon.

<HARD-GATE>
Do NOT author the spec, write any code, mint a work-item, or hand off until you
have presented the requirements (the **what**) and the owner has explicitly
approved them. And do NOT consider Discovery finished until the owner gives their
final approval of the written spec (step 8) — review-crew advises, the owner
decides. A spec can be short; it cannot be skipped, and its gates cannot be
self-approved.
</HARD-GATE>

## Checklist

Create a TodoWrite item for each step and complete them in order:

1. **Initial context gathering**
2. **Research check** → research only if it helps (and the owner consents to spend)
3. **Requirements dialogue** (one question at a time; EARS phrasing; run the coverage checklist)
4. **UI/UX** when relevant (hand the owner a Claude Design prompt)
5. **Present requirements → owner approves the *what*** ← HARD GATE
6. **Author the spec** via the `writing-specs` skill
7. **Review-spec** (automated gate; fix findings before the owner spends time)
8. **Owner review & final approval** ← terminal gate; then ready for Plan

## The steps

### 1. Initial context gathering

- Explore the project first: `CLAUDE.md`, `README`, recent commits, existing
  `docs/superheroes/` specs. Understand what already exists before asking.
- **You are the Discovery engine for this project.** Requirements work in a
  superheroes project routes here — do **not** invoke superpowers `brainstorming`.
  You may borrow its *technique* (one question at a time, explore before deciding,
  present-and-approve), but the artifact you produce is the superheroes `spec` and
  the phase ends with the owner's approval, not with `writing-plans`.
- **Scope check.** If the idea is really several independent pieces (e.g. "a
  platform with chat, billing, and analytics"), say so before refining details.
  Help the owner pick the **first** piece; each piece gets its own
  spec → plan → tasks cycle. Recursion is one level — don't decompose a
  decomposition.

### 2. Research check → research only if it helps

Internet research can ground requirements in prior art, market norms, and
feasibility — but it costs the owner time and usage, so decide deliberately:

- **Research likely helps when** the work is novel, in an unfamiliar domain,
  medium-or-large, the requirements are vague, or it's a user-facing "what do other
  products do here?" call.
- **A confident owner is not an automatic skip.** Confidence isn't correctness — an
  owner can be sure and still be missing something. If the call is consequential,
  offer a quick prior-art check rather than assuming.
- **Consent is the floor for anything non-trivial.** A single quick lookup can run
  on its own; but before any deeper research (especially the `deep-research`
  capability), name in plain language that it would help and roughly what it costs
  **in time and extra usage** — never a dollar figure (owners are typically on
  usage plans, not per-token billing) — and let the owner choose. Never silently
  spend on discretionary research.
- **Skip for** small or mechanical, well-understood work.

When you do research, use `deep-research` if available, else `WebSearch`/`WebFetch`;
if neither is available, say so and proceed. Report findings in **plain language**
("most apps in this space do X; the trade-off is Y") — never raw dumps.

### 3. Requirements dialogue (one question at a time)

Refine the idea through natural dialogue, capturing requirements in **EARS** form:

- **One question per message.** Prefer multiple-choice; use `AskUserQuestion` for
  genuine either/or decisions with approachable options.
- **Phrase each requirement as EARS** (the owner answers in plain language; you
  reflect it back as a constrained sentence and confirm):
  - Ubiquitous: *The system shall &lt;response&gt;.*
  - Event-driven: *When &lt;trigger&gt;, the system shall &lt;response&gt;.*
  - State-driven: *While &lt;state&gt;, the system shall &lt;response&gt;.*
  - Optional: *Where &lt;feature is present&gt;, the system shall &lt;response&gt;.*
  - Unwanted behavior: *If &lt;bad thing&gt;, then the system shall &lt;response&gt;.*
- **Enforce the anti-slop rules** as you capture:
  1. One requirement, one behavior — no "and/or" chaining (split it).
  2. No vague/unmeasurable words (fast, secure, robust, user-friendly, handle,
     support, manage, always/never, some/most) — name the concrete behavior or a
     fit-criterion.
  3. No implementation/how (tech, data models, frameworks, APIs) — that's the `plan`.
  4. Every functional requirement is verifiable — capture **≥1 acceptance
     criterion** (a Given-When-Then scenario, or a pass/fail rule). If you can't
     write one, the requirement is too vague to keep.
- **Run the coverage checklist** — the happy path plus the *significant* unhappy
  paths. Probe each owner-facing area; tag it **Specify / Defer-to-plan / N-A** so a
  skip is a recorded decision. Risk-gate: go deeper only where a failure costs
  money, data, safety, trust, or legal standing. One representative case per area,
  not a matrix.

  | Coverage area | Ask the owner |
  | --- | --- |
  | **Empty & first-run states** | What do they see the first time, or with nothing here yet? |
  | **Invalid & malformed input** | If they enter something wrong/blank, what happens and what message? |
  | **Boundaries & limits** | Any limits that matter, and behavior right at / just past them? |
  | **Errors & failures** | When something fails (not their fault), what do they see and do? |
  | **Access & permissions** | Who may, who may not, and what does the wrong person see? |
  | **Duplicates & double-actions** | What if they submit twice or double-click? |
  | **Conflicting / simultaneous use** *(multi-user)* | Two people change the same thing — last wins, lock, merge? |
  | **Misuse & abuse** *(sensitive features)* | Could someone abuse this (money, private data) — what must we prevent? |
  | **Reach** *(if in scope)* | Other languages/currencies/timezones? Keyboard + screen-reader usable? |

  Connectivity & timing failures (dropped network, timeouts, duplicate requests at
  the wire) are **defer-to-plan**: capture only the owner-visible *promise* ("a
  dropped connection never loses their work").
- **Non-functional needs** are captured as **outcomes with a measurable bar** ("a
  page they wait on responds within 2 seconds", "only the owner can see their
  data"), never as mechanisms.

### 4. UI/UX when relevant (hand the owner a Claude Design prompt)

If the work is user-facing, the design is created in **Claude Design** — a separate
surface — and its output is referenced by the spec. The flow is **text-first** so it
works for owners on any client (including a terminal):

1. From the requirements so far, compose a **Claude Design prompt** (the feature,
   who it's for, key screens/states, tone, and any design-system reference) and hand
   it to the owner.
2. The owner creates and iterates the design in Claude Design, then brings back its
   **handoff output**.
3. The spec's UI/UX section **references that actual handoff output**, not a
   reinterpretation.

`mcp__visualize__show_widget` (inline SVG/HTML) may help for a quick option
comparison **on graphical clients only** — it does **not** render in a terminal, so
never rely on it; always have a plain-text description as the fallback.

### 5. Present requirements → owner approves the *what* (HARD GATE)

Present the requirements back in sections scaled to complexity — purpose, who it's
for, functional requirements, the significant-unhappy-path behaviors, non-functional
outcomes, UI/UX, definition of done, assumptions, constraints, out-of-scope. Ask
after each section whether it's right. **Do not proceed past this gate until the
owner explicitly approves the *what*.** Revise and re-present as needed.

Settle two things here with the owner:
- **Title** — a concise work-item title. It's the sole input to the *frozen*
  work-item slug (§6.1), so confirm it with the owner; it shouldn't be improvised.
- **`size`** (`small | medium | large`) — owner-chosen or inferred from scope. It's
  frozen into the spec and inherited by plan/tasks (§6.4).

### 6. Author the spec via `writing-specs`

Once the owner has approved the requirements, invoke the **`writing-specs`** skill
to mint the work-item, emit the §3.1 frontmatter, fill the body template, and write
the spec to `docs/superheroes/<work-item>/spec.md`. Hand it the approved set:
**title, purpose, who-it's-for, the functional requirements (EARS + acceptance
criteria), the significant-unhappy-path requirements, non-functional requirements,
UI/UX outcome, definition of done, assumptions & dependencies, constraints,
out-of-scope, and `size`.** That skill owns the on-disk artifact; you own the
dialogue that feeds it.

### 7. Review-spec (automated gate)

Run review-crew's **`review-spec`** on the authored spec and address its findings
**before** asking the owner to spend their time — the automated review catches
ambiguity, missing coverage, and tech leakage the owner would otherwise have to.
Fix what it raises (or, where it's a judgment call, note it for the owner).

### 8. Owner review & final approval (terminal gate)

Ask the owner to review the written, review-passed spec:

> "Spec written to `docs/superheroes/<work-item>/spec.md` and through review.
> Please review it and tell me if you want any changes before it moves to planning."

- If the owner requests changes, apply them and **re-run `review-spec` on the
  deltas** before coming back to them.
- **The owner's approval is the terminal gate** — review-crew advises, the owner
  decides. On approval, Discovery is done and the spec is ready for the (more
  autonomous) **Plan** phase. Do **not** start `plan` yourself — hand off; the
  producer/owner drives the transition.

## Rationalization table

| Excuse | Reality |
| --- | --- |
| "This is too simple to need a spec" | Simple work is where bad assumptions hide. Short spec, never skipped. |
| "I'll just use brainstorming" | In a superheroes project, Discovery is this skill. Produce a `spec`. |
| "Let me note the tech approach" | The *how* is the `plan`. Keep the spec to the *what*. |
| "Happy path is enough" | The significant unhappy paths are the anti-slop core. Run the coverage checklist. |
| "I'll research to be thorough" | Research is consented — offer it, name the time/usage cost, let the owner choose. |
| "The owner's sure, skip research" | Confidence isn't correctness. Offer a quick prior-art check on consequential calls. |
| "review-spec passed, that's done" | review-crew advises; the **owner** has the final say (step 8). |
| "Owner approved the idea, start planning" | The HARD GATE needs explicit approval of the *what*, then the written spec, before Plan. |
