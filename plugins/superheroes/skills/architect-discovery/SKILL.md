---
name: discovery
description: Use at the START of any new piece of work in a superheroes project — when a fuzzy idea needs to become an owner-approved requirements spec. It OWNS the requirements front-half — the *what*, in plain language, no technical implementation. Elicits requirements (incl. significant unhappy paths) with the owner, produces the `spec` definition-doc, and ends with the owner's approval. Not for the technical *how* (that stays with the build) or for code — the spec is the *what*.
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# Discovery

Turn a fuzzy idea into an owner-approved definition-doc: the requirements for one piece of
work, in plain language, with **no technical *how***. This is the **requirements front-half**
of the superheroes loop. You own the **what**; the **how** stays with the build — the builder
makes it explicit in its build brief, never a plan document.

Discovery is the requirements **front door**: it turns a fuzzy idea into the owner-approved
**`spec`**. The skill opens in **gather + frame** mode (steps 1–5), then authors and reviews
the spec (steps 6–8).

The audience is a product-minded owner who may not be technical. Speak their
language. Translate every non-functional concern into a plain-language outcome.
When a genuine choice needs the owner, present it with approachable pros/cons —
never with jargon.

<HARD-GATE>
Do NOT author the spec, write any code, mint a work-item, or hand off until you
have presented the framing (the **what**) and the owner has explicitly
approved it. And do NOT consider Discovery finished until the owner gives their
final approval of the written spec (step 8) — review-crew advises, the owner
decides. A spec can be short; it cannot be skipped, and its gates cannot be
self-approved — you may *record the owner's* explicit approval (step 8), but never
approve on your own behalf.
</HARD-GATE>

## Checklist

Create a TodoWrite item for each step and complete them in order:

1. **Initial context gathering**
2. **Research check** → research only if it helps (and the owner consents to spend)
3. **Requirements dialogue** (one question at a time; EARS phrasing; run the coverage checklist)
4. **UI/UX** when relevant (hand the owner a Claude Design prompt)
5. **Confirm the framing → owner approves the *what*** ← HARD GATE
6. **Author the spec** via the `writing-specs` skill
7. **Review-spec** (automated gate; fix findings before the owner spends time)
8. **Owner review & final approval** ← terminal gate; the approved spec is the ready artifact

## The steps

### 1. Initial context gathering

