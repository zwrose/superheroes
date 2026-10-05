# spec-alignment-landing-2026-10-05 — the landing epic of the alignment specs

**Specs (owner-approved 2026-10-04, committed in this repository):**

- Spec A, the alignment flow: [`docs/superheroes/aligning-on-what-to-build-6da1ee/spec.md`](../aligning-on-what-to-build-6da1ee/spec.md)
  (workItem `aligning-on-what-to-build-6da1ee`): the owner-vs-craft line, "who it's for", Canon, the
  discovery flow and the review cycle.
- Spec B, the review surface: [`docs/superheroes/the-review-surface-d59417/spec.md`](../the-review-surface-d59417/spec.md)
  (workItem `the-review-surface-d59417`): the Comic panel theme, the shared review template, cards,
  sheets and image zoom.

Approval is recorded in both specs' frontmatter (`approved: "2026-10-04"`) and in the discovery
handoff, `docs/superheroes/discovery-notes/spec-alignment/HANDOFF.md`, ruling 62. Both specs' Amendments
logs are empty, so every child anchors at `as-of amendment #0`. Per Spec A FR-39, this breakdown rides
the spec PR, #1614, and one merge word covers specs and breakdown; the children file, with the
owner's word, as it merges.

This folder holds the decomposition artifacts. The specs live in their own work-item folders; one
package covers both because Spec A relies on Spec B's sheets and theme, and the seams between them
(the sheet data file, how answers come back, the theme file) are register entries both sides quote.

- [`coverage-map.md`](coverage-map.md): every criterion of both specs (117) owned exactly once by a child.
- [`register.md`](register.md): the cross-child contract register (25 entries); children quote it verbatim.
- [`epic.md`](epic.md): the epic issue body, as it would be filed.
- `children/C1.md` to `children/C8.md`: the child (feature) issue bodies, as they would be filed.
- `children/C4-L1.md` to `C4-L4.md`, `C5-L1.md`, `C5-L2.md`, `C7-L1.md`, `C7-L2.md`, `C8-L1.md` to `C8-L4.md`: the twelve layer sub-issue bodies of the four stacked children.
- `package-read-audit.md`: not yet started; the independent package read writes it before the children file.

## The children

| Child | What | Spec | Criteria | Size (non-test lines) | Stack | Lane | Presentation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [C1](children/C1.md) | Canon, the seam: contract doc, resolver lookup, anchor-resolution amendment, covenant pointer, this repo's Canon seed | A | 13 | ~330 shipped + ~150 seed | no | full | say it |
| [C2](children/C2.md) | The owner-vs-craft line: one rubric home, every older statement repointed, door rules as cases | A | 11 | ~350 | no | full | say it |
| [C3](children/C3.md) | Configuration items: "who it's for" (item 14), item 13 → Canon with its migration, the spec-reviewer seat | A | 3 | ~280 | no | full | say it |
| [C4](children/C4.md) | The discovery flow: grounding and questions, boards, writing with source tags, sheets and the handoff | A | 31 | ~1,150 | 4 layers | full | show it |
| [C5](children/C5.md) | The three checks, then review-spec's retirement and the weight call's | A | 18 | ~1,750 | 2 layers | full | say it |
| [C6](children/C6.md) | The advisor's vet and the approval handoff: vet never fixes, breakdown on the same PR, one merge word | A | 6 | ~250 | no | full | show it |
| [C7](children/C7.md) | The Comic panel theme and the review template's shell, with the sheet data schema | B | 8 | ~600 | 2 layers | full | show it |
| [C8](children/C8.md) | Cards, sheets, images and answers: the owner-facing sheet, phone and desktop, final sheet, zoom | B | 27 | ~1,200 | 4 layers | full | show it |

Total: about 5,900 shipped non-test lines (plus C1's ~150-line Canon seed for this repository) across eight children and twelve planned layers (C4 4, C5 2, C7 2,
C8 4). Every child is `kind:product` and on the full lane: each one changes doctrine or behaviour that
every later session or every sheet depends on, and the failure in each is quiet.

## Sequencing

Seam first, on each side:

- **Wave 0:** C1 (Spec A's seam: every A child writes or reads Canon) and C7 (Spec B's seam: the theme,
  the shell and the sheet data schema). They share no surface, so they run in parallel.
- **Wave 1:** C3 after C1 (its migration writes Canon entries); C8 after C7.
- **Wave 2:** C2 after C1 and C3 (its sorting rule reads Canon; its "no setting moves the line"
  criterion needs item 13 pointing at Canon); C5 after C1 and C3 (the source check reads Canon; the
  checks read the spec-reviewer seat).
