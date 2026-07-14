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
updated: "2026-07-13"
---
# Acceptance-harness fixture — Spec

## Purpose

A throwaway, canned work-item the standalone showrunner acceptance harness runs end-to-end
to prove the pipeline still reaches a ready-for-review PR. It is the cheapest possible real
change: creating one two-line text file on the branch — a seeded one-line baseline plus one
dated line below it. It exists only to exercise the showrunner; it is never merged, and every
artifact it creates is torn down by the harness.

## Functional requirements

- **FR-1:** Create `target.txt` on the work-item branch containing exactly two lines: the
  one-line baseline seeded from the copy shipped alongside the work-item's docs, and exactly
  one dated line below it. The branch starts without the file. No other file is touched,
  created, or deleted.

## Definition of done

All judged on the branch's net diff and file content — never on commit count or structure
(the execution engine may fold work into a single commit):

- The branch's net diff adds exactly one file, `target.txt`, with exactly two lines: the
  seeded baseline line first, one dated line below it.
- No file other than `target.txt` is modified anywhere on the branch.
- The change is shippable to a ready-for-review PR with green CI.
