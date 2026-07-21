{{frontmatter}}
# {{Title}}

<!-- AUTHOR GUIDANCE — for whoever fills this template; DELETE this whole comment
     before the spec is delivered to the owner. It must not appear in the final spec.

  Plain-language requirements for this work — the WHAT, not the HOW. Owner co-authored.
  No technical implementation details (libraries, data models, APIs, frameworks) — those
  stay with the build. Depth target: the happy path PLUS the significant unhappy paths that
  matter, not an exhaustive enumeration.

  Functional requirements are written in EARS (Easy Approach to Requirements Syntax): one
  constrained-English sentence per requirement, each matching a pattern:
    - Ubiquitous (always true):  The system shall <response>.
    - Event-driven:              When <trigger>, the system shall <response>.
    - State-driven:              While <state>, the system shall <response>.
    - Optional feature:          Where <feature is present>, the system shall <response>.
    - Unwanted behavior:         If <bad thing happens>, then the system shall <response>.
  "The system" may be the product's real name. Every requirement names an OBSERVABLE
  result the owner could see, and carries >=1 acceptance criterion (the verifiable face).
-->

<!-- AUTHOR GUIDANCE (provenance / citations) — DELETE this whole comment before delivering.

  A load-bearing MIRROR-FACT — a spec sentence asserting something about the EXISTING repo
  that the repo could contradict ("reuses/extends the existing X", "the current limit is N",
  "today the system does Y") — carries an inline CITATION naming its repo source. A
  DEFINITION (a NEW behavior/requirement this spec itself defines — the owner's *what*)
  carries NO citation: it is the source of truth, it mirrors nothing.

  The test: "Could today's repo contradict this sentence?" YES → mirror-fact → cite.
  NO (a new thing the spec defines) → definition → no cite.

  NOISE BUDGET: only LOAD-BEARING mirror-facts (ones the build relies on being true) get
  citations; incidental mentions don't. Citations stay rare — a spec dense with them is
  usually leaking the build's *how* (itself a finding). No cite-everything.

  Grammar (illustration only — the ONE authoritative machine home of this grammar is
  plugins/superheroes/lib/citation_validator.py's CITATION_RE):
    [cite: <repo-relative-path>]
    [cite: <repo-relative-path> § <anchor>]    (anchor = a literal substring findable in the file)
  Canonical example: [cite: plugins/superheroes/lib/definition_doc.py § mint]

  A `[cite: …]` provenance marker is a sanctioned spec construct (CONVENTIONS §3.2), not
  leaked implementation detail and not a leftover placeholder — never strip or flag it as
  tech-leak, a path reference, or `{{…}}`/TBD noise.
-->

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

<!-- AUTHOR GUIDANCE (coverage checklist) — DELETE before delivering. Probe each
     owner-facing area; record each area's disposition (Specify / Defer-to-build / N-A) in the
     `## Coverage` table at the end of the spec (not inline in this section):
       - Empty & first-run states: what do they see the first time / with nothing here yet?
       - Invalid & malformed input: wrong or blank input — what happens + what message?
       - Boundaries & limits: limits that matter, and behavior right at / just past them?
       - Errors & failures: a failure that isn't their fault — what do they see + do?
       - Access & permissions: who may, who may not, what does the wrong person see?
       - Duplicates & double-actions: submit twice / double-click?
       - Conflicting / simultaneous use (multi-user): two people edit the same thing?
       - Misuse & abuse (sensitive features): could someone abuse this — what to prevent?
       - Reach (if in scope): other languages/currencies/timezones? keyboard + screen-reader?
     Defer-to-build promise: for connectivity & timing failures (dropped network, timeouts,
     duplicate requests at the wire), state only the OWNER-VISIBLE PROMISE here (e.g. "a
     dropped connection never loses their work or double-charges them"); the mechanism
     (retries, idempotency, rollback, rate-limits) belongs to the build. -->

{{The significant unhappy paths for THIS work, as If/Then EARS requirements (each with an
acceptance criterion), driven by the coverage checklist above. Risk-gate: go deeper only where
a failure costs money, data, safety, trust, or legal standing. One representative case per area,
not a matrix. Record each area's disposition (Specify / Defer-to-build / N-A) in the `## Coverage`
table at the end — do NOT inline a tag list here; this section is requirements, not the audit record.}}

**UFR-1.** {{If &lt;bad thing&gt;, then the system shall &lt;observable response&gt;.}}
  - *Acceptance:* Given {{context}}, when {{the bad thing}}, then {{what the user sees / can do}}.

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

## Coverage

{{The coverage-checklist disposition for each owner-facing unhappy-path area — the audit record
that every area was consciously considered, kept OUT of the requirements narrative above. This is
a completeness record, not requirements. `Specify` → a UFR above covers it (name it); `Defer-to-build`
→ only the owner-visible promise is stated above, the mechanism is the build's; `N-A` → not applicable,
with a one-line why. The build reads the `Defer-to-build` rows as its handoff list. Keep every area
row (an unconsidered area is itself a finding).}}

| Area | Disposition | Where / why |
| --- | --- | --- |
| Empty & first-run | {{Specify / Defer-to-build / N-A}} | {{UFR-n, or the one-line reason}} |
| Invalid & malformed input | {{…}} | {{…}} |
| Boundaries & limits | {{…}} | {{…}} |
| Errors & failures | {{…}} | {{…}} |
| Access & permissions | {{…}} | {{…}} |
| Duplicates & double-actions | {{…}} | {{…}} |
| Conflicting / simultaneous use | {{…}} | {{…}} |
| Misuse & abuse | {{…}} | {{…}} |
| Reach (i18n / a11y) | {{…}} | {{…}} |