- **Wave 3:** C6 after C5 (both rewrite showrunner duty 1) and C2 (it points at the line's home).
- **Wave 4:** C4, which consumes every other child. Its lower layers may start as their own
  dependencies land: layer 1 after C1, C2 and C3; layer 2 after C7; layer 3 after C5; layer 4 after C6
  and C8.

The longest chain is C1 → C3 → C5 (two layers) → C6 → C4 (four layers). **Release note for the
advisor:** if a release cuts mid-epic, a consuming project could adopt a partial flow. Each child is
built to leave the plugin coherent on its own (C5's retirement points today's discovery at the three
checks, so discovery always has a review), but the advisor may prefer to hold the release until C4
lands so weekly-eats adopts the whole flow at once.

## Changes from the starting sketch, and why

- **FR-12 moved from C3 to C4.** It is a step of discovery's grounding ("when discovery grounds
  itself, then it recommends the advisor setup"), and the discovery skill has one owner; C3 still
  provides item 14, the value FR-12 reads.
- **FR-18 and the item-13 migration moved from C1 to C3.** Every change to configure
  (`lib/project_config.py`, the view, set-up and engine preferences) sits in one child, so one surface
  has one builder; C3 is sequenced after C1, so the migration writes C1's entry shape. The register
  carries the item numbers once (R10) for C2, C3 and C4.
- **FR-15's second bullet (the advisor's Canon writes) moved from C1 to C6.** It is the advisor's
  own write path; the advisor's holding step before its next PR is decide-by C6 (R5). This is the
  package's one declared split.
- **FR-38 and FR-38a (the final sheet and the re-approval loop) are C4's, not C6's.** Both are
  discovery's acts; C6 keeps the advisor's side (FR-37, FR-39, UFR-6, duty 1). The vet record between
  them is R21, decide-by C6, so C6 is sequenced before C4.
- **FR-43 stays in C3**, with the seat's shape decided now (R11) so C5 reads a key C3 has landed.
- **C5 is a two-layer stack:** the checks first, then the retirement, so discovery is never without a
  review. The front-half-sdlc-core FR-16/17 amendment was recorded by the advisor in PR #1614
  at approval; C5's second layer owns its coverage row and confirms it.
- **The glossary terms** are spread by owner (R24): Canon, ceded call and standing ruling with C1;
  the line with C2; remainder sheet and ready for vet with C4; card and sheet with C8.
- **This repository's own Canon seed** (Spec A's reading note: the decisions among the handoff's
  rulings "move into Canon once Canon exists") is C1's, as the contract's first real use.

## Owner-sensitive choices

R7 is the one register entry that touches the covenant, the short form of PHILOSOPHY that every
session carries: it adds two pointer lines there (to Canon's contract doc and to the owner-vs-craft
line's home) and restates nothing, and it is named here for the owner's veto at the merge word.

## Cross-epic seams

- **The review-overhaul discovery (#1472)** has no spec yet. Spec A's assumption (ruling 57) ties
  "who it's for" and the review overhaul's risk profile into one setup sitting, with the home of
  risk-tolerance records decided once, with that discovery. Register R12 records the seam on this
  side, consumed by C3. **Reciprocal seam owed:** when #1472's spec is approved, its register (or its
  single child's issue body) must quote R12; until then the seam is recorded on one side only by
  necessity, and the package read should treat it as owed, not as a collision.
- **front-half-sdlc-core-6181ee** is amended (FR-16, FR-17) by Spec A's approval, not decomposed
  again; its children have landed, so no live child needs notifying. The advisor records the amendment in
  that spec's Amendments log in PR #1614, at approval.

## Milestone note

The open milestone "Review-spec keeps pace" names a skill C5 retires. Whether that milestone closes,
is renamed, or is folded once C5 lands is a train-level call for the advisor and owner, not this
package's.

## Consequences (from each child's consequence line)

A consuming project (weekly-eats) keeps today's behaviour until it adopts the release that carries
the children: rulings stay where it records them today, item 13 keeps its value, review-spec and the
weight call stay, its advisor keeps delivering "ready for your approval", and owner calls arrive as
chat prose. At adoption its item-13 value moves into Canon, its next discovery runs the new flow, and
its specs get the three checks. A Codex host gets Canon and the checks unchanged, boards as local
HTML files, and sheets as numbered chat prose.

## Owed before filing

- The independent package read (decomposition.md § The adversarial package read), with its audit
  trail written through `lib/package_read_audit.py`.
- The filing dry-run over every body (epic, eight children, twelve layers), recorded in the audit
  trail. The children's and layers' build-ready and register checks pass on this draft; each layer's
  binding register check uses its feature issue's body and child token, and the layer tokens on the
  register's `*Consumers:*` lines let the same check also prove each layer's own quotes.
