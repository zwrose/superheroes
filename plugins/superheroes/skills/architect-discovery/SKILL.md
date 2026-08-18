---
name: discovery
description: Use at the START of any new piece of work in a superheroes project — when a fuzzy idea needs to become an owner-approved requirements spec. It OWNS the requirements front-half — the *what*, in plain language. Elicits requirements (incl. significant unhappy paths) with the owner, produces the `spec` definition-doc, or exits through a findings record or a park note. Not the technical *how* (that stays with the build).
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# Discovery

Turn a fuzzy idea into requirements the build can be graded against: the *what* for one piece
of work, in plain language, with **no technical *how***. This is the **requirements front-half**
of the superheroes loop. You own the **what**; the **how** stays with the build — the builder
makes it explicit in its build brief, never a plan document.

Discovery is the requirements **front door**, and its **usual** outcome is the owner-approved
**`spec`** — steps 1–8 below are that path. It is not the only ending: a discovery can also
close on a **findings record** or a **park note** (see **The three exits**). The skill opens in
**gather + frame** mode (steps 1–5), then authors and reviews the spec (steps 6–8).

The audience is a product-minded owner who may not be technical. Speak their
language. Translate every non-functional concern into a plain-language outcome.
When a genuine choice needs the owner, present it with approachable pros/cons —
never with jargon.

<HARD-GATE>
**On the spec path (Exit A):** do NOT author the spec, write any code, mint a
work-item, or hand off until you have presented the framing (the **what**) and the
owner has explicitly approved it. And do NOT consider that path finished until the
owner gives their final approval of the written spec (step 8) — review-crew advises,
the owner decides. A spec can be short; on this path it cannot be skipped, and its
gates cannot be self-approved — you may *record the owner's* explicit approval
(step 8), but never approve on your own behalf.

**The two other exits are not loopholes in that gate — they are the other two ways a
discovery legitimately ends** (see **The three exits**). Each closes by writing its own
durable artifact, which is why **Exit B mints the work-item and places its record** and
why **Exit C hands back with no approved spec**. Where a draft was already written before
the park — step 7's unweighable draft is the usual case — **the draft stays on disk at the spec
path `resolve-write --doc spec` reports, with `status: draft`, and the park note carries that
path, never a second copy**. The draft is neither discarded nor treated as an artifact anything may anchor to. What is never permitted on any exit is fabricating a spec, or approving one on
the owner's behalf.
</HARD-GATE>

## The one front door

Requirements work has exactly one door, and this is it. **The plugin offers no separate spike
or investigation surface** — "spike" survives only as the informal name of discovery's
investigation phase (step 2), and **when an investigation ends, discovery's exit gate is still
ahead**. There is no path that investigates its way into a build without passing an exit.

**A decision the owner has already made needs no discovery.** An owner decision recorded as a
**dated ruling** — a micro dictation, a mid-build ruling, or a ruling in the advisor's channel
such as a PR follow-up — is already the *what*: the advisor records it where it was made and
files against it directly. **What that filing routes to is the advisor's call, not
discovery's** — this skill only declines the work; it does not name the route. A follow-up that
raises a product question no approved artifact answers is *not* a recorded ruling, and it comes
here.

## The three exits

Discovery ends in **exactly one of three exits**. Each one lands a **durable artifact**, and
**every exit reports to the advisor** — an exit that happened only in the conversation is not
an exit.

| Exit | Durable artifact | Where |
| --- | --- | --- |
| **A — the approved spec** | `spec.md` in the work-item folder, its review gate flipped on the owner's explicit approval | steps 6–8 |
| **B — the findings record** | `findings.md` beside where the spec would live, carrying the owner's recorded ratification | below |
| **C — the park note** | the full park note on the owner's reading surface, plus a durable copy on the item's issue or PR | below |

**No spec is ever fabricated to close a discovery.** An investigation that finds no new product
surface exits through the **findings record** — never through a thin spec written so there is
something to hand over.

### Exit B — the findings record

Take it when the work resolves without opening a new product surface: the answer is "there is
nothing to specify", "what exists already covers it", or "the idea does not survive contact
with what is there."

