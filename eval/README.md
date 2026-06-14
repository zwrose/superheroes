# superheroes — band eval harness

The cross-plugin / loop-level measurement instrument for the superheroes band. It
generalizes the pattern proven in [`plugins/review-crew/eval/`](../plugins/review-crew/eval/)
(per-plugin review-quality evals stay there; this harness is for the *band* and the
*loop*).

## The model (from review-crew/eval, generalized)

- **Frozen fixtures + ground truth.** A fixture is a self-contained input plus an
  expected result. Fixtures are **frozen** — you add new ones, you never weaken an
  existing one to make something pass.
- **Deterministic scorer.** Matching is mechanical and re-runnable, not vibes.
- **A gate.** A change must clear the gate (non-regression, or a mechanical bar) before
  it lands.
- **Liveness smokes.** Unit tests assert the fixtures/spec actually resolve and can fire.

## Two tracks

**1. Conformance (deterministic) — live now.** Does an implementation match the locked
contracts in [`CONVENTIONS.md`](../CONVENTIONS.md)? This is buildable today because the
conventions are frozen and these checks need no running loop:

- [`lib/identifiers.py`](lib/identifiers.py) — the **canonical reference impls** of the
  new §6 pure functions (`work_item_slug`, `content_hash`). The executable spec of §6.
  Plugins consume these instead of re-implementing them, so they can't drift (the #1
  theme of the convention reviews). *How a plugin consumes them — vendor vs shared dep —
  is decided when the first plugin needs them (Phase 1+).*
- [`lib/schemas/`](lib/schemas/) — JSON Schemas for the locked artifacts (define-doc
  frontmatter, `checkpoint.json`, `queue.json`, `registry.json`). The canonical shape
  any plugin's output is validated against.
- [`lib/tests/`](lib/tests/) — determinism / freeze / collision tests for the impls,
  and accept/reject tests for the schemas.

**2. Behavioral & loop — populated as plugins land.** Does the loop *do the right
thing*? (define producing a sound spec/plan/tasks; each review gate actually blocking a
bad artifact; the loop surviving interruption and producing a PR that meets the spec's
acceptance criteria.) These need a runnable loop, so their fixtures arrive with the
plugins that produce them — Phase 1 onward. `fixtures/` is the placeholder home.

## The gate

What a phase must pass is specified in [`gate.md`](gate.md). Today it defines the
**Phase-1 gate** ("one issue, evals-gated"): the deterministic conformance subset is
enforceable now; the behavioral checks are filled in as Phase 1 builds the loop.

## Running

```bash
python3 -m pytest eval/lib/tests/ -q
```

(`jsonschema` is needed for the schema-validation tests; the identifier tests are
dependency-free. CI installs it.)
