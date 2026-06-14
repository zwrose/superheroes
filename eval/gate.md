# Phase-1 gate — "one issue, evals-gated"

Phase 1 (see [ROADMAP.md](../ROADMAP.md)) takes a single work-item through the full loop
— Discovery → Plan → Tasks → Build → Verify → Integrate — with a human watching. This is
what must pass before that run counts as **correct**. Checks marked **[live]** are
enforceable today (deterministic conformance); **[Phase 1]** checks are behavioral and
get their fixtures as the loop is built.

## Conformance — deterministic

- **[live] Identifiers via the reference impls.** The work-item slug and the work-branch
  content-hash are produced by [`lib/identifiers.py`](lib/identifiers.py) (or a vendored
  copy proven equal to it), not re-derived ad hoc. Covered by `lib/tests/test_identifiers.py`.
- **[live] Artifacts validate against their schemas.** Every define-doc's frontmatter,
  and every `checkpoint.json` / `queue.json` / `registry.json` the loop writes, validates
  against [`lib/schemas/`](lib/schemas/). Covered for the schemas themselves by
  `lib/tests/test_schemas.py`; the loop's *emitted* artifacts get checked once define/producer exist.
- **[Phase 1] Gate-state coherence.** A define-doc's `status` is consistent with its
  `gates.review` (`approved` iff `passed`, CONVENTIONS §3.1); `checkpoint.json` `gates`
  aggregates the per-doc gates.

## Behavioral — the loop does the right thing

- **[Phase 1] End-to-end completion.** The work-item reaches Integrate and produces a PR
  whose diff satisfies the `spec`'s acceptance criteria.
- **[Phase 1] Gates actually block.** Each review gate (review-spec / review-plan /
  review-tasks) is shown to **stop** a seeded-bad artifact (a deliberately flawed
  spec/plan/tasks fixture must not pass review), not just rubber-stamp.
- **[Phase 1] Behavioral proof.** test-pilot exercises the change and the run leads with
  "here's it working" before the human spot-check.

## Resume / idempotency — a taste now, the rest in Phase 2a

- **[live] Content-hash determinism.** The same approved tasks doc hashes identically
  across runs (so two resumers mint the same branch) and ignores volatile metadata.
  Covered by `lib/tests/test_identifiers.py`.
- **[Phase 2a] Full resume.** Killing the loop mid-phase and resuming reads the same
  branch from `checkpoint.json`, re-acquires the lease, and neither loses nor duplicates
  work. (Phase 2a-core; the crash/compaction spike.)

## Rule

Don't weaken a fixture or relax a schema to make a run pass — the fixtures and schemas
are the frozen ground truth. Fix the implementation, or add a new fixture.
