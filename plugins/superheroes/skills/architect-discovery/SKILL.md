---
name: discovery
description: Use at the START of any new piece of work in a superheroes project — when a fuzzy idea needs to become an owner-approved requirements spec. It OWNS the requirements front-half, the *what* in plain language. Elicits requirements (incl. significant unhappy paths) with the owner into the `spec` definition-doc. Not the technical *how* (that is the build).
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

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

**Owner rulings you receive are recorded in the project's Canon** as `${CLAUDE_PLUGIN_ROOT}/rubric/canon-contract.md` says.

**Every call you meet is sorted by the owner-vs-craft line** in `${CLAUDE_PLUGIN_ROOT}/rubric/owner-vs-craft-line.md`.

<HARD-GATE>
**On the spec path (Exit A):** do NOT author the spec, write any code, create a
work-item folder or any other artifact beyond Canon's own entries, or hand off until you
have presented the framing (the **what**) and the
owner has explicitly approved it. And do NOT consider that path finished until the
owner gives their final approval of the written spec (step 8) — review-crew advises,
the owner decides. A spec can be short; on this path it cannot be skipped, and its
gates cannot be self-approved — you may *record the owner's* explicit approval
(step 8), but never approve on your own behalf.

**The two other exits are not loopholes in that gate — they are the other two ways a
discovery legitimately ends** (see **The three exits**). Each closes by writing its own
durable artifact, which is why **Exit B mints the work-item and places its record** and
why **Exit C hands back with no approved spec**. Where a draft was already written before
the park — a draft whose checks could not run in step 7 is the usual case — **the draft stays on disk at the spec
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
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
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

   A discovery that reached step 1's mint already holds its slug. It sets `WORK_ITEM` to that
   slug instead of running the mint, and everything after the mint runs as written.

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
- **A park before the framing leaves the committed Canon entries as they are.** The park note
  names the slug minted in step 1, when one was minted.
- **Report the park to the advisor** with everything else.

## Checklist

Create a TodoWrite item for each step and complete them in order. **These steps are the spec
path (Exit A).** When a discovery ends on **Exit B** or **Exit C** instead, the remaining steps
are not run — that exit's own artifact closes the work.

1. **Ground yourself before the first question**
2. **The consent gate** → investigation spend starts only on the owner's consent
3. **Requirements dialogue** (owner calls only, one at a time; EARS phrasing; run the coverage checklist)
4. **Confirm the framing → owner approves the *what*** ← HARD GATE
5. **Draw it before writing it** → journeys, then choices, then the build board for the owner's approval (or skip: small with nothing to draw)
6. **Author the spec** via the `writing-specs` skill, once the build board is approved, every statement tagged with its source
7. **Run the three spec checks** (fix craft findings before the owner spends time), then the writing pass and its meaning check
8. **Remainder sheets, ready for vet, the advisor's vet, then the final sheet & the owner's approval** ← terminal gate for Exit A; the approved spec is the ready artifact

## The steps

