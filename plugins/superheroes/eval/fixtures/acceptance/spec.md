---
superheroes: doc
schemaVersion: 1
docType: spec
workItem: acceptance-fixture-placeholder
issue: null
size: small
status: approved
gates: {review: passed}
producedBy: "the-architect@0.4.0"
created: "2026-07-02"
updated: "2026-07-02"
---
# Acceptance-harness fixture — Spec

## Purpose

A throwaway, canned work-item the standalone showrunner acceptance harness runs end-to-end
to prove the pipeline still reaches a ready-for-review PR. It is the cheapest possible real
change: appending exactly one dated line to a single tracked file. It exists only to exercise
the showrunner; it is never merged, and every artifact it creates is torn down by the harness.

## Functional requirements

- **FR-1:** Append exactly one line to `target.txt`. The appended line is a single dated
  line placed below the existing content; no other file is touched, created, or deleted.

## Definition of done

- `target.txt` has exactly one additional line versus its committed state.
- No file other than `target.txt` is modified.
- The change is shippable to a ready-for-review PR with green CI.
