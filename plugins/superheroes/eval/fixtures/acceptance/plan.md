---
superheroes: doc
schemaVersion: 1
docType: plan
workItem: acceptance-fixture-placeholder
issue: null
parent: {workItem: acceptance-fixture-placeholder, docType: spec}
size: small
status: approved
gates: {review: passed}
producedBy: "the-architect@0.4.0"
created: "2026-07-02"
updated: "2026-07-13"
---
# Acceptance-harness fixture — Plan

## Overview

Realize FR-1 with the smallest possible change: create `target.txt` on the branch as the
seeded one-line baseline plus one dated line below it. There is no code, no dependency, no
configuration — a single-file text creation exercised through the full pipeline so the
acceptance harness can judge a real terminal outcome.

## Goals & non-goals

- **Goal:** Create the two-line `target.txt` (seeded baseline + one dated line) and ship it
  to a ready-for-review PR.
- **Non-goal:** Any behavior, any second file, any merge. The change is intentionally trivial.

## Architecture

The fixture is a single text file, `target.txt`. The build seeds its one-line baseline from
the copy shipped alongside the work-item docs and appends one dated line. There are no
components, modules, or interfaces — the "architecture" is one two-line file.

## Components & interfaces

- `target.txt` — the sole artifact. Seeded then appended in one task; no reader, no other
  writer.

## How the requirements are met

- **FR-1** is met by the single task: it copies the one-line baseline from the directory
  holding the work-item docs (where the harness places it), appends exactly one dated line,
  verifies the two-line shape and single-file scope, and commits — touching nothing else.

## Key decisions & alternatives

- **Decision:** The work item itself seeds the baseline. The branch is cut from a repo that
  does not carry `target.txt`, so seeding must be part of the task to keep every reviewer's
  spec-compliance judgment consistent with what the branch diff actually shows.
  **Alternative considered:** harness-side seeding before the run — rejected: the branch is
  minted mid-pipeline, after the harness hands off; the harness has nothing to commit onto.
- **Decision:** Judge outcomes on net diff and file content, never commit count — external
  engine adapters fold a task's work into one commit, so commit-structure requirements would
  be unsatisfiable on engine legs.
- **Decision:** One-file edit, no test harness of its own. **Alternative considered:** a code
  change with unit tests — rejected as needlessly expensive for a pipeline-exercising fixture.

## Risks & mitigations

- **Risk:** the change drifts to touch more than one file. **Mitigation:** the single task's
  steps name `target.txt` as the only path and verify it with `git status --porcelain`; the
  harness drift-check anchors on the target file.
- **Risk:** a retry or engine fall-open re-enters the task after partial progress.
  **Mitigation:** Step 1 is state-aware — it recognizes the completed two-line shape and
  reports done instead of failing, and STOPs only on genuinely foreign content.

## Dependencies & assumptions

- **Assumption:** the one-line, newline-terminated baseline `target.txt` ships alongside the
  materialized work-item docs (the harness places it next to this plan). The harness
  drift-check verifies the fixture carries the target file before a run; a CI test pins the
  committed baseline's one-line shape and that materialization copies it alongside the docs.
