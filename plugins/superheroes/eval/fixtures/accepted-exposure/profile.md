<!-- review-profile · managed by review-crew · schema 1 -->
<!-- provenance — do not hand-edit this block; everything below it is yours to edit -->
schema: 1
plugin: superheroes@0.1.0
rubric-version: 3
generated: 2026-09-16
updated: 2026-09-16
status: stable
nudge-ack: {}
signals:
  dep-set: []
  default-branch: main
  forge: github
<!-- end provenance -->

## Project
Accepted-exposure dry-run fixture for the security lens (C4). Not a real product.

## Threat model
single-user local eval fixture.

Accepted exposures (owner-ruled):
- Unauthenticated read of `GET /api/health` — intentional public liveness probe; cite this entry rather than flagging.

## Verify
command: true

## Scope exclusions
- General accessibility — out of scope.

## Focus hints
- security: honor accepted exposures declared above before raising IDOR/auth findings.

## Canonical patterns
- health route: `src/routes/health.ts` exports `getHealth`.

## Conventions
See CLAUDE.md.
