# Phase-1 gate — "one issue, evals-gated"

> **Status (v2).** The **[live]** conformance rows for **identifiers and schema validation** remain CI-enforced and current. The content-hash / branch-addressing rows and the **[Phase 1]** behavioral rows describe the retired v1 loop (Discovery→Plan→Tasks with review-plan/review-tasks gates, #478/#479) and are historical — the v2 review-eval rebuild is scheduled in the S2 lane (epic #476).

Phase 1 (see [ROADMAP.md](../ROADMAP.md)) takes a single work-item through the full loop
— Discovery → Plan → Tasks → Build → Verify → Ship — with a human watching. This is
what must pass before that run counts as **correct**. Checks marked **[live]** are
enforceable today (deterministic conformance); **[Phase 1]** checks are behavioral and
get their fixtures as the loop is built.

## Conformance — deterministic

- **[live] Identifiers via the reference impls.** The work-item slug and the work-branch
  content-hash are produced by [`lib/identifiers.py`](lib/identifiers.py) (or a vendored
  copy proven equal to it), not re-derived ad hoc. Covered by `lib/tests/test_identifiers.py`.
- **[live] Artifacts validate against their schemas.** Every definition-doc's frontmatter,
  and every `checkpoint.json` / `queue.json` / `registry.json` the loop writes, validates
  against [`lib/schemas/`](lib/schemas/). Covered for the schemas themselves by
  `lib/tests/test_schemas.py`; the loop's *emitted* artifacts get checked once the-architect/producer exist.
- **[Phase 1] Gate-state coherence.** A definition-doc's `status` is consistent with its
  `gates.review` (`approved` iff `passed`, CONVENTIONS §3.1); `checkpoint.json` `gates`
  aggregates the per-doc gates.

## Behavioral — the loop does the right thing

- **[Phase 1] End-to-end completion.** The work-item reaches Ship and produces a PR
  whose diff satisfies the `spec`'s acceptance criteria.
- **[Phase 1] Gates actually block.** Each review gate (review-spec / review-plan /
  review-tasks) is shown to **stop** a seeded-bad artifact (a deliberately flawed
  spec/plan/tasks fixture must not pass review), not just rubber-stamp.
- **[Phase 1] Behavioral proof.** test-pilot exercises the change and the run leads with
  "here's it working" before the human spot-check.

## Resume / idempotency — full resume landed in 2a-core (resilience)

- **[live] Content-hash determinism.** The same approved tasks doc hashes identically
  across runs and hosts (so two resumers mint the same branch), ignores volatile
  metadata, and is NFC-stable for non-ASCII text. Pinned by a golden value in
  `lib/tests/test_identifiers.py`.
- **[Phase 1 — entry-gate] Content-hash canon-versioning.** When `content_hash` gets its
  first consumer (producer/the-architect), confirm the deferred decision from CONVENTIONS §6.4:
  a breaking change to the §6.3 canonicalization must bump the definition-doc `schemaVersion`,
  and decide whether to also embed an explicit canon-version in the stored branch key.
  (The `DEFERRED` comment in `lib/identifiers.py` marks the spot.)
- **[live — 2a-core] Full resume.** Killing the loop mid-phase and resuming reads the
  durable cursor from `checkpoint.json`, re-acquires the lease, reconciles against reality
  (reality-wins), and neither loses nor duplicates work. Pinned by the kill-resume
  exactly-once spike (`plugins/superheroes/lib/tests/test_kill_resume_spike.py`) plus the
  `recover` / `journal` / `lock` unit tests.

## Rule

Don't weaken a fixture or relax a schema to make a run pass — the fixtures and schemas
are the frozen ground truth. Fix the implementation, or add a new fixture.

### [Phase 2a-core] Escalation calibration

- **Layer 1 — routing-logic (deterministic, HARD GATE).** `escalation.py`'s floor-classifier,
  `route()` truth-table, `route()` fail-closed, the fixer file-scope guard, and the loop_state
  disposition-pipeline property must match the frozen fixture
  `plugins/superheroes/eval/escalation/expected.json` exactly (see
  `plugins/superheroes/eval/tests/test_escalation_eval.py` and `…/lib/tests/test_loop_state.py`).
  A change must clear this before it lands. The fixture is frozen ground truth — fix the code, never
  weaken the fixture.
- **Layer 2 — axis-assignment calibration (model-in-loop, TRACKED).** The model's ability to assign
  the rubric's axes on realistic scenarios (`…/eval/escalation/calibration.json`) is tracked as an
  escalation-accuracy measure (false-negative + false-positive escalations), not a deterministic
  blocking gate; it deepens with the producer/test-pilot harness.
