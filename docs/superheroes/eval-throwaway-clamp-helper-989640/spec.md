---
superheroes: doc
schemaVersion: 1
docType: spec
workItem: eval-throwaway-clamp-helper-989640
issue: null
size: small
status: approved
gates: {review: passed}
approved: "2026-06-27"
producedBy: "the-architect@0.2.0"
created: "2026-06-27"
updated: "2026-06-27"
---
# Eval throwaway: a pure `clamp` helper

## Purpose

A deliberately tiny, disposable work-item that exists **only** to prove the live
showrunner can drive an approved spec end-to-end to a ready-for-review pull request.
It adds one pure, dependency-free Python helper plus its unit tests. There is no
user-facing surface and no behavioral/browser dimension — this is intentionally the
smallest CI-safe change that still exercises the full plan → tasks → build → review →
PR → ship pipeline. After the run is observed it is discarded (PR closed, branch
deleted).

## Background / context

The repo is a Claude Code plugin marketplace. Plugin library code lives under
`plugins/superheroes/lib/` with unit tests under `plugins/superheroes/lib/tests/`.
CI runs three manifest/skill validators and a `pytest` sweep over the lib tests. A
new pure helper plus a pytest test fits this layout and passes CI without touching
any manifest, skill, or schema.

## Functional requirements

- **FR-1 — `clamp(value, lo, hi)` exists.** Add a new module
  `plugins/superheroes/lib/eval_throwaway_clamp.py` exporting a single pure function
  `clamp(value, lo, hi)`.
- **FR-2 — in-range values pass through.** When `lo <= value <= hi`, `clamp` returns
  `value` unchanged.
- **FR-3 — out-of-range values are bounded.** When `value < lo`, return `lo`; when
  `value > hi`, return `hi`.
- **FR-4 — invalid bounds raise.** When `lo > hi`, raise `ValueError` with a clear
  message; the function never silently returns on inverted bounds.
- **FR-5 — numeric-general.** Works for both `int` and `float` inputs (no type
  coercion beyond Python's native comparison); e.g. `clamp(2.5, 0, 2) == 2`.

## Non-functional requirements

- **Pure & dependency-free.** No imports beyond the standard library; no I/O, no
  global state, no side effects. The function is deterministic.
- **Tested test-first (TDD).** Unit tests live at
  `plugins/superheroes/lib/tests/test_eval_throwaway_clamp.py` and cover each FR
  (in-range pass-through, below-low, above-high, the boundary equals, the inverted-bounds
  `ValueError`, and a float case). Tests are written before the implementation.
- **CI-clean.** The change passes the three validators and the full `pytest` set with
  no new warnings; it touches no manifest, skill, rubric, or schema file.

## Significant unhappy paths

- **Inverted bounds (`lo > hi`)** → `ValueError`, asserted with `pytest.raises`.
- **Value exactly on a boundary** (`value == lo` or `value == hi`) → returned
  unchanged (boundaries are inclusive).

## Definition of done / success

- `plugins/superheroes/lib/eval_throwaway_clamp.py` defines `clamp(value, lo, hi)`
  satisfying FR-1…FR-5.
- `plugins/superheroes/lib/tests/test_eval_throwaway_clamp.py` asserts every FR and
  both unhappy paths, written test-first, all green under
  `python3 -m pytest plugins/superheroes/lib/tests/test_eval_throwaway_clamp.py -q`.
- The full CI set (three validators + the lib/eval/scripts pytest sweep) stays green.
- A ready-for-review pull request is opened against the default branch (never merged).

## Out of scope

- Any change to manifests, skills, rubrics, schemas, or the showrunner itself.
- Any user-facing, web, or browser surface (test-pilot applicability is expected to be
  N/A and should gracefully skip).
- Configurable behavior beyond the three positional arguments.

## Assumptions

- The disposable branch and PR this run produces will be discarded after the run is
  observed; the GitHub churn is the accepted cost of real end-to-end evidence.