- **`CLAUDE.md` is mandatory context, not optional reading.** If it is **not
  already in your context, read it now** (plus any nested `CLAUDE.md` governing
  paths you'll touch) before gathering anything else — its rules are binding and
  override your defaults. Then explore the rest: `README`, recent commits, and any
  existing `docs/superheroes/` specs — understand what exists before asking.
- **You are the Discovery engine for this project.** Requirements work in a
  superheroes project routes here — do **not** invoke superpowers `brainstorming`.
  You may borrow its *technique* (one question at a time, explore before deciding,
  present-and-approve), but the artifact you produce is the superheroes `spec` and
  the phase ends with the owner's approval, not with `writing-plans`.
- **Scope check.** If the idea is really several independent pieces (e.g. "a
  platform with chat, billing, and analytics"), say so before refining details.
  Help the owner pick the **first** piece; each piece gets its own
  spec. Recursion is one level — don't decompose a
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
  genuine either/or decisions.
- **Frame every consequential choice — recipe, in order.** A choice is
  *consequential* when getting it wrong would change the spec's scope, an
  owner-visible behavior, the `size`, or cost/risk the owner carries. For each one,
  the message *before* the question lays out, in this order:
  1. **The decision & why it matters** — one or two plain sentences: what's being
     decided and what it changes for the owner. No internal jargon; if a term is
     unavoidable, define it in the same breath.
  2. **The options** — 2–3 named options, each with a one-line plain-language *pro*
     and *con* (the real trade-off, not a restatement of the label).
  3. **Your recommendation** — name the option you'd pick and why, in one line, and
     mark it `(Recommended)` in the choices. No confident pick? Say so ("close call —
     your call") rather than feigning neutrality.

  Then ask: the `AskUserQuestion` option labels stay crisp — the framing already
  lives in the message above — with `(Recommended)` on your pick. A *trivial*
  confirmation (naming, a yes/no with one obvious default, a detail with no downside)
  needs none of this; ask it in a line.
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
  3. No implementation/how (tech, data models, frameworks, APIs) — that belongs to the build, not the spec.
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

If the owner doesn't have or doesn't want to use Claude Design, **don't block** —
capture the UI/UX as a plain-language description of the key screens and states in
the spec instead.

**Design-capture peer (host-neutral):** capture the design source using the path appropriate for your host — Claude Design on Claude Code; the host-native design-capture path on Codex (resolve via `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md`). Record *which* source was used in the spec's `## UI / UX` section so the artifact is traceable regardless of host.

`mcp__visualize__show_widget` (inline SVG/HTML) may help for a quick option
comparison **on graphical clients only** — it does **not** render in a terminal, so
never rely on it; always have a plain-text description as the fallback.

### 5. Confirm the framing → owner approves the *what* (HARD GATE)

Present a compact **decision brief** the owner can digest in under a minute — not a replay
of every requirement (that is the spec, which they review at step 8):
- **One line each:** what this is, who it's for, and the `size` you're assigning.
- **Load-bearing decisions** — the handful of calls that shape the work: the
  resolutions you reached on the consequential questions, plus any default you chose
  on the owner's behalf. One line each.
- **Still open** — anything unresolved or assumed that the owner should rule on now.

Ask: *"Does this framing look right? Anything to change before I write it up?"* **Do not
proceed past this gate until the owner approves the framing.** Revise and re-present as
needed. The full, requirement-by-requirement review happens **once**, on the authored spec
(step 8) — not twice. Then continue to step 6 (author the spec).

Decide two things here **yourself** — never make the owner pick them:
- **Title / slug** — choose a concise, accurate work-item title from the approved
  requirements; it's the sole input to the *frozen* work-item slug (§6.1), so pick it
  deliberately (it can't change later). Don't ask the owner to choose or confirm it —
  they'll see it in the spec they review.
- **`size`** (`small | medium | large`) — infer it from the scope of the approved
  requirements. The skill decides; the owner never picks. It's frozen into the spec (§6.4).

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
**If `review-spec` is not available in this project**, say so and proceed to step 8 —
the self-review (step 6) stands in, and the owner's review is the terminal gate
regardless. Never fabricate a review result.

### 8. Owner review & final approval (terminal gate)

Ask the owner to review the written spec. **Tell them the truth about whether an
automated review ran** — never claim a review that didn't happen:

> *If `review-spec` ran (step 7):* "Spec written to
> `docs/superheroes/<work-item>/spec.md` and through automated review. Please review
> it and tell me if you want any changes before it goes to the build."
>
> *If `review-spec` was unavailable:* "Spec written to
> `docs/superheroes/<work-item>/spec.md`. Automated spec-review isn't set up on this
> project, so it's coming straight to you — please review it and tell me if you want
> any changes before it goes to the build."

- If the owner requests changes, apply them and (where available) **re-run
  `review-spec` on the deltas** before coming back to them.
- **The owner's approval is the terminal gate** — review-crew advises, the owner
  decides. **Only once the owner explicitly approves**, record their decision so the
  work-item is ready to build:

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
  ROOT=$(git rev-parse --show-toplevel)
  WORK_ITEM="<work-item>"
  DOC_PATH=$(python3 "$ROOT_DIR/lib/definition_doc.py" path \
    --doc spec --work-item "$WORK_ITEM" --root "$ROOT")
  HASH=$(python3 "$ROOT_DIR/lib/definition_doc.py" content-hash --path "$DOC_PATH")
  python3 "$ROOT_DIR/lib/definition_doc.py" set-gate \
    --doc spec --work-item "$WORK_ITEM" --review passed --root "$ROOT" \
    --expected-hash "$HASH" --run-id "selfcert-$WORK_ITEM"
  ```

  This writes `gates.review: passed` (and derives `status: approved`) — the
  machine-readable signal that the spec is approved (and the only thing that flips the gate
  when `review-spec` isn't wired yet). Recording the **owner's** explicit decision is
  **not** self-approval — the HARD-GATE forbids *you* rubber-stamping your own
  un-reviewed work, not recording the owner's call. Run this **after** the owner says
  yes, never before.
- **Discovery is done — hand back (FR-1).** With the spec approved, Discovery's job is
  complete: the owner-approved spec is the ready artifact. Do **not** start a build yourself —
  hand back to the owner, who routes the approved work-item to a build session. The spec's
  approval gate is the authoritative signal.

## Rationalization table

| Excuse | Reality |
| --- | --- |
| "This is too simple to need a spec" | A spec can be short; it cannot be skipped — discovery produces the *what*. "Simple" is never license to skip the thinking or fabricate requirements. |
| "I'll just use brainstorming" | In a superheroes project, Discovery is this skill. Produce a `spec`. |
| "Let me note the tech approach" | The *how* is the build's. Keep the spec to the *what*. |
| "Happy path is enough" | The significant unhappy paths are the anti-slop core. Run the coverage checklist. |
| "I'll research to be thorough" | Research is consented — offer it, name the time/usage cost, let the owner choose. |
| "The owner's sure, skip research" | Confidence isn't correctness. Offer a quick prior-art check on consequential calls. |
| "review-spec passed, that's done" | review-crew advises; the **owner** has the final say (step 8). |
| "Owner approved the idea, start building" | The HARD GATE needs explicit approval of the *what*, then the written spec, before the build. |
| "Restate every requirement so they can approve" | Step 5 is a compact decision brief, not a spec replay. The requirement-by-requirement review is the spec (step 8) — don't double-review. |
| "They can infer the trade-offs from the options" | A consequential question carries its own why-it-matters, per-option pro/con, and a recommendation (step 3) — in plain language, before the ask. |
