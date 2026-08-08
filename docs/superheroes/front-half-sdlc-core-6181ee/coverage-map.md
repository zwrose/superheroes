# Coverage map — front-half-sdlc-core-6181ee

Acceptance-level allocation (FR-27): every acceptance criterion owned by exactly one child;
each FR/UFR group marked as faces of one behavior allocates as one. Four declared splits,
each at the spec's own acceptance-bullet granularity — each criterion still owned exactly
once: UFR-10 (two parents, two bullets — one each to C4/C7); FR-1 (refusal rule to C1 with
FR-8; kinds requirement to C2); FR-11 (routing bullets to C3; front-door rule to C4);
FR-31 (charter rule to C6; checker artifact to C9).

Children: C1 issue-contract seam · C2 anchor invariant · C3 routing + builder boundary ·
C4 discovery · C5 spec content + amendments · C6 epic machinery · C7 closure · C8 adoption ·
C9 exact-text checker.

**Sequencing (FR-30 + round-1 finding B4):** C1 first (R1/R2 are the seam), then C9 (R3's
checker — C2 and C6 integrate it). C2–C5 launch after C9 with charter-file overlaps
sequenced at launch (disjoint pairs parallel). **C6 launches only after C2 and C3 merge**
(shared showrunner vet-duty and workhorse-intake surfaces). C7 after C6. C8 last. The
detective child (sibling spec) is ordered freely per R9's landing rule.

