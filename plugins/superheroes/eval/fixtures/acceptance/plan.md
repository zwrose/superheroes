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
updated: "2026-07-02"
---
# Acceptance-harness fixture — Plan

## Overview

Realize FR-1 with the smallest possible change: append one dated line to the tracked file
`target.txt`. There is no code, no dependency, no configuration — only a single-file text edit
exercised through the full pipeline so the acceptance harness can judge a real terminal outcome.

## Goals & non-goals

- **Goal:** Append exactly one dated line to `target.txt` and ship it to a ready-for-review PR.
- **Non-goal:** Any behavior, any second file, any merge. The change is intentionally trivial.

## Architecture

The fixture is a single text file, `target.txt`. The build appends one line to it. There are no
components, modules, or interfaces — the "architecture" is one append to one file.

## Components & interfaces

- `target.txt` — the sole artifact. One append; no reader, no other writer.

## How the requirements are met

- **FR-1** is met by the single task's append step, which writes exactly one dated line below
  the existing content of `target.txt` and touches nothing else.

## Key decisions & alternatives

- **Decision:** One-file append, no test harness of its own. **Alternative considered:** a code
  change with unit tests — rejected as needlessly expensive for a pipeline-exercising fixture.

## Risks & mitigations

- **Risk:** the append drifts to touch more than one file. **Mitigation:** the single task's
  steps name `target.txt` as the only path; the harness drift-check anchors on it.

## Dependencies & assumptions

- **Assumption:** `target.txt` exists in the checkout. The harness drift-check verifies this
  before a run and fails naming the missing target otherwise.