1. **Mint the work-item** if one does not exist yet, then resolve **the folder** the spec would
   occupy. Use the canonical form — the bare script name is not on `PATH`:

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
   ROOT=$(git rev-parse --show-toplevel)
   WORK_ITEM=$(python3 -B "$ROOT_DIR/lib/definition_doc.py" mint --title "<title>") \
     || { echo "the-architect: cannot mint the work-item (see message above) — not writing the findings record." >&2; exit 1; }
   [ -n "$WORK_ITEM" ] \
     || { echo "the-architect: mint returned an empty work-item — not writing the findings record." >&2; exit 1; }
   SPEC=$(python3 -B "$ROOT_DIR/lib/definition_doc.py" resolve-write \
     --doc spec --work-item "$WORK_ITEM" --root "$ROOT") \
     || { echo "the-architect: cannot resolve the work-item folder (see message above) — not writing the findings record." >&2; exit 1; }
   FINDINGS="$(dirname "$SPEC")/findings.md"
   ```

   **Both captures are guarded, and the empty-string check is not belt-and-braces.**
   `resolve-write` accepts an empty `--work-item`, exits 0, and returns the docs base with the
   work-item folder collapsed out — so an unguarded `mint` failure would land the owner's
   ratified record outside any work-item folder instead of stopping. Guard the mint, check it is
   non-empty, and only then resolve.

   `resolve-write` is used **only to learn where the work-item folder is** — it is the one
   resolver that is correct in both storage modes. **Take its directory; never write to the
   `spec.md` path it names** — on this exit no spec is written at all. The findings record is
   `findings.md` in that folder, and it is **not** a definition-doc: no frontmatter block, no
   gates.
2. **Write it in plain language:** what was asked, what was investigated, what was found, and
   **the outcome — that no spec is being written, and why**. State that outcome explicitly; a
   findings record that trails off without saying it is not an exit.
3. **Ask the owner to ratify the outcome, and record their answer in the file** — their words,
   with the date. **The ratification is the owner's, never yours**; an unratified findings
   record is a park, not an exit.
4. **Report the exit to the advisor:** the work-item, the path to the record, and the one-line
   outcome.

### Exit C — the park note

Take it when discovery stops without reaching either other exit — the session ends, the owner
goes quiet after consenting to spend, the work is displaced, or a gate has nothing to proceed
on.

**A park lands the full park note — what was elicited or found so far, explicitly marked unapproved — on the owner's reading surface at park time: in the advisor's delivery message when the owner is present, else as the opening item of the advisor's next delivery message; a durable copy lands as a comment on the parked item's issue or PR, and the durable copy is for the record — it is never required owner reading.**

- **A draft that already exists stays where step 6 put it.** It remains at the spec path
  `resolve-write --doc spec` reports for the work-item — **the mode-correct path, never a
  hardcoded repo path.** In-repo storage resolves it under the repository and global storage
  resolves it in the project's store; naming the resolver covers both modes in one sentence,
  and a hardcoded path silently means the wrong file in one of them. The draft keeps
  `status: draft` — a parked draft is never `approved` and its review gate is never flipped —
  and the park note **names that path and marks the draft unapproved in the same breath**. One
  durable artifact per home: the note points at the draft, it never carries a copy of it.
  Nothing may anchor to a parked draft.
- **"Explicitly marked unapproved" is load-bearing.** Elicited requirements in a park note are
  notes. Nothing downstream may anchor to them, and nothing in them is approved content.
- **Nothing elicited is lost.** Every answer the owner gave goes into the note, so the work
  survives the gap.
- **Report the park to the advisor** with everything else.

## Checklist

Create a TodoWrite item for each step and complete them in order. **These steps are the spec
path (Exit A).** When a discovery ends on **Exit B** or **Exit C** instead, the remaining steps
are not run — that exit's own artifact closes the work.

1. **Initial context gathering**
2. **The consent gate** → investigation spend starts only on the owner's consent
3. **Requirements dialogue** (one question at a time; EARS phrasing; run the coverage checklist)
4. **UI/UX** when relevant (hand the owner a Claude Design prompt)
5. **Confirm the framing → owner approves the *what*** ← HARD GATE
6. **Author the spec** via the `writing-specs` skill
7. **The weight call, then review at that weight** (the advisor's call; fix findings before the owner spends time)
8. **Owner review & final approval** ← terminal gate for Exit A; the approved spec is the ready artifact

## The steps

### 1. Initial context gathering

- **`CLAUDE.md` is mandatory context, not optional reading.** If it is **not
  already in your context, read it now** (plus any nested `CLAUDE.md` governing
  paths you'll touch) before gathering anything else — its rules are binding and
  override your defaults. Then explore the rest: `README`, recent commits, and any
  existing `docs/superheroes/` specs — understand what exists before asking.
- **You are the Discovery engine for this project.** Requirements work in a
  superheroes project routes here — do **not** hand it to a generic brainstorming skill.
  Borrow the *technique* (one question at a time, explore before deciding,
  present-and-approve), but the artifact you produce is the superheroes `spec` — or one of
  the two other exits' artifacts — and the phase ends at an exit, never with a plan document.
- **Scope check.** If the idea is really several independent pieces (e.g. "a
  platform with chat, billing, and analytics"), say so before refining details.
  Help the owner pick the **first** piece; each piece gets its own
  spec. Recursion is one level — don't decompose a
  decomposition.

### 2. The consent gate — investigation spend is the owner's to authorize

Reading what already exists (step 1) is not investigation. **Investigation** is spend on a
**genuine unknown that blocks requirements** — prior-art research, a `deep-research` run, a
feasibility read of an unfamiliar domain. It has one rule, and this is it:

- **Consent before spend, with the spend named.** Say in plain language what the investigation
  would settle and **what it costs in time and usage** — never a dollar figure (owners are
  typically on usage plans, not per-token billing). Then wait.
- **Silence is not consent. Spend never starts on silence.** While the owner is unavailable the
  item **waits or parks** (Exit C) — it never proceeds on an assumption that they would have
  said yes.
- **Consent names the spend it covers, and that bound stops the work.** Reaching the named bound
  **stops the investigation**; it reports what it found and **asks again** before any further
  spend. A bound that quietly stretches is the failure this rule exists to prevent.
- **This is the only mid-flight consent point.** Discovery asks the owner to authorize spend
  here and nowhere else. Every other owner interaction in this skill is elicitation or a gate,
  never a spend request.

**Investigation likely helps when** the work is novel, in an unfamiliar domain, medium-or-large,
the requirements are vague, or it is a user-facing "what do other products do here?" call. **A
confident owner is not an automatic skip** — confidence isn't correctness, so offer the check on
a consequential call and let them choose. **Skip for** small or mechanical, well-understood work.

Once consent is granted, use `deep-research` if available, else `WebSearch`/`WebFetch`; if
neither is available, say so and proceed. Report findings in **plain language** ("most apps in
this space do X; the trade-off is Y") — never raw dumps. **If the investigation resolves the
unknown and opens no new product surface, take Exit B** rather than carrying on to a spec
nobody needs.

### 3. Requirements dialogue (one question at a time)

Refine the idea through natural dialogue, capturing requirements in **EARS** form:

- **One question per message, in prose.** **No up-front ceremony choice** — you never ask the
  owner (and never decide in advance) how heavy this discovery will be, and you never select a
  lighter process before knowing what the work needs. The dialogue's shape comes from what the
  answers reveal, not from a mode picked at the start.
- **Probe every opinion-bearing dimension, and ask whether they care.** A dimension is
  opinion-bearing when a reasonable owner could hold a view on it that changes what gets built.
  Put each one in front of them and **ask whether they care** — "do you have a view on X, or
  should I choose?" A dimension they explicitly hand back to you is a **recorded disposition**,
  not a skipped question.
- **The spec's dispositions table is the stopping rule, not a question quota.** That table is
  the spec's `## Coverage` section: one row per probed area, each carrying its disposition.
  Discovery closes when **every dimension the table covers carries a disposition** — Specify,
  Defer-to-build, or N-A.
  **A small surface therefore closes having asked only the questions its table needed**, and
  that is the expected outcome for small work, never a shortcut you have to justify.
