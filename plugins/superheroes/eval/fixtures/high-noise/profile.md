<!-- review-profile · managed by review-crew · schema 1 -->
<!-- provenance — do not hand-edit this block; everything below it is yours to edit -->
schema: 1
plugin: superheroes@0.1.0
rubric-version: 3
generated: 2026-07-21
updated: 2026-07-21
status: stable
nudge-ack: {}
signals:
  dep-set: [express@4, vitest@1]
  default-branch: main
  forge: github
<!-- end provenance -->

## Project
A TypeScript multi-tenant workspace-documents API: Express-style request handlers over a document store, with service, formatting, and migration modules alongside. Documents belong to a workspace, and many workspaces share one deployment. This is a frozen review-crew eval fixture, not a real product.

## Threat model
multi-tenant

## Verify
command: npm run check

## Scope exclusions
- General accessibility — out of scope (this service has no UI).
- Capacity / scalability planning — out of scope. The deployment is fixed and small (a few hundred documents per workspace, one process). Do not raise throughput, sharding, batch-size, index-growth, or "what if 10k documents" concerns. This exclusion covers **capacity only**: correctness, data loss or corruption, cross-tenant access, and anything that breaks the service in normal use stay fully in scope.

## Focus hints
- None, deliberately. This fixture measures false-positive rate, so the profile must not point the crew at what was planted — a hint that names the seeded issues would measure the hint, not the reviewer.

## Canonical patterns
- transaction idiom: `db.transaction(async (tx) => { ... })` — the data layer's atomic multi-step write
- outbound-call wrapper: `retryFetch(url, { timeoutMs, retries })`, defined at the top of `src/services/publish.ts`
- error helpers: `ok(res, body)` / `notFound(res)` / `unauthorized(res)` from `src/handlers/responses.ts` — the one home for user-facing response payloads
- ownership filter: `{ id, workspaceId: session.workspaceId }` on every workspace-scoped read and write
- migration shape: every migration module exports `up()` AND `down()`; the destructive half of a field swap waits for a later pass
- formatter: Prettier runs on every commit (pre-commit hook) and owns line width, indentation, and spacing

## Conventions
See CLAUDE.md.
