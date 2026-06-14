{{frontmatter}}
# {{Title}}

> Plain-language requirements for this work — the **what**, not the **how**.
> Owner co-authored. No technical implementation details (libraries, data models,
> APIs, frameworks) — those live in the `plan`. Depth target: the happy path
> **plus the significant unhappy paths** that matter, not an exhaustive enumeration.
>
> **Requirements are written in EARS** (Easy Approach to Requirements Syntax): one
> constrained-English sentence per requirement, each matching a pattern below. This
> keeps them plain enough to read, precise enough to verify, and locked to the *what*.
>
> | Pattern | Shape |
> | --- | --- |
> | Ubiquitous (always true) | *The system shall &lt;response&gt;.* |
> | Event-driven | *When &lt;trigger&gt;, the system shall &lt;response&gt;.* |
> | State-driven | *While &lt;state&gt;, the system shall &lt;response&gt;.* |
> | Optional feature | *Where &lt;feature is present&gt;, the system shall &lt;response&gt;.* |
> | Unwanted behavior | *If &lt;bad thing happens&gt;, then the system shall &lt;response&gt;.* |
>
> "The system" may be the product's real name. Every requirement names an
> **observable** result the owner could see. Each carries **≥1 acceptance
> criterion** (the verifiable face of the requirement).

## Purpose

{{Why this work exists, in the owner's words: the problem or opportunity, and the
value it delivers. One short paragraph.}}

## Who it's for

{{The people who use this — a lightweight persona or two (role + what they're
trying to get done). Anchors every requirement to a real user.}}

## Functional requirements

{{Numbered EARS requirements for the happy path. One requirement = one behavior
(no "and"/"or" chaining — split them). Affirmative phrasing. No vague words
(fast, easy, robust, user-friendly, handle, support, manage) — name the concrete
behavior. No tech. Each requirement carries ≥1 acceptance criterion: a
Given-When-Then scenario for a behavioral flow, or a rule bullet for a simple
constraint (limit, format).}}

**FR-1.** {{When &lt;trigger&gt;, the system shall &lt;observable response&gt;.}}
  - *Acceptance (Given-When-Then):* Given {{context}}, when {{action}}, then {{observable result}}.

**FR-2.** {{The system shall &lt;response&gt;.}}
  - *Acceptance (rule):* {{a single pass/fail rule — e.g. "a title of more than 100 characters is rejected"}}

## When things go wrong (significant unhappy paths)

{{The anti-slop core. Written as **If/Then EARS** requirements (each with an
acceptance criterion), driven by the coverage checklist below. Cover the cases
that genuinely matter for THIS work — tag each area **Specify / Defer-to-plan /
N-A** so a skipped area is a recorded decision, not an oversight. Risk-gate: probe
deeper only where a failure would cost money, data, safety, trust, or legal
standing. One representative example per category, not a matrix.}}

| Coverage area (owner-facing) | Prompt |
| --- | --- |
| Empty & first-run states | What do they see the very first time, or when there's nothing here yet? |
| Invalid & malformed input | If they enter something wrong or blank, what happens and what message do they see? |
| Boundaries & limits | Any limits that matter (biggest/smallest/longest), and what happens right at and just past them? |
| Errors & failures | When something fails that isn't their fault, what do they see and what can they do (retry, save progress)? |
| Access & permissions | Who's allowed, who isn't, and what does the wrong person see if they try? |
| Duplicates & double-actions | What if they submit twice, or double-click the button? |
| Conflicting / simultaneous use | *(multi-user only)* If two people change the same thing at once — last wins, locked, or merged? |
| Misuse & abuse | *(sensitive features only)* Could someone abuse this (money, private data, reputation) — what must we prevent? |
| Reach: language / region / accessibility | *(if in scope)* Other languages, currencies, or timezones? Keyboard-only and screen-reader usable (WCAG AA)? |

**UFR-1.** {{If &lt;bad thing&gt;, then the system shall &lt;observable response&gt;.}}
  - *Acceptance:* Given {{context}}, when {{the bad thing}}, then {{what the user sees / can do}}.

> **Defer-to-plan promise:** for connectivity & timing failures (dropped network,
> timeouts, duplicate requests at the wire), state only the **owner-visible
> promise** here (e.g. "a dropped connection never loses their work or double-charges
> them"); the mechanism (retries, idempotency, rollback, rate-limits) belongs in the `plan`.

## Non-functional requirements

{{Speed, reliability, privacy, security-as-outcome, accessibility — each stated as
an **outcome with a measurable bar** (a fit-criterion), never a mechanism. Omit the
section if there are none worth stating.}}

- **Performance:** {{e.g. "a page the user waits on responds within 2 seconds for 95% of visits"}}
- **Security (outcome):** {{e.g. "a signed-out person can never see another customer's data"}}
- **Privacy:** {{what personal data is collected, who can see it, how long it's kept}}
- **Reliability / accessibility / …:** {{as applicable, each with a concrete bar}}

## UI / UX

{{For user-facing work, the design is created in **Claude Design**: Discovery hands
the owner a design prompt built from these requirements, the owner creates/iterates
the design, and its **handoff output is referenced here** — not re-described from
memory. Link or embed the Claude Design handoff (component structure, key screens,
states, tone). Omit this section entirely if the work is not user-facing.}}

## Definition of done / success

{{How the owner knows the *whole thing* worked, end-to-end — beyond any single
requirement (e.g. "an owner can publish a post from scratch without help"). This is
the top-level acceptance gate.}}

## Assumptions & dependencies

{{What this work takes as given or relies on from outside: accounts, third-party
services, data the owner provides, other work that must exist first. Surfaces
hidden blockers before the build hits them.}}

## Constraints

{{Non-negotiable boundaries stated as outcomes — must work on mobile, a budget, a
regulatory rule, a platform requirement. Distinct from non-functional requirements
and from out-of-scope.}}

## Out of scope

{{What this work explicitly does NOT include — the boundaries that keep it a single,
shippable piece.}}

## Open questions

{{Anything still undecided. This section is empty before the owner approves the
spec — resolve or defer each item first.}}

## Glossary

{{Domain terms with one agreed meaning each, so the owner and the agents speak the
same language. Omit if there are no terms worth pinning.}}