- **Frame every consequential choice as prose — never a pick-one widget.** A choice is
  *consequential* when getting it wrong would change the spec's scope, an owner-visible
  behavior, the `size`, or cost/risk the owner carries. **Present the options as prose in the
  conversation**, in this order:
  1. **The decision & why it matters** — one or two plain sentences: what is being decided, what
     it changes for the owner, and what is at stake if it goes the wrong way. No internal
     jargon; if a term is unavoidable, define it in the same breath.
  2. **The options** — 2–3 named options, each with a one-line plain-language *pro* and *con*
     (the real trade-off, not a restatement of the label).
  3. **Your recommendation** — name the option you would pick and why, in one line. No confident
     pick? Say so ("close call — your call") rather than feigning neutrality.

  **Never route a consequential choice through a pick-one widget** — not a single-selection
  control of any kind. A widget forces the owner into your labels, and the whole point is that
  they may not be in your labels. **Accept free-form answers and carry the dialogue forward.**
  A clarifying question, a mix of two options, a fourth option you did not list, or "why does
  this need deciding at all?" are all valid answers: answer the question, fold the mix in, or
  take the new option — and **never re-present the same list demanding a single selection**.
  **Re-forcing the choice after a clarifying answer is the failure this rule names.** A
  *trivial* confirmation (naming, a yes/no with one obvious default, a detail with no downside)
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
- **Run the coverage checklist** — one row per area in the Dispositions table
  (`## Coverage`). The first nine rows cover significant unhappy paths; the last
  six are the **initial** happy-path seed dimensions (grown by the learning loop
  below as discovery learns what was never asked). Probe each row; record a
  disposition (**Specify / Defer-to-build / N-A**) and a **`Show-it?`** call
  (**Yes / No**) alongside it — whether the owner should be **shown** this at
  handback rather than told. Risk-gate: go deeper only where a failure costs
  money, data, safety, trust, or legal standing. One representative case per area,
  not a matrix.

  | Coverage area | Ask the owner |
  | --- | --- |
  | **Empty & first-run** | What do they see the first time, or with nothing here yet? |
  | **Invalid & malformed input** | If they enter something wrong/blank, what happens and what message? |
  | **Boundaries & limits** | Any limits that matter, and behavior right at / just past them? |
  | **Errors & failures** | When something fails (not their fault), what do they see and do? |
  | **Access & permissions** | Who may, who may not, and what does the wrong person see? |
  | **Duplicates & double-actions** | What if they submit twice or double-click? |
  | **Conflicting / simultaneous use** | Two people change the same thing — last wins, lock, merge? |
  | **Misuse & abuse** | Could someone abuse this (money, private data) — what must we prevent? |
  | **Reach (i18n / a11y)** | Other languages/currencies/timezones? Keyboard + screen-reader usable? |
  | **Wording & tone** | What words should the product use when talking to them about this, and how should it sound? |
  | **Workflow shape** | What order should the steps happen in, and does anything have to come before something else? |
  | **Placement & prominence** | Where should this live in the product, and how much should it stand out? |
  | **Limits & defaults** | If they don't choose, what happens — and what's a sensible ceiling? |
  | **Tier & access boundaries** | Should this work differently depending on who they are or what they pay for? |
  | **Visibility & disclosure** | Who else can see this, and what should the product tell them about that? |

  Connectivity & timing failures (dropped network, timeouts, duplicate requests at
  the wire) are **defer-to-build**: capture only the owner-visible *promise* ("a
  dropped connection never loses their work").
- **Non-functional needs** are captured as **outcomes with a measurable bar** ("a
  page they wait on responds within 2 seconds", "only the owner can see their
  data"), never as mechanisms.

#### The elicitation test (FR-19)

**The admission rule.** A line earns its place in a spec by **the elicitation
test**: *the owner was asked, and cared.* That is the **only** admission rule. A
line does **not** earn its place because it seemed important, because it is true,
because a template has a slot for it, or because leaving it out felt incomplete —
**there is no author-side filter that admits a line the owner was never asked
about.**

**These six classes do not land in specs** — each fails the elicitation test:

1. **Mechanisms** — how something works. That is the build's, not the spec's.
2. **Limits the owner would not enforce** — a number nobody would defend if it were hit.
3. **Vacuous quality lines** — "it should be reliable", "the UI should be intuitive":
   nothing a build could be graded against.
4. **Design-handoff transcription** — re-describing the design output in prose instead
   of referencing it.
5. **Test obligations** — that something will be tested. Tests are the build's contract.
6. **Non-load-bearing mirror-facts** — repo facts the build does not rely on being true.

#### Failure semantics (FR-20)

When a row in `## Coverage` is violated, the consequence rides the **decision
axis** — the disposition determines what kind of failure it is:

- A violated **`Specify`** row is a **builder defect**. The owner decided; the build
  did something else.
- A missing **`Show-it`** presentation is a **handback omission** — the decision was
  honored, the delivery failed to show it. It is fixed at handback, not charged to
  the build as a defect.
- An owner's **negative reaction to a shown `Defer-to-build` choice** creates a **new
  ruling, never a defect**. The build was authorized to choose; the owner is now
  choosing differently, and that is a ruling that amends the spec. **You did not do
  anything wrong by choosing; they are deciding now.** Nobody is charged with a
  defect for a deferred choice the owner later dislikes.

#### The learning loop (FR-21)

Handback findings close the loop between one discovery and the next — and two
different failures are **not** graded the same way:

- **"Asked and deferred"** — the owner was asked, and handed the choice back. If they
  later want it different, that is a **cheap amendment**. No finding; nobody missed
  anything.
- **"Never asked"** — the dimension was never put in front of the owner at all. That is
  a **finding against discovery**, and it carries a **duty**: **add that dimension to
  the coverage checklist in this charter and to the template's Dispositions table**, so
  the next discovery asks it. That growth is why the six happy-path dimensions are
  described as the **initial** seed list everywhere they appear — the list is designed
  to get longer, and a surface that presents it as closed is wrong.

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
always have a plain-text description as the fallback; never rely on it.

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
the spec to the path `resolve-write --doc spec` reports for the work-item — the same
resolver Exit B's block calls, correct in both storage modes; never a hardcoded repo
path. Hand it the approved set:
**title, purpose, who-it's-for, the functional requirements (EARS + acceptance
criteria), the significant-unhappy-path requirements, non-functional requirements,
UI/UX outcome, definition of done, assumptions & dependencies, constraints,
out-of-scope, and `size`.** That skill owns the on-disk artifact; you own the
dialogue that feeds it. What it writes is a **draft** — `status: draft` until the owner approves it at step 8, and if
the discovery parks before then, the draft stays exactly where this step put it (Exit C).

### 7. The weight call, then review at that weight

**The weight call is the advisor's — always.** It is made **on the completed draft**, never
before: you cannot weigh a spec you have not written. **When discovery runs with no advisor in
the loop, the completed draft waits for the advisor's call** — you do not weigh your own draft,
and you do not proceed to review at a weight you picked. If that wait cannot be resolved, the
item **parks (Exit C)** with the draft left at the spec path `resolve-write --doc spec` reports,
`status: draft`,
and explicitly marked unapproved in the park note.

**A weight call names `light` or `full`, states its measurables (gradable-line count for a spec draft; child count and register-entry count for a package read), names a round ceiling when it governs a read loop, and may be overridden in either direction by one stated sentence; the numeric bars are guidelines, never gates.**

Grade **both** classification inputs on the draft, and state both:

- **Gradable requirement lines** — the requirement sentences a reviewer could grade a change
  against: every numbered functional requirement and every significant-unhappy-path requirement.
  Acceptance criteria, prose sections and the Coverage table are **not** gradable lines.
- **Interlocking sections** — sections that **cite or constrain one another** (one requirement's
  behavior is defined by another's, or a section names another as its bound). A draft whose
  sections stand alone has none.

**At or under 10 gradable requirement lines with no interlocking sections calls `light`; above
calls `full`.** **Both inputs must hold for `light`** — 6 gradable lines with two interlocking
sections is `full`.

| Weight | Review | Vet | Owner approval |
| --- | --- | --- | --- |
| `light` | **one independent review seat** over the draft — a single fresh-context reviewer, cross-vendor where one is configured; not `review-spec`'s panel | a **light vet**: the advisor reads the draft and that seat's findings, and rules in-channel | **in-channel** — ask in the conversation and record the answer when it comes |
| `full` | **`review-spec`'s panel** | the **full spec vet** | **scheduled owner review** — hand the spec over and agree a time; never press for an answer in the moment |

**Record the call:** name the gradable-line count, whether any sections interlock, and the
resulting weight. **An override is valid only when stated, and one stated sentence is enough** —
"calling this full despite 7 lines: the two limits sections define each other" — in either
direction.

**The 10-line bar is a guideline, never a gate.** Nothing in this skill, and no gate anywhere,
turns it into a hard block: a 40-line draft may be called `light` with one stated sentence, and
a 4-line draft may be called `full` the same way. If you find yourself saying "the number won't
let me", the number has been misread.

Address the review's findings **before** asking the owner to spend their time — the review
catches ambiguity, missing coverage and tech leakage the owner would otherwise have to. Fix what
it raises (or, where it is a judgment call, note it for the owner). **Never fabricate a review
result.**

**If `review-spec` is not available in this project**, that is not an exemption from review —
handle it by weight. On `light`, `review-spec` was never the reviewer: the **one independent
seat still runs**, because a fresh-context reviewer needs no skill to be installed. On `full`,
the panel cannot run, so either the advisor **calls it down to `light` with the one stated
sentence** an override needs and the single seat runs, or the draft **parks (Exit C)** marked
unapproved. **Self-review is never the substitute** — step 6's self-review is the author's own
pass and was never independent. Whichever way it goes, the owner is told, in plain language,
what did not run.

### 8. Owner review & final approval (terminal gate)

Ask the owner to review the written spec. **Tell them the truth about which review ran** —
never claim a review that didn't happen, and never offer them a spec that had none. The
message follows the weight called in step 7.

**Name the real path** — the one `resolve-write --doc spec` reported for this work-item, never a
hardcoded repo path. `<spec path>` below stands for it.

> *At `light` weight:* "Spec written to `<spec path>` and read by
> one independent reviewer. Please review it and tell me if you want any changes before it
> goes to the build."
>
> *At `full` weight:* "Spec written to `<spec path>` and through
> `review-spec`'s panel. Please review it and tell me if you want any changes before it
> goes to the build."
>
> *At `full` weight, overridden down because the panel could not run:* "Spec written to
> `<spec path>`. `review-spec`'s panel isn't available on this
> project, so this was called down to light weight and read by one independent reviewer
> instead. Please review it and tell me if you want any changes before it goes to the build."

**There is no fourth message.** `review-spec` being unavailable is not a reason to hand the
owner an unreviewed spec at either weight — step 7 rules that out, and a draft that can reach
neither review path **parks (Exit C)** rather than arriving here.

**How you ask depends on the weight called in step 7.** On `light`, ask **in-channel** — put it
in the conversation and record the answer when it comes. On `full`, agree a **scheduled owner
review**: hand the spec over, name when you will come back to it, and do not press for a verdict
in the moment. Weight changes how the approval is scheduled; it never changes who approves.

- **If the owner requests changes, apply them and re-review the revised draft at its effective
  weight before coming back to them.** On `light`, the one independent seat reads it again; on
  `full`, `review-spec`'s panel runs again; on a draft called down to `light` because the panel
  could not run, the one independent seat reads it again. **There is no path from "changes
  requested" to `set-gate … passed` without a re-review at the effective weight** — a revised
  draft is a draft, and step 7's rule that no draft reaches the owner unreviewed applies to it
  exactly as it applied the first time.
- **The owner's approval is the terminal gate** — review-crew advises, the owner
  decides. **Only once the owner explicitly approves**, record their decision so the
  work-item is ready to build:

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
  ROOT=$(git rev-parse --show-toplevel)
  WORK_ITEM="<work-item>"
  DOC_PATH=$(python3 -B "$ROOT_DIR/lib/definition_doc.py" path \
    --doc spec --work-item "$WORK_ITEM" --root "$ROOT")
  HASH=$(python3 -B "$ROOT_DIR/lib/definition_doc.py" content-hash --path "$DOC_PATH")
  python3 -B "$ROOT_DIR/lib/definition_doc.py" set-gate \
    --doc spec --work-item "$WORK_ITEM" --review passed --root "$ROOT" \
    --expected-hash "$HASH" --run-id "selfcert-$WORK_ITEM"
  ```

  This writes `gates.review: passed` (and derives `status: approved`) — the
  machine-readable signal that the spec is approved (and the only thing that flips the gate
  when `review-spec` isn't wired yet). Recording the **owner's** explicit decision is
  **not** self-approval — the HARD-GATE forbids *you* rubber-stamping your own
  un-reviewed work, not recording the owner's call. Run this **after** the owner says
  yes, never before.
- **Exit A is done — report and hand back.** With the spec approved, this path is complete: the
  owner-approved spec is the ready artifact. **Report the exit to the advisor** — the
  work-item, the spec's path, and the weight the review ran at — exactly as Exits B and C
  report theirs. Do **not** start a build yourself — hand back to the owner, who routes the
  approved work-item to a build session. The spec's approval gate is the authoritative signal.

## Rationalization table

| Excuse | Reality |
| --- | --- |
| "This is too simple to need a spec" | On the spec path a spec can be short; it cannot be skipped — discovery produces the *what*. "Simple" is never license to skip the thinking or fabricate requirements. If there is genuinely nothing to specify, that is **Exit B**, not a thin spec. |
| "I'll just use a generic brainstorming skill" | In a superheroes project, Discovery is this skill — and it closes at one of its three exits, never with a plan document or a hand-off to somewhere else. |
| "Let me note the tech approach" | The *how* is the build's. Keep the spec to the *what*. |
| "Happy path is enough" | The significant unhappy paths are the anti-slop core. Run the coverage checklist. |
| "I'll research to be thorough" | Research is consented — offer it, name the time/usage cost, let the owner choose. |
| "The owner's sure, skip research" | Confidence isn't correctness. Offer a quick prior-art check on consequential calls. |
| "review-spec passed, that's done" | review-crew advises; the **owner** has the final say (step 8). |
| "Owner approved the idea, start building" | The HARD GATE needs explicit approval of the *what*, then the written spec, before the build. |
| "Restate every requirement so they can approve" | Step 5 is a compact decision brief, not a spec replay. The requirement-by-requirement review is the spec (step 8) — don't double-review. |
| "They can infer the trade-offs from the options" | A consequential question carries its own why-it-matters, per-option pro/con, and a recommendation (step 3) — in plain language, before the ask. |
| "It's just a spike — I'll investigate and skip the gate" | There is no spike surface. "Spike" is the informal name of discovery's investigation phase; when it ends, an exit is still ahead. |
| "The owner ruled on this already, so I'll run discovery anyway to be safe" | A recorded dated ruling is already the *what* — it needs no discovery. Decline the work; what it routes to is the advisor's call, not yours. |
| "They haven't answered — I'll start the research and tell them after" | Spend never starts on silence. Wait, or park (Exit C). |
| "The investigation hit its bound but I'm nearly there" | The bound stops the work. Report and re-ask. A bound that stretches was never a bound. |
| "I'll ask them to approve the extra spend while I'm at it" | The consent gate is the **only** mid-flight consent point. Anything else you need from the owner is elicitation or a gate, not a spend request. |
| "The investigation found nothing — I'll write a thin spec so there's something to hand over" | That is a fabricated spec. Take **Exit B**: a findings record, with the owner's ratification recorded in it. |
| "The findings are obvious — I'll close it out myself" | The ratification is the owner's. An unratified findings record is a park, not an exit. |
| "The owner went quiet — I'll leave it and come back" | An abandoned discovery gets a park note (**Exit C**). Silence is not an exit, and the note is what keeps their answers from being lost or mistaken for approved content. |
| "A pick-one widget is faster than writing the options out" | Options are prose in the conversation. A widget forces the owner into your labels — and they may not be in your labels. |
| "They answered with a question instead of picking one — I'll re-ask the list" | That is re-forcing the choice. Answer the question and carry the dialogue forward. |
| "This looks small, I'll run the light version of discovery" | There is no up-front ceremony choice. Probe each opinion-bearing dimension and stop when the spec's dispositions table (`## Coverage`) is satisfied — a small surface closes early on its own. |
| "No advisor is around, so I'll call the weight myself" | The weight call is the advisor's. The completed draft waits for it; if the wait can't be resolved, the item parks (Exit C). |
| "Only 7 gradable lines, so it's light" | Both inputs are graded. Interlocking sections make it `full` whatever the count says. |
| "It's 12 lines, so the guideline blocks light" | The bar is a guideline, never a gate. Override in either direction with one stated sentence. |
| "They only asked for a small wording change — I'll just apply it and flip the gate" | A revised draft is a draft. Re-review at the effective weight before going back to the owner; there is no path from "changes requested" to `set-gate … passed` without one (step 8). |
| "We're parking — I'll paste the draft into the park note so nothing is lost" | The draft is already durable at the spec path `resolve-write --doc spec` reports. The note carries the **path** and the unapproved mark, never a second copy — one artifact per home (Exit C). |
