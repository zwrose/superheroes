---
name: discovery
description: Use at the START of any new piece of work in a superheroes project — when the owner has a fuzzy idea, feature request, bug, or "let's build / add / change / fix X" and it needs to become a reviewed requirements spec. This is superheroes' Discovery phase: it OWNS the requirements front-half — the *what*, in plain language, no technical implementation — and supersedes generic brainstorming here. Elicits requirements (incl. significant unhappy paths) with the owner, optionally researches prior art, captures UI/UX, then produces the `spec` define-doc and hands to review-spec. Not for technical approach (that is `plan`) or steps (that is `tasks`).
---

# Discovery

Turn a fuzzy idea into an owner-approved **`spec`** define-doc: the requirements
for one piece of work, in plain language, with **no technical *how***. This is
the front half of the superheroes loop (Discovery → Plan → Tasks → Build →
Verify → Integrate). You own the **what**; the `plan` skill owns the **how**.

The audience is a product-minded owner who may not be technical. Speak their
language. Translate every non-functional concern into a plain-language outcome.
When a genuine choice needs the owner, present it with approachable pros/cons —
never with jargon.

<HARD-GATE>
Do NOT author the spec, write any code, mint a work-item, or hand off to any
other skill until you have presented the requirements (the **what**) and the
owner has explicitly approved them. This holds for every project regardless of
perceived simplicity — "too simple to need a spec" is exactly where unexamined
assumptions cost the most. A spec can be short; it cannot be skipped.
</HARD-GATE>

## Checklist

Create a TodoWrite item for each step and complete them in order:

1. **Context + supersede brainstorming**
2. **Research gate** → research only if promoted
3. **Requirements dialogue** (one question at a time; run the coverage checklist)
4. **UI/UX** when relevant (visuals / Claude Design)
5. **Present requirements → owner approves the *what*** ← HARD GATE
6. **Author the spec** via the `writing-specs` skill
7. **Spec self-review + owner review gate**
8. **Hand off to `review-spec`** (NOT writing-plans)

## The steps

### 1. Context + supersede brainstorming

- Explore the project first: `CLAUDE.md`, `README`, recent commits, existing
  `docs/superheroes/` specs. Understand what already exists before asking.
- **You are the Discovery engine, not superpowers `brainstorming`.** In a
  superheroes project, requirements work routes here. If the project's
  `CLAUDE.md` carries a routing line ("Discovery → use the-architect
  `discovery`, not brainstorming"), it has already settled this. If it does not
  (Phase 1 — `init` that writes the line lands in 2a), proceed here anyway and
  do **not** invoke `brainstorming`: this skill is the requirements front-half
  for this band. You may borrow brainstorming's *technique* (one question at a
  time, explore before deciding, present-and-approve) — but the artifact you
  produce is the superheroes `spec`, and the terminal hand-off is `review-spec`,
  never `writing-plans`.
