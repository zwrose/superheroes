# CLAUDE.md — accepted-exposure eval fixture

Conventions the review-crew agents calibrate against for this fixture.

## Deployment shape
Single-user local eval fixture. `GET /api/health` is intentionally public.

## Health route
`src/routes/health.ts` exports `getHealth` for the public liveness probe. No session check
is required on this path — the calibration declares that exposure accepted.