### 1. Ground yourself before the first question

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
- **Ground yourself in four sources, all before the first question.**
  1. **Who the product is for.** Read configuration item 14 with
     `python3 -B "${CLAUDE_PLUGIN_ROOT}/lib/project_config.py" get --item whoItsFor --cwd .`.
     The answer is the `effective` field of its JSON output.
  2. **Canon.** Read it as
     [Canon's contract](${CLAUDE_PLUGIN_ROOT}/rubric/canon-contract.md#reading-canon) says. Its
     standing rulings and ceded calls bind this discovery. When the lookup refuses or the default
     branch cannot be read, the contract's own stop rule applies. When there is no Canon file yet,
     the contract covers that case.
  3. **Sibling specs and their boards.** Read the other work-item folders where the project keeps
     its definition-docs: their specs, and any board kept with them.
  4. **The product as built.** Read the `README`, the recent commits, and the code or screens the
     idea touches.
- **When item 14 is empty, recommend its setup before anything else.** Treat item 14 as empty when
  `effective` is null, empty, or only whitespace, when `malformed` is true, and when the command
  fails or refuses. Then, before the first question, make this the first thing you say to the
  owner: you strongly recommend that they set up who the product is for and what it's for with the
  advisor before going on. Give the reason in one sentence. Discovery grounds every question in it,
  and without it, discovery guesses who the product serves. Ask whether to stop for that or go on.
  For example: "Before I ask anything, I strongly recommend settling who this product is for and
  what it's for with the advisor. I ground every question in that, and without it I'd be guessing
  who it serves. Want to stop and do that first, or should I go on?" When the owner chooses to go
  on, go on. Their choice is never blocked, and you do not repeat the recommendation.
- **Light scope check.** If the idea is plainly several independent pieces (e.g. "a
  platform with chat, billing, and analytics"), say so before refining details.
  This check splits off only the obvious bundles. Help the owner pick the **first** piece.
  Each piece gets its own spec. The full split check runs later, when the spec is written.
  Recursion is one level. Don't decompose a decomposition.
- **Pick the title and mint the slug before the first requirements question.** Choose a concise, accurate
  title for the piece. It is the sole input to the *frozen* work-item slug, so choose it
  deliberately: it cannot change later. Never ask the owner to pick or confirm it. Mint with the
  guarded form, and stop on a non-zero exit or an empty result:

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
  WORK_ITEM=$(python3 -B "$ROOT_DIR/lib/definition_doc.py" mint --title "<title>") \
    || { echo "the-architect: cannot mint the work-item (see message above) — not starting the dialogue." >&2; exit 1; }
  [ -n "$WORK_ITEM" ] \
    || { echo "the-architect: mint returned an empty work-item — not starting the dialogue." >&2; exit 1; }
  ```

  Minting writes nothing. The slug is frozen from here on, and the Canon entry of every ruling
  for this piece names it. When the scope check had the owner pick which piece comes first, record
  that pick in Canon right after the mint, naming the slug.

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

**Offer investigation only when an unknown blocks the requirements.** You cannot write a
requirement without settling it. Spend on it only after the owner consents to a named cost. These
are signs that an unknown may be blocking: the work is novel, it is in an unfamiliar domain, the
requirements are vague, or it is a user-facing "what do other products do here?" call. **A
confident owner is not an automatic skip when an unknown blocks** — confidence isn't correctness,
so offer the check and let them choose. **Skip it when nothing blocks the requirements.**

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
- **Ask only owner calls.** Before you ask anything, sort the call as
  [How a call is sorted](${CLAUDE_PLUGIN_ROOT}/rubric/owner-vs-craft-line.md#how-a-call-is-sorted)
  says. Only a call sorted as the owner's becomes a question.
- **Decide craft calls yourself, and record each one for the owner's veto.** Do not ask. Keep a
  running list. Each entry holds the call, what you chose, and one line of why. Show the list at
  the framing (step 4) and carry it into the spec.
- **Probe every opinion-bearing dimension in an owner category, and ask whether they care.** A
  dimension is opinion-bearing when a reasonable owner could hold a view on it that changes what
  gets built. Put each owner-category one in front of them and **ask whether they care** — "do
  you have a view on X, or should I choose?" A dimension they explicitly hand back to you is a
  **recorded disposition**, not a skipped question.
- **The spec's dispositions table is the stopping rule, not a question quota.** That table is
  the spec's `## Coverage` section: one row per probed area, each carrying its disposition.
  Discovery closes when **every dimension the table covers carries a disposition** — Specify,
  Defer-to-build, or N-A.
  **A small surface therefore closes having asked only the questions its table needed**, and
  that is the expected outcome for small work, never a shortcut you have to justify.
- **Frame every consequential choice as prose — never a pick-one widget.** A choice is
  *consequential* when getting it wrong would change the spec's scope, an owner-visible
  behavior, the `size`, or cost/risk the owner carries. A question is one of two kinds.

  **A real choice** carries what is being decided and why it matters, the options each with its
  plain consequences, and your recommendation. **Present the options as prose in the
  conversation**, in this order:
  1. **The decision & why it matters** — one or two plain sentences: what is being decided, what
     it changes for the owner, and what is at stake if it goes the wrong way. No internal
     jargon; if a term is unavoidable, define it in the same breath.
  2. **The options** — 2–3 named options, each with its plain consequences: a one-line *pro*
     and *con* (the real trade-off, not a restatement of the label).
  3. **Your recommendation** — name the option you would pick and why, in one line. No confident
     pick? Say so ("close call — your call") rather than feigning neutrality.

  **An open question** (for example "who is this for?") is asked as it is, with no options
  invented.

  **Never route a consequential choice through a pick-one widget** — not a single-selection
  control of any kind. A widget forces the owner into your labels, and the whole point is that
  they may not be in your labels. **Accept free-form answers and carry the dialogue forward.**
  A clarifying question, a mix of two options, a fourth option you did not list, or "why does
  this need deciding at all?" are all valid answers: answer the question, fold the mix in, or
  take the new option — and **never re-present the same list demanding a single selection**.
  **Re-forcing the choice after a clarifying answer is the failure this rule names.** A
  *trivial* confirmation (naming, a yes/no with one obvious default, a detail with no downside)
  needs none of this; ask it in a line.
- **A conflict with an earlier Canon ruling is its own decision.** When an answer would conflict
  with an earlier Canon ruling, pick neither and do not fold it in. Put the conflict to the owner
  as its own question, with both rulings side by side: the earlier entry's id, date, and words,
  and the new answer. Say what each would mean for this piece, and give your recommendation. The
  owner's answer is recorded as
  [Canon's contract](${CLAUDE_PLUGIN_ROOT}/rubric/canon-contract.md#append-only-and-supersession)
  says.
- **Record every ruling in Canon.** Every ruling you receive is recorded in Canon as
  [Canon's contract](${CLAUDE_PLUGIN_ROOT}/rubric/canon-contract.md#writing-a-ruling) says.
- **Capture who the piece is for as user stories.** Write one or more in the form "As a …, I
  want …, so I can …" that evoke the core need without listing every detail. Edge cases are
  requirements (the unhappy paths), never user stories.
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
  not a matrix. A row whose call sorts as craft gets its disposition from you, recorded for the
  owner's veto, with no question.

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

#### The elicitation test

**The admission rule.** A line earns its place in a spec by **the elicitation
test**: *the owner was asked, and cared.* That is the **only** admission rule. A
line does **not** earn its place because it seemed important, because it is true,
because a template has a slot for it, or because leaving it out felt incomplete —
**there is no author-side filter that admits a line the owner was never asked
about.**

A craft call recorded for the owner's veto and shown at the framing passes the test, because the
owner saw it and could veto it.

**These six classes do not land in specs** — each fails the elicitation test:

1. **Mechanisms** — how something works. That is the build's, not the spec's.
2. **Limits the owner would not enforce** — a number nobody would defend if it were hit.
3. **Vacuous quality lines** — "it should be reliable", "the UI should be intuitive":
   nothing a build could be graded against.
4. **Board transcription** — re-describing the approved board in prose instead of
   pointing at it.
5. **Test obligations** — that something will be tested. Tests are the build's contract.
6. **Non-load-bearing mirror-facts** — repo facts the build does not rely on being true.

#### Failure semantics

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

#### The learning loop

Handback findings close the loop between one discovery and the next — and two
different failures are **not** graded the same way:

- **"Asked and deferred"** — the owner was asked, and handed the choice back. If they
  later want it different, that is a **cheap amendment**. No finding; nobody missed
  anything.
- **"Never asked"** — the dimension was never put in front of the owner at all (a craft call
  shown for the owner's veto was put in front of them, so it is not "never asked"). That is
  a **finding against discovery**, and it carries a **duty**: **add that dimension to
  the coverage checklist in this charter and to the template's Dispositions table**, so
  the next discovery asks it. That growth is why the six happy-path dimensions are
  described as the **initial** seed list everywhere they appear — the list is designed
  to get longer, and a surface that presents it as closed is wrong.

### 4. Confirm the framing → owner approves the *what* (HARD GATE)

Nothing is drawn before this gate: no design prompt, sketch, or board comes before the owner
approves the framing.

Present a compact **decision brief** the owner can digest in under a minute — not a replay
of every requirement (the requirements live in the spec, and what still needs the owner comes
back as cards on the sheets in step 8):
- **One line each:** what this is and the `size` you're assigning.
- **Who it's for** — the user stories you captured in step 3.
- **Load-bearing decisions** — the handful of calls that shape the work: the
  resolutions you reached on the consequential questions. One line each.
- **Craft calls made for your veto** — each call you decided yourself, from the running list in
  step 3. One line each: the call, what you chose, and why.
- **Still open** — anything unresolved or assumed that the owner should rule on now.

Ask: *"Does this framing look right? Anything to change before I write it up?"* **Do not
proceed past this gate until the owner approves the framing.** Revise and re-present as
needed. After this gate the owner sees only what still needs them, as cards on the sheets in
step 8, so they never review the same thing twice. Then continue to step 5, which either draws
the boards or records the skip.

Decide one thing here **yourself** — never make the owner pick it:
- **`size`** (`small | medium | large`) — infer it from the scope of the approved
  requirements. The skill decides; the owner never picks. It's frozen into the spec (§6.4).

### 5. Draw it before writing it

This step runs only after the owner approves the framing in step 4. The theme for every board's
frame is `${CLAUDE_PLUGIN_ROOT}/theme/comic-panel.css`.

Read `${CLAUDE_PLUGIN_ROOT}/skills/architect-discovery/reference/boards.md` when you draw, publish, save or redraw a board.

Draw three boards in order. The owner comments and rules on each before the next.

1. **Journeys or flows.** How a person moves through the work.
2. **The open choices, side by side.** Each option is drawn, so the owner compares by looking.
3. **The build board.** The settled design, for the owner's approval.

Any visual that communicates counts: screens, storyboards, flow charts, diagrams.

The build board holds three things. It holds only the settled design, with no open alternative. It
uses the product's real wording, never placeholder copy. Everything that can reasonably be drawn is
drawn, not described in prose.

A board is never less detailed than the chat. Anything the chat settled appears on the board.

**The owner approves the build board.** Then save it with the spec, in the work-item's `board/`
folder, as the reference says. Do not author the spec before that approval.

**Skip the board only when the work is small and has nothing to draw.** Say so at the framing, and
write the spec from the framing and the rulings. A small screen or a small flow still gets a board.

**Where the spec and the approved board disagree, the board wins.** Correct the spec in the same
pass, and run the checks again on the changed parts.

When a later ruling changes something the approved board shows, redraw that part, republish it to
the same link, and record the redraw in `board/redraws.md` marked `sent: no`. The owner's next sheet
shows every entry still marked `sent: no`.

### 6. Author the spec via `writing-specs`

Write the spec only once the owner has approved the build board, or once the skip is recorded at
the framing. Write it from the approved board and the owner's rulings.

Invoke the **`writing-specs`** skill
to emit the §3.1 frontmatter, fill the body template, and write
the spec to the path `resolve-write --doc spec` reports for the work-item — the same
resolver Exit B's block calls, correct in both storage modes; never a hardcoded repo
path. Hand it the slug minted in step 1, which it reuses and never mints again, along with
the approved set:
**title, purpose, who-it's-for, the functional requirements (EARS + acceptance
criteria), the significant-unhappy-path requirements, non-functional requirements,
the approved build board's saved path (or the recorded skip), the owner's rulings for this piece, definition of done, assumptions & dependencies, constraints,
out-of-scope, the craft calls made for the owner's veto, and `size`.** That skill owns the on-disk artifact; you own the
dialogue that feeds it. What it writes is a **draft** — `status: draft` until the owner approves it at step 8, and if
the discovery parks before then, the draft stays exactly where this step put it (Exit C).

**Every statement ends with its source tag**, plain text at the end of the statement, as
`writing-specs` says. A tag never cites transcript line numbers.

**One spec covers one piece the owner could approve and ship on its own.** When writing turns up a
second such piece, stop and propose a split to the owner: what each piece holds, and which one to
write first. The owner rules, and each piece gets its own spec. When the spec passes about 300 to
400 lines, raise splitting with the owner. Length alone never stops the work: when the owner keeps
one spec, write on.

### 7. Run the three spec checks

Every spec draft gets the three spec checks. Run them exactly as
`skills/architect-discovery/reference/spec-checks.md` says. This charter does not restate its
rules.

Nothing sizes the review. No one, the advisor included, picks a lighter or a heavier review for a
spec. Every spec gets the same three checks.

Fix the craft pile before the owner sees the spec. The owner's queue goes to the owner in step 8.
**Never fabricate a review result.**

**When the seat verb reports that no reviewer can run, the draft parks (Exit C).** It stays at the
spec path `resolve-write --doc spec` reports, `status: draft`, and the park note marks it
unapproved. The owner is told, in plain language, that no review ran. **Self-review is never the
substitute** — step 6's self-review is the author's own pass and was never independent.

**Then run the writing pass.** When the checks come back clean, or after round 4, and before the
owner is asked, run one writing pass over the spec to `${CLAUDE_PLUGIN_ROOT}/rubric/prose-standard.md`.
The pass changes wording only. It never adds, drops or moves a requirement, and every statement
keeps its source tag. Keep a copy of the spec as it stood before the pass.

**Then check that no meaning shifted.** When the pass changed nothing, no check runs, and the record
says so. Otherwise dispatch the meaning check to the spec-reviewer seat the three checks use, in its
own run directory, the way `spec-checks.md` dispatches a check. Count its result only when it is
real, by that doc's rule. Its prompt carries the spec before the pass and the spec after it, each
labelled, the diff between them, and this lens, copied verbatim:

```text
You are checking that a wording pass changed no meaning in a requirements spec. Two versions of the
spec follow, labelled before and after, with the diff between them. For each statement the diff
changes, report one finding. Use taxonomy meaning:kept, severity Nit, when the statement still says
the same thing, with the same scope and the same source tag. Use taxonomy meaning:shifted, severity
Important, saying what moved, when its meaning, its scope or its source tag changed. Report nothing
about wording quality. file is the spec path and line is the line in the after version. Return
{"findings": [...], "investigated": [...]}, never a bare list.
```

When the meaning check reports any shift, you may redo the pass once, leaving each shifted statement
as it stood before the pass, and run the meaning check again on the whole result. A second shift,
or a meaning check with no real result after one re-dispatch, discards the whole pass: the spec as
it stood before the pass stands. A real result still has to cover every changed statement: before
keeping the pass, reconcile the findings against the statements the diff changes. A changed
statement with no finding, a statement with two findings, or a finding that matches no changed
statement counts as no real result and takes the same path: one re-dispatch, then discard. No text
reaches the owner that the meaning check did not clear.

Record the pass in `checks-record.md`, under a "Writing pass" section: what the pass changed, in a
sentence; each meaning check's run directory, result and findings; and whether the pass was kept or
discarded.

### 8. Owner review & final approval (terminal gate)

The owner never reads the spec end to end. Every call that needs them arrives as a card on a sheet.
**Read `${CLAUDE_PLUGIN_ROOT}/skills/architect-discovery/reference/sheets.md` when you build, send, read or take over a sheet.**

**Tell them the truth about which review ran** — never claim a review that didn't happen, and never
offer them a spec that had none.

1. **Remainder sheets first.** After step 7, send the owner
   [remainder sheets](${CLAUDE_PLUGIN_ROOT}/rubric/glossary.md#remainder-sheet), built from
   `checks-record.md` as `sheets.md` says. They hold only what no board, ruling or earlier answer
   covers, plus findings the review didn't settle and declines the reviewer still contests. A
   statement with no source that decides product behaviour goes on the next remainder sheet with a
   recommendation, never kept or cut by discovery. Record each ruling in Canon and apply the answers.
   Run the checks again on the changed parts as `spec-checks.md` says in its After rulings section,
   then send the next remainder sheet. Repeat until nothing is left. When nothing is left after step
   7, send no remainder sheet.
2. **Then ask whether the spec is
   [ready for vet](${CLAUDE_PLUGIN_ROOT}/rubric/glossary.md#ready-for-vet).** It is its own word,
   separate from approval. Ask it only once no remainder item is left. Never take a remainder
   sheet's answers, or silence, as that word.
3. **On the word, hand the spec to the advisor's vet.** Open the spec PR: the spec,
   `checks-record.md`, the saved board and the `sheets/` folder on a branch. Where the project keeps
   its specs out of the repo, or in the repo but gitignored, hand over the stored spec instead. It
   stands in for the PR, with the same vet, approval and merge-word steps. The project's
   definition-doc policy (`definition_doc.py` resolves it) says which applies, and `sheets.md`
   carries the how. The advisor files issues at the merge word.
4. **Wait for the vet record.** The advisor's vet record is the notice that the vet is done; how to
   pick the record and tell a stale one from a current one is in
   `skills/showrunner/reference/spec-vet.md` § How discovery learns the vet is done — read it there,
   and act on a record only as it says. Ask the owner only after a current record reads `clean`.
   Fix every craft finding the vet raises, run the checks again on the changed parts, and hand the
   spec back for the next vet. When those checks put anything new in the owner's queue, send a
   remainder sheet for it and settle it as in Building a remainder sheet before handing the spec
   back; a clean vet does not clear the checks' queue. Owner calls in a record go to the final
   sheet. When discovery runs
   with no advisor reachable, the draft waits for the vet; if that cannot be resolved, the discovery
   parks (Exit C) with the draft marked unapproved.
5. **The final sheet.** After a current clean record, send the final sheet as `sheets.md` says: the
   vet's owner calls, the declined findings folded away, the plain disclosure when the record says
   the reviewer was from the author's own family, the line about the writing pass, and the approval
   card. When `checks-record.md` shows a check that did not run, say so on the sheet: name each
   check that did not run and why in plain words. Ask for approval one way, for every spec. Name
   when you will come back to the sheet, and do not press for a verdict in the moment.

**The owner approves only when all three hold.** The verdict saved for the published revision of the
final sheet reads Approve, the owner says in the chat that the sheet is done, and no other answer on
that sheet changes the spec. A saved Approve alone, a Not yet, a cleared verdict, or no verdict is
not approval: ask. `theme/review-template.md` says how the verdict is read.

- **If the owner requests changes, record the gate as `changes-requested` first.** An answer on the
  final sheet that changes the spec holds approval the same way. Then apply the changes, run the
  checks again on the changed parts as `spec-checks.md` says in its After rulings section, and hand
  the spec back to the advisor's vet. Only then go back to the owner, with a new final sheet. It is
  a republish, so it starts unsigned, and its new last card asks for approval. Record it the same
  way as the approval block below records `passed`:

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
  ROOT=$(git rev-parse --show-toplevel)
  WORK_ITEM="<work-item>"
  DOC_PATH=$(python3 -B "$ROOT_DIR/lib/definition_doc.py" path \
    --doc spec --work-item "$WORK_ITEM" --root "$ROOT")
  HASH=$(python3 -B "$ROOT_DIR/lib/definition_doc.py" content-hash --path "$DOC_PATH")
  python3 -B "$ROOT_DIR/lib/definition_doc.py" set-gate \
    --doc spec --work-item "$WORK_ITEM" --review changes-requested --root "$ROOT" \
    --expected-hash "$HASH" --run-id "owner-changes-$WORK_ITEM"
  ```

  **There is no path from `changes-requested` to `passed` without that re-run.** A revised draft
  is a draft.
- **The owner's approval is the terminal gate** — the checks advise, the owner
  decides. It runs only after the three conditions above hold.
  **Only once the owner explicitly approves**, record their decision so the work-item is ready to
  build:

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
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
  machine-readable signal that the spec is approved. The owner's approval is the only thing that
  writes `passed`. The gate's rules, its three states and the reset of a stale approval, are in
  `skills/architect-discovery/reference/spec-checks.md` under The review gate. Recording the
  **owner's** explicit decision is **not** self-approval — the HARD-GATE forbids *you*
  rubber-stamping your own un-reviewed work, not recording the owner's call. Run this **after** the
  owner says yes, never before.
- **Exit A is done — report and hand back.** With the spec approved, this path is complete: the
  owner-approved spec is the ready artifact. **Report the exit to the advisor** — the
  work-item, the spec's path, the path of the sheet folder, and the path of its `checks-record.md` —
  exactly as Exits B and C report theirs. A ruling that changes an approved board but reaches the
  advisor after this discovery session has ended is appended by the advisor to the piece's
  `redraws.md` (in the work item's `board` folder), in the format
  `skills/architect-discovery/reference/boards.md` § Skipping the board, the board winning, and
  redraws gives, marked `sent: no`. The next discovery session on the piece redraws from it before
  anything else. Do **not** start a build yourself — hand back to the owner, who routes the
  approved work-item to a build session. The spec's approval gate is the authoritative signal.
  **Breaking the spec into issues, filing those issues and wiring the project board are the
  advisor's, after approval.** Discovery does none of them.

## Rationalization table

| Excuse | Reality |
| --- | --- |
| "This is too simple to need a spec" | On the spec path a spec can be short; it cannot be skipped — discovery produces the *what*. "Simple" is never license to skip the thinking or fabricate requirements. If there is genuinely nothing to specify, that is **Exit B**, not a thin spec. |
| "I'll just use a generic brainstorming skill" | In a superheroes project, Discovery is this skill — and it closes at one of its three exits, never with a plan document or a hand-off to somewhere else. |
| "Let me note the tech approach" | The *how* is the build's. Keep the spec to the *what*. |
| "Happy path is enough" | The significant unhappy paths are the anti-slop core. Run the coverage checklist. |
| "I'll research to be thorough" | Research is consented — offer it, name the time/usage cost, let the owner choose. |
| "The owner's sure, skip research" | Confidence isn't correctness. Offer a quick prior-art check on an unknown that blocks the requirements. |
| "The checks came back clean, that's done" | The checks advise; the **owner** has the final say (step 8). |
| "Owner approved the idea, start building" | The HARD GATE needs explicit approval of the *what*, then the written spec, before the build. |
| "Restate every requirement so they can approve" | Step 4 is a compact decision brief, not a spec replay. What the owner still has to rule on arrives later as cards on a sheet (step 8) — don't double-review. |
| "They can infer the trade-offs from the options" | A real choice carries its own why-it-matters, per-option consequences, and a recommendation (step 3) — in plain language, before the ask. |
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
| "It's small, I'll skip the board" | Only work that is small **and** has nothing to draw skips the board. A small screen or a small flow still gets one (step 5). |
| "The spec says it differently from the board — I'll keep the spec" | The board wins. Correct the spec and run the checks again on the changed parts (step 5). |
| "I'll describe the screen in chat; the board can be lighter" | A board is never less detailed than the chat. Anything the chat settled appears on the board (step 5). |
| "This looks small, I'll run the light version of discovery" | There is no up-front ceremony choice. Probe each opinion-bearing dimension and stop when the spec's dispositions table (`## Coverage`) is satisfied — a small surface closes early on its own. |
| "They only asked for a small wording change — I'll just apply it and flip the gate" | A revised draft is a draft. Record `changes-requested`, run the checks again on the changed parts, hand the spec back for the vet, then send a new final sheet. There is no path from `changes-requested` to `set-gate … passed` without that (step 8). |
| "We're parking — I'll paste the draft into the park note so nothing is lost" | The draft is already durable at the spec path `resolve-write --doc spec` reports. The note carries the **path** and the unapproved mark, never a second copy — one artifact per home (Exit C). |
| "The spec is long — I'll stop writing until it's split" | Length alone never stops the work. Past about 300 to 400 lines, raise splitting with the owner; when they keep one spec, write on (step 6). |
| "The writing pass only touched wording, so the meaning can't have moved" | Every pass that changed text gets the meaning check before the owner sees it. A shift the check does not clear discards the pass (step 7). |
| "The spec is approved — I'll break it into issues and file them" | Breaking a spec into issues, filing them and wiring the board are the advisor's, after approval (step 8). |
| "They answered the remainder sheet, so the spec is ready for vet" | Ready for vet is its own word. Ask it once no remainder item is left. Answers and silence never stand in for it (step 8). |
| "The final sheet shows Approve, so I'll record the approval" | A saved Approve alone is not approval. It takes the verdict for the published revision, the owner's word in the chat that the sheet is done, and no other answer that changes the spec (step 8). |
| "This statement has no source, but it reads fine — I'll keep it" | A statement with no source that decides product behaviour goes on a remainder sheet with a recommendation. Discovery never keeps or cuts it (step 8). |
