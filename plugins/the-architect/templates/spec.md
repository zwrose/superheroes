{{frontmatter}}
# {{Title}}

> Plain-language requirements for this work — the **what**, not the **how**.
> Owner co-authored. No technical implementation details (those live in the
> `plan`). Depth target: the happy path **plus the significant unhappy paths**
> that matter — not an exhaustive enumeration.

## Purpose

{{Why this work exists, in the owner's words: the problem or opportunity, and
who it's for. One short paragraph.}}

## Requirements

### Functional requirements

{{What the system must do on the happy path, as numbered behavioral
requirements. Each is owner-visible and verifiable — "the system does X when
the user does Y", not "use library Z".}}

1. {{…}}

### Behavior in significant unhappy paths

{{The anti-slop core. Cover the cases that genuinely matter for this work — not
every conceivable one. Delete rows that don't apply; add ones that do.}}

- **Empty / initial states:** {{what the owner/user sees before there is any
  data, on first run, or after everything is cleared.}}
- **Errors & failures:** {{what happens when something goes wrong (a save
  fails, a service is down, an action can't complete) and what the user is
  told.}}
- **Key edge & boundary cases:** {{limits, very large or unusual inputs,
  duplicates, simultaneous use — the boundaries where behavior must be
  pinned down.}}
- **Access & permissions:** {{who is allowed to do what; what an unauthorized
  or signed-out attempt results in.}}
- **Input validation:** {{what counts as valid input; how invalid input is
  rejected or corrected, and what the user sees.}}

### Non-functional requirements

{{Speed, scale, reliability, privacy, and security expectations — translated
into plain language ("results feel instant", "safe to use on a phone",
"only the owner can see their data"). Omit the section if there are none worth
stating.}}

## UI / UX

{{The outcome of any Claude Design / visual exploration done during Discovery,
captured as requirements (layout, key screens, states, tone). Reference the
visuals produced. Omit this section entirely if the work is not user-facing.}}

## Acceptance criteria

{{Owner-verifiable checks that say "this was built right" — one per important
behavior, including the significant unhappy paths above. These are what
`review-spec` and, later, the build's verification check against.}}

- [ ] {{…}}

## Out of scope

{{What this work explicitly does NOT include — the boundaries that keep it a
single, shippable piece. Naming these prevents scope creep during the plan and
build.}}

## Open questions

{{Anything still undecided. This section should be empty before the owner
approves the spec — resolve or defer each item first.}}
