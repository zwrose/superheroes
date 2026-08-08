# Coverage map — front-half-sdlc-core-6181ee

Acceptance-level allocation (FR-27): every acceptance criterion owned by exactly one child;
each FR/UFR group marked as faces of one behavior allocates as one. UFR-10 is the one
declared split — the spec itself gives it two parents (FR-13 and FR-37) and two acceptance
bullets; each bullet is allocated once, to its parent's child.

Children: C1 issue-contract seam · C2 anchor invariant · C3 routing + builder boundary ·
C4 discovery · C5 spec content + amendments · C6 epic machinery · C7 closure · C8 adoption.
Sequencing: C1 first (FR-30 — R1/R2 are its seam); C6 before C7 (closure rides epic
machinery); C8 last (adoption runs against shipped doctrine); C2–C5 sequence by charter-file
overlap at launch, disjoint pairs parallel.

| Requirement (with failure faces) | Acceptance criteria | Owner |
| --- | --- | --- |
| FR-1 (anchor kinds) + FR-2 (advisor records at filing) | FR-1 rule; FR-2 given/when/then | **C2** |
| FR-3 (intake resolution) + UFR-1 (unresolvable anchor) + UFR-9 (superseded ruling anchor) | FR-3 both bullets; UFR-1 bullet; UFR-9 bullet | **C2** |
| FR-4 (vet diff layer) + UFR-2 (uncovered new behavior) | FR-4 bullet; UFR-2 bullet | **C2** |
| FR-5 (four routes) + FR-6 (no size/lane at routing) | FR-5 both bullets; FR-6 rule | **C3** |
| FR-7 (skeleton) + FR-8 (empty-Anchor block) + FR-9 (DoD bar) + FR-10 (one-hop currency) | FR-7 rule; FR-8 bullet; FR-9 rule; FR-10 bullet | **C1** |
| FR-11 (one front door; rulings need no discovery) | both bullets + rule | **C4** |
| FR-12 (consent before spend) | both bullets | **C4** |
| FR-13 (three exits) + UFR-10a (abandoned discovery — first acceptance bullet) | FR-13 both bullets; UFR-10 bullet 1 | **C4** |
| FR-14 (adaptive elicitation) + FR-15 (prose options) | FR-14 rule; FR-15 bullet | **C4** |
| FR-16 (weight call) + FR-17 (light spec same class) | FR-16 both bullets; FR-17 rule | **C4** |
| FR-18 (Dispositions table) + FR-19 (elicitation test) | FR-18 rule; FR-19 rule | **C5** |
| FR-20 (failure semantics) + FR-21 (learning loop) | FR-20 bullet; FR-21 rule | **C5** |
| FR-22 (amendments + classes) | both bullets | **C5** |
| FR-23 (consolidation guideline) + FR-24 (annex rule) + FR-25 (no rulings ledger) | FR-23 rule; FR-24 rule; FR-25 rule | **C5** |
| FR-26 (spec vet + fixed sequence + dated approval) | all three rules | **C6** |
| FR-27 (coverage map) + UFR-3 (unallocated criterion) | FR-27 bullet; UFR-3 bullet | **C6** |
| FR-28 (register) + FR-29 (decide-by) | FR-28 rule; FR-29 rule | **C6** |
| FR-30 (seam first) + FR-31 (verbatim quotes + machine check) | FR-30 bullet; FR-31 rule | **C6** |
| FR-32 (package read) + UFR-7 (ceiling park) | all four FR-32 rules; UFR-7 bullet | **C6** |
| FR-33 (post-approval only; re-entry) | both rules | **C6** |
| FR-34 (reciprocal seams) + FR-35 (vet register row) + UFR-6 (undisclosed drift) | FR-34 rule; FR-35 bullet; UFR-6 bullet | **C6** |
| FR-36 (single-issue fast path) | rule | **C6** |
| UFR-4 (mid-flight amendment propagation; failure face of the amendment and register rules, both owned above) | bullet | **C6** *(machinery side; the class definitions are C5's — the seam is register entry R4)* |
| FR-37 (closure receipt) + UFR-8 (failing validation run) + UFR-10b (abandoned child — second acceptance bullet) | FR-37 bullet; UFR-8 bullet; UFR-10 bullet 2 | **C7** |
| FR-38 (delivery acceptance) + UFR-5 (partial delivery) | FR-38 rule; UFR-5 bullet | **C7** |
| FR-39 (builder boundary — no inline discovery) | bullet | **C3** |
| FR-40 (adoption pass) | bullet + rule | **C8** |

## Non-functional requirements — package-wide

The three NFRs (owner reading load; plain language; guidelines over trip-lines) are
constraints on every child, graded at each child's vet and re-checked in the closure
receipt (C7). They allocate to no single child; a child introducing an owner gate that
reads outside the NFR's artifact list, plugin-internal vocabulary unglossed, or a number
hardened into a gate, takes the finding.

## Spec DoD — closure mapping (C7 assembles; demonstrating child named)

| Spec DoD bullet | Demonstrated by |
| --- | --- |
| Anchor enforcement exercised at all three layers | C1 (filing refusal FR-8) + C2 (intake stop UFR-1; vet flag UFR-2) |
| Spec artifact carries Dispositions + Amendments; light = same class | C5 (+ C4 for the light-weight path) |
| Epic decomposition artifacts + package read trail + register vet row | C6 |
| Final-child vet carries closure receipt; owner delivery decision rides it | C7 |
| Discovery presents prose options, never a pick-one widget | C4 |

## Amendments

None yet — map drafted 2026-08-08, ahead of the package read.