- **Scope check.** If the idea is really several independent pieces (e.g. "a
  platform with chat, billing, and analytics"), say so before refining details.
  Help the owner pick the **first** piece; each piece gets its own
  spec → plan → tasks cycle. Recursion is one level — don't decompose a
  decomposition.

### 2. Research gate → research only if promoted

Internet research is **first-class but gated** — it grounds requirements in
prior art, market norms, and feasibility, but it costs tokens, so don't run it
by reflex. Run a quick gate first:

- **PROMOTE research when** the work is novel, in an unfamiliar domain,
  medium-or-large, the requirements are vague, the owner is unsure what they
  want, or it's a user-facing "what do other products do here?" call.
- **SKIP for** small or mechanical work, well-understood territory, or when the
  owner already knows exactly what they want.
- **Borderline but expensive?** **Ask the owner first** — name that research
  would help and roughly what it costs, and let them choose. Never silently
  spend on discretionary research.

When promoted, use the `deep-research` capability if available; otherwise fall
back to `WebSearch`/`WebFetch`, and if neither is available, say so and proceed.
Report findings in **plain language** ("most apps in this space do X; the
trade-off is Y") — never raw dumps.

### 3. Requirements dialogue (one question at a time)

Refine the idea through natural dialogue:

- **One question per message.** Prefer multiple-choice when it's cleaner; use
  `AskUserQuestion` for genuine either/or decisions with approachable options.
- Focus on **purpose, constraints, and success criteria** — the *what* and
  *why*, never the *how*.
- Translate non-functional needs into plain outcomes ("results feel instant",
  "safe on a phone", "only you can see your data") and confirm them.
- **Run the coverage checklist** as you go — this is the anti-slop core. The
  spec must cover the happy path **and the significant unhappy paths**. Don't
  enumerate exhaustively; do proactively probe the ones that matter:

  | Coverage area | Ask the owner |
  | --- | --- |
  | **Empty / initial states** | What do they see on first run, or with nothing yet? |
  | **Errors & failures** | What happens when an action can't complete — and what are they told? |
  | **Edge & boundary cases** | Limits, very large/odd inputs, duplicates, simultaneous use? |
  | **Access & permissions** | Who may do what? What does an unauthorized/signed-out attempt do? |
  | **Input validation** | What's valid input, and how is invalid input handled? |

  Capture these as **behavioral requirements + acceptance criteria** (owner-
  visible WHAT), not as technical mechanisms (that's the `plan`).

### 4. UI/UX when relevant (visuals / Claude Design)

If the work is user-facing, explore the interface here (its outcome is recorded
in the spec; the `plan` only references how it gets built):

- For quick mockups, diagrams, or option comparisons, use the
  `mcp__visualize__show_widget` tool (inline SVG/HTML) — pick it when the owner
  would understand something better by **seeing** it than reading it.
- For real UI/design-system work, use **Claude Design** via the `DesignSync`
  tool / `/design-sync` skill when available.
- Both are *when-available*; if neither is, fall back to a clear text
  description of the screens and states. Never block on a visual tool.

### 5. Present requirements → owner approves the *what* (HARD GATE)

Present the requirements back in sections scaled to their complexity — purpose,
functional requirements, the significant-unhappy-path behaviors, any
non-functional needs, UI/UX outcome, acceptance criteria, out-of-scope. Ask
after each section whether it's right. **Do not proceed past this gate until the
owner explicitly approves the *what*.** Revise and re-present as needed.

Also settle **`size`** here (`small | medium | large`) — owner-chosen or
inferred from scope. It is frozen into the spec and inherited by plan/tasks
(CONVENTIONS §6.4).

### 6. Author the spec via `writing-specs`

Once the owner has approved the requirements, invoke the **`writing-specs`**
skill to mint the work-item, emit the §3.1 frontmatter, fill the body template,
and write the spec to `docs/superheroes/<work-item>/spec.md`. That skill owns
the on-disk artifact; you own the dialogue that feeds it. Hand it the approved
requirements (purpose, the requirement set including unhappy-path behaviors,
acceptance criteria, UI/UX outcome, out-of-scope, `size`).

### 7. Spec self-review + owner review gate

`writing-specs` runs a self-review (placeholders, contradictions, scope,
ambiguity) and fixes inline. Then ask the owner to review the written file:

> "Spec written to `docs/superheroes/<work-item>/spec.md`. Please review it and
> tell me if you want any changes before it goes to review."

If they request changes, make them and re-run the self-review. Only proceed once
the owner approves the written spec.

### 8. Hand off to `review-spec`

The terminal state is the **`review-spec`** gate (review-crew owns it) — **not**
`writing-plans` and **not** the `plan` skill directly. Discovery's job ends when
the owner-approved spec is ready for review. (In Phase 1, if `review-spec` is
not yet wired, state that the spec is ready for the review gate and stop — do
not start the plan.)

## Rationalization table

| Excuse | Reality |
| --- | --- |
| "This is too simple to need a spec" | Simple work is where bad assumptions hide. Short spec, never skipped. |
| "I'll just use brainstorming" | In a superheroes project, Discovery is this skill. Produce a `spec`, hand to `review-spec`. |
| "Let me note the tech approach while I'm here" | The *how* is the `plan`. Keep the spec to the *what*. |
| "Happy path is enough" | The significant unhappy paths are the anti-slop core. Run the coverage checklist. |
| "I'll research to be thorough" | Research is gated — promote it by the rubric or ask the owner. Don't silently spend. |
| "Owner seemed fine, I'll start the plan" | The HARD GATE needs an *explicit* approval of the what. Then `writing-specs`, then `review-spec`. |
