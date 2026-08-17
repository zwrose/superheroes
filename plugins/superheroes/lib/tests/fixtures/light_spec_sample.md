---
superheroes: doc
schemaVersion: 1
docType: spec
workItem: light-spec-sample-a1b2c3d4
issue: null
parent: null
size: small
status: approved
approved: "2026-08-16"
gates: {review: passed}
producedBy: "the-architect@0.29.1"
created: "2026-08-16"
updated: "2026-08-16"
---
# Light spec sample

## Purpose

Give plugin users a tiny, owner-approved spec fixture that proves a light-weight
definition-doc is the same artifact class as a full spec — omitting empty sections
without weakening anchor power or approval authority.

## Who it's for

- **Plugin maintainers** — who need a realistic small spec in conformance tests.
- **The owner** — who approves only what they have read and can grade.

## Functional requirements

**FR-1.** When a conformance test reads this fixture, the test shall treat it as a
`spec` definition-doc with `size: small` and owner-approved status.
  - *Acceptance (rule):* `read_frontmatter` reports `docType: spec`, `status: approved`,
    and a dated `approved` field.

**FR-2.** When a test copies this fixture to a temp root, `set_gate` shall accept a
`passed` review fence on the copy without mutating the committed fixture.
  - *Acceptance:* Given a temp copy of the fixture, when `set_gate(..., "passed", ...)`
    runs with the copy's content hash, then the call returns `ok: True` and the copy
    still shows `gates: {review: passed}`.

## Definition of done / success

An integrator can run the light-spec equivalence cluster against this file alone and
see every heading trace to `templates/spec.md`, every omitted section stay absent,
and every retained section carry real prose.

## Constraints

The fixture stays in `lib/tests/fixtures/` so it ships inside the plugin bundle and
never lands in a project's `docs/superheroes/` tree during ordinary use.

## Out of scope

Full unhappy-path coverage, glossary terms, open questions, and non-functional bars —
this sample exists only to exercise the four equivalence labels.