| Requirement (with failure faces) | Acceptance criteria | Owner |
| --- | --- | --- |
| FR-1 anchor-kinds requirement + FR-2 (advisor records at filing) | FR-2 given/when/then | **C2** |
| FR-1 acceptance rule (no anchor ⇒ cannot mark build-ready) | FR-1 rule | **C1** *(one gate with FR-8 — round-1 finding C1)* |
| FR-3 (intake resolution) + UFR-1 (unresolvable anchor: stop-report AND advisor repair) + UFR-9 (superseded ruling anchor) | FR-3 both bullets; UFR-1 bullet; UFR-9 bullet | **C2** |
| FR-4 (vet diff layer) + UFR-2 (uncovered new behavior) | FR-4 bullet; UFR-2 bullet | **C2** |
| FR-5 (four routes) + FR-6 (no size/lane at routing) + FR-11 routing bullets (ruled follow-up → build-ready; product question → discovery) | FR-5 both bullets; FR-6 rule; FR-11 second bullet | **C3** *(route selection exclusive — round-1 finding C2)* |
| FR-7 (skeleton) + FR-8 (empty-Anchor block) + FR-9 (DoD bar) + FR-10 (one-hop currency + whole-body state match) | FR-7 rule; FR-8 bullet; FR-9 rule; FR-10 bullet (both halves) | **C1** |
| FR-11 front-door rule (one door; no spike surface; ruling bypass defined) | FR-11 first rule | **C4** |
| FR-12 (consent before spend; wait-or-park on silence; sole mid-flight consent point) | both bullets, all three elements | **C4** |
| FR-13 (three exits, each artifact + ratification + report; no fabricated spec) + UFR-10a (abandoned discovery — first acceptance bullet) | FR-13 both bullets; UFR-10 bullet 1 | **C4** |
| FR-14 (adaptive elicitation) + FR-15 (prose options; free-form answers proceed) | FR-14 rule; FR-15 bullet | **C4** |
| FR-16 (weight call: line count AND interlocking sections; light AND full paths) + FR-17 (light spec same class: template, home, anchor power, approval authority; empty sections omitted) | FR-16 both bullets; FR-17 rule | **C4** |
| FR-18 (Dispositions table) + FR-19 (elicitation test) | FR-18 rule; FR-19 rule | **C5** |
| FR-20 (failure semantics) + FR-21 (learning loop) | FR-20 bullet; FR-21 rule | **C5** |
| FR-22 (amendment classes, in-place edit, log format; propagation MACHINERY delegated to C6 per R4) | both bullets (classification + log halves) | **C5** |
| FR-23 (consolidation: next-touch re-read + owner re-stamp; number stays guideline) + FR-24 (annex rule) + FR-25 (no ledger; absorption = recorded advisor judgment, never mechanical) | FR-23 rule (behavior included); FR-24 rule; FR-25 rule | **C5** *(exclusive — round-1 finding C8; C4 carries only the 10-line number)* |
| FR-26 (spec vet + fixed sequence + dated approval) | all three rules | **C6** |
| FR-27 (coverage map) + UFR-3 (unallocated criterion) | FR-27 bullet; UFR-3 bullet | **C6** |
| FR-28 (register) + FR-29 (decide-by) | FR-28 rule; FR-29 rule | **C6** |
| FR-30 (seam first) + FR-31 charter rule (verbatim quoting requirement; check invocations per R3's split) | FR-30 bullet; FR-31 rule (charter half) | **C6** |
| FR-31 checker artifact (the script, its invocation + result contract) | FR-31 rule (machine half) | **C9** |
| FR-32 (package read incl. seat composition per the 2026-08-08 amendment) + UFR-7 (ceiling park) | all five FR-32 rules; UFR-7 bullet | **C6** |
| FR-33 (post-approval only; re-entry; contradiction dispositions — package fix / owner-stamped amendment / recorded refutation, never a silent spec edit) | both rules | **C6** |
| FR-34 (reciprocal seams, incl. the single-issue shared-seam form) + FR-35 (vet register row) + UFR-6 (undisclosed drift) | FR-34 rule; FR-35 bullet; UFR-6 bullet | **C6** |
| FR-36 (single-issue fast path + shared-seam rule) | both rules | **C6** |
| UFR-4 (mid-flight amendment propagation, BOTH branches — register re-injection and spec-text coverage re-check — and both sides of a reciprocal seam; failure face of the amendment and register rules owned above) | bullet, all elements | **C6** |
| FR-37 (closure receipt) + UFR-8 (failing run: repair path AND the owner's disclosed-failure acceptance alternative) + UFR-10b (abandoned child — second acceptance bullet) | FR-37 bullet; UFR-8 bullet (both outcomes); UFR-10 bullet 2 | **C7** |
| FR-38 (delivery acceptance) + UFR-5 (partial delivery) | FR-38 rule; UFR-5 bullet | **C7** |
| FR-39 (builder boundary — no inline discovery) | bullet | **C3** |
| FR-40 (adoption pass) | bullet + rule | **C8** |

## Non-functional requirements — package-wide

The three NFRs (owner reading load; plain language; guidelines over trip-lines) are
constraints on every child, graded at each child's vet via **the standing NFR vet row C6's
charter work ships** (round-1 finding C13), and re-checked in the closure receipt's NFR
element (R8). A child introducing an owner gate that reads outside the NFR's artifact
list, unglossed plugin-internal vocabulary, or a number hardened into a gate takes the
finding.

## Spec DoD — closure mapping (C7 assembles; demonstrating child named)

| Spec DoD bullet | Demonstrated by |
| --- | --- |
| Anchor enforcement exercised at all three layers | C1 (filing refusal FR-8) + C2 (intake stop UFR-1; vet flag UFR-2) |
| Spec artifact carries Dispositions + Amendments; light = same class | C5 (template halves) + C4 (light-path equivalences, exercised per its DoD) |
| Epic decomposition artifacts + package read trail + register vet row | C6 (one recorded end-to-end package rehearsal in its handback — round-1 finding C14) |
| Final-child vet carries closure receipt; owner delivery decision rides it | C7 (one recorded closure rehearsal in its handback — round-1 finding C15) |
| Discovery presents prose options and free-form answers proceed | C4 (recorded rehearsal or completed live transcript in its handback) |

## Amendments

- **2026-08-08 (round-1 fold):** C9 added (checker child — finding B2); FR-1 refusal rule
  → C1 (finding C1); FR-11 routing bullets → C3 (finding C2); FR-23/FR-25 exclusivity +
  behavior in C5 (findings C8/C9); UFR-4 all-elements wording (findings A9/C11);
  sequencing extended to C6-after-C2+C3 (finding B4); NFR vet-row home named (finding
  C13); rehearsal demonstrations named in the closure mapping (findings C14/C15/C6-c4).
